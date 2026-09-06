# `_recon/` — R1 踩點用的一次性分析工具（**暫存，PR 定稿前會刪**）

存在的理由：本批唯一承重的宣稱是「③ 會不會寫到使用者的 Google Sheet」，
而該宣稱**取決於「有沒有漏看」**（`CLAUDE.md §-2` 規則 5）→ 必須用可重跑的工具產出，
不能用字面 grep 的印象。四支腳本都刻意**寧可多抓**，命中後人工逐一判讀。

| 檔 | 做什麼 |
|---|---|
| `closure.py`   | AST 傳遞 import 閉包（含函式內 lazy import、含 `pkg/__init__` 連帶） |
| `gs_writes.py` | AST 掃 gspread 寫入形態的呼叫（`ws.update` / `append_row` …），含 pandas 同名假陽性 |
| `callgraph.py` | 第一方函式**呼叫**可達性；含「函式被當成值傳給 `safe_section` 」這種 callback 形態 |
| `path.py`      | 印出 entry → 目標函式的其中一條實際路徑，供逐邊人工複驗 |

⚠️ **import 可達 ≠ 呼叫可達**：本批兩者都算，並以**逐邊讀原始碼**為最終依據。
