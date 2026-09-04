"""shared/session_keys.py — 跨層共用的 `st.session_state` 鍵名 SSOT(L0,純常數)。

## 為什麼需要一個 L0 模組放「兩個字串」

2026-09-04 第三輪稽核 B2:Tab ① 熱錢快覽卡的兩個 session 鍵名當時**逐字寫在三個
地方** —— `ui/tab1_macro.py` 的常數、`ui/tab5_data_guard.py` 的字面值、以及測試裡
**第三份**字面值;那條「手動更新會作廢卡片 stash」的守衛比對的是 tab5 的字面值與
**測試自己那一份**,從頭到尾沒有碰過生產端的常數 —— 改壞 `ui/tab1_macro.py` 的常數
名,測試照樣全綠。

同一輪的 A5 又發現這兩個鍵**必須**同時被三個刷新入口清掉,而那三個入口分屬三層:

    `infra/cache.py::global_refresh_all`            L0 Infra
    `services/macro/__init__.py::clear_tab1_macro_caches`  L2 Service
    `ui/tab5_data_guard.py` 的「📥 立即更新」按鈕      L3 UI

L0 / L2 **不得** import L3(CLAUDE.md §8.2 硬規則:跨層上行 import 違憲),所以
「把 `ui/tab1_macro.py` 當 SSOT、其餘 import 它」在 L0/L2 那兩處**物理上做不到**。
唯一能同時被三層讀到的位置就是 L0 `shared/`(其職責定義即「常數 / TTL / 色票,無 IO
純常數」)。故本模組成立 —— 它不是「為了兩個字串而做的抽象」,而是分層規則直接推出
來的唯一合法落點。

⚠️ 新增鍵時請一併確認它有沒有被**所有**該作廢它的刷新入口涵蓋(A5 的教訓:F6 那一輪
只接了三個入口裡的一個,使用者按 Tab ① 的「強制重抓」或側欄「全域刷新」之後,這張卡
仍然抱著上一輪的失敗結果不放)。
"""
from __future__ import annotations

#: Tab ① 熱錢快覽卡「本 session 已嘗試過取數」旗標(成敗皆標記)。
#: 語意見 `ui/tab1_macro.py::_render_top_card_grid` 卡 4 的 F6 段落。
HM_CARD_TRIED_KEY: str = "_hm_card_fetch_tried"

#: 同卡的取數結果 stash —— `(flow_df, fx_df, ferr, xerr)` 四元組。
HM_CARD_STASH_KEY: str = "_hm_card_frames"

#: 上面兩個鍵的元組,給「把它們全部清掉」的刷新入口直接展開用。
#: **刷新入口請引用本元組,不要逐個列名** —— 逐個列名正是 A5 漏掉兩個入口的形態。
HM_CARD_SESSION_KEYS: tuple[str, ...] = (HM_CARD_TRIED_KEY, HM_CARD_STASH_KEY)
