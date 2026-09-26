# 49｜ui_v2 五頁接真資料規劃

**量測日**：2026-09-26　**基底 SHA**：`16eb828`（開工時確認本地 main 與遠端 main 同為此 commit）　**性質**：規劃文件。

> ⛔ **本文件是規劃，不構成動工授權（`CLAUDE.md` §-1）。**
> 第 3 節的架構是**待裁示的提案**，不是既定結論；第 6 節列的客戶裁示題與總管自決題全部裁完之前，任何一頁都不得開工。
> 本文件本身不改任何 `.py`、不改 `docs/v2/44_fund_ui_ssot.md`（已凍結）。
> **與本文件同輪、唯一的另一處改動**：`tests/test_doc_counters.py` 的 `_MD_DOCS` 具名清單加了本文件一行，並把同檔兩處寫著「31 個 `.md`」的註解同步為 32（總管裁定屬測試與 CI 守衛範圍、由總管自決）。基線檔 `tests/doc_counters_baseline.json` 沒有動。

**讀法約定**

- 引用程式一律寫「路徑＋符號名」，不寫行號（行號每一輪都在漂）。
- 「`44`」指 `docs/v2/44_fund_ui_ssot.md`；「第四節八張表」指該檔第四節的 `holding`／`nav`／`dividend`／`policy`／`market_indicator`／`user_setting`／`fetch_log`／`fund_profile`。
- 「交接檔」指 `docs/handover_2026_09_24.md`。
- 凡是會被一條指令推翻的敘述，旁邊附指令；指令一律把 `16eb828` 寫進去，照跑可重現。
- 「缺口」＝ 在 `16eb828` 上找不到能直接填這一欄的既有實作。「缺口」不等於「做不到」，只表示要新寫東西或要客戶給規則。
- 本文件依交接檔 §12 的體例標示查證狀態：本組查過的寫查過，查不到的寫「查不到」，沒去查的寫「本組沒有查」。

---

## 1. 資料源盤點

### 1.1 總表

| 來源 | 在 repo 裡的取數實作（路徑＋符號名） | 憑證 | TTL／快取 | 發布延遲 | 已知失敗模式 |
|---|---|---|---|---|---|
| **FRED**（美國聖路易聯準銀行 API） | `repositories/macro/fred.py::fetch_fred`（單條序列）、`repositories/macro/fred.py::fetch_fred_batch`（並行預熱，自己不快取）、`repositories/macro/fred.py::fred_get_next_release_date`；序列 ID 常數在 `shared/fred_series.py`（例：`FRED_HY_SPREAD`、`FRED_FED_FUNDS`、`FRED_T10Y2Y`、`FRED_CFNAI`） | `st.secrets["FRED_API_KEY"]`，由 `app.py::_load_keys` 鏡像到環境變數；呼叫時以 `api_key` 參數傳入 | `fetch_fred` 掛 `infra/cache.py::_ttl_cache`（`TTL_30MIN`）；下一次公布日另有磁碟快取目錄 `cache/fred_release`（30 日） | 依序列而定：日頻利差約 T+1；月頻（CPI、就業）月後約 1~2 週且會回溯修正（`CLAUDE.md` §2.3） | 缺 key 回空表且不標失敗；連線失敗走 `infra/proxy.py::mark_fetch_failed_if_retryable`，可重試者不入快取；**404、407、「回 200 但沒有觀測」、「回 200 但 JSON 解析失敗」四種照常快取 30 分鐘**（後兩種是該函式內自註的刻意設計）；失敗與「真的沒資料」兩者都回空 DataFrame，失敗原文不隨回傳值出來（見 1.4） |
| **Yahoo Finance**（chart API） | `repositories/macro/yf.py::fetch_yf_close`（`^VIX`、`USDTWD=X` 等）、`repositories/macro/yf.py::fetch_yf_latest`、`repositories/macro/yf.py::fetch_benchmark_close`；匯率另有 `repositories/hot_money_repository.py::fetch_usdtwd_series`（回 `(DataFrame, 錯誤訊息)`）與 L2 的 `services/fund_service.py::get_fx_rate_by_date` | 不需要金鑰 | `fetch_yf_close` 掛 `_ttl_cache`（`TTL_10MIN`）；`fetch_yf_latest` 掛 `TTL_5MIN`；`fetch_usdtwd_series` 內層 `_cached_usdtwd_series` 掛 `st.cache_data(ttl=TTL_10MIN)` | 收盤資料約美東 16:00 後，換算台灣時間約翌日清晨（`CLAUDE.md` §2.3） | 被限流或網路失敗。`fetch_usdtwd_series` 的失敗分兩支：**上游拋例外那一支回 `(空表, "USDTWD 抓取失敗：<例外字串>")`，這個失敗結果會被 `st.cache_data` 快取 10 分鐘**；Yahoo 回空那一支 raise 內部例外、穿過快取不被存下，對外回 `(空表, "USDTWD 無資料（Yahoo Chart API 失敗或被限流）")` —— **後者是固定字串，不是來源原文**。兩支的處置理由寫在 `_fetch_usdtwd_series_uncached` 的說明表 |
| **MoneyDJ**（主站＋子網域） | 淨值 `repositories/fund/nav_metrics.py::fetch_nav`；配息 `repositories/fund/nav_metrics.py::fetch_div`；績效 `repositories/fund/nav_metrics.py::fetch_performance_wb01`；風險 `repositories/fund/nav_metrics.py::fetch_risk_metrics`；多來源總入口 `repositories/fund/sources.py::fetch_fund_multi_source`；頁型備援序 `repositories/fund/sources.py::get_page_types_to_try`；子網域設定 `fund_fetcher.py` 的 `PORTAL_CFG` | 不需要金鑰；雲端 IP 常被擋，實務上靠 NAS 代理 | 上列四個 `fetch_*` 掛 `infra/cache.py::_daily_cache`（以台灣日曆日為界，隔日零時失效；空結果與失敗結果不入快取，**非空結果一律入快取**） | 淨值 T+1~T+3；配息頁月更或季更 | 子網域 403；HTML 改版。**`fetch_nav` 在所有即時網址都失敗後，退回 `cache/nav/<代碼>.json` 的預存序列**（該處自註為 GitHub Actions 每日預存；`CLAUDE.md` §8.2.A.1 已記載 `fetch_nav_cache.yml` 不存在，本組沒有查那批檔案是否仍在更新），這份序列非空、所以**被 `_daily_cache` 當成成功結果快取到當日結束**；但它**辨識得出來**：`attrs["source"]` 以 `GitHubActions:cache/nav/` 開頭，並帶 `nav_quality`、`cache_updated_at`（見 4.3）。`fetch_div` 以「表格含配息字樣」＋「欄位中第一個介於 0.0001 與 100 的數字」猜金額，解析失敗的列被跳過；**同一個日期只保留一筆、最後只取最近 24 筆**；回傳只有日期與金額，**沒有幣別、沒有入帳日、沒有收益／本金類別** |
| **FundClear**（境外基金） | `repositories/fundclear_offshore.py::get_nav_history`、`list_funds`、`list_classes`、`list_organizes` | 不需要金鑰 | 自帶 md5 磁碟快取 `cache/fundclear`＋節流；`list_organizes` 端點全敗時退回內建已知機構清單 | 境外 NAV 約 T+1 | 端點候選路徑未驗證（檔內自陳）；級別代碼不可傳 `all`；查無資料回欄位齊全的空表。**`get_nav_history` 的回傳帶 `attrs["currency"]`**，是本組找到的少數能交出來源自報幣別的淨值取數 |
| **TDCC**（集保 OpenAPI） | `repositories/fund/sources.py::tdcc_search_fund`（說明寫「搜尋境外基金」）、`tdcc_get_agents`，以及 `fetch_fund_multi_source` 內的境內分流 | 不需要金鑰 | 本組沒有在 `tdcc_search_fund` 上找到快取裝飾器（未逐層追到內部呼叫） | 約 T+1 | 以關鍵字搜尋，不是全量清單；**函式內有 `except Exception: pass`，查詢失敗時回空清單，看不出是失敗還是查無** |
| **Google Sheets**（持倉／保單） | 讀：`repositories/policy/v2.py::load_all_policies_v2`（v2 與 v1 分頁混合相容）、`repositories/policy/v2.py::load_all_policy_worksheets`（⚠️ 名字在 `v2.py` 裡，讀的卻是 **v1 欄位**：它經 `_records_to_policy_df` 對齊到 `repositories/policy/_helpers.py::ALL_COLS`，即 `fund_url`、`policy_tier` 那一套）、`repositories/policy/v1.py::load_policies`；連線：`repositories/policy/_helpers.py::get_gspread_client`、`get_gspread_client_from_oauth`；配額重試 `infra/gspread_retry.py::with_gspread_retry` | 服務帳戶 `google_service_account`，或使用者 OAuth（`[google_oauth]` 區段，讀取點 `ui/helpers/io/oauth_state.py`、流程 `infra/oauth.py`）；試算表 ID 為 `POLICY_SHEET_ID` secret 或使用者在畫面上填的 `policy_sheet_id`（細節見 4.1） | `load_all_policy_worksheets` 有 60 秒手動 TTL（`_LOAD_ALL_WS_CACHE`，`gspread.Client` 不可雜湊，故不走 `_ttl_cache`）；**`load_all_policies_v2` 本身沒有任何快取** | 即時（使用者手動維護） | 配額 429（`repositories/snapshot_repository.py` 的註解記載每使用者每分鐘 60 次讀取，本組沒有對 Google 官方文件查證）；**兩個讀取函式都在單一分頁讀失敗時 `except Exception: continue` 略過該分頁**，那一張保單的基金整批從結果裡消失，回傳值看不出來；`load_all_policy_worksheets` 還會把這個缺了分頁的結果快取 60 秒（見 4.3） |
| **Google Sheets**（交易帳） | `repositories/ledger_repository.py::load_all_ledgers`，讀系統分頁 `_Ledgers`（欄位 `LEDGER_COLS`：`policy_id`、`date`、`code`、`action`、`units`、`nav_at_action`、`twd`、`fee`、`note`） | 同持倉 | 本組沒有找到快取 | 即時 | 打不開試算表或找不到分頁時回空表（不拋）；逐欄正規化用 `_norm_float`，**空白與無法解析的值一律變成 0.0**（見 1.3 出入 7）；`repositories/policy/v2.py` 檔頭註明 v2 schema「不需要 `_Ledgers`」，所以 v2 使用者的這張分頁可能是空的或舊的 |
| **Google Sheets**（持倉快照） | `repositories/snapshot_repository.py::load_all_ledgers_snapshot` 讀 `_T7_State`（欄位 `SNAPSHOT_COLS`，每檔一列 JSON）；`_持倉總覽`（欄位 `HOLDINGS_COLS`：保單號碼、基金代碼、基金名稱、幣別、級別、持有單位數、平均成本淨值、平均含息成本、平均匯率、投資金額(TWD)、現金給付%、累積已領配息(TWD)、更新時間）**只有寫入函式 `save_holdings_overview`，本組找不到讀取函式** | 同持倉 | 本組沒有找到快取 | 由舊分頁寫入時更新 | `_T7_State` 打不開時回空 dict；單列 JSON 解析失敗時 `continue` 略過 |
| **Google Sheets**（淨值累積） | `services/nav_history_gs.py::load_series`、`load_points`、`coverage_status`、`append_points` | 服務帳戶；試算表 ID 為 `NAV_SHEET_ID` secret，**缺時退回檔內寫死的 `_NAV_SHEET_ID_DEFAULT`** | `services/nav_history_gs.py` 模組內**本組沒有找到快取裝飾器**；舊分頁 `ui/tab5_data_guard.py::_cached_nh_coverage` 以 `st.cache_data(ttl=TTL_5MIN)` 包了 `coverage_status`（那是 L3 的快取，不是本模組的） | 由使用者日常使用累積，每日至多一筆 | 該檔 gspread 往返未登錄於 `EXCEPTIONS.md` 例外表，已記在 `tests/test_services_purity_contract.py` 的 `GSPREAD_DEBT`（登記不等於核准） |
| **Google Sheets**（選股池） | `repositories/pool_repository.py::list_pool`（Sheets 或本地 JSON 兩後端）；代碼查表 `_cached_pool_map`、對外入口 `_pool_map_or_empty` | 服務帳戶或注入的使用者 OAuth；試算表 ID 為 `POOL_SHEET_ID` secret，**缺時退回檔內寫死的 `_POOL_SHEET_ID_DEFAULT`** | `list_pool` 本身沒有快取；`_cached_pool_map` 以 `st.cache_data(ttl=TTL_30MIN)` 快取「代碼 → 條目」對照表：讀失敗會拋、不入快取；**真的是空池時，空對照表會被快取 30 分鐘**（空池是合法狀態）；`_pool_map_or_empty` 在冷卻中或讀失敗時回空 dict | 即時 | `get_pool_store` 在「沒有服務帳戶、也沒有注入 OAuth」時退回本地 JSON，雲端檔案系統重開即消失（`pool_backend_status` 會回 `"local"` 供畫面警告）；本地 JSON 檔壞掉或內容不是清單時，`LocalJsonPoolStore._read` 印一行 log 後回空清單 —— **壞檔被當成空池，而空池會被 `_cached_pool_map` 快取 30 分鐘** |
| **FinMind**（台灣總經、外資） | 景氣指標 `repositories/macro_tw_local_repository.py::fetch_ndc_signal_history`（內部呼叫私有函式 `_finmind_business_indicator`）；外資 `repositories/hot_money_repository.py::fetch_foreign_flow_series` | `FINMIND_TOKEN`（可選，未設走匿名額度；讀取點見 4.1） | `fetch_ndc_signal_history` 掛 `_ttl_cache`（`TTL_15MIN`），**失敗結果（帶 `error` 欄的 dict）也會被快取 15 分鐘**（本組在 `EXCEPTIONS.md` 查不到這一點的登記；該檔的 `P-NDCCACHE-1` 登記的是另一件事：`ui/helpers/macro/ndc.py::_cached_ndc_score` 在 UI 層又疊了一層同 TTL 的快取）；外資內層 `st.cache_data(ttl=TTL_30MIN)` | 景氣指標月後約 5~10 天 | 402 額度用盡、401 token 失效；`fetch_ndc_signal_history` 以 `error` 欄位交出失敗原文 |
| **台灣 PMI 九源** | `repositories/tw_pmi_repository.py`＋`repositories/macro_tw_local_repository.py::fetch_tw_pmi_local` | 不需要 | 見該檔 | 月頻 | 與本規劃五頁無直接對應欄位，列出僅供完整 |
| **NAS 代理** | `infra/proxy.py::fetch_url`、`infra/proxy.py::get_proxy_config` | `st.secrets["PROXY_URL"]` 或 `[proxy]` 區段 | — | — | 407 代理驗證失敗；代理失效自動降級直連 |
| **來源退避** | `infra/source_backoff.py::should_skip`、`record_failure`、`get_backoff_state`；冷卻秒數 SSOT 在 `shared/backoff_policy.py`（`BACKOFF_COOLDOWN_SEC`、`NO_COOLDOWN_KINDS`）；Sheets 另有 `infra/gspread_retry.py::should_skip_gspread` | — | 以 host（或 Sheets 的 actor＋試算表）為單位的冷卻狀態，不存任何回傳值；狀態存在行程記憶體裡 | — | 冷卻中 `fetch_url` 直接回 `None`，與「真的打了但失敗」回傳相同 |

### 1.2 TTL 常數與快取裝飾器（本組讀過的）

- `shared/ttls.py`：`TTL_1MIN`、`TTL_5MIN`、`TTL_10MIN`、`TTL_15MIN`、`TTL_30MIN`、`TTL_1HOUR`，另有字串常數 `TTL_TODAY`。
- `infra/cache.py::_ttl_cache`：秒數 TTL，不快取例外；`infra/cache.py::_daily_cache`：台灣日曆日為界，預設空結果與失敗結果不入快取。
- `infra/cache.py::register_cache`、`clear_all_caches`、`get_all_cache_info`、`global_refresh_all`：登記、清除、盤點。
- 上列快取全部住在**單一行程的記憶體**（`st.cache_data` 同樣是每個 Streamlit 行程各自一份）。部署形態對它們的影響見 4.8。

### 1.3 與 `CLAUDE.md` 或既有說明對照時發現的出入（逐條到程式碼核對過）

| # | 既有寫法 | `16eb828` 上的實況 | 對本規劃的影響 |
|---|---|---|---|
| 1 | `CLAUDE.md` §2.1 T1 列仍點名 CBC ms1.json（M1B/M2） | 該列自己已註明實作已刪；`repositories`、`services` 底下查不到 CBC 取數（指令見下） | 若「政策利率」要用台灣央行，屬缺口 |
| 2 | `fetch_fred` 的說明寫 `realtime_start` 約等於真實發布日 | 呼叫時沒有帶任何 vintage 參數；依 FRED 官方文件，未指定時 `realtime_start` 預設為**查詢當天**。本環境不發網路請求，本組沒有實測 | 若拿它填 `market_indicator.release_date`，可能把每一筆的公布日都寫成今天 —— 那是捏造，見 4.5 |
| 3 | `_finmind_business_indicator` 說明列出 `leading`／`coincident`／`lagging` 三欄 | 實際只保留 `monitoring`、`monitoring_color`、`leading` 三欄，`coincident` 被丟掉（指令見下）；而且它是私有函式，公開的 `fetch_ndc_signal_history` 只交出對策信號分數 | `coincident_index` 在 L1 取回後就沒了；`leading_index` 雖有取回但沒有公開出口 |
| 4 | `shared/fred_series.py::FRED_LEI`（`USSLIND`） | 同檔註明已停更、僅作舊參照；`services/macro/us_indicators.py` 在 LEI 那一段註明**改用 CFNAI（`FRED_CFNAI`）作為替代**，並註明兩者數值意涵不同、門檻另訂 | 若「領先指標」要用美國版，現有可用的是 CFNAI，而它是「活動指數」，不是同一個指標，屬業務定義題（Q2） |
| 5 | 基金基本資料的幣別 | **預設值不一致**：`repositories/fund/sources.py` 的 `_src_fundclear_meta`、`_src_fundclear_div`、`_src_direct_moneydj_url`、`_src_tcb_meta`、`_src_tdcc_meta` 缺幣別時預設 **USD**；`repositories/fund/fund_orchestration.py` 內亦有「計價幣別」缺欄預設 USD 的寫法；**唯獨 `_src_allianzgi_meta` 預設 TWD** | 見下一列與 4.6 |
| 6 | `repositories/fund/fund_orchestration.py::_correct_currency`、`_ensure_currency` 依名稱修正幣別 | 它**只在目前值為空或 USD 時才動手**，依序用「名稱內的幣別字樣 → 選股池登記的幣別 → 名稱含台灣就推定 TWD」修正；目前值已是其他幣別（含 Allianz 預設出來的 TWD）時**原樣回傳** | 所以 Allianz 的 TWD 預設**修不到**；而修得到的那些，修出來的也是**推測值**。轉換層一律不得把預設或推測出來的幣別當成真值（見 2.7） |
| 7 | `repositories/ledger_repository.py::_norm_float` | 空值、空字串、純空白、無法解析的字串，一律回 `0.0` | 若拿 `_Ledgers` 推單位數或成本，空欄會被算成 0 —— 與 `44` 第四節「不以零補」直接衝突 |

驗證指令（每條都把基底 SHA 寫在指令裡）：

- 出入 1：`git grep -n -E "\bCBC\b|重貼現" 16eb828 -- 'repositories/*.py' 'repositories/**/*.py' 'services/*.py' 'services/**/*.py'` → 無輸出（exit=1）。正控：`git grep -c -E "\bCBC\b" 16eb828 -- shared/api_endpoints.py` → `shared/api_endpoints.py:1`，表示同一個字樣在別處抓得到。
- 出入 3：`git grep -c "coincident" 16eb828 -- repositories/macro_tw_local_repository.py` → 1 行命中，且那一行是說明文字；保留欄位清單那一行用 `git grep -n -E "'leading'\)" 16eb828 -- repositories/macro_tw_local_repository.py` 可看到清單只列三個欄名。
- 出入 5：`git grep -n "計價幣別\", \"TWD\"" 16eb828 -- repositories/fund/sources.py` → 1 行命中（位在 `_src_allianzgi_meta`）；對照組 `git grep -c "計價幣別\", \"USD\"" 16eb828 -- repositories/fund/sources.py` → 3 行命中（`_src_direct_moneydj_url`、`_src_tcb_meta`、`_src_tdcc_meta` 各一；`_src_fundclear_meta`、`_src_fundclear_div` 的 USD 預設寫法不同，這條指令不含它們）。
- 出入 6：`git grep -n -E "def (_correct_currency|_ensure_currency)" 16eb828 -- repositories/fund/fund_orchestration.py` → 2 行命中。

### 1.4 失敗原文拿不拿得到（決定 ⛔ 能不能照 `44` 誠實呈現）

`44` 的 `fetch_log.message` 要求存「來源回傳的原始字串，不改寫也不截斷」，各頁的取數失敗文案也要照印原文。
依交出錯誤的方式，現有取數函式分三類：

| 類 | 交出錯誤的方式 | 代表 |
|---|---|---|
| 甲 | 回傳值裡直接帶錯誤字串 | `fetch_usdtwd_series`、`fetch_foreign_flow_series`（回 tuple 第二個值；但其中有些是固定字串，不是來源原文，見 1.1）；`fetch_ndc_signal_history`（`error` 欄）；`load_all_policies_v2` 在整本打不開時 raise `PolicySheetError` |
| 乙 | 只回空值，原因只寫到 stdout 或標記裡 | `fetch_fred`（空 DataFrame）、`fetch_yf_close`（空 Series）、`fetch_nav`（即時網址與預存檔都失敗時回空 Series；退回預存舊序列那一支不是失敗，可由 `attrs` 辨識，見 4.3）、`fetch_div`（空 list） |
| 丙 | 例外被吞，呼叫端完全看不到 | `load_all_policies_v2`／`load_all_policy_worksheets` 的單一分頁失敗；`tdcc_search_fund`；`load_all_ledgers` 打不開試算表時；既有 L2 門面如 `services/fund_service.py::get_latest_vix`（`except Exception` 回 `None`） |

⚠️ 本表是分類敘述，不是窮舉。未涵蓋：`repositories/fund/sources.py` 內的各 `_src_*` 內部來源（該檔在 `16eb828` 上有 25 個以 `_src_` 開頭的函式，指令：`git grep -c -E "^def _src_" 16eb828 -- repositories/fund/` → `repositories/fund/sources.py:25`，同目錄其他檔 0 命中）、`fundclear_offshore.py` 的錯誤型別、`pool_repository.py` 的兩個後端。
⚠️ 把失敗原文交出來還有一個**金鑰外洩**的問題，另見 4.9 與 Q13。

---

## 2. 每頁接什麼

### 2.0 共通：換資料的接縫在哪裡

五頁的 `page.py` 各自呼叫 `fixtures` 取得資料，再交給 `logic.build_page_model`。**五頁交出去的東西外形不同**（以下是本組在 `16eb828` 上實際呼叫 fixtures 印出的鍵）：

| 頁 | `page.py` 內的呼叫 | fixtures 回傳的外形 |
|---|---|---|
| mkt | `fixtures.all_datasets()`，再以 `?scenario=` 挑一份 | `{rows, errors}`；`rows` 就是 `market_indicator` 的列，設定值不在裡面，由頁面輸入與 `st.session_state` 傳入 |
| hld | `fixtures.scenario(名)`，展開成 `build_page_model(**…)` 的參數 | `{dataset, 部分情境另帶 fields}`；`dataset` 內為 `holding`、`nav`、`dividend`、`policy`、`fund_profile`、`user_setting`、`errors`。**`fields` 是使用者輸入欄的狀態，不是資料** |
| exp | `fixtures.scenario_with(名, save_failed=…)` | `{dataset, compare_checked, watch_checked}`，部分情境另帶 `draft_rules`；`dataset` 內為 `fund_profile`、`nav`、`dividend`、`user_setting`、`div_ratio_pct`、`errors`、`save_errors`。**兩組勾選狀態與 `draft_rules`（條件欄的當下內容）是 UI 狀態，不是資料** |
| alo | `fixtures.scenario_with(名, save_failed=…)` | `holding`、`nav`、`policy`、`market_indicator`、`user_setting`、`errors`、`save_errors` |
| set | `fixtures.scenario_with(名, save_failed=…)` | `nav`、`dividend`、`market_indicator`、`fetch_log`、`user_setting`、`errors`、`save_errors`、`save_inputs`、`now_utc`、`spec` |

所以接真資料**不是只換一行**：資料與 UI 狀態要拆開，「存檔」「重新取數」要接後端，情境機制與示意字樣要處理，而示意字樣有一部分寫在 `logic.py` 裡。逐項清單見 3.4。

### 2.1 ① 市場總覽（mkt）→ 指標清單

fixtures 只用 `market_indicator` 一張表（`ui_v2/mkt/fixtures.py::SIX_KEYS` 六鍵＋`EXTRA_KEY`）。

| 假資料欄位（`indicator_key`） | 卡 | 建議真實來源 | 現有 L1／L2 函式 | 狀態 |
|---|---|---|---|---|
| `vol_index` | MKT-1 | Yahoo `^VIX` | `repositories/macro/yf.py::fetch_yf_close` | 有 L1 |
| `credit_spread_pct` | MKT-1 | FRED `BAMLH0A0HYM2` | `fetch_fred` ＋ `FRED_HY_SPREAD` | 有 L1；公布日需帶 vintage 參數（技術題 T1） |
| `leading_index` | MKT-2 | 待裁示（Q2） | 台灣：`_finmind_business_indicator`（私有，無公開出口）；美國：只有替代的 CFNAI | **缺口**：沒有公開出口、沒有公布日 |
| `coincident_index` | MKT-2 | 待裁示（Q2） | 台灣：該欄被 L1 丟掉；美國：無 | **缺口** |
| `policy_rate_pct` | MKT-3 | 待裁示（Q1） | 美國：`fetch_fred` ＋ `FRED_FED_FUNDS`（月頻）；台灣：無 | 美國有 L1、台灣為**缺口** |
| `fx_twd_per_usd` | MKT-3 | Yahoo `USDTWD=X` | `repositories/hot_money_repository.py::fetch_usdtwd_series` | 有 L1 |
| `term_spread_pct`（第七鍵） | MKT-5／6／7 | FRED `T10Y2Y` | `fetch_fred` ＋ `FRED_T10Y2Y` | 有 L1；公布日同 `credit_spread_pct` |

`market_indicator` 每一欄怎麼填、第一階段的處置見 2.6（不可空缺口總表）。
⚠️ `ui_v2/mkt/fixtures.py` 目前把 `source_tier` 寫成 `T1`／`T2`（舊五層分級），不在 `44` 值域（`淨值`／`配息`／`市場指標`／`其他`）內；接真資料時照 `44` 寫 `市場指標`。

### 2.2 ② 持倉體檢（hld）→ 持倉、淨值、配息

本頁的報酬、回撤、波動由 `ui_v2/hld/logic.py` 自己算（`return_pct`、`drawdown_pct`、`vol_pct`），只需要原始序列，不需要舊樹的 L2 指標。

**`holding` 的候選來源有三處，各自的欄位覆蓋**（「—」＝該處沒有這一欄）：

| `44` 欄 | 保單分頁（`load_all_policies_v2`，欄名見 `ALL_COLS_V2`） | `_Ledgers`（`load_all_ledgers`） | `_持倉總覽` |
|---|---|---|---|
| `holding_id` | —（可由 `policy_id`＋`fund_code` 組） | — | — |
| `policy_id`／`fund_code` | 有 | 有（`code`） | 有（保單號碼、基金代碼） |
| `fund_name` | 有 | — | 有 |
| `ccy` | 有（`currency`，使用者手填） | — | 有（幣別） |
| `units_shares` | `units`（**選填**） | 可由 `buy`／`sell` 列的 `units` 加總推得 | 有（持有單位數） |
| `cost_orig_ccy` | 可由 `units` × `avg_nav` 推（兩欄都選填） | 可由 `units` × `nav_at_action` 推 | 可由持有單位數 × 平均成本淨值推 |
| `cost_twd` | 有（`invest_twd`） | 可由 `twd` 加總推得 | 有（投資金額(TWD)） |
| `opened_on` | — | 可取最早一筆 `buy` 的 `date` | — |
| `bucket` | `tier`（值域 core／satellite／空） | — | 有（級別） |
| `last_synced_at` | — | — | 有（更新時間） |

三處的共同限制：

- `_Ledgers` 是**唯一**推得出 `opened_on` 的來源，但 v2 schema 已不需要它（`repositories/policy/v2.py` 檔頭），v2 使用者的這張分頁可能是空的或停在舊資料；而且它的 `_norm_float` 會把空欄算成 0（1.3 出入 7）。**本組沒有看過客戶實際試算表，這三處哪一處有資料，查不到。**
- `_持倉總覽` 欄位最齊，但**沒有讀取函式**，要讀它就得新寫 L1。
- 保單分頁的 `invest_twd` 經 `repositories/policy/_helpers.py::parse_invest_twd` 解析，空白會變成 0（業務語意是「這列沒填本金」），與 `44`「不以零補」的讀法要對齊。

`nav`：兩條路。(a) `fetch_nav` 回單一 Series，沒有幣別、沒有推估旗標，失敗時可能退回舊序列（4.3）；(b) FundClear 路徑的 `get_nav_history` 帶 `attrs["currency"]`；(c) `services/nav_history_gs.py::load_series` 為 Sheets 累積序列。
⚠️ `fetch_nav` 吃的是 MoneyDJ 的 `full_key`；Sheets 的 `fund_code` 能不能直接當 `full_key` 用，本組沒有查（`repositories/fund/sources.py::parse_moneydj_input`、`normalize_domestic_code` 是可能的轉換點）。

`dividend`：`fetch_div` 回 `{date, amount, source, fetched_at}`，`date` 是不是除息日本組沒有查頁面欄位語意；沒有 `pay_date`（可空，照填空）、沒有 `ccy`、沒有 `div_kind`（只能寫 `unknown`）。第一階段處置見 2.6。

`policy`：Sheets 只有保單分頁名（即 `policy_id`）；`policy_name`、`issuer`、`premium_paid_twd`、`fee_rate_pct`、`opened_on`、`status` 在 v2 欄位裡都沒有。`DIRECT` 保留列可由轉換層依 `44` 4.4 固定產生。

`fund_profile`（本頁只用 `inception_on`）：`_src_allianzgi_meta` 與 `_src_fundclear_meta` 兩條解析路徑有 `inception_date`；其他來源本組沒有逐一查。⚠️ `fund_profile.dividend_policy` 是不可空欄，Q6 下裁示前 `fund_profile` 一列都寫不進去，本頁也就拿不到 `inception_on`（3.2）。

`user_setting`：鍵為 `hld_window_start`／`hld_window_end`／`hld_deviation_rules`，持久化見 2.7。

### 2.3 ③ 標的探索（exp）→ 基金資料

fixtures 以 `ui_v2/exp/fixtures.py::_universe` 程式生成 128 檔示意基金，另有 `nav`、`dividend`、`user_setting`，以及一份預先給定的 `div_ratio_pct` 示意值。

| 假資料欄位 | 建議真實來源 | 現有函式 | 狀態 |
|---|---|---|---|
| 基金母體（有哪些候選） | 待裁示（Q6 上半） | 候選：`repositories/pool_repository.py::list_pool`（使用者選股池）、`tdcc_search_fund`（境外基金關鍵字搜尋，吞例外）、`repositories/fundclear_offshore.py::list_funds`（逐機構） | **缺口**：沒有一個函式交出「全量母體＋完整基本資料」 |
| `fund_profile.fund_name`／`ccy` | MoneyDJ／各 `_src_*_meta` | `fetch_fund_multi_source` 回傳 dict 的 `fund_name`、`currency` | 有，但**幣別多半是預設值或推測值**（1.3 出入 5、6） |
| `fund_profile.inception_on` | 同上 | `inception_date`（`_src_allianzgi_meta`、`_src_fundclear_meta`） | 部分 |
| `fund_profile.dividend_policy`（`accum`／`dist`） | 無直接欄位 | 現有只有 `dividend_freq`（配息頻率文字） | **缺口**（Q6 下半） |
| `fund_profile.mgmt_fee_rate_pct` | 同上 | `mgmt_fee` | 部分（可空） |
| `nav.nav_date`／`nav_orig_ccy` | MoneyDJ | `fetch_nav` 取最後一筆 | 有；逐檔抓取，母體大時成本高（4.2） |
| `div_ratio_pct`（近 12 個月配息佔淨值比） | 由 `nav`＋`dividend` 計算 | 無 | **缺口**：`44` 只給欄名、沒給算式（Q7）。⚠️ `fetch_div` 只取最近 24 筆且同日只留一筆，月配基金的 12 個月大致夠，但同日多筆配息會被合併掉 |
| `dividend` 表 | `fetch_div` | 同 2.2 | ⚠️ `ui_v2/exp/fixtures.py` 的配息列用了 `div_amount_orig_ccy` 且少 `fetched_at`，與 `44` 第四節的 `div_per_unit_orig_ccy` 不同名；接真資料時照 `44` |
| `nav` 表 | 同上 | 同上 | ⚠️ `ui_v2/exp/fixtures.py::_navs` 的淨值列**沒有 `fetched_at`**，而 `44` 4.2 宣告該欄不可空；接真資料時照 `44` |

### 2.4 ④ 資產配置（alo）→ 持倉、設定

| 假資料欄位 | 建議真實來源 | 現有函式 | 狀態 |
|---|---|---|---|
| `holding` | Sheets | 同 2.2 | 同 2.2 的缺口。**比重基準選「成本」時只需要 `cost_twd` 與 `bucket`**，但 `44` 規定不可空欄位缺值時整列不寫入，所以即使只用兩欄，`opened_on` 等欄缺值仍會讓整列消失（2.6） |
| `nav`（市值基準用最新一筆） | MoneyDJ | `fetch_nav` 取最後一筆 | 有 |
| `market_indicator`：`fx_twd_per_usd` | Yahoo | `fetch_usdtwd_series` | 有；⚠️ 非美元持倉（例：EUR、JPY）在 `44` 裡沒有對應匯率鍵（Q9） |
| `policy` | Sheets | 同 2.2 | 同 2.2 的缺口 |
| `user_setting`：`alo_basis`、`alo_bucket_names`、`alo_target_weights`、`alo_tolerance_pp`、`alo_scenario_input` | — | 見 2.7 | 見 2.7 |

⚠️ 單位字面值：`ui_v2/alo/fixtures.py` 的匯率列 `value_unit` 寫 `TWD/USD`，`ui_v2/mkt/fixtures.py` 對同一個指標鍵寫 `新臺幣／美元`，而 mkt 的 MKT-3 會拿 `value_unit` 比對本卡宣告的單位、對不上就顯示「單位不符」。兩頁共用同一張表時只能有一個字面值（4.6）。

### 2.5 ⑤ 設定與診斷（set）→ 全部

| 假資料欄位 | 建議真實來源 | 現有函式 | 狀態 |
|---|---|---|---|
| SET-1 各資料類的最新 `fetched_at` | 其他四頁轉換層的輸出 | 依賴 2.1~2.4 | 依賴前序；尚未接上的資料類誠實顯示無資料 |
| SET-2 各來源層的最後一次成敗與原文 | `fetch_log` | 舊樹沒有這張表的實作（指令見下） | **缺口** |
| SET-2 補充：目前被冷卻的 host | `infra/source_backoff.py::get_backoff_state` | 有；但顆粒度是 host，不是 `44` 的四個 `source_tier`；而且狀態只在單一行程內（4.8） | 需訂對照規則（技術題） |
| SET-4 參數讀寫 | `user_setting` | 見 2.7 | 見 2.7 |
| SET-5 重新取數 | 清快取＋寫 `fetch_log` | `infra/cache.py::clear_all_caches` 或 `global_refresh_all`（兩者差異見 3.4） | 有清快取；寫 `fetch_log` 為缺口 |
| SET-6 取數紀錄 | `fetch_log` | 無 | **缺口** |
| `spec` 快照 | 維持現狀（`tests/ui_v2/test_set_logic.py` 保證它跟 `44` 一致） | — | 不需要接資料 |
| `now_utc` | 系統時鐘 | — | 現為固定值；接真資料時改讀時鐘（4.5） |

驗證（`fetch_log` 在舊樹沒有實作）：

- `git grep -l "fetch_log" 16eb828 -- '*.py'` 共 10 檔命中，逐檔路徑皆在 `ui_v2/` 或 `tests/ui_v2/` 之下（此為正控：字樣本身抓得到）。
- 把那兩個目錄濾掉：`git grep -l "fetch_log" 16eb828 -- '*.py' | grep -v -E "^16eb828:(ui_v2|tests/ui_v2)/"` → 無輸出（exit=1）。

### 2.6 第一階段怎麼處理每一個不可空缺口

`44` 第四節開頭：「可空」為「否」的欄位若取不到值，該筆不寫入，不以零或空字串補。下表逐欄寫出第一階段的處置與後果。
處置只有三種：**有真值就寫**；**取不到就不寫該列**；**待裁示**（在裁示前一律按「不寫該列」處理）。

| 表.欄 | 現有資料源有沒有值 | 第一階段處置 | 後果 |
|---|---|---|---|
| `market_indicator.release_date`（日頻行情：VIX、USDTWD） | 行情序列只給交易日，沒有獨立的公布日 | 待裁示（Q3）：建議訂一條「日頻收盤行情的公布日＝觀測日」的來源規則 | 裁示前 MKT-1 的波動度、MKT-3 的匯率不寫列 |
| `market_indicator.release_date`（FRED：HY 利差、期限利差、政策利率） | 有，但要帶 vintage 參數才拿得到真的公布日（出入 2） | 技術題 T1，總管自決：實作 vintage 取數；做好之前不寫 | 做好之前那三鍵不寫列 |
| `market_indicator.release_date`（FinMind 景氣指標） | 無 | 待裁示（Q3） | MKT-2 兩鍵不寫列，卡片顯示來源缺 |
| `market_indicator.is_revised` | 現有 L1 只取最新版，不保存前一版 | 行情類：隨 Q3 的來源規則一起裁（行情不回溯修正）；FRED：技術題 T1，以 vintage 比對；其餘：取不到就不寫 | 依上 |
| `holding.opened_on` | 保單分頁、`_持倉總覽` 皆無；`_Ledgers` 可推但可能是空的 | 待裁示（Q4） | 裁示前**每一列持倉都不寫** ⇒ alo、hld 兩頁的持倉表為空，只剩 `44` 已訂的「前往 Sheets 維護持倉」空狀態 |
| `holding.cost_orig_ccy` | 三處都只能推算，且來源欄是選填 | 待裁示（Q4） | 同上 |
| `holding.units_shares` | 保單分頁選填；`_Ledgers`、`_持倉總覽` 可推或有 | 待裁示（Q4） | 同上 |
| `holding.last_synced_at` | 只有 `_持倉總覽` 的更新時間，而 `_持倉總覽` **沒有讀取函式**；其他來源只能用讀取時間 | 待裁示（Q4）：「什麼算一次對帳」是業務語意；裁示前不得以讀取時間冒充 | 即使 Q4 其他欄都補齊，這一欄沒裁之前**每一列持倉仍寫不進去** |
| `holding.holding_id` | 無，可由 `policy_id`＋`fund_code` 組成 | 技術題 T2，總管自決（組法寫死、可重現） | 無 |
| `policy` 的 `policy_name`／`issuer`／`premium_paid_twd`／`opened_on`／`status`／`ccy` | 無 | 待裁示（Q4） | 除 `DIRECT` 外的保單列不寫；掛在那些保單下的持倉如何顯示，由 `logic.py` 既有規則決定，本組沒有逐一追 |
| `nav.ccy` | MoneyDJ 不給；FundClear 路徑有 `attrs["currency"]`；持倉列有使用者在 Sheets 手填的「幣別」 | 技術題 T3：收來源自報的幣別，或持倉列的使用者手填幣別（該欄語意就是這檔基金的計價幣別，與淨值幣別同義）；預設值、名稱推測值一律不收 | 兩者都沒有的基金，淨值不寫列 |
| `dividend.ccy` | `fetch_div` 不給；`_src_fundclear_div` 有這一欄，但缺值時預設 USD，轉換層分不出是來源自報還是預設 | 技術題 T3：**只收來源自報的幣別，不沿用持倉列的幣別**（配息幣別可能與計價幣別不同）；分不出是不是預設值的，一律當成沒有 | 走 MoneyDJ 的基金，配息一列都寫不進去 ⇒ `HLD-3` 期間配息顯示資料未備（Q5 一併請客戶知悉） |
| `nav.is_estimated` | 來源不給 | 技術題 T3：即時公布值寫否；**退回舊序列那一支（4.3）不得寫成一般即時值**，須另行標示或不寫 | — |
| `dividend.div_kind` | 無 | 寫 `unknown`（`44` 4.3 已定義此值） | `HLD-8` 的本金類佔比恆為不適用（Q5） |
| `fund_profile.dividend_policy` | 無 | 待裁示（Q6 下半） | 裁示前 `fund_profile` 整列不寫 ⇒ exp 候選清單為空；hld 的 `HLD-2` 也拿不到 `inception_on` |
| `fund_profile.inception_on`、`ccy` | 部分來源有 | 有真值才寫 | 缺的基金不寫列 |
| `fetch_log` 全表 | 無實作 | 待裁示（Q10、Q12） | set 頁 SET-2／SET-6 顯示無紀錄 |

### 2.7 共通：`user_setting` 與 `fetch_log` 的持久化

`44` 5.3 規定「存檔」寫 `user_setting`、「取數」寫取回的列與 `fetch_log`。舊樹的設定落點分類如下（分類敘述，不是窮舉）：

- **行程內**：舊分頁的設定多住在 `st.session_state`（`ui_v2/mkt/page.py::_on_save` 目前也把存檔寫進 `st.session_state["_user_setting"]` 這個替身）。
- **使用者手動匯出匯入**：`ui/helpers/io/json_backup.py`。
- **可持久化的 Sheets 先例**：`repositories/pool_repository.py`、`services/nav_history_gs.py`、`repositories/portfolio_perf_repository.py`、`services/macro/weights_store.py`（總經權重）。
- **本地檔案**：Streamlit Cloud 的檔案系統重開即清空，不是可靠的持久化。

驗證（`44` 的 `user_setting` 鍵名在舊樹沒有被任何程式讀寫）：`git grep -l -E "mkt_window_days|hld_window_start|alo_target_weights" 16eb828 -- '*.py'` → 命中檔全在 `ui_v2/` 或 `tests/ui_v2/` 之下（正控）；加上 `| grep -v -E "^16eb828:(ui_v2|tests/ui_v2)/"` → 無輸出（exit=1）。
⚠️ 這只證明「那幾個鍵名沒被讀寫」，不證明舊樹沒有其他形態的設定表；上面的分類就是為此而寫。

後端選哪裡、分頁怎麼切屬技術題（T4，總管自決）；**會不會在客戶的 Google 帳號裡新建試算表**屬客戶同意事項（Q10）。

### 2.8 接真資料時必須保留的行為

| 行為 | 來源規格 | 接真資料時的具體要求 |
|---|---|---|
| 失敗用 ⛔ 誠實呈現 | `44` 各塊空狀態；`CLAUDE.md` §1 | 轉換層把失敗原文放進 `errors[鍵]`（遮蔽規則待 Q13）；乙類、丙類函式（1.4）要先補出錯誤原文，不能讓頁面只看到空表而誤判成「資料未備」 |
| 缺值不得補值 | `CLAUDE.md` §1；`44` 第四節 | 轉換層不得以 0、空字串、前一筆值、預設幣別、推測幣別、讀取時間補欄；取不到就不寫那一列，並計數被略過的筆數 |
| 舊資料不得冒充新資料 | `CLAUDE.md` §1、§2.4 | 一般情形 `fetched_at` 取 L1 回傳值，L2 不得以當下時間覆寫。**唯一的例外是 `fetch_nav` 退回預存舊序列那一支**：它的 `attrs["fetched_at"]` 是讀檔當下的時間，不是取得時間，轉換層改取 `attrs["cache_updated_at"]`；沒有 `cache_updated_at` 就不寫列。辨識方式：`attrs["source"]` 以 `GitHubActions:cache/nav/` 開頭，或 `attrs` 帶 `nav_quality`。判斷過期看 `nav_quality["stale"]`，不看 `supports_annualized` |
| 新鮮度燈號 | `44` 5.2；`ui_v2/mkt/logic.py::delay_days`（取得日減觀測日，日曆日） | `fetched_at` 必須是真的取得時間（UTC） |
| 不預設任何輸入值 | `44` 1.1 `G3†` | 真資料接上後，觀察窗、門檻、目標比重仍然空白，直到使用者自己填 |
| 頁面只讀四張核心表 | `44` 5.3 | ui_v2 不寫 `holding`／`policy`／`nav`／`dividend`；持倉仍在 Sheets 維護 |
| 修正值不覆蓋原列 | `44` `market_indicator` 主鍵含 `release_date` | 需要持久化才做得到，見 Q12 |

---

## 3. 接的順序與接線架構（**待裁示的提案**）

> ⛔ 本節的每一個結論都**依附於 Q11（放寬舊樹檔案邊界）**。交接檔 §12 的常設規矩是「不碰舊 repo 的 `.py`」，而本節的方案 A 需要新建舊樹模組、也需要改到幾支既有 L1。Q11 裁示之前，本節只是提案。

### 3.1 各頁的量化比較（可驗證）

| 頁 | 用到的第四節表數 | 需要逐檔抓取的表 | 需要的憑證 | 欄位缺口（依第 2 節） | 讀寫使用者資料 |
|---|---|---|---|---|---|
| mkt | 2（`market_indicator`、`user_setting`） | 無 | `FRED_API_KEY`；`FINMIND_TOKEN` 可選 | `leading_index`（無公開出口、無公布日）、`coincident_index`、台灣政策利率、七鍵的 `release_date`／`is_revised` 規則 | 只有設定 |
| set | 5＋`spec` | 依賴其他頁 | 依已接上的來源而定 | `fetch_log` 整張表 | 設定、取數紀錄 |
| alo | 5 | `nav`（僅市值基準） | Sheets 服務帳戶或 OAuth | `holding` 的 `opened_on`、`cost_orig_ccy`、`units_shares`、`last_synced_at`；`policy` 六欄；非美元匯率 | 讀持倉 |
| hld | 6 | `nav`、`dividend` | 同上 | 同 alo，再加 `div_kind`、`nav.ccy`／`dividend.ccy`、`fund_profile.inception_on`（要先有 `dividend_policy`，Q6 下） | 讀持倉 |
| exp | 4 | `fund_profile`、`nav`、`dividend`（母體多少檔就抓多少次） | 視母體來源而定 | 母體定義、`dividend_policy`、`div_ratio_pct` 算式 | 視母體來源而定 |

表數的自驗方式：alo、hld、exp、set 看 `ui_v2/<頁>/fixtures.py::_dataset` 回傳 dict 裡的表名鍵；mkt 的 `ui_v2/mkt/fixtures.py::_dataset` 只帶 `rows`（即 `market_indicator`），`user_setting` 那一張是依 `44` MKT-4 的來源欄計入。

### 3.2 建議順序（依 2.6 重排）

| 順序 | 頁 | 開工前要先裁完的題 | 理由（可驗證） |
|---|---|---|---|
| 0 | 共通基礎 | Q11、Q10、Q13、T4 | 設定存檔後端、欄位契約、隔離守衛改版是四頁共用的前置；沒有存檔後端，任何一頁的「存檔」接上真資料後都會變成假存檔 |
| 1 | mkt（部分鍵） | Q1、Q2、Q3、T1 | 唯一不碰使用者持倉、不需要 Sheets 的一頁。**但它不能整頁一次接完**：依 2.6，七鍵裡只有日頻行情兩鍵在 Q3 裁完後就能寫列，FRED 三鍵要等 T1 的 vintage 取數，MKT-2 兩鍵要等 Q2、Q3。接上的鍵照出數、沒接上的照 `44` 顯示資料未備，頁面不會整頁被擋 |
| 2 | set（只診斷已接上的層） | Q12 | mkt 接上之後，`市場指標` 這一層就有真的取數可以診斷；其他三層誠實顯示無紀錄。放在 alo／hld 之前的理由：那兩頁要等 Q4，而 Q4 會改動客戶的 Sheets 結構，時程不在我方手上 |
| 3 | alo | Q4（含 `last_synced_at` 的對帳定義）、Q8；市值基準另需 Q9 | 依 2.6，Q4 裁示前每一列持倉都寫不進去，**整頁只剩空狀態**。`last_synced_at` 是最容易漏掉的一欄：它唯一的來源 `_持倉總覽` 沒有讀取函式，所以 Q4 必須連同「什麼算一次對帳」一起裁，否則其他欄補齊了仍然寫不進去。Q4 裁完後，成本基準只需要 `cost_twd` 與 `bucket`，比 hld 少淨值序列與配息 |
| 4 | hld | Q4、Q5、Q6 下、T3 | 沿用 alo 的持倉轉換，再加淨值序列與配息。**Q6 下也是前提**：`HLD-2` 要用 `fund_profile.inception_on`，而 `fund_profile.dividend_policy` 是不可空欄，沒裁就一列 `fund_profile` 都寫不進去。`div_kind` 只讓 `HLD-8` 那一欄誠實顯示不適用；`dividend.ccy` 只收來源自報（2.6），走 MoneyDJ 的基金配息會顯示資料未備 |
| 5 | exp | Q6、Q7 | 母體、配息方式、配息佔比算式三件未裁之前，`fund_profile` 一列都寫不進去 |

### 3.3 接線架構（寫給總管審；`CLAUDE.md` §8.1 六步）

**候選方案比較**

| 方案 | 做法 | 與 `CLAUDE.md` §8.2 的關係 | 與交接檔 §12「不碰舊 repo 的 `.py`」的關係 | 評估 |
|---|---|---|---|---|
| A：經 L2 新轉換層 | 新建一個 L2 模組，呼叫 L1、把結果轉成第四節表列；ui_v2 只經由每頁一個 `source.py` 碰到它 | 合規：L3 → L2 → L1 | **需要放寬**：新建舊樹模組，並需改到幾支既有 L1（見 Q11 清單） | 本組建議，待 Q11 |
| B：ui_v2 自建 adapter 直呼 L1 | adapter 放在 `ui_v2/` 底下，直接 import `repositories.*` | 違反「L3 不得直呼 L1」，需擴大 `EXCEPTIONS.md` 的 `EX-PASSTHRU-1` | 不新建舊樹檔，但錯誤出口與分頁吞例外的問題仍要改既有 L1 | 不建議 |
| C：沿用既有 L2 門面 | 呼叫 `services/fund_service.py::get_latest_vix` 之類 | 合規 | 不必改 | 不足：這類門面只回單一數值或 `None`，吞掉錯誤原文（1.4 丙類），也不給序列 |

既有先例，照實寫：`ui/views/page_02_health.py` 在模組頂端只 import `streamlit` 與 `ui.helpers` 系列，檔頭自陳「本檔禁 import `repositories/**`」；函式內另有延遲 import，對象含 `services.*`、`shared.signal_thresholds`、`ui.components.mutual_exclusion`、`ui.helpers.fund.checkup` 與 `ui.helpers.fund_grp_health.*`。**其中 `ui/helpers/fund_grp_health/ai.py` 內 import `repositories.news_repository`**，所以那一頁是「本檔不直接 import」，不是「整條呼叫鏈不經過 L1」。方案 A 若要比它嚴，隔離守衛就要看整條鏈，見 3.5。

**第 1 步｜單一職責**：把舊樹 L1 取回的資料，轉成 `44` 第四節表格形狀的列（附 `fetched_at` 與失敗原文），交給 ui_v2 各頁既有的 `logic.build_page_model`；轉換層不做任何判定、不算任何指標。

**第 2 步｜模組切分**（名稱皆為暫定）

| 模組 | 層 | 職責 |
|---|---|---|
| `services/v2_tables/`（新） | L2 | 每張表一個轉換函式；回傳 `{"rows": [...], "errors": {...}}`。本身不發請求、不碰檔案，只呼叫 L1 並轉形 |
| `services/v2_tables` 內的欄位契約 | L2 | 第四節八張表的欄名與不可空欄清單，出口前逐列檢查。**真相源是 `44`，不是這份契約**：契約是 `44` 的鏡像，另寫一條測試比照 `tests/ui_v2/test_set_logic.py` 對 `ui_v2/set/fixtures.py::SPEC_TABLES` 的做法，從 `44` 逐欄重抽比對，漂了就紅。L2 不得 import `ui_v2`（上行），所以不能直接共用 `SPEC_TABLES` |
| 設定與取數紀錄的讀寫（新） | L1 | `user_setting`、`fetch_log`（與 Q12 若裁定落地的 `market_indicator`）的持久化；形態比照 `EXCEPTIONS.md` 的 `EX-CRUD-1`，但 ui_v2 仍經 L2 呼叫 |
| Q4 那兩張 `_` 分頁的讀取（新） | L1 | 讀持倉補充與保單資料兩張分頁；Sheets 讀取的短期快取放在這一層（4.4） |
| `ui_v2/<頁>/source.py`（新，每頁一檔） | L3 | 組出該頁 `build_page_model` 需要的資料參數；接存檔與重新取數的後端。**只由 `app_<頁>_live.py` import，`page.py` 不 import 它**。真正的理由：`source.py` 經 `services.v2_tables` 會連到 `repositories.fund.*`，而 `repositories/fund/sources.py`、`fund_orchestration.py`、`nav_metrics.py` 都在模組頂端 `from bs4 import BeautifulSoup`；交接檔 §2 量測的驗收 venv（stvenv）沒有 `bs4`、也沒有 `pandera`，`page.py` 一旦 import 它，五支 `test_*_page.py` 在那個 venv 裡會在 import 階段就炸。（系統 lane 不受影響：五支 `test_*_page.py` 都有 `pytest.importorskip("streamlit")`，系統直譯器沒有 streamlit，整檔跳過。hld、exp 的字面守衛擋的是 `from services.` 這類字樣，`from . import source` 不會命中，所以那不是理由。）⚠️ 本組這一輪用的驗收 venv 有 `bs4`、`pandera`，與交接檔記載的 stvenv 不同，所以「會炸」是依交接檔推得，本組沒有在 stvenv 實跑 |
| `ui_v2/app_<頁>_live.py`（新，每頁一檔） | L3 | **正式入口**：import 本頁 `source`，把載入函式傳給 `page.render(...)`。既有的 `ui_v2/app_<頁>.py` **維持原樣，當示範入口**（fixtures ＋ `?scenario=`）—— `ACCEPTANCE.md` 與既有測試指向的就是它 |
| 既有 `logic.py`／`fixtures.py`／`theme.py` | L3 | `fixtures.py` 不動；`logic.py` **要動**（示意字樣寫在裡面，見 3.4）；`theme.py` 不動 |

**第 3 步｜資料流**

```
外部來源
  → L0 infra/proxy.py::fetch_url（退避 infra/source_backoff.py）
  → L1 repositories/...（既有快取；新的 Sheets 讀取在這一層加 60 秒手動快取）
  → L2 services/v2_tables/...（轉成第四節表列＋失敗原文＋fetched_at；不另疊快取，見 4.4）
  → L3 ui_v2/<頁>/source.py（組參數；不放快取，見 4.4）
  → ui_v2/<頁>/logic.py::build_page_model
  → ui_v2/<頁>/page.py 渲染
```

**第 4 步｜依賴方向**：`ui_v2.app_<頁>_live` → `ui_v2.<頁>.source` → `services.v2_tables` → `repositories.*` → `infra.*`／`shared.*`；`ui_v2.app_<頁>_live` 另 import `ui_v2.<頁>.page`，把載入函式傳進去。單向，無上行 import。`ui_v2` 各頁之間仍互不 import。

**第 5 步｜失敗降級**

- 一律 fail loud：L2 轉換層在來源失敗時回 `rows=[]` 並把原文放進 `errors`，頁面照 `44` 顯示 ⛔ 與原文。
- **正式路徑不得呼叫 fixtures**。`app_<頁>_live.py` 與 `source.py` 不得 import `fixtures`；fixtures 只經既有的 `app_<頁>.py`（示範入口）與測試進入 `page.py`，示範模式照舊標示示意值。
- 乙類、丙類函式要先補錯誤出口（1.4）；補好之前，轉換層只能寫「來源回傳空值，原因未提供」這種如實但較弱的訊息，不得自行編造原因。
- `fetch_nav` 退回預存舊序列（4.3）：以 `attrs["source"]` 前綴或 `nav_quality` 辨識；`fetched_at` 改用 `cache_updated_at`；`nav_quality["stale"]` 為真時標成舊資料，不得當成當日即時值交出去。
- 來源在冷卻中時，轉換層把冷卻狀態（`infra/source_backoff.py::should_skip`、`infra/gspread_retry.py::should_skip_gspread` 的回傳）寫進錯誤原文，讓使用者看得出是「暫停重試」而不是「來源沒資料」。

**第 6 步｜自評過度設計**

| 項目 | 判定 |
|---|---|
| 通用的「來源外掛註冊表」 | **先不做**。每頁只寫它用得到的轉換函式 |
| 背景預抓、排程 | **先不做**。沿用既有 L1 快取 |
| 修改既有 L1 的回傳型別 | **先不做**。錯誤出口以「新增旁路輸出」（比照 `_finmind_business_indicator` 的 `error_out` 參數）處理，不改既有呼叫端看到的回傳值；逐支列入 Q11 |
| 八張表的落地保存 | **不列在這裡**：它不是過度設計的取捨，是與 `44` 5.3 的矛盾，另送 Q12 |

### 3.4 `page.py`（與 `logic.py`）要改的東西，逐項

| # | 項目 | 現況（`16eb828`） | 要改成 | 屬不屬於 `CLAUDE.md` §-1.5.4 要先出草稿的版面或文案變更 |
|---|---|---|---|---|
| 1 | 資料從哪來 | 五頁 `page.py` 各自呼叫 `fixtures` | `page.render` 加一個選填的載入函式參數；沒傳時照舊用 fixtures（既有示範入口與測試不受影響），`app_<頁>_live.py` 傳入 `source` 的載入函式 | 否（不改畫面） |
| 2 | 資料與 UI 狀態拆開 | hld 的情境帶 `fields`（輸入欄狀態）；exp 的情境帶 `compare_checked`、`watch_checked`，部分情境另帶 `draft_rules`（`EXP-1` 條件欄的當下內容，與 `user_setting` 裡的已存值 `exp_filter_rules` 不同）；hld 的 `open_fund` 另由 `st.session_state` 傳 | 正式路徑的 UI 狀態只來自 `st.session_state` 與 `user_setting`，`source.py` 只交資料 | 否 |
| 3 | 存檔後端 | mkt `_on_save` 寫進 `st.session_state["_user_setting"]`；`ui_v2/set/page.py` 檔頭自陳「存檔」「重新取數」兩種按鈕沒有後端；各頁以 `?savefail=1` 模擬寫入失敗 | 接 `source.save(...)` → L2 → L1 的設定存檔；失敗照現有 `save_errors` 外形回傳 | 否（`44` 已訂存檔失敗的畫面） |
| 4 | 重新取數後端 | 無 | 經 L2 包一層清快取。兩個候選：`infra/cache.py::clear_all_caches` 清 `_CACHE_REGISTRY` 裡登記過的快取 —— **其中包括 `infra/source_backoff.py` 的冷卻狀態**（該模組以 `_BackoffRegistryProxy` 登記進同一張表），按一次就解除所有來源的冷卻；`global_refresh_all` 先做同一件事，再清 `_ST_CACHE_REGISTRY` 裡登記過的 `st.cache_data`（沒登記的不清，本組在 `repositories/pool_repository.py` 沒有看到 `_cached_pool_map` 登記）、清磁碟快取目錄與 `_FUND_SNAPSHOT`，**只有在傳入 `session_state` 時**才刪 `_GLOBAL_REFRESH_SESSION_KEYS` 列名且不在保留清單內的鍵；它明文不清 `data_cache/`。兩者清的都是**整個行程**的快取 | 否；選哪一個列技術題 T5 |
| 5 | 情境機制 | `?scenario=`、各頁 `fixtures.ALL_SCENARIO_NAMES`／`SCENARIO_LABELS`（mkt 為 `all_datasets()` 的鍵），**畫面上印出「情境 …」標籤** | 正式入口移除；示範入口保留 | **是**：移除一段畫面上可見的文字。它是示範用的標籤、不在 `44` 裡，本組判為「回到 `44` 規格」，但依 §-1.5.4「分不清時從嚴」，列入草稿審 |
| 6 | 示意字樣 | mkt 頁首「資料為假資料（示意值）」；hld、exp 頁首各有一行假資料說明，且兩頁的 `ui_v2/hld/logic.py::hinted`、`ui_v2/exp/logic.py::hinted` 在數字後加「（示意）」；alo 的 `ui_v2/alo/logic.py::PAGE_HINT_NOTE`／`HINT_NOTE`、set 的同類說明行 | 正式入口不帶示意字樣；需要在 `logic.py` 加一個開關（`logic.py` 因此要動） | **是**：`ui_v2/hld/logic.py` 註明「草稿逐字要求：螢幕上每一個數字後面都帶（示意）」，拿掉等於改動已拍板草稿的文字，須出草稿等客戶拍板 |
| 7 | 新出現的文案 | 無 | 例如「來源冷卻中」「憑證已遮蔽」「舊資料」這類 `44` 沒有逐字訂的說明 | **是**：新文案一律先出草稿 |

### 3.5 隔離守衛：現況與改法

**現況（本組逐檔讀過）**

| 頁 | 測試 | 掃哪些檔 | 怎麼掃 | 新增 `source.py` 會不會被掃到 |
|---|---|---|---|---|
| alo | `tests/ui_v2/test_alo_logic.py::test_六個檔都沒有import舊repo或網路或姊妹頁` | 寫死在 `_ALL_SOURCE_FILES` 的六個檔（`__init__.py`、`fixtures.py`、`logic.py`、`theme.py`、`page.py`、`app_alo.py`），並斷言清單長度 ＝ 6 | AST，換算絕對模組名後比對 `_OLD_ROOTS`、`_NET_ROOTS`、`_SISTER_PAGES` | **不會**：清單寫死，新檔不在裡面 |
| set | `tests/ui_v2/test_set_logic.py` 同名測試 | 同上（`app_set.py`） | 同上 | **不會** |
| hld | fast lane：`tests/ui_v2/test_hld_logic.py::test_logic零streamlit與零舊repo_import`、`test_fixtures零網路字表`；slow lane：`tests/ui_v2/test_hld_page.py::test_page沒有import舊repo模組也沒有網路字表`、`test_進入點沒有import舊repo模組` | fast lane：前者只掃 `logic.py`，後者掃 `logic.py`、`fixtures.py`、`theme.py`；slow lane：`page.py` 與 `app_hld.py` | 字面子字串比對（兩條 lane 相同）；slow lane 對 `page.py` 另擋網路套件字樣，對 `app_hld.py` 只擋舊樹前綴 | **不會** |
| exp | fast lane：`tests/ui_v2/test_exp_logic.py::test_logic與fixtures與theme都沒有import_streamlit或舊repo或網路`；slow lane：`tests/ui_v2/test_exp_page.py::test_page沒有import舊repo模組也沒有網路字表`、`test_進入點沒有import舊repo模組` | fast lane：`logic.py`、`fixtures.py`、`theme.py`；slow lane：`page.py` 與 `app_exp.py` | 字面子字串比對（兩條 lane 相同）；slow lane 對 `page.py` 另擋網路套件、`socket` 與姊妹頁字樣 | **不會** |
| mkt | fast lane：`tests/ui_v2/test_mkt_logic.py::test_logic與fixtures都沒有import_streamlit或舊repo模組`；slow lane：`tests/ui_v2/test_mkt_page.py::test_page沒有import舊repo模組` | 前者掃 `logic`／`fixtures`／`theme`；後者掃 `page.py` | 前者只擋 `import streamlit`／`import pandas`／`import numpy`（測試名寫「舊 repo 模組」但字表沒有）；後者以字面比對擋 `from ui.`、`from services.`、`from repositories.`、`from shared.`、`from infra.`、`import fund_fetcher` | **不會**；mkt 的 `logic`／`fixtures`／`theme` 在 fast lane 沒有舊樹 import 守衛，也沒有網路套件守衛 |

結論：五頁的守衛**各自不同、射程不一**，沒有一頁的守衛會自動把新增檔納入；hld、exp、mkt 三頁對 `page.py`（hld、exp 另含進入點）的 import 守衛只在 slow lane。

**改法（提案，本輪沒有改任何 ui_v2 測試）**

- **新增一支測試**（不改既有測試的斷言），放 fast lane：五頁一律用同一支 AST 掃描、fail-closed 的逐檔白名單；掃描母體取「`ui_v2/<頁>/` 底下全部 `.py` ＋ 該頁 `app_*.py`（含 `app_<頁>_live.py`）」，不用寫死的清單；每一檔只能 import 它白名單裡的模組，**不在白名單就紅**。
- 白名單的形狀：只有 `app_<頁>_live.py` 可以 import 本頁的 `source`；只有 `source.py` 可以 import `services.v2_tables`（逐模組列名，不開整個 `services`）；`app_<頁>_live.py` 與 `source.py` 不得 import `fixtures`；網路套件（`_NET_ROOTS` 那一組）在 ui_v2 內一律不在白名單上。⚠️ 這與第一輪稽核意見「只有 `page.py` 可以 import `source`」不同，理由見 3.3 的 `source.py` 那一列。
**這樣做之後，第 5 節第 9 條「不改既有 ui_v2 測試的斷言」能不能成立**（本組逐檔讀過引用點）：

- 既有測試以 `_APP` 指向 `ui_v2/app_<頁>.py`：五支 `test_*_page.py` 本組都看到了（mkt 在 `tests/ui_v2/test_mkt_page.py`、set 在 `tests/ui_v2/test_set_page.py`，兩支本輪回填確認）；`tests/ui_v2/test_hld_logic.py` 讀 `app_hld.py` 的 docstring 比對情境清單；`ACCEPTANCE.md` 列的啟動指令也是 `app_<頁>.py`。示範入口留在原檔名，這些引用不必改。
- alo、set 的 `_ALL_SOURCE_FILES` 寫死六個檔，新檔不在其中，清單長度 ＝ 6 的斷言照樣成立 —— 代價是新檔不在那兩支守衛的射程內，靠上面新增的那一支補。
- 成立的條件有五條，缺一不可：(1) `app_<頁>.py` 與它的 docstring 不動；(2) `page.render` 新增的載入參數是選填、預設行為與現在逐字相同；(3) `page.py` 不 import `source`，也不 import 任何在 import 時會連到 `repositories.fund.*` 的模組 —— 否則在缺 `bs4`／`pandera` 的驗收 venv 裡，五支 `test_*_page.py` 會在 import 階段失敗（理由見 3.3 的 `source.py` 那一列）；(4) `logic.py` 的示意字樣開關預設為開；(5) `page.py`、`logic.py`、`fixtures.py`、`theme.py` 與既有進入點裡**為正式模式新增的分支與字串**，不得寫進會被既有字面掃描命中的字樣 —— 這些檔在 alo 的禁詞掃描（`tests/ui_v2/test_alo_logic.py` 以 `_ALL_SOURCE_FILES` 為母體）、exp 的 `_QUOTE_SCAN_FILES`（`tests/ui_v2/test_exp_logic.py`）、hld 與 mkt 的 `_MY_FILES`（`tests/ui_v2/test_hld_logic.py`、`tests/ui_v2/test_mkt_logic.py`）射程內，新增文字一旦命中就是改了斷言的結果。
- 在這五條下，本組判斷第 9 條成立；這是讀程式碼推得的，本組沒有實際改一版去跑。
- 正式模式「真的不碰 fixtures」要有執行期證據，不能只靠 import 掃描：見 4.7 第 4 點。

- 另加一條「整條呼叫鏈」的守衛：`services/v2_tables` 只准 import `repositories.*`、`shared.*`、`infra.*` 與標準函式庫，並納入既有 `tests/test_services_purity_contract.py` 的白名單體系。

---

## 4. 風險清單

### 4.1 憑證

| 風險 | 現況（本組讀過的） | 對策方向 |
|---|---|---|
| secrets 鍵名 | `FRED_API_KEY`；`FINMIND_TOKEN`（讀取點分散：`ui/helpers/macro/ndc.py`、`ui/tab1_macro.py`、`ui/tab1_macro_longterm.py`、`ui/tab5_data_guard.py`、`ui/views/page_01_macro.py`，全在 L3）；`google_service_account`（可以是 TOML 表格，也可以是 JSON 字串，`repositories/pool_repository.py::_sa_present` 兩種都收）；`[google_oauth]` 區段（`ui/helpers/io/oauth_state.py` 讀取）；`POLICY_SHEET_ID`、`NAV_SHEET_ID`、`POOL_SHEET_ID`；`PROXY_URL` 或 `[proxy]` 區段 | L2 轉換層統一讀取，不要再增加第六個 `FINMIND_TOKEN` 讀點 |
| 寫死的試算表 ID 預設值 | `services/nav_history_gs.py::_NAV_SHEET_ID_DEFAULT`、`repositories/pool_repository.py::_POOL_SHEET_ID_DEFAULT` —— secret 沒設時會連到檔內寫死的那一本 | ui_v2 的設定頁要能顯示「目前讀的是哪一本、是不是預設值」，否則使用者分不出是讀到自己的還是讀到預設的 |
| 選股池的退回條件 | `get_pool_store`：沒有服務帳戶也沒有注入 OAuth → 退回本地 JSON | 退回時必須大聲顯示（`pool_backend_status` 已提供判斷） |
| 缺 key 的呈現 | `fetch_fred` 缺 key 回空表且不標失敗 | 轉換層先檢查 key，缺 key 直接寫成錯誤原文「未設定 FRED_API_KEY」 |
| 服務帳戶權限 | 服務帳戶必須被加為各試算表的編輯者或檢視者（`repositories/pool_repository.py` 檔頭有記載） | 設定頁要能顯示「讀不到」與「沒權限」的區別 |
| OAuth 與服務帳戶兩條路 | `ui/tab3_portfolio.py` 內有「有服務帳戶就優先用它」的規則 | ui_v2 沿用同一條規則，不另立一套 |
| 多個 app 的 secrets | 五個進入點若在 Streamlit Cloud 各開一個 app，secrets 是分開設定的 | 部署形態查不到，見 4.8 |

### 4.2 速率限制與退避

- 既有機制：`infra/proxy.py::fetch_url`（單次呼叫內 429 退避 2／4／8 秒）＋ `infra/source_backoff.py`（跨呼叫的 host 冷卻）＋ `infra/gspread_retry.py`（Sheets 配額重試與冷卻）＋ `fundclear_offshore.py` 自帶節流。
- **Sheets 配額**：Streamlit 每次互動都會從頭重跑整支腳本，`source.py` 因此每次重跑都會被呼叫。`load_all_policies_v2` 沒有快取，每呼叫一次要讀 2＋N 次（開試算表 1 次、列分頁 1 次、N 張保單分頁各 1 次）。以 `repositories/snapshot_repository.py` 註解記載的每使用者每分鐘 60 次計，五張保單分頁時每次重跑 7 次讀取，一分鐘內重跑約 9 次就會撞到上限；撞到之後 `with_quota_retry` 會在同一次呼叫內等待重試，畫面卡住。
- **連按「重新取數」會繞過退避**：3.4 第 4 項的兩個候選都會清掉 `infra/source_backoff.py` 的冷卻狀態（它以 `_BackoffRegistryProxy` 登記在 `_CACHE_REGISTRY` 裡），使用者連按幾次，就等於連續解除冷卻、連續打同一個已經在限流的來源。對策：來源在冷卻中時，「重新取數」按鈕停用，並以 `44` 5.3 既有的停用原因欄寫出「某來源冷卻中、還剩幾秒」；或讓「重新取數」只清資料快取、不清冷卻狀態（技術題 T5）。停用原因的文字是新文案，依 3.4 第 7 項先出草稿。
- **exp 逐檔抓取**：母體若是上百檔、逐檔呼叫 `fetch_nav` 與 `fetch_div`，一次載入就可能觸發 MoneyDJ 或代理的限流，接著整個 host 被冷卻，連帶讓 hld、alo 也拿不到淨值。**對策不能改變區塊內容**（`44` EXP-2 的「最近淨值」「近 12 個月配息佔淨值比」兩欄一定要有值或誠實的不適用），所以只能從**母體大小**下手，併入 Q6 上半。

### 4.3 失敗處理

- 乙類、丙類函式（1.4）是最大風險：頁面會把「抓失敗」誤判成「資料未備」，違反 `44` 對系統錯誤要顯示紅色與原文的要求。
- **分頁被略過**：`load_all_policies_v2` 與 `load_all_policy_worksheets` 的單一分頁失敗被 `continue` 略過，持倉**少一張保單而沒有任何提示** —— 這是會算錯配置比重的那一種失敗；`load_all_policy_worksheets` 還會把這個缺了分頁的結果快取 60 秒。接 alo 之前必須先讓它把失敗分頁名交出來（列入 Q11 的改動清單）。
- **看起來像成功的舊資料**：`fetch_nav` 即時網址全敗時退回 `cache/nav/<代碼>.json`，這份非空序列被 `_daily_cache` 當成成功結果快取到當日結束。它**辨識得出來**：`repositories/fund/sources.py::_src_cache_files` 在 `attrs` 放 `source`（`GitHubActions:cache/nav/<代碼>.json`）、`cache_updated_at`、`nav_quality`、`supports_annualized`，所以不必改 `fetch_nav`，L2 讀 `attrs` 就能判讀。⚠️ 兩個容易讀錯的地方：(a) `supports_annualized` 只反映筆數不足與序列稀疏（`shared/data_quality.py::assess_nav_cache_quality` 內以 `usable and not sparse` 算出），**與過期無關**；判斷過期要看 `nav_quality["stale"]`（最新資料點距今超過 `MJ_FRESH_DAYS_YELLOW`）。(b) 這一支的 `attrs["fetched_at"]` 是讀檔當下的時間，取得時間要看 `cache_updated_at`（2.8）。
- `services/fund_service.py` 的 `_RF_ANNUAL` 預設 4%：本規劃不走舊樹 L2 指標，不受影響；若日後有人改走 `calc_metrics`，要注意這個預設值。

### 4.4 快取中毒與快取放哪一層

- 既有 L1 多數已改為「只快取成功結果」，但有**照常快取失敗的已知支線**：`fetch_fred` 的 404、407、「回 200 沒有觀測」、「回 200 但 JSON 解析失敗」（30 分鐘）；`fetch_usdtwd_series` 上游拋例外那一支（10 分鐘）；`fetch_ndc_signal_history` 帶 `error` 的結果（15 分鐘，`EXCEPTIONS.md` 查不到登記）；`load_all_policy_worksheets` 缺分頁的結果（60 秒）。轉換層要把這些情形寫成不同的原文，並在 SET 頁可見。
- **快取放哪一層**：
  - 外部 HTTP 取數的快取**只放在 L1**（沿用既有 TTL）。L2 轉換層**不另疊一層**，否則會與 L1 的 TTL 失準，並把 L1 刻意不快取的失敗鎖住。
  - Sheets 讀取目前沒有可用的快取（`load_all_policies_v2` 無），而 4.2 的配額問題又必須解決：快取放在 **L1**，就加在 `load_all_policies_v2` 本身（6.3 E-1），比照 `repositories/policy/v2.py::load_all_policy_worksheets` 的 60 秒手動快取先例（`gspread.Client` 不可雜湊，所以用模組層 dict），但鍵要改成「登入者＋試算表 ID」，不能只用試算表 ID —— OAuth 模式下不同登入者的讀取權限不同；**只快取成功的結果，有任何一張分頁被略過就算失敗、不快取**；「存檔」或「重新取數」時清掉。⚠️ **不能拿 `load_all_policy_worksheets` 代替**：它雖然已有 60 秒快取，讀的卻是 v1 欄位（`_records_to_policy_df` ＋ `repositories/policy/_helpers.py::ALL_COLS`），v2 分頁的 `fund_code`、`units`、`avg_nav` 等欄不在其內。**不放 L3**：v3 `01` 規定 UI 層不得私自存放原始資料，而 `EX-UICACHE-1` 的射程只到 `ui/**` 的 `@st.cache_data`，ui_v2 不在其內。
- `fetched_at` 必須取自 L1 回傳，不能在 L2 用當下時間覆寫 —— 快取命中時覆寫會讓舊資料看起來是新的。例外見 2.8（`fetch_nav` 退回預存舊序列那一支改取 `cache_updated_at`）。

### 4.5 時區與 T+1

- `44` 規定時間欄存 UTC、日期欄不帶時間；`ui_v2/mkt/logic.py::STORAGE_TIMEZONE` 為 UTC。
- `_daily_cache` 以台灣日曆日為界；FundClear、TDCC、MoneyDJ 的日期是台灣時間；Yahoo 收盤是美東時間。
- 淨值 T+1~T+3、週末假日無列是正常狀態（`44` `nav` 表「不補列」），轉換層不得補列。⚠️ `services/fund_service.py::get_fx_rate_by_date` 為了查表方便，會把匯率**逐日補值**（週末沿用前一交易日，該處自註為無未來資料）；若 Q9 裁定用它，那是查表用的中間結果，**不得**把補出來的日期寫成 `market_indicator` 的列。
- **公布日**：若拿 FRED 預設回傳的 `realtime_start` 當 `release_date`，可能整批寫成查詢當天（1.3 出入 2）；FinMind 景氣指標沒有公布日欄位。處置見 2.6。

### 4.6 單位陷阱（`CLAUDE.md` §4.1）

| 陷阱 | 本規劃的具體位置 |
|---|---|
| 百分比與小數 | `alo_target_weights` 用 0~1 比例；`div_cash_pct` 是 0~100；`credit_spread_pct` 以百分點顯示 |
| 原幣與新臺幣 | `cost_orig_ccy` 與 `cost_twd` 不可互換；非美元持倉沒有對應匯率鍵（Q9） |
| 匯率方向 | `fx_twd_per_usd` 是「新臺幣／美元」；FRED 的 `DEXUSEU` 是反向（美元／歐元），若日後補歐元匯率要注意 |
| 單位字面值不一致 | mkt fixtures 寫 `新臺幣／美元`、alo fixtures 寫 `TWD/USD`；轉換層只能輸出一個，以 mkt 的 MKT-3 宣告為準 |
| 預設幣別與推測幣別 | 多數 meta 路徑預設 USD、Allianz 預設 TWD、`_correct_currency` 依名稱推測（1.3 出入 5、6）；**轉換層一律不收**，只收來源自報或使用者手填 |
| 沿用持倉幣別 | `nav.ccy` 可收持倉列的使用者手填幣別（該欄語意就是計價幣別）；**`dividend.ccy` 不沿用**，只收來源自報（配息幣別可能與計價幣別不同）。處置見 2.6 |
| 空白變 0 | `_norm_float`（`_Ledgers`）、`parse_invest_twd`（保單分頁） |
| 交易日與日曆日 | mkt 觀察窗是日曆日（`days_calendar`）；舊樹年化用 252 交易日 |

### 4.7 測試策略（CI 不打真網路）

- 現況：`tests/conftest.py` 沒有任何阻斷網路的機制（`git grep -c socket 16eb828 -- tests/conftest.py` → 無輸出；正控 `git grep -c socket 16eb828 -- tests/ui_v2/test_alo_logic.py` → 2 行命中）。CI 目前靠的是「測試沒有去呼叫」，不是「呼叫會被擋」。
- 建議分三層：
  1. **轉換層單元測試**：以錄好的 L1 回傳值（DataFrame、list、錯誤字串、退回舊序列那一支）當輸入，驗證輸出列符合第四節欄位契約、缺值列被略過並計數、錯誤原文照 Q13 的規則保留或遮蔽。
  2. **接縫測試**：`source.py` 的輸出丟進既有 `logic.build_page_model`，與 fixtures 走同一批判準。
  3. **網路阻斷**：新增的測試以 fixture 把對外連線換成立即失敗；**必須放行 loopback**（`127.0.0.1`、`localhost`），因為 `tests/ui_v2/_ui_v2_chromium.py::streamlit_server` 與瀏覽器測試要連本機起的 Streamlit 行程。
  4. **正式模式不碰 fixtures 的執行期測試**：把本頁的 `fixtures` 模組換成一個「任何屬性存取都拋錯」的替身，再以一個 stub 載入函式（回傳一份最小的合法資料）呼叫 `page.render(...)`；只要正式模式的任何一條路徑讀了 fixtures，測試就紅。這一條補的是 import 掃描抓不到的東西：`page.py` 本來就 import `fixtures`（示範模式要用），所以「有沒有 import」不能證明「正式模式有沒有呼叫」。需要 streamlit，歸 slow lane。
- 既有 `tests/ui_v2/test_*_logic.py` 與 `test_*_page.py` 繼續吃 fixtures。

### 4.8 部署形態

- `ACCEPTANCE.md` 記載五頁各以 `streamlit run ui_v2/app_<頁>.py` 啟動 —— 也就是**五個獨立行程**。1.2 列的快取、`infra/source_backoff.py` 的冷卻狀態、`load_all_policy_worksheets` 的手動快取，全部住在各行程的記憶體裡，**五頁之間不共享**：mkt 剛把 FRED 冷卻起來，alo 那個行程不知道，照打。
- 若日後改成單一 app 多頁，則共享快取，但 3.4 第 4 項的「重新取數」會連帶清掉同行程裡所有頁（含舊 `app.py`，若同行程）的快取。
- Streamlit Cloud 上 ui_v2 是否已經或將要部署、以什麼形態部署，**查不到**（repo 內除 `ACCEPTANCE.md` 與各進入點的說明外，沒有找到 ui_v2 的部署設定）。

### 4.9 失敗原文與金鑰外洩

- `infra/proxy.py::fetch_url` 印 log 時已把網址的查詢字串砍掉（該處自註：FRED `api_key`、FinMind `token` 都走 `params`），**但同一函式在其他錯誤分支直接印例外物件本身**，而 HTTP 套件的連線例外字串通常會帶完整的請求路徑與查詢字串 —— `api_key` 就在查詢字串裡。這一點依套件行為推論，本環境不發網路請求，本組沒有實測。
- 407 代理驗證失敗的例外字串會不會帶出 `PROXY_URL` 裡的帳密，**查不到**（本組沒有實測）。
- `44` 對 `fetch_log.message` 與畫面上的取數失敗文案要求「原文、不改寫、不截斷」；照做就可能把金鑰印到畫面與 Sheets 上。**這是本規劃與 `44` 的矛盾，送 Q13 裁示。**

### 4.10 登記：與既有文件的新矛盾（只登記，不處置）

- `44` 第六節的死碼登記在 `docs/v2/46_fund_live_dead.md`。本規劃提的新模組（`ui_v2/<頁>/source.py`、`ui_v2/app_<頁>_live.py`、`services/v2_tables/`、6.3 清單內的新 L1 檔）建立之後，要不要登進那張表、登在哪一節，本組沒有答案。依交接檔 §12「遇新矛盾只登記，不回頭改規格」，在此登記。
- `44` 5.3「取數寫回資料表」與本規劃第一階段「即時組表」之間的矛盾，已送 Q12。
- `44`「原文不改」與金鑰遮蔽之間的矛盾，已送 Q13。

---

## 5. 不做的事（本階段範圍邊界）

| # | 不做 | 依據 |
|---|---|---|
| 1 | **不碰舊 repo 的 `.py`**，直到 Q11 裁示；裁示後也只做 Q11 清單內點名的改動 | 交接檔 §12 客戶常設規矩 |
| 2 | 不改 `ui/tab*.py` 任何一個字 | 交接檔 §12；客戶派工 |
| 3 | 不關舊入口（`app.py` 與既有分頁照常運作），ui_v2 與舊樹並存 | 客戶派工 |
| 4 | 不改 `docs/v2/44_fund_ui_ssot.md`；遇新矛盾只登記 | 已凍結；交接檔 §11、§12 |
| 5 | 不刪任何被判定為沒人呼叫的元件，只在登記表上標 | `44` 第六節「不刪，只標」 |
| 6 | ui_v2 不寫入 `holding`／`policy`／`nav`／`dividend`；持倉仍在 Sheets 維護 | `44` 5.3、`G1†` |
| 7 | 不為任何輸入欄提供預設值或候選值 | `44` `G3†` |
| 8 | 不改動畫面版面、不增刪卡片或分頁；3.4 列為「是」的文案變更先出草稿 | `CLAUDE.md` §-1.5.4 草稿先行 |
| 9 | 不刪 fixtures，不改既有 ui_v2 測試的斷言；示範入口沿用既有 `app_<頁>.py` | 既有測試與示範模式依賴它們；成立的五個條件見 3.5 |
| 10 | 第一階段不新增任何外部資料源，只用 `16eb828` 上已有的 L1 取數函式 | `CLAUDE.md` §-1、§8.1 第 6 步；交接檔 §12「不准發明不存在的資料源」 |
| 11 | 不改既有 L1 函式的回傳型別；補錯誤出口以新增旁路輸出處理，逐支列入 Q11 | 避免牽動舊分頁的呼叫端 |
| 12 | 不改 Streamlit Cloud 的部署設定或 secrets | 屬客戶環境 |
| 13 | 不在 ui_v2 內輸出任何方向、排名或配置結論 | `44` 1.2 呈現層禁令 |
| 14 | 不 commit、不 push、不 merge | 交接檔 §12 |

---

## 6. 裁示題

### 6.1 需要客戶裁示的題

「建議」欄是總管建議方案與理由；客戶只需要回「同意」或改寫。

📌 **2026-09-26 客戶已逐題裁示**，結果寫在每一題最後一欄的末尾（附帶條件照抄在後面）。第 3 節的提案自此以裁示結果為準；**裁示不等於動工授權**（§-1），6.2 的 T1~T5 仍待總管自決。

| 代號 | 問題 | 為什麼要客戶裁 | 建議方案與理由 |
|---|---|---|---|
| Q1 | 市場總覽的「政策利率」看美國聯邦基金利率，還是台灣央行利率？ | 決定指標定義；台灣版目前沒有取數實作 | 我建議**美國聯邦基金利率**，理由：已有 L1（`FRED_FED_FUNDS`），不必新增資料源；台灣版要新寫取數，違反第 5 節第 10 條。　**裁示：客戶 2026-09-26 同意** |
| Q2 | 「領先指標」「同時指標」看台灣國發會，還是美國？ | 美國領先指標序列已停更、現有替代品 CFNAI 是不同的指標；台灣同時指標被 L1 丟掉 | 我建議**台灣國發會**，理由：兩個指標是同一套編製、同一個資料集（FinMind 已在取回），只差把被丟掉的欄位與私有函式開出來（列入 Q11）；改用 CFNAI 等於換掉指標定義。　**裁示：客戶 2026-09-26 同意** |
| Q3 | 三件事請一起同意或否決：(a) 日頻收盤行情（VIX、匯率）的公布日一律＝觀測日；(b) **日頻收盤行情的 `is_revised` 一律寫「否」**；(c) 來源不給公布日的月頻指標（國發會景氣指標），第一階段顯示「資料未備」 | `44` 規定公布日與 `is_revised` 不可空，跨期比較只能用公布日；這三條是資料語意規則 | 我建議**三條都同意**，理由：收盤行情在收盤當下即公開、事後不回溯修正，(a)(b) 不會捏造時點或版次；景氣指標若硬給一個固定延遲天數就是捏造公布日，寧可誠實顯示資料未備。FRED 的公布日與版次屬技術題 T1。　**裁示：客戶 2026-09-26 同意** |
| Q4 | 持倉的「持有起始日」「最後對帳時間」（**什麼算一次對帳**）怎麼補；「單位數」「原幣平均成本」能否在既有欄位補齊並改為必填；保單的名稱、發行單位、已繳保費、生效日、狀態、幣別怎麼補？ | 照 `44` 現行規定，缺任一不可空欄的持倉與保單整列不顯示 ⇒ alo、hld 兩頁只剩空狀態。⚠️ **兩個資料遺失風險，據實揭露**：(1) 新欄若加在既有保單分頁，`repositories/policy/v2.py::load_all_policies_v2` 讀取時只保留 `ALL_COLS_V2` 那 10 欄，新欄會被丟掉；而舊 App「保單管理」裡的「📦 立即全部寫入」按鈕（`ui/helpers/portfolio/policy_admin_section.py` 呼叫 `ui/helpers/cloud_io.py::dump_all_to_sheet`，v2 分頁走 `_dump_all_to_sheet_v2` → `write_policy_v2`）會先 `ws.clear` 整張分頁、再只寫回 10 欄 —— **新欄的資料按一次就被清掉，救不回來**。同檔的 `fix_and_shrink_v2_sheets` 也走 `write_policy_v2`，但本組在 `16eb828` 上只找到測試在呼叫它。`ui/helpers/v2_editor.py` 自 v19.451 起是唯讀顯示，不寫回。(2) `_dump_all_to_sheet_v2` 寫回 `units`、`avg_nav` 時，**以舊 App 行程內的 T7 帳本部位為準、保單資料為後備**，所以客戶在 Sheets 手填的單位數與平均成本，也可能被那一次寫入蓋掉 | 我建議：**(a) 單位數、原幣平均成本 → 填在既有的 `units`（持有單位數）、`avg_nav`（平均買入單位成本）兩欄，並改為必填**。本組查過語意：`repositories/policy/v2.py::compute_units` 的算式是 `units = invest_twd / (avg_nav × avg_fx)`，同檔 `avg_nav_with_div_from_cumul_div_twd` 註明單位是 local currency per unit，所以 `avg_nav` 就是原幣平均買入單位成本，`cost_orig_ccy` ＝ `units` × `avg_nav`。**權威只有一個**：`cost_twd` 取 `invest_twd`、`units_shares` 取 `units`、`cost_orig_ccy` 由 `units` × `avg_nav` 算出，不另存一欄，也不用 `avg_fx` 反推任何一欄；`units` 或 `avg_nav` 為 0 或空白（`_normalize_float` 會把空白讀成 0.0）一律當成沒填。**(b) 持有起始日、最後對帳時間 → 另開一張 `_持倉補充` 分頁，只放這兩欄**，以「保單編號＋基金代號」為鍵；以 `_` 開頭的分頁會被三個保單讀取函式跳過、`dump_all_to_sheet` 的 v2 路徑也不寫它。**(c) 保單六欄 → 另開 `_保單資料` 分頁**。**(d) 請客戶同意：以 Sheets 為權威，補填之後不再使用舊 App 的「📦 立即全部寫入」**，否則 (a) 的兩欄可能被舊 App 的 T7 帳本值蓋掉。理由：10 欄裡本來就有的東西不另開欄，避免同一件事有兩個真相源（`CLAUDE.md` §2.1）；只有 10 欄裡真的沒有的兩欄才放到清除動作碰不到的分頁。　**裁示：客戶 2026-09-26 同意**；附帶條件：`_持倉補充`、`_保單資料` 兩張分頁由客戶自己開 |
| Q5 | 配息的收益／本金類別沒有來源，`HLD-8` 會一直顯示不適用，可以接受嗎？ | 業務語意；補來源需要新的外部資料 | 我建議**接受**，理由：`44` 4.3 已定義 `unknown` 與它的畫面；補來源違反第 5 節第 10 條。另請客戶知悉：依 2.6，`dividend.ccy` 只收來源自報，走 MoneyDJ 的基金配息會整列不寫，`HLD-3` 期間配息會顯示資料未備。　**裁示：客戶 2026-09-26 同意** |
| Q6 上 | 標的探索的基金母體是哪一群？ | 決定整頁的範圍、抓取成本與限流風險（4.2） | 我建議**用選股池**（`list_pool`），理由：量小、是使用者自己維護的名單、已有 Sheets 後端；集保搜尋是關鍵字查詢，不是母體，且會吞例外。　**裁示：客戶 2026-09-26 同意** |
| Q6 下 | 「累積／配息」怎麼從配息頻率文字判定？ | 業務規則 | 我建議**訂一張寫死的對照表，只收對照表裡有的頻率字樣，對不上的整列不寫**，理由：不猜；對照表可由客戶逐項確認。　**裁示：客戶 2026-09-26 同意**；附帶條件：對照表要讓客戶逐項確認 —— 已確認，見本節表下「配息頻率對照表（客戶 2026-09-26 定案）」 |
| Q7 | 「近 12 個月配息佔淨值比」的算式 | `44` 只給欄名 | 我建議**分子＝除息日落在最新淨值日往前 12 個月內的每單位配息合計（含類別未知者）；分母＝最新一筆淨值；配息幣別與淨值幣別不同時顯示不適用**，理由：只用本頁已有的兩張表、不需要匯率、不捏造換算；並提醒 `fetch_div` 同日只留一筆、最多 24 筆。　**裁示：客戶 2026-09-26 同意** |
| Q8 | 資產配置的「類別」沿用 Sheets 的「級別」（核心／衛星），還是另開一欄讓使用者自訂名稱？ | `44` 的類別是使用者自訂 | 我建議**另開一欄**，理由：沿用「級別」會把類別名稱鎖死成兩種，與 `44` ALO-1「類別名稱一律由使用者新增與命名」不符。　**裁示：客戶 2026-09-26 同意** |
| Q9 | 非美元計價的持倉在「市值基準」下怎麼換算？ | `44` 只定義美元匯率鍵 | 我建議**新增對應幣別的匯率鍵，由 L2 轉換層直接呼叫既有的 L1 `repositories/macro/yf.py::fetch_yf_close`（例：`EURTWD=X`）**，理由：已有取數、不新增資料源；不新增的話這些持倉在市值基準下只能顯示不適用。⚠️ `services/fund_service.py::get_fx_rate_by_date` 雖然已有，但它屬 1.4 丙類：失敗時回空 dict、不交原因，回傳的對照表沒有 `fetched_at`，而且會把週末逐日補值（4.5），**不適合直接當 `market_indicator` 的來源**。　**裁示：客戶 2026-09-26 同意** |
| Q10 | 同意由**客戶自己**在 Google 帳號新建一本試算表、分享給服務帳戶（編輯者），用來存放使用者設定與取數紀錄嗎？ | 會在客戶帳號建立新檔案；而且**必須由客戶建檔**：服務帳戶自己建立的檔案會落在服務帳戶自己的雲端硬碟，客戶看不到（這是服務帳戶的一般行為，本組沒有在 repo 內實測；repo 內選股池、淨值累積兩本的說明都要求「服務帳戶須被加為該試算表編輯者」，做法一致） | 我建議**同意，並比照選股池獨立一本**，理由：不與持倉試算表混用，避免動到客戶的持倉資料；分頁怎麼切屬技術題 T4。　**裁示：客戶 2026-09-26 同意**；附帶條件：試算表由客戶自己建，建好後分享給服務帳戶 |
| Q11 | 放寬舊樹檔案邊界：可否依 6.3 的清單新建檔案，並對既有檔做逐項點名的最小改動？ | 交接檔 §12 常設規矩「不碰舊 repo 的 `.py`」 | 我建議**同意「新增檔可以、既有檔只做 6.3 逐項點名的改動」**，理由：不改既有檔，1.4 的乙、丙兩類錯誤就無法誠實呈現，持倉也會無聲少一張保單；逐項點名讓每一處改動都有客戶簽名，不會變成空白授權。6.3 每一項都寫了「不改的話，後果是什麼」，客戶可以逐項否決。　**裁示：客戶 2026-09-26 同意**；附帶條件：6.3 第二類的 8 處改動（E-1~E-8）要一次做完、一次稽核、一次凍結，不准分批 |
| Q12 | `44` 5.3 規定「取數」要把取回的列寫進資料表，而「修正值不覆蓋原列」也只有落地保存才做得到；第一階段要落地哪些表？ | 本規劃與 `44` 的矛盾 | 我建議**`market_indicator` 與 `fetch_log` 在 mkt、set 兩個階段就落地到 Q10 那一本試算表；`nav`、`dividend` 等到 hld 階段再裁**，理由：前兩張量小、是 set 頁診斷的必要輸入；淨值與配息逐檔逐日，量大，應等 hld 的實際需要出來再定。　**裁示：客戶 2026-09-26 同意** |
| Q13 | `44` 要求取數失敗訊息「照原文、不改寫、不截斷」，但原文可能帶 API 金鑰或代理帳密（4.9）。可否在寫入 `fetch_log` 與上畫面之前遮蔽？ | 本規劃與 `44` 的矛盾；洩漏金鑰是不可逆的 | 我建議**只把已知的秘密值（各 secrets 的值）替換成固定記號，其餘字元逐字保留，並在該訊息旁註明「已遮蔽憑證」**，理由：遮蔽只動秘密值本身，錯誤的類型、來源、狀態碼仍逐字可見，除錯資訊不減。　**裁示：客戶 2026-09-26 同意**；附帶條件：遮蔽規則的落點改為「實作時寫進 `ACCEPTANCE.md`」，原因是 `44` 已凍結、不得加附註；「已遮蔽」要寫進 `fetch_log`，也要顯示在畫面上 |

#### 配息頻率對照表（客戶 2026-09-26 定案）

用途：Q6 下的規則 ——「只收對照表裡有的頻率字樣，對不上的整列不寫」—— 用這張表把來源的配息頻率文字對到 `fund_profile.dividend_policy`。

| 類別 | 來源寫法（左欄，推測） | 寫入 `dividend_policy` |
|---|---|---|
| 配息 | 月配、月配息、季配、季配息、半年配、半年配息、年配、年配息、雙月配、月收 | `dist` |
| 累積 | 不配息、無配息、累積、累積型 | `accum` |
| 不寫入 | 空白、「—」、不定期，以及任何表上沒有的寫法 | 不寫入（該基金的 `fund_profile` 整列不寫） |

⚠️ **左欄是推測的寫法，沒有實測過。** repo 裡沒有任何一筆 MoneyDJ「配息頻率」欄的真實樣本（該欄只在 `repositories/fund/sources.py`、`repositories/fund/fund_orchestration.py` 以 `rows_map.get("配息頻率", ...)` 讀取，沒有落檔的樣本），本環境也連不到 MoneyDJ。

三條規則：

1. 接上真資料後，遇到表上沒有的寫法，這一筆 `fund_profile` 算**寫入失敗**：不寫入，並在 `fetch_log` 記 `outcome` ＝ `failed`，`message` 寫「配息頻率寫法不在對照表：<原字樣>」。這符合 `44` 4.5 對 `message` 的定義（失敗訊息原文），也會出現在 `SET-2`（總管 2026-09-26 裁定）。
2. 每季回查一次：回查時拿 `fetch_log` 裡「配息頻率寫法不在對照表」這一類失敗訊息，把其中的新寫法補進本表；補表時照本文件體例，舊表劃線保留。
3. 在 `ACCEPTANCE.md` 留一行指向本表，讓後人知道它的來源是推測（已於 2026-09-26 加上）。

### 6.2 總管自決題（技術題，不送客戶）

| 代號 | 題目 | 規劃組的建議 |
|---|---|---|
| T1 | FRED 的公布日與修正版次：帶 vintage 參數取真的公布日，並以此判斷 `is_revised` | 實作前三鍵不寫列（2.6） |
| T2 | `holding_id` 的組法 | 組法寫死、可重現（`last_synced_at` 的定義已移到 Q4） |
| T3 | `nav.ccy`、`dividend.ccy`、`is_estimated` 的取值規則 | `nav.ccy`：來源自報或持倉列的使用者手填；`dividend.ccy`：只收來源自報；兩者都記錄出處（2.6） |
| T4 | 設定與取數紀錄的試算表分頁結構 | 待 Q10 同意後由總管定 |
| T5 | 「重新取數」用 `clear_all_caches` 還是 `global_refresh_all` | 兩者都會清整個行程、也都會解除來源冷卻（3.4 第 4 項）；須先確認部署形態（4.8） |

### 6.3 Q11 的改動清單

**第一類：新增檔**（舊樹裡新建，不動既有檔）

| # | 檔（暫名） | 用途 | 不做的話，後果是什麼 |
|---|---|---|---|
| N-1 | `services/v2_tables/` | L2 轉換層 | 方案 A 不成立 |
| N-2 | 設定、取數紀錄（與 Q12 裁定落地的 `market_indicator`）的 L1 存取模組 | `user_setting`、`fetch_log`、`market_indicator` 落地 | 「存檔」沒有後端；set 頁沒有取數紀錄；`is_revised` 無從比對 |
| N-3 | FRED vintage 取數的新 L1 檔（**不動 `fetch_fred` 本體**） | 取公布日與版次（T1） | FRED 三鍵不寫列 |
| N-4 | Q4 那兩張 `_` 分頁的 L1 讀取模組（含 60 秒手動快取，4.4） | 讀持倉補充與保單資料 | alo、hld 只剩空狀態 |

**第二類：既有檔的最小改動**（每項只加旁路輸出或開公開出口，不改既有呼叫端看到的回傳值）

| # | 檔與符號 | 改什麼 | 什麼時候才需要 | 不改的話，後果是什麼 |
|---|---|---|---|---|
| E-1 | `repositories/policy/v2.py::load_all_policies_v2`（及 `load_all_policy_worksheets`） | (a) 交出被略過的分頁名；(b) `load_all_policies_v2` 加 60 秒手動快取，鍵為「登入者＋試算表 ID」，只快取成功的結果，有分頁被略過就算失敗、不快取（4.4）。`load_all_policy_worksheets` 讀 v1 欄位，不能拿來代替 | 接 alo、hld 時 | (a) 不改：持倉無聲少一張保單，配置比重算錯；(b) 不改：Streamlit 每次重跑都讀 2＋N 次，撞 Sheets 配額（4.2） |
| E-2 | `repositories/macro_tw_local_repository.py`（`_finmind_business_indicator`） | 保留 `coincident` 欄、開公開出口 | Q2 裁定台灣時 | MKT-2 永遠顯示資料未備 |
| E-3 | `repositories/macro/fred.py::fetch_fred` | 新增錯誤旁路輸出（vintage 不在這裡，見 N-3） | 接 mkt 時 | FRED 失敗只能顯示「來源回傳空值，原因未提供」，分不出缺 key、404 與連線失敗 |
| E-4 | `repositories/macro/yf.py::fetch_yf_close` | 新增錯誤旁路輸出 | 接 mkt 時 | VIX 等序列失敗時同上 |
| E-5 | `repositories/fund/nav_metrics.py::fetch_div` | 新增錯誤旁路輸出 | 接 hld 時 | 配息抓失敗與「這檔沒有配息」分不出來 |
| E-6 | `repositories/fund/sources.py::tdcc_search_fund` | 不再吞例外，或交出失敗 | Q6 上裁定用集保時 | 查詢失敗顯示成「零檔符合」 |
| E-7 | `repositories/ledger_repository.py::load_all_ledgers` | 打不開試算表時交出原因 | 只在日後改採 `_Ledgers` 時 | 讀不到被當成「沒有交易紀錄」 |
| E-8 | `repositories/fund/nav_metrics.py::fetch_nav` | 即時網址與預存檔**都**失敗時，新增錯誤旁路輸出交出原因（退回預存舊序列那一支不必改，4.3） | 接 hld、alo 市值基準時 | 全敗時回空 Series、原因只 `print` 到 stdout，頁面只能寫「來源回傳空值，原因未提供」，分不出子網域 403、代理失效與「這檔真的查無淨值」 |

**刻意不列入的**：`fetch_nav` 的「退回預存舊序列」那一支（已可由 `attrs` 判讀，4.3；全敗那一支列為 E-8）；`ALL_COLS_V2`（Q4 建議不動它，理由見 Q4）；`fetch_usdtwd_series`（已是 1.4 甲類）。

**E-8 為什麼選「補旁路」而不是「接受原因未提供」**：`fetch_nav` 是 hld 淨值序列與 alo 市值基準的唯一即時來源，而它全敗的三個主因（子網域 403、代理失效、查無此基金）對使用者的處置完全不同 —— 前兩者等一下再試，後者要回 Sheets 檢查基金代號。只寫「原因未提供」會讓使用者無從判斷；旁路輸出比照 E-3~E-5，不改既有回傳，舊呼叫端零影響。

---

## 7. 本文件的方法、查證範圍與稽核狀態

- **本組實際讀過的**：五頁的 `fixtures.py`、`page.py` 的接縫與存檔、情境、示意字樣段落、`logic.py` 的函式清單與示意字樣常數；`44` 第三節五頁總表、MKT-1~3、第四節八張表、5.3 按鈕、第六節；交接檔 §11、§12；上文逐條點名的 L1 函式本體或其說明段落；`infra/source_backoff.py` 檔頭、`shared/backoff_policy.py` 常數、`infra/proxy.py::fetch_url` 的 log 遮罩段落；五頁的 ui_v2 隔離守衛。
- **本組沒有查的，或查不到的**：
  - FRED 預設 `realtime_start` 的實際值、HTTP 例外字串是否帶查詢字串、407 例外是否帶帳密（本環境不發網路請求）；
  - `fetch_div` 的日期欄是不是除息日；
  - Sheets 的 `fund_code` 能否直接當 MoneyDJ `full_key`；
  - 客戶實際試算表裡 `_Ledgers`、`_持倉總覽`、保單分頁哪些有資料（查不到）；
  - `cache/nav/` 預存檔目前是否仍在更新；
  - `tdcc_search_fund`、`list_pool`、`load_series` 的速率細節；
  - ui_v2 的雲端部署形態（查不到）；
  - Sheets 每分鐘 60 次讀取的上限，只引自 repo 內註解，沒有對 Google 官方文件查證。
- **稽核狀態**：本文件已經兩組獨立稽核三輪（架構範圍組、事實證據組；第一輪必修 17 筆、第二輪 11 筆、第三輪 6 筆），第三輪回修內容待複驗；客戶已於 2026-09-26 逐題裁示 Q1~Q13（見 6.1）。回修對照見附錄。

---

## 8. 已登記、不在本輪處理

> 本節只登記，不改任何程式、不改任何規格（交接檔 §12「遇新矛盾只登記」）。

**舊 bug：`div_freq_n` 算了但沒有交出去**

- `services/fund_service.py::calc_metrics` 以配息間隔算出區域變數 `div_freq_n`（12／4／2／1），**初值為 12**；但它的回傳 `dict(...)` 沒有這個鍵。
- `services/fund_row.py` 讀 `(fd.get("metrics") or {}).get("div_freq_n")`，值在 (12, 4, 2, 1) 時才用自算的頻率，否則退回 MoneyDJ 原文 `dividend_freq`。因為上游從未交出這個鍵，**自算分支在 production 永遠走不到**。
- `ui/helpers/fund_grp_health/columns.py` 的「配息頻率」欄說明寫「優先用本站從實際配息記錄歸納出來的頻率」，與實際行為不符。
- 若將來把它接上：初值 12 在沒有任何配息紀錄時不會被改寫，**不配息的基金會被標成「月配息」**。接上時必須先把「沒有配息紀錄」與「月配」分開。
- 查證方式（2026-09-26，本組實跑）：以 `ast` 解析 `services/fund_service.py`，排除巢狀函式後，`calc_metrics` 自己恰好有 2 個 `return`：一個是交出結果的 `dict(...)`，它的關鍵字參數裡沒有 `div_freq_n`；另一個 return 是函式開頭的 `if s.empty or len(s) < 5: return {}`（空 dict）；另以 `git grep -n "div_freq_n" 16eb828 -- '*.py'` 排除 `tests/` 後，全 repo 沒有任何一處把 `div_freq_n` 當成鍵寫進 dict（命中只有 `calc_metrics` 內的區域變數、該函式說明、`services/fund_row.py` 的讀取，以及 `scripts/diagnose_ret_3y_fallback.py` 的一個鍵名清單）。⚠️ 「沒有任何一處」取決於有沒有漏看，是本組單組判讀。

**上一輪稽核登記的三筆**

- (a) Q4 (a) 的 `invest_twd` 空白時會被讀成 0（`repositories/policy/_helpers.py::parse_invest_twd`），要與 `units`、`avg_nav` 套用同一條「0 或空白視為沒填」的規則；本輪未改 Q4 的文字。
- (b) 4.7 第 4 點的執行期測試：`page.py` 以 `from . import fixtures` 把模組綁在 page 模組的屬性上，所以替身必須以 monkeypatch 換掉 **page 模組上的 `fixtures` 屬性**；只換 `sys.modules` 裡的 `ui_v2.<頁>.fixtures` 不會影響已綁好的名字，測試會空轉。
- (c) 6.3 E-8 的「三個主因」沒有量測依據；而且「查無此基金」與「MoneyDJ HTML 改版、解析不到」在回傳上分辨不出來。實作 E-8 時，旁路輸出要據實分類，不得把後兩者合併寫成「查無此基金」。

**已在本輪直接修正的一筆**：§5 第 9 條原寫「四個條件」，3.5 已是五個條件，本輪改為「五個」；原句見附錄第四輪。

---

## 附錄　回修對照（第一版 → 本版）

第一版未曾提交，本附錄保留被改掉的舊表述，供複驗組逐條比對。

⚠️ **本段（第一輪）為轉述**：下表「第一版的舊表述」欄有一部分是概括，不是逐字原句（例：B1、B2、B9、B10 列）；逐字原句可由第一版檔案比對。第二輪、第三輪兩段一律貼逐字原句。

| 稽核編號 | 位置 | 第一版的舊表述 | 本版 |
|---|---|---|---|
| B1 | 前言、3、5、6.1 Q11 | ~~第 3 節寫成既定結論；第 5 節沒有「不碰舊 repo 的 `.py`」~~ | 3 改為待裁示提案；5 第 1 條；Q11 |
| B2 | 2.6、3.1、3.2 | ~~3.2 以「表數最少、七鍵有五鍵已有 L1」為由把 mkt 排第一、alo 排第二~~ | 新增 2.6 逐欄處置；3.1 mkt 列補 `leading_index`；3.2 重排並改寫理由 |
| B3 | 3.3 第 6 步、6.1 Q12 | ~~「本地資料庫鏡像」列在自評過度設計「先不做」~~ | 移出第 6 步，改送 Q12 |
| B4 | 4.2 | ~~「exp 的逐檔資料只在使用者勾選『對照』或展開單檔時才抓」~~ | 改為限縮母體，併入 Q6 上 |
| B5 | 4.2、4.4 | ~~「新增的轉換層不得自己再疊一層快取」~~ | 補 Sheets 配額風險；4.4 寫明快取分層 |
| B6 | 4.9、6.1 Q13 | ~~原文照印，未提金鑰外洩~~ | 新增 4.9 與 Q13 |
| B7、A5 | 3.5 | ~~「網路套件在整個 `ui_v2/` 仍然全擋」~~；~~「mkt 是五頁裡唯一『隔離靠自律』的一頁」~~ | 現況逐頁照實寫；改法改為 AST fail-closed 逐檔白名單 |
| B8 | 2.0、3.4 | ~~「接真資料只需要產出一份與 fixtures 同形的 dataset，`logic.py` 原則上不動」~~ | 3.4 逐項列出並判定是否需草稿 |
| B9 | 1.1、1.3、2.2、Q4 | ~~未列 `_Ledgers`、`_T7_State`、`_持倉總覽`~~ | 補列；出入 7 登記 `_norm_float`；Q4 重寫 |
| B10 | 6.1、6.2 | ~~Q3、Q6、Q7、Q9 沒有寫成「我建議 X，理由 Y」；Q3、Q10 技術半題送客戶~~ | 四題改寫成「我建議 X，理由 Y」；技術半題移入 6.2 |
| B11 | 前言 | ~~「本文件不改任何 `.py`，不改 44（已凍結），不改任何測試或基線」~~；~~「以上改法是規劃，本輪沒有改任何測試」~~ | 照實寫出 `_MD_DOCS` 的改動 |
| B12 | 1.1、2.7 | ~~淨值累積與選股池的 TTL「本組未查」~~；~~「沒有任何現成的持久化實作」~~；~~「沒有一張可讀寫的設定表」~~ | 補上實際快取；兩句全稱句改為分類敘述並附指令 |
| A1 | 1.1、4.4 | ~~`fetch_usdtwd_series`「只快取成功結果」~~ | 寫明拋例外那一支會被快取 10 分鐘 |
| A2 | 1.3、2.3、2.6、4.6 | ~~只提 Allianz 預設 TWD~~ | 補 USD 預設與名稱推測修正，並規定轉換層不收 |
| A3 | 1.1、2.8、3.3、4.3 | ~~未提 `fetch_nav` 退回舊序列~~ | 登記為「看起來像成功的舊資料」 |
| A4 | 1.4 | ~~「`fund_orchestration.py` 內的各 `_src_*` 內部來源」~~ | 改為 `repositories/fund/sources.py`，附計數指令 |
| 建議 | 7 | ~~「本文件未經第二組獨立複驗」~~ | 改寫為稽核狀態 |

### 第二輪回修（第二版 → 本版）

每一條貼第二版的原句（加刪除線），不轉述。沒有舊句可貼的（純新增）不列入；純新增的有：2.6 的 `dividend.ccy` 列、3.3 的 `_` 分頁讀取列、3.5 末段「第 9 條能不能成立」、6.3 整節。

- **A3/N4**｜1.1 MoneyDJ 列｜第二版原句：~~這份序列非空、所以**被 `_daily_cache` 當成成功結果快取到當日結束** —— 見 4.3「看起來像成功的舊資料」。~~
- **建議（選股池壞檔）**｜1.1 選股池列｜第二版原句：~~（`pool_backend_status` 會回 `"local"` 供畫面警告） |~~
- **建議（P-NDCCACHE-1）**｜1.1 FinMind 列｜第二版原句：~~**失敗結果（帶 `error` 欄的 dict）也會被快取 15 分鐘**（已登記為 `EXCEPTIONS.md` 的 `P-NDCCACHE-1`）~~
- **N4**｜1.4 乙類｜第二版原句：~~`fetch_nav`（空 Series；另有退回舊序列那一支，連「失敗」都看不出來，見 4.3）~~
- **建議（draft_rules）**｜2.0 exp 列｜第二版原句：~~`{dataset, compare_checked, watch_checked}`；~~
- **建議（draft_rules）**｜2.0 exp 列｜第二版原句：~~**兩組勾選狀態是 UI 狀態，不是資料**~~
- **建議（inception_date）、N3**｜2.2 fund_profile 段｜第二版原句：~~`fund_profile`（本頁只用 `inception_on`）：Allianz 解析路徑有 `inception_date`；其他來源本組沒有逐一查。~~
- **建議（inception_date）**｜2.3 表｜第二版原句：~~`inception_date`（目前只在 Allianz 解析路徑看到）~~
- **N2**｜2.6 表 last_synced_at 列｜第二版原句：~~| `holding.last_synced_at` | 只有 `_持倉總覽` 的更新時間；其他來源只能用讀取時間 | 技術題 T2，總管自決：**不得**以讀取時間冒充對帳時間；讀不到 `_持倉總覽` 時不寫 | 同上 |~~
- **N7**｜2.6 表幣別列｜第二版原句：~~| `nav.ccy`、`dividend.ccy` | MoneyDJ 不給；FundClear 路徑有 `attrs["currency"]`；持倉列有使用者手填幣別 | 技術題 T3，總管自決：只接受來源自報或使用者手填的幣別，並在列上可追溯來自哪一個；**預設值、名稱推測值一律不收** | 兩者都沒有的基金，淨值與配息不寫列 |~~
- **N3**｜2.6 表 dividend_policy 列｜第二版原句：~~裁示前 `fund_profile` 整列不寫 ⇒ exp 候選清單為空 |~~
- **B**｜2.8 表｜第二版原句：~~| 舊資料不得冒充新資料 | `CLAUDE.md` §1、§2.4 | `fetch_nav` 退回舊序列（4.3）、快取命中的舊結果，其 `fetched_at` 必須是原本那次取得的時間，不得以查詢當下覆寫 |~~
- **N2**｜3.1 alo 列｜第二版原句：~~`holding` 的 `opened_on`、`cost_orig_ccy`、`units_shares`；~~
- **N3**｜3.1 hld 列｜第二版原句：~~`fund_profile.inception_on` | 讀持倉 |~~
- **N2**｜3.2 alo 列｜第二版原句：~~| 3 | alo | Q4、Q8；市值基準另需 Q9 | 依 2.6，Q4 裁示前每一列持倉都寫不進去，**整頁只剩空狀態**。Q4 裁完後，成本基準只需要 `cost_twd` 與 `bucket`，比 hld 少淨值序列與配息 |~~
- **N3**｜3.2 hld 列｜第二版原句：~~| 4 | hld | Q4、Q5、T3 | 沿用 alo 的持倉轉換，再加淨值序列與配息；`div_kind` 只讓 `HLD-8` 那一欄誠實顯示不適用 |~~
- **建議（先例）**｜3.3 先例段｜第二版原句：~~既有先例，照實寫：`ui/views/page_02_health.py` 本身只 import `services/**` 與 `ui.helpers`，檔頭自陳「本檔禁 import `repositories/**`」；**但它呼叫的 `ui.helpers` 模組會碰到 `repositories`**（例：`ui/helpers/fund_grp_health/switch_advisor_section.py` 內 import `repositories.pool_repository`、`repositories.portfolio_perf_repository`），所以那一頁是「本檔不直接 import」，不是「整條呼叫鏈不經過 L1」。方案 A 若要比它嚴，隔離守衛就要看整條鏈，見 3.5。~~
- **N6**｜3.3 模組切分表 source.py 列｜第二版原句：~~| `ui_v2/<頁>/source.py`（新，每頁一檔） | L3 | 組出該頁 `build_page_model` 需要的資料參數；接存檔與重新取數的後端 |~~
- **N6**｜3.3 模組切分表示範入口列｜第二版原句：~~| `ui_v2/app_<頁>_demo.py`（新，每頁一檔） | L3 | 示範與測試入口，唯一可以餵 fixtures 給 `page.py` 的地方 |~~
- **N5**｜3.3 第 3 步資料流｜第二版原句：~~  → L1 repositories/...（既有快取）~~
- **N5**｜3.3 第 3 步資料流｜第二版原句：~~  → L3 ui_v2/<頁>/source.py（組參數；Sheets 讀取的短期快取放這一層，見 4.4）~~
- **N6**｜3.3 第 4 步｜第二版原句：~~**第 4 步｜依賴方向**：`ui_v2.<頁>.page` → `ui_v2.<頁>.source` → `services.v2_tables` → `repositories.*` → `infra.*`／`shared.*`。~~
- **N6**｜3.3 第 5 步｜第二版原句：~~- **正式路徑不得呼叫 fixtures**。fixtures 只能經 `app_<頁>_demo.py` 與測試進入 `page.py`，示範模式照舊標示示意值。~~
- **A、B**｜3.3 第 5 步｜第二版原句：~~- `fetch_nav` 退回舊序列（4.3）：轉換層要能分辨這一支，把它標成舊資料或當成失敗，不得當成當日即時值交出去。~~
- **N6**｜3.4 第 1 項｜第二版原句：~~| 1 | 資料從哪來 | 五頁 `page.py` 各自呼叫 `fixtures` | 正式入口改由 `source.py` 提供；fixtures 只經 `app_<頁>_demo.py` 進來 | 否（不改畫面） |~~
- **建議（draft_rules）**｜3.4 第 2 項｜第二版原句：~~| 2 | 資料與 UI 狀態拆開 | hld 的情境帶 `fields`（輸入欄狀態）；exp 的情境帶 `compare_checked`、`watch_checked`；hld 的 `open_fund` 另由 `st.session_state` 傳 | 正式路徑的 UI 狀態只來自 `st.session_state` 與 `user_setting`，`source.py` 只交資料 | 否 |~~
- **建議（global_refresh_all）**｜3.4 第 4 項｜第二版原句：~~| 4 | 重新取數後端 | 無 | 經 L2 包一層清快取。⚠️ 兩個候選行為差很多：`infra/cache.py::clear_all_caches` 只清已登記的 TTL 快取；`global_refresh_all` 另外清 `st.cache_data`、磁碟快取，**還會刪 `st.session_state` 裡的鍵**。兩者清的都是**整個行程**的快取，若與舊 `app.py` 同行程，會連帶清掉舊分頁的快取 | 否；但選哪一個會影響使用者按下去之後看到什麼，列技術題 T5 |~~
- **C**｜3.5 現況表 hld 列｜第二版原句：~~| hld | `tests/ui_v2/test_hld_logic.py::test_logic零streamlit與零舊repo_import`、`test_fixtures零網路字表` | 前者只掃 `logic.py`；後者掃 `logic.py`、`fixtures.py`、`theme.py` | 字面子字串比對 | **不會**；`page.py`、`app_hld.py` 目前也沒有被任何 import 守衛掃到 |~~
- **C**｜3.5 現況表 exp 列｜第二版原句：~~| exp | `tests/ui_v2/test_exp_logic.py::test_logic與fixtures與theme都沒有import_streamlit或舊repo或網路` | `logic.py`、`fixtures.py`、`theme.py` | 字面子字串比對 | **不會**；`page.py`、`app_exp.py` 同上 |~~
- **C**｜3.5 結論｜第二版原句：~~結論：五頁的守衛**各自不同、射程不一**，沒有一頁的守衛會自動把新增檔納入。~~
- **N6**｜3.5 改法第 1 點｜第二版原句：~~- 五頁一律改成**同一支 AST 掃描、fail-closed 的逐檔白名單**：掃描母體取「`ui_v2/<頁>/` 底下全部 `.py` ＋ 該頁 `app_*.py`」，而不是寫死的清單；每一檔只能 import 它白名單裡的模組，**不在白名單就紅**。~~
- **N6**｜3.5 改法第 2 點｜第二版原句：~~- 白名單的形狀：只有 `page.py` 可以 import 本頁的 `source`；只有 `source.py` 可以 import `services.v2_tables`（逐模組列名，不開整個 `services`）；`page.py` 不得 import `fixtures`，只有 `app_<頁>_demo.py` 與測試可以；網路套件（`_NET_ROOTS` 那一組）在 ui_v2 內一律不在白名單上。~~
- **A、B、N4**｜4.3 看起來像成功的舊資料｜第二版原句：~~- **看起來像成功的舊資料**：`fetch_nav` 即時網址全敗時退回 `cache/nav/<代碼>.json`，這份非空序列被 `_daily_cache` 當成成功結果快取到當日結束。它的 `attrs` 帶 `supports_annualized` 旗標，只在序列稀疏或過期時為否。對 ui_v2 的要求寫在 2.8 與 3.3 第 5 步。~~
- **建議（P-NDCCACHE-1）**｜4.4 第 1 點｜第二版原句：~~（15 分鐘，`P-NDCCACHE-1`）~~
- **N5**｜4.4 快取分層｜第二版原句：~~  - Sheets 讀取目前沒有可用的快取（`load_all_policies_v2` 無），而 4.2 的配額問題又必須解決：快取放在 **L3 的 `source.py`**，以「目前登入者＋試算表 ID」為鍵、短 TTL、**只快取成功結果**，並在「存檔」或「重新取數」時清掉。放 L3 的理由：`gspread.Client` 不可雜湊（`load_all_policy_worksheets` 自陳），而使用者身分只在 L3 取得到。~~
- **N7**｜4.6 表｜第二版原句：~~| 沿用持倉幣別 | 把 `nav.ccy`、`dividend.ccy` 直接抄持倉列的幣別，是一種預設值：配息幣別可能與計價幣別不同。第一階段處置見 2.6 |~~
- **N6**｜4.10｜第二版原句：~~（`ui_v2/<頁>/source.py`、`ui_v2/app_<頁>_demo.py`、`services/v2_tables/`）~~
- **N6**｜5 第 9 條｜第二版原句：~~| 9 | 不刪 fixtures，不改既有 ui_v2 測試的斷言 | 既有測試與示範模式依賴它們 |~~
- **N8**｜6.1 Q3｜第二版原句：~~| Q3 | 日頻行情（VIX、匯率）的公布日可否訂為「公布日＝觀測日」；來源不給公布日的月頻指標（國發會景氣指標），第一階段是否接受「資料未備」 | `44` 規定公布日不可空，跨期比較只能用它；這兩條是資料語意規則 | 我建議**兩條都同意**，理由：收盤行情在收盤當下即公開、事後不回溯修正，這條規則不會捏造時點；景氣指標若硬給一個固定延遲天數就是捏造公布日，寧可誠實顯示資料未備。FRED 的公布日屬技術題 T1 |~~
- **N1、N2**｜6.1 Q4｜第二版原句：~~| Q4 | 持倉的「持有起始日」「原幣成本」「單位數」與保單的名稱、發行單位、已繳保費、生效日、狀態、幣別，要怎麼補？ | 照 `44` 現行規定，缺任一不可空欄的持倉與保單整列不顯示 ⇒ alo、hld 兩頁只剩空狀態 | 我建議**在客戶的保單試算表每張分頁加「持有起始日」欄、把「持有單位數」「平均買入單位成本」改為必填，另開一張保單資料分頁放保單六欄**，理由：`_Ledgers` 雖然推得出持有起始日，但 v2 schema 已不維護它，且它的空欄會被算成 0；`_持倉總覽` 沒有持有起始日、也沒有讀取函式；只有在來源端補欄，才不必改凍結的 `44`、也不必讓程式去猜 |~~
- **N7**｜6.1 Q5｜第二版原句：~~| 我建議**接受**，理由：`44` 4.3 已定義 `unknown` 與它的畫面；補來源違反第 5 節第 10 條 |~~
- **建議（get_fx_rate_by_date）**｜6.1 Q9｜第二版原句：~~| Q9 | 非美元計價的持倉在「市值基準」下怎麼換算？ | `44` 只定義美元匯率鍵 | 我建議**新增對應幣別的匯率鍵，資料走既有的 `services/fund_service.py::get_fx_rate_by_date`／`get_latest_fx`**，理由：已有取數、不新增資料源；不新增的話這些持倉在市值基準下只能顯示不適用 |~~
- **建議（Q10 建檔）**｜6.1 Q10｜第二版原句：~~| Q10 | 同意在客戶的 Google 帳號新建一本試算表，存放使用者設定與取數紀錄嗎？ | 會在客戶帳號建立新檔案 | 我建議**同意，並比照選股池獨立一本**，理由：不與持倉試算表混用，避免動到客戶的持倉資料；分頁怎麼切屬技術題 T4 |~~
- **N4**｜6.1 Q11｜第二版原句：~~| Q11 | 放寬舊樹檔案邊界：可否新建 `services/v2_tables/` 與設定存檔的 L1 模組，並對以下既有檔做最小改動？（`repositories/policy/v2.py`：兩個讀取函式交出失敗分頁名；`repositories/macro/fred.py`：`fetch_fred` 新增錯誤旁路輸出與 vintage 取數；`repositories/macro_tw_local_repository.py`：公開領先與同時指標；`repositories/fund/nav_metrics.py`：`fetch_nav` 標示退回舊序列那一支） | 交接檔 §12 常設規矩「不碰舊 repo 的 `.py`」 | 我建議**同意「新增檔可以、既有檔只做上列逐項點名的改動」**，理由：不改既有檔，1.4 的乙、丙兩類錯誤就無法誠實呈現，會違反 `44` 對系統錯誤的要求；逐項點名則讓每一處改動都有客戶簽名，不會變成空白授權 |~~
- **N2**｜6.2 T2｜第二版原句：~~| T2 | `holding_id` 的組法；`last_synced_at` 不得以讀取時間冒充 | 組法寫死、可重現 |~~
- **N7**｜6.2 T3｜第二版原句：~~| T3 | `nav.ccy`、`dividend.ccy`、`is_estimated` 的取值規則 | 只收來源自報或使用者手填，並記錄出處 |~~
- **建議（global_refresh_all）**｜6.2 T5｜第二版原句：~~| T5 | 「重新取數」用 `clear_all_caches` 還是 `global_refresh_all` | 兩者都會清整個行程；須先確認部署形態（4.8） |~~
- **建議**｜7 稽核狀態｜第二版原句：~~- **稽核狀態**：本文件第一版已經兩組獨立稽核一輪（架構範圍組、事實證據組，合計必修 17 筆）；本版為回修版，回修內容待複驗。回修對照見附錄。~~

### 第三輪回修（第三版 → 本版）

每一條貼第三版的原句（加刪除線），不轉述。純新增、沒有舊句可貼的：3.5 第 9 條段新增的第 5 點、4.2「連按重新取數會繞過退避」、4.7 第 4 點、6.3 的 E-8 列與「E-8 為什麼選補旁路」段、附錄第一輪的「本段為轉述」標註。

- **R1**｜1.1 Google Sheets（持倉／保單）列｜第三版原句：~~、`repositories/policy/v2.py::load_all_policy_worksheets`、~~
- **R4**｜3.3 模組切分表 source.py 列｜第三版原句：~~| `ui_v2/<頁>/source.py`（新，每頁一檔） | L3 | 組出該頁 `build_page_model` 需要的資料參數；接存檔與重新取數的後端。**只由 `app_<頁>_live.py` import，`page.py` 不 import 它**：`page.py` 若 import 它，會把 `services`→`repositories`→`requests` 整條鏈帶進既有的 `test_*_page.py`，而交接檔 §2 記載系統 lane 的直譯器沒有 `requests` |~~
- **建議（_APP 回填）**｜3.5 第 9 條段第 1 點｜第三版原句：~~- 既有測試以 `_APP` 指向 `ui_v2/app_<頁>.py`（alo、exp、hld 三支 `test_*_page.py` 本組有看到；mkt、set 兩支本組沒有逐一確認），`tests/ui_v2/test_hld_logic.py` 讀 `app_hld.py` 的 docstring 比對情境清單，`ACCEPTANCE.md` 列的啟動指令也是 `app_<頁>.py`。示範入口留在原檔名，這些引用不必改。~~
- **R4、建議（條件 5）**｜3.5 第 9 條段第 3 點｜第三版原句：~~- 成立的條件有四條，缺一不可：(1) `app_<頁>.py` 與它的 docstring 不動；(2) `page.render` 新增的載入參數是選填、預設行為與現在逐字相同；(3) `page.py` 不 import `source` 或 `services`（否則 hld、exp 的字面守衛會紅，系統 lane 也會缺 `requests`）；(4) `logic.py` 的示意字樣開關預設為開。~~
- **R5**｜3.5 第 9 條段（新增一點，無舊句）｜第三版原句：~~- 在這四條下，本組判斷第 9 條成立；這是讀程式碼推得的，本組沒有實際改一版去跑。~~
- **R1**｜4.4 快取分層｜第三版原句：~~  - Sheets 讀取目前沒有可用的快取（`load_all_policies_v2` 無），而 4.2 的配額問題又必須解決：快取放在 **L1**，比照 `repositories/policy/v2.py::load_all_policy_worksheets` 的 60 秒手動快取先例（`gspread.Client` 不可雜湊，所以用模組層 dict），但鍵要改成「登入者＋試算表 ID」，不能只用試算表 ID —— OAuth 模式下不同登入者的讀取權限不同；**只快取成功結果**，「存檔」或「重新取數」時清掉。**不放 L3**：v3 `01` 規定 UI 層不得私自存放原始資料，而 `EX-UICACHE-1` 的射程只到 `ui/**` 的 `@st.cache_data`，ui_v2 不在其內。~~
- **建議（fetched_at 例外）**｜4.4 最後一點｜第三版原句：~~- `fetched_at` 必須取自 L1 回傳，不能在 L2 用當下時間覆寫 —— 快取命中時覆寫會讓舊資料看起來是新的。~~
- **R3、R6**｜6.1 Q4｜第三版原句：~~| Q4 | 持倉的「持有起始日」「原幣成本」「單位數」「最後對帳時間」（**什麼算一次對帳**），以及保單的名稱、發行單位、已繳保費、生效日、狀態、幣別，要怎麼補？ | 照 `44` 現行規定，缺任一不可空欄的持倉與保單整列不顯示 ⇒ alo、hld 兩頁只剩空狀態。⚠️ **資料遺失風險**：若把新欄加在既有保單分頁，`repositories/policy/v2.py::load_all_policies_v2` 讀取時只保留 `ALL_COLS_V2` 那 10 欄，新欄會被丟掉；更嚴重的是舊分頁的保單編輯器存檔時走 `write_policy_v2`，它先 `ws.clear` 整張分頁、再只寫回 10 欄 —— **客戶填在新欄的資料，舊畫面存一次檔就被清掉，救不回來** | 我建議**客戶在同一本試算表另開一張以 `_` 開頭的分頁（暫名 `_持倉補充`），以「保單編號＋基金代號」為鍵，放持有起始日、原幣成本、單位數、最後對帳時間四欄；保單六欄另開一張 `_保單資料`**。理由：(1) 以 `_` 開頭的分頁會被 `load_all_policies_v2`、`load_all_policy_worksheets`、`list_policy_worksheets` 跳過，舊編輯器不讀它、也不寫它，資料不會被清掉；(2) 不必改 `ALL_COLS_V2` —— 改它等於改舊分頁的存檔行為，而且改好之前任何一次舊畫面存檔都會清資料，風險落在客戶身上；(3) 「最後對帳時間」由客戶每次對帳時自己填，不由程式以讀取時間冒充。把 `ALL_COLS_V2` 擴成 14 欄並列入 Q11 是另一個做法，本組判為較差，理由同 (2)。`_Ledgers` 推得出持有起始日，但 v2 schema 已不維護它、空欄會被算成 0；`_持倉總覽` 沒有持有起始日、也沒有讀取函式 |~~
- **R1**｜6.3 E-1｜第三版原句：~~| E-1 | `repositories/policy/v2.py::load_all_policies_v2`、`load_all_policy_worksheets` | 交出被略過的分頁名 | 接 alo、hld 時 | 持倉無聲少一張保單，配置比重算錯 |~~
- **R2**｜6.3 刻意不列入｜第三版原句：~~**刻意不列入的**：`fetch_nav`（退回預存舊序列那一支已可由 `attrs` 判讀，4.3）；`ALL_COLS_V2`（Q4 建議另開 `_` 分頁，理由見 Q4）；`fetch_usdtwd_series`（已是 1.4 甲類）。~~
- **建議**｜7 稽核狀態｜第三版原句：~~- **稽核狀態**：本文件已經兩組獨立稽核兩輪（架構範圍組、事實證據組；第一輪必修 17 筆、第二輪必修 11 筆）；本版為第二輪回修，回修內容待複驗。回修對照見附錄。~~

### 第四輪（客戶裁示回填）

本輪只回填客戶裁示並新增第 8 節；被改掉的原句逐字貼在下面。純新增、沒有舊句可貼的：6.1 各題末尾的裁示、6.1 前言的裁示說明、配息頻率對照表、第 8 節。

- **回填（直接修正）**｜5 第 9 條｜原句：~~既有測試與示範模式依賴它們；成立的四個條件見 3.5 |~~
- **回填**｜7 稽核狀態｜原句：~~- **稽核狀態**：本文件已經兩組獨立稽核三輪（架構範圍組、事實證據組；第一輪必修 17 筆、第二輪 11 筆、第三輪 6 筆）；本版為第三輪回修，回修內容待複驗。回修對照見附錄。~~

### 第五輪（稽核必修 2 筆）

- 6.1 對照表規則 1｜原句：~~1. 接上真資料後，遇到表上沒有的寫法就不寫入，並登記這個新寫法（寫進 `fetch_log` 的訊息，讓 set 頁看得到）。~~
- 6.1 對照表規則 2｜原句：~~2. 每季回查一次，把實際遇到的寫法補進本表；補表時照本文件體例，舊表劃線保留。~~
- §8 查證方式｜原句：~~走訪 `calc_metrics` 內的全部 `return`，最後那個 `dict(...)` 的關鍵字參數裡沒有 `div_freq_n`，其餘 `return` 屬巢狀函式或非 dict；~~
