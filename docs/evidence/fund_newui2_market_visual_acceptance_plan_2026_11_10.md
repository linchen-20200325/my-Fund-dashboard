# 基金 New UI2「🌍 市場與趨勢」視覺驗收規劃與證據歸檔（第二階段；2026-11-10）

> **性質**：驗收規劃與證據歸檔（docs-only）。**不是**新的設計 SSOT、**不新增** token／視覺規格、**不重畫**已核准的資訊架構（IA）與金融資訊；**不啟動 UI 施工**；**不核准** token 值、深色預設或導覽改版。
>
> **權威邊界**：基金正式依據是既有基金線框與裁示（`docs/v2/80`、`docs/v2/81`、`PROJECT_RULES.md` 13.2／13.5 及所列 DEC）。股票 HTML 只作視覺參考；**本 PR 沒有、也未見股票 HTML 原檔**，下文凡「參考側」皆轉引 PR #1200 文件（已合併，`e730789c`；路徑 `docs/evidence/fund_newui2_vs_stock_html_visual_gap_2026_11_10.md`），一律標 **NOT VERIFIED**。
>
> **標記**：FACT＝本批讀檔或實測；INFERENCE＝推論，可被推翻；NOT VERIFIED＝本批未驗。
>
> **證據限制**：截圖與量測由離線合成資料（`tests/ui_v3/market_stubs.py`，人造數值，非市場資料）＋本機 Chromium 產生，不連 FRED／Yahoo 等任何外部來源；截圖**不入 repo**；**不是** Streamlit Cloud、WebView 或真機證據。
>
> **來源**：客戶 2026-11-10 指示經總管轉達（要點轉述，無逐字存檔，本批未見客戶對話本身），登記為 `DEC-2026-11-10-06`。本檔整合一份單組唯讀研究草稿，並由整合者自行抽查關鍵宣稱（§8：15 組成立項、5 項被推翻或收窄者）；**未經第二組獨立驗證**。

基準：撰寫時 `origin/main` 的 `3c463408`；已合併 main（`e730789c`，含 #1200）。

---

## 0. 結論與 Decision Gate（先讀這裡）

### 0.1 專案 AI 推薦（未經客戶裁示）

最小方案是 **V1＋V4**，兩者都**不改任何 UI 程式**：

1. **V1 補視覺驗收證據**：把本批已證明可重跑的離線流程正式化，產出 390／768／1280 的 Reference／Current／Delta 表（Reference 需客戶提供股票 HTML 原檔或截圖，否則 Delta 只能維持 NOT VERIFIED）。
2. **V4 補 🌍 頁本體的瀏覽器級守衛**：目前導覽有瀏覽器級測試，但頁本體（卡片／圖／間距）沒有。
3. **V2／V3（token 值、版面微調）一律等客戶先就下表 G2、G3、G6 裁示**，之前不動 `ui_v3`。

**現況判讀（FACT 為主）**：🌍 的資訊架構、區塊順序、缺值行為與頁首五格已實作且有 DOM 級守衛；視覺層（色票／圓角／間距／字級）仍是「Preview 暫用樣式」，`tokens.py` 的值為 None。這是**待客戶定案的設計議題**，不是 bug。

### 0.2 Decision Gate

| # | 要裁示的事 | 為什麼 | 專案 AI 建議 | 若不裁示的後果 |
|---|---|---|---|---|
| G1 | 是否授權 V1：重產 390／768／1280 截圖入 `docs/evidence/`，並做 Reference／Current／Delta；Reference 由客戶提供股票 HTML 原檔或截圖 | 現行導覽（頁首 S1）之後沒有 768 與 1280 的 🌍 現行截圖存證；參考側目前只有轉引文字 | 同意 V1，並提供 Reference | 無法產出可核對的 Delta；參考側差距維持 NOT VERIFIED |
| G2 | 主內容外觀：維持「淺色主內容＋深色側欄」（`DEC-2026-10-27-09`）、改深色預設，或提供 light／dark 雙版 | 影響全站 theme 與對比；參考側為 dark-only（轉引）；客戶 10-27 曾明示不要先全深色再做第二次 theme migration | 未裁示前維持現狀；若要深藍風格，先看對比計算與 light／dark 兩版對照再裁 | 維持現狀，不會有視覺改版 |
| G3 | token 值（色票／圓角／間距／字級）。`ui_v3/design/tokens.py` 命名已有、值為 None | 值未定是任何視覺改版的前置；`docs/v2/80` 第 5 節的尺度自標為提案，不是核准值 | 隨 G2 一併提案；核准前不改 `tokens.py`，不抄參考側色票 | `mkt.py`／`nav.py` 的暫用硬碼樣式持續存在 |
| G4 | 桌機導覽樣式是否改變（現為固定左側欄，已裁示） | 參考側為頂端雙層頁籤（轉引） | 維持側欄；不搬股票導覽 | 維持現狀 |
| G5 | 手機首屏「主圖至少露出多少」的驗收門檻；頁首維持非 sticky 或改黏附 | `DEC-2026-11-07-02` 條件為「結論 chip＋主圖或主數字可見」，未訂可見量；現況 390px 主圖約露 157／239px | 請客戶定一個門檻，或明示承認現況；頁首維持 S1 非 sticky | 「首屏夠不夠」無客觀判準，後續驗收會各說各話 |
| G6 | 是否要「首屏大狀態卡」「圖卡化」「Secondary 兩卡頂對齊」等版面異動 | 屬版面異動，須 UI 草稿先行（`CLAUDE.md` §-1.5.4）；首屏預算 ≤5 為 frozen 44，不得放寬 | 先出文字線框草稿再裁；不與 V1 混批 | 不施工 |
| G7 | Streamlit Cloud、WebView、真機視覺驗收的授權與時機 | 本批無法驗；`DEC-2026-11-07-02` 的適用性／獨立 QA 仍標未驗 | 另批；先完成非作者 QA | 維持「僅離線合成證據」 |
| G8 | 是否授權 V4（🌍 頁本體瀏覽器級守衛，純新增測試） | 頁本體目前沒有任何瀏覽器級視覺守衛（範圍：tests/ui_v3；全 repo 未窮舉） | 同意 V4 | 頁本體視覺回歸只能靠人工 |

**未經授權不得開始 UI 施工**：本檔、`DEC-2026-11-10-06` 與上表任何建議，皆不構成 `ui_v3`／`ui_v2`／正式入口的改動授權。

---

## 1. 🌍 視覺驗收條件表（基金正式依據）

核准狀態：已核准＝已有 DEC 或已裁示線框；候選／待裁示＝文件提案，尚無客戶裁示。可驗方式：DOM＝DOM／AppTest／CSS 斷言；截圖＝Chromium 量測與截圖；人眼＝須人看。

| 條件 | 條件內容 | 出處 | 核准狀態 | 可驗方式 |
|---|---|---|---|---|
| MV-01 | 五頁 IA 與順序 `mkt／ast／exp／ai／set`；只有 🌍 註冊；🤖 在 Phase 7 前可見不可進；不得空殼頁或假資料 | `PROJECT_RULES.md` 13.2 第 1 點（五頁順序依據）；`ui_v3/shell/registry.py` 的 `IA_PAGES`；`docs/v2/80` 7.4 僅作 🤖 Phase 7 前不可進的出處，不作順序依據；`DEC-2026-10-29-06`／`-07` | 已核准 | DOM |
| MV-02 | 區塊順序：首屏摘要（市場狀態→是否需注意→重要依據→資料新鮮度）→Primary（檢視／期間／基準日行／圖／各序列資料日／來源與限制）→Secondary（≤3，現 2）→依據卡 MKT-1~3→尚未取得／各項資料狀態 | `docs/v2/81` 3.1、3.2、5；`DEC-2026-11-03-01`、`-09` | 已核准 | DOM |
| MV-03 | 首屏 chip＋核心數字 ≤5（常態 3 chip＋2 數字） | `docs/v2/81` 3.1 Visual Budget、10.2；`DEC-2026-11-03-09`、`-11`；44 之十九其一之一第 2 條 | 已核准 | DOM（既有守衛） |
| MV-04 | 市場狀態、是否需注意各一枚 `⬜ 無法判定`；新鮮度一枚 `⬜ 門檻待裁示`；頁級不放延遲天數與日期 | `docs/v2/81` 3.1、Q1／Q5；`DEC-2026-11-03-01`、`-09` | 已核准 | DOM |
| MV-05 | Primary＝台股 vs S&P 500 歸一化；單 Y 軸、≤3 series、實線／虛線＋末點直標、缺段斷線不補不畫零、不畫 threshold／目標價線／方向箭頭；390px 標籤重疊時減 series 不縮字 | `docs/v2/81` 3.1「圖本體」 | 已核准 | DOM＋截圖（標籤重疊須人眼） |
| MV-06 | 歸一化揭露：基準日＝100、頻率日、缺值不補斷線；基準日為圖前純文字行 | `docs/v2/81` 3.1、10.2；`DEC-2026-11-03-07`、`-09` | 已核准 | DOM |
| MV-07 | 缺資料：缺一條→另一條仍畫＋缺項說明；兩條皆缺→非 ok 卡、不畫空座標軸；Missing 恆 `◇ 資料未備`；取數失敗原文不上一般畫面 | `docs/v2/81` 4.1；`PROJECT_RULES.md` 13.5 | 已核准 | DOM＋截圖 |
| MV-08 | 手機（≤768）頁首五格 S1：固定橫排、全部可見、不左右滑動、各格觸控 ≥48px、禁入項 aria-disabled、選取態非顏色唯一；≥769 維持左側欄；無整頁橫向捲動 | `DEC-2026-11-06-01`、`-07-01`、`-07-02`；`docs/v2/80` 18 | **設計 S1 已核准**；`-07-02` 自述「LEGAL／INDEPENDENT QA UNVERIFIED」 | DOM＋截圖；WebView／真機屬 Cloud／真機 |
| MV-09 | 390px 首屏「結論 chip＋主圖或主數字可見」；Primary 圖上緣在首屏（V7） | `DEC-2026-11-07-02` 保留約束；`docs/v2/81` 6 | 條件文字已核准；**「可見量」未訂** | 截圖 |
| MV-10 | 顏色只是第三重（符號＋字樣為主），只映射資料狀態、不映射投資好壞 | `docs/v2/80` 5；`docs/v2/81` 0 | 已核准 | DOM |
| MV-11 | 視覺 token 值（色票／圓角／間距／字級）。命名已有，值為 None；`docs/v2/80` 5 的尺度屬提案 | `ui_v3/design/tokens.py`；`docs/v2/80` 5、12 | **候選／待裁示** | DOM（值是否填入）＋人眼 |
| MV-12 | 外觀基準：主內容淺色＋側欄深色（視覺 theme） | `.streamlit/config.toml`；`DEC-2026-10-27-09` | 已核准 | 截圖 |
| MV-13 | 桌機固定左側欄（無收合鈕），含資料狀態與「更新資料」CTA（不可用＋一句原因）；Status Bar 純文字 | `docs/v2/80` 17.2、17.3；`DEC-2026-11-03-10`、`-11` | 已核准 | DOM＋截圖 |
| MV-14 | 觸控目標下限 48px（手機頁首各格） | `DEC-2026-11-07-02`；`ui_v3/shell/nav.py` 的 `TOUCH_MIN_PX` | 手機頁首已核准；**頁內其他控制項（radio／expander）未訂** | DOM＋截圖 |
| MV-15 | 工程資訊不進一般 UI；資料健康集中 ⚙️；UI 精簡不等於資料精簡 | `PROJECT_RULES.md` 13.5；`docs/v2/80` 16 | 已核准 | DOM（既有守衛） |
| MV-16 | 歷史藍圖（`docs/design/new_ui2_full_implementation_blueprint_2026_11_05.md`）的視覺細節 | 該檔自標歷史候選；PR #1200 文件亦同 | **候選，不得當驗收依據** | — |

FACT：`docs/v2/81` 3.1 線框中的「手機底部列」已被 `DEC-2026-11-06-01`／`-07-02` 的頁首 S1 取代；`docs/v2/80` 17.5 的底部列量測屬歷史。

---

## 2. 已實作現況對照

| 條件 | 判定 | 依據（檔案＋符號） |
|---|---|---|
| MV-01 | 已實作 | `ui_v3/shell/registry.py` 的 `IA_PAGES`（只有 `mkt` 的 `registered=True`；`ai` 在 Phase 7 前註冊會在建構時被擋）；`ui_v3/pages/chrome.py` 的 `disabled_side_html`／`disabled_top_html` |
| MV-02 | 已實作 | `ui_v3/pages/mkt.py::_render` 依序 summary→divider→Primary→Secondary→依據卡→兩個 expander；離線渲染卡片順序為 vix／term_spread_pct／MKT-1／MKT-2／MKT-3 |
| MV-03／04 | 已實作（讀碼＋渲染） | `mkt.py::summary_html`、`chip`；頁面內 `.uv3-chip` 實測 13 枚（常態），頁級口徑為 3 chip＋2 數字。頁內總數是否被「頁級 ≤5」口徑排除＝INFERENCE，既有守衛 `tests/ui_v3/test_ui_v3_degraded_first_screen_budget.py` 以頁級口徑計 |
| MV-05 | 已實作 | `ui_v3/pages/chart_svg.py::line_chart_svg`（`currentColor`、虛線、末點標籤、`_spread` 推開標籤、斷線） |
| MV-06 | 已實作 | `mkt.py::disclosure_notes`；渲染可見「基準日…＝100；頻率：日｜缺值不補、斷線」 |
| MV-07 | 已實作（讀碼＋缺台股情境渲染） | `mkt.py::status_html`、`primary_notes_html`；缺台股情境三寬度皆無橫溢，圖仍畫單序列＋說明 |
| MV-08 | 已實作（Chromium 合成 fixture） | `ui_v3/shell/nav.py::shell_css`；量測見 §3 |
| MV-09 | **部分** | 390px：chip 在首屏；主圖頂 y≈687、首屏可見約 157／239px。「可見量」未訂，故不判優劣 |
| MV-10 | 已實作 | `mkt.py::chip` 的 tone 為淡底三色；圖全用 `currentColor` |
| MV-11 | **未實作** | `ui_v3/design/tokens.py` 的 `Token.value` 預設 None；`mkt.py` 的 CSS 為暫用樣式（8px 圓角、13／14／20px 字級、`rgba(128,128,128,…)` 邊線） |
| MV-12 | 已實作 | `.streamlit/config.toml`：light base、主內容 `#f6f8fa`、側欄 `#0e1117`；渲染 appBg 與側欄色與之相符 |
| MV-13 | 已實作 | `chrome.py::render_navigation`、`render_status` |
| MV-14 | **部分** | 頁首各格 60px（≥48）；頁內 radio／expander 見 §3 |
| MV-15 | 已實作（既有守衛） | `tests/ui_v3/test_ui_v3_no_engineering_leak_guard.py`；渲染畫面無工程字串 |
| MV-16 | 無法由讀碼判斷 | 歷史候選，非驗收依據 |

---

## 3. 離線量測事實（只記錄事實，不判優劣；非真機）

**方法與重現**（整合者於 2026-11-10 重跑一次，結果與草稿一致）：

- 環境：Streamlit 1.59.2（裝於 scratchpad，非 repo 依賴）、Chromium（headless，`--no-sandbox`）、Playwright（node）、`deviceScaleFactor` 2。
- 啟動：以一支 harness 腳本（不入 repo）把 `ui_v3.adapters.market_page.load` 換成 `tests/ui_v3/market_stubs.py` 的 `view()`／`table()`，再呼叫 `ui_v3.app_preview.main()`；`streamlit run` 帶 `--server.headless true --global.developmentMode false --server.fileWatcherType none`。**不抓外部資料。**
- 量測：視窗 390×844、768×1024、1280×800；以 `getBoundingClientRect`／`getComputedStyle` 取值；情境 `normal` 與 `missing`（台股缺資料）。
- 兩次執行差異：重跑時加了 `--client.toolbarMode minimal`，Streamlit 框架的 Deploy／選單鈕（約 28px，框架 chrome）因此不在量測內，「<48px 的可互動元素」數：原 measure.json 實測 390／768 為 23、1280 為 24（normal 與 missing 同）；重跑僅一次、toolbarMode＝minimal 時為 21（1280 為 22），重跑值未經 QA 獨立驗證。這些元素多為框架元件（標題錨點連結、radio input、expander summary 等，含 Deploy／選單鈕），不全是頁面自繪元件；其餘數字相同。Cloud 是否顯示該框架鈕＝NOT VERIFIED。

| 項目 | 390×844 | 768×1024 | 1280×800 |
|---|---|---|---|
| 整頁橫向捲動 | 無（scrollWidth＝390） | 無 | 無 |
| 導覽 | 頁首五格各 71.6×60，側欄隱藏，頁首自 y≈70.4 | 五格各 147.2×60 | 側欄 300px 寬，頁首隱藏 |
| stHeader 高 | 60 | 60 | 60（自 x＝300 起） |
| 背景／文字色 | rgb(246,248,250)／rgb(31,35,40) | 同 | 同；側欄 rgb(14,17,23) |
| 主內容 padding／max-width | 16px／1100px | 同 | 同（欄寬 980） |
| h1 字級 | 27.2px／700 | 同 | 同 |
| 內文列／備註／chip／主數字字級 | 13／13／14／20px | 同 | 同 |
| 卡片 | 圓角 8px、內距 10×12、mb 8px、1px `rgba(128,128,128,.35)` 邊線、背景透明 | 同 | 同 |
| Secondary 兩卡 | 單欄 | 並排各 360 寬；利率卡 y 比 VIX 卡低 84px | 並排各 466 寬；同樣低 84px |
| 依據卡三張 | 單欄 | 並排各約 235 寬 | 並排各約 305 寬 |
| Primary 圖 寬×高 | 358×238.7 | 720×480 | 720×480 |
| 圖縮放／刻度字／末點標籤字 | 0.994／10.9／11.9px | 2.0／22／24px | 同 768 |
| 圖頂 y／首屏可見圖高 | 687／約 157px | 663／約 361px | 602／約 198px |
| expander summary 高 | 38px | 38px | 38px |
| 缺台股情境 | 無橫溢，圖仍畫 | 同 | 同 |

補量（本批新增；方法：對 `[data-testid="stRadio"] label` 取 `getBoundingClientRect`，三個寬度相同）：

- radio **選項 label 外框**高 22.4px、寬 39.6～82px；radio **標題 label** 高 24px、寬 213～278px；input 本身 13×13px。以上外框皆小於 48px。
- **實際可點擊區**（可能因父層 padding 或偽元素大於 label 外框）**本批未量**，仍為 NOT VERIFIED。
- Secondary 兩卡不齊高的成因（讀碼）：利率卡的 radio 在卡片 HTML 之前、同一欄內，把卡片往下推；VIX 欄沒有 radio。

FACT 補充：圖表 `.uv3-chart` 的 `max-width` 為 720px、viewBox 360×240，桌機圖寬 720 小於欄寬 948（右側留白）。

---

## 4. 現有視覺證據的可重用性與過期清單

| 證據 | 涵蓋 | 日期 | 對應現況？ |
|---|---|---|---|
| `docs/evidence/bl0536_mkt_preview_2026-11-03/`（m_*.png 手機、d_*.png 桌機） | 🌍 頁各情境 | 2026-11-03 | **導覽部分過期**：拍攝時為底部列；Shell 之後改為頁首 S1（2026-11-07）。頁本體 `mkt.py` 與 adapter 的最後修改都在 11-03，頁本體大致仍對應（INFERENCE） |
| `docs/evidence/bl0536_shell_h5_2026-11-03/` | 390／768／769／1280 量測 | 2026-11-03 | 底部列量測**過期**，僅供歷史 |
| `docs/evidence/bl0544_s1_chromium_fixture_2026_11_07/` | 頁首 S1 的 374／375／390／768／769／1280 與 190% 字模擬 | 2026-11-07 | **對應現行導覽**；本批重量的 390／768 頁首五格尺寸與其一致；非 production、非真機 |
| `tests/ui_v3/test_ui_v3_top_nav_browser.py`（slow lane） | 374／375／390／768 與 769／1280、190% 字（374／390） | 現行 | 現行；只測 Shell，不測頁本體卡片／圖 |
| `tests/ui_v3/` 的首屏預算、導覽、AppTest、工程字串外漏守衛 | DOM 級 | 現行 | 現行；非視覺 |
| `tests/visual_fidelity/`（VF safety net） | 只覆蓋 `ui_v2` 的 `mkt` 等頁 | — | **不涵蓋 `ui_v3` 🌍**（該目錄內無 `ui_v3` 引用） |

結論：**沒有 768px 的 🌍 現行截圖存證**；**1280 的 🌍 現行圖只有 11-03 版**。本批產生的截圖可補這兩個缺口，但不入 repo（若 G1 獲准才歸檔）。

---

## 5. 參考側差距分類（轉引 PR #1200 文件；參考側 NOT VERIFIED）

分類：**已實作**、**需要改善（visual-only，不改金融內容）**、**需要客戶裁示**。

| 維度 | 參考側（轉引） | 基金 Current（FACT） | 分類 | 備註／所需 Gate |
|---|---|---|---|---|
| 深海軍藍 `#0b1020`、漸層卡、淺字、dark-only | 見左 | 淺色主內容＋深色側欄；token 值 None | **需要客戶裁示** | G2、G3；`DEC-2026-10-27-09` 為客戶 theme 裁示，不得直接抄色票 |
| 卡片 16px 圓角、層級卡、12-column、手機單欄 | 見左 | 8px 圓角、背景透明、Secondary 兩欄／依據卡三欄 | **需要改善**（圓角／間距數值屬 token）；12-column 屬版面異動 | 數值：G3；版面：G6 草稿先行 |
| 頂端雙層橫向五頁籤，手機可橫滑 | 見左 | 桌機左側欄（已裁示）；手機頁首五格不橫滑（S1 已核准） | **已實作**（相異處為刻意） | 不搬股票橫滑做法；改動走 G4／G5 |
| 首屏大狀態卡＋主要風險＋下一步 CTA | 見左 | 四列摘要（`DEC-2026-11-03-09`），無新 CTA | 內容已實作；「大狀態卡」視覺化＝**需要客戶裁示** | G6；首屏預算 ≤5 為 frozen 44 |
| Primary 大圖卡、日期、空資料不畫假線 | 見左 | 已有日期行與缺值斷線；圖外無卡片框 | 部分；「圖卡化」屬 visual-only **需要改善** | 不可改共同基準日或歸一化；動版面則 G6 |
| 狀態／缺值 pill 字詞 | 見左 | 取 `shared/ui_semantics/rules.py` | 已實作 | 不逐字移植股票字詞；改字樣需客戶定字 |
| 帳號／Active Sheet 槽位（DEMO） | 見左 | Preview 無登入入口 | 不屬本批 | 不得複製股票假 account；屬 OAuth／Active Sheet Gate |

---

## 6. 響應式驗收條件（390／768／1280）

自動守衛現況：導覽有瀏覽器級測試（slow lane）；首屏預算、字樣、AppTest 是 DOM 級；VF safety net 不含 `ui_v3`。**頁本體目前沒有任何瀏覽器級視覺守衛**（範圍：tests/ui_v3；全 repo 未窮舉）。

| 斷點 | 必須成立 | 可接受差異 | 失敗條件 | 驗證方式 |
|---|---|---|---|---|
| **390** | 無整頁橫向捲動；頁首五格全可見、各 ≥48×48、等寬、不橫滑、非 sticky；首屏四列摘要完整；結論 chip 在首屏；頁級 chip＋核心數字 ≤5；缺資料不畫假線；工程字串不外漏 | 主圖在首屏僅露上半（現約 157／239px）——在 G5 裁示前屬已知現況；框架 chrome 不計 | 橫溢；任一格 <48；五格被截或裁字；Missing 畫成 0；工程字串外漏 | 頁首：已有（slow）；其餘：DOM 級已有，**頁本體瀏覽器級：無**，只能截圖＋人眼 |
| **768**（手機上限） | 同 390 頁首規則；Secondary 兩欄不重疊；依據卡三欄文字不被截 | 圖放大至 720px 與 Secondary 兩卡不齊高屬現況 | 同 390＋卡片文字被截 | 頁首：已有；其餘：截圖（本批已重產） |
| **769**（邊界） | 側欄顯示、頁首隱藏、無橫溢 | — | 兩種導覽同時出現或都不出現 | 已有（slow） |
| **1280** | 側欄 300px 固定可見、無收合鈕；主內容無橫溢；主圖在首屏有露出；Secondary 並排 | 圖寬小於欄寬（右留白）；首屏圖露出約 198／480px | 側欄裁切主內容；主圖完全在首屏外 | 側欄：已有；其餘：截圖＋人眼 |
| 全斷點 | 缺資料／失敗／未設定情境不橫溢（本批只量 `missing`） | — | — | `failed`／`nokey` 等其他情境本批未重量 |

- **只能人工或截圖**：視覺密度、對比、首屏圖露出是否可接受、卡片不齊高是否可接受。
- **需 Cloud／真機（本批 NOT VERIFIED）**：Cloud 實際字型與主題、WebView、iOS／Android safe-area 與動態網址列、真實 OS 字級放大、螢幕閱讀器、真資料畫面、dark 模式對比（`config.toml` 為 light base，本批未測 dark）、radio 實際可點區。

---

## 7. 方案 V1～V4 比較

| 方案 | 做什麼 | 正確性／風險 | 速度／Token | 維護成本 | 回滾 | 所需 Gate |
|---|---|---|---|---|---|---|
| **V1（推薦）證據歸檔** | 重產 390／768／1280 截圖入 `docs/evidence/` 新資料夾；Reference／Current／Delta 表；人眼 checklist；不改程式 | 最低；Reference 缺原檔則 Delta 為 NOT VERIFIED | 最快／最省 | 低（證據會過期，需標日期） | 刪證據檔 | G1（docs-only） |
| V2 token 值提案 | 先做對比計算、light／dark 兩版對照與 token 值提案文件；**客戶核准後**才填 `tokens.py`、改 `mkt.py`／`nav.py` 引用 | 中：動 theme 影響全頁，與 `DEC-2026-10-27-09` 並存需裁示 | 中／中 | 中（token 值需同步守衛） | 還原 token 值 | G2、G3（視覺 Gate）；非作者 QA；不得放寬 44 首屏預算 |
| V3 `mkt.py` visual-only 微調 | 例：圓角／內距／邊框、Secondary 兩卡頂對齊、圖卡化外框 | 中：頂對齊與圖卡化屬版面異動 | 中／中 | 中 | `git revert` | 版面異動：G6 草稿先行；數值：G3；非作者 QA；不碰 services／`ui_v2`／44 |
| V4 頁本體瀏覽器級守衛 | 仿 `test_ui_v3_top_nav_browser.py` 為 🌍 頁本體加 390／768／1280 的無橫溢、圖上緣在首屏、字級下限等斷言（slow lane） | 低；不改視覺 | 中／中 | 中（slow lane 需瀏覽器） | 刪測試檔 | G8；非作者 QA；先反向破壞 CSS 驗證會紅 |

推薦：**V1 先行（可與 V4 並行）**；V2→V3 待客戶先裁 G2／G3／G6。以上為專案 AI 讀法，**未經客戶裁示**。

---

## 8. 抽查結果與推翻／收窄

整合者對草稿自行抽查關鍵宣稱，**成立**項（15 組）：

1. 只有 🌍 在 `registry.py` 為 `registered=True`，`ai` 被建構期檢查擋住。
2. `tokens.py` 的 `value` 預設 None。
3. `tests/visual_fidelity/` 內無 `ui_v3` 引用（該目錄只覆蓋 `ui_v2`）。
4. 11-03 H5 量測為底部列時代（`docs/v2/80` 17.5 自述）。
5. 頁首五格尺寸：重跑 390→71.6×60、768→147.2×60，與 `measure.json` 一致。
6. 三寬度、兩情境皆無橫向溢出（重跑一致）。
7. 390 主圖頂 y≈687、首屏可見約 156.6／238.7px（重跑一致）。
8. 768／1280 Secondary 兩卡差 84px（重跑一致；成因讀碼確認）。
9. expander summary 38px；選項 label 外框高 22.4px（本批補量）。
10. `nav.py` 的 `TOUCH_MIN_PX`＝48；`mkt.py` 的卡片圓角 8px、`.block-container` max-width 1100px。
11. `.streamlit/config.toml` 色票與 `DEC-2026-10-27-09` 描述相符。
12. `docs/v2/81` 3.1 Visual Budget＝3 chip＋2 數字；`PROJECT_RULES.md` 13.2 第 1 點五頁順序。
13. 所引 DEC（`2026-10-27-09`、`11-03-01／-07／-09／-10／-11`、`11-06-01`、`11-07-01／-02`、`10-29-06／-07`）在 `docs/DECISIONS.md` 皆存在。
14. 導覽瀏覽器測試涵蓋的寬度（374／375／390／768、769／1280、190% 字於 374／390）與草稿所述一致。
15. PR #1200 文件撰寫時尚在分支上，現已合併（`e730789c`），main 上路徑 `docs/evidence/fund_newui2_vs_stock_html_visual_gap_2026_11_10.md`；其差距表內容與草稿 §4 的轉引相符（合併前已核對，合併後未再逐字比對）。

**被推翻或收窄**：

- **「非 sticky 為已核准」收窄**：`DEC-2026-11-07-02` 本文未寫 sticky；「客戶定案非 sticky」只出現在 S1 fixture 的 README。故本檔寫「頁首在文件流內（非 sticky）」為現況與證據檔所述，**不引為 DEC 條文**；G5 將它列為可確認項。
- **MV-09 收窄**：草稿把「Primary 圖上緣在首屏」寫成核准條件。`DEC-2026-11-07-02` 的字句是「結論 chip＋主圖**或主數字**可見」；圖上緣在首屏（V7）出自 `docs/v2/81` 6 的守衛計畫。故 157／239px **不構成對 DEC 條件的違反**；11-03 的 H5 量測當時為約 158px 並被判「未發現實質衝突」，現況數字與之相近。
- **adapter 日期推翻**：草稿稱 adapter 最後修改為 11-05（某 commit）；本批查 `ui_v3/adapters/market_page.py` 最後修改在 2026-11-03，該說法未能重現，已刪除。
- **radio 觸控區（原 NOT VERIFIED）部分補量**：label 外框已量（<48）；實際可點區仍未量。
- **框架 chrome 計數**：草稿的「<48px 元素 23 個」含 Deploy／選單鈕；toolbarMode＝minimal 重跑時為 21（單次重跑）。已在 §3 逐寬度註明。

---

## 9. 未涵蓋與限制

- 單組草稿＋整合者抽查，**未經第二組獨立驗證**；§1「核准狀態」是專案 AI 讀 DEC／規格的判斷，不是客戶確認。
- 渲染為合成 fixture＋本機 Chromium＋Streamlit 1.59.2：非 production、非 Cloud、非 WebView、非真機、非真資料。
- 未測 dark 模式、374／375／190% 字體（沿用既有 S1 證據，未重驗）、`failed`／`nokey` 等其他情境；未逐條讀 44／57／CONSTITUTION 全文（僅經 `docs/v2/80` 與 DEC 轉述）；未讀歷史藍圖全文。
- 股票 HTML：本批未見原檔；§5 參考側欄位全部轉引 PR #1200 文件。
- 「頁內 chip 13 枚 vs 頁級 ≤5」的口徑差異屬 INFERENCE，需客戶／QA 裁示口徑。
- 本檔不新增任何 token、門檻、字樣或資料來源，不構成施工授權。
