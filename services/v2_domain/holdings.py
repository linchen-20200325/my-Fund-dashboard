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

# ⚠️ 本檔刻意**不**寫 `from __future__ import annotations`：下方 frozen dataclass 的欄位註記若是字串，
#    `dataclasses` 會去查 `sys.modules[cls.__module__]`；而突變測試（`tests/test_alo_core_golden_mutations.py`）
#    以 `exec(compile(…, dont_inherit=True))` 載入本檔、且依約不進 `sys.modules`，字串註記會讓它在載入時炸掉。
#    本檔其餘註記（`-> bool`）立即求值無妨。
import math
from dataclasses import dataclass

__all__ = (
    "HOLDING_SUM_COLUMNS", "HOLDING_SAME_COLUMNS", "HoldingKeyConflict",
    "holding_key", "merge_same_key_holdings", "aggregate_holding_rows",
    "latest_nav_row", "fx_row_as_of", "fx_rate_as_of", "bucket_category", "exceeds", "target_sum",
    # BL-0542 G1-② 最小 PORT：基準值（成本／市值）與類別加總的純數值＋缺值判定核心。
    "REASON_NAV_ABSENT", "REASON_NAV_STALE", "REASON_NAV_STALE_UNDATED", "REASON_FX_ABSENT",
    "KIND_NAV", "KIND_FX", "MissingReason", "StaleMerge", "CategorySlot",
    "basis_value_with_reason", "category_values",
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


def fx_row_as_of(indicator_rows, nav_date, key):
    """`market_indicator` 表裡 `indicator_key == key` 且 `obs_date` 不晚於 `nav_date` 的最近一**列**（整列，不只數值）；沒有 → None。
    BL-0542 G1-③：對齊規則的**唯一實作**（`fx_rate_as_of` 委派到這裡）；同日多列取第一個出現的（`max` 的規則）。"""
    rows = [
        r
        for r in indicator_rows
        if r["indicator_key"] == key and r["obs_date"] <= nav_date
    ]
    return max(rows, key=lambda r: r["obs_date"]) if rows else None


def fx_rate_as_of(indicator_rows, nav_date, key):
    """`market_indicator` 表裡 `indicator_key == key` 且 `obs_date` 不晚於 `nav_date` 的最近一筆 `value_num`；沒有 → None。
    （BL-0542 G1-③：本體改為委派 `fx_row_as_of`；回傳值、例外型別與發生時機不變。）"""
    row = fx_row_as_of(indicator_rows, nav_date, key)
    return row["value_num"] if row is not None else None


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


# ───────────────────────── BL-0542 G1-② 最小 PORT：基準值與類別加總 ─────────────────────────
#
# 本段是 `ui_v2/alo/logic.py::basis_value_with_key`／`_category_values` 的**純數值與缺值判定**本體（判定一字未改）。
# 回傳值不帶任何畫面字樣：缺值原因是機器可讀的英文代碼（`MissingReason`／`StaleMerge`），由 ui_v2 薄包裝換回原本的中文句子與
# 資料類字樣（`page_health.DATA_CLASSES`）。逐位元組不變由 `tests/test_alo_core_golden.py`（212 情境）與其突變測試守住。
#
# 刻意保留的行為（PORT 不得順手「改好」）：
# - 浮點累加起點是 `0.0`、依持倉順序 `+=`；缺值是 `None`，不是 0.0。
# - 取表是惰性的：成本基準從不讀 `nav`／`market_indicator`；`market_indicator` 只在非新臺幣淨值時才讀。
# - 例外型別、訊息與發生時機不變：`stale_provider`／`fx_key_of` 由呼叫端注入（ui_v2 的 `nav_not_ready`／`fx_key_for`，
#   中文例外訊息原樣穿過），且只在原本就會呼叫的那個位置才呼叫。
# - 同類別遇到的第一種缺值定案；之後的持倉仍會被計入件數、仍會被呼叫（可能丟例外），只是值被忽略。
# - `NAV_NOT_READY_DAYS` 不在這裡：天數由 `stale_provider()` 帶進來（唯一給值處仍是 `ui_v2/thresholds.py`）。

# 缺值原因代碼（機器可讀；中文句子由 ui_v2 對照）。
REASON_NAV_ABSENT = "nav_absent"                  # 該檔在 `nav` 表沒有任何一列，也不在過期名單
REASON_NAV_STALE = "nav_stale"                    # 在過期名單，且帶最後淨值日（`stale_day`）
REASON_NAV_STALE_UNDATED = "nav_stale_undated"    # 在過期名單，舊形狀（沒有最後淨值日）
REASON_FX_ABSENT = "fx_absent"                    # 有淨值，但缺該幣別的換算匯率（`fx_key`）
# 缺值屬哪一類資料（ui_v2 對照 `page_health.DATA_CLASSES`）。
KIND_NAV = "nav"
KIND_FX = "fx"


@dataclass(frozen=True)
class MissingReason:
    """單檔缺基準值的原因。`fx_key` 只在 `REASON_FX_ABSENT` 有值；`stale_day`／`stale_days` 只在過期兩種有值
    （`REASON_NAV_STALE_UNDATED` 的 `stale_day` 為 None）。"""

    code: str
    fx_key: object = None
    stale_day: object = None
    stale_days: object = None


@dataclass(frozen=True)
class StaleMerge:
    """類別層「淨值過期」的合併結果：`entries` 是 ((代碼, 最後淨值日), …)，依持倉順序、同代碼只一次；`days` 是門檻天數。"""

    entries: tuple
    days: object


@dataclass(frozen=True)
class CategorySlot:
    """一個類別的加總結果。`value` 為 None ＝ 缺值（不是 0.0）；缺值時 `reason` 是 `MissingReason` 或 `StaleMerge`、
    `kind` 是 `KIND_*`；有值時兩者皆 None。`count` 含被忽略的後續持倉。"""

    value: object
    reason: object
    count: int
    kind: object


def basis_value_with_reason(holding, tables, *, market, fx_key_of, stale_provider):
    """單檔基準值 → (新臺幣值 或 None, `MissingReason` 或 None, `KIND_*` 或 None)。

    `market` 為 False ＝ 成本基準（`float(cost_twd)`，不讀任何表）；True ＝ 市值基準（淨值 × 單位數，非新臺幣再乘匯率）。
    `tables`：有 `"nav"`、`"market_indicator"` 兩張表列的映射，**惰性**讀取（成本基準一張都不碰）。
    `fx_key_of(ccy)`：幣別 → 匯率鍵（呼叫端注入；不合法的幣別由它丟例外）。
    `stale_provider()`：→ (過期代碼集合, 天數, {代碼: 最後淨值日} 或 None)；**只在該檔沒有淨值時**才呼叫。"""
    if not market:
        return float(holding["cost_twd"]), None, None
    code = holding["fund_code"]
    nav = latest_nav_row(tables["nav"], code)
    if nav is None:
        codes, days, last = stale_provider()
        if holding["fund_code"] in codes:
            if last is None:   # 舊形狀（沒有 `last`）：沒有日期
                return None, MissingReason(REASON_NAV_STALE_UNDATED, stale_days=days), KIND_NAV
            return None, MissingReason(REASON_NAV_STALE, stale_day=last[holding["fund_code"]], stale_days=days), KIND_NAV
        return None, MissingReason(REASON_NAV_ABSENT), KIND_NAV
    value = holding["units_shares"] * nav["nav_orig_ccy"]
    if nav["ccy"] == "TWD":
        return value, None, None
    key = fx_key_of(nav["ccy"])
    nav_date = nav["nav_date"]
    rate = fx_rate_as_of(tables["market_indicator"], nav_date, key)
    if rate is None:
        return None, MissingReason(REASON_FX_ABSENT, fx_key=key), KIND_FX
    return value * rate, None, None


def category_values(holdings, tables, *, market, track_stale, category_of, fx_key_of, stale_provider):
    """持倉（已同鍵加總）→ ({類別: `CategorySlot`}, {類別: `StaleMerge`})，類別依第一次出現的順序。

    `track_stale`：True 時，定案的缺值若是「過期且帶日期」，同類別後面同為過期的檔併進同一個 `StaleMerge`
    （同代碼只一次）；單檔過期也一律包成 `StaleMerge`（一筆）。第二個回傳值依「定案」的先後順序。
    `category_of(holding)`：持倉 → 類別（呼叫端注入，含未分類的字樣）。其餘參數同 `basis_value_with_reason`。"""
    slots = {}    # 類別 → [值, 原因, 件數, 資料類]（工作狀態，最後才凍結）
    stale = {}    # 類別 → StaleMerge
    for holding in holdings:
        cat = category_of(holding)
        slot = slots.setdefault(cat, [0.0, None, 0, None])
        slot[2] += 1
        value, reason, kind = basis_value_with_reason(
            holding, tables, market=market, fx_key_of=fx_key_of, stale_provider=stale_provider)
        code = holding["fund_code"]
        is_stale = track_stale and value is None and reason.code == REASON_NAV_STALE
        if slot[1] is not None:
            if is_stale and cat in stale and code not in {c for c, _ in stale[cat].entries}:
                stale[cat] = StaleMerge(stale[cat].entries + ((code, reason.stale_day),), reason.stale_days)
                slot[1] = stale[cat]
            continue
        if value is None:
            slot[0], slot[1], slot[3] = None, reason, kind
            if is_stale:
                stale[cat] = StaleMerge(((code, reason.stale_day),), reason.stale_days)
                slot[1] = stale[cat]
        else:
            slot[0] += value
    return {cat: CategorySlot(s[0], s[1], s[2], s[3]) for cat, s in slots.items()}, stale
