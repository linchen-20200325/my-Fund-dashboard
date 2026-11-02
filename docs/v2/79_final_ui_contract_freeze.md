# 79｜Final UI／Decision System Contract Freeze（提案；⛔ 待客戶裁示）

- **定位**：**Proposal／Decision Gate／Migration Contract。不是規格、不是第二套 UI 或 AI 憲法、不是動工授權。** 本檔把客戶 2026-11-02 要求凍結的「最終 UI 與決策系統契約」整理成一份可一次裁示的提案：現況、提案條文、遷移地圖與 Gate。本檔寫下的任何「提案」在客戶裁示前不生效；裁示後也不以本檔為正式條文住址（見下方落盤策略）。
- **位階**：不凌駕 `CLAUDE.md`、`PROJECT_RULES.md`、`docs/v2/44_fund_ui_ssot.md`（frozen）、`docs/v2/67_ai_action_vocabulary.md`、`docs/v2/75_onebrain_ai_architecture.md` 與 `docs/DECISIONS.md` 的正式裁示；衝突一律以它們為準。本檔的提案若與它們牴觸，視為本檔寫錯，不視為對它們的修改。
- **客戶核准後的落盤策略（`PROJECT_RULES.md` 13.4 第 7 條：文件不重複 SSOT）**：正式規則回寫既有 canonical SSOT —— 裁示登記 `docs/DECISIONS.md`；未完成工作進 `docs/BACKLOG.md`（優先掛既有列，不碎片化）；現況與接手點進 `docs/HANDOFF.md`；AI／Decision 語意以 `docs/v2/67` 增節承接；只有在第一個實作批真的與 44 條文衝突時，才開 44 新一輪 amendment（同 `DEC-2026-11-01-02` G-E5 模式）。本檔核准後只保留三樣：rationale、migration map、visual contract rationale；不再作為任何條文的引用來源。
- **量測基準**：**程式事實以 main `20bf6442` 為準；`DEC-2026-11-01-02` 見 #1117（Batch E Gate 落盤）——#1117 已 squash 合併，main＝`52da0cab`（~~Draft~~，分支 `815fb88e` 為合併前的落盤 commit；狀態更新，不是漏刪）；`52da0cab` 與 `20bf6442` 在 `ui_v2/`、`services/`、`shared/` 三處無差異（兩點 diff 確認），故程式事實不變。** 本檔撰寫時的本機工作樹是 #1117 較早的 `0d2e05f3`，該 commit 與 `20bf6442` 在 `ui_v2/`、`services/`、`shared/` 三處無差異（本組以兩點 diff 確認）。程式位置寫「檔案::符號」，不寫行號。
- **現況的來源（據實揭露）**：本檔第 1、9、12 節的「現況」大多來自兩組**單組唯讀盤點**（程式現況組、SSOT 現況組），由總管轉述給本組，**未經第二組複驗**。本組在 1 分鐘內能重驗的承重事實已重驗並改標【F-重驗】；其餘標【F-轉述】。重驗清單見第 16 節。
- **客戶指示來源**：客戶 2026-11-02「Final UI／Decision System Contract Freeze」任務（對話中）；與本檔相關的段落已由總管逐字摘錄存於 `docs/evidence/decisions/2026-11-02_final_ui_contract_freeze_assignment.md`（`DEC-2026-11-02-01`）。本檔引用其中兩處，以該逐字摘錄為準：「第 30 節」（「找基金 Primary Visual 建議：Normalized NAV，Base = 100」）與「第 48 節」（缺資料時用 `◇ 資料未備`、不新造另一套詞）。
- **BACKLOG 追蹤**：BL-0531（Gate 子項）、BL-0532（Missing 統一）。
- **建立日**：2026-11-02。**編號**：78 為 Batch E 線框，本檔取 79。
- **修訂紀錄**：2026-11-02 獨立稽核提出 4 個 blocker（B1 情境線引用錯誤、B2 歸一化基準值與 Step 4 自相矛盾、B3 Risk Cap 可做行為越權、B4 🌍 依據列違反 D7 順序）與數項必修；總管抽驗 B1、B2 屬實；本輪逐項修正（本檔尚未合併，直接改正文）。
- **產出者聲明**：文件組單組產出，未經獨立複驗（`CLAUDE.md` §-2 規則 6）。本檔屬治理／data semantics／AI decision semantics 等級，依 `DEC-2026-10-16-05` 與 `PROJECT_RULES.md` 13.4 第 1 條，正式回寫前至少要 1 組真正獨立稽核。

## 0. 標記法

| 記法 | 意思 |
|---|---|
| 【F-重驗】 | 本組這一輪自己讀檔或搜尋重驗過（見第 16 節） |
| 【F-轉述】 | 來自兩組單組盤點，經總管轉述，本組未重驗 |
| 【I】 | 推論，可推翻 |
| 【P】 | 提案，待客戶裁示；每項另註「依據既有條文」或「新定義，需裁示」 |
| Illustrative Only | 示意數字或詞彙，**非正式規則**；不得被實作批當成門檻或詞表 |
| 符號 | 只用 44 已落字的 ◆ ◇ ⬜ ⛔ ◷；本檔不新增狀態詞或符號 |
| 「擬：」 | 本檔新擬的畫面字樣，屬客戶定字範圍（`ui_v2/shell_nav.py` 檔頭），待客戶定字 |

---

## 1. 現況成熟度（五頁）

| 頁 | 已完成 production | 已定義未實作 | 未定義 |
|---|---|---|---|
| 🌍 市場與趨勢 | Batch C（`DEC-2026-10-30-01`）：頁首資料狀態 chip＋一句「暫無完整市場綜合判定（缺正式 aggregation rule）」；Primary 單序列切換；Secondary 3 張迷你圖；Missing、各項資料狀態、`MKT-1`～`MKT-7` 下沉【F-轉述；一句與預設值 F-重驗】 | 依據卡的 local explanation；新鮮度門檻（目前「⬜ 門檻待裁示」） | 市場綜合判定 aggregation rule；regime；圖上任何 threshold／band |
| 💼 我的資產 | Batch D＋P3 頁級狀態容器（β 階梯）＋Layout A（`DEC-2026-10-30-02`、`-04`、`DEC-2026-10-31-01`、`-02`）【F-轉述】 | 合併頁層 3／層 4 超上限的收斂（44 之二十其二第 5 條） | Risk Cap；再平衡政策；任何行動語意；drawdown／risk 正式資料契約 |
| 🔍 找基金 | 選股池篩選器 `EXP-0`～`EXP-7`【F-轉述】 | Batch E：MoneyDJ code 主入口、ISIN「尚未啟用」、session-only 比較（`DEC-2026-11-01-01`、`-02`；`docs/v2/78`） | ISIN 對照來源（BL-0530 research）；排名模型（BL-0511，維持不做） |
| 🤖 AI 投資總結 | **無**：導覽未掛、零實作【F-重驗：`ui_v2/app_preview.py::PAGES` 無此頁】 | IA 與輸出格式（`DEC-2026-10-29-07`、67 第 6.1 節）；Phase 7 才掛導覽 | Decision Digest production、OneBrain runtime、句子→依據對映（`AI-3`） |
| ⚙️ 設定 | `SET-0`、帳號、Sheet picker、`SET-1`、`SET-2`、`SET-3`（唯讀）、`SET-8`、`SET-5`～`SET-7`、進階診斷【F-轉述】 | 低頻全域化（44 之二十其三第 5 條） | Rule Registry；Digest Viewer；audit 檢視 |

【F-重驗】`ui_v2/app_preview.py::PAGES` 只有四列：`mkt` 🌍 市場與趨勢、`ast` 💼 我的資產、`exp` 🔍 找基金、`set` ⚙️ 設定。`ui_v2/shell.py` 的 docstring 寫「畫側欄五項與底部導覽五項」，與 PAGES 四項不一致，屬文件措辭問題（見第 15 節）。

---

## 2. 五條鐵則（提案）

> 本節是提案的核心。五條都不是全新的價值觀；多數是把散在 67／58／75／DEC 的既有條文收成一句可引用的名字，另補少量新定義。下表逐條拆開「既有依據」與「本提案新增」。

| 鐵則 | 一句話 | 既有依據 | 本提案新增 | 建議落點 | 碰 Gate？ |
|---|---|---|---|---|---|
| **C-1 Single Action Authority** | 唯一的動作權威＝Deterministic Rules＋Risk Cap 產出的 System Action State；OneBrain 不另發 action | 67 第 1 節固定鏈、第 2.7 節「AI 覆寫 deterministic rule」禁止、第 3.3 節；`DEC-2026-10-27-14` 固定鏈與七項禁止；`DEC-2026-10-27-40`；75 第 11 節 | 「System Action State」這個具名中介物（第 6 節）；「OneBrain 只能引用、不能產生 action」的明文 | 67 新增一節（例：第 8 節） | 是（新定義，需裁示） |
| **C-2 No Uncalibrated Probability** | 沒有 calibration contract 前，畫面與 AI 輸出禁止任何 % 機率、信心值；LLM 不得自估機率 | 58 U-25 禁「信心 n%」「綜合分數」「星等」；67 第 5.3 節 confidence「不納入」；75 第 10 節「confidence 若未有正式定義，不能上 production」；`DEC-2026-10-27-33` 禁 AI score | calibration contract 的最低構成：historical labels、prediction target、backtest、calibration、reliability curve 或同等、Brier score 或同等、versioning；七項缺一即不得出現機率；**只適用於機率／信心類輸出**，不適用於 deterministic 公式結果（例：已核准的情境指數） | 67 新增節 | 是（新定義，需裁示） |
| **C-3 Constraint Precedence** | Hard Constraint ＞ interpretation；解讀永遠不能推翻約束 | 75 第 11 節（不得繞過 Risk Cap、覆蓋 hard gate）；67 第 3.3 節；`DEC-2026-10-27-14`；`PROJECT_RULES.md` 13.2 第 7 條 | 優先序的完整排列（第 6.2 節）與「衝突時顯示什麼」 | 67 新增節 | 是（新定義，需裁示） |
| **C-4 Field-Level Provenance** | 每個進入決策的欄位各自帶 source／as_of／freshness 等，不靠頁級時間戳 | `CLAUDE.md` §2.2～§2.4；`PROJECT_RULES.md` 第 13 節第 5 條；67 第 5.3 節最低欄位 | 欄位 schema 候選與「global timestamp 只代表 render 時間」（第 7 節）；Freshness Policy schema（不填值） | 67 第 5 節增補；值另走 Threshold Gate | schema：是；門檻值：另案 |
| **C-5 Auditability** | 任何一句畫面字可回溯：UI → Decision Digest → Rule → Canonical Data → Source | 67 第 3.2 節「查看依據」、第 5.6 節第 6 項；75 第 7 節 trace；`PROJECT_RULES.md` 13.3 | 回溯鏈的固定五段與 AI 句子的 traceability 要求（第 8.4 節） | 67 新增節 | 是（新定義，需裁示） |

**共同邊界（依據既有條文）**：五條都不新增行動詞、不新增狀態符號、不填任何門檻數值、不授權任何實作；C-2 不禁止 deterministic 計算出的比率（例：配置占比 %、報酬率 %）與已核准的 deterministic 情境值（44 之十八其十的情境指數），禁止的是「機率」與「信心」這類對未來或對判斷本身的機率陳述。

---

## 3. 正式概念鏈（提案；依據既有條文，名稱整合屬新定義）

```text
Raw Sources
  → Source Resolution／Validation（含 identity resolution）
  → Canonical Data
  → Domain Calculation
  → Deterministic Rules
  → Risk Cap／Hard Constraints
  → System Action State
  → Decision Digest
  → OneBrain
  → Presentation（各頁、🤖）
```

| 與既有鏈的對位 | 說明 |
|---|---|
| 67 第 1 節固定鏈 `Raw Data → Validate → Normalize → Domain / Formula → Deterministic Rules → Risk Cap → AI Explanation` | 同向；本鏈把 identity resolution 明列在 Validation（`DEC-2026-11-01-01`：Source ≠ Identity），並在 Risk Cap 之後插入 System Action State |
| 67 第 5.1 節 `Raw Sources → Canonical Data → Rules / Indicators / Risk Cap → Decision Digest → One AI Brain → UI` | 同向；本鏈把 Rules 與 Risk Cap 拆開以表達 C-3 的優先序 |
| `PROJECT_RULES.md` 13.3 第 1 條 | 同向（Raw → Resolution／Validation → Canonical → Domain → Page View → One AI Brain） |

**AI 在鏈上不得做的事（依據 67 第 3.3 節、75 第 2、5、11 節、`PROJECT_RULES.md` 13.1）**：不 fetch；不改 canonical data；不補 missing；不算應由 Python 算的公式；不覆寫 rule result 或 Risk Cap；不產生 System Action State。

---

## 4. Chart Contract（提案）

### 4.1 四層：每一層可以畫什麼

| 層 | 內容 | 誰產生 | 可畫 | 禁止 |
|---|---|---|---|---|
| **A Fact** | 觀測值、序列、current value、as_of、source、freshness、missing | Canonical Data | 線、點、條、current value marker、as_of／source／freshness chip、缺段斷線 | 補線、畫零、推估值冒充觀測值 |
| **B Deterministic Threshold／Rule** | 已登錄的正式規則門檻、使用者自訂參數帶（例：容許帶） | Deterministic Rules；使用者設定 | threshold line／band、target band、tolerance band，**必須標出處類別** | 未登錄、無 DEC 的門檻上圖；把使用者參數標成系統規則 |
| **B′ Deterministic 情境（已核准公式）** | 已核准的市場指數層級情境指數（`docs/v2/66` 第 4 節公式，`DEC-2026-10-27-21`；`DEC-2026-10-27-35`） | Domain／Formula（deterministic） | 情境線，可用系列色區分（44 之十八其三第 3 條），**條件**：同時顯示 44 之十八其十第 3 條六項（EPS 情境、本益比情境、as-of、資料來源、Missing 狀態、66 第 4.6 節免責句）；名稱用「情境指數／情境點位」 | 稱「目標價／目標點位／預測高點」；缺正式預估資料時假裝畫出（顯示 44 之十八其十第 5 條字樣）；本提案只引用、不擴充（不新增情境種類，不帶入基金或其他層級的估值介面） |
| **C Regime／State** | 市場或組合的狀態 | Deterministic Rules（aggregation rule） | regime chip（限 aggregation rule 經裁示後） | aggregation rule 未裁示前出現任何綜合狀態 chip；以 AI 判斷充當狀態 |
| **D OneBrain Interpretation／OneBrain 情境** | 解讀文字、OneBrain 情境敘述 | OneBrain（只讀 Digest） | **只能文字**（在 🤖 或各頁 local summary 位置），**不畫在圖上、不產生數值** | 在圖上疊 AI 標注；OneBrain 情境畫成線或給出點位數值（若要畫需另走 Gate） |

**依據既有條文**：44 之十八其三（第 2 條缺段斷線不補、不畫零；**第 3 條允許系列色區分不同序列、基金、比較基準與情境線**；第 4 條禁只靠紅綠；**第 5 條只禁目標價線、預測高點線與方向箭頭**）、之十八其十（情境指數不是目標價，六項必顯示資訊）、之十九其三與其四（圖卡結構、chip 不自創門檻）。**新定義，需裁示**：四層分類本身、B′／D 的分界（deterministic 情境可畫、OneBrain 情境只能文字）與「出處類別必須可見」。

> ⚠️ **本輪更正（稽核 B1）**：初稿寫「scenario／forecast 線維持禁止，若要開需 44 amendment＋C-2 calibration contract」，**引用錯誤** —— 44 之十八其三第 5 條只禁目標價線、預測高點線與箭頭，第 3 條明文允許情境線；情境指數已由 `DEC-2026-10-27-35` 核准。calibration 前提只屬機率／信心類輸出（C-2），不適用於 deterministic 公式結果，已刪。

### 4.2 Annotation taxonomy（標注種類 × 出處類別）

出處類別七種：**官方定義**／**資料來源值**／**市場慣例**／**本系統正式 deterministic rule 或公式**（含已核准的情境指數）／**使用者自訂參數**／**OneBrain interpretation**／**OneBrain 情境**。

| 標注 | 允許的出處類別 | 顯示規則 | 現況 |
|---|---|---|---|
| current value marker | 資料來源值 | 標值＋單位＋as_of | 🌍 chips 有最新值與資料日【F-轉述】 |
| threshold line | 本系統正式 rule；官方定義（需註明出處） | 線旁文字標出處類別與 Rule ID；不得只靠顏色 | 全 ui_v2 無【F-轉述】 |
| threshold band | 同上 | 同上；band 名稱用中性字，不用好壞字 | 無 |
| target band | 使用者自訂參數 | 標「使用者設定」 | 無 |
| tolerance band | 使用者自訂參數 | 標「使用者設定」；不是系統建議 | 💼 容許帶只以文字出現、未畫【F-轉述】 |
| reference line | 資料來源值；官方定義 | 標來源（例：比較基準） | 無 |
| regime chip | 本系統正式 rule（aggregation） | aggregation rule 裁示前不得出現 | 無；🌍 顯示「暫無完整市場綜合判定」【F-重驗】 |
| as_of | 資料來源值 | 每序列各自；不以頁級時間代替 | 🌍 有資料日 chip；無頁級日期【F-轉述】 |
| source | 資料來源值 | 可收進「▸」展開區（44 之十九其四第 4 條） | 市場域帶 source【F-轉述】 |
| freshness | 本系統正式 rule（門檻）＋資料來源值（天數） | 門檻未裁示時只顯示天數與「⬜ 門檻待裁示」 | 🌍 現況即如此【F-重驗】 |
| stale | 本系統正式 rule | `◷ 不是最新`；門檻未裁示不得判 stale | 🌍 未判【F-重驗】 |
| missing | 資料來源值（狀態） | 斷線＋`◇ 資料未備` 或空狀態模板 | 已有【F-轉述】 |
| deterministic 情境線（已核准情境指數） | 本系統正式公式（`docs/v2/66` 第 4 節，`DEC-2026-10-27-21`） | 依 44 之十八其十：六項同時顯示；系列色＋至少一種非顏色辨識；無正式預估資料時顯示該其第 5 條字樣 | ui_v2 尚無；資料源待 BL-0501；進哪一頁、哪一塊隨 BL-0485 |
| OneBrain 情境 | OneBrain 情境 | 只能文字敘述；不畫線、不產生點位數值；若要畫需另走 Gate | 無（OneBrain 未啟用） |
| 目標價線、預測高點線、方向箭頭 | — | **維持禁止**（44 之十八其三第 5 條、第一節第二小節禁輸出） | 無 |

**通則（新定義，需裁示）**：出處類別必須在畫面上可見（文字，不只顏色）；兩種出處類別的標注不得用同一種線型與同一種字樣；市場慣例只能標「市場慣例」，不得冒充系統規則。

### 4.3 VIX 案例（說明為什麼要有出處類別）

| 說法 | 出處類別 | 本檔判定 |
|---|---|---|
| 「VIX <15／15–25／25–40／>40」四段 | 市場慣例（坊間說法） | **Illustrative Only／非正式規則**；程式與正式文件查無【F-轉述】 |
| 「VIX>50＝恐慌」 | 市場慣例 | **不是 Cboe 官方規定**；同上查無【F-轉述】 |
| 舊樹 `shared/macro_buckets.py::_VIX_YELLOW`＝22、`_VIX_RED`＝30 | 舊樹內部 SSOT（`CLAUDE.md` §8.3 F-GRAY-4） | 存在【F-重驗】，但 ui_v2 未採用、未呈現【F-轉述】；要上圖需另走 Threshold Gate（第 13 節 UI-4 的 B） |
| 舊樹 `services/macro/us_indicators.py::_VIX_SNAPSHOT_CALM`＝18 | 舊樹快照層獨立校準 | 存在【F-重驗】；ui_v2 未採用【F-轉述】 |
| 舊樹 `services/macro/tw_local.py` 的 VIX 計分帶 15／20／25／30 | 舊樹計分邏輯 | 存在【F-重驗：該檔 docstring 與計分分支】；ui_v2 未採用【F-轉述】 |
| 舊樹 `shared/signal_thresholds.py::LADDER235_VIX_L1`～`L3`＝20／25／30 | 舊樹 235 燈號 | 存在【F-重驗】；ui_v2 未採用【F-轉述】 |
| ui_v2 唯一具名門檻 `ui_v2/thresholds.py::NAV_NOT_READY_DAYS`＝10 | 客戶裁示 | 存在【F-重驗】；與 VIX 無關 |

舊樹 VIX 門檻至少有上列四組彼此不同的切法，**本表非窮舉**；這正是「沒有出處類別就不准上圖」的理由。

### 4.4 Multi-Series Comparison（提案）

| 規則 | 內容 | 依據 |
|---|---|---|
| 主要 series 上限 | 同一張圖原則 ≤3 條主要 series | 新定義，需裁示（44 查無 series 上限） |
| 同單位同尺度 | 可直接 overlay（例：美 2Y 與美 10Y，皆 %） | 新定義，需裁示 |
| 不同絕對尺度比走勢 | 用歸一化（Normalized）；必須標起始日、base value、frequency、missing handling；基準值 1 或 100 只是顯示尺度，見 UI-13 | 新定義，需裁示（44 查無 normalized；🔍 已核准的 78 寫起點＝1） |
| 不同語意或單位 | 不硬疊；改並排或切換 | 新定義，需裁示 |
| dual-axis | **預設禁止**（雙軸會誘導讀者看出不存在的相關性），列 Gate | 新定義，需裁示（44 查無 dual-axis） |
| frequency 不一致 | 不 resample 冒充同頻；圖上標示頻率差 | `CLAUDE.md` §2.3、§4.5 對齊原則 |
| 缺值 | 斷線、不補、不畫零 | 44 之十八其三（既有） |
| 期間 | 3M／6M／1Y／3Y，預設 1Y，各頁一致 | 44 之十八其四（既有） |
| 非顏色辨識 | 直接標籤、圖例、線型或標記點至少一種 | 44 之十八其三（既有） |
| mobile（390px） | 圖例改直接標籤或圖下一行；current value label 只標最後一點；tooltip 不承載唯一資訊；label 不得重疊（重疊時減 series，不縮字） | 新定義，需裁示 |

---

## 5. Market Regime Contract（提案）

### 5.1 Evidence taxonomy（只定「有哪幾類證據」，不定怎麼加總）

| 類 | 候選證據 | 現況 |
|---|---|---|
| Trend | TAIEX、S&P 500、趨勢結構；均線（**僅限有正式資料與定義**）；breadth（**僅限有正式 source**） | TAIEX、S&P 500 已在 🌍【F-重驗：`ui_v2/mkt/overview.py::PRIMARY_KEYS`】；均線、breadth 無 |
| Risk | VIX、credit spread（`BAMLH0A0HYM2`）、term spread（`T10Y2Y`） | 已在 🌍 Secondary【F-轉述】 |
| Rate／Macro | 美 2Y、美 10Y、policy rate（`FEDFUNDS`）、macro | 前三者已在 🌍【F-轉述】；macro 另案 |
| FX | 僅限正式 source 可用 | 未驗證 FX 保持關閉（`PROJECT_RULES.md` 第 13 節第 7 條） |

### 5.2 狀態詞與規則

- **狀態詞候選**：牛市擴張／牛市高波動／修正／熊市／無法判定 —— **Illustrative Only；詞彙本身需客戶核准**（新定義）。
- 【I】⚠️ 同一件事已有既有詞：`DEC-2026-10-27-14` 新允許清單已列「中性偏多／中性／中性偏空等綜合狀態」（仍須走固定鏈），66 第 3.1 節也以此為例。另立一套「牛／熊」詞會形成兩套 regime 詞彙；本檔推薦**優先沿用 `-14` 既有詞**，另立新詞須說明為何既有詞不夠（`PROJECT_RULES.md` 13.4 第 6 條、75 第 10 節「不自行創造投資狀態」）。
- **不定分數、權重、門檻、總分**（`DEC-2026-10-27-14` 禁黑盒單一總分與 0～100 分數；67 第 2.7 節）。
- aggregation rule 經 Formula Gate 裁示前，🌍 維持「暫無完整市場綜合判定（缺正式 aggregation rule）」（`DEC-2026-10-27-41`、66 第 3.1 節；`ui_v2/mkt/market_section.py::TEXT_NO_CONCLUSION`【F-重驗】）。
- 舊樹 regime／verdict 不得匯入當 SSOT（`DEC-2026-10-27-14`「不取代」清單）。
- **Current State ≠ Forecast**：目前狀態與任何情境永久分卡，不同卡、不同出處類別、不同字樣（新定義，需裁示）。
- **已核准的情境指數不是 forecast**：44 之十八其十第 1、2、4 條（`DEC-2026-10-27-35`）定義它是「指定情境下依透明公式得到的假設性指數水準」，不是目標價、不是預測；它屬第 4.1 節 B′ 層（deterministic 公式），不是 regime 狀態，也不是 OneBrain 情境。本提案只引用、不擴充（44 之十八其三、其十為正式依據；更正稽核 B1 指出的初稿誤引）。

---

## 6. Action／Risk Cap boundary（提案）

### 6.1 System Action State（新定義，需裁示）

| 項 | 內容 |
|---|---|
| 定義 | Deterministic Rules＋Risk Cap 評估後，對某個作用對象（組合／類型／單檔）的唯一動作狀態 |
| 值域 | 只用 67 第 2 節六詞：續抱、觀察、降低曝險、減碼、替代比較、無法判定；**不新增行動詞** |
| 現行值 | Rules 與 Risk Cap 未定義前只會是「無法判定」（67 第 1 節現行可用性；`DEC-2026-10-27-40`） |
| 產生者 | 只有 deterministic layer；OneBrain 只能引用（C-1） |
| 必帶欄位 | 作用對象、值、原因（含「缺什麼」）、Rule ID（若存在）、評估時間、輸入 Digest 參照 |
| 呈現 | 沿用 67 第 2.6 節「⬜ 無法判定（資料未備／證據不足）」字型 |

### 6.2 Constraint precedence（新定義，需裁示）

```text
資料狀態（取數失敗／資料未備／不是最新）
  ＞ Hard Constraints（含 Risk Cap 超限）
  ＞ Deterministic Rule Result
  ＞ System Action State
  ＞ OneBrain interpretation
```

上層不成立時，下層不得產生比上層更樂觀的結論（例：資料未備時不得出現續抱；Risk Cap 超限時 OneBrain 不得寫「可以維持」）。依據：67 第 2.6 節、第 5.4 節；`PROJECT_RULES.md` 13.1；`DEC-2026-10-24-10`。

### 6.3 Risk Cap 的未來行為邊界（不定數值、不定 trigger；數值與 trigger 走 BL-0495／BL-0496）

| 候選行為（需 BL-0495 與行動詞彙 Gate 裁示，**本提案不核准**） | 不可做（依據既有條文；本提案請求核准此清單） |
|---|---|
| 顯示超限與超限幅度 | AI 選擇要賣哪一檔基金（67 第 2.3、3.3 節；75 第 11 節） |
| 「凍結加碼（Freeze Add Exposure）」—— **不在 67 六詞內** | 計算贖回金額（`DEC-2026-10-27-14`：AI 不得決定資產水位） |
| 顯示 constraint reason 與 Rule ID | 決定核心或衛星先賣誰（75 第 11 節：不得自行創造 core／satellite 規則） |
| 「需進一步再平衡決策」的標示 —— 44 資產配置頁「不產生再平衡動作」 | 決定成本或稅務優先序 |

> ⚠️ **本輪更正（稽核 B3）**：初稿把左欄寫成「可做」，**越權** —— Risk Cap 的輸出定義屬 BL-0495 待裁；「凍結加碼」不在 67 六詞內；44 資產配置頁照舊「不產生再平衡動作」（44 之十八其十一第 3 條）。左欄改為候選，本提案不核准。
> 若客戶日後要表達「禁止新增曝險」，須在 67 六詞框架內另走詞彙 Gate（例：把它定義為「降低曝險」的前提或限制條件，而不是一個新動作），**不得作為隱含新詞**出現在畫面、Digest 或 OneBrain 輸出。

- 再平衡政策未定時：顯示「⬜ 無法判定（待再平衡決策）」—— **「待再平衡決策」是「無法判定」的原因字樣，不是新行動詞**（列 Gate UI-6；字樣待客戶定字）。
- **Rebalance Policy Gap（未定義清單）**：core／satellite 優先序、fund role、minimum redemption、fees、tax、liquidity、settlement、exposure hierarchy、concentration、missing、stale、replacement availability。
- 任何比例數字（例：50%、58%、8pp、單檔 20%、某類型 40%）只要出現在提案或線框中，一律標 **Illustrative Only／非正式規則**；本檔不提出任何比例門檻（67 檔頭「不要自行發明數值 threshold」）。

---

## 7. Field-Level Provenance／Freshness（提案）

### 7.1 決策欄位 schema 候選（新定義，需裁示；對照 67 第 5.3 節）

| 欄 | 意思 | 67 第 5.3 節已有概念？ | repo 既有承載（轉述自盤點） |
|---|---|---|---|
| value | 值 | 是（value／result） | `value_num` 等 |
| unit | 單位 | 是 | `value_unit` |
| source | 具體來源名 | 是 | 市場域 `source`；`market_indicator` 只有 `source_tier`（4 類別，不是來源名） |
| provenance | 來源鏈與修正紀錄 | 是 | nav、Cell、`market_view` |
| as_of | 觀測日 | 是 | `obs_date`、`nav_date` 等 |
| release_date | 公布日 | 部分（as_of 欄內） | `market_indicator` 有【F-重驗】 |
| retrieved_at | 取得時間 | 是 | `fetched_at` |
| frequency | 頻率 | 否（新增） | — |
| freshness_state | 依 Freshness Policy 判出的狀態 | 是（stale／freshness state） | 三套說法（67 第 5.3 節） |
| stale | 是否不是最新 | 同上 | nav `provenance.stale` |
| missing／unavailable／error | 三種不同的缺 | 是（missing／unavailable state） | 44 四狀態、Cell status、`reason_code` |

- 正式 source 不提供 release date 時**不虛構**，該欄寫「來源未提供」（依據 `CLAUDE.md` §2.3、§1）。
- 【F-轉述】ui_v2 無全域「更新時間」；本提案：**global timestamp 只代表 UI render／summary refresh 時間，不得被讀成資料時間**（新定義）。

### 7.2 Freshness Policy schema（只定欄位，不填任何門檻值）

| 欄 | 意思 |
|---|---|
| policy_id | 政策識別碼 |
| frequency | 日／週／月／季 |
| expected_lag | 正常發布延遲（文字或天數，取自來源事實） |
| stale_after | **值待裁示**（Threshold Gate） |
| authority | 誰裁示（DEC 編號） |

**現況對照**：`CLAUDE.md` §2.4 定義 TTL 常數與舊 SPEC §2 的 daily／monthly 綠黃紅門檻，ui_v2 尚未採用【F-轉述】；同節另有「月度指標超過 40 天 → AI Prompt 附 `[STALE: XXd]` 標籤」規則，Digest／OneBrain 批需決定是否沿用；🌍 顯示「新鮮度門檻 ⬜ 門檻待裁示」（`ui_v2/mkt/market_section.py::TEXT_FRESHNESS_THRESHOLD`【F-重驗】）；`SET-1` 用使用者輸入 `set_max_age_days`【F-轉述】。本提案不把 §2.4 的值搬進 ui_v2；要採用須另走 Gate（第 13 節 UI-8）。

---

## 8. Decision Digest Full Context Contract（提案）

### 8.1 原則（依據 67 第 5.1 節客戶原話）

**UI 可以只顯示 10%，Digest 必須保留 100% 有決策意義的 context。**（10%／100% 為示意比例，不是指標。） 67 第 5.1 節已有客戶原話「Presentation Simplification must never reduce AI Decision Context」與「Data View ≠ Decision Context ≠ AI Output」；本節只把它展開成欄位群。

### 8.2 欄位群（對照 67 第 5.3 節與 BL-0527）

| 群 | 欄位 | 67 第 5.3 節 | BL-0527 缺口 |
|---|---|---|---|
| Identity | canonical identifier、類別、identity resolution 狀態（resolved／unresolved） | identifier | 跨類別 identifier（隨 DG-2） |
| Value | value、unit、currency／share class | value、unit | — |
| Time | as_of、release_date、retrieved_at、frequency | as_of、retrieved_at | as_of 與 stale 統一定義 |
| Source | source（具體名）、source_tier、provenance、fallback 是否發生 | source、provenance | 市場指標逐項 provider |
| Health | freshness_state、stale、missing、unavailable、error、reason_code | stale、missing | 狀態字彙對照表 |
| Domain | domain calculation 結果與其輸入參照 | — | 規則結果的正式來源層 |
| Rule | rule result、Rule ID、rule_version、threshold 引用 | rule result、threshold 引用 | rule_version 不存在；引用格式 |
| Risk | Risk Cap 輸入／輸出（目前只能「未定義」）、System Action State | — | Risk Cap 只能未定義 |
| Audit | digest id、schema version、fingerprint、policy version、建立時間 | — | 「查看依據」對映（`AI-3`） |

confidence：**不納入**（67 第 5.3 節，條件不成立；C-2）。

⚠️ **與 67 第 5 節的張力（據實寫明）**：67 第 5 節引客戶原話「不要現在武斷建立全新巨大 schema。先盤點 repo 既有資料結構並設計最小契約」。上表**只列欄位群，不是 schema**；落地時以 67 第 5.3 節的最低概念欄位為核心，依 BL-0527 缺口逐步擴充，不一次建立全欄位結構。

### 8.3 OneBrain context 三分（新定義，需裁示；75 未分層）

| 類 | 定義 | 例 |
|---|---|---|
| Required | 沒有就不能做正式分析；缺時 OneBrain 輸出「無法判定」並列出缺什麼 | identity、value、as_of、health、rule result、System Action State |
| Optional | 有則用、缺則在 missing 清單揭露，不阻擋分析 | 歷史序列、補充 provenance |
| Excluded | 不得進入 Digest 與 fingerprint | widget 展開狀態、scroll、container 順序、cosmetic color、session-only display metadata |

**OneBrain 不得**從 UI 顏色、widget visibility、圖的位置、收合狀態、UI 文案反推 canonical fact（依據 67 第 5.2 節第 2 點、75 第 6.3 節）。

### 8.4 Traceability（C-5 的 AI 部分）

```text
AI sentence → Digest fields → Rule Result → Rule ID → Canonical Data → source／as_of
```

每次 OneBrain 正式輸出至少含：核心理由；使用了哪些 Rule Result；最大反證（Falsification Condition：什麼事實出現就推翻本判讀）；Missing／uncertainty 清單（新定義，需裁示）。

### 8.5 OneBrain qualitative outlook（維持 proposal，不得 production）

| 項 | 候選值 | 狀態 |
|---|---|---|
| 情境方向 | 偏強／中性／偏弱／無法判定 | Illustrative Only；【I】與 `DEC-2026-10-27-14` 既有「中性偏多／中性／中性偏空」重疊，推薦沿用既有詞 |
| 信號一致性 | 低／中／高 | Illustrative Only；「一致性」無定義前只能是 proposal |

兩者都是 interpretation 層（第 4.1 節 D 層），不是 System Action State，不得被畫成 regime chip，也不得帶 %（C-2）。

---

## 9. 五頁 Page Contract 與文字線框（提案）

> 線框標記：`[現]`＝現況已有；`[提]`＝本檔提案；`[Gate]`＝需客戶裁示。數值一律用 `‹值›` 遮罩。框寬約 56 欄，全形字算 2 欄，右框偶有不齊屬正常。

### 9.1 🌍 市場與趨勢

| 項 | 內容 |
|---|---|
| 唯一核心問題 | 現在市場有沒有異常、需要注意？主要趨勢長怎樣？（`DEC-2026-10-30-01` 額外 UI Guardrail 三眼） |
| 順序 | 依 `DEC-2026-10-30-01` D7：status chip → 一句主判讀 → Primary → Secondary → 依據卡 → details／Missing／provenance；依據卡不要求在第一屏 `[現]` |
| First Eye | status chip＋一句主判讀：regime Gate 前＝「暫無完整市場綜合判定（缺正式 aggregation rule）」`[現]` |
| Primary | **現況**＝`DEC-2026-10-30-01` D1 單序列切換（TAIEX／S&P 500／VIX／美 10Y／美 2Y，預設 TAIEX、期間預設 1Y）【F-重驗】。`[Gate UI-12]` 提案改為 TAIEX＋S&P 500 歸一化比較圖（標起始日、base、frequency、missing handling）＝**修改 D1，需客戶覆議** |
| Secondary ≤3 | **現況**三張：「風險｜VIX」「國際｜S&P 500」「利率與信用」（D2 P2 切換）`[現]`【F-重驗：`ui_v2/mkt/overview.py::SECONDARY_RISK_TITLE`、`SECONDARY_INTL_TITLE`】。VIX 卡維持現況、不畫 band（無已核准規則）；若 Primary 改比較，「國際｜S&P 500」卡會與 Primary 重複，其去留須一併裁示 `[Gate UI-12]`；美 2Y＋10Y 同單位 overlay 為 `[提]`（可放進「利率與信用」切換內） |
| 依據卡 | 緊湊依據（各 domain 局部狀態，限 deterministic 支持者），**位置在 Secondary 之後**（D7）；「≤3 條」是新的數量限制 `[Gate UI-12 第 (3) 子題]` |
| Third | Missing、freshness、source、observation dates、limitations、`MKT-1`～`MKT-7`：下沉，不得刪除 `[現]` |
| 保留 | Batch C 語意；D2 P2 合併切換；D7 順序；chip 規則；Secondary 不複製 Primary 完整資訊（D1 硬限制）。**D1 版面需覆議**（UI-12） |
| 相對現況差異 | 只在 UI-12 核准時：Primary 由單序列改比較圖、S&P 500 卡去留；其餘維持現況 |

```text
桌機 1280                                   手機 390
┌───────────────────────────────────────┐  ┌──────────────────────┐
│[現] status chip ‹n›                   │  │[現] status chip      │
│[現] 暫無完整市場綜合判定（缺正式…）   │  │[現] 暫無完整市場…    │
│[現] Primary 單序列切換（預設 TAIEX）  │  │[現] Primary          │
│  [Gate UI-12] 或 TAIEX vs S&P 歸一化  │  │ [Gate] 或比較圖      │
│  [ 3M 6M 1Y 3Y ]  資料日‹日›          │  │ [ 1Y ]  資料日‹日›   │
├────────────┬────────────┬─────────────┤  ├──────────────────────┤
│[現]風險VIX │[現]國際S&P │[現]利率與信用│  │[現] VIX ‹值›‹變動›   │
│ ‹值›‹變動› │[Gate]去留  │[提]2Y+10Y疊 │  │[現] S&P ‹值›         │
│ band：無   │            │ 切換 1 序列 │  │[現] 利率與信用 ‹值›  │
├────────────┴────────────┴─────────────┤  ├──────────────────────┤
│[Gate] 依據卡 ≤3（D7：Secondary 後）  │  │[Gate] 依據卡 ≤3      │
│[現] ▸ Missing／來源／限制             │  │ ▸ Missing…           │
└───────────────────────────────────────┘  └──────────────────────┘
```

### 9.2 💼 我的資產

| 項 | 內容 |
|---|---|
| 唯一核心問題 | 我的錢放在哪？有沒有偏離？哪些持股需要注意？（44 之二十其二第 1 條） |
| First Eye | P3 頁級狀態容器（β 階梯，`is_rule_result: False`）`[現]`【F-重驗：`ui_v2/asset/page_status.py` 檔頭】 |
| Primary | 資產配置現況 vs 目標 `[現]`＋**畫出 tolerance band**，出處類別＝「使用者設定」，不是系統規則 `[Gate UI-12]`（現況容許帶只有文字【F-轉述】） |
| Secondary ≤3 | 基金占比、各檔區間報酬（原幣）`[現]`；drawdown／risk **只在有正式資料契約時** `[提]` |
| Third | 層 3／4 明細、Missing 清單 `[現]` |
| 行動 | action state 只來自 deterministic rules；現況無 → **不顯示任何行動** |
| 保留不推翻 | Batch D、P3、Layout A、page-state semantics、Domain Block Identity ≠ Presentation Container（`DEC-2026-10-30-02`、`DEC-2026-10-31-01`）；不畫 `HLD-0`／`ALO-0` 重複燈；容許帶等參數無預設值 |
| 相對現況差異 | 只差 Primary 上的 band 視覺 |

```text
桌機 1280                                   手機 390
┌───────────────────────────────────────┐  ┌──────────────────────┐
│[現] P3 狀態容器：‹頭條›／‹第二行›     │  │[現] P3 狀態容器      │
│[現] 摘要 ◇ 資料未備 ×4               │  │[現] 摘要（精簡）     │
│[現] Primary 現況 vs 目標              │  │[現] Primary          │
│  類型A ███████│░░ ‹%›                 │  │ 類型A ████│░ ‹%›     │
│  [Gate] ┆容許帶┆ 標「使用者設定」    │  │ ┆帶┆ 使用者設定       │
├───────────────────┬───────────────────┤  ├──────────────────────┤
│[現] 基金占比       │[現] 各檔區間報酬 │  │ 基金占比（緊湊）     │
├───────────────────┴───────────────────┤  ├──────────────────────┤
│[現] 持股明細／Missing（層 3、4）      │  │ ▸ 明細／Missing      │
└───────────────────────────────────────┘  └──────────────────────┘
```

### 9.3 🔍 找基金

| 項 | 內容 |
|---|---|
| 唯一核心問題 | 這一檔（或這幾檔）基金是什麼、長怎樣？在我的條件下有哪些符合？ |
| 結構 | 同頁上下 P：上「找一檔基金」、下既有 EXP 篩選器原樣（`DEC-2026-11-01-02`） |
| First Eye | 單一輸入框 X（MoneyDJ 基金代碼或 ISIN）；ISIN「尚未啟用／目前沒有已核准的 ISIN 對照來源」；S6 字樣「輸入類型：代碼型字串（原值未改寫）」「基金身份：◇ 尚未確認」 |
| Lookup Result | 基金名稱、MoneyDJ code、ISIN（無已核准來源時不顯示推斷值）、fund category、currency、as_of、source／provenance；分清「查無基金」與「取數失敗」，分不清時不寫查無（G-E3） |
| Comparison Workspace | 使用者手動加入；78 未定上限；Batch E 實作暫以 3 檔為顯示上限（與 Visual Budget ≤3 series 一致），正式上限由 UI-12 確認，不以本題為前置（開工時點依 `DEC-2026-11-02-01`：Step 3 客戶裁示後）（客戶 2026-11-02 任務轉述「最多 2～3 檔」）`[Gate UI-12]`；session-only、唯讀；不寫 Sheet、我的資產、候選、觀察清單（G-E6） |
| Primary | 歸一化 NAV：基準值裁示前沿用 78 已核准的「起點＝1」，推薦改 100（UI-13）；標 base date、date range、frequency、missing treatment、各檔 as_of、source |
| Secondary（下沉） | 1M／3M／6M／1Y／3Y、Sharpe、Beta、Max Drawdown、配息分布、費用、規模、幣別、經理人、來源、限制 —— 只有 repo 已有正式資料才顯示，否則 `◇ 資料未備` |
| 下方 | EXP 篩選器原樣（`EXP-0`～`EXP-7`；`EXP-3` 並排對照上限 3 不動） |
| 禁止 | 名次截取（Top N）、最佳、精選、AI 排名、AI score、名稱模糊搜尋（`DEC-2026-10-27-32`、`-33`、`DEC-2026-11-01-01`） |

> ⚠️ **更正總管轉述的一項現況**：轉述寫「`EXP-3` 並排對照上限 4（44 逐字）」。本組重驗【F-重驗】：44 `EXP-3` 規則欄逐字為「**同時最多對照 3 檔**」，第 4 個勾選框停用；程式 `ui_v2/exp/logic.py::COMPARE_LIMIT`＝3。**上限是 3，不是 4。** 因此「lookup 比較上限 3 與 EXP-3 上限 4 並存」的前提不成立；剩下的小題是：兩者數字相同但是兩個不同元件（選取不互通、不合併計數），是否需要客戶確認（第 13 節 UI-12 第 (5) 子題）。

```text
桌機 1280                                   手機 390
┌───────────────────────────────────────┐  ┌──────────────────────┐
│ 找一檔基金                             │  │ 找一檔基金           │
│ [ MoneyDJ 基金代碼或 ISIN       ][查] │  │ [代碼或 ISIN   ][查] │
│ ISIN：尚未啟用（無已核准對照來源）    │  │ ISIN：尚未啟用        │
│ 輸入類型：代碼型字串（原值未改寫）    │  │ 基金身份：◇ 尚未確認 │
│ 基金身份：◇ 尚未確認                  │  ├──────────────────────┤
├───────────────────────────────────────┤  │ ‹基金名›｜‹code›     │
│ ‹基金名›｜‹code›｜‹類別›｜‹幣別›      │  │ as_of‹日›｜來源‹›    │
│ as_of‹日›｜來源‹›   [加入比較 ‹n›/3]  │  │ [加入比較 ‹n›/3]     │
│ Primary：歸一化 NAV（基準值 UI-13）   │  │ Primary 歸一化 NAV   │
│  base‹日›｜‹區間›｜日頻｜缺值斷線     │  │ ▸ 報酬／風險／費用…  │
│ ▸ 報酬／風險／費用／限制（下沉）      │  │                      │
├═══════════════════════════════════════┤  ├══════════════════════┤
│ [現] 依條件篩選（EXP-0～7 原樣）      │  │ [現] 依條件篩選      │
└───────────────────────────────────────┘  └──────────────────────┘
```

### 9.4 🤖 AI 投資總結

| 項 | 內容 |
|---|---|
| 唯一核心問題 | 現在怎麼看、主要原因、最大風險、是否需要行動（67 第 6.1 節第 3 條） |
| 六段 | 市場一句；我的資產／配置一句；持股一句；找基金／候選比較一句；主要風險 1～3；本期行動 ≤3 |
| Action | 只能引用 System Action State（目前只會是「無法判定」並寫缺什麼） |
| 版面四區 `[Gate UI-14]` | System State（deterministic）／OneBrain Interpretation（AI）／Maximum Falsification（最大反證）／Evidence（可展開「查看依據」）—— 超出 67 第 6.1 節固定輸出（Maximum Falsification 為新增），Phase 7 線框時裁示 |
| 禁止 | 未校準 %；大量長文；複製市場頁全部圖或資產頁全部表；平行 action；AI score；假信心；Missing 時硬判方向（67 第 3.3、6 節；C-1、C-2） |
| runtime 未啟用時 | 沿用 75 第 12 節字樣「AI 分析暫不可用／無法判定」—— 誠實狀態，不放假資料 |
| 導覽 | **已裁示**：`DEC-2026-10-29-07` Phase 7 才掛入；目標 IA＝五頁不變（不重問） |

```text
桌機 1280（Phase 7 後）                     手機 390
┌───────────────────────────────────────┐  ┌──────────────────────┐
│ System State（deterministic）          │  │ System State         │
│  本期行動：⬜ 無法判定（‹缺什麼›）    │  │ ⬜ 無法判定（‹缺›）  │
├───────────────────────────────────────┤  ├──────────────────────┤
│ OneBrain Interpretation               │  │ 市場｜資產｜持股｜候選│
│  市場：‹一句›     我的資產：‹一句›    │  │ 各一句                │
│  持股：‹一句›     找基金：‹一句›      │  │ 主要風險 1～3        │
├───────────────────────────────────────┤  │ 最大反證：‹一句›     │
│ Maximum Falsification：‹一句›         │  │ ▸ 查看依據           │
│ ▸ 查看依據（Digest／Rule／來源）      │  └──────────────────────┘
└───────────────────────────────────────┘
runtime 未啟用時：整區只顯示「AI 分析暫不可用／無法判定」（75 第 12 節）
```

### 9.5 ⚙️ 設定

| 項 | 內容 |
|---|---|
| 唯一核心問題 | 資料可不可信、連線與來源是否健康、規則參數是什麼 |
| 保留 `[現]` | 帳號、Sheet picker、`SET-0`～`SET-3`、`SET-5`～`SET-8`、進階診斷【F-轉述】 |
| notifications | repo 內新版無既有功能 → 標「未定義」，本檔不提案 |
| 新提案：Rule Registry（唯讀） | 欄：Rule ID、version、description、threshold、effective date、source／authority（Rule ID 編碼與 rule_version 格式未定，屬 BL-0527 第 4 項、非機械式，見 UI-10；格式定案前殼只列名稱與出處）；**只登錄已存在的正式規則**（現況可登錄者極少，例：`NAV_NOT_READY_DAYS`）；禁止 slider 任意改正式 Risk Cap 或 threshold；第一階段唯讀（44 之十六）不變 |
| 新提案：Digest Viewer 雙層 | L1 human-readable，例「VIX ‹值›｜Rule：‹Rule ID›｜Result：‹›｜as_of ‹日›｜source ‹›」—— Rule ID 與 threshold 只有真的存在才顯示，例中 Rule ID 為 Illustrative Only；L2 raw Digest JSON：digest id、schema version、input facts、source、as_of、missing、rules、action state、fingerprint、policy version；**不得顯示 secret**（75 第 7.1、13 節） |
| 前置 | Digest Viewer 需 Decision Digest production 之後才能做 |

```text
桌機 1280                                   手機 390
┌───────────────────────────────────────┐  ┌──────────────────────┐
│[現] SET-0 可信度｜帳號｜Sheet         │  │[現] SET-0｜帳號      │
│[現] SET-1 新鮮度｜SET-2 來源健康      │  │[現] SET-1｜SET-2     │
│[現] SET-8 各頁資料狀態總表            │  │ ▸ SET-8 總表         │
│[提] ▸ 規則登錄（唯讀）                │  │ ▸ 規則登錄（唯讀）   │
│     Rule ID｜版本｜門檻｜生效日｜出處 │  │ ▸ Digest（Digest 後）│
│[提] ▸ Decision Digest（Digest 後）    │  │ ▸ 進階診斷           │
│     L1 可讀｜L2 JSON（無 secret）     │  └──────────────────────┘
│[現] ▸ SET-3／5／6／7／進階診斷        │
└───────────────────────────────────────┘
```

---

## 10. Mobile-first 與 Desktop（依據既有條文為主）

| 面向 | 390px 手機 | 桌機 | 依據 |
|---|---|---|---|
| 首屏順序 | 狀態 → 是否需注意 → 最重要數字 → Primary 起始區 → 主 CTA | 同序，可 2～3 欄 | 44 之十九其七；`DEC-2026-10-30-01` D7 |
| 不先出現 | metadata 長句、長說明、10 張卡 | 資料牆 | 44 之十九其一之一第 4 條 |
| Visual Budget | Primary 1、Secondary ≤3、第一屏核心數字＋chips ≤5、主判讀 ≤1 句 | 同 | 44 之十九其一之一第 2 條 |
| V7 | Primary 在首屏；**不得放寬** | — | `DEC-2026-10-31-01`（不採 C）；`tests/visual_fidelity/layout_checks.py` V7 |
| Secondary | 緊湊列，不縮成桌機圖 | 並排 | `DEC-2026-10-30-01` D6 |
| 側欄 audit | 收進抽屜 | 可放側欄，但不做資料牆 | 新定義，需裁示（屬 Visual Budget 內） |

【F-轉述】「Mobile Visual Budget」在程式中無具名常數；本檔不新增常數。

---

## 11. Missing Contract（依據既有條文；不新增詞）

| 符號與字樣 | 意思 | 不等於 |
|---|---|---|
| `◇ 資料未備` | 來源缺或資料尚未備齊 | ≠ 0、≠ 中性 |
| `⬜ 無法判定`（含不適用、未設定） | 證據或規則不足以判定 | ≠ 安全、≠ 續抱、≠ HOLD |
| `⛔ 取數失敗` | 上游取數失敗 | ≠ 查無 |
| `◷ 不是最新` | 依正式門檻判為舊（門檻未裁示時不判） | ≠ 錯誤 |
| `◆ 需要注意` | 規則判出的注意事項 | ≠ 賣出訊號 |

- missing ≠ 0；unavailable ≠ neutral；not evaluated ≠ safe；unknown ≠ HOLD；顏色不是唯一訊息（44 之十九其五第 1 條、`PROJECT_RULES.md` 第 13 節第 2～4 條、13.2 第 3 條）。符號 SSOT：`ui_v2/symbols.py`、`ui_v2/health.py`【F-重驗 symbols】。
- **正式字樣依據**：44 之十九其五第 4 條（客戶第三則 Gate 裁示確認 Missing 的正式字樣照舊是 `◇ 資料未備`，「⬜ 資料未取得」之類為版面示意）。
- **⬜／◇ 資料未備不一致不列為待裁 Gate**：`DEC-2026-10-26-01` 寫「⬜ 資料未備」，44 之十九其五第 5 條登記此不一致、寫「誰改本輪不裁」。現況：**客戶 2026-11-02 任務第 48 節表態「缺資料時：◇ 資料未備，不要新造另一套詞」（逐字見 `docs/evidence/decisions/2026-11-02_final_ui_contract_freeze_assignment.md`）＋44 正式字樣**，已於 `DEC-2026-11-02-01` 落盤（同批），機械式統一為 `◇ 資料未備`（BL-0532）。
- 已知機械式修正對象（**非窮舉**）：`ui_v2/mkt/market_section.py` 的狀態字表把 `STATE_MISSING` 對到「⬜ 資料未備」；`ui_v2/mkt/chart.py::TEXT_EMPTY`＝「⬜ 資料未取得，無法繪圖」【兩者 F-重驗】。🌍 是否因此兩套符號並存，本組未實跑畫面【I】。

---

## 12. Final UI Gap Matrix

> 「已完成」只寫 production 已實作者；文件寫過不算完成。「本提案」＝本檔提出、尚未定義。

| Page | 已完成 | 已定義未實作 | 尚未定義 | Data Gap | Rule Gap | UI Gap | OneBrain Gap | Blocker |
|---|---|---|---|---|---|---|---|---|
| 🌍 | Batch C 頁、單序列 Primary、3 Secondary、Missing 下沉 | local explanation | aggregation rule；regime 詞；圖上 band；依據卡數量上限（本提案 ≤3，UI-12 第 (3) 子題） | breadth、均線無正式來源；市場指標逐項 provider（BL-0527）；情境指數資料源（BL-0501） | aggregation、freshness 門檻、VIX 門檻 | 比較圖＝D1 覆議（UI-12）；Missing 字樣統一 | local summary 未接 | Formula Gate；Threshold Gate |
| 💼 | Batch D、P3、Layout A | 層 3／4 超上限收斂 | Risk Cap；再平衡政策；行動 | drawdown／risk 契約；未驗證 FX 關閉 | Risk Cap（BL-0495）、trigger（BL-0496）；容許帶端點歸屬（`ui_v2/alo/fixtures.py` 檔頭 `ALO-GAP-端點`） | band 視覺（UI-12） | local summary 未接；A 線 AI 仍產生減碼與比例建議（BL-0528，與 C-1 張力） | BL-0495／0496；BL-0528 |
| 🔍 | EXP-0～7 篩選器 | Batch E 主入口、比較、歸一化 NAV（`DEC-2026-11-01-02` 已核准） | ISIN 對照來源 | ISIN→code（BL-0530）；部分 Secondary 欄無來源 | 無（不排名） | lookup 區（Batch E）；基準值（UI-13） | local summary 未接 | Batch E 實作；BL-0530 |
| 🤖 | 無 | IA、輸出格式（67 第 6.1 節）；Phase 7 掛導覽（`DEC-2026-10-29-07`） | Digest production；句子→依據對映；版面四區（UI-14） | Digest 七項缺口（BL-0527） | System Action State（UI-6） | 頁未掛（已裁示 Phase 7） | runtime、provider、cache、trace、budget（OB-01～10） | Digest；Risk Cap；OB-B |
| ⚙️ | SET-0～3、5～8、帳號、Sheet | 低頻全域化 | Rule Registry；Digest Viewer；audit；Rule ID 格式 | rule_version 不存在 | 正式規則清單極少 | Registry 殼（UI-10） | Viewer 依賴 Digest | Digest production |

---

## 13. Contract Decision Gates（⛔ 待客戶裁示）

> 格式依 `PROJECT_RULES.md` 第 4 節：商業語言、附總管推薦與理由；不是選擇題丟回。凡標「推薦」均為總管推薦，不是裁示。UI-11 已有裁示，不重問（`PROJECT_RULES.md` 13.4 第 6 條：Gate 不氾濫）。

**UI-1 五條鐵則是否正式採用**
- A：全採，回寫 67 新節＋DEC。B：只先採 C-1～C-3，C-4／C-5 待 Digest 批。C：維持 proposal。
- 優點：A 一次定錨，Digest、OneBrain、UI 批都有可引用的名字；B 減少一次寫入量、C-4／C-5 與 Digest 同批驗證；C 零寫入成本。
- 風險：A 的 C-4／C-5 需 Digest 才能驗證，短期是「有條文、無實作」；B 讓 Digest 批沒有既定的 provenance／audit 目標；C 讓後續各批各自解讀。
- **推薦 A**：五條多數已有既有依據，正式化成本低，且 C-4／C-5 是 Digest 批的設計輸入，越早定越不會返工。

**UI-2 Chart Contract（四層＋出處類別）的落盤方式**
- A：DEC 核准＋本檔保留 rationale，等第一個實作批真的需要時再開 44 新一輪 amendment（同 G-E5）。B：現在就開 44 amendment。C：延後。
- 優點：A 不動 frozen 44、仍有正式依據；B 條文最集中；C 零成本。
- 風險：A 期間有「DEC 有、44 沒有」的落差；B 為尚未實作的東西解凍 44；C 讓下一個畫圖的批次沒有出處類別規則。
- **推薦 A**：44 每次解凍成本高，現在要畫 band 的實作批還不存在。

**UI-3 Multi-series 規則**
- A：≤3、同單位 overlay、跨尺度歸一化＋強制揭露、dual-axis 禁止。B：同 A 但允許標示清楚的 dual-axis。C：維持單序列。
- 優點：A 支撐 🔍 多檔比較且無雙軸誤導；B 可同圖看不同單位；C 最簡單。
- 風險：A 不同單位需並排、多佔版面；B 的雙軸即使標示清楚，讀者仍易把兩條線交會讀成訊號；C 讓 🔍 多檔 NAV 比較無法成立。
- **推薦 A**：比較需求真實存在，歸一化已足以比走勢，雙軸的誤導成本不值得。

**UI-4 圖上 threshold／band**
- A：只有登錄於 Rule Registry 且有 DEC 的正式規則才畫；現況維持不畫。B：把舊樹 VIX 22／30 正式採用為系統規則並上圖（需另走 Threshold Gate）。C：畫市場慣例 band 並標「市場慣例」。
- 優點：A 每條線都有出處；B 很快就有 VIX 參考線；C 對使用者直覺。
- 風險：A 短期圖上沒有參考線；B 把舊樹內部校準升格成新 UI 規則，而舊樹至少有四組不同 VIX 切法（第 4.3 節），需單獨論證選哪一組；C 讓坊間說法看起來像系統判斷。
- **推薦 A**（B 另案）：先有出處、後有線。

**UI-5 Market Regime**
- A：只採 evidence taxonomy 與「無法判定優先」原則，狀態詞為 illustrative，aggregation rule 另走 Formula Gate。B：同時核准狀態詞彙。C：延後。
- 優點：A 不先定字、不卡 aggregation；B 線框可先用正式字；C 零成本。
- 風險：A 線框暫時只能寫示意詞；B 若採「牛／熊」詞，會與 `DEC-2026-10-27-14` 既有「中性偏多／中性／中性偏空」並存成兩套；C 讓 regime 相關討論沒有證據分類可依。
- **推薦 A**：詞彙應與 aggregation rule 一起定，且優先沿用既有詞。

**UI-6 System Action State＋Constraint Precedence＋Risk Cap 禁止清單**
- A：**只採** System Action State 定義（值域只用 67 六詞；「待再平衡決策」作為「無法判定」的原因字樣）、Constraint Precedence 原則、第 6.3 節右欄 Risk Cap 禁止事項清單；**Risk Cap 可做行為（第 6.3 節左欄候選）不在本次核准範圍**，數值、trigger 與輸出定義仍走 BL-0495／0496。B：新增獨立狀態「⬜ 待再平衡決策」為新詞。C：延後。
- 優點：A 給 Digest 與 🤖 一個唯一動作來源，且不新增詞；B 字面最直接；C 零成本。
- 風險：A 的 System Action State 目前只會是「無法判定」，看起來空；若有人把左欄候選讀成已核准，會越過 BL-0495 —— 故 A 明文排除左欄；B 新增行動詞，違反「行動詞只限六個」（44 之十八其十一、`DEC-2026-10-27-36`）；C 讓 Digest 批沒有動作欄位的定義。
- **推薦 A**：不新增詞即可表達，且把待裁的 Risk Cap 行為留在 BL-0495。

**UI-7 OneBrain qualitative outlook**
- A：維持 proposal，一致性定義與輸出 schema 隨 OneBrain 批另走 Gate。B：現在採用詞表。C：放棄。
- 優點：A 不先有字後有義；B 線框可先定字；C 減少一個待辦。
- 風險：A 多一個待辦；B 詞表與 `DEC-2026-10-27-14` 既有詞重疊、且「一致性」無定義；C 讓 OneBrain 輸出缺少方向以外的不確定性表達。
- **推薦 A**：沒有一致性定義前採詞表等於先有字、後有義。

**UI-8 Field-level provenance＋Freshness Policy schema**
- A：採 schema 為 Digest／L2 契約目標，門檻值 per source 另走 Gate。B：連門檻一起定。C：延後。
- 優點：A 先定欄位、門檻逐源論證；B 一次完成；C 零成本。
- 風險：A 欄位裡的 `stale_after` 暫時沒有值；B 一次定多個 threshold，屬正式 threshold 的值，須逐源論證；C 讓 Digest 批自行決定欄位，容易出現第四套 stale 說法（67 第 5.3 節已有三套）。
- **推薦 A**：欄位是 Digest 設計的前置，門檻值卻需要逐源資料事實（發布頻率、延遲）支撐，兩者分開才不會為了趕 schema 而拍腦袋定門檻。

**UI-9 OneBrain Context 三分與 Digest Full Context 原則**
- A：採用並回寫 67。B：只採原則。C：延後到 Digest 批。
- 優點：A 直接決定 fingerprint 不被 UI 汙染；B 寫入量小；C 與 Digest 同批定。
- 風險：A 的 Required 清單可能隨 Digest 實作調整；B 沒有 Excluded 清單，fingerprint 仍可能吃進 UI 狀態；C 讓 Digest 設計時沒有分層依據。
- **推薦 A**：Excluded 清單直接決定 fingerprint 不被 UI 汙染（75 第 6.3 節），應在 Digest 設計前定。

**UI-10 ⚙️ Rule Registry（唯讀）＋Digest Viewer 雙層＋Rule ID 格式**
- A：Batch F 做 Registry 唯讀殼與 source health；Digest Viewer 待 Digest production 後；**Rule ID 編碼、rule_version、門檻引用格式（BL-0527 第 4 項）另走格式 Gate，非機械式**。B：兩者都等 Digest。C：不做。
- 優點：A 先讓使用者看得到「目前有哪些正式規則」；B 一次做完、格式與 Digest 同批；C 零成本。
- 風險：A 的 Registry 初期內容極少（正式規則少），看起來空 —— 但那是誠實狀態；且殼的欄位要等 Rule ID 格式定案才能固定；B 讓 source health 跟著延後；C 讓 C-5 Auditability 在 UI 端沒有落點。
- **推薦 A**：Registry 是 C-5 回溯鏈在畫面上的終點，先做唯讀殼成本低、不涉及語意；格式未定前殼只列名稱與出處，不臆造編碼。

**UI-11 🤖 導覽掛入時機 —— 已裁示，不重問**
- `DEC-2026-10-29-07`：Phase 7 實作 One AI Brain 時掛入；目標 IA＝五頁（🌍、💼、🔍、🤖、⚙️）不變。本檔不列為待裁。

**UI-12 版面變更是否核准為下一批 wireframe 基準**
- 子項：(1) 🌍 Primary 改 TAIEX＋S&P 500 歸一化比較 ＝ **修改 `DEC-2026-10-30-01` D1（單序列切換），需客戶覆議**；(2) 若 (1) 核准，現行 Secondary「國際｜S&P 500」卡與 Primary 重複，**其去留一併裁示**（現行 Secondary：「風險｜VIX」「國際｜S&P 500」「利率與信用」）；(3) 🌍 依據卡「≤3 條」—— D7 只定依據卡的位置、未定數量，這是**新的數量限制，需確認**；(4) 💼 Primary 畫出 tolerance band（出處＝使用者設定；端點歸屬未定）；(5) 🔍 lookup 比較上限：78 未定，Batch E 暫以 3 檔顯示（不以本題為前置；開工時點依 `DEC-2026-11-02-01`：Step 3 客戶裁示後），正式上限在此確認；且它與 `EXP-3` 上限 3 為兩個獨立元件、選取不互通（**更正**：轉述的「EXP-3 上限 4」不成立，見第 9.3 節）。
- A：核准方向，實作前每批仍附精確 wireframe。B：逐頁另審。C：維持現況。
- 優點：A 方向一次定、精確版面仍逐批送審；B 每頁單獨權衡；C 不動已核准的 Batch C／D。
- 風險：A 會一次覆議 D1，Batch C 已實作的版面要重排；B 多次往返；C 讓 🌍 看不到 TAIEX 與 S&P 500 的相對走勢、💼 容許帶仍只有文字。
- **推薦 A，但 (1)(2) 請客戶明確表態是否覆議 D1**：(3)～(5) 不改既有裁示（(3)、(5) 是新增數量限制，請一併確認）；(1) 是改既有裁示，不得被「核准方向」一語帶過。

**UI-13 歸一化基準值（1 或 100）**
- 背景：🔍 已核准的 78（`DEC-2026-11-01-02` 第 2 部分原則通過）寫「歸一化起點＝1」；客戶 2026-11-02 任務第 30 節「找基金 Primary Visual 建議：Normalized NAV，Base = 100」（逐字見 `docs/evidence/decisions/2026-11-02_final_ui_contract_freeze_assignment.md`，以該檔為準）。
- A：採 100，跨頁一致；採用後在 78 就地加註。B：維持 78 的 1。C：各頁自選。
- 優點：A 符合客戶最新建議、與 🌍 比較圖一致；B 不動已核准線框；C 無。
- 風險：A 要在 78 加註一行；B 與客戶 2026-11-02 建議不一致；C 違反 44 之十八其四「各頁不得各自不同」的同一精神。
- **推薦 A**：基準值 1 或 100 只是顯示尺度、不改語意；採 100 跟隨客戶最新建議並跨頁一致。**Batch E 不以本題為前置：本題裁示前，Batch E 的基準值沿用 78 的 1；Batch E 的開工時點仍依 `DEC-2026-11-02-01`（Step 3 客戶裁示後才開始 Step 4）。**

**UI-14 🤖 版面四區（含 Maximum Falsification）**
- 背景：67 第 6.1 節固定輸出為市場、資產、持股、候選各一句＋主要風險 1～3＋本期行動 ≤3；本檔第 9.4 節的四區分隔（System State／OneBrain Interpretation／Maximum Falsification／Evidence）超出該固定輸出，Maximum Falsification 為新增內容。
- A：方向核准，Phase 7 實作時出線框再定。B：現在定版面。C：不採，維持 67 第 6.1 節原樣。
- 優點：A 先定「deterministic 與 AI 分區、要有反證」的方向；B 線框提早定；C 不增加輸出。
- 風險：A Phase 7 前沒有精確版面；B 為未啟用的頁先定版面，可能與 Digest 實作不合；C 讓使用者分不清哪句是規則、哪句是 AI，也看不到推翻條件。
- **推薦 A（方向核准、實作時出線框）**。

---

## 14. Implementation Sequence（提案）

| Step | 內容 | 前置 |
|---|---|---|
| 1 | 收斂 #1117（本輪）——**已完成（#1117，main `52da0cab`）** | — |
| 2 | Final UI Contract Freeze（本檔，本輪） | — |
| 3 | 客戶一次性裁示 UI-1～UI-10、UI-12～UI-14 | 本檔 |
| 4 | Batch E production：MoneyDJ code 主入口、ISIN「尚未啟用」、歸一化 NAV session-only 比較 | **`DEC-2026-11-01-02` 已核准範圍；內容不以 UI-3／UI-12 為前置；開工時點依 `DEC-2026-11-02-01`（客戶 2026-11-02 第 55 節：Step 3 客戶裁示後才開始 Step 4）**；基準值裁示前沿用 78；78 未定上限；Batch E 實作暫以 3 檔為顯示上限（與 Visual Budget ≤3 series 一致），正式上限由 UI-12 確認，不以本題為前置 |
| 5 | Batch F：⚙️ source health、Rule Registry 唯讀殼 | UI-10；殼的欄位待 Rule ID 格式 |
| 6 | Decision Digest production | UI-1、UI-8、UI-9；BL-0527 |
| 7 | Risk Cap／deterministic action rules | BL-0495／0496 Formula Gate（非機械式） |
| 8 | OneBrain Provider／Cache／Trace／Budget（自 75 OB-B fake provider 起） | 75 第 18.2 節；BL-0529 |
| 9 | OneBrain controlled integration | OB-C～OB-E；客戶授權 |

| 核准後即可機械式實作（不含語意） | 核准方向後仍需逐批線框／格式裁示 | 不可機械式（另走 Gate） |
|---|---|---|
| Missing 語彙統一為 `◇ 資料未備`（含 `ui_v2/mkt/chart.py::TEXT_EMPTY` 與 `market_section` 狀態字表；依 44 之十九其五第 4 條，已於 `DEC-2026-11-02-01` 落盤（同批）；開工時點依 `DEC-2026-11-02-01`（Step 3 後）、需客戶開實作批） | annotation 中 as_of／source／freshness／missing 標示框架（不含 threshold） | regime aggregation rule |
| Batch E（`DEC-2026-11-01-02` 已核准範圍；開工時點依 `DEC-2026-11-02-01`（Step 3 後）） | 💼 容許帶視覺（端點歸屬未定，見 `ui_v2/alo/fixtures.py` 檔頭） | 任何 threshold 值（含 VIX、freshness） |
| — | Rule Registry 唯讀殼 | Risk Cap 數值、作用層級與輸出 |
| — | 🤖 版面（UI-14） | action trigger；System Action State 本身的定義 |
| — | — | Rule ID／rule_version／門檻引用格式 |
| — | — | 歸一化基準日選法與基準點缺值處理（射程是跨頁通用規則，屬 UI-3；Batch E 在 78 範圍內採 deterministic、可重現、並於圖下揭露的基準日即可，不以本題為前置；開工時點仍依 Step 3 客戶裁示） |
| — | — | Digest schema 版本與 fingerprint |
| — | — | 情境指數資料源（BL-0501） |
| — | — | calibration contract 與任何機率輸出；OneBrain runtime；新 source；writer；DG2 |

**Model／Effort**（依 `PROJECT_RULES.md` 5.1，不寫模型名）：Step 4、5 與機械式項可用較省設定；Step 6～9 中涉及 data semantics、Risk Cap、AI decision semantics 者需較高設定，開工前依 5.1 判斷。

---

## 15. Cleanup plan（只列候選與依據，不處置）

| # | 候選 | 依據／說明 |
|---|---|---|
| 1 | 75 第 10 節 structured output 示意含 `confidence` | 與 58 U-25、67 第 5.3 節（不納入）、C-2 的張力；75 本身已寫「未定義不得上 production」，建議補一行指向 C-2 |
| 2 | ⬜／◇ 資料未備不一致 | 客戶 2026-11-02 第 48 節表態＋44 之十九其五第 4 條正式字樣；已於 `DEC-2026-11-02-01` 落盤（同批），機械式修正見 BL-0532（第 11 節） |
| 3 | `docs/v2/52` 儲備規格（雙軸、寫死 80% 門檻） | 【F-轉述】待複核；與 UI-3、UI-4 推薦方向牴觸，應標 superseded 或註記 |
| 4 | `docs/v2/78` G-E 區 | `DEC-2026-11-01-02` 後屬裁示前原文，已就地加註（別組進行中）；UI-13 若採 A，另在 78 歸一化起點處加註 |
| 5 | `docs/v2/77` 緊急快照 | 已過期，屬歷史 |
| 6 | `docs/HANDOFF.md` Resume Checkpoint | 「唯一下一接手點」多處疊加（違反 Supersession hygiene「不允許兩個看似同時有效的版本並存」，`PROJECT_RULES.md` 0.5） |
| 7 | BL-0529 下的 OB-01～OB-10 | 未編正式 BL（75 第 16 節）；依 13.4 第 3 條，可維持為 BL-0529 subtask，不必拆 |
| 8 | `ui_v2/shell.py` docstring「五項」 | 與 `PAGES` 四項不一致【F-重驗】；措辭修正 |
| 9 | `docs/v2/56`、`docs/v2/60` | 已被取代的提案，確認是否已標 superseded |
| 10 | 轉述「EXP-3 上限 4」 | 本檔已更正為 3；總管後續派工單請勿沿用 |
| 11 | BL-0528：A 線 AI 仍產生減碼與比例建議 | 與 C-1（唯一動作權威）張力；處置仍待 BL-0528 客戶裁示，本檔不處置 |

---

## 16. 產出者聲明與未驗證清單

**本組自己重驗的（讀檔或搜尋，基準 `0d2e05f3`，該 commit 的 `ui_v2/`、`services/`、`shared/` 與 `20bf6442` 相同）**
- `ui_v2/app_preview.py::PAGES` 四列（mkt、ast、exp、set），無 🤖；`ui_v2/shell.py` docstring 寫「五項」。
- `ui_v2/mkt/overview.py::DEFAULT_PRIMARY`＝`taiex`，`PRIMARY_KEYS` 五序列；`ui_v2/mkt/chart.py::DEFAULT_PERIOD`＝`1Y`、`PERIODS`＝3M／6M／1Y／3Y。
- `ui_v2/mkt/market_section.py::TEXT_NO_CONCLUSION`＝「暫無完整市場綜合判定（缺正式 aggregation rule）」（轉述少了「正式」二字）；`TEXT_FRESHNESS_THRESHOLD` 含「⬜ 門檻待裁示」；狀態字表 `STATE_MISSING` 對到「⬜ 資料未備」。
- `ui_v2/exp/logic.py::COMPARE_LIMIT`＝3，44 `EXP-3` 規則欄「同時最多對照 3 檔」—— **更正轉述的 4**。
- `ui_v2/thresholds.py::NAV_NOT_READY_DAYS`＝10；`shared/macro_buckets.py::_VIX_YELLOW`＝22.0、`_VIX_RED`＝30.0；`services/macro/us_indicators.py::_VIX_SNAPSHOT_CALM`＝18.0。
- 以 git grep 於 `0d2e05f3` 搜 `infra.llm`、`ai_service`：`ui_v2/` 下無命中。
- 以 git grep 於 `0d2e05f3` 搜 rule_id 類字樣：唯一命中是 `ui_v2/exp/page.py::_next_rule_id`，那是篩選條件列的列序號，**不是決策規則 ID**；轉述的「rule_id 程式查無」讀作「沒有決策規則 ID」才精確。
- `ui_v2/asset/page_status.py`、`ui_v2/status_class.py` 檔頭明寫頭條不是 rule result、不進 Decision Digest。
- `services/v2_tables/market_indicator.py` 有 `release_date`、`is_revised`。
- （修訂輪補）`ui_v2/mkt/overview.py::SECONDARY_RISK_TITLE`＝「風險｜VIX」、`SECONDARY_INTL_TITLE`＝「國際｜S&P 500」；`ui_v2/mkt/chart.py::TEXT_EMPTY`＝「⬜ 資料未取得，無法繪圖」；`services/macro/tw_local.py` 的 VIX 計分帶切點 15／20／25／30；`shared/signal_thresholds.py::LADDER235_VIX_L1`～`L3`＝20／25／30；`ui_v2/alo/fixtures.py` 檔頭登記容許帶端點未定（`ALO-GAP-端點`）；78 線框寫「歸一化，起點＝1」、未寫比較上限；`815fb88e` 為 #1117 上 `DEC-2026-11-01-02` 落盤 commit；44 之十八其三第 3、5 條與之十八其十、其十一第 3 條原文；66 第 4.6 節六項必顯示資訊。
- `tests/visual_fidelity/vf_config.py::VIEWPORTS` 含 1280×800；`tests/visual_fidelity/layout_checks.py` V7＝Primary 在首屏。
- 正式文件：44 之十八其三與其四、之十九其一之一與其五、之二十；67 第 1～7 節；75 第 5～12、15～18 節；66 第 3.1 節；`DEC-2026-10-27-14`、`-40`、`DEC-2026-10-30-01`、`DEC-2026-10-31-01`、`DEC-2026-11-01-02` 摘要（逐字檔本組未讀）。

**本組沒有重驗的（照轉述，標【F-轉述】者）**
- 🌍 Secondary 三張迷你圖的序列與 chips 數；無頁級日期；`MKT-1`～`MKT-7` 位置。
- 💼 summary strip 四格皆 `◇ 資料未備`；Primary 為 HTML 條、容許帶只以文字出現；Secondary 恰 2；9 項 Missing；容許帶無預設值。
- 🔍 無代碼／ISIN 搜尋輸入；禁欄現況。
- ⚙️ 各區塊現況、`set_max_age_days`、無 rule registry、無 digest viewer。
- 全 ui_v2 圖表無 threshold／band／reference line；ui_v2 無 AI 文字、機率、信心、AI score、排名（本組只重驗了 import 與 rule_id 兩項）。
- 「VIX 15/25/40」「VIX>50」程式與正式文件查無。
- 市場域 dict 欄位（source、fetched_at、obs_date、reason_code、value_unit）、`source_tier` 為 4 類別。
- `docs/v2/52` 雙軸與 80% 門檻；`DEC-2026-10-26-01` 原文（本組只經 44 之十九其五第 5 條間接確認不一致存在）。
- 🌍 是否實際出現兩套符號並存（未實跑畫面）。

**修訂輪說明**：稽核 B1～B4 與必修項由本組逐項修正；B3、B4 與必修項的事實面本組已讀檔確認（如上），但修正後全文**仍未經第二組複驗**。另經獨立稽核：首輪 4 blocker 已修、複核無 blocker（總管回報）。

**全稱句揭露**：本檔中「查無」「無」類敘述凡標【F-轉述】者，皆取決於盤點組有沒有漏看，本組不宣稱窮舉。第 2、4～8、13 節的提案與推薦為文件組整理、總管推薦，可被客戶推翻。

---

## 17. UI-15 增量補充｜配息行事曆與 LINE Information／Event Notification（提案；⛔ 待客戶裁示）

> **定位與 supersession**：本節是客戶 2026-11-02 對同一份 Final UI Proposal 的缺口補充，**不是第二套規格**。它只增補／修正本檔第 1、7～9、12～14 節中與「配息行事曆／通知」相關的空白；第 9.5 節原句「notifications｜repo 內新版無既有功能 → 標未定義，本檔不提案」自本節起讀作：**新 UI 尚未定義／未實作，但 repo 舊線已有可重用的 informational dividend-calendar／LINE capability，故納入 UI-15 proposal；directional/action notification 仍排除。** 本節不構成 UI-15 裁示，也不授權任何 production migration。

### 17.1 GitHub inventory：既有能力與嚴格邊界

| 能力 | GitHub 實況 | 本提案定位 |
|---|---|---|
| 配息／除息行事曆 L2 | `services/dividend_calendar.py`：純 deterministic、零 I/O；以**單一基金自己的歷史**辨識月／季／半年／年／irregular 節奏，推估基準日與發放日；樣本／重現不足時棄權；沒有 `pay_date` 歷史時不硬編 | **Existing legacy capability／migration required**；保留，未來定位為 **Dividend Date Fallback Estimation Engine** |
| Calendar renderer | `services/dividend_calendar_render.py`：App 與 LINE 共用 HTML renderer；v19.533 起畫面不再直接顯示 high／medium／low confidence，而以逐檔 error band／「僅供參考」呈現 | **Existing legacy capability／migration required**；不因 Final UI freeze 刪除 |
| App calendar | `docs/DIVIDEND_CALENDAR_SETUP.md`：舊 UI「我的管理室 → 除息行事曆」可看本月月曆 | **Existing legacy capability／New UI not implemented** |
| 月底 LINE 摘要 | `.github/workflows/dividend_calendar_notify.yml`＋`scripts/dividend_calendar_notify.py`：現行 cron 為每月 28 日 00:23 UTC（台灣 08:23）產生**下個月**摘要；支援 `workflow_dispatch`、`dry_run`、`target_month`；測試鎖住 cron／target-month pairing | **Existing legacy capability／migration required**；本輪不改 cron、不新增 reminder schedule |
| LINE transport | `infra/line_push.py`：Messaging API push，token／user id fail-loud，支援 text／flex／image、dry-run；不把 token 寫入回傳訊息 | **Existing infrastructure**；只視為 delivery transport，不是投資規則 |
| 「actual」接縫 | `actual_ex_for_month`／notify path 會把目標月已有歷史實際紀錄的事件標 `is_actual=True`；現有 renderer 未完整區分 actual／estimate，repo 已登記為已知接縫 | **不得直接映射成本提案的 `confirmed`**：`is_actual` 只證明既有資料內有實際紀錄；若沒有可追溯 authority／announcement provenance，不足以宣稱「官方已確認」 |
| 舊 LINE 換股／action 通報 | `ui/tab_manage.py::_sec_notify`、`services.switch_notify` 等舊線存在換股／行動相關通知；62 F5 已把 calendar 與 directional notification 同時盤出 | **嚴格排除本輪 migration**：不因 LINE capability 重用而恢復到 New UI；只登記於既有 directional／Phase 5～8 邊界 |

**兩類 LINE 永久分離（本提案請求核准此邊界）**：

1. **Information／Event Notification**：配息基準日、除息日、基金發放日、日期異動、資料缺失、推估升級為正式公告、配息行事曆。這些是 facts／event state，不是投資動作。
2. **Directional／Action Notification**：換股、加碼、減碼、賣出、switch recommendation、action advice。**本輪不得恢復**；未來只能在 Deterministic Rules → Risk Cap → System Action State → 正式 action vocabulary → OneBrain controlled integration 邊界成立後另走 Gate。

### 17.2 UI Ownership Contract（提案；不增加第六頁）

| 能力 | 唯一 owner page | 第一階段 proposal | 明確不做 |
|---|---|---|---|
| **配息行事曆** | 💼 我的資產 | 放 **Secondary／detail area**，或一個「查看配息行事曆」CTA；可呈現本月／下月、已確認／已排定／推估／資料未備數量、逐檔日期狀態、drill-down 與來源 | 不塞進第一屏；不建立第六頁；不因 calendar 產生投資 action |
| **Notification Preferences** | ⚙️ 設定 | LINE 配息提醒開關、月底下月摘要、正式日期變更提醒、發放日前提醒等**政策 proposal**；具體 cadence 待裁 | 不讓使用者在通知設定修改 Risk Cap、action rule、threshold |
| **Delivery Health／Audit** | ⚙️ 設定 | LINE connection／delivery health、最近成功推播時間、最近失敗原因、測試通知、唯讀 audit | 不顯示／保存 LINE access token、secret、credential raw value |

**版面 Gate**：💼 具體擺放位置與 ⚙️ 通知區元件仍須 wireframe Gate；UI-15 只定 ownership 與 contract boundary，不定 production layout。

### 17.3 Dividend Event Date Contract（提案）

至少分四個概念，**不得混稱**：

| Concept | 中文語意 | Contract |
|---|---|---|
| `record_date` | 配息基準日 | 基金名冊／配息資格的基準日期 |
| `ex_dividend_date` | 除息日 | 除息事件日期；不得與 record date 合併成同一欄 |
| `payment_date` | 基金公司／基金正式發放日 | **只代表基金端正式發放日**；不得稱「實際銀行入帳日」 |
| `estimated_bank_credit_window` | 預估銀行／平台實際入帳區間 | 只有未來有可支持的 deterministic contract 才能填；repo 現有 `pay_date`／`pay_window` **不得自動升格成銀行實際入帳事實**；沒有銀行／平台實際事件資料時為 Missing |

**Legacy semantic gap**：現行 setup／renderer 有「入帳(估)」與 pay-window 語彙。這是舊線既存語意，**本輪不改 production copy／code**；Final UI migration 必須先依上表拆開 `payment_date` 與 bank credit window，再決定新 UI 字樣。

### 17.4 Date Status Contract（提案；domain status ≠ 第二套 Missing copy）

候選 domain 值：`confirmed`／`scheduled`／`estimated`／`unavailable`。

| status | 語意 | 不得推論 |
|---|---|---|
| `confirmed` | 可追溯的正式資料已確認且日期確定 | 不得只因 legacy `is_actual=True` 就自動成立；仍需 authority／provenance |
| `scheduled` | 正式來源已公布預定日期，但來源本身仍保留變更可能 | 不等於 confirmed |
| `estimated` | 正式日期尚未取得；由既有 deterministic 歷史推估引擎估算 | 不得升格成 confirmed／scheduled；不屬 LLM 判斷 |
| `unavailable` | 沒有足夠證據／資料可給日期 | UI 呈現仍沿用本檔第 11 節正式 Missing contract：`◇ 資料未備`，**不新增第四套 Missing 文案** |

【F-重驗】repo 目前有 `is_actual`、`confidence`、`estimate_error_band` 等 legacy 欄位／內部訊號，但**查無一個已核准、可直接等同上述四態的正式 date-status contract**。因此這四態仍是 UI-15 的 contract proposal；production copy／symbol 若與 44／79 既有字表衝突，以正式 SSOT 為準，另在同一 UI-15 裁示後的 wireframe Gate 定字，不自行創第二套。

### 17.5 Source Precedence（只定方向；本輪不新增 source）

```text
Official confirmed／scheduled source
  ↓
Existing approved authoritative structured source
  ↓
Existing approved secondary structured source
  ↓
Historical deterministic estimation
  ↓
Unavailable
```

- **已有正式日期時，不得再用推估覆蓋。**
- **推估值不得升格成 `confirmed`。**
- repo 目前的 calendar engine 主要讀既有基金配息歷史；本輪**不宣稱已有可直接支撐 `confirmed／scheduled` 的官方日期來源鏈**。
- 新增任何外部 source、或把既有 source 升格為新的 authority／precedence，必須另走 **Data Source Decision Gate**；UI-15 不授權 integration。
- 同一事件不同來源衝突時，先保留 provenance／unresolved；不得用名稱、AI 或猜測補 identity／date。

### 17.6 Existing Estimation Engine 的正式候選定位

`services.dividend_calendar.py` 不刪除；提案定位為 **Dividend Date Fallback Estimation Engine**：只在更高 precedence 的正式日期尚未取得時使用。

保留的 deterministic 特性：
- 只用該基金自己的歷史，不借其他基金的日期間隔。
- 月／季／半年／年／irregular 節奏辨識；無可重現 anchor 時棄權。
- 發放日估算只用該基金歷史 base／record → pay gap；沒有 pay history 時不硬編。
- 樣本少、重現度低時降低 engine confidence／直接棄權。
- 已有正式／較高 precedence date 後，fallback estimate 不得覆蓋。

**C-2 對齊**：現行 engine 的 `confidence` 是 deterministic 內部 gating evidence，不是 LLM 自估機率；renderer 自 v19.534 已停止直接顯示 high／medium／low confidence，改以 historical walk-forward error band／「僅供參考」呈現。Final UI **不得把 `confidence` 當成未校準成功機率或 AI 信心值**。若未來要外露，候選名稱優先研究 `evidence quality`／`estimation reliability`；production 字樣仍需 Gate。可追溯的 `evidence_count`、error window、estimation method 可作 objective evidence；不得把它們轉譯成未經 calibration 的「成功率」。

### 17.7 Field-Level Provenance＋Revision Contract（proposal）

每個 Dividend Event date field 至少研究以下欄位；來源沒有就 Missing，不虛構：

`fund_identity`、`event_type`、`event_date`、`date_status`、`source`、`source_url／source_ref`、`as_of`、`retrieved_at`、`announcement_date`、`is_revised`、`previous_value`、`estimation_method`、`evidence_count`。

**Revision transitions**（示意 contract，不是 UI 文案）：
- `estimated → scheduled → confirmed`
- `scheduled(old) → scheduled(new)`
- `confirmed(old) → corrected confirmed(new)`

每次 revision 至少能追：previous date、new date、source、update timestamp、change reason（**只有來源有提供才存；沒有就 Missing**）。不得覆寫到看不出舊值，也不得因 estimate 被正式日期取代就刪掉估算 provenance。

### 17.8 LINE semantic-change notification／Monthly Summary／Reminder Policy

**Change notification proposal**：資料刷新本身不構成通知事件；只有真正的 semantic change 才可發「異動通知」。例如 estimated → confirmed、scheduled date 變更、confirmed correction、Missing → 正式日期。未來 implementation 必須具備 dedupe、idempotency、同一版本不重發、retry 不造成重複通知；fingerprint／delivery key 到 implementation batch 再定，**本輪不實作**。

**月底下月摘要 use case 保留**：現有月排程的使用情境保留為 proposal，但未來摘要應能分：已確認／已排定／推估／資料未備。實際 icon／字樣若與 44／本檔第 11 節衝突，以正式 Missing SSOT 為準；本節不自行定 production copy。

**Notification Policy Proposal（cadence 待客戶裁示）**：
- 月底產生下月行事曆（legacy capability）。
- 正式公告出現時是否即時更新／通知。
- 日期真正發生變動時是否推播。
- 是否需要 T-7／T-1 reminder。
- 是否只提醒持有基金，或也含 watchlist。

本輪**不新增 T-30／T-14／T-7／T-1 cron，不修改現有 cron**。

### 17.9 Delivery Audit（⚙️ 唯讀 proposal）

至少研究欄位：`notification_id`、`notification_type`、`target_period`、`generated_at`、`data_fingerprint`、`channel`、`delivery_status`、`delivered_at`、`retry_count`、`error_class`。

- audit 只記 delivery metadata／結果，不存 `LINE_CHANNEL_TOKEN`、`LINE_CHANNEL_ACCESS_TOKEN`、`LINE_USER_ID` 的 raw secret／credential 值。
- 「測試通知」是 delivery test，不是投資建議測試；不得觸發 action rule。
- preference 只控制「是否通知／怎麼通知」，**Notification preference ≠ 投資規則**。

### 17.10 Decision Digest／OneBrain boundary

若未來 Dividend Event 會影響 cash-flow reasoning，**objective facts** 可以是 Decision Digest 候選輸入：record date、ex-dividend date、confirmed／scheduled／estimated state、payment date、Missing、provenance、revision。是否納入 Required／Optional 仍隨 Digest schema Gate。

以下 **delivery metadata 必須 Excluded**，不得進投資 Decision Digest／OneBrain fingerprint：LINE 是否已送達／已讀、notification retry count、Flex／PNG renderer metadata、delivery channel health、widget state。這些屬 notification infrastructure／audit，不得污染投資推理 fingerprint。

### 17.11 Final UI Gap Matrix 增量（amends §12；不是「新版已完成」）

| Page | Capability | Contract status | Production status | Legacy evidence | Migration gap |
|---|---|---|---|---|---|
| 💼 我的資產 | Dividend Calendar；Dividend Event Date Contract；confirmed／scheduled／estimated distinction；source／provenance；future official-date upgrade | **defined as proposal／UI-15 pending** | **not implemented in New UI** | App calendar＋L2 estimator／renderer 已存在 | ownership、date semantics、status、provenance、revision、wireframe、official-source research／Gate |
| ⚙️ 設定 | Notification Preferences；LINE delivery health；notification audit；test notification | **defined as proposal／UI-15 pending** | **not implemented in New UI** | LINE transport＋monthly workflow／dry-run 已存在 | preference model、health／audit schema、idempotency、wireframe；不得含 action-rule controls |

**與 62／BACKLOG 的 anti-bloat 對位**：62 F5 已盤出「除息行事曆」與「LINE 換股通報」兩種舊能力；BL-0401 已承接 directional／action 類 Phase 5～8，不得拿來當 informational calendar migration 的授權。Final UI proposal 的 Gate 工作直接掛 **BL-0531 子項 UI-15**，本輪**不新增 BL**；UI-15 核准後若真的需要 official-source research／calendar migration／notification audit implementation，再依 Anti-Bloat 檢查既有列後決定是否開最少必要 BL。

### 17.12 UI-15｜配息行事曆與 LINE 通知如何納入 Final UI？（⛔ 待客戶裁示）

- **A（推薦）**：💼 我的資產擁有配息行事曆；⚙️ 設定擁有通知偏好／delivery health／audit；正式日期優先、歷史 deterministic estimation 只 fallback；保留月底下月 LINE 摘要 use case；日期 semantic change 可作未來通知；directional／action LINE **不在本輪恢復**。具體 layout、status production copy、reminder cadence、fingerprint／delivery key、任何新 source 都另走既有 Gate。
- **B**：只保留 LINE 月底摘要 use case，不把 calendar 正式納入 New UI。
- **C**：全部延後，不納入 Final UI Freeze。

**推薦 A**：這是 repo 已存在、且對持有基金的現金流事件有直接使用價值的 capability；如果 Final UI Freeze 完全不登記，後續 migration 很容易因「新版 notifications 未定義」而把既有能力遺失。A 只凍結 ownership／semantic boundary／migration contract，**不等於授權 production migration**。

### 17.13 Implementation Sequence amendment／本輪禁止事項

- 第 14 節 Step 3 的「一次性裁示」增補 **UI-15**；UI-11 仍不重問。
- UI-15 裁示前不開始 calendar／notification production migration；即使 A 核准，下一步仍是 wireframe／contract batch，而不是直接寫 production。
- 本輪禁止修改：production code、LINE workflow／cron、secrets、新 source／provider、Risk Cap、action trigger、OneBrain runtime、frozen 44、舊 LINE directional／action production。
- 本輪只做：**inventory＋contract proposal＋Gap registration＋Decision Gate**。

### 17.14 UI-15 delta audit checklist

後續真正獨立稽核至少逐項確認：
1. 沒有把 directional／action LINE 通報偷帶回 New UI。
2. 沒有新增／升格任何 source authority。
3. `estimated` 沒有被寫成 `confirmed`；legacy `is_actual` 沒有無條件等同「官方確認」。
4. `payment_date` 沒有被稱為實際銀行／平台入帳日；bank credit 無實際事件資料時保持 Missing。
5. 沒有建立第二套 Missing／status presentation vocabulary；`unavailable` 最終仍映射既有 `◇ 資料未備` presentation contract。
6. engine `confidence` 沒有變成未校準機率／LLM 信心；error band／evidence 仍標 deterministic evidence。
7. notification delivery metadata 沒有進 Decision Digest／OneBrain fingerprint。
8. BL-0531／HANDOFF／本檔 UI-15 對位一致；本輪沒有新增碎片化 BL。
