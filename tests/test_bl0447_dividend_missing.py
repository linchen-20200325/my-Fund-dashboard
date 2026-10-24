"""BL-0447（2026-10-24）：換標的建議規則 (a)（吃本金）——「沒有配息資料」不等於「非配息基金」。

`check_eating_principal_1y_mk` 回 None（非例外）的意思是「沒有任何配息跡象」；那可能是
確實不配息，也可能是配息取數失敗。DG-6 原本把它一律當成規則 (a) 不適用 → 配息資料全缺的
配息基金可以落到 🟢 保留（Missing → HOLD）。

本檔鎖住收窄後的行為：只有 L1 配息取數總結 `dividends_fetch_outcome` 為
`outcome == "none_confirmed"` 且 `none_evidenced is True`（與 v2 B 線
`services/v2_tables/nav_dividend.py` 同一標準）時，規則 (a) 才算不適用；其餘一律判不動 → ⬜。
公式、門檻、`resolve_dividend_rate_12m`／`check_eating_principal_1y_mk` 皆未改。
"""
from __future__ import annotations

import pytest

from services.health import replacement as rep_mod
from services.health.replacement import check_replacement_recommendation
from services.regime_fit import asset_bucket
from services.zscore_engine import is_core_bucket


def _noncore_category() -> str:
    for cat in ("全球股票型", "科技股票型", "平衡型", "多重資產型", "貨幣市場型"):
        if asset_bucket(cat)[0] is not None and is_core_bucket(cat) is False:
            return cat
    raise AssertionError("找不到可對應的非核心類別")


_CAT = _noncore_category()

# 規則 (b)(c)(d) 都判得動且都不觸發的指標（Sharpe>0、3-3-3 通過、4D 等第可算）
_OK_METRICS = {"sharpe": 1.0, "std_1y": 8.0, "max_drawdown": -15.0,
               "ret_3y_ann_tr": 9.0, "ret_1y_total": 12.0, "ret_1y_window_days": 365}

_CONFIRMED_NONE = {"outcome": "none_confirmed", "sources": [], "legacy_inline_parse": False,
                   "none_evidenced": True}


def _no_div_fd(outcome=None, *, top_level=False):
    """沒有任何配息跡象（無 moneydj_div_yield、無配息列）的基金。outcome=None → 不帶總結鍵。"""
    mj = {"perf": {"1Y": 12.0}}
    fd = {"category": _CAT, "moneydj_raw": mj, "metrics": dict(_OK_METRICS)}
    if outcome is not None:
        (fd if top_level else mj)["dividends_fetch_outcome"] = outcome
    return fd


# ───────── Case A：確定不配息 → 規則 (a) 不適用 → 可 🟢 保留 ─────────

@pytest.mark.parametrize("top_level", [False, True], ids=["in_moneydj_raw(Tab2)", "top_level"])
def test_case_a_confirmed_non_distributing_can_keep(top_level):
    r = check_replacement_recommendation(_no_div_fd(_CONFIRMED_NONE, top_level=top_level),
                                         holding_years=4)
    assert r["verdict"] == "keep" and r["emoji"] == "🟢" and r["status"] == "ok"


def test_case_a_flat_health_row_shape_can_keep():
    """健診 row 的 `_fund_raw` 是 auto_fetch_moneydj 的平坦結果（有 perf、無 moneydj_raw）→
    函式內 wrap 後總結鍵落在 moneydj_raw，仍要讀得到。"""
    flat = {"perf": {"1Y": 12.0}, "category": _CAT, "metrics": dict(_OK_METRICS),
            "dividends": [], "dividends_fetch_outcome": dict(_CONFIRMED_NONE)}
    r = check_replacement_recommendation(flat, holding_years=4)
    assert r["verdict"] == "keep" and r["status"] == "ok"


# ───────── Case B：配息基金、配息資料完整 → 規則 (a) 照算 ─────────

def _div_fd(tr1y: float, adr: float):
    m = dict(_OK_METRICS, ret_1y_total=tr1y, ret_1y_div_count=12, annual_div_rate=adr)
    return {"category": _CAT,
            "moneydj_raw": {"perf": {"1Y": tr1y}, "moneydj_div_yield": adr,
                            "dividends_fetch_outcome": {"outcome": "rows", "sources": [],
                                                        "legacy_inline_parse": False,
                                                        "none_evidenced": False}},
            "metrics": m}


def test_case_b_dividend_fund_not_eating_principal_keep():
    r = check_replacement_recommendation(_div_fd(tr1y=12.0, adr=5.0), holding_years=4)
    assert r["verdict"] == "keep" and r["status"] == "ok"
    assert not any(t.startswith("(a)") for t in r["triggered_rules"])


def test_case_b_dividend_fund_eating_principal_triggers_a():
    r = check_replacement_recommendation(_div_fd(tr1y=-3.0, adr=8.0), holding_years=4)
    assert r["verdict"] == "replace"
    assert any(t.startswith("(a)") for t in r["triggered_rules"])


# ───────── Case C：配息資料缺失 → 不得 🟢，⬜ 無法判定列出 (a) ─────────

@pytest.mark.parametrize("outcome", [
    None,                                                                   # 鍵缺（舊快取／未知來源）
    {"outcome": "failed", "sources": [], "none_evidenced": False},
    {"outcome": "undetermined", "sources": [], "none_evidenced": False},
    {"outcome": "none_confirmed", "sources": [], "none_evidenced": False},  # 回空但無認得代碼的證據
    {"outcome": "none_confirmed"},                                          # 證據欄缺
    "none_confirmed",                                                       # 型別不對
], ids=["key_absent", "failed", "undetermined", "none_unevidenced", "evidence_missing", "bad_type"])
def test_case_c_dividend_data_missing_not_keep(outcome):
    r = check_replacement_recommendation(_no_div_fd(outcome), holding_years=4)
    assert r["verdict"] == "unknown" and r["emoji"] == "⬜"
    assert r["status"] == "rules_incomplete" and r["label"] == "無法判定"
    assert "(a)" in r["message"] and "不提供保留結論" in r["message"]
    assert "🟢" not in r["message"]


def test_case_c_red_zone_and_row_label():
    """健診配息表的換標的欄同樣不得出現 🟢。"""
    from services.health.report import build_dividend_summary_row
    row = build_dividend_summary_row(_no_div_fd(None), "MISS1", holding_years=4)
    assert row["換標的建議"] == "⬜ 無法判定"
    assert row["_verdict"] != "keep"


def test_short_holding_still_evaluable_without_outcome():
    """持有 < 1 年：hard rule (a) 本來就不可能觸發 → 判得動（既有語意，本次未改）。"""
    r = check_replacement_recommendation(_no_div_fd(None),
                                         holding_years=0.5)
    assert "(a)" not in r["message"]


def test_outcome_literals_match_l1():
    """replacement 模組刻意不 import L1；字面值須與 fund_orchestration 常數同步。"""
    from repositories.fund.fund_orchestration import DIV_OUTCOME_NONE, DIVIDENDS_OUTCOME_KEY
    assert rep_mod._DIVIDENDS_OUTCOME_KEY == DIVIDENDS_OUTCOME_KEY
    assert rep_mod._DIV_OUTCOME_NONE == DIV_OUTCOME_NONE
