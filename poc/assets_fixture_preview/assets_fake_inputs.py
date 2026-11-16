# -*- coding: utf-8 -*-
"""💼 我的資產 Preview 的 FAKE 輸入（純 dict；形狀＝載入結果的 primitive）。

⚠️ 全部是人造的 FAKE：基金名稱、代碼、數值都不是任何真實資料，不代表真實持倉。
不 import 任何 `ui_v3` 模組、`services`、`gspread`、`requests`；不讀檔、不連網、不取憑證。
形狀與 `tests/ui_v3/assets_page_support.py` 的同名情境逐一相同（有 drift 測試鎖）；真生產者形狀的一致性為 NOT VERIFIED。
每個建構器每次呼叫都回傳全新的 dict。
"""
from __future__ import annotations

FAKE_FIXTURE = True

SENTINEL_CATEGORY_VALUE = 987654321.5
SENTINEL_HOLDING_VALUE = 555555.5
SENTINEL_COST_TWD = 424242.25
SENTINEL_COST_ORIG = 313131.75
SENTINEL_SHARE_PCT = 33.25
FAKE_SKIPPED_TAB_ITEM = {"tab": "FAKE-TAB-SKIPPED"}
FAKE_SKIPPED_ROW_ITEM = {"tab": "FAKE-TAB", "row": 9, "fund_code": "FAKE-X", "reasons": ["FAKE reason"]}


def fake_holding(n: int = 1, **over) -> dict:
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
    return {"status": "not_provided", "items": []} if items is None else {"status": "provided", "items": list(items)}


def fake_evidence(*, holdings=(), coverage="complete", coverage_codes=(), skipped_tabs=(), omitted_rows=(),
                  active_source="selected", basis_value="成本", basis_status="set") -> dict:
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
        "chart_comparability": {"status": "comparable", "failing_conditions": [], "pending_gates": []},
        "open_gates": [], "fx_rule_verified": False, "nav_input_state": "not_provided",
    }


def fake_result(*, status="evaluated", blocked_reason=None, evidence="default", problems=(), holding_failure_code=None,
                settings_status=None) -> dict:
    settings = {"alo_basis": "set", "alo_target_weights": "set", "alo_tolerance_pp": "set", "alo_bucket_names": "set"}
    settings.update(settings_status or {})
    return {
        "schema_version": 1, "status": status, "blocked_reason": blocked_reason, "problems": list(problems),
        "settings_status": settings, "holding_failure_code": holding_failure_code,
        "chart_claim": "withheld_pending_approval", "evidence": fake_evidence() if evidence == "default" else evidence,
    }


# ───────────── 七個情境 ─────────────

def multi_currency_result() -> dict:
    """①來源完整、兩列：一列新臺幣、一列美元（只呈現原幣事實；本 Preview 不做任何匯率換算或合計）。"""
    rows = [fake_holding(1, ccy="TWD"), fake_holding(2, ccy="USD")]
    return fake_result(evidence=fake_evidence(holdings=rows))


def complete_no_rows_result() -> dict:
    """②來源完整、沒有任何列。"""
    return fake_result(evidence=fake_evidence(holdings=[], coverage="complete"))


def market_blocked_result() -> dict:
    """③市值基準被擋：不讀持倉、沒有證據。"""
    return fake_result(status="blocked", blocked_reason="market_basis_assembly_not_available_in_preview", evidence=None)


def partial_result() -> dict:
    """④部分缺漏（現行 view model 沒有逐檔淨值／配息／1Y 的概念，故以略過分頁／略過列代表局部缺漏）。"""
    rows = [fake_holding(1, fund_name=None), fake_holding(2, units_shares=True)]
    ev = fake_evidence(holdings=rows, coverage="incomplete", coverage_codes=("skipped_tabs_present", "omitted_rows_present"),
                       skipped_tabs=[FAKE_SKIPPED_TAB_ITEM], omitted_rows=[FAKE_SKIPPED_ROW_ITEM, dict(FAKE_SKIPPED_ROW_ITEM, row=10)])
    return fake_result(evidence=ev)


def no_active_result() -> dict:
    """⑤未選定 Active 來源。"""
    ev = fake_evidence(coverage="not_selected", coverage_codes=("no_active_source",), active_source="none",
                       skipped_tabs=None, omitted_rows=None)
    return fake_result(evidence=ev, problems=["no_active_source"])


def read_failed_result(code: str = "NETWORK_ERROR") -> dict:
    """⑥讀取失敗（失敗代碼不得出現在畫面上）。"""
    ev = fake_evidence(coverage="failed", coverage_codes=("holding_read_failed",), skipped_tabs=None, omitted_rows=None)
    return fake_result(evidence=ev, problems=["holding_read_failed"], holding_failure_code=code)


def unprovided_skip_evidence_result() -> dict:
    """⑦來源說完整，但略過證據沒有提供（沒有列）：不得顯示「來源已讀完」。"""
    ev = fake_evidence(holdings=[], coverage="complete", skipped_tabs=[], omitted_rows=None)
    return fake_result(evidence=ev)


# 情境 id → (畫面上的情境名, 建構器)；順序即 selectbox 順序。
SCENARIOS = {
    "multi_currency": ("①完整（新臺幣＋美元）", multi_currency_result),
    "complete_no_rows": ("②來源完整但沒有持倉列", complete_no_rows_result),
    "market_blocked": ("③市值基準未開放", market_blocked_result),
    "partial": ("④局部缺漏", partial_result),
    "no_active": ("⑤未選定來源", no_active_result),
    "read_failed": ("⑥讀取失敗", read_failed_result),
    "unprovided_skip_evidence": ("⑦略過證據未提供", unprovided_skip_evidence_result),
}
DEFAULT_SCENARIO = "multi_currency"


def build(scenario_id: str) -> dict:
    """情境 id → 全新的 FAKE 結果 dict；未知 id → KeyError（不猜）。"""
    return SCENARIOS[scenario_id][1]()
