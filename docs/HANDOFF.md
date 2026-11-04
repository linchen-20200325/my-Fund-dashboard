# HANDOFF — 現行交接（單一現況；每次覆蓋、不累加）

> **用途**：只回答六件事：現在在哪、active work、最新 main／PR／CI checkpoint、下一接手點、blocker／待客戶裁示、新對話從哪開始。**本檔不得單獨作為完成或正確的證明**（`PROJECT_RULES.md` 1.3）；任何「已合併」「CI 綠」都要回 GitHub／git 重查。
> **歷史**：2026-11-03 Canonical Rule Convergence 批把舊版全文（543 行；含檔頭 40 則追加 checkpoint、24 個「第 N 次現況」框、舊下一步）逐字搬到 `docs/evidence/history/2026-11-03_handoff_pre_convergence.md`（**NOT CURRENT，不是現行規則或現況**）。更舊的交接本 `docs/handover_2026_09_26_latest.md` 為歷史紀錄（第 0 節永遠不准刪，客戶 2026-09-28 裁示）。本檔改寫依據：客戶 2026-11-03 指示（`DEC-2026-11-03-08`）；`PROJECT_RULES.md` 6.1.2「覆蓋、不累加」。

> **⏯ Resume Checkpoint**（總管提供；接手先依 `PROJECT_RULES.md` 6.1.2 比對 GitHub，不一致以 GitHub 為準；本區塊覆蓋舊版）
> - **查詢時點**：2026-11-04；最新 main 為 `b9595833`（本批整合 #1144 的基底；#1139 為 `66a09ed2`）；#1136（Shell 定字與降級首屏）先前合併為 `f07acd44`；main 現況與 Open／Draft PR 以 GitHub 為準；本批**未重查 GitHub**，接手先 `git fetch origin main`。
> - **Open／Draft PR**：以 GitHub 為準；接手先 `git fetch origin main` 並查 `gh pr list`。
> - **唯一下一接手點（單一）**：💼 我的資產：客戶已核准主圖在前、四格後置與 Missing（DEC-2026-11-04-01），並於 2026-11-04 核准 U1～U5 全部 UI 設計及缺 FX 方案 A（DEC-2026-11-04-02；82 §9.8）。接下來為 G-1～G-5 逐一 Decision Gate 與尚未解決的欄位／資料語意提案，由客戶裁示；獨立稽核後才能取得另批實作授權；**本次沒有授權 💼 程式**。
> - **2026-11-04 #1144 整合批**：客戶核准的 💼 U1～U5 全部 UI 設計與缺 FX 方案 A（`DEC-2026-11-04-02`；82 §9.8）已併入；#1142／#1143 已合併；僅 UI 設計核准，不授權 G-1～G-5 或 💼 程式；被覆寫的舊接手點句逐字搬至 `docs/evidence/history/2026-11-04_after_1144_handoff_superseded.md`（H9；NOT CURRENT）；基底 main `b9595833`，未重查 GitHub／CI。
> - **2026-11-04 #1140 整合批**：客戶核准的 💼 版面方向（主圖在前、四格摘要在後、缺值如實 Missing；僅 UI 順序，不授權 G-1～G-5 或 💼 程式）已併入 `DEC-2026-11-04-01`／82 §0.1；被覆寫的舊接手點句逐字搬至 `docs/evidence/history/2026-11-04_after_1139_handoff_superseded.md`（H8；NOT CURRENT）；基底 main `66a09ed2`，未重查 GitHub／CI。
> - **本批已落地**：#1135 的有效成果併入 `docs/v2/80`（第 7.4 節 🤖 導覽可見但不可點、不註冊頁面；第 16.1 節 Chart SPEC 位置）；#1135 的第 17.3／17.4 節與 HANDOFF 改動不併入（正式字樣只在 `shared/ui_semantics/rules.py::APPROVED_WORDING`）。Shell 定字、Status Bar 純文字、降級情境第一屏 ≤5 已隨 #1136 合併（`DEC-2026-11-03-11`；量測 `docs/evidence/bl0536_shell_h5_2026-11-03/`）。
> - **2026-11-04 #1138 整合批**：ChatGPT 的 💼 施工前草案 `docs/v2/82` 已併入（~~待客戶核准、非規格~~ 現況：U1～U5 UI 設計已核准〔`DEC-2026-11-04-02`〕、僅 UI；其餘仍待裁示；非規格）；三組獨立稽核（單組各自）已核實 §2／§4 並回修，結果在 82 第 8 節；稽核新增的待客戶問題與 Decision Gate 候選（G-1～G-5）登記於 `docs/BACKLOG.md` BL-0542；基底 main `21296a0d`，未重查 GitHub／CI。
> - **仍待驗證（不得宣稱已通過；`docs/BACKLOG.md` BL-0536 逐條）**：iOS／Android 實機、Safari、深色模式、Yahoo／FRED 真實連線、Streamlit 升版後導覽相容性、安全的資料更新入口（更新資料 CTA 停用中；不得為完成 Shell 開新 refresh pipeline）。
> - **待客戶確認（總管讀法，不裁決）**：圖下摘要行逐序列仍各列一項狀態，若稽核把帶 `data-status-key` 的元素都算名額，降級 390px 比較檢視仍為 7；替代方案＝彙總句加逐序列移入展開區（`docs/v2/81` 第 10.2 節）。Status Bar 與側欄狀態句內的「n／m 項已取得」不算頁級核心數字的讀法（若整句算一個名額，降級會是 6，須回 Gate）。
> - **已裁示、不再待裁**：🌍 首屏採 C 與用字統一（`DEC-2026-11-03-09`）；Shell 字樣、Status Bar 讀法、全取得不寫「正常」、降級首屏須 ≤5（`DEC-2026-11-03-11`）；#1135 文字修訂授權與 💼 階段分工（`DEC-2026-11-03-12`）。
> - **舊 Checkpoint 全文**（#1136 合併前版本；NOT CURRENT）：`docs/evidence/history/2026-11-04_after_1136_handoff_backlog_superseded.md`（H3）。

## 1. 必讀順序（新對話或換人接手）

1. `CLAUDE.md`（資料完整性憲法；`§-2`、`§-1.5`、`§-1` 位階最高）
2. `PROJECT_RULES.md`（專案 AI 工作規則入口；**0.4「現行規則索引」＝規則與頁面規格的唯一入口**）
3. 本檔
4. `docs/BACKLOG.md`（未完成工作主索引）
5. `docs/DECISIONS.md`（客戶裁示與正式決策）
6. 依任務讀對應 SSOT：New UI2 架構 `docs/v2/80`；各頁規格見 `PROJECT_RULES.md` 0.4 索引；子法 1 `docs/v2/CONSTITUTION.md` 須併讀修正案 #8 `docs/v2/57_amendment_8_directional_judgment.md`（`DEC-2026-10-16-14`）；例外與待判定登記簿 `EXCEPTIONS.md`。

**工作規則一律看 `PROJECT_RULES.md`，本檔不重述**：Silent Autonomous Cruise／No Progress Narration（第 3 節）、Model／Effort Change Gate 與 Hard-Stop（5.1）、Context Efficiency（11.1）、Minimum-Cost Correct Path（9.2）、正式 Streamlit 顯示規則與 cutover 檢查（13.2）、一般 merge commit 與不加 AI 署名（第 10 節）。

## 2. 現況（2026-11-04；以 GitHub 為準）

| 項 | 現況 |
|---|---|
| UI 三層邊界 | Old UI read-only；`ui_v2` maintenance-only；`ui_v3`＝New UI2 唯一未來正式（`DEC-2026-11-02-05`、`-06`）。正式 App 現況推定為 Old UI（Streamlit Cloud 設定，repo 內無法查證）；Preview App 平行驗收，尚未 cutover |
| 現行五頁 | 🌍 市場與趨勢／💼 我的資產／🔍 找基金／🤖 AI 投資總結（Phase 7 前導覽可見但不可點，不註冊頁面）／⚙️ 設定（`PROJECT_RULES.md` 13.2 第 1 點；程式側 `ui_v3/shell/registry.py`） |
| 🌍 | wireframe 已裁示（`DEC-2026-11-03-01`）；歸一化 A2／B2／C2、H1b／H2／H3、Preview rendering、九項正式字樣、首屏採 C 與用字統一、Navigation Shell＋H5（#1134）、Shell 定字與降級首屏收尾（#1136；`DEC-2026-11-03-11`）已合併（#1125～#1136；`DEC-2026-11-03-07`、`-09`、`-10`、`-11`）。詳情看 `docs/BACKLOG.md` BL-0536 與 `docs/v2/81` |
| 💼／🔍／⚙️／🤖 | 💼 已有 `docs/v2/82`（U1～U5 UI 設計已核准〔`DEC-2026-11-04-02`〕，其餘仍待裁示；ChatGPT 草案＋專案 AI 獨立稽核核實結果；不是現行規格、不授權 💼 程式；Gate 候選與待客戶問題見 `docs/BACKLOG.md` BL-0542）；🔍／⚙️／🤖 wireframe 尚未起草（順序 💼 → 🔍 → ⚙️；🤖 依 Phase 7）；核准前不寫該頁 `ui_v3` 代碼 |
| cutover | 未開始；強制驗收項 BL-0535 |
| 本機環境 | `ui_v2` 摘要守衛要用 Python 3.11 跑（CI 為 3.11）；`.claude/worktrees` 殘留會讓檔案引用守衛誤紅，需要時在乾淨 worktree 驗 |

## 2.1 背景 active work、不能自行做的事、主要風險

- **背景累積線**：BL-0509 EPS Data Source Probe 與 MoneyDJ NAV probe 照既有排程累積（預計 2026-10-28～2026-11-03），累積達標後一次回報客戶；現況以 `docs/BACKLOG.md` BL-0509 為準，不阻擋主線。

**不能自行做的事**（索引摘要，規則本文見 `PROJECT_RULES.md` 第 4 節與 13.2；不新增規則）：

1. 新增或替換 production 資料源／API、改正式公式、門檻或投資語意、改 data identity 規則——須停下請客戶裁示。
2. 改 frozen 文件（`docs/v2/44`、子法 1、57）、做 destructive migration、刪 Old UI 或 `ui_v2`、cutover 正式入口——須走 Gate。
3. 寫任一頁 `ui_v3` 代碼前，該頁 wireframe 須經客戶核准；UI 版面變更先出草稿。
4. 切換 Model／Effort 前送出 Gate 並停下，等客戶回覆「已切換／可以開始」。
5. 未經客戶明示不得 `git push --force`、重寫已推送歷史、直接 push main。

**主要風險**：

1. 正式 App 現況推定為 Old UI（Streamlit Cloud 設定，repo 內不可驗）；cutover 前須有 BL-0535 守衛綠燈與 URL／OAuth redirect 未變的紀錄。
2. 真實 Yahoo／FRED 連線未驗（環境限制）；Preview 截圖為注入資料，不是真實行情。
3. freshness 門檻未裁示（BL-0369），首屏只顯示 `⬜ 門檻待裁示`；不得自創新舊判定。
4. 本批收斂內容未經客戶確認 Latest-Rule-Only 讀法（BL-0538），否決時須自 `docs/evidence/history/` 還原。
5. 規則收斂僅第一階段，`PROJECT_RULES.md` 與 `docs/v2/81` 仍有劃線舊句（BL-0541）。
6. 本批併入 main `d6173220` 時，main 在 `82ba783f` 後新增的 HANDOFF 兩則與 BACKLOG BL-0536 列（`d6173220` 版）已逐字搬 `docs/evidence/history/2026-11-03_main_after_82ba783f_superseded.md`（區塊 H2、B2）。

## 3. 待客戶裁示（Decision Gate；本檔只列 ID，內容與推薦看 `docs/BACKLOG.md`）

| ID | 題目 |
|---|---|
| BL-0538 | Latest-Rule-Only 讀法與 0.5 改寫的客戶確認（G-1；總管讀法採方案 B，待確認） |
| BL-0540 | Missing 字樣並存（`資料不足`／`此圖目前沒有可畫的資料`／`◇ 資料未備`）是否取代或並存（G-2）；🤖 輸出「六項」對映六段／四區（G-5）；資料健康度集中 ⚙️ 與 frozen 44 的承接（G-3，需 amendment） |
| BL-0542 | 💼 稽核新增的待客戶問題與 Gate 候選（G-1～G-5；內容看 BACKLOG 與 `docs/v2/82` 第 6.1 節）；82 之 U1～U5 UI 設計已核准（`DEC-2026-11-04-02`），G-1～G-5 與其餘 Q 仍待裁示 |
| BL-0369 | freshness 門檻（BL-0536-H4）；未裁示前首屏只顯示 `⬜ 門檻待裁示` |
| BL-0537 | Old UI／`ui_v2` 凍結清單機械守衛 |
| 其他 | 見 `docs/BACKLOG.md` §4 快速索引〈待客戶裁示〉 |

## 4. 新對話 takeover

1. `git fetch origin`；`git log -1 --format='%H %P' origin/main` 與第 2 節比對，不一致以 GitHub 為準並先更新本檔。
2. 查 open PR 與 main 最新 push 的三條 CI job 逐條 `conclusion`。
3. 依第 1 節順序讀文件；待辦查 BACKLOG，裁示查 DECISIONS，舊脈絡查 `docs/evidence/history/`（歷史，不是現行）。
4. 確認 working tree 乾淨、無殘留 worktree，再接上方 Resume Checkpoint 的接手點；有不一致或新發現依 `PROJECT_RULES.md` 第 12 節落盤，不只留在聊天。

## 5. 本檔沒查證的部分

- main `21296a0d`（含 #1136、#1138）為工作樹基底，**未重查 GitHub／CI**；#1134、#1136 已合併為 git log 所見，CI 結果未查。本批的量測為 Chromium＋注入的人造資料，真實連線、Safari、實機、深色模式未驗；降級名額守衛是 DOM 計數（AppTest 不載入 CSS），可視計數以 Playwright 為準。
- 第 3 節 BL-0538～BL-0540 為本批新登記，內容單組寫成、未經第二組驗證。
- 舊版 HANDOFF 內「未查證」各條（約 60 條，多為 2026-10 月批次紀錄）隨全文搬至歷史檔，**不再是現行聲明**。
