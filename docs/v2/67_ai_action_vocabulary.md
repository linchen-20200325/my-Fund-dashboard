# 67｜AI 行動語意 SSOT 與 One AI Brain（2026-10-27）

> ⛔ **狀態：語意邊界 SSOT（客戶 2026-10-27 裁示）／不構成任何實作授權。**
> 本檔只定六個行動詞的**語意邊界**與 One AI Brain 的**結構**；客戶原話：「本輪先定義「語意邊界」。」「不要自行發明數值 threshold。」本檔**不含任何數值門檻、切點、權重或分數**。
> 客戶原話：「不要在正式公式／Risk Cap／trigger 尚未完成前做假的 AI 投資建議。」

- **建立日**：2026-10-27。**量測基準**：main `c1d4ecab`。程式位置寫「檔案::符號」，不寫行號；會漂移，引用前請現場重查。
- **決策出處**：`docs/DECISIONS.md` `DEC-2026-10-27-22`（六個行動語意）、`DEC-2026-10-27-18`（One AI Brain）、`DEC-2026-10-27-14`（Gate 7A：有限 supersede 與固定鏈）。逐字存檔 `docs/evidence/decisions/2026-10-27_vnext_gate_rulings.md` 第四、七、八節。
- **位階**：受 `CLAUDE.md` §-2 ＋ §-1.5 ＋ §-1 與 `PROJECT_RULES.md` 管轄；**不凌駕** `docs/v2/44_fund_ui_ssot.md`（凍結 SSOT）與子法 1（併讀 `docs/v2/57` 正式修正案 #8）。方向性輸出的准入仍依 44 第七節第三小節之四其二的三條件（正式規格經客戶核准、證據足夠、新鮮度與出處合格）與 `DEC-2026-10-16-08`；本檔是那個「正式規格」中**語意**的部分，不是它的全部。
- **待辦登記**：`docs/BACKLOG.md` BL-0495（Risk Cap 正式定義）、BL-0496（減碼 deterministic trigger 定義）、BL-0490（批次 7 One AI Brain integration）。登記不構成動工授權。
- 📌 **2026-10-29 增補**（`DEC-2026-10-29-06`）：第 5 節 Decision Digest Contract（最小契約）、第 6 節 One AI Brain contract 整合、第 7 節揭露；第 1～4 節原文一字未改。待辦另見 ~~BL-0526（AI 投資總結入口形式 Gate）~~〔2026-10-29 已裁示方案 C，見第 6.1 節，`DEC-2026-10-29-07`〕、BL-0527（Digest 缺口與守衛）。

---

## 1. 固定鏈與現行可用性

**新允許的輸出一律必須來自（客戶逐字）**：

```text
Raw Data → Validate → Normalize → Domain / Formula → Deterministic Rules → Risk Cap → AI Explanation
```

| 環節 | repo 現況（量測 `c1d4ecab`；文件組單組讀檔，不宣稱窮舉） |
|---|---|
| Raw Data → Validate → Normalize | B 線各頁已有部分（例：`services/v2_tables/market_indicator.py::INDICATOR_SPECS`）；各頁資料缺口見 `docs/design/vnext_visual_blueprint.md` 第 8.11 節 |
| Domain / Formula | 部分已定（例：台股 EPS × PE，`docs/v2/66` 第 4 節）；多項未定（規格第 8 節 `G-FORM` 列） |
| Deterministic Rules | 六個行動詞的觸發規則**未定義**（含減碼 trigger，BL-0496；「正式降低部位條件」同樣未定義） |
| Risk Cap | **未定義**：repo 內只以名稱出現，沒有定義、公式、門檻或資料欄位（規格 `AI-5`；BL-0495） |
| AI Explanation | B 線現無 AI（44 第七節第三小節之四其六）；結構見第 3 節 |

**⇒ 現行可用性（文件組讀法，可被客戶推翻）**：在 Deterministic Rules 與 Risk Cap 正式定義並經客戶裁示之前，系統可以產生的行動詞**只有「無法判定」**；其餘五詞的定義本身就引用了尚未存在的正式規則或 Risk Cap，不得由 AI 或 UI 自行填補。現有守衛（例：`ui_v2/**/logic.py::FORBIDDEN_DIRECTION_WORDS`、`tests/test_no_direct_trade_advice_20260914.py`）本檔不改；何時、如何調整，隨正式規則的實作批一起處理。

---

## 2. 六個行動詞（語意邊界 SSOT）

> 「代表」「不代表」「必須顯示」「前提」「至少比較」各欄以客戶原話為準（逐字存檔第七節）；「層級」與「本檔補充」為文件組整理，可被客戶推翻。

### 2.1 續抱

| 欄 | 內容 |
|---|---|
| 代表（客戶原話） | 目前正式規則與 Risk Cap 沒有要求降低部位，且資料完整度足以判定。 |
| 不代表（客戶原話） | 加碼；強烈看多；保證上漲。 |
| 層級 | 單一基金／單一部位 |
| 前提（本檔補充） | 正式規則存在且已評估；Risk Cap 存在且已評估；資料完整度足以判定。三者任一不成立 → 「無法判定」，**不是**續抱（見 2.6）。 |

### 2.2 觀察

| 欄 | 內容 |
|---|---|
| 代表（客戶原話） | 出現值得追蹤的惡化／不確定因素，但尚未達正式降低部位條件。 |
| 必須顯示（客戶原話） | 觀察原因；相關指標；下一個需要確認的條件。 |
| 層級 | 單一基金或組合（文件組讀法） |
| 本檔補充 | 「正式降低部位條件」未定義前，觀察與降低曝險／減碼的分界不存在，故不得產生（第 1 節）。觀察不是行動指令。 |

### 2.3 降低曝險

| 欄 | 內容 |
|---|---|
| 層級（客戶原話） | 屬 portfolio／asset-class／region／style 層級。 |
| 代表（客戶原話） | 某類型曝險過高或風險環境改變，建議降低該 exposure。 |
| 不代表（客戶原話） | 不等同指定單一基金一定要賣。 |
| 本檔補充 | 依賴類型／區域／風格的可靠 mapping（規格 `AL-5`～`AL-7`、`HL-6`，多為 `G-DATA`）與曝險判定規則；mapping 不可靠時該類型「無法判定」，不得以基金名稱猜屬性（`DEC-2026-10-23-10` (5)）。不得變成 AI 自行決定的資產水位或持股比例（`DEC-2026-10-27-14` 仍然禁止項）。 |

### 2.4 減碼

| 欄 | 內容 |
|---|---|
| 層級（客戶原話） | 屬單一基金／單一部位的具體方向性動作。 |
| 正式使用前必須有（客戶原話） | deterministic trigger；足夠資料；Risk Cap；可追溯依據。 |
| 限制（客戶原話） | trigger 尚未正式定義前，AI 不得自行決定減碼。 |
| 本檔補充 | 四項前提缺一 → 不得輸出減碼；改顯示「無法判定」（「觀察」須另有其正式條件）。trigger 的定義屬 BL-0496，需客戶裁示；本檔不定任何數值。Missing／Unknown 不得經單軸訊號重新產生減碼（`DEC-2026-10-24-10`、`-12`）。 |

### 2.5 替代比較

| 欄 | 內容 |
|---|---|
| 代表（客戶原話） | 現有基金出現弱化／不適配，且候選池存在可比較標的，進入 replacement comparison。 |
| 不代表（客戶原話） | 不代表 AI 自動換基金。 |
| 至少比較（客戶原話） | 原基金；候選基金；類型；風險；績效／回撤；配置影響；資料完整度。 |
| 本檔補充 | 「弱化／不適配」的判定規則未定義；候選池定義待 `docs/v2/62` CAP-GATE-05（候選池／觀察清單是否同一份）。比較表中任一欄缺值顯示 Missing，不補值。比較的呈現不得冠「精選」「推薦」「最佳」（44 現行 🔍 規則；是否調整屬 `DEC-2026-10-27-13` 的 44 逐項解凍）。 |

### 2.6 無法判定

| 欄 | 內容 |
|---|---|
| 使用時機（客戶原話） | 當關鍵資料 Missing、stale、error，或規則所需證據不足。 |
| 正式規定（客戶原話） | 無法判定 ≠ 續抱；無法判定 ≠ 安全；無法判定 ≠ 中性。 |
| 本檔補充 | 也包括：正式規則或 Risk Cap 尚未定義（第 1 節）。畫面須說明缺的是什麼（資料未備／證據不足），沿用 44 既有字型「⬜ 無法判定（資料未備／證據不足）」（44 第七節第三小節之四其三）；不得以「正常」「中性」語氣或非灰色狀態色呈現，顏色不得是唯一語意載體（`PROJECT_RULES.md` 13.2 第 3 條）。 |

### 2.7 共通禁止（取自 `DEC-2026-10-27-14` 仍然禁止七項）

黑盒單一總分；用單一 0～100 分數決定市場好壞；AI 自己決定資產水位；AI 自己發明持股比例；AI 自己發明 threshold；關鍵資料不足仍硬給方向；AI 覆寫 deterministic rule。

---

## 3. One AI Brain, Many Data Views（`DEC-2026-10-27-18`）

### 3.1 結構

- **全站唯一 AI Brain**；不是每頁各有一個獨立 AI Brain（客戶原話）。
- **各頁只提供四種輸入**（客戶原話）：Data View、Domain Result、Rule Result、Local Explanation。
- **整合順序（客戶原話）**：市場 → 資產配置 → 持股 → 候選基金 → Missing／freshness → Risk Cap → 最終行動摘要。

### 3.2 固定六項輸出（客戶原話）

1. 市場
2. 配置
3. 持股
4. 候選基金
5. 主要風險
6. 本期最多 3 項行動

- 每一項未來須能展開「查看依據」（客戶原話：「每一項未來都必須能展開："查看依據"」）。句子 → evidence／rule 的對映格式未定義（規格 `AI-3`，`G-FORM`）。
- 第 6 項的行動詞只能取自第 2 節六詞，且受第 1 節現行可用性約束；Risk Cap 未定義前，第 6 項只能是「無法判定」並說明缺的是什麼（文件組讀法，可被客戶推翻）。
- 「一句話市場結論」不是單一總分，只是多個已計算結果的自然語言摘要（`DEC-2026-10-27-14` 客戶原話）。

### 3.3 AI 禁止事項（客戶原話）

AI 不得：自己生成市場數字；自己補 Missing；自己改 threshold；自己新增資料來源；自己改 Risk Cap；自己推翻 deterministic rule。

### 3.4 尚未定義（登記，不裁決）

| 項目 | 狀態 | 登記 |
|---|---|---|
| 四種輸入的 schema（輸入輸出 contract） | 未定義 | 規格 `AI-1`；BL-0490 |
| 模型與 provider 選擇、評估方式 | 未定義 | 規格 `AI-1`；BL-0490 |
| Risk Cap | **未定義**（repo 內無定義、公式、門檻或欄位） | 規格 `AI-5`；BL-0495 |
| 減碼 deterministic trigger；「正式降低部位條件」 | 未定義 | BL-0496 |
| 右側 AI 區的版面位置 | 屬 44 逐項解凍（`SH-4`） | `DEC-2026-10-27-13`；BL-0494 |

---

## 4. 本檔沒有查證的部分（誠實揭露）

1. 本檔由文件組單組寫成，**未經第二組獨立驗證**（`CLAUDE.md` §-2 規則 6）；屬 investment meaning 等級，依 `PROJECT_RULES.md` 第 8 節須至少 1 組真正獨立稽核。
2. 「Risk Cap 在 repo 內未定義」沿用規格 `AI-5` 的查找（文件組單組，取決於有沒有漏看，不宣稱窮舉）。
3. 第 1 節「現行可用性」、各詞「本檔補充」與第 3.2 節第 6 項的限制為文件組讀法，可被客戶推翻。
4. 客戶裁示經總管派工單轉達並逐字存檔，文件組未見客戶對話本身。

---

## 5. Decision Digest Contract（最小契約；客戶 2026-10-29，`DEC-2026-10-29-06`）

> **出處**：客戶 2026-10-29 第三則訊息第四～六、十、十五～十七節，逐字存檔 `docs/evidence/decisions/2026-10-29_presentation_contract_migration.md` 第三段圍欄。**本節是最小契約，不是 schema**：客戶原話「不要現在武斷建立全新巨大 schema。先盤點 repo 既有資料結構並設計最小契約。」既有結構的盤點（調查組 3，單組）摘要在 `docs/v2/71_presentation_contract_migration.md` 第八節。
> **為什麼落在本檔**：本檔是 One AI Brain 的現行正式規格（`DEC-2026-10-27-18` 的落點），Decision Digest 是 Brain 的輸入層，兩者放同一份才不會出現兩套 AI 規格；`docs/v2/54` 自述 Non-production，不適合當正式落點；`docs/v2/71` 是遷移盤點，不放規格（執行組判斷，可推翻）。

### 5.1 架構鏈與硬規則（客戶原話）

```text
Raw Sources → Canonical Data → Rules / Indicators / Risk Cap → Decision Digest → One AI Brain → UI Local Summary / AI 投資總結
```

- 與第 1 節固定鏈的關係（執行組讀法，可推翻）：兩條鏈同向。第 1 節的 `Raw Data → Validate → Normalize` 對應這裡的 Raw Sources → Canonical Data；`Domain / Formula → Deterministic Rules → Risk Cap` 對應 Rules／Indicators／Risk Cap；Decision Digest 是新插進 Risk Cap 與 AI 之間的一層，把前段結果整理成 AI 讀得到的結構化輸入。第 1 節的現行可用性（Rules 與 Risk Cap 未定義前只能「無法判定」）照舊。
- **Presentation Simplification must never reduce AI Decision Context.**（客戶原話）UI 可以壓縮、聚合、收合、少顯示欄位、少顯示圖表；但不得因此刪除或降低：canonical data、rule results、indicator results、Risk Cap inputs／outputs、provenance、source、as_of、stale、missing、confidence／quality state（若既有 contract 有）、identity、relevant history、AI Decision Context。
- **Data View ≠ Decision Context ≠ AI Output**（客戶原話）。UI 主畫面可以只顯示 5 個數字，Decision Digest 可以保留 30 項以上的有效資訊，One AI Brain 讀完整的 Decision Digest。不得因為「使用者看不到」就把資料從 AI context 移除；也不得因為「AI 需要」就把資料全部塞進 UI。

### 5.2 Decision Digest 的責任

1. 它是 AI 的完整、結構化決策輸入層，**不是 UI scrape**；由 canonical data＋正式規則結果直接建立（客戶原話）。
2. AI 不得：從 Streamlit widget 文字反推 canonical data；從顏色猜狀態；依 UI 隱藏或展開狀態決定讀不讀資料；因為 UI 沒顯示某指標就認定該資料不存在（客戶原話）。
3. 由盤點得出、本契約明寫的界線（執行組讀法，可推翻）：
   - B 線各頁的 page model（`ui_v2/*/logic.py` 產出的 block）屬呈現層；其中 `value_text` 是已格式化的字串，**不得當 Digest 的值來源**（值要回 canonical 表取）。
   - `◇`、`◆`、`⬜` 等符號是渲染結果（`ui_v2/symbols.py` 在渲染時才把狀態換成符號），**不是資料語意**；Digest 記的是狀態本身，不是符號。
   - 目前「規則結果」只有使用者門檻驅動的比較（`HLD-0` 偏離筆數、`ALO-0` 帶內帶外、`EXP` 篩選候選集），而且住在 L3 的 `ui_v2/*/logic.py`。它們是純函式、不是 widget，但屬呈現層；要不要先下沉到 domain／service 層再給 Digest 讀，是 Phase 7 前置的缺口（第 5.6 節），本契約不定。

### 5.3 每個可判斷項的最低概念欄位（客戶第六節）與 repo 既有承載

> 「既有承載」欄只說 repo 現在有什麼可以對上，不是指定欄名；量測 main `02615e41`，調查組 3 讀碼結果；執行組抽查四件：`value_text`（page model 只留格式化字串）、`rule_version`（零命中）、`build_ai_summary`（零命中，第 5.7 節）、B 線沒有 AI 呼叫（第 5.7 節），其餘照錄。

| 概念（客戶原文） | repo 既有承載 | 缺口 |
|---|---|---|
| identifier | `indicator_key`（`market_indicator`）、`domain`（`market_view`）、`fund_code`、`holding_id`、`policy_id`；DG-2 Shadow 的 `base_fund_code`（flag 預設關） | 沒有跨類別統一的 identifier；`domain` 與 `indicator_key` 是兩套鍵；基金三層身份（`DEC-2026-10-29-03`）尚未 canonical 化 |
| value／result | `value_num`、`points[].value_num`、`nav_orig_ccy`、`exp_profile` Cell 的 `value` | page model 只留 `value_text` 字串（不得當來源，第 5.2 節） |
| unit（如適用） | `value_unit`、`ccy` | 同一族兩種單位（殖利率 `%`、利差 `pp`），Digest 照記、不換算 |
| source | `market_view` 的 `source`（provider 標籤）、nav 的 `provenance.source`、Cell 的 `sources`／`failed_sources` | `market_indicator` 列沒有 provider，只有 `source_tier`；provider 要從 `INDICATOR_SPECS` 反查 |
| as_of | `obs_date`、`release_date`、`nav_date`、`ex_date`、Cell 的 `observed_at` | 欄名不統一；PIT 該取哪一欄未定 |
| retrieved_at（如既有） | 各表的 `fetched_at`；Cell 的 `fetched_at` 是「來源 → 時間」對照 | 形狀不一 |
| stale／freshness state | nav 的 `provenance.stale`、`cache_fallback`；設定頁總表的「不是最新」；市場指標的延遲天數 | 淨值過期直接併進「資料未備」，沒有獨立 stale；市場指標 stale 門檻未定；三套說法 |
| missing／unavailable state | 44 第五節第一小節四狀態；Cell 的 `not_ready`／`fetch_failed`／`inconsistent`；設定頁總表四類；`market_view` 的 `reason_code` | **狀態字彙至少三套，沒有對照表** |
| provenance | nav 的 `provenance`；`market_view` 整份 view 的 provenance；Cell 的 `raw`、`source_status`；`is_revised`、`is_estimated` | 逐項 provenance 只有 nav 與 Cell 有 |
| rule result | 第 5.2 節第 3 點所列的使用者門檻比較 | 正式 deterministic investment rules 尚不存在（第 1 節）；現有比較住在呈現層 |
| relevant threshold／policy reference | `user_setting` 的 `setting_key`（例 `alo_tolerance_pp`）；淨值不可用天數常數 | **沒有 rule_version**（`git grep -n -i -E "rule_version|規則版本" 02615e41 -- '*.py'` 實跑無輸出，執行組 2026-10-29）；門檻引用沒有統一格式 |
| confidence／evidence state（僅若既有系統已有正式語意） | 沒有正式語意（`docs/v2/54` 第 2、15 節自述 Non-production；44 `SET-0` 的「可信度」是資料可信度燈，不是投資信心） | **不納入**（客戶第六節的條件不成立） |

### 5.4 Missing 保持 Missing

1. 不得 Missing → 0；Missing → neutral；not evaluated → safe；unavailable → HOLD（客戶原話）。
2. 下列項目現在**未定義**，Digest 裡只能以 Missing／未定義表示，不得由 AI 或任何一層補值：Risk Cap 的輸入、輸出、作用層級與 Missing 行為（BL-0495）；減碼 trigger 與正式降低部位條件（BL-0496）；觀察與降低曝險的分界；🌍 綜合狀態判定規則；`MK-2` 風險分級；`AL-3` 配置風險位階；第 2.5 節「弱化／不適配」判定；候選池定義（`docs/v2/62` CAP-GATE-05）。
3. 固定輸出的「本期行動」在 Risk Cap 正式定義前只能輸出「無法判定」並寫出缺什麼（第 1 節現行可用性、第 3.2 節第 6 項）。

### 5.5 與 `docs/v2/54` 第 15 節 Decision Snapshot 的關係

- Decision Digest＝**現在**給 One AI Brain 讀的結構化輸入層（本契約）。
- 54 第 15 節 Decision Snapshot＝Phase 7 研究項，自述 Non-production、「schema 格式 Phase 7 再定」。兩者概念重疊（rule version、evidence references 等），但**本契約不固定 54 第 15 節的 schema**，也不把 Digest 當成要保存的 snapshot；兩者怎麼銜接留到 Phase 7（執行組讀法，可推翻）。

### 5.6 缺口（Phase 7 前置；登記 `docs/BACKLOG.md` BL-0527，不構成動工授權）

1. 狀態字彙對照表（44 四狀態 ↔ Cell status ↔ 設定頁總表四類 ↔ `reason_code`），含「⬜ 無法判定」與「未定義」。
2. 市場指標逐項 provider。
3. as_of 與 stale 的統一定義（哪一欄、PIT 用不用 `release_date`、市場指標 stale 門檻）——涉及正式 threshold 時走 Decision Gate（`PROJECT_RULES.md` 第 4 節）。
4. 規則結果的正式來源層與 threshold／rule 的引用格式（含 rule_version）。
5. 跨類別 identifier（隨 DG-2 三層身份）。
6. 「查看依據」：句子 → Digest 項目的對映格式（規格 `AI-3`）。
7. Risk Cap 欄位：只能是未定義（第 5.4 節）。

### 5.7 實作前的 Stop Gate（客戶第十五、十六節）

1. Decision Digest 契約定義前，不寫 prompt 或 LLM glue。
2. repo 內沒有 `build_ai_summary`：`git grep -n "build_ai_summary" 02615e41` 實跑無輸出（執行組 2026-10-29）。現有 AI 呼叫只在舊線（A compatibility line），每一處都是「該頁自己組文字快照 → 自己呼叫 LLM」，沒有一處吃結構化 canonical data＋rule result，也沒有一處帶 Risk Cap；B 線沒有任何 AI 呼叫（盤點見 `docs/v2/71` 第八節）。⇒ 沒有現成函式可以宣稱為 One AI Brain；可重用的只有傳輸層（多 provider、多金鑰輪替），其餘屬 replace（調查組讀法，可推翻）。任何既有函式要被重用，先盤點 input、scope、provenance、missing、freshness、Risk Cap 整合、跨頁一致性。

---

## 6. One AI Brain contract（2026-10-29 整合；`DEC-2026-10-27-18`、`-25`、`-26`、44 第七節第三小節之十八其一與其二、藍圖 `SH-4`、客戶第三則第七～十節）

1. **一個 Brain、一份 Digest**：全站唯一 AI Brain（第 3.1 節）。各頁只提供 Data View、Domain Result、Rule Result、Local Explanation（`-18` 四項）；客戶本輪另列「Local AI Summary（若需要）」——它必須來自同一個 Brain、同一份 Decision Digest 的對應 slice，不得 🌍、💼、🔍 各自生成一套 AI 而彼此結論不一致（客戶第七節）。
2. **整合順序**：市場 → 資產配置／我的資產 → 持股 → 候選基金 → Missing／freshness → Risk Cap → 最終行動摘要。讀法（執行組依總管指定，可推翻）：客戶本輪第八節列的順序沒有「Missing／freshness」那一段，但同一節寫「全站 AI 最終整合順序維持正式方向」，而正式方向就是 `-18`（正式裁示，有這一段）；拿掉就是悄悄少一環，故保留。
3. **AI 投資總結的輸出格式（客戶第八節）**：市場一句；我的資產一句；持股一句；候選基金一句；主要風險 1～3 點；本期行動至多 3 項。每一句都要能「查看依據」，回鏈到 Decision Digest、canonical evidence 或 rule result（對映格式未定，`AI-3`）。第 2 項 `-18` 原稱「配置」，四頁 IA（44 第七節第三小節之二十）後稱「我的資產」，slice 範圍＝我的資產頁整體、含資產配置區段（執行組讀法，可推翻）。第 6 項受第 5.4 節第 3 點限制。
4. **AI 投資總結的禁止事項（客戶第九節）**：它不是另一個大型資料頁；不複製原始圖表、不重列市場資料、不另做持股表、不重複其他頁的內容、不產生大量 AI 長文。它只做：現在怎麼看 → 為什麼 → 風險在哪 → 是否要行動；證據按需要展開。第 3.3 節 AI 六項禁止照舊。
5. **AI 只讀**：資料層 ≠ AI 推理層；canonical data 只由正式 data pipeline 建立；AI 不回寫 canonical data；missing ≠ 0、unavailable ≠ neutral、not evaluated ≠ safe；provenance 保留；顏色不是唯一資訊載體（客戶第十七節；`PROJECT_RULES.md` 第 13 節第 1 條、13.1）。
6. **AI 不讀畫面**：第 5.2 節第 2 點。repo 內原本沒有這條規則，也沒有對應守衛（調查組 3 盤點；「沒找到」只代表那幾條字串查不到）；守衛登記 BL-0527，Phase 7 實作批之前補上。
7. **入口位置**：現行正式規定是「全站 AI 區屬導覽與全站殼層能力、不算任何一頁的塊」（`-25`、44 之十八其一）、桌機第一屏至多 1 個 AI 摘要入口（`-26`、44 之十八其二）、藍圖 `SH-4` 寫桌機右側可保留；B 線目前不接 AI（44 之四其六）。客戶本輪要求「清楚、容易找到的集中入口」，並把 🤖 AI 投資總結列進目標頁單；它最終是獨立頂層頁、殼層右欄或兩者並存，~~**待單一最小 Gate**（`docs/BACKLOG.md` BL-0526），本節不定。~~ **【2026-10-29 已裁示方案 C（`DEC-2026-10-29-07`，決策者：客戶；舊句保留，劃線為狀態更新，不是漏刪）：見下方第 6.1 節。】**
8. **舊方向的 supersede**：`docs/BACKLOG.md` BL-0293 承接的 2026-10-17 Roadmap 標籤「未來 AI page interpretation」，其文件組讀法「未來 AI 可解讀頁面內容」與第 5.2 節（Digest 不是 UI scrape、AI 不讀畫面）方向相反；自 `DEC-2026-10-29-06` 起，該讀法由第 5.2 節取代，標籤讀作「AI 解讀各頁對應的 Digest slice」（執行組讀法，可推翻；BL-0293 列尾已補記，原文不刪）。

---

### 6.1 🤖 AI 投資總結的入口與各頁 local summary（方案 C；`DEC-2026-10-29-07`，客戶 2026-10-29）

逐字存檔 `docs/evidence/decisions/2026-10-29_batch_a_rulings.md`。本小節把裁示落成契約；不改第 1～5 節原文，不是動工授權。

1. **定義**：🤖 AI 投資總結是全站唯一完整整合型 AI Decision Output。來源鏈只有一條：Canonical Data → Rules／Indicators／Risk Cap → Decision Digest（第 5 節）→ One AI Brain → AI 投資總結。不得由 UI 文字拼湊。
2. **各頁**：🌍 市場與趨勢、💼 我的資產、🔍 找基金，每頁至多一個 local AI summary，或一個「查看 AI 判斷」鏡像入口。Local summary 必須來自同一份 Decision Digest 的對應 slice、與 🤖 的結論一致、可查看依據；不得自行重新呼叫另一套 prompt，也不得另建 AI Brain。
3. **🤖 頁的責任**：只回答四件事——現在怎麼看、主要原因、最大風險、是否需要行動。正式輸出維持：市場一句、我的資產與配置一句、持股一句、候選基金一句；主要風險 1～3 點；本期行動至多 3 項；每一項都有「查看依據」。不做成另一個資料牆，不重複其他頁的全部圖表。
4. **導覽**：Phase 7 實作 One AI Brain 時才正式加入「🤖 AI 投資總結」作為頂層入口；目標導覽為 🌍 市場與趨勢、💼 我的資產、🔍 找基金、🤖 AI 投資總結、⚙️ 設定，共 5 項。本裁示只批准 IA 與入口；Batch A 不實作 One AI Brain、不改 `ui_v2/app_preview.py::PAGES`、不改頁數與頁序守衛。
5. **取代範圍**（逐筆核對原文）：`DEC-2026-10-27-25` 的「AI 區屬導覽與全站殼層、不算任何一頁的塊」之定性部分（「各頁不得各自呼叫獨立 AI」「第一階段不接 AI」照舊）；藍圖 `SH-4` 對 AI 區位置的寫法（桌機右側可保留，不再是入口形式的依據）；44 之二十其一第 2 條的「待 Gate」。`DEC-2026-10-27-26` 的「桌機第一屏至多 1 個 AI 摘要入口」數量上限照舊（不被取代）。`DEC-2026-10-27-18` 的整合順序保留。
6. **本小節沒有查證的部分**：「各頁入口不計各頁塊數」是執行組讀法，客戶未明說，可推翻；🤖 頁的版面與資料牆界線留待 Phase 7 線框送客戶。

## 7. 第 5、6 節沒有查證的部分

1. 第 5、6 節由執行組單組寫成，未經第二組獨立驗證（`CLAUDE.md` §-2 規則 6）；屬 AI decision semantics 與 data semantics 等級，依 `PROJECT_RULES.md` 第 8 節須至少 1 組真正獨立稽核。
2. 第 5.3 節「既有承載」與第 5.7 節的現有 AI 盤點是調查組 3 單組讀碼結果；執行組抽查四件（與第 5.3 節檔頭同一份清單）：`value_text`、`rule_version`、`build_ai_summary`、B 線沒有 AI 呼叫，其餘照錄，欄位是讀建構函式得出，沒有跑過實際回傳值。
3. 第 5.1 節兩條鏈的對位、第 5.2 節第 3 點、第 5.5 節、第 6 節第 2、3、8 點為讀法，可被客戶推翻。
