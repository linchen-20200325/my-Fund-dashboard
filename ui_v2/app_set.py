# -*- coding: utf-8 -*-
"""進入點：streamlit run ui_v2/app_set.py

本頁只畫設定與診斷一頁，資料為假資料（示意值），不接任何真實資料源。
17 種情境用查詢參數切：`?scenario=ok|first|stale|zero|nolimit|norows|failed|notier|emptyresp|badkind|broken|undef|keep1|navfail|logfail|settingfail|zerotoday`。
「存檔寫入失敗」是**與情境正交**的一枚開關，疊在任一種情境上：`&savefail=1`。

⚠️ 上面那份情境清單的**唯一真相源是 `ui_v2/set/fixtures.ALL_SCENARIO_NAMES`**；
   本 docstring 只是轉述，兩者由測試釘死。
"""

from __future__ import annotations

import pathlib
import sys

import streamlit as st

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from ui_v2.set import page  # noqa: E402

st.set_page_config(page_title="設定與診斷", layout="wide")
page.render()
