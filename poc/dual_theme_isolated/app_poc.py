# -*- coding: utf-8 -*-
"""雙模式隔離 PoC 的 Streamlit 入口（非 production；沒有 `pages/`，不由任何正式入口 import）。

手動執行：`streamlit run poc/dual_theme_isolated/app_poc.py`
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import streamlit as st  # noqa: E402

st.set_page_config(page_title="雙模式 PoC（隔離）", page_icon="🧪", layout="wide")

import poc_page  # noqa: E402

poc_page.render()
