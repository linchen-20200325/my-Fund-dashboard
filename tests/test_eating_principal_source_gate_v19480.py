"""v19.480 稽核 PR-1 → 2026-10-23 裁示 1B 改寫:吃本金判定只認「本地還原含息」。

v19.480 的守門是「拒收不可信報酬基準」(B1 短窗累積 / B2 純淨值)→ ⚪ 不報假 🔴;
裁示 1B 後 SSOT **根本不再產出**那些基準 —— 只有一層(還原淨值法、窗口 ≥ 350 天),
其餘一律「⬜ 資料未備／無法判定」+ `reason`。本檔改守:
- 純淨值 / 短窗 / 只有官方 wb01 → 一律灰色 dict(`eating_principal is None`,不是 False)
- 真正的還原含息(ret_1y_total + 足夠窗口 + 窗內有配息)→ 正常判定(綠 / 黃 / 紅)
- 來源辨識 helper 對 SSOT 新標籤的行為
"""

from services.fund_total_return import (
    SRC_SELF_RESTORED,
    SRC_UNAVAILABLE_PREFIX,
    is_nav_only_1y_source,
    is_partial_window_1y_source,
    is_too_short_1y_source,
    resolve_1y_total_return,
)
from services.health.dividend import (
    EATING_STATUS_UNAVAILABLE,
    check_eating_principal_1y_mk,
)


# ── 來源辨識 helper ─────────────────────────────────────────────────────
def test_legacy_label_classifiers_still_recognise_old_labels():
    """舊標籤的辨識保留(UI 既有分支相容),但 SSOT 已不會產出它們。"""
    assert is_partial_window_1y_source("自算含息（僅 200 天窗口）") is True
    assert is_partial_window_1y_source("自算含息") is False
    assert is_partial_window_1y_source("—（僅 90 天資料，不足以推算一年）") is False
    assert is_nav_only_1y_source("自算（僅淨值，不含配息）") is True
    assert is_nav_only_1y_source("MoneyDJ 官方") is False
    assert is_too_short_1y_source("—（僅 90 天資料，不足以推算一年）") is True


def test_ssot_labels_never_match_retired_classifiers():
    """SSOT 產出的每一種標籤都不該再被辨識成「外推 / 短窗累積 / 純淨值」。"""
    labels = [
        resolve_1y_total_return({"metrics": {"ret_1y_total": 3.0, "ret_1y_window_days": 365}})["label"],
        resolve_1y_total_return({"metrics": {"ret_1y_total": 3.0, "ret_1y_window_days": 200}})["label"],
        resolve_1y_total_return({"metrics": {"ret_1y": 2.0}})["label"],
        resolve_1y_total_return({"metrics": {"ret_1y_total": 3.0, "ret_1y_window_days": 365,
                                             "ret_1y_div_count": 0},
                                 "moneydj_div_yield": 5.0})["label"],
    ]
    for _l in labels:
        assert is_partial_window_1y_source(_l) is False, _l
        assert is_nav_only_1y_source(_l) is False, _l
        assert "外推年化" not in _l


def test_too_short_matches_window_short_and_no_series_only():
    r_short = resolve_1y_total_return({"metrics": {"ret_1y_total": 3.0, "ret_1y_window_days": 90}})
    r_none = resolve_1y_total_return({"metrics": {}})
    r_div = resolve_1y_total_return({"metrics": {"ret_1y_total": 3.0, "ret_1y_window_days": 365,
                                                 "ret_1y_div_count": 0},
                                     "moneydj_div_yield": 5.0})
    assert (r_short["reason"], r_none["reason"], r_div["reason"]) == (
        "window_short", "no_series", "dividend_data_missing")
    assert is_too_short_1y_source(r_short["label"]) is True
    assert is_too_short_1y_source(r_none["label"]) is True
    assert is_too_short_1y_source(r_div["label"]) is False


# ── 端到端:check_eating_principal_1y_mk ─────────────────────────────────
def _grey(res, reason=None):
    ok = (res is not None and res.get("alert_level") == "grey"
          and res.get("status") == EATING_STATUS_UNAVAILABLE
          and res.get("eating_principal") is None)
    if reason is not None:
        ok = ok and res.get("reason") == reason
    return ok


def test_nav_only_source_refuses_verdict_not_red():
    """純 NAV +2% vs 配息 6% —— 舊碼 2<6 → 🔴;現在純淨值根本不是來源 → 灰、reason no_series。"""
    fund = {"metrics": {"ret_1y": 2.0, "annual_div_rate": 6.0}}
    res = check_eating_principal_1y_mk(fund)
    assert _grey(res, "no_series"), res
    assert (res.get("_tr1y_method") or "").startswith(SRC_UNAVAILABLE_PREFIX)
    assert res.get("_adr_pct") == 6.0, "tr1y 缺席時 adr 仍要帶出去(換標建議規則 (b) 用)"


def test_partial_window_source_refuses_verdict_not_red():
    """短窗(200 天)→ 灰、reason window_short,不拿短窗累積去比年化配息率。"""
    fund = {"metrics": {"ret_1y_total": 3.0, "ret_1y_window_days": 200,
                        "annual_div_rate": 6.0}}
    res = check_eating_principal_1y_mk(fund)
    assert _grey(res, "window_short"), res
    assert res.get("_tr1y_window_days") == 200


def test_official_wb01_only_is_unavailable_not_judged():
    """只有官方 wb01 含息(8%)、沒有本地還原值 → 不判(灰),官方值不當主值。"""
    fund = {"perf": {"1Y": 8.0}, "perf_source": "wb01",
            "metrics": {"annual_div_rate": 6.0}, "moneydj_div_yield": 6.0}
    res = check_eating_principal_1y_mk(fund)
    assert _grey(res, "no_series"), res


def test_restored_with_zero_dividends_in_window_not_laundered():
    """配息基金、還原窗口內 0 筆配息 → 還原序列 ≡ 純淨值 → 灰(dividend_data_missing)。"""
    fund = {
        "moneydj_div_yield": 6.0,
        "metrics": {"ret_1y_total": 2.0, "ret_1y_window_days": 365,
                    "ret_1y_div_count": 0, "annual_div_rate": 6.0},
    }
    res = check_eating_principal_1y_mk(fund)
    assert _grey(res, "dividend_data_missing"), res


def test_restored_with_real_dividends_is_judged():
    """還原含息 7% vs 配息 3%(窗內有配息)→ 正常判定 🟢。"""
    fund = {
        "moneydj_div_yield": 3.0,
        "metrics": {"ret_1y_total": 7.0, "ret_1y_window_days": 365,
                    "ret_1y_div_count": 1, "annual_div_rate": 3.0},
    }
    res = check_eating_principal_1y_mk(fund)
    assert res is not None and res.get("alert_level") == "green", res
    assert res.get("eating_principal") is False
    assert res.get("_tr1y_method") == SRC_SELF_RESTORED
    assert res.get("_tr1y_window_days") == 365 and res.get("_adr_source") == "divs_12m_sum"


def test_restored_genuine_eating_still_red():
    """還原含息 1% vs 配息 8% → 真吃本金 → 🔴(新 gate 不誤殺真紅燈)。"""
    fund = {"metrics": {"ret_1y_total": 1.0, "ret_1y_window_days": 365,
                        "ret_1y_div_count": 12, "annual_div_rate": 8.0},
            "moneydj_div_yield": 8.0}
    res = check_eating_principal_1y_mk(fund)
    assert res is not None and res.get("eating_principal") is True
    assert res.get("alert_level") == "red" and res.get("gap_pct") == 7.0
