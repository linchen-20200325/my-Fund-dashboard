# HANDOFF — 現行交接（單一現況；每次覆蓋、不累加）

> **用途**：只回答六件事：現在在哪、active work、最新 main／PR／CI checkpoint、下一接手點、blocker／待客戶裁示、新對話從哪開始。**本檔不得單獨作為完成或正確的證明**（`PROJECT_RULES.md` 1.3）；任何「已合併」「CI 綠」都要回 GitHub／git 重查。
> **歷史**：2026-11-03 Canonical Rule Convergence 批把舊版全文（543 行；含檔頭 40 則追加 checkpoint、24 個「第 N 次現況」框、舊下一步）逐字搬到 `docs/evidence/history/2026-11-03_handoff_pre_convergence.md`（**NOT CURRENT，不是現行規則或現況**）。更舊的交接本 `docs/handover_2026_09_26_latest.md` 為歷史紀錄（第 0 節永遠不准刪，客戶 2026-09-28 裁示）。本檔改寫依據：客戶 2026-11-03 指示（`DEC-2026-11-03-08`）；`PROJECT_RULES.md` 6.1.2「覆蓋、不累加」。

> **⏯ Resume Checkpoint**（2026-11-06 台北；依 `PROJECT_RULES.md` 6.1.2 覆蓋舊版，接手須重查 GitHub）
> - **main**：`861628cc377352c4f651ddc1172e13ab07e4d90d`（本次合併時 `git rev-parse origin/main` 所見；CI 狀態需重查）。
> - **唯一下一接手點（單一）**：G-2 以 GitHub 實況為準；之後：等客戶另批授權（市值基準的 NAV／匯率組裝與 NAV 10 日門檻歸屬 Gate、⚙️ 登入／Active 入口、或 💼 頁 wireframe 與 ui_v3 接線；需 Effort Gate 與獨立稽核）。G-2 為最小 Preview 資料載入轉接層（`ui_v3/adapters/assets_source.py`；未接任何頁面或 renderer、守衛零變更），授權依據為客戶 2026-11-05 於對話中的指示（要點轉述、非逐字）；G-3～G-5、OneBrain／Phase 7 與 💼 程式照舊未授權。
> - **清理線狀態摘要**（專案級下一接手點不被清理線取代；證據只在 BL-0543、#1152～#1154 與 H14，不在此重述）：
>
> | PR | branch | 已記錄 head | 內容 | 狀態 |
> |---|---|---|---|---|
> | #1152 | `audit/code-data-boundaries-20261105` | `0a482e79` | 清理線：shadow 條件修正 | Draft；獨立 QA／逐條 CI 需重查 |
> | #1153 | `audit/static-reachability-tool-20261105` | `6e021744`（工具修補）；本分支另含 checkpoint 收斂，精確 head 以 GitHub 為準 | 靜態可達性盤點工具＋文件收斂；工具測試 5 passed、連同文件計數 71 passed（BL-0543 記錄） | 非 Draft；QA／逐條 CI 需重查 |
> | #1154 | `refactor/shared-masker-factory-20261105` | `74c1e98c` | 清理線：callback 相容性修正 | Draft；獨立 QA／逐條 CI 需重查 |
> | 規則 | — | — | 工具清單（1082 模組、664 候選）＝TRIAGE_ONLY_NOT_SAFE_TO_DELETE，**不是死碼確認**；無刪碼結論 | 刪碼須另經確認 |
> | 保護條件 | — | — | branch protection 讀取 HTTP 403、rulesets=[] | required checks **未驗證**，不得宣稱已確認或繞過 |
>
> 證據與範圍：BL-0543（`docs/BACKLOG.md`）；舊 checkpoint 與聲明逐字保全於 `docs/evidence/history/2026-11-05_cleanup_handoff_superseded.md`（H14，NOT CURRENT）。共用 aware datetime parser 僅為下一批候選，未動工。

## 1. 必讀順序（新對話或換人接手）

1. `CLAUDE.md`（資料完整性憲法；`§-2`、`§-1.5`、`§-1` 位階最高）
2. `PROJECT_RULES.md`（專案 AI 工作規則入口；**0.4「現行規則索引」＝規則與頁面規格的唯一入口**）
3. 本檔
4. `docs/BACKLOG.md`（未完成工作主索引）
5. `docs/DECISIONS.md`（客戶裁示與正式決策）
6. 依任務讀對應 SSOT：New UI2 架構 `docs/v2/80`；各頁規格見 `PROJECT_RULES.md` 0.4 索引；子法 1 `docs/v2/CONSTITUTION.md` 須併讀修正案 #8 `docs/v2/57_amendment_8_directional_judgment.md`（`DEC-2026-10-16-14`）；例外與待判定登記簿 `EXCEPTIONS.md`。

**工作規則一律看 `PROJECT_RULES.md`，本檔不重述**：Silent Autonomous Cruise／No Progress Narration（第 3 節）、Model／Effort Change Gate 與 Hard-Stop（5.1）、Context Efficiency（11.1）、Minimum-Cost Correct Path（9.2）、正式 Streamlit 顯示規則與 cutover 檢查（13.2）、一般 merge commit 與不加 AI 署名（第 10 節）。

## 2. 現況（2026-11-05；以 GitHub 為準）

| 項 | 現況 |
|---|---|
| UI 三層邊界 | Old UI read-only；`ui_v2` maintenance-only；`ui_v3`＝New UI2 唯一未來正式（`DEC-2026-11-02-05`、`-06`）。正式 App 現況推定為 Old UI（Streamlit Cloud 設定，repo 內無法查證）；Preview App 平行驗收，尚未 cutover |
| 現行五頁 | 🌍 市場與趨勢／💼 我的資產／🔍 找基金／🤖 AI 投資總結（Phase 7 前導覽可見但不可點，不註冊頁面）／⚙️ 設定（`PROJECT_RULES.md` 13.2 第 1 點；程式側 `ui_v3/shell/registry.py`） |
| 🌍 | wireframe 已裁示（`DEC-2026-11-03-01`）；歸一化 A2／B2／C2、H1b／H2／H3、Preview rendering、九項正式字樣、首屏採 C 與用字統一、Navigation Shell＋H5（#1134）、Shell 定字與降級首屏收尾（#1136；`DEC-2026-11-03-11`）已合併（#1125～#1136；`DEC-2026-11-03-07`、`-09`、`-10`、`-11`）。詳情看 `docs/BACKLOG.md` BL-0536 與 `docs/v2/81` |
| 💼／🔍／⚙️／🤖 | 💼 已有 `docs/v2/82`（U1～U5 UI 設計已核准〔`DEC-2026-11-04-02`〕，其餘仍待裁示；ChatGPT 草案＋專案 AI 獨立稽核核實結果；不是現行規格、不授權 💼 程式；Gate 候選與待客戶問題見 `docs/BACKLOG.md` BL-0542）；🔍／⚙️／🤖 wireframe 尚未起草（順序 💼 → 🔍 → ⚙️；🤖 依 Phase 7）；核准前不寫該頁 `ui_v3` 代碼 |
| G-2 資料轉接 | #1149 已隨 main `43b54f32` 合併，`ui_v3/adapters/assets_source.py` 未接頁面／renderer；仍不授權市值基準組裝移植與 UI 接線，詳見 BL-0542 |
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

- 真實 Cloud 外部入口、帳號、Secrets、Yahoo／FRED／Google／MoneyDJ 連線、外部排程、Safari／iOS／Android 實機與深色模式未驗；CI fixture 截圖不能冒充 production-like 驗收。
- 必要獨立 QA 與修復後各 head 的完整 CI 未結案；局部測試通過不等於三支 PR 可合併。
- 舊 checkpoint 的各次量測、未查證聲明與歷史基準已逐字保存於 H14，不再當成本輪最新事實；既有待裁事項仍查 `docs/BACKLOG.md`。
