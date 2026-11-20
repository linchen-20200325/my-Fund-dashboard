# UI-D：OneBrain × New UI2 跨頁共用分析線框（docs-only；2026-11-20；#1300）

單組產出，未經獨立複驗；非授權、非裁示、非客戶核准；登記不構成動工授權（`CLAUDE.md` §-1）。對應 `docs/BACKLOG.md` BL-0561 R3（🌍 OneBrain 預留位線框草稿）與 BL-0560（共用分析快照契約差額）。本稿是 B 類 UI 草稿（`CLAUDE.md` §-1.5.4）：先出草稿、等客戶拍板，才能寫任何 UI 程式碼。

**基準**：origin/main `8ebb5290`。方向依 `DEC-2026-11-20-02`（要點轉述〔待核〕，非逐字）；OB-B 範圍依 `DEC-2026-11-20-01`。

## 0. 結論
1. 已交付單檔、無外部資源、無 JS 的靜態線框 HTML：先畫資料流，再對 🌍 💼 🔍 🤖 ⚙️ 五頁各畫一組「桌機 1280／手機 390」畫面。
2. 每頁只示意**一個**「OneBrain｜本頁解釋」位置（🌍 💼 🔍）：預設收合、標「未啟用」「設計示意」、放在主內容與必要揭露之後（不在首屏）；位置內沒有任何解釋文字、百分比、範例結論或 Fake Provider 文字。🤖 只畫將來槽位結構（無內容），⚙️ 沒有 OneBrain 位置，只有 deterministic 的「缺資料會限制 AI 判讀」說明。
3. 🌍 💼 🔍 三個位置是**同一份分析快照的不同 slice**（翻頁不各自重跑 AI）。資料流圖並示意「分析未完成／快照不一致／資料不足」三種不可用狀態：位置不變、內容不顯示，不以舊結論頂替。
4. 揭露：OB-B（`services/onebrain/`）目前只是離線 Fake Provider 型別與測試，不連 UI。本組以 `git grep -ln "services.onebrain\|from services import onebrain" -- '*.py'` 實查，只有 `services/onebrain/` 自身與 `tests/test_onebrain_*.py` 三檔命中（單組、未複驗；不含動態 import 或非 `.py` 引用）。

## 1. 檔案
| 路徑 | 說明 |
|---|---|
| `docs/design/onebrain_new_ui2_shared_slice_wireframe_2026_11_20.html` | 線框本體（單檔；內嵌 CSS；無外部資源；無 JS；收合用原生 `<details>`） |
| `docs/evidence/ui_d_onebrain_wireframe_2026_11_20/shot_390.png`、`shot_1280.png` | Chromium 整頁截圖，視窗 390／1280、DPR 1 |
| `docs/evidence/ui_d_onebrain_wireframe_2026_11_20/measure.py` | 量測＋截圖腳本（可重現；§6 的輸出原文即它的 stdout） |
| 本 README | 說明、對照表、衝突與建議、PendingWording、最小 Gate、量測、測試輸出 |

**截圖說明**：整頁（390 寬 11,601px 高；1280 寬 9,517px 高）。為符合單檔 < 400KB，以 Pillow 轉調色盤 PNG（無抖色）：390 為 64 色（317,579 bytes）、1280 為 16 色（371,779 bytes），**不是原始全彩輸出**，細緻色階（例如淡色底）會被合併。截圖內的 `⬜` 顯示成方框：截圖環境的字型沒有該字形，屬截圖環境問題，不是線框內容。390 視窗下桌機框（比視窗寬）放在自己的橫向捲動容器內，截圖只看得到它的左側一段。

**版面說明**：390 與 1280 兩個畫面因寬度不同無法在 1280 視窗內左右並排，故上下堆疊（桌機框在上、手機框在下）；桌機框固定為桌機版型（深色左側欄＋淺色主區），不隨視窗寬度改變。

## 2. 每頁對照：保留的 UI 證據／OneBrain 預留位置／正式 Gate
各頁「保留的 UI 證據」只是把既有線框與證據文件已要求的必要揭露照錄、不重畫版面；是否可搬或可刪仍依 BL-0540（本稿一項都不刪）。

| 頁 | 保留的 UI 證據（必要 Missing／Source／Freshness 與主要內容） | OneBrain 預留位置（線框內） | 正式 Gate（誰要拍板才能前進） |
|---|---|---|---|
| 🌍 市場與趨勢 | Primary 圖卡與基準日／頻率／缺值不補／資料日／來源；Secondary 卡；Missing（◇ 資料未備）、新鮮度（⬜ 門檻待裁示）、來源；「查看完整資料健康度」入口位置 | 主內容與必要揭露之後、預設收合的單一「OneBrain｜本頁解釋」（未啟用） | G2（位置與首屏限制）；加位置須 amend `docs/v2/81` 層 2（`DEC-2026-11-20-02` 不授權）；BL-0540 G-3 |
| 💼 我的資產 | 主圖在前、摘要四項不因 Missing 消失（缺值顯示 ◇ 資料未備，不顯示 0）、近期事件位置、持倉來源／資料日／新鮮度 | 同上 | G2；💼 renderer／registry／真實接線仍未核准（`PROJECT_RULES.md` §0.4 文件地圖列） |
| 🔍 找基金 | 查一檔基金（MoneyDJ 代碼或 ISIN；ISIN 尚未啟用）、基金身份、結果三態（有資料／查無／取數失敗）、不排名、來源／資料日 | 同上 | G2；🔍 線框尚未核准（registry `wireframe_not_approved`） |
| 🤖 AI 投資總結 | Phase 7 前導覽可見不可點、不註冊頁面（`docs/v2/80` §7.4） | 無 slice：本頁就是全站綜合；只示意將來四個槽位（主要證據／最強反證／未確認／Evidence trace），全空 | G3（槽位與 67 §8.9／80 §16.4 對映）；Phase 7 與正式 OneBrain 入口 Gate |
| ⚙️ 設定 | 完整資料健康度三層（沿用 UI-B #1297，本稿不重畫）；必要揭露 | **無**。只有 deterministic「資料限制說明」（規則產生，非 AI）。不加第 4 個 local summary | G3；BL-0560 (a)；BL-0540 |

## 3. 與既有契約的衝突與建議
以下「建議」是本組讀法，可推翻。

1. **67 §6.1 第 2 點（各頁至多一個 local summary，或一個「查看 AI 判斷」鏡像入口）**：本稿畫成收合的 local summary 位。「local summary」與「鏡像入口」二選一尚未定。建議：先採收合位（不佔首屏），待 G2 裁示。
2. **44 之十八其二第 3 點（桌機第一屏至多 1 個 AI 摘要入口；手機第一屏更少）**：本稿位置在主內容之後、預設收合，兩種版面的第一屏都沒有 AI 入口，不違反上限。若客戶要首屏入口，仍只能 1 個，且手機更少。
3. **`docs/v2/81` 層 2（現仍列 🌍 展開區）**：在 🌍 加 OneBrain 位置等於新增元素，`DEC-2026-11-20-02` 明示不授權修改 81 層 2。建議：本稿核准後，81 的 amendment 與 G2 同批處理，不單獨改 81。（81 層 2 現行逐字內容本組未再讀，只引 DEC 的記載。）
4. **67 §6.1 只批准 🌍／💼／🔍，⚙️ 不在內**：UI-B（#1297）曾放「OneBrain｜資料限制說明」可見版（標尚未啟用、DOM 內有元素）；本稿把 ⚙️ 該塊改稱「資料限制說明（規則產生，非 AI）」，不使用 OneBrain 名稱，避免被讀成第 4 個 local summary。建議：UI-B 與本稿一併收斂為「⚙️ 只有 deterministic 說明」；UI-B 若已核准的部分與此不同，以客戶裁示為準。
5. **輸出項目對映未定**：`docs/v2/80` §16.4（客戶 2026-11-03 所列六項：系統狀態／AI 投資總結／主要依據／最強反證／風險不確定性／Evidence trace）、`docs/v2/67` §6.1 六段與 §8.9 四區，三者對映待客戶確認（BL-0540）。🤖 槽位四個名稱（主要證據／最強反證／未確認／Evidence trace）取自本次派工單，是示意用，不是對映結論；本稿不擇一、不改 67。
6. **共用快照契約未定**：fingerprint、refresh 觸發、失效策略、快取均屬 BL-0560 (b)，本稿不發明任何欄位、Rule IDs、cache schema 或 Digest 欄位。線框內的「‹快照識別›」只是佔位。
7. **「舊分析」是否可顯示**：本稿預設不顯示（避免把舊結論當新分析）；若客戶要顯示「舊分析」並標明產生時間，是新的契約決定，不在本稿範圍。
8. **現行 `ui_v3/shell/nav.py` 的手機頁首用 12px／10px 字**：本線框為符合「最小字級 ≥ 13px」一律 ≥ 13px（與 UI-B 同做法），這不是對現行實作的修改建議，只是線框量測基準。

## 4. PendingWording 清單（HTML 內新字樣；未經核准，不得寫成已核准）
「新」＝本線框新增；「既有」＝repo 內已存在但仍未核准的字樣；「已核准」＝`APPROVED_WORDING`／規則表／`docs/v2` 已核准。HTML 內虛線底線的字樣大致對應「新」與「既有」。文件層（標題、框外註記、標籤）不進產品，不列入。

**新**
- OneBrain 位置：OneBrain｜本頁解釋；本頁解釋；查看依據（作為位置標籤；「查看依據」概念見 67 §6.1，但作為此位置標籤是新用法）；分析快照；‹快照識別›（佔位，不是欄位定義）；⬜ 未啟用；設計示意；「此區是「同一份分析快照」的本頁 slice，不會在本頁自行重新分析。」；「本頁解釋（此位置尚無內容；啟用前不顯示任何文字）」；「（未啟用）」；「‹快照識別›｜與其他頁為同一份（示意佔位，不是欄位定義）」。
- 不可用狀態：⬜ 分析未完成；⬜ 快照不一致；⬜ 資料不足；「本頁解釋暫不顯示，不以先前的結論頂替。」；「各頁未對齊到同一份分析快照，本頁解釋暫不顯示。」；「缺：‹類別清單›；無法產生本頁解釋。」；「翻頁只是看同一份快照的不同 slice，不各自重跑 AI。」；「是否允許顯示「舊分析」並標明產生時間＝待裁示…」（文件層說明）。
- 🤖：示意：Phase 7 後；「現況：導覽項標「尚未開放」、不可點、不註冊頁面。」；主要證據；最強反證；未確認；Evidence trace；全站綜合；「🤖 是唯一的全站綜合頁；🌍／💼／🔍 的「本頁解釋」是同一份快照的 slice，不在此重複。」；（空）。
- ⚙️：資料限制說明；規則產生，非 AI；「缺資料會限制 AI 判讀：下列類別目前未取得，啟用 AI 後相關判讀會因此受限。」；「未取得：‹類別清單›」；「這是 deterministic 的說明句，不是 OneBrain 輸出；本頁沒有 OneBrain 位置。」；必要揭露（本頁即完整資料健康度所在）；① 全站資料取得摘要、② 逐來源／序列明細、③ 開發者診斷（預設收合）（沿用 UI-B 的新字樣，仍未核准）。
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
- 問題：🌍 💼 🔍 的位置是否定為「主內容之後、預設收合的單一 local summary 位」（而非「鏡像入口」或首屏入口）？
- 已知答案：67 §6.1 每頁至多一個 local summary 或一個鏡像入口；44 之十八其二桌機第一屏至多 1 個 AI 入口；81 層 2 現行不含它。
- 推薦：採收合位、非首屏；同批 amend 81 層 2（與 BL-0540 G-3 同一批處理）。
- 風險：放首屏會擠掉必要的 Missing／Source／Freshness；放太深可能使用者找不到。

**G3｜⚙️ 只有 deterministic 說明，與 🤖 槽位對映（BL-0560 (a)／67 §8.9／80 §16.4）**
- 問題：⚙️ 是否確認只放規則產生的「資料限制說明」、不加第 4 個 local summary；🤖 槽位四名稱如何對映 67 §8.9 四區與 80 §16.4 六項？
- 已知答案：67 §6.1 只批准 🌍／💼／🔍；`DEC-2026-11-20-02` 未授權 ⚙️ 獨立 AI local summary；對映待客戶確認（BL-0540）。
- 推薦：⚙️ 維持 deterministic；🤖 槽位對映待 Phase 7 前再議，本稿四名稱僅示意。
- 風險：若 ⚙️ 出現 OneBrain 字樣，會被讀成第 4 個 local summary（違反 67 §6.1）。

## 6. 量測（真 Chromium；playwright；DPR 1；腳本＝同夾的 `measure.py`）
**stdout 原文**（只算「目前可見」的元素；未展開的 `<details>` 內容不計；`touchTargets` ＝ `summary`、頁首五格／側欄項、輸入欄、按鈕、pill、入口列、slice pill）：
```
== viewport 390
default (all <details> closed): {'scrollWidth': 390, 'clientWidth': 390, 'fullHeight': 11601, 'minFontPx': 13, 'textNodesUnder13px': 0, 'touchTargets': 89, 'touchMinHeightPx': 48, 'touchUnder48': 0, 'chipsVisible': 63, 'chipsWithoutText': 0, 'overflowElementsOutsideDeskWrap': 0, 'deskWraps': 5, 'deskWrapScrolls': 5, 'mobFrames': 5, 'mobFrameMaxWidthPx': 358, 'mobFramesScrollingInside': 0, 'mobTopnavCells': '5,5,5,5,5', 'mobTopnavMinCellHeightPx': 60.1875, 'mobTopnavPositions': 'static', 'deskFrames': 5, 'deskTopnavHidden': True, 'mobSideHidden': True, 'obSlotsClosedByDefault': True, 'obSlots': 6}
all <details> open: {'scrollWidth': 390, 'clientWidth': 390, 'fullHeight': 13600, 'minFontPx': 13, 'textNodesUnder13px': 0, 'touchTargets': 89, 'touchMinHeightPx': 48, 'touchUnder48': 0, 'chipsVisible': 63, 'chipsWithoutText': 0, 'overflowElementsOutsideDeskWrap': 0, 'deskWraps': 5, 'deskWrapScrolls': 5, 'mobFrames': 5, 'mobFrameMaxWidthPx': 358, 'mobFramesScrollingInside': 0, 'mobTopnavCells': '5,5,5,5,5', 'mobTopnavMinCellHeightPx': 60.1875, 'mobTopnavPositions': 'static', 'deskFrames': 5, 'deskTopnavHidden': True, 'mobSideHidden': True, 'obSlotsClosedByDefault': False, 'obSlots': 6}
screenshot shot_390.png: 390x11601px, 64 colors, 317579 bytes
== viewport 1280
default (all <details> closed): {'scrollWidth': 1280, 'clientWidth': 1280, 'fullHeight': 9517, 'minFontPx': 13, 'textNodesUnder13px': 0, 'touchTargets': 89, 'touchMinHeightPx': 48, 'touchUnder48': 0, 'chipsVisible': 63, 'chipsWithoutText': 0, 'overflowElementsOutsideDeskWrap': 0, 'deskWraps': 5, 'deskWrapScrolls': 0, 'mobFrames': 5, 'mobFrameMaxWidthPx': 390, 'mobFramesScrollingInside': 0, 'mobTopnavCells': '5,5,5,5,5', 'mobTopnavMinCellHeightPx': 60.1875, 'mobTopnavPositions': 'static', 'deskFrames': 5, 'deskTopnavHidden': True, 'mobSideHidden': True, 'obSlotsClosedByDefault': True, 'obSlots': 6}
all <details> open: {'scrollWidth': 1280, 'clientWidth': 1280, 'fullHeight': 11356, 'minFontPx': 13, 'textNodesUnder13px': 0, 'touchTargets': 89, 'touchMinHeightPx': 48, 'touchUnder48': 0, 'chipsVisible': 63, 'chipsWithoutText': 0, 'overflowElementsOutsideDeskWrap': 0, 'deskWraps': 5, 'deskWrapScrolls': 0, 'mobFrames': 5, 'mobFrameMaxWidthPx': 390, 'mobFramesScrollingInside': 0, 'mobTopnavCells': '5,5,5,5,5', 'mobTopnavMinCellHeightPx': 60.1875, 'mobTopnavPositions': 'static', 'deskFrames': 5, 'deskTopnavHidden': True, 'mobSideHidden': True, 'obSlotsClosedByDefault': False, 'obSlots': 6}
screenshot shot_1280.png: 1280x9517px, 16 colors, 371779 bytes
```
**讀法**
- 文件溢出：兩個視窗、預設與「全部 `<details>` 展開」後，`scrollWidth` ＝ `clientWidth`（390／1280），`overflowElementsOutsideDeskWrap` ＝ 0。
- 桌機框：1280 視窗下 5 個桌機框都容得下（`deskWrapScrolls` ＝ 0）；390 視窗下 5 個桌機框都比視窗寬，改在自己的捲動容器內橫向捲動（`deskWrapScrolls` ＝ 5，設計如此，不計入文件溢出）。手機框在兩個視窗都不在框內溢出（`mobFramesScrollingInside` ＝ 0）。
- 最小字級：`minFontPx` ＝ 13，`textNodesUnder13px` ＝ 0（以文字節點 computed `font-size` 量測；不含 emoji／符號字型的實際字高）。
- 觸控：可見目標 89 個，最小高度 48px，`touchUnder48` ＝ 0。頁首五格與入口列在線框中是靜態示意，量測用來確認版型尺寸。
- 手機頁首五格：5 個手機框都是 5 格，`mobTopnavMinCellHeightPx` ＝ 60.19（≥ 60）；`position` 為 `static`（非 sticky／fixed）。桌機框的頁首隱藏、手機框的側欄隱藏。
- OneBrain 位置：3 頁 × 2 框共 6 個，預設全部收合（`obSlotsClosedByDefault` ＝ True）。
- 狀態標籤：每個可見 chip 都有文字（`chipsWithoutText` ＝ 0）；符號是第二重、顏色是第三重。
- 未涵蓋：Cloud／真機／WebView 未量；只量單一 Chromium 版本。

## 7. 測試輸出
指令（repo 根目錄；本 worktree；用總管指定的 scratchpad venv）：
```
python -m pytest tests/test_canonical_rule_consistency.py tests/test_doc_counters.py tests/test_constitution_file_refs.py -q -p no:cacheprovider
```
輸出原文（本 README 與其餘新檔皆已存在於工作樹後執行）：
```
........................................................................ [ 63%]
.........................................                                [100%]
113 passed in 92.20s (0:01:32)
```
本稿新增一個 `.py`（`measure.py`），另跑會掃全 repo `.py` 的守衛 `tests/test_services_purity_contract.py` 與 `tests/test_onebrain_offline_guard.py`（同 venv、同旗標）：`136 passed in 13.72s`。

## 8. NOT VERIFIED
- 客戶／使用者未核准本線框；不是 DEC、不是 amendment；字樣全為暫行。
- 本檔未經獨立複驗（單組）；§3 的衝突判斷與建議是本組讀法，可推翻。
- `DEC-2026-11-20-02` 與 GitHub #1278 comment 的原文：本組只讀 repo 內的要點轉述，未見逐字原文；該 comment 是否為使用者本人原話無法由 repo 核對。
- 本組未重新讀 `docs/v2/81`、`docs/v2/44` 全文；對 81 層 2 與 44 第一屏 AI 入口上限的引用，來自 `DEC-2026-11-20-02` 的記載與 `docs/v2/44` 該處 grep 到的一行。
- `docs/design/ui_b_settings_data_health_wireframe_2026_11_20.html`（UI-B）的版型與 token 是沿用；本組未驗 UI-B 是否已經客戶核准。
- 「全 repo 只有 `services/onebrain/` 與其測試引用 OB-B」是單組 `git grep`，未涵蓋動態 import 與非 `.py` 引用；OB-B 程式 PR 的 GitHub 狀態本組未查。
- Cloud／真機／WebView 實際畫面；瀏覽器相容性只在單一 Chromium 版本驗過。
- 截圖為調色盤 PNG（390：64 色、1280：16 色，為符合 < 400KB），非原始全彩輸出；`⬜` 在截圖中顯示為方框屬字型缺字。
- CI 狀態未查；未 push、未開 PR、未合併。
