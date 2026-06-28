"""repositories/macro/_helpers.py — v19.203 P2-5 module-level imports + 常數。"""
from __future__ import annotations


import datetime as _dt
import json as _json
import math
import os as _os
from typing import Optional

import numpy as np
import pandas as pd

# v11.0 A-1 後 infra/proxy.py 為 fetch_url 主位置；proxy_helper.py 走 shim 也可，
# 但 Repository Layer 直接依新路徑，少一跳 import 並示範新分層
from infra.proxy import fetch_url

# v18.58: 借用 fund_fetcher 的 TTL 快取裝飾器（同樣模組層共享、可 clear_all_caches 統一清空）
from fund_fetcher import _ttl_cache, register_cache
from shared.fred_series import (
    FRED_BSCICP02,
    FRED_CHN_CPI,
    FRED_CHN_M2,
    FRED_CHN_OECD_CLI,
    FRED_CHN_PMI,
    FRED_CNH_USD,
    FRED_PHILLY_FED,
)
from shared.macro_thresholds_v2 import (  # F-GRAY-4 v19.169 HY + v19.183 CPI
    CPI_YOY_THRESHOLDS as _CPI_THR,
    HY_SPREAD_THRESHOLDS as _HY_THR,
)

# F-GRAY-4 v19.169: HY_SPREAD stoplight SSOT (SPEC §16.2)
_HY_SPREAD_STOPLIGHT = _HY_THR["stoplight"]
# F-GRAY-4 v19.183:CPI stoplight SSOT(原 inline {1.5/2.5/3.5/4.0} 完全等價)
_CPI_STOPLIGHT = _CPI_THR["stoplight"]
from shared.signal_thresholds import (  # v19.74 W3a SSOT consume
    RECESSION_LOGIT_COEF_INTERCEPT,
    RECESSION_LOGIT_COEF_SPREAD,
)
from shared.ttls import TTL_5MIN, TTL_10MIN, TTL_30MIN

__version__ = "1.0.0"

FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"
FRED_RELEASE_BASE = "https://api.stlouisfed.org/fred/series/release"
FRED_RELEASE_DATES_BASE = "https://api.stlouisfed.org/fred/release/dates"
YF_CHART_BASE = "https://query1.finance.yahoo.com/v8/finance/chart"

_FRED_RELEASE_CACHE_DIR = _os.path.join("cache", "fred_release")
_FRED_RELEASE_CACHE_TTL_DAYS = 30
