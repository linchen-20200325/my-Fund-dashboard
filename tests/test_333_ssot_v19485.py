"""v19.485 稽核 PR-2:3-3-3 輸入推導 SSOT(H3 成立年數下界 / H4 含息 / P3 複數保護)。

check_333_principle 三態本就正確;本 PR 修**餵進去的兩個輸入**並收成單一權威:
- H3:NAV 首日 proxy 是年齡下界 → proxy < 3 年 → None(⬜,不假 ❌「成立<3年」)
- H4:3 年年化改**含息(wb01)優先**,純NAV 退回並標註(配息型不再假 ❌)
- P3:累積 ≤ −100% → 年化 None(避免複數)
"""
import datetime as dt

from services.health.dividend import (
    check_333_principle,
    clamp_333_proxy_years,
    derive_ann_3y_for_333,
    derive_years_for_333,
)

_TODAY = dt.date(2026, 8, 19)


# ── H3:成立年數下界 clamp ──────────────────────────────────────────────
def test_clamp_proxy_short_returns_none():
    # proxy 1.6 年 < 3 → None(無法反證 <3 年,§1)
    assert clamp_333_proxy_years(1.6, True) is None


def test_clamp_proxy_long_kept_as_lower_bound():
    # proxy 5 年 ≥ 3 → 一定 ≥ 門檻 → 照回
    assert clamp_333_proxy_years(5.0, True) == 5.0


def test_clamp_real_inception_short_kept():
    # 真成立日 1.6 年(非 proxy)→ 精確值原樣回(此檔確實年輕)
    assert clamp_333_proxy_years(1.6, False) == 1.6


def test_clamp_none_stays_none():
    assert clamp_333_proxy_years(None, True) is None
    assert clamp_333_proxy_years(None, False) is None


def test_derive_years_meta_exact():
    y, from_proxy = derive_years_for_333("2019-01-01", "2025-01-01", today=_TODAY)
    assert from_proxy is False
    assert 7.5 < y < 7.8              # 2019→2026 ≈ 7.6 年,用成立日非 NAV proxy


def test_derive_years_proxy_short_none():
    # 無成立日 + NAV 首日僅 ~1.6 年前 → proxy < 3 → None(H3)
    y, from_proxy = derive_years_for_333("", "2025-01-01", today=_TODAY)
    assert from_proxy is True and y is None


def test_derive_years_proxy_long_kept():
    y, from_proxy = derive_years_for_333(None, "2020-01-01", today=_TODAY)
    assert from_proxy is True and y is not None and y >= 3


def test_derive_years_all_missing():
    assert derive_years_for_333(None, None, today=_TODAY) == (None, False)


# ── H4:含息優先 + P3 複數保護 ─────────────────────────────────────────
def test_ann_3y_prefers_total_return_wb01():
    # wb01 含息 3Y 累積 +33.1% → 年化 ≈ 10.0%;即使 metrics 有純NAV 也**優先含息**
    fd = {"perf": {"3Y": 33.1}, "metrics": {"ret_3y_ann": 6.0}}
    ann, basis = derive_ann_3y_for_333(fd)
    assert basis == "含息(wb01)"
    assert 9.9 < ann < 10.1


def test_ann_3y_income_fund_no_longer_false_fail():
    # 配息型:純NAV 6% 會被判 ❌(≤7%);含息 10% → ✅。verdict 端整合驗證
    fd = {"perf": {"3Y": 33.1}, "metrics": {"ret_3y_ann": 6.0}}
    ann, _ = derive_ann_3y_for_333(fd)
    r = check_333_principle(5.0, ann)
    assert r["passed"] is True


def test_ann_3y_falls_back_to_nav_labeled():
    fd = {"perf": {}, "metrics": {"ret_3y_ann": 6.0}}
    ann, basis = derive_ann_3y_for_333(fd)
    assert ann == 6.0 and basis == "純NAV(偏低)"


def test_ann_3y_nav_cum_fallback():
    fd = {"metrics": {"ret_3y_cum": 33.1}}
    ann, basis = derive_ann_3y_for_333(fd)
    assert basis == "純NAV(偏低)" and 9.9 < ann < 10.1


def test_ann_3y_p3_total_loss_guard():
    # P3:3Y 累積 −100% → 年化無定義 → None(非複數 / NaN)
    fd = {"perf": {"3Y": -100.0}}
    ann, basis = derive_ann_3y_for_333(fd)
    assert ann is None and basis == "—"


def test_ann_3y_p3_below_total_loss_guard():
    fd = {"metrics": {"ret_3y_cum": -120.0}}
    assert derive_ann_3y_for_333(fd) == (None, "—")


def test_ann_3y_all_missing():
    assert derive_ann_3y_for_333({"metrics": {}}) == (None, "—")


# ── 生產接線整合(report build_health_analysis_row)──────────────────────
def test_report_verdict_uses_total_return_but_display_stays_nav_price():
    """H4 decouple:report 3-3-3 verdict 用**含息**(perf 3Y),顯示欄「3Y 年化 %」仍**純NAV**。"""
    from services.health.report import build_health_analysis_row
    fd = {
        "inception_date": "2019-01-01",                 # ≥3 年 → years_ok
        "perf": {"3Y": 33.1},                           # 含息累積 → 年化 ~10% > 7%
        "metrics": {"ret_3y_ann": 5.0, "nav": 10.0},    # 純NAV 顯示值(< 7%)
        "moneydj_raw": {"perf": {"3Y": 33.1}},
    }
    r = build_health_analysis_row(fd, "TR333")
    assert r["3Y 年化 %"] == 5.0                         # 顯示欄維持純NAV(H4 decouple 不動)
    assert r[" 3-3-3"].startswith("✅")                  # verdict 用含息 10% → 通過


def test_report_h3_short_nav_no_inception_is_grey_not_red():
    """H3:無成立日 + 短 NAV(proxy<3年)→ report 3-3-3 = ⬜(資料不足),非 ❌(假報成立<3年)。"""
    import datetime as _dt
    import pandas as pd
    from services.health.report import build_health_analysis_row
    idx = pd.date_range(end=_dt.date(2026, 8, 19), periods=40, freq="D")   # ~40 天 << 3 年
    s = pd.Series([10.0 + i * 0.01 for i in range(40)], index=idx)
    fd = {"series": s, "metrics": {"nav": 10.39}, "perf": {}}
    r = build_health_analysis_row(fd, "SHORT333")
    assert r[" 3-3-3"].startswith("⬜")                  # proxy<3年 → None → ⬜(非 ❌)
