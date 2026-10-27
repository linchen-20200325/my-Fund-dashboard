# -*- coding: utf-8 -*-
"""正式入口：streamlit run ui_v2/app_exp_live.py

依據 docs/v2/49_data_integration_plan.md §3.3 與客戶 2026-10-13 裁示（B 線標的探索正式模式第一批）：
本檔 import 本頁 `source`，把它的載入函式與寫入函式（`EXP-1`／`EXP-4`／`EXP-5` 的存檔）傳給 `page.render`。
示範入口 `ui_v2/app_exp.py`（fixtures ＋ ?scenario=）維持原樣。
本檔與 `source` 都不 import fixtures（守衛：tests/ui_v2/test_ui_v2_live_import_guard.py；
執行期證據：tests/ui_v2/test_exp_live_page.py）。
"""

from __future__ import annotations

import pathlib
import sys

import streamlit as st

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from ui_v2.exp import page, source  # noqa: E402

st.set_page_config(page_title="🔍 找基金", layout="wide")
page.render(load_live=source.load_live, save_live=source.save_setting, mask_error=source.mask_error)
