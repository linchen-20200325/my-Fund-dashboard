# -*- coding: utf-8 -*-
"""💼 頁 view model 契約（S-VM 切片）：區塊順序、A20 恆 4 格、Missing 永遠是 None＋原因、嚴格 int、frozen、(a)(b) 不混、
不含金額／百分比／合計／判斷字樣、A50 不固化欄位集合、入口只在有可用列時存在、首屏點數（兩種計法都鎖）、暫時字樣不冒充已核准字樣。

輸入一律 FAKE（`assets_page_support`）；不依賴 pandas／streamlit／services，可用 `--noconftest` 在輕量環境執行。
這裡直接建構 VM 物件測不變量；經 adapter 組出完整頁的測試在 `test_ui_v3_assets_page_adapter.py`。
"""
from __future__ import annotations

import dataclasses
import re

import pytest

import assets_page_support as S
from shared.ui_semantics import rules
from ui_v3.adapters import assets_page as adapter
from ui_v3.viewmodels import assets_page as vm
from ui_v3.viewmodels import preview_wording as W

A, B = vm.CATEGORY_SOURCE_DATA, vm.CATEGORY_BASIS_NOT_APPROVED


def build(name):
    return adapter.build_assets_page(S.SCENARIOS[name]())


def cause(code):
    return vm.CauseFact(vm.category_of_cause(code), code)


def missing(*codes, status="missing"):
    return vm.MissingFact(status, tuple(cause(c) for c in codes))


def cells(fact=None):
    fact = fact or missing(vm.CAUSE_BASIS_NOT_APPROVED)
    return vm.A20Summary(tuple(vm.A20Cell(c, None, fact) for c in vm.A20_CELL_CODES))


def page(*, a00=None, a50=None, entry=None, a60=None, fact=None):
    fact = fact or missing(vm.CAUSE_BASIS_NOT_APPROVED_WITH_ROWS)
    return vm.AssetsPageModel(
        a00=a00 or vm.A00Status(vm.SRC_COMPLETE, None),
        a10=vm.A10Card(fact, "set", "成本", vm.LIMIT_CODES, entry), a20=cells(fact),
        a30=vm.NoResultLine("A30", fact), a40=vm.NoResultLine("A40", fact),
        a50=a50 or vm.A50Section(vm.A50_STATUS_ONLY), a52=vm.A52Section(tuple(vm.SettingState(c, "set") for c in vm.SETTING_CODES)),
        a60=a60 or vm.A60Evidence(0, 0, (), ()))


def one_row(n=1, **facts):
    return vm.HoldingRow(n, tuple(vm.RowFact(code, vm.ROW_STATE_PRESENT, value, None) for code, value in (facts or {"fund_name": "FAKE"}).items()))


# ───────────────────────── 區塊順序、A20 恆 4 格 ─────────────────────────

def test_block_order_is_a00_to_a60_for_every_scenario():
    assert vm.BLOCK_ORDER == ("A00", "A10", "A20", "A30", "A40", "A50", "A52", "A60")
    for name in S.SCENARIOS:
        model = build(name)
        assert tuple(code for code, _ in model.blocks()) == vm.BLOCK_ORDER, name
        assert tuple(type(block).__name__ for _, block in model.blocks()) == (
            "A00Status", "A10Card", "A20Summary", "NoResultLine", "NoResultLine", "A50Section", "A52Section", "A60Evidence")


def test_a20_is_always_exactly_four_cells_in_fixed_order():
    assert vm.A20_CELL_CODES == ("a20_cell_1", "a20_cell_2", "a20_cell_3", "a20_cell_4")
    for name in S.SCENARIOS:
        assert tuple(c.cell_code for c in build(name).a20.cells) == vm.A20_CELL_CODES, name
    cell = vm.A20Cell("a20_cell_1", None, missing(vm.CAUSE_BASIS_NOT_APPROVED))
    for bad in ((), (cell,), (cell,) * 3, (cell,) * 5, tuple(reversed([vm.A20Cell(c, None, cell.missing) for c in vm.A20_CELL_CODES]))):
        with pytest.raises(ValueError):
            vm.A20Summary(bad)
    with pytest.raises(ValueError):
        vm.A20Cell("a20_cell_5", None, cell.missing)


def test_a20_cell_codes_are_position_codes_not_financial_nouns():
    for code in vm.A20_CELL_CODES:
        assert re.fullmatch(r"a20_cell_[1-4]", code)


# ───────────────────────── Missing ≠ 0 ─────────────────────────

@pytest.mark.parametrize("bad", [0, 0.0, 1, 1.5, -1, True, float("nan")])
def test_a20_value_must_be_none_formula_gate_closed(bad):
    assert vm.A20_VALUES_ENABLED is False
    with pytest.raises(ValueError):
        vm.A20Cell("a20_cell_1", bad, missing(vm.CAUSE_BASIS_NOT_APPROVED))


def test_a20_gate_constant_is_the_only_thing_standing_between_a_cell_and_a_number(monkeypatch):
    """負控：關卡打開（只在本測試記憶體內）後，仍拒絕 bool／NaN／inf——證明 None 規則不是只靠常數。"""
    monkeypatch.setattr(vm, "A20_VALUES_ENABLED", True)
    assert vm.A20Cell("a20_cell_1", 1.5, missing(vm.CAUSE_BASIS_NOT_APPROVED)).value == 1.5
    for bad in (True, float("nan"), float("inf"), "1"):
        with pytest.raises(ValueError):
            vm.A20Cell("a20_cell_1", bad, missing(vm.CAUSE_BASIS_NOT_APPROVED))


def test_missing_is_none_never_zero_anywhere_in_any_scenario():
    for name in S.SCENARIOS:
        model = build(name)
        assert all(c.value is None for c in model.a20.cells), name
        for row in model.a50.rows:
            for fact in row.facts:
                if fact.state == vm.ROW_STATE_MISSING:
                    assert fact.value is None and fact.missing is not None, (name, fact)
                else:
                    assert fact.value is not None and fact.missing is None


def test_row_fact_missing_cannot_carry_zero_or_empty_string():
    m = missing(vm.CAUSE_FIELD_NOT_PROVIDED)
    for bad in (0, 0.0, "", " ", "0"):
        with pytest.raises(ValueError):
            vm.RowFact("fund_name", vm.ROW_STATE_MISSING, bad, m)
    with pytest.raises(ValueError):
        vm.RowFact("fund_name", vm.ROW_STATE_MISSING, None, None)          # missing 必須帶原因
    for bad in (None, True, "", float("nan"), float("inf"), [1], {"non_finite": "nan"}):
        with pytest.raises(ValueError):
            vm.RowFact("fund_name", vm.ROW_STATE_PRESENT, bad, None)
    with pytest.raises(ValueError):
        vm.RowFact("fund_name", vm.ROW_STATE_PRESENT, "x", m)              # present 不得帶 missing
    assert vm.RowFact("units_shares", vm.ROW_STATE_PRESENT, 0, None).value == 0   # 真的 0 是事實，可以存在（與缺值不同）


# ───────────────────────── 嚴格 int ─────────────────────────

class _FakeNumpyInt:
    """像 numpy 整數、但不是 int 子類的物件（拒絕：嚴格 int 只收 Python int）。"""

    def __index__(self):
        return 3

    def __int__(self):
        return 3


@pytest.mark.parametrize("bad", [True, False, 1.0, 2.5, "1", -1, _FakeNumpyInt()])
def test_a60_counts_reject_non_int(bad):
    for name in ("skipped_tab_count", "skipped_row_count"):
        with pytest.raises(ValueError):
            vm.A60Evidence(**{"skipped_tab_count": 0, "skipped_row_count": 0, "problem_codes": (), "causes": (), name: bad})


def test_a60_counts_accept_zero_and_none_and_none_is_not_zero():
    unknown = vm.A60Evidence(None, None, (), ())
    zero = vm.A60Evidence(0, 0, (), ())
    assert unknown.skipped_tab_count is None and zero.skipped_tab_count == 0 and unknown != zero


@pytest.mark.parametrize("bad", [0, -1, True, 1.0, "1", None])
def test_row_ordinal_is_a_strict_positive_int(bad):
    with pytest.raises(ValueError):
        vm.HoldingRow(bad, (one_row().facts[0],))


def test_first_screen_count_is_a_strict_int():
    for name in S.SCENARIOS:
        for policy in (vm.POLICY_A10_TEXT_EXCLUDED, vm.POLICY_A10_TEXT_INCLUDED):
            n = vm.first_screen_element_count(build(name), policy)
            assert type(n) is int and n >= 0


# ───────────────────────── frozen ─────────────────────────

def test_view_models_are_frozen():
    model = build("complete")
    for obj, attr in ((model, "a00"), (model.a00, "source_state"), (model.a10, "entry"), (model.a20.cells[0], "value"),
                      (model.a50, "state"), (model.a60, "skipped_tab_count"), (model.a10.missing.causes[0], "category")):
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(obj, attr, None)
    assert isinstance(model.a50.rows, tuple) and isinstance(model.a20.cells, tuple)


def test_view_models_are_deterministic_and_comparable():
    assert build("partial") == build("partial") and build("partial") != build("complete")


# ───────────────────────── (a)(b) 不混 ─────────────────────────

def test_cause_categories_are_two_distinct_codes_and_every_cause_key_has_exactly_one():
    assert vm.CAUSE_CATEGORIES == (A, B) and A != B
    assert {vm.category_of_cause(c) for c in vm.CAUSE_KEYS} == {A, B}
    assert vm.category_of_cause(vm.CAUSE_PARTIAL_SOURCE) == A and vm.category_of_cause(vm.CAUSE_BASIS_NOT_APPROVED) == B


def test_cause_fact_cannot_masquerade_as_the_other_category():
    for code in vm.CAUSE_KEYS:
        other = B if vm.category_of_cause(code) == A else A
        with pytest.raises(ValueError):
            vm.CauseFact(other, code)
    with pytest.raises(ValueError):
        vm.CauseFact(A, "some_new_cause")


def test_missing_fact_keeps_a_and_b_as_separate_ordered_facts_and_b_only_with_the_approved_missing_word():
    both = missing(vm.CAUSE_PARTIAL_SOURCE, vm.CAUSE_BASIS_NOT_APPROVED_WITH_ROWS)
    assert both.categories == (A, B) and len(both.causes) == 2
    with pytest.raises(ValueError):   # (b) 不得排在 (a) 前面
        missing(vm.CAUSE_BASIS_NOT_APPROVED_WITH_ROWS, vm.CAUSE_PARTIAL_SOURCE)
    with pytest.raises(ValueError):   # 不得重複
        missing(vm.CAUSE_PARTIAL_SOURCE, vm.CAUSE_PARTIAL_SOURCE)
    with pytest.raises(ValueError):   # 沒有原因
        vm.MissingFact("missing", ())
    for status in ("undetermined", "fetch_failed"):   # (b) 只搭 `◇ 資料未備`
        with pytest.raises(ValueError):
            missing(vm.CAUSE_BASIS_NOT_APPROVED, status=status)
        assert missing(vm.CAUSE_SAME_AS_SOURCE_STATUS, status=status).status_key == status   # (a) 可搭其他已核准字樣
    with pytest.raises(ValueError):   # 未核准的狀態鍵一律拒絕（本層不新增狀態詞）
        missing(vm.CAUSE_PARTIAL_SOURCE, status="all_good")
    with pytest.raises(ValueError):
        missing(vm.CAUSE_PARTIAL_SOURCE, status="ok")   # 規則表有 ok，但 ok 不是本層可引用的缺值字樣


def test_partial_scenario_carries_both_categories_on_every_missing_surface():
    model = build("partial")
    for fact in (model.a10.missing, model.a30.missing, model.a40.missing, *(c.missing for c in model.a20.cells)):
        assert fact.categories == (A, B)


def test_a60_may_only_carry_category_a():
    with pytest.raises(ValueError):
        vm.A60Evidence(0, 0, (), (cause(vm.CAUSE_BASIS_NOT_APPROVED),))
    assert vm.A60Evidence(0, 0, (), (cause(vm.CAUSE_PARTIAL_SOURCE),)).causes
    for name in S.SCENARIOS:
        assert all(r.category == A for r in build(name).a60.causes), name


# ───────────────────────── 不含金額／百分比／合計／判斷 ─────────────────────────

_FORBIDDEN_FIELD_TOKENS = ("total", "subtotal", "sum", "percent", "pct", "ratio", "share", "weight", "value_twd", "amount",
                           "return", "pnl", "profit", "loss", "health", "safe", "stale", "normal", "grade", "score", "rank", "top")
_FORBIDDEN_WORDS = ("金額", "百分比", "100%", "合計", "小計", "占比", "比例", "報酬", "損益", "過期", "正常", "安全", "健康", "%")


def test_no_vm_dataclass_field_can_carry_a_total_percentage_or_judgement():
    names = S.all_dataclass_field_names(vm)
    assert names, "沒有找到任何 dataclass 欄位（守衛失效）"
    hits = sorted(n for n in names for t in _FORBIDDEN_FIELD_TOKENS if t in n.lower())
    assert hits == [], hits


def test_no_vm_value_in_any_scenario_contains_a_forbidden_word_or_percent():
    for name in S.SCENARIOS:
        for leaf in S.leaf_values(build(name)):
            if isinstance(leaf, str):
                assert not [w for w in _FORBIDDEN_WORDS if w in leaf], (name, leaf)


def test_vm_module_holds_no_collection_that_enumerates_row_field_names():
    """A50 不固化欄位集合：VM 模組沒有任何含有持倉欄位名的集合常數（暫行欄位集合只住 adapter，且可由呼叫端換掉）。"""
    row_field_names = set(adapter.PROVISIONAL_ROW_FIELDS)
    holders = [n for n, v in vars(vm).items()
               if isinstance(v, (tuple, list, set, frozenset, dict)) and row_field_names & {x for x in v if isinstance(x, str)}]
    assert holders == []
    assert vm.FIELD_SET_PENDING_T6 == "pending_t6"


# ───────────────────────── A50 與入口 ─────────────────────────

def test_a50_does_not_fix_the_field_set_any_field_codes_are_accepted_and_rows_may_differ():
    row1 = one_row(1, zz_custom_one="a", zz_custom_two=3)
    row2 = one_row(2, fund_name="FAKE", another_field=1.5)
    section = vm.A50Section(vm.A50_ROWS, (row1, row2))
    assert section.row_count == 2 and section.field_set_status == vm.FIELD_SET_PENDING_T6
    with pytest.raises(ValueError):
        vm.A50Section(vm.A50_ROWS, (row1,), field_set_status="approved")


def test_a50_rows_state_needs_rows_and_status_only_has_none_and_order_is_source_order():
    with pytest.raises(ValueError):
        vm.A50Section(vm.A50_ROWS)
    with pytest.raises(ValueError):
        vm.A50Section(vm.A50_STATUS_ONLY, (one_row(),))
    with pytest.raises(ValueError):
        vm.A50Section(vm.A50_ROWS, (one_row(2), one_row(1)))        # 不重排
    with pytest.raises(ValueError):
        vm.A50Section(vm.A50_ROWS, (one_row(1), one_row(3)))        # 序號不連續（不得略列／Top N）
    with pytest.raises(ValueError):
        vm.HoldingRow(1, (vm.RowFact("a", vm.ROW_STATE_PRESENT, "x", None), vm.RowFact("a", vm.ROW_STATE_PRESENT, "y", None)))
    with pytest.raises(ValueError):
        vm.HoldingRow(1, ())


def test_entry_is_a_provisional_candidate_and_carries_no_number():
    entry = vm.PositionEntry()
    assert entry.provisional is True and entry.target_block == "A50"
    assert not S.numeric_leaves(entry)
    for kwargs in ({"provisional": False}, {"provisional": 1}, {"target_block": "A60"}):
        with pytest.raises(ValueError):
            vm.PositionEntry(**kwargs)


def test_entry_exists_only_when_a50_has_rows():
    section = vm.A50Section(vm.A50_ROWS, (one_row(),))
    assert page(a50=section, entry=vm.PositionEntry()).a10.entry is not None
    with pytest.raises(ValueError):    # 沒有可用列卻有入口＝導向空內容
        page(a50=vm.A50Section(vm.A50_STATUS_ONLY), entry=vm.PositionEntry())
    # 有列但沒入口是允許的建構（入口存在條件由 adapter 的暫行候選函式決定，並由 adapter 測試鎖）
    assert page(a50=section, entry=None).a10.entry is None


@pytest.mark.parametrize("state", [vm.SRC_NOT_SELECTED, vm.SRC_READ_FAILED, vm.SRC_COMPLETE_NO_ROWS, vm.SRC_NOT_READ])
def test_no_rows_source_states_can_never_have_rows_or_an_entry(state):
    a00 = vm.A00Status(state, vm.a00_status_key_of(state), failure_code=None,
                       cause_key="market_basis_assembly_not_available_in_preview" if state == vm.SRC_NOT_READ else None)
    section = vm.A50Section(vm.A50_ROWS, (one_row(),))
    with pytest.raises(ValueError):
        page(a00=a00, a50=section)
    assert page(a00=a00).a50.state == vm.A50_STATUS_ONLY


# ───────────────────────── A00 ─────────────────────────

def test_a00_status_key_follows_the_state_and_only_uses_approved_keys():
    assert {s: vm.a00_status_key_of(s) for s in vm.SOURCE_STATES} == {
        "complete": None, "partial": None, "not_selected": None, "complete_no_rows": None,
        "read_failed": "fetch_failed", "undetermined": "undetermined", "not_read": "undetermined"}
    for state in vm.SOURCE_STATES:
        key = vm.a00_status_key_of(state)
        assert key is None or (key in vm.APPROVED_STATUS_KEYS and key in rules.ENTRIES)
    with pytest.raises(ValueError):
        vm.A00Status(vm.SRC_COMPLETE, "missing")             # 不得亂掛狀態字樣
    with pytest.raises(ValueError):
        vm.A00Status(vm.SRC_READ_FAILED, None)               # 取數失敗必須引用已核准的 ⛔ 取數失敗
    with pytest.raises(ValueError):
        vm.A00Status("looks_fine", None)
    with pytest.raises(ValueError):
        vm.A00Status(vm.SRC_COMPLETE, None, failure_code="NETWORK_ERROR")   # failure_code 只有 read_failed 可有
    with pytest.raises(ValueError):
        vm.A00Status(vm.SRC_NOT_READ, "undetermined")        # not_read 必須帶 cause_key
    with pytest.raises(ValueError):
        vm.A00Status(vm.SRC_COMPLETE, None, cause_key="x_y")


def test_a00_read_failed_is_distinct_from_not_selected_and_from_undetermined():
    states = {build(n).a00.source_state for n in ("no_active", "read_failed", "complete_no_rows", "unknown_coverage")}
    assert states == {vm.SRC_NOT_SELECTED, vm.SRC_READ_FAILED, vm.SRC_COMPLETE_NO_ROWS, vm.SRC_UNDETERMINED}


def test_chart_claim_is_withheld_and_there_is_no_chart_field():
    assert vm.CHART_CLAIM_WITHHELD == "withheld_pending_approval"
    for name in S.SCENARIOS:
        assert build(name).chart_claim == vm.CHART_CLAIM_WITHHELD
    kwargs = {f.name: getattr(build("complete"), f.name) for f in dataclasses.fields(vm.AssetsPageModel)}
    for bad in ("comparable", "", None):
        with pytest.raises(ValueError):
            vm.AssetsPageModel(**{**kwargs, "chart_claim": bad})
    assert [n for n in S.all_dataclass_field_names(vm) if "chart" in n] == ["chart_claim"]


# ───────────────────────── 首屏元素點數（兩種計法都鎖；待 UI Review） ─────────────────────────

# (場景) → (排除 A10 入口與原因句, 包含)；固定部分＝A00 1＋A20 四格 4＝5。
_EXPECTED_COUNTS = {
    "complete": (5, 7),           # 入口 +1、原因 1 個 +1
    "partial": (5, 8),            # 入口 +1、原因 2 個（a、b）+2
    "no_active": (5, 6),          # 無入口；原因 1 個
    "read_failed": (5, 6),
    "complete_no_rows": (5, 6),
    "unknown_coverage": (5, 8),   # 有 1 列→有入口 +1；原因 2 個（a、b）
    "settings_failed": (5, 8),    # 有 1 列但來源不完整且無略過證據→undetermined：入口 +1、原因 2 個（a、b）
    "market_blocked": (5, 6),
}


def test_first_screen_count_has_no_default_policy_the_choice_is_pending_ui_review():
    model = build("complete")
    with pytest.raises(TypeError):
        vm.first_screen_element_count(model)                                  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        vm.first_screen_element_count(model, True)                            # type: ignore[arg-type]
    with pytest.raises(TypeError):
        vm.FirstScreenCountPolicy(count_a10_entry=1, count_a10_causes=False)  # type: ignore[arg-type]
    assert "待 UI Review" in vm.FirstScreenCountPolicy.__doc__


@pytest.mark.parametrize("name", list(_EXPECTED_COUNTS))
def test_first_screen_counts_under_both_policies(name):
    model = build(name)
    excluded, included = _EXPECTED_COUNTS[name]
    assert vm.first_screen_element_count(model, vm.POLICY_A10_TEXT_EXCLUDED) == excluded == 1 + len(model.a20.cells)
    assert vm.first_screen_element_count(model, vm.POLICY_A10_TEXT_INCLUDED) == included
    assert vm.first_screen_within_limit(model, vm.POLICY_A10_TEXT_EXCLUDED) is (excluded <= vm.FIRST_SCREEN_LIMIT) is True
    assert vm.first_screen_within_limit(model, vm.POLICY_A10_TEXT_INCLUDED) is (included <= vm.FIRST_SCREEN_LIMIT) is False


def test_first_screen_policy_components_are_independent():
    model = build("complete")
    only_entry = vm.FirstScreenCountPolicy(count_a10_entry=True, count_a10_causes=False)
    only_causes = vm.FirstScreenCountPolicy(count_a10_entry=False, count_a10_causes=True)
    assert vm.first_screen_element_count(model, only_entry) == 6 == vm.first_screen_element_count(model, only_causes)
    assert vm.FIRST_SCREEN_LIMIT == 5


# ───────────────────────── 字樣：已核准取規則表、暫時字樣不冒充 ─────────────────────────

_ENV_SHAPE = re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b")
_SNAKE = re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b")


def test_approved_status_keys_exist_in_the_rules_table_and_are_not_duplicated_here():
    assert set(vm.APPROVED_STATUS_KEYS) <= set(rules.ENTRIES)
    for key in vm.APPROVED_STATUS_KEYS:
        assert not rules.ENTRIES[key].is_pending, key
        assert key not in vm.ASSETS_PENDING_WORDING


def test_pending_wording_is_pending_sourced_disjoint_and_never_impersonates_an_approved_wording():
    table = vm.ASSETS_PENDING_WORDING
    assert table and set(table) & set(rules.APPROVED_WORDING) == set()
    approved = {e.wording for e in rules.ENTRIES.values() if e.wording and not e.is_pending} | {a.text for a in rules.APPROVED_WORDING.values()}
    symbols = {e.symbol for e in rules.ENTRIES.values() if e.symbol}
    for key, item in table.items():
        assert item.key == key and item.status == W.STATUS_PENDING and item.source.strip()
        assert item.text not in approved and not any(sym in item.text for sym in symbols), key
        assert not _ENV_SHAPE.search(item.text) and not _SNAKE.search(item.text), key   # 不得外漏工程資訊形的字
        assert "候選" in item.source or "衍生" in item.source, key


def test_pending_wording_texts_contain_no_forbidden_word_except_the_one_negated_82_candidate():
    """82 的限制列候選逐字含「不合計」（否定句，不是產生合計）；其餘字樣不得含任何禁用字。"""
    for key, item in vm.ASSETS_PENDING_WORDING.items():
        text = item.text.replace("不合計", "") if key == "limit_no_fx_conversion" else item.text
        assert not [w for w in _FORBIDDEN_WORDS if w in text], (key, item.text)
    assert "合計" in vm.ASSETS_PENDING_WORDING["limit_no_fx_conversion"].text


def test_every_state_without_an_approved_word_has_a_pending_candidate_and_cause_wording_exists_where_82_gives_one():
    for state in vm.SOURCE_STATES:
        if vm.a00_status_key_of(state) is None:
            assert f"a00_{state}" in vm.ASSETS_PENDING_WORDING, state
    for key in ("cause_partial_source", "cause_basis_not_approved_with_rows", "cause_basis_not_approved",
                "entry_view_holdings", "limit_no_fx_conversion"):
        assert vm.pending_wording(key).text
    with pytest.raises(KeyError):
        vm.pending_wording("missing")   # 已核准字樣不在暫時字樣表
    with pytest.raises(ValueError):
        W.PendingWording("k", "t", "s", status="approved")


def test_the_two_basis_causes_differ_in_whether_they_claim_viewable_holdings():
    """(b) 在有可用列時可以說『已有持倉資料可查看』；沒有列或沒讀取時不得聲稱有。"""
    assert "已有持倉資料可查看" in vm.pending_wording("cause_basis_not_approved_with_rows").text
    assert "已有持倉資料可查看" not in vm.pending_wording("cause_basis_not_approved").text
    assert build("complete").a10.missing.causes[-1].cause_key == vm.CAUSE_BASIS_NOT_APPROVED_WITH_ROWS
    assert build("market_blocked").a10.missing.causes[-1].cause_key == vm.CAUSE_BASIS_NOT_APPROVED
    for name in ("no_active", "read_failed", "complete_no_rows"):
        assert vm.CATEGORY_BASIS_NOT_APPROVED not in build(name).a10.missing.categories, name   # 無列時不寫 (b)，不暗示有資料可看
