"""harness（本批在 scratchpad 執行，原樣入庫供重現，非 repo 程式；ROOT 為佔位，須改成本機 worktree 絕對路徑）：注入 tests/ui_v3/market_stubs 的人造資料後啟動 Preview App。數值是人造的。"""
import sys
ROOT = "<WORKTREE_ROOT>"
sys.path.insert(0, ROOT); sys.path.insert(0, ROOT + "/tests/ui_v3")
import streamlit as st
import market_stubs as ms
from ui_v3.adapters import market_page as a
sc = st.query_params.get("scenario", "normal")
kw = dict(tw="missing") if sc == "missing" else {}
v, t = ms.view(**kw), ms.table()
a.load = lambda sources: (v, t)
from ui_v3 import app_preview
app_preview.main()
