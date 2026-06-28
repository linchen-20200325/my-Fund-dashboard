"""
test_ledger_store — _Ledgers tab + Sheets API 單元測試
gspread / google-auth 不需安裝（duck-typed MagicMock）
"""
from unittest.mock import MagicMock

import pytest

from repositories.ledger_repository import (
    LEDGER_COLS,
    LEDGER_TAB,
    append_ledger_row,
    ensure_ledger_worksheet,
    load_all_ledgers,
    replace_ledgers_for_policy,
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

    def _add(title, rows=500, cols=11):
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
# ensure_ledger_worksheet
# ──────────────────────────────────────────────────────────────────────
def test_ensure_ledger_creates_when_missing():
    sh = _make_sh({})
    client = _make_client(sh)
    ws = ensure_ledger_worksheet(client, "FAKE")
    sh.add_worksheet.assert_called_once()
    ws.append_row.assert_called_once_with(list(LEDGER_COLS))


def test_ensure_ledger_reuses_existing_with_header():
    ws = _make_ws(all_values=[list(LEDGER_COLS)])
    ws.row_values.return_value = list(LEDGER_COLS)
    sh = _make_sh({LEDGER_TAB: ws})
    client = _make_client(sh)
    out = ensure_ledger_worksheet(client, "FAKE")
    assert out is ws
    sh.add_worksheet.assert_not_called()
    # 表頭已存在，不應該再 append
    ws.append_row.assert_not_called()


# ──────────────────────────────────────────────────────────────────────
# load_all_ledgers
# ──────────────────────────────────────────────────────────────────────
def test_load_all_ledgers_empty_when_tab_missing():
    sh = _make_sh({})
    df = load_all_ledgers(_make_client(sh), "FAKE")
    assert df.empty
    assert list(df.columns) == list(LEDGER_COLS)


def test_load_all_ledgers_normalizes_types_and_date():
    records = [
        {"policy_id": "PL-1", "date": "2024/01/15", "code": "TLZF9",
         "action": "BUY", "units": "100.5", "nav_at_action": "12.34",
         "twd": "1,240", "fee": "", "note": " hi "},
        {"policy_id": "PL-2", "date": "2024-02-01", "code": "ACTI94",
         "action": "dividend", "units": 0, "nav_at_action": 0,
         "twd": 500, "fee": 0, "note": ""},
    ]
    ws = _make_ws(records=records)
    sh = _make_sh({LEDGER_TAB: ws})
    df = load_all_ledgers(_make_client(sh), "FAKE")
    assert len(df) == 2
    assert df.iloc[0]["date"] == "2024-01-15"
    assert df.iloc[0]["units"] == 100.5
    assert df.iloc[0]["twd"] == 1240.0
    assert df.iloc[0]["note"] == "hi"
    # action 不會被強制小寫（load 不動，append 才小寫）
    assert df.iloc[0]["action"] in ("BUY", "buy")


def test_append_ledger_normalizes_and_writes():
    ws = _make_ws(all_values=[list(LEDGER_COLS)])
    ws.row_values.return_value = list(LEDGER_COLS)
    sh = _make_sh({LEDGER_TAB: ws})
    client = _make_client(sh)
    append_ledger_row(client, "FAKE", {
        "policy_id": "PL-1", "date": "2024/03/05", "code": "TLZF9",
        "action": "BUY", "units": "10", "nav_at_action": "30.5",
        "twd": "300", "fee": "", "note": "test",
    })
    args = ws.append_row.call_args.args[0]
    assert args[0] == "PL-1"
    assert args[1] == "2024-03-05"
    assert args[2] == "TLZF9"
    assert args[3] == "buy"          # action 小寫化
    assert args[4] == 10.0
    assert args[5] == 30.5
    assert args[6] == 300.0
    assert args[8] == "test"


def test_append_ledger_rejects_missing_keys():
    sh = _make_sh({LEDGER_TAB: _make_ws()})
    client = _make_client(sh)
    with pytest.raises(PolicySheetError, match="policy_id"):
        append_ledger_row(client, "FAKE", {"code": "X", "action": "buy"})
    with pytest.raises(PolicySheetError, match="policy_id"):
        append_ledger_row(client, "FAKE", {"policy_id": "P1"})


# ──────────────────────────────────────────────────────────────────────
# replace_ledgers_for_policy
# ──────────────────────────────────────────────────────────────────────
def test_replace_ledgers_clears_then_writes():
    header = list(LEDGER_COLS)
    old_a1 = ["PL-A", "2024-01-01", "X", "buy", 1, 1, 1, 0, ""]
    old_a2 = ["PL-A", "2024-01-02", "X", "sell", 1, 1, 1, 0, ""]
    old_b  = ["PL-B", "2024-01-03", "Y", "buy", 1, 1, 1, 0, ""]
    ws = _make_ws(all_values=[header, old_a1, old_a2, old_b])
    ws.row_values.return_value = header
    sh = _make_sh({LEDGER_TAB: ws})
    client = _make_client(sh)

    new_rows = [
        {"date": "2024-02-01", "code": "Z", "action": "buy",
         "units": 5, "nav_at_action": 10, "twd": 50, "fee": 0, "note": ""},
        {"date": "2024-02-05", "code": "Z", "action": "dividend",
         "units": 0, "nav_at_action": 0, "twd": 8, "fee": 0, "note": "div"},
    ]
    count = replace_ledgers_for_policy(client, "FAKE", "PL-A", new_rows)
    assert count == 2

    # 應該刪除 PL-A 的兩列（從尾到頭 → row 3 然後 row 2）
    deleted_rows = [c.args[0] for c in ws.delete_rows.call_args_list]
    assert deleted_rows == [3, 2]
    # PL-B 列不應被刪
    assert 4 not in deleted_rows

    # 應該 append 兩列新資料（policy_id 強制覆寫成 PL-A）
    appended = [c.args[0] for c in ws.append_row.call_args_list]
    assert len(appended) == 2
    assert appended[0][0] == "PL-A"
    assert appended[0][2] == "Z"


def test_replace_ledgers_skips_rows_missing_code():
    ws = _make_ws(all_values=[list(LEDGER_COLS)])
    ws.row_values.return_value = list(LEDGER_COLS)
    sh = _make_sh({LEDGER_TAB: ws})
    client = _make_client(sh)
    count = replace_ledgers_for_policy(client, "FAKE", "PL-X", [
        {"date": "2024-01-01", "code": "", "action": "buy", "units": 1},   # skipped
        {"date": "2024-01-02", "code": "Z", "action": "buy", "units": 1},
    ])
    assert count == 1
