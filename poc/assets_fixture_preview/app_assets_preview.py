# -*- coding: utf-8 -*-
"""💼 我的資產｜隔離式 FAKE Preview 入口（非正式頁面、非正式資料）。

`streamlit run poc/assets_fixture_preview/app_assets_preview.py`

頁頂固定一列 FAKE 標示（屬 harness，不屬 renderer）；下方用 selectbox 切換九個 FAKE 情境，
情境 dict → `build_assets_page` → renderer。不取數、不讀憑證、不寫任何東西。
"""
from __future__ import annotations

import pathlib
import sys

_HERE = pathlib.Path(__file__).resolve().parent
for _p in (str(_HERE), str(_HERE.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import streamlit as st  # noqa: E402

import assets_fake_inputs as fake  # noqa: E402
from ui_v3.adapters.assets_page import build_assets_page  # noqa: E402
from ui_v3.design import theme  # noqa: E402
from ui_v3.pages.assets import render  # noqa: E402

KEY_SCENARIO = "uvp_assets_scenario"
FAKE_BANNER = "FAKE／測試資料（非真實持倉，不代表任何實際資料）"


def main() -> None:
    border, text = theme.v("color.card.border"), theme.v("color.text.primary")
    st.markdown(
        f'<div data-harness="true" style="border:1px dashed {border};color:{text};padding:6px 10px;margin:0 0 6px 0;'
        f'font-size:{theme.v("type.caption")}">{FAKE_BANNER}</div>',
        unsafe_allow_html=True)
    st.selectbox("情境", list(fake.SCENARIOS), key=KEY_SCENARIO, index=list(fake.SCENARIOS).index(fake.DEFAULT_SCENARIO),
                 format_func=lambda sid: fake.SCENARIOS[sid][0])
    render(build_assets_page(fake.build(st.session_state[KEY_SCENARIO])))


main()
