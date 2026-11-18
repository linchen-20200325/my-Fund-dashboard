# 🔍 找基金｜版面掛載 Gate-M 裁示卡（與 Gate-D 資料接線分開）（2026-11-17）

> **2026-11-18 狀態註記（最小加註，原文未改）**：本文寫成時 D2 R-NAV-4 為 Pending；其後 R-NAV-4 已由 `DEC-2026-11-17-06` 核准契約文字 `T-NAV4`（僅 nav 表 `source_tier`；經對話提示語轉達自稱客戶，待核），R-NAV-6 仍 Pending。下文涉 R-NAV-4 之『Pending／候選』敘述為歷史，以 `docs/DECISIONS.md` 為準。

> **單組作者整理，未經獨立 QA；全稱句（「只有／沒有／全部」）皆為單組 grep／讀碼結論，未經第二組驗證。**
> **不構成授權、不是客戶裁示、不改任何程式或測試。** 基準 main `809dbd16`（含 #1268；2026-11-17 `git fetch` 實查，使用前須重查 GitHub）。
> 證據符號：【碼】讀現行程式；【DEC】對照 `docs/DECISIONS.md`；【文】依既有 evidence／BACKLOG（本組未重驗）；【未驗】本組沒查。不寫行號，以「檔案::符號」定位。

## 0　結論（先講）

| 問題 | 單組結論 |
|---|---|
| 現在要不要問客戶 Gate-M？ | **現在不建議單獨問**（理由見第 4 節）；裁示卡已備妥（第 5 節），客戶若想看「🔍 在真實 Shell 導覽內的樣子」可隨時用。 |
| Gate-D（真實資料接線）？ | **維持暫緩**，直到 `DEC-2026-11-14-08` 的 S2-T0 解凍；不在本卡問。 |
| 不需新 Gate 的下一個 🔍 可見切片？ | **沒有**（第 6 節）。 |
| 最大的結構性發現 | 掛載不是「改 registry 一格」：🔍 的 renderer／logic／wording／fake_inputs 四個模組現住 `poc/`，ui_v3 不能 import `poc/`；FAKE 輸入又不能經 `ui_v3.fixtures` 進 `app_preview`（既有守衛禁止）。**掛載必然連帶「搬 renderer」「FAKE 輸入供應處」「放寬或新增守衛」三件事，每一件都需新授權。**【碼】 |

## 1　掛載需要改哪些檔（精確範圍，單組估計）

現況【碼】：`ui_v3/shell/registry.py::IA_PAGES` 中 `exp` ＝ `PageSlot("exp","🔍 找基金", False, REASON_WIREFRAME_PENDING)`；`ui_v3/app_preview.py::main` 只有 `renderers = {"mkt": _render_mkt}`；`assert_preview_ready()` 取 `registered_pages()`；`pages/chrome.py::render_navigation` 對 `available`（＝`registered`）項才 `st.page_link(pages[slug])`，其餘畫 disabled「開發中」。

### 1-A　必改／新增的來源檔

| # | 檔案 | 動作 | 為什麼 |
|---|---|---|---|
| S1 | `ui_v3/shell/registry.py` | `exp` 改 `registered=True`（另見 2-B 是否加註冊狀態欄位） | 導覽才會出現可點的 🔍 |
| S2 | `ui_v3/app_preview.py` | 新增 `_render_exp` 並加進 `renderers`；若有 FAKE 標示由 Shell 負責則另有小改 | 否則 `main()` 對「已掛載卻無 renderer」直接 `NotImplementedError`（Fail Loud，現行守衛已測） |
| S3 | `ui_v3/pages/exp.py`（新） | 由 `poc/fund_search_fixture_preview/fund_search_renderer.py` 搬入 | `app_preview` 只能 import `ui_v3` 內層；`pages` 層依 `LAYER_DEPS` 只可 import `pages／shell／design／viewmodels` |
| S4 | `ui_v3/viewmodels/` 新檔（logic） | 由 `fund_search_logic.py` 搬入 | renderer 依賴它；已 import `viewmodels.exp_counts`，同層可行 |
| S5 | `ui_v3/viewmodels/` 新檔（wording） | 由 `fund_search_wording.py` 搬入（含 `PendingWording` 暫行字樣） | renderer 依賴；`shared.ui_semantics` 僅 `viewmodels／pages` 可 import（`SHARED_ALLOWED_LAYERS`） |
| S6 | **FAKE 輸入供應處（新；位置待裁）** | 由 `fund_search_fake_inputs.py` 轉入 `ui_v3/` 內某處 | 見 2-C：`ui_v3/fixtures/` 依既有守衛不得被 `app_preview`／`pages` import |
| S7 | `poc/fund_search_fixture_preview/*.py` | 改成薄 harness（import ui_v3 版本），或保留並加 drift 測試 | 避免兩份分叉；💼／⚙️ 已有同型先例（`poc/assets_fixture_preview`、`poc/nas_diag_preview` 搭配 `ui_v3/pages/assets.py`、`nas_diag.py`）【碼】 |

### 1-B　會因此要改的既有守衛／測試（單組 grep 結果，非窮舉）

| 測試檔 | 為什麼會紅／要改 |
|---|---|
| `tests/ui_v3/test_ui_v3_page_registry_guard.py` | `test_only_market_page_is_registered_so_no_empty_shell` 斷言已掛載＝`["mkt"]` 且其餘四頁必須 `registered=False` |
| `tests/ui_v3/test_ui_v3_navigation_shell.py` | 斷言 `available` 的 slug 清單＝`["mkt"]`；`exp` 於「未掛載可見不可進」迴圈內 |
| `tests/ui_v3/test_ui_v3_assets_source_import_isolation.py` | `test_registry_has_no_new_page_and_preview_renderers_are_unchanged` 斷言已掛載＝`["mkt"]` |
| `tests/ui_v3/test_ui_v3_top_nav_browser.py`、`test_ui_v3_market_page_browser.py` | 瀏覽器層預期「未掛載四項 `aria-disabled`、只有 🌍 可聚焦」（slow／browser；本組未跑）【未驗】 |
| `tests/ui_v3/test_ui_v3_preview_navigation_pages_guard.py` | **多半自動跟 registry 走**（比較 `st.navigation` 頁集合與 `registered_pages()`）；其負控（插入 `zz` 頁）應仍紅。需 CI 實跑確認【未驗】 |
| `tests/ui_v3/test_ui_v3_preview_not_formal_guard.py` | 負控用 `ast` 當「已掛載卻無 renderer」，與 `exp` 無關，**預期不用改**；`app_preview` 模組層零 streamlit／零 fixtures 的檢查須維持 |
| `tests/ui_v3/test_ui_v3_import_guard.py`、`test_ui_v3_fixtures_are_fake_guard.py`、`ui_v3_guard_lib.py` | 若 FAKE 供應處放 `adapters`／`viewmodels`，需新增「FAKE 專用模組白名單＋必須有 FAKE 標示」規則；放 `fixtures` 則必須放寬「`app_preview`／`pages` 不得 import fixtures」（`DEC` 外的原則改變，**不建議**） |
| `tests/poc_fund_search_preview/*` | 隨 renderer／logic／wording／fake_inputs 搬遷改 import 路徑，並保留 drift 鎖 |
| **待查守衛（本組未讀其內容，是否受影響須實查）**【未驗】 | `tests/poc_fund_search_preview/test_fund_search_guards.py`（poc 目錄 import 白名單與隔離守衛）、`tests/poc_assets_preview/test_assets_preview_apptest.py`、`tests/visual_fidelity/test_ci_fixture_screenshots.py` |
| 新增 | `tests/ui_v3/test_ui_v3_exp_page_*`（renderer／AppTest）、FAKE 標示守衛、註冊狀態守衛、nav 內 🔍 可進／可聚焦的瀏覽器斷言 |

### 1-C　可見成果與回滾

- **可見成果（若獲准）**：在 `streamlit run ui_v3/app_preview.py` 的 Preview 導覽（桌機側欄／手機頁首五格）中，🔍 由「開發中」變可點；點入看到與 poc 相同的離線 FAKE 版面（上區查詢、下區 EXP-0／1／2／7），可操作 `FAKE-OK01／FAKE-LOW1／FAKE-ERR1` 與三個 FAKE 條件勾選。🌍 仍是唯一真實資料頁。
- **回滾**：建議拆成兩個 PR，先搬後掛。**PR-M0**（搬 renderer／logic／wording、poc 改薄 harness、drift 測試，**不改 registry／app_preview**）與 **PR-M1**（S1＋S2＋守衛調整）。回滾 M1 ＝ `git revert` M1 一個 commit：`exp` 還原 `registered=False, REASON_WIREFRAME_PENDING`、刪 `_render_exp` 與 `renderers` 一格、守衛還原；M0 搬出的檔留在 ui_v3 但**未被任何入口引用**（`ui_v3` 本來就沒有 production 引用者）。M0 與 M1 合併成一個 PR 則回滾範圍為整個 PR（S1～S7＋測試）。

## 2　註冊狀態語意與風險

### 2-A　`registered=True` 對 🔍 的意義【碼】

`registry.py` 檔頭定義：`registered` ＝「已有核准 wireframe 且已實作的頁」；`PageSlot` 只有 `slug／title／registered／unregistered_reason` 四欄，**沒有「資料是真是假」欄位**；`app_preview` 檔頭明文「preview 不得顯示 fake 資料、不得 import fixtures」。
→ 🔍 若直接 `registered=True`，Shell 導覽對 🌍（真資料）與 🔍（離線 FAKE）**呈現完全相同**（同樣可點、同樣無「開發中」標籤）。

### 2-B　風險與緩解

| 風險 | 說明 | 緩解（需裁示的條目） |
|---|---|---|
| R1 被誤讀為正式資料頁 | 同一導覽內 FAKE 與真資料並列；FAKE 基金名稱／代碼雖明示，但「找基金」看起來就是正式功能 | 頁頂常駐 FAKE 橫幅（poc 的 `FAKE_BANNER` 目前屬 harness，不屬 renderer；搬遷後須由頁本身帶出，不可只靠 harness）；導覽項加「FAKE」標記 |
| R2 `registered` 語意稀釋 | 日後有人以「registered 即已接真資料」推論；`app_preview` 的 Fail Loud 邏輯也不分真假 | 新增 PageSlot 欄位（例：`data_mode`：`real`／`offline_fake`）＋守衛：`offline_fake` 必須帶 FAKE 橫幅且不得 import 任何網路／Sheet／secrets 模組 |
| R3 既有「preview 不顯示 fake 資料」原則被破例 | 這是原則改變，不只是檔案改動 | 須客戶明確裁示「Preview 允許一頁離線 FAKE」；否則 S6 無合法落點 |
| R4 `test_ui_v3_preview_not_formal_guard` 的約束 | 它守的是「正式入口不得引用 ui_v3」「`app_preview` 模組層零副作用」，**並不阻止**在 `app_preview` 內註冊 FAKE 頁；也**不提供** FAKE 標示約束 | 需新增專屬 FAKE 標示守衛（本卡把它列為授權條目 A4） |
| R5 暫行字樣固化進 Shell | `DEC-2026-11-17-02` 仍列 (a)～(g) 待客戶／設計者裁示（W14 替代句、ISIN 常駐句、缺值字樣 `⬜`／`◇`、EXP-7 欄位等）【DEC】 | 掛載後仍一律 `PendingWording`（虛線底線＋`data-pending-wording`），不得升格 |

### 2-C　FAKE 輸入供應處的結構性卡點【碼】

- `ui_v3/fixtures/`：`test_ui_v3_fixtures_are_fake_guard.py` 規定除 `tests/` 與 fixtures 本身外**不得有任何 `.py` import `ui_v3.fixtures`（含 `app_preview.py`）**。
- `ui_v3/adapters/`：`LAYER_DEPS` 允許 import `viewmodels`；目前 `market_page`、`assets_source` 等為取數 adapter。放 FAKE 供應者需新增「FAKE-only adapter」白名單與標示守衛。
- 最小選項：新檔 `ui_v3/adapters/exp_fake_source.py`（模組層宣告 `FAKE_FIXTURE = True`、無網路／無 `shared`／無環境變數），並讓守衛只准 `app_preview::_render_exp` 一處 import 它。此為**單組設計建議，未驗**。

## 3　需要新增授權的條目（`DEC-2026-11-17-02` 的「不授權範圍」明列 registry／`app_preview`／導覽，且只授權 `poc/` 與其測試目錄）【DEC】

| # | 授權條目 | 為什麼現有 DEC 不涵蓋 |
|---|---|---|
| A1 | 於 `ui_v3/pages/exp.py` 與 `ui_v3/viewmodels/` 新增 🔍 renderer／logic／wording（由 poc 搬入；第四個模組 fake_inputs 轉入 FAKE-only adapter，見 S6） | DEC 明列「不修改正式 `ui_v3/pages` 或導覽」 |
| A2 | 修改 `ui_v3/shell/registry.py`（`exp` 掛載；可能加欄位） | DEC 明列不授權 |
| A3 | 修改 `ui_v3/app_preview.py`（`_render_exp`／`renderers`） | DEC 明列不授權 |
| A4 | 新增／放寬守衛：FAKE 專用模組白名單、FAKE 橫幅必備、`registered` 與資料真假的關係、nav 測試改寫 | 原則性改變（R3） |
| A5 | 明示「Preview 導覽可含離線 FAKE 頁」並規定導覽項／頁頂標示方式 | 與 `app_preview` 現行「不顯示 fake 資料」文字相反 |
| A6 | 修改 `poc/fund_search_fixture_preview/*` 為薄 harness、`tests/poc_fund_search_preview/*` 改 import | DEC 授權的是新建，未涵蓋搬遷後改寫 |

## 4　為什麼現在不建議單獨問 Gate-M

1. **價值低於成本**：客戶今天已可 `streamlit run poc/fund_search_fixture_preview/app_fund_search_preview.py` 看到同一份 FAKE 版面；掛載多出來的只是「在 Shell 導覽內點得到」，卻要動 registry／`app_preview`／至少 6 個守衛檔並搬 4 個模組（renderer／logic／wording／fake_inputs；其中 fake_inputs 轉入 FAKE-only adapter，見 S6）。
2. **原則衝突需先裁**：A5 會推翻 `app_preview`「不顯示 fake 資料」；💼（A50／A60）、⚙️（BL-0550）同為 FAKE 隔離預覽，**目前皆未掛載**。若只掛 🔍，對其餘兩頁形成不一致先例；較合理是一次裁「Preview 導覽可否含離線 FAKE 頁」的政策（第 7 節），再逐頁套用。
3. **待定字樣尚多**：`DEC-2026-11-17-02` 的 (a)～(g) 未裁；掛進 Shell 會讓暫行字樣更接近使用者可見位置。
4. **對「往正式前進」的貢獻有限**：正式可用的真正阻擋在 Gate-D（S2-T0 暫緩、選股池 `pool_not_cloud`、D2 Pending、ISIN 無對照來源），掛載 FAKE 頁不縮短這條路徑。
5. **翻案條件**：若客戶明說要「看 🔍 在真實 Shell（手機頁首五格／側欄）內的樣子」，或決定對三個 FAKE 預覽頁一併採同一政策，才值得問；此時用第 5 節的卡。

## 5　兩個 Gate 的拆分方案表

| 方案 | 內容 | 優點 | 缺點 | 風險 | AI 推薦 |
|---|---|---|---|---|---|
| **M-0　維持現狀（不問）** | 🔍 FAKE 只留 `poc/`；registry 不動 | 零改動、零誤讀 | Shell 內仍看不到 🔍 | 無新增 | **推薦（現在）** |
| **M-1　Gate-M：掛載離線 FAKE（兩步：先搬 M0、後掛 M1）** | A1～A6；🔍 `registered=True`＋`offline_fake` 標記＋頁頂 FAKE 橫幅＋FAKE-only adapter；全部 FAKE，不接資料 | 可在真 Shell 驗導覽／手機頁首／選取態；回滾乾淨（revert M1） | 檔案面廣（S1～S7＋守衛）；推翻「Preview 不顯示 fake」原則；暫行字樣更顯眼 | R1、R2、R3、R5 | 客戶只想看 🔍 一頁在 Shell 內的效果、且不打算同時掛 💼／⚙️ 時才推薦 |
| **M-2　先裁「FAKE 頁掛載政策」再逐頁** | 一次裁示 🔍／💼／⚙️ 是否可進 Preview 導覽及標示規格；之後各頁各自小 Gate | 避免不一致先例；守衛只改一次 | 比 M-1 多一輪對話 | 低 | 客戶有意讓 🔍／💼／⚙️ 多頁掛載時優於 M-1（🔍 可當第一頁套用） |
| **D-0　Gate-D 維持暫緩** | 不授權任何真實資料接線；等 S2-T0 解凍 | 與 `DEC-2026-11-14-08` 一致 | 無進度 | 無 | **推薦（維持）** |
| D-1　Gate-D：接真實資料 | 需另有完整接線 Gate | — | 見第 8 節各項阻擋 | 高 | **不在本卡問** |

### Gate-M 最小裁示卡（若客戶要問才用；商業語言，附推薦）

> **問**：是否同意把「🔍 找基金」的**離線 FAKE 版面**掛進 New UI2 Preview 導覽（僅供看版面與操作感，所有基金名稱／數字都是模擬，不接任何真實資料）？
> **推薦**：現在先不掛（M-0）；若客戶要看 Shell 內效果：只想看 🔍 一頁選 M-1；有意讓多頁掛載選 M-2（先裁政策，再逐頁套用，🔍 可當第一頁）。兩者皆須 🔍 頁頂永遠顯示「FAKE／離線測試資料」。
> **做法與範圍（M-1）**：僅 `ui_v3/shell/registry.py`、`ui_v3/app_preview.py`、`ui_v3/pages/exp.py`、`ui_v3/viewmodels/` 新增 logic、wording 兩檔、一個 FAKE-only adapter（承接 fake_inputs）、`poc/fund_search_fixture_preview/` 薄化、對應測試與守衛。
> **使用者可見**：Preview 導覽 🔍 可點入離線 FAKE 版面。
> **不得觸碰**：Google Sheet、選股池、frozen 44、正式公式、Schema、FX、ISIN 解析與對照、secrets、任何網路請求、D2 Pending 欄位值、EXP-3／4／5／6、使用者設定寫入；不得宣稱 🔍 功能完成。
> **字樣規則**：沿用 `PendingWording`；新字樣一律暫行，已核准字樣取規則表；不得自行定稿。
> **回滾**：revert 掛載 commit（registry 一格＋renderer 一個＋守衛）。
> **品質門檻**：至少 1 組真正獨立 QA（涉治理規則與使用者可見語意）；CI 全綠（含 slow lane 與 browser 測試）；Cloud／真機驗收另列 NOT VERIFIED，不得宣稱已驗。
> **待客戶一併確認**：(1) 是否同意推翻「Preview 不顯示 fake 資料」的既有原則（僅限標示為離線 FAKE 的頁）；(2) 導覽項是否加「FAKE」字樣；(3) 要不要與 💼／⚙️ 一併適用同一政策。

## 6　不需新 Gate 的下一個可見切片

| 頁 | 清單 |
|---|---|
| 🔍 | **沒有**新的使用者可見切片：任何進 Shell 的可見物都撞 A1～A6；在 `poc/fund_search_fixture_preview/` 內的修整只可處理 `DEC-2026-11-17-02` 已授權範圍，且其待定項（W14 替代句、ISIN 句、缺值字樣、EXP-7 欄位等）屬設計者／客戶裁示，**預覽不可自行定稿**。 |
| 其他頁 | 見第 7 節對照（引用 `docs/evidence/new_ui2_five_page_status_2026_11_17.md`，本組未重驗）。 |

## 7　其餘四頁最小下一步（一句話；出處 `new_ui2_five_page_status_2026_11_17.md`）

| 頁 | 最小下一步 |
|---|---|
| 🌍 | 候選 BL-0544 唯讀驗收（取得 Cloud 證據，區分 PASS／NOT VERIFIED／NOT RUN）；該項是否落在 BL-0544 授權字面待客戶確認。 |
| 💼 | 在 `DEC-2026-11-16-01`／`-17-01` 的 FAKE 隔離範圍內補「待確認字樣」修整（新字樣一律 `PendingWording`）；不掛頁、不接資料。 |
| 🤖 | 無（Phase 7 前 `PageSlot` 建構即擋 `registered=True`）。 |
| ⚙️ | 僅 FAKE 層小修；掛載與真實探測等 BL-0550 九項裁示。 |
| 附註 | 該 status 文件寫「🔍 無 FAKE 預覽頁」，**已被 #1267／#1268 的 `poc/fund_search_fixture_preview/` 取代而過期**【碼】；本卡不改該檔，建議 HANDOFF 同步時一併更正。 |

## 8　Gate-D：既有 L2 能合法提供什麼、什麼不能接

只讀盤點，單組 grep／讀檔，未跑任何函式【未驗】。

| 能力 | 現有 L2 | 契約／狀態 | 能否接 🔍 |
|---|---|---|---|
| 條件三態比較（純計算） | `services/v2_domain/rule_filter.py::apply_rules_tristate`／`compare_tristate`（缺值＝無法判定；ui_v3 adapters 靜態守衛允許 import `services.v2_domain`）【碼】 | 判定一字未改自 ui_v2；條件欄位／母體契約仍屬 D2 | 引擎可用；**母體與欄位語意未定**，不能直接接 |
| 母體（選股池代碼） | `services/v2_tables/exp_universe.py::load_pool_codes`（只讀 `code`；本機 JSON 回 `STATUS_NOT_CLOUD`）【碼】 | `pool_not_cloud` 顯示語意未裁；`DEC-2026-11-14-08` 暫緩且不得接 Google Sheet【DEC】 | **不可接** |
| 基金基本資料 | `services/v2_tables/exp_profile.py::build_profiles`（名稱／成立日／配息政策／幣別逐欄出處）【碼】 | 屬 B 線 C2，尚未接 ui_v3；需 MoneyDJ 網路取數（本卡範圍禁網路） | 非 Gate-M；屬 Gate-D 範圍，且受 S2-T0 暫緩 |
| 淨值／配息 | `services/v2_tables/exp_nav.py::load_nav_dividend`、`nav_dividend.build_nav_dividend_tables`【碼】 | D2：R-NAV-2（T-NAV2）、R-NAV-5（T-NAV5）已核准；**R-NAV-3 暫緩、~~R-NAV-4／~~R-NAV-6 Pending**（2026-11-18：R-NAV-4 已由 `DEC-2026-11-17-06` 核准〔僅 `T-NAV4`〕，不影響『不可接』結論）【DEC：`DEC-2026-11-14-07`（R-NAV-3 暫緩）；`DEC-2026-11-13-06`（D2 核准欄位狀態列：R-NAV-4／R-NAV-6 仍 Pending）】 | **不可接**（含 Pending 欄位值） |
| 代碼→full_key | `services/v2_tables/fund_keys.py::resolve_full_keys`（要求純代碼；非 ASCII 判失敗）【碼】 | 不處理 ISIN | 僅代碼型輸入 |
| ISIN | 無已核准對照來源；`DEC-2026-11-01-02`（G-E1：A＋C）要求入口保留但未核准前不啟用【DEC】 | 預覽已固定顯示「ISIN 未啟用」 | **不可接** |
| `services/fund_service.py` | 含 `calc_metrics`、`fetch_fund_by_key_enriched` 等（舊樹 L2，會取數與算指標）【碼】 | 與 🔍 New UI2 契約無對應；公式屬 frozen 範圍 | 不可接 |

## 9　NOT VERIFIED

1. 第 1-B 表為單組 grep；有無其他測試受影響（含 slow／browser 層）未實跑【未驗】。
2. 「沒有」類全稱句（無不需新 Gate 的 🔍 切片；ui_v3 不能 import `poc/`）為單組讀碼結論；`poc/` 不可被 import 係由 `LAYER_DEPS` 與 import 守衛推得，**未用負控實測**。
3. 第 8 節未執行任何函式，契約狀態取自 DEC 文字；D2 欄位狀態以 `DEC-2026-11-13-06` 該列為準（本組只讀該列，其後是否有更新裁示未逐筆重核）。
4. 檔案數與守衛數為單組估計；實際範圍以 PR 為準。
5. Cloud／真機／瀏覽器像素未驗；CI 結果未查（main CI 尚未回報）。
6. 本卡所有推薦為作者建議，**非授權、非客戶裁示**。
