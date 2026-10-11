# -*- coding: utf-8 -*-
"""② 組合健診大表與 ③ 單檔研究訊號卡的名稱訊號（客戶 2026-10-10 裁示 V5／Q5；2026-10-11 客戶再裁示停用）。

沿革（兩邊並陳，不是漏刪）：
- 2026-10-10（V5／Q5 止血）：`ui/helpers/macro/helpers.py::mk_fund_signal` 以基金名稱關鍵字判核心／衛星，
  兩邊都沒命中的「混合型」原本走 `RECS[phase][False]`、等於拿衛星專屬的動作句 ⇒ 只擋「混合型」這一條，
  名稱已命中者**維持**原行為。那一版的測試把「全球科技基金 → 賣出獲利」「收益債券基金 → 持有減碼」
  鎖成預期。
- 2026-10-11（客戶裁示）：名稱不是級別的可追溯來源，**整條名稱推定路徑停用**
  （含原本被保留的「名稱已命中」那一半）。舊測試所鎖的行為即是被停用的行為，故改為斷言「已停用」。
  完整守衛見 `tests/test_tier_q6_asset_attr_retired.py`。
"""
from __future__ import annotations


# ══════════════════════════════════════════════════════════════════
# H. ② ③ 名稱訊號：不論名稱像什麼，都不給核心／衛星專屬動作句
# ══════════════════════════════════════════════════════════════════
def test_q5_mixed_fund_gets_no_core_or_satellite_action():
    """判不出核心或衛星的名稱（舊「混合型」）→ 基金屬性「—」、操作訊號「—」、理由空白。"""
    from ui.helpers.macro.helpers import mk_fund_signal
    for _ph in ("復甦", "擴張", "高峰", "衰退"):
        sig = mk_fund_signal({"基金名稱": "某某全球股票基金"}, _ph, 5.0)
        assert sig["asset_class"] == "—", (_ph, sig)
        assert sig["label"] == "—" and sig["reason"] == "", (_ph, sig)


def test_q5_name_matched_funds_are_no_longer_given_actions():
    """舊測試把「全球科技基金 → 🔴 賣出獲利」「收益債券基金 → 🟡 持有減碼」鎖成預期；
    這正是 2026-10-11 被停用的名稱推定。突變：把名稱關鍵字判斷貼回 → 本條紅。"""
    from ui.helpers.macro.helpers import mk_fund_signal
    for _name in ("全球科技基金", "收益債券基金"):
        sig = mk_fund_signal({"基金名稱": _name}, "高峰", 5.0)
        assert sig["label"] == "—", (_name, sig)
        assert sig["asset_class"] == "—", (_name, sig)
        assert sig["sig_type"] == "none" and sig["reason"] == "", (_name, sig)
