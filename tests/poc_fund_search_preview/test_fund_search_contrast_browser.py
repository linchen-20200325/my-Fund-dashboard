# -*- coding: utf-8 -*-
"""🔍 FAKE Preview｜DEC-2026-11-17-03 視覺對比守衛（slow lane；需要 streamlit 與 Chromium）。

要求：空選股池與整檔「無法判定」的虛線邊框，重要狀態辨識對比至少 3:1，並有符號或文字輔助，不依賴灰底、顏色或虛線單獨傳達狀態；須用實際量測，不以手算宣稱通過。
做法：390／768／1280 三個寬度，用真 Chromium 取 computed style（邊框四邊色與線型、元素自身與外層的有效底色、文字色與有效底色），
以 WCAG 相對亮度公式（`fund_search_browser_lib.contrast_ratio`）**即時**算比值；色值不寫死在斷言裡（改 token 後守衛仍然成立）。
- 邊框（非文字）：對外層背景、對卡片自身背景皆 ≥3:1。
- 文字：空池三張卡與無法判定列內的每一段可見文字對其有效底色 ≥4.5:1。
- 輔助標記：空池三張卡各有『○ 選股池目前是空的』（PendingWording `pool_empty_marker`）；無法判定列各有規則表的『⬜ 無法判定』。
- G-5：EXP-7 在 390 手機可換行、不強制四欄橫排。
變異驗證：把邊框色退回舊值（約 2.8:1）判定必須報紅；拿掉標記判定必須報紅。
⚠️ 只量本機 headless Chromium；Streamlit Cloud 與真機未驗（NOT VERIFIED）。
"""
import pytest

import fund_search_support as S  # noqa: F401

pytestmark = pytest.mark.slow

pytest.importorskip("streamlit", reason="本環境匯入不到 streamlit")

import fund_search_browser_lib as lib  # noqa: E402
import fund_search_wording as W  # noqa: E402
from shared.ui_semantics import rules  # noqa: E402
from test_fund_search_browser import _open, _scenario, _set_conditions, server_and_browser  # noqa: E402,F401

WIDTHS = (390, 768, 1280)
EMPTY_CARDS = ('[data-block="exp0"]', '[data-block="exp2"]', '[data-block="exp7"]')
UNDET_ROW = '.fs-fund[data-row-state="undetermined"]'
SPEC_EMPTY = {"borders": list(EMPTY_CARDS), "texts": list(EMPTY_CARDS), "cells": '[data-block="exp7"] [data-trace] .fs-cell'}
SPEC_UNDET = {"borders": [UNDET_ROW], "texts": [UNDET_ROW], "cells": '[data-block="exp7"] [data-trace] .fs-cell'}
UNDET_WORDING = rules.entry("undetermined").wording
MARKER = W.text("pool_empty_marker")


def _card_texts(page):
    return page.evaluate("() => Object.fromEntries([...document.querySelectorAll('[data-block=\"exp0\"], [data-block=\"exp2\"], [data-block=\"exp7\"]')].map(e => [e.dataset.block, e.innerText]))")


def _undet_row_texts(page):
    return page.evaluate("() => [...document.querySelectorAll('.fs-fund[data-row-state=\"undetermined\"]')].map(e => e.innerText)")


@pytest.fixture(scope="module")
def measured(server_and_browser):
    base, browser = server_and_browser
    out = {}
    for width in WIDTHS:
        o = _open(browser, base, width)
        try:
            page = o.page
            _scenario(page, "empty_pool")
            _set_conditions(page, {1, 2, 3})
            out[(width, "empty_pool")] = {"c": page.evaluate(lib.CONTRAST_JS, SPEC_EMPTY), "cards": _card_texts(page), "m": o.measure()}
            _scenario(page, "no_match")
            _set_conditions(page, {1, 2, 3})
            out[(width, "no_match")] = {"c": page.evaluate(lib.CONTRAST_JS, {"borders": list(EMPTY_CARDS), "texts": [], "cells": None}), "cards": _card_texts(page)}
            for sid in ("mixed", "undetermined_only"):
                _scenario(page, sid)
                _set_conditions(page, {1, 2, 3})
                out[(width, sid)] = {"c": page.evaluate(lib.CONTRAST_JS, SPEC_UNDET), "rows": _undet_row_texts(page), "m": o.measure()}
            _scenario(page, "mixed")
            _set_conditions(page, {1, 2, 3})
            out[(width, "trace")] = page.evaluate(lib.CONTRAST_JS, SPEC_EMPTY)
        finally:
            o.close()
    return out


# ───────────────────────── 量測公式本身（純函式，不需瀏覽器） ─────────────────────────

def test_wcag_contrast_formula_matches_known_values():
    assert lib.contrast_ratio((0, 0, 0), (255, 255, 255)) == pytest.approx(21.0, abs=1e-9)
    assert lib.contrast_ratio((255, 255, 255), (255, 255, 255)) == pytest.approx(1.0, abs=1e-9)
    assert lib.contrast_ratio((119, 119, 119), (255, 255, 255)) == pytest.approx(4.48, abs=0.01)    # #777 對白：WCAG 公認約 4.48，剛好不到 4.5
    assert lib.contrast_ratio((255, 255, 255), (119, 119, 119)) == lib.contrast_ratio((119, 119, 119), (255, 255, 255))
    # 本批修正前的組合：card.border #7f8ca6 對 tone.grey 底 #e6eaf3 ≈ 2.81（< 3），對頁底 #f5f7fb ≈ 3.16、對白 ≈ 3.38
    assert lib.contrast_ratio((127, 140, 166), (230, 234, 243)) == pytest.approx(2.81, abs=0.01)


def test_checker_flags_a_border_below_3_to_1_and_text_below_4_5_to_1_and_missing_elements():
    base = {"sel": "x", "i": 0, "styles": ["dashed"] * 4, "widths": [1.0] * 4, "own": [230, 234, 243], "outer": [245, 247, 251], "text": ""}
    weak = dict(base, colors=[[127, 140, 166, 1]] * 4)
    strong = dict(base, colors=[[74, 86, 112, 1]] * 4)
    assert lib.border_violations({"borders": [weak]}, "x") and any("3:1" in v[0] for v in lib.border_violations({"borders": [weak]}, "x"))
    assert lib.border_violations({"borders": [strong]}, "x") == []
    assert lib.border_violations({"borders": [dict(strong, styles=["solid"] * 4)]}, "x")          # 線型不對
    assert lib.border_violations({"borders": [dict(strong, colors=[[74, 86, 112, 0.5]] * 4)]}, "x")   # 半透明：量不準，判違規
    assert lib.border_violations({"borders": []}, "x") == [("找不到元素", "x")]
    t = {"texts": [{"sel": "t", "ri": 0, "text": "a", "fg": [119, 119, 119], "bg": [255, 255, 255], "opacity": 1}]}
    assert lib.text_violations(t, "t") and lib.text_violations({"texts": []}, "t") == [("找不到文字", "t")]
    assert lib.text_violations({"texts": [dict(t["texts"][0], fg=[0, 0, 0])]}, "t") == []
    assert lib.text_violations({"texts": [dict(t["texts"][0], fg=[0, 0, 0], opacity=0.6)]}, "t")


# ───────────────────────── 空選股池 ─────────────────────────

@pytest.mark.parametrize("width", WIDTHS)
@pytest.mark.parametrize("card", EMPTY_CARDS)
def test_empty_pool_dashed_border_has_at_least_3_to_1_against_outer_and_own_background(measured, width, card):
    c = measured[(width, "empty_pool")]["c"]
    assert lib.border_violations(c, card) == [], lib.border_rows(c, card)


@pytest.mark.parametrize("width", WIDTHS)
def test_empty_pool_text_has_at_least_4_5_to_1_against_its_background(measured, width):
    c = measured[(width, "empty_pool")]["c"]
    for card in EMPTY_CARDS:
        assert lib.text_violations(c, card) == [], (card, lib.text_rows(c, card))


@pytest.mark.parametrize("width", WIDTHS)
def test_empty_pool_state_is_also_carried_by_a_symbol_plus_text_marker_on_all_three_cards(measured, width):
    cards = measured[(width, "empty_pool")]["cards"]
    for block in ("exp0", "exp2", "exp7"):
        assert MARKER in cards[block], (block, cards[block])
    assert "○" in MARKER and "失敗" not in MARKER and "缺" not in MARKER and "來源" not in MARKER   # 空池≠取數失敗≠來源缺失
    # 有基金但零符合：實線、不帶空池標記（兩種『0 符合』不再只靠灰底／虛線分辨）
    none = measured[(width, "no_match")]
    assert all(MARKER not in none["cards"][b] for b in none["cards"])
    assert all(r["all_want_style"] is False for card in EMPTY_CARDS for r in lib.border_rows(none["c"], card, want_style="dashed"))


@pytest.mark.parametrize("width", WIDTHS)
def test_empty_pool_is_still_distinguished_visually_by_dashed_border_and_the_page_is_not_broken(measured, width):
    m = measured[(width, "empty_pool")]["m"]
    assert lib.structure_violations(m) == [], lib.structure_violations(m)
    c = measured[(width, "empty_pool")]["c"]
    for card in EMPTY_CARDS:
        assert all(r["all_want_style"] for r in lib.border_rows(c, card))


# ───────────────────────── 整檔無法判定的列 ─────────────────────────

@pytest.mark.parametrize("sid", ("mixed", "undetermined_only"))
@pytest.mark.parametrize("width", WIDTHS)
def test_undetermined_row_dashed_border_has_at_least_3_to_1_and_text_has_4_5_to_1(measured, width, sid):
    c = measured[(width, sid)]["c"]
    assert lib.border_violations(c, UNDET_ROW) == [], lib.border_rows(c, UNDET_ROW)
    assert lib.text_violations(c, UNDET_ROW) == [], lib.text_rows(c, UNDET_ROW)


@pytest.mark.parametrize("sid", ("mixed", "undetermined_only"))
@pytest.mark.parametrize("width", WIDTHS)
def test_every_undetermined_row_carries_the_approved_symbol_plus_wording_not_just_the_dashed_border(measured, width, sid):
    rows = measured[(width, sid)]["rows"]
    assert rows and all(UNDET_WORDING in t for t in rows), rows       # 『⬜ 無法判定』來自規則表；符號＋字樣，不靠虛線或顏色
    assert all(MARKER not in t for t in rows)
    assert lib.structure_violations(measured[(width, sid)]["m"]) == []


# ───────────────────────── G-5：EXP-7 手機可換行 ─────────────────────────

def test_exp7_cells_wrap_on_a_phone_and_are_not_forced_into_four_columns(measured):
    c = measured[(390, "trace")]
    cells = c["cells"]
    assert cells and len(cells) % 4 == 0
    for i in range(0, len(cells), 4):
        row = cells[i:i + 4]
        assert len({x["top"] for x in row}) >= 2, row                 # 390：四格不在同一橫列（已換行）
        assert all(x["right"] <= c["vw"] + 0.5 for x in row)
    for width in WIDTHS:                                              # 任何寬度都不得溢出視窗
        assert all(x["right"] <= measured[(width, "trace")]["vw"] + 0.5 for x in measured[(width, "trace")]["cells"])


# ───────────────────────── 變異驗證（判定必須報紅） ─────────────────────────

def test_mutation_reverting_the_empty_pool_border_to_the_old_color_turns_the_checker_red(server_and_browser):
    base, browser = server_and_browser
    o = _open(browser, base, 390)
    try:
        _scenario(o.page, "empty_pool")
        _set_conditions(o.page, {1, 2, 3})
        assert lib.border_violations(o.page.evaluate(lib.CONTRAST_JS, SPEC_EMPTY), '[data-block="exp0"]') == []
        o.page.add_style_tag(content='.uv3-card[data-pool-size="0"]{border-color:#7f8ca6 !important}')    # 舊值：card.border，對灰底約 2.81:1
        o.page.wait_for_timeout(200)
        bad = lib.border_violations(o.page.evaluate(lib.CONTRAST_JS, SPEC_EMPTY), '[data-block="exp0"]')
        assert bad and any(v[0] == "邊框對比低於 3:1" and v[2] == "vs_own" for v in bad), bad
    finally:
        o.close()


def test_mutation_light_text_on_the_empty_pool_card_turns_the_text_checker_red(server_and_browser):
    base, browser = server_and_browser
    o = _open(browser, base, 390)
    try:
        _scenario(o.page, "empty_pool")
        _set_conditions(o.page, {1, 2, 3})
        o.page.add_style_tag(content='[data-block="exp0"] [data-row="conclusion"]{color:#9aa5bd !important}')
        o.page.wait_for_timeout(200)
        assert lib.text_violations(o.page.evaluate(lib.CONTRAST_JS, SPEC_EMPTY), '[data-block="exp0"]')
    finally:
        o.close()


def test_mutation_removing_the_marker_turns_the_marker_check_red(server_and_browser):
    base, browser = server_and_browser
    o = _open(browser, base, 390)
    try:
        _scenario(o.page, "empty_pool")
        _set_conditions(o.page, {1, 2, 3})
        assert all(MARKER in t for t in _card_texts(o.page).values())
        o.page.evaluate("() => document.querySelectorAll('[data-marker=\"pool-empty\"]').forEach(e => e.remove())")
        assert not all(MARKER in t for t in _card_texts(o.page).values())
    finally:
        o.close()
