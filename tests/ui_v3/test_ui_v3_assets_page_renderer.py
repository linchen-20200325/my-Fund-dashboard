# -*- coding: utf-8 -*-
"""💼 我的資產頁 renderer（A00／A10／A20，隔離式 FAKE Preview 第一批）單元與守衛。純 HTML 層，不需要瀏覽器。

資料全部是 `assets_page_support` 的 FAKE 輸入；七個情境與隔離入口的 FAKE 輸入同形（drift 測試在 `tests/poc_assets_preview/`）。
負控一律在記憶體內現編，不寫檔、不改任何 production 檔。
"""
from __future__ import annotations

import ast
import re
import subprocess
import sys
from html.parser import HTMLParser

import pytest

import assets_page_support as sup
import ui_v3_guard_lib as lib
from shared.ui_semantics import rules
from ui_v3.adapters.assets_page import build_assets_page
from ui_v3.design import tokens
from ui_v3.pages import assets
from ui_v3.viewmodels import assets_page as vm
from ui_v3.viewmodels import assets_preview_wording as AW

RENDERER_SRC = lib.read(lib.ROOT / "ui_v3" / "pages" / "assets.py")
WORDING_SRC = lib.read(lib.ROOT / "ui_v3" / "viewmodels" / "assets_preview_wording.py")


def _multi_currency():
    return sup.fake_result(evidence=sup.fake_evidence(holdings=[sup.fake_holding(1, ccy="TWD"), sup.fake_holding(2, ccy="USD")]))


SCENARIOS = {
    "multi_currency": _multi_currency,
    "complete_no_rows": sup.complete_no_rows_result,
    "market_blocked": sup.market_blocked_result,
    "partial": sup.partial_result,
    "no_active": sup.no_active_result,
    "read_failed": sup.read_failed_result,
    "unprovided_skip_evidence": lambda: sup.complete_with_unprovided_skip_evidence_result(rows=0),
}
EXPECTED_STATE = {"multi_currency": "complete", "complete_no_rows": "complete_no_rows", "market_blocked": "not_read", "partial": "partial",
                  "no_active": "not_selected", "read_failed": "read_failed", "unprovided_skip_evidence": "undetermined"}


def model_of(name):
    return build_assets_page(SCENARIOS[name]())


def html_of(name):
    return assets.page_html(model_of(name))


class _Visible(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_starttag(self, tag, attrs):
        self.parts += [v for k, v in attrs if k in ("aria-label", "title", "alt") and v]

    def handle_data(self, data):
        self.parts.append(data)


def visible(html):
    p = _Visible()
    p.feed(html)
    return " ".join(p.parts)


ALL = list(SCENARIOS)


# ───────────────────────── 前提：情境真的落在預期的來源狀態 ─────────────────────────

@pytest.mark.parametrize("name", ALL)
def test_scenarios_land_in_the_intended_source_state(name):
    assert model_of(name).a00.source_state == EXPECTED_STATE[name]


# ───────────────────────── 結構：A00／A10／A20、首屏五個 ─────────────────────────

@pytest.mark.parametrize("name", ALL)
def test_blocks_in_fixed_order_and_first_screen_marks_are_exactly_five(name):
    html = html_of(name)
    marks = re.findall(r'data-first-screen="([^"]+)"', html)
    assert marks == ["a00", *vm.A20_CELL_CODES]
    assert len(marks) == vm.first_screen_element_count(model_of(name), vm.POLICY_A10_TEXT_EXCLUDED) == 5
    assert html.index('data-block="a00"') < html.index('data-block="a10"') < html.index('data-block="a20"')
    for forbidden in ('data-block="a30"', 'data-block="a40"', 'data-block="a50"', 'data-block="a52"', 'data-block="a60"'):
        assert forbidden not in html


@pytest.mark.parametrize("name", ALL)
def test_a10_text_has_no_first_screen_mark_and_is_not_a_chip(name):
    html = html_of(name)
    a10 = html[html.index('data-block="a10"'):html.index('data-block="a20"')]
    assert "data-first-screen" not in a10
    assert "uv3-chip" not in html
    assert 'data-status-key="missing"' in a10


@pytest.mark.parametrize("name", ALL)
def test_a20_is_always_four_missing_cells_and_never_a_value(name):
    html = html_of(name)
    a20 = html[html.index('<div class="uv3-a20"'):]
    assert len(re.findall(r'data-cell="a20_cell_[1-4]"', a20)) == 4
    assert a20.count('data-status-key="missing"') == 4
    assert re.findall(r'data-cell="([^"]+)"', a20) == list(vm.A20_CELL_CODES)
    assert not re.search(r"[0-9]", visible(a20))


@pytest.mark.parametrize("name", ALL)
def test_each_cause_is_its_own_row_and_the_status_symbol_is_the_approved_text(name):
    model = model_of(name)
    html = html_of(name)
    rows = re.findall(r'data-a10="cause"', html)
    assert len(rows) == len(model.a10.missing.causes)
    assert rules.entry("missing").wording in visible(html)
    assert html.count('data-a10="spec"') == 1 and html.count('data-a10="limit"') == len(model.a10.limit_codes) == 1


# ───────────────────────── 逐情境字樣 ─────────────────────────

def test_complete_no_rows_is_not_a_failure_or_a_data_gap_and_shows_both_pending_keys():
    html = html_of("complete_no_rows")
    text = visible(html)
    assert "取數失敗" not in text and "資料缺漏" not in text
    assert 'data-pending-wording="a00_complete"' in html and 'data-pending-wording="a00_complete_no_rows"' in html
    a10 = html[html.index('data-block="a10"'):html.index('data-block="a20"')]
    cause = a10[a10.index('data-a10="cause"'):a10.index('data-a10="spec"')]
    assert cause.count("data-pending-wording") == 2   # 分隔符＋同一句；不重複展開 A00 的兩句
    assert 'data-pending-wording="a00_complete_no_rows"' in cause and "a00_complete\"" not in cause


def test_read_failed_shows_fetch_failed_and_never_the_failure_code():
    model = model_of("read_failed")
    assert model.a00.failure_code == "NETWORK_ERROR"   # VM 有、畫面不得有
    html = html_of("read_failed")
    assert "NETWORK" not in html and "ERROR" not in html and "failure" not in html.lower()
    assert rules.entry("fetch_failed").wording in visible(html)
    assert 'data-status-key="fetch_failed"' in html


@pytest.mark.parametrize("name", ["unprovided_skip_evidence", "market_blocked"])
def test_undetermined_and_not_read_never_claim_the_source_was_read(name):
    html = html_of(name)
    assert "來源已讀完" not in visible(html) and "a00_complete" not in html
    a00 = html[:html.index('data-block="a10"')]
    assert rules.entry("undetermined").wording in visible(a00)


def test_market_blocked_hides_the_internal_reason_and_does_not_claim_holdings():
    model = model_of("market_blocked")
    assert model.a00.cause_key
    html = html_of("market_blocked")
    assert model.a00.cause_key not in html and "market_basis" not in html
    assert "已有持倉資料可查看" not in html
    assert 'data-pending-wording="cause_basis_not_approved"' in html and "cause_basis_not_approved_with_rows" not in html


def test_not_selected_uses_its_own_pending_sentence():
    html = html_of("no_active")
    assert 'data-pending-wording="a00_not_selected"' in html
    assert html.count('data-pending-wording="a00_not_selected"') == 2   # A00 與 A10 原因行（引用同一句）


def test_partial_shows_two_separate_cause_rows_a_before_b():
    html = html_of("partial")
    causes = re.findall(r'data-a10="cause">(.*?)</div>', html)
    assert len(causes) == 2
    assert "cause_partial_source" in causes[0] and "cause_basis_not_approved_with_rows" in causes[1]
    assert "cause_partial_source" not in causes[1]


def test_multi_currency_is_shown_without_any_total_or_conversion():
    model = model_of("multi_currency")
    ccys = {f.value for row in model.a50.rows for f in row.facts if f.field_code == "ccy"}
    assert ccys == {"TWD", "USD"}
    html = html_of("multi_currency")
    text = visible(html)
    assert "TWD" not in html and "USD" not in html
    assert 'data-pending-wording="limit_no_fx_conversion"' in html
    assert not re.search(r"[0-9]", text)
    assert "總計" not in text and "合計：" not in text


# ───────────────────────── 入口不畫 ─────────────────────────

ENTRY_SCENARIOS = [n for n in ALL if model_of(n).a10.entry is not None]


def test_entry_scenarios_include_complete_and_partial():
    assert {"multi_currency", "partial"} <= set(ENTRY_SCENARIOS)   # 正控：參數化母體真的含「帶入口」的情境


@pytest.mark.parametrize("name", ENTRY_SCENARIOS)
def test_position_entry_is_never_drawn_even_when_the_model_has_one(name):
    model = model_of(name)
    assert model.a10.entry is not None   # 前提：VM 真的帶了入口
    html = assets.page_html(model)
    assert "entry_view_holdings" not in html and "查看持倉明細" not in html
    assert not re.search(r"<a[ >]|href=|<button|role=\"link\"|data-entry|A50", html)


def test_registered_gap_undetermined_with_rows_claims_viewable_holdings_is_locked_as_is():
    """已登記落差 `undetermined_with_rows_claims_viewable_holdings`：證據不足（undetermined）但有列時，VM 的原因含「已有持倉資料可查看」。
    Preview 刻意不使用此情境；這裡只鎖 renderer 對該 model 的實際輸出（不改 renderer 行為）：A00 仍是無法判定、不聲稱來源已讀完，
    A10 兩個原因各一行（先同 A00 的無法判定，再「已有持倉資料可查看…」），仍不畫入口。"""
    result = sup.complete_with_unprovided_skip_evidence_result(rows=1)
    model = build_assets_page(result)
    assert model.a00.source_state == "undetermined" and model.a50.row_count == 1
    assert [c.cause_key for c in model.a10.missing.causes] == ["same_as_source_status", "basis_not_approved_with_rows"]
    html = assets.page_html(model)
    a00 = html[:html.index('data-block="a10"')]
    assert rules.entry("undetermined").wording in visible(a00) and "來源已讀完" not in visible(html)
    causes = re.findall(r'data-a10="cause">(.*?)</div>', html)
    assert len(causes) == 2
    assert 'data-status-key="undetermined"' in causes[0] and 'data-pending-wording="cause_basis_not_approved_with_rows"' in causes[1]
    assert "已有持倉資料可查看" in visible(html)   # 落差本身：不足以判定卻聲稱有資料可看（待客戶裁示，不在本批處置）
    assert model.a10.entry is not None and "查看持倉明細" not in html


# ───────────────────────── 全頁禁止內容 ─────────────────────────

@pytest.mark.parametrize("name", ALL)
def test_no_percent_amount_zero_count_or_advice_in_the_page(name):
    html = html_of(name)
    text = visible(html)
    assert "%" not in html and "％" not in html
    assert not re.search(r"[0-9]", text)
    for bad in ("資產 0", "持倉 0", "資產0", "持倉0", "100", "建議", "風險", "安全", "正常", "健康", "賣出", "買進"):
        assert bad not in text, bad


@pytest.mark.parametrize("name", ALL)
def test_sentinel_numbers_and_row_facts_never_leak_into_the_page(name):
    html = html_of(name)
    for sentinel in (sup.SENTINEL_CATEGORY_VALUE, sup.SENTINEL_HOLDING_VALUE, sup.SENTINEL_COST_TWD, sup.SENTINEL_COST_ORIG, sup.SENTINEL_SHARE_PCT):
        for form in (str(sentinel), f"{sentinel:,.2f}", f"{sentinel:,.1f}", str(int(sentinel)), f"{int(sentinel):,}"):
            assert form not in html, form
    for fact in ("FAKE 基金", "FK0001", "FAKE-POLICY", "FAKE-TAB"):
        assert fact not in html


@pytest.mark.parametrize("name", ALL)
def test_no_engineering_text_is_visible(name):
    text = visible(html_of(name))
    env, snake = re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b"), re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b")
    assert not env.findall(text) and not snake.findall(text)
    assert not re.search(r"Traceback|Exception|Error|\.py\b|\b(?:services|repositories|infra|shared|ui_v2|ui_v3)[./]", text)


@pytest.mark.parametrize("name", ALL)
def test_every_pending_key_shown_exists_in_a_pending_table(name):
    keys = set(re.findall(r'data-pending-wording="([^"]+)"', html_of(name)))
    assert keys and keys <= set(vm.ASSETS_PENDING_WORDING) | set(AW.ASSETS_PREVIEW_WORDING)
    assert not (set(vm.ASSETS_PENDING_WORDING) & set(AW.ASSETS_PREVIEW_WORDING))


def test_a20_labels_are_marked_provisional_on_screen():
    html = html_of("multi_currency")
    assert 'data-a20="labels-note"' in html and "暫行" in visible(html)


# ───────────────────────── 不讀分類欄位（施工 A） ─────────────────────────

def category_reads(source):
    """原始碼中對原因分類欄位的任何讀取或引用（名稱、屬性、字串）。"""
    hits = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Name) and node.id.startswith("CATEGORY_"):
            hits.append(node.id)
        elif isinstance(node, ast.Attribute) and (node.attr.startswith("CATEGORY_") or node.attr in ("category", "categories")):
            hits.append(f".{node.attr}")
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in ("category", "categories"):
            hits.append(repr(node.value))
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "getattr" and len(node.args) > 1 \
                and isinstance(node.args[1], ast.Constant) and node.args[1].value in ("category", "categories"):
            hits.append("getattr")
    return hits


def test_renderer_never_reads_cause_categories():
    assert category_reads(RENDERER_SRC) == []
    for token in ("CATEGORY_", ".category", ".categories"):
        assert token not in RENDERER_SRC


@pytest.mark.parametrize("snippet", ["x = c.category\n", "y = m.categories\n", "z = vm.CATEGORY_SOURCE_DATA\n", "w = getattr(c, 'category')\n"])
def test_negative_control_category_checker_turns_red(snippet):
    assert category_reads(snippet)


@pytest.mark.parametrize("name", ALL)
def test_output_is_invariant_to_the_category_field(name):
    """把每個原因的分類欄位改成另一類（繞過 frozen），畫面一字不變。"""
    model = model_of(name)
    before = assets.page_html(model)
    other = {vm.CATEGORY_SOURCE_DATA: vm.CATEGORY_BASIS_NOT_APPROVED, vm.CATEGORY_BASIS_NOT_APPROVED: vm.CATEGORY_SOURCE_DATA}
    for cause in model.a10.missing.causes:
        object.__setattr__(cause, "category", other[cause.category])
    assert assets.page_html(model) == before


# ───────────────────────── 原始碼層守衛 ─────────────────────────

def _docstring_ids(tree):
    return {id(n.body[0].value) for n in ast.walk(tree)
            if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.body
            and isinstance(n.body[0], ast.Expr) and isinstance(getattr(n.body[0], "value", None), ast.Constant)}


_CJK = re.compile(r"[㐀-鿿＀-￯①-⓿]")


def hardcoded_cjk(source):
    tree = ast.parse(source)
    skip = _docstring_ids(tree)
    return [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in skip and _CJK.search(n.value)]


def test_renderer_hardcodes_no_chinese_string():
    assert hardcoded_cjk(RENDERER_SRC) == []


def test_negative_control_hardcoded_text_checker_turns_red():
    assert hardcoded_cjk('x = "寫死的字"\n') and not hardcoded_cjk('"""說明"""\nx = "ok"\n')


def test_no_poc_path_string_and_no_hex_colour_in_renderer_or_wording():
    for src in (RENDERER_SRC, WORDING_SRC):
        assert "poc/" not in src
        assert not re.search(r"#[0-9a-fA-F]{3,8}\b", src) and "rgb(" not in src
    hexes = set(re.findall(r"#[0-9a-fA-F]{3,8}\b", assets.CSS))
    allowed = {h.lower() for name in tokens.TOKEN_NAMES for h in re.findall(r"#[0-9a-fA-F]{3,8}\b", repr(tokens.TOKENS[name]))}
    assert {h.lower() for h in hexes} <= allowed


def test_renderer_imports_follow_layer_rules_and_do_not_touch_adapters_or_lower_layers():
    rel = "ui_v3/pages/assets.py"
    assert lib.import_violations(rel, RENDERER_SRC) == []
    assert lib.write_surface_violations(rel, RENDERER_SRC) == []
    mods = lib.imports_of(ast.parse(RENDERER_SRC), lib.package_of(rel))
    for bad in ("ui_v3.adapters", "ui_v3.fixtures", "services", "gspread", "requests", "repositories", "infra"):
        assert not [m for m in mods if m == bad or m.startswith(bad + ".")], bad
    top = [n for n in ast.parse(RENDERER_SRC).body if isinstance(n, (ast.Import, ast.ImportFrom))]
    assert not [n for n in top if "streamlit" in ast.dump(n)]   # streamlit 只在函式內 import


def test_importing_the_renderer_does_not_load_streamlit_or_forbidden_modules():
    code = ("import sys; import ui_v3.pages.assets as a; "
            "bad=[m for m in sys.modules if m=='streamlit' or m.startswith(('streamlit.','services','ui_v3.adapters','ui_v3.fixtures','gspread','requests'))]; "
            "print(bad)")
    out = subprocess.run([sys.executable, "-c", code], cwd=str(lib.ROOT), capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "[]", out.stdout


def test_model_type_is_checked():
    with pytest.raises(TypeError):
        assets.page_html({"a00": 1})
    with pytest.raises(ValueError):
        assets.source_state_html("no_such_state")
