# -*- coding: utf-8 -*-
"""🔍 找基金結果卡的 NAV／輔助判定 sibling view model（純 Python，只用標準函式庫；不取數、不算公式、不含任何顯示字樣）。

授權：客戶 2026-11-24 核准 A-EXP-NAV-SIBLING-FAKE-1（G1／G2／G5；`#1296` comment 7131670389，**要點轉述；正式 DEC 由治理 writer 落盤，本檔不冒充已入主線的 DEC**）。
範圍：僅本機隔離 `ui_v3` /exp Preview。**不變更** `FundLookupView`／`ProfileFields`／`FieldView`、五欄順序或既有算法；不定義正式 L1／L2／Digest schema。
規格依據：`NAV-ADMISSION-CASES v1.0.1-draft`（#7126703853）、A 的 UI 映射（#7129644954）、Work 規格 PASS（#7131280961）。

這裡只放「已判定好的結果」：
- 3-3-3 與吃本金的**判定與數值格式化都在來源層完成**（FAKE fixture；日後是 L2）。renderer 與本檔都**不算、不四捨五入、不呼叫任何公式**
  （DEC 長期原則：UI 不承載核心投資邏輯；也避開公式訊息字串 `7.01→7.0` 的四捨五入陷阱）。
- 淨值**只有**在 `VERIFIED` 時才有數值：`nav_value` 非空 ⇒ `VERIFIED`＋幣別、觀測日、來源、快取更新時間齊備（`__post_init__` 強制）。
  被扣下（衝突、未准入）或缺值時，結構上放不進淨值數字。
- 三個時間欄位不互相代填：`nav_date`（觀測日）／`cache_updated_at`（快取更新時間）／`supplier_fetched_at`（原始供應者擷取時間；`None`＝未知）；
  幣別有自己的 `ccy_declared_at`。
- 三種判定結果互斥：有證據的未通過（❌）／已證實無配息的事實（無判定符號）／無法判定（⬜）。`is_eating=False` 之類布林不進本檔。
- 層 F（基金級：衝突、未准入）命中 ⇒ 兩項判定一律 `UNDETERMINED`；層 M（指標級）逐項獨立，每項只列自己的原因。

契約不符一律 fail-closed：raise `ExpNavContractError`，訊息只含欄位名與型別名，**絕不回顯收到的值**。
"""
from __future__ import annotations

import datetime as _dt
import re
import unicodedata
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

__all__ = (
    "ExpNavContractError", "NavDisplay", "MetricKind", "DividendStatus", "ConflictDiag", "NavSummaryView", "MetricView", "JudgementView",
    "ExpNavView", "NAV_REASONS", "METRIC_REASONS", "TEXT_MAX",
)

#: 任一顯示字串的長度上限（保守值）。
TEXT_MAX = 120


class ExpNavContractError(ValueError):
    """sibling 契約不符（fail-closed）。訊息只含欄位名與型別名，不回顯值。"""


class NavDisplay(Enum):
    VERIFIED = "verified"
    WITHHELD_CONFLICT = "withheld_conflict"
    WITHHELD_NOT_ADMITTED = "withheld_not_admitted"
    MISSING = "missing"


class MetricKind(Enum):
    PASS_EVIDENCED = "pass_evidenced"        # 已准入且輸入齊全、明確通過／未吃本金
    FAIL_EVIDENCED = "fail_evidenced"        # 已准入且有明確反證（未達門檻、成立未滿 3 年、含息報酬低於配息率）
    FACT_NO_DIVIDEND = "fact_no_dividend"    # 已證實無配息（事實；無判定符號）
    UNDETERMINED = "undetermined"            # 缺輸入／衝突／未准入：不計算、不顯示結論


class DividendStatus(Enum):
    MISSING = "missing"                      # 配息資料未取得（不是「無配息」）
    CONFIRMED_NONE = "confirmed_none"        # 已證實無配息（需雙證據；由來源層判定）
    PRESENT = "present"


#: 淨值區原因碼（固定類別碼；不是訊息、不上畫面；字樣屬 wording 層）。
NAV_REASONS = frozenset({
    "input_conflict", "identity_unverified", "class_unverified", "rights_unverified", "source_untraceable", "ccy_source_unclear",
})
#: 判定列原因碼（只列該指標自己的原因）。
METRIC_REASONS = frozenset({
    "input_conflict", "identity_unverified", "rights_unverified", "nav_not_admitted",
    "dividend_not_obtained", "history_short", "inception_missing", "return_1y_missing", "proxy_input", "stale", "required_input_missing",
})
#: 衝突碼。
CONFLICT_CODES = frozenset({"nav_before_inception"})
_CCY_SOURCES = frozenset({"declared_page"})

_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_STAMP = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}(?:T[0-9]{2}:[0-9]{2}(?::[0-9]{2})?Z)?")


def _kind(value: object) -> str:
    return type(value).__name__


def _need(ok: bool, field: str, expected: str, value: object) -> None:
    if not ok:
        raise ExpNavContractError(f"{field}: expected {expected}, got {_kind(value)}") from None


def _is_text(value: object) -> bool:
    return (isinstance(value, str) and value.strip() != "" and len(value) <= TEXT_MAX
            and not any(unicodedata.category(c).startswith("C") for c in value)
            and "http" not in value.lower() and "www." not in value.lower())


def _is_date(value: object) -> bool:
    if not isinstance(value, str) or _DATE.fullmatch(value) is None:
        return False
    try:
        _dt.date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _is_stamp(value: object) -> bool:
    """擷取型時間（快取更新／原始供應者擷取／幣別自報）：ISO 日期，或帶 `Z` 的 ISO 時間戳（到分或秒）。**原值保留，不截成日期**。"""
    if not isinstance(value, str) or _STAMP.fullmatch(value) is None:
        return False
    if not _is_date(value[:10]):
        return False
    if len(value) > 10:
        hh, mm = int(value[11:13]), int(value[14:16])
        ss = int(value[17:19]) if len(value) >= 20 else 0
        return hh < 24 and mm < 60 and ss < 60
    return True


def _opt(value: object, check, field: str, expected: str) -> None:
    _need(value is None or check(value), field, expected + " or None", value)


@dataclass(frozen=True)
class ConflictDiag:
    """衝突診斷（兩邊的標籤代碼與日期值；**不放 NAV 數值**）。"""

    code: str
    a_date: str
    b_date: str

    def __post_init__(self) -> None:
        _need(isinstance(self.code, str) and self.code in CONFLICT_CODES, "code", "a known conflict code", self.code)
        _need(_is_date(self.a_date), "a_date", "ISO date", self.a_date)
        _need(_is_date(self.b_date), "b_date", "ISO date", self.b_date)


@dataclass(frozen=True)
class NavSummaryView:
    """淨值區。`nav_value` 只在 `VERIFIED` 時存在（結構性不變式）。"""

    display: NavDisplay
    reason_codes: Tuple[str, ...] = ()
    nav_value: Optional[str] = None            # 來源層已格式化的字串（renderer 不算）
    ccy: Optional[str] = None                  # 淨值的幣別（僅 VERIFIED 才與 NAV 併列）
    nav_date: Optional[str] = None             # 觀測日
    source_label: Optional[str] = None
    cache_updated_at: Optional[str] = None     # 快取更新時間（ISO 日期）
    supplier_fetched_at: Optional[str] = None  # 原始供應者擷取時間；None＝未知（不得以 cache_updated_at 代填）
    ccy_declared_at: Optional[str] = None      # 幣別自報頁的擷取時間（不得以 NAV 的時間代填）
    ccy_declared: Optional[str] = None         # 自報幣別（級別未核證時只作「自報」呈現，不視為 NAV 幣別）
    time_sources_differ: bool = False
    conflicts: Tuple[ConflictDiag, ...] = ()
    content_tier: str = "T1"                   # T1＝可列診斷日期值（合成案）；T0＝只列結構（真實材料待裁）

    def __post_init__(self) -> None:
        _need(isinstance(self.display, NavDisplay), "display", "NavDisplay", self.display)
        _need(isinstance(self.reason_codes, tuple) and all(isinstance(r, str) and r in NAV_REASONS for r in self.reason_codes),
              "reason_codes", "tuple of known reason codes", self.reason_codes)
        _need(len(set(self.reason_codes)) == len(self.reason_codes), "reason_codes", "unique codes", self.reason_codes)
        _need(isinstance(self.conflicts, tuple) and all(isinstance(c, ConflictDiag) for c in self.conflicts), "conflicts", "tuple of ConflictDiag", self.conflicts)
        _need(isinstance(self.time_sources_differ, bool), "time_sources_differ", "bool", self.time_sources_differ)
        _need(self.content_tier in ("T0", "T1"), "content_tier", "T0 or T1", self.content_tier)
        for name in ("nav_value", "ccy", "source_label", "ccy_declared"):
            _opt(getattr(self, name), _is_text, name, "short text")
        _opt(self.nav_date, _is_date, "nav_date", "ISO date")                      # 觀測日：維持 date 契約
        for name in ("cache_updated_at", "supplier_fetched_at", "ccy_declared_at"):  # 擷取型時間：日期或帶 Z 的時間戳，原值保留
            _opt(getattr(self, name), _is_stamp, name, "ISO date or Z timestamp")
        d = self.display
        if self.nav_value is not None:
            _need(d is NavDisplay.VERIFIED, "nav_value", "None unless the display is verified", self.nav_value)
        if d is NavDisplay.VERIFIED:
            for name in ("nav_value", "ccy", "nav_date", "source_label", "cache_updated_at"):
                _need(getattr(self, name) is not None, name, "present when verified", None)
            _need(self.reason_codes == () and self.conflicts == (), "reason_codes", "empty when verified", self.reason_codes)
        elif d is NavDisplay.WITHHELD_CONFLICT:
            _need(len(self.conflicts) >= 1, "conflicts", "non-empty when withheld for conflict", self.conflicts)
            _need("input_conflict" in self.reason_codes, "reason_codes", "contains input_conflict when withheld for conflict", self.reason_codes)
        elif d is NavDisplay.WITHHELD_NOT_ADMITTED:
            _need(self.conflicts == (), "conflicts", "empty when withheld as not admitted", self.conflicts)
            _need(len(self.reason_codes) >= 1 and "input_conflict" not in self.reason_codes, "reason_codes",
                  "non-empty and without input_conflict when withheld as not admitted", self.reason_codes)
        else:
            _need(self.conflicts == () and self.reason_codes == (), "reason_codes", "empty when the nav is missing", self.reason_codes)
            for name in ("ccy", "nav_date", "source_label"):
                _need(getattr(self, name) is None, name, "None when the nav is missing", getattr(self, name))
        if d is not NavDisplay.VERIFIED:
            _need(self.ccy is None and self.nav_date is None, "ccy", "None unless verified (declared currency goes in ccy_declared)", self.ccy)


@dataclass(frozen=True)
class MetricView:
    """一項判定的**已判定結果**。符號只由 `kind` 決定；`evidence` 是來源層格式化好的（標籤, 值）字串，renderer 照放。"""

    kind: MetricKind
    reason_code: Optional[str] = None
    evidence: Tuple[Tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        _need(isinstance(self.kind, MetricKind), "kind", "MetricKind", self.kind)
        _need(isinstance(self.evidence, tuple) and all(isinstance(p, tuple) and len(p) == 2 and _is_text(p[0]) and _is_text(p[1]) for p in self.evidence),
              "evidence", "tuple of (label, value) short texts", self.evidence)
        if self.kind is MetricKind.UNDETERMINED:
            _need(isinstance(self.reason_code, str) and self.reason_code in METRIC_REASONS, "reason_code", "a known metric reason when undetermined", self.reason_code)
        else:
            _need(self.reason_code is None, "reason_code", "None unless undetermined", self.reason_code)
        if self.kind in (MetricKind.PASS_EVIDENCED, MetricKind.FAIL_EVIDENCED):
            _need(len(self.evidence) >= 1, "evidence", "non-empty for an evidenced result", self.evidence)


@dataclass(frozen=True)
class JudgementView:
    three_three_three: MetricView
    eating_principal: MetricView
    dividend_status: DividendStatus

    def __post_init__(self) -> None:
        _need(isinstance(self.three_three_three, MetricView), "three_three_three", "MetricView", self.three_three_three)
        _need(isinstance(self.eating_principal, MetricView), "eating_principal", "MetricView", self.eating_principal)
        _need(isinstance(self.dividend_status, DividendStatus), "dividend_status", "DividendStatus", self.dividend_status)
        _need(self.three_three_three.kind is not MetricKind.FACT_NO_DIVIDEND, "three_three_three", "not a dividend fact", self.three_three_three)
        # 吃本金與配息狀態不得互相頂替：事實項 ⇔ 已證實無配息；未取得配息 ⇒ 吃本金只能「無法判定」。
        _need((self.eating_principal.kind is MetricKind.FACT_NO_DIVIDEND) == (self.dividend_status is DividendStatus.CONFIRMED_NONE),
              "eating_principal", "a no-dividend fact exactly when the dividend status is confirmed-none", self.eating_principal)
        if self.dividend_status is DividendStatus.MISSING:
            _need(self.eating_principal.kind is MetricKind.UNDETERMINED, "eating_principal", "undetermined when dividends are missing", self.eating_principal)


@dataclass(frozen=True)
class ExpNavView:
    """sibling 聚合：淨值區＋判定區＋（不影響主畫面的）AI 使用旗標。"""

    nav: NavSummaryView
    judgement: JudgementView
    ai_usable: bool = False

    def __post_init__(self) -> None:
        _need(isinstance(self.nav, NavSummaryView), "nav", "NavSummaryView", self.nav)
        _need(isinstance(self.judgement, JudgementView), "judgement", "JudgementView", self.judgement)
        _need(isinstance(self.ai_usable, bool), "ai_usable", "bool", self.ai_usable)
        if self.nav.display is not NavDisplay.VERIFIED:
            # 層 F：基金級扣下 ⇒ 兩項判定一律無法判定（不計算、不顯示結論）；無配息事實亦不顯示。
            for name in ("three_three_three", "eating_principal"):
                _need(getattr(self.judgement, name).kind is MetricKind.UNDETERMINED, name, "undetermined when the nav is withheld or missing", None)
            _need(self.judgement.dividend_status is not DividendStatus.CONFIRMED_NONE, "dividend_status",
                  "not confirmed-none when the nav is withheld or missing", None)
