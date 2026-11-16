# -*- coding: utf-8 -*-
"""💼 我的資產頁 A50 的 `holding_id` 身份鍵（DEC-2026-11-16-01 要點 2）：adapter 驗證、與 `ui_v2/hld/logic.py::_check_holding_ids` 的差異測試。

規則：必填、非空字串、無前後空白（不 strip）、同一批內唯一；缺／空／非字串／前後空白／重複 → ValueError，不靜默修正、不生成、不以 fund_code 取代，
錯誤訊息不外洩資料值。`holding_id` 只作身份鍵：不上畫面、不進 DOM（renderer 測試另鎖）。

差異測試需要 ui_v2（import 它會連帶載入 L2），所以放在獨立檔；匯入不到就整檔跳過，不假綠。輸入一律 FAKE。
"""
from __future__ import annotations

import re

import pytest

import assets_page_support as S
from ui_v3.adapters import assets_page as adapter
from ui_v3.viewmodels import assets_page as vm


def v2():
    """只有差異測試需要 ui_v2；匯入不到就只 skip 那幾個測試，不連累其他（洩漏、row_fields、順序、多保單）。"""
    return pytest.importorskip("ui_v2.hld.logic", reason="本環境匯入不到 ui_v2（差異測試需要它）")


def build(holdings, **kw):
    return adapter.build_assets_page(S.fake_result(evidence=S.fake_evidence(holdings=holdings)), **kw)


def _h(n, **over):
    return S.fake_holding(n, **over)


def _without_key(n):
    row = _h(n)
    del row["holding_id"]
    return row


# 每個案例：(名稱, 持倉列清單)。接受／拒絕必須與 ui_v2 `_check_holding_ids` 一致。
CASES = [
    ("valid_unique", [_h(1), _h(2), _h(3)], True),
    ("empty_list", [], True),
    ("single", [_h(1)], True),
    ("same_fund_code_different_ids", [_h(1, fund_code="FK0001"), _h(2, fund_code="FK0001")], True),
    ("inner_space_ok", [_h(1, holding_id="a b|c")], True),
    ("case_differs_ok", [_h(1, holding_id="Ab"), _h(2, holding_id="aB")], True),
    ("missing_key", [_h(1), _without_key(2)], False),
    ("none", [_h(1, holding_id=None)], False),
    ("empty_string", [_h(1, holding_id="")], False),
    ("only_spaces", [_h(1, holding_id="   ")], False),
    ("leading_space", [_h(1, holding_id=" x")], False),
    ("trailing_space", [_h(1, holding_id="x ")], False),
    ("tab_padded", [_h(1, holding_id="\tx")], False),
    ("newline_padded", [_h(1, holding_id="x\n")], False),
    ("nbsp_padded", [_h(1, holding_id=" x")], False),
    ("int", [_h(1, holding_id=1)], False),
    ("zero_int", [_h(1, holding_id=0)], False),
    ("float", [_h(1, holding_id=1.5)], False),
    ("bool", [_h(1, holding_id=True)], False),
    ("bytes", [_h(1, holding_id=b"id")], False),
    ("list", [_h(1, holding_id=["a"])], False),
    ("duplicate", [_h(1, holding_id="dup"), _h(2, holding_id="dup")], False),
    ("duplicate_far_apart", [_h(1, holding_id="dup"), _h(2), _h(3), _h(4, holding_id="dup")], False),
    ("duplicate_and_padded", [_h(1, holding_id="dup"), _h(2, holding_id="dup ")], False),
    ("fund_code_not_a_substitute", [_h(1, holding_id=None, fund_code="FK0001")], False),
]


def _accepts_v2(holdings) -> bool:
    try:
        v2()._check_holding_ids(holdings)
    except ValueError:
        return False
    return True


def _accepts_v3(holdings) -> bool:
    try:
        build(holdings)
    except ValueError as exc:
        # 確認拒絕是 holding_id 規則造成，不是別的驗證
        assert "holding_id" in str(exc) or re.search(r"第 \d+ 列", str(exc)), str(exc)
        return False
    return True


@pytest.mark.parametrize("name,holdings,expected", CASES, ids=[c[0] for c in CASES])
def test_ui_v3_accepts_and_rejects_exactly_like_ui_v2(name, holdings, expected):
    v2, v3 = _accepts_v2(holdings), _accepts_v3(holdings)
    assert v2 is expected, f"ui_v2 對 {name} 的判定與預期不同（預期表錯了）"
    assert v3 is v2, f"{name}: ui_v2={v2} ui_v3={v3}（身份鍵語意分歧）"


def test_both_sides_raise_the_value_error_family_and_the_differential_has_both_outcomes():
    assert v2().HoldingIdError.__mro__[1] is ValueError
    assert {c[2] for c in CASES} == {True, False}   # 正控：母體同時含接受與拒絕，不是單向空綠
    with pytest.raises(v2().HoldingIdError):
        v2()._check_holding_ids([_h(1, holding_id="")])
    with pytest.raises(ValueError):
        build([_h(1, holding_id="")])


def test_differential_has_teeth_mutating_the_real_validator_flips_expected_rejections(monkeypatch):
    """真變異：把 ui_v3 的單值驗證改成永遠接受，至少一個預期拒絕的案例必須轉為『v3 接受』（否則差異測試抓不到退化）。"""
    monkeypatch.setattr(vm, "check_holding_id", lambda value: value)
    def accepts_mutated(holdings):
        try:
            return _accepts_v3(holdings)
        except TypeError:   # 變異後不可雜湊的值（list）走到 set：不是被規則拒絕，不算翻轉
            return False

    flipped = [name for name, holdings, expected in CASES if not expected and accepts_mutated(holdings)]
    assert flipped   # 例如 空字串、前後空白、非字串
    # 重複仍由 A50Section 擋，所以「duplicate」類案例不在此列也合理；只要有案例翻轉即證明比較有牙齒


# ───────────────────────── adapter：身份鍵進 VM、不外洩資料值 ─────────────────────────

def test_rows_carry_the_input_holding_id_in_source_order_without_rewriting():
    ids = ["z|3", "a|1", "m|2"]
    model = build([_h(i + 1, holding_id=hid) for i, hid in enumerate(ids)])
    assert [r.holding_id for r in model.a50.rows] == ids and [r.ordinal for r in model.a50.rows] == [1, 2, 3]


def test_same_fund_code_under_two_policies_is_two_rows_with_two_keys():
    model = build(list(S.same_fund_two_policies_result()["evidence"]["holdings"]))
    assert model.a50.row_count == 2
    codes = [{f.field_code: f for f in r.facts}["fund_code"].value for r in model.a50.rows]
    assert codes == ["FK0001", "FK0001"]
    keys = [r.holding_id for r in model.a50.rows]
    assert len(set(keys)) == 2 and all(k.startswith("FAKE-POLICY-") for k in keys)


@pytest.mark.parametrize("name,holdings,expected", [c for c in CASES if not c[2]], ids=[c[0] for c in CASES if not c[2]])
def test_rejection_messages_do_not_leak_the_data_value(name, holdings, expected):
    with pytest.raises(ValueError) as exc:
        build(holdings)
    message = str(exc.value)
    for secret in ("dup", "FK0001", "FAKE-POLICY", "id"):   # 資料值（身份鍵、基金代號、保單代號）
        assert secret not in message.replace("holding_id", ""), (name, message)


@pytest.mark.parametrize("make", [
    lambda: _h(1, holding_id="LEAK  SENTINEL\t7 "),            # 前後空白
    lambda: _h(1, holding_id=" LEAK  SENTINEL\t7"),
])
def test_rejection_messages_do_not_leak_a_distinctive_value_with_inner_whitespace(make):
    with pytest.raises(ValueError) as exc:
        build([make()])
    assert "LEAK" not in str(exc.value) and "SENTINEL" not in str(exc.value)
    with pytest.raises(ValueError) as exc2:
        build([_h(1, holding_id="LEAK  SENTINEL\t7"), _h(2, holding_id="LEAK  SENTINEL\t7")])   # 重複
    assert "LEAK" not in str(exc2.value) and "SENTINEL" not in str(exc2.value)


def test_holding_id_is_never_a_displayable_row_field():
    with pytest.raises(ValueError):
        build([_h(1)], row_fields=("fund_name", "holding_id"))
    assert "holding_id" not in adapter.PROVISIONAL_ROW_FIELDS


def test_a_bad_key_on_a_row_that_would_be_dropped_still_fails_loud_on_the_normal_path():
    """證據自相矛盾（coverage=failed 卻有列）時列不展示；壞身份鍵仍 fail loud（與 ui_v2 同向），不靜默丟掉。"""
    result = S.fake_result(evidence=S.fake_evidence(holdings=[_h(1, holding_id="")], coverage="failed", coverage_codes=("holding_read_failed",),
                                                   skipped_tabs=None, omitted_rows=None))
    with pytest.raises(ValueError):
        adapter.build_assets_page(result)


def test_known_scope_difference_early_return_problem_codes_do_not_inspect_rows():
    """已登記範圍差異（`early_return_skips_row_and_coverage_validation`）：問題碼提早回傳的路徑不看列，所以不驗身份鍵；ui_v2 則一律先驗。
    這裡把差異鎖成現況（不處置），避免它被誤讀成已與 ui_v2 完全等範圍。"""
    result = S.no_active_result()
    result["evidence"]["holdings"] = [_h(1, holding_id="")]
    model = adapter.build_assets_page(result)   # 不丟例外
    assert model.a50.state == vm.A50_STATUS_ONLY and model.a50.rows == ()
    with pytest.raises(ValueError):
        v2()._check_holding_ids(result["evidence"]["holdings"])
