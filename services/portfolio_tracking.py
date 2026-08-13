"""services/portfolio_tracking.py — 組合績效追蹤(v19.430)。純函式,零 IO,不 import streamlit。

「定期追蹤投資組合績效」的兩層(數學全收口至 `portfolio_performance` SSOT):
- **走勢重建** `reconstruct_trend`:用「已累積的每檔 NAV × 目前權重」重建組合報酬走勢 + 當期指標。
  §A.7 年化閘門:共同交易日 < `PORTFOLIO_TREND_MIN_DAYS` → 只給累積曲線 + 期間報酬,**抑制年化**
  CAGR/σ/Sharpe(稀疏序列 ×√252 會失真,§4.6);< `PORTFOLIO_TREND_ROBUST_DAYS` → low_confidence。
- **快照列** `build_snapshot_row`:把當期(閘門後)指標 + 真實權重打包成 dict,交 L3 寫入 L1
  `portfolio_perf_repository`(本模組**不** import L1;維持純函式 + 分層,§8.2)。

§1 誠實:無共同交易日 / 權重全非正 / NAV 不足 → ok=False + reason,**不偽造走勢**;缺值不填 0。
§4.1 單位:權重 ratio(Σ=1)、報酬 %、252 交易日年化。§4.4 固定目前權重(明示 assumption)。
"""
from __future__ import annotations

import hashlib
import json

from services.portfolio_performance import (
    metrics_from_return_series,
    portfolio_returns,
)
from shared.signal_thresholds import (
    PORTFOLIO_TREND_MIN_DAYS,
    PORTFOLIO_TREND_ROBUST_DAYS,
)

_ASSUMPTION = "fixed-weight daily-rebalance"
# 年化閘門會抹掉的鍵(保留 period_return_pct —— 累積報酬不依賴年化,任何長度都成立)
_ANNUALIZED_KEYS = ("cagr_pct", "ann_vol_pct", "sharpe", "calmar")


def _tw_today() -> str:
    """今日(台北時區 UTC+8)ISO 日期字串。"""
    import datetime as _dt
    return _dt.datetime.now(_dt.timezone(_dt.timedelta(hours=8))).date().isoformat()


def _utc_now() -> str:
    import datetime as _dt
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def weights_fingerprint(weights_norm: dict) -> "tuple[str, str]":
    """歸一化權重 → (穩定 hash, JSON)。hash 對「排序後 {code: round(w,4)}」算,供快照去重/比對。"""
    _rounded = {str(k): round(float(v), 4) for k, v in sorted((weights_norm or {}).items())}
    _js = json.dumps(_rounded, ensure_ascii=False, sort_keys=True)
    _h = hashlib.md5(_js.encode("utf-8")).hexdigest()[:12]   # noqa: S324 — 非安全用途,只求穩定指紋
    return _h, _js


def reconstruct_trend(nav_by_code: dict, weights: dict, rf_annual: float = 0.0,
                      ccy_by_code=None, fx_series=None) -> dict:
    """已存 NAV + 目前權重 → 組合走勢 + 當期指標(閘門後)。

    Returns dict:
      ok                     : bool
      reason                 : str | None            # ok=False 時的誠實原因
      daily_returns          : pd.Series | None       # 組合每日報酬(共同交易日,已去首日 NaN)
      curve                  : pd.Series | None        # 累積成長(= Π(1+r);起點 ≈ 1+r1)
      metrics                : dict                    # metrics_from_return_series(閘門後可能抹年化)
      weights_norm           : dict                    # 歸一化後實際使用權重(Σ=1)
      n_funds_used, excluded : int, list
      coverage_start/end, n_days
      annualized_suppressed  : bool                    # True = 交易日太少,年化被抹(仍有累積報酬)
      low_confidence         : bool                    # True = 不足 1 年,標「參考」
      assumption             : str
    """
    _blank = {
        "ok": False, "reason": None, "daily_returns": None, "curve": None,
        "metrics": {}, "weights_norm": {}, "n_funds_used": 0, "excluded": [],
        "coverage_start": None, "coverage_end": None, "n_days": 0,
        "annualized_suppressed": False, "low_confidence": False,
        "assumption": _ASSUMPTION,
    }

    if not nav_by_code:
        return {**_blank, "reason": "尚未提供任何基金 NAV —— 無法追蹤(§1)"}

    # v19.449 稽核 HIGH:傳入 ccy+fx → 各檔轉 TWD basis 再重建走勢(含匯率損益);
    # 缺 ccy/fx 時退回原幣加權(向後相容,單一幣別組合無差)。
    _res = portfolio_returns(nav_by_code, weights, ccy_by_code, fx_series)
    if _res is None:
        return {**_blank, "reason": "無共同交易日 / 權重全非正 / NAV 不足 —— 資料不足以重建走勢(§1)"}

    _port, _used, _w, _excluded = _res
    _metrics = dict(metrics_from_return_series(_port, rf_annual))
    _n = int(_metrics.get("n_days") or 0)

    _suppressed = _n < PORTFOLIO_TREND_MIN_DAYS
    if _suppressed:
        for _k in _ANNUALIZED_KEYS:                     # 年化太少 → 抹掉(保留 period_return_pct)
            _metrics[_k] = None
    _low_conf = (not _suppressed) and (_n < PORTFOLIO_TREND_ROBUST_DAYS)

    _curve = (1.0 + _port).cumprod()

    return {
        "ok": True,
        "reason": None,
        "daily_returns": _port,
        "curve": _curve,
        "metrics": _metrics,
        "weights_norm": _w,
        "n_funds_used": len(_used),
        "excluded": _excluded,
        "coverage_start": _metrics.get("start"),
        "coverage_end": _metrics.get("end"),
        "n_days": _n,
        "annualized_suppressed": _suppressed,
        "low_confidence": _low_conf,
        "assumption": _ASSUMPTION,
    }


def build_snapshot_row(
    nav_by_code: dict,
    weights: dict,
    *,
    total_cost_twd: "float | None" = None,
    is_equal_weight: bool = False,
    rf_annual: float = 0.0,
    today: "str | None" = None,
    recorded_at: "str | None" = None,
    ccy_by_code=None,
    fx_series=None,
) -> "dict | None":
    """當期(閘門後)指標 + 真實權重 → 快照 dict(欄位對齊 `PerfSnapshot`;不 import L1)。

    §1:資料不足以重建走勢 → 回 None(呼叫端據此不寫快照,不寫假資料)。
    total_cost_twd:成本基礎 Σ invest_twd(§B.2,非市值);由呼叫端算好傳入。
    today / recorded_at:預設台北今日 / UTC now,可注入以利測試(§5 可重現)。
    """
    _t = reconstruct_trend(nav_by_code, weights, rf_annual, ccy_by_code, fx_series)
    if not _t["ok"]:
        return None

    _m = _t["metrics"]
    _hash, _js = weights_fingerprint(_t["weights_norm"])
    return {
        "date": today or _tw_today(),
        "period_return_pct": _m.get("period_return_pct"),
        "cagr_pct": _m.get("cagr_pct"),
        "ann_vol_pct": _m.get("ann_vol_pct"),
        "sharpe": _m.get("sharpe"),
        "max_drawdown_pct": _m.get("max_drawdown_pct"),
        "n_funds": _t["n_funds_used"],
        "total_cost_twd": (float(total_cost_twd) if total_cost_twd is not None else None),
        "is_equal_weight": bool(is_equal_weight),
        "weights_hash": _hash,
        "weights_json": _js,
        "coverage_start": _t["coverage_start"] or "",
        "coverage_end": _t["coverage_end"] or "",
        "n_days": _t["n_days"],
        "recorded_at": recorded_at or _utc_now(),
    }


__all__ = ["reconstruct_trend", "build_snapshot_row", "weights_fingerprint"]
