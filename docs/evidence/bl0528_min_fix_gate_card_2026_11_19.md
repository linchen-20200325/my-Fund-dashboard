# BL-0528 最小安全修正 Decision Gate 卡（草稿；非客戶裁示、非授權施工）

基準 `origin/main` `9473a76f`（回修重核；初稿為 `0cfd86b9`）；2026-11-19；A 線執行組（唯讀、單組、**非獨立 QA**）。證據包：`docs/evidence/bl0528_legacy_ai_safety_audit_2026_11_18.md`（下稱「稽核包」，引用不複製）。路徑寫「檔案::符號」不寫行號。標記：FACT＝讀過原碼／文件；INFERENCE＝推得；RECOMMENDATION＝可被客戶推翻。全稱句一律「單組未驗」。

## 客戶只需回答（速查；推薦皆為執行組讀法，可被推翻）

| 題 | 問什麼 | 推薦 | 一句風險 |
|---|---|---|---|
| **先決** | 是否正式採用方案 B 並登記 DEC（目前 repo 無選 B 記錄） | 是，請客戶明示後登記 | 不登記則 BL-0528 不能轉可施工 |
| G5 | `services/ai_*`、`mcp_server/` 的「僅移除牴觸輸出」是否不算修 Old UI | O1：不算，限「僅移除、不碰 `ui/`／`app.py`」 | 窄解釋 DEC，可能被後人援引放寬 |
| G2 | 是否授權刪 prompt 的減碼名單／配置比例／觸發條件 | P-1 刪除式；改寫項須另核准 | 模型仍可能自補建議，離線驗不到 |
| G3a | MCP 的 `verdict.action`、`action_light`（含 `regime.alloc_suggest`／買進 label）是否移除 | (i) 移除鍵 | 未知外部 MCP 使用者可能缺鍵 |
| G3b | `composite_score` 等單一分數／機率欄位算不算黑盒 | (a) 本批不動、另登記 | DEC-14「單一總分」疑慮續存 |
| G6 | 是否併入其他 AI 呼叫 | S-1 只做 BL-0528 兩處 | 其他路徑續存，須在揭露寫明 |
| 揭露字樣 | W1／W2 是否核准或改寫 | 客戶核准字樣 | 未核准字樣不得進 production |

## 0 前提（先講最重要的）

- **FACT**：「客戶採納方案 B」只來自本派工單（ChatGPT 轉達〔待核〕、非逐字）。基準 `9473a76f` 重核：repo 內沒有任何一處登記客戶選 B——`git grep "最小安全修正"` 只命中稽核包自身；`HANDOFF.md` 第 8 行多處提到 BL-0528，但**全是「BL-0528 G1～G6 維持／仍待客戶」**，無選 B 記錄；`DEC-2026-11-19-02`／`-05`／`-06` 的不授權欄也都寫「BL-0528 G1～G6」待客戶（單組 grep）。BL-0528 現況仍是「待客戶裁示」。本卡把「採納 B」當**方向**，不當授權。
- **FACT**：`docs/evidence/open_decisions_ledger_2026_11_18.md` §5.5 的 A1／A2 列是**文件組作者讀法／待裁題，不是客戶的選擇**，可能是「客戶已採納 B」的混淆來源；本組未見任何客戶選 B 的 repo 紀錄。
- **FACT**：`DEC-2026-11-18-03` 不授權欄明列「解除 BL-0527／BL-0528 的其他 Gate」，其 (E2) 切片也明寫不改 `services/ai_service.py`／`ai_prompts.py` → **沒有任何現有 DEC 授權改這兩檔**。
- **FACT**：稽核包自述已歷 1 輪非作者稽核（唯讀 subagent，非 GitHub review），實作前仍須另派獨立稽核。

## 1 方案 B 精確變更範圍（草案，不施工）

### 1.1 `services/ai_prompts.py::build_mk_advisor_prompt`（＋`services/ai_service.py::analyze_portfolio_mk_advisor` 小動）

| prompt 段落（FACT，已實讀） | 處置選項 | 建議 |
|---|---|---|
| 開頭「高階教練…結構化建議」 | 刪除／改中性「分析者」 | 改中性，不再要求「建議」 |
| 「建議配置：{alloc_str}」（餵 Old UI `phase_info["allocation"]` 百分比；來源未追，單組未驗） | 模板不印（簽名與 `ai_service` 呼叫不動）／保留並標「舊位階配置，非系統建議」 | **模板不印**（標示擋不住模型照抄） |
| 一、3 大缺點的「建議行動」；同節寫死的 % 範例（「JFZN3 吃本金 5pp」「ACDD01 占比過低 1%」） | 刪／改「影響」；範例改無數字或刪 | 刪「建議行動」；刪寫死 % 範例（會被模型當門檻樣板） |
| 二、節標題含「換股建議」；「該減碼」2–3 檔＋「該補進」類型；**範例句**「Top 1 SLOOS…→ 減碼景氣循環衛星」；底層持股「6–12 個月最大可能損益」 | 全刪／改中性描述 | 標題與範例句一併刪（範例句本身就是減碼指示）；刪名單與補進；刪「最大可能損益」（與 `docs/v2/67` §8.1 C-2 同向有張力，INFERENCE）；持股×新聞若要保留須改寫為「描述暴露」 |
| 三、建議配置比例：具體 %、「差距>20pp 需大幅調整」、「提高現金至 25%+」 | 整節刪（本節本質就是比例，**不能**改寫成中性描述） | 整節刪 |
| 四、兩種操作策略：賣／買觸發條件、「不超過總資產 X%」、結尾「該偏向 A 還是 B 的明確結論」 | 整節刪；末段「系統性風險警示」保留為**風險描述**並刪「明確結論」 | 刪＋改 |
| 「嚴格規則」（只能引用上方資料） | 保留；新增「不得自行提出任何百分比、門檻、比例、買賣／減碼指示」 | 新增 |
| 揭露句（§3） | 模型生成／程式附加 | **程式附加於非錯誤回傳的尾端**，不依賴模型遵守；**不可前置**。附加端錯誤判定採**單一規則：不比 UI 與 `infra/llm.py` 任一處寬鬆（任一處判為錯誤即不附加）**。FACT：`ui/tab3_t7_ledger.py`（約 3512 行）以 `startswith(("❌","⚠️"))` 判錯誤、**不 lstrip**；`infra/llm.py`（約 89 行）用 `str(result).lstrip().startswith(...)`，**兩處寫法不同**，故附加端須採較嚴（含 lstrip）者；**空字串／非 str 一律不附加**（FACT：`tests/test_tier_three_state.py` 的 `call_llm` stub 回 `""`） |

**變更範圍的性質（調和「只能移除」與上表多處「改寫」）**：**刪除是最小集，也是本卡唯一不需新語意的動作**（符合 §4「只能移除」）。凡「改寫為中性描述」（例：持股×新聞改寫成描述暴露、「建議行動」改「影響」、末段風險警示改寫）都是**新的 prompt 語意**，不是移除，須客戶在 G2 一併核准；客戶若只核准刪除，改寫項即不做。

Old UI 副作用（FACT）：`ui/tab3_t7_ledger.py` 的按鈕「🤖 生成 策略3 深度建議」、區塊說明「AI 4 節結構：3 大缺點 / 換股建議 / 配置比例 / 高賣低買 vs 跌就買」、`not_ready` 文案「AI 給不出景氣位階對應的換股建議」與 caption「AI 建議僅供參考」，B 皆不改（G5）→ 畫面文字與內容不再一致（R5）。另 **FACT（客戶明令）**：客戶有「不得修改現有線上正常運作的舊版 Tab」明令（`DEC-2026-11-01-01` 轉述）；B 雖不改 `ui/` 程式，但**會改動線上 Tab 的 AI 輸出**，G5 須把這點一併攤給客戶。

### 1.2 `mcp_server/tools_macro.py::build_macro_snapshot`（僅組裝層；不動 `services/macro/*`）

| 欄位（FACT） | 選項 | 建議 |
|---|---|---|
| `verdict.action`（`composite_verdict` 第 4 元素，五句逐字買賣指示） | (i) 移除鍵 (ii) 置 null 保鍵 (iii) 保留＋標「非正式 Action」 | (i)。標示擋不住下游 LLM 轉述「拉高現金水位至 15-25%」（INFERENCE） |
| `action_light` 整塊（實際鍵：`light`／`action`／`reasons`／`override`，另有 `support`／`all_clear_support`／`no_trigger_support`）：模組 docstring 明寫 🟢🟡🔴＝可加碼／持有／減碼 → **只刪 `action` 句不夠，`light` 本身就是行動分類** | (i) 整塊移除 (ii) 只留 override 觸發原因 (iii) 標示 | (i)；(ii) 是新輸出語意，非最小 |
| **新發現（稽核包未點名）**：`regime.alloc_suggest`（`identify_regime` 硬編碼配置 %，如成長期 股50／債30／衛星20）與 `regime.zscore_pmi`（`label`「PMI 低估（買進訊號）」／「PMI 高估（過熱警告）」＋ `signal` 🟢🔴），經 MCP `regime` 鍵外露 | 同上 | 納入第一層，但**超出 BL-0528 登記字面，須客戶確認** |
| **說明文字（FACT，稽核包與初稿皆漏）**：`mcp_server/server.py::get_macro_snapshot` docstring 寫「買/賣總結燈(action_light)」「加權健康度總分(composite_score)」；`tools_macro` 模組 docstring 寫「買賣燈(`macro_action_light`)」、`build_macro_snapshot` docstring 的 Returns 列出 `composite_score / verdict / phase / action_light`；`mcp_server/__init__.py` 模組 docstring（約第 10 行）只描述工具定位、**未列欄位名**，本組判讀無須改但請複核。**INFERENCE**：FastMCP 工具描述通常取自 docstring，外部 AI 客戶端可能直接讀到這句；欄位移除後這些說明須同步改，否則仍向外部宣稱有買／賣燈（工具描述是否真的外送，未驗） | 同步改 docstring／刪該說明 | 與欄位同批改 |
| `composite_score`、`verdict.icon/level`：FACT 公式為公開加權＋provenance，但 MCP 只輸出 `sources／fetched_at_latest／n_indicators`，**不含逐指標貢獻**；是否屬 DEC-14「黑盒單一總分」＝INFERENCE，未裁 | 保留標 legacy／移除／保留＋加貢獻（新 schema，不建議） | 本批不動，列 G3b |
| `phase.score_10`、`phase.rec_prob_pct`（同為舊單一分數／機率%；`rec_prob` 是否為校準機率未驗，C-2） | 同上 | 本批不動，列 G3b，登記 |

### 1.3 受影響測試（已實讀測試碼；**未實跑**）

- **會紅**：`tests/test_ai_prompts.py::test_build_mk_advisor_prompt_requires_phase4_3b_citation`——斷言標題「二、」「三、」「四、」、「必須引用上方『領先指標排名』」（在二）、「(1) 1-2 條上方新聞／(2) Phase 4／(3) Phase 3-B」（在四末段）；三、四節整刪即紅。它目前是**鎖住牴觸結構**的測試（稽核包 §5.3），須同批改寫，不得 xfail／放寬成恆綠。
- **會紅**：`tests/test_mcp_server_smoke.py::test_snapshot_happy_path_keys` 斷言 `snap["action_light"]["light"]=="🟡"`；且 `_patch_l2` 對 `tools_macro.macro_action_light` 做 `monkeypatch.setattr`，組裝層若不再 import 該名會 AttributeError（pytest 預設 `raising=True`）→ `test_snapshot_through_envelope_is_json_safe` 同紅。`verdict.level` 斷言只在 G3b 不動時續綠。
- **預期仍綠（只斷言 `pf_snap`／指標行／幣別行，不斷言章節文字；前提：保留 `build_mk_advisor_prompt` 簽名）**：`test_tier_three_state.py`、`test_ssot_1b_total_return_adr_eating.py`、`test_unknown_currency_fail_closed_20261010.py`、`test_xview_characterization.py`。
- **只 grep 辨識、未讀內容**：`test_services_purity_contract.py`、`test_audit_20260805_tab1_wiring.py`、`test_audit_static_reachability.py`、`test_macro_indicator_signs.py`、`tests/doc_counters_baseline.json`（含 `build_mk_advisor_prompt` production import 計數文字）。
- **需新增的守衛（只列需求）**：N1 **限縮於模板文字**（不是整份組好的 prompt）不得含方向詞與「數字＋%」建議樣態——注入資料行（指標、持股、`pf_snap`）本來就含 %，掃整份必誤報；且模板內的「禁止」句會自我命中，須區分指示與禁止句（`CLAUDE.md` §-2.A 第 8 款）；N2 把 `test_no_direct_trade_advice_20260914` 的射程擴到 `ai_prompts`／`mcp_server`（該檔 docstring 明文「不守 mcp_server/tools_macro.py」），建議另開新檔，不動既有 A／C／D 組；N3 MCP 序列化後不得含 `action_light`／`verdict.action`／`alloc_suggest`，**且守衛範圍含 `mcp_server/server.py` 的 `get_macro_snapshot` docstring 與 `tools_macro` docstring（不得再宣稱買／賣總結燈）**，五句 action_text 從 L2 現場取回、不手抄第二份；N4 揭露句只附加於非錯誤回傳，判定規則見 §1.1（不比 UI／`llm.py` 任一處寬鬆）；須測**「空白＋❌」「空白＋⚠️」邊界字串**（UI 不 lstrip 會當成功、`llm.py` 會當錯誤）、`❌`／`⚠️` 開頭不被改、空字串／非 str 不附加；N5 突變驗證：把「該減碼」加回 prompt、把 `action_light` 加回組裝層，守衛必須轉紅。**以上全是靜態／注入式，驗不到模型實際輸出（§3）。**

## 2 Decision Gate：逐項最小裁示問題

### G5（前置）修改 `services/ai_*`／`mcp_server/` 是否違反 `DEC-2026-11-02-02`？

- **FACT**：該 DEC「影響範圍」原文：「不修改舊 UI 任何程式（`app.py`、`ui/` 等舊樹）；不維護兩套 UI；不得把 Old UI 當 migration target」；決策摘要 (4)「不得因為 Old UI 有某個功能就去修 Old UI」。明列 `app.py`、`ui/`，「等」字開放，**未列** `services/ai_*`、`mcp_server/`。
- **FACT**：`DEC-2026-11-01-01`（丙）G-E7 的「舊樹」列舉（`ui/views/page_03_research.py`、`ui/helpers/fund_research/code_finder.py`、`services/fund_search.py` 等）是**文件組列舉、「只列、不替客戶裁」**；客戶實際回答在 `DEC-2026-11-01-02` G-E7 採 A（「目前完全不修改正常運作中的舊 UI……不因 Batch E 回頭修改或移除舊版 Tab」），**沒有檔案清單**。**INFERENCE**：由此只能推得「repo 內的『舊樹』用語在文件組列舉中含 `services/` 檔案」，**不是客戶裁定 services 屬舊樹**；風險仍在，但不得寫成客戶已劃界。另 **FACT**：客戶另有「不得修改現有線上正常運作的舊版 Tab」明令；B 不改 `ui/` 程式，但會改動線上 Tab 的 AI 輸出——須一併攤給客戶。
- **FACT**：`build_mk_advisor_prompt` 唯一 production 消費者鏈止於 `ui/tab3_t7_ledger.py`；MCP 為本地 stdio process、不在 Streamlit 部署內（稽核包 §5.1／5.2，單組未驗）。B 不必改 `ui/`／`app.py`；但 G6 的 `ui/tab1_macro_ai.py` 必改 `ui/`，落在明文範圍（本組重跑 grep 已重現其「建議減持高 beta 部位、提高現金比」）。
- **INFERENCE**：MCP 部分完全不是 UI，風險低。prompt 部分字面不在 `app.py`／`ui/`，但唯一用途服務 Old UI，有被讀成舊樹的實質風險；B 的動機是移除與客戶裁示牴觸的輸出，不是保留 Old UI 功能，可辯護但**不是客戶表態**。→ 執行組**不裁**，判定為「未裁」。

| 方案 | 優點 | 缺點 | 風險 |
|---|---|---|---|
| **O1 客戶一句話表態：`services/ai_*`、`mcp_server/` 不屬舊樹；僅限「移除與 DEC-14／22／40 牴觸之輸出、不新增功能、不碰 `ui/`／`app.py`」的合規修正，不算修 Old UI（推薦）** | B 可行；邊界寫死 | 對 DEC 範圍作窄解釋 | 先例被後人援引放寬（須明寫「僅限移除」）；按鈕標籤不一致無法同批修 |
| O2 視 `ai_prompts`／`ai_service` 為舊樹不動，只改 `mcp_server` | 嚴守 DEC | Old UI 減碼／25%+ 輸出續存；與「採納 B」方向只做一半 | 須另裁 G1 風險接受 |
| O3 全部視舊樹，等 cutover／退役 | 零違規 | cutover（BL-0535）屬 LATER，時限不定；MCP 也不動 | 牴觸持續在 production 可達路徑 |

### G2 是否授權改寫 `build_mk_advisor_prompt`（§1.1）？

| 方案 | 優點 | 缺點 | 風險 |
|---|---|---|---|
| **P-1 刪除式：刪減碼名單／配置比例／觸發條件，模板不印 `alloc_str`，程式附加揭露句（推薦）** | 直接移除與 C1～C3 字面牴觸的指示句；單一 revert 可回滾 | 改變 AI 行為（Gate）；輸出變薄 | 模型仍可能自補（§3 R1） |
| P-2 只刪減碼名單與比例，保留四、策略 | 改動更小 | 觸發條件／「X%」仍是 prompt 內發明 threshold（DEC-14 牴觸續存） | 需再開一輪 |
| P-3 P-1＋輸出端 regex 後處理（命中「減碼／%」改顯「⬜ 無法判定」） | 理論上擋自補 | 新邏輯、誤殺合法引用（如「吃本金 5pp」）；測試只能驗已知樣態 | 偽安全感；不建議 |

### G3 是否授權改 MCP 輸出欄位？

- **G3a**（行動欄位：`verdict.action`、`action_light` 整塊，＋是否納入新發現的 `regime.alloc_suggest`／`zscore_pmi` 買進 label）

| 方案 | 優點 | 缺點 | 風險 |
|---|---|---|---|
| **(i) 移除鍵（推薦）** | 確實不外露；舊行動欄位無從冒充 Action | 外部客戶端若讀這些鍵會缺鍵 | **本組不知有無外部 MCP 使用者（未驗）**，須客戶確認 |
| (ii) 置 null 保鍵 | schema 不變、下游不崩 | 鍵仍在，日後易被回填；null 易被讀成「資料缺」而非「刻意移除」 | 半吊子 |
| (iii) 保留＋標「非正式 Action」 | 零破壞 | 標示擋不住 LLM 轉述；仍違 C-1（冒充） | 牴觸續存 |

- **G3b**（`composite_score`、`verdict.level/icon`、`phase.score_10`、`phase.rec_prob_pct` 算不算黑盒單一總分／未校準機率）：選項＝(a) 本批不動、另登記 BL（**推薦**：最小，且客戶方向只點名「行動欄位」）／(b) 一併移除／(c) 保留＋加 legacy 標記（新增鍵＝契約變更）。**風險**：選 (a) 則 DEC-14「單一總分」疑慮續存。`composite_score` 單一總分＝FACT，「黑盒」與否＝INFERENCE，由客戶定。

### G6 是否併入其他 AI 呼叫？

- **FACT**：`build_structured_summary_prompt` 範例句「某檔可以考慮換掉／先別急著加碼」（較輕的方向暗示）；`ui/tab1_macro_ai.py` prompt 含「建議減持高 beta 部位、提高現金比、停止新加碼」與「建議配置…%」（在 `ui/`，受 G5 明文範圍約束）；`composite_verdict`／`macro_action_light` 其他消費者（`services/decision_matrix.py`、`allocation_ladder.py`、`realtime_signal.py`、`ui/tab1_macro.py` 等）與 `ui/helpers/fund_grp_health/ai.py` **未逐一判讀**。

| 方案 | 優點 | 缺點 | 風險 |
|---|---|---|---|
| **S-1 只處理 BL-0528 登記兩處；其餘登記新 BL、不動（推薦）** | 符合最小範圍（`PROJECT_RULES` §9）；不碰 `ui/` | 殘餘路徑續存 | 客戶誤以為「全站已清」→ 須在揭露寫明 |
| S-2 併入 `build_structured_summary_prompt` 範例句 | 一行字串；`test_ai_prompts` 該 builder 只斷言「一句話總結」，應不受影響 | 影響所有 Tab 的 AI 總結（blast radius 大） | 範圍擴張 |
| S-3 全站 AI prompt 方向詞掃描＋修 | 較完整 | 新調查＋必改 `ui/` | 不建議本批 |

## 3 揭露文字（PendingWording 候選；**未核准，不得宣稱已核准字樣**）與殘餘風險

- **W1（Old UI 輸出尾端，程式附加）**：「〔PendingWording 候選〕本段為 AI 自由生成文字，無法保證不含買賣、減碼或配置比例的暗示；它不是系統行動，也不是投資建議。系統行動須由正式規則與風險上限產出。」（初稿曾寫「目前尚未定義，故本頁不提供」——**NOT VERIFIED，已刪**：`ui/tab1_macro.py` 仍呼叫 `macro_action_light`，「本頁不提供」未驗。）
- **W2（MCP，若客戶選擇保留部分欄位）**：「〔PendingWording 候選〕本輸出僅為資料與描述，不含行動結論；行動須由系統規則決定（尚未定義）。」
- **無現行核准依據**：未核准字樣能否進 production 輸出，須客戶核准字樣，或明示同意暫行；不得援引其他決議的 PendingWording 慣例類推。
- **誠實殘餘風險**：R1 **離線驗不到模型行為**：刪指示句不等於模型不再自補「建議減碼／配置 X%」，本批無任何真實 API 呼叫，只能驗 prompt 文字與守衛。R2 **自由生成文字無法靠 Prompt 保證完全安全**；守衛只證明「我們沒要求」，不證明「模型沒說」。R3 尾端揭露使用者未必讀；Old UI caption「AI 建議僅供參考」仍在（受凍結）。R4 §G6 路徑續存。R5 `ui/tab3_t7_ledger.py` 的按鈕「策略3 深度建議」、區塊說明「AI 4 節結構：3 大缺點 / 換股建議 / 配置比例 / 高賣低買 vs 跌就買」、`not_ready` 文案「AI 給不出景氣位階對應的換股建議」與內容不一致（凍結，不能改；使用者會看到承諾 4 節卻只有刪減後的內容）。R6 未知的外部 MCP 消費者可能因移除鍵而受影響。

## 4 「Deterministic Rules＋Risk Cap 為唯一行動權威」的現況事實

- **FACT**：`docs/v2/67` §8.1 C-1、§8.2：System Action State 值域限六詞，**Rules 與 Risk Cap 未定義前只會是「無法判定」**。BL-0495（Risk Cap）、BL-0496（減碼 trigger）皆「待客戶裁示」；`DEC-2026-10-27-22`／`-40`：trigger 未定義前 AI 不得自行決定減碼、方向性 AI Action 不得提前實作。單組 `git grep -i "risk_cap|system_action_state" -- '*.py'`（基準 `9473a76f`）：**production 無定義**，僅命中註解（`shared/ui_semantics/rules.py`、`ui_v2/asset/*` 等）與 `tests/` 內兩個測試檔（`test_p3_page_status_logic.py`、`test_ui_v3_viewmodel_contract.py`，皆為「不是 Risk Cap 輸入／輸出」類斷言）。
- **結論**：方案 B **只能「移除」，不能「替換成確定性行動」**。移除後 Old UI／MCP 是「沒有任何行動輸出」，不是「有正式行動」，與 §8.2 現行值同向（INFERENCE）。移除處**不得**放任何看似行動的替代字樣（例如「建議維持」「觀察」——那是六詞之一，同受 `-22` 禁止），中性文字只能是描述。

## 5 進入施工還缺什麼（逐項）與稽核

1. **（最缺的一項）客戶對「採納方案 B」的可核對表態**（逐字或客戶本人確認）＋登記 DEC。目前僅 ChatGPT 轉達〔待核〕，repo 無記錄；沒有它，BL-0528 不能由「待裁」轉為可施工。
2. G5 表態（推薦 O1）——無此則 prompt 部分不可動。
3. G2 授權（推薦 P-1）。
4. G3a 授權（含 `regime.alloc_suggest`／買進 label 是否納入）＋G3b 處置；客戶確認有無外部 MCP 使用者。
5. G6 範圍（推薦 S-1）。
6. 揭露字樣核准（W1／W2 或客戶改寫）。
7. 施工授權單：檔案白名單（`services/ai_prompts.py`、`services/ai_service.py` 僅限附加揭露、`mcp_server/tools_macro.py`、**`mcp_server/server.py`（`get_macro_snapshot` docstring）**、**`mcp_server/__init__.py`（若複核需改）**、`tests/test_ai_prompts.py`、`tests/test_mcp_server_smoke.py`、新增守衛檔；**docs 登記（`DECISIONS.md`／`BACKLOG.md`／`HANDOFF.md`）須明列是否納入**，且 **`tests/doc_counters_baseline.json` 是否需同步（其含 `build_mk_advisor_prompt` production import 計數文字，及其他計數類守衛是否受影響）——未查證**）；**不含** `ui/`、`app.py`、`services/macro/*`、`infra/llm.py`、真實 AI 呼叫、secrets。`PROJECT_RULES` §5 是否要求 Model／Effort 切換：**未查證**。
8. **稽核**（`PROJECT_RULES` §8）：AI 行為變更＋investment meaning＋governance → **至少 1 組真正獨立稽核**（非作者；§-2.A 第 5 款：派工單本身納入稽核範圍）。若客戶將本案認列為「資安／重大合規」則 2 組；執行組讀法為前者（BL-0528 類別標 compliance／bug，非資安，可被推翻）。RECOMMENDATION：低成本下派兩種角度——一組逐句比對 prompt 與 DEC 條文，一組做突變（把減碼句／`action_light` 加回，守衛須轉紅）。本卡本身是治理／投資語意文件，轉為依據前也須獨立複核。

## 6 我沒有查證的部分

- 客戶採納 B 僅為轉述；未見逐字。未跑 app、未跑 pytest、未呼叫任何 AI；§1.3 的紅／綠判斷來自讀測試碼，未實跑。
- 只 grep 未讀內容的測試（§1.3 第 4 點）、`phase_info["allocation"]` 來源、`reconciliation`／`regime` 其餘欄位內容、`phase.rec_prob` 是否校準：未驗。
- 外部 MCP 消費者、Old UI 使用者是否真在用：無數據。
- 全稱句皆單組未驗：「production 無 Risk Cap 定義」「MCP 輸出的行動類欄位只有上列」「B 不必改 `ui/`／`app.py`」「`ai_prompts` 唯一 production 消費者是 `ai_service`」。
- 行號一律未寫；符號以 `9473a76f` 為準（回修時已就 M1、M2、S1、S3～S6 重核對應事實，其餘段落未逐句重驗，沿用 `0cfd86b9` 讀法）。本卡為單組草稿，非獨立 QA。
