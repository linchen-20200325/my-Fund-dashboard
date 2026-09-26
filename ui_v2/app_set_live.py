# -*- coding: utf-8 -*-
"""正式入口：streamlit run ui_v2/app_set_live.py

依據 docs/v2/49_data_integration_plan.md §3.3：本檔 import 本頁 `source`，把它的三個函式
（載入、存檔、重新取數）傳給 `page.render`。示範入口 `ui_v2/app_set.py`（fixtures ＋ ?scenario=）維持原樣。
本檔與 `source` 都不 import fixtures（守衛：tests/ui_v2/test_ui_v2_live_import_guard.py；
執行期證據：tests/ui_v2/test_set_live_page.py）。
"""

from __future__ import annotations

import pathlib
import sys

import streamlit as st

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from ui_v2.set import page, source  # noqa: E402

st.set_page_config(page_title="設定與診斷", layout="wide")
page.render(load_live=source.load_live, save_live=source.save_setting, refetch_live=source.refetch)
