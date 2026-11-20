# UI-D：OneBrain × New UI2 跨頁共用分析線框（docs-only；2026-11-20；#1300）

單組產出，未經獨立複驗；非授權、非裁示、非客戶核准；登記不構成動工授權（`CLAUDE.md` §-1）。對應 `docs/BACKLOG.md` BL-0561 R3（🌍 OneBrain 預留位線框草稿）與 BL-0560（共用分析快照契約差額）。本稿是 B 類 UI 草稿（`CLAUDE.md` §-1.5.4）：先出草稿、等客戶拍板，才能寫任何 UI 程式碼。

**基準**：origin/main `8ebb5290`。方向依 `DEC-2026-11-20-02`（要點轉述〔待核〕，非逐字）；OB-B 範圍依 `DEC-2026-11-20-01`。

## 0. 結論
1. 已交付單檔、無外部資源、無 JS 的靜態線框 HTML：先畫資料流，再對 🌍 💼 🔍 🤖 ⚙️ 五頁各畫一組「桌機 1280／手機 390」畫面。
2. 每頁只示意**一個**「OneBrain｜本頁解釋」位置（🌍 💼 🔍）：預設收合、標「未啟用」「設計示意」、DOM 順序在必要揭露之後（手機單欄在主內容之後）；實測桌機框與手機 🔍 框的位置落在首屏內、手機 🌍／💼 在首屏外（§3-2、§6）；位置內沒有任何解釋文字、百分比、範例結論或 Fake Provider 文字。🤖 只畫將來槽位結構（無內容），⚙️ 沒有 OneBrain 位置，只有 deterministic 的「缺資料會限制 AI 判讀」說明。
3. 🌍 💼 🔍 三個位置是**同一份分析快照的不同 slice**（翻頁不各自重跑 AI）。資料流圖並示意「分析未完成／快照不一致／資料不足」三種不可用狀態：位置不變、內容不顯示，不以舊結論頂替。
4. 揭露：OB-B（`services/onebrain/`）目前只是離線 Fake Provider 型別與測試，不連 UI。本組以 `git grep -ln "services.onebrain\|from services import onebrain" -- '*.py'` 實查，只有 `services/onebrain/` 自身與 `tests/test_onebrain_*.py` 三檔命中（單組、未複驗；不含動態 import 或非 `.py` 引用）。

5. **共用註記（QA 非作者 Must-Fix，#1303）**：HTML 資料流圖旁加「共用註記」（`#shared-note`；💼／⚙️ 的框外註記指回此處），逐字採用 QA 建議文案：「同一快照換頁、收合診斷或隱藏卡片，完整證據及 Missing 集合應保持一致。即使顯示相同，持倉只轉交 skipped_holdings／skipped_tabs，其他略過組未涵蓋，件數未知不能寫成零；NAV 須保留來源、資料日、取回時間及 stale／失敗／拒收原因；缺 FX 的幣別及未估值部位仍須保留；設定讀取失敗須與確實未設定分開。」
   - 「持倉兩組轉交」是 CURRENT 限制；真實持倉的影響 NOT VERIFIED；BL-0545 BLOCKED；不得寫成「資料斷線」。
   - **驗收方向**：僅換頁→證據相同；僅改上游拒收／略過→同畫面仍可分辨（NOT RUN；設計層，本稿未驗任何實作）。
   - 不新增產品欄位、不造數字、不發明 schema；`skipped_holdings`／`skipped_tabs` 為 QA 文案內既有識別名，本組未再核對其程式定義。

6. **OB-B／Fake Provider 揭露的位置**：HTML 資料流區底部「OB-B 現況揭露」callout 是**文件層揭露**，不是畫面框內文字；五頁的畫面框內沒有任何 Fake Provider 字樣。
7. **共用註記的標示**：HTML 註記標題含「CURRENT 限制；NOT VERIFIED」，正文中「持倉只轉交…」前亦標「CURRENT 限制、真實影響 NOT VERIFIED」（QA 逐字文案因此多插一個括號，其餘字句未動），避免單獨被引用成已確認事實；🌍／💼／🔍／⚙️ 的框外註記皆指回 `#shared-note`。

## 1. 檔案
| 路徑 | 說明 |
|---|---|
| `docs/design/onebrain_new_ui2_shared_slice_wireframe_2026_11_20.html` | 線框本體（單檔；內嵌 CSS；無外部資源；無 JS；收合用原生 `<details>`） |
| `docs/evidence/ui_d_onebrain_wireframe_2026_11_20/shot_390.png`、`shot_1280.png` | Chromium 整頁截圖，視窗 390／1280、DPR 1 |
| `docs/evidence/ui_d_onebrain_wireframe_2026_11_20/measure.py` | 量測＋截圖腳本（可重現；§6 的輸出原文即它的 stdout） |
| 本 README | 說明、對照表、衝突與建議、PendingWording、最小 Gate、量測、測試輸出 |

**截圖說明**：整頁（390 寬 12,362px 高；1280 寬 9,761px 高）。為符合單檔 < 400KB，以 Pillow 轉調色盤 PNG（無抖色）：390 為 64 色（368,620 bytes）、1280 為 12 色（376,978 bytes），**不是原始全彩輸出**，細緻色階（例如淡色底）會被合併。截圖內的 `⬜` 顯示成方框：截圖環境的字型沒有該字形，屬截圖環境問題，不是線框內容。390 視窗下桌機框（比視窗寬）放在自己的橫向捲動容器內，截圖只看得到它的左側一段。

**版面說明**：390 與 1280 兩個畫面因寬度不同無法在 1280 視窗內左右並排，故上下堆疊（桌機框在上、手機框在下）；桌機框固定為桌機版型（深色左側欄＋淺色主區），不隨視窗寬度改變。

## 2. 每頁對照：保留的 UI 證據／OneBrain 預留位置／正式 Gate
各頁「保留的 UI 證據」只是把既有線框與證據文件已要求的必要揭露照錄、不重畫版面；是否可搬或可刪仍依 BL-0540（本稿一項都不刪）。

| 頁 | 保留的 UI 證據（必要 Missing／Source／Freshness 與主要內容） | OneBrain 預留位置（線框內） | 正式 Gate（誰要拍板才能前進） |
|---|---|---|---|
| 🌍 市場與趨勢 | Primary 圖卡與基準日／頻率／缺值不補／資料日／來源；Secondary 卡；Missing（◇ 資料未備）、新鮮度（⬜ 門檻待裁示）、來源；「查看完整資料健康度」入口位置 | DOM 順序在必要揭露之後、預設收合的單一「OneBrain｜本頁解釋」（未啟用；桌機實測入口 summary 在首屏內，見 §3-2） | G2（位置與首屏限制）；加位置須 amend `docs/v2/81` 層 2（`DEC-2026-11-20-02` 不授權）；BL-0540 G-3 |
| 💼 我的資產 | 主圖在前、摘要四項不因 Missing 消失（缺值顯示 ◇ 資料未備，不顯示 0）、近期事件位置、持倉來源／資料日／新鮮度 | 同上 | G2；💼 renderer／registry／真實接線仍未核准（`PROJECT_RULES.md` §0.4 文件地圖列） |
| 🔍 找基金 | 查一檔基金（MoneyDJ 代碼或 ISIN；ISIN 尚未啟用）、基金身份、結果三態（有資料／查無／取數失敗）、不排名、來源／資料日 | 同上 | G2；🔍 線框尚未核准（registry `wireframe_not_approved`） |
| 🤖 AI 投資總結 | Phase 7 前導覽可見不可點、不註冊頁面（`docs/v2/80` §7.4） | 無 slice：本頁就是全站綜合；只示意將來四個槽位（主要證據／最強反證／未確認／Evidence trace），全空 | G3（槽位與 67 §8.9／80 §16.4 對映）；Phase 7 與正式 OneBrain 入口 Gate |
| ⚙️ 設定 | 完整資料健康度三層（沿用 UI-B #1297，本稿不重畫）；必要揭露 | **無**。只有 deterministic「資料限制說明」（規則產生；框內不出現 OneBrain 字樣）。不加第 4 個 local summary | G3；BL-0560 (a)；BL-0540 |

## 3. 與既有契約的衝突與建議
以下「建議」是本組讀法，可推翻。

1. **67 §6.1 第 2 點（各頁至多一個 local summary，或一個「查看 AI 判斷」鏡像入口）**：本稿畫成收合的 local summary 位。「local summary」與「鏡像入口」二選一尚未定。現況（§3-2、§6 實測）：入口 summary 的位置，桌機三頁與手機 🔍 落在首屏內、手機 🌍／💼 在首屏外；收合內容預設不展開。是否維持收合位、入口是否須移出首屏，待 G2 裁示，本稿不裁決。
2. **44 之十八其二第 3 點（桌機第一屏至多 1 個 AI 摘要入口；手機第一屏更少）**：本稿位置的 DOM 順序在必要揭露之後（手機單欄在主內容之後），預設收合。**但實測並非都在首屏之外**（`measure.py`，位移＝位置 summary 頂端相對所在框頂端，框頂視為開啟該頁時的視窗頂）：桌機框（視窗 1280×800）🌍 665／💼 439／🔍 248px，全部小於 800，即落在首屏內（桌機雙欄把右欄的位置拉高）；手機框（視窗 390×844）🔍 729px（底 789px）落在首屏內，🌍 1062px、💼 979px 在首屏外。桌機每頁仍只有 1 個入口、符合「至多 1 個」的數量上限，但「是否算首屏 AI 入口、手機是否算『更少』」與 44 該條的關係**待 Gate（G2）**，本稿不裁決。（390 視窗下的桌機框為 1000px 寬的捲動框，數值不代表 1280 桌機，以 1280 視窗的數值為準。）
3. **`docs/v2/81` 層 2（現仍列 🌍 展開區）**：在 🌍 加 OneBrain 位置等於新增元素，`DEC-2026-11-20-02` 明示不授權修改 81 層 2。建議：本稿核准後，81 的 amendment 與 G2 同批處理，不單獨改 81。（81 層 2 現行逐字內容本組未再讀，只引 DEC 的記載。）
4. **67 §6.1 只批准 🌍／💼／🔍，⚙️ 不在內**：UI-B（#1297）曾放「OneBrain｜資料限制說明」可見版（標尚未啟用、DOM 內有元素）；本稿把 ⚙️ 該塊改稱「資料限制說明（規則產生，非 AI）」，不使用 OneBrain 名稱，避免被讀成第 4 個 local summary。建議：UI-B 與本稿一併收斂為「⚙️ 只有 deterministic 說明」；UI-B 若已核准的部分與此不同，以客戶裁示為準。
5. **輸出項目對映未定**：`docs/v2/80` §16.4（客戶 2026-11-03 所列六項：系統狀態／AI 投資總結／主要依據／最強反證／風險不確定性／Evidence trace）、`docs/v2/67` §6.1 六段與 §8.9 四區，三者對映待客戶確認（BL-0540）。🤖 槽位四個名稱（主要證據／最強反證／未確認／Evidence trace）取自本次派工單，是示意用，不是對映結論；本稿不擇一、不改 67。
6. **共用快照契約未定**：fingerprint、refresh 觸發、失效策略、快取均屬 BL-0560 (b)，本稿不發明任何欄位、Rule IDs、cache schema 或 Digest 欄位。線框內的「‹快照識別›」只是佔位。
7. **「舊分析」是否可顯示**：本稿預設不顯示（避免把舊結論當新分析）；若客戶要顯示「舊分析」並標明產生時間，是新的契約決定，不在本稿範圍。
8. **現行 `ui_v3/shell/nav.py` 的手機頁首用 12px／10px 字**：本線框為符合「最小字級 ≥ 13px」一律 ≥ 13px（與 UI-B 同做法），這不是對現行實作的修改建議，只是線框量測基準。
9. **⚙️ 框內字樣取捨**：依 QA 意見，⚙️ 框內不再出現 OneBrain 字樣（改為文件層註記），並把「缺資料會限制 AI 判讀」改為「缺資料會限制分析判讀」（chip 由「規則產生，非 AI」改為「規則產生」，說明句改為「這是規則產生的說明句，不是分析結果」）。"分析"取代"AI"不改變原意（限制的是啟用後的分析），但**張力仍在**：原派工用語為「缺資料會限制 AI 判讀」，且 🤖 框內仍用既有字樣「AI 分析暫不可用」；最終用字待客戶定字（已列入 §4）。

## 4. PendingWording 清單（HTML 內新字樣；未經核准，不得寫成已核准）
「新」＝本線框新增；「既有」＝repo 內已存在但仍未核准的字樣；「已核准」＝`APPROVED_WORDING`／規則表／`docs/v2` 已核准。HTML 內虛線底線的字樣大致對應「新」與「既有」。文件層（標題、框外註記、標籤）不進產品，不列入。

**新**
- OneBrain 位置：OneBrain｜本頁解釋；本頁解釋；查看依據（作為位置標籤；「查看依據」概念見 67 §6.1，但作為此位置標籤是新用法）；分析快照；‹快照識別›（佔位，不是欄位定義）；⬜ 未啟用；設計示意；「此區是「同一份分析快照」的本頁 slice，不會在本頁自行重新分析。」；「本頁解釋（此位置尚無內容；啟用前不顯示任何文字）」；「（未啟用）」；「‹快照識別›｜與其他頁為同一份（示意佔位，不是欄位定義）」。
- 不可用狀態：⬜ 分析未完成；⬜ 快照不一致；⬜ 資料不足；「本頁解釋暫不顯示，不以先前的結論頂替。」；「各頁未對齊到同一份分析快照，本頁解釋暫不顯示。」；「缺：‹類別清單›；無法產生本頁解釋。」；「翻頁只是看同一份快照的不同 slice，不各自重跑 AI。」；「是否允許顯示「舊分析」並標明產生時間＝待裁示…」（文件層說明）。
- 🤖：示意：Phase 7 後；「現況：導覽項標「尚未開放」、不可點、不註冊頁面。」；主要證據；最強反證；未確認；Evidence trace；全站綜合；「🤖 是唯一的全站綜合頁；🌍／💼／🔍 的「本頁解釋」是同一份快照的 slice，不在此重複。」；（空）。
- ⚙️：資料限制說明；規則產生；「缺資料會限制分析判讀：下列類別目前未取得，分析啟用後相關判讀會因此受限。」；「未取得：‹類別清單›」；「這是規則產生的說明句，不是分析結果。」；必要揭露（本頁即完整資料健康度所在）；① 全站資料取得摘要、② 逐來源／序列明細、③ 開發者診斷（預設收合）（沿用 UI-B 的新字樣，仍未核准）。
- 共用註記（文件層，但字樣待核）：同一畫面不等於同一上游證據；「同一快照換頁、收合診斷或隱藏卡片，完整證據及 Missing 集合應保持一致。…設定讀取失敗須與確實未設定分開。」（全文見 §0-5）；「持倉兩組轉交」「CURRENT 限制」「NOT VERIFIED」「BL-0545 BLOCKED」。
- 各頁示意區塊標題（畫面內；沿用既有線框的區塊、標題為本稿示意，未核准）：近期事件／配息（位置示意）；摘要四項（缺值仍保留位置，不顯示 0）；缺 ‹N› 項（四項摘要不因缺值消失）；依條件篩選；查一檔基金；持股明細（預設收合）。
- 資料流圖與位置標籤（畫面示意；名稱沿用既有概念、欄位未定）：Decision Digest；單一 OneBrain；各頁 slice；未來（未啟用）：給 OneBrain 讀；不可用狀態（位置不變，內容不顯示）；💼 的「頁級狀態」（作為列名；β 階梯語意沿用既有）。
- 各頁共用：必要揭露（保留在頁內）；Missing／新鮮度／來源（作為列名）；「尚未取得 ‹N› 項（名單收合，一項不刪）」。
- 🔍：查無此代碼；「結果三態要分開：有資料／查無此代碼／⛔ 取數失敗（查無 ≠ 取數失敗）」（說明句）。

**既有（repo 內已有，仍未核准）**
- 查看完整資料健康度 ›（入口字樣，UI-B 已列待核准）；System State、整區只顯示「AI 分析暫不可用／無法判定」（`docs/v2/80` §7.4／75，proposal）；MoneyDJ 基金代碼或 ISIN、◇ 尚未確認（`docs/v2/80` §7.3，proposal）；暫無完整市場綜合判定（缺正式 aggregation rule）（`docs/v2/80` §7.1／`DEC-2026-10-27-41`；本線框在其前加 ⬜ 符號，符號用法待確認）。

**已核准（本線框直接沿用）**
- ◇ 資料未備、⬜ 無法判定、⛔ 取數失敗、⬜ 門檻待裁示、開發中、尚未開放、PREVIEW、基金投資儀表板、市場／資產／找基金／AI／設定、「‹n›／‹m› 項已取得」、「更新：‹時間›」、ISIN：尚未啟用、目前條件下有 N 檔符合。

## 5. 最小 Gate（≤ 3 項；總管決定是否向使用者提問）
**G1｜共用分析快照契約（BL-0560 (b)）**
- 問題：是否採「全站一份分析快照、🌍 💼 🔍 各為其 slice、翻頁不各自重跑 AI」；三種不可用狀態（分析未完成／快照不一致／資料不足）是否採「位置不變、內容不顯示、不以舊結論頂替」？
- 已知答案：`DEC-2026-11-20-02` 方向第 (3) 點已有「全站一個 OneBrain、各頁為同一份 Digest 與快照的 slice」；fingerprint、refresh、失效、快取契約明列為不授權、待 Gate。
- 推薦：先只核准「slice 與不可用狀態的行為原則」；契約細節（欄位、快取）留待 Digest Gate，不在本稿定。
- 風險：若契約晚於 UI 定案，位置會被迫改；若各頁自行呼叫 AI，會出現互相矛盾的解釋。

**G2｜OneBrain 位置與首屏限制（67 §6.1／44 之十八其二／81 層 2）**
- 問題：🌍 💼 🔍 的位置是否定為「主內容之後、預設收合的單一 local summary 位」（而非「鏡像入口」）；是否可落在首屏另議？
- 已知答案：67 §6.1 每頁至多一個 local summary 或一個鏡像入口；44 之十八其二桌機第一屏至多 1 個 AI 入口；81 層 2 現行不含它。
- 推薦：收合內容預設不展開；入口 summary 的首屏落位待裁示（實測桌機三頁與手機 🔍 的 summary 落在首屏內，見 §3-2）；同批 amend 81 層 2（與 BL-0540 G-3 同一批處理）。
- 風險：位置落在首屏可能與 44 之十八其二的首屏 AI 入口限制衝突，並擠掉必要的 Missing／Source／Freshness；放太深可能使用者找不到。

**G3｜⚙️ 只有 deterministic 說明，與 🤖 槽位對映（BL-0560 (a)／67 §8.9／80 §16.4）**
- 問題：⚙️ 是否確認只放規則產生的「資料限制說明」、不加第 4 個 local summary；🤖 槽位四名稱如何對映 67 §8.9 四區與 80 §16.4 六項？
- 已知答案：67 §6.1 只批准 🌍／💼／🔍；`DEC-2026-11-20-02` 未授權 ⚙️ 獨立 AI local summary；對映待客戶確認（BL-0540）。
- 推薦：⚙️ 維持 deterministic；🤖 槽位對映待 Phase 7 前再議，本稿四名稱僅示意。
- 風險：若 ⚙️ 出現 OneBrain 字樣，會被讀成第 4 個 local summary（違反 67 §6.1）。

## 6. 量測（真 Chromium；playwright；DPR 1；腳本＝同夾的 `measure.py`）
**stdout 原文**（只算「目前可見」的元素；未展開的 `<details>` 內容不計；視窗高 1280×800／390×844；`touchTargets` ＝ `summary`、頁首五格／側欄項、輸入欄、按鈕、pill、入口列、slice pill；`first-screen` 列＝OneBrain 位置的首屏位置）：
```
== viewport 390
default (all <details> closed): {'scrollWidth': 390, 'clientWidth': 390, 'fullHeight': 12362, 'minFontPx': 13, 'textNodesUnder13px': 0, 'touchTargets': 88, 'touchMinHeightPx': 48, 'touchUnder48': 0, 'chipsVisible': 63, 'chipsWithoutText': 0, 'overflowElementsOutsideDeskWrap': 0, 'deskWraps': 5, 'deskWrapScrolls': 5, 'mobFrames': 5, 'mobFrameMaxWidthPx': 358, 'mobFramesScrollingInside': 0, 'mobTopnavCells': '5,5,5,5,5', 'mobTopnavMinCellHeightPx': 60.1875, 'mobTopnavPositions': 'static', 'deskFrames': 5, 'deskTopnavHidden': True, 'mobSideHidden': True, 'obSlotsClosedByDefault': True, 'obSlots': 6}
first-screen: {'page': 'p-mkt', 'frame': 'desk', 'summaryTopInFramePx': 707, 'summaryBottomInFramePx': 768, 'viewportH': 844, 'inFirstScreen': True}
first-screen: {'page': 'p-mkt', 'frame': 'mob', 'summaryTopInFramePx': 1062, 'summaryBottomInFramePx': 1122, 'viewportH': 844, 'inFirstScreen': False}
first-screen: {'page': 'p-ast', 'frame': 'desk', 'summaryTopInFramePx': 482, 'summaryBottomInFramePx': 542, 'viewportH': 844, 'inFirstScreen': True}
first-screen: {'page': 'p-ast', 'frame': 'mob', 'summaryTopInFramePx': 979, 'summaryBottomInFramePx': 1039, 'viewportH': 844, 'inFirstScreen': False}
first-screen: {'page': 'p-exp', 'frame': 'desk', 'summaryTopInFramePx': 292, 'summaryBottomInFramePx': 352, 'viewportH': 844, 'inFirstScreen': True}
first-screen: {'page': 'p-exp', 'frame': 'mob', 'summaryTopInFramePx': 729, 'summaryBottomInFramePx': 789, 'viewportH': 844, 'inFirstScreen': True}
all <details> open: {'scrollWidth': 390, 'clientWidth': 390, 'fullHeight': 14361, 'minFontPx': 13, 'textNodesUnder13px': 0, 'touchTargets': 88, 'touchMinHeightPx': 48, 'touchUnder48': 0, 'chipsVisible': 63, 'chipsWithoutText': 0, 'overflowElementsOutsideDeskWrap': 0, 'deskWraps': 5, 'deskWrapScrolls': 5, 'mobFrames': 5, 'mobFrameMaxWidthPx': 358, 'mobFramesScrollingInside': 0, 'mobTopnavCells': '5,5,5,5,5', 'mobTopnavMinCellHeightPx': 60.1875, 'mobTopnavPositions': 'static', 'deskFrames': 5, 'deskTopnavHidden': True, 'mobSideHidden': True, 'obSlotsClosedByDefault': False, 'obSlots': 6}
screenshot shot_390.png: 390x12362px, 64 colors, 368620 bytes
== viewport 1280
default (all <details> closed): {'scrollWidth': 1280, 'clientWidth': 1280, 'fullHeight': 9761, 'minFontPx': 13, 'textNodesUnder13px': 0, 'touchTargets': 88, 'touchMinHeightPx': 48, 'touchUnder48': 0, 'chipsVisible': 63, 'chipsWithoutText': 0, 'overflowElementsOutsideDeskWrap': 0, 'deskWraps': 5, 'deskWrapScrolls': 0, 'mobFrames': 5, 'mobFrameMaxWidthPx': 390, 'mobFramesScrollingInside': 0, 'mobTopnavCells': '5,5,5,5,5', 'mobTopnavMinCellHeightPx': 60.1875, 'mobTopnavPositions': 'static', 'deskFrames': 5, 'deskTopnavHidden': True, 'mobSideHidden': True, 'obSlotsClosedByDefault': True, 'obSlots': 6}
first-screen: {'page': 'p-mkt', 'frame': 'desk', 'summaryTopInFramePx': 665, 'summaryBottomInFramePx': 725, 'viewportH': 800, 'inFirstScreen': True}
first-screen: {'page': 'p-mkt', 'frame': 'mob', 'summaryTopInFramePx': 1019, 'summaryBottomInFramePx': 1080, 'viewportH': 800, 'inFirstScreen': False}
first-screen: {'page': 'p-ast', 'frame': 'desk', 'summaryTopInFramePx': 439, 'summaryBottomInFramePx': 499, 'viewportH': 800, 'inFirstScreen': True}
first-screen: {'page': 'p-ast', 'frame': 'mob', 'summaryTopInFramePx': 979, 'summaryBottomInFramePx': 1039, 'viewportH': 800, 'inFirstScreen': False}
first-screen: {'page': 'p-exp', 'frame': 'desk', 'summaryTopInFramePx': 248, 'summaryBottomInFramePx': 309, 'viewportH': 800, 'inFirstScreen': True}
first-screen: {'page': 'p-exp', 'frame': 'mob', 'summaryTopInFramePx': 729, 'summaryBottomInFramePx': 789, 'viewportH': 800, 'inFirstScreen': True}
all <details> open: {'scrollWidth': 1280, 'clientWidth': 1280, 'fullHeight': 11619, 'minFontPx': 13, 'textNodesUnder13px': 0, 'touchTargets': 88, 'touchMinHeightPx': 48, 'touchUnder48': 0, 'chipsVisible': 63, 'chipsWithoutText': 0, 'overflowElementsOutsideDeskWrap': 0, 'deskWraps': 5, 'deskWrapScrolls': 0, 'mobFrames': 5, 'mobFrameMaxWidthPx': 390, 'mobFramesScrollingInside': 0, 'mobTopnavCells': '5,5,5,5,5', 'mobTopnavMinCellHeightPx': 60.1875, 'mobTopnavPositions': 'static', 'deskFrames': 5, 'deskTopnavHidden': True, 'mobSideHidden': True, 'obSlotsClosedByDefault': False, 'obSlots': 6}
screenshot shot_1280.png: 1280x9761px, 12 colors, 376978 bytes
```
**讀法**
- 文件溢出：兩個視窗、預設與「全部 `<details>` 展開」後，`scrollWidth` ＝ `clientWidth`（390／1280），`overflowElementsOutsideDeskWrap` ＝ 0。
- 桌機框：1280 視窗下 5 個桌機框都容得下（`deskWrapScrolls` ＝ 0）；390 視窗下 5 個桌機框都比視窗寬，改在自己的捲動容器內橫向捲動（`deskWrapScrolls` ＝ 5，設計如此，不計入文件溢出）。手機框在兩個視窗都不在框內溢出（`mobFramesScrollingInside` ＝ 0）。
- 最小字級：`minFontPx` ＝ 13，`textNodesUnder13px` ＝ 0（以文字節點 computed `font-size` 量測；不含 emoji／符號字型的實際字高）。
- 觸控：可見目標 88 個，最小高度 48px，`touchUnder48` ＝ 0。頁首五格與入口列在線框中是靜態示意，量測用來確認版型尺寸。
- 手機頁首五格：5 個手機框都是 5 格，`mobTopnavMinCellHeightPx` ＝ 60.19（≥ 60）；`position` 為 `static`（非 sticky／fixed）。桌機框的頁首隱藏、手機框的側欄隱藏。
- OneBrain 位置：3 頁 × 2 框共 6 個，預設全部收合（`obSlotsClosedByDefault` ＝ True）。
- 首屏位置（`first-screen` 列；以 1280 視窗的桌機框與 390 視窗的手機框為準）：桌機 🌍 665／💼 439／🔍 248px（視窗高 800，全部在首屏內）；手機 🌍 1062／💼 979／🔍 729px（視窗高 844；只有 🔍 在首屏內）。
- 狀態標籤：每個可見 chip 都有文字（`chipsWithoutText` ＝ 0）；符號是第二重、顏色是第三重。
- 未涵蓋：Cloud／真機／WebView 未量；只量單一 Chromium 版本。

## 7. 測試輸出
本輪（QA 後續修訂）於 README 與其餘新檔皆已存在於工作樹後執行；用總管指定的 scratchpad venv（pytest 在該 venv；同旗標）。

**治理守衛**（repo 根目錄；本 worktree）：
```
python -m pytest tests/test_canonical_rule_consistency.py tests/test_doc_counters.py tests/test_constitution_file_refs.py -q -p no:cacheprovider
........................................................................ [ 63%]
.........................................                                [100%]
113 passed in 86.55s (0:01:26)
```

**S3：新增的 `measure.py` 不會被守衛掃到（讀碼＋實跑）**
讀碼結果（本組讀各守衛的掃描母體；單組、未複驗）：
- `tests/ui_v3/test_ui_v3_import_guard.py`：母體由 `ui_v3_guard_lib` 取，`UI_V3.rglob("*.py")`（只在 `ui_v3/`）。
- `tests/ui_v2/test_ui_v2_live_import_guard.py`：`_UI_V2.rglob("*.py")`（只在 `ui_v2/`）。
- `tests/ui_v2/test_ui_v2_lane_guards.py`：對 `tests/` 底下 `rglob("*.py")` 找特定字串；不掃 `docs/`。
- `tests/test_new_ui_no_imputation_static_guard.py`：`SCAN_DIRS = ("services/v2_tables", "services/v2_domain", "ui_v2", "ui_v3", "shared/ui_semantics")` 加 `shared/active_sheet.py`；不含 `docs/`。
- `tests/test_services_purity_contract.py`、`tests/test_onebrain_offline_guard.py`：前者掃 `services/` 下的 `.py`（`SERVICES.rglob`），後者掃 `services/onebrain/` 與 `tests/test_onebrain_*.py`；皆不含 `docs/`。
- `tests/ui_v2/test_readonly_write_surface_guard.py`：`SCAN_DIRS = ("ui_v2", "services/v2_tables")`，不含 `docs/`。
- 結論：`docs/evidence/…/measure.py` 不在上列任何母體內。這是單組讀碼＋實跑結果，不排除其他未列守衛（例如 pre-commit／CI 工作流的檢查）掃到它。

實跑（同 venv、同旗標）：
```
python -m pytest tests/ui_v3/test_ui_v3_import_guard.py tests/ui_v2/test_ui_v2_lane_guards.py tests/ui_v2/test_ui_v2_live_import_guard.py tests/ui_v2/test_readonly_write_surface_guard.py tests/test_new_ui_no_imputation_static_guard.py tests/test_services_purity_contract.py tests/test_onebrain_offline_guard.py -q -p no:cacheprovider
........................................................................ [ 34%]
........................................................................ [ 52%]
........................................................................ [ 69%]
........................................................................ [ 86%]
.......................................................                  [100%]
415 passed in 25.43s
```

**`git diff --check`**：見下（commit 前對工作樹與暫存區各跑一次；輸出為空＝無空白錯誤）。
```
$ git diff --check HEAD
（無輸出，exit 0）
$ git diff --cached --check
（無輸出，exit 0）
```

## 8. NOT VERIFIED
- 客戶／使用者未核准本線框；不是 DEC、不是 amendment；字樣全為暫行。
- 本檔未經獨立複驗（單組）；§3 的衝突判斷與建議是本組讀法，可推翻。
- `DEC-2026-11-20-02` 與 GitHub #1278 comment 的原文：本組只讀 repo 內的要點轉述，未見逐字原文；該 comment 是否為使用者本人原話無法由 repo 核對。
- 本組未重新讀 `docs/v2/81`、`docs/v2/44` 全文；對 81 層 2 與 44 第一屏 AI 入口上限的引用，來自 `DEC-2026-11-20-02` 的記載與 `docs/v2/44` 該處 grep 到的一行。
- `docs/design/ui_b_settings_data_health_wireframe_2026_11_20.html`（UI-B）的版型與 token 是沿用；本組未驗 UI-B 是否已經客戶核准。
- 「全 repo 只有 `services/onebrain/` 與其測試引用 OB-B」是單組 `git grep`，未涵蓋動態 import 與非 `.py` 引用；OB-B 程式 PR 的 GitHub 狀態本組未查。
- Cloud／真機／WebView 實際畫面；瀏覽器相容性只在單一 Chromium 版本驗過。
- 截圖為調色盤 PNG（390：64 色、1280：12 色，為符合 < 400KB），非原始全彩輸出；`⬜` 在截圖中顯示為方框屬字型缺字。
- CI 狀態未查；未 push、未開 PR、未合併。
