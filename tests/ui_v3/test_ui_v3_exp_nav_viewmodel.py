# -*- coding: utf-8 -*-
"""🔍 找基金 NAV／輔助判定 sibling：view model 不變式與 adapter 契約（全部離線、零網路；A-EXP-NAV-SIBLING-FAKE-1）。

沿用 `ui_v3/fixtures/exp_lookup_fake.py` 內既有的 NAV-ADMISSION-CASES 合成案（FAKE-ZZ*），不另製案例。
所有負控在記憶體內現編。
"""
from __future__ import annotations

import ast
import dataclasses
import pathlib

import pytest

import ui_v3.fixtures.exp_lookup_fake as fake
from ui_v3.adapters.exp_nav import adapt_exp_nav, load_exp_nav
from ui_v3.viewmodels import exp_nav as M
from ui_v3.viewmodels.fund_lookup import FieldView, FundLookupView, ProfileFields

ROOT = pathlib.Path(__file__).resolve().parents[2]

# 代碼 → (淨值狀態, 3-3-3 種類, 吃本金種類, 配息狀態)
EXPECTED = {
    "FAKE-ZZC1": ("withheld_conflict", "undetermined", "undetermined", "present"),
    "FAKE-ZZC1B": ("withheld_conflict", "undetermined", "undetermined", "present"),
    "FAKE-ZZ10A": ("withheld_not_admitted", "undetermined", "undetermined", "present"),
    "FAKE-ZZ10B": ("verified", "pass_evidenced", "pass_evidenced", "present"),
    "FAKE-ZZC2": ("verified", "undetermined", "undetermined", "missing"),
    "FAKE-ZZC2B": ("verified", "fail_evidenced", "undetermined", "missing"),
    "FAKE-ZZC3A": ("verified", "fail_evidenced", "fact_no_dividend", "confirmed_none"),
    "FAKE-ZZC3B": ("verified", "undetermined", "fact_no_dividend", "confirmed_none"),
    "FAKE-ZZC3D": ("verified", "undetermined", "undetermined", "missing"),
    "FAKE-ZZR4": ("verified", "pass_evidenced", "pass_evidenced", "present"),
    "FAKE-ZZR3": ("verified", "undetermined", "undetermined", "present"),
}


def _nav(**over):
    base = dict(display=M.NavDisplay.VERIFIED, nav_value="1.2345", ccy="美元", nav_date="2026-11-20", source_label="合成來源", cache_updated_at="2026-11-21")
    base.update(over)
    return M.NavSummaryView(**base)


def _undet(reason="input_conflict"):
    return M.MetricView(M.MetricKind.UNDETERMINED, reason)


def _judge(a=None, b=None, div=M.DividendStatus.PRESENT):
    return M.JudgementView(a or _undet(), b or _undet(), div)


@pytest.mark.parametrize("code", sorted(EXPECTED))
def test_every_synthetic_case_builds_the_expected_view(code):
    v = load_exp_nav(fake.make_nav_loader(), code)
    nav_state, k333, keat, div = EXPECTED[code]
    assert (v.nav.display.value, v.judgement.three_three_three.kind.value, v.judgement.eating_principal.kind.value, v.judgement.dividend_status.value) == (nav_state, k333, keat, div)


def test_every_demo_zz_code_is_covered_and_plain_codes_have_no_sibling():
    assert {c for c in fake.DEMO_CODES if c.startswith("FAKE-ZZ")} == set(EXPECTED)
    for code in fake.DEMO_CODES:
        if not code.startswith("FAKE-ZZ"):
            assert load_exp_nav(fake.make_nav_loader(), code) is None


def test_withheld_views_never_carry_a_nav_value_or_a_nav_currency():
    for code, (state, *_rest) in EXPECTED.items():
        v = load_exp_nav(fake.make_nav_loader(), code)
        if state != "verified":
            assert v.nav.nav_value is None and v.nav.ccy is None and v.nav.nav_date is None, code
            assert v.judgement.three_three_three.kind is M.MetricKind.UNDETERMINED and v.judgement.eating_principal.kind is M.MetricKind.UNDETERMINED


def test_supplier_time_is_unknown_unless_the_case_gives_one_and_is_never_filled_from_the_cache_time():
    for code in EXPECTED:
        n = load_exp_nav(fake.make_nav_loader(), code).nav
        if code.startswith("FAKE-ZZC3"):
            assert n.supplier_fetched_at == "2026-11-20T09:30Z"          # 原始時間戳原值保留（不截成日期、不等於快取時間）
            assert n.supplier_fetched_at != n.cache_updated_at
        else:
            assert n.supplier_fetched_at is None          # 預存檔（cache_only 形）：未知，不得以快取時間代填
        assert n.cache_updated_at is not None
        assert n.ccy_declared_at != n.cache_updated_at or code.startswith("FAKE-ZZC3")   # 幣別自報時間獨立，不等於 NAV 的快取時間


# ───────────────────────── 不變式負控（每一條都要能讓契約拋錯） ─────────────────────────

@pytest.mark.parametrize("build", [
    lambda: _nav(display=M.NavDisplay.WITHHELD_CONFLICT, reason_codes=("input_conflict",), conflicts=(M.ConflictDiag("nav_before_inception", "2011-11-18", "2020-02-03"),)),
    lambda: _nav(display=M.NavDisplay.WITHHELD_NOT_ADMITTED, reason_codes=("rights_unverified",)),
    lambda: _nav(display=M.NavDisplay.MISSING),
], ids=["conflict", "not_admitted", "missing"])
def test_a_nav_value_on_a_non_verified_view_is_rejected(build):
    with pytest.raises(M.ExpNavContractError):
        build()


def test_verified_requires_currency_date_source_and_cache_time():
    for field in ("ccy", "nav_date", "source_label", "cache_updated_at", "nav_value"):
        with pytest.raises(M.ExpNavContractError):
            _nav(**{field: None})


def test_conflict_view_requires_the_diagnostics_and_the_reason():
    with pytest.raises(M.ExpNavContractError):
        M.NavSummaryView(M.NavDisplay.WITHHELD_CONFLICT, ("input_conflict",))
    with pytest.raises(M.ExpNavContractError):
        M.NavSummaryView(M.NavDisplay.WITHHELD_CONFLICT, ("rights_unverified",), conflicts=(M.ConflictDiag("nav_before_inception", "2011-11-18", "2020-02-03"),))


def test_not_admitted_may_not_claim_a_conflict_and_needs_a_reason():
    with pytest.raises(M.ExpNavContractError):
        M.NavSummaryView(M.NavDisplay.WITHHELD_NOT_ADMITTED, ())
    with pytest.raises(M.ExpNavContractError):
        M.NavSummaryView(M.NavDisplay.WITHHELD_NOT_ADMITTED, ("input_conflict",))


def test_layer_f_withheld_nav_forces_both_metrics_undetermined():
    nav = M.NavSummaryView(M.NavDisplay.WITHHELD_NOT_ADMITTED, ("rights_unverified",))
    ok = _judge()
    assert M.ExpNavView(nav, ok)
    for bad in (M.MetricView(M.MetricKind.FAIL_EVIDENCED, None, (("a", "b"),)), M.MetricView(M.MetricKind.PASS_EVIDENCED, None, (("a", "b"),))):
        with pytest.raises(M.ExpNavContractError):
            M.ExpNavView(nav, _judge(a=bad))
        with pytest.raises(M.ExpNavContractError):
            M.ExpNavView(nav, _judge(b=bad))
    with pytest.raises(M.ExpNavContractError):         # 扣下時不得出現「已證實無配息」
        M.ExpNavView(nav, M.JudgementView(_undet(), M.MetricView(M.MetricKind.FACT_NO_DIVIDEND), M.DividendStatus.CONFIRMED_NONE))


def test_no_dividend_fact_and_missing_dividends_cannot_stand_in_for_each_other():
    fact = M.MetricView(M.MetricKind.FACT_NO_DIVIDEND)
    with pytest.raises(M.ExpNavContractError):         # 事實項但配息狀態不是 confirmed-none
        _judge(b=fact, div=M.DividendStatus.MISSING)
    with pytest.raises(M.ExpNavContractError):
        _judge(b=fact, div=M.DividendStatus.PRESENT)
    with pytest.raises(M.ExpNavContractError):         # confirmed-none 卻不是事實項
        _judge(b=_undet("dividend_not_obtained"), div=M.DividendStatus.CONFIRMED_NONE)
    with pytest.raises(M.ExpNavContractError):         # 配息未取得時吃本金只能無法判定
        _judge(b=M.MetricView(M.MetricKind.PASS_EVIDENCED, None, (("a", "b"),)), div=M.DividendStatus.MISSING)
    with pytest.raises(M.ExpNavContractError):         # 3-3-3 不能是配息事實
        _judge(a=fact, b=fact, div=M.DividendStatus.CONFIRMED_NONE)


def test_metric_view_rules():
    with pytest.raises(M.ExpNavContractError):
        M.MetricView(M.MetricKind.UNDETERMINED)                         # 無法判定必須有原因
    with pytest.raises(M.ExpNavContractError):
        M.MetricView(M.MetricKind.UNDETERMINED, "not_a_reason")
    with pytest.raises(M.ExpNavContractError):
        M.MetricView(M.MetricKind.FAIL_EVIDENCED, "input_conflict", (("a", "b"),))   # 有證據的結果不帶原因
    with pytest.raises(M.ExpNavContractError):
        M.MetricView(M.MetricKind.FAIL_EVIDENCED)                       # 有證據的結果必須有證據
    with pytest.raises(M.ExpNavContractError):
        M.MetricView(M.MetricKind.UNDETERMINED, "input_conflict", (("a", "http://x"),))  # 網址形字串


def test_dates_must_be_real_iso_dates_and_unknown_codes_are_rejected():
    for bad in ("2026-13-01", "20261121", "yesterday"):
        with pytest.raises(M.ExpNavContractError):
            _nav(nav_date=bad)
    with pytest.raises(M.ExpNavContractError):
        M.NavSummaryView(M.NavDisplay.WITHHELD_NOT_ADMITTED, ("made_up",))
    with pytest.raises(M.ExpNavContractError):
        M.ConflictDiag("made_up", "2011-11-18", "2020-02-03")


def test_contract_error_messages_never_echo_the_received_value():
    secret = "SECRET-VALUE-123"
    try:
        _nav(nav_date=secret)
    except M.ExpNavContractError as exc:
        assert secret not in str(exc)
    else:
        raise AssertionError("expected a contract error")


# ───────────────────────── adapter ─────────────────────────

def test_adapter_rejects_unknown_keys_missing_keys_and_wrong_types():
    good = fake.make_nav_loader()("FAKE-ZZ10B")
    assert adapt_exp_nav(good)
    with pytest.raises(M.ExpNavContractError):
        adapt_exp_nav({**good, "extra": 1})
    with pytest.raises(M.ExpNavContractError):
        adapt_exp_nav({"nav": good["nav"]})
    with pytest.raises(M.ExpNavContractError):
        adapt_exp_nav("not a dict")
    bad_nav = {**good["nav"], "display": "mystery"}
    with pytest.raises(M.ExpNavContractError):
        adapt_exp_nav({**good, "nav": bad_nav})
    with pytest.raises(M.ExpNavContractError):
        adapt_exp_nav({**good, "nav": {**good["nav"], "surprise": 1}})


def test_adapter_does_not_swallow_a_contract_violation_into_a_missing_value():
    good = fake.make_nav_loader()("FAKE-ZZ10B")
    bad = {**good, "nav": {**good["nav"], "display": "withheld_conflict"}}       # 仍帶淨值 → 必須拋
    with pytest.raises(M.ExpNavContractError):
        adapt_exp_nav(bad)


def test_loader_must_be_callable_and_query_non_blank_and_none_means_no_sibling():
    with pytest.raises(M.ExpNavContractError):
        load_exp_nav("nope", "FAKE-ZZC1")
    with pytest.raises(M.ExpNavContractError):
        load_exp_nav(lambda q: None, "   ")
    assert load_exp_nav(lambda q: None, "X") is None


def test_the_loader_is_called_once_with_the_stripped_code():
    loader = fake.make_nav_loader()
    load_exp_nav(loader, "  FAKE-ZZC1  ")
    assert loader.calls == ["FAKE-ZZC1"]


# ───────────────────────── 既有契約與層次守衛 ─────────────────────────

def test_the_locked_lookup_contract_is_unchanged():
    assert [f.name for f in dataclasses.fields(FundLookupView)] == ["state", "input_code", "reason_code", "fields"]
    assert [f.name for f in dataclasses.fields(ProfileFields)] == ["fund_name", "dividend_policy", "inception_on", "mgmt_fee_rate_pct"]
    assert [f.name for f in dataclasses.fields(FieldView)] == ["status", "value"]


@pytest.mark.parametrize("rel", ["ui_v3/viewmodels/exp_nav.py", "ui_v3/adapters/exp_nav.py", "ui_v3/pages/exp_lookup.py"])
def test_sibling_layers_import_no_formula_service_repository_infra_fixture_or_network_module(rel):
    tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names.append(node.module or "")
    banned = ("services", "repositories", "infra", "shared.", "ui_v3.fixtures", "requests", "httpx", "urllib", "socket", "gspread", "os", "subprocess")
    assert [n for n in names if n == "os" or any(n == b or n.startswith(b + ".") or (b.endswith(".") and n.startswith(b)) for b in banned)] == []


# ───────────────────────── MF-A-1：擷取型時間保留原值（Work #7132438926） ─────────────────────────

@pytest.mark.parametrize("stamp", ["2026-11-23T00:58Z", "2026-11-23T00:58:07Z", "2026-11-23"])
def test_capture_times_accept_a_date_or_a_z_timestamp_and_keep_the_original_value(stamp):
    for field in ("supplier_fetched_at", "cache_updated_at", "ccy_declared_at"):
        assert getattr(_nav(**{field: stamp}), field) == stamp


@pytest.mark.parametrize("bad", ["2026-11-23T00:58", "2026-11-23T24:00Z", "2026-11-23T00:60Z", "2026-11-23T00:58+08:00", "2026-11-23 00:58Z", "yesterday"])
def test_capture_times_reject_malformed_timestamps(bad):
    for field in ("supplier_fetched_at", "cache_updated_at", "ccy_declared_at"):
        with pytest.raises(M.ExpNavContractError):
            _nav(**{field: bad})


def test_the_nav_observation_date_stays_a_plain_date():
    with pytest.raises(M.ExpNavContractError):
        _nav(nav_date="2026-11-20T09:30Z")


def test_the_adapter_keeps_a_verified_supplier_timestamp_verbatim_and_cache_only_stays_null():
    good = fake.make_nav_loader()("FAKE-ZZC3A")
    injected = {**good, "nav": {**good["nav"], "supplier_fetched_at": "2026-11-23T00:58Z"}}
    assert adapt_exp_nav(injected).nav.supplier_fetched_at == "2026-11-23T00:58Z"      # T-P1 的原值
    cache_only = fake.make_nav_loader()("FAKE-ZZC2")
    assert adapt_exp_nav(cache_only).nav.supplier_fetched_at is None                    # T-N1：預存檔＝未知，不以快取時間代填
