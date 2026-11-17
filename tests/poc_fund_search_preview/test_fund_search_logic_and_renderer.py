# -*- coding: utf-8 -*-
"""🔍 找一檔基金／依條件篩選 隔離式 FAKE Preview：view model 與 renderer 單元（純函式，不開 Streamlit、不開瀏覽器）。

驗：單檔查詢分流（成功／資料不足／失敗／無法辨識／無 fixture／ISIN）、escape、禁用字樣、缺值不為 0、N／M／N＋M 一致、零條件、三態、
五個情境全勾與各子集合；變異（把 N 改錯、拿掉 escape、以 0 取代缺值、顯示『基金不存在』）一律轉紅。
"""
from __future__ import annotations

import itertools
import re

import pytest

import fund_search_support as S  # noqa: F401  # 設定 sys.path

import fund_search_fake_inputs as fake  # noqa: E402
import fund_search_logic as L  # noqa: E402
import fund_search_renderer as R  # noqa: E402
import fund_search_wording as W  # noqa: E402
from ui_v3.viewmodels import exp_counts  # noqa: E402

COUNT = fake.CONDITION_COUNT
SUBSETS = [c for r in range(0, COUNT + 1) for c in itertools.permutations(range(1, COUNT + 1), r)]


def _exp_html(sid, active):
    sc = fake.build(sid)
    view = None if sc["failed"] else L.build_filter_view(sc["pool"], active, COUNT)
    return R.exp0_html(view, sc["failed"]) + R.exp2_html(view, sc["failed"]) + R.exp7_html(view, sc["failed"]), view


# ───────────────────────── 單檔查詢分流 ─────────────────────────

@pytest.mark.parametrize("raw,outcome", [
    ("FAKE-OK01", L.OUT_FOUND), ("  fake-ok01  ", L.OUT_FOUND), ("FAKE-LOW1", L.OUT_INSUFFICIENT), ("FAKE-ERR1", L.OUT_FAILED),
    ("", L.OUT_UNRECOGNIZED), ("   ", L.OUT_UNRECOGNIZED), ("!!", L.OUT_UNRECOGNIZED), ("a b c", L.OUT_UNRECOGNIZED), ("基金", L.OUT_UNRECOGNIZED),
    ("<script>alert(1)</script>", L.OUT_UNRECOGNIZED), ("X" * 25, L.OUT_UNRECOGNIZED),
    ("ABC123", L.OUT_NO_FIXTURE), ("FAKE-ZZZ9", L.OUT_NO_FIXTURE),
    ("US0378331005", L.OUT_ISIN), ("us0378331005", L.OUT_ISIN), (" LU0000000001 ", L.OUT_ISIN),
])
def test_lookup_classification(raw, outcome):
    r = L.classify_lookup(raw, fake.LOOKUP_FIXTURES)
    assert r.outcome == outcome and r.raw == raw   # 輸入原值保留，不改寫、不拆後綴


@pytest.mark.parametrize("bad", [None, 0, 1.5, b"x", ["a"]])
def test_lookup_rejects_non_string(bad):
    with pytest.raises(ValueError):
        L.classify_lookup(bad, fake.LOOKUP_FIXTURES)


def test_fixture_codes_are_not_isin_shaped_and_are_fake():
    for code, outcome in fake.LOOKUP_FIXTURES.items():
        assert code.startswith("FAKE-") and outcome in L.OUTCOMES
        assert L.classify_lookup(code, fake.LOOKUP_FIXTURES).outcome == outcome != L.OUT_ISIN


@pytest.mark.parametrize("raw", ["FAKE-OK01", "FAKE-LOW1", "FAKE-ERR1", "", "ABC123", "<script>x</script>"])
def test_lookup_card_never_claims_identity_or_nonexistence_and_has_fake_tag(raw):
    html = R.lookup_card_html(L.classify_lookup(raw, fake.LOOKUP_FIXTURES), fake.FAKE_FOUND_NAME)
    assert S.page_violations(html) == [] or all("EXP" in v for v in S.page_violations(html))
    assert S.forbidden_word_violations(html) == [] and S.raw_script_violations(html) == []
    assert 'data-tag="fake"' in html and "FAKE 模擬" in html
    assert "◇ 尚未確認" in html and "已確認" not in html            # 身份永遠是待確認


def test_lookup_card_profile_fields_are_missing_not_zero_and_found_has_only_a_fake_name():
    found = R.lookup_card_html(L.classify_lookup("FAKE-OK01", fake.LOOKUP_FIXTURES), fake.FAKE_FOUND_NAME)
    assert fake.FAKE_FOUND_NAME in found
    for row in ("inception", "dividend-mode", "mgmt-fee"):
        m = re.search(rf'data-row="{row}">(.*?)</div>', found)
        assert m and "◇ 資料未備" in m.group(1) and not re.search(r">\s*0\s*<", m.group(1))
    low = R.lookup_card_html(L.classify_lookup("FAKE-LOW1", fake.LOOKUP_FIXTURES), fake.FAKE_FOUND_NAME)
    assert fake.FAKE_FOUND_NAME not in low and "資料不足" in low
    for row in ("name", "inception", "dividend-mode", "mgmt-fee"):
        assert "◇ 資料未備" in re.search(rf'data-row="{row}">(.*?)</div>', low).group(1)


def test_failed_lookup_uses_the_approved_failure_wording_and_never_says_not_found():
    html = R.lookup_card_html(L.classify_lookup("FAKE-ERR1", fake.LOOKUP_FIXTURES), fake.FAKE_FOUND_NAME)
    assert "⛔ 取數失敗" in html and W.text("fail_not_identity") in html
    assert S.forbidden_word_violations(html) == []
    assert 'data-row="name"' not in html   # 失敗時不畫任何個人資料列


@pytest.mark.parametrize("raw", ["", "###"])
def test_unrecognized_input_is_undetermined_not_nonexistent(raw):
    html = R.lookup_card_html(L.classify_lookup(raw, fake.LOOKUP_FIXTURES), fake.FAKE_FOUND_NAME)
    assert "⬜ 無法判定" in html and W.text("suffix_unrecognized") in html and S.forbidden_word_violations(html) == []


def test_isin_shaped_input_shows_only_the_inactive_notice_no_card_no_echo():
    result = L.classify_lookup("US0378331005", fake.LOOKUP_FIXTURES)
    html = R.isin_result_html()
    assert "ISIN 目前未啟用" in html and "lookup-result" not in html and "US0378331005" not in html
    with pytest.raises(ValueError):
        R.lookup_card_html(result, fake.FAKE_FOUND_NAME)   # ISIN 形的輸入不出結果卡
    assert S.forbidden_word_violations(html) == []


@pytest.mark.parametrize("raw", S.NASTY_INPUTS)
def test_user_input_is_escaped_in_the_result_card(raw):
    html = R.lookup_card_html(L.classify_lookup(raw, fake.LOOKUP_FIXTURES), fake.FAKE_FOUND_NAME)
    assert S.raw_script_violations(html) == []
    assert "$" not in re.search(r'data-value="input-code">(.*?)</span>', html).group(1)
    assert S.text_of(re.search(r'data-value="input-code">(.*?)</span>', html).group(1)).strip() == raw   # 還原後逐字相同


def test_mutation_without_escape_turns_red(monkeypatch):
    monkeypatch.setattr(R, "safe", lambda v: str(v))
    html = R.lookup_card_html(L.classify_lookup("<script>alert(1)</script>", fake.LOOKUP_FIXTURES), fake.FAKE_FOUND_NAME)
    assert "raw <script>" in S.raw_script_violations(html)


def test_blank_input_row_shows_the_missing_wording_not_zero():
    html = R.lookup_card_html(L.classify_lookup("", fake.LOOKUP_FIXTURES), fake.FAKE_FOUND_NAME)
    assert "◇ 資料未備" in re.search(r'data-row="input-code">(.*?)</div>', html).group(1)


def test_details_is_one_collapsed_unnested_details_and_has_no_forbidden_words():
    html = R.basic_info_details_html()
    assert html.count("<details") == 1 and "open" not in re.search(r"<details[^>]*>", html).group(0)
    assert W.text("details_title") in html and S.forbidden_word_violations(html) == []


def test_isin_note_is_permanent_symbol_free_and_pending():
    html = R.isin_note_html()
    assert W.text("isin_note") in html and 'data-pending-wording="isin_note"' in html
    assert not any(sym in W.text("isin_note") for sym in "◆◇⬜⛔◷")


# ───────────────────────── 下區：篩選計數 ─────────────────────────

@pytest.mark.parametrize("sid", [s for s in fake.SCENARIOS if s != "source_failed"])
@pytest.mark.parametrize("active", SUBSETS)
def test_counts_are_consistent_everywhere_for_every_subset(sid, active):
    html, view = _exp_html(sid, active)
    n, m = view.conclusion.matched, view.conclusion.undetermined
    if not active:
        assert not view.conclusion.counts_shown and view.rows == () and view.trace == ()
        assert view.conclusion.text == exp_counts.TEXT_NO_CONDITION
    else:
        exp_counts.verify_exp2_row_count(len(view.rows), n, m)
        exp_counts.verify_exp7_last_row([(t.matched, t.undetermined) for t in view.trace], n, m)
        assert view.conclusion == exp_counts.exp0_conclusion(len(active), n, m)   # 文案只來自 exp_counts
    assert S.count_consistency_violations(html) == []
    assert S.page_violations(html) == []


def test_zero_conditions_has_no_counts_and_no_result_rows():
    for sid in fake.SCENARIOS:
        if sid == "source_failed":
            continue
        html, view = _exp_html(sid, ())
        assert 'data-counts-shown="no"' in html and "data-matched" not in html
        assert "data-fund=" not in html and "data-trace=" not in html
        assert html.count(exp_counts.TEXT_NO_CONDITION) == 3   # EXP-0／EXP-2／EXP-7 都只寫尚未設定條件


@pytest.mark.parametrize("sid,expected", [
    ("has_match", (2, 0)), ("no_match", (0, 0)), ("undetermined_only", (0, 3)), ("mixed", (2, 2))])
def test_scenarios_cover_all_four_count_shapes_with_all_conditions_on(sid, expected):
    _, view = _exp_html(sid, (1, 2, 3))
    assert (view.conclusion.matched, view.conclusion.undetermined) == expected
    text = view.conclusion.text
    assert (("尚" not in text), ("；另有" in text)) == (True, expected[1] > 0)
    if expected == (0, 0):
        assert text == exp_counts.TEXT_NO_MATCH and len(view.rows) == 0 and view.trace[-1].matched == 0


def test_undetermined_is_never_counted_as_match_zero_or_no_match():
    _, view = _exp_html("undetermined_only", (1, 2, 3))
    assert view.conclusion.matched == 0 and view.conclusion.undetermined == 3
    assert {r.state for r in view.rows} == {L.UNDET}                      # 無法判定的列留在清單、標無法判定
    html = R.exp2_html(view, False)
    assert html.count("⬜ 無法判定") == 3 and html.count('data-row-state="match"') == 0


def test_no_match_rows_are_not_listed_and_order_is_fund_code_not_rank():
    _, view = _exp_html("mixed", (1, 2))
    codes = [r.code for r in view.rows]
    assert codes == sorted(codes) and all(r.state in (L.MATCH, L.UNDET) for r in view.rows)
    listed = {r.code for r in view.rows}
    pool = {f["cells"]["code"]: f for f in fake.build("mixed")["pool"]}
    for code, f in pool.items():
        if code not in listed:
            assert L.combine([f["states"][i - 1] for i in (1, 2)]) == L.NOMATCH


def test_missing_cells_render_the_missing_wording_never_zero():
    _, view = _exp_html("undetermined_only", (1, 2, 3))
    html = R.exp2_html(view, False)
    assert "◇ 資料未備" in html and S.missing_shown_as_zero_violations(html) == []
    mutated = html.replace("◇ 資料未備", "0")
    assert S.missing_shown_as_zero_violations(mutated)                        # 變異：以 0 取代缺值 → 轉紅


def test_trace_rows_are_cumulative_and_before_is_previous_n_plus_m():
    _, view = _exp_html("mixed", (1, 2, 3))
    assert [(t.before, t.matched, t.undetermined) for t in view.trace] == [(6, 4, 1), (5, 2, 2), (4, 2, 2)]
    for prev, cur in zip(view.trace, view.trace[1:]):
        assert cur.before == prev.matched + prev.undetermined


def test_source_failure_shows_the_failure_wording_and_no_counts_not_zero():
    sc = fake.build("source_failed")
    assert sc["failed"] and sc["pool"] == []
    html = R.exp0_html(None, True) + R.exp2_html(None, True) + R.exp7_html(None, True)
    assert html.count("⛔ 取數失敗") == 3 and "data-matched" not in html and "data-trace=" not in html and "data-fund=" not in html
    assert not re.search(r"目前條件下", html) and S.forbidden_word_violations(html) == []


def test_non_failed_view_must_not_be_none():
    for fn in (R.exp0_html, R.exp2_html, R.exp7_html):
        with pytest.raises(ValueError):
            fn(None, False)


# ───────────────────────── 變異：頁面層級判定函式必須報紅 ─────────────────────────

def test_mutation_wrong_n_is_flagged():
    html, _ = _exp_html("mixed", (1, 2, 3))
    assert S.count_consistency_violations(html) == []
    bad = html.replace('data-matched="2"', 'data-matched="3"', 1)
    assert S.count_consistency_violations(bad)


def test_mutation_wrong_m_and_wrong_trace_and_dropped_row_are_flagged():
    html, _ = _exp_html("mixed", (1, 2, 3))
    assert S.count_consistency_violations(html.replace('data-undetermined="2"', 'data-undetermined="1"', 1))
    exp7_start = html.index('data-block="exp7"')
    tampered = html[:exp7_start] + html[exp7_start:].replace("</span>2</div>", "</span>9</div>")
    assert S.count_consistency_violations(tampered)
    first_fund = re.search(r'<div class="fs-fund" data-fund=.*?</div></div>', html).group(0)
    assert S.count_consistency_violations(html.replace(first_fund, "", 1))


def test_mutation_renderer_with_wrong_n_raises_through_exp_counts(monkeypatch):
    sc = fake.build("mixed")
    view = L.build_filter_view(sc["pool"], (1, 2, 3), COUNT)
    wrong = L.FilterView(view.conditions, exp_counts.exp0_conclusion(3, 3, 2), view.rows, view.trace)
    with pytest.raises(ValueError):
        R.exp2_html(wrong, False)
    with pytest.raises(ValueError):
        R.exp7_html(wrong, False)


def test_mutation_not_exist_wording_is_flagged_everywhere():
    for inject in ("基金不存在", "查無基金", "最佳", "推薦", "排名", "已確認", "NAV", "報酬", "績效"):
        html = R.lookup_card_html(L.classify_lookup("FAKE-OK01", fake.LOOKUP_FIXTURES), fake.FAKE_FOUND_NAME) + f"<div>{inject}</div>"
        assert S.forbidden_word_violations(html), inject


# ───────────────────────── view model 契約 ─────────────────────────

def test_combine_rule_and_validation():
    assert L.combine([L.MATCH, L.MATCH]) == L.MATCH
    assert L.combine([L.MATCH, L.UNDET]) == L.UNDET
    assert L.combine([L.UNDET, L.NOMATCH]) == L.NOMATCH
    assert L.combine([L.NOMATCH, L.MATCH]) == L.NOMATCH
    with pytest.raises(ValueError):
        L.combine([])
    with pytest.raises(ValueError):
        L.combine(["maybe"])


@pytest.mark.parametrize("states", [("match", "match"), ("match", "match", "unknown"), ("match", None, "match"), ()])
def test_pool_with_missing_or_unknown_tri_state_fails_loudly(states):
    pool = [{"cells": {"code": "FAKE-001"}, "states": states}]
    with pytest.raises(ValueError):
        L.build_filter_view(pool, (1,), COUNT)


@pytest.mark.parametrize("active", [(0,), (4,), (1, 1), (True,), ("1",), (-1,)])
def test_invalid_active_conditions_are_rejected(active):
    with pytest.raises(ValueError):
        L.build_filter_view(fake.build("mixed")["pool"], active, COUNT)


def test_the_view_model_derives_nothing_from_values():
    """三態由 fixture 明確給定：把所有格子的值換掉，結果不變。"""
    pool = fake.build("mixed")["pool"]
    base = L.build_filter_view(pool, (1, 2, 3), COUNT).conclusion
    for f in pool:
        for col in f["cells"]:
            if col != "code":
                f["cells"][col] = None
    assert L.build_filter_view(pool, (1, 2, 3), COUNT).conclusion == base


def test_every_scenario_builds_fresh_objects_and_unknown_scenario_is_an_error():
    a, b = fake.build("mixed"), fake.build("mixed")
    assert a == b and a["pool"] is not b["pool"] and a["pool"][0]["cells"] is not b["pool"][0]["cells"]
    a["pool"][0]["cells"]["name"] = "changed"
    assert fake.build("mixed")["pool"][0]["cells"]["name"] != "changed"
    with pytest.raises(KeyError):
        fake.build("no_such")


def test_exp1_wording_has_no_save_vocabulary_and_section_title_is_pending():
    html = R.exp1_head_html() + R.divider_html()
    assert not [w for w in S.SAVE_WORDS if w in S.text_of(html)]
    assert "依條件篩選" in html and "本次瀏覽暫時條件" in html and 'data-block="exp-divider"' in html
