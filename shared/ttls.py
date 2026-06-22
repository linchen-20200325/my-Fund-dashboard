"""v19.69 快取 TTL SSOT — `@_ttl_cache(ttl_sec=N)` / `@st.cache_data(ttl=N)` 秒數常數集中地.

22 處 `ttl_sec=N` / `ttl=N` 散落 9 production 檔，集中為 6 個語意常數（依時間長度命名）。
與 Stock 端 shared/ttls.py 對稱（Fund-only，不進 sync_to_stock.sh）：Fund 用 custom
`@_ttl_cache(ttl_sec=N)` 為主，Stock 用 Streamlit `@st.cache_data(ttl=N)` 為主，
兩端常數值定義各自獨立。

排除：
  - test_fetch_cache.py：測試 fixture 用 literal ttl=300/1 為刻意行為，保留不改。
  - infra/cache.py:13：docstring code example，純文件不需 import。

caller 用法：
    from shared.ttls import TTL_30MIN

    @_ttl_cache(ttl_sec=TTL_30MIN, maxsize=2)
    def fetch_macro(...): ...
"""
from __future__ import annotations

TTL_1MIN: int = 60
TTL_5MIN: int = 300
TTL_10MIN: int = 600
TTL_15MIN: int = 900
TTL_30MIN: int = 1800
TTL_1HOUR: int = 3600
