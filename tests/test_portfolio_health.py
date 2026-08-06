"""test_portfolio_health — v18.163 PR：組合健康度 KPI helper 單元測試。

涵蓋 compute_health_kpis 純函式邏輯（render_hero_kpi_cards 依賴 streamlit runtime，
留 PR D smoke 測補）。
"""
from __future__ import annotations

import pandas as pd

from ui.helpers.portfolio_health import compute_health_kpis


def test_compute_health_kpis_empty_input():
    out = compute_health_kpis([], None)
    assert out["n_funds"] == 0
    assert out["n_buy"] == 0
    assert out["n_warn"] == 0
    assert out["n_take"] == 0
    assert out["ratio_label"] == "—"
    assert out["ratio_delta"] is None


def test_compute_health_kpis_none_input():
    out = compute_health_kpis(None, None)
    assert out["n_funds"] == 0
    assert out["ratio_label"] == "—"


def test_compute_health_kpis_dedup_by_code():
    """同 code 跨多保單只算一次（mirror mk_dashboard L694-702 行為）。"""
    funds = [
        {"code": "F1", "policy_id": "P1", "loaded": True},
        {"code": "F1", "policy_id": "P2", "loaded": True},   # 重複 code
        {"code": "F2", "policy_id": "P1", "loaded": True},
        {"code": "", "policy_id": "P1", "loaded": True},      # 空 code skip
        {"code": "F3", "loaded": False},                       # 未載入 skip
        {"code": "F4", "loaded": True, "load_error": "boom"},  # 錯誤 skip
    ]
    out = compute_health_kpis(funds, None)
    assert out["n_funds"] == 2   # F1 + F2


def test_compute_health_kpis_mk_labels():
    """從 mk_df 算 撿便宜雷達 / 留校查看 / 停利提醒。"""
    funds = [{"code": f"F{i}", "loaded": True} for i in range(5)]
    mk_df = pd.DataFrame([
        {"MK_Class": "Core",      "Price_Zone": "Buy_Zone",       "Health_Check": "OK",            "Principal_Erosion": "Healthy"},
        {"MK_Class": "Core",      "Price_Zone": "Buy_Zone_Deep",  "Health_Check": "OK",            "Principal_Erosion": "Healthy"},
        {"MK_Class": "Satellite", "Price_Zone": "Take_Profit",    "Health_Check": "OK",            "Principal_Erosion": "Healthy"},
        {"MK_Class": "Core",      "Price_Zone": "Hold",           "Health_Check": "Sharpe_Warning", "Principal_Erosion": "Eroding"},
        {"MK_Class": "Satellite", "Price_Zone": "Hold",           "Health_Check": "Weak",          "Principal_Erosion": "Healthy"},
    ])
    out = compute_health_kpis(funds, mk_df)
    assert out["n_buy"] == 2   # Buy_Zone + Buy_Zone_Deep
    # Sharpe_Warning(1) + Weak(1) + Core+Eroding(1) = 3
    assert out["n_warn"] == 3
    # Satellite + Take_Profit
    assert out["n_take"] == 1


def test_compute_health_kpis_ratio_label_is_fund_count_not_amount():
    """ratio_label 是**檔數**口徑，且不帶任何目標值比較。

    修正前會紅（舊行為衝突紅）：舊版 label 是「核心 70% / 衛星 30%」百分比，
    且 ratio_delta 會拿檔數去比寫死的 80 —— 與「① 配置總覽」的金額版目標偏差
    給出相反的再平衡結論。金額口徑的唯一真相在
    ui/helpers/portfolio/allocation.summarize_core_satellite。
    """
    funds = [{"code": f"F{i}", "loaded": True} for i in range(10)]
    mk_df = pd.DataFrame([
        *[{"MK_Class": "Core",      "Price_Zone": "Hold", "Health_Check": "OK", "Principal_Erosion": "Healthy"}] * 7,
        *[{"MK_Class": "Satellite", "Price_Zone": "Hold", "Health_Check": "OK", "Principal_Erosion": "Healthy"}] * 3,
    ])
    out = compute_health_kpis(funds, mk_df)
    assert out["n_classed"] == 10
    # pct_core / pct_sat 仍保留（檔數百分比），供其他 caller 用
    assert out["pct_core"] == 70
    assert out["pct_sat"] == 30
    # label 改成檔數，且不再出現百分比或目標值
    assert "7 檔" in out["ratio_label"]
    assert "3 檔" in out["ratio_label"]
    assert "%" not in out["ratio_label"]
    assert out["ratio_delta"] is None


def test_compute_health_kpis_no_hardcoded_target_comparison():
    """檔數口徑不得再與任何寫死目標比較（修正前會紅：舊版回「符合 …」字串）。"""
    funds = [{"code": f"F{i}", "loaded": True} for i in range(10)]
    mk_df = pd.DataFrame([
        *[{"MK_Class": "Core",      "Price_Zone": "Hold", "Health_Check": "OK", "Principal_Erosion": "Healthy"}] * 8,
        *[{"MK_Class": "Satellite", "Price_Zone": "Hold", "Health_Check": "OK", "Principal_Erosion": "Healthy"}] * 2,
    ])
    out = compute_health_kpis(funds, mk_df)
    assert out["pct_core"] == 80
    assert out["ratio_delta"] is None


def test_compute_health_kpis_cashflow_eat_principal():
    """吃本金邏輯：含息 < 配息 且配息 > 0 → n_eat++。"""
    funds = [
        # 含息 3% < 配息 5% → 吃本金
        {"code": "EAT1", "loaded": True,
         "moneydj_raw": {"moneydj_div_yield": 5.0, "perf": {"1Y": 3.0}},
         "metrics": {}, "series": [100, 101, 102, 103]},
        # 含息 10% > 配息 5% → 健康
        {"code": "OK1", "loaded": True,
         "moneydj_raw": {"moneydj_div_yield": 5.0, "perf": {"1Y": 10.0}},
         "metrics": {}, "series": [100, 105, 108, 110]},
        # 無配息（div=0）→ 健康
        {"code": "NODIV", "loaded": True,
         "moneydj_raw": {"perf": {"1Y": 2.0}},
         "metrics": {}, "series": [100, 101, 102]},
    ]
    out = compute_health_kpis(funds, None)
    assert out["n_funds"] == 3
    assert out["n_eat"] == 1
    assert out["n_cash_ok"] == 2
    assert out["n_na"] == 0


def test_compute_health_kpis_cashflow_na_when_no_1y_data():
    """compute_1y_total_return 回 None → n_na++（不誤判吃本金）。"""
    funds = [
        # 沒 perf / 沒 series → 1Y 算不出來
        {"code": "NA1", "loaded": True,
         "moneydj_raw": {"moneydj_div_yield": 5.0},
         "metrics": {}},
    ]
    out = compute_health_kpis(funds, None)
    assert out["n_funds"] == 1
    assert out["n_na"] == 1
    assert out["n_eat"] == 0
    assert out["n_cash_ok"] == 0


def test_compute_health_kpis_no_mk_df_only_cashflow():
    """沒 mk_df 時 MK 標籤全 0、配置 ratio 全 0，但現金流計算仍正常。"""
    funds = [
        {"code": "F1", "loaded": True,
         "moneydj_raw": {"moneydj_div_yield": 5.0, "perf": {"1Y": 10.0}},
         "metrics": {}, "series": [100, 105]},
    ]
    out = compute_health_kpis(funds, None)
    assert out["n_funds"] == 1
    assert out["n_cash_ok"] == 1
    assert out["n_buy"] == 0
    assert out["n_warn"] == 0
    assert out["n_take"] == 0
    assert out["ratio_label"] == "—"
