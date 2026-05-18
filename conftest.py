"""pytest conftest — 跨 test 共用 fixture

v18.58: TTL fetch cache 是模組層 dict，跨 test 會互相污染（A 測試 mock
fetcher 回 X，B 測試以為 mock 自己的 fetcher 但 cache hit 拿到 A 的 X）。
這裡 autouse fixture 在每個 test 開始前清空所有快取。
"""
import pytest


@pytest.fixture(autouse=True)
def _clear_fetch_cache_between_tests():
    """每個 test 前後清空模組層 TTL cache，避免測試污染。"""
    try:
        from fund_fetcher import clear_all_caches as _cac
        _cac()
    except Exception:
        pass
    yield
    try:
        from fund_fetcher import clear_all_caches as _cac
        _cac()
    except Exception:
        pass
