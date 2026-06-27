"""tests/test_mk_ssot_unification.py — MK 老師 1Y SSOT 跨 tab 一致性守衛(v19.148)

User 截圖回報:同一檔 FTZU8 在「健診總表(全期自算)」顯示 🔴 吃本金,
在「健診摘要表(1Y MoneyDJ)」顯示 🟢 健康 — SSOT 違憲。
v19.148 改用 services.fund_dividend_health.check_eating_principal_1y_mk 作為
唯一 1Y SSOT 入口,本檔守:
1. 新 helper 對 nested / flat 兩種 shape 都能讀到同樣 verdict
2. 同 fund dict → 同 verdict(不論 caller 是 fund_checkup 還是 tab_fund_grp_health)
3. 3-3-3 原則 helper 邊界條件
4. 既有 portfolio_service.dividend_safety SSOT 不回歸
"""
from __future__ import annotations

import pytest

from services.fund_dividend_health import (
    check_eating_principal_1y_mk,
    check_333_principle,
    classify_eating_principal,
)


# ──────────────────────────────────────────────────────────
# 1. check_eating_principal_1y_mk — 跨 shape SSOT
# ──────────────────────────────────────────────────────────
class TestCheckEatingPrincipal1yMk:
    def test_nested_shape_eating(self):
        """Nested {moneydj_raw, metrics} 形 → MK fund_checkup 路徑。"""
        fund = {
            "moneydj_raw": {"moneydj_div_yield": 8.0},
            "metrics": {"ret_1y": 5.0},
        }
        r = check_eating_principal_1y_mk(fund)
        assert r is not None
        assert "吃本金" in r["status"], f"含息 5 < 配息 8 → 應吃本金,實際 {r['status']}"

    def test_flat_shape_eating(self):
        """Flat {moneydj_div_yield, metrics} 形(_auto_fetch_moneydj 直回)。"""
        fund = {
            "moneydj_div_yield": 8.0,
            "metrics": {"ret_1y": 5.0},
        }
        r = check_eating_principal_1y_mk(fund)
        assert r is not None
        assert "吃本金" in r["status"]

    def test_nested_and_flat_same_verdict(self):
        """**SSOT 鐵則**:同 input(adr / tr1y)兩種 shape 必須給出同 verdict。"""
        nested = {"moneydj_raw": {"moneydj_div_yield": 7.0},
                  "metrics": {"ret_1y": 4.0}}
        flat = {"moneydj_div_yield": 7.0,
                "metrics": {"ret_1y": 4.0}}
        r_n = check_eating_principal_1y_mk(nested)
        r_f = check_eating_principal_1y_mk(flat)
        assert r_n["status"] == r_f["status"], \
            f"兩 shape SSOT 不一致! nested={r_n['status']} flat={r_f['status']}"
        assert r_n["alert_level"] == r_f["alert_level"]

    def test_metrics_fallback_when_moneydj_missing(self):
        """moneydj_div_yield 缺 → metrics.annual_div_rate fallback。"""
        fund = {"metrics": {"ret_1y": 10.0, "annual_div_rate": 5.0}}
        r = check_eating_principal_1y_mk(fund)
        assert r is not None
        assert "健康" in r["status"], f"含息 10 > 配息 5 → 應健康,實際 {r['status']}"

    def test_moneydj_takes_precedence_over_metrics(self):
        """moneydj_div_yield 有值 → 不應走 metrics.annual_div_rate fallback。

        v19.175 3 色制改用 gap_pct 門檻:
        - 用 mj=8 → tr=5, gap=8-5=3pp > 2pp → 🔴 吃本金
        - 若誤用 metrics=3 → tr=5, gap=-2pp → 🟢 健康
        測試確保走 mj 主源(若答案是吃本金 → 證明用對 mj)。
        """
        fund = {
            "moneydj_raw": {"moneydj_div_yield": 8.0},
            "metrics": {"ret_1y": 5.0, "annual_div_rate": 3.0},  # metrics=3 是誤導陷阱
        }
        r = check_eating_principal_1y_mk(fund)
        assert r is not None
        assert "吃本金" in r["status"] or r["alert_level"] == "red", (
            f"應以 moneydj_div_yield=8 為準(gap=3pp 紅),"
            f"若走 metrics=3 會誤判健康。實際 {r}"
        )
        assert r["gap_pct"] == 3.0, (
            f"v19.175 應提供 gap_pct 欄位 = 8-5 = 3.0,實際 {r.get('gap_pct')}"
        )

    def test_data_missing_returns_none(self):
        """ret_1y 缺或 adr 缺 → 回 None(§1 不偽造)。"""
        assert check_eating_principal_1y_mk({}) is None
        assert check_eating_principal_1y_mk(
            {"moneydj_div_yield": 5.0}  # 缺 ret_1y
        ) is None
        assert check_eating_principal_1y_mk(
            {"metrics": {"ret_1y": 5.0}}  # 缺 adr
        ) is None

    def test_zero_or_negative_div_yield_returns_none(self):
        """adr ≤ 0(無配息 / 累積型基金)→ 回 None(吃本金概念不適用)。"""
        assert check_eating_principal_1y_mk(
            {"moneydj_div_yield": 0.0, "metrics": {"ret_1y": 5.0}}
        ) is None
        assert check_eating_principal_1y_mk(
            {"moneydj_div_yield": -1.0, "metrics": {"ret_1y": 5.0}}
        ) is None

    def test_uses_canonical_classify_eating_principal(self):
        """SSOT 守:本 helper 結論必須與 canonical classify_eating_principal 一致。
        防有人未來繞過 canonical 自己另算。"""
        fund = {"moneydj_div_yield": 7.0, "metrics": {"ret_1y": 4.0}}
        r = check_eating_principal_1y_mk(fund)
        core = classify_eating_principal(4.0, 7.0)
        assert core.is_eating is True
        assert r["eating_principal"] is True  # dividend_safety field


# ──────────────────────────────────────────────────────────
# 2. check_333_principle — MK 老師 3-3-3 長線輔助
# ──────────────────────────────────────────────────────────
class TestCheck333Principle:
    def test_pass_when_years_ge_3_and_return_gt_7(self):
        r = check_333_principle(years_since_inception=5.2, ann_return_3y_pct=8.5)
        assert r["passed"] is True
        assert r["years_ok"] is True
        assert r["return_ok"] is True

    def test_fail_short_history(self):
        r = check_333_principle(years_since_inception=2.5, ann_return_3y_pct=10.0)
        assert r["passed"] is False
        assert r["years_ok"] is False
        assert "成立" in r["message"]

    def test_fail_low_return(self):
        r = check_333_principle(years_since_inception=5.0, ann_return_3y_pct=6.5)
        assert r["passed"] is False
        assert r["return_ok"] is False
        assert "≤ 7" in r["message"] or "7%" in r["message"]

    def test_boundary_exactly_3_years_and_7pct(self):
        """邊界:成立剛好 3 年(通過)、年化剛好 7%(不通過,需 > 7)。"""
        r = check_333_principle(years_since_inception=3.0, ann_return_3y_pct=7.0)
        # years_ok = True (>= 3), return_ok = False (not > 7)
        assert r["years_ok"] is True
        assert r["return_ok"] is False
        assert r["passed"] is False

    def test_data_missing_both(self):
        r = check_333_principle(None, None)
        assert r["passed"] is None
        assert "資料不足" in r["message"]


# ──────────────────────────────────────────────────────────
# 3. 跨 caller SSOT 守衛:fund_checkup 路徑 + tab_fund_grp_health 路徑
#    同 fund dict input → 同 verdict
# ──────────────────────────────────────────────────────────
class TestCrossCallerSSOT:
    def test_tab_fund_grp_health_uses_same_helper_as_fund_checkup(self):
        """v19.148 後,兩 caller 都應呼叫 check_eating_principal_1y_mk。
        防有人靜默走回頭路自己算(SSOT 違憲)。"""
        # tab_fund_grp_health.py 程式碼掃描
        with open("ui/tab_fund_grp_health.py",
                  encoding="utf-8") as _f:
            _src_grp = _f.read()
        assert "check_eating_principal_1y_mk" in _src_grp, (
            "tab_fund_grp_health 必須走 check_eating_principal_1y_mk SSOT 入口"
        )
        # 不該再用 calc_health_from_manual (v19.70 J2 舊路徑)做 verdict
        # (calc_health_from_manual 本身未刪除,因為其他單檔 fallback 場景仍用)
        # 只守 tab_fund_grp_health.py:_process_one_fund 不再 import 它做 verdict
        assert "from services.fund_service import calc_health_from_manual" not in _src_grp, (
            "tab_fund_grp_health 不應再 import calc_health_from_manual"
            "(v19.148 已移除自算 1Y 路徑改走 MK SSOT)"
        )

    def test_old_misleading_column_removed(self):
        """v19.148:移除「燈號（全期 🧮）」這個誤導 column(語意非 1Y,但顯示風格
        讓 user 以為與 1Y 燈號平行)。"""
        with open("ui/tab_fund_grp_health.py",
                  encoding="utf-8") as _f:
            _src_grp = _f.read()
        # 該 column 已不再寫入 row dict
        # (註解內可能還會提到,但不該是 dict key)
        # 找精確 pattern:'"燈號（全期 🧮）":' (字典 key 形)
        assert '"燈號（全期 🧮）":' not in _src_grp, (
            "燈號（全期 🧮）column 應已從 row dict 移除"
        )
        # 新 column 存在
        assert '"吃本金燈號 (1Y · MK)":' in _src_grp, (
            "新 MK SSOT column「吃本金燈號 (1Y · MK)」應存在"
        )
