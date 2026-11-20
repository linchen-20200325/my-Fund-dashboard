# UI-B：⚙️ 設定 → 資料健康度 可審視線框（docs-only；2026-11-20）

單組產出，未經獨立複驗；非授權、非裁示、非客戶核准；登記不構成動工授權（`CLAUDE.md` §-1）。對應 `docs/evidence/bl0540_health_centralization_gap_2026_11_20.md` 的 **B1**（⚙️ 資料健康度線框草稿）。

**基準 SHA（三個不同）**：本稿基於 origin/main `b103e99c`；引用的 `bl0540_health_centralization_gap_2026_11_20.md` 基準為 `c128a0d8`；引用的 `ui_next_batch_gap_2026_11_20.md` 基準為 `429e92c7`。兩份證據文件內的實測與全稱句（例如「基金／持倉／配息／匯率／景氣沒有可讀的健康度資料來源」「🌍 是唯一有頁內診斷的頁」）**本稿未在 `b103e99c` 上重驗**，只照錄其分類與結論。

## 0. 結論
1. 已交付一份單檔、無外部資源、**無 JS** 的靜態線框 HTML；手機 390px 單欄（頁首五格）、桌機 1280px 沿用「深色左側欄＋淺色主區」殼，依視窗寬度自動切換。
2. 三層：① 全站資料取得摘要（先講可評估範圍：8 類中只有「市場」「利率」2 類目前有可顯示的資料狀態，其餘 6 類＝未接線 4／未評估 1／待裁示 1）→ ② 逐來源／序列明細 → ③ 開發者診斷（預設收合）。另預留一格「OneBrain｜資料限制說明」，標「尚未啟用」，內容只有規則產生的限制句。
3. 三個示意情境（CSS radio 切換，皆標 `示意（FAKE）`）：A 五序列皆取得（**最佳情況示意，不代表常態**）、**B 部分缺漏與失敗（預設顯示，截圖亦為 B）**、C 本次尚未載入。C 的計數全為「—」，用來示範「真 0」與「Missing」的區別。
4. **僅限情境 A–C 的畫面**：沒有任何類別被顯示為「已取得」「正常」或綠色；附註 A 的「已取得」只是字樣定義（且「已取得」單獨作為類別層狀態是新用法）。日期一律用 `‹YYYY-MM-DD›` 佔位格式，不使用像真資料的數字。
5. 不一致處已標明：市場頁揭露對照 15 項中有 3 項（#8、#11、#14）兩份證據說法不同，見 §3。

## 1. 檔案
| 路徑 | 說明 |
|---|---|
| `docs/design/ui_b_settings_data_health_wireframe_2026_11_20.html` | 線框本體（單檔；內嵌 CSS；無外部資源；無 JS；收合用原生 `<details>`；情境切換用 radio＋CSS） |
| `docs/evidence/ui_b_settings_health_wireframe_2026_11_20/shot_390.png`、`shot_1280.png` | Chromium 截圖，視窗 390／1280、DPR 1 |
| `docs/evidence/ui_b_settings_health_wireframe_2026_11_20/measure.py` | 量測＋截圖腳本（可重現；§7 的輸出原文即它的 stdout） |
| 本 README | 說明、對照表、PendingWording、最小 Gate、量測、測試輸出 |

**截圖範圍**：預設情境 **B**；範圍＝「文件頭＋App 框」（390 寬 5,178px 高、1280 寬 2,413px 高），**不是首屏**，也不含附註 A–E。整頁在 390 寬約 14,650px，單檔 1.5MB 以上、超過 400KB 上限，故只截此區段；存檔時以 Pillow 轉 128 色調色盤 PNG（無抖色）以符合 < 400KB，非原始全彩輸出。附註請直接開 HTML 看。重現：`UI_V2_CHROMIUM=<chromium 路徑> python docs/evidence/ui_b_settings_health_wireframe_2026_11_20/measure.py`（需 playwright 與 Pillow）。

## 2. 線框內容摘要（如實性要點）
- **色票／字級／間距**：全部取自 `ui_v3/design/tokens.py` 的核准值（page `#f5f7fb`、surface `#ffffff`、primary `#1a5fd0`、側欄 `#101a33` 等；tone 的 neutral／grey／yellow／red；字級 body 15／caption 13；card 圓角 8、內距 10×12；chip 圓角 12）。**沒有新造色票**。文件層註解（圖釘、虛線框）只用 primary／border／surface。
- **導覽殼**：手機＝頁首五格（🌍 市場／💼 資產／🔍 找基金／🤖 AI／⚙️ 設定；未掛載項標「開發中」，🤖 標「尚未開放」，皆已核准字樣）；桌機＝深色側欄。⚙️ 以「掛載後」狀態示意；現況 registry `set` 仍是 `wireframe_not_approved`。
- **字級偏離（刻意）**：現行 `ui_v3/shell/nav.py` 的頁首導覽格與 Status Bar 用 12px／10px；本線框為符合「最小字級 ≥ 13px」（與 R1 方向一致）一律 ≥ 13px。這**不是**對現行實作的修改建議，只是線框量測基準。
- **Status Bar 的「5／5 項已取得」**：照現行字樣示意，並以圖釘 N1 標明分母＝🌍 五序列、⚙️ ① 不沿用為全站結論（bl0540 R4）。
- **freshness**：`freshness_state` 現恆為 `undetermined`（stale_after 待 Threshold Gate）。新鮮度欄只出現「⬜ 門檻待裁示」（有資料）或「⬜ 無法判定」（無資料）。① 的新鮮度列拆成「範圍內五序列」與「其餘類別（⬜ 無法判定）」，不用「全站」一詞，也不暗示只差門檻；情境 C 的五序列也是「⬜ 無法判定」（沒有資料就無從談門檻）。
- **類別層對映（依證據文件 §2；皆為本線框讀法，單組未驗）**：市場＝部分（3 序列＋7 項無來源）；利率＝部分（美10Y／美2Y 在五序列內；利差／信用／政策利率三子序列＝**未評估**，因為 adapter 可讀但未入 ViewModel，本頁尚未判定）；基金、NAV、配息、景氣＝未接線；持倉＝未評估（`ui_v3/adapters/assets_source.py` 有轉接層但無 production 呼叫端）；FX＝待裁示（`FX_OBS_DATE_RULE_VERIFIED=False`、FX Gate 關閉）。
- **語言層級**：一般層（① ②）只用使用者語言（例：「目前沒有可顯示的來源」「資料來源尚待建立」「本頁尚未判定這個序列」）；「轉接層」「沒有 producer」「來源尚未進入 ViewModel」等實作視角措辭**只出現在 ③ 開發者診斷**（及本 README）。
- **③ 開發者診斷**：預設收合；欄位限來源標籤、取得路徑、結果類別、冷卻、必要狀態；範例 FAKE 列**隨示意情境改變**（A 全成功、B 含逾時與空資料、C 全為「—（尚未嘗試）」）；不顯示 secrets、內部例外、環境變數名、網址或帳密（沿用 `NasDiagObservation` 建構時拒絕 `://`、`user:pass@`、非白名單字元的慣例）。NAS 診斷只作單一區塊參考，標 FAKE-only，不冒充跨全站健康。
- **OneBrain 位置**：只預留一格，標「尚未啟用」；內容僅「哪些類別未取得，因此 AI 分析將受限」的規則句；**不含任何 AI 文字**；不是 ⚙️ 獨立 AI local summary（67 §6.1 只批准 🌍／💼／🔍；BL-0560 (a)）。
- **入口位置（附註 C）**：在 🌍／💼／🔍 三種內容頁示意「查看完整資料健康度」位置（💼🔍 為未掛載頁，僅位置示意）；並明寫「掛載前不應出現」（死入口風險，bl0540 §3）。

## 3. 市場頁（🌍）必要揭露對照
分類沿用 `bl0540_health_centralization_gap_2026_11_20` §1（必／集／裁）；「本線框讀法」為【R】建議、可推翻；「兩處皆留」是本線框的設計讀法（⚙️ ② 有對應欄位），不是證據文件的分類。**BL-0540 規格 Gate 完成前，🌍 原有清單一項都不刪。** ui_next ＝ `docs/evidence/ui_next_batch_gap_2026_11_20.md`。

| # | 現有揭露 | 位置 | 本線框讀法 | 證據分類 | 出處／不一致 |
|---|---|---|---|---|---|
| 1 | Shell Status Bar（PREVIEW＋資料狀態一句＋更新時間） | 全頁頂端 | **保留在頁內（Shell）** | 必 | bl0540 §1 #1；80 §17.2；79 §7.1；分母是 🌍 五序列，不是全站；⚙️ ① 不沿用該句當全站結論（bl0540 R4、80 §17.4）。 |
| 2 | 側欄「資料狀態 n／5 項已取得」＋最後更新時間 | 桌機側欄 | **保留在頁內（Shell）** | 必 | bl0540 §1 #2；80 §17.2／§17.4；同 #1。時間是取得時間，不是資料日（79 §7.1）。 |
| 3 | 首屏「資料新鮮度 ⬜ 門檻待裁示」chip | 🌍 首屏 | **兩處皆留（頁內 chip 不動；⚙️ ② 新鮮度欄顯示同一字樣）** | 必 | bl0540 §1 #3；81 §3.1 Q5 B；DEC-2026-11-03-09；「兩處皆留」是本線框的設計讀法【R】，不是證據文件的分類（證據只分 必／集／裁）。 |
| 4 | 圖下基準日／頻率／缺值不補（Chart SPEC 子集） | 圖卡下方 | **保留在頁內** | 必 | bl0540 §1 #4；80 §16.1；79 §4.4 |
| 5 | 圖下各序列資料日＋經過天數 | 圖卡下方 | **兩處皆留（頁內是日期唯一落點；⚙️ ② 資料日欄為逐列明細）** | 必 | bl0540 §1 #5；81 §3.1 日期表；「兩處皆留」為本線框讀法【R】。 |
| 6 | 圖下非 ok 序列一行摘要＋缺值短因（缺資料／取數失敗／尚未設定） | 圖卡下方 | **兩處皆留（頁內摘要；⚙️ ② 原因欄逐列）** | 必 | bl0540 §1 #6；81 §4.1 S2–S9；44 之十九其五.2、§5.4；44 對 New UI2 是否仍拘束＝bl0540 Q1（待裁示）；「兩處皆留」為本線框讀法【R】。 |
| 7 | 圖卡 `▸ 來源與限制`：來源名＋限制句 | Primary 圖卡內 | **保留在頁內** | 必（來源名／限制句） | bl0540 §1 #7；81 §3.3 層3；44 之十九其四.4 |
| 8 | 圖卡 `▸ 來源與限制`：取得時間 | Primary 圖卡內 | **待移至 ⚙️（需 BL-0540 G-3／81 amendment）** | 裁（可集中） | bl0540 §1 #7；【不一致】ui_next §2a 把整個 `▸ 來源與限制` 列為「必須留在 🌍」；bl0540 §1 #7 把取得時間分出為「裁」。本線框採較細的 bl0540 分法；若採 ui_next 讀法，此項改為「兩處皆留」。 |
| 9 | Secondary 卡（值＋資料日＋迷你線；`SecondaryCard.source` 有值但不渲染） | 次要卡片 | **保留在頁內** | 必 | bl0540 §1 #8；81 §3.1；來源缺口見 #11。 |
| 10 | 依據卡 MKT-1～3（觀測值＋as_of 或 ◇） | 依據區 | **保留在頁內** | 必 | bl0540 §1 #9；81 §4；D4 |
| 11 | VIX 來源 `Yahoo:^VIX`（目前只出現在 `▸ 各項資料狀態`） | 狀態展開區 | **搬走 #13 之前，必須先把來源補進 VIX 卡的 `▸ 來源與限制`（新增元素＝B 類；端態＝兩處皆留）** | 必（來源揭露） | bl0540 §0 第 3 點、§5 R1、Q2；【不一致（證據強度）】bl0540 為【F】（以測試替身資料實跑頁面純函式）；ui_next §2a 為【I】（讀碼推論、未驗）。真實 runtime／Cloud＝NOT VERIFIED。 |
| 12 | 利率卡三個 FRED 來源（`FRED (T10Y2Y)`／`FRED (BAMLH0A0HYM2)`／`FRED (FEDFUNDS)`） | 整頁文字 0 命中 | **現況本來就不在頁內；是否補列＝待裁示（Q2）。⚙️ ② 先以「未接線」列出** | 裁 | bl0540 §5 R1／R2、Q2；81 §4；81 §4 對利率卡只要求「觀測日沿用現況說明」，不是違規（R2）。美10Y／美2Y 的來源與資料日也只在 #13，且比較檢視不畫它們（R1 限定）。 |
| 13 | `▸ 各項資料狀態` 逐列明細（5 列：取得／來源／資料日，或失敗狀態） | 圖卡下展開區 | **待移至 ⚙️（需 BL-0540 G-3／81 amendment）** | 裁（G-3 核心） | bl0540 §1 #11；81 §3.3 層2、MV-02；80 §16.2；DEC-2026-11-20-02；搬動前提：⚙️ 線框核准＋實作＋掛載，與入口同批同 PR（bl0540 R7、Q3）。MV-02 已裁示，現行 81 保留此區，故須 amendment。 |
| 14 | `▸ 尚未取得（N 項）` 名單（7 項，恆 ◇ 資料未備） | 頁底收合群組 | **兩處皆留（頁內名單一項不刪；⚙️ ② 另列逐項狀態）** | 必 | bl0540 §1 #10；81 §4 D4＝β；80 §7.1；67 §5.4；【不一致】bl0540 §0 第 2 點與 ui_next §2a 稱必要揭露、必須留；bl0540 §1 #10 又寫「名單本身待 Q2」。本線框採「名單一項不刪」。 |
| 15 | 更新資料 CTA（目前不可用） | Shell | **待 ⚙️ 線框一併裁定；本線框不放任何 CTA** | 裁 | bl0540 §1 #12；80 §17.3；位置未定；本線框不暗示任何可操作動作。 |

## 4. 內部狀態 → 畫面字樣
| 內部狀態 | 畫面字樣 | 字樣狀態 |
|---|---|---|
| OK | 取得 | 暫行（既有預覽字樣；規則表 `ok` 刻意不寫「正常／資料齊」） |
| Missing | ◇ 資料未備 | 已核准 |
| failed | ⛔ 取數失敗（設定未設時為 ⛔ 尚未設定） | 已核准 |
| skipped | 本線框 v1 不出現（💼 A60 有「略過」字樣，僅 FAKE-only 預覽） | 暫行 |
| unjudged | ⬜ 無法判定／⬜ 門檻待裁示 | 已核准 |
| 類別層：已取得／部分／失敗／未取得／未接線／未評估／待裁示 | 見 §5-A | **全部待客戶定字** |

## 5. PendingWording 清單（HTML 內所有新字樣；未經核准，不得寫成已核准）
「新」＝本線框新增；「既有」＝repo 內已存在的 PendingWording（仍未核准）；「已核准」＝`APPROVED_WORDING`／規則表已有。

**A. 類別層狀態詞（新）**：已取得、◐ 部分（符號 ◐ 亦待定）、⛔ 失敗、⬜ 未取得、◇ 未接線、⬜ 未評估、⬜ 待裁示、⬜ 尚未啟用（OneBrain 位）。
- 「已取得」一詞在 `shell_status_counts`（「n／m 項已取得」）已核准，但**單獨作為類別層狀態詞是新用法**。
- ⚠️ 「未取得」與 🌍 既有「尚未取得（N 項）」（＝無正式來源）**同字異義**，需定字區分。
- ⚠️ 張力（`PROJECT_RULES.md` 13.5：工程資訊不進一般 UI）：「未接線」是工程詞；一般層已改用使用者語言描述原因，但狀態詞本身仍是工程詞。③ 內的「轉接層」「producer」「ViewModel」是工程詞（只在 ③，開發者層）；若 Q4 裁示 ③ 不得出現內部詞，須再改。
- 「FX」與 80 §16.2 的「匯率」用詞不一致，待定。

**B. 頁名、區塊標題、類別名（新）**：資料健康度；① 全站資料取得摘要；② 逐來源／序列明細；③ 開發者診斷；（預設收合）；OneBrain｜資料限制說明；查看完整資料健康度（入口字樣，另需核准）；尚無正式來源（7 項）；其他類別；（尚無來源可列；逐類狀態見 ①）；類別名 基金、NAV、持倉、配息、FX、景氣（「市場」「資產」等導覽短名已核准，但作為類別名是新用法）；7 項無來源的項目名沿用 81 的名稱。

**C. ① 摘要與說明句（新）**：
- 可評估範圍句：「8 類中，只有「市場」「利率」2 類目前有可顯示的資料狀態；其餘 6 類：未接線 4、未評估 1、待裁示 1。」
- 「這不是全站健康結論。「取得」不代表資料可用，也不代表資料齊全。」
- 「範圍內五序列結果（🌍 市場頁的五條序列；不是全站）」；計數格標籤 取得／缺漏／失敗；計數註 「項」「真的 0 項」「尚未載入，無從計數（不是 0）」。
- 「另 7 項尚無正式來源」；新鮮度列：「新鮮度」「範圍內五序列」「其餘類別」。
- 類別磚說明句：「3 序列已取得；另 7 項尚無來源」「1 取得、1 缺資料、1 失敗；另 7 項尚無來源」「3 序列尚未載入；另 7 項尚無來源」「美10Y／美2Y 已取得；另 3 條序列本頁尚未判定」「美10Y／美2Y 尚未載入；另 3 條序列本頁尚未判定」「目前沒有可顯示的來源」「目前沒有可顯示的取得紀錄」「有資料入口，本頁尚未判定」「資料來源尚待建立」「判定規則待客戶裁示」。
- OneBrain 限制句：「尚無 AI 分析。啟用後，下列類別未取得，AI 分析會因此受限：…。部分取得：…。」與「由上方類別狀態逐項列出（規則產生，非 AI 文字）。位置預留，內容不含任何 AI 分析。」
- 「本頁不提供「更新資料」操作；位置待裁」（「更新資料」「預覽版尚未開放更新資料」本身已核准；此句是線框說明）。

**D. ② 明細（新）**：欄位名 來源、資料日、取得時間、新鮮度、狀態、缺漏／失敗原因（「資料日」在 `data_date_line` 已核准、「取得時間」「來源」在 `fetched_at_line`／`source_line` 為既有 PendingWording，作為欄名是新用法）；「「—」＝沒有值（Missing），不是 0，也不是正常。」；原因短語：本頁尚未判定這個序列、目前沒有可顯示的來源、目前沒有可顯示的取得紀錄、本頁尚未判定、資料來源尚待建立、判定規則待客戶裁示、尚無正式來源、本工作階段尚未載入（已核准並沿用：「沒有觀測值」「來源資料無法使用」）。

**E. ③ 開發者診斷（新，除標註者外）**：「只顯示經遮蔽的分類碼與來源標籤；不顯示環境變數名、網址、帳密或例外全文。欄位範圍待裁示。」；「示意（FAKE）：下列範例只示範欄位，並隨上方示意情境改變…」（線框說明）；欄位名 來源標籤、取得路徑、結果類別、冷卻、必要狀態；欄位值 直連、經 NAS 中繼、無、—（尚未嘗試）、成功、逾時（歸屬未判定）、空資料、否；小標「類別層的工程原因（只在這一層出現）」與四條工程原因（尚無可讀的狀態來源（沒有 producer）／轉接層存在，但尚未被正式呼叫／來源尚未進入 ViewModel／匯率觀測日規則未驗證；規則待裁示）；「NAS 中繼診斷」；「兩軸分開呈現：NAS 中繼檢查結果、目標網站本次回應。」；「◌ 尚未測試」＝**既有** PendingWording（`ui_v3/viewmodels/nas_diag_wording.py`，BL-0550）；NAS 診斷區塊本身沿用既有預覽，字樣皆既有 PendingWording。

**F. 僅線框用、不進產品**：示意情境標籤（A 五序列皆取得／B 部分缺漏／失敗／C 本次尚未載入）、「示意（FAKE）」、圖釘 N1–N7、附註 A–E 全文、框外說明句。

**已核准、本線框直接沿用**：◇ 資料未備、⬜ 無法判定、⛔ 取數失敗、⛔ 尚未設定、⬜ 門檻待裁示、開發中、尚未開放、PREVIEW、基金投資儀表板、市場／資產／找基金／AI／設定、資料狀態、最後更新時間、「n／m 項已取得」、「部分資料未取得（…）」、「其中 N 項取數失敗」、「更新：{時間}」、「沒有觀測值」「來源資料無法使用」。

## 6. 最小 Gate（≤ 3 項；總管決定是否向使用者提問）
**G1｜搬遷承接（BL-0540 G-3＋Q1／Q2／Q3）**
- 問題：是否把 🌍 `▸ 各項資料狀態` 逐列明細（與取得時間）搬到 ⚙️，並同批把 VIX 與利差三子序列的來源補進卡的 `▸ 來源與限制`？
- 已知答案：80 §16.2「主頁只留 freshness／source 摘要」，未逐項點名；總管推薦各頁 wireframe 承接、44 與 72／73／78／65 標 successor 不解凍，涉資料語意才走 G-44 amendment。
- 推薦：本線框核准後，⚙️ 掛載（registry＋renderer＋守衛）＋#13 搬遷＋入口＋VIX／利差來源補進卡，**同批同 PR**，附逐項去向的資訊無損對照表（§3）；44 不解凍。
- 風險：先搬後掛＝使用者同時失去頁內明細且無處可看（R7）；先放入口＝死入口；不補來源＝VIX 卡失去唯一的頁面來源標示（bl0540 R1，【F】僅替身資料實跑；ui_next 為【I】）。

**G2｜⚙️ 第一版範圍與新狀態詞（Q5＋字樣核准）**
- 問題：第一版是否只做 in-session 的 🌍 五序列＋三子序列＋NAS 診斷，其餘類別顯示「未接線／未評估／待裁示」；並核准（或改定）頁名、區塊標題、類別層狀態詞與入口字樣？
- 已知答案：83 的獨立監控 Sheet 是候選、未核准；80 §16.2 要求涵蓋所有正式資料類別；§5 所列新字樣在 `APPROVED_WORDING` 皆 0 命中。
- 推薦：是；全部維持 PendingWording，由客戶逐項定字；不等 83 的 Sheet。
- 風險：使用者預期「涵蓋所有類別」卻看到 6／8 類無內容；「未接線」「未取得」的字義與工程詞問題（§5-A）。

**G3｜③ 層欄位範圍與 OneBrain 說明位（Q4＋BL-0560 (a)）**
- 問題：③ 可顯示哪些欄位；⚙️ 的「OneBrain｜資料限制說明」可見版是否允許？
- 已知答案：`PROJECT_RULES.md` 13.5 第 3 點只說「開發者診斷層預設收合」；67 §6.1 只批准 🌍／💼／🔍 每頁至多一個 local summary；ui_next Q2 推薦先只預留、不渲染。
- 推薦：③ 只放經遮蔽的分類碼／來源標籤／HTTP 結果類別，預設收合；OneBrain 位置先只預留（DOM 無元素），可見版僅供本線框審視，待契約差額 Gate 後再議。
- 風險：欄位過寬即洩漏；可見版若上線＝⚙️ 獨立 AI 說明，違反 67 §6.1。

## 7. 量測（真 Chromium；playwright；DPR 1；腳本＝同夾的 `measure.py`）
**stdout 原文**（只算「目前可見」的元素；`chipsVisible` 含附註區的 chip；`detailsVisible` 只算目前可見情境內的 `<details>`，隱藏的另兩個情境不計；`touchTargets` ＝ `summary`、情境切換 label、頁首導覽格／桌機側欄項、入口列）：
```
== viewport 390 (default scenario radio: sc-b)
scenario a: {'scrollWidth': 390, 'clientWidth': 390, 'fullHeight': 14657, 'minFontPx': 13, 'textNodesUnder13px': 0, 'touchTargets': 14, 'touchMinHeightPx': 48, 'touchUnder48': 0, 'detailsVisible': 2, 'detailsOpenVisible': 0, 'chipsVisible': 72, 'chipsWithoutText': 0, 'overflowElements': 0, 'sideDisplay': 'none', 'topnavDisplay': 'grid'}
scenario b: {'scrollWidth': 390, 'clientWidth': 390, 'fullHeight': 14673, 'minFontPx': 13, 'textNodesUnder13px': 0, 'touchTargets': 14, 'touchMinHeightPx': 48, 'touchUnder48': 0, 'detailsVisible': 2, 'detailsOpenVisible': 0, 'chipsVisible': 72, 'chipsWithoutText': 0, 'overflowElements': 0, 'sideDisplay': 'none', 'topnavDisplay': 'grid'}
scenario c: {'scrollWidth': 390, 'clientWidth': 390, 'fullHeight': 14652, 'minFontPx': 13, 'textNodesUnder13px': 0, 'touchTargets': 14, 'touchMinHeightPx': 48, 'touchUnder48': 0, 'detailsVisible': 2, 'detailsOpenVisible': 0, 'chipsVisible': 72, 'chipsWithoutText': 0, 'overflowElements': 0, 'sideDisplay': 'none', 'topnavDisplay': 'grid'}
scenario b, all <details> open: {'scrollWidth': 390, 'clientWidth': 390, 'fullHeight': 16880, 'minFontPx': 13, 'textNodesUnder13px': 0, 'touchTargets': 14, 'touchMinHeightPx': 48, 'touchUnder48': 0, 'detailsVisible': 2, 'detailsOpenVisible': 2, 'chipsVisible': 72, 'chipsWithoutText': 0, 'overflowElements': 0, 'sideDisplay': 'none', 'topnavDisplay': 'grid'}
screenshot shot_390.png: 390x5178px, 172003 bytes
== viewport 1280 (default scenario radio: sc-b)
scenario a: {'scrollWidth': 1280, 'clientWidth': 1280, 'fullHeight': 6583, 'minFontPx': 13, 'textNodesUnder13px': 0, 'touchTargets': 14, 'touchMinHeightPx': 48, 'touchUnder48': 0, 'detailsVisible': 2, 'detailsOpenVisible': 0, 'chipsVisible': 72, 'chipsWithoutText': 0, 'overflowElements': 0, 'sideDisplay': 'block', 'topnavDisplay': 'none'}
scenario b: {'scrollWidth': 1280, 'clientWidth': 1280, 'fullHeight': 6577, 'minFontPx': 13, 'textNodesUnder13px': 0, 'touchTargets': 14, 'touchMinHeightPx': 48, 'touchUnder48': 0, 'detailsVisible': 2, 'detailsOpenVisible': 0, 'chipsVisible': 72, 'chipsWithoutText': 0, 'overflowElements': 0, 'sideDisplay': 'block', 'topnavDisplay': 'none'}
scenario c: {'scrollWidth': 1280, 'clientWidth': 1280, 'fullHeight': 6571, 'minFontPx': 13, 'textNodesUnder13px': 0, 'touchTargets': 14, 'touchMinHeightPx': 48, 'touchUnder48': 0, 'detailsVisible': 2, 'detailsOpenVisible': 0, 'chipsVisible': 72, 'chipsWithoutText': 0, 'overflowElements': 0, 'sideDisplay': 'block', 'topnavDisplay': 'none'}
scenario b, all <details> open: {'scrollWidth': 1280, 'clientWidth': 1280, 'fullHeight': 7381, 'minFontPx': 13, 'textNodesUnder13px': 0, 'touchTargets': 14, 'touchMinHeightPx': 48, 'touchUnder48': 0, 'detailsVisible': 2, 'detailsOpenVisible': 2, 'chipsVisible': 72, 'chipsWithoutText': 0, 'overflowElements': 0, 'sideDisplay': 'block', 'topnavDisplay': 'none'}
screenshot shot_1280.png: 1280x2413px, 163539 bytes
```
**讀法**
- 溢出：兩個視窗、A／B／C 與「全部 `<details>` 展開」後，`scrollWidth` ＝ `clientWidth`（390／1280），`overflowElements` ＝ 0。
- 最小字級：`minFontPx` ＝ 13，`textNodesUnder13px` ＝ 0（以文字節點 computed `font-size` 量測，不含 emoji／符號字型實際字高）。
- 觸控：可見目標 14 個，最小高度 48px，`touchUnder48` ＝ 0；頁首導覽格與入口列在線框中是靜態示意，量測用來確認版型尺寸。
- 預設收合：每個情境可見的 2 個 `<details>`（「尚無正式來源（7 項）」與 ③）`detailsOpenVisible` ＝ 0；整檔 HTML 共 6 個 `<details>`（A／B／C 各 2，含隱藏情境），目前可見的只有 2 個，兩者不要混為一談。
- 狀態標籤：每個可見 chip 都有文字（`chipsWithoutText` ＝ 0）；符號是第二重、顏色是第三重。
- 導覽：390 時側欄 `display:none`、頁首五格 `grid`；1280 時反之。
- 未涵蓋：Cloud／真機／WebView 未量。

## 8. 測試輸出
指令（repo 根目錄；本 worktree）：
```
python -m pytest tests/test_canonical_rule_consistency.py tests/test_doc_counters.py tests/test_constitution_file_refs.py -q -p no:cacheprovider
```
輸出原文（本 README 與其餘新檔皆已存在於工作樹後執行）：
```
........................................................................ [ 63%]
.........................................                                [100%]
113 passed in 86.40s (0:01:26)
```
`tests/test_doc_counters.py` 的受檢語料依讀碼為 `docs/v2/`（`DOCS_DIR`）內的檔案，不含 `docs/design/` 與 `docs/evidence/`；上列全綠，故 HTML 維持在 `docs/design/`，未改放 `docs/evidence/`。

## 9. NOT VERIFIED
- 客戶／使用者未核准本線框；不是 DEC、不是 amendment；字樣全為暫行。
- 本檔未經獨立複驗（單組）；§3 的「本線框讀法」與 §2 的類別層對映是本組讀法，可推翻。
- 類別層對映引自 `bl0540`（基準 `c128a0d8`）§2 與 `ui_next`（基準 `429e92c7`）§2；本組未在 `b103e99c` 重跑其實測，也未重新讀 `ui_v3` 各檔驗證其全稱句。
- Cloud／真機／WebView 實際畫面；真實資料下各類別的狀態；`infra/proxy.py` 能否產出 ③ 的欄位。
- 瀏覽器相容性只在單一 Chromium 版本驗過；情境切換為 radio＋兄弟選擇器（無 JS），未在其他瀏覽器驗。
- 截圖為 128 色調色盤 PNG（為符合 < 400KB），範圍為文件頭＋App 框（情境 B），非首屏、非原始全彩輸出。
- CI 狀態未查；未 push、未開 PR、未合併。
