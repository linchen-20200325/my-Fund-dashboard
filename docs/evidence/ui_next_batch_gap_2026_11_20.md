單組產出，未經獨立複驗；非授權、非裁示；登記不構成動工授權。唯讀分析，未改任何程式、測試或其他文件。

# New UI2 下一批 UI：規格 vs 現況差額分析（基準 main 429e92c7；2026-11-20）

標記：【F】本組讀檔／grep 所見；【I】推論；【R】建議，可推翻。分類 A＝已核准且現有 Gate 內可直接施工（Preview-only 純視覺，不碰資料／規則／來源）；B＝需最小 UI Decision Gate（版面／元件增刪／分頁動線，先出線框草稿，CLAUDE.md §-1.5.4）；C＝需正式 Decision Gate；D＝受阻（等外部輸入／OneBrain 授權）。分類是本組讀法。
**方向來源**：「手機上方五格、桌機深色側欄、五頁精簡圖表優先、診斷統一到 ⚙️、每頁預留 OneBrain 位置、未授權前不顯示假 AI 結論」為 ChatGPT 總管轉述〔待核〕，repo 無逐字存檔（比照 DEC-2026-11-19-11 的來源性質）。本分析不把它當成 DEC。

## 0. 結論
1. 轉述方向的前兩項（手機頁首五格、桌機深色側欄）**現況已落地、無差額**（見表列 1、2）；仍欠 Cloud／真機驗收（D）。
2. 真正的差額集中在：⚙️ 資料健康度頁尚無 wireframe；OneBrain 位置在任何線框（80 §7、81）都沒有；🌍 圖表系列色；💼🔍⚙️ 掛載。
3. 推薦下一批（§3）：R1 [A] 🌍 小幅純視覺；R2 [B] 🌍 圖表系列色（色票草稿）；R3 [B] 🌍 OneBrain 預留位的線框草稿（docs-only，不渲染）。

## 1. 規格 vs 現況差額表
| # | 項目 | 規格出處 | 現況（檔:符號） | 差額 | 類 |
|---|---|---|---|---|---|
| 1 | 手機頁首五格（固定橫排、不橫滑、≥48px） | 80 §18；DEC-2026-11-07-02；PROJECT_RULES §0.4 CURRENT | ui_v3/shell/nav.py::shell_css（≤768 `.st-key-uv3-top-nav`、`TOUCH_MIN_PX=48`） | 無（Cloud／真機／WebView NOT RUN） | D（僅驗收） |
| 2 | 桌機深色左側欄＋淺色主內容 | DEC-2026-10-27-09；§0.4 CURRENT | ui_v3/design/tokens.py::PALETTE `color.sidebar.*`；nav.shell_css 側欄規則 | 無；深色**主內容**（雙模式）不在範圍 | — |
| 3 | 五頁頁序／短標／🤖 禁入 | 80 §7；registry 檔頭 | shell/registry.py::IA_PAGES：mkt=True；ast／exp／set=`wireframe_not_approved`；ai=`phase7_onebrain_not_enabled`（建構時擋） | 僅 🌍 可進，其餘見列 14～17 | — |
| 4 | 🌍 首屏主圖露出量 | 13.5 #1；81 MV-09 只要求「主圖或主數字可見」 | pages/mkt.py::_render（摘要卡→Primary）；批 1 後 390／768／1280 露出 199.8／249.4／266.4 px（mkt_visual_batch1 draft.md） | 露出**門檻客戶未訂**；stHeader 60→40 未做（收益+14.4px，需連動 padding-top） | D（門檻）；做法 B |
| 5 | 🌍 圖表系列色（兩線可分） | 44 之十八其三（DEC-2026-10-27-27 允許系列色，另需非顏色辨識）；gap §2.B G3 | pages/chart_svg.py 全用 currentColor；tokens `chart.*` 為 None | 兩線同色，僅靠實／虛線＋末點標籤 | B（色值核准；非版面） |
| 6 | 輔助字 12→13px | DEC-2026-11-11-02／-03（併下一個已授權 UI 批，先測三寬度；不可改導覽控制項尺寸） | tokens `type.caption`=13px；shell/nav.py 有 7 行含 `font-size:12px`（約 3 行屬手機頁首導覽格，不動；其餘為側欄標籤、CTA 註、Status Bar、footer）；theme.py 那 1 行是註解、非字級 | Shell 殘留 12px | A |
| 7 | 🌍 狀態展開列排版（G9） | 81 §3.3 層 2 | mkt.py::status_row_html 純文字列 | 390 展開折行擠；內容語意不變 | A（需使用者點名範圍） |
| 8 | pill hover；768 主圖置中（QA N1／N4） | draft.md「待 Visual Gate」 | 無 hover；768 主圖 x=17 偏左 | 需新 token／客戶審 | B |
| 9 | 🌍 摘要卡層級（G6） | DEC-2026-11-03-09；gap G6 | mkt.py::summary_html 四列同字級 | 「首屏大狀態卡」屬版面異動；不得增 chip／數字 | B |
| 10 | 藍圖內容：風險儀表、偏多偏空、EPS×PE、NASDAQ／MSCI、右側 AI 區 | gap §2.A；81 §4 | 「尚未取得（7 項）」收合群組 | 語意／資料 Gate，非視覺 | C（參考圖片 D） |
| 11 | 暫行字樣虛線底線（G7） | rules.py::APPROVED_WORDING | `.uv3-pending` | 須客戶逐項定字 | C（字樣核准） |
| 12 | 完整資料診斷集中 ⚙️ 設定→資料健康度 | 80 §16.2；79 §9.5（SET-1／2／8）；83 | registry `set` 未掛；PROJECT_RULES 索引「⚙️ 尚無 New UI2 wireframe」；ui_v3/pages/nas_diag.py 只是 NAS 診斷 FAKE 渲染 | 整頁缺 wireframe；83 的獨立 Sheet 是候選、未核准 | B（先出線框）；Sheet／契約 C |
| 13 | 每頁預留 OneBrain 解釋位置 | 67 §6.1.2、§8.9；80 §7.4／§16.4；44 之十八其二（桌機第一屏至多 1 個 AI 入口） | 任何頁都沒渲染；viewmodels/action_slot.py 是「行動詞佔位」（Phase 7 前只能「無法判定」），ui_v3 內僅 viewmodels/__init__ 再匯出、頁面未引用（grep） | 80 §7.1／81 線框沒有該位置 | B（見 §2b）；顯示 AI 內容 D |
| 14 | 💼 掛載（FAKE-only 單頁） | DEC-2026-11-14-06；DEC-2026-11-19-01／-09；c_assets_s_ast_m1_gate_v2 | pages/assets.py＋adapters/assets_page.py 已在 ui_v3；registry `ast` 未掛；poc 11 情境 | 修正版 Gate 待使用者核准；需對 S-a(7) 提精確例外、改 2 條以上守衛 | B（真資料 C／D：BL-0545、BL-0542 G-1～5） |
| 15 | 🔍 掛載 | DEC-2026-11-14-04／-08；BL-0554 | 兩個 renderer 住 poc/（fund_search_renderer、fund_lookup_renderer）；ui_v3 無 pages/exp.py；VM／adapter 已在 ui_v3 | 掛載需先**搬模組**（與掛載分 PR，M-2 卡）；Gate-D 另計 | B（Gate-D C） |
| 16 | ⚙️ 掛載 | BL-0550；DEC-2026-11-19-01 | pages/nas_diag.py 已在 ui_v3；無核准 wireframe | 同列 12 | B |
| 17 | 🤖 | DEC-2026-10-29-07；DEC-2026-11-20-01（OB-B 離線切片，不含 UI） | registry 禁入 | Phase 7 前不得掛 | D |
| 18 | 雙模式（深色主內容） | DEC-2026-11-11-02 T2（等 ⚙️ 設定頁核准實作才設入口） | 僅 poc/dual_theme_isolated | 無 | D |

## 2. 三項特別檢查
**a. 資料診斷集中到 ⚙️ vs 🌍 現有底部資料狀態列**
- 現況【F】：🌍 底部有 `▸ 尚未取得（N 項）`、`▸ 各項資料狀態`（五條序列：來源／資料日／狀態），Primary 卡內有 `▸ 來源與限制`；Shell 另有 Status Bar 與側欄「資料狀態 n／5」（mkt.py::_render、chrome.py）。
- **必須留在 🌍**：① `▸ 尚未取得`（D4=β，Missing 一項不刪、恆 `◇ 資料未備`；80 §5、81 §3.1／§4）；② 圖卡內缺值／取數失敗短原因（81 §4.1 S2～S9）；③ Chart SPEC（基準日、頻率、缺值不補）與圖下各序列資料日、`▸ 來源與限制`——80 §16.1／§16.2 明寫「主頁只留與判讀直接相關的 freshness／source 摘要」。
- **可移（尚未可動）**：`▸ 各項資料狀態` 的逐列明細，以及 developer diagnostics 層（80 §16.2 第三層，本來就不在一般畫面）。
- **移動前提**：⚙️ 資料健康度已有核准 wireframe 並實作（13.5 #4「UI 精簡≠資訊精簡」）。【I，單組讀碼未驗】預設「比較」檢視下，美 10Y／美 2Y 的來源與資料日可能只出現在該狀態列（利率卡切的是 term／credit／policy 三個衍生序列），所以現在整塊搬走＝移掉**必要來源揭露**。
- **Gate**：改 81 已核准層 2＝B（先草稿）；因含必要來源揭露，BL-0540 G-3（待客戶裁示；總管推薦：只在各頁 wireframe 承接、44 與 72／73／78／65 標 successor 不解凍，涉資料語意才走 G-44 amendment）須先答＝C。【R】⚙️ 建成前不移任何東西；83 的獨立監控 Sheet 與此項無關，不得連動。

**b. 每頁預留 OneBrain 位置 vs 🤖 禁入、Digest、BL-0527／0528**
- 規格內有空間：67 §6.1.2 每頁至多一個 local AI summary 或「查看 AI 判斷」鏡像入口；44 之十八其二桌機第一屏至多 1 個。但 80 §7.1／81 的 🌍 線框**沒有該位置**，且桌機線框右側原是「重要證據 ≤3」（80 §7.1），預留位置會與它競爭。
- **是否構成版面異動【I】**：可見元件（含靜態「AI 尚未啟用」一列）＝新增視覺元件＝B，須先出草稿。**不渲染**的預留（線框上標位置、ViewModel 留 slot 契約、DOM 無元素）不是版面異動，不需 UI 草稿——但「位置」本身仍要寫進線框，那份線框修訂就是 B。
- 與其他項目的關係：registry 🤖 禁入不受影響（slot 不是頁，也不是導覽項）；現有 ActionSlot 是 System Action State（deterministic）的佔位，≠ OneBrain Interpretation（67 §8.9 兩區分隔），**不可拿它冒充**；BL-0527（Digest 契約缺口、「AI 不讀畫面」守衛）與 BL-0540 G-5（客戶「輸出六項」對映 67 6.1 六段／8.9 四區，未決）使 slot 的**內容結構**目前無法定義，只能預留容器；BL-0528 是 A 線舊 AI 行為，與 ui_v3 無依賴，但 slot 不得重用 services/ai_service。DEC-2026-11-20-01 明列不授權 UI。
- 可見字樣：「AI 分析暫不可用／無法判定」只出現在 75／80 文件，**不在 rules.py::APPROVED_WORDING**（grep 無命中）→ 任何可見字樣＝PendingWording，需另核（C）。
- 只有 🌍 已掛載；💼🔍⚙️ 的 slot 受各自掛載 Gate 限制，現在只能做 🌍。

**c. 現有 poc 預覽可作下一批離線素材**
| poc | 可用素材 | 限制 |
|---|---|---|
| assets_fixture_preview | 11 個 FAKE 情境＋A00／A10／A20／A50／A60；renderer 已是 ui_v3/pages/assets.py | 掛載條件見列 14；不得顯示假金額／成本（DEC-2026-11-19-09），建議情境③ |
| nas_diag_preview | 13 情境；renderer 已是 ui_v3/pages/nas_diag.py；可作 ⚙️ 資料健康度草稿的「單一來源診斷區塊」參考 | 無 ⚙️ 整頁線框；NAS 診斷≠全站資料健康度 |
| fund_search_fixture_preview／fund_lookup_component_preview | 🔍 兩區版面與缺值語意；renderer 在 poc/ | 須搬模組才能掛；字樣皆 PendingWording；授權為轉述 |
| dual_theme_isolated | 淺／深對比量測與 token 作法 | 僅隔離 PoC，不得被 ui_v3 引用（守衛）；等 ⚙️ 入口 |
全是 FAKE／離線，不能當真實資料驗收；poc 與 ui_v3 互相引用受守衛限制。

## 3. 推薦「下一個最小 UI 批」（互不衝突；皆只動 🌍）
**R1 [A] 🌍 小幅純視覺**：目標＝Shell 殘留 12px→13px（不含導覽格尺寸）＋狀態展開列排版（G9，需使用者點名範圍）。檔案＝ui_v3/shell/nav.py（僅 Status Bar／footer 字級）、ui_v3/pages/mkt.py（status_row_html 與 CSS）。守衛＝test_ui_v3_navigation_shell／top_nav_browser／market_page_browser／design_tokens／degraded_first_screen_budget。驗收＝390／768／1280 無橫向溢出、五格仍等寬≥48px、首屏露出不低於批 1 基線。不碰＝導覽控制項尺寸、首屏預算、字樣、資料、registry、config.toml。理由＝授權方向已存在（DEC-2026-11-11-02／-03），風險最低。
**R2 [B] 🌍 圖表系列色**：目標＝兩線不同色，保留實／虛線＋末點標籤。最小草稿＝一頁色票示意（候選色值、對 `color.surface` 的對比數字、色盲模擬；避開 red／yellow／grey 狀態語意色）。檔案＝tokens.py（新增 chart 系列 token）、chart_svg.py、對應測試（chart_svg 現鎖 currentColor）。守衛＝design_tokens、token_contrast、market_chart_svg。驗收＝三寬度兩線可分、純灰階仍可辨、迷你圖同色。不碰＝單 Y 軸、≤3 series、斷線、不畫 band／目標價。理由＝gap 分析判定觀感差距最大；與 R1 檔案不重疊。
**R3 [B] 🌍 OneBrain 預留位置線框草稿（docs-only）**：目標＝在 81 增補一頁位置示意（桌機／390），預設**不渲染**；同時列出「可見版」候選供使用者選。檔案＝新增一份 docs/evidence 草稿，不改 81 本文。守衛＝無（docs）；日後實作才加。驗收＝草稿標明與首屏預算（≤5）、「重要證據 ≤3」、桌機至多 1 個 AI 入口的關係。不碰＝registry、🤖、ActionSlot 啟用、services/*、任何 AI 字樣上線。理由＝位置要先定才不會與右側證據欄衝突，且不產生假 AI 內容。
**未入選但建議緊接**：⚙️ 資料健康度 wireframe 草稿（B，列 12）——它是搬動 🌍 任何診斷的前提，且需先有 BL-0540 G-3 答案，故不與 R1～R3 並批。

## 4. 需使用者裁示的最小問題（只列真正未決）
**Q1（C，BL-0540 G-3）** 診斷集中到 ⚙️ 後，🌍 底部要不要保留？既有答案：80 §16.2「主頁只留 freshness／source 摘要」，未說移除；總管推薦見 BL-0540。【R】保留 `▸ 尚未取得`、圖卡揭露、`▸ 來源與限制`；`▸ 各項資料狀態` 待 ⚙️ 建成後再議。風險：現在移動會失去美 10Y／2Y 揭露（【I】未驗）。
**Q2（B／C）** OneBrain 位置：(i) 只在線框預留、不渲染；(ii) 頁底靜態一列；(iii) 桌機右欄。既有答案：67／80 只限「≤1、不放假資料」。【R】先 (i)，由 R3 草稿決定。風險：(ii)(iii) 需新增 PendingWording，且與「五頁精簡」相衝。
**Q3（B）** 圖表兩線是否同意不同色，並核准色值？既有答案：44 之十八其三已允許系列色，值未核准。【R】由 R2 色票草稿定。風險：色值若帶好壞語意（紅綠）會違反「顏色只映射資料狀態」。
**Q4（D）** 請本人確認轉述方向（尤其 OneBrain 位置、診斷集中）並提供金融儀表板參考圖片；Cloud 截圖（確認 Deploy 頂欄、stHeader 縮 40 是否值得）。既有答案：repo 無；依 DEC-2026-11-20-01 的做法，由使用者本人逐字確認後才能登記為 DEC。風險：沒有它，「像不像參考圖」只能 NOT VERIFIED。
**Q5（D）** 🌍 手機首屏主圖至少露出多少 px？既有答案：未訂，現 199.8／249.4／266.4（fixture）。【R】訂 ≥200（390）作為守衛基線。風險：Cloud 真機字型差異。

## 5. 無法確認項
- 轉述方向的原文與涵蓋範圍；金融儀表板參考圖片。
- Cloud／真機／WebView 實際畫面；ui_v3 Cloud URL 與部署 SHA（PROJECT_RULES §0.4：NOT VERIFIED）。
- 表列 4、8 的量測引自 mkt_visual_batch1 證據（本組未重跑）；列 6 的「7 行」為 grep 行數，歸屬（導覽格 vs 其餘）僅憑 grep -o 片段判讀，未讀全。
- §2a 的「美 10Y／2Y 揭露只在狀態列」為讀碼推論，未實跑 UI。
- R1～R3 的守衛清單由檔名推得，未實跑任何測試；CI 狀態未查。
- 本表為單組結論，「現況無其他差額」之類全稱句不成立，視為待驗。
