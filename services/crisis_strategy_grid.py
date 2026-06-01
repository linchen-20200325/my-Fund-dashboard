"""crisis_strategy_grid.py — 策略網格搜尋引擎 (v18.260, Phase 4).

User 需求第 4 階段：在歷史危機事件上回測 4 種策略 × 3 個訊號門檻
的「期末資產 / 最大回撤 / Sharpe / 危機期報酬」表現。

設計原則：
- 純後端、純函式式，不依賴 Streamlit
- 共用 Phase 3 抓好的訊號序列；不重新抓任何 I/O
- 每組（策略, 門檻）→ 一筆 StrategyResult；總計 4×3=12 個 cell
- 輸出可直接 pivot 成 heatmap DataFrame

後續 Phase（PR #114）：Gemini AI 解讀最佳策略原因 + 風險提醒
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal, Optional

import pandas as pd

Direction = Literal["above", "below"]


@dataclass(frozen=True)
class StrategySpec:
    """單一策略規格 — 每日倉位由 position_fn(triggered, market_dd) 決定。

    position_fn 回傳值代表市場曝險倍數：
      0.0 = 全現金；1.0 = 滿倉；1.5 = 加碼 1.5 倍
    """
    key: str
    label: str
    description: str
    position_fn: Callable[[bool, float], float]


# ──────────────────────────────────────────────────────────────
# 4 個預設策略
# ──────────────────────────────────────────────────────────────
def _pos_buy_and_hold(triggered: bool, market_dd: float) -> float:
    return 1.0


def _pos_signal_exit(triggered: bool, market_dd: float) -> float:
    return 0.0 if triggered else 1.0


def _pos_signal_half(triggered: bool, market_dd: float) -> float:
    return 0.5 if triggered else 1.0


def _pos_buy_dip(triggered: bool, market_dd: float) -> float:
    # 訊號觸發 且 大盤從高點跌 ≥ 5% → 加碼到 1.5 倍
    if triggered and market_dd <= -0.05:
        return 1.5
    return 1.0


DEFAULT_STRATEGIES: list[StrategySpec] = [
    StrategySpec(
        key="buy_and_hold",
        label="全程持有",
        description="100% 滿倉，永不出場（baseline）",
        position_fn=_pos_buy_and_hold,
    ),
    StrategySpec(
        key="signal_exit",
        label="訊號出場",
        description="訊號觸發 → 全部轉現金；訊號消退 → 回場",
        position_fn=_pos_signal_exit,
    ),
    StrategySpec(
        key="signal_half",
        label="訊號減半",
        description="訊號觸發 → 減倉至 50%；訊號消退 → 回場",
        position_fn=_pos_signal_half,
    ),
    StrategySpec(
        key="buy_dip",
        label="訊號加碼低點",
        description="訊號觸發 + 大盤跌 ≥ 5% → 加碼至 150%（槓桿）",
        position_fn=_pos_buy_dip,
    ),
]


@dataclass
class StrategyResult:
    """單一（策略 × 門檻）組合的回測結果。"""
    strategy_key: str
    strategy_label: str
    threshold: float
    final_value: float          # 期末資產（起始 = 100）
    total_return_pct: float     # 期末 / 100 - 1
    max_drawdown_pct: float     # 策略本身的最大回撤（負數）
    sharpe_ratio: float         # 年化（√252）
    crisis_return_pct: float    # 大盤回撤 ≤ -10% 期間的累計策略報酬
    n_trigger_days: int         # 訊號觸發天數
    n_total_days: int           # 序列總天數

    def to_dict(self) -> dict:
        return {
            "strategy_key": self.strategy_key,
            "strategy_label": self.strategy_label,
            "threshold": float(self.threshold),
            "final_value": float(self.final_value),
            "total_return_pct": float(self.total_return_pct),
            "max_drawdown_pct": float(self.max_drawdown_pct),
            "sharpe_ratio": float(self.sharpe_ratio),
            "crisis_return_pct": float(self.crisis_return_pct),
            "n_trigger_days": int(self.n_trigger_days),
            "n_total_days": int(self.n_total_days),
        }


def _is_triggered(value: float, threshold: float, direction: Direction) -> bool:
    if pd.isna(value):
        return False
    if direction == "above":
        return value >= threshold
    return value <= threshold


def run_strategy(
    market_series: pd.Series,
    signal_series: pd.Series,
    spec: StrategySpec,
    threshold: float,
    direction: Direction = "above",
    crisis_dd_floor: float = -0.10,
) -> StrategyResult:
    """單次回測：給定策略 × 訊號門檻，產出績效。

    Args:
        market_series: 日度大盤收盤（用於計算 returns / running peak）
        signal_series: 日度訊號值（可不同頻率，會 reindex+ffill 對齊）
        spec: StrategySpec
        threshold: 訊號觸發閾值
        direction: 訊號方向（above = 大於等於警戒；below = 小於等於警戒）
        crisis_dd_floor: 大盤回撤 ≤ 此值算「危機期」（預設 -10%）

    Returns:
        StrategyResult
    """
    if market_series is None or market_series.empty or len(market_series) < 2:
        return StrategyResult(
            strategy_key=spec.key, strategy_label=spec.label, threshold=threshold,
            final_value=100.0, total_return_pct=0.0, max_drawdown_pct=0.0,
            sharpe_ratio=0.0, crisis_return_pct=0.0,
            n_trigger_days=0, n_total_days=0,
        )

    mkt = market_series.dropna().astype(float).sort_index()
    # 對齊訊號（ffill 把點觀測延伸到下一個觀測前一天）
    if signal_series is None or signal_series.empty:
        sig_aligned = pd.Series(float("nan"), index=mkt.index)
    else:
        sig_aligned = signal_series.astype(float).sort_index().reindex(mkt.index, method="ffill")

    mkt_ret = mkt.pct_change().fillna(0.0)
    running_peak = mkt.expanding().max()
    mkt_dd = (mkt - running_peak) / running_peak

    # 每日倉位（用 t-1 訊號決定 t 的倉位 → 避免前視偏誤）
    raw_pos = pd.Series(
        [
            spec.position_fn(
                _is_triggered(sig_aligned.iloc[i], threshold, direction),
                float(mkt_dd.iloc[i]),
            )
            for i in range(len(mkt))
        ],
        index=mkt.index,
        dtype=float,
    )
    position = raw_pos.shift(1).fillna(1.0)

    port_ret = position * mkt_ret
    cum_value = (1.0 + port_ret).cumprod() * 100.0

    final_value = float(cum_value.iloc[-1])
    total_return = final_value / 100.0 - 1.0

    port_peak = cum_value.expanding().max()
    port_dd = (cum_value - port_peak) / port_peak
    max_dd = float(port_dd.min())

    std = float(port_ret.std())
    sharpe = float(port_ret.mean() / std * (252 ** 0.5)) if std > 0 else 0.0

    crisis_mask = mkt_dd <= crisis_dd_floor
    if crisis_mask.any():
        crisis_ret = float((1.0 + port_ret[crisis_mask]).prod() - 1.0)
    else:
        crisis_ret = 0.0

    n_trigger = int(
        sum(
            1 for v in sig_aligned
            if not pd.isna(v) and _is_triggered(float(v), threshold, direction)
        )
    )

    return StrategyResult(
        strategy_key=spec.key,
        strategy_label=spec.label,
        threshold=float(threshold),
        final_value=final_value,
        total_return_pct=total_return,
        max_drawdown_pct=max_dd,
        sharpe_ratio=sharpe,
        crisis_return_pct=crisis_ret,
        n_trigger_days=n_trigger,
        n_total_days=int(len(mkt)),
    )


def grid_search(
    market_series: pd.Series,
    signal_series: pd.Series,
    thresholds: list[float],
    specs: Optional[list[StrategySpec]] = None,
    direction: Direction = "above",
    crisis_dd_floor: float = -0.10,
) -> list[StrategyResult]:
    """跑完整 (策略 × 門檻) 網格。

    Returns:
        list[StrategyResult]，順序 = specs outer × thresholds inner
    """
    if specs is None:
        specs = DEFAULT_STRATEGIES
    out: list[StrategyResult] = []
    for spec in specs:
        for thr in thresholds:
            out.append(run_strategy(
                market_series, signal_series, spec, thr,
                direction=direction, crisis_dd_floor=crisis_dd_floor,
            ))
    return out


def results_to_dataframe(results: list[StrategyResult]) -> pd.DataFrame:
    """攤平結果成寬表，欄位順序固定。"""
    if not results:
        return pd.DataFrame(columns=[
            "strategy_key", "strategy_label", "threshold",
            "final_value", "total_return_pct", "max_drawdown_pct",
            "sharpe_ratio", "crisis_return_pct",
            "n_trigger_days", "n_total_days",
        ])
    return pd.DataFrame([r.to_dict() for r in results])


def build_heatmap_data(
    results: list[StrategyResult],
    metric: str = "total_return_pct",
) -> pd.DataFrame:
    """轉成 heatmap 用的 2D DataFrame（index=策略 label, columns=門檻）。

    Args:
        results: grid_search 的輸出
        metric: 要顯示的 metric 欄名（StrategyResult 的屬性）

    Returns:
        DataFrame: rows=策略, columns=threshold 值, values=指定 metric
    """
    if not results:
        return pd.DataFrame()
    df = results_to_dataframe(results)
    if metric not in df.columns:
        raise ValueError(f"metric '{metric}' 不存在；可用：{list(df.columns)}")
    pivot = df.pivot(index="strategy_label", columns="threshold", values=metric)
    # 保持策略順序
    order = list(dict.fromkeys(df["strategy_label"]))
    return pivot.reindex(order)


def rank_results(
    results: list[StrategyResult],
    by: str = "sharpe_ratio",
    top_n: int = 5,
    ascending: bool = False,
) -> pd.DataFrame:
    """依指定 metric 排名 top N。"""
    if not results:
        return pd.DataFrame()
    df = results_to_dataframe(results)
    if by not in df.columns:
        raise ValueError(f"by '{by}' 不存在；可用：{list(df.columns)}")
    return df.sort_values(by, ascending=ascending).head(top_n).reset_index(drop=True)
