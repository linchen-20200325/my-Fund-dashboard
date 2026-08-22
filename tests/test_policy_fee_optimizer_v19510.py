"""v19.510:投資型保單跨幣別扣費決策引擎(services/policy_fee_optimizer.py)。

覆蓋 §2 數學模型 + §2.3 燈號 + §2.4 三情境決策 + §1/§4.1/§4.6 邊界。
§6 三個最容易出錯的輸入(NAV<=0 / 外幣缺匯率 / cost_nav<=0)皆單獨測 + property 測試。
"""
import math

import pytest

from services.policy_fee_optimizer import (
    BADGE_DANGER,
    BADGE_SUCCESS,
    BADGE_WARNING,
    REC_CASH,
    REC_FUND,
    evaluate_fund,
    optimize_policy_fee,
)


def _usd_fund(**kw):
    base = {"id": "US_A", "name": "美股基金", "currency": "USD",
            "units": 1000.0, "current_nav": 20.0, "cost_nav": 16.0, "cost_rate": 30.0}
    base.update(kw)
    return base


def _twd_fund(**kw):
    base = {"id": "TW_0050", "name": "台股高股息", "currency": "TWD",
            "units": 100.0, "current_nav": 50.0, "cost_nav": 50.0}
    base.update(kw)
    return base


# ── Golden:§2 完整算例(USD 高基期 → 情境 A)──────────────────────────
def test_golden_usd_high_base_scenario_a():
    out = optimize_policy_fee(3000.0, {"USD": 33.0, "TWD": 1.0}, [_usd_fund(), _twd_fund()])
    assert out["recommendation"] == REC_FUND and out["scenario"] == "A"
    assert out["top_pick_id"] == "US_A"
    # 排序後第一檔 = USD
    top = out["funds"][0]
    assert top["id"] == "US_A"
    assert math.isclose(top["effective_rate"], 33.0)
    assert math.isclose(top["unit_value_twd"], 660.0)              # 20 × 33
    assert math.isclose(top["market_value_twd"], 660000.0)         # 1000 × 660
    assert math.isclose(top["units_deduct"], 3000.0 / 660.0, rel_tol=1e-6)
    # loss_pct 輸出四捨五入 4 dp(百分比)→ 用寬容差比對未捨值
    assert math.isclose(top["loss_pct"], (3000.0 / 660.0) / 1000.0 * 100.0, rel_tol=1e-3)
    assert math.isclose(top["score"], 1.25 * 1.1, rel_tol=1e-9)    # (20/16)×(33/30)=1.375
    assert top["badge_level"] == BADGE_SUCCESS and top["is_sufficient"] is True


# ── TWD 標的:有效匯率恆 1.0,S_i 純由 NAV 倍數決定 ──────────────────────
def test_twd_rate_forced_one_and_score_is_nav_ratio():
    e = evaluate_fund(_twd_fund(current_nav=60.0, cost_nav=50.0), {"TWD": 1.0}, 1000.0)
    assert e.effective_rate == 1.0
    assert math.isclose(e.score, 60.0 / 50.0)                      # 1.2,匯率不參與
    assert math.isclose(e.unit_value_twd, 60.0)


# ── 情境 B:所有足額標的 S_i < 1.15 → 台幣現金 ───────────────────────────
def test_scenario_b_all_below_high_uses_cash():
    funds = [_twd_fund(current_nav=52.0, cost_nav=50.0),          # 1.04 WARNING
             _usd_fund(current_nav=16.0, cost_nav=16.0, cost_rate=33.0)]  # (1.0)*(33/33)=1.0
    out = optimize_policy_fee(2000.0, {"USD": 33.0, "TWD": 1.0}, funds)
    assert out["recommendation"] == REC_CASH and out["scenario"] == "B"
    assert out["top_pick_name"] == "台股高股息"                     # 最高分但 <1.15
    assert "未達高檔停利標準" in out["annotation"]


# ── 情境 C:所有標的餘額不足 → 降級防禦台幣現金 ─────────────────────────
def test_scenario_c_all_insufficient_uses_cash():
    # fee 巨大 → M < F,全排除
    out = optimize_policy_fee(9_999_999.0, {"USD": 33.0, "TWD": 1.0}, [_usd_fund(), _twd_fund()])
    assert out["recommendation"] == REC_CASH and out["scenario"] == "C"
    assert out["top_pick_id"] is None and out["eligible_count"] == 0
    assert "餘額不足" in out["annotation"]
    # 不足額標的仍列於 funds 輸出(供 UI 揭露),但 is_sufficient=False
    assert all(f["is_sufficient"] is False for f in out["funds"])


def test_empty_funds_is_scenario_c():
    out = optimize_policy_fee(1000.0, {"USD": 33.0}, [])
    assert out["recommendation"] == REC_CASH and out["scenario"] == "C"


# ── 跨幣別公平:S_i 無量綱,與基金原始單價尺度無關(§2.2 step6 設計目的)──────
def test_score_scale_invariant_to_nominal_nav():
    cheap = evaluate_fund(_twd_fund(current_nav=12.5, cost_nav=10.0), {"TWD": 1.0}, 100.0)
    pricey = evaluate_fund(_twd_fund(current_nav=1250.0, cost_nav=1000.0), {"TWD": 1.0}, 100.0)
    assert math.isclose(cheap.score, pricey.score)                # 皆 1.25,單價高低不影響


# ── §6 高風險輸入①:current_nav <= 0 → error 旗標 + 排除(§1 不矇、不炸整批)──
def test_bad_current_nav_flagged_not_fabricated():
    out = optimize_policy_fee(1000.0, {"USD": 33.0, "TWD": 1.0},
                              [_usd_fund(current_nav=0.0), _twd_fund()])
    bad = next(f for f in out["funds"] if f["id"] == "US_A")
    assert bad["error"] is not None and bad["score"] is None and bad["is_sufficient"] is False
    # 其餘檔照算 → TWD 檔仍被評估
    good = next(f for f in out["funds"] if f["id"] == "TW_0050")
    assert good["error"] is None


# ── §6 高風險輸入②:外幣標的缺該幣別即期匯率 → error(不假設匯率)───────────
def test_missing_fx_rate_flagged():
    e = evaluate_fund(_usd_fund(), {"TWD": 1.0}, 1000.0)          # 沒給 USD
    assert e.error is not None and "USD" in e.error and e.score is None


# ── §6 高風險輸入③:cost_nav <= 0 → error(除以零報酬倍數守衛)──────────────
def test_bad_cost_nav_flagged():
    e = evaluate_fund(_twd_fund(cost_nav=0.0), {"TWD": 1.0}, 1000.0)
    assert e.error is not None and e.score is None


def test_bad_units_flagged():
    e = evaluate_fund(_twd_fund(units=0.0), {"TWD": 1.0}, 1000.0)
    assert e.error is not None


# ── §1:管理費 <= 0 → raise(整份輸入無效,不猜)────────────────────────
@pytest.mark.parametrize("fee", [0.0, -100.0, "x", None])
def test_nonpositive_or_bad_fee_raises(fee):
    with pytest.raises(ValueError):
        optimize_policy_fee(fee, {"USD": 33.0}, [_usd_fund()])


# ── 成本缺省 → 報酬倍數 = 1.0(§2.1 預設)──────────────────────────────
def test_cost_defaults_give_unit_multiplier():
    f = {"id": "X", "name": "X", "currency": "USD", "units": 10.0, "current_nav": 25.0}
    e = evaluate_fund(f, {"USD": 31.0}, 100.0)                    # 無 cost_nav / cost_rate
    assert math.isclose(e.score, 1.0)                            # (25/25)×(31/31)=1.0


# ── §2.3 燈號邊界:1.15→SUCCESS、0.90→WARNING、0.8999→DANGER ──────────────
def test_classification_boundaries():
    hi = evaluate_fund(_twd_fund(current_nav=115.0, cost_nav=100.0), {"TWD": 1.0}, 10.0)
    mid = evaluate_fund(_twd_fund(current_nav=90.0, cost_nav=100.0), {"TWD": 1.0}, 10.0)
    lo = evaluate_fund(_twd_fund(current_nav=89.99, cost_nav=100.0), {"TWD": 1.0}, 10.0)
    assert hi.badge_level == BADGE_SUCCESS                        # 1.15 含左界 → 高
    assert mid.badge_level == BADGE_WARNING                       # 0.90 含左界 → 中
    assert lo.badge_level == BADGE_DANGER                         # <0.90 → 低


# ── 過濾規則:M < F → is_sufficient=False,排除 eligible 但仍列於輸出 ─────────
def test_insufficient_fund_excluded_but_listed():
    small = _twd_fund(id="TINY", name="小額", units=1.0, current_nav=50.0, cost_nav=40.0)  # M=50
    out = optimize_policy_fee(100.0, {"TWD": 1.0}, [small])       # 50 < 100
    tiny = next(f for f in out["funds"] if f["id"] == "TINY")
    assert tiny["is_sufficient"] is False and tiny["error"] is None  # 資料正常但餘額不足
    assert out["scenario"] == "C" and out["eligible_count"] == 0


# ── 排序:分數由高到低,error 檔沉底 ────────────────────────────────────
def test_sort_desc_errors_sink():
    funds = [_twd_fund(id="LOW", current_nav=80.0, cost_nav=100.0),   # 0.8
             _twd_fund(id="HIGH", current_nav=130.0, cost_nav=100.0),  # 1.3
             _usd_fund(id="ERR", current_nav=-1.0)]                    # error
    out = optimize_policy_fee(10.0, {"USD": 33.0, "TWD": 1.0}, funds)
    ids = [f["id"] for f in out["funds"]]
    assert ids[0] == "HIGH" and ids[1] == "LOW" and ids[-1] == "ERR"


# ── property:U_deduct × V ≈ F(贖回單位折台幣 = 管理費,§2.2 step4 不變量)──────
@pytest.mark.parametrize("fee,rate,nav", [(3000.0, 33.0, 20.0), (500.0, 1.0, 55.5),
                                          (12345.0, 4.1, 8.3)])
def test_invariant_deduct_value_equals_fee(fee, rate, nav):
    ccy = "TWD" if rate == 1.0 else "JPY"
    e = evaluate_fund({"id": "P", "name": "P", "currency": ccy, "units": 5000.0,
                       "current_nav": nav}, {ccy: rate}, fee)
    assert math.isclose(e.units_deduct * e.unit_value_twd, fee, rel_tol=1e-4)


# ── property:score 與 units 無關;loss_pct 隨 units 反比(units ×2 → loss_pct ÷2)──────
def test_units_scale_does_not_change_score_but_halves_loss_pct():
    a = evaluate_fund(_twd_fund(units=100.0, current_nav=60.0, cost_nav=50.0), {"TWD": 1.0}, 300.0)
    b = evaluate_fund(_twd_fund(units=200.0, current_nav=60.0, cost_nav=50.0), {"TWD": 1.0}, 300.0)
    assert math.isclose(a.score, b.score)                        # score 與單位數無關(§2.2 step6)
    assert math.isclose(b.loss_pct, a.loss_pct / 2.0, rel_tol=1e-9)   # units ×2 → 損耗% ÷2


# ── 稽核③ mutation 7(最高優先):情境觸發用**足額**最高分,非全體最高分 ────────────
def test_scenario_trigger_uses_eligible_top_not_global():
    tiny_hi = _twd_fund(id="TINY_HI", name="小高", units=1.0, current_nav=100.0, cost_nav=50.0)   # S=2.0,M=100
    big_low = _twd_fund(id="BIG_LOW", name="大低", units=10000.0, current_nav=50.0, cost_nav=50.0)  # S=1.0,M=500000
    out = optimize_policy_fee(1000.0, {"TWD": 1.0}, [tiny_hi, big_low])
    # 全體最高是 TINY_HI(2.0)但不足額;正確應看足額最高 BIG_LOW(1.0)< 1.15 → 情境 B/現金
    assert out["scenario"] == "B" and out["recommendation"] == REC_CASH
    assert out["top_pick_id"] == "BIG_LOW"
    assert "小高" in out["annotation"]                           # F1:高分不足額標的誠實點名


# ── 稽核③ mutation 6:M == F 足額邊界(含界,>= 非 >)──────────────────────────
def test_sufficiency_boundary_market_value_equals_fee():
    f = _twd_fund(id="EQ", units=100.0, current_nav=10.0, cost_nav=8.0)   # M=1000 恰等 fee,S=1.25
    out = optimize_policy_fee(1000.0, {"TWD": 1.0}, [f])
    assert out["funds"][0]["is_sufficient"] is True              # M==F → 足額(含界)
    assert out["scenario"] == "A" and out["eligible_count"] == 1


# ── 稽核③ mutation 8:TWD 標的忽略任何 cost_rate(有效/成本匯率恆 1.0)──────────
def test_twd_ignores_cost_rate_field():
    e = evaluate_fund(_twd_fund(current_nav=60.0, cost_nav=50.0, cost_rate=25.0), {"TWD": 1.0}, 300.0)
    assert math.isclose(e.score, 1.2)                           # 60/50;cost_rate=25 對 TWD 無效


# ── 稽核③ mutation 10 firm-up:負 NAV(非僅 0)也判 error(§4.6 停售/清算不可扣)──────
def test_negative_nav_flagged_as_error():
    e = evaluate_fund(_twd_fund(current_nav=-5.0), {"TWD": 1.0}, 100.0)
    assert e.error is not None and e.score is None


# ── 稽核① F2:小寫幣別 key 也解析得到匯率(字典 key 正規化)──────────────────────
def test_lowercase_currency_rate_key_resolves():
    e = evaluate_fund({"id": "A", "name": "A", "currency": "usd", "units": 1000.0,
                       "current_nav": 20.0, "cost_nav": 16.0, "cost_rate": 30.0},
                      {"usd": 33.0}, 3000.0)
    assert e.error is None and math.isclose(e.score, 1.375)


# ── 稽核① F4:evaluate_fund 直呼者,fee<=0 也 fail-loud(不只 optimize 守)──────────
@pytest.mark.parametrize("fee", [0.0, -1.0, "x"])
def test_evaluate_fund_bad_fee_raises(fee):
    with pytest.raises(ValueError):
        evaluate_fund(_twd_fund(), {"TWD": 1.0}, fee)


# ── 輸出 JSON-safe:全 dict / 原生型別(無 dataclass 殘留)──────────────────
def test_output_is_json_safe():
    import json
    out = optimize_policy_fee(1000.0, {"USD": 33.0, "TWD": 1.0}, [_usd_fund(), _twd_fund()])
    json.dumps(out)   # 不拋 = JSON-safe


# ── 護欄①(§1 金融稽核 Q2):成本缺省 → is_cost_estimated=True、badge=None(不假裝 S=1.0 是「正常」)──
def test_cost_estimated_flag_no_confident_badge():
    f = {"id": "X", "name": "X", "currency": "USD", "units": 10.0, "current_nav": 25.0}  # 無 cost_nav/cost_rate
    e = evaluate_fund(f, {"USD": 31.0}, 100.0)
    assert e.is_cost_estimated is True
    assert e.badge_level is None                      # ★ 不給綠/黃/紅燈
    assert "成本未知" in e.status_tag
    assert math.isclose(e.score, 1.0)                 # 分數仍算(spec 不動)但標記為推定
    # 有成本 → 非推定、給確定燈號(55/50=1.1 → WARNING)
    e2 = evaluate_fund(_twd_fund(current_nav=55.0, cost_nav=50.0), {"TWD": 1.0}, 100.0)
    assert e2.is_cost_estimated is False and e2.badge_level == BADGE_WARNING


# ── 護欄②(Q4):S 拆解 return_factor × fx_factor,供辨別高分來源(基金 vs 匯兌)──────
def test_score_decomposition_return_times_fx():
    e = evaluate_fund(_usd_fund(), {"USD": 33.0}, 3000.0)     # nav 20/16, rate 33/30
    assert math.isclose(e.return_factor, 20.0 / 16.0)        # 1.25 基金報酬
    assert math.isclose(e.fx_factor, 33.0 / 30.0)            # 1.1  匯兌
    assert math.isclose(e.score, e.return_factor * e.fx_factor)


def test_twd_fx_factor_is_one():
    e = evaluate_fund(_twd_fund(current_nav=60.0, cost_nav=50.0), {"TWD": 1.0}, 100.0)
    assert math.isclose(e.fx_factor, 1.0)                    # TWD 匯兌倍數恆 1.0


# ── 護欄③:輸出帶顯著免責 disclaimer(稅/費/複利未計入,非賣出建議)──────────────
def test_disclaimer_present():
    out = optimize_policy_fee(1000.0, {"USD": 33.0, "TWD": 1.0}, [_usd_fund()])
    assert "disclaimer" in out
    for kw in ("非賣出建議", "稅", "贖回", "複利", "loss_pct"):
        assert kw in out["disclaimer"]


# ── 護欄①延伸:情境 A 的 top 若成本未知 → annotation 誠實提醒高分可能來自匯兌 ──────────
def test_scenario_a_estimated_top_gets_caveat():
    # 無 cost_nav(return_factor=1.0)但 cost_rate=25、eff_rate=33 → fx=1.32 → S=1.32 → 情境 A
    f = {"id": "FX", "name": "純匯兌高分", "currency": "USD", "units": 1000.0,
         "current_nav": 20.0, "cost_rate": 25.0}
    out = optimize_policy_fee(3000.0, {"USD": 33.0}, [f])
    assert out["scenario"] == "A"
    assert out["funds"][0]["is_cost_estimated"] is True
    assert "成本未知" in out["annotation"]                    # 高分來自匯兌 → 誠實提醒
