# -*- coding: utf-8 -*-
"""`services/v2_domain/nav_evidence.py` 離線測試（零網路、零 I/O；只讀合成 fixture）。

結構：12 條必要正負控各一個 `ctl_*` 函式（吃「模組」參數，所以同一份判準可對真模組與變異模組各跑一次）；
變異控制（mutation）：對模組原始碼做單點替換、載入成新模組，**對應控制必須轉紅**；再加純度／身分／契約等結構性測試。
"""
from __future__ import annotations

import ast
import copy
import dataclasses
import itertools
import json
import re
import socket
import sys
import types
from pathlib import Path

import pytest

from services.v2_domain import nav_evidence as real

_FIXTURE = Path(__file__).parent / "fixtures" / "nav_evidence_snapshots.json"
_DOC = json.loads(_FIXTURE.read_text(encoding="utf-8"))
_CASES = {c["case_id"]: c for c in _DOC["cases"]}
_ISIN_RE = re.compile(r"\b[A-Z]{2}[A-Z0-9]{9}[0-9]\b")


def _rules() -> dict:
    """既有規則（`services/health/dividend.py`）由測試端注入；被測模組本身不 import 它們。"""
    from services.health.dividend import check_333_principle, classify_eating_principal
    return {"three_three_three": check_333_principle, "eating_principal": classify_eating_principal}


def _input(cid: str) -> dict:
    return copy.deepcopy(_CASES[cid]["input"])


class _Counting:
    """包住既有規則並計次（只用來證明「有沒有被呼叫」；不改規則）。"""

    def __init__(self, real_rules: dict) -> None:
        self.calls: list = []
        self.rules = {k: self._wrap(k, fn) for k, fn in real_rules.items()}

    def _wrap(self, name, fn):
        def w(*a, **kw):
            self.calls.append(name)
            return fn(*a, **kw)
        return w


def _long_inputs() -> dict:
    return {"years_since_inception": 5.0, "ann_return_3y_pct": 8.5, "total_return_pct": 9.0, "dividend_yield_pct": 4.0}


def _raises(exc, fn) -> bool:
    try:
        fn()
    except exc:
        return True
    return False


# ═══════════════════════════ 12 條必要控制（吃模組參數） ═══════════════════════════
def ctl_01_verified_positive(m) -> None:
    s = m.build_nav_evidence_snapshot(_input("verified_7d"))
    assert s.status == "verified" and s.reason_codes == () and s.conflict_codes == ()
    assert (s.nav, s.ccy, s.times.nav_date) == ("12.3456", "USD", "2026-11-20")
    assert s.source_label and ("nav", "SYN-VERIFIED-7D#nav") in s.support_refs
    assert s.display_allowed and s.derive_allowed and s.ai_usable
    assert s.ai_payload() is not None
    a = dict(s.attribution)
    assert all(a[k] for k in ("license_statement", "license_url", "agency", "source_org", "dataset"))


def ctl_02_conflict(m) -> None:
    for cid in ("conflict_same_day", "conflict_class", "conflict_day_class_verified"):
        s = m.build_nav_evidence_snapshot(_input(cid))
        assert s.status == "withheld_conflict" and s.nav is None and s.to_public_dict()["display"] is None
        assert "input_conflict" in s.reason_codes and s.conflict_codes
    # 檢核布林顯示衝突、但沒有帶扣下原因、且值已釋出：仍必須判衝突（不能被「已釋出」蓋過）。
    ev = _input("verified_7d")
    ev["aggregate"]["checks"]["nav_conflict"] = True
    s = m.build_nav_evidence_snapshot(ev)
    assert s.status == "withheld_conflict" and s.nav is None and "same_day_nav_conflict" in s.conflict_codes
    # 級別核證與日期衝突各自獨立。
    cv = m.build_nav_evidence_snapshot(_input("conflict_day_class_verified"))
    assert dict(cv.checks)["class_verified"] is True and "class_unverified" not in cv.reason_codes
    cc = m.build_nav_evidence_snapshot(_input("conflict_class"))
    assert dict(cc.checks)["class_verified"] is False and "class_unverified" in cc.reason_codes


def ctl_03_not_admitted_rights(m) -> None:
    s = m.build_nav_evidence_snapshot(_input("not_admitted_rights"))
    assert s.status == "withheld_not_admitted" and s.reason_codes == ("rights_unverified",) and s.nav is None
    assert (s.display_allowed, s.derive_allowed, s.ai_usable) == (False, False, False) and s.ai_payload() is None
    # 值已釋出但 R2 非 ALLOWED（結構性防線）：照樣不准顯示。
    ev = _input("verified_7d")
    ev["aggregate"]["rights"]["R2"] = "UNKNOWN"
    s = m.build_nav_evidence_snapshot(ev)
    assert s.status == "withheld_not_admitted" and "rights_unverified" in s.reason_codes and s.nav is None


def ctl_04_missing_never_zero(m) -> None:
    s = m.build_nav_evidence_snapshot(_input("missing_not_found"))
    assert s.status == "missing" and s.nav is None and s.ccy is None and s.to_public_dict()["display"] is None
    assert ("nav", "nav_missing") in s.rejected_metrics
    for bad, expect_status in (("0", "withheld_not_admitted"), ("0.0000", "withheld_not_admitted"), ("abc", "missing"), ("-1.5", "missing"), ("", "missing")):
        ev = _input("verified_7d")
        ev["local_display"]["nav"] = bad
        s = m.build_nav_evidence_snapshot(ev)
        assert s.status == expect_status and s.nav is None, bad
    ev = _input("verified_7d")
    ev["local_display"]["nav"] = 0  # 非字串（數字 0）也不得被當成值
    s = m.build_nav_evidence_snapshot(ev)
    assert s.status == "missing" and s.nav is None


def ctl_05_r4_deny_keeps_display(m) -> None:
    s = m.build_nav_evidence_snapshot(_input("verified_r4_deny"))
    assert s.status == "verified" and s.display_allowed and s.nav == "12.3456"
    assert s.to_public_dict()["display"]["nav"] == "12.3456"
    assert s.rights.r4 == "DENY" and s.ai_usable is False and s.ai_payload() is None and s.derive_allowed is True


def ctl_06_insufficient_rights_no_derive_no_ai(m) -> None:
    for cid, extra in (("verified_r3_unknown", True), ("not_admitted_rights", True)):
        ev = _input(cid)
        ev["aggregate"]["long_term_metrics"] = "supplied_by_evidence"
        ev["rule_inputs"] = _long_inputs()
        spy = _Counting(_rules())
        s = m.build_nav_evidence_snapshot(ev, rules=spy.rules)
        assert spy.calls == [] and s.formulas_called == 0, cid
        assert s.derive_allowed is False and s.ai_usable is False and s.ai_payload() is None, cid
        assert s.three_three_three.kind == "undetermined" and s.eating_principal.kind == "undetermined", cid
    s = m.build_nav_evidence_snapshot(_input("verified_r3_unknown"))
    assert s.three_three_three.reason_code == "rights_unverified" and s.display_allowed is True
    # 基金級扣下時，即使三軸全 ALLOWED 也不得進 AI。
    s = m.build_nav_evidence_snapshot(_input("conflict_same_day"))
    assert s.rights.ai is True and s.ai_usable is False and s.ai_payload() is None


def ctl_07_conflict_nav_not_in_support(m) -> None:
    for cid in ("conflict_same_day", "conflict_class", "conflict_day_class_verified"):
        s = m.build_nav_evidence_snapshot(_input(cid))
        assert not any(k == "nav" for k, _ in s.support_refs) and ("nav", "input_conflict") in s.rejected_metrics
        d = s.to_public_dict()
        assert all(r["metric"] != "nav" for r in d["support_refs"])
    # 直接建構也不能把衝突的 NAV 塞進 support_refs／塞回數字。
    ok = m.build_nav_evidence_snapshot(_input("verified_7d"))
    assert _raises(m.NavEvidenceContractError, lambda: dataclasses.replace(ok, status="withheld_conflict", reason_codes=("input_conflict",), conflict_codes=("same_day_nav_conflict",)))
    c = m.build_nav_evidence_snapshot(_input("conflict_same_day"))
    assert _raises(m.NavEvidenceContractError, lambda: dataclasses.replace(c, support_refs=(("nav", "x#nav"),)))
    assert _raises(m.NavEvidenceContractError, lambda: dataclasses.replace(c, nav="12.3456"))


def ctl_08_time_fields_separate(m) -> None:
    s = m.build_nav_evidence_snapshot(_input("verified_7d"))
    t = s.times
    assert t.fetched_at_utc == "2026-11-25T03:10Z" and t.nav_date == "2026-11-20"
    assert t.supplier_fetched_at is None and t.cache_updated_at is None and t.ccy_declared_at is None  # 沒證據＝null，不互相代填
    assert "supplier_fetched_at_unavailable" in s.data_gaps and "cache_updated_at_unavailable" in s.data_gaps and "ccy_declared_at_unavailable" in s.data_gaps
    u = m.build_nav_evidence_snapshot(_input("supplier_time_without_evidence"))
    assert u.times.supplier_fetched_at is None and "supplier_fetched_at_unevidenced" in u.data_gaps and u.times.fetched_at_utc == "2026-11-25T03:10Z"
    e = m.build_nav_evidence_snapshot(_input("supplier_time_with_evidence"))
    assert (e.times.supplier_fetched_at, e.times.cache_updated_at, e.times.ccy_declared_at) == ("2026-11-24T22:00Z", "2026-11-24T23:00Z", "2026-11-24T21:00Z")
    assert len({e.times.fetched_at_utc, e.times.supplier_fetched_at, e.times.cache_updated_at, e.times.ccy_declared_at}) == 4
    ev = _input("supplier_time_with_evidence")
    ev["supplier_fetched_at"] = "not-a-time"
    assert m.build_nav_evidence_snapshot(ev).times.supplier_fetched_at is None
    ev = _input("supplier_time_with_evidence")
    ev["supplier_fetched_at_evidence_ref"] = "  "
    assert m.build_nav_evidence_snapshot(ev).times.supplier_fetched_at is None
    # 被扣下時沒有本機收到時間可言：`fetched_at_utc` 也是 null，不由別欄代填。
    w = m.build_nav_evidence_snapshot(_input("conflict_same_day"))
    assert w.times.fetched_at_utc is None and w.times.nav_date is None and "fetched_at_utc_unavailable" in w.data_gaps


def ctl_09_attribution_and_source(m) -> None:
    s = m.build_nav_evidence_snapshot(_input("verified_7d"))
    a = dict(s.attribution)
    assert a["dataset"].startswith("SYNTHETIC") and a["license_url"].startswith("https://") and s.source_label.startswith("SYNTHETIC")
    assert a["release_year"] is None and a["dataset_version"] is None and a["metadata_updated_on"] is None  # 「未載明」如實留空，不猜
    assert {"attribution_release_year_unstated", "attribution_dataset_version_unstated", "attribution_metadata_updated_on_unstated"} <= set(s.data_gaps)
    for drop in ("license_url", "license_statement", "agency", "source_org", "dataset"):
        ev = _input("verified_7d")
        del ev["local_display"]["attribution"][drop]
        w = m.build_nav_evidence_snapshot(ev)
        assert w.status == "withheld_not_admitted" and "attribution_missing" in w.reason_codes and w.nav is None, drop
    ev = _input("verified_7d")
    ev["local_display"]["attribution"] = None
    assert m.build_nav_evidence_snapshot(ev).status == "withheld_not_admitted"
    ev = _input("verified_7d")
    ev["local_display"]["attribution"]["release_year"] = 2024  # 有值就原樣採用（轉文字），不當「未載明」
    assert dict(m.build_nav_evidence_snapshot(ev).attribution)["release_year"] == "2024"


def ctl_10_seven_days_no_long_term(m) -> None:
    ev = _input("verified_7d")
    ev["rule_inputs"] = {**_long_inputs(), "dividend_confirmed_none": True}
    spy = _Counting(_rules())
    s = m.build_nav_evidence_snapshot(ev, rules=spy.rules)
    assert spy.calls == [] and s.formulas_called == 0
    assert s.three_three_three == m.MetricResult("undetermined", "history_short") and s.eating_principal == m.MetricResult("undetermined", "history_short")
    assert s.long_term_metrics.startswith("not_computed_insufficient_history") and "history_7d_only" in s.data_gaps and s.distinct_dates == 7
    assert s.dividend_status == "missing" and ("three_three_three", "history_short") in s.rejected_metrics
    # 對照：同樣輸入、改為「長期證據齊備」時才會呼叫既有規則（證明閘門看的是歷史，不是一律不呼叫）。
    ev = _input("verified_rules_pass")
    spy = _Counting(_rules())
    s2 = m.build_nav_evidence_snapshot(ev, rules=spy.rules)
    assert sorted(spy.calls) == ["eating_principal", "three_three_three"] and s2.formulas_called == 2
    # 預設不注入規則＝一個都不呼叫。
    s3 = m.build_nav_evidence_snapshot(_input("verified_rules_pass"))
    assert s3.formulas_called == 0 and s3.three_three_three.reason_code == "required_input_missing"


def ctl_11_golden_shared_by_a_and_c(m) -> None:
    for cid, c in _CASES.items():
        rules = _rules() if c["with_default_rules"] else None
        d = m.build_nav_evidence_snapshot(copy.deepcopy(c["input"]), rules=rules).to_public_dict()
        assert d == c["expect_public"], cid
        assert json.loads(json.dumps(d, ensure_ascii=False)) == d, cid  # 可序列化、無隱藏型別


def ctl_12_immutable(m) -> None:
    s = m.build_nav_evidence_snapshot(_input("verified_rules_pass"), rules=_rules())
    for name, val in (("status", "missing"), ("nav", "1"), ("data_gaps", ()), ("rights", m.Rights())):
        assert _raises(dataclasses.FrozenInstanceError, lambda n=name, v=val: setattr(s, n, v)), name
    assert _raises(dataclasses.FrozenInstanceError, lambda: setattr(s.rights, "r4", "ALLOWED"))
    assert _raises(dataclasses.FrozenInstanceError, lambda: setattr(s.times, "supplier_fetched_at", "2026-01-01"))
    assert _raises(dataclasses.FrozenInstanceError, lambda: setattr(s.three_three_three, "kind", "undetermined"))
    hash(s)  # 可雜湊＝內部沒有 list／dict 等可變容器
    d = s.to_public_dict()
    d["status"] = "withheld_conflict"
    d["display"]["nav"] = "999"
    d["support_refs"].clear()
    d["judgement"]["three_three_three"]["kind"] = "undetermined"
    again = s.to_public_dict()
    assert again["status"] == "verified" and again["display"]["nav"] == "12.3456" and len(again["support_refs"]) == 3
    assert again["judgement"]["three_three_three"]["kind"] == "pass_evidenced"
    assert _raises(m.NavEvidenceContractError, lambda: dataclasses.replace(s, status="bogus"))


_CONTROLS = {n: f for n, f in sorted(globals().items()) if n.startswith("ctl_")}


@pytest.mark.parametrize("name", sorted(_CONTROLS))
def test_required_controls_pass_on_real_module(name):
    _CONTROLS[name](real)


# ═══════════════════════════ 其他語意測試 ═══════════════════════════
def ctl_13_rights_truth_table(m) -> None:
    for r2, r3, r4 in itertools.product(m.RIGHT_STATES, repeat=3):
        r = m.Rights(r2, r3, r4)
        assert r.display is (r2 == "ALLOWED")
        assert r.derive is (r2 == "ALLOWED" and r3 == "ALLOWED")
        assert r.ai is (r2 == "ALLOWED" and r3 == "ALLOWED" and r4 == "ALLOWED")
    for bad in ("allowed", "ALLOWED ", "", None, 1, True):
        ev = _input("verified_7d")
        ev["aggregate"]["rights"]["R2"] = bad
        s = m.build_nav_evidence_snapshot(ev)
        assert s.rights.r2 == "UNKNOWN" and s.status == "withheld_not_admitted", repr(bad)
    ev = _input("verified_7d")
    ev["aggregate"]["rights"]["R4"] = "DENY-SIGNAL"  # 舊詞正規化為 DENY（不是授權）
    assert m.build_nav_evidence_snapshot(ev).rights.r4 == "DENY"
    ev = _input("verified_7d")
    ev["aggregate"]["rights"] = None  # 沒有權利資料＝三軸 UNKNOWN（缺 ≠ 允許）
    s = m.build_nav_evidence_snapshot(ev)
    assert (s.rights.r2, s.rights.r3, s.rights.r4) == ("UNKNOWN",) * 3 and s.status == "withheld_not_admitted"
    # 輸入端宣稱的 use_decisions 不被採信：用途一律由三軸重新推導。
    ev = _input("verified_r4_deny")
    ev["aggregate"]["use_decisions"] = {"display": True, "derive": True, "ai": True}
    assert m.build_nav_evidence_snapshot(ev).ai_usable is False


def ctl_14_rule_semantics(m) -> None:
    rules = _rules()
    p = m.build_nav_evidence_snapshot(_input("verified_rules_pass"), rules=rules)
    assert (p.three_three_three.kind, p.eating_principal.kind, p.dividend_status) == ("pass_evidenced", "pass_evidenced", "present")
    assert p.formulas_called == 2  # 兩項規則各呼叫一次，計數如實
    f = m.build_nav_evidence_snapshot(_input("verified_rules_fail"), rules=rules)
    assert (f.three_three_three.kind, f.eating_principal.kind) == ("fail_evidenced", "fail_evidenced")
    x = m.build_nav_evidence_snapshot(_input("verified_rules_missing_input"), rules=rules)
    assert x.three_three_three == m.MetricResult("undetermined", "required_input_missing")
    assert x.eating_principal == m.MetricResult("undetermined", "return_1y_missing") and x.dividend_status == "missing"
    n = m.build_nav_evidence_snapshot(_input("verified_no_dividend_fact"), rules=rules)
    assert n.eating_principal.kind == "fact_no_dividend" and n.dividend_status == "confirmed_none" and n.three_three_three.kind == "pass_evidenced"
    # 規則說「無配息」但沒有來源層的雙證據確認 → 只能無法判定（不得自己下「無配息」事實）。
    ev = _input("verified_no_dividend_fact")
    del ev["rule_inputs"]["dividend_confirmed_none"]
    u = m.build_nav_evidence_snapshot(ev, rules=rules)
    assert u.eating_principal == m.MetricResult("undetermined", "dividend_not_obtained") and u.dividend_status == "missing"
    # 規則拋例外 → 無法判定，不吞成通過。
    def boom(*a): raise RuntimeError("secret-looking-detail")
    ev = _input("verified_rules_pass")
    b = m.build_nav_evidence_snapshot(ev, rules={"three_three_three": boom, "eating_principal": boom})
    assert b.three_three_three.kind == "undetermined" and b.eating_principal.kind == "undetermined" and "rule_error" in b.data_gaps
    assert b.formulas_called == 2  # 嘗試呼叫即計數（含拋例外者）
    assert "secret-looking-detail" not in json.dumps(b.to_public_dict(), ensure_ascii=False)
    # 缺值不當 0：輸入帶字串／布林／None 一律當缺。
    ev = _input("verified_rules_pass")
    ev["rule_inputs"] = {"years_since_inception": "5", "ann_return_3y_pct": True, "total_return_pct": None, "dividend_yield_pct": "4"}
    z = m.build_nav_evidence_snapshot(ev, rules=rules)
    assert z.three_three_three.kind == "undetermined" and z.eating_principal.kind == "undetermined"


def ctl_15_contract_hardening(m) -> None:
    secret = "ZZ-SECRET-VALUE-123"
    base = _input("verified_7d")
    bad_inputs = [
        None, "x", [], {**base, "snapshot_id": "US1234567890"[:12]}, {**base, "snapshot_id": "bad id!"}, {**base, "snapshot_id": ""},
        {**base, "aggregate": None}, {**base, "local_display": "nope"},
        {**base, "aggregate": {**base["aggregate"], "withheld_reason": secret}},
    ]
    for ev in bad_inputs:
        assert _raises(m.NavEvidenceContractError, lambda e=ev: m.build_nav_evidence_snapshot(e)), repr(ev)[:40]
    try:
        m.build_nav_evidence_snapshot({**base, "aggregate": {**base["aggregate"], "withheld_reason": secret}})
    except m.NavEvidenceContractError as e:
        assert secret not in str(e)
    assert _raises(m.NavEvidenceContractError, lambda: m.build_nav_evidence_snapshot(base, rules=[1]))
    # ISIN 形狀的 id 在建構與直接建構兩條路徑都擋。
    s = m.build_nav_evidence_snapshot(base)
    assert _raises(m.NavEvidenceContractError, lambda: dataclasses.replace(s, snapshot_id="LU0000000008"))
    assert _raises(m.NavEvidenceContractError, lambda: m.build_nav_evidence_snapshot({**base, "snapshot_id": "LU0000000008"}))


def ctl_16_status_precedence(m) -> None:
    # 衝突優先於未准入（rights 不足＋衝突 → 仍是衝突，並同時列出 rights_unverified）。
    ev = _input("conflict_same_day")
    ev["aggregate"]["rights"]["R2"] = "UNKNOWN"
    s = m.build_nav_evidence_snapshot(ev)
    assert s.status == "withheld_conflict" and "rights_unverified" in s.reason_codes and "input_conflict" in s.reason_codes
    # 技術性中止（未列入對照表的原因）＝缺值，不是未准入；未知狀態一律走缺值而非通過。
    s = m.build_nav_evidence_snapshot(_input("missing_technical_stop"))
    assert s.status == "missing" and "fetch_not_completed" in s.data_gaps and s.nav is None
    # 值已釋出但任一檢核布林缺（None）或為 False → 不准顯示（缺 ≠ 通過）。
    for name in ("isin_format_ok", "checksum_ok", "found", "pairing_unambiguous", "class_verified", "date_ok"):
        for v in (None, False):
            ev = _input("verified_7d")
            ev["aggregate"]["checks"][name] = v
            s = m.build_nav_evidence_snapshot(ev)
            assert s.status == "withheld_not_admitted" and s.nav is None, (name, v)
    # 值已釋出但沒有 local_display → 缺值（不得自行編造）。
    ev = _input("verified_7d")
    ev["local_display"] = None
    assert m.build_nav_evidence_snapshot(ev).status == "missing"


_MORE = {n: f for n, f in sorted(globals().items()) if re.match(r"ctl_1[3-9]_", n)}


@pytest.mark.parametrize("name", sorted(_MORE))
def test_additional_controls_pass_on_real_module(name):
    _MORE[name](real)


# ═══════════════════════════ 變異控制：單點替換 → 對應控制必須轉紅 ═══════════════════════════
_SRC = Path(real.__file__).read_text(encoding="utf-8")
_ALL = {**_CONTROLS, **_MORE}
_mut_n = itertools.count()


def _mutant(old, new, count: int = 1) -> types.ModuleType:
    """`old`／`new` 可為單一字串，或等長 tuple（多點同時替換：用來殺掉有「雙層防線」的行為，避免單層變異被另一層掩護）。"""
    olds, news = (old, new) if isinstance(old, tuple) else ((old,), (new,))
    src = _SRC
    for o, n in zip(olds, news):
        want = count if len(olds) == 1 else 1
        assert src.count(o) == want, f"mutation anchor drifted ({src.count(o)}!={want}): {o[:60]!r}"
        src = src.replace(o, n)
    name = f"_nav_evidence_mut_{next(_mut_n)}"
    mod = types.ModuleType(name)
    mod.__file__ = real.__file__
    sys.modules[name] = mod
    try:
        exec(compile(src, f"<{name}>", "exec"), mod.__dict__)
    except BaseException:
        del sys.modules[name]
        raise
    return mod


def _fails(mod, ctl: str) -> bool:
    try:
        _ALL[ctl](mod)
    except Exception:  # noqa: BLE001 — 任何例外（含契約錯誤）都算「該控制抓到變異」
        return True
    return False


_MUTANTS = [
    ("derive 不看 R2", 'return self.r2 == "ALLOWED" and self.r3 == "ALLOWED"\n', 'return self.r3 == "ALLOWED"\n', 1, ("ctl_13_rights_truth_table",)),
    ("ai 不看 R4", 'return self.r2 == "ALLOWED" and self.r3 == "ALLOWED" and self.r4 == "ALLOWED"', 'return self.r2 == "ALLOWED" and self.r3 == "ALLOWED"', 1, ("ctl_05_r4_deny_keeps_display", "ctl_13_rights_truth_table")),
    ("display 恆真", 'def display(self) -> bool:\n        return self.r2 == "ALLOWED"', "def display(self) -> bool:\n        return True", 1, ("ctl_13_rights_truth_table",)),
    ("R4 DENY 連累顯示", 'return self.status == VERIFIED and self.rights.display', 'return self.status == VERIFIED and self.rights.ai', 1, ("ctl_05_r4_deny_keeps_display",)),
    ("拿掉 nav_conflict 檢核", ' or cd["nav_conflict"] is True:', ":", 1, ("ctl_02_conflict",)),
    ("ai_usable 不看狀態", "return self.status == VERIFIED and self.rights.ai", "return self.rights.ai", 1, ("ctl_06_insufficient_rights_no_derive_no_ai",)),
    ("nav 允許 0", "if decimal.Decimal(nav_t) <= 0:", "if decimal.Decimal(nav_t) < 0:", 1, ("ctl_04_missing_never_zero",)),
    ("缺值回 0", "nav=nav if display_ok else None", 'nav=nav if display_ok else "0"', 1, ("ctl_04_missing_never_zero", "ctl_02_conflict")),
    ("供應者時間不要證據", "if _is_text(sup_ref) and _is_stamp(sup_raw):", "if _is_stamp(sup_raw):", 1, ("ctl_08_time_fields_separate",)),
    ("供應者時間用本機時間代填", "        supplier = None\n", "        supplier = fetched\n", 1, ("ctl_08_time_fields_separate",)),
    ("快取時間用本機時間代填", 'cache_u = evidence.get("cache_updated_at") if _is_stamp(evidence.get("cache_updated_at")) else None', "cache_u = fetched", 1, ("ctl_08_time_fields_separate",)),
    ("7 日歷史閘門拿掉", "    elif short:\n", "    elif False:\n", 1, ("ctl_10_seven_days_no_long_term",)),
    ("衍生權利閘門拿掉", "    elif not rights.derive:\n", "    elif False:\n", 1, ("ctl_06_insufficient_rights_no_derive_no_ai",)),
    ("衝突 NAV 進 support_refs", "    if status == VERIFIED:\n        support.append", "    if True:\n        support.append", 1, ("ctl_07_conflict_nav_not_in_support", "ctl_02_conflict")),
    ("顯名核心改為任一即可", "if not all(_is_text(raw.get(k)) for k in _ATTR_CORE):", "if not any(_is_text(raw.get(k)) for k in _ATTR_CORE):", 1, ("ctl_09_attribution_and_source",)),
    ("「未載明」當作真值", 'stated = (_is_year(v) if k == "release_year" else _is_date(v) if k == "metadata_updated_on" else _only(v, _VERSION_CHARS, 1, 32))', "stated = _is_text(v)", 1, ("ctl_09_attribution_and_source",)),
    ("權利缺值預設 ALLOWED", 'v in RIGHT_STATES else "UNKNOWN"', 'v in RIGHT_STATES else "ALLOWED"', 1, ("ctl_13_rights_truth_table",)),
    ("未准入權利檢查拿掉", '        if rights.r2 != "ALLOWED":\n            bad.append("rights_unverified")\n', "", 1, ("ctl_03_not_admitted_rights",)),
    ("判定結果 False 被當缺", "            if passed is True or passed is False:", "            if passed:", 1, ("ctl_14_rule_semantics",)),
    ("無配息事實不需確認", 'if ri.get("dividend_confirmed_none") is True:', "if True:", 1, ("ctl_14_rule_semantics",)),
    ("公式次數不計", "calls += 1", "calls += 0", 2, ("ctl_10_seven_days_no_long_term", "ctl_14_rule_semantics", "ctl_11_golden_shared_by_a_and_c")),
    ("ISIN 形狀 id 放行", " and not _is_isin_shape(value)", "", 1, ("ctl_15_contract_hardening",)),
    ("公開 dict 在未核證時仍帶 display", 'if self.status == VERIFIED else None),', "if True else None),", 1, ("ctl_02_conflict", "ctl_04_missing_never_zero", "ctl_11_golden_shared_by_a_and_c")),
    ("公開 dict 回傳共用容器（改動會污染快照）", '"data_gaps": list(self.data_gaps),', '"data_gaps": self.data_gaps,', 1, ("ctl_11_golden_shared_by_a_and_c",)),
    ("不重新推導用途而採信輸入宣稱", '"use": {"display": self.display_allowed, "derive": self.derive_allowed, "ai": self.ai_usable},', '"use": {"display": True, "derive": True, "ai": True},', 1, ("ctl_11_golden_shared_by_a_and_c",)),
    ("技術中止誤判為已核證", "            status = MISSING\n            _add(gaps, \"fetch_not_completed\")\n    elif not released:\n        status = MISSING", "            status = VERIFIED\n            _add(gaps, \"fetch_not_completed\")\n    elif not released:\n        status = MISSING", 1, ("ctl_16_status_precedence",)),
    ("檢核布林缺值當通過", 'any(cd[n] is not True for n in ("isin_format_ok", "checksum_ok", "found", "pairing_unambiguous"))', 'any(cd[n] is False for n in ("isin_format_ok", "checksum_ok", "found", "pairing_unambiguous"))', 1, ("ctl_16_status_precedence",)),
    ("衝突被未准入蓋過", 'if reason in _CONFLICT_REASONS or cd["nav_conflict"] is True:', 'if False:', 1, ("ctl_02_conflict", "ctl_16_status_precedence")),
    ("nav 文字格式不驗", "parsed_ok = (_is_nav_text(nav_t) and", "parsed_ok = (True and", 1, ("ctl_04_missing_never_zero",)),
    ("契約錯誤回顯值", '"{field}: expected {expected}, got {type(value).__name__}"', '"{field}: expected {expected}, got {value!r}"', 1, ("ctl_15_contract_hardening",)),
]


@pytest.mark.parametrize("label,old,new,count,killers", _MUTANTS, ids=[m[0] for m in _MUTANTS])
def test_mutants_are_killed(label, old, new, count, killers):
    mod = _mutant(old, new, count)
    survived = [c for c in killers if not _fails(mod, c)]
    assert not survived, f"mutant {label!r} survived controls: {survived}"


# ═══════════════════════════ 與 A／C 的共用契約（只對字面；不 import 對方到本模組） ═══════════════════════════
def test_vocabulary_matches_a_view_model():
    from ui_v3.viewmodels import exp_nav as a
    assert set(real.STATUSES) == {e.value for e in a.NavDisplay}
    assert set(real.KINDS) == {e.value for e in a.MetricKind}
    assert a.NAV_REASONS <= real.REASON_CODES  # A 的六個淨值原因碼都在
    assert {"history_short", "rights_unverified", "input_conflict", "nav_not_admitted", "required_input_missing", "return_1y_missing", "dividend_not_obtained"} <= a.METRIC_REASONS
    # 判定列只用 A 既有的原因碼。
    used = set()
    for c in _CASES.values():
        d = c["expect_public"]["judgement"]
        used |= {d["three_three_three"]["reason_code"], d["eating_principal"]["reason_code"]} - {None}
    assert used <= a.METRIC_REASONS
    assert {e.value for e in a.DividendStatus} == {"missing", "confirmed_none", "present"}


def test_public_shape_meets_c_evidence_input_rules():
    """C 的 `admit()` 拒收規則（以字面複製檢查，因 C 的模組尚在別的 PR）：support_refs／rejected_metrics 皆為含 `metric` 的 mapping、
    同一指標不得兩邊都有、證據項不得夾帶結論類鍵（risk_level／action／score…）。"""
    forbidden = {"risk_level", "risk_cap", "action", "recommendation", "score", "rating", "verdict"}
    for cid, c in _CASES.items():
        d = c["expect_public"]
        rej = {r["metric"] for r in d["rejected_metrics"]}
        for ref in d["support_refs"]:
            assert isinstance(ref["metric"], str) and not (forbidden & set(ref)) and ref["metric"] not in rej, cid
        assert all(isinstance(r["metric"], str) for r in d["rejected_metrics"]) and all(isinstance(g, str) for g in d["data_gaps"]), cid
        assert set(d["rights"]) == {"R2", "R3", "R4"}, cid


# ═══════════════════════════ 純度、身分、零網路 ═══════════════════════════
def test_module_is_pure_no_io_no_network_no_ui_imports():
    tree = ast.parse(_SRC)
    allowed = {"__future__", "datetime", "dataclasses", "decimal"}  # 與 `test_v2_domain_port` 的白名單一致；規則函式由呼叫端注入
    seen = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            seen |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            seen.add(n.module or "")
    assert seen <= allowed, seen - allowed
    banned_calls = {"open", "exec", "eval", "compile", "__import__", "input", "print"}
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
            assert n.func.id not in banned_calls, n.func.id
    for word in ("streamlit", "requests", "socket", "subprocess", "urllib", "tdcc_11641_min_fetch", "ui_v3", "ui_v2", "http"):
        assert not re.search(rf"^\s*(import|from)\s+{word}\b", _SRC, re.M), word


def test_builds_every_case_with_network_and_file_open_blocked(monkeypatch):
    def deny(*a, **k):
        raise AssertionError("network touched")
    for name in ("socket", "create_connection", "getaddrinfo"):
        monkeypatch.setattr(socket, name, deny)
    import builtins
    real_open = builtins.open

    def guarded_open(file, *a, **k):
        raise AssertionError(f"file opened: {file!r}")
    for c in _CASES.values():
        monkeypatch.setattr(builtins, "open", guarded_open)
        s = real.build_nav_evidence_snapshot(copy.deepcopy(c["input"]), rules=_rules() if c["with_default_rules"] else None)
        s.to_public_dict(); s.ai_payload()
        monkeypatch.setattr(builtins, "open", real_open)


def test_inputs_are_not_mutated_by_build():
    for c in _CASES.values():
        ev = copy.deepcopy(c["input"])
        before = copy.deepcopy(ev)
        real.build_nav_evidence_snapshot(ev, rules=_rules() if c["with_default_rules"] else None)
        assert ev == before


def test_no_isin_fund_name_or_real_identity_anywhere_in_public_output_or_fixture():
    text = _FIXTURE.read_text(encoding="utf-8")
    assert not _ISIN_RE.findall(text)
    for c in _CASES.values():
        assert "SYNTHETIC FUND" not in json.dumps(c["expect_public"], ensure_ascii=False)  # 輸入裡的基金名稱不外流到快照
        s = real.build_nav_evidence_snapshot(copy.deepcopy(c["input"]))
        assert "SYNTHETIC FUND" not in repr(s) and not _ISIN_RE.findall(json.dumps(s.to_public_dict(), ensure_ascii=False))
    assert {f.name for f in dataclasses.fields(real.NavEvidenceSnapshot)}.isdisjoint({"isin", "fund_code", "fund_name", "name", "url"})


def test_fixture_is_synthetic_and_covers_all_four_states():
    assert _DOC["schema"] == "nav_evidence_snapshots.golden.v1" and all(c["case_id"] for c in _DOC["cases"])
    assert {c["expect_public"]["status"] for c in _DOC["cases"]} == set(real.STATUSES)
    assert all(c["input"]["snapshot_id"].startswith("SYN-") for c in _DOC["cases"])
    assert "example.invalid" in _FIXTURE.read_text(encoding="utf-8")  # 不含任何真實網址
