# 品質補強 Batch 3｜專業 Agent 定義、Token／返工 A/B 量測、零記憶接手驗收（2026-11-13）

> **統一聲明**：本檔是設計與證據落盤，**非客戶裁示、非授權施工**；基準 main `c8847f00ef13abe52deb6240bf152757693023dc`（#1230 merge）；來源為 GitHub Issue #1228 Batch 3，授權依客戶 2026-11-13 Batch 3 裁示（登記於 `DEC-2026-11-13-04`，要點轉述，非逐字；**Issue 是派工入口，不是授權狀態 SSOT**）。本檔為**單組作者草稿，尚待非作者 QA**；所有全稱句（「0 命中」「只有 N 處」「沒有任何」）皆為單組字面查詢，未經第二組驗證。路徑引用一律「檔案::符號」，不寫行號。
>
> **本檔對應 PR-1**：三個 Agent 定義檔、結構守衛、最小文件同步、evidence 骨架。**PR-2（A/B 量測、零記憶接手驗收、正式權限正負向測試）尚未執行**，本檔對應章節一律標 **NOT RUN**，不預填任何結果、不預設任何節省比例。
>
> 「推薦」「讀法」一律是專案 AI 讀法，可被客戶推翻。BL-0545 仍是唯一全域 NEXT（BLOCKED），本批不取代它。

## 0. 一頁結論（先讀）

1. PR-1 建立三個**唯讀** Agent 定義（`.claude/agents/fund-nav-data.md`、`fund-governance-auditor.md`、`fund-independent-qa.md`），frontmatter 僅 `name`／`description`／`tools: Read, Grep, Glob`／`disallowedTools: Write, Edit, NotebookEdit, Bash, Agent`；本文固定七個二級標題；結構由 `tests/test_claude_agents_definitions.py` 守衛。
2. **工具白名單不等於資安隔離。** 敏感路徑 `Read(...)` deny 規則與唯讀 GitHub MCP 工具兩件事都屬待客戶裁示（BL-0549），本批不施工、不建立 `.claude/settings*`。
3. 三個 Agent 的獨立性僅限「不同 context、無寫入能力、不接受自己的修改」；與主 session 共享同一個派工來源，**不等於**組織上完全獨立（Batch 1 §1.4(d)-6 的 NOT VERIFIED 依然成立）。
4. **Token／返工 A/B 量測、零記憶接手驗收、正式權限正負向測試：全部 NOT RUN。** 在 PR-2 取得有效數據之前，不得宣稱效益，也不得宣稱六項品質補強全部完成。

## 1. 三個 Agent 定義

**設計依據**：角色職責、Forbidden 清單與路由表引用 `docs/evidence/quality_batch1_delta_2026_11_13.md` §1.4（角色草案(b)、Forbidden 對應出處(c)、路由表(e)），Agent 檔內**引用該節而非複製全文**（`PROJECT_RULES.md` §13.4 Anti-Bloat）。

| Agent | 職責（唯讀） | 與 Batch 1 §1.4 的對照 |
|---|---|---|
| `fund-nav-data` | NAV、來源、資料契約、Missing／Partial、freshness、lineage 查核 | 對應(b)列 1；Forbidden 另明列不得合併 `provenance.source`／`source_tier`／績效 `source` 三種語意 |
| `fund-governance-auditor` | 正式規格、憲法、DEC、BACKLOG、Decision Gate 對照與衝突偵測 | 對應(b)列 2；不得自行判定投資語意 |
| `fund-independent-qa` | 非作者稽核 PR／測試／CI／交接**證據**（只審提供的 diff、log、檔案內容與 SHA） | 對應(b)列 3；不得驗收自己編修的內容；另含獨立性限度聲明 |

**官方格式查證結論**（查證日 2026-11-13；來源 `https://code.claude.com/docs/en/sub-agents.md`、`permissions.md`、`headless.md`、`agent-sdk/cost-tracking.md`。**本組撰寫 PR-1 時未獨立重查官方文件，下列為總管派工單轉述的查證結論**）：

| 類別 | 內容 |
|---|---|
| 文件明文（轉述） | 必填欄位只有 `name` 與 `description`；省略 `tools` 會繼承全部工具（含 MCP 與寫入）；`disallowedTools` 先套用、`tools` 再解析；未知 frontmatter 欄位被靜默忽略；Read 在工作目錄內預設免確認；`.claudeignore` 無效 |
| 本組推論 | 因未知欄位被靜默忽略，不得靠不認得的欄位做限制；因省略 `tools` 會繼承寫入，必須顯式列 `tools` 並加 `disallowedTools` 作雙重限制 |

**欄位選擇理由**：只用 `name`／`description`／`tools`／`disallowedTools`。**不寫** `model`、`permissionMode`、`hooks`、`mcpServers`、`skills`、`memory`、`maxTurns`：避免與 `PROJECT_RULES.md` §5 Model／Effort Gate 衝突（Batch 1 §1.4(d)-3 已列此空缺），也避免依賴未經查證的行為。`description` 刻意不寫 use proactively，因為 PR-2 要量測自然路由，不人為加強。

## 2. 權限與隔離

### 2.1 官方文件說法

見 §1 表。重點：工具白名單不等於資安隔離；Read 的敏感路徑保護要靠 deny 規則，且 deny 規則本身屬需客戶裁示的設定變更（BL-0549）。

### 2.2 本機 spike 觀察（單組自測；經總管派工單轉述，本組未重跑）

環境：`claude -p`（CLI 2.1.323），在 scratch 目錄以**假檔**實測，未讀任何真實密鑰。

- `tools` 白名單外的工具**根本不存在**於該 subagent（不是執行期被拒）。
- 省略 `tools` 時，subagent 繼承 Write／Edit／Bash 與全部工具。
- 在 `acceptEdits` 下，`tools` 限制為 Read／Grep／Glob 的 subagent 仍不能寫。
- `Read(./假檔)` deny 規則對「有」與「無」`tools` 欄位的 subagent 都生效，且 Grep 不繞過。

**限制（不得略）**：單組自測；MCP 在該環境全部連線失敗，故 MCP 排除標為 **NOT APPLICABLE**；`bypassPermissions` 父 session 下白名單是否仍強制＝**NOT VERIFIED（文件亦未載明）**；Bash `cat` 繞過 deny 未測。**本觀察不構成完整資安隔離。**

### 2.3 3 項正式權限正負向測試（對最終三個 Agent 檔）

**NOT RUN（待測試組填入）。** 預計項目與結果欄由 PR-2 測試組填寫；PR-1 不預填。

| # | 測試項 | 結果 |
|---|---|---|
| 1 | 待測試組定義（正向：可 Read 無敏感內容的測試檔） | NOT RUN |
| 2 | 待測試組定義（負向：嘗試寫入／執行須失敗） | NOT RUN |
| 3 | 待測試組定義（負向：敏感路徑 Read 行為，僅用假檔） | NOT RUN |

## 3. Token／返工 A/B 量測

**NOT RUN（PR-2 執行）。** 設計摘要（授權內容見 `DEC-2026-11-13-04` (3)）：

- 載具：`claude -p --output-format json`。
- 固定：相同 main SHA、任務、主模型、Effort、初始資料；各自獨立冷啟動；先 N=3，再 N=6 配對。
- 取數注意（總管派工單轉述的 spike 觀察，待 PR-2 重驗）：`usage` 欄位不含 subagent 用量，須用 `modelUsage` 與 `total_cost_usd`；輸入基線約 44k tokens 為固定開銷；`cache_creation`／`cache_read` 切分會漂移，故比較用「三項輸入合計＋output＋cost」。
- 記錄：token、費用（有可靠來源才計）、正確率、漏項、返工、路由符合度、交接開銷。
- 判準：正確性與安全性不得退步；效益目標為中位數降低至少 10%；樣本小不得宣稱統計顯著；量測不可得標 NOT VERIFIED，不得編造節省比例。

| 指標 | A（無 Agent） | B（有 Agent） | 結果 |
|---|---|---|---|
| 全部指標 | NOT RUN | NOT RUN | NOT RUN |

## 4. 零記憶接手驗收

**NOT RUN（PR-2 執行）。** 範圍：正負例含權限、角色衝突、資料缺值；失敗據實保留，不得改寫標準（`DEC-2026-11-13-04` (4)）。

## 5. 盲點與 NOT VERIFIED

1. 官方文件查證與 §2.2 的 spike 觀察，本組撰寫 PR-1 時**未獨立重跑**，皆為派工單轉述。
2. 結構守衛只驗檔案結構，**不驗**實際執行期權限；通過不代表隔離成立。
3. `fund-independent-qa` 與主 session 共享派工來源，獨立性為有限度的（§0-3）。
4. 以 Agent 工具自動路由到這三個 Agent 的實際行為未量測（PR-2）。
5. 「`.claude/agents/` 僅此三檔」「`.claude/` 下無 settings 檔」等全稱句為單組字面搜尋，未經第二組驗證。
6. 本批未執行任何 live 探測、未讀任何憑證、未印任何敏感內容。

## 6. 對下一步的含義

- PR-1 經非作者 QA 與同 head CI 後以一般 merge commit 合併；PR-2 另批執行 §2.3、§3、§4 並填入結果。
- 待客戶裁示、不施工（BL-0549）：(i) 是否為三個 Agent 開放唯讀 GitHub MCP 查詢工具；(ii) 是否在 `.claude/settings.json` 加敏感路徑 `Read(...)` deny 規則。**登記不等於施工。**
- 在 PR-2 取得有效數據前，不得宣稱 Agent 導入的效益，也不得宣稱六項品質補強全部完成。
