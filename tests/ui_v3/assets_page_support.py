# -*- coding: utf-8 -*-
"""💼 頁 VM／adapter 測試共用的 **FAKE** 輸入建構器（不是測試檔；檔名取唯一的 `assets_page_support`，同 `assets_source_support` 體例）。

⚠️ 這裡所有資料都是**人造的 FAKE**：基金名稱、代碼、金額、試算表分頁名都不是任何真實資料；不代表真實持倉、不得宣稱「真實資料」。
純 dict（形狀＝`AssetsLoadResult.to_primitive()`；欄位名取自證據生產者輸出的讀碼對照，**未經本批測試鎖住**），
**不 import pandas／streamlit／services**，可在輕量環境執行。

真生產者形狀對照已延後，需另行授權；目前 fake 形狀與真生產者的一致性為 NOT VERIFIED（repo 內 assets_source 既有契約測試覆蓋載入端）。每個建構器每次呼叫都回傳**全新的** dict（測試可放心修改）。
"""
from __future__ import annotations

import dataclasses
import math
import pathlib
import sys

_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:   # 本機以 `--noconftest` 跑；不依賴 conftest
    sys.path.insert(0, str(_ROOT))

FAKE_FIXTURE = True

# 刻意設成與任何持倉列的金額都不同的哨兵值：它若出現在 VM 的任何地方，就是 `categories[*].value_twd` 漏進來了。
SENTINEL_CATEGORY_VALUE = 987654321.5
SENTINEL_HOLDING_VALUE = 555555.5     # 證據持倉列的 `value_twd`（逐檔估值金額）；預設欄位集合不含它
SENTINEL_COST_TWD = 424242.25         # 證據持倉列的 `cost_twd`（逐檔淨投資金額）；預設欄位集合不含它
SENTINEL_COST_ORIG = 313131.75        # 證據持倉列的 `cost_orig_ccy`
SENTINEL_SHARE_PCT = 33.25            # 類別 `share_of_covered_pct`（比例）
FAKE_SKIPPED_TAB_ITEM = {"tab": "FAKE-TAB-SKIPPED"}
FAKE_SKIPPED_ROW_ITEM = {"tab": "FAKE-TAB", "row": 9, "fund_code": "FAKE-X", "reasons": ["FAKE reason"]}


def fake_holding(n: int = 1, **over) -> dict:
    """一列證據持倉（欄位名＝生產者 `HoldingEvidence` 的 primitive 子集）。FAKE。"""
    row = {
        "policy_id": f"FAKE-POLICY-{n}", "fund_code": f"FK{n:04d}", "holding_id": f"FAKE-POLICY-{n}|FK{n:04d}|1",
        "fund_name": f"FAKE 基金 {n}", "bucket": "core" if n % 2 else "sat", "category": "core" if n % 2 else "sat",
        "is_unclassified": False, "ccy": "USD", "units_shares": 1000.0 + n, "cost_twd": SENTINEL_COST_TWD,
        "cost_orig_ccy": SENTINEL_COST_ORIG, "source_row_count": 1,
        "nav": {"status": "not_required"}, "fx": {"status": "not_required"}, "nav_state": "not_required",
        "value_status": "valued", "value_twd": SENTINEL_HOLDING_VALUE, "valued": True, "errors": [],
    }
    row.update(over)
    return row


def _facet(items=None) -> dict:
    """`ProvidedItems` 的 primitive：`items=None` ＝ 來源沒提供（not_provided）。"""
    return {"status": "not_provided", "items": []} if items is None else {"status": "provided", "items": list(items)}


def fake_evidence(*, holdings=(), coverage="complete", coverage_codes=(), skipped_tabs=(), omitted_rows=(),
                  active_source="selected", basis_value="成本", basis_status="set") -> dict:
    """`AllocationEvidence.to_primitive()` 的子集＋會被測試用來證明「不外洩」的欄位（`categories`／`denominator`／`coverage`）。FAKE。

    `skipped_tabs`／`omitted_rows` 傳 None ＝ 來源沒提供該證據（≠ 空 list）。
    """
    return {
        "producer_id": "FAKE.producer", "schema_version": 2, "rule_ref": {"status": "not_defined"},
        "settings": {"basis": {"status": basis_status, "value": basis_value if basis_status == "set" else None},
                     "targets": {"status": "unset", "value": None}, "tolerance": {"status": "unset", "value": None},
                     "bucket_names": {"status": "unset", "value": None}},
        "source": {"state_status": "provided", "active_source": active_source, "read_errors": _facet([]),
                   "skipped_tabs": _facet(skipped_tabs if skipped_tabs is None else list(skipped_tabs)),
                   "omitted_rows": _facet(omitted_rows if omitted_rows is None else list(omitted_rows))},
        "holdings": [dict(h) for h in holdings],
        "categories": [{"category": "core", "origin": "from_holdings", "status": "valued", "value_twd": SENTINEL_CATEGORY_VALUE,
                        "value_origin": "summed", "holding_count": len(list(holdings)),
                        "share": {"status": "computed", "share_of_covered_pct": SENTINEL_SHARE_PCT, "covers_all_holdings": True}}],
        "denominator": {"value_twd": SENTINEL_CATEGORY_VALUE, "verdict": "complete"},
        "coverage": {"covered_value_twd": SENTINEL_CATEGORY_VALUE},
        "source_coverage": {"status": coverage, "reason_codes": list(coverage_codes)},
        "valuation_completeness": {"status": "complete", "reason_codes": []},
        "chart_comparability": {"status": "comparable", "failing_conditions": [], "pending_gates": []},  # 生產者內部候選；不得被當成圖表可比
        "open_gates": [], "fx_rule_verified": False, "nav_input_state": "not_provided",
    }


def fake_result(*, status="evaluated", blocked_reason=None, evidence="default", problems=(), holding_failure_code=None,
                settings_status=None) -> dict:
    """`AssetsLoadResult.to_primitive()` 形狀的 FAKE dict。`evidence="default"` ＝ 一份空的完整證據。"""
    settings = {"alo_basis": "set", "alo_target_weights": "set", "alo_tolerance_pp": "set", "alo_bucket_names": "set"}
    settings.update(settings_status or {})
    return {
        "schema_version": 1, "status": status, "blocked_reason": blocked_reason, "problems": list(problems),
        "settings_status": settings, "holding_failure_code": holding_failure_code,
        "chart_claim": "withheld_pending_approval", "evidence": fake_evidence() if evidence == "default" else evidence,
    }


# ───────────── 情境（82 §11.9.7 三種來源情境＋市值基準 blocked） ─────────────

def complete_result(n: int = 2) -> dict:
    """情境一：來源完整、有 n 列。"""
    return fake_result(evidence=fake_evidence(holdings=[fake_holding(i) for i in range(1, n + 1)]))


def partial_result() -> dict:
    """情境二：部分缺漏——略過 1 個分頁、2 列；仍有 2 列可用，其中一列缺 fund_name、另一列 units_shares 是不可用型別。"""
    rows = [fake_holding(1, fund_name=None), fake_holding(2, units_shares=True)]
    ev = fake_evidence(holdings=rows, coverage="incomplete", coverage_codes=("skipped_tabs_present", "omitted_rows_present"),
                       skipped_tabs=[FAKE_SKIPPED_TAB_ITEM], omitted_rows=[FAKE_SKIPPED_ROW_ITEM, dict(FAKE_SKIPPED_ROW_ITEM, row=10)])
    return fake_result(evidence=ev)


def partial_tabs_only_result() -> dict:
    """只有略過分頁、沒有略過列（略過列證據已提供且為空）；仍有 1 列可用。"""
    ev = fake_evidence(holdings=[fake_holding(1)], coverage="incomplete", coverage_codes=("skipped_tabs_present",),
                       skipped_tabs=[FAKE_SKIPPED_TAB_ITEM], omitted_rows=[])
    return fake_result(evidence=ev)


def partial_rows_only_result() -> dict:
    """只有略過列、沒有略過分頁（略過分頁證據已提供且為空）；仍有 1 列可用。"""
    ev = fake_evidence(holdings=[fake_holding(1)], coverage="incomplete", coverage_codes=("omitted_rows_present",),
                       skipped_tabs=[], omitted_rows=[FAKE_SKIPPED_ROW_ITEM])
    return fake_result(evidence=ev)


def complete_with_unprovided_skip_evidence_result(rows: int = 1, missing_facet: str = "omitted_rows") -> dict:
    """coverage 說 complete，但其中一項略過證據來源沒提供（not_provided）——不得顯示『來源已讀完』。"""
    kwargs = {"skipped_tabs": [], "omitted_rows": []}
    kwargs[missing_facet] = None
    ev = fake_evidence(holdings=[fake_holding(i) for i in range(1, rows + 1)], coverage="complete", **kwargs)
    return fake_result(evidence=ev)


def complete_with_skip_items_result(facet: str = "skipped_tabs") -> dict:
    """coverage 說 complete，但略過證據的件數 >0（自相矛盾）——不得顯示『來源已讀完』。"""
    kwargs = {"skipped_tabs": [], "omitted_rows": []}
    kwargs[facet] = [FAKE_SKIPPED_TAB_ITEM] if facet == "skipped_tabs" else [FAKE_SKIPPED_ROW_ITEM]
    ev = fake_evidence(holdings=[fake_holding(1)], coverage="complete", **kwargs)
    return fake_result(evidence=ev)


def no_active_result() -> dict:
    """情境三 (a)：未選 Active。"""
    ev = fake_evidence(coverage="not_selected", coverage_codes=("no_active_source",), active_source="none",
                       skipped_tabs=None, omitted_rows=None)
    return fake_result(evidence=ev, problems=["no_active_source"])


def read_failed_result(code: str = "NETWORK_ERROR") -> dict:
    """情境三 (b)：讀取失敗。"""
    ev = fake_evidence(coverage="failed", coverage_codes=("holding_read_failed",), skipped_tabs=None, omitted_rows=None)
    return fake_result(evidence=ev, problems=["holding_read_failed"], holding_failure_code=code)


def complete_no_rows_result() -> dict:
    """情境三 (c)：來源完整（略過證據都提供且為空）但沒有任何列。"""
    return fake_result(evidence=fake_evidence(holdings=[], coverage="complete"))


def unknown_coverage_result(rows: int = 1, coverage: str = "unknown") -> dict:
    """證據不足以歸類：coverage 是 unknown（或呼叫端指定的未知字串），有或沒有列。"""
    ev = fake_evidence(holdings=[fake_holding(i) for i in range(1, rows + 1)], coverage=coverage,
                       coverage_codes=("omitted_rows_not_provided",), skipped_tabs=[], omitted_rows=None)
    return fake_result(evidence=ev)


def settings_failed_result() -> dict:
    """持倉讀取成功（1 列），但設定讀取失敗 → 生產者把來源涵蓋記成 incomplete，且沒有任何略過證據。"""
    ev = fake_evidence(holdings=[fake_holding(1)], coverage="incomplete", coverage_codes=("settings_read_failed",),
                       skipped_tabs=[], omitted_rows=[], basis_status="read_failed")
    return fake_result(evidence=ev, problems=["settings_read_failed"], settings_status={
        "alo_basis": "read_failed", "alo_target_weights": "read_failed", "alo_tolerance_pp": "read_failed",
        "alo_bucket_names": "read_failed"})


def market_blocked_result() -> dict:
    """市值基準：`assets_source` 回 blocked（不讀持倉、不呼叫生產者、evidence=None）。"""
    return fake_result(status="blocked", blocked_reason="market_basis_assembly_not_available_in_preview", evidence=None)


SCENARIOS = {
    "complete": complete_result,
    "partial": partial_result,
    "no_active": no_active_result,
    "read_failed": read_failed_result,
    "complete_no_rows": complete_no_rows_result,
    "unknown_coverage": unknown_coverage_result,
    "settings_failed": settings_failed_result,
    "market_blocked": market_blocked_result,
}


# ───────────── 存取追蹤 dict／VM 走訪 ─────────────

class TrackingDict(dict):
    """記錄被讀過哪些鍵的 dict（證明 adapter 從不讀 `categories` 等金額欄位）。只追蹤這一層。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.accessed = set()
        self.iterated = False

    def __getitem__(self, key):
        self.accessed.add(key)
        return super().__getitem__(key)

    def get(self, key, default=None):
        self.accessed.add(key)
        return super().get(key, default)

    def __contains__(self, key):
        return super().__contains__(key)   # 檢查鍵是否存在不算讀值

    def __iter__(self):
        self.iterated = True
        return super().__iter__()

    def items(self):
        self.iterated = True
        return super().items()

    def values(self):
        self.iterated = True
        return super().values()

    def keys(self):
        self.iterated = True
        return super().keys()


def walk(obj):
    """走訪 dataclass／tuple 的所有節點（含自己）。"""
    yield obj
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        for f in dataclasses.fields(obj):
            yield from walk(getattr(obj, f.name))
    elif isinstance(obj, (tuple, list)):
        for x in obj:
            yield from walk(x)


def leaf_values(obj):
    """VM 內所有葉值（字串、數字、None、bool）。"""
    return [n for n in walk(obj) if n is None or isinstance(n, (str, int, float, bool))]


def numeric_leaves(obj):
    return [n for n in leaf_values(obj) if isinstance(n, (int, float)) and not isinstance(n, bool)]


def all_dataclass_field_names(*modules):
    """給定模組裡所有 dataclass 的欄位名。"""
    names = set()
    for mod in modules:
        for value in vars(mod).values():
            if isinstance(value, type) and dataclasses.is_dataclass(value) and value.__module__ == mod.__name__:
                names |= {f.name for f in dataclasses.fields(value)}
    return names


def finite(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)
