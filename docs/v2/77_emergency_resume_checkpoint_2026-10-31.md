# 77｜額度中斷保全：基金專案緊急接手快照（2026-10-31）

> **2026-10-31 更新：#1113 已合併（main `5c73f529`）**（就地更正，原文不刪；狀態更新，不是漏刪）：以下「最新 GitHub 實況」為合併前紀錄，現況以 `docs/HANDOFF.md` 為準（唯一下一接手點＝#1112 canonical index sync）。

> 目的：客戶目前可用額度只剩約 8%，本檔用來保證即使對話／模型額度中斷，新 session 仍能只靠 GitHub 恢復進度。GitHub 為 SSOT；HANDOFF/STATE/舊對話只作輔助。

## 1. 最新 GitHub 實況（寫檔前重新核對）

- main：`01f42aa260b6cc683a984420e8e425c9ac0ab29c`（#1111 已 squash merge）。
- Open PR：
  - #1113 `BL-0525-D3：P3 頁級狀態 aggregation`，Draft；branch `claude/fund-dashboard-handoff-verify-n6ny72`；本檔建立前已知 head `c957af4a3f0cea5368e704a7383f60bdad9cf896`。
  - #1112 `OneBrain AI Phase A：正式架構方向、邊界與未來導入 Backlog`，Draft；branch `docs/onebrain-architecture-20261031`。
- #1113 尚未合併；#1112 尚未合併。

## 2. #1113：P3 / V7 現況

### 已完成並落盤
- `DEC-2026-10-30-04`：P3，precedence β：`取數失敗 > 無持倉 > ◆ > ◇ > ⬜ > 持股只評估一部分 > 無偏離／帶內`。
- D-3 阻擋項 F-13 / F-2 / F-14 / F-18 / F-19 已於 #1111 收斂。
- P3 已在 #1113 實作為 page-level presentation aggregation；不回寫 domain blocks，不改 Risk Cap、Decision Digest 原始 rule result、公式、門檻或 canonical data。
- H6（逐檔取數失敗）正式維持「持股只評估一部分」級；仍外露既有 `⛔` 失敗原因，不把 partial failure 升為 whole-area failure。
- F-5 字樣核准沿用：`持股：`、`配置：`、`持股與配置：`。

### V7 / Layout A 已裁示
- `DEC-2026-10-31-01`：採 A。
- 頁級 P3 狀態容器保留在第一眼；在「💼 我的資產」合併頁上，移除 HLD-0 / ALO-0 的重複 presentation。
- 這只是 presentation de-duplication：`Domain Block Identity ≠ Presentation Instance`。
- 不採 B（不把頁級狀態移到 Primary 後面）。
- 不採 C（不得放寬 V7 / Mobile Visual Budget）。
- `docs/v2/76_assets_v7_layout_a_wireframe.md` 已完成最小文字線框；截至本檔建立時，production A 尚未實作。

### 線框最新審批（本次額度保全前的最後裁示）
1. 「體檢結論燈」「差距結論燈」在合併頁不再顯示：核准。
2. 原文 `本燈只讀 目標對照卡 算出的差距，不指出方向。` 不應原樣保留；A 實作後沒有獨立燈，改為：
   - `此配置判讀只讀 目標對照卡 算出的差距，不指出方向。`
   - 只屬 UI copy 校正；不改公式、rule result、方向性限制或 domain vocabulary。
3. `前往 Sheets` 按鈕留在持股明細第一個位置；key 不變；不塞進 P3 HTML 容器。

### Mobile / degraded-data 優先序
- 正常 `full` 情境，A 線框推估可讓 390px Primary 上緣由 883px 降到約 750px。
- 但 Missing / error / partial 的極端組合不保證全部在第一屏看到完整 Primary；這是已知限制，不擴 scope。
- 正式優先序：`重要頁級狀態 / Missing / Error reason > 強迫 Primary 完整露出`。
- 禁止為了圖表高度：隱藏 Missing / omitted rows / error reason、縮字到難讀、放寬 V7、修改 Mobile Visual Budget、或自動折疊關鍵錯誤資訊。
- 實作後仍要量測並據實記錄 V7 hard pass/fail 與 Primary 實際可見高度；未測不得寫成通過。

## 3. #1112：OneBrain Phase A 現況

- OneBrain 正式定位：`AI Reasoning & Orchestration Layer`。
- 核心原則：`Data is evidence. Rules are constraints. OneBrain is reasoning.`
- 資料 / API / DB → 取得、清理、標準化、驗證、追溯 → 客觀資料層 → deterministic rules / Risk Cap → Decision Digest → OneBrain → reasoning / explanation → UI。
- AI 不得創造缺失資料、missing→0、unavailable→neutral、not evaluated→safe、無來源製造市場事實、回寫 canonical data，或用 LLM 取代 Python / deterministic rules。
- Provider-neutral；Claude API 是未來 Primary policy，不得寫死在 UI/domain/data layer。
- future：Provider Router、prompt/policy versioning、fingerprint/cache、trace/audit、budget control、graceful degradation、structured output。
- 尚未接正式 Claude API；尚未要求真實 API key；未改 production provider chain；未安裝額外 SDK。
- #1112 目前只完成新增 architecture / evidence 文件；原本因 #1111 並行而延後 canonical DECISIONS/BACKLOG/HANDOFF index sync。#1111 已合併，因此 #1112 下一步是先 rebase/refresh main，再做純索引 sync；不要重新開 OneBrain 方向 Gate。
- 不要在 #1113 P3/V7 批順手開始 OneBrain runtime。

## 4. 永久協作規則：新 session 必讀

### GitHub Verification Gate
任何專案判斷、下一步、提示語、merge/close/branch cleanup、CI/QA/audit、架構/資料/公式/清理建議以前，都必須 fresh-check GitHub：main SHA、Open/Draft PR、相關 head/diff、CI/QA、必要時 branches。GitHub = SSOT。

### Silent Autonomous Cruise / No Progress Narration
- 不需要客戶行動時，不發訊息。
- 禁止回報：正在改檔、agent 正在跑、CI 還在等、audit 已派、worktree/scratchpad、內部下一步。
- 只在：真 Decision Gate、真 blocker、Model/Effort Change Gate、整批完成時回報。

### Model / Effort：Minimum Sufficient Effort
目前基金專案預設：`Claude Sonnet 5.5 + Medium`。

只在以下真正高風險 Gate 暫升 `Claude Opus 5.5 + High`：
- 新公式 / Rule semantics
- Risk Cap
- Decision Digest semantics
- 新資料來源 / source precedence
- identity / NAV / valuation / FX cutoff
- OAuth / credentials / security architecture
- OneBrain architecture / Provider policy 的新 Decision Gate

升級前必須先走 Model/Effort Change Gate；該 Gate 收斂後立刻降回 Sonnet 5.5 + Medium。一般 UI、測試、文件、機械式整合不得常駐 Opus。

### Data layer ≠ AI reasoning layer
- missing ≠ 0
- unavailable ≠ neutral
- not evaluated ≠ safe
- Unknown 必須保留 Unknown
- AI 只讀已取得且可追溯的資料，不得改寫資料層。

### Presentation / Mobile
- 圖表 > 數字 > 短句 > 長文字。
- Presentation Simplification must never reduce AI Decision Context。
- Visual Priority ≠ Visual Quantity。
- Mobile-first；第一眼先讓使用者知道「現在狀態 / 是否需行動 / 下一步」，但 Missing/Error 的真實原因優先於為了塞圖而隱藏資訊。
- Domain Block Identity ≠ Presentation Container / Presentation Instance。

### Durable Memory
Conversation 不是 SSOT。正式裁示、規則、架構、UI 原則、OneBrain contract、Backlog、handoff 必須寫入 repo。新 session 應先讀：
1. `PROJECT_RULES.md`
2. `docs/DECISIONS.md`
3. `docs/BACKLOG.md`
4. `docs/HANDOFF.md`
5. `docs/v2/67_ai_action_vocabulary.md`
6. `docs/v2/71_presentation_contract_migration.md`
7. `docs/v2/74_assets_d3_formula_gate.md`
8. `docs/v2/76_assets_v7_layout_a_wireframe.md`
9. 本檔 `docs/v2/77_emergency_resume_checkpoint_2026-10-31.md`
10. OneBrain branch 的 `docs/v2/75_onebrain_ai_architecture.md`（#1112 未合併前須從其 branch 讀）。

## 5. 唯一安全接手點

先處理 #1113，不開新功能：

1. 以 #1113 最新 head fresh-check GitHub。
2. 把最新線框審批正式落盤：兩燈標題消失；ALO copy 改為「此配置判讀只讀 目標對照卡 算出的差距，不指出方向。」；Sheets CTA 留原位。
3. 依已核准 Layout A 實作 presentation de-duplication；不改 domain semantics。
4. 依既定驗收重跑：P3 7×6、7×7、10 情境、H6 partial、domain semantics guard、Sheets CTA、omitted/Missing reason、desktop/390 Visual Fidelity、relevant regression、CI；補「附行不得被合成/de-dup 吞掉」守衛。
5. 獨立稽核；安全則 Auto-Ship #1113。
6. #1113 收斂後，再處理 #1112 OneBrain Phase A canonical index sync。

不得從本檔推論 #1113 / #1112 已合併；每次仍須重新查 GitHub。
