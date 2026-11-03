# 80｜New UI2 Architecture Proposal（~~提案；⛔ 待客戶裁示~~ → 已裁示並凍結：`DEC-2026-11-02-05`）

- **2026-11-02 裁示狀態（`DEC-2026-11-02-05`；決策者：客戶；狀態更新，不是漏刪）**：客戶 2026-11-02 裁示 NG-1～NG-5 全部採 A（逐字見 `docs/evidence/decisions/2026-11-02_new_ui2_ng_and_final_ui_contract_ruling.md`）。**已裁示並凍結**：本檔的 architecture（第 1、2 節）、Reuse Matrix（第 3 節）、migration boundary（第 8 節）凍結；**五頁 wireframe（第 7 節）為正式 implementation input**，各頁最終呈現依 NG-5／UI-12 由 New UI2 各頁 wireframe 重新核准。正式 Streamlit 顯示規則與 cutover 約束另見 `DEC-2026-11-02-06`（第 10 節）；Final UI Contract 的 UI-1～UI-15 裁示見 `DEC-2026-11-02-07`（`docs/v2/79`）。下方「定位」各句保留原字作歷史；凡寫「提案／待客戶裁示／不生效」者，自本日起讀作「已裁示並凍結（`DEC-2026-11-02-05`）」。正式條文住址仍依下方落盤策略（DECISIONS／BACKLOG／HANDOFF），本檔不升格為第二套規格。**仍不授權**：`ui_v3` production 實作須待 Model／Mode／Effort Change Gate 由客戶回覆「已切換／可以開始」（`DEC-2026-11-02-04`）；不改 Old UI、不刪 ui_v2、不改 44。
- **`<pkg>` 全域對照（2026-11-02，NG-1 A）**：本檔所有 `<pkg>` 一律讀作 **`ui_v3/`**（New UI2＝`ui_v3/`）。為減少改動，正文保留 `<pkg>` 佔位符，不逐處替換；本行即為單點對照宣告。
- **定位**：**Architecture Proposal／Decision Gate／Migration Contract。不是規格、不是第二套 UI 憲法、不是動工授權。** 本檔把客戶 2026-11-02 已裁示的 New UI2 架構方向（`DEC-2026-11-02-03`）展開成可一次裁示的提案：目標分層、Reuse Matrix、目錄結構、Design Contract、View Model Contract、五頁文字線框、遷移邊界、測試策略、Cutover，以及少量 Decision Gate（NG-1～NG-5；前端框架改列內部決定，見第 12 節附註）。本檔寫下的任何「提案」在客戶裁示前不生效。
- **已裁示、本檔不重問的方向**（逐字見 `docs/evidence/decisions/2026-11-02_new_ui2_architecture_direction.md`）：New UI2＝Greenfield Presentation Layer、不是重寫系統；Old UI＝read-only logic reference；ui_v2＝Legacy New UI／Reuse Candidate、不先刪；New UI2＝唯一未來正式 presentation layer；五頁 IA 不變、不得新增第六頁；Cutover 預設順序。**仍待裁示**（本檔 NG-1～NG-5）：目錄命名、ui_v2 freeze policy、preview／cutover、視覺語言沿用範圍、presentation DEC 釋放規則；前端框架屬內部決定（維持 Streamlit 現況），不列客戶 Gate。（→ **2026-11-02 已裁示**：NG-1～NG-5 全部採 A；客戶並確認 Streamlit 維持現行內部決定、不更換 framework（`DEC-2026-11-02-05`；狀態更新，不是漏刪））
- **位階**：不凌駕 `CLAUDE.md`、`PROJECT_RULES.md`、`docs/v2/44_fund_ui_ssot.md`（frozen）、`docs/v2/67_ai_action_vocabulary.md`、`docs/v2/75_onebrain_ai_architecture.md`、`docs/v2/79_final_ui_contract_freeze.md`（語意部分）與 `docs/DECISIONS.md` 的正式裁示；衝突一律以它們為準，視為本檔寫錯。
- **客戶核准後的落盤策略**（`PROJECT_RULES.md` 13.4 第 7 條：文件不重複 SSOT）：裁示登記 `docs/DECISIONS.md`；工作項掛 `docs/BACKLOG.md`（優先掛 BL-0533 子項，不碎片化）；接手點進 `docs/HANDOFF.md`；必要時列 44 amendment backlog（不在本批解凍 44）。本檔核准後只保留 rationale 與 migration map，不再作為條文引用來源。
- **量測基準**：origin/main `fade6046`＋PR #1119（`DEC-2026-11-02-03` 待合併）。本組重驗在本機分支 `d89b1fbc` 上進行；`git diff --stat fade6046 d89b1fbc -- ui_v2 services shared repositories infra tests` → 無輸出，故程式事實等同 `fade6046`；撰寫期間 #1119 分支新增 docs commit `82678c87`，同一指令改比 `82678c87` 亦無輸出。程式位置寫「檔案::符號」，不寫行號。
- **BACKLOG 追蹤**：BL-0533（本提案＋Gates）；相關：BL-0531（UI-1～UI-15）、BL-0532（Missing 統一）、BL-0525（呈現遷移批）。
- **現況的來源（據實揭露）**：第 3、8、9、14 節的現況大多來自三組**單組唯讀盤點**（下層組、ui_v2 組、SSOT 組），由總管轉述，**未經第二組複驗**；本組能快速重驗的承重事實已重驗並標【F-重驗】，其餘標【F-轉述】（＝轉述自盤點組）。重驗清單見第 15 節。
- **建立日**：2026-11-02。**編號**：79 為 Final UI Contract，本檔取 80。
- **產出者聲明**：文件組單組產出，未經獨立複驗（`CLAUDE.md` §-2 規則 6）。本檔涉及 formula／data semantics 搬遷（PORT）與治理規則，依 `DEC-2026-10-16-05`，正式回寫前至少要 1 組真正獨立稽核。

## 0. 標記法

| 記法 | 意思 |
|---|---|
| 【F-重驗】 | 本組這一輪自己讀檔或搜尋重驗過（第 15 節） |
| 【F-轉述】 | 轉述自盤點組（單組），本組未重驗 |
| 【I】 | 推論，可推翻 |
| 【P】 | 提案，待客戶裁示 |
| `<pkg>` | New UI2 套件目錄名的佔位符；~~實際名稱待 NG-1~~ → **＝`ui_v3/`**（NG-1 A，`DEC-2026-11-02-05`；狀態更新，不是漏刪） |
| 符號 | 只用 44 已落字的 ◆ ◇ ⬜ ⛔ ◷；本檔不新增狀態詞或符號 |

---

## 1. 目標與非目標【P；方向依 `DEC-2026-11-02-03`】

| 是 | 不是 |
|---|---|
| 一個新的 **presentation layer**：五頁（🌍／💼／🔍／🤖／⚙️）的頁面、元件、設計語言、view model、導覽 | 新資料系統、新 source layer（不新增 provider、不改取數鏈） |
| 讀取既有已驗證的 data／services／deterministic logic／provenance／health 的「消費者」 | 新 business rule engine（不新增規則、不改門檻值） |
| mobile-first（390px 首屏先設計）、五頁一致 | 新 AI engine（OneBrain 不在本範圍；只預留接口） |
| 以 79 語意規格與既有語意 DEC 作為 **input contract** | 新 portfolio engine（不新增彙總公式、不改 β 階梯語意） |
| 第一階段唯讀（同 44 之十六、`settings_sheet_repository.is_read_only()`） | 第六個主要頁面；任何寫入功能 |

**三條硬規則【P；依據既有條文】**：
1. **New UI2 不創造 objective facts**：畫面上每個值、狀態、日期都來自下層（canonical data、domain calculation、正式 rule result），不在 presentation 層推估、補值或合成（`CLAUDE.md` §1；67 第 5.4 節）。
2. **AI 不寫回 data**：OneBrain 只讀 Decision Digest，不回寫 canonical data（67 第 6 節第 5 點；`PROJECT_RULES.md` 13.1）。
3. **Streamlit 不承擔 domain calculation**：報酬、回撤、偏離、配置彙總、三態篩選等計算住在 domain 層（第 3 節 PORT），Streamlit 頁只渲染 view model。

---

## 2. 目標分層【P】

```text
L0  Data／External Sources（FRED、Yahoo、MoneyDJ、Google Sheets …；既有，不動）
      │
L1  Normalization／Validation        repositories/＋services/v2_tables/（KEEP；寫入守衛照舊）
      │
L2  Domain／Deterministic Logic      services/（含 PORT 進來的 ui_v2 領域計算，落點例：services/v2_domain/）
      │                               ── 未來接口（只預留，不實作）：
      │                                  Deterministic Rules → Risk Cap → System Action State
      │                                  → Decision Digest → OneBrain
      │
L3a View Model／Presentation Contract  <pkg>/viewmodels/（純 Python、無 streamlit、無 I/O、可單元測試）
      │                               ← 只經 <pkg>/adapters/ 取下層結果
      │
L3b New UI2 pages／components         <pkg>/pages/、<pkg>/shell/、<pkg>/design/（Streamlit；只渲染 view model）
```

| 層 | 可以做 | 不可以做 |
|---|---|---|
| adapters | 呼叫 `services.v2_tables.*` 與 `services/v2_domain`；注入 session state；遮蔽失敗原文 | 計算領域值；決定狀態語意；網路呼叫（經下層才可） |
| viewmodels | 把下層結果組成元件級 schema（第 6 節）；套用呈現規則資料表（狀態→符號、Missing 字樣） | import streamlit；讀 secrets；補值；從 UI 狀態反推事實 |
| pages／components | 版面、互動、導覽；把 view model 畫出來 | 任何計算或判定；直接 import 下層 |
| 未來 Digest／Risk Cap／Action State／OneBrain | 位置預留在 L2 之後、L3a 之前；L3a 只讀其產出 | **本提案不實作**；禁止 fake Risk Cap、fake action state、fake AI probability、fake Digest |

**未來接口的佔位規則【P】**：view model 預留 `ActionSlot`（第 6 節）與 🤖 頁的 Digest 讀取點；在對應 Gate 通過前，`ActionSlot` 恆為「⬜ 無法判定」或不顯示，🤖 頁不掛導覽（`DEC-2026-10-29-07`）。

---

## 3. Reuse Matrix

分類：**KEEP AS-IS**（原樣 import）／**WRAP**（經 adapter 或去掉 presentation 假設後使用）／**PORT**（行為不變搬遷到共同層，測試隨行）／**REIMPLEMENT**（New UI2 重新寫）／**RETIRE LATER**（cutover 後再評估清理）／**DO NOT TOUCH**（Old UI）。

### 3.1 下層（services／repositories／shared／infra）

| 模組 | 分類 | 證據 | New UI2 用法 | 風險 |
|---|---|---|---|---|
| `services/v2_tables/contract`、`masking`、`market_indicator`、`nav_dividend`、`alo_holdings`、`personal_session`、`fund_keys`、`exp_universe`、`exp_profile`、`exp_nav` | KEEP AS-IS | 不 import streamlit／`ui_v2`／`ui`【F-重驗：檔內無 streamlit import，僅 docstring 提及】 | adapters 直接呼叫 | 部分回傳帶中文 reason 文字；New UI2 以 `reason_code`／`WITHHELD_*`／`STATUS_*` 為鍵，字樣由 view model 規則表決定 |
| `services/v2_tables/market_view` | KEEP AS-IS | `_domain` dict 帶 domain／status／reason_code／reason／source／fetched_at／obs_date／value_unit／points【F-轉述】；`STATE_MISSING`＝「資料未備」【F-重驗】 | 最貼近 view model 的來源 | 中文狀態字面屬 presentation 假設；view model 以 status 鍵映射 |
| `services/v2_tables/settings_store` | WRAP | `PAGES_READING_SETTINGS`＝`("set", "alo", "hld", "mkt", "exp")`【F-重驗】；`RUNTIME_STATE_KEY`＝`_v2_refetch_runtime`【F-重驗】 | adapter 把 New UI2 頁代號對到既有頁常數（不改下層） | 頁代號是 ui_v2 頁形狀；New UI2 若合併 alo／hld 為 💼，需對照表 |
| `repositories/settings_sheet_repository::is_read_only` | KEEP AS-IS | 第一階段恆為 True【F-重驗】 | 寫入面沿用 | — |
| `shared/ui_v2_error_codes` | KEEP AS-IS | 九個 error code（`AUTH_REQUIRED` … `UNAVAILABLE`）＋`ALL_ERROR_CODES`【F-重驗】 | view model 錯誤分類鍵 | 檔名含 `ui_v2`，屬 L0 常數；不改名（改名會動 ui_v2） |
| `repositories/v2_source_status`（冷卻） | KEEP AS-IS | 【F-轉述】 | 經 v2_tables 間接使用 | — |
| `infra/personal_oauth`＋`services/v2_tables/personal_session` | KEEP AS-IS | PKCE；session namespace `b_oauth.`【F-重驗：兩檔註解】 | 登入流程沿用 | 另一網址需在 Google 端另登記 redirect（第 10 節） |
| `services/dividend_calendar` 計算核心（`infer_schedule`、`predict_ex_for_month`、`detect_anchor`、`estimate_error_band`） | KEEP AS-IS（capability） | 只 import 標準函式庫、無 I/O【F-重驗：模組 import 清單】；但 `predict_ex_for_month` 經 `_tw_holidays` 讀選配的 `holidays` 套件（缺套件時只跳週末），輸出依執行環境而異【F-重驗：`_tw_holidays` 與 `_HOLIDAY_CAL_WEEKEND`】 | 💼 配息事件（UI-15 未裁前為 proposal） | `confidence` 不得外露為機率（79 §17.6） |
| `services/dividend_calendar::build_summary_text`、`build_summary_flex`、`ERR_BAND_FOOTNOTE` | 不重用（LINE presentation） | 【F-重驗：符號存在】 | 不用 | — |
| `services/dividend_calendar_render` | 不重用 | HTML 產生器（presentation 住在 services）【F-轉述】 | 不用；New UI2 依 design system 重做 | — |
| `infra/line_push`、`.github/workflows/dividend_calendar_notify.yml`（cron `23 0 28 * *`【F-重驗】）、`scripts/dividend_calendar_notify.py` | infrastructure，New UI2 不碰 | `tests/test_line_push_decoupled_from_ui.py` 鎖與 UI 解耦【F-重驗：檔存在】 | ⚙️ 只做唯讀 delivery health（UI-15） | 該 workflow 以 secrets `GOOGLE_SERVICE_ACCOUNT`（服務帳戶）與 `POLICY_SHEET_ID` 讀表、不是個人 Active Sheet【F-重驗：workflow env 段】 |
| `repositories/macro/yf.py`、`repositories/macro/fred.py` | KEEP AS-IS | 從根目錄 `fund_fetcher` import `_ttl_cache`【F-重驗】 | 經 v2_tables 間接 | 閉包拖入舊 services（體積）；不屬 New UI2 範圍，只登記 |
| `repositories/pool_repository::_cached_pool_map` | KEEP AS-IS | try-import `st.cache_data`（EX-CACHE-1）【F-重驗】 | 間接 | 同 process 共用快取 |
| 下層既有測試（v2_tables 各模組、golden、dividend_calendar、line_push、source_backoff、`tests/test_services_purity_contract.py`） | KEEP AS-IS | 【F-轉述；purity 測試檔存在 F-重驗】 | 不重寫 | — |
| Old UI（`app.py`、`ui/`、舊 services 的 presentation） | **DO NOT TOUCH** | `DEC-2026-11-02-02` 第 (1)～(4) 點 | 只作 logic reference | 切 default 若需改 `app.py` 即撞此邊界（第 10 節） |

### 3.2 ui_v2

| 模組 | 分類 | 證據 | New UI2 用法 | 風險 |
|---|---|---|---|---|
| `ui_v2/hld/logic.py::return_pct`、`drawdown_pct`、`vol_pct`、`deviation_rows`、`merge_same_key_holdings` | **PORT** | 符號存在【F-重驗】；領域計算住在 L3【F-轉述】 | 搬到共同 domain 層後 import | formula／data semantics 高風險；模組 import `page_health`、`status_class`【F-重驗】，搬遷須切斷 L3 依賴 |
| `ui_v2/alo/logic.py::aggregated_holdings`、`basis_value`、`category_of`、`exceeds`、`target_sum` | **PORT** | 同上【F-重驗】 | 同上 | 同上 |
| `ui_v2/exp/logic.py::apply_rules_tristate`、`compare_tristate` | **PORT** | 同上【F-重驗】 | 同上 | 三態語意（不得把未知當不符合） |
| `ui_v2/mkt/chart.py::slice_period`；`ui_v2/mkt/logic.py::delay_days` | **PORT** | 同上【F-重驗】 | 同上 | 期間切片＝display control，但切片邊界屬資料語意 |
| `ui_v2/thresholds.py::NAV_NOT_READY_DAYS`（＝10，客戶裁示的 domain 規則） | **PORT**（見 3.3 (b)） | 定義只在此檔【F-重驗】；`ui_v2/alo/source.py`、各頁 `live.py`／`logic.py` 引用【F-重驗】 | 改從 shared 常數讀 | domain 規則住在 UI 層 |
| `ui_v2/status_class.py`（β 階梯七類） | KEEP（語意）／隨 PORT 下沉 | 【F-轉述】；不 import streamlit【F-重驗：只在 docstring 出現】 | view model 狀態分類 | 被 logic 依賴；放 shared 或 v2_domain 待內部決定 |
| `ui_v2/page_health.py`（`KIND_UNCONFIGURED`／`KIND_FETCH`／`KIND_MISSING`／`KIND_STALE`、main_reason） | KEEP（分類部分） | `KIND_*` 存在【F-重驗】 | 頁級狀態分類鍵 | 混有中文字面（KIND 值即字樣）；以鍵用、字樣另表 |
| `ui_v2/readonly.py`（`WRITE_CONTROLS_ENABLED`＝False） | KEEP（常數） | 【F-重驗】 | New UI2 同型旗標 | — |
| `ui_v2/presentation.py`（chip／chart_card／detail／missing 四種模型） | WRAP（去掉 `*_html`） | 函式存在；`from ui_v2 import health`【F-重驗】 | 模型形狀參考 | 依賴 `ui_v2.health`（分層例外 E4） |
| `ui_v2/plain.py`、`symbols.py`、`sections.py`、`health.py`、`health_view.py`（純部分） | WRAP → 以「規則資料表＋純函式」移入共同層（3.3 (c)） | 純函式、無 streamlit【F-重驗：plain／symbols／health docstring】；耦合 block dict 形狀與客戶裁示中文字面【F-轉述】 | 判定規則與字樣表重用，不複製 block dict | 字面契約鎖測試（B 類）在 ui_v2 |
| `ui_v2/mkt/chart.py::build_spec`（vega-lite 純 dict） | KEEP | 【F-重驗：符號存在】 | 圖表 spec 起點 | 尺寸與配色常數屬 ui_v2 設計 |
| 各頁 `live.py`／`source.py`、`mkt/market_section`、`mkt/overview`、`asset/overview`、`asset/page_status` | WRAP | 【F-轉述】 | 取其組裝邏輯為 adapter 參考 | `source.py` 混 session／secrets 邏輯（E3） |
| `ui_v2/active_gate.py` 純邏輯、各頁 `theme.py::contrast_ratio`、`mkt/page.py::mark_fetch_failures` 等 page.py 內純函式 | PORT | `contrast_ratio` 在 alo／hld／set／exp 四份 `theme.py` 各有一份【F-重驗】；`mark_fetch_failures` 存在【F-重驗】 | 收成一份 | 重複（鏡像） |
| 各頁 `page.py`（含 `hld/page.py::prepare_live` 後處理管線）、`presentation_view`、`shell`、`shell_nav`、CSS、各頁 theme 色碼、`mkt/chart.py::sparkline_svg` | **REIMPLEMENT** | `prepare_live` 存在【F-重驗】；管線就地改寫 block dict、碰 session【F-轉述】 | 不 import | 若 import 等於把 Streamlit 版面假設帶進 New UI2 |
| `ui_v2/app_*_live.py`、`ui_v2/app_preview.py` 與 production 掛載 | RETIRE LATER | `app_preview.py::PAGES` 四列 mkt／ast／exp／set【F-重驗】 | 不用 | 清理需另走刪除 Gate（第 10 節） |
| `ui_v2/*/fixtures`、`ui_v2/set/spec` | KEEP（測試資料） | 【F-轉述】 | fake scenario 參考 | 形狀是 ui_v2 block |
| `tests/ui_v2/`（110 個 `.py`，`fade6046`）【F-重驗】 | 依類分流（第 9 節） | A 類領域語意／B 類字面鎖／C 類 AST 守衛／D 類 source 與寫入／E 類畫面【F-轉述】 | A 隨 PORT 搬；B 轉 view-model 規則測試；C 泛化 | — |

**分層例外（轉述自盤點組 E1～E8，依列序編號）**：E1 page.py 混純邏輯、E2 管線在 page.py、E3 source.py 混 session／secrets、E4 presentation.py 依賴 ui_v2.health、E5 asset/page.py 頁對頁耦合、E6 領域計算在 logic、E7 active_gate／health_view 混檔、E8 set/logic 不一致【F-轉述】。頁間鏡像重複：`_grid_css`（mkt／hld／alo／exp／set 各一份）、`DISPLAY_TZ`（alo／mkt／set 各一份）、`NAV_NOT_READY_TEXT`（alo／hld 各一份）【F-重驗】。

**結論【I】**：ui_v2 的 block dict 內建 Streamlit 版面假設（`_viewport_width`、`_layer`、`_default_open`、`_columns`、inputs／buttons）、文案與資料混在一起、語意靠 `_` 前綴約定【F-轉述】，**不建議直接升級為 New UI2 presentation contract**；可重用的是「判定語意」與「規則表」，不是 block dict。

### 3.3 特別段

**(a) 領域計算 PORT 方案比較【P】**

| 方案 | 做法 | 優點 | 風險 |
|---|---|---|---|
| a1 複製 | 把 logic 函式複製到 New UI2 | ui_v2 一行不動 | **兩份同一公式**，日後必然漂移；違反 SSOT（`CLAUDE.md` §2.1）—— **不推薦；僅作 NG-2＝B 時的退路** |
| **a2 搬到共同層＋ui_v2 留 re-export shim**（推薦） | 函式搬到 `services/v2_domain/`（名稱為提案），ui_v2 原位置改為 re-export；A 類測試指向新住址，golden 不變 | 一份公式、兩代 UI 共用；ui_v2 行為不變 | 需 NG-2 允許「行為不變的抽取」；**現行 `tests/ui_v2/test_ui_v2_live_import_guard.py` 規則 (5) 禁止 ui_v2 檔 import 舊樹模組（`services` 只准 `source.py` 經規則 (2) 逐模組 import）**【F-重驗：檔頭規則】，故 shim 需在該守衛加一條逐檔白名單（shim 檔只准 import `services.v2_domain.*`），屬 ui_v2 測試變更；被搬函式目前 import `page_health`／`status_class`，須先切斷 L3 依賴 |
| a3 New UI2 直接 import ui_v2 logic | 不搬 | 零搬遷成本 | New UI2 永久耦合 legacy；ui_v2 日後清理時被卡住；L3 依賴 L3 |

**推薦 a2**，列入 NG-2（A 選項包含「行為不變的抽取＋re-export shim」）。a1 不推薦；僅在 NG-2 選 B（hard freeze）時作為退路，採「a1 複製＋等價測試鎖一致」，並在 BACKLOG 登記「ui_v2 清理時收回重複」。

**(b) `NAV_NOT_READY_DAYS` 落點【P】**：搬到 `shared/` 下一個 domain 常數模組（名稱內部決定），值 10 不變；`ui_v2/thresholds.py` 改 re-export（同 a2 的守衛白名單）。理由：它是客戶裁示的 domain 規則（淨值不可用天數），不是 UI 參數；放 shared 讓 New UI2、ui_v2、日後 Digest 讀同一個值。

**(c) 呈現規則的移法【P】**：plain／symbols／sections／health 內客戶裁示的字樣與判定，抽成「**規則資料表**（狀態鍵 → 符號、字樣、tone）＋**純函式**（判定）」放共同層（例：`shared/` 下 presentation-semantic 常數），New UI2 view model 與 ui_v2 皆讀同一表；**不複製貼上**、**不搬 block dict**。字樣衝突（例：`NAV_NOT_READY_TEXT` 用「⬜ 資料未備」【F-重驗】、`ui_v2/mkt/chart.py::TEXT_EMPTY` 用「⬜ 資料未取得」【F-轉述自 79 §11】）依 BL-0532 射程處理：只限正式模式的「⬜ 資料未備」統一為 `◇ 資料未備`；`TEXT_EMPTY` 的「⬜ 資料未取得」屬版面示意字樣，實作批逐一判讀；示範模式依 44 照舊、另議；不得全域取代。在 ui_v2 端是否也統一，見 NG-2 附題。

**(d) settings_store 頁面常數 adapter【P】**：不改 `PAGES_READING_SETTINGS`；New UI2 的 💼 adapter 把「我的資產」對到既有 `alo`＋`hld` 兩個代號讀設定。下層頁常數的泛化（改成與頁無關的設定鍵）列為後續可選，不在第一批。

**(e) dividend_calendar【P】**：計算核心 KEEP；`dividend_calendar_render` 與 LINE 專用 presentation（`build_summary_*`、`ERR_BAND_FOOTNOTE`）不重用；New UI2 的配息呈現依 79 §17.3～17.4 的 date contract 與本檔 design system 重做（UI-15 裁示後）。

---

## 4. 目錄結構提案（~~命名待 NG-1~~ → 命名已裁示：`ui_v3/`，NG-1 A，`DEC-2026-11-02-05`；狀態更新，不是漏刪）

### 4.1 命名選項【P】

| 選項 | cutover 後要改名嗎 | 與 ui_v2 混淆風險 | import 路徑穩定 | 判斷 |
|---|---|---|---|---|
| **A `ui_v3/`**（推薦） | 不必 | 中低：數字不同，`ui_v2` 的搜尋不會命中 `ui_v3`；但產品名「New UI2」與目錄名「v3」不一致，須在 SSOT 登記對照一次 | 穩定 | 世代編號一致（Old＝`ui`、New UI＝`ui_v2`、New UI2＝`ui_v3`） |
| B `ui_next/` | 「next」在 cutover 後變成「current」，名不符實；改名＝全 import 改寫 | 低 | 改名時不穩 | 適合臨時分支，不適合唯一正式層 |
| C `ui2/` | 不必 | **高**：口語「UI2」與「ui_v2」極易互指，PR 描述、派工單、grep 都會混 | 穩定 | 名稱與產品名一致，但混淆成本最高 |

**推薦 A**：唯一正式層需要一個 cutover 後不必改的名字；世代編號可自我說明；名不一致只需一行對照（「New UI2＝`ui_v3/`」），而 C 的混淆在每一次溝通都要付。

→ **2026-11-02 裁示：採 A（`ui_v3/`）**；SSOT 對照「New UI2＝`ui_v3/`」依落盤策略登記於 `docs/DECISIONS.md`（`DEC-2026-11-02-05`）。

### 4.2 內部結構示例【P；名稱屬內部決定】

```text
<pkg>/
  app_preview.py          獨立 preview 入口（Streamlit main file）；不 import ui_v2
  shell/                  導覽（底部五項／側欄）、頁框、登入卡位置
  design/                 tokens 命名與元件契約（第 5 節）；不放業務字樣
  viewmodels/<page>.py    純 Python：下層結果 → 元件級 schema（第 6 節）
  pages/<page>.py         Streamlit render：只吃 view model
  adapters/<page>_source.py  唯一可 import services.v2_tables／services.v2_domain 的位置
  fixtures/               fake／scenario 資料（第 9 節情境清單）；正式路徑不得 import
services/v2_domain/       PORT 進來的領域計算（行為不變；名稱為提案）
shared/<presentation-semantic 常數模組>  狀態類別、Missing 字樣 token、NAV_NOT_READY_DAYS（名稱為提案）
```

頁代號建議沿用 IA 意義：`mkt`／`ast`／`exp`／`ai`／`set`（`ai` 在 Phase 7 前無 render 掛載）【P】。

---

## 5. Design Contract（規則與 token 命名；不寫 CSS）【P】

| 面向 | 規則 | token 命名（建議尺度，屬提案） |
|---|---|---|
| spacing | 4px 基數；元件內距與區塊間距分開命名；390px 左右 gutter 固定 | `space.1`＝4、`space.2`＝8、`space.3`＝12、`space.4`＝16、`space.6`＝24、`space.8`＝32；`gutter.mobile`＝16 |
| typography | 五級：頁標題／區塊標題／主數字／內文／輔助；主數字不靠字重單獨表意；390px 不縮內文以塞內容 | `type.page`、`type.section`、`type.metric`、`type.body`、`type.caption`（建議 22／17／20／15／12） |
| card system | 三種卡：摘要卡（≤5，`DEC-2026-10-27-26`）、圖卡（核心圖 ≤4）、明細容器（收合）；Block ID ≠ Container（`DEC-2026-10-30-02`） | `card.summary`、`card.chart`、`card.detail`；`radius.card`、`elevation.none` |
| status chips | **文字＋符號**，顏色只是第三重；只用 ◆ ◇ ⬜ ⛔ ◷；顏色只映射資料狀態與新鮮度、不映射投資好壞（44 第一節） | `chip.attention`（◆）、`chip.missing`（◇）、`chip.undetermined`（⬜）、`chip.failed`（⛔）、`chip.stale`（◷）、`chip.neutral` |
| source／freshness display | 逐欄 as_of，不以頁級時間代替；source 可收進「▸」；門檻未裁示時只顯示天數與「⬜ 門檻待裁示」 | `meta.asof`、`meta.source`、`meta.freshness` |
| chart container | 標題＋≤3 chips＋圖＋「▸」detail（44 之十九圖卡模板）；缺段斷線不補、不畫零；不畫目標價線與方向箭頭；非顏色辨識至少一種；期間 3M／6M／1Y／3Y、預設 1Y（`DEC-2026-10-27-31`） | `chart.height.primary`、`chart.height.secondary`、`chart.period` |
| empty／error／loading | 四空狀態沿用 44（未設定／資料未備／取數失敗／無資料）；Missing 恆為 `◇ 資料未備`；loading 不得顯示假值或骨架數字 | `state.empty.*`、`state.loading` |
| CTA hierarchy | 每頁至多 1 個主 CTA；第一階段唯讀，CTA 只能是導覽、展開、查詢、加入 session 比較，不得是寫入或交易語意 | `cta.primary`、`cta.secondary`、`cta.link` |
| mobile navigation | 底部五項導覽；🤖 Phase 7 前不掛（只四項可見）；≤2 次互動到達任何區（`DEC-2026-10-27-11`） | `nav.bottom`、`nav.item` |

**視覺語言沿用範圍**：見 NG-4（推薦沿用狀態符號、語意色名、字樣規範；版面、元件、spacing、typography 重建）。

---

## 6. View Model Contract（元件級 schema）【P】

**共同欄位**（凡帶值的元件皆有；沒有就填 Missing 狀態，不填假值）：

| 欄位 | 意思 | 來源 |
|---|---|---|
| `value` | 原值（數字或 None；不是格式化字串） | canonical／domain |
| `unit` | 單位 | 下層 `value_unit`／`ccy` |
| `source` | 具體來源名 | 下層 `source`／`provenance.source` |
| `as_of` | 觀測日 | `obs_date`／`nav_date` 等 |
| `retrieved_at` | 取得時間 | `fetched_at` |
| `freshness_state` | 新鮮度狀態；門檻未裁示＝`undetermined` | 只讀下層或正式規則的結果（view model 不自行判新鮮度） |
| `status` | 資料狀態鍵（ok／missing／failed／stale／undetermined） | 下層 status／reason_code |
| `reason_code` | 下層原因鍵 | `reason_code`／`WITHHELD_*`／error code |

| 元件 | 額外欄位 | 規則 |
|---|---|---|
| `StatusChip` | `kind`、`label_key` | 字樣由規則表依 `kind` 給；不接受自由文字狀態 |
| `MetricCard` | `title`、`display_value`（由 view model 格式化）、`delta`（可無） | `value` 為 None → `◇ 資料未備`，不顯示 0 |
| `ChartCard` | `series[]`（各自帶共同欄位）、`period`、`chips[]`（≤3）、`detail` | 缺段斷線；不補線；series ≤3 |
| `EvidenceItem` | `label`、`rule_ref`（只有正式規則存在才填） | 不得自造 Rule ID |
| `MissingItem` | `what`、`reason_code` | presentation 恆為 `◇ 資料未備`＋原因 |
| `ProvenanceTag` | `source`、`as_of`、`fallback_used` | 可收合 |
| `ActionSlot` | `state`、`reason`、`source_ref` | **Phase 7 前恆為「⬜ 無法判定」或不顯示；來源只能是 System Action State**（79 §6.1）；不得由 view model 推出 |

**禁止**：Missing 補 0、neutral、HOLD、safe；從 UI 狀態（顏色、收合、位置）反推事實；把 `display_value` 當 Digest 值來源（67 第 5.2 節第 3 點）。

---

## 7. 五頁文字線框（390px 先、再 desktop）【~~P；版面待各頁 New UI2 wireframe 核准~~ → 正式 implementation input（`DEC-2026-11-02-05`）；各頁最終呈現仍由 New UI2 各頁 wireframe 重新核准（NG-5／UI-12）；狀態更新，不是漏刪】

> **2026-11-02 狀態**：本節五頁線框自本日起為 New UI2 的**正式 implementation input**（起點），不是最終版面核准；各頁進入實作前仍依第 10 節階段 3 先出精確 wireframe 送客戶（§-1.5.4）。線框內 `[Gate]`／`[提]` 原字保留，已裁示部分見各頁表格末列。

> 標記：`[語]`＝語意來自既有 input contract（括號註明）；`[提]`＝本檔提案版面；`[Gate]`＝需裁示。數值用 `‹值›`。首屏回答四件事：現在狀態／是否需要關注（◆，不是行動建議）／下一步／主 CTA。

### 7.1 🌍 市場與趨勢

```text
390px                                   desktop 1280
┌──────────────────────┐   ┌───────────────────────────────────────┐
│[語] 狀態 chip ‹n›    │   │[語] 狀態 chip｜暫無完整市場綜合判定     │
│[語] 暫無完整市場綜合 │   │[提] ◆ 需要注意 ‹n› 項（規則判出）     │
│     判定（缺正式…）  │   ├───────────────────────┬───────────────┤
│[提] ◆ 需要注意 ‹n›   │   │[語] Primary（D1 單序列 │[提] 重要證據  │
│[語] Primary 1Y       │   │ 切換；[Gate] 比較圖）  │ ≤3（D7 順序） │
│ [3M 6M 1Y 3Y]        │   │ 資料日‹日›｜來源‹›    │               │
│ 資料日‹日›           │   ├───────────────────────┴───────────────┤
├──────────────────────┤   │[語] Secondary ≤3（VIX／S&P／利率信用）│
│[語] Secondary 緊湊列 │   ├───────────────────────────────────────┤
│[提] ▸ 重要證據       │   │[語] ▸ Missing／新鮮度／來源（下沉）   │
│[語] ▸ Missing…       │   └───────────────────────────────────────┘
└──────────────────────┘
主 CTA：切換 Primary 序列（display control，不是判定）
```

| 項 | 內容與 input contract |
|---|---|
| Market state | 依 79 §5 regime 原則：aggregation rule 裁示前固定「暫無完整市場綜合判定（缺正式 aggregation rule）」（`DEC-2026-10-27-41`）`[語]` |
| 是否需關注 | 字樣對齊既有「◆ 需要注意」；◆ 只來自正式規則判出的注意事項，不是行動建議；取數失敗（⛔）與不是最新（◷）是資料狀態、另用各自符號，不計入 ◆；正式規則未存在時此列不顯示 `[提]` |
| Primary | 現行語意＝`DEC-2026-10-30-01` D1 單序列切換；**改比較圖＝D1 amendment**（NG-5 明列、79 UI-12(1)）`[Gate]`（→ **2026-11-02 已裁示**：客戶同意 amend D1 —— New UI2 🌍 Primary 方向＝**TAIEX vs S&P 500 比較圖**，歸一化基準 100（UI-13 A）；**最終呈現由 New UI2 🌍 頁 wireframe 重新核准**；「國際｜S&P 500」Secondary 卡去留併入同一張 wireframe（客戶未單獨表態；總管讀法，可被客戶推翻）；依據卡 ≤3（UI-12 (3) A）（`DEC-2026-11-02-07`；有意識的政策變更，不是漏刪；決策者：客戶）） |
| Missing／stale／failure | 斷線＋`◇ 資料未備`；取數失敗 `⛔`；新鮮度門檻未裁示時不判 stale |

### 7.2 💼 我的資產

```text
390px                                   desktop 1280
┌──────────────────────┐   ┌───────────────────────────────────────┐
│[語] 頁級狀態（β 階梯）│   │[語] 頁級狀態：‹頭條›／‹第二行›         │
│[語] 摘要 2×2         │   │[語] 摘要 ×4（缺→◇ 資料未備）          │
│ 總資產｜損益｜報酬｜配息│ ├───────────────────────┬───────────────┤
│[語] 配置 現況 vs 目標 │   │[語] 配置 現況 vs 目標  │[提] 近期事件  │
│ 偏離 ‹n› 類（事實）  │   │ [Gate] 容許帶標示      │ 配息（UI-15） │
├──────────────────────┤   ├───────────────────────┴───────────────┤
│[提] 近期事件（UI-15）│   │[語] 基金占比｜各檔區間報酬（全列）     │
│[語] ▸ 持股明細       │   ├───────────────────────────────────────┤
│[提] ▸ 配息行事曆     │   │[語] ▸ 持股／配置明細／Missing          │
└──────────────────────┘   └───────────────────────────────────────┘
主 CTA：查看偏離明細（展開，不是再平衡動作）
```

| 項 | 內容與 input contract |
|---|---|
| 資產現況 | 摘要四項不得因 Missing 從第一屏消失；不新增彙總公式；禁 Top N（`DEC-2026-10-30-02`）`[語]` |
| 頁級狀態 | β 階梯語意與 H6 保留（`DEC-2026-10-30-04`）；位置重設計 `[語]`＋`[提]` |
| allocation／deviation | 偏離是使用者門檻比較的事實，不產生再平衡動作（44 之十八其十一第 3 條）`[語]` |
| 近期事件／配息 | UI-15 未裁前為 proposal；date status 四態僅為 data 層候選（79 §17.4）`[提]`（→ **2026-11-02 UI-15 A**：💼 擁有 Dividend Calendar；正式日期優先、deterministic estimate 只作 fallback；Old UI calendar 只參考 logic／capability、不搬 UI；`pay_date` 在 44 amendment（BL-0534）完成前不得標成銀行／平台實際入帳日（79 §17.12）；`DEC-2026-11-02-07`；狀態更新，不是漏刪） |
| 是否需處理 | 只顯示 ◆ 規則事實；行動恆無（`ActionSlot` 不顯示） |
| 容許帶 | `[Gate]` 容許帶標示（→ **2026-11-02 已裁示**：UI-12 (4) A 核准，出處＝使用者設定、端點歸屬仍未定；`DEC-2026-11-02-07`） |

### 7.3 🔍 找基金

```text
390px                                   desktop 1280
┌──────────────────────┐   ┌───────────────────────────────────────┐
│ 查一檔基金           │   │ 查一檔基金                            │
│ [MoneyDJ 代碼或 ISIN]│   │ [MoneyDJ 基金代碼或 ISIN      ][查]   │
│ ISIN：尚未啟用        │   │ ISIN：尚未啟用（無已核准對照來源）    │
│ 基金身份：◇ 尚未確認 │   │ ‹基金名›｜‹code›｜as_of‹日›｜來源‹›   │
│ [加入比較 ‹n›/3]     │   │ 歸一化 NAV（基準值依 UI-13）          │
├══════════════════════┤   ├═══════════════════════════════════════┤
│[語] 依條件篩選       │   │[語] 依條件篩選（EXP-0～7）            │
│ 目前條件下有 N 檔符合│   │ 目前條件下有 N 檔符合（不排名）       │
└──────────────────────┘   └───────────────────────────────────────┘
主 CTA：查詢（第一區）
```

| 項 | 內容與 input contract |
|---|---|
| 第一區 | MoneyDJ code primary；ISIN「尚未啟用」；分清查無與取數失敗（`DEC-2026-11-01-01`／`-02`；78）`[語]` |
| 第二區 | 既有 candidate filter；三態篩選；比較上限 3（`EXP-3`）`[語]` |
| 歸一化與比較（2026-11-02 已裁示） | 第一區歸一化 NAV 基準值＝**100**（UI-13 A）；lookup 基金比較**最多 3 檔**（UI-12 (5) A），與 `EXP-3` 為兩個獨立元件、選取不互通（`DEC-2026-11-02-07`；狀態更新，不是漏刪） |
| 禁止 | 名次、精選、AI 排名、名稱模糊搜尋（`DEC-2026-10-27-32`／`-33`）`[語]` |

### 7.4 🤖 AI 投資總結（Phase 7 前導覽可見但不可點；不註冊頁面）

```text
390px（Phase 7 後）                     desktop 1280（Phase 7 後）
┌──────────────────────┐   ┌───────────────────────────────────────┐
│ System State         │   │ System State：⬜ 無法判定（‹缺什麼›） │
│ ⬜ 無法判定（‹缺›）  │   ├───────────────────────────────────────┤
│ 解讀｜反證｜依據     │   │ 解讀｜最大反證｜▸ 查看依據（UI-14）   │
└──────────────────────┘   └───────────────────────────────────────┘
runtime 未啟用：整區只顯示「AI 分析暫不可用／無法判定」（75 第 12 節）
```

四區方向＝79 UI-14 proposal；不放假資料、不顯示機率或信心（79 C-2；沿用較嚴原句，不採「僅限未校準」的放寬措辭，因 79 C-2 規則本文為「沒有 calibration contract 前禁止任何機率、信心值」）。Phase 7 前：導覽項可見但不可點、不註冊 renderer、不進空殼頁，標示字樣引用 `shared/ui_semantics/rules.py::APPROVED_WORDING["shell_nav_not_open"]`（不在本檔複製字樣；Shell `DEC-2026-11-03-10`、`DEC-2026-11-03-11`）；`<pkg>` 不註冊此頁（`DEC-2026-10-29-07`）。頁面具體 wireframe 與 Phase 7 啟用仍需另行核准，上方線框僅供 Phase 7 後審核。runtime 未啟用：整區只顯示「AI 分析暫不可用／無法判定」（75 第 12 節）。（來源：#1135 有效成果 A，`DEC-2026-11-03-12`）

### 7.5 ⚙️ 設定

```text
390px                                   desktop 1280
┌──────────────────────┐   ┌───────────────────────────────────────┐
│[語] 資料可信度｜帳號 │   │[語] 資料可信度｜Google 帳號｜Active Sheet│
│[語] Active Sheet     │   │[語] 來源健康｜各頁資料狀態總表         │
│[語] ▸ 來源健康       │   │[提] ▸ 通知偏好＋送達健康（UI-15）      │
│[提] ▸ 通知（UI-15）  │   │[提] ▸ 規則登錄（唯讀，UI-10）          │
│[提] ▸ 規則登錄（唯讀）│  │[提] ▸ Digest viewer（Digest 之後）     │
└──────────────────────┘   └───────────────────────────────────────┘
```

不是投資 rule editor：不得編 Risk Cap、action rule、threshold（79 §17.2）；第一階段唯讀；不顯示 secret。

**2026-11-02 已裁示（UI-15 A、UI-10 A，`DEC-2026-11-02-07`；狀態更新，不是漏刪）**：⚙️ 擁有 notification preference／delivery health／audit（Notification Preference ≠ Investment Rule；audit 不存 secret／credential raw value；delivery metadata 不進 Decision Digest／OneBrain fingerprint，79 §17.9～17.10）；規則登錄為唯讀殼，Digest viewer 待 Digest production。線框中「[提] ▸ 通知（UI-15）」「[提] ▸ 規則登錄（唯讀）」自本日起為已裁示的 ownership，元件版面仍待 New UI2 ⚙️ 頁 wireframe。

---

## 8. Migration boundary

### 8.1 三代 UI【F-轉述 `DEC-2026-11-02-02`／`-03`；整理為 P】

| | Old UI（`app.py`、`ui/`） | ui_v2（Legacy New UI） | New UI2（`<pkg>`） |
|---|---|---|---|
| 定位 | read-only logic reference | Legacy／Reuse Candidate；freeze（政策見 NG-2） | 唯一未來正式 presentation layer |
| 可做 | 讀它的公式、edge case、fallback 當參考 | 依 NG-2：安全與正確性修正；（A 案）行為不變的抽取＋shim | 新頁、新元件、新 view model、新守衛 |
| 禁止 | 修改、重構、新增功能、搬 layout／navigation／visual style | 加功能、改版面、刪除（清理另走 Gate） | import ui_v2 的 page／view／css／shell；新增資料源或規則 |
| **2026-11-02 已裁示**（`DEC-2026-11-02-05`、`-06`） | 不修改、不新增功能、**不公開到正式 Streamlit**、只作 logic／capability reference | **maintenance-only**（NG-2 A）：只修安全／正確性問題；可把共用計算搬到 shared／domain 層，但 ui_v2 行為不變、搬遷批須獨立稽核；BL-0532 字樣統一也套用（NG-2 附題 A）；不新增新版面；**不公開到正式 Streamlit**；只保留 rollback／reuse 能力 | `ui_v3/`；未來唯一正式 Presentation Layer；正式 cutover 後唯一出現在正式 Streamlit 的 UI |

> 上表三列原字保留；第四列為 2026-11-02 裁示後的現行邊界（狀態更新，不是漏刪）。migration boundary（本節）自 2026-11-02 起凍結（`DEC-2026-11-02-05`）。

### 8.2 搬什麼、永不搬什麼【P】

| 搬（PORT／KEEP） | 永不搬（REIMPLEMENT 或不用） |
|---|---|
| 3.2 表中 PORT 列（領域計算、`NAV_NOT_READY_DAYS`、`contrast_ratio`、`mark_fetch_failures` 類純函式、active_gate 純邏輯）；規則資料表（3.3 (c)）；`status_class`／`page_health` 分類語意 | ui_v2 layout、CSS、theme 色碼、shell／shell_nav、presentation_view、page.py 管線、sparkline_svg、block dict 形狀；Old UI 任何 presentation |

---

## 9. Test Strategy【P】

| 類 | 做法 |
|---|---|
| domain 測試 | ui_v2 A 類（例：`test_hld_logic`、`test_alo_logic`、`test_hld_live_freshness`、`test_p3_page_status_logic`【F-轉述】）隨 PORT 搬遷到新住址；golden 值一字不改；搬遷前後同一組輸入輸出比對 |
| view-model 測試 | 每頁 view model 對 fake scenario 產出元件 schema；B 類字面鎖改寫成「狀態鍵 → 字樣」規則表測試 |
| navigation 測試 | 頁序、頁名、🤖 Phase 7 前不註冊、無第六頁 |
| component contract 測試 | `StatusChip` 只接受規則表 kind；`ActionSlot` 在 Phase 7 前只能是無法判定或不顯示；Missing 恆為 `◇ 資料未備` |
| AppTest smoke | 每頁在 fake adapter 下可 render、不拋例外 |
| mobile screenshot acceptance | 沿用 `tests/visual_fidelity`：V1～V3 直接用；V4～V8 參數化選擇器（目前綁 `.pc-chip` 等）；M1～M6、A1～A6 屬 ui_v2，New UI2 另寫頁專屬檢查；`evaluate`／`hard_failures`／分級與 `vf_config` 視窗（390×844、desktop）沿用【F-重驗：`evaluate`、`hard_failures`、`VIEWPORTS` 存在】 |
| 守衛 | (1) New UI2 import guard（同型於 `tests/ui_v2/test_ui_v2_live_import_guard.py`：只 adapters 可 import 下層、禁舊樹、禁網路、禁動態 import、fail-closed 白名單、新檔自動納入）＋**新增「不得 import ui_v2 的 page／view／css／shell，只准 import 明列 reuse allowlist」**；(2) 擴大 `tests/ui_v2/test_readonly_write_surface_guard.py` 的 `SCAN_DIRS`（現為 `ui_v2`、`services/v2_tables`【F-重驗】）納入 `<pkg>` 與 `services/v2_domain`；(3) New UI2 自備頁序守衛（`tests/ui_v2/test_preview_entry.py` 逐字對 44 的頁序，屬 legacy 保留【F-重驗】） |
| scenario 清單 | Missing、source failure、stale、long text（長基金名、長原因）、no holdings、multiple holdings（含同鍵合併）、ISIN 未啟用、OAuth 未登入、Sheet 未選、權限不足 |
| 原則 | screenshot 不取代語意測試；CI fixture screenshot ≠ production-like Cloud screenshot（同既有 VF 兩層標示） |
| CI lane | fast：view-model、守衛、domain、component contract；slow：AppTest、截圖 |
| **cutover 守衛（2026-11-02 增補；BL-0535；`DEC-2026-11-02-06`）** | 自動化測試：正式 entrypoint **只註冊 `ui_v3` 的頁**；**不 import、不連結** Old UI 或 ui_v2 的頁；**不存在舊／新 UI 切換 widget**。此測試是 **cutover 驗收 Gate**（未綠不得切 default）；**在 cutover 批撰寫**（`ui_v3/` 目前尚不存在，現在寫不出可執行的斷言）。正式 Cloud 的 main file 設定屬 repo 外狀態，另需 Cloud 設定證據（截圖或設定紀錄）登記於 evidence，與測試一起構成 BL-0535 的驗收【I：Cloud 設定無法由 repo 內測試驗證】 |

---

## 10. Cutover Strategy＋Preview-first【~~P~~ → NG-3 A 已裁示（`DEC-2026-11-02-05`）；cutover 約束見 `DEC-2026-11-02-06`；狀態更新，不是漏刪】

> **2026-11-02 正式 Streamlit 顯示規則與 cutover 約束（`DEC-2026-11-02-06`；決策者：客戶；永久；逐字見 `docs/evidence/decisions/2026-11-02_new_ui2_ng_and_final_ui_contract_ruling.md`）**——下方兩張表原字保留，凡與本段牴觸處以本段為準：
> 1. **正式 Streamlit 對使用者只顯示目前最新正式 UI。** 切換前：New UI2 以獨立 Preview App 平行驗收（NG-3 A），正式 App 維持現行版本，Preview 不影響正式使用者。
> 2. **cutover 後**：正式 entrypoint 只指 `ui_v3`；正式 UI 只顯示 New UI2；Old UI 與 ui_v2 從正式 navigation／entrypoint 隱藏。
> 3. **不提供切換器**：不提供一般使用者舊 UI 切換入口，首頁不放「舊版／新版」切換器。
> 4. **rollback 只作維運用途**：repo 內保留回切能力（ui_v2 為 maintenance-only／rollback candidate），不做成使用者功能。下表「ui_v2 保留可回切」一律讀作維運回切。
> 5. **正式網址**：若能在不破壞部署與 OAuth／redirect contract 的前提下維持原正式網址，優先維持；不為 New UI2 任意改正式 URL。
> 6. **切換方法**：首選「改 Streamlit Cloud 正式 App 的 main file 設定」【I：不必改 `app.py`、原網址可保留；是否可行須於 cutover 時實測】；**若必須改 `app.py`，即撞 Old UI DO NOT TOUCH 邊界，屆時停下送客戶 Gate**，不得自行處置。
> 7. **不授權刪除**：Old UI 與 ui_v2 保留程式（保留程式 ≠ 對使用者公開）；刪除另走刪除 Gate（階段 7）。
> 8. **可稽核要求**：cutover 後正式 navigation／entrypoint 不得暴露 Old UI 或 ui_v2 —— 以第 9 節 BL-0535 cutover 守衛（自動化測試）＋ Cloud 設定證據驗收；兩者未備，不得視為 cutover 完成。

| 階段 | 內容 | 出口條件 |
|---|---|---|
| 0 | ui_v2 進入 freeze（NG-2） | 客戶裁示 |
| 1 建立 | PORT 共同層、`<pkg>` 骨架、preview 入口、守衛 | 守衛綠、domain golden 不變 |
| 2 fake／VM 驗證 | 五頁以 fixtures 跑 view model 與 AppTest | scenario 清單全綠 |
| 3 page-by-page integration | 每頁先出 New UI2 線框送客戶（§-1.5.4）→ 接 adapters | 每頁客戶核准＋稽核 |
| 4 parallel preview | New UI2 preview 與 ui_v2 並行 | 客戶驗收清單 |
| 5 acceptance | 390px 與 desktop 驗收、VF Gate | 客戶核准 |
| 6 switch default | 正式入口改指 New UI2；ui_v2 保留可回切 | 回切演練過（→ 2026-11-02 增補：另須 BL-0535 cutover 守衛綠＋Cloud 設定證據；Old UI／ui_v2 不出現在正式導覽、無切換器，`DEC-2026-11-02-06`） |
| 7 再評估清理 ui_v2 | 另走刪除 Gate | 客戶裁示 |

| 議題 | 提案 |
|---|---|
| preview 部署 | **A**：另建一個 Streamlit Cloud app（main file＝`<pkg>/app_preview.py`）；前例：`fade6046` 的 `docs/HANDOFF.md` 下一步指示寫明 ui_v2 preview 以第二個 App、main file `ui_v2/app_preview.py` 建立【F-重驗：HANDOFF 該句存在】；但書：那是 HANDOFF 的「下一步」指示，HANDOFF 自陳 repo 內無法查證 Cloud App 是否已照此建立。需客戶在 Cloud 建 app、在 Google 端另登記 OAuth redirect。**B**：同 app 內隱藏入口——省一個 app，但 session 與快取和 ui_v2 混在同一 process、導覽守衛更複雜 |
| switch default | 【I】若以「改 Cloud app 的 main file 設定」切換，不必改 `app.py`，可避開 Old UI DO NOT TOUCH 與 `DEC-2026-11-02-02` supersedes 欄登記的「切正式入口若需動 `app.py`」張力；回切＝改回設定 |
| session key | New UI2 自有前綴（內部決定）；OAuth 沿用 `b_oauth.` 與 `_v2_refetch_runtime`（下層定義，不改）；B 案同 process 時須確認兩代 UI 不互相清除 |
| 快取 | 同 process 天然共用（`register_cache`、`_ttl_cache`）【F-轉述】；不同 app 各自一份，冷啟動成本加倍 |
| 回復 | switch default 可回切；ui_v2 在清理 Gate 前不刪 |
| 禁止 | 先刪 ui_v2；以 preview 冒充正式驗收 |
| 清理張力 | ui_v2 清理需另走刪除 Gate；`DEC-2026-10-26-01` (10)「新 UI 覆蓋後移除舊頁」與「先凍結不刪」的關係待客戶表態（本案只凍結不刪）（→ **2026-11-02**：客戶裁示「保留程式 ≠ 對使用者公開」—— 舊頁自正式導覽隱藏、程式不先刪，刪除仍另走 Gate，`DEC-2026-11-02-06`；狀態更新，不是漏刪） |

---

## 11. Presentation DEC 處置表【~~P~~ → NG-5 A 已裁示（`DEC-2026-11-02-05`）；分類依 `DEC-2026-10-29-05` 的 A 資訊語意／B presentation-only／C mixed】

> DEC 內容為轉述自 SSOT 組【F-轉述】；分類與處置為文件組整理，可被客戶推翻。
>
> **2026-11-02 狀態（`DEC-2026-11-02-05`、`-07`；狀態更新，不是漏刪）**：客戶採 NG-5 A —— 純 presentation／layout DEC 由 New UI2 各頁 wireframe 重新核准；涉及資料語意、投資語意、規則語意者保留；被 amend 的既有 DEC 必須逐條列出、不得默默覆蓋。本表處置自本日起為已核准的處置；`DEC-2026-10-30-01` D1 的 amendment 由客戶在 UI-12 (1) 明確同意；UI-12 (2)「國際｜S&P 500」卡去留客戶未單獨表態，併入 New UI2 🌍 wireframe（總管讀法，可被客戶推翻）（`DEC-2026-11-02-07`）。表列內容一字未改。

| DEC／條文 | 類 | 處置 |
|---|---|---|
| `DEC-2026-10-30-01` D1（🌍 Primary 單序列切換） | C | 語意（Primary 只一張、Secondary 不複製 Primary）保留；**改比較圖＝amendment Gate**（79 UI-12(1)）（→ **2026-11-02 客戶已同意 amend**：方向＝TAIEX vs S&P 500 比較圖，最終呈現由 New UI2 🌍 wireframe 重新核准，`DEC-2026-11-02-07`） |
| `DEC-2026-10-30-01` D2～D7 | 多為 B／C | 順序語意（D7：狀態→主判讀→Primary→Secondary→依據→details）保留；版面釋放到 New UI2 🌍 wireframe 核准 |
| `DEC-2026-10-30-02` D-1～D-12 | 多為 C | 「Block ID ≠ Container」「四項核心欄位不得因 Missing 從第一屏消失」「禁 Top N」「不新增彙總公式」保留；容器排列釋放 |
| `DEC-2026-10-30-04`、`DEC-2026-10-31-01`、`-02` | C | β 階梯與 H6 語意保留；P3 容器位置與 Layout A 釋放 |
| `DEC-2026-11-01-02`（IA P、單一輸入框 X、S6 字樣） | C | 上下兩區與身份語意、字樣保留；版面釋放 |
| `DEC-2026-10-27-09`～`-12`（深色側欄、底部導覽、≤2 次互動、390 實測） | C | 「≤2 次互動」「不做空殼」「390 實測」保留；深色側欄等視覺釋放（NG-4） |
| `DEC-2026-10-27-26`／`-27`／`-28`／`-31` | A／C | 摘要卡 ≤5、核心圖 ≤4、期間 3M/6M/1Y/3Y 預設 1Y、非顏色辨識保留 |
| 44 之十九（Visual Budget、圖卡模板、placeholder、其七首屏、其九 VFG 12 項） | A（流程規則） | 建議沿用為 New UI2 流程規則 |
| 44 第二節／2.1（四層、層 3／4 ≤3、三斷點 375／768／1280） | C | 上限語意保留；層別排列可重設計 |
| 44 之二十（頁序頁名、Pending≠Active） | A／C | 頁序頁名與 Pending≠Active 保留；位置可重設計 |
| 各頁 BLOCK 規格 | C | 塊 ID／來源／規則／空狀態保留；層別與排列可重設計 |
| vnext_visual_blueprint、`DEC-2026-10-27-07`（禁未經 Gate 重設 IA／hierarchy） | C | 併入 New UI2 wireframe Gate（即「經 Gate」） |
| `DEC-2026-11-02-02` 第 (5) 點 | — | 已由 `DEC-2026-11-02-03` superseded（ui_v2 baseline 一句） |

**純語意 input contract（不釋放）**：◇ 資料未備與符號對照、四狀態與四空狀態、β 階梯語意、Block ID≠Container、67 六行動詞、禁方向詞／排名／星等／Top N、情境指數≠目標價、找基金 identity contract、Digest／OneBrain 邊界（`DEC-2026-10-27-18`、`-10-29-06`／`-07`、`-10-31-03`）、Visual Budget 上限語意、第一階段唯讀、圖表缺段斷線不補／不畫目標價線／不只靠紅綠、期間切換是 display control、13.3 跨頁一致。

**44 處置【~~P~~ → 已核准（NG-5 A）】**：不改 44（`tests/ui_v2/test_alo_logic.py` 等以 md5 鎖 44【F-重驗：`test_alo_logic.py` 有 md5 斷言】）；沿用「以 DEC 指標限定 supersede 範圍」的前例。79 UI-12／UI-13／UI-14 的 presentation 部分併入 New UI2 wireframe 裁示，**UI-12(1) 仍明列為 D1 amendment**。

---

## 12. Decision Gates（~~⛔ 待客戶裁示~~ → 已裁示：NG-1～NG-5 全部採 A，`DEC-2026-11-02-05`；狀態更新，不是漏刪）

> **2026-11-02 裁示結果（決策者：客戶；逐字見 `docs/evidence/decisions/2026-11-02_new_ui2_ng_and_final_ui_contract_ruling.md`）**：下表選項與推薦原字保留作 rationale；各 Gate 的裁示結果見表下「裁示結果」表。UI-1～UI-15 已同批裁示（`DEC-2026-11-02-07`，見 79 第 13 節）。

> UI-1～UI-15（UI-11 已裁示、不重問）仍是**語意 Gate**，建議與 NG-1～NG-5 **一次裁示**；合併呈現時，UI-12／UI-13／UI-14 的 presentation 部分視為由 NG-5 處理，UI-12(1) 另行明列。技術細節（session 前綴、token 數值、目錄內部命名、selector）屬內部決定，不列 Gate。

| Gate | A | B | C | 推薦 | 影響 | 可回復 | 涉及 migration |
|---|---|---|---|---|---|---|---|
| **NG-1 目錄命名** | `ui_v3/` | `ui_next/` | `ui2/` | **A**（第 4.1 節） | import 路徑、守衛路徑、文件對照 | 早期可（尚無程式）；有程式後改名成本高 | 否 |
| **NG-2 ui_v2 freeze policy** | maintenance-only：只修安全與正確性 bug；允許行為不變的領域計算抽取＋re-export shim（含 import 守衛加白名單）；不加功能、不改版面 | hard freeze：一行不改；PORT 改用複製並以測試鎖一致 | 繼續演進（與已裁方向不符，`DEC-2026-11-02-03`） | **A** | A 讓公式只有一份；B 產生重複、清理時收回 | 可 | **是**（PORT 方式） |
| NG-2 附題：BL-0532 Missing 統一是否也做在 ui_v2 | 做（ui_v2 仍在 preview，字樣一致） | 只做在 New UI2 | — | **A**【I】：正確性修正屬 maintenance 範圍 | ui_v2 B 類字面鎖測試需同步 | 可 | 否 |
| **NG-3 Preview／cutover** | 另建 Streamlit Cloud preview app 平行驗收；驗收後切 default；ui_v2 保留可回切 | 同 app 隱藏入口 | 直接替換（不建議；與已裁方向不符，`DEC-2026-11-02-03` 第 (6) 點 parallel preview） | **A** | 需客戶建 app、OAuth redirect 另登記 | 可（切回設定） | **是** |
| **NG-4 視覺語言沿用範圍** | 沿用狀態符號、語意色名、字樣規範；版面／元件／spacing／typography 重建 | 版面與視覺皆重建（含色名） | 沿用 ui_v2 CSS（不建議；與已裁方向不符，`DEC-2026-11-02-03`：New UI2 presentation 必須重新乾淨建立） | **A** | 使用者辨識度延續；設計 token 重訂 | 可 | 否 |
| **NG-5 Presentation DEC 釋放規則** | 純 presentation DEC 不綁 New UI2、由各頁 New UI2 wireframe 重新核准；混合 DEC 語意保留、版面釋放；會被 amend 的客戶 DEC 逐一明列（見表下） | 既有 presentation DEC 照搬 | 逐條重審 | **A**（第 11 節表） | 決定 New UI2 線框自由度 | 可 | 否 |

**裁示結果（2026-11-02，`DEC-2026-11-02-05`）**：

| Gate | 裁示 | 客戶補充 |
|---|---|---|
| NG-1 | **A** `ui_v3/` | — |
| NG-2 | **A** maintenance-only | 只修安全／正確性問題；共用計算可搬到 shared／domain 層，但 ui_v2 行為不變、搬遷批需獨立稽核 |
| NG-2 附題 | **A** | BL-0532 缺資料字樣統一也套用到 ui_v2，視為正確性修正 |
| NG-3 | **A** 獨立 Preview App 平行驗收，通過後才切正式預設 | 正式 Streamlit 顯示規則與 cutover 約束另立 `DEC-2026-11-02-06`（第 10 節） |
| NG-4 | **A** | 保留既有狀態符號、顏色語意與正式用字；layout、component、spacing、information hierarchy 重新建立 |
| NG-5 | **A** | 純 presentation／layout DEC 由 New UI2 各頁 wireframe 重新核准；涉及資料語意、投資語意、規則語意者保留；被 amend 的既有 DEC 逐條列出、不得默默覆蓋 |
| 前端框架（內部決定） | 客戶確認：Streamlit 維持現行內部決定，不更換 framework | — |

**推薦理由摘要（總管推薦，可被客戶推翻）**：NG-1 A 免 cutover 後改名；NG-2 A 是唯一能讓領域公式只有一份的方式，且 shim 讓 ui_v2 行為不變；NG-3 A 有 ui_v2 preview 的 HANDOFF 前例（見第 10 節但書）、可回切，且【I】若以 Cloud main file 設定切換即不碰 `app.py`；NG-4 A 保留使用者已熟悉的狀態語言、同時給 New UI2 乾淨版面；NG-5 A 讓語意不流失、版面不被舊裁示綁死。

**NG-5 A 會 amend 的客戶 DEC（逐一列出；依第 11 節 C 類，射程只限版面，語意保留）**（→ **2026-11-02 已核准**：下表 amendment 依 `DEC-2026-11-02-05`（NG-5 A）與 `DEC-2026-11-02-07`（UI-12 (1) D1；(2) S&P 500 卡去留併入 🌍 wireframe，總管讀法，可被客戶推翻）生效；清單保留，不得默默擴張；狀態更新，不是漏刪）：

| DEC | 被 amend 的部分 | 語意保留的部分 |
|---|---|---|
| `DEC-2026-10-30-01` D1 | 🌍 Primary 單序列切換（若改比較圖；即 79 UI-12(1)，**需客戶明確覆議**）（→ 2026-11-02 客戶已明確同意：方向＝TAIEX vs S&P 500 比較圖，最終呈現由 New UI2 🌍 wireframe 重新核准，`DEC-2026-11-02-07`） | Primary 只一張、Secondary 不複製 Primary |
| `DEC-2026-10-30-01` D2～D7 | 圖卡與區塊的版面配置 | D7 段序（狀態→主判讀→Primary→Secondary→依據→details） |
| `DEC-2026-10-27-09` | 正式目標視覺＝深色主側欄＋淺色主內容區（只限視覺 theme；New UI2 視覺依 NG-4 重訂） | —（該則自陳只限視覺 theme） |
| `DEC-2026-10-27-10`～`-12` | 導覽與側欄的視覺形式 | ≤2 次互動、不做空殼、390 實測 |
| `DEC-2026-10-30-02` D-1～D-12 | 容器排列 | Block ID ≠ Container、四項核心欄位不得因 Missing 離開第一屏、禁 Top N、不新增彙總公式 |
| `DEC-2026-10-30-04`、`DEC-2026-10-31-01`、`-02` | P3 容器位置、Layout A | β 階梯、H6 |
| `DEC-2026-11-01-02` | 兩區的版面位置 | IA P（上下兩區）、單一輸入框 X、S6 字樣與身份語意 |
| `DEC-2026-10-27-07`（vnext_visual_blueprint） | 舊藍圖的版面與 hierarchy 細節 | 「未經 Gate 不得重設 IA／hierarchy」：New UI2 各頁 wireframe 核准即為該 Gate |

⚠️ 上表 DEC 內容轉述自 SSOT 組【F-轉述】；`DEC-2026-10-27-09` 標題「只限視覺 theme」本組讀過【F-重驗】。

**附註｜前端框架（原列 NG-6，改為內部決定）**（→ **2026-11-02 客戶確認**維持現行內部決定、不更換 framework，`DEC-2026-11-02-05`）：維持 Streamlit 現況（共用 OAuth／secrets／快取／測試工具鏈），不列客戶 Gate；依 `PROJECT_RULES.md` 13.4 第 6 條（Decision Gate 不氾濫）——維持現況、無多個具產品意義的合理方案。若日後真要換框架，屬重大遷移，屆時另開 Gate。

---

## 13. 核准後實作順序【P】

> **2026-11-02 狀態**：NG-1～NG-5 已核准（`DEC-2026-11-02-05`），下表 `<pkg>`＝`ui_v3/`。**下表任一批開工前**，須先通過 Model／Mode／Effort Change Gate：客戶明確回覆「已切換／可以開始」前不得開始 `ui_v3` production（`DEC-2026-11-02-04`）。cutover 批另須 BL-0535 守衛（第 9 節）與 `DEC-2026-11-02-06` 約束（第 10 節）。

> 📌 **2026-11-03 指標（`DEC-2026-11-03-02` G3；不改下表任何一格）**：客戶 2026-11-02 逐字「每批至少一組真正獨立稽核」（`docs/evidence/decisions/2026-11-03_mkt_wireframe_ruling.md`「同批補錄」(d)）。執行組讀法（可被客戶推翻）：每個 `ui_v3` 實作批至少 1 組真正獨立稽核，比下表「稽核等級」欄的依風險分級更嚴；兩者衝突取嚴。

| 批 | 內容 | 可機械式？ | 稽核等級 |
|---|---|---|---|
| 1 | PORT 領域計算到共同層（a2）＋`NAV_NOT_READY_DAYS` 落點＋ui_v2 shim＋import 守衛白名單；golden 不變 | 搬遷動作可機械式，但屬 formula／data semantics 等級 | **至少 1 組獨立稽核**（`DEC-2026-10-16-05`） |
| 1 | `<pkg>` 骨架、preview 入口、New UI2 import guard、readonly guard 擴大、頁序守衛 | 可機械式 | 治理規則等級：1 組獨立稽核 |
| 1 | fake scenario fixtures＋view model 骨架（共同欄位、`ActionSlot` 佔位） | 可機械式 | 自驗＋稽核併批 1 |
| 2 | 呈現規則資料表（3.3 (c)）＋Design token 命名 | 規則表內容屬語意，須對照客戶裁示字樣 | 1 組獨立稽核 |
| 3～ | 逐頁：先線框送客戶（§-1.5.4）→ view model → page → adapters → VF | 線框不可機械式；核准後 render 可機械式 | 每頁依風險分級 |
| 後續 | Digest／Risk Cap／Action State／OneBrain 接口 | 不可機械式（另走 Gate） | 依 79／75 |

**Model／Effort**（依 `PROJECT_RULES.md` 5.1，不寫模型名）：架構凍結、PORT 稽核通過後，骨架、守衛、render 等機械式批可降低設定；PORT 本身、規則表、Digest 相關批維持較高設定。

---

## 14. 風險與缺口

| # | 風險 | 處置方向 |
|---|---|---|
| R1 | 領域計算住在 ui_v2 logic，且 import `page_health`／`status_class`（L3）【F-重驗】。另：`hld/logic.py::deviation_rows` 的輸入是 ui_v2 形狀的 node dict（`_state`／`_raw`／`_fund_code`），state 值是中文字面（`STATE_MISSING`＝「資料未備」、`STATE_ERROR`＝「系統錯誤」）；`exp/logic.py::apply_rules_tristate` 經 `compare_tristate` 回傳中文原因字串【F-重驗】 | PORT 前先切斷依賴；`status_class` 一併下沉或拆分。【I】行為不變地搬入 services 會把 presentation 形狀與字面帶進 L2；要不要先改成鍵值介面（字樣留在 view model），交 PORT 的獨立稽核判讀 |
| R2 | 現行 ui_v2 import 守衛禁止 ui_v2 檔 import 舊樹（除 `source.py`）【F-重驗】 | a2 需加逐檔白名單；屬 NG-2 A 範圍 |
| R3 | 頁間鏡像重複（`_grid_css`、`DISPLAY_TZ`、`NAV_NOT_READY_TEXT`、`contrast_ratio`）【F-重驗】 | New UI2 只寫一份；ui_v2 重複留待清理 Gate |
| R4 | OAuth redirect：另一網址需在 Google 端另登記 | 客戶部署動作，列入 NG-3 A 的前置 |
| R5 | 快取與 session 共用（同 app 方案） | 推薦另建 app；若 B 案須驗兩代 UI 不互清 state |
| R6 | VF 選擇器綁 ui_v2 class | V4～V8 參數化；ui_v2 專屬檢查不沿用 |
| R7 | 44 md5 守衛 | 不改 44；以 DEC 指標限定範圍 |
| R8 | `DEC-2026-10-26-01` (10) 退役原則與「凍結不刪」張力；切 default 若改 `app.py` 撞 Old UI 邊界 | 清理與切換分開裁示；推薦以 Cloud 設定切換 |
| R9 | `repositories/macro/yf.py`／`fred.py` 經根目錄 `fund_fetcher` 拖入舊 services【F-重驗】 | 不屬 New UI2 範圍；登記，不動 |
| R10 | 下層中文 reason／狀態字面被當 presentation 用 | view model 一律以 reason_code／status 鍵映射 |
| R11 | ui_v2 頁代號（alo／hld）與 New UI2 IA（💼 合併）不同 | settings_store adapter 對照（3.3 (d)） |
| R12 | 72／73／76／78 是 ui_v2 的線框核准，不自動延伸到 New UI2（§-1.5.4） | New UI2 每頁線框重新送客戶 |

---

## 15. 產出者聲明與未驗證清單

**本組重驗的（`d89b1fbc`；其程式目錄與 `fade6046` 相同）**
- `services/v2_tables/` 十三個模組檔（含 `__init__`）中，streamlit 字樣只出現在 docstring／註解，無 import；無 `ui_v2`／`ui` import。
- `services/v2_tables/settings_store.py::PAGES_READING_SETTINGS`＝`("set", "alo", "hld", "mkt", "exp")`、`RUNTIME_STATE_KEY`＝`_v2_refetch_runtime`；`market_view::STATE_MISSING`＝「資料未備」。
- `ui_v2/thresholds.py::NAV_NOT_READY_DAYS`＝10，定義只在此檔（非測試檔中），引用者為 ui_v2 的 alo／hld／exp 模組。
- ui_v2 logic 符號存在：`hld/logic.py` 五個、`alo/logic.py` 五個、`exp/logic.py` 兩個、`mkt/chart.py::slice_period`／`build_spec`、`mkt/logic.py::delay_days`；這些 logic 模組 import `page_health`／`status_class`。
- `services/dividend_calendar.py` 的 `infer_schedule`、`predict_ex_for_month`、`detect_anchor`、`estimate_error_band`、`build_summary_text`、`build_summary_flex`、`ERR_BAND_FOOTNOTE` 存在；workflow cron 字面 `23 0 28 * *`。
- `repositories/settings_sheet_repository.py::is_read_only` 註明第一階段恆為 True；`ui_v2/readonly.py::WRITE_CONTROLS_ENABLED`＝False；`b_oauth.` namespace 見 `infra/personal_oauth.py`、`services/v2_tables/personal_session.py` 註解。
- `repositories/macro/yf.py`、`fred.py` 自 `fund_fetcher` import `_ttl_cache`；`repositories/pool_repository.py` 以 try-import 用 `st.cache_data`。
- `shared/ui_v2_error_codes.py` 九個 code。
- `ui_v2/app_preview.py::PAGES` 四列；`ui_v2/presentation.py` 函式清單與 `from ui_v2 import health`；`ui_v2/page_health.py::KIND_*` 四個；`contrast_ratio` 在四份 `theme.py`；`_grid_css`、`DISPLAY_TZ`、`NAV_NOT_READY_TEXT` 鏡像位置；`hld/page.py::prepare_live`、`mkt/page.py::mark_fetch_failures`。
- `tests/ui_v2/` 下 110 個 `.py`（`fade6046`）；`tests/ui_v2/test_ui_v2_live_import_guard.py` 檔頭規則 (1)～(8)；`tests/ui_v2/test_readonly_write_surface_guard.py::SCAN_DIRS`；`tests/visual_fidelity/vf_config.py::VIEWPORTS` 含 390×844；`layout_checks.py::evaluate`／`hard_failures`；`tests/ui_v2/test_alo_logic.py` 對 44 的 md5 斷言；`tests/ui_v2/test_preview_entry.py` 讀 44 3.0 五頁總表。
- 根目錄無 `ui_v3`、`ui_next`、`ui2` 目錄。
- `fade6046` 的 `docs/HANDOFF.md` 記載 ui_v2 preview 以第二個 Streamlit Cloud App、main file `ui_v2/app_preview.py` 建立。
- `docs/DECISIONS.md`（~~工作樹，別組編修中~~ → 2026-11-02 該條目已合併入 main；本輪於 main `e5794711` 重讀，該清單內容一致；狀態更新，不是漏刪）`DEC-2026-11-02-03` 條目的「仍待客戶裁示」清單：NG-1／NG-3／NG-4／NG-5 分別對應目錄命名、preview／cutover、視覺語言沿用範圍、presentation DEC amendment；NG-2 對應 ui_v2 freeze policy，其附題依據 BL-0532；原 NG-6（前端框架）已轉為內部決定，不在該清單內。（→ 該清單各項已由 `DEC-2026-11-02-05` 裁示結案。）

**本組沒有重驗的（轉述自盤點組）**
- `market_view` `_domain` dict 欄位全集；`nav_dividend` 的 `WITHHELD_*`／`PENDING_*`；`exp_profile` 逐欄出處與 `STATUS_*`；`repositories/v2_source_status` 冷卻。
- `dividend_calendar_render` 屬 HTML 產生器、workflow 讀 `POLICY_SHEET_ID`。
- ui_v2 block dict 的 `_` 前綴欄位、`prepare_live` 管線步驟、E1～E8 分層例外的完整內容。
- tests/ui_v2 的 A～E 分類與約 3079 個 test；VF 的 V1～V8／M1～M6／A1～A6 泛用性判斷。
- 第 11 節各 DEC 的內容摘要（本組只讀了 `DEC-2026-10-29-05`、`DEC-2026-11-02-02`、`-03` 的相關段）。
- 44 第二節、之十九、之二十的條文（經 79 與盤點轉述）。

**全稱句揭露**：本檔「無」「只」類敘述凡標【F-轉述】者，取決於盤點組有沒有漏看，本組不宣稱窮舉；標【F-重驗】者為本組單組搜尋，亦未經第二組驗證。第 2～7、10～13 節的分層、命名、token、schema、線框、Gate 推薦為文件組整理、總管推薦，可被客戶推翻。本檔不授權任何 production 實作、不建立 New UI2 目錄、不改 ui_v2、不改 Old UI、不改 44。

**2026-11-02 裁示落盤輪**：檔頭、第 0、4、7、8、9、10、11、12、13 節與本節的裁示註記，依客戶 2026-11-02 裁示（`DEC-2026-11-02-05`～`-07`）由文件組單組就地加註，原字保留；裁示內容以 evidence 逐字檔為準；第 9 節 BL-0535 守衛與第 10 節 cutover 約束的「首選以 Cloud main file 設定切換」仍是推論【I】，須於 cutover 批實測。未經第二組獨立複驗（`CLAUDE.md` §-2 規則 6）。本輪同樣不授權任何 production 實作。

## 16. 客戶 2026-11-03 增補：New UI2 呈現與資料分流契約（`DEC-2026-11-03-08`）

> **增補性質**：客戶 2026-11-03 的正式有效方向（要點轉述存檔 `docs/evidence/decisions/2026-11-03_canonical_convergence_and_new_ui2_rules.md`；其中 D、G 兩段另有**逐字節錄**存檔 `docs/evidence/decisions/2026-11-03_new_ui2_rules_A_to_I_verbatim_excerpt.md`，16.2、16.3 的欄位清單以該逐字檔為準；不在逐字檔內的句子已標「執行組補充」或「要點轉述」）。**不改**第 1、2、3、8 節的凍結內容；永久共用的人類 UI 呈現原則（簡單不失判讀、chart-first、工程資訊不進一般 UI、Presentation Compression≠Information Loss）住 `PROJECT_RULES.md` 13.5，本節只放架構契約，一條規則只有一個權威位置。**不授權實作、不 amend 44、不改任何 Gate**；各頁具體版面仍須該頁 wireframe 核准。

### 16.1 Chart SPEC（主要圖表的短小規格列）

主要圖表的 SPEC 位於主圖上方或緊鄰圖表的可見位置，不要求全部塞入首屏、不得遮蓋主圖；已核准的歸一化揭露可與 SPEC 共用同一顯示區、不重複佔 chip 預算；完整技術細節改放展開的來源／限制／⚙️ 資料健康度，不把長文件塞進主 UI（出處：`DEC-2026-11-03-09` 首屏採 C、基準日純文字行；`docs/v2/81` 第 10.2 節基準日行位於 Primary 圖之前；來源：#1135 有效成果 B，`DEC-2026-11-03-12`；欄位清單與 `PROJECT_RULES.md` 13.5 不變）。欄位依適用性取用：

| 欄位 | 說明 |
|---|---|
| 標的 | 圖畫的是哪個（組）序列 |
| period | 期間（例 3M／6M／1Y／3Y） |
| benchmark／normalized base | 比較基準與歸一化基準值 |
| base date | 歸一化基準日 |
| unit | 單位 |
| frequency | 資料頻率 |
| latest data date | 各序列最新資料日 |
| Missing handling | 缺值處理 |
| comparison rule | 比較規則（例 兩序列取共同基準日） |

範例（客戶）：「SPEC｜基準日 2025-11-03＝100｜日頻｜缺值不補」。`docs/v2/79` 第 4.4 節四項強制揭露（基準日、基準值、頻率、缺值處理）是本表的子集；歸一化比較圖必備該四項，其餘欄位依圖適用。已核准字樣仍以 `shared/ui_semantics/rules.py` 為準（🌍 已核准「基準日 {日}＝100」「頻率：日｜缺值不補、斷線」）；其他欄位的字樣待各頁 wireframe 核准，核准前不得自創。

### 16.2 資料健康度集中到 ⚙️ 設定

- 完整資料診斷不再散落在 🌍／💼／🔍 主頁；主頁只留與判讀直接相關的 freshness／source 摘要。完整診斷集中於 ⚙️ 設定→資料健康度。
- 涵蓋所有正式資料類別：市場、基金、持倉、配息、匯率、利率、景氣、其他正式來源；每項可呈現 status、是否取得、source、as_of、retrieved_at、freshness、Missing 或 failed reason、source health。
- 三層呈現：① 一般使用者摘要 ② provenance／date／source ③ developer diagnostics（預設收合；工程資訊規則見 `PROJECT_RULES.md` 13.5 第 3 點）。
- （執行組補充）與 frozen 44 的「進階診斷」「頁內資料狀態塊」及 ui_v2 時期 `docs/v2/65`、`72`、`73`、`78` 的承接：44 不解凍；由各頁 New UI2 wireframe 承接，是否需 amendment 待客戶確認（`docs/BACKLOG.md` BL-0540）。

### 16.3 資料流與分流：UI ViewModel≠Decision Digest

```text
Data／Sources → Validation／Normalization → Domain／Deterministic Logic → Complete Evidence Layer
   ├─ UI ViewModel（給人看：精簡、圖表優先、key evidence、mobile-first）
   └─ Decision Digest／OneBrain Context（完整正式 evidence：已取得的 objective facts、Missing、
      provenance、source、as_of、retrieved_at、freshness、deterministic calculations、rule results、
      holdings、allocation、dividend／events、market indicators、counter-evidence、cross-page context）
```

- UI 沒顯示的正式資料，OneBrain 仍可讀；OneBrain 可讀的資料，不代表 UI 必須全部顯示。
- UI 精簡不得造成資料精簡：不得因 UI 不顯示就不抓資料、刪 adapter／provenance／health／deterministic result，或停止測試（`PROJECT_RULES.md` 13.5 第 4 點）。
- （執行組補充）與 `docs/v2/67` 8.6（OneBrain context 的 Required／Optional／Excluded 三分）一致；本節補明「ViewModel≠Digest」。

### 16.4 OneBrain 定位

- （H 段，要點轉述，非逐字）OneBrain 不是讀畫面摘要再摘要；它讀完整 Decision Digest，整合 🌍／💼／🔍 evidence、dividend／events、data health、freshness、rule results、counter-evidence 與其他核准資料。
- 未來輸出（客戶 2026-11-03 所列）：系統狀態、AI 投資總結、主要依據、最強反證、風險／不確定性、Evidence trace。**此六項與 `docs/v2/67` 6.1 六段（內容）／8.9 四區（版面）的對映待客戶確認（BL-0540），本節不擇一、不改 67。**
- 仍禁止：AI 創造 objective facts、回寫 canonical data、把 Missing 補成 0／neutral／safe／HOLD、fake probability／Risk Cap／action state；Phase 7 前不正式啟用 🤖。

⚠️ 本節由文件組單組寫成，未經第二組獨立驗證；客戶逐字原文本組未見（要點轉述，見存檔檔頭）。

## 17. 全站共用 Navigation Shell（客戶 2026-11-03 授權只進 Preview App；`DEC-2026-11-03-10`）

> **性質**：實作紀錄與選型依據（BL-0536 Shell 批）。客戶要求與 80 第 7 節五頁 IA 一致：五頁共用同一個 Shell，後續頁直接掛上，不每頁各做導航。**客戶 2026-11-03 驗收裁示（`DEC-2026-11-03-11`）已定 Shell 字樣、Status Bar 讀法與降級首屏收斂（本節 17.2、17.4、17.5 已據以更新）。** **不 amend 第 1～3、8 節**；未新增資料源、dependency、公式、門檻；不 cutover；`app.py` 不引用 `ui_v3`。程式在 `ui_v3/shell/nav.py`（純邏輯與 CSS）、`ui_v3/pages/chrome.py`（畫面）、`ui_v3/adapters/shell_status.py`（既有 health → 狀態）、`ui_v3/viewmodels/shell.py`。

### 17.1 Minimum-Cost Correct Path 比較（`PROJECT_RULES.md` 9.2；內部決定）

現場讀 `requirements.txt`（`streamlit>=1.59.1,<1.60.0`）與實際安裝版本 1.59.2 的 `st.navigation`／`st.Page`／`st.page_link`／`st.container(key=, horizontal=)`／`st.set_page_config` 簽名後比較：

| 面向 | Route A：原生 sidebar navigation＋CSS 底部列 | Route B：完全自製 router／shell | **Route C（採用）：routing 用 `st.navigation(position="hidden")`，presentation shell 自畫** |
|---|---|---|---|
| 未完成頁「可見但不可進」 | 原生導覽只列有 `st.Page` 的頁；要讓四個未完成頁出現，就得為它們建 page（＝空殼頁，被禁止） | 可以，但要自己維持目前頁與 URL | 可以：未掛載頁畫成不可點文字項，沒有 `st.Page`、沒有 renderer |
| 正確性／穩定性 | 手機底部列仍要自製，兩套導覽並存 | 自管 URL／session，換頁與重新整理狀態最容易出錯 | routing 沿用既有 `app_preview` 做法（已有 AppTest 覆蓋），只新增畫面層 |
| mobile | 原生側欄在手機是抽屜，不是固定五格 | 可做 | 底部列是 `st.container(key=, horizontal=True)`＋CSS 固定列；手機隱藏側欄 |
| 修改範圍／回歸 | 中 | 大（取代既有導覽） | 小：`app_preview.main()` 加一個 `render_navigation`；頁面 `mkt.py` 只移走頁首長說明 |
| 可逆性 | 中 | 低 | 高：拿掉 `chrome` 呼叫即回到原本隱藏導覽 |
| 沿用 registry／app_preview | 部分 | 需重寫 | 完全沿用 `IA_PAGES`／`registered_pages()` |
| accessibility／測試 | 原生較佳但不適用 | 要全自己做 | `st.page_link` 是真連結；不可點項用 `aria-disabled`＋`aria-label`；AppTest 可測，版面用 Playwright |

選 C 的理由是上表唯一同時滿足「不建空殼頁」「不自管 URL」「改動最小」「可逆」的一列。已知限制：`st.page_link` 沒有 `aria-current`，目前頁以容器 key（`uv3-nav-now-…`）加 CSS 呈現粗體＋色條／上緣線＋底線（不只靠顏色）；CSS 依賴 Streamlit 內部的 `data-testid`，升版時由 Playwright 量測發現。【I】此為執行組選型，可被客戶推翻。

### 17.2 Shell 內容與未完成頁行為

- **桌機／平板（寬度大於 768px）**：左側固定側欄（標題、五頁導覽、資料狀態區、更新資料 CTA）；沒有收合鈕；不顯示底部導覽。**手機（768px 以下）**：固定底部導覽五格（icon＋短名，觸控高度 60px，納入 safe-area，頁尾留白讓內容可捲過導覽）；不顯示側欄。斷點沿用 44 第二節 2.1 的 768，兩種導覽不會同時出現。
- **未完成頁（💼／🔍／⚙️／🤖）**：可見但不可點，💼／🔍／⚙️ 標「開發中」、🤖 標「尚未開放」（客戶 2026-11-03 定字）；選擇「不可點文字項」而非「可點後跳提示」，原因是可點會讓人以為已完成，且需要一個 handler；沒有任何 renderer、空殼頁或假資料。🤖 在 Phase 7 前不可進，由登錄表建構時擋（`DEC-2026-10-29-07`）。
- **Top／Status Bar**：主區頂端一行**純文字**，內容為「PREVIEW」（滑過顯示「Preview｜非正式頁面」）＋（有缺資料時）資料狀態一句＋更新時間；**不放 chip 形式元素或核心數字元素**（客戶 2026-11-03 裁示第一項：若放了就不能以位於 Shell 為由排除計數）。資料狀態與時間只來自 `MarketPageModel.statuses` 的既有取得狀態與 `fetched_at`（取得時間，不是資料日）；沒有取得時間就寫規則表的缺資料字樣（純文字、零 chip），不推估。⚠️ **資料全部取得時不寫「正常」「資料齊」**：`rules.entry("ok")` 刻意無字（44 頁首資料狀態行規則），客戶要求範例中的「● 主要資料正常」因此未採用；客戶 2026-11-03 已裁示維持不顯示「正常／資料齊」、不得自創綜合結論（資料取得成功不等於 freshness、可靠性、投資判讀或安全狀態全部正常）。長說明（原頁首 Preview 橫幅）移到頁尾。
- **「尚未設定」不是取數失敗**：Status Bar 的取數失敗項數不計尚未設定的序列（44 之十二其二第 1 條）。
- **首屏預算讀法（客戶 2026-11-03 已裁示，`DEC-2026-11-03-11`）**：Status Bar 與導覽同屬 Shell chrome，採純文字讀法、不計入 44 之十九其一之一的「頁級 chip＋核心數字 ≤5」；**但**若 Status Bar 顯示資料狀態 chip 或核心數字，不能僅以位於 Shell 為由排除計數，故本批兩處（Status Bar、側欄狀態區）都不放 chip 形式元素。降級情境的第一屏名額另見 `docs/v2/81` 第 10.2 節（定義、方案比較、前後計數）。

### 17.3 更新資料 CTA：盤點結果與選擇

盤點到的既有路徑：(a) `infra.cache.global_refresh_all`（Old UI 側欄「全域刷新」：清全部 TTL／`st.cache_data`／磁碟快取，並**一併清掉來源退避**，且清 session state）；(b) 舊 B 線 `ui_v2/mkt/live.py` 的「重新取數」按鈕在 `ui_v2` 自己就是停用（原因文案「重新取數尚未接上」，冷卻中則寫來源冷卻秒數）；(c) `services.v2_tables.market_indicator.source_cooldowns()` 只回報冷卻狀態，不提供清除。(d) 既有 `services.macro.clear_tab1_macro_caches(session_state=None)`（Tab1「強制重抓」的正式 L2 路徑）：只清 Tab1 快取與一個 dataset 的退避；是否清得到 `ui_v3` 市場頁用的快取未驗；且 adapters 分層守衛不許 import `services.macro`，直接接上須放寬守衛。
選擇：**不可用＋一句原因**（「預覽版尚未開放更新資料」，客戶 2026-11-03 已定字，`DEC-2026-11-03-11`）。理由：(a) 在 `ui_v3` 分層守衛下 adapters 只能 import `services.v2_tables`／`services.v2_domain`，不能碰 `infra`；且它會清掉退避，違反「失敗時退避、不連續轟炸來源」；現有路徑都無法在不新增 L2 函式或放寬分層守衛下安全接上；新增或放寬都屬新的 refresh pipeline 或分層變更，不在本批授權內。`ShellStatus.refresh_available` 目前恆為 False（原因代碼 `refresh_not_wired`），日後有安全入口時由 adapter 改成 True 並接上；手機沒有 CTA（Status Bar 保持極薄），位置待 ⚙️ 線框。

### 17.4 Shell 字樣（客戶 2026-11-03 已定字，`DEC-2026-11-03-11`；正式用字只在 `shared/ui_semantics/rules.py::APPROVED_WORDING` 的 `shell_*` 鍵）

superseded：本節舊的 pending 候選字樣表與第 17.2 節舊「首屏預算讀法」（含「此讀法未經客戶確認」）已整段取代、未留劃線，原字逐字搬至 `docs/evidence/history/2026-11-03_v2_80_shell_wording_superseded.md`（區塊 S1～S3，基準 `875b1955`，歷史、非現行）。

字樣本文**只有一份**（規則表 `APPROVED_WORDING`；逐字出處 `docs/evidence/decisions/2026-11-03_shell_wording_and_degraded_first_screen_ruling.md`），本節不複製字樣表（不建立第二套字樣表）。`ui_v3/viewmodels/preview_wording.py` 的 `shell_*` preview-only 暫擬定義已退役。與先前暫擬的差異：「部分資料缺失（{n}／{m} 項取得）」→「部分資料未取得（{n}／{m} 項已取得）」；「{n}／{m} 項取得」→「{n}／{m} 項已取得」；🤖 的未開放標籤用「尚未開放」（`shell_nav_not_open`，其餘三頁維持「開發中」）。一項也沒取得時不另造句型，用已核准的「{n}／{m} 項已取得」（總管讀法，可推翻）。

**計數分母的界線**：分母＝本次檢查涵蓋的已登錄項目＝🌍 頁 view model 的五條主要序列（`MarketPageModel.statuses`，由 adapter 以 `len(statuses)` 取得，不是常數）；字樣與畫面不得暗示涵蓋超過這五條的全系統健康結論（守衛 `tests/ui_v3/test_ui_v3_navigation_shell.py`；全量資料健康明細由未來 ⚙️ 承接，見第 16.2 節）。

### 17.5 H5：390px 首屏與桌機量測（BL-0536-H5；注入的人造資料，非真實行情）

Playwright chromium、`deviceScaleFactor` 2；腳本與原始數字在 `docs/evidence/bl0536_shell_h5_2026-11-03/`（`measure.js`、`measurements.jsonl`、截圖）。常態（兩序列 ok）：

| 項目 | 390×844 | 1280×800 |
|---|---|---|
| 無橫向捲動（`scrollWidth`＝`clientWidth`） | 是 | 是（另量 768、769 亦是） |
| 導覽 | 底部列顯示（y 784–844，五格各高 60），側欄隱藏 | 側欄顯示（寬 300），底部列隱藏；768 顯示底部列、769 顯示側欄 |
| 市場狀態、是否需注意、重要依據、資料新鮮度四列 | 皆在第一屏（最後一列底緣約 y 300 之內，可視高度 784） | 皆在第一屏 |
| Primary 圖起點 | 圖頂 y 626，在底部列之上可見（可見約 158px；標題、檢視、期間切換、基準日行都在其上） | 圖頂 y 602 |
| 首屏 chip＋核心數字 | 3 chip＋2 數字＝5（不含 Status Bar） | 同 |
| 頁尾捲到底 | 頁尾底緣 y 776，在底部列頂緣 783 之上，未被遮住 | — |
| 側欄不裁切主內容 | — | 主內容區自 x 300 起，無水平溢出 |

~~⚠️ 首屏 chip＋核心數字計為 5 僅指常態（complete）。降級情境（`measurements.jsonl`：both_missing 390px 為 7 chip＋2 數字、failed 1280px 為 4 chip＋2 數字）整個第一屏的 chip 形式元素較多……降級情境是否另需預算規則，待客戶確認。~~（**客戶 2026-11-03 已裁示不接受降級 7 chip＋2 數字為最終第一屏**，`DEC-2026-11-03-11`；本批把圖下逐序列狀態收成一行文字摘要，降級情境的第一屏名額恆為 5，定義、方案比較與前後計數見 `docs/v2/81` 第 10.2 節；狀態更新，不是漏刪；決策者：客戶。）上表「首屏 chip＋核心數字」列的量測是**常態**；降級情境與重拍後數字見 81 第 10.2 節與 `measurements.jsonl`（含 all_missing、all_failed、美10Y／VIX 檢視）。

結論：未發現首屏預算或資訊密度的實質衝突，沒有放寬 frozen 44。量測限制：真實 Yahoo／FRED 未連線；只量了 Chromium（Safari 未驗）；沒有實機 iOS／Android 瀏覽器（safe-area 與動態網址列為 CSS `env()` 推論，未實機驗）；未驗深色模式的底部列；Streamlit 升版後導覽相容性未驗（CSS 依賴 `data-testid`）；首屏「可見」以座標判定，不是人眼評審。以上皆保留在 BACKLOG BL-0536 待驗證清單，不得宣稱已通過。

⚠️ 本節由執行組單組寫成，未經第二組獨立驗證；選型與首屏預算讀法為總管可推翻的執行組讀法。
