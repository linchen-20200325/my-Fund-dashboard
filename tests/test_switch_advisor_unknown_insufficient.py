"""2026-10-23 客戶裁示(BL-0426 回修,選項 1):震盪型基金「基金位置無法判定」→ INSUFFICIENT。

`services/switch_advisor.py::advise_holding` 在震盪型、σ rank 為「—」/ 缺值(classify_base →
unknown)時,~~回 HOLD、理由「基期未知(未貼近高點)→ 續抱」~~ —— 那句把「不知道」說成
「未貼近高點」。改走既有 INSUFFICIENT;不新增狀態、門檻、公式。high / low / mid 分支不動
(迴歸:輸出與 f2539a7d 逐字相同,下方 `_BASE_OUTPUTS` 由該 commit 的 switch_advisor.py 產生)。
"""
from __future__ import annotations

import json

import pytest

from services.switch_advisor import HOLD, INSUFFICIENT, advise_holding


def _held(sr, **kw):
    return {"code": "H1", "name": "Held", "基金類別": "債券型", "σ rank": sr,
            "type_override": "震盪", "currency": "USD", "nav_series": None, **kw}


_POOL = [{"code": "P1", "name": "Pool", "基金類別": "股票型", "σ rank": "-2.10σ", "4D Grade": "A",
          "吃本金燈號": "🟢 健康", "操盤評分": 80, "距 HWM %": "-12.00%", "currency": "USD",
          "type_override": "震盪", "nav_series": None}]

_CASES = {
    "high_nocand": (_held("-0.20σ"), [], "neutral"),
    "high_cand": (_held("-0.20σ"), _POOL, "weak_twd"),
    "low": (_held("-2.00σ"), _POOL, "strong_twd"),
    "mid": (_held("-1.00σ"), _POOL, None),
}

#: f2539a7d 的 `advise_holding` 對上列 4 個情境的完整輸出(JSON,sort_keys)。
_BASE_OUTPUTS = json.loads(r"""{
 "high_cand": {
  "action": "switch",
  "action_zh": "🔄 建議換股",
  "code": "H1",
  "er": null,
  "name": "Held",
  "reason": "震盪型 + 貼近高基期 → 換入池中低基期健康標的「Pool」(賺回歸)。淨值高基期 + 台幣弱(換回台幣划算)→ 雙重划算,出場條件較佳。",
  "signals": {
   "breakdown": null,
   "fx_label": "weak_twd",
   "macro_composite": 0.0,
   "nav_level": "high",
   "sigma_rank": null
  },
  "switch_to": {
   "buy_sigma": -2.1,
   "ccy": "USD",
   "code": "P1",
   "cross_ccy": false,
   "name": "Pool",
   "potential_pct": 13.6,
   "type": "震盪"
  },
  "type": "震盪",
  "type_method": "override",
  "underperf_candidate": null,
  "underperformance": {
   "benchmark_used": null,
   "excess_pct": null,
   "full_period": false,
   "is_underperforming": false,
   "lags_benchmark": false,
   "reasons": [],
   "redlight": null
  }
 },
 "high_nocand": {
  "action": "hold",
  "action_zh": "➖ 續抱",
  "code": "H1",
  "er": null,
  "name": "Held",
  "reason": "震盪型 + 高基期,但池中無『低基期且健康』標的可換 → 建議持有或轉現金(不硬湊,§1)。",
  "signals": {
   "breakdown": null,
   "fx_label": "neutral",
   "macro_composite": 0.0,
   "nav_level": "high",
   "sigma_rank": null
  },
  "switch_to": null,
  "type": "震盪",
  "type_method": "override",
  "underperf_candidate": null,
  "underperformance": {
   "benchmark_used": null,
   "excess_pct": null,
   "full_period": false,
   "is_underperforming": false,
   "lags_benchmark": false,
   "reasons": [],
   "redlight": null
  }
 },
 "low": {
  "action": "hold",
  "action_zh": "➖ 續抱",
  "code": "H1",
  "er": null,
  "name": "Held",
  "reason": "震盪型 + 低基期(未貼近高點)→ 續抱,等接近高基期再評估換出。",
  "signals": {
   "breakdown": null,
   "fx_label": "strong_twd",
   "macro_composite": 0.0,
   "nav_level": "low",
   "sigma_rank": null
  },
  "switch_to": null,
  "type": "震盪",
  "type_method": "override",
  "underperf_candidate": null,
  "underperformance": {
   "benchmark_used": null,
   "excess_pct": null,
   "full_period": false,
   "is_underperforming": false,
   "lags_benchmark": false,
   "reasons": [],
   "redlight": null
  }
 },
 "mid": {
  "action": "hold",
  "action_zh": "➖ 續抱",
  "code": "H1",
  "er": null,
  "name": "Held",
  "reason": "震盪型 + 中性(未貼近高點)→ 續抱,等接近高基期再評估換出。",
  "signals": {
   "breakdown": null,
   "fx_label": null,
   "macro_composite": 0.0,
   "nav_level": "mid",
   "sigma_rank": null
  },
  "switch_to": null,
  "type": "震盪",
  "type_method": "override",
  "underperf_candidate": null,
  "underperformance": {
   "benchmark_used": null,
   "excess_pct": null,
   "full_period": false,
   "is_underperforming": false,
   "lags_benchmark": false,
   "reasons": [],
   "redlight": null
  }
 }
}""")


@pytest.mark.parametrize("name", sorted(_CASES))
def test_high_low_mid_unchanged_vs_f2539a7d(name):
    h, pool, fx = _CASES[name]
    got = advise_holding(h, pool, fx_label=fx, macro_composite=0.0)
    # DG-6（DEC-2026-10-24-12）：advise_holding 新增 `underperf_suppressed` 鍵（預設 False，
    # 只有資料不足列的表現差換股建議被抑制時才為 True）。本快照的 high/low/mid 列都不是資料不足、
    # 也沒有表現差 → 必為 False；把新鍵拿掉後，其餘輸出仍須與 f2539a7d 快照逐鍵相同。
    got = dict(got)
    assert got.pop("underperf_suppressed") is False
    assert json.loads(json.dumps(got, ensure_ascii=False, sort_keys=True, default=str)) \
        == _BASE_OUTPUTS[name]


@pytest.mark.parametrize("sr", ["—", None, "⬜", "nan"])
def test_range_unknown_is_insufficient_not_hold(sr):
    a = advise_holding(_held(sr), _POOL, fx_label="neutral", macro_composite=0.0)
    assert a["action"] == INSUFFICIENT and a["action"] != HOLD
    assert a["signals"]["nav_level"] == "unknown"
    assert "未貼近高點" not in a["reason"] and "續抱" not in a["reason"]
    assert "基金位置無法判定" in a["reason"] and a["switch_to"] is None


def test_range_unknown_reason_carries_white_reason_when_available():
    why = "⬜ 無法判定／不適用（配息基金但近一年窗口內沒有任何配息被還原）"
    a = advise_holding(_held("—", **{"HWM 位階": why}), [], fx_label=None, macro_composite=0.0)
    assert a["action"] == INSUFFICIENT and why in a["reason"]


def test_switch_notify_insufficient_not_actionable_unchanged():
    """LINE 週報沿用既有處理:INSUFFICIENT 不觸發通知(未新增推送內容)。"""
    from services.switch_notify import _is_actionable
    a = advise_holding(_held("—"), _POOL, fx_label="neutral", macro_composite=0.0)
    assert _is_actionable(a) is False
