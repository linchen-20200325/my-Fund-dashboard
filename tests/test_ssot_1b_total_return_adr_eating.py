"""2026-10-23 客戶裁示 1B(docs/v2/64 §4 #1/#4/#5;BL-0420)—— L2 SSOT 收斂守衛。

三件事各只有**一個**算法、一個住址:
  - 1Y 含息報酬:本地配息還原淨值法 `metrics.ret_1y_total`(窗口 ≥ 350 天、窗內有配息)
    → `services.fund_total_return.resolve_1y_total_return`
  - 年化配息率:近 12 個月實際配息合計 ÷ 最新淨值 × 100
    → `services.fund_service.calc_metrics` 寫、`services.health.dividend.resolve_dividend_rate_12m` 讀
  - 吃本金:上述兩個輸入 → `check_eating_principal_1y_mk` → `dividend_safety`(2pp 黃燈帶不動)
Missing 永不得變 0 / False / 中性 —— 一律顯式 None + status/reason。
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from services.fund_service import calc_metrics, finalize_fund_metrics
from services.fund_total_return import (
    SRC_NONE,
    SRC_SELF_RESTORED,
    SRC_UNAVAILABLE_PREFIX,
    compute_1y_total_return,
    resolve_1y_total_return,
)
from services.health.dividend import (
    EATING_STATUS_UNAVAILABLE,
    _resolve_adr_with_fallback,
    check_eating_principal_1y_mk,
    resolve_dividend_rate_12m,
)
from shared.signal_thresholds import (
    NEAR_DIVIDEND_WARNING_PCT,
    RET_1Y_RESTORED_MIN_WINDOW_DAYS,
)


# ── 合成序列:NAV 10 → 9.6 線性、253 個交易日、月配 0.06(對齊淨值日)──────────
def _synthetic(n_days: int = 253, monthly_div: float | None = 0.06):
    idx = pd.bdate_range("2025-10-01", periods=n_days)
    s = pd.Series(np.linspace(10.0, 9.6, n_days), index=idx)
    divs = []
    if monthly_div:
        # 每 21 個交易日一筆,**日期對齊淨值日**(還原法以日期 left-join,落在非淨值日的配息不會被加回)
        divs = [{"date": idx[-1 - 21 * i].strftime("%Y-%m-%d"), "amount": monthly_div}
                for i in range(12)]
    return s, divs


def _restored_expectation(s: pd.Series, divs: list) -> float:
    """獨立重算還原淨值法:Adj_NAV_T / Adj_NAV_0 − 1,窗口起點 = s.index[-252]。"""
    start = s.index[-252]
    fac = 1.0
    for d in divs:
        fac *= 1.0 + d["amount"] / float(s.loc[pd.Timestamp(d["date"])])
    return (float(s.iloc[-1]) * fac / float(s.loc[start]) - 1.0) * 100.0


def _fund_from_metrics(m: dict, s=None, divs=None, **extra) -> dict:
    fd = {"metrics": m, "series": s, "dividends": divs or [], "moneydj_raw": {}}
    fd.update(extra)
    return fd


# ── (a) 合成序列:還原值、配息率、吃本金 2pp 帶 ──────────────────────────────
def test_a_synthetic_series_restored_return_adr_and_eating_band():
    s, divs = _synthetic()
    m = calc_metrics(s, divs)
    # 1Y 含息 = 還原淨值法(與獨立重算一致,窗口 ≥ 350 天、12 筆配息都被加回)
    assert m["ret_1y_window_days"] >= RET_1Y_RESTORED_MIN_WINDOW_DAYS
    assert m["ret_1y_div_count"] == 12
    assert math.isclose(m["ret_1y_total"], _restored_expectation(s, divs), abs_tol=0.01)
    assert 2.5 < m["ret_1y_total"] < 3.6, m["ret_1y_total"]   # 淨值 −4% + 12 × 0.06 再投資
    # 年化配息率 = 近 12 個月實配合計 ÷ 最新淨值 × 100 = 0.72 / 9.6 × 100
    assert math.isclose(m["annual_div_rate"], 0.72 / 9.6 * 100, abs_tol=0.01)
    assert m["annual_div_rate_div_count"] == 12 and m["annual_div"] == 0.72
    assert m["monthly_div"] == 0.06
    assert m["annual_div_rate_window_end"] == s.index[-1].date().isoformat()

    fd = _fund_from_metrics(m, s, divs)
    r = resolve_1y_total_return(fd)
    assert r["status"] == "ok" and r["value_pct"] == m["ret_1y_total"]
    assert r["source"] == SRC_SELF_RESTORED and r["label"] == SRC_SELF_RESTORED
    adr, src = _resolve_adr_with_fallback(fd)
    assert adr == m["annual_div_rate"] and src == "divs_12m_sum"

    # 吃本金:gap = 7.5 − 3.3 ≈ 4.2pp > 2pp → 🔴;eating_principal 為真布林
    out = check_eating_principal_1y_mk(fd)
    assert out["alert_level"] == "red" and out["eating_principal"] is True
    assert math.isclose(out["gap_pct"], adr - r["value_pct"], abs_tol=0.01)
    assert out["_tr1y_method"] == SRC_SELF_RESTORED and out["_adr_pct"] == adr
    assert out["_tr1y_window_days"] == m["ret_1y_window_days"] and out["_tr1y_meta"] is None
    assert out["nav_warning"] is None   # nav_change 用純淨值 ret_1y(−3.98%),未達 −5% 門檻


@pytest.mark.parametrize("gap", [0.0, NEAR_DIVIDEND_WARNING_PCT, NEAR_DIVIDEND_WARNING_PCT + 0.01])
def test_a2_eating_band_is_the_existing_2pp_ssot(gap):
    """2pp 黃燈帶照舊走 `dividend_safety` SSOT:gap ≤ 0 綠、0 < gap ≤ 2 黃、> 2 紅。"""
    adr = 6.0
    fd = _fund_from_metrics({"ret_1y_total": adr - gap, "ret_1y_window_days": 365,
                             "ret_1y_div_count": 12, "annual_div_rate": adr})
    out = check_eating_principal_1y_mk(fd)
    expect = "green" if gap <= 0 else ("yellow" if gap <= NEAR_DIVIDEND_WARNING_PCT else "red")
    assert out["alert_level"] == expect, out


# ── (b) 只有官方 wb01 perf["1Y"]、無還原值 → unavailable,官方值只在 official_1y_pct ──
def test_b_official_perf_1y_without_restored_value_is_unavailable():
    fd = {"metrics": {}, "moneydj_raw": {"perf": {"1Y": 8.8}, "perf_source": "wb01",
                                         "moneydj_div_yield": 5.0}}
    r = resolve_1y_total_return(fd)
    assert r["status"] == "unavailable" and r["value_pct"] is None
    assert r["official_1y_pct"] == 8.8 and r["source"] == SRC_NONE
    assert r["label"].startswith(SRC_UNAVAILABLE_PREFIX)
    assert compute_1y_total_return(fd) == (None, r["label"])
    out = check_eating_principal_1y_mk(fd)
    assert out["status"] == EATING_STATUS_UNAVAILABLE and out["eating_principal"] is None
    # 有還原值時官方值仍只做對帳,不影響主值
    fd2 = {"metrics": {"ret_1y_total": 3.0, "ret_1y_window_days": 365, "ret_1y_div_count": 12},
           "moneydj_raw": {"perf": {"1Y": 8.8}, "perf_source": "wb01"}}
    r2 = resolve_1y_total_return(fd2)
    assert r2["value_pct"] == 3.0 and r2["official_1y_pct"] == 8.8


# ── (c) 窗口 200 天 → window_short ───────────────────────────────────────────
def test_c_window_200_days_is_unavailable_window_short():
    fd = _fund_from_metrics({"ret_1y_total": 3.0, "ret_1y_window_days": 200,
                             "annual_div_rate": 6.0})
    r = resolve_1y_total_return(fd)
    assert r["status"] == "unavailable" and r["reason"] == "window_short"
    assert r["window_days"] == 200 and "200" in r["label"]
    out = check_eating_principal_1y_mk(fd)
    assert out["alert_level"] == "grey" and out["reason"] == "window_short"
    assert out["eating_principal"] is None and out["_adr_pct"] == 6.0
    assert out["_tr1y_window_days"] == 200 and out["coverage"] is None and out["gap_pct"] is None


# ── (d) 配息基金但窗內 0 筆 → dividend_data_missing;吃本金灰、eating_principal None ──
def test_d_dividend_fund_with_zero_dividends_in_window_is_unavailable():
    fd = {"metrics": {"ret_1y_total": 3.0, "ret_1y_window_days": 365, "ret_1y_div_count": 0,
                      "annual_div_rate": 4.0},
          "moneydj_raw": {"moneydj_div_yield": 5.0}}
    r = resolve_1y_total_return(fd)
    assert r["status"] == "unavailable" and r["reason"] == "dividend_data_missing"
    out = check_eating_principal_1y_mk(fd)
    assert out["status"] == EATING_STATUS_UNAVAILABLE and out["alert_level"] == "grey"
    assert out["reason"] == "dividend_data_missing" and out["eating_principal"] is None
    # 連配息率都算不出來(窗內 0 筆、只有 wb05)→ 同樣灰、`_adr_pct` None,不拿官方 5% 頂替
    fd2 = {"metrics": {"ret_1y_total": 3.0, "ret_1y_window_days": 365, "ret_1y_div_count": 0,
                       "annual_div_rate": None},
           "moneydj_raw": {"moneydj_div_yield": 5.0}}
    adr, src = _resolve_adr_with_fallback(fd2)
    assert adr is None and src == "⬜ 配息資料未備"
    out2 = check_eating_principal_1y_mk(fd2)
    assert out2["alert_level"] == "grey" and out2["eating_principal"] is None
    assert out2["_adr_pct"] is None and out2["reason"] == "dividend_data_missing"


# ── (e) 純累積基金 → ok 且值 == 純淨值報酬;adr (None, "—");吃本金 None ─────────
def test_e_accumulation_fund_restored_equals_pure_nav_and_no_eating_verdict():
    s, _ = _synthetic(monthly_div=None)
    m = calc_metrics(s, [])
    assert m["ret_1y_div_count"] == 0
    assert m["ret_1y_total"] == m["ret_1y"], "無配息 → 還原序列 ≡ 原序列"
    assert m["annual_div_rate"] is None and m["annual_div"] is None and m["monthly_div"] is None
    fd = _fund_from_metrics(m, s, [])
    r = resolve_1y_total_return(fd)
    assert r["status"] == "ok" and r["value_pct"] == m["ret_1y"]
    assert _resolve_adr_with_fallback(fd) == (None, "—")
    assert resolve_dividend_rate_12m(fd)["reason"] == "no_dividend"
    assert check_eating_principal_1y_mk(fd) is None


# ── (f) annual_div_rate:窗內無配息 → None,不是 0 ────────────────────────────
def test_f_annual_div_rate_is_none_not_zero_when_no_dividend_in_window():
    s, _ = _synthetic(monthly_div=None)
    old = [{"date": (s.index[0] - pd.Timedelta(days=400)).strftime("%Y-%m-%d"), "amount": 0.5}]
    m = calc_metrics(s, old)
    assert m["annual_div_rate"] is None and m["annual_div_rate_div_count"] == 0
    assert m["annual_div"] is None and m["monthly_div"] is None
    assert m["ret_1y_div_count"] == 0
    # 讀端:有歷史配息紀錄 → 配息資料未備(不是「無配息」)
    fd = _fund_from_metrics(m, s, old)
    rr = resolve_dividend_rate_12m(fd)
    assert rr["status"] == "unavailable" and rr["reason"] == "dividend_data_missing"
    assert rr["value_pct"] is None and rr["div_count"] == 0
    # metrics 無 annual_div_rate 鍵時以 dividends + nav 現算(anchor = 最後 NAV 日)
    fd2 = {"metrics": {"nav": 9.6}, "series": s,
           "dividends": [{"date": s.index[-5].strftime("%Y-%m-%d"), "amount": 0.24}]}
    rr2 = resolve_dividend_rate_12m(fd2)
    assert rr2["status"] == "ok" and math.isclose(rr2["value_pct"], 0.24 / 9.6 * 100)
    assert rr2["div_count"] == 1 and rr2["window_end"] == s.index[-1].date().isoformat()
    assert rr2["label"] == "divs_12m_sum"


def test_f2_official_wb05_is_never_the_adr_value():
    fd = {"metrics": {"nav": 10.0}, "moneydj_raw": {"moneydj_div_yield": 9.0}, "dividends": []}
    rr = resolve_dividend_rate_12m(fd)
    assert rr["value_pct"] is None and rr["official_wb05_pct"] == 9.0
    assert rr["reason"] == "dividend_data_missing"
    assert _resolve_adr_with_fallback(fd) == (None, "⬜ 配息資料未備")


# ── finalize_fund_metrics:不再注入 perf["1Y"] / local_calc;對帳保留 ───────────
def test_finalize_no_longer_injects_local_calc_into_perf(monkeypatch):
    import services.fund_service as fs
    monkeypatch.setattr(fs, "_merge_nav_history_series", lambda s, code, oauth_client=None: (s, None))
    s, divs = _synthetic()
    result = {"series": s, "dividends": divs, "fund_code": "SYN", "perf": {},
              "moneydj_div_yield": 7.0}
    finalize_fund_metrics(result)
    assert result["perf"].get("1Y") is None, "perf 只放官方值,本地還原值不得寫進去"
    assert result.get("perf_source") != "local_calc"
    m = result["metrics"]
    assert m["ret_1y_total"] is not None and m["ret_1y_window_days"] >= RET_1Y_RESTORED_MIN_WINDOW_DAYS
    # 對帳:self = 還原值;mj 缺(無 wb01)→ b_missing
    rec = m["ret_1y_reconcile"]
    assert math.isclose(rec["value_a"], m["ret_1y_total"] / 100.0) and rec["value_b"] is None
    dy = m["div_yield_reconcile"]
    assert math.isclose(dy["value_a"], m["annual_div_rate"] / 100.0)
    assert math.isclose(dy["value_b"], 0.07)


def test_finalize_reconcile_uses_wb01_only_and_short_window_self_is_dropped(monkeypatch):
    import services.fund_service as fs
    monkeypatch.setattr(fs, "_merge_nav_history_series", lambda s, code, oauth_client=None: (s, None))
    s, _ = _synthetic(n_days=120, monthly_div=None)   # 跨度 < 350 天 → 還原值不當一年報酬進對帳
    result = {"series": s, "dividends": [], "fund_code": "SHORT",
              "perf": {"1Y": 4.0}, "perf_source": "wb01"}
    finalize_fund_metrics(result)
    m = result["metrics"]
    assert m["ret_1y_window_days"] < RET_1Y_RESTORED_MIN_WINDOW_DAYS
    rec = m["ret_1y_reconcile"]
    assert rec["value_a"] is None and math.isclose(rec["value_b"], 0.04)
    assert result["perf"]["1Y"] == 4.0 and result["perf_source"] == "wb01"
    # perf_source 不是 wb01 → 官方值不進對帳
    result2 = {"series": s, "dividends": [], "fund_code": "UNL", "perf": {"1Y": 4.0}}
    finalize_fund_metrics(result2)
    assert "ret_1y_reconcile" not in result2["metrics"]


# ── services 層 consumer 改讀 SSOT ────────────────────────────────────────────
def test_portfolio_alpha_and_rank_read_ssot_not_perf():
    from services.portfolio_service import (
        calc_fund_factor_score,
        get_factor_availability,
        rank_funds_within_portfolio,
    )
    ssot_fd = {"perf": {"1Y": 20.0}, "perf_source": "wb01",
               "metrics": {"ret_1y_total": 5.0, "ret_1y_window_days": 365,
                           "ret_1y_div_count": 12, "annual_div_rate": 3.0},
               "moneydj_raw": {}}
    alpha = calc_fund_factor_score(ssot_fd)["factors"]["Alpha"]["value"]
    assert math.isclose(alpha, 5.0 - 3.0), "Alpha 須用還原值 5,不是官方 perf 20"
    assert get_factor_availability(ssot_fd)["Alpha"] is True
    only_perf = {"perf": {"1Y": 20.0}, "perf_source": "wb01",
                 "metrics": {"annual_div_rate": 3.0}, "moneydj_raw": {}}
    assert "Alpha" not in calc_fund_factor_score(only_perf)["factors"]
    assert get_factor_availability(only_perf)["Alpha"] is False

    funds = [
        {"code": "A", "moneydj_raw": {"perf": {"1Y": 50.0}, "perf_source": "wb01"},
         "metrics": {"ret_1y_total": 1.0, "ret_1y_window_days": 365}},
        {"code": "B", "moneydj_raw": {},
         "metrics": {"ret_1y_total": 9.0, "ret_1y_window_days": 365}},
        {"code": "C", "moneydj_raw": {"perf": {"1Y": 99.0}, "perf_source": "wb01"},
         "metrics": {"ret_1y": 30.0}},    # 只有純淨值 / 官方值 → 不參與排名
    ]
    out = rank_funds_within_portfolio(funds)
    assert out["B"]["return_rank"] == 1 and out["A"]["return_rank"] == 2
    assert out["C"]["return_rank"] is None and out["A"]["return_n"] == 2


def test_ai_prompt_snapshot_uses_ssot_and_never_fills_zero(monkeypatch):
    import services.ai_service as ai
    captured = {}

    def _fake_llm(prompt, *a, **kw):
        captured["prompt"] = prompt
        return "ok"
    monkeypatch.setattr(ai, "call_llm", _fake_llm)
    funds = [
        {"loaded": True, "code": "SSOT", "name": "有還原值", "invest_twd": 1000,
         "metrics": {"ret_1y_total": 2.5, "ret_1y_window_days": 365, "ret_1y_div_count": 12,
                     "annual_div_rate": 8.0},
         "moneydj_raw": {"perf": {"1Y": 30.0}, "perf_source": "wb01", "moneydj_div_yield": 1.0}},
        {"loaded": True, "code": "NONE", "name": "只有官方值", "invest_twd": 1000,
         "metrics": {}, "moneydj_raw": {"perf": {"1Y": 30.0}, "perf_source": "wb01",
                                         "moneydj_div_yield": 6.0}},
    ]
    ai.analyze_portfolio_mk_advisor("k", funds, {"phase": "x"})
    p = captured.get("prompt") or ""
    assert "1Y含息 2.50%" in p and "配息率 8.0%" in p and "吃本金(5.5pp)" in p
    assert "1Y含息 N/A(" in p and "配息率 N/A(" in p
    assert "30.0" not in p.split("`NONE`")[1].split("\n")[0], "官方 perf 30% 不得進 prompt 當值"
    assert "配息率 0.0%" not in p and "1Y含息 0" not in p


def test_dividend_safety_docstring_names_the_only_caller():
    from services.portfolio_service import dividend_safety
    assert "check_eating_principal_1y_mk" in (dividend_safety.__doc__ or "")
