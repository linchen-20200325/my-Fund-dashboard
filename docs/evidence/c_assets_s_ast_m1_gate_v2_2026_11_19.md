# 💼 S-AST-M1 修正版 Gate（v2；A1a 安全修正版＋獨立示範標記）

> **兩點先講清楚**：(i) **「改固定情境③」是作者（執行組）推薦【R】，不是客戶核准的 A1a 內容**——客戶方向（〔待核〕轉述）只含「A1a 安全修正版」與條件，未指定情境；(ii) 本卡內的條件編號 (1)～(8)（以及 §a／§b／§e／§f 引用的「條件 (n)」）是**作者自編、非來源編號**，與 `DEC-2026-11-19-01` S-a(1)～(7) 的條號無關；提到 S-a 時一律寫「S-a(n)」。

> **卡狀態（2026-11-20 起）**：單組草稿；稽核 1 組（與作者共享派工來源）；修正後未複驗。2026-11-20 稽核結果見文末「2026-11-20 獨立稽核後修正」節（[F]／[I]／NV 標記），其更正就地以刪除線＋新句呈現。

> 單組執行組唯讀草稿，**未經第二組獨立複驗**；不是授權、不是 DEC、不改 repo（突變實跑只在 `git archive` 暫存副本）。
> 標記：【F】事實（讀檔／實跑）、【I】推論、【R】執行組推薦（可被推翻）、【未驗】。不寫行號。
> **裁示來源**：下列「已方向核准」皆為 ChatGPT 總管轉達、客戶經其轉述〔待核〕，**非客戶逐字、repo 無原文**；本卡不把方向寫成逐字規格，不捏造引言。
> ~~基準 `origin/main` `eb08c5fc`（重核）。【F】自 `0cfd86b9` 起 `ui_v3`／`poc`／`tests` 無任何變動，僅 docs（#1285、#1286；#1286 已把上一版卡落為 `docs/evidence/c_assets_s_ast_m1_gate_card_2026_11_19.md`，本組未重讀該檔）。~~ **（2026-11-20 有意識的更正，不是漏刪：原句在 `eb08c5fc` 當時為真；被推翻的是它的前提——#1299 與 #1298 之後 `ui_v3`／`tests` 已有變動，見文末 M1。兩邊理由：舊基準讓本卡讀碼有確定版本，仍有追溯價值；但「無變動」「一字不動」已不成立，沿用會讓人在過期基準上施工。）** 現行基準：`origin/main` `72b64531`（2026-11-20 查 `git log origin/main`；施工前須再取最新 SHA 並重核）。**原 A1a（固定 ⑤）作廢，不得直接施工。**

## 0　結論

【F】**A10 假「成本」不需改 viewmodel／adapter／renderer／fixture 內容即可消除**：改固定既有情境 **③「市值基準未開放」**（`evidence=None`）。我在暫存副本用真實 `build_assets_page`＋`page_html`（純函式，與 runtime 同碼）渲染：③ 頁面文字為「來源 ⬜ 無法判定｜資產配置 ◇ 資料未備｜**基準 ◇ 資料未備**｜四格 ◇ 資料未備｜完整持倉 ⬜ 無法判定｜A60：略過分頁數／列數 ◇ 資料未備、⬜ 無法判定」。無基金名、無持倉列、無「成本」、無任何設定值；首屏標記 5 個、`<details>` 只有 A60 一個（A50 為純文字 status-only）。
【R】**採 ③，條件 (1) 可滿足且屬「優先用既有元件」**（2026-11-20 呼應稽核 M2：11 個既有情境中**實質只有 ③ 可滿足條件 (1)**〔其餘走 `fake_evidence` 預設「成本」〕，故「採 ③」是唯一不需改程式的可行解，不是從等價選項中挑選；且 ③ 下 A50／A60 版面在 Preview 看不到內容，見 §i M2）。導覽／頁頂標記需新增少量 Shell 程式（§b），評估後仍屬可控；若 §b 的 Chromium 五格量測不過，依條件 (8) 落 **A0**。

## a　A10 假成本處置（可判定方案；條件編號為作者自編）

| 方案 | 做法 | 動到 | 顯示 | 判定 |
|---|---|---|---|---|
| **X1（推薦；實質為唯一不改程式的可行解，見 §i M2）固定情境③** | `_render_ast` 吃與③相同的封包；基準列走既有「set 但無值」路徑 | **無 VM／adapter／renderer／fixture 內容變更**；新增一個純常數函式（見 §d）＝既有③封包的複本，以 drift 測試鎖等於 `tests/ui_v3/assets_page_support.py::market_blocked_result()` | 基準 `◇ 資料未備`（已核准字樣） | **滿足條件 (1)、(7)** |
| X2 ⑤＋基準「未設定」 | 在⑤封包把 `settings_status.alo_basis` 設 `unset` | 僅 fixture 層一個鍵；實渲染：基準 `⬜ 未設定`（`user_param_unset`，已核准字樣） | 不顯示設定值，但**宣稱「使用者尚未設定基準」＝仍是對個人設定狀態的 FAKE 陳述** | 可行但較差；僅在客戶要「選定來源」敘事時備用 |
| X3 改 renderer／VM 隱藏基準列 | 動 `ui_v3/pages/assets.py` 或 adapter | VM／renderer＋既有 renderer／adapter 測試 | — | **不滿足「優先既有」，且~~動已驗收程式~~（2026-11-20 更正：`assets.py` 已於 #1299 `adb760e2` 改過〔`st.title(..., anchor=False)`、A10 `h4`→`div role=heading`〕，故「已驗收、未動」之說不實（**有意識的更正，不是漏刪**；兩邊理由：舊句「動已驗收程式」在 `eb08c5fc` 當時為真，且「不輕動已驗收碼」的謹慎仍成立；被推翻的是「已驗收、未動」這個前提）；仍不採的理由改為「不滿足優先既有」＋改它會牽動已被 #1299 重新量測過的版面證據）；不採** |
| X4 維持⑤（顯示「成本」） | — | — | FAKE 個人設定值 | **違反條件 (1)，禁止** |

【F】已知舊落差照舊（`blocked_basis_state_without_value`：③ 的基準狀態是 set 但無值，顯示 `◇ 資料未備`）——poc README 已登記，本版不處置。【I】③ 的 A10 原因句「配置比較的計算口徑尚未核准，故不提供結果」為既有 PendingWording，非核准字樣。
【F】③ 是否等同「production 載入端現況」：BACKLOG／gap supplement 記載載入端在市值基準下一律 blocked、不讀持倉（本組未重驗）。~~【I】故③頁面是誠實的「現況空狀態」，不是假資料頁；~~（2026-11-20 有意識的更正，不是漏刪：此為建立在未重驗載入端記載上的推論，不應寫成結論；見 §i M3。舊句理由——③ 確無任何假值——仍成立，被權衡掉的是「等於現況」這半句。）代價＝**可見進展僅限「💼 在 Preview 可進入、版面與缺值語意可審」，沒有任何資料。**

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
- **語意張力（須客戶選字）**：~~③ 頁面本身沒有任何假資料（是誠實的現況空狀態）~~〔2026-11-20 **有意識的更正，不是漏刪**：「③ 頁面沒有任何假資料」仍為 [F]（封包 `evidence=None`）；被推翻的是「是誠實的現況空狀態」——它是 [I]，依賴未重驗的「production 載入端在市值基準下一律 blocked」，固定封包是否等於現況為 NV，見 §i M3。兩邊理由：舊句想強調頁面無假值，這點成立；但「現況」二字會把推論寫成事實〕③ 頁面本身沒有任何假資料，但橫幅／標記寫「FAKE」，可能被讀成「資料壞了／這是假的」而非「離線示範、尚未接資料」。候選：「FAKE」（可追溯、但易反讀）／「示範」（語意較貼切、但是新詞，須客戶核准字樣）。橫幅內文沿用 harness 字串含「非真實持倉」，在無持倉的③ 頁仍為真，但資訊量低。
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

**重核「≥8 條」**（2026-11-20 加註：僅 #1、#2 為實跑；#3～#8 為讀碼推論、「僅此 8 條」為單組全稱句未驗，且另有未列入的受影響測試，見 §i Should-Fix 3）：【F】實跑突變（registry 翻 ast＋adapters 常數＋`_render_ast`，無 streamlit）仍只轉紅 #1、#2（另 2 條既有環境失敗為缺 `requests`，與本案無關）；#3～#8 為讀碼推論未執行（需 streamlit／Chromium）。**本版仍是 8 條**，但**上一版的 4 條「FAKE 供應處」條件式守衛本版不再觸發**——因為封包放 `ui_v3/adapters/` 而非 `ui_v3/fixtures/`：【F】實跑確認 `fixtures_are_fake_guard`／`import_guard`／`preview_module_has_no_module_level…` 皆不轉紅（【I】`test_page_imports_no_fixtures_and_no_old_ui` 同理不紅，AppTest 未執行）。**不再需要放寬 fixtures 相關守衛**。
**必須「不改即過」的既有守衛**（驗收項；任何一條「需改才過」＝超出本例外，**回 Decision Gate 或落 A0**）：
- `test_ui_v3_top_nav_browser.py` 共 5 個測試函式：`test_mobile_top_nav_five_equal_visible_cells_at_least_48px`、`test_mobile_top_nav_states_and_aria`（＝§c #8，唯一允許改的）、`test_desktop_keeps_sidebar_and_hides_top_nav`、`test_top_nav_survives_190_percent_text_without_clipping_or_scrolling`、`test_top_nav_scrolls_away_with_the_page_flow`；其餘 4 條須不改即過。
- `test_ui_v3_market_page_browser.py`：`test_top_nav_s1_five_cells_mobile_and_sidebar_desktop` 與其 mutation／版面測試——🌍 頁頁首同樣會多出 demo 標記，須驗不破壞。
- `test_ui_v3_design_tokens.py::test_css_has_no_color_literal_outside_the_token_table`：`nav.shell_css()` 新樣式只准用 `theme.v(...)` token，不得色碼、不得 `rgb(`／`rgba(`。
- `test_ui_v3_preview_navigation_pages_guard.py::test_negative_control_extra_page_turns_red`：依賴 `app_preview.py` 內原字串 `navigation = st.navigation(list(st_pages.values())` 不得變。
- `poc_fund_search_preview`／`poc_fund_lookup_component_preview`／`poc_nas_diag_preview` 三組守衛：以子字串掃 `registry.py`、`app_preview.py`、`shell/*`、`pages/*`（禁字含 `fund_search`、`fund_lookup_component`、`nas_diag`、`NAS`、`poc`；registry 內連 `poc` 子字串都不能有），且整個 `ui_v3/**` 禁含 `poc/`。
- `tests/test_canonical_rule_consistency.py`：`nav.py` 須仍含 `TOP_KEY = "uv3-top-nav"`。
- `test_ui_v3_navigation_shell.py`：`test_css_switches_between_sidebar_and_top_nav_at_one_breakpoint`（新規則不得進入 `.st-key-uv3-top-nav{…}` 主塊、不得 `position:`／固定高度）；`test_shell_files_do_not_call_refresh_or_cache_clearing_or_fetch`（`nav.py`／`chrome.py` 不得含 `global_refresh_all`、`clear_all_caches`、`cache_clear`、`st.cache`、`fetch_url`、`session_state.pop`）；`test_shell_wording_lives_only_in_the_rules_table…`（`shell_*` 恰 19 鍵）；`test_old_provisional_shell_wording_is_banned…`。
- `test_ui_v3_preview_wording_guard.py::test_no_pending_text_equals_or_embeds_an_approved_registry_wording`：新字樣不得等於／~~內含~~已核准字樣，**且不得含符號 ◆◇⬜⛔◷**。（2026-11-20 **有意識的更正，不是漏刪**：守衛實際只檢整串相等與符號，不檢子字串內含，見 §i Should-Fix 6。兩邊理由：舊句「不得內含」作為作者自律慣例仍有道理，但把它寫成守衛要求不實；被推翻的是「守衛會檢」這個前提。）
- `test_ui_v3_no_engineering_leak_guard.py`、`test_ui_v3_degraded_first_screen_budget.py`、`test_ui_v3_market_page_apptest.py`、`test_ui_v3_first_screen_c_and_wording_unify.py`：掃 `at.markdown`／sidebar 的名額與字樣——**標記文字不得含方向詞／工程詞，不得使用 `uv3-chip`／`uv3-evidence` class**（否則計入首屏名額或違 Shell 不放 chip 裁示）。
- `test_nothing_in_ui_v3_references_the_adapter…`：新檔與 docstring 不得含 `assets_source` 字樣。
【未驗】守衛搜尋只用字面詞，未列者可能仍漏；slow／browser 層其餘守衛未讀。

## d　檔案白名單／不得碰

**白名單（共 5 改＋1 新生產檔）**：`ui_v3/shell/registry.py`、`ui_v3/shell/nav.py`、`ui_v3/pages/chrome.py`、`ui_v3/viewmodels/preview_wording.py`、`ui_v3/app_preview.py`；新增 `ui_v3/adapters/assets_demo_envelope.py`（純常數函式，回傳與③相同的無值「市值基準未開放」封包；不 import 任何東西；檔名與 docstring 不得含 `assets_source`、`poc/`）。**同批必須更新的過時 docstring（在白名單檔內，不另增檔）**：`ui_v3/app_preview.py` 開頭「preview 不得顯示 fake 資料」（改為如實描述：🌍 為真實資料頁；💼 為離線示範頁、封包無任何值）；`ui_v3/shell/registry.py` 開頭「`registered` 是『已有核准 wireframe 且已實作的頁』」（補 `data_mode` 與 💼 以離線示範掛載的例外說明）。docstring 一律不得含 `poc/`、`poc`、`assets_source`。**測試**：改 §c 的 8 條；新增 `tests/ui_v3/test_ui_v3_assets_demo_mount.py`（見 §e），其中**新增一條機械守衛專鎖新檔**：封包 `evidence is None`、`holdings` 無列、封包遞迴掃描無金額／持倉值欄位（以 `build_assets_page` 結果驗 `a50` 為 status-only、`a10.basis_value is None`）。
【R】封包放 `adapters/` 的理由：`app_preview` 禁 import `ui_v3.fixtures`、`ui_v3` 禁含 `poc/`；放 adapters 不觸發任何 fixtures／層級守衛。【I】代價＝adapters 層語意本是「真實取數轉接」，此檔是無值示範封包，須在 docstring 明寫；替代方案「封包直接寫在 `_render_ast` 函式內」亦不觸發守衛但較難測，本組未實測。

**不得碰**：frozen `docs/v2/44_fund_ui_ssot.md` 與 `docs/v2/44*`、其他 `docs/**` 類檔案（文件同步另批）；`shared/ui_semantics/rules.py`；`ui_v3/viewmodels/assets_page.py`、`assets_preview_wording.py`、`ui_v3/adapters/assets_page.py`、`assets_source.py`、`ui_v3/pages/assets.py`（renderer／VM／adapter ~~一字不動~~〔2026-11-20 更正：`assets.py` 在 `eb08c5fc` 之後已被 #1299 改動；本卡的意思是「本批施工不再動它」，不是「它自卡片基準起沒變」。舊句在 `eb08c5fc` 時為真，被推翻的是前提〕）；`ui_v3/fixtures/**`；`poc/**`；`services/`、`repositories/`、`shared/`（rules 外）、`infra/`；`ui_v2/**`、`app.py`、`ui/**`；`.github/**`；正式 registry 以外的頁（🔍／🤖／⚙️ 仍未掛載）；任何 `st.secrets`／環境變數／網路／Sheet 存取。

## e　驗收清單（作者自編條件 (6)；全部需 exact-head CI 四 lane success＋獨立 QA）

1. **作者自編條件 (1) 的機械鎖**（新測試）：渲染 `_render_ast` 的頁面文字不含「成本」、不含任何基金名稱／代碼／幣別／單位數；`a10.basis_value is None`；封包 `evidence is None`；無 `data-a50="rows"`、`<details>` 恰 1 個（A60）；首屏標記恰 5。封包 drift 測試：`blocked_envelope() == tests/ui_v3/assets_page_support.market_blocked_result()`（【F】該函式存在；實跑兩份 poc／adapters 封包相等為 True）。
2. **AppTest**：`AppTest.from_function` 直接跑 `_render_ast`（【I】`AppTest` 對 `st.navigation` 頁切換的支援依 Streamlit 版本，未驗，不以它切頁）；socket 攔截下無網路、不讀憑證環境變數（沿用 poc 既有手法）；橫幅在 `st.title` 之前；頁面無 engineering leak。
3. **導覽 AppTest**：`render_navigation` 下 `ast` 的 page_link 存在、短標「資產」「我的資產」未變；標記元素有 `data-nav-demo`、**無 `aria-disabled`、無 `uv3-nav-soon`／`uv3-tn-soon`**；`exp`／`ai`／`set` 仍是 soon 且 aria-disabled。
4. **Chromium（slow lane；沿用 `test_ui_v3_top_nav_browser.py` 的 `base_and_browser`、`_MEASURE`；〔2026-11-20 補〕現有 `_MEASURE` 量不到標記，量測必須涵蓋標記元素本身：標記寬高、不被裁、不遮蓋或擠壓連結可點區、連結仍 ≥48px，另在手機五格與側欄兩種版面都量）**：在 374／375／390／768 驗五格全可見、等寬（±1px）、每格 ≥48px、文字不被裁、整頁與頁首無橫向溢出；190% 字放大五格仍可見（含 demo 標記不被裁）；≥769／1280 側欄在、頁首隱藏、側欄 💼 項可點且旁有標記；進入 `/ast`（url_path）在 **390 與 1280** 量測：橫幅在頁頂、無橫向溢出、A60 `<details>` 高度 48px 可開合且不產生 websocket client→server 訊息、首屏標記 5。
5. **字樣**：新 PendingWording 皆有來源標示、不等於~~／不內含~~已核准字樣、不含符號、不進 `rules.py`（「不內含」2026-11-20 **有意識的更正，不是漏刪**：守衛不檢，見 §i；兩邊理由：舊句「不內含」作為作者自律慣例仍有道理，保留為建議；但守衛實際只檢整串相等與符號、不檢子字串，把它寫成守衛強制不實；被推翻的是「守衛會檢」這個前提）、不以 `shell_` 開頭、source 不含 `poc/`。
6. **獨立 QA**：治理／守衛修改＋Shell 變動屬高風險，≥1 組非作者獨立稽核（`DEC-2026-10-16-05`）；開工前依 `PROJECT_RULES.md` §5.1 重評 Model／Effort（該表本組未讀【未驗】）。
7. **完成宣稱上限**：只能寫「fixture／Chromium 層」，不得寫 Cloud／真機／像素驗收、不得寫 💼 正式完成；BL-0544 的 Cloud／非作者 QA 缺口不因此關閉。
8. **落 A0 的觸發（作者自編條件 (8)；任一成立即停、保留隔離預覽、回報）**：需改 VM／adapter／renderer／rules.py；五格量測不過且唯一解法是改短標、縮小觸控區或移除標記；§c 任一守衛需超出「僅允許的修改形狀」；標記無法與 soon 語意區隔；新增檔必須含 `poc/` 或 import fixtures；需任何真實資料／Sheet／網路。

## f　三欄區分

| 總管建議（執行組讀法，【R】可被推翻） | 使用者已方向核准（〔待核〕，ChatGPT 轉達，非逐字） | 仍待使用者正式核准與施工授權 |
|---|---|---|
| 固定情境③（X1）；封包放 `adapters/`；標記為連結兄弟元素、獨立 class、不帶 aria-disabled；導覽標記候選詞「FAKE」；橫幅沿用 harness 既有字串作 PendingWording；5 改＋1 新檔白名單；§c 逐條形狀；§e 落 A0 觸發 | 採 A1a 安全修正版；Q2 採「獨立示範標記」方向；條件 (1)～(8)（**作者自編編號，非來源編號**；不顯示假持股／假金額／個人設定值、導覽＋頁頂辨識且不混用 soon、不改短標、不接真實資料、僅 💼 單頁精確限縮 S-a(7)、必要驗收、優先既有元件、不滿足即 A0） | ① 正式放寬 `DEC-2026-11-19-01` S-a(7)，範圍＝§c 八條守衛、僅限所列形狀、僅 💼；② 掛載本身（registry／`app_preview` 修改）；③ **新字樣**：頁頂橫幅、導覽標記（含詞「FAKE」或其他）屬 PendingWording，S-a 只給「沿用既有來源」方向，**逐字內容與可追溯來源須確認**；④ `PageSlot.data_mode` 與 `NavItem.demo` 的新增（Shell 結構）；⑤ 新增 `adapters/assets_demo_envelope.py`；⑥ 施工授權與 Model／Effort（Change Gate） |

## g　待使用者核准的最小差異（清單）

> **2026-11-20 重寫**：舊清單（原 1～6 與 4b）保留如下並加刪除線——**有意識的更正，不是漏刪**。兩邊理由：舊清單把多件事捆成「同意 3～5 項」，客戶只能整批答；仍成立的是每一項待核內容本身。被權衡掉的是捆綁形式。新題序 Q1→Q5，客戶一題一答；Q1 否決則 Q2～Q5 不必問。以下推薦皆【R】可被推翻、非客戶裁示。

~~1. 授權 💼 單頁掛載（`registered=True`、`data_mode="offline_demo"`），固定情境③（頁面無任何 FAKE 持股、金額、個人設定值）。~~
~~2. 授權精確限縮 S-a(7)：僅改 §c 的 8 條守衛……（原文略，內容併入新 Q3）~~
~~3. 確認或給定兩個暫行字樣：頁頂橫幅、導覽標記（候選「FAKE」；「示範」須核准新詞）。~~ → 併入新 Q2
~~4. 同意新增 Shell 結構……（含 `adapters/` vs `fixtures/` 取捨；若不接受，替代＝放 `fixtures/` 並另行放寬 4 條 fixtures／import 守衛）~~ → 併入新 Q4
~~4b. 確認或接受：💼 頁無 Status Bar PREVIEW 標籤與頁尾 preview 提示，只剩 FAKE 橫幅；以及選字語意張力。~~ → 併入新 Q1／Q2（並補：側欄「資料狀態」區與「更新資料」CTA 也缺；`page_icon="🌍"` 寫死、瀏覽器分頁圖示與頁籤標題為 🌍 市場頁的）
~~5. 同意落 A0 的客觀觸發（§e-8），並同意 390／1280 五格 Chromium 量測為 gate。~~ → 併入新 Q3／Q5
~~6. 施工開工前 Model／Effort 切換與獨立 QA 組數。~~ → 新 Q5

**共通已知答案**：方向（〔待核〕轉述，非客戶逐字）＝採 A1a 安全修正版＋獨立示範標記；`DEC-2026-11-19-09` 區分欄 1 的方向核准與「仍待核准」欄須分開讀；「③ 是作者推薦、非客戶核准」；條件 (1)～(8) 為作者自編；`DEC-2026-11-19-01` S-a(7) 的放寬尚未核准。

**Q1　要不要掛 💼（情境③＋FAKE 橫幅）？**
- 已知答案：A1a 方向已轉述核准；固定情境 ③ 是作者推薦，不是客戶指定（§0、§i M2：11 個情境中實質只有 ③ 可滿足條件 (1)）。
- 待答的五個子點（拆開，客戶可逐點答）：
  - (a) ③ 空狀態＋FAKE 橫幅的語意張力（§b、§i M3）；
  - (b) ③ 下 A50／A60 已驗收版面看不到內容（§i M2）；
  - (c)「不做空殼」與 registered 定義（registry docstring、`DEC-2026-10-27-10`／`-12`、`REASON_WIREFRAME_PENDING`）是否相容；
  - (d) Preview URL 可見對象（`DEC-2026-11-19-01` 未驗清單）；
  - (e) 💼 頁缺 Status Bar PREVIEW 標籤、頁尾提示、側欄資料狀態區、更新資料 CTA，且 `page_icon`／分頁標題為 🌍。
- 選項：a 掛 ③；b 掛但改 X2（⑤＋基準未設定；需改 fixture 層，**而 §d 不得碰 `ui_v3/fixtures`／`poc`，故需另放寬 fixtures／poc 邊界**，範圍更大）；c 不掛（A0，保留隔離 poc 預覽）。
- 推薦：【R】僅在客戶接受 (a)(b)(c)(e) 後選 a，否則 c；可被推翻。
- 風險：把推論（③＝現況）當事實；空殼疑慮；可見對象未驗。

**Q2　導覽標記與頁頂橫幅字樣**
- 已知答案：S-a(2)「不創第二套無來源文案」；已核准的 PREVIEW 語意是整 App 預覽，不借用；字樣最終未核。
- 選項：a「FAKE」（可追溯 harness、易被反讀為「資料壞了」）；b「示範」（較貼切，新詞須客戶核准）；c 其他。橫幅沿用 harness 既有字串。
- 推薦：【R】a 暫行、可被推翻；若客戶在意反讀則 b。
- 風險：新字樣為 PendingWording，守衛只檢整串相等與符號（§i Should-Fix 6），其餘靠人工。

**Q3　S-a(7) 例外守衛的修改形狀**
- 已知答案：S-a(7) 現況不可放寬；§c 逐條形狀僅限 💼、不刪斷言、不改 `rules.py`。
- 選項：a 僅改 §c 所列斷言期望值（mkt→mkt＋ast）並新增 FAKE 辨識；b 不放寬（＝A0）。
- 推薦：【R】a；可被推翻。
- 風險：「8 條」#3～#8 為讀碼推論、全稱句未驗；`test_not_yet_open_label…` 未列入；§c 以 `eb08c5fc` 讀，新基準未重核（§i M1）；任一守衛需超出所列形狀即落 A0。

**Q4　Shell 新增結構與放置位置**
- 已知答案：新增 `PageSlot.data_mode`、`NavItem.demo`、chrome 標記與橫幅函式；封包放 `adapters/` 或 `fixtures/` 是取捨。
- 選項：a 封包放 `adapters/`（不放寬 fixtures 守衛；與「FAKE 只住 fixtures」原意有張力，以專屬機械守衛鎖）；b 放 `fixtures/` 並另行放寬 4 條 fixtures／import 守衛（範圍更大）。
- 推薦：【R】a；可被推翻。
- 風險：adapters 層語意被稀釋；手機五格加標記後的版面完全未量測（CSS 兄弟元素、`display:flex`；量測須涵蓋標記本身，§e-4）。

**Q5　施工授權與 Model／Effort**
- 已知答案：Change Gate；高風險至少 1 組真獨立稽核（`DEC-2026-10-16-05`）；完成宣稱上限＝fixture／Chromium 層。
- 選項：授權／不授權；Model／Effort 於開工前依 `PROJECT_RULES.md` §5.1 重評（本組未讀，NV）。
- 推薦：【R】Q1～Q4 全過後才問；可被推翻。
- 風險：落 A0 觸發條件（§e-8）；BL-0544 Cloud／非作者 QA 缺口不因此關閉。

（若客戶不接受 Q1～Q4 任一項 → A0：保留隔離 poc 預覽，💼 無其他安全切片。）

## 附：獨立最小 Gate 草稿（S7；只寫入卡，不向使用者提；【R】可被推翻）
~~（2026-11-20 第一版：單題「是否授權 💼 掛載……」，選項 A 掛 ③／B 掛 X2／C 不掛。）~~ **有意識的更正，不是漏刪**；兩邊理由：第一版把 Q1～Q5 壓成單題，仍可作 Q1 的摘要；被權衡掉的是它沒涵蓋順序與送客戶分批，且 B 選項（X2）漏寫需放寬 fixtures／poc 邊界。以下為重寫版。
- **問題**：是否授權 💼 以離線示範頁掛載（固定情境③＋獨立示範標記），並放寬 S-a(7) 於 💼 單頁？拆為 Q1～Q5（§g）。
- **已知答案**：`DEC-2026-11-19-09` 區分欄 1（方向核准，〔待核〕轉述）＝A1a 安全修正版＋獨立示範標記；「③ 是作者推薦，非客戶核准」；條件 (1)～(8) 作者自編；S-a(7) 尚未放寬；基準以 `72b64531` 為新、`eb08c5fc` 為舊（§i M1）。
- **順序與送客戶分批**（【R】）：
  - **第一批只送 Q1**（掛不掛、是否接受 ③ 空狀態；子點 a～e 逐點答）。Q1 否決 → Q2～Q5 作廢，落 A0。
  - Q1 同意後 **第二批**：Q2 字樣＋Q3 守衛形狀。
  - **Q4、Q5 其後**；Q4（Shell 新增結構與放置位置）[I] 可能屬總管內部自決（技術細節），是否須送客戶待判。
- **選項（Q1）**：a 掛 ③（X1）；b 掛 X2（需另放寬 fixtures／poc 邊界）；c 不掛（A0）。
- **推薦**：【R】a，前提客戶接受 §i M2／M3 代價；可被推翻。
- **風險**：③＝現況未驗；A50／A60 看不到內容；「不做空殼」相容性未判；Preview 可見對象未驗；§c 守衛在新基準未重核；手機五格加標記未量測；**字樣未核**（FAKE／示範皆待客戶核准）；**Shell 新增結構**（`PageSlot.data_mode`、`NavItem.demo`、chrome 標記函式）屬結構變更、需守衛與測試同步。

## h　仍未驗／限制

1. 本環境無 streamlit／瀏覽器：§c #3～#8、§e 的 AppTest／Chromium 項均**未執行**，為讀碼推論；手機五格加標記後的實際版面完全未量測（本版最大技術風險）。
2. 突變實跑只涵蓋 fast 靜態守衛，且以最小示意實作（registry＋常數檔＋`_render_ast`），未含 `nav.py`／`chrome.py`／wording 的變更；這些變更對其餘守衛的影響為讀碼推論。
3. ③ 渲染結果取自 `page_html` 純函式（與 runtime 同碼），未經 Streamlit 實際渲染；Cloud／真機未驗。
4. 「③＝production 載入端現況」引自 BACKLOG／evidence，本組未重驗；#1286 落檔的上一版卡本組未重讀。
5. 所有客戶方向皆〔待核〕轉述；導覽標記字詞、橫幅字樣皆未核准；`AppTest` 對 `st.navigation` 切頁支援未驗。
6. 守衛清單以字面詞搜尋，可能漏列；slow／browser 層除 `top_nav_browser` 外未讀。

## i　2026-11-20 獨立稽核後修正（稽核 1 組，與作者共享派工來源；以下修正未經複驗）

> 標記：[F]＝讀檔／`git` 可重現；[I]＝推論；NV＝NOT VERIFIED。本節不是客戶裁示、不是授權；不改 `DEC-2026-11-19-09` 任何字。

**M1　基準過期（[F]）**
- 2026-11-20 `git log origin/main` 最新為 `72b64531`；`eb08c5fc` 之後 `ui_v3`／`tests` 有變動：`git diff --name-only eb08c5fc origin/main -- ui_v3 poc tests` 含 `ui_v3/pages/assets.py`、`ui_v3/shell/nav.py`、`ui_v3/design/theme.py`、`ui_v3/design/tokens.py`、`ui_v3/pages/mkt.py`、`ui_v3/pages/chart_svg.py`，以及 `tests/ui_v3/` 下 `assets_page_renderer`、`design_tokens`、`market_page_browser`、`navigation_shell`、`token_contrast` 與 `tests/poc_assets_preview/` 兩檔。
- #1299（merge `b6603f23`）對 `assets.py`：`st.title(PAGE_TITLE, anchor=False)`；A10 標題由 `<h4>` 改為 `<div class="uv3-card-title" role="heading" aria-level="4">`（避免 Streamlit 自動標題錨點造成看不見的 Tab 停駐點）。#1298（`8ebb5290`，市場頁視覺批 2）另動 `nav.py`／`theme.py`／`tokens.py`／`mkt.py`。
- 故 §0「自 `0cfd86b9` 起 `ui_v3`／`poc`／`tests` 無變動」、§d「`ui_v3/pages/assets.py` 一字不動」、§a X3「動已驗收程式」三句已就地劃線更正。
- `DEC-2026-11-19-09` F1 引用 `eb08c5fc` 的處置：**只在本卡內註明**，不改該 DEC；該 DEC 引用的是當時基準，仍為歷史事實。
- NV：§b／§c 對 `nav.py`／`chrome.py`／各守衛的描述是以 `eb08c5fc` 讀的，**在 `72b64531` 上未逐項重讀**（含 #1298 對 `nav.py` 的改動）；施工前須整體重核。

**M2　D4（固定情境③）與條件 (1)——選項空間實質只有 ③**
- [F] 在 `poc/assets_fixture_preview/assets_fake_inputs.py` 的情境建構器中，`market_blocked_result()`（③）是唯一傳 `evidence=None` 者；其餘情境建構器均經 `fake_evidence(...)` 產生證據，其預設 `basis_value="成本"`、`basis_status="set"`，**掛載後 A10 會顯示「成本」**（本組讀建構器原碼，未逐一渲染其餘 10 個，故「會顯示」為讀碼推論 [I]）。
- 結論：條件 (1)（不顯示個人設定值／假成本）在 11 個既有情境中**只有 ③ 可滿足**；X1 的「推薦」其實是「唯一不需改程式的可行解」，不是從多個等價選項中挑出。X2 仍需改 fixture 層，X3／X4 如表。
- 代價（須客戶知悉）：選 ③ 後，**A50（持倉）／A60（來源與缺項證據）已驗收版面在 Preview 永遠看不到內容**——③ 的 A50 是 status-only、無持倉列，已驗收的列版面與 A60 展開內容無從審視；Preview 可審的只剩「可進入」與缺值語意。

**M3　「③ 是誠實現況空狀態」是推論（[I]）**
- §a 該句依據「production 載入端在市值基準下一律 blocked」的 BACKLOG／evidence 記載，**本組未重驗**。
- NV：「固定封包是否等於 production 現況」。若不等，**等於以常數假冒系統狀態**（頁面宣稱「資料未備／無法判定」，實際系統可能能讀到持倉）。
- 風險張力：頁頂「FAKE」橫幅說「這是測試資料」，與③「這是現況空狀態」兩種語意並陳，使用者可能讀成「現況是假的」或「空狀態是假的」；與 §b 的選字張力同源，列入 §g 待確認。

**Should-Fix**
1. **不做空殼 vs registered 定義（[F]／[I]）**：掛載 💼 為 `registered=True` 與 registry docstring 對 `registered` 的定義（「已有核准 wireframe 且已實作的頁」）、`DEC-2026-10-27-10`／`-12`（不做空殼頁的相關裁示）、`REASON_WIREFRAME_PENDING` 的語意是否相容，**未判定**；③ 頁無任何資料，是否構成「空殼」須客戶／總管裁。**已同步至 §g（Q1）**。（本組未重讀上述 DEC 逐字，NV。）
2. **Preview URL 可見對象（NV）**：`DEC-2026-11-19-01` 的未驗清單含 Preview 對外可見範圍；掛載後 💼 頁對誰可見未驗。**已同步至 §g（Q1）**。
3. **「8 條守衛」標題加註**：§c 的「8 條」中，#1、#2 為實跑突變轉紅（[F]）；**#3～#8 為讀碼推論（[I]），「僅此 8 條、無其他」是單組全稱句，未驗**。另補列一條**受影響但原未列入「不改即過」清單**的測試：`tests/ui_v3/test_ui_v3_navigation_shell.py::test_not_yet_open_label_is_not_open_for_ai_and_under_development_for_the_rest`（其 `labels` 斷言含 `"ast": "開發中"`；`ast` 改為可進後，`soon_key` 是否仍被該測試以 `nav_items()` 全五項取用須重核，若有改動需併入 §c 修改範圍或確認不改即過）。
4. **導覽標記 CSS 風險（[I]）**：`nav.py` 手機版 `.st-key-uv3-top-nav` 為 `display:flex` 一列，每格 `> div` 為 `flex:1 1 0`；標記作為連結的兄弟元素，可能壓縮連結可點寬度或改變格高。現有 browser 測試的 `_MEASURE` 量的是連結／soon 格，**量不到標記本身**；§e-4 的 Chromium 量測須**明寫涵蓋標記元素本身**（寬度、不被裁、不遮連結、≥48px 觸控區不受影響）。
5. **§g-4b 補充**：除 Status Bar PREVIEW 與頁尾提示缺席外，**側欄「資料狀態」區與「更新資料」CTA 在 💼 頁也會缺**（`_render_ast` 不呼叫 `chrome.render_status`／`render_footer`）；另 `page_icon="🌍"` 寫死，💼 頁的瀏覽器分頁圖示與頁籤標題會是 🌍 市場頁的——是否可接受須確認。
6. **§e「新字樣不得內含已核准字樣」改寫（[F]）**：依實際守衛 `test_no_pending_text_equals_or_embeds_an_approved_registry_wording`，守衛只檢 (a) 暫時字樣**整串**不等於任一已核准字樣、(b) 不含規則表符號（◆◇⬜⛔◷）；**並不檢查「內含已核准子字串」**。故 §e 與 §c 倒數第三項中「不得內含」之說，應改為「不得整串相等、不得含符號」；是否另自律不內含已核准子字串，屬作者慣例而非守衛強制。
7. **§g 的捆綁拆題**：原 §g 把多件事捆成一串；**已同步至 §g 正文（Q1～Q5，每題附已知答案／選項／推薦／風險）**；此處為摘要：依序由客戶一題一答（每題附推薦，[R]可被推翻）：
   - **Q1**　要不要掛 💼（含「③ 空狀態＋FAKE 橫幅」情境，及「不做空殼」疑慮）？推薦：僅在客戶接受 M2／M3 代價時才掛，否則 A0。
   - **Q2**　導覽標記與頁頂橫幅字樣（「FAKE」或其他；字樣最終需核准）。
   - **Q3**　S-a(7) 例外守衛的修改形狀（§c 逐條；僅 💼、不刪斷言、不改 `rules.py`）。
   - **Q4**　Shell 新增結構（`PageSlot.data_mode`、`NavItem.demo`、`adapters/assets_demo_envelope.py`）與放置位置（`adapters/` vs `fixtures/` 取捨）。
   - **Q5**　施工授權與 Model／Effort（Change Gate；高風險至少 1 組真獨立稽核）。
   Q1 否決則 Q2～Q5 不必問。

**本節未驗事項彙總**：NV——§b／§c 在新基準上的重核、其餘 10 情境的實際渲染、「③＝production 現況」、Preview URL 可見對象、`DEC-2026-10-27-10`／`-12` 逐字、`test_not_yet_open_label…` 對 `ast` 改可進的實際反應。本節由稽核後修正組單組寫成，未經複驗。
