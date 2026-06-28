"""v19.181 — services.fund_replacement_verdict 純函式單元測試。

守住 MK 4 規則心型警結合判定邏輯:
(a) 吃本金 1Y·MK 且持有 ≥ 1 年 → hard trigger
(b) 4D Grade F → hard trigger;Grade D → observe 訊號
(c) 3-3-3 未通過且持有 ≥ 3 年 → hard trigger
(d) Sharpe < 0 且 max_dd < -30% → hard trigger

任一 hard trigger 中 → 🔴 換 / 1-2 observe → 🟡 / 全部未中 → 🟢
所有關鍵指標缺 → ⬜ unknown
"""
from __future__ import annotations

from services.health.replacement import check_replacement_recommendation


class TestEmptyFd:
    """空 fd / 全 None input — 應回 unknown,不假綠燈。"""

    def test_empty_fd_returns_unknown(self):
        r = check_replacement_recommendation({})
        assert r["verdict"] == "unknown"
        assert r["emoji"] == "⬜"

    def test_no_holding_no_metrics_returns_unknown(self):
        r = check_replacement_recommendation({"metrics": {}})
        assert r["verdict"] == "unknown"


class TestKeepVerdict:
    """無任何規則中 + 至少 1 個 signal → keep(🟢)。"""

    def test_all_healthy_returns_keep(self):
        fd = {"metrics": {
            "sharpe": 1.5,
            "max_drawdown": -10.0,
            "ret_3y_ann": 9.0,
        }}
        r = check_replacement_recommendation(fd, holding_years=4)
        assert r["verdict"] == "keep"
        assert r["emoji"] == "🟢"
        assert not r["triggered_rules"]

    def test_sharpe_positive_short_dd_keep(self):
        # 給足 4D 4 維資料,避免 Grade D 觸發 observe(b*)
        fd = {
            "moneydj_raw": {"perf": {"1Y": 12.0}, "moneydj_div_yield": 5.0},
            "metrics": {
                "sharpe": 1.0,
                "std_1y": 8.0,
                "max_drawdown": -15.0,
                "ret_3y_ann": 9.0,
            },
        }
        r = check_replacement_recommendation(fd, holding_years=2)
        assert r["verdict"] == "keep"


class TestRuleA_EatPrincipal:
    """規則 (a):吃本金 1Y·MK 且持有 ≥ 1 年 → hard trigger。"""

    def test_eat_principal_long_hold_triggers(self):
        # 構造會被 check_eating_principal_1y_mk 判吃本金的 fd:
        # adr 高(10%)、tr1y 低(2%)
        fd = {
            "moneydj_raw": {
                "perf": {"1Y": 2.0},
                "moneydj_div_yield": 10.0,
            },
            "metrics": {},
        }
        r = check_replacement_recommendation(fd, holding_years=2)
        assert r["verdict"] == "replace"
        assert any("(a)" in t for t in r["triggered_rules"])

    def test_eat_principal_short_hold_observes_only(self):
        fd = {
            "moneydj_raw": {
                "perf": {"1Y": 2.0},
                "moneydj_div_yield": 10.0,
            },
            "metrics": {},
        }
        r = check_replacement_recommendation(fd, holding_years=0.5)
        # 持有 < 1 年 → 不下 hard trigger,但計觀察分
        assert r["verdict"] in ("observe", "replace")  # 可能其他規則也中
        # 至少不該無原因 keep
        assert r["verdict"] != "keep"


class TestRuleD_ExtremelyBadRiskAdjusted:
    """規則 (d):Sharpe < 0 AND max_dd < -30% → hard trigger。"""

    def test_sharpe_negative_dd_severe_triggers(self):
        fd = {"metrics": {
            "sharpe": -0.5,
            "max_drawdown": -35.0,
        }}
        r = check_replacement_recommendation(fd, holding_years=2)
        assert r["verdict"] == "replace"
        assert any("(d)" in t for t in r["triggered_rules"])

    def test_sharpe_negative_dd_mild_observes_only(self):
        # Sharpe < 0 但 dd 還可接受 → 計觀察(d*)
        # 補完整 4D 維度避免 Grade F 誤觸 (b)
        fd = {
            "moneydj_raw": {"perf": {"1Y": 8.0}, "moneydj_div_yield": 5.0},
            "metrics": {
                "sharpe": -0.2,
                "std_1y": 12.0,
                "max_drawdown": -15.0,
                "ret_3y_ann": 8.0,
            },
        }
        r = check_replacement_recommendation(fd, holding_years=2)
        assert r["verdict"] == "observe"

    def test_sharpe_positive_dd_severe_no_d_trigger(self):
        # Sharpe 0.5 不滿足 < 0 → 不該 (d) trigger
        fd = {"metrics": {
            "sharpe": 0.5,
            "max_drawdown": -35.0,
        }}
        r = check_replacement_recommendation(fd, holding_years=2)
        assert not any("(d)" in t for t in r["triggered_rules"])


class TestRuleC_333:
    """規則 (c):3-3-3 未通過且持有 ≥ 3 年 → hard trigger。"""

    def test_low_3y_long_hold_triggers(self):
        # 持有 4 年 + 3 年年化 3%(< 7% 不通過)
        fd = {"metrics": {
            "ret_3y_ann": 3.0,
            "sharpe": 0.5,  # 避免 unknown
        }}
        r = check_replacement_recommendation(fd, holding_years=4)
        assert r["verdict"] == "replace"
        assert any("(c)" in t for t in r["triggered_rules"])

    def test_low_3y_short_hold_observes_only(self):
        fd = {"metrics": {
            "ret_3y_ann": 3.0,
            "sharpe": 0.5,
        }}
        r = check_replacement_recommendation(fd, holding_years=2)
        # 持有 < 3 年 → 不下 hard trigger
        assert r["verdict"] in ("observe", "keep")
        assert not any("(c) " in t for t in r["triggered_rules"]
                       if not t.startswith("(c*)"))


class TestObserveAggregation:
    """1-2 個觀察訊號 → 🟡 observe;不該升級 replace。"""

    def test_single_observe_signal(self):
        # Sharpe < 0 但 dd 沒到 → 觀察(d*) only
        # 補完整 4D 維度避免 Grade F 誤觸 (b)
        fd = {
            "moneydj_raw": {"perf": {"1Y": 6.0}, "moneydj_div_yield": 5.0},
            "metrics": {
                "sharpe": -0.2,
                "std_1y": 14.0,
                "max_drawdown": -10.0,
                "ret_3y_ann": 9.0,
            },
        }
        r = check_replacement_recommendation(fd, holding_years=2)
        assert r["verdict"] == "observe"
        assert r["emoji"] == "🟡"


class TestSchema:
    """回傳 schema 守住 — caller 端可放心使用 keys。"""

    def test_return_has_required_keys(self):
        r = check_replacement_recommendation({"metrics": {"sharpe": 1.0}})
        required = {"verdict", "emoji", "label", "triggered_rules",
                    "observe_signals", "message"}
        assert required <= set(r.keys())

    def test_verdict_in_allowed_set(self):
        r = check_replacement_recommendation({})
        assert r["verdict"] in ("replace", "observe", "keep", "unknown")
