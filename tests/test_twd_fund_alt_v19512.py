"""v19.512:台幣基金安全扣款候選 twd_fund_alt(services.policy_fee_optimizer.optimize_policy_fee)。

user 2026-08-22「台幣基金也納入扣款候選」。投資型保單管理費多為贖回單位內扣;台幣基金
fx_factor 恆 1.0 → 免匯率風險,是「不動用外部現金也能避開匯兌」的保單內扣款替代。

三位 AI 專家會審後的 §1 誠實護欄(本測守之):
  - 只從足額(is_sufficient)+ 無 error 的台幣基金挑;物理上扣不動的(市值<管理費)排除。
  - 排除 is_cost_estimated:成本未知 → score 是推定 1.0,不可拿假分數當划算訊號。
  - 排除 DANGER(score < 0.90):賣它 = 低點實現虧損,不當「安全」賣。
  - **依 loss_pct 升序**挑「對部位擾動最小」者,**非**依 score(避免偏好賣獲利最大/課稅最不利檔)。
  - L2 無條件計算(不綁 scenario)→ scenario A 也帶 twd_fund_alt。None = 無合格台幣基金。
"""
import json

import pytest

from services.policy_fee_optimizer import (
    REC_CASH,
    REC_FUND,
    SCORE_LOW,
    optimize_policy_fee,
)


def _fund(fid, ccy, nav, cost_nav, units, cost_rate=None, name=None):
    """組引擎輸入 fund dict。TWD 免 cost_rate(引擎短路 1.0)。cost_nav=None → 成本未知。"""
    d = {"id": fid, "name": name or fid, "currency": ccy,
         "current_nav": nav, "units": units, "cost_nav": cost_nav}
    if cost_rate is not None:
        d["cost_rate"] = cost_rate
    return d


# ── T1:無台幣基金 → twd_fund_alt None ───────────────────────────────────────
def test_no_twd_fund_alt_is_none():
    # 單一美元基金,score 落 WARNING(<1.15)→ scenario B;無台幣基金 → alt None。
    usd = _fund("US_A", "USD", nav=20.0, cost_nav=19.0, units=1000.0, cost_rate=30.0)
    out = optimize_policy_fee(1000.0, {"USD": 30.0}, [usd])
    assert out["recommendation"] == REC_CASH and out["scenario"] == "B"
    assert out["twd_fund_alt"] is None


# ── T2:單一「成本之上」台幣基金(1.0<score<1.15)→ 被挑,幣別/分數/損耗正確 ───────
def test_single_above_cost_twd_picked():
    twd = _fund("TW_A", "TWD", nav=11.0, cost_nav=10.0, units=10000.0, name="台幣穩健")
    out = optimize_policy_fee(1000.0, {}, [twd])
    assert out["recommendation"] == REC_CASH and out["scenario"] == "B"
    alt = out["twd_fund_alt"]
    assert alt is not None
    assert alt["id"] == "TW_A" and alt["currency"] == "TWD"
    assert abs(alt["score"] - 1.1) < 1e-6           # 11/10
    # loss_pct = fee/(nav*units)*100 = 1000/(11*10000)*100
    assert abs(alt["loss_pct"] - (1000.0 / 110000.0 * 100.0)) < 1e-3


# ── T3(核心):多檔台幣基金 → 挑 loss_pct 最低者,**非** score 最高者 ──────────────
def test_pick_lowest_loss_pct_not_highest_score():
    # A:高分小倉(score 1.14,但市值僅 1140 → loss_pct ~87.7%)
    a = _fund("HI_SCORE", "TWD", nav=11.4, cost_nav=10.0, units=100.0, name="高分小倉")
    # B:低分大倉(score 1.05,市值 105000 → loss_pct ~0.95%)
    b = _fund("BIG_POS", "TWD", nav=10.5, cost_nav=10.0, units=10000.0, name="低分大倉")
    out = optimize_policy_fee(1000.0, {}, [a, b])
    assert out["scenario"] == "B"                   # 兩檔皆 <1.15
    alt = out["twd_fund_alt"]
    # 若依 score 挑會選 A(1.14);依 loss_pct 挑選 B(擾動最小)——本測釘住 loss_pct 準則。
    assert alt["id"] == "BIG_POS" and alt["name"] == "低分大倉"
    assert abs(alt["score"] - 1.05) < 1e-6
    assert alt["loss_pct"] < 1.0                    # ~0.95%


# ── T4:唯一台幣基金在 DANGER(score<0.90)→ 排除 → None(F1)─────────────────
def test_danger_twd_excluded():
    twd = _fund("TW_LOW", "TWD", nav=8.0, cost_nav=10.0, units=10000.0)   # score 0.8
    out = optimize_policy_fee(1000.0, {}, [twd])
    assert out["scenario"] == "B"
    assert 0.8 < SCORE_LOW                          # 前提:0.8 確實 <0.90
    assert out["twd_fund_alt"] is None


# ── T5:成本未知台幣基金(cost_nav None)→ 排除,不拿推定 1.0 排名(F2)─────────────
def test_cost_estimated_twd_excluded():
    twd = _fund("TW_EST", "TWD", nav=10.0, cost_nav=None, units=10000.0)
    out = optimize_policy_fee(1000.0, {}, [twd])
    # 引擎:成本未知 → is_cost_estimated True、score 推定 1.0,但 twd_fund_alt 須排除。
    est = next(f for f in out["funds"] if f["id"] == "TW_EST")
    assert est["is_cost_estimated"] is True and est["error"] is None
    assert out["twd_fund_alt"] is None


# ── T6:市值不足(M<F)台幣基金 → 排除(F5)──────────────────────────────────
def test_insufficient_twd_excluded():
    twd = _fund("TW_TINY", "TWD", nav=10.0, cost_nav=9.0, units=50.0)     # M=500 < fee 1000
    out = optimize_policy_fee(1000.0, {}, [twd])
    assert out["scenario"] == "C" and out["eligible_count"] == 0
    assert out["twd_fund_alt"] is None


# ── T7:略低於成本 WARNING(0.90<=score<1.0)→ 納入,且 score<1.0 供 UI 標小幅虧損 ──
def test_below_cost_warning_included_flags_loss():
    twd = _fund("TW_DIP", "TWD", nav=9.5, cost_nav=10.0, units=10000.0)   # score 0.95
    out = optimize_policy_fee(1000.0, {}, [twd])
    alt = out["twd_fund_alt"]
    assert alt is not None and alt["id"] == "TW_DIP"
    assert SCORE_LOW <= alt["score"] < 1.0          # 0.90 <= 0.95 < 1.0(UI 須標實現小幅虧損)


# ── T8:scenario A(美元高檔)仍計算 twd_fund_alt(L2 不綁 scenario)────────────────
def test_alt_computed_even_in_scenario_a():
    usd = _fund("US_HI", "USD", nav=25.0, cost_nav=20.0, units=1000.0, cost_rate=30.0)  # score 1.375
    twd = _fund("TW_OK", "TWD", nav=10.5, cost_nav=10.0, units=10000.0)                 # score 1.05
    out = optimize_policy_fee(1000.0, {"USD": 33.0}, [usd, twd])
    assert out["recommendation"] == REC_FUND and out["scenario"] == "A"
    assert out["top_pick_id"] == "US_HI"
    alt = out["twd_fund_alt"]
    assert alt is not None and alt["id"] == "TW_OK" and alt["currency"] == "TWD"


# ── T9:輸出 JSON-safe(twd_fund_alt 為 dict/None,可序列化)────────────────────
def test_output_json_safe():
    twd = _fund("TW_A", "TWD", nav=11.0, cost_nav=10.0, units=10000.0)
    out = optimize_policy_fee(1000.0, {}, [twd])
    json.dumps(out)                                 # 不炸 = 通過


# ── T10:twd_fund_alt 形狀(關鍵欄位齊備供 L3 渲染 + 誠實揭露)──────────────────
def test_alt_shape_has_render_keys():
    twd = _fund("TW_A", "TWD", nav=11.0, cost_nav=10.0, units=10000.0, name="台幣穩健")
    out = optimize_policy_fee(1000.0, {}, [twd])
    alt = out["twd_fund_alt"]
    for k in ("id", "name", "currency", "loss_pct", "score", "return_factor",
              "badge_level", "is_cost_estimated"):
        assert k in alt, f"twd_fund_alt 缺欄位 {k}"
    assert alt["currency"] == "TWD" and alt["is_cost_estimated"] is False


# ── T11:外幣基金(USD)在成本之上但非高檔,不會被當台幣候選(只認 TWD)─────────────
def test_usd_not_treated_as_twd_alt():
    usd = _fund("US_MID", "USD", nav=21.0, cost_nav=20.0, units=1000.0, cost_rate=30.0)  # ~1.05
    out = optimize_policy_fee(1000.0, {"USD": 30.0}, [usd])
    assert out["scenario"] == "B"                   # <1.15
    assert out["twd_fund_alt"] is None              # USD 非 TWD → 不入候選


# ── T12:多檔台幣基金 loss_pct 相同 → id 決定性 tie-break(§5 可重現)──────────────
def test_tie_break_deterministic_by_id():
    # 兩檔市值/損耗相同(nav*units 同),score 同 → 依 id 昇序取("AAA" < "ZZZ")。
    a = _fund("ZZZ", "TWD", nav=10.0, cost_nav=10.0, units=10000.0)
    b = _fund("AAA", "TWD", nav=10.0, cost_nav=10.0, units=10000.0)
    out = optimize_policy_fee(1000.0, {}, [a, b])
    # score=1.0 → 非 DANGER、成本已知 → 皆合格;loss_pct 相同 → id 昇序 → AAA。
    assert out["twd_fund_alt"]["id"] == "AAA"


# ── T13(端到端):建構器 → 引擎 → twd_fund_alt(帳本 TWD 基金流過純建構器)──────────
def test_end_to_end_via_builder():
    from ui.helpers.portfolio.fee_deduction import build_fee_inputs

    class _Pos:
        def __init__(self, units, cost_unit, fx_avg):
            self.units, self.cost_unit, self.fx_avg = units, cost_unit, fx_avg

    class _Led:
        def __init__(self, units, cost_unit, fx_avg=1.0):
            self.position = _Pos(units, cost_unit, fx_avg)

    from models.policy import fund_pk_str
    f = {"code": "TW_0050", "name": "台股高股息", "currency": "TWD", "policy_id": "POL1"}
    pk = fund_pk_str(f)
    leds = {pk: _Led(units=10000.0, cost_unit=10.0)}          # 成本 10,現價 11 → score 1.1
    ef, exc, rates = build_fee_inputs([f], leds, lambda _f: (11.0, None))
    assert exc == [] and len(ef) == 1
    out = optimize_policy_fee(1000.0, rates, ef)
    assert out["scenario"] == "B"                              # 1.1 < 1.15
    alt = out["twd_fund_alt"]
    assert alt is not None and alt["currency"] == "TWD"
    assert abs(alt["score"] - 1.1) < 1e-6
