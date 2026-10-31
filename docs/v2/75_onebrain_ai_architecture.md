# 75｜OneBrain AI 架構方向（Phase A：Architecture / Governance）

> **性質**：正式架構方向與邊界紀錄；本輪只做 Architecture / Governance，不構成 runtime 動工授權。
> **位階**：本檔不得凌駕 `CLAUDE.md`、`PROJECT_RULES.md`、子法 1、`docs/v2/44_fund_ui_ssot.md`、`docs/v2/67_ai_action_vocabulary.md`。AI 行動語意、Decision Digest 與 One AI Brain 既有正式條文仍以 `docs/v2/67_ai_action_vocabulary.md` 為準；本檔只補足 Provider、routing、cache、trace、budget、prompt governance、structured output 與 rollout 邊界，避免建立第二套 AI 憲法。
> **量測基準**：GitHub main `9e508046277a9e41f07bcba67d91cc8f97c7517a`（2026-10-31 驗證）。同時存在 Draft PR #1111（D-3／OAuth 裁示落盤與阻擋項修正），因此本輪刻意不碰 #1111 正在修改的既有治理／產品檔案。
> **核心設計原則**：**Data is evidence. Rules are constraints. OneBrain is reasoning.**

---

## 1. 正式定位

OneBrain 在本專案中的正式定位：

> **AI 推理／協調層（AI Reasoning & Orchestration Layer）**。

OneBrain 不是：

- 資料來源；
- ETL；
- 指標計算器；
- 財務公式引擎；
- Risk Cap 規則本身；
- UI；
- 資料庫；
- 自行搜尋資料、補資料或回寫客觀資料的 Agent。

固定概念鏈：

```text
資料來源 / API / DB
  ↓
取得、清理、標準化、驗證、追溯
  ↓
Canonical / Objective Data
  ↓
Deterministic Domain Calculations / Rules / Risk Engine
  ↓
Decision Digest / Normalized AI Input
  ↓
OneBrain AI
  ↓
分析、推理、解釋、矛盾整合、情境說明
  ↓
UI / 決策輸出
```

與 `docs/v2/67` 的既有鏈一致：Raw Data → Validate → Normalize → Domain / Formula → Deterministic Rules → Risk Cap → AI Explanation。

---

## 2. 不可變邊界：資料層 ≠ AI 推理層

OneBrain 只能讀取**已取得且可追溯的現有資料**。禁止 OneBrain：

1. 自行創造缺失資料；
2. 將 missing 補成 0；
3. 將 unavailable 當 neutral；
4. 將 not evaluated 當 safe；
5. 因缺資料自行假設「無風險」；
6. 回寫或修改 raw / canonical objective data；
7. 以自然語言推論取代本應由 Python / rule engine 計算的公式；
8. 在沒有來源的情況下製造市場事實；
9. 以 LLM 結論覆蓋 deterministic rule / Risk Cap；
10. 把「AI 沒有執行」轉譯成 HOLD / SAFE / neutral / 無風險。

必要資料不足時，沿用本專案既有 Missing / 無法判定契約：

> **資料不足／無法判定**，不得猜測。

---

## 3. Repo 現況盤點（2026-10-31）

### 3.1 已存在，可沿用的骨架

| 位置 | 現況 | OneBrain 判定 |
|---|---|---|
| `docs/v2/67_ai_action_vocabulary.md` | 已有 One AI Brain、Decision Digest、固定輸入／輸出語意與 safety boundary | **正式沿用；本檔不重複定義語意** |
| `infra/llm.py` | 已把 raw HTTP I/O 與 service 層分離；已有 Gemini / Anthropic / OpenAI 三 provider 與 timeout / retry / 429 處理；支援 JSON request mode（部分 provider） | **可沿用「I/O 與 service 分層」觀念；runtime 介面需後續替換／包裝** |
| `services/ai_prompts.py` | prompt 已集中於 service 檔，而非全部散落 UI | **可沿用「集中管理」方向；prompt 內容與版本治理需重整** |
| `services/ai_service.py` | service 層會先整理部分資料再送 LLM；已有 prompt 壓縮／持股聚合的歷史工作 | **可沿用「Python 先壓縮再送 LLM」方向；舊 AI 行為不可直接當 OneBrain** |
| `tests/test_llm.py` | 有 provider fallback / transport 行為測試 | **可作未來 Provider abstraction 測試參考** |
| `docs/v2/71_presentation_contract_migration.md` | 已盤點舊線 AI，並將部分舊 prompt / page-level AI 分類為 replace；BL-0528 已登記舊線 AI 牴觸 | **沿用既有盤點，不另開第二份衝突清單** |

### 3.2 與 OneBrain 方向有衝突或不足

| 項目 | 現況 | 衝突／缺口 |
|---|---|---|
| Provider priority | `infra/llm.py` 預設 chain 為 `gemini → anthropic → openai` | 未來 OneBrain 方向為 **Claude Primary**；但本輪不改 runtime chain |
| Provider abstraction | 目前是函式＋字串回傳，provider 名稱／模型常數直接存在 `infra/llm.py` | 尚未形成穩定 Provider interface / typed request / typed response |
| Model config | 模型名稱直接存在 infra 常數 | 未來應由 configuration / policy 管理，不得進 domain logic |
| AI output | 主要仍是自由文字；舊 service 直接回傳 LLM 字串 | 尚未建立正式 schema-based OneBrain output contract |
| Trace | 本輪盤點未找到正式 `analysis_id` / source references / prompt_version / policy_version / data_hash / usage / cost / fallback trace 契約 | 缺正式 trace / audit contract |
| Cache | 本輪盤點未找到 OneBrain `data_hash` / analysis fingerprint 驅動的 AI cache 契約 | UI reload 不能等價於新 AI 分析，需新增 fingerprint/cache |
| Budget | 現有 provider transport 有 retry / timeout / quota error，但未見正式 monthly soft/hard cap、per-analysis cap、per-feature budget 契約 | 缺 budget control |
| Prompt governance | prompt 有集中檔，但未形成 version + purpose + required inputs + output schema + missing behavior + policy version 的正式契約 | 缺版本化治理 |
| Old AI semantics | `analyze_portfolio_mk_advisor` / `build_mk_advisor_prompt` 舊線含方向性配置／減碼語意；`docs/v2/71` 已判為 replace | 不得直接升格為 OneBrain；留待 BL-0528／後續 controlled migration |
| Page-local AI | 既有歷史線存在各頁／各功能獨立 AI 的痕跡 | 與「One AI Brain, Many Data Views」不一致；不得新增新的 page-local brain |

> 本節是 2026-10-31 對 main `9e508046` 的盤點，不宣稱對所有歷史檔案窮舉；若後續發現新路徑，先追加 inventory，再決定是否納入 OneBrain migration。

---

## 4. Provider 架構

未來正式架構方向：

```text
OneBrain
  ├─ Provider Router
  │   ├─ ClaudeProvider      ← Primary（目前策略）
  │   ├─ OpenAIProvider      ← approved fallback / future
  │   ├─ GeminiProvider      ← approved fallback / future
  │   └─ OtherProvider       ← future
  ├─ Prompt / Policy Layer
  ├─ Model Routing
  ├─ Analysis Cache
  ├─ Trace / Audit
  ├─ Budget Control
  └─ Graceful Degradation
```

### 4.1 Provider-neutral interface（未來契約方向）

Provider interface 至少需要抽象：

- provider name；
- model；
- request；
- response；
- timeout；
- retry；
- rate-limit error；
- provider unavailable；
- token usage（若 provider 提供）；
- estimated / actual cost（若可取得）；
- trace metadata；
- structured-output capability；
- degradation/error classification。

本輪**不安裝任何新 SDK**。既有 `requests` transport 可繼續存在，直到後續 Provider abstraction batch 有明確理由才決定是否改 SDK。

### 4.2 Claude Primary 是 policy，不是 domain rule

未來正式啟用時：

1. Claude API 可用且 policy 允許 → Claude；
2. Claude timeout / rate limit / unavailable / budget cap / 明確禁止 → 才依**已核准** fallback policy；
3. 當 provider 全部不可用 → 客觀資料頁仍可工作，AI 狀態明確顯示「AI 分析暫不可用／無法判定」。

禁止：

- 把 Claude 寫死在 UI、domain logic、資料模組；
- 把短期贈送額度、訂閱價格或促銷條件寫進產品架構；
- provider fail 時默默切到更昂貴模型；
- provider fail 時產生假的 HOLD / SAFE / neutral。

---

## 5. Deterministic-first：能算的不用 LLM

正式原則：

> **能確定性計算的，不使用 LLM。**

通常應由 Python / domain rules 處理：

- EPS、成長率、報酬率；
- 技術指標；
- 排名、分數、門檻；
- Risk Cap；
- schema / data completeness validation；
- 日期與 freshness；
- deterministic classification；
- 可明確公式化的財務模型；
- candidate admission rule；
- 已定義 action matrix / hard gate。

OneBrain 適合：

- 多來源訊號整合；
- 基本面變化解讀；
- 新聞／事件對持股的影響解釋（前提：事件資料已由資料層取得）；
- 產業趨勢推理；
- Regime / 基本面 / 籌碼 / 事件間關係說明；
- 矛盾訊號解析；
- 情境分析；
- 人類可讀的決策理由；
- 已存在 deterministic rule 結果的整合與解釋。

---

## 6. Analysis fingerprint / Cache

### 6.1 目標

禁止把 UI reload、session refresh 或無語意差異視為新分析需求。

概念流程：

```text
Normalized OneBrain Input
  ↓
Analysis Fingerprint / data_hash
  ↓
Compare latest compatible analysis
  ├─ same → cache hit → 不呼叫 provider
  └─ changed → cache miss → 才允許新分析
```

### 6.2 Fingerprint 至少納入

- 主要 canonical / normalized input；
- source data version / timestamp；
- Decision Digest schema version；
- prompt version；
- policy version；
- analysis type；
- 必要時 model configuration；
- 任何會實質改變語意輸出的 deterministic rule version。

### 6.3 Fingerprint 不應被下列因素污染

- UI widget 展開／收合；
- session id；
- 純顯示順序；
- 非語意欄位；
- 頁面 reload timestamp；
- cosmetic copy change（除非 prompt 本身版本有變）。

Fingerprint canonicalization 規則、TTL、持久化位置、cache invalidation 仍屬未來 implementation design，不在本輪拍死。

---

## 7. Trace / Audit Contract

每一次正式 OneBrain analysis 未來至少要能追溯：

- `analysis_id`；
- provider；
- model；
- analysis_type；
- prompt_version；
- policy_version；
- source data references；
- data_hash / fingerprint；
- source data timestamp；
- AI request timestamp；
- token usage（若 provider 提供）；
- estimated / actual cost（若可取得）；
- cache hit / miss；
- fallback 是否發生；
- error / degradation reason；
- output schema version。

### 7.1 Trace 禁止保存

- API key；
- secret；
- Authorization header；
- provider credential；
- 可反推出 credential 的敏感值；
- 不必要的完整 raw payload。

不得只保存一段沒有來源脈絡的 AI 文字。

---

## 8. Cost / Budget Governance

### 8.1 成本原則

- 不因頁面刷新重跑；
- 不因背景沒有實質變化重跑；
- 不把大量 raw data 無篩選塞給 LLM；
- Python 先過濾、聚合、標準化；
- 相同 fingerprint 優先 cache；
- 根據任務複雜度走 model routing；
- 簡單分類不固定使用最高成本模型。

### 8.2 未來 Budget Control 至少保留

- provider monthly soft cap；
- provider monthly hard cap；
- per-analysis max token / cost；
- per-feature budget；
- usage telemetry。

達 hard cap 時：

```text
Primary budget exhausted
  ↓
approved fallback policy ?
  ├─ yes → approved fallback
  └─ no  → AI unavailable / budget exhausted
            ↓
            客觀資料與 deterministic result 照常顯示
```

禁止偷偷改用更昂貴模型。

---

## 9. Prompt / Policy Governance

Prompt 不得散落在 Streamlit page / UI component。

未來可依 repo 實況形成概念上的：

```text
onebrain/
  providers/
  prompts/
  policies/
  routing/
  schemas/
  cache/
  trace/
```

這只是責任邊界示意，**不是本輪指定實體目錄**；後續 implementation 必須先看現有 `infra/`、`services/` 分層，避免為了命名搬家。

每個正式 prompt / policy 至少需要：

- version；
- analysis purpose；
- required inputs；
- output schema；
- missing-data behavior；
- safety / domain constraints；
- compatible Decision Digest schema version。

Prompt change 是否需要 cache invalidation 由 fingerprint contract 決定。

---

## 10. Structured Output

正式 OneBrain output 優先採 schema-based output，不以自由文字作唯一契約。

概念 schema：

```json
{
  "status": "...",
  "confidence": "...",
  "evidence": [],
  "risks": [],
  "contradictions": [],
  "reasoning_summary": "...",
  "action_context": "...",
  "missing_data": []
}
```

這不是新的 domain vocabulary。實際欄位值必須：

- 服從 `docs/v2/67` 既有行動語意；
- 服從 44 / Risk Cap / deterministic rules；
- 不自行創造投資狀態、UI 詞彙、confidence 等級；
- 如需新增 domain vocabulary → **Decision Gate**。

`confidence` 若未有正式定義，不能因為 schema 示意而上 production。

---

## 11. Domain Safety Boundary

固定關係：

```text
Objective Data
  ↓
Deterministic Rules / Hard Gates / Risk Cap
  ↓
Decision Digest
  ↓
OneBrain reasoning / explanation
  ↓
仍受 Risk Cap / safety rules 約束的輸出
```

OneBrain 不得：

- 繞過 Risk Cap；
- 覆蓋 hard gate；
- 將 missing 降格成 safe；
- 自行放寬 candidate admission；
- 自行創造 core/satellite 規則；
- 自行修改 regime rule；
- 在 deterministic trigger 未定義時自行決定減碼。

---

## 12. Graceful Degradation

AI provider 全部不可用時：

- Data View 繼續可用；
- Domain Result 繼續可用；
- Rule Result / Risk Cap 已有結果照常顯示；
- AI 區顯示「AI 分析暫不可用／無法判定」；
- 不產生假的 AI action；
- 不將 provider error 寫回 canonical data。

Graceful degradation 是 OneBrain 的必要功能，不是例外路徑。

---

## 13. Secrets

API key：

- 不進 Git；
- 不寫文件真值；
- 不印 log；
- 不放 trace；
- 不放 AI output。

沿用現有 environment / secrets 慣例；本輪不要求客戶提供真實 Claude key，也不修改 production secrets。

---

## 14. 跨專案相容方向

長期概念可相容：

```text
             OneBrain concept
                  │
        ┌─────────┼─────────┐
        ↓         ↓         ↓
     my-stock   my-Fund   mynews
        │         │         │
        └─────────┼─────────┘
                  ↓
            Provider Router
                  ↓
        Claude → approved fallback
```

但本輪只處理 `my-Fund-dashboard`：

- 不建立第四個共用 repo；
- 不建立 shared runtime service；
- 不要求三 repo 共用 package；
- 只確保命名、provider-neutral boundary、trace/cache/budget 思想可相容。

是否抽 shared service / package，等至少兩個 repo 有穩定重複實作與實際維運需求後，再開 Decision Gate；避免 premature abstraction。

---

## 15. Future implementation sequence（不是新的專案 Phase 編號）

以下只是 OneBrain 子工作順序，不改本專案既有 Phase / Batch 制度：

### OB-A｜Architecture / Governance

本輪。只落架構、邊界、決策、backlog；不接 runtime。

### OB-B｜Provider abstraction

- typed Provider interface；
- fake provider；
- provider-neutral request / response / error；
- configuration policy；
- 不接正式 Claude。

### OB-C｜Claude Provider Shadow

- Claude Primary 只跑 shadow analysis；
- 不接正式決策輸出；
- trace / usage / cost / cache；
- graceful degradation；
- 不改 Risk Cap。

### OB-D｜Controlled feature integration

選一個低風險、非方向性功能，先接 OneBrain；正式功能需另行裁示。

### OB-E｜Evaluation

至少評估 correctness、consistency、cost、latency、fallback、cache hit、missing-data behavior、schema validation。

### OB-F｜Production enablement

必須另行客戶裁示；沒有裁示不得 production enable。

---

## 16. Backlog decomposition

> 下列為 OneBrain 子工作。正式 BL-ID 應由 `docs/BACKLOG.md` 在不與並行 PR 衝突時統一編號；本輪先固定工作內容，不在並行 Draft PR #1111 期間搶號或覆寫 master backlog。

| Key | 類別 | 工作 | 前置／Gate | 本輪狀態 |
|---|---|---|---|---|
| OB-01 | architecture debt | Provider abstraction：typed interface + fake provider | 本檔 | deferred |
| OB-02 | architecture debt | OneBrain normalized input / Decision Digest adapter contract | `docs/v2/67`、BL-0527 | deferred |
| OB-03 | tech debt | analysis fingerprint / cache contract + tests | OB-02 | deferred |
| OB-04 | governance | trace / audit schema（analysis_id、source refs、usage、cost、fallback） | OB-01/02 | deferred |
| OB-05 | governance | budget policy（soft/hard cap、per-analysis cap、per-feature budget） | OB-01 | deferred |
| OB-06 | architecture debt | prompt / policy versioning + output schema registry | OB-02 | deferred |
| OB-07 | future validation | Claude Primary shadow provider；不接正式決策 | OB-01~06 + 客戶動工授權 | deferred |
| OB-08 | future validation | 一個低風險 feature controlled integration + evaluation | OB-07 + Decision Gate | deferred |
| OB-09 | tech debt | 舊線 AI migration / retirement 與 BL-0528 整合 | BL-0528；不得直接 reuse 舊 direction prompt | deferred |
| OB-10 | research | 是否需要 shared package/service（跨 repo） | 至少兩 repo 有穩定重複實作後 | deferred |

---

## 17. 本輪明確禁止

OB-A 不得：

- 大規模 runtime implementation；
- 改 UI；
- 改投資公式；
- 改 Risk Cap；
- 改既有決策結果；
- 新增外部資料來源；
- 新增付費服務；
- 安裝不必要 SDK；
- 建跨 repo shared service；
- 寫入真實 API key；
- 改 production secrets；
- 自動建立 fallback 付費帳號；
- 因 OneBrain 重構整個專案；
- 改 `infra/llm.py` 現行 provider chain；
- 把 Claude Primary 直接切到 production。

任何上述需求 → backlog / Decision Gate。

---

## 18. Handoff

### 18.1 本輪完成條件

- 本檔合併；
- 客戶裁示證據檔合併；
- canonical `docs/DECISIONS.md` / `docs/BACKLOG.md` / `docs/HANDOFF.md` 在並行 #1111 收斂後補索引，避免兩個並行文件 PR 同時改同一批高衝突檔；
- STATE 依 `PROJECT_RULES.md` 現行治理為歷史檔，不恢復成現行熱交接來源。

### 18.2 唯一 OneBrain handoff point

> **等本架構文件合併並完成 canonical index sync 後，下一個 OneBrain 工作只能是 OB-B Provider abstraction 的設計／fake provider batch；不得直接接正式 Claude API。**

如果當時仍有 BL-0528、Risk Cap、Decision Digest schema 等上位 blocker，先依既有 Gate 處理，不得繞過。

---

## 19. 一句話總結

> **資料提供證據；確定性規則提供邊界；OneBrain 只在既有證據與邊界內進行推理、整合與解釋。AI 不得取代資料事實，也不得凌駕安全規則。**
