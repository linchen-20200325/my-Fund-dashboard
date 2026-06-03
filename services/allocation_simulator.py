"""allocation_simulator.py — 配息分配前向模擬器 (v18.260, Phase 6b).

User 需求：「設模擬器，再不同階段調整配股、配息、放停泊帳戶，本金變化、配息變化的
差異就好了，要考慮匯差」。

模型：
- 起始：本金 TWD ÷ FX → 原幣 → ÷ NAV → 起始單位數
- 每月：
    1. NAV ← NAV × (1 + 該 phase 月變化率)
    2. 月配息（原幣）= units × NAV × 年配率 / 12
    3. 月配息分三桶：
        - DRIP %：÷ NAV → 新增單位（立即複利）
        - CASH %：累積到原幣現金桶
        - STAY %：× FX → 加進 TWD 定存桶（月複利）
    4. FX 依模型走（固定 / 線性 / 隨機 GBM）
- 終值：基金桶 + 現金桶（× 期末 FX）+ 定存桶 → TWD 合計

蒙地卡羅：FX = random GBM 時跑 N 次，輸出 5/50/95% quantile + 樣本路徑（供 fan chart）。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd


# ────────────────────────────────────────────────────────────────────
# 預設 4 段景氣劇本（User 指定：復甦 → 擴張 → 放緩 → 衰退，完整 4-phase cycle）
# v18.286：每 phase 可有自己的 drip/cash/stay 比例；缺漏時用 params 全期值
# ────────────────────────────────────────────────────────────────────
DEFAULT_PHASE_SCRIPT: list[dict] = [
    # 復甦期：NAV 開始反彈 → DRIP 多買加速複利
    {"months": 12, "phase": "復甦", "monthly_nav_change_pct": 0.8,
     "drip_pct": 80, "cash_pct": 10, "stay_pct": 10},
    # 擴張期：NAV 持續漲 → CASH 開始鎖利
    {"months": 18, "phase": "擴張", "monthly_nav_change_pct": 0.5,
     "drip_pct": 60, "cash_pct": 30, "stay_pct": 10},
    # 放緩期：NAV 上升放緩 → CASH 多領防範
    {"months": 12, "phase": "放緩", "monthly_nav_change_pct": 0.1,
     "drip_pct": 30, "cash_pct": 50, "stay_pct": 20},
    # 衰退期：NAV 下跌 → STAY 留原幣等回升
    {"months": 6,  "phase": "衰退", "monthly_nav_change_pct": -1.0,
     "drip_pct": 10, "cash_pct": 20, "stay_pct": 70},
]


# ────────────────────────────────────────────────────────────────────
# v18.280：4 風格策略 preset × 4 階段配置矩陣
# 每階段保留 DEFAULT_PHASE_SCRIPT 的「月數 + monthly_nav_change_pct」，
# 只覆寫 drip_pct/cash_pct/stay_pct 三桶比例。
# 每組 sum 必 = 100；UI 切 preset 一鍵套用 4 階段 12 個數字。
# ────────────────────────────────────────────────────────────────────
STRATEGY_PRESETS: dict[str, dict] = {
    "balanced": {
        "label": "⚖️ 穩健平衡",
        "desc": "經典美林邏輯：復甦多 DRIP、衰退多 STAY，全期間平衡（= 系統預設）",
        "allocations": {
            "復甦": {"drip_pct": 80, "cash_pct": 10, "stay_pct": 10},
            "擴張": {"drip_pct": 60, "cash_pct": 30, "stay_pct": 10},
            "放緩": {"drip_pct": 30, "cash_pct": 50, "stay_pct": 20},
            "衰退": {"drip_pct": 10, "cash_pct": 20, "stay_pct": 70},
        },
    },
    "aggressive_growth": {
        "label": "🚀 積極成長",
        "desc": "全期 DRIP 為主極大化複利；衰退少量 STAY 緩衝，犧牲下檔換上檔",
        "allocations": {
            "復甦": {"drip_pct": 95, "cash_pct": 5,  "stay_pct": 0},
            "擴張": {"drip_pct": 85, "cash_pct": 15, "stay_pct": 0},
            "放緩": {"drip_pct": 60, "cash_pct": 40, "stay_pct": 0},
            "衰退": {"drip_pct": 30, "cash_pct": 30, "stay_pct": 40},
        },
    },
    "income_first": {
        "label": "💰 收益優先",
        "desc": "高 CASH 比例每月領穩定現金流，犧牲長期複利換可預測收入",
        "allocations": {
            "復甦": {"drip_pct": 50, "cash_pct": 40, "stay_pct": 10},
            "擴張": {"drip_pct": 30, "cash_pct": 60, "stay_pct": 10},
            "放緩": {"drip_pct": 20, "cash_pct": 70, "stay_pct": 10},
            "衰退": {"drip_pct": 10, "cash_pct": 30, "stay_pct": 60},
        },
    },
    "defensive": {
        "label": "🛡️ 防禦保本",
        "desc": "高 STAY 比例守 TWD 定存桶，最低波動，犧牲報酬換下檔保護",
        "allocations": {
            "復甦": {"drip_pct": 40, "cash_pct": 20, "stay_pct": 40},
            "擴張": {"drip_pct": 30, "cash_pct": 30, "stay_pct": 40},
            "放緩": {"drip_pct": 15, "cash_pct": 30, "stay_pct": 55},
            "衰退": {"drip_pct": 5,  "cash_pct": 5,  "stay_pct": 90},
        },
    },
}


def get_preset_phase_script(preset_key: str) -> list[dict]:
    """套 preset 的三桶比例到 DEFAULT_PHASE_SCRIPT，回傳完整 phase_script。

    保留 DEFAULT_PHASE_SCRIPT 的 months / monthly_nav_change_pct，
    只用 preset 覆寫 drip_pct/cash_pct/stay_pct。

    Raises:
        KeyError: preset_key 不在 STRATEGY_PRESETS
    """
    if preset_key not in STRATEGY_PRESETS:
        raise KeyError(
            f"未知 preset_key: {preset_key!r}（可選：{list(STRATEGY_PRESETS)}）"
        )
    allocations = STRATEGY_PRESETS[preset_key]["allocations"]
    out = []
    for seg in DEFAULT_PHASE_SCRIPT:
        phase = seg["phase"]
        alloc = allocations.get(phase)
        if alloc is None:
            out.append(dict(seg))
            continue
        out.append({**seg, **alloc})
    return out


@dataclass(frozen=True)
class SimulationParams:
    amount_twd: float = 1_000_000.0
    annual_yield_pct: float = 6.0
    initial_nav: float = 10.0
    initial_fx: float = 32.0
    phase_script: list[dict] = field(default_factory=lambda: list(DEFAULT_PHASE_SCRIPT))
    drip_pct: float = 70.0
    cash_pct: float = 20.0
    stay_pct: float = 10.0
    stay_yield_pct: float = 1.5
    fx_model: str = "fixed"        # 'fixed' | 'linear' | 'random'
    fx_end_value: float = 32.0     # for linear
    fx_volatility_pct: float = 2.0  # for random — 年化 σ %


def validate_and_normalize(params: SimulationParams) -> SimulationParams:
    """三桶比例 sum = 100% 校驗，不滿則自動 normalize。

    Raises:
        ValueError: 三桶總和 ≤ 0、phase_script 為空、或負金額參數
    """
    if params.amount_twd <= 0:
        raise ValueError("amount_twd 必須 > 0")
    if params.initial_nav <= 0 or params.initial_fx <= 0:
        raise ValueError("initial_nav / initial_fx 必須 > 0")
    if not params.phase_script:
        raise ValueError("phase_script 不可為空")
    if params.fx_model not in ("fixed", "linear", "random"):
        raise ValueError(f"未知 fx_model: {params.fx_model}")

    total = params.drip_pct + params.cash_pct + params.stay_pct
    if total <= 0:
        raise ValueError("DRIP + CASH + STAY 必須 > 0")
    factor = 100.0 / total
    # frozen dataclass → 用 dict spread 重建
    return SimulationParams(
        amount_twd=params.amount_twd,
        annual_yield_pct=params.annual_yield_pct,
        initial_nav=params.initial_nav,
        initial_fx=params.initial_fx,
        phase_script=list(params.phase_script),
        drip_pct=params.drip_pct * factor,
        cash_pct=params.cash_pct * factor,
        stay_pct=params.stay_pct * factor,
        stay_yield_pct=params.stay_yield_pct,
        fx_model=params.fx_model,
        fx_end_value=params.fx_end_value,
        fx_volatility_pct=params.fx_volatility_pct,
    )


def _build_phase_timeline(phase_script: list[dict]) -> list[tuple[int, str, float, dict]]:
    """展開 phase_script 成逐月 [(month, phase_name, monthly_nav_change_pct, alloc_dict)].

    v18.286：alloc_dict 內含該 phase 的 drip/cash/stay% 若 phase 有定義；
    缺漏欄位由 caller 用 params 全期值補。
    """
    timeline: list[tuple[int, str, float, dict]] = []
    m = 0
    for seg in phase_script:
        n = int(seg.get("months", 0))
        if n <= 0:
            continue
        name = str(seg.get("phase", "—"))
        pct = float(seg.get("monthly_nav_change_pct", 0.0))
        # v18.286: per-phase allocation（可選）
        alloc: dict = {}
        for k in ("drip_pct", "cash_pct", "stay_pct"):
            if k in seg:
                try:
                    alloc[k] = float(seg.get(k, 0.0))
                except (TypeError, ValueError):
                    pass
        for _ in range(n):
            m += 1
            timeline.append((m, name, pct, alloc))
    return timeline


def _build_fx_path(params: SimulationParams, n_months: int,
                   rng: Optional[np.random.Generator] = None) -> list[float]:
    """建 n_months + 1 個 FX 值（含 month=0 起點）."""
    fx0 = params.initial_fx
    if params.fx_model == "fixed":
        return [fx0] * (n_months + 1)
    if params.fx_model == "linear":
        if n_months <= 0:
            return [fx0]
        fx_end = params.fx_end_value
        return [fx0 + (fx_end - fx0) * i / n_months for i in range(n_months + 1)]
    # random — 簡化 GBM：每月相對變化 ~ N(0, sigma_monthly)
    if rng is None:
        rng = np.random.default_rng()
    sigma_monthly = params.fx_volatility_pct / 100.0 / math.sqrt(12)
    path = [fx0]
    for _ in range(n_months):
        shock = rng.normal(0.0, sigma_monthly)
        path.append(path[-1] * (1.0 + shock))
    return path


def run_single_simulation(params: SimulationParams,
                          seed: Optional[int] = None) -> pd.DataFrame:
    """跑一次月度模擬 → DataFrame indexed by month。

    Columns: phase, nav, fx, units, cash_local, stay_twd, fund_value_twd,
             cash_value_twd, total_twd, div_this_twd, cum_div_twd
    """
    params = validate_and_normalize(params)
    timeline = _build_phase_timeline(params.phase_script)
    n_months = len(timeline)

    rng = np.random.default_rng(seed) if seed is not None else None
    fx_path = _build_fx_path(params, n_months, rng=rng)

    # 起始
    amt_local_init = params.amount_twd / fx_path[0]
    nav = float(params.initial_nav)
    units = amt_local_init / nav

    cash_local = 0.0       # 累積外幣現金桶（CASH 桶）
    stay_twd = 0.0         # TWD 定存桶（STAY 桶）
    cum_div_twd = 0.0
    stay_monthly_rate = params.stay_yield_pct / 100.0 / 12.0
    yield_monthly = params.annual_yield_pct / 100.0 / 12.0

    rows: list[dict] = []
    # Month 0 起始快照
    rows.append({
        "month": 0,
        "phase": "初始",
        "nav": round(nav, 4),
        "fx": round(fx_path[0], 4),
        "units": round(units, 4),
        "cash_local": 0.0,
        "stay_twd": 0.0,
        "fund_value_twd": round(units * nav * fx_path[0], 2),
        "cash_value_twd": 0.0,
        "total_twd": round(units * nav * fx_path[0], 2),
        "div_this_twd": 0.0,
        "cum_div_twd": 0.0,
    })

    for m, phase, monthly_nav_change_pct, _phase_alloc in timeline:
        nav = nav * (1.0 + monthly_nav_change_pct / 100.0)
        fx = fx_path[m]

        div_local = units * nav * yield_monthly

        # v18.286：per-phase allocation 優先；缺漏退回 params 全期值
        _drip = _phase_alloc.get("drip_pct", params.drip_pct)
        _cash = _phase_alloc.get("cash_pct", params.cash_pct)
        _stay = _phase_alloc.get("stay_pct", params.stay_pct)
        # phase-level normalize（避免 user 設 sum != 100% crash）
        _sum_phase = _drip + _cash + _stay
        if _sum_phase > 0:
            _f = 100.0 / _sum_phase
            _drip, _cash, _stay = _drip * _f, _cash * _f, _stay * _f

        drip_local = div_local * _drip / 100.0
        cash_local_inc = div_local * _cash / 100.0
        stay_local_inc = div_local * _stay / 100.0

        if nav > 0:
            units += drip_local / nav
        cash_local += cash_local_inc
        stay_twd = stay_twd * (1.0 + stay_monthly_rate) + stay_local_inc * fx

        div_this_twd = div_local * fx
        cum_div_twd += div_this_twd

        fund_value_twd = units * nav * fx
        cash_value_twd = cash_local * fx
        total_twd = fund_value_twd + cash_value_twd + stay_twd

        rows.append({
            "month": m,
            "phase": phase,
            "nav": round(nav, 4),
            "fx": round(fx, 4),
            "units": round(units, 4),
            "cash_local": round(cash_local, 2),
            "stay_twd": round(stay_twd, 2),
            "fund_value_twd": round(fund_value_twd, 2),
            "cash_value_twd": round(cash_value_twd, 2),
            "total_twd": round(total_twd, 2),
            "div_this_twd": round(div_this_twd, 2),
            "cum_div_twd": round(cum_div_twd, 2),
        })

    return pd.DataFrame(rows).set_index("month")


def summarize_simulation(df: pd.DataFrame) -> dict:
    """從單一 simulation DataFrame 抓終值統計。"""
    if df is None or df.empty:
        return {}
    last = df.iloc[-1]
    first_amount = float(df.iloc[0]["total_twd"])
    total_twd = float(last["total_twd"])
    div_series = df.loc[df.index > 0, "div_this_twd"] if (df.index > 0).any() else pd.Series([], dtype=float)
    return {
        "n_months": int(df.index.max()),
        "amount_twd": first_amount,
        "fund_value_twd": float(last["fund_value_twd"]),
        "cash_value_twd": float(last["cash_value_twd"]),
        "stay_twd": float(last["stay_twd"]),
        "total_twd": total_twd,
        "total_return_pct": (total_twd / first_amount - 1.0) * 100 if first_amount > 0 else 0.0,
        "cum_div_twd": float(last["cum_div_twd"]),
        "monthly_div_avg_twd": float(div_series.mean()) if len(div_series) > 0 else 0.0,
        "fx_end": float(last["fx"]),
    }


def run_monte_carlo(params: SimulationParams,
                    n_runs: int = 200,
                    seed: int = 42) -> dict:
    """跑 N 次蒙地卡羅，回 dict 含 quantile 統計 + 樣本路徑。

    fx_model != 'random' 時退回單次模擬（n_runs 忽略）。

    Returns:
        {
            "n_runs": int,
            "paths_sample": list[pd.DataFrame],  # 至多 50 條（記憶體保護）
            "terminal_quantiles": dict | None,    # {col: {p5, p50, p95, mean, std}}
            "summary": dict,                       # 第一條路徑 summary（範例）
        }
    """
    if params.fx_model != "random" or n_runs <= 1:
        df = run_single_simulation(params)
        return {
            "n_runs": 1,
            "paths_sample": [df],
            "terminal_quantiles": None,
            "summary": summarize_simulation(df),
        }

    rng = np.random.default_rng(seed)
    all_terminals: list[dict] = []
    all_paths: list[pd.DataFrame] = []

    for _ in range(n_runs):
        sub_seed = int(rng.integers(0, 2**32 - 1))
        df = run_single_simulation(params, seed=sub_seed)
        all_terminals.append({
            "total_twd": float(df["total_twd"].iloc[-1]),
            "fund_value_twd": float(df["fund_value_twd"].iloc[-1]),
            "cash_value_twd": float(df["cash_value_twd"].iloc[-1]),
            "stay_twd": float(df["stay_twd"].iloc[-1]),
            "cum_div_twd": float(df["cum_div_twd"].iloc[-1]),
            "fx_end": float(df["fx"].iloc[-1]),
        })
        all_paths.append(df)

    terminals_df = pd.DataFrame(all_terminals)
    quantiles = {
        col: {
            "p5": float(np.percentile(terminals_df[col], 5)),
            "p50": float(np.percentile(terminals_df[col], 50)),
            "p95": float(np.percentile(terminals_df[col], 95)),
            "mean": float(terminals_df[col].mean()),
            "std": float(terminals_df[col].std()),
        }
        for col in terminals_df.columns
    }

    sample_size = min(50, n_runs)
    sample_idx = sorted(rng.choice(n_runs, size=sample_size, replace=False).tolist())
    paths_sample = [all_paths[i] for i in sample_idx]

    return {
        "n_runs": n_runs,
        "paths_sample": paths_sample,
        "terminal_quantiles": quantiles,
        "summary": summarize_simulation(all_paths[0]),
    }
