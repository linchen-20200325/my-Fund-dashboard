"""multi_factor_optimization.py — 總經多因子權重最佳化 + 高原區 + Walk-Forward 驗證 (v18.285).

User 需求：總經回測系統 + 找最佳評比 + 拐點參數最佳化。
不是找「歷史回測單一最高績效」，而是找「參數高原區 (Parameter Plateau)」 —
鄰域內績效變異數最小、平均績效高的權重組合 → walk-forward OOS 驗證穩定性。

核心觀念：
1. 綜合分數 S_t = Σ w_i × normalize(I_{i, t-lag}) — lag=1 防未來引用
2. 拐點偵測：S_t 由 <threshold 跨過 ≥threshold 即警戒
3. 高原評分 = 鄰域 mean(F1) − λ × std(F1) — 偏好平台
4. Walk-forward：滾動 train_window 找高原 → test_window 套用 → 串 OOS 權益曲線
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

import numpy as np
import pandas as pd

from services.crisis_backtest import CrisisEvent

Direction = Literal["above", "below"]
NormalizeMethod = Literal["zscore", "minmax"]


@dataclass(frozen=True)
class FactorSpec:
    """單一因子規格 — 用於 multi-factor weighted composite score."""
    key: str
    label: str
    source: Literal["yahoo", "fred", "calculated"]
    series_id: str
    direction: Direction         # above: 高於 mean 為風險 / below: 低於 mean 為風險
    normalize: NormalizeMethod = "zscore"
    note: str = ""


FACTOR_POOL: list[FactorSpec] = [
    FactorSpec("VIX", "VIX 恐慌指數", "yahoo", "^VIX", "above", note="高 VIX = 市場恐慌"),
    FactorSpec("HY_SPREAD", "HY 信用利差", "fred", "BAMLH0A0HYM2", "above",
               note="高 HY OAS = 信用緊縮"),
    FactorSpec("T10Y2Y", "10Y-2Y 殖利率利差", "fred", "T10Y2Y", "below",
               note="負值 = 殖利率倒掛"),
    FactorSpec("UNRATE", "美國失業率", "fred", "UNRATE", "above", note="高失業 = 就業惡化"),
    FactorSpec("PMI", "ISM 製造業 PMI", "fred", "NAPM", "below", note="< 50 = 製造業萎縮"),
    FactorSpec("CPI_YOY", "CPI 年增率", "fred", "CPIAUCSL", "above",
               note="高通膨 = Fed 緊縮壓力"),
    FactorSpec("FEDFUNDS", "Fed Funds Rate", "fred", "FEDFUNDS", "above",
               note="高利率 = 緊縮環境"),
    FactorSpec("M2_YOY", "M2 年增率", "fred", "M2SL", "below",
               note="M2 收縮 = 流動性緊縮"),
    FactorSpec("DXY", "美元指數", "fred", "DTWEXBGS", "above",
               note="強美元 = 風險資產壓力"),
    FactorSpec("T10Y3M", "10Y-3M 殖利率利差", "fred", "T10Y3M", "below",
               note="負值 = 短端倒掛"),
    # v18.286 進階補強因子（債市流動性 + 高頻景氣 + 金融環境）
    FactorSpec("MOVE", "MOVE 公債波動率", "yahoo", "^MOVE", "above",
               note="債市 VIX；高 MOVE = 利率波動 = 流動性枯竭"),
    FactorSpec("NFCI", "NFCI 全國金融狀況", "fred", "NFCI", "above",
               note="芝加哥聯儲 105 項金融指標；>0 = 金融環境緊縮"),
    FactorSpec("COPPER_GOLD_RATIO", "銅金比", "calculated", "HG=F/GC=F", "below",
               note="銅/金期貨；下彎 = 景氣轉弱領先指標"),
]

FACTOR_POOL_BY_KEY = {f.key: f for f in FACTOR_POOL}

DEFAULT_TRAIN_MONTHS = 36
DEFAULT_TEST_MONTHS = 12
DEFAULT_LAG_DAYS = 1
DEFAULT_LAMBDA_STD = 0.5
DEFAULT_PLATEAU_RADIUS = 1
DEFAULT_THRESHOLD = 1.0
DEFAULT_GRID_STEP = 0.2


def fetch_factor_series(
    spec: FactorSpec,
    years: int = 20,
    fred_api_key: str = "",
) -> pd.Series:
    """Lazy-fetch 任一 FACTOR_POOL 因子的歷史序列。

    source:
      - yahoo:      fetch_yf_close(series_id, range_=f"{years}y")
      - fred:       fetch_fred(series_id, api_key, n=years*365)
      - calculated: 目前僅支援 COPPER_GOLD_RATIO（HG=F / GC=F）

    失敗一律回**空 DatetimeIndex Series**（不拋例外，由呼叫端決定 fallback）。
    v19.2 hotfix：empty return 改用 ``pd.DatetimeIndex([])`` 而非預設 RangeIndex，
    避免下游 walk_forward_validate / _slice_series 做 ``index >= Timestamp`` 比較時 TypeError。
    """
    _empty = lambda: pd.Series(  # noqa: E731
        dtype=float, name=spec.key, index=pd.DatetimeIndex([]),
    )
    try:
        if spec.source == "yahoo":
            from repositories.macro_repository import fetch_yf_close
            s = fetch_yf_close(spec.series_id, range_=f"{int(years)}y", interval="1d")
            if s is None or s.empty:
                return _empty()
            s = s.dropna()
            s.name = spec.key
            return s
        if spec.source == "fred":
            from repositories.macro_repository import fetch_fred
            n = max(int(years) * 365, 250)
            df = fetch_fred(spec.series_id, fred_api_key, n=n)
            if df is None or df.empty:
                return _empty()
            return pd.Series(
                df["value"].values,
                index=pd.to_datetime(df["date"]),
                name=spec.key, dtype=float,
            ).dropna()
        if spec.source == "calculated" and spec.key == "COPPER_GOLD_RATIO":
            from repositories.macro_repository import fetch_yf_close
            copper = fetch_yf_close("HG=F", range_=f"{int(years)}y", interval="1d")
            gold = fetch_yf_close("GC=F", range_=f"{int(years)}y", interval="1d")
            if copper is None or copper.empty or gold is None or gold.empty:
                return _empty()
            df = pd.concat([copper.rename("c"), gold.rename("g")], axis=1).ffill().dropna()
            ratio = (df["c"] / df["g"]).dropna()
            ratio.name = spec.key
            return ratio
        return _empty()
    except Exception as e:
        print(f"[multi_factor_optimization.fetch_factor_series] {spec.key} 抓取失敗：{e}")
        return _empty()


def _zscore(series: pd.Series) -> pd.Series:
    mu = series.mean()
    sd = series.std()
    if not np.isfinite(sd) or sd == 0:
        return pd.Series(0.0, index=series.index)
    return (series - mu) / sd


def _normalize(series: pd.Series, method: NormalizeMethod, spec_direction: Direction) -> pd.Series:
    """Z-score 或 min-max 正規化；direction=below 翻號讓「高分 = 風險」一致."""
    if method == "minmax":
        lo, hi = series.min(), series.max()
        if not np.isfinite(hi - lo) or hi == lo:
            normalized = pd.Series(0.0, index=series.index)
        else:
            normalized = (series - lo) / (hi - lo)
    else:
        normalized = _zscore(series)
    return -normalized if spec_direction == "below" else normalized


def compute_composite_score(
    factor_series_by_key: dict[str, pd.Series],
    weights: dict[str, float],
    specs_by_key: Optional[dict[str, FactorSpec]] = None,
    lag_days: int = DEFAULT_LAG_DAYS,
) -> pd.Series:
    """S_t = Σ w_i × normalize(I_{i, t-lag_days})  — vectorized, lag 防未來引用.

    Returns:
        綜合分數 series（index = 日期 union after dropna）。

    Raises:
        ValueError: weights 為空或 factor series 全空。
    """
    if not weights:
        raise ValueError("weights 為空")
    specs_by_key = specs_by_key or FACTOR_POOL_BY_KEY
    cols = []
    for key, w in weights.items():
        if w == 0:
            continue
        series = factor_series_by_key.get(key)
        if series is None or series.empty:
            continue
        spec = specs_by_key.get(key)
        direction = spec.direction if spec else "above"
        normalize = spec.normalize if spec else "zscore"
        normalized = _normalize(series.dropna(), normalize, direction)
        lagged = normalized.shift(lag_days)
        cols.append((w * lagged).rename(key))
    if not cols:
        return pd.Series(dtype=float)
    df = pd.concat(cols, axis=1).dropna(how="all")
    return df.sum(axis=1, skipna=False).dropna()


def score_to_signal(
    score: pd.Series, threshold: float = DEFAULT_THRESHOLD,
) -> pd.Series:
    """S_t ≥ threshold → 1（警戒）；否則 0；轉折日 = 由 0 跨到 1（v2 edge detection）."""
    warn = (score >= threshold).astype(int)
    crossings = warn & ~warn.shift(1, fill_value=0).astype(bool)
    return crossings.astype(int)


def evaluate_f1(
    crossings: pd.Series,
    events: list[CrisisEvent],
    max_forward_days: int = 365,
) -> dict[str, float]:
    """前向 precision × 後向 recall → F1 諧波平均.

    precision: 每個 crossing 在 max_forward_days 內是否命中 peak_date
    recall:    每個 peak_date 前 max_forward_days 內是否有 crossing
    """
    if crossings.empty or not events:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0,
                "n_crossings": 0, "n_events": len(events)}
    cross_dates = crossings[crossings == 1].index
    n_cross = len(cross_dates)
    if n_cross == 0:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0,
                "n_crossings": 0, "n_events": len(events)}
    peak_dates = [pd.Timestamp(e.peak_date) for e in events]
    tp = 0
    for cd in cross_dates:
        window_end = cd + pd.Timedelta(days=max_forward_days)
        if any(cd <= pk <= window_end for pk in peak_dates):
            tp += 1
    hit_events = 0
    for pk in peak_dates:
        window_start = pk - pd.Timedelta(days=max_forward_days)
        if any(window_start <= cd <= pk for cd in cross_dates):
            hit_events += 1
    precision = tp / n_cross if n_cross else 0.0
    recall = hit_events / len(peak_dates) if peak_dates else 0.0
    f1 = (2 * precision * recall / (precision + recall)
          if (precision + recall) > 0 else 0.0)
    return {"precision": precision, "recall": recall, "f1": f1,
            "n_crossings": n_cross, "n_events": len(events)}


def evaluate_sharpe(
    crossings: pd.Series,
    returns: pd.Series,
    fwd_days: int = 60,
) -> dict[str, float]:
    """訊號當日 → 持倉 fwd_days → next-period return → annualized Sharpe.

    模型：訊號日 short underlying（賭跌）；無訊號日空倉。
    """
    if crossings.empty or returns.empty:
        return {"sharpe": 0.0, "annual_return": 0.0, "annual_vol": 0.0, "n_trades": 0}
    rets = returns.pct_change(fwd_days).shift(-fwd_days)
    aligned = crossings.reindex(rets.index, fill_value=0)
    trade_rets = -rets[aligned == 1].dropna()
    if trade_rets.empty:
        return {"sharpe": 0.0, "annual_return": 0.0, "annual_vol": 0.0, "n_trades": 0}
    mu = trade_rets.mean()
    sd = trade_rets.std()
    n = len(trade_rets)
    periods_per_year = 252 / fwd_days
    annual_return = mu * periods_per_year
    annual_vol = sd * np.sqrt(periods_per_year) if sd > 0 else 0.0
    sharpe = annual_return / annual_vol if annual_vol > 0 else 0.0
    return {"sharpe": float(sharpe), "annual_return": float(annual_return),
            "annual_vol": float(annual_vol), "n_trades": int(n)}


def generate_simplex_grid(
    factor_keys: list[str], step: float = DEFAULT_GRID_STEP,
) -> list[dict[str, float]]:
    """產生 simplex 上的 weight 組合（Σ w_i = 1, w_i ∈ [0, 1] 以 step 為間隔）.

    n=2 → 1/step + 1 點；n=3 → (1/step+1)(1/step+2)/2；指數成長注意.
    """
    n = len(factor_keys)
    if n == 0 or step <= 0 or step > 1:
        return []
    grid_pts = int(round(1.0 / step)) + 1
    combos: list[dict[str, float]] = []

    def _recurse(idx: int, remaining: int, current: list[int]):
        if idx == n - 1:
            current.append(remaining)
            w = {k: v * step for k, v in zip(factor_keys, current)}
            combos.append(w)
            current.pop()
            return
        for v in range(remaining + 1):
            current.append(v)
            _recurse(idx + 1, remaining - v, current)
            current.pop()

    _recurse(0, grid_pts - 1, [])
    return combos


def grid_search_performance(
    factor_series_by_key: dict[str, pd.Series],
    returns: pd.Series,
    events: list[CrisisEvent],
    factor_keys: list[str],
    threshold: float = DEFAULT_THRESHOLD,
    step: float = DEFAULT_GRID_STEP,
    max_forward_days: int = 365,
    fwd_days: int = 60,
    specs_by_key: Optional[dict[str, FactorSpec]] = None,
) -> dict:
    """遍歷 simplex 權重組合 → 計算每組 F1 + Sharpe → 回傳 grid.

    Returns:
        {
          "combos": list[dict],         # 權重組合
          "f1": np.ndarray,             # F1 同 index
          "sharpe": np.ndarray,         # Sharpe 同 index
          "n_crossings": np.ndarray,
        }
    """
    combos = generate_simplex_grid(factor_keys, step)
    if not combos:
        return {"combos": [], "f1": np.array([]), "sharpe": np.array([]),
                "n_crossings": np.array([])}
    f1_arr = np.zeros(len(combos))
    sharpe_arr = np.zeros(len(combos))
    n_cross_arr = np.zeros(len(combos), dtype=int)
    for i, w in enumerate(combos):
        score = compute_composite_score(factor_series_by_key, w, specs_by_key)
        if score.empty:
            continue
        crossings = score_to_signal(score, threshold)
        f1_stat = evaluate_f1(crossings, events, max_forward_days)
        f1_arr[i] = f1_stat["f1"]
        n_cross_arr[i] = f1_stat["n_crossings"]
        sh_stat = evaluate_sharpe(crossings, returns, fwd_days)
        sharpe_arr[i] = sh_stat["sharpe"]
    return {"combos": combos, "f1": f1_arr, "sharpe": sharpe_arr,
            "n_crossings": n_cross_arr}


def evaluate_plateau(
    grid_result: dict,
    factor_keys: list[str],
    step: float = DEFAULT_GRID_STEP,
    radius: int = DEFAULT_PLATEAU_RADIUS,
    lambda_std: float = DEFAULT_LAMBDA_STD,
    metric: Literal["f1", "sharpe"] = "f1",
) -> np.ndarray:
    """高原評分 = 鄰域 mean − λ × std；高分代表「績效高且穩定」.

    為避免 N-D dense grid 記憶體爆炸，本實作用點對點距離（chebyshev）找鄰域：
    每點檢查所有其他點，距離 ≤ radius × step 視為鄰居。
    """
    combos = grid_result["combos"]
    if not combos:
        return np.array([])
    perf = grid_result[metric]
    coords = np.array([[w[k] for k in factor_keys] for w in combos])
    n = len(combos)
    plateau = np.zeros(n)
    tol = radius * step + 1e-9
    for i in range(n):
        d = np.max(np.abs(coords - coords[i]), axis=1)
        neighbors = perf[d <= tol]
        if len(neighbors) <= 1:
            plateau[i] = perf[i]
            continue
        plateau[i] = neighbors.mean() - lambda_std * neighbors.std()
    return plateau


def find_plateau_optimum(
    grid_result: dict,
    plateau_scores: np.ndarray,
) -> dict:
    """回傳 plateau argmax 對應的權重 + 該點原始績效."""
    combos = grid_result["combos"]
    if not combos or len(plateau_scores) == 0:
        return {"weights": {}, "f1": 0.0, "sharpe": 0.0, "plateau_score": 0.0,
                "argmax_idx": -1}
    idx = int(np.argmax(plateau_scores))
    return {
        "weights": combos[idx],
        "f1": float(grid_result["f1"][idx]),
        "sharpe": float(grid_result["sharpe"][idx]),
        "plateau_score": float(plateau_scores[idx]),
        "argmax_idx": idx,
    }


def _filter_events_by_window(
    events: list[CrisisEvent], start: pd.Timestamp, end: pd.Timestamp,
) -> list[CrisisEvent]:
    return [e for e in events if start <= pd.Timestamp(e.peak_date) <= end]


def _slice_series(
    series_by_key: dict[str, pd.Series], start: pd.Timestamp, end: pd.Timestamp,
) -> dict[str, pd.Series]:
    """切片各因子序列至 [start, end]。

    v19.2 hotfix：對非 DatetimeIndex 的空 Series（fetch 失敗時 default RangeIndex）做防禦，
    回對應 key 的空 DatetimeIndex Series，避免 ``RangeIndex >= Timestamp`` 觸發 TypeError。
    """
    out: dict[str, pd.Series] = {}
    for k, s in series_by_key.items():
        if s is None or s.empty or not isinstance(s.index, pd.DatetimeIndex):
            out[k] = pd.Series(dtype=float, name=k, index=pd.DatetimeIndex([]))
            continue
        out[k] = s[(s.index >= start) & (s.index <= end)]
    return out


def walk_forward_validate(
    factor_series_by_key: dict[str, pd.Series],
    returns: pd.Series,
    events: list[CrisisEvent],
    factor_keys: list[str],
    train_months: int = DEFAULT_TRAIN_MONTHS,
    test_months: int = DEFAULT_TEST_MONTHS,
    threshold: float = DEFAULT_THRESHOLD,
    step: float = DEFAULT_GRID_STEP,
    radius: int = DEFAULT_PLATEAU_RADIUS,
    lambda_std: float = DEFAULT_LAMBDA_STD,
    metric: Literal["f1", "sharpe"] = "f1",
    max_forward_days: int = 365,
    fwd_days: int = 60,
    specs_by_key: Optional[dict[str, FactorSpec]] = None,
) -> dict:
    """滾動 walk-forward：每窗訓練找 plateau → test 套用 → 串 OOS curve.

    Returns:
        {
          "folds": list[dict],         # 每折 train_range/test_range/weights/test_f1/test_sharpe
          "oos_crossings": pd.Series,  # 全 OOS 期間的訊號（concat）
          "oos_f1": float,             # 整段 OOS F1
          "oos_sharpe": float,
          "n_folds": int,
        }
    """
    if not factor_series_by_key or not factor_keys:
        return {"folds": [], "oos_crossings": pd.Series(dtype=int),
                "oos_f1": 0.0, "oos_sharpe": 0.0, "n_folds": 0,
                "status": "no_factors"}
    all_dates = pd.concat(factor_series_by_key.values()).index
    if all_dates.empty:
        return {"folds": [], "oos_crossings": pd.Series(dtype=int),
                "oos_f1": 0.0, "oos_sharpe": 0.0, "n_folds": 0,
                "status": "empty_series"}
    start = all_dates.min()
    end = all_dates.max()
    train_delta = pd.DateOffset(months=train_months)
    test_delta = pd.DateOffset(months=test_months)
    if start + train_delta + test_delta > end:
        return {"folds": [], "oos_crossings": pd.Series(dtype=int),
                "oos_f1": 0.0, "oos_sharpe": 0.0, "n_folds": 0,
                "status": "window_larger_than_data"}
    folds: list[dict] = []
    oos_pieces: list[pd.Series] = []
    cursor = start
    while cursor + train_delta + test_delta <= end:
        train_start = cursor
        train_end = cursor + train_delta
        test_start = train_end
        test_end = train_end + test_delta
        train_series = _slice_series(factor_series_by_key, train_start, train_end)
        train_returns = returns[(returns.index >= train_start) & (returns.index <= train_end)]
        train_events = _filter_events_by_window(events, train_start, train_end)
        train_grid = grid_search_performance(
            train_series, train_returns, train_events, factor_keys, threshold,
            step, max_forward_days, fwd_days, specs_by_key,
        )
        plateau = evaluate_plateau(train_grid, factor_keys, step, radius,
                                   lambda_std, metric)
        opt = find_plateau_optimum(train_grid, plateau)
        if not opt["weights"]:
            cursor = test_end
            continue
        test_series = _slice_series(factor_series_by_key, test_start, test_end)
        test_returns = returns[(returns.index >= test_start) & (returns.index <= test_end)]
        test_events = _filter_events_by_window(events, test_start, test_end)
        test_score = compute_composite_score(test_series, opt["weights"], specs_by_key)
        test_crossings = score_to_signal(test_score, threshold) if not test_score.empty else pd.Series(dtype=int)
        test_f1_stat = evaluate_f1(test_crossings, test_events, max_forward_days)
        test_sharpe_stat = evaluate_sharpe(test_crossings, test_returns, fwd_days)
        folds.append({
            "fold": len(folds) + 1,
            "train_range": (str(train_start.date()), str(train_end.date())),
            "test_range": (str(test_start.date()), str(test_end.date())),
            "n_train_events": len(train_events),
            "n_test_events": len(test_events),
            "weights": opt["weights"],
            "train_f1": opt["f1"],
            "train_sharpe": opt["sharpe"],
            "train_plateau": opt["plateau_score"],
            "test_f1": test_f1_stat["f1"],
            "test_sharpe": test_sharpe_stat["sharpe"],
            "test_n_crossings": test_f1_stat["n_crossings"],
        })
        oos_pieces.append(test_crossings)
        cursor = test_end
    oos_crossings = (pd.concat(oos_pieces) if oos_pieces
                     else pd.Series(dtype=int))
    oos_events = _filter_events_by_window(
        events,
        oos_crossings.index.min() if not oos_crossings.empty else start,
        oos_crossings.index.max() if not oos_crossings.empty else end,
    )
    oos_f1_stat = evaluate_f1(oos_crossings, oos_events, max_forward_days)
    oos_sharpe_stat = evaluate_sharpe(oos_crossings, returns, fwd_days)
    return {
        "folds": folds,
        "oos_crossings": oos_crossings,
        "oos_f1": oos_f1_stat["f1"],
        "oos_sharpe": oos_sharpe_stat["sharpe"],
        "n_folds": len(folds),
        "status": "ok" if folds else "no_valid_fold",
    }


def build_plateau_heatmap_2d(
    grid_result: dict,
    plateau_scores: np.ndarray,
    factor_keys: list[str],
    free_dims: tuple[str, str],
    metric_name: str = "F1 plateau",
):
    """2D heatmap：free_dims = (x, y)，其他維度做投影（取 max plateau score）."""
    import plotly.graph_objects as go
    combos = grid_result["combos"]
    if not combos or len(plateau_scores) == 0:
        return go.Figure()
    x_key, y_key = free_dims
    xs = sorted({w[x_key] for w in combos})
    ys = sorted({w[y_key] for w in combos})
    Z = np.full((len(ys), len(xs)), np.nan)
    for w, p in zip(combos, plateau_scores):
        ix = xs.index(w[x_key])
        iy = ys.index(w[y_key])
        if np.isnan(Z[iy, ix]) or p > Z[iy, ix]:
            Z[iy, ix] = p
    fig = go.Figure(data=go.Heatmap(
        z=Z, x=xs, y=ys, colorscale="Viridis",
        colorbar=dict(title=metric_name),
    ))
    fig.update_layout(
        title=f"參數高原 2D 熱圖（自由軸：{x_key} × {y_key}）",
        xaxis_title=f"w({x_key})", yaxis_title=f"w({y_key})",
        height=420,
    )
    return fig


def build_plateau_surface_3d(
    grid_result: dict,
    plateau_scores: np.ndarray,
    factor_keys: list[str],
    free_dims: tuple[str, str],
    metric_name: str = "F1 plateau",
):
    """3D surface：free_dims = (x, y)，z = plateau score（其餘維度取 max 投影）."""
    import plotly.graph_objects as go
    combos = grid_result["combos"]
    if not combos or len(plateau_scores) == 0:
        return go.Figure()
    x_key, y_key = free_dims
    xs = sorted({w[x_key] for w in combos})
    ys = sorted({w[y_key] for w in combos})
    Z = np.full((len(ys), len(xs)), np.nan)
    for w, p in zip(combos, plateau_scores):
        ix = xs.index(w[x_key])
        iy = ys.index(w[y_key])
        if np.isnan(Z[iy, ix]) or p > Z[iy, ix]:
            Z[iy, ix] = p
    fig = go.Figure(data=go.Surface(
        z=Z, x=xs, y=ys, colorscale="Viridis",
        colorbar=dict(title=metric_name),
    ))
    fig.update_layout(
        title=f"參數高原 3D 曲面（自由軸：{x_key} × {y_key}）",
        scene=dict(xaxis_title=f"w({x_key})", yaxis_title=f"w({y_key})",
                   zaxis_title=metric_name),
        height=520,
    )
    return fig
