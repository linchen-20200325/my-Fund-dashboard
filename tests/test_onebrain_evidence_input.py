"""C-OB-EVIDENCE-OFFLINE-1：離線證據輸入器測試（services/onebrain/evidence_input.py）。

授權：#1296 comment 7132782309。全部離線、合成；每個測試前以 autouse 守衛封鎖 socket（零外連）。
不 import 任何 services.health／ui_v3／真 Provider；只用 FakeProvider 與測試內自訂 Provider。
"""

from __future__ import annotations

import copy
import socket

import pytest

from services.onebrain import evidence_input as ei
from services.onebrain.fake_provider import FakeProvider, FakeScenario
from services.onebrain.provider_interface import AnalysisProvider
from services.onebrain.provider_types import ProviderOutcome, ProviderResponse


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    def deny(*a, **k):
        raise AssertionError("network attempted")

    monkeypatch.setattr(socket, "socket", deny)
    monkeypatch.setattr(socket, "create_connection", deny)
    monkeypatch.setattr(socket, "getaddrinfo", deny)


def grants(**over):
    base = {a: ei.RightGrant(state="ALLOWED", basis_ref="DEC-TEST-1", scope=("R2", "R3", "R4"), synthetic=True)
            for a in ei.RIGHT_AXES}
    base.update(over)
    return base


def card(card_id="C-1", lens=(ei.LENS_RISK, ei.LENS_CASHFLOW), rights=None, **kw):
    d = dict(
        card_id=card_id,
        lens=lens,
        support_refs=({"metric": "check_333_principle", "status": "computed", "result": "not_met"},
                      {"metric": "classify_eating_principal", "status": "no_dividend"}),
        contradicting_evidence_refs=({"type": "source", "idx": 1},),
        contradiction_search="found",
        rejected_metrics=({"metric": "x_metric", "reason_codes": ["RJ4:required_input_missing:a"]},),
        data_gaps=("time_sources_differ_note",),
        credibility_boundary={"n_sources": 2, "window_hours": 72, "not_forecast": True},
        rights=grants() if rights is None else rights,
        card_status="partial",
    )
    d.update(kw)
    return ei.AdmittedCard(**d)


# ───────── 權利軸：任一非 ALLOWED 即整筆拒收，且內容不外洩 ─────────
BAD_GRANTS = {
    "unknown": ei.RightGrant(state="UNKNOWN", basis_ref="D", scope=("R2", "R3", "R4")),
    "deny": ei.RightGrant(state="DENY", basis_ref="D", scope=("R2", "R3", "R4")),
    "deny_signal_legacy": ei.RightGrant(state="DENY-SIGNAL", basis_ref="D", scope=("R2", "R3", "R4")),
    "archived_is_not_a_right": ei.RightGrant(state="archived", basis_ref="D", scope=("R2", "R3", "R4")),
    "unverified_word": ei.RightGrant(state="UNVERIFIED", basis_ref="D", scope=("R2", "R3", "R4")),
    "allowed_no_basis": ei.RightGrant(state="ALLOWED", basis_ref="", scope=("R2", "R3", "R4")),
    "allowed_scope_missing_axis": ei.RightGrant(state="ALLOWED", basis_ref="D", scope=()),
    "allowed_expired": ei.RightGrant(state="ALLOWED", basis_ref="D", scope=("R2", "R3", "R4"), expired=True),
    "allowed_revoked": ei.RightGrant(state="ALLOWED", basis_ref="D", scope=("R2", "R3", "R4"), revoked=True),
    "allowed_inferred": ei.RightGrant(state="ALLOWED", basis_ref="D", scope=("R2", "R3", "R4"), inferred=True),
    "none": None,
    "plain_string": "ALLOWED",
}


@pytest.mark.parametrize("axis", ei.RIGHT_AXES)
@pytest.mark.parametrize("name", sorted(BAD_GRANTS))
def test_any_axis_not_allowed_refuses_whole_card_without_leaking(axis, name):
    c = card(rights=grants(**{axis: BAD_GRANTS[name]}))
    b = ei.admit([c], test_mode=True)
    assert b.approved == () and len(b.refused) == 1
    r = b.refused[0]
    assert ei.REASON_RJ3 in r.reason_codes and "rights_unverified" in r.data_gaps
    dump = repr(b)
    for secret in ("check_333_principle", "classify_eating_principal", "not_met", "no_dividend", "found"):
        assert secret not in dump, secret                       # 被拒者不夾帶任何證據內容
    assert dict(r.rights_detail)[axis] in ("UNKNOWN", "DENY")


def test_missing_rights_mapping_or_axis_is_refused():
    assert ei.admit([card(rights={})], test_mode=True).approved == ()
    only_two = {k: v for k, v in grants().items() if k != "R4"}
    b = ei.admit([card(rights=only_two)], test_mode=True)
    assert b.approved == () and dict(b.refused[0].rights_detail)["R4"] == "UNKNOWN"


def test_all_axes_allowed_is_approved_and_evidence_preserved_verbatim():
    c = card()
    b = ei.admit([c], test_mode=True)
    assert len(b.approved) == 1 and b.refused == ()
    a = b.approved[0]
    assert a.support_refs == c.support_refs and type(a.support_refs[0]["metric"]) is str
    assert list(a.contradicting_evidence_refs) == list(c.contradicting_evidence_refs)
    assert a.contradiction_search == "found"
    assert list(a.rejected_metrics) == list(c.rejected_metrics)      # 上游拒絕原因碼只作追溯保留
    assert a.data_gaps == ("time_sources_differ_note",)
    assert a.credibility_boundary == {"n_sources": 2, "window_hours": 72, "not_forecast": True}


def test_synthetic_allowed_only_valid_in_test_mode():
    c = card()
    assert ei.admit([c], test_mode=False).approved == ()            # 非測試模式：合成 ALLOWED＝UNKNOWN
    assert len(ei.admit([c], test_mode=True).approved) == 1
    real = {a: ei.RightGrant(state="ALLOWED", basis_ref="DEC-REAL", scope=ei.RIGHT_AXES) for a in ei.RIGHT_AXES}
    assert len(ei.admit([card(rights=real)], test_mode=False).approved) == 1   # 非合成且依據齊 → 可


def test_evidence_not_aliased_to_input():
    refs = [{"metric": "m1", "status": "computed"}]
    c = card(support_refs=tuple(refs))
    b = ei.admit([c], test_mode=True)
    refs[0]["status"] = "mutated"
    assert b.approved[0].support_refs[0]["status"] == "computed"


# ───────── 輸入自相矛盾 ─────────
def test_metric_both_supported_and_rejected_is_refused():
    c = card(support_refs=({"metric": "m", "status": "computed"},),
             rejected_metrics=({"metric": "m", "reason_codes": ["RJ1:input_conflict"]},))
    b = ei.admit([c], test_mode=True)
    assert b.approved == () and ei.REASON_INCONSISTENT in b.refused[0].reason_codes


@pytest.mark.parametrize("key", sorted(ei._FORBIDDEN_EVIDENCE_KEYS))
def test_forbidden_conclusion_keys_in_evidence_are_refused(key):
    c = card(support_refs=({"metric": "m", key: "x"},))
    assert ei.admit([c], test_mode=True).approved == ()


def test_non_mapping_evidence_item_is_refused():
    assert ei.admit([card(support_refs=("raw string",))], test_mode=True).approved == ()


def test_invalid_card_construction_raises():
    with pytest.raises(ValueError):
        card(lens=())
    with pytest.raises(ValueError):
        card(lens=("unknown_lens",))
    with pytest.raises(ValueError):
        card(contradiction_search="no_contradiction")
    with pytest.raises(ValueError):
        card(card_status="ok")
    with pytest.raises(TypeError):
        ei.admit(["not a card"])


# ───────── 三主題共用同一份證據；缺值／反證保留 ─────────
def test_three_lenses_share_the_same_approved_evidence():
    c = card(lens=(ei.LENS_RISK, ei.LENS_CASHFLOW, ei.LENS_TREND))
    b = ei.admit([c], test_mode=True)
    views = [b.by_lens(x) for x in ei.LENSES]
    assert all(len(v) == 1 for v in views)
    assert views[0][0] is views[1][0] is views[2][0]                # 同一物件，不複製、不改寫


def test_lens_view_only_contains_cards_tagged_with_that_lens():
    b = ei.admit([card("A", lens=(ei.LENS_RISK,)), card("B", lens=(ei.LENS_CASHFLOW,))], test_mode=True)
    assert [a.card_id for a in b.by_lens(ei.LENS_RISK)] == ["A"]
    assert [a.card_id for a in b.by_lens(ei.LENS_CASHFLOW)] == ["B"]
    assert b.by_lens(ei.LENS_TREND) == ()
    with pytest.raises(ValueError):
        b.by_lens("settings")


@pytest.mark.parametrize("state", ei.CONTRADICTION_STATES)
def test_contradiction_states_preserved_and_not_normalised(state):
    refs = ({"type": "source", "idx": 2},) if state == "found" else ()
    b = ei.admit([card(contradicting_evidence_refs=refs, contradiction_search=state)], test_mode=True)
    a = b.approved[0]
    assert a.contradiction_search == state and list(a.contradicting_evidence_refs) == list(refs)


def test_missing_data_is_never_reported_as_ok():
    # 全拒收／無支持證據 → status 只會是 insufficient；沒有 ok／normal 這類值
    assert ei.admit([], test_mode=True).status == "insufficient"
    assert ei.admit([card(rights=grants(R4=BAD_GRANTS["deny"]))], test_mode=True).status == "insufficient"
    no_support = card(support_refs=(), contradiction_search="not_searched", card_status="insufficient")
    b = ei.admit([no_support], test_mode=True)
    assert b.status == "insufficient" and len(b.approved) == 1      # 缺口仍可被看見
    assert ei.admit([card()], test_mode=True).status == "partial"
    assert {"ok", "normal", "safe"} & {s for s in ("partial", "insufficient")} == set()


def test_data_gaps_aggregate_with_card_scope_and_refused_gaps_visible():
    b = ei.admit([card("A", data_gaps=("g1",)), card("B", rights=grants(R3=BAD_GRANTS["unknown"]))], test_mode=True)
    assert "A:g1" in b.data_gaps and "B:rights_unverified" in b.data_gaps


# ───────── explain：AI 停用／失敗／逾時／例外 不阻塞 UI、不改證據 ─────────
class SpyProvider(AnalysisProvider):
    def __init__(self, behaviour="ok", text="解釋文字 7.0% 8.0"):
        self.calls, self.behaviour, self.text, self.last = 0, behaviour, text, None

    @property
    def name(self):
        return "SPY"

    def invoke(self, request):
        self.calls += 1
        self.last = request
        if self.behaviour == "raise":
            raise RuntimeError("secret-detail-should-not-leak")
        if self.behaviour == "timeout_exc":
            raise TimeoutError("slow")
        if self.behaviour == "bad_type":
            return "not an outcome"
        return ProviderOutcome(response=ProviderResponse(request_id=request.request_id, provider_name="SPY",
                                                          model=request.model, text=self.text, is_fake=True))


def _bundle():
    return ei.admit([card()], test_mode=True)


def test_disabled_or_missing_provider_never_calls_provider():
    b, spy = _bundle(), SpyProvider()
    r1 = ei.explain(b, ei.LENS_RISK, spy, enabled=False)
    r2 = ei.explain(b, ei.LENS_RISK, None, enabled=True)
    assert spy.calls == 0 and r1.status is ei.ExplainStatus.DISABLED and r2.status is ei.ExplainStatus.DISABLED
    assert r1.evidence == b.by_lens(ei.LENS_RISK) and r1.text == ""


def test_no_evidence_means_provider_not_called():
    spy = SpyProvider()
    b = ei.admit([card(rights=grants(R4=BAD_GRANTS["unknown"]))], test_mode=True)   # 全拒收
    r = ei.explain(b, ei.LENS_RISK, spy, enabled=True)
    assert spy.calls == 0 and r.status is ei.ExplainStatus.NO_EVIDENCE and r.evidence == ()
    b2 = ei.admit([card(support_refs=(), card_status="insufficient")], test_mode=True)  # 有缺口但無支持證據
    assert ei.explain(b2, ei.LENS_RISK, spy, enabled=True).status is ei.ExplainStatus.NO_EVIDENCE and spy.calls == 0


def test_provider_only_receives_approved_evidence_never_refused_content():
    good = card("GOOD", support_refs=({"metric": "m_good", "status": "computed"},))
    bad = card("BAD", rights=grants(R4=BAD_GRANTS["deny"]), support_refs=({"metric": "m_bad", "status": "computed"},))
    spy = SpyProvider()
    ei.explain(ei.admit([good, bad], test_mode=True), ei.LENS_RISK, spy, enabled=True)
    assert "m_good" in spy.last.input_text and "m_bad" not in spy.last.input_text and "BAD" not in spy.last.input_text


@pytest.mark.parametrize("scenario,kind", [(FakeScenario.TIMEOUT, "timeout"), (FakeScenario.RATE_LIMIT, "rate_limit"),
                                           (FakeScenario.UNAVAILABLE, "provider_unavailable"),
                                           (FakeScenario.DEGRADED, "degraded")])
def test_provider_failures_return_structured_result_and_keep_evidence(scenario, kind):
    b = _bundle()
    before = repr(b)
    r = ei.explain(b, ei.LENS_CASHFLOW, FakeProvider(scenario), enabled=True)
    assert r.status is ei.ExplainStatus.FAILED and r.failure_kind == kind and r.text == ""
    assert r.evidence == b.by_lens(ei.LENS_CASHFLOW) and repr(b) == before


@pytest.mark.parametrize("behaviour,status,kind", [("raise", ei.ExplainStatus.ERROR, ""),
                                                   ("timeout_exc", ei.ExplainStatus.FAILED, "timeout"),
                                                   ("bad_type", ei.ExplainStatus.ERROR, "")])
def test_provider_exceptions_never_propagate_or_leak(behaviour, status, kind):
    b = _bundle()
    r = ei.explain(b, ei.LENS_RISK, SpyProvider(behaviour), enabled=True)
    assert r.status is status and r.failure_kind == kind and r.text == ""
    assert "secret-detail" not in repr(r) and r.evidence == b.by_lens(ei.LENS_RISK)


def test_explanation_text_never_rewrites_rule_values():
    b = _bundle()
    snap = copy.deepcopy(repr(b.by_lens(ei.LENS_RISK)))
    r = ei.explain(b, ei.LENS_RISK, SpyProvider(text="改成 99.9% 通過"), enabled=True)
    assert r.status is ei.ExplainStatus.OK and r.text == "改成 99.9% 通過"
    assert repr(r.evidence) == snap and "99.9" not in repr(r.evidence)       # 文字與證據分離，數值不被覆寫
    assert r.is_fake is True


def test_fake_provider_success_marks_fake():
    r = ei.explain(_bundle(), ei.LENS_TREND if False else ei.LENS_RISK, FakeProvider(FakeScenario.MARKER), enabled=True)
    assert r.status is ei.ExplainStatus.OK and r.is_fake is True and "FAKE" in r.text


def test_explain_rejects_non_bundle_and_unknown_lens():
    with pytest.raises(TypeError):
        ei.explain("x", ei.LENS_RISK)
    with pytest.raises(ValueError):
        ei.explain(_bundle(), "settings")                          # ⚙️ 設定不設 AI


# ───────── 隔離：模組不依賴公式、不重算 ─────────
def test_module_does_not_import_formulas_or_ui():
    import ast
    import pathlib

    src = pathlib.Path(ei.__file__).read_text(encoding="utf-8")
    mods = {n.module for n in ast.walk(ast.parse(src)) if isinstance(n, ast.ImportFrom)}
    assert not any(m and (m.startswith("services.health") or m.startswith("ui_v3") or m.startswith("ui"))
                   for m in mods)
    assert "check_333_principle(" not in src and "classify_eating_principal(" not in src
