"""mcp_server/server.py — FastMCP stdio 進入點(PoC,thin orchestrator)。

角色對照 `app.py`:只註冊工具 + 啟動,**零業務邏輯**。所有計算走 L2 `services/*`,
所有正規化 / 錯誤信封走 `mcp_server._serialize`。這是唯一 import fastmcp 的檔 ——
fastmcp 缺失不影響 `tools_macro` / `_serialize` 的單元測試。

跑法(本地 stdio,接 Claude Desktop):
    export FRED_API_KEY=xxxx
    python -m mcp_server.server

Claude Desktop 設定(claude_desktop_config.json)範例:
    {
      "mcpServers": {
        "fund-dashboard": {
          "command": "python",
          "args": ["-m", "mcp_server.server"],
          "cwd": "/path/to/my-Fund-dashboard",
          "env": {"FRED_API_KEY": "xxxx"}
        }
      }
    }
"""
from __future__ import annotations

import contextlib
import sys

from mcp_server._serialize import error_envelope

# import tools_macro 會連帶 import services.macro → streamlit,啟動時 streamlit 可能
# 印 config 警告到 stdout。stdio MCP 的 stdout 專供 protocol,故 import 期間把 stdout
# 導向 stderr(protocol 尚未開始寫,安全);import 完 stdout 自動還原給 FastMCP。
with contextlib.redirect_stdout(sys.stderr):
    from mcp_server.tools_macro import build_macro_snapshot

try:
    from fastmcp import FastMCP
except ImportError as _e:  # pragma: no cover — 缺依賴的友善提示
    raise SystemExit(
        "fastmcp 未安裝。請先安裝 MCP server 依賴:\n"
        "    pip install -r mcp_server/requirements.txt"
    ) from _e


mcp = FastMCP("fund-dashboard-mcp")


@mcp.tool()
def get_macro_snapshot() -> dict:
    """當前美國總經健康度快照。

    回傳:加權健康度總分(composite_score)、5 級白話評價(verdict)、
    景氣位階 0-10(phase)、買/賣總結燈(action_light)、regime、
    雙演算法對帳(reconciliation)、風險警報(alerts)、資料血緣(provenance)。

    FRED_API_KEY 讀自環境變數。資料全部來自儀表板的 L2 服務層(services/macro/*),
    與 Streamlit 網頁看到的同一套計算。缺 key / 全來源失敗時回
    `{"ok": false, "error": ...}`(誠實報錯,不回假數字)。
    """
    return error_envelope(build_macro_snapshot)


def main() -> None:
    """stdio transport 啟動(FastMCP 預設)。"""
    mcp.run()


if __name__ == "__main__":
    main()
