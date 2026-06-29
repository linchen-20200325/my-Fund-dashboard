"""v19.250 R20 regression test — _daily_cache decorator(保存當日 / 隔日 miss 重抓)。

對齊 _ttl_cache 行為:
- cache_clear / cache_info SSOT 對稱
- 不可 hash 引數 bypass
- 同日 cache hit / 隔日 miss
- GC 舊日 entry(memory bound)
"""
from __future__ import annotations


def test_daily_cache_hit_within_day():
    """同 today 重複呼叫 → cache hit,fn 只跑 1 次。"""
    from infra.cache import _daily_cache

    call_count = [0]

    @_daily_cache(today_fn=lambda: "2026-06-29")
    def expensive(x: int) -> int:
        call_count[0] += 1
        return x * 2

    assert expensive(5) == 10
    assert expensive(5) == 10
    assert expensive(5) == 10
    assert call_count[0] == 1, "同日 3 次 call 應只 hit 1 次 fn"
    info = expensive.cache_info()
    assert info["hits"] == 2 and info["misses"] == 1


def test_daily_cache_miss_next_day():
    """隔日 today_fn 變化 → cache miss → 重抓。"""
    from infra.cache import _daily_cache

    call_count = [0]
    today_state = ["2026-06-29"]

    @_daily_cache(today_fn=lambda: today_state[0])
    def fetch_holdings(code: str) -> dict:
        call_count[0] += 1
        return {"code": code, "version": call_count[0]}

    out1 = fetch_holdings("ACCP138")
    assert out1["version"] == 1

    # 同日重複 → hit
    assert fetch_holdings("ACCP138")["version"] == 1

    # 隔日 → miss
    today_state[0] = "2026-06-30"
    out2 = fetch_holdings("ACCP138")
    assert out2["version"] == 2, "隔日應 miss 重抓 → version 遞增"
    assert call_count[0] == 2


def test_daily_cache_gc_old_day_entries():
    """隔日首次呼叫:GC 前一日 entry,memory bound 確保。"""
    from infra.cache import _daily_cache

    today_state = ["2026-06-29"]

    @_daily_cache(today_fn=lambda: today_state[0])
    def fetch(code: str) -> str:
        return code

    # Day 1:塞 3 codes
    fetch("A"); fetch("B"); fetch("C")
    assert fetch.cache_info()["currsize"] == 3

    # Day 2:首次呼叫應 GC 舊日 entry,只留新 entry
    today_state[0] = "2026-06-30"
    fetch("X")
    info = fetch.cache_info()
    assert info["currsize"] == 1, \
        f"隔日首呼後應只剩當日 entry,實際 {info['currsize']}"


def test_daily_cache_unhashable_args_bypass():
    """list/dict 引數 → 跳過 cache(對齊 _ttl_cache 行為)。"""
    from infra.cache import _daily_cache

    call_count = [0]

    @_daily_cache
    def lookup(filters: dict) -> int:
        call_count[0] += 1
        return len(filters)

    lookup({"x": 1})
    lookup({"x": 1})
    lookup({"x": 1})
    assert call_count[0] == 3, "dict 不可 hash → 每次重跑"


def test_daily_cache_clear_and_info_api():
    """cache_clear / cache_info API 對齊 _ttl_cache。"""
    from infra.cache import _daily_cache

    @_daily_cache(today_fn=lambda: "2026-06-29")
    def fn(x): return x

    fn(1); fn(2); fn(1)
    info1 = fn.cache_info()
    assert info1["currsize"] == 2
    assert info1["ttl"] == "daily-reset"
    assert "name" in info1

    fn.cache_clear()
    info2 = fn.cache_info()
    assert info2["currsize"] == 0


def test_daily_cache_registers_with_global_clear():
    """@register_cache + @_daily_cache 連動 — clear_all_caches() 應清。"""
    from infra.cache import _daily_cache, register_cache, clear_all_caches

    @register_cache
    @_daily_cache(today_fn=lambda: "2026-06-29")
    def some_fetcher(x): return x * 10

    some_fetcher(7)
    assert some_fetcher.cache_info()["currsize"] == 1

    cleared = clear_all_caches()
    assert cleared >= 1
    # cache should now be empty
    info = some_fetcher.cache_info()
    assert info["currsize"] == 0


def test_fetch_holdings_uses_daily_cache():
    """v19.250 R20 整合守 — fetch_holdings 應透過 _daily_cache 裝飾(R20 migration 目標)。"""
    import fund_fetcher  # noqa: F401
    from repositories.fund.nav_metrics import fetch_holdings
    info = fetch_holdings.cache_info()
    assert info["ttl"] == "daily-reset", \
        f"fetch_holdings 應走 _daily_cache(ttl=daily-reset),實際 {info['ttl']}"


def test_ttl_today_marker_exists():
    """v19.250 R20 SSOT 一致性 — shared.ttls 應 export TTL_TODAY marker。"""
    from shared.ttls import TTL_TODAY
    assert TTL_TODAY == "daily-reset", \
        f"TTL_TODAY marker 字串應對齊 _daily_cache cache_info[ttl],實際 {TTL_TODAY!r}"
