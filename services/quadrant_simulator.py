"""services/quadrant_simulator.py — v18.285 4 象限策略模擬

User 反饋：「想知道 台幣升值/貶值 × NAV 升降 四種狀態下，基金要怎麼調整才能得到最大效益」。

四象限：
  Q1 台幣升值 + NAV 下降 → 雙重打擊（最壞）
  Q2 台幣貶值 + NAV 下降 → 匯利 vs NAV 損
  Q3 台幣升值 + NAV 上升 → NAV 利 vs 匯損
  Q4 台幣貶值 + NAV 上升 → 雙重利（最好）

對每象限模擬 3 策略：
  DRIP  配股再投入：用配息原幣再買單位
  CASH  配息領現：每月配息換 TWD 拿走
  STAY  停泊外幣：配息留原幣不換，期末才換 TWD

公式（單期月度迴圈）：
  units_t      = units_(t-1) + (DRIP 增加單位)
  div_local_t  = units_t × NAV_t × (ADR%/12)
  fx_t         = fx_0 × (1 + monthly_fx_change)^t
  nav_t        = nav_0 × (1 + monthly_nav_change)^t

期末計算：
  final_twd = units × NAV × FX + Σ CASH_TWD + STAY_local × FX_end
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class QuadrantScenario:
    """單一象限參數定義。"""
    code: str               # "Q1" ~ "Q4"
    name: str               # "台幣升值 + NAV 下降"
    fx_change_pct_year: float    # FX 年化變化 %（正=TWD 貶值；負=TWD 升值）
    nav_change_pct_year: float   # NAV 年化變化 %（正=NAV 漲；負=跌）
    color: str
    insight: str            # 該象限直覺解讀


DEFAULT_QUADRANTS: tuple = (
    QuadrantScenario(
        code="Q1", name="台幣升值 + NAV 下降",
        fx_change_pct_year=-5.0, nav_change_pct_year=-10.0,
        color="#ef4444",
        insight="雙重打擊：FX 損 + NAV 損；應 STAY 等回升避免換匯虧損",
    ),
    QuadrantScenario(
        code="Q2", name="台幣貶值 + NAV 下降",
        fx_change_pct_year=+5.0, nav_change_pct_year=-10.0,
        color="#f59e0b",
        insight="匯利抵 NAV 損；DRIP 趁低加碼，未來反彈時利潤放大",
    ),
    QuadrantScenario(
        code="Q3", name="台幣升值 + NAV 上升",
        fx_change_pct_year=-5.0, nav_change_pct_year=+10.0,
        color="#10b981",
        insight="NAV 利被匯損吃掉部分；CASH 鎖利但要小心 NAV 還會漲",
    ),
    QuadrantScenario(
        code="Q4", name="台幣貶值 + NAV 上升",
        fx_change_pct_year=+5.0, nav_change_pct_year=+10.0,
        color="#22c55e",
        insight="雙重利潤；CASH 持續領取最大化 TWD 現金流",
    ),
)


def simulate_quadrant(
    quadrant: QuadrantScenario,
    initial_twd: float,
    nav: float,
    fx: float,
    annual_div_rate_pct: float,
    horizon_months: int = 12,
    strategy: str = "DRIP",
) -> dict:
    """單一象限 × 單一策略模擬。

    Args:
        quadrant: 象限參數
        initial_twd: 初始投入 TWD
        nav: 當前 NAV（原幣）
        fx: 當前 FX (1 原幣 = ? TWD)
        annual_div_rate_pct: 年化配息率 %
        horizon_months: 模擬月數
        strategy: "DRIP" / "CASH" / "STAY"

    Returns:
        dict 含 final_value_twd / units_final_value_twd / dividends_total_twd /
        total_return_pct / final_nav / final_fx / final_units / strategy
    """
    if initial_twd <= 0 or nav <= 0 or fx <= 0:
        return {
            "strategy": strategy, "final_value_twd": 0.0,
            "units_final_value_twd": 0.0, "dividends_total_twd": 0.0,
            "total_return_pct": 0.0, "final_nav": nav, "final_fx": fx,
            "final_units": 0.0,
        }
    if strategy not in ("DRIP", "CASH", "STAY"):
        raise ValueError(f"unknown strategy: {strategy}")

    initial_local = initial_twd / fx
    units = initial_local / nav
    cash_twd = 0.0           # CASH 策略累積 TWD
    stay_local = 0.0         # STAY 策略累積原幣

    monthly_fx_chg = (quadrant.fx_change_pct_year / 100.0) / 12.0
    monthly_nav_chg = (quadrant.nav_change_pct_year / 100.0) / 12.0
    monthly_div_rate = (annual_div_rate_pct / 100.0) / 12.0

    cur_nav, cur_fx = float(nav), float(fx)
    for _ in range(int(horizon_months)):
        cur_nav *= (1.0 + monthly_nav_chg)
        cur_fx *= (1.0 + monthly_fx_chg)
        if cur_nav <= 0:
            cur_nav = 0.0001
        if cur_fx <= 0:
            cur_fx = 0.0001
        div_local = units * cur_nav * monthly_div_rate
        if div_local <= 0:
            continue
        if strategy == "DRIP":
            units += div_local / cur_nav
        elif strategy == "CASH":
            cash_twd += div_local * cur_fx
        elif strategy == "STAY":
            stay_local += div_local

    units_final_value_twd = units * cur_nav * cur_fx
    stay_final_twd = stay_local * cur_fx
    final_value_twd = units_final_value_twd + cash_twd + stay_final_twd
    total_return_pct = (final_value_twd / initial_twd - 1.0) * 100.0

    return {
        "strategy": strategy,
        "final_value_twd": final_value_twd,
        "units_final_value_twd": units_final_value_twd,
        "dividends_total_twd": cash_twd + stay_final_twd,
        "total_return_pct": total_return_pct,
        "final_nav": cur_nav,
        "final_fx": cur_fx,
        "final_units": units,
    }


def compare_strategies_per_quadrant(
    quadrants: tuple = DEFAULT_QUADRANTS,
    *,
    initial_twd: float = 1_000_000.0,
    nav: float = 10.0,
    fx: float = 32.0,
    annual_div_rate_pct: float = 6.0,
    horizon_months: int = 12,
    strategies: tuple = ("DRIP", "CASH", "STAY"),
) -> pd.DataFrame:
    """每個象限跑所有策略 → 長表格 + 標記最佳策略。

    Returns:
        DataFrame with columns: 象限 / 策略 / 期末 TWD / 報酬 % /
        持有部位 TWD / 累計配息 TWD / 最佳
    """
    rows = []
    for q in quadrants:
        per_q_rows = []
        best_ret = -float("inf")
        best_strat = None
        for s in strategies:
            r = simulate_quadrant(
                q, initial_twd=initial_twd, nav=nav, fx=fx,
                annual_div_rate_pct=annual_div_rate_pct,
                horizon_months=horizon_months, strategy=s,
            )
            per_q_rows.append({
                "象限": q.name,
                "策略": s,
                "期末 TWD": int(round(r["final_value_twd"])),
                "報酬 %": round(r["total_return_pct"], 2),
                "持有部位 TWD": int(round(r["units_final_value_twd"])),
                "累計配息 TWD": int(round(r["dividends_total_twd"])),
            })
            if r["total_return_pct"] > best_ret:
                best_ret = r["total_return_pct"]
                best_strat = s
        for row in per_q_rows:
            row["最佳"] = "🏆" if row["策略"] == best_strat else ""
            rows.append(row)
    return pd.DataFrame(rows)


def summarize_best_per_quadrant(comparison_df: pd.DataFrame) -> pd.DataFrame:
    """從 long-form 比較表抽出每象限最佳策略 → 4 行摘要表。"""
    if comparison_df is None or comparison_df.empty:
        return pd.DataFrame(columns=["象限", "最佳策略", "期末 TWD", "報酬 %"])
    best_rows = comparison_df[comparison_df["最佳"] == "🏆"].copy()
    return best_rows[["象限", "策略", "期末 TWD", "報酬 %"]].rename(
        columns={"策略": "最佳策略"}
    ).reset_index(drop=True)


# ──────────────────────────────────────────────────────────────────
# v18.286 Part B：用歷史資料分類 4 象限（user 反饋「歷史資料上面已經有這資料了」）
# ──────────────────────────────────────────────────────────────────
def classify_historical_quadrants(
    nav_series: pd.Series,
    fx_series: pd.Series,
    window_months: int = 3,
) -> pd.DataFrame:
    """把歷史 NAV + FX 月序列按象限分類（rolling window）。

    Args:
        nav_series: 基金 NAV（DatetimeIndex）
        fx_series: 原幣對 TWD 匯率（DatetimeIndex）
        window_months: 看多少個月內的變化判定象限（預設 3）

    Returns:
        DataFrame [date, nav, fx, nav_chg_pct, fx_chg_pct, quadrant]
        quadrant: 'Q1' / 'Q2' / 'Q3' / 'Q4'
        - Q1: TWD升 + NAV跌（fx_chg < 0, nav_chg < 0）
        - Q2: TWD貶 + NAV跌（fx_chg > 0, nav_chg < 0）
        - Q3: TWD升 + NAV漲（fx_chg < 0, nav_chg > 0）
        - Q4: TWD貶 + NAV漲（fx_chg > 0, nav_chg > 0）
    """
    if nav_series is None or nav_series.empty:
        return pd.DataFrame()
    if fx_series is None or fx_series.empty:
        return pd.DataFrame()
    # 月末對齊
    try:
        nav_m = nav_series.resample("ME").last().dropna()
        fx_m = fx_series.resample("ME").last().dropna()
    except Exception:
        nav_m = nav_series.resample("M").last().dropna()
        fx_m = fx_series.resample("M").last().dropna()
    df = pd.concat([nav_m.rename("nav"), fx_m.rename("fx")], axis=1).dropna()
    if df.empty or len(df) <= window_months:
        return pd.DataFrame()
    df["nav_chg_pct"] = df["nav"].pct_change(window_months) * 100.0
    df["fx_chg_pct"] = df["fx"].pct_change(window_months) * 100.0
    df = df.dropna(subset=["nav_chg_pct", "fx_chg_pct"]).copy()

    def _classify(row):
        twd_down = row["fx_chg_pct"] > 0  # FX 漲 = TWD 貶
        nav_up = row["nav_chg_pct"] > 0
        if twd_down and nav_up:
            return "Q4"
        if twd_down and not nav_up:
            return "Q2"
        if (not twd_down) and nav_up:
            return "Q3"
        return "Q1"

    df["quadrant"] = df.apply(_classify, axis=1)
    df["date"] = df.index
    return df[["date", "nav", "fx", "nav_chg_pct", "fx_chg_pct", "quadrant"]].reset_index(drop=True)


def summarize_historical_distribution(classified_df: pd.DataFrame) -> dict:
    """歷史落在各象限的時間分佈 + 平均 FX/NAV 變化。

    Returns:
        dict[quadrant_code] = {count, pct, avg_nav_chg, avg_fx_chg}
        外加 total: 總月數
    """
    out: dict = {}
    if classified_df is None or classified_df.empty:
        return out
    n_total = len(classified_df)
    out["_total"] = n_total
    for q in ["Q1", "Q2", "Q3", "Q4"]:
        sub = classified_df[classified_df["quadrant"] == q]
        n = len(sub)
        out[q] = {
            "count": n,
            "pct": (n / n_total * 100.0) if n_total > 0 else 0.0,
            "avg_nav_chg": float(sub["nav_chg_pct"].mean()) if n > 0 else 0.0,
            "avg_fx_chg": float(sub["fx_chg_pct"].mean()) if n > 0 else 0.0,
        }
    return out
