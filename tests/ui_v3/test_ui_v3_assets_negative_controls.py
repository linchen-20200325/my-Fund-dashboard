# -*- coding: utf-8 -*-
"""💼 我的資產｜「反控制」（negative-control）測試：同一個可見畫面，不同的上游證據，能不能被分辨？

三組，全部是純函式層（不需要瀏覽器；瀏覽器級見 `tests/poc_assets_preview/test_assets_preview_negative_browser.py`）。資料全是人造 FAKE：

A. 畫面層：含假成本／假持倉／NAV 過期／匯率缺／金額為 0 的輸入，畫面不得出現任何金額字樣，缺值一律走缺值字樣、不得變成 0；
   「來源已讀完」只准出現在真的讀完的兩個狀態。
B. 上游差分（載入端）：`assets_source` 對「略過分頁／略過列／未提供／無 Active／讀取失敗」要能各自留下可分辨的證據。
C. C-13 已知缺口的鎖：L2 其他略過群組（孤兒、重複、壞列等）不進證據，載入端結果與全乾淨的上游**逐位元相同**，
   一路到畫面都顯示「來源已讀完」。這是**如實鎖住現狀**，不是核准；日後有人讓載入端能分辨它們，這幾條會轉紅，屆時須同步更新
   `docs/evidence/open_items_ledger_2026_11_20.md` 的 C-13 列與本檔，而不是把測試改綠了事。

負控一律在記憶體內現編，不寫檔、不改任何 production 檔。
"""
from __future__ import annotations

import copy
import html
import json
import re
import secrets

import pytest

import assets_page_support as sup
import assets_source_support as X
from services.v2_tables import alo_holdings as A
from shared.ui_semantics import rules
from ui_v3.adapters import assets_source as M
from ui_v3.adapters.assets_page import build_assets_page
from ui_v3.pages.assets import page_html

MISSING = rules.entry("missing").wording


def visible(h: str) -> str:
    h = re.sub(r"<style.*?</style>", "", h, flags=re.S)
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "|", h)))


def page_of(result) -> str:
    return page_html(build_assets_page(result))


def state_of(h: str) -> str:
    m = re.search(r'data-source-state="([^"]+)"', h)
    assert m, "頁面必須帶 data-source-state"
    return m.group(1)


# ═══════════════ A. 畫面層：假成本／假持倉／NAV 過期／匯率缺 ═══════════════

SENTINELS = (sup.SENTINEL_COST_TWD, sup.SENTINEL_COST_ORIG, sup.SENTINEL_HOLDING_VALUE, sup.SENTINEL_CATEGORY_VALUE, sup.SENTINEL_SHARE_PCT)


def _forms(x: float) -> list[str]:
    """一個哨兵數字可能被畫成的字串形態（原值、千分位、整數、去小數）。"""
    i = int(x)
    out = {repr(x), str(x), f"{x:,}", f"{x:,.2f}", f"{x:,.0f}", str(i), f"{i:,}"}
    return sorted((f for f in out if len(f) >= 5 or "." in f), key=len, reverse=True)   # 太短的整數形態（33）太容易誤中，不當證據


def _stale_fx_missing_row(n=1):
    return sup.fake_holding(n, nav={"status": "stale"}, nav_state="stale", fx={"status": "missing"}, value_status="missing",
                            value_twd=None, valued=False, errors=["nav_stale", "fx_missing"])


def _zero_money_row(n=1):
    return sup.fake_holding(n, cost_twd=0, cost_orig_ccy=0, value_twd=0, value_status="missing", valued=False)


def _none_money_row(n=1):
    return sup.fake_holding(n, cost_twd=None, cost_orig_ccy=None, value_twd=None, value_status="missing", valued=False)


ROW_VARIANTS = {
    "valued_with_sentinels": lambda: sup.fake_holding(1),
    "nav_stale_fx_missing": _stale_fx_missing_row,
    "money_zero": _zero_money_row,
    "money_none": _none_money_row,
}


def _row_page(variant: str, n_rows: int = 2) -> str:
    rows = [ROW_VARIANTS[variant]() for _ in range(1)] + [sup.fake_holding(i) for i in range(2, n_rows + 1)]
    return page_of(sup.fake_result(evidence=sup.fake_evidence(holdings=rows)))


@pytest.mark.parametrize("variant", sorted(ROW_VARIANTS))
def test_no_cost_value_or_share_number_ever_reaches_the_page_whatever_the_row_says(variant):
    text = visible(_row_page(variant))
    for s in SENTINELS:
        for form in _forms(s):
            assert form not in text, (variant, form)
    for bad in ("NaN", "None", "null", "inf", "undefined"):
        assert bad not in text, (variant, bad)
    assert "%" not in text and "NT$" not in text and "$" not in text, variant   # 沒有比例、沒有貨幣符號


@pytest.mark.parametrize("variant", sorted(ROW_VARIANTS))
def test_the_four_summary_cells_stay_missing_never_zero_even_when_rows_carry_zero_or_none_money(variant):
    h = _row_page(variant)
    a20 = h[h.index('data-block="a20"'):h.index('data-block="a50"')] if 'data-block="a50"' in h else h[h.index('data-block="a20"'):]
    assert a20.count('data-status-key="missing"') == 4, variant
    assert visible(a20).count(MISSING) >= 4, variant
    assert not re.search(r">\s*0(\.0+)?\s*<", a20), variant   # 四格沒有任何一個以 0 代替缺值


def test_zero_money_row_does_not_change_anything_the_user_can_see_except_through_units():
    base = visible(_row_page("valued_with_sentinels"))
    for variant in ("money_zero", "money_none"):
        assert visible(_row_page(variant)) == base, variant   # 金額欄不進畫面：0 與 None 與有值，畫面逐字相同


def test_known_gap_nav_stale_and_fx_missing_are_invisible_to_the_page():
    """⚠️ 已知落差（如實鎖住，不是核准）：頁面沒有逐檔 NAV／匯率面向，列上 nav=stale、fx=missing、value 缺，畫面與正常列**逐字相同**。
    不會畫出假數字（金額欄全不進畫面、四格恆為缺值），但使用者**看不到『為什麼沒有金額』的逐檔原因**。
    日後若加了逐檔 NAV／匯率的缺項呈現（需線框與字樣核准），此條應轉紅，屆時改寫為『stale／missing 要如實標示』。"""
    assert visible(_row_page("nav_stale_fx_missing")) == visible(_row_page("valued_with_sentinels")), "缺口若已補好，請更新 docs/evidence/open_items_ledger_2026_11_20.md C-13 列與 Gate G1，並同步調整本鎖，不得單純改綠"


def test_negative_control_the_leak_forms_detector_fires_on_an_injected_sentinel():
    """注入正控：執行時隨機產生的哨兵注入文字後，`_forms` 產生的任一形態都必須命中；乾淨輸入 0 命中。"""
    token = float(secrets.randbelow(10**9) + 10**9) + 0.5
    forms = _forms(token)
    assert forms, "哨兵必須至少產生一個可比對形態"
    injected = visible(f"<p>x {token:,.2f} y</p>")
    assert any(f in injected for f in forms)
    assert not any(f in visible("<p>x 1 y</p>") for f in forms)


def test_basis_value_shown_is_exactly_what_the_evidence_says_never_invented():
    """基準字樣只來自證據的設定；改證據就改畫面（差分），未設定時不顯示值（不編一個預設）。"""
    token = "ZZ-BASIS-" + secrets.token_hex(6)   # 每次執行隨機產生的哨兵，不寫死、不入庫
    shown = visible(page_of(sup.fake_result(evidence=sup.fake_evidence(holdings=[sup.fake_holding(1)], basis_value=token))))
    assert token in shown
    unset = visible(page_of(sup.fake_result(evidence=sup.fake_evidence(holdings=[sup.fake_holding(1)], basis_status="unset"))))
    assert token not in unset and "成本" not in unset


def test_market_blocked_page_shows_no_holdings_no_basis_value_and_no_fake_marker_in_the_card():
    h = page_of(sup.market_blocked_result())
    t = visible(h)
    assert state_of(h) == "not_read"
    assert "基金名稱" not in t and "單位數" not in t and "成本" not in t
    assert 'data-block="a50"' not in h or "完整持倉" in t   # 不畫列容器（status-only 一行）
    assert not re.search(r"\b\d{3,}\b", t)                   # 沒有任何三位數以上的數字（沒有金額、沒有單位數）


# ───────── 「來源已讀完」只准出現在真的讀完的狀態 ─────────

def _all_states():
    return {
        "complete": sup.complete_result(2),
        "complete_no_rows": sup.complete_no_rows_result(),
        "partial": sup.partial_result(),
        "no_active": sup.no_active_result(),
        "read_failed": sup.read_failed_result(),
        "unprovided_skip": sup.complete_with_unprovided_skip_evidence_result(rows=1),
        "skip_items_but_complete": sup.complete_with_skip_items_result("skipped_tabs"),
        "unknown_coverage": sup.unknown_coverage_result(),
        "market_blocked": sup.market_blocked_result(),
    }


def _a00_word(result) -> str:
    """A00 來源狀態字樣（取頁面實際輸出，不在測試裡硬寫第二份字串）。"""
    tokens = [t.strip() for t in visible(page_of(result)).split("|") if t.strip()]
    return tokens[tokens.index("來源") + 1]


def test_read_done_wording_appears_only_in_the_two_truly_complete_states():
    word = _a00_word(sup.complete_result(2))
    assert _a00_word(sup.complete_no_rows_result()) == word
    others = {k: _a00_word(v) for k, v in _all_states().items() if k not in ("complete", "complete_no_rows")}
    assert word not in others.values(), others


def test_every_upstream_state_has_its_own_source_state_key_and_distinct_visible_status():
    pages = {k: page_of(v) for k, v in _all_states().items()}
    keys = {k: state_of(h) for k, h in pages.items()}
    assert keys["complete"] != keys["no_active"] != keys["read_failed"] != keys["market_blocked"]
    assert len({keys[k] for k in ("complete", "complete_no_rows", "partial", "no_active", "read_failed", "market_blocked")}) == 6
    first = {k: visible(h)[:40] for k, h in pages.items() if k in ("no_active", "read_failed", "market_blocked", "unprovided_skip")}
    assert len(set(first.values())) >= 3, first   # 未選定／失敗／未讀／無法判定不得長得一樣（unprovided_skip 與 market_blocked 同為『無法判定』是既有口徑）


def _after(result, label: str) -> str:
    toks = [t.strip() for t in visible(page_of(result)).split("|") if t.strip()]
    return toks[toks.index(label) + 1]


def test_missing_skip_evidence_is_never_shown_as_zero_skipped():
    """略過件數：來源沒提供 → 缺值字樣；提供了且為 0 → 數字 0。兩者不得互換（差分）。"""
    provided = sup.complete_result(1)
    unprovided = sup.complete_with_unprovided_skip_evidence_result(rows=1)   # omitted_rows 未提供
    assert _after(provided, "略過列數") == "0"
    assert _after(unprovided, "略過列數") == MISSING and _after(unprovided, "略過分頁數") == "0"


def test_failure_code_and_raw_error_text_never_reach_the_page():
    for code in ("NETWORK_ERROR", "PERMISSION_DENIED", "SCHEMA_INVALID"):
        t = visible(page_of(sup.read_failed_result(code)))
        assert code not in t and "Traceback" not in t


# ═══════════════ B. 上游差分：載入端對各種上游狀態要留下可分辨的證據 ═══════════════

def _load(tables=None, *, holding_exc=None, basis="成本"):
    reads, _ = X.make_reads(M, holdings=tables, holding_exc=holding_exc, settings=X.settings_payload(X.settings_rows(basis=basis)))
    return M.load({}, [X.SECRET], reads=reads)


def _tabs(extra_supp=(), supp_missing=False):
    return X.tabs_of([X.srec(2, code="ZZ1"), X.srec(3, code="ZZ2", bucket="sat"), *extra_supp], [X.precd(2)], supp_missing=supp_missing)


def _rows():
    return [X.prow(row=2, code="ZZ1", invest=300000), X.prow(row=3, code="ZZ2", invest=100000)]


def _clean():
    return A.build_alo_tables(_rows(), _tabs())


def _coverage(result) -> tuple:
    p = result.to_primitive()["evidence"]
    return p["source_coverage"]["status"], tuple(p["source_coverage"]["reason_codes"])


def test_positive_control_skipped_holdings_make_the_evidence_differ_from_a_clean_source():
    dirty = A.build_alo_tables(_rows(), X.tabs_of([X.srec(2, code="ZZ1")], [X.precd(2)]))   # ZZ2 缺持倉補充 → skipped_holdings
    assert len(dirty["skipped_holdings"]) == 1 and not _clean()["skipped_holdings"]
    assert _coverage(_load(_clean())) == ("complete", ())
    status, codes = _coverage(_load(dirty))
    assert status == "incomplete" and codes, (status, codes)


def test_positive_control_skipped_tabs_make_the_evidence_differ_from_a_clean_source():
    dirty = A.build_alo_tables(_rows(), _tabs(), skipped_tabs=[{"tab": "PX-OTHER", "error": "read failed"}])
    status, codes = _coverage(_load(dirty))
    assert status == "incomplete" and codes, (status, codes)


def test_positive_control_unprovided_skip_keys_are_not_the_same_as_empty_lists():
    """缺 skipped_* 鍵（不知道）≠ 空 list（讀過、沒有略過）：兩者的證據必須不同，缺鍵不得被當成『沒有略過』。"""
    unknown = {k: v for k, v in _clean().items() if k not in ("skipped_holdings", "skipped_tabs")}
    assert _load(unknown).to_primitive()["evidence"]["source"] != _load(_clean()).to_primitive()["evidence"]["source"]
    assert _coverage(_load(unknown))[0] != "complete"


def test_no_active_failed_and_loaded_are_three_distinguishable_results():
    no_active = _load(holding_exc=X.FakeActiveSourceError("AUTH_REQUIRED"))
    failed = _load(holding_exc=X.FakeActiveSourceError("NETWORK_ERROR"))
    loaded = _load(_clean())
    assert no_active.problems == ("no_active_source",) and failed.problems == ("holding_read_failed",) and loaded.problems == ()
    assert failed.holding_failure_code == "NETWORK_ERROR" and no_active.holding_failure_code is None
    assert _coverage(no_active)[0] == "not_selected" and _coverage(failed)[0] == "failed" and _coverage(loaded)[0] == "complete"


def test_market_basis_is_blocked_and_never_asks_the_holding_source_or_the_producer():
    calls = []
    reads, c = X.make_reads(M, holdings=_clean(), settings=X.settings_payload(X.settings_rows(basis="市值")))
    result = M.load({}, [X.SECRET], reads=reads, producer=lambda *a, **k: calls.append(1))
    assert result.status == "blocked" and result.evidence is None and not calls and not c.holdings


def test_end_to_end_each_upstream_state_reaches_the_page_as_a_different_source_state():
    dirty = A.build_alo_tables(_rows(), X.tabs_of([X.srec(2, code="ZZ1")], [X.precd(2)]))
    pages = {
        "loaded_clean": page_of(_load(_clean()).to_primitive()),
        "loaded_with_skips": page_of(_load(dirty).to_primitive()),
        "no_active": page_of(_load(holding_exc=X.FakeActiveSourceError("AUTH_REQUIRED")).to_primitive()),
        "failed": page_of(_load(holding_exc=X.FakeActiveSourceError("NETWORK_ERROR")).to_primitive()),
    }
    assert [state_of(pages[k]) for k in ("loaded_clean", "loaded_with_skips", "no_active", "failed")] == ["complete", "partial", "not_selected", "read_failed"]


# ═══════════════ C. C-13：其他略過群組不進證據（如實鎖住現狀） ═══════════════

def _with(**extra):
    t = _clean()
    t.update(extra)
    return t


C13_OTHER_GROUPS = {
    "orphan_supplement": lambda: A.build_alo_tables(_rows(), _tabs(extra_supp=[X.srec(9, pid="PX-GONE", code="ORPH")])),
    "orphan_profile": lambda: A.build_alo_tables(_rows(), X.tabs_of([X.srec(2, code="ZZ1"), X.srec(3, code="ZZ2", bucket="sat")],
                                                                   [X.precd(2), X.precd(8, pid="PX-GONE")])),
    "invest_twd_parse_errors": lambda: A.build_alo_tables(_rows(), _tabs(), invest_twd_parse_errors=[{"tab": "PX-TEST-001", "row": 4, "raw": "x"}]),
    "bad_rows_injected": lambda: _with(bad_rows={"_持倉補充": [{"row": 5, "cells": ["?"]}]}),
    "duplicate_supplement_injected": lambda: _with(duplicate_supplement=[{"policy_id": "PX-TEST-001", "fund_code": "ZZ1", "rows": [2, 7]}]),
}


@pytest.mark.parametrize("name", sorted(C13_OTHER_GROUPS))
def test_known_gap_c13_other_skip_groups_leave_evidence_identical_to_a_clean_upstream(name):
    """C-13（FACT，如實鎖住，不是核准）：上游與乾淨來源**不同**（本群組非空），但載入端結果的證據**逐位元相同**、coverage=complete。
    所以僅憑 `assets_source` 的輸出，無法分辨『來源整體無拒收』與『有其他群組被略過』。"""
    dirty = C13_OTHER_GROUPS[name]()
    clean = _clean()
    assert dirty != clean   # 上游確實不同（差分的前提；若相同，這條測試沒有意義）
    assert json.dumps(_load(dirty).to_primitive(), sort_keys=True) == json.dumps(_load(clean).to_primitive(), sort_keys=True), (name, "缺口若已補好，請更新 docs/evidence/open_items_ledger_2026_11_20.md C-13 列與 Gate G1，並同步調整本鎖，不得單純改綠")
    assert _coverage(_load(dirty)) == ("complete", ()), (name, "缺口若已補好，請更新 docs/evidence/open_items_ledger_2026_11_20.md C-13 列與 Gate G1，並同步調整本鎖，不得單純改綠")


def test_known_gap_c13_the_user_sees_the_same_complete_page_for_clean_and_other_group_skips():
    clean_page = page_of(_load(_clean()).to_primitive())
    for name, build in C13_OTHER_GROUPS.items():
        dirty_page = page_of(_load(build()).to_primitive())
        assert dirty_page == clean_page, (name, "缺口若已補好，請更新 docs/evidence/open_items_ledger_2026_11_20.md C-13 列與 Gate G1，並同步調整本鎖，不得單純改綠")
        assert state_of(dirty_page) == "complete", (name, "缺口若已補好，請更新 docs/evidence/open_items_ledger_2026_11_20.md C-13 列與 Gate G1，並同步調整本鎖，不得單純改綠")


def test_c13_other_groups_do_not_hide_the_two_groups_that_are_forwarded():
    """C-13 的另一半：被承接的兩組（skipped_holdings、skipped_tabs）疊在其他群組上時，仍然會改變證據（不會被『其他群組』蓋掉）。"""
    t = C13_OTHER_GROUPS["orphan_supplement"]()
    t = copy.deepcopy(t)
    t["skipped_holdings"] = [{"tab": "PX-TEST-001", "row": 3, "policy_id": "PX-TEST-001", "fund_code": "ZZ2", "reasons": ["缺持倉補充"]}]
    assert _coverage(_load(t))[0] == "incomplete"
