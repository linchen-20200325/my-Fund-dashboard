# -*- coding: utf-8 -*-
"""🔍 找一檔基金／依條件篩選｜隔離式 FAKE Preview 的 view model（純 Python，只用標準函式庫與 `ui_v3.viewmodels.exp_counts`）。

⚠️ 組合規則（任一不符合→不符合；否則任一資料不足→無法判定；否則→符合）**僅屬測試輸入的計數演示規則**，
不是金融公式、不是正式篩選判準，**不得搬入 production**。三態本身由 fixture 明確給定，本檔不從任何數值推導它。
N／M／N＋M 的文案與一致性驗證全部重用 `exp_counts`，不重造。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

from ui_v3.viewmodels import exp_counts

MATCH, NOMATCH, UNDET = "match", "nomatch", "undetermined"
STATES = (MATCH, NOMATCH, UNDET)

# 單檔查詢的結果種類
OUT_FOUND = "found"
OUT_INSUFFICIENT = "insufficient"
OUT_FAILED = "failed"
OUT_UNRECOGNIZED = "unrecognized"
OUT_NO_FIXTURE = "no_fixture"
OUT_ISIN = "isin"
OUTCOMES = (OUT_FOUND, OUT_INSUFFICIENT, OUT_FAILED, OUT_UNRECOGNIZED, OUT_NO_FIXTURE, OUT_ISIN)

# 預覽用的「輸入型態」判斷：只表示輸入長得像什麼，不表示基金身份（不是正式 resolver、不是正式格式契約）。
_ISIN_SHAPE = re.compile(r"[A-Z]{2}[A-Z0-9]{9}[0-9]")
_CODE_SHAPE = re.compile(r"[A-Z0-9-]{3,24}")


@dataclass(frozen=True)
class LookupResult:
    outcome: str
    raw: str  # 輸入原值（不改寫、不拆後綴）；顯示時才 escape

    def __post_init__(self) -> None:
        if self.outcome not in OUTCOMES:
            raise ValueError(f"未知的查詢結果種類 {self.outcome!r}")
        if not isinstance(self.raw, str):
            raise ValueError(f"raw 必須是字串，收到 {self.raw!r}")


def classify_lookup(raw: object, fixtures) -> LookupResult:
    """輸入 → 查詢結果種類。ISIN 形的輸入只標 `isin`：不解析、不取數、不查任何對照。
    空白或非支援格式 → `unrecognized`（無法判定，不是『不存在』）；格式像代碼但 fixture 沒有 → `no_fixture`（同樣無法判定）。"""
    if not isinstance(raw, str):
        raise ValueError(f"輸入必須是字串，收到 {raw!r}（{type(raw).__name__}）")
    key = raw.strip().upper()
    if not key:
        return LookupResult(OUT_UNRECOGNIZED, raw)
    if _ISIN_SHAPE.fullmatch(key):
        return LookupResult(OUT_ISIN, raw)
    if not _CODE_SHAPE.fullmatch(key):
        return LookupResult(OUT_UNRECOGNIZED, raw)
    return LookupResult(fixtures.get(key, OUT_NO_FIXTURE), raw)


@dataclass(frozen=True)
class FundRow:
    code: str
    cells: Tuple[Tuple[str, Optional[str]], ...]   # (欄鍵, 值或 None＝缺值)，順序固定
    state: str                                      # match／undetermined（不符合的不列）

    def cell(self, col: str) -> Optional[str]:
        return dict(self.cells)[col]


@dataclass(frozen=True)
class TraceRow:
    index: int          # 條件序號（1 起算）
    before: int         # 套用前檔數（第一條＝池大小；其後＝上一列的 符合＋無法判定）
    matched: int
    undetermined: int


@dataclass(frozen=True)
class FilterView:
    conditions: Tuple[int, ...]
    conclusion: exp_counts.ExpCountsConclusion
    rows: Tuple[FundRow, ...]
    trace: Tuple[TraceRow, ...]


def combine(states: Sequence[str]) -> str:
    """僅供計數演示：任一不符合→不符合；否則任一資料不足→無法判定；否則→符合。空序列沒有意義，直接拒絕。"""
    if not states:
        raise ValueError("combine 至少要一個條件")
    for s in states:
        if s not in STATES:
            raise ValueError(f"未知的三態值 {s!r}")
    if NOMATCH in states:
        return NOMATCH
    if UNDET in states:
        return UNDET
    return MATCH


def _validate_pool(pool: Sequence[dict], condition_count: int) -> None:
    for fund in pool:
        states = fund["states"]
        if len(states) != condition_count:
            raise ValueError(f"每檔基金必須明確提供 {condition_count} 個條件的三態，收到 {states!r}")
        for s in states:
            if s not in STATES:
                raise ValueError(f"未知的三態值 {s!r}")


def build_filter_view(pool: Sequence[dict], active: Sequence[int], condition_count: int) -> FilterView:
    """`active`：生效條件的序號（1 起算，依畫面順序套用）。零生效條件 → 尚未設定條件、不展示 N／M、沒有列、沒有軌跡。"""
    _validate_pool(pool, condition_count)
    seen = tuple(active)
    if len(set(seen)) != len(seen) or any((not isinstance(i, int)) or isinstance(i, bool) or i < 1 or i > condition_count for i in seen):
        raise ValueError(f"生效條件序號不合法：{seen!r}")
    if not seen:
        return FilterView((), exp_counts.exp0_conclusion(0, None, None), (), ())
    trace = []
    before = len(pool)
    for step in range(1, len(seen) + 1):
        chosen = seen[:step]
        status = [combine([f["states"][i - 1] for i in chosen]) for f in pool]
        m, u = status.count(MATCH), status.count(UNDET)
        trace.append(TraceRow(index=chosen[-1], before=before, matched=m, undetermined=u))
        before = m + u
    final = [combine([f["states"][i - 1] for i in seen]) for f in pool]
    rows = tuple(sorted(
        (FundRow(code=f["cells"]["code"], cells=tuple((c, f["cells"][c]) for c in f["cells"]), state=s)
         for f, s in zip(pool, final) if s != NOMATCH),
        key=lambda r: r.code))   # 固定順序：fund_code 字面值升冪（不是名次）
    n, m = final.count(MATCH), final.count(UNDET)
    conclusion = exp_counts.exp0_conclusion(len(seen), n, m)
    exp_counts.verify_exp2_row_count(len(rows), n, m)
    exp_counts.verify_exp7_last_row([(t.matched, t.undetermined) for t in trace], n, m)
    return FilterView(seen, conclusion, rows, tuple(trace))
