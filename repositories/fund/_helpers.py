"""repositories/fund/_helpers.py — v19.200 P1-5 module-level imports + 共用常數。

從 fund_repository 主檔抽出(原 line 16-73)。所有子檔(sources / fund_orchestration /
nav_metrics / fx_and_main)從本檔取共用 import + 常數。
"""
from __future__ import annotations


import re        # [Auto-Fixed v18.203] 原缺此 import，致多處 HTML 解析的 re.findall/search 被呼叫時 NameError→靜默失敗
import requests   # [Auto-Fixed v18.203] 原缺此 import，致 L341/406/434 的 requests.get 在被呼叫時 NameError→靜默落 fallback
import pandas as pd
from bs4 import BeautifulSoup

# v11.0 B-9b-5: 從 infra.cache 取 cache 機制（@register_cache / @_ttl_cache /
# _cache_load_* / _cache_save_* / _FUND_SNAPSHOT）— slice A 內含這些 decorators
from infra.cache import (  # noqa: F401
    _ttl_cache,
    register_cache,
    _CACHE_DIR,
    _FUND_SNAPSHOT,
    _cache_path,
    _cache_load_nav,
    _cache_save_nav,
    _cache_load_div,
    _cache_save_div,
    _cache_load_meta,
    _cache_save_meta,
)
from shared.fred_series import (
    FRED_CHF_USD,
    FRED_CNH_USD,
    FRED_EUR_USD,
    FRED_JPY_USD,
)
from shared.ttls import TTL_5MIN, TTL_15MIN, TTL_30MIN

# Utility from fund_fetcher — module-level import is partial-load safe，因為
# fund_fetcher 載入到本檔的 re-export 點（line ~663）時，下方 utility 已定義
# v18.122 issue 4 真根因：本檔 39+ 處用以下 symbol 但僅 import 3 個，其餘全 NameError
#   → 各 _src_* fallback chain 抓到 NameError 後吞掉 → series=0 假象
#   → 用 NAS Proxy 也救不了（NameError 在 HTTP 前就崩）
# 修補 6 個漏 import：HDR (13 callsites) / HDR_JSON (1) / PORTAL_CFG (8) /
#   normalize_result_state (6) / merge_non_empty (9) / classify_fetch_status (2)
from fund_fetcher import (  # noqa: F401
    safe_float,
    fetch_url_with_retry,
    is_valid_moneydj_page,
    HDR,
    HDR_JSON,
    PORTAL_CFG,
    TCB_BASE,
    _INSURANCE_SUBDOMAIN_HINTS,
    normalize_result_state,
    merge_non_empty,
    classify_fetch_status,
)

# v18.115 B-A: 修補 _proxies/_ssl_verify NameError（PR #171 已修）
from infra.proxy import _proxies, _ssl_verify  # noqa: F401
