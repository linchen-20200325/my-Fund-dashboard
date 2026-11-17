# -*- coding: utf-8 -*-
"""💼 我的資產頁 renderer（A00／A10／A20＋A50 單一容器四欄唯讀持倉＋A60 來源與缺項證據，隔離式 FAKE Preview）單元與守衛。純 HTML 層，不需要瀏覽器。

資料全部是 `assets_page_support` 的 FAKE 輸入；十一個情境與隔離入口的 FAKE 輸入同形（drift 測試在 `tests/poc_assets_preview/`）。
A50 區（`<details>` 容器或 status-only 那一列）允許 fund_name／fund_code／ccy／units_shares 的 FAKE 值；**非 A50 區**的「無數字／無 FAKE 事實」斷言維持原樣不放寬，
A50 區另有針對性斷言（無 %、金額字樣、合計、占比、「資產 0」「持倉 0」，不含 holding_id、policy_id、cost_*）。
A60 區（DEC-2026-11-17-01）在頁面最後、A50 之後：`split_a50` 的「A50 區」不含 A60，`split_a60` 另切；A60 允許顯示略過件數（整數），其餘區塊的斷言不放寬。
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
    "same_fund_two_policies": sup.same_fund_two_policies_result,
    "many_rows": sup.many_rows_result,
    "a60_sensitive_strings": sup.a60_sensitive_strings_result,
    "complete_counts_unprovided": sup.complete_counts_unprovided_result,
}
EXPECTED_STATE = {"multi_currency": "complete", "complete_no_rows": "complete_no_rows", "market_blocked": "not_read", "partial": "partial",
                  "no_active": "not_selected", "read_failed": "read_failed", "unprovided_skip_evidence": "undetermined",
                  "same_fund_two_policies": "complete", "many_rows": "complete", "a60_sensitive_strings": "partial",
                  "complete_counts_unprovided": "undetermined"}


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
A50_SCENARIOS = [n for n in ALL if model_of(n).a50.state == vm.A50_ROWS]
STATUS_ONLY_SCENARIOS = [n for n in ALL if model_of(n).a50.state == vm.A50_STATUS_ONLY]


A60_MARK = '<details class="uv3-a60"'


def split_a60(html):
    """(A60 之前, A60 區)。A60 是最後一個區塊（A50 之後、獨立 `<details>`）；沒有 A60 標記 → 整頁與空字串（讓缺 A60 的頁在結構測試中變紅）。"""
    i = html.find(A60_MARK)
    return (html, "") if i < 0 else (html[:i], html[i:])


def split_a50(html):
    """(非 A50 區, A50 區)。A50 區止於 A60 之前：容器 `<details`（第一個）或 status-only 那一列之後、A60 之前都算 A50。"""
    html = split_a60(html)[0]
    marks = [html.find(m) for m in ("<details", 'data-a50="status-only"') if html.find(m) >= 0]
    if not marks:
        return html, ""
    i = min(marks)
    i = html.rfind("<div", 0, i) if html[i:i + 8] != "<details" else i
    return html[:i], html[i:]


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
    for forbidden in ('data-block="a30"', 'data-block="a40"', 'data-block="a51"', 'data-block="a52"'):
        assert forbidden not in html
    # A60（DEC-2026-11-17-01）恆畫一次，在 A50（若有）之後、整頁最後；不標首屏
    assert html.count('data-block="a60"') == 1 and html.index('data-block="a20"') < html.index('data-block="a60"')
    assert html.index('data-block="a60"') > max(html.find('data-block="a50"'), html.find('data-a50="status-only"'))
    assert "data-first-screen" not in split_a60(html)[1] and html.endswith("</details>")
    # A50 只有「有列」才畫容器，且在 A20 之後；沒有列時不畫容器（status-only 只有一列文字）
    assert ('data-block="a50"' in html) is (name in A50_SCENARIOS)
    if name in A50_SCENARIOS:
        assert html.index('data-block="a20"') < html.index('data-block="a50"')
    assert "data-first-screen" not in split_a50(html)[1]


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
    a20 = split_a50(html)[0][html.index('<div class="uv3-a20"'):]
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
    assert html.count('data-pending-wording="a00_not_selected"') == 3   # A00、A10 原因行、A50 的 status-only 那一列（皆引用同一句）


def test_partial_shows_two_separate_cause_rows_a_before_b():
    html = html_of("partial")
    causes = re.findall(r'data-a10="cause">(.*?)</div>', html)
    assert len(causes) == 2
    assert "cause_partial_source" in causes[0] and "cause_basis_not_approved_with_rows" in causes[1]
    assert "cause_partial_source" not in causes[1]


def test_multi_currency_is_shown_per_row_without_any_total_or_conversion():
    model = model_of("multi_currency")
    ccys = {f.value for row in model.a50.rows for f in row.facts if f.field_code == "ccy"}
    assert ccys == {"TWD", "USD"}
    html = html_of("multi_currency")
    outside, a50 = split_a50(html)
    assert "TWD" not in outside and "USD" not in outside        # 非 A50 區不出現原幣
    assert "TWD" in a50 and "USD" in a50                          # 原幣只以 A50 逐檔原值呈現
    assert 'data-pending-wording="limit_no_fx_conversion"' in outside
    limit = re.search(r'data-a10="limit">(.*?)</div>', html).group(1)
    assert visible(limit).strip() == "此預覽不提供匯率換算或跨幣別合計"   # 客戶 DEC-2026-11-16-01 指定字樣（暫行，不進已核准字樣表）
    assert not re.search(r"[0-9]", visible(outside))
    text = visible(a50)
    assert "總計" not in text and "合計" not in text and "換算" not in text and "%" not in a50


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
    outside, a50 = split_a50(html)
    text = visible(html)
    assert "%" not in html and "％" not in html
    assert not re.search(r"[0-9]", visible(outside))       # 非 A50 區維持「無任何數字」（不放寬）
    for bad in ("資產 0", "持倉 0", "資產0", "持倉0", "建議", "風險", "安全", "正常", "健康", "賣出", "買進"):
        assert bad not in text, bad                          # 全頁（含 A50）仍禁
    assert "100" not in visible(outside)                      # 「100」只在非 A50 區禁（A50 的 FAKE 單位數可能含此子字串；百分比由 % 守衛擋）
    for bad in ("總計", "合計", "占比", "佔比", "報酬率", "損益", "配息率", "成本", "市值", "金額", "NT$", "$", "元"):
        assert bad not in visible(a50), bad


@pytest.mark.parametrize("name", ALL)
def test_sentinel_numbers_and_row_facts_never_leak_into_the_page(name):
    html = html_of(name)
    outside, a50 = split_a50(html)
    for sentinel in (sup.SENTINEL_CATEGORY_VALUE, sup.SENTINEL_HOLDING_VALUE, sup.SENTINEL_COST_TWD, sup.SENTINEL_COST_ORIG, sup.SENTINEL_SHARE_PCT):
        for form in (str(sentinel), f"{sentinel:,.2f}", f"{sentinel:,.1f}", str(int(sentinel)), f"{int(sentinel):,}"):
            assert form not in outside, form                 # 非 A50 區：所有寫法都不得出現（不放寬）
            if "." in form or "," in form or len(form) >= 6:
                assert form not in a50, form                 # A50 區：帶小數點／千分位、或 6 位以上整數（不可能與 FAKE 編號巧合）不得出現；僅短整數（如 33）豁免
    for fact in ("FAKE 基金", "FK0001", "FAKE-POLICY", "FAKE-TAB"):
        assert fact not in outside                           # 非 A50 區不得有逐檔事實（不放寬）
    for fact in ("FAKE-POLICY", "FAKE-TAB", "FAKE-X", "|"):
        assert fact not in html, fact                        # 身份鍵／保單代號／略過證據任何地方都不得外洩（A50 也不行）


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


# ───────────────────────── A50：單一容器、四欄唯讀持倉（DEC-2026-11-16-01） ─────────────────────────

FIELD_ORDER = ["fund_name", "fund_code", "ccy", "units_shares"]


def test_a50_scenario_populations_are_not_empty_positive_controls():
    assert {"multi_currency", "partial", "same_fund_two_policies", "many_rows"} <= set(A50_SCENARIOS)
    assert {"complete_no_rows", "market_blocked", "no_active", "read_failed", "unprovided_skip_evidence"} == set(STATUS_ONLY_SCENARIOS)


@pytest.mark.parametrize("name", A50_SCENARIOS)
def test_a50_is_exactly_one_collapsed_details_container_with_one_summary_and_no_nesting(name):
    html = split_a60(html_of(name))[0]   # A50 區在 A60 之前；A60 的結構另有 `test_page_has_a50_and_a60_as_two_sibling_collapsed_details`
    assert html.count("<details") == 1 and html.count("</details>") == 1 and html.count("<summary") == 1
    assert html.count('data-block="a50"') == 1
    assert not re.search(r"<details[^>]*\sopen[\s>=]", html)              # 預設收合（DEC 待確認 (c) 未裁；暫行）
    a50 = html[html.index("<details"):html.index("</details>")]
    assert a50.index("<summary") < a50.index("data-row=")              # 摘要（可點的列）在逐檔列之前
    assert html.index("</details>") == len(html) - len("</details>")      # A50 是 A60 之前的最後一個區塊
    # 沒有任何其他展開元件：逐檔不展開（A51 不在本批）、不放進別的展開容器
    for bad in ("<details", "expander", "<dialog", 'role="button"', "<button", "<a ", "href=", "onclick", "<script"):
        assert a50.count(bad) <= (1 if bad == "<details" else 0), bad


@pytest.mark.parametrize("name", A50_SCENARIOS)
def test_a50_rows_follow_source_order_with_the_four_fields_in_fixed_order(name):
    model = model_of(name)
    a50 = split_a50(html_of(name))[1]
    rows = re.findall(r'<div class="uv3-a50-row" data-row="(\d+)">(.*?)</div></div>(?=<div class="uv3-a50-row"|</div></details>)', a50)
    assert [int(n) for n, _ in rows] == [r.ordinal for r in model.a50.rows] == list(range(1, model.a50.row_count + 1))
    for _, body in rows:
        assert re.findall(r'data-field="([^"]+)"', body) == FIELD_ORDER
        assert re.findall(r'data-pending-wording="(a50_col_[a-z_]+)"', body) == [k for _, k in AW.A50_FIELD_LABEL_KEYS]


def test_a50_field_labels_are_pending_wording_aligned_with_the_adapter_field_set():
    from ui_v3.adapters import assets_page as adapter

    assert [c for c, _ in AW.A50_FIELD_LABEL_KEYS] == list(adapter.PROVISIONAL_ROW_FIELDS) == FIELD_ORDER
    assert [AW.preview_wording(k).text for _, k in AW.A50_FIELD_LABEL_KEYS] == ["基金名稱", "基金代號", "幣別", "單位數"]
    for key in [k for _, k in AW.A50_FIELD_LABEL_KEYS] + ["a50_title", "a50_labels_note"]:
        item = AW.preview_wording(key)
        assert item.status == "pending" and item.source.strip() and key not in rules.APPROVED_WORDING
    html = html_of("multi_currency")
    assert "暫行字樣，尚未核准" in visible(html) and 'data-a50="labels-note"' in html


@pytest.mark.parametrize("name", STATUS_ONLY_SCENARIOS)
def test_status_only_draws_a_single_line_quoting_a00_and_no_container_table_entry_or_zero(name):
    html = split_a60(html_of(name))[0]   # A60 另有自己的獨立 `<details>` 與件數（見 A60 測試）；此處只看 A50 的 status-only
    model = model_of(name)
    assert model.a50.state == vm.A50_STATUS_ONLY and model.a50.rows == ()
    for bad in ("<details", "<summary", 'data-block="a50"', "data-row=", "<table", "<a ", "href=", "<button", "data-entry"):
        assert bad not in html, bad
    assert html.count('data-a50="status-only"') == 1
    line = re.search(r'<div class="uv3-row" data-a50="status-only">(.*?)</div>$', html).group(1)
    a00 = html[:html.index('data-block="a10"')]
    a00_status = a00[a00.index('<span class="uv3-label">'):a00.rindex("</div>")]
    assert a00_status.split("</span>", 1)[1] in line          # 引用 A00 同一個狀態文字
    assert "持倉 0" not in visible(html) and "持倉0" not in visible(html) and not re.search(r"[0-9]", visible(html))


@pytest.mark.parametrize("name", A50_SCENARIOS)
def test_holding_id_and_policy_and_cost_never_reach_the_dom_and_rows_are_keyed_by_ordinal(name):
    model = model_of(name)
    html = html_of(name)
    for row in model.a50.rows:
        assert row.holding_id not in html
    for token in ("holding_id", "holding-id", "policy_id", "FAKE-POLICY", "cost_", "|1", "data-key", "data-id", "id="):
        assert token not in html, token
    for sentinel in (sup.SENTINEL_COST_TWD, sup.SENTINEL_COST_ORIG, sup.SENTINEL_HOLDING_VALUE):
        assert str(sentinel) not in html


def test_missing_values_show_the_approved_missing_status_never_zero_or_blank():
    model = model_of("partial")
    html = html_of("partial")
    rows = re.findall(r'<div class="uv3-a50-row" data-row="(\d+)">(.*?)</div></div>(?=<div class="uv3-a50-row"|</div></details>)', html)
    assert len(rows) == 2
    assert 'data-field="fund_name"><span class="uv3-label"><span class="uv3-pending" data-pending-wording="a50_col_fund_name">基金名稱</span></span>' \
           '<span class="uv3-st uv3-st-' in rows[0][1]
    for ordinal, field in ((0, "fund_name"), (1, "units_shares")):
        cell = re.search(rf'data-field="{field}">(.*?)</div>', rows[ordinal][1] + "</div>").group(1)
        assert 'data-status-key="missing"' in cell and rules.entry("missing").wording in visible(cell), field
        assert not re.search(r">\s*0\s*<", cell) and visible(cell).strip().endswith(rules.entry("missing").wording)
    assert {f.field_code: f.state for f in model.a50.rows[0].facts}["fund_name"] == vm.ROW_STATE_MISSING


def test_a50_values_are_escaped_and_whitespace_never_produces_a_blank_line():
    html = html_of("many_rows")
    assert "<b>" not in html and "<script" not in html and "</script>" not in html
    assert "&lt;b&gt;基金&lt;/b&gt;" in html and "&amp;" in html and "&quot;引號&quot;" in html
    weird = sup.complete_result(1)
    weird["evidence"]["holdings"][0]["fund_name"] = "第一行\n\n第二行\t  末尾<i>"
    page = assets.page_html(build_assets_page(weird))
    assert "\n" not in page and "第一行 第二行 末尾&lt;i&gt;" in page      # 空白摺成單一空格：不產生空行（空行會截斷 Markdown 的 HTML 區塊）
    assert "\n\n" not in html


def test_units_shares_are_the_original_value_as_text_without_thousands_separator_or_conversion():
    result = sup.complete_result(2)
    result["evidence"]["holdings"][0]["units_shares"] = 1234567.5
    result["evidence"]["holdings"][1]["units_shares"] = 1000.0
    a50 = split_a50(assets.page_html(build_assets_page(result)))[1]
    values = re.findall(r'data-field="units_shares"><span class="uv3-label">.*?</span></span>(.*?)</div>', a50)
    assert values == ["1234567.5", "1000.0"] and "," not in "".join(values)   # 顯示格式未裁：原值字串（暫行）


def test_fifty_rows_are_all_present_and_the_container_scrolls_instead_of_truncating():
    html = html_of("many_rows")
    assert html.count('class="uv3-a50-row"') == 50 and html.count('data-field="fund_code"') == 50
    assert re.search(r"\.uv3-a50-body\{[^}]*max-height:[^;}]+;[^}]*overflow-y:auto", assets.CSS)
    assert "text-overflow" not in assets.CSS and "line-clamp" not in assets.CSS


def test_a50_summary_css_sets_the_touch_target_min_height():
    from ui_v3.shell import nav

    assert re.search(rf"\.uv3-a50 > summary,\.uv3-a60 > summary\{{[^}}]*min-height:{nav.TOUCH_MIN_PX}px", assets.CSS)   # A50 與 A60 的摘要共用同一條規則


def test_a50_renderer_rejects_a_field_it_does_not_know_instead_of_guessing():
    row = vm.HoldingRow(1, (vm.RowFact("cost_twd", vm.ROW_STATE_PRESENT, "x", None),), "FAKE-ID-1")
    with pytest.raises(ValueError):
        assets.a50_row_html(row)


def test_same_fund_two_policies_draws_two_rows_with_the_same_fund_code():
    html = html_of("same_fund_two_policies")
    assert html.count('class="uv3-a50-row"') == 2 and html.count("FK0001") == 2
    assert "FAKE-POLICY" not in html and "合併" not in visible(html)


def test_limit_line_uses_the_customer_specified_pending_wording_in_every_scenario():
    for name in ALL:
        html = html_of(name)
        limit = re.search(r'data-a10="limit">(.*?)</div>', html).group(1)
        assert visible(limit).strip() == "此預覽不提供匯率換算或跨幣別合計", name
    assert "此預覽不提供匯率換算或跨幣別合計" not in {a.text for a in rules.APPROVED_WORDING.values()}


def _structure_problems(a50_html_text):
    """A50 結構判定（與 `test_a50_is_exactly_one_collapsed_details…` 同一組規則的純字串版，供負控使用）。"""
    bad = []
    if a50_html_text.count("<details") != 1 or a50_html_text.count("</details>") != 1 or a50_html_text.count("<summary") != 1:
        bad.append("count")
    if re.search(r"<details[^>]*\sopen[\s>=]", a50_html_text):
        bad.append("open")
    inner = a50_html_text[a50_html_text.index("<details") + 1:] if "<details" in a50_html_text else ""
    if "<details" in inner:
        bad.append("nested")
    return bad


def test_structure_checker_is_green_on_the_real_page_and_red_on_injected_mutations():
    html = split_a60(html_of("multi_currency"))[0]
    assert _structure_problems(html) == []
    assert "count" in _structure_problems(html + html[html.index("<details"):])                            # 第二個 <details>
    assert "open" in _structure_problems(html.replace("<details class", "<details open class", 1))          # 注入 open
    nested = html.replace('<div class="uv3-a50-body"', '<details><summary>x</summary>y</details><div class="uv3-a50-body"', 1)
    assert {"count", "nested"} <= set(_structure_problems(nested))                                          # 巢狀 <details>


@pytest.mark.parametrize("name,raw,shown", [
    ("ideographic_space", "甲\u3000乙", "甲 乙"),
    ("nbsp", "\u00a0甲\u00a0\u00a0乙\u00a0", "甲 乙"),
    ("leading_trailing", "  甲  ", "甲"),
])
def test_value_whitespace_folding_is_not_verbatim_locked_as_is(name, raw, shown):
    """現況：`str.split()` 會把 U+3000、NBSP 等也摺成 ASCII 空格並修剪頭尾——畫面值不是逐字原值（已於 README 揭露；是否改為保留由客戶決定）。"""
    result = sup.complete_result(1)
    result["evidence"]["holdings"][0]["fund_name"] = raw
    a50 = split_a50(assets.page_html(build_assets_page(result)))[1]
    assert re.search(r'data-field="fund_name"><span class="uv3-label">.*?</span></span>(.*?)</div>', a50).group(1) == shown


# ───────────────────────── A60：來源與缺項證據（DEC-2026-11-17-01，D1～D8） ─────────────────────────
# A60＝A50 之後的獨立 `<details>`（預設收合、並列、不巢狀、不標首屏）；只呈現略過分頁數／略過列數／依來源狀態的暫行說明／既有 (a) 原因。
# 全部資料是 FAKE；字樣皆 PendingWording；不進規則表。

# 情境 → (略過分頁數, 略過列數, A60 說明採用的狀態)
A60_EXPECT = {
    "multi_currency": (0, 0, "undetermined"), "complete_no_rows": (0, 0, "complete_no_rows"), "market_blocked": (None, None, "undetermined"),
    "partial": (1, 2, "partial"), "no_active": (None, None, "undetermined"), "read_failed": (None, None, "read_failed"),
    "unprovided_skip_evidence": (0, None, "undetermined"), "same_fund_two_policies": (0, 0, "undetermined"), "many_rows": (0, 0, "undetermined"),
    "a60_sensitive_strings": (1, 2, "partial"), "complete_counts_unprovided": (None, None, "undetermined"),
}
_A60_STATE_KEY = {"read_failed": "a60_state_read_failed", "partial": "a60_state_partial", "complete_no_rows": "a60_state_complete_no_rows"}
_A60_FORBIDDEN_KEYS = ("a60_state_complete", "a60_state_not_selected", "a60_state_not_read", "a60_cause_partial")


def a60_of(name):
    return split_a60(html_of(name))[1]


def _page_structure_problems(page, *, with_a50):
    """整頁展開容器結構判定（純字串；供負控）：A50（有列才有）與 A60 各恰一個 `<details>`／`<summary>`、都不 open、互不巢狀、A60 在 A50 之後。"""
    bad = []
    want = 2 if with_a50 else 1
    if not (page.count("<details") == page.count("</details>") == page.count("<summary") == want):
        bad.append("count")
    if re.search(r"<details[^>]*\sopen[\s>=]", page):
        bad.append("open")
    depth = 0
    for m in re.finditer(r"<details|</details>", page):
        depth += 1 if m.group(0) == "<details" else -1
        if depth > 1:
            bad.append("nested")
            break
    if page.count('data-block="a60"') != 1 or page.count('data-block="a50"') != (1 if with_a50 else 0):
        bad.append("blocks")
    if with_a50 and 'data-block="a60"' in page and page.find('data-block="a50"') > page.find('data-block="a60"'):
        bad.append("order")
    if with_a50 and page.find("</details>") > page.find('data-block="a60"'):
        bad.append("a60-inside-a50")
    return bad


@pytest.mark.parametrize("name", ALL)
def test_page_has_a50_and_a60_as_two_sibling_collapsed_details(name):
    assert _page_structure_problems(html_of(name), with_a50=name in A50_SCENARIOS) == []


def test_page_structure_checker_is_red_on_injected_mutations():
    html = html_of("multi_currency")
    assert _page_structure_problems(html, with_a50=True) == []
    a60 = html[html.index(A60_MARK):]
    assert "count" in _page_structure_problems(html + a60, with_a50=True)                                              # 第二個 A60
    assert "open" in _page_structure_problems(html.replace(A60_MARK, '<details open class="uv3-a60"', 1), with_a50=True)   # A60 展開
    assert "nested" in _page_structure_problems(html.replace('data-a60="body">', 'data-a60="body"><details><summary>x</summary>y</details>', 1),
                                                with_a50=True)                                                         # A60 內再巢一個
    assert "count" in _page_structure_problems(split_a60(html)[0], with_a50=True)                                      # 缺 A60
    inner = html.replace('<div class="uv3-a50-body" data-a50="body">', '<div class="uv3-a50-body" data-a50="body">' + a60.replace("</details>", "") + "</details>", 1)
    assert _page_structure_problems(inner, with_a50=True)                                                              # A60 被塞進 A50 內
    assert "count" in _page_structure_problems(html, with_a50=False)                                                   # 沒有 A50 卻有兩個 details


@pytest.mark.parametrize("name", ALL)
def test_a60_shows_integer_counts_as_is_and_missing_counts_as_the_approved_missing_status_never_zero(name):
    tabs, rows, _ = A60_EXPECT[name]
    model = model_of(name)
    assert (model.a60.skipped_tab_count, model.a60.skipped_row_count) == (tabs, rows)   # 前提：情境真的落在預期的件數
    a60 = a60_of(name)
    for code, expected in (("skipped-tabs", tabs), ("skipped-rows", rows)):
        cell = re.search(rf'data-a60="{code}">(.*?)</div>', a60).group(1)
        value = cell.split("</span></span>", 1)[1]
        if expected is None:
            assert 'data-status-key="missing"' in value and rules.entry("missing").wording in visible(value)   # D2：既有 `◇ 資料未備`
            assert not re.search(r"[0-9]", visible(value))
        else:
            assert value == str(expected)   # 0 也照顯示 0（D1）；只是數字，不宣稱完整
    assert re.findall(r"\d+", visible(a60)) == [str(n) for n in (tabs, rows) if n is not None]   # A60 裡的數字只有件數本身


@pytest.mark.parametrize("name", ALL)
def test_a60_state_line_follows_the_source_state_and_the_approved_undetermined_wording_when_evidence_is_short(name):
    state = A60_EXPECT[name][2]
    a60 = a60_of(name)
    line = re.search(r'<div class="uv3-row" data-a60="state" data-a60-state="([a-z_]+)">(.*?)</div>', a60)
    assert line.group(1) == state and a60.count('data-a60="state"') == 1
    if state == "undetermined":
        assert 'data-status-key="undetermined"' in line.group(2) and rules.entry("undetermined").wording in visible(line.group(2))   # D3：證據不足
    else:
        key = _A60_STATE_KEY[state]
        assert f'data-pending-wording="{key}"' in line.group(2) and AW.preview_wording(key).text in visible(line.group(2))


@pytest.mark.parametrize("name", [n for n in ALL if A60_EXPECT[n][2] != "complete_no_rows"])
def test_the_complete_no_rows_sentence_is_absent_unless_the_source_state_is_complete_no_rows(name):
    assert 'data-pending-wording="a60_state_complete_no_rows"' not in a60_of(name)
    assert AW.preview_wording("a60_state_complete_no_rows").text not in visible(html_of(name))


def test_complete_no_rows_sentence_appears_exactly_for_complete_no_rows_with_both_counts_zero():
    html = a60_of("complete_no_rows")
    assert html.count('data-pending-wording="a60_state_complete_no_rows"') == 1 and 'data-a60-state="complete_no_rows"' in html


_COUNT_COMBOS = [(0, 0), (0, None), (None, 0), (None, None), (1, 0), (0, 3), (2, 2)]


@pytest.mark.parametrize("tabs,rows", _COUNT_COMBOS)
@pytest.mark.parametrize("source_state", [vm.SRC_COMPLETE, vm.SRC_COMPLETE_NO_ROWS])
def test_zero_alone_proves_nothing_complete_claims_need_both_counts_to_be_integer_zero(source_state, tabs, rows):
    html = assets.a60_html(vm.A60Evidence(tabs, rows, (), ()), source_state)
    both_zero = (tabs, rows) == (0, 0)
    state = re.search(r'data-a60-state="([a-z_]+)"', html).group(1)
    assert state == ("complete_no_rows" if (both_zero and source_state == vm.SRC_COMPLETE_NO_ROWS) else "undetermined")   # complete（有列）恆為無法判定
    if state == "undetermined":
        assert 'data-pending-wording="a60_state_complete_no_rows"' not in html and 'data-status-key="undetermined"' in html
        assert "完整" not in visible(html) and "沒有可顯示的持倉列" not in visible(html)


@pytest.mark.parametrize("tabs,rows", _COUNT_COMBOS)
def test_partial_needs_at_least_one_positive_count_else_undetermined(tabs, rows):
    html = assets.a60_html(vm.A60Evidence(tabs, rows, (), (vm.CauseFact(vm.CATEGORY_SOURCE_DATA, vm.CAUSE_PARTIAL_SOURCE),)), vm.SRC_PARTIAL)
    positive = (tabs or 0) > 0 or (rows or 0) > 0
    assert ('data-a60-state="partial"' in html) is positive and 'data-pending-wording="a60_cause_partial"' not in html
    assert ('data-a60-state="undetermined"' in html) is (not positive)


@pytest.mark.parametrize("tabs,rows", _COUNT_COMBOS)
@pytest.mark.parametrize("source_state,state", [(vm.SRC_READ_FAILED, "read_failed"), (vm.SRC_NOT_SELECTED, "undetermined"),
                                                (vm.SRC_NOT_READ, "undetermined"), (vm.SRC_UNDETERMINED, "undetermined")])
def test_failure_not_selected_not_read_and_undetermined_never_claim_completeness_whatever_the_counts(source_state, state, tabs, rows):
    html = assets.a60_html(vm.A60Evidence(tabs, rows, (), ()), source_state)
    assert f'data-a60-state="{state}"' in html
    for key in (*_A60_FORBIDDEN_KEYS, "a60_state_complete_no_rows", "a60_state_partial"):
        assert f'data-pending-wording="{key}"' not in html
    if state == "undetermined":
        assert 'data-status-key="undetermined"' in html and rules.entry("undetermined").wording in visible(html)


def test_blocked_and_not_read_never_say_the_source_was_read_to_the_end():
    for name in ("market_blocked", "read_failed", "no_active", "complete_counts_unprovided", "unprovided_skip_evidence"):
        a60 = a60_of(name)
        assert "已完整讀取" not in visible(a60) and "未發現略過" not in visible(a60) and "a60_state_complete" not in a60, name


# ── 防誤判（ChatGPT UI 設計方向 2026-11-17）：件數為 0 不得被讀成「來源完整」；說明句只留四類；blocked／未選定只剩 `⬜ 無法判定` ──
_COMPLETE_CLAIMS = ("完整", "已讀取", "未發現略過", "沒有略過", "無略過")


@pytest.mark.parametrize("name", ["multi_currency", "same_fund_two_policies", "many_rows"])
def test_complete_with_rows_and_zero_counts_never_claims_completeness_only_the_counts_and_undetermined(name):
    a60 = a60_of(name)
    assert A60_EXPECT[name][:2] == (0, 0) and 'data-a60-state="undetermined"' in a60   # 前提：件數 (0,0) 且 complete 有持倉列
    text = visible(a60)
    assert not any(w in text for w in _COMPLETE_CLAIMS) and "沒有可顯示的持倉列" not in text
    assert rules.entry("undetermined").wording in text and 'data-pending-wording="a60_state_' not in a60


@pytest.mark.parametrize("name", ["market_blocked", "no_active"])
def test_blocked_and_not_selected_show_only_undetermined_and_invent_no_cause_sentence(name):
    a60 = a60_of(name)
    assert 'data-a60-state="undetermined"' in a60 and 'data-status-key="undetermined"' in a60
    assert 'data-a60="cause"' not in a60 and 'data-pending-wording="a60_state_' not in a60 and 'data-pending-wording="a60_cause_' not in a60
    # 狀態列只有 `⬜ 無法判定`；整個 A60 不得有除標題說明、欄名、件數外的原因句
    line = re.search(r'data-a60="state"[^>]*>(.*?)</div>', a60).group(1)
    assert visible(line).strip() == rules.entry("undetermined").wording


def test_none_counts_show_missing_never_zero_and_int_zero_shows_zero():
    for name in ("market_blocked", "no_active", "read_failed", "complete_counts_unprovided"):
        a60 = a60_of(name)
        assert "0" not in re.findall(r"\d+", visible(a60)) and visible(a60).count(rules.entry("missing").wording) == 2, name
    a60 = a60_of("complete_no_rows")
    assert re.findall(r"\d+", visible(a60)) == ["0", "0"] and rules.entry("missing").wording not in visible(a60)


def test_mutation_old_complete_claim_is_caught_by_the_guards(monkeypatch):
    """變異：把 complete 改回舊聲稱（兩件數為 0 就說『已完整讀取』）→ 上面的防誤判條件必須轉紅。"""
    original = assets._a60_effective_state

    def old_claim(a60, source_state):
        if source_state == vm.SRC_COMPLETE and (a60.skipped_tab_count, a60.skipped_row_count) == (0, 0):
            return "complete_no_rows"   # 舊行為的等價：宣稱完整
        return original(a60, source_state)

    monkeypatch.setattr(assets, "_a60_effective_state", old_claim)
    a60 = split_a60(assets.page_html(model_of("multi_currency")))[1]
    text = visible(a60)
    assert 'data-a60-state="undetermined"' not in a60 or any(w in text for w in _COMPLETE_CLAIMS) or 'a60_state_' in a60
    assert 'data-a60-state="undetermined"' not in a60   # 守衛條件會因此失敗＝變異被偵測


def test_a60_unknown_source_state_and_wrong_types_fail_loudly():
    evidence = model_of("partial").a60
    with pytest.raises(ValueError):
        assets.a60_html(evidence, "no_such_state")
    with pytest.raises(TypeError):
        assets.a60_html(None, vm.SRC_PARTIAL)
    with pytest.raises(ValueError):
        assets._a60_count_html(True)
    with pytest.raises(ValueError):
        assets._a60_count_html("1")


def test_a60_never_carries_a_category_b_cause_and_unknown_cause_keys_fail_loudly():
    b_cause = vm.CauseFact(vm.CATEGORY_BASIS_NOT_APPROVED, vm.CAUSE_BASIS_NOT_APPROVED)
    with pytest.raises(ValueError):
        vm.A60Evidence(1, 1, (), (b_cause,))   # 契約層就擋
    with pytest.raises(ValueError):
        assets._a60_cause_rows_html((b_cause,), "partial")   # renderer 再擋一次，不畫
    weird = vm.CauseFact(vm.CATEGORY_SOURCE_DATA, vm.CAUSE_PARTIAL_SOURCE)
    object.__setattr__(weird, "cause_key", "no_such_cause")
    with pytest.raises(ValueError):
        assets._a60_cause_rows_html((weird,), "partial")
    for name in ALL:
        assert "計算口徑" not in visible(a60_of(name)) and "basis_not_approved" not in a60_of(name), name


@pytest.mark.parametrize("name", ALL)
def test_a60_output_is_invariant_to_the_category_field(name):
    model = model_of(name)
    before = assets.page_html(model)
    other = {vm.CATEGORY_SOURCE_DATA: vm.CATEGORY_BASIS_NOT_APPROVED, vm.CATEGORY_BASIS_NOT_APPROVED: vm.CATEGORY_SOURCE_DATA}
    for cause in model.a60.causes:
        object.__setattr__(cause, "category", other[cause.category])
    assert assets.page_html(model) == before


def test_partial_has_one_state_sentence_and_no_duplicate_cause_row():
    for name in ("partial", "a60_sensitive_strings"):
        a60 = a60_of(name)
        assert a60.count('data-pending-wording="a60_state_partial"') == 1 and 'data-a60="cause"' not in a60 and "a60_cause_partial" not in a60
    for name in ALL:
        assert 'data-a60="cause"' not in a60_of(name), name


# ── D4／D8：內部碼、略過原始字串、網址、試算表 ID、例外、敏感資訊完全不上畫面 ──

def _internal_tokens(model):
    tokens = set(model.a60.problem_codes) | set(vm.CAUSE_KEYS) | {c.cause_key for c in model.a60.causes}
    for value in (model.a00.failure_code, model.a00.cause_key):
        if value:
            tokens.add(value)
    return tokens


def leaks(html, sentinels):
    """HTML 原樣與 escape 後的形態、可見文字裡出現哨兵 → 回傳命中的哨兵。"""
    from html import escape

    text = visible(html)
    return sorted({s for s in sentinels if s in html or escape(s) in html or s in text})


@pytest.mark.parametrize("name", ALL)
def test_a60_exposes_no_internal_code_sensitive_string_or_percent(name):
    model = model_of(name)
    tokens = _internal_tokens(model) | set(sup.FAKE_SENSITIVE_STRINGS) | {"NETWORK_ERROR", "market_basis", "problem_codes", "cause_key", "failure_code"}
    a60 = a60_of(name)
    assert leaks(a60, tokens) == []
    page_tokens = set(model.a60.problem_codes) | {t for t in (model.a00.failure_code, model.a00.cause_key) if t}
    assert leaks(html_of(name), page_tokens) == []   # 整頁也不得有問題碼、失敗代碼、市值基準被擋的原因碼
    assert "%" not in a60 and "％" not in a60 and "<script" not in a60 and "href" not in a60 and "<a " not in a60


def test_sensitive_scenario_really_carries_the_sentinels_in_the_input_and_the_model_has_problem_codes():
    result = sup.a60_sensitive_strings_result()
    raw = repr(result)
    assert sup.FAKE_SENSITIVE_SHEET_ID in raw and "docs.google.com" in raw and "Traceback" in raw   # 正控：輸入裡真的有，所以「畫面沒有」不是空綠
    model = build_assets_page(result)
    assert model.a60.problem_codes == sup.FAKE_A60_PROBLEM_CODES and model.a60.skipped_tab_count == 1 and model.a60.skipped_row_count == 2
    html = assets.page_html(model)
    assert leaks(html, set(sup.FAKE_SENSITIVE_STRINGS) | set(sup.FAKE_A60_PROBLEM_CODES)) == []


def test_read_failed_sensitive_failure_code_and_exception_text_never_reach_the_page():
    code = f"{sup.FAKE_SENSITIVE_URL} {sup.FAKE_SENSITIVE_EXCEPTION}"
    model = build_assets_page(sup.read_failed_result(code))
    assert model.a00.failure_code == code   # VM 有、畫面不得有
    html = assets.page_html(model)
    assert leaks(html, set(sup.FAKE_SENSITIVE_STRINGS) | {"holding_read_failed"}) == []


def test_leak_checker_negative_control_turns_red():
    html = html_of("a60_sensitive_strings")
    assert leaks(html + f"<div>{sup.FAKE_SENSITIVE_URL}</div>", sup.FAKE_SENSITIVE_STRINGS)
    assert leaks(html + "<div>&lt;Traceback&gt;</div>", ["<Traceback>"])
    assert leaks(html.replace("</details>", f"{sup.FAKE_A60_PROBLEM_CODES[0]}</details>"), sup.FAKE_A60_PROBLEM_CODES)
    assert leaks(a60_of("partial"), [str(1)]) == ["1"]   # 檢查器本身能抓到可見文字裡的內容


_INTERNAL_NAMES = ("problem_codes", "failure_code")


def internal_code_reads(source):
    """原始碼中對內部碼欄位的任何讀取或引用：屬性、名稱、字串常數、getattr、asdict／vars／__dict__。"""
    hits = []
    for n in ast.walk(ast.parse(source)):
        if isinstance(n, ast.Attribute) and (n.attr in _INTERNAL_NAMES or n.attr in ("__dict__", "asdict")):
            hits.append(f".{n.attr}")
        elif isinstance(n, ast.Name) and (n.id in _INTERNAL_NAMES or n.id in ("asdict", "vars")):
            hits.append(n.id)
        elif isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value in _INTERNAL_NAMES:
            hits.append(repr(n.value))
        elif isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "getattr" and len(n.args) > 1 \
                and isinstance(n.args[1], ast.Constant) and n.args[1].value in _INTERNAL_NAMES:
            hits.append("getattr")
    return hits


def test_renderer_source_never_reads_problem_codes_or_failure_code():
    assert internal_code_reads(RENDERER_SRC) == []


@pytest.mark.parametrize("snippet", ["x = a60.problem_codes\n", "y = a00.failure_code\n", "z = getattr(a60, 'problem_codes')\n",
                                     "w = d['failure_code']\n", "v = dataclasses.asdict(a60)\n", "u = vars(a60)\n", "t = a60.__dict__\n"])
def test_negative_control_internal_code_checker_turns_red(snippet):
    assert internal_code_reads(snippet)


A60_STATE_DOMAIN = {"read_failed", "partial", "complete_no_rows", "undetermined"}   # 測試屬性，不是使用者可見的正式狀態契約


def test_a60_state_attribute_domain_is_closed_over_scenarios_and_count_matrix():
    seen = set()
    for name in ALL:
        seen.add(re.search(r'data-a60-state="([^"]*)"', a60_of(name)).group(1))
    states = (vm.SRC_COMPLETE, vm.SRC_PARTIAL, vm.SRC_NOT_SELECTED, vm.SRC_READ_FAILED, vm.SRC_COMPLETE_NO_ROWS, vm.SRC_UNDETERMINED, vm.SRC_NOT_READ)
    for state in states:
        for tabs, rows in _COUNT_COMBOS:
            html = assets.a60_html(vm.A60Evidence(tabs, rows, (), ()), state)
            seen.add(re.search(r'data-a60-state="([^"]*)"', html).group(1))
    assert seen <= A60_STATE_DOMAIN and seen == A60_STATE_DOMAIN   # 值域只能是這四個，且四個都有被走到（不是空綠）


# ── D6：新增字樣全是 PendingWording，不進規則表 ──

def test_every_a60_wording_is_pending_and_none_is_in_the_approved_table():
    keys = [k for k in AW.ASSETS_PREVIEW_WORDING if k.startswith("a60_")]
    assert set(keys) == {"a60_title", "a60_labels_note", "a60_label_skipped_tabs", "a60_label_skipped_rows", "a60_state_read_failed", "a60_state_partial",
                         "a60_state_complete_no_rows"}
    for key in keys:
        item = AW.preview_wording(key)
        assert item.status == "pending" and item.source.strip()
        assert key == "a60_labels_note" or "DEC-2026-11-17-01" in item.source or "ChatGPT UI 設計方向 2026-11-17" in item.source
        assert "客戶逐字" not in item.source.replace("非客戶逐字裁示", "")   # 出處不得寫成客戶裁示
        assert key not in rules.ENTRIES and key not in rules.APPROVED_WORDING
        assert item.text not in {a.text for a in rules.APPROVED_WORDING.values()}


@pytest.mark.parametrize("name", ALL)
def test_a60_text_is_only_pending_spans_approved_status_and_counts(name):
    a60 = a60_of(name)
    rest = re.sub(r'<span class="uv3-pending" data-pending-wording="[a-z0-9_]+">.*?</span>', "", a60)
    rest = re.sub(r'<span class="uv3-st uv3-st-[a-z]+" data-status-key="[a-z_]+">.*?</span>', "", rest)
    assert re.fullmatch(r"[0-9\s]*", visible(rest)), visible(rest)   # 剩下的可見文字只有件數數字
    keys = re.findall(r'data-pending-wording="([^"]+)"', a60)
    assert keys and all(k in AW.ASSETS_PREVIEW_WORDING for k in keys)
    assert set(re.findall(r'data-status-key="([^"]+)"', a60)) <= {"missing", "undetermined"}   # 只用兩個已核准狀態字樣


def test_a60_labels_note_is_visible_inside_the_collapsed_container_not_in_a_new_first_screen_element():
    a60 = a60_of("multi_currency")
    assert 'data-a60="labels-note"' in a60 and "暫行字樣，尚未核准" in visible(a60) and "data-first-screen" not in a60
