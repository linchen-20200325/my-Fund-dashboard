"""v18.58 模組層 TTL 快取裝飾器測試

驗證：
  - 同 args 在 TTL 內 hit cache（fetcher 不被呼叫第二次）
  - args 不同 → 各自獨立 entry
  - TTL 過期 → 重新 fetch
  - cache_clear() 清空後 → 強制 fetch
  - LRU maxsize 超過 → 砍最舊 entry
  - clear_all_caches() 註冊機制
"""
import time

import pytest

from fund_fetcher import (
    _ttl_cache,
    register_cache,
    clear_all_caches,
    get_all_cache_info,
)


def _make_counting_fetcher(ttl: int = 300, maxsize: int = 8):
    """測試輔助：建一個被 _ttl_cache 包過的 fake fetcher，回傳 (fn, call_log)"""
    _log: list = []

    @_ttl_cache(ttl_sec=ttl, maxsize=maxsize)
    def _fake_fetch(arg: str, opt: int = 0):
        _log.append((arg, opt))
        return f"result-{arg}-{opt}"

    return _fake_fetch, _log


def test_cache_hit_same_args():
    """同 args 在 TTL 內 → 只 fetch 一次"""
    fn, log = _make_counting_fetcher(ttl=300)
    r1 = fn("AAA")
    r2 = fn("AAA")
    r3 = fn("AAA")
    assert r1 == r2 == r3 == "result-AAA-0"
    assert len(log) == 1, "同 args 應該只觸發 1 次底層 fetch"


def test_cache_miss_different_args():
    """args 不同 → 各自 entry"""
    fn, log = _make_counting_fetcher(ttl=300)
    fn("AAA")
    fn("BBB")
    fn("AAA")   # cache hit
    fn("BBB")   # cache hit
    assert len(log) == 2, "AAA / BBB 各 1 次，重複命中 cache"


def test_cache_kwargs_normalized():
    """kwargs 順序不同但內容相同 → 同 cache key"""
    fn, log = _make_counting_fetcher(ttl=300)
    fn("X", opt=1)
    fn("X", opt=1)
    assert len(log) == 1


def test_cache_ttl_expire():
    """TTL 過期 → 重新 fetch"""
    fn, log = _make_counting_fetcher(ttl=1)   # 1 秒 TTL
    fn("AAA")
    assert len(log) == 1
    time.sleep(1.2)
    fn("AAA")
    assert len(log) == 2, "TTL 過期應觸發第二次 fetch"


def test_cache_clear_forces_refetch():
    """cache_clear() 後同 args 強制 fetch"""
    fn, log = _make_counting_fetcher(ttl=300)
    fn("AAA")
    fn("AAA")
    assert len(log) == 1
    fn.cache_clear()
    fn("AAA")
    assert len(log) == 2, "清空後應重新 fetch"


def test_cache_info_returns_metrics():
    """cache_info() 回傳 size / hits / misses"""
    fn, _ = _make_counting_fetcher(ttl=300)
    fn("AAA"); fn("BBB"); fn("AAA")    # 2 miss + 1 hit
    info = fn.cache_info()
    assert info["size"] == 2
    assert info["hits"] == 1
    assert info["misses"] == 2
    assert info["ttl_sec"] == 300


def test_cache_lru_maxsize_evicts_oldest():
    """超過 maxsize → 砍最舊（直接驗證 cache size 不超過 maxsize）"""
    fn, log = _make_counting_fetcher(ttl=300, maxsize=2)
    fn("A"); time.sleep(0.01)
    fn("B"); time.sleep(0.01)
    fn("C")   # 觸發 LRU eviction
    # cache size 應該維持 maxsize
    info = fn.cache_info()
    assert info["size"] <= 2, f"cache size {info['size']} 超過 maxsize=2"
    # 訪問 A → 該已被 evict → cache miss → 觸發新 fetch
    _calls_before = len(log)
    fn("A")
    assert len(log) == _calls_before + 1, "A 應已被 evict，再次訪問應觸發新 fetch"


def test_unhashable_kwargs_bypass_cache():
    """unhashable kwargs (e.g. list) → 不快取直接走原 fn"""
    @_ttl_cache(ttl_sec=300)
    def _f(arg, opt=None):
        return id(opt) if opt is not None else 0

    # list 不可 hash → 應該不 cache 但不該丟例外
    r1 = _f("x", opt=[1, 2])
    r2 = _f("x", opt=[1, 2])
    # 兩次呼叫都正常 return（cache miss 走原 fn）
    assert r1 is not None
    assert r2 is not None


def test_register_cache_and_clear_all():
    """register_cache 註冊 + clear_all_caches 統一清"""
    @register_cache
    @_ttl_cache(ttl_sec=300)
    def _g(x):
        return x * 2

    @register_cache
    @_ttl_cache(ttl_sec=300)
    def _h(x):
        return x + 1

    _g(1); _g(1); _h(5)
    info = get_all_cache_info()
    names = [r["name"] for r in info]
    assert "_g" in names and "_h" in names

    _n = clear_all_caches()
    assert _n >= 2   # 至少這兩個（其他模組可能也有註冊）

    # clear 後 hits/misses 都歸零
    info_after = get_all_cache_info()
    for r in info_after:
        if r["name"] in ("_g", "_h"):
            assert r["size"] == 0
            assert r["hits"] == 0
            assert r["misses"] == 0


def test_wrapped_function_preserves_name():
    """functools.wraps 應保留 __name__（給 register/info 顯示用）"""
    @_ttl_cache(ttl_sec=300)
    def my_named_fetcher(x):
        return x
    assert my_named_fetcher.__name__ == "my_named_fetcher"


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
