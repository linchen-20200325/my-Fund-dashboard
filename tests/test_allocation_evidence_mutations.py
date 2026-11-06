# -*- coding: utf-8 -*-
"""BL-0542 G1-3: mutation tests for `services/v2_domain/allocation_evidence.py` - proof that the guards in
`tests/test_v2_domain_allocation_evidence.py` really bite (they are not an empty sweep).

Method (same style as `tests/test_alo_core_golden_mutations.py`): read the CURRENT source of the producer, apply ONE in-memory
string replacement (the old string must occur EXACTLY once, otherwise this file goes red: the target vanished or became
ambiguous), exec the mutant into an isolated namespace (nothing written to disk, nothing put in `sys.modules`) and run the
whole `CHECKS` registry of the evidence test file against it. A mutant must make at least one check fail (raise).

Control: the unmutated source loaded by the same loader must pass every check, so "the mutant is red" is caused by the
mutation, not by the loading method.

Survivors (equivalent or unreachable mutations) must be listed in `SURVIVORS_DOCUMENTED` with a reason - no assertion is
padded just to kill one.
"""

from __future__ import annotations

import pathlib
import types

import pytest

import test_v2_domain_allocation_evidence as T

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_SRC = _ROOT / "services" / "v2_domain" / "allocation_evidence.py"

# (id, old (exactly once), new, what it breaks)
MUTATIONS = [
    ("E01_missing_value_becomes_zero", "value_status=status, value_twd=value, reason=",
     "value_status=status, value_twd=(0.0 if value is None else value), reason=", "missing holding value reported as 0"),
    ("E02_only_first_missing_reason_kept",
     "missing_members = tuple(MissingHolding(i.policy_id, i.fund_code, i.reason) for i in group if i.value_status == MISSING)",
     "missing_members = tuple(MissingHolding(i.policy_id, i.fund_code, i.reason) for i in group if i.value_status == MISSING)[:1]",
     "category keeps only the first missing holding's reason"),
    ("E03_counted_in_denominator_ignores_category_rule", "counted = i.valued and not is_missing", "counted = i.valued",
     "a valued holding of an excluded category is counted"),
    ("E04_coverage_complete_ignores_skipped_tabs", "if skip_evidence and aggregated:", "if False and aggregated:",
     "skipped tabs / omitted rows no longer downgrade source coverage"),
    ("E05_uncovered_amount_fabricated",
     'NOT_COMPUTABLE, ("missing_holdings_have_no_value",) + (() if proven_scope else ("source_scope_not_proven",)))',
     'NOT_COMPUTABLE if False else "computed", ())', "uncovered scope reported as computable"),
    ("E06_provenance_not_provided_becomes_false", "        if prov is None:\n            return NOT_PROVIDED\n",
     "        if prov is None:\n            return False\n", "absent side channel read as False"),
    ("E07_chart_ignores_denominator_verdict", "if evaluate and verdict not in (DEN_COMPLETE, DEN_INCOMPLETE):", "if False:",
     "chart comparability no longer looks at the denominator verdict"),
    ("E08_covers_all_ignores_source_coverage",
     "covers_all = verdict == DEN_COMPLETE and src_status == SRC_COMPLETE and valuation.status == VAL_COMPLETE",
     "covers_all = verdict == DEN_COMPLETE and valuation.status == VAL_COMPLETE", "share claims full scope with incomplete source"),
    ("E09_target_zero_loses_origin", "value_origin=REAL_ZERO_BY_RULE", "value_origin=None",
     "target-without-holdings real zero loses its origin"),
    ("E10_identity_conflict_not_recorded", "except _h.HoldingKeyConflict as exc:", "except ZeroDivisionError as exc:",
     "identity conflict stops being recorded as a conflict"),
    ("E11_twd_goes_through_fx_path", 'if nav["ccy"] == "TWD":', "if False:", "TWD holding also asks for an FX key"),
    ("E12_empty_holdings_with_skips_not_unknown", "        if skip_evidence and not aggregated:\n            unknown = True\n",
     "        if skip_evidence and not aggregated:\n            unknown = False\n", "empty holdings + skipped evidence no longer unknown"),
    ("E13_fx_candidates_dropped", 'seen = tuple(r["obs_date"] for r in table if r["indicator_key"] == key)', "seen = ()",
     "which-of-several FX rows is no longer visible"),
    ("E14_unset_basis_still_evaluated", "if echo.basis.status != SET and not settings_failed:", "if False:",
     "unset basis no longer blocks valuation"),
    ("E15_not_fresh_member_always_false", "        return code in parts[part]", "        return False",
     "membership flags from the side channel always False"),
    ("E16_incomplete_verdict_reported_complete", "    elif n_missing:\n        verdict = DEN_INCOMPLETE",
     "    elif n_missing:\n        verdict = DEN_COMPLETE", "partial denominator reported as complete"),
    ("E17_stale_entries_dropped", "stale_entries=tuple(merged.entries) if merged is not None else (),", "stale_entries=(),",
     "merged stale dates dropped from the category"),
    ("E18_unclassified_flag_lost", 'unclassified = _h.bucket_category(agg.get("bucket"), bucket_names) is None',
     "unclassified = False", "unclassified holding no longer marked"),
    ("E19_source_row_count_wrong", "source_row_count=len(raw_rows),", "source_row_count=1,",
     "merged raw row count lost"),
    ("E20_excluded_flag_never_set", "excluded_by_category_rule=i.valued and is_missing", "excluded_by_category_rule=False",
     "valued-but-excluded holding not flagged"),
    ("E21_uncovered_share_fabricated", "        return ShareFact(NOT_COMPUTABLE, None, covers_all)",
     "        return ShareFact(NOT_COMPUTABLE, 0.0, covers_all)", "uncovered category share reported as 0.0"),
    ("E22_share_ignores_incomplete_flag", "return ShareFact(\"computed\", value / denominator * 100.0, covers_all)",
     "return ShareFact(\"computed\", value / denominator * 100.0, True)", "share always claims the full scope"),
    ("E23_denominator_order_changed", "denominator = sum(s.value for s in slots.values() if s.value is not None)",
     "denominator = sum(sorted((s.value for s in slots.values() if s.value is not None), reverse=True))",
     "denominator accumulated in a different order"),
    ("E24_policy_error_ignored_by_coverage", "            incomplete = True\n            src_codes.append(\"non_holding_read_error\")",
     "            src_codes.append(\"non_holding_read_error\")", "non-holding table failure no longer downgrades coverage"),
    ("E25_invalid_nav_not_ready_not_blocking", '            hard.append("invalid_nav_not_ready")', "            pass",
     "malformed nav_not_ready no longer blocks the valuation"),
    ("E26_settings_failure_read_as_unset", "            return SettingFact(READ_FAILED, None)", "            return SettingFact(UNSET, None)",
     "a failed settings read is presented as 'unset'"),
    ("E27_active_none_not_recognised", 'if source.active_source == "none":\n        soft.append("no_active_source")',
     'if False:\n        soft.append("no_active_source")', "no Active source no longer blocks valuation"),
    ("E28_chart_comparable_with_incomplete_valuation", 'if valuation.status != VAL_COMPLETE:\n        failing.append("valuation_" + valuation.status)',
     "if False:\n        failing.append(\"valuation_\" + valuation.status)", "chart comparability ignores valuation completeness"),
]

MUTATIONS += [
    # ── audit round 1: A (never raises) ──
    ("F01_none_uncovered_ignores_source_proof", "elif evaluate and proven_scope and valuation.status == VAL_COMPLETE:",
     "elif evaluate and valuation.status == VAL_COMPLETE:", "'none_uncovered' emitted although the source is not proven complete"),
    ("F02_unproven_zero_reported_as_real_zero", "value_origin=REAL_ZERO_BY_RULE if proven_zero else UNPROVEN_ZERO,",
     "value_origin=REAL_ZERO_BY_RULE,", "target-without-holdings zero always 'real'"),
    ("F03_comparable_ignores_pending_gates", "    elif pending:\n        chart = ChartComparability(CHART_UNDETERMINED, pending, pending)",
     "    elif False:\n        chart = ChartComparability(CHART_UNDETERMINED, pending, pending)", "gates no longer stop 'comparable'"),
    ("F04_target_sum_exact_float_compare", "not math.isclose(echo.targets_weight_sum, 1.0, rel_tol=1e-9, abs_tol=1e-9)",
     "echo.targets_weight_sum != 1.0", "exact float equality for the target sum (CLAUDE.md 4.3)"),
    ("F05_fx_gate_not_provided_dropped", 'gates.append("fx_obs_date_rule_status_not_provided")', "pass",
     "missing FX-rule status no longer recorded"),
    ("F06_fx_gate_unverified_dropped", 'gates.append("fx_obs_date_rule_unverified")', "pass", "unverified FX rule no longer recorded"),
    ("F07_missing_target_weight_not_blocking", 'failing.append("target_weight_missing")', "pass",
     "a target without weight no longer blocks comparability"),
    ("F08_settings_failure_not_downgrading_coverage",
     '        if settings_failed:\n            incomplete = True\n            src_codes.append("settings_read_failed")',
     '        if False:\n            incomplete = True\n            src_codes.append("settings_read_failed")', "settings read failure leaves coverage complete"),
    ("F09_empty_message_error_dropped", "for t in raw.keys() if raw[t] is not None))", "for t in raw.keys() if raw[t]))",
     "an error with an empty message is dropped"),
    ("F10_fx_without_value_reported_present", "status = PRESENT if row[\"value_num\"] is not None else PRESENT_WITHOUT_VALUE",
     "status = PRESENT", "FX row without value reported as present"),
    ("F11_no_entry_reported_as_not_provided", "            return NO_ENTRY        # the side channel", "            return NOT_PROVIDED        # the side channel",
     "provided-but-no-entry collapsed into not_provided"),
    ("F12_known_table_errors_counted_as_non_holding",
     "other_error = any(t not in (_HOLDING_TABLE, _SETTINGS_TABLE) + _MARKET_INPUT_TABLES for t in error_tables)",
     "other_error = any(t != _HOLDING_TABLE for t in error_tables)", "nav / market_indicator / settings errors counted as non-holding errors"),
    ("F13_duplicate_target_gate_dropped", '        gates.append("target_duplicate_bucket_unjudged")', "        pass", "duplicate target buckets no longer recorded"),
    ("F14_unclassified_any_instead_of_all", "bool(group) and all(i.is_unclassified for i in group)",
     "bool(group) and any(i.is_unclassified for i in group)", "category unclassified when only SOME members are"),
    ("F15_unreadable_table_not_unknown_coverage",
     '        if table_unreadable:\n            unknown = True\n            src_codes.append("holding_table_unreadable")',
     '        if False:\n            unknown = True\n            src_codes.append("holding_table_unreadable")', "unreadable holding table leaves coverage complete"),
    ("F16_unreadable_table_not_blocking_valuation", '        hard.append("holding_table_unreadable")', "        pass",
     "unreadable holding table does not fail the valuation"),
    ("F17_unhashable_label_check_removed",
     "        hash(label)                      # a category label is a dict key downstream: unhashable is a recorded error\n", "",
     "unhashable category label no longer caught"),
    ("F18_bucket_names_not_validated",
     "if names.status in (SET, EMPTY) and not (isinstance(names.value, list) and all(isinstance(n, str) for n in names.value)):",
     "if False:", "malformed bucket_names accepted"),
    ("F19_target_weight_type_not_validated", '"weight_ratio" in t and weight_ok(t["weight_ratio"])', '"weight_ratio" in t',
     "a non-numeric target weight accepted"),
    ("F20_non_numeric_value_accepted", "elif isinstance(value, bool) or not isinstance(value, (int, float)):", "elif False:",
     "a non-numeric computed value accepted as valued"),
    ("F21_uncovered_own_value_flagged_counted", "i.value_twd is not None, False)", "i.value_twd is not None, True)",
     "an uncovered holding's own value flagged as counted"),
    ("F22_dates_not_iso_text", "if isinstance(value, datetime.date):          # also datetime.datetime (a subclass)", "if False:",
     "date objects left unconverted in the JSON form"),
    ("F23_value_reliable_ignores_source", "value_reliable=(not is_missing) and src_status == SRC_COMPLETE))",
     "value_reliable=not is_missing))", "summed category reliable although the source is not proven"),
    ("F24_target_zero_reliable_ignores_source", "                    value_reliable=proven_zero))",
     "                    value_reliable=True))", "target-without-holdings zero reliable although the source is not proven"),
    ("F25_tolerance_gate_dropped", '        gates.append("tolerance_unset_effect_unjudged")', "        pass", "unset tolerance no longer recorded"),
    ("F26_scope_not_proven_code_dropped", '(() if proven_scope else ("source_scope_not_proven",))', "()",
     "uncovered amount does not say that the source scope is unproven"),
    ("F27_stale_gate_dropped", '        gates.append("stale_nav_degradation_unjudged")', "        pass", "stale NAV question no longer recorded"),
    ("F28_ccy_disagreement_gate_dropped", '        gates.append("holding_nav_ccy_disagreement_unjudged")', "        pass",
     "holding vs NAV currency disagreement no longer recorded"),
    ("F29_fx_lag_gate_dropped", '        gates.append("fx_obs_date_lag_degradation_unjudged")', "        pass", "FX date lag no longer recorded"),
    ("F30_unclassified_gate_dropped", '        gates.append("unclassified_comparability_unjudged")', "        pass", "unclassified question no longer recorded"),
    ("G01_unproven_zero_returned_as_numeric_zero", "status=VALUED if proven_zero else NOT_COMPUTABLE, value_twd=0.0 if proven_zero else None,",
     "status=VALUED if proven_zero else NOT_COMPUTABLE, value_twd=0.0,", "unproven target zero reported as a numeric 0.0"),
    ("G02_unproven_zero_share_computed", "share=share_fact(0.0) if proven_zero else ShareFact(NOT_COMPUTABLE, None, covers_all),",
     "share=share_fact(0.0),", "unproven target zero gets a computed 0.0 share"),
    ("G03_active_source_compared_without_type_check", "if not (isinstance(active, str) and active in (\"selected\", \"none\")):",
     "if active not in (\"selected\", \"none\"):", "a hostile active_source reaches an equality comparison"),
    ("G04_lookup_no_entry_collapsed", "            return NO_ENTRY        # part provided, nothing for this fund",
     "            return None        # part provided, nothing for this fund", "withheld / too_old_last lose the no_entry state"),
    ("F31_fx_gate_not_checked_for_missing_rows", "if any(i.fx.status in (PRESENT, MISSING, PRESENT_WITHOUT_VALUE) for i in final_items):",
     "if any(i.fx.status == PRESENT for i in final_items):", "FX gate only when an FX row exists"),
]

MUTATIONS += [
    # ── Option D: NAV input state (nav_input_state / HoldingEvidence.nav_state) ──
    ("N01_declaration_ignored", "not_assembled = market and nav_input_state == NAV_INPUT_NOT_ASSEMBLED", "not_assembled = False",
     "a declared not_assembled no longer stops the evaluation"),
    ("N02_cost_basis_gated_off_market", "not_assembled = market and nav_input_state == NAV_INPUT_NOT_ASSEMBLED",
     "not_assembled = nav_input_state == NAV_INPUT_NOT_ASSEMBLED", "the declaration blocks the cost basis too"),
    ("N03_not_assembled_returned_as_no_data", "        return NAV_STATE_NOT_ASSEMBLED\n", "        return NAV_STATE_NO_DATA\n",
     "not assembled is reported as assembled-but-no-data"),
    ("N04_failed_vs_not_assembled_priority_swapped",
     "    if nav_table_failed:\n        return NAV_STATE_FAILED\n    if declared == NAV_INPUT_NOT_ASSEMBLED:\n        return NAV_STATE_NOT_ASSEMBLED\n",
     "    if declared == NAV_INPUT_NOT_ASSEMBLED:\n        return NAV_STATE_NOT_ASSEMBLED\n    if nav_table_failed:\n        return NAV_STATE_FAILED\n",
     "a nav read failure is hidden behind not_assembled"),
    ("N05_chart_failing_code_removed", '    if not_assembled:\n        failing.append("nav_not_assembled")', '    if False:\n        failing.append("nav_not_assembled")',
     "chart comparability no longer names the missing NAV assembly"),
    ("N06_not_in_prerequisite_only", ', "source_coverage_not_selected", "nav_not_assembled"}', ', "source_coverage_not_selected"}',
     "not_assembled is read as a blocking fact instead of a missing prerequisite"),
    ("N07_stale_not_rejected",
     "    if reason is not None and reason.code in (_h.REASON_NAV_STALE, _h.REASON_NAV_STALE_UNDATED):\n        return NAV_STATE_OBTAINED_REJECTED\n",
     "", "a stale-listed fund no longer reads as obtained-but-rejected"),
    ("N08_key_failed_ignored", "    if key_failed is True:\n        return NAV_STATE_FAILED\n", "", "a per-fund key failure is ignored"),
    ("N09_no_data_without_declaration", "    if declared == NAV_INPUT_ASSEMBLED and key_failed is False", "    if key_failed is False",
     "no_data claimed without the caller's declaration"),
    ("N10_cause_unknown_becomes_no_data", "    return NAV_STATE_CAUSE_UNKNOWN\n", "    return NAV_STATE_NO_DATA\n",
     "an unexplained missing row is reported as no data"),
    ("N11_echo_fixed_to_assembled", "nav_input_state=NOT_PROVIDED if nav_input_state is None else nav_input_state)",
     "nav_input_state=NAV_INPUT_ASSEMBLED)", "the echo of the declaration is fixed"),
    ("N12_invalid_declaration_accepted", '        raise TypeError("nav_input_state must be None', '        pass; ("nav_input_state must be None',
     "an invalid declaration is accepted"),
    ("N13_provenance_not_discarded_under_not_assembled", '            parts = None\n        if "nav" in error_tables:',
     '            pass\n        if "nav" in error_tables:', "assembler lists are still trusted although nothing was assembled"),
    ("N14_conflict_problem_removed",
     '            problems.append(InputProblem("nav_not_ready", "must be None when nav_input_state is not_assembled"))', "            pass",
     "a nav_not_ready given with not_assembled is silently dropped"),
    ("N15_soft_code_swapped", '        soft.append("nav_not_assembled")', '        soft.append("no_holdings")',
     "the missing NAV assembly is reported under another code"),
    # additional mutants of the new code (all must be killed as well)
    ("N16_no_data_ignores_key_failed_list", "key_failed is False and not_fresh is False and too_old is False and withheld is False:",
     "not_fresh is False and too_old is False and withheld is False:", "no_data without the key_failed list being provided"),
    ("N17_no_data_ignores_not_fresh_list", "key_failed is False and not_fresh is False and too_old is False and withheld is False:",
     "key_failed is False and too_old is False and withheld is False:", "no_data without the not_fresh list being provided"),
    ("N18_no_data_ignores_too_old_list", "key_failed is False and not_fresh is False and too_old is False and withheld is False:",
     "key_failed is False and not_fresh is False and withheld is False:", "no_data without the too_old list being provided"),
    ("N19_no_data_ignores_withheld_part", "key_failed is False and not_fresh is False and too_old is False and withheld is False:",
     "key_failed is False and not_fresh is False and too_old is False:", "no_data without the withheld part being provided"),
    ("N20_rejected_ignores_withheld", "if not_fresh is True or too_old is True or withheld is True:", "if not_fresh is True or too_old is True:",
     "a withheld fund is not obtained-but-rejected"),
    ("N21_rejected_ignores_not_fresh", "if not_fresh is True or too_old is True or withheld is True:", "if too_old is True or withheld is True:",
     "a not_fresh fund is not obtained-but-rejected"),
    ("N22_rejected_ignores_too_old", "if not_fresh is True or too_old is True or withheld is True:", "if not_fresh is True or withheld is True:",
     "a too_old fund is not obtained-but-rejected"),
    ("N23_table_failure_ignored", "    if nav_table_failed:\n        return NAV_STATE_FAILED\n", "", "a nav table read failure is not shown per holding"),
    ("N24_soft_code_dropped", '        soft.append("nav_not_assembled")', "        pass", "not_assembled no longer blocks the evaluation"),
    ("N25_nav_not_ready_not_neutralised", "        nav_nr = (frozenset(), None, None)\n    elif market:", "        nav_nr = None\n    elif market:",
     "the stale listing slot is left open under not_assembled"),
    ("N26_mode_known_ignored", "    if not mode_known:\n        return NAV_STATE_NOT_EVALUATED\n", "",
     "an unknown basis reads as not_required"),
    ("N27_cost_basis_state_dropped", "    if not market:\n        return NAV_STATE_NOT_REQUIRED\n", "",
     "the cost basis state depends on whether anything was evaluated"),
    ("N28_provenance_conflict_dropped",
     '            problems.append(InputProblem("nav_provenance", "must be None when nav_input_state is not_assembled"))',
     "            pass", "a nav_provenance given with not_assembled is silently dropped"),
    ("N29_errors_conflict_dropped",
     '            problems.append(InputProblem("nav_input_state", "not_assembled conflicts with a nav read error"))', "            pass",
     "not_assembled together with a nav read error is not recorded as a conflict"),
    ("N30_unknown_membership_read_as_false", "    if parts is None or part not in parts:\n        return None\n",
     "    if parts is None or part not in parts:\n        return False\n", "a side-channel part that was not provided is read as clear"),
    ("N31_version_not_bumped", "SCHEMA_VERSION = 2 ", "SCHEMA_VERSION = 1 ", "schema version not bumped for the new fields"),
    # ── audit round: str subclass, priority pin, not_assembled + malformed nav_not_ready ──
    ("N32_str_subclass_accepted", "if nav_input_state is not None and not (type(nav_input_state) is str and",
     "if nav_input_state is not None and not (isinstance(nav_input_state, str) and", "a str subclass declaration passes validation"),
    ("N33_key_failed_outranks_stale_listing",
     "    if reason is not None and reason.code in (_h.REASON_NAV_STALE, _h.REASON_NAV_STALE_UNDATED):\n        return NAV_STATE_OBTAINED_REJECTED\n"
     "    key_failed = _in_part(parts, \"key_failed\", code)\n    if key_failed is True:\n        return NAV_STATE_FAILED\n",
     "    key_failed = _in_part(parts, \"key_failed\", code)\n    if key_failed is True:\n        return NAV_STATE_FAILED\n"
     "    if reason is not None and reason.code in (_h.REASON_NAV_STALE, _h.REASON_NAV_STALE_UNDATED):\n        return NAV_STATE_OBTAINED_REJECTED\n",
     "the priority between the stale listing and a key failure is swapped"),
    ("N34_not_assembled_validates_nav_not_ready", "        nav_nr = (frozenset(), None, None)\n    elif market:",
     "        nav_nr = _normalize_nav_not_ready(nav_not_ready, problems)\n    elif market:",
     "a malformed nav_not_ready under not_assembled is validated and turns into a second problem / hard failure"),
]

#: survivors -> reason (empty = every mutation is killed)
SURVIVORS_DOCUMENTED: dict = {}


def _load(mutation=None):
    source = _SRC.read_text(encoding="utf-8")
    if mutation is not None:
        mid, old, new, _doc = mutation
        count = source.count(old)
        assert count == 1, f"{mid}: old string occurs {count} times in allocation_evidence.py (must be exactly 1)"
        source = source.replace(old, new)
    ns = {"__name__": "services.v2_domain._mutant_allocation_evidence", "__package__": "services.v2_domain"}
    # dont_inherit: do not inherit this file's `from __future__ import annotations` (dataclass annotations must stay real).
    exec(compile(source, "<mutant:allocation_evidence>", "exec", dont_inherit=True), ns)   # noqa: S102 - repo's own source, one edit
    return types.SimpleNamespace(**{k: v for k, v in ns.items() if not k.startswith("__")})


def _failures(module):
    failed = []
    for fn in T.CHECKS:
        try:
            fn(module)
        except Exception:  # noqa: BLE001 - any failure or crash of a check means "the mutant was noticed"
            failed.append(fn.__name__)
    return failed


def test_control_unmutated_loader_passes_every_check():
    assert _failures(_load()) == []


@pytest.mark.parametrize("mutation", [m for m in MUTATIONS if m[0] not in SURVIVORS_DOCUMENTED], ids=lambda m: m[0])
def test_mutation_is_killed(mutation):
    if mutation[0] == "E23_denominator_order_changed" and sum([0.1, 0.2, 0.3]) == sum([0.3, 0.2, 0.1]):
        pytest.skip("this interpreter's sum() is order-insensitive for the probe (CPython >= 3.12 compensated sum); "
                    "the order mutation cannot change a float result here")
    if mutation[0] == "F04_target_sum_exact_float_compare" and sum([0.6, 0.3, 0.1]) == 1.0:
        pytest.skip("this interpreter's builtin sum() is compensated (CPython >= 3.12): the target sum is exactly 1.0 here, so an "
                    "exact-equality mutant behaves identically; the mutation is observable (and killed) on CPython 3.11, the CI version")
    killers = _failures(_load(mutation))
    assert killers, f"{mutation[0]} ({mutation[3]}): no check noticed the mutation"


def test_survivor_targets_still_exist_and_have_reasons():
    for mid, reason in SURVIVORS_DOCUMENTED.items():
        _load(next(m for m in MUTATIONS if m[0] == mid))
        assert reason.strip()


def test_mutation_list_is_not_trivial_and_ids_are_unique():
    ids = [m[0] for m in MUTATIONS]
    assert len(ids) == len(set(ids)) >= 25


def test_mutants_do_not_pollute_sys_modules():
    import sys
    _load(MUTATIONS[0])
    assert not any("_mutant" in name for name in sys.modules)
