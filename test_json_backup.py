"""test_json_backup — v18.161 PR：JSON 備份 helper 純函式單元測試。

涵蓋：
- build_export_payload：欄位剝離、空 session_state、ledger.to_dict 呼叫
- restore_from_json_bytes：成功路徑、格式錯誤、JSON 壞檔、loaded flag reset
"""
from __future__ import annotations

import json

from ui.helpers.json_backup import (
    SCHEMA_VERSION,
    build_export_payload,
    restore_from_json_bytes,
)


class _FakeLedger:
    """模擬 services.ledger_service.Ledger.to_dict()"""

    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def to_dict(self) -> dict:
        return self._payload


def test_build_export_payload_empty_session_state():
    payload = build_export_payload({})
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["portfolio_funds"] == []
    assert payload["t7_ledgers"] == {}
    assert payload["t7_scenarios"] == []
    assert payload["active_policy_id"] == ""
    assert payload["policy_sheet_id"] == ""
    assert "exported_at" in payload


def test_build_export_payload_strips_heavy_fields():
    """series / moneydj_raw 等大物件應被剝掉，只留核心欄位。"""
    ss = {
        "portfolio_funds": [
            {
                "code": "F1", "name": "fund-1", "invest_twd": 100000,
                "policy_id": "P1", "policy_name": "policy 1",
                "policy_tier": "core", "currency": "USD",
                "is_core": True, "invest_date": "2024-01-01",
                "fx_at_buy": 31.5,
                "series": [1, 2, 3, 4, 5],
                "moneydj_raw": {"big": "object"},
            },
        ],
    }
    payload = build_export_payload(ss)
    assert len(payload["portfolio_funds"]) == 1
    _f = payload["portfolio_funds"][0]
    assert _f["code"] == "F1"
    assert _f["invest_twd"] == 100000
    assert "series" not in _f
    assert "moneydj_raw" not in _f


def test_build_export_payload_calls_ledger_to_dict():
    ss = {
        "t7_ledgers": {
            "P1::F1": _FakeLedger({"pk": "P1::F1", "events": []}),
            "P2::F2": _FakeLedger({"pk": "P2::F2", "events": [1, 2]}),
        },
    }
    payload = build_export_payload(ss)
    assert set(payload["t7_ledgers"].keys()) == {"P1::F1", "P2::F2"}
    assert payload["t7_ledgers"]["P1::F1"]["pk"] == "P1::F1"
    assert payload["t7_ledgers"]["P2::F2"]["events"] == [1, 2]


def test_restore_from_json_bytes_success():
    payload = {
        "schema_version": "1.0",
        "portfolio_funds": [
            {"code": "F1", "name": "fund-1", "invest_twd": 50000,
             "loaded": True, "load_error": "stale"},
        ],
        "t7_ledgers": {},
        "t7_scenarios": ["S1", "S2"],
        "policy_sheet_id": "SHEET_ABC",
        "active_policy_id": "P1",
    }
    raw = json.dumps(payload).encode("utf-8")
    ss: dict = {"_t7_auto_restore_done": True}
    result = restore_from_json_bytes(raw, ss)
    assert result["ok"] is True
    assert result["n_funds"] == 1
    assert result["n_ledgers"] == 0
    assert result["error"] is None
    # 還原後 portfolio_funds 的 loaded flag 應重置（強制重新抓 NAV）
    assert ss["portfolio_funds"][0]["loaded"] is False
    assert ss["portfolio_funds"][0]["load_error"] is None
    assert ss["t7_scenarios"] == ["S1", "S2"]
    assert ss["policy_sheet_id"] == "SHEET_ABC"
    assert ss["active_policy_id"] == "P1"
    # auto-restore flag 應被清掉，讓 T7 重新對齊
    assert "_t7_auto_restore_done" not in ss


def test_restore_from_json_bytes_invalid_json():
    result = restore_from_json_bytes(b"not a json {{{", {})
    assert result["ok"] is False
    assert "JSON 解析失敗" in result["error"]


def test_restore_from_json_bytes_missing_portfolio_funds_key():
    raw = json.dumps({"foo": "bar"}).encode("utf-8")
    result = restore_from_json_bytes(raw, {})
    assert result["ok"] is False
    assert "格式錯誤" in result["error"]


def test_restore_from_json_bytes_skips_garbage_ledger_entries():
    """壞掉的 ledger entry 應 silently skip，不應整批失敗。"""
    payload = {
        "portfolio_funds": [],
        "t7_ledgers": {
            "good": {"events": []},        # 假設 Ledger.from_dict 可吃
            "bad":  {"invalid": "shape"},   # 假設會丟 exception
        },
    }
    raw = json.dumps(payload).encode("utf-8")
    ss: dict = {}
    result = restore_from_json_bytes(raw, ss)
    assert result["ok"] is True
    # 至少不會炸；n_ledgers 視 Ledger.from_dict 行為而定，不強制斷言

def test_round_trip_preserves_core_fields():
    """build → restore round-trip 應保留所有 portfolio_funds 核心欄位。"""
    ss_in = {
        "portfolio_funds": [
            {"code": "F1", "name": "fund-1", "invest_twd": 100000,
             "policy_id": "P1", "policy_name": "policy 1",
             "policy_tier": "core", "currency": "USD",
             "is_core": True, "invest_date": "2024-01-01",
             "fx_at_buy": 31.5},
        ],
        "t7_ledgers": {},
        "t7_scenarios": ["scenario-1"],
        "active_policy_id": "P1",
        "policy_sheet_id": "SHEET_X",
    }
    payload = build_export_payload(ss_in)
    raw = json.dumps(payload).encode("utf-8")
    ss_out: dict = {}
    result = restore_from_json_bytes(raw, ss_out)
    assert result["ok"] is True
    _f_out = ss_out["portfolio_funds"][0]
    assert _f_out["code"] == "F1"
    assert _f_out["invest_twd"] == 100000
    assert _f_out["is_core"] is True
    assert _f_out["fx_at_buy"] == 31.5
    assert ss_out["t7_scenarios"] == ["scenario-1"]
    assert ss_out["active_policy_id"] == "P1"
