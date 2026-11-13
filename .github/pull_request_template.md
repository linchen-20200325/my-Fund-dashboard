<!-- 最小 PR Impact Check（客戶 2026-11-13 Batch 2 第 2 項）。本註解不會顯示；每一項請留下一個選項、不要留空。
     對映：Stop／Decision Gate＝PROJECT_RULES §4；完成定義＝§7；稽核分級＝§8；PR／merge＝§10。
     本表只做如實揭露：不新增 Gate、不取代 CI／QA、不構成授權；沒跑的寫沒跑，查不到寫 NOT VERIFIED。 -->

## 來源與授權
- 派工入口／授權出處（DEC-…／Issue #…；Issue 不是授權 SSOT）：
- 基準 main `<完整 SHA>`　本 PR head `<完整 SHA>`
- diff 清單（檔／變更／大小）與「是否在授權範圍內、無夾帶」：

## Impact Check（逐項選一，「無影響」也要勾並附一句依據）
- **功能行為**（產品方向、AI 行為是否改變投資判斷）：[ ] 無影響　[ ] 有影響：
- **資料契約**（schema／欄位／identity／missing 語意／來源優先序）：[ ] 無影響　[ ] 有影響：
- **金融公式與門檻**（公式、投資語意、threshold 的值或語意）：[ ] 無影響　[ ] 有影響：
- **UI**（版面、字樣、元件、分頁動線；UI 變更附桌機與 390px 截圖，未做寫「Visual Fidelity Gate 未執行」）：[ ] 無影響　[ ] 有影響：
- **測試**（新增／修改／skip；是否動黃金檔或 baseline）：[ ] 無影響　[ ] 有影響：
- **SSOT 文件**（CLAUDE／PROJECT_RULES／DECISIONS／BACKLOG／HANDOFF／凍結 44）：[ ] 無影響　[ ] 有影響：
- **回滾條件**：[ ] revert 單一 merge commit 即足夠　[ ] 另有不可逆項（production 寫入／migration／歷史改寫／branch 刪除）：
- **Stop／Decision Gate 對映**：[ ] 以上皆未觸及　[ ] 已觸及，客戶裁示出處：

## 風險分級（跨級取最高級；AI 自判，客戶可覆寫）
- [ ] 低風險（文字、說明、交接同步）：作者自驗
- [ ] 治理規則／data semantics／investment meaning／公式／identity／freshness／provenance／migration／destructive cleanup：至少 1 組獨立稽核
- [ ] 資安／重大合規：2 組獨立稽核

## QA／CI 狀態
- 非作者 QA（誰、組數、MERGE-READY／NEEDS-FIX、針對哪個 head）；作者自驗不得寫成獨立 QA：
- CI 對最新 head（run 編號；各 job 的 head_sha 須等於上列 head）：
  - Fast：　　Schema：　（逐條讀 conclusion）
  - Slow、Visual 為 continue-on-error：讀 step log 末行，不只看 job 圖示或 mergeable：
- 本機測試（指令、環境、與 CI 的版本差異）：
- NOT RUN／NOT VERIFIED（如實列出）：

## 衛生
- [ ] commit message 與本說明沒有共同作者行、session 網址或 ID、模型名稱；建 PR 後已讀回 body，工具自動附加且帶 session 網址的頁尾已改寫移除
- [ ] 預計用一般 merge commit（禁 squash）；不 force push；未碰 workflow 與 required checks（除非本 PR 即為該授權）
