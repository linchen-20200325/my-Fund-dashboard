# 💼 我的資產｜最小施工 Gate 卡（C 線；2026-11-19）

> **已由 `docs/evidence/c_assets_s_ast_m1_gate_v2_2026_11_19.md`（v2）取代；原 A1a 作廢，不得直接施工。**（本檔以下內文不改，僅供追溯。）

> 單組執行組唯讀整理，**未經第二組獨立複驗**；全稱句皆為單組 grep／讀檔結論。**不是授權、不是 DEC、不改 repo。**
> 基準：`origin/main` `9473a76f`（2026-11-19 重核；自 `0cfd86b9` 起僅 docs 變動〔#1285：DEC-2026-11-19-06／-07、BACKLOG／HANDOFF／evidence〕，`ui_v3`／`poc`／`tests` 無變動；DEC-06／-07 屬 Gate-D／BL-0551，本組未讀其內文；使用前重查）。
> 2026-11-19 依非作者稽核（Must-Fix 2）修訂：更正 §1 的內容描述、Q1 補寫守衛放寬與情境選擇、補守衛清單與 Shell 呈現、補 BL 引用與【I】標記。
> 標記：【F】事實（讀檔／實跑）、【I】推論、【R】推薦（可被推翻）、【未驗】。引用只指不抄；不寫行號。
> 客戶要求「經 ChatGPT 轉達」〔待核〕，本組未見原文。

## 0　一句結論（先講最不好聽的）

【F】**A00／A10／A20 已經做完，而且已在 main**：`ui_v3/viewmodels/assets_page.py`（S-VM，#1248）、`ui_v3/adapters/assets_page.py`、`ui_v3/pages/assets.py`（renderer；A00／A10／A20＋A50＋A60）、隔離 harness `poc/assets_fixture_preview/`（十一情境）。A00／A10／A20 Preview 的合併出處：BACKLOG BL-0542 補註與 HANDOFF 記為 #1256（merge `a1e5a38e`）；A50／A60 之後續合併為 #1257／#1261 等（commit 層級未逐一對 repo 文件核對，本卡不再引個別 commit hash）。
【I】在這三塊上再新增程式＝重複既有 FAKE 預覽；「不再建重複 FAKE 預覽」出自派工單轉述〔待核〕，repo 內 `DEC-2026-11-19-04` (1)(5) 針對的是 🔍 的模組搬移，不是 💼，故「客戶已否決」不能寫成 DEC 事實，僅為本組讀法。
【F】**目前沒有任何「現有授權內、可以新增程式、且使用者會看到新東西」的 💼 切片。** 使用者今天只能在本機 `streamlit run poc/assets_fixture_preview/app_assets_preview.py` 看到 💼；在 Preview App（`ui_v3/app_preview.py`）導覽裡 💼 仍「可見但不可進」。
【I】唯一會改變「使用者看到什麼」的最小切片＝**把既有 renderer 掛進 Preview App（Gate-M，💼 單頁）**。它必然需要 DEC 未授權的事（改守衛、掛載、新字樣、導覽層 FAKE 辨識），故停在 Decision Gate（§7）。

## 1　建議的唯一最小切片：**S-AST-M1「💼 FAKE-only 單頁掛載」**

- 內容：不新增任何版面元件；把已合併的 A00／A10／A20（＋既有 A50／A60 原樣，不增不減）以**單一固定 FAKE 情境**掛為 Preview 導覽可進的 💼 頁；頁頂 FAKE 橫幅（PendingWording，暫行）。不接資料、不含情境切換器（切換器是否算新增正式元件＝`DEC-2026-11-16-01` 待確認 (h)，未裁）。
- **固定哪一個情境是內容決定，不是技術細節，已列入 Q1**：poc 現行預設是「①完整（新臺幣＋美元）」＝**有列**（fund_name／fund_code／ccy／units_shares 為 FAKE 值，含 USD 列）；若選它＝把假持倉放在「我的資產」下，正是本卡 §1 自己列的最大誤讀風險。本組推薦無列情境（如「⑤未選定來源」：A50 只畫一列引用 A00 的狀態文字、無任何假持倉；A60 件數為 `◇ 資料未備`、狀態為 `⬜ 無法判定`〔【F】由 `no_active_result` 與 poc README 讀得，未實跑渲染〕）。
- 為何選它：A00／A10／A20 擇一或組合皆已存在；A30／A40（T7 去留未裁）、A10 入口、A50 預設展開、A51（`DEC-2026-11-16-01`／`-17-01` 不授權；82 §11.10 Stage 2）都被擋；真實資料被 Gate-D／BL-0545／BL-0551 擋。掛載是唯一不碰資料與金融語意、仍能改變可見度的一步。
- 【F】M-2 卡 §3：💼 的 renderer＋VM 已在 `ui_v3`，且有 Stage 1 線框基準（`DEC-2026-11-14-06`）；🔍 renderer 仍在 `poc/`，且 `DEC-2026-11-19-04` 選 G-A 不搬。【未驗】「⚙️ 沒有核准線框」只是 M-2 卡 §3 的「未查到」，本組沒有證實其不存在，所以**不能據此說只有 💼 合格**。
- 【I】**本卡選 💼，與 `DEC-2026-11-19-01` 執行組推薦欄的 🔍→⚙️→💼 排序方向不同**。理由：BL-0536 現況段記載 wireframe Gate 順序為 💼（G2）→ 🔍（G3）→ ⚙️（G4）；且 🔍 因 G-A 暫不進行。M-2 卡把 💼 排最後係因誤讀風險最高；「該排序前提（🔍 能先行）已不成立」是本組推論，未經客戶確認。
- **使用者真正看到的進展（誠實版）**：Preview 導覽出現可點的「資產」；進入後頁面主體只有 FAKE 橫幅、來源狀態、降級卡、**A20 四格恆為 `◇ 資料未備`**（G-4 未核，BL-0542；A20 無任何正式值）；另有預設收合區：**A1a（無列情境，如⑤）只有 A60 是 `<details>`（內含略過件數 `◇ 資料未備` 與 `⬜ 無法判定`），A50 只是一列引用 A00 的純文字；A1b／A2（有列情境）A50 也是 `<details>`，展開後含 FAKE 基金名稱／代碼／幣別／單位數，A60 件數視情境**。沒有圖、金額、占比、合計。若客戶期待「看到資產資料」，此切片不會給；那需要 Gate-D。Preview 實際可見對象（誰能開 Preview URL）【未驗】。
- **Shell 呈現（`_render_ast` 的設計約束）**：【F】`_render_mkt` 會呼叫 `chrome.render_status`（Status Bar＋側欄資料狀態區，資料來自 🌍 市場 model）。💼 頁**應省略 Status Bar／側欄狀態區**（無對應 model，且不得為此牽出任何網路取數）；【F】`main()` 內 `st.set_page_config(page_icon="🌍")` 寫死，掛載後 💼 頁的瀏覽器分頁圖示會仍是 🌍（需決定是否改，屬 `app_preview.py` 變更範圍）。

## 2　精確檔案清單（若獲授權；單一 PR，回滾＝`git revert` 該 commit，`registered` 回 False）

| 動作 | 檔案 | 說明 |
|---|---|---|
| 改（生產） | `ui_v3/shell/registry.py` | `PageSlot("ast", …)` 改 `registered=True`（移除 unregistered_reason）。**這只表達「已掛載」，無法表達「離線 FAKE」** |
| 改（生產，獨立項） | `PageSlot` 欄位（`registry.py`）或 `nav.py` 另設表 | 【F】`PageSlot` 只有 slug／title／registered／unregistered_reason，`nav_items` 只從這些生成；要讓導覽層知道某頁是 FAKE，必須新增欄位（M-2 卡建議的 `data_mode` 為示例，【未驗】）或另設表。此項無論 Q2 選 N1／N2 皆需要（N3 不需要） |
| 改（生產） | `ui_v3/app_preview.py` | 新增 `_render_ast`（import 皆在函式內）並加入 `renderers`；其餘不動 |
| 改（生產） | `ui_v3/viewmodels/assets_preview_wording.py` | 新增 1 個 `PendingWording`（FAKE 橫幅，帶來源標示；不進 `shared/ui_semantics/rules.py`） |
| 新增（生產） | FAKE 輸入供應處（【R】`ui_v3/fixtures/` 下 1 檔） | **技術細節，不併入客戶 Q1**（但「改守衛」本身在 Q1 授權清單）。`ui_v3` 任何檔不得含 `poc/` 子字串（見 §3），故新增檔、PendingWording 來源標示與 drift 說明**都不得寫 `poc/` 路徑**；`app_preview` 不得 import `ui_v3.fixtures`（現行守衛）。第三份同形資料需 drift 測試（現有 poc 與 `tests/ui_v3/assets_page_support.py` 兩份已有） |
| 視 Q2 | `ui_v3/shell/nav.py`、`ui_v3/pages/chrome.py` | 僅 Q2 選 N1（導覽項 FAKE 標記）時才動 |
| 改（守衛，=Stop） | 見 §3 五～七個既有測試 | 逐項列於 §3 |
| 新增（測試） | `tests/ui_v3/` 下 1～2 檔 | 掛載後不變量＋橫幅＋無網路（§5） |

## 3　哪些既有守衛會阻擋（實讀碼；實跑範圍已標）

**實跑方法**：在 `git archive` 的暫存副本（不動 repo）做突變，跑 `tests/ui_v3`＋`tests/poc_assets_preview`（`--noconftest`）。基線 2 failed／2649 passed／16 skipped（2 failed＝本環境缺 `requests` 的 subprocess，與掛載無關）。**本環境無 streamlit → AppTest／Chromium 守衛整檔 skip，未執行**。

| 守衛（檔::符號） | 掛載後 | 依據 |
|---|---|---|
| `test_ui_v3_page_registry_guard.py::test_only_market_page_is_registered_so_no_empty_shell` | **紅** | 【F】實跑突變（僅 registry 翻 True） |
| `test_ui_v3_assets_source_import_isolation.py::test_registry_has_no_new_page_and_preview_renderers_are_unchanged` | **紅** | 【F】同上 |
| `test_ui_v3_navigation_shell.py::test_nav_items_are_the_five_pages_in_ia_order_and_only_registered_are_available`、`::test_app_has_exactly_one_navigable_page_and_no_empty_shell_pages`（斷言僅 🌍 可進、連結數 2、title 僅 🌍）、`::test_unregistered_pages_are_visible_but_never_available_and_ai_never_available`（斷言 `items["ast"].available is False`）、`::test_top_nav_is_not_a_second_router_and_uses_all_five_approved_labels`（斷言可進項＝＝`{"mkt"}`、非 mkt 皆不可進） | 紅 | 【I】讀碼推論，未執行（需 streamlit） |
| `test_ui_v3_preview_not_formal_guard.py::test_preview_main_fails_loud_when_registered_page_has_no_renderer`（以 `ast` 當「已掛載無 renderer」負控） | 紅 | 【I】讀碼推論，未執行 |
| 若 FAKE 輸入放 `ui_v3/fixtures/` 且由 `app_preview` import：`test_ui_v3_fixtures_are_fake_guard.py::test_no_production_module_imports_fixtures`、`test_ui_v3_preview_not_formal_guard.py::test_preview_module_has_no_module_level_streamlit_or_fixtures`、`test_ui_v3_import_guard.py::test_no_import_violations_in_ui_v3`（`ui_v3_guard_lib.LAYER_DEPS["root"]` 不含 fixtures） | **紅** | 【F】實跑突變（三條皆紅） |
| 同上情形：`test_ui_v3_market_page_apptest.py::test_page_imports_no_fixtures_and_no_old_ui`（斷言 `app_preview.py` 不得 import `ui_v3.fixtures`） | 紅 | 【I】讀碼推論，未執行（AppTest） |
| `test_ui_v3_top_nav_browser.py::test_mobile_top_nav_states_and_aria`（slow；斷言 `cells[1:]` 皆 `aria-disabled="true"`、無 href、文字含「開發中」，Tab 只聚焦 🌍） | **紅**（掛載後 💼 格可進、有 href、可聚焦） | 【I】讀碼推論，未執行；同檔其餘五格版面斷言須在掛載後重量 |
| `tests/poc_fund_lookup_component_preview/test_fund_lookup_cmp_guards.py::test_registry_app_preview_pages_and_shell_do_not_mention_the_preview_and_ui_v3_never_mentions_poc`，以及 `tests/poc_fund_search_preview/test_fund_search_guards.py` 同型守衛（斷言 `ui_v3/**/*.py` 任何檔不含 `"poc/"` 子字串）；渲染測試另有同型斷言 | **條件式紅**：只要新增的 `ui_v3` 檔、PendingWording 來源標示、docstring 含 `poc/` 即紅 | 【F】讀碼（現行 `ui_v3` 內 `grep poc/` 為 0 命中）；為約束，不是必紅 |
| `tests/poc_assets_preview/*`（`_FORBIDDEN_ENTRY` 鎖 harness 入口、不讀 registry 狀態） | 不變 | 【F】突變下無新紅 |
| 新檔自動納入的 import／readonly／wording／engineering-leak 守衛 | 需合規 | 【F】母體取 `ui_v3/**` 全部 `.py`，無白名單 |

**判定**：新增檔本身不會讓既有守衛轉紅（含 `poc/` 字串者除外）；**掛載（registry＋renderer）必然使 ≥8 條既有守衛轉紅（實跑 2＋讀碼推論 6：navigation_shell 4、preview_not_formal 1、top_nav_browser 1；另有 FAKE 供應處與 `poc/` 字串的條件式）。`test_ui_v3_navigation_shell.py` 全檔皆圍繞「僅 🌍 可進」，掛載後該檔需整體檢視**，須改既有守衛＝Stop。`DEC-2026-11-14-06`（禁改 registry／app_preview／既有守衛）與 `DEC-2026-11-19-01`（不授權修改或新增守衛／測試、不授權掛載）明文排除，故**不得自行施工**。也無「不改守衛的掛載」：registry 的 `registered` 就是被守衛鎖死的值。**此外 `DEC-2026-11-19-01` S-a(7) 明文「不得修改 `shared/ui_semantics/rules.py` 或任何現有守衛」——A1 若要執行，需客戶明文放寬此條（限 💼 單頁、限 Q1 所列守衛），光是「不授權清單」不足以涵蓋。**

## 4　涉及項目（逐項）

| 項目 | 是否涉及 | 備註 |
|---|---|---|
| 正式 Shell／導覽 | **是**（Preview Shell；非正式 `app.py`） | 手機五格頁首（≤768px、≥48px、`DEC-2026-11-07-02`）；Q2 選 N1 會動；BL-0544 的「正式 Cloud／非作者 QA 證據缺口」與導覽改動相關，不得宣稱已驗 |
| `ui_v3/shell/registry.py` | **是** | `registered` 翻轉；另需 FAKE 表達機制（§2「獨立項」） |
| `ui_v3/app_preview.py` | **是** | 新增一個 renderer |
| 正式 `app.py`／Old UI／`ui_v2` | 否 | `test_formal_entry_candidates_do_not_reference_ui_v3` 鎖 |
| FAKE 標示 | **是** | 橫幅字樣未核（rules 無 FAKE 字樣；M-2 卡 §2） |
| 金融資料／公式／FX／Schema | **否** | 全 FAKE；無 L1／L2／secrets／網路 |

## 5　最小測試與完成條件（【R】；全部需 exact-head CI 四 lane success）

1. 改後守衛：registry 不變量改為「🌍 真實＋💼 offline_fake；🔍／🤖／⚙️ 未掛載；🤖 仍不可建構為已掛載」（精確化，不是刪除）。
2. AppTest：💼 頁以 FAKE 渲染、無 exception、FAKE 橫幅在頁頂、頁面無 engineering leak、無 `%`／金額／合計；socket 攔截下無網路、不讀 secrets／憑證環境變數（沿用 poc 既有手法）。
3. PendingWording：新字樣皆 `PendingWording`＋來源標示，不等於也不內含已核准字樣，不進 `rules.py`。
4. Chromium slow lane：**390 與 1280**——五格導覽仍全部可見、≥48px、無橫向溢出；390 首屏標記仍恰 5；**A1a 只有 A60 `<details>`；A1b／A2 A50 與 A60 兩個** 開合不產生 websocket client→server 訊息；Q2 選 N1 須重量五格。
5. 獨立 QA：治理／守衛修改屬高風險，依 `DEC-2026-10-16-05` ≥1 組真正獨立稽核；開工前依 `PROJECT_RULES.md` §5.1 Change Gate 重評 Model／Effort（該表本組未讀，【未驗】）。
6. 完成宣稱只能寫「fixture／Chromium 層」，不得寫成 Cloud／真機／像素驗收或 💼 正式完成。

## 6　不接真實資料能否先有可操作 UI？

【F】**能，而且已經有**：poc 內十一情境＋A50／A60 兩個零 rerun 展開容器。再往上的「可操作」（A10 入口定位、A50 依視窗預設展開、A51 逐檔詳情）被**技術 Gate／T6／待確認 (c)** 擋，不是被資料擋——所以「先做 UI 再接資料」的空間已用完。

## 7　需客戶裁示的最少問題（兩題）＋執行組推薦（可被推翻）

**已被 DEC 回答、不重提**：`DEC-2026-11-19-01`（Q1＝P1 逐頁獨立 Gate、預設 `registered=False`；Q2＝S-a 暫行，沿用既有隔離警示字串作 PendingWording 候選；**但 S-a(6) 明定「真正掛入 Shell 前須另行解決導覽層 FAKE 辨識」**）；`DEC-2026-11-14-06`（Stage 1 基準＝A00／A10／A20／A50／A60）；`DEC-2026-11-16-01`／`-17-01`（A50／A60 隔離）；`DEC-2026-11-19-04`（🔍 G-A 不搬；Gate-M 與 S2-T0 分離；日後再提最小逐頁方案＝本卡）；`DEC-2026-11-07-02`（五格短標不改）；`DEC-2026-10-29-07`（🤖）。`DEC-2026-11-14-04`／`-08` 屬 🔍，不適用。

**Q1　分兩問。Q1-a：要不要現在啟動 💼 的獨立 Gate-M（掛 vs 不掛）？** 若選「掛」（A1／A2），客戶須**明文放寬 `DEC-2026-11-19-01` S-a(7)「不得修改 `rules.py` 或任何現有守衛」——限 💼 單頁、僅限下列守衛**（不是只有「不授權清單」；FAKE 供應處放哪屬技術細節，不在本題）：
(1) `test_only_market_page_is_registered_so_no_empty_shell`（registry 不變量改為「🌍＋💼 已掛載」）；(2) `test_registry_has_no_new_page_and_preview_renderers_are_unchanged`；(3) **`tests/ui_v3/test_ui_v3_navigation_shell.py` 全檔（限 💼）**——至少含 `test_nav_items_are_the_five_pages_…`、`test_unregistered_pages_are_visible_but_never_available_…`、`test_top_nav_is_not_a_second_router_…`、`test_app_has_exactly_one_navigable_page_…` 四條（授權以整檔為單位，因逐條列舉可能漏，本組只用字面詞搜尋，未列者【未驗】）；(4) `test_preview_main_fails_loud_when_registered_page_has_no_renderer`（改用其他頁作負控）；(5) `test_ui_v3_top_nav_browser.py::test_mobile_top_nav_states_and_aria`；(6) 視 FAKE 供應處：`test_no_production_module_imports_fixtures`、`test_preview_module_has_no_module_level_streamlit_or_fixtures`、`test_no_import_violations_in_ui_v3`、`test_page_imports_no_fixtures_and_no_old_ui`（`DEC-2026-11-19-01` 不授權清單另含新增守衛／測試，故新增的不變量測試也須一併授權）。
**Q1-b（僅在 Q1-a 選「掛」時問）：固定哪一種情境？**（內容決定，非技術細節；A0 不掛載則無此問）


| 方案 | 優點 | 缺點 | 風險 |
|---|---|---|---|
| A0 不掛載（維持現況） | 零改動、零守衛變動 | Preview 內 💼 無進展可看；是否落空客戶期待的「實際可見進展」〔待核，來源為轉述〕 | 無 |
| **A1a 單頁、固定「無列」情境（如⑤未選定來源）、無切換器、頁頂橫幅** | 可見度提升且畫面無任何假持倉；單 commit 可回滾；不碰資料 | 改上列守衛＋新增不變量測試；整頁幾乎只有 `◇ 資料未備`／`⬜ 無法判定`；**A10 基準列仍會顯示 FAKE 的「成本」並標為已設定（⑤的 `fake_evidence` 帶 `basis_value="成本"`、狀態 set，【F】`tests/ui_v3/assets_page_support.py`；renderer 把它當使用者設定值顯示）——FAKE 值仍掛在「我的資產」下，僅不含持倉；**FAKE 橫幅、導覽層標示字樣仍暫行 | 暫行字樣更近使用者；展示價值低；FAKE 基準值被誤讀為使用者設定 |
| A1b 單頁、固定「有列」情境（現 poc 預設①完整：含 USD 列、單位數） | 展示 A50 逐檔容器，客戶看得到較多東西 | 同 A1a 的守衛修改；**把假持倉放在「我的資產」下**（`CLAUDE.md` §1：錯誤數字比沒有數字危險） | **高誤讀風險**（假持倉被當個人資料） |
| A2 同 A1 但保留 11 情境切換器 | 展示價值最高 | 切換器是否算新增正式元件未裁（(h)）；更易誤讀為真功能 | 高 |

**Q2　導覽層如何辨識「這是離線 FAKE 頁」（S-a(6) 的前置，現無解）？**

| 方案 | 優點 | 缺點 | 風險 |
|---|---|---|---|
| N1 沿用既有虛線小標記的視覺形式，為 FAKE 頁加一個不改短標的標記（新 PendingWording） | 不動已核准短標；有既有視覺先例 | 動 `nav.py`／`chrome.py`＋`PageSlot`；手機五格版面須重量。**`nav.py` 的 `.uv3-nav-soon` 虛線小標記現有語意是「開發中／不可進」，用在「可進的 FAKE 頁」語意相反，可能被讀成不可進**（可能需另設樣式，此時就不再是沿用） | 五格擠壓（需 Chromium 量）；語意誤讀 |
| N2 改短標（如加「示範」） | 最直觀 | 動 `DEC-2026-11-07-02` 已核准短標＝需新授權 | 違反已核准字樣 |
| N3 導覽不標、只靠頁頂橫幅 | 最簡 | 與 S-a(6) 衝突；深連結以外的導覽進入者看不出 | 誤讀（高） |

**【R】** 若要看到進展：**Q1-a＝掛、Q1-b＝A1a、Q2＝N1**（並要求 390 五格量測為完成條件）；若客戶不想在 Shell 內出現 FAKE 頁：**A0**，此時 💼 **沒有其他安全施工切片**，建議停手，工作重心留給 Gate-D／BL-0551。**【R】不建議 A1b、A2、N3。**

**已評估並排除**：①新增 A00／A10／A20 程式（已存在，重複）；②在 `ui_v3/app_*.py` 另開第二個 FAKE 入口（仍撞 fixtures／LAYER_DEPS 守衛，且可見度不比 poc 高）；③把 poc 部署到 Cloud（部署未授權）；④A10 入口／A50 預設展開／A51／A30／A40（`DEC-2026-11-16-01`／`-17-01` 及 82 Stage 2 未授權）；⑤截圖證據包（需 streamlit＋Chromium，本環境皆無；自動化需動 `.github/`，不建議）。

## 8　未查證／限制

0. 相關 BL 現況：BL-0536（in progress；其「現行下一步」寫「專案 AI 現不開始 💼 程式」為 2026-11-03 舊文，已被後續 DEC 取代，引用時不採）；BL-0542（G-4 摘要四格口徑待 Gate；2026-11-16 補註 #1256 已合併 `a1e5a38e`）；BL-0544（S1 Preview Code 已合併，正式 Cloud／非作者 QA 證據缺口仍在）。

1. 本環境無 streamlit、無 Playwright 瀏覽器：AppTest／Chromium 守衛**未執行**，§3 標【I】者為讀碼推論。突變實跑只涵蓋 fast 靜態守衛；暫存副本實跑，**未動 repo**。
2. 「A00／A10／A20 已完整」指 renderer／VM／poc／測試存在且 main 上合併；**不代表**其內容已驗收（#1256 的授權來源為對話訊息、repo 無對應 DEC，見 `DEC-2026-11-16-01` 註；Cloud／真機／390／1280 像素皆未驗）。
3. 所有 DEC 的客戶來源皆「要點轉述〔待核〕」，本組無法核對原話；`DEC-2026-11-14-04`／`-08`、`-17-04` 僅讀標題與適用範圍。
4. FAKE 供應處 B1（`ui_v3/fixtures/`）為執行組選擇；其他放法（adapters 內 FAKE 模組、`app_preview` 內嵌資料）各有層語意代價，本組未逐一實測。
5. 「掛載使 ≥8 條既有守衛轉紅」為下限：已實跑 2 條＋讀碼推論 6 條（未執行）；另 FAKE 放 `ui_v3/fixtures/` 時實跑突變 3 條（條件式）；`test_ui_v3_navigation_shell.py` 內其餘斷言（如約 :72 的 soon 標籤、:361 的條件式）本組判讀為不受影響但未驗；slow／browser 層守衛僅讀了 `test_ui_v3_top_nav_browser.py`，其餘未讀，可能另紅。
6. 未讀 `PROJECT_RULES.md` §5.1 表（Model／Effort）、#1285 內容；main 可能已前進。
7. Preview URL 可見對象、客戶實際如何觀看 poc＝未查。
