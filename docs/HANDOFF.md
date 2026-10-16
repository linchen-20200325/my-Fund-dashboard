# HANDOFF — 現行交接

> **用途**：自 2026-10-16 起的**現行交接**。只回答六件事：現在在哪、active work、最新 main／PR／CI checkpoint、下一步、blocker／待客戶裁示、新對話從哪開始。
> **歷史交接紀錄**：`docs/handover_2026_09_26_latest.md`（2026-10-16 起整檔轉為歷史紀錄＝總管結構判定；第 0 節永遠不准刪＝客戶 2026-09-28 裁示；舊裁示、舊待辦、舊規則原文都在那裡）。
> 出處：客戶 2026-10-16 頒布 Project AI Constitution v1.0（總管轉達要點，對話中，repo 內無逐字原文）；本檔結構依總管 2026-10-16 設計基準。
> 文中若引「約 :N」行號，以 `git show d5d391b:<path>` 讀（本批合併後交接本等檔的行號已因指標行而位移）。

---

## 0. 本檔的規則

1. **HANDOFF ≠ BACKLOG。** 本檔只寫「現在」與「下一步」；未完成工作的主索引在 `docs/BACKLOG.md`，客戶裁示在 `docs/DECISIONS.md`，工作規則在 `PROJECT_RULES.md`。本檔不複製那些內容，只指過去。
2. **本檔不得單獨作為完成或正確的證明。** 任何「已合併」「CI 綠」「已完成」都要能回到 GitHub／git／測試輸出查證；本檔寫的是查詢當下的快照，接手時先重查（見第 5 節）。
3. **更新時機**：每次 merge 後（main SHA）、每完成一輪稽核、milestone、換對話前更新本檔（main SHA、active PR、CI、下一步）。來源是交接本 §0.1（五個觸發點）與 §0.5 第 2～5 條（客戶逐字），**承接不抄**：原文仍在 `docs/handover_2026_09_26_latest.md` 第 0 節；承接規則統一見 `PROJECT_RULES.md` 第 12 節。把「寫進交接本」改讀為「寫進本檔」是**總管裁決**（可被客戶推翻），張力見 `PROJECT_RULES.md` 第 14 節之 10。
4. 交接本 §0.6「交接讀取 · 省額度」所稱「HANDOFF 第一節」，自 2026-10-16 起讀作**本檔**（交接本第 0 節開頭已加註；圍欄內逐字原文未改）。
5. 會漂移的數字一律附查詢時間與 SHA；過期就重查，不要引用舊值。

## 1. 必讀順序（新對話或換人接手時）

1. `CLAUDE.md`（資料完整性憲法；`§-2`、`§-1.5`、`§-1` 位階最高）
2. `PROJECT_RULES.md`（專案 AI 工作規則入口；受 `CLAUDE.md` 管轄）
3. 本檔 `docs/HANDOFF.md`
4. `docs/BACKLOG.md`（未完成工作主索引）
5. `docs/DECISIONS.md`（客戶裁示與正式決策）
6. 依任務讀對應 SSOT，例如：
   - `docs/v2/44_fund_ui_ssot.md`（凍結 SSOT，畫面與文案規格）
   - `docs/v2/49_data_integration_plan.md`（資料接線計畫）
   - `docs/v2/55_preview_acceptance_guide.md`（Phase 3 驗收前置與已知限制）
   - `docs/v2/CONSTITUTION.md`（子法 1）
   - `EXCEPTIONS.md`（憲法的例外清單與 `8.3.P` 待判定登記簿）

## 2. 現況 checkpoint

**查詢時間**：2026-10-16 10:33 UTC（`date -u` 實測）。**查詢方式**：`git fetch` 後 `git log`、`git ls-remote --heads origin`；GitHub MCP 唯讀工具（open PR 清單、main push 的 workflow run 與 job）。

| 項目 | 現況 | 出處 |
|---|---|---|
| main | `d5d391b`（全長 `d5d391bd6f2b14939f71dd1ed0e007449f519f59`；PR #978 的 merge commit，2 parents `cac7c005`、`74b865d4`），**本批 PR 合併後更新** | 本組 `git log -1 --format='%H %P'` 實查 |
| main CI | `d5d391b` 的 push run `38884240502`：Schema gate、Fast checks、Slow tests（informational）三條 job 皆 `success`（逐條看 job conclusion，不看 run 總結） | GitHub MCP `list_workflow_jobs` 實查 |
| Phase 位置 | **Phase 2 完成**；分支成果保存批完成（#978）；**Project AI Constitution v1.0 導入中**（本批）；**Phase 3 尚未開始，等客戶指示** | Phase 2 完成見交接本〈第六十五次更新〉；保存批見〈第六十六次更新〉；Phase 3 時機為總管 2026-10-16 轉達 |
| active PR | **本批 PR #979**（導入 v1.0 四份治理文件；由總管開與合併） | 總管 2026-10-16 派工單 |
| 舊 draft PR | #791、#836、#837、#839 四支，**客戶指示不動** | GitHub MCP `list_pull_requests(state=open)` 實查：open 只有這四支 draft（本批 PR 開之前） |
| blocker | 目前無（依上列實查：main CI 三條 success、無衝突中的 PR） | 本組實查；「無」只涵蓋上列查過的項目 |

## 3. 下一步與待客戶裁示

**下一步**：

1. 本批 PR（`PROJECT_RULES.md`、`docs/BACKLOG.md`、`docs/DECISIONS.md`、本檔，及交接本／`CLAUDE.md`／root `BACKLOG.md`／`TODO.md` 的指標行）→ 稽核 → CI → 合併 → 更新本檔第 2 節 main SHA。
2. 合併後**停手等客戶指示**是否開始 **Phase 3：客戶實際使用／視覺／390px 手機 UX 驗收**（依 `docs/v2/55_preview_acceptance_guide.md`）。客戶回報驗收問題後進 Phase 4（修驗收問題，每批原則上最多 3 項）。
3. 本項以外**不構成動工授權**（`CLAUDE.md` §-1）。

**待客戶裁示**（本檔不複製，只指位置）：

- `PROJECT_RULES.md` 第 14 節〈未調和的衝突（待客戶裁示）〉。
- `docs/BACKLOG.md` 中標「需客戶裁示」的條目（例：子法 1 條款衝突、`delete_branch_on_merge` 等既有登記；以該檔為準）。

## 4. 分支現況摘要

- 遠端分支的 A～E 分類、保存清單與保存位置：見交接本〈第六十六次更新〉四與 `docs/evidence/README.md`。
- 本批**未刪任何既有分支、未建 tag**（PR 自身 head 依 `delete_branch_on_merge` 於合併時自動刪除，屬既有常設授權，總管裁決，可被客戶推翻；見 `PROJECT_RULES.md` 第 10 節、第 14 節之 8）。既有／歷史 remote branch 的刪除須客戶指示；刪前六項確認見 `PROJECT_RULES.md` 第 10 節。
- 遠端分支數：19（量測時間 2026-10-16 10:33 UTC，`git ls-remote --heads origin`，本批 PR 開立之前；本批 PR head 推送後與合併自動刪除後都會變，引用前重查）。

## 5. 新對話 takeover

接手時先做下列驗證，**不得要客戶重講已落盤的資訊**：

1. `git fetch origin`，以 `git log -1 --format='%H %P' origin/main` 確認 main SHA，與本檔第 2 節比對；不一致 → 以 GitHub 為準，先更新本檔再動作。
2. 查 open PR 與 main 最新 push 的三條 CI job（Schema gate、Fast checks、Slow tests）逐條 `conclusion`。
3. 依第 1 節順序讀文件；待辦查 `docs/BACKLOG.md`，裁示查 `docs/DECISIONS.md`，舊脈絡查交接本（凍結，只讀）。
4. 確認 working tree 乾淨、沒有遺留的未提交內容或殘留 worktree。
5. 確認之後再接續第 3 節的下一步；有不一致或新發現，依 `PROJECT_RULES.md` 第 12 節（新發現落盤）寫進對應文件，不只留在聊天。

## 6. 本檔沒查證的部分

- 「Phase 3 等客戶指示」與本批範圍為總管 2026-10-16 轉達，本組未見客戶原文。
- `PROJECT_RULES.md`、`docs/BACKLOG.md`、`docs/DECISIONS.md` 由同批其他組撰寫，本檔原稿寫作時尚未見其定稿；PR #979 稽核回修時已把本檔對 `PROJECT_RULES.md` 的引用改為該檔節號。
- blocker「目前無」只涵蓋第 2 節查過的項目，不宣稱窮舉。
