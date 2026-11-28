# -*- coding: utf-8 -*-
"""NavEvidenceSnapshot：把「一檔基金的 NAV 證據」收成一份不可變的邏輯快照（純函式；A 與 C 共用同一份證據）。

授權：客戶 2026-11-25「B｜NavEvidenceSnapshot 離線施工」（僅三個新增檔案；D1～D4）。**正式 DEC 由治理 writer 落盤，本檔不冒充已入主線的 DEC。**
範圍：邏輯證據快照而已——**不是**正式 Digest schema、**不是** Runtime／Provider；不取數、不做任何 I/O、不 import streamlit／真實取數腳本／任何 UI 套件。
（`services/v2_domain` 的 import 白名單測試要求只用標準庫的 `decimal`／`datetime`／`dataclasses`；故以手寫的小驗證函式取代 `re`／`typing`，輸入只收 `dict`。）
輸入是 `scripts/tdcc_11641_min_fetch.py` 已回存形狀的**純 dict**（`Result.aggregate()`＋僅本機的 `local_display`）；本檔只讀不寫。

不變式（結構性，`NavEvidenceSnapshot.__post_init__` 強制，直接建構也繞不過）：
- 淨值數字**只有** `VERIFIED` 才存在；缺值是 `None`（不是 0、不是中性、不是「未觸發」）。
- 衝突或被扣下的 NAV **不進** `support_refs`；只進 `rejected_metrics`（附原因碼）。
- 權利三軸各自獨立：顯示←R2；衍生←R2∧R3；AI←R2∧R3∧R4。**R4 DENY 不影響 R2 已允許的本機顯示**；權利不足不得衍生、不得進 AI。
- 五個時間欄位互不代填：`fetched_at_utc`（本機收到時間）／`supplier_fetched_at`（原始供應者擷取時間；無獨立證據＝`None`）／
  `cache_updated_at`／`ccy_declared_at`／`nav_date`（觀測日）。
- 判定（3-3-3、吃本金）**只借用既有函式**（`services/health/dividend.py` 的 `check_333_principle`／`classify_eating_principal`），由呼叫端注入
  （本模組**不 import** 它們，也不重寫公式）；預設不注入＝不呼叫（`formulas_called == 0`）。
  只有最近 7 日資料時不做長期健檢、兩項判定一律「無法判定」，**且不呼叫公式**。
- 快照**不含 ISIN、基金代碼、基金名稱**（D2：真實身分資料不入 GitHub；ISIN 只在記憶體、且不進本快照）。

契約不符一律 fail-closed：raise `NavEvidenceContractError`，訊息只含欄位名與型別名，**不回顯收到的值**。
"""
from __future__ import annotations

import datetime as _dt
import decimal
from dataclasses import dataclass

__all__ = (
    "NavEvidenceContractError", "NavEvidenceSnapshot", "Rights", "NavTimes", "MetricResult", "build_nav_evidence_snapshot",
    "SCHEMA", "STATUSES", "REASON_CODES", "KINDS", "RIGHT_STATES", "RIGHT_AXES",
)

SCHEMA = "nav_evidence_snapshot.v1"

# 狀態字（與 NAV-ADMISSION-CASES／A 的 `NavDisplay` 同字；測試鎖字面一致）
VERIFIED = "verified"
WITHHELD_CONFLICT = "withheld_conflict"
WITHHELD_NOT_ADMITTED = "withheld_not_admitted"
MISSING = "missing"
STATUSES = (VERIFIED, WITHHELD_CONFLICT, WITHHELD_NOT_ADMITTED, MISSING)

# 判定種類（與 A 的 `MetricKind` 同字）
PASS_EVIDENCED = "pass_evidenced"
FAIL_EVIDENCED = "fail_evidenced"
FACT_NO_DIVIDEND = "fact_no_dividend"
UNDETERMINED = "undetermined"
KINDS = (PASS_EVIDENCED, FAIL_EVIDENCED, FACT_NO_DIVIDEND, UNDETERMINED)

RIGHT_AXES = ("R2", "R3", "R4")
RIGHT_STATES = ("ALLOWED", "UNKNOWN", "DENY")

#: 淨值區原因碼（固定類別碼；不是訊息）。前六個與 A 的 `NAV_REASONS` 同字；其餘為本快照多出的細項。
REASON_CODES = frozenset({
    "input_conflict", "identity_unverified", "class_unverified", "rights_unverified", "source_untraceable", "ccy_source_unclear",
    "nav_not_positive", "nav_date_in_future", "nav_date_stale", "too_many_dates", "attribution_missing", "nav_date_unverified",
})
#: 判定列原因碼（只用 A 既有的 `METRIC_REASONS` 子集）。
_METRIC_REASONS = frozenset({
    "input_conflict", "rights_unverified", "nav_not_admitted", "dividend_not_obtained", "history_short", "return_1y_missing",
    "required_input_missing",
})

_REJECT_REASONS = REASON_CODES | _METRIC_REASONS | {"nav_missing"}
_CONFLICT_REASONS = {"same_day_conflict": "same_day_nav_conflict", "class_conflict": "class_conflict"}
_MISSING_REASONS = frozenset({"isin_not_found", "nav_unreadable", "nav_date_unreadable"})
#: 取數腳本的扣下原因 → 本快照原因碼（未列者＝技術性中止：沒有值、沒有結論，一律 MISSING＋`fetch_not_completed`）。
_NOT_ADMITTED_MAP = {
    "rights_unverified": "rights_unverified",
    "class_unverified": "class_unverified",
    "class_evidence_insufficient": "class_unverified",
    "pairing_ambiguous": "identity_unverified",
    "isin_invalid": "identity_unverified",
    "ccy_unrecognized": "ccy_source_unclear",
    "nav_not_positive": "nav_not_positive",
    "nav_date_in_future": "nav_date_in_future",
    "nav_date_stale": "nav_date_stale",
    "too_many_dates": "too_many_dates",
}
_CHECK_NAMES = ("isin_format_ok", "checksum_ok", "found", "pairing_unambiguous", "class_verified", "nav_conflict", "date_ok")
#: OGDL 顯名必備（缺任一＝不得顯示）；後三項**依形狀**判斷是否「有載明」（年份／版本代碼／日期）：不合形狀（含來源寫的「未載明」說明文字）就如實留空並記 data_gap，不猜。
_ATTR_CORE = ("license_statement", "license_url", "agency", "source_org", "dataset")
_ATTR_OPTIONAL = ("release_year", "dataset_version", "metadata_updated_on")

_TEXT_MAX = 200
_LONG_TERM_SHORT_PREFIX = "not_computed_insufficient_history"
_DIGITS = "0123456789"
_UP = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_LOW = "abcdefghijklmnopqrstuvwxyz"
_TOKEN_CHARS = _LOW + _DIGITS + "_"
_ID_CHARS = _UP + _LOW + _DIGITS + "._-"
_VERSION_CHARS = _UP + _LOW + _DIGITS + "._-"


class NavEvidenceContractError(ValueError):
    """輸入契約不符（fail-closed）。訊息只含欄位名與型別名，不回顯值。"""


def _need(ok: bool, field: str, expected: str, value: object) -> None:
    if not ok:
        raise NavEvidenceContractError(f"{field}: expected {expected}, got {type(value).__name__}") from None


def _only(value: object, chars: str, lo: int, hi: int) -> bool:
    return isinstance(value, str) and lo <= len(value) <= hi and all(c in chars for c in value)


def _is_token(value: object) -> bool:
    return _only(value, _TOKEN_CHARS, 1, 64)


def _is_sid(value: object) -> bool:
    """不透明 id：英數與 `._-`，且**不得長得像 ISIN**（D2：真實身分不入快照）。"""
    return _only(value, _ID_CHARS, 1, 64) and not _is_isin_shape(value)


def _is_isin_shape(value: object) -> bool:
    return (isinstance(value, str) and len(value) == 12 and _only(value[:2], _UP, 2, 2)
            and _only(value[2:11], _UP + _DIGITS, 9, 9) and value[11] in _DIGITS)


def _is_date(value: object) -> bool:
    if not (isinstance(value, str) and len(value) == 10 and value[4] == "-" and value[7] == "-"
            and _only(value[:4] + value[5:7] + value[8:], _DIGITS, 8, 8)):
        return False
    try:
        _dt.date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _is_stamp(value: object) -> bool:
    """ISO 日期，或 `YYYY-MM-DDTHH:MM[:SS]Z`。"""
    if not isinstance(value, str) or not _is_date(value[:10]):
        return False
    if len(value) == 10:
        return True
    rest = value[10:]
    if len(rest) not in (7, 10) or rest[0] != "T" or rest[3] != ":" or rest[-1] != "Z":
        return False
    parts = [rest[1:3], rest[4:6]] + ([rest[7:9]] if len(rest) == 10 else [])
    if len(rest) == 10 and rest[6] != ":":
        return False
    if not all(_only(p, _DIGITS, 2, 2) for p in parts):
        return False
    hh, mm = int(parts[0]), int(parts[1])
    ss = int(parts[2]) if len(parts) == 3 else 0
    return hh < 24 and mm < 60 and ss < 60


def _is_nav_text(value: object) -> bool:
    if not isinstance(value, str):
        return False
    whole, dot, frac = value.partition(".")
    return _only(whole, _DIGITS, 1, 12) and (dot == "" or _only(frac, _DIGITS, 1, 8))


def _is_text(value: object) -> bool:
    return isinstance(value, str) and value.strip() != "" and len(value) <= _TEXT_MAX


def _is_year(value: object) -> bool:
    return _only(value, _DIGITS, 4, 4)


def _add(seq: list, code: str) -> None:
    if code not in seq:
        seq.append(code)


# ───────────────────────────── 資料類型（全部 frozen；容器一律 tuple） ─────────────────────────────
@dataclass(frozen=True, slots=True)
class Rights:
    """三條權利軸（各自獨立；用途由三軸**推導**，不是輸入）。"""

    r2: str = "UNKNOWN"
    r3: str = "UNKNOWN"
    r4: str = "UNKNOWN"

    def __post_init__(self) -> None:
        for name in ("r2", "r3", "r4"):
            _need(getattr(self, name) in RIGHT_STATES, name, "ALLOWED/UNKNOWN/DENY", getattr(self, name))

    @property
    def display(self) -> bool:
        return self.r2 == "ALLOWED"

    @property
    def derive(self) -> bool:
        return self.r2 == "ALLOWED" and self.r3 == "ALLOWED"

    @property
    def ai(self) -> bool:
        return self.r2 == "ALLOWED" and self.r3 == "ALLOWED" and self.r4 == "ALLOWED"


@dataclass(frozen=True, slots=True)
class NavTimes:
    """五個時間欄位：互不代填；沒有證據就是 `None`。"""

    fetched_at_utc: str | None = None      # 本機收到回應的時間（不是供應者擷取時間）
    supplier_fetched_at: str | None = None  # 原始供應者擷取時間：只在有獨立證據時才有值
    cache_updated_at: str | None = None
    ccy_declared_at: str | None = None
    nav_date: str | None = None             # 觀測日（日期）

    def __post_init__(self) -> None:
        for name in ("fetched_at_utc", "supplier_fetched_at", "cache_updated_at", "ccy_declared_at"):
            v = getattr(self, name)
            _need(v is None or _is_stamp(v), name, "ISO date or Z timestamp or None", v)
        _need(self.nav_date is None or _is_date(self.nav_date), "nav_date", "ISO date or None", self.nav_date)


@dataclass(frozen=True, slots=True)
class MetricResult:
    """一項判定的結果。`UNDETERMINED` 必附原因碼；`evidence` 是 (標籤, 值) 字串對，值**原樣不四捨五入**。"""

    kind: str
    reason_code: str | None = None
    evidence: tuple = ()

    def __post_init__(self) -> None:
        _need(self.kind in KINDS, "kind", "a known metric kind", self.kind)
        if self.kind == UNDETERMINED:
            _need(self.reason_code in _METRIC_REASONS, "reason_code", "a known metric reason", self.reason_code)
        else:
            _need(self.reason_code is None, "reason_code", "None unless undetermined", self.reason_code)
        _need(isinstance(self.evidence, tuple) and all(isinstance(p, tuple) and len(p) == 2 and _is_text(p[0]) and _is_text(p[1]) for p in self.evidence),
              "evidence", "tuple of (label, value) texts", self.evidence)
        if self.kind in (PASS_EVIDENCED, FAIL_EVIDENCED):
            _need(len(self.evidence) >= 1, "evidence", "non-empty for an evidenced result", self.evidence)


@dataclass(frozen=True, slots=True)
class NavEvidenceSnapshot:
    """不可變的 NAV 證據快照。**直接建構亦受結構性不變式約束**（`__post_init__`）；建議一律用 `build_nav_evidence_snapshot`。"""

    snapshot_id: str
    status: str
    reason_codes: tuple
    conflict_codes: tuple
    rights: Rights
    times: NavTimes
    checks: tuple
    nav: str | None = None            # 只在 VERIFIED 才有；缺值＝None（不是 0）
    ccy: str | None = None
    source_label: str | None = None
    attribution: tuple = ()
    distinct_dates: int | None = None
    long_term_metrics: str | None = None
    three_three_three: MetricResult = MetricResult(UNDETERMINED, "required_input_missing")
    eating_principal: MetricResult = MetricResult(UNDETERMINED, "required_input_missing")
    dividend_status: str = "missing"
    support_refs: tuple = ()          # (metric, ref)
    rejected_metrics: tuple = ()      # (metric, reason_code)
    data_gaps: tuple = ()
    formulas_called: int = 0

    def __post_init__(self) -> None:
        _need(_is_sid(self.snapshot_id), "snapshot_id", "an opaque id that is not ISIN-shaped", self.snapshot_id)
        _need(self.status in STATUSES, "status", "a known status", self.status)
        _need(isinstance(self.reason_codes, tuple) and all(c in REASON_CODES for c in self.reason_codes) and len(set(self.reason_codes)) == len(self.reason_codes),
              "reason_codes", "unique known reason codes", self.reason_codes)
        _need(isinstance(self.rights, Rights), "rights", "Rights", self.rights)
        _need(isinstance(self.times, NavTimes), "times", "NavTimes", self.times)
        _need(isinstance(self.formulas_called, int) and not isinstance(self.formulas_called, bool) and self.formulas_called >= 0,
              "formulas_called", "non-negative int", self.formulas_called)
        _need(self.dividend_status in ("missing", "confirmed_none", "present"), "dividend_status", "known dividend status", self.dividend_status)
        for name in ("three_three_three", "eating_principal"):
            _need(isinstance(getattr(self, name), MetricResult), name, "MetricResult", getattr(self, name))
        _need(self.three_three_three.kind != FACT_NO_DIVIDEND, "three_three_three", "not a dividend fact", self.three_three_three)
        _need((self.eating_principal.kind == FACT_NO_DIVIDEND) == (self.dividend_status == "confirmed_none"),
              "eating_principal", "a no-dividend fact exactly when the dividend status is confirmed-none", self.eating_principal)
        s = self.status
        if s == VERIFIED:
            # 只有 VERIFIED 才有數字；且權利、顯名、幣別、觀測日、來源缺一不可。
            for name in ("nav", "ccy", "source_label"):
                _need(getattr(self, name) is not None, name, "present when verified", None)
            _need(self.times.nav_date is not None, "nav_date", "present when verified", None)
            _need(self.rights.display, "rights", "R2 ALLOWED when verified", self.rights)
            _need(self.reason_codes == () and self.conflict_codes == (), "reason_codes", "empty when verified", self.reason_codes)
            _need(len(self.attribution) > 0 and all(dict(self.attribution).get(k) for k in _ATTR_CORE), "attribution", "complete core attribution when verified", None)
            _need(any(m == "nav" for m, _ in self.support_refs), "support_refs", "contains nav when verified", None)
            _need(not any(m == "nav" for m, _ in self.rejected_metrics), "rejected_metrics", "no nav when verified", None)
        else:
            _need(self.nav is None and self.ccy is None and self.times.nav_date is None, "nav", "None unless verified", None)
            _need(not any(m == "nav" for m, _ in self.support_refs), "support_refs", "no nav unless verified", None)
            _need(any(m == "nav" for m, _ in self.rejected_metrics), "rejected_metrics", "contains nav when not verified", None)
            _need(all(r in _REJECT_REASONS for _, r in self.rejected_metrics), "rejected_metrics", "known reason codes", None)
            for name in ("three_three_three", "eating_principal"):
                _need(getattr(self, name).kind == UNDETERMINED, name, "undetermined when the nav is not verified", None)
            _need(self.dividend_status != "confirmed_none", "dividend_status", "not confirmed-none when the nav is not verified", None)
        if s == WITHHELD_CONFLICT:
            _need("input_conflict" in self.reason_codes and len(self.conflict_codes) >= 1, "reason_codes", "input_conflict plus a conflict code", self.reason_codes)
        else:
            _need(self.conflict_codes == () and "input_conflict" not in self.reason_codes, "conflict_codes", "empty unless withheld for conflict", self.conflict_codes)
        if s == WITHHELD_NOT_ADMITTED:
            _need(len(self.reason_codes) >= 1, "reason_codes", "non-empty when not admitted", self.reason_codes)
        # 同一指標不得同時是「支持」與「被拒」。
        _need(not ({m for m, _ in self.support_refs} & {m for m, _ in self.rejected_metrics}), "support_refs", "disjoint from rejected_metrics", None)
        # 判定要有證據才可有結論：只有衍生權利成立才可能是 evidenced／fact。
        if not self.rights.derive:
            for name in ("three_three_three", "eating_principal"):
                _need(getattr(self, name).kind == UNDETERMINED, name, "undetermined without derive rights", None)
            _need(self.formulas_called == 0, "formulas_called", "0 without derive rights", self.formulas_called)

    # ─── 派生（全由三軸＋狀態算出；沒有第二套判斷邏輯） ───
    @property
    def display_allowed(self) -> bool:
        return self.status == VERIFIED and self.rights.display

    @property
    def derive_allowed(self) -> bool:
        return self.status == VERIFIED and self.rights.derive

    @property
    def ai_usable(self) -> bool:
        return self.status == VERIFIED and self.rights.ai

    def to_public_dict(self) -> dict:
        """給 A（顯示）與 C（證據輸入）的同一份公開形狀。每次呼叫都回**全新**的 dict（改它不影響快照）；不含 ISIN／代碼／名稱。"""
        def _m(r: MetricResult) -> dict:
            return {"kind": r.kind, "reason_code": r.reason_code, "evidence": [[a, b] for a, b in r.evidence]}
        t = self.times
        return {
            "schema": SCHEMA,
            "snapshot_id": self.snapshot_id,
            "status": self.status,
            "reason_codes": list(self.reason_codes),
            "conflict_codes": list(self.conflict_codes),
            "display": ({"nav": self.nav, "ccy": self.ccy, "nav_date": t.nav_date, "source_label": self.source_label} if self.status == VERIFIED else None),
            "times": {"fetched_at_utc": t.fetched_at_utc, "supplier_fetched_at": t.supplier_fetched_at, "cache_updated_at": t.cache_updated_at,
                      "ccy_declared_at": t.ccy_declared_at, "nav_date": t.nav_date},
            "rights": {"R2": self.rights.r2, "R3": self.rights.r3, "R4": self.rights.r4},
            "use": {"display": self.display_allowed, "derive": self.derive_allowed, "ai": self.ai_usable},
            "checks": {k: v for k, v in self.checks},
            "attribution": ({k: v for k, v in self.attribution} if self.attribution else None),
            "history": {"distinct_dates": self.distinct_dates, "long_term_metrics": self.long_term_metrics},
            "judgement": {"three_three_three": _m(self.three_three_three), "eating_principal": _m(self.eating_principal), "dividend_status": self.dividend_status},
            "support_refs": [{"metric": m, "ref": r} for m, r in self.support_refs],
            "rejected_metrics": [{"metric": m, "reason": r} for m, r in self.rejected_metrics],
            "data_gaps": list(self.data_gaps),
            "formulas_called": self.formulas_called,
        }

    def ai_payload(self) -> dict | None:
        """AI 可用的證據：**只有** VERIFIED 且 R2∧R3∧R4 皆 ALLOWED 才有；否則 `None`（不是空 dict、不是降級版）。"""
        if not self.ai_usable:
            return None
        d = self.to_public_dict()
        return {"snapshot_id": d["snapshot_id"], "display": d["display"], "times": d["times"], "attribution": d["attribution"],
                "judgement": d["judgement"], "support_refs": d["support_refs"], "rejected_metrics": d["rejected_metrics"], "data_gaps": d["data_gaps"]}


# ───────────────────────────── 解析 ─────────────────────────────
def _rights_from(raw: object) -> Rights:
    if not isinstance(raw, dict):
        return Rights()
    out = {}
    for axis in RIGHT_AXES:
        v = raw.get(axis)
        v = "DENY" if v == "DENY-SIGNAL" else v
        out[axis.lower()] = v if type(v) is str and v in RIGHT_STATES else "UNKNOWN"
    return Rights(**out)


def _checks_from(raw: object) -> tuple:
    m = raw if isinstance(raw, dict) else {}
    return tuple((n, m.get(n) if isinstance(m.get(n), bool) else None) for n in _CHECK_NAMES)


def _attr_from(raw: object, gaps: list) -> tuple | None:
    """核心五項齊全才回 tuple；否則 None（呼叫端據此不准顯示）。後三項「未載明」＝如實 None，不猜。"""
    if not isinstance(raw, dict):
        return None
    if not all(_is_text(raw.get(k)) for k in _ATTR_CORE):
        return None
    pairs = [(k, raw[k]) for k in _ATTR_CORE]
    for k in _ATTR_OPTIONAL:
        v = raw.get(k)
        if isinstance(v, int) and not isinstance(v, bool):
            v = str(v)
        stated = (_is_year(v) if k == "release_year" else _is_date(v) if k == "metadata_updated_on" else _only(v, _VERSION_CHARS, 1, 32))
        if stated:
            pairs.append((k, v))
        else:
            pairs.append((k, None))
            _add(gaps, f"attribution_{k}_unstated")
    return tuple(pairs)


def _num(v: object) -> float | None:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _ev(label: str, value: float | None) -> tuple:
    return (label, repr(value))


def _undetermined(reason: str) -> MetricResult:
    return MetricResult(UNDETERMINED, reason)


def build_nav_evidence_snapshot(evidence: dict, *, rules: dict | None = None) -> NavEvidenceSnapshot:
    """由已回存形狀的純 dict 建出快照。純函式、零 I/O。

    `evidence` 鍵：`snapshot_id`（不透明 id，不得長得像 ISIN）、`aggregate`（`Result.aggregate()`）、`local_display`（僅本機；扣下時為 None）、
    選填：`supplier_fetched_at`＋`supplier_fetched_at_evidence_ref`（兩者皆有才採信）、`cache_updated_at`、`ccy_declared_at`、
    `rule_inputs`（`years_since_inception`／`ann_return_3y_pct`／`total_return_pct`／`dividend_yield_pct`／`dividend_confirmed_none`）。
    `rules`：注入既有規則函式的 mapping（預設 `None`＝一個公式都不呼叫）。
    """
    _need(isinstance(evidence, dict), "evidence", "dict", evidence)
    sid = evidence.get("snapshot_id")
    _need(_is_sid(sid), "snapshot_id", "an opaque id that is not ISIN-shaped", sid)
    agg = evidence.get("aggregate")
    _need(isinstance(agg, dict), "aggregate", "dict", agg)
    disp = evidence.get("local_display")
    _need(disp is None or isinstance(disp, dict), "local_display", "dict or None", disp)
    _need(rules is None or isinstance(rules, dict), "rules", "dict or None", rules)

    rights = _rights_from(agg.get("rights"))
    checks = _checks_from(agg.get("checks"))
    cd = dict(checks)
    reason = agg.get("withheld_reason") if agg.get("withheld_reason") is not None else agg.get("stop_reason")
    _need(reason is None or _is_token(reason), "withheld_reason", "a short token or None", reason)
    released = agg.get("value_released") is True and isinstance(disp, dict)
    long_term = agg.get("long_term_metrics")
    long_term = long_term if _is_token(long_term) else None
    dd = agg.get("distinct_dates")
    dd = dd if isinstance(dd, int) and not isinstance(dd, bool) and dd >= 0 else None

    gaps: list = []
    reasons: list = []
    conflict: list = []

    # ── 時間（互不代填）──
    d = disp if isinstance(disp, dict) else {}
    fetched = d.get("fetched_at_utc") if _is_stamp(d.get("fetched_at_utc")) else None
    if fetched is None:
        _add(gaps, "fetched_at_utc_unavailable")
    sup_ref = evidence.get("supplier_fetched_at_evidence_ref")
    sup_raw = evidence.get("supplier_fetched_at")
    if _is_text(sup_ref) and _is_stamp(sup_raw):
        supplier = sup_raw
    else:
        supplier = None
        _add(gaps, "supplier_fetched_at_unevidenced" if sup_raw is not None else "supplier_fetched_at_unavailable")
    cache_u = evidence.get("cache_updated_at") if _is_stamp(evidence.get("cache_updated_at")) else None
    if cache_u is None:
        _add(gaps, "cache_updated_at_unavailable")
    ccy_at = evidence.get("ccy_declared_at") if _is_stamp(evidence.get("ccy_declared_at")) else None
    if ccy_at is None:
        _add(gaps, "ccy_declared_at_unavailable")

    # ── 狀態 ──
    attr = _attr_from(d.get("attribution"), gaps) if released else None
    display_ok = False
    nav = ccy = source_label = nav_date = None
    if reason in _CONFLICT_REASONS or cd["nav_conflict"] is True:
        status = WITHHELD_CONFLICT
        _add(reasons, "input_conflict")
        if reason in _CONFLICT_REASONS:
            _add(conflict, _CONFLICT_REASONS[reason])
        if cd["nav_conflict"] is True:
            _add(conflict, "same_day_nav_conflict")
        if cd["class_verified"] is not True and cd["class_verified"] is not None:
            _add(reasons, "class_unverified")  # 級別未核證與日期衝突是兩件事，各自獨立列出
    elif reason in _MISSING_REASONS:
        status = MISSING
    elif reason is not None:
        if reason in _NOT_ADMITTED_MAP:
            status = WITHHELD_NOT_ADMITTED
            _add(reasons, _NOT_ADMITTED_MAP[reason])
        else:
            status = MISSING
            _add(gaps, "fetch_not_completed")
    elif not released:
        status = MISSING
        _add(gaps, "fetch_not_completed")
    else:
        # 值已釋出：仍逐項結構性核對（任何一項不成立＝不准顯示；缺 ≠ 通過）
        bad = []
        if any(cd[n] is not True for n in ("isin_format_ok", "checksum_ok", "found", "pairing_unambiguous")):
            bad.append("identity_unverified")
        if cd["class_verified"] is not True:
            bad.append("class_unverified")
        if cd["date_ok"] is not True:
            bad.append("nav_date_unverified")
        nav_t, ccy_t, date_t, src_t = d.get("nav"), d.get("currency"), d.get("nav_date"), d.get("source")
        parsed_ok = (_is_nav_text(nav_t) and _only(ccy_t, _UP, 3, 3) and _is_date(date_t) and _is_text(src_t))
        if parsed_ok:
            try:
                if decimal.Decimal(nav_t) <= 0:
                    bad.append("nav_not_positive")
            except decimal.InvalidOperation:
                parsed_ok = False
        if attr is None:
            bad.append("attribution_missing")
        if rights.r2 != "ALLOWED":
            bad.append("rights_unverified")
        if not parsed_ok:
            status = MISSING
            _add(gaps, "display_fields_invalid")
        elif bad:
            status = WITHHELD_NOT_ADMITTED
            for c in bad:
                _add(reasons, c)
        else:
            status = VERIFIED
            display_ok = True
            nav, ccy, source_label, nav_date = nav_t, ccy_t, src_t, date_t
    if status in (WITHHELD_CONFLICT, WITHHELD_NOT_ADMITTED) and rights.r2 != "ALLOWED":
        _add(reasons, "rights_unverified")

    # ── 判定（只借用注入的既有函式；先過閘門再呼叫）──
    calls = 0
    short = long_term is not None and long_term.startswith(_LONG_TERM_SHORT_PREFIX)
    if short:
        _add(gaps, "history_7d_only")
    dividend_status = "missing"
    if status != VERIFIED:
        why = "input_conflict" if status == WITHHELD_CONFLICT else "nav_not_admitted"
        m333 = mep = _undetermined(why)
    elif not rights.derive:
        m333 = mep = _undetermined("rights_unverified")
    elif short:
        m333 = mep = _undetermined("history_short")
    else:
        ri = evidence.get("rule_inputs")
        ri = ri if isinstance(ri, dict) else None
        fn333 = rules.get("three_three_three") if (rules is not None and ri is not None) else None
        fnep = rules.get("eating_principal") if (rules is not None and ri is not None) else None
        m333 = _undetermined("required_input_missing")
        mep = _undetermined("required_input_missing")
        if callable(fn333):
            yrs, ann = _num(ri.get("years_since_inception")), _num(ri.get("ann_return_3y_pct"))
            calls += 1
            try:
                r = fn333(yrs, ann)
                passed = r.get("passed") if isinstance(r, dict) else None
            except Exception:  # noqa: BLE001 — 規則拋例外＝無法判定（不吞成通過、不回顯）
                passed = None
                _add(gaps, "rule_error")
            if passed is True or passed is False:
                m333 = MetricResult(PASS_EVIDENCED if passed else FAIL_EVIDENCED, None, (_ev("years_since_inception", yrs), _ev("ann_return_3y_pct", ann)))
        if callable(fnep):
            tr, dy = _num(ri.get("total_return_pct")), _num(ri.get("dividend_yield_pct"))
            calls += 1
            ok = False
            missing_flag = no_div = eating = False
            try:
                core = fnep(tr, dy)
                missing_flag, no_div, eating = bool(core.is_data_missing), bool(core.is_no_dividend), bool(core.is_eating)
                ok = True
            except Exception:  # noqa: BLE001
                _add(gaps, "rule_error")
            if ok:
                if missing_flag:
                    mep = _undetermined("return_1y_missing" if tr is None else "dividend_not_obtained")
                elif no_div:
                    if ri.get("dividend_confirmed_none") is True:
                        mep = MetricResult(FACT_NO_DIVIDEND)
                        dividend_status = "confirmed_none"
                    else:
                        mep = _undetermined("dividend_not_obtained")
                else:
                    mep = MetricResult(FAIL_EVIDENCED if eating else PASS_EVIDENCED, None, (_ev("total_return_pct", tr), _ev("dividend_yield_pct", dy)))
                    dividend_status = "present"
    if dividend_status == "missing":
        _add(gaps, "dividend_data_unavailable")

    # ── 證據引用／被拒指標（衝突或被扣下的 NAV 絕不進 support_refs）──
    support: list = []
    rejected: list = []
    if status == VERIFIED:
        support.append(("nav", f"{sid}#nav"))
    else:
        rejected.append(("nav", reasons[0] if reasons else "nav_missing"))
    for name, m in (("three_three_three", m333), ("eating_principal", mep)):
        if m.kind in (PASS_EVIDENCED, FAIL_EVIDENCED, FACT_NO_DIVIDEND):
            support.append((name, f"{sid}#{name}"))
        else:
            rejected.append((name, m.reason_code))

    return NavEvidenceSnapshot(
        snapshot_id=sid, status=status, reason_codes=tuple(reasons), conflict_codes=tuple(conflict), rights=rights,
        times=NavTimes(fetched_at_utc=fetched, supplier_fetched_at=supplier, cache_updated_at=cache_u, ccy_declared_at=ccy_at,
                       nav_date=nav_date if display_ok else None),
        checks=checks, nav=nav if display_ok else None, ccy=ccy if display_ok else None, source_label=source_label if display_ok else None,
        attribution=attr or (), distinct_dates=dd, long_term_metrics=long_term,
        three_three_three=m333, eating_principal=mep, dividend_status=dividend_status,
        support_refs=tuple(support), rejected_metrics=tuple(rejected), data_gaps=tuple(gaps), formulas_called=calls,
    )
