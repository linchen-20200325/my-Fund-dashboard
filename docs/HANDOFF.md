# HANDOFF — 現行交接（單一現況；每次覆蓋、不累加）

> **用途**：只回答六件事：現在在哪、active work、最新 main／PR／CI checkpoint、下一接手點、blocker／待客戶裁示、新對話從哪開始。**本檔不得單獨作為完成或正確的證明**（`PROJECT_RULES.md` 1.3）；任何「已合併」「CI 綠」都要回 GitHub／git 重查。
> **歷史**：2026-11-03 Canonical Rule Convergence 批把舊版全文（543 行；含檔頭 40 則追加 checkpoint、24 個「第 N 次現況」框、舊下一步）逐字搬到 `docs/evidence/history/2026-11-03_handoff_pre_convergence.md`（**NOT CURRENT，不是現行規則或現況**）。更舊的交接本 `docs/handover_2026_09_26_latest.md` 為歷史紀錄（第 0 節永遠不准刪，客戶 2026-09-28 裁示）。本檔改寫依據：客戶 2026-11-03 指示（`DEC-2026-11-03-08`）；`PROJECT_RULES.md` 6.1.2「覆蓋、不累加」。

> **⏯ Resume Checkpoint**（總管提供；接手先依 `PROJECT_RULES.md` 6.1.2 比對 GitHub，不一致以 GitHub 為準；本區塊覆蓋舊版）
> - **查詢時點**：2026-11-03；**latest verified main＝`4d8c07dd`**（Merge #1131，BL-0536 🌍 Preview rendering；本批讀工作樹基底，**未重查 GitHub**，接手先 `git fetch origin main`）。
> - **Open／Draft PR**：以 GitHub 為準（本檔寫成時，下列兩批尚未開 PR）。
> - **唯一下一接手點（單一）**：**(1) 🌍 正式字樣落盤批**（`DEC-2026-11-03-07`；分支 `ccr-a427a479-81wzdy`，commit `82ba783f`）→ 獨立稽核 → 開 PR → CI → 合併（PR 號以 GitHub 為準，**待開**）；**(2) 本規則收斂批**（`DEC-2026-11-03-08`）→ 獨立稽核（治理規則等級，`DEC-2026-10-16-05`）→ CI → 合併。兩批 docs／字樣為主，無新資料源、無公式變更。**(3) 之後**才是 Navigation Shell＋H5（尚未開始，需 (1)(2) 合併與下列 Gate 裁示）。
> - **待客戶裁示（隨 (1) 一併回報；BL-0539）**：🌍 首屏「市場狀態」與「是否需注意」拆兩枚 chip 的預算 Gate——Visual Budget 5 vs 6；方案 A＝兩枚 chip 並 amend 44 預算為 ≤6、B＝維持現況一枚共用 chip、C＝兩列各一枚 chip 並把「基準日」改為圖上純文字揭露行（→ 5；總管推薦 C）。未裁示前不實作、不放寬預算。

## 1. 必讀順序（新對話或換人接手）

1. `CLAUDE.md`（資料完整性憲法；`§-2`、`§-1.5`、`§-1` 位階最高）
2. `PROJECT_RULES.md`（專案 AI 工作規則入口；**0.4「現行規則索引」＝規則與頁面規格的唯一入口**）
3. 本檔
4. `docs/BACKLOG.md`（未完成工作主索引）
5. `docs/DECISIONS.md`（客戶裁示與正式決策）
6. 依任務讀對應 SSOT：New UI2 架構 `docs/v2/80`；各頁規格見 `PROJECT_RULES.md` 0.4 索引；子法 1 `docs/v2/CONSTITUTION.md` 須併讀修正案 #8 `docs/v2/57_amendment_8_directional_judgment.md`（`DEC-2026-10-16-14`）；例外與待判定登記簿 `EXCEPTIONS.md`。

**工作規則一律看 `PROJECT_RULES.md`，本檔不重述**：Silent Autonomous Cruise／No Progress Narration（第 3 節）、Model／Effort Change Gate 與 Hard-Stop（5.1）、Context Efficiency（11.1）、Minimum-Cost Correct Path（9.2）、正式 Streamlit 顯示規則與 cutover 檢查（13.2）、一般 merge commit 與不加 AI 署名（第 10 節）。

## 2. 現況（2026-11-03；以 GitHub 為準）

| 項 | 現況 |
|---|---|
| UI 三層邊界 | Old UI read-only；`ui_v2` maintenance-only；`ui_v3`＝New UI2 唯一未來正式（`DEC-2026-11-02-05`、`-06`）。正式 App 現況推定為 Old UI（Streamlit Cloud 設定，repo 內無法查證）；Preview App 平行驗收，尚未 cutover |
| 現行五頁 | 🌍 市場與趨勢／💼 我的資產／🔍 找基金／🤖 AI 投資總結（Phase 7 前不掛導覽）／⚙️ 設定（`PROJECT_RULES.md` 13.2 第 1 點；程式側 `ui_v3/shell/registry.py`） |
| 🌍 | wireframe 已裁示（`DEC-2026-11-03-01`）；歸一化 A2／B2／C2、H1b／H2／H3、Preview rendering 已合併（#1125～#1131）；九項正式字樣已落盤於 `82ba783f`（待合併，見上）。詳情看 `docs/BACKLOG.md` BL-0536 與 `docs/v2/81` |
| 💼／🔍／⚙️／🤖 | wireframe 尚未起草（順序 💼 → 🔍 → ⚙️；🤖 依 Phase 7）；核准前不寫該頁 `ui_v3` 代碼 |
| cutover | 未開始；強制驗收項 BL-0535 |
| 本機環境 | `ui_v2` 摘要守衛要用 Python 3.11 跑（CI 為 3.11）；`.claude/worktrees` 殘留會讓檔案引用守衛誤紅，需要時在乾淨 worktree 驗 |

## 3. 待客戶裁示（Decision Gate；本檔只列 ID，內容與推薦看 `docs/BACKLOG.md`）

| ID | 題目 |
|---|---|
| BL-0538 | Latest-Rule-Only 讀法與 0.5 改寫的客戶確認（G-1；總管讀法採方案 B，待確認） |
| BL-0539 | 🌍 首屏「市場狀態」「是否需注意」拆兩枚 chip（Visual Budget 5→6；方案 A／B／C，總管推薦 C） |
| BL-0540 | Missing 字樣並存（`資料不足`／`此圖目前沒有可畫的資料`／`◇ 資料未備`）是否取代或並存（G-2）；🤖 輸出「六項」對映六段／四區（G-5）；資料健康度集中 ⚙️ 與 frozen 44 的承接（G-3，需 amendment） |
| BL-0369 | freshness 門檻（BL-0536-H4）；未裁示前首屏只顯示 `⬜ 門檻待裁示` |
| BL-0537 | Old UI／`ui_v2` 凍結清單機械守衛 |
| 其他 | 見 `docs/BACKLOG.md` §4 快速索引〈待客戶裁示〉 |

## 4. 新對話 takeover

1. `git fetch origin`；`git log -1 --format='%H %P' origin/main` 與第 2 節比對，不一致以 GitHub 為準並先更新本檔。
2. 查 open PR 與 main 最新 push 的三條 CI job 逐條 `conclusion`。
3. 依第 1 節順序讀文件；待辦查 BACKLOG，裁示查 DECISIONS，舊脈絡查 `docs/evidence/history/`（歷史，不是現行）。
4. 確認 working tree 乾淨、無殘留 worktree，再接上方 Resume Checkpoint 的接手點；有不一致或新發現依 `PROJECT_RULES.md` 第 12 節落盤，不只留在聊天。

## 5. 本檔沒查證的部分

- main `4d8c07dd` 為工作樹基底，**未重查 GitHub／CI**；兩批「待開 PR」為總管轉達。
- 第 3 節 BL-0538～BL-0540 為本批新登記，內容單組寫成、未經第二組驗證。
- 舊版 HANDOFF 內「未查證」各條（約 60 條，多為 2026-10 月批次紀錄）隨全文搬至歷史檔，**不再是現行聲明**。
