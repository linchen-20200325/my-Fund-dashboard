# 🔍 找基金最小離線模組搬移 — Stop Gate 可行性分析（2026-11-19）

> **稽核狀態**：單組作者＋已有一組非作者稽核（subagent，非 GitHub review）：Stop 結論成立、Must-Fix 0。稽核原始報告不在 repo 內，本檔不逐字轉錄；除 Stop 結論外，其餘全稱句與細節未經第二組複驗。
> **性質**：唯讀分析（docs-only），**非客戶裁示、非授權施工**；登記不構成動工授權（`CLAUDE.md` §-1）。配套登記見 `docs/DECISIONS.md` 的 `DEC-2026-11-19-03`。
> **來源**：下列分析內文由 C 線執行組撰寫（原稿標題見下一行），未改動實質內容。

# C 線「🔍 找基金最小離線模組搬移」可行性分析（唯讀；單組執行組，未經第二組複驗）

基準：main `8273f92f`（工作樹乾淨，未改任何 repo 檔）。守衛皆實讀原碼；下列「實測」皆為本組在記憶體內餵檔案內容給守衛函式，或實跑既有測試（`/root/.local/bin/pytest ... --noconftest`，基線 499 passed：poc guards＋logic/renderer＋ui_v3 import／readonly／registry／preview_wording）。模擬腳本：`scratchpad/sim.py`、`sim2.py`（只讀）。

## 0. 結論

**可搬的最小子集 ＝ 空集（在「不改任何既有守衛、不新增 `ui_v3/pages/*`」的前提下）。→ Stop。**

三個決定性理由（各自獨立成立）：
1. **「poc 改成薄層 import 搬出模組」本身會讓既有守衛轉紅**：`tests/poc_fund_search_preview/test_fund_search_guards.py::import_violations` 的白名單 `ALLOWED_PREFIX` 只開 `ui_v3.design`、`ui_v3.viewmodels.exp_counts`、`ui_v3.viewmodels.preview_wording`、`shared.ui_semantics`。poc 一旦 import 任何新的 `ui_v3.viewmodels.<新模組>`，`test_imports_are_inside_the_allowlist[...]` 轉紅（實測四種寫法皆回「不在白名單的 import」）。要改只能改該守衛 ＝ 授權明文禁止。
2. **renderer 無合規的非頁面落點**（`LAYER_DEPS`：`viewmodels` 不能 import `ui_v3.design`／streamlit；`design` 不能 import streamlit／viewmodels；可同時 import design＋viewmodels＋streamlit 的層只有 `pages`、`root`〔`root` 允許 shell/pages/adapters/design/viewmodels，`STREAMLIT_LAYERS` 含 root〕）。`pages/` 即授權明文要求「停下」的範圍（`DEC-2026-11-17-04` 排除 `ui_v3/pages/exp.py`、`DEC-2026-11-18-04` E1 明寫「若日後要放 `ui_v3/pages/`，須客戶 Decision Gate」）；`root` 是 `app_preview` 類頂層進入點所在，且 `DEC-2026-11-17-02` 明文把 renderer 鎖在 poc。（2026-11-19 稽核修正：原稿寫「只能進 pages」不精確。）
3. **logic 的核心（`combine`／`build_filter_view`）依執行組讀法與 DEC-2026-11-17-02 語意及自身 docstring 自述衝突**（推論，見 §2.1 降級說明），且 `classify_lookup` 與已在 `ui_v3/viewmodels/fund_lookup.py` 的輸入型態判斷形成第二套（見 §2.1）。

唯一「技術上最可行」的候選是 **wording**（見 §3），但它仍卡理由 1，且搬了沒有第二個使用者，價值低。

## 1. 模組現況與 import 圖（實讀）

| poc 模組 | 行數 | import（含函式內） | 說明 |
|---|---|---|---|
| `fund_search_logic.py` | 135 | `re`、`dataclasses`、`typing`、`ui_v3.viewmodels.exp_counts` | 單檔查詢分流（`classify_lookup`／`LookupResult`）＋三態組合（`combine`）＋`build_filter_view`（含 `FundRow`／`TraceRow`／`FilterView`） |
| `fund_search_wording.py` | 137 | `html.escape`、`types.MappingProxyType`、`typing`、`shared.ui_semantics.rules`、`ui_v3.viewmodels.preview_wording.PendingWording` | `FUND_SEARCH_PENDING` 字樣表＋`text/pending/status/undetermined/missing_cell/plain` |
| `fund_search_renderer.py` | 318 | `html`、`typing`、`fund_search_logic`、`fund_search_wording`、`ui_v3.design.theme`、`ui_v3.viewmodels.exp_counts`、**函式內 `streamlit`（4 處）** | HTML 組裝＋`render_*`（`st.session_state` 寫 `fs_last_query`） |
| `fund_search_fake_inputs.py` | 82 | 只有 `__future__` | FAKE fixtures；留 poc（授權明列） |
| `app_fund_search_preview.py` | 46 | streamlit、上列四者、`ui_v3.design.theme`；入口含 sys.path 設定與 `main()` | harness；留 poc |

poc 內部以**平面模組名**互 import（`import fund_search_logic as L`，靠入口／測試的 sys.path 設定）。

## 2. 逐模組：能否搬、搬到哪、會碰到哪些守衛

守衛母體（實讀）：`tests/ui_v3/ui_v3_guard_lib.py`（`LAYER_DEPS`、`population()`＝`ui_v3/**/*.py` 全部、`STREAMLIT_LAYERS`、`SHARED_ALLOWED_LAYERS`＝viewmodels/pages）、`test_ui_v3_import_guard`（import 方向、零副作用）、`test_ui_v3_readonly_guard`（寫入面）、`test_ui_v3_page_registry_guard`、`test_ui_v3_preview_wording_guard`、`test_ui_v3_no_engineering_leak_guard`（靜態：`ui_v3/` 字串常數不得為環境變數形）、`test_ui_v3_preview_not_formal_guard`、`test_ui_v3_fixtures_are_fake_guard`；poc 側 `test_fund_search_guards.py`（import 白名單、禁動態 import／寫入面、模組層零副作用、`session_state` 寫入僅一處、字樣、隔離守衛）。`tests/test_services_purity_contract.py` 只掃 `services/**`（及 `repositories`／`fund_fetcher` 反向規則），本組檢視未見其涵蓋 `ui_v3`／`poc`，與本搬移無關。

### 2.1 logic

候選層：`ui_v3/viewmodels/`。
- ui_v3 守衛模擬（in-memory）：放 `viewmodels` 或 `pages`：`import_violations`＝空、寫入面＝空、模組層副作用＝空、環境變數形字串常數＝空 → **對 ui_v3 側守衛不轉紅**。放 `design`：紅（design 不得 import viewmodels）。
- **但 DEC 層衝突（非守衛紅，卻是更根本的）**：
  - 事實：`DEC-2026-11-17-02` 決策內容寫「fixture 三態評估不形成可搬入 production 的新金融公式」；(4)「僅屬測試輸入，不新增正式篩選判準」。`fund_search_logic.py` docstring（及 README）自述「組合規則…不得搬入 production」。
  - **推論（降級，2026-11-19 稽核修正；可被客戶推翻）**：「不得搬入 production」出自該檔自身 docstring 的自述；DEC 條文字面是**描述性質**（說明該評估不形成可搬的公式），**不是**明文禁止搬碼。執行組將其讀為禁止；「`ui_v3/viewmodels/` 是 production 候選樹」亦屬推論。因此 `combine`／`build_filter_view` 排除的依據是「自述＋DEC 語意的保守讀法」，不是 DEC 明文禁令。
  - `classify_lookup`（ISIN 形／代碼形判斷，`_CODE_SHAPE`＝3–24 碼）：`ui_v3/viewmodels/fund_lookup.py` 已有另一套（`looks_like_isin`、`looks_like_url`、`INPUT_ECHO_MAX=64`、ISIN 判斷前移除非英數）；兩套語意不同。搬入＝在 ui_v3 內多一套輸入型態判斷，與 `DEC-2026-11-18-04` 及 `DEC-2026-11-19-02`（Q2 八點）所處理的鍵／輸入語意可能互相牴觸，且「ISIN resolver／正式身分對照不授權」。此部分亦排除。
  - 剩下可搬的只有 `FundRow`／`TraceRow`／`FilterView` 資料類別（無獨立價值）。
- 判定：**不搬**。

### 2.2 wording（最可行候選，但仍卡 §3 的 C1／C2）

候選層：`ui_v3/viewmodels/`（先例：`nas_diag_wording.py`、`assets_preview_wording.py` 皆在 viewmodels）。
- 模擬：`import_violations`（viewmodels／pages）＝空，寫入面／副作用／環境變數形字串＝空。`shared.ui_semantics` 只開 viewmodels／pages，viewmodels 合規。
- ui_v3 側既有字樣守衛：`test_ui_v3_preview_wording_guard` 只比對 `PREVIEW_PENDING_WORDING` 與規則表，不掃新增的 wording 表 → 不轉紅（單組讀碼判斷，未實跑「搬後」狀態）。
- 隔離守衛 `test_no_production_path_references_the_preview`：掃 `ui_v3/**` 檔案**內容**是否含 `fund_search_*` 模組名；另一個測試禁止任何 `ui_v3` 檔含 `"poc/"`。現 wording／logic 檔本文無此類字串（grep 0 命中）；新檔須改名（建議 `exp_filter_wording.py`），避免檔名／註解帶 `fund_search`。
- 仍存在的問題：
  - **C1（紅）**：poc 薄層 import 新模組 → 白名單守衛轉紅（見 §0-1）。
  - **C3（紅，已實讀）**：`test_fund_search_logic_and_renderer.py` 有 `monkeypatch.setattr(W, "FUND_SEARCH_PENDING", mutated)` 的變異測試，共 **2 個測試函式**（第 156 行一個；第 624 行為單一測試內 3 次迴圈迭代）。若薄層只是 re-export，`W.text()` 讀的是搬出模組自己的全域表，patch 不生效，原本預期「轉紅」的斷言變成不紅，測試失敗。解法必須讓 poc 保留「持有表、函式讀 poc 模組全域」的縫（薄層 wrapper），而這又等於 poc 端仍有一份邏輯。
  - **C2（DEC 語意，非守衛）**：`missing_demo`（`⬜ 資料未備`）、`isin_note` 等字樣依 `DEC-2026-11-17-03` G-2～G-6「僅適用本 Preview，不自動變更正式共用字樣」；規則表 `rules.py` 檔頭「`◇` 只限正式模式」。把這些字樣放進 `ui_v3/viewmodels/`（全 ui_v3 共用層）有被當成共用字樣的風險；`DEC-2026-11-18-04` E1 對單檔元件則偏向「字樣檔同置 poc、不新增 viewmodels 檔」（執行組讀法，可被推翻）。先例（nas_diag／assets）存在，故此點為「需客戶表態」而非「必然衝突」。
- 判定：**技術上可搬；在不改守衛的前提下不可行（C1），且搬後無第二使用者，價值低**。

### 2.3 renderer

- 放 `viewmodels`：紅（`ui_v3.design`、streamlit）。放 `design`：紅。放 `pages`：import 守衛綠，但這是**新增 `ui_v3/pages/<x>.py`**，落入授權明文「停下」條件。放 `root`：import 守衛綠（root 允許 design／viewmodels／streamlit），但 root 即 `app_preview` 類頂層進入點層，非 renderer 應在之處，且 `DEC-2026-11-17-02` 明文鎖 renderer 於 poc → 結論不變。
- 另有 poc 側守衛：`test_registry_does_not_register_the_exp_page...` 斷言 `ui_v3/pages/exp.py` 與 `ui_v3/pages/fund_search.py` 不存在；renderer 內 `st.session_state[KEY_QUERY]` 的寫入由 `test_no_session_state_write_outside_the_one_session_key` 以檔名 `fund_search_renderer.py` 鎖定（搬檔即需改守衛）；`test_directory_layout_...` 要求 `fund_search_renderer.py` 仍在 poc 目錄。
- 判定：**不搬（Stop）**。

### 2.4 fake_inputs

授權明列留在 poc。`DEC-2026-11-17-02`：「renderer 與 fake 輸入只放 `poc/fund_search_fixture_preview/` 及其測試目錄」（renderer 一併被該句鎖在 poc）。

## 3. 與 DEC 條文逐條對照

| DEC | 條文要點（實讀 `docs/DECISIONS.md`） | 對搬移的影響 |
|---|---|---|
| 11-17-02 | 授權**僅** `poc/fund_search_fixture_preview/` 及其測試；「renderer 與 fake 輸入只放」該處；不授權改 registry／`app_preview`、掛 🔍 頁；三態「不形成可搬入 production 的新金融公式」（描述性質） | 搬出 poc 本身超出其授權（需新 DEC，正是本草稿）；renderer 被明文鎖 poc；`combine` 依執行組讀法（推論）與其自述衝突 |
| 11-17-03 | G-1 僅放行 `shared.ui_semantics`、限本 Preview、「不放寬正式 adapter 的 import 守衛」；G-2～G-6 字樣僅適用本 Preview | wording 進 viewmodels 不放寬 import 守衛（viewmodels 本來就可 import `shared.ui_semantics`），但「僅適用本 Preview」的字樣被放進共用層需客戶表態（C2） |
| 11-14-08 | S2-T0 暫緩、不掛 🔍 頁、不接 Sheet | 不衝突（本搬移不掛載、不接 Sheet）；若新增 `pages/exp.py` 則衝突 |
| 11-17-04 | 僅 `ui_v3/adapters`、`viewmodels` 與測試之 S2-T0 內部切片；排除 `ui_v3/pages/exp.py`、掛 🔍 頁、registry／`app_preview`、**既有守衛修改** | 明文排除守衛修改與 pages/exp |
| 11-18-04 | E1：單檔元件 renderer／wording 放 poc、不新增 viewmodels 檔、日後放 `ui_v3/pages/` 須 Gate；E2 不改既有守衛 | 與「新增 viewmodels 檔」及「進 pages」傾向相反（執行組讀法） |
| 11-19-01 | P1：🔍／💼／⚙️ 各自獨立掛載 Gate、預設不掛；「掛載 PR 與搬模組 PR 分開」（M-2 卡，執行組候選，未核准） | 本搬移是「搬模組」不是掛載；不衝突，但亦無授權 |

## 4. 最小解法（供客戶 Decision Gate；皆為候選，非裁示）

- **G-A（執行組推薦）：現在不搬。** 理由：無第二個使用者；搬動需改既有守衛（授權禁止）；`combine`／`classify_lookup` 與 DEC 條文衝突；搬了反而要在 poc 與 ui_v3 各留一份邏輯。待真正有 🔍 頁掛載 Gate（M-2 P1 逐頁 Gate）與 S2-T0 解凍後，與掛載一併設計，才有「第二使用者」。
- **G-B（若客戶堅持推進）：僅 wording，需客戶一次明文兩件事**：(i) 新增 `ui_v3/viewmodels/exp_filter_wording.py`（搬 `FUND_SEARCH_PENDING` 資料與純格式化函式；不含 `combine`、`classify_lookup`、renderer）；(ii) **准許對 `tests/poc_fund_search_preview/test_fund_search_guards.py` 的 `ALLOWED_PREFIX` 加唯一一條 `"ui_v3.viewmodels.exp_filter_wording"`（純加法，不放寬其他）**。
  - 搬移方式：資料與「接收 table 參數」的純函式搬出（例 `text_from(table, key, **f)`）；poc `fund_search_wording.py` 留薄層：`FUND_SEARCH_PENDING = moved.FUND_SEARCH_PENDING`，並以 poc 內的 wrapper（`def text(key, **f): return moved.text_from(FUND_SEARCH_PENDING, key, **f)` 等）保留 monkeypatch 縫，使既有 4 個變異測試案例不需修改；`_index`／`SOURCE*`／`RULE_*_KEYS` 同步 re-export（測試會取用）。
  - 測試：既有 poc 測試一字不動；新增 `tests/ui_v3/test_ui_v3_exp_filter_wording.py`（不改既有守衛）：鎖 `status=pending`、出處固定、鍵不在規則表、文字不複寫已核准字樣、無環境變數形字串、與 poc 薄層取字一致（防分叉：比對 poc 表 `is` 搬出表）。
  - 回滾：還原 poc 薄層為原檔、刪新模組與新測試、還原 `ALLOWED_PREFIX` 那一行。
  - 驗收：poc 全部測試（含 browser／apptest）與 `tests/ui_v3` 全綠；registry／`app_preview`／pages 無 diff；`git diff --stat` 僅列 DEC 授權檔。
  - 本方案仍不解決 C2（字樣放共用層）；須客戶明答。
  - **與授權 (5)「避免雙份實作」僅部分相容**：poc 的 wrapper 仍保留函式本體（text／pending／status 等的薄包裝），只有資料表與純邏輯單一來源化。

## 4.1 方案表（含被排除的變體；2026-11-19 稽核補列）

| 變體 | 守衛結果 | 排除原因 |
|---|---|---|
| (a) 在 ui_v3 建**新副本**、poc 不 import | 技術上不使守衛轉紅 | 是複製非搬移，違反授權 (5) 避免雙份實作；`DEC-2026-11-17-04` 的新增檔授權僅涵蓋 S2-T0 內部切片 |
| (b) wording 放 `ui_v3/design` | 層級守衛紅 | design 層不能 import viewmodels 的 `PendingWording`；`shared.ui_semantics` 只開給 viewmodels／pages |
| (c) renderer 放 `root` 層 | import 守衛綠（root 允許 design／viewmodels／streamlit） | root 即 `app_preview` 類頂層；`DEC-2026-11-17-02` 明文鎖 renderer 於 poc；結論不變 |
| (d) wording 放 `viewmodels`＋poc 薄層（G-B） | poc 白名單守衛紅（C1）→ 需改守衛 | 授權禁止改守衛；僅部分避免雙份 |
| (e) 不搬（G-A） | 無 | 推薦 |

## 5. 未查證項（誠實揭露）

1. 授權內容『聽你的建議』指涉哪一項建議、範圍是否等於本任務敘述：repo 無紀錄，**NOT VERIFIED**（ChatGPT 轉達〔待核〕）。
2. 「搬後」狀態未實跑：ui_v3 側守衛結果來自 in-memory 模擬／讀碼；未建立 worktree 實測整套 `tests/ui_v3`。
3. browser／AppTest 層（Chromium、slow lane）是否受影響：未讀完全部、未實跑。
4. `tests/test_services_purity_contract.py` 與 `ui_v3`／`poc` 無涉：單組讀檔與 grep（無 `ui_v3`／`poc` 字樣）判斷，未讀完 1034 行全文。
5. 「poc 內只有這幾個守衛會紅」非窮舉：我只枚舉了 import 白名單（C1）與 monkeypatch 變異測試（C3）；其餘 poc 測試是否有以檔案路徑或模組身分為前提者，只做了 grep 抽查（`read_text|getsource|__file__` 無額外命中）。
6. `DEC-2026-11-18-04` E1 為「執行組讀法，可被客戶推翻」，不是客戶裁示；其方向與 nas_diag 先例相反。
7. 規則 `⬜` 符號在 `ui_v3/viewmodels` 新字樣檔中是否被未來守衛視為違規：現有守衛不掃，未來未知。
8. CI／GitHub 狀態（main CI、open PR）未重查。
