# -*- coding: utf-8 -*-
"""NAS 中繼站診斷 view model 守衛（純 Python；不連網、不讀憑證）。

驗：六態真值表全覆蓋、NAS 失敗但直連成功 ≠ 成功、矛盾輸入 → 無法判定、缺值（None）≠ 成功、兩軸分開判定、
標籤與憑證形字串被拒（訊息不洩值）、輸入沒有原始例外字串欄位、與 `shared/backoff_policy.py` 失敗分類名同步（漂移會紅）、
暫行字樣不冒充已核准字樣、模組只 import 標準函式庫與允許的層。負控一律在記憶體內現編。
"""
from __future__ import annotations

import ast
import dataclasses
import pathlib
import re

import pytest

import nas_diag_support as sup
import ui_v3_guard_lib as lib
from shared import backoff_policy as bp
from shared.ui_semantics import rules
from ui_v3.viewmodels import nas_diag as vm
from ui_v3.viewmodels import nas_diag_wording as W

OBS = vm.NasDiagObservation
ALL_SCENARIOS = list(sup.SCENARIO_KWARGS)


def _classify(**kw) -> vm.NasDiagView:
    return vm.classify(OBS(**kw))


# ───────────────────────── 真值表 ─────────────────────────

@pytest.mark.parametrize("sid", ALL_SCENARIOS)
def test_scenario_truth_table(sid):
    view = _classify(**sup.kwargs(sid))
    assert (view.state, view.nas_health, view.target_health, view.reason_key) == sup.EXPECTED[sid]


def test_all_six_states_are_reachable_and_the_set_is_exactly_six():
    seen = {_classify(**sup.kwargs(s)).state for s in ALL_SCENARIOS}
    assert seen == set(vm.STATES) and len(vm.STATES) == 6


def test_nas_failed_but_direct_succeeded_is_degraded_not_success():
    for sid in ("degraded_direct", "blocked_403_then_direct"):
        view = _classify(**sup.kwargs(sid))
        assert view.state == vm.STATE_DEGRADED and view.state != vm.STATE_OK
        assert view.nas_health == vm.HEALTH_FAILED and view.target_health == vm.HEALTH_OK
        assert view.route_code == vm.ROUTE_FALLBACK


def test_success_requires_the_nas_route_and_both_axes_ok():
    view = _classify(**sup.kwargs("nas_ok"))
    assert (view.state, view.route_code) == (vm.STATE_OK, vm.ROUTE_NAS)
    # 結構不變量：連線成功不可能配 NAS 失敗；已降級直連不可能配 NAS 正常
    base = dataclasses.asdict(view)
    with pytest.raises(ValueError):
        vm.NasDiagView(**{**base, "nas_health": vm.HEALTH_FAILED})
    with pytest.raises(ValueError):
        vm.NasDiagView(**{**base, "route_code": vm.ROUTE_FALLBACK})
    degraded = dataclasses.asdict(_classify(**sup.kwargs("degraded_direct")))
    with pytest.raises(ValueError):
        vm.NasDiagView(**{**degraded, "nas_health": vm.HEALTH_OK})


def test_two_axes_are_judged_independently():
    nas_ok_target_bad = _classify(**sup.kwargs("blocked_403"))
    assert (nas_ok_target_bad.nas_health, nas_ok_target_bad.target_health) == ("ok", "failed")
    nas_bad_target_ok = _classify(**sup.kwargs("degraded_direct"))
    assert (nas_bad_target_ok.nas_health, nas_bad_target_ok.target_health) == ("failed", "ok")
    nas_bad_target_untried = _classify(**sup.kwargs("auth_407"))   # 407：從沒碰到目標，目標軸不得被說成失敗或成功
    assert (nas_bad_target_untried.nas_health, nas_bad_target_untried.target_health) == ("failed", "not_tested")
    nas_cause = _classify(**sup.kwargs("blocked_403_then_direct"))
    assert nas_cause.nas_cause_key == "cause_blocked_403" and nas_cause.target_cause_key is None


def test_not_configured_is_a_state_of_its_own_and_may_carry_a_direct_result():
    assert _classify(proxy_configured=False).state == vm.STATE_NOT_CONFIGURED
    direct_ok = _classify(proxy_configured=False, route_used="direct", target_http_status=200, error_class="ok",
                          latency_ms=300, checked_at=sup.CHECKED_AT)
    assert (direct_ok.state, direct_ok.nas_health, direct_ok.target_health) == ("not_configured", "not_configured", "ok")
    direct_bad = _classify(proxy_configured=False, route_used="direct", target_http_status=403, error_class="forbidden_403",
                           checked_at=sup.CHECKED_AT)
    assert (direct_bad.state, direct_bad.target_health) == ("not_configured", "failed")


# ───────────────────────── 矛盾與缺值 ─────────────────────────

CONTRADICTIONS = {
    "route nas but nas unreachable": dict(nas_reachable=False, route_used="nas"),
    "route nas with a nas-fault class": dict(route_used="nas", target_http_status=None, error_class="proxy_unreachable"),
    "route nas with 407": dict(route_used="nas", target_http_status=407, error_class="proxy_auth_407"),
    "route nas carrying a nas error class": dict(nas_error_class="proxy_unreachable"),
    "ok class with non-2xx status": dict(target_http_status=500),
    "2xx status with a failure class": dict(error_class="other"),
    "403 status with a 429 class": dict(target_http_status=403, error_class="rate_limited_429"),
    "429 status with timeout class": dict(target_http_status=429, error_class="timeout"),
    "timeout with a status code": dict(target_http_status=504, error_class="timeout"),
    "fallback with nas reachable and fault class": dict(route_used="fallback_direct", nas_reachable=True, nas_error_class="proxy_unreachable"),
    "fallback without a nas error class": dict(nas_reachable=False, route_used="fallback_direct"),
    "fallback with nas error class ok": dict(nas_reachable=False, route_used="fallback_direct", nas_error_class="ok"),
    "fallback direct result is a nas fault": dict(nas_reachable=False, route_used="fallback_direct", nas_error_class="timeout",
                                                  target_http_status=None, error_class="proxy_unreachable"),
    "route none but nas reachable": dict(nas_reachable=True, route_used="none", nas_error_class="timeout", target_http_status=None,
                                         error_class="timeout"),
    "route none with ok result": dict(nas_reachable=False, route_used="none", nas_error_class="proxy_unreachable"),
    "direct route while nas flagged reachable": dict(route_used="direct"),
}


@pytest.mark.parametrize("name", list(CONTRADICTIONS))
def test_contradictory_inputs_become_undetermined_not_a_guess(name):
    base = sup.kwargs("nas_ok")
    base.update(CONTRADICTIONS[name])
    view = _classify(**base)
    assert view.state == vm.STATE_UNDETERMINED, name
    assert (view.nas_health, view.target_health) == (vm.HEALTH_UNDETERMINED, vm.HEALTH_UNDETERMINED)
    # 無法判定時不帶狀態碼、延遲、原因分類：不把矛盾的事實當證據
    assert (view.target_http_status, view.latency_ms, view.nas_cause_key, view.target_cause_key) == (None, None, None, None)


def test_unconfigured_but_claims_to_have_used_the_nas_is_a_contradiction():
    for extra in (dict(nas_reachable=True), dict(route_used="nas"), dict(route_used="fallback_direct"), dict(nas_error_class="timeout")):
        assert _classify(proxy_configured=False, **extra).state == vm.STATE_UNDETERMINED, extra


def test_missing_values_are_never_read_as_success_or_zero():
    cases = {
        "config unknown": dict(),
        "result without timestamp": dict(proxy_configured=True, nas_reachable=True, route_used="nas", target_http_status=200, error_class="ok"),
        "timestamp only": dict(proxy_configured=True, checked_at=sup.CHECKED_AT),
        "ok class but no status": dict(proxy_configured=True, nas_reachable=True, route_used="nas", error_class="ok", checked_at=sup.CHECKED_AT),
        "status but no class": dict(proxy_configured=True, nas_reachable=True, route_used="nas", target_http_status=200, checked_at=sup.CHECKED_AT),
        "nas reachability unknown": dict(proxy_configured=True, route_used="nas", target_http_status=200, error_class="ok", checked_at=sup.CHECKED_AT),
        "route unknown": dict(proxy_configured=True, nas_reachable=True, target_http_status=200, error_class="ok", checked_at=sup.CHECKED_AT),
        "direct route with a configured nas": dict(proxy_configured=True, route_used="direct", nas_reachable=None, target_http_status=200,
                                                   error_class="ok", checked_at=sup.CHECKED_AT),
    }
    for name, kw in cases.items():
        view = _classify(**kw)
        assert view.state == vm.STATE_UNDETERMINED, name
        assert view.state != vm.STATE_OK and vm.HEALTH_OK not in (view.nas_health, view.target_health), name
    # 只有「已設定、沒有任何結果事實」才是尚未測試
    assert _classify(proxy_configured=True).state == vm.STATE_NOT_TESTED
    assert _classify(proxy_configured=True, route_used="none").state == vm.STATE_NOT_TESTED
    assert _classify().reason_key == "config_unknown"


def test_latency_zero_is_a_value_and_none_is_missing():
    zero = _classify(**{**sup.kwargs("nas_ok"), "latency_ms": 0})
    none = _classify(**{**sup.kwargs("nas_ok"), "latency_ms": None})
    assert zero.latency_ms == 0 and none.latency_ms is None and zero.state == none.state == vm.STATE_OK


# ───────────────────────── 輸入驗證（標籤、憑證形、型別） ─────────────────────────

@pytest.mark.parametrize("label", ["MoneyDJ", "Yahoo Finance", "財金資料來源", "TDCC-境內", "FRED"])
def test_whitelisted_labels_are_accepted(label):
    assert OBS(target_label=label).target_label == label


@pytest.mark.parametrize("label", [
    sup.POISON_URL, "https://www.example.com/path", "www.moneydj.com/funddj?a=1", "user:pass@host", "a@b", "x?y=1", "a#b", "a=b", "a&b",
    "host:3128", "a/b", "", " " * 0, "x" * 41, "<b>x</b>", "a\nb", "a.b", "  http://u:p@h",
])
def test_labels_that_look_like_urls_credentials_or_markup_are_rejected_without_echoing_the_value(label):
    with pytest.raises((ValueError, TypeError)) as info:
        OBS(target_label=label)
    assert sup.SECRET not in str(info.value) and label not in str(info.value) or label == ""


@pytest.mark.parametrize("sid", ALL_SCENARIOS)
def test_every_scenario_rejects_a_poisoned_field_and_never_echoes_it(sid):
    for field, value in (("target_label", sup.POISON_URL), ("checked_at", "2026-11-16T10:30:00+08:00 " + sup.POISON_URL)):
        kw = sup.kwargs(sid)
        kw[field] = value
        with pytest.raises(ValueError) as info:
            OBS(**kw)
        assert sup.SECRET not in str(info.value) and "http" not in str(info.value)


def test_no_raw_error_text_field_exists_and_extra_fields_are_rejected():
    names = {f.name for f in dataclasses.fields(OBS)}
    assert not [n for n in names if re.search(r"raw|exception|message|traceback|text|detail|url|proxy_url|host|header", n)], names
    assert names == {"proxy_configured", "nas_reachable", "route_used", "target_label", "target_http_status", "error_class",
                     "latency_ms", "checked_at", "nas_error_class"}
    for extra in ("raw_error", "exception", "proxy_url", "headers"):
        with pytest.raises(TypeError):
            OBS(**{extra: "http://u:" + sup.SECRET + "@h:3128"})
    view_names = {f.name for f in dataclasses.fields(vm.NasDiagView)}
    assert not [n for n in view_names if re.search(r"raw|exception|message|url|host|header", n)], view_names


@pytest.mark.parametrize("kw", [
    dict(proxy_configured=1), dict(proxy_configured="yes"), dict(nas_reachable=0), dict(route_used="proxy"), dict(error_class="boom"),
    dict(nas_error_class="boom"), dict(target_http_status=True), dict(target_http_status=99), dict(target_http_status=600),
    dict(target_http_status="200"), dict(latency_ms=-1), dict(latency_ms=True), dict(latency_ms=1.5),
    dict(checked_at="2026-11-16T10:30:00"), dict(checked_at="not a time"), dict(checked_at=20261116),
])
def test_bad_types_and_values_are_rejected(kw):
    with pytest.raises((ValueError, TypeError)):
        OBS(**kw)


def test_checked_at_display_keeps_the_observed_offset():
    assert vm.checked_at_display("2026-11-16T10:30:00+08:00") == "2026-11-16 10:30 UTC+08:00"
    assert vm.checked_at_display("2026-11-16T02:30:00+00:00") == "2026-11-16 02:30 UTC+00:00"


def test_classify_rejects_non_observations():
    with pytest.raises(TypeError):
        vm.classify({"proxy_configured": True})


# ───────────────────────── 與 shared/backoff_policy 失敗分類同步（漂移會紅） ─────────────────────────

def _mapping_drift(mapping, policy_kinds, error_classes, no_cooldown):
    """對映表 vs 退避政策的差異（純函式，供真測試與負控共用）。"""
    problems = []
    if set(mapping) != set(policy_kinds):
        problems.append(("kind 集合不同", sorted(set(mapping) ^ set(policy_kinds))))
    covered = {c for classes in mapping.values() for c in classes}
    if covered != set(error_classes) - {"ok"}:
        problems.append(("失敗分類沒有被對映表完整涵蓋", sorted(covered ^ (set(error_classes) - {"ok"}))))
    if not set(no_cooldown) <= set(mapping):
        problems.append(("NO_COOLDOWN_KINDS 含對映表沒有的 kind", sorted(set(no_cooldown) - set(mapping))))
    return problems


def test_fail_kind_names_match_shared_backoff_policy():
    assert _mapping_drift(vm.BACKOFF_KIND_TO_CLASSES, bp.BACKOFF_COOLDOWN_SEC, vm.ERROR_CLASSES, bp.NO_COOLDOWN_KINDS) == []
    assert len(bp.BACKOFF_COOLDOWN_SEC) == 6   # 「六種」


def test_drift_check_negative_controls_turn_red():
    full = dict(vm.BACKOFF_KIND_TO_CLASSES)
    dropped = {k: v for k, v in full.items() if k != "blocked"}
    assert _mapping_drift(dropped, bp.BACKOFF_COOLDOWN_SEC, vm.ERROR_CLASSES, bp.NO_COOLDOWN_KINDS)
    renamed = {("rate_limit" if k == "rate_limited" else k): v for k, v in full.items()}
    assert _mapping_drift(renamed, bp.BACKOFF_COOLDOWN_SEC, vm.ERROR_CLASSES, bp.NO_COOLDOWN_KINDS)
    assert _mapping_drift(full, {**bp.BACKOFF_COOLDOWN_SEC, "brand_new_kind": 5}, vm.ERROR_CLASSES, bp.NO_COOLDOWN_KINDS)
    assert _mapping_drift(full, bp.BACKOFF_COOLDOWN_SEC, vm.ERROR_CLASSES + ("brand_new_class",), bp.NO_COOLDOWN_KINDS)


def test_every_fail_kind_assigned_in_infra_proxy_is_known_to_the_policy_and_the_mapping():
    """infra/proxy.py 只讀（AST 掃字串指派，不 import 它）：它指派給 `_fail_kind` 的每個字串都必須在退避政策與本 VM 對映表內。"""
    tree = ast.parse(lib.read(lib.ROOT / "infra" / "proxy.py"))
    assigned = {n.value.value for n in ast.walk(tree) if isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant)
                and isinstance(n.value.value, str) and any(isinstance(t, ast.Name) and t.id == "_fail_kind" for t in n.targets)}
    assert assigned, "找不到 _fail_kind 的字串指派（掃描失效）"
    assert assigned <= set(bp.BACKOFF_COOLDOWN_SEC) and assigned <= set(vm.BACKOFF_KIND_TO_CLASSES), assigned


def test_cause_keys_cover_every_non_ok_class_and_all_have_pending_wording():
    assert set(vm.CAUSE_OF_CLASS) == set(vm.ERROR_CLASSES) - {"ok"}
    for key in vm.CAUSE_KEYS:
        assert key in W.NAS_DIAG_WORDING, key


# ───────────────────────── 暫行字樣 ─────────────────────────

def test_wording_is_pending_with_source_and_never_in_the_approved_table():
    assert len(W.NAS_DIAG_WORDING) > 30
    for key, item in W.NAS_DIAG_WORDING.items():
        assert item.key == key and item.status == "pending" and item.text.strip()
        assert "執行組暫擬" in item.source and "字樣待客戶裁示" in item.source
        assert key not in rules.APPROVED_WORDING and key not in rules.ENTRIES


def test_pending_text_never_equals_or_embeds_approved_wording_or_symbols():
    approved = {e.wording for e in rules.ENTRIES.values() if e.wording and not e.is_pending} | {a.text for a in rules.APPROVED_WORDING.values()}
    symbols = {e.symbol for e in rules.ENTRIES.values() if e.symbol}
    for key, item in W.NAS_DIAG_WORDING.items():
        assert item.text not in approved, key
        assert not any(s in item.text for s in symbols), (key, item.text)


def test_approved_wording_is_reused_for_not_configured_and_undetermined_and_missing():
    assert W.STATE_LABEL_SOURCE[vm.STATE_NOT_CONFIGURED] == ("rule", "not_configured")
    assert W.STATE_LABEL_SOURCE[vm.STATE_UNDETERMINED] == ("rule", "undetermined")
    for kind, key in list(W.STATE_LABEL_SOURCE.values()) + list(W.ROUTE_LABEL_SOURCE.values()) + list(W.NAS_HEALTH_SOURCE.values()) + list(W.TARGET_HEALTH_SOURCE.values()):
        assert key in (rules.ENTRIES if kind == "rule" else W.NAS_DIAG_WORDING), (kind, key)
        if kind == "rule":
            assert not rules.entry(key).is_pending
    # 四個新狀態詞是暫行，不借用規則表的「取數失敗」等字樣
    for state in (vm.STATE_NOT_TESTED, vm.STATE_OK, vm.STATE_FAILED, vm.STATE_DEGRADED):
        assert W.STATE_LABEL_SOURCE[state][0] == "pending"


def test_every_reachable_state_reason_pair_has_a_conclusion_sentence_and_degraded_is_not_called_success():
    pairs = {(v.state, v.reason_key) for v in (_classify(**sup.kwargs(s)) for s in ALL_SCENARIOS)}
    assert pairs <= set(W.CONCLUSION_KEY), pairs - set(W.CONCLUSION_KEY)
    assert set(W.CONCLUSION_KEY.values()) <= set(W.NAS_DIAG_WORDING)
    assert W.NAS_DIAG_WORDING["concl_degraded"].text == "NAS 失敗，改走直連；NAS 並未正常"
    assert "成功" not in W.NAS_DIAG_WORDING["concl_degraded"].text and "成功" not in W.NAS_DIAG_WORDING["state_degraded"].text
    assert W.NAS_DIAG_WORDING["state_ok"].text == "連線成功" != W.NAS_DIAG_WORDING["state_degraded"].text


def test_human_causes_say_which_side_and_never_ask_to_open_the_nas_to_the_public_or_disable_verification():
    texts = {k: W.NAS_DIAG_WORDING[k].text for k in vm.CAUSE_KEYS}
    assert "NAS" in texts["cause_auth_407"] and "NAS" in texts["cause_nas_unreachable"]
    assert "目標網站" in texts["cause_blocked_403"] and "不是 NAS 斷線" in texts["cause_blocked_403"]
    assert "憑證" in texts["cause_tls"] and "不要為了通過而關閉憑證驗證" in texts["cause_tls"]
    for key, text in texts.items():
        for bad in ("開放到公網", "關閉驗證", "verify=False", "verify = False"):
            assert bad not in text.replace("不需要把 NAS 管理介面開放到公網", "").replace("不要為了通過而關閉憑證驗證", ""), (key, bad)


# ───────────────────────── 模組純度 ─────────────────────────

@pytest.mark.parametrize("rel", ["ui_v3/viewmodels/nas_diag.py", "ui_v3/viewmodels/nas_diag_wording.py"])
def test_viewmodel_modules_import_only_stdlib_and_allowed_layers(rel):
    src = lib.read(lib.ROOT / rel)
    assert lib.import_violations(rel, src) == []
    assert lib.write_surface_violations(rel, src) == []
    assert lib.module_level_side_effects(src) == []
    for module in lib.imports_of(ast.parse(src), lib.package_of(rel)):
        root = module.split(".")[0]
        assert root in lib.STDLIB or module.startswith(("ui_v3.viewmodels", "shared.ui_semantics")) or module == "ui_v3", module
    for banned in ("streamlit", "requests", "urllib", "socket", "infra", "repositories", "services", "os", "subprocess"):
        assert not [m for m in lib.imports_of(ast.parse(src), lib.package_of(rel)) if m.split(".")[0] == banned], (rel, banned)
