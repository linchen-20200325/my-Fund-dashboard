# -*- coding: utf-8 -*-
"""進入點：streamlit run ui_v2/app_hld.py

本頁只畫持倉體檢一頁，資料為假資料（示意值），不接任何真實資料源。
六種狀態用查詢參數切：`?scenario=full|srcmiss|bizexc|fetchfail|nothr|empty`。
"""

from __future__ import annotations

import pathlib
import sys

import streamlit as st

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from ui_v2.hld import page  # noqa: E402

st.set_page_config(page_title="持倉體檢", layout="wide")
page.render()
