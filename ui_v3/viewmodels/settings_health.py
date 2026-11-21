# -*- coding: utf-8 -*-
"""⚙️ 設定→資料健康度 第一切片的 view model（BL-0540 前置；**隔離、未掛載**；純 Python、frozen、建構時驗證）。

定位（先講清楚，避免被讀成「健康度已完成」）：
- 本檔**只承載事實與代碼**，不放任何畫面字樣（類別層狀態詞全部待客戶定字，見
  `docs/evidence/ui_b_settings_health_wireframe_2026_11_20/README.md` §5-A）；沒有 renderer、沒有 registry 變更。
- 輸入是已存在的 `DomainStatus` 列（🌍 `MarketPageModel.statuses`），**不取數、不計算新鮮度、不讀現在時間**。
  補上 `ShellStatus` 缺的兩件事（`tests/ui_v3/test_ui_v3_status_rows_failed_vs_not_evaluated_offline.py` 自陳的缺口）：
  1. 五種狀態各自計數（ok／missing／failed／not_configured／undetermined），餘數不再混在一起；
  2. **範圍揭露**：八個類別中哪些有可顯示的資料狀態、哪些是未接線／未評估／待裁示——
     沒有資料的類別 `tally is None`（Missing ≠ 0：不是「0 項成功」，是「無從計數」）。
- **刻意不提供任何「整體健康／整體 ok」欄位**：覆蓋範圍只有部分類別時，任何單一總燈都會被讀成全站結論（bl0540 R4）。
- 類別覆蓋（`coverage`）由呼叫端注入、本檔不寫死：哪個類別「未接線」是需要證據的事實，不是本檔能宣稱的（fail-closed：
  八類必須全部明確給值，缺任何一類就拒絕，不預設為「正常」或「已覆蓋」）。
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Mapping, Optional, Sequence, Tuple

from shared.ui_semantics import rules as _rules

from ui_v3.viewmodels.common import (
    STATUS_FAILED,
    STATUS_MISSING,
    STATUS_OK,
    STATUS_UNDETERMINED,
    optional_text,
    require_key,
)
from ui_v3.viewmodels.market_page import DomainStatus
from ui_v3.viewmodels.shell import ShellStatus

__all__ = (
    "SNAPSHOT_KEY", "HealthSnapshot", "DEFAULT_ROW_CATEGORY", "PHASE_1A_COVERAGE", "build_from_snapshot",
    "HEALTH_CATEGORY_KEYS", "COVERAGE_KINDS", "COVERAGE_COVERED", "COVERAGE_NOT_WIRED",
    "COVERAGE_NOT_EVALUATED", "COVERAGE_PENDING_RULING", "HEALTH_STATES",
    "STATE_OK", "STATE_MISSING", "STATE_FAILED", "STATE_NOT_CONFIGURED", "STATE_UNDETERMINED",
    "GAP_FIELDS", "StateTally", "HealthRow", "CategoryHealth", "SettingsHealthModel", "build_settings_health",
)

# 八個類別（線框 §2 的類別層；順序固定，輸出順序不隨輸入改變）。名稱是內部鍵，不是畫面字樣。
HEALTH_CATEGORY_KEYS = ("market", "rates", "fund", "nav", "holdings", "dividend", "fx", "macro_cycle")

COVERAGE_COVERED = "covered"                # 有可顯示的資料狀態列
COVERAGE_NOT_WIRED = "not_wired"            # 未接線（沒有 producer／入口）
COVERAGE_NOT_EVALUATED = "not_evaluated"    # 有資料入口但本頁尚未判定
COVERAGE_PENDING_RULING = "pending_ruling"  # 判定規則待客戶裁示
COVERAGE_KINDS = (COVERAGE_COVERED, COVERAGE_NOT_WIRED, COVERAGE_NOT_EVALUATED, COVERAGE_PENDING_RULING)

STATE_OK = "ok"
STATE_MISSING = "missing"
STATE_FAILED = "failed"
STATE_NOT_CONFIGURED = "not_configured"   # 「尚未設定」不是取數失敗（44 之十二其二第 1 條）：不計入 failed
STATE_UNDETERMINED = "undetermined"       # 未評估／無法判定：不是成功、也不是失敗
HEALTH_STATES = (STATE_OK, STATE_MISSING, STATE_FAILED, STATE_NOT_CONFIGURED, STATE_UNDETERMINED)

# ok 列理應帶的證據欄位；缺哪個就如實列出（不補值、不以其他欄位代替）。
GAP_FIELDS = ("source", "as_of", "fetched_at")


# ── Phase 1A（客戶 2026-11-21 裁示 #7056447977）：同一 session 的市場／利率快照 ─────────────────
SNAPSHOT_KEY = "uv3_health_snapshot"   # st.session_state 的鍵：每個使用者 session 各自一份，不進全域 cache

# 🌍 五條序列 → 類別的暫用對映（線框讀法；客戶只授權「市場與利率」，不是全站）。
DEFAULT_ROW_CATEGORY = {"taiex": "market", "sp500": "market", "vix": "market", "us10y": "rates", "us2y": "rates"}
# 本頁只評估市場與利率；其餘六類「本頁尚未評估」——這是本頁範圍的事實，不宣稱它們是否接線。
PHASE_1A_COVERAGE = {k: (COVERAGE_COVERED if k in ("market", "rates") else COVERAGE_NOT_EVALUATED)
                     for k in HEALTH_CATEGORY_KEYS}


@dataclass(frozen=True)
class HealthSnapshot:
    """市場頁**已產生**的一份狀態快照（唯讀；設定頁只讀它、不取數）。不含時間戳以外的任何衍生值；不補現在時間。"""

    statuses: Tuple[DomainStatus, ...]
    shell_status: ShellStatus

    def __post_init__(self) -> None:
        if not isinstance(self.statuses, tuple) or not self.statuses or not all(isinstance(r, DomainStatus) for r in self.statuses):
            raise TypeError("statuses 必須是非空的 DomainStatus tuple")
        if not isinstance(self.shell_status, ShellStatus):
            raise TypeError("shell_status 必須是 ShellStatus")


def build_from_snapshot(snapshot: HealthSnapshot) -> "SettingsHealthModel":
    """快照 → 健康度模型（純函式；同快照同輸出）。"""
    return build_settings_health(snapshot.statuses, row_category=DEFAULT_ROW_CATEGORY, coverage=PHASE_1A_COVERAGE)


def _blank_to_none(value: Optional[str]) -> Optional[str]:
    return None if value is None or not str(value).strip() else value


def _state_of(row: DomainStatus) -> str:
    """`DomainStatus` → 五態。不認得的 status 一律拒絕（fail-closed，不預設為 ok 也不預設為 failed）。"""
    if row.status == STATUS_OK:
        return STATE_OK
    if row.status == STATUS_MISSING:
        return STATE_MISSING
    if row.status == STATUS_UNDETERMINED:
        return STATE_UNDETERMINED
    if row.status == STATUS_FAILED:
        return STATE_NOT_CONFIGURED if row.reason_code == _rules.REASON_NOT_CONFIGURED else STATE_FAILED
    raise ValueError(f"無法對映的 status：{row.status!r}")


def _gaps_of(row: DomainStatus, state: str) -> Tuple[str, ...]:
    """只有 ok 列才談證據缺口：ok 卻缺來源／資料日／取得時間 → 如實列出。非 ok 列沒有「應有」的證據，缺口為空。"""
    if state != STATE_OK:
        return ()
    return tuple(name for name in GAP_FIELDS if getattr(row, name) is None)


@dataclass(frozen=True)
class StateTally:
    """五態計數。五個數字互斥、相加＝`total`；沒有「其他」「餘數」欄。"""

    ok: int
    missing: int
    failed: int
    not_configured: int
    undetermined: int

    def __post_init__(self) -> None:
        for name in HEALTH_STATES:
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} 必須是非負整數，收到 {value!r}")

    @property
    def total(self) -> int:
        return self.ok + self.missing + self.failed + self.not_configured + self.undetermined


@dataclass(frozen=True)
class HealthRow:
    """② 逐來源／序列的一列。`as_of`／`fetched_at`／`source` 缺值保留 None，不補現在、不以他欄代替。"""

    key: str
    category_key: str
    label_key: str
    state: str
    reason_code: Optional[str]
    source: Optional[str]
    as_of: Optional[str]
    fetched_at: Optional[str]
    gaps: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        require_key("key", self.key)
        require_key("label_key", self.label_key)
        if self.category_key not in HEALTH_CATEGORY_KEYS:
            raise ValueError(f"category_key 必須在 {HEALTH_CATEGORY_KEYS}，收到 {self.category_key!r}")
        if self.state not in HEALTH_STATES:
            raise ValueError(f"state 必須在 {HEALTH_STATES}，收到 {self.state!r}")
        if self.reason_code is not None:
            require_key("reason_code", self.reason_code)
        if self.state != STATE_OK and self.reason_code is None:
            raise ValueError(f"state={self.state} 必須帶 reason_code")
        if (self.state == STATE_NOT_CONFIGURED) != (self.reason_code == _rules.REASON_NOT_CONFIGURED):
            raise ValueError("not_configured 狀態與原因碼必須同時成立（尚未設定 ≠ 取數失敗）")
        for name in GAP_FIELDS:
            optional_text(name, getattr(self, name))
        if not isinstance(self.gaps, tuple) or any(g not in GAP_FIELDS for g in self.gaps):
            raise ValueError(f"gaps 必須是 {GAP_FIELDS} 的子集 tuple")
        expected = tuple(n for n in GAP_FIELDS if getattr(self, n) is None) if self.state == STATE_OK else ()
        if self.gaps != expected:
            raise ValueError(f"gaps 必須如實反映 ok 列缺哪些證據欄位：應為 {expected}，收到 {self.gaps}")


@dataclass(frozen=True)
class CategoryHealth:
    """① 一個類別。`tally is None`＝這個類別沒有可計數的資料狀態列（未接線／未評估／待裁示），**不是 0**。"""

    category_key: str
    coverage: str
    tally: Optional[StateTally]

    def __post_init__(self) -> None:
        if self.category_key not in HEALTH_CATEGORY_KEYS:
            raise ValueError(f"category_key 必須在 {HEALTH_CATEGORY_KEYS}，收到 {self.category_key!r}")
        if self.coverage not in COVERAGE_KINDS:
            raise ValueError(f"coverage 必須在 {COVERAGE_KINDS}，收到 {self.coverage!r}")
        if self.coverage == COVERAGE_COVERED:
            if not isinstance(self.tally, StateTally) or self.tally.total < 1:
                raise ValueError("covered 的類別必須有至少一列的 StateTally")
        elif self.tally is not None:
            raise ValueError("非 covered 的類別不得帶 tally（沒有資料 ≠ 0 項）")


@dataclass(frozen=True)
class SettingsHealthModel:
    """⚙️ 資料健康度（第一切片）。

    - `categories`：八類固定順序；`rows`：輸入順序（只含 covered 類別的列）。
    - 沒有整體／全站層級欄位（見檔頭）；`freshness_state` 恆為 `undetermined`（門檻待 Threshold Gate）。
    """

    categories: Tuple[CategoryHealth, ...]
    rows: Tuple[HealthRow, ...]
    freshness_state: str = "undetermined"

    def __post_init__(self) -> None:
        if tuple(c.category_key for c in self.categories) != HEALTH_CATEGORY_KEYS:
            raise ValueError(f"categories 必須恰為 {HEALTH_CATEGORY_KEYS}（順序固定）")
        if self.freshness_state != "undetermined":
            raise ValueError("門檻未裁示前 freshness_state 只能是 undetermined")
        keys = [r.key for r in self.rows]
        if len(set(keys)) != len(keys):
            raise ValueError("rows 的 key 不得重複")
        for cat in self.categories:
            mine = [r for r in self.rows if r.category_key == cat.category_key]
            if cat.coverage != COVERAGE_COVERED:
                if mine:
                    raise ValueError(f"類別 {cat.category_key} 非 covered，卻有資料列")
                continue
            recount = StateTally(*(sum(1 for r in mine if r.state == s) for s in HEALTH_STATES))
            if recount != cat.tally:
                raise ValueError(f"類別 {cat.category_key} 的 tally 與資料列不符")

    @property
    def covered_keys(self) -> Tuple[str, ...]:
        return tuple(c.category_key for c in self.categories if c.coverage == COVERAGE_COVERED)

    @property
    def uncovered_keys(self) -> Tuple[str, ...]:
        return tuple(c.category_key for c in self.categories if c.coverage != COVERAGE_COVERED)


def build_settings_health(
    statuses: Sequence[DomainStatus],
    *,
    row_category: Mapping[str, str],
    coverage: Mapping[str, str],
) -> SettingsHealthModel:
    """由 `DomainStatus` 列組出健康度模型。純函式：同輸入同輸出，不讀時間、不取數。

    - `coverage` 必須恰好給齊八類（缺一類或多一類都拒絕）；
    - 每一列都必須在 `row_category` 有對映，且對映的類別必須是 covered（不替未對映的列猜類別、不丟棄列）；
    - `row_category` 多出來沒用到的鍵不影響結果（它不產生任何資料）。
    """
    if set(coverage) != set(HEALTH_CATEGORY_KEYS):
        raise ValueError(f"coverage 必須恰好涵蓋 {HEALTH_CATEGORY_KEYS}，收到 {tuple(coverage)}")
    for category, kind in coverage.items():
        if kind not in COVERAGE_KINDS:
            raise ValueError(f"coverage[{category!r}] 必須在 {COVERAGE_KINDS}，收到 {kind!r}")
    rows = []
    for status in statuses:
        if not isinstance(status, DomainStatus):
            raise TypeError("statuses 必須是 DomainStatus 的序列")
        if status.key not in row_category:
            raise ValueError(f"資料列 {status.key!r} 沒有類別對映（不替它猜類別、也不丟棄）")
        category = row_category[status.key]
        if category not in HEALTH_CATEGORY_KEYS:
            raise ValueError(f"資料列 {status.key!r} 的類別 {category!r} 不在 {HEALTH_CATEGORY_KEYS}")
        if coverage[category] != COVERAGE_COVERED:
            raise ValueError(f"資料列 {status.key!r} 屬於非 covered 的類別 {category!r}（覆蓋宣告與資料互相矛盾）")
        # 空字串／全空白＝沒有值（缺值），一律視為 None；不補值、不讓空字串讓整頁崩潰。
        status = dataclasses.replace(status, source=_blank_to_none(status.source), as_of=_blank_to_none(status.as_of),
                                     fetched_at=_blank_to_none(status.fetched_at))
        state = _state_of(status)
        rows.append(HealthRow(status.key, category, status.label_key, state, status.reason_code, status.source,
                              status.as_of, status.fetched_at, _gaps_of(status, state)))
    categories = []
    for key in HEALTH_CATEGORY_KEYS:
        if coverage[key] != COVERAGE_COVERED:
            categories.append(CategoryHealth(key, coverage[key], None))
            continue
        mine = [r for r in rows if r.category_key == key]
        categories.append(CategoryHealth(key, COVERAGE_COVERED,
                                         StateTally(*(sum(1 for r in mine if r.state == s) for s in HEALTH_STATES))))
    return SettingsHealthModel(tuple(categories), tuple(rows))
