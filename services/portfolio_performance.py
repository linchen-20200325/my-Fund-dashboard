"""services/portfolio_performance.py — 組合層績效(v19.421)。純函式,零 IO。

輸入各基金 NAV 序列 + 權重 → 組合層指標。假設**固定權重、每日再平衡**(明示於輸出
`assumption`);對齊到**所有納入基金的共同交易日**(§4.5 intersection,不 ffill 偽造);
權重非正 / 序列 <2 點的基金誠實排除並回報(§1);共同日 <2 → None。

指標:年化報酬(幾何)、年化波動(σ×√252)、Sharpe、最大回撤、各檔報酬貢獻。
交易日年化用 252(§4.1);無風險利率 `rf_annual` 由呼叫端指定(預設 0,明示)。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from shared.signal_thresholds import TRADING_DAYS_PER_YEAR

_BLANK: dict = {
    "ann_return_pct": None, "ann_vol_pct": None, "sharpe": None,
    "max_drawdown_pct": None, "n_days": 0, "start": None, "end": None,
    "n_funds_used": 0, "excluded": [], "assumption": "fixed-weight daily-rebalance",
}


def _clean_nav(nav) -> "pd.Series | None":
    """NAV 序列 → 乾淨升冪 Series(tz-naive, 唯一日期, >0);<2 點 → None。"""
    if nav is None:
        return None
    s = pd.Series(nav).dropna()
    if len(s) < 2:
        return None
    idx = pd.to_datetime(s.index, errors="coerce")
    s = s[idx.notna()]
    idx = idx[idx.notna()]
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_localize(None)
    s.index = idx
    s = s.sort_index()
    s = s[~s.index.duplicated(keep="last")]
    s = s[s > 0]
    return s if len(s) >= 2 else None


def _normalize_weights(weights: dict, codes: list) -> "dict | None":
    """取 codes 子集的正權重並歸一(Σ=1);全非正 → None。"""
    _w = {c: float(weights.get(c, 0) or 0) for c in codes}
    _pos = {c: v for c, v in _w.items() if v > 0}
    _tot = sum(_pos.values())
    if _tot <= 0:
        return None
    return {c: v / _tot for c, v in _pos.items()}


def portfolio_returns(nav_by_code: dict, weights: dict):
    """各基金 NAV + 權重 → (組合每日報酬 Series, 納入 codes, 歸一權重, 排除清單)。

    §1:權重非正 / NAV 不足的基金排除並回報;無共同交易日或 <2 → None。
    """
    excluded: list = []
    cleaned: dict = {}
    for _code, _nav in (nav_by_code or {}).items():
        _s = _clean_nav(_nav)
        if _s is None:
            excluded.append({"code": _code, "reason": "NAV 序列不足(<2 有效點)"})
        else:
            cleaned[_code] = _s

    _w = _normalize_weights(weights or {}, list(cleaned.keys()))
    if _w is None:
        return None
    # 只留有正權重的
    for _code in list(cleaned.keys()):
        if _code not in _w:
            excluded.append({"code": _code, "reason": "權重 ≤ 0(未納入)"})
            cleaned.pop(_code)
    if not cleaned:
        return None

    # 共同交易日 intersection(§4.5,不 ffill)
    _common = None
    for _s in cleaned.values():
        _common = _s.index if _common is None else _common.intersection(_s.index)
    if _common is None or len(_common) < 2:
        return None

    # 各基金於共同日的日報酬,加權求和(固定權重)
    _port = None
    for _code, _s in cleaned.items():
        _r = _s.loc[_common].pct_change()
        _contrib = _r * _w[_code]
        _port = _contrib if _port is None else _port.add(_contrib, fill_value=0.0)
    _port = _port.dropna()                      # 第一天無前值 → NaN,丟(不填 0)
    if len(_port) < 2:
        return None
    return _port, list(cleaned.keys()), _w, excluded


def metrics_from_return_series(daily_returns, rf_annual: float = 0.0) -> dict:
    """日報酬 Series → 風險調整指標(組合層 SSOT)。<2 有效點 → 全 None。

    CAGR = 幾何((1+累積)^(252/n)−1);波動 = std(ddof=1)×√252;Sharpe =(CAGR−rf)/波動
    (波動=0 → None,§1 不硬除);最大回撤 = min(累積/前高−1);Calmar = CAGR/|MaxDD|
    (無回撤 → None,不除零)。start/end 由序列 index 首末日期。
    """
    _s = pd.Series(daily_returns).dropna()
    _n = len(_s)
    _blank = {"cagr_pct": None, "ann_vol_pct": None, "sharpe": None,
              "max_drawdown_pct": None, "calmar": None, "period_return_pct": None,
              "n_days": _n, "start": None, "end": None}
    if _n < 2:
        return _blank
    _tpy = TRADING_DAYS_PER_YEAR

    _cum = float((1.0 + _s).prod())             # 累積乘積(= 期末/期初)
    _cagr = _cum ** (_tpy / _n) - 1.0 if _cum > 0 else None
    _ann_vol = float(_s.std(ddof=1)) * np.sqrt(_tpy)
    _sharpe = ((_cagr - rf_annual) / _ann_vol
               if (_cagr is not None and _ann_vol and _ann_vol > 0) else None)

    _curve = (1.0 + _s).cumprod()
    _dd = float((_curve / _curve.cummax() - 1.0).min())
    _calmar = (_cagr / abs(_dd)) if (_cagr is not None and _dd < 0) else None

    return {
        "cagr_pct": round(_cagr * 100.0, 2) if _cagr is not None else None,
        "ann_vol_pct": round(_ann_vol * 100.0, 2),
        "sharpe": round(_sharpe, 2) if _sharpe is not None else None,
        "max_drawdown_pct": round(_dd * 100.0, 2),
        "calmar": round(_calmar, 2) if _calmar is not None else None,
        "period_return_pct": round((_cum - 1.0) * 100.0, 2),   # 期間累積報酬(= 期末/期初 − 1)
        "n_days": _n,
        "start": str(_s.index[0].date()) if hasattr(_s.index[0], "date") else str(_s.index[0]),
        "end": str(_s.index[-1].date()) if hasattr(_s.index[-1], "date") else str(_s.index[-1]),
    }


def performance_metrics(nav_by_code: dict, weights: dict, rf_annual: float = 0.0) -> dict:
    """組合績效:{年化報酬% / 年化波動% / Sharpe / 最大回撤% / n_days / start / end / …}。

    數學收口至 `metrics_from_return_series`(SSOT);本函式維持既有出口鍵名 + 組合層欄位
    (n_funds_used / excluded / assumption),向後相容零變化。
    """
    _res = portfolio_returns(nav_by_code, weights)
    if _res is None:
        return dict(_BLANK)
    _port, _used, _w, _excluded = _res
    _base = metrics_from_return_series(_port, rf_annual)

    return {
        "ann_return_pct": _base["cagr_pct"],
        "ann_vol_pct": _base["ann_vol_pct"],
        "sharpe": _base["sharpe"],
        "max_drawdown_pct": _base["max_drawdown_pct"],
        "n_days": _base["n_days"],
        "start": _base["start"],
        "end": _base["end"],
        "n_funds_used": len(_used),
        "excluded": _excluded,
        "rf_annual": rf_annual,
        "assumption": "fixed-weight daily-rebalance",
    }


def contribution_by_fund(nav_by_code: dict, weights: dict) -> dict:
    """各檔對組合報酬的貢獻 = 權重 × 該檔於共同期間純價格報酬(百分點)。keyed by code。

    §4.5:各檔用**同一組共同交易日**的首/末量報酬(公平)。無共同期間 → {}。
    """
    _res = portfolio_returns(nav_by_code, weights)
    if _res is None:
        return {}
    _port, _used, _w, _ = _res
    # 重算共同日(portfolio_returns 內部已對齊,但這裡要各檔總報酬)
    cleaned = {c: _clean_nav(nav_by_code[c]) for c in _used}
    _common = None
    for _s in cleaned.values():
        _common = _s.index if _common is None else _common.intersection(_s.index)
    out: dict = {}
    for _code in _used:
        _s = cleaned[_code].loc[_common]
        _ret = float(_s.iloc[-1] / _s.iloc[0] - 1.0)
        out[_code] = {
            "weight_pct": round(_w[_code] * 100.0, 2),
            "fund_return_pct": round(_ret * 100.0, 2),
            "contribution_pct": round(_w[_code] * _ret * 100.0, 2),
        }
    return out
