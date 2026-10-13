"""ui_v2（B 線）跨頁共用的門檻常數 —— 純常數，不 import 任何東西。

為什麼住在這裡（不是 `shared/signal_thresholds.py`）：
`tests/ui_v2/test_ui_v2_live_import_guard.py` 第 (5) 條規定 `ui_v2` 內一律不得 import 舊樹
（`shared` 在內），唯一的例外是 `source.py` 碰 `services.v2_tables`；而各頁的 `live.py` 是純函式模組，
既不能碰 `shared` 也不能碰 `services`。各頁又刻意不互相 import（見各頁 `__init__.py`）。
所以兩頁要共用同一個數字，只能放在 `ui_v2` 底下、不屬於任何一頁的這個檔。
"""

# 淨值「資料未備」門檻（日曆日）。
# N ＝ 觀測日（台灣今天的日期）減該檔最後一筆 `nav_date`；**N 大於這個數**才算超過（等於 10 不算）。
# 出處：
#   - 客戶 2026-10-02 裁示（`docs/wireframes/draft_hld_live.html` §G 第 1a 題），客戶要求註明的原話：
#     「門檻 10 天，非 44 規定，是本輪依長假實況訂的」；理由：7 天遇到春節等長假會把所有基金誤標。
#   - 客戶 2026-10-13 裁示：淨值日距觀測日 > 10 天 → 視為「資料未備」；10 天要有單一、明確的共用定義，
#     不要在不同 UI／service 散落不同的寫死數字；缺值仍是缺值，不得以 0 代替、不得猜淨值、不得為長假發明新 fallback。
# 使用者（兩頁各自保留本地別名，值一律從這裡來）：
#   - `ui_v2/hld/live.py::NAV_FRESH_DAYS_YELLOW`：持倉頁 ~~超過 → 黃燈、照用（行為照 2026-10-02 裁示，未改）~~
#     → 客戶 2026-10-13 裁示（狀態更新，不是漏刪）：超過 → 該檔淨值「資料未備」，不再用過期淨值算任何一個數，
#     徽章為中性灰「⬜ 資料未備」（不是投資黃燈）；與資產配置頁同一個語意；
#   - `ui_v2/alo/live.py::NAV_MAX_AGE_DAYS`：資產配置頁超過 → 市值基準下不納入（畫「資料未備」）。
# ⛔ 與舊介面 `shared/signal_thresholds.py::MJ_FRESH_DAYS_GREEN／MJ_FRESH_DAYS_YELLOW`（2／7）是**不同的兩套**：
#    那兩個管的是舊 UI 與 L2 的 `stale`，算法也不同；舊 UI 待退役，本常數不沿用、也不去改它們。
NAV_NOT_READY_DAYS = 10
