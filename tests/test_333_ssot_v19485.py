"""v19.485 稽核 PR-2:3-3-3 輸入推導 SSOT(H3 成立年數下界 / H4 含息 / P3 複數保護)。

check_333_principle 三態本就正確;本 PR 修**餵進去的兩個輸入**並收成單一權威:
- H3:NAV 首日 proxy 是年齡下界 → proxy < 3 年 → None(⬜,不假 ❌「成立<3年」)
- H4:3 年年化改**含息(wb01)優先**,純NAV 退回並標註(配息型不再假 ❌)
- P3:累積 ≤ −100% → 年化 None(避免複數)

2026-10-23 客戶裁示 3A(有意識的政策變更,不是漏刪):H4 的「wb01 優先 → 純NAV 退回」兩層
**退役**,3Y 含息年化**唯一**來自 `metrics.ret_3y_ann_tr`(配息還原淨值法,與 1Y 同口徑);
缺 → ⬜,不退純淨值、不讀 wb01。H3 / P3 不動(P3 只剩對帳用途 `official_3y_ann_pct`)。
下方 H4 段已改寫為 3A 語意;完整正面測試見 `tests/test_ssot_3a_333.py`。
"""
import datetime as dt

from services.health.dividend import (
    ANN3Y_BASIS_RESTORED,
    ANN3Y_LABEL_HISTORY_SHORT,
    ANN3Y_LABEL_NONE,
    check_333_principle,
    clamp_333_proxy_years,
    derive_ann_3y_for_333,
    derive_years_for_333,
    resolve_ann_3y_for_333_detail,
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


# ── H4(3A 改寫):含息 **唯一**來自 ret_3y_ann_tr;wb01 / 純NAV 不再當值 ────────
def test_ann_3y_uses_restored_total_return_only():
    # 配息還原淨值法的 3Y 含息年化 10.0% → 直接採用,basis 原樣印給使用者
    fd = {"metrics": {"ret_3y_ann_tr": 10.0, "ret_3y_div_count": 36, "ret_3y_ann": 6.0}}
    ann, basis = derive_ann_3y_for_333(fd)
    assert (ann, basis) == (10.0, ANN3Y_BASIS_RESTORED)


def test_ann_3y_income_fund_no_longer_false_fail():
    # 配息型:純NAV 6% 會被判 ❌(≤7%);含息(還原淨值)10% → ✅。verdict 端整合驗證
    fd = {"metrics": {"ret_3y_ann_tr": 10.0, "ret_3y_div_count": 36, "ret_3y_ann": 6.0},
          "dividends": [{"date": "2026-01-05", "amount": 0.05}]}
    ann, _ = derive_ann_3y_for_333(fd)
    r = check_333_principle(5.0, ann)
    assert r["passed"] is True


def test_ann_3y_wb01_perf_is_not_a_value_anymore():
    # 3A:wb01 `perf["3Y"]` 只做對帳(official_3y_ann_pct),**不**當主值 → 無序列 → (None, "—")
    fd = {"perf": {"3Y": 33.1}, "perf_source": "wb01", "metrics": {"ret_3y_ann": 6.0}}
    assert derive_ann_3y_for_333(fd) == (None, ANN3Y_LABEL_NONE)
    d = resolve_ann_3y_for_333_detail(fd)
    assert d["status"] == "unavailable" and d["value_pct"] is None
    assert 9.9 < d["official_3y_ann_pct"] < 10.1       # 對帳欄仍算得出來,只是不進主值


def test_ann_3y_never_falls_back_to_nav_price():
    # 3A:純NAV `ret_3y_ann` / `ret_3y_cum` **不再**退回當含息值
    assert derive_ann_3y_for_333({"perf": {}, "metrics": {"ret_3y_ann": 6.0}}) == (None, ANN3Y_LABEL_NONE)
    assert derive_ann_3y_for_333({"metrics": {"ret_3y_cum": 33.1}}) == (None, ANN3Y_LABEL_NONE)


def test_ann_3y_short_history_is_grey_not_value():
    import pandas as pd
    s = pd.Series([10.0] * 100, index=pd.bdate_range("2026-01-01", periods=100))
    fd = {"metrics": {"ret_3y_ann": 9.0}, "series": s}   # 純NAV 9% 也不准頂上
    assert derive_ann_3y_for_333(fd) == (None, ANN3Y_LABEL_HISTORY_SHORT)


def test_ann_3y_p3_total_loss_guard_on_official():
    # P3(只剩對帳用途):wb01 3Y 累積 −100% → official 年化無定義 → None(非複數 / NaN)
    fd = {"perf": {"3Y": -100.0}, "perf_source": "wb01", "metrics": {}}
    d = resolve_ann_3y_for_333_detail(fd)
    assert d["official_3y_ann_pct"] is None and d["value_pct"] is None


def test_ann_3y_all_missing():
    assert derive_ann_3y_for_333({"metrics": {}}) == (None, ANN3Y_LABEL_NONE)


# ── 生產接線整合(report build_health_analysis_row)──────────────────────
def test_report_verdict_uses_total_return_but_display_stays_nav_price():
    """H4 decouple(3A 語意):verdict 用 `ret_3y_ann_tr`(含息),顯示欄「3Y 年化 %」仍**純NAV**,
    另有「3Y 含息年化 %」= verdict 用的同一值。"""
    from services.health.report import build_health_analysis_row
    fd = {
        "inception_date": "2019-01-01",                 # ≥3 年 → years_ok
        "perf": {"3Y": 33.1},                           # wb01 累積:3A 後只做對帳,不進 verdict
        "metrics": {"ret_3y_ann": 5.0, "ret_3y_ann_tr": 10.0, "nav": 10.0},
        "moneydj_raw": {"perf": {"3Y": 33.1}},
    }
    r = build_health_analysis_row(fd, "TR333")
    assert r["3Y 年化 %"] == 5.0                         # 顯示欄維持純NAV(H4 decouple 不動)
    assert r["3Y 含息年化 %"] == 10.0                    # 3A 新欄 = verdict 用的同一值
    assert r[" 3-3-3"].startswith("✅")                  # verdict 用含息 10% → 通過


def test_report_wb01_only_is_grey_and_does_not_backfill_display():
    """3A:只有 wb01 perf 3Y、無 ret_3y_ann_tr → verdict ⬜;顯示欄不再被 wb01 年化回填。"""
    from services.health.report import build_health_analysis_row
    fd = {
        "inception_date": "2019-01-01",
        "perf": {"3Y": 33.1},
        "metrics": {"nav": 10.0},
        "moneydj_raw": {"perf": {"3Y": 33.1}},
    }
    r = build_health_analysis_row(fd, "WB01ONLY")
    assert r["3Y 年化 %"] is None and r["3Y 含息年化 %"] is None
    assert r[" 3-3-3"].startswith("⬜")


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
