"""v19.198 P1-6 fund_grp_health 子套件 utility — 從 fund_grp_health_extras 主檔抽出。

_build_fund_dict / _safe_num 兩個共用 helper,供子模組(dividend/investment/risk/signals/ai)
複用。
"""
from __future__ import annotations


def _build_fund_dict(fd_raw: dict, code: str, principal_twd: float,
                     name_hint: str = "") -> dict:
    """把 _auto_fetch_moneydj 回傳的 raw dict 包成 portfolio_funds 標準結構。

    對照 tab3_portfolio.py L1522-1533 的組合建構邏輯。
    invest_twd 欄位給 fund_checkup._compute_fund_health_kpis 算「月配息 TWD」用。

    name_hint:呼叫端已知名(選股池 / 政策表)。線上抓不到真名(如 "AL" 系代碼)時
    用它,而非把代號當名字(v19.497 ALZF9);都沒有才退代號。
    """
    if not fd_raw:
        return {}
    return {
        "code": code,
        "name": fd_raw.get("fund_name") or (name_hint or "").strip() or code,
        "series": fd_raw.get("series"),
        "dividends": fd_raw.get("dividends", []) or [],
        "metrics": fd_raw.get("metrics", {}) or {},
        "moneydj_raw": fd_raw,
        "risk_metrics": fd_raw.get("risk_metrics", {}) or {},
        "currency": (fd_raw.get("currency", "")
                     or (fd_raw.get("metrics", {}) or {}).get("currency", "")),
        "loaded": True,
        "invest_twd": float(principal_twd or 0),
    }


# v19.222 P1-1:_safe_num 收口至 shared/converters.py SSOT
from shared.converters import safe_num as _safe_num  # noqa: E402
