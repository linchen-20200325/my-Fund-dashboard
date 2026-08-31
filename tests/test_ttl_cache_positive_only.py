"""tests/test_ttl_cache_positive_only.py — v3 憲法 §02「只快取成功結果」守衛。

## 這組測試守的是什麼

`infra/cache.py::_ttl_cache` 原本在 `fn()` 回傳後**無條件**寫入快取。而 L1 fetcher
的慣例是「失敗 → 回空 Series / 空 DataFrame」,於是**一次上游瞬斷會把空值鎖住
整個 TTL** —— 使用者看到總經盤面空白,而且分不出「抓不到」與「真的沒有」。

## ⚠️ 最重要的一條:第 3 組(真的沒有 vs 抓失敗)

前兩組(失敗不入 / 成功照入)只證明「會過濾」;**第 3 組證明「不會過度過濾」**。
「空」有兩種意思、回傳值長得一模一樣,若讓裝飾器用 `len(result) == 0` 去猜,
會把 FRED 明說「該區間沒有觀測」也當成失敗 → 每次呼叫都重打來源(v3 §02
另一半「不連續轟炸」)。**這一組是本檔存在的理由,不是補充。**

## 突變自證

每條斷言都經過「把修復拿掉必須轉紅燈」實跑(v3 §03-1 突變測試要求),
結果列在本次 PR 描述。
"""
from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest

from infra.cache import (
    _ttl_cache,
    is_fetch_failed,
    mark_fetch_failed,
    FETCH_FAILED_ATTR,
)


# ══════════════════════════════════════════════════════════════
# 1. 標記機制本身
# ══════════════════════════════════════════════════════════════

def test_mark_and_read_back_on_series():
    """標記掛得上、讀得回,且**不改變回傳值本身**(型別 / 內容 / 空與否)。"""
    s = pd.Series(dtype=float, name="x")
    out = mark_fetch_failed(s, "boom")
    assert out is s, "應回傳同一個物件,讓 fetcher 可以 `return mark_fetch_failed(...)`"
    assert is_fetch_failed(out) is True
    assert out.attrs[FETCH_FAILED_ATTR] == "boom"
    # 呼叫端讀的是這些,一個都不能被標記影響
    assert isinstance(out, pd.Series) and out.empty and len(out) == 0


def test_mark_works_on_dataframe():
    df = pd.DataFrame()
    assert is_fetch_failed(mark_fetch_failed(df, "boom")) is True
    assert df.empty, "標記不得改變 DataFrame 內容"


def test_unmarked_objects_are_treated_as_success():
    """未標記 = 成功。這是既有 `_ttl_cache` 使用者零行為改變的保證。"""
    for obj in (pd.Series(dtype=float), pd.DataFrame(), {}, [], None, 0, "x"):
        assert is_fetch_failed(obj) is False, f"{obj!r} 未標記卻被當成失敗"


def test_mark_fetch_failed_raises_on_unmarkable_type():
    """無法承載標記時**必須 fail loud**,不得 silent no-op。

    靜默失敗會讓作者以為自己擋住了失敗快取、實際什麼都沒發生 ——
    那正是本次要修的那種假象(§-2「沒查證的宣稱比沒有宣稱更危險」)。
    """
    for bad in ({}, [], "str", 42, None):
        with pytest.raises(TypeError, match="無法承載失敗標記"):
            mark_fetch_failed(bad, "boom")


# ══════════════════════════════════════════════════════════════
# 2. 裝飾器:失敗不入快取 / 成功照常入快取
# ══════════════════════════════════════════════════════════════

def test_failed_result_is_not_cached_and_next_call_really_retries():
    """失敗不入快取,而且下次呼叫**真的重跑 fn**(不是只有 cache dict 是空的)。"""
    calls = {"n": 0}

    @_ttl_cache(ttl_sec=600)
    def f(_k):
        calls["n"] += 1
        return mark_fetch_failed(pd.Series(dtype=float), "upstream down")

    f("a")
    f("a")
    f("a")
    assert calls["n"] == 3, f"失敗結果被快取了,fn 只跑了 {calls['n']} 次"
    assert f.cache_info()["size"] == 0
    assert f.cache_info()["uncached_fail"] == 3


def test_success_after_failure_is_cached():
    """瞬斷恢復後,成功值要能正常入快取(不能因為修了失敗就連成功都不快取)。"""
    calls = {"n": 0}

    @_ttl_cache(ttl_sec=600)
    def f(_k):
        calls["n"] += 1
        if calls["n"] == 1:
            return mark_fetch_failed(pd.Series(dtype=float), "transient")
        return pd.Series([1.0, 2.0])

    r1 = f("a")
    assert r1.empty
    r2 = f("a")
    assert len(r2) == 2
    r3 = f("a")
    assert len(r3) == 2
    assert calls["n"] == 2, "成功值沒有入快取,第 3 次又重跑了"
    assert f.cache_info()["hits"] == 1


def test_unmarked_empty_result_still_cached_backward_compat():
    """未標記的空結果照舊快取 —— 既有 `_ttl_cache` 使用者行為零改變。"""
    calls = {"n": 0}

    @_ttl_cache(ttl_sec=600)
    def f(_k):
        calls["n"] += 1
        return pd.Series(dtype=float)

    f("a")
    f("a")
    assert calls["n"] == 1, "未標記的結果不該被過濾"
    assert f.cache_info()["size"] == 1


def test_cache_clear_resets_uncached_fail_counter():
    @_ttl_cache(ttl_sec=600)
    def f(_k):
        return mark_fetch_failed(pd.Series(dtype=float), "x")

    f("a")
    assert f.cache_info()["uncached_fail"] == 1
    f.cache_clear()
    assert f.cache_info()["uncached_fail"] == 0


# ══════════════════════════════════════════════════════════════
# 3. ⭐「真的沒有資料」與「抓失敗」被分開對待
#    —— 本檔最重要的一組,證明裝飾器**不會過度過濾**
# ══════════════════════════════════════════════════════════════

def test_genuinely_empty_and_fetch_failure_are_distinguished():
    """兩者回傳值**完全一樣**,只有標記不同,而快取行為必須相反。

    若有人把修復寫成「空的就不要快取」,這條會紅 —— 那正是要擋的誤修。
    """
    empty_ok = pd.Series(dtype=float, name="x")          # 真的沒有:來源明說沒資料
    empty_fail = pd.Series(dtype=float, name="x")        # 抓失敗:連回應都沒拿到
    mark_fetch_failed(empty_fail, "fetch_url returned None")

    # 前提:兩者作為「值」無法分辨
    assert empty_ok.empty and empty_fail.empty
    assert len(empty_ok) == len(empty_fail) == 0
    assert list(empty_ok) == list(empty_fail)

    calls = {"ok": 0, "fail": 0}

    @_ttl_cache(ttl_sec=600)
    def genuinely_empty(_k):
        calls["ok"] += 1
        return pd.Series(dtype=float, name="x")

    @_ttl_cache(ttl_sec=600)
    def fetch_failed(_k):
        calls["fail"] += 1
        return mark_fetch_failed(pd.Series(dtype=float, name="x"), "down")

    for _ in range(3):
        genuinely_empty("a")
        fetch_failed("a")

    assert calls["ok"] == 1, "「真的沒有」被當成失敗 → 每次呼叫都重打來源(轟炸)"
    assert calls["fail"] == 3, "「抓失敗」被快取 → 整個 TTL 拿不到資料"


def test_fred_empty_observations_is_cached_but_fetch_failure_is_not():
    """真 fetcher 版的第 3 組:FRED 回 200 + `observations: []` 是**答案**,要快取;
    `fetch_url` 回 None 是**抓失敗**,不快取。"""
    from repositories.macro import fred as fred_mod

    fred_mod.fetch_fred.cache_clear()
    calls = {"n": 0}

    class _Resp:
        status_code = 200

        @staticmethod
        def json():
            return {"observations": []}      # FRED 明說:該區間沒有觀測

    def _side_effect(_url, **_kw):
        calls["n"] += 1
        return _Resp()

    with patch.object(fred_mod, "fetch_url", side_effect=_side_effect):
        a = fred_mod.fetch_fred("EMPTYSER", "k")
        b = fred_mod.fetch_fred("EMPTYSER", "k")
    assert a.empty and b.empty
    assert calls["n"] == 1, "「FRED 明說沒有」被當成失敗 → 每次都重打 FRED"

    # 對照組:同樣回空 DataFrame,但這次是抓失敗
    fred_mod.fetch_fred.cache_clear()
    calls2 = {"n": 0}

    def _fail(_url, **_kw):
        calls2["n"] += 1
        return None

    with patch.object(fred_mod, "fetch_url", side_effect=_fail):
        c = fred_mod.fetch_fred("DOWNSER", "k")
        d = fred_mod.fetch_fred("DOWNSER", "k")
    assert c.empty and d.empty
    assert calls2["n"] == 2, "抓失敗被快取,下次沒有重試"


# ══════════════════════════════════════════════════════════════
# 4. 三個 fetcher 的實地行為
# ══════════════════════════════════════════════════════════════

def _fake_ok(payload):
    class _R:
        status_code = 200

        @staticmethod
        def json():
            return payload
    return _R()


def test_fetch_yf_close_failure_not_cached_then_recovers():
    from repositories.macro import yf as yf_mod

    yf_mod.fetch_yf_close.cache_clear()
    calls = {"n": 0}
    ok = {"chart": {"result": [{
        "timestamp": [1704067200, 1704153600],
        "indicators": {"quote": [{"close": [100.0, 101.0]}]},
    }]}}

    def _side_effect(_url, **_kw):
        calls["n"] += 1
        return None if calls["n"] == 1 else _fake_ok(ok)

    with patch.object(yf_mod, "fetch_url", side_effect=_side_effect):
        r1 = yf_mod.fetch_yf_close("^VIX")
        assert r1.empty and is_fetch_failed(r1)
        r2 = yf_mod.fetch_yf_close("^VIX")
    assert len(r2) == 2, "瞬斷後沒有重試,拿到的還是被快取的空序列"
    assert calls["n"] == 2


def test_fetch_yf_close_parse_failure_is_deliberately_still_cached():
    """HTTP 200 但內容壞掉 → **刻意仍快取**,不是漏掉。

    來源活著且明確回答了,再要一次是同一份壞回應 —— 重抓不會變好,
    只會每次呼叫多打一次來源。這條把「刻意」釘成契約,
    免得後人看到「有個失敗分支沒標記」就順手補上去。
    """
    from repositories.macro import yf as yf_mod

    yf_mod.fetch_yf_close.cache_clear()
    calls = {"n": 0}

    def _side_effect(_url, **_kw):
        calls["n"] += 1
        return _fake_ok({"chart": {"result": None}})     # 壞 ticker 的真實形狀

    with patch.object(yf_mod, "fetch_url", side_effect=_side_effect):
        a = yf_mod.fetch_yf_close("BADTICKER")
        b = yf_mod.fetch_yf_close("BADTICKER")
    assert a.empty and b.empty
    assert is_fetch_failed(a) is False, "解析失敗不應被標記為抓失敗"
    assert calls["n"] == 1, "解析失敗改成不快取了 → 每次呼叫都會重打來源"


def test_fetch_defillama_failure_not_cached():
    from repositories.macro import alternate as alt_mod

    alt_mod.fetch_defillama_stablecoin_mcap.cache_clear()
    calls = {"n": 0}
    ok = [
        {"date": "1704067200", "totalCirculatingUSD": {"peggedUSD": 1.3e11}},
        {"date": "1704153600", "totalCirculatingUSD": {"peggedUSD": 1.31e11}},
    ]

    def _side_effect(_url, **_kw):
        calls["n"] += 1
        return None if calls["n"] == 1 else _fake_ok(ok)

    with patch.object(alt_mod, "fetch_url", side_effect=_side_effect):
        s1 = alt_mod.fetch_defillama_stablecoin_mcap()
        assert s1.empty and is_fetch_failed(s1)
        s2 = alt_mod.fetch_defillama_stablecoin_mcap()
    assert len(s2) == 2
    assert calls["n"] == 2


# ══════════════════════════════════════════════════════════════
# 5. ⭐ 與既有來源退避的組合
#    「失敗不快取」不得退化成「連續轟炸來源」(v3 §02 的另一半)
# ══════════════════════════════════════════════════════════════

def test_failure_retry_is_gated_by_existing_source_backoff():
    """失敗不入快取 → 下次會重試;但那個重試會先撞上 `infra.source_backoff`
    的來源冷卻而**根本不發請求**,所以不會轟炸來源。

    這條證明本次**沒有新造退避** —— 用的是 repo 既有的那一套
    (`infra/proxy.py::fetch_url` 進場先問 `should_skip()`)。
    """
    from infra import source_backoff as sb
    from infra import proxy as proxy_mod

    sb.reset_all()
    sent = {"n": 0}

    class _Sess:
        @staticmethod
        def get(*_a, **_kw):
            sent["n"] += 1
            raise RuntimeError("connection refused")   # → unreachable → 60s 冷卻

    try:
        with patch.object(proxy_mod, "_get_thread_session", return_value=_Sess()):
            first = proxy_mod.fetch_url("https://example.invalid/a", timeout=1, retries=1)
            after_first = sent["n"]
            # 冷卻期內再打同一個 host（含 chain 上換 path 的那種轟炸）
            second = proxy_mod.fetch_url("https://example.invalid/a", timeout=1, retries=1)
            third = proxy_mod.fetch_url("https://example.invalid/b", timeout=1, retries=1)

        assert first is None and second is None and third is None
        assert after_first >= 1, "第一次應該真的有出門"
        assert sent["n"] == after_first, (
            f"冷卻期內仍發出請求({sent['n']} > {after_first})— 來源退避沒有生效,"
            f"『失敗不快取』會變成連續轟炸來源"
        )
        # 冷卻是「不發請求」,不是「記住失敗值」——§1 Fail Loud 不變
        state = sb.get_backoff_state()
        assert state and state[0]["source"] == "example.invalid"
        assert not any(k in state[0] for k in ("value", "payload", "result")), \
            "退避狀態不得存放任何回傳值"
    finally:
        sb.reset_all()


def test_backoff_cooldown_expiry_really_retries():
    """冷卻過期後**必須真的重試** —— 退避不可讓資料永遠消失(§1 的對偶)。"""
    from infra import source_backoff as sb

    sb.reset_all()
    fake_now = {"t": 1000.0}
    orig_clock = sb._clock
    try:
        sb._clock = lambda: fake_now["t"]
        key = "example.invalid"
        cooldown = sb.record_failure(key, "unreachable")
        assert cooldown > 0

        skip, remaining, kind = sb.should_skip(key)
        assert skip is True and kind == "unreachable" and remaining > 0

        fake_now["t"] += cooldown - 1        # 還差 1 秒
        assert sb.should_skip(key)[0] is True, "冷卻未到期就放行"

        fake_now["t"] += 2                   # 過期
        assert sb.should_skip(key)[0] is False, "冷卻過期後沒有恢復 → 資料會永遠消失"
    finally:
        sb._clock = orig_clock
        sb.reset_all()
