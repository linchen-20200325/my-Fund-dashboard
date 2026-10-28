# 客戶 2026-10-28 永久 Context Efficiency 規則（逐字）

- **來源**：客戶 2026-10-28 對話中的永久規則指示，經總管於派工單內逐字轉存；執行組照抄，未見客戶對話本身。
- **遮蔽**：無。本文沒有作者或老師姓名，也沒有 secret。
- **決策登記**：`docs/DECISIONS.md` `DEC-2026-10-28-02`（客戶裁示，永久）。落地：`PROJECT_RULES.md` 11.1、第 0.5 節索引一列、`docs/HANDOFF.md` 簡短指標。
- **性質**：本檔只存原文，不含執行組讀法。圍欄為派工單內客戶原文，字句未改；唯一格式處理：本檔圍欄內無只含空白的行，行尾空白已確認為 0 行，其餘字元、順序、段落一字未動。圍欄內文本身含以雙引號包住的環境變數與指令字面，照原樣保留。
- **存檔日期**：2026-10-28
- **圍欄內文 sha256**：`fa959c7305a269c4d75188d75fff33a2a8e57b778bc9e6849b95129aca95fe4d`
- **依據規則**：`PROJECT_RULES.md` 12.2 GitHub Discussion Persistence Gate。

```text
新增永久 Context Efficiency 規則，目的為降低 token 浪費與避免不必要的大範圍重讀。

1. 自動 Compact

Claude Code 本身支援 automatic compaction。

若執行環境允許設定，建議：

"CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=75"

讓 context 約使用到 75% 時提前自動 compact，不等到接近滿載。

不得設定：

- "DISABLE_AUTO_COMPACT=1"
- "DISABLE_COMPACT=1"

除非有明確除錯理由。

若環境不方便修改變數，則在 context 明顯變大、完成重要 batch 或進入新階段時，可主動使用：

"/compact"

但 compact 前必須先確保：

- GitHub SSOT 已同步
- HANDOFF / Resume Checkpoint 足以接手
- 未提交工作狀態清楚
- 重要客戶裁示已落盤

Compact 不得取代 GitHub persistence。

---

2. Compact 時保留重點

若手動執行 "/compact"，摘要應優先保留：

- repo / branch / main SHA
- 當前 batch
- Open PR
- 已核准 Decision
- 尚未完成 Stop Gate
- 下一個唯一 action
- Model / Effort
- Data / AI boundary
- frozen 44 相關限制
- Missing / Risk Cap 等關鍵治理
- 未提交工作

不要保留大量已完成的逐步執行紀錄。

---

3. Minimum Necessary Read Scope

從現在起禁止每次任務都大範圍重讀 repo。

採：

Search first → targeted read → expand only when needed

每次 GitHub Verification Gate

只先讀：

1. current main SHA
2. Open / Draft PR
3. 與當前 task 相關 commits / diff / CI
4. HANDOFF 的 current checkpoint / next action
5. BACKLOG 中當前 BL 編號
6. 相關 DECISION

不要預設全文讀取：

- 整份 BACKLOG
- 整份 DECISIONS
- 整份 HANDOFF 歷史
- 整份 frozen 44
- 所有 spec
- 全 repo

---

4. Frozen 44

只有當本次工作真的碰到 frozen 44 的條款時：

- 先搜尋相關 heading / keyword / clause
- 只讀必要段落與上下文
- 不得每輪重新讀 5,000+ 行全文

只有：

- integrity audit
- md5 / line guard
- 大規模 amendment
  才允許全文檢查。

---

5. BACKLOG / DECISIONS

若目前工作是 BL-XXXX：

先搜尋：
"BL-XXXX"

再讀它附近必要上下文。

若需裁示：
只讀直接相關 DEC 編號與 supersede chain。

不要因為存在數百條 BACKLOG 就全部載入 context。

---

6. Code

先：

- grep / search symbol
- 找 caller / callee
- 找 tests

再讀精確檔案與函式。

禁止為了解一個 function 而先掃完整 repo。

---

7. 已完成歷史

已 merge 且 HANDOFF 已記錄的舊 batch：

原則上只看：

- commit summary
- 必要 diff
- Decision reference

不要重建整個歷史推理。

---

8. 新對話 / Compact 後

恢復工作時：

GitHub Verification Gate
→ HANDOFF current checkpoint
→ current BACKLOG item
→ direct DECISION / spec
→ code needed for current task

不要重新做「全專案 onboarding」。

---

9. Silent Cruise

不要回報：

- 「我要 compact」
- 「context 變大」
- 「我正在讀檔」
- 「我讀了哪些文件」

除非：

- context / quota 已危及正確性
- 必須換新對話
- compact 無法安全繼續

平常全部靜默處理。

---

10. 原則

GitHub 是長期記憶；conversation context 只是工作快取。

不要用巨大 context 取代良好的 SSOT / targeted retrieval。

請把這項規則加入 PROJECT_RULES 的永久 AI 工作規範，並在 HANDOFF 僅保留簡短指標。

Model：Sonnet 5.5
Effort：Low～Medium；此項主要是治理／context efficiency。
```
