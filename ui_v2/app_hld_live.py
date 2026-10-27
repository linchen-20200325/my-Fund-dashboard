# -*- coding: utf-8 -*-
"""正式入口：streamlit run ui_v2/app_hld_live.py

體例同 `ui_v2/app_alo_live.py`：本檔 import 本頁 `source`，把載入函式與遮蔽函式傳給 `page.render`。
客戶 2026-10-16 裁示第 2 點起另傳寫入函式（`source.save_setting`；HLD-4「存檔」接上 `user_setting`）。
示範入口 `ui_v2/app_hld.py`（fixtures ＋ ?scenario=）維持原樣。
本檔與 `source` 都不 import fixtures（守衛：tests/ui_v2/test_ui_v2_live_import_guard.py）。
"""

from __future__ import annotations

import pathlib
import sys

import streamlit as st

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from ui_v2.hld import page, source  # noqa: E402

st.set_page_config(page_title="💼 我的持股", layout="wide")
page.render(load_live=source.load_live, mask_error=source.mask_error, save_live=source.save_setting)
