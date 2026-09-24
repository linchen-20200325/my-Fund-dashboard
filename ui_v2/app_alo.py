# -*- coding: utf-8 -*-
"""進入點：streamlit run ui_v2/app_alo.py

本頁只畫資產配置一頁，資料為假資料（示意值），不接任何真實資料源。
16 種情境用查詢參數切：`?scenario=full|first|noholding|notarget|nobasis|inband|notol|mvbasis|nofx|unbkt|nobucket|partial|holdfail|fxfail|settingfail|policyfail`。
「存檔寫入失敗」是**與情境正交**的一枚開關，疊在任一種情境上：`&savefail=1`。

⚠️ 上面那份情境清單的**唯一真相源是 `ui_v2/alo/fixtures.ALL_SCENARIO_NAMES`**；
   本 docstring 只是轉述，兩者由測試釘死。
"""

from __future__ import annotations

import pathlib
import sys

import streamlit as st

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from ui_v2.alo import page  # noqa: E402

st.set_page_config(page_title="資產配置", layout="wide")
page.render()
