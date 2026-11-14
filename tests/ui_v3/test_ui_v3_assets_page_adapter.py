# -*- coding: utf-8 -*-
"""💼 頁 adapter 契約（S-VM 切片）：`AssetsLoadResult.to_primitive()` 形狀的 dict → `AssetsPageModel`。

涵蓋：三種來源情境（完整／部分缺漏／完全未取得 a b c）、市值基準 blocked 降級、未知狀態／缺鍵／形狀不符 fail-closed、
`categories[*].value_twd` 不外洩（存取追蹤＋哨兵值）、入口暫行候選只在有可用列時存在、輸入不被修改、import 零副作用與隔離、
暫行標示清單 `PROVISIONAL_ITEMS` 的鎖。

輸入一律 FAKE（`assets_page_support`）；全部測試不依賴 pandas／streamlit／services，可用 `--noconftest` 在輕量環境執行。

**真生產者形狀對照已延後，需另行授權**：客戶授權字面是「無 L2 import」，本批不含任何 import `services.*`（含經由
`assets_source` 或其 support 間接觸及 L2）的測試。目前 fake 形狀與真生產者的一致性為 **NOT VERIFIED**
（repo 內 `assets_source` 既有契約測試覆蓋載入端）。
"""
from __future__ import annotations

import ast
import copy
import inspect
import pathlib
import subprocess
import sys

import pytest

import assets_page_support as S
import ui_v3_guard_lib as lib
from ui_v3.adapters import assets_page as adapter
from ui_v3.viewmodels import assets_page as vm

A, B = vm.CATEGORY_SOURCE_DATA, vm.CATEGORY_BASIS_NOT_APPROVED
ROOT = pathlib.Path(__file__).resolve().parents[2]


def build(result=None, **kw):
    return adapter.build_assets_page(S.complete_result() if result is None else result, **kw)


def codes(fact):
    return tuple(r.cause_key for r in fact.causes)


# ───────────────────────── 三種來源情境 ─────────────────────────

def test_scenario_one_complete_source_has_rows_entry_and_only_category_b():
    model = build(S.complete_result(2))
    assert (model.a00.source_state, model.a00.status_key) == (vm.SRC_COMPLETE, None)
    assert model.a50.state == vm.A50_ROWS and model.a50.row_count == 2
    assert model.a10.entry == vm.PositionEntry() and model.a10.entry.provisional is True
    assert codes(model.a10.missing) == (vm.CAUSE_BASIS_NOT_APPROVED_WITH_ROWS,) and model.a10.missing.status_key == "missing"
    assert all(codes(c.missing) == codes(model.a10.missing) and c.value is None for c in model.a20.cells)
    assert (model.a60.skipped_tab_count, model.a60.skipped_row_count, model.a60.problem_codes, model.a60.causes) == (0, 0, (), ())
    assert (model.a10.basis_state, model.a10.basis_value, model.a10.limit_codes) == ("set", "成本", (vm.LIMIT_NO_FX_CONVERSION,))
    assert model.a50.field_set_status == vm.FIELD_SET_PENDING_T6


def test_scenario_two_partial_keeps_usable_rows_separates_a_and_b_and_reports_counts_as_facts():
    model = build(S.partial_result())
    assert model.a00.source_state == vm.SRC_PARTIAL and model.a00.status_key is None
    assert (model.a60.skipped_tab_count, model.a60.skipped_row_count) == (1, 2)
    assert model.a50.state == vm.A50_ROWS and model.a50.row_count == 2 and model.a10.entry is not None
    assert codes(model.a10.missing) == (vm.CAUSE_PARTIAL_SOURCE, vm.CAUSE_BASIS_NOT_APPROVED_WITH_ROWS)
    assert model.a10.missing.categories == (A, B)                       # 兩類並列、不混成一個
    assert all(c.missing == model.a10.missing for c in model.a20.cells)
    assert model.a60.causes == (vm.CauseFact(A, vm.CAUSE_PARTIAL_SOURCE),)   # A60 只承載 (a)
    facts = {f.field_code: f for f in model.a50.rows[0].facts}
    assert facts["fund_name"].state == vm.ROW_STATE_MISSING and facts["fund_name"].value is None   # 缺 fund_name：整列保留、該格缺值
    assert facts["fund_code"].state == vm.ROW_STATE_PRESENT
    second = {f.field_code: f for f in model.a50.rows[1].facts}
    assert second["units_shares"].state == vm.ROW_STATE_MISSING and second["units_shares"].missing.causes[0].cause_key == vm.CAUSE_VALUE_UNUSABLE


@pytest.mark.parametrize("name,state,status_key", [
    ("no_active", vm.SRC_NOT_SELECTED, None),
    ("read_failed", vm.SRC_READ_FAILED, "fetch_failed"),
    ("complete_no_rows", vm.SRC_COMPLETE_NO_ROWS, None),
])
def test_scenario_three_nothing_obtained_a_b_c_have_no_entry_no_rows_and_only_category_a(name, state, status_key):
    model = build(S.SCENARIOS[name]())
    assert (model.a00.source_state, model.a00.status_key) == (state, status_key)
    assert model.a10.entry is None and model.a50.state == vm.A50_STATUS_ONLY and model.a50.rows == ()
    assert codes(model.a10.missing) == (vm.CAUSE_SAME_AS_SOURCE_STATUS,) and model.a10.missing.categories == (A,)
    assert all(c.missing.categories == (A,) and c.value is None for c in model.a20.cells)   # 四格 (a) ×4，原因＝引用 A00
    assert B not in model.a30.missing.categories and B not in model.a40.missing.categories
    assert adapter.provisional_holding_entry_available(S.SCENARIOS[name]()) is False


def test_read_failed_carries_only_the_internal_failure_code_never_free_text():
    model = build(S.read_failed_result("UPSTREAM_ERROR"))
    assert model.a00.failure_code == "UPSTREAM_ERROR"
    assert build(S.no_active_result()).a00.failure_code is None
    # 失敗碼只在 read_failed 才帶；就算輸入帶了也不外溢到別的狀態
    leaked = S.no_active_result()
    leaked["holding_failure_code"] = "NETWORK_ERROR"
    assert build(leaked).a00.failure_code is None


def test_ab_are_never_merged_between_read_failure_and_unapproved_basis():
    """(a) 原始資料缺漏／取數失敗 與 (b) 計算口徑未核准是兩個不同代碼；取數失敗的頁面不得出現 (b)，完整來源的頁面不得出現 (a)。"""
    failed = build(S.read_failed_result())
    complete = build(S.complete_result())
    assert failed.a10.missing.categories == (A,) and complete.a10.missing.categories == (B,)
    assert failed.a10.missing != complete.a10.missing
    assert {r.cause_key for r in failed.a10.missing.causes}.isdisjoint({r.cause_key for r in complete.a10.missing.causes})


# ───────────────────────── 市值基準 blocked ─────────────────────────

def test_market_basis_blocked_degrades_without_fabricating_anything():
    result = S.market_blocked_result()
    model = build(result)
    assert (model.a00.source_state, model.a00.status_key, model.a00.cause_key) == (
        vm.SRC_NOT_READ, "undetermined", "market_basis_assembly_not_available_in_preview")
    assert all(c.value is None and c.missing.categories == (B,) for c in model.a20.cells)
    assert codes(model.a20.cells[0].missing) == (vm.CAUSE_BASIS_NOT_APPROVED,)   # 不聲稱「已有持倉資料可查看」
    assert model.a50.state == vm.A50_STATUS_ONLY and model.a50.rows == () and model.a10.entry is None
    assert model.chart_claim == "withheld_pending_approval"
    assert (model.a60.skipped_tab_count, model.a60.skipped_row_count) == (None, None)   # 沒讀＝不知道，不是 0
    assert model.a10.basis_state == "set" and model.a10.basis_value is None              # blocked 沒有證據，不編基準值
    assert adapter.provisional_holding_entry_available(result) is False


def test_blocked_with_evidence_or_without_cause_is_a_contract_violation():
    bad = S.market_blocked_result()
    bad["evidence"] = S.fake_evidence(holdings=[S.fake_holding(1)])
    with pytest.raises(ValueError):
        build(bad)
    for cause in (None, "", "  "):
        no_cause = S.market_blocked_result()
        no_cause["blocked_reason"] = cause
        with pytest.raises(ValueError):
            build(no_cause)


# ───────────────────────── fail-closed ─────────────────────────

def _mutated(fn):
    r = S.complete_result()
    fn(r)
    return r


_CONTRACT_VIOLATIONS = {
    "not a mapping": lambda: ["x"],
    "none": lambda: None,
    "empty": lambda: {},
    "missing status": lambda: {k: v for k, v in S.complete_result().items() if k != "status"},
    "missing evidence key": lambda: {k: v for k, v in S.complete_result().items() if k != "evidence"},
    "missing chart_claim": lambda: {k: v for k, v in S.complete_result().items() if k != "chart_claim"},
    "unknown status": lambda: _mutated(lambda r: r.update(status="ok")),
    "schema version 2": lambda: _mutated(lambda r: r.update(schema_version=2)),
    "schema version bool": lambda: _mutated(lambda r: r.update(schema_version=True)),
    "schema version float": lambda: _mutated(lambda r: r.update(schema_version=1.0)),
    "chart claim comparable": lambda: _mutated(lambda r: r.update(chart_claim="comparable")),
    "unknown problem": lambda: _mutated(lambda r: r.update(problems=["something_new"])),
    "problems not list": lambda: _mutated(lambda r: r.update(problems="no_active_source")),
    "settings status not mapping": lambda: _mutated(lambda r: r.update(settings_status=["set"])),
    "settings key missing": lambda: _mutated(lambda r: r["settings_status"].pop("alo_basis")),
    "settings unknown state": lambda: _mutated(lambda r: r["settings_status"].update(alo_basis="fine")),
    "failure code blank": lambda: _mutated(lambda r: r.update(holding_failure_code=" ")),
    "evaluated without evidence": lambda: _mutated(lambda r: r.update(evidence=None)),
    "evidence not mapping": lambda: _mutated(lambda r: r.update(evidence=[1])),
    "evidence missing source": lambda: _mutated(lambda r: r["evidence"].pop("source")),
    "evidence missing holdings": lambda: _mutated(lambda r: r["evidence"].pop("holdings")),
    "evidence missing source_coverage": lambda: _mutated(lambda r: r["evidence"].pop("source_coverage")),
    "holdings not list": lambda: _mutated(lambda r: r["evidence"].update(holdings="rows")),
    "holding row not mapping": lambda: _mutated(lambda r: r["evidence"].update(holdings=[["FAKE"]])),
    "skipped_tabs facet missing": lambda: _mutated(lambda r: r["evidence"]["source"].pop("skipped_tabs")),
    "provided facet without items list": lambda: _mutated(lambda r: r["evidence"]["source"].update(omitted_rows={"status": "provided", "items": 3})),
    "source_coverage not mapping": lambda: _mutated(lambda r: r["evidence"].update(source_coverage="complete")),
}


@pytest.mark.parametrize("name", list(_CONTRACT_VIOLATIONS))
def test_contract_violations_raise_value_error_never_a_complete_looking_page(name):
    bad = _CONTRACT_VIOLATIONS[name]()
    with pytest.raises(ValueError):
        adapter.build_assets_page(bad)
    with pytest.raises(ValueError):
        adapter.provisional_holding_entry_available(bad)


def test_extra_unknown_top_level_keys_are_ignored_not_trusted():
    result = S.complete_result()
    result["something_new"] = {"status": "all_good"}
    assert build(result) == build(S.complete_result())


@pytest.mark.parametrize("coverage", ["unknown", "something_new", "", None, 7])
def test_unknown_source_coverage_values_degrade_to_undetermined_never_complete(coverage):
    model = build(S.unknown_coverage_result(rows=1, coverage=coverage))
    assert model.a00.source_state == vm.SRC_UNDETERMINED and model.a00.status_key == "undetermined"
    assert model.a00.source_state != vm.SRC_COMPLETE
    assert model.a10.missing.categories == (A, B)      # 原始資料狀態不明（a）；有列所以口徑未核准（b）也成立


def test_undetermined_without_rows_never_claims_no_valid_rows():
    """沒有證據能證明「來源完整」時，不得寫成『沒有有效持倉列』(c)，只能是無法判定。"""
    model = build(S.unknown_coverage_result(rows=0))
    assert model.a00.source_state == vm.SRC_UNDETERMINED and model.a50.state == vm.A50_STATUS_ONLY and model.a10.entry is None
    assert model.a10.missing.categories == (A,)


def test_incomplete_without_skip_evidence_is_undetermined_not_partial():
    model = build(S.settings_failed_result())
    assert model.a00.source_state == vm.SRC_UNDETERMINED          # 設定讀取失敗造成的 incomplete，不是「部分略過」
    assert (model.a60.skipped_tab_count, model.a60.skipped_row_count) == (0, 0)
    assert model.a60.problem_codes == ("settings_read_failed",)
    assert [s.state for s in model.a52.settings] == ["read_failed"] * 4


def test_problems_take_priority_over_a_contradicting_coverage_or_rows():
    """證據自相矛盾（coverage 說完整、有列，問題碼卻說沒有 Active／讀取失敗）：以問題碼為準，不展示列、沒有入口。"""
    for problem, state in (("no_active_source", vm.SRC_NOT_SELECTED), ("holding_read_failed", vm.SRC_READ_FAILED)):
        result = S.complete_result(2)
        result["problems"] = [problem]
        model = build(result)
        assert model.a00.source_state == state and model.a50.rows == () and model.a10.entry is None
        assert adapter.provisional_holding_entry_available(result) is False


@pytest.mark.parametrize("coverage,state", [("not_selected", vm.SRC_NOT_SELECTED), ("failed", vm.SRC_READ_FAILED)])
def test_coverage_not_selected_or_failed_with_rows_drops_the_rows(coverage, state):
    result = S.complete_result(2)
    result["evidence"]["source_coverage"]["status"] = coverage
    model = build(result)
    assert model.a00.source_state == state and model.a50.state == vm.A50_STATUS_ONLY and model.a10.entry is None


def test_skip_facet_not_provided_is_none_not_zero():
    result = S.partial_result()
    result["evidence"]["source"]["omitted_rows"] = {"status": "not_provided", "items": []}
    model = build(result)
    assert (model.a60.skipped_tab_count, model.a60.skipped_row_count) == (1, None)
    result["evidence"]["source"]["omitted_rows"] = {"status": "invalid", "items": []}
    assert build(result).a60.skipped_row_count is None


# ───────────────────────── 金額不外洩 ─────────────────────────

def test_category_value_twd_is_never_read_and_never_reaches_the_vm():
    evidence = S.TrackingDict(S.complete_result(2)["evidence"])
    result = S.complete_result(2)
    result["evidence"] = evidence
    model = build(result)
    assert "categories" not in evidence.accessed and "denominator" not in evidence.accessed and "coverage" not in evidence.accessed
    assert evidence.accessed <= {"source", "holdings", "source_coverage", "settings"}, evidence.accessed
    assert evidence.iterated is False
    numbers = S.numeric_leaves(model)
    for sentinel in (S.SENTINEL_CATEGORY_VALUE, S.SENTINEL_HOLDING_VALUE, S.SENTINEL_SHARE_PCT):
        assert sentinel not in numbers, sentinel
    assert "987654321" not in repr(model) and "555555" not in repr(model) and "33.25" not in repr(model)


def test_every_scenario_vm_has_no_category_or_percentage_number_even_with_poisoned_evidence():
    for name, make in S.SCENARIOS.items():
        result = make()
        if result["evidence"] is not None:
            result["evidence"]["categories"][0]["value_twd"] = S.SENTINEL_CATEGORY_VALUE
        numbers = S.numeric_leaves(build(result))
        assert S.SENTINEL_CATEGORY_VALUE not in numbers and S.SENTINEL_SHARE_PCT not in numbers, name


@pytest.mark.parametrize("field", list(adapter.FORBIDDEN_ROW_FIELDS))
def test_row_fields_cannot_name_a_field_that_brings_amounts_or_ratios_back(field):
    with pytest.raises(ValueError):
        build(row_fields=("fund_code", field))


def test_default_row_fields_contain_no_amount_or_ratio_field_at_all():
    assert adapter.PROVISIONAL_ROW_FIELDS == ("fund_name", "fund_code", "ccy", "units_shares")
    assert not set(adapter.PROVISIONAL_ROW_FIELDS) & set(adapter.FORBIDDEN_ROW_FIELDS)
    assert {"value_twd", "cost_twd", "cost_orig_ccy", "share_of_covered_pct", "weight_ratio"} <= set(adapter.FORBIDDEN_ROW_FIELDS)


@pytest.mark.parametrize("name", list(S.SCENARIOS))
def test_fixture_rows_carrying_cost_and_value_sentinels_never_surface_on_the_default_path(name):
    """證據持倉列帶有 cost_twd／cost_orig_ccy／value_twd 哨兵值時，預設路徑下 VM 任何位置（含 repr）都不出現。"""
    result = S.SCENARIOS[name]()
    for row in (result["evidence"] or {}).get("holdings", []):
        assert row["cost_twd"] == S.SENTINEL_COST_TWD and row["value_twd"] == S.SENTINEL_HOLDING_VALUE   # fixture 確實帶著它們
    model = build(result)
    numbers = S.numeric_leaves(model)
    for sentinel in (S.SENTINEL_COST_TWD, S.SENTINEL_COST_ORIG, S.SENTINEL_HOLDING_VALUE, S.SENTINEL_CATEGORY_VALUE, S.SENTINEL_SHARE_PCT):
        assert sentinel not in numbers, (name, sentinel)
        assert str(sentinel) not in repr(model) and str(int(sentinel)) not in repr(model), (name, sentinel)
    assert "cost_twd" not in repr(model) and "value_twd" not in repr(model)


# ───────────────────────── 入口：暫行候選 ─────────────────────────

def test_entry_function_is_named_and_documented_as_a_provisional_candidate_not_a_production_rule():
    fn = adapter.provisional_holding_entry_available
    assert "provisional" in fn.__name__
    doc = inspect.getdoc(fn)
    assert "UI-2" in doc and "NOT VERIFIED" in doc and "不得升格為 production 規則" in doc
    module_doc = inspect.getdoc(adapter)
    assert "UI-2" in module_doc and "不是 production 規則" in module_doc and "暫行候選" in module_doc
    assert "provisional" in inspect.getdoc(vm.PositionEntry).lower() or "暫行候選" in inspect.getdoc(vm.PositionEntry)


@pytest.mark.parametrize("name", list(S.SCENARIOS))
def test_entry_function_always_agrees_with_the_page_and_exists_only_with_usable_rows(name):
    result = S.SCENARIOS[name]()
    model = build(result)
    available = adapter.provisional_holding_entry_available(result)
    assert available is (model.a10.entry is not None) is (model.a50.state == vm.A50_ROWS) is (model.a50.row_count > 0)
    if available:
        assert model.a00.source_state not in vm.NO_ROWS_SOURCE_STATES


def test_entry_appears_exactly_for_complete_partial_and_undetermined_with_rows():
    with_entry = sorted(n for n in S.SCENARIOS if adapter.provisional_holding_entry_available(S.SCENARIOS[n]()))
    assert with_entry == ["complete", "partial", "settings_failed", "unknown_coverage"]


def test_no_page_ever_writes_zero_holdings_a_and_b_have_no_row_container_at_all():
    for name in ("no_active", "read_failed", "complete_no_rows", "market_blocked"):
        model = build(S.SCENARIOS[name]())
        assert model.a50.state == vm.A50_STATUS_ONLY and model.a50.rows == () and model.a10.entry is None
        assert not any(isinstance(leaf, str) and "持倉 0" in leaf for leaf in S.leaf_values(model))


# ───────────────────────── 欄位集合不固化 ─────────────────────────

def test_row_fields_are_a_parameter_vm_accepts_any_set_and_defaults_are_marked_provisional():
    default = build(S.complete_result(1))
    custom = build(S.complete_result(1), row_fields=("fund_code", "zz_other_field"))
    assert [f.field_code for f in default.a50.rows[0].facts] == list(adapter.PROVISIONAL_ROW_FIELDS)
    assert [f.field_code for f in custom.a50.rows[0].facts] == ["fund_code", "zz_other_field"]
    assert custom.a50.rows[0].facts[1].state == vm.ROW_STATE_MISSING                      # 來源沒有的欄位＝缺值＋原因，不編
    assert default.a50.field_set_status == custom.a50.field_set_status == vm.FIELD_SET_PENDING_T6
    assert "T6" in inspect.getsource(adapter) and "不是欄位規格" in inspect.getsource(adapter)


@pytest.mark.parametrize("bad", [(), [], "fund_code", None, ("fund_code", "fund_code"), ("Bad Code",)])
def test_invalid_row_fields_are_rejected(bad):
    with pytest.raises(ValueError):
        build(row_fields=bad)


@pytest.mark.parametrize("value,cause", [
    (None, vm.CAUSE_FIELD_NOT_PROVIDED), ("", vm.CAUSE_FIELD_NOT_PROVIDED), ("   ", vm.CAUSE_FIELD_NOT_PROVIDED),
    (True, vm.CAUSE_VALUE_UNUSABLE), (float("nan"), vm.CAUSE_VALUE_UNUSABLE), (float("inf"), vm.CAUSE_VALUE_UNUSABLE),
    ({"non_finite": "nan"}, vm.CAUSE_VALUE_UNUSABLE), ([1], vm.CAUSE_VALUE_UNUSABLE),
])
def test_unusable_row_values_become_missing_with_a_cause_never_zero(value, cause):
    result = S.complete_result(1)
    result["evidence"]["holdings"][0]["units_shares"] = value
    fact = {f.field_code: f for f in build(result).a50.rows[0].facts}["units_shares"]
    assert fact.state == vm.ROW_STATE_MISSING and fact.value is None and fact.missing.causes[0].cause_key == cause


def test_real_zero_units_is_kept_as_a_fact_not_confused_with_missing():
    result = S.complete_result(1)
    result["evidence"]["holdings"][0]["units_shares"] = 0
    fact = {f.field_code: f for f in build(result).a50.rows[0].facts}["units_shares"]
    assert fact.state == vm.ROW_STATE_PRESENT and fact.value == 0


def test_rows_keep_source_order_without_sorting_or_truncation():
    result = S.complete_result(0)
    result["evidence"]["holdings"] = [S.fake_holding(n, cost_twd=1000 * (10 - n)) for n in (5, 1, 9, 2, 7, 3, 8)]
    rows = build(result).a50.rows
    assert [r.ordinal for r in rows] == list(range(1, 8))
    assert [{f.field_code: f for f in r.facts}["fund_code"].value for r in rows] == [f"FK{n:04d}" for n in (5, 1, 9, 2, 7, 3, 8)]


# ───────────────────────── 純函式：不修改輸入、不保留參照、可重現 ─────────────────────────

@pytest.mark.parametrize("name", list(S.SCENARIOS))
def test_building_does_not_mutate_the_input_and_is_reproducible(name):
    result = S.SCENARIOS[name]()
    before = copy.deepcopy(result)
    first = build(result)
    adapter.provisional_holding_entry_available(result)
    assert result == before
    assert build(result) == first


def test_vm_keeps_no_reference_to_the_input_so_later_edits_do_not_change_it():
    result = S.partial_result()
    model = build(result)
    snapshot = copy.deepcopy(model)
    result["evidence"]["holdings"][0]["fund_code"] = "CHANGED"
    result["evidence"]["holdings"].clear()
    result["problems"].append("no_active_source")
    result["settings_status"]["alo_basis"] = "invalid"
    assert model == snapshot


def test_models_are_frozen_all_the_way_down_no_mutable_containers():
    for name in S.SCENARIOS:
        for node in S.walk(build(S.SCENARIOS[name]())):
            assert not isinstance(node, (list, dict, set)), (name, type(node))


# ───────────────────────── import 隔離與零副作用 ─────────────────────────

_NEW_FILES = ("ui_v3/viewmodels/assets_page.py", "ui_v3/adapters/assets_page.py")


@pytest.mark.parametrize("rel", _NEW_FILES)
def test_new_files_pass_every_static_ui_v3_guard(rel):
    source = lib.read(ROOT / rel)
    assert lib.import_violations(rel, source) == []
    assert lib.write_surface_violations(rel, source) == []
    assert lib.module_level_side_effects(source) == []
    assert rel in {lib.rel_of(p) for p in lib.population()}


def _imports(rel):
    return set(lib.imports_of(ast.parse(lib.read(ROOT / rel)), lib.package_of(rel)))


def test_adapter_imports_only_stdlib_and_viewmodels_no_l2_no_assets_source_no_fixtures_no_streamlit():
    mods = _imports("ui_v3/adapters/assets_page.py")
    roots = {m.split(".")[0] for m in mods}
    assert roots <= set(sys.stdlib_module_names) | {"__future__", "ui_v3"}, roots
    ui_v3_mods = {m for m in mods if m.split(".")[0] == "ui_v3"}
    assert all(m == "ui_v3" or m.startswith("ui_v3.viewmodels") for m in ui_v3_mods), ui_v3_mods
    assert not {m for m in mods if "assets_source" in m or "fixtures" in m or "allocation_evidence" in m}


def test_viewmodel_imports_only_stdlib_viewmodels_and_the_ui_semantics_rules():
    mods = _imports("ui_v3/viewmodels/assets_page.py")
    for m in mods:
        root = m.split(".")[0]
        assert root in set(sys.stdlib_module_names) | {"__future__"} or m.startswith("ui_v3.viewmodels") or m == "ui_v3" \
            or m == "shared.ui_semantics" or m.startswith("shared.ui_semantics."), m


def test_function_bodies_have_no_lazy_imports():
    """本批的兩個新檔沒有任何函式內 import（沒有偷偷延遲載入 L2 的後門）。"""
    for rel in _NEW_FILES:
        for node in ast.walk(ast.parse(lib.read(ROOT / rel))):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                assert not [n for n in ast.walk(node) if isinstance(n, (ast.Import, ast.ImportFrom))], (rel, node.name)


def test_importing_the_adapter_in_a_clean_interpreter_loads_no_l2_ui_or_third_party_modules():
    code = (
        f"import sys; sys.path.insert(0, {str(ROOT)!r})\n"
        "import ui_v3.adapters.assets_page, ui_v3.viewmodels.assets_page\n"
        "banned_roots = {'streamlit','ui','ui_v2','services','repositories','infra','fund_fetcher','app','pandas','numpy','requests',"
        "'gspread','yfinance','bs4'}\n"
        "bad = sorted(n for n in sys.modules if n.split('.')[0] in banned_roots or n in {'ui_v3.adapters.assets_source', 'ui_v3.fixtures'}"
        " or (n.startswith('shared.') and not n.startswith('shared.ui_semantics')))\n"
        "print('BAD:' + ','.join(bad))\n"
    )
    proc = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, cwd=str(ROOT), timeout=60)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "BAD:", proc.stdout


# ───────────────────────── 部分缺漏：略過分頁與略過列各自獨立成立（存活變異 `or`→`and`） ─────────────────────────

def test_partial_when_only_tabs_were_skipped_and_no_rows_were_skipped():
    model = build(S.partial_tabs_only_result())
    assert model.a00.source_state == vm.SRC_PARTIAL
    assert (model.a60.skipped_tab_count, model.a60.skipped_row_count) == (1, 0)
    assert model.a10.entry is not None and model.a50.row_count == 1
    assert model.a10.missing.categories == (A, B)


def test_partial_when_only_rows_were_skipped_and_no_tabs_were_skipped():
    model = build(S.partial_rows_only_result())
    assert model.a00.source_state == vm.SRC_PARTIAL
    assert (model.a60.skipped_tab_count, model.a60.skipped_row_count) == (0, 1)
    assert model.a10.entry is not None and model.a50.row_count == 1
    assert model.a10.missing.categories == (A, B)


# ───────────────────────── coverage=complete 的防禦：略過證據必須已提供且為 0 ─────────────────────────

@pytest.mark.parametrize("facet", ["skipped_tabs", "omitted_rows"])
@pytest.mark.parametrize("rows", [0, 1])
def test_complete_coverage_with_an_unprovided_skip_facet_is_undetermined_never_read_to_the_end(facet, rows):
    model = build(S.complete_with_unprovided_skip_evidence_result(rows=rows, missing_facet=facet))
    assert model.a00.source_state == vm.SRC_UNDETERMINED and model.a00.status_key == "undetermined"
    assert model.a00.source_state not in (vm.SRC_COMPLETE, vm.SRC_COMPLETE_NO_ROWS)   # 沒有證據時不得寫『來源已讀完』或『沒有有效持倉列』
    assert (model.a50.state == vm.A50_ROWS) is bool(rows) and (model.a10.entry is not None) is bool(rows)
    unknown = model.a60.skipped_tab_count if facet == "skipped_tabs" else model.a60.skipped_row_count
    assert unknown is None            # 沒提供＝不知道，不是 0


@pytest.mark.parametrize("facet", ["skipped_tabs", "omitted_rows"])
def test_complete_coverage_that_contradicts_positive_skip_counts_is_undetermined(facet):
    model = build(S.complete_with_skip_items_result(facet))
    assert model.a00.source_state == vm.SRC_UNDETERMINED
    assert model.a60.skipped_tab_count == (1 if facet == "skipped_tabs" else 0)


def test_complete_coverage_with_both_skip_facets_provided_and_empty_is_still_complete():
    assert build(S.complete_result(1)).a00.source_state == vm.SRC_COMPLETE
    assert build(S.complete_no_rows_result()).a00.source_state == vm.SRC_COMPLETE_NO_ROWS


# ───────────────────────── bucket：不在預設欄位集合（82 §11.3 語意落差），但呼叫端可明確傳入 ─────────────────────────

def test_bucket_is_not_a_default_field_but_can_be_requested_and_its_gap_is_registered():
    assert "bucket" not in adapter.PROVISIONAL_ROW_FIELDS
    assert "bucket" not in {f.field_code for r in build(S.complete_result(1)).a50.rows for f in r.facts}
    custom = build(S.complete_result(1), row_fields=("fund_code", "bucket"))
    assert [f.field_code for f in custom.a50.rows[0].facts] == ["fund_code", "bucket"]
    assert "bucket_blank_semantics_gap" in vm.PROVISIONAL_KEYS


# ───────────────────────── 暫行標示清單 ─────────────────────────

_REQUIRED_PROVISIONAL_KEYS = {
    "partial_narrow_definition", "complete_no_rows_is_category_a", "a20_cells_share_one_missing_fact",
    "entry_shown_when_undetermined_with_rows", "entry_extra_coverage_and_blocked_conditions", "a60_field_set",
    "market_basis_blocked_symbol_and_category", "a00_states_without_approved_symbol",
    "cause_basis_not_approved_plain_wording_derived", "a52_four_setting_states", "first_screen_count_policies",
    "complete_requires_zero_skip_evidence", "bucket_blank_semantics_gap", "provisional_row_fields_exclude_amounts",
    "problems_override_contradicting_coverage", "limit_no_fx_conversion_always_present",
    "undetermined_with_rows_claims_viewable_holdings", "row_field_missing_always_category_a", "a30_a40_share_one_missing_fact",
}


def test_provisional_items_key_set_is_locked_and_every_item_is_explained_and_unique():
    assert set(vm.PROVISIONAL_KEYS) == _REQUIRED_PROVISIONAL_KEYS and len(vm.PROVISIONAL_KEYS) == len(_REQUIRED_PROVISIONAL_KEYS)
    for item in vm.PROVISIONAL_ITEMS:
        assert isinstance(item, vm.ProvisionalItem) and item.note.strip() and item.gap_ref.strip(), item.key
        assert ("不得升格" in item.note) or ("待 UI Review" in item.note) or ("已知落差" in item.note), item.key
    assert vm.provisional_item("complete_no_rows_is_category_a").note.startswith("暫行：(c)")
    assert "Decision Gate" in vm.provisional_item("complete_no_rows_is_category_a").note
    with pytest.raises(KeyError):
        vm.provisional_item("not_registered")
    for bad in ({"key": "", "note": "x", "gap_ref": "y"}, {"key": "k", "note": " ", "gap_ref": "y"}, {"key": "k", "note": "x", "gap_ref": ""}):
        with pytest.raises(ValueError):
            vm.ProvisionalItem(**bad)


def _carriers():
    """每個登記項 → 承載它引用的**指定物件**（docstring、公開字串屬性或暫時字樣的 source）。逐 key 檢查，不用整檔字串包含。"""
    return {
        "partial_narrow_definition": adapter._resolve,
        "complete_requires_zero_skip_evidence": adapter._resolve,
        "problems_override_contradicting_coverage": adapter._resolve,
        "complete_no_rows_is_category_a": adapter._causes_for,
        "undetermined_with_rows_claims_viewable_holdings": adapter._causes_for,
        "market_basis_blocked_symbol_and_category": vm.A00Status,
        "a00_states_without_approved_symbol": vm.A00Status,
        "entry_shown_when_undetermined_with_rows": adapter.provisional_holding_entry_available,
        "entry_extra_coverage_and_blocked_conditions": adapter.provisional_holding_entry_available,
        "a20_cells_share_one_missing_fact": vm.A20Summary,
        "a30_a40_share_one_missing_fact": vm.NoResultLine,
        "a52_four_setting_states": vm.A52Section,
        "a60_field_set": vm.A60Evidence,
        "limit_no_fx_conversion_always_present": vm.A10Card,
        "row_field_missing_always_category_a": adapter._row_fact,
        "first_screen_count_policies": vm.FirstScreenCountPolicy,
        "cause_basis_not_approved_plain_wording_derived": vm.pending_wording("cause_basis_not_approved").source,
        "provisional_row_fields_exclude_amounts": adapter.PROVISIONAL_ROW_FIELDS_NOTE,
        "bucket_blank_semantics_gap": adapter.PROVISIONAL_ROW_FIELDS_NOTE,
    }


def _text_of(carrier):
    return carrier if isinstance(carrier, str) else (inspect.getdoc(carrier) or "")


def test_every_registered_provisional_item_is_cited_by_its_own_designated_object():
    carriers = _carriers()
    assert set(carriers) == set(vm.PROVISIONAL_KEYS)                      # 沒有登記項漏掉承載物，也沒有多餘的
    for key, carrier in carriers.items():
        assert key in _text_of(carrier), key
        assert "不得升格" in _text_of(carrier) or "待 UI Review" in _text_of(carrier), key
    assert "cause_key" in inspect.getdoc(vm) and "UI-1" in inspect.getdoc(vm)


def test_no_docstring_or_comment_still_claims_a_test_locks_the_loader_or_producer():
    for rel in ("ui_v3/adapters/assets_page.py", "ui_v3/viewmodels/assets_page.py"):
        text = lib.read(ROOT / rel)
        assert "逐字對載入端" not in text and "（測試鎖" not in text and "(測試鎖" not in text and "詞彙鏡像" not in text and "代碼的鏡像" not in text, rel
    assert "NOT VERIFIED" in inspect.getdoc(adapter)
