# 客戶 2026-11-03 裁示：Primary 為 VIX 時 Secondary VIX 卡讓位（採 A）（逐字）

- **來源**：客戶 2026-11-03 在本對話中的訊息，經總管逐字轉交；執行組照抄，未見客戶對話本身。
- **性質**：正式裁示（presentation 去重規則；不改資料、來源、公式、狀態、freshness 或投資語意），並附帶兩個殘留點的處置（不擴大 scope）。
- **遮蔽**：無。本文沒有作者或老師姓名，也沒有 secret。
- **決策登記**：`docs/DECISIONS.md` `DEC-2026-11-03-06`
- **存檔日期**：2026-11-03
- **依據規則**：`PROJECT_RULES.md` 12.1 新裁示同批 GitHub 落盤、12.2 GitHub Discussion Persistence Gate。
- **三方案（執行組整理，不是客戶原文）**：

| 方案 | 內容 | 結果 |
|---|---|---|
| **A** | Primary 為 VIX 時 Secondary VIX 卡讓位、不顯示；切回其他檢視恢復；不補卡 | **客戶採用** |
| B | 不讓位，Secondary VIX 與 Primary VIX 並存（重複顯示同一序列） | 未採用 |
| C | 讓位並補入其他卡以維持 Secondary 張數 | 未採用 |

- **落地位置**：`docs/DECISIONS.md` `DEC-2026-11-03-06`；`docs/v2/81_new_ui2_wireframe_01_market.md`（第 1／3.1／6 節 VIX 讓位處與第 10 節）；`docs/BACKLOG.md` BL-0536；`docs/HANDOFF.md`；`ui_v3/viewmodels/market_page.py`、`ui_v3/adapters/market_page.py`（註解）；`tests/ui_v3/test_ui_v3_market_page_adapter.py`。

```text
裁示：採 A。
正式規則：
- 當 Primary 目前檢視為 VIX 時，Secondary 的 VIX 卡讓位、不顯示。
- 當 Primary 切回「比較／美 10Y／美 2Y」時，Secondary VIX 卡恢復顯示。
- 這是 presentation 去重規則，目的為遵守既有 D1「Secondary 不複製 Primary」。
- 不修改 VIX 的資料、來源、公式、狀態、freshness 或任何投資語意。
- 不因讓位補入其他新卡片；Secondary 張數可以隨 Primary 檢視而變化。
- 不為維持卡片數量而新增資料或擴大版面 scope。
另兩個殘留點不擴大 scope：週末起點殘留邊界維持既有 A2 contract（adapter 已有 pre-window margin），除非真實資料驗證證明仍有語意錯誤，否則不改 formula；日期格式目前 Preview 用 YYYY-MM-DD 可暫留，視為 presentation wording/format，正式定版時與其他待核准字樣一起送 Gate。
```
