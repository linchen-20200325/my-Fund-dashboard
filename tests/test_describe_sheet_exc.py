"""§1 Fail-Loud 回歸:gspread 例外訊息永不空白(2026-08-11 線上事故 v19.431)。

gspread 6.x `open_by_key` 對 403 會 `raise PermissionError`(無參數)→ str() 空 →
「列 worksheets 失敗:」後面全白,使用者零線索。`describe_sheet_exc` 一律帶型別 + 可行動指示。
"""
from __future__ import annotations

import pytest

from repositories.policy._helpers import PolicySheetError, describe_sheet_exc


# ── describe_sheet_exc 本體 ────────────────────────────────
def test_permission_error_never_blank_and_actionable():
    msg = describe_sheet_exc(PermissionError())           # str() == "" 的元凶
    assert msg.strip() != "" and "PermissionError" in msg
    assert "403" in msg and "client_email" in msg          # 可行動:分享給 SA


def test_permission_error_with_sheet_id_appends_id():
    msg = describe_sheet_exc(PermissionError(), sheet_id="1QPXAq71nJyJez1234567")
    assert "1QPXAq71nJyJ" in msg                            # 前 12 碼


def test_spreadsheet_not_found_maps_404():
    class SpreadsheetNotFound(Exception):
        pass
    msg = describe_sheet_exc(SpreadsheetNotFound())
    assert "404" in msg and msg.strip() != ""


def test_quota_error_maps_429():
    msg = describe_sheet_exc(Exception("APIError [429]: Quota exceeded"))
    assert "429" in msg


def test_generic_error_keeps_type_and_message_no_hint():
    msg = describe_sheet_exc(ValueError("boom"))
    assert "ValueError" in msg and "boom" in msg
    assert "403" not in msg and "404" not in msg           # 無誤導 hint


def test_no_orphan_colon_when_message_empty():
    # str(PermissionError()) == "" → 不可留出「PermissionError:」的孤兒冒號
    assert not describe_sheet_exc(PermissionError()).startswith("PermissionError:")


# ── v2 列 worksheets 端到端:bare PermissionError → 非空白 PolicySheetError ──
class _FakeClient403:
    def open_by_key(self, key):
        raise PermissionError()                            # 模擬 gspread 403(無參數)


def test_list_policy_worksheets_403_message_not_blank():
    from repositories.policy.v2 import list_policy_worksheets
    with pytest.raises(PolicySheetError) as e:
        list_policy_worksheets(_FakeClient403(), "1QPXAq71nJyJezABCDEFG")
    _m = str(e.value)
    assert "PermissionError" in _m and "403" in _m         # §1:不再空白,且可行動
    assert not _m.endswith("：")                            # 沒有孤兒冒號結尾


def test_load_all_policy_worksheets_403_message_not_blank():
    from repositories.policy.v2 import load_all_policy_worksheets
    with pytest.raises(PolicySheetError) as e:
        load_all_policy_worksheets(_FakeClient403(), "1QPXAq71nJyJezABCDEFG")
    assert "PermissionError" in str(e.value) and "403" in str(e.value)
