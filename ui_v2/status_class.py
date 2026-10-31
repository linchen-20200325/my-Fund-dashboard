# -*- coding: utf-8 -*-
"""頁級狀態分類（page-level presentation status）用的封閉分類詞與嚴重度（純常數；零 streamlit import）。

客戶 2026-10-30 裁示 P3／β（`docs/DECISIONS.md` `DEC-2026-10-30-04`；`docs/v2/74_assets_d3_formula_gate.md` 第 3 節 P3）。
`HLD-0`／`ALO-0` 各自在 **logic 的判定分支裡**明示自己屬哪一類（`_page_class` 鍵），頁級 aggregation（`ui_v2/asset/page_status.py`）
只讀這個鍵，**不比對字面、不比對 `_tone`**（74 第 1.4 節第 4 點、第 4.2 節）。這個鍵只是分類標籤：不改任何 rule result、
不改燈的字樣／符號／顏色／`_state`，不進 Decision Digest，不是 Risk Cap 的輸入或輸出。

β 階梯（客戶原話）：取數失敗 > 無持倉 > ◆ > ◇ > ⬜ > 持股只評估一部分（H7） > 無偏離／帶內。
"""

from __future__ import annotations

ERROR = "取數失敗"            # E：⛔
NO_HOLDING = "無持倉"          # Z：尚未建立任何持倉
ATTENTION = "需要注意"         # D：◆
MISSING = "資料未備"           # M：◇（含 A6m／A5c／F-18／F-19）
UNSET = "未設定或不適用"        # U／X：⬜
PARTIAL = "只評估一部分"        # N*：H7／H6 部分評估（無偏離，但他卡不完整）
NORMAL = "無偏離"              # N：完整評估且無偏離／帶內

# 由重到輕（β）。同級時「持股」先、「配置」後（由 aggregation 處理）。
SEVERITY_ORDER = (ERROR, NO_HOLDING, ATTENTION, MISSING, UNSET, PARTIAL, NORMAL)
RANK = {cls: index for index, cls in enumerate(SEVERITY_ORDER)}

# 正常以外一律「非正常」：任何一區是這些之一，另一區的 NORMAL 不得把它遮成正常。
NON_NORMAL = frozenset(SEVERITY_ORDER) - {NORMAL}
