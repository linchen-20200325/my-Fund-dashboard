"""v18.161 PR：JSON 備份 / 還原 helper（純函式，便於上下方快捷面板共用）。

抽自 ui/tab3_portfolio.py L920+ 的 `_pm_export_payload` / restore 邏輯，
讓上方互動式快捷面板與下方完整 backup 段共用同一份序列化規則，
也方便寫單元測試（不必模擬 streamlit runtime）。
"""
from __future__ import annotations

import datetime as _dt
import json as _json
from typing import Any, MutableMapping

SCHEMA_VERSION = "1.0"


def build_export_payload(ss: MutableMapping[str, Any]) -> dict:
    """從 session_state（dict-like）建立 JSON 匯出 payload。

    剝掉 series / moneydj_raw 等大物件，只保留可序列化的核心欄位。
    """
    _slim_funds = []
    for _f in ss.get("portfolio_funds", []) or []:
        _slim_funds.append({
            "code":         _f.get("code", ""),
            "name":         _f.get("name", ""),
            "invest_twd":   _f.get("invest_twd", 0),
            "policy_id":    _f.get("policy_id", ""),
            "policy_name":  _f.get("policy_name", ""),
            "policy_tier":  _f.get("policy_tier", ""),
            "currency":     _f.get("currency", ""),
            "is_core":      _f.get("is_core"),
            "invest_date":  _f.get("invest_date", ""),
            "fx_at_buy":    _f.get("fx_at_buy"),
        })
    _ledgers_dict = {}
    for _pk, _l in (ss.get("t7_ledgers", {}) or {}).items():
        _to_dict = getattr(_l, "to_dict", None)
        _ledgers_dict[_pk] = _to_dict() if callable(_to_dict) else _l
    return {
        "schema_version":   SCHEMA_VERSION,
        "exported_at":      _dt.datetime.now().isoformat(timespec="seconds"),
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

    ss["t7_scenarios"] = list(_data.get("t7_scenarios", []) or [])
    if _data.get("policy_sheet_id"):
        ss["policy_sheet_id"] = _data["policy_sheet_id"]
    if _data.get("active_policy_id"):
        ss["active_policy_id"] = _data["active_policy_id"]
    ss.pop("_t7_auto_restore_done", None)

    return {"ok": True, "n_funds": len(_restored_funds),
            "n_ledgers": len(_restored_led), "error": None}
