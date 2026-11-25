# -*- coding: utf-8 -*-
"""🔍 找基金 NAV／輔助判定 sibling：renderer 離線測試（HTML 純函式；零網路；A-EXP-NAV-SIBLING-FAKE-1）。

驗收重點（#7131285515 §4）：五欄 DOM 不變；扣下時無任何淨值數字；三種結果互斥；時間欄位不互相代填；
R4 單獨拒絕不改主畫面；OneBrain 槽恆未啟用；renderer 不計算。所有負控在記憶體內現編。
"""
from __future__ import annotations

import re

import pytest

import ui_v3.fixtures.exp_lookup_fake as fake
from ui_v3.adapters.exp_nav import load_exp_nav
from ui_v3.adapters.fund_lookup import lookup_fund
from ui_v3.pages import exp_lookup as R
from ui_v3.viewmodels import exp_nav as M

FIVE_ROWS = ["input-code", "name", "dividend-mode", "inception", "mgmt-fee"]


def _card(code: str, *, with_nav: bool = True) -> str:
    view = lookup_fund(fake.make_loader(), code)
    nav = load_exp_nav(fake.make_nav_loader(), code) if with_nav else None
    return R.lookup_card_html(view, fake=True, nav=nav)


def _text(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html).replace("&#36;", "$"))


def _rows(html: str) -> list:
    return re.findall(r'data-row="([a-z-]+)"', html)


def _judgements(html: str) -> dict:
    """{metric: (data-judgement, 該列文字)}；只取 `data-block="judgement"` 區，以 `fl-judge` 起頭切段。"""
    block = html.split('data-block="judgement"', 1)[1].split("</section>", 1)[0]
    out = {}
    for chunk in block.split('<span class="fl-judge"')[1:]:
        kind = re.search(r'data-judgement="([a-z-]+)"', chunk).group(1)
        metric = re.search(r'data-metric="([a-z0-9]+)"', chunk).group(1)
        out[metric] = (kind, _text(chunk.split(">", 1)[1]))
    return out


NAV_VALUES = ("12.3456",)      # 合成淨值（測試內現編的負控字串；不落文件）


# ───────────────────────── 五欄不變 ─────────────────────────

@pytest.mark.parametrize("code", sorted(c for c in fake.DEMO_CODES if c.startswith("FAKE-ZZ")))
def test_five_rows_keep_their_order_and_come_before_the_sibling_blocks(code):
    html = _card(code)
    rows = _rows(html)
    assert [r for r in rows if r in FIVE_ROWS] == FIVE_ROWS
    assert html.index('data-row="mgmt-fee"') < html.index('data-block="nav"') < html.index('data-block="judgement"') < html.index('data-note="single"')


@pytest.mark.parametrize("code", ["FAKE-OK01", "FAKE-OK02", "FAKE-OK03", "FAKE-ZZC1", "FAKE-ZZC3A"])
def test_the_five_row_html_is_byte_identical_with_and_without_the_sibling(code):
    with_nav, without = _card(code), _card(code, with_nav=False)
    five_with = re.search(r'<dl class="fl-list" data-block="rows">.*?</dl>', with_nav, re.S).group(0)
    five_without = re.search(r'<dl class="fl-list" data-block="rows">.*?</dl>', without, re.S).group(0)
    assert five_with == five_without


@pytest.mark.parametrize("code", ["FAKE-FAIL1", "FAKE-PAGE2", "FAKE-OK01", "FAKE-IOERR"])
def test_states_without_a_sibling_render_exactly_as_before(code):
    view = lookup_fund(fake.make_loader(), code)
    assert R.lookup_card_html(view, fake=True, nav=None) == R.lookup_card_html(view, fake=True)
    assert 'data-block="nav"' not in _card(code)


def test_a_non_result_state_ignores_a_supplied_sibling():
    view = lookup_fund(fake.make_loader(), "FAKE-FAIL1")
    nav = load_exp_nav(fake.make_nav_loader(), "FAKE-ZZ10B")
    assert R.lookup_card_html(view, fake=True, nav=nav) == R.lookup_card_html(view, fake=True)


# ───────────────────────── 扣下：無淨值數字、兩判定無法判定 ─────────────────────────

@pytest.mark.parametrize("code", ["FAKE-ZZC1", "FAKE-ZZC1B", "FAKE-ZZ10A"])
def test_withheld_cards_show_no_nav_value_and_no_verdict_symbols(code):
    html = _card(code)
    text = _text(html)
    for value in NAV_VALUES:
        assert value not in html
    assert "✅" not in text and "❌" not in text
    j = _judgements(html)
    assert j["333"][0] == "undetermined" and j["eating"][0] == "undetermined"
    assert 'data-row="nav-value"' not in html and 'data-row="nav-date"' not in html


def test_conflict_card_lists_the_two_dates_for_t1_and_only_the_structure_for_t0():
    html = _card("FAKE-ZZC1")
    assert "2011-11-18" in html and "2020-02-03" in html and 'data-nav-display="withheld_conflict"' in html
    n = load_exp_nav(fake.make_nav_loader(), "FAKE-ZZC1")
    t0 = M.ExpNavView(M.NavSummaryView(**{**{f: getattr(n.nav, f) for f in n.nav.__dataclass_fields__}, "content_tier": "T0"}), n.judgement)
    html0 = R.lookup_card_html(lookup_fund(fake.make_loader(), "FAKE-ZZC1"), fake=True, nav=t0)
    assert "2011-11-18" not in html0 and 'data-nav-display="withheld_conflict"' in html0


def test_one_dash_zero_a_is_withheld_for_the_class_not_for_a_date_conflict():
    html = _card("FAKE-ZZ10A")
    assert 'data-nav-display="withheld_not_admitted"' in html
    assert "2011-11-18" not in html                                    # 日期矛盾已不存在，不顯示診斷日期
    assert "基金級別尚未核證" in _text(html)


def test_one_dash_zero_b_shows_the_nav_and_both_evidenced_passes():
    html = _card("FAKE-ZZ10B")
    assert "12.3456" in html and 'data-nav-display="verified"' in html
    j = _judgements(html)
    assert j["333"][0] == "pass-evidenced" and j["eating"][0] == "pass-evidenced"
    assert "9.00%" in j["333"][1] and "5.00%" in j["eating"][1]


# ───────────────────────── 三種結果互斥、獨立 ─────────────────────────

def test_c2_missing_dividends_shows_neither_a_verdict_nor_a_dividend_fact_nor_the_naive_annualised_figure():
    html = _card("FAKE-ZZC2")
    text = _text(html)
    j = _judgements(html)
    assert j["333"][0] == "undetermined" and j["eating"][0] == "undetermined"
    assert "配息資料未取得" in j["333"][1] and "配息資料未取得" in j["eating"][1]
    assert "無配息（事實）" not in text and "吃本金：不適用" not in text
    assert "✅" not in text and "❌" not in text and "8.0" not in text
    assert 'data-dividend="missing"' in html


def test_c2b_keeps_the_independent_years_below_three_counter_evidence():
    j = _judgements(_card("FAKE-ZZC2B"))
    assert j["333"][0] == "fail-evidenced" and "❌" in j["333"][1] and "2.0 年" in j["333"][1]
    assert j["eating"][0] == "undetermined" and "❌" not in j["eating"][1]


def test_c3a_separates_evidenced_fail_from_the_no_dividend_fact():
    html = _card("FAKE-ZZC3A")
    j = _judgements(html)
    assert j["333"][0] == "fail-evidenced" and "❌" in j["333"][1] and "6.00%" in j["333"][1]
    kind, text = j["eating"]
    assert kind == "fact-no-dividend" and "無配息（事實）" in text and "吃本金：不適用" in text
    assert not any(sym in text for sym in ("✅", "❌", "⬜"))
    assert 'data-dividend="confirmed_none"' in html


def test_c3b_and_c3d():
    j = _judgements(_card("FAKE-ZZC3B"))
    assert j["333"][0] == "undetermined" and j["eating"][0] == "fact-no-dividend"      # 兩者互不頂替
    j = _judgements(_card("FAKE-ZZC3D"))
    assert j["333"][0] == "undetermined" and j["eating"][0] == "undetermined"
    assert "無配息（事實）" not in _text(_card("FAKE-ZZC3D"))                            # 證據只有一半 → 不得顯示無配息


@pytest.mark.parametrize("code", sorted(c for c in fake.DEMO_CODES if c.startswith("FAKE-ZZ")))
def test_symbols_are_exclusive_to_their_judgement_kind(code):
    for _metric, (kind, text) in _judgements(_card(code)).items():
        assert ("❌" in text) == (kind == "fail-evidenced")
        assert ("✅" in text) == (kind == "pass-evidenced")
        assert ("⬜" in text) == (kind == "undetermined")


def test_r3_only_keeps_the_nav_but_withholds_both_judgements():
    html = _card("FAKE-ZZR3")
    assert "12.3456" in html
    j = _judgements(html)
    assert j["333"][0] == "undetermined" and "衍生計算權利未核證" in j["333"][1]


def test_r4_only_leaves_the_main_screen_unchanged():
    base, r4 = _card("FAKE-ZZ10B"), _card("FAKE-ZZR4")
    note = re.search(r'<div class="uv3-note" data-note="ai-unusable">.*?</div>', r4, re.S)
    assert note and "AI 使用權：未核證" in note.group(0) and "ai-unusable" not in base
    normalise = lambda h: h.replace("FAKE-ZZR4", "CODE").replace("FAKE-ZZ10B", "CODE")
    assert normalise(r4.replace(note.group(0), "")) == normalise(base)


# ───────────────────────── 時間欄位 ─────────────────────────

@pytest.mark.parametrize("code", sorted(c for c in fake.DEMO_CODES if c.startswith("FAKE-ZZ")))
def test_times_are_labelled_per_field_and_never_as_a_bare_fetch_time(code):
    html = _card(code)
    text = _text(html)
    assert "取得時間" not in text
    assert 'data-row="nav-cache-at"' in html and 'data-row="nav-supplier-at"' in html and 'data-row="ccy-declared-at"' in html
    assert "資料時間不同：依欄位分別標示" in text


def test_supplier_time_is_shown_as_unknown_for_cache_only_cases_and_as_a_value_when_given():
    unknown = _card("FAKE-ZZC2")
    assert re.search(r'data-row="nav-supplier-at".*?data-kind="unknown"', unknown, re.S)
    known = _card("FAKE-ZZC3A")
    assert 'data-row="nav-supplier-at"' in known and not re.search(r'data-row="nav-supplier-at".*?data-kind="unknown"', known.split('data-row="nav-supplier-at"')[1].split("</div>")[0], re.S)


def test_every_sibling_card_keeps_source_date_and_limits_visible():
    for code in (c for c in fake.DEMO_CODES if c.startswith("FAKE-ZZ")):
        html = _card(code)
        assert 'data-row="nav-source"' in html and 'data-row="nav-cache-at"' in html
        assert 'data-fold="why"' in html and 'data-fold="missing"' in html


# ───────────────────────── OneBrain 槽、renderer 不計算 ─────────────────────────

def test_the_onebrain_slot_is_static_and_disabled():
    html = R.onebrain_slot_html()
    assert 'data-state="disabled"' in html and "未啟用" in _text(html)
    assert R.onebrain_slot_html() == html and "ActionSlot" not in R.__dict__


def test_the_renderer_does_not_compute_it_prints_the_source_layer_strings_verbatim():
    n = load_exp_nav(fake.make_nav_loader(), "FAKE-ZZC3A")
    custom = M.MetricView(M.MetricKind.FAIL_EVIDENCED, None, (("3 年平均年化", "7.01%"),))
    judgement = M.JudgementView(custom, n.judgement.eating_principal, n.judgement.dividend_status)
    html = R.lookup_card_html(lookup_fund(fake.make_loader(), "FAKE-ZZC3A"), fake=True, nav=M.ExpNavView(n.nav, judgement))
    assert "7.01%" in html and "7.0%" not in html.replace("7.01%", "")


def test_a_mutated_view_model_cannot_smuggle_a_withheld_value_into_the_html():
    n = load_exp_nav(fake.make_nav_loader(), "FAKE-ZZC1")
    with pytest.raises(M.ExpNavContractError):
        M.NavSummaryView(n.nav.display, n.nav.reason_codes, nav_value="12.3456", conflicts=n.nav.conflicts)


def test_the_card_prints_the_supplier_timestamp_verbatim_and_separately_from_the_cache_time():
    html = _card("FAKE-ZZC3A")
    cell = re.search(r'data-row="nav-supplier-at".*?</div>', html, re.S).group(0)
    assert "2026-11-20T09:30Z" in cell and "2026-11-21" not in cell
    assert "2026-11-21" in re.search(r'data-row="nav-cache-at".*?</div>', html, re.S).group(0)
