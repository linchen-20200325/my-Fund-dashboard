"""H5／Shell 量測用啟動器：把取數換成 tests/ui_v3/market_stubs 的**注入資料**後啟動 Preview App。數值是人造的，不是真實行情。"""
import os, sys
ROOT = "/home/user/my-Fund-dashboard"
sys.path.insert(0, ROOT); sys.path.insert(0, ROOT + "/tests/ui_v3")
import streamlit as st
import market_stubs as ms
from ui_v3.adapters import market_page as a

scenario = st.query_params.get("scenario", "normal")
kw, tkw = {}, {}
if scenario == "missing": kw = dict(tw="missing")
elif scenario == "failed": kw = dict(us="error")
elif scenario == "both_missing": kw = dict(tw="missing", us="missing")
elif scenario == "stale": kw = dict(us_dates=ms.weekdays("2021-06-01", "2026-10-30"))
elif scenario == "partial": kw = dict(us_dates=ms.weekdays("2024-11-01", ms.LAST_US))
elif scenario == "nokey": kw = dict(key=""); tkw = dict(errors={"credit_spread_pct": "未設定 FRED_API_KEY", "term_spread_pct": "未設定 FRED_API_KEY"}, drop=("credit_spread_pct", "term_spread_pct"))
elif scenario == "all_missing": kw = dict(tw="missing", us="missing", vx="missing"); tkw = dict(drop=("vol_index", "credit_spread_pct", "term_spread_pct", "policy_rate_pct"))
elif scenario == "all_failed": kw = dict(tw="error", us="error", vx="error"); tkw = dict(errors={k: "HTTP 429 injected" for k in ("vol_index", "credit_spread_pct", "term_spread_pct", "policy_rate_pct")}, drop=("vol_index", "credit_spread_pct", "term_spread_pct", "policy_rate_pct"))
elif scenario == "negative":
    pass
v = ms.view(**kw)
if scenario == "negative":
    for d in v["domains"]:
        if d["domain"] == "taiex": d["fetched_at"] = "2026-10-30T02:00:00+00:00"
t = ms.table(**tkw)
a.load = lambda sources: (v, t)
from ui_v3 import app_preview
app_preview.main()
