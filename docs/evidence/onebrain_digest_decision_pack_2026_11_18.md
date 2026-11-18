# OneBrain Decision Digest 缺口決策包（逐域 R／O／E、as_of、Freshness、Provider、Rule ID、Evidence trace）

> **單組作者，尚待非作者獨立稽核。** 本檔由專案 AI 單組唯讀研究寫成，未經第二組驗證；依 `DEC-2026-10-16-05` 屬 data semantics／AI decision semantics 等級，合併前須至少 1 組真正獨立稽核。
> **稽核紀錄指標（後補）**：第 3 行與下方「稽核狀態」並存，以後者及 `docs/evidence/audit_record_2026_11_18.md` 為準；該紀錄為摘要，稽核原始報告 repo 內無存檔。
> **性質：docs-only 決策包，不是客戶裁示、不是核准欄位、不是 Schema、不是施工授權。** 登記不構成動工授權（`CLAUDE.md` §-1）。
> **基準**：`origin/main` `09ed82ba`（2026-11-18，#1275 merge）。路徑一律寫「檔案::符號」或「檔案:章節」，不寫行號。
> **授權來源說明**：本批題目方向「平行作業完成 UI + OneBrain」是經 ChatGPT 派工單轉述的客戶方向〔待核〕；本組在 `docs/DECISIONS.md`、`docs/HANDOFF.md`、`docs/BACKLOG.md` 查無含該句的 DEC，最接近的是 `PROJECT_RULES.md` 第 16 節的 A／B／C 三線平行規則（流程規則，明文「不改變任何既有 Stop／Decision Gate」）。故該方向**只當作本文件的研究題目，不當作任何 Gate 的裁示**。
> **現況補註（後補，不改本文基準）**：`DEC-2026-11-18-03`／`-04` 已登記（待合併 PR #1276）；`-03` 明定 OB-B 程式 PR 前須客戶先確認 `DEC-2026-10-31-03` 的 fake provider Gate。本文 V8「查無對應 DEC」在基底 `09ed82ba` 屬實，現已有 `-03`；本組未讀 `-03`／`-04` 全文（NOT VERIFIED），第 5 節仍以基底為準。
> **稽核狀態**：已有 1 組非作者治理稽核（總管回報：可合併，Must-Fix 0；稽核報告本組未見）；仍屬單組作者原稿加小修。
> 分段：**FACT**＝可由 repo 指令或文件重現；**INFERENCE**＝由事實推得；**RECOMMENDATION**＝AI 推薦，可被客戶推翻。缺值寫「⬜ 無法判定」或 NOT VERIFIED，不補值。

---

## 0. 結論先行

| # | 結論 | 類別 |
|---|---|---|
| 1 | Decision Digest 目前**只有原則與欄位群，沒有 schema、沒有生產者、沒有程式**：`rule_version` 在整個 repo 的 `.py` 只出現在一個測試（斷言「沒有」該屬性）；`build_ai_summary` 零命中；沒有 `FakeProvider`。 | FACT |
| 2 | 「已有」的是：固定鏈與硬規則（67 第 5 節）、欄位群與 Required／Optional／Excluded 三分通則（67 第 8.5～8.7 節）、Freshness Policy 的**欄位**（無任何門檻值）、D2 首批 5 列**契約文字**（R-ID-1、R-NAV-1、R-NAV-2、R-NAV-4、R-NAV-5）、D3(a) 唯讀字彙對照表（非契約）。**逐域 R／O／E 正式清單：0 個資料域完成**；而且那 5 列只核准「契約文字」，列內狀態仍寫「Required 升格／New UI2 適用仍未核」。 | FACT |
| 3 | 六個要補的維度裡，**真正只有客戶能解的**是：stale 門檻值（含 NAV 10 日）、Rule ID／`rule_version` 格式、D2 剩餘 12 列與其餘六域、反證定義、Risk Cap 與減碼 trigger。**技術可自決**的只有純事實整理（例：把 `INDICATOR_SPECS` 的 provider 反查成唯讀對照），且不得升格成契約。 | INFERENCE |
| 4 | **BL-0527／BL-0528 對 OB-B 的阻擋，在 75 號文件裡是模糊的**：75 第 16 節把 OB-01（Provider abstraction）的前置只寫「本檔」，BL-0527 掛在 OB-02、BL-0528 掛在 OB-09；但第 18.2 節又寫「若仍有 BL-0528、Risk Cap、Decision Digest schema 等上位 blocker，先依既有 Gate 處理」。兩處可有兩種讀法（見第 4 節）。 | FACT＋INFERENCE |
| 5 | **離線 interface／Fake Provider 是否落在 `DEC-2026-10-31-03`／`DEC-2026-11-08-02` 的限制之外，文字上不是明確的**：前者影響範圍欄明寫「任一後續階段（fake provider、shadow、整合、production）都須另行裁示」，後者寫「Phase 7／Provider／Claude API runtime＝未授權」。專案 AI 與 ChatGPT 都不能自行宣告「落在限制外」；這是客戶才能解的題（第 5 節附選項表，AI 推薦方案 B）。 | FACT＋RECOMMENDATION |

**最重要的 3 個發現**（給接手者的短版）：
1. 「核准欄位數 5」不等於「5 個欄位已是 Digest Required」：DEC 核准的是契約文字，Required 升格仍待核，且 Digest schema 依 `DEC-2026-11-11-04` D2-G2 是**另一個 Gate**。
2. OB-B 本身（typed interface＋fake provider）按 75 第 16 節**並不依賴** BL-0527／BL-0528 的內容；真正擋住它的是 `DEC-2026-10-31-03`「每階段另行裁示」這句，而不是 Digest 缺口。BL-0527／BL-0528 擋的是 OB-02 與 OB-09。
3. 「Provider」一詞在本題裡指兩件不同的事（資料供應者 vs AI Provider），且 `DEC-2026-11-17-06` 已明寫 NAV 域**不新增 Provider 欄**——Digest 的「逐域 provider」不能直接當成已獲准的欄位。

---

## 1. 基準、方法與 FACT 驗證

指令執行基準一律為 `09ed82ba`（worktree HEAD 與該 SHA 相同；表內指令省略 SHA 者亦以其為準）；pathspec 皆為 `'*.py'` 或指定檔，被掃的是程式或 DEC，本檔本身不在掃描範圍。

| # | 宣稱 | 指令（摘要） | 結果 |
|---|---|---|---|
| V1 | `rule_version`／`policy_version` 在程式碼中幾乎不存在 | `git grep -n -i -E "rule_version\|policy_version" 09ed82ba -- '*.py'` | 僅命中 `tests/test_v2_domain_allocation_evidence.py` 一行，內容是斷言 `rule_ref.status == "not_defined"` 且**沒有** `rule_version` 屬性 |
| V2 | repo 內沒有 `build_ai_summary` | `git grep -n "build_ai_summary" 09ed82ba -- '*.py'` | 無輸出（rc=1） |
| V3 | 沒有 Fake Provider | `git grep -l "FakeProvider\|fake_provider" 09ed82ba -- '*.py'` | 無輸出（rc=1） |
| V4 | Digest／OneBrain 字樣在程式中只出現在守衛與註解 | `git grep -il -E "decision_digest\|DecisionDigest\|onebrain\|one_brain" -- '*.py'` | 命中 3 檔：`ui_v3/shell/registry.py`（🤖 頁在 Phase 7 前建構時即擋）、`ui_v3/viewmodels/action_slot.py`（docstring 寫「本批不實作 Risk Cap、System Action State、Decision Digest、OneBrain」；`ACTION_SLOT_SOURCES_ENABLED = False`）、`tests/test_doc_counters.py`（檔名清單）。**本組只讀了命中行，未通讀三檔** |
| V5 | 現行 `infra/llm.py` provider chain 仍是 gemini→anthropic→openai | 讀 `infra/llm.py::_DEFAULT_CHAIN` | `["gemini", "anthropic", "openai"]`；與 75 第 3.2 節描述一致，75 第 17 節禁止本輪改它 |
| V6 | 市場指標七鍵在程式內各有 `source` 二元組（供應者，序列） | 讀 `services/v2_tables/market_indicator.py::INDICATOR_SPECS` | `vol_index`＝Yahoo `^VIX`；`fx_twd_per_usd`＝Yahoo `USDTWD=X`；`credit_spread_pct`／`term_spread_pct`／`policy_rate_pct`＝FRED；`leading_index`／`coincident_index`＝`FinMind:TaiwanBusinessIndicator`（此二鍵 `phase1` 為 `pending`，原因＝來源不給公布日）。表列本身只寫 `source_tier`＝「市場指標」 |
| V7 | `stale_after` 沒有任何已裁的值 | `git grep -c "stale_after" 09ed82ba -- docs/DECISIONS.md` | 1 行，即 `DEC-2026-11-08-02` 的「仍未授權」欄把 `stale_after` 列為保留原 Gate 者；DEC 內無數值 |
| V8 | 「平行作業完成 UI + OneBrain」不是 repo 內的 DEC | 對 `DECISIONS.md`／`HANDOFF.md`／`BACKLOG.md`／`PROJECT_RULES.md` 做字面 grep | 無命中此句；`PROJECT_RULES.md` 第 16 節標題為 A／B／C 三線平行（自稱客戶、待核） |

**方法限制（必讀）**：
1. 以上全稱句（「沒有」「零命中」）是字面 `git grep`，**改名、動態組字串、別名不在內**，動態 import 未驗。
2. `docs/DECISIONS.md`（體積大）只讀與 OneBrain、D1～D10、D2 相關的條目，未通讀；`BACKLOG.md` 只讀相關列。
3. 本機沒有 `requests` 等依賴，**未執行任何與業務相關的測試**；唯一跑的是第 6 節列出的三支文件守衛。
4. 未連網、未碰憑證與 Sheet、未改任何既有檔。

---

## 2. Digest 已有／尚缺的決策逐項表

**「誰裁示」欄的讀法（作者讀法，可被客戶推翻）**：
- **客戶**＝命中 `PROJECT_RULES.md` 第 4 節 Stop／Decision Gate 者（data identity、正式 threshold 值或語意、正式公式或投資語意、產品方向、會改變投資判斷的 AI 行為）；另依 `DEC-2026-11-17-05` 第 8 點：正式資料契約、資安與上位規則變更仍由客戶核准。
- **ChatGPT 總管**＝依 `docs/HANDOFF.md` 分工，負責產品、架構、UI、金融語意與資料契約的**規劃、提示語與選項整理**；**不單方核准**上列客戶事項。
- **技術可自決**＝專案 AI 在已授權範圍內、不改語意、不新增欄位／來源／門檻的純事實整理。

### 2.1 逐域 R／O／E 語意

**FACT**：跨域通則已核准（67 第 8.6 節，`DEC-2026-11-02-07` UI-9 A）：Required＝identity、value、as_of、health、rule result、System Action State（缺時輸出「無法判定」並列缺什麼）；Optional＝歷史序列、補充 provenance；Excluded＝widget 展開狀態、scroll、container 順序、cosmetic color、session-only display metadata，另加 67 第 8.11 節的 delivery metadata 與 Notification Preference；`confidence` 不納入（67 第 5.3 節）。「例」字表示非封閉清單。**逐域清單**依 `DEC-2026-11-11-04`（D2-G1＝B 修正版）須逐列審核、不得整欄升格，且 D2-G3＝A 首批限基金身份、NAV、績效。

| 資料域（沿用 `onebrain_evidence_coverage_gap_audit_2026_11_08.md` 第 3 節九域） | 現況出處與已核准 | 缺口 | 誰裁示 | AI 推薦與理由 |
|---|---|---|---|---|
| 基金身份 | `T-ID1`（R-ID-1，`DEC-2026-11-13-06`）；R-ID-2（`full_key`）、R-ID-3（`ok`）Pending | `full_key`／`ok` 的契約；EXP 選股池代碼命名空間另案；跨類別 identifier（BL-0527 第 5 項，隨 DG-2） | 客戶（data identity） | 維持逐列審核；R-ID-3 依附 R-ID-2，建議同批問。理由：`ok` 只表示代碼通過解析鏈，不代表基金存在（`d2_contract_approval_prep_2026_11_12.md` N4），單獨核准易被誤讀 |
| 基金 NAV | `T-NAV1`／`T-NAV2`／`T-NAV4`／`T-NAV5` 已核契約文字；R-NAV-3（`fetched_at`）暫緩；R-NAV-6（`ccy_source`）Pending | R-NAV-3 等 D3(b) 的新鮮度語意；R-NAV-6 是否進契約欄；NAV 10 日規則（`DEC-2026-11-05-03` 禁止升格） | 客戶 | R-NAV-3 不單獨推進，併入 D3(b)＋D7 一題問（理由：觀測時間與取得時間的語意與 stale 門檻互相依賴）；R-NAV-6 與 R-NAV-5 成對，建議在 R-NAV-5 實作狀態穩定後再問 |
| 基金績效 | R-PERF-1～8 全 Pending（1／3／6 是與已核列重複的列，不獨立計）；1Y 含息只在舊站已裁（`DEC-2026-10-23-02` 1B），New UI2 未核准 | 報酬口徑（BL-0524、BL-0427 五題）；`calc_metrics` 1Y 窗口估算路徑無旗標（BL-0547） | 客戶（正式公式） | 暫不推進。理由：綁正式公式 Gate，且 D2-B 要求四項同源證據；`d2_contract_approval_prep_2026_11_12.md` 已建議 1Y 含息排最後 |
| 市場與總體 | 無逐鍵已核準項；跨域通則適用 | 逐鍵 R／O；regime 聚合規則（Formula Gate）；stale 門檻；provider 表（見 2.4） | 客戶 | 依 D2-G3＝A **延後、不啟動契約草案**；「延後」≠ Excluded。維持原狀 |
| 持倉／資產配置 | `allocation_evidence`（內部候選，檔頭自稱 not approved vocabulary）；持倉占比 C 延後（`DEC-2026-11-08-05`） | G-1 分母、G-3～G-5、11 個 open gate | 客戶（金融語意） | 維持延後 |
| 配息／事件 | Excluded 通則已核（67 第 8.11 節）；納入 Required 或 Optional「隨 Digest schema Gate」 | `pay_date` amendment（BL-0534）；`date_status` 無正式契約 | 客戶 | 維持延後 |
| FX／利率／景氣 | 通則適用；FX 閘門維持關閉（`DEC-2026-11-08-02`） | 開閘證據軌；國發會兩鍵來源不給公布日 | 客戶 | 維持延後 |
| 資料健康／Freshness | 三軸分開原則（`DEC-2026-11-06-02`）；D3(a) 對照表 | 狀態字彙契約化（D3(a) 非契約）；門檻（D3(b)）；准入（D9） | 客戶 | 見 2.3 |
| Rules／Risk Cap／Action State | 六行動詞語意；Risk Cap 未定義前恆為「無法判定」（67 第 8.2 節） | Risk Cap、減碼 trigger（BL-0495／0496）；Rule ID（2.5） | 客戶 | Risk Cap 與 trigger 建議這一輪不問（見第 3 節 D4-1／D4-2）；Digest 內一律以 Missing 表示 |
| Supporting／Counter-evidence | 「最大反證」輸出方向已核（67 第 8.7、8.9 節） | 反證定義（D5）；程式內零生產者 | 客戶（投資語意） | 採 evidence 檔提案：反證＝「某個可客觀檢查、且來自已記錄資料的事實出現，就推翻本次判讀」，**但這是提案不是裁示** |

**INFERENCE（解讀不確定性，請讀者注意）**：D2 核准欄位數寫作「5」，但候選檔列內對 R-NAV-1／2／4／5 仍標「Required 升格／New UI2 適用仍未核」。兩處並讀，較嚴的讀法是：**5 列是契約文字已核，Required 地位尚未核**。若客戶原意是「同時核准為 Required」，需客戶澄清；本組採較嚴讀法，因為 D2-G1 明寫「不得把整欄 Required 自動升格」。

### 2.2 as_of 語意

| 項 | 內容 |
|---|---|
| 現況出處 | 67 第 5.3 節：`obs_date`／`release_date`／`nav_date`／`ex_date`／Cell `observed_at` 欄名不統一；PIT 取哪一欄未定。67 第 8.5 節：`as_of`（觀測日）、`release_date`（公布日）、`retrieved_at` 分開；「來源不提供公布日就寫『來源未提供』，不虛構」；global timestamp 只代表 render 時間。`T-NAV2`（`nav_date`）已核契約文字，客戶附註：各 provider 日期語意未驗證、日期合理範圍僅是實作事實、不升格為門檻；不核准 NAV 10 日規則、「今天」的正式定義、未來日期語意、PIT、FX 對齊、1Y `as_of`。 |
| 缺口 | (1) PIT 對齊用哪一欄（`CLAUDE.md` §2.3 與各域欄名不一）；(2) 證據物件**無根層 as_of／產生時間**（稽核 V12：`allocation_evidence` 不攜帶 `last_synced_at`／`opened_on`）；(3) 績效輸出沒有 `as_of` 與窗口起訖日（R-PERF-5／6）；(4) 國發會兩鍵來源不提供公布日（`phase1`＝`pending`）。 |
| 誰裁示 | 客戶（涉 PIT 與正式 threshold 時走 Decision Gate，67 第 5.6 節第 3 點） |
| AI 推薦 | **分兩段問**：第一段只問命名與結構（Digest 每個決策欄位各自帶 `as_of`／`release_date`／`retrieved_at` 三欄、缺的欄位寫「來源未提供」，不得用 render 時間頂替）——這與 67 第 8.5 節已核方向一致，風險低；第二段才問 PIT 取哪一欄與 `release_date` 缺時的處置。理由：兩段性質不同，第一段不涉投資語意，第二段牽動回測與 lookahead（`CLAUDE.md` §2.3）。 |

### 2.3 Freshness（stale 判定）

| 項 | 內容 |
|---|---|
| 現況出處 | 67 第 8.5 節 Freshness Policy schema：`policy_id`、`frequency`、`expected_lag`、`stale_after`（**值待裁示**）、`authority`。D3(a) 對照表（`docs/evidence/data_state_vocabulary_crosswalk_d3a_2026_11_08.md`）已盤點 17 組詞彙族；其檔頭說明該表為單組作者、不構成契約。`DEC-2026-11-08-04` Q4：缺資料沿用「資料未備／無法判定」，不新增「過期／衝突」正式詞、不改門檻。 |
| 缺口 | (1) `stale_after` 逐來源值（V7：DEC 內無值）；(2) 是否新增獨立 `stale` 狀態（新字樣另受 `APPROVED_WORDING` Gate）；(3) conflict 判定（容差、何謂同 as-of 不一致）；(4) NAV 10 日規則跨頁語意 (a)～(e)（`DEC-2026-11-05-03` 待決）；(5) 月度 `[STALE: XXd]` 標籤沿用與否；(6) 新鮮度門檻散在三處（稽核 R7，作者採底稿、NOT VERIFIED）。 |
| 誰裁示 | 客戶（正式 threshold 值或語意）。D3(b) 與 D7 在 `onebrain_decision_gate_route_and_risk_check_2026_11_08.md` 建議合併為一題。 |
| AI 推薦 | 沿用該提案：**按來源逐一定，不用單一全站天數**；先由專案 AI 附各來源實際發布延遲事實，再請客戶定天數；不一致時不顯示任何一方、保留被捨棄來源與差異。理由：各來源更新週期差異大，統一數字會誤判；且在 D3(b)＋D7 裁示前，Digest 內 stale 一律以「門檻未裁示（`threshold_pending`）」表示，不得由 AI 自行判舊。 |

### 2.4 Provider（兩個意思，必須分開）

| 意思 | 現況出處 | 缺口 | 誰裁示 | AI 推薦 |
|---|---|---|---|---|
| **A. 資料 Provider（Digest 的 `source`）** | 67 第 5.3 節＋V6：市場指標七鍵程式內有 `source` 二元組，表列只有 `source_tier`；NAV 域 `source_tier`（`T-NAV4`）核准文字明寫「是資料表類別標籤，不是資料供應者名稱」，**不新增 Provider 欄，不核准旁路 `provenance[fund_code].source` 與 `chain.data_source`**。 | 逐項 provider 表（BL-0527 第 2 項）：市場指標七鍵可由 `INDICATOR_SPECS` 反查，**市場 view 的 12 個 domain 的 provider 本組未讀 NOT VERIFIED**；NAV 域 provider 契約**未核准**；FX 鍵 provider 依閘門。 | provider 對照**表**（唯讀事實）→ 技術可自決；把 provider **升格為 Digest 契約欄**→ 客戶 | 專案 AI 可另批產出「唯讀 provider 對照表」，明標「事實整理、不是契約」；**不得**以此為由在 NAV 域新增 Provider 欄（`DEC-2026-11-17-06` 已明確不核准）。理由：事實整理不改語意，但契約欄牽動 `T-NAV4` 的限制 |
| **B. AI Provider（OneBrain 的 Claude／fallback）** | 75 第 4 節：Claude Primary 是 policy；`infra/llm.py` 現行 chain 仍是 gemini 優先（V5）。 | typed interface、fake provider、config policy（OB-01）；皆未存在（V3） | 客戶（見第 5 節） | 第 5 節處理，本表不重複 |

### 2.5 Rule ID／`rule_version`／門檻引用格式

| 項 | 內容 |
|---|---|
| 現況出處 | 79 UI-10 A（`DEC-2026-11-02-07`）：Rule Registry 唯讀殼先做；**Rule ID 編碼、`rule_version`、門檻引用格式另走格式 Gate，非機械式**。67 第 8.2 節：System Action State 必帶「Rule ID（若存在）」。V1：程式內只有一個「沒有 `rule_version`」的測試斷言。現存「規則結果」只有使用者門檻驅動的比較（`HLD-0`、`ALO-0`、`EXP`），住在 L3 呈現層（67 第 5.2 節第 3 點）。 |
| 缺口 | (1) 編碼格式；(2) 版本格式；(3) 門檻引用格式；(4) 規則結果的正式來源層（要不要先下沉到 domain／service）；(5) 目前正式 deterministic investment rules 尚不存在，所以 Rule ID 實際指向的物件，現階段多半是「使用者設定的比較」而非投資規則。 |
| 誰裁示 | D4-3（格式）：評估為**不涉投資語意的命名格式**（evidence 檔判斷），但 79 UI-10 明寫「另走格式 Gate」→ 客戶；Rule ID 指向的規則內容（Risk Cap、trigger）→ 客戶（投資語意）。 |
| AI 推薦 | 先問格式、不問內容（沿用 evidence 檔 D4-3 一鍵問法）。理由：格式是後續每一條規則與每一句 AI 結論回溯的共同依賴，且不需要先定義 Risk Cap。**注意**：因現階段沒有正式投資規則，格式被核准後 Registry 仍會近乎空白，那是誠實狀態（79 UI-10 風險欄已說明）。 |

### 2.6 Evidence trace（兩種 trace，不要混用）

| 種類 | 現況出處 | 缺口 | 誰裁示 | AI 推薦 |
|---|---|---|---|---|
| **資料血緣 trace（C-5）** | 67 第 8.7 節固定五段：AI sentence → Digest fields → Rule Result → Rule ID → Canonical Data → source／as_of；每次正式輸出至少含核心理由、使用的 Rule Result、最大反證、Missing／uncertainty 清單。 | 句子→依據的**對映格式**（規格 `AI-3`，BL-0527 第 6 項）未定；「AI 不讀畫面」「AI 輸出不回寫 canonical」兩條守衛 repo 內沒有專門守衛（BL-0527 自述；稽核 R14 NOT VERIFIED）。 | 對映格式→客戶（67 第 8.7 節「仍待」）；守衛→技術可自決，但屬新增測試，需在授權範圍內 | 守衛先於格式：先補「AI 不讀畫面／不回寫」的測試守衛，再問對映格式。理由：守衛不涉語意，且能在 Digest 存在前就卡死最危險的兩種違規 |
| **分析 trace（75 第 7 節）** | `analysis_id`、provider、model、prompt／policy／output schema version、source refs、fingerprint、usage／cost、cache、fallback。全部**未實作**（75 第 3.2 節自陳）。 | 與資料血緣 trace 的銜接：fingerprint 要納入的 Digest schema version 與 rule version（75 第 6.2 節）目前**都不存在** | 客戶（Schema Gate） | 不單獨推進；隨 OB-04（trace schema）排在 Digest schema Gate 之後。理由：fingerprint 的輸入在 Digest 定案前不存在 |

### 2.7 其他仍缺但不在題目六項內的項目（只列）

| 項 | 出處 | 說明 |
|---|---|---|
| Digest id／schema version／fingerprint／policy version | 67 第 8.6 節 Audit 欄位群；75 第 6 節 | 屬 Digest schema Gate（D2-G2：D2 逐域契約完成後才另行提） |
| 跨類別 identifier | BL-0527 第 5 項 | 隨 DG-2 三層身份；shadow 旗標預設關 |
| Risk Cap 欄位 | 67 第 5.4 節 | 只能是 Missing／未定義 |
| 狀態字彙契約 | BL-0527 第 1 項；D3(a) | 對照表已有，**契約**未有；字彙至少三套（67 第 5.3 節）／至少五套（稽核 R6，兩者皆未逐一點算） |

---

## 3. 與已裁示 D1～D10 的關係

**FACT 來源**：`onebrain_decision_gate_route_and_risk_check_2026_11_08.md`（D1～D10 是該檔的研究提案編號，**不是客戶裁示編號**）；客戶實際裁示見各 DEC。

| Gate | 狀態（截至 `09ed82ba`） | 依據 | 仍未決／與 Digest 缺口的關係 |
|---|---|---|---|
| D1 路線 A／B／C | **已定**：採 C（資料契約先行，Digest 後續再建）為規劃方向 | `DEC-2026-11-08-02`（要點轉述，非逐字） | 「正式 Digest 施工」「Phase 7／Provider／Claude API runtime」明寫未授權 |
| D2 各域 R／O／E | **部分**：首批限身份、NAV、績效；5 列契約文字已核（R-ID-1、R-NAV-1／2／4／5）；R-NAV-3 暫緩；其餘 Pending | `DEC-2026-11-11-04`、`-13-06`、`-14-07`、`-17-06` | 其餘六域延後；Digest schema 是獨立 Gate，順序在 D2 之後 |
| D3(a) 字彙對照表 | **已產出**（唯讀文件，非契約） | `DEC-2026-11-08-02`；crosswalk 檔 | 對照表不是契約；計數為作者判定 |
| D3(b)＋D7 stale／conflict／NAV 10 日 | **未決** | `DEC-2026-11-05-03` 禁止升格；V7 | 擋 R-NAV-3、2.3 全部、BL-0527 第 3 項 |
| D4-1 Risk Cap／D4-2 減碼 trigger | **未決**（建議延後，不阻擋其他題） | BL-0495／0496 | Digest 一律 Missing |
| D4-3 Rule ID 格式 | **未決** | 79 UI-10；BL-0527 第 4 項 | 擋 2.5 |
| D5 反證定義 | **未決** | evidence 檔 D5 | 擋 67 第 8.9 節「最大反證」區的內容 |
| D6 💼 G-1／G-3／G-4／G-5 | **未決**（G-2 已授權，不在此題） | `DEC-2026-11-05-02` 起 | 持倉域 R／O／E 的前提 |
| D8 FX 閘門 | **已定**：維持關閉、不以相同方法立即重跑 | `DEC-2026-11-08-02` | 補跑與開閘仍未授權；`FX_OBS_DATE_RULE_VERIFIED` 維持 `False` |
| D9 BL-0545 合法輸入 | **未決**，待外部輸入（全域唯一 NEXT 且 BLOCKED） | `docs/HANDOFF.md`；BL-0545 | 真實覆蓋率 NOT VERIFIED；影響「正式資料准入」定義 |
| D10 授權鏈重確認 | **已定**：保留歷史摘要、標示無逐字原話且未重新追認 | `DEC-2026-11-08-03`（客戶逐字指示） | 不是追認；`allocation_evidence` 的授權鏈仍屬要點轉述 |

**INFERENCE**：D1～D10 裡**已定**的是方向性與治理性的四題（D1、D3(a)、D8、D10）；**資料語意與門檻性**的題（D3(b)、D7、D4、D5、D6、D9）與 D2 大部分仍未決——這正是 Digest 缺口無法由技術側單獨填補的原因。

---

## 4. 最小可行決策序列（不替客戶裁決）

### 4.1 先釐清「阻擋」到底擋什麼

**FACT**：
- 75 第 16 節：OB-01（Provider abstraction：typed interface＋fake provider）前置＝「本檔」；OB-02（normalized input／Digest adapter contract）前置＝67、BL-0527；OB-09（舊線 AI 遷移）前置＝BL-0528。
- 75 第 18.2 節：OB-B 設計／fake provider 是「下一個 OneBrain 工作」，但「如果當時仍有 BL-0528、Risk Cap、Decision Digest schema 等上位 blocker，先依既有 Gate 處理，不得繞過」。
- 67 第 5.7 節 Stop Gate 1：Decision Digest 契約定義前，不寫 prompt 或 LLM glue。67 檔頭：Risk Cap／trigger 未完成前，不做假的 AI 投資建議。

**兩種讀法（不替客戶決定）**：
- **讀法 1（逐表讀）**：OB-01 不依賴 BL-0527／0528 的內容；只要 OB-B 範圍限定在「與 Digest 內容無關的 transport 介面」，兩者不構成 blocker。
- **讀法 2（保守讀）**：75 第 18.2 節的「Decision Digest schema 等上位 blocker」把 Digest 缺口都算進去，OB-B 在 Digest schema Gate 前不得動。

### 4.2 最小序列（RECOMMENDATION）

| 序 | 要裁的題 | 誰 | 解除什麼 | 先決條件 | 推薦答案與理由 |
|---|---|---|---|---|---|
| **Q1** | OB-B（離線 typed interface＋Fake Provider）是否獲得單獨、限縮的授權，及範圍文字（第 5 節方案 B） | 客戶 | OB-B 本身；同時回答 `DEC-2026-10-31-03`「每階段另行裁示」 | 無 | 推薦給（限縮版）。理由：最小、可逆、不碰 Digest 內容、符合 75 第 18.2 節指定的下一步 |
| **Q2** | 明確聲明「BL-0528 與 BL-0527 不是 OB-B（限縮版）的 blocker，只擋 OB-02／OB-09」，並重申 OB-B 不改 `infra/llm.py` chain、不碰舊線 AI | 客戶（或在 Q1 同一句裁示中順帶） | 消除 75 第 16 與 18.2 兩節的歧義 | Q1 | 注意：此聲明等同改變 `docs/v2/75` §18.2 的讀法，客戶裁示後須同步記入 `DECISIONS.md`。推薦併入 Q1 一次問。理由：不併入，OB-B 做完仍會被 18.2 節的字面擋下 |
| **Q3** | D4-3：Rule ID／`rule_version`／門檻引用格式 | 客戶 | BL-0527 第 4 項；2.5；後續 trace | 無 | 推薦先問（純格式）。**這是解除 BL-0527 對 OB-02 阻擋的第一步，不是 OB-B 的必要條件** |
| **Q4** | D3(b)＋D7 合併：stale／conflict／NAV 10 日 | 客戶 | BL-0527 第 3 項；R-NAV-3；2.2 第二段、2.3 | 專案 AI 先附各來源發布延遲事實 | 推薦按來源逐一定（evidence 檔提案）。**依賴最重，建議排在 Q3 之後** |
| **Q5** | D2 首批剩餘列逐列：R-ID-2／3、R-NAV-6、（R-NAV-3 隨 Q4）、R-PERF 系列 | 客戶 | 首批三域的 R／O／E 完整 | Q4（R-NAV-3）；績效綁正式公式 Gate | 推薦只推身份／NAV 剩餘列；績效暫緩（見 2.1） |
| **Q6** | Digest schema Gate 是否提出 | 客戶 | OB-02、fingerprint、trace 欄位 | Q3～Q5 完成（D2-G2：先 D2 後 Digest） | 現在不問 |
| **Q7** | D5 反證定義 | 客戶 | 🤖 頁「最大反證」區內容 | 無（生產者另需 D4） | 可獨立問；不阻擋 OB-B |
| 延後 | D4-1／D4-2 Risk Cap 與減碼 trigger；D6；D9 | 客戶 | 方向性行動輸出 | — | 這一輪不問；Digest 一律 Missing／「無法判定」 |

**INFERENCE**：若客戶採讀法 1，**只需 Q1（含 Q2）一題**即可解除對 OB-B 的阻擋；Q3～Q6 是解除 BL-0527 對 OB-02 的阻擋，與 OB-B 可平行（對應 `PROJECT_RULES.md` 第 16 節三線平行，但各線遇 Gate 照停）。若客戶採讀法 2，則必須先走完 Q3～Q6，OB-B 才能動。**本組不知道客戶採哪個讀法；這本身就是 Q2 要問的事。**

---

## 5. 與 `DEC-2026-10-31-03`、`DEC-2026-11-08-02` 的關係：離線 interface／Fake Provider 是否落在限制外

### 5.1 FACT：兩筆 DEC 的相關文字

| DEC | 相關文字（摘要，非逐字引用全文） | 性質 |
|---|---|---|
| `DEC-2026-10-31-03` | 影響範圍欄：「OneBrain 僅為未來架構，沒有任何 runtime 工作被授權；**任一後續階段（fake provider、shadow、整合、production）都須另行裁示**」。決策摘要列出未來順序：Architecture／Governance → Provider abstraction＋fake provider → Claude shadow → controlled low-risk integration → evaluation → production enablement。 | 決策者欄：客戶（客戶對話本身執行組未見，原文由總管轉存逐字檔） |
| `DEC-2026-11-08-02` | 「仍未授權」欄：「正式 Decision Digest 施工＝未授權；**Phase 7／Provider／Claude API runtime＝未授權**；D2 與正式 Digest schema＝未核准」。D1 採方案 C 是**規劃方向已核准**，不產生程式。 | 要點轉述，非逐字，客戶可推翻 |
| 75 第 18.2 節 | 唯一 OneBrain handoff point：下一個工作只能是 OB-B Provider abstraction 的**設計／fake provider batch**，不得直接接正式 Claude API；第 18.1 節與第 17 節明寫本檔不構成 runtime 動工授權。 | 架構文件（客戶裁示的落地），本身不是授權 |

### 5.2 INFERENCE：為什麼專案 AI 與 ChatGPT 都不能自行宣告「落在限制外」

1. `DEC-2026-10-31-03` 的字面把「fake provider」**點名**列在需另行裁示的階段內。要主張「離線 interface 不算 fake provider 階段」，需要把 interface 與 fake provider 拆開——這是一個**解讀**，而且拆開後的 Fake Provider 仍然是被點名的那一項。
2. `DEC-2026-11-08-02` 的「Provider」可讀作「Provider runtime」（限定詞掛在 runtime 上），也可讀作「Provider（整個項目）與 Claude API runtime」。**文字本身不能決定哪一個**，該 DEC 又是要點轉述、非逐字。
3. 75 第 18.2 節指定了 OB-B 為下一個工作主題，但同檔第 18.1 與第 17 節又明寫不構成 runtime 動工授權，並在 18.2 加了「上位 blocker 先處理」的條件。
4. `DEC-2026-11-17-05` 第 8 點：正式資料契約、資安與上位規則變更仍由客戶核准；ChatGPT 的 UI／架構規劃職責不取代。`PROJECT_RULES.md` 第 4 節的「產品方向」「會改變投資判斷的 AI 行為」是 Stop／Decision Gate。
5. 「平行作業完成 UI + OneBrain」的轉述不是 DEC（V8），且標〔待核〕。
→ 因此「是否落在限制外」是客戶才能解的題。（依 `CLAUDE.md` §-1.5.1c 判定 3 類推：登記與規劃不等於授權。）

### 5.3 選項表

**OB-B 的潛在內容（用於比較；皆為離線）**：typed Provider interface（provider-neutral request／response／error，不含任何具體 SDK）、一個只能回傳「AI 分析暫不可用／無法判定」或固定錯誤分類的 Fake Provider、純單元測試；**不含**真實 HTTP、金鑰、prompt、Digest 內容、任何 UI 接線、對 `infra/llm.py` chain 的修改。

| 方案 | 內容 | 優點 | 缺點 | 風險 |
|---|---|---|---|---|
| **A. 視為落在限制外，直接做** | 不另請示，把離線 interface＋Fake 當作 75 第 18.2 節指定工作 | 最快；與 75 字面指定的下一步一致 | 與 `DEC-2026-10-31-03`「fake provider 須另行裁示」字面衝突；等於由專案 AI 單方解讀客戶 DEC | **高**：違反 Stop／Decision Gate 精神；若客戶原意不同，需回退；依 `PROJECT_RULES.md` 第 4 節屬客戶層級事項，不應自決 |
| **B. 請客戶一句話裁示限縮範圍（推薦）** | 客戶明文授權「離線 typed interface＋Fake Provider（只回傳降級狀態、不含 prompt／Digest 內容／UI 接線／真實連線／SDK／金鑰）」，並同句聲明 BL-0527／0528 不是此範圍的 blocker | 解決兩筆 DEC 的字面歧義與 75 第 16／18.2 的歧義；範圍小、可逆、純文件＋離線測試；不碰 Digest | 需要客戶一次表態；OB-B 產出短期無使用者可見成果 | **低（推論；成立前提是客戶授權文字夠窄）**：Fake Provider 若被誤接到 UI 會變成「假的 AI 輸出」——故授權文字須明寫「不得被任何頁面渲染」 |
| **C. 暫不做 OB-B，先走 Q3～Q6 至 Digest schema Gate** | OB-B 排在 OB-02 之後；對應讀法 2 | 完全避開 Stop Gate 1 與 Fake 的疑慮；Digest 契約先定可讓 interface 的 request 型別一次到位 | 最慢；OneBrain 線在 D2 完成前無可做的工作；與 `PROJECT_RULES.md` 第 16 節三線平行的精神相悖（B 線資料契約已在走，OneBrain 線卻閒置） | 低；但有「契約拖很久，interface 一直等」的進度風險，且 interface 日後可能因 Digest 定案而重做 |
| **D. 把 OB-B 與 Digest adapter contract（OB-02）合併做** | 一次做 interface＋Digest 輸入契約 | 看似減少往返 | 觸 67 第 5.7 節 Stop Gate 1（Digest 契約定義前不寫 prompt／LLM glue）與 D2-G2（Digest schema 為獨立 Gate）；一次問太多題 | **高**：易被視為提前啟動 Digest schema 研究／施工，這是 `DEC-2026-11-11-04` 明寫不授權的 |

**RECOMMENDATION：方案 B。** 理由：(1) 兩筆 DEC 的字面都沒有明確放行或明確禁止「離線 interface」，只有客戶能消歧；(2) B 是唯一能同時避開「專案 AI 自行解讀客戶 DEC」與「OneBrain 線整段閒置」兩種壞結果的方案；(3) 範圍可寫得夠小，使其不需要任何 Digest 內容，因此不與 BL-0527／0528 產生實質競爭；(4) 與 75 第 15 節的 OB-B 定義（typed interface、fake provider、provider-neutral request／response／error、configuration policy、不接正式 Claude）逐項一致。**建議客戶授權文字至少包含的邊界**（供客戶改寫，不是已核准文字）：不接任何真實 provider、不安裝 SDK、不讀任何金鑰、不寫 prompt、不放 Digest 內容、Fake 只回降級／不可用狀態，不得輸出任何看似分析、判斷或信心的內容，且不得被任何頁面渲染成分析結果、不改 `infra/llm.py` 現行 chain、不動舊線 AI（BL-0528）、不改 UI。

**INFERENCE（一個必須先講的反面）**：即使客戶選 B，也**不解決** Q3～Q6；OB-B 完成後，下一個 OneBrain 工作（OB-C 起）仍受 Digest 缺口與 Risk Cap 未定義限制，Claude shadow 之前仍須另行裁示。

---

## 6. 我沒有查證的部分

1. **本文件整體是單組作者產出，未經第二組獨立驗證**（`CLAUDE.md` §-2 規則 6）；第 0 節的全稱句（「0 個資料域完成」「零命中」）只代表字面指令結果。
2. 第 2.1 節「5 列只核准契約文字、Required 升格仍未核」是**對 DEC 與候選檔列內狀態並讀的較嚴解讀**，客戶原意可能不同。
3. 市場 view 12 個 domain 的 provider、`market_view` 的欄位、`docs/v2/79` 全文、`docs/v2/80`／`82` 皆未通讀；僅引用 67、75 與 evidence 檔已轉述之處。
4. D2 的 17 列內容取自候選檔「Required 逐列待審表」與核准準備檔；R-PERF 系列各列細節本組只讀摘要。
5. D1～D10 的「未決」狀態是對 `DECISIONS.md` 相關條目的讀取結果；**不排除另有尚未登記的客戶口頭裁示**。
6. 多筆近期 DEC（`DEC-2026-11-17-05`、`-17-06`、`-18-01`）的決策者欄標「自稱客戶、待核」；本文件**引用其內容但不替它們背書真實性**。
7. 方案 B 的「低風險」判斷是作者推論，未做任何實作驗證；Fake Provider 被誤接 UI 的可能性只能靠授權文字與測試守衛防，未評估具體守衛設計。
8. 是否觸發 Model／Effort Change Gate（`PROJECT_RULES.md` 第 5.1 節）：本文件為 docs-only 研究，**未評估** OB-B 施工階段是否屬需切換模型的等級。
9. 沒有跑任何業務測試；依賴齊全環境下三支文件守衛是否綠，只能由 CI 驗。

---

## 7. 不構成授權聲明

- 本文件**不核准**任何 Schema、欄位、門檻、Rule ID 格式、provider 欄、Fake Provider、OB-B 範圍或任何施工；不新增任何程式、不寫 prompt 或 LLM glue；不產生 Risk Cap、System Action State、減碼、機率或信心數字。
- 第 2 節各列「AI 推薦」、第 4 節序列與第 5 節方案 B，皆為**專案 AI 讀法，可被客戶推翻**，不是 DEC。
- 「平行作業完成 UI + OneBrain」僅為研究題目來源（〔待核〕轉述）；不改變任何 Stop／Decision Gate，也不解鎖 BL-0545（仍為全域唯一 NEXT）。
- 不改任何既有檔；`docs/BACKLOG.md`、`docs/HANDOFF.md`、`docs/DECISIONS.md` 的索引同步不在本批範圍（若需要，另批處理）。
