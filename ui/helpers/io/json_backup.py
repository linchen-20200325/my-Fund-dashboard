"""v18.161 PR：JSON 備份 / 還原 helper（純函式，便於上下方快捷面板共用）。

抽自 ui/tab3_portfolio.py L920+ 的 `_pm_export_payload` / restore 邏輯，
讓上方互動式快捷面板與下方完整 backup 段共用同一份序列化規則，
也方便寫單元測試（不必模擬 streamlit runtime）。
"""
from __future__ import annotations

import json as _json
from typing import Any, MutableMapping

from shared.policy_tier import CORE_TIER, SATELLITE_TIER, normalize_tier, resolve_tier
from ui.helpers.tw_time import tw_now

SCHEMA_VERSION = "1.0"

_IS_CORE_BY_TIER = {CORE_TIER: True, SATELLITE_TIER: False}


def build_export_payload(ss: MutableMapping[str, Any]) -> dict:
    """從 session_state（dict-like）建立 JSON 匯出 payload。

    剝掉 series / moneydj_raw 等大物件，只保留可序列化的核心欄位。
    """
    _slim_funds = []
    for _f in ss.get("portfolio_funds", []) or []:
        # 級別一律以 `policy_tier` 承載（v2 session 的級別住在 `is_core`，也收進來），
        # `is_core` 由它推得 —— 還原端只信 `policy_tier`（見 `restore_from_json_bytes`）。
        _tier = resolve_tier(_f)
        _slim_funds.append({
            "code":         _f.get("code", ""),
            "name":         _f.get("name", ""),
            "invest_twd":   _f.get("invest_twd", 0),
            "policy_id":    _f.get("policy_id", ""),
            "policy_name":  _f.get("policy_name", ""),
            "policy_tier":  _tier or "",
            "currency":     _f.get("currency", ""),
            "is_core":      _IS_CORE_BY_TIER.get(_tier),
            "invest_date":  _f.get("invest_date", ""),
            "fx_at_buy":    _f.get("fx_at_buy"),
            # v18.180：含息成本 + 現金給付% 一併備份。v1 保單分頁 schema 無此兩欄，
            # 只有 JSON 備份能讓它們離線還原（否則重整 Sheet 後歸零）。
            "avg_nav_with_div": _f.get("avg_nav_with_div", 0),
            "div_cash_pct":     _f.get("div_cash_pct", 100),
        })
    _ledgers_dict = {}
    for _pk, _l in (ss.get("t7_ledgers", {}) or {}).items():
        _to_dict = getattr(_l, "to_dict", None)
        _ledgers_dict[_pk] = _to_dict() if callable(_to_dict) else _l
    return {
        "schema_version":   SCHEMA_VERSION,
        "exported_at":      tw_now().isoformat(timespec="seconds"),
        "portfolio_funds":  _slim_funds,
        "t7_ledgers":       _ledgers_dict,
        "t7_scenarios":     list(ss.get("t7_scenarios", []) or []),
        "active_policy_id": ss.get("active_policy_id", ""),
        "policy_sheet_id":  ss.get("policy_sheet_id", ""),
    }


def restore_from_json_bytes(raw: bytes,
                            ss: MutableMapping[str, Any]) -> dict:
    """從 JSON bytes 還原 session_state。

    回傳：{ok: bool, n_funds: int, n_ledgers: int, error: str|None}
    """
    try:
        _data = _json.loads(raw.decode("utf-8"))
    except Exception as _e:
        return {"ok": False, "n_funds": 0, "n_ledgers": 0,
                "error": f"JSON 解析失敗：{str(_e)[:120]}"}
    if not isinstance(_data, dict) or "portfolio_funds" not in _data:
        return {"ok": False, "n_funds": 0, "n_ledgers": 0,
                "error": "格式錯誤（須含 portfolio_funds 欄位）"}

    _restored_funds = []
    for _f in _data.get("portfolio_funds", []) or []:
        _f.update({"loaded": False, "load_error": None})
        # 2026-10-10（級別三態）：備份裡的 `is_core` 一律不採 —— 舊備份的 `is_core` 可能是
        # 基金名稱猜測（改動前批次載入會覆寫未載入的基金），也可能是 Sheet 設定（已載入的基金
        # 經 v2 讀回後即為 Sheet 值），無法分辨。級別以備份裡的 `policy_tier` 為準；取不到時
        # 顯示未設定，重新從雲端讀取即可恢復。「全部寫入」時以 keep_sheet_tier 保留 Sheet 原值。
        _tier = normalize_tier(_f.get("policy_tier"))
        _f["policy_tier"] = _tier or ""
        _f["is_core"] = _IS_CORE_BY_TIER.get(_tier)
        _restored_funds.append(_f)
    ss["portfolio_funds"] = _restored_funds

    _restored_led: dict = {}
    try:
        from services.ledger_service import Ledger as _Ledger
        for _pk, _d in (_data.get("t7_ledgers", {}) or {}).items():
            try:
                _restored_led[_pk] = _Ledger.from_dict(_d)
            except Exception:
                continue
    except ImportError:
        _restored_led = dict(_data.get("t7_ledgers", {}) or {})
    ss["t7_ledgers"] = _restored_led

    # v18.191：讀取齊全 — 用帳本補齊 portfolio_funds spine + 回填成本基礎，
    # 確保還原後帳本不缺料（與 Sheet 讀回一致）。
    try:
        from ui.helpers.portfolio_load import reconcile_funds_with_ledgers
        _rec, _ = reconcile_funds_with_ledgers(ss["portfolio_funds"], _restored_led)
        ss["portfolio_funds"] = _rec
        _restored_funds = _rec
    except Exception:
        pass   # smoke-allow-pass — 對帳失敗不擋還原，既有資料仍在

    ss["t7_scenarios"] = list(_data.get("t7_scenarios", []) or [])
    if _data.get("policy_sheet_id"):
        ss["policy_sheet_id"] = _data["policy_sheet_id"]
    if _data.get("active_policy_id"):
        ss["active_policy_id"] = _data["active_policy_id"]
    ss.pop("_t7_auto_restore_done", None)

    return {"ok": True, "n_funds": len(_restored_funds),
            "n_ledgers": len(_restored_led), "error": None}
