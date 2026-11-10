# Secrets 更新後資料恢復驗證：離線盤點與最小驗證方式（2026-11-10）

> **證據歸檔，不是核准，不是恢復證明。**
>
> - 本 session 在沙箱內：**無法存取 Streamlit Cloud**、環境內**沒有任何 FRED／相關環境變數**、GitHub Actions secrets 清單 API 被 proxy 擋下。本文件**不輸出、不猜測任何 Secret 值**（連部分字元也沒有）。
> - **本文件不宣稱 Streamlit Cloud 已恢復**，也不宣稱仍失敗：Cloud 端現況為「無法驗證」。
> - 不核准任何項目；不授權外部抓取、探針、workflow、快取修改、程式修改。`FX_OBS_DATE_RULE_VERIFIED=False` 不變；不動唯一 NEXT＝BL-0545；不新增 BL、不新增 DEC。
> - 客戶「已將先前相關 Key 更新至 Streamlit Cloud Secrets」是**客戶口述，未經本 session 驗證**（NOT VERIFIED）。
> - 本批唯讀：只讀 repo 檔案與 git 歷史，未做任何網路請求。標記：**FACT**＝本 session 讀碼／讀檔所見；**INFERENCE**＝由 FACT 推得；**NOT VERIFIED**＝本 session 不可能驗到。
> - 引用處一律用「檔案＋符號」，不寫行號。

## 0. 置頂摘要

### 0.1 推薦的最小驗證方式（未經客戶裁示）

**推薦候選 1：零程式改動，客戶在 Cloud App 內自行操作並回報畫面文字與日期**（做法見第 5 節）。理由：它是唯一能直接證明「Streamlit Cloud 的 Secrets 與網路」的方式；不需新 workflow、不需任何授權、不輸出 Secret。候選 2（Actions 端探測）只能證明 Actions 端的 Key，不能代替 Cloud。

### 0.2 狀態表（資料 × 環境）

狀態只能是三種：**已恢復（有證據）／仍失敗（有證據）／無法驗證（證據不足）**。

| 資料 | Streamlit Cloud | GitHub Actions |
|---|---|---|
| DGS10（美債 10Y） | **無法驗證**（repo 內無任何 Cloud 端取數證據） | **曾成功取數**：快取末觀測日 2026-11-05；週日排程近期 success（第 6 節）。僅證明 Actions 端 Key 在該日有效，非恢復證明 |
| DGS2（美債 2Y） | **無法驗證** | 同上，末觀測日 2026-11-05 |
| BAMLH0A0HYM2（HY 信用利差） | **無法驗證** | 同上，末觀測日 2026-11-05（快取僅自 2023-06-05 起，見 A1 報告） |
| FEDFUNDS（聯邦基金利率） | **無法驗證** | **無法驗證**：不在 Actions 抓取清單（第 6 節），沒有間接證據 |
| 舊 UI 美國總經指標（CPI、失業率、M2、Sahm、HY 等） | **無法驗證** | **部分有間接證據**：僅 CPIAUCSL、UNRATE、M2SL、WALCL、DTWEXBGS 在抓取清單且快取有列；其餘 series 不在 Actions 清單，**無法驗證**；PPIACO、PCOPPUSDM 宣告但快取零列（A1 報告） |

**阻礙分類總覽**（逐項依據見第 2～4 節）：

| 阻礙 | 狀態 |
|---|---|
| Key（Cloud Secrets 是否有 `FRED_API_KEY`、是否有效） | **NOT VERIFIED**（客戶口述已更新；repo 內無 Cloud 端證據） |
| Cloud 網路（Cloud 出口能否連 FRED／NAS Proxy） | **NOT VERIFIED**；repo 內從未有過 FRED 真實連線在 Cloud 的驗證紀錄（第 3.3 節） |
| 來源（FRED 本身） | Actions 端 2026-11 仍可取數（FACT）；Cloud 端 NOT VERIFIED |
| 既有程式 | 缺 Key 與取數失敗的處理路徑均為 fail loud／降級顯示（FACT，第 2 節）；未見「更新 Key 後必然仍失敗」的程式缺陷，但這不是恢復證明 |
| 快取／行程狀態 | 有可能讓「Key 更新後仍短暫顯示舊失敗」的機制（INFERENCE，第 4 節）；平台是否自動重啟 NOT VERIFIED |

### 0.3 下一個最小安全修復建議（推薦在前，未經客戶裁示）

1. **先由客戶執行候選 1**（5～10 分鐘；必要時先在 Streamlit Cloud 手動 Reboot app，讓行程內快取與退避清零；Reboot 是否必要 NOT VERIFIED，但成本低）。
2. 依客戶回報的畫面文字，用第 5.4 節判讀表分流：金鑰（Secrets 名稱／格式）、網路（Proxy／出口）、來源，三者處理路徑不同，**回報前不要先改程式**。
3. 本批**不建議**新增 workflow 或探測器（會證明錯的環境，見第 5.2 節）。

## 1. Secret 名稱總表（兩個 scope）

### 1.1 兩個 scope 不共用

- **Streamlit App Secrets（部署環境）**：由 Streamlit Cloud 的 Settings → Secrets 注入，`st.secrets` 讀取；`app.py::_load_keys` 另把 `FRED_API_KEY`、`GEMINI_API_KEY`、`GEMINI_API_KEYS`、`GEMINI_API_KEY_1..10`、`ANTHROPIC_API_KEY`、`OPENAI_API_KEY` 鏡射到行程 `os.environ`。讀取順序（`infra.config.get_secret`）：先 `st.secrets`，失敗或缺才 `os.environ`（FACT）。
- **GitHub Actions Secrets**：只在 `.github/workflows/*.yml` 以 `${{ secrets.X }}` 取用並作為步驟環境變數交給腳本；腳本以 `os.environ` 或 `get_secret`（`st.secrets` 失敗後落到 `os.environ`）讀取（FACT）。
- **兩者不共用**：workflow 的 `secrets.X` 只存在於 Actions 執行環境，不會進入 Streamlit 行程；Streamlit 的 `st.secrets` 不會進入 Actions。repo 內未見任何把一邊同步到另一邊的機制（INFERENCE：grep 讀碼所見，單組判讀）。**客戶更新了 Cloud Secrets，不會改變 Actions 端；反之亦然。**
- 既有註記：`infra.proxy.get_proxy_config()` **只讀 `st.secrets`，不讀環境變數**（`PROXY_URL` 或舊格式 `proxy` 區段），結果在行程內快取（TTL 300 秒；讀失敗時快取為空設定）。Streamlit 行程內 `PROXY_URL` 必須放在 Cloud Secrets。

### 1.2 名稱總表

依 grep 讀碼整理，**不宣稱窮舉**（動態組名、未列入字表的封裝可能漏）。「缺漏時」欄只描述程式行為，不含任何 Secret 值。

| 名稱 | Streamlit | Actions | 主要讀取位置（檔案／符號） | 讀取順序 | 缺漏時行為 | 畫面呈現 |
|---|---|---|---|---|---|---|
| `FRED_API_KEY` | 是 | 是 | `app.py::_load_keys`；`ui_v2/mkt/source.py::_fred_api_key`；`ui/helpers/io/data_registry.py`；`ui/tab5_data_guard.py`；`ui/tab2_single_fund.py`、`ui/tab3_portfolio.py`（FX 第二來源）；`scripts/update_macro_history.py`；`scripts/weekly_switch_notify.py` | `st.secrets` → `os.environ`（ui_v2 以 `[st.secrets, os.environ]`；舊總經頁讀 `os.environ`，依賴 `app.py` 先鏡射） | 見第 2 節：不拋錯、降級＋文案；Actions 腳本寫 `last_error` 並跳過 | 見第 2.3 節 |
| `PROXY_URL`（或 `proxy` 區段） | 是（僅 `st.secrets`） | 是 | `infra/proxy.py::get_proxy_config`；多支 workflow 的 env | Streamlit：僅 `st.secrets`；Actions：環境變數 | 無設定→直連降級；Cloud IP 對部分來源可能被擋（`ui/tab5_data_guard.py` 文案） | 側欄／Tab5「Proxy 未設定」灰色說明 |
| `GEMINI_API_KEY`（及 `GEMINI_API_KEYS`、`GEMINI_API_KEY_1..10`） | 是 | 僅 `pr-check.yml` 測試假值 | `app.py::_load_keys`；`services/ai_service.py`；`infra/llm.py` | `st.secrets` → `os.environ` | AI 摘要區塊降級，其餘照常 | Tab5 金鑰表顯示未設定（可降級，不擋路） |
| `ANTHROPIC_API_KEY`／`OPENAI_API_KEY` | 是 | 否 | `app.py::_load_keys`；`infra/llm.py` | 同上 | 該 provider 在 fallback 鏈中略過 | — |
| `FINMIND_TOKEN` | 是 | 否（未見 workflow 傳入） | `ui/helpers/macro/ndc.py`；`ui/tab1_macro_longterm.py`；`ui/views/page_01_macro.py` | `get_secret`；**不被 `_load_keys` 鏡射** | 空字串→FinMind 匿名額度 | Tab5 金鑰表 |
| `ALPHAVANTAGE_API_KEY` | 是 | 否 | `repositories/fund/sources.py`、`fund_orchestration.py` | 同上 | 該來源略過 | — |
| `google_service_account`（區段） | 是 | 是（secret 名為 `GOOGLE_SERVICE_ACCOUNT`） | `repositories/policy/_helpers.py`、`pool_repository.py`、`policy_supplement_repository.py`；多支 workflow | Streamlit：`st.secrets`；Actions：env | 未設定→Sheet 功能降級 | 各頁「尚未設定」灰色說明 |
| `POLICY_SHEET_ID`、`POOL_SHEET_ID`、`NAV_SHEET_ID`、`MACRO_WEIGHTS_SHEET_ID`（`macro_weights_sheet_id`） | 是 | 是（多數） | `repositories/*`、`services/nav_history_*`、`scripts/*` | 同上 | `POOL_SHEET_ID` 無寫死預設，未設→「選股池未設定雲端來源」；`NAV_SHEET_ID` 有 baked 預設 | `ui_v2/plain.py` 已知訊息表 |
| `WATCH_CSV_URL`、`LINE_CHANNEL_TOKEN`、`LINE_CHANNEL_ACCESS_TOKEN`、`LINE_USER_ID` | 是（管理室） | 是 | `infra/line_push.py`、`scripts/*_notify.py`、`ui/tab_manage.py` | 同上 | 通知略過 | — |
| `GSPREAD_SA_JSON`、`GOOGLE_SERVICE_ACCOUNT_JSON`、`GOOGLE_APPLICATION_CREDENTIALS` | 否 | 否（僅腳本環境變數） | `scripts/fetch_nav_cache.py`（前兩者）、`scripts/migrate_v149_schema.py` | `os.environ` | 腳本自行處理 | — |
| `[google_oauth]` 區段（`client_id`、`client_secret`、`redirect_uri`） | 是（僅 Streamlit） | 否 | `infra/personal_oauth.py::SECRETS_SECTION`；`ui/helpers/io/oauth_state.py` | `st.secrets` | 個人 Google 登入不可用 | 登入相關區塊顯示未設定 |
| `GITHUB_TOKEN` | 否 | 是（Actions 內建） | 多支 workflow | — | — | — |

註：workflow 內 `GOOGLE_SERVICE_ACCOUNT`（Actions secret 名）與 Streamlit `google_service_account`（secrets 區段名）大小寫與形態不同，是兩個 scope 各自的名稱，不是同一份設定。

### 1.3 兩邊都有／只有一邊

- **兩邊都有**（各自獨立設定）：`FRED_API_KEY`、`PROXY_URL`、`google_service_account`／`GOOGLE_SERVICE_ACCOUNT`、`POLICY_SHEET_ID`、`POOL_SHEET_ID`、`MACRO_WEIGHTS_SHEET_ID`、`WATCH_CSV_URL`、`LINE_*`；`NAV_SHEET_ID` 在 workflow 與 Streamlit 側都有讀取。
- **只有 Streamlit 用**：`GEMINI_API_KEY*`、`ANTHROPIC_API_KEY`、`OPENAI_API_KEY`、`FINMIND_TOKEN`、`ALPHAVANTAGE_API_KEY`（workflow 內未見取用）。
- **只有 Actions 用**：`GITHUB_TOKEN`；`pr-check.yml` 內的 `FRED_API_KEY`／`GEMINI_API_KEY` 是 CI 測試假值字串，**不是**真實 Secret。
- `FRED_API_KEY` 在 Actions 的使用者：`update_macro_history.yml`（每週日 UTC 00:00 排程）與 `weekly_switch_notify.yml`（傳入環境變數，但該 workflow 呼叫腳本時未見 `--with-macro` 旗標，腳本只在該旗標下才用 FRED；INFERENCE：該 workflow 的 FRED 路徑目前可能不啟用）。

## 2. FRED 路徑（Old UI／ui_v2／ui_v3）

### 2.1 取數鏈（FACT，讀碼）

1. **Key 來源**：`app.py::_load_keys` 於每次腳本執行時以 `get_secret` 讀 `FRED_API_KEY`，有值就寫入 `os.environ`。
2. **L1 取數**：`repositories/macro/fred.py::fetch_fred(series_id, api_key, n)`：`@_ttl_cache(TTL_30MIN, maxsize=32)`；`api_key` 為空→回空 DataFrame 並附錯誤原文，**不發請求**；`fetch_url` 回 `None`（連不上／逾時／403／429／5xx 等）→ 標記為失敗，**不入快取**（404／407 例外：不標記、照舊快取）；FRED 回 200 但 `observations` 為空→**照常快取**（視為 FRED 的答案）。
3. **舊 UI 總經**：`ui/tab1_macro.py` 與 `ui/views/page_01_macro.py` 讀 `os.environ["FRED_API_KEY"]`；`services/macro/us_indicators.py::fetch_all_indicators` 以 `fetch_fred_batch` 預熱一批 series（DGS10／DGS2／DGS3MO、BAMLH0A0HYM2、M2SL、WALCL、CPIAUCSL、FEDFUNDS、UNRATE、PPIACO、UMCSENT、ICSA、HSN1F、SAHMREALTIME、DRTSCILM、CFNAI、CCSA、WM2NS、T5YIE、PERMIT、PAYEMS、DTWEXBGS、DEXJPUS、DEXSZUS、RRPONTSYD、WTREGEN 等；以該函式內清單為準，條數會漂移），單條失敗以 `_fred_iso` 隔離成空表，只讓該格降級。PMI 已**不再走 FRED**（改走 `repositories/macro/alternate.py::fetch_ism_pmi` 備援鏈）。
4. **ui_v2／ui_v3 市場頁**：`ui_v2/mkt/source.py::_fred_api_key` 用 `market_indicator.fred_api_key_from([st.secrets, os.environ])`；`services/v2_tables/market_indicator.py` 與 `market_view.py` 對 FRED 三鍵（HY 信用利差、期限利差、聯邦基金利率）與 DGS10／DGS2 殖利率 domain 呼叫 `fetch_fred_with_error`；缺 Key→**不打 L1**，錯誤原文 `MISSING_FRED_API_KEY`＝「未設定 FRED_API_KEY」。`ui_v3/adapters/market_page.py` 把該原文映射為 `not_configured`（「尚未設定」），其他失敗為 `fetch_failed`（「取數失敗」）。
5. **其他消費者（抽樣，非窮舉）**：`ui/tab2_single_fund.py` 與 `ui/tab3_portfolio.py` 的 FX 第二來源（Yahoo 失敗時走 FRED）、`ui/helpers/io/data_registry.py` 的 FRED 揭露日、`services/risk_radar.py`、`services/liquidity_engine.py`（經 `fetch_fred`）、`repositories/fund/fx_and_main.py`（缺 Key→`out["fred"]["error"]="未設定 FRED_API_KEY"`）、`fund_service` 的無風險利率注入。

### 2.2 各指標對應（FACT）

| 指標 | series | 主要消費點 |
|---|---|---|
| 美債 10Y／2Y | DGS10／DGS2 | `market_view` 殖利率 domain；舊總經頁利率區；Actions 快取 |
| 信用利差 | BAMLH0A0HYM2 | `market_indicator`（HY 利差鍵）；舊總經頁；Actions 快取 |
| 聯邦基金利率 | FEDFUNDS | `market_indicator`；`fetch_all_indicators`；**不在 Actions 抓取清單** |
| 通膨／就業／貨幣 | CPIAUCSL、UNRATE、M2SL、WALCL、PPIACO、PAYEMS、UMCSENT | 舊總經頁 `us_indicators` |
| 衰退／景氣 | SAHMREALTIME、CFNAI、DRTSCILM、ICSA、CCSA、HSN1F、PERMIT | 舊總經頁 `turning_points`、`us_indicators` |
| 流動性／匯率 | WALCL、RRPONTSYD、WTREGEN、DTWEXBGS、DEXJPUS、DEXSZUS | 流動性引擎；FX 第二來源 |

### 2.3 缺 Key／失敗時的畫面文案（原文，FACT）

| 情境 | 畫面文字 |
|---|---|
| 舊總經頁（`ui/tab1_macro.py`、`ui/views/page_01_macro.py`）缺 Key | 灰色說明：「尚未設定 FRED 金鑰，無法載入總經資料」，位置提示：「Streamlit Cloud → Settings → Secrets 的 `FRED_API_KEY`」 |
| Tab5 金鑰表缺 Key | 「尚未設定 FRED_API_KEY —— 整個「<市場定調頁名>」頁無法載入(這一把缺了會擋路)」 |
| Tab5 FRED 揭露日診斷缺 Key | 「FRED_API_KEY 未設定 → 下方揭露日全部會走 fallback」 |
| ui_v2 市場頁缺 Key | 「⛔ 尚未設定：<哪一項>（<哪幾項>）」；原文「未設定 FRED_API_KEY」進跨頁原始訊息 |
| ui_v3 市場頁缺 Key | 狀態字樣「尚未設定」 |
| ui_v2／ui_v3 有 Key 但取數失敗 | 「⛔ 取數失敗」／「取數失敗」；無任何觀測的序列另標「◇ 資料未備」（取數失敗與缺資料分開，不併入） |
| 舊總經頁載入例外 | 「總經指標載入失敗」＋提示「上游 FRED / PMI 來源可能暫時不可用；……請稍後再按一次送出鈕」 |
| 舊總經頁（僅 `ui/tab1_macro.py`；`ui/views/page_01_macro.py` 沒有此 4 小時門檻）已載入但距上次更新逾 4 小時 | 「指標數據已 N 小時未更新（上次：<時間>），點擊下方「🔄 更新總經資料」即可同步最新數據」 |

### 2.4 NOT VERIFIED（本節）

- 無效 Key 時 FRED 的 HTTP 回應，以及 `fetch_url` 內走哪一條分支，本 session 未實測。INFERENCE：非 200 且非 404／407 者回 `None`，畫面應顯示「取數失敗」而非「尚未設定」，因此**「尚未設定」消失不等於 Key 有效**。
- 畫面上 DGS10／DGS2 的實際取數成功與否：NOT VERIFIED。

## 3. 過往失敗原因（僅 repo 內證據）

### 3.1 Actions 端：Key 曾缺，後已補（FACT，提交歷史）

`data_cache/metadata.json` 的歷史版本：

| 提交 | 日期 | `fred_indicators.last_error` | 備註 |
|---|---|---|---|
| `d171cce4` | 2026-06-02 | 「FRED_API_KEY 未設定」，`row_count=0` | 當次 Actions 環境讀不到 Key（腳本寫入此文字） |
| `2a96a4fb` | 2026-06-03 | 「抓取結果為空」，`row_count=8457` | 有資料列但該次抓取結果為空 |
| `f39a1b69` | 2026-06-03 | `null`，`row_count=13343` | 此後 `last_error` 為 `null`；目前 metadata `last_updated=2026-11-05` |

限制：這是 **Actions 端**證據，來源是自動提交的 metadata；它不說明 Streamlit Cloud。

### 3.2 Streamlit Cloud 端 Key 狀態

**repo 內沒有證據**（NOT VERIFIED）。僅有：程式文案（缺 Key 時提示去 Cloud Secrets 設定）、客戶口述（已更新，未驗）。

### 3.3 「FRED 真實連線在 Cloud 從未驗證」的出處（FACT）

- `services/v2_tables/market_view.py` 檔頭：「本 session 沒有對 FRED 真實連線驗證回應；只用替身測過形狀。首次部署要看畫面是否為『⛔ 取數失敗』或空序列。」
- `docs/evidence/international_market_source_inventory_2026_11_09.md` 第 5 節：`ui_v2`、`ui_v3` 的 live 真資料（Yahoo、FRED）從未在 Cloud 或真機驗過。
- `docs/evidence/stage2_reuse8_semantics_validation_spec_draft_2026_11_09.md`：FRED 對共用 L1 的 Cloud 真實連線結果列為待證據。
- `docs/evidence/decisions/2026-11-03_shell_wording_and_degraded_first_screen_ruling.md` 與多份 HANDOFF 歷史檔：「Yahoo／FRED 真實連線」仍待驗證。

限制：上列都是「尚未驗證」的陳述，**不是**「Cloud 連 FRED 失敗」的證據。本批未在 repo 內發現 Cloud 出口與 FRED 401／403／429 相關的失敗紀錄（grep 讀碼結果，未窮舉歷史文件）。

## 4. Key 更新後的快取殘留風險（讀碼判斷，標 INFERENCE／NOT VERIFIED）

| 機制 | 讀碼事實（FACT） | 對「Key 更新後仍顯示舊失敗」的影響（INFERENCE） |
|---|---|---|
| `fetch_fred` 的 `_ttl_cache` | 30 分鐘、`maxsize=32`；`api_key` 是快取鍵的一部分；失敗（`fetch_url` 回 `None`）不入快取（404／407 除外） | Key 更換後是新的快取項，不會命中舊失敗項；但 FRED 回 200 且 `observations` 為空會被快取 30 分鐘；`fred.py` 註解所列「JSON 解析壞」也會被 `_ttl_cache` 快取；404／407 失敗也會被快取。另 INFERENCE（未實測）：無效 Key 時 FRED 回 400 類，依 `kind_for_status`（>=400 歸 server_error）會進 300 秒冷卻 |
| 主機層退避 `infra/source_backoff.py` | 行程內 `_STATE` 字典，無檔案寫入；失敗後依類型冷卻（封鎖 900 秒、限流 1800 秒、5xx 300 秒、逾時／連不上 60 秒），冷卻期內 `fetch_url` 直接回 `None` 不發請求 | 若更新前行程已累積冷卻，更新 Secrets 本身不會清除；最長約 30 分鐘內仍可能看到失敗，直到冷卻期滿或行程重啟（Tab5 診斷路徑可刻意繞過，僅限診斷） |
| `get_proxy_config` 快取 | 行程內，TTL 300 秒，讀失敗也快取為空設定 | `PROXY_URL` 改動最多 5 分鐘內可能未生效 |
| Streamlit session 狀態 | 舊總經頁把載入結果／錯誤存在 `st.session_state`；需按送出鈕（或「強制重抓」）才重新載入 | 同一瀏覽器工作階段內，舊失敗訊息會留到重新按鈕或重新整理頁面 |
| `app.py::_load_keys` | 每次腳本執行都重讀 `st.secrets` 並鏡射到 `os.environ`（有值才寫入） | 行程存活期間，若 `st.secrets` 被平台更新，下一次執行即可讀到；是否即時更新 NOT VERIFIED |
| Cloud 更新 Secrets 後是否自動重啟 app、`st.secrets` 是否熱更新 | repo 內無任何證據 | **NOT VERIFIED（平台行為，不斷言）**。保守做法：客戶更新後手動 Reboot，再按各頁載入按鈕 |
| `st.cache_data` 殘留失敗 | 本節範圍的 FRED 路徑（`fetch_fred` 與 ui_v2 市場頁取數）採 `_ttl_cache`；`market_indicator.py` 檔頭明述不再疊 `st.cache_data`；其他頁面（FX、NAV 等）是否另有 `st.cache_data` 未逐一盤點 | 對 FRED 市場頁風險低；全站範圍 NOT VERIFIED |

結論：**更新 Key 後，Key 本身通常會換出新的快取項；殘留風險主要來自行程內的主機退避、空觀測快取（30 分鐘）與瀏覽器工作階段狀態**。Cloud 是否自動重啟 NOT VERIFIED，建議以手動 Reboot＋重新載入作為驗證前置。

## 5. 既有診斷入口與最小驗證方式

### 5.1 候選 1：客戶在 Cloud App 內自行操作（零程式改動；推薦，未經客戶裁示）

| # | 入口（位置） | 顯示什麼 | 洩漏 Secret？ | 會發外部請求？ |
|---|---|---|---|---|
| 1 | **Tab5 資料守門／⑤ 設定與診斷 →「④ API 金鑰狀態」表**（`ui/tab5_data_guard.py`） | `FRED_API_KEY` 等：使用來源（`st.secrets`／`os.environ`／`(無)`）、遮罩值、`os.environ` 同步 | **注意（FACT）**：遮罩函式顯示**前 4 字＋後 4 字＋長度**，不是完全不輸出原值。客戶自己看沒問題，但**回報時請勿貼該欄位或截圖，只回報「使用來源」欄與是否為 `(無)`** | 否 |
| 2 | **🌐 市場定調頁（總經）**：送出／載入按鈕（舊 `ui/tab1_macro.py` 與 `ui/views/page_01_macro.py`） | 載入後的各指標卡、「✅ 已載入 · <時間> TW」、各指標資料日 | 否 | 客戶按下才發 |
| 3 | **ui_v2／ui_v3 市場頁**（若 Cloud 有部署該入口；`app.py` 未 import 預覽入口，是否部署 NOT VERIFIED） | DGS10／DGS2、HY 利差、FEDFUNDS 卡與資料日；失敗為「⛔ 取數失敗」或「尚未設定」 | 否（錯誤原文經 `masking` 遮蔽） | 客戶按下才發 |
| 4 | **Tab5「🔬 FRED next_release_date 診斷」→「🔍 立即診斷（會打 API，30 天 cache）」** | 12 條 series 的下次發布日；「❌ None (API 失敗 / 無資料)」或日期＋距今 | 否 | 是，客戶按下才發。限制：只證明 FRED 可達且 Key 可用於 release 端點；**不顯示最新觀測值** |
| 5 | **側欄「🔍 測試 Proxy 連線」** | 逐一測 MoneyDJ／TDCC／Yahoo／**FRED 首頁**等：「✅ <名稱> 可達！HTTP <碼>」 | 否 | 是，客戶按下才發。限制：FRED 項測的是 `fred.stlouisfed.org` 首頁、**不帶 Key**，只證明出口網路／Proxy 可達，**不證明 Key 有效**；且僅在有設定 `PROXY_URL` 時才有此測試 |
| 6 | **Tab5「🌍 FX 即時匯率來源診斷」→「🔍 跑 FX 來源診斷」** | 逐源檢測，含 FRED 第二來源 | 否 | 是，客戶按下才發 |

### 5.2 候選 2：授權一次性 GitHub Actions FRED 唯讀探測

- **能證明**：Actions 端的 `FRED_API_KEY` 目前有效、FRED 目前可從 GitHub Runner 連線。
- **不能證明**：Streamlit Cloud 的 Secrets 是否已更新、Cloud 出口能否連 FRED。兩邊 Secrets 與網路都不同（第 1.1 節）。
- **風險／成本**：需新 workflow 與外部請求，須客戶另行授權；本批不做。「Actions 成功」可能被誤讀為「Cloud 已恢復」。
- **速度／Token**：分鐘級／中等（新增 workflow＋稽核）。
- **推薦度**：低（不能回答客戶的問題）。

### 5.3 候選 3：新增 App 內「Secrets 與連線自檢」小功能（僅列選項，本批不做）

- **能證明**：同候選 1，但操作更集中。
- **不能證明**：不能超過 App 內可見資訊。
- **風險**：新增程式與畫面（涉及 UI 草稿先行、遮蔽規則、測試），需客戶授權。
- **速度／Token**：慢／高。
- **推薦度**：低；候選 1 結果不足時再議。

### 5.4 判讀表（畫面文字 → 狀態）

| 客戶回報的畫面 | 判讀 |
|---|---|
| 金鑰表 `FRED_API_KEY` 的使用來源為 `(無)`，或頁面仍是「尚未設定 FRED 金鑰」 | **仍失敗（Key 層）**：Cloud 讀不到 `FRED_API_KEY`；檢查 Secrets 名稱與引號格式（Tab5 另有 TOML 格式錯誤提示） |
| 使用來源為 `st.secrets`，總經頁載入後 DGS10／DGS2／HY 有數值，資料日為近期交易日 | **已恢復（Cloud 端，該指標）**：需回報資料日；不含 Secret |
| 使用來源為 `st.secrets`，但載入後仍「取數失敗」 | **仍失敗（網路／來源／Key 無效，尚不可分）**；再看第 4、5 項診斷分流 |
| FRED 揭露日診斷全部「❌ None」，且側欄 Proxy 測試 FRED 項不可達 | 偏向 **網路／Proxy 層**（INFERENCE） |
| FRED 揭露日診斷有日期，但市場頁仍失敗 | 偏向 **取數端／快取／退避層**（INFERENCE）；建議 Reboot 後重試 |
| 畫面只顯示資料日但看不出是否為更新前快取 | **無法判定**：需客戶回報「最後更新時間」與頁面載入時間 |
| 頁面為「資料未備」（◇） | **無法判定**：缺資料與取數失敗分開，此狀態不代表已恢復也不代表失敗 |

客戶回報模板（不含 Secret）：「使用來源欄顯示：<st.secrets／os.environ／(無)>；總經頁載入後 DGS10／DGS2／HY／FEDFUNDS 各自是否出現數值、資料日期、頁面顯示的文字；是否已手動 Reboot」。

### 5.5 外洩面範圍（FACT，既有行為，本批不修改）

Tab5「API 金鑰狀態」表（`_key_targets`）共 5 把：`FRED_API_KEY`、`GEMINI_API_KEY`、`FINMIND_TOKEN`、`PROXY_URL`、`GOOGLE_SHEET_ID`，**都會顯示前 4 字＋後 4 字＋長度**。其中 `PROXY_URL` 可能含帳密。客戶回報時**一律不要貼或截圖該表**，只回報「使用來源」欄。登記為後續待辦候選（未經客戶裁示，不動工）。

### 5.6 非本批範圍的新風險（低，未修改）

- `scripts/update_macro_history.py` 的 FRED 取數以 `requests.get(params=api_key)`，`except` 內 `print` 例外訊息；`requests` 連線類例外訊息含完整 URL（含 `api_key` 查詢參數）。
- 重現條件：Actions 內 FRED 連線逾時／Max retries。
- 緩解：GitHub Actions 日誌會自動遮罩已註冊的 secret 值，實際風險低（INFERENCE，平台行為未實測）。
- Streamlit 路徑（`infra/proxy.py`、`fetch_fred`）已以 `_url_log`／`_exc_log` 砍掉查詢字串。
- 建議（未經客戶裁示）：另批處理，並對 `fred_vintage.py` 等直接使用者做同法盤點。

## 6. Actions 端現有證據（離線；引用，不重算）

- `data_cache/fred_indicators.parquet`：13829 列、9 個 series、共同最大日期 2026-11-05（`docs/evidence/cache_quality_check_a1_report_2026_11_10.md`；範例報告以自製讀取器產生，未對拍 pyarrow，須 CI／QA 重現）。DGS10、DGS2、DGS3MO、BAMLH0A0HYM2 末觀測日 2026-11-05；CPIAUCSL 與 M2SL 末觀測日 2026-04-01；UNRATE 2026-10-01；WALCL 2026-11-04；DTWEXBGS 2026-10-30。
- `data_cache/metadata.json`：`fred_indicators.last_updated=2026-11-05`、`last_error=null`、`updated_at=2026-11-08T04:07:01Z`。
- `update_macro_history` workflow（每週日 UTC 00:00）：客戶／總管提供的 GitHub API 唯讀事實——2026-11-08 run `42445437781` success、2026-11-01 與 2026-10-25 等亦 success。**本 session 未重新查詢**，視為已知事實引用。repo 內可佐證：2026-11-01、2026-11-08 皆有「每週全球總經歷史增量」自動提交。
- **這是「Actions 端曾成功取數」的證據，不是 Streamlit Cloud 的證據。**
- `FEDFUNDS` 不在 `scripts/update_macro_history.py::FRED_SERIES_IDS`（11 項：DGS10、DGS2、DGS3MO、BAMLH0A0HYM2、M2SL、WALCL、CPIAUCSL、UNRATE、DTWEXBGS、PPIACO、PCOPPUSDM），因此 Actions 端對 FEDFUNDS **沒有任何間接證據**。
- 宣告 11 項 vs 快取 9 項：PPIACO 與 PCOPPUSDM 宣告但零列（A1 報告「CONFIRMED」項，成因不判）。本批引用，不重做。

## 7. NOT VERIFIED 清單

1. Streamlit Cloud Secrets 目前是否含有效的 `FRED_API_KEY`（客戶口述）。
2. Cloud 出口能否連到 FRED／NAS Proxy。
3. Cloud 更新 Secrets 後是否自動重啟、`st.secrets` 是否熱更新。
4. 無效 Key 時 FRED 回應與 `fetch_url` 的實際分支。
5. 第 6 節所引 Actions run 的最新狀態（本 session 未查）。
6. 第 1.2 節名稱總表為 grep 讀碼整理，未經第二組獨立複驗，不宣稱窮舉；全站其餘 `st.cache_data` 使用處未盤點。
7. 本文件為專案 AI 單組整理，未經獨立稽核。

## 8. 一句話結論

repo 內有足夠證據說明 **Actions 端**資料到 2026-11-05 仍可取得，但對 **Streamlit Cloud 端**，所有 FRED 相關資料目前都是「無法驗證」。最小驗證是請客戶在 Cloud App 內做第 5.1 節的操作並回報畫面文字與資料日期（不含任何 Secret）。
