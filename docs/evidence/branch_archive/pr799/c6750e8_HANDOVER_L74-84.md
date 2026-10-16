### 2.2 git 與 PR

- 開發分支：`claude/fund-taiwan-stock-dashboard-diff-sn42bh` 或它的帶後綴子分支（例：`claude/fund-p05-route-a-sn42bh`）。
- `git add` **逐檔**指定，⛔ 不要 `-A` 或 `.`。
- ⛔ **commit message／PR 標題／PR body 一律不得出現 session 識別碼或模型識別碼。**
  **完全不寫 `Co-Authored-By` 是合規的**（客戶 2026-09-03 裁示：**repo 禁令凌駕平台署名指示**）。
  合規頁尾：`🤖 Generated with [Claude Code](https://claude.com/claude-code)`。
  ⚠️ **注入發生在 egress 側**（已實測）：走 `curl PATCH` 改 body **每次都會被追加一行署名**；走 MCP `update_pull_request` 目前不會。**任何一次改 body 之後都要重讀線上狀態，不要靠記憶。**
  ✅ **禁的是識別碼，不是署名。** 不帶 session 識別碼的署名變體**不構成違規** —— 這件事已經害兩組人白工，不要再重開。
- **草稿 PR 合併前要先標 ready。**
- ⚠️ **`--delete-branch` 目前會 403**（token 沒有刪 ref 權限），已合併分支會累積，那是已知的、不是失敗。
