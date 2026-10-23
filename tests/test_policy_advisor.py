"""
test_policy_advisor — 純規則建議引擎單元測試
覆蓋 10 條規則 + 邊界條件（rank 邊界、None / 空 dict 容錯）。
"""

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
    POSITION_EVIDENCE_ONLY,
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
# ~~規則 1～9:σ 驅動的行動文字(跌了就買 / 汰弱換強 / 加碼參考區 / 留意加碼點 / 勿接刀 /
# 停利檢視 / 健康持有 / 創新高停利 / 標準持有)~~
# 2026-10-23 客戶裁示 BL-0428 DG-3 C(DEC-2026-10-23-11):全部退休。
# σ 可判定 → 只回中性位置證據(POSITION_EVIDENCE_ONLY,灰);舊規則的每一個觸發條件
# (含邊界 −2.0 / +0.5、VIX 恐慌、吃本金、60MA 上/下)都改斷言「不再產生行動文字」。
# ──────────────────────────────────────────────────────────────────────
_ACTION_WORDS = ("加碼", "跌了就買", "汰弱換強", "承接", "停利", "健康持有", "標準持有",
                 "勿接刀", "創新高", "攤平", "買", "賣")

_OLD_RULE_TRIGGERS = [
    ({"sigma_rank": -2.3}, {"alert_level": "green"}, None, 32.0),     # 舊規則 1
    ({"sigma_rank": -2.5}, {"alert_level": "red"}, None, 35.0),       # 舊規則 1 優先於 2
    ({"sigma_rank": -2.4}, {"alert_level": "red", "coverage": 0.45}, None, 15.0),  # 舊規則 2
    ({"sigma_rank": -2.1}, {"alert_level": "green"}, None, None),     # 舊規則 3
    ({"sigma_rank": -2.0}, {"alert_level": "green"}, None, None),     # 舊邊界 −2.0
    ({"sigma_rank": -1.3}, {"alert_level": "green"}, "up", None),     # 舊規則 4
    ({"sigma_rank": -1.7}, {"alert_level": "green"}, "down", None),   # 舊規則 5
    ({"sigma_rank": -0.2}, {"alert_level": "red", "coverage": 0.8}, None, None),  # 舊規則 6
    ({"sigma_rank": 0.1}, {"alert_level": "green", "coverage": 1.5}, None, None),  # 舊規則 7
    ({"sigma_rank": 0.5}, {"alert_level": "green"}, None, None),      # 舊邊界 +0.5
    ({"sigma_rank": 1.2}, {"alert_level": "green"}, None, None),      # 舊規則 8
    ({"sigma_rank": -0.8}, {"alert_level": "green"}, None, None),     # 舊規則 9
    ({"sigma_rank": -1.5}, None, "up", None),                         # dividend_info None
    ({"sigma_rank": -2.5}, {"alert_level": "red"}, None, None),       # 無 coverage
]


def test_dg3_old_sigma_rules_no_longer_produce_action_text():
    _retired = {DEEP_DROP_VIX_BUY, DEEP_DROP_RED_SWITCH, DEEP_DROP_NEUTRAL, MID_DROP_MA_UP,
                MID_DROP_MA_DOWN, NEAR_HWM_RED_TP_CHECK, NEAR_HWM_GREEN_HOLD,
                ABOVE_HWM_TAKE_PROFIT, DEFAULT_HOLD}
    for _sig, _div, _ma, _vix in _OLD_RULE_TRIGGERS:
        r = advise_fund(_sig, _div, ma60_trend=_ma, vix=_vix)
        assert r["code"] == POSITION_EVIDENCE_ONLY, (_sig, r)
        assert r["code"] not in _retired
        assert r["color"] == "grey"
        assert "不是買賣建議" in r["text"]
        _body = r["text"].replace("不是買賣建議", "")
        for _w in _ACTION_WORDS:
            assert _w not in _body, (_sig, _w, r["text"])


def test_dg3_position_text_uses_ssot_three_state_label():
    # 有 SSOT label → 原樣使用;沒有 → 由 hwm_position_from_rank 對映(同一把尺)
    r = advise_fund({"sigma_rank": -0.9, "label": "中段（−1.5σ ～ −0.5σ）"}, None)
    assert "中段" in r["text"]
    assert "遠離高點" in advise_fund({"sigma_rank": -1.6}, None)["text"]
    assert "接近高點" in advise_fund({"sigma_rank": -0.1}, None)["text"]


def test_dg3_dividend_ma_vix_do_not_change_output():
    """dividend / 60MA / VIX 原本只在與 σ 組合時才用;σ 規則退休後它們不得單獨產生建議。"""
    _base = advise_fund({"sigma_rank": -2.3}, None)
    for _div in (None, {"alert_level": "red"}, {"alert_level": "green", "coverage": 2.0}):
        for _ma in (None, "up", "down"):
            for _vix in (None, 10.0, 99.0):
                assert advise_fund({"sigma_rank": -2.3}, _div, _ma, _vix) == _base


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


def test_recommend_policy_risk_heavy_drop_retired_dg3():
    """~~核心比 75% 達標、但 2 檔 σ ≤ -2 → 系統性風險警示「可分批加碼」~~
    2026-10-23 DG-3 C:P3 退休 —— 深跌不再產生加碼文字;位置可判定 → 照常走 P5。"""
    r = recommend_policy([
        _fund(750_000, is_core=True,  sigma_rank=-2.3),
        _fund(250_000, is_core=False, sigma_rank=-2.1),
    ], target_core_pct=75.0)
    assert r["code"] != POLICY_RISK_HEAVY_DROP
    assert r["code"] == POLICY_HEALTHY
    assert "加碼" not in r["text"] and "超跌" not in r["text"]


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


def test_recommend_policy_red_still_fires_when_deep_drop_retired():
    """~~同時觸發 P3 + P4 → P3 短路勝出~~ → DG-3 C 後 P3 不存在,P4(吃本金,非 σ 規則)照常。"""
    r = recommend_policy([
        _fund(500_000, is_core=True,
              sigma_rank=-2.5, alert_level="red"),
        _fund(500_000, is_core=False,
              sigma_rank=-2.2, alert_level="red"),
    ], target_core_pct=50.0)  # 偏差 0%，不觸發 P1/P2
    assert r["code"] == POLICY_RISK_HEAVY_RED


def test_recommend_policy_return_shape():
    r = recommend_policy([_fund(1_000_000)])
    assert set(r.keys()) == {"text", "code", "color"}
    assert r["text"] and isinstance(r["text"], str)
