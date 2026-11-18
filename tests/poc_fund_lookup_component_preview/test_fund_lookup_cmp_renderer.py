# -*- coding: utf-8 -*-
"""單檔基金查詢呈現元件 隔離式 FAKE Preview：renderer 純函式單元測試（不開 Streamlit、不開瀏覽器）。

ViewModel 一律由 FakeLoader 經 adapter 產生（CONFLICT 與名稱含特殊字元者以直接建構演示，註明現行 L2 不可達）。負控／變異一律在記憶體內現編。
"""
from __future__ import annotations

import re

import pytest

import fund_lookup_cmp_support as S

import fund_lookup_fake_inputs as fake  # noqa: E402
import fund_lookup_renderer as R  # noqa: E402
import fund_lookup_wording as W  # noqa: E402
from shared.ui_semantics import rules  # noqa: E402
from ui_v3.adapters.fund_lookup import lookup_fund, not_queried  # noqa: E402
from ui_v3.viewmodels import fund_lookup as VM  # noqa: E402


def _html(raw, fake_flag=True):
    return R.lookup_card_html(lookup_fund(fake.make_loader(), raw), fake=fake_flag)


def test_the_full_battery_passes_on_the_production_renderer():
    assert S.battery(R) == []


def test_the_battery_is_not_vacuous_it_covers_every_state_and_every_reason_code_except_conflict_via_the_adapter():
    seen = set()
    for _label, view in S.build_views():
        seen.add((view.state, view.reason_code))
    reasons = {r for (_s, r) in seen}
    assert reasons >= (VM.BLOCKED_REASONS | VM.SOURCE_FAILED_REASONS | VM.PAGE_UNMATCHED_REASONS)
    assert {s for (s, _r) in seen} == set(VM.LookupState)


def test_every_reason_code_has_its_own_wording_key_in_the_wording_table():
    for r in VM.SOURCE_FAILED_REASONS:
        assert f"failed_{r}" in W.FUND_LOOKUP_PENDING
    for r in VM.PAGE_UNMATCHED_REASONS:
        assert f"unmatched_{r}" in W.FUND_LOOKUP_PENDING
    for r in VM.BLOCKED_REASONS:
        assert f"blocked_{r}" in W.FUND_LOOKUP_PENDING


def test_idle_card_shows_only_not_queried_and_no_field_rows():
    html = R.lookup_card_html(not_queried(), fake=True)
    assert S.text_of(html).strip() == W.text("not_queried") == "尚未查詢"
    assert 'data-state="idle"' in html and "data-row=\"input-code\"" not in html and 'data-tag="fake"' not in html and "<dl" not in html


@pytest.mark.parametrize("raw,names", [("FAKE-OK01", list(S.FIVE_ROWS)), ("FAKE-OK02", list(S.FIVE_ROWS)), ("FAKE-OK03", list(S.FIVE_ROWS)),
                                       ("FAKE-FAIL1", ["input-code"]), ("FAKE-PAGE1", ["input-code"]), ("FAKE-REJ1", ["input-code"]),
                                       ("   ", []), ("US0378331005", []), ("http://x.example/a", []), ("A<B>C", ["input-code"])])
def test_field_rows_are_exactly_the_five_in_order_for_result_and_at_most_the_input_code_otherwise(raw, names):
    html = _html(raw)
    assert S.row_names(html) == names and S.field_violations(html) == []


def test_result_fields_use_the_five_labels_in_order_and_no_unapproved_field_appears():
    html = _html("FAKE-OK01")
    labels = [S.text_of(x).strip() for x in re.findall(r"<dt[^>]*>(.*?)</dt>", html, re.S)]
    assert labels == list(S.FIVE_LABELS)
    assert S.forbidden_word_violations(html) == []
    for token in ("ccy", "fetched_at", "Provider", "NAV", "淨值", "報酬", "績效", "幣別", "取得時間", "資料日", "來源等級", "供應者"):
        assert token not in html, token


def test_field_values_missing_conflict_and_value_are_distinct_and_never_zero_or_none_words():
    ok1, ok2, ok3 = _html("FAKE-OK01"), _html("FAKE-OK02"), _html("FAKE-OK03")
    assert "2000-01-02" in ok1 and "配息型" in ok1 and "此欄尚無可顯示的值" in ok1
    assert "累積型" in ok2 and 'data-row="inception" data-field-status="missing"' in ok2
    assert 'data-row="dividend-mode" data-field-status="missing"' in ok3 and 'data-row="mgmt-fee" data-field-status="missing"' in ok3
    conflict = R.lookup_card_html(fake.conflict_view(), fake=True)
    assert conflict.count('data-field-status="conflict"') == 2 and W.text("field_conflict") in S.text_of(conflict)
    assert W.text("field_conflict") != W.text("field_missing")
    for html in (ok1, ok2, ok3, conflict):
        for row in ("dividend-mode", "inception", "mgmt-fee"):
            cell = S._row_text(html, row)
            assert cell not in ("0", "無", "不配息", "-", "—", "")


def test_management_fee_is_always_missing_in_a_result_because_the_contract_has_no_source():
    for raw in ("FAKE-OK01", "FAKE-OK02", "FAKE-OK03"):
        assert 'data-row="mgmt-fee" data-field-status="missing"' in _html(raw)


def test_the_fake_tag_is_exactly_one_and_before_every_status_line_and_field_row_and_it_is_optional():
    for raw in S.ADAPTER_INPUTS:
        assert S.fake_tag_order_violations(_html(raw)) == [], raw
        assert 'data-tag="fake"' not in _html(raw, fake_flag=False), raw
    assert S.fake_tag_order_violations("<div><dl><div data-row=\"name\"></div></dl><span data-tag=\"fake\"></span></div>")        # 負控
    assert S.fake_tag_order_violations("<div>no tag</div>")                                                                      # 負控


@pytest.mark.parametrize("raw,state", [("FAKE-FAIL1", "failed"), ("FAKE-COOL1", "failed"), ("FAKE-IOERR", "failed"),
                                       ("FAKE-PAGE1", "unmatched"), ("FAKE-PAGE2", "unmatched"), ("FAKE-PAGE3", "unmatched"), ("FAKE-NAME1", "unmatched"),
                                       ("ABC123", "unmatched"), ("FAKE-REJ1", "blocked"), ("   ", "blocked"), ("US0378331005", "blocked"),
                                       ("http://x.example/a", "blocked"), ("A<B>C", "blocked"), ("FAKE-OK01", "result")])
def test_each_state_has_its_own_wording_and_never_says_the_fund_does_not_exist(raw, state):
    html = _html(raw)
    visible = S.text_of(html)
    assert f'data-state="{state}"' in html
    for w in ("基金不存在", "查無", "不存在", "沒有這檔", "無此基金", "找不到基金"):
        assert w not in visible, (raw, w)
    if state == "failed":
        assert rules.entry("fetch_failed").wording in visible and rules.entry("undetermined").wording not in visible
        assert W.text("not_identity") in visible and 'role="alert"' in html
    elif state == "unmatched":
        assert rules.entry("undetermined").wording in visible and rules.entry("fetch_failed").wording not in visible
        assert W.text("not_identity") in visible
    elif state == "blocked":
        assert W.text("blocked_impact") in visible and 'role="alert"' in html
        assert rules.entry("fetch_failed").wording not in visible and rules.entry("undetermined").wording not in visible
    else:
        assert W.text("state_result") in visible and 'role="status"' in html


def test_blocked_inputs_are_never_echoed_and_the_loader_is_not_called_for_them():
    for raw in S.NEVER_ECHO_INPUTS:
        loader = fake.make_loader()
        view = lookup_fund(loader, raw)
        assert view.state is VM.LookupState.BLOCKED and view.input_code is None and loader.calls == []
        assert raw.strip() not in S.text_of(R.lookup_card_html(view, fake=True))
    loader = fake.make_loader()
    assert lookup_fund(loader, "   ").input_code == "   " and loader.calls == []
    assert S.row_names(_html("   ")) == []                                       # 全空白輸入不畫輸入代碼列


def test_user_controlled_text_is_escaped_in_the_input_code_and_the_fund_name():
    html = _html("A<B>C")
    shown = re.sub(r"</?span[^>]*>", "", S._row_value_html(html, "input-code"))
    assert "&lt;B&gt;" in shown and S.special_char_violations(shown) == [] and S.raw_script_violations(html) == []
    name_view = dict(S.build_views())["nasty-name"]
    name_html = S._row_value_html(R.lookup_card_html(name_view, fake=True), "name")
    assert "&lt;b&gt;" in name_html and "&#36;" in name_html and "&#92;" in name_html and "&amp;amp;" in name_html and S.special_char_violations(name_html) == []
    assert R.safe("a\nb\r$\\<>\"'&") == "a&#10;b&#13;&#36;&#92;&lt;&gt;&quot;&#x27;&amp;"


def test_safe_is_total_over_nasty_inputs():
    for raw in S.NASTY_INPUTS:
        out = R.safe(raw)
        assert S.special_char_violations(out) == [], raw


def test_status_symbols_and_wording_come_from_the_rules_table_via_its_api():
    html = _html("FAKE-FAIL1")
    entry = rules.entry("fetch_failed")
    assert f'<span class="uv3-st uv3-st-{entry.tone}" data-status-key="fetch_failed">{entry.wording}</span>' in html
    undet = rules.entry("undetermined")
    assert f'data-status-key="undetermined">{undet.wording}</span>' in _html("FAKE-PAGE1")
    for bad in ("missing", "ok", "attention", "stale", "not_configured", "no_such_key"):
        with pytest.raises(KeyError):
            W.status(bad)


def test_non_view_input_is_rejected_loudly():
    for bad in (None, "FAKE-OK01", {"state": "result"}, 3):
        with pytest.raises(TypeError):
            R.lookup_card_html(bad, fake=True)


def test_unknown_wording_keys_are_errors_not_guesses():
    for fn in (W.text, W.pending):
        with pytest.raises(KeyError):
            fn("no_such_key")


def test_isin_note_is_always_present_symbol_free_and_marked_pending():
    note = R.isin_note_html()
    assert 'data-block="isin-note"' in note and 'data-pending-wording="isin_note"' in note
    assert not any(c in W.text("isin_note") for c in "◆◇⬜⛔◷✓✕▲◌")


def test_rendering_is_deterministic_and_does_not_mutate_the_view():
    view = lookup_fund(fake.make_loader(), "FAKE-OK01")
    a, b = R.lookup_card_html(view, fake=True), R.lookup_card_html(view, fake=True)
    assert a == b and view == lookup_fund(fake.make_loader(), "FAKE-OK01")


def test_fake_loader_records_calls_and_unlisted_codes_are_page_not_found_never_existence_claims():
    loader = fake.make_loader()
    view = lookup_fund(loader, "ZZZ999")
    assert loader.calls == ["ZZZ999"] and view.state is VM.LookupState.PAGE_UNMATCHED and view.reason_code == "no_page"


def test_css_colors_are_exactly_token_values_and_the_touch_target_floor_is_48px():
    from ui_v3.design import tokens
    palette = {v.lower() for v in tokens.PALETTE.values()}
    for tone in tokens.TONE_KEYS:
        palette |= {v.lower() for v in tokens.value(f"color.tone.{tone}").values()}
    used = {c.lower() for c in re.findall(r"#[0-9a-fA-F]{6}\b", R.CSS)}
    assert used and used <= palette, used - palette
    assert re.search(r'\[data-testid="stFormSubmitButton"\] button\{min-height:48px;min-width:48px\}', R.CSS)
    assert re.search(r'\[data-testid="stTextInput"\] input\{min-height:48px', R.CSS)
    assert "outline:2px solid" in R.CSS and ":focus-visible" in R.CSS
