# BL-0544｜手機頁首五頁籤最小合法修正與施工 Gate 提案（2026-11-07）

> **僅為 ChatGPT 產品／治理提案，非客戶新裁示、非 44 amendment、非施工授權。** 依 main `b215d13b8def1715005d68087b266058f812046b`（PR #1162 合併後）與已合入的 `DEC-2026-11-06-01`／`-02`、`docs/v2/80` §18、`docs/evidence/new_ui2_top_tabs_44_amendment_inventory_2026_11_06.md` 整理。本檔不能取代 frozen 44／57／CONSTITUTION、DECISIONS 或精確線框核准。

## 0. 已確定／尚未確定

- **已核准產品方向**：New UI2 **手機**頁首橫向五頁籤，順序固定 🌍／💼／🔍／🤖／⚙️；僅 supersede `DEC-2026-10-27-11` 的**手機導航位置形式**（底部 → 頂部）。桌機側欄、登入／OAuth、Active Sheet、五頁 IA、🤖 Phase 7 前可見不可進都不變。
- **事實勘誤**：44 不含 `底部`／`bottom` 字面強制條款；44 第二節 2.1 的 768 是欄數斷點，不是導覽形式條款。原盤點列出 44 :5627 帳號入口「導覽抽屜或精簡帳號控制」、:5384 與 :5551 的手機第一屏條件；均須維持且重驗，**不能自行宣稱 44 已合法 amended**。
- **目前程式**：`ui_v3/shell/nav.py` 仍是手機 bottom-nav（`MOBILE_MAX_PX=768`、`TOUCH_MIN_PX=48`、`BOTTOM_NAV_HEIGHT_PX=60`），`ui_v3/pages/chrome.py` 與 `ui_v3/design/tokens.py`、navigation shell tests、visual fidelity tests 有相依；尚未改程式或測試。
- **授權邊界**：現有 B 是**設計方向裁示**；不等於 frozen 44 合法修正或 Claude Code 新一批程式施工授權。不得藉此動 Old UI、`ui_v2`、金融公式、來源、Risk Cap、配息、NAV/FX、OAuth 或 Phase 7。

## 1. 三條可行修正路線（供客戶真正需要的 Gate 核准）

| 路線 | 作法 | 正確性／風險 | 速度／Token | 結論 |
|---|---|---|---|---|
| A. 直接修 44 正文 | 正式走 44 amendment 與 md5 guard 更新；僅更動真實衝突條款 | 程序嚴謹，但現時無明文底部條款，可能無必要解凍；容易擴大測試 | 最慢／高 | 非預設 |
| **B. 最小 successor／適用性確認** | 逐條確認 44 :5627、:5384、:5551 與頂部方案不矛盾，對較早 `DEC-2026-10-27-11` 的手機位置部分以已核准的較新 DEC 為 successor；**由客戶明示確認此路線是否滿足 44 合法修正 Gate**。若確認不必修 44，保持 44 原封不動，並將裁示寫 DEC／BL／設計 spec | **最少變更，且不誤稱修改過 44；法律／治理適用性須客戶核准，不能由 AI 推定** | **最快／最低 Token** | **推薦** |
| C. 另立 44 最小 amendment 附錄 | 只加適用條款／例外與 44 hash guard，保留原文，依正式 amendment 程序 | 合規穩健，但多一層 frozen 版本變更及 tests／審查成本 | 中／中高 | 若 B 被否決時採用 |

**建議：B（先精確定位、再做單點決定）**。此處 B 指「合法修正路線」，與客戶已核准的**手機 UI 方案 B**是不同選項；不可混淆。如果客戶或上位治理指出 B 無法構成合法 44 amendment，必須回到 C 或按正式程序提案，不能逕自跳過。

## 2. 建議的最小施工授權範圍（仍待客戶核准）

只授權 **Preview-only** 的 `ui_v3` shell 導覽外觀變更：
1. 手機尺寸（以現行 `MOBILE_MAX_PX=768` 為待核查實作斷點）將固定底部五入口改為**頁首可橫向捲動五頁籤**；桌機 sidebar 保留；不註冊空殼頁。
2. 五頁名稱、順序、`🤖` 禁入、≤2 次互動、共用 routing 與 APPROVED_WORDING 不變。頁首右側精簡登入入口不得被覆蓋；不改 OAuth callback/session/token 或 Active Sheet 身分規則。
3. 避免頁面橫向溢出與首屏遮擋；顧及 safe-area／WebView／鍵盤／螢幕閱讀器，`48px` 觸控區與 active/focus 語意；只改導覽 shell 必要檔案與對應 tests、tokens；**不改頁面資料內容、任何金融邏輯或正式 Cloud cutover**。
4. 測試與驗收：390／768／769／1280px（包含 768/769 邊界）；390 首屏結論燈仍可見且不暗中調高 ≤5 預算；側欄、頁籤 scrolling、帳號入口、🤖 disabled、路由及 Visual Fidelity；真實 WebView／手機測試無法執行者標未驗，不得當 PASS。
5. 範圍外項目都不授權：`ui_v2`／Old UI、正式上線切換、UI 第六頁、新資料源、配息／NAV／FX、Risk Cap、健康准入、OneBrain/Phase 7。正式版面必須經精確線框／字樣 Gate、獨立 QA 與 CI。

## 3. 文件責任與最短路徑

- **ChatGPT**：核對 frozen 44 真實條款及 80 §18；提出本提案；記錄客戶對 B 或 C 的最小核准範圍於 `docs/DECISIONS.md`，同步 `docs/BACKLOG.md`／`docs/HANDOFF.md` 及對應 spec；合法修正與 UI 施工授權是兩個不同 Gate。
- **獨立 QA**：先核對「沒有偷偷解凍 44」「上位條款適用性」與案中完整限制（治理等級）。
- **Claude Code**：只有 Gate 真正核准且落盤、CI 合格後才做上述單切片 Preview UI 程式＋針對性測試；由非作者 QA 複核，再由 ChatGPT GitHub Gate/Auto-Ship。
- **最短依賴鏈**：#1162 已合併 → 獨立審閱最小修正路線 → 客戶只裁示**B 的合法適用性**及**限縮施工範圍** → DEC/BL/HANDOFF 落盤 → Code 單切片 → QA/CI → Preview 驗收；無須等 BL-0541 廣域清理。

## 4. 待客戶單點裁示（不是重問手機位置）

**建議核准句**：「我同意 BL-0544 走最小 successor／適用性確認 B：先由獨立稽核確認 44 真實相關條文與頁首導覽無衝突；若無直接衝突，44 不動，較新 DEC 僅取代舊 DEC 的手機導覽位置。完成合法 Gate、精確 UI 線框及獨立 QA 後，授權 Claude Code **只做 Preview 的 ui_v3 手機頁首五頁籤 shell 單切片**，不含資料、OAuth、Phase 7 或 cutover。若查到真實 44 文字衝突，停下按正式 amendment 另裁示。」

> 上述句子是**建議裁示**，未經客戶明示同意以前，不得登記為「已核准」或視為施工許可。

## 5. 2026-11-07 客戶裁示狀態更新（不修改原提案與三路比較）

- **已核准方案 B**：客戶針對本提案與限縮 Preview-only 工作回覆「同意 B」。正式裁示射程、Stop Gate 與不得動工範圍已記 `docs/DECISIONS.md` **`DEC-2026-11-07-01`**，`docs/BACKLOG.md` **BL-0544**，交接見 `docs/HANDOFF.md`。
- **還沒核准完成的不是 B 選型，而是 B 的合法適用性及施工前 Gate**：非作者稽核仍需逐條確認 frozen 44 與導覽位置沒有真實衝突，並驗證上位治理允許以 newer DEC 作適用性 successor。精確線框、字樣與驗收契約也需獨立完成，不能把客戶一句「同意 B」擴大解讀為所有程序均 PASS。
- **施工權限為條件式而非即刻開工**：合法 Gate／精確線框／獨立 QA 通過、GitHub 落盤後，才可按 DEC 在 `ui_v3` 做 Preview-only 手機頁首五頁籤；如遇真實 frozen 衝突，回到正式 amendment 路線，停止程式施工。
- **本 PR 是治理文件批**，無 frozen 44、57、CONSTITUTION、程式、測試或 OAuth 改動；完成本 PR 的治理稽核與 CI 前仍 Draft，不直接 Auto-Ship。

## 6. 2026-11-07 增量原文適用性盤點（GitHub main `d0a0af20390af66171f7c75c46aaff9c18a28e0f`；**非正式獨立 QA**）

此節是逐條查得的原始條文、風險判讀及候選驗收契約；不是新的客戶裁示。**已選方案 B，但不代表合法適用性 Gate 已通過**。

| 權威／實作證據 | 查得的內容 | 本案判讀與未驗點 |
|---|---|---|
| frozen `44` §2.1，約 149–189 | 斷點 375／768／1280；≤768 單欄、769–1279 兩欄、≥1280 三欄；硬規則文字為「**任何一段都不出現橫向捲動**」，接著說放不下須換行／單欄，不能把**整頁**推寬 | 44 未指定手機導覽必須在底部；**但「任何一段」是否也禁止局部頁籤條的橫向滾動，無法只憑整頁不溢出推定通過**；這是本批新增的真實文本歧義／潛在衝突 |
| frozen `44` 之十八其二、之十九其七，約 5384、5551 | 手機第一屏比桌機少；390px 首屏可見結論 chip，且能看到主圖或主數字 | 頁首導覽會佔高度；**未量測**前不可承諾首屏符合 |
| frozen `44` 之二十其三，約 5627 | 手機帳號入口可在導覽抽屜或精簡帳號控制，須容易取得且不能吃掉主要第一屏；OAuth／Active Sheet 不改 | 頁籤與帳號入口要共存；現行 `ui_v3` 並沒有可視為完整登入入口的實作證據，不得做假登入按鈕 |
| `79` 檔頭的「客戶核准後落盤策略」 | **只有第一個實作批與 44 的真實條文衝突時**，才啟動新的 44 amendment | 支持 B 先查適用性，不支持「任何變更都先動 44」 |
| `80` §18.2 第 1、2 點（2026-11-06 記錄） | 舊要求「先產出最小正式 amendment」，並要求「橫向頁籤滾動」 | 已有較新 `DEC-2026-11-07-01` 選 B；但「局部滾動」仍可能撞 44 原文字面，須在正式線框核准前解決 |
| `CONSTITUTION` §1.1～1.2；`57` §3 的 1-3 | F1～F6 凍結的是舊線上 UI、`app.py`、services／資料與遷移；`57` 保留子法 §6.1「全站底部固定標註」的**投資免責聲明** | 「底部固定標註」不是 bottom navigation，不能誤當成 UI 導覽位置；本批不修改 F1～F6，也不碰聲明 |
| 現行 `ui_v3/shell/nav.py`、`ui_v3/pages/chrome.py`、`ui_v3/shell/registry.py` | CSS 固定底欄、`st.navigation(position="hidden")` 只管路由，`st.page_link` 畫導覽；目前只有 🌍 已 registered，其餘（含 🤖）未註冊 | Shell 單切片可局限 `ui_v3`；**不應為了新導覽放行任何未實作頁** |

### 6.1 對「五頁籤」的三種最小處置（新發現子題；客戶 B 的路線選擇不重問）

| 子方案 | 實作形狀 | 44 §2.1 風險 | 速度／回修／Token | Gate |
|---|---|---|---|---|
| **S1：五等寬頁首標籤、不橫向捲動** | 390px／375px 使用已核准短字樣「市場／資產／找基金／AI／設定」，五欄同列；更窄時檢查縮字或換行能否維持可點高度／資訊密度 | **較低**：無局部滾動，維持 44 字面；但較舊 `80` §18.2 的「滾動」測試與本提案 §2「可橫向捲動」須經正式 UI Gate 覆核，不可私自抹除 | **最快、最低 token**；裝置寬度仍需實測 | 本方案為**設計候選**，非現行核准線框 |
| S2：只讓頁籤容器局部滑動 | 保留五入口，整頁絕不橫溢，頁籤內部 `overflow-x:auto`；可鍵盤操作及聚焦滾入可見範圍 | **歧義待決**：44「任何一段」可能也禁止局部捲動；不得直接宣稱合規 | 中；需解決解釋衝突與可達性測試 | 先由獨立治理 QA／正式適用性 Gate 認定是否容許，**UNVERIFIED** |
| S3：正式 44 最小 amendment | 若 44 明文射程包括頁籤局部捲動且仍選滑動，就提出「頁籤容器例外、整頁仍禁止」的正式條文與守衛變更 | 可釐清文本，但**不可自行解凍** | 最慢、風險與審查較高 | 依原凍結修正程序取得客戶核准，再獨立 QA |

**初步建議 S1 為最小可驗候選**，因使用者核准的核心是「手機導覽改到頁首，五頁水平排列」，不是新開任何投資邏輯；但 S1 與已落盤的「頁籤可橫向捲動」要求存在差異，**須先完成客戶精確線框／字樣 Gate，不能在本 PR 視為 S1 已獲核准**。若後續必須保留可滑動，依 S2→S3 的合法性 Gate；不得偷偷改 44 文義。

## 7. 精確 Shell 線框候選與測試契約（僅供 Gate；不是已核准 UI）

**適用範圍**：New UI2 Preview-only `ui_v3`，五頁登錄表保持不變；沒有完成任何 Streamlit／Cloud／手機 WebView 實測。

### 7.1 構圖／字樣／權責

```text
390×844 手機（位置候選；非現行實際畫面）
┌─────────────────────────────────┐
│ 可用的品牌／帳號精簡入口（依 #1161；│
│ 未實作時保持原本安全登入流程，不造假）│
├─────────────────────────────────┤
│ 🌍 市場  💼 資產  🔍 找基金  🤖 AI  ⚙️ 設定 │ ← 五頁籤同一行，S1 不橫向滑動
├─────────────────────────────────┤
│ PREVIEW 〔取得狀態〕〔取得時間〕   │ ← 原 ShellStatus，不猜來源時間
│ ① 畫面結論 chip＋簡短狀態          │
│ 原 🌍 核心圖／主數字可見            │ ← 首屏預算待實機量測
│ 主內容保持不變                    │
└─────────────────────────────────┘

769／1280 桌機／平板：保留原側欄與內容。768 及以下才顯示上方五頁籤。
```

- **已核准字樣只引用** `shared/ui_semantics/rules.py::APPROVED_WORDING`：`shell_nav_short_mkt/ast/exp/ai/set`、`shell_nav_soon`（未註冊頁＝開發中）、`shell_nav_not_open`（🤖＝尚未開放）、`shell_nav_aria`（主要導覽）、`shell_preview_tag`（PREVIEW）、`shell_app_title`。不得新增平行字樣表／推定正式用詞。
- 有頁：使用現行 `registered` 與 `st.page_link`；無頁：可見、不得點、無 URL、無 renderer、無假資料。🤖 Phase 7 前絕不能 registered=True。
- 目前頁使用**非顏色唯一**的粗體＋可辨識底線／邊框；理想需 `aria-current`／等價可驗的語意。現行只有 key＋CSS 強調，是否有真正的 `aria-current` **尚未證實**，不得憑 CSS 代替無障礙 QA。
- `TOUCH_MIN_PX=48` 是現有下限；固定底欄移除後不留遮蓋頁尾的 overlay。帳號入口是獨立既有設計／授權來源，本切片**不新增 OAuth／Active Sheet 流程**。
- S1 如在窄於 375 或字體放大後無法保留 5 個入口的可達性與 44 禁捲動規則，**停止提交正式 UI**，先回法律／線框 Gate；不得縮到小於觸控下限冒充完成。

### 7.2 驗收矩陣（此刻全為 NOT RUN）

| case | 容許變動 | 必要斷言／證據 |
|---|---|---|
| 390×844、375×812、374px | 上方五頁標籤；側欄及底部 overlay 不可見 | `scrollWidth <= clientWidth` 整頁無橫溢；首屏結論 chip + 主圖／主數字皆可見；48px 觸控，字樣未截斷成另一意思 |
| 768／769／1280px | 768 為手機單欄＋上方；769 起桌機側欄；1280 不變 | 兩種導覽不得同時可見／可互動；四層頁內容不改；無重複導覽 |
| 路由／可進／不可進 | 只 🌍 registered；其他保留 `REASON_WIREFRAME_PENDING`、🤖 `REASON_PHASE7` | 目標五頁順序與短字樣一致；不可進項目無可操作連結；沒有跳向空頁；重新整理不猜身分 |
| 目前頁／鍵盤／讀屏 | 可聚焦頁連結，有明顯 focus ring，Enter 正確導航 | 非顏色唯一狀態、當前頁可被讀屏辨識；未掛載項目確實禁點、禁執行，不假裝 Tab 可進 |
| 帳號／WebView／safe-area | 帳號入口依既有契約，頁首和登入不可互遮 | 390 正式 Preview＋至少一種實際嵌入 WebView／真機證據；安全區、動態網址列、鍵盤可用性；無實測＝NOT RUN |
| 正式禁區／資料層 | `ui_v3` Preview shell＋必要的定向測試 | `ui_v2`／Old UI、frozen 44／57、services、OAuth、NAV／FX、Rule／Risk Cap、OneBrain、正式入口、Cloud cutover diff=0 |
| CI／Visual Fidelity | Fast／Schema／Slow／Visual、必要獨立 QA | 四項最新 head job conclusion=success；390 與桌機 production-like screenshot；不能用 deterministic fixture 圖當正式 Cloud 驗收 |

**留在 Gate 的兩項未決**：① 44「任何一段都不出現橫向捲動」是否允許 S2 局部頁籤滑動；② S1 不滑動版是否作為最終精確線框（需依現行客戶裁示程序核准）。**這兩項未解以前不開 Code PR，不將此文件簽為 QA PASS。**

## 8. 既有 Code／測試實際依賴與最小施工差異（2026-11-07 唯讀核對；**沒有動程式**）

取證基準為 main `d0a0af20390af66171f7c75c46aaff9c18a28e0f`，僅記錄**現存原始碼／測試**及未來的必要差異；這份工程影響盤點不是 B 方案的合法性簽核、不是線框客戶核准，也不構成另一張 Code 派工單。

| 真實檔案／符號 | 目前原始碼證據 | **若 Gate 日後通過**的最小處置 |
|---|---|---|
| `ui_v3/shell/nav.py`：`shell_css`, `MOBILE_MAX_PX`, `TOUCH_MIN_PX`, `BOTTOM_KEY` | ≤768px 固定底部、桌機側欄；`position:fixed; bottom:0`；48px 觸控下限、60px 底欄及 `padding-bottom` 避讓 | 只替換**導覽位置／CSS**，消除底部 overlay／頁尾避讓舊依賴；保留 768 邊界、48px 下限、對比與焦點狀態。S1／S2 尚未裁定，**不可先寫 overflow-x 或偷偷調閾值** |
| `ui_v3/pages/chrome.py`：`render_navigation`, `disabled_bottom_html`, `_now_key` | `st.navigation(position="hidden")` 路由，`st.page_link` 活頁、未掛載項為 `aria-disabled` 無 URL；手機 DOM 掛於 `st.container(key=nav.BOTTOM_KEY,...)` | 保留 routing 與未掛載保護；移至已核准頁首區時審查 DOM 順序與 PREVIEW Status Bar、不多做第二套導航、不讓不可進頁變可點。**尚未證明 `aria-current` 會由 Streamlit 提供** |
| `ui_v3/shell/registry.py`：`IA_PAGES` | 五頁 IA，只有 `mkt` 已 `registered=True`；`ai` 禁註冊、其餘缺正式整頁實作 | **保持原封不動**，不可為了測試新頁籤而新增空殼 renderer 或開 Phase 7 |
| `shared/ui_semantics/rules.py`／`ui_v3/viewmodels/preview_wording.py` | 19 個 `shell_*` 正式字樣取 `APPROVED_WORDING`；短字串為市場／資產／找基金／AI／設定；已核准字樣不放 pending table | **保持原封不動**，本批不造新標籤、狀態符號或平行字樣表；若佈局裝不下，回 UI Gate，不縮到不能辨識 |
| `ui_v3/design/tokens.py` | `nav.bottom`、`nav.item` 仍是**值為 None**的設計 token 名稱，非 production 數值 | 僅在正式 UI contract 要求改名／定值時一併修改其測試；**不能把 `nav.bottom` 沿用作新頂欄的正式語意** |
| `ui_v3/app_preview.py` | 模組文件仍稱手機底欄，`main()` 沿用 routing／renderer | 實作批若產生已核准新行為，**只同步 docstring**，不得動正式入口或 cutover |
| `tests/ui_v3/test_ui_v3_navigation_shell.py` | `test_css_switches_between_sidebar_and_bottom_nav_at_one_breakpoint` 明確斷言 `BOTTOM_NAV_HEIGHT_PX`、`bottom:0`、底部避讓；`test_disabled_nav_items_are_not_links_and_say_under_development` 覆蓋不可點；AppTest 有真頁註冊檢查 | 逐條改**過期底欄斷言**為核准的新頂欄契約，維持原有 IA／disabled／字樣／Missing／狀態守衛；不得為求綠燈直接刪測試 |
| `tests/ui_v3/test_ui_v3_design_tokens.py`、`tests/visual_fidelity/vf_config.py` | token 守衛可能與 `nav.bottom` 綁定；Visual Fidelity viewport 現僅 390×844、1280×800（見既有清冊 §3） | 新測 375／374、768／769 由**額外定向證據**補足；原 390／桌機截圖保留。若更改 VF 配置引起其他工作流行為改變，另核最小範圍 |
| `docs/evidence/bl0536_shell_h5_2026-11-03/measure.js` | 歷史 Chromium 測量腳本硬查 `.st-key-uv3-bottom-nav`，用底欄頂緣作首屏下限 | **不要改寫歷史測量證據**；在新 UI Code PR 另存量測版本，改按 viewport 真實可視範圍、頁首佔用與 chart 起點計算；不要把舊底欄測量冒充新驗收 |

### 8.1 施工順序（條件式，沒有授權立即開始）

1. 獨立驗 44 §2.1 的「四個**視窗寬度段**」及「不把**整頁**推寬」與**局部導覽容器滾動**是否可區分；同時核 44 之十九首屏與帳號入口、57／CONSTITUTION 程序。若仍有歧義，`LEGAL_GATE_UNVERIFIED`，不得自認合規。
2. 依正式 UI Gate 確認 **S1 或 S2 的精確畫面與字樣**。S1 非橫向滑動，可能需要修 80 §18.2 所列的原「滾動」驗收方向；S2 必須先解上項歧義。兩條不能同時做成互相衝突的 CSS。
3. 先讓 `nav.shell_css()`／`chrome.render_navigation()` 的定向守衛具備新布局測試，再改 Preview shell；只有 🌍 可進、其他五頁槽位仍保留相同可見／禁入狀態；不影響原 Status Bar／資料／認證。
4. 390×844 與 1280×800 瀏覽器實測，並補 375／374、768／769 與字體縮放／鍵盤 focus；局部滑動時需量測 `documentElement.scrollWidth <= clientWidth` 和容器本身的捲動與鍵盤可操作性，兩者分開記；有資料時須可見結論 chip＋主圖／主數字。WebView／真機未量測一律 `NOT RUN`。
5. 同 PR 完成定向測試、4 個 CI job、真正非作者 UI／治理 QA 與 production-like 截圖；**不得由本文件的技術清單替代客戶線框、法規適用性與實機驗收**。

**單一下一步**：這一份文件盤點已把「可以先問程式碼什麼」縮成明確差異清單。Code 目前仍停在 `DEC-2026-11-07-01` 的條件授權之前，無需交 Claude 重做同一份文件／技術準備。
