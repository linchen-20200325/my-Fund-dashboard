# 客戶（使用者本人）2026-11-20 對 OB-B 最小離線切片之授權確認（逐字）

- **來源**：使用者（客戶）2026-11-20 在 ChatGPT 對話中親自確認，經使用者訊息轉交 Claude Code 存檔；執行組以檔案複製方式放入圍欄，未手打重抄，未見 ChatGPT 對話本身。
- **性質**：只保存授權原文。本檔不是程式 PR 授權，不含任何原文沒說的授權。原文自己寫明「仍需獨立治理稽核、白名單與 CI 驗證後才能開始程式 PR」，該前置條件本檔不解除、不放寬。
- **不改既有決策**：不改 `DEC-2026-10-31-03`、`DEC-2026-11-08-02` 本文；原文對兩者的關係（離線 Fake Provider 階段限縮裁示、非 Provider／Phase 7／Claude API runtime）僅以原文為準，本檔不另行擴張解讀。
- **遮蔽**：無。本文沒有作者姓名，也沒有 secret。
- **決策登記**：`docs/DECISIONS.md` `DEC-2026-11-20-01`
- **存檔日期**：2026-11-20
- **base**：main `c7a1349f`
- **圍欄內文**：773 bytes，sha256 `c2ce8efa83fa6cd9b15da6dee121d51e19e8f03a41a7353adbd983ef89e68071`（含結尾單一換行；與來源檔位元組比對相同）

```text
我本人確認授權投資基金 OB-B 最小離線切片：Provider-neutral 型別與介面、離線 Fake Provider、結構化錯誤與降級狀態、注入式及無網路測試；採 Q-OB1 A 與 Q-OB2 A，限 services/onebrain/ 的四個新增程式檔及三個新增測試檔。此授權是 DEC-2026-10-31-03 的離線 Fake Provider 階段限縮裁示，不屬 DEC-2026-11-08-02 禁止的正式 Provider／Phase 7／Claude API runtime，不受 BL-0527／0528 或完整 D2 尚未完成阻擋。不得使用真實 Provider、SDK、金鑰、prompt、Digest、UI、Risk Cap 或投資行動；FAKE 輸出不得進正式頁面或 production 路徑。同意將這段本人確認逐字存入 GitHub，仍需獨立治理稽核、白名單與 CI 驗證後才能開始程式 PR。
```
