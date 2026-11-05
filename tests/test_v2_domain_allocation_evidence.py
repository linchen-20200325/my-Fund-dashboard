# -*- coding: utf-8 -*-
"""BL-0542 G1-3: guards for `services/v2_domain/allocation_evidence.py` (CANDIDATE "Complete Evidence / Completeness" producer).

Layout:
1. `CHECKS` registry: every behavioural check is a function `check_xxx(E)` that takes the module under test. The same
   registry runs (a) against the real module here and (b) against in-memory mutants in
   `tests/test_allocation_evidence_mutations.py` (a mutant must turn at least one check red).
2. Parity with `ui_v2/alo/logic.py::_build_alo2` over every scenario of `tests/_alo_core_golden.py` (same scenarios as the
   G1-1 golden): covered / uncovered category sets, denominator, per-category value and share must equal what ui_v2 produced.
3. Purity, strict-JSON round trip (Missing stays None, never 0), lazy table reads, domain-layer guard on the new module,
   single implementation of the FX alignment rule, no ASCII-violating / Chinese constant in the module.

Scenario values are copied from the G1-1 builders; nothing here records or loosens a golden.
"""

from __future__ import annotations

import ast
import copy
import datetime
import importlib.util
import json
import math
import pathlib

import pytest

import _alo_core_golden as G

G.setup_path()

from services.v2_domain import allocation_evidence as REAL  # noqa: E402
from services.v2_domain import holdings as D  # noqa: E402
from ui_v2.alo import logic as L  # noqa: E402

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_MODULE_PATH = _ROOT / "services" / "v2_domain" / "allocation_evidence.py"

MV, COST = G.MV, G.COST
H, N, FX, DS, NNR = G.H, G.N, G.FX, G.DS, G.NNR
FX_USD, FX_EUR = G.FX_USD, G.FX_EUR
CORE, SAT, BOND = G.CORE, G.SAT, G.BOND
NAV_ALL = [N("A", "2026-10-03", 10.0, "USD"), N("B", "2026-10-03", 20.0, "TWD"), N("C", "2026-10-03", 5.0, "EUR"),
           N("D", "2026-10-03", 8.0, "USD")]


# ═══════════════════════ adapters (what a future caller would do) ═══════════════════════


def _settings_of(ds):
    st = {r["setting_key"]: r["setting_value"] for r in ds["user_setting"]}
    return {"basis": st.get("alo_basis"), "targets": st.get("alo_target_weights"),
            "tolerance": st.get("alo_tolerance_pp"), "bucket_names": st.get("alo_bucket_names")}


def _nnr_of(ds):
    raw = ds.get("nav_not_ready")
    if raw is None:
        return None
    try:
        codes, days, last = L.nav_not_ready(ds)
    except Exception:  # noqa: BLE001 - a malformed shape is handed to the domain as-is
        return raw
    out = {"codes": sorted(codes), "days": days}
    if last is not None:
        out["last"] = last
    return out


def _source_of(ds):
    return {"active_source": "selected", "errors": ds["errors"], "skipped_tabs": ds.get("skipped_tabs") or [],
            "skipped_holdings": ds.get("skipped_holdings") or []}


def build(E, ds, *, settings="auto", source="auto", prov=None, nnr="auto", use_label=True, tables=None, fx=True,
          category_fn=None):
    """`fx` is the caller-supplied FX-rule status (True by default so that existing scenarios are not 'undetermined' only
    because of the FX gate; tests of the gate pass None / False explicitly)."""
    st = _settings_of(ds) if settings == "auto" else settings
    names = st.get("bucket_names") if hasattr(st, "get") else None
    label_fn = category_fn if category_fn is not None else (
        (lambda h: L.category_of(h, names)) if use_label else None)
    return E.build_allocation_evidence(
        ds if tables is None else tables, settings=st, nav_not_ready=_nnr_of(ds) if nnr == "auto" else nnr, fx_key_of=L.fx_key_for,
        basis_mode_of=lambda b: E.BasisMode(market=(b != COST), track_stale=(b == MV)),
        category_of=label_fn, source_state=_source_of(ds) if source == "auto" else source, nav_provenance=prov,
        fx_rule_verified=fx)


def _by_code(ev, code, policy=None):
    hits = [h for h in ev.holdings if h.fund_code == code and (policy is None or h.policy_id == policy)]
    assert len(hits) == 1, (code, policy, [(h.policy_id, h.fund_code) for h in ev.holdings])
    return hits[0]


def _cat(ev, label):
    hits = [c for c in ev.categories if c.category == label]
    assert len(hits) == 1, (label, [c.category for c in ev.categories])
    return hits[0]


def FX_STD():
    return [FX(FX_USD, "2026-10-03", 30.0), FX(FX_EUR, "2026-10-03", 35.0)]


def NAMES_():
    return G.NAMES


CHECKS = []


def check(fn):
    CHECKS.append(fn)
    return fn


# ═══════════════════════ 1. per-holding provenance (nav row and fx row actually used) ═══════════════════════


@check
def check_trace_fx_row_chosen_among_several(E):
    ds = DS([H("A", units=10.0)], [N("A", "2026-10-05", 10.0)],
            [FX(FX_USD, "2026-10-01", 29.0), FX(FX_USD, "2026-10-04", 31.0), FX(FX_USD, "2026-10-06", 33.0),
             FX(FX_EUR, "2026-10-05", 99.0)], basis=MV)
    h = _by_code(build(E, ds), "A")
    assert h.fx.status == "present" and h.fx.fx_key == FX_USD and h.fx.indicator_key == FX_USD
    assert h.fx.obs_date == "2026-10-04" and h.fx.value_num == 31.0 and h.fx.release_date == "2026-10-04"
    assert h.fx.is_revised is False and h.fx.fetched_at == "2026-10-04T00:00:00Z" and h.fx.source_tier == "市場指標"
    assert h.fx.candidate_obs_dates == ("2026-10-01", "2026-10-04", "2026-10-06")   # which of several rows was picked
    assert h.nav.status == "present" and h.nav.nav_date == "2026-10-05" and h.nav.nav_orig_ccy == 10.0
    assert h.nav.ccy == "USD" and h.nav.source_tier == "淨值" and h.nav.is_estimated is False
    assert h.nav.fetched_at == "2026-10-04T00:00:00Z"
    assert h.value_twd == 10.0 * 10.0 * 31.0 and h.valued and h.value_status == "valued" and h.reason is None


@check
def check_trace_latest_nav_of_several_drives_fx_date(E):
    ds = DS([H("A", units=1.0)], [N("A", "2026-10-01", 10.0), N("A", "2026-10-05", 12.0)],
            [FX(FX_USD, "2026-10-01", 29.0), FX(FX_USD, "2026-10-04", 31.0), FX(FX_USD, "2026-10-05", 32.0)], basis=MV)
    h = _by_code(build(E, ds), "A")
    assert h.nav.nav_date == "2026-10-05" and h.nav.nav_orig_ccy == 12.0
    assert h.nav.candidate_nav_dates == ("2026-10-01", "2026-10-05")
    assert h.fx.obs_date == "2026-10-05" and h.fx.value_num == 32.0 and h.value_twd == 12.0 * 32.0


@check
def check_trace_same_day_fx_rows_first_wins_and_both_visible(E):
    ds = DS([H("A", units=1.0)], [N("A", "2026-10-03", 10.0)],
            [FX(FX_USD, "2026-10-03", 31.0), FX(FX_USD, "2026-10-03", 99.0)], basis=MV)
    h = _by_code(build(E, ds), "A")
    assert h.fx.value_num == 31.0 and h.fx.candidate_obs_dates == ("2026-10-03", "2026-10-03")


@check
def check_cost_basis_reads_no_nav_or_fx_tables(E):
    ds = DS([H("A", cost=100.0), H("B", bucket=SAT, ccy="TWD", cost=50.0)], NAV_ALL, [FX(FX_USD, "2026-10-03", 30.0)])
    spy = G.Spy(ds)
    ev = build(E, ds, tables=spy)
    assert "nav" not in spy.touched and "market_indicator" not in spy.touched, spy.touched
    h = _by_code(ev, "A")
    assert h.nav.status == "not_required" and h.fx.status == "not_required" and h.value_twd == 100.0


@check
def check_twd_only_market_basis_never_reads_fx_table(E):
    ds = DS([H("B", ccy="TWD", units=100.0)], NAV_ALL, [], basis=MV)
    spy = G.Spy(ds)
    ev = build(E, ds, tables=spy)
    assert "market_indicator" not in spy.touched, spy.touched
    h = _by_code(ev, "B")
    assert h.fx.status == "not_required" and h.value_twd == 2000.0 and ev.valuation_completeness.status == "complete"


# ═══════════════════════ 2. missing is never zero ═══════════════════════


@check
def check_missing_nav_is_none_never_zero(E):
    ds = DS([H("Z"), H("B", bucket=SAT, ccy="TWD", units=100.0)], NAV_ALL, FX_STD(), basis=MV)
    ev = build(E, ds)
    z = _by_code(ev, "Z")
    assert z.value_twd is None and z.value_status == "missing" and not z.valued and not z.counted_in_denominator
    assert z.reason.code == "nav_absent" and z.missing_kind == "nav"
    assert z.nav.status == "missing" and z.nav.nav_date is None and z.fx.status == "not_evaluated"
    core = _cat(ev, CORE)
    assert core.status == "missing" and core.value_twd is None and core.value_origin is None and not core.covered
    assert ev.coverage.uncovered_value.status == "not_computable"


@check
def check_missing_fx_for_one_ccy_only(E):
    ds = DS([H("A"), H("B", bucket=SAT, ccy="TWD", units=100.0)], NAV_ALL, [], basis=MV)
    ev = build(E, ds)
    a, b = _by_code(ev, "A"), _by_code(ev, "B")
    assert a.value_twd is None and a.reason.code == "fx_absent" and a.reason.fx_key == FX_USD and a.missing_kind == "fx"
    assert a.fx.status == "missing" and a.fx.fx_key == FX_USD and a.nav.status == "present"
    assert b.value_twd == 2000.0 and b.fx.status == "not_required" and b.valued
    assert ev.valuation_completeness.status == "incomplete" and ev.valuation_completeness.reason_codes == ("category_missing",)


@check
def check_missing_fx_for_all_currencies(E):
    ds = DS([H("A"), H("C", bucket=SAT, ccy="EUR")], NAV_ALL, [], basis=MV)
    ev = build(E, ds)
    assert {h.reason.fx_key for h in ev.holdings} == {FX_USD, FX_EUR}
    assert all(h.value_twd is None for h in ev.holdings)
    assert ev.denominator.verdict == "none" and ev.denominator.value_twd is None
    assert ev.coverage.covered_value_twd is None and ev.coverage.covered_categories == ()
    assert set(ev.coverage.uncovered_categories) == {CORE, SAT}
    assert ev.valuation_completeness.status == "incomplete" and "no_category_valued" in ev.valuation_completeness.reason_codes
    assert all(c.share.status == "not_computable" and c.share.share_of_covered_pct is None for c in ev.categories)


# ═══════════════════════ 3. stale NAV (old and new nav_not_ready shapes) ═══════════════════════


@check
def check_stale_new_shape_merges_dates(E):
    last = {"Z": "2026-09-01", "Y": "2026-09-05"}
    ds = DS([H("Z"), H("Y")], NAV_ALL, FX_STD(), basis=MV, nav_not_ready=NNR(["Z", "Y"], 10, last))
    ev = build(E, ds)
    z, y = _by_code(ev, "Z"), _by_code(ev, "Y")
    assert z.reason.code == "nav_stale" and z.reason.stale_day == "2026-09-01" and z.reason.stale_days == 10
    assert y.reason.stale_day == "2026-09-05"
    core = _cat(ev, CORE)
    assert core.stale_entries == (("Z", "2026-09-01"), ("Y", "2026-09-05")) and core.stale_days == 10
    assert core.first_reason.code == "nav_stale" and core.first_reason.stale_entries == core.stale_entries
    assert [m.fund_code for m in core.all_missing_holdings] == ["Z", "Y"]


@check
def check_stale_old_shape_has_no_date(E):
    ds = DS([H("Z")], NAV_ALL, FX_STD(), basis=MV, nav_not_ready=NNR(["Z"], 7))
    z = _by_code(build(E, ds), "Z")
    assert z.reason.code == "nav_stale_undated" and z.reason.stale_day is None and z.reason.stale_days == 7


@check
def check_nav_not_ready_days_is_a_parameter_not_owned(E):
    ds = DS([H("Z")], NAV_ALL, FX_STD(), basis=MV, nav_not_ready=NNR(["Z"], 3, {"Z": "2026-09-01"}))
    assert _by_code(build(E, ds), "Z").reason.stale_days == 3
    assert not hasattr(E, "NAV_NOT_READY_DAYS")


@check
def check_stale_listing_ignored_when_nav_present(E):
    ds = DS([H("A")], NAV_ALL, FX_STD(), basis=MV, nav_not_ready=NNR(["A"], 10, {"A": "2026-09-01"}))
    a = _by_code(build(E, ds), "A")
    assert a.valued and a.reason is None


# ═══════════════════════ 4. provenance side channel ═══════════════════════


@check
def check_provenance_flags_from_side_channel(E):
    ds = DS([H("A"), H("B", bucket=SAT, ccy="TWD", units=100.0)], NAV_ALL, FX_STD(), basis=MV)
    prov = {"provenance": {"A": {"cache_fallback": True, "stale": False, "live_error": "boom"}},
            "withheld": {"B": "ccy_missing"}, "key_failed": [], "not_fresh": ["A"], "too_old": [], "too_old_last": {}}
    ev = build(E, ds, prov=prov)
    a, b = _by_code(ev, "A").nav_cause, _by_code(ev, "B").nav_cause
    assert a.cache_fallback is True and a.stale is False and a.live_error == "boom"
    assert a.estimated == "not_provided"                 # the entry has no `estimated` key -> unknown, not False
    assert a.in_not_fresh is True and a.in_too_old is False and a.key_failed is False
    assert a.withheld == "no_entry" and a.too_old_last == "no_entry"  # part provided, nothing for this fund (not "not_provided")
    assert b.withheld == "ccy_missing" and b.in_not_fresh is False
    assert b.cache_fallback == "no_entry" and b.live_error == "no_entry"           # provided, but no entry for this fund
    assert a.estimated == "not_provided"                                            # entry exists, key absent


@check
def check_provenance_not_provided_is_never_false(E):
    ds = DS([H("A")], NAV_ALL, FX_STD(), basis=MV)
    cause = _by_code(build(E, ds, prov=None), "A").nav_cause
    values = [getattr(cause, f) for f in ("cache_fallback", "stale", "estimated", "live_error", "withheld", "key_failed",
                                         "in_not_fresh", "in_too_old", "too_old_last")]
    assert values == ["not_provided"] * 9
    only = build(E, ds, prov={"not_fresh": ["A"]})                      # only one part given
    c2 = _by_code(only, "A").nav_cause
    assert c2.in_not_fresh is True and c2.cache_fallback == "not_provided" and c2.withheld == "not_provided"
    assert c2.key_failed == "not_provided" and c2.in_too_old == "not_provided"


@check
def check_provenance_malformed_is_a_recorded_problem_not_a_crash(E):
    ds = DS([H("A")], NAV_ALL, FX_STD(), basis=MV)
    ev = build(E, ds, prov={"nope": 1})
    assert any(p.argument == "nav_provenance" for p in ev.input_problems)
    assert _by_code(ev, "A").nav_cause.cache_fallback == "not_provided"


# ═══════════════════════ 5. category rule: first reason AND every missing holding ═══════════════════════


@check
def check_all_missing_holdings_keep_their_own_reasons(E):
    ds = DS([H("A"), H("Z"), H("Y")], NAV_ALL, [], basis=MV, nav_not_ready=NNR(["Y"], 10, {"Y": "2026-09-01"}))
    ev = build(E, ds)
    core = _cat(ev, CORE)
    assert core.first_reason.code == "fx_absent"                                  # the category keeps the FIRST reason ...
    got = [(m.fund_code, m.reason.code) for m in core.all_missing_holdings]       # ... and the list keeps ALL of them
    assert got == [("A", "fx_absent"), ("Z", "nav_absent"), ("Y", "nav_stale")], got
    assert core.holding_count == 3 and core.valued_holding_count == 0


@check
def check_valued_holding_excluded_by_category_rule(E):
    ds = DS([H("A"), H("B", ccy="TWD", units=100.0), H("E", bucket=SAT, ccy="TWD", units=50.0)],
            NAV_ALL + [N("E", "2026-10-03", 5.0, "TWD")], [], basis=MV)
    ev = build(E, ds)
    b = _by_code(ev, "B")
    assert b.valued is True and b.value_twd == 2000.0                             # it HAS a value ...
    assert b.counted_in_denominator is False and b.excluded_by_category_rule is True   # ... but is not counted
    assert b.category_status == "missing" and b.category_first_reason.code == "fx_absent"
    core = _cat(ev, CORE)
    assert core.excluded_valued_holdings == (("P1", "B"),) and core.valued_holding_count == 1
    c = _by_code(ev, "E")
    assert c.valued and c.counted_in_denominator and not c.excluded_by_category_rule
    assert ev.denominator.value_twd == 250.0 and ev.denominator.valued_holding_count == 2
    assert ev.denominator.counted_holding_count == 1
    assert {(u.fund_code, u.own_value_status) for u in ev.coverage.uncovered_holdings} == {("A", "missing"), ("B", "valued")}


# ═══════════════════════ 6. identity ═══════════════════════


@check
def check_same_fund_code_two_policies_stays_two_holdings(E):
    ds = DS([H("A", policy="P1", cost=100.0), H("A", policy="P2", cost=200.0)])
    ev = build(E, ds)
    assert [(h.policy_id, h.fund_code, h.value_twd) for h in ev.holdings] == [("P1", "A", 100.0), ("P2", "A", 200.0)]
    assert all(h.source_row_count == 1 for h in ev.holdings) and ev.denominator.raw_row_count == 2


@check
def check_same_key_rows_are_merged_and_traceable(E):
    rows = [H("A", cost=100.0, units=1.0), H("A", cost=50.0, units=2.0), H("C", bucket=SAT, cost=10.0, ccy="EUR")]
    ev = build(E, DS(rows))
    a = _by_code(ev, "A")
    assert a.source_row_count == 2 and a.units_shares == 3.0 and a.cost_twd == 150.0 and a.value_twd == 150.0
    assert [(r.policy_id, r.fund_code, r.bucket, r.ccy, r.units_shares, r.cost_twd) for r in a.source_rows] == [
        ("P1", "A", CORE, "USD", 1.0, 100.0), ("P1", "A", CORE, "USD", 2.0, 50.0)]
    assert ev.denominator.raw_row_count == 3 and ev.denominator.aggregated_holding_count == 2


@check
def check_identity_conflict_is_recorded_not_raised(E):
    for rows, columns in (([H("A", bucket=CORE), H("A", bucket=SAT)], ("bucket",)), ([H("A", ccy="USD"), H("A", ccy="EUR")], ("ccy",))):
        ev = build(E, DS(rows))
        assert ev.identity_conflict is not None and ev.identity_conflict.key == ("P1", "A")
        assert ev.identity_conflict.columns == columns
        assert ev.holdings == () and ev.categories == ()
        assert ev.valuation_completeness.status == "failed" and "identity_conflict" in ev.valuation_completeness.reason_codes
        assert ev.chart_comparability.status == "not_comparable" and "identity_conflict" in ev.chart_comparability.failing_conditions
        assert ev.denominator.raw_row_count == 2 and ev.denominator.verdict == "none"


# ═══════════════════════ 7. source coverage (never 'complete' when anything is skipped) ═══════════════════════


@check
def check_source_coverage_matrix(E):
    core2 = [H("A", cost=3000.0), H("B", cost=3000.0, ccy="TWD")]
    tabs = [{"tab": "tabB", "error": "timeout"}, {"tab": "tabC"}]
    rows = [{"tab": "tabA", "row": 5, "fund_code": "A", "reasons": ["no bucket", "cost not a number"]}]
    base = DS(core2)
    assert build(E, base).source_coverage.status == "complete" and build(E, base).source_coverage.reason_codes == ()
    s = build(E, DS(core2, skipped_tabs=tabs)).source_coverage
    assert s.status == "incomplete" and "skipped_tabs_present" in s.reason_codes
    s = build(E, DS(core2, skipped_holdings=rows)).source_coverage
    assert s.status == "incomplete" and "omitted_rows_present" in s.reason_codes
    both = build(E, DS(core2, skipped_holdings=rows, skipped_tabs=tabs))
    assert both.source_coverage.status == "incomplete" and both.denominator.omitted_row_count == 1
    assert both.denominator.skipped_tab_count == 2
    # empty holdings + skipped evidence: unknown, NOT "no holdings"
    for ds in (DS([], skipped_tabs=tabs), DS([], skipped_holdings=rows), DS([], skipped_holdings=rows, skipped_tabs=tabs)):
        ev = build(E, ds)
        assert ev.source_coverage.status == "unknown" and "skip_evidence_without_holdings" in ev.source_coverage.reason_codes
        assert ev.valuation_completeness.status == "not_evaluated"
    # a read failure on the holding table
    ev = build(E, DS(core2, errors={"holding": "HTTP 503"}))
    assert ev.source_coverage.status == "failed" and ev.source_coverage.reason_codes == ("holding_read_failed",)
    assert ev.valuation_completeness.status == "failed" and ev.valuation_completeness.reason_codes == ("holding_read_failed",)
    assert all(h.value_status == "not_evaluated" and h.value_twd is None for h in ev.holdings)
    # non-holding table failing: recorded, not silently ignored
    ev = build(E, DS(core2, errors={"policy": "HTTP 503"}))
    assert ev.source_coverage.status == "incomplete" and "non_holding_read_error" in ev.source_coverage.reason_codes
    assert "non_holding_read_error_effect_unjudged" in ev.open_gates


@check
def check_source_state_not_provided_is_unknown_never_complete(E):
    ds = DS([H("A", cost=3000.0)])
    ev = build(E, ds, source=None)
    assert ev.source_coverage.status == "unknown" and ev.source.state_status == "not_provided"
    assert ev.source.skipped_tabs.status == "not_provided" and ev.source.omitted_rows.status == "not_provided"
    assert ev.denominator.omitted_row_count is None and ev.denominator.skipped_tab_count is None   # not 0
    partial = build(E, ds, source={"active_source": "selected"})
    assert partial.source_coverage.status == "unknown"
    assert "read_errors_not_provided" in partial.source_coverage.reason_codes
    assert "skipped_tabs_not_provided" in partial.source_coverage.reason_codes
    assert "omitted_rows_not_provided" in partial.source_coverage.reason_codes
    only_state = build(E, ds, source={"errors": {}, "skipped_tabs": [], "skipped_holdings": []})
    assert only_state.source_coverage.status == "unknown" and "active_source_not_provided" in only_state.source_coverage.reason_codes


@check
def check_active_source_unset_is_not_selected(E):
    ds = DS([])
    ev = build(E, ds, source={"active_source": "none", "errors": {}, "skipped_tabs": [], "skipped_holdings": []})
    assert ev.source_coverage.status == "not_selected" and ev.source_coverage.reason_codes == ("no_active_source",)
    assert ev.valuation_completeness.status == "not_evaluated" and "no_active_source" in ev.valuation_completeness.reason_codes
    assert ev.chart_comparability.status == "not_evaluated"


@check
def check_legitimately_empty_holdings_with_proven_complete_source(E):
    ev = build(E, DS([]))
    assert ev.source_coverage.status == "complete" and ev.holdings == () and ev.categories == ()
    assert ev.valuation_completeness.status == "not_evaluated" and ev.valuation_completeness.reason_codes == ("no_holdings",)
    assert ev.chart_comparability.status == "not_evaluated" and ev.denominator.value_twd is None


@check
def check_omitted_rows_are_kept_as_given_data(E):
    rows = [{"tab": "tabA", "row": 5, "fund_code": "A", "reasons": ["r1", "r2"]},
            {"tab": None, "row": None, "fund_code": None, "reasons": []}]
    ev = build(E, DS([H("A", cost=1.0)], skipped_holdings=rows, skipped_tabs=[{"tab": "x", "error": "boom"}]))
    assert list(ev.source.omitted_rows.items) == rows and list(ev.source.skipped_tabs.items) == [{"tab": "x", "error": "boom"}]
    assert ev.source.omitted_rows.items is not rows                       # a copy, not an alias
    assert "omitted_row_reason_codes_undefined" in ev.open_gates


@check
def check_source_state_malformed_is_recorded_not_raised(E):
    ev = build(E, DS([H("A", cost=1.0)]), source={"active_source": "selected", "errors": {}, "skipped_tabs": [],
                                                  "skipped_holdings": "x"})
    assert ev.source.omitted_rows.status == "invalid" and ev.source_coverage.status == "unknown"
    assert any(p.argument == "source_state.skipped_holdings" for p in ev.input_problems)


# ═══════════════════════ 8. settings are preserved, never defaulted ═══════════════════════


@check
def check_basis_unset_is_preserved_and_nothing_defaults_to_cost(E):
    ds = DS([H("A", cost=3000.0), H("C", bucket=SAT, cost=4000.0, ccy="EUR")], NAV_ALL, FX_STD(), basis=None)
    spy = G.Spy(ds)
    ev = build(E, ds, tables=spy)
    assert ev.settings.basis.status == "unset" and ev.settings.basis.value is None
    assert ev.settings.basis_market is None and ev.settings.basis_track_stale is None
    assert ev.valuation_completeness.status == "not_evaluated" and ev.valuation_completeness.reason_codes == ("basis_unset",)
    assert all(h.value_twd is None and h.value_status == "not_evaluated" and not h.valued for h in ev.holdings)
    assert ev.categories == () and ev.denominator.value_twd is None and ev.denominator.verdict == "none"
    assert ev.chart_comparability.status == "not_evaluated" and "basis_unset" in ev.chart_comparability.failing_conditions
    assert spy.touched == {"holding"}, spy.touched
    # still identity-traceable
    assert [(h.policy_id, h.fund_code, h.cost_twd) for h in ev.holdings] == [("P1", "A", 3000.0), ("P1", "C", 4000.0)]


@check
def check_targets_unset_blocks_chart_but_not_valuation(E):
    for targets, status in ((None, "unset"), ([], "empty")):
        ev = build(E, DS([H("A", cost=3000.0)], targets=targets))
        assert ev.settings.targets.status == status
        assert ev.valuation_completeness.status == "complete"
        assert ev.chart_comparability.status == "not_evaluated" and ("targets_" + status) in ev.chart_comparability.failing_conditions


@check
def check_settings_echo_is_exact_and_unset_stays_unset(E):
    targets = [{"bucket": CORE, "weight_ratio": 0.6}, {"bucket": SAT, "weight_ratio": None}]
    ds = DS([H("A", cost=1.0)], targets=targets, tol=5.0, names=NAMES_())
    ev = build(E, ds)
    assert ev.settings.targets.value == targets and ev.settings.targets.value is not targets
    assert ev.settings.tolerance.status == "set" and ev.settings.tolerance.value == 5.0
    assert ev.settings.bucket_names.value == [CORE, SAT] and ev.settings.targets_weight_sum == 0.6
    none = build(E, DS([H("A", cost=1.0)], tol=None, names=None))
    assert none.settings.tolerance.status == "unset" and none.settings.tolerance.value is None
    assert none.settings.bucket_names.status == "unset"
    nothing = build(E, DS([H("A", cost=1.0)]), settings=None)
    assert nothing.settings.basis.status == "not_provided" and nothing.valuation_completeness.status == "not_evaluated"
    failed = build(E, DS([H("A", cost=1.0)], errors={"user_setting": "boom"}))
    assert failed.settings.basis.status == "read_failed" and failed.valuation_completeness.status == "failed"
    assert failed.valuation_completeness.reason_codes == ("settings_read_failed",)


@check
def check_producer_metadata_and_rule_ref(E):
    ev = build(E, DS([H("A", cost=1.0)]))
    assert ev.producer_id == E.PRODUCER_ID == "v2_domain.allocation_evidence"
    assert type(ev.schema_version) is int and ev.schema_version == E.SCHEMA_VERSION
    assert ev.rule_ref.status == "not_defined" and not hasattr(ev.rule_ref, "rule_version")
    assert isinstance(ev.open_gates, tuple) and ev.open_gates == ()


# ═══════════════════════ 9. categories ═══════════════════════


@check
def check_unclassified_is_preserved_as_none(E):
    ds = DS([H("A", cost=3000.0), H("C", bucket=None, cost=1000.0), H("D", bucket="other", cost=500.0)])
    ev = build(E, ds, use_label=False)                                  # domain default: unclassified label is None
    un = _cat(ev, None)
    assert un.is_unclassified and un.holding_count == 2 and un.value_twd == 1500.0 and un.target.status == "no_target"
    assert _by_code(ev, "C").category is None and _by_code(ev, "C").is_unclassified and _by_code(ev, "A").is_unclassified is False
    assert "unclassified_comparability_unjudged" in ev.open_gates
    assert not _cat(ev, CORE).is_unclassified


@check
def check_target_without_holdings_is_a_real_zero_with_origin(E):
    targets = G.TARGETS + [{"bucket": BOND, "weight_ratio": 0.1}]
    ds = DS([H("A", cost=3000.0), H("C", bucket=SAT, cost=4000.0)], targets=targets, names=G.NAMES + (BOND,))
    ev = build(E, ds)
    bond = _cat(ev, BOND)
    assert bond.origin == "target_without_holdings" and bond.status == "valued" and bond.value_twd == 0.0
    assert bond.value_origin == "real_zero_by_rule" and bond.holding_count == 0 and bond.share.share_of_covered_pct == 0.0
    assert BOND not in ev.coverage.covered_categories and BOND not in ev.coverage.uncovered_categories
    core = _cat(ev, CORE)
    assert core.origin == "from_holdings" and core.value_origin == "summed"
    miss = build(E, DS([H("A"), H("C", bucket=SAT, ccy="TWD", units=100.0)], NAV_ALL, [], basis=MV, targets=targets,
                       names=G.NAMES + (BOND,)))
    assert _cat(miss, CORE).value_twd is None and _cat(miss, CORE).value_origin is None        # Missing is not a real zero
    assert _cat(miss, BOND).value_twd == 0.0


@check
def check_target_facts_per_category(E):
    targets = [{"bucket": CORE, "weight_ratio": None}, {"bucket": SAT, "weight_ratio": 0.4}]
    ev = build(E, DS([H("A", cost=3000.0), H("C", bucket=SAT, cost=4000.0), H("D", bucket=None, cost=1.0)], targets=targets),
               use_label=True)
    assert _cat(ev, CORE).target.status == "weight_unset" and _cat(ev, CORE).target.weight_ratio is None
    assert _cat(ev, SAT).target.status == "set" and _cat(ev, SAT).target.weight_ratio == 0.4
    assert "target_weight_sum_rule_undefined" in ev.open_gates
    assert ev.chart_comparability.status == "not_comparable" and "target_weight_missing" in ev.chart_comparability.failing_conditions


# ═══════════════════════ 10. covered / uncovered / share ═══════════════════════


@check
def check_denominator_is_the_ordered_sum_of_category_values(E):
    values = [0.1, 0.2, 0.3]                 # on CPython < 3.12 naive float addition is order dependent: 0.6000000000000001 vs 0.6
    rows = [H("A", cost=values[0], bucket=CORE), H("C", bucket=SAT, cost=values[1]), H("D", bucket=BOND, cost=values[2])]
    ds = DS(rows, targets=G.TARGETS, names=G.NAMES + (BOND,))
    ev = build(E, ds)
    assert ev.denominator.value_twd == sum(values) and ev.coverage.covered_value_twd == ev.denominator.value_twd
    assert ev.denominator.verdict == "complete"


@check
def check_share_is_share_of_covered_and_flags_total_claim(E):
    ev = build(E, DS([H("A", cost=7000.0), H("C", bucket=SAT, cost=3000.0)]))
    core = _cat(ev, CORE)
    assert core.share.status == "computed" and core.share.share_of_covered_pct == 7000.0 / 10000.0 * 100.0
    assert core.share.covers_all_holdings is True
    part = build(E, DS([H("A"), H("B", bucket=SAT, ccy="TWD", units=100.0)], NAV_ALL, [], basis=MV))
    assert _cat(part, SAT).share.share_of_covered_pct == 100.0 and _cat(part, SAT).share.covers_all_holdings is False
    assert part.denominator.verdict == "incomplete"


@check
def check_hundred_percent_trap_is_flagged_not_hidden(E):
    """USD fund missing FX + TWD fund valued: the old ALO shows the TWD category as 100%; here it is share_of_covered of an
    incomplete scope, the uncovered scope is listed, and its TWD amount is not computable (never 0)."""
    ds = DS([H("A", bucket=CORE, ccy="USD"), H("B", bucket=SAT, ccy="TWD", units=100.0)], NAV_ALL, [], basis=MV)
    ev = build(E, ds)
    sat = _cat(ev, SAT)
    assert sat.share.status == "computed" and sat.share.share_of_covered_pct == 100.0
    assert sat.share.covers_all_holdings is False
    assert ev.coverage.covered_categories == (SAT,) and ev.coverage.uncovered_categories == (CORE,)
    assert ev.coverage.uncovered_value.status == "not_computable" and ev.coverage.uncovered_value.reason_codes
    assert [(u.fund_code, u.own_value_twd) for u in ev.coverage.uncovered_holdings] == [("A", None)]
    assert _cat(ev, CORE).share.status == "not_computable" and _cat(ev, CORE).share.share_of_covered_pct is None
    assert ev.denominator.verdict == "incomplete" and ev.denominator.excluded_category_count == 1
    assert ev.valuation_completeness.status == "incomplete"
    assert ev.chart_comparability.status == "not_comparable" and "valuation_incomplete" in ev.chart_comparability.failing_conditions


@check
def check_non_positive_denominator_is_failed_not_raised(E):
    for rows in ([H("A", cost=0.0), H("C", bucket=SAT, cost=0.0)], [H("A", cost=-100.0), H("C", bucket=SAT, cost=50.0)]):
        ev = build(E, DS(rows))
        assert ev.denominator.verdict == "non_positive" and ev.denominator.value_twd <= 0
        assert ev.valuation_completeness.status == "failed" and "denominator_non_positive" in ev.valuation_completeness.reason_codes
        assert "denominator_not_positive" in ev.chart_comparability.failing_conditions
        assert all(c.share.status == "not_computable" for c in ev.categories)
    nan = build(E, DS([H("A", units=float("nan")), H("B", bucket=SAT, ccy="TWD")], NAV_ALL, FX_STD(), basis=MV))
    assert nan.denominator.verdict == "non_finite" and nan.valuation_completeness.status == "failed"


# ═══════════════════════ 11. three separate assessments ═══════════════════════


@check
def check_three_assessments_are_independent(E):
    core2 = [H("A", cost=3000.0), H("C", bucket=SAT, cost=4000.0)]
    ok = build(E, DS(core2))
    assert (ok.source_coverage.status, ok.valuation_completeness.status, ok.chart_comparability.status) == \
        ("complete", "complete", "comparable")
    # source complete, valuation incomplete
    a = build(E, DS([H("A"), H("B", bucket=SAT, ccy="TWD", units=100.0)], NAV_ALL, [], basis=MV))
    assert (a.source_coverage.status, a.valuation_completeness.status, a.chart_comparability.status) == \
        ("complete", "incomplete", "not_comparable")
    # source incomplete, valuation complete
    b = build(E, DS(core2, skipped_tabs=[{"tab": "x"}]))
    assert (b.source_coverage.status, b.valuation_completeness.status, b.chart_comparability.status) == \
        ("incomplete", "complete", "not_comparable")
    assert b.denominator.verdict == "complete"
    assert all(c.share.covers_all_holdings is False for c in b.categories)       # complete valuation, incomplete source
    assert all(c.share.covers_all_holdings is True for c in ok.categories)
    assert b.chart_comparability.failing_conditions == ("source_coverage_incomplete",)
    # source complete, valuation complete, chart not evaluated (targets unset)
    c = build(E, DS(core2, targets=None))
    assert (c.source_coverage.status, c.valuation_completeness.status, c.chart_comparability.status) == \
        ("complete", "complete", "not_evaluated")
    # source failed (valuation follows), chart not comparable
    d = build(E, DS(core2, errors={"holding": "x"}))
    assert d.source_coverage.status == "failed" and d.chart_comparability.status == "not_comparable"


@check
def check_evaluation_error_of_injected_callable_is_recorded(E):
    ds = DS([H("A")], [N("A", "2026-10-03", 10.0, "usd")], FX_STD(), basis=MV)
    ev = build(E, ds)
    h = _by_code(ev, "A")
    assert h.value_status == "error" and h.value_twd is None and h.errors and h.errors[0].error_type == "ValueError"
    assert ev.valuation_completeness.status == "failed" and "holding_evaluation_error" in ev.valuation_completeness.reason_codes
    assert ev.evaluation_errors and ev.categories == ()


@check
def check_invalid_nav_not_ready_is_recorded_only_when_it_matters(E):
    ds = DS([H("A")], NAV_ALL, FX_STD(), basis=MV, nav_not_ready={"codes": ["A"]})
    ev = build(E, ds)
    assert any(p.argument == "nav_not_ready" for p in ev.input_problems)
    assert ev.valuation_completeness.status == "failed" and "invalid_nav_not_ready" in ev.valuation_completeness.reason_codes
    cost = build(E, DS([H("A", cost=5.0)], nav_not_ready={"codes": ["A"]}))
    assert cost.input_problems == () and cost.valuation_completeness.status == "complete"


@check
def check_market_input_read_failure_blocks_valuation_only_on_market_basis(E):
    mv = build(E, DS([H("A")], NAV_ALL, FX_STD(), basis=MV, errors={"nav": "HTTP 503"}))
    assert mv.valuation_completeness.status == "failed" and "nav_read_failed" in mv.valuation_completeness.reason_codes
    cost = build(E, DS([H("A", cost=5.0)], NAV_ALL, FX_STD(), errors={"nav": "HTTP 503"}))
    assert cost.valuation_completeness.status == "complete" and ("nav", "HTTP 503") in cost.source.read_errors.items


@check
def check_open_gates_record_judgments_not_made(E):
    ds = DS([H("A")], [N("A", "2026-10-05", 10.0)], [FX(FX_USD, "2026-10-01", 29.0)], basis=MV)
    assert "fx_obs_date_lag_degradation_unjudged" in build(E, ds).open_gates
    same_day = DS([H("A")], [N("A", "2026-10-05", 10.0)], [FX(FX_USD, "2026-10-05", 29.0)], basis=MV)
    assert "fx_obs_date_lag_degradation_unjudged" not in build(E, same_day).open_gates
    mismatch = DS([H("A", ccy="EUR")], [N("A", "2026-10-05", 10.0, "USD")], [FX(FX_USD, "2026-10-05", 29.0)], basis=MV)
    ev = build(E, mismatch)
    assert _by_code(ev, "A").nav_ccy_matches_holding_ccy is False and "holding_nav_ccy_disagreement_unjudged" in ev.open_gates
    stale = DS([H("Z")], NAV_ALL, FX_STD(), basis=MV, nav_not_ready=NNR(["Z"], 10, {"Z": "2026-09-01"}))
    assert "stale_nav_degradation_unjudged" in build(E, stale).open_gates


# ═══════════════════════ A. the producer never raises for data / settings conditions ═══════════════════════


def _strict(E, ev):
    """strict JSON (allow_nan=False) must succeed on whatever the producer returns."""
    return json.loads(json.dumps(E.to_primitive(ev), allow_nan=False))


_CLEAN_SETTINGS = {"basis": COST, "targets": G.TARGETS, "tolerance": 5.0, "bucket_names": list(G.NAMES)}


def _cost_ds():
    return DS([H("A", cost=3000.0), H("C", bucket=SAT, cost=4000.0)])


@check
def check_bucket_names_of_wrong_type_is_recorded_not_raised(E):
    for bad in (5, "abc", 1.5, {"a": 1}, [1, 2], [["x"]], True):
        ev = build(E, _cost_ds(), settings={**_CLEAN_SETTINGS, "bucket_names": bad})
        assert ev.settings.bucket_names.status == "invalid", bad
        assert any(p.argument == "settings.bucket_names" for p in ev.input_problems)
        assert ev.valuation_completeness.status == "failed" and "bucket_names_invalid" in ev.valuation_completeness.reason_codes
        assert ev.chart_comparability.status == "not_comparable"
        _strict(E, ev)


@check
def check_malformed_targets_are_recorded_not_raised(E):
    bad_targets = ([{"bucket": CORE, "weight_ratio": "x"}], [{"bucket": ["z"], "weight_ratio": 0.5}],
                   [{"bucket": {"k": 1}, "weight_ratio": 0.5}], [{"bucket": CORE}], [5], "abc", {"bucket": CORE},
                   [{"bucket": CORE, "weight_ratio": True}], [{"bucket": None, "weight_ratio": 0.5}])
    for bad in bad_targets:
        ev = build(E, _cost_ds(), settings={**_CLEAN_SETTINGS, "targets": bad})
        assert ev.settings.targets.status == "invalid", bad
        assert any(p.argument == "settings.targets" for p in ev.input_problems)
        assert ev.chart_comparability.status == "not_comparable" and "targets_invalid" in ev.chart_comparability.failing_conditions
        assert ev.settings.targets_weight_sum is None
        _strict(E, ev)


@check
def check_unhashable_or_raising_category_label_is_recorded(E):
    for fn in (lambda h: [h["bucket"]], lambda h: {"x": 1}, lambda h: {1, 2}, lambda h: 1 / 0):
        ev = build(E, _cost_ds(), category_fn=fn)
        assert all(h.errors and h.errors[0].stage == "category_of" for h in ev.holdings)
        assert ev.valuation_completeness.status == "failed" and "holding_evaluation_error" in ev.valuation_completeness.reason_codes
        assert ev.categories == () and ev.chart_comparability.status == "not_comparable"
        _strict(E, ev)
    # only one of two holdings misbehaves: the other keeps its identity facts
    ev = build(E, _cost_ds(), category_fn=lambda h: [] if h["fund_code"] == "C" else h["bucket"])
    assert _by_code(ev, "A").errors == () and _by_code(ev, "C").errors


@check
def check_non_numeric_computed_value_is_an_error_not_a_number(E):
    ds = DS([H("A", units=3, ccy="TWD")], [N("A", "2026-10-03", "ab", "TWD")], [], basis=MV)
    ev = build(E, ds)
    h = _by_code(ev, "A")
    assert h.value_status == "error" and h.value_twd == "ababab" and h.errors      # raw product kept as given, flagged as error
    assert ev.valuation_completeness.status == "failed"
    _strict(E, ev)


# ═══════════════════════ B. 'none_uncovered' and real zeros need a proven source ═══════════════════════


@check
def check_none_uncovered_only_with_proven_complete_source(E):
    clean = build(E, _cost_ds())
    assert clean.coverage.uncovered_value.status == "none_uncovered"
    for label, ev in (
            ("skipped_tabs", build(E, DS(_cost_ds()["holding"], skipped_tabs=[{"tab": "t"}]))),
            ("omitted_rows", build(E, DS(_cost_ds()["holding"], skipped_holdings=[{"tab": "t", "row": 1, "reasons": ["r"]}]))),
            ("source_state_none", build(E, _cost_ds(), source=None)),
            ("policy_error", build(E, DS(_cost_ds()["holding"], errors={"policy": "boom"}))),
            ("settings_error", build(E, DS(_cost_ds()["holding"], errors={"user_setting": "boom"})))):
        status = ev.coverage.uncovered_value.status
        assert status == "not_evaluated", (label, status)
    codes = build(E, _cost_ds(), source=None).coverage.uncovered_value.reason_codes
    assert codes == ("source_coverage_unknown",)
    partial = build(E, DS([H("A"), H("B", bucket=SAT, ccy="TWD", units=100.0)], NAV_ALL, [], basis=MV, skipped_tabs=[{"tab": "t"}]))
    assert partial.coverage.uncovered_value.status == "not_computable"                 # existing meaning kept
    assert partial.coverage.uncovered_value.reason_codes == ("missing_holdings_have_no_value", "source_scope_not_proven")


@check
def check_target_zero_is_unproven_when_source_is_not_complete(E):
    targets = G.TARGETS + [{"bucket": BOND, "weight_ratio": 0.1}]
    rows = [H("A", cost=3000.0), H("C", bucket=SAT, cost=4000.0)]
    names = G.NAMES + (BOND,)
    proven = build(E, DS(rows, targets=targets, names=names))
    bond = _cat(proven, BOND)
    assert bond.value_origin == "real_zero_by_rule" and bond.value_reliable is True and bond.value_twd == 0.0
    assert _cat(proven, CORE).value_reliable is True
    for ds, kw in ((DS(rows, targets=targets, names=names, skipped_tabs=[{"tab": "t"}]), {}),
                   (DS(rows, targets=targets, names=names), {"source": None})):
        ev = build(E, ds, **kw)
        bond = _cat(ev, BOND)
        assert bond.value_origin == "unproven_zero" and bond.value_reliable is False
        assert bond.value_twd is None and bond.status == "not_computable"                  # Missing, never a numeric 0.0
        assert bond.share.status == "not_computable" and bond.share.share_of_covered_pct is None
        assert _cat(ev, CORE).value_reliable is False                 # a partial sum over an unproven source is not reliable either
    miss = build(E, DS([H("A"), H("C", bucket=SAT, ccy="TWD", units=1.0)], NAV_ALL, [], basis=MV))
    assert _cat(miss, CORE).value_reliable is False                   # a missing category is never reliable


@check
def check_uncovered_holding_own_value_cannot_be_read_as_uncovered_amount(E):
    ds = DS([H("A"), H("B", ccy="TWD", units=100.0)], NAV_ALL, [], basis=MV)
    ev = build(E, ds)
    by = {u.fund_code: u for u in ev.coverage.uncovered_holdings}
    assert by["A"].own_value_known is False and by["A"].own_value_twd is None
    assert by["B"].own_value_known is True and by["B"].own_value_twd == 2000.0
    assert by["A"].own_value_counted is False and by["B"].own_value_counted is False
    assert ev.coverage.uncovered_value.status == "not_computable"


# ═══════════════════════ C. chart comparability: blocking facts, pending gates, 'undetermined' ═══════════════════════


@check
def check_target_without_weight_is_a_blocking_fact(E):
    targets = [{"bucket": CORE, "weight_ratio": None}, {"bucket": SAT, "weight_ratio": 0.4}]
    ev = build(E, DS([H("A", cost=3000.0), H("C", bucket=SAT, cost=4000.0)], targets=targets))
    assert ev.chart_comparability.status == "not_comparable"
    assert ev.chart_comparability.failing_conditions == ("target_weight_missing",)


@check
def check_pending_gates_make_the_chart_undetermined_not_comparable(E):
    rows = [H("A", cost=3000.0), H("C", bucket=SAT, cost=4000.0)]
    clean = build(E, DS(rows))
    assert clean.chart_comparability.status == "comparable" and clean.chart_comparability.pending_gates == ()
    assert clean.open_gates == ()
    # unclassified
    ev = build(E, DS(rows + [H("D", bucket=None, cost=1.0)]))
    assert ev.chart_comparability.status == "undetermined"
    assert ev.chart_comparability.failing_conditions == ("unclassified_comparability_unjudged",) == ev.chart_comparability.pending_gates
    # target weights not summing to 1 (clearly)
    ev = build(E, DS(rows, targets=[{"bucket": CORE, "weight_ratio": 0.9}, {"bucket": SAT, "weight_ratio": 0.9}]))
    assert ev.chart_comparability.status == "undetermined" and "target_weight_sum_rule_undefined" in ev.chart_comparability.pending_gates
    # duplicate target buckets
    ev = build(E, DS(rows, targets=[{"bucket": CORE, "weight_ratio": 0.6}, {"bucket": CORE, "weight_ratio": 0.4},
                                    {"bucket": SAT, "weight_ratio": 0.0}]))
    assert "target_duplicate_bucket_unjudged" in ev.open_gates
    assert ev.chart_comparability.status == "undetermined" and "target_duplicate_bucket_unjudged" in ev.chart_comparability.pending_gates
    # fx observation date earlier than the nav date
    lag = DS([H("A")], [N("A", "2026-10-05", 10.0)], [FX(FX_USD, "2026-10-01", 29.0)], basis=MV, names=G.NAMES,
             targets=[{"bucket": CORE, "weight_ratio": 1.0}])
    ev = build(E, lag)
    assert ev.chart_comparability.status == "undetermined" and "fx_obs_date_lag_degradation_unjudged" in ev.chart_comparability.pending_gates
    # holding currency differs from the nav currency
    mismatch = DS([H("A", ccy="EUR")], [N("A", "2026-10-05", 10.0, "USD")], [FX(FX_USD, "2026-10-05", 29.0)], basis=MV,
                  targets=[{"bucket": CORE, "weight_ratio": 1.0}])
    ev = build(E, mismatch)
    assert ev.chart_comparability.status == "undetermined" and "holding_nav_ccy_disagreement_unjudged" in ev.chart_comparability.pending_gates
    # stale NAV: valuation incomplete is a blocking fact; the gate is still listed
    stale = DS([H("Z"), H("B", bucket=SAT, ccy="TWD", units=1.0)], NAV_ALL, FX_STD(), basis=MV,
               nav_not_ready=NNR(["Z"], 10, {"Z": "2026-09-01"}))
    ev = build(E, stale)
    assert ev.chart_comparability.status == "not_comparable" and "stale_nav_degradation_unjudged" in ev.chart_comparability.pending_gates


@check
def check_target_sum_uses_a_tolerance_not_exact_equality(E):
    weights = [0.6, 0.3, 0.1]
    assert sum(weights) != 1.0 and abs(sum(weights) - 1.0) < 1e-12                # the float trap this test is about
    targets = [{"bucket": CORE, "weight_ratio": 0.6}, {"bucket": SAT, "weight_ratio": 0.3}, {"bucket": BOND, "weight_ratio": 0.1}]
    rows = [H("A", cost=6.0), H("C", bucket=SAT, cost=3.0), H("D", bucket=BOND, cost=1.0)]
    ev = build(E, DS(rows, targets=targets, names=G.NAMES + (BOND,)))
    assert "target_weight_sum_rule_undefined" not in ev.open_gates and ev.chart_comparability.status == "comparable"
    off = build(E, DS(rows, targets=[{"bucket": CORE, "weight_ratio": 0.6}, {"bucket": SAT, "weight_ratio": 0.3},
                                     {"bucket": BOND, "weight_ratio": 0.1001}], names=G.NAMES + (BOND,)))
    assert "target_weight_sum_rule_undefined" in off.open_gates


@check
def check_tolerance_unset_is_recorded_but_does_not_change_the_chart_state(E):
    ev = build(E, DS([H("A", cost=3000.0), H("C", bucket=SAT, cost=4000.0)], tol=None))
    assert "tolerance_unset_effect_unjudged" in ev.open_gates
    assert ev.chart_comparability.status == "comparable" and ev.chart_comparability.pending_gates == ()
    assert "tolerance_unset_effect_unjudged" not in build(E, _cost_ds()).open_gates


# ═══════════════════════ D. FX observation-date rule status gate ═══════════════════════


def _fx_clean_ds(**kw):
    return DS([H("A"), H("B", bucket=SAT, ccy="TWD", units=100.0)], NAV_ALL, FX_STD(), basis=MV, **kw)


@check
def check_fx_rule_gate_is_always_recorded_when_a_non_twd_fx_was_required(E):
    ds = _fx_clean_ds()
    none = build(E, ds, fx=None)
    assert none.open_gates == ("fx_obs_date_rule_status_not_provided",) and none.fx_rule_verified == "not_provided"
    assert none.chart_comparability.status == "undetermined"
    assert none.chart_comparability.failing_conditions == ("fx_obs_date_rule_status_not_provided",)
    false = build(E, ds, fx=False)
    assert false.open_gates == ("fx_obs_date_rule_unverified",) and false.fx_rule_verified is False
    assert false.chart_comparability.status == "undetermined"
    true = build(E, ds, fx=True)
    assert true.open_gates == () and true.chart_comparability.status == "comparable" and true.fx_rule_verified is True
    # FX required but the row is absent: the gate is still recorded (the FX was required)
    gone = build(E, DS([H("A"), H("B", bucket=SAT, ccy="TWD", units=100.0)], NAV_ALL, [], basis=MV), fx=None)
    assert "fx_obs_date_rule_status_not_provided" in gone.open_gates


@check
def check_fx_rule_gate_is_absent_without_a_non_twd_fx(E):
    twd = DS([H("B", ccy="TWD", units=100.0), H("E", bucket=SAT, ccy="TWD", units=1.0)], NAV_ALL + [N("E", "2026-10-03", 5.0, "TWD")],
             [], basis=MV)
    for fx in (None, False, True):
        ev = build(E, twd, fx=fx)
        assert not any(g.startswith("fx_obs_date_rule") for g in ev.open_gates), (fx, ev.open_gates)
    for fx in (None, False):
        cost = build(E, _cost_ds(), fx=fx)
        assert not any(g.startswith("fx_obs_date_rule") for g in cost.open_gates)
    blocked = build(E, DS([H("A")], NAV_ALL, FX_STD(), basis=None), fx=None)         # nothing was evaluated: no FX was required
    assert not any(g.startswith("fx_obs_date_rule") for g in blocked.open_gates)


# ═══════════════════════ SHOULD-FIX facts ═══════════════════════


@check
def check_fx_row_without_value_is_present_without_value_and_holding_missing(E):
    ds = DS([H("A"), H("B", bucket=SAT, ccy="TWD", units=100.0)], NAV_ALL, [FX(FX_USD, "2026-10-03", None)], basis=MV)
    ev = build(E, ds)
    a = _by_code(ev, "A")
    assert a.fx.status == "present_without_value" and a.fx.value_num is None and a.fx.obs_date == "2026-10-03"
    assert a.value_twd is None and a.reason.code == "fx_absent" and a.value_status == "missing"


@check
def check_settings_read_failure_downgrades_source_coverage(E):
    ev = build(E, DS(_cost_ds()["holding"], errors={"user_setting": "boom"}))
    assert ev.source_coverage.status == "incomplete" and ev.source_coverage.reason_codes == ("settings_read_failed",)
    assert "non_holding_read_error_effect_unjudged" not in ev.open_gates


@check
def check_known_table_read_errors_are_not_non_holding_errors(E):
    cost_nav = build(E, DS(_cost_ds()["holding"], errors={"nav": "x", "market_indicator": "y"}))
    assert cost_nav.source_coverage.status == "complete" and cost_nav.valuation_completeness.status == "complete"
    assert "non_holding_read_error_effect_unjudged" not in cost_nav.open_gates
    for table in ("nav", "market_indicator"):
        mv = build(E, DS([H("A")], NAV_ALL, FX_STD(), basis=MV, errors={table: "x"}))
        assert mv.source_coverage.status == "complete" and "non_holding_read_error" not in mv.source_coverage.reason_codes
        assert mv.valuation_completeness.status == "failed"
    other = build(E, DS(_cost_ds()["holding"], errors={"policy": "x"}))
    assert other.source_coverage.status == "incomplete" and "non_holding_read_error" in other.source_coverage.reason_codes


@check
def check_empty_message_error_is_still_a_read_failure(E):
    # ui_v2 `fetch_error` tests truthiness (an empty message would be dropped); this producer is intentionally stricter.
    ev = build(E, DS(_cost_ds()["holding"], errors={"holding": ""}))
    assert ev.source_coverage.status == "failed" and ev.source.read_errors.items == (("holding", ""),)
    assert build(E, DS(_cost_ds()["holding"], errors={"holding": None})).source_coverage.status == "complete"


@check
def check_unreadable_holding_table_is_unknown_coverage_and_failed_valuation(E):
    ds = _cost_ds()
    tables = {k: v for k, v in ds.items() if k != "holding"}
    ev = build(E, ds, tables=tables)
    assert ev.source_coverage.status == "unknown" and "holding_table_unreadable" in ev.source_coverage.reason_codes
    assert ev.valuation_completeness.status == "failed" and "holding_table_unreadable" in ev.valuation_completeness.reason_codes
    assert ev.holdings == () and ev.evaluation_errors[0].stage == "holding_table"


@check
def check_category_is_unclassified_only_when_every_member_is(E):
    ds = DS([H("A", bucket=CORE, cost=1.0), H("C", bucket=None, cost=2.0)])
    ev = build(E, ds, category_fn=lambda h: "X")                       # one category with a classified and an unclassified member
    cat = _cat(ev, "X")
    assert cat.holding_count == 2 and cat.is_unclassified is False
    assert _by_code(ev, "C").is_unclassified is True and _by_code(ev, "A").is_unclassified is False
    only = build(E, DS([H("C", bucket=None, cost=2.0), H("D", bucket="other", cost=1.0)]), category_fn=lambda h: "X")
    assert _cat(only, "X").is_unclassified is True


@check
def check_dates_in_rows_are_iso_text_in_strict_json(E):
    import datetime as dt
    ds = DS([H("A")], [N("A", dt.date(2026, 10, 3), 10.0)], [FX(FX_USD, dt.date(2026, 10, 2), 30.0)], basis=MV)
    ds["nav"][0]["fetched_at"] = dt.datetime(2026, 10, 4, 1, 2, 3)
    ev = build(E, ds)
    data = _strict(E, ev)
    h = data["holdings"][0]
    assert h["nav"]["nav_date"] == "2026-10-03" and h["fx"]["obs_date"] == "2026-10-02"
    assert h["nav"]["fetched_at"] == "2026-10-04T01:02:03" and h["value_twd"] == 10.0 * 10.0 * 30.0


@check
def check_unsupported_types_do_not_break_strict_json(E):
    class Weird:
        pass
    ds = DS([H("A", cost=1.0)])
    ds["holding"][0]["fund_name"] = Weird()
    ds["holding"][0]["opened_on"] = float("nan")
    data = _strict(E, build(E, ds))
    assert data["holdings"][0]["fund_name"]["unsupported_type"] == "Weird"


# ═══════════════════════ real-module runs of the registry ═══════════════════════


@pytest.mark.parametrize("fn", CHECKS, ids=lambda f: f.__name__)
def test_registry_check_on_real_module(fn):
    fn(REAL)


def test_registry_is_not_trivially_small():
    names = [f.__name__ for f in CHECKS]
    assert len(names) == len(set(names)) >= 30, len(names)


# ═══════════════════════ purity, laziness, JSON ═══════════════════════


def _scenario_battery():
    return list(G._alo2_cases().values())


def test_inputs_are_never_mutated():
    for ds in _scenario_battery():
        before = copy.deepcopy(ds)
        prov = {"provenance": {"A": {"cache_fallback": True}}, "not_fresh": ["A"], "withheld": {"B": "x"}}
        prov_before = copy.deepcopy(prov)
        st = _settings_of(ds)
        st_before = copy.deepcopy(st)
        nnr = _nnr_of(ds)
        nnr_before = copy.deepcopy(nnr)
        src = _source_of(ds)
        src_before = copy.deepcopy(src)
        ev = REAL.build_allocation_evidence(
            ds, settings=st, nav_not_ready=nnr, fx_key_of=L.fx_key_for,
            basis_mode_of=lambda b: REAL.BasisMode(b != COST, b == MV), category_of=lambda h: L.category_of(h, st["bucket_names"]),
            source_state=src, nav_provenance=prov)
        assert ds == before or _same_with_nan(ds, before)
        assert prov == prov_before and st == st_before and nnr == nnr_before and src == src_before
        again = REAL.build_allocation_evidence(
            ds, settings=st, nav_not_ready=nnr, fx_key_of=L.fx_key_for,
            basis_mode_of=lambda b: REAL.BasisMode(b != COST, b == MV), category_of=lambda h: L.category_of(h, st["bucket_names"]),
            source_state=src, nav_provenance=prov)
        assert _json(ev) == _json(again)                                          # deterministic


def _same_with_nan(a, b):
    return json.dumps(a, sort_keys=True, default=repr) == json.dumps(b, sort_keys=True, default=repr)


def _json(ev):
    return json.dumps(REAL.to_primitive(ev), ensure_ascii=False, sort_keys=True, allow_nan=False)


def test_output_is_strict_json_and_round_trips_for_every_scenario():
    n = 0
    for label, ds in G._alo2_cases().items():
        ev = build(REAL, ds)
        text = _json(ev)                                                          # allow_nan=False -> strict JSON
        data = json.loads(text)
        assert json.loads(json.dumps(data)) == data, label
        n += 1
    assert n >= 100


def _walk(node, path=()):
    if isinstance(node, dict):
        for k, v in node.items():
            yield from _walk(v, path + (k,))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _walk(v, path + (i,))
    else:
        yield path, node


def test_missing_is_never_a_numeric_zero_in_the_json_form():
    seen_missing = 0
    for label, ds in G._alo2_cases().items():
        data = REAL.to_primitive(build(REAL, ds))
        for h in data["holdings"]:
            if h["value_status"] != "valued":
                assert h["value_twd"] is None, (label, h["fund_code"])
                seen_missing += 1
            if h["nav"]["status"] != "present":
                assert h["nav"]["nav_orig_ccy"] is None and h["nav"]["nav_date"] is None
            if h["fx"]["status"] != "present":
                assert h["fx"]["value_num"] is None
        for c in data["categories"]:
            if c["status"] == "missing":
                assert c["value_twd"] is None and c["share"]["share_of_covered_pct"] is None, label
        if data["denominator"]["verdict"] == "none":
            assert data["denominator"]["value_twd"] is None and data["coverage"]["covered_value_twd"] is None
        assert data["coverage"]["uncovered_value"]["status"] in ("not_computable", "none_uncovered", "not_evaluated")
        assert "value_twd" not in data["coverage"]["uncovered_value"]                # no numeric field at all
    assert seen_missing > 20


def test_no_field_claims_a_total_assets_or_full_percentage():
    keys = set()
    for ds in _scenario_battery():
        for path, _v in _walk(REAL.to_primitive(build(REAL, ds))):
            keys.update(str(p) for p in path if isinstance(p, str))
    bad = [k for k in keys if "total" in k.lower() or k.lower() in ("pct", "percent", "share_pct", "hundred_pct")]
    assert bad == [], bad
    assert "share_of_covered_pct" in keys and "covers_all_holdings" in keys


def test_whole_module_is_ascii_and_has_no_chinese_constant():
    source = _MODULE_PATH.read_text(encoding="utf-8")
    assert source.isascii()


def test_json_primitive_form_has_no_chinese_in_codes_only_data():
    """codes / status values are English; Chinese may appear only as data copied from the input (labels, source strings)."""
    ev = build(REAL, DS([H("A"), H("B", bucket=SAT, ccy="TWD", units=100.0)], NAV_ALL, [], basis=MV))
    data = REAL.to_primitive(ev)
    code_fields = [data["source_coverage"], data["valuation_completeness"], data["chart_comparability"],
                   data["denominator"]["verdict"], data["open_gates"], data["producer_id"], data["rule_ref"],
                   [h["value_status"] for h in data["holdings"]], [h["reason"] for h in data["holdings"]]]
    for _p, v in _walk(code_fields):
        assert not (isinstance(v, str) and not v.isascii()), v


# ═══════════════════════ domain-layer guard, single alignment rule ═══════════════════════


def _load_port_guard():
    path = _ROOT / "tests" / "test_v2_domain_port.py"
    spec = importlib.util.spec_from_file_location("_alloc_evidence_port_guard", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_domain_guard_covers_and_passes_the_new_module():
    guard = _load_port_guard()
    files = {p.name for p in guard._domain_files()}
    assert "allocation_evidence.py" in files                       # the real enumeration includes the new module
    source = _MODULE_PATH.read_text(encoding="utf-8")
    assert guard._domain_violations(source) == []
    # negative controls: the same guard bites on an appended offence
    assert guard._domain_violations(source + "\nimport streamlit\n")
    assert guard._domain_violations(source + "\nimport json\n")
    assert guard._domain_violations(source + "\nfrom ui_v2 import page_health\n")
    assert guard._domain_violations(source + "\nX = '資料未備'\n")
    assert guard._domain_violations(source + "\nx = open('a')\n")
    assert guard._domain_violations(source + "\nprint(1)\n")


def test_alignment_rule_has_exactly_one_implementation():
    hold = ast.parse((_ROOT / "services" / "v2_domain" / "holdings.py").read_text(encoding="utf-8"))
    funcs = {n.name: n for n in hold.body if isinstance(n, ast.FunctionDef)}
    body = lambda fn: ast.unparse(ast.Module(body=fn.body[1:], type_ignores=[]))      # noqa: E731 - without the docstring
    assert "obs_date" not in body(funcs["fx_rate_as_of"])                            # it only delegates
    assert "fx_row_as_of" in body(funcs["fx_rate_as_of"])
    assert "obs_date" in body(funcs["fx_row_as_of"])
    evidence = _MODULE_PATH.read_text(encoding="utf-8")
    assert "<= " not in evidence.replace("<= 0", "")                                  # no second comparison rule in the producer
    assert "fx_row_as_of" in evidence and "fx_rate_as_of" not in evidence


def test_fx_rate_as_of_still_equals_row_value_and_none_when_absent():
    rows = [FX(FX_USD, "2026-10-01", 29.0), FX(FX_USD, "2026-10-04", 31.0), FX(FX_EUR, "2026-10-03", 5.0),
            FX(FX_USD, "2026-10-04", 77.0)]
    for day in ("2026-09-01", "2026-10-01", "2026-10-03", "2026-10-04", "2026-10-09"):
        for key in (FX_USD, FX_EUR, "fx_twd_per_jpy"):
            row = D.fx_row_as_of(rows, day, key)
            rate = D.fx_rate_as_of(rows, day, key)
            assert (rate is None) if row is None else (rate == row["value_num"])
    assert D.fx_row_as_of(rows, "2026-10-09", FX_USD)["value_num"] == 31.0          # same-day tie -> first wins


def test_fx_rate_as_of_error_behaviour_is_unchanged():
    with pytest.raises(KeyError):
        D.fx_rate_as_of([{"indicator_key": "k", "obs_date": "2026-01-01"}], "2026-02-01", "k")   # missing value_num
    with pytest.raises(TypeError):
        D.fx_rate_as_of([{"indicator_key": "k", "obs_date": None, "value_num": 1.0}], "2026-02-01", "k")
    # a row of ANOTHER key is never compared (short-circuit on the key first): no TypeError, just None
    assert D.fx_rate_as_of([{"indicator_key": "k", "obs_date": None, "value_num": 1.0}], "2026-02-01", "other") is None


def test_programming_errors_raise_but_data_conditions_do_not():
    ok = dict(settings=None, nav_not_ready=None, fx_key_of=L.fx_key_for, basis_mode_of=lambda b: REAL.BasisMode(True, True))
    with pytest.raises(TypeError):
        REAL.build_allocation_evidence([], **ok)
    with pytest.raises(TypeError):
        REAL.build_allocation_evidence({}, **{**ok, "fx_key_of": None})
    with pytest.raises(TypeError):
        REAL.build_allocation_evidence({}, **{**ok, "category_of": 5})
    ev = REAL.build_allocation_evidence({}, **ok)                    # no `holding` key at all: recorded, not raised
    assert ev.evaluation_errors and ev.evaluation_errors[0].stage == "holding_table"
    assert ev.valuation_completeness.status == "failed" and "holding_table_unreadable" in ev.valuation_completeness.reason_codes


# ═══════════════════════ parity with ui_v2 `_build_alo2` ═══════════════════════

#: scenarios where the adapter cannot express the input (ALO raises KeyError because the settings rows are absent).
_PARITY_SKIPPED = {"settings:missing_row_key": "settings rows absent in the dataset: ALO raises KeyError; no settings to hand over"}


def _alo_outcome(ds):
    try:
        return L._build_alo2(ds), None
    except Exception as exc:  # noqa: BLE001
        return None, exc


def test_parity_with_build_alo2_over_every_golden_scenario():
    classes = {"rows": 0, "placeholder": 0, "raised": 0}
    diverged = []                    # scenarios where the evidence INTENTIONALLY differs from ALO (unproven target zero)
    for label, ds in G._alo2_cases().items():
        if label in _PARITY_SKIPPED:
            continue
        alo2, exc = _alo_outcome(ds)
        ev = build(REAL, ds)                                          # must never raise
        if exc is not None:
            classes["raised"] += 1
            status = (ev.source_coverage.status, ev.valuation_completeness.status)
            assert "failed" in status or ev.source_coverage.status == "unknown", (label, status, exc)
            assert ev.chart_comparability.status == "not_comparable", label
            continue
        if alo2["placeholder"] is not None:
            classes["placeholder"] += 1
            _parity_placeholder(label, alo2, ev)
            continue
        classes["rows"] += 1
        _parity_rows(label, ds, alo2, ev, diverged)
    assert classes["rows"] >= 60 and classes["placeholder"] >= 15 and classes["raised"] >= 8, classes


def _parity_rows(label, ds, alo2, ev, diverged):
    values = alo2["_values"]
    rows_by_bucket = {r["_bucket"]: r for r in alo2["_rows"]}
    from_holdings = [c for c in ev.categories if c.origin == "from_holdings"]
    assert [c.category for c in from_holdings] == list(values), label          # same categories, same order
    for c in from_holdings:
        slot = values[c.category]
        assert c.value_twd == slot["value"] or (math.isnan(c.value_twd) and math.isnan(slot["value"])), label
        assert c.holding_count == slot["count"], label
        assert (c.status == "missing") == (slot["value"] is None), label
    covered = {c for c, s in values.items() if s["value"] is not None}
    uncovered = {c for c, s in values.items() if s["value"] is None}
    assert set(ev.coverage.covered_categories) == covered and set(ev.coverage.uncovered_categories) == uncovered, label
    assert set(ev.coverage.uncovered_categories) == {r["_bucket"] for r in alo2["_rows"] if r["_value"] is None
                                                      and r["_bucket"] in values}, label
    # denominator: exactly the ALO accumulation
    alo_den = sum(v["value"] for v in values.values() if v["value"] is not None)
    if alo2["_no_denominator"]:
        assert ev.denominator.verdict == "none" and ev.denominator.value_twd is None, label
    elif isinstance(alo_den, float) and math.isnan(alo_den):
        assert ev.denominator.verdict == "non_finite", label
        return
    else:
        assert ev.denominator.value_twd == alo_den, label
        assert ev.denominator.verdict == ("incomplete" if uncovered else "complete"), label
    # per-category share = ALO current percent (where ALO computed one)
    for label_c, row in rows_by_bucket.items():
        cat = [c for c in ev.categories if c.category == label_c]
        assert len(cat) == 1, (label, label_c)
        unproven_zero = cat[0].origin == "target_without_holdings" and cat[0].value_origin == "unproven_zero"
        if unproven_zero:
            # EXPLICIT, ASSERTED DIVERGENCE from ui_v2: ALO shows 0.0 / 0.0% for a target category without holdings even when
            # the source is not proven complete; the evidence reports Missing there (value None, share not_computable).
            assert row["_current_pct"] == 0.0 and row["_value"] == 0.0, label
            assert cat[0].value_twd is None and cat[0].share.status == "not_computable", label
            assert ev.source_coverage.status != "complete", label
            diverged.append(label)
            continue
        if row["_current_pct"] is not None:
            assert cat[0].share.status == "computed" and cat[0].share.share_of_covered_pct == row["_current_pct"], label
        else:
            assert cat[0].share.share_of_covered_pct is None, label
        if row["_value"] is None and label_c in values:
            assert cat[0].status == "missing" and cat[0].share.status == "not_computable", label
        # target-without-holdings: ALO treats it as 0.0 value / count 0
        if label_c not in values:
            assert cat[0].origin == "target_without_holdings" and row["_value"] == 0.0, label
            assert cat[0].value_twd == 0.0 and cat[0].value_origin == "real_zero_by_rule", label
    # per-holding: own values sum (in holding order) to the category value when the category is valued
    for c in from_holdings:
        mine = [h for h in ev.holdings if h.category == c.category]
        assert len(mine) >= 1 and c.holding_count == len(mine)
        if c.status == "valued":
            acc = 0.0
            for h in mine:
                acc += h.value_twd
            assert acc == c.value_twd or (math.isnan(acc) and math.isnan(c.value_twd)), label
            assert all(h.counted_in_denominator for h in mine)
        else:
            assert not any(h.counted_in_denominator for h in mine)
            assert c.first_reason is not None and len(c.all_missing_holdings) >= 1
    # old ALO behaviour vs plan A: ALO shows a percentage next to an uncovered category; the evidence says so explicitly
    if uncovered and covered:
        assert ev.chart_comparability.status == "not_comparable" and ev.valuation_completeness.status == "incomplete"
        assert all(c.share.covers_all_holdings is False for c in ev.categories)
        assert ev.coverage.uncovered_value.status == "not_computable"
    # omitted rows / skipped tabs never leave source coverage at 'complete'
    if ds.get("skipped_tabs") or ds.get("skipped_holdings"):
        assert ev.source_coverage.status != "complete", label


def _parity_placeholder(label, alo2, ev):
    kind = alo2["placeholder"]["_empty_kind"]
    if alo2["_failed"]:
        assert "failed" in (ev.source_coverage.status, ev.valuation_completeness.status), label
        assert ev.chart_comparability.status == "not_comparable", label
    elif alo2["_holdings_empty"]:
        assert ev.valuation_completeness.status == "not_evaluated" and ev.valuation_completeness.reason_codes == ("no_holdings",), label
    elif alo2["_target_unset"]:
        assert ev.settings.targets.status in ("unset", "empty"), label
        assert ("targets_" + ev.settings.targets.status) in ev.chart_comparability.failing_conditions, label
        assert ev.chart_comparability.status != "comparable", label
    elif kind == "算不出來":
        assert ev.valuation_completeness.status == "not_evaluated" and "basis_unset" in ev.valuation_completeness.reason_codes, label
    else:
        assert kind == "來源缺", (label, kind)                         # every category missing: no denominator
        assert ev.denominator.verdict == "none" and ev.valuation_completeness.status == "incomplete", label
        assert ev.coverage.covered_categories == () and ev.coverage.uncovered_value.status == "not_computable", label


def test_parity_scenarios_cover_the_known_100_percent_difference():
    ds = G._alo2_cases()["known_diff:usd_missing_twd_valued_twd_100pct"]
    alo2, exc = _alo_outcome(ds)
    assert exc is None and alo2["_rows"][1]["_current_pct"] == 100.0          # the frozen current ui_v2 behaviour (kept, not fixed)
    ev = build(REAL, ds)
    assert _cat(ev, SAT).share.share_of_covered_pct == 100.0 and _cat(ev, SAT).share.covers_all_holdings is False
    assert ev.coverage.uncovered_categories == (CORE,) and ev.chart_comparability.status == "not_comparable"


# ═══════════════════════ fuzz: no raise, strict JSON ═══════════════════════


def _weird_values():
    cyclic = []
    cyclic.append(cyclic)
    return [None, 0, -1, 5, 1.5, float("nan"), float("inf"), True, "", "x", "abc", b"x", [], {}, [1], ["a"], [[]], [{}], [None],
            {"a": 1}, {1: 2}, (1, 2), {1, 2}, frozenset(), object(), datetime.date(2026, 1, 1), cyclic,
            [{"bucket": None, "weight_ratio": None}], [{"bucket": CORE, "weight_ratio": "x"}],
            [{"bucket": ["z"], "weight_ratio": 1}], [{"bucket": CORE}], {"k": {"k": [1, {"z": object()}]}}, lambda: 1,
            [{"bucket": CORE, "weight_ratio": float("nan")}], [{"bucket": CORE, "weight_ratio": float("inf")}]]


def _mv_ds():
    return DS([H("A"), H("B", bucket=SAT, ccy="TWD", units=100.0)], NAV_ALL, FX_STD(), basis=MV)


def test_fuzz_weird_settings_never_raise_and_stay_strict_json():
    n = 0
    for ds in (_cost_ds(), _mv_ds()):
        for key in ("basis", "targets", "tolerance", "bucket_names"):
            for weird in _weird_values():
                settings = {**_settings_of(ds), key: weird}
                ev = build(REAL, ds, settings=settings)
                data = _strict(REAL, ev)
                assert data["schema_version"] == 1
                n += 1
        for weird in _weird_values():                                         # the settings object itself
            _strict(REAL, build(REAL, ds, settings=weird))
            n += 1
    assert n > 300, n


def test_fuzz_weird_category_labels_never_raise():
    for weird in _weird_values():
        for ds in (_cost_ds(), _mv_ds()):
            ev = build(REAL, ds, category_fn=lambda h, w=weird: w)
            _strict(REAL, ev)
            try:
                hash(weird)
                continue                                                      # hashable labels are legal categories
            except TypeError:
                pass
            assert ev.valuation_completeness.status == "failed" and ev.chart_comparability.status == "not_comparable"


def test_fuzz_weird_other_arguments_never_raise():
    ds = _mv_ds()
    for weird in _weird_values():
        _strict(REAL, build(REAL, ds, nnr=weird))
        _strict(REAL, build(REAL, ds, source=weird))
        _strict(REAL, build(REAL, ds, prov=weird))
        for key in ("active_source", "errors", "skipped_tabs", "skipped_holdings"):
            _strict(REAL, build(REAL, ds, source={**_source_of(ds), key: weird}))
        for key in ("provenance", "withheld", "key_failed", "not_fresh", "too_old", "too_old_last"):
            _strict(REAL, build(REAL, ds, prov={key: weird}))
        for key in ("codes", "days", "last"):
            _strict(REAL, build(REAL, ds, nnr={"codes": [], "days": None, **{key: weird}}))
    for bad_tables in ({"holding": 5}, {"holding": [5]}, {"holding": [{}]}, {"holding": [H("A")], "nav": 5, "market_indicator": None},
                       {"holding": [H("A")], "nav": [5], "market_indicator": [5]}, {"holding": [None]},
                       {"holding": [H("A")], "nav": [{"fund_code": "A"}], "market_indicator": []}):
        ev = build(REAL, _mv_ds(), tables=bad_tables)
        _strict(REAL, ev)
        assert ev.chart_comparability.status != "comparable"


# ═══════════════════════ the duplicated share formula is pinned to ALO ═══════════════════════


def test_share_of_covered_equals_alo_current_pct_over_the_parity_scenarios():
    """`share_of_covered_pct` re-states `value / denominator * 100.0` (ui_v2 `_current_pct`). Duplicated on purpose, pinned here."""
    compared = 0
    for label, ds in G._alo2_cases().items():
        if label in _PARITY_SKIPPED:
            continue
        alo2, exc = _alo_outcome(ds)
        if exc is not None or alo2["placeholder"] is not None:
            continue
        ev = build(REAL, ds)
        shares = {c.category: c.share for c in ev.categories}
        for row in alo2["_rows"]:
            if row["_current_pct"] is not None and shares[row["_bucket"]].status == "computed":
                assert shares[row["_bucket"]].share_of_covered_pct == row["_current_pct"], (label, row["_bucket"])
                compared += 1
    assert compared > 80, compared


def test_unproven_target_zero_is_an_explicit_divergence_from_alo_and_proven_zero_is_not():
    targets = G.TARGETS + [{"bucket": BOND, "weight_ratio": 0.1}]
    rows = [H("A", cost=3000.0), H("C", bucket=SAT, cost=4000.0)]
    names = G.NAMES + (BOND,)
    for kw, proven in (({}, True), ({"skipped_tabs": [{"tab": "t"}]}, False)):
        ds = DS(rows, targets=targets, names=names, **kw)
        alo2, exc = _alo_outcome(ds)
        bond_row = [r for r in alo2["_rows"] if r["_bucket"] == BOND][0]
        assert exc is None and bond_row["_value"] == 0.0 and bond_row["_current_pct"] == 0.0     # ALO: a bare 0.0 either way
        bond = _cat(build(REAL, ds), BOND)
        if proven:
            assert bond.value_twd == 0.0 and bond.share.share_of_covered_pct == 0.0 and bond.value_origin == "real_zero_by_rule"
        else:
            assert bond.value_twd is None and bond.share.status == "not_computable" and bond.share.share_of_covered_pct is None
            assert bond.value_origin == "unproven_zero" and bond.value_reliable is False


@check
def check_hostile_active_source_does_not_raise(E):
    class Hostile:
        def __eq__(self, other):
            raise RuntimeError("boom")
        __hash__ = None

    for state in ({"active_source": Hostile(), "errors": {}, "skipped_tabs": [], "skipped_holdings": []},
                  {"active_source": 5, "errors": {}, "skipped_tabs": [], "skipped_holdings": []}):
        ev = build(E, _cost_ds(), source=state)
        assert ev.source.active_source == "invalid" and ev.source_coverage.status == "unknown"
        assert any(p.argument == "source_state.active_source" for p in ev.input_problems)
        _strict(E, ev)


@check
def check_withheld_and_too_old_last_distinguish_no_entry_from_not_provided(E):
    ds = DS([H("A"), H("B", bucket=SAT, ccy="TWD", units=100.0)], NAV_ALL, FX_STD(), basis=MV)
    ev = build(E, ds, prov={"withheld": {"B": "ccy_missing"}, "too_old_last": {"A": "2026-09-01"}})
    a, b = _by_code(ev, "A").nav_cause, _by_code(ev, "B").nav_cause
    assert a.withheld == "no_entry" and b.withheld == "ccy_missing"
    assert a.too_old_last == "2026-09-01" and b.too_old_last == "no_entry"
    none = _by_code(build(E, ds, prov={"not_fresh": ["A"]}), "A").nav_cause
    assert none.withheld == "not_provided" and none.too_old_last == "not_provided"
