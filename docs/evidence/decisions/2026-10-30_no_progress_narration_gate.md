# 客戶 2026-10-30 No Progress Narration Gate（禁止過程直播）正式裁示（逐字）

- **來源**：客戶 2026-10-30 對話中的正式裁示，經總管於派工單內轉存為逐字文字檔；執行組照抄，未見客戶對話本身。
- **遮蔽**：無。本文沒有作者或老師姓名，也沒有 secret。
- **決策登記**：`docs/DECISIONS.md` `DEC-2026-10-30-03`（客戶裁示）。落地：`PROJECT_RULES.md` 第 3 節 3.3。
- **性質**：本檔只存原文，不含執行組讀法。圍欄為轉存的客戶原文，字句未改；唯一格式處理：無（行尾空白：0 行；單一換行結尾）。
- **存檔日期**：2026-10-30
- **圍欄內文 sha256**：`0f94d50913abba4a205e9d0026628de9e8f85227341e943cfb266bed20a65392`
- **依據規則**：`PROJECT_RULES.md` 12.2 GitHub Discussion Persistence Gate。
- **撞字**：無。

```text
立即恢復 Silent Autonomous Cruise。

你目前又開始輸出大量過程直播，這違反既有規則。

以下這類訊息從現在起禁止對客戶輸出：

- 已派出幾組 agent
- 哪一組正在執行
- 哪一組正在稽核
- 正在寫哪個檔案
- scratchpad 已寫入
- branch 已建立
- working tree 有哪些未提交變更
- 等 CI
- 等 agent
- 等稽核
- 等 commit / push
- 下一步準備派哪組
- 「Launch independent audit…」
- 「Now record…」
- 「正在執行代理」
- 任何內部 orchestration / agent routing / scratchpad / worktree narration

這些全部屬於：

«Internal execution telemetry»

不是客戶需要知道的內容。

新增硬規則：No Progress Narration Gate

除非符合以下 4 類之一，否則完全不要傳訊息給客戶：

1. 🔴 真正需要客戶裁示的 Decision Gate
2. 🔴 真 blocker，而且無法自行繼續
3. 🟡 Model / Effort Change Gate，需要客戶知道或切換
4. 🟢 一個完整 Batch / Phase 已完成，可以一次性收尾回報

其餘全部靜默執行。

特別注意：

即使工作持續超過很久，也不要為了「讓客戶知道我還在做」而回報進度。

不要輸出：

- 「正在處理」
- 「已派出」
- 「還在跑」
- 「等結果」
- 「完成後再……」
- 「目前沒有要你回覆」
- 「只是狀態通知」

如果不需要客戶採取行動，就不要發訊息。

對外回報原則

允許的完成回報必須一次講完：

- 做了什麼
- GitHub 最終狀態
- CI / QA 結果
- 是否有未解決風險
- 是否需要客戶回覆
- 下一個唯一接手點

不要把同一 Batch 拆成 5～10 則狀態訊息。

Agent / scratchpad 規則

agent、sub-agent、scratchpad、worktree、internal audit flow 都是內部實作細節。

除非：

- 它造成真正 blocker
- 或產生需要客戶裁示的衝突

否則不要對客戶提及。

GitHub Durable Memory

把這次新增的 No Progress Narration Gate 正式寫入 GitHub 的長期治理規則。

至少同步到：

- "PROJECT_RULES.md"
- 必要時 "docs/DECISIONS.md"

HANDOFF 只需指向規則，不要複製整段。

正式規則要能讓新 session 只讀 GitHub 就知道：

«Silent Autonomous Cruise = 不只是「不用客戶回覆」，而是「不需要客戶行動時根本不要發訊息」。»

現在的處理

你目前 D-3 / OAuth / Batch D 工作照常繼續。

這一則之後：

不要再傳任何進度訊息。

直到出現：

- 真 Decision Gate
- 真 blocker
- Model / Effort Gate
- 或完整 Batch D 完成

才一次回報。
```
