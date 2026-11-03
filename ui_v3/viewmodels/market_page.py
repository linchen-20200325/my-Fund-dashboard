# -*- coding: utf-8 -*-
"""🌍 市場與趨勢頁的 view model（BL-0536 rendering 批；純 Python、frozen、建構時驗證；無 streamlit／services）。

由 `ui_v3/adapters/market_page.py` 從既有正式資料層結果組出，由 `ui_v3/pages/mkt.py` 渲染。本層**不放畫面字樣**
（暫時字樣在 `preview_wording.py`，已核准字樣在 `shared/ui_semantics/rules.py`），只放代碼與事實：
Missing ≠ 0（缺值一律 `None`＋原因代碼）、取數失敗（`failed`）與缺資料（`missing`）分開、無法判定（`undetermined`）另列。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from ui_v3.viewmodels.common import (
    STATUS_FAILED,
    STATUS_MISSING,
    STATUS_OK,
    STATUS_UNDETERMINED,
    optional_text,
    require_key,
    require_number_or_none,
    require_text,
)
from ui_v3.viewmodels.components import ChartCard, ChartPoint

VIEW_COMPARE = "compare"
VIEW_VIX = "vix"
VIEW_US10Y = "us10y"
VIEW_US2Y = "us2y"
PRIMARY_VIEWS = (VIEW_COMPARE, VIEW_VIX, VIEW_US10Y, VIEW_US2Y)
DEFAULT_PRIMARY_VIEW = VIEW_COMPARE

RATES_TERM = "term_spread_pct"
RATES_CREDIT = "credit_spread_pct"
RATES_POLICY = "policy_rate_pct"
RATES_KEYS = (RATES_TERM, RATES_CREDIT, RATES_POLICY)
DEFAULT_RATES_KEY = RATES_TERM

_FACT_STATUSES = (STATUS_OK, STATUS_MISSING, STATUS_FAILED, STATUS_UNDETERMINED)


def _check_status(status: str, reason_code: Optional[str], value: Optional[float]) -> None:
    if status not in _FACT_STATUSES:
        raise ValueError(f"status 必須在 {_FACT_STATUSES}，收到 {status!r}")
    if reason_code is not None:
        require_key("reason_code", reason_code)
    if status != STATUS_OK and reason_code is None:
        raise ValueError(f"status={status} 必須帶 reason_code")
    if status == STATUS_OK and value is None:
        raise ValueError("status=ok 必須有值（缺值請用 missing／failed 並帶原因）")
    if status != STATUS_OK and value is not None:
        raise ValueError("非 ok 不得攜帶數值（Missing ≠ 0）")


@dataclass(frozen=True)
class EvidenceChange:
    """首屏「重要依據」一條序列的期間漲跌（無日期；Q4 A、Q5 B）。`period_change` 單位＝百分點（＝% 漲跌，基準同圖）。"""

    key: str
    status: str
    reason_code: Optional[str]
    period_change: Optional[float]

    def __post_init__(self) -> None:
        require_key("key", self.key)
        require_number_or_none("period_change", self.period_change)
        _check_status(self.status, self.reason_code, self.period_change)


@dataclass(frozen=True)
class SeriesNote:
    """圖卡下一條序列的資料日一行（日期與經過天數只在圖卡出現）。

    `elapsed_days` 可為負（取得時間早於觀測日，資料不一致）——照實保留，由呈現層寫成不適用，不得當成新。
    """

    key: str
    status: str
    reason_code: Optional[str]
    as_of: Optional[str]
    elapsed_days: Optional[int]
    source: Optional[str]
    fetched_at: Optional[str]

    def __post_init__(self) -> None:
        require_key("key", self.key)
        optional_text("as_of", self.as_of)
        optional_text("source", self.source)
        optional_text("fetched_at", self.fetched_at)
        if self.status not in _FACT_STATUSES:
            raise ValueError(f"status 必須在 {_FACT_STATUSES}，收到 {self.status!r}")
        if self.status != STATUS_OK and self.reason_code is None:
            raise ValueError(f"status={self.status} 必須帶 reason_code")
        if self.elapsed_days is not None and (isinstance(self.elapsed_days, bool) or not isinstance(self.elapsed_days, int)):
            raise ValueError("elapsed_days 必須是 int 或 None")
        if self.elapsed_days is not None and self.as_of is None:
            raise ValueError("沒有資料日就沒有經過天數")


@dataclass(frozen=True)
class SecondaryCard:
    """Secondary 緊湊卡（VIX、利率與信用）：最新值＋資料日＋近 1Y 迷你線。非 ok 時無值、無迷你線。"""

    key: str
    status: str
    reason_code: Optional[str]
    value: Optional[float]
    unit: Optional[str]
    as_of: Optional[str]
    elapsed_days: Optional[int]
    source: Optional[str]
    spark: Tuple[ChartPoint, ...] = ()
    spark_status: Optional[str] = None  # None＝有迷你線或不適用；"insufficient"＝近 1Y 涵蓋不足

    def __post_init__(self) -> None:
        require_key("key", self.key)
        require_number_or_none("value", self.value)
        _check_status(self.status, self.reason_code, self.value)
        if self.status == STATUS_OK:
            if self.as_of is None or self.source is None or self.unit is None:
                raise ValueError("ok 的 Secondary 卡必須帶 as_of／source／unit")
        elif self.spark:
            raise ValueError("非 ok 不得有迷你線（Missing ≠ 0）")
        if not isinstance(self.spark, tuple) or not all(isinstance(p, ChartPoint) for p in self.spark):
            raise TypeError("spark 必須是 ChartPoint 的 tuple")
        if self.elapsed_days is not None and (isinstance(self.elapsed_days, bool) or not isinstance(self.elapsed_days, int)):
            raise ValueError("elapsed_days 必須是 int 或 None")


@dataclass(frozen=True)
class EvidenceFact:
    """依據卡的一個事實：觀測值（不判定）或缺值。`label_key` 對 `preview_wording` 的鍵。"""

    label_key: str
    status: str
    reason_code: Optional[str]
    value: Optional[float]
    unit: Optional[str]
    as_of: Optional[str]

    def __post_init__(self) -> None:
        require_key("label_key", self.label_key)
        require_number_or_none("value", self.value)
        _check_status(self.status, self.reason_code, self.value)
        if self.status == STATUS_OK and (self.as_of is None or self.unit is None):
            raise ValueError("ok 的事實必須帶 as_of 與 unit")


@dataclass(frozen=True)
class EvidenceCard:
    """依據卡（≤3；沒有正式規則 → 不帶 rule_ref、不下判斷）。"""

    code: str
    title_key: str
    facts: Tuple[EvidenceFact, ...]

    def __post_init__(self) -> None:
        require_text("code", self.code)
        require_key("title_key", self.title_key)
        if not isinstance(self.facts, tuple) or not self.facts or not all(isinstance(f, EvidenceFact) for f in self.facts):
            raise TypeError("facts 必須是非空的 EvidenceFact tuple")


@dataclass(frozen=True)
class DomainStatus:
    """▸ 各項資料狀態的一列（原因代碼；失敗原文不上畫面，44 P0-①）。"""

    key: str
    label_key: str
    status: str
    reason_code: Optional[str]
    source: Optional[str]
    as_of: Optional[str]
    fetched_at: Optional[str]

    def __post_init__(self) -> None:
        require_key("key", self.key)
        require_key("label_key", self.label_key)
        if self.status not in _FACT_STATUSES:
            raise ValueError(f"status 必須在 {_FACT_STATUSES}，收到 {self.status!r}")
        if self.status != STATUS_OK and self.reason_code is None:
            raise ValueError(f"status={self.status} 必須帶 reason_code")


@dataclass(frozen=True)
class MarketPageModel:
    """🌍 頁的完整 view model。

    - `view`：Primary 檢視（`PRIMARY_VIEWS`）；`period`：與圖與首屏漲跌相同的期間。
    - `evidence_changes`：首屏重要依據（兩條序列的期間漲跌；與圖同一個 `NormalizedComparison`）。
    - `evidence_comparable`／`comparison_mode`：首屏依據所用的 `NormalizedComparison`（與 Primary 檢視無關，永遠是 TAIEX vs S&P 500）；
      只有兩條在同一基準日比較時 `evidence_comparable` 才為 True；單序列／退回單序列的漲跌不是比較。
    - `primary_card`：歸一化比較圖卡（`view == compare`）或單序列圖卡；`primary_notes`：圖下各序列資料日一行。
    - `primary_unit`：單序列檢視的單位（比較檢視為 None）。
    - `secondary`：至多 2 張（VIX 在 Primary 為 VIX 時讓位——執行組讀法，可被客戶推翻）。
    - `freshness_state`：恆為 `undetermined`（門檻未裁示；首屏只一枚 chip）。
    """

    period: str
    view: str
    evidence_comparable: bool
    comparison_mode: str
    evidence_changes: Tuple[EvidenceChange, ...]
    primary_card: ChartCard
    primary_notes: Tuple[SeriesNote, ...]
    primary_unit: Optional[str]
    secondary: Tuple[SecondaryCard, ...]
    rates_key: str
    evidence_cards: Tuple[EvidenceCard, ...]
    missing: Tuple[DomainStatus, ...]
    statuses: Tuple[DomainStatus, ...]
    freshness_state: str = "undetermined"

    def __post_init__(self) -> None:
        if self.view not in PRIMARY_VIEWS:
            raise ValueError(f"view 必須在 {PRIMARY_VIEWS}，收到 {self.view!r}")
        if self.rates_key not in RATES_KEYS:
            raise ValueError(f"rates_key 必須在 {RATES_KEYS}，收到 {self.rates_key!r}")
        if not isinstance(self.primary_card, ChartCard):
            raise TypeError("primary_card 必須是 ChartCard")
        if self.freshness_state != "undetermined":
            raise ValueError("門檻未裁示前 freshness_state 只能是 undetermined")
        if len(self.evidence_cards) > 3:
            raise ValueError("依據卡至多 3 張（UI-12 (3)）")
        if len(self.secondary) > 2:
            raise ValueError("Secondary 至多 2 張（S&P 卡已移除，Q3 A）")
        if self.view == VIEW_VIX and any(c.key == VIEW_VIX for c in self.secondary):
            raise ValueError("Primary 檢視為 VIX 時 VIX 卡必須讓位（D1：Secondary 不複製 Primary）")
        if (self.view == VIEW_COMPARE) != self.primary_card.normalized:
            raise ValueError("只有比較檢視是歸一化圖卡")
        if self.evidence_comparable and self.comparison_mode != "pair":
            raise ValueError("只有 pair 模式可以是比較")
