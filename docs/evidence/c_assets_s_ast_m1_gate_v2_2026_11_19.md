# 💼 S-AST-M1 修正版 Gate（v2；A1a 安全修正版＋獨立示範標記）

> **兩點先講清楚**：(i) **「改固定情境③」是作者（執行組）推薦【R】，不是客戶核准的 A1a 內容**——客戶方向（〔待核〕轉述）只含「A1a 安全修正版」與條件，未指定情境；(ii) 本卡內的條件編號 (1)～(8)（以及 §a／§b／§e／§f 引用的「條件 (n)」）是**作者自編、非來源編號**，與 `DEC-2026-11-19-01` S-a(1)～(7) 的條號無關；提到 S-a 時一律寫「S-a(n)」。

> 單組執行組唯讀草稿，**未經第二組獨立複驗**；不是授權、不是 DEC、不改 repo（突變實跑只在 `git archive` 暫存副本）。
> 標記：【F】事實（讀檔／實跑）、【I】推論、【R】執行組推薦（可被推翻）、【未驗】。不寫行號。
> **裁示來源**：下列「已方向核准」皆為 ChatGPT 總管轉達、客戶經其轉述〔待核〕，**非客戶逐字、repo 無原文**；本卡不把方向寫成逐字規格，不捏造引言。
> 基準 `origin/main` `eb08c5fc`（重核）。【F】自 `0cfd86b9` 起 `ui_v3`／`poc`／`tests` 無任何變動，僅 docs（#1285、#1286；#1286 已把上一版卡落為 `docs/evidence/c_assets_s_ast_m1_gate_card_2026_11_19.md`，本組未重讀該檔）。**原 A1a（固定 ⑤）作廢，不得直接施工。**

## 0　結論

【F】**A10 假「成本」不需改 viewmodel／adapter／renderer／fixture 內容即可消除**：改固定既有情境 **③「市值基準未開放」**（`evidence=None`）。我在暫存副本用真實 `build_assets_page`＋`page_html`（純函式，與 runtime 同碼）渲染：③ 頁面文字為「來源 ⬜ 無法判定｜資產配置 ◇ 資料未備｜**基準 ◇ 資料未備**｜四格 ◇ 資料未備｜完整持倉 ⬜ 無法判定｜A60：略過分頁數／列數 ◇ 資料未備、⬜ 無法判定」。無基金名、無持倉列、無「成本」、無任何設定值；首屏標記 5 個、`<details>` 只有 A60 一個（A50 為純文字 status-only）。
【R】**採 ③，條件 (1) 可滿足且屬「優先用既有元件」**。導覽／頁頂標記需新增少量 Shell 程式（§b），評估後仍屬可控；若 §b 的 Chromium 五格量測不過，依條件 (8) 落 **A0**。

## a　A10 假成本處置（可判定方案；條件編號為作者自編）

| 方案 | 做法 | 動到 | 顯示 | 判定 |
|---|---|---|---|---|
| **X1（推薦）固定情境③** | `_render_ast` 吃與③相同的封包；基準列走既有「set 但無值」路徑 | **無 VM／adapter／renderer／fixture 內容變更**；新增一個純常數函式（見 §d）＝既有③封包的複本，以 drift 測試鎖等於 `tests/ui_v3/assets_page_support.py::market_blocked_result()` | 基準 `◇ 資料未備`（已核准字樣） | **滿足條件 (1)、(7)** |
| X2 ⑤＋基準「未設定」 | 在⑤封包把 `settings_status.alo_basis` 設 `unset` | 僅 fixture 層一個鍵；實渲染：基準 `⬜ 未設定`（`user_param_unset`，已核准字樣） | 不顯示設定值，但**宣稱「使用者尚未設定基準」＝仍是對個人設定狀態的 FAKE 陳述** | 可行但較差；僅在客戶要「選定來源」敘事時備用 |
| X3 改 renderer／VM 隱藏基準列 | 動 `ui_v3/pages/assets.py` 或 adapter | VM／renderer＋既有 renderer／adapter 測試 | — | **不滿足「優先既有」，且動已驗收程式；不採** |
| X4 維持⑤（顯示「成本」） | — | — | FAKE 個人設定值 | **違反條件 (1)，禁止** |

【F】已知舊落差照舊（`blocked_basis_state_without_value`：③ 的基準狀態是 set 但無值，顯示 `◇ 資料未備`）——poc README 已登記，本版不處置。【I】③ 的 A10 原因句「配置比較的計算口徑尚未核准，故不提供結果」為既有 PendingWording，非核准字樣。
【F】③ 是否等同「production 載入端現況」：BACKLOG／gap supplement 記載載入端在市值基準下一律 blocked、不讀持倉（本組未重驗）。【I】故③頁面是誠實的「現況空狀態」，不是假資料頁；代價＝**可見進展僅限「💼 在 Preview 可進入、版面與缺值語意可審」，沒有任何資料。**

## b　導覽標記與頁頂標記機制（作者自編條件 (2)(3)(4)）

**設計原則**：標記與 `.uv3-nav-soon`／`.uv3-tn-soon`（語意＝開發中、`aria-disabled="true"`、不可進）完全分開：不同 CSS class、不同 DOM 屬性（`data-nav-demo`）、**不帶 `aria-disabled`、不設 `cursor:not-allowed`、可進的連結照舊是 `st.page_link`**；已核准五頁短標（市場／資產／找基金／AI／設定）與 `shell_*` 19 鍵一字不動。

| 檔案 | 變更 | 說明 |
|---|---|---|
| `ui_v3/shell/registry.py` | `PageSlot` 末尾新增 `data_mode: str = "real"`（值域 `real`／`offline_demo`；`offline_demo` 僅允許 `registered=True` 且 `slug != "ai"`）；`ast` 改 `registered=True, data_mode="offline_demo"` | 【F】現有 `PageSlot(...)` 呼叫皆為 ≤4 個位置參數，新增預設欄位不破壞；已實跑突變：僅 2 條守衛轉紅（§c） |
| `ui_v3/shell/nav.py` | `NavItem` 新增 `demo: bool = False`；`nav_items()` 由 `slot.data_mode` 帶入；`shell_css()` 新增 `.uv3-nav-demo`／`.uv3-tn-demo`／`.uv3-demo-banner` 樣式（**實線框、可進語意、不得與 soon 共用 class**） | 既有 `test_css_switches_between_sidebar_and_top_nav_at_one_breakpoint` 的字串斷言須仍成立（新規則不得進入 `.st-key-uv3-top-nav{…}` 主規則塊、不得出現 `position:`／固定高度） |
| `ui_v3/pages/chrome.py` | `render_navigation`：`item.available and item.demo` 時，在**同一個 `_now_key` 容器內**、`st.page_link` 之後多一個 `st.markdown` 標記（側欄與手機頁首各一）；新增純函式 `demo_banner_html()`／`demo_marker_html(item)` | 【F】該檔既有守衛要求 `render_navigation` 原始碼含 `nav.TOP_KEY`、`st.page_link`、`disabled_top_html`——不得刪；標記是**連結的兄弟元素**，不改 `page_link` 的 label（短標不變） |
| `ui_v3/viewmodels/preview_wording.py` | 新增 2 個 `PendingWording`：頁頂橫幅、導覽標記；**key 不得以 `shell_` 開頭**（【F】`test_shell_wording_lives_only_in_the_rules_table…` 要求 `W.PREVIEW_PENDING_WORDING` 無 `shell_*`，且規則表 `shell_*` 恰 19 鍵）；`source` 不得含 `poc/` | 不動 `shared/ui_semantics/rules.py` |
| `ui_v3/app_preview.py` | 新增 `_render_ast`（見 §d）：先畫頁頂橫幅，再 `assets.render(build_assets_page(封包))`；**不呼叫 `chrome.render_status`**（無市場 model，且確保不牽出網路）；`renderers` 加 `ast` | `page_icon="🌍"` 寫死維持不動（本版不處理，登記） |

- **頁頂標記**：橫幅位於 💼 頁最上方（在 `st.title` 之前），class 為 `uv3-demo-banner`；文字【R】沿用 harness 既有字串「FAKE／測試資料（非真實持倉，不代表任何實際資料）」作為 PendingWording（`DEC-2026-11-19-01` S-a 方向；字樣最終未核）。
- **導覽標記文字**：【I】`DEC-2026-11-19-01` S-a(2)「不創第二套無來源文案」⇒ 導覽標記不能憑空發明新詞。【R】候選＝取自上述既有字串的詞 **「FAKE」**（可追溯來源）；若客戶要「示範」等新詞，須客戶核准該字樣（見 §g）。已核准的 `PREVIEW`／`Preview｜非正式頁面` 語意是「整個 App 為預覽」，不等於「此頁為離線示範」，不借用。
- **新 PendingWording 的 `source` 寫法**（【R】；不得含 `poc/`）：例如 `DEC-2026-11-19-01 S-a（方向，轉述〔待核〕）；取自 harness 常數 FAKE_BANNER（💼 隔離預覽入口檔內）；字樣未核准`。僅引 DEC 編號與常數名，不寫路徑。
- **語意張力（須客戶選字）**：③ 頁面本身沒有任何假資料（是誠實的現況空狀態），但橫幅／標記寫「FAKE」，可能被讀成「資料壞了／這是假的」而非「離線示範、尚未接資料」。候選：「FAKE」（可追溯、但易反讀）／「示範」（語意較貼切、但是新詞，須客戶核准字樣）。橫幅內文沿用 harness 字串含「非真實持倉」，在無持倉的③ 頁仍為真，但資訊量低。
- **Shell 呈現落差（列為待核問題）**：【F】`_render_ast` 不呼叫 `chrome.render_status`／`render_footer`，故 💼 頁**沒有 Status Bar 的 PREVIEW 標籤與頁尾 preview_banner（「Preview｜非正式頁面」）**，只剩 FAKE 橫幅。是否可接受（或需另補一條 PREVIEW 提示）待客戶／QA 確認；補的話屬 `chrome.py` 範圍內但需再驗。
- 【F】手機頁首每格已有「圖示／短標／標籤」三行結構（未掛載項）；可進的 demo 格改為「連結＋下方標記」。【未驗】兩者高度、五格等寬（±1px）、≥48px、190% 字放大、374／375／390／768 全寬度下的版面——本環境無瀏覽器，**這是條件 (6) 的必要實測，不過就落 A0**。

## c　S-a(7) 精確限縮例外（僅 💼 單頁；**不得全面移除任何守衛、不得刪除斷言、不得改 `rules.py`**）

**總則**：例外＝「斷言的期望值由『只有 🌍』精確改為『🌍＋💼(offline_demo)』，並**新增**斷言鎖住 FAKE 辨識」；🔍／🤖／⚙️ 仍不可進的斷言、🤖 不可建構為已掛載的斷言一律保留。新增的測試檔屬純新增。

| # | 守衛（檔::符號） | 現況斷言 | 僅允許的修改形狀 |
|---|---|---|---|
| 1 | `test_ui_v3_page_registry_guard.py::test_only_market_page_is_registered_so_no_empty_shell` | `registered_pages()` slugs `== ["mkt"]`；其餘頁 `registered is False` | 同函式內**兩處**期望都改：`registered_pages()` slugs 與 `assert_preview_ready()` slugs，皆由 `["mkt"]` 改 `["mkt","ast"]`（不得只改一處、不得刪任一條）；迴圈「其餘頁」改為排除 `mkt`、`ast`（exp／ai／set 仍須 `registered False` 且有 reason）；新增 `ast.data_mode=="offline_demo"`、`mkt.data_mode=="real"` |
| 2 | `test_ui_v3_assets_source_import_isolation.py::test_registry_has_no_new_page_and_preview_renderers_are_unchanged` | `registered == ["mkt"]` | 僅期望改 `["mkt","ast"]`（斷言數不減） |
| 3 | `test_ui_v3_navigation_shell.py::test_nav_items_are_the_five_pages_in_ia_order_and_only_registered_are_available` | 可進項 `== ["mkt"]` | 期望改 `["mkt","ast"]`；新增 `demo` 旗標斷言（僅 ast） |
| 4 | 同檔 `::test_unregistered_pages_are_visible_but_never_available_and_ai_never_available` | `("ast","exp","ai","set")` 皆 `available is False` | 迴圈改 `("exp","ai","set")`；新增 `ast.available is True and demo is True`；「記憶體內掛載」負控改以 `exp` 為對象（期望 `{"mkt","ast","exp"}`）；🤖 `ValueError` 斷言保留 |
| 5 | 同檔 `::test_top_nav_is_not_a_second_router_and_uses_all_five_approved_labels` | 可進項 `=={"mkt"}`、其餘皆不可進；短標列表 | 集合改 `{"mkt","ast"}`、「其餘」改排除兩者；**短標列表斷言一字不動**（＝條件 (3) 的機械證明）；`st.page_link`／`disabled_top_html` 原始碼斷言不動 |
| 6 | 同檔 `::test_app_has_exactly_one_navigable_page_and_no_empty_shell_pages`（AppTest） | page_link 數 2、label 集合 `{市場與趨勢,市場}`、title `["🌍 市場與趨勢"]` | 數量改 4、label 集合加 `我的資產`、`資產`；title 斷言不動（預設頁仍 🌍）；函式名含「exactly one」不再精確，只准改名不准改弱 |
| 7 | `test_ui_v3_preview_not_formal_guard.py::test_preview_main_fails_loud_when_registered_page_has_no_renderer` | 以 `ast` 當「已掛載但無 renderer」 | 僅把被突變的 slug `ast` 換為 `exp`；仍須 `pytest.raises(NotImplementedError)` |
| 8 | `test_ui_v3_top_nav_browser.py::test_mobile_top_nav_states_and_aria`（slow） | `cells[1:]` 皆 aria-disabled、無 href、文字含「開發中」；Tab 只聚焦 🌍 | `cells[0]`、`cells[1]` 為可進（href 非空、無 aria-disabled）；`cells[2:]` 保留原斷言（`_SOON` 去掉「資產」）；Tab 路徑 in-nav 恰 2 個（市場、資產）；**新增**：資產格旁有 `data-nav-demo` 標記、文字不含「開發中」、標記非 `aria-disabled` |

**重核「≥8 條」**：【F】實跑突變（registry 翻 ast＋adapters 常數＋`_render_ast`，無 streamlit）仍只轉紅 #1、#2（另 2 條既有環境失敗為缺 `requests`，與本案無關）；#3～#8 為讀碼推論未執行（需 streamlit／Chromium）。**本版仍是 8 條**，但**上一版的 4 條「FAKE 供應處」條件式守衛本版不再觸發**——因為封包放 `ui_v3/adapters/` 而非 `ui_v3/fixtures/`：【F】實跑確認 `fixtures_are_fake_guard`／`import_guard`／`preview_module_has_no_module_level…` 皆不轉紅（【I】`test_page_imports_no_fixtures_and_no_old_ui` 同理不紅，AppTest 未執行）。**不再需要放寬 fixtures 相關守衛**。
**必須「不改即過」的既有守衛**（驗收項；任何一條「需改才過」＝超出本例外，**回 Decision Gate 或落 A0**）：
- `test_ui_v3_top_nav_browser.py` 共 5 個測試函式：`test_mobile_top_nav_five_equal_visible_cells_at_least_48px`、`test_mobile_top_nav_states_and_aria`（＝§c #8，唯一允許改的）、`test_desktop_keeps_sidebar_and_hides_top_nav`、`test_top_nav_survives_190_percent_text_without_clipping_or_scrolling`、`test_top_nav_scrolls_away_with_the_page_flow`；其餘 4 條須不改即過。
- `test_ui_v3_market_page_browser.py`：`test_top_nav_s1_five_cells_mobile_and_sidebar_desktop` 與其 mutation／版面測試——🌍 頁頁首同樣會多出 demo 標記，須驗不破壞。
- `test_ui_v3_design_tokens.py::test_css_has_no_color_literal_outside_the_token_table`：`nav.shell_css()` 新樣式只准用 `theme.v(...)` token，不得色碼、不得 `rgb(`／`rgba(`。
- `test_ui_v3_preview_navigation_pages_guard.py::test_negative_control_extra_page_turns_red`：依賴 `app_preview.py` 內原字串 `navigation = st.navigation(list(st_pages.values())` 不得變。
- `poc_fund_search_preview`／`poc_fund_lookup_component_preview`／`poc_nas_diag_preview` 三組守衛：以子字串掃 `registry.py`、`app_preview.py`、`shell/*`、`pages/*`（禁字含 `fund_search`、`fund_lookup_component`、`nas_diag`、`NAS`、`poc`；registry 內連 `poc` 子字串都不能有），且整個 `ui_v3/**` 禁含 `poc/`。
- `tests/test_canonical_rule_consistency.py`：`nav.py` 須仍含 `TOP_KEY = "uv3-top-nav"`。
- `test_ui_v3_navigation_shell.py`：`test_css_switches_between_sidebar_and_top_nav_at_one_breakpoint`（新規則不得進入 `.st-key-uv3-top-nav{…}` 主塊、不得 `position:`／固定高度）；`test_shell_files_do_not_call_refresh_or_cache_clearing_or_fetch`（`nav.py`／`chrome.py` 不得含 `global_refresh_all`、`clear_all_caches`、`cache_clear`、`st.cache`、`fetch_url`、`session_state.pop`）；`test_shell_wording_lives_only_in_the_rules_table…`（`shell_*` 恰 19 鍵）；`test_old_provisional_shell_wording_is_banned…`。
- `test_ui_v3_preview_wording_guard.py::test_no_pending_text_equals_or_embeds_an_approved_registry_wording`：新字樣不得等於／內含已核准字樣，**且不得含符號 ◆◇⬜⛔◷**。
- `test_ui_v3_no_engineering_leak_guard.py`、`test_ui_v3_degraded_first_screen_budget.py`、`test_ui_v3_market_page_apptest.py`、`test_ui_v3_first_screen_c_and_wording_unify.py`：掃 `at.markdown`／sidebar 的名額與字樣——**標記文字不得含方向詞／工程詞，不得使用 `uv3-chip`／`uv3-evidence` class**（否則計入首屏名額或違 Shell 不放 chip 裁示）。
- `test_nothing_in_ui_v3_references_the_adapter…`：新檔與 docstring 不得含 `assets_source` 字樣。
【未驗】守衛搜尋只用字面詞，未列者可能仍漏；slow／browser 層其餘守衛未讀。

## d　檔案白名單／不得碰

**白名單（共 5 改＋1 新生產檔）**：`ui_v3/shell/registry.py`、`ui_v3/shell/nav.py`、`ui_v3/pages/chrome.py`、`ui_v3/viewmodels/preview_wording.py`、`ui_v3/app_preview.py`；新增 `ui_v3/adapters/assets_demo_envelope.py`（純常數函式，回傳與③相同的無值「市值基準未開放」封包；不 import 任何東西；檔名與 docstring 不得含 `assets_source`、`poc/`）。**同批必須更新的過時 docstring（在白名單檔內，不另增檔）**：`ui_v3/app_preview.py` 開頭「preview 不得顯示 fake 資料」（改為如實描述：🌍 為真實資料頁；💼 為離線示範頁、封包無任何值）；`ui_v3/shell/registry.py` 開頭「`registered` 是『已有核准 wireframe 且已實作的頁』」（補 `data_mode` 與 💼 以離線示範掛載的例外說明）。docstring 一律不得含 `poc/`、`poc`、`assets_source`。**測試**：改 §c 的 8 條；新增 `tests/ui_v3/test_ui_v3_assets_demo_mount.py`（見 §e），其中**新增一條機械守衛專鎖新檔**：封包 `evidence is None`、`holdings` 無列、封包遞迴掃描無金額／持倉值欄位（以 `build_assets_page` 結果驗 `a50` 為 status-only、`a10.basis_value is None`）。
【R】封包放 `adapters/` 的理由：`app_preview` 禁 import `ui_v3.fixtures`、`ui_v3` 禁含 `poc/`；放 adapters 不觸發任何 fixtures／層級守衛。【I】代價＝adapters 層語意本是「真實取數轉接」，此檔是無值示範封包，須在 docstring 明寫；替代方案「封包直接寫在 `_render_ast` 函式內」亦不觸發守衛但較難測，本組未實測。

**不得碰**：frozen `docs/v2/44_fund_ui_ssot.md` 與 `docs/v2/44*`、其他 `docs/**` 類檔案（文件同步另批）；`shared/ui_semantics/rules.py`；`ui_v3/viewmodels/assets_page.py`、`assets_preview_wording.py`、`ui_v3/adapters/assets_page.py`、`assets_source.py`、`ui_v3/pages/assets.py`（renderer／VM／adapter 一字不動）；`ui_v3/fixtures/**`；`poc/**`；`services/`、`repositories/`、`shared/`（rules 外）、`infra/`；`ui_v2/**`、`app.py`、`ui/**`；`.github/**`；正式 registry 以外的頁（🔍／🤖／⚙️ 仍未掛載）；任何 `st.secrets`／環境變數／網路／Sheet 存取。

## e　驗收清單（作者自編條件 (6)；全部需 exact-head CI 四 lane success＋獨立 QA）

1. **作者自編條件 (1) 的機械鎖**（新測試）：渲染 `_render_ast` 的頁面文字不含「成本」、不含任何基金名稱／代碼／幣別／單位數；`a10.basis_value is None`；封包 `evidence is None`；無 `data-a50="rows"`、`<details>` 恰 1 個（A60）；首屏標記恰 5。封包 drift 測試：`blocked_envelope() == tests/ui_v3/assets_page_support.market_blocked_result()`（【F】該函式存在；實跑兩份 poc／adapters 封包相等為 True）。
2. **AppTest**：`AppTest.from_function` 直接跑 `_render_ast`（【I】`AppTest` 對 `st.navigation` 頁切換的支援依 Streamlit 版本，未驗，不以它切頁）；socket 攔截下無網路、不讀憑證環境變數（沿用 poc 既有手法）；橫幅在 `st.title` 之前；頁面無 engineering leak。
3. **導覽 AppTest**：`render_navigation` 下 `ast` 的 page_link 存在、短標「資產」「我的資產」未變；標記元素有 `data-nav-demo`、**無 `aria-disabled`、無 `uv3-nav-soon`／`uv3-tn-soon`**；`exp`／`ai`／`set` 仍是 soon 且 aria-disabled。
4. **Chromium（slow lane；沿用 `test_ui_v3_top_nav_browser.py` 的 `base_and_browser`、`_MEASURE`）**：在 374／375／390／768 驗五格全可見、等寬（±1px）、每格 ≥48px、文字不被裁、整頁與頁首無橫向溢出；190% 字放大五格仍可見（含 demo 標記不被裁）；≥769／1280 側欄在、頁首隱藏、側欄 💼 項可點且旁有標記；進入 `/ast`（url_path）在 **390 與 1280** 量測：橫幅在頁頂、無橫向溢出、A60 `<details>` 高度 48px 可開合且不產生 websocket client→server 訊息、首屏標記 5。
5. **字樣**：新 PendingWording 皆有來源標示、不等於／不內含已核准字樣、不進 `rules.py`、不以 `shell_` 開頭、source 不含 `poc/`。
6. **獨立 QA**：治理／守衛修改＋Shell 變動屬高風險，≥1 組非作者獨立稽核（`DEC-2026-10-16-05`）；開工前依 `PROJECT_RULES.md` §5.1 重評 Model／Effort（該表本組未讀【未驗】）。
7. **完成宣稱上限**：只能寫「fixture／Chromium 層」，不得寫 Cloud／真機／像素驗收、不得寫 💼 正式完成；BL-0544 的 Cloud／非作者 QA 缺口不因此關閉。
8. **落 A0 的觸發（作者自編條件 (8)；任一成立即停、保留隔離預覽、回報）**：需改 VM／adapter／renderer／rules.py；五格量測不過且唯一解法是改短標、縮小觸控區或移除標記；§c 任一守衛需超出「僅允許的修改形狀」；標記無法與 soon 語意區隔；新增檔必須含 `poc/` 或 import fixtures；需任何真實資料／Sheet／網路。

## f　三欄區分

| 總管建議（執行組讀法，【R】可被推翻） | 使用者已方向核准（〔待核〕，ChatGPT 轉達，非逐字） | 仍待使用者正式核准與施工授權 |
|---|---|---|
| 固定情境③（X1）；封包放 `adapters/`；標記為連結兄弟元素、獨立 class、不帶 aria-disabled；導覽標記候選詞「FAKE」；橫幅沿用 harness 既有字串作 PendingWording；5 改＋1 新檔白名單；§c 逐條形狀；§e 落 A0 觸發 | 採 A1a 安全修正版；Q2 採「獨立示範標記」方向；條件 (1)～(8)（**作者自編編號，非來源編號**；不顯示假持股／假金額／個人設定值、導覽＋頁頂辨識且不混用 soon、不改短標、不接真實資料、僅 💼 單頁精確限縮 S-a(7)、必要驗收、優先既有元件、不滿足即 A0） | ① 正式放寬 `DEC-2026-11-19-01` S-a(7)，範圍＝§c 八條守衛、僅限所列形狀、僅 💼；② 掛載本身（registry／`app_preview` 修改）；③ **新字樣**：頁頂橫幅、導覽標記（含詞「FAKE」或其他）屬 PendingWording，S-a 只給「沿用既有來源」方向，**逐字內容與可追溯來源須確認**；④ `PageSlot.data_mode` 與 `NavItem.demo` 的新增（Shell 結構）；⑤ 新增 `adapters/assets_demo_envelope.py`；⑥ 施工授權與 Model／Effort（Change Gate） |

## g　待使用者核准的最小差異（清單）

1. 授權 💼 單頁掛載（`registered=True`、`data_mode="offline_demo"`），固定情境③（頁面無任何 FAKE 持股、金額、個人設定值）。
2. 授權精確限縮 S-a(7)：僅改 §c 的 8 條守衛，且僅限所列「斷言期望值 mkt→mkt＋ast、並新增 FAKE 辨識斷言」的形狀；不得刪斷言、不得改 `rules.py`、不得動其他頁。
3. 確認或給定兩個暫行字樣：頁頂橫幅（候選＝harness 既有字串）、導覽標記（候選＝「FAKE」；若要「示範」須明確核准該新詞）。
4. 同意新增 Shell 結構：`PageSlot.data_mode`、`NavItem.demo`、`chrome` 標記與橫幅函式、`adapters/assets_demo_envelope.py`。**客戶須明確知悉一項取捨**：示範封包放 `ui_v3/adapters/` 而非 `ui_v3/fixtures/`，是為了不必放寬 fixtures 相關守衛、符合「`app_preview` 不得 import fixtures」；但這與守衛原意（FAKE 資料只住 `fixtures/` 並帶 `FAKE_FIXTURE` 標記）有張力。緩解：封包無任何值（`evidence=None`），並以專屬機械守衛鎖定；`app_preview` 與 `registry` 的過時 docstring 同批更新（§d）。若客戶不接受此取捨，替代＝放 `fixtures/` 並另行放寬 4 條 fixtures／import 守衛（§c 舊版 4 條，範圍更大）。
4b. 確認或接受：💼 頁無 Status Bar PREVIEW 標籤與頁尾 preview 提示，只剩 FAKE 橫幅（§b）；以及橫幅／導覽標記選字（FAKE／示範）的語意張力。
5. 同意落 A0 的客觀觸發（§e-8），並同意 390／1280 五格 Chromium 量測為 gate。
6. 施工開工前 Model／Effort 切換與獨立 QA 組數。
（若客戶不接受 3～5 任一項 → A0：保留隔離 poc 預覽，💼 無其他安全切片。）

## h　仍未驗／限制

1. 本環境無 streamlit／瀏覽器：§c #3～#8、§e 的 AppTest／Chromium 項均**未執行**，為讀碼推論；手機五格加標記後的實際版面完全未量測（本版最大技術風險）。
2. 突變實跑只涵蓋 fast 靜態守衛，且以最小示意實作（registry＋常數檔＋`_render_ast`），未含 `nav.py`／`chrome.py`／wording 的變更；這些變更對其餘守衛的影響為讀碼推論。
3. ③ 渲染結果取自 `page_html` 純函式（與 runtime 同碼），未經 Streamlit 實際渲染；Cloud／真機未驗。
4. 「③＝production 載入端現況」引自 BACKLOG／evidence，本組未重驗；#1286 落檔的上一版卡本組未重讀。
5. 所有客戶方向皆〔待核〕轉述；導覽標記字詞、橫幅字樣皆未核准；`AppTest` 對 `st.navigation` 切頁支援未驗。
6. 守衛清單以字面詞搜尋，可能漏列；slow／browser 層除 `top_nav_browser` 外未讀。
