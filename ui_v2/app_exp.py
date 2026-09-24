# -*- coding: utf-8 -*-
"""進入點：streamlit run ui_v2/app_exp.py

本頁只畫標的探索一頁，資料為假資料（示意值），不接任何真實資料源。
23 種情境用查詢參數切：`?scenario=full|nocond|zero|blankvalue|onematch|tenmatch|nocolumn|sortdropped|
sortnav|sortname|sortccy|sortdate|sortratio|profilefail|
profilefail_picked|navfail|twofail|nofee|unknownfund|watchall|nowatch|
mixedccy|draftdiffers`。
「存檔寫入失敗」是**與情境正交**的一枚開關，疊在任一種情境上：`&savefail=1`。

⚠️ 上面那份情境清單的**唯一真相源是 `ui_v2/exp/fixtures.ALL_SCENARIO_NAMES`**；
   本 docstring 只是轉述，兩者由測試釘死（`test_進入點docstring列的情境集合等於fixtures那一份`）。
"""

from __future__ import annotations

import pathlib
import sys

import streamlit as st

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from ui_v2.exp import page  # noqa: E402

st.set_page_config(page_title="標的探索", layout="wide")
page.render()
