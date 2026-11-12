# UI × 資料層唯讀稽核（五頁契約對照＋資料層盤點＋可安全施工清單）

> **研究證據（唯讀稽核）；非客戶裁示、非授權施工。** 基準：main `b991df70623242afd1876b217088e9eccd5a6ebb`（#1224 merge）；產生日 2026-11-12（Asia/Taipei）。
> 方法：三個任務各由單組唯讀稽核產出，另有一次獨立抽驗（14 項：11 CONFIRMED、3 PARTIAL、0 REFUTED；逐項抽驗紀錄不在本檔素材內，數字轉述自總管，未在本 PR 重驗）；**仍有未驗項（見 §6）**。
> 授權來源：客戶 2026-11-12 本批授權單（未另立 DEC，repo 內無逐字存檔）；`docs/DECISIONS.md` `DEC-2026-11-12-01` 為優先序 DEC（資料／契約優先、New UI2 安全部分並行；**不授權** Schema、provider、來源、公式、正式門檻、Cloud／Sheet 寫入、migration）。
> 本檔不修改任何程式、workflow、守衛、測試、`CLAUDE.md`、`PROJECT_RULES.md`、`DECISIONS.md`；文中「推薦」一律是**總管讀法，可被客戶推翻**。作者不是獨立 QA。
> 路徑一律寫「檔案::符號」，不寫行號。未寫 secret、NAS 位址、Sheet ID 值。
> 狀態詞只用五種：**已有且可驗證**／**部分缺漏**／**尚未接線**／**無法驗證**／**需要客戶裁示**。「已有且可驗證」＝讀過程式碼，且有測試檔、DEC 或 BL 可指；**不是我們跑綠**（本機沒有依賴齊全的 pytest 環境，所有測試是否綠只能由 CI 驗）。
> 「資料未取得／無法判定」一律寫作 ⬜（UNAVAILABLE），**不得讀成 0 或正常**。

---

## 0. 結論先行

1. **資料層結構清楚、New UI 路徑 Missing≠0 成立；缺口在「未裁」與「未接線」，不在欄位。** L1 取數（`repositories/**`、`infra/**`）→ L2 資料表／契約（`services/v2_tables/**`、`services/v2_domain/**`）→ L3 畫面（`ui_v2`、`ui_v3`）。`services/v2_tables/contract.py` 的列層契約逐欄有型別、可空與值域檢查，取不到值＝該列不寫，不補 0。
2. **四件關鍵事項未裁或未接線**：(a) DG2 canonical identity 仍 shadow（`DG2_SHADOW_ENABLED=False`，production 0 consumer）；(b) FX 閘門 `FX_OBS_DATE_RULE_VERIFIED=False`；(c) Actions 快取（`data_cache/`）尚未接進 New UI，且快取本身有已證實異常；(d) D2 正式契約「核准欄位數＝0」。
3. **Old UI 路徑仍有缺值被補 0／持有**（`composite_score`、`decision_matrix`）；New UI 路徑（`ui_v2`、`ui_v3`、`services/v2_tables`、`services/v2_domain`）對這兩者 0 引用。已登記為 BL-0546（待客戶裁示，本 PR 新增一列，登記不構成動工授權）。
4. **正式 production 入口仍是 Old UI**（`app.py`）；`app.py` 不 import `ui_v2`／`ui_v3`。New UI2（`ui_v3`）只有 🌍 一頁已註冊並實作於獨立 Preview。Streamlit Cloud 入口設定 repo 內查不到＝**NOT VERIFIED**。
5. **低風險候選 UI／文件工作很少**（§3 只找到 2 項＋1 項草稿產出物；皆未授權開工，其中 U2(b)(c) 是否在 NG-2「只修安全／正確性」範圍**無明文**，見 §3.1）。真正擋進度的是客戶裁示（§5）。
6. 本檔**沒有**提出需要新 provider／Schema／來源／公式的「可直接做」項目。

---

## 1. 任務 1｜現有資料層盤點（8 面向）

### 1.1 面向一：資料來源

| 來源／群組 | 實作位置 | 狀態 | 證據與缺口 |
|---|---|---|---|
| 基金 NAV 多來源瀑布（編排結構） | `repositories/fund/fund_orchestration.py::_fetch_fund_single`；A 鏈 `services/moneydj_fetcher.py::auto_fetch_moneydj`；`repositories/fund/nav_metrics.py::fetch_nav` | 已有且可驗證 | 讀碼：安聯官網→FundClear→鉅亨→TCB MoneyDJ→www.moneydj→SITCA→近 30 日→晨星→Yahoo／AlphaVantage／銀行平台／Franklin／JPM→台灣人壽等分支；測試檔 `tests/test_v2_tables_nav_chain_handover.py`、`tests/test_v2_tables_nav_dividend.py` 存在（**未執行**）；客戶 2026-10-13「B 線沿用既有多來源淨值鏈」。`repositories/fund/sources.py` 內 `_src_*` 函式共 25 個（含 meta／div）；其中名稱含 nav 或 url 者 15 個、加 `_src_cache_files` 為 16 個（單組 `grep -cE "^def _src_"` 計數，口徑不同結果不同）；各 adapter 的 live 可達性見下一列 |
| 各 NAV adapter 的 live 可達性 | `repositories/fund/sources.py::_src_*` | 無法驗證 | 需 live＋NAS Proxy／美國 IP；本稽核不連網。GitHub Actions 為美國 IP，台灣來源可能被擋 |
| TDCC OpenAPI | `repositories/fund/sources.py::_src_tdcc_meta`、`tdcc_search_fund_with_error`；`declared_profile.py::fetch_tdcc_listing` | 部分缺漏 | NAV 瀑布裡 TDCC **只有 meta 段**（`_src_tdcc_meta`），沒有 `_src_tdcc_nav`；只能給最新單點，不能給序列。**更正（抽驗後）**：`sources.py` 與 `scripts/fetch_nav_cache.py` 的 docstring 都寫 TDCC OpenAPI 是**境外**基金 API、境內基金（如安聯台灣）走 SITCA；故 `CLAUDE.md` §2.1「TDCC（境內）主」連「境內」標籤都可能標錯。**是否更正憲法需客戶／總管確認；本 PR 不改憲法，僅登記**（見 §5 G12） |
| 市場指標：FRED（含 vintage 首次公布日） | `repositories/macro/fred.py::fetch_fred`、`fred_vintage.py`；L2 `services/v2_tables/market_indicator.py`、`market_view.py` | 已有且可驗證 | 七鍵中四鍵 `phase1="write"`，一鍵受 FX 閘門，兩個 NDC 鍵 `pending`；測試 `tests/test_v2_tables_market_indicator_fred.py`、`test_v2_tables_market_view.py`。FRED 金鑰缺→誠實「⛔ 尚未設定」；Cloud 端 Secrets 是否已設＝無法驗證 |
| 市場指標：Yahoo `^VIX`／`^TWII`／`^GSPC` | `repositories/macro/yf.py::fetch_yf_close_with_error`；`market_view.py` | 已有且可驗證 | TAIEX 唯一來源 Yahoo，標示不寫 TWSE 官方；收盤判定為「暫行」（`DEC-2026-11-09-10`）；A1 報告 CONFIRMED：2026-06-03 兩列與參考不同（成因未判） |
| 匯率 USDTWD（New UI） | `market_indicator.py::FX_OBS_DATE_RULE_VERIFIED`、`build_fx_indicator_table` | 尚未接線 | 閘門 `False`（`DEC-2026-11-08-02`）；冬令探測「是否足以支持開閘：否」（`docs/evidence/fx_obs_date_winter_probe_2026_11_08.md`） |
| 匯率（Old UI） | `repositories/fund/fx_and_main.py::get_latest_fx`；`services/fund_service.py::get_fx_rate_by_date` | 部分缺漏 | 只回數值，不帶觀測日，不受 FX Gate；positive-only 快取（失敗不入 cache）；多個備援分支使用 `verify=False`（單組 grep，數量以現場重跑為準）；`get_fx_rate_by_date` 以 `reindex(freq="D").ffill()` 補週末（docstring 自述 on-or-before、非靜默） |
| 台灣景氣燈號 NDC | `repositories/macro_tw_local_repository.py::fetch_tw_business_indicator_with_error` | 尚未接線 | `phase1="pending"`、`ndc_no_release_date`（來源不給公布日） |
| 台灣 PMI／出口 YoY | `fetch_tw_pmi_local`、`fetch_tw_export_yoy` | 尚未接線 | **更正（抽驗後）**：`services/macro/_helpers.py` 內這兩個名字**不是 re-export**，是 `_TAB1_TTL_CACHE_NAMES` 的快取清除**字串名**。production 消費端為 0 與 `CLAUDE.md` §2.1 2026-09-01 更正一致（單組 grep，不含別名／動態組字） |
| Old UI 總經／新聞／外資／AAII | `app.py`→`ui/tab1_macro*.py` 等 | 已有且可驗證 | New UI 五頁**不**使用這批來源；Old UI 為 read-only 邏輯參考 |
| 國際市場資料集中監控（83） | `docs/v2/83_international_market_data_monitor_design.md` | 需要客戶裁示 | 設計文件不是實作；正式母集合、Eligibility、分母、indicator Schema、writer 仍待 Gate |
| TWSE／MOPS EPS | `scripts/probe_twse_eps*` | 尚未接線 | 僅探針與證據；`market_view.py` 對 EPS／PE 維持 unavailable |
| ISIN→MoneyDJ 決定性對照 | BL-0530 | 需要客戶裁示 | research-only；無已核准 source 前不得啟用 mapping |

### 1.2 面向二：資料庫／快取

| 項目 | 實作位置 | 狀態 | 證據與缺口 |
|---|---|---|---|
| 設定試算表四分頁契約 | `repositories/settings_sheet_repository.py::TAB_SPECS`；`services/v2_tables/contract.py`；`settings_store.py` | 已有且可驗證（程式面） | 寫入一律 RAW、標頭不符不寫、只追加；測試 `tests/test_settings_sheet_repository.py`、`test_v2_tables_contract_settings.py`。**真實 Sheet 標頭／列數／值域＝無法驗證** |
| 個人 Active Sheet | `shared/active_sheet.py`；`services/v2_tables/personal_session.py`、`alo_holdings.py` | 已有且可驗證（程式面） | session-only、無 fallback；測試 `tests/test_active_sheet_state.py` 等。真實覆蓋率＝無法驗證（BL-0545） |
| `nav`／`dividend` 表持久化 | `services/v2_tables/nav_dividend.py` | 已有且可驗證 | **不存**（每次開頁即時抓），客戶 2026-10-13 Q-A＝A；代價是無歷史累積 |
| `data_cache/` 5 檔 | 寫入 `scripts/update_macro_history.py`＋`update_macro_history.yml`；讀取 `services/macro/validation.py`（Old UI） | 部分缺漏 | `metadata.json` 2026-11-08 `last_error=null`；A1 報告：3 CONFIRMED（`PPIACO`、`PCOPPUSDM` 宣告卻零列；06-03 SPX／VIX 與參考不同）、14 SUSPECTED。**New UI 尚未讀此快取**；接線 G1～G6 待客戶（`DEC-2026-11-10-04`、`-05`）。parquet 內容本稽核未讀（無 pyarrow） |
| `cache/nav/TLZF9.json`＋`snap.json` | `repositories/fund/nav_metrics.py`（最終 fallback） | 部分缺漏 | 讀檔：`TLZF9.json` `updated_at=2026-07-22`、`count=10`、末筆 `date=2011-11-18`；**無任何 workflow 執行 `scripts/fetch_nav_cache.py`**（workflow 內僅註解提及，單組 grep），故不會自動更新 |
| 雲端累積 NAV（`nav_history`） | `services/nav_history_gs.py`；cron `weekly_nav_backfill.yml` | 無法驗證 | 累積點不帶出處；`NAV_HISTORY_PROVENANCE_VERIFIED=False` ⇒ B 線不讀；內容無法驗證 |
| L1／L2 TTL 快取與冷卻 | `shared/ttls.py`、`infra/cache.py`、`infra/source_backoff.py` | 已有且可驗證 | `tests/test_source_backoff.py`；`P-RETRYKIND-1`（EXCEPTIONS.md）登記未判定 |
| `fund.db` 匯出 | `export_db.yml`（結果分支 `data`） | 無法驗證 | 僅讀 workflow 檔頭；客戶 2026-11-08 裁示保留該分支 |

### 1.3 面向三：基金身份

| 項目 | 狀態 | 證據與缺口 |
|---|---|---|
| 代碼→MoneyDJ `full_key`（production 主鍵）`services/v2_tables/fund_keys.py::resolve_full_keys` | 已有且可驗證 | 測試 `tests/test_v2_tables_fund_keys.py`；少 `canonicalize_moneydj_url` 一步（檔頭自陳比舊頁嚴） |
| DG2 canonical identity（`services/fund_identity.py`、`fund_identity_shadow.py`） | 尚未接線 | `DG2_SHADOW_ENABLED=False`；非自身檔案只有兩支探針腳本與 `fund_keys.py` 旗標 hook；`IDENTITY_EXCEPTIONS` 預設空 |
| Sheet「基金代號」欄契約違反標示（D2-A＝B） | 尚未接線 | `DEC-2026-11-09-01` 已裁，**尚未實作** |
| `holding_id`／DIRECT | 部分缺漏 | 鍵含 `\|` 不寫入、撞號 raise；**DIRECT 持倉不產生 `holding` 列＝總管暫定，不是客戶裁示** |
| ISIN | 需要客戶裁示 | BL-0530 |
| `shadow_diff` 真實分布 | 無法驗證 | 僅存在於離線探針；live 模式 NOT IMPLEMENTED |

### 1.4 面向四：NAV

| 項目 | 狀態 | 證據與缺口 |
|---|---|---|
| `nav` 表列契約（`contract.py::NAV_FIELDS`，7 欄） | 已有且可驗證 | 型別、可空、值域逐欄檢查；**沒有 `source` 欄**，來源放在 `provenance` 側車 |
| 日期語意 T+1～T+3 | 部分缺漏 | 各來源發布延遲沒有進入列欄位；只有 `ui_v2/thresholds.py::NAV_NOT_READY_DAYS=10` 一個單一門檻（客戶 2026-10-13，非 44 規定） |
| 週末／假日缺值不 ffill（New UI 路徑） | 已有且可驗證 | 掃 `repositories/fund/`、`services/v2_tables/` 無 `ffill`／`bfill`／`fillna(0)`／`interpolate`（單組 grep；Old UI 有若干有註記的例外，如配息 `fillna(0)`＝無配息事件、匯率日表 ffill） |
| 幣別與單位 | 已有且可驗證 | `nav.ccy` 只來自持倉手填或 meta 自報；兩者衝突→整檔不寫；非原生報價來源未宣告幣別→擋下。`P-CNHALIAS-1`、`P-ALIASSHAPE-1` 登記未判定 |
| 預存舊序列退回 | 已有且可驗證 | `fetched_at` 取 `attrs["cache_updated_at"]`，無則整批不寫；畫面標示方式未見落地證據 |
| 累積點出處 | 需要客戶裁示 | `NAV_HISTORY_PROVENANCE_VERIFIED=False` |
| 純數學層 NaN | 部分缺漏 | 離線實測（`services/v2_domain/nav_metrics.py`）：`drawdown_pct([1,nan,2])→0.0`（NaN 被當無回撤）；`return_pct([nan,1,2])→nan`；現況由上游 `nav_row_problems` 擋住，函式自身不防 NaN。屬公式層，修法**未被任何 DEC 授權** |

### 1.5 面向五：日期

| 項目 | 狀態 | 證據與缺口 |
|---|---|---|
| `market_indicator`：`obs_date`／`release_date`／`fetched_at`／`is_revised` | 已有且可驗證 | FRED vintage 首次公布日；`market_view` 的 DGS10／DGS2 走 `fetch_fred`，`obs_date` 是觀測日不是公布日 |
| `nav`／`dividend` 日期 | 部分缺漏 | `DIV_DATE_IS_EX_DATE_VERIFIED=False`；BL-0427(5)：`dividend_record_date` 取值順序與 MoneyDJ 欄位語意相反，**真實資料未驗** |
| 持倉 `last_synced_at` | 部分缺漏 | 由「最後核對日」推定為當日 12:00 台灣時間，**推定值，不是真實同步時間** |
| 證據物件根層 `as_of` | 部分缺漏 | `services/v2_domain/allocation_evidence.py::build_allocation_evidence` 無根層 `as_of`；該生產者無 production 呼叫端 |
| 沿路保留 source／fetched_at | 已有且可驗證 | Old UI 匯率只回數值，日期語意在 L1 就丟失 |

### 1.6 面向六：幣別與 FX

| 項目 | 狀態 | 證據與缺口 |
|---|---|---|
| FX Gate（New UI） | 尚未接線 | 閘門關→`pending[鍵]=fx_obs_date_rule`，不取數不寫列；開閘前條件 (a)～(e) 無一項可寫「已完成」 |
| 原幣 vs TWD、淨投資金額 | 已有且可驗證 | `nav` 只存原幣；市值基準需淨值＋匯率組裝，`ui_v3/adapters/assets_source.py` 市值基準一律 `blocked` |
| 非 USD 外幣 FX 風險 | 部分缺漏 | `services/fx_regime_service.py::SUPPORTED_FX=("USD",)`；非 USD 走 Missing |
| 未知幣別不當 USD | 已有且可驗證 | 幣對不足 6 碼→`None`（客戶 2026-10-10 裁示） |

### 1.7 面向七：績效

| 項目 | 狀態 | 證據與缺口 |
|---|---|---|
| 1Y 含息（還原淨值法） | 部分缺漏 | `services/fund_total_return.py`（客戶 2026-10-23 裁示 1B）；無值回 ⬜；**BL-0427 待客戶裁示**（配息落非淨值日低估、兩窗口不同窗、日頻序列 `window_days≈251` 恆 unavailable、配息日期口徑）；裁示前公式不得改 |
| New UI 績效 | 部分缺漏 | `services/v2_domain/nav_metrics.py` 為價格報酬、非含息；New UI 路徑 0 引用 1Y 含息（單組 grep）；`docs/v2/69` G-RET 口徑待決 |
| Sharpe／σ | 部分缺漏 | 期間／來源／無風險利率口徑未標準化；不得改最低維度數／權重／切點 |
| 對帳 reconcile | 部分缺漏 | `services/reconcile.py`；對帳 chip 住在 Old UI；New UI 未見對帳呈現 |
| 位置（σ rank） | 已有且可驗證 | `services/fund_position.py::compute_fund_position` fail-closed；位置 ⬜ 時僅加 tag，不改動作 |

### 1.8 面向八：缺值與資料健康度

**狀態詞彙（回應「`DataStatus`」查詢）**：`DataStatus` 在 repo **0 命中**（對全 repo 追蹤檔字面搜尋，單組 grep，未經第二組驗證；不含動態組字）。實際是**四～五套並行詞彙，不是一個型別**：

| 套 | 位置 | 值 |
|---|---|---|
| ① 呈現規則表 | `shared/ui_semantics/rules.py`（`ENTRIES`） | ok／attention／missing／undetermined／not_applicable／fetch_failed／stale／threshold_pending／neutral／not_configured／user_param_unset |
| ② view model 狀態鍵 | `ui_v3/viewmodels/common.py` | `STATUS_OK/MISSING/FAILED/STALE/UNDETERMINED`；`FRESH_*`（值域為「最小集合，待客戶裁示覆核」） |
| ③ 44 §5.1 卡片四態 | `services/v2_tables/market_view.py`、`ui_v2/*/logic.py` | ok／資料未備／業務例外／系統錯誤 |
| ④ 頁級嚴重度 | `ui_v2/status_class.py` | 取數失敗＞無持倉＞需要注意＞資料未備＞未設定或不適用＞只評估一部分＞無偏離 |
| 零散 | `ui_v2/page_health.py::KIND_*` | 尚未設定／取數失敗／資料未備／不是最新 |

「同字不同義」已由 `docs/evidence/data_state_vocabulary_crosswalk_d3a_2026_11_08.md` 記載（單組草稿、非核准）。

| 缺值項目 | 位置 | 狀態 | 證據與缺口 |
|---|---|---|---|
| 契約層：取不到值→該列不寫 | `contract.py::_fields_problems` | 已有且可驗證 | None、非有限值、空字串、格式不符皆回 problem |
| 填補旗標 `is_imputed` | `CLAUDE.md` §1 要求填補須帶旗標 | 部分缺漏 | **更正（抽驗後）**：`is_imputed` 字面在所有 `.py`（含測試）**0 命中**，但**等價旗標存在、名稱不統一**：`is_cost_estimated`（`services/policy_fee_optimizer.py`、`ui/helpers/portfolio/fee_deduction.py`）、`is_estimated`（NAV 契約欄位）、`is_proxy`。結論是「旗標名稱不統一」，**不是**「無旗標靠 log」。是否統一命名需客戶／總管裁定 |
| `is_stale`／新鮮度門檻 | `services/v2_domain/holdings.py`、`ui_v2/health.py` 等 | 部分缺漏 | `stale`、`NAV_NOT_READY_DAYS=10`、`MJ_FRESH_DAYS_*`（2／7）三套門檻並存，檔內自陳為不同兩套 |
| 代理資料不當真資料 | `market_view.py` | 已有且可驗證 | NASDAQ／MSCI 維持 Missing，不以 ETF 頂替 |
| 總經健康度 `calculate_composite_score` | `services/macro/composite_score.py` | 部分缺漏 | **更正（抽驗後）**：docstring 自述「缺值/NaN/型別錯誤一律以 0 處理」，但實作是 **NaN／型別錯誤為略過（不計入 `n_indicators`）**，score 缺值才 `or 0`；零指標時 `total=0.0`→「🟡 中性」；已加 `provenance_out["support"]`（`composite_support`）揭露是否缺資料造成，**不改 `total`**；evidence 缺件時 `support=None`（檔內自陳已知缺陷）。消費端：`services/allocation_ladder.py`、`services/realtime_signal.py`、`mcp_server/tools_macro.py`、`scripts/weekly_switch_notify.py`（僅 `--with-macro`，workflow 預設不帶）。**New UI 路徑（`ui_v2`／`ui_v3`／`services/v2_tables`／`services/v2_domain`）0 引用**（單組 grep）。對上 `PROJECT_RULES.md` 13.1「Missing ≠ 0／中性」＝落差，已登記 BL-0546 |
| 決策矩陣 `verdict_to_actions` | `services/decision_matrix.py` | 部分缺漏 | **更正（抽驗後）**：未知 `verdict_level`→全部「持有」**並加 tag**；級別未設定→fail-closed 持有，**只靠 reason 字串標「未設定」（tags 為空）**；σ ⬜ 加 tag。有揭露，但仍是「缺→HOLD」；BL-0428 前為 legacy 語意 |
| 外資買賣超 | `repositories/macro_tw_local_repository.py` | 已有且可驗證 | `fillna(0)`＋print log（靠 print，非結構化旗標） |
| BL-0545 覆蓋率／准入 | `scripts/bl0545_coverage_probe.py` | 無法驗證 | 固定輸出 `real_active_sheet_coverage: "NOT VERIFIED"`、`admission: "NOT DEFINED"`；live 模式 NOT IMPLEMENTED |
| D2 正式契約 | `docs/evidence/d2_contract_candidates_returns_identity_holdings_2026_11_08.md` | 需要客戶裁示 | `DEC-2026-11-11-04`：正式核准欄位數＝0；17 列皆 Pending |

### 1.9 資料層 vs AI 推理層（可疑點，登記不修）

New UI 路徑分離乾淨：`ui_v2` import 守衛禁止 import 舊樹；`ui_v3/viewmodels/action_slot.py::ACTION_SLOT_SOURCES_ENABLED=False`；Complete Evidence 生產者無 production 呼叫端。可疑點均屬 Old UI／周邊：(1) `composite_score` 缺值當 0 後仍可驅動 `mcp_server/tools_macro.py` 的 `action_light`；(2) `decision_matrix` 缺→持有；(3) `mcp_server/tools_macro.py` 輸出混入 UI 字樣；(4) 若干 UI 層持有取數／快取責任（`P-LEDGERNAV-1`、`P-NDCCACHE-1`、`P-UISUBPROC-1`，EXCEPTIONS.md 已登記）；(5) `services/ai_service.py` 未見自行補數字，但 `ai_prompts.py` 與各 UI AI 區塊如何處理缺值**未逐檔審查**。

### 1.10 文件／程式不一致

| # | 內容 | 標記 |
|---|---|---|
| B-1 | `CLAUDE.md` §2.1 TDCC 標「境內／NAV 主」；程式無 TDCC NAV adapter，且 docstring 寫 TDCC OpenAPI 為境外 | 已確認（見 §1.1 更正） |
| B-2 | `update_macro_history.yml` 註解提及與 `fetch_nav_cache` 每日 cron 錯開，但無 workflow 執行 `scripts/fetch_nav_cache.py` | 已確認（單組 grep） |
| B-3 | `fetch_fund_multi_source` docstring 的 NAV 順序（快取→FundClear→鉅亨→TCB→SITCA）與 `_fetch_fund_single` 實際分支不符 | 已確認 |
| B-4 | `cache/nav/TLZF9.json` 末筆 2011，與「保留作最終 fallback」的目的不相稱 | 已確認（檔案事實）／推論（被採用時的後果） |
| B-5 | `CLAUDE.md` §1 的 `is_imputed` 字面 0 命中；等價旗標名稱不統一 | 已確認（見 §1.8 更正） |
| B-6 | `PROJECT_RULES.md` 13.1 對上 `composite_score`／`decision_matrix` | 已確認；已登記 BL-0546 |
| B-7 | `docs/v2/45_fund_db_inventory.md` 列數為 2026-09-21 快照，非現況 | 已確認 |
| B-8 | Old UI 匯率不受 FX Gate 管、不帶觀測日 | 已確認 |
| B-9 | `NAV_NOT_READY_DAYS=10` 與 `MJ_FRESH_DAYS_YELLOW` 並存 | 已確認（有意登記） |
| B-11 | `CLAUDE.md` §3.1 開頭「requirements.txt 無 pandera」與同節「pandera 已 pin」自相矛盾 | 引 `CLAUDE.md` 自陳（該檔已標註未修；本 PR 不改憲法） |

---

## 2. 任務 2｜New UI2 五頁資料契約對照

### 2.1 五頁與權威層級

正式五頁與順序：**🌍 市場與趨勢（mkt）→ 💼 我的資產（ast）→ 🔍 找基金（exp）→ 🤖 AI 投資總結（ai）→ ⚙️ 設定（set）**。權威：`PROJECT_RULES.md` 13.2 第 1 點；`DEC-2026-10-29-06`／`-07`；程式側 `ui_v3/shell/registry.py::IA_PAGES`。文件之間**未發現五頁名稱／順序的實質衝突**（限讀過範圍）。

| 層 | 內容 | 證據 |
|---|---|---|
| 正式 Runtime | Old UI：`app.py` 9 格 tabs（5 正式＋4 `[新]` 並行預覽），頁名為舊名；`app.py` 不 import `ui_v2`／`ui_v3` | 單組 grep；Streamlit Cloud main file repo 內查不到＝NOT VERIFIED |
| Preview A：`ui_v2` B 線 | `ui_v2/app_preview.py::PAGES` **僅 4 頁**（mkt／ast／exp／set；alo 與 hld 併入 ast）；讀真資料（L3→L2→L1）；maintenance-only（`DEC-2026-11-02-05` NG-2）。**更正（抽驗後）：不是「五頁皆讀真資料」** | `ui_v2/app_preview.py::PAGES` |
| Preview B：`ui_v3` New UI2 | 只導覽 `registered_pages()`＝🌍 一頁；守衛不得被 `app.py`／`ui/`／`ui_v2/` 引用 | `ui_v3/shell/registry.py::IA_PAGES` |
| PoC／fixtures | `ui_v3/fixtures`（僅測試）；`poc/dual_theme_isolated/` | 守衛 `test_ui_v3_fixtures_are_fake_guard` 等 |
| 研究草案 | `docs/v2/82`（部分核准）、`83`、D2 候選、`actions_cache_newui_wiring_gap` | 各檔檔頭 |

### 2.2 文件地位與衝突（不自行裁決）

| # | 項目 | 內容 | 性質 |
|---|---|---|---|
| C2 | 79／80／81／82 的「凍結」與「現行規格」地位 | **更正（抽驗後）**：不寫「皆 frozen」。事實：`PROJECT_RULES.md` 凍結清單不含 79／80；`PROJECT_RULES.md` 0.5 明寫 82 是「U1～U5 UI 設計已核准、其餘仍待裁示的草案，不是現行規格」；`docs/HANDOFF.md` §0 第 4 點卻把 79／80／81／82 與 frozen 44、子法 1＋57 並列為「正式 SSOT／規格」。**清單用語與 PROJECT_RULES 0.5 不一致，需確認**（總管讀法：79／80＝正式 input contract，不等同 frozen；82＝部分核准草案） | 需客戶／總管確認 |
| C3 | 🤖 輸出「客戶六項」對映 67 §6.1 六段／§8.9 四區 | 未確認前不改 67 | BL-0540 G-5，待客戶裁示 |
| C4 | 資料健康度「集中 ⚙️」vs 44 頁內資料狀態塊 | 總管推薦由各頁 New UI2 wireframe 承接、44 不解凍 | BL-0540 G-3，待客戶裁示 |
| C5 | `資料不足`／`此圖目前沒有可畫的資料` 與 `◇ 資料未備` 並存或取代 | 目前並存於 `rules.py` | BL-0540 G-2，待客戶裁示 |
| C6 | 44 `dividend.pay_date` 語意 | amendment 文字未起草 | BL-0534 |
| C9 | `DEC-2026-11-12-01` 的 provenance | 要點轉述，無逐字存檔；客戶實際同意範圍專案 AI 不可獨立核對 | 引用時別當逐字裁示 |
| — | 已解決 | 🌍「國際｜S&P 500」卡移除；歸一化基準 100 | 不需再問 |

### 2.3 五頁總表

| 頁 | 狀態 | 資料契約齊備度 | 可否安全施工 | 主要 Gate |
|---|---|---|---|---|
| 🌍 市場與趨勢 | `ui_v3` Preview 已實作並有 live 接線；`ui_v2` 並存 | 高（VM＋守衛＋live；缺綜合判定／新鮮度門檻／部分來源） | 僅限已核准設計範圍 | aggregation rule、freshness、VIX 門檻、FX、cutover（BL-0535） |
| 💼 我的資產 | `ui_v3` 無頁（未註冊，`wireframe_not_approved`）；有內部 adapter＋Domain 證據層；`ui_v2` live | 中（D2 核准欄位＝0；摘要四格無算法；市值基準 blocked） | **不可（需 Gate）** | BL-0542 G-1／G-3／G-4／G-5、BL-0545、D8 |
| 🔍 找基金 | `ui_v3` 無頁；`ui_v2` EXP-0～7 live；Batch E lookup 未實作 | 中低（lookup／ISIN 無來源） | **不可（需 Gate）** | New UI2 🔍 wireframe（BL-0536-G3）、BL-0530、D2 |
| 🤖 AI 投資總結 | 無頁；導覽佔位不可進（建構時拒絕 `registered=True`） | 無（Digest 無 schema、無 production 生產者） | **不可（需 Gate）** | Phase 7、Digest、Risk Cap（BL-0495／0496）、BL-0528、BL-0540 G-5 |
| ⚙️ 設定 | `ui_v3` 無頁；`ui_v2` live；Rule Registry／Digest Viewer／通知皆無程式 | 中（`ui_v2` 契約完整；New UI2 無） | **不可（需 Gate）** | New UI2 ⚙️ wireframe（BL-0536-G4）、Rule ID 格式、BL-0540 G-3、BL-0534 |

### 2.4 每頁要點（元件→資料→缺值→Gate）

**🌍**：元件 `ui_v3/pages/mkt.py`、`ui_v3/viewmodels/market_page.py::MarketPageModel`；資料 TAIEX／S&P 500／VIX（Yahoo）、美10Y／2Y（FRED，觀測日非公布日）、信用／期限利差、政策利率；live 經 `ui_v3/adapters/market_page.py` → `services/v2_tables/market_view.py` → L1。缺值四態＋原因代碼，非 ok 不得有數值（建構時驗證）；「市場狀態」「是否需注意」兩枚獨立 chip 無規則時恆 `⬜ 無法判定`。**已核准**：版面、比較圖（基準 100）、字樣（`APPROVED_WORDING`）、視覺 G3／G6 限縮施工（#1207）。**未核准**：市場綜合判定規則、新鮮度門檻、VIX 門檻、深色模式正式施工、Preview→正式 cutover。可施工範圍：僅 `ui_v3` Preview 內已核准版面／字樣／樣式維護與測試。

**💼**：`ui_v3` 無頁；`ui_v2/asset/page.py`、`ui_v2/alo/logic.py::_build_alo2`、`ui_v2/hld/logic.py`。持倉只讀使用者 Active Sheet（無 fallback）；摘要四格（總資產／總損益／報酬／配息）**一律 Missing（`◇ 資料未備`）**，無核准算法（G-4）。**已登記落差（更正措辭，抽驗後）**：`ui_v2/alo/logic.py::_build_alo2` 缺 FX 時分母只加總有值類別，這是**尚未對齊 `DEC-2026-11-04-02` 方案 A 的已登記落差**（BL-0542 G-1 補註）；`ui_v2` 為 maintenance-only；頁尾仍列「合計未涵蓋」。已核准僅設計層（主圖在前、U1～U5、缺 FX 方案 A、「淨投資金額」用語）；所有金融口徑未核准。

**🔍**：`ui_v2/exp/page.py`（EXP-0～7）、`ui_v2/exp/source.py::load_live`；母體＝選股池代碼；禁止欄位＝分數／星等／排名／推薦；Batch E「找一檔基金」lookup 未實作；ISIN 無來源（維持「尚未啟用」）；New UI2 wireframe 無。

**🤖**：`ui_v3/shell/registry.py` 佔位＋`action_slot.py`（`state` 只能 None 或「無法判定」，`ACTION_SLOT_SOURCES_ENABLED=False`）；A 線 `services/ai_service.py` 現行 prompt 與正式裁示牴觸（BL-0528，A 線不遷移）。全部未授權。

**⚙️**：`ui_v2/set/page.py`（SET-0～8）；`ui_v2/set/source.py::load_live`；OAuth scope／callback／credential／token 不得改；Rule Registry、Digest Viewer、通知偏好、Delivery audit 無程式（單組 grep，字表非窮舉）；LINE 推播能力存在於 `infra/line_push.py`，未接 New UI2。

### 2.5 UI 層「自行抓資料／補值／合併投資語意」檢查（單組 grep，不得讀成「UI 已掃乾淨」）

- 自行抓資料：對 `ui_v2`、`ui_v3` 搜網路 client／SDK 字表，僅命中 `ui_v2/app_preview.py` 檔頭的**文字說明**，無實際 import／呼叫。字表不含所有可能形態。
- 自行補值：對 `ui_v2`、`ui_v3` 搜 `fillna`／`ffill`／`bfill`／`interpolate` → 0 命中。`or 0` 寬掃僅命中顯示用計數／剩餘秒數。例外觀察：`_build_alo2` 對「有目標但無持倉」類別預設 `{"value": 0.0}`（真 0 或缺值需看資料完整性）與分母只加總有值類別（見上）。`ui_v3` VM 強制「非 ok 不得有數值」。
- 合併成單一分數：未見把趨勢／風險／Risk Cap／信心／完整度合併成數值分數（`mkt` 三檔未逐行讀完）。**非分數的合併**：💼 P3 頁級狀態頭條（`ui_v2/asset/page_status.py::aggregate`，`is_rule_result: False`，`DEC-2026-10-30-04`）；`ui_v2` MKT-0 結論燈（只依資料狀態取最嚴）。Risk Cap／System Action State 未實作。

---

## 3. 任務 3｜低風險候選 UI／文件工作、資料缺口、方案比較

### 3.1 低風險候選 UI／文件工作（僅 2 項＋1 項草稿產出物；皆**不在本階段授權內**，也**不是已核准施工項**）

判斷準則：有明文已核准的 DEC／文件條文；不新增資料來源／欄位／公式／門檻；不改版面結構；有現成守衛或能寫成測試。

| # | 工作 | 依據 | 涉及檔案 | 草稿先行？ | 風險 |
|---|---|---|---|---|---|
| U1 | **BL-0532 殘餘**：正式模式仍露出的「⬜ 資料未備／⬜ 資料未取得」統一為 `◇ 資料未備`（先做影響掃描，只改殘餘） | `DEC-2026-11-02-01` 甲(四)；`docs/v2/79` §14；BL-0532（「屬機械式」，但明寫需客戶開實作批） | `ui_v2/mkt/chart.py::TEXT_EMPTY`、`ui_v2/mkt/market_section.py::_STATUS_TEXT`、`ui_v2/symbols.py::mark_missing`、`ui_v2/sections.py::MKT6_EMPTY_LINE` | 否（只換字樣符號） | 示範模式須照舊 ⬜；`TEXT_EMPTY` 目標字樣有歧義（需客戶回 Q2）；`symbols.apply` 已在正式模式做渲染期改寫，可見殘餘可能只剩 `⬜ 資料未取得`（**推論，未跑 AppTest**）；`ui_v2` 為 rollback candidate，價值有限 |
| U2 | **文件／註解一致性小批**：(a) HANDOFF §0 把草案 82 與 79／80／81 並列為「正式 SSOT」→改標；(b) `ui_v2/shell.py` docstring「五項」與 `PAGES` 四項不一致；(c) `fetch_fund_multi_source` docstring 的 NAV 順序與實際不符 | (a) `PROJECT_RULES.md` 0.5；(b) `docs/v2/79` §15 #8 措辭修正；(c) B-3 | 純註解／docstring／HANDOFF | 否 | (b)(c) 是否在 NG-2「只修安全／正確性」範圍內**無明文**，建議併入客戶一句話確認；(a) 屬總管讀法 |
| U3 | **🔍 找基金 New UI2 文字線框草稿**（草稿先行產出物本身，**不是 UI 程式碼**；不接資料） | `DEC-2026-11-01-02`（Batch E 範圍已核准）；`DEC-2026-11-02-05` NG-5；BL-0536-G3 | 新增文件於 `docs/v2/`（編號由客戶／總管指派） | 本身就是草稿，須送客戶審 | 線框內容越界風險（D2 欄位、ISIN 啟用）；線框不等於施工授權；「查無 vs 取數失敗」分流需新資料行為（G-E3），線框只能標示不能承諾 |

**有意識沒列入的近似項目（避免被誤當已核准）**：`_build_alo2` 缺 FX 分母（涉及 G-1 公式承接，須獨立稽核）；`nav_metrics.drawdown_pct` NaN（公式層，無 DEC 授權修法）；BL-0455／BL-0457（需客戶指定用語）；BL-0412、BL-0483、BL-0514（排序／尺寸變更，從嚴先出草稿；BL-0412 可能已過時，未驗）；BL-0372（匯出檔 ⬜ vs ◇，另裁）；12px→13px、深色模式、`grey`／`neutral` 區分（`DEC-2026-11-11-03` 併入「下一個已授權 UI 批」，目前沒有）；🌍 兩枚 chip 的非「無法判定」值；Old UI `composite_score`／`decision_matrix`（read-only 邏輯參考，BL-0428／BL-0440 待裁）；💼 Stage 1 線框（停在客戶 UI Review）。

### 3.2 尚須解決的資料缺口 D1～D16（依阻擋程度；「客戶」＝落在 v1.0 Stop／Decision Gate）

| 序 | 缺口 | 阻擋哪裡 | Gate | 誰處理 |
|---|---|---|---|---|
| D1 | 真實 Active Sheet 覆蓋率 NOT VERIFIED；使用者暫不提供輸入；探針 live 模式 NOT IMPLEMENTED | 💼 任何「真實資料」宣稱；DG2 證據；D2 分母 | BL-0545（唯一全域 NEXT）、`DEC-2026-11-07-03` | 使用者（專案 AI 不得請求憑證） |
| D2 | D2 正式契約（身份／NAV／績效）核准欄位數＝0，17 列 Pending | 💼／🔍 `ui_v3` 資料接線 | `DEC-2026-11-11-04` | 客戶逐列核可 |
| D3 | DG2 仍 shadow；D2-A＝B 未實作；ISIN→MoneyDJ 無來源；DIRECT 持倉不產生 `holding` 列（總管暫定） | 🔍 lookup；💼 DIRECT | `DEC-2026-10-28-05`、`-10-29-01`、`-11-09-01`；BL-0530 | 客戶（identity 規則） |
| D4 | FX 閘門關；冬令探測證據不足；非 USD 驗證法未定 | 💼 市值基準；🌍 USDTWD 卡 | `DEC-2026-11-08-02` | 客戶 |
| D5 | 💼 口徑：摘要四格、配息推估、狀態詞對映、G-1 PORT 後續、NAV 10 日規則 | 💼 整頁 | BL-0542 G-1／3／4／5；`DEC-2026-11-05-03` | 客戶（formula） |
| D6 | 績效口徑：New UI 無 1Y 含息；BL-0427 未裁 | 💼／🔍 績效顯示 | BL-0427、BL-0524、`docs/v2/69` | 客戶（formula） |
| D7 | 🌍 市場綜合判定規則、新鮮度門檻、VIX 門檻均無 | 🌍 兩枚 chip 只能 ⬜ | BL-0369、BL-0536-H4 | 客戶（threshold） |
| D8 | Actions→Cache→New UI 未接線；快取已證實異常 | 🌍 取數失敗回退 | `DEC-2026-11-10-04`（G1～G6）、`-05`（G1～G10） | 客戶 |
| D9 | 狀態詞彙四～五套並存；`資料未備` 同時裝三種成因 | 跨頁字樣統一 | BL-0540 G-2／G-3；BL-0532 | 機械部分＝U1；crosswalk 獨立複驗可自理；語意取捨＝客戶 |
| D10 | NDC 無公布日；TW PMI／出口 YoY 無 production 消費端 | 🌍 台灣景氣類卡 | 客戶 2026-09-26 Q3(c) | 客戶 |
| D11 | 配息日期語意：`DIV_DATE_IS_EX_DATE_VERIFIED=False`；`pay_date` amendment 未起草 | 💼 配息行事曆 | BL-0534、BL-0427(5) | 客戶；amendment 草稿可自理 |
| D12 | NAV 供應鏈：累積 NAV 無出處；TDCC 只有最新點；`cache/nav/TLZF9.json` 靜態 | NAV 序列完整度 | `P-NAVCACHE-1`；`DEC-2026-11-08-01` | 客戶（開閘）；B-1／B-3 文件修正可自理 |
| D13 | 🤖：Digest 無 schema／生產者；Risk Cap、減碼 trigger；A 線 prompt 牴觸 | 🤖 全部 | BL-0527、BL-0495／0496、BL-0528；Phase 7 | 客戶 |
| D14 | Old UI 缺值→0／中性／持有；`is_imputed` 字面 0 命中（等價旗標名稱不統一） | 擋 Old→New 行動語意遷移 | BL-0428、BL-0440、**BL-0546**；`CLAUDE.md` 不得修改（BL-0538） | 客戶 |
| D15 | Streamlit Cloud 入口、Secrets、真實連線全部 NOT VERIFIED | 正式驗收、cutover | BL-0535、BL-0544 | 客戶提供 Cloud 證據 |
| D16 | 國際市場監控新 provider／獨立 Sheet（83） | 選配 | `DEC-2026-11-09-05`～`-10` | 客戶 |

專案 AI 在現有授權內可自理的僅有：D9 crosswalk 獨立複驗、D11 amendment 文字草稿、D12 的 B-1／B-3 文件修正、各頁線框草稿。其餘全部要客戶。

### 3.3 三個實施方案比較（成本欄一律 **ESTIMATE**，未實測）

假設每個 PR＝實作 1 組＋非作者獨立稽核 1 組＋總管複驗，約 0.7M tokens；CI Fast 約 20 分＋Slow 約 25 分（Slow 為 `continue-on-error`，仍須逐 lane 看 `conclusion`）。

| 項目 | α：字樣／文件修補，不碰版面 | β：α＋🔍 New UI2 文字線框草稿 | γ：資料缺口整理成 Gate 清單，客戶一次裁示後再開工 |
|---|---|---|---|
| 內容 | PR-α1＝U1；PR-α2＝U2 | α 的兩個 PR＋PR-β3＝U3（docs-only） | 1 個 docs PR：D1～D16 收斂為 ≤10 題 A／B／C，每題附推薦與風險 |
| regression 面 | 低（U1 若字面全統一則 37 檔／169 行測試需同步，面積變大） | 同 α；風險在線框越界 | 零程式 regression；風險在推薦被誤讀為已核准、題目過多 |
| 速度 | 2 PR，序列約 1.5～2 小時 | 3 PR，另加客戶線框審核等待 | 1 PR；之後取決於客戶裁示節奏 |
| Token（ESTIMATE） | ≈1.4M | ≈2.2M | ≈0.8M |
| 客戶決策次數 | 1（開 BL-0532 實作批＋Q1／Q2） | 2～3 | 1 輪（≈8～10 題） |
| 使用者可見價值 | 很小 | 小～中 | 無直接可見，但解鎖最多後續工作 |
| 可逆性 | 全可 revert | 全可 revert | 全可 revert |

**推薦 α 並行 γ（總管讀法，可被客戶推翻）**：α 風險最低、不觸發草稿先行，但**老實說使用者可見價值很小**；γ 檔案不與 α 重疊，是真正的解鎖。β 只在客戶明確想先看 🔍 時才值得。**不推薦的捷徑**：直接寫 `ui_v3` 💼／🔍／⚙️ 程式碼；碰 `_build_alo2` 分母；改 `nav_metrics`；任何 FX／快取／provider 動作。

### 3.4 若客戶選 α，PR-α1 前要問的兩題（A／B／C 表）

**Q1：BL-0532 做多大？**

| 方案 | 優點 | 缺點 | 風險 | 推薦 |
|---|---|---|---|---|
| A 只做影響掃描確認後的「殘餘」＋防回流守衛 | PR 小、審得完 | logic 層仍留 ⬜ 字串（渲染期改寫） | 低；可能發現殘餘為 0 | **推薦** |
| B `ui_v2` 110 行字面全部統一 | 與 BL-0532 字面最接近 | 37 檔／169 行測試同步；易誤改示範模式 | 中 | 不推薦 |
| C 不做，等 cutover 自然取代 | 零成本 | 擱置已核准項 | 低但留不一致 | 備選 |

**Q2：`ui_v2/mkt/chart.py::TEXT_EMPTY`（「⬜ 資料未取得，無法繪圖」）改成什麼？**

| 方案 | 優點 | 缺點 | 風險 | 推薦 |
|---|---|---|---|---|
| A 改為 `◇ 資料未備`（BL-0532 原文） | 對齊 BL-0532 與 79 §11 | 失去「無法繪圖」資訊 | 可能與 `ui_v3` 已核准字樣分歧 | 備選 |
| B 維持現狀，登記為版面示意字樣 | 不動語意 | BL-0532 留尾巴 | 低 | 備選；客戶不表態預設 B（最小改動） |
| C 改為 `此圖目前沒有可畫的資料` | 兩條線一致 | BL-0540 G-2 未裁，會預先替客戶答題 | 中（越界） | 不推薦（等 G-2） |

---

## 4. 抽驗結果與已套用的更正

獨立抽驗結果（轉述自總管）：14 項中 11 CONFIRMED、3 PARTIAL、0 REFUTED。下列 8 項措辭更正已套用於本檔；作者在本 PR 另對照 repo 重驗了標「✔」者（其餘維持單組盤點狀態）。

| # | 更正 | 本 PR 重驗 |
|---|---|---|
| 1 | TDCC：除「無 NAV adapter」外，補 docstring 寫 TDCC OpenAPI 為境外、境內走 SITCA；`CLAUDE.md` §2.1「境內」標籤可能標錯；本 PR 不改憲法 | ✔ `sources.py::_src_tdcc_meta` 僅 meta；`scripts/fetch_nav_cache.py` 註解「走 SITCA 而非 TDCC 境外 API」；`_src_tdcc_nav` 在 `repositories/fund/` 0 命中 |
| 2 | `is_imputed`：字面 0 命中，等價旗標存在，寫成「名稱不統一」 | ✔ 全 repo `.py`（含測試）0 命中；`is_cost_estimated`／`is_estimated`／`is_proxy` 多檔存在 |
| 3 | `decision_matrix`：未知 verdict 有 tag；級別未設定只靠 reason | ✔ 讀 `services/decision_matrix.py`（未知 verdict 加 tag；未設定 fail-closed 持有） |
| 4 | `composite_score`：NaN／型別錯誤為略過，score 缺值才 `or 0`；零指標「中性」；`support` sidecar；消費端與 New UI 0 引用 | ✔ 讀 `composite_score.py`（`float(v.get("score", 0) or 0)`、sidecar）；`ui_v2`／`ui_v3`／`services/v2_tables`／`services/v2_domain` 對 `composite_score`／`decision_matrix` 0 命中；`weekly_switch_notify.py` 的 `--with-macro` 為 opt-in |
| 5 | `services/macro/_helpers.py` 的 tw_pmi／tw_export 是 `_TAB1_TTL_CACHE_NAMES` 字串名，非 re-export | ✔ 讀該檔 `_TAB1_TTL_CACHE_NAMES` 區塊 |
| 6 | `_build_alo2` 缺 FX 分母：寫成已登記落差，不寫「缺陷／相反」 | ✔ 該函式分母 `sum(... if v["value"] is not None)` 存在；落差登記於 BL-0542 G-1 |
| 7 | `ui_v2` Preview 為 4 頁（alo／hld 併入 ast） | ✔ `ui_v2/app_preview.py::PAGES` 四列 |
| 8 | HANDOFF §0 第 4 點並列 79／80／81／82：寫成「用語不一致，需確認」 | ✔ `PROJECT_RULES.md` 0.5 對 82 的措辭；HANDOFF §0 第 4 點原文 |

另：`DataStatus` 在 repo 0 命中，實際為四～五套並行詞彙（✔ 全 repo 字面搜尋 0 命中）；Streamlit Cloud 入口 repo 內查不到＝NOT VERIFIED。

---

## 5. 下一個需要客戶裁示的 Decision Gate 清單（推薦＝總管讀法，可被客戶推翻）

| # | Gate | 問題（商業語言） | 推薦 |
|---|---|---|---|
| G1 | BL-0545 | 使用者何時提供合法輸入（方式 A 本人 session／方式 B 匿名清單） | 維持唯一全域 NEXT；不請求憑證 |
| G2 | 79／80 凍結地位＋HANDOFF 對 82 的標示（C2） | 兩份正式輸入契約是否列入凍結清單；HANDOFF 是否改標 82 為部分核准草案 | 79／80 維持「正式 input contract，不等同 frozen」；HANDOFF 改標（純文件） |
| G3 | BL-0540 G-2／G-3／G-5 | 資料不足與資料未備並存或取代；健康度集中 ⚙️ 如何承接；AI 六項對映 | G-2 並存；G-3 由各頁 wireframe 承接、44 不解凍；G-5 先不改 67 |
| G4 | 🌍 市場綜合判定、新鮮度、VIX 門檻（D7） | 要不要有正式判定規則與「何時算舊」 | 先不裁，維持 `⬜`；若裁，逐源以發布頻率證據論證，不用舊樹 22／30 當預設 |
| G5 | cutover（BL-0535）與深色模式正式施工 | 何時把正式入口切到 `ui_v3` | 💼／🔍／⚙️ wireframe 與資料契約過關前不 cutover |
| G6 | 💼 BL-0542 G-3／G-4／G-5、NAV 10 日規則 | 摘要四格、配息推估、狀態詞 | 走 82 第一切片（資料契約＋fixture＋缺值 VM）；G-4 暫不開 |
| G7 | 💼 Stage 1 線框審批 | 客戶審精修後線框 | 照現行停點，不跳 Stage 3 |
| G8 | 🔍 BL-0530 ISIN、New UI2 🔍 wireframe（BL-0536-G3）、D2 首批逐列核可 | ISIN 要不要啟用 | ISIN 維持「尚未啟用」；先逐列審 D2 Required 17 列；lookup 只收 MoneyDJ code |
| G9 | 🤖 Phase 7 前置：Digest schema、Risk Cap、BL-0528 | 何時啟動 AI 總結；A 線牴觸 prompt 如何處置 | 維持 Phase 7 前不啟用；BL-0528 另案評估 |
| G10 | ⚙️ wireframe（BL-0536-G4）、Rule ID 格式、BL-0534 | Registry 殼、通知偏好版面 | Registry 殼先只列名稱與出處；`pay_date` 先起草 amendment 文字 |
| G11 | FX 閘門 D8；Actions→Cache 讀取路線（`DEC-2026-11-10-04`） | 閘門何時可開；快取何時能當主來源 | FX 維持關閉；快取最窄版 α（僅 DGS10／DGS2、僅取數失敗回退）為研究推薦，尚未授權 |
| G12 | `CLAUDE.md` §2.1 TDCC「境內」標籤／§3.1 pandera 自相矛盾（BL-0538 不延伸授權修憲法） | 是否登記為憲法勘誤待另案 | 僅登記，不在本批修改 |
| G13 | BL-0546 Old UI `composite_score`／`decision_matrix` 缺值語意（新登記） | 缺值→0／中性／持有是否沿用 legacy | 不動 Old UI；等 BL-0428／BL-0440 一併裁；New UI 不得沿用 |

---

## 6. 盲點與未驗項

1. **未執行任何測試**；「已有且可驗證」是讀碼＋測試檔存在＋DEC／BL，不是跑綠。依賴齊全環境下是否綠只能由 CI 驗；本 PR 的 QA／CI 結論 NOT VERIFIED。
2. **parquet 內容未讀**（無 pyarrow）；`data_cache` 列數引 `metadata.json` 與 A1 報告，未獨立重算。
3. **全稱句的限度**：所有「0 命中／只有 N 處／無 production 消費端」皆為單組字面 grep（`DataStatus`、`is_imputed`、`fetch_tw_pmi_local`／`fetch_tw_export_yoy` 無消費端、「`ui_v2`／`ui_v3` 無自行抓資料／補值」、「`ui_v3` 只有 🌍 已註冊」），**不含別名、動態組字、字串內嵌 import**，**未經第二組驗證**。
4. **大檔只讀頭部**：`docs/v2/44`（約 94 萬字元）、`DECISIONS.md`、`BACKLOG.md`、`docs/v2/79`／`80`／`81`／`82` 只讀相關節；`ui_v2/*` 大檔、`ui_v3/pages` 部分、Old UI `ui/**`、`services/macro/**` 大部分、`services/health/**` 未逐行讀。「五頁無名稱衝突」限讀過範圍。
5. **未驗證**：Streamlit Cloud 正式入口與 Secrets；真實 Active Sheet／設定試算表內容；各來源 live 可達性；GitHub CI 狀態；`docs/evidence/` 下探針結果內容；`EXCEPTIONS.md` 各 `P-*` 列現況是否仍準確。
6. **成本估算**（tokens、小時）全部是 ESTIMATE，未用歷史 PR 回歸。
7. **決策出處**：多數 DEC 為「要點轉述」，專案 AI 見不到客戶對話本身；`DEC-2026-11-12-01` 僅作「優先序與不授權邊界」引用。
8. 本檔 §4 的抽驗統計（14／11／3／0）轉述自總管，本 PR 未取得逐項抽驗紀錄；其餘由單組盤點產出，作者僅重驗 §4 標 ✔ 的項目。**本檔全文未經獨立 QA。**
