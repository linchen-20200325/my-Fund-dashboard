# -*- coding: utf-8 -*-
"""BL-0542 G1-3: pure producer of the allocation "Complete Evidence / Completeness" object (CANDIDATE design).

Purpose: a future human UI ViewModel and a future Decision Digest only READ the object built here; neither recomputes
a formula. Numeric and missing-value logic is NOT re-implemented: every number comes from the G1-2 core in
`services.v2_domain.holdings` (`aggregate_holding_rows`, `basis_value_with_reason`, `category_values`, `latest_nav_row`,
`fx_row_as_of`), so parity with `ui_v2/alo/logic.py` holds by construction.

Boundaries (approved: docs/v2/82 sections 3, 8, 9.4, 9.5; DEC-2026-11-04-02 plan A; DEC-2026-11-04-03):
- Domain layer: English-only machine codes; no UI wording; no I/O; no streamlit; no import of any UI package.
- Every name in this module is an INTERNAL CANDIDATE, not approved vocabulary (the schema version is CANDIDATE too).
- No new threshold, no new valuation or FX calculator. The NAV not-ready day count is a PARAMETER supplied by the caller
  inside `nav_not_ready`; this module never defines or owns it.
- Missing is never zero: an unknown amount is None with an explicit status code. No field expresses "100 percent of
  total assets"; a category share is named `share_of_covered` and carries `covers_all_holdings`.
- Anything that would need a NEW definition is not decided here; it is recorded as an `open_gates` code.

Inputs (all explicit; nothing global, nothing read from disk or network):
- `tables`: mapping with `holding`, `nav`, `market_indicator` row lists. `holding` is always read; `nav` and
  `market_indicator` are read lazily, only on the market-value path (same laziness as the G1-2 core).
- `settings`: mapping with optional keys `basis`, `targets`, `tolerance`, `bucket_names`. None means UNSET and stays unset.
  The basis label is opaque to the domain; `basis_mode_of(basis)` (injected) returns a `BasisMode`.
- `nav_not_ready`: already-normalized mapping `{codes, days[, last]}` or None (caller owns validation of the real shape;
  the domain only checks it minimally and reports a problem instead of raising).
- `fx_key_of(ccy)`, `basis_mode_of(basis)`, optional `category_of(holding)`: injected callables.
- `source_state` (optional): mapping with optional keys `active_source` ("selected" or "none"), `errors` ({table: message}),
  `skipped_tabs` (list of mappings), `skipped_holdings` (list of mappings). An absent key is "not provided", which is
  different from an empty list ("provided, none").
- `nav_provenance` (optional side channel, the same shape as `notes["nav"]` of the live assembler): optional keys
  `provenance`, `withheld`, `key_failed`, `not_fresh`, `too_old`, `too_old_last`. An absent part is "not_provided";
  a provided `provenance` with no entry for a fund gives "no_entry" for that fund's flags (different from "not_provided").
  Source strings and reasons are kept AS DATA and are never interpreted into new wording.
- `fx_rule_verified` (optional bool or None): whether the FX observation-date rule is verified. The domain cannot import
  `services.v2_tables`, so the caller passes `market_indicator.FX_OBS_DATE_RULE_VERIFIED`. None = not provided.
  Whenever a non-TWD FX was required an open gate is ALWAYS recorded (`fx_obs_date_rule_status_not_provided` for None,
  `fx_obs_date_rule_unverified` for False); True records no gate. Both gates affect chart comparability.
- `nav_input_state` (optional, CALLER-DECLARED, internal technical state): None = legacy behaviour (echoed as "not_provided";
  a missing NAV row never claims "no data" without a declaration, it is `cause_unknown`). "not_assembled" = the caller did NOT
  assemble the NAV side at all: on the market basis nothing is evaluated (all per-holding values None, `nav_state` is
  "not_assembled", valuation `not_evaluated` with the soft code `nav_not_assembled`, chart never `comparable`), `tables["nav"]`
  and `tables["market_indicator"]` are never read, and `nav_not_ready` / `nav_provenance` must be None (given anyway: recorded
  as an `InputProblem` and discarded). "assembled" = the caller claims it ran the assembler; the producer CANNOT verify that
  claim (it only lets a missing row be told apart as "no_data" when the assembler-supplied lists are clear, see `nav_state`).
  The cost basis does not use NAV, so the declaration is inert there (echoed only).
  `HoldingEvidence.nav_state` (per holding, all internal codes, no wording): "not_required" (cost basis), "not_evaluated"
  (basis unknown / nothing evaluated), "not_assembled", "failed" (`source_state.errors["nav"]`, or the fund is in
  `nav_provenance["key_failed"]`), "present", "error" (the trace itself raised), and for a MISSING row: "obtained_rejected"
  (the fund is in `nav_not_ready` or in the assembler's `not_fresh` / `too_old` / `withheld`), "no_data" (declared
  "assembled", the assembler lists `key_failed` / `not_fresh` / `too_old` / `withheld` are provided and hold nothing for the fund),
  else "cause_unknown". The producer reads only the assembler-supplied lists; it never interprets per-fund cache_fallback /
  stale / estimated flags itself and adds no threshold. Missing is never 0, complete, comparable or safe.
  CONTRACT RISK (found by audit): "no_data" relies on the caller converting the assembler's error (assemble_nav["error"]) into
  `source_state.errors["nav"]`. If a caller omits that conversion, a per-fund fetch failure with a declared "assembled" and
  empty lists would be classified "no_data"; the producer cannot verify the claim.

Output: frozen dataclasses (`AllocationEvidence` at the root) and `to_primitive()` for a JSON-primitive form.
The producer NEVER raises for data or settings conditions (identity conflict, non-positive denominator, a failing or
misbehaving injected callable, malformed settings, unhashable category labels, ...); it records them as `input_problems` /
`evaluation_errors` and downgrades the assessments. It raises only for programming errors (a non-callable argument,
`tables` not a mapping, `fx_rule_verified` not None/bool, `nav_input_state` not None / "not_assembled" / "assembled").

chart_comparability (CANDIDATE states):
- `comparable`: no blocking fact and no comparability-affecting open gate.
- `not_comparable`: a blocking FACT exists (basis/targets not usable, source coverage not complete, valuation not complete,
  denominator not positive, identity conflict, a target category with `weight_ratio` None = `target_weight_missing`).
- `not_evaluated`: only prerequisites are missing (basis or targets unset, nothing to value, no Active source).
- `undetermined`: no blocking fact, but at least one judgment-pending gate is raised (`pending_gates`): the producer does
  not claim comparable and does not claim not_comparable. `tolerance_unset_effect_unjudged` is recorded but is NOT
  comparability-affecting (the tolerance only drives in/out-of-band judgments, not the share-vs-target comparison).
"""

import dataclasses
import datetime
import math

from services.v2_domain import holdings as _h

__all__ = (
    "PRODUCER_ID", "SCHEMA_VERSION", "BasisMode", "AllocationEvidence", "build_allocation_evidence", "to_primitive",
    "NOT_PROVIDED", "NOT_COMPUTABLE", "NOT_EVALUATED", "NOT_DEFINED", "NOT_REQUIRED", "PRESENT", "MISSING",
    "NAV_INPUT_NOT_ASSEMBLED", "NAV_INPUT_ASSEMBLED", "NAV_INPUT_STATES", "NAV_STATE_PRESENT", "NAV_STATE_NOT_REQUIRED",
    "NAV_STATE_NOT_EVALUATED", "NAV_STATE_ERROR", "NAV_STATE_NOT_ASSEMBLED", "NAV_STATE_FAILED", "NAV_STATE_NO_DATA",
    "NAV_STATE_OBTAINED_REJECTED", "NAV_STATE_CAUSE_UNKNOWN", "NAV_STATES",
)

PRODUCER_ID = "v2_domain.allocation_evidence"
SCHEMA_VERSION = 2   # CANDIDATE: the evidence schema is not an approved contract; bump on any field change.
#                      v2: + HoldingEvidence.nav_state, + AllocationEvidence.nav_input_state, + code `nav_not_assembled`.

# generic status codes
PRESENT = "present"
MISSING = "missing"
NOT_REQUIRED = "not_required"
NOT_PROVIDED = "not_provided"
NOT_COMPUTABLE = "not_computable"
NOT_EVALUATED = "not_evaluated"
NOT_DEFINED = "not_defined"
# setting statuses
SET = "set"
UNSET = "unset"
EMPTY = "empty"
READ_FAILED = "read_failed"
INVALID = "invalid"
# facet statuses
PROVIDED = "provided"
# holding value statuses
VALUED = "valued"
ERROR = "error"
# category origins
FROM_HOLDINGS = "from_holdings"
TARGET_WITHOUT_HOLDINGS = "target_without_holdings"
REAL_ZERO_BY_RULE = "real_zero_by_rule"
UNPROVEN_ZERO = "unproven_zero"    # a target-without-holdings 0.0 while source coverage is not complete
PRESENT_WITHOUT_VALUE = "present_without_value"   # an FX row was picked but its value_num is None
NO_ENTRY = "no_entry"   # side channel provided, but it has no entry for this fund
SUMMED = "summed"
# source_coverage statuses
SRC_COMPLETE = "complete"
SRC_INCOMPLETE = "incomplete"
SRC_UNKNOWN = "unknown"
SRC_FAILED = "failed"
SRC_NOT_SELECTED = "not_selected"
# valuation_completeness statuses
VAL_COMPLETE = "complete"
VAL_INCOMPLETE = "incomplete"
VAL_NOT_EVALUATED = NOT_EVALUATED
VAL_FAILED = "failed"
# chart_comparability statuses
CHART_COMPARABLE = "comparable"
CHART_NOT_COMPARABLE = "not_comparable"
CHART_NOT_EVALUATED = NOT_EVALUATED
CHART_UNDETERMINED = "undetermined"
# denominator verdicts
DEN_COMPLETE = "complete"
DEN_INCOMPLETE = "incomplete"
DEN_NONE = "none"
DEN_NON_POSITIVE = "non_positive"
DEN_NON_FINITE = "non_finite"
# NAV input declaration (CALLER-DECLARED; internal technical codes only) and per-holding NAV state
NAV_INPUT_NOT_ASSEMBLED = "not_assembled"
NAV_INPUT_ASSEMBLED = "assembled"
NAV_INPUT_STATES = (NAV_INPUT_NOT_ASSEMBLED, NAV_INPUT_ASSEMBLED)
NAV_STATE_PRESENT = PRESENT
NAV_STATE_NOT_REQUIRED = NOT_REQUIRED
NAV_STATE_NOT_EVALUATED = NOT_EVALUATED
NAV_STATE_ERROR = ERROR
NAV_STATE_NOT_ASSEMBLED = "not_assembled"        # declared: the NAV side was never assembled / attempted
NAV_STATE_FAILED = "failed"                      # the NAV read / key failed
NAV_STATE_NO_DATA = "no_data"                    # assembled, nothing failed, nothing removed, and no row for this fund
NAV_STATE_OBTAINED_REJECTED = "obtained_rejected"   # obtained but rejected by the data-validity requirements
NAV_STATE_CAUSE_UNKNOWN = "cause_unknown"        # row missing and the evidence cannot say why
NAV_STATES = (NAV_STATE_PRESENT, NAV_STATE_NOT_REQUIRED, NAV_STATE_NOT_EVALUATED, NAV_STATE_ERROR, NAV_STATE_NOT_ASSEMBLED,
              NAV_STATE_FAILED, NAV_STATE_NO_DATA, NAV_STATE_OBTAINED_REJECTED, NAV_STATE_CAUSE_UNKNOWN)

_SETTING_KEYS = ("basis", "targets", "tolerance", "bucket_names")
_SOURCE_KEYS = ("active_source", "errors", "skipped_tabs", "skipped_holdings")
_PROVENANCE_KEYS = ("provenance", "withheld", "key_failed", "not_fresh", "too_old", "too_old_last")
_HOLDING_TABLE = "holding"
_SETTINGS_TABLE = "user_setting"
_MARKET_INPUT_TABLES = ("nav", "market_indicator")
#: open gates that bear on whether the chart may be called comparable (judgments the domain must not make silently).
#: `tolerance_unset_effect_unjudged`, `omitted_row_reason_codes_undefined`, `non_holding_read_error_effect_unjudged`
#: are deliberately NOT in this set (see the module docstring).
_CHART_AFFECTING_GATES = frozenset((
    "unclassified_comparability_unjudged", "target_weight_sum_rule_undefined", "target_duplicate_bucket_unjudged",
    "fx_obs_date_lag_degradation_unjudged", "stale_nav_degradation_unjudged", "holding_nav_ccy_disagreement_unjudged",
    "fx_obs_date_rule_status_not_provided", "fx_obs_date_rule_unverified"))


# ----------------------------- output dataclasses -----------------------------


@dataclasses.dataclass(frozen=True)
class BasisMode:
    """Result of the injected `basis_mode_of(basis)`: which path the G1-2 core takes for a set basis."""

    market: bool
    track_stale: bool


@dataclasses.dataclass(frozen=True)
class ErrorFact:
    """An exception recorded as evidence (never swallowed silently). `message` is kept as given."""

    stage: str
    error_type: str
    message: str


@dataclasses.dataclass(frozen=True)
class InputProblem:
    """A malformed argument component, reported instead of raised. `argument` names it."""

    argument: str
    message: str


@dataclasses.dataclass(frozen=True)
class ReasonFact:
    """Why a value is missing. `code` is one of the G1-2 `REASON_*` codes. A merged stale category reason has
    `code == "nav_stale"` and `stale_entries == ((fund_code, last_nav_day), ...)`."""

    code: str
    fx_key: object
    stale_day: object
    stale_days: object
    stale_entries: tuple


@dataclasses.dataclass(frozen=True)
class RawRowFact:
    """One raw holding row merged into an aggregated holding (identity facts for tracing)."""

    holding_id: object
    policy_id: object
    fund_code: object
    fund_name: object
    bucket: object
    ccy: object
    units_shares: object
    cost_orig_ccy: object
    cost_twd: object


@dataclasses.dataclass(frozen=True)
class NavFact:
    """The NAV row actually used (or why there is none). `candidate_nav_dates` = every nav_date of that fund in table order."""

    status: str
    nav_date: object
    nav_orig_ccy: object
    ccy: object
    source_tier: object
    fetched_at: object
    is_estimated: object
    candidate_nav_dates: tuple


@dataclasses.dataclass(frozen=True)
class FxFact:
    """The FX row actually used. `candidate_obs_dates` = every obs_date of rows with this key, in table order, so the chosen
    `obs_date` can be told apart from the others. The alignment rule itself lives only in `holdings.fx_row_as_of`."""

    status: str
    fx_key: object
    indicator_key: object
    obs_date: object
    release_date: object
    value_num: object
    source_tier: object
    is_revised: object
    fetched_at: object
    candidate_obs_dates: tuple


@dataclasses.dataclass(frozen=True)
class NavCauseFact:
    """Per-fund cause details from the provenance side channel. Each field is the given value or the string
    "not_provided" (never invented, never False when unknown)."""

    cache_fallback: object
    stale: object
    estimated: object
    live_error: object
    withheld: object
    key_failed: object
    in_not_fresh: object
    in_too_old: object
    too_old_last: object


@dataclasses.dataclass(frozen=True)
class HoldingEvidence:
    """One aggregated holding (identity rule of `holdings.aggregate_holding_rows`: policy_id + fund_code)."""

    policy_id: object
    fund_code: object
    holding_id: object
    fund_name: object
    bucket: object
    category: object
    is_unclassified: object
    ccy: object
    units_shares: object
    cost_twd: object
    cost_orig_ccy: object
    source_row_count: int
    source_rows: tuple
    nav: NavFact
    fx: FxFact
    nav_ccy_matches_holding_ccy: object
    nav_cause: NavCauseFact
    nav_state: str   # one of NAV_STATES (internal technical code)
    value_status: str
    value_twd: object
    reason: object
    missing_kind: object
    valued: bool
    counted_in_denominator: bool
    excluded_by_category_rule: bool
    category_status: object
    category_first_reason: object
    errors: tuple


@dataclasses.dataclass(frozen=True)
class MissingHolding:
    policy_id: object
    fund_code: object
    reason: object


@dataclasses.dataclass(frozen=True)
class ShareFact:
    """`share_of_covered_pct` = category value / covered denominator * 100. It is NOT a share of total assets unless
    `covers_all_holdings` is True."""

    status: str
    share_of_covered_pct: object
    covers_all_holdings: bool


@dataclasses.dataclass(frozen=True)
class TargetFact:
    status: str
    weight_ratio: object


@dataclasses.dataclass(frozen=True)
class CategoryEvidence:
    category: object
    origin: str
    is_unclassified: bool
    status: str
    value_twd: object
    value_origin: object
    holding_count: int
    valued_holding_count: int
    first_reason: object
    first_reason_kind: object
    stale_entries: tuple
    stale_days: object
    all_missing_holdings: tuple
    excluded_valued_holdings: tuple
    covered: bool
    target: TargetFact
    share: ShareFact
    value_reliable: bool   # True only for a valued category while source coverage is complete


@dataclasses.dataclass(frozen=True)
class DenominatorFacts:
    value_twd: object
    verdict: str
    raw_row_count: int
    aggregated_holding_count: int
    valued_holding_count: int
    counted_holding_count: int
    category_count: int
    covered_category_count: int
    excluded_category_count: int
    omitted_row_count: object
    skipped_tab_count: object


@dataclasses.dataclass(frozen=True)
class UncoveredHolding:
    """A holding that sits in an uncovered category. `own_value_twd` is the holding's OWN value (None when it has none);
    it is NOT an uncovered amount and was NOT counted in the denominator (`own_value_counted` is always False)."""

    policy_id: object
    fund_code: object
    category: object
    own_value_status: str
    own_value_twd: object
    own_value_known: bool
    own_value_counted: bool


@dataclasses.dataclass(frozen=True)
class UncoveredAmount:
    """The TWD amount of the uncovered scope is NOT computable (missing holdings have no value). Never 0."""

    status: str
    reason_codes: tuple


@dataclasses.dataclass(frozen=True)
class CoverageFacts:
    covered_value_twd: object
    covered_categories: tuple
    uncovered_categories: tuple
    uncovered_holdings: tuple
    uncovered_value: UncoveredAmount


@dataclasses.dataclass(frozen=True)
class ProvidedItems:
    """A source-state facet: `status` is "provided" / "not_provided" / "invalid"; `items` are kept AS GIVEN."""

    status: str
    items: tuple


@dataclasses.dataclass(frozen=True)
class SourceFacts:
    state_status: str
    active_source: str
    read_errors: ProvidedItems
    skipped_tabs: ProvidedItems
    omitted_rows: ProvidedItems


@dataclasses.dataclass(frozen=True)
class SettingFact:
    status: str
    value: object


@dataclasses.dataclass(frozen=True)
class SettingsEcho:
    basis: SettingFact
    targets: SettingFact
    tolerance: SettingFact
    bucket_names: SettingFact
    basis_market: object
    basis_track_stale: object
    targets_weight_sum: object


@dataclasses.dataclass(frozen=True)
class Assessment:
    status: str
    reason_codes: tuple


@dataclasses.dataclass(frozen=True)
class ChartComparability:
    status: str
    failing_conditions: tuple
    pending_gates: tuple


@dataclasses.dataclass(frozen=True)
class IdentityConflict:
    key: tuple
    columns: tuple


@dataclasses.dataclass(frozen=True)
class RuleRef:
    """Placeholder: no rule/threshold version exists anywhere in code today. Nothing is invented."""

    status: str


@dataclasses.dataclass(frozen=True)
class AllocationEvidence:
    producer_id: str
    schema_version: int
    rule_ref: RuleRef
    settings: SettingsEcho
    source: SourceFacts
    holdings: tuple
    categories: tuple
    denominator: DenominatorFacts
    coverage: CoverageFacts
    source_coverage: Assessment
    valuation_completeness: Assessment
    chart_comparability: ChartComparability
    identity_conflict: object
    evaluation_errors: tuple
    input_problems: tuple
    open_gates: tuple
    fx_rule_verified: object   # True / False, or "not_provided"
    nav_input_state: str       # echo of the caller's declaration: "not_provided" / "not_assembled" / "assembled"


# ----------------------------- small helpers -----------------------------


def _is_mapping(value) -> bool:
    return hasattr(value, "keys") and hasattr(value, "__getitem__")


def _plain(value):
    """Deep plain-data copy (dict / list / scalars). Anything else is a malformed input (TypeError)."""
    if value is None or isinstance(value, (bool, int, float, str, datetime.date)):
        return value
    if _is_mapping(value):
        if not all(isinstance(k, str) for k in value.keys()):
            raise TypeError("mapping keys must be strings")
        return {k: _plain(value[k]) for k in value.keys()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return sorted((_plain(v) for v in value), key=repr)
    raise TypeError(f"unsupported value type {type(value).__name__}")


def _error(stage, exc) -> ErrorFact:
    return ErrorFact(stage=stage, error_type=type(exc).__name__, message=str(exc))


def _reason_fact(reason):
    if reason is None:
        return None
    if isinstance(reason, _h.StaleMerge):
        return ReasonFact(_h.REASON_NAV_STALE, None, None, reason.days, tuple(reason.entries))
    return ReasonFact(reason.code, reason.fx_key, reason.stale_day, reason.stale_days, ())


def _is_codes(value) -> bool:
    return (not isinstance(value, (str, bytes))) and isinstance(value, (list, tuple, set, frozenset)) \
        and all(isinstance(c, str) and c for c in value)


# ----------------------------- input normalizers -----------------------------


def _settings_echo(settings, settings_read_failed, problems, basis_mode_of):
    """-> (SettingsEcho, BasisMode or None, targets list or None)."""
    given = {}
    if settings is not None:
        if not _is_mapping(settings):
            problems.append(InputProblem("settings", "settings must be a mapping or None"))
        else:
            for key in settings.keys():
                if key not in _SETTING_KEYS:
                    problems.append(InputProblem("settings", f"unknown settings key {key!r}"))
            given = {key: settings[key] for key in _SETTING_KEYS if key in settings.keys()}

    def fact(key):
        if settings_read_failed:
            return SettingFact(READ_FAILED, None)
        if settings is None or not _is_mapping(settings):
            return SettingFact(NOT_PROVIDED, None)
        value = given.get(key)
        if value is None:
            return SettingFact(UNSET, None)
        try:
            plain = _plain(value)
        except Exception as exc:  # noqa: BLE001 - malformed setting value: recorded as a problem, status invalid
            problems.append(InputProblem(f"settings.{key}", f"{type(exc).__name__}: {exc}"))
            return SettingFact(INVALID, None)
        if isinstance(plain, (list, str)) and len(plain) == 0:
            return SettingFact(EMPTY, plain)
        return SettingFact(SET, plain)

    basis, targets, tolerance, names = fact("basis"), fact("targets"), fact("tolerance"), fact("bucket_names")
    target_list, weight_sum = None, None
    if names.status in (SET, EMPTY) and not (isinstance(names.value, list) and all(isinstance(n, str) for n in names.value)):
        problems.append(InputProblem("settings.bucket_names", "bucket_names must be a list of strings"))
        names = SettingFact(INVALID, None)
    if targets.status == SET:
        def weight_ok(w):
            return w is None or (isinstance(w, (int, float)) and not isinstance(w, bool))
        ok = isinstance(targets.value, list) and all(
            isinstance(t, dict) and isinstance(t.get("bucket"), str) and "weight_ratio" in t and weight_ok(t["weight_ratio"])
            for t in targets.value)
        if ok:
            target_list = targets.value
            weight_sum = _h.target_sum(target_list)
        else:
            problems.append(InputProblem("settings.targets", "targets must be a list of {bucket: string, weight_ratio: number or None}"))
            targets = SettingFact(INVALID, None)
    mode = None
    if basis.status == SET:
        try:
            mode = basis_mode_of(basis.value)
            if not isinstance(getattr(mode, "market", None), bool) or not isinstance(getattr(mode, "track_stale", None), bool):
                raise TypeError("basis_mode_of must return an object with bool `market` and bool `track_stale`")
        except Exception as exc:  # noqa: BLE001 - recorded as evidence below, not swallowed
            problems.append(InputProblem("settings.basis", f"basis_mode_of failed: {type(exc).__name__}: {exc}"))
            mode = None
    echo = SettingsEcho(basis, targets, tolerance, names,
                        None if mode is None else mode.market, None if mode is None else mode.track_stale, weight_sum)
    return echo, mode, target_list


def _items(value, name, problems):
    """-> ProvidedItems for a list-of-mappings facet. An absent facet (None) is not_provided."""
    if value is None:
        return ProvidedItems(NOT_PROVIDED, ())
    if isinstance(value, (str, bytes)) or _is_mapping(value) or not isinstance(value, (list, tuple)):
        problems.append(InputProblem(f"source_state.{name}", "must be a list of mappings"))
        return ProvidedItems(INVALID, ())
    try:
        copied = tuple(_plain(v) for v in value)
    except Exception as exc:  # noqa: BLE001 - recorded as a problem
        problems.append(InputProblem(f"source_state.{name}", f"{type(exc).__name__}: {exc}"))
        return ProvidedItems(INVALID, ())
    if not all(isinstance(v, dict) for v in copied):
        problems.append(InputProblem(f"source_state.{name}", "every item must be a mapping"))
        return ProvidedItems(INVALID, ())
    return ProvidedItems(PROVIDED, copied)


def _source_facts(source_state, problems):
    if source_state is None:
        empty = ProvidedItems(NOT_PROVIDED, ())
        return SourceFacts(NOT_PROVIDED, NOT_PROVIDED, empty, empty, empty)
    if not _is_mapping(source_state):
        problems.append(InputProblem("source_state", "source_state must be a mapping or None"))
        empty = ProvidedItems(INVALID, ())
        return SourceFacts(INVALID, NOT_PROVIDED, empty, empty, empty)
    for key in source_state.keys():
        if key not in _SOURCE_KEYS:
            problems.append(InputProblem("source_state", f"unknown source_state key {key!r}"))
    active = NOT_PROVIDED
    if "active_source" in source_state.keys() and source_state["active_source"] is not None:
        active = source_state["active_source"]
        # isinstance first: a hostile object with a raising __eq__ must never reach a comparison
        if not (isinstance(active, str) and active in ("selected", "none")):
            problems.append(InputProblem("source_state.active_source", "must be 'selected' or 'none'"))
            active = INVALID
    errors = ProvidedItems(NOT_PROVIDED, ())
    if "errors" in source_state.keys() and source_state["errors"] is not None:
        raw = source_state["errors"]
        if not _is_mapping(raw):
            problems.append(InputProblem("source_state.errors", "must be a mapping {table: message}"))
            errors = ProvidedItems(INVALID, ())
        else:
            try:
                # A key that is present with ANY non-None message (even "") is a read failure. ui_v2 `fetch_error` uses
                # truthiness (an empty message would be dropped); this producer is intentionally stricter.
                errors = ProvidedItems(PROVIDED, tuple((t, _plain(raw[t])) for t in raw.keys() if raw[t] is not None))
            except Exception as exc:  # noqa: BLE001 - recorded as a problem
                problems.append(InputProblem("source_state.errors", f"{type(exc).__name__}: {exc}"))
                errors = ProvidedItems(INVALID, ())
    tabs = _items(source_state["skipped_tabs"] if "skipped_tabs" in source_state.keys() else None, "skipped_tabs", problems)
    rows = _items(source_state["skipped_holdings"] if "skipped_holdings" in source_state.keys() else None,
                  "skipped_holdings", problems)
    return SourceFacts(PROVIDED, active, errors, tabs, rows)


def _normalize_nav_not_ready(value, problems):
    """-> (codes frozenset, days, last dict or None) for the injected stale provider, or None when malformed."""
    if value is None:
        return frozenset(), None, None
    if not _is_mapping(value) or set(value.keys()) not in ({"codes", "days"}, {"codes", "days", "last"}):
        problems.append(InputProblem("nav_not_ready", "must be a mapping with keys codes, days[, last]"))
        return None
    codes, days = value["codes"], value["days"]
    if not _is_codes(codes):
        problems.append(InputProblem("nav_not_ready", "codes must be a list of non-empty strings"))
        return None
    if codes and (isinstance(days, bool) or not isinstance(days, int) or days < 0):
        problems.append(InputProblem("nav_not_ready", "days must be a non-negative integer when codes is not empty"))
        return None
    if "last" not in value.keys():
        return frozenset(codes), days, None
    last = value["last"]
    if not _is_mapping(last) or set(last.keys()) != set(codes) or not all(isinstance(last[c], str) for c in last.keys()):
        problems.append(InputProblem("nav_not_ready", "last must map exactly the codes to day strings"))
        return None
    return frozenset(codes), days, {c: last[c] for c in last.keys()}


def _normalize_provenance(value, problems):
    """-> dict of validated parts (absent part = not provided) or None when nothing usable was given."""
    if value is None:
        return None
    if not _is_mapping(value):
        problems.append(InputProblem("nav_provenance", "must be a mapping or None"))
        return None
    parts = {}
    for key in value.keys():
        if key not in _PROVENANCE_KEYS:
            problems.append(InputProblem("nav_provenance", f"unknown nav_provenance key {key!r}"))
            return None
    for key in _PROVENANCE_KEYS:
        if key not in value.keys() or value[key] is None:
            continue
        raw = value[key]
        if key in ("key_failed", "not_fresh", "too_old"):
            if not _is_codes(raw):
                problems.append(InputProblem(f"nav_provenance.{key}", "must be a list of codes"))
                return None
            parts[key] = frozenset(raw)
        else:
            if not _is_mapping(raw):
                problems.append(InputProblem(f"nav_provenance.{key}", "must be a mapping keyed by fund code"))
                return None
            try:
                parts[key] = {c: _plain(raw[c]) for c in raw.keys()}
            except Exception as exc:  # noqa: BLE001 - recorded as a problem
                problems.append(InputProblem(f"nav_provenance.{key}", f"{type(exc).__name__}: {exc}"))
                return None
    return parts


def _nav_cause(code, parts) -> NavCauseFact:
    try:
        hash(code)
    except TypeError:
        return NavCauseFact(*([NOT_PROVIDED] * 9))

    def flag(name):
        prov = (parts or {}).get("provenance")
        if prov is None:
            return NOT_PROVIDED
        if code not in prov:
            return NO_ENTRY        # the side channel was provided, but it has nothing for this fund
        entry = prov[code] or {}
        return entry[name] if isinstance(entry, dict) and name in entry else NOT_PROVIDED

    def member(part):
        if parts is None or part not in parts:
            return NOT_PROVIDED
        return code in parts[part]

    def lookup(part):
        if parts is None or part not in parts:
            return NOT_PROVIDED
        if code not in parts[part]:
            return NO_ENTRY        # part provided, nothing for this fund (different from not_provided)
        return parts[part][code]

    return NavCauseFact(
        cache_fallback=flag("cache_fallback"), stale=flag("stale"), estimated=flag("estimated"),
        live_error=flag("live_error"), withheld=lookup("withheld"), key_failed=member("key_failed"),
        in_not_fresh=member("not_fresh"), in_too_old=member("too_old"), too_old_last=lookup("too_old_last"))


def _in_part(parts, part, code):
    """True / False when the side-channel `part` was provided (membership of `code`), None when it was not provided."""
    if parts is None or part not in parts:
        return None
    try:
        hit = code in parts[part]
    except TypeError:        # an unhashable fund code: unknown, never "not in"
        return None
    return hit


def _nav_state(*, mode_known, market, declared, nav_table_failed, nav_fact, reason, parts, code):
    """Per-holding NAV state, derived ONLY from facts already in the evidence and the assembler-supplied lists.
    No threshold, no judgment of cache_fallback / stale / estimated flags (they are not read here)."""
    if not mode_known:
        return NAV_STATE_NOT_EVALUATED
    if not market:
        return NAV_STATE_NOT_REQUIRED
    if nav_table_failed:
        return NAV_STATE_FAILED
    if declared == NAV_INPUT_NOT_ASSEMBLED:
        return NAV_STATE_NOT_ASSEMBLED
    if nav_fact.status != MISSING:
        return nav_fact.status       # present / not_evaluated / error
    if reason is not None and reason.code in (_h.REASON_NAV_STALE, _h.REASON_NAV_STALE_UNDATED):
        return NAV_STATE_OBTAINED_REJECTED
    key_failed = _in_part(parts, "key_failed", code)
    if key_failed is True:
        return NAV_STATE_FAILED
    not_fresh, too_old, withheld = (_in_part(parts, name, code) for name in ("not_fresh", "too_old", "withheld"))
    if not_fresh is True or too_old is True or withheld is True:
        return NAV_STATE_OBTAINED_REJECTED
    if declared == NAV_INPUT_ASSEMBLED and key_failed is False and not_fresh is False and too_old is False and withheld is False:
        return NAV_STATE_NO_DATA
    return NAV_STATE_CAUSE_UNKNOWN


# ----------------------------- per-holding trace -----------------------------


def _row_get(row, key):
    return row.get(key) if hasattr(row, "get") else None


def _trace_nav_fx(holding, tables, market, fx_key_of):
    """-> (NavFact, FxFact, nav_ccy_matches). Uses only the G1-2 atoms; the NAV pick and the FX alignment rule are not re-implemented."""
    if not market:
        return (NavFact(NOT_REQUIRED, None, None, None, None, None, None, ()),
                FxFact(NOT_REQUIRED, None, None, None, None, None, None, None, None, ()), None)
    code = holding["fund_code"]
    nav = _h.latest_nav_row(tables["nav"], code)
    if nav is None:
        return (NavFact(MISSING, None, None, None, None, None, None, ()),
                FxFact(NOT_EVALUATED, None, None, None, None, None, None, None, None, ()), None)
    candidates = tuple(r["nav_date"] for r in tables["nav"] if r["fund_code"] == code)
    nav_fact = NavFact(PRESENT, nav["nav_date"], nav["nav_orig_ccy"], nav["ccy"], _row_get(nav, "source_tier"),
                       _row_get(nav, "fetched_at"), _row_get(nav, "is_estimated"), candidates)
    matches = nav["ccy"] == holding["ccy"]
    if nav["ccy"] == "TWD":
        return nav_fact, FxFact(NOT_REQUIRED, None, None, None, None, None, None, None, None, ()), matches
    key = fx_key_of(nav["ccy"])
    table = tables["market_indicator"]
    row = _h.fx_row_as_of(table, nav["nav_date"], key)
    seen = tuple(r["obs_date"] for r in table if r["indicator_key"] == key)
    if row is None:
        return nav_fact, FxFact(MISSING, key, None, None, None, None, None, None, None, seen), matches
    status = PRESENT if row["value_num"] is not None else PRESENT_WITHOUT_VALUE   # the core treats a None value as fx_absent
    return nav_fact, FxFact(status, key, row["indicator_key"], row["obs_date"], _row_get(row, "release_date"),
                            row["value_num"], _row_get(row, "source_tier"), _row_get(row, "is_revised"),
                            _row_get(row, "fetched_at"), seen), matches


def _empty_nav(status):
    return (NavFact(status, None, None, None, None, None, None, ()),
            FxFact(status, None, None, None, None, None, None, None, None, ()))


def _evaluate_holding(agg, raw_rows, tables, *, market, fx_key_of, stale_provider, evaluate, category_of, bucket_names, parts,
                      mode_known, declared, nav_table_failed):
    errors = []
    code = agg["fund_code"]
    nav_fact, fx_fact = _empty_nav(NOT_EVALUATED)
    matches = None
    value, missing, kind = None, None, None
    status = NOT_EVALUATED
    if evaluate:
        status = VALUED
        try:
            value, missing, kind = _h.basis_value_with_reason(
                agg, tables, market=market, fx_key_of=fx_key_of, stale_provider=stale_provider)
            if value is None:
                status = MISSING
            elif isinstance(value, bool) or not isinstance(value, (int, float)):
                status = ERROR
                errors.append(ErrorFact("basis_value", "TypeError", "computed value is not a number"))
        except Exception as exc:  # noqa: BLE001 - recorded as evidence, never swallowed
            status = ERROR
            errors.append(_error("basis_value", exc))
        try:
            nav_fact, fx_fact, matches = _trace_nav_fx(agg, tables, market, fx_key_of)
        except Exception as exc:  # noqa: BLE001 - recorded as evidence, never swallowed
            errors.append(_error("trace_nav_fx", exc))
            nav_fact, fx_fact = _empty_nav(ERROR)
    try:
        label = category_of(agg)
        hash(label)                      # a category label is a dict key downstream: unhashable is a recorded error
    except Exception as exc:  # noqa: BLE001 - recorded as evidence, never swallowed
        label = None
        status = ERROR if evaluate else status
        errors.append(_error("category_of", exc))
    try:
        unclassified = _h.bucket_category(agg.get("bucket"), bucket_names) is None
    except Exception as exc:  # noqa: BLE001 - recorded as evidence, never swallowed
        unclassified = None
        errors.append(_error("bucket_category", exc))
    nav_state = _nav_state(mode_known=mode_known, market=market, declared=declared, nav_table_failed=nav_table_failed,
                           nav_fact=nav_fact, reason=_reason_fact(missing), parts=parts, code=code)
    return HoldingEvidence(
        policy_id=agg["policy_id"], fund_code=code, holding_id=agg.get("holding_id"), fund_name=agg.get("fund_name"),
        bucket=agg.get("bucket"), category=label, is_unclassified=unclassified, ccy=agg.get("ccy"),
        units_shares=agg.get("units_shares"), cost_twd=agg.get("cost_twd"), cost_orig_ccy=agg.get("cost_orig_ccy"),
        source_row_count=len(raw_rows),
        source_rows=tuple(RawRowFact(*[_row_get(r, k) for k in (
            "holding_id", "policy_id", "fund_code", "fund_name", "bucket", "ccy", "units_shares", "cost_orig_ccy", "cost_twd")])
                          for r in raw_rows),
        nav=nav_fact, fx=fx_fact, nav_ccy_matches_holding_ccy=matches, nav_cause=_nav_cause(code, parts),
        nav_state=nav_state, value_status=status, value_twd=value, reason=_reason_fact(missing), missing_kind=kind,
        valued=(status == VALUED), counted_in_denominator=False, excluded_by_category_rule=False,
        category_status=None, category_first_reason=None, errors=tuple(errors))


# ----------------------------- main producer -----------------------------


def build_allocation_evidence(tables, *, settings, nav_not_ready, fx_key_of, basis_mode_of, category_of=None,
                              source_state=None, nav_provenance=None, fx_rule_verified=None, nav_input_state=None):
    """Build the `AllocationEvidence` for one allocation scope. Pure; never mutates its inputs; see the module docstring."""
    if not _is_mapping(tables):
        raise TypeError("tables must be a mapping")
    if not callable(fx_key_of) or not callable(basis_mode_of):
        raise TypeError("fx_key_of and basis_mode_of must be callable")
    if category_of is not None and not callable(category_of):
        raise TypeError("category_of must be callable or None")
    if fx_rule_verified is not None and not isinstance(fx_rule_verified, bool):
        raise TypeError("fx_rule_verified must be True, False or None")
    # exact type check: a str subclass (hostile __eq__ / __hash__) never gets in, so every later comparison and the echo
    # only ever see a plain str that was validated once here
    if nav_input_state is not None and not (type(nav_input_state) is str and nav_input_state in NAV_INPUT_STATES):
        raise TypeError("nav_input_state must be None, 'not_assembled' or 'assembled'")
    problems = []

    source = _source_facts(source_state, problems)
    error_tables = {t for t, _m in source.read_errors.items}
    settings_failed = _SETTINGS_TABLE in error_tables
    echo, mode, target_list = _settings_echo(settings, settings_failed, problems, basis_mode_of)
    parts = _normalize_provenance(nav_provenance, problems)
    names = echo.bucket_names.value if echo.bucket_names.status in (SET, EMPTY) else None
    if category_of is None:
        def category_of(holding, _names=names):
            return _h.bucket_category(holding["bucket"], _names)

    # -- identity: raw rows -> aggregated holdings (single source: holdings.aggregate_holding_rows) --
    evaluation_errors = []
    raw_rows, aggregated, conflict = [], [], None
    table_unreadable = False
    try:
        raw_rows = list(tables[_HOLDING_TABLE])
    except Exception as exc:  # noqa: BLE001 - recorded as evidence, never swallowed
        table_unreadable = True
        evaluation_errors.append(_error("holding_table", exc))
    aggregation_error = False
    if not table_unreadable:
        try:
            aggregated = _h.aggregate_holding_rows(raw_rows)
        except _h.HoldingKeyConflict as exc:
            conflict = IdentityConflict(tuple(exc.key), tuple(exc.columns))
        except Exception as exc:  # noqa: BLE001 - recorded as evidence, never swallowed
            aggregation_error = True
            evaluation_errors.append(_error("aggregate_holding_rows", exc))

    # -- what blocks evaluation --
    market = mode is not None and mode.market
    nav_nr = None
    not_assembled = market and nav_input_state == NAV_INPUT_NOT_ASSEMBLED
    if not_assembled:
        # declared "not assembled": no NAV-side input can exist, so nothing of it is read or trusted (fail closed)
        if nav_not_ready is not None:
            problems.append(InputProblem("nav_not_ready", "must be None when nav_input_state is not_assembled"))
        if nav_provenance is not None:
            problems.append(InputProblem("nav_provenance", "must be None when nav_input_state is not_assembled"))
            parts = None
        if "nav" in error_tables:
            problems.append(InputProblem("nav_input_state", "not_assembled conflicts with a nav read error"))
        nav_nr = (frozenset(), None, None)
    elif market:
        nav_nr = _normalize_nav_not_ready(nav_not_ready, problems)
    hard = []
    if conflict is not None:
        hard.append("identity_conflict")
    if aggregation_error:
        hard.append("aggregation_error")
    if table_unreadable:
        hard.append("holding_table_unreadable")
    if _HOLDING_TABLE in error_tables:
        hard.append("holding_read_failed")
    if settings_failed:
        hard.append("settings_read_failed")
    if echo.basis.status == SET and mode is None:
        hard.append("basis_mode_error")
    if echo.bucket_names.status == INVALID:
        hard.append("bucket_names_invalid")
    if market:
        for table in _MARKET_INPUT_TABLES:
            if table in error_tables:
                hard.append(table + "_read_failed")
        if nav_nr is None:
            hard.append("invalid_nav_not_ready")
    soft = []
    if source.active_source == "none":
        soft.append("no_active_source")
    if echo.basis.status != SET and not settings_failed:
        soft.append("basis_" + echo.basis.status)
    if not aggregated and conflict is None and not aggregation_error and not table_unreadable:
        soft.append("no_holdings")
    if not_assembled:
        soft.append("nav_not_assembled")
    evaluate = not hard and not soft

    # -- per-holding evaluation (single source: holdings.basis_value_with_reason) --
    stale_provider = (lambda: nav_nr) if nav_nr is not None else (lambda: (frozenset(), None, None))
    holding_items = []
    for agg in aggregated:
        group = [r for r in raw_rows if r["policy_id"] == agg["policy_id"] and r["fund_code"] == agg["fund_code"]]
        holding_items.append(_evaluate_holding(
            agg, group, tables, market=market, fx_key_of=fx_key_of, stale_provider=stale_provider, evaluate=evaluate,
            category_of=category_of, bucket_names=names, parts=parts, mode_known=mode is not None, declared=nav_input_state,
            nav_table_failed=market and "nav" in error_tables))
    any_item_error = any(item.errors for item in holding_items)
    if any_item_error:
        hard.append("holding_evaluation_error")
        evaluate = False

    # -- category level (single source: holdings.category_values) --
    slots, stale = {}, {}
    if evaluate:
        try:
            slots, stale = _h.category_values(
                aggregated, tables, market=market, track_stale=mode.track_stale, category_of=category_of,
                fx_key_of=fx_key_of, stale_provider=stale_provider)
        except Exception as exc:  # noqa: BLE001 - recorded as evidence, never swallowed
            hard.append("category_evaluation_error")
            evaluation_errors.append(_error("category_values", exc))
            slots, stale = {}, {}
            evaluate = False

    target_of = {}
    duplicate_targets = False
    if target_list is not None:
        for t in target_list:
            duplicate_targets = duplicate_targets or t["bucket"] in target_of
            target_of[t["bucket"]] = t["weight_ratio"]

    # denominator: same expression and order as the ALO core (`sum` over category values in category order)
    n_valued = sum(1 for s in slots.values() if s.value is not None)
    n_missing = sum(1 for s in slots.values() if s.value is None)
    denominator = sum(s.value for s in slots.values() if s.value is not None)
    if n_valued == 0:
        verdict = DEN_NONE
    elif not math.isfinite(denominator):
        verdict = DEN_NON_FINITE
    elif denominator <= 0:
        verdict = DEN_NON_POSITIVE
    elif n_missing:
        verdict = DEN_INCOMPLETE
    else:
        verdict = DEN_COMPLETE
    den_value = None if verdict == DEN_NONE else denominator
    nonfinite_holding = any(
        item.valued and isinstance(item.value_twd, float) and not math.isfinite(item.value_twd) for item in holding_items)

    # -- source_coverage --
    n_omitted = len(source.omitted_rows.items) if source.omitted_rows.status == PROVIDED else None
    n_tabs = len(source.skipped_tabs.items) if source.skipped_tabs.status == PROVIDED else None
    src_codes = []
    if source.active_source == "none":
        src_status = SRC_NOT_SELECTED
        src_codes.append("no_active_source")
    else:
        failed = _HOLDING_TABLE in error_tables
        other_error = any(t not in (_HOLDING_TABLE, _SETTINGS_TABLE) + _MARKET_INPUT_TABLES for t in error_tables)
        skip_evidence = bool(n_omitted) or bool(n_tabs)
        incomplete = False
        unknown = False
        if failed:
            src_codes.append("holding_read_failed")
        if skip_evidence and aggregated:
            incomplete = True
            if n_tabs:
                src_codes.append("skipped_tabs_present")
            if n_omitted:
                src_codes.append("omitted_rows_present")
        if skip_evidence and not aggregated:
            unknown = True
            src_codes.append("skip_evidence_without_holdings")
        if settings_failed:
            incomplete = True
            src_codes.append("settings_read_failed")
        if other_error:
            incomplete = True
            src_codes.append("non_holding_read_error")
        for facet, name in ((source.active_source, "active_source"), (source.read_errors.status, "read_errors"),
                            (source.skipped_tabs.status, "skipped_tabs"), (source.omitted_rows.status, "omitted_rows")):
            if facet == INVALID:
                unknown = True
                src_codes.append(name + "_invalid")
            elif facet == NOT_PROVIDED:
                unknown = True
                src_codes.append(name + "_not_provided")
        if table_unreadable:
            unknown = True
            src_codes.append("holding_table_unreadable")
        if failed:
            src_status = SRC_FAILED
        elif incomplete:
            src_status = SRC_INCOMPLETE
        elif unknown:
            src_status = SRC_UNKNOWN
        else:
            src_status = SRC_COMPLETE
    source_coverage = Assessment(src_status, tuple(src_codes))

    # -- valuation_completeness --
    val_failed = list(hard)
    if evaluate and verdict == DEN_NON_POSITIVE:
        val_failed.append("denominator_non_positive")
    if evaluate and verdict == DEN_NON_FINITE:
        val_failed.append("denominator_not_finite")
    if evaluate and nonfinite_holding:
        val_failed.append("holding_value_not_finite")
    val_incomplete = []
    if evaluate and n_valued == 0 and slots:
        val_incomplete.append("no_category_valued")
    if evaluate and n_missing:
        val_incomplete.append("category_missing")
    if val_failed:
        valuation = Assessment(VAL_FAILED, tuple(val_failed + soft))
    elif soft:
        valuation = Assessment(VAL_NOT_EVALUATED, tuple(soft))
    elif val_incomplete:
        valuation = Assessment(VAL_INCOMPLETE, tuple(val_incomplete))
    else:
        valuation = Assessment(VAL_COMPLETE, ())
    covers_all = verdict == DEN_COMPLETE and src_status == SRC_COMPLETE and valuation.status == VAL_COMPLETE
    share_ok = evaluate and verdict in (DEN_COMPLETE, DEN_INCOMPLETE)

    # -- categories --
    members = {}
    for item in holding_items:
        members.setdefault(item.category, []).append(item)
    categories = []
    final_items = list(holding_items)
    index = {id(item): n for n, item in enumerate(holding_items)}

    def target_fact(label):
        if label not in target_of:
            return TargetFact("no_target", None)
        weight = target_of[label]
        return TargetFact("weight_unset" if weight is None else SET, weight)

    def share_fact(value):
        # NOTE: this is the same expression as ui_v2 `_build_alo2` `_current_pct` (`value / denominator * 100.0`). The
        # duplication is parity-locked (tests compare it with ALO's `_current_pct` over every golden scenario); retire it
        # when ui_v2 reads this object.
        if share_ok and value is not None:
            return ShareFact("computed", value / denominator * 100.0, covers_all)
        return ShareFact(NOT_COMPUTABLE, None, covers_all)

    for label, slot in slots.items():
        group = members.get(label, [])
        missing_members = tuple(MissingHolding(i.policy_id, i.fund_code, i.reason) for i in group if i.value_status == MISSING)
        valued_members = [i for i in group if i.valued]
        is_missing = slot.value is None
        first = _reason_fact(slot.reason)
        merged = stale.get(label)
        categories.append(CategoryEvidence(
            category=label, origin=FROM_HOLDINGS, is_unclassified=bool(group) and all(i.is_unclassified for i in group),
            status=MISSING if is_missing else VALUED, value_twd=slot.value, value_origin=None if is_missing else SUMMED,
            holding_count=slot.count, valued_holding_count=len(valued_members), first_reason=first,
            first_reason_kind=slot.kind, stale_entries=tuple(merged.entries) if merged is not None else (),
            stale_days=merged.days if merged is not None else None, all_missing_holdings=missing_members,
            excluded_valued_holdings=tuple((i.policy_id, i.fund_code) for i in valued_members) if is_missing else (),
            covered=not is_missing, target=target_fact(label), share=share_fact(slot.value),
            value_reliable=(not is_missing) and src_status == SRC_COMPLETE))
        for i in group:
            counted = i.valued and not is_missing
            final_items[index[id(i)]] = dataclasses.replace(
                i, counted_in_denominator=counted, excluded_by_category_rule=i.valued and is_missing,
                category_status=MISSING if is_missing else VALUED, category_first_reason=first if is_missing else None)
    if evaluate:
        for label in target_of:
            if label not in slots:
                # ALO shows 0.0 here. The evidence agrees ONLY when the source is proven complete (a real zero by rule);
                # otherwise the zero is unproven, so value and share are Missing (None / not_computable), never 0.0.
                proven_zero = src_status == SRC_COMPLETE
                categories.append(CategoryEvidence(
                    category=label, origin=TARGET_WITHOUT_HOLDINGS, is_unclassified=False,
                    status=VALUED if proven_zero else NOT_COMPUTABLE, value_twd=0.0 if proven_zero else None,
                    value_origin=REAL_ZERO_BY_RULE if proven_zero else UNPROVEN_ZERO,
                    holding_count=0, valued_holding_count=0, first_reason=None,
                    first_reason_kind=None, stale_entries=(), stale_days=None, all_missing_holdings=(),
                    excluded_valued_holdings=(), covered=False, target=target_fact(label),
                    share=share_fact(0.0) if proven_zero else ShareFact(NOT_COMPUTABLE, None, covers_all),
                    value_reliable=proven_zero))

    uncovered_cats = tuple(c.category for c in categories if c.origin == FROM_HOLDINGS and not c.covered)
    covered_cats = tuple(c.category for c in categories if c.origin == FROM_HOLDINGS and c.covered)
    uncovered_holdings = tuple(
        UncoveredHolding(i.policy_id, i.fund_code, i.category, i.value_status, i.value_twd, i.value_twd is not None, False)
        for i in final_items if i.category_status == MISSING)
    proven_scope = src_status == SRC_COMPLETE
    if uncovered_cats:
        uncovered_value = UncoveredAmount(
            NOT_COMPUTABLE, ("missing_holdings_have_no_value",) + (() if proven_scope else ("source_scope_not_proven",)))
    elif evaluate and proven_scope and valuation.status == VAL_COMPLETE:
        uncovered_value = UncoveredAmount("none_uncovered", ())      # only when the source is proven complete AND nothing is uncovered
    else:
        uncovered_value = UncoveredAmount(NOT_EVALUATED, ("source_coverage_" + src_status,) if evaluate and not proven_scope else ())
    coverage = CoverageFacts(den_value, covered_cats, uncovered_cats, uncovered_holdings, uncovered_value)
    denominator_facts = DenominatorFacts(
        value_twd=den_value, verdict=verdict, raw_row_count=len(raw_rows), aggregated_holding_count=len(aggregated),
        valued_holding_count=sum(1 for i in final_items if i.valued),
        counted_holding_count=sum(1 for i in final_items if i.counted_in_denominator),
        category_count=len(slots), covered_category_count=len(covered_cats), excluded_category_count=len(uncovered_cats),
        omitted_row_count=n_omitted, skipped_tab_count=n_tabs)

    # -- open gates: judgments that would need a NEW definition are recorded, never decided --
    gates = []
    if any(c.is_unclassified for c in categories):
        gates.append("unclassified_comparability_unjudged")
    if target_list is not None and not math.isclose(echo.targets_weight_sum, 1.0, rel_tol=1e-9, abs_tol=1e-9):
        gates.append("target_weight_sum_rule_undefined")      # tolerance per CLAUDE.md 4.3: never an exact float compare
    if duplicate_targets:
        gates.append("target_duplicate_bucket_unjudged")
    if any(i.fx.status == PRESENT and i.fx.obs_date != i.nav.nav_date for i in final_items):
        gates.append("fx_obs_date_lag_degradation_unjudged")
    if any(i.nav_ccy_matches_holding_ccy is False for i in final_items):
        gates.append("holding_nav_ccy_disagreement_unjudged")
    if any(i.reason is not None and i.reason.code in (_h.REASON_NAV_STALE, _h.REASON_NAV_STALE_UNDATED) for i in final_items):
        gates.append("stale_nav_degradation_unjudged")
    if any(i.fx.status in (PRESENT, MISSING, PRESENT_WITHOUT_VALUE) for i in final_items):   # a non-TWD FX was required
        if fx_rule_verified is None:
            gates.append("fx_obs_date_rule_status_not_provided")
        elif fx_rule_verified is False:
            gates.append("fx_obs_date_rule_unverified")
    if echo.tolerance.status in (UNSET, NOT_PROVIDED):
        gates.append("tolerance_unset_effect_unjudged")   # recorded; NOT comparability-affecting (see module docstring)
    if n_omitted:
        gates.append("omitted_row_reason_codes_undefined")
    if "non_holding_read_error" in src_codes:
        gates.append("non_holding_read_error_effect_unjudged")

    # -- chart_comparability: derived ONLY from the facts and gates above --
    failing = []
    if echo.basis.status != SET:
        failing.append("basis_" + echo.basis.status)
    if echo.targets.status != SET:
        failing.append("targets_" + echo.targets.status)
    if any(t["weight_ratio"] is None for t in (target_list or ())):
        failing.append("target_weight_missing")             # a blocking FACT (a target without a weight cannot be compared)
    if src_status != SRC_COMPLETE:
        failing.append("source_coverage_" + src_status)
    if valuation.status != VAL_COMPLETE:
        failing.append("valuation_" + valuation.status)
    if evaluate and verdict not in (DEN_COMPLETE, DEN_INCOMPLETE):
        failing.append("denominator_not_positive")
    if conflict is not None:
        failing.append("identity_conflict")
    if not_assembled:
        failing.append("nav_not_assembled")                 # a prerequisite is missing: nothing was evaluated
    pending = tuple(g for g in gates if g in _CHART_AFFECTING_GATES)
    prerequisite_only = {"basis_unset", "basis_not_provided", "targets_unset", "targets_empty", "targets_not_provided",
                         "valuation_not_evaluated", "source_coverage_not_selected", "nav_not_assembled"}
    if failing:
        status = CHART_NOT_EVALUATED if all(code in prerequisite_only for code in failing) else CHART_NOT_COMPARABLE
        chart = ChartComparability(status, tuple(failing), pending)
    elif pending:
        chart = ChartComparability(CHART_UNDETERMINED, pending, pending)
    else:
        chart = ChartComparability(CHART_COMPARABLE, (), ())

    return AllocationEvidence(
        producer_id=PRODUCER_ID, schema_version=SCHEMA_VERSION, rule_ref=RuleRef(NOT_DEFINED), settings=echo, source=source,
        holdings=tuple(final_items), categories=tuple(categories), denominator=denominator_facts, coverage=coverage,
        source_coverage=source_coverage, valuation_completeness=valuation, chart_comparability=chart,
        identity_conflict=conflict, evaluation_errors=tuple(evaluation_errors + [e for i in final_items for e in i.errors]),
        input_problems=tuple(problems), open_gates=tuple(gates),
        fx_rule_verified=NOT_PROVIDED if fx_rule_verified is None else fx_rule_verified,
        nav_input_state=NOT_PROVIDED if nav_input_state is None else nav_input_state)


# ----------------------------- JSON-primitive form -----------------------------


def to_primitive(value):
    """Dataclasses -> dict, tuples -> list, dates -> ISO text, scalars as-is. A non-finite float becomes
    {"non_finite": "nan"|"inf"|"-inf"} and a value of an unsupported type becomes {"unsupported_type", "repr"}, so the
    result is always strict JSON. Missing stays None (never 0). Non-string dict keys are rendered with repr()."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: to_primitive(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, (list, tuple)):
        return [to_primitive(v) for v in value]
    if isinstance(value, dict):
        return {(k if isinstance(k, str) else repr(k)): to_primitive(v) for k, v in value.items()}
    if isinstance(value, datetime.date):          # also datetime.datetime (a subclass)
        return value.isoformat()
    if isinstance(value, float):
        if math.isfinite(value):
            return value
        return {"non_finite": "nan" if math.isnan(value) else ("inf" if value > 0 else "-inf")}
    if value is None or isinstance(value, (bool, int, str)):
        return value
    return {"unsupported_type": type(value).__name__, "repr": repr(value)}
