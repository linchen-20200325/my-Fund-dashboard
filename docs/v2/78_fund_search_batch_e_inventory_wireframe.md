# 78｜🔍 找基金「第一批」現況盤點與最小文字線框（BL-0525 Batch E；~~⛔ 待客戶審批，~~ → 2026-11-01 客戶原則核准、S6 修字後正式核准（`DEC-2026-11-01-02`）；不是規格、不是動工授權）

- **狀態**：~~⛔ **文字線框 Gate，待客戶審批。**~~ → **2026-11-01 客戶裁示：第 2 部分原則通過，S6 字樣依客戶修正後視為正式核准，可進下一實作批（MoneyDJ code 主入口）**（`DEC-2026-11-01-02`；狀態更新，不是漏刪；決策者：客戶；原「待客戶審批」在寫下當時為真）。本批只寫文件：沒有改任何 `ui_v2/`、`services/`、`repositories/`、`tests/` 程式，沒有接資料、沒有新增來源、沒有改任何資料語意。第 2 部分的線框通過審批前，不得寫任何 UI 程式（`CLAUDE.md` §-1.5.4 草稿先行）。
- **客戶裁示（2026-11-01；決策者：客戶；正式記錄 `docs/DECISIONS.md` `DEC-2026-11-01-01`；逐字 `docs/evidence/decisions/2026-11-01_fund_search_entries_and_identity_ruling.md`；追蹤 `docs/BACKLOG.md` BL-0525 Batch E 與 BL-0530）**：找基金的正式搜尋入口只有兩個。(1) **MoneyDJ 基金代碼**＝主入口（例：ACTI97）。(2) **ISIN**＝alternate lookup，經 identity resolution 對到同一個 canonical fund identity；無法可靠對應時**不猜、不用名稱模糊比對、不用 AI**，顯示既有 Missing／無法判定語意，保留 provenance 與 unresolved。**取消**：名稱／模糊搜尋、FundClear／TDCC 搜尋入口、其他非正式代碼入口、多來源搜尋模式切換、AI 猜基金。**Source ≠ Identity**；基金身份與持倉／商品／平台碼身份分離（`ACDD01-EQTAL005` 不得用 `split("-")[0]` 猜）；持股比例以 resolved canonical fund identity 為基礎，unresolved 須揭露、不補 0。**本批不做**：AI ranking／星等／Top N／AI score／自動推薦、新公式、新 Risk Cap、新資料來源、OneBrain runtime、候選／觀察清單寫入、Google Sheet 新 writer、舊 UI 大規模搬運；BL-0511 維持 deferred。本檔只引用裁示，不重議。
- **客戶第二則裁示（2026-11-01；2026-11-02 重申，一致；決策者：客戶；正式記錄 `docs/DECISIONS.md` `DEC-2026-11-01-02`；逐字 `docs/evidence/decisions/2026-11-01_batch_e_gate_rulings.md`）**：G-E1 採 A＋C、G-E2 採 A＋C、G-E3～G-E7 採 A；搜尋框採 X（單一輸入框＋格式分流）；S6 字樣修正；頁面 IA 採 P（同頁上下）；第 2 部分原則通過。各項逐條見第 3 部分；第 2 部分狀態見該部分頂部。
- **建立日**：2026-11-01。**讀碼基準**：main `38a16a4`（工作樹無其他程式改動）。程式位置寫「檔案::符號」，不寫行號。
- **編號**：76 為 V7 Layout A 線框，77 為緊急續接檢查點，本檔取 78。
- **落點選擇**：沿用 `docs/v2/72`、`73`、`76` 的「`docs/v2/` 編號 `.md` 文字線框」慣例（不做 HTML 原型，理由同 `docs/v2/72` 開頭）。`tests/test_doc_counters.py` 的 `_MD_DOCS` 已由落盤組在同批登記本檔（+1 行）；本檔作者未改該檔。
- **產出者聲明**：文件組單組產出，**未經獨立複驗**。第 1 部分的「事實」大多來自另一組單組唯讀盤點（本組**轉述，未重驗**，逐項標注）；本組自己重驗的項目標「本組重驗」。完整未驗證清單見第 5 部分。

---

## 0. 怎麼讀

| 記法 | 意思 |
|---|---|
| **【F】** 事實 | 讀碼或實跑得到，附「檔案::符號」；單組判讀 |
| **【F-重驗】** | 本組這一輪自己用 `git grep`／讀檔／離線實跑重驗過（指令與結果見第 5 部分） |
| **【F-轉述】** | 來自另一組單組唯讀盤點，**本組未重驗** |
| **【I】** 推論 | 由事實推出的讀法，可推翻 |
| **【R】** 建議 | 設計選擇或總管推薦，**不是裁示**，由客戶拍板 |
| `‹值›` | 格式遮罩（示意）；本檔沒有任何看似真實的數值或基金名 |
| 符號 | 只用已落字的 ⛔ ◇ ⬜ ◆ ◷；不新增狀態詞或符號 |
| 框寬 | 約 62 欄；全形字算 2 欄，右框線偶有不齊屬正常 |
| 草稿尺寸 | 桌機 1280×800、手機 390×844（`tests/visual_fidelity/vf_config.py::VIEWPORTS`） |

「擬：」開頭的畫面字樣是本檔新擬，**待客戶定字**（`ui_v2/shell_nav.py` 檔頭：UI 文案屬客戶定字）。

---

# 第 1 部分｜現況盤點

## 1.1 ui_v2「🔍 找基金」頁現況（`ui_v2/exp/`）

【F-轉述，其中標【F-重驗】者本組已查】頁名「標的探索」，區塊 `EXP-0`～`EXP-7`，實為**選股池篩選器**：

- 輸入只有條件列（`ui_v2/exp/page.py::_render_exp1`／`_render_exp1_live`：欄位選單＋運算子＋數值）、兩個 multiselect（對照、觀察清單）、欄位勾選與排序。
- 【F-重驗】`ui_v2/exp/page.py` 內確有兩處 `st.text_input`，**但都是條件列的「運算子」「數值」欄**（`_render_exp1` 與 `_render_exp1_live` 內），不是以基金代碼、名稱或 ISIN 為輸入的框；`ui_v2/exp` 下沒有 `chat_input`。因此「沒有代碼／名稱／ISIN 輸入」這句話的正確讀法是「沒有**搜尋**輸入」，不是「沒有任何 text_input」。
- 母體＝Google Sheet `_fund_pool` 的 code 欄：`services/v2_tables/exp_universe.py::load_pool_codes`，只取 code，檔頭註明刻意不讀 `name`／`currency`／`category`／`type_override`／`isin`／`morningstar_secid`／`status`（【F-重驗】檔頭文字確含 `isin`）。
- 基本資料 `services/v2_tables/exp_profile.py`、NAV／配息 `services/v2_tables/exp_nav.py`（【F-重驗】兩檔存在）、代碼→full_key `services/v2_tables/fund_keys.py::resolve_full_keys`。
- `ui_v2/exp/live.py` 檔頭「禁止從基金名稱、代碼或 AI 推測任何屬性」【F-轉述】。
- 第一階段唯讀：`ui_v2/readonly.py::WRITE_CONTROLS_ENABLED = False`、`PHASE1_HIDDEN_INPUT_CODES` 含 `EXP-1`／`EXP-4`／`EXP-5`（【F-重驗】）。
- ui_v2 守衛：`tests/ui_v2/test_ui_v2_live_import_guard.py` 規定只有 `<頁>/source.py` 能 import `services.v2_tables`；`tests/ui_v2/test_readonly_write_surface_guard.py` 以 AST 擋寫入（【F-重驗】兩檔存在；內容規則【F-轉述】）。
- 【F-重驗】`git grep search_funds|tdcc_search_fund -- ui_v2`（`38a16a4`）**0 命中**：ui_v2 內沒有任何搜尋鏈呼叫。

## 1.2 舊樹的「代碼查一檔」與名稱搜尋【F-轉述，函式存在處本組重驗】

| 項目 | 內容 |
|---|---|
| L2 facade | `services/fund_search.py::search_funds`（lazy import；【F-重驗】存在）→ `repositories/fund/sources.py::tdcc_search_fund`／`tdcc_search_fund_with_error`（【F-重驗】存在）：TDCC 3-2／3-4 名錄子字串比對＋FundClear `goGetSearchFundList` 備援 |
| 舊 UI 使用者 | `ui/helpers/fund_research/code_finder.py`（舊 ③「找代號」）；`ui/views/page_03_research.py`（新 ⑧ 並行預覽：搜尋表單「代碼或名稱」＋來源 selectbox＋`DIRECT_LABEL` 逃生門，把任意輸入原封當代碼／網址） |
| 舊 ③ 模式 A | `tab2_single_fund` 的「MoneyDJ URL 或代碼」→ `services/moneydj_fetcher.py::auto_fetch_moneydj`（可 reuse 的 MoneyDJ 代碼取數）；`services/moneydj_fetcher.py::normalize_manual_fund_input`（裸碼 strip＋upper；網址先抽 `?a=`；【F-重驗】讀過 docstring） |
| 與裁示衝突的名稱路徑 | `repositories/fund/fund_orchestration.py::search_fundclear`／`search_moneydj_by_name`（【F-重驗】存在）；`services/fundclear_backfill.py::rank_candidates`／`find_fund_candidates`（difflib 0.55；轉述稱查無非 tests 呼叫者，**非窮舉保證**）；`sources.py::_cnyes_search` 名稱橋接；`sources.py::_morningstar_search_secid` 取 `results[0]`（`docs/v2/69` G-ID-3 已登記） |

## 1.3 ISIN 能力現況

- 【F-轉述】repo 查無 ISIN→MoneyDJ code 的 deterministic 對照。
- 現有 ISIN 相關：`repositories/pool_repository.py::PoolEntry.isin`（選股池第 8 欄手填）與 `resolve_isin`（code→ISIN 單向；【F-重驗】`resolve_isin` 存在）；`sources.py::_morningstar_screener_secid`／`_yahoo_search_secid_by_isin`（ISIN→secId，用於補 NAV）；`services/fund_identity.py` 的 `CanonicalFundIdentity.isin`（optional verification attribute，不從 ISIN 推 code）。
- 【F-重驗】離線實跑 `repositories/fund/sources.py::parse_moneydj_input('LU0766462157')` 回 `code='LU0766462157'`、`is_url=False`：**ISIN 被原樣當成 MoneyDJ code 接受**。
- 【F-重驗】離線實跑 `services/v2_tables/fund_keys.py::_is_pure_code` 對 `LU0766462157`、`ACDD01-EQTAL005`、`ACTI97` 都回 `True`：**12 碼 ISIN 與帶後綴字串的格式都會被放行**。
- 【I】結論：**新入口必須在進入 resolver 與任何取數之前先做輸入分流**，不得讓 ISIN 流進「MoneyDJ code」路徑被當代碼取數（取不到也會被誤認成「查無」）。
- TDCC／FundClear 回應是否含 ISIN 欄：【F-轉述】查無（未打網路、repo 無解析碼）。持倉／保單 Sheet 無 ISIN 欄（`docs/v2/69` G-ID-2；【F-重驗】`docs/v2/69` 該段文字存在）。
- 【F-重驗】`git grep ACTI97` **0 命中（`38a16a4`）**：repo 內沒有以 ACTI97 為例的測試或程式（本檔以它當範例字串，不代表有資料）。

## 1.4 TDCC／FundClear 的後端用途（與搜尋入口不同路徑；裁示未取消）【F-轉述】

NAV（`sources.py::_src_fundclear_nav`、`repositories/fundclear_offshore.py`）、meta（`_src_tdcc_meta`、`_src_fundclear_meta`）、配息（`_src_fundclear_div`）、cron 快取 `scripts/fetch_nav_cache.py`、幣別自報（`declared_profile.py`）。【I】取消的是「**用它們當搜尋入口**」，不是取消它們在 NAV／meta／配息取數鏈的角色；本批不動。

## 1.5 Identity 現況

- 【F-重驗】`shared/fund_identity.py::DG2_SHADOW_ENABLED = False`（啟用需另一次 Gate）。
- 【F-轉述】`services/fund_identity.py::resolve_fund_identity`：只在已驗證 mapping 命中才剝後綴；FundClear `AGIF-HT5` 不剝；shadow hook 只在 `fund_keys.resolve_full_keys` 且 flag 關時不 import；**生產路徑不經 resolver**。
- `split("-")` 實證：`repositories/fund/sources.py::canonicalize_moneydj_url` 只對行動版／mobile 樣式網址（如 `m.moneydj.com`、`/mobile/b1.aspx`）切第一個 `-` 之前，未驗證 mapping；稽核組實測 `m.moneydj.com/a1.aspx?a=ACDD01-EQTAL005` 得 `?a=ACDD01`，桌面 chubb 頁 `wr01.djhtm?a=ACDD01-EQTAL005` 原樣不切【F-重驗（稽核組）】。其餘子句【F-轉述】：`fund_keys.resolve_full_keys` 保留 `ACDD01-EQTAL005` 不剝 → 同輸入舊頁與新頁 key 不同（稽核組也已重驗 `resolve_full_keys(['ACDD01-EQTAL005'])` 回 full_key 原樣、`mapping_hit=False`）；`docs/v2/70` DG-2 §10 缺陷 B 的 `full_key.split("-")[-1]` 已拔除。
- 持倉鍵 `(policy_id, fund_code)`，跨保單同基金不合併【F-轉述】。
- 別名表 `_DEFAULT_MAPPING`（`ACTI171→ACTI71` 等；【F-重驗】`services/fund_identity.py` 內存在該名稱）是否為 resolver 的正式輸入＝`DEC-2026-10-29-01` 未定（轉述）。

## 1.6 候選池／觀察清單／寫入面【F-轉述】

- `repositories/pool_repository.py::GoogleSheetsPoolStore` 已有 writer，寫入呼叫點只在舊 UI `switch_advisor_section.py` 與 `scripts/fill_pool_currency.py`；ui_v2 以 AST 守衛擋寫入。
- 觀察清單存 user_setting 鍵 `exp_watchlist`（與選股池不同儲存位置）；另有 `scripts/weekly_switch_notify.py` 讀公開 CSV 觀察代號（第三來源）。
- 客戶 2026-09-06 永久授權：查詢／搜尋功能一律唯讀、禁止反向寫入 Sheet。

## 1.7 守衛缺口【F-轉述；ACTI97 部分本組重驗】

沒有任何測試守「ISIN 只能 alternate lookup、對不到顯示 Missing、不得名稱模糊」，也沒有 ACTI97 的測試。

## 1.8 盤點總表：可 reuse／要 replace／與裁示衝突／舊語意／尚缺 contract

| # | 項目（檔案::符號） | 分類 | 說明 |
|---|---|---|---|
| 1 | `services/moneydj_fetcher.py::auto_fetch_moneydj` | **可 reuse** | MoneyDJ code 取數；是否算「新來源」見 G-E3 |
| 2 | `services/moneydj_fetcher.py::normalize_manual_fund_input` | **可 reuse（有條件）** | 裸碼 strip＋upper、網址抽碼；**不含 ISIN 分流**，需在它**之前**先分流 |
| 3 | `repositories/fund/sources.py::parse_moneydj_input` | **可 reuse（有條件）** | 【F-重驗】會把 ISIN 原樣當 code；不可直接面對使用者輸入 |
| 4 | `services/v2_tables/fund_keys.py::resolve_full_keys` | **可 reuse（有條件）** | 保留帶後綴字串不剝（符合不猜）；`_is_pure_code` 放行 ISIN 格式 |
| 5 | `services/v2_tables/exp_nav.py`／`exp_profile.py` | **可 reuse（待查）** | 現為「選股池 code」母體的 NAV／基本資料；池外代碼直查見 G-E6 |
| 6 | `services/fund_identity.py::resolve_fund_identity`＋`shared/fund_identity.py::DG2_SHADOW_ENABLED` | **尚缺正式 contract** | 只有 shadow，flag 關；ISIN→canonical 沒有對照來源（G-E1、G-E4） |
| 7 | `pool_repository.PoolEntry.isin`／`resolve_isin` | **尚缺正式 contract** | 手填欄、單向 code→ISIN，不是反查來源；`exp_universe` 刻意不讀（G-E1 方案 B） |
| 8 | `ui_v2/exp/page.py` EXP-1～7 篩選器 | **保留不動** | 不是搜尋入口；本批不動、不刪（IA 題見 §2.6） |
| 9 | `services/fund_search.py::search_funds`、`sources.py::tdcc_search_fund(_with_error)` | **與裁示衝突（入口用途）** | 名稱／TDCC／FundClear 搜尋；新入口不得呼叫；舊樹仍在用（G-E7） |
| 10 | `fund_orchestration.py::search_fundclear`／`search_moneydj_by_name` | **與裁示衝突** | 名稱路徑 |
| 11 | `services/fundclear_backfill.py::rank_candidates`／`find_fund_candidates` | **與裁示衝突** | difflib 模糊；非窮舉 |
| 12 | `sources.py::_cnyes_search`、`_morningstar_search_secid`（取 `results[0]`） | **與裁示衝突** | 名稱橋接／取第一筆（`docs/v2/69` G-ID-3） |
| 13 | `ui/helpers/fund_research/code_finder.py`、`ui/views/page_03_research.py`（含 `DIRECT_LABEL`） | **只是舊 UI 舊語意** | 舊樹；「任意輸入原封當代碼」是舊語意，不得搬進新入口 |
| 14 | `services/fund_search.py::search_funds` 空清單語意（`EMPTY_MEANS_UNKNOWN`） | **舊語意（教訓）** | 分不出查無與取不到；新入口須分開（§2.4） |
| 15 | ISIN→MoneyDJ code deterministic 對照 | **尚缺正式 contract（無來源）** | repo 查無；G-E1 |
| 16 | 「ISIN／ACTI97／不得名稱模糊」守衛測試 | **尚缺** | 實作批須補（本批不寫） |
| 17 | TDCC／FundClear 的 NAV／meta／配息後端 | **保留（非搜尋用途）** | 裁示未取消；本批不動 |

---

# 第 2 部分｜最小文字線框（~~⛔ 待客戶審批~~ → 2026-11-01 客戶核准（S6 修字後）；只動 UI 結構，不改 Domain 語意）

> **狀態（2026-11-01 客戶裁示，`DEC-2026-11-01-02`；決策者：客戶；狀態更新，不是漏刪）**：本部分**原則核准**；S6 字樣依客戶修正（見 §2.4 S6）後**視為正式核准**，可進下一實作批。**ISIN 採「尚未啟用」版本（§2.4 S5 版本乙）為現行**；版本甲（§2.2／§2.3 與 S4 所畫的「ISIN 對照來源已核准」樣式）**僅待 G-E1 來源經 Source／Identity Decision Gate 核准後啟用**——不得因 UI 已畫出 ISIN 就假裝後端已具備 identity resolution。**輸入框採單一輸入框（X）**；格式辨識只表示「輸入類型」，不表示 canonical identity 已確認。**IA 採同頁上下（P）**：上方「找一檔基金」、下方既有 EXP 篩選器原樣保留並明確分隔，**不加頁內分頁**。本部分其餘「擬：」字樣是否已隨原則核准一併定字，客戶原文未逐字點名，本檔不判（執行組讀法，可被客戶推翻）。

## 2.0 設計約束（引用裁示，不新增規則）

- 只有兩種輸入類別：MoneyDJ 基金代碼、ISIN。**不畫**：名稱搜尋框、來源切換、AI 配對／推薦、星等／排名／Top N、寫入清單的按鈕、大型 Screener。
- 流程：**輸入 MoneyDJ Code 或 ISIN → 找到基金 → 核心基金資料 → 比較／後續操作**。
- Presentation 沿用 44 之十九：**圖表 ＞ 數字 ＞ 短句 ＞ 長文字**；Missing／Error 原因優先於為塞圖隱藏。
- 每一格都明確 Missing／來源／`as_of`。「加入對照」**僅 session-only**，不寫入任何清單、不碰 `exp_watchlist`、不碰 Google Sheet。
- ISIN 格式分流（例：2 個英文字母＋9 碼英數＋1 位檢查碼）**只是輸入類別判斷，不是身份解析**；身份解析在資料層。

## 2.1 輸入框兩案（【R】推薦其一）

| 方案 | 做法 | 優點 | 缺點 | 風險 |
|---|---|---|---|---|
| **X｜單一輸入框＋依格式分流** | 一個框，提示「MoneyDJ 基金代碼或 ISIN」；格式像 ISIN 走 ISIN 分支，其餘走代碼分支 | 第一屏最省空間（手機首屏友善）；符合「單一入口」直覺 | 格式相似時需靠分流規則（例如 12 碼英數但不符 ISIN 結構）；使用者看不出自己被當成哪一類 | 分流規則錯誤會把 ISIN 當代碼取數（§1.3 已實證放行）；**必須在輸入下方回顯「輸入類型：‹代碼型字串／ISIN 格式›（原值未改寫）」＋「基金身份：◇ 尚未確認」**以避免靜默誤判（字樣依客戶 2026-11-01 裁示修正，見 §2.4 S6） |
| **Y｜兩個分頁式輸入**（「MoneyDJ 代碼」「ISIN」） | 使用者先選類別再輸入 | 類別由人選，**不需格式分流**；錯放時可直接報「這不是有效 ISIN 格式」 | 多一次點擊；手機第一屏多一列分頁；ISIN 分頁在 G-E1 未裁示時是整頁「尚未啟用」 | 兩個分頁讓人誤以為對等；主入口與 alternate 的主從關係須用版面（分頁順序、預設分頁）表達 |

**客戶裁示：採 X（見 `DEC-2026-11-01-02`；2026-11-01，客戶）。** **總管推薦：X（單一輸入框＋回顯辨識類別）。** 理由：(1) 裁示把代碼定為**主**入口、ISIN 為 alternate，單一輸入框最貼近主從語意；(2) 手機 390px 首屏預算吃緊；(3) 風險（分流誤判）用「回顯已辨識類別＋分流在進入 resolver 之前、格式不確定時不猜、回報『無法辨識輸入格式』」可控。若客戶認為「不要靠格式猜」優先於「省一次點擊」，改選 Y。此推薦可被客戶推翻。

## 2.2 桌機線框（1280×800；方案 X；G-E1「來源已核准」版）

> 2026-11-01（`DEC-2026-11-01-02`）：本圖為**版本甲**，僅待 G-E1 來源核准後啟用；**現行為 S5 版本乙**（ISIN 尚未啟用）。MoneyDJ 代碼入口與結果卡結構照本圖。

```
┌────────────────────────────────────────────────────────────────┐
│ 🔍 找基金　擬：用 MoneyDJ 基金代碼或 ISIN 找一檔基金              │ ← 頁名＋提問句（擬字）
│ ‹資料截至 MM-DD›                                                │ ← 頁首資料狀態（沿用既有）
├────────────────────────────────────────────────────────────────┤
│ ┌──────────────────────────────────────────┐ ［查詢］           │
│ │ ‹輸入：MoneyDJ 基金代碼 或 ISIN›           │                   │ ← 單一輸入框
│ └──────────────────────────────────────────┘                   │
│ 輸入類型：‹代碼型字串／ISIN 格式／無法辨識›（原值未改寫）         │ ← 分流回顯（只是格式判斷）
│ 基金身份：‹◇ 尚未確認｜canonical MoneyDJ 代碼›                   │ ← 只有正式 identity resolution 確認後才顯示 code
├────────────────────────────────────────────────────────────────┤
│ 結果卡                                                          │
│ ┌────────────────────────────────────────────────────────────┐ │
│ │ ‹基金名稱›                                  ［加入對照］   │ │ ← 僅 session-only
│ │ MoneyDJ 代碼 ‹CODE›　　ISIN ‹ISIN｜⬜ 無 ISIN 資料›          │ │
│ │ 類別 ‹…｜◇ 資料未備›　幣別 ‹…｜◇ 資料未備›                    │ │
│ │ 來源 ‹…›　資料日 ‹MM-DD›                                     │ │
│ │ 主要比較視覺：淨值走勢（歸一化，起點＝1）                      │ │
│ │   1.0 ┤ ╭──╮ ‹本檔›                                           │ │
│ │       ┤─╯  ╰─  ‹對照檔（加入後出現）›                         │ │
│ │       └──────────────────────────  ‹起日›～‹迄日›（as_of）    │ │
│ │ ▸ 為什麼／來源／限制／去哪補                                   │ │
│ └────────────────────────────────────────────────────────────┘ │
├────────────────────────────────────────────────────────────────┤
│ 對照（session-only；關閉頁面即消失；不寫入任何清單）               │
│ ‹對照檔名稱›　［移除對照］                                       │
├────────────────────────────────────────────────────────────────┤
│ ▸ 尚未取得（點名缺的項目）                                       │
│ 頁尾一句（擬）：此頁不產生推薦或排名。                            │
└────────────────────────────────────────────────────────────────┘
```

> 上框「主要比較視覺：淨值走勢（歸一化，起點＝1）」與縱軸「1.0」：→ 2026-11-02 起 New UI2 歸一化基準＝100（`DEC-2026-11-02-07` UI-13 A；原字保留，狀態更新，不是漏刪）。

要點：第一屏只有輸入框、辨識回顯、結果卡（名稱／代碼／ISIN／類別／淨值走勢）。「加入對照」第二檔後，同一張圖畫兩條歸一化曲線，**不做排名、不顯示誰比較好**。圖表區的時間窗口、歸一化起點（＝1）與 `as_of` 一律標在圖下。（→ 2026-11-02 起 New UI2 歸一化基準＝100（`DEC-2026-11-02-07` UI-13 A；原字保留，狀態更新，不是漏刪））

## 2.3 390px 手機線框（單欄；方案 X）

```
┌────────────────────────────┐
│ 🔍 找基金                  │
│ 擬：輸入代碼或 ISIN        │
│ ┌────────────────────────┐ │
│ │ ‹MoneyDJ 代碼或 ISIN›  │ │
│ └────────────────────────┘ │
│ ［查詢］ 輸入類型：‹類別›  │
│ 基金身份：◇ 尚未確認       │
├────────────────────────────┤
│ ‹基金名稱›    ［加入對照］ │
│ 代碼 ‹CODE›                │
│ ISIN ‹ISIN｜⬜ 無 ISIN›    │
│ 類別 ‹…｜◇ 資料未備›       │
│ 淨值走勢（起點＝1）        │
│  ╭──╮                      │ ← 圖在首屏內（設計值）
│ ─╯  ╰──   ‹起›～‹迄›       │
│ 來源 ‹…›  資料日 ‹MM-DD›   │
│ ▸ 為什麼／來源／限制       │
├────────────────────────────┤
│ ▸ 對照（session-only）     │
│ ▸ 尚未取得                 │
└────────────────────────────┘
```

> 上框「淨值走勢（起點＝1）」：→ 2026-11-02 起 New UI2 歸一化基準＝100（`DEC-2026-11-02-07` UI-13 A；原字保留，狀態更新，不是漏刪）。

要點：390px 單欄；表格若有則橫向捲動，**頁面本身不水平捲動**。圖在結果卡的第三、四行（設計值，不是量測值；實作後須以 Visual Fidelity 實測，本檔不提議改任何 V7／Visual Budget 門檻）。

## 2.4 必畫狀態

> 以下每個狀態用既有符號與既有語意；本節的畫面字句皆為「擬」，待客戶定字。桌機與手機同構，手機只把卡片疊成單欄。

**S0 初始空白**
```
┌────────────────────────────────────────────┐
│ ┌────────────────────────────────┐［查詢］  │
│ │ ‹MoneyDJ 基金代碼或 ISIN›       │          │
│ └────────────────────────────────┘          │
│ 擬：輸入 MoneyDJ 基金代碼（例 ACTI97）或 ISIN │
│ （沒有結果卡、沒有圖；不顯示任何預設基金）     │
└────────────────────────────────────────────┘
```

**S1 找到**：即 §2.2／§2.3 的結果卡。

**S2 查無（MoneyDJ 代碼取不到，但來源有回應）與 S3 取數失敗（⛔）——必須分開，不得合併**
```
S2 查無（來源有回應、確認沒有這個代碼）
┌────────────────────────────────────────────┐
│ ⬜ 查無：MoneyDJ 沒有代碼 ‹輸入›              │
│ 來源 ‹…›　查詢時間 ‹MM-DD HH:MM›              │
│ ▸ 為什麼／來源／限制                         │
└────────────────────────────────────────────┘
S3 取數失敗（來源沒回應或回應不可用）
┌────────────────────────────────────────────┐
│ ⛔ 取數失敗：‹來源›　‹原因：逾時／403／解析失敗›│
│ 這不代表基金不存在。　［重試］                  │
│ ▸ 為什麼／來源／限制                         │
└────────────────────────────────────────────┘
```
【F-轉述】依據：既有 `EMPTY_MEANS_UNKNOWN`（`services/fund_search.py`）與 `docs/v2/62` CAP-FND-06：空結果分不出「查無」與「取不到」，在改用 `_with_error` 或等效路徑前，**空結果一律顯示「無法判定」，不得說『不存在』**。【I】因此新入口若**沒有**能分辨二者的取數路徑，S2 不得畫成「查無」，只能畫「無法判定」；S2 與 S3 的區分**是一個前置條件，不是 UI 裝飾**（實作批須先確認既有取數鏈能否分辨，見 §3 G-E3）。（→ 已裁示，見 `DEC-2026-11-01-02` G-E3：須先驗證既有取數鏈能否區分「查無基金」與「上游取數失敗」；無法可靠區分時不得顯示「不存在／查無」，只能顯示既有「無法判定／取數失敗」；2026-11-01，客戶）

**S4 ISIN 無法可靠對應（G-E1「來源已核准」時）**
```
┌────────────────────────────────────────────┐
│ ◇ 無法判定：ISIN ‹ISIN› 未能可靠對應 MoneyDJ 基金代碼│
│ 來源（對照用）‹…›　as_of ‹MM-DD›　狀態：unresolved   │
│ 不顯示任何猜測候選。                           │
│ ▸ 為什麼／來源／限制／去哪補                  │
└────────────────────────────────────────────┘
```
保留 provenance 與 unresolved；**不畫**「你是不是要找…」候選、不用名稱模糊、不用 AI。

**S5 G-E1 未裁示前的誠實狀態（需畫兩版）**

> 2026-11-01 G-E1 已裁示（採 A＋C，`DEC-2026-11-01-02`）：**版本乙為現行**；版本甲僅待 ISIN 對照來源另走 Source／Identity Decision Gate 核准後啟用。

版本甲｜**ISIN 對照來源已核准時**：S1／S4 如上，輸入框說明列寫「MoneyDJ 基金代碼或 ISIN」。

版本乙｜**ISIN 對照來源未核准時**：
```
┌────────────────────────────────────────────────────┐
│ ┌────────────────────────────────┐［查詢］          │
│ │ ‹MoneyDJ 基金代碼›              │                  │
│ └────────────────────────────────┘                  │
│ ISIN：⬜ 尚未啟用：目前沒有已核准的 ISIN 對照來源      │ ← 輸入說明改寫；不假裝能查
│ （若使用者仍貼入 ISIN 格式字串）                       │
│ ⬜ 尚未啟用：目前沒有已核准的 ISIN 對照來源；未用      │
│    ISIN 取數、未猜測任何代碼                           │
└────────────────────────────────────────────────────┘
```
版本乙在方案 Y 下＝ISIN 分頁整頁顯示「尚未啟用」；在方案 X 下＝輸入說明列與分流回顯改寫，貼入 ISIN 時**不進 resolver、不進取數**，回報如上。【R】兩版由 G-E1 的裁示決定哪一版上線，**不可兩版並存地假裝都能查**。（→ 已裁示，見 `DEC-2026-11-01-02`：版本乙現行、版本甲待來源核准；2026-11-01，客戶）

**S6 輸入像 `ACDD01-EQTAL005` 的帶後綴字串**
```
┌────────────────────────────────────────────────────┐
│ 輸入類型：代碼型字串（原值未改寫）                     │
│ 基金身份：◇ 尚未確認                                   │
│ ◇ 無法判定：‹原值› 未能對應已驗證的基金身份            │
│ 顯示原值＋unresolved；未拆分、未猜測                    │
│ ▸ 為什麼：不依 "-" 切字串；只有已驗證對照才會剝後綴      │
└────────────────────────────────────────────────────┘
```
字樣修正（客戶 2026-11-01 裁示，`DEC-2026-11-01-02`；有意識的更正，不是漏刪；決策者：客戶）：原線框首行 ~~「已辨識為：‹MoneyDJ 代碼（原值，未改寫）›」~~ 容易讓人誤以為 identity 已經確認，改為「輸入類型：代碼型字串（原值未改寫）」，並另一行顯示「基金身份：◇ 尚未確認」。**只有經正式 identity resolution 確認後，才能顯示 canonical MoneyDJ code；不得用 `split("-")[0]`。** 舊字在寫下當時的用意（回顯分流結果）仍成立；被修正的是它暗示「身份已確認」。本檔其餘「已辨識為」回顯一併直接改為「輸入類型」＋「基金身份」兩行。

處置：不 `split("-")`、不 `split("-")[0]`；依既有 resolver 規則（只在已驗證 mapping 命中才剝後綴）顯示原值＋unresolved；resolver 未啟用（`DG2_SHADOW_ENABLED = False`，G-E4）時一律顯示原值＋「尚未判定身份」，**不補、不猜**。

**S7 無法辨識輸入格式**（例：非代碼格式也非 ISIN 結構）
```
│ 輸入類型：⬜ 無法辨識（既不是 MoneyDJ 代碼格式，也不是 ISIN 結構）│
│ 未查詢任何來源。                                                │
```

## 2.5 明確不畫（核對裁示的取消清單）

名稱搜尋框、來源 selectbox／來源切換、AI 配對／AI 推薦、星等／排名／Top N／AI score、寫入觀察清單／候選池／Sheet 的按鈕、大型 Screener（本批的第一屏不放條件列）。

## 2.6 與既有頁的關係（IA 題；~~【R】待客戶審批~~ → 已裁示採 P，見 `DEC-2026-11-01-02`）

現有 `ui_v2/exp` 篩選器（EXP-1～7）本批不動、不刪。新入口放在哪：

| 方案 | 做法 | 優點 | 缺點 | 風險 |
|---|---|---|---|---|
| **P｜同頁上下關係**：新入口放 🔍 頁最上方（EXP-0 之前），篩選器在其下 | 同一個 `ui_v2/exp` 頁、單一頁名；使用者一頁看到「找一檔」與「篩選一批」 | 不新增頁籤；與頁名「找基金」語意貼合；既有篩選器零改動 | 第一屏被新入口占去，篩選器被推到第一屏下方；頁變長；兩種心智模型（找一檔／篩一批）疊在同頁 | 新入口的結果卡與 EXP 的母體（選股池）資料來源不同，使用者可能誤以為結果卡來自選股池；須在卡上標「來源」與「不來自選股池」（G-E6） |
| **Q｜並列（頁內兩個分頁）**：「找一檔」「篩選」 | 同頁兩分頁，各自完整 | 兩種心智模型分開；篩選器不被推下去 | 多一層分頁；手機底部導覽已有 4 頁，頁內分頁再加一層；改動 `ui_v2/exp/page.py` 的版面結構 | 動到既有頁結構，更接近「舊 UI 大規模搬運」；與本批「EXP 不動」的範圍較不一致 |

**總管推薦：P（同頁上下）**，但**新入口與 EXP 篩選器之間以明確分隔標題分開**，EXP 區原樣下移、不改內容。理由：(1) 本批範圍是「EXP 不動」，P 只在其前新增一區；(2) 避免在頁內再增一層分頁；(3) 結果卡明標來源，降低與選股池混淆。若客戶認為「找一檔」應是獨立入口，改選 Q。**這是 IA 題，須客戶審批，審批前不寫程式。**（→ 已裁示，見 `DEC-2026-11-01-02`：採 P 同頁上下；上方「找一檔基金」（MoneyDJ code／ISIN、結果卡、主要視覺、session-only comparison），下方既有 EXP 篩選器原樣保留、明確分隔、本批不重新設計；不再加一層頁內分頁；2026-11-01，客戶）

## 2.7 資料流與層次（只畫箭頭與責任，不設計 contract）

```
輸入（使用者）
  │
  ▼
[輸入分流]            只判斷「像代碼／像 ISIN／都不像」；不解析身份；
  │                   ISIN 不得流進「代碼取數」路徑（§1.3 實證）
  ├── 像 MoneyDJ 代碼 ───────────────┐
  └── 像 ISIN（G-E1 核准前：停在此，回「尚未啟用」；G-E1 已裁 A＋C：來源另走 Source／Identity Gate 核准前一律停在此）
        │
        ▼
[Identity resolution]  資料層；deterministic、traceable；
  │                    輸出 canonical MoneyDJ code ＋ provenance；
  │                    對不到 → unresolved（不猜、不名稱模糊、不用 AI）
  ▼
canonical MoneyDJ code
  │
  ▼
[既有取數鏈]  NAV／meta；來源與 as_of 外露；備援旗標外露（G-E3）
  │
  ▼
[呈現]  結果卡＋淨值走勢＋Missing／來源／as_of；session-only 對照
```
**AI 不在鏈中。** 層次責任（【I】，只畫責任，不設計 contract）：輸入分流屬 UI 之前的純格式判斷；identity resolution 與取數屬資料層（`services/`／`repositories/`）；`ui_v2` 只經 `<頁>/source.py` 取得結果（沿用既有 import 守衛）；全程唯讀。

---

# 第 3 部分｜~~待客戶裁示 G-E1～G-E7~~ → 已裁示（`DEC-2026-11-01-02`）、IA 題與線框審批

> 以下每項「總管推薦」都**不是已決定**，一律可被客戶推翻。
>
> **2026-11-01 狀態更新（不是漏刪；決策者：客戶）**：G-E1～G-E7、IA 題、輸入框形式與線框審批**已全部由客戶裁示**，見 `docs/DECISIONS.md` `DEC-2026-11-01-02`；各項「客戶裁示」行加在總管推薦之前，原推薦與方案表保留原字。

## G-E1｜ISIN→MoneyDJ 代碼對照的資料來源

- **問題**：ISIN 入口要有一個「可靠、deterministic、可追溯」的 ISIN→MoneyDJ code 對照；repo 目前沒有。裁示要求新來源前先過 Decision Gate。
- **現況事實**：【F-轉述】repo 查無 deterministic 對照；`PoolEntry.isin` 是手填單向；TDCC／FundClear 回應是否含 ISIN 欄查無；持倉／保單 Sheet 無 ISIN 欄。【F-重驗】`exp_universe` 檔頭刻意不讀 `isin`。

| 方案 | 優點 | 缺點 | 風險 |
|---|---|---|---|
| **A**｜先上線 MoneyDJ 代碼入口；ISIN 入口誠實「尚未啟用」，另開研究批找已核准來源 | 不引入未核准來源；主入口可先用；符合 Source ≠ Identity | ISIN 入口暫時不能用 | 低；使用者期待落差須以「尚未啟用」字樣誠實說明 |
| **B**｜沿用選股池 `isin` 欄做反查 | 不新增外部來源 | 手填、覆蓋面不明、只涵蓋已在池內的基金；`exp_universe` 刻意不讀 `isin`，改讀需動母體語意；與 `DEC-2026-10-29-01`「不改 Sheet schema」的關係待確認（本方案不新增欄位，但新增「讀」是否也屬需裁示範圍，本檔不判） | 中；把「手填欄」當對照來源，等於把使用者輸入當身份來源，且一對多／錯填無驗證 |
| **C**｜研究 TDCC／MoneyDJ 頁面是否本身含 ISIN 欄 | 若有，可成為 deterministic 對照 | 僅是 Research，**不等於導入**；結果不確定；需查證打網路行為與條款 | 低（研究）；導入時另走 Gate |

**客戶裁示（2026-11-01，客戶）：採 A＋C（見 `DEC-2026-11-01-02`）：MoneyDJ code 主入口可先實作；ISIN 入口保留但顯示「尚未啟用／目前沒有已核准的 ISIN 對照來源」，不進 MoneyDJ resolver、不進取數鏈、不用名稱搜尋補、不用 AI 猜；C 另開 research-only（`docs/BACKLOG.md` BL-0530），research 不等於導入，找到候選後另走 Source／Identity Decision Gate；**不得使用選股池手填 `isin` 欄作正式 identity authority**（方案 B 不採）。** 以下總管推薦保留原字：

**總管推薦：A＋C。** 理由：A 讓主入口立即可用且不新增未核准來源；C 在不導入的前提下回答「有沒有可靠來源」。B 不推薦（身份來源不應是手填欄）。

## G-E2｜ISIN 對到多個 code／與同時輸入 code 不一致的規則

- **問題**：一個 ISIN 若對到多個 MoneyDJ code（例如不同通路／級別），或使用者同時提供 code 與 ISIN 而二者不一致，系統怎麼處置。
- **現況事實**：【F-轉述】`resolve_fund_identity` 只在已驗證 mapping 命中才剝後綴；沒有「多對一」的正式規則。

| 方案 | 優點 | 缺點 | 風險 |
|---|---|---|---|
| **A**｜對到多個 code 或與輸入 code 不一致 → 一律 unresolved，顯示全部候選的**原值**（不排序、不推薦、不選第一筆） | 不猜；最保守 | 可能讓使用者多一步 | 低；但「顯示候選」不得變成推薦，須只列事實 |
| **B**｜對到多個 code → 依固定優先序選一個 | 少一步 | 優先序本身是新規則＝source precedence，須另裁示；易被讀成猜 | 高，且觸及 identity／source precedence |
| **C**｜只接受 ISIN 或 code 單一輸入，不接受同時輸入 | 規則最簡單 | 限制使用情境 | 低 |

**客戶裁示（2026-11-01，客戶）：採 A＋C（見 `DEC-2026-11-01-02`）：一個 ISIN 對到多個 MoneyDJ code → unresolved；code 與 ISIN 互相衝突 → unresolved；不自動選第一筆、不設定猜測型優先序、不排名候選、不用 AI 決定；可列可驗證的原始候選事實供查看，但不得代替客戶選定 canonical identity；UI 採單一輸入，正常互動不要求同時輸入 code＋ISIN，衝突規則保留給資料匯入、mapping 或未來 contract。** 以下總管推薦保留原字：

**總管推薦：A＋C。** 理由：符合「無法可靠對應就不猜」；B 引入新 precedence，屬 identity／source precedence，另需 Model／Effort Gate（第 4 部分）。

## G-E3｜MoneyDJ code 直查是否沿用既有 production 取數鏈（即不算新來源）＋備援旗標揭露

- **問題**：新入口的代碼直查若沿用 `auto_fetch_moneydj` 與既有 NAV／meta 取數鏈，是否視為「沒有新增資料來源」；取數鏈中出現備援（fallback chain，例如 MoneyDJ→TDCC→FundClear→Cnyes）時，結果卡是否要揭露備援旗標。
- **現況事實**：【F-轉述】舊 ③ 模式 A 已有此取數鏈；§1 Fail Loud 要求備援須保留來源旗標。【F-重驗】`services/moneydj_fetcher.py::auto_fetch_moneydj` 存在。**本組未查證**取數鏈能否分辨「查無」與「取不到」（S2／S3 的前置條件）。

| 方案 | 優點 | 缺點 | 風險 |
|---|---|---|---|
| **A**｜沿用既有鏈，不算新來源；結果卡一律外露實際命中來源與是否為備援 | 不新增來源；符合 §1／Source ≠ Identity | 需確認鏈能回報命中來源 | 低 |
| **B**｜沿用既有鏈，但備援命中時只顯示結果、不揭露旗標 | 畫面較乾淨 | 違反「保留來源旗標」 | 高；不符 §1 |
| **C**｜新入口另建專用取數路徑 | 可針對搜尋最佳化 | 屬新來源／新路徑，須走 Gate | 高 |

**客戶裁示（2026-11-01，客戶）：採 A（見 `DEC-2026-11-01-02`）：沿用既有 MoneyDJ／NAV／meta production 取數鏈＝既有來源 reuse、不構成新增 source；須外露實際命中來源、fallback 時外露 fallback／source flag、保留 provenance 與 as_of；先驗證既有鏈能否區分「查無基金」與「上游取數失敗」，無法可靠區分時不得顯示「不存在／查無」，只能顯示既有「無法判定／取數失敗」。** 以下總管推薦保留原字：

**總管推薦：A。** 理由：最小必要變更；並把「鏈能否分辨查無與取不到」列為實作批的前置查證（本檔 §2.4 S2／S3）。

## G-E4｜Shadow resolver 是否隨入口啟用（Stage-2，BL-0521）

- **問題**：`DG2_SHADOW_ENABLED` 預設 `False`；新入口要不要同時啟用 shadow resolver。
- **現況事實**：【F-重驗】`shared/fund_identity.py::DG2_SHADOW_ENABLED = False`；【F-轉述】啟用需另一次 Gate、生產路徑不經 resolver。

| 方案 | 優點 | 缺點 | 風險 |
|---|---|---|---|
| **A**｜本批不啟用；入口對帶後綴字串顯示原值＋unresolved（§2.4 S6） | 不改 identity 行為；範圍最小 | ISIN 入口（G-E1 核准後）缺少正式 resolver 可用 | 低 |
| **B**｜隨入口啟用 shadow | 入口一次到位 | 啟用會改變 key 行為，與舊頁並存（舊頁與新頁 key 不同）；屬 identity 政策 | 高；須另走 Gate 與 Model／Effort Gate |

**客戶裁示（2026-11-01，客戶）：採 A（見 `DEC-2026-11-01-02`）：本批不啟用 `DG2_SHADOW_ENABLED`；不因 Batch E 順手進入 Stage-2 identity migration；帶後綴或無法驗證 identity 的輸入保持原值＋unresolved。** 以下總管推薦保留原字：

**總管推薦：A。** 理由：裁示本身不要求啟用；啟用屬 BL-0521 Stage-2 另案。

## G-E5｜是否開 44 amendment

- **問題**：「找基金」第一屏流程（輸入→結果卡→比較）與 44 之十九／之二十既有 IA 條文是否需要一則 amendment（例如：新增「結果卡」元件定位、session-only 對照的呈現約束）。
- **現況事實**：44 的條文本組未重讀全文；`docs/v2/72`、`73`、`76` 的先例是「線框經客戶核准後登記於 DEC，不另改 44」，但是否適用本批須客戶判斷。

| 方案 | 優點 | 缺點 | 風險 |
|---|---|---|---|
| **A**｜不開 amendment；線框＋DEC 即為依據，與 72／73／76 一致 | 最小；不增文件 | 若新元件確實超出 44 既有條文，之後可能補洞 | 低 |
| **B**｜開 amendment，把「搜尋結果卡」「session-only 對照」寫進 44 | 條文化 | 屬治理文件變更，需客戶頒布與獨立稽核 | 中 |

**客戶裁示（2026-11-01，客戶）：採 A（見 `DEC-2026-11-01-02`）：目前不修改 frozen `docs/v2/44`；以 DECISION、本 wireframe、evidence、BACKLOG／HANDOFF 完成正式紀錄；若後續實作證明新元件與 44 正式條文真的衝突，再另開 amendment Gate。** 以下總管推薦保留原字：

**總管推薦：A。** 理由：本批元件都落在 44 之十九既有原則（圖表＞數字＞短句＞長文字、Missing／Error 原因優先）內；若客戶審批線框時認為有超出，再轉 B。（此判斷是讀法，本組未逐條對照 44 全文。）

## G-E6｜池外代碼直查

- **問題**：現有 🔍 頁母體＝選股池 code 欄；新入口輸入的 MoneyDJ 代碼可能不在選股池。結果卡是否允許池外代碼。
- **現況事實**：【F-轉述】`load_pool_codes` 只取 code；`fund_keys.resolve_full_keys` 的輸入是代碼清單；ui_v2 全程唯讀。

| 方案 | 優點 | 缺點 | 風險 |
|---|---|---|---|
| **A**｜允許池外直查，唯讀，結果卡標「不在選股池」，不寫入池 | 符合「找基金」本意；不新增 writer | 需確認 `exp_nav`／`exp_profile` 能對池外代碼取數；母體語意與 EXP 不同 | 中；須明標，避免與選股池混淆 |
| **B**｜只允許池內代碼 | 與 EXP 母體一致；零新取數 | 失去「找基金」的主要價值 | 低，但幾乎抵銷本批目的 |

**客戶裁示（2026-11-01，客戶）：採 A：允許（見 `DEC-2026-11-01-02`）：既有 production 取數鏈可查即允許唯讀查詢；不自動加入選股池、不自動加入觀察清單、不寫 Google Sheet、不因查到基金就改候選池；UI 必須清楚區分「單檔查詢結果」與「選股池」（2026-11-02 重申補：亦不得自動加入我的資產、不得自動寫 watchlist）。** 以下總管推薦保留原字：

**總管推薦：A。** 理由：裁示要的是「用代碼找一檔基金」；池外標示可控。

## G-E7｜舊樹入口處置

- **問題**：舊樹仍有名稱／TDCC／FundClear 搜尋入口（`ui/helpers/fund_research/code_finder.py`、`ui/views/page_03_research.py`、`services/fund_search.py`），與裁示衝突。
- **現況事實**：【F-轉述】舊 UI 正常運作；客戶另有明令「不得修改現有線上正常運作的舊版 Tab」。

| 方案 | 優點 | 缺點 | 風險 |
|---|---|---|---|
| **A**｜本批不動舊樹；登記為「與裁示衝突的舊語意，待客戶另裁示處置」 | 遵守不得修改舊版 Tab 的明令；零行為變更 | 兩個世界並存一段時間 | 低 |
| **B**｜在舊樹移除名稱／TDCC／FundClear 搜尋入口 | 與裁示一致 | 直接違反「不得修改舊版 Tab」明令，除非客戶另裁示 | 高 |

**客戶裁示（2026-11-01，客戶）：採 A（見 `DEC-2026-11-01-02`）：目前完全不修改正常運作中的舊 UI；舊樹名稱搜尋、TDCC 搜尋入口、FundClear 搜尋入口標記為 legacy／superseded semantics；不因 Batch E 回頭修改或移除舊版 Tab；新版不得搬入這些搜尋入口。** 以下總管推薦保留原字：

**總管推薦：A。** 理由：不動程式；留待客戶對舊樹另有指示時處理。

## 第三部分之外的審批題

- **IA 題**：新入口與 EXP 篩選器的關係（§2.6，P／Q）。**總管推薦 P。**（→ 客戶裁示：採 P，見 `DEC-2026-11-01-02`）
- **輸入框形式**（§2.1，X／Y）。**總管推薦 X。**（→ 客戶裁示：採 X，見 `DEC-2026-11-01-02`）
- **線框審批**：本檔第 2 部分線框是否通過。**通過前不得寫任何 UI 程式；通過後的實作批仍受 G-E1～G-E7 約束**（尤其 G-E1 未裁示前 ISIN 入口只能畫「尚未啟用」版本乙）。（→ 已裁示，見 `DEC-2026-11-01-02`：第 2 部分原則通過，S6 修字後視為正式核准；ISIN 採版本乙；2026-11-01，客戶）

---

# 第 4 部分｜Model／Effort

- **2026-11-01 客戶裁示（`DEC-2026-11-01-02`）**：identity／source Decision（G-E1／G-E2 與相關 contract）落盤用較高設定；落盤完成後，若後續只是既定 UI 實作、測試、文件與 CI 即降回（依 `PROJECT_RULES.md` 5.1；設定名稱見逐字檔）。以下原段保留。
- 本批（現況盤點＋UX 文字線框）：**Sonnet＋Medium 足夠**。
- G-E1（ISIN 來源）、G-E2（一對多規則）、G-E4（shadow resolver）一旦進入 contract 設計，屬 **identity／source precedence**，依 `PROJECT_RULES.md` 第 5 節 5.1（`DEC-2026-10-17-05`）**須先走 Model／Effort Change Gate**。本檔只陳述此條件，**不替客戶升級**。
- 實作批若只是機械式落線框（已核准的 UI 結構、不涉及 contract 設計），可維持 Sonnet＋Medium；這是讀法，由客戶與總管決定。

---

# 第 5 部分｜產出者聲明與未驗證

## 5.1 產出者

文件組單組產出，**未經獨立複驗**。盤點事實大多來自另一組單組唯讀盤點，**本組轉述**。

## 5.2 本組重驗（2026-11-01，main `38a16a4`）

| 事實 | 結果 |
|---|---|
| `ui_v2/exp` 有無 text_input | **有 2 處（`ui_v2/exp/page.py`，`_render_exp1`／`_render_exp1_live`），但都是條件列的運算子／數值欄**，不是代碼／名稱／ISIN 輸入；無 `chat_input`。轉述的「沒有以代碼／名稱／ISIN 為輸入的 text_input」語意成立，字面「沒有 text_input」不成立（已在 §1.1 更正寫法） |
| ui_v2 內有無搜尋鏈呼叫 | `git grep "search_funds\|tdcc_search_fund" -- ui_v2`（`38a16a4`）→ **0 命中** |
| `ACTI97` 在 repo | `git grep ACTI97`（`38a16a4`）→ **0 命中** |
| `DG2_SHADOW_ENABLED` 預設 | `shared/fund_identity.py` → **`False`** |
| `parse_moneydj_input('LU0766462157')`（離線） | 回 `code='LU0766462157'`、`is_url=False`：**ISIN 被當 code 接受** |
| `parse_moneydj_input('ACDD01-EQTAL005')`（離線） | 回 `code='ACDD01-EQTAL005'`（原樣，未切） |
| `fund_keys._is_pure_code`（離線）對 `LU0766462157`／`ACDD01-EQTAL005`／`ACTI97` | 三者皆 **True**：ISIN 格式與帶後綴字串都被放行 |
| `canonicalize_moneydj_url` 對行動版網址 | 本組離線只驗了一個非行動版網址（原樣回傳）；行動版切法已由稽核組重驗（見 §1.5）；其餘未驗範圍照舊 |
| 以下符號／檔案存在 | `services/fund_search.py::search_funds`、`sources.py::tdcc_search_fund`／`tdcc_search_fund_with_error`／`_cnyes_search`／`_morningstar_search_secid`／`canonicalize_moneydj_url`／`parse_moneydj_input`、`fund_orchestration.py::search_fundclear`／`search_moneydj_by_name`、`services/fundclear_backfill.py::rank_candidates`、`exp_universe.py::load_pool_codes`、`fund_keys.py::resolve_full_keys`、`pool_repository.py::resolve_isin`、`ui_v2/readonly.py::WRITE_CONTROLS_ENABLED=False` 與 `PHASE1_HIDDEN_INPUT_CODES`、兩支 ui_v2 守衛測試檔、`exp_nav.py`／`exp_profile.py`／`ui_v2/exp/live.py` |
| `exp_universe.py` 檔頭是否提到不讀 `isin` | 是 |

## 5.3 本組未重驗（轉述）

TDCC／FundClear 回應是否含 ISIN 欄；`rank_candidates`／`find_fund_candidates` 是否有非 tests 呼叫者；舊 UI 各檔的內部呼叫鏈與 `DIRECT_LABEL` 行為；（行動版切法與 `resolve_full_keys` 對 `ACDD01-EQTAL005` 的行為已由稽核組重驗，見 §1.5，不在本清單）；`resolve_fund_identity` 的 mapping 規則與 shadow hook；`_DEFAULT_MAPPING` 內容；持倉鍵 `(policy_id, fund_code)`；`GoogleSheetsPoolStore` 寫入呼叫點清單；`exp_watchlist` 與 `weekly_switch_notify.py`；ui_v2 兩支守衛的具體規則；`ui_v2/exp/live.py` 檔頭文字；44 之十九／之二十的全文。

## 5.4 未驗到的設計面

線框是文字示意，**沒有起 Streamlit、沒有看真實畫面、沒有連任何資料來源**；390px 首屏內容、圖高、點擊數皆為設計值，不是量測值；實作後須以 Visual Fidelity 實測，本檔不提議改任何 V7／Visual Budget 門檻。取數鏈能否分辨「查無」與「取不到」（S2／S3 前置條件）本組未查證。「單一輸入框＋格式分流」的 ISIN 格式判斷規則本檔未定義。

## 5.5 文件測試

`tests/test_doc_counters.py` 的 `_MD_DOCS` 已由落盤組在同批登記本檔（+1 行）；兩支文件守衛的實際結果以總管統一回報為準。
