# -*- coding: utf-8 -*-
"""set 頁正式模式畫面測試的接頭：測試把三個函式放進 `LOADERS`，AppTest 腳本讀它呼叫 `page.render`。

AppTest 在同一個行程裡跑腳本，所以測試對 L1（假 gspread）與 `source.st` 的替換，腳本裡看得到。
"""

LOADERS: dict = {}
CALLS: list = []
PICKER: dict = {}  # 批 3b-3：`page.render(picker_live=...)` 的替身（`{"load": 函式, "act": 函式}`）
LOGIN: dict = {}   # 批 3b-2：`page.render(login_live=...)` 的替身（`{"load": 函式, "act": 函式}`）
