# -*- coding: utf-8 -*-
"""正式入口：streamlit run ui_v2/app_mkt_live.py

依據 docs/v2/49_data_integration_plan.md §3.3：本檔 import 本頁 `source`，把它的載入函式
傳給 `page.render`。示範入口 `ui_v2/app_mkt.py`（fixtures ＋ ?scenario=）維持原樣。
本檔與 `source` 都不 import fixtures（守衛：tests/ui_v2/test_ui_v2_live_import_guard.py；
執行期證據：tests/ui_v2/test_mkt_live_page.py）。
"""

from __future__ import annotations

import pathlib
import sys

import streamlit as st

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from ui_v2.mkt import page, source  # noqa: E402

st.set_page_config(page_title="市場總覽", layout="wide")
page.render(load_live=source.load_live)
