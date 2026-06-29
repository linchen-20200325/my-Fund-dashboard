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

# v19.250 R20:日 TTL 語意 marker(對齊 `infra.cache._daily_cache` 裝飾器)。
# 用於月更新源頭(MoneyDJ 持股 / wb07 風險 / wb05 配息),保存當日 TW UTC+8,
# 隔日午夜 miss 重抓。caller 用 `@_daily_cache` 直接裝飾(不傳 ttl_sec),
# 本 marker 提供 grep 可見性 + 文件一致性。
TTL_TODAY: str = "daily-reset"
