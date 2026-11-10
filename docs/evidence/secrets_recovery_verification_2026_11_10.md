# Secrets 更新後資料恢復驗證：離線盤點與最小驗證方式（2026-11-10）

> **證據歸檔，不是核准，不是恢復證明。**
>
> - 本 session 在沙箱內：**無法存取 Streamlit Cloud**、環境內**沒有任何 FRED／相關環境變數**、GitHub Actions secrets 清單 API 被 proxy 擋下。本文件**不輸出、不猜測任何 Secret 值**（連部分字元也沒有）。
> - **本文件不宣稱 Streamlit Cloud 已恢復**，也不宣稱仍失敗：Cloud 端現況為「無法驗證」。
> - 不核准任何項目；不授權外部抓取、探針、workflow、快取修改、程式修改。`FX_OBS_DATE_RULE_VERIFIED=False` 不變；不動唯一 NEXT＝BL-0545；不新增 BL、不新增 DEC。
> - 客戶「已將先前相關 Key 更新至 Streamlit Cloud Secrets」是**客戶口述，未經本 session 驗證**（NOT VERIFIED）。
> - 本批唯讀：只讀 repo 檔案與 git 歷史，未做任何網路請求。標記：**FACT**＝本 session 讀碼／讀檔所見；**INFERENCE**＝由 FACT 推得；**NOT VERIFIED**＝本 session 不可能驗到。
> - 引用處一律用「檔案＋符號」，不寫行號。
> - **2026-11-10 範圍追加（客戶要求，沿用 #1196）**：除 FRED 外，補上舊 UI 完整資料來源矩陣（附錄 A）、缺口、可重用能力與最小驗證建議；置頂新增「推薦結論」（§0A）。矩陣由兩份單組唯讀草稿整合，**本組已自行抽查 13 項關鍵宣稱**（附錄 B），未抽查的列標「轉載」，仍屬單組、未經第二組驗證。

## 0A. 推薦結論與五張精簡表（2026-11-10 追加；未經客戶裁示）

**推薦結論**：目前**沒有任何一個來源在 Streamlit Cloud 端有機器可驗的「取得成功」證據**（FACT：repo 內搜尋所得，單組）；有證據者全是 GitHub Actions 端或離線。最省、最低風險的下一步是：**客戶先在 Cloud 用既有診斷入口回報畫面文字（零程式改動、零新外部請求），再依結果決定要不要改程式**。已讀碼確認的幾個「改 Key 也救不了」的程式面問題（見表 b、e）應在 Cloud 回報之後再排序，不應先動。

### (a) 舊 UI 有、New UI（ui_v2／ui_v3）沒有的資料與功能（FACT，依呼叫鏈；單組 grep）
| 類別 | 項目 |
|---|---|
| 總經 | 約 20 條 FRED 指標（CPI、PPI、失業率、非農、M2、Fed 資負表、Sahm、CFNAI、SLOOS 等）、美國 PMI 備援鏈、風險雷達、流動性引擎、拐點偵測、景氣位階；New UI 只接 `^VIX`、`^GSPC`、`^TWII`、DGS10／DGS2、HY OAS、10Y-2Y、FEDFUNDS（FX 閘門關閉）|
| 籌碼／情緒／新聞 | FinMind 外資買賣超（熱錢）、NDC 景氣燈號、AAII、穩定幣市值、RSS 新聞與個股新聞 |
| 基金 | 持股前十大／產業配置、績效 wb01／風險 wb07／同儕比較、雙演算法對帳、保單基金備援鏈（Morningstar／Yahoo／Alpha Vantage／保單商官網）、批次續跑、TDCC／FundClear 找代號（新 UI 已裁示取消）|
| 帳本與其他 | 帳本與 T7 快照、選股池 switch_advisor、績效追蹤、LINE 通知、配息行事曆、組合基準對比 |
| AI | Gemini 單基金／組合／跨檔解盤、策略 3 組合建議、資料健康 AI（ui_v2／ui_v3 對 `ai_service`／`infra.llm` 的 import，本組 `git grep` 為 0）|

### (b) 已接線、但可能因 Key／Proxy 失敗的來源（風險，不是已失敗）
| 來源 | 風險機制 | 分類 | 標籤 |
|---|---|---|---|
| FRED 全部（舊 UI 與 ui_v2／ui_v3）| 缺或無效 `FRED_API_KEY`；Cloud 出口／Proxy 未驗 | 缺 Secret／認證失敗／Cloud 網路限制（三者不可混為一談，Cloud 端皆未驗）| NOT VERIFIED |
| FinMind 外資買賣超（舊總經頁熱錢卡）| `page_01_macro` 只讀 `os.environ`，`_load_keys` 不鏡射 `FINMIND_TOKEN`；token 只放 Streamlit Secrets 時，此頁會以空 token（匿名額度）呼叫 | 缺 Secret（讀取不一致）| FACT（讀碼）／INFERENCE（Cloud 影響）|
| TDCC、Morningstar 搜尋與 timeseries、Yahoo 基金、Alpha Vantage | 裸 `urllib`，靠 `infra.proxy` import 時裝一次全域 opener；import 當下讀不到 `st.secrets` 則標記已嘗試而**不再重裝** | Cloud 網路限制／設定時序 | FACT（程式）／INFERENCE（Cloud 影響）|
| 鉅亨 cnyes、Morningstar 持股、Allianz JSON | `requests` 帶 `proxies=`，沒有 403 降級直連與主機退避 | Cloud 網路限制 | FACT |
| `update_macro_history` 的 Proxy 路徑 | 它嘗試的兩個 import 目標（`infra.proxy_helper`、`repositories.macro_repository.fetch_url`）本組 `git grep` 皆不存在，最後退到不帶 proxy 的 `requests.get`；workflow 雖傳 `PROXY_URL`，實際未被使用 | 既有程式／快取或增量缺陷 | FACT |
| Google Sheets（`google_service_account`、`*_SHEET_ID`）、`[google_oauth]`、Gemini | 缺 Secret 時各自降級（灰色說明）；Cloud 讀寫成敗未驗 | 缺 Secret／認證失敗 | NOT VERIFIED |
| FundClear `GetFundBasicInfo` | 2026-10-14 Actions 探針 9/9 回非 JSON，原因未知；經 NAS 未驗 | 來源停供或欄位改變（未確認）| FACT（現象）／原因 NOT VERIFIED |

### (c) 已有取得證據的來源（只有 Actions 端或離線；Cloud 端證據多半為零）
| 來源 | 環境 | 證據 | 限制 |
|---|---|---|---|
| FRED 9 series | **Actions** | 快取末觀測 2026-11-05、`last_error=null`；週日排程 success（引用，本 session 未重查）| 非 Cloud；CPI／M2 末觀測 2026-04-01、PPIACO／PCOPPUSDM 零列、DTWEXBGS 21 列（A1 報告）|
| Yahoo `^GSPC`／`^VIX`／`^TWII` | **Actions** | 2026-11-09 受控探測 HTTP 200；指數快取 2026-11-06 | 日期規則未驗；非 Cloud |
| Yahoo 匯率 6 代號 | **Actions** | 2026-11-08 探測 `status=ok` | CNY／CNH 僅回 1 根；`FX_OBS_DATE_RULE_VERIFIED=False` |
| MoneyDJ www 基本資料／NAV 頁 | **Actions**（直連與 NAS 兩路徑）| 2026-10-14 基本頁 8 碼 200；2026-10-29～11-09 NAV 探針 | 非 Cloud；tcbbankfund 頁型多為 404；回 200 不證明代碼被識別 |
| TDCC 3-2 清單 | **Actions** | 5251→5295 列 | 與 MoneyDJ／保單碼體系不通；3-4 回 0 筆 |
| 鉅亨 NAV | **Cloud（客戶自述）** | 2026-07-22 STATE：App 端抓得到當日 NAV | 非機器證據；同日 Actions 端全掛 |
| 其餘（FinMind、Stooq、Cboe、AAII、DefiLlama、RSS、er-api、Frankfurter、海關、SITCA、Morningstar 等）| — | 無近期成功紀錄 | 見附錄 A；Cboe Put/Call 凍結檔、Stooq `^cpc`、Yahoo `^CPC`／`^CPCE` 另有 2026-06／07 的失敗紀錄（STATE，轉載）|

### (d) 必須 Streamlit Cloud 實測才能確認
1. Secrets 內 `FRED_API_KEY`、`FINMIND_TOKEN`、`PROXY_URL`、Google／Gemini 各名稱是否存在且有效（只回報「使用來源」欄，勿貼遮罩值）。
2. Cloud 出口與 NAS Proxy 對 FRED、Yahoo、FinMind、MoneyDJ、FundClear、cnyes、TDCC 的可達性。
3. 總經頁熱錢卡實際是否以空 token 呼叫。
4. 全域 urllib opener 在 Cloud 啟動時是否成功安裝。
5. AAII（曾被 Cloudflare 攔截）、Stooq、Cboe、DefiLlama、RSS、Google News RSS 在 Cloud 出口是否被擋。
6. 更新 Secrets 後是否需手動 Reboot（行程內退避、30 分鐘快取、300 秒 Proxy 設定快取）。

### (e) 下一批修復順序（推薦在前；未經客戶裁示）
| 順序 | 內容 | 改程式？ | 新外部請求？ | 是否觸及 Stop Gate（總管讀法，可被推翻）| 速度／Token |
|---|---|---|---|---|---|
| 1 | 客戶在 Cloud 以既有診斷入口回報（§5.1）| 否 | 客戶自行按下才發 | 否 | 最快／最省 |
| 2 | `FINMIND_TOKEN` 讀取一致性（`page_01_macro` 與 `_load_keys` 鏡射／`get_secret` 對齊）| 是（小）| 否 | 否（讀取方式，不新增 source、不動公式）| 快／低 |
| 3 | Proxy 一致性：全域 opener 時序、cnyes／Morningstar 持股／Allianz 的 403 降級與退避 | 是（中）| 否（但需 Cloud 實測才能驗）| 否，屬 infra；若改為新 production 呼叫形態需另評 | 中 |
| 4 | `update_macro_history` 的 Proxy 路徑與增量缺陷（CPI／M2 停更、零列 series、後加序列不回補）| 是（含 workflow）| 是（Actions 重抓）| **可能**：涉及 `data_cache` 回補與 migration，需客戶裁示 | 中／中高 |
| 5 | 新 UI 接線（FinMind 籌碼、更多 FRED 指標、AI）| 是（大）| 是 | **是**：新 production data source、UI 草稿先行、AI 行為 | 慢／高 |

**資料層與 AI 層分離：API 成功 ≠ 符合金融語意 ≠ 可供 AI 使用。** 上列「取得成功」只代表 HTTP 與解析成功，不代表觀測日／時區、單位／方向、vintage 或幣別口徑已核實，也不代表已核准納入畫面計算或 AI evidence。

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
| `FINMIND_TOKEN` | 是 | 否（未見 workflow 傳入） | `ui/helpers/macro/ndc.py`；`ui/tab1_macro_longterm.py`；`ui/views/page_01_macro.py`<br>~~（舊表述：三處皆以 `get_secret` 讀取）~~ | `ui/helpers/macro/ndc.py` 與 `ui/tab5_data_guard.py` 用 `get_secret`；**`ui/views/page_01_macro.py::_load_everything` 只讀 `os.environ`（不是 `get_secret`）**；**全部不被 `_load_keys` 鏡射** ——（2026-11-10 有意識更正，不是漏刪：舊表述把總經頁寫成 `get_secret`，與讀碼不符；`git grep` 本組自驗）| 空字串→FinMind 匿名額度 | Tab5 金鑰表 |
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
3. ~~**舊 UI 總經**：`ui/tab1_macro.py` 與 `ui/views/page_01_macro.py` 讀 `os.environ["FRED_API_KEY"]`；~~（2026-11-10 有意識更正，不是漏刪：`app.py` 現行呼叫的舊總經頁是 `ui/views/page_01_macro.py::render_market_overview`；`ui/tab1_macro.py::render_macro_tab` 本組 `git grep`（排除 tests）僅見註解／docstring 提及，**未見任何呼叫點**，單組 grep、未經第二組驗證、可能漏動態呼叫。以下取數鏈以 `page_01_macro` 為準，`tab1_macro` 內的路徑在 `app.py` 不被渲染。）**舊 UI 總經**：`ui/views/page_01_macro.py` 讀 `os.environ["FRED_API_KEY"]`；`services/macro/us_indicators.py::fetch_all_indicators` 以 `fetch_fred_batch` 預熱一批 series（DGS10／DGS2／DGS3MO、BAMLH0A0HYM2、M2SL、WALCL、CPIAUCSL、FEDFUNDS、UNRATE、PPIACO、UMCSENT、ICSA、HSN1F、SAHMREALTIME、DRTSCILM、CFNAI、CCSA、WM2NS、T5YIE、PERMIT、PAYEMS、DTWEXBGS、DEXJPUS、DEXSZUS、RRPONTSYD、WTREGEN 等；以該函式內清單為準，條數會漂移），單條失敗以 `_fred_iso` 隔離成空表，只讓該格降級。PMI 已**不再走 FRED**（改走 `repositories/macro/alternate.py::fetch_ism_pmi` 備援鏈）。
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
| 舊總經頁（`ui/views/page_01_macro.py`；~~`ui/tab1_macro.py`~~ 同文案但 `app.py` 不呼叫）缺 Key | 灰色說明：「尚未設定 FRED 金鑰，無法載入總經資料」，位置提示：「Streamlit Cloud → Settings → Secrets 的 `FRED_API_KEY`」 |
| Tab5 金鑰表缺 Key | 「尚未設定 FRED_API_KEY —— 整個「<市場定調頁名>」頁無法載入(這一把缺了會擋路)」 |
| Tab5 FRED 揭露日診斷缺 Key | 「FRED_API_KEY 未設定 → 下方揭露日全部會走 fallback」 |
| ui_v2 市場頁缺 Key | 「⛔ 尚未設定：<哪一項>（<哪幾項>）」；原文「未設定 FRED_API_KEY」進跨頁原始訊息 |
| ui_v3 市場頁缺 Key | 狀態字樣「尚未設定」 |
| ui_v2／ui_v3 有 Key 但取數失敗 | 「⛔ 取數失敗」／「取數失敗」；無任何觀測的序列另標「◇ 資料未備」（取數失敗與缺資料分開，不併入） |
| 舊總經頁載入例外 | 「總經指標載入失敗」＋提示「上游 FRED / PMI 來源可能暫時不可用；……請稍後再按一次送出鈕」 |
| ~~舊總經頁（僅 `ui/tab1_macro.py`；`ui/views/page_01_macro.py` 沒有此 4 小時門檻）已載入但距上次更新逾 4 小時~~（2026-11-10 有意識更正：此文案只在 `ui/tab1_macro.py`，而該頁 `app.py` 不呼叫，故**現行舊 UI 畫面看不到這句**；列保留供追溯）| 「指標數據已 N 小時未更新（上次：<時間>），點擊下方「🔄 更新總經資料」即可同步最新數據」 |

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
| 2 | **🌐 市場定調頁（總經）**：送出／載入按鈕（`ui/views/page_01_macro.py`；~~舊 `ui/tab1_macro.py`~~ 見 §2.1 更正） | 載入後的各指標卡與各指標資料日（~~「✅ 已載入 · <時間> TW」~~ 該句屬 `tab1_macro`，現行頁是否有同句未驗） | 否 | 客戶按下才發 |
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

## 附錄 A　舊 UI 完整資料來源矩陣（2026-11-10 追加）

**讀法**：欄位＝供應者｜資料｜舊 UI 入口｜實際函式（檔案＋符號）｜Secret（名稱·scope；S＝Streamlit Secrets、A＝Actions）｜Proxy｜fallback 順序｜證據（Actions 端／Cloud 端，標日期）｜ui_v2／ui_v3 是否重用｜問題分類｜標籤。「問題分類」七選一（缺 Secret／認證失敗／Cloud 網路限制／來源停供或欄位改變／快取或增量缺陷／新 UI 尚未接線／未經實測），無已知問題則寫「無已知問題」，不混用。**標籤「轉載」＝取自兩份單組草稿、本組未逐項重驗**；標 FACT 者為本組讀碼或 `git grep` 所見。「0 production caller」一律是**單組 grep、未經第二組驗證**，可能漏動態或字串名呼叫。Cloud 端證據欄凡寫「無」＝repo 內未見，不是「已確認失敗」。

### A.1 總經與市場資料

| 供應者 | 資料 | 舊 UI 入口 | 實際函式 | Secret | Proxy | fallback | 證據 | v2／v3 | 問題分類 | 標籤 |
|---|---|---|---|---|---|---|---|---|---|---|
| FRED | 約 20 條美國總經（CPI、PPI、失業、非農、M2、Fed 資負表、DGS 系列、HY OAS 等）| ① 市場定調頁送出後 | `services/macro/us_indicators.py::fetch_all_indicators`→`repositories/macro/fred.py::fetch_fred` | `FRED_API_KEY`·S | 經 `fetch_url`（有設則 NAS）| 單 series 失敗只讓該格缺；無跨源備援 | Actions：9 series 末觀測 2026-11-05；Cloud：無 | 僅 DGS10／DGS2／HY OAS／10Y-2Y／FEDFUNDS | 未經實測（Cloud）；新 UI 尚未接線（多數指標）| FACT／轉載 |
| FRED | 風險雷達、流動性、美股流動性、拐點 | ① 同上 | `services/risk_radar.py::detect_risk_radar`、`services/liquidity_engine.py::fetch_liquidity_factors`、`services/us_liquidity_engine.py::fetch_us_liquidity_snapshot`、`services/macro/turning_points.py::detect_turning_points` | 同上 | 同上 | 無 | 無 | 無 | 新 UI 尚未接線；未經實測 | 轉載 |
| FRED | v2／v3 殖利率、利差、FEDFUNDS（含 vintage）| 舊 UI 不使用 | `services/v2_tables/market_view.py`、`market_indicator.py`、`repositories/macro/fred_vintage.py` | 同上；缺 Key 時不打 L1，文案「未設定 FRED_API_KEY」| 同上 | 無 | 檔頭自陳只用替身測過形狀；Cloud：無 | **是** | 未經實測 | FACT |
| FRED | 發布日（Tab5／data_registry）| ⑤ 診斷 | `repositories/macro_repository.py::fred_get_next_release_date` | 同上 | 同上 | 失敗→靜態天數閾值 | 無 | 否 | 未經實測 | 轉載 |
| FRED NAPM／ISPMANPMI | ISM PMI（2016 停更）| 已拔除（2026-09-01）| 守衛 `tests/test_dead_fred_pmi_series_removed.py` | — | — | — | — | — | 來源停供（已移除取數）| FACT（CLAUDE.md §2.3）|
| Yahoo chart | `^VIX`、銅、SPY／RSP、DXY、跨幣、BTC、HYG／LQD、板塊 ETF、`^MOVE`、亞洲指數等 | ① 總經頁、雷達、流動性 | `repositories/macro/yf.py::fetch_yf_close` | 無 | 經 `fetch_url`；主機級共用冷卻 | 單 ticker 失敗只缺該格 | Actions：`^VIX` 2026-11-09 探測 200；其餘 ticker 無；Cloud：無 | 僅 `^VIX`／`^GSPC`／`^TWII` | 未經實測 | 轉載 |
| Yahoo chart | `^CPC`／`^CPCE`（Put/Call）| ① 雷達 | 同上 | 無 | 同上 | Stooq→Cboe pcratio | STATE 2026-06／07（user 回報，Cloud）：production trace「empty」 | 否 | 來源停供 | 轉載 |
| Yahoo chart | USDTWD 與基金幣別 `<ISO>TWD=X` | ①熱錢、②③④ 換匯 | `repositories/hot_money_repository.py::fetch_usdtwd_series`、`repositories/fund/fx_and_main.py::get_latest_fx` | 無 | `fetch_url`；er-api／Frankfurter 另以 `requests` 直打 | TWD：Yahoo→er-api；非 TWD：Yahoo→FRED DEX→er-api→Frankfurter | Actions：2026-11-08 FX 探測 6 代號 ok（日期規則未驗）；Cloud：無 | v2 B 線閘門關閉＝不取數 | 新 UI 尚未接線（閘門）；未經實測 | 轉載 |
| FinMind | 外資買賣超（熱錢卡）| ① | `repositories/hot_money_repository.py::fetch_foreign_flow_series` | `FINMIND_TOKEN`·S（選填；**總經頁只讀 `os.environ`**，見附錄 B #2）| `fetch_url` | 無；額度用盡有 dataset 專屬退避 | STATE 2026-07-11：外資卡曾顯示 106 天未更新（當時 UI 問題）；近期 Actions／Cloud：無 | **否** | 缺 Secret（讀取不一致，INFERENCE）；新 UI 尚未接線 | FACT／INFERENCE |
| FinMind | NDC 景氣燈號 | ③ 單基金（Z 門檻）| `ui/helpers/macro/ndc.py::get_ndc_status`→`fetch_ndc_signal_history` | `FINMIND_TOKEN`·S（`get_secret`）| `fetch_url` | 失敗退預設門檻 | 無 | 否（v2 規格 pending 不取數）| 新 UI 尚未接線；未經實測 | 轉載 |
| 多源 | 台灣 PMI 9 源賽跑、出口 YoY（海關 6053）、外資連續買賣超日數 | 無（`app.py` 可達鏈上 0 呼叫）| `repositories/macro_tw_local_repository.py::fetch_tw_pmi_local`、`fetch_tw_export_yoy` | 外資連續日數需 `FINMIND_TOKEN` | `fetch_url` | 賽跑首命中 | 無 | 否 | 未經實測 | 轉載；「0 caller」單組 grep、未經第二組驗證 |
| Stooq | `^vix3m`／`^vxv`／`^cpc`／`^cpce` | ① 雷達 | `repositories/external_market_repository.py::fetch_stooq_csv` | 無 | `fetch_url` | VIX3M 第 3 層；Put/Call 第 2 層 | STATE 2026-06-30：`^cpc` 無法解析 | 否 | 來源停供（`^cpc`）；其餘未經實測 | 轉載 |
| Cboe CDN | VIX3M 歷史 CSV；Put/Call CSV | ① 雷達 | `fetch_cboe_csv`、`fetch_cboe_pcratio_csv` | 無 | `fetch_url` | VIX3M 第 2 層；Put/Call 末層 | STATE：Put/Call 檔末筆停在 2019-10（凍結檔），程式以 30 天時效拒用 | 否 | 來源停供或欄位改變 | 轉載 |
| AAII | 散戶情緒 | ①（美股流動性）| `repositories/macro/alternate.py::fetch_aaii_sentiment` | 無 | `fetch_url` | 3 段 URL | STATE 2026-07（user 回報，Cloud）：被 Cloudflare 攔截 | 否 | Cloud 網路限制／來源阻擋 | 轉載 |
| DefiLlama | 穩定幣市值 | ① 流動性 | `repositories/macro/alternate.py::fetch_defillama_stablecoin_mcap` | 無 | `fetch_url` | 無（該因子 N/A）| 無 | 否 | 未經實測 | 轉載 |
| MacroMicro／ISM World／DBnomics／FRED 代理 | 美國 PMI 備援鏈（5 段）| ① | `repositories/macro/alternate.py::fetch_ism_pmi` | 後二段需 `FRED_API_KEY`·S | `fetch_url` | MacroMicro→ISM World→DBnomics→Phil Fed（代理）→OECD（概念替代）；全敗回空值不填 | 無；HTML 抓取易改版（INFERENCE）| 否 | 未經實測 | 轉載 |
| open.er-api／Frankfurter | 匯率備援 | ②③④ | `get_latest_fx`（同上）| 無 | `requests` 直打＋`get_proxy_config` | 見上 | 無 | 否 | 未經實測 | 轉載 |
| 5 RSS（MarketWatch、Yahoo、CNBC×2、BBC）| 國際財經新聞 | ④ T7 帳本顧問按鈕（總經頁新聞卡灰態不取數）| `repositories/news_repository.py::fetch_market_news` | 無 | `fetch_url` | 單 feed 失敗跳過 | 無 | 否 | 新 UI 尚未接線；未經實測 | 轉載 |
| Google News RSS | 個股新聞 | ③ 持股新聞按鈕 | `fetch_stock_news` | 無 | `fetch_url` | — | 無 | 否 | 未經實測 | 轉載 |
| TWSE／TPEX／CBC／MOF | 官方端點 | 無（僅 scripts／探針 workflow）| — | — | — | — | — | 否 | 舊 UI 本來就沒有 | 轉載；單組 grep |

### A.2 基金資料

| 供應者 | 資料 | 舊 UI 入口 | 實際函式 | Secret | Proxy | fallback | 證據 | v2／v3 | 問題分類 | 標籤 |
|---|---|---|---|---|---|---|---|---|---|---|
| MoneyDJ www | meta、NAV、績效 wb01、風險 wb07、持股、配息 | ②③④管理室（經 `auto_fetch_moneydj`）| `repositories/fund/fund_orchestration.py::fetch_fund_from_moneydj_url`；`nav_metrics.py::fetch_nav` | 無 | `fetch_url` | 瀑布靠後（見附錄 B #11）；程式註解稱 Cloud 被封（無日期，舊）| Actions：2026-10-14 基本頁 8 碼 200；NAV 探針 2026-10-29～11-09；Cloud：無 | **是**（`nav_dividend`、`exp_profile`）| Cloud 網路限制（舊註解）；未經實測 | 轉載 |
| MoneyDJ tcbbankfund（合庫）| NAV、meta、配息 | 同上 | `repositories/fund/sources.py::_src_tcb_nav`／`_src_tcb_meta`／`_src_tcb_div` | 無 | `fetch_url` | 瀑布第 4 | Actions：2026-10-14 探針部分頁型直連 404；NAS 路徑另有逾時紀錄；Cloud：無 | 是（同上）| 來源停供或欄位改變（頁型 404，原因未定）；逾時 | 轉載 |
| MoneyDJ chubb／保單商子網域／銀行平台 | NAV、持股 | 同上 | `_src_tcb_nav`（含 chubb）、`_src_insurance_subdomain_nav`、`_src_bank_platform_nav` | 無 | 多為 `fetch_url`；`_src_bank_platform_nav` 為裸 `urllib` | 子網域為推測名稱 | 幾乎無專屬證據 | 間接 | 未經實測 | 轉載；FACT：銀行平台函式用裸 `urllib`（附錄 B #7）|
| TDCC OpenAPI | 境外清單、名稱、最新 NAV（3-4）、搜尋 | ③ 找代號、meta 備援 | `sources.py::_tdcc_get`、`_src_tdcc_meta`、`tdcc_search_fund` | 無 | **裸 `urllib`**（靠全域 opener）| meta 最終備援 | Actions：2026-07-22 3-4 回 0 筆；2026-10-14 清單 5295 列、MoneyDJ／保單碼 0 命中 | 部分（`declared_profile.fetch_tdcc_listing`）| 來源欄位改變／代碼體系不符；Cloud 網路限制待驗 | FACT（裸 urllib）／轉載 |
| FundClear SmartFundAPI | 境外 NAV、meta、配息 | 同 MoneyDJ 列 | `_src_fundclear_nav`／`_src_fundclear_meta`／`_src_fundclear_div` | 無 | `fetch_url` | **NAV 第 2 外部源**（Allianz 之後）| Actions：2026-10-14 `GetFundBasicInfo` 9/9 回非 JSON，原因未知；Cloud：無 | 是（`fetch_fundclear_declared_ccy`）| 來源停供或欄位改變（未確認）| 轉載 |
| FundClear 搜尋／境外觀測站 | 關鍵字搜尋；20 年歷史 NAV | 找代號；觀測站函式無入口 | `tdcc_search_fund_with_error` 備援段；`repositories/fundclear_offshore.py` | 無 | 自帶 `get_proxy_config` | — | 觀測站端點未驗 | 搜尋入口新 UI 已裁示取消 | 觀測站取數函式 0 production caller（附錄 B #5）| FACT（單組 grep）|
| 鉅亨 cnyes | NAV、配息、持股 | 同 MoneyDJ 列 | `sources.py::_src_cnyes_nav`、`fetch_holdings_cnyes` | 無 | `requests`＋`proxies=`，**無 403 降級直連與退避**（附錄 B #6）| NAV 第 3 | STATE 2026-07-22：Actions 端全掛；Cloud 客戶自述抓得到（非機器證據）| 否 | Actions：Cloud 網路限制；Cloud：未經實測 | FACT（程式）／轉載 |
| Allianz 投信 | 5 檔 NAV、meta | 同上 | `sources.py::_src_allianzgi_nav`／`_src_allianzgi_meta` | 無 | `requests.post`＋`proxies=`，無 403 降級 | **NAV 第 1** | STATE 2026-07-22：Actions 端改版或被擋 | 否 | 來源停供或欄位改變／Cloud 網路限制（未定）| FACT（程式）／轉載 |
| Morningstar | NAV（保單／LU）、meta、持股 | 同上（保單碼）| `_src_morningstar_nav`、`_morningstar_search_secid`、`fetch_holdings_morningstar` | 無 | NAV／搜尋：裸 `urllib`；持股：`requests`＋`proxies=` | 瀑布靠後 | 無機器證據 | 否 | 未經實測 | FACT（裸 urllib）／轉載 |
| Yahoo 基金（secId.F）| 保單／LU NAV | 同上 | `_src_yahoo_finance_nav`、`_yahoo_search_secid_by_isin` | 無 | 裸 `urllib` | Morningstar 之後 | 同上 | 否 | 未經實測 | FACT（裸 urllib）／轉載 |
| Alpha Vantage | 保單基金 NAV | 同上 | `_src_alphavantage_nav` | `ALPHAVANTAGE_API_KEY`·S（Actions 未傳入；`secrets.toml.example` 未列）| 裸 `urllib` | Yahoo 之後 | 無 | 否 | 缺 Secret 時略過；未經實測 | FACT（裸 urllib）／轉載 |
| SITCA | 境內 meta／NAV | 同上 | `_src_sitca_meta`／`_src_sitca_nav` | 無 | `fetch_url` | NAV 第 6 | 無 | 否 | 未經實測 | 轉載 |
| Franklin／JPMorgan／台灣人壽官網 | 保單基金 NAV | 同上 | `_src_franklin_nav`、`_src_jpmorgan_nav`、`_src_taiwanlife_nav` | 無 | 裸 `urllib`／部分 `fetch_url` | 瀑布末段 | 端點為推測 | 否 | 未經實測 | FACT（順序）／轉載 |
| 本機 `cache/nav` | NAV 備援 | live 全敗時 | `sources.py::_src_cache_files` | 無 | 本地 | `fetch_nav` 最後一步 | 目前只有一檔；產生者不明 | 間接 | 快取或增量缺陷 | 轉載 |

### A.3 Google、AI、Proxy

| 供應者 | 資料／用途 | 舊 UI 入口 | 實際函式 | Secret | Proxy | fallback | 證據 | v2／v3 | 問題分類 | 標籤 |
|---|---|---|---|---|---|---|---|---|---|---|
| Google Sheets（服務帳戶）| 政策、帳本、選股池、NAV 累積、權重、績效 | ④②管理室 | `repositories/policy/v1.py::load_policies`、`repositories/pool_repository.py::list_pool`、`services/nav_history_gs.py`、`services/macro/weights_store.py` | `google_service_account`·S／A（名稱 `GOOGLE_SERVICE_ACCOUNT`）；`POLICY_SHEET_ID`、`POOL_SHEET_ID`（**無預設**，附錄 B #10）、`NAV_SHEET_ID`（有 baked 預設）、`MACRO_WEIGHTS_SHEET_ID` | 不經 Proxy | 服務帳戶優先，開不了該表才回退使用者 OAuth | 無 Cloud 成功紀錄 | 部分（`alo`、`exp_universe`、`nav_dividend`）| 缺 Secret 時降級；未經實測 | 轉載 |
| Google OAuth／Drive | 個人登入、個人試算表 | 側欄登入 | `infra/personal_oauth.py`、`ui/helpers/io/oauth_state.py` | `[google_oauth]`·S | 不經 Proxy | — | 無 | 是（ui_v2 `alo`、ui_v3 `assets_source`）| 缺 Secret／認證失敗（未驗）| 轉載 |
| Gemini | 解盤、摘要、顧問 | ②③④管理室 | `infra/llm.py`、`services/ai_service.py` | `GEMINI_API_KEY*`·S（`_load_keys` 鏡射）| `requests.post` 直連，不經 NAS | 多把輪替；Anthropic／OpenAI 為後備 | 無 | **否**（對 AI 模組 import 為 0）| 缺 Secret 時降級；未經實測 | FACT（0 import）／轉載 |
| Anthropic／OpenAI | LLM 後備 | 同上 | `infra/llm.py` | `ANTHROPIC_API_KEY`／`OPENAI_API_KEY`·S | 直連 | 缺則略過 | 是否設定：未驗 | 否 | 未經實測 | 轉載 |
| NAS Proxy | 全部經 `fetch_url` 的來源 | 全站 | `infra/proxy.py::get_proxy_config`、`fetch_url`、`install_global_urllib_proxy` | `PROXY_URL`／舊 `[proxy]` 區段·S（**只讀 `st.secrets`**）；Actions 有同名 secret 但**腳本實際未使用**（附錄 B #4）| — | 407 立即 None；403×2→直連；ProxyError→直連 | Actions：NAV 等價探針的 NAS 路徑有效（探針腳本自建 Session，不經 `infra.proxy`，轉載）；Cloud：僅 2026-07-22 客戶自述 | — | Cloud 網路限制待驗；407 帳密錯誤無紅色出口 | FACT／轉載 |

**問題分類彙整（不混為一談）**：缺 Secret＝FinMind 讀取不一致、Alpha Vantage 未列範例；認證失敗＝無任何已確認案例；Cloud 網路限制＝Actions 端 cnyes／Allianz／AAII 的歷史紀錄，Cloud 端皆未驗；來源停供或欄位改變＝Yahoo `^CPC`／`^CPCE`、Stooq `^cpc`、Cboe Put/Call 凍結檔、FundClear 非 JSON（未定）、TDCC 3-4；快取或增量缺陷＝`fred_indicators` 的 CPI／M2／PPIACO／PCOPPUSDM／DTWEXBGS（A1 報告）；新 UI 尚未接線＝見 §0A(a)；未經實測＝其餘。

## 附錄 B　本組自行抽查（13 項；`git grep`／讀碼，排除 tests，單組）

基準確認：`git diff --stat 21a68bc0 HEAD -- '*.py'` 輸出為空＝本分支與 `21a68bc0` 的 `*.py` 無差異（FACT）。

| # | 草稿宣稱 | 本組結果 |
|---|---|---|
| 1 | `page_01_macro` 才是現行舊總經頁；`tab1_macro::render_macro_tab` 在 `app.py` 無人呼叫 | **屬實**。`app.py` 匯入並呼叫 `render_market_overview`；`render_macro_tab` 僅見定義與註解／docstring 提及，無呼叫點。限制：單組 grep，可能漏動態呼叫 |
| 2 | `page_01_macro` 以 `os.environ` 讀 `FINMIND_TOKEN`；`_load_keys` 不鏡射 | **屬實**。`_load_keys` 只鏡射 FRED／GEMINI／ANTHROPIC／OPENAI；`app.py` 內 FINMIND 僅出現在註解 |
| 3 | `infra.proxy` 只讀 `st.secrets` | **屬實**。`get_proxy_config` 只檢查 `st.secrets`，例外時快取為空設定 |
| 4 | `update_macro_history.py` 的 proxy 路徑指向不存在模組；Actions 的 `PROXY_URL` 實際未使用 | **屬實**。`infra/` 下只有 `proxy.py`，無 `proxy_helper`；`repositories/macro_repository.py` 內無 `fetch_url`；兩條 import 皆失敗後落到**不帶 proxy** 的 `requests.get`；腳本內未讀 `PROXY_URL`。「Actions 實際直連」為 INFERENCE |
| 5 | `fundclear_offshore` 取數函式與 `fetch_nav_history_long` 為 0 production caller | **大致屬實**。`fetch_nav_history_long` 除自身檔外無呼叫；`services/fundclear_backfill.py` 的取數函式（含 `download_and_store`、`find_fund_candidates`）無外部呼叫，只有 `analyze_backfill_conflict` 被 `nav_history_store` 呼叫。單組 grep |
| 6 | cnyes／Morningstar 持股／Allianz 走 `requests`＋`proxies`，無 403 降級 | **部分驗證**。cnyes（`nav_metrics`、`sources`）與 Allianz（`requests.post`）確認為 `requests`＋`proxies=_proxies()`，未經 `fetch_url`；Morningstar 持股本組未逐行驗，屬轉載 |
| 7 | TDCC、Morningstar 搜尋、Yahoo 基金、Alpha Vantage 用裸 `urllib`，靠 import 時全域 opener | **屬實**。`_tdcc_get`、`_morningstar_search_secid`、`_morningstar_screener_secid`、`_yahoo_search_secid_by_isin`、`_src_yahoo_finance_nav`、`_av_time_series`、`_src_bank_platform_nav` 內皆為 `urlopen`；`install_global_urllib_proxy` 於 `infra/proxy.py` import 時執行，**無 proxy 設定時標記已嘗試而不再重裝**（時序風險為 INFERENCE）|
| 8 | ui_v2 重用清單 | **部分驗證**。FRED 路徑（`market_indicator`／`market_view`）與 MoneyDJ／TDCC／FundClear（`nav_dividend`、`exp_profile`）重用屬實；未見 FinMind 籌碼、新聞、AAII、`get_latest_fx` 的取數呼叫（僅註解或遮蔽名單提及）|
| 9 | ui_v2／ui_v3 完全沒用 AI | **屬實**（範圍：`ui_v2`、`ui_v3`、`services/v2_tables`，對 `ai_service`／`infra.llm` 的 import 為 0）|
| 10 | `POOL_SHEET_ID` 現碼無預設，而 `docs/v2/49` 稱有 | **屬實**。`pool_repository` 無 `_POOL_SHEET_ID_DEFAULT`（測試守衛斷言其不存在）；`docs/v2/49` 的「寫死的試算表 ID 預設值」列仍列出它。草稿 B 標示的章節位置（§1.1）本組未核對，列名以實際列為準 |
| 11 | `fetch_fund_multi_source` docstring 與瀑布順序不符 | **屬實**。docstring 寫 NAV：快取→FundClear→鉅亨→TCB→SITCA；`_fetch_fund_single` 實際先 Allianz，之後 FundClear→cnyes→tcb→保單子網域→SITCA→銀行平台→Morningstar→Yahoo→Alpha Vantage→Franklin／JPMorgan→台灣人壽 |
| 12 | 4 小時過期文案只在 `tab1_macro` | **屬實**（`page_01_macro` 無此門檻；而該頁 `app.py` 不呼叫 → 現行畫面看不到）|
| 13 | 草稿 A 指出 SEC 文件把 `tab1_macro` 當現行取數者 | **屬實**，已於本文件 §1.2、§2.1、§2.3、§5.1 就地更正（舊句劃線保留）|

**被推翻的草稿宣稱**：無。一處細節以本組驗證為準：草稿 B 把 POOL 預設值不符標在 `docs/v2/49` §1.1，實際該文字在同檔另一列（見 #10）。其餘未抽查的列（Stooq、Cboe、AAII、各探針日期與筆數、STATE 引述）標「轉載」。

## 附錄 C　與既有盤點（`docs/evidence/international_market_source_inventory_2026_11_09.md`）不一致或未涵蓋處（不改該報告）

1. 該盤點未涵蓋（本組以其全文 grep 草稿所述，未逐列重驗）：Put/Call（Yahoo `^CPC`／`^CPCE`、Stooq、Cboe pcratio）、AAII、DefiLlama、`BTC-USD`、`HYG`／`LQD`、板塊 ETF、海關 6053、Alpha Vantage、RSS 取數入口。本附錄 A 補之。
2. 本文件前一版（本檔 §1.2、§2.1、§2.3、§5.1）把 `ui/tab1_macro.py` 當現行舊總經頁取數者、把 `page_01_macro` 的 `FINMIND_TOKEN` 讀法寫成 `get_secret`：均已更正（舊句劃線保留）。
3. 該盤點與其他早期文件中凡以 `tab1_macro` 為現行總經頁取數者的敘述，本組**未逐句核對**，需另行複核；依本組 `git grep`，`render_macro_tab` 在 `app.py` 無呼叫點。
4. 該盤點基準為較早的 main（`558fc00f`），本文件基準為 `611170a5` 之上的本分支；期間 `*.py` 變動未逐檔比對（僅確認與 `21a68bc0` 無差異）。
5. `docs/v2/49` 仍稱 `POOL_SHEET_ID` 有寫死預設，與現碼不符（附錄 B #10）。

## 8. 一句話結論

repo 內有足夠證據說明 **Actions 端**資料到 2026-11-05 仍可取得，但對 **Streamlit Cloud 端**，所有 FRED 相關資料目前都是「無法驗證」。最小驗證是請客戶在 Cloud App 內做第 5.1 節的操作並回報畫面文字與資料日期（不含任何 Secret）。
