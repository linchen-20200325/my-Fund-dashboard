"""test_migrate_v149_schema — v1→v2 一次性 migration 工具測試。

涵蓋：
- `_fold_ledger_json` 把 _T7_State.ledger_json 序列化內容 fold 出 units / avg_nav / avg_fx
- `migrate_one_policy` 對單張保單 v1 → v2 整套流程
- `migrate_sheet` 帶 backup safety net + 冪等性（已是 v2 跳過）
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from scripts.migrate_v149_schema import (
    _fold_ledger_json,
    migrate_one_policy,
    migrate_sheet,
)
from repositories.policy_repository import ALL_COLS_V2, ITEM_TYPE_FUND


# ──────────────────────────────────────────────────────────────────────
# _fold_ledger_json
# ──────────────────────────────────────────────────────────────────────
def test_fold_ledger_json_empty_returns_zero_snapshot():
    assert _fold_ledger_json("") == {"units": 0.0, "avg_nav": 0.0, "avg_fx": 0.0}
    assert _fold_ledger_json("{}") == {"units": 0.0, "avg_nav": 0.0, "avg_fx": 0.0}


def test_fold_ledger_json_single_buy_yields_exact_avg():
    lj = json.dumps({"transactions": [
        {"action": "buy", "units": 100, "nav_at_action": 10, "twd": 30000},
    ]})
    out = _fold_ledger_json(lj)
    assert out["units"] == 100.0
    assert out["avg_nav"] == 10.0
    assert out["avg_fx"] == 30.0   # 30000 TWD / (100 × 10) = 30


def test_fold_ledger_json_weighted_avg_across_multiple_buys():
    """買兩次：100 @ NAV 10 / FX 30，再 50 @ NAV 12 / FX 32。
    units = 150
    avg_nav = (100×10 + 50×12) / 150 = 10.666...
    avg_fx  = (30000 + 19200) / (100×10 + 50×12) = 49200/1600 = 30.75
    """
    lj = json.dumps({"transactions": [
        {"action": "buy", "units": 100, "nav_at_action": 10, "twd": 30000},
        {"action": "buy", "units":  50, "nav_at_action": 12, "twd": 19200},
    ]})
    out = _fold_ledger_json(lj)
    assert out["units"] == 150.0
    assert abs(out["avg_nav"] - 10.6667) < 0.001
    assert abs(out["avg_fx"] - 30.75) < 0.001


def test_fold_ledger_json_sell_reduces_units_and_cost():
    """buy 100 @ 10 / FX 30、sell 30 @ 12 / FX 31 → 剩 70 units，
    剩餘成本 = 100×10 − 30×12 = 640；avg_nav = 640/70 ≈ 9.143
    剩餘 TWD 成本 = 30000 − 11160 = 18840；avg_fx = 18840/640 ≈ 29.44
    """
    lj = json.dumps({"transactions": [
        {"action": "buy", "units": 100, "nav_at_action": 10, "twd": 30000},
        {"action": "sell", "units": 30, "nav_at_action": 12, "twd": 11160},
    ]})
    out = _fold_ledger_json(lj)
    assert out["units"] == 70.0
    assert abs(out["avg_nav"] - 9.143) < 0.01
    assert abs(out["avg_fx"] - 29.44) < 0.05


def test_fold_ledger_json_handles_corrupt_json_gracefully():
    """壞 JSON / 非 list transactions → 安全回 0。"""
    assert _fold_ledger_json("not-json")["units"] == 0.0
    assert _fold_ledger_json('{"transactions": "wrong-type"}')["units"] == 0.0


def test_fold_ledger_json_skips_invalid_numeric_fields():
    """txn 內欄位無法 cast → 跳過該筆，不影響其他筆。"""
    lj = json.dumps({"transactions": [
        {"action": "buy", "units": "abc", "nav_at_action": 10},  # bad units
        {"action": "buy", "units": 50, "nav_at_action": 10, "twd": 15000},
    ]})
    out = _fold_ledger_json(lj)
    assert out["units"] == 50.0


# ──────────────────────────────────────────────────────────────────────
# migrate_one_policy
# ──────────────────────────────────────────────────────────────────────
def _make_v1_ws_with_records(records):
    ws = MagicMock()
    ws.get_all_records.return_value = records
    ws.row_values.return_value = ["policy_id", "policy_name", "fund_url",
                                   "invest_twd", "invest_date", "currency",
                                   "fx_at_buy", "notes", "policy_tier"]
    return ws


def test_migrate_one_policy_writes_v2_rows_from_v1_and_t7_state():
    """v1 保單分頁有 2 檔 fund，t7_index 提供 1 檔的 ledger_json →
    v2 應寫 2 列 fund（其中 1 列有持倉、1 列 zero snapshot）。
    """
    v1_records = [
        {"policy_id": "p1", "policy_name": "富達世界", "fund_url": "FIDXEQI",
         "invest_twd": "475000", "currency": "USD", "fx_at_buy": "31.2",
         "policy_tier": "core"},
        {"policy_id": "p1", "policy_name": "安聯科技", "fund_url": "ALLNATEC",
         "invest_twd": "155000", "currency": "USD", "fx_at_buy": "31.2",
         "policy_tier": "satellite"},
    ]
    v1_ws = _make_v1_ws_with_records(v1_records)

    write_ws = MagicMock()
    sh = MagicMock()
    # 路由：load_policy_worksheet 走的 sh.worksheet(...) 與 write_policy_v2 走的
    # sh.worksheet(_sanitize_tab_name(policy_id)) 同名 — 都回 v1_ws / write_ws；
    # 簡化：兩者用同一個 MagicMock（write_policy_v2 會呼叫 ws.update）
    sh.worksheet.return_value = v1_ws
    client = MagicMock(); client.open_by_key.return_value = sh

    # 用 patch 把 write 路徑分離（讓 load 用 v1_ws、write 用 write_ws）
    from unittest.mock import patch
    with patch("scripts.migrate_v149_schema.write_policy_v2") as mock_write:
        t7_index = {
            ("p1", "FIDXEQI"): json.dumps({"transactions": [
                {"action": "buy", "units": 1234.5, "nav_at_action": 12.345,
                 "twd": 475000},
            ]}),
        }
        stat = migrate_one_policy(client, "sid", "p1", t7_index)

    assert stat["funds"] == 2
    assert stat["errors"] == []
    mock_write.assert_called_once()
    _args = mock_write.call_args.args
    df_passed = _args[3]
    assert len(df_passed) == 2
    # 第 1 檔：用 ledger fold 結果
    row1 = df_passed.iloc[0]
    assert row1["fund_code"] == "FIDXEQI"
    assert row1["units"] == 1234.5
    assert abs(row1["avg_nav"] - 12.345) < 0.001
    assert row1["tier"] == "core"
    assert row1["item_type"] == ITEM_TYPE_FUND
    # 第 2 檔：t7_index 無此 key → units / avg_nav 為 0，avg_fx 用 fx_at_buy 補
    row2 = df_passed.iloc[1]
    assert row2["fund_code"] == "ALLNATEC"
    assert row2["units"] == 0.0
    assert row2["avg_fx"] == 31.2   # fallback from v1 fx_at_buy
    assert row2["tier"] == "satellite"


def test_migrate_one_policy_empty_v1_returns_zero_stats():
    """v1 保單分頁是空的 → 不寫 v2，stat funds=0。"""
    v1_ws = _make_v1_ws_with_records([])
    sh = MagicMock(); sh.worksheet.return_value = v1_ws
    client = MagicMock(); client.open_by_key.return_value = sh

    stat = migrate_one_policy(client, "sid", "p1", {})
    assert stat["funds"] == 0


# ──────────────────────────────────────────────────────────────────────
# migrate_sheet
# ──────────────────────────────────────────────────────────────────────
def test_migrate_sheet_with_backup_creates_backup_before_touching_original():
    """with_backup=True 必先呼叫 copy_sheet_as_backup 才動原本。"""
    backup_sh = MagicMock(); backup_sh.id = "BAK_ID"
    backup_sh.url = "https://docs.google.com/spreadsheets/d/BAK_ID/edit"

    client = MagicMock()
    client.copy.return_value = backup_sh

    sh = MagicMock(); sh.title = "Fund Dashboard"
    sh.worksheets.return_value = []
    client.open_by_key.return_value = sh

    summary = migrate_sheet(client, "SRC", with_backup=True)
    assert summary["backup_sheet_id"] == "BAK_ID"
    client.copy.assert_called_once()


def test_migrate_sheet_skips_v2_tabs():
    """已是 v2 的 worksheet 應該被認出來、不重複轉換。"""
    backup_sh = MagicMock(); backup_sh.id = "BAK_ID"
    backup_sh.url = "u"
    src_sh = MagicMock(); src_sh.title = "src"

    v2_ws = MagicMock(); v2_ws.title = "policy-v2"
    v2_ws.row_values.return_value = list(ALL_COLS_V2)

    client = MagicMock()
    client.copy.return_value = backup_sh
    client.open_by_key.return_value = src_sh
    src_sh.worksheets.return_value = [v2_ws]
    # _read_t7_state_rows 路徑：worksheet("_T7_State") raise → 回 []
    src_sh.worksheet.side_effect = Exception("no _T7_State")

    summary = migrate_sheet(client, "SRC", with_backup=True)
    assert summary["v2_already"] == 1
    assert summary["policies"] == 1
    assert summary["migrated"][0]["skipped"] == "already v2"


def test_migrate_sheet_aborts_if_backup_fails():
    """backup 失敗 → 中斷 migration，不動原 Sheet。"""
    client = MagicMock()
    client.copy.side_effect = Exception("Drive 403")
    src_sh = MagicMock(); src_sh.title = "src"
    client.open_by_key.return_value = src_sh

    summary = migrate_sheet(client, "SRC", with_backup=True)
    assert summary["backup_sheet_id"] == ""
    assert summary["policies"] == 0
    assert any("備份失敗" in e for e in summary["errors"])


def test_migrate_sheet_without_backup_runs_anyway():
    """with_backup=False → 跳過備份；可用於 dry-run / debug。"""
    src_sh = MagicMock(); src_sh.title = "src"
    src_sh.worksheets.return_value = []
    src_sh.worksheet.side_effect = Exception("no _T7_State")
    client = MagicMock(); client.open_by_key.return_value = src_sh

    summary = migrate_sheet(client, "SRC", with_backup=False)
    assert summary["backup_sheet_id"] == ""
    assert summary["policies"] == 0
    client.copy.assert_not_called()
