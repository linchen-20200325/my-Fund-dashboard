# 品質補強 Batch 2 第 3 項｜Production 健康度分層驗收表（2026-11-13）

> **統一聲明**：本檔是研究／驗收設計證據落盤，**非客戶裁示、非授權施工**；基準 main `5e24f62fb0faa53891e8b159deabf3c75fd73a0d`（#1229 merge）；來源為 GitHub Issue #1228 Batch 2 第 3 項「Production 健康度驗收」，限縮範圍依客戶 2026-11-13 Batch 2 裁示（登記於 `DEC-2026-11-13-03`，要點轉述，非逐字；**Issue 是派工入口，不是授權狀態 SSOT**）。本檔為**單組作者草稿，尚待非作者 QA**；所有全稱句（「0 命中」「只有 N 處」「沒有任何」）皆為單組字面查詢，未經第二組驗證。
>
> **本檔是「分層驗收表」，不是第二份 data dictionary**：不新建欄位、Schema、狀態詞、門檻或 provider；不重做 #1225（`ui_data_contract_audit_2026_11_12.md`）、#1227、#1229（`quality_batch1_delta_2026_11_13.md`）已合併成果，只引用並補「production 健康度」分層。
>
> **本批嚴格唯讀**：未連任何 live 資料源、未探 Streamlit Cloud／Google Sheets／NAS、未觸發任何 workflow／探針、未碰憑證、未印 secret／NAS／Sheet ID。GitHub 資料僅經唯讀查詢（Actions 的 workflow 清單、run 清單、單一 run 的 job／step 結論）；**未讀任何 job log 內文**。不解除 D2／FX／DG2／BL-0545 Gate。「推薦」「讀法」一律是專案 AI 讀法，可被客戶推翻。BL-0545 仍是唯一全域 NEXT（BLOCKED），本批不取代它。
>
> **量測日 2026-11-13（Asia/Taipei）**。GitHub run 數字是查詢當下的快照，會漂移；引用前請重查（§2 各層附唯讀重現指令）。

## 0. 一頁結論（先讀）

1. 「健康」不是一個值。本檔把它拆成五層，**彼此不得冒充**：L1 CI／AppTest、L2 NAV 更新（排程執行）、L3 涵蓋率／freshness、L4 Sheet 可用性、L5 New UI2 五頁正式資料。
2. **目前有證據的只有 L1 與 L2 的「執行層」**：main `5e24f62f` 的 push CI 四個 job 結論皆 `success`；NAV／總經／匯出三條排程近期皆 `success`。這些只證明「工作有跑、結論為何」。
3. **L3 部分、L4 與 L5 的「資料正確／可用／已驗收」皆 NOT VERIFIED**：沒有任何 live 合法證據；BL-0545 真實覆蓋率 BLOCKED（等使用者自願提供合法輸入，不得要求憑證）；`FX_OBS_DATE_RULE_VERIFIED=False`；New UI2 五頁 S4（正式資料已驗證）全為 NOT VERIFIED、S5（使用者已驗收）全為否（引用 Batch 1 §2.1）。
4. **探針成功不等於正式來源核准**；workflow `success` 不等於資料正確；CI `success` 不等於 production 正常；`data_cache` 存在不等於已驗證（§3）。
5. 本檔不新增門檻：各資料域「多久算舊」在 New UI2 皆未核准（首屏為 `⬜ 門檻待裁示`），下一步只能由客戶裁示，專案 AI 不自創數字。

**不得冒充清單（任何一句出現在報告／PR／HANDOFF 都應退回）**：

| 禁止寫法 | 為什麼 | 正確寫法（範例） |
|---|---|---|
| 「production 健康」「系統正常」 | 五層只有 L1／L2 有執行層證據 | 「L1：main `5e24f62f` 四 job success；L2：近 N 次排程 success；L3～L5 NOT VERIFIED」 |
| 「NAV 已更新到 ○○」 | 排程 `success` 不證明寫入列數、不證明淨值正確 | 「`weekly_nav_backfill` 近 6 次 schedule conclusion=success；寫入內容 NOT VERIFIED（未讀 log、未讀 Sheet）」 |
| 「探針通過所以來源可用」 | 探針是研究證據，`DEC-2026-11-09-10` 等明文不核准 | 「探針 run ○○ 執行結論 success；是否核准為正式來源：未核准」 |
| 「資料新鮮／過期」 | New UI2 的新鮮度門檻未核准 | 「最新觀測日 ○○；門檻待裁示（`DEC-2026-11-03-01` Q5 B）」 |
| 「Sheet 可用」 | 無任何合法 live 證據 | 「NOT VERIFIED（BL-0545 BLOCKED）」 |
| 「New UI2 五頁已上線」 | 僅 🌍 有 `ui_v3` Preview-only；`app.py` 不 import `ui_v3`／`ui_v2` | 「🌍 Preview-only；其餘四頁 `ui_v3` 無頁；皆非 production」 |

## 1. 五層驗收總表

狀態詞只用：**已有證據／部分／NOT VERIFIED／BLOCKED**。「已有證據」一律附「限於 ○○」。

| 層 | 被驗收的是什麼 | 何者算通過證據（allowed evidence） | 何者明確不算證據 | 現況（GitHub 唯讀實查，量測日 2026-11-13） | 狀態 | 負責人與下一個合法動作 | 相關 Gate |
|---|---|---|---|---|---|---|---|
| **L1 CI／AppTest** | 程式在 CI 環境（Python 3.11）下，Fast／Schema（阻擋合併）與 Slow／Visual（資訊性）的測試是否通過 | 同一 head 的 **job／step conclusion**；對 informational lane 需再讀 step log 末行（pytest 摘要）；本機實跑須註明 Python 版本與缺件 | 本機 Python 3.13 結果；PR head 的結論拿來冒充 main；run 層級 conclusion 單獨引用；`mergeable=true`；branch protection 讀取 403 → required checks NOT VERIFIED | main push CI run `43353067763`（head `5e24f62f`，2026-11-13 02:34Z 起）：Fast／Schema／Slow／Visual 四 job `conclusion=success`；Slow 的 `Run AppTest (slow lane)` step 約 26 分 47 秒、Visual 的 `Capture CI fixture screenshots + layout checks` step 約 1 分 34 秒皆 `success`；Visual 的 `Cloud capture` 兩 step `skipped`（僅手動 dispatch 才跑）。**pytest 通過／略過數量本檔未讀（NOT READ）** | 部分（job／step 結論有；測試數量與內容未讀） | 專案 AI：每次引用前重查最新 head；Slow／Visual 結論寫「informational」。客戶：無待辦 | 無（但 branch protection API 403，required checks NOT VERIFIED） |
| **L2 NAV 更新（排程執行）** | 排程 workflow 是否有被執行、結論為何 | workflow run 的 `event=schedule`、`conclusion`、`created_at`；失敗時 LINE 推播步驟是否被觸發（需讀 step 結論） | 把 `success` 讀成「資料已更新／正確」；把排程執行讀成「來源已核准」；`data_cache` commit 存在 | `weekly_nav_backfill`（#84～#89，2026-11-07～11-12）6 次皆 schedule＋`success`；`export_db`（#112～#116，11-09～11-13）5 次皆 `success`；`update_macro_history`（#24～#28，10-11～11-08 每週日）5 次皆 `success`，最新 commit `8ca33547`（2026-11-08T04:07:01Z，bot）；總 run 數 89／116／28 | 部分（限執行層） | 專案 AI：如需寫入內容證據，須先取得客戶授權才可讀 Sheet／log。客戶：無待辦 | 無（寫入內容屬 data semantics，不在本批） |
| **L3 涵蓋率／freshness** | 各資料域的最新觀測日、缺漏、涵蓋率分母、新鮮度門檻 | 離線可重現的檢查（A1 報告，基於 commit `8ca33547` 的 `data_cache`）；**已核准**的門檻值；BL-0545 在合法輸入下量得的三層分母 | A1 腳本內部啟發式門檻（如 `gap_factor`、46.5 天）當成核准門檻；`metadata.json` 的 `last_updated`（共同最大日期）冒充各 series 最新日；樣本冒充個人持倉；任何自創門檻 | `data_cache/metadata.json` `updated_at` 2026-11-08T04:07:01Z；fred_indicators `last_updated` 2026-11-05（13,829 列）；spx／vix／twii `last_updated` 2026-11-06。A1 報告（2026-11-10）：3 筆 CONFIRMED、14 筆 SUSPECTED、0 筆 INSUFFICIENT_EVIDENCE。New UI2 新鮮度門檻**全數未核准**；BL-0545 真實覆蓋率 NOT VERIFIED；`FX_OBS_DATE_RULE_VERIFIED=False` | 部分（離線檢查有；門檻與覆蓋率 NOT VERIFIED） | 客戶：新鮮度門檻（#1225 G4）、FRED P1 G2／G3／G4、Actions→Cache→New UI 接線（`DEC-2026-11-10-04` G1～G6）裁示。專案 AI：只能等裁示 | #1225 G4／BL-0369；FX 閘門；BL-0545；D2 |
| **L4 Sheet 可用性** | 使用者個人 Active Sheet 與 Settings Sheet（四表）在真實環境下可讀寫／結構正確 | 合法 live 證據（使用者本人 session，或自願提供的匿名清單／截圖）且驗的是**該表本身** | Actions 服務帳號對選股池／NAV／政策 Sheet 的排程結果（不同主體）；離線 fixture；客戶口述「已設定」；`ui_v2` 測試通過 | **無任何合法 live 證據**。BL-0545 Phase 1 探針已合併但 live 模式 NOT IMPLEMENTED；使用者目前明示暫不提供輸入 | NOT VERIFIED；BL-0545 子項 **BLOCKED** | 客戶：自願選擇方式 A（本人合法登入 session）或方式 B（匿名基金代碼清單）才可能產生證據；**專案 AI 不得要求憑證、不得探 live** | BL-0545；`DEC-2026-11-07-03`；`docs/v2/50` 四表契約 |
| **L5 New UI2 五頁正式資料** | 🌍／💼／🔍／🤖／⚙️ 在 production 以正式資料呈現並經使用者驗收 | S4：可追溯的真實來源／真實 Sheet／Streamlit Cloud 驗證且驗的是該列本身；S5：客戶明示「驗收通過」紀錄 | fixture／合成 stub、一次性探針、離線快取檢查、Preview 畫面、AppTest 綠、`ui_v2` 完成率冒充 `ui_v3` | 引用 Batch 1 §2.1：五頁 S4 皆 NOT VERIFIED、S5 皆否；`ui_v3` 僅 🌍 為 Preview-only，💼／🔍／⚙️ 無頁、🤖 僅佔位；`app.py` 對 `ui_v3`／`ui_v2` 0 命中；Streamlit Cloud 入口設定 repo 內查不到 | NOT VERIFIED | 客戶：cutover（BL-0535）與 G7（Cloud／WebView／真機）go；專案 AI 不自行接線 | BL-0535、BL-0544、BL-0545、D2、FX、DG2 |

## 2. 各層細節

### 2.1 L1 CI／AppTest

**四條 lane（讀自 `.github/workflows/pr-check.yml`，基準 `5e24f62f`）**：

| lane（job 名） | 內容 | 阻擋合併 | Python | 近期實查（run `43353067763`） | 證明什麼 | 不證明什麼 |
|---|---|---|---|---|---|---|
| Fast checks | `pre-commit run --all-files`（含 `pytest -m "not slow"` 的 smoke hook） | 是 | 3.11 | job `success`；pre-commit step 02:34:41Z→02:48:14Z（約 13 分 33 秒；job 名稱寫「~30s」已與實況不符，僅事實登記） | 同 head 的 fast 子集通過、hook 通過 | 測試**數量**（hook 不印）；Slow 標記的測試；Playwright 級斷言 |
| Schema gate | pandera schema 測試檔（`test_schemas_phase_*`） | 是 | 3.11 | job `success`；step 約 3 秒 | 6 個 schema 測試檔在 CI 通過 | 真實資料符合 schema（用的是合成資料） |
| Slow tests（AppTest） | `pytest -v -m "slow"`，含 Chromium 安裝與啟動 smoke check | **否**（job 級 `continue-on-error: true`，informational） | 3.11 | job `success`；Chromium 安裝／smoke／`Run AppTest (slow lane)` step 皆 `success` | 該 head 的 slow 標記測試在 CI 執行完且 step 成功 | 不證明 production；**job 失敗時 run 層級也可能顯示 success**；摘要行未讀 |
| Visual Fidelity safety net | `tests/visual_fidelity/test_ci_fixture_screenshots.py` | **否**（`continue-on-error: true`，informational） | 3.11 | job `success`；`Cloud capture` 兩 step `skipped` | CI fixture 截圖與 layout 檢查可執行 | 截圖對象是 **`ui_v2` fixtures、標示 NOT production-like**；不涵蓋 `ui_v3`；不是 Cloud 畫面 |

**要記的事實（引用 Batch 1，不重驗）**：
- **本機 Python 3.13 與 CI Python 3.11 的差異**：Batch 1 §1.2-6 實驗確認 8 條黃金／摘要測試（alo golden 2＋mutations 1、hld 兩檔 4、rulings 1）在 3.12 起紅燈，**根因是 CPython 3.12 起 float `sum()` 改補償加總**；3.11 同矩陣逐位元組相同。**不是 baseline 漂移、不是程式退化；禁止重錄 Golden**（BL-0342、BL-0453 的出處欄已追加線索）。
- **production Python 版本 repo 內查無 pin**（`runtime.txt`、`.python-version` 皆不存在，本檔 `ls` 實測）；Streamlit Cloud 實際版本 NOT VERIFIED。
- **run 層級 `success` ≠ 四條 lane 全綠**：Slow／Visual 為 `continue-on-error`；歷史上有「runner apt DNS 失敗、Slow／Visual 記為 NOT RUN」的實例（PR #1215 合併訊息自陳；本檔僅轉述 commit 訊息，未重驗）。

**通過證據的最小寫法**：`main <sha>` 的 run `<id>` 四 job conclusion 逐條；Slow／Visual 另標 informational；若未讀 step log 末行，一律寫「測試數量 NOT READ」。

**唯讀重現（GitHub CLI／MCP，皆只讀）**：
```
gh run list --workflow pr-check.yml --branch main --event push -L 3 --json databaseId,headSha,conclusion,createdAt
gh api repos/<owner>/<repo>/actions/runs/<run_id>/jobs --jq '.jobs[]|{name,conclusion,steps:[.steps[]|{name,conclusion}]}'
```

### 2.2 L2 NAV 更新（排程執行）

**逐 workflow 表**（來源：各 workflow 檔頭與設定；run 資料為 GitHub 唯讀查詢，量測日 2026-11-13）：

| workflow（檔） | 排程／觸發 | 寫入目標 | 最近結論（schedule 觸發） | **這證明什麼** | **不證明什麼** |
|---|---|---|---|---|---|
| 每日 NAV 自動補齊（`weekly_nav_backfill.yml`） | cron `0 12 * * *`（UTC）；另有 `workflow_dispatch`（`dry_run` 預設 true）；排程觸發為實抓實寫（workflow 註解明寫），僅手動 dispatch 的 dry_run 預設 true | 雲端 `nav_history`（Google Sheet，以 GitHub secrets 存取；本檔不印 ID）；步驟含 `POOL_SHEET_ID` 非空檢查、失敗時 LINE 推播 | #89（11-12T19:38Z）、#88（11-11T19:20Z）、#87（11-10T19:25Z）、#86（11-09T22:00Z）、#85（11-08T17:43Z）、#84（11-07T17:32Z）皆 `success`；每次約 4～7 分鐘 | 排程有跑；`POOL_SHEET_ID` 檢查通過；腳本結束碼 0 | 實際 append 列數（週末／假日 no-op 為正常）；淨值正確；幣別守衛是否攔截；覆蓋率；來源是否已核准。**觀察**：實際 `created_at` 較 cron 12:00Z 晚約 5.5～10 小時，原因 NOT VERIFIED，不得據此推斷「當日淨值已確定」 |
| 匯出 fund.db（`export_db.yml`） | cron `0 21 * * *`（UTC） | 把 `data_cache` parquet 匯成 fund.db，force-push 到 `data` 分支（單 commit） | #116（11-13T01:42Z）、#115、#114、#113、#112 皆 `success` | 匯出步驟執行成功 | 輸入是**已 commit 的 `data_cache`**（每週才更新一次），故每日 success **不代表 fund.db 內容每日更新**；下游是否消費 NOT VERIFIED |
| 全球總經歷史快取（`update_macro_history.yml`） | cron `0 0 * * 0`（週日 UTC）；`workflow_dispatch`（含 bootstrap） | 增量寫回 `data_cache/`（bot commit）；需 `FRED_API_KEY`（secret，本檔不碰） | #28（11-08T04:06Z）、#27（11-01）、#26（10-25）、#25（10-18）、#24（10-11）皆 `success`；最新 commit `8ca33547` | 每週有跑並有 commit | **success ≠ 各 series 都有增量**：A1 報告顯示 `CPIAUCSL`、`M2SL` 最新停在 2026-04-01（SUSPECTED，落後共同最大日期 218 天）、`PPIACO`／`PCOPPUSDM` 宣告卻零列（CONFIRMED）；`DEC-2026-11-10-01` ② 對成因的是專案 AI 推論（INFERENCE）；BL-0220：該 workflow 的 `PROXY_URL` 對 `infra.proxy` 無效（僅登記） |
| 補選股池 currency（`fill_pool_currency.yml`） | 僅 `workflow_dispatch`（一次性維護，預設 dry_run） | 選股池 Sheet 的 currency 欄 | **本檔未查 run**（NOT VERIFIED） | — | 非週期性健康指標，不應納入「最近一次成功」判讀 |
| 追蹤清單驗證（`watchlist_verify.yml`） | 僅 `workflow_dispatch` | 無寫入（dry-run、不送 LINE） | 本檔未查 | — | 同上 |
| 換股顧問健康週報（`weekly_switch_notify.yml`）／除息行事曆月底摘要（`dividend_calendar_notify.yml`） | cron 週日 `0 10`／每月 28 日 `23 0`（UTC） | LINE 推播 | 前者 #17（11-08T16:29Z）等 3 次 `success`；後者 #11（10-28T05:54Z）等 `success` | 推播工作有跑 | **LINE 推播成功 ≠ 資料新鮮 ≠ 內容正確**；屬通知層，不屬 NAV 健康證據 |

**通過證據的最小寫法**：「`<workflow>` 最近 N 次 `event=schedule` 皆 `conclusion=success`（run id 範圍 ○○～○○）；寫入內容／正確性／來源核准 NOT VERIFIED」。若有任一次 `failure`／`cancelled`／`skipped`，**逐次列出並標原因 NOT READ**，不得以「多數成功」帶過。

**唯讀重現**：
```
gh run list --workflow weekly_nav_backfill.yml --event schedule -L 7 --json databaseId,conclusion,createdAt,headSha
git log -5 --format='%h %cI %an %s' -- data_cache/metadata.json
```

### 2.3 L3 涵蓋率／freshness（門檻核准狀態）

**原則**：本表只登記「現況是什麼」與「門檻是否已核准」，**不提議任何門檻數字**。Old UI 的舊門檻（`CLAUDE.md` §2.4 引 SPEC §2）是 Old UI 的歷史規則，**不等於 New UI2 已核准**；#1225 G4 明確建議「若裁，逐源以發布頻率證據論證，不用舊樹 22／30 當預設」。

| 資料域 | 現況（量測日 2026-11-13，基準 `data_cache` @ `8ca33547`） | 新鮮度門檻是否已核准（New UI2） | 相關裁示／限制 | 狀態 |
|---|---|---|---|---|
| Yahoo 指數（spx／vix／twii 快取） | `last_updated` 2026-11-06；列數 3,879／3,881／3,762。A1：2026-06-03 的 `^GSPC` 7595.98 vs 參考 7553.68、`^VIX` 16.26 vs 16.06 **與探測參考不同**（CONFIRMED，僅證實「與此參考不同」，不判成因）；該兩列首見提交落在美股盤內（SUSPECTED `intraday_freeze`）；另有週日列、與前一列同值列（SUSPECTED，不單獨足以判異常） | **否**（首屏 `⬜ 門檻待裁示`；`DEC-2026-11-03-01` Q5 B；#1225 G4；BL-0369） | `DEC-2026-11-09-10`：週末排除維持現行（不擴大為已驗證交易日規則）、收盤判準**暫行**、06-03 證據保留；不核准正式收盤判準／交易日曆 | 部分（離線檢查有；門檻 NOT VERIFIED） |
| FRED（fred_indicators） | `last_updated` 2026-11-05；13,829 列；快取 9 個 series（宣告 11）；`CPIAUCSL`、`M2SL` 停在 2026-04-01；`UNRATE` 缺 2026-05-01；`DTWEXBGS` 僅 21 列；`PPIACO`、`PCOPPUSDM` 零列（CONFIRMED） | **否**（逐源門檻未裁） | FRED P1 G2／G3／G4 未授權；`DEC-2026-11-10-05` 純離線驗證、不授權正式修復；`DEC-2026-11-10-03` 資安最小修補已完成；Cloud 端 `FRED_API_KEY` 狀態 NOT VERIFIED（`secrets_recovery_verification_2026_11_10.md`） | 部分（離線事實有；門檻與 Cloud 端 NOT VERIFIED） |
| NAV（`nav_history` Sheet） | 排程執行層見 §2.2；**repo 內沒有可讀的最新淨值日度量**（本批不讀 Sheet）。NAV 為 T+1～T+3 公布，週末／假日無新值為正常（`CLAUDE.md` §1 脈絡），不得 ffill | **否**（New UI2 無核准的 NAV 新鮮度門檻；D2 R-NAV-1 核准欄位數＝0） | `DEC-2026-11-13-01`：D2 最小核准包僅 R-ID-1／R-NAV-1，核准數仍為 0 | NOT VERIFIED |
| FX（USDTWD） | `FX_OBS_DATE_RULE_VERIFIED=False`（`services/v2_tables/market_indicator.py` 常數）；冬令探測 run `42455423910`（2026-11-08）證據不足以開閘；Batch 1 Δ3-03：FX 對齊無新鮮度上限、不讀 `value_unit` | **否**（FX 閘門關閉） | `DEC-2026-11-08-02`：閘門維持關閉、不立即以相同方法重跑；D8 補跑未授權 | NOT VERIFIED |
| 持倉覆蓋率（五維健康評級三層分母） | `scripts/bl0545_coverage_probe.py` 離線／匿名清單模式已合併，live 模式 NOT IMPLEMENTED；正式 admission NOT DEFINED | **否**（分母與准入未定義） | BL-0545 BLOCKED；`DEC-2026-11-07-03` | **BLOCKED** |
| TWSE／MOPS EPS（BL-0509） | shadow research，探針每日兩次排程累積樣本（`twse_eps_probe.yml`）；不接正式 signal | 否（研究專用） | `DEC-2026-10-27-37`／`-41`；升格正式來源才需裁示 | 部分（研究證據；非正式） |

**Actions→Cache→New UI 接線差距**（Actions 寫入的快取是否被 New UI 讀取、是否「優先由 Streamlit 讀已驗證快取」）屬 `DEC-2026-11-10-04` 的 G1～G6，**待客戶**；本檔不判定、不推薦切換 production。

**唯讀重現**：
```
python3 -c "import json;d=json.load(open('data_cache/metadata.json'));print(d['updated_at'],{k:(v['last_updated'],v['row_count']) for k,v in d['datasets'].items()})"
python scripts/check_cache_quality.py --no-git --format md --as-of 2026-11-13      # A1 離線唯讀；需 pyarrow；不寫 cache、不連網
```
（`--git-all-refs` 與 `--reference` 的完整重現見 `cache_quality_check_a1_report_2026_11_10.md` §2；A1 對盤中凍結的證據需完整 git 歷史，淺層 clone 會標「證據不足」。）

### 2.4 L4 Sheet 可用性

| Sheet 類別 | 現有證據 | 為何 NOT VERIFIED | 何時才可能有合法證據 | 專案 AI 的邊界 |
|---|---|---|---|---|
| 使用者個人 Active Sheet（持倉等，OAuth 本人 session） | 無 | 專案 AI 沒有、也不得索取使用者 session／token；BL-0545 live 模式 NOT IMPLEMENTED；使用者明示暫不提供輸入 | 使用者自願選方式 A（本人合法登入 session 由使用者本人執行探針）或方式 B（匿名基金代碼清單）之後 | 不得請求憑證、不得探 live、不得虛構覆蓋率百分比；樣本不得冒充個人持倉 |
| Settings Sheet（`SETTINGS_SHEET_ID`；`docs/v2/50` 四表：`user_setting_log`、`market_indicator`、`fetch_log`、`fetch_log_open`） | 僅 `ui_v2` 邏輯／AppTest（合成）；Batch 1 §2：⚙️ S4＝NOT VERIFIED（標頭／列數／值域在 Cloud 皆無真實證據） | 無法由 repo 內證據判斷真實 Sheet 現況 | 需客戶授權的合法唯讀檢查（形式由客戶決定）；本檔**不提議**新增取證方式 | 不得讀寫、不得新增分頁或 Schema；`docs/v2/83` 的候選監控 Sheet 屬另案、未授權 |
| （附帶）選股池／NAV／政策 Sheet 經 Actions 服務帳號讀寫 | `weekly_nav_backfill` 的 schedule `success` 只是 L2 執行層的**間接線索** | 服務帳號 ≠ 使用者 Active Sheet；本批未讀 log 或 Sheet；Streamlit Cloud 端存取 NOT VERIFIED | — | 不得把此線索升格為 L4 證據 |

### 2.5 L5 New UI2 五頁正式資料（引用 Batch 1 §2.1，不重驗）

| 頁 | S1 規格已核准 | S2 技術已實作 | S3 同 head 測試 | **S4 正式資料已驗證** | **S5 使用者已驗收** | production 入口 |
|---|---|---|---|---|---|---|
| 🌍 市場與趨勢 | 部分 | 是（`ui_v3` **Preview-only**） | 是（Batch 1 R1：`tests/ui_v3` 878 passed、84 skipped〔無 playwright〕；CI 四 lane success） | **NOT VERIFIED**（測試全用合成 stub） | 否 | 否 |
| 💼 我的資產 | 部分 | `ui_v3` 無頁（僅 adapter、0 production caller）；`ui_v2` 有 | 部分 | **NOT VERIFIED** | 否 | 否 |
| 🔍 找基金 | 部分 | `ui_v3` 無頁；`ui_v2` 篩選器有；lookup／ISIN／身份 0 實作 | 部分 | **NOT VERIFIED** | 否 | 否 |
| 🤖 AI 投資總結 | 部分 | `ui_v3` 僅佔位（`ActionSlot` 0 頁消費） | 部分 | **NOT VERIFIED／—** | 否 | 否 |
| ⚙️ 設定 | 部分 | `ui_v3` 無頁；`ui_v2` 有 | 部分 | **NOT VERIFIED** | 否 | 否 |

Batch 1 §2.1 的原句同樣適用於此：**頁級彙總中任何一格的「是」都不得外推到該頁其他列**；🌍 的 S3「是」不等於 S4。Streamlit Cloud 正式入口 repo 內查不到（#1225 D15）。

## 3. 誤讀與冒充風險（每項附出處）

### 3.1 探針成功 ≠ 正式來源核准

| 探針 workflow | 觸發 | 近況（唯讀實查） | 對應 DEC／BL | 它證明什麼 | **它不證明什麼（明文）** |
|---|---|---|---|---|---|
| `fx_obs_date_probe.yml` | 手動／按鈕分支，無排程 | 共 4 次；最新 run `42455423910`（2026-11-08T06:36Z）`success` | FX 閘門 `DEC-2026-11-08-02`；證據 `fx_obs_date_winter_probe_2026_11_08.md`、`probe_fx_obs_date/` | Yahoo 匯率日線觀測日的一次取樣 | 證據不足以開閘；`FX_OBS_DATE_RULE_VERIFIED` 維持 `False`；D8 補跑未授權 |
| `moneydj_basic_probe.yml` | 手動／按鈕分支 | 共 1 次；run `38548232056`（2026-10-14）`success` | 證據 `probe_moneydj_basic/`；workflow 檔頭未標 DEC／BL | MoneyDJ 基本資料頁真實樣本 | 不啟用 ISIN→MoneyDJ 對照（BL-0530 research-only、`DEC-2026-11-01-02` G-E1） |
| `moneydj_nav_equivalence_probe.yml` | 手動／按鈕分支／排程（cron `17 13 * * 1-5` UTC） | 共 13 次；最新 run `43304039696`（2026-11-12T20:49Z）`success` | `DEC-2026-10-29-02`／`-03`；證據 `probe_moneydj_nav/` | MoneyDJ NAV 等價性比對的取樣 | 排程持續 `success` 不是「NAV 來源已核准」；NAV 來源仲裁屬 identity／data semantics Gate |
| `twse_eps_probe.yml` | 手動／按鈕分支／兩個固定排程（UTC `37 11 * * 1-5` 與 `43 22 * * 1-5`，即台北 19:37 與隔日 06:43） | 共 26 次；最新 run `43355258917`（2026-11-13T02:53Z）`success` | BL-0509；`DEC-2026-10-27-37`／`-41` | TWSE／MOPS 公開端點可達性與欄位 | 研究／shadow；不得接正式 signal、AI Brain；`actual` 不得冒充 forward |
| `yahoo_indices_sp_probe.yml` | 手動／按鈕分支，一次性授權（最多 4 次 HTTP） | 共 1 次；run `42656242596`（2026-11-09T16:35Z）`success` | `DEC-2026-11-09-08`；結果登記 `DEC-2026-11-09-10`（Q1～Q5） | Yahoo 三指數日線的描述性取樣 | `DEC-2026-11-09-10`③：不核准 Eligibility、母集合、分母、日期轉換、正式收盤判準、交易日曆、新來源 |

補充：探針 `success` 只表示腳本跑完、結束碼為 0；「探到什麼」要看結果分支 `probe/*-results` 的報告（**本批未讀**，且 `DEC-2026-11-08-01` 要求這些分支全部保留）。探針 workflow 持有 `contents: write` 僅為推結果分支；從其他分支手動觸發會跑 main（`fx_obs_date_probe.yml` 檔頭，已讀）。

### 3.2 其他冒充風險

| # | 容易被讀成 | 實際上 | 出處 |
|---|---|---|---|
| 1 | workflow `success` ＝ 資料正確 | `update_macro_history` 近 5 週皆 success，A1 卻同時報告多個 series 停更／零列 | §2.2；`cache_quality_check_a1_report_2026_11_10.md` §3 |
| 2 | CI `success` ＝ production 正常 | CI 在 Python 3.11 的 fixture 環境；production Python 版本 NOT VERIFIED；run 層級 success 含 informational job | §2.1；Batch 1 §1.2-6 |
| 3 | `data_cache` 存在或 `metadata.json` 有值 ＝ 已驗證 | `DEC-2026-11-10-04` ②明文：「把快取存在視為已驗證」不授權；`last_updated` 是共同最大日期，不是各 series 最新日 | `DEC-2026-11-10-04`；A1 報告 |
| 4 | Preview／AppTest 綠 ＝ production | 🌍 `ui_v3` 為 Preview-only；`app.py` 不 import `ui_v3`；Cloud 入口 NOT VERIFIED | Batch 1 §2.1；#1225 D15 |
| 5 | Visual lane 綠 ＝ New UI2 畫面驗收 | 截圖對象是 `ui_v2` fixtures，標示 NOT production-like | `pr-check.yml` Visual 步驟名稱；Batch 1 §2.0 S3 |
| 6 | 本機 3.13 紅燈 ＝ 程式退化 | 8 條為 3.12 `sum()` 補償加總的版本差異；禁止重錄 Golden | Batch 1 §1.2-6；BL-0342／BL-0453；BL-0548 ① |
| 7 | 每日 `export_db` success ＝ fund.db 每日更新 | 輸入是每週更新的 `data_cache` | `export_db.yml` 檔頭；`update_macro_history.yml` |
| 8 | LINE 推播成功 ＝ 資料新鮮 | 通知層，不證明內容 | `weekly_switch_notify.yml`／`dividend_calendar_notify.yml` |
| 9 | 排程 `schedule` 在當天 ＝ 當日淨值已確定 | 觀察到實際啟動時間晚於 cron 5.5～10 小時，原因 NOT VERIFIED；NAV T+1～T+3 | §2.2；`CLAUDE.md` §1 |
| 10 | A1 的 CONFIRMED／SUSPECTED ＝ 正式健康狀態或 Schema | 腳本內部報告用列舉，**不是**狀態詞或資料契約；「未發現不等於正常」 | `DEC-2026-11-10-02` ② |
| 11 | 客戶「已更新 Cloud Secrets」＝ Cloud 端恢復 | 客戶口述，未驗證；Cloud 端無機器可驗的取得成功證據（單組） | `secrets_recovery_verification_2026_11_10.md` §0A |
| 12 | branch protection／required checks 已驗 | branch protection API 讀取 403 → NOT VERIFIED | HANDOFF 與多筆 PR 合併訊息 |
| 13 | 作者自述 QA 通過 ＝ 非作者 QA | 本檔與 Batch 1 同屬單組草稿；`COMMENTED`／自述不冒充驗收 | `PROJECT_RULES.md` §8；HANDOFF §4 |

## 4. 盲點與 NOT VERIFIED

1. **沒有任何 live 合法證據**：未探 Streamlit Cloud、Google Sheets、NAS、任何外部來源；L4、L5 的「正式資料」層全部 NOT VERIFIED。
2. **Streamlit Cloud 實際入口與 Python 版本 repo 內查無**（無 `runtime.txt`／`.python-version`）；Cloud 端 Secrets 狀態 NOT VERIFIED。
3. **未讀任何 job log 內文**：L1 的 pytest 通過／略過數量、L2 各排程實際寫入列數與錯誤訊息皆 NOT READ；Slow 在歷史上有 apt DNS 失敗而記 NOT RUN 的實例，本次 run 的 step 結論雖為 success，但**摘要行未讀**。
4. **run 清單只看最近 3～7 次**（總數：nav 89、export 116、macro 28、twse 26、nav 探針 13、fx 探針 4、yahoo 探針 1、moneydj basic 1）；更早的失敗／取消**未查**。`fill_pool_currency`、`watchlist_verify` 的 run 未查。
5. **未讀探針結果分支**（`probe/*-results`）與各 evidence 檔的完整內容；只引用 workflow 檔頭、DEC 與已合併 evidence 的摘要。
6. **L3 數字取自 A1 報告（`data_cache` @ `8ca33547`）與 `metadata.json`**：本批未重跑 A1（環境與 pyarrow 條件未驗）；A1 的 SUSPECTED 為啟發式，不是已證實錯誤。
7. **DEC／BL 引用**：已逐一在 `docs/DECISIONS.md`、`docs/BACKLOG.md` 實際確認存在；內容僅引用其明文，未重新詮釋。`moneydj_basic_probe.yml` 與 `fx_obs_date_probe.yml` 檔頭沒有標 DEC／BL，對應關係以 evidence 目錄與 FX 閘門 DEC 為準，**屬專案 AI 讀法**。
8. **全稱句限度**：「無任何 live 合法證據」「`app.py` 對 `ui_v3` 0 命中」「repo 內查無 Cloud 入口」皆單組字面查詢，未經第二組驗證；客戶口頭驗收若未入 repo，專案 AI 無從核對。
9. **未動**：repo 任何檔、`data_cache`、workflow、Golden、Schema、provider、公式、Sheet、憑證。登記與建議皆不構成動工授權（`CLAUDE.md` §-1）。

## 5. 驗收使用方式（給後續接手者）

1. 先重查 GitHub（main SHA、最新 head 的四 job）→ 填 L1。
2. 再查三條排程最近 N 次 → 填 L2；只寫結論，不寫「資料已更新」。
3. L3：引用 A1 與 `metadata.json`；門檻一律寫「待裁示」。
4. L4、L5：除非客戶提供合法輸入／驗收紀錄，**原封寫 NOT VERIFIED**。
5. 發現 L1～L5 任一層與本檔不一致，以即時 GitHub 為準，並更正本檔（附日期與理由，不刪舊句）。

## 6. PR Impact Check 設計說明（Batch 2 第 2 項；單組作者，尚待非作者 QA）

> §0～§5 是第 3 項（Production 健康度驗收）的唯讀研究；§4 第 9 點的「未動」指該研究階段。§6、§7 登記同一批其他兩項，所指的檔由同一個 commit 新增。

**交付物**：`.github/pull_request_template.md`（35 行，單一 HTML 註解＋五個二級標題）與 `tests/test_pr_template_impact_check.py`（6 支測試）。兩檔必須同一 PR 進去，否則測試先進會紅、模板先進則無守衛。回滾＝刪這兩檔（或 revert 單一 merge commit）；刪一不刪二則測試轉紅。

**欄位出處（讀自 `PROJECT_RULES.md`）**：來源與授權／範圍無夾帶＝§9、§10；七個影響維度與 Gate 對映＝§4（Stop／Decision Gate）、§13.1、§13.3；UI 截圖與「Visual Fidelity Gate 未執行」＝§7；測試＝`PROCESS.md` §4 Test Liveness；SSOT 文件＝§12.1、§13.4；回滾條件＝§10（一般 merge commit、禁 squash）與 §4（destructive migration）；風險分級三檔＝§8（「跨級取最高級、AI 自判、客戶可覆寫」逐字承接）；非作者 QA／CI 逐 job 對 head＝§7、§8，以及 `pr-check.yml` 的 Fast／Schema（阻擋）與 Slow／Visual（`continue-on-error`）；衛生＝§10 與 §14 之 7（`DEC-2026-10-16-09`）。

**與直接 merge 條件的關係（不新增、不改變）**：§10 的四條件（稽核必修 0／CI 綠／範圍與派工單相符／PR 說明無 session 網址）各有一個填寫位置。模板內任何勾選都不是 Gate，勾了不等於授權，沒勾也不會自動擋 merge；「Stop／Decision Gate 對映」是自陳，觸及時照 §4 本來就要停下請客戶。

**取捨**：七維度每項一行 `[ ] 無影響　[ ] 有影響：`，「無影響」是一等公民選項；用行內 `[ ]` 而非列表任務框，因 PR body 常由 AI 以文字寫入。風險分級第三檔刻意不併入 §13.4 第 1 點列的第 2 組高風險項（該疊加屬文件組讀法，模板不替客戶裁決；若評審認為應併入，只改第三檔一行）。「動黃金檔或 baseline」是本作者的揭露項，repo 無逐字條文，已刻意不寫成規則。合併後動作（main push CI、HANDOFF 觀測基準）不放進模板：PR body 在合併前寫，預填只會變成空承諾。

**誠實限制**：
1. **模板不是自動強制。** 網頁介面開新 PR 才會預填；以 GitHub MCP 或 `gh pr create` 帶 body 建 PR 時 body 由作者自寫，不會套用模板。唯一間接牽引是此 session 的 GitHub MCP 指示文字要求建 PR 前先找模板（僅見於工具指示，其他 AI 對話是否遵守 NOT VERIFIED）。
2. **機械守衛只有兩件事**：模板檔的必要標題（先剝 HTML 註解，避免標題寫進註解也過）與八個粗體維度標籤存在；模板全文不含禁用署名字樣（共同作者行、session 網址或 ID）。擋不住「PR body 亂填」，真正把關仍是 §8 的非作者 QA 與 §10 的讀回掃描。
3. 禁用字樣的偵測式與負控在測試內由片段現編，不以字面落在任何檔案（`CLAUDE.md` §-2.A 第 8 款的精神）；模板用中文描述「共同作者行」「session 網址或 ID」。
4. 模板內的衛生勾選不能替代「建 PR 後讀回 body」：工具自動附加的頁尾在建立當下才產生，模板填寫時看不到。

**與既有全站守衛的關係（讀碼＋本機實跑，單組判讀）**：`tests/test_public_repo_name_redaction.py` 掃所有追蹤文字檔，含此模板，日後改模板文字須重跑；`tests/test_constitution_file_refs.py` 只納入「檔頭前 20 行含獨立一行標記」的 `.md`，模板勿加該標記；`tests/test_canonical_rule_consistency.py`、`tests/test_doc_counters.py` 不掃 `.github/`。不新增或修改 workflow、不改 required checks（branch protection API 讀取 403，required checks 現況 NOT VERIFIED，故模板亦不聲稱哪些是 required）、不放 Issue 範本或多模板目錄。

**NOT VERIFIED**：GitHub 對模板檔名與位置的行為（依官方文件為準，本環境未連網驗證）；CI 完整環境（Python 3.11、含 conftest）下新測試與既有守衛是否全綠；本機未安裝 pre-commit，僅逐條複刻其判定；所有全稱句為單組字面搜尋。風險分級建議：模板本身屬治理流程文字，落地 PR 比照 §8 至少 1 組獨立稽核（作者建議，可被客戶覆寫）。

## 7. 第 1 項（CPython 版本守衛＋跨層測試）交叉指標

第 1 項的實作在 PR #1230（僅測試層，黃金檔與 production 程式未動；**2026-11-13 更新：已合併**，main `c8847f00ef13abe52deb6240bf152757693023dc`，一般 merge commit），本檔不重述其內容，只登記位置：

- 守衛 helper：`tests/_py_baseline_guard.py`（基準 CPython 3.11；`decide` 純函式三分支：3.11 照跑嚴格比對、非 3.11 且不在 CI 則帶原因 skip、非 3.11 且 `GITHUB_ACTIONS=true` 則 fail 的 tripwire）；自測 `tests/test_py_baseline_guard.py`（含基準常數與黃金檔檔頭交叉驗證、10 條函式確實掛上守衛的 AST 檢查）。
- 被裝飾的 10 條測試函式（`@baseline_python_only`；比對本體一字未動）：
  - `tests/test_alo_core_golden.py`：`test_整份矩陣_工作樹與黃金檔逐位元組相同`、`test_逐情境相同`（參數化）、`test_額外對照_從git歷史的基準原始碼重算_等於黃金檔`
  - `tests/test_alo_core_golden_mutations.py`：`test_對照組_未突變的載入器重現黃金檔`、`test_突變被黃金檔抓到`（參數化；非 3.11 時未突變基準本身就與黃金檔不同，`assert differ` 會空泛為真而成為假綠燈，故同樣只在基準版本執行）
  - `tests/ui_v2/test_hld_logic.py`：`test_第2件反向控制_十二情境乘九塊一百零八格逐格未變`、`test_第2件_三個新情境的整頁模型逐格釘住`
  - `tests/ui_v2/test_hld_read_failure_logic.py`：`test_T2c正_十七個情境_示範與正式模式共389個模型_與改動前相同`、`test_空白套用d反_設定讀得到_清空再套用照舊說未設定_本條修正不改這些頁面`
  - `tests/ui_v2/test_rulings_2026_10_18b_logic.py`：`test_示範模式_持倉體檢與標的探索全情境模型_md5與動手前相同`
- 新增跨層測試：`tests/test_alo_core_golden_user_visible_invariance.py`（任何 CPython 版本都執行：使用者可見內容與黃金檔相同，只容許內部浮點欄尾差，不放寬嚴格比對）、`tests/test_new_ui_no_imputation_static_guard.py`（New UI 資料路徑的 AST 靜態守衛：不得出現顯式補值 API，對應 Batch 1 Δ3-11／G-1）。
- 數字口徑說明：§2.1 引用 Batch 1 的「8 條」是 3.12 起實測紅燈的測試數；本節的「10 條函式」是被掛上守衛的函式數。兩者口徑不同（被掛守衛者含參數化函式與依賴版本歷史的對照測試），本檔不宣稱兩者應相等，也未逐條重驗哪幾條在非 3.11 實際紅燈。
- 取捨：`test_逐情境相同` 以整函式掛守衛，本機非 3.11 時因此整函式 skip，連不受浮點尾差影響的情境也失去嚴格訊號；此處接受該代價，使用者可見層的訊號由在任何版本都執行的 `tests/test_alo_core_golden_user_visible_invariance.py` 提供。
- 本機 Python 3.13 與 CI Python 3.11 的差異仍在：3.11 完整 pytest 只有 CI 能驗；本機的 skip 不等於通過。PR #1230 的補強已於 2026-11-13 合併（合併前非作者 QA 兩組結論 MERGE-READY、四條 lane CI success；main push CI run 43374994855 success）。限度：Fast lane 不印 pytest 計數，「10 條函式在 CI 逐條執行」仍屬間接推論，未取得逐條日誌。
