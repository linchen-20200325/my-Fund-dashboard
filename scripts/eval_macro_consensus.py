#!/usr/bin/env python3
"""scripts/eval_macro_consensus.py — v19.27 純長期 vs 雙頭合議 歷史熊市命中率對照.

User 問題：「長期 macro 判斷對歷年熊市準不準？搭配短期轉折/雷達後呢？」
本腳本用既有 data_cache parquet 跑離線回測，產對照表回答。

對照組
======
A. **純長期**：Macro_Score（9-factor 簡化版）在 peak 前 ``lead-months`` 月相對下跌
   ≥ ``drop-threshold`` → hit。沿用 services.macro_validation.verify_score_vs_crises。
B. **雷達 proxy**：peak 前 ``radar-lookback`` 月內任一月 VIX 月均 > ``radar-vix``
   → 雷達 hit。
C. **雙頭合議 (A∪B)**：任一命中即視為「總經 + 雷達」聯合命中。

資料源（離線 parquet，無 IO）
=============================
- ``data_cache/fred_indicators.parquet``：BAMLH0A0HYM2 / CPIAUCSL / DGS10 / DGS2 /
  DGS3MO / M2SL / UNRATE / WALCL（8 series, 2011-06 → 2026-06）
- ``data_cache/spx_history.parquet``：SPX 日度 close
- ``data_cache/vix_history.parquet``：VIX 日度 close

⚠️ 已知限制
============
1. **2008 GFC / 2000 dot-com 不在範圍**：parquet 起始 2011-06。
2. **9 factors 而非 14**：parquet 缺 PMI / BREADTH / DXY / PPI / COPPER。
3. **FEDRATE 用 DGS3MO 代理**：FEDFUNDS 未 cache（DGS3MO 與 FEDFUNDS 相關 > 0.95）。
4. **雷達 proxy 只用 VIX**：完整 risk_radar 10 燈含 MOVE / HY OAS / SOX / 防禦vs攻擊
   等需重建日度序列，本版只用 VIX 月均作 first approximation。

CLI
===
    python scripts/eval_macro_consensus.py
    python scripts/eval_macro_consensus.py --threshold -0.15 --lead-months 3
    python scripts/eval_macro_consensus.py --radar-vix 28 --radar-lookback 2
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 讓 scripts/ 下執行也能 import services.*
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

import pandas as pd  # noqa: E402

from services.crisis_backtest import detect_crisis_events  # noqa: E402
from services.macro_score_calibration import compute_historical_score  # noqa: E402
from services.macro_validation import verify_score_vs_crises  # noqa: E402

CACHE_DIR = _REPO_ROOT / "data_cache"


# ════════════════════════════════════════════════════════════════
# §1 資料載入：parquet → monthly wide
# ════════════════════════════════════════════════════════════════
def load_fred_wide() -> pd.DataFrame:
    """讀 fred_indicators.parquet → pivot 成日頻 wide → resample 到月底."""
    df = pd.read_parquet(CACHE_DIR / "fred_indicators.parquet")
    df["date"] = pd.to_datetime(df["date"])
    wide = df.pivot(index="date", columns="series_id", values="value").sort_index()
    return wide.resample("ME").last()


def load_spx_monthly() -> pd.Series:
    df = pd.read_parquet(CACHE_DIR / "spx_history.parquet")
    df["date"] = pd.to_datetime(df["date"])
    s = df.set_index("date")["close"].sort_index()
    return s.resample("ME").last().dropna()


def load_vix_monthly() -> pd.DataFrame:
    """回 DataFrame 含 vix_close (月底) + vix_mean (月均，給雷達 proxy)."""
    df = pd.read_parquet(CACHE_DIR / "vix_history.parquet")
    df["date"] = pd.to_datetime(df["date"])
    s = df.set_index("date")["close"].sort_index()
    return pd.DataFrame({
        "vix_close": s.resample("ME").last(),
        "vix_mean": s.resample("ME").mean(),
    })


# ════════════════════════════════════════════════════════════════
# §2 9-factor panel 組裝（對齊 macro_score_calibration FACTORS key）
# ════════════════════════════════════════════════════════════════
def build_factor_panel(
    fred_monthly: pd.DataFrame,
    vix_monthly: pd.Series,
) -> pd.DataFrame:
    """raw FRED + VIX → FACTORS key 對齊的 panel；缺 series 則 column 不出現."""
    out = pd.DataFrame(index=fred_monthly.index)
    if "DGS10" in fred_monthly and "DGS2" in fred_monthly:
        out["YIELD_10Y2Y"] = fred_monthly["DGS10"] - fred_monthly["DGS2"]
    if "DGS10" in fred_monthly and "DGS3MO" in fred_monthly:
        out["YIELD_10Y3M"] = fred_monthly["DGS10"] - fred_monthly["DGS3MO"]
    if "BAMLH0A0HYM2" in fred_monthly:
        out["HY_SPREAD"] = fred_monthly["BAMLH0A0HYM2"]
    if "M2SL" in fred_monthly:
        out["M2"] = (fred_monthly["M2SL"] / fred_monthly["M2SL"].shift(12) - 1) * 100
    if "CPIAUCSL" in fred_monthly:
        out["CPI"] = (fred_monthly["CPIAUCSL"] / fred_monthly["CPIAUCSL"].shift(12) - 1) * 100
    if "DGS3MO" in fred_monthly:
        # FEDFUNDS proxy（與 FEDFUNDS 相關係數 > 0.95）
        out["FEDRATE"] = fred_monthly["DGS3MO"]
    if "UNRATE" in fred_monthly:
        out["UNEMP"] = fred_monthly["UNRATE"]
    if "WALCL" in fred_monthly:
        out["FED_BS"] = (fred_monthly["WALCL"] / fred_monthly["WALCL"].shift(52) - 1) * 100
    out["VIX"] = vix_monthly.reindex(out.index, method="ffill")
    return out


# ════════════════════════════════════════════════════════════════
# §3 雙頭合議 proxy 評估
# ════════════════════════════════════════════════════════════════
def strategy_b_radar_proxy(
    score_series: pd.DataFrame,
    events: list,
    vix_monthly: pd.DataFrame,
    radar_threshold: float = 30.0,
    lookback_months: int = 3,
    lead_months: int = 6,
    drop_threshold: float = 0.20,
) -> list[dict]:
    """三策略每事件結果。

    Strategies
    ----------
    - A 純長期 (pre-warning)：score 在 peak 前 ``lead_months`` 月跌 ≥ ``drop_threshold``
    - B 雷達 pre (peak 前)：peak 前 ``lookback_months`` 月內 VIX 月均 > threshold
    - C 雷達 during (期間內)：peak → trough 之間 VIX 月均 > threshold
        ↑ 對齊 dual_verdict 設計：雷達是 real-time 防守、非 pre-warning
    - A∪C 雙頭合議 (real-time)：A 或 C 任一命中（夠用即避免跌段）
    """
    a_results = verify_score_vs_crises(
        score_series, events,
        lead_months=lead_months,
        drop_threshold=drop_threshold,
    )
    out: list[dict] = []
    for ev, a_res in zip(events, a_results):
        peak_dt = pd.Timestamp(ev.peak_date)
        trough_dt = pd.Timestamp(ev.trough_date)

        # B: peak 前
        pre_start = peak_dt - pd.DateOffset(months=lookback_months)
        vix_pre = vix_monthly.loc[pre_start:peak_dt, "vix_mean"]
        b_hit = bool((vix_pre > radar_threshold).any()) if len(vix_pre) else False
        b_max = float(vix_pre.max()) if len(vix_pre) else None

        # C: peak → trough（real-time 防守視窗）
        vix_during = vix_monthly.loc[peak_dt:trough_dt, "vix_mean"]
        c_hit = bool((vix_during > radar_threshold).any()) if len(vix_during) else False
        c_max = float(vix_during.max()) if len(vix_during) else None

        out.append({
            "peak_date": peak_dt,
            "trough_date": trough_dt,
            "drawdown": float(ev.drawdown_pct),
            "a_hit": bool(a_res.hit),
            "a_drop": a_res.score_drop_pct,
            "a_score_lead": a_res.score_lead,
            "a_score_peak": a_res.score_peak,
            "b_radar_hit": b_hit,
            "b_vix_max": b_max,
            "c_radar_hit": c_hit,
            "c_vix_max": c_max,
            "combined_pre_hit": bool(a_res.hit) or b_hit,
            "combined_during_hit": bool(a_res.hit) or c_hit,
        })
    return out


# ════════════════════════════════════════════════════════════════
# §4 對照表渲染
# ════════════════════════════════════════════════════════════════
def print_table(
    results: list[dict],
    *,
    lead_months: int,
    drop_threshold: float,
    radar_threshold: float,
    radar_lookback: int,
) -> None:
    width = 112
    print(f"\n{'='*width}")
    print(
        f"純長期 (A) vs 雷達 pre (B) vs 雷達 during (C) vs 合議  "
        f"(lead={lead_months}mo, drop≥{drop_threshold:.0%}, VIX>{radar_threshold:.0f})"
    )
    print("=" * width)
    print(
        f"{'Peak':<9} {'DD':>7}  "
        f"{'A:lead→peak':>20}  {'A':>2}  "
        f"{'B:pre VIX':>10}  {'B':>2}  "
        f"{'C:during VIX':>13}  {'C':>2}  "
        f"{'A∪B':>4}  {'A∪C':>4}"
    )
    print("-" * width)
    n_a = n_b = n_c = n_ab = n_ac = 0
    n = len(results)
    for r in results:
        peak = r["peak_date"].strftime("%Y-%m")
        dd = f"{r['drawdown']*100:>5.1f}%"
        if r["a_score_lead"] is not None and r["a_score_peak"] is not None:
            a_drop = (
                f"{r['a_score_lead']:>5.2f}→{r['a_score_peak']:<5.2f}"
                f"({(r['a_drop'] or 0)*100:>+4.0f}%)"
            )
        else:
            a_drop = " " * 20
        a_hit = "✅" if r["a_hit"] else "❌"
        b_vix = f"{r['b_vix_max']:>8.1f}" if r["b_vix_max"] is not None else "    N/A "
        b_hit = "✅" if r["b_radar_hit"] else "❌"
        c_vix = f"{r['c_vix_max']:>10.1f}" if r["c_vix_max"] is not None else "      N/A "
        c_hit = "✅" if r["c_radar_hit"] else "❌"
        ab_hit = "✅" if r["combined_pre_hit"] else "❌"
        ac_hit = "✅" if r["combined_during_hit"] else "❌"
        n_a += int(r["a_hit"])
        n_b += int(r["b_radar_hit"])
        n_c += int(r["c_radar_hit"])
        n_ab += int(r["combined_pre_hit"])
        n_ac += int(r["combined_during_hit"])
        print(
            f"{peak:<9} {dd:>7}  {a_drop:>20}  {a_hit:>2}  "
            f"{b_vix:>10}  {b_hit:>2}  {c_vix:>13}  {c_hit:>2}  "
            f"{ab_hit:>4}  {ac_hit:>4}"
        )
    print("-" * width)
    if n:
        print(
            f"命中率                                       "
            f"{n_a}/{n}({n_a/n*100:>3.0f}%)             "
            f"{n_b}/{n}({n_b/n*100:>3.0f}%)                "
            f"{n_c}/{n}({n_c/n*100:>3.0f}%)  "
            f"{n_ab}/{n}({n_ab/n*100:>3.0f}%) {n_ac}/{n}({n_ac/n*100:>3.0f}%)"
        )
    print("=" * width)


# ════════════════════════════════════════════════════════════════
# §5 CLI 主入口
# ════════════════════════════════════════════════════════════════
def main() -> None:
    parser = argparse.ArgumentParser(
        description="純長期 vs 雙頭合議：歷史熊市命中率對照表",
    )
    parser.add_argument("--threshold", type=float, default=-0.20,
                        help="SPX MaxDD 偵測門檻（負數，預設 -0.20）")
    parser.add_argument("--lead-months", type=int, default=6,
                        help="Score lead window 月數（預設 6）")
    parser.add_argument("--drop-threshold", type=float, default=0.20,
                        help="Score 相對下跌 ≥ 此值算 A 命中（預設 0.20）")
    parser.add_argument("--radar-vix", type=float, default=30.0,
                        help="雷達 proxy: VIX 月均 > 此值算警報（預設 30）")
    parser.add_argument("--radar-lookback", type=int, default=3,
                        help="雷達 proxy: peak 前 N 月觀察視窗（預設 3）")
    args = parser.parse_args()

    print("[1/4] 讀 parquet ...")
    fred_monthly = load_fred_wide()
    spx_monthly = load_spx_monthly()
    vix_monthly = load_vix_monthly()
    print(f"    FRED: {fred_monthly.index.min().date()} → {fred_monthly.index.max().date()}"
          f", {fred_monthly.shape[1]} series")
    print(f"    SPX : {spx_monthly.index.min().date()} → {spx_monthly.index.max().date()}"
          f", {len(spx_monthly)} 月")
    print(f"    VIX : {vix_monthly.index.min().date()} → {vix_monthly.index.max().date()}"
          f", {len(vix_monthly)} 月")

    print("[2/4] 組 9-factor panel → compute_historical_score ...")
    panel = build_factor_panel(fred_monthly, vix_monthly["vix_close"])
    score = compute_historical_score(panel).to_frame(name="score").dropna()
    print(f"    score: {score.index.min().date()} → {score.index.max().date()}, n={len(score)}")
    print(f"    平均 {score['score'].mean():.2f}, std {score['score'].std():.2f}, "
          f"min {score['score'].min():.2f}, max {score['score'].max():.2f}")

    print(f"[3/4] detect_crisis_events(SPX 月度, threshold={args.threshold:.0%}) ...")
    events = detect_crisis_events(spx_monthly, threshold=args.threshold, market="SPX")
    print(f"    偵測 {len(events)} 個事件：")
    for ev in events:
        print(
            f"      • {ev.peak_date.strftime('%Y-%m')} → {ev.trough_date.strftime('%Y-%m')}"
            f"  DD={ev.drawdown_pct*100:>5.1f}%  duration={ev.duration_days}d"
        )

    print("[4/4] 跑 A=純長期 + B=雷達 proxy + 合議 ...")
    results = strategy_b_radar_proxy(
        score, events, vix_monthly,
        radar_threshold=args.radar_vix,
        lookback_months=args.radar_lookback,
        lead_months=args.lead_months,
        drop_threshold=args.drop_threshold,
    )
    print_table(
        results,
        lead_months=args.lead_months,
        drop_threshold=args.drop_threshold,
        radar_threshold=args.radar_vix,
        radar_lookback=args.radar_lookback,
    )


if __name__ == "__main__":
    main()
