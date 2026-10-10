# -*- coding: utf-8 -*-
"""② 組合健診大表與 ③ 單檔研究訊號卡的名稱訊號止血（客戶 2026-10-10 裁示 V5／Q5）。

`ui/helpers/macro/helpers.py::mk_fund_signal` 以基金名稱關鍵字判核心／衛星；兩邊都沒命中的
「混合型」原本走 `RECS[phase][False]`，等於拿衛星專屬的動作句。本批只做最小 guard：
無法確認核心或衛星 → 操作訊號「—」、理由空白；名稱已命中者不受影響。
"""
from __future__ import annotations


# ══════════════════════════════════════════════════════════════════
# H. ② ③ 名稱訊號：無法確認核心或衛星 → 不給核心／衛星專屬動作句（V5）
# ══════════════════════════════════════════════════════════════════
def test_q5_mixed_fund_gets_no_core_or_satellite_action():
    """突變：拿掉 `mk_fund_signal` 的混合型 guard → 高峰期混合型拿到「🔴 賣出獲利」，本條紅。"""
    from ui.helpers.macro.helpers import mk_fund_signal
    for _ph in ("復甦", "擴張", "高峰", "衰退"):
        sig = mk_fund_signal({"基金名稱": "某某全球股票基金"}, _ph, 5.0)
        assert sig["asset_class"] == "混合型 ⚖️"
        assert sig["label"] == "—" and sig["reason"] == "", (_ph, sig)


def test_q5_guard_does_not_touch_name_matched_funds():
    from ui.helpers.macro.helpers import mk_fund_signal
    assert mk_fund_signal({"基金名稱": "全球科技基金"}, "高峰", 5.0)["label"] == "🔴 賣出獲利"
    assert mk_fund_signal({"基金名稱": "收益債券基金"}, "高峰", 5.0)["label"] == "🟡 持有減碼"
