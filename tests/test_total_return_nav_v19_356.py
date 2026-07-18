# -*- coding: utf-8 -*-
"""v19.356 — 項4:配息還原淨值(total-return NAV)供風險指標計算。

背景(§4.5 配息切割 / §4.6 ex-date 跳空):配息型基金除息日 NAV 下跳一個配息額,
**不是**真實下跌(持有人領到現金),但自算 log return 會當成暴跌 → 高估 σ、放大
max_drawdown、壓低 Sharpe/Sortino。`services.fund_service._total_return_nav()` 用
Factor 還原法(複用 SSOT `calculate_fund_total_return`)把配息再投資複利還原進序列,
只餵給 `calc_metrics` 的 `log_ret`(σ / Sharpe / Sortino / max_dd);顯示值、買賣點、
高低點、純 NAV 報酬仍用原始 `s`。

三個最容易讓這段程式出錯的輸入(§6):
1. **ex-date 不落在 NAV 交易日** → left-merge 丟棄該筆 → 長度須保留、s_tr==s(該筆未還原,
   不可爆長度)。
2. **同一除息日重複配息** → merge 膨脹使長度 != 原序列 → 長度守衛 → **回退原始 s**
   (寧可未還原,不可回傳錯位序列)。
3. **首日即除息** → Factor 於 index 0 生效、cumprod 起點 > 1 → 全正、長度保留。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import fund_fetcher  # noqa: F401  解 circular import
from services.fund_service import (
    _total_return_nav,
    calc_metrics,
    calculate_fund_total_return,  # noqa: F401  SSOT 複用來源(確保可 import)
)


def _mk_series(values, end="2026-07-10"):
    idx = pd.date_range(end=pd.Timestamp(end), periods=len(values), freq="B")
    return pd.Series([float(v) for v in values], index=idx, name="nav")


# ══════════════════════════════════════════════════════════════
# 單元:_total_return_nav 降級(§1 Fail Loud → 顯式回退)
# ══════════════════════════════════════════════════════════════
class TestTotalReturnNavDegradation:
    def test_no_divs_returns_identity(self):
        """divs 空 / None → 逐點等於 s(純累積型行為零變化)。"""
        s = _mk_series([10, 11, 12, 13, 14])
        assert _total_return_nav(s, []).equals(s)
        assert _total_return_nav(s, None) is s          # None 直接原物件回

    def test_all_nonpositive_amount_skipped(self):
        """amount<=0 全跳過 → 無配息事件 → 回原序列(防禦降級,validator 出口才擋)。"""
        s = _mk_series([10, 11, 12, 13, 14])
        d1 = str(s.index[2].date())
        divs = [{"date": d1, "amount": 0.0}, {"date": d1, "amount": -3.0}]
        assert _total_return_nav(s, divs).equals(s)

    def test_bad_date_skipped(self):
        """日期不可解析 → 跳過 → 若全壞則回原序列(不爆例外)。"""
        s = _mk_series([10, 11, 12, 13, 14])
        out = _total_return_nav(s, [{"date": "not-a-date", "amount": 5.0}])
        assert out.equals(s)

    def test_empty_series_passthrough(self):
        """空序列 → 原樣回(不爆)。"""
        s = pd.Series([], dtype="float64")
        assert _total_return_nav(s, [{"date": "2026-01-01", "amount": 1.0}]).empty


# ══════════════════════════════════════════════════════════════
# 單元:還原正確性(golden)
# ══════════════════════════════════════════════════════════════
class TestTotalReturnNavCorrectness:
    def test_dividend_only_drop_flattens(self):
        """GOLDEN:NAV 100→90 的跌幅**恰好**是配息 10 → 還原後序列拉平為 100。

        Factor(除息日) = 1 + 10/90;Adj_NAV = 90 × (1+10/90) = 100 → 全期 100。
        """
        idx = pd.to_datetime(
            ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05"]
        )
        s = pd.Series([100.0, 100.0, 100.0, 90.0, 90.0], index=idx)
        s_tr = _total_return_nav(s, [{"date": "2026-01-04", "amount": 10.0}])
        assert np.allclose(s_tr.to_numpy(), 100.0), s_tr.to_numpy()
        # 還原後 log return 幾乎全 0(假暴跌被消掉)
        lr = np.log(s_tr / s_tr.shift(1)).dropna()
        assert float(lr.abs().max()) < 1e-9

    def test_first_day_dividend(self):
        """易錯輸入 3:首日即除息 → Factor 於 index 0 生效,cumprod 起點>1,全正。"""
        idx = pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03"])
        s = pd.Series([100.0, 101.0, 102.0], index=idx)
        s_tr = _total_return_nav(s, [{"date": "2026-01-01", "amount": 5.0}])
        # Factor0 = 1+5/100 = 1.05 → [105, 106.05, 107.10]
        assert np.allclose(s_tr.to_numpy(), [105.0, 106.05, 107.10])
        assert len(s_tr) == len(s) and bool((s_tr > 0).all())

    def test_exdate_not_on_nav_date_preserves_length(self):
        """易錯輸入 1:ex-date 不在 NAV index → left-merge 丟棄該筆,長度保留、s_tr==s。"""
        idx = pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03"])
        s = pd.Series([100.0, 100.0, 100.0], index=idx)
        s_tr = _total_return_nav(s, [{"date": "2026-01-10", "amount": 5.0}])  # 不在 index
        assert len(s_tr) == len(s)
        assert s_tr.equals(s)

    def test_duplicate_exdate_falls_back_to_raw(self):
        """易錯輸入 2:同一除息日重複配息 → merge 膨脹 → 長度守衛 → 回退原始 s。"""
        idx = pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03"])
        s = pd.Series([100.0, 100.0, 100.0], index=idx)
        divs = [{"date": "2026-01-02", "amount": 5.0},
                {"date": "2026-01-02", "amount": 5.0}]  # 同日兩筆
        out = _total_return_nav(s, divs)
        assert out.equals(s), "重複除息日應觸發長度守衛 → 回退原始 s"


# ══════════════════════════════════════════════════════════════
# Property:不變量(§4.2)
# ══════════════════════════════════════════════════════════════
class TestTotalReturnNavInvariants:
    def test_length_index_positivity(self):
        """任意合法配息 → s_tr 與 s 等長、同 index、全正。"""
        s = _mk_series([100 + np.sin(i / 5) * 3 for i in range(60)])
        # 每 20 天配息一次
        divs = [{"date": str(s.index[k].date()), "amount": 1.5} for k in (19, 39, 59)]
        s_tr = _total_return_nav(s, divs)
        assert len(s_tr) == len(s)
        assert s_tr.index.equals(s.index)
        assert bool((s_tr > 0).all())

    def test_total_return_ge_price_return_when_divs_positive(self):
        """配息>0 → 還原(含息)累積漲幅 ≥ 純價格漲幅(再投資複利只會加不會減)。"""
        s = _mk_series([100.0] * 30)                       # 純價格 0 漲幅
        divs = [{"date": str(s.index[10].date()), "amount": 2.0}]
        s_tr = _total_return_nav(s, divs)
        price_ret = s.iloc[-1] / s.iloc[0] - 1.0           # = 0
        total_ret = s_tr.iloc[-1] / s_tr.iloc[0] - 1.0
        assert total_ret >= price_ret - 1e-12
        assert total_ret > 0                               # 有配息 → 含息 > 0


# ══════════════════════════════════════════════════════════════
# 整合:calc_metrics 風險指標含息化 + 純累積型零變化
# ══════════════════════════════════════════════════════════════
class TestCalcMetricsIntegration:
    def _dividend_step_series(self):
        """前 150 日 NAV=100,除息日下跳至 92(配息 8),後 150 日=92。
        含息還原後 Adj_NAV 全期 = 100(92×(1+8/92)) → max_dd≈0、σ≈0。"""
        n = 300
        idx = pd.date_range(end=pd.Timestamp("2026-07-10"), periods=n, freq="B")
        vals = [100.0] * 150 + [92.0] * 150
        s = pd.Series(vals, index=idx, name="nav")
        ex_date = str(idx[150].date())
        divs = [{"date": ex_date, "amount": 8.0}]
        return s, divs

    def test_maxdd_and_sigma_smaller_with_dividend_reinvest(self):
        """除息跳空為假回撤:含息還原後 max_dd/σ 應顯著小於未還原(raw)。"""
        s, divs = self._dividend_step_series()
        m_div = calc_metrics(s, divs)
        m_raw = calc_metrics(s, [])          # divs=[] → 走原始 NAV(假回撤)
        # 含息:除息跳空被消掉 → 幾乎無回撤
        assert abs(m_div["max_drawdown"]) < 0.5, m_div["max_drawdown"]
        # 未還原:假回撤 ~ -8%
        assert m_raw["max_drawdown"] < -5.0, m_raw["max_drawdown"]
        # σ 同向:含息 < 未還原
        assert m_div["std_1y"] < m_raw["std_1y"]

    def test_no_dividend_zero_change(self):
        """回歸:無配息基金 → _total_return_nav(s,[]) 逐點等於 s → 風險指標零變化。

        以 max_drawdown 對帳:calc_metrics(s,[]) 與『直接用原始 s 算』一致。
        """
        vals = [10.0 * (1 + 0.001 * ((-1) ** i) + i * 0.0002) for i in range(300)]
        s = _mk_series(vals)
        # 身分保證:空配息 → 還原序列 == 原序列
        assert _total_return_nav(s, []).equals(s)
        m = calc_metrics(s, [])
        # 直接以原始 s 重算 max_dd(對照演算法,§4.3)
        lr = np.log(s / s.shift(1)).dropna()
        cum = (1 + lr).cumprod()
        expect_dd = round(float(((cum - cum.cummax()) / cum.cummax()).min()) * 100, 2)
        assert m["max_drawdown"] == expect_dd


# ══════════════════════════════════════════════════════════════
# Source-scan:釘住 wiring(避免未來重構悄悄拔線)
# ══════════════════════════════════════════════════════════════
class TestWiringPinned:
    def test_log_ret_uses_total_return_series(self):
        from pathlib import Path
        src = (Path(__file__).resolve().parent.parent
               / "services/fund_service.py").read_text(encoding="utf-8")
        assert "s_tr = _total_return_nav(s, divs)" in src
        assert "np.log(s_tr / s_tr.shift(1))" in src
        # 舊的原始 NAV log_ret 不應殘留在 calc_metrics 主計算路徑
        assert "log_ret = np.log(s / s.shift(1))" not in src
