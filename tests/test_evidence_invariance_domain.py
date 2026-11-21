# -*- coding: utf-8 -*-
"""C 線（known-gap 防回歸）：Complete Evidence 離線「證據不變性」正反控制（只加測試，不改任何 production 檔）。

依據：#1296 槽 C；`docs/evidence/open_items_ledger_2026_11_20.md` C-13；BL-0527／D2-G2。全離線：不碰 Google／NAS／MoneyDJ／FX。

三層：
1. 域層（`services.v2_domain.allocation_evidence`，不經 UI）：同一組可見持倉＋同一時鐘，只改 orphan／skipped、或只改
   NAV stale／FX missing／NAV 未評估 → 域事實（Evidence）必須不同、未知值不得變成 0；只換順序 → 排序後域事實不變。
2. 離線 producer（`services.v2_tables.alo_holdings.build_alo_tables`）餵成本基準：skipped 群組穿過 Evidence。
3. UI 轉接層 known-gap（C-13）：NAV stale／FX missing 在現況**無法**穿透 `ui_v3/adapters/assets_source.py`；
   本檔把「現況邊界」與「期望的修復行為」分開釘死，後者標 xfail(strict)。**不是 C-13 已修好，也不是 bug fix**；
   任何會改 Evidence 語意／契約的修復須先經 BL-0527／D2-G2 Gate。
"""
from __future__ import annotations

import copy
import dataclasses
import pathlib
import sys

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[1]
for _p in (str(_ROOT), str(_ROOT / "tests"), str(_ROOT / "tests" / "ui_v3")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import _alo_core_golden as G  # noqa: E402
from services.v2_domain import allocation_evidence as E  # noqa: E402
from ui_v2.alo import logic as L  # noqa: E402

MV, COST = G.MV, G.COST
H, N, FX, DS, NNR = G.H, G.N, G.FX, G.DS, G.NNR
LEDGER = "docs/evidence/open_items_ledger_2026_11_20.md C-13"
GATE = "BL-0527/D2-G2"

NAV_A = N("A", "2026-10-03", 10.0, "USD")
NAV_B = N("B", "2026-10-03", 20.0, "TWD")
FX_USD = FX(L.fx_key_for("USD"), "2026-10-03", 30.0)


def _holdings():
    return [H("A", ccy="USD"), H("B", bucket=G.SAT, ccy="TWD")]


def _build(ds, *, nnr=None, source=None, nav_input_state=None):
    st = {"basis": ds["_basis"], "targets": G.TARGETS, "tolerance": 5.0, "bucket_names": list(G.NAMES)}
    tables = {k: v for k, v in ds.items() if k != "_basis"}
    return E.build_allocation_evidence(
        tables, settings=st, nav_not_ready=nnr, fx_key_of=L.fx_key_for,
        basis_mode_of=lambda b: E.BasisMode(market=(b != COST), track_stale=(b == MV)),
        source_state=source if source is not None else {"active_source": "selected", "errors": {}},
        nav_provenance=None, fx_rule_verified=True, nav_input_state=nav_input_state)


def _mv(holdings=None, nav=(NAV_A, NAV_B), fx=(FX_USD,), **kw):
    ds = DS(_holdings() if holdings is None else holdings, list(nav), list(fx), basis=MV)
    ds["_basis"] = MV
    return _build(ds, **kw)


def _cost(holdings=None, **kw):
    ds = DS(_holdings() if holdings is None else holdings, basis=COST)
    ds["_basis"] = COST
    return _build(ds, **kw)


def _prim(ev):
    return E.to_primitive(ev)


def _by_code(prim, code):
    return next(h for h in prim["holdings"] if h["fund_code"] == code)


def _canonical(prim):
    """排序後的域事實（只抹掉「呈現順序」，不抹掉任何事實）。"""
    out = copy.deepcopy(prim)
    out["holdings"] = sorted(out["holdings"], key=lambda h: str(h["holding_id"]))
    out["categories"] = sorted(out["categories"], key=lambda c: str(c["category"]))
    out["coverage"]["covered_categories"] = sorted(out["coverage"]["covered_categories"])
    return out


def _changed_top_keys(a, b):
    return sorted(k for k in a if a[k] != b[k])


def _unknown_as_zero(prim):
    """未知被當成 0 的違規：status 不是 valued 的持倉，value_twd 必須是 None；分母 None 時不得有數字。"""
    bad = [h["fund_code"] for h in prim["holdings"] if h["value_status"] != "valued" and h["value_twd"] is not None]
    if prim["denominator"]["value_twd"] is None and prim["coverage"]["covered_value_twd"] not in (None,):
        bad.append("coverage_with_unknown_denominator")
    return bad


# ═══════════════════ 1. 域層：Evidence 對「資料事實」敏感 ═══════════════════


def test_market_basis_baseline_is_complete_and_has_no_unknown_as_zero():
    base = _prim(_mv())
    assert base["valuation_completeness"]["status"] == "complete"
    assert _unknown_as_zero(base) == []


def test_fx_missing_changes_evidence_and_unknown_is_none_not_zero():
    base, nofx = _prim(_mv()), _prim(_mv(fx=()))
    assert base != nofx, f"FX missing 必須改變域事實（{LEDGER}）"
    a = _by_code(nofx, "A")
    assert a["value_status"] == "missing" and a["value_twd"] is None, "FX 缺失的持倉金額必須是 None，不得是 0"
    assert a["reason"]["code"] == "fx_absent"
    assert nofx["valuation_completeness"]["status"] == "incomplete"
    assert nofx["valuation_completeness"] != base["valuation_completeness"]
    assert _by_code(nofx, "B")["value_twd"] == 200.0, "不缺 FX 的 TWD 持倉不受牽連"
    assert _unknown_as_zero(nofx) == []


def test_nav_stale_changes_evidence_and_is_distinct_from_fx_missing():
    stale = _prim(_mv(nav=(NAV_B,), nnr=NNR(["A"], days=10, last={"A": "2026-09-01"})))
    fxmiss = _prim(_mv(fx=()))
    a = _by_code(stale, "A")
    assert a["value_twd"] is None and a["nav_state"] == "obtained_rejected" and a["reason"]["code"] == "nav_stale"
    assert _by_code(fxmiss, "A")["reason"]["code"] == "fx_absent"
    assert _by_code(stale, "A")["reason"] != _by_code(fxmiss, "A")["reason"], "兩種缺值原因必須可被域事實區分"
    assert stale != _prim(_mv())
    assert _unknown_as_zero(stale) == []


def test_nav_row_absent_without_declaration_is_cause_unknown_not_no_data():
    ev = _prim(_mv(nav=(NAV_B,)))
    a = _by_code(ev, "A")
    assert (a["value_twd"], a["nav_state"], a["reason"]["code"]) == (None, "cause_unknown", "nav_absent")


def test_nav_not_assembled_means_not_evaluated_everywhere_and_never_zero():
    ev = _prim(_mv(nav_input_state="not_assembled"))
    assert all(h["value_twd"] is None and h["nav_state"] == "not_assembled" for h in ev["holdings"])
    assert ev["valuation_completeness"] == {"status": "not_evaluated", "reason_codes": ["nav_not_assembled"]}
    assert ev["denominator"]["value_twd"] is None and ev["coverage"]["covered_value_twd"] is None
    assert ev["chart_comparability"]["status"] != "comparable"
    assert _unknown_as_zero(ev) == []


def test_orphan_skipped_changes_evidence_and_unknown_amount_stays_unknown():
    clean = _prim(_cost(source={"active_source": "selected", "errors": {}, "skipped_tabs": [], "skipped_holdings": []}))
    skipped = _prim(_cost(source={"active_source": "selected", "errors": {}, "skipped_tabs": [{"tab": "PX-X", "error": "e"}],
                                  "skipped_holdings": [{"tab": "P1", "row": 9, "fund_code": "Z", "reasons": ["r"]}]}))
    assert clean != skipped and "source" in _changed_top_keys(clean, skipped)
    assert clean["source_coverage"]["status"] == "complete"
    assert skipped["source_coverage"]["status"] != "complete"
    # 未涵蓋金額：不可算，絕不是 0
    assert skipped["coverage"]["uncovered_value"]["status"] == "not_evaluated"
    assert skipped["coverage"]["uncovered_value"]["status"] != "none_uncovered"
    assert skipped["denominator"]["skipped_tab_count"] == 1 and skipped["denominator"]["omitted_row_count"] == 1
    assert _unknown_as_zero(skipped) == []


def test_unprovided_skipped_groups_are_not_the_same_as_provided_empty():
    """C-13 反控制語意：『兩組為空』與『兩組根本沒提供』是不同事實，不得互相推導。"""
    provided_empty = _prim(_cost(source={"active_source": "selected", "errors": {}, "skipped_tabs": [], "skipped_holdings": []}))
    not_provided = _prim(_cost(source={"active_source": "selected", "errors": {}}))
    assert provided_empty["source"] != not_provided["source"]
    assert provided_empty["source_coverage"]["status"] == "complete"
    assert not_provided["source_coverage"]["status"] != "complete", "未提供略過群組不得被讀成『來源整體無拒收』"


# ═══════════════════ 1b. 域層：呈現型變因不改事實 ═══════════════════


def test_row_order_and_repeat_calls_do_not_change_domain_facts():
    fwd = _prim(_mv(holdings=_holdings()))
    rev = _prim(_mv(holdings=list(reversed(_holdings()))))
    assert _canonical(fwd) == _canonical(rev)
    assert _prim(_mv()) == _prim(_mv()), "同輸入重算必須逐欄相同（時鐘固定、無隱性狀態）"


def test_inputs_are_not_mutated_by_evidence_build():
    ds = DS(_holdings(), [NAV_A, NAV_B], [FX_USD], basis=MV)
    ds["_basis"] = MV
    before = copy.deepcopy(ds)
    _build(ds)
    assert ds == before


# ═══════════════════ 負控：檢查器本身不空轉 ═══════════════════


def test_negative_control_unknown_as_zero_detector_fires_on_a_zero_filled_mutant():
    mutant = _prim(_mv(fx=()))
    _by_code(mutant, "A")["value_twd"] = 0.0           # 手工把未知填成 0
    assert _unknown_as_zero(mutant) == ["A"]


def test_negative_control_sensitivity_detector_fires_when_a_fact_is_hidden():
    base = _prim(_mv(fx=()))
    hidden = copy.deepcopy(base)
    hidden["holdings"][0]["reason"] = None             # 假想的「原因被投影丟失」
    assert base != hidden and _by_code(hidden, "A")["reason"] is None


def test_negative_control_order_canonicalizer_does_not_mask_a_real_fact_change():
    fwd = _prim(_mv())
    changed = _prim(_mv(fx=()))
    assert _canonical(fwd) != _canonical(changed)


# ═══════════════════ 2. 離線 producer（v2_tables）→ Evidence ═══════════════════


def _producer_tables(skipped_tabs=None, drop_supplement_for=None):
    import assets_source_support as X
    from services.v2_tables import alo_holdings as A
    rows = [X.prow(row=2, code="ZZ1", invest=300000), X.prow(row=3, code="ZZ2", invest=100000)]
    supp = [X.srec(2, code="ZZ1", bucket="core")]
    if drop_supplement_for != "ZZ2":
        supp.append(X.srec(3, code="ZZ2", bucket="sat"))
    return A.build_alo_tables(rows, X.tabs_of(supp, [X.precd(2)]), skipped_tabs=list(skipped_tabs or []))


def _evidence_from_producer(out):
    st = {"basis": COST, "targets": G.TARGETS, "tolerance": 5.0, "bucket_names": ["core", "sat"]}
    src = {"active_source": "selected", "errors": {}, "skipped_tabs": out.get("skipped_tabs"),
           "skipped_holdings": out.get("skipped_holdings")}
    return _prim(E.build_allocation_evidence(
        {"holding": out["holding"]}, settings=st, nav_not_ready=None, fx_key_of=L.fx_key_for,
        basis_mode_of=lambda b: E.BasisMode(market=(b != COST), track_stale=False), source_state=src, fx_rule_verified=True))


def test_v2_tables_producer_orphan_difference_reaches_evidence():
    full = _evidence_from_producer(_producer_tables())
    orphan = _evidence_from_producer(_producer_tables(drop_supplement_for="ZZ2", skipped_tabs=[{"tab": "PX-O", "error": "e"}]))
    assert full != orphan
    assert full["source_coverage"]["status"] == "complete" and orphan["source_coverage"]["status"] != "complete"
    assert len(orphan["holdings"]) < len(full["holdings"]), "被略過的持倉不得以 0 金額留在可見持倉內"
    assert orphan["coverage"]["uncovered_value"]["status"] == "not_evaluated"


# ═══════════════════ 3. UI 轉接層（C-13 known-gap） ═══════════════════


def _ui_modules():
    import assets_source_support as X
    from ui_v3.adapters import assets_page as P
    from ui_v3.adapters import assets_source as M
    return X, M, P


def _page_dict(tables):
    X, M, P = _ui_modules()
    stage = M.settings_stage(M.SettingsOutcome("loaded", X.settings_rows(), ()))
    res = M.evaluate(stage, M.HoldingOutcome("loaded", tables=tables), mask=X.mask, fx_key_of=lambda c: c, fx_rule_verified=True)
    return res, dataclasses.asdict(P.build_assets_page(res.to_primitive()))


def test_ui_adapter_carries_skipped_groups_into_page_facts():
    """現況（可通過）：skipped 兩組穿過轉接層，頁面來源狀態由 complete 變 partial，且件數是事實。"""
    X, _M, _P = _ui_modules()
    _r1, clean = _page_dict(X.two_fund_tables())
    _r2, skipped = _page_dict(X.tables_with_skips())
    assert clean["a00"]["source_state"] == "complete" and skipped["a00"]["source_state"] == "partial"
    assert (skipped["a60"]["skipped_tab_count"], skipped["a60"]["skipped_row_count"]) == (1, 1)
    assert clean["a60"]["skipped_tab_count"] == 0


def test_ui_presentation_only_changes_do_not_change_source_facts():
    """換欄位順序／持倉順序：a00、a10、a20、a60 的事實區塊不變（a50 的 ordinal 本就隨順序）。"""
    X, M, P = _ui_modules()
    tables = X.two_fund_tables()
    swapped = dict(tables, holding=list(reversed(tables["holding"])))
    _r, fwd = _page_dict(tables)
    _r, rev = _page_dict(swapped)
    for block in ("a00", "a10", "a20", "a60"):
        assert fwd[block] == rev[block], block
    stage = M.settings_stage(M.SettingsOutcome("loaded", X.settings_rows(), ()))
    res = M.evaluate(stage, M.HoldingOutcome("loaded", tables=tables), mask=X.mask, fx_key_of=lambda c: c, fx_rule_verified=True)
    a = dataclasses.asdict(P.build_assets_page(res.to_primitive(), row_fields=("fund_name", "fund_code")))
    b = dataclasses.asdict(P.build_assets_page(res.to_primitive(), row_fields=("fund_code", "fund_name")))
    for block in ("a00", "a10", "a20", "a60"):
        assert a[block] == b[block], block


def test_known_gap_c13_current_boundary_nav_and_fx_side_inputs_are_dropped_at_holding_stage_inputs():
    """【現況邊界／C-13 known-gap，非 PASS 宣稱】`holding_stage_inputs` 只轉交 holding 表與 skipped_*；
    nav／market_indicator／nav_not_ready 一律不轉交 → NAV stale／FX missing 原因無法進轉接層的 Evidence。
    若此測試轉紅，代表邊界被改動：須先過 BL-0527/D2-G2 再改本檔。"""
    X, M, _P = _ui_modules()
    stage = M.settings_stage(M.SettingsOutcome("loaded", X.settings_rows(), ()))
    tables = dict(X.two_fund_tables(), nav=[NAV_A], market_indicator=[FX_USD], nav_not_ready=NNR(["A"], 10, {"A": "2026-09-01"}))
    out_tables, source_state = M.holding_stage_inputs(M.HoldingOutcome("loaded", tables=tables), stage, mask=X.mask)
    assert set(out_tables) == {"holding"}
    assert not ({"nav", "market_indicator", "nav_not_ready"} & set(source_state))


def test_known_gap_c13_market_basis_is_blocked_so_nav_fx_cause_cannot_reach_evidence():
    """【現況邊界】市值基準在轉接層直接 blocked、不呼叫生產者：NAV／FX 差異在 UI 層連成為 Evidence 的機會都沒有。"""
    X, M, _P = _ui_modules()
    stage = M.settings_stage(M.SettingsOutcome("loaded", X.settings_rows(basis=MV), ()))
    res = M.evaluate(stage, None, mask=X.mask, fx_key_of=lambda c: c, fx_rule_verified=True)
    assert res.status == M.STATUS_BLOCKED and res.evidence is None
    assert res.chart_claim == M.CHART_CLAIM_WITHHELD, "不得宣稱圖表可比"


@pytest.mark.xfail(strict=True, reason=f"C-13 known-gap：NAV stale／FX missing 差異目前不穿透 UI 轉接層；修復屬 Evidence 契約變更，須先經 {GATE}（{LEDGER}）")
def test_expected_fail_c13_nav_fx_difference_would_reach_ui_page_model():
    """【期望行為，目前 XFAIL】同一組可見持倉、只改 NAV／FX 事實 → 頁面事實應不同。現況：兩者逐欄相同。"""
    X, _M, _P = _ui_modules()
    base = dict(X.two_fund_tables(), nav=[NAV_A], market_indicator=[FX_USD])
    degraded = dict(X.two_fund_tables(), nav=[], market_indicator=[], nav_not_ready=NNR(["ZZ1"], 10, {"ZZ1": "2026-09-01"}))
    _r1, a = _page_dict(base)
    _r2, b = _page_dict(degraded)
    assert a != b
