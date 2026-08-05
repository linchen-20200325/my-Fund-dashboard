# -*- coding: utf-8 -*-
"""風險指標「揭露鏈」回歸網 —— 修的是「算對了但沒人看得到」。

前一輪被 QA Reject 的主因不是數學,是**淨效果為零**:樣本門檻提高後,
`m["sharpe"]` 仍由 wb07 供應、`mixed_period_warning` 全 repo **production 0 reader**,
線上那個「Sharpe 1Y = 0.28」與「1Y 含息 = −2.71%」並列的矛盾畫面**完全沒變**。
本檔守四件事:

1. **switch_score 缺值 ≠ 壞值**(§1):`MIN_OBS_MAX_DRAWDOWN` 上調後,短歷史基金的
   Max DD 變 None,原碼固定分母 100 會讓它憑空少 20 分,與「MaxDD −40% 拿 0 分」
   在畫面上無法區分 —— 改為**只計入有資料的維度**再放回 0-100。
2. **對帳降級須具名**(§4.3 + §1):自算 Sharpe 被 250 筆門檻擋掉時,雙演算法對帳恆為
   `a_missing`;必須在 meta 說明是「本地根本沒算」而非「兩邊不合」。
3. **Calmar 分子分母同源**(C-4):分子原取自純價格 NAV、分母取自含息還原序列;
   月配息基金可讓 Calmar **連正負號都相反**。
4. **UI 真的接線**(source-scan):tab2 必須讀 `mixed_period_warning` /
   `reconcile_blocked_reason`,且不得殘留已過時的 60 筆 / 1Y fallback 文案。

三個最容易讓這段程式出錯的輸入(§6):
A. **四維全有資料** → 重正規化必須**位元等價**於原始加總(否則悄悄改了所有既有分數)。
B. **vs 大盤% 有值但 ≤ 0** → 這是「真的沒有超額」,計 0 分且**留在分母**,不可與缺值同路。
C. **高配息 + 價格下跌的基金** → 純價格 3Y 年化為負、含息為正,Calmar 正負號翻轉。
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

import fund_fetcher  # noqa: F401  解 circular import
from services.fund_service import (
    MIN_OBS_CALMAR,
    TRADING_DAYS_PER_YEAR,
    _total_return_nav,
    calc_metrics,
)
from services.switch_strategy import switch_score
from shared.switch_thresholds import (
    SWITCH_ALPHA_POINTS,
    SWITCH_MAXDD_TIERS,
    SWITCH_SHARPE_TIERS,
    SWITCH_TR_TIERS,
)

_MAXDD_WEIGHT = max(p for _c, p in SWITCH_MAXDD_TIERS)
_TOTAL = (max(p for _c, p in SWITCH_TR_TIERS)
          + max(p for _c, p in SWITCH_SHARPE_TIERS)
          + _MAXDD_WEIGHT + int(SWITCH_ALPHA_POINTS))


# ══════════════════════════════════════════════════════════════════
# 1. switch_score:缺值不得偽裝成壞值(§1)
# ══════════════════════════════════════════════════════════════════
class TestSwitchScoreCoverage:
    def test_missing_maxdd_is_not_scored_like_bad_maxdd(self):
        """核心迴歸 —— **修正前必紅**。

        修正前:缺 MaxDD 與 MaxDD=−40%(tier 落底)**同為 +0 分**,分母都是 100
        → 兩者分數相同(80),使用者無從分辨。修正後缺值退出分母 → 80/80 → 100。
        """
        _best = switch_score(8.0, 1.0, -10.0, 5.0)      # 四維全滿
        _bad_dd = switch_score(8.0, 1.0, -40.0, 5.0)    # MaxDD 真的很差 → 該項 0 分
        _no_dd = switch_score(8.0, 1.0, None, 5.0)      # MaxDD 缺
        assert _best == _TOTAL
        assert _bad_dd == _TOTAL - _MAXDD_WEIGHT        # 壞值照扣,語意不變
        assert _no_dd > _bad_dd, (
            "§1:缺 MaxDD 不得與『MaxDD 很差』得到同一個分數")
        assert _no_dd == _TOTAL                          # 有證據的維度全拿滿

    def test_missing_vs_market_is_not_scored_like_negative_alpha(self):
        """易錯輸入 B —— **修正前必紅**:vs 大盤% 缺 vs 有值但為負,原碼皆 +0。"""
        _neg_vm = switch_score(8.0, 1.0, -10.0, -2.0)
        _no_vm = switch_score(8.0, 1.0, -10.0, None)
        assert _neg_vm == _TOTAL - int(SWITCH_ALPHA_POINTS)
        assert _no_vm > _neg_vm, "缺 vs大盤% ≠ 沒有超額報酬"

    def test_full_coverage_is_bitwise_unchanged(self):
        """易錯輸入 A:四維全有值 → 走原始加總(不繞浮點),既有分數零變化。

        (修正前也綠 —— 這條是**防止修正順手改壞既有行為**的護欄,不是 bug 偵測器。)
        """
        assert switch_score(8.0, 1.0, -10.0, 5.0) == 100
        assert switch_score(3.0, 0.5, -20.0, -2.0) == 55
        # 全落底(vs大盤 **有值**但為負 → 0 分且留在分母)→ 0/100
        assert switch_score(-15.0, -0.5, -30.0, -1.0) == 0

    def test_core_missing_still_returns_none(self):
        """核心維度(1Y 含息 / Sharpe)缺 → 仍是 None,不被重正規化救活(§1)。"""
        assert switch_score(None, 1.0, -10.0, 5.0) is None
        assert switch_score(8.0, None, -10.0, 5.0) is None

    def test_coverage_side_car_discloses_missing(self):
        """§1「填補須帶旗標」 —— **修正前必紅**(舊簽名無 coverage_out → TypeError)。"""
        cov = {}
        _sc = switch_score(8.0, 1.0, None, 5.0, coverage_out=cov)
        assert _sc is not None
        assert cov["rescaled"] is True
        assert cov["missing"] == ["Max DD %"]
        assert cov["available"] == _TOTAL - _MAXDD_WEIGHT
        assert cov["total"] == _TOTAL
        assert math.isclose(cov["coverage_pct"],
                            (_TOTAL - _MAXDD_WEIGHT) / _TOTAL * 100.0,
                            rel_tol=0, abs_tol=0.05)
        assert cov["reason"] and "缺值不計為壞值" in cov["reason"]

    def test_coverage_side_car_clean_when_full(self):
        cov = {}
        switch_score(8.0, 1.0, -10.0, 5.0, coverage_out=cov)
        assert cov["rescaled"] is False and cov["missing"] == []
        assert cov["reason"] is None

    def test_coverage_side_car_on_none_path(self):
        cov = {}
        assert switch_score(None, None, None, None, coverage_out=cov) is None
        assert "1Y 含息 %" in cov["missing"] and "Sharpe 1Y" in cov["missing"]
        assert cov["reason"] and "核心維度缺值" in cov["reason"]


# ══════════════════════════════════════════════════════════════════
# 2. 對帳降級具名(C-3,§4.3 + §1)
# ══════════════════════════════════════════════════════════════════
def _nav(n: int, seed: int = 42, mu: float = 0.0004, sigma: float = 0.01) -> pd.Series:
    rng = np.random.default_rng(seed)
    return pd.Series(10.0 * np.exp(np.cumsum(rng.normal(mu, sigma, n))),
                     index=pd.date_range("2018-01-01", periods=n, freq="B"))


class TestReconcileDowngradeDisclosed:
    def test_reconcile_blocked_reason_present_when_self_calc_gated(self):
        """**修正前必紅**(meta 無此 key → KeyError)。

        wb07 有 Sharpe、本地序列 < 250 筆 → `sharpe_reconcile` 恆 a_missing。
        必須具名說明是「本地自算被樣本門檻擋掉」,否則 §4.3 的雙演算法對帳
        被靜默關掉而 UI 只顯示一個看不懂的 ⬜。
        """
        m = calc_metrics(_nav(120), [],
                         risk_override={"risk_table": {"一年": {"標準差": 10.0,
                                                               "Sharpe": 0.28}}})
        _meta = m["risk_metric_meta"]["sharpe"]
        assert _meta["self_calc_value"] is None
        _blocked = _meta["reconcile_blocked_reason"]
        assert _blocked and "對帳停用" in _blocked, _blocked
        assert "樣本不足" in _blocked
        # 對帳 dict 本身確實降級為 a_missing(釘住兩者一致)
        assert (m.get("sharpe_reconcile") or {}).get("status") == "a_missing"

    def test_no_blocked_reason_when_both_available(self):
        m = calc_metrics(_nav(400), [],
                         risk_override={"risk_table": {"一年": {"標準差": 10.0,
                                                               "Sharpe": 1.1}}})
        assert m["risk_metric_meta"]["sharpe"]["reconcile_blocked_reason"] is None

    def test_no_blocked_reason_when_no_wb07(self):
        """純自算(無 wb07)→ 對帳本來就只有一邊,不算「被門檻降級」。"""
        m = calc_metrics(_nav(120), [])
        assert m["risk_metric_meta"]["sharpe"]["reconcile_blocked_reason"] is None


# ══════════════════════════════════════════════════════════════════
# 3. Calmar 分子分母同源(C-4)
# ══════════════════════════════════════════════════════════════════
class TestCalmarSameBasis:
    def _high_dividend_declining_nav(self):
        """易錯輸入 C:月配息 + 價格單調下跌 → 純價格 3Y 年化為負、含息為正。

        NAV 10.0 → 8.0 線性下滑(800 個交易日),每 21 個交易日配息 0.09。
        """
        n = 800
        idx = pd.date_range("2016-01-04", periods=n, freq="B")
        nav = np.linspace(10.0, 8.0, n)
        s = pd.Series(nav, index=idx, name="nav")
        divs = [{"date": str(idx[k].date()), "amount": 0.09}
                for k in range(21, n, 21)]
        return s, divs

    def test_calmar_sign_follows_total_return_not_price(self):
        """**修正前必紅**:修正前分子用純價格年化(負)→ Calmar 為負;
        修正後分子與分母同取含息還原序列(正)→ Calmar 為正。"""
        s, divs = self._high_dividend_declining_nav()
        m = calc_metrics(s, divs)
        assert m["calmar"] is not None
        _cm = m["risk_metric_meta"]["calmar"]
        # 兩個基準確實不同源(否則本 fixture 沒造出該測的情境)
        assert _cm["ret_3y_ann_price_pct"] is not None
        assert _cm["ret_3y_ann_price_pct"] < 0.0, "fixture 前提:純價格 3Y 年化為負"
        assert _cm["ret_3y_ann_tr_pct"] > 0.0, "fixture 前提:含息 3Y 年化為正"
        assert m["calmar"] > 0.0, "C-4:Calmar 必須跟著含息分子,不可被純價格帶成負號"

    def test_calmar_recomputable_from_total_return_series(self):
        """完全重算(不靠字面值,§3.3):分子分母皆取自同一條 s_tr 的同一個窗、未 round。"""
        s, divs = self._high_dividend_declining_nav()
        m = calc_metrics(s, divs)
        s_tr = _total_return_nav(s, divs)
        cum = np.exp(np.log(s_tr / s_tr.shift(1)).dropna().cumsum())
        c3 = cum.tail(MIN_OBS_CALMAR)
        m3 = c3.cummax()
        dd3_raw = float(((c3 - m3) / m3).min()) * 100.0
        yrs3 = len(c3) / TRADING_DAYS_PER_YEAR
        ret3_raw = ((float(c3.iloc[-1]) / float(c3.iloc[0])) ** (1.0 / yrs3) - 1.0) * 100.0
        _cm = m["risk_metric_meta"]["calmar"]
        assert math.isclose(_cm["max_dd_3y_pct"], round(dd3_raw, 2),
                            rel_tol=0, abs_tol=1e-9)
        assert math.isclose(_cm["ret_3y_ann_tr_pct"], round(ret3_raw, 2),
                            rel_tol=0, abs_tol=1e-9)
        assert math.isclose(m["calmar"], round(ret3_raw / abs(dd3_raw), 2),
                            rel_tol=0, abs_tol=1e-9)
        assert _cm["period_days"] == len(c3)

    def test_no_dividend_fund_numerator_matches_price_basis(self):
        """回歸:無配息 → s_tr ≡ s → 同源分子與純價格年化只差中間 round,不應大幅偏離。"""
        m = calc_metrics(_nav(MIN_OBS_CALMAR + 60), [])
        _cm = m["risk_metric_meta"]["calmar"]
        assert _cm["ret_3y_ann_tr_pct"] is not None and _cm["ret_3y_ann_price_pct"] is not None
        assert math.isclose(_cm["ret_3y_ann_tr_pct"], _cm["ret_3y_ann_price_pct"],
                            rel_tol=0, abs_tol=0.5), (_cm["ret_3y_ann_tr_pct"],
                                                      _cm["ret_3y_ann_price_pct"])


# ══════════════════════════════════════════════════════════════════
# 4. UI 接線 source-scan(沿用 test_total_return_nav_v19_356 的 pin 手法)
#    —— 純函式測不到 streamlit 渲染,但可以釘住「這幾條線沒被拔掉」。
# ══════════════════════════════════════════════════════════════════
def _tab2_src() -> str:
    return (Path(__file__).resolve().parent.parent
            / "ui/tab2_single_fund.py").read_text(encoding="utf-8")


class TestTab2DisclosureWiring:
    def test_mixed_period_warning_has_production_reader(self):
        """**修正前必紅**:`mixed_period_warning` 原本全 repo 只有 fund_service
        自己 + test 檔在讀,UI 0 reader → 矛盾畫面照舊。"""
        src = _tab2_src()
        assert src.count("mixed_period_warning") >= 2, (
            "tab2 必須至少在進階指標與風險指標兩處揭露混期警告")

    def test_reconcile_blocked_reason_rendered(self):
        assert "reconcile_blocked_reason" in _tab2_src()

    def test_period_label_rendered_not_hardcoded_1y(self):
        """標籤必須由 risk_metric_meta 決定(含 wb07 六個月不得再叫 1Y)。"""
        src = _tab2_src()
        assert "_lbl_with_period" in src
        assert "wb07_6m" in src, "wb07 六個月來源必須被標成 6M,不可硬掛 1Y"
        assert 'cC.metric("Sharpe 1Y"' not in src, "Sharpe 欄位標籤不得寫死 1Y"

    def test_1y_total_return_card_label_is_window_aware(self):
        """**修正前必紅**:吃本金 KPI 卡把 42 天的本地含息報酬硬掛「1Y 含息報酬」,
        正是與 wb07 Sharpe 並列時那個數學上不可能的組合的另一半。"""
        src = _tab2_src()
        assert "_kpi_tr_label" in src
        assert "ret_1y_window_days" in src, "標籤必須看實際窗長"
        assert "天含息報酬(非 1Y)" in src

    def test_stale_threshold_copy_removed(self):
        """必修 4 —— **修正前必紅**:UI 對 user 說的門檻是舊值(60 筆 / 1Y fallback)。"""
        src = _tab2_src()
        assert "需 ≥60 筆" not in src
        assert "需 NAV ≥ 60 筆" not in src
        assert "或 1Y 報酬 + max_dd" not in src
        assert "需 3Y 年化 / 或 1Y 報酬 + max_dd" not in src
        # 改為從 SSOT 常數 import 渲染,不再寫死數字
        assert "MIN_OBS_SHARPE_SORTINO as _MIN_SS" in src
        assert "MIN_OBS_CALMAR as _MO_CAL" in src


if __name__ == "__main__":
    import sys

    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
