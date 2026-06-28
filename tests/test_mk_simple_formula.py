"""tests/test_mk_simple_formula.py — MK 老師嚴格單利 1Y 含息報酬率公式守衛(v19.149)

User 釐清 MK 老師體檢邏輯:
    含息_1Y = NAV 漲跌幅% + 累計配息率%

公式:
    nav_change_pct = (NAV_now − NAV_1Y_ago) / NAV_1Y_ago × 100
    div_total_pct  = Σ(divs in last 1Y) / NAV_1Y_ago × 100
    ret_pct        = nav_change_pct + div_total_pct

本檔守:
1. 公式正確性(手算 + property tests)
2. 1Y 窗口邊界(剛好 365 天 / 短窗 / 缺資料)
3. 配息日界線(start exclusive,end inclusive)
4. 邊界條件(空 dividends / NAV 為 0 / NaN guard)
5. check_eating_principal_1y_mk v19.149 升級後仍向後相容
"""
from __future__ import annotations

import datetime as _dt
import math

import pytest

from services.health.dividend import (
    check_eating_principal_1y_mk,
    compute_1y_total_return_mk_simple,
)


# ──────────────────────────────────────────────────────────
# 1. 公式正確性 — 手算 golden
# ──────────────────────────────────────────────────────────
class TestMkSimpleFormulaGolden:
    """手算 golden case:確認公式 = NAV 漲跌 + 累計配息率。"""

    def test_basic_one_dividend(self):
        """NAV 100 → 110(漲 10%),1Y 內配息 5 元 → 5%,合計 15%。"""
        nav = {
            "2025-06-26": 100.0,  # 1Y ago start
            "2026-06-26": 110.0,  # now
        }
        divs = [{"date": "2026-01-01", "amount": 5.0}]
        ret, meta = compute_1y_total_return_mk_simple(nav, divs)
        assert math.isclose(ret, 15.0, abs_tol=0.01), (
            f"預期 15%(10 + 5),實際 {ret}"
        )
        assert math.isclose(meta["nav_change_pct"], 10.0, abs_tol=0.01)
        assert math.isclose(meta["div_total_pct"], 5.0, abs_tol=0.01)
        assert meta["div_count"] == 1
        assert meta["source"] == "mk_strict"

    def test_zero_nav_change_only_dividends(self):
        """NAV 不變,3 次配息各 2 元 → 6/100 = 6% 含息。"""
        nav = {"2025-06-26": 100.0, "2026-06-26": 100.0}
        divs = [
            {"date": "2025-12-01", "amount": 2.0},
            {"date": "2026-02-01", "amount": 2.0},
            {"date": "2026-05-01", "amount": 2.0},
        ]
        ret, meta = compute_1y_total_return_mk_simple(nav, divs)
        assert math.isclose(ret, 6.0, abs_tol=0.01)
        assert meta["div_count"] == 3
        assert math.isclose(meta["div_sum_per_unit"], 6.0, abs_tol=0.001)

    def test_nav_drop_negative_return(self):
        """NAV 100 → 90(跌 10%),無配息 → -10% 含息(警示但非吃本金,看 caller)。"""
        nav = {"2025-06-26": 100.0, "2026-06-26": 90.0}
        ret, meta = compute_1y_total_return_mk_simple(nav, [])
        assert math.isclose(ret, -10.0, abs_tol=0.01)
        assert math.isclose(meta["nav_change_pct"], -10.0, abs_tol=0.01)
        assert meta["div_total_pct"] == 0.0
        assert meta["div_count"] == 0

    def test_no_dividends_pure_nav(self):
        """無配息列表 → div_total = 0,等於純 NAV 報酬。"""
        nav = {"2025-06-26": 100.0, "2026-06-26": 108.0}
        ret, meta = compute_1y_total_return_mk_simple(nav, None)
        assert math.isclose(ret, 8.0, abs_tol=0.01)

    def test_monthly_dividend_1pct_year(self):
        """月配 1 元(NAV 100 起),12 個月共 12 元 → 12%。"""
        nav = {"2025-06-26": 100.0, "2026-06-26": 100.0}
        divs = [
            {"date": f"2025-{m:02d}-15", "amount": 1.0}
            for m in range(7, 13)
        ] + [
            {"date": f"2026-{m:02d}-15", "amount": 1.0}
            for m in range(1, 7)
        ]
        ret, meta = compute_1y_total_return_mk_simple(nav, divs)
        assert math.isclose(ret, 12.0, abs_tol=0.01)
        assert meta["div_count"] == 12


# ──────────────────────────────────────────────────────────
# 2. 1Y 窗口邊界
# ──────────────────────────────────────────────────────────
class TestWindowBoundary:
    def test_window_days_recorded(self):
        """meta.window_days 應記錄實際天數。"""
        nav = {"2025-06-26": 100.0, "2026-06-26": 105.0}
        _, meta = compute_1y_total_return_mk_simple(nav, [])
        assert meta["window_days"] == 365

    def test_short_window_lt_1y(self):
        """基金不滿 1 年 → 用最早 NAV 起點 + 標 mk_strict_short_window。"""
        nav = {"2026-01-01": 100.0, "2026-06-26": 105.0}  # 半年
        ret, meta = compute_1y_total_return_mk_simple(nav, [])
        assert ret is not None
        assert meta["source"] == "mk_strict_short_window"
        assert 170 < meta["window_days"] < 200  # ~半年

    def test_div_before_window_excluded(self):
        """配息日早於 1Y 窗起點 → 排除。"""
        nav = {"2025-06-26": 100.0, "2026-06-26": 100.0}
        divs = [
            {"date": "2025-01-01", "amount": 100.0},  # 一年半前,排除
            {"date": "2025-12-01", "amount": 3.0},   # 窗內,算入
        ]
        ret, meta = compute_1y_total_return_mk_simple(nav, divs)
        assert math.isclose(ret, 3.0, abs_tol=0.01)
        assert meta["div_count"] == 1

    def test_div_after_window_excluded(self):
        """配息日晚於截止日 → 排除(理論上不該發生,但守邊界)。"""
        nav = {"2025-06-26": 100.0, "2026-06-26": 100.0}
        divs = [
            {"date": "2026-12-01", "amount": 100.0},  # 未來,排除
            {"date": "2026-05-01", "amount": 4.0},   # 窗內,算入
        ]
        ret, meta = compute_1y_total_return_mk_simple(nav, divs)
        assert math.isclose(ret, 4.0, abs_tol=0.01)

    def test_div_on_start_date_excluded(self):
        """配息日剛好在 start 日 → 排除(start exclusive,符合金融慣例)。"""
        nav = {
            "2025-06-26": 100.0,  # 1Y ago(start_date 候選)
            "2026-06-26": 100.0,
        }
        divs = [{"date": "2025-06-26", "amount": 5.0}]  # 剛好 start day
        ret, meta = compute_1y_total_return_mk_simple(nav, divs)
        # start exclusive → 不算入
        assert math.isclose(ret, 0.0, abs_tol=0.01)
        assert meta["div_count"] == 0


# ──────────────────────────────────────────────────────────
# 3. 邊界條件 / fail loud
# ──────────────────────────────────────────────────────────
class TestEdgeCases:
    def test_nav_1y_ago_zero_returns_none(self):
        """NAV_1Y_ago = 0 → None(§1 不偽造,除以 0 無意義)。"""
        nav = {"2025-06-26": 0.0, "2026-06-26": 100.0}
        ret, meta = compute_1y_total_return_mk_simple(nav, [])
        assert ret is None
        assert meta["error"] is not None
        assert "起點" in meta["error"] or "無效" in meta["error"]

    def test_nav_only_one_point_returns_none(self):
        nav = {"2026-06-26": 100.0}
        ret, meta = compute_1y_total_return_mk_simple(nav, [])
        assert ret is None
        assert "不足" in (meta["error"] or "")

    def test_nan_nav_filtered(self):
        """NaN NAV 應靜默 skip,不阻斷其他資料。"""
        nav = {"2025-06-26": 100.0, "2025-12-26": float("nan"),
               "2026-06-26": 110.0}
        ret, meta = compute_1y_total_return_mk_simple(nav, [])
        assert ret is not None
        assert math.isclose(ret, 10.0, abs_tol=0.01)

    def test_invalid_dividend_amounts_skipped(self):
        """配息金額 ≤ 0 / None / 非數值 → skip。"""
        nav = {"2025-06-26": 100.0, "2026-06-26": 100.0}
        divs = [
            {"date": "2025-12-01", "amount": 3.0},
            {"date": "2026-01-01", "amount": -1.0},   # 負,skip
            {"date": "2026-02-01", "amount": None},   # None,skip
            {"date": "2026-03-01", "amount": "abc"},  # 非數值,skip
            {"date": "", "amount": 5.0},              # 缺日期,skip
        ]
        ret, meta = compute_1y_total_return_mk_simple(nav, divs)
        assert math.isclose(ret, 3.0, abs_tol=0.01)
        assert meta["div_count"] == 1

    def test_tuple_shape_dividends(self):
        """支援 list of tuple(date, amount)。"""
        nav = {"2025-06-26": 100.0, "2026-06-26": 100.0}
        divs = [("2026-01-01", 5.0), ("2026-04-01", 3.0)]
        ret, meta = compute_1y_total_return_mk_simple(nav, divs)
        assert math.isclose(ret, 8.0, abs_tol=0.01)
        assert meta["div_count"] == 2

    def test_as_of_date_override(self):
        """as_of_date 指定 → 終點不取最新,1Y 窗回推自指定日。"""
        nav = {
            "2024-06-26": 100.0,
            "2025-06-26": 110.0,  # 用此當 end
            "2026-06-26": 150.0,  # 超出 as_of,不算
        }
        ret, meta = compute_1y_total_return_mk_simple(
            nav, [], as_of_date="2025-06-26"
        )
        assert math.isclose(ret, 10.0, abs_tol=0.01)
        assert meta["nav_end"] == 110.0
        assert meta["nav_start"] == 100.0


# ──────────────────────────────────────────────────────────
# 4. check_eating_principal_1y_mk v19.175 — wb01 業界複利優先
# ──────────────────────────────────────────────────────────
# v19.175 user 拍板「網路資料(wb01 MoneyDJ 官方)優先,自算 fallback」,
# v19.149 的「mk_simple 優先」契約已過時:
#   - 主源 走 compute_1y_total_return chain(perf["1Y"] > ret_1y_total > ret_1y > NAV 外推)
#   - mk_simple 退居「對照欄」(_tr1y_meta 內保留 mk_simple_value 供 UI 顯示)
# 詳 services/fund_dividend_health.check_eating_principal_1y_mk docstring。
class TestCheckEatingV19175WbCompoundFirst:
    """v19.175 契約:tr1y 主源走 wb01 業界複利優先(對齊 Tab2/Tab3 SSOT)。"""

    def test_metrics_ret_1y_only_uses_ret_1y_path(self):
        """fund 只有 metrics.ret_1y(無 perf / 無 series)→ tr1y 走 ret_1y precedence。

        v19.175:gap = 7 - 4 = 3pp > 2pp 警戒線 → 🔴 吃本金(3 色制)。
        """
        fund = {
            "moneydj_div_yield": 7.0,
            "metrics": {"ret_1y": 4.0},
        }
        r = check_eating_principal_1y_mk(fund)
        assert r is not None
        assert "吃本金" in r["status"], (
            f"預期吃本金(gap=3pp > 2pp),實際 {r['status']}"
        )
        assert "ret_1y" in r["_tr1y_method"], (
            f"預期走 ret_1y precedence,實際 {r['_tr1y_method']}"
        )

    def test_with_series_dividends_still_uses_wb_industry_precedence(self):
        """v19.175:fund 有 series + dividends 也不再以 mk_simple 為主源。

        precedence:perf['1Y'] > ret_1y_total > ret_1y > NAV 外推。
        本 case:metrics.ret_1y=99(business path)→ tr1y=99, adr=5 → 健康。
        mk_simple 算出的 13% 退居 `_tr1y_meta.mk_simple_value` 對照欄。
        """
        fund = {
            "moneydj_div_yield": 5.0,
            "metrics": {"ret_1y": 99.0},  # v19.175 走業界路徑
            "series": {"2025-06-26": 100.0, "2026-06-26": 110.0},
            "dividends": [{"date": "2026-01-01", "amount": 3.0}],
        }
        r = check_eating_principal_1y_mk(fund)
        assert r is not None
        assert "ret_1y" in r["_tr1y_method"], (
            f"v19.175 應走業界 ret_1y precedence,實際 {r['_tr1y_method']}"
        )
        # tr1y=99, adr=5 → gap=-94 → 🟢 健康
        assert "健康" in r["status"], f"預期健康,實際 {r['status']}"
        # mk_simple 對照值仍計算並保留於 _tr1y_meta
        assert r["_tr1y_meta"] is not None
        assert "mk_simple_value" in r["_tr1y_meta"]
        assert math.isclose(r["_tr1y_meta"]["mk_simple_value"], 13.0, abs_tol=0.01), (
            f"對照欄 mk_simple_value 應算出 13%(10 + 3),實際 {r['_tr1y_meta']['mk_simple_value']}"
        )

    def test_nested_shape_with_perf_1y_wins(self):
        """Nested shape + perf['1Y']=15% → perf 為最高優先級,SSOT wb01。"""
        fund = {
            "moneydj_raw": {
                "moneydj_div_yield": 7.0,
                "perf": {"1Y": 15.0},  # wb01 模本
                "perf_source": "wb01",
                "series": {"2025-06-26": 100.0, "2026-06-26": 102.0},
                "dividends": [{"date": "2026-03-01", "amount": 2.0}],
            },
            "metrics": {"ret_1y": 99.0},  # 誘餌:perf 應勝出
        }
        r = check_eating_principal_1y_mk(fund)
        assert r is not None
        # perf['1Y']=15 為最高優先 → tr1y=15, adr=7 → gap=-8 → 🟢 健康
        assert "wb01" in r["_tr1y_method"], (
            f"v19.175 應走 wb01 (perf['1Y']) 最權威,實際 {r['_tr1y_method']}"
        )
        assert "健康" in r["status"]

    def test_v19148_helper_signature_unchanged(self):
        """v19.148 既有 caller 介面 100% 相容(僅 fund dict input,return dict)。"""
        fund = {"moneydj_div_yield": 5.0, "metrics": {"ret_1y": 10.0}}
        r = check_eating_principal_1y_mk(fund)
        assert r is not None
        # 既有欄位仍存在
        for k in ("status", "alert_level", "coverage", "eating_principal"):
            assert k in r, f"v19.148 欄位 {k} 應仍存在"
        # v19.149 新增 meta 欄位
        assert "_tr1y_method" in r
        assert "_tr1y_window_days" in r
        assert "_tr1y_meta" in r


# ──────────────────────────────────────────────────────────
# 5. Property:單利 公式具備加法可拆性
# ──────────────────────────────────────────────────────────
class TestPropertySimpleFormulaAdditivity:
    """MK 單利的關鍵性質:nav 報酬與 div 報酬可加(不像複利會有 cross-term)。
    這條 property 守:任何時候 ret = nav_change + div_total 必須成立。"""

    @pytest.mark.parametrize("nav_pct,div_pct", [
        (10.0, 5.0), (-5.0, 8.0), (0.0, 0.0),
        (20.0, 0.0), (0.0, 12.0), (-15.0, 15.0),
    ])
    def test_additivity(self, nav_pct: float, div_pct: float):
        nav_start = 100.0
        nav_end = 100.0 * (1 + nav_pct / 100)
        div_sum = 100.0 * (div_pct / 100)  # 每單位累計配息
        nav = {"2025-06-26": nav_start, "2026-06-26": nav_end}
        divs = [{"date": "2026-01-01", "amount": div_sum}] if div_sum > 0 else []
        ret, meta = compute_1y_total_return_mk_simple(nav, divs)
        assert ret is not None
        assert math.isclose(ret, nav_pct + div_pct, abs_tol=0.01), (
            f"加法可拆性違反:預期 {nav_pct} + {div_pct} = {nav_pct + div_pct},"
            f"實際 {ret}"
        )
