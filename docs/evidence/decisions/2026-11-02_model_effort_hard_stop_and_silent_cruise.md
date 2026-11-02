# 客戶 2026-11-02 Silent Autonomous Cruise 重申＋Hard-Stop Model／Mode／Effort Change Gate（逐字）

- **來源**：客戶 2026-11-02 在本對話中的訊息，經總管於派工單內轉存為逐字文字檔；執行組照抄，未見客戶對話本身。
- **性質**：永久治理規則（permanent governance rule）。本檔只存原文，不含執行組讀法；圍欄為轉存的客戶原文，字句未改。
- **遮蔽**：無。本文沒有作者或老師姓名，也沒有 secret。
- **決策登記**：`docs/DECISIONS.md` `DEC-2026-11-02-04`（客戶裁示）。
- **存檔日期**：2026-11-02
- **依據規則**：`PROJECT_RULES.md` 12.1 新裁示同批 GitHub 落盤、12.2 GitHub Discussion Persistence Gate。

```text
恢復 Silent Autonomous Cruise / No Progress Narration。

不要再回報：

- CI 還在跑／跑多久
- writer 還在處理
- untracked file 為何尚未 commit
- 下一步準備做什麼
- 沒有新決策價值的中間狀態

以上都屬安全且已授權的進度，請自行處理。

之後只在以下情況回報：

1. 需要我裁示的 Decision Gate
2. 真 blocker／CI 真錯誤
3. 需要切換 Model / Effort
4. 整批完成並已做 GitHub final verification

另外新增一條硬停手規則：

«如果下一個階段建議切換 Model、模式或 Effort，必須先回報 Model / Effort Change Gate，明確告訴我建議切成什麼，然後立即停下。
不得先開始下一階段，不得先做下一批任何實作，不得邊提醒邊繼續。
必須等我明確回覆「已切換／可以開始」後，才能進入下一階段。»

這條也要寫入正式 GitHub governance，並納入 HANDOFF / 稽核清單；若尚未落盤，請在本批安全範圍內補齊。
```

## 落地位置

- `docs/DECISIONS.md` `DEC-2026-11-02-04`
- `PROJECT_RULES.md` 第 0.5 節快速索引（Silent Autonomous Cruise、Model／Effort 兩列）、第 3 節 3.3 末尾指標、第 5 節 5.1 第 7／8／10 點「改好了」劃線或指標、新增第 11 點（含稽核檢查項）、第 6 節 6.1.3 第 3 點劃線指標
- `docs/HANDOFF.md` 第 0 節接手檢查一行、Resume Checkpoint 唯一下一接手點
