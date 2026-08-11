"""L2 換股通知決策 + 文字(services/switch_notify,v19.432)。

守:actionable 判定(換股/賣現金/表現差觸發、WARN/HOLD 不觸發)、訊息含關鍵資訊、
無建議時 should_notify=False、明細截斷、LINE 長度上限。
"""
from __future__ import annotations

from services.switch_advisor import HOLD, INSUFFICIENT, SELL_CASH, SWITCH, WARN
from services.switch_notify import build_notification


def _adv(action=HOLD, name="基金A", code="AAA", under=False, reasons=None,
         excess=None, switch_to=None, underperf_cand=None):
    return {
        "code": code, "name": name, "type": "震盪", "type_method": "er", "er": 0.1,
        "action": action, "action_zh": {"switch": "🔄 建議換股", "sell_to_cash": "🔴 建議賣出轉現金",
                                         "warn": "🟡 警示留意", "hold": "➖ 續抱",
                                         "insufficient": "⬜ 資料不足"}[action],
        "reason": "", "switch_to": switch_to, "underperf_candidate": underperf_cand,
        "underperformance": {"is_underperforming": under, "reasons": reasons or [],
                             "excess_pct": excess, "benchmark_used": "TWII"},
        "signals": {},
    }


def _result(advices, **summary):
    _s = {"n_holdings": len(advices), "n_switch": 0, "n_sell_cash": 0, "n_warn": 0,
          "n_hold": 0, "n_insufficient": 0, "n_underperforming": 0}
    _s.update(summary)
    return {"advices": advices, "summary": _s, "caveat": "..."}


def test_no_actionable_should_not_notify():
    r = build_notification(_result([_adv(HOLD), _adv(WARN)]))
    assert r["should_notify"] is False and r["n_actionable"] == 0
    assert "本週無需換股" in r["message"]


def test_switch_is_actionable():
    cand = {"code": "BBB", "name": "替代B", "type": "震盪", "buy_sigma": -1.8, "potential_pct": 10.0}
    r = build_notification(_result([_adv(SWITCH, name="持股A", switch_to=cand)], n_switch=1))
    assert r["should_notify"] is True and r["n_actionable"] == 1
    assert "持股A" in r["message"] and "替代B" in r["message"] and "σ-1.8" in r["message"]


def test_sell_cash_is_actionable():
    r = build_notification(_result([_adv(SELL_CASH, name="成長G")], n_sell_cash=1))
    assert r["should_notify"] is True and "成長G" in r["message"]


def test_underperform_with_candidate_actionable():
    cand = {"code": "CCC", "name": "替代C", "buy_sigma": -2.0}
    r = build_notification(_result(
        [_adv(HOLD, name="落後D", under=True, reasons=["跑輸大盤"], excess=-8.0, underperf_cand=cand)],
        n_underperforming=1))
    assert r["should_notify"] is True
    assert "落後D" in r["message"] and "跑輸大盤" in r["message"]
    assert "vs 大盤 -8.0pp" in r["message"] and "替代C" in r["message"]


def test_underperform_without_candidate_is_honest():
    r = build_notification(_result(
        [_adv(HOLD, name="落後E", under=True, reasons=["絕對虧損"], underperf_cand=None)],
        n_underperforming=1))
    assert r["should_notify"] is True
    assert "無合適替代標的" in r["message"]


def test_warn_and_hold_not_actionable():
    r = build_notification(_result([_adv(WARN), _adv(HOLD), _adv(INSUFFICIENT)]))
    assert r["should_notify"] is False


def test_actionable_codes_reported():
    cand = {"code": "B", "name": "b", "buy_sigma": -1.5}
    r = build_notification(_result([_adv(SWITCH, code="X1", switch_to=cand), _adv(HOLD, code="X2")]))
    assert r["actionable_codes"] == ["X1"]


def test_detail_rows_truncated_and_within_line_limit():
    cand = {"code": "B", "name": "替代", "buy_sigma": -1.5}
    advs = [_adv(SWITCH, code=f"C{i}", name=f"基金{i}", switch_to=cand) for i in range(30)]
    r = build_notification(_result(advs, n_switch=30))
    assert r["should_notify"] is True and r["n_actionable"] == 30
    assert "另有" in r["message"]                      # 收斂提示
    assert len(r["message"]) <= 4800                    # LINE 長度上限
