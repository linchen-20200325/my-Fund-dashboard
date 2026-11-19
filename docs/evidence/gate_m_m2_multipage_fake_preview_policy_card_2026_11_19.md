# Gate-M／M-2｜多頁 FAKE 預覽政策與最小裁示準備卡（2026-11-19）

> **單組作者整理，未經獨立 QA；全稱句（「只有／沒有／全部」）皆為單組 grep／讀檔結論，未經第二組驗證。不構成授權、不是客戶裁示、不是 DEC、不改任何程式或測試。**
> 基準 main `58652da1`（2026-11-19 `git fetch` 實查；使用前須重查 GitHub）。符號：【F】事實（讀檔／grep）；【I】推論；【R】執行組推薦（可被客戶推翻）；【未驗】本組沒查。不寫行號，以「檔案::符號」定位。
> **M-2 的來源**：「客戶選 M-2＝多頁 FAKE 預覽政策與最小裁示準備」經 ChatGPT 派工單轉述〔待核〕；【F】`docs/DECISIONS.md` 內查無記錄此選擇的 DEC（`Gate-M` 只出現在 `DEC-2026-11-18-01`／`-02` 的不授權清單，寫「維持 M-0，不掛 FAKE」）。故 M-2 **只是核准規劃方向**，**不是**正式 FAKE 掛載政策已核准。
> **與既有卡的關係**：`docs/evidence/fund_search_mount_gate_card_2026_11_17.md` 已涵蓋 🔍 單頁的檔案範圍（S1～S7）、守衛清單、R1～R5 風險、A1～A6 授權條目與回滾，**不複製**。本卡只寫差異：三頁統一原則，與 M-2 方案欄之後尚未回答的問題。

## 1　三頁統一原則（全為【R】候選，未核准）

1. 掛載政策 ≠ 掛載。政策核准後，**每頁仍須各自的 Gate**；任何一頁**預設不掛載**（`registered=False`）。
2. FAKE 頁必須在**導覽項與頁頂兩處**同時可辨識為離線 FAKE；不得只靠 harness。
3. FAKE 與真實資料不得在同一頁混用；🌍 仍是唯一真實資料頁。🤖 不納入（Phase 7 前不得掛，`DEC-2026-10-29-07`，原文存 evidence 檔）。
4. 掛載 PR 與搬模組 PR 分開；回滾 ＝ `git revert` 單一掛載 commit，使 `registered` 回 False。

## 2　標示與資料區分

- 【F】`shared/ui_semantics/rules.py` 內**沒有任何 FAKE 字樣**（grep `FAKE` 0 命中）；`docs/DECISIONS.md` 也**查無**核准 FAKE 橫幅字串的 DEC。
- 【F】現有橫幅只存在各 harness 的 `FAKE_BANNER`：🔍／⚙️／單檔元件＝`FAKE／測試資料（離線注入，未執行任何真實請求）`，💼＝`FAKE／測試資料（非真實持倉，不代表任何實際資料）`。**屬 harness 字串，不在規則表、無 DEC 核准。**
- 【I】故「沿用既有核准字樣」對 FAKE 標示**做不到**；本卡**不創新文案**。其餘一律沿用：已核准字樣取 `shared/ui_semantics/rules.py::approved`／`entry`；新字樣一律 `ui_v3/viewmodels/preview_wording.py::PendingWording`＋`pending_span`（`data-pending-wording` 虛線底線）。
- 【R】真實／模擬區分：`PageSlot`（`ui_v3/shell/registry.py`）現無資料真假欄位，建議未來加 `data_mode`（`real`／`offline_fake`），`offline_fake` 必須帶橫幅且不得 import 網路／Sheet／secrets 模組（同既有卡 R2）。【未驗】欄位名稱僅為示例。

## 3　每頁獨立 Gate（最小條件）【R】

| 條件 | 🔍 | 💼 | ⚙️ |
|---|---|---|---|
| renderer／VM 已在 `ui_v3`？【F】 | **否**，renderer／logic／wording／fake_inputs 四檔仍在 `poc/fund_search_fixture_preview/` | 是（`ui_v3/pages/assets.py`、`ui_v3/viewmodels/assets_page.py`；`poc/assets_fixture_preview` 只放 fake_inputs＋harness） | 是（`ui_v3/pages/nas_diag.py`、`ui_v3/viewmodels/nas_diag.py`；`poc/nas_diag_preview` 同型） |
| 線框狀態【I】 | 整頁線框基準 `DEC-2026-11-14-04`（來源待核） | Stage 1 範圍 `DEC-2026-11-14-06` Q1＝A（來源待核） | 【未驗】本組未查到核准線框；`BL-0550` 列多項 Pending（含「掛載位置與入口」） |
| FAKE 輸入供應處 | 待裁（既有卡 S6） | 同左，尚無落點 | 同左，尚無落點 |
| 其他 | 暫行字樣 `DEC-2026-11-17-02`(a)～(g) 未裁 | 「可用持倉列」門檻、T6 仍 Pending | 真實探測、冷卻、新字樣均 Pending |

另【F】`fund_lookup_component_preview`（`DEC-2026-11-18-04`）是 🔍 的第二個隔離 PoC，**尚未併入** `fund_search_fixture_preview`；🔍 掛載範圍是否含它，不在本卡裁示。

## 4　必守條件（守衛／符號，已實查存在）

- 掛載與導覽：`tests/ui_v3/test_ui_v3_page_registry_guard.py::test_only_market_page_is_registered_so_no_empty_shell`；`tests/ui_v3/test_ui_v3_navigation_shell.py::test_nav_items_are_the_five_pages_in_ia_order_and_only_registered_are_available`；`tests/ui_v3/test_ui_v3_assets_source_import_isolation.py::test_registry_has_no_new_page_and_preview_renderers_are_unchanged`。**掛任一頁都會使上列轉紅，須改守衛**（既有卡 1-B 的跨頁化）。
- 資料隔離：`tests/ui_v3/test_ui_v3_fixtures_are_fake_guard.py::test_no_production_module_imports_fixtures`（`ui_v3.fixtures` 不得被 `app_preview`／`pages` import）、`::test_every_fixture_module_declares_fake_marker_at_module_level`；`tests/ui_v3/test_ui_v3_preview_not_formal_guard.py::test_preview_module_has_no_module_level_streamlit_or_fixtures`、`::test_preview_main_fails_loud_when_registered_page_has_no_renderer`。
- poc 端反向鎖（掛載會使其改寫）：`tests/poc_fund_search_preview/test_fund_search_guards.py::test_registry_does_not_register_the_exp_page_and_navigation_is_untouched`；`tests/poc_nas_diag_preview/test_nas_diag_preview_apptest.py::test_formal_page_registry_is_untouched_by_the_preview`；`tests/poc_fund_lookup_component_preview/test_fund_lookup_cmp_guards.py::test_registry_app_preview_pages_and_shell_do_not_mention_the_preview_and_ui_v3_never_mentions_poc`；💼 端以 `tests/poc_assets_preview/test_assets_preview_apptest.py` 的 `_FORBIDDEN_ENTRY`（含 `ui_v3.app_preview`、`ui_v3.shell.registry`）鎖入口。
- 字樣：`tests/ui_v3/test_ui_v3_preview_wording_guard.py::test_pending_wording_is_nonempty_unique_and_all_pending`、`::test_no_pending_text_equals_or_embeds_an_approved_registry_wording`；🔍 端 `test_fund_search_guards.py::test_every_new_wording_is_a_pending_wording_with_the_required_source_and_never_a_rules_key_or_text`。
- 無網路／secrets：`test_nas_diag_preview_apptest.py::test_all_scenarios_work_with_the_network_blocked`、`::test_no_credential_secret_or_proxy_environment_access_in_a_run`；🔍 端 `test_no_network_environment_secret_or_file_call_by_ast`。
- 導覽版面約束【F，取自 HANDOFF 快照，未重測】：手機 ≤768px 五格同列、無橫滑、≥48px（`DEC-2026-11-06-01`、`DEC-2026-11-07-02` 客戶逐字存檔）；導覽項加「FAKE」標記不得破壞此約束。

## 5　建議先行頁面（【R】執行組讀法，可被客戶推翻）

建議 **🔍 先行，⚙️ 次之，💼 最後**。理由：(a) 誤讀風險：🔍 的 FAKE 基金代碼（如 `FAKE-OK01`）一眼可辨；⚙️ 的假「連線成功」可能被誤當真實診斷；💼 的假持倉掛在「我的資產」下，最易被誤當個人資料（`CLAUDE.md` §1：錯誤數字比沒有數字危險）；(b) 🔍 整頁線框基準最完整，且既有卡已備好範圍與回滾。代價：🔍 檔案面最廣（尚需搬四檔），💼／⚙️ 技術上較省；本推薦把誤讀風險置於工程成本之前。【未驗】三頁誤讀風險高低為判讀，非實測。

## 6　真正需客戶裁示、既有 DEC 尚未回答的最少問題

**已被正式 DEC 回答、不重提（provenance 等級依實讀原文）**

| DEC | 已回答 | provenance |
|---|---|---|
| `DEC-2026-10-27-12` | 不做空殼、不放「規劃中」 | 客戶逐字（表內有原話） |
| `DEC-2026-10-29-07` | 🤖 Phase 7 前不掛導覽 | 客戶，原文存 evidence 檔 |
| `DEC-2026-11-06-01`／`11-07-02` | 手機五頁籤全部可見 | 客戶，前者逐字存 evidence 檔，後者「可以」二字 |
| `DEC-2026-11-07-01` | 🌍 Preview-only 有條件施工 | 客戶「同意 B」，其餘為射程整理 |
| `DEC-2026-11-16-01`／`11-17-01`／`11-17-02`／`11-17-03`／`11-18-04` | 各 FAKE 預覽僅限 `poc`／隔離路徑；明列不授權 registry、`app_preview`、掛載 | 要點轉述，來源待核（`-04` 為 ChatGPT 派工單轉述） |
| `DEC-2026-11-18-01`／`-02` | Gate-M 維持 M-0，不掛 FAKE | 對話提示語轉達〔待核〕，非逐字 |
| `DEC-2026-11-14-08` | S2-T0 暫緩；Gate-D 不動 | 來源待核，要點轉述 |

**Q1　Preview 導覽是否允許出現離線 FAKE 頁？**（`app_preview` 現行文字：preview 不得顯示 fake 資料）

| 方案 | 優點 | 缺點 | 風險 |
|---|---|---|---|
| P0 不允許（維持 M-0） | 零改動 | Shell 內仍看不到三頁 | 無新增 |
| P1 允許，須逐頁 Gate、標示規格另裁（Q2） | 守衛只改一次原則；可逐頁撤回 | 多一輪裁示 | 誤讀為正式頁（需 Q2 緩解） |
| P2 一次授權三頁掛載 | 最少對話 | 範圍過大；💼 風險最高；暫行字樣更近使用者 | 高 |

【R】P1；若客戶無意在 Shell 看 FAKE，P0 亦合理。

**Q2　FAKE 標示的字樣與位置由誰定？**（【F】現無核准字樣）

| 方案 | 優點 | 缺點 | 風險 |
|---|---|---|---|
| S-a 沿用 harness 現有字串，定性為 `PendingWording` | 不創新文案；最快 | 💼 與其餘字串不一致；字樣仍未核 | 暫行字樣固化 |
| S-b 請客戶／設計者核定字樣後進規則表 | 字樣正式 | 需先走字樣 Gate | 延遲 |
| S-c 僅導覽項標記、頁頂不加 | 版面最簡 | 頁內無警示，深連結進入會漏 | 誤讀（高） |

【R】S-a 作暫行，並登記 S-b 為後續；不建議 S-c。

**Q3　若 P1，先掛哪一頁？**（見第 5 節理由）

| 方案 | 優點 | 缺點 | 風險 |
|---|---|---|---|
| 🔍 先行 | 誤讀風險低；線框與範圍最完整 | 須搬四檔，工程最大 | 中（工程面） |
| ⚙️ 先行 | 渲染層已在 `ui_v3` | 線框／BL-0550 多項未裁；假狀態易誤讀 | 中高 |
| 💼 先行 | 渲染層已在 `ui_v3`，改動最少 | 假持倉在「我的資產」下 | 高 |

【R】🔍 先行。

## 7　NOT VERIFIED／未查證

1. 三頁「renderer 已在 `ui_v3`」依 `ls` 與 harness import 判讀，未逐檔核對完整依賴。
2. 第 4 節守衛名稱已實查存在，但**未實跑**其內容是否會因掛載轉紅（既有卡 1-B 同限制）；slow／browser 層守衛未讀。
3. `BL-0550` 九項 Pending 取自 BACKLOG 文字，⚙️ 無核准線框為「未查到」，非已證實。
4. HANDOFF 的手機導覽約束（五格同列／48px）未重測；Cloud／真機未驗。
5. 本組未查 Preview 實際部署的可見對象（誰能開 Preview URL），此影響 Q1 風險評估。
6. 所有 DEC 的 provenance 以 `docs/DECISIONS.md` 文字為準，其中「來源待核」者無法由 repo 核對。
