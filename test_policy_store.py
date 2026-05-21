"""
test_policy_store — gspread 整合層單元測試
重點：
- gspread / google-auth **不需安裝**也能跑完（lazy import + duck-typed mock）
- MagicMock 取代 client / worksheet，純函式直接餵 DataFrame
"""
from unittest.mock import MagicMock

import pandas as pd
import pytest

from repositories.policy_repository import (
    ALL_COLS,
    ALL_COLS_V2,
    ITEM_TYPE_CASH,
    ITEM_TYPE_FUND,
    OPTIONAL_COLS,
    REQUIRED_COLS,
    PolicySheetError,
    _sanitize_tab_name,
    copy_sheet_as_backup,
    create_dashboard_sheet,
    detect_sheet_schema_version,
    is_v2_worksheet,
    list_user_sheets,
    delete_fund_in_policy,
    delete_policy_row,
    delete_policy_worksheet,
    ensure_policy_worksheet,
    get_gspread_client,
    get_gspread_client_from_oauth,
    list_policy_worksheets,
    load_all_policies_v2,
    load_all_policy_worksheets,
    load_policies,
    load_policy_v2,
    load_policy_worksheet,
    sync_policies_to_portfolio_funds,
    upsert_fund_in_policy,
    upsert_policy_row,
    write_policy_v2,
)


# ──────────────────────────────────────────────────────────────────────
# helpers
# ──────────────────────────────────────────────────────────────────────
def _make_ws(records=None, all_values=None):
    ws = MagicMock()
    ws.get_all_records.return_value = records or []
    ws.get_all_values.return_value = all_values or []
    ws.row_values.return_value = (all_values or [[]])[0] if all_values else []
    return ws


def _make_client(ws):
    sh = MagicMock()
    sh.worksheet.return_value = ws
    client = MagicMock()
    client.open_by_key.return_value = sh
    return client


# ──────────────────────────────────────────────────────────────────────
# 1. get_gspread_client：credentials 缺欄即丟 PolicySheetError
# ──────────────────────────────────────────────────────────────────────
def test_get_gspread_client_invalid_creds_raises():
    with pytest.raises(PolicySheetError, match="client_email"):
        get_gspread_client({"type": "service_account"})  # 缺 client_email


# ──────────────────────────────────────────────────────────────────────
# 2. load_policies：空表 → 空 DataFrame（含 8 欄）
# ──────────────────────────────────────────────────────────────────────
def test_load_policies_empty_returns_empty_df_with_schema():
    ws = _make_ws(records=[])
    client = _make_client(ws)
    df = load_policies(client, "FAKE_ID")
    assert df.empty
    # P3：空表回 9 欄完整 schema（含選填 policy_tier）
    assert list(df.columns) == list(ALL_COLS)


# ──────────────────────────────────────────────────────────────────────
# 3. load_policies：缺欄 → 丟 PolicySheetError
# ──────────────────────────────────────────────────────────────────────
def test_load_policies_missing_columns_raises():
    bad = [{"policy_id": "P1", "policy_name": "保單A"}]  # 只 2 欄
    ws = _make_ws(records=bad)
    client = _make_client(ws)
    with pytest.raises(PolicySheetError, match="缺欄位"):
        load_policies(client, "FAKE_ID")


# ──────────────────────────────────────────────────────────────────────
# 4. load_policies：正常路徑 — invest_twd 字串→int、fx 容錯
# ──────────────────────────────────────────────────────────────────────
def test_load_policies_filters_schema_leak_rows():
    """v18.159：sheet 內若混進 schema header 字串當資料列（policy_name='policy_name',
    fund_url='fund_url'），load_policies 必須自動過濾掉，避免畫面顯示亂碼列。"""
    rows = [
        {
            "policy_id": "P1", "policy_name": "正常保單", "fund_url": "ACTI71",
            "invest_twd": 100000, "invest_date": "2024-01-01",
            "currency": "USD", "fx_at_buy": "31.5", "notes": "",
        },
        {
            # ← v1→v2 schema 遷移殘留 / JSON 還原把 header dict 當資料寫回
            "policy_id": "X", "policy_name": "policy_name", "fund_url": "fund_url",
            "invest_twd": 0, "invest_date": "", "currency": "", "fx_at_buy": "",
            "notes": "",
        },
        {
            "policy_id": "P2", "policy_name": "另一保單", "fund_url": "JFZN3",
            "invest_twd": 50000, "invest_date": "2024-02-01",
            "currency": "TWD", "fx_at_buy": "", "notes": "",
        },
    ]
    ws = _make_ws(records=rows)
    client = _make_client(ws)
    df = load_policies(client, "FAKE_ID")
    assert len(df) == 2   # schema-leak 列已過濾
    assert "policy_name" not in df["policy_name"].values
    assert "fund_url" not in df["fund_url"].values
    assert set(df["policy_id"]) == {"P1", "P2"}


def test_load_policies_happy_path_normalizes_types():
    rows = [
        {
            "policy_id": "P1", "policy_name": "南山UL01", "fund_url": "ABCD",
            "invest_twd": "1,000,000", "invest_date": "2024-03-01",
            "currency": "USD", "fx_at_buy": "31.5", "notes": "",
        },
        {
            "policy_id": "P1", "policy_name": "南山UL01", "fund_url": "WXYZ",
            "invest_twd": 500000, "invest_date": "2024-05-12",
            "currency": "TWD", "fx_at_buy": "", "notes": "test",
        },
    ]
    ws = _make_ws(records=rows)
    client = _make_client(ws)
    df = load_policies(client, "FAKE_ID")
    assert len(df) == 2
    assert df.loc[0, "invest_twd"] == 1_000_000
    assert df.loc[1, "invest_twd"] == 500_000
    assert df.loc[0, "fx_at_buy"] == 31.5
    assert pd.isna(df.loc[1, "fx_at_buy"])   # None 經 pandas 變 NaN（同義「缺值」）


# ──────────────────────────────────────────────────────────────────────
# 5. upsert_policy_row：不存在 → append_row 被呼叫
# ──────────────────────────────────────────────────────────────────────
def test_upsert_policy_row_inserts_new():
    header = list(REQUIRED_COLS)
    ws = _make_ws(all_values=[header])  # 只有表頭
    ws.row_values.return_value = header
    client = _make_client(ws)
    row = {
        "policy_id": "P2", "policy_name": "國泰VUL", "fund_url": "NEWURL",
        "invest_twd": 200000, "invest_date": "2025-01-15",
        "currency": "USD", "fx_at_buy": 32.0, "notes": "",
    }
    result = upsert_policy_row(client, "FAKE_ID", row)
    assert result == "inserted"
    ws.append_row.assert_called()
    ws.update.assert_not_called()


# ──────────────────────────────────────────────────────────────────────
# 6. upsert_policy_row：(policy_id, fund_url) 已存在 → 觸發 update
# ──────────────────────────────────────────────────────────────────────
def test_upsert_policy_row_updates_existing():
    header = list(REQUIRED_COLS)
    existing = [
        header,
        ["P2", "國泰VUL", "OLD_URL", "100000", "2024-01-01", "USD", "31.0", ""],
    ]
    ws = _make_ws(all_values=existing)
    ws.row_values.return_value = header
    client = _make_client(ws)
    row = {
        "policy_id": "P2", "policy_name": "國泰VUL", "fund_url": "OLD_URL",
        "invest_twd": 999999, "invest_date": "2024-01-01",
        "currency": "USD", "fx_at_buy": 31.0, "notes": "edited",
    }
    result = upsert_policy_row(client, "FAKE_ID", row)
    assert result == "updated"
    ws.update.assert_called_once()
    # 確認 update 範圍是第 2 列
    call_args = ws.update.call_args
    assert "2:H2" in call_args.args[0] or "A2:H2" in str(call_args)


def test_upsert_policy_row_missing_key_raises():
    client = _make_client(_make_ws())
    with pytest.raises(PolicySheetError, match="policy_id"):
        upsert_policy_row(client, "FAKE_ID", {"policy_id": "", "fund_url": "X"})


# ──────────────────────────────────────────────────────────────────────
# 7. delete_policy_row：命中 → delete_rows，未命中 → 回 False
# ──────────────────────────────────────────────────────────────────────
def test_delete_policy_row_hit_and_miss():
    header = list(REQUIRED_COLS)
    existing = [
        header,
        ["P1", "AAA", "URL_A", "1000", "", "", "", ""],
        ["P2", "BBB", "URL_B", "2000", "", "", "", ""],
    ]
    ws = _make_ws(all_values=existing)
    client = _make_client(ws)

    hit = delete_policy_row(client, "FAKE_ID", "P2", "URL_B")
    assert hit is True
    ws.delete_rows.assert_called_with(3)  # P2/URL_B 在第 3 列

    ws.delete_rows.reset_mock()
    miss = delete_policy_row(client, "FAKE_ID", "P99", "NOPE")
    assert miss is False
    ws.delete_rows.assert_not_called()


# ──────────────────────────────────────────────────────────────────────
# 8. sync_policies_to_portfolio_funds：純函式 add/keep/remove diff
# ──────────────────────────────────────────────────────────────────────
def test_sync_policies_to_portfolio_funds_diff():
    """v18.56: report 鍵改用 pk_str (`policy_id::code`)，匹配複合鍵 dedupe。"""
    df = pd.DataFrame([
        {"policy_id": "P1", "policy_name": "A", "fund_url": "AAAA",
         "invest_twd": 100, "invest_date": "", "currency": "USD",
         "fx_at_buy": 31.0, "notes": ""},
        {"policy_id": "P2", "policy_name": "B", "fund_url": "BBBB",
         "invest_twd": 200, "invest_date": "", "currency": "USD",
         "fx_at_buy": 31.0, "notes": ""},
    ])
    current = [
        {"code": "AAAA", "policy_id": "P1",
         "loaded": True, "metrics": {"nav": 12.3}, "invest_twd": 999},
        {"code": "ZZZZ", "policy_id": "P1", "loaded": True},   # 不在新表 → removed
    ]
    merged, report = sync_policies_to_portfolio_funds(df, current)

    codes = [f["code"] for f in merged]
    assert codes == ["AAAA", "BBBB"]
    aaaa = [f for f in merged if f["code"] == "AAAA"][0]
    assert aaaa["loaded"] is True               # 既存 loaded 保留
    assert aaaa["metrics"] == {"nav": 12.3}      # 既存 metrics 保留
    assert aaaa["invest_twd"] == 100             # 但 invest_twd 由 Sheet 蓋上
    assert aaaa["policy_id"] == "P1"

    bbbb = [f for f in merged if f["code"] == "BBBB"][0]
    assert bbbb["loaded"] is False               # 新加：未載入骨架

    assert set(report["added"]) == {"P2::BBBB"}
    assert set(report["kept"]) == {"P1::AAAA"}
    assert set(report["removed"]) == {"P1::ZZZZ"}


def test_sync_preserves_same_code_across_policies():
    """v18.56: 同 code 跨多保單 → 各自保留為獨立條目（不再合併）。

    使用者實況：JFZN3 在 4 張保單 / ACDD19 在 3 張保單 …等，舊版用 code-only
    dedupe 導致 19 筆讀回後縮成 7 檔，T7 帳本看不到對應保單。
    """
    df = pd.DataFrame([
        {"policy_id": "P1", "policy_name": "A", "fund_url": "DUP",
         "invest_twd": 100, "invest_date": "", "currency": "",
         "fx_at_buy": None, "notes": ""},
        {"policy_id": "P2", "policy_name": "B", "fund_url": "DUP",
         "invest_twd": 300, "invest_date": "", "currency": "",
         "fx_at_buy": None, "notes": ""},
        {"policy_id": "P3", "policy_name": "C", "fund_url": "DUP",
         "invest_twd": 500, "invest_date": "", "currency": "",
         "fx_at_buy": None, "notes": ""},
    ])
    merged, report = sync_policies_to_portfolio_funds(df, [])
    assert len(merged) == 3
    pids = sorted([f["policy_id"] for f in merged])
    assert pids == ["P1", "P2", "P3"]
    invests = sorted([f["invest_twd"] for f in merged])
    assert invests == [100, 300, 500]    # 各自保留，無加總
    assert set(report["added"]) == {"P1::DUP", "P2::DUP", "P3::DUP"}


def test_sync_aggregates_dup_rows_same_pk():
    """同 (policy_id, code) 在 Sheet 內出現兩次 → invest_twd 加總（罕見邊界）"""
    df = pd.DataFrame([
        {"policy_id": "P1", "policy_name": "A", "fund_url": "DUP",
         "invest_twd": 100, "invest_date": "", "currency": "",
         "fx_at_buy": None, "notes": ""},
        {"policy_id": "P1", "policy_name": "A", "fund_url": "DUP",
         "invest_twd": 50, "invest_date": "", "currency": "",
         "fx_at_buy": None, "notes": ""},
    ])
    merged, _ = sync_policies_to_portfolio_funds(df, [])
    assert len(merged) == 1
    assert merged[0]["invest_twd"] == 150
    assert merged[0]["policy_id"] == "P1"


def test_sync_empty_df_returns_empty():
    merged, report = sync_policies_to_portfolio_funds(pd.DataFrame(columns=REQUIRED_COLS), [])
    assert merged == []
    assert report == {"added": [], "kept": [], "removed": []}


# ──────────────────────────────────────────────────────────────────────
# P3：選填欄 policy_tier 行為（向後相容）
# ──────────────────────────────────────────────────────────────────────
def test_load_policies_missing_optional_column_backward_compat():
    """舊 8 欄 Sheet：load 應自動補 policy_tier="" 而非拋錯。"""
    rows = [{
        "policy_id": "P1", "policy_name": "A", "fund_url": "AAAA",
        "invest_twd": 100, "invest_date": "", "currency": "USD",
        "fx_at_buy": "31.0", "notes": "",
        # 故意不放 policy_tier
    }]
    ws = _make_ws(records=rows)
    client = _make_client(ws)
    df = load_policies(client, "FAKE_ID")
    assert "policy_tier" in df.columns
    assert df.loc[0, "policy_tier"] == ""


def test_load_policies_normalizes_policy_tier_to_lowercase_or_empty():
    rows = [
        {"policy_id": "P1", "policy_name": "A", "fund_url": "U1",
         "invest_twd": 100, "invest_date": "", "currency": "USD",
         "fx_at_buy": "31", "notes": "", "policy_tier": "Core"},
        {"policy_id": "P1", "policy_name": "A", "fund_url": "U2",
         "invest_twd": 50, "invest_date": "", "currency": "USD",
         "fx_at_buy": "31", "notes": "", "policy_tier": "SATELLITE"},
        {"policy_id": "P1", "policy_name": "A", "fund_url": "U3",
         "invest_twd": 50, "invest_date": "", "currency": "USD",
         "fx_at_buy": "31", "notes": "", "policy_tier": "亂填"},  # 非法 → ""
    ]
    ws = _make_ws(records=rows)
    client = _make_client(ws)
    df = load_policies(client, "FAKE_ID")
    assert df.loc[0, "policy_tier"] == "core"
    assert df.loc[1, "policy_tier"] == "satellite"
    assert df.loc[2, "policy_tier"] == ""


def test_sync_passes_policy_tier_through():
    df = pd.DataFrame([{
        "policy_id": "P1", "policy_name": "A", "fund_url": "AAAA",
        "invest_twd": 100, "invest_date": "", "currency": "USD",
        "fx_at_buy": 31.0, "notes": "", "policy_tier": "core",
    }])
    merged, _ = sync_policies_to_portfolio_funds(df, [])
    assert merged[0]["policy_tier"] == "core"


def test_upsert_writes_8_cols_if_sheet_has_legacy_header():
    """向後相容：舊 Sheet 表頭仍 8 欄時，upsert 不應寫第 9 欄破壞結構。"""
    legacy_header = list(REQUIRED_COLS)
    ws = _make_ws(all_values=[legacy_header])
    ws.row_values.return_value = legacy_header
    client = _make_client(ws)
    row = {
        "policy_id": "P9", "policy_name": "Legacy", "fund_url": "L1",
        "invest_twd": 1, "invest_date": "", "currency": "USD",
        "fx_at_buy": 31, "notes": "",
        "policy_tier": "core",  # 提供也不寫
    }
    result = upsert_policy_row(client, "FAKE_ID", row)
    assert result == "inserted"
    # append_row 收到的 list 應只 8 個元素（policy_tier 不被推入）
    _called_values = ws.append_row.call_args.args[0]
    assert len(_called_values) == len(REQUIRED_COLS)


def test_upsert_writes_9_cols_if_sheet_has_new_header():
    """新 Sheet 表頭含 policy_tier 時，upsert 應寫滿 9 欄。"""
    full_header = list(ALL_COLS)
    ws = _make_ws(all_values=[full_header])
    ws.row_values.return_value = full_header
    client = _make_client(ws)
    row = {
        "policy_id": "P9", "policy_name": "New", "fund_url": "N1",
        "invest_twd": 1, "invest_date": "", "currency": "USD",
        "fx_at_buy": 31, "notes": "",
        "policy_tier": "satellite",
    }
    result = upsert_policy_row(client, "FAKE_ID", row)
    assert result == "inserted"
    _called_values = ws.append_row.call_args.args[0]
    assert len(_called_values) == len(ALL_COLS)
    assert _called_values[-1] == "satellite"


# ══════════════════════════════════════════════════════════════════════
# P4：per-policy worksheet API
# ══════════════════════════════════════════════════════════════════════


def _make_sh_with_worksheets(tab_to_ws: dict):
    """sh 物件支援 .worksheets() / .worksheet(name) / .add_worksheet() / .del_worksheet()。"""
    sh = MagicMock()
    sh.worksheets.return_value = [
        MagicMock(title=t) for t in tab_to_ws.keys()
    ]

    def _ws_by_name(name):
        if name not in tab_to_ws:
            raise Exception(f"worksheet '{name}' not found")
        return tab_to_ws[name]

    sh.worksheet.side_effect = _ws_by_name

    def _add(title, rows=100, cols=12):
        new = _make_ws(all_values=[])
        new.title = title
        tab_to_ws[title] = new
        sh.worksheets.return_value = [MagicMock(title=t) for t in tab_to_ws.keys()]
        return new

    sh.add_worksheet.side_effect = _add
    sh.del_worksheet.side_effect = lambda ws: tab_to_ws.pop(ws.title, None)
    return sh


def _make_client_with_sh(sh):
    client = MagicMock()
    client.open_by_key.return_value = sh
    return client


def test_sanitize_tab_name_strips_bad_chars():
    assert _sanitize_tab_name("PL-2024-001") == "PL-2024-001"
    assert _sanitize_tab_name("a/b:c") == "a_b_c"
    assert _sanitize_tab_name("  spaces  ") == "spaces"


def test_sanitize_tab_name_rejects_empty_or_reserved():
    with pytest.raises(PolicySheetError, match="不可為空"):
        _sanitize_tab_name("")
    with pytest.raises(PolicySheetError, match="保留給系統"):
        _sanitize_tab_name("_Ledgers")


def test_list_policy_worksheets_filters_system_and_default():
    sh = _make_sh_with_worksheets({
        "PL-001": _make_ws(),
        "PL-002": _make_ws(),
        "_Ledgers": _make_ws(),     # 系統 tab，過濾掉
        "Policies": _make_ws(),     # 舊 schema 預設 tab，過濾掉
    })
    client = _make_client_with_sh(sh)
    names = list_policy_worksheets(client, "FAKE_ID")
    assert sorted(names) == ["PL-001", "PL-002"]


def test_ensure_policy_worksheet_creates_when_missing():
    sh = _make_sh_with_worksheets({})   # 空 sheet
    client = _make_client_with_sh(sh)
    ws = ensure_policy_worksheet(client, "FAKE_ID", "PL-NEW")
    # 應該呼叫 add_worksheet 且寫表頭
    sh.add_worksheet.assert_called_once()
    ws.append_row.assert_called_once_with(list(ALL_COLS))


def test_ensure_policy_worksheet_reuses_existing():
    existing_ws = _make_ws(all_values=[list(ALL_COLS)])
    existing_ws.row_values.return_value = list(ALL_COLS)
    sh = _make_sh_with_worksheets({"PL-EXIST": existing_ws})
    client = _make_client_with_sh(sh)
    ws = ensure_policy_worksheet(client, "FAKE_ID", "PL-EXIST")
    assert ws is existing_ws
    sh.add_worksheet.assert_not_called()


def test_load_policy_worksheet_returns_empty_when_missing():
    sh = _make_sh_with_worksheets({})
    client = _make_client_with_sh(sh)
    df = load_policy_worksheet(client, "FAKE_ID", "PL-MISSING")
    assert df.empty
    assert list(df.columns) == list(ALL_COLS)


def test_load_policy_worksheet_normalizes():
    records = [{
        "policy_id": "PL-1", "policy_name": "T", "fund_url": "TLZF9",
        "invest_twd": "100,000", "invest_date": "2024-01-01",
        "currency": "USD", "fx_at_buy": "31.5", "notes": "",
        "policy_tier": "CORE",
    }]
    ws = _make_ws(records=records)
    sh = _make_sh_with_worksheets({"PL-1": ws})
    client = _make_client_with_sh(sh)
    df = load_policy_worksheet(client, "FAKE_ID", "PL-1")
    assert len(df) == 1
    assert df.iloc[0]["invest_twd"] == 100000
    assert df.iloc[0]["fx_at_buy"] == 31.5
    assert df.iloc[0]["policy_tier"] == "core"


def test_load_all_policy_worksheets_concats_and_overrides_pid():
    """跨保單合併，且 tab 名強制覆寫 policy_id 欄。"""
    ws1 = _make_ws(records=[{
        "policy_id": "stale-001",  # 故意給髒值，下面確認被覆寫
        "policy_name": "A", "fund_url": "U1",
        "invest_twd": 100, "invest_date": "", "currency": "",
        "fx_at_buy": "", "notes": "", "policy_tier": "",
    }])
    ws2 = _make_ws(records=[{
        "policy_id": "stale-002", "policy_name": "B", "fund_url": "U2",
        "invest_twd": 200, "invest_date": "", "currency": "",
        "fx_at_buy": "", "notes": "", "policy_tier": "",
    }])
    sh = _make_sh_with_worksheets({"PL-001": ws1, "PL-002": ws2})
    client = _make_client_with_sh(sh)
    df = load_all_policy_worksheets(client, "FAKE_ID")
    assert len(df) == 2
    assert sorted(df["policy_id"].tolist()) == ["PL-001", "PL-002"]


def test_upsert_fund_in_policy_inserts_then_updates():
    ws = _make_ws(all_values=[list(ALL_COLS)])
    ws.row_values.return_value = list(ALL_COLS)
    sh = _make_sh_with_worksheets({"PL-X": ws})
    client = _make_client_with_sh(sh)

    row = {"fund_url": "TLZF9", "policy_name": "X", "invest_twd": 500,
           "invest_date": "", "currency": "USD", "fx_at_buy": 31, "notes": "",
           "policy_tier": "core"}
    action = upsert_fund_in_policy(client, "FAKE_ID", "PL-X", row)
    assert action == "inserted"
    # 確認 policy_id 強制覆寫成 tab 名
    appended = ws.append_row.call_args.args[0]
    assert appended[0] == "PL-X"

    # 第二次同 URL 應該 update
    ws.get_all_values.return_value = [list(ALL_COLS), appended]
    action2 = upsert_fund_in_policy(client, "FAKE_ID", "PL-X", row)
    assert action2 == "updated"


def test_upsert_fund_in_policy_requires_fund_url():
    sh = _make_sh_with_worksheets({"PL-Y": _make_ws()})
    client = _make_client_with_sh(sh)
    with pytest.raises(PolicySheetError, match="fund_url"):
        upsert_fund_in_policy(client, "FAKE_ID", "PL-Y", {"fund_url": ""})


def test_delete_fund_in_policy_hits_and_misses():
    header = list(ALL_COLS)
    hit_row = ["PL-Z", "Z", "TARGET_URL"] + [""] * (len(header) - 3)
    ws = _make_ws(all_values=[header, hit_row])
    sh = _make_sh_with_worksheets({"PL-Z": ws})
    client = _make_client_with_sh(sh)

    assert delete_fund_in_policy(client, "FAKE_ID", "PL-Z", "TARGET_URL") is True
    ws.delete_rows.assert_called_once_with(2)

    ws.get_all_values.return_value = [header]   # 已被刪
    assert delete_fund_in_policy(client, "FAKE_ID", "PL-Z", "TARGET_URL") is False


def test_delete_policy_worksheet_returns_false_when_missing():
    sh = _make_sh_with_worksheets({})
    client = _make_client_with_sh(sh)
    assert delete_policy_worksheet(client, "FAKE_ID", "PL-GONE") is False


def test_delete_policy_worksheet_returns_true_when_present():
    ws = _make_ws()
    ws.title = "PL-ALIVE"
    sh = _make_sh_with_worksheets({"PL-ALIVE": ws})
    client = _make_client_with_sh(sh)
    assert delete_policy_worksheet(client, "FAKE_ID", "PL-ALIVE") is True
    sh.del_worksheet.assert_called_once()


def test_get_gspread_client_from_oauth_rejects_none():
    with pytest.raises(PolicySheetError, match="OAuth flow"):
        get_gspread_client_from_oauth(None)


# ──────────────────────────────────────────────────────────────────────
# create_dashboard_sheet（v18.40）
# ──────────────────────────────────────────────────────────────────────
def test_create_dashboard_sheet_returns_id_and_url():
    fake_sh = MagicMock()
    fake_sh.id = "NEW_ID_123"
    fake_sh.url = "https://docs.google.com/spreadsheets/d/NEW_ID_123/edit"
    client = MagicMock()
    client.create.return_value = fake_sh

    sid, url = create_dashboard_sheet(client, "My Dashboard")
    assert sid == "NEW_ID_123"
    assert "NEW_ID_123" in url
    client.create.assert_called_once_with("My Dashboard")


def test_create_dashboard_sheet_raises_on_failure():
    client = MagicMock()
    client.create.side_effect = Exception("API quota exceeded")
    with pytest.raises(PolicySheetError, match="建立 Sheet 失敗"):
        create_dashboard_sheet(client, "x")


def _mock_drive_v3_response(files: list[dict]):
    """v18.155：mock Drive v3 list response（client.http_client.request 用）。"""
    resp = MagicMock()
    resp.json.return_value = {"files": files, "nextPageToken": None}
    return resp


def test_list_user_sheets_sorts_by_name():
    client = MagicMock()
    client.http_client.request.return_value = _mock_drive_v3_response([
        {"id": "ID_B", "name": "Zebra Sheet"},
        {"id": "ID_A", "name": "alpha Sheet"},
        {"id": "ID_C", "name": "Mid Sheet"},
    ])
    out = list_user_sheets(client)
    assert [f["id"] for f in out] == ["ID_A", "ID_C", "ID_B"]


def test_list_user_sheets_handles_missing_fields():
    client = MagicMock()
    client.http_client.request.return_value = _mock_drive_v3_response([
        {"id": "OK", "name": "Valid"},
        {"id": "NoName"},        # 缺 name → 跳過
        {"name": "NoId"},         # 缺 id → 跳過
        {},                       # 空 → 跳過
    ])
    out = list_user_sheets(client)
    assert len(out) == 1
    assert out[0]["id"] == "OK"


def test_list_user_sheets_raises_on_api_error():
    client = MagicMock()
    client.http_client.request.side_effect = Exception("403 insufficient scopes")
    with pytest.raises(PolicySheetError, match="列出 Drive Sheets 失敗"):
        list_user_sheets(client)


def test_list_user_sheets_filters_trashed_via_query():
    """v18.155：Drive v3 query 帶 `trashed=false` → 已刪除 sheets 不會出現。"""
    client = MagicMock()
    client.http_client.request.return_value = _mock_drive_v3_response([
        {"id": "Live", "name": "Active sheet"},
    ])
    list_user_sheets(client)
    # 檢查呼叫時 q 參數有 trashed=false
    _call_args = client.http_client.request.call_args
    q_param = _call_args.kwargs["params"]["q"]
    assert "trashed=false" in q_param
    assert 'mimeType="application/vnd.google-apps.spreadsheet"' in q_param


def test_list_user_sheets_folder_id_adds_parents_filter():
    """v18.155：folder_id 非空 → q 帶 `'FOLDER_ID' in parents`。"""
    client = MagicMock()
    client.http_client.request.return_value = _mock_drive_v3_response([])
    list_user_sheets(client, folder_id="MY_FOLDER")
    _call_args = client.http_client.request.call_args
    q_param = _call_args.kwargs["params"]["q"]
    assert '"MY_FOLDER" in parents' in q_param


def test_create_dashboard_sheet_raises_when_id_missing():
    fake_sh = MagicMock()
    fake_sh.id = ""   # gspread 回傳異常情境
    fake_sh.url = ""
    client = MagicMock()
    client.create.return_value = fake_sh
    with pytest.raises(PolicySheetError, match="未取得 ID"):
        create_dashboard_sheet(client, "x")


# ══════════════════════════════════════════════════════════════════════
# v18.149 Schema v2 — snapshot-only 11 欄 + 多幣別現金 + migration safety
# ══════════════════════════════════════════════════════════════════════
def test_v2_schema_has_12_cols_in_canonical_order():
    """v18.153：ALL_COLS_V2 是 12 欄、加入 avg_nav_with_div（含息成本）。"""
    assert ALL_COLS_V2 == (
        "policy_id", "item_type", "fund_code", "fund_name",
        "units", "avg_nav", "avg_nav_with_div", "avg_fx", "currency",
        "tier", "amount", "invest_twd",
    )
    assert ITEM_TYPE_FUND == "fund"
    assert ITEM_TYPE_CASH == "cash"


def test_v2_user_input_vs_auto_cols_disjoint_and_complete():
    """v18.153：USER_INPUT_COLS + AUTO_COLS 應該覆蓋全 12 欄、互不重疊。"""
    from repositories.policy_repository import USER_INPUT_COLS, AUTO_COLS
    union = set(USER_INPUT_COLS) | set(AUTO_COLS)
    intersection = set(USER_INPUT_COLS) & set(AUTO_COLS)
    assert union == set(ALL_COLS_V2)
    assert intersection == set()


def test_v2_zh_headers_round_trip():
    """v18.153：中英文 header 雙向 mapping 應一致。"""
    from repositories.policy_repository import ZH_HEADERS_V2, EN_HEADERS_V2
    assert set(ZH_HEADERS_V2.keys()) == set(ALL_COLS_V2)
    for en, zh in ZH_HEADERS_V2.items():
        assert EN_HEADERS_V2[zh] == en


def test_compute_units_matches_official_formula():
    """v18.153：units = invest_twd / (avg_nav × avg_fx) 對應對帳單公式(4)。"""
    from repositories.policy_repository import compute_units
    # 截圖實例：avg_nav=8.67, avg_fx=32.3485, invest_twd=499509 → units≈1781.025
    u = compute_units(499509, 8.67, 32.3485)
    assert abs(u - 1781.025) < 0.5


def test_compute_units_zero_denominator_returns_zero():
    from repositories.policy_repository import compute_units
    assert compute_units(100000, 0, 30) == 0.0
    assert compute_units(100000, 10, 0) == 0.0
    assert compute_units(100000, -5, 30) == 0.0


def test_avg_nav_with_div_from_cumul_div_twd_matches_user_screenshot():
    """v18.157：對帳單 type B 反推實例（user 截圖 USDEQ6200）：
    avg_nav=8.25, avg_fx=31.0885, invest_twd=1000285, cumul_div_twd=49913
    → units=3900.05, avg_nav_with_div≈7.84
    """
    from repositories.policy_repository import (
        avg_nav_with_div_from_cumul_div_twd, compute_units,
    )
    units = compute_units(1000285, 8.25, 31.0885)
    anwd = avg_nav_with_div_from_cumul_div_twd(8.25, 31.0885, units, 49913)
    assert abs(anwd - 7.838) < 0.01


def test_avg_nav_with_div_from_cumul_div_twd_zero_cumul_returns_avg_nav():
    """無配息 → 含息成本 = avg_nav（含息 = 不含息）。"""
    from repositories.policy_repository import avg_nav_with_div_from_cumul_div_twd
    anwd = avg_nav_with_div_from_cumul_div_twd(10.0, 30.0, 100.0, 0)
    assert anwd == 10.0


def test_avg_nav_with_div_from_cumul_div_twd_safe_on_bad_inputs():
    """零分母 / 負值 → 回 0（不拋例外）。"""
    from repositories.policy_repository import avg_nav_with_div_from_cumul_div_twd
    assert avg_nav_with_div_from_cumul_div_twd(0, 30, 100, 5000) == 0.0
    assert avg_nav_with_div_from_cumul_div_twd(10, 0, 100, 5000) == 0.0
    assert avg_nav_with_div_from_cumul_div_twd(10, 30, 0, 5000) == 0.0
    # 配息超過總成本 → clamp to 0（不會回負值）
    assert avg_nav_with_div_from_cumul_div_twd(10, 30, 100, 10_000_000) == 0.0


def test_normalize_header_to_en_translates_chinese():
    from repositories.policy_repository import _normalize_header_to_en
    assert _normalize_header_to_en("保單編號") == "policy_id"
    assert _normalize_header_to_en("含息單位成本") == "含息單位成本"  # 認不出回原值
    assert _normalize_header_to_en("policy_id") == "policy_id"


def test_is_v2_worksheet_detects_item_type_header():
    """header 含 item_type → v2；否則 → v1。"""
    ws_v2 = MagicMock()
    ws_v2.row_values.return_value = list(ALL_COLS_V2)
    assert is_v2_worksheet(ws_v2) is True

    ws_v1 = MagicMock()
    ws_v1.row_values.return_value = ["policy_id", "policy_name", "fund_url",
                                      "invest_twd", "fx_at_buy"]
    assert is_v2_worksheet(ws_v1) is False


def test_is_v2_worksheet_handles_empty_or_error():
    """空 header / row_values 拋例外 → 安全回 False。"""
    ws_empty = MagicMock()
    ws_empty.row_values.return_value = []
    assert is_v2_worksheet(ws_empty) is False

    ws_err = MagicMock()
    ws_err.row_values.side_effect = Exception("API down")
    assert is_v2_worksheet(ws_err) is False


def test_detect_sheet_schema_version_empty_returns_empty():
    """沒有保單分頁（只有 _T7_State / Policies / _Ledgers）→ 'empty'。"""
    sh = MagicMock()
    ws_sys = MagicMock(); ws_sys.title = "_T7_State"
    ws_def = MagicMock(); ws_def.title = "Policies"
    sh.worksheets.return_value = [ws_sys, ws_def]
    client = MagicMock(); client.open_by_key.return_value = sh
    assert detect_sheet_schema_version(client, "any-id") == "empty"


def test_detect_sheet_schema_version_returns_v2_if_any_tab_is_v2():
    """至少一張保單分頁是 v2 → 整本算 'v2'（為混合 sheet 留遷移空間）。"""
    sh = MagicMock()
    ws_v1 = MagicMock(); ws_v1.title = "policy-A"
    ws_v1.row_values.return_value = ["policy_id", "policy_name", "fund_url"]
    ws_v2 = MagicMock(); ws_v2.title = "policy-B"
    ws_v2.row_values.return_value = list(ALL_COLS_V2)
    sh.worksheets.return_value = [ws_v1, ws_v2]
    client = MagicMock(); client.open_by_key.return_value = sh
    assert detect_sheet_schema_version(client, "any-id") == "v2"


def test_detect_sheet_schema_version_returns_v1_if_no_v2():
    """全部保單分頁都還是 v1 → 'v1'（需要升級）。"""
    sh = MagicMock()
    ws_v1a = MagicMock(); ws_v1a.title = "policy-A"
    ws_v1a.row_values.return_value = ["policy_id", "policy_name", "fund_url"]
    ws_v1b = MagicMock(); ws_v1b.title = "policy-B"
    ws_v1b.row_values.return_value = ["policy_id", "policy_name", "fund_url"]
    sh.worksheets.return_value = [ws_v1a, ws_v1b]
    client = MagicMock(); client.open_by_key.return_value = sh
    assert detect_sheet_schema_version(client, "any-id") == "v1"


def test_load_policy_v2_returns_empty_df_when_ws_missing():
    """ws 不存在 → 回 11 欄空 df，不丟例外。"""
    sh = MagicMock()
    sh.worksheet.side_effect = Exception("WorksheetNotFound")
    client = MagicMock(); client.open_by_key.return_value = sh
    df = load_policy_v2(client, "sid", "policy-A")
    assert df.empty
    assert list(df.columns) == list(ALL_COLS_V2)


def test_load_policy_v2_returns_empty_when_v1_schema():
    """ws 存在但是 v1 schema → 回空 df（避免誤讀 v1 為 v2）。"""
    ws = MagicMock()
    ws.row_values.return_value = ["policy_id", "policy_name", "fund_url"]
    ws.get_all_records.return_value = [{"policy_id": "p1", "fund_url": "X"}]
    sh = MagicMock(); sh.worksheet.return_value = ws
    client = MagicMock(); client.open_by_key.return_value = sh
    df = load_policy_v2(client, "sid", "policy-A")
    assert df.empty


def test_load_policy_v2_normalizes_numeric_fields():
    """v2 worksheet (英文 header) → units/avg_nav/avg_fx/amount/invest_twd 都正規化。"""
    ws = MagicMock()
    ws.row_values.return_value = list(ALL_COLS_V2)
    ws.get_all_records.return_value = [
        {"policy_id": "p1", "item_type": "fund", "fund_code": "FIDXEQI",
         "fund_name": "富達世界", "units": "1234.5", "avg_nav": "12.345",
         "avg_nav_with_div": "10.1", "avg_fx": "31.2", "currency": "USD",
         "tier": "core", "amount": "", "invest_twd": "475,000"},
        {"policy_id": "p1", "item_type": "cash", "fund_code": "",
         "fund_name": "", "units": "", "avg_nav": "", "avg_nav_with_div": "",
         "avg_fx": "", "currency": "TWD", "tier": "", "amount": "500000",
         "invest_twd": ""},
    ]
    sh = MagicMock(); sh.worksheet.return_value = ws
    client = MagicMock(); client.open_by_key.return_value = sh
    df = load_policy_v2(client, "sid", "p1")
    assert len(df) == 2
    assert df.iloc[0]["units"] == 1234.5
    assert df.iloc[0]["avg_nav"] == 12.345
    assert df.iloc[0]["avg_nav_with_div"] == 10.1
    assert df.iloc[0]["invest_twd"] == 475000
    assert df.iloc[1]["item_type"] == "cash"
    assert df.iloc[1]["amount"] == 500000.0


def test_load_policy_v2_reads_chinese_headers():
    """v18.153：worksheet 用中文 header 也要讀得進來、欄位名翻譯回英文。"""
    from repositories.policy_repository import ZH_HEADERS_V2
    ws = MagicMock()
    ws.row_values.return_value = [ZH_HEADERS_V2[c] for c in ALL_COLS_V2]
    # get_all_records 用中文 key
    ws.get_all_records.return_value = [{
        ZH_HEADERS_V2["policy_id"]: "p1",
        ZH_HEADERS_V2["item_type"]: "fund",
        ZH_HEADERS_V2["fund_code"]: "FIDXEQI",
        ZH_HEADERS_V2["fund_name"]: "富達",
        ZH_HEADERS_V2["units"]: "1781",
        ZH_HEADERS_V2["avg_nav"]: "8.67",
        ZH_HEADERS_V2["avg_nav_with_div"]: "6.97",
        ZH_HEADERS_V2["avg_fx"]: "32.35",
        ZH_HEADERS_V2["currency"]: "USD",
        ZH_HEADERS_V2["tier"]: "core",
        ZH_HEADERS_V2["amount"]: "",
        ZH_HEADERS_V2["invest_twd"]: "499509",
    }]
    sh = MagicMock(); sh.worksheet.return_value = ws
    client = MagicMock(); client.open_by_key.return_value = sh
    df = load_policy_v2(client, "sid", "p1")
    # df 欄位名應該被翻成英文
    assert list(df.columns) == list(ALL_COLS_V2)
    assert df.iloc[0]["policy_id"] == "p1"
    assert df.iloc[0]["avg_nav_with_div"] == 6.97
    assert df.iloc[0]["invest_twd"] == 499509


def test_is_v2_worksheet_detects_zh_header():
    """v18.153：含「類型」中文 header 也視為 v2。"""
    from repositories.policy_repository import is_v2_worksheet, ZH_HEADERS_V2
    ws = MagicMock()
    ws.row_values.return_value = [ZH_HEADERS_V2[c] for c in ALL_COLS_V2]
    assert is_v2_worksheet(ws) is True


def test_write_policy_v2_writes_zh_header_plus_rows_only_v2_cols():
    """v18.153：整 tab 覆寫 — header 列為 ZH 翻譯；fund + cash 各 1 列。"""
    from repositories.policy_repository import ZH_HEADERS_V2
    ws = MagicMock()
    sh = MagicMock(); sh.worksheet.return_value = ws
    client = MagicMock(); client.open_by_key.return_value = sh

    import pandas as pd
    df = pd.DataFrame([
        {"policy_id": "p1", "item_type": ITEM_TYPE_FUND, "fund_code": "FIDXEQI",
         "fund_name": "富達世界", "units": 1234.5, "avg_nav": 12.345,
         "avg_nav_with_div": 10.1, "avg_fx": 31.2, "currency": "USD",
         "tier": "core", "amount": "", "invest_twd": 475000,
         "extra_garbage": "ignore me"},
        {"policy_id": "p1", "item_type": ITEM_TYPE_CASH, "currency": "TWD",
         "amount": 500000},
    ])
    n = write_policy_v2(client, "sid", "p1", df)
    assert n == 2
    ws.clear.assert_called_once()
    ws.update.assert_called_once()
    _addr, payload = ws.update.call_args.args
    assert _addr == "A1"
    # header 是中文（雙向翻譯層）
    assert payload[0] == [ZH_HEADERS_V2[c] for c in ALL_COLS_V2]
    # 兩列：fund + cash
    assert len(payload) == 3
    # extra_garbage 被丟掉
    assert "ignore me" not in str(payload)


def test_write_policy_v2_drops_fully_empty_rows():
    """整列空白 row 應該被剔除。"""
    ws = MagicMock()
    sh = MagicMock(); sh.worksheet.return_value = ws
    client = MagicMock(); client.open_by_key.return_value = sh

    import pandas as pd
    df = pd.DataFrame([
        {"policy_id": "p1", "item_type": ITEM_TYPE_FUND, "fund_code": "X"},
        {"policy_id": "", "item_type": "", "fund_code": ""},
        {"policy_id": "p1", "item_type": ITEM_TYPE_CASH, "currency": "TWD",
         "amount": 100},
    ])
    n = write_policy_v2(client, "sid", "p1", df)
    assert n == 2   # 空 row 被剔除


def test_write_policy_v2_creates_ws_if_missing():
    """ws 不存在 → 自動 add_worksheet。"""
    sh = MagicMock()
    sh.worksheet.side_effect = Exception("WorksheetNotFound")
    new_ws = MagicMock()
    sh.add_worksheet.return_value = new_ws
    client = MagicMock(); client.open_by_key.return_value = sh

    import pandas as pd
    df = pd.DataFrame([{"policy_id": "p1", "item_type": ITEM_TYPE_FUND,
                        "fund_code": "X"}])
    write_policy_v2(client, "sid", "p1", df)
    sh.add_worksheet.assert_called_once()
    new_ws.update.assert_called_once()


def test_load_all_policies_v2_concats_only_v2_tabs():
    """混合 sheet（v1 + v2）→ load_all_policies_v2 只回 v2 內容。"""
    ws_v1 = MagicMock(); ws_v1.title = "policy-v1"
    ws_v1.row_values.return_value = ["policy_id", "policy_name"]
    ws_v2 = MagicMock(); ws_v2.title = "policy-v2"
    ws_v2.row_values.return_value = list(ALL_COLS_V2)
    ws_v2.get_all_records.return_value = [
        {"policy_id": "p2", "item_type": "fund", "fund_code": "F1",
         "fund_name": "f1", "units": 100, "avg_nav": 10, "avg_fx": 30,
         "currency": "USD", "tier": "core", "amount": "", "invest_twd": 30000},
    ]
    ws_sys = MagicMock(); ws_sys.title = "_T7_State"
    sh = MagicMock(); sh.worksheets.return_value = [ws_v1, ws_v2, ws_sys]
    client = MagicMock(); client.open_by_key.return_value = sh

    df = load_all_policies_v2(client, "sid")
    assert len(df) == 1
    assert df.iloc[0]["policy_id"] == "p2"


def test_copy_sheet_as_backup_succeeds():
    """copy_sheet_as_backup → 回傳新 sheet_id + url。"""
    new_sh = MagicMock(); new_sh.id = "BACKUP_ID_X"
    new_sh.url = "https://docs.google.com/spreadsheets/d/BACKUP_ID_X/edit"
    client = MagicMock()
    client.copy.return_value = new_sh

    src_sh = MagicMock(); src_sh.title = "Fund Dashboard - 本人"
    client.open_by_key.return_value = src_sh

    bid, burl = copy_sheet_as_backup(client, "SRC_ID")
    assert bid == "BACKUP_ID_X"
    assert "BACKUP_ID_X" in burl
    client.copy.assert_called_once()
    # title 含原檔名 + suffix
    _kwargs = client.copy.call_args.kwargs
    assert "本人" in _kwargs["title"]
    assert "backup" in _kwargs["title"]
    assert _kwargs["copy_permissions"] is False


def test_copy_sheet_as_backup_raises_on_failure():
    client = MagicMock()
    client.copy.side_effect = Exception("Drive API error")
    src_sh = MagicMock(); src_sh.title = "x"
    client.open_by_key.return_value = src_sh

    with pytest.raises(PolicySheetError, match="備份 Sheet 失敗"):
        copy_sheet_as_backup(client, "any-id")


# ══════════════════════════════════════════════════════════════════════
# v18.152 — Quota 429 退避重試
# ══════════════════════════════════════════════════════════════════════
def test_is_quota_error_detects_common_signatures():
    from repositories.policy_repository import _is_quota_error
    assert _is_quota_error(Exception("APIError: [429]: Quota exceeded"))
    assert _is_quota_error(Exception("RATE_LIMIT_EXCEEDED"))
    assert _is_quota_error(Exception("RESOURCE_EXHAUSTED"))
    assert not _is_quota_error(Exception("404 not found"))
    assert not _is_quota_error(Exception("permission denied"))


def test_with_quota_retry_eventually_succeeds(monkeypatch):
    """429 失敗兩次後第三次成功 → 回 result，不拋。"""
    import repositories.policy_repository as _pr
    # 避開實際 sleep
    monkeypatch.setattr("time.sleep", lambda *_a, **_k: None)

    calls = {"n": 0}
    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise Exception("APIError: [429] Quota exceeded")
        return "OK"
    assert _pr._with_quota_retry(flaky) == "OK"
    assert calls["n"] == 3


def test_with_quota_retry_non_quota_error_raised_immediately(monkeypatch):
    """非 429 錯誤 → 不重試，立刻 raise。"""
    import repositories.policy_repository as _pr
    monkeypatch.setattr("time.sleep", lambda *_a, **_k: None)

    calls = {"n": 0}
    def boom():
        calls["n"] += 1
        raise ValueError("not quota")
    with pytest.raises(ValueError, match="not quota"):
        _pr._with_quota_retry(boom)
    assert calls["n"] == 1   # 沒重試


def test_with_quota_retry_persistent_429_eventually_raises(monkeypatch):
    """連續 4 次都 429 → 最後一次拋出。"""
    import repositories.policy_repository as _pr
    monkeypatch.setattr("time.sleep", lambda *_a, **_k: None)

    calls = {"n": 0}
    def always_quota():
        calls["n"] += 1
        raise Exception("429 Quota exceeded")
    with pytest.raises(Exception, match="Quota exceeded"):
        _pr._with_quota_retry(always_quota)
    assert calls["n"] == 4   # 4 次都試過
