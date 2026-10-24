"""v19.181 — services.health.replacement 純函式單元測試。

守住  4 規則心型警結合判定邏輯:
(a) 吃本金 1Y·且持有 ≥ 1 年 → hard trigger
(b) 4D Grade F → hard trigger;Grade D → observe 訊號
(c) 3-3-3 未通過且持有 ≥ 3 年 → hard trigger
(d) Sharpe < 0 且 max_dd < -30% → hard trigger

任一 hard trigger 中 → 🔴 換 / 1-2 observe → 🟡 / 全部未中 → 🟢
所有關鍵指標缺 → ⬜ unknown
"""
from __future__ import annotations

from services.health.replacement import check_replacement_recommendation

# DG-6（DEC-2026-10-24-12）：分類未判定（is_core_bucket(category) is None）→ ⬜ 不給換／留結論。
# 本檔各規則測試原本的 fixture 都沒有基金類別 —— 那正是現在被禁止的「分類未判定仍給換／留」。
# 為保留各規則測試原本要守的語意，fixture 一律補上一個可對應的非 Core 類別（_CAT）；
# 分類未判定本身的行為另由 tests/test_dg6_missing_no_action.py 守。
_CAT = "全球股票型"   # services.regime_fit.asset_bucket → 「股票」（非 Core）


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
        # DG-6（DEC-2026-10-24-12）：「判不動時不得 🟢 保留」—— 原 fixture 只有 sharpe / max_dd /
        # 純淨值 3Y，規則 (a)(b)(c) 都判不動（無吃本金訊號、無 4D 等第、無含息 3Y → 3-3-3 ⬜），
        # 舊行為卻給 🟢。現改為：原 fixture → ⬜ 無法判定；補齊 4 規則所需資料 → 🟢 保留。
        thin = {"category": _CAT, "metrics": {
            "sharpe": 1.5,
            "max_drawdown": -10.0,
            "ret_3y_ann": 9.0,
        }}
        r_thin = check_replacement_recommendation(thin, holding_years=4)
        assert r_thin["verdict"] == "unknown" and r_thin["emoji"] == "⬜"
        assert r_thin["status"] == "rules_incomplete"
        assert "🟢" not in r_thin["message"] and "保留 —" not in r_thin["message"]

        fd = {
            "category": _CAT,
            "moneydj_raw": {"perf": {"1Y": 12.0}, "moneydj_div_yield": 5.0},
            "metrics": {
                "sharpe": 1.5, "std_1y": 8.0, "max_drawdown": -10.0,
                "ret_3y_ann": 9.0, "ret_3y_ann_tr": 9.0,
                "ret_1y_total": 12.0, "ret_1y_window_days": 365,
                "ret_1y_div_count": 12, "annual_div_rate": 5.0,
            },
        }
        r = check_replacement_recommendation(fd, holding_years=4)
        assert r["verdict"] == "keep"
        assert r["emoji"] == "🟢"
        assert r["status"] == "ok"
        assert not r["triggered_rules"]

    def test_sharpe_positive_short_dd_keep(self):
        # 給足 4D 4 維資料,避免 Grade D 觸發 observe(b*)
        # DG-6（DEC-2026-10-24-12）：補基金類別（分類需可判定）＋ 12M 實際配息與含息 1Y
        # （原 fixture 有配息跡象卻無 12M 配息紀錄 → 吃本金 ⬜ → 規則 (a) 判不動 → 不得 🟢）。
        fd = {
            "category": _CAT,
            "moneydj_raw": {"perf": {"1Y": 12.0}, "moneydj_div_yield": 5.0},
            "metrics": {
                "sharpe": 1.0,
                "std_1y": 8.0,
                "max_drawdown": -15.0,
                "ret_3y_ann": 9.0,
                "ret_1y_total": 12.0, "ret_1y_window_days": 365,
                "ret_1y_div_count": 12, "annual_div_rate": 5.0,
            },
        }
        r = check_replacement_recommendation(fd, holding_years=2)
        assert r["verdict"] == "keep"


class TestRuleA_EatPrincipal:
    """規則 (a):吃本金 1Y·且持有 ≥ 1 年 → hard trigger。"""

    def test_eat_principal_long_hold_triggers(self):
        # 構造會被 check_eating_principal_1y_mk 判吃本金的 fd:
        # adr 高(10%)、tr1y 低(2%)
        # 2026-10-23 裁示 1B:判定讀本地還原值 + 近 12 個月實際配息率(官方值只對帳)
        fd = {
            "category": _CAT,  # DG-6（DEC-2026-10-24-12）：分類需可判定，否則 ⬜ 不給換／留
            "moneydj_raw": {
                "perf": {"1Y": 2.0},
                "moneydj_div_yield": 10.0,
            },
            "metrics": {"ret_1y_total": 2.0, "ret_1y_window_days": 365,
                        "ret_1y_div_count": 12, "annual_div_rate": 10.0},
        }
        r = check_replacement_recommendation(fd, holding_years=2)
        assert r["verdict"] == "replace"
        assert any("(a)" in t for t in r["triggered_rules"])

    def test_eat_principal_short_hold_observes_only(self):
        fd = {
            "category": _CAT,  # DG-6（DEC-2026-10-24-12）：分類需可判定，否則 ⬜ 不給換／留
            "moneydj_raw": {
                "perf": {"1Y": 2.0},
                "moneydj_div_yield": 10.0,
            },
            "metrics": {"ret_1y_total": 2.0, "ret_1y_window_days": 365,
                        "ret_1y_div_count": 12, "annual_div_rate": 10.0},
        }
        r = check_replacement_recommendation(fd, holding_years=0.5)
        # 持有 < 1 年 → 不下 hard trigger,但計觀察分
        assert r["verdict"] in ("observe", "replace")  # 可能其他規則也中
        # 至少不該無原因 keep
        assert r["verdict"] != "keep"


class TestRuleD_ExtremelyBadRiskAdjusted:
    """規則 (d):Sharpe < 0 AND max_dd < -30% → hard trigger。"""

    def test_sharpe_negative_dd_severe_triggers(self):
        # DG-6（DEC-2026-10-24-12）：補基金類別（分類未判定時不給換／留結論）
        fd = {"category": _CAT, "metrics": {
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
            "category": _CAT,  # DG-6（DEC-2026-10-24-12）：分類需可判定，否則 ⬜ 不給換／留
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
        # DG-6（DEC-2026-10-24-12）：補基金類別（分類未判定時不給換／留結論）
        fd = {"category": _CAT, "metrics": {
            "sharpe": 0.5,
            "max_drawdown": -35.0,
        }}
        r = check_replacement_recommendation(fd, holding_years=2)
        assert not any("(d)" in t for t in r["triggered_rules"])


class TestRuleC_333:
    """規則 (c):3-3-3 未通過且持有 ≥ 3 年 → hard trigger。"""

    def test_low_3y_long_hold_triggers(self):
        # 持有 4 年 + 3 年**含息**年化 3%(< 7% 不通過)
        # 2026-10-23 裁示 3A:3-3-3 的 3 年年化唯一來源 = `metrics.ret_3y_ann_tr`(配息還原淨值法),
        # 不再退純淨值 `ret_3y_ann` —— 本 fixture 原本只給 `ret_3y_ann` 3.0,3A 後那條會是 ⬜
        # (無法判定,不觸發 (c)),故改餵 SSOT 的輸入鍵;規則 (c) 本身的語意未改。
        # 純淨值-only 不再觸發 (c) 的反向案例見 test_nav_only_3y_no_longer_triggers_c。
        # DG-6（DEC-2026-10-24-12）：補基金類別（分類未判定時不給換／留結論）
        fd = {"category": _CAT, "metrics": {
            "ret_3y_ann_tr": 3.0,
            "sharpe": 0.5,  # 避免 unknown
        }}
        r = check_replacement_recommendation(fd, holding_years=4)
        assert r["verdict"] == "replace"
        assert any("(c)" in t for t in r["triggered_rules"])

    def test_nav_only_3y_no_longer_triggers_c(self):
        """3A:只有純淨值 `ret_3y_ann`(無含息 `ret_3y_ann_tr`)→ 3-3-3 ⬜ → 不得觸發 (c)(§1 缺 ≠ 不通過)。"""
        # DG-6（DEC-2026-10-24-12）：補基金類別（分類未判定時不給換／留結論）
        fd = {"category": _CAT, "metrics": {"ret_3y_ann": 3.0, "sharpe": 0.5}}
        r = check_replacement_recommendation(fd, holding_years=4)
        assert not any(t.startswith("(c)") for t in r["triggered_rules"])

    def test_low_3y_short_hold_observes_only(self):
        # DG-6（DEC-2026-10-24-12）：補基金類別（分類未判定時不給換／留結論）
        fd = {"category": _CAT, "metrics": {
            "ret_3y_ann": 3.0,
            "sharpe": 0.5,
        }}
        r = check_replacement_recommendation(fd, holding_years=2)
        # 持有 < 3 年 → 不下 hard trigger
        # DG-6（DEC-2026-10-24-12）：本 fixture 無 4D 等第 → 規則 (b) 判不動 → 不得 🟢，回 ⬜ 無法判定
        assert r["verdict"] in ("observe", "keep", "unknown")
        assert r["verdict"] != "replace"
        assert not any("(c) " in t for t in r["triggered_rules"]
                       if not t.startswith("(c*)"))


class TestObserveAggregation:
    """1-2 個觀察訊號 → 🟡 observe;不該升級 replace。"""

    def test_single_observe_signal(self):
        # Sharpe < 0 但 dd 沒到 → 觀察(d*) only
        # 補完整 4D 維度避免 Grade F 誤觸 (b)
        fd = {
            "category": _CAT,  # DG-6（DEC-2026-10-24-12）：分類需可判定，否則 ⬜ 不給換／留
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
