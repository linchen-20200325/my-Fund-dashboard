# BL-0528 限縮「Prompt 修正」施工 Gate（草稿；方向 ≠ 施工授權；本檔不改 repo）

基準 `origin/main` `eb08c5fc`（`services/`、`mcp_server/`、`tests/test_ai_prompts.py`、`tests/test_mcp_server_smoke.py` 自 `9473a76f` 起無變動，`git diff --stat` 為空）。來源：ChatGPT 總管轉達客戶方向〔待核〕、非逐字（登記草稿見 `DEC-2026-11-19-08`）；G3a 查核見 `docs/evidence/bl0528_g3a_mcp_compat_2026_11_19.md`（結論：**無法確認**）。A 線執行組、單組、**非獨立 QA**。FACT＝讀過原碼／文件；INFERENCE＝推得；RECOMMENDATION＝可被推翻。全稱句單組未驗。路徑寫「檔案::符號」不寫行號。

**本 Gate 只涵蓋 Prompt 修正，不得被說成「全站 AI 安全已解決」。**

## 0 範圍界定

- **S-1「現有兩處」＝ BL-0528 登記的兩處**（FACT：`docs/BACKLOG.md` BL-0528 列）：(1) `services/ai_service.py::analyze_portfolio_mk_advisor`＋`services/ai_prompts.py::build_mk_advisor_prompt`（Old UI AI 輸出）；(2) `mcp_server/tools_macro.py::build_macro_snapshot` 的舊行動欄位。
- **(2) 在 S-1 範圍內，但被 G3a 擱置**：G3a 無法確認 ⇒ 依客戶方向不刪已公開鍵，故**本 Gate 只處理 (1)，(2) 不在本次施工白名單**（`tools_macro.py`、`server.py`〔含 `get_macro_snapshot` docstring 與工具描述〕、`__init__.py`、`tests/test_mcp_server_smoke.py` 皆不碰）。BL-0528 (2) 維持開放。**「docstring 一律不得碰」是執行組讀法，非客戶裁示**（客戶只說未確認前不直接刪除已公開輸出欄位；docstring 是否屬「已公開輸出」亦未裁）。
- 不在本 Gate：G3b（`composite_score`／`verdict.level`／`phase.score_10`／`phase.rec_prob_pct`）；`build_structured_summary_prompt` 範例句、`ui/tab1_macro_ai.py`、`composite_verdict`／`macro_action_light` 其他消費者（G6 S-1 之外，登記不動）。

## 1 精確白名單（施工時唯一可動的檔案）

| 檔案 | 允許內容 |
|---|---|
| `services/ai_prompts.py` | 只動 `build_mk_advisor_prompt` 的模板文字與其 docstring（§2）；**不動** `build_structured_summary_prompt`。**註解殘留（待核，§8 第 6 項）**：模組 docstring 的「analyze_portfolio_mk_advisor (策略3 組合 4 節)」與節標註釋「策略3 組合 4 節 + Phase 4/3-B 引用」（約第 15、28 行）仍寫「4 節」，是否允許**僅改註解**待客戶／QA 決定（不改則留下與程式不符的註解） |
| `services/ai_service.py` | 只動 `analyze_portfolio_mk_advisor`：(a) 回傳尾端附加揭露句（§4）；(b) 函式 docstring「結構化 4 節：缺點／換股／配置／策略」與上方區塊註解（約第 100～107 行：「缺點／更換／配置／策略」「給標的更換建議」「提供高賣低買＋跌就買兩條策略」）的**僅註解**更新——是否允許待核（§8 第 6 項）。**不動** `alloc_str` 計算與傳參（保留 `build_mk_advisor_prompt` 簽名，理由見 §5） |
| `tests/test_ai_prompts.py` | 改寫 `test_build_mk_advisor_prompt_requires_phase4_3b_citation` 的過時斷言（§5）；不動 `build_structured_summary_prompt` 三個測試 |
| 新增測試檔（建議 `tests/test_bl0528_prompt_safety.py`） | §5 的新守衛與突變測試 |

**不得碰（逐項）**：`mcp_server/*`（含 `tools_macro.py`、`server.py` docstring、`__init__.py`）；`services/macro/*`；`ui/*`（含 `ui/tab3_t7_ledger.py` 的按鈕標籤、「AI 4 節結構…」說明、`not_ready` 文案、caption）；`app.py`；`infra/llm.py`；`tests/test_mcp_server_smoke.py`；`tests/test_no_direct_trade_advice_20260914.py`（不擴射程，新守衛另開新檔）；`tests/doc_counters_baseline.json`、`docs/v2/*`；任何 `requirements*.txt`；secrets。**docs 登記（`DECISIONS.md`／`BACKLOG.md`／`HANDOFF.md`）由治理 owner 單一整合，不在實作 PR 內。**

## 2 要刪除的 prompt 段落（逐項；現況 FACT，已實讀 `build_mk_advisor_prompt`）

| # | 現有文字（轉述） | 處置 | 對應 P-1 項 |
|---|---|---|---|
| D1 | 開頭「高階教練…針對以下組合給結構化建議」 | **機械中性化**（刪「教練／建議」措辭，改「分析者／結構化分析」）——屬改寫，列 §8 待核准項 | 不新增建議 |
| D2 | 「當前景氣位階」段的「建議配置：{alloc_str}」整行 | **刪除該行**（保留「位階：{phase}（評分…）」） | 配置比例 |
| D3 | 「輸出格式…4 節必出」 | 隨章節刪除**機械更新**節數與標題清單（D5 預設最小刪除後剩「一、二」兩節＋末段警示；屬改寫類，§8 待核） | — |
| D4 | 一、3 大缺點：每點「**建議行動**」欄；括號內寫死範例（「JFZN3 吃本金 5pp」「ACDD01 占比過低 1%」「USD 占比 90%」） | 刪「建議行動」欄；刪寫死數字範例（INFERENCE：被當門檻樣板，歸「未核准門檻」；**是否在 P-1 字面內列 §8 待核准**） | 未核准門檻／不新增建議 |
| D5 | 二：標題「…的換股建議」；句子「列出 2–3 檔**該減碼**的標的…＋2–3 檔**該補進**的類型」；範例（括號）「Top 1 SLOOS…→ 減碼景氣循環衛星」；兩段分析指示（「必須引用前 3 名 driver」「必須點名底層個股、評估 6–12 個月最大可能損益」） | **預設＝最小刪除**：(a) 刪整句「該減碼…＋該補進…」（其中「該補進」**不在 P-1 字面清單**，但與減碼名單同一句、無法只刪前半，列 §8 待核）；(b) 刪括號範例句（含「減碼景氣循環衛星」）；(c) 標題截去「的換股建議」字樣（截尾，仍屬刪除性）；(d) **保留**兩段分析指示（「必須引用 driver」「點名底層個股」不在 P-1 字面清單，不刪）；(e)「最大可能損益」子句：不在 P-1 字面清單、同為模型自估損益（與 `docs/v2/67` §8.1 C-2 有張力，INFERENCE），**預設保留、列 §8 待核**。**整節刪除（D5-full）列為待核准選項**，不是預設 | 減碼名單 |
| D6 | 三、整節：具體 %、「差距 >20pp 標需大幅調整」、「提高現金比例至 25%+」、「系統性風險升高同樣加碼現金」 | **整節刪除**（本質為比例，不可中性化） | 配置比例、未核准門檻 |
| D7 | 四、整節：策略 A／B 的賣／買「觸發條件」、「VIX 多少／NBER」、「必要現金水位／不超過總資產 X%」 | **整節刪除** | 策略觸發要求 |
| D8 | 末段「⚠️ 系統性風險警示」中「給『目前該偏向 A 還是 B』的明確結論」子句（及指向已刪策略 A／B 的字樣） | 刪該子句；**保留**其餘「必須引用 (1) 新聞 (2) driver 前 2 名 (3) 子領域回測，加上 VIX／殖利率倒掛／NBER」的**風險描述**部分 | 策略觸發要求 |
| 保留 | 全部資料注入段（景氣位階、總經指標、driver 排名、子領域燈號回測、新聞、持倉、底層持股）；「嚴格規則：只能引用上方資料…禁止編造」 | 不動 | — |

D5 預設最小刪除後，輸出剩「一、3 大缺點（缺點→影響）」「二、（景氣位階＋driver＋新聞＋底層持股的分析）」與末段風險警示；若客戶選 D5-full 則剩「一」與末段警示。**輸出會變薄，這是 P-1 的預期代價**，須在 PR 說明寫明。

## 3 非捏造條款（施工與文字一律遵守）

1. **只刪不增**：不得新增任何替代投資建議；不得用「觀察」「續抱」「降低曝險」「減碼」「替代比較」任一行動詞作替代文字（`docs/v2/67` §8.2：Rules／Risk Cap 未定義前系統只能是「無法判定」，AI 不得代發六詞）。
2. 不得新增任何數字門檻、百分比、比例、價位、機率；不得新增資料來源或指標。
3. **唯一允許的新增 prompt 文字**＝一句禁止性指令（「不得自行提出任何百分比、門檻、比例，或買進／賣出／減碼／加碼指示」）——屬防禦性新增，列 §8 待核准；若客戶不核准則不加。
4. 不得引用或杜撰客戶原話；不得在程式註解、PR 描述、揭露句寫「客戶已核准」「已解決」；來源一律寫「客戶經 ChatGPT 轉達〔待核〕、非逐字」。
5. 不得在 PR／HANDOFF 宣稱「Old UI AI 輸出已安全」「BL-0528 已解決」：只能寫「Prompt 內已知違規指示已移除；模型仍可能自行補回；MCP 與其他路徑未處理」。

## 4 揭露句候選與附加規則

- **候選文字（PendingWording；未核准、待正式揭露文字核准；不得上線）**：「本段為 AI 自由生成文字，無法保證不含買賣、減碼或配置比例的暗示；它不是系統行動，也不是投資建議。系統行動須由正式規則與風險上限產出。」（FACT 對照：初稿曾有「目前尚未定義，故本頁不提供」，因 `ui/tab1_macro.py` 仍呼叫 `macro_action_light` 而 NOT VERIFIED，已刪。）候選前的〔PendingWording 候選〕標籤**不得**隨程式上線；上線字樣須為客戶核准版本。
- **附加位置**：`analyze_portfolio_mk_advisor` 回傳字串的**尾端**，**不前置**。
- **附加條件（單一規則）**：**不比 UI 與 `infra/llm.py` 任一處寬鬆**——任一處會判為錯誤者不附加。FACT：`ui/tab3_t7_ledger.py` 以 `startswith(("❌","⚠️"))` 判錯誤且**不 lstrip**；`infra/llm.py` 以 `str(result).lstrip().startswith(...)` 判。故附加端採 lstrip 後判定（較嚴者），且 `not isinstance(result, str)` 或 `result.strip()==""` 一律不附加（FACT：多個既有測試以 `call_llm` stub 回 `""`／`"stub"`／`"ok"`）。
- **兩個張力（字樣仍待客戶核准，須在核准時一併處理）**：(T1) 候選句「系統行動須由正式規則與風險上限產出」預設該機制存在，但 FACT：Rules／Risk Cap 尚未定義（`docs/v2/67` §8.2：現行值只會是「無法判定」；BL-0495／BL-0496 待客戶）——句子可能被讀成「有正式行動輸出，只是不在這裡」；是否改寫由客戶定。(T2) Old UI 按鈕「🤖 生成 策略3 深度建議」與 caption「AI 建議僅供參考」**凍結不動**，會與揭露句「不是投資建議」**並存於同一畫面**，使用者看到互相矛盾的措辭。
- **揭露是補強，不是安全保證**：它靠使用者閱讀；Old UI caption「AI 建議僅供參考」與按鈕「🤖 生成 策略3 深度建議」凍結不動。

## 5 受影響與新增測試（FACT：讀測試碼；**未實跑**）

- **會紅（須同批改寫，不得 xfail／放寬為恆綠）**：`tests/test_ai_prompts.py::test_build_mk_advisor_prompt_requires_phase4_3b_citation`——「### ⚖️ 三、」「### 🎯 四、」兩個標題斷言會失敗；在 D5 預設最小刪除下，「### 🔄 二、」前綴、「必須引用上方『領先指標排名』」與末三條（(1)(2)(3)）**應仍成立**（INFERENCE；若客戶選 D5-full 整節刪，則「二、」與「必須引用…」也會紅）。
- **預期仍綠（INFERENCE；前提：保留 `build_mk_advisor_prompt` 簽名與資料注入段）**：`test_tier_three_state.py`、`test_ssot_1b_total_return_adr_eating.py`、`test_unknown_currency_fail_closed_20261010.py`、`test_xview_characterization.py`（只斷言 `pf_snap`／指標行／幣別行；xview 斷言含「VIX」的行不含日期或來源——D8 保留段的「VIX」行不含這些）。**保留簽名的理由**：`test_tier_three_state` 以 `lambda **kw` 攔截並讀 `pf_snap`；移除 `alloc_str` 參數會牽動呼叫端，不在最小範圍。代價：`alloc_str` 成為模板未使用的參數（死參數，登記不處理）。
- **新增守衛（只列需求）**：
  - **N1 模板守衛**：以不含 `%`、不含方向詞的哨兵輸入呼叫 `build_mk_advisor_prompt`，掃**模板文字**——不得含「該減碼」「減碼」「提高現金」「25%」「20pp」「X%」「觸發條件」「該補進」「明確結論」等；唯一例外是 §3 第 3 點那一句禁止性指令，守衛須先**整句扣除**並另斷言它存在（否則禁止句自我命中，`CLAUDE.md` §-2.A 第 8 款；負控字串只在指令現編、不落文件）。
  - **N2 結構守衛**：輸出不得含「### ⚖️ 三、」「### 🎯 四、」與「換股建議」字樣（D5-full 則另加「### 🔄 二、」）；資料注入段標題（領先指標排名、子領域燈號歷史回測、持倉、底層持股）仍在。
  - **N3 揭露附加守衛**：非錯誤字串尾端附加、不前置；`❌`／`⚠️` 開頭不附加；**「空白＋❌」「空白＋⚠️」邊界字串不附加**（UI 不 lstrip 會當成功、`llm.py` 會當錯誤，取較嚴）；`""`／`None`／非 str 不附加。
  - **N4 突變驗證**（`PROJECT_RULES`／v2 第一條「拔掉修復必須轉紅」）：把「該減碼」句、「25%+」句、策略觸發句分別加回模板，N1 必須轉紅；把附加改成前置、或把錯誤判定放寬為不 lstrip，N3 必須轉紅。
  - **N5 邊界守衛**：`git diff --name-only` 檔案邊界必須落在 §1 白名單（`mcp_server/*`、`ui/*` 零變更）——實務上由 QA 逐檔確認，亦可做成測試。
- **誠實限制**：以上全為靜態／注入式，**驗不到模型實際輸出**；刪除指示句**不等於**模型不再自行補回建議。
- **`tests/doc_counters_baseline.json` 是否需同步（盡量實查）**：FACT（讀 `tests/test_doc_counters.py`，未實跑）——該守衛的受檢語料只有 `docs/v2/*.md` 與 `docs/v2/prototype/*.html`（`DOCS_DIR = docs/v2`、`DOCS_GLOBS`），baseline 以「文件內正規化句子」為 key，**不讀程式碼檔**；baseline 內與本案相關的條目（`docs/v2/20_ui_spec.md` 的「`services/ai_prompts.py:102` `build_structured_summary_prompt`…」、`docs/v2/24_proposal_4a.md` 的 `build_mk_advisor_prompt` production import 計數）是**文件句子的快照**，改 `.py` 不會改變它們。→ **INFERENCE：本 Gate 白名單（不含 `docs/v2/*`）不需同步 baseline。** 但若施工順手編輯任何 `docs/v2/*` 檔，必須實跑 `tests/test_doc_counters.py`；本組**未實跑**，此結論待 QA 實跑確認。
- 其他只 grep 辨識未讀：`tests/test_services_purity_contract.py`（`ai_service` 的純度白名單：附加字串不得新增 import／I/O；FACT 該檔白名單含 `services/ai_service.py::<module> -> infra.llm`，附加邏輯為純字串處理，**預期不觸發**，未實跑）。

## 6 QA 安排

- **至少 1 組真正獨立 QA**（`PROJECT_RULES` 第 8 節：AI 行為／investment meaning／治理；實作者不得自驗）。本案列為「治理＋AI 行為」，執行組讀法**非資安**，故 1 組為下限（可被推翻）。
- **RECOMMENDATION**：低成本下派兩種角度（下限仍是 1 組）——角度一：逐句比對 prompt diff 與 `DEC-2026-10-27-14`／`-22`／`-40`、`docs/v2/67` §8.4 條文，確認 D1～D8 全部落實且無新增指示；角度二：突變／邊界紅隊（N3 邊界字串、N4 突變、檔案邊界、`ui/`／`mcp_server/` 零變更）。
- QA 須實跑：新守衛、`tests/test_ai_prompts.py`、§5 列的四個預期仍綠測試、`test_services_purity_contract.py`、`test_doc_counters.py`（若動 `docs/v2/*`）、以及路徑掃描 `services/`／`mcp_server/` 的守衛（`tests/poc_*` 5 檔的 `_PY_DIRS`、`tests/ui_v3/test_ui_v3_preview_not_formal_guard.py`；見 `docs/evidence/bl0528_g3a_mcp_compat_2026_11_19.md` C6b；FACT 讀碼，不依賴 prompt 內容，預期不受影響，未實跑）；回報實跑結果而非讀碼推論。
- 派工單本身納入稽核範圍（`CLAUDE.md` §-2.A 第 5 款）；本 Gate 文件在轉為施工依據前亦須獨立複核（單組草稿）。

## 7 Model／Mode／Effort 建議與 Change Gate

- **FACT**：`PROJECT_RULES.md` 第 5 節 10 點矩陣把「投資核心語意…高風險」列為 Opus 5.5／High；「複雜 correctness／資料契約」為 Opus 5.5／Medium；「一般 coding、單模組 bug、tests」為 Sonnet 5.5／Medium。第 11 點（`DEC-2026-11-02-04`）：任一項（Model、模式、Effort）需變更 ⇒ 先送 Change Gate 並**立即停下**，等客戶回覆「已切換／可以開始」；不得自行切換、不得先施工。
- **RECOMMENDATION（總管派工單所述建議；執行組不另加理由）**：**Opus 5.5／Plan／High**。理由**只能掛在**「需逐句對照 `DEC-2026-10-27-14`／`-22`／`-40` 與 `docs/v2/67` §8.4 條文，並設計突變測試與邊界守衛」這項具體複雜度；**不得**以「投資專案預設 High」為由（`PROJECT_RULES.md` 5.1 第 9 點：不得因為是投資專案就預設 High）。矩陣「投資核心語意」列為 High 僅作預設起點，現場以最低足夠判斷為準。**INFERENCE 備註**：若只看「純刪除模板＋寫測試」的機械量，`省額度優先` 可主張 Sonnet 5.5／Medium 已足；是否升 Opus／High **由客戶／總管定**（Opus／Plan／High 為總管派工單所述建議，來源待核）。
- **Mode 注意（INFERENCE）**：Plan 模式通常不能寫入；規劃（定稿本 Gate）可在 Plan，**寫入施工需退出 Plan＝第二次模式切換，依第 11 點可能需再送一次 Change Gate**。是否合併成一次，請總管定。
- Gate 訊息草稿（填入目前設定後由總管送；須為該批最後一則、其後無任何動作）：

```text
⏸️ 建議切換 Model／模式／推理強度
下一階段：BL-0528 Prompt 修正施工（限縮白名單）
目前 Model：<總管填>
建議 Model：Opus 5.5
目前 Effort：<總管填>
建議 Effort：High
建議模式：Plan（規劃）；寫入階段另行確認
原因：須逐條對照 DEC 條文並設計突變與邊界守衛（非「投資專案預設 High」）
切換完成後請回覆「已切換／可以開始」。
```

## 8 仍待使用者核准的最小差異（進入施工前逐項）

**P-1 字面清單只有四項：減碼名單、配置比例、未核准門檻、策略觸發要求。** 下列凡超出者，皆須客戶確認「是否在 O1／P-1 範圍」；**擴大讀法須客戶確認，否則砍掉該項**：

1. **Change Gate 回覆**（Opus／Plan／High 或客戶另定）。
2. **揭露字樣**核准（§4 候選或客戶改寫），或明示同意暫行。
3. **超出 P-1 字面的刪除項**：D4a「建議行動」欄、D4b 寫死 % 範例、D5(a)「該補進」、D5(e)「最大可能損益」（預設保留）；以及 **D5-full 整節刪除**（含「必須引用 driver／點名底層個股」兩段分析）是否核准——預設不做。
4. **改寫類**：D1 措辭中性化、D3 節數／標題更新（P-1 字面只列「移除」）。
5. **新增類（超出「只刪」）**：(i) `ai_service.py` 新增附加揭露的**程式碼**；(ii) prompt 新增一句**禁止性指令**（§3 第 3 點）——是否在 O1／P-1 範圍，或砍掉（砍掉＝本 Gate 退為純 prompt 刪除，無揭露附加）。
6. **僅改註解**：`ai_prompts.py` 模組 docstring／節標註釋、`ai_service.py` 區塊註解是否允許只改註解。
7. **白名單與「保留簽名、`alloc_str` 死參數」**是否同意。
8. **docs 登記**（DEC／BACKLOG／HANDOFF）由治理 owner 整合的時序（建議 DEC 先落 main）。
9. **舊 UI 凍結相關（DEC 草稿 amends 欄所列）**：本 carve-out 對 `DEC-2026-11-01-02` G-E7、`DEC-2026-11-02-01`（甲）(一) 與「不得修改線上正常運作舊版 Tab」明令的處理——B 會改動該線上 Tab 的 AI 輸出，**待客戶確認**。
10. 明確確認：**MCP (2)（被 G3a 擱置）、G3b、其他 AI 呼叫路徑本 Gate 不處理**。

## 9 誠實殘餘與未查證

- **離線驗不到模型行為**；刪除指示句不保證輸出不含建議；「自由生成文字無法靠 Prompt 保證完全安全」（候選揭露句已寫入）。
- **殘餘路徑**：MCP 舊行動欄位與 docstring（在 S-1 內、被 G3a 擱置）、`build_structured_summary_prompt` 範例句、`ui/tab1_macro_ai.py`、`composite_verdict`／`macro_action_light` 其他 Old UI 消費者；Old UI 標籤與內容不一致（凍結）。
- **未驗**：`phase_info["allocation"]` 來源；`tests/test_services_purity_contract.py`、`tests/test_doc_counters.py` 是否在變更後仍綠（均未實跑）；§5「預期仍綠」四檔為讀碼推論；本 clone 為 shallow（歷史類證據不可用）。
- 本檔單組草稿、非獨立 QA；客戶方向僅轉述〔待核〕；方向 ≠ 施工授權。
