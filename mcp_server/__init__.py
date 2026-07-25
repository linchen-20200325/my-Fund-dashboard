"""mcp_server — read-only MCP (Model Context Protocol) delivery adapter (PoC).

架構定位(對照 CLAUDE.md §8.2):本套件是**與 `ui/` 平行的 L3-sibling 交付 adapter**。
它只呼叫 L2 `services/*`(和 UI 走同一條路),不含業務邏輯、不做交易、不寫資料。

- `_serialize`:L2 回傳(dict/df/scalar/pandas/numpy)→ JSON-safe;fail-loud raise → 結構化 error 信封
- `tools_macro`:`build_macro_snapshot` 純邏輯(不依賴 fastmcp,可單元測試)
- `server`:FastMCP stdio 進入點(唯一 import fastmcp 的檔),thin orchestrator

PoC 範圍:只暴露 1 個工具 `get_macro_snapshot`(驗證 MCP 互動手感),
手感確認後再照 §8.5 一次一個補上 fund/health/fx 工具湊成 v1。

依賴隔離:fastmcp 只列在 `mcp_server/requirements.txt`,**不進主 requirements.txt**,
避免污染 Streamlit Cloud 部署(app 本身不需要 fastmcp)。
"""
