# -*- coding: utf-8 -*-
"""🔍 找一檔基金／依條件篩選 隔離式 FAKE Preview：view model 與 renderer 單元（純函式，不開 Streamlit、不開瀏覽器）。

驗：單檔查詢分流（成功／資料不足／失敗／無法辨識／無 fixture／ISIN）、escape、禁用字樣、缺值不為 0、N／M／N＋M 一致、零條件、三態、
五個情境全勾與各子集合；變異（把 N 改錯、拿掉 escape、以 0 取代缺值、顯示『基金不存在』）一律轉紅。

⚠️ 變異測試分兩種，**不要混為一談**：
- 對判定函式（checker：`fund_search_support.py` 的 `*_violations`）變異的，只證明「檢查函式抓得到這種壞 HTML」，**不證明 production renderer 不會產生該錯誤**。
  本檔屬此類：`test_mutation_wrong_n_is_flagged`、`test_mutation_wrong_m_and_wrong_trace_and_dropped_row_are_flagged`、`test_mutation_not_exist_wording_is_flagged_everywhere`，
  以及 `test_missing_cells_render_the_missing_wording_never_zero` 內的 0 取代缺值。
- 真正對 production 程式變異的（monkeypatch 後重跑 production renderer／view model）：`test_mutation_without_escape_turns_red`、
  `test_mutation_removing_any_safe_branch_turns_the_special_char_guard_red`（`R.safe` 逐分支）、`test_mutation_renderer_with_wrong_n_raises_through_exp_counts`
  （餵錯的 view 給 production renderer，由 `exp_counts` 驗證擋下）。
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
    assert S.page_violations(html) == []   # 單看結果卡 HTML：沒有 EXP 區塊，頁面層級判定函式必須整個為空
    assert S.forbidden_word_violations(html) == [] and S.raw_script_violations(html) == []
    assert 'data-tag="fake"' in html and "FAKE 模擬" in html
    assert "已確認" not in html and 'data-row="identity"' not in html and "◇ 尚未確認" not in html   # 沒有『基金身份』欄（DEC-2026-11-18-01：結果欄位只有五個），更不會宣稱已確認


def _card(raw, mode=None):
    return R.lookup_card_html(L.classify_lookup(raw, fake.LOOKUP_FIXTURES), fake.FAKE_FOUND_NAME, mode)


def _row_html(html, name):
    return re.search(rf'data-row="{name}">(.*?)</div>', html).group(1)


def test_lookup_card_profile_fields_are_missing_not_zero_and_found_has_a_fake_name_and_a_candidate_dividend_mode():
    found = _card("FAKE-OK01", fake.LOOKUP_DIVIDEND_MODE["FAKE-OK01"])
    assert fake.FAKE_FOUND_NAME in found
    assert W.text("div_mode_distributing") == "配息型" and "配息型" in _row_html(found, "dividend-mode")
    for row in ("inception", "mgmt-fee"):
        assert "⬜ 資料未備" in _row_html(found, row) and not re.search(r">\s*0\s*<", _row_html(found, row))
    other = _card("FAKE-OK02", fake.LOOKUP_DIVIDEND_MODE["FAKE-OK02"])
    assert W.text("div_mode_accumulating") == "累積型" and "累積型" in _row_html(other, "dividend-mode") and "配息型" not in other
    no_mode = _card("FAKE-OK01")                                          # 沒給候選值 → 缺值字樣，不猜
    assert "⬜ 資料未備" in _row_html(no_mode, "dividend-mode") and "配息型" not in no_mode and "累積型" not in no_mode
    low = _card("FAKE-LOW1", "distributing")                              # 只有 found 才顯示候選值；資料不足一律缺值
    assert fake.FAKE_FOUND_NAME not in low and "資料不足" in low and "配息型" not in low
    for row in ("name", "inception", "dividend-mode", "mgmt-fee"):
        assert "⬜ 資料未備" in _row_html(low, row)
    with pytest.raises(ValueError):
        _card("FAKE-OK01", "半年配")                                       # 未知候選值 fail loud，不顯示


def test_lookup_card_has_exactly_the_five_approved_fields_in_the_clients_order():
    found = _card("FAKE-OK01", "distributing")
    assert [x for x in S._LABEL_RE.findall(found)] == list(S.FIVE_LABELS)
    assert re.findall(r'data-row="([^"]+)"', found) == ["result", "input-code", "name", "dividend-mode", "inception", "mgmt-fee"]
    assert W.text("row_inception") == "成立日期"


@pytest.mark.parametrize("raw", ["FAKE-OK01", "FAKE-OK02", "FAKE-LOW1", "FAKE-ERR1", "", "???", "ABC123", "<script>x</script>"])
def test_lookup_card_has_no_field_beyond_the_five_for_every_outcome(raw):
    """DEC-2026-11-18-01 第 7 點：不顯示未核准幣別／NAV／報酬／績效／fetched_at／供應者欄位，也不留舊的查詢結果／輸入類型／基金身份欄。"""
    assert S.lookup_field_violations(_card(raw, fake.LOOKUP_DIVIDEND_MODE.get(raw.upper()))) == []


def test_details_area_holds_no_field_rows_source_fallback_asof_are_removed():
    html = R.basic_info_details_html()
    assert S.details_field_violations(html) == []
    for key in ("row_source", "row_fallback", "row_asof", "not_obtained_note", "row_result", "row_input_type", "input_type_code", "row_identity", "identity_unconfirmed"):
        assert key not in W.FUND_SEARCH_PENDING, key


def test_mutation_extra_field_rows_in_the_production_renderer_turn_the_whitelist_red(monkeypatch):
    """對 production renderer 變異：結果卡多畫一列『幣別』／收合區把『來源』欄位列放回去，白名單必須報紅（未變異時為空）。"""
    assert S.lookup_field_violations(_card("FAKE-OK01", "distributing")) == [] and S.details_field_violations(R.basic_info_details_html()) == []
    orig_row = R._row

    def with_currency(label_key, value_html, name):
        extra = '<div class="uv3-row" data-row="ccy"><span class="uv3-label">幣別</span>X</div>' if name == "mgmt-fee" else ""
        return orig_row(label_key, value_html, name) + extra
    monkeypatch.setattr(R, "_row", with_currency)
    bad = S.lookup_field_violations(_card("FAKE-OK01", "distributing"))
    assert ("非五欄標籤", "幣別") in bad and ("非白名單 data-row", "ccy") in bad and ("未核准欄位字樣", "幣別") in bad
    monkeypatch.undo()
    orig_details = R.basic_info_details_html
    monkeypatch.setattr(R, "basic_info_details_html",
                        lambda: orig_details().replace("</details>", '<div class="uv3-row" data-row="source"><span class="uv3-label">來源</span>x</div></details>'))
    assert S.details_field_violations(R.basic_info_details_html())
    # 其他未核准欄位字樣各自都抓得到（對判定函式變異：在已知乾淨的結果卡尾端塞入該字樣）
    clean = _card("FAKE-OK01", "distributing")
    for token in ("NAV", "淨值", "報酬", "績效", "fetched_at", "供應者", "備援來源", "資料日", "幣別"):
        head, _, tail = clean.rpartition("</div>")
        assert [v for v in S.lookup_field_violations(head + token + "</div>" + tail) if v[0] == "未核准欄位字樣"], token


def test_idle_card_says_only_not_queried_and_the_mutations_turn_red(monkeypatch):
    html = R.lookup_idle_html()
    assert S.idle_violations(html) == [] and W.text("not_queried") == "尚未查詢" and 'data-pending-wording="not_queried"' in html
    assert 'data-block="lookup-result"' not in html and S.forbidden_word_violations(html) == []
    # 變異一：idle 卡多畫一列欄位 → 報紅
    monkeypatch.setattr(R, "lookup_idle_html", lambda: html.replace("</div></div>", '</div><div class="uv3-row" data-row="name"><span class="uv3-label">基金名稱</span>x</div></div>'))
    assert S.idle_violations(R.lookup_idle_html())
    monkeypatch.undo()
    # 變異二：改 production 字樣 → 報紅
    from ui_v3.viewmodels.preview_wording import PendingWording
    mutated = dict(W.FUND_SEARCH_PENDING)
    mutated["not_queried"] = PendingWording("not_queried", "查無基金", W.SOURCE_DEC1118)
    monkeypatch.setattr(W, "FUND_SEARCH_PENDING", mutated)
    assert S.idle_violations(R.lookup_idle_html())


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
    shown = re.search(r'data-value="input-code">(.*?)</span>', html, re.S).group(1)
    assert S.special_char_violations(shown) == []                  # < > $ 反斜線 換行都已轉成字元參照
    assert S.text_of(shown).strip() == raw.strip()                 # 還原後逐字相同（頭尾空白不影響判斷）


def _safe_without(branch):
    """production `R.safe` 的變異版：拿掉某一個分支（在記憶體內現編）。"""
    from html import escape

    def mutated(value):
        out = escape(str(value), quote=True)
        for char, ref in (("$", "&#36;"), ("\\", "&#92;"), ("\n", "&#10;"), ("\r", "&#13;")):
            if char != branch:
                out = out.replace(char, ref)
        return out
    return mutated


@pytest.mark.parametrize("branch,raw", [("$", "cost $5 $x$"), ("\\", "a\\b \\$x\\$"), ("\n", "a\nb"), ("\r", "a\rb")])
def test_mutation_removing_any_safe_branch_turns_the_special_char_guard_red(monkeypatch, branch, raw):
    """對 production renderer 變異：拿掉 `safe()` 的任一分支，結果卡的特殊字元守衛必須報紅（含反斜線分支）。"""
    html = R.lookup_card_html(L.classify_lookup(raw, fake.LOOKUP_FIXTURES), fake.FAKE_FOUND_NAME)
    assert S.special_char_violations(re.search(r'data-value="input-code">(.*?)</span>', html, re.S).group(1)) == []   # 未變異：綠
    monkeypatch.setattr(R, "safe", _safe_without(branch))
    bad = R.lookup_card_html(L.classify_lookup(raw, fake.LOOKUP_FIXTURES), fake.FAKE_FOUND_NAME)
    assert branch in S.special_char_violations(re.search(r'data-value="input-code">(.*?)</span>', bad, re.S).group(1))


def test_mutation_without_escape_turns_red(monkeypatch):
    monkeypatch.setattr(R, "safe", lambda v: str(v))
    html = R.lookup_card_html(L.classify_lookup("<script>alert(1)</script>", fake.LOOKUP_FIXTURES), fake.FAKE_FOUND_NAME)
    assert "raw <script>" in S.raw_script_violations(html)


def test_blank_input_row_shows_the_missing_wording_not_zero():
    html = R.lookup_card_html(L.classify_lookup("", fake.LOOKUP_FIXTURES), fake.FAKE_FOUND_NAME)
    assert "⬜ 資料未備" in re.search(r'data-row="input-code">(.*?)</div>', html).group(1)


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
    assert "⬜ 資料未備" in html and S.missing_shown_as_zero_violations(html) == []
    mutated = html.replace("⬜ 資料未備", "0")
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


# ───────────────────────── 2026-11-17 收斂批：輸入類型列、缺值／無法判定分開、空選股池、獨立算盤 ─────────────────────────

from shared.ui_semantics import rules  # noqa: E402

_TYPE_LABEL, _TYPE_VALUE = "輸入類型", "代碼型字串（原值未改寫）"


@pytest.mark.parametrize("raw", ["FAKE-OK01", "FAKE-LOW1", "FAKE-ERR1", "ABC123", "  fake-ok01  ", "", "???"])
def test_input_type_and_identity_rows_are_gone_and_the_input_code_is_kept_verbatim(raw):
    """DEC-2026-11-18-01：『輸入類型』『基金身份』不在五欄內，已移除；輸入代碼仍顯示原值（不改寫）。"""
    html = R.lookup_card_html(L.classify_lookup(raw, fake.LOOKUP_FIXTURES), fake.FAKE_FOUND_NAME)
    assert 'data-row="input-type"' not in html and 'data-row="identity"' not in html
    assert _TYPE_LABEL not in html and _TYPE_VALUE not in html and "基金身份" not in S.text_of(html).replace("不是對基金身份的判斷", "")
    assert "◇ 尚未確認" not in html and "已解析" not in html and "已確認" not in html
    if raw.strip():
        shown = re.search(r'data-value="input-code">(.*?)</span>', html, re.S).group(1)
        assert S.text_of(shown) == raw                                  # 原值未改寫（連頭尾空白、大小寫都保留）


def test_input_type_row_is_absent_in_the_isin_situation():
    assert L.classify_lookup("US0378331005", fake.LOOKUP_FIXTURES).outcome == L.OUT_ISIN
    html = R.isin_result_html()
    assert _TYPE_LABEL not in html and _TYPE_VALUE not in html and "lookup-result" not in html


def test_undetermined_and_missing_are_different_wordings_and_different_dom_markers_everywhere():
    """『無法判定』＝資料不足以判定；『資料缺值』＝這一格沒有值。兩者不共用字樣、不共用標記。"""
    _, view = _exp_html("undetermined_only", (1, 2, 3))
    exp2 = R.exp2_html(view, False)
    tags = re.findall(r'<div class="uv3-row" data-row="undetermined">(.*?)</div>', exp2)
    assert len(tags) == 3
    for t in tags:
        assert S.text_of(t).replace(" ", "") == "⬜無法判定（資料未備）"      # 整檔無法判定列沿用 44 客戶逐字結構
        assert 'data-status-key="undetermined"' in t and 'data-kind="missing"' not in t and "⬜ 資料未備" not in t   # 沿用 44 逐字結構；不含缺值格的字樣與標記
    cells = re.findall(r'<span class="uv3-st uv3-st-grey uv3-pending" data-kind="missing"[^>]*>([^<]*)</span>', exp2)
    assert len(cells) >= 3 and set(cells) == {W.text("missing_demo")} and "無法判定" not in W.text("missing_demo")
    unrec = R.lookup_card_html(L.classify_lookup("???", fake.LOOKUP_FIXTURES), fake.FAKE_FOUND_NAME)
    assert 'data-status-key="undetermined"' in unrec and "資料未備" not in re.search(r'data-row="result">(.*?)</div>', unrec).group(1)


def test_the_formal_mode_missing_wording_never_appears_in_any_preview_html():
    formal = rules.entry("missing").wording
    parts = [R.basic_info_details_html(), R.isin_note_html(), R.isin_result_html(), R.lookup_idle_html(), R.exp1_head_html(), R.divider_html(), R.CSS]
    for raw in ("FAKE-OK01", "FAKE-LOW1", "FAKE-ERR1", "", "???", "ABC123"):
        parts.append(R.lookup_card_html(L.classify_lookup(raw, fake.LOOKUP_FIXTURES), fake.FAKE_FOUND_NAME))
    for sid in fake.SCENARIOS:
        for active in ((), (1,), (1, 2, 3)):
            parts.append(_exp_html(sid, active)[0] if sid != "source_failed" else R.exp0_html(None, True))
    assert all(formal not in p for p in parts)
    known_bad = f'<span>{formal}</span>'                 # 負控：對一段已知含正式缺值字樣的 HTML 跑同一判定式
    assert any(formal in p for p in parts + [known_bad]) and not any(formal in p for p in parts)


def _oracle_trace(pool, active):
    """獨立算盤（不呼叫 L.*）：逐條件累計套用；回傳 [(套用前, 符合, 無法判定)]。"""
    out, remaining = [], list(pool)
    for step in range(1, len(active) + 1):
        before = len(remaining)
        chosen = active[:step]
        nxt, m, u = [], 0, 0
        for f in pool:
            sts = [f["states"][i - 1] for i in chosen]
            if "nomatch" in sts:
                continue
            if "undetermined" in sts:
                u += 1
            else:
                m += 1
            nxt.append(f)
        out.append((before, m, u))
        remaining = nxt
    return out


@pytest.mark.parametrize("sid", ["has_match", "no_match", "undetermined_only", "mixed", "empty_pool"])
@pytest.mark.parametrize("active", [(1,), (3,), (1, 3), (3, 1), (2, 3, 1), (1, 2, 3)])
def test_trace_matches_an_independent_oracle_for_partial_and_multi_conditions_in_every_order(sid, active):
    pool = fake.build(sid)["pool"]
    view = L.build_filter_view(pool, active, COUNT)
    assert [(t.before, t.matched, t.undetermined) for t in view.trace] == _oracle_trace(pool, active)
    assert [t.index for t in view.trace] == list(active)             # 軌跡依畫面順序，一列一條
    assert (view.conclusion.matched, view.conclusion.undetermined) == _oracle_trace(pool, active)[-1][1:]


def test_application_order_changes_the_earlier_rows_but_not_the_last_row():
    pool = fake.build("mixed")["pool"]
    a, b = L.build_filter_view(pool, (1, 3), COUNT), L.build_filter_view(pool, (3, 1), COUNT)
    rows = lambda v: [(t.before, t.matched, t.undetermined) for t in v.trace]   # noqa: E731
    assert rows(a) == [(6, 4, 1), (5, 4, 1)] and rows(b) == [(6, 6, 0), (6, 4, 1)]   # 順序不同 → 前面的列不同
    assert rows(a)[-1][1:] == rows(b)[-1][1:] == (4, 1)                              # 最後一列（＝EXP-0 的 N／M）相同


def test_empty_pool_is_distinguishable_from_a_pool_with_zero_matches():
    empty, none = fake.build("empty_pool")["pool"], fake.build("no_match")["pool"]
    assert empty == [] and len(none) == 4
    ve, vn = L.build_filter_view(empty, (1, 2, 3), COUNT), L.build_filter_view(none, (1, 2, 3), COUNT)
    assert (ve.conclusion.matched, ve.conclusion.undetermined) == (vn.conclusion.matched, vn.conclusion.undetermined) == (0, 0)
    assert ve.conclusion.text == vn.conclusion.text == exp_counts.TEXT_NO_MATCH           # N=M=0 的結論文案相同（文案取 exp_counts）
    assert ve.trace[0].before == 0 and vn.trace[0].before == 4 and ve.rows == vn.rows == ()
    he, hn = _exp_html("empty_pool", (1, 2, 3))[0], _exp_html("no_match", (1, 2, 3))[0]
    assert 'data-pool-size="0"' in he and 'data-pool-size="4"' in hn and he != hn
    assert S.page_violations(he) == [] and S.page_violations(hn) == []


_POOL_MARKER_RE = re.compile(r'<div class="uv3-row" data-marker="pool-empty">.*?</span></div>')


def _without_pool_marker(html):
    return _POOL_MARKER_RE.sub("", html)


def test_empty_pool_has_a_visual_marker_and_a_symbol_text_marker_and_nothing_else_differs_in_text():
    """空選股池 vs 有基金但零符合：結構屬性＋CSS（虛線框、灰底）＋ DEC-2026-11-17-03 的符號＋文字標記（`pool_empty_marker`）。
    原守衛『不新增任何文字』已被 DEC-2026-11-17-03 取代；改鎖『拿掉那一個標記後，可見文字與零符合完全相同』＝標記是唯一新增的文字。"""
    for sid, size in (("empty_pool", "0"), ("no_match", "4")):
        sc = fake.build(sid)
        view = L.build_filter_view(sc["pool"], (1, 2, 3), COUNT)
        for html in (R.exp0_html(view, False), R.exp2_html(view, False), R.exp7_html(view, False)):
            assert f'data-pool-size="{size}"' in html
            assert (W.text("pool_empty_marker") in html) is (size == "0")                  # 只有空池帶標記
            assert (html.count('data-marker="pool-empty"') == 1) is (size == "0")
    views = {s: L.build_filter_view(fake.build(s)["pool"], (1, 2, 3), COUNT) for s in ("empty_pool", "no_match")}
    for render in (R.exp0_html, R.exp2_html):                    # EXP-0／EXP-2：拿掉標記後，可見文字與零符合完全相同
        assert re.sub(r"<[^>]+>", "", _without_pool_marker(render(views["empty_pool"], False))) == \
               re.sub(r"<[^>]+>", "", render(views["no_match"], False))
    # EXP-7：各列的檔數是真實數字（0 vs 4 等），本來就會不同；把所有數字遮掉、拿掉標記後，可見文字（欄位名稱、字樣）必須相同
    t7 = [re.sub(r"\d+", "#", re.sub(r"<[^>]+>", "|", _without_pool_marker(R.exp7_html(views[s], False)))) for s in ("empty_pool", "no_match")]
    assert t7[0] == t7[1]
    css = re.sub(r"\s+", "", R.CSS)
    assert '.uv3-card[data-pool-size="0"]{border-style:dashed;background:' in css          # 空池：虛線框＋灰底
    grey_bg = R.theme.m("color.tone.grey")["background"]
    assert f'.uv3-card[data-pool-size="0"]{{border-style:dashed;background:{grey_bg}}}'.replace(" ", "") in css
    text2 = R.theme.v("color.text.secondary")                                               # DEC-03：邊框色改用既有 token（不新增色票）
    assert f'.uv3-card[data-pool-size="0"]{{border-color:{text2}}}' in css
    assert '.fs-fund[data-row-state="undetermined"]{border-style:dashed}' in css           # 整檔無法判定列：虛線框
    assert 'data-pool-size' not in R.exp0_html(None, True) and 'data-pool-size' not in R.exp2_html(None, True)   # 來源失敗不標池大小
    assert 'data-marker' not in R.exp0_html(None, True) and 'data-marker' not in R.exp7_html(None, True)         # 來源失敗≠空池：不標記


def test_pool_empty_marker_is_pending_symbol_plus_text_and_never_hints_at_failure_or_missing_source():
    item = W.FUND_SEARCH_PENDING["pool_empty_marker"]
    assert item.status == "pending" and item.source == W.SOURCE_DEC03 == W.SOURCE_DEC1118       # 2026-11-18 客戶指示定稿(待核)：出處改為 DEC-2026-11-18-01 轉述句
    assert "DEC-2026-11-18-01" in item.source and "待核" in item.source and "仍是 PendingWording" in item.source and "不進 rules.py" in item.source
    assert "執行組暫擬" not in item.source and "待 ChatGPT／客戶確認定字" not in item.source
    assert item.text[0] == "○" and len(item.text) > 2                                      # 符號＋短語；不是只有符號
    assert not any(w in item.text for w in ("失敗", "缺", "來源", "不存在", "查無", "無法判定", "資料未備"))   # 空池≠失敗≠來源缺失≠無法判定
    assert not any(c in item.text for c in "◆◇⬜⛔◷")                                       # 不借用規則表狀態符號
    assert 'data-pending-wording="pool_empty_marker"' in W.pending("pool_empty_marker")


def test_pool_marker_only_appears_when_the_pool_is_known_to_be_empty():
    for conds, expect in (((1, 2, 3), True), ((1,), True), ((), False)):          # 零條件沒有軌跡、無從得知池大小 → 不標
        html, view = _exp_html("empty_pool", conds)
        assert ('data-marker="pool-empty"' in html) is expect, conds
    html, view = _exp_html("no_match", (1, 2, 3))
    assert 'data-marker' not in html


def test_zero_conditions_never_shows_a_pool_size_or_counts_even_for_the_empty_pool():
    html, view = _exp_html("empty_pool", ())
    assert "data-pool-size" not in html and 'data-counts-shown="no"' in html and view.trace == ()


def test_exp7_columns_are_the_fake_preview_four_and_zero_conditions_say_only_the_no_condition_text():
    """FAKE 專屬（執行組／ChatGPT UI 設計方向的四格：條件、套用前、符合、無法判定；見提示語，repo 無逐字存檔，NOT VERIFIED；DEC-2026-11-17-02 (e) 待裁），**不是** frozen 44 §EXP-7 的三欄（條件文字／套用前檔數／套用後檔數），
    也不升格正式 EXP-7 契約；零條件時 44 寫『來源缺＋尚未設定條件』，本預覽只寫『尚未設定條件』，不含『來源缺』（兩者差異列為待 Gate，見 README『EXP-7 規則對照』）。"""
    html, view = _exp_html("mixed", (1, 2, 3))
    exp7 = html[html.index('data-block="exp7"'):]
    labels = re.findall(r'<span class="uv3-label"[^>]*>(?:<span[^>]*>)?([^<]+)</span>', exp7)
    assert labels == [W.text("col_cond"), W.text("col_before"), W.text("col_matched"), W.text("col_undetermined")] * len(view.trace)
    assert re.findall(r'data-col="([a-z]+)"', exp7) == ["cond", "before", "matched", "undetermined"] * len(view.trace)
    assert "套用後檔數" not in html and "來源缺" not in html
    zero, _ = _exp_html("mixed", ())
    assert exp_counts.TEXT_NO_CONDITION in zero and "來源缺" not in zero


@pytest.mark.parametrize("raw", ["---", "123", "AAA", "-A-"])
def test_code_shape_is_a_heuristic_so_dash_or_digit_only_input_is_no_fixture(raw):
    """現況揭露（不改行為）：`_CODE_SHAPE` 只看字元集與長度，這類輸入也會判 no_fixture（⬜ 無法判定，不是『不存在』）；『輸入類型』列已於 DEC-2026-11-18-01 移除。"""
    r = L.classify_lookup(raw, fake.LOOKUP_FIXTURES)
    assert r.outcome == L.OUT_NO_FIXTURE
    html = R.lookup_card_html(r, fake.FAKE_FOUND_NAME)
    assert 'data-status-key="undetermined"' in html and 'data-row="input-type"' not in html


def test_exp7_cells_grid_is_auto_fit_and_never_forced_to_four_columns_g5():
    """G-5：手機可換行、不強制四欄橫排——格線是 auto-fit＋minmax，不得寫死 repeat(4, …)／固定欄數；瀏覽器守衛另量 390 實際換行。"""
    css = re.sub(r"\s+", "", R.CSS)
    assert ".fs-cells{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,150px),1fr))" in css
    assert not re.search(r"grid-template-columns:repeat\(\d", css) and "flex-wrap:nowrap" not in css


# ───────────────────────── 2026-11-18 C 線：取數失敗不得說基金不存在（DEC-2026-11-18-01 第 6 點） ─────────────────────────

def test_failed_lookup_says_only_the_fetch_failed_sentences_and_draws_no_profile_rows():
    html = _card("FAKE-ERR1")
    assert W.text("fail_not_identity") == "這次取數失敗，不是對基金身份的判斷" and W.text("fail_not_identity") in html
    assert "⛔ 取數失敗" in html and W.text("fail_impact") in html
    assert S.forbidden_word_violations(html) == [] and S.lookup_field_violations(html) == []
    assert re.findall(r'data-row="([^"]+)"', html) == ["result", "input-code"]          # 失敗：只有狀態訊息與輸入代碼，不畫基金名稱等欄位


def test_mutation_failed_card_that_claims_the_fund_does_not_exist_turns_the_wording_guard_red(monkeypatch):
    """對 production 字樣變異：把失敗句換成『基金不存在』類說法，禁用字樣守衛必須報紅（未變異時為空）。"""
    from ui_v3.viewmodels.preview_wording import PendingWording
    assert S.forbidden_word_violations(_card("FAKE-ERR1")) == []
    for claim in ("這檔基金不存在", "查無基金", "查無此代碼"):
        mutated = dict(W.FUND_SEARCH_PENDING)
        mutated["fail_not_identity"] = PendingWording("fail_not_identity", claim, W.SOURCE)
        monkeypatch.setattr(W, "FUND_SEARCH_PENDING", mutated)
        assert S.forbidden_word_violations(_card("FAKE-ERR1")), claim
        monkeypatch.undo()
