"""
test_policy_advisor — 純規則建議引擎單元測試
覆蓋 10 條規則 + 邊界條件（rank 邊界、None / 空 dict 容錯）。
"""
import pytest

from services.policy_advisor_service import (
    advise_fund,
    recommend_policy,
    INSUFFICIENT_DATA,
    DEEP_DROP_VIX_BUY,
    DEEP_DROP_RED_SWITCH,
    DEEP_DROP_NEUTRAL,
    MID_DROP_MA_UP,
    MID_DROP_MA_DOWN,
    NEAR_HWM_RED_TP_CHECK,
    NEAR_HWM_GREEN_HOLD,
    ABOVE_HWM_TAKE_PROFIT,
    DEFAULT_HOLD,
    POLICY_EMPTY,
    POLICY_CORE_OVER,
    POLICY_CORE_UNDER,
    POLICY_RISK_HEAVY_DROP,
    POLICY_RISK_HEAVY_RED,
    POLICY_HEALTHY,
)


# ──────────────────────────────────────────────────────────────────────
# 規則 0：資料不足
# ──────────────────────────────────────────────────────────────────────
def test_insufficient_when_sigma_info_none():
    r = advise_fund(None, {"alert_level": "green"})
    assert r["code"] == INSUFFICIENT_DATA
    assert r["color"] == "grey"
    assert "資料不足" in r["text"]


def test_insufficient_when_sigma_info_has_error():
    r = advise_fund({"error": "資料不足"}, {"alert_level": "green"})
    assert r["code"] == INSUFFICIENT_DATA


def test_insufficient_when_sigma_rank_missing():
    r = advise_fund({"hwm": 100.0}, {"alert_level": "green"})
    assert r["code"] == INSUFFICIENT_DATA


# ──────────────────────────────────────────────────────────────────────
# 規則 1：深度超跌 + 恐慌
# ──────────────────────────────────────────────────────────────────────
def test_deep_drop_vix_buy_triggers_when_vix_ge_30():
    r = advise_fund({"sigma_rank": -2.3}, {"alert_level": "green"}, vix=32.0)
    assert r["code"] == DEEP_DROP_VIX_BUY
    assert "跌了就買" in r["text"]
    assert "VIX 32" in r["text"]


def test_deep_drop_vix_buy_priority_over_red():
    # rank ≤ -2 + red + VIX≥30 → 規則 1 短路勝出（不被規則 2 蓋）
    r = advise_fund({"sigma_rank": -2.5}, {"alert_level": "red"}, vix=35.0)
    assert r["code"] == DEEP_DROP_VIX_BUY


# ──────────────────────────────────────────────────────────────────────
# 規則 2：深度超跌 + 配息吃本金
# ──────────────────────────────────────────────────────────────────────
def test_deep_drop_red_switch():
    r = advise_fund(
        {"sigma_rank": -2.4},
        {"alert_level": "red", "coverage": 0.45},
        vix=15.0,
    )
    assert r["code"] == DEEP_DROP_RED_SWITCH
    assert "汰弱換強" in r["text"]
    assert "0.45" in r["text"]


# ──────────────────────────────────────────────────────────────────────
# 規則 3：深度超跌 + 其他 → 加碼區
# ──────────────────────────────────────────────────────────────────────
def test_deep_drop_neutral_green():
    r = advise_fund({"sigma_rank": -2.1}, {"alert_level": "green"})
    assert r["code"] == DEEP_DROP_NEUTRAL
    assert "加碼" in r["text"]


def test_deep_drop_neutral_no_vix_no_red():
    r = advise_fund({"sigma_rank": -2.5}, {"alert_level": "yellow"}, vix=18.0)
    assert r["code"] == DEEP_DROP_NEUTRAL


# ──────────────────────────────────────────────────────────────────────
# 規則 4：中度跌 + 60MA 上升
# ──────────────────────────────────────────────────────────────────────
def test_mid_drop_ma_up():
    r = advise_fund(
        {"sigma_rank": -1.3},
        {"alert_level": "green"},
        ma60_trend="up",
    )
    assert r["code"] == MID_DROP_MA_UP
    assert "60MA 上升" in r["text"]


# ──────────────────────────────────────────────────────────────────────
# 規則 5：中度跌 + 60MA 下行
# ──────────────────────────────────────────────────────────────────────
def test_mid_drop_ma_down():
    r = advise_fund(
        {"sigma_rank": -1.7},
        {"alert_level": "green"},
        ma60_trend="down",
    )
    assert r["code"] == MID_DROP_MA_DOWN
    assert "60MA 下行" in r["text"]


# ──────────────────────────────────────────────────────────────────────
# 規則 6：接近 HWM + 紅燈 → 停利檢視
# ──────────────────────────────────────────────────────────────────────
def test_near_hwm_red_take_profit_check():
    r = advise_fund(
        {"sigma_rank": -0.2},
        {"alert_level": "red", "coverage": 0.8},
    )
    assert r["code"] == NEAR_HWM_RED_TP_CHECK
    assert "停利檢視" in r["text"]


# ──────────────────────────────────────────────────────────────────────
# 規則 7：接近 HWM + 綠燈 → 健康持有
# ──────────────────────────────────────────────────────────────────────
def test_near_hwm_green_hold():
    r = advise_fund(
        {"sigma_rank": 0.1},
        {"alert_level": "green", "coverage": 1.5},
    )
    assert r["code"] == NEAR_HWM_GREEN_HOLD
    assert r["color"] == "green"
    assert "健康持有" in r["text"]


# ──────────────────────────────────────────────────────────────────────
# 規則 8：超越 HWM → 過熱停利
# ──────────────────────────────────────────────────────────────────────
def test_above_hwm_take_profit():
    r = advise_fund({"sigma_rank": 1.2}, {"alert_level": "green"})
    assert r["code"] == ABOVE_HWM_TAKE_PROFIT
    assert "創新高" in r["text"]


# ──────────────────────────────────────────────────────────────────────
# 規則 9：其他 → 標準持有
# ──────────────────────────────────────────────────────────────────────
def test_default_hold_mid_drop_no_ma_trend():
    # -2 < rank ≤ -1 但無 ma60_trend → 落到 default
    r = advise_fund({"sigma_rank": -1.5}, {"alert_level": "green"})
    assert r["code"] == DEFAULT_HOLD


def test_default_hold_between_minus1_and_minus0_5():
    # rank 在 (-1, -0.5] 區間，無特別規則 → default
    r = advise_fund({"sigma_rank": -0.8}, {"alert_level": "green"})
    assert r["code"] == DEFAULT_HOLD


# ──────────────────────────────────────────────────────────────────────
# 邊界 / 容錯
# ──────────────────────────────────────────────────────────────────────
def test_boundary_exact_minus_2():
    # rank == -2.0 應落到深度超跌規則
    r = advise_fund({"sigma_rank": -2.0}, {"alert_level": "green"})
    assert r["code"] == DEEP_DROP_NEUTRAL


def test_boundary_exact_plus_0_5():
    # rank == 0.5 邊界，依規則 7 (接近 HWM) — 因為 -0.5 < 0.5 ≤ 0.5
    r = advise_fund({"sigma_rank": 0.5}, {"alert_level": "green"})
    assert r["code"] == NEAR_HWM_GREEN_HOLD


def test_dividend_info_none_does_not_crash():
    # dividend_info=None → 走 alert='grey' 路徑，不應 raise
    r = advise_fund({"sigma_rank": -1.5}, None, ma60_trend="up")
    # alert='grey' → 規則 4 不滿足（要 ma60_trend up 即可，alert 任意），所以匹配 MID_DROP_MA_UP
    assert r["code"] == MID_DROP_MA_UP


def test_coverage_none_does_not_crash():
    r = advise_fund(
        {"sigma_rank": -2.5},
        {"alert_level": "red"},   # 故意不放 coverage
    )
    assert r["code"] == DEEP_DROP_RED_SWITCH
    assert "N/A" in r["text"]


def test_vix_below_30_does_not_trigger_buy():
    r = advise_fund({"sigma_rank": -2.3}, {"alert_level": "green"}, vix=25.0)
    assert r["code"] == DEEP_DROP_NEUTRAL  # 不是 DEEP_DROP_VIX_BUY


def test_return_shape_always_has_three_keys():
    r = advise_fund({"sigma_rank": 0.0}, {"alert_level": "green"})
    assert set(r.keys()) == {"text", "code", "color"}
    assert isinstance(r["text"], str) and r["text"]
    assert isinstance(r["code"], str)
    assert isinstance(r["color"], str)


# ══════════════════════════════════════════════════════════════════════
# P3：recommend_policy — 保單級配置建議規則
# ══════════════════════════════════════════════════════════════════════
def _fund(invest, is_core=True, sigma_rank=None, alert_level=None):
    """測試用 fund factory。"""
    out = {"invest_twd": invest, "is_core": is_core}
    if sigma_rank is not None:
        out["sigma_info"] = {"sigma_rank": sigma_rank}
    if alert_level is not None:
        out["dividend_info"] = {"alert_level": alert_level}
    return out


def test_recommend_policy_empty_returns_empty_code():
    r = recommend_policy([])
    assert r["code"] == POLICY_EMPTY
    r2 = recommend_policy([_fund(0)])  # 零金額
    assert r2["code"] == POLICY_EMPTY


def test_recommend_policy_core_over():
    # 全核心 100% > target 75% + 10% → POLICY_CORE_OVER
    r = recommend_policy([_fund(1_000_000, is_core=True)], target_core_pct=75.0)
    assert r["code"] == POLICY_CORE_OVER
    assert "高於目標" in r["text"]


def test_recommend_policy_core_under():
    # 全衛星 0% < target 75% - 10% → POLICY_CORE_UNDER
    r = recommend_policy([_fund(500_000, is_core=False)], target_core_pct=75.0)
    assert r["code"] == POLICY_CORE_UNDER


def test_recommend_policy_risk_heavy_drop():
    # 核心比 75% 達標、但 2 檔 σ ≤ -2 → 系統性風險警示
    r = recommend_policy([
        _fund(750_000, is_core=True,  sigma_rank=-2.3),
        _fund(250_000, is_core=False, sigma_rank=-2.1),
    ], target_core_pct=75.0)
    assert r["code"] == POLICY_RISK_HEAVY_DROP
    assert "2" in r["text"]


def test_recommend_policy_risk_heavy_red():
    # 配置健康、無深度超跌、但 2 檔吃本金 → POLICY_RISK_HEAVY_RED
    r = recommend_policy([
        _fund(750_000, is_core=True,  alert_level="red"),
        _fund(250_000, is_core=False, alert_level="red"),
    ], target_core_pct=75.0)
    assert r["code"] == POLICY_RISK_HEAVY_RED


def test_recommend_policy_healthy():
    # 75% 核心、無風險訊號 → 健康
    r = recommend_policy([
        _fund(750_000, is_core=True,  sigma_rank=-0.2, alert_level="green"),
        _fund(250_000, is_core=False, sigma_rank=0.1,  alert_level="green"),
    ], target_core_pct=75.0)
    assert r["code"] == POLICY_HEALTHY
    assert r["color"] == "green"


def test_recommend_policy_drop_priority_over_red():
    """同時觸發 P3 + P4 → P3 短路勝出（更嚴重）。"""
    r = recommend_policy([
        _fund(500_000, is_core=True,
              sigma_rank=-2.5, alert_level="red"),
        _fund(500_000, is_core=False,
              sigma_rank=-2.2, alert_level="red"),
    ], target_core_pct=50.0)  # 偏差 0%，不觸發 P1/P2
    assert r["code"] == POLICY_RISK_HEAVY_DROP


def test_recommend_policy_return_shape():
    r = recommend_policy([_fund(1_000_000)])
    assert set(r.keys()) == {"text", "code", "color"}
    assert r["text"] and isinstance(r["text"], str)
