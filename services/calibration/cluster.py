"""services/cluster_calibration.py — v18.292 per-cluster 歷史 F1 校準

User 反饋鏈：
1. v18.291 加了 7 維獨立合議 → 但 user 仍想知道「每個 cluster 歷史準度多少」
2. 「系統承認自己有多不準」的真正落地

設計：
- 對過去 20 年每月逐 cluster 算 signal (🔴🟡🟢)
- 對映 SPX [t+1 ... t+3 月] 最大回撤 < -10% 為真值
- per-cluster：treat 🔴 為 "預警 = 1"，🟢🟡 為 "0"
- 計算 precision / recall / F1
- 結果寫 cache/cluster_calibration.json (30 天 TTL)

公開 API：
- run_cluster_calibration(indicators) → 跑完整校準
- get_cached_calibration() → 讀 cache（過期回 None）
- compute_cluster_f1(cluster_signals, truth) → 純函式給測試用
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd

from shared.colors import MATERIAL_GREEN, MATERIAL_ORANGE, MATERIAL_RED

_CACHE_DIR = Path("cache")
_CACHE_FILE = _CACHE_DIR / "cluster_calibration.json"
_TTL_DAYS = 30


def compute_cluster_f1(
    signals: pd.Series, truth: pd.Series
) -> dict:
    """純函式：給定 cluster signal Series + truth Series，算 precision/recall/F1。

    Args:
        signals: pd.Series of '🔴'/'🟡'/'🟢' (按月) — 對齊到 truth.index
        truth: pd.Series of 0/1 (按月) — 1 代表「未來 3 月真有大跌」

    Returns:
        {tp, fp, fn, tn, precision, recall, f1, n_obs, n_pos, n_pred_pos}
    """
    aligned = pd.DataFrame({"sig": signals, "t": truth}).dropna()
    if aligned.empty:
        return {"tp": 0, "fp": 0, "fn": 0, "tn": 0,
                "precision": 0.0, "recall": 0.0, "f1": 0.0,
                "n_obs": 0, "n_pos": 0, "n_pred_pos": 0}

    pred = aligned["sig"].astype(str).str.contains("🔴").astype(int)
    actual = aligned["t"].astype(int)

    tp = int(((pred == 1) & (actual == 1)).sum())
    fp = int(((pred == 1) & (actual == 0)).sum())
    fn = int(((pred == 0) & (actual == 1)).sum())
    tn = int(((pred == 0) & (actual == 0)).sum())

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)
          if (precision + recall) > 0 else 0.0)

    return {
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "n_obs": int(len(aligned)),
        "n_pos": int(actual.sum()),
        "n_pred_pos": int(pred.sum()),
    }


def _signal_from_norm(norm: float) -> str:
    """同 compute_cluster_signals 的 threshold — 保持一致。"""
    if norm >= 0.3:
        return "🟢 安全"
    if norm <= -0.3:
        return "🔴 危險"
    return "🟡 警戒"


def _aligned_score_history(
    indicators_now: dict, years: int = 20, freq: str = "ME"
) -> pd.DataFrame:
    """對齊各 indicator series 到月末 + 套用 SCORE_RULES → 月度 (key, score, weight) 表。

    Returns:
        DataFrame indexed by month-end, columns = indicator keys, values = score
        ＋ DataFrame columns = indicator keys, values = weight (常數)
    """
    from services.macro_validation import SCORE_RULES

    end = pd.Timestamp.today().normalize()
    start = end - pd.DateOffset(years=int(years))
    date_range = pd.date_range(start=start, end=end, freq=freq)

    score_data: dict[str, pd.Series] = {}
    weights: dict[str, float] = {}
    for key, (w, score_fn) in SCORE_RULES.items():
        ind = (indicators_now or {}).get(key)
        if not ind:
            continue
        s = ind.get("series")
        if s is None or (hasattr(s, "empty") and s.empty):
            continue
        s = s.copy()
        if not isinstance(s.index, pd.DatetimeIndex):
            try:
                s.index = pd.to_datetime(s.index)
            except Exception:
                continue
        s = s.sort_index()
        aligned = s.reindex(date_range, method="ffill")
        scored = aligned.apply(
            lambda v: max(-w, min(w, float(score_fn(float(v)))))
            if pd.notna(v) else float("nan")
        )
        score_data[key] = scored
        weights[key] = w

    score_df = pd.DataFrame(score_data, index=date_range)
    return score_df, weights


def _cluster_norm_history(
    score_df: pd.DataFrame, weights: dict
) -> pd.DataFrame:
    """從各 indicator 月度 score → 各 cluster 月度 norm (-1~+1)。

    Returns:
        DataFrame indexed by month-end, columns = cluster name, values = norm
    """
    from services.macro_service import INDEPENDENT_CLUSTERS

    out: dict[str, pd.Series] = {}
    for cluster in INDEPENDENT_CLUSTERS:
        # 找出該 cluster 在 SCORE_RULES 裡實際有的 key
        avail_keys = [k for k in cluster["keys"] if k in score_df.columns]
        if not avail_keys:
            out[cluster["name"]] = pd.Series(dtype=float, index=score_df.index)
            continue
        # 每月 weighted avg (考慮 NaN)
        # 注意：score 已是絕對值（已 clamp 到 [-w, +w]），不該再乘 weight
        # norm = sum(score_per_indicator) / sum(weight_of_non_nan_indicator)
        sub = score_df[avail_keys]
        w_arr = pd.Series({k: weights[k] for k in avail_keys})
        sum_w = (sub.notna() * w_arr).sum(axis=1)  # 該月有資料的 weight 總和
        # W5-6 §1 註明:fillna(0) 對應「該指標當月無資料」,搭配 sum_w 只計入 notna 的 weight,
        # 結果為「對有資料指標」做加權平均,數學上正確(非掩蓋)
        sum_s = sub.fillna(0).sum(axis=1)           # 該月 score 直接相加
        norm = (sum_s / sum_w).where(sum_w > 0)
        out[cluster["name"]] = norm
    return pd.DataFrame(out)


def _spx_forward_drawdown_labels(
    spx_daily: pd.Series, horizon_months: int = 3, threshold: float = -0.10
) -> pd.Series:
    """對每月末，往前看 horizon 月 SPX 最大回撤；< -10% 標 1。

    Returns:
        pd.Series indexed by month-end, values = 0 或 1
    """
    if spx_daily is None or spx_daily.empty:
        return pd.Series(dtype=float)
    spx = spx_daily.copy()
    if not isinstance(spx.index, pd.DatetimeIndex):
        spx.index = pd.to_datetime(spx.index)
    spx = spx.sort_index()
    # resample 月末
    monthly = spx.resample("ME").last().dropna()

    labels = []
    for i, dt in enumerate(monthly.index):
        end_dt = dt + pd.DateOffset(months=horizon_months)
        window = spx.loc[dt:end_dt]
        if len(window) < 2:
            labels.append(float("nan"))
            continue
        peak_so_far = window.cummax()
        dd = (window / peak_so_far - 1).min()
        labels.append(1.0 if dd < threshold else 0.0)
    return pd.Series(labels, index=monthly.index)


def run_cluster_calibration(
    indicators_now: dict,
    years: int = 20,
    horizon_months: int = 3,
    dd_threshold: float = -0.10,
) -> dict:
    """跑完整 per-cluster F1 校準。

    Args:
        indicators_now: fetch_all_indicators 輸出，需含 .series
        years: 回看年數
        horizon_months: SPX 預警視窗（月）
        dd_threshold: 「大跌」門檻（負數）

    Returns:
        {
          "timestamp": float,
          "years": int,
          "horizon_months": int,
          "dd_threshold": float,
          "clusters": [{name, f1, precision, recall, n_obs, n_pos, n_pred_pos, ...}],
          "errors": [...],
        }
    """
    result = {
        "timestamp": time.time(),
        "years": years,
        "horizon_months": horizon_months,
        "dd_threshold": dd_threshold,
        "clusters": [],
        "errors": [],
    }

    # 1. 抓 SPX
    try:
        from services.crisis_backtest import fetch_market_series
        spx = fetch_market_series("SPX", years=years + 1)
        if spx is None or spx.empty:
            result["errors"].append("SPX 抓取失敗（空 series）")
            return result
    except Exception as e:
        result["errors"].append(f"SPX 抓取例外：{e}")
        return result

    # 2. 算月度 truth label
    truth = _spx_forward_drawdown_labels(
        spx, horizon_months=horizon_months, threshold=dd_threshold
    )
    if truth.empty:
        result["errors"].append("Truth label 算不出（SPX 太短）")
        return result

    # 3. 算月度各 cluster norm
    try:
        score_df, weights = _aligned_score_history(indicators_now, years=years)
        if score_df.empty:
            result["errors"].append("各 indicator series 對齊後為空")
            return result
        cluster_norm_df = _cluster_norm_history(score_df, weights)
    except Exception as e:
        result["errors"].append(f"算 cluster norm 失敗：{e}")
        return result

    # 4. 對每 cluster 算 F1
    from services.macro_service import INDEPENDENT_CLUSTERS
    for cluster in INDEPENDENT_CLUSTERS:
        name = cluster["name"]
        norm_series = cluster_norm_df.get(name)
        if norm_series is None or norm_series.dropna().empty:
            result["clusters"].append({
                "name": name, "icon": cluster["icon"],
                "f1": None, "precision": None, "recall": None,
                "n_obs": 0, "n_pos": 0, "n_pred_pos": 0,
                "note": "資料不足（SCORE_RULES 內無此 cluster 之 indicator）",
            })
            continue
        sig_series = norm_series.apply(
            lambda v: _signal_from_norm(v) if pd.notna(v) else float("nan")
        )
        stats = compute_cluster_f1(sig_series, truth)
        result["clusters"].append({
            "name": name, "icon": cluster["icon"],
            "f1": stats["f1"],
            "precision": stats["precision"],
            "recall": stats["recall"],
            "n_obs": stats["n_obs"],
            "n_pos": stats["n_pos"],
            "n_pred_pos": stats["n_pred_pos"],
        })

    return result


def save_calibration(payload: dict) -> bool:
    """寫 cache/cluster_calibration.json。"""
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _CACHE_FILE.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return True
    except Exception:
        return False


def get_cached_calibration() -> dict | None:
    """讀 cache；超過 _TTL_DAYS 天當過期回 None。"""
    if not _CACHE_FILE.exists():
        return None
    try:
        data = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
        ts = float(data.get("timestamp", 0))
        if (time.time() - ts) > _TTL_DAYS * 86400:
            return None
        return data
    except Exception:
        return None


def f1_to_grade(f1: float | None) -> tuple[str, str]:
    """F1 分數 → (等級文字, 顏色) 給 UI 顯示。"""
    if f1 is None:
        return "n/a", "#666"
    if f1 >= 0.7:
        return "可信", MATERIAL_GREEN
    if f1 >= 0.5:
        return "參考", MATERIAL_ORANGE
    return "雜訊", MATERIAL_RED
