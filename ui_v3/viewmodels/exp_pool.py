# -*- coding: utf-8 -*-
"""S2-T0 選股池來源 view model 與 EXP 計數組裝（純 Python，只用標準函式庫與 S0 `exp_counts`）。

授權與邊界（`DEC-2026-11-17-04`，補充 `DEC-2026-11-14-08`；僅內部唯讀切片）：
- 本檔**不取數、不讀任何持久層、不碰 secrets 與環境變數、不發網路請求、不寫入任何東西**；
  暫時條件只活在函式參數裡，函式結束即消失。
- 本檔**不是**頁面，也**不是**資料接線：輸入全由呼叫端注入。注入測試輸入不等於資料接線，
  不得以此宣稱「🔍 找基金」頁面或選股池功能已完成。
- 選股池代碼是**不透明字串**：只驗證它是非空白的 `str`，原樣保留（大小寫、空白、全形、類 ISIN 字串皆不動），
  不解析、不正規化、不比對、不當基金身份、**不冒用 R-ID-1**（R-ID-1 僅限持倉「基金代號」欄，明文不含選股池代碼）。

四個互斥狀態（`PoolState`）：
- `OK`：來源成功且有代碼；
- `EMPTY`：來源成功但沒有任何代碼（選股池是空的——**不併入**「沒有符合的基金」）；
- `FAILED`：來源失敗（含 L2 回報的冷卻中，以及呼叫端注入的取數函式拋出例外）；
- `UNAVAILABLE`：L2 回報 `pool_not_cloud`。**涵蓋「未設定」與「憑證無法使用」兩種成因，L2 分不出來，
  本層也不擅自區分或確定原因**（正式字樣待對應 Gate）。

洩漏面（結構上不帶）：view model 只有 `state`／`codes`／固定類別碼 `reason_code`／`read_at`（ISO 字串或 None）。
**沒有** backend 名稱、**沒有**原始訊息、沒有例外字串；驗證失敗的例外訊息只含欄位名與型別名，不回顯任何收到的值。

`build_exp_counts` 的三態組合規則（任一不符合→不符合；否則任一無法判定→無法判定；否則符合）**只用來驗證
EXP-0／2／7 彼此一致**，輸入的三態是呼叫端的測試輸入，**不是正式篩選判準**；
⛔ 不得把這個組合函式搬進 production 當篩選實作（正式實作是 L2 `apply_rules_tristate`，本檔不 import 它）。
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Optional, Sequence

from ui_v3.viewmodels.exp_counts import (
    TEXT_NO_CONDITION,
    ExpCountsConclusion,
    exp0_conclusion,
    require_count,
    verify_exp2_row_count,
    verify_exp7_last_row,
)

__all__ = (
    "PoolContractError", "PoolState", "PoolSourceView", "Exp2Row", "Exp7Row", "ExpCountsView",
    "REASON_SOURCE_FAILED", "REASON_SOURCE_COOLING", "REASON_LOADER_RAISED", "REASON_POOL_UNAVAILABLE",
    "TRI_MATCH", "TRI_NO_MATCH", "TRI_UNDETERMINED",
    "COUNTS_COUNTED", "COUNTS_NO_CONDITIONS", "COUNTS_POOL_EMPTY", "COUNTS_POOL_UNAVAILABLE", "COUNTS_POOL_FAILED",
    "build_exp_counts",
)


class PoolContractError(ValueError):
    """選股池契約不符（fail-closed）。訊息只含欄位名與型別名，**絕不回顯收到的值**（值可能是秘密、網址或例外字串）。"""


class PoolState(Enum):
    OK = "ok"
    EMPTY = "empty"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"


# 固定類別碼（key 形；不是訊息、不上畫面；正式字樣待 Gate）。
REASON_SOURCE_FAILED = "source_failed"          # L2 回報 failed（非冷卻）
REASON_SOURCE_COOLING = "source_cooling"        # L2 回報 failed 且處於冷卻中
REASON_LOADER_RAISED = "loader_raised"          # 呼叫端注入的取數函式拋出例外（例外字串一律丟棄）
REASON_POOL_UNAVAILABLE = "pool_unavailable"    # L2 回報 pool_not_cloud（未設定／憑證無法使用，不區分）

_FAILED_REASONS = frozenset({REASON_SOURCE_FAILED, REASON_SOURCE_COOLING, REASON_LOADER_RAISED})
_UNAVAILABLE_REASONS = frozenset({REASON_POOL_UNAVAILABLE})

TRI_MATCH = "match"
TRI_NO_MATCH = "no_match"
TRI_UNDETERMINED = "undetermined"
_TRI_VALUES = frozenset({TRI_MATCH, TRI_NO_MATCH, TRI_UNDETERMINED})


def _kind(value: object) -> str:
    return type(value).__name__


def _need(ok: bool, field: str, expected: str, value: object) -> None:
    if not ok:
        raise PoolContractError(f"{field}: expected {expected}, got {_kind(value)}") from None


def _is_blank(code: object) -> bool:
    return not isinstance(code, str) or code.strip() == ""


@dataclass(frozen=True)
class PoolSourceView:
    """選股池來源的單一 view model。`codes` 為不透明字串、保序、已去重（以精確字串比對，大小寫不同＝不同代碼）。"""

    state: PoolState
    codes: tuple = ()
    reason_code: Optional[str] = None
    read_at: Optional[str] = None

    def __post_init__(self) -> None:
        _need(isinstance(self.state, PoolState), "state", "PoolState", self.state)
        _need(isinstance(self.codes, tuple), "codes", "tuple", self.codes)
        for index, code in enumerate(self.codes):
            _need(not _is_blank(code), f"codes[{index}]", "non-blank str", code)
        _need(len(set(self.codes)) == len(self.codes), "codes", "no duplicates", self.codes)
        if self.read_at is not None:
            _need(isinstance(self.read_at, str), "read_at", "ISO 8601 str or None", self.read_at)
            try:
                _dt.datetime.fromisoformat(self.read_at)
            except ValueError:
                raise PoolContractError("read_at: expected ISO 8601 str, got unparsable str") from None
        if self.state is PoolState.OK:
            _need(len(self.codes) > 0, "codes", "non-empty tuple when state is OK", self.codes)
            _need(self.reason_code is None, "reason_code", "None when state is OK", self.reason_code)
        elif self.state is PoolState.EMPTY:
            _need(len(self.codes) == 0, "codes", "empty tuple when state is EMPTY", self.codes)
            _need(self.reason_code is None, "reason_code", "None when state is EMPTY", self.reason_code)
        else:
            allowed = _FAILED_REASONS if self.state is PoolState.FAILED else _UNAVAILABLE_REASONS
            _need(len(self.codes) == 0, "codes", "empty tuple when source is not usable", self.codes)
            _need(self.read_at is None, "read_at", "None when source is not usable", self.read_at)
            _need(isinstance(self.reason_code, str) and self.reason_code in allowed,
                  "reason_code", "a known category code for this state", self.reason_code)

    @property
    def usable(self) -> bool:
        return self.state in (PoolState.OK, PoolState.EMPTY)


# ───────────────────────── EXP-0／2／7 組裝（測試輸入驅動；非正式篩選） ─────────────────────────

COUNTS_COUNTED = "counted"                      # 來源 OK 且有生效條件：N／M 與兩張表齊備
COUNTS_NO_CONDITIONS = "no_conditions"          # 來源 OK 且尚未設定條件：只有「尚未設定條件」，不展示 N／M
COUNTS_POOL_EMPTY = "pool_empty"                # 選股池是空的：不產生 N／M（不併入「沒有符合」）
COUNTS_POOL_UNAVAILABLE = "pool_unavailable"    # 來源不可用：不產生任何 N／M（不偽稱 0）
COUNTS_POOL_FAILED = "pool_failed"              # 來源失敗：不產生任何 N／M（不偽稱 0）
_COUNTS_STATUSES = (COUNTS_COUNTED, COUNTS_NO_CONDITIONS, COUNTS_POOL_EMPTY, COUNTS_POOL_UNAVAILABLE, COUNTS_POOL_FAILED)


@dataclass(frozen=True)
class Exp2Row:
    """EXP-2 一列：不透明代碼＋三態結論（只有 `match`／`undetermined` 會被列出；`no_match` 不列）。"""

    code: str
    outcome: str

    def __post_init__(self) -> None:
        _need(not _is_blank(self.code), "code", "non-blank str", self.code)
        _need(self.outcome in (TRI_MATCH, TRI_UNDETERMINED), "outcome", "match or undetermined", self.outcome)


@dataclass(frozen=True)
class Exp7Row:
    """EXP-7 一列：逐條件套用前／符合／無法判定（累計語意，與 L2 `apply_rules_tristate` 的 steps 一致）。"""

    condition_id: str
    before: int
    matched: int
    undetermined: int

    def __post_init__(self) -> None:
        _need(not _is_blank(self.condition_id), "condition_id", "non-blank str", self.condition_id)
        for name in ("before", "matched", "undetermined"):
            require_count(name, getattr(self, name))
        if self.matched + self.undetermined > self.before:
            raise PoolContractError("trajectory row: matched + undetermined exceeds before")


@dataclass(frozen=True)
class ExpCountsView:
    """EXP-0／2／7 的組裝結果。`status` 可識別不可用：非 `counted`／`no_conditions` 時**沒有任何 N／M**。"""

    status: str
    conditions_count: int
    conclusion: Optional[ExpCountsConclusion] = None
    rows: tuple = ()
    trajectory: tuple = ()

    def __post_init__(self) -> None:
        _need(self.status in _COUNTS_STATUSES, "status", "a known status", self.status)
        require_count("conditions_count", self.conditions_count)
        _need(isinstance(self.rows, tuple) and all(isinstance(r, Exp2Row) for r in self.rows), "rows", "tuple of Exp2Row", self.rows)
        _need(isinstance(self.trajectory, tuple) and all(isinstance(r, Exp7Row) for r in self.trajectory),
              "trajectory", "tuple of Exp7Row", self.trajectory)
        if self.status == COUNTS_COUNTED:
            _need(self.conditions_count > 0, "conditions_count", "positive when counted", self.conditions_count)
            _need(isinstance(self.conclusion, ExpCountsConclusion) and self.conclusion.counts_shown,
                  "conclusion", "ExpCountsConclusion with counts", self.conclusion)
            _need(len(self.trajectory) == self.conditions_count, "trajectory", "one row per condition", self.trajectory)
            n, m = self.conclusion.matched, self.conclusion.undetermined
            try:
                verify_exp2_row_count(len(self.rows), n, m)
                verify_exp7_last_row([(r.matched, r.undetermined) for r in self.trajectory], n, m)
            except ValueError:
                raise PoolContractError("EXP-0/2/7 are inconsistent with each other") from None
            _need(sum(1 for r in self.rows if r.outcome == TRI_MATCH) == n, "rows", "N matched rows", self.rows)
        elif self.status == COUNTS_NO_CONDITIONS:
            _need(self.conditions_count == 0, "conditions_count", "zero when no conditions", self.conditions_count)
            _need(isinstance(self.conclusion, ExpCountsConclusion) and not self.conclusion.counts_shown
                  and self.conclusion.text == TEXT_NO_CONDITION, "conclusion", "the no-condition conclusion", self.conclusion)
            _need(not self.rows and not self.trajectory, "rows", "empty when no conditions", self.rows)
        else:
            _need(self.conclusion is None, "conclusion", "None when the pool yields no counts", self.conclusion)
            _need(not self.rows and not self.trajectory, "rows", "empty when the pool yields no counts", self.rows)

    @property
    def counts_shown(self) -> bool:
        """是否有 N／M 可展示（只有 `counted`）。"""
        return self.status == COUNTS_COUNTED


def _condition_ids(conditions: object) -> tuple:
    _need(isinstance(conditions, (list, tuple)), "conditions", "list or tuple of str", conditions)
    for index, cid in enumerate(conditions):
        _need(not _is_blank(cid), f"conditions[{index}]", "non-blank str", cid)
    _need(len(set(conditions)) == len(conditions), "conditions", "unique ids", conditions)
    return tuple(conditions)


def _tri_for(per_code: object, condition_id: str) -> str:
    """缺值（整檔沒給、或該條件沒給、或值為 None）一律是「無法判定」——**絕不轉成不符合或 0**。其他值必須是三態字面。"""
    if per_code is None:
        return TRI_UNDETERMINED
    _need(isinstance(per_code, Mapping), "tristate_by_code[code]", "mapping or None", per_code)
    value = per_code.get(condition_id)
    if value is None:
        return TRI_UNDETERMINED
    _need(isinstance(value, str) and value in _TRI_VALUES, "tristate value", "match/no_match/undetermined", value)
    return value


def build_exp_counts(pool_view: PoolSourceView, tristate_by_code: object, conditions: object) -> ExpCountsView:
    """組出 EXP-0 結論、EXP-2 列與 EXP-7 軌跡（測試輸入驅動，非正式篩選；契約見模組 docstring）。

    - `tristate_by_code`：`{代碼: {條件 id: 'match'|'no_match'|'undetermined'}}`；代碼必須屬於選股池（否則 fail-closed）。
    - `conditions`：**生效**條件 id 的有序序列（未填值而不生效的條件由呼叫端先排除）；每個 id 非空白、不重複。
    - 組合規則（僅供一致性驗證，⛔ 不得搬入 production）：任一不符合→不符合；否則任一無法判定→無法判定；否則符合。
    - `pool_view` 為 `UNAVAILABLE`／`FAILED`／`EMPTY`：**不產生 N／M**（不偽稱 0；空池也不併入「沒有符合」），
      `status` 可識別；零條件（且來源 OK）：只有「尚未設定條件」，不展示 N／M、不產生列。
    """
    _need(isinstance(pool_view, PoolSourceView), "pool_view", "PoolSourceView", pool_view)
    ids = _condition_ids(conditions)
    if pool_view.state is PoolState.UNAVAILABLE:
        return ExpCountsView(COUNTS_POOL_UNAVAILABLE, len(ids))
    if pool_view.state is PoolState.FAILED:
        return ExpCountsView(COUNTS_POOL_FAILED, len(ids))
    if pool_view.state is PoolState.EMPTY:
        return ExpCountsView(COUNTS_POOL_EMPTY, len(ids))
    if not ids:
        return ExpCountsView(COUNTS_NO_CONDITIONS, 0, exp0_conclusion(0, None, None))

    _need(isinstance(tristate_by_code, Mapping), "tristate_by_code", "mapping", tristate_by_code)
    pool = set(pool_view.codes)
    unknown = [c for c in tristate_by_code if c not in pool]
    if unknown:
        raise PoolContractError("tristate_by_code: contains a code that is not in the pool") from None

    per_code = {code: [_tri_for(tristate_by_code.get(code), cid) for cid in ids] for code in pool_view.codes}

    # EXP-7：逐條件累計（alive＝到這一條為止沒有不符合；sure＝到這一條為止每一條都符合）。
    trajectory = []
    alive_before = len(pool_view.codes)
    for step, cid in enumerate(ids):
        alive = sum(1 for tris in per_code.values() if TRI_NO_MATCH not in tris[: step + 1])
        sure = sum(1 for tris in per_code.values() if all(t == TRI_MATCH for t in tris[: step + 1]))
        trajectory.append(Exp7Row(cid, alive_before, sure, alive - sure))
        alive_before = alive

    # EXP-2：最終列（保持選股池順序）；不符合者不列。
    rows = []
    for code in pool_view.codes:
        tris = per_code[code]
        if TRI_NO_MATCH in tris:
            continue
        rows.append(Exp2Row(code, TRI_UNDETERMINED if TRI_UNDETERMINED in tris else TRI_MATCH))
    n = sum(1 for r in rows if r.outcome == TRI_MATCH)
    m = len(rows) - n
    return ExpCountsView(COUNTS_COUNTED, len(ids), exp0_conclusion(len(ids), n, m), tuple(rows), tuple(trajectory))
