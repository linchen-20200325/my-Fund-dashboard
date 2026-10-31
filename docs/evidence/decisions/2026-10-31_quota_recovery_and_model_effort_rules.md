# 2026-10-31｜額度中斷保全＋Model/Effort 永久作業規則

## 背景
客戶告知目前使用額度只剩約 8%，要求先存檔，並把新的規則寫進 GitHub，避免額度耗盡後進度與規則失去可追溯性。

本檔只做治理／接手證據，不是 production runtime 變更授權。

## 客戶要求
1. 在額度中斷前，把目前進度寫進 GitHub。
2. 把近期新增的協作規則、模型／理解力路由、P3/V7 最新裁示、OneBrain 現況留下 durable record。
3. 新 session 不得依賴舊聊天記憶，必須能由 GitHub 恢復。

## 正式作業規則

### A. Minimum Sufficient Effort
基金專案目前預設：
- Model：Claude Sonnet 5.5
- Effort：Medium

只有真正涉及下列高風險語意／架構 Gate 時，才暫升：
- 新 formula / Rule semantics
- Risk Cap
- Decision Digest semantics
- 新資料來源或 source precedence
- identity / NAV / valuation / FX cutoff
- OAuth / credentials / security architecture
- OneBrain architecture / Provider policy 的新 Decision Gate

高風險 Gate 使用：
- Model：Claude Opus 5.5
- Effort：High

規則：
1. 升級前先走 Model/Effort Change Gate。
2. Gate 收斂後立即降回 Sonnet 5.5 + Medium。
3. UI、tests、Visual Fidelity、docs、metadata、機械式整合不得無理由常駐 Opus。

### B. Silent Autonomous Cruise / No Progress Narration
不需要客戶行動時，不發訊息。

只在以下情況回報：
1. 真 Decision Gate
2. 真 blocker
3. Model/Effort Change Gate
4. 整批完成

禁止把「正在做、正在等 CI、agent/audit 已派、worktree/scratchpad、內部步驟」當作客戶訊息。

### C. Durable Memory / Recovery
Conversation 不是 SSOT。重大裁示、規則、架構、Backlog、handoff 必須寫入 repo。

每次新 session：
1. 先做 GitHub Verification Gate。
2. GitHub 與 HANDOFF/舊聊天不一致時，以 GitHub 實況為準。
3. 本次額度中斷接手點見 `docs/v2/77_emergency_resume_checkpoint_2026-10-31.md`。

## P3 / V7 最新裁示保全
- V7 Layout 採 A，A 是 presentation de-duplication，不刪 HLD-0/ALO-0 domain blocks。
- 不採 B，不採 C；不得放寬 V7 / Mobile Visual Budget。
- H6 維持「只評估一部分」級，但既有 ⛔ 逐檔取數失敗原因要外露。
- F-5 字樣核准：`持股：`、`配置：`、`持股與配置：`。
- A 線框核准：兩個燈標題在合併頁消失；Sheets CTA 留在持股明細第一個位置。
- ALO 說明 copy 從「本燈只讀 目標對照卡 算出的差距，不指出方向。」校正為「此配置判讀只讀 目標對照卡 算出的差距，不指出方向。」；這只屬 presentation copy，不改 domain semantics。
- Mobile degraded-data 情境：`重要頁級狀態 / Missing / Error reason > 強迫 Primary 完整露出`。不得為塞圖隱藏 Missing/error 或放寬 V7。

## OneBrain 保全
- OneBrain Phase A 在 Draft PR #1112。
- 定位：AI Reasoning & Orchestration Layer。
- 核心：`Data is evidence. Rules are constraints. OneBrain is reasoning.`
- provider-neutral；Claude future Primary，但不寫死於 UI/domain/data layer。
- 尚未接正式 Claude API、尚未要求真實 key、尚未改 production provider chain。
- #1111 已合併後，#1112 下一步只是 canonical DECISIONS/BACKLOG/HANDOFF index sync；不需要重新開 OneBrain 方向 Gate。

## 非授權事項
本檔不授權：
- 新資料來源
- 新 formula / Risk Cap
- OneBrain runtime
- Claude API production 接線
- OAuth 變更
- Visual Budget 放寬
- 任何 secrets 變更
