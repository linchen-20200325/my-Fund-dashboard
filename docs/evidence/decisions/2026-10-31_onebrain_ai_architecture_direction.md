# 客戶 2026-10-31 OneBrain AI 未來導入方向（正式裁示紀錄）

- **來源**：客戶 2026-10-31 在本對話中的正式指示。
- **性質**：Architecture / Governance；不是 runtime 動工授權。
- **落地文件**：`docs/v2/75_onebrain_ai_architecture.md`。
- **既有 SSOT 關係**：AI 行動語意、Decision Digest、One AI Brain 既有正式條文仍以 `docs/v2/67_ai_action_vocabulary.md` 為準；75 只補 Provider、routing、cache、trace、budget、prompt governance、structured output、secrets 與 rollout 邊界。
- **量測基準**：main `9e508046277a9e41f07bcba67d91cc8f97c7517a`；同時有 Draft PR #1111，故本輪不與其競寫 `docs/DECISIONS.md`、`docs/BACKLOG.md`、`docs/HANDOFF.md`。

## 正式核心原則

> **Data is evidence. Rules are constraints. OneBrain is reasoning.**
>
> 資料提供證據。確定性規則提供邊界。OneBrain 負責在既有證據與邊界內進行推理、整合與解釋。AI 不得取代資料事實，也不得凌駕安全規則。

## 正式方向摘要

1. OneBrain 定位為 **AI Reasoning & Orchestration Layer**，不是資料來源、ETL、公式引擎、Risk Cap、UI、DB 或自行補資料的 Agent。
2. 固定責任鏈：資料取得／驗證／標準化 → canonical data → deterministic calculations/rules/Risk Cap → Decision Digest → OneBrain → UI/決策輸出。
3. OneBrain 只能讀已取得且可追溯資料；Missing / unavailable / not evaluated 不得被補成 0 / neutral / safe；資料不足就「資料不足／無法判定」。
4. Provider 必須解耦。**Claude API 是目前未來 Primary Provider 的 policy 方向**，不是 domain rule；OpenAI / Gemini / 其他 provider 只作已核准 fallback / future。
5. 這一輪不改目前 `infra/llm.py` 的 runtime chain，不接正式 Claude API，也不安裝不必要 SDK。
6. **能確定性計算的，不使用 LLM。** 公式、門檻、Risk Cap、schema、freshness、deterministic classification 等留在 Python / rules。
7. 未來 OneBrain 必須有 analysis fingerprint / data_hash 驅動 cache，避免 UI reload 或無語意變化重跑 API。
8. 正式 AI analysis 必須可追溯 analysis_id、provider/model、analysis type、prompt/policy version、source refs、fingerprint、timestamps、usage/cost、cache、fallback、degradation、output schema version。
9. 成本治理必須保留 monthly soft/hard cap、per-analysis cap、per-feature budget 與 usage telemetry；hard cap 不得偷偷改用更昂貴模型。
10. Prompt / policy 集中治理且版本化；不得散落 UI。實體目錄需依既有 repo 分層決定，不能為了示意強行搬家。
11. 正式 output 優先 schema-based；不得自行新增投資狀態／UI 詞彙／confidence 等級；新增 domain vocabulary 必須 Decision Gate。
12. OneBrain 不得繞過 Risk Cap、hard gate、candidate admission、core/satellite、regime 或其他 deterministic safety logic。
13. Provider 全失敗時，客觀資料與 deterministic 結果仍正常；AI 顯示「AI 分析暫不可用／無法判定」，不得製造假的 HOLD / SAFE / neutral。
14. API key 不進 Git / log / trace / AI output；本輪不要求真實 key、不改 production secrets。
15. 跨 `my-stock` / `my-Fund` / `mynews` 只先保持概念與邊界相容；不建立第四個共用 repo、shared runtime 或 package。shared abstraction 留待真正重複出現後再裁示。
16. 未來順序：Architecture/Governance → Provider abstraction + fake provider → Claude shadow → controlled low-risk integration → evaluation → production enablement；production enablement 必須另行裁示。

## 本輪禁止

- 不做大規模 runtime implementation。
- 不改 UI、公式、Risk Cap、既有決策結果、資料層邏輯。
- 不新增外部資料來源、付費服務、SDK、shared service。
- 不 commit secrets。
- 不將 Claude Primary 直接切到 production。

## Canonical index sync 說明

`PROJECT_RULES.md` 現行射程明定只管「專案 AI 怎麼工作」，產品架構不應塞入其本文；因此 OneBrain 產品架構正式住在 v2 architecture / AI SSOT 鏈。

`docs/DECISIONS.md`、`docs/BACKLOG.md`、`docs/HANDOFF.md` 是 canonical index，但 2026-10-31 此刻 Draft PR #1111 正在修改同一批高衝突治理檔。為避免並行文件 PR 互相覆寫，本輪先把客戶裁示與完整架構寫成新增檔；#1111 收斂後只需做純索引 sync，不得重新開 OneBrain 方向 Gate。

root `STATE.md` 依現行 `PROJECT_RULES.md` 為歷史檔，不恢復成熱交接來源。
