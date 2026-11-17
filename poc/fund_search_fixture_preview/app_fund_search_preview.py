# -*- coding: utf-8 -*-
"""🔍 找一檔基金／依條件篩選｜隔離式 FAKE Preview 入口（非正式頁面、非正式資料）。

`streamlit run poc/fund_search_fixture_preview/app_fund_search_preview.py`

頁頂固定一列 FAKE 標示（屬 harness，不屬 renderer）；下區以 selectbox 切換 FAKE 選股池情境。
不取數、不連線、不讀憑證、不寫任何東西；不接 registry／`app_preview`、不掛 🔍 頁。
"""
from __future__ import annotations

import pathlib
import sys

_HERE = pathlib.Path(__file__).resolve().parent
for _p in (str(_HERE), str(_HERE.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import streamlit as st  # noqa: E402

import fund_search_fake_inputs as fake  # noqa: E402
import fund_search_renderer as R  # noqa: E402
import fund_search_wording as W  # noqa: E402
from ui_v3.design import theme  # noqa: E402

KEY_SCENARIO = "uvp_fs_scenario"
FAKE_BANNER = "FAKE／測試資料（離線注入，未執行任何真實請求）"
SCENARIO_LABEL = "選股池情境（harness）"


def main() -> None:
    border, text = theme.v("color.card.border"), theme.v("color.text.primary")
    st.markdown(
        f'<div data-harness="true" style="border:1px dashed {border};color:{text};padding:6px 10px;margin:0 0 6px 0;'
        f'font-size:{theme.v("type.caption")}">{FAKE_BANNER}<br>{fake.HARNESS_CODES_HINT}</div>',
        unsafe_allow_html=True)
    R.render_css()
    R.render_lookup(fake.LOOKUP_FIXTURES, fake.FAKE_FOUND_NAME)
    st.markdown(R.divider_html(), unsafe_allow_html=True)
    ids = list(fake.SCENARIOS)
    st.selectbox(SCENARIO_LABEL, ids, key=KEY_SCENARIO, index=ids.index(fake.DEFAULT_SCENARIO),
                 format_func=lambda sid: fake.SCENARIOS[sid][0])
    R.render_exp(fake.build(st.session_state[KEY_SCENARIO]), fake.CONDITION_COUNT)


main()
