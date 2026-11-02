# -*- coding: utf-8 -*-
"""持倉列的純計算（原 `ui_v2/hld/logic.py` 與 `ui_v2/alo/logic.py`，2026-11-02 PORT，判定一字未改）。

輸入是 `services/v2_tables` 交出的表列（`44` 第四節的 `holding`／`nav`／`market_indicator` 列），
不是 ui_v2 的 block dict。回傳值不帶任何畫面字樣：類別「未分類」回 `None`、衝突丟中性例外
`HoldingKeyConflict`，由 ui_v2 薄包裝換回原本的 `ValueError` 原字訊息與「未分類」字樣。

⚠️ **兩種同鍵合併規則刻意各留一支、不合併**（行為不變的 PORT 不得順手統一）：
- `merge_same_key_holdings`（原 hld）：鍵兩邊去前後空白；比對 `HOLDING_SAME_COLUMNS` 四欄，一次列出全部不同的欄；
  欄位用 `.get` 讀（缺欄當 None 比）。
- `aggregate_holding_rows`（原 alo）：鍵**不**去空白；只比 `bucket`、再比 `ccy`，遇到第一個不同就停；欄位用 `[]` 讀。
兩者是否該收斂成一條規則，屬跨頁一致性（`PROJECT_RULES.md` 13.3）的業務判斷，本批登記、不裁。
"""

from __future__ import annotations

import math

__all__ = (
    "HOLDING_SUM_COLUMNS", "HOLDING_SAME_COLUMNS", "HoldingKeyConflict",
    "holding_key", "merge_same_key_holdings", "aggregate_holding_rows",
    "latest_nav_row", "fx_rate_as_of", "bucket_category", "exceeds", "target_sum",
)

# 同鍵加總的三欄（hld 與 alo 相同、順序相同）。
HOLDING_SUM_COLUMNS = ("units_shares", "cost_orig_ccy", "cost_twd")
# hld 規則：同鍵而這四欄任一不同 → 不是同一語意，不加總（原 `ui_v2/hld/logic.py` 的同名常數）。
HOLDING_SAME_COLUMNS = ("ccy", "bucket", "opened_on", "last_synced_at")


class HoldingKeyConflict(ValueError):
    """同鍵兩列語意不同（不加總、也不挑一列）。`columns` 是不同的欄名（依比對順序）。"""

    def __init__(self, key, columns):
        self.key = key
        self.columns = tuple(columns)
        super().__init__(f"holding key {key!r}: columns differ: {', '.join(self.columns)}")


def holding_key(row) -> tuple:
    """hld 規則的鍵：(`policy_id`, `fund_code`)，字串只去前後空白，不改大小寫、不補 0。"""
    def text(value):
        return value.strip() if isinstance(value, str) else value
    return (text(row.get("policy_id")), text(row.get("fund_code")))


def merge_same_key_holdings(holdings) -> list:
    """hld 規則：同鍵多列加總成一列。順序照第一次出現的位置；不改輸入。"""
    merged, order = {}, []
    for row in holdings:
        key = holding_key(row)
        if key not in merged:
            merged[key] = dict(row)
            order.append(key)
            continue
        base = merged[key]
        diff = [column for column in HOLDING_SAME_COLUMNS if base.get(column) != row.get(column)]
        if diff:
            raise HoldingKeyConflict(key, diff)
        for column in HOLDING_SUM_COLUMNS:
            base[column] = base[column] + row[column]
    return [merged[key] for key in order]


def aggregate_holding_rows(rows) -> list:
    """alo 規則：業務唯一鍵（`policy_id`, `fund_code`）；同鍵多列加總成一列。
    `bucket` 不同 → `HoldingKeyConflict(key, ("bucket",))`；`ccy` 不同 → `HoldingKeyConflict(key, ("ccy",))`
    （不同幣別的原幣成本不得相加，`CLAUDE.md` §4.1）。"""
    merged, order = {}, []
    for row in rows:
        key = (row["policy_id"], row["fund_code"])
        if key not in merged:
            merged[key] = dict(row)
            order.append(key)
            continue
        base = merged[key]
        if base["bucket"] != row["bucket"]:
            raise HoldingKeyConflict(key, ("bucket",))
        if base["ccy"] != row["ccy"]:
            raise HoldingKeyConflict(key, ("ccy",))
        for column in HOLDING_SUM_COLUMNS:
            base[column] = base[column] + row[column]
    return [merged[key] for key in order]


def latest_nav_row(nav_rows, fund_code):
    """`nav` 表裡該檔 `nav_date` 最大的一列；沒有 → None（同日多列取第一個出現的，`max` 的規則）。"""
    rows = [r for r in nav_rows if r["fund_code"] == fund_code]
    return max(rows, key=lambda r: r["nav_date"]) if rows else None


def fx_rate_as_of(indicator_rows, nav_date, key):
    """`market_indicator` 表裡 `indicator_key == key` 且 `obs_date` 不晚於 `nav_date` 的最近一筆 `value_num`；沒有 → None。"""
    rows = [
        r
        for r in indicator_rows
        if r["indicator_key"] == key and r["obs_date"] <= nav_date
    ]
    return max(rows, key=lambda r: r["obs_date"])["value_num"] if rows else None


def bucket_category(bucket, bucket_names):
    """`bucket` 空值、或不在類別名稱裡 → None（未分類）；否則回 `bucket` 本身。"""
    if bucket is None or bucket not in (bucket_names or ()):
        return None
    return bucket


def exceeds(diff, tolerance) -> bool:
    """超出容許帶：|差距| 大於容許帶；相等（含浮點容差 1e-9）不算超出。"""
    return abs(diff) > tolerance and not math.isclose(abs(diff), tolerance, abs_tol=1e-9)


def target_sum(targets):
    """目標比重合計：`weight_ratio` 留空（None）的那一列不計入。"""
    return sum(t["weight_ratio"] for t in targets or () if t["weight_ratio"] is not None)
