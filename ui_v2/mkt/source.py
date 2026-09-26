# -*- coding: utf-8 -*-
"""市場總覽的正式資料來源：呼叫 L2 `services/v2_tables`，組出與 fixtures 同形的 dataset。

依據 docs/v2/49_data_integration_plan.md §3.3 方案 A（`source.py` 那一列）與
`ACCEPTANCE.md` 七（失敗訊息遮蔽，客戶 2026-09-26 裁示 Q13）：
- **只由 `ui_v2/app_mkt_live.py` import**；`page.py` 不 import 本檔 —— 本檔經 L2 會連到
  舊樹 L1（及其 streamlit、bs4 等相依），`page.py` 一旦 import 本檔，缺那些套件的驗收環境
  會在 import 階段就失敗。
- 本檔不 import fixtures；不放任何快取（快取只在 L1，49 §4.4）；不發任何網路請求。
- **秘密值在本層讀**（`st.secrets`、環境變數、登入後的 OAuth 權杖），交給 L2 的遮蔽函式；
  遮蔽在這裡做一次（畫面的寫出點），L2 本身不讀任何秘密值、不 import streamlit。

`load_live()` 回傳：
- `dataset`：與 `fixtures.dataset_*()` 同形的 `{"rows": [...], "errors": {...}}`，errors 已遮蔽；
- `notes`：正式模式畫面要用的附註 ——
  `pending`（不寫列的鍵 → 原因代碼）、`masked_keys`（錯誤原文含遮蔽記號的鍵）、
  `cooldowns`（本頁來源的冷卻狀態）。
"""

from __future__ import annotations

import os

import streamlit as st

from services.v2_tables import market_indicator, masking


def _secret_values() -> list:
    """從 `st.secrets`、環境變數與登入權杖讀出 ACCEPTANCE 7.2 列名鍵的值。"""
    return masking.secret_values(
        [st.secrets, os.environ],
        oauth_tokens=st.session_state.get("gsheet_tokens"),
        custom_oauth_cfg=st.session_state.get("custom_oauth_cfg"),
    )


def load_live() -> dict:
    """給 `page.render(load_live=...)` 用的載入函式。"""
    table = market_indicator.build_market_indicator_table()
    values = _secret_values()
    errors = {key: masking.mask_message(message, values)
              for key, message in table["errors"].items()}
    return {
        "dataset": {
            "rows": [dict(row) for row in table["rows"]],
            "errors": errors,
        },
        "notes": {
            "pending": dict(table["pending"]),
            "masked_keys": sorted(k for k, m in errors.items() if masking.is_masked(m)),
            "cooldowns": market_indicator.source_cooldowns(),
        },
    }
