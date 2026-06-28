"""macro_validation.py — Tab1 Macro Score 預測力驗證 (v18.260, Phase 6a).

User 需求：「我比較想驗證目前我的總經 Tab 的歷史資料與歷史景氣變差的差異
（這樣才知道看總經 Tab 準不準）」。

實作策略：
- 不依賴歷史 macro_score DB（不存在）
- 即時利用 fetch_all_indicators() 各 indicator 的 .series 欄位（FRED 多年歷史時序）
- 逐月對齊每個指標到 month-end，套用與 fetch_all_indicators() 完全一致的閾值規則打分
- 聚合公式鏡像 services.macro_service.calc_macro_phase：
    norm = (earned_w + total_w) / (2 * total_w) * 10
- 與既有 services.crisis_backtest.detect_crisis_events 輸出對齊，量化「peak 前 N 月
  score 降幅 ≥ threshold 才算預警」的命中率，並做 crisis vs 平時的 t-test。
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import pandas as pd

from shared.macro_thresholds_v2 import (  # F-GRAY-4 v19.169 + v19.178 CPI + v19.179 PMI
    CPI_YOY_THRESHOLDS as _CPI_THR,
    HY_SPREAD_THRESHOLDS as _HY_THR,
    PMI_THRESHOLDS as _PMI_THR,
)

# F-GRAY-4 v19.179: PMI score_function SSOT (SPEC §16.2)
_PMI_EXPANSION = _PMI_THR["score_function"]["expansion_above"]  # 50.0
_PMI_RECESSION = _PMI_THR["score_function"]["recession_below"]  # 45.0

DEFAULT_PARQUET_CACHE_DIR = Path("data_cache")

# F-GRAY-4 v19.169: HY_SPREAD score_function SSOT (SPEC §16.2)
_HY_TIGHT = _HY_THR["score_function"]["tight_below"]
_HY_WIDE = _HY_THR["score_function"]["wide_above"]

# F-GRAY-4 v19.178: CPI_YOY score_function SSOT (SPEC §16.2)
_CPI_IDEAL_LOW = _CPI_THR["score_function"]["ideal_low"]
_CPI_IDEAL_HIGH = _CPI_THR["score_function"]["ideal_high"]
_CPI_ELEVATED = _CPI_THR["score_function"]["elevated_above"]


# ────────────────────────────────────────────────────────────────────
# 各指標的 (weight, 閾值打分) — 鏡像 services/macro_service.py:fetch_all_indicators
# 只收 series 已為「絕對值」（可直接 ffill 對齊月末）的核心指標，
# 排除 ADL/DXY/cross-rates（series 是 ratio/level，score 看 monthly change，回測對齊複雜）
# ────────────────────────────────────────────────────────────────────
ScoreFn = Callable[[float], float]

# v18.279 D 案 + C2-C v19.159 — VIX 閾值對齊 SSOT
# JSON override 由 scripts/calibrate_macro_score.py 季度校準後人類審閱 PR merge 寫入。
#
# C2-C v19.159(撤銷 v19.147 multi-cutoff):
# - DEFAULT_VIX_WARNING 18.0 → 22.0(對齊 macro_buckets._VIX_YELLOW SSOT)
# - DEFAULT_VIX_CRISIS 30.0(panic 全員一致)— 改 import _VIX_RED SSOT
# - calibration JSON 仍可微調(新 bound:warning ∈ [18, 26] / crisis ∈ [25, 35]),
#   原 JSON 若校準到 14~17 區會落 fallback → 自動採新 SSOT 22(intended)
# - 用 macro_buckets SSOT 取代 inline magic;若未來 SSOT 改值,此處自動跟
from shared.macro_buckets import _VIX_RED as _MB_VIX_RED, _VIX_YELLOW as _MB_VIX_YELLOW

DEFAULT_VIX_CRISIS: float = _MB_VIX_RED       # = 30,全站 panic
DEFAULT_VIX_WARNING: float = _MB_VIX_YELLOW   # = 22,SSOT yellow


def _make_vix_score_fn(crisis_thr: float, warning_thr: float) -> ScoreFn:
    """根據閾值產出 VIX score_fn。warning < v < crisis → 0.0；外側為 ±1.0。"""
    def _fn(v: float) -> float:
        if v < warning_thr:
            return 1.0
        if v > crisis_thr:
            return -1.0
        return 0.0
    return _fn


def _load_vix_calibrated_thresholds(
    cache_dir: Path = DEFAULT_PARQUET_CACHE_DIR,
) -> tuple[float, float]:
    """讀 data_cache/macro_thresholds_global.json → (crisis, warning).

    缺檔 / 解析失敗 / 值越界 → silently 回 module 預設,不噴錯。
    C2-C v19.159 越界守門更新:
        crisis  ∈ [25, 35](維持原寬幅)
        warning ∈ [18, 26](原 [14, 22] → 對齊 SSOT 22 重心,允許微調 ±4)
        warning < crisis 仍守。
    既有校準 JSON 落在舊 [14, 18) 區會視為越界 → fallback 至 SSOT 22(intended)。
    """
    import json as _json
    path = cache_dir / "macro_thresholds_global.json"
    try:
        if path.exists():
            cfg = _json.loads(path.read_text(encoding="utf-8"))
            c = float(cfg.get("VIX_CRISIS_THRESHOLD", DEFAULT_VIX_CRISIS))
            w = float(cfg.get("VIX_WARNING_THRESHOLD", DEFAULT_VIX_WARNING))
            if 25.0 <= c <= 35.0 and 18.0 <= w <= 26.0 and w < c:
                return c, w
    except Exception:
        pass
    return DEFAULT_VIX_CRISIS, DEFAULT_VIX_WARNING


_VIX_CRISIS, _VIX_WARNING = _load_vix_calibrated_thresholds()

SCORE_RULES: dict[str, tuple[float, ScoreFn]] = {
    "PMI":          (2.0, lambda v: 2.0 if v >= _PMI_EXPANSION else (-2.0 if v < _PMI_RECESSION else -1.0)),
    "YIELD_10Y2Y":  (2.0, lambda v: 2.0 if v > 0.5 else (-2.0 if v < 0 else 0.0)),
    "YIELD_10Y3M":  (2.0, lambda v: 2.0 if v > 0.5 else (-2.0 if v < 0 else 0.0)),  # v19.195 A2:對齊 10Y-2Y 三段(0~0.5 轉平=中性)
    "HY_SPREAD":    (2.0, lambda v: 2.0 if v < _HY_TIGHT else (-2.0 if v > _HY_WIDE else 0.0)),
    "M2":           (1.0, lambda v: 1.0 if v > 5 else (-1.0 if v < 0 else 0.0)),
    "FED_BS":       (1.0, lambda v: 1.0 if v > 5 else (-1.0 if v < -5 else 0.0)),
    "VIX":          (1.0, _make_vix_score_fn(_VIX_CRISIS, _VIX_WARNING)),
    "CPI":          (0.5, lambda v: 1.0 if _CPI_IDEAL_LOW < v < _CPI_IDEAL_HIGH else (-1.0 if v > _CPI_ELEVATED else 0.0)),
    "UNEMPLOYMENT": (0.5, lambda v: 1.0 if v < 4.5 else (-2.0 if v > 6 else 0.0)),
}


def aggregate_score(scored: dict[str, tuple[float, float]]) -> tuple[float, str]:
    """把 {key: (weight, score)} 聚合成 (0-10 score, phase 名稱).

    與 services.macro_service.calc_macro_phase 公式一致：
        norm = (earned_w + total_w) / (2 * total_w) * 10
    """
    if not scored:
        return 5.0, "復甦"
    total_w = sum(w for w, _ in scored.values())
    earned_w = sum(s for _, s in scored.values())
    if total_w <= 0:
        norm = 5.0
    else:
        # 每個指標 score 已 clip 到 [-w, +w]（由 SCORE_RULES 保證），此處不再 clip
        norm = (earned_w + total_w) / (2 * total_w) * 10
    score = round(max(0.0, min(10.0, norm)), 1)
    if score >= 8:
        phase = "高峰"
    elif score >= 5:
        phase = "擴張"
    elif score >= 3:
        phase = "復甦"
    else:
        phase = "衰退"
    return score, phase


def load_indicators_from_parquet(
    cache_dir: Path = DEFAULT_PARQUET_CACHE_DIR,
) -> dict:
    """從 data_cache/*.parquet 重組 indicators dict（鏡像 fetch_all_indicators 結構）.

    v18.276 (Phase B.2)：解開「Phase 6a 必須先去 Tab1 抓 FRED 才能跑驗證」的綁定。
    讀 Parquet 快取（PR #160 v18.275 weekly cron 維護）並做與 services/macro_service
    完全一致的衍生轉換（spread / YoY%）：

    | SCORE_RULES key | Parquet 來源              | 轉換                                  |
    |-----------------|---------------------------|---------------------------------------|
    | YIELD_10Y2Y     | fred_indicators DGS10/DGS2 | spread = DGS10 - DGS2                  |
    | YIELD_10Y3M     | fred_indicators DGS10/DGS3MO | spread = DGS10 - DGS3MO              |
    | HY_SPREAD       | fred_indicators BAMLH0A0HYM2 | direct level                        |
    | M2              | fred_indicators M2SL       | (s / s.shift(12) - 1) * 100 (YoY%)     |
    | FED_BS          | fred_indicators WALCL      | (s / s.shift(52) - 1) * 100 (週頻 YoY) |
    | CPI             | fred_indicators CPIAUCSL   | (s / s.shift(12) - 1) * 100            |
    | UNEMPLOYMENT    | fred_indicators UNRATE     | direct level                          |
    | VIX             | vix_history close          | direct level                          |
    | PMI             | (不在 Parquet)             | 留給 indicators_now fallback           |

    Returns: {key: {"series": pd.Series with DatetimeIndex}} — series 已轉換為 score
             可直接吃的格式；缺檔/缺 series → 對應 key 不存在。
    """
    out: dict[str, dict] = {}

    fred_path = cache_dir / "fred_indicators.parquet"
    if fred_path.exists():
        try:
            df = pd.read_parquet(fred_path)
            if not df.empty and {"date", "series_id", "value"}.issubset(df.columns):
                df = df.copy()
                df["date"] = pd.to_datetime(df["date"])
                # pivot 長 → 寬
                wide = df.pivot_table(index="date", columns="series_id",
                                       values="value", aggfunc="last").sort_index()

                def _add(key: str, s: pd.Series) -> None:
                    s = s.dropna()
                    if not s.empty:
                        out[key] = {"series": s}

                # 殖利率利差（日頻）
                if "DGS10" in wide.columns and "DGS2" in wide.columns:
                    _add("YIELD_10Y2Y", (wide["DGS10"] - wide["DGS2"]))
                if "DGS10" in wide.columns and "DGS3MO" in wide.columns:
                    _add("YIELD_10Y3M", (wide["DGS10"] - wide["DGS3MO"]))
                # HY 利差（日頻 level）
                if "BAMLH0A0HYM2" in wide.columns:
                    _add("HY_SPREAD", wide["BAMLH0A0HYM2"])
                # M2 YoY%（月頻：shift 12）
                if "M2SL" in wide.columns:
                    s_raw = wide["M2SL"].dropna()
                    if len(s_raw) >= 13:
                        _add("M2", (s_raw / s_raw.shift(12) - 1) * 100)
                # FED_BS YoY%（週頻：shift 52）
                if "WALCL" in wide.columns:
                    s_raw = wide["WALCL"].dropna()
                    if len(s_raw) >= 53:
                        _add("FED_BS", (s_raw / s_raw.shift(52) - 1) * 100)
                # CPI YoY%
                if "CPIAUCSL" in wide.columns:
                    s_raw = wide["CPIAUCSL"].dropna()
                    if len(s_raw) >= 13:
                        _add("CPI", (s_raw / s_raw.shift(12) - 1) * 100)
                # 失業率（月頻 level）
                if "UNRATE" in wide.columns:
                    _add("UNEMPLOYMENT", wide["UNRATE"])
        except Exception as e:  # noqa: BLE001 — 缺檔/壞檔 graceful
            print(f"[macro_validation/load_parquet] fred_indicators read 失敗：{e}")

    # VIX 從 vix_history.parquet
    vix_path = cache_dir / "vix_history.parquet"
    if vix_path.exists():
        try:
            df = pd.read_parquet(vix_path)
            if not df.empty and {"date", "close"}.issubset(df.columns):
                df = df.copy()
                df["date"] = pd.to_datetime(df["date"])
                s = df.set_index("date")["close"].dropna().sort_index()
                if not s.empty:
                    out["VIX"] = {"series": s}
        except Exception as e:  # noqa: BLE001
            print(f"[macro_validation/load_parquet] vix_history read 失敗：{e}")

    return out


def calc_macro_score_series(
    indicators_now: Optional[dict] = None,
    years: int = 15,
    freq: str = "ME",
    prefer_parquet: bool = True,
    cache_dir: Path = DEFAULT_PARQUET_CACHE_DIR,
) -> pd.DataFrame:
    """重算過去 N 年每月 macro_score → 拿來驗證 Tab1 預測力.

    Args:
        indicators_now: fetch_all_indicators(fred_api_key) 輸出（may be None when
                        prefer_parquet=True; 主要用來補 PMI 等不在 Parquet 的指標）
        years: 回看年數（預設 15；最大受限於各 series 涵蓋範圍）
        freq: 重算頻率 ('ME' 月末 / 'W' 週末)
        prefer_parquet: True（預設）→ 優先讀 `data_cache/*.parquet`；
                        Parquet 缺/壞才 fallback 到 indicators_now。
        cache_dir: Parquet 快取目錄（v18.275 PR #160 維護的位置）

    Returns:
        DataFrame indexed by date with columns [score, phase, n_indicators].
        n_indicators = 該日期實際參與打分的指標數（未涵蓋的不算）
    """
    # 合併資料源：Parquet 優先（v18.275 PR #160 引入），indicators_now 補洞 PMI 等缺項
    sources: dict[str, dict] = {}
    if prefer_parquet:
        sources.update(load_indicators_from_parquet(cache_dir))
    if indicators_now:
        for k, v in indicators_now.items():
            if k not in sources:  # Parquet 優先；不覆蓋已有
                sources[k] = v

    end = pd.Timestamp.today().normalize()
    start = end - pd.DateOffset(years=int(years))
    date_range = pd.date_range(start=start, end=end, freq=freq)

    # 對齊每個 indicator series 到 date_range（forward-fill 取≤該日期最後已知值）
    aligned: dict[str, pd.Series] = {}
    for key in SCORE_RULES:
        ind = sources.get(key)
        if not ind:
            continue
        s = ind.get("series")
        if s is None or (hasattr(s, "empty") and s.empty):
            continue
        s = s.copy()
        if not isinstance(s.index, pd.DatetimeIndex):
            try:
                s.index = pd.to_datetime(s.index)
            except Exception as e:
                # v19.184 F-MED:加 stderr log(§3.3 反捏造);跳過該指標
                import sys as _sys
                print(f'[macro_validation] index to_datetime fail for "{key}" (skip): '
                      f'{type(e).__name__}: {e}', file=_sys.stderr)
                continue
        s = s.sort_index()
        aligned[key] = s.reindex(date_range, method="ffill")

    rows = []
    for dt in date_range:
        scored: dict[str, tuple[float, float]] = {}
        for key, (w, score_fn) in SCORE_RULES.items():
            if key not in aligned:
                continue
            v = aligned[key].loc[dt]
            if pd.isna(v):
                continue
            try:
                s = float(score_fn(float(v)))
            except Exception:
                continue
            # clip 到 [-w, +w] 保險（鏡像 calc_macro_phase 行 861）
            s = max(-w, min(w, s))
            scored[key] = (w, s)
        score, phase = aggregate_score(scored)
        rows.append({
            "date": dt,
            "score": score,
            "phase": phase,
            "n_indicators": len(scored),
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.set_index("date")


@dataclass
class CrisisVerifyResult:
    """單一危機事件的 macro_score 預警判定結果."""
    peak_date: pd.Timestamp
    trough_date: Optional[pd.Timestamp]
    score_lead: Optional[float]      # peak 前 lead_months 個月的 score
    score_peak: Optional[float]      # peak 月的 score
    score_trough: Optional[float]    # trough 月的 score
    score_drop_pct: Optional[float]  # (score_peak - score_lead) / score_lead
    hit: bool                        # drop_pct ≤ -drop_threshold 算預警成功


def verify_score_vs_crises(
    score_series: pd.DataFrame,
    events: list,
    lead_months: int = 6,
    drop_threshold: float = 0.20,
) -> list[CrisisVerifyResult]:
    """對每個 crisis event 判斷「峰前 N 月 score 是否預警下降」.

    判定規則：score 由 lead 點到 peak 點降幅 ≥ drop_threshold → 命中。
    """
    out: list[CrisisVerifyResult] = []
    if score_series is None or score_series.empty:
        return out
    scores = score_series["score"]

    def _score_at(dt: pd.Timestamp) -> Optional[float]:
        mask = scores.index <= dt
        if not mask.any():
            return None
        return float(scores[mask].iloc[-1])

    for ev in events or []:
        peak_dt = pd.Timestamp(ev.peak_date) if getattr(ev, "peak_date", None) is not None else None
        trough_dt = pd.Timestamp(ev.trough_date) if getattr(ev, "trough_date", None) is not None else None
        if peak_dt is None:
            continue
        lead_dt = peak_dt - pd.DateOffset(months=int(lead_months))

        s_lead = _score_at(lead_dt)
        s_peak = _score_at(peak_dt)
        s_trough = _score_at(trough_dt) if trough_dt is not None else None

        drop_pct: Optional[float] = None
        hit = False
        if s_lead is not None and s_peak is not None and s_lead > 0:
            drop_pct = (s_peak - s_lead) / s_lead
            hit = drop_pct <= -float(drop_threshold)

        out.append(CrisisVerifyResult(
            peak_date=peak_dt,
            trough_date=trough_dt,
            score_lead=s_lead,
            score_peak=s_peak,
            score_trough=s_trough,
            score_drop_pct=drop_pct,
            hit=hit,
        ))
    return out


def compute_period_stats(
    score_series: pd.DataFrame,
    events: list,
) -> dict:
    """crisis 期間 vs 平時 score 分佈差異 (含 Welch t-test p-value).

    crisis 期 = peak_date 到 trough_date 之間（含端點）；其餘為平時。
    """
    blank = {
        "crisis_mean": None, "normal_mean": None,
        "crisis_std": None, "normal_std": None,
        "n_crisis": 0, "n_normal": 0,
        "p_value": None,
    }
    if score_series is None or score_series.empty:
        return blank

    in_crisis = pd.Series(False, index=score_series.index)
    for ev in events or []:
        peak_dt = getattr(ev, "peak_date", None)
        trough_dt = getattr(ev, "trough_date", None)
        if peak_dt is None or trough_dt is None:
            continue
        peak_dt = pd.Timestamp(peak_dt)
        trough_dt = pd.Timestamp(trough_dt)
        mask = (score_series.index >= peak_dt) & (score_series.index <= trough_dt)
        in_crisis = in_crisis | mask

    scores = score_series["score"]
    crisis_scores = scores[in_crisis]
    normal_scores = scores[~in_crisis]

    p_value: Optional[float] = None
    if len(crisis_scores) >= 5 and len(normal_scores) >= 5:
        try:
            from scipy.stats import ttest_ind
            _t, p = ttest_ind(crisis_scores, normal_scores, equal_var=False)
            if pd.notna(p):
                p_value = float(p)
        except Exception:
            p_value = None

    return {
        "crisis_mean": float(crisis_scores.mean()) if len(crisis_scores) > 0 else None,
        "normal_mean": float(normal_scores.mean()) if len(normal_scores) > 0 else None,
        "crisis_std": float(crisis_scores.std()) if len(crisis_scores) > 1 else None,
        "normal_std": float(normal_scores.std()) if len(normal_scores) > 1 else None,
        "n_crisis": int(in_crisis.sum()),
        "n_normal": int((~in_crisis).sum()),
        "p_value": p_value,
    }
