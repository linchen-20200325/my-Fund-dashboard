# -*- coding: utf-8 -*-
"""P0 風險指標修正回歸網 — services/fund_service.calc_metrics。

四個 P0 對應:
1. **Sortino 分母不是 downside deviation**
   原式 `r252[r252 < 0].std()` = 「負報酬子集合繞自身平均數的樣本標準差(ddof=1)」。
   CFA Institute(Kidd 2012, "The Sortino Ratio")逐字點名此為 *a fairly common
   mistake*:把平方離差和除以「低於 MAR 的筆數」而非「總樣本數」。
   正確 TDD:σ_D = sqrt( (1/N)·Σ[min(0, rₜ−MAR)]² )(分母全樣本 N)。
   GOLDEN {−1%,−2%,−3%,−5%}:TDD = 3.1225% vs 錯式 1.7078%
   → TDD 低估 45%、Sortino **高估 82%**(方向恆為高估 = 排序反向)。
2. **對數報酬混用簡單複利**
   `cum = (1+log_ret).cumprod()` → `cum = exp(cumsum(log_ret))`。
   因 ln(1+x) ≤ x(等號僅 x=0),原式系統性向下漂移 → MaxDD 被**高估**。
3. **樣本閘門 + 期間誠實化**
   sharpe/sortino ≥ 250、maxdd ≥ 125、calmar ≥ 756(Young 1991 的 36 個月)。
   不足 → None + `risk_metric_meta[<指標>]["reason"]`(§1,不靜默回 0/硬算)。
4. **Calmar 期間統一 3Y**(取消 1Y fallback;分母改用同一個 3Y 窗的回撤)。
   - **C-11**:分母不得先 `round(...,2)` 再除 —— 回撤 −0.004% 會被量化成 −0.0
     而誤判 Calmar=None;`round` 只用於 meta 顯示。
   - **C-4**:分子改由**同一條含息還原序列的同一個窗**推年化,與分母同基準
     (原分子取自純價格 NAV,高配息基金會讓 Calmar 正負號相反)。

三個最容易讓這段程式出錯的輸入(§6):
A. **全正報酬**(線性上升 NAV)→ 無低於 MAR 的樣本 → σ_D = 0 → Sortino 若回 inf
   會汙染 factor 排序;必須 None + 原因。
B. **常數 NAV**(停售 / 剛成立填平值,§4.6)→ σ=0;取 MAR=rf 後每點都低於 MAR,
   Sortino 會收斂到 −√252 ≈ −15.87 這種「看起來很精確」的假數字 → 必須 None。
C. **剛好等於門檻**(len(s)=251 → 250 筆 log return)→ off-by-one 會讓合法 1 年
   序列被誤殺 / 或 249 筆被放行。
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

import fund_fetcher  # noqa: F401  解 circular import
import services.fund_service as FS
from services.fund_service import (
    MIN_DOWNSIDE_OBS_SORTINO,
    MIN_OBS_CALMAR,
    MIN_OBS_MAX_DRAWDOWN,
    MIN_OBS_SHARPE_SORTINO,
    _target_downside_deviation,
    calc_metrics,
)
from shared.signal_thresholds import TRADING_DAYS_PER_YEAR


@pytest.fixture(autouse=True)
def _isolate_risk_free_rate():
    """隔離 `_RF_ANNUAL` module 全域,避免**跨測試污染**(§5 冪等性)。

    `services.fund_service.set_risk_free_rate()` 寫的是 module-level 全域
    (`fund_service.py:45-48`),套件內其他測試呼叫後**不會還原**。實測:
    單跑本檔 `_rf_daily()` = 0.04/252 = 0.000159(預設 4%);
    跑全套件時卻拿到 0.001984 = **0.5/252** —— 代表某個先跑的測試把 rf 設成
    50% 就走了,於是「全正報酬 → 無低於 MAR 的樣本」這個前提直接翻掉
    (日報酬 0.0005 < rf 日率 0.00198 → 每一點都低於 MAR),產生
    「單跑綠、全跑紅」的假象。

    測試不該依賴執行順序,故本檔每個 test 前後都明確設定/還原。
    """
    _saved = FS._RF_ANNUAL
    FS.set_risk_free_rate(0.04)   # 明確設回預設,不倚賴前一個測試留下什麼
    yield
    FS._RF_ANNUAL = _saved


def _rf_daily() -> float:
    """rf 為 module-level 全域(app.py 會注入 FEDFUNDS)→ **執行時**讀,
    不可 import 時綁定,否則跑全套件時可能與 production 值不同步。
    本檔已由 `_isolate_risk_free_rate` autouse fixture 固定為 4%。"""
    return FS._RF_ANNUAL / TRADING_DAYS_PER_YEAR


def _nav(n: int, seed: int = 42, mu: float = 0.0004, sigma: float = 0.01) -> pd.Series:
    """合成 NAV(常態 log return 複利),有漲有跌 → 下檔樣本充足。"""
    rng = np.random.default_rng(seed)
    log_r = rng.normal(mu, sigma, n)
    nav = 10.0 * np.exp(np.cumsum(log_r))
    return pd.Series(nav, index=pd.date_range("2018-01-01", periods=n, freq="B"))


def _unrounded_pair(s: pd.Series) -> tuple:
    """重算「未 round」的 (sharpe, sortino, σ, σ_D) — C-8 seed 樂透防護。

    `calc_metrics` 輸出經 `round(...,2)`;直接拿兩個 2dp 值相除,當 |Sharpe| 落在
    0.1 附近時**單次 round 就可能有 5% 相對誤差**(0.005/0.1),而 fixture 的年化
    Sharpe 標準誤 ≈ 1.0(Lo 2002:SE_ann ≈ √((1+½S²)/T_years)),seed 一換就可能
    間歇紅。恆等式測試一律改用未 round 值,rounding 另以「output == round(unrounded,2)」
    單獨釘住,兩件事分開驗。
    """
    lr = np.log(s / s.shift(1)).dropna()
    r252 = lr.tail(TRADING_DAYS_PER_YEAR)
    _sigma = float(r252.std())
    _excess = (r252 - _rf_daily()).to_numpy(dtype=float)
    _tdd = _target_downside_deviation(_excess)
    _ann = float(np.sqrt(TRADING_DAYS_PER_YEAR))
    _sharpe = float(r252.mean() - _rf_daily()) / _sigma * _ann
    _sortino = float(_excess.mean()) / _tdd * _ann
    return _sharpe, _sortino, _sigma, _tdd


def _nav_all_gains(n: int, seed: int = 3) -> pd.Series:
    """全正報酬但**有波動**:每日 log return ∈ [0.05%, 0.15%],皆 > rf 日率
    (0.04/252 ≈ 0.0159%)。σ > 0 讓 Sharpe 仍算得出,但零下檔樣本 → 專測
    Sortino 的 σ_D = 0 分支(若寫成等比數列,log return 會恆定 → σ=0,
    會誤觸退化守衛而測不到本分支)。"""
    rng = np.random.default_rng(seed)
    log_r = rng.uniform(0.0005, 0.0015, n)
    nav = 10.0 * np.exp(np.cumsum(log_r))
    return pd.Series(nav, index=pd.date_range("2018-01-01", periods=n, freq="B"))


# ══════════════════════════════════════════════════════════════════
# 1. Sortino — TDD GOLDEN(§4.3 浮點比較一律用容差,禁 ==)
# ══════════════════════════════════════════════════════════════════
class TestTargetDownsideDeviationGolden:
    CASE = [-0.01, -0.02, -0.03, -0.05]      # MAR = 0 → excess 即原值

    def test_golden_tdd_equals_3_12_pct(self):
        """σ_D = sqrt((0.01²+0.02²+0.03²+0.05²)/4) = sqrt(0.000975) ≈ 3.12249%。

        ⚠️ **不可**把稽核報告口徑「3.1225%」當精確值再配 rel_tol=1e-9:
            0.031225² = 9.75000625e-4 ≠ 9.75e-4
            真值 = 0.031225·sqrt(1 − 6.41e-7) ≈ 0.0312248999…,差 ~1.0e-8,
            而 rel_tol=1e-9 的容差只有 3.12e-11 → 超標 ~320 倍,assertion 必紅。
        §3.3 反捏造:期望值一律用**公式**推,不寫手算四捨五入字面值。
        """
        tdd = _target_downside_deviation(self.CASE)
        _expect = math.sqrt(0.01 ** 2 + 0.02 ** 2 + 0.03 ** 2 + 0.05 ** 2) / 2.0
        assert math.isclose(_expect, math.sqrt(0.000975), rel_tol=1e-15), _expect
        assert math.isclose(tdd, _expect, rel_tol=1e-12, abs_tol=1e-15), (tdd, _expect)
        # 稽核報告口徑:3.12%(2dp 才是安全的字面值比較粒度)
        assert math.isclose(round(tdd * 100, 2), 3.12, rel_tol=0, abs_tol=1e-9)

    def test_wrong_formula_reproduces_1_71_pct(self):
        """釘住錯式數值,證明兩者確實不同源(不是四捨五入差)。"""
        wrong = float(pd.Series(self.CASE).std())          # ddof=1,繞自身平均數
        assert math.isclose(round(wrong * 100, 2), 1.71, rel_tol=0, abs_tol=1e-9), wrong
        tdd = _target_downside_deviation(self.CASE)
        # TDD 低估 45%:1 − 1.7078/3.1225 ≈ 0.453
        assert math.isclose(1 - wrong / tdd, 0.453, rel_tol=0, abs_tol=0.005)
        # Sortino 高估 82%:3.1225/1.7078 − 1 ≈ 0.828
        assert math.isclose(tdd / wrong - 1, 0.828, rel_tol=0, abs_tol=0.01)
        # 方向:錯式分母恆較小 → Sortino 恆被高估(排序反向,不是精度問題)
        assert wrong < tdd

    def test_above_mar_stays_in_denominator(self):
        """核心語意:超過 MAR 的觀測值計 0 但**仍留在分母**。

        同樣 4 筆下檔,再補 4 筆正報酬 → N 從 4 變 8 → σ_D 應**變小**(除以 8)。
        """
        tdd4 = _target_downside_deviation(self.CASE)
        tdd8 = _target_downside_deviation(self.CASE + [0.01, 0.02, 0.03, 0.05])
        assert math.isclose(tdd8, tdd4 / math.sqrt(2.0), rel_tol=1e-12, abs_tol=1e-15)
        # 錯式在同輸入下**完全不變**(只看負報酬子集合)→ 兩式語意不同的直接證據
        wrong4 = float(pd.Series(self.CASE).std())
        wrong8 = float(pd.Series([v for v in self.CASE + [0.01, 0.02, 0.03, 0.05]
                                  if v < 0]).std())
        assert math.isclose(wrong4, wrong8, rel_tol=1e-12, abs_tol=1e-15)

    def test_empty_and_all_positive(self):
        # §4.3:浮點一律容差比較(此處雖為精確 0.0,仍不寫 `==`)
        assert math.isclose(_target_downside_deviation([]), 0.0, abs_tol=1e-15)
        assert math.isclose(_target_downside_deviation([0.01, 0.02]), 0.0, abs_tol=1e-15)


class TestSortinoWiredWithTDD:
    def test_sortino_matches_hand_computed_tdd(self):
        """端到端:calc_metrics 的 sortino 必須等於手算 TDD 版(MAR = rf 日率)。"""
        s = _nav(MIN_OBS_SHARPE_SORTINO + 60)
        m = calc_metrics(s, [])
        assert m["sortino"] is not None
        lr = np.log(s / s.shift(1)).dropna()
        r252 = lr.tail(TRADING_DAYS_PER_YEAR)
        excess = (r252 - _rf_daily()).to_numpy(dtype=float)
        tdd = _target_downside_deviation(excess)
        expect = round(float(excess.mean() / tdd * np.sqrt(TRADING_DAYS_PER_YEAR)), 2)
        assert math.isclose(m["sortino"], expect, rel_tol=0, abs_tol=1e-9)

    def test_sortino_magnitude_lower_than_legacy_wrong_formula(self):
        """舊錯式分母恆較小 ⇒ |Sortino| 被放大(分子相同,故比幅度不比正負)。

        分子(r̄ − rf)兩式**完全相同**;只有分母不同:
          TDD(全樣本 N) > legacy(負報酬子集合 ddof=1 繞自身平均數)
        近對稱分佈下 TDD ≈ σ/√2 ≈ 0.707σ、legacy ≈ σ√(1−2/π) ≈ 0.603σ,
        差距 ~17%(MAR=rf>0 會讓 TDD 再更大)。
        """
        s = _nav(MIN_OBS_SHARPE_SORTINO + 60)
        m = calc_metrics(s, [])
        assert m["sortino"] is not None
        lr = np.log(s / s.shift(1)).dropna()
        r252 = lr.tail(TRADING_DAYS_PER_YEAR)
        legacy_dstd = float(r252[r252 < 0].std())
        _, _sortino_raw, _, tdd = _unrounded_pair(s)
        assert tdd > legacy_dstd, (tdd, legacy_dstd)
        legacy = float((r252.mean() - _rf_daily()) / legacy_dstd
                       * np.sqrt(TRADING_DAYS_PER_YEAR))
        # C-8:比幅度用**未 round** 值(round 到 2dp 後,小值的相對誤差可翻轉不等號)
        assert abs(_sortino_raw) < abs(legacy), (_sortino_raw, legacy)
        # rounding 另外釘:production 輸出必須 == round(未 round 值, 2)
        assert math.isclose(m["sortino"], round(_sortino_raw, 2),
                            rel_tol=0, abs_tol=1e-9), (m["sortino"], _sortino_raw)

    def test_mar_consistent_with_sharpe_numerator(self):
        """MAR = rf → Sharpe 與 Sortino **分子完全相同** ⇒ sortino/sharpe = σ/σ_D。

        這是「分子分母同基準」的可驗證後果;若 MAR 被改回 0,本恆等式立刻破。

        C-8:**不可**拿兩個 `round(...,2)` 的 output 相除來驗恆等式 —— 年化 Sharpe
        的標準誤 ≈ 1.0,seed 一換就可能讓 |Sharpe| 靠近 0,兩次 round 的相對誤差
        直接吃掉 5% 容差 → 間歇紅。恆等式用未 round 值驗(可收到 1e-12),
        round 行為另外單獨釘。
        """
        s = _nav(MIN_OBS_SHARPE_SORTINO + 60)
        m = calc_metrics(s, [])
        assert m["sharpe"] is not None and m["sortino"] is not None
        _sharpe_raw, _sortino_raw, sigma, tdd = _unrounded_pair(s)
        assert abs(_sharpe_raw) > 1e-12, "fixture 前提:Sharpe 不得退化為 0"
        assert math.isclose(_sortino_raw / _sharpe_raw, sigma / tdd,
                            rel_tol=1e-12, abs_tol=1e-15)
        # production 輸出 = round(未 round 值, 2),兩件事分開驗
        assert math.isclose(m["sharpe"], round(_sharpe_raw, 2), rel_tol=0, abs_tol=1e-9)
        assert math.isclose(m["sortino"], round(_sortino_raw, 2), rel_tol=0, abs_tol=1e-9)

    def test_sortino_source_and_meta(self):
        s = _nav(MIN_OBS_SHARPE_SORTINO + 60)
        m = calc_metrics(s, [])
        assert m["sortino_source"] == "self_calc"
        meta = m["risk_metric_meta"]["sortino"]
        assert meta["period_days"] == TRADING_DAYS_PER_YEAR
        assert meta["min_required"] == MIN_OBS_SHARPE_SORTINO
        assert "MAR=rf" in meta["definition"]
        assert meta["reason"] is None


# ══════════════════════════════════════════════════════════════════
# 2. cum:exp(cumsum) vs (1+log).cumprod()
# ══════════════════════════════════════════════════════════════════
class TestLogReturnCompounding:
    def test_exp_cumsum_equals_price_ratio_and_old_form_drifts_down(self):
        """exp(cumsum(lr)) 恆等於 s/s[0];舊式因 ln(1+x) ≤ x 系統性向下漂移。"""
        s = _nav(600, seed=7, mu=0.0, sigma=0.012)
        lr = np.log(s / s.shift(1)).dropna()
        new = np.exp(lr.cumsum())
        old = (1 + lr).cumprod()
        px = (s / float(s.iloc[0])).iloc[1:]
        assert np.allclose(new.to_numpy(), px.to_numpy(), rtol=1e-12, atol=1e-12)
        # 逐點 old ≤ new(嚴格:只要有任一 lr ≠ 0 即嚴格小於)
        assert bool((old <= new + 1e-15).all())
        assert float(old.iloc[-1]) < float(new.iloc[-1])

    def test_old_form_overstates_maxdd(self):
        """舊式 MaxDD 必然**不淺於**(更負或相等)正確式 → 回撤被高估。"""
        s = _nav(600, seed=11, mu=0.0, sigma=0.015)
        lr = np.log(s / s.shift(1)).dropna()
        # 與 production 用**同一個代數形式** (c−cmax)/cmax:a/b−1 與 (a−b)/b 差 1 ulp,
        # 落在 round(...,2) 邊界時會偽紅 —— 對帳測試不該被寫法差異綁架。
        _cum = np.exp(lr.cumsum()); _cmax = _cum.cummax()
        dd_new = float(((_cum - _cmax) / _cmax).min())
        old = (1 + lr).cumprod()
        dd_old = float((old / old.cummax() - 1).min())
        assert dd_old <= dd_new + 1e-12, (dd_old, dd_new)
        m = calc_metrics(s, [])
        assert math.isclose(m["max_drawdown"], round(dd_new * 100, 2),
                            rel_tol=0, abs_tol=1e-9)

    def test_maxdd_definition_and_range(self):
        """不變量:MaxDD = min(cum/cummax − 1) ∈ [-100%, 0]。"""
        s = _nav(400)
        m = calc_metrics(s, [])
        assert m["max_drawdown"] is not None
        assert -100.0 <= m["max_drawdown"] <= 0.0


# ══════════════════════════════════════════════════════════════════
# 3. 樣本閘門 + 原因字串 + 期間 meta
# ══════════════════════════════════════════════════════════════════
class TestSampleGates:
    def test_sharpe_sortino_exact_threshold_passes(self):
        """剛好等於門檻:len(s)=251 → log_ret=250 = MIN_OBS_SHARPE_SORTINO → 放行。"""
        s = _nav(MIN_OBS_SHARPE_SORTINO + 1)
        m = calc_metrics(s, [])
        assert len(np.log(s / s.shift(1)).dropna()) == MIN_OBS_SHARPE_SORTINO
        assert m["sharpe"] is not None and m["sortino"] is not None
        assert m["risk_metric_meta"]["sharpe"]["period_days"] == MIN_OBS_SHARPE_SORTINO

    def test_sharpe_sortino_one_short_returns_none_with_reason(self):
        """差 1 筆(249)→ None + 「樣本不足(249/250 交易日)」。"""
        s = _nav(MIN_OBS_SHARPE_SORTINO)          # → 249 筆 log return
        m = calc_metrics(s, [])
        assert m["sharpe"] is None and m["sortino"] is None
        assert m["sharpe_source"] is None and m["sortino_source"] is None
        meta = m["risk_metric_meta"]
        for key, sub in (("sharpe", "self_calc_reason"), ("sortino", "reason")):
            reason = meta[key][sub]
            assert reason and "樣本不足" in reason, (key, reason)
            assert f"{MIN_OBS_SHARPE_SORTINO - 1}/{MIN_OBS_SHARPE_SORTINO}" in reason

    def test_maxdd_threshold_boundary(self):
        """len(s)=126 → cum 125 = 門檻 → 放行;len(s)=125 → 124 → None + 原因。"""
        ok = calc_metrics(_nav(MIN_OBS_MAX_DRAWDOWN + 1), [])
        assert ok["max_drawdown"] is not None
        assert ok["risk_metric_meta"]["max_drawdown"]["period_days"] == MIN_OBS_MAX_DRAWDOWN
        bad = calc_metrics(_nav(MIN_OBS_MAX_DRAWDOWN), [])
        assert bad["max_drawdown"] is None
        assert bad["max_drawdown_source"] is None
        r = bad["risk_metric_meta"]["max_drawdown"]["reason"]
        assert r and "樣本不足" in r and f"/{MIN_OBS_MAX_DRAWDOWN}" in r

    def test_calmar_threshold_boundary(self):
        """len(s)=756 → 放行;755 → None + 原因(且**不得**回退 1Y)。"""
        s_ok = _nav(MIN_OBS_CALMAR)
        ok = calc_metrics(s_ok, [])
        assert ok["calmar"] is not None
        # 期間誠實化:log 差分讓 cum 比 s 少 1 點 → 邊界上實際窗長 = 755,
        # meta 必須報**實際**窗長而非宣稱的 756(這正是本次任務的主題)。
        assert (ok["risk_metric_meta"]["calmar"]["period_days"]
                == min(MIN_OBS_CALMAR, len(s_ok) - 1))
        bad = calc_metrics(_nav(MIN_OBS_CALMAR - 1), [])
        assert bad["calmar"] is None and bad["calmar_source"] is None
        r = bad["risk_metric_meta"]["calmar"]["reason"]
        assert r and "樣本不足" in r and f"/{MIN_OBS_CALMAR}" in r

    def test_thresholds_are_named_constants_not_inline(self):
        """§3.3:門檻必須具名(非 inline magic),且 250/125/756 語意正確。"""
        assert MIN_OBS_SHARPE_SORTINO == 250
        assert MIN_OBS_MAX_DRAWDOWN == 125
        assert MIN_OBS_CALMAR == 3 * TRADING_DAYS_PER_YEAR == 756
        assert MIN_DOWNSIDE_OBS_SORTINO == 5


# ══════════════════════════════════════════════════════════════════
# 4. Calmar 期間一致性(Young 1991)
# ══════════════════════════════════════════════════════════════════
class TestCalmarPeriodConsistency:
    def test_calmar_uses_3y_window_drawdown_not_full_history(self):
        """分母必須是**同一個 3Y 窗**的回撤,不是全期 max_drawdown。

        造一條「早期大跌 + 近 3 年平穩」的序列:全期 MaxDD 遠深於 3Y MaxDD,
        兩者相除會得到完全不同的 Calmar → 用 3Y 窗才符合 Young (1991)。
        """
        n_old, n_new = 400, MIN_OBS_CALMAR + 10
        rng = np.random.default_rng(5)
        old_part = 10.0 * np.exp(np.cumsum(rng.normal(-0.0015, 0.02, n_old)))  # 早期崩
        base = float(old_part[-1])
        new_part = base * np.exp(np.cumsum(rng.normal(0.0004, 0.003, n_new)))  # 近期穩
        vals = np.concatenate([old_part, new_part])
        s = pd.Series(vals, index=pd.date_range("2012-01-02", periods=len(vals), freq="B"))
        m = calc_metrics(s, [])
        assert m["calmar"] is not None
        dd_full = m["max_drawdown"]
        dd_3y = m["risk_metric_meta"]["calmar"]["max_dd_3y_pct"]
        assert dd_3y is not None
        # 單調性:MaxDD 對窗長單調非遞減 ⇒ |全期| ≥ |3Y|
        assert abs(dd_full) >= abs(dd_3y) - 1e-9
        assert abs(dd_full) > abs(dd_3y), "本 fixture 應造出明顯的窗長差異"
        # ── C-11 + C-4:分子分母皆取自**同一條 cum、同一個窗、未 round** ──
        # divs=[] ⇒ s_tr ≡ s ⇒ cum 逐點 = s/s[0],測試可完全重算(不靠字面值)。
        lr = np.log(s / s.shift(1)).dropna()
        cum = np.exp(lr.cumsum())
        c3 = cum.tail(MIN_OBS_CALMAR)
        m3 = c3.cummax()
        dd3_raw = float(((c3 - m3) / m3).min()) * 100.0
        yrs3 = len(c3) / TRADING_DAYS_PER_YEAR
        ret3_tr_raw = ((float(c3.iloc[-1]) / float(c3.iloc[0])) ** (1.0 / yrs3) - 1.0) * 100.0
        assert math.isclose(dd_3y, round(dd3_raw, 2), rel_tol=0, abs_tol=1e-9)
        assert math.isclose(m["risk_metric_meta"]["calmar"]["ret_3y_ann_tr_pct"],
                            round(ret3_tr_raw, 2), rel_tol=0, abs_tol=1e-9)
        assert math.isclose(m["calmar"], round(ret3_tr_raw / abs(dd3_raw), 2),
                            rel_tol=0, abs_tol=1e-9)
        # 若誤用全期回撤,數值會明顯不同(釘住不可回歸)
        assert not math.isclose(m["calmar"],
                                round(ret3_tr_raw / abs(dd_full), 2),
                                rel_tol=0, abs_tol=1e-9)

    def test_calmar_denominator_not_pre_rounded(self):
        """C-11 迴歸:分母若先 round(…,2) 再除,微小回撤會被量化甚至歸零。

        造一條「3Y 窗內回撤僅 ~0.004%」的序列:
          - 修正前:round(-0.004, 2) = -0.0 → 命中 `abs(...) <= 1e-9` → Calmar = None
          - 修正後:用未 round 的 -0.004 當除數 → Calmar 有值(且極大,反映真實)
        本測試在修正前**必紅**(m["calmar"] is None)。
        """
        n = MIN_OBS_CALMAR + 5
        # 幾乎單調上升 + 單一極淺的凹陷 → 3Y 窗最大回撤 ≈ 4e-5 (=0.004%)
        log_r = np.full(n, 2e-4)
        log_r[n // 2] = -4e-5          # 單日 log return = -4e-5 → 回撤 ≈ -0.004%
        nav = 10.0 * np.exp(np.cumsum(log_r))
        s = pd.Series(nav, index=pd.date_range("2016-01-04", periods=n, freq="B"))
        m = calc_metrics(s, [])
        dd_3y = m["risk_metric_meta"]["calmar"]["max_dd_3y_pct"]
        # 顯示用的 2dp 值確實會被量化成 -0.0(證明「先 round 再除」必然歸零)
        assert dd_3y is not None and abs(dd_3y) < 1e-9, dd_3y
        # 但 Calmar 必須算得出來(用未 round 分母)
        assert m["calmar"] is not None, "C-11:分母先 round 會讓極淺回撤誤判 Calmar=None"
        assert m["risk_metric_meta"]["calmar"]["reason"] is None

    def test_no_1y_fallback_even_when_1y_return_available(self):
        """300 筆:ret_1y 有值、max_dd 有值,但 Calmar 仍必須 None(取消 fallback)。"""
        m = calc_metrics(_nav(300), [])
        assert m["ret_1y"] is not None and m["max_drawdown"] is not None
        assert m["calmar"] is None


# ══════════════════════════════════════════════════════════════════
# 5. 邊界(§4.6)
# ══════════════════════════════════════════════════════════════════
class TestEdgeCases:
    def test_all_positive_returns_sortino_none_not_inf(self):
        """易錯輸入 A:全正報酬 → 無下檔樣本 → Sortino 回 None(§1),**不可** inf。"""
        assert _rf_daily() < 0.0005, "fixture 前提:rf 日率須低於序列最低日報酬"
        m = calc_metrics(_nav_all_gains(MIN_OBS_SHARPE_SORTINO + 60), [])
        assert m["sortino"] is None, m["sortino"]
        assert m["sortino_source"] is None
        r = m["risk_metric_meta"]["sortino"]["reason"]
        assert r and "低於 MAR" in r, r
        # sharpe 仍算得出(σ>0)→ 證明不是整段被誤殺
        assert m["sharpe"] is not None

    def test_constant_nav_sharpe_and_sortino_none(self):
        """易錯輸入 B:常數 NAV(停售,§4.6)→ σ=0 → Sharpe / Sortino 皆 None。

        注意:取 MAR=rf 後常數 NAV 每點都低於 MAR,若無退化守衛,Sortino 會算出
        −√252 ≈ −15.87 這種假精確值。
        """
        idx = pd.date_range("2018-01-01", periods=MIN_OBS_SHARPE_SORTINO + 60, freq="B")
        m = calc_metrics(pd.Series([10.0] * len(idx), index=idx), [])
        assert m["sharpe"] is None and m["sortino"] is None
        assert "σ=0" in (m["risk_metric_meta"]["sortino"]["reason"] or "")

    def test_single_point_and_too_short(self):
        """單筆 / <5 筆 → calc_metrics 直接回 {}(既有契約)。"""
        idx = pd.date_range("2026-01-01", periods=1, freq="B")
        assert calc_metrics(pd.Series([10.0], index=idx), []) == {}
        idx4 = pd.date_range("2026-01-01", periods=4, freq="B")
        assert calc_metrics(pd.Series([10.0, 10.1, 10.2, 10.3], index=idx4), []) == {}

    def test_all_nan_series_raises(self):
        """全 NaN NAV → 入口 pandera 擋下並 raise(§1 Fail Loud,不吞不補)。"""
        idx = pd.date_range("2026-01-01", periods=30, freq="B")
        with pytest.raises(Exception):
            calc_metrics(pd.Series([np.nan] * 30, index=idx), [])

    def test_meta_keys_always_present(self):
        """schema 守:不論長短,risk_metric_meta 四個指標鍵恆在(UI 可無條件讀)。"""
        for n in (30, 300, MIN_OBS_CALMAR + 5):
            m = calc_metrics(_nav(n), [])
            meta = m["risk_metric_meta"]
            for k in ("sharpe", "sortino", "max_drawdown", "calmar"):
                assert k in meta and isinstance(meta[k], dict), (n, k)
            assert "mixed_period_warning" in meta


# ══════════════════════════════════════════════════════════════════
# 6. Provenance:本地自算 vs wb07 官方混用(§2.2)
# ══════════════════════════════════════════════════════════════════
class TestSharpeProvenance:
    def _override(self, sharpe_1y=None, sharpe_6m=None):
        tbl = {}
        if sharpe_1y is not None:
            tbl["一年"] = {"標準差": 10.0, "Sharpe": sharpe_1y}
        if sharpe_6m is not None:
            tbl["六個月"] = {"標準差": 9.0, "Sharpe": sharpe_6m}
        return {"risk_table": tbl}

    def test_wb07_value_and_source_agree(self):
        m = calc_metrics(_nav(300), [], risk_override=self._override(sharpe_1y=1.2))
        # §4.3:浮點比較用容差,不用 ==
        assert math.isclose(m["sharpe"], 1.2, rel_tol=1e-9, abs_tol=1e-12), m["sharpe"]
        assert m["sharpe_source"] == "wb07_1y"
        assert "wb07 官方一年" in m["risk_metric_meta"]["sharpe"]["period_label"]

    def test_wb07_zero_sharpe_does_not_fall_through(self):
        """§2.2 provenance 不可說謊:wb07 Sharpe 恰為 0.0 時,原 `or` 鏈會 falsy
        落到自算值,但 source 仍標 wb07 → 值與標籤不一致。修正後兩者必須同源。"""
        m = calc_metrics(_nav(300), [], risk_override=self._override(sharpe_1y=0.0))
        assert m["sharpe_source"] == "wb07_1y"
        assert math.isclose(m["sharpe"], 0.0, rel_tol=0, abs_tol=1e-12), m["sharpe"]

    def test_self_calc_marked_with_actual_period(self):
        m = calc_metrics(_nav(300), [])
        assert m["sharpe_source"] == "self_calc"
        meta = m["risk_metric_meta"]["sharpe"]
        assert meta["period_days"] == TRADING_DAYS_PER_YEAR
        assert "本地自算" in meta["period_label"]

    def test_mixed_period_warning_when_wb07_sharpe_meets_short_local_return(self):
        """線上實測情境:wb07 官方 Sharpe(1Y)× 本地 42 天含息報酬並列 → 必須示警。"""
        s = _nav(30)                       # ~42 自然日
        m = calc_metrics(s, [], risk_override=self._override(sharpe_1y=0.28))
        assert m["ret_1y_window_days"] is not None and m["ret_1y_window_days"] < 350
        warn = m["risk_metric_meta"]["mixed_period_warning"]
        assert warn and "期間不一致" in warn, warn
        # 本地自算 Sharpe 在此長度必須是 None(不可能同時吐出兩個 1Y)
        assert m["risk_metric_meta"]["sharpe"]["self_calc_value"] is None
        assert "樣本不足" in (m["risk_metric_meta"]["sharpe"]["self_calc_reason"] or "")

    def test_no_warning_when_periods_align(self):
        m = calc_metrics(_nav(400), [], risk_override=self._override(sharpe_1y=1.1))
        assert m["risk_metric_meta"]["mixed_period_warning"] is None


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
