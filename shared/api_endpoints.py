"""shared/api_endpoints.py — SSOT 集中重複的 production API endpoints(L0 純常數)。

v19.223 P1-2:深層稽核發現 3+2+2 = 7 處 production URL 字串重複,收口至本 SSOT。

設計原則
========
- **只收「真實重複」**:同一 URL 字串散落 2+ 檔的才入庫
- **不收「散落但唯一」**:單一 caller 唯一定義的 URL 保留 source-local
  (例 fred.py FRED_BASE / yf.py YF_CHART_BASE 等 fetcher 自家 URL,
   作為 fetcher 內聚的 SSOT,不抽出來)

當前 SSOT 內容
==============
- FINMIND_BASE:FinMind v4 data API,被 hot_money_repository /
  macro_tw_local_repository / tw_macro_repository 3 檔共用

未列入(各自 source-local SSOT,讀 caller 即見)
==============================================
- repositories/macro/fred.py:28 FRED_BASE
- repositories/macro/yf.py:18 YF_CHART_BASE
- repositories/macro/alternate.py: DEFILLAMA / AAII
- repositories/fund/sources.py: ALLIANZ / Cnyes / MoneyDJ
- repositories/news_repository.py: _GOOGLE_NEWS_RSS
- repositories/tw_macro_repository.py:39 TWSE_MI_INDEX_URL
- repositories/tw_macro_repository.py:45 CBC_EF15M01_URL
- services/ai_service.py:28 GEMINI_URL
- infra/oauth.py: GOOGLE_AUTH_URL / GOOGLE_TOKEN_URL

scripts 重複 URL 改 import 規則
==============================
scripts/update_macro_history.py 原 dupe `FRED_URL` + `YF_CHART_BASE`
改 import from production fetcher 位置(L1 SSOT):
  - `from repositories.macro.fred import FRED_BASE`
  - `from repositories.macro.yf import YF_CHART_BASE`
"""
from __future__ import annotations

# FinMind v4 data API — 3 caller 共用
# 原散落:hot_money_repository:25 / macro_tw_local_repository:35 / tw_macro_repository:40
FINMIND_BASE = "https://api.finmindtrade.com/api/v4/data"
