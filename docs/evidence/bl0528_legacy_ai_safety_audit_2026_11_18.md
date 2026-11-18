# BL-0528 舊版 AI 安全稽核（決策包）

> **研究證據（唯讀、離線稽核）；非客戶裁示、非授權施工。** 基準：`origin/main` `09ed82ba`（#1275 merge）；產生日 2026-11-18。
> 範圍：只讀 repo 原始碼與 `docs/`；未改任何程式、prompt、`mcp_server/`、`docs/DECISIONS.md`、`docs/BACKLOG.md`、`docs/HANDOFF.md`；未做網路探測、未呼叫任何真實 API、未讀 secrets 與真實持倉。
> 作者是 A 線執行組，不是最終決策者，也不是獨立 QA。文中「推薦」一律是**執行組讀法，可被客戶推翻**。
> 路徑一律寫「檔案::符號」，不寫行號。標記法：**FACT**＝本組讀過原始碼／文件可直接指出；**INFERENCE**＝由事實推得；**RECOMMENDATION**＝建議。
> 全稱句（「只有」「沒有其他」）一律標「單組未驗」。

---

## 0. 結論先行

1. **FACT**：`services/ai_prompts.py::build_mk_advisor_prompt` 的 prompt 直接指示模型「列出該減碼的標的（指明代碼＋原因）」、「給出具體 % 比例（核心／衛星／現金）」、「明確要求提高現金比例至 25%+」。這三句與 `DEC-2026-10-27-14`（AI 決定資產水位、發明持股比例與 threshold 仍禁止）、`-22`（減碼需 deterministic trigger，trigger 定義前 AI 不得自行決定減碼）、`-40`（Risk Cap／減碼 trigger 未完成，方向性 AI Action 不得提前實作）字面牴觸。
2. **FACT**：`mcp_server/tools_macro.py::build_macro_snapshot` 的回傳 dict 含 `composite_score`（單一總分）、`verdict.action`（由 `composite_verdict` 產生的逐字買賣指示句）、`action_light`（買賣總結燈）。BACKLOG 根目錄檔已有「`mcp_server/tools_macro.py` 沒有證據支撐閘門」的登記（2026-09-04）。
3. **INFERENCE**：`ui/tab3_t7_ledger.py` 的 A 線路徑屬 Old UI 樹（FACT：位於 `ui/`）；MCP 與 `services/ai_*` 是否算「舊樹」未裁——`DEC-2026-11-02-02` 影響範圍欄只明列 `app.py`、`ui/` 等，未列 `mcp_server/`（見 §5.4）。`DEC-2026-11-02-02`（永久）規定 Old UI 不再修改、不維護兩套 UI；**任何「改程式」的方案都要先過這個解釋問題**。
4. **INFERENCE**：三個方案中，只有「維持並明示限制（純文件）」不碰任何程式；其餘兩案都改變 AI 輸出行為或下架既有輸出，屬 Stop Gate（§6）。
5. **RECOMMENDATION（執行組讀法）**：文件層登記可先做（不等於選方案）；A／B／C 的選擇待客戶。若客戶要求在 A 線仍運作期間就降風險，執行組讀法傾向 B 而非 C（理由見 §4）。執行組**並未**替客戶選定 A。

---

## 1. 核對一：`services/ai_service.py`／`services/ai_prompts.py` 的減碼與比例建議

### 1.1 prompt 內牴觸文字（FACT；皆在 `services/ai_prompts.py::build_mk_advisor_prompt`）

| # | 位置（節） | 文字要點（轉述，非全文） | 對應牴觸 |
|---|---|---|---|
| P1 | 輸出格式「二、換股建議」 | 要求列出 2–3 檔「該減碼」的標的並指明代碼與原因；另列 2–3 檔「該補進」的類型 | `DEC-2026-10-27-22`：減碼屬單一部位的方向性動作，trigger 未正式定義前 AI 不得自行決定；`DEC-2026-10-27-40`；`docs/v2/67_ai_action_vocabulary.md` 第 2.4 節（減碼）、第 3.3 節（AI 禁止事項）；`docs/v2/67` 第 8.4 節（Risk Cap 禁止事項第 1 點：AI 選擇要賣哪一檔基金） |
| P2 | 同節 | 要求點名 2–3 檔底層個股並評估「繼續持有 6–12 個月的最大可能損益」 | 屬模型自行估計損益範圍，無 deterministic 出處；與 `docs/v2/67` 第 8.1 節 C-2（無 calibration 不得出現機率／信心類輸出）同向有張力（INFERENCE：「最大可能損益」未必是機率，是否落入 C-2 未裁） |
| P3 | 「三、建議配置比例（核心／衛星／現金）」 | 要求「具體 % 比例」；差距 >20pp 標「需大幅調整」；紅燈回測成立時「明確要求提高現金比例至 25%+」 | `DEC-2026-10-27-14`：AI 自己決定資產水位、AI 自己發明持股比例、AI 自己發明 threshold 仍禁止（「25%」「>20pp」皆為 prompt 內寫死的數值）；`docs/v2/67` 第 8.4 節第 2 點（計算贖回金額） |
| P4 | 「四、兩種操作策略」 | 要求寫「何時賣／何時買」觸發條件與「不超過總資產 X%」 | 觸發條件由模型生成，非 Deterministic Rules 產出；與 `DEC-2026-10-27-14`「AI 自己發明 threshold」「AI 覆寫 deterministic rule」同向牴觸（INFERENCE：模型實際輸出是否含數值需執行期驗證，本組未跑） |
| P5 | 「一、3 大缺點」 | 每點含「建議行動」 | 方向性建議文字；程度較 P1／P3 輕（INFERENCE） |
| P6 | 「當前景氣位階」段 | 注入 `alloc_str`，來源是呼叫端 `phase_info["allocation"]`（Old UI 的景氣位階配置） | `DEC-2026-10-27-14` 與 `docs/v2/67` 禁止「舊 regime／verdict 作 SSOT」；此為把舊位階配置當事實餵給模型（INFERENCE：`allocation` 的內容由 Old UI 的 `phase_info_global` 決定，本組未逐層追） |

### 1.2 `services/ai_service.py::analyze_portfolio_mk_advisor`（FACT）

- 組 prompt 後直接 `call_llm(prompt, max_tokens=5000, gemini_key=api_key)`，回傳原字串。
- 檔內沒有對輸出做方向詞過濾、數值掃描或 post-processing（FACT：函式尾端即上述 return；INFERENCE：因此牴觸不會在輸出端被攔下）。
- 由呼叫端（`ui/tab3_t7_ledger.py`）僅檢查回傳是否以「❌」「⚠️」開頭（視為錯誤），其餘原樣存進 `st.session_state["mk_advisor_txt"]` 並以 `st.markdown` 渲染；其後有一行「AI 建議僅供參考，最終決策需自行判斷」的 caption（FACT）。該 caption 不是 Risk Cap，也不是 deterministic 出處。

### 1.3 相鄰但非本案核心（只登記，不展開）

- `services/ai_prompts.py::build_structured_summary_prompt` 的「一句話總結 & 下一步」段，範例含「某檔可以考慮換掉」（FACT）。這是較輕的方向暗示；`docs/v2/71_presentation_contract_migration.md` 第 8.2 節已把該 builder 判為 replace（UI scrape），但**沒有**把這句範例列為牴觸。是否納入 BL-0528 由客戶／總管定。本組未追其全部 caller（`ui/helpers/ai_summary.py::render_ai_summary_widget` 的各 Tab 呼叫點見 `docs/v2/71` 第 8.2 節，單組讀碼，本組未重驗）。

- **相鄰牴觸路徑（具名登記，未納入本案方案；單組）**：
  - FACT：`ui/tab1_macro_ai.py` 的 AI 景氣判斷 prompt 含「建議減持高 beta 部位、提高現金比、停止新加碼」與「建議配置」字樣（grep 命中；`docs/v2/71` 第 8.2 節稱此檔未找到 production caller，但 `ui/tab1_macro.py` 內有 `render_ai_summary_section` 的 import 呼叫點——可達性本組未驗）。
  - 僅檔名命中、**未逐一判讀（未驗）**：`composite_verdict`／`macro_action_light` 的其他 Old UI 消費者——`services/decision_matrix.py`、`services/allocation_ladder.py`、`services/realtime_signal.py`、`ui/tab1_macro.py`、`ui/helpers/macro/*`。
  - **方案 B 殘餘缺口須點名上述各處**：B 只改 `build_mk_advisor_prompt` 與 MCP 組裝層，不處理這些路徑。

---

## 2. 核對二：`mcp_server/tools_macro.py` 的舊版行動文字外露

### 2.1 輸出內容（FACT）

`build_macro_snapshot` 回傳 dict 的鍵：`composite_score`、`verdict{icon,level,action}`、`phase{...}`、`action_light`、`regime`、`reconciliation`、`alerts`、`provenance`。

- `verdict.action`＝`services/macro/composite_score.py::composite_verdict` 第 4 個元素。FACT：該函式五個等級的 `action_text` 都是逐字操作句，其中含「可滿倉持有」「分批進場」「拉高現金水位至 15-25%」「現金 30%+，核心轉防守型」等。
- `action_light`＝`services/macro/action_light.py::macro_action_light` 的回傳（含 `light`、`action`、`reasons`、`override`）。
- `composite_score` 是舊 composite 加權單一總分；`DEC-2026-10-27-14` 仍禁止「黑盒單一總分」「用單一 0～100 分數決定市場好壞」（INFERENCE：此處分數刻度非 0～100，但同屬單一總分；是否被該條涵蓋未裁）。

### 2.2 已有的守衛與登記（FACT）

- `tests/test_no_direct_trade_advice_20260914.py` 檔頭明文：只守 `ui/views/page_01_macro.py` 一個檔；`composite_verdict`／`macro_action_light` 的其他消費端（含 `mcp_server/tools_macro.py`）「不在本批射程內，本檔不守，也不宣稱它們合規」。
- 根目錄 `BACKLOG.md`〈已登記未做 — `mcp_server/tools_macro.py` 沒有證據支撐閘門〉：登記該出口未經 `support` 閘門，並寫明「在此之前，任何人引用 MCP 的總經輸出時，請知道它沒有這道閘門」。該登記是**證據支撐**問題，與本案的**行動文字／單一總分**問題相關但不同。　（N1：該登記寫的函式名是 `macro_snapshot`，實際符號為 `build_macro_snapshot`／工具名 `get_macro_snapshot`。）
- `docs/v2/71` 第 8.2 節第 6 列：判為「不可當 Digest 原料；只登記（BL-0528）」。
- `tests/test_mcp_server_smoke.py`：驗 fail-loud、鍵存在與 JSON 序列化；happy path 以 monkeypatch 注入 `verdict`／`action_light`，**僅斷言 `verdict.level` 與 `action_light.light`**，未斷言任何 `action` 文字（FACT）。

---

## 3. 核對三：與正式文件的衝突（逐條）

| # | 正式條文（檔案::節／DEC） | 內容要點 | 與 §1／§2 的關係 |
|---|---|---|---|
| C1 | `docs/DECISIONS.md` `DEC-2026-10-27-14` | 固定鏈 Raw Data → Validate → Normalize → Domain/Formula → Deterministic Rules → Risk Cap → AI Explanation；七項仍禁止（黑盒單一總分、單一 0～100 分數、AI 決定資產水位、AI 發明持股比例、AI 發明 threshold、關鍵資料不足仍硬給方向、AI 覆寫 deterministic rule） | P3、P4、§2 的 `composite_score`、`verdict.action` |
| C2 | `DEC-2026-10-27-22`＋`docs/v2/67` 第 2 節 | 六詞語意；減碼需 deterministic trigger；Rules／Risk Cap 定義前除「無法判定」外五詞不得由系統產生（文件組讀法） | P1（減碼名單） |
| C3 | `DEC-2026-10-27-40` | Risk Cap／減碼 trigger 未完成，方向性 AI Action 不得提前實作 | P1、P3、P4 |
| C4 | `docs/v2/67` 第 8.1 節 C-1 Single Action Authority | 唯一動作權威＝Deterministic Rules＋Risk Cap 產出的 System Action State；OneBrain 不另發 action | 舊 prompt 讓模型自行發 action（P1、P3、P4） |
| C5 | `docs/v2/67` 第 8.2 節 System Action State | 值域限六詞；Rules／Risk Cap 未定義前只會是「無法判定」 | 舊輸出完全繞過此狀態 |
| C6 | `docs/v2/67` 第 8.3 節 Constraint Precedence | 資料狀態 ＞ Hard Constraints ＞ Rule Result ＞ System Action State ＞ interpretation | 舊 prompt 在總經完整率不足時仍可生成。**FACT（單組 grep）**：`ui/tab3_t7_ledger.py` 該區段文案提到「略過按鈕」，但區段內只有 `btn_mk_advisor` 生成鈕與清除鈕，無略過元件；完整率不足（`_mk_data_ok` < 50）只多一行灰字提示，不阻擋生成 |
| C7 | `docs/v2/67` 第 8.4 節 Risk Cap 禁止事項（UI-6 A，`DEC-2026-11-02-07`） | 不可：AI 選擇賣哪一檔基金；計算贖回金額；決定核心或衛星先賣誰；決定成本或稅務優先序 | P1、P3 |
| C8 | `docs/v2/79_final_ui_contract_freeze.md` 第 15 節 cleanup 第 11 項／`BL-0531` 列尾 | 已登記「BL-0528 與 C-1 張力」為 cleanup 候選，**不處置** | 本稽核即為該候選的資料包；處置仍待客戶 |
| C9 | `DEC-2026-11-02-02`（永久） | Old UI 不再修改；不維護兩套 UI；不得因 Old UI 有功能就修 Old UI；退役／刪除不動 | 約束 §4 各方案的可行性（見 §5） |

---

## 4. 三方案表

> 範圍界定：以下「影響範圍」只列本組讀得到的檔案；是否還有其他受影響處屬單組未驗。

### 方案 A｜維持並明示限制（零程式變更）

| 項 | 內容 |
|---|---|
| 做法 | 不改任何 `.py`。在文件層（BACKLOG／HANDOFF／必要時說明書文件，由總管單一 owner 整合）寫明：A 線 `analyze_portfolio_mk_advisor` 的輸出是模型自由生成、含減碼名單與比例，**不是**系統 Action；MCP `get_macro_snapshot` 的 `verdict.action`／`action_light`／`composite_score` 是舊 composite 產物，不得當 Digest／OneBrain 原料或行動依據 |
| 影響範圍 | 僅文件；Old UI、MCP、測試皆不動 |
| 回滾方案 | 還原文件 commit；無執行期影響 |
| 獨立 QA 需求 | 文件層、低風險：依 `CLAUDE.md` §-2 規則 4 的 2026-10-16 指標可自驗；但因涉及 governance 語意（把已知牴觸登記為「維持」），建議至少 1 組獨立複核措辭，避免被讀成「客戶已核准維持牴觸」 |
| 優點 | 立即可做；不與 `DEC-2026-11-02-02` 衝突；零回歸風險 |
| 缺點／風險 | **牴觸文字仍在 production 可達路徑上**，使用者按下按鈕仍會得到減碼名單與 25%+ 現金建議；若無 UI 內揭露（改 UI 即違 `DEC-2026-11-02-02`），揭露只在文件，終端使用者看不到。屬風險接受，而非風險消除 |
| Stop Gate？ | **是（實質）**：把已知與正式裁示牴觸的行為登記為「維持」，等同由執行組決定接受風險；須客戶明示（BL-0528 本來就是待客戶裁示） |　**註：A 的 Gate 屬性是執行組讀法，不在 `PROJECT_RULES.md` 第 4 節十項字面清單內。**

### 方案 B｜最小安全修正（改 prompt 與 MCP 欄位，行為變更）

| 項 | 內容 |
|---|---|
| 做法（草案，不實作） | (1) `build_mk_advisor_prompt`：刪除「該減碼」標的名單、具體 % 比例、「25%+」「>20pp」與策略 A／B 的觸發條件／X% 要求；改為描述性分析（缺點、風險暴露、新聞／driver 的**描述**）並加固定句「本文不構成買賣、減碼或配置比例建議；動作需由系統規則產出」。(2) `build_macro_snapshot`：移除或置空 `verdict.action`、`action_light.action`，並評估 `composite_score` 是否保留。(3) 同步更新鎖住現行章節標題的 `tests/test_ai_prompts.py`，並補「prompt 不得含減碼名單／具體比例」守衛 |
| 影響範圍 | `services/ai_prompts.py`、`mcp_server/tools_macro.py`、`tests/test_ai_prompts.py`、`tests/test_mcp_server_smoke.py`；另有多個測試以 monkeypatch 或呼叫 `analyze_portfolio_mk_advisor`／`build_mk_advisor_prompt`（`tests/test_tier_three_state.py`、`tests/test_ssot_1b_total_return_adr_eating.py`、`tests/test_unknown_currency_fail_closed_20261010.py`、`tests/test_xview_characterization.py` 等；本組只用 grep 辨識，未逐一判讀是否受影響，單組未驗） |
| 回滾方案 | 單一 revert；prompt 為純字串、MCP 為 dict 鍵，無資料遷移 |
| 獨立 QA 需求 | **至少 1 組真正獨立稽核**（`PROJECT_RULES.md` 第 8 節風險分級：investment meaning／AI 行為／governance 等級）；稽核須含 prompt 全文逐句比對與「模型實際輸出仍可能自行補回比例」的離線 fixture 設想（無真實 API 前提下只能驗 prompt 與守衛，驗不到模型行為） |
| 優點 | 直接移除與 C1～C3 字面牴觸的指示句；改動面小；可回滾 |
| 缺點／風險 | (a) 這是「會改變投資判斷的 AI 行為」，屬 Gate；(b) 改的是 Old UI 的 AI 行為，與 `DEC-2026-11-02-02` 的關係未裁（§5）；(c) 殘餘缺口（須點名 §1.3 的相鄰路徑：`ui/tab1_macro_ai.py` 與 `composite_verdict`/`macro_action_light` 其他 Old UI 消費者，皆不在 B 內）：模型仍可能在自由文字中自行建議，且 `build_structured_summary_prompt` 範例句、其他 Tab 的 AI 呼叫不在本案修正內；(d) 改 prompt 後模型輸出無法離線驗證 |
| Stop Gate？ | **是**：會改變投資判斷的 AI 行為（`PROJECT_RULES.md` 第 4 節）；若動 `composite_verdict`／`action_light` 本體還會波及其他消費端，應避免（本案草案只改 MCP 組裝層） |

### 方案 C｜停止有風險輸出（關閉或下架）

| 項 | 內容 |
|---|---|
| 做法（草案，不實作） | (1) 停用 Old UI 的「生成 策略3 深度建議」入口（例如旗標關閉或移除按鈕）；(2) MCP：移除或停用 `get_macro_snapshot` 工具，或僅回傳資料欄位（不含 `verdict`／`action_light`／`composite_score`） |
| 影響範圍 | `ui/tab3_t7_ledger.py`（Old UI 樹）、`mcp_server/server.py`／`tools_macro.py`；相關測試；使用者目前能用的一個功能消失 |
| 回滾方案 | revert；若旗標式則切旗標。功能層面可回，但已下架期間使用者流程中斷 |
| 獨立 QA 需求 | 至少 1 組獨立稽核（下架既有功能＋AI 行為），並需確認「是否有使用者實際在用」（本組無使用數據，未驗） |
| 優點 | 完全消除該輸出牴觸；與「Old UI 只作參考」方向一致 |
| 缺點／風險 | (a) 正式下架既有功能屬客戶請示範圍（`CLAUDE.md` §-1.5.1c 判定 3 表格「正式下架仍在被使用的既有功能 → 請示客戶」）；(b) 要動 Old UI 樹，直接觸及 `DEC-2026-11-02-02` 與 `DEC-2026-10-26-01` 第 (10) 點「退役是否互斥」的未裁張力；(c) 若 MCP 有外部 AI 客戶在用（本組不知），移除會破壞其流程 |
| Stop Gate？ | **是**：下架／退役、Old UI 修改、AI 行為，三者皆為 Gate |

### 推薦（執行組讀法，可被客戶推翻）

1. 立即可做、不需動程式：方案 A 的文件部分（由總管整合進 BACKLOG／HANDOFF），並在客戶回覆前把本列維持「待客戶裁示」。
2. 客戶若要求在 A 線仍可用期間就消除字面牴觸：推薦 B（僅 prompt 與 MCP 組裝層），**不**推薦 C 為首選——理由是 C 必然觸及退役與下架兩個尚有未裁張力的 Gate，成本與不確定性最高，且 `DEC-2026-11-02-02` 已把 Old UI 定位為「不遷移的參考」，功能是否留存本就由退役 Gate 另案處理。
3. 無論選哪一案，都不要引用本檔作為「已核准」依據；任何實作須先有客戶裁示（`PROJECT_RULES.md` 第 4 節）。

---

## 5. 核對四：可達路徑與守衛覆蓋（FACT／INFERENCE，全稱句單組未驗）

### 5.1 Old UI 可達路徑（靜態追 caller；未啟動 app）

- FACT：`services/ai_service.py::analyze_portfolio_mk_advisor` 的 production import 在 `ui/tab3_t7_ledger.py`（檔頂 `from services.ai_service import analyze_portfolio_mk_advisor`），呼叫點在 `ui/tab3_t7_ledger.py::render_t7_section` 內「策略3 深度組合建議」區的 `btn_mk_advisor` 按鈕分支。
- FACT：`render_t7_section` 由 `ui/tab3_portfolio.py::render_portfolio_tab` 於「持倉戰情（T7 帳本）」段呼叫，外面只包 `except T7InputAbort`；`render_portfolio_tab` 由 `app.py` 的資產配置分頁（`tab_portfolio`）呼叫。`app.py` 內也有註解自述此鏈（「無條件呼叫」）。
- FACT：觸發條件在 `ui/tab3_t7_ledger.py`：需有 `GEMINI_KEY`、有已載入基金；總經完整率不足時僅顯示 `not_ready` 提示、不阻擋（文案寫仍可生成）。
- FACT：`build_mk_advisor_prompt` 的 production import 只在 `services/ai_service.py`（`tests/doc_counters_baseline.json` 內亦有他處引用此事實，但那是文件計數基線，不是獨立證據）。
- **INFERENCE（單組未驗）**：以上構成 A 線 production 靜態可達；`docs/v2/71` 第 8.2 節亦同樣標為「靜態可達性未跑 app」。是否真的部署於使用者環境（Streamlit Cloud 入口）、使用者是否按過該按鈕，本組無法驗證。`docs/evidence/ui_data_contract_audit_2026_11_12.md` 的結論提到正式入口仍是 Old UI（`app.py`），本組僅引述，未重驗。
- **單組未驗全稱句**：「`analyze_portfolio_mk_advisor` 只有 `ui/tab3_t7_ledger.py` 一個 production 呼叫點」——本組 `git grep` 於 `-- ':!docs'` 範圍只見該處與 tests／註解；動態呼叫、字串反射、其他分支未查。

### 5.2 MCP 可達路徑

- FACT：`mcp_server/server.py` 以 `FastMCP("fund-dashboard-mcp")` 註冊 `get_macro_snapshot`，transport 為 stdio，由 `mcp.run()` 啟動；`mcp_server/requirements.txt` 明寫它是「另一個本地 process」、不在 Streamlit Cloud 部署依賴內。
- FACT：本組在非 `docs`、非 `tests`、非 `mcp_server` 的範圍 `git grep` `mcp_server|fastmcp`，只命中註解（例如 `services/macro/composite_score.py` 的說明、`ACCEPTANCE.md`）；未見 `app.py`、CI、`.streamlit` 啟動該 server。
- **INFERENCE（單組未驗）**：MCP 出口只有在有人本機手動啟動該 server 並由外部 AI 客戶端連線時才可達；沒有身分驗證／閘門層（stdio 本地）。**不知道**目前是否有人這樣在用。
- **單組未驗全稱句**：「MCP 沒有其他入口」。

### 5.3 現有守衛與缺口

| 守衛 | 覆蓋 | 缺口 |
|---|---|---|
| `tests/test_no_direct_trade_advice_20260914.py` | 只守 `ui/views/page_01_macro.py` 的 `action_text`／`action` 消費 | 明文不守 `mcp_server/tools_macro.py`、`ui/tab1_macro.py`、`services/realtime_signal.py`；**完全不涉** `ai_prompts`／`ai_service` |
| `tests/test_ai_prompts.py` | 驗 `build_mk_advisor_prompt` 含 Phase 4／3-B 引用與四個章節標題 | 反向：它**鎖住**現行含「二、換股」「三、配置」的結構；沒有任何「不得含減碼名單／具體比例」斷言 |
| `tests/test_mcp_server_smoke.py` | fail-loud、鍵存在、JSON 序列化 | 不驗 `verdict.action`／`action_light.action` 內容 |
| `ui_v2/**/logic.py::FORBIDDEN_DIRECTION_WORDS` 與相關測試（`docs/BACKLOG.md` BL-0508 提及） | B 線（New UI）方向詞 | 範圍是 `ui_v2`，不含 Old UI 與 `services/ai_*`、`mcp_server/`；BL-0508 自述「是否涵蓋『觀察』『降低曝險』『替代比較』未逐一查證」，本組亦未驗 |
| 本組在 `tests/` 內以「減碼」字串掃描 | 命中若干測試檔 | 本組僅看到命中檔名清單，未逐一判讀是否有專守 `ai_prompts`／`mcp_server` 的方向詞守衛；**單組未驗，不得讀成「沒有」** |

### 5.4 與 `DEC-2026-11-02-02` 的張力（未裁，據實揭露）

- FACT：該 DEC 影響範圍明列「不修改舊 UI 任何程式（`app.py`、`ui/` 等舊樹）」。`services/ai_*`、`mcp_server/` 是否屬「舊樹」DEC 未明寫。
- INFERENCE：`services/` 同時被 Old UI 與新線使用（例如 `services/v2_tables`、`ui_v2`），把 `services/ai_prompts.py` 視為共享層則方案 B 的 prompt 修正不算「修 Old UI」；但其唯一 production 消費者是 Old UI，故實質上是在修一個只服務 Old UI 的行為。**這是需要客戶表態的解釋問題，不是本組可裁的。**
- FACT：`DEC-2026-11-02-02` 同批揭露的另一未裁張力：退役／刪除與「Old UI 不再修改」是否互斥，裁示前一律不動。

---

## 6. Stop Gate 與需客戶裁示的項目

| # | 項目 | 為何是 Gate（`PROJECT_RULES.md` 第 4 節／`CLAUDE.md` §-1.5） | 執行組讀法 |
|---|---|---|---|
| G1 | 是否接受「維持現狀（A）」 | 等同接受已知與正式裁示牴觸的行為留在 production 可達路徑 | 客戶須明示；執行組不代決 |
| G2 | 是否改寫 AI prompt（B） | 會改變投資判斷的 AI 行為 | Gate |
| G3 | 是否改 MCP 輸出欄位／移除 `composite_score` | 正式輸出契約變更；`composite_score` 是否屬「黑盒單一總分」需客戶定 | Gate |
| G4 | 是否停用／下架入口（C） | 正式下架既有功能；觸及 Old UI 與退役張力 | Gate |
| G5 | 修 `services/ai_*`／`mcp_server/` 是否違反 `DEC-2026-11-02-02` | 治理解釋，未裁 | 請客戶一句話表態 |
| G6 | `build_structured_summary_prompt` 範例句與其他 Tab 的 AI 呼叫是否併入 BL-0528 | 範圍問題（scope） | 請客戶定範圍；執行組推薦本案先只處理 BL-0528 登記的兩處 |

可由總管／執行組在不問客戶的前提下做的事：把本檔登記進 BACKLOG／HANDOFF（文件同步，總管單一 owner）。不構成動工授權。

---

## 7. 我沒有查證的部分（誠實揭露）

1. **沒有跑 app、沒有跑任何 AI 呼叫**：牴觸是從 prompt 原文與 DEC 字面比對得出；模型實際輸出會不會真的含減碼名單與 25%+、含哪些數字，未驗。
2. **沒有部署／使用數據**：不知道 Streamlit Cloud 目前實際入口、使用者是否按過該按鈕、是否有人在用 MCP server。
3. **全稱句皆單組未驗**：「只有一個 production 呼叫點」「MCP 沒有其他入口」「`tests/` 沒有專守這兩處的方向詞守衛」皆未窮舉；`git grep` 字表有限，動態呼叫與反射不在內。
4. （已改為 FACT，見 C6）略過按鈕不存在；此點僅剩「單組 grep」限定。
5. **其他 AI 呼叫點未審**：`ui/helpers/fund_grp_health/ai.py`、`ui/tab1_macro_ai.py`、各 Tab 的 `render_ai_summary_widget` 呼叫、`infra/llm.py` 的實際行為，本組只依 `docs/v2/71` 第 8.2 節引述，未重驗。
6. **`composite_score` 是否被 `DEC-2026-10-27-14`「黑盒單一總分」涵蓋**：文字比對的 INFERENCE，未經客戶裁示。
7. **其餘測試受方案 B 影響的範圍**：只列出 grep 命中檔名，未逐一讀內容判斷是否會紅。
8. **本檔是單組產出，非獨立 QA**：依 `PROJECT_RULES.md` 第 8 節，本檔屬 AI 行為／governance 資料包；若客戶據此裁示後要實作，實作前須另派獨立稽核。
9. **行號一律未寫**；符號名以讀取當下 `09ed82ba` 為準，後續重構可能失效。
