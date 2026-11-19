單組產出，未經獨立複驗；截圖在同目錄、未入 repo

# 🌍 市場頁 UI 落差分析（唯讀；main eb08c5fc；2026-11-19）

> **檔頭註記（落檔時補）**：單組作者；**截圖未入 repo**（下文所列截圖與腳本位於產出當時的暫存目錄，repo 內不存在）；以下為報告**全文原樣**。落差分析為 FACT／推論／建議的混合，**不是裁示、不是授權施工**；是否採用任何改善項須由使用者核准（見 `docs/evidence/` 內同批 DEC-2026-11-19-11 的未核准欄）。

標記：FACT＝本組實測或讀檔；【I】＝推論，可推翻；【R】＝建議，不是裁示。
未改 repo 任何檔，git status 全程乾淨。未連外部資料源，未碰 secrets 與 Google Sheet。

## 0. 輸出檔案與限制

目錄：/tmp/claude-0/-home-user-my-Fund-dashboard/cb254a0d-a287-54c7-8b6d-e7845fbbacbb/scratchpad/mkt_gap/

截圖（Chromium 1243、Streamlit 1.59.2、deviceScaleFactor 1、zh-TW）：
- 首屏：mkt_normal_390_fold.png（390x844）、mkt_normal_768_fold.png（768x1024）、mkt_normal_1280_fold.png（1280x800）。
- 全頁（viewport 高度設成 stMain 的 scrollHeight 再截）：mkt_normal_{390,768,1280}_full.png。
- 摺疊區全展開：mkt_normal_390_expanded_full.png、mkt_normal_1280_expanded_full.png。
- 降級情境：mkt_tw_missing_{390,768,1280}_{fold,full}.png、mkt_us_failed_{390,768,1280}_{fold,full}.png。
- 文字與腳本：mkt_normal_*_text.txt、mkt_normal_*_expanded_text.txt、app_stub.py、shoot.py、shoot2.py。

起服務的做法：
- 沿用 tests/ui_v3/test_ui_v3_market_page_browser.py 的 _APP：用 market_stubs 合成 fixture 替換 adapter.load，再呼叫 ui_v3.app_preview.main()。
- 用 scratchpad 既有的 venv311（內有 streamlit 與 playwright）。
- 瀏覽器用 /opt/pw-browsers/chromium-1243/chrome-linux64/chrome（playwright 預設的 chromium-1255 路徑不存在，須明指）。

NOT VERIFIED：
1. 資料是人造 fixture，圖形是正弦波，不代表真實行情。這不是 Cloud、WebView 或真機畫面。
2. 使用者的參考圖與「台股 AI 戰情室 index(1).html」我都拿不到。repo 只有 docs/evidence/fund_newui2_vs_stock_html_visual_gap_2026_11_10.md 的轉述，該檔自己也標 NOT VERIFIED。所以下列落差是對照 repo 內已核准設計與一般金融儀表板慣例，不是對照使用者的圖。
3. repo 內沒有市場頁專屬的 HTML prototype，也沒有設計稿 png/jpg/svg。
   - docs/v2/prototype/ 只有 today、hld、alo、exp、set、set_oauth 六份（舊樹頁）。
   - docs/evidence/bl0536_* 的 png 是舊實作截圖，不是設計稿。
   - 市場頁已核准的設計來源只有文字線框：docs/v2/81、72、79 §9.1、80 §5/§7.1/§16–18。
4. 本機 run 的頂欄有 Deploy ⋮。Cloud 是否一樣，未驗。

## 1. 現況量測（FACT）

390：
- 頂欄 header 60px（y0–60）。
- 頁首五格 nav y70–131。
- h1 在 y187。
- 摘要卡 y226–425，高 199px。
- Primary 圖卡 y442 起，高 612。
- 檢視、期間兩組原生單選各 68px，共 136px。
- 主圖 y684，高 237。視窗 844，首屏只露出主圖約 160px（總 237px）。這與 G3 證據的 159.8 一致。
- Secondary：VIX 卡 y1070（高 192），利率卡 y1278（高 250）。
- 頁高 2313；摺疊區全展開為 3075。

768：Secondary 兩卡並排，MKT-1/2/3 三卡並排；頁高 2030。

1280：
- 側欄 300px。
- 主圖 720x480（核准的最大寬），卡寬約 948，圖右側留白約 230px。
- Secondary 兩卡高 192 與 250，不強制等高（G6 已核准）。
- 頁高 1947。

## 2. 落差清單

總結：「不符預期」來自三層。
- (A) 已核准設計本來就長這樣。
- (B) 純視覺可改，但需新授權或 token 核准。
- (C) 原始藍圖要求的內容是語意或資料，已被後續裁示 supersede 或仍卡 Gate，不是視覺問題。

### 2.A 對照原始藍圖（docs/evidence/decisions/2026-10-27_vnext_visual_blueprint.md）

藍圖 🌍 要求以下項目：
- 一句話市場結論（如「中性偏多」）。
- 5 級風險儀表。
- 四張摘要卡：台股趨勢、國際趨勢、利率環境、市場風險，含偏多/中性/偏空與 EPS 方向。
- 台股加權趨勢（含成交量）。
- EPS×PE 多情境圖。
- 國際指數：S&P、NASDAQ、MSCI World、MSCI EM。
- 右側 AI 總結區。

現況畫面一項都沒有，改為：
- ⬜ 無法判定、「暫無完整市場綜合判定」。
- 台股 vs S&P 歸一化比較圖。
- VIX 卡、利率卡、MKT-1~3。
- 「尚未取得（7 項）」：台股成交量、市場統計、NASDAQ、MSCI World、MSCI EM、EPS×PE 情境、implied trailing 盈餘。

FACT 原因：
- docs/design/vnext_visual_blueprint.md §8.2 的 MK-1/3/4/8 把這些判為 G-DEC／G-FORM／G-DATA／G-DIR。理由包括：禁 composite 單一總分、偏多偏空規則未核准、EPS×PE 公式與資料來源未核准、NASDAQ/MSCI 無來源。
- DEC-2026-10-30-01（D1–D7）已取代藍圖的 🌍 首屏密度。
- DEC-2026-11-03-01/-09 裁示了現行首屏。

結論：這一層全部是語意或凍結契約，不得以「視覺修正」名義動。

### 2.B 對照已核准 🌍 設計，逐項

| # | 項目 | 現況（FACT） | 與核准設計 | 類別 |
|---|---|---|---|---|
| G1 | 手機首屏主圖露出量 | 390 只露 ~160/237px。主圖在 nav、標題、摘要卡與兩組單選（136px）之後（mkt_normal_390_fold.png） | 81 MV-09 只要求「結論 chip＋主圖或主數字可見」。可見量門檻客戶未訂（視覺驗收計畫 G5）。V4 守衛鎖基線 156.6/181.4/198.4，只能升不能降 | 純視覺可改（CSS 間距、標籤內嵌）。單選改排版屬版面異動，G6 要求草稿先行。門檻需客戶定 |
| G2 | Streamlit 頂欄 60px（Deploy、⋮）在 nav 之上 | 390、768 皆有（本機）。theme.py 只把 stHeader 塗成頁底色 | 設計未提及 | ui_v3 內 CSS 壓縮可多給 ~60px 首屏。Cloud 是否有此列未驗。.streamlit/config.toml 是全 repo 共用，G3 批刻意不動 |
| G3 | 圖表單色：兩線皆 currentColor，只靠實線/虛線＋末點標籤區分 | chart_svg.py 全用 currentColor。test_ui_v3_market_chart_svg.py:38 鎖「不指定色碼」。tokens.py 的 chart.* 為 UNVALUED_BY_DESIGN | 44 之十八其三：顏色不得是唯一辨識，可當第三重。G3 核准只含色票 B＋尺寸 A，沒有圖表線色 | 純視覺，但需使用者核准 chart token 值並改測試。【I】一般金融儀表板每序列用不同色，這是觀感差距最大的一項 |
| G4 | 桌機主圖固定 720 寬，卡內右側留白 ~230px（mkt_normal_1280_full.png） | 圖左貼卡內，右側空 | G3 裁示「圖最大寬 720，不得為填滿欄寬而放大」。browser 守衛斷言 ≤720.5 | 置中屬視覺。放大主圖是偏離核准限制，需使用者核准 |
| G5 | Secondary 卡內容空：一個小數字加 160x40 迷你圖（SPARK_WIDTH/HEIGHT），1280 時卡寬 ~460、空白過半 | 無漲跌、無 band（UI-4 A 禁） | 72/81：迷你圖固定近 1Y、無軸；D6 緊湊列 | 迷你圖放大或填滿卡寬屬純視覺。加漲跌或 band 是語意，不得 |
| G6 | 摘要卡無層級：四列同字級，三枚同樣灰色 ⬜ chip（mkt_normal_390_fold.png） | 內容本身全是「無法判定/門檻待裁示」，沒有可強調的內容 | 首屏預算 ≤5；市場狀態與是否需注意各一枚 chip（DEC-2026-11-03-09） | 可純視覺調層級。「首屏大狀態卡」被視覺驗收計畫 G6 列為版面異動，須草稿先行。不得增加 chip 或數字（44） |
| G7 | 虛線底線遍布標題、欄位名與 footer（「字樣標有虛線底線者為暫時字樣，待客戶定字」），三個寬度皆見 | 【I】這是使用者第一印象之一 | 這是 PENDING wording 的強制標記（preview_wording.py 與 test_ui_v3_preview_wording_guard.py）。DEC-2026-11-03-07 只核准部分字樣 | 不是 CSS 問題。移除須客戶逐項定字並寫入 rules.py::APPROVED_WORDING，屬字樣核准，不得純視覺處理 |
| G8 | 檢視/期間/利率子序列是原生圓點 radio，390 上占 2x68px | — | 81 線框為按鈕列 [3M][6M][1Y●][3Y] | 改 segmented/pill 屬純 CSS，但要打 Streamlit 內部 data-testid，會碰 browser 守衛的 radio 斷言。【I】換 widget 型別會動 AppTest key 契約，風險較高 |
| G9 | 「各項資料狀態」展開後是純文字列（台股：取得 ｜ 來源 Yahoo Finance (^TWII) ｜ 資料日 2026-11-02），390 折行擠（mkt_normal_390_expanded_full.png） | 5 列，無表格結構、無 chip | 81 §3.3 層 2 | 純視覺（欄位對齊、chip 化），內容語意不變 |
| G10 | type.caption：80 建議 12，核准值 13px（tokens.py 已落值） | DEC-2026-11-11-03 G6：「12→13px 併下一個已授權 UI 批」 | — | 已核准待併批。本組未查證實際 CSS 是否已全面用 13px |
| G11 | 手機頁首五格 | 五格全可見、選取態有粗體與底線與灰底、不橫滑 | 完全對應 DEC-2026-11-07-02（S1） | 無落差。是否符合使用者參考圖未知 |
| G12 | 桌機深色側欄＋淺色主內容 | mkt_normal_1280_fold.png | DEC-2026-10-27-09 | 無落差 |
| G13 | Secondary 兩卡高度不一（192 vs 250） | — | G6 裁示「頂對齊、不強制等高」 | 已核准。要等高是偏離，需使用者核准 |

降級情境（FACT）：mkt_us_failed_* 與 mkt_tw_missing_* 的畫面符合 81 §4.1 S2/S6，無視覺缺陷。

### 2.D 不得動（凍結或已核准契約，任何視覺批都不得碰）

- 44（frozen）：
  - 首屏 chip＋核心數字 ≤5；頁級不放延遲天數與日期。
  - Primary 只一張，Secondary 不複製 Primary（D1）。
  - 「國際｜S&P 500」卡已移除。
  - VIX 在 Primary 為 VIX 檢視時讓位。
- 圖表規則：
  - 單 Y 軸（禁 dual axis）、≤3 series。
  - 缺值斷線，不補、不畫零。
  - 不畫 threshold、band、目標價、方向箭頭。
  - 不另畫 100 基準線。
  - 非顏色辨識。
- shared/ui_semantics/rules.py（APPROVED_WORDING、TONES、STATUS_TONES）與 DEC-2026-11-03-09（首屏 C：兩獨立欄位各一枚 chip，基準日為圖旁純文字行）。
- 方向性詞彙（偏多、偏空、風險儀表）、EPS×PE、NASDAQ/MSCI 資料、AI 區，另有 Gate。
- services/、repositories/、shared/（含 registry）、.streamlit/config.toml 不屬視覺批範圍。

## 3. 市場頁底部「完整資料來源/狀態列表」與統一管理設計

### 現況（FACT）

- 🌍 底部有兩個摺疊區：
  - ▸ 尚未取得（7 項）（缺項名單，D4＝β）。
  - ▸ 各項資料狀態（ui_v3/pages/mkt.py 的 st.expander(W.text("status_group_title"))）。它列 model.statuses 五條：台股、S&P 500、VIX、美10Y、美2Y 的狀態、來源、資料日。
- 另有 Primary 圖卡內的 ▸ 來源與限制，以及側欄「資料狀態 5／5 項已取得」。
- 資料來源：ui_v3/adapters/market_page.py::load 呼叫 L2 services/v2_tables/market_view 與 market_indicator。
- 本頁沒有直接讀 Google Sheet 的程式。market_indicator 的 Sheet 契約屬 docs/v2/50 與 repositories/settings_sheet_repository.py，Preview 路徑未接。

### 設計出處（FACT，已讀）

- docs/v2/81 §3.1、§3.3、§3.2：🌍 保留 ▸ 尚未取得 與 ▸ 各項資料狀態（MV-02，已裁示）。
  - 現況與 81 一致。
  - 81 線框另列 ▸ 次要圖：來源與限制，本組沒在現行畫面看到。【I】未驗是否為落差。
- docs/v2/80 §16.2（DEC-2026-11-03-08）：「完整資料診斷不再散落在 🌍/💼/🔍 主頁；主頁只留與判讀直接相關的 freshness/source 摘要。完整診斷集中於 ⚙️ 設定→資料健康度。」
  - §17.4：計數分母＝🌍 頁五條序列。字樣不得暗示全系統健康，全量明細由未來 ⚙️ 承接。
- docs/v2/83（DEC-2026-11-09-05，候選設計，不是 Schema 或施工授權）：
  - 資訊分工：🌍 呈現必要市場事實與限制，⚙️ 持有詳細來源健康與診斷。
  - Google Sheet 只是狀態 registry、觀測紀錄與使用者可見管理表，不是資料來源。
  - 首選方案 B：獨立國際市場資料監控 Sheet。不塞進 SETTINGS_SHEET_ID 的四張表（user_setting_log、market_indicator、fetch_log、fetch_log_open）。
  - 指標 ID、來源語意與 Gate 留在 GitHub 版本化契約，Sheet 不得人工改 Gate。
- docs/v2/79 §9.5：⚙️ 擁有 SET-1 新鮮度、SET-2 來源健康、SET-8 各頁資料狀態總表。⚙️ 目前未掛載，顯示「開發中」。

### 兩個位置要分清

1. UI 呈現位置：🌍 底部那一小段（五條序列狀態＋缺項）是 81 已核准的頁內摘要。完整、跨頁、跨來源健康診斷的「家」依 80 §16.2 與 83 是 ⚙️，尚未建置。
2. 資料 metadata 與 Sheet 管理位置：依 83 是候選的獨立監控 Sheet（未建立、未核准 Schema）。既有 SETTINGS_SHEET_ID 四表不得擴充。market_indicator、fetch_log 是既有契約，不是新清單。

### 是否一致【I】

- 現況與 81 一致。
- 與 80 §16.2 有待釐清的張力：「主頁只留 freshness/source 摘要」是否包含 ▸ 各項資料狀態 的逐序列來源列？文件沒寫要移走它，也沒有任何 DEC 裁示移除。
- BL-0540（待裁示）登記的是「⚙️ 承接 44 的進階診斷與頁內資料狀態塊，是否需 amendment」。
- 【R】⚙️ 建好且使用者裁示前不要移除 🌍 底部列表，只做純視覺整理（G9）。不提議新增或改寫任何 Google Sheet；83 維持候選。

## 4. 最小可見改善清單（【R】，依使用者可見價值排序）

### 授權前提

現有授權不涵蓋後續 🌍 樣式施工：
- DEC-2026-11-11-01 對 ui_v3 的授權僅限 G3/G6，且已完成（#1207）。
- DEC-2026-11-11-03 明寫不授權任何 UI/Runtime 施工。
- 視覺驗收計畫 G6：版面異動須 UI 草稿先行（CLAUDE.md §-1.5.4）。

所以下列每一項都需使用者新授權。使用者這次「UI 不符預期」的指示是否構成授權，請總管確認。

關於 Gate-M：
- DEC-2026-11-19-01 的 Gate-M 管的是 💼/🔍/⚙️ 的 FAKE 頁掛載。🌍 已掛載，視覺改動不適用 Gate-M。
- 但仍須 Visual Gate 或 token 核准，加非作者 QA。
- 這是我的讀法，非裁示。

| 優先 | 項目 | 檔案範圍 | 碰凍結/rules.py/registry？ | 需配合的守衛 | 授權需求 | 驗收 390/1280 |
|---|---|---|---|---|---|---|
| 1 | 首屏壓縮：縮頂欄占位（G2）＋單選標籤內嵌或縮距（G1） | ui_v3/design/theme.py、ui_v3/pages/mkt.py CSS | 否。動 config.toml 則碰全 repo 共用設定，不建議 | test_ui_v3_market_page_browser.py（露出量基線、單選仍在卡內可操作）、test_ui_v3_degraded_first_screen_budget.py、test_ui_v3_token_contrast.py | 標籤內嵌屬版面異動，草稿先行加核准。移除頂欄占位屬 CSS，但需先有 Cloud 截圖確認該列存在 | 390 主圖露出 ≥160px（目標值待使用者訂）；1280 無橫溢 |
| 2 | 圖表線色：兩線不同色，保留虛線與末點標籤 | tokens.py（chart.* 值）、chart_svg.py、theme.py | 否。但 chart.* 現為 UNVALUED_BY_DESIGN，需客戶核准色值 | test_ui_v3_design_tokens.py（CSS 色碼須來自 token 表）、test_ui_v3_market_chart_svg.py:38（現鎖 currentColor，需同步改）、test_ui_v3_token_contrast.py | 需使用者核准 chart token 值（G3 類） | 兩線色相可分，色盲模擬下仍靠虛線與標籤可辨 |
| 3 | 迷你圖與 Secondary 卡寬度對齊、主圖置中（G4/G5） | chart_svg.py（SPARK_WIDTH）、mkt.py CSS | 否。放大主圖需核准（720 是 G3 核准限制） | test_ui_v3_market_chart_svg.py、browser 守衛（圖寬 ≤720.5、比例 360:240） | 新樣式批需授權；放大主圖需核准 | 1280 卡內無大片單邊留白 |
| 4 | 單選樣式（segmented/pill），只做 CSS | theme.py、mkt.py | 否 | browser 守衛；AppTest key uv3_mkt_period/_view/_rates 不變 | 需授權。依賴 Streamlit 內部 data-testid，升版會壞（80 §17.1 已知限制） | 390 觸控 ≥48px 不退步 |
| 5 | 「各項資料狀態」列內結構整理（對齊、狀態 chip 化、手機不擠） | mkt.py::status_row_html 一帶 | 否（狀態詞取規則表） | test_ui_v3_wording_fidelity.py、test_ui_v3_no_engineering_leak_guard.py | 需授權，不涉資料 | 390 展開後每列不超過兩行 |
| 6 | 摘要卡層級（字級、分隔、左側色條），不增減 chip 與數字 | mkt.py CSS | 否。增加 chip 或「首屏大狀態卡」屬版面異動，須草稿 | test_ui_v3_first_screen_c_and_wording_unify.py、degraded budget | 草稿先行加核准 | 首屏 chip＋數字仍 =5 |
| 7 | caption 12→13px（已核准待併批） | tokens/CSS | 否 | token 守衛 | DEC-2026-11-11-03 G6 已核准方向，需下一個已授權 UI 批 | 無新溢出 |
| ✗ | 移除虛線底線（G7）、風險儀表、偏多偏空、EPS×PE、NASDAQ/MSCI、AI 區 | — | 是（字樣核准、語意、資料、Gate） | — | 不屬視覺批，各有 Gate | — |

另外，以下需另請使用者核准或不要動：
- §2.D 全部。
- 移除 🌍 底部狀態列表（BL-0540 待裁示）。
- config.toml。
- 任何 Google Sheet。

## 5. 需使用者提供或確認

1. 金融儀表板參考圖，以及「台股 AI 戰情室 index(1).html」原檔或截圖（repo 沒有）。沒有它，「像不像參考圖」只能 NOT VERIFIED。
2. 目前不符預期的實際畫面截圖，最好是 Cloud 或手機瀏覽器，附裝置與寬度。用來確認 Deploy 頂欄、虛線底線、單色圖表在使用者畫面長怎樣。
3. 確認問題：
   - (a) 要的是「接近參考圖的視覺風格（色彩、卡片層次、圖表配色）」，還是「增加藍圖內容（風險儀表、偏多偏空、EPS×PE、國際指數）」？後者是語意或資料 Gate，不是視覺批。
   - (b) 同意圖表兩線不同色（保留虛線與末點標籤）嗎？請核准 chart.* 色值或提供色票。
   - (c) 手機首屏主圖至少露出多少 px 才可接受（現約 160/237）？
   - (d) 暫定字樣（虛線底線）由使用者逐項定字，還是沿用現況直到定字？
   - (e) 主圖 720px 上限可否放寬，或同意維持並僅置中？
   - (f) 底部資料來源列表：維持在 🌍（現況＝81 已核准），還是等 ⚙️ 資料健康度建好再移？這與任何 Sheet 設計無關。
4. 授權範圍：是否授權新一批「純視覺、不改金融語意」的 ui_v3 🌍 樣式施工，授權第 4 節 1~7 項中的哪幾項。

## 6. 未驗與單組聲明

單組產出，未經獨立複驗（CLAUDE.md §-2 規則 6）。FACT 僅限本組實測截圖與讀檔。

未驗：
- Cloud 頂欄是否同樣有 Deploy。
- chart.* 是否只需 token 核准與改 test_ui_v3_market_chart_svg.py 即可改，除此之外是否還有其他守衛鎖 currentColor。
- 81 線框的 ▸ 次要圖：來源與限制 現況是否缺。
- G10 的 caption 13px 是否已全面落到實際 CSS。

Gate 需求（是否需 Gate-M、是否構成授權）是我的讀法，非裁示。
