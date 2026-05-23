"""
test_ledger_snapshot_store — _T7_State snapshot tab 單元測試
gspread / google-auth 不需安裝（duck-typed MagicMock + fund_ledger.Ledger）
"""
import json
from datetime import date
from unittest.mock import MagicMock

import pytest

from services.ledger_service import Ledger
from repositories.snapshot_repository import (
    HOLDINGS_COLS,
    HOLDINGS_TAB,
    SNAPSHOT_COLS,
    T7_STATE_TAB,
    ensure_state_worksheet,
    get_state_metadata,
    load_all_ledgers_snapshot,
    save_all_ledgers_snapshot,
    save_holdings_overview,
)
from repositories.policy_repository import PolicySheetError


def _make_ws(records=None, all_values=None):
    ws = MagicMock()
    ws.get_all_records.return_value = records or []
    ws.get_all_values.return_value = all_values or []
    ws.row_values.return_value = (all_values or [[]])[0] if all_values else []
    return ws


def _make_sh(tab_to_ws):
    sh = MagicMock()

    def _ws_by_name(name):
        if name not in tab_to_ws:
            raise Exception(f"worksheet '{name}' not found")
        return tab_to_ws[name]

    sh.worksheet.side_effect = _ws_by_name

    def _add(title, rows=200, cols=8):
        new = _make_ws(all_values=[])
        new.title = title
        tab_to_ws[title] = new
        return new

    sh.add_worksheet.side_effect = _add
    return sh


def _make_client(sh):
    c = MagicMock()
    c.open_by_key.return_value = sh
    return c


# ──────────────────────────────────────────────────────────────────────
# ensure_state_worksheet
# ──────────────────────────────────────────────────────────────────────
def test_ensure_state_creates_when_missing():
    sh = _make_sh({})
    ws = ensure_state_worksheet(_make_client(sh), "FAKE")
    sh.add_worksheet.assert_called_once()
    ws.append_row.assert_called_once_with(list(SNAPSHOT_COLS))


def test_ensure_state_reuses_with_header():
    ws = _make_ws(all_values=[list(SNAPSHOT_COLS)])
    ws.row_values.return_value = list(SNAPSHOT_COLS)
    sh = _make_sh({T7_STATE_TAB: ws})
    out = ensure_state_worksheet(_make_client(sh), "FAKE")
    assert out is ws
    sh.add_worksheet.assert_not_called()
    ws.append_row.assert_not_called()


# ──────────────────────────────────────────────────────────────────────
# save_all_ledgers_snapshot
# ──────────────────────────────────────────────────────────────────────
def test_save_empty_ledgers_returns_zero():
    sh = _make_sh({})
    assert save_all_ledgers_snapshot(_make_client(sh), "FAKE", {}) == 0


def test_save_writes_ledger_dict_as_json():
    """v18.73: 改為 batch update — 表頭 + 資料一次寫入，不再逐筆 append。"""
    led = Ledger(fund_code="TLZF9", currency="USD")
    led.subscribe(100_000.0, 31.5, 9.5, date(2024, 1, 15))
    ledgers = {"PL-001::TLZF9": led}
    funds = {"PL-001::TLZF9": {"policy_id": "PL-001"}}

    ws = _make_ws(all_values=[list(SNAPSHOT_COLS)])
    ws.row_values.return_value = list(SNAPSHOT_COLS)
    sh = _make_sh({T7_STATE_TAB: ws})
    count = save_all_ledgers_snapshot(_make_client(sh), "FAKE", ledgers, funds)

    assert count == 1
    ws.clear.assert_called_once()                          # v18.73: 先 clear
    update_call = ws.update.call_args
    values = update_call.kwargs.get("values") or update_call.args[1]
    # values[0] 是表頭，values[1] 起是 data rows
    assert values[0] == list(SNAPSHOT_COLS)
    appended = values[1]
    assert appended[0] == "PL-001::TLZF9"           # pk_str
    assert appended[1] == "TLZF9"                   # fund_code
    assert appended[2] == "USD"                     # currency
    assert appended[3] == "PL-001"                  # policy_id
    parsed = json.loads(appended[4])                # ledger_json
    assert parsed["fund_code"] == "TLZF9"
    assert len(parsed["transactions"]) == 1
    assert parsed["transactions"][0]["txn_type"] in ("subscribe", "BUY", "buy")
    assert appended[5]                              # updated_at 非空


def test_save_falls_back_pid_from_pk_when_no_lookup():
    """funds_lookup 為 None 時，從 pk_str 解析 policy_id（'pid::code' 結構）。"""
    led = Ledger(fund_code="X", currency="USD")
    led.subscribe(1.0, 1.0, 1.0, date(2024, 1, 1))
    ledgers = {"PID-X::X": led}

    ws = _make_ws(all_values=[list(SNAPSHOT_COLS)])
    ws.row_values.return_value = list(SNAPSHOT_COLS)
    sh = _make_sh({T7_STATE_TAB: ws})
    save_all_ledgers_snapshot(_make_client(sh), "FAKE", ledgers, None)
    update_call = ws.update.call_args
    values = update_call.kwargs.get("values") or update_call.args[1]
    appended = values[1]   # values[0] 是表頭
    assert appended[3] == "PID-X"


# ──────────────────────────────────────────────────────────────────────
# v18.182 save_holdings_overview（人看得懂的成本帳本 _持倉總覽）
# ──────────────────────────────────────────────────────────────────────
def test_overview_empty_returns_zero():
    sh = _make_sh({})
    assert save_holdings_overview(_make_client(sh), "FAKE", {}) == 0


def test_overview_writes_readable_row():
    led = Ledger(fund_code="TLZF9", currency="USD")
    led.subscribe(100_000.0, 31.5, 9.5, date(2024, 1, 15))
    # v18.180：含息成本若有設，position.cost_unit_with_div 反映之
    led.position.cost_unit_with_div = 8.0
    ledgers = {"PL-001::TLZF9": led}
    funds = {"PL-001::TLZF9": {
        "policy_id": "PL-001", "name": "安聯收益成長", "is_core": True,
        "invest_twd": 100_000, "div_cash_pct": 80.0,
    }}

    ws = _make_ws(all_values=[list(HOLDINGS_COLS)])
    ws.row_values.return_value = list(HOLDINGS_COLS)
    sh = _make_sh({HOLDINGS_TAB: ws})
    count = save_holdings_overview(_make_client(sh), "FAKE", ledgers, funds)

    assert count == 1
    ws.clear.assert_called_once()
    values = ws.update.call_args.kwargs.get("values") or ws.update.call_args.args[1]
    assert values[0] == list(HOLDINGS_COLS)
    row = values[1]
    assert row[0] == "PL-001"            # 保單號碼
    assert row[1] == "TLZF9"             # 基金代碼
    assert row[2] == "安聯收益成長"        # 基金名稱（來自 funds_lookup）
    assert row[3] == "USD"               # 幣別
    assert row[4] == "核心"               # 級別（is_core True）
    assert row[6] == 9.5                 # 平均成本淨值
    assert row[7] == 8.0                 # 平均含息成本（v18.180 設定值）
    assert row[8] == 31.5                # 平均匯率
    assert row[9] == 100_000             # 投資金額(TWD)
    assert row[10] == 80.0               # 現金給付%
    assert row[12]                       # 更新時間非空


def test_overview_tier_satellite_and_pid_fallback():
    led = Ledger(fund_code="ACDD01", currency="TWD")
    led.subscribe(50_000.0, 1.0, 100.0, date(2024, 2, 1))
    ledgers = {"PID-Z::ACDD01": led}
    funds = {"PID-Z::ACDD01": {"is_core": False}}   # 無 policy_id → 由 pk 解析

    ws = _make_ws(all_values=[list(HOLDINGS_COLS)])
    ws.row_values.return_value = list(HOLDINGS_COLS)
    sh = _make_sh({HOLDINGS_TAB: ws})
    save_holdings_overview(_make_client(sh), "FAKE", ledgers, funds)
    row = (ws.update.call_args.kwargs.get("values")
           or ws.update.call_args.args[1])[1]
    assert row[0] == "PID-Z"   # pid 從 pk_str fallback
    assert row[4] == "衛星"     # is_core False


def test_save_clears_old_rows_before_writing():
    """v18.73: 由 delete_rows 迴圈 → 單次 ws.clear()，把 API call 從 O(M+N) 降到 2 次。"""
    led = Ledger(fund_code="X", currency="USD")
    led.subscribe(1.0, 1.0, 1.0, date(2024, 1, 1))
    ledgers = {"::X": led}

    header = list(SNAPSHOT_COLS)
    old1 = ["::OLD1", "OLD1", "USD", "", "{}", ""]
    old2 = ["::OLD2", "OLD2", "USD", "", "{}", ""]
    ws = _make_ws(all_values=[header, old1, old2])
    ws.row_values.return_value = header
    sh = _make_sh({T7_STATE_TAB: ws})
    save_all_ledgers_snapshot(_make_client(sh), "FAKE", ledgers, None)

    # v18.73: 不再呼叫 delete_rows；改為單次 clear + 單次 update
    ws.delete_rows.assert_not_called()
    ws.clear.assert_called_once()
    ws.update.assert_called_once()


# ──────────────────────────────────────────────────────────────────────
# load_all_ledgers_snapshot
# ──────────────────────────────────────────────────────────────────────
def test_load_empty_when_missing_tab():
    sh = _make_sh({})
    out = load_all_ledgers_snapshot(_make_client(sh), "FAKE", Ledger)
    assert out == {}


def test_load_roundtrip_with_subscribed_ledger():
    """先 save 一筆，再 load 應拿回等價 Ledger（position 一致）。"""
    led = Ledger(fund_code="TLZF9", currency="USD")
    led.subscribe(100_000.0, 31.5, 9.5, date(2024, 1, 15))
    led_json = json.dumps(led.to_dict(), ensure_ascii=False)

    records = [{
        "pk_str":      "PL-001::TLZF9",
        "fund_code":   "TLZF9",
        "currency":    "USD",
        "policy_id":   "PL-001",
        "ledger_json": led_json,
        "updated_at":  "2024-01-15T10:00:00",
    }]
    ws = _make_ws(records=records)
    sh = _make_sh({T7_STATE_TAB: ws})

    out = load_all_ledgers_snapshot(_make_client(sh), "FAKE", Ledger)
    assert "PL-001::TLZF9" in out
    restored = out["PL-001::TLZF9"]
    assert restored.fund_code == "TLZF9"
    assert restored.currency == "USD"
    assert restored.position.units == led.position.units
    assert restored.position.cost_unit == led.position.cost_unit


def test_load_skips_invalid_json():
    records = [
        {"pk_str": "A::1", "ledger_json": "not-valid-json", "fund_code": "1",
         "currency": "USD", "policy_id": "A", "updated_at": ""},
        {"pk_str": "B::2", "ledger_json": "", "fund_code": "2",
         "currency": "USD", "policy_id": "B", "updated_at": ""},
    ]
    ws = _make_ws(records=records)
    sh = _make_sh({T7_STATE_TAB: ws})
    out = load_all_ledgers_snapshot(_make_client(sh), "FAKE", Ledger)
    assert out == {}


def test_get_state_metadata_returns_row_count_and_latest():
    records = [
        {"pk_str": "A::1", "fund_code": "1", "currency": "USD", "policy_id": "A",
         "ledger_json": "{}", "updated_at": "2024-01-10T00:00:00"},
        {"pk_str": "B::2", "fund_code": "2", "currency": "USD", "policy_id": "B",
         "ledger_json": "{}", "updated_at": "2024-02-20T00:00:00"},
    ]
    ws = _make_ws(records=records)
    sh = _make_sh({T7_STATE_TAB: ws})
    meta = get_state_metadata(_make_client(sh), "FAKE")
    assert meta["row_count"] == 2
    assert meta["latest_updated_at"] == "2024-02-20T00:00:00"


def test_get_state_metadata_empty_when_no_tab():
    sh = _make_sh({})
    assert get_state_metadata(_make_client(sh), "FAKE") == {}
