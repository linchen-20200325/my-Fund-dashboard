# 2026-11-05｜程式可達性與資料責任分類：第一輪唯讀盤點

> **性質**：ChatGPT 獨立初步稽核；**不是「死碼可刪」裁示、不是重構／刪除授權**。GitHub main baseline `81827057b6116096ad16cd304540af55a3e1f1af`，CI success。抽樣追查入口、既有架構文件、特定符號的 GitHub code search 與程式檔頭，並非全庫 AST 全引用圖；動態 import／Streamlit Cloud 外部入口／腳本／排程不可能單靠字串搜尋排除。報告中的「確認」只指找到明確連結或重複實作，「疑似」均尚待全庫呼叫圖驗證。
>
> **隔離正在進行工作**：G-2 Preview source PR #1149；登入 UI 規格 PR #1150；New UI2 全站設計 PR #1151。此盤點不改那三條線，尤其不得把 #1149 未合併內容當 main 事實。

## A. 結論矩陣

| 範圍／符號 | 第一輪證據 | 分類 | 目前處置 |
|---|---|---|---|
| `app.py`、`ui/` | `app.py` 是舊正式入口（Cloud 外部設定未核）；`docs/v2/80` §8–10 明確把 Old UI 留作唯讀邏輯參考 | **Legacy-live / DO NOT TOUCH**，不是死碼 | 不刪、不改、不搬畫面；cutover 另 Gate |
| `ui_v2/app_preview.py`、`ui_v2/app_*_live.py` | `ui_v2/app_preview.py` 明列五頁 Live 接線與 OAuth／Active Sheet 路徑；`80` §3.2 分類 RETIRE LATER | **Legacy-rollback candidate**，不是可即刪 | 只保留維運／回切能力；不新增新 UI 功能 |
| `ui_v3/app_preview.py`、`ui_v3/shell/*` | 新 Preview 入口已註冊 🌍；`shell/nav.py` 具 ≤768px 底部導覽；守衛禁止正式入口偷接 | **Current New UI2** | 唯一新 UI 主線、不可刪 |
| `ui_v2/*/page.py::_grid_css` | GitHub code search 命中 mkt／hld／alo／exp／set 五份 | **確認重複 presentation**，非死碼 | 新 UI 用一份共同 layout/token；不在 Legacy 直接合併或刪 |
| `services/v2_tables/alo_holdings.py::load_alo_tables` | 檔頭明說舊 `POLICY_SHEET_ID` 路徑只剩 `refetch_nav` 相容用途；持倉主要改 `load_alo_tables_active` | **Residual reachable compatibility path（文件宣告，待符號呼叫圖複驗）** | 專項列出 caller／CI／Cloud 流量／回切依賴後才判退役，不先動 |
| `services/v2_tables/personal_session.py` | L2 明確包既有 Google OAuth、Pending／Active Sheet、白名單、失效清 Session | **權威認證與選本橋接** | New UI 共用，不重造認證／token 層 |
| `services/fund_identity_shadow.py` | 檔頭宣告由 `fund_keys.resolve_full_keys` 且 `DG2_SHADOW_ENABLED` 預設為 `False`；啟用時才 import；GitHub 搜尋顯示兩處相關 services 引用 | **Conditional shadow／diagnostic code**，不是死碼 | 確認 probe／CI／覆核期與正式 DEC，未經結案前不得刪 |
| `services/v2_tables/market_indicator.py::FX_OBS_DATE_RULE_VERIFIED` | GitHub 目前為 `False`；程式檔頭列出 DST／國定假日等未驗證條件 | **正式資料有效性 Gate** | 不能以整理為名開閘／補 0／改成本口徑 |
| `services/v2_domain/*` | G-1 ①～③已合併，包含 `allocation_evidence.py` 的確定性 Evidence producer | **Current canonical domain candidate / implemented** | 保留單一算法，禁止複製回 UI |
| `services/dividend_calendar_render.py` | GitHub 搜尋在 `ui/helpers/`、`scripts/`、`tests/`、`ui/views/` 等查到名稱 | **有潛在 consumer，未證實死亡** | 先查定時腳本和維運用途再判斷 |
| `services/fundclear_backfill.py` | GitHub 搜尋見 `services/nav_history_gs.py`、`services/nav_history_store.py`、測試等引用 | **不能視為無呼叫者** | 釐清 active vs historical backfill，保留 until proven |
| `tests/ui_v2/*`、Legacy VF | `80` §3.2、§9 說明 golden／字面／AST guard／source／視覺測試分流 | **驗收護欄／歷史回歸資產** | 不因畫面過時就批量刪；依正式 cutover 後退役 Gate |

## B. 資料應重新歸類的地方（最小可行 schema taxonomy）

這是**文件分類與模組責任提案**，不是新增欄位的正式金融合約，不擅自改 frozen 44：

| 正式分類（概念） | 責任 | 現有主要位置／例 | 禁止混淆 |
|---|---|---|---|
| **Identity / Reference** | canonical fund identity、MoneyDJ code／ISIN（若可證）、share class、平台後綴、source-of-identity | `services/fund_identity.py`、`services/v2_tables/fund_keys.py`、shadow；`repositories/fund/*` | Source code ≠ canonical identity；同名或剪後綴不能合併不同基金 |
| **Account / Access / Source Selection** | login state、pending login、選本驗證、active sheet、權限／session 失效 | `services/v2_tables/personal_session.py`、`infra/personal_oauth.py`、`shared.active_sheet` | 登入 ≠ 已選本 ≠ 資料取得成功 |
| **User Holdings / Policy** | 每筆持倉、保單／補充欄、來源試算表、略過列原因 | `repositories/personal_policy_reader.py` → `services/v2_tables/alo_holdings.py` | 個人 Active Sheet ≠ 服務帳戶設定 Sheet；無持倉 ≠ 來源讀失敗 |
| **Market / NAV / FX / Dividend** | 原始可追溯行情、基金 NAV、FX 觀測日與股息／配息日期語意 | `repositories/macro/*`、`services/v2_tables/{market_view,market_indicator,nav_dividend}.py` | 來源取得時間≠觀測日期；除息≠實際入帳；FX 未驗證不套算 |
| **User Configuration / Targets** | 目標類別、basis、容許帶、設定寫入與來源 | `repositories/settings_sheet_repository.py`、`services/v2_tables/settings_store.py` | 使用者設定 ≠ 已核准投資規則；未設≠0 |
| **Canonical / Data Quality** | schema、型別、來源、timestamp、missing、failed、skipped、unread、freshness | `services/v2_tables/contract.py` 和各 loader | `unavailable`≠`neutral`；source failure ≠ zero rows |
| **Deterministic Domain / Evidence** | 既有正式算法與完整證據／母體分母、比較合法性 | `services/v2_domain/`，G1-③ `allocation_evidence.py` | UI 或 AI 不能複製計算；covered-only ≠ full 100% |
| **Presentation / AI** | `ui_v3` ViewModel 是人看的壓縮投影；未來 Digest 才是 OneBrain input | `ui_v3/viewmodels`、未來 Digest | 畫面摘要不等於完整 Evidence；Digest 不得無授權開工 |
| **Diagnostic / Historical / Rollback** | shadow comparator、Old UI、ui_v2 Preview、probe、evidence、rollback tests | `services/fund_identity_shadow.py`、`ui_v2/`、`scripts/probe_*`、`docs/evidence` | 未在正式 UI 出現 ≠ 死碼；可能受排程、稽核或回切使用 |

**最重要的資料整理優先序**：

1. **身份與來源分開**：以 canonical identity + provenance 作為跨頁接線基礎，不把 MoneyDJ code、ISIN、平台碼、Share class 混成單一模糊字串。
2. **帳號選本與兩本 Sheet 分開**：Personal Active Sheet 供個人持倉；Settings Sheet 的 user_setting／fetch_log／market_indicator 有自己的讀寫權限與新鮮度；`POLICY_SHEET_ID` 只標 legacy path，須查 `refetch_nav` 呼叫再退。
3. **原始資料、品質證據、Domain 與 ViewModel 分開**：G1-③ 正在承接後半；未驗證 FX、缺 NAV、略過資料等要在 Evidence 保留，畫面簡化不能抹掉。

## C. 三條清理路線比較

| 路線 | 做法 | 速度 | 風險／總成本 | 判定 |
|---|---|---|---|---|
| A 全庫大掃除 | 見舊檔就刪、資料層一次搬完 | 看似快 | 極高：三代 UI、排程、回切與 frozen 合約容易壞 | ⛔ 不採 |
| B 永遠保留 | 所有歷史檔和重複實作原封不動 | 當下快 | 長期負擔高，容易讓新 UI 重複算錯 | 不推薦 |
| **C 分級盤點＋定點 PORT＋延後清理** | 先標 reachability／owner／source-of-truth、結合現行 G-2 接線，後續小批剝離重複邏輯；功能和 rollback 門檻過後才提刪除 Gate | **可平行、最快可安全執行** | 中低；有 golden、contract、import guard 防漂移 | ✅ 推薦 |

## D. 第二輪必要的機械化驗證（現在尚未執行）

1. 從 `app.py`、`ui_v2/app_preview.py`、`ui_v3/app_preview.py`、`scripts/`、GitHub workflows 建**靜態 import／symbol 可達圖**；排除 string-based dynamic imports、Streamlit Cloud 外部設定的漏網。
2. 每個候選函式列出：宣告位置、非測試呼叫者、測試呼叫者、cron／workflow／script 入口、最近修改、資料語意依據、rollback 依賴、移除風險；證據不足只標 `CANDIDATE`。
3. 判定 `DEAD_CONFIRMED` 需同時無 runtime／script／workflow／rollback／測試契約用途，另需負向測試或確認執行證據；CI 綠不代表可刪。
4. 先沿 G-2 adapter **真實**回傳欄位建立「來源→欄位→資料類別→domain→UI」矩陣；禁止從名字反推存在的欄位、推估 source freshness。
5. 同一種 deterministic 算法以 `services/v2_domain` 為單一合法落點；查到別的平行 formula 先列 diff＋golden，不做自動統一。
6. 第二輪交付是清單與 scope-protected PR；**是否刪除／重構須另批授權**。依現行 PROJECT_RULES Stop／Cutover Gate，不移動 Old UI、ui_v2 的正式禁改界線。
7. 每個真工程批最少一組真正獨立稽核；有 L3／frozen／公式／身份／FX 等需客戶 Decision Gate。

## E. 第一輪取證索引

- 程式入口：`app.py`、`ui_v2/app_preview.py`、`ui_v3/app_preview.py`、`ui_v3/shell/registry.py`。
- 分層與保留：`docs/v2/80_new_ui2_architecture_proposal.md` §3.2、§8–10；`PROJECT_RULES.md` §13.2、0.4。
- 身份／Shadow：`services/fund_identity_shadow.py` 頂部、`services/v2_tables/fund_keys.py`；GitHub code search for `fund_identity_shadow`。
- 個人選本：`services/v2_tables/personal_session.py`。
- 兩種持倉入口：`services/v2_tables/alo_holdings.py`，Legacy `ui_v2/{hld,alo}/source.py`。
- 設定與 Legacy 更新：`services/v2_tables/settings_store.py`、`ui_v2/app_preview.py`、BL-0460。
- FX：`services/v2_tables/market_indicator.py` 的 `FX_OBS_DATE_RULE_VERIFIED=False` 與觀測日條件。
- 重複 CSS：GitHub code search `_grid_css` in `ui_v2`，五個 `page.py`。
- Dividend／Backfill：GitHub code search `dividend_calendar_render`／`fundclear_backfill`，存在多個潛在 consumer，不可推定死碼。
- **本輪未做**：完整 clone + AST reachability、動態程式跟蹤、真正 Cloud 流量、所有 secrets／外部工作排程盤點、任何寫入與程式刪除。

**本輪驗收界線**：只讀定位與分類建議，所有數字與候選僅在上述 SHA、搜尋條件下成立；主線 G-2、PR #1150/#1151 不受影響。
