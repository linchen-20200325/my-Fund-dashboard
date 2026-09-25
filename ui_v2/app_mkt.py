# -*- coding: utf-8 -*-
"""進入點：streamlit run ui_v2/app_mkt.py

本頁只畫市場總覽一頁，資料為假資料（示意值），不接任何真實資料源。
"""

from __future__ import annotations

import pathlib
import sys

import streamlit as st

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from ui_v2.mkt import page  # noqa: E402

st.set_page_config(page_title="市場總覽", layout="wide")
page.render()
