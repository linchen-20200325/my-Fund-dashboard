# 客戶 2026-11-03 指示：PR #1135／#1136 收斂與 💼 階段分工（逐字節錄）

- **來源**：客戶對話中的指示，經總管於派工單內以「原文節錄」逐字轉交；執行組照抄，未見客戶對話本身（repo 內無另一份原文可做逐位元組比對）。**節錄**，非全文。
- **性質**：正式指示（文件治理與工作分工；不改 formula、data semantics、資料來源、門檻、狀態判定或投資語意；不修訂 frozen 44）。
- **遮蔽**：無。本文沒有作者或老師姓名，也沒有 secret。
- **決策登記**：`docs/DECISIONS.md` `DEC-2026-11-03-12`
- **存檔日期**：2026-11-03（#1135 的 GitHub 授權日期顯示 2026-11-04，分支名 `20261104`；以 GitHub PR 日期為準）
- **依據規則**：`PROJECT_RULES.md` 12.1 新裁示同批 GitHub 落盤、12.2 GitHub Discussion Persistence Gate。
- **落地位置**：`docs/v2/80` 第 7.4、16.1 節；`docs/HANDOFF.md`；`docs/BACKLOG.md` BL-0536。

```text
請先完成目前 PR 收斂，不開始新的 UI 功能。Fresh GitHub Verification Gate 後，處理：PR #1135：ChatGPT 提交的 New UI2 文字設計修訂。PR #1136：Shell 定字與降級情境首屏修正。先比較兩個 PR 的完整 diff、規格重疊、依賴順序與合併衝突。採 Minimum-Cost Correct Path，選擇最安全、最少重工的整合順序。要求：1. 兩個 PR 的有效成果都要保留，不讓舊版規格覆蓋新版。2. #1135 由你進行獨立文件與治理稽核。3. #1136 保持正式字樣的單一 SSOT。4. 不修改 frozen、歷史證據、正式資料公式或來源。5. 各 PR 通過獨立稽核、CI 與既有 Auto-Ship Gate 後，依 normal merge 合併。6. 全部完成後更新 HANDOFF／BACKLOG，提供 final GitHub Verification。完成兩個 PR 後停在下一個交接點：💼 我的資產：UI × Data × Evidence 詳細設計。下一階段先由 ChatGPT 負責設計文字、資料串接契約及正式 GitHub 規格，再由你依核准規格實作。現在不要自行開始 💼 程式開發，也不要另開競爭性設計文件。
```
