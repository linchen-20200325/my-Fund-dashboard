# BL-0540 資料健康度集中到 ⚙️：規格差額分析（唯讀；2026-11-20；基準 main `c128a0d8`）

單組產出，未經獨立複驗；非授權、非裁示；登記不構成動工授權。未改任何程式、測試或其他文件。標記：【F】本組讀檔／實跑所見；【I】推論；【R】建議，可推翻。全稱句（「只有」「沒有」）皆為單組判讀，視為待驗。
**方向來源**：#1278 comment 7033251336 §C（本組以 GitHub 讀取確認該則存在且 §C 與轉述一致；性質為使用者對話確認存檔，其自述「非正式 DEC amendment、非 QA」）。不是 DEC。同則明寫：BL-0540 的 UI／規格衝突與可移動清單範圍仍須合法裁示或 amendment。

## 0. 結論
1. 🌍 是目前唯一有實際頁內診斷的頁（`ui_v3/pages/mkt.py`）；💼 為隔離 FAKE renderer（`pages/assets.py`，registry 未掛）；🔍 renderer 住 `poc/`；⚙️ 無 wireframe、無 renderer（`shell/registry.py::IA_PAGES` 的 `set`＝`wireframe_not_approved`；`PROJECT_RULES.md` 索引「尚無 New UI2 wireframe」）。
2. 🌍 真正可「集中」的只有 `▸ 各項資料狀態` 逐列明細（與來源取得時間）；其餘（圖下資料日、缺值短原因、Chart SPEC、`▸ 尚未取得`、依據卡 ◇）屬必要揭露。
3. 【F 實跑】求證結果（§5 R1）：預設比較檢視下，美10Y／美2Y 與 VIX 的來源只在 `▸ 各項資料狀態` 出現；利差／信用／政策利率三個子序列的來源（`FRED (T10Y2Y)` 等）在整頁文字中**完全不出現**。故「現在整塊搬走」會移掉 VIX 卡唯一的頁面來源標示。
4. ⚙️ 資料健康度能誠實顯示的，目前只有 🌍 五序列＋三利率子序列＋七個無來源 domain 的 in-session 狀態；基金／持倉／配息／匯率／景氣沒有可讀的健康度資料來源（§2）。
5. 第一步最小且最安全：只產出 ⚙️ 資料健康度「線框草稿」（docs-only，不動 🌍、不動 registry、不動程式）。

## 1. 現有頁內診斷與揭露清單
分類：**必**＝必要揭露（留該頁）；**集**＝可集中到 ⚙️；**裁**＝待裁示。條款縮寫：44＝frozen `docs/v2/44`；80/81/83/67/79＝`docs/v2/` 同號；PR＝`PROJECT_RULES.md`。
| # | 頁 | 元素（位置：檔:符號） | 內容 | 規格出處 | 類 |
|---|---|---|---|---|---|
| 1 | 🌍 | Shell Status Bar（`pages/chrome.py::status_bar_html`） | PREVIEW＋資料狀態一句＋更新時間（取得時間，非資料日） | 80 §17.2；79 §7.1 | 必（Shell，非頁尾堆疊） |
| 2 | 🌍 | 側欄資料狀態區（`chrome.py::sidebar_status_html`；`adapters/shell_status.py`） | 「n／5 項已取得」＋失敗數＋最後更新 | 80 §17.2／§17.4（分母＝五序列，不得暗示全系統） | 必（⚙️ 層①雛形，不可冒充全站） |
| 3 | 🌍 | 首屏「資料新鮮度 ⬜ 門檻待裁示」（`mkt.py::summary_html`） | 單一 chip，無日期無天數 | 81 §3.1 Q5 B；`DEC-2026-11-03-09` | 必 |
| 4 | 🌍 | 圖下基準日／頻率／缺值不補（`mkt.py::disclosure_notes`） | Chart SPEC 子集 | 80 §16.1；79 §4.4 | 必 |
| 5 | 🌍 | 圖下各序列資料日＋經過天數（`mkt.py::primary_notes_html`） | 日期唯一落點 | 81 §3.1 日期表 | 必 |
| 6 | 🌍 | 圖下非 ok 序列一行摘要（`data-summary="series-status"`） | 缺資料／取數失敗／尚未設定各自字樣 | 81 §4.1 S2–S9；44 之十九其五.2、§5.4（缺什麼收合時看得見） | 必 |
| 7 | 🌍 | 圖卡 `▸ 來源與限制`（`mkt.py::source_limits_html`） | 各序列來源名＋取得時間＋3 句限制 | 81 §3.3 層3；44 之十九其四.4 | 來源名／限制句：必；取得時間：裁（可集中） |
| 8 | 🌍 | Secondary 卡（`mkt.py::_secondary_parts`） | 值＋資料日＋迷你線；`SecondaryCard.source` 有值但**不渲染** | 81 §3.1 | 必（來源缺口見 R1） |
| 9 | 🌍 | 依據卡 MKT-1～3（`mkt.py::fact_html`） | 觀測值＋as_of 或 ◇；無來源 | 81 §4；D4 | 必 |
| 10 | 🌍 | `▸ 尚未取得（N 項）`（`mkt.py::_render`；`adapters/market_page.py::_MISSING_DOMAINS` 7 項） | Missing 名單，一律 ◇ 資料未備 | 81 §4 D4＝β；80 §7.1；79 §11；67 §5.4 | 必（Missing 一項不刪；理由與逐項狀態可集中，名單本身待 Q2） |
| 11 | 🌍 | `▸ 各項資料狀態`（`mkt.py::status_row_html`；`_STATUS_ROWS` 5 列） | 序列：取得／來源／資料日，或失敗狀態 | 81 §3.3 層2、MV-02（已裁示）；80 §16.2 | **裁**（BL-0540 G-3 核心）；搬動前提見 §3 |
| 12 | 🌍 | 更新資料 CTA 不可用（`chrome.py::render_status`） | 一句原因；位置「待 ⚙️ 線框」 | 80 §17.3 | 裁（⚙️ 線框一併定） |
| 13 | 💼 | A00 來源狀態容器（`pages/assets.py::a00_html`） | 來源狀態（complete／partial／未選定／讀取失敗／未讀） | 82（A00 線框，約 L1003 一帶）；`DEC-2026-11-14-06` | 必 |
| 14 | 💼 | A10 降級卡原因句、A20 四格 ◇、A50 逐檔 ◇ | Missing 不為 0 | 80 §7.2「摘要四項不得因 Missing 消失」；79 §11 | 必 |
| 15 | 💼 | A60 略過件數＋一句說明（`assets.py` 獨立 `<details>`） | 略過分頁／列數、四類說明；FAKE-only | `DEC-2026-11-17-01`；82 A60 列（「來源健康在 ⚙️ 詳細承接」） | 件數＋一句：必（判讀相關）；逐列明細若日後有：集 |
| 16 | 🔍 | 單檔查詢狀態（尚未查詢／入口攔截／取不到／頁面無法確認／結果）（`viewmodels/fund_lookup.py::LookupState`） | 取數失敗≠查無 | 80 §7.3；`DEC-2026-11-01-01`／`-02` | 必 |
| 17 | 🔍 | 欄位級 MISSING／CONFLICT；`pool_empty_marker`（poc） | 缺值不為 0 | BL-0557 | 必 |
| 18 | 🔍 | 收合區標題「基本資料｜尚未取得｜來源與限制」（`poc/fund_search_fixture_preview/fund_search_wording.py::details_title`） | PendingWording | BL-0557 待確認 (4) | 裁 |
| 19 | ⚙️ | NAS 中繼診斷（`pages/nas_diag.py`、`viewmodels/nas_diag.py`；`poc/nas_diag_preview/`） | 兩軸／六態／預設收合技術證據；FAKE 輸入 | BL-0550（九項 Pending） | 集（本來就是 ⚙️ 內容；掛載待裁） |
| 20 | ⚙️ | B 線既有 SET-1／2／6／8（`ui_v2/set/logic.py`、`ui_v2/page_health.py`） | 新鮮度／來源健康／取數紀錄／各頁狀態總表 | 79 §9.5；44 之十四其二（A 線先例） | 集（僅作 IA／能力參考；ui_v3 不得 import ui_v2） |
| 21 | 🤖 | 無頁、無元素（registry `phase7_onebrain_not_enabled`） | — | `DEC-2026-10-29-07` | 不適用 |
A 線先例【F】：44 之十四其二.7 在把來源／新鮮度搬到 SET-8 時，**明列「判讀證據照留」**（卡上 ◷／⛔／◇、「最近一筆淨值已超過 10 日」等），且 44 之十九其二.4 寫「下沉不等於搬走……不把任何一項只留在別頁而本卡什麼指引都不留」。這是本案「保留清單」的現成範本；44 對 New UI2 是否仍拘束＝Q1。

## 2. ⚙️ 資料健康度三層：最小規格差額
| 層 | 需要（80 §16.2 / #1278 §C） | 現有可讀（【F】檔:符號） | 缺口（不得假設） |
|---|---|---|---|
| ① 一般摘要 | 跨類別摘要；不寫「正常／資料齊」；僅陳述範圍內事實 | `viewmodels/shell.py::ShellStatus`（ok／total／failed／最後取得）僅涵蓋 🌍 五序列 | 基金／持倉／配息／匯率／景氣無摘要來源；範圍外必須顯示為「未評估／◇」，不可綠燈 |
| ② 逐來源／序列 | status、是否取得、source、as_of、retrieved_at、freshness、Missing／失敗原因、source health | `viewmodels/market_page.py::DomainStatus`（key／status／reason_code／source／as_of／fetched_at；5 序列＋7 無來源 domain）；利差三子序列在 `adapters/market_page.py::_indicator_series`（`release_date`、`errors`、`pending` 可讀，未入 VM）；`services/v2_tables/market_indicator.py::source_cooldowns()`（冷卻；ui_v3 未使用，【I】可由 adapter 讀，未驗） | **freshness**：`freshness_state` 恆 `undetermined`（stale_after 待 Threshold Gate，67 §8.5、BL-0531(5)）→ 該欄只能 `⬜ 門檻待裁示`；**持久化取數紀錄**：`fetch_log` 自 2026-10-26 僅存 session 記憶體（`services/v2_tables/settings_store.py` 檔頭），無「最近成功時間」；💼 有 `adapters/assets_source.py` 狀態（無 production 呼叫端）；🔍 無 loader；配息 `PENDING_TABLES=("dividend",)`；匯率 `FX_OBS_DATE_RULE_VERIFIED=False`；景氣 leading／coincident pending；狀態詞彙四～五套無對照表（`docs/evidence/ui_data_contract_audit_2026_11_12.md` §1.8；67 §5.3） |
| ③ 開發者診斷 | 預設收合；不漏 secrets；不堆 traceback 到普通 UI | `viewmodels/nas_diag.py` 建構時拒絕 `://`、`user:pass@`、非白名單字元，且無原始例外欄位；`pages/nas_diag.py` 預設收合 `<details>` | `infra/proxy.py` 是否能產出該 VM 的欄位＝NOT VERIFIED（README 自承）；PR 13.5.3「internal reason code 不顯示」與「開發者層」可顯示什麼＝Q4 |
與 83 的關係【F】：83 是**候選設計**（獨立監控 Sheet、`catalog_status` 等四分頁），自述「非 Schema、非施工授權」。其 §5 的 Fetch／Validation／Eligibility 三層**不是**#1278 的三層（摘要／provenance／診斷），勿混用。⚙️ 第一版可只用 in-session ViewModel 而不依賴該 Sheet；`last_success_at`、`fetch_events` 無持久來源→顯示 ⬜／◇，不補值。
#1278 §E：⚙️ 可「說明缺漏如何限制 AI 分析」，但未授權前只能是 deterministic 健康度說明，不得是獨立 OneBrain local summary（67 §6.1 僅批准 🌍／💼／🔍）。

## 3. 各頁保留項＋「查看完整資料健康度」入口：最小規格
- **保留項**＝§1 標「必」者。入口不是保留項的替代品。
- **入口字樣**：「查看完整資料健康度」在 `shared/ui_semantics/rules.py::APPROVED_WORDING` 與 `ui_v3/viewmodels/preview_wording.py` 皆 0 命中（【F】`grep 資料健康度`：ui_v3／shared 無命中）→ 只能是 **PendingWording**，需字樣核准；字樣本身為使用者轉述，非已核准詞。
- **目標不可進時**：registry `set` 未掛載→導覽以 `chrome.py::disabled_side_html`／`disabled_top_html` 呈現「可見但不可進」（`aria-disabled`、「開發中」＝已核准 `shell_nav_soon`）；`st.page_link` 只能連已註冊頁。故入口在 ⚙️ 掛載前只能是**不可點文字＋「開發中」**，且【R】**不要在 ⚙️ 掛載前出現**（會是看似連結的死入口，且尚無任何內容可被它取代）。
- 【R】入口、`▸ 各項資料狀態` 搬遷、⚙️ 掛載（registry＋`app_preview` renderer＋守衛改動）同批、同 PR，並附「資訊無損」對照表（§1 逐列去向）。入口屬新增視覺元件→需 UI 草稿（B）。

## 4. 合法施工 Gate 路徑
| 類 | 項目 | 備註 |
|---|---|---|
| **A** 現有 Gate 內 | A1 本差額分析入庫（docs-only）；A2 把 §1「必要揭露」清單轉成契約守衛測試草案（僅鎖現狀，不改 production） | A2 屬 tests，仍需派工授權；不動 UI |
| **B** 需最小 UI 草稿（CLAUDE.md §-1.5.4） | **B1 ⚙️ 資料健康度線框草稿**（390／1280；三層；情境：全取得／部分缺／來源失敗／範圍外類別 ◇／freshness 門檻待裁示）；B2 各頁入口位置草稿（不可進狀態）；B3 對 81 §3.3 層2 的修訂草稿（保留項＋VIX／利差來源去向） | 皆 docs-only；B1 不需先過 C |
| **C** 正式 Decision Gate／amendment | C1 BL-0540 G-3 承接方式（Q1）；C2 **最小 amendment 範圍**：僅 81 §3.3 層2「各項資料狀態」一列＋80 §7.5 ⚙️ 區塊＋BL-0540 回填；44 照總管推薦標 successor 不解凍，**僅在 Q1 答「44 仍拘束」時**才升級 G-44；C3 入口字樣核准；C4 ③ 層欄位範圍（Q4）；C5 freshness `stale_after`（Threshold Gate，既有 Pending）；C6 registry `set` 掛載＋守衛修改（Gate-M） | 搬動任何「必」項＝C；單純新增 ⚙️ 內容不是 |
| **D** 受阻 | 持久化取數紀錄／`last_success_at`（83 Schema 未核准）；NAS 真實探測（BL-0550）；匯率健康（FX Gate 關閉，BL-0217）；配息／景氣健康（來源 pending）；真實 Active Sheet 覆蓋（BL-0545）；Cloud／真機驗收（NOT RUN） | 在 ⚙️ 內一律顯示 ◇／⬜，不得假設可取 |
**建議順序**：B1（⚙️ 線框草稿）→ 使用者回答 Q1～Q5 → C1／C2（最小 amendment＋字樣）→ ⚙️ 內容實作（僅 in-session VM，Gate-M 掛載）→ 同批移除 🌍 `▸ 各項資料狀態` 並加入口。**第一步＝B1，不動 🌍。**

## 5. 風險與誤判點
- **R1（已求證）** 「預設比較檢視下，美10Y／2Y 的來源與資料日只出現在狀態列」：【F】以 `tests/ui_v3/market_stubs.py` 的測試替身資料（非真實行情、非 Streamlit 實跑）呼叫頁面純函式組出整頁文字後掃描：美10Y／美2Y 的來源與資料日只在 `status_row_html`；VIX 卡只顯示值與資料日，來源 `Yahoo:^VIX` 只在狀態列；`FRED (T10Y2Y)`／`BAMLH0A0HYM2`／`FEDFUNDS` 在整頁文字 0 命中（`SecondaryCard.source` 有值卻不渲染；`source_limits_html` 只列 Primary 兩序列＋通用限制句）。限定：比較檢視下美10Y／2Y 本身**不畫**（只在單序列檢視才畫），故它們的狀態列是狀態紀錄而非「已顯示數字」的來源揭露；真正的揭露風險在 VIX 卡與利率卡。真實 runtime／Cloud＝NOT VERIFIED。
- R2 81 §4 對利率卡只要求「觀測日沿用現況說明」，未要求子序列來源名→目前不是違規；是否補列＝裁（併入 Q2）。
- R3 來源標示格式不一致【F】：`Yahoo:^VIX` vs `Yahoo Finance (^TWII)`；是否為內部鍵外露（PR 13.5.3）NOT VERIFIED（替身資料所致或真實如此未驗）。
- R4 「n／5 項已取得」易被讀成全站健康（80 §17.4）；⚙️ 層① 不可沿用該字樣當全站結論。Status Bar 的時間是取得時間，不是資料日（79 §7.1）。
- R5 「取得」≠「可用」（83 §5）；⚙️ 不得以 ok 列暗示資料齊／正常（80 §17.2；44 之十四其一.3）。
- R6 Missing 名單（#10）與「完整缺值堆疊」容易被一併移走；Missing 一項不刪（D4＝β、67 §5.4）。
- R7 搬動後若 ⚙️ 仍 `wireframe_not_approved`，使用者將同時失去頁內明細且無處可看（資訊遺失）→ 必須同批。
- R8 #1278 comment 為使用者對話存檔，非 DEC；BL-0540 G-3 條文目前仍是「待客戶裁示」，不得因該則視為已解。
- R9 本組未重跑 CI／測試；`tests/ui_v3` 中涉及 §1 元素的現有守衛清單未逐一核對（可能有字面鎖定而擋住搬遷）。

## 6. 需使用者裁示的最小問題
1. **Q1（C；BL-0540 G-3）** 承接方式。既有答案：總管推薦「各頁 wireframe 承接、44 與 72／73／78／65 標 successor 不解凍；涉資料語意才走 G-44」。【R】照此，並確認 44 之十九其二.4／§5.4 對 New UI2 是否仍拘束。風險：若仍拘束，搬走 #11 需 G-44 amendment。
2. **Q2** 搬遷範圍：【R】僅搬 #11 逐列明細（與 #7 取得時間）；保留 #10 名單；並同批把 VIX 與利差三子序列的來源補進卡的 `▸ 來源與限制`。既有答案：80 §16.2「主頁只留 freshness／source 摘要」，未逐項點名。風險：補來源屬新增元素（B）；不補則 VIX／利率卡失去來源。
3. **Q3** 入口時機與字樣：【R】入口與 ⚙️ 掛載、#11 搬遷同批；字樣「查看完整資料健康度」先作 PendingWording。風險：先放入口＝死入口。
4. **Q4** ③ 層可顯示欄位：【R】僅經遮蔽的分類碼／來源標籤／HTTP 類別，預設收合；不含環境變數名、URL、帳密、traceback（沿用 `NasDiagObservation` 的拒絕規則）。既有答案：PR 13.5.3 只說「開發者診斷層預設收合」。風險：範圍過寬即洩漏。
5. **Q5** ⚙️ 第一版範圍：【R】只做 in-session 的 🌍 資料＋NAS 診斷，其他類別顯示 ◇／⬜「尚未評估」，不等 83 的 Sheet。既有答案：83 為候選且未核准。風險：使用者可能預期「涵蓋所有類別」（80 §16.2）而看到多數為空。

## 7. 無法確認項
真實 `ui_v3` Cloud 畫面與 SHA（NOT VERIFIED）；R1 的真實資料行為；`infra/proxy.py` 能否產出 NAS VM 欄位；現有 tests 對 §1 元素的字面鎖定；#1278 §C 以外的 ChatGPT HTML 視覺稿（NOT PROVIDED）；`docs/v2/72／73／78／65` 各自頁內資料狀態塊的逐條現況（僅引 80 §16.2 與 BL-0540 的承接說法，未逐檔讀）。
