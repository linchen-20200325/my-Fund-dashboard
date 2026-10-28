# 客戶 2026-10-28 永久治理規則：Anti-Bloat / Minimum Governance Overhead（逐字）

- **來源**：客戶 2026-10-28 對話中的永久治理規則指示，經總管轉存為逐字文字檔；執行組照抄，未見客戶對話本身。
- **遮蔽**：無。本文沒有作者或老師姓名，也沒有 secret。
- **決策登記**：`docs/DECISIONS.md` `DEC-2026-10-28-04`（客戶裁示，永久）。落地：`PROJECT_RULES.md` 13.4 與第 0.5 節索引一列、`docs/HANDOFF.md` 一行指標。
- **性質**：本檔只存原文，不含執行組讀法。圍欄為轉存的客戶原文，字句未改；唯一格式處理：無（行尾空白：0 行）。
- **存檔日期**：2026-10-28
- **圍欄內文 sha256**：`4f42cb01aa97d0d11fbfb728748d284c34c30811f7528cb355b99ccfeaab2778`
- **依據規則**：`PROJECT_RULES.md` 12.2 GitHub Discussion Persistence Gate。

```text
新增永久治理規則：

Anti-Bloat / Minimum Governance Overhead

目的：避免治理、審計、文件、BACKLOG、Evidence 與 PR 數量持續膨脹，讓治理成本超過實作成本。

此規則與以下既有規則並行：

- Silent Autonomous Cruise
- Context Efficiency
- Minimum Sufficient Work
- Minimum Sufficient Test Scope
- GitHub-first Verification Gate

不得降低必要的正確性、安全性或 Stop Gate。

1. Audit 數量採 Minimum Sufficient Audit

預設：

- 文件、小修、純 UI、metadata、低風險 deterministic change：
  最多 1 組獨立 audit
- 一般跨模組但不涉及核心投資語意：
  1 組 audit 即可
- 只有下列高風險項目才考慮第 2 組獨立 audit：
  - Risk Cap
  - 投資核心判定
  - source precedence
  - canonical data contract
  - canonical identity migration
  - valuation methodology
  - FX cutoff
  - 公式／門檻
  - credential/security
  - 不可逆資料遷移
  - frozen SSOT amendment

禁止因「多驗比較安心」而固定派 3～5 組 audit。

audit 發現問題後：
原實作組修正 → 原 audit 或 1 組獨立複驗即可。
除非出現新的高風險範圍，不得無限追加稽核組。

---

2. PR 數量最小化

能安全同批完成的：

- implementation
- tests
- BACKLOG
- HANDOFF
- DECISION reference

原則上放同一 PR。

不要形成：

"功能 PR → HANDOFF PR → BACKLOG PR → evidence PR"

除非：

- 功能 PR 已經合併且當時客觀上無法同步
- 文件修改需要獨立 Decision Gate
- frozen / protected file 必須獨立流程

否則文件同步應與原 batch 一次完成。

---

3. BACKLOG Anti-Fragmentation

不要把每個：

- audit should-fix
- 小註解
- wording
- minor cleanup
- evidence 補充
- 可順手修的小缺口

都拆成新 BL。

只有符合至少一項才新增獨立 BACKLOG：

- 可獨立排程
- 有不同 acceptance criteria
- 有獨立 Decision Gate
- 有不同風險等級
- 無法在目前 batch 安全完成
- 需要新資料源／credential／人工操作
- 明確屬另一個產品需求

其餘放在目前 BL 的 subtask / follow-up。

---

4. Evidence 採 Minimum Sufficient Evidence

只保留足以：

- 重現
- 稽核
- 驗收
- 追溯 Decision

的最小證據。

禁止為同一事實重複建立多份內容高度重疊的：

- audit report
- checkpoint
- evidence note
- summary
- handoff copy

已有正式 SSOT 時：
引用，不複製全文。

逐字存證只限：

- 客戶正式裁示
- 法規／授權／高風險治理需要

一般執行紀錄不需要逐字永久保存。

---

5. Batch 大小

預設每 batch：

最多 3 個實際工作項目。

可以是：

- 1 個功能 + tests + docs
- 2～3 個高度相關的小項

不要把 8～10 個互不相干的 backlog 塞成一批。

反過來也不要把一件很小的工作拆成 5 個 PR。

原則：
最小但完整的可驗收批次。

---

6. Decision Gate 不得氾濫

只有真正會改變：

- 產品語意
- 投資邏輯
- 資料契約
- source precedence
- 公式／門檻
- UX 核心行為
- 安全／不可逆操作

才升 Decision Gate。

已確認的 bug 且只有一個明確安全修法：
自行修，不得包裝成客戶裁示。

純實作選擇：
由 AI 總管依既有規格自行決定。

---

7. 文件不要重複 SSOT

PROJECT_RULES：
只放永久治理。

DECISIONS：
只放正式裁示與 supersede 關係。

BACKLOG：
只放尚未完成工作。

HANDOFF：
只放目前狀態與下一接手點。

Spec：
只放該領域正式設計。

Evidence：
只放驗證證據。

禁止同一內容在五份文件各複製一份完整版本。

---

8. 完成後停止

一個 batch 若已：

- acceptance criteria 通過
- targeted tests 通過
- 必要 audit 通過
- CI 通過
- GitHub SSOT 同步

就結束。

不要因為「還可以再整理」而自行擴大：

- cleanup
- refactor
- naming
- extra tests
- extra docs
- neighboring backlog

非必要改善進既有 backlog 或忽略，不延長當前 batch。

---

9. 與 Silent Cruise 的關係

Anti-Bloat 不只是少做文件，也包含少回報。

不得主動回報：

- audit 派出了幾組
- reviewer 在跑
- CI 還在等
- 文件正在同步
- 又新增了哪些小 BL

只有 Silent Cruise 允許的四種情況才回報。

---

10. 每次開工前自問

只需要內部判斷，不要回報客戶：

1. 這項真的需要獨立 BL 嗎？
2. 真的需要另一個 PR 嗎？
3. 真的需要第二組 audit 嗎？
4. 已有 SSOT 可以引用嗎？
5. 這項能否在目前 batch 安全完成？
6. 是否正在把治理本身變成主要工作？

若答案顯示流程正在膨脹，優先縮減流程。

請將本規則寫入 "PROJECT_RULES" 的永久治理區，並在治理快速索引加入 Anti-Bloat / Minimum Governance Overhead。

HANDOFF 只保留一行指標，不複製全文。

不要另外建立新的治理 SSOT。

本次只做治理規則落盤，不要趁機重整既有 BACKLOG、歷史 evidence 或舊 PR。

Model：Sonnet 5.5
Effort：Low
```
