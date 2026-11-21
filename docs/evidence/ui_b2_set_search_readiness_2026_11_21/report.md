# UI-B2：⚙️ 設定／🔍 找基金 可掛載就緒度（readiness matrix）

日期 2026-11-21（工作日 2026-11-20 起算）｜基準 origin/main `bf3d61b2`｜單組產出（執行組以非作者角度實跑），未經獨立複驗；非授權、非裁示、非客戶核准；登記不構成動工授權（`CLAUDE.md` §-1）。
本稿未改任何程式、registry、`app_preview`、DECISIONS、BACKLOG、HANDOFF；唯一新增檔案即本檔。標記：【F】本組實跑／讀檔所見；【I】推論；【NV】未驗證。

## 0. 結論（先講）

1. 【F】現存三條合法離線 UI 路徑（NAS 診斷、單檔查詢元件、找基金＋條件篩選）在真 Chromium（390／1280）實際操作皆無缺陷：無橫向溢出、可互動控制項（renderer 內）高度 ≥48px、鍵盤焦點可見、缺值不顯示成 0、全程只出現 FAKE 代碼、無任何個人資料或真實持倉。本次探測**未發現「已授權、不需客戶 Gate 的純修復」**，因此**沒有做任何程式修正**，也就沒有變異負控可附。
2. 【F】⚙️ 與 🔍 目前都「只存在隔離 poc／未掛載頁」：`registry` 只有 🌍 為 True。⚙️ 只有 NAS 診斷一塊有 renderer（`ui_v3/pages/nas_diag.py`，FAKE 輸入）；「資料健康度」三層**沒有 renderer、沒有 view model**，只有 docs-only 線框。🔍 的 renderer 全在 `poc/`（`DEC-2026-11-19-04` G-A：目前不搬）。
3. 【F】🔍 現存**兩套互不共用的單碼查詢**：`poc/fund_lookup_component_preview/`（經 `ui_v3.adapters.fund_lookup`＋`viewmodels/fund_lookup.py`）與 `poc/fund_search_fixture_preview/` 上區（自帶 `fund_search_logic.py`，不經 adapter）。同一個 FAKE 碼在兩邊的缺值字樣與無法判定原因句不同（見 §2.3）。
4. 【I】兩個最小可交付選項都**卡在客戶 Gate，不卡在工程能力**；推薦先裁「⚙️ 分階段」（§5 P1；本稿 P≠ledger G），因為它能讓 BL-0540 主線有明確 DoD，且不需動 `registry`（選項 B 同樣有 DoD，但價值較低）。

## 1. 方法（FACT）

- 環境：Chromium `/opt/pw-browsers/chromium-1243/chrome-linux64/chrome`（`UI_V2_CHROMIUM`，未 `playwright install`）；venv 為 scratchpad 內既有 venv；以 Playwright 驅動、各 app 以 `streamlit run` 啟動於隨機本機埠，**無任何對外請求**（三個 preview 均離線）。
- 探測腳本在 scratchpad（不入庫）：對三個 app 各在 390×844、1280×900 量測：文件／主區橫向溢出、超出視窗右緣元素數、<13px 的文字節點數、可互動元素尺寸、Tab 焦點外觀；並實際輸入／選擇情境。
- 本稿**不是**重跑既有 browser 守衛：同一批既有測試另跑（§6）；兩者獨立。

## 2. 實跑結果（真 Chromium）

### 2.1 單檔查詢元件（`poc/fund_lookup_component_preview/`）

輸入 14 種字串（Enter 送出），兩個寬度結果一致：

| 輸入 | 畫面（摘） | 溢出 |
|---|---|---|
| `FAKE-OK01` | FAKE 模擬；配息型；成立日期有值；經理費率「此欄尚無…」 | 無 |
| `FAKE-OK02`／`-OK03` | 欄位缺值顯示「此欄尚無可顯示的值」，不是 0／無／不配息 | 無 |
| `FAKE-FAIL1`／`-COOL1`／`-IOERR` | `⛔ 取數失敗`＋「這不是對基金身份的判斷」；三種原因句各異 | 無 |
| `FAKE-PAGE2`／`-NAME1`／`ABC123` | `⬜ 無法判定`（頁面無法確認是這一檔） | 無 |
| `FAKE-REJ1`、空白、`US0378331005`、`http://x.y`、`A<B>C` | 「輸入未通過檢查，未發出查詢」＋各自原因；`A<B>C` 以 escape 後原樣回顯，未被當標籤 | 無 |

- 控制項高度：輸入框 48px、「查詢」鈕 48px；harness 的情境 selectbox 38px（harness 不屬 renderer，README 與既有測試亦已揭露）。
- 焦點：Tab 到「查詢」鈕，`outline: 2px solid` 主色＋外環陰影，可見。

### 2.2 NAS 診斷（`poc/nas_diag_preview/`）

以選項文字逐一選 13 個情境，兩個寬度：徽章依序為 `⛔ 尚未設定`／`◌ 尚未測試`／`✓ 本次連線成功`／`▲ 已降級直連`／`✕ 本次連線失敗`（⑤⑥⑦a⑫）／`▲ 已降級直連`（⑦b）／`⬜ 無法判定`（⑧⑨⑩⑪）；26 次組合皆無溢出（`scrollWidth`＝視窗寬）。renderer 內唯一可互動元素「詳細技術證據」summary 48px。HTTP 結果與檢查時間缺值顯示 `◇ 資料未備`，不為 0。
首輪以下拉索引點選時，虛擬化清單只列 11 項而漏 2 項，故改以文字過濾重跑 13 項（探測方法的教訓，非產品缺陷）。

### 2.3 找基金＋條件篩選（`poc/fund_search_fixture_preview/`）

- 上區單碼：`FAKE-OK01／OK02／LOW1／ERR1`、`ABC123`、空白、ISIN 形皆有獨立畫面；ISIN 只顯示「目前未啟用」，不回顯、不出結果卡。缺值為 `⬜ 資料未備`。
- 下區：3 個條件勾選框，label 48×94px（input 本身 13px，點擊面是 label）；全勾後「符合 2／無法判定 0」，與 README 情境①的 (2,0) 一致。
- 【F】**與 2.1 並排比較的不一致（非缺陷，屬 G-A「不重複實作」的代價）**：同一種「未知合法代碼」，2.1 說「找不到對應頁面」，2.3 說「離線預覽沒有這個代碼的模擬資料」；缺值 2.1 為「此欄尚無可顯示的值」、2.3 為「⬜ 資料未備」；空白輸入 2.1 為入口攔截「請先輸入基金代碼」、2.3 為「⬜ 無法判定（無法辨識格式）」並在輸入代碼列顯示 `⬜ 資料未備`。兩套都是 FAKE、都標了 PendingWording，未違反任何現行守衛。
- 兩個 app 的 Streamlit 工具列「Deploy」鈕屬 dev server 殼，不計入。

### 2.4 缺陷判定

可互動元素高度、溢出、焦點、缺值≠0、個資：無違規。故**無「純修復」可做**（任務授權的修復範圍：poc／pages 預覽檔與其測試）。

## 3. Readiness matrix（五頁）

| 頁 | 已可實際操作（【F】） | 只存在 FAKE | 缺 renderer／adapter | 掛載需改的檔與守衛（【I】依 grep；未實際試改） | 客戶 Gate |
|---|---|---|---|---|---|
| 🌍 `mkt` | registry True；`app_preview` 有 renderer；controls＋adapter 取數；本稿**未實跑**（有既有 AppTest／browser 守衛） | 無 | 無 | 已掛載 | 無（BL-0559 視覺批另案；BL-0540 G-3 影響其 `▸ 各項資料狀態`） |
| 💼 `ast` | 本稿未實跑；`pages/assets.py` 僅 FAKE 隔離預覽 | `pages/assets.py` FAKE renderer＋`poc/assets_fixture_preview/` | 正式掛載用 renderer 入口、真來源接線（`adapters/assets_source.py` 無 production 呼叫端，引自 BL-0540 證據，本組未重驗） | `shell/registry.py`、`app_preview.py::renderers`；守衛 `test_ui_v3_page_registry_guard.py`（寫死 `["mkt"]`）、`test_ui_v3_navigation_shell.py:41`、`test_ui_v3_assets_source_import_isolation.py:240`、`test_ui_v3_top_nav_browser.py` 等 | 開放 ledger G2（S-AST-M1，`open_items_ledger` §4；本稿 P≠ledger G） |
| 🔍 `exp` | 單碼查詢（2.1、2.3 上區）、條件篩選（2.3 下區）皆可操作 | 兩個 poc 預覽全是 FAKE 輸入；選股池情境全為人造 | renderer 住 `poc/`（G-A 不搬）；無正式取數 loader（adapter 只收注入函式）；EXP-6 正式契約未核准 | 同上；另需把 renderer 移進 `ui_v3/pages/`（`LAYER_DEPS["pages"]` 現可 import viewmodels，但 poc 的 `fund_lookup_wording`、`fund_search_logic` 不在 ui_v3 內）；`tests/poc_*` 守衛的 `ALLOWED_PREFIX` | `DEC-2026-11-19-04` 已裁 G-A（轉述〔待核〕）；搬移須新 Gate（Gate-M） |
| 🤖 `ai` | 不可進（正確） | — | — | `PageSlot` 建構時即擋 registered=True | Phase 7（`DEC-2026-10-29-07`） |
| ⚙️ `set` | NAS 診斷 13 情境可操作（2.2） | NAS 診斷全為 FAKE；`docs/design/ui_b_settings_data_health_wireframe_2026_11_20.html` 為靜態線框 | **資料健康度三層無 VM、無 renderer**；類別層狀態詞全待客戶定字；`freshness_state` 恆 undetermined（門檻待 Threshold Gate）；NAS 診斷欄位 `infra/proxy.py` 能否產出＝【NV】 | `registry.py`、`app_preview.py`、同 💼 的守衛；`pages/nas_diag.py` 經 `ui_v3.shell.nav` 取斷點常數，非獨立 | BL-0540 G-3（ledger G1；本稿 P≠ledger G）、BL-0550 九項 Pending、BL-0560(a)（⚙️ 不得有獨立 OneBrain 摘要） |

註：⚙️ 唯一與 🌍 的耦合是 BL-0540 要把 `▸ 各項資料狀態` 移到 ⚙️；搬動前提（bl0540 證據 §3、R7）是「⚙️ 掛載、搬遷、入口同批同 PR」。本稿**不建議先做新增入口**（死入口）。

## 4. 兩個最小可交付選項比較

| 項目 | 選項 A：⚙️ deterministic 健康度第一階段 | 選項 B：🔍 使用者輸入單碼、只離線注入 |
|---|---|---|
| 要交付什麼（具體） | 新增隔離 `poc/settings_health_preview/`（FAKE 情境 selectbox）＋純 VM `ui_v3/viewmodels/settings_health.py`（輸入＝已觀測事實；輸出＝①類別層摘要〔只含「市場」「利率」兩類有資料，其餘顯示「未接線／未評估」〕、②逐序列列、③預設收合診斷）＋ renderer（先放 poc，不放 `ui_v3/pages/`）。**不接 `registry`、不動 🌍**。 | 把現存兩套單碼查詢收斂成一套（2.3 的上區改走 `ui_v3.adapters.fund_lookup`＋同一 renderer），或明文保留兩套並加共同字樣表；仍在 `poc/`，不接 `registry`。 |
| 為何可行／現狀 | 已有 `ShellStatus`、`DomainStatus`、NAS VM 可當輸入形狀；NAS 診斷是同型先例（FAKE、13 情境、browser 守衛）。 | adapter、VM、renderer、FakeLoader、mutations 測試皆已存在且通過。 |
| 需先有的客戶決定 | 1) 類別層狀態詞定字（線框 §5-A 全部 Pending）；2) 線框核准（UI-B 為 docs-only，未核准）；3) BL-0540 G-3 範圍。 | 1) 是否推翻 G-A「不重複實作」的現狀（收斂＝改 `poc/fund_search_*`）；2) 缺值字樣二選一（`⬜ 資料未備` 或「此欄尚無…」）；3) EXP-6 正式契約仍未核准。 |
| 最小測試 DoD | 純函式 VM 測試（輸入乘積→狀態；缺值不為 0；範圍外類別不得為綠／「正常」）；renderer 結構測試（區塊順序、③預設收合、無外連、無 secrets 形字串）；AppTest；Chromium 390／1280（溢出、48px、焦點、缺值）；變異負控（拔掉「範圍外類別」判斷必轉紅）；`tests/ui_v3` import／wording／no-leak 守衛全綠。 | 兩個 preview 同碼同畫面的對照測試（同輸入→同狀態與同字樣）；既有 `test_fund_lookup_cmp_*`、`test_fund_search_*` 全綠；變異負控（把共用字樣改回分歧必轉紅）；Chromium 390／1280。 |
| 風險 | 新增視覺元件＝§-1.5.4 需草稿（已有線框，但未核准）；字樣全 Pending；易被讀成「健康度已完成」。 | 改動 `poc/` 既有已核准預覽，易觸及 `DEC-2026-11-17-02` 授權邊界；字樣二選一本身是客戶裁示。 |
| 掛載（之後） | 仍需 Gate-M＋BL-0540 同批 PR。 | 仍需 Gate-M＋G-A 反轉。 |
| 【I】本組讀法 | 價值較高（解鎖 BL-0540 主線），工程量中，客戶決定數 3。 | 價值較低（多為字樣統一），工程量小，但是「重複實作」是否為問題本身待客戶定義。 |

## 5. 可直接裁示的提案 P1–P3（≤3 項；本稿 P 編號與 `open_items_ledger` 的 G1–G3 是不同東西；推薦為執行組讀法，可被推翻）

**P1｜（本稿 P≠ledger G）是否核准「⚙️ 資料健康度分階段」：第一階段只做隔離 FAKE Preview（選項 A），不掛 registry、不搬 🌍 任何揭露**
- 選項：(a) 核准；(b) 先只定字樣（類別層狀態詞），暫不做 Preview；(c) 不做。
- 推薦：(a)。理由：它是 BL-0540 G-3 的前置、與 NAS 診斷同型、不動任何現有已掛頁。
- 若選 (a)，請同時回答：線框 `ui_b_settings_data_health_wireframe_2026_11_20.html` 是否作為草稿核准（§-1.5.4）。

**P2｜（本稿 P≠ledger G）🔍 兩套單碼查詢：維持現狀（G-A）或收斂**
- 選項：(a) 維持現狀，僅在 README 並列說明差異；(b) 收斂為單一路徑（走 adapter），缺值／無法判定字樣二選一；(c) 暫不處理。
- 推薦：(a)。理由：不重複實作的代價目前只是預覽字樣不同，兩邊都是 FAKE；(b) 需先定字樣且觸及已核准預覽。

**P3｜（本稿 P≠ledger G）⚙️／🔍 是否授權之後「掛載到 Preview App」的 Gate-M 預審（只做影響清單與守衛差額，不改 registry）**
- 選項：(a) 授權預審；(b) 暫緩至 P1 完成。
- 推薦：(b)。理由：P1 沒定前掛載 ⚙️ 只會得到 NAS 一塊；與 BL-0540 要求的「同批同 PR」衝突。

## 6. 測試原文輸出

### 6.1 與預覽相關的測試（背景執行完成）

```
1971 passed in 574.52s (0:09:34)
```

指令：`pytest tests/poc_nas_diag_preview tests/poc_fund_search_preview tests/poc_fund_lookup_component_preview tests/ui_v3/test_ui_v3_nas_diag_renderer.py tests/ui_v3/test_ui_v3_nas_diag_viewmodel.py tests/ui_v3/test_ui_v3_fund_lookup_adapter.py tests/ui_v3/test_ui_v3_fund_lookup_viewmodel.py tests/ui_v3/test_ui_v3_fund_lookup_mutations.py -q -p no:cacheprovider`。測試時 HEAD＝`bf3d61b2013adc4f1aae7aac525f76a003e7a887`（worktree 基準；本報告檔當時尚未 commit，不影響該批測試目標）；環境：scratchpad venv 的 python、`UI_V2_CHROMIUM=/opt/pw-browsers/chromium-1243/chrome-linux64/chrome`，未帶 `--noconftest`，無其他旗標。含 browser slow lane；CI 的 slow lane `continue-on-error`，此結果是本機證據，不是 CI 結論。

### 6.2 治理守衛四檔

```
........................................................................ [ 60%]
................................................                         [100%]
120 passed in 82.90s (0:01:22)
```

指令：`pytest tests/test_canonical_rule_consistency.py tests/test_doc_counters.py tests/test_constitution_file_refs.py tests/test_retired_exception_ids.py -q -p no:cacheprovider`。測試時 HEAD＝`bf3d61b2013adc4f1aae7aac525f76a003e7a887`；執行時 report.md 已寫成但尚未 commit（工作樹含該未追蹤檔）；同 scratchpad venv，未帶 `--noconftest`，無其他旗標。

## 7. FACT／INFERENCE／NOT VERIFIED

| 類 | 內容 |
|---|---|
| FACT | §2 全部實跑所見；registry 僅 `mkt`；`pages/` 無 set／exp renderer；兩套單碼查詢並存；13 個 NAS 情境 × 2 寬度皆無溢出；1971 passed。 |
| INFERENCE | 掛載需改的守衛清單（grep 所得，未實際試改後跑紅）；選項 A／B 的工程量與價值判斷；推薦。 |
| NOT VERIFIED | 🌍／💼 頁本稿未實跑；Streamlit Cloud 與真機（未驗，不宣稱 PASS）；`infra/proxy.py` 能否產出 NAS VM 欄位；BL-0540 證據中「基金／持倉／配息／匯率／景氣無健康度資料來源」本稿未重驗；DEC 轉述內容的來源真實性（repo 無逐字存檔）；未合併、未 push、未開 PR、CI 未跑。 |
