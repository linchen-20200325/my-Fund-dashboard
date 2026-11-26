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


# ───────── MF-C1／MF-C2（Work #7161452041）：fail-closed 反例與 test_mode 嚴格布林 ─────────
def _g(**kw):
    base = dict(state="ALLOWED", basis_ref="D", scope=("R2", "R3", "R4"), synthetic=False)
    base.update(kw)
    return ei.RightGrant(**base)


def _real_rights():
    return {a: _g() for a in ei.RIGHT_AXES}


BAD_SCOPES = [None, "R2R3R4", "R4", 5, 1.5, {"R4": 1}, object()]


@pytest.mark.parametrize("scope", BAD_SCOPES)
def test_c1_malformed_scope_folds_to_unknown_without_raising(scope):
    assert ei.effective_right(_g(scope=scope), "R4") is ei.RightState.UNKNOWN
    b = ei.admit([card(rights={**_real_rights(), "R4": _g(scope=scope)})])
    assert b.approved == () and b.refused[0].reason_codes == (ei.REASON_RJ3,)


def test_c1_scope_list_and_set_forms_still_valid_positive_control():
    for scope in (("R4",), ["R4"], frozenset({"R4"}), {"R4"}):
        assert ei.effective_right(_g(scope=scope), "R4") is ei.RightState.ALLOWED


@pytest.mark.parametrize("field,value", [("support_refs", None), ("contradicting_evidence_refs", None),
                                         ("rejected_metrics", None), ("data_gaps", None),
                                         ("support_refs", ({"metric": ["wrong-shape"]},)),
                                         ("support_refs", ({"metric": {"a": 1}},)),
                                         ("contradicting_evidence_refs", ("raw",)),
                                         ("rejected_metrics", ({"metric": ["x"]},)),
                                         ("support_refs", 5)])
def test_c1_malformed_evidence_with_allowed_rights_is_refused_not_raised(field, value):
    b = ei.admit([card(**{field: value})], test_mode=True)
    assert b.approved == () and len(b.refused) == 1
    assert b.refused[0].reason_codes == (ei.REASON_INCONSISTENT,)
    assert "wrong-shape" not in repr(b)


def test_c1_deny_with_none_support_refs_returns_rj3_only_and_no_leak():
    c = card(rights=grants(R4=BAD_GRANTS["deny"]), support_refs=None, contradicting_evidence_refs=None)
    b = ei.admit([c], test_mode=True)
    assert b.approved == () and b.refused[0].reason_codes == (ei.REASON_RJ3,)    # 只回固定 RJ3，不夾 input_inconsistent
    assert b.refused[0].data_gaps == ("rights_unverified",)


def test_c1_rights_failure_with_malformed_refs_is_rj3_only():
    c = card(rights=grants(R3=BAD_GRANTS["unknown"]), support_refs=({"metric": ["wrong-shape"]},))
    b = ei.admit([c], test_mode=True)
    assert b.refused[0].reason_codes == (ei.REASON_RJ3,) and "wrong-shape" not in repr(b)


def test_c1_mixed_valid_and_invalid_cards_do_not_block_each_other():
    good1 = card("G1")
    bad = [card("B1", rights={**_real_rights(), "R4": _g(scope=None)}),
           card("B2", rights=grants(R4=BAD_GRANTS["deny"]), support_refs=None),
           card("B3", support_refs=({"metric": ["wrong-shape"]},)),
           card("B4", data_gaps=None)]
    good2 = card("G2", lens=(ei.LENS_TREND,))
    b = ei.admit([good1, *bad, good2], test_mode=True)
    assert [a.card_id for a in b.approved] == ["G1", "G2"]
    assert [r.card_id for r in b.refused] == ["B1", "B2", "B3", "B4"]
    assert b.by_lens(ei.LENS_TREND)[0].card_id == "G2"
    assert set(b.refused[0].reason_codes + b.refused[1].reason_codes) == {ei.REASON_RJ3}
    assert b.refused[2].reason_codes == b.refused[3].reason_codes == (ei.REASON_INCONSISTENT,)


@pytest.mark.parametrize("flag", ["false", "true", "False", "True", "", "0", "1", 0, 1, 2, 1.0, None, [], [1], object()])
def test_c2_test_mode_only_explicit_bool_true_enables_synthetic(flag):
    assert ei.effective_right(_g(synthetic=True), "R4", test_mode=flag) is ei.RightState.UNKNOWN
    assert ei.admit([card()], test_mode=flag).approved == ()


def test_c2_explicit_bool_true_positive_and_false_negative_controls():
    assert ei.effective_right(_g(synthetic=True), "R4", test_mode=True) is ei.RightState.ALLOWED
    assert len(ei.admit([card()], test_mode=True).approved) == 1
    assert ei.effective_right(_g(synthetic=True), "R4", test_mode=False) is ei.RightState.UNKNOWN


def test_c2_non_synthetic_real_grant_is_unaffected_by_test_mode_value():
    assert len(ei.admit([card(rights=_real_rights())], test_mode="false").approved) == 1


class _ExplodingMapping(dict):
    def keys(self):
        raise RuntimeError("boom-detail-should-not-leak")


def test_c1_unexpected_exception_while_inspecting_evidence_fails_closed_without_leak():
    good = card("OK")
    bad = card("BOOM", support_refs=(_ExplodingMapping(metric="m"),))
    b = ei.admit([bad, good], test_mode=True)
    assert [a.card_id for a in b.approved] == ["OK"]
    assert b.refused[0].reason_codes == (ei.REASON_INCONSISTENT,) and "boom-detail" not in repr(b)


# ───────── MF-C1 殘餘（Work #7163046730）：scope 完整校驗／容器例外／快照失敗／權利不合不讀證據 ─────────
class _RaisingContainsList(list):
    def __contains__(self, item):
        raise RuntimeError("contains-detail-should-not-leak")


class _RaisingIterList(list):
    def __iter__(self):
        raise RuntimeError("iter-detail-should-not-leak")


class _LyingContainsList(list):
    def __contains__(self, item):
        return True


class _BadStr(str):
    def strip(self, *a, **k):
        raise RuntimeError("strip-detail-should-not-leak")


class _RaisingGetMapping(dict):
    def get(self, key, default=None):
        raise RuntimeError("get-detail-should-not-leak")


class _ExplodingItemsDict(dict):
    def items(self):
        raise RuntimeError("items-detail-should-not-leak")


class _BadStrObj:
    def __str__(self):
        raise RuntimeError("str-detail-should-not-leak")


class _ReadTracker(dict):
    """任何讀取（鍵／值／迭代／取值）都累計；用來證明權利不合時不讀證據。"""
    reads = 0

    def _hit(self):
        type(self).reads += 1

    def keys(self):
        self._hit()
        return super().keys()

    def items(self):
        self._hit()
        return super().items()

    def get(self, *a, **k):
        self._hit()
        return super().get(*a, **k)

    def __getitem__(self, k):
        self._hit()
        return super().__getitem__(k)

    def __iter__(self):
        self._hit()
        return super().__iter__()


@pytest.mark.parametrize("scope", [["R4", None], ("R4", None), ("R4", 5), ["R4", ["R4"]], {"R4", None},
                                   _RaisingContainsList(["R4"]), _RaisingIterList(["R4"]),
                                   _LyingContainsList(["R2"]), _LyingContainsList([None])])
def test_c1b_scope_fully_validated_all_elements_str_and_exceptions_fold_to_unknown(scope):
    assert ei.effective_right(_g(scope=scope), "R4") is ei.RightState.UNKNOWN
    b = ei.admit([card("A"), card("B", rights={**_real_rights(), "R4": _g(scope=scope)}), card("C")], test_mode=True)
    assert [a.card_id for a in b.approved] == ["A", "C"]
    assert b.refused[0].card_id == "B" and b.refused[0].reason_codes == (ei.REASON_RJ3,)
    assert "detail-should-not-leak" not in repr(b)


def test_c1b_clean_scope_positive_controls_still_allowed():
    for scope in (("R2", "R3", "R4"), ["R4"], {"R4", "R2"}, frozenset({"R4"})):
        assert ei.effective_right(_g(scope=scope), "R4") is ei.RightState.ALLOWED
    assert ei.effective_right(_g(scope=["R4", "R2"]), "R3") is ei.RightState.UNKNOWN      # 範圍不涵蓋該軸


def test_c1b_grant_with_exploding_state_or_rights_get_folds_to_rj3_and_batch_continues():
    bad_state = card("S", rights={**_real_rights(), "R2": _g(state=_BadStr("ALLOWED"))})
    bad_get = card("G", rights=_RaisingGetMapping(_real_rights()))
    b = ei.admit([card("A"), bad_state, bad_get, card("Z")], test_mode=True)
    assert [a.card_id for a in b.approved] == ["A", "Z"]
    assert [r.reason_codes for r in b.refused] == [(ei.REASON_RJ3,), (ei.REASON_RJ3,)]
    assert "detail-should-not-leak" not in repr(b)


@pytest.mark.parametrize("make", [
    lambda: card("X", support_refs=({"metric": "m", "nested": _ExplodingItemsDict(a=1)},)),
    lambda: card("X", contradicting_evidence_refs=({"type": "source", "nested": _ExplodingItemsDict(a=1)},)),
    lambda: card("X", credibility_boundary=_ExplodingItemsDict(n=1)),
    lambda: card("X", rejected_metrics=({"metric": "m2", "reason_codes": [_ExplodingItemsDict(a=1)]},)),
    lambda: card("X", data_gaps=(_BadStrObj(),)),
])
def test_c1b_snapshot_failure_after_rights_pass_is_per_card_input_inconsistent(make):
    b = ei.admit([card("A"), make(), card("Z", lens=(ei.LENS_TREND,))], test_mode=True)
    assert [a.card_id for a in b.approved] == ["A", "Z"]                 # 畸形卡前後的合法卡仍獲准
    assert [r.card_id for r in b.refused] == ["X"]
    r = b.refused[0]
    assert r.reason_codes == (ei.REASON_INCONSISTENT,) and r.data_gaps == ("input_inconsistent",)
    assert "detail-should-not-leak" not in repr(b)
    assert b.by_lens(ei.LENS_TREND)[0].card_id == "Z"


@pytest.mark.parametrize("bad_right", ["unknown", "deny"])
def test_c1b_rights_denied_or_unknown_never_reads_evidence_content(bad_right):
    _ReadTracker.reads = 0
    tr = _ReadTracker(metric="m")
    c = card("T", rights=grants(R4=BAD_GRANTS[bad_right]), support_refs=(tr,),
             contradicting_evidence_refs=(_ReadTracker(a=1),), credibility_boundary=_ReadTracker(n=1))
    b = ei.admit([c], test_mode=True)
    assert b.refused[0].reason_codes == (ei.REASON_RJ3,)                # 既有 RJ3-only 順序
    assert _ReadTracker.reads == 0                                       # 完全沒讀證據內容


def test_c1b_all_cards_malformed_returns_empty_bundle_not_exception():
    cards = [card("B1", rights={**_real_rights(), "R4": _g(scope=None)}),
             card("B2", support_refs=({"metric": "m", "n": _ExplodingItemsDict(a=1)},))]
    b = ei.admit(cards, test_mode=True)
    assert b.approved == () and len(b.refused) == 2 and b.status == "insufficient"


class _BenignList(list):
    pass


def test_c1b_even_benign_scope_subclass_is_fail_closed_unknown():
    assert ei.effective_right(_g(scope=_BenignList(["R4"])), "R4") is ei.RightState.UNKNOWN


class _BadBasis(str):
    def strip(self, *a, **k):
        raise RuntimeError("basis-detail-should-not-leak")


def test_c1b_effective_right_itself_never_raises_on_exploding_string_fields():
    assert ei.effective_right(_g(state=_BadStr("ALLOWED")), "R2") is ei.RightState.UNKNOWN
    assert ei.effective_right(_g(basis_ref=_BadBasis("D")), "R2") is ei.RightState.UNKNOWN


class _FalseAxis(str):
    def __eq__(self, other):
        return True

    __hash__ = str.__hash__


class _PlainStrSub(str):
    pass


@pytest.mark.parametrize("elem", [_FalseAxis("unrelated"), _FalseAxis("R4"), _PlainStrSub("R4")])
def test_c1c_scope_elements_must_be_exact_builtin_str(elem):
    assert ei.effective_right(_g(scope=(elem,)), "R4") is ei.RightState.UNKNOWN
    assert ei.effective_right(_g(scope=[elem, "R4"]), "R4") is ei.RightState.UNKNOWN
    b = ei.admit([card("A"), card("B", rights={**_real_rights(), "R4": _g(scope=(elem,))}), card("C")], test_mode=True)
    assert [a.card_id for a in b.approved] == ["A", "C"]
    assert b.refused[0].card_id == "B" and b.refused[0].reason_codes == (ei.REASON_RJ3,)


def test_c1c_exact_str_scope_positive_and_rj3_only_controls_preserved():
    assert ei.effective_right(_g(scope=("R2", "R3", "R4")), "R4") is ei.RightState.ALLOWED
    assert ei.effective_right(_g(scope=("unrelated",)), "R4") is ei.RightState.UNKNOWN
    b = ei.admit([card("D", rights=grants(R4=BAD_GRANTS["deny"]), support_refs=None)], test_mode=True)
    assert b.refused[0].reason_codes == (ei.REASON_RJ3,)


# ═════════════ 三主題短解釋（brief_for_lens／briefs_for_all_lenses） ═════════════
import re

_FORBIDDEN_CONCLUSION = re.compile(r"無異常|低風險|高風險|安全|正常|買進|賣出|加碼|減碼|持有|建議你|保證|預測")


def _shared_bundle():
    risk_cash = card("RC", lens=(ei.LENS_RISK, ei.LENS_CASHFLOW),
                     contradicting_evidence_refs=({"type": "source", "idx": 1},), contradiction_search="found",
                     data_gaps=("window_too_short",))
    trend = card("T", lens=(ei.LENS_TREND,), contradicting_evidence_refs=(), contradiction_search="not_found_in_window",
                 data_gaps=("no_fund_mapping",), credibility_boundary={"n_sources": 2, "window_hours": 48, "not_forecast": False})
    refused = card("REF", lens=(ei.LENS_RISK,), rights=grants(R4=BAD_GRANTS["deny"]))
    return ei.admit([risk_cash, trend, refused], test_mode=True)


def test_brief_has_conclusion_evidence_counter_gaps_boundary_for_each_lens_from_same_bundle():
    b = _shared_bundle()
    briefs = ei.briefs_for_all_lenses(b)
    assert set(briefs) == set(ei.LENSES)
    r, c, t = briefs[ei.LENS_RISK], briefs[ei.LENS_CASHFLOW], briefs[ei.LENS_TREND]
    assert r.conclusion == c.conclusion == t.conclusion == ei.CONCLUSION_PARTIAL
    assert r.evidence == c.evidence and r.counter_evidence == c.counter_evidence       # 風險／現金流共用同一張卡的證據
    assert r.counter_evidence == ({"type": "source", "idx": 1},) and t.counter_evidence == ()
    assert r.evidence[0] is b.approved[0].support_refs[0]                              # 同一物件，未複製或改寫
    assert r.contradiction_summary == (ei.CONTRADICTION_TEXT["found"],)
    assert t.contradiction_summary == (ei.CONTRADICTION_TEXT["not_found_in_window"],)
    assert "RC:window_too_short" in r.data_gaps and "T:no_fund_mapping" in t.data_gaps
    assert r.credibility_boundary["not_forecast"] is True and t.credibility_boundary["not_forecast"] is True  # 恆 True，輸入 False 也不可覆寫
    assert t.credibility_boundary["window_hours"] == 48
    assert r.ai_status == "disabled" and r.ai_text == ""


def test_brief_without_any_approved_support_is_insufficient_never_ok():
    b = ei.admit([card("X", rights=grants(R3=BAD_GRANTS["unknown"]))], test_mode=True)
    for lens in ei.LENSES:
        br = ei.brief_for_lens(b, lens)
        assert br.conclusion == ei.CONCLUSION_INSUFFICIENT and br.evidence == () and br.counter_evidence == ()
    only_gap = ei.admit([card("G", support_refs=(), card_status="insufficient", data_gaps=("g1",))], test_mode=True)
    br = ei.brief_for_lens(only_gap, ei.LENS_RISK)
    assert br.conclusion == ei.CONCLUSION_INSUFFICIENT and "G:g1" in br.data_gaps          # 缺口仍可見


def test_conclusions_never_contain_assurance_rating_or_action_words():
    for text in (ei.CONCLUSION_INSUFFICIENT, ei.CONCLUSION_PARTIAL, *ei.CONTRADICTION_TEXT.values()):
        assert not _FORBIDDEN_CONCLUSION.search(text.replace("不構成投資判斷或行動建議", "")), text


def test_ai_text_is_separate_and_cannot_change_conclusion_or_evidence():
    b = _shared_bundle()
    before = repr(b)
    br = ei.brief_for_lens(b, ei.LENS_RISK, SpyProvider(text="觀察到市場波動，資料日期見證據"), enabled=True)
    assert br.ai_status == "ok" and br.ai_text.startswith("觀察到") and br.ai_is_fake is True
    assert br.conclusion == ei.CONCLUSION_PARTIAL and repr(b) == before


@pytest.mark.parametrize("bad", ["建議買進", "目前低風險", "一切正常", "預測將上漲", "可以安心持有", "無異常"])
def test_ai_text_with_advice_or_assurance_is_dropped(bad):
    br = ei.brief_for_lens(_shared_bundle(), ei.LENS_RISK, SpyProvider(text=bad), enabled=True)
    assert br.ai_status == "text_rejected" and br.ai_text == "" and br.conclusion == ei.CONCLUSION_PARTIAL


@pytest.mark.parametrize("scenario", [FakeScenario.TIMEOUT, FakeScenario.RATE_LIMIT, FakeScenario.UNAVAILABLE, FakeScenario.DEGRADED])
def test_ai_failure_never_blocks_the_brief(scenario):
    brs = ei.briefs_for_all_lenses(_shared_bundle(), FakeProvider(scenario), enabled=True)
    for lens, br in brs.items():
        assert br.ai_text == "" and br.ai_status in ("failed", "no_evidence")
        assert br.conclusion in (ei.CONCLUSION_PARTIAL, ei.CONCLUSION_INSUFFICIENT)


@pytest.mark.parametrize("behaviour", ["raise", "timeout_exc", "bad_type"])
def test_provider_exceptions_do_not_block_briefs(behaviour):
    brs = ei.briefs_for_all_lenses(_shared_bundle(), SpyProvider(behaviour), enabled=True)
    assert all(b.ai_text == "" for b in brs.values()) and brs[ei.LENS_RISK].evidence


def test_provider_called_at_most_once_per_lens_and_only_with_evidence():
    spy = SpyProvider()
    ei.briefs_for_all_lenses(_shared_bundle(), spy, enabled=True)
    assert spy.calls == 3
    spy2 = SpyProvider()
    ei.briefs_for_all_lenses(ei.admit([], test_mode=True), spy2, enabled=True)
    assert spy2.calls == 0


def test_brief_rejects_unknown_lens_and_settings_page_has_no_brief():
    with pytest.raises(ValueError):
        ei.brief_for_lens(_shared_bundle(), "settings")


# ═════════════ MF-C-BRIEF-1：短解釋保留各主題的固定 reasons-only 拒收缺口 ═════════════
def _mixed_bundle():
    good = card("GOOD", lens=(ei.LENS_RISK, ei.LENS_CASHFLOW, ei.LENS_TREND), data_gaps=("time_sources_differ_note",))
    bad_rights = card("BAD", lens=(ei.LENS_RISK, ei.LENS_CASHFLOW), rights=grants(R4=BAD_GRANTS["deny"]),
                      support_refs=({"metric": "secret-metric-name", "status": "computed"},))
    bad_shape = card("SHAPE", lens=(ei.LENS_TREND,), support_refs=({"metric": ["wrong-shape"]},))
    return ei.admit([good, bad_rights, bad_shape], test_mode=True)


def test_brief_keeps_fixed_refusal_gaps_per_lens_in_mixed_batch():
    b = _mixed_bundle()
    risk, cash, trend = (ei.brief_for_lens(b, x) for x in (ei.LENS_RISK, ei.LENS_CASHFLOW, ei.LENS_TREND))
    assert "GOOD:time_sources_differ_note" in risk.data_gaps and "BAD:rights_unverified" in risk.data_gaps
    assert "BAD:rights_unverified" in cash.data_gaps and "SHAPE:input_inconsistent" not in cash.data_gaps
    assert "SHAPE:input_inconsistent" in trend.data_gaps and "BAD:rights_unverified" not in trend.data_gaps   # 只保留該主題有權取得者
    for br in (risk, cash, trend):
        assert br.conclusion == ei.CONCLUSION_PARTIAL and len(br.evidence) == 2               # 只有 GOOD 的支持證據，拒收者不添 support
        assert "secret-metric-name" not in repr(br) and "wrong-shape" not in repr(br)        # 不洩露拒收內容


def test_brief_keeps_refusal_gaps_when_every_card_is_refused():
    b = ei.admit([card("B1", lens=(ei.LENS_RISK,), rights=grants(R3=BAD_GRANTS["unknown"])),
                  card("B2", lens=(ei.LENS_TREND,), support_refs=None)], test_mode=True)
    assert b.approved == ()
    risk, cash, trend = (ei.brief_for_lens(b, x) for x in (ei.LENS_RISK, ei.LENS_CASHFLOW, ei.LENS_TREND))
    assert risk.data_gaps == ("B1:rights_unverified",) and trend.data_gaps == ("B2:input_inconsistent",)
    assert cash.data_gaps == ()
    for br in (risk, cash, trend):
        assert br.conclusion == ei.CONCLUSION_INSUFFICIENT and br.evidence == () and br.counter_evidence == ()


def test_refusal_gaps_in_brief_never_call_provider_or_add_support():
    spy = SpyProvider()
    b = ei.admit([card("B1", lens=(ei.LENS_RISK,), rights=grants(R4=BAD_GRANTS["deny"]))], test_mode=True)
    br = ei.brief_for_lens(b, ei.LENS_RISK, spy, enabled=True)
    assert spy.calls == 0 and br.ai_status == "no_evidence" and br.data_gaps == ("B1:rights_unverified",)


def test_refused_evidence_carries_lens_routing_without_reading_evidence():
    _ReadTracker.reads = 0
    c = card("T", lens=(ei.LENS_CASHFLOW,), rights=grants(R4=BAD_GRANTS["deny"]), support_refs=(_ReadTracker(metric="m"),))
    b = ei.admit([c], test_mode=True)
    assert b.refused[0].lens == (ei.LENS_CASHFLOW,) and _ReadTracker.reads == 0


def test_snapshot_failure_refusal_also_routes_fixed_gap_to_its_lens_only():
    bad = card("SNAP", lens=(ei.LENS_CASHFLOW,), support_refs=({"metric": "m", "nested": _ExplodingItemsDict(a=1)},))
    b = ei.admit([card("OK", lens=(ei.LENS_RISK,)), bad], test_mode=True)
    assert b.refused[0].lens == (ei.LENS_CASHFLOW,)
    assert ei.brief_for_lens(b, ei.LENS_CASHFLOW).data_gaps == ("SNAP:input_inconsistent",)
    assert "SNAP:input_inconsistent" not in ei.brief_for_lens(b, ei.LENS_RISK).data_gaps


# ═════════════ MF-C-BRIEF-1（Work 7174337858 殘餘反例）：路由主題在驗證時固定為不可變值 ═════════════
class _IterOnceThenRaise(list):
    """建構時可迭代；之後任何迭代都拋錯（模擬驗證後才壞掉的 list 子類）。"""

    armed = False

    def __iter__(self):
        if _IterOnceThenRaise.armed:
            raise RuntimeError("iteration after construction")
        return super().__iter__()


def test_rights_refusal_lens_is_frozen_at_validation_even_if_original_list_is_mutated():
    lens_list = [ei.LENS_RISK]
    c = card("MUT", lens=lens_list, rights=grants(R4=BAD_GRANTS["deny"]))
    lens_list[:] = [ei.LENS_TREND]                                  # 建構後改動原 list
    b = ei.admit([c], test_mode=True)
    assert b.refused[0].lens == (ei.LENS_RISK,)
    assert ei.brief_for_lens(b, ei.LENS_TREND).data_gaps == ()      # 不跨主題漏到趨勢
    assert ei.brief_for_lens(b, ei.LENS_RISK).data_gaps == ("MUT:rights_unverified",)


def test_snapshot_failure_refusal_lens_is_frozen_too():
    lens_list = [ei.LENS_CASHFLOW]
    c = card("MUT2", lens=lens_list, support_refs=({"metric": "m", "nested": _ExplodingItemsDict(a=1)},))
    lens_list[:] = [ei.LENS_TREND]
    b = ei.admit([c], test_mode=True)
    assert b.refused[0].lens == (ei.LENS_CASHFLOW,)
    assert ei.brief_for_lens(b, ei.LENS_TREND).data_gaps == ()


@pytest.mark.parametrize("bad_card", ["rights", "snapshot", "approved"])
def test_lens_iterable_that_raises_after_construction_does_not_break_batch(bad_card):
    _IterOnceThenRaise.armed = False
    lens_list = _IterOnceThenRaise([ei.LENS_RISK])
    kw = {"rights": grants(R4=BAD_GRANTS["deny"])} if bad_card == "rights" else {}
    if bad_card == "snapshot":
        kw["support_refs"] = ({"metric": "m", "nested": _ExplodingItemsDict(a=1)},)
    c = card("BOOM", lens=lens_list, **kw)
    _IterOnceThenRaise.armed = True
    try:
        b = ei.admit([c, card("AFTER", lens=(ei.LENS_TREND,))], test_mode=True)   # 不丟 RuntimeError
    finally:
        _IterOnceThenRaise.armed = False
    assert {a.card_id for a in b.approved} >= {"AFTER"}                            # 後續合法卡繼續處理
    assert ei.brief_for_lens(b, ei.LENS_TREND).data_gaps == () or all(
        not g.startswith("BOOM") for g in ei.brief_for_lens(b, ei.LENS_TREND).data_gaps)


def test_card_rejects_non_str_or_unknown_lens_members_at_construction():
    class _StrSub(str):
        pass

    for bad in ([_StrSub(ei.LENS_RISK)], [None], [("x",)], []):
        with pytest.raises(ValueError):
            card("X", lens=bad)


# ═════════════ MF-C-BRIEF-1（Work 7178971235）：子類建構後讓 `lens` 讀取回傳「另一個合法 tuple」不得跨主題 ═════════════
def _spoofed(base_kwargs, spoof):
    """建立 AdmittedCard 子類：建構時一切正常，建構後 `__getattribute__("lens")` 回傳 spoof。"""
    state = {"armed": False}

    class _Spoof(ei.AdmittedCard):
        def __getattribute__(self, name):
            if name == "lens" and state["armed"]:
                return spoof
            return super().__getattribute__(name)

    c = _Spoof(**base_kwargs)
    state["armed"] = True
    return c


def _kwargs(card_id, lens, **kw):
    c = card(card_id, lens=lens, **kw)
    return {f: getattr(c, f) for f in ("card_id", "lens", "support_refs", "contradicting_evidence_refs",
                                      "contradiction_search", "rejected_metrics", "data_gaps",
                                      "credibility_boundary", "rights", "card_status")}


@pytest.mark.parametrize("spoof", [(ei.LENS_TREND,), [ei.LENS_TREND], ("not-a-lens",), None, ()])
@pytest.mark.parametrize("kind", ["rights", "snapshot", "approved"])
def test_subclass_cannot_reroute_refusal_gap_by_returning_other_lens_after_construction(kind, spoof):
    extra = {}
    if kind == "rights":
        extra["rights"] = grants(R4=BAD_GRANTS["deny"])
    elif kind == "snapshot":
        extra["support_refs"] = ({"metric": "m", "nested": _ExplodingItemsDict(a=1)},)
    c = _spoofed(_kwargs("SPOOF", (ei.LENS_RISK,), **extra), spoof)
    b = ei.admit([c, card("AFTER", lens=(ei.LENS_TREND,))], test_mode=True)
    assert {a.card_id for a in b.approved} >= {"AFTER"}                       # 後續合法卡照常處理
    trend = ei.brief_for_lens(b, ei.LENS_TREND)
    assert all(not g.startswith("SPOOF") for g in trend.data_gaps)            # 趨勢不出現被騙來的拒收缺口
    assert all(a.card_id != "SPOOF" or a.lens == (ei.LENS_RISK,) for a in b.approved)
    if kind != "approved":
        assert b.refused[0].lens == (ei.LENS_RISK,)                           # 路由用建構時固定值
        assert "SPOOF:" in " ".join(ei.brief_for_lens(b, ei.LENS_RISK).data_gaps)


@pytest.mark.parametrize("bad", [[ei.LENS_RISK], (), ("not-a-lens",), (ei.LENS_RISK, 3), None])
def test_card_whose_fixed_lens_was_tampered_after_construction_is_never_approved(bad):
    c = card("TAMPER", lens=(ei.LENS_RISK,))
    object.__setattr__(c, "lens", bad)                                          # 繞過 frozen 的惡意改動
    b = ei.admit([c, card("AFTER", lens=(ei.LENS_TREND,))], test_mode=True)
    assert [a.card_id for a in b.approved] == ["AFTER"]                          # 無合法固定主題者不獲准
    assert b.refused[0].card_id == "TAMPER" and b.refused[0].data_gaps == ("input_inconsistent",)
    assert b.refused[0].lens == ()
