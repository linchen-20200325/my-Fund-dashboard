# 客戶 2026-10-17 歷史 branch 清理裁示（存檔）

- **來源**：客戶 2026-10-17 在對話中的裁示，經總管於派工單內轉述要點；本檔作為 `docs/DECISIONS.md` `DEC-2026-10-17-06` 的 provenance。
- **存檔日期**：2026-10-17。**存檔時的 base**：main `762f602`（全長 `762f602863f622bfb4d994db06d7e512b04436dd`）。
- **性質**：**要點轉述，不是客戶逐字原文**。總管派工單以條列轉述，圍欄內是該條列照抄；文件組未見客戶對話本身。
- **效力**：本檔是裁示的存檔，不是新規則。落地範圍以 `docs/DECISIONS.md` `DEC-2026-10-17-06` 為準。

---

```text
- 停止為舊 branch 做考古與封存。
- 舊 branch 若含未進 main、未完整封存，或未來可能需要的程式碼或文件，可以放棄；日後真的需要時，依當時最新的 main、SSOT 與需求重新設計、重新實作，不以保留舊 branch 為前提。
- 歷史 branch 與 WIP branch 只要不是現行 workflow、data、output 所依賴的，就可以刪除。刪除前只做最低限度檢查：是否被 open PR、workflow 或 production 使用；不再做歷史內容完整性調查。
- 不得刪除的範圍：
  - main、data、push-assets
  - 現行 workflow 依賴的 trigger／results branch
  - open PR 使用中的 branch
  - 其他經查證屬 production／runtime 必要的 branch
- 沒有權限刪除時，列出清單交給客戶手動刪除。
```
