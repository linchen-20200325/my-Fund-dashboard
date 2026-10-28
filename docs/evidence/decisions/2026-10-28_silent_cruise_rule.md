# 客戶 2026-10-27 永久工作規則：恢復並嚴格執行 Silent Autonomous Cruise（逐字）

- **來源**：客戶 2026-10-27 正式裁示（客戶稱「這是永久工作規則，不是本輪臨時要求」），經總管於派工單內逐字轉存；執行組照抄，未見客戶對話本身。
- **遮蔽**：無。本文沒有作者或老師姓名，也沒有 secret。
- **決策登記**：`docs/DECISIONS.md` `DEC-2026-10-27-45`（客戶裁示，永久）。落地：`PROJECT_RULES.md` 第 3 節 3.2、第 0.5 節索引一列、`docs/HANDOFF.md` 第 0 節第 6 點。
- **性質**：本檔只存原文，不含執行組讀法。圍欄為派工單內客戶原文，字句未改；唯一格式處理：原文有三行只含空白的行（編號項目與其子項之間），行尾空白已清成空行（本 repo 不留行尾空白），其餘字元、順序、段落一字未動。
- **存檔日期**：2026-10-28（裁示日 2026-10-27）。
- **圍欄內文 sha256**：`1c33dde67761a575acd35c397a812d9f5d6e8b3ab46da62395e43ab90ac93589`
- **依據規則**：`PROJECT_RULES.md` 12.2 GitHub Discussion Persistence Gate。

```text
恢復並嚴格執行 Silent Autonomous Cruise。

你現在又開始輸出不必要的中途進度，例如：

- 「實作批次已派出」
- 「同一個 PR 內做三項」
- 「完成後再派獨立稽核」
- 「實作組還在跑」
- 「不需要你回覆」

這些都屬於過程碎碎唸，禁止再輸出。

從現在起：

只有以下 4 種情況才可以主動回報

1. 完整 batch / stage 已完成

   - PR 已完成
   - audit 已完成
   - CI 結果已知
   - merge／Auto-Ship 已完成或明確被阻擋

2. 真正 Stop Gate

   - 必須客戶裁示才能繼續

3. Model / Effort Change Gate

   - 必須客戶切換模型或 effort

4. 真正 blocker

   - 無法安全自行解決
   - 且會實際阻止下一步

以下情況一律靜默

- PR 正在寫
- PR 已開但 CI 還在跑
- audit 已派出
- agent 還在工作
- 正在跑測試
- 等 workflow
- 等 reviewer
- 等 mergeability 更新
- 正在同步 BACKLOG / HANDOFF
- 「這則只是通知」
- 「不需要你回覆」
- 重複確認 merged / ready-for-review / subscribed / unsubscribed
- 沒有新決策的新狀態

不要再用「🟢 不需要你回覆」來包裝中途進度。
如果真的不需要客戶回覆，就不要發訊息。

完整批次回報格式

只在整批結束時一次回報：

- 第一行：🟢／🟡／🔴
- main SHA
- PR
- 完成內容
- audit
- CI
- 是否需要客戶回覆
- 下一個唯一接手點
- Model / Effort（只有需要改變時才特別標）

除此之外保持完全靜默。

這是永久工作規則，不是本輪臨時要求。
請同步進 PROJECT_RULES / HANDOFF 的工作模式說明，避免新對話再次退化。

目前 BL-0517 繼續執行，不需要回報中途狀態。
```
