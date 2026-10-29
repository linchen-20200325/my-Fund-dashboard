# 客戶 2026-10-29 永久規則：Context Compaction Gate（逐字）

- **來源**：客戶 2026-10-29 對話中的永久規則裁示，經總管於派工單內轉存為逐字文字檔；執行組照抄，未見客戶對話本身。
- **遮蔽**：無。本文沒有作者或老師姓名，也沒有 secret。
- **決策登記**：`docs/DECISIONS.md` `DEC-2026-10-29-04`（客戶裁示）。落地：`PROJECT_RULES.md` 11.1 之 Context Compaction Gate 小節。
- **性質**：本檔只存原文，不含執行組讀法。圍欄為轉存的客戶原文，字句未改；唯一格式處理：無（行尾空白：0 行）。
- **存檔日期**：2026-10-29
- **圍欄內文 sha256**：`907257f1f80cea9c5c1e538c1bd490584c774af355a6a59e2a260a1a08a9d83a`
- **依據規則**：`PROJECT_RULES.md` 12.2 GitHub Discussion Persistence Gate。

```text
補充一條永久 Context Compaction 規則，並寫入適當的 PROJECT_RULES / AI 作業手冊；不要另建重複規則文件。

Context Compaction Gate

專案 AI 必須主動管理對話 context，不得一路累積到接近上限才處理。

觸發條件

符合任一情況時，應先做 context compaction，再繼續工作：

1. 對話已累積多個完成 Batch / PR / Decision；
2. 已完成一個明確階段，接下來進入新階段；
3. 同一對話已反覆讀取大量 GitHub diff、CI、audit、HANDOFF；
4. 開始出現重複查證、重複敘述、忘記已裁示事項；
5. context 使用量明顯偏高，可能影響理解力或造成 token 浪費；
6. Model / Effort 升級前，若大量舊 context 已不再需要。

壓縮方式

壓縮時只保留：

- GitHub 最新 main SHA
- Open / Draft PR
- 尚未完成的 Decision Gate
- 現行 PROJECT_RULES / DECISIONS
- 目前 Batch 目標
- 已確認的資料契約
- 尚未解決的 bug / risk
- 下一個唯一安全接手點

已完成且已寫入 GitHub 的：

- 舊 PR 過程
- CI 等待過程
- audit 對話
- 重複研究
- 已結案 Decision 討論
- 中間推理與暫時方案

全部視為可丟棄 context，後續需要時重新由 GitHub targeted fetch。

核心原則

GitHub 是長期記憶。

對話 context 只保存「現在仍會影響下一步」的資訊。

不得為避免重新讀 GitHub 而長期保留大量歷史 context。

Silent Cruise

Context compaction 屬內部維護，不需要回報客戶。

只有：

- compaction 後發現 GitHub 與既有記憶衝突
- 遺失必要裁示
- 需要重新確認客戶決策

才回報。

模型

此規則屬低風險治理更新：

Sonnet 5.5
Effort：Medium

完成規則落盤後繼續原本工作，不要另開新 Batch。
```
