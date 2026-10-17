# 客戶 2026-10-17 UI/UX 與 Personal Investment Decision System 長期方向登記指示（逐字存檔）

- **來源**：客戶 2026-10-17 在對話中的指示，經總管於派工單內轉存給文件實作組（派工單明載「the customer's own words — archive verbatim」）；本檔把全文落盤到 repo，作為 `docs/DECISIONS.md` `DEC-2026-10-17-01` 的 provenance，與 `docs/BACKLOG.md` §4〈2026-10-17 客戶確認之 UI/UX 與 Personal Investment Decision System 長期方向〉的出處。
- **存檔日期**：2026-10-17。**存檔時的 base**：main `57f03c9`（全長 `57f03c9188f35cf0aaee147625e159aaa002b6ad`）。
- **名稱**：一律稱「客戶 2026-10-17 UI/UX／PIDS 長期方向登記指示」，簡稱「2026-10-17 方向登記指示」。PIDS＝Personal Investment Decision System。它不是 2026-10-16 的任何一份裁示，不得混用。
- **逐字原則與轉存時的格式處理（據實揭露）**：圍欄內是總管轉存的客戶字句，一字不改、不重排。文件實作組只做了三件格式處理，都不動字句：(1) 派工單以「」把客戶的兩段敘述句包起來（第一段，以及最後兩句各自一組），本檔拿掉這幾組**最外層**引號，保留句內原有的「」；(2) 第 4 段（「哪些屬 Phase 3；……」）在派工單中前面帶一個英文引導詞，該引導詞看起來是總管轉存時加的標題、不是客戶字句，本檔不收；(3) 各段之間以空行分隔（派工單中各段本來就分行）。文件實作組未見客戶對話本身，無法判定 (2) 的引導詞是否其實是客戶原話。
- **禁詞**：圍欄內以交接本第 7 節〈客戶 2026-10-05 接手訊息：禁詞〉詞表八個詞碼位組字掃描，2026-10-17 實跑 0 命中，無須跳脫碼。
- **兩個 sha256**（2026-10-17 實跑；驗證指令見同目錄 `README.md`）：
  - 圍欄內文（＝本檔圍欄內實際位元組，亦即總管轉存字句經上列格式處理後的全文）：`33eca6c750bbd5959acebaaa994c32ba62633fe8f50f6d0800450e789488d01b`
  - 整檔：見同目錄 `README.md` 存檔清單（整檔雜湊涵蓋本檔頭，寫進來就會改變它自己）。
- **效力**：本檔是指示原文的存檔，不是新規則。指示內容是「登記」：**登記不構成動工授權**（`CLAUDE.md` §-1）；指示本身亦寫明「不要在本舊對話開始實作」「不得因為登記 backlog 就視為已核准立即實作」。各方向的範圍、依賴與完成條件以 `docs/BACKLOG.md` 該小節為準，決策登記以 `docs/DECISIONS.md` `DEC-2026-10-17-01` 為準。

---

```text
將客戶已確認的新 UI/UX 與「Personal Investment Decision System」長期方向，正式登記進 docs/BACKLOG.md，避免只存在對話中而遺失。先檢查 BACKLOG 現有項目，禁止重複建立已有工作。若已有相同／高度重疊項目，更新或補充既有項目，而不是新增重複 backlog。至少確認下列方向都有可追蹤的 backlog；但不要在本舊對話開始實作：

【Phase 3 / 近期】B 線五頁 Answer-first UX；390px Mobile First；UI de-engineering；Data Health 集中至 SET；錯誤去重與 actionable empty/error states；investment status 與 data status 分離；change-first / exception-first；Global Context / context persistence；controls / CTA 簡化；OAuth → valid Sheet → worksheet UX；READ / WRITE boundary；Evidence Path / provenance 可追溯架構；partial failure isolation；freshness-aware refresh；draft vs saved；simulation vs real change；mobile / desktop information density

【Roadmap / 後續，不得在 Phase 3 一次實作】Today Overview / 今日總覽；Signal Lifecycle：NEW / ONGOING / WORSENING / RESOLVED；Why Now / 首次越過門檻；Thesis Card / Thesis Monitoring；Supporting vs Contrary Evidence；Severity vs Evidence Quality；Decision Journal；Decision Quality ≠ Investment Outcome；Expected vs Actual / Thesis Review；Portfolio Look-through Exposure；Fund overlap / False Diversification；What-if Engine；Replacement Flow：HLD → ALO → EXP → ALO；Performance Attribution（fund / FX / dividend / allocation）；Regime × Fund；AI disagreement with deterministic rules；Counterfactual Review；Portfolio Story；Alert usefulness / threshold review；「無法判定」原因分類；未來 AI page interpretation，但 AI 與 Data Layer 必須分離；Decision-time evidence snapshot / rule version preservation

哪些屬 Phase 3；哪些屬 Later / Roadmap；dependency；acceptance / completion condition（適用時）；不得因為登記 backlog 就視為已核准立即實作。

若上述方向屬於已確認的產品／架構決策，依現有文件治理判斷是否也需要在 docs/DECISIONS.md 建立或更新索引。不要把所有 backlog 複製進 DECISIONS；只記錄真正的決策。

HANDOFF 只保留新對話接手所需的短版現況。不要把完整 Roadmap 全部複製進 HANDOFF。HANDOFF 應指向 BACKLOG / DECISIONS 作為後續工作的正式來源。
```
