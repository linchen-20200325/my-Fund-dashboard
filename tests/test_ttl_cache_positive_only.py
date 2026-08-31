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
    clear_fetch_failed,
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


def test_mark_fetch_failed_rejects_empty_reason():
    """⭐ 2026-08-31 稽核 F5:空 `reason` 曾是**靜默 no-op**,現在必須 raise。

    修復前:`.attrs` 確實被寫入 `""`,但 `is_fetch_failed` 用 `bool()` 判斷 ——
    `bool("")` 為 False → 結果**照樣入快取**。也就是作者寫了標記、以為擋住了,
    實際上什麼都沒發生,而 `mark_fetch_failed` 的 docstring 明寫
    「**刻意 fail loud,不做 silent no-op**」—— 那句話對空 reason 為假。

    這條同時釘住兩件事:(a) 空 reason 會 raise;(b) **raise 之前不留下半套標記**
    (物件不得被改成「有 attrs 但 falsy」那種既不算失敗、又不乾淨的狀態)。
    """
    for bad in ("", "   ", None, 0):
        s = pd.Series([1.0])
        with pytest.raises(ValueError):
            mark_fetch_failed(s, bad)          # type: ignore[arg-type]
        assert FETCH_FAILED_ATTR not in s.attrs, (
            f"reason={bad!r} raise 了,卻仍在 .attrs 留下殘跡 —— "
            f"半套狀態比沒標記更難查"
        )
        assert is_fetch_failed(s) is False


def test_empty_reason_would_have_been_a_silent_noop_without_the_guard():
    """反證 F5 的必要性:**只要繞過那道 ValueError,空 reason 就是靜默 no-op。**

    這條不是在測產品碼,是在把「為什麼要加那道 raise」的理由固化下來 ——
    直接模擬舊行為(直接寫 `.attrs`),證明 `is_fetch_failed` 會回 False、
    `_ttl_cache` 會照樣快取。沒有這條,下一個人可能會覺得那道 raise 太嚴而拿掉。
    """
    calls = {"n": 0}

    @_ttl_cache(ttl_sec=600)
    def fake_fetch(_k):
        calls["n"] += 1
        out = pd.Series(dtype=float)
        out.attrs[FETCH_FAILED_ATTR] = ""     # ← 舊行為:reason 為空
        return out

    fake_fetch("a")
    fake_fetch("a")
    assert calls["n"] == 1, "空 reason 竟然擋住了快取 —— 那 F5 的前提就不成立"
    assert fake_fetch.cache_info()["size"] == 1
    assert fake_fetch.cache_info()["uncached_fail"] == 0, \
        "空 reason 的標記不會被 is_fetch_failed 認出 —— 這正是它是 no-op 的證據"


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


# ── ⭐ 2026-08-31 F1：六種失敗分類逐一釘住「標不標記」的決定 ──────────
#
# **為什麼原本那一條不夠**：`test_failure_retry_is_gated_by_existing_source_backoff`
# 只覆蓋 `unreachable` 一種 —— 而它恰好是「有冷卻期」的那一族。
# `shared/backoff_policy.NO_COOLDOWN_KINDS`（`not_found` 404 / `proxy_auth` 407）
# **冷卻 0 秒**，對它們來說 `_ttl_cache` 是**唯一的節流器**；一律標記成失敗
# ＝ 同時拆掉兩層，每次 rerun 都重打一輪（實測 5 次 rerun：404 由 3 個請求變 15 個、
# 407 由 1 變 5）。單一 kind 的守衛結構上看不到這件事，故改成**六種全參數化**。

_FAIL_KIND_MATRIX = [
    # (kind, 讓 fetch_url 走到那個分類的 HTTP 狀態碼；None = 連線層例外, 應否標記)
    ("unreachable",  None, True),
    ("server_error", 500,  True),
    ("blocked",      403,  True),
    ("rate_limited", 429,  True),
    ("not_found",    404,  False),   # ← NO_COOLDOWN_KINDS
    ("proxy_auth",   407,  False),   # ← NO_COOLDOWN_KINDS
]


def _drive_yf(status, reruns=1):
    """用假 Session 把 `fetch_yf_close` 推到指定 HTTP 狀態碼，回傳 (結果, 實際出門次數)。

    刻意走**完整的 `fetch_url`**（而不是直接 patch `yf.fetch_url` 回 None）——
    本測試要驗的正是「分類 → 標不標記」這整條鏈，patch 掉 `fetch_url` 就等於
    把要驗的東西假設掉了。
    """
    from unittest.mock import patch as _patch
    from infra import proxy as proxy_mod
    from repositories.macro import yf as yf_mod

    class _Resp:
        def __init__(self, code):
            self.status_code = code
            self.content = b'{"chart":{"result":[{}]}}'

    sent = {"n": 0}

    class _Sess:
        @staticmethod
        def get(*_a, **_kw):
            sent["n"] += 1
            if status is None:
                raise RuntimeError("connection refused")   # → unreachable
            return _Resp(status)

    out = None
    with _patch.object(proxy_mod, "_get_thread_session", return_value=_Sess()), \
         _patch.object(proxy_mod, "get_proxy_config", return_value={}):
        for _ in range(reruns):
            out = yf_mod.fetch_yf_close("^VIX")
    return out, sent["n"]


@pytest.mark.parametrize("kind, status, should_mark", _FAIL_KIND_MATRIX,
                         ids=[k for k, _s, _m in _FAIL_KIND_MATRIX])
def test_mark_decision_matches_backoff_policy_for_every_fail_kind(kind, status, should_mark):
    """六種失敗分類，逐一釘住「該不該標記成失敗」。

    契約:**`NO_COOLDOWN_KINDS` 不標記,其餘標記** —— 而且這個判斷必須跟著
    `shared/backoff_policy.py`(SSOT)走,不是在測試裡另寫一份清單。
    """
    from unittest.mock import patch as _patch
    from infra import proxy as proxy_mod
    from infra import source_backoff as sb
    from infra.proxy import pop_last_fail_kind
    from repositories.macro import yf as yf_mod
    from shared.backoff_policy import NO_COOLDOWN_KINDS

    # 期望值直接由 SSOT 推導 —— 若有人改 NO_COOLDOWN_KINDS,本表會跟著變,
    # 不會出現「政策改了測試還綠」的情況。
    assert should_mark == (kind not in NO_COOLDOWN_KINDS), (
        f"本測試的期望表與 shared/backoff_policy.NO_COOLDOWN_KINDS 不一致 —— "
        f"改政策時請一併改這張表(kind={kind})"
    )

    sb.reset_all()
    yf_mod.fetch_yf_close.cache_clear()
    try:
        # ① 先單獨驗**分類**:直接打 fetch_url,自己把值取走。
        #    ⚠️ 刻意與 ② 分開跑 —— `pop_last_fail_kind()` 是取出即清掉的
        #    (理由見該函式 docstring),在 ② 裡讀等於把 fetcher 要用的值搶走。
        _sent_cls = {"n": 0}

        class _Resp:
            def __init__(self, code):
                self.status_code = code
                self.content = b"{}"

        class _S:
            @staticmethod
            def get(*_a, **_kw):
                _sent_cls["n"] += 1
                if status is None:
                    raise RuntimeError("connection refused")
                return _Resp(status)

        with _patch.object(proxy_mod, "_get_thread_session", return_value=_S()), \
             _patch.object(proxy_mod, "get_proxy_config", return_value={}):
            assert proxy_mod.fetch_url("https://q.example.invalid/x",
                                       timeout=1, backoff_on_429=False) is None
        assert pop_last_fail_kind() == kind, (
            f"fetch_url 把這個狀態碼分類錯了,預期 {kind!r} —— "
            f"分類錯了,後面的標記決定一定跟著錯"
        )
        sb.reset_all()

        # ② 再驗**決定**:走完整的 fetch_yf_close。
        out, _sent = _drive_yf(status)
        assert is_fetch_failed(out) is should_mark, (
            f"kind={kind}:標記決定錯了(實際 {is_fetch_failed(out)},預期 {should_mark})"
        )
        _size = yf_mod.fetch_yf_close.cache_info()["size"]
        assert _size == (0 if should_mark else 1), (
            f"kind={kind}:快取狀態與標記決定不一致(size={_size})"
        )
    finally:
        sb.reset_all()
        yf_mod.fetch_yf_close.cache_clear()


@pytest.mark.parametrize("kind, status", [(k, s) for k, s, m in _FAIL_KIND_MATRIX if not m],
                         ids=[k for k, _s, m in _FAIL_KIND_MATRIX if not m])
def test_no_cooldown_kinds_are_throttled_by_the_ttl_cache_alone(kind, status):
    """⭐ `NO_COOLDOWN_KINDS`:**沒有退避可用,所以請求量必須靠 `_ttl_cache` 壓住。**

    這一條是 F1 的核心 —— 它同時斷言三件事:
      ① 這個 kind 確實**沒有進退避**(`get_backoff_state()` 空的,所以不是退避在擋);
      ② 結果**沒有被標記**(＝入了快取);
      ③ 5 次 rerun 的對外請求量**等於**第 1 次的量(＝真的沒有增加)。

    ⚠️ ① 是關鍵:少了它,②③ 在「退避幫忙擋著」的情況下也會通過,
    這條就會變成一個**看起來有守、其實守不到**的測試。
    """
    from infra import source_backoff as sb
    from repositories.macro import yf as yf_mod

    sb.reset_all()
    yf_mod.fetch_yf_close.cache_clear()
    try:
        _out1, n_first = _drive_yf(status, reruns=1)
        assert sb.get_backoff_state() == [], (
            f"kind={kind} 竟然進了退避 —— 它應在 NO_COOLDOWN_KINDS 內。"
            f"本測試的前提(沒有退避可用)不成立,結論無效"
        )
        assert is_fetch_failed(_out1) is False, \
            f"kind={kind} 被標記成失敗 → 不入快取 → 唯一的節流器被拆掉"

        _out5, n_total = _drive_yf(status, reruns=5)
        assert n_total == 0, (
            f"kind={kind}:再打 5 次 rerun 仍對外送出 {n_total} 個請求 —— "
            f"沒有被 _ttl_cache 擋住(第一次是 {n_first} 個)。"
            f"這正是 2026-08-31 稽核量到的 404:3→15 / 407:1→5 那個放大器"
        )
        assert yf_mod.fetch_yf_close.cache_info()["hits"] >= 5, \
            "5 次 rerun 應該全部命中快取"
    finally:
        sb.reset_all()
        yf_mod.fetch_yf_close.cache_clear()


def test_fail_kind_is_consumed_on_read_so_a_stale_value_cannot_leak():
    """⭐ `pop_last_fail_kind()` 必須**取出即清掉**,否則殘值會造成靜默錯誤決定。

    ⚠️ **這條是 2026-08-31 突變測試補出來的缺口**:突變 M-F1e(把 pop 改成
    單純的 getter)當時**48 條全綠**,也就是那個設計決定完全沒有守衛。

    危險情境:某個 fetcher 因條件不成立而**根本沒呼叫 `fetch_url`**,卻仍走到
    失敗分支去問「剛剛是哪一種失敗」→ 讀到同執行緒上一個 fetcher 留下的殘值。
    若那個殘值恰好是 404,**這次的真失敗會被判成「照舊快取」、鎖滿一個 TTL**
    —— 正是本 PR 要修的那個 bug 換一個入口再犯一次。

    取出即清掉之後,沒有對應 `fetch_url` 的讀取一律拿到 `""`,而 `""` 不在
    `NO_COOLDOWN_KINDS` 內 → 落到「標記、不快取」的安全側(fail-safe)。
    """
    from unittest.mock import patch as _patch
    from infra import proxy as proxy_mod
    from infra import source_backoff as sb
    from infra.proxy import pop_last_fail_kind, mark_fetch_failed_if_retryable

    class _Resp:
        status_code = 404
        content = b"{}"

    sb.reset_all()
    try:
        with _patch.object(proxy_mod, "_get_thread_session",
                           return_value=type("S", (), {"get": staticmethod(lambda *a, **k: _Resp())})), \
             _patch.object(proxy_mod, "get_proxy_config", return_value={}):
            assert proxy_mod.fetch_url("https://q.example.invalid/x", timeout=1) is None

        assert pop_last_fail_kind() == "not_found", "第一次讀應拿到本次的分類"
        assert pop_last_fail_kind() == "", (
            "第二次讀仍拿得到值 —— 值沒有被消費掉,殘值會外洩到下一個 fetcher"
        )

        # 端到端:沒有經過 fetch_url 的失敗分支,必須落在安全側(標記、不快取)
        out = mark_fetch_failed_if_retryable(pd.Series(dtype=float), "some other failure")
        assert is_fetch_failed(out) is True, (
            "沒有對應 fetch_url 的呼叫竟然被判成『不用重試』—— "
            "它讀到了殘值,而且是往不安全的方向錯"
        )
    finally:
        sb.reset_all()


def test_retryable_kinds_do_not_get_cached_so_cooldown_expiry_can_recover():
    """對照組:**有冷卻期的四種必須不入快取** —— 否則冷卻過期後拿到的仍是被鎖住的空值。

    這條與上一條是一體兩面:一個守「不該標的別標」,一個守「該標的別漏」。
    只有其中一條時,把判斷寫死成常數(永遠標 / 永遠不標)只會紅一半。
    """
    from infra import source_backoff as sb
    from repositories.macro import yf as yf_mod
    from shared.backoff_policy import NO_COOLDOWN_KINDS

    for kind, status, should_mark in _FAIL_KIND_MATRIX:
        if kind in NO_COOLDOWN_KINDS:
            continue
        sb.reset_all()
        yf_mod.fetch_yf_close.cache_clear()
        try:
            out, _n = _drive_yf(status)
            assert is_fetch_failed(out) is True, f"{kind} 應標記卻沒標"
            assert yf_mod.fetch_yf_close.cache_info()["size"] == 0, \
                f"{kind} 被寫進快取 → 冷卻過期後仍會拿到鎖住的空值"
        finally:
            sb.reset_all()
            yf_mod.fetch_yf_close.cache_clear()


def test_no_cooldown_kinds_are_still_unlockable_by_the_clear_cache_button():
    """§1 對偶:404/407 被快取之後,**使用者不必等 TTL** —— 清快取按鈕真的解得開。

    這條守的是 `mark_fetch_failed_if_retryable` docstring 裡那個逃生口宣稱。
    若某天有人把這三個 fetcher 從 `_CACHE_REGISTRY` 拿掉,按鈕就會失效,
    而「404 照舊快取」的整個正當性建立在這個逃生口上 —— 故必須有測試釘住。
    """
    from infra import source_backoff as sb
    from repositories.macro import yf as yf_mod
    import repositories.macro_repository  # noqa: F401 — 同 UI 按鈕作法,觸發註冊
    from fund_fetcher import clear_all_caches, get_all_cache_info

    sb.reset_all()
    yf_mod.fetch_yf_close.cache_clear()
    try:
        _out, n_first = _drive_yf(404, reruns=2)
        assert yf_mod.fetch_yf_close.cache_info()["size"] == 1, "404 應該入快取"
        assert "fetch_yf_close" in {r.get("name") for r in get_all_cache_info()}, \
            "fetch_yf_close 不在 _CACHE_REGISTRY 內 → 清快取按鈕清不到它"

        clear_all_caches()
        assert yf_mod.fetch_yf_close.cache_info()["size"] == 0, "按鈕沒清掉這一層"

        _out2, n_after = _drive_yf(404, reruns=1)
        assert n_after > 0, "清完之後沒有真的重打上游 → 逃生口是假的"
    finally:
        sb.reset_all()
        yf_mod.fetch_yf_close.cache_clear()


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


# ══════════════════════════════════════════════════════════════
# 6. ⭐ `.attrs` 傳播（2026-08-31 獨立稽核 F1）
#    這一組守的不是「今天壞了」,是「明天有人踩到」——
#    它防的是一種**不會自己叫**的病:新函式繼承了上游的失敗標記 →
#    永遠不入快取 → 每次重抓 → 答案仍然正確,只是安靜地變慢。
#    沒有任何既有測試會因為它變紅,所以必須專門釘一條。
# ══════════════════════════════════════════════════════════════

def _clean_series():
    return pd.Series([1.0, 2.0], index=pd.to_datetime(["2024-01-01", "2024-01-02"]))


def _marked_series():
    s = pd.Series([3.0, 4.0], index=pd.to_datetime(["2024-01-01", "2024-01-02"]))
    return mark_fetch_failed(s, "upstream down")


# ⚠️ 版本判定：`requirements.txt` 宣告 `pandas>=2.3.3,<3.0`，CI 與 production
#    用 2.x；開發沙箱可能是 3.x。二元運算的傳播語意**兩版不同**，故本節依實際
#    載入的版本分支斷言 —— **刻意不寫成「兩邊都過」**，那會讓這組測試失去意義。
_PANDAS_MAJOR = int(pd.__version__.split(".")[0])
_IS_PANDAS_3PLUS = _PANDAS_MAJOR >= 3


@pytest.mark.parametrize("label, op", [
    ("copy",        lambda m: m.copy()),
    ("dropna",      lambda m: m.dropna()),
    ("to_frame",    lambda m: m.to_frame()),
    ("sort_index",  lambda m: m.sort_index()),
    ("islice",      lambda m: m.iloc[:1]),
    ("rename",      lambda m: m.rename("x")),
    ("scalar_mul",  lambda m: m * 2),
    ("marked_left", lambda m: m + _clean_series()),
])
def test_derived_operations_propagate_the_mark_on_all_supported_pandas(label, op):
    """⚠️ 這一組在 **pandas 2.3.3 與 3.0.5 實測皆傳播** —— 硬斷言，不分版本。

    **它證明「衍生函式會繼承標記」的風險在目前宣告的 2.x 就存在**，
    不是「升到 3.x 才會活過來」。`clear_fetch_failed` 的存在理由就在這裡。
    """
    assert is_fetch_failed(op(_marked_series())) is True, (
        f"{label}: 標記未被繼承 —— 若 pandas 改了語意，"
        f"infra/cache.py 的傳播段需同步更正"
    )


def test_binary_op_with_marked_on_the_right_is_version_dependent():
    """⚠️ **唯一的版本差異點**，故依版本分支斷言。

    - pandas 2.x：只從**左**運算元繼承 `.attrs` → `乾淨 + 被標記` **不**傳播
    - pandas 3.x：兩邊都繼承 → **傳播**

    這條紅了代表 pandas 改了語意 —— **那正是它該做的事**，
    請同步更正 `infra/cache.py` 的傳播段，不要把它改成兩邊都過。
    """
    got = is_fetch_failed(_clean_series() + _marked_series())
    if _IS_PANDAS_3PLUS:
        assert got is True, (
            f"pandas {pd.__version__}: 預期 3.x 會從右運算元繼承標記，實得 {got}"
        )
    else:
        assert got is False, (
            f"pandas {pd.__version__}: 預期 2.x **不**從右運算元繼承標記，實得 {got}"
        )


@pytest.mark.parametrize("label, op", [
    ("combine_first", lambda m, c: m.combine_first(c)),
    ("fillna",        lambda m, c: m.fillna(c)),
    ("where",         lambda m, c: m.where(m > 3, c)),
])
def test_merge_ops_keep_the_mark_when_the_marked_one_is_the_caller(label, op):
    """⚠️ **合併類操作看誰是 caller** —— `self` 那側的 attrs 勝出。兩版皆然。

    這條是補上第一版漏掉的那個方向。第一版只斷言了
    `乾淨.combine_first(標記) is False`（安全的那向），就在註解裡寫成
    「combine_first 會清掉標記」的通則 —— **錯在安全方向**：
    會讓作者以為用了 combine_first 就不必叫 `clear_fetch_failed`。
    """
    assert is_fetch_failed(op(_marked_series(), _clean_series())) is True, (
        f"{label}: 被標記者作為 caller 時標記應保留"
    )


@pytest.mark.parametrize("label, op", [
    ("combine_first", lambda m, c: c.combine_first(m)),
    ("fillna",        lambda m, c: c.fillna(m)),
])
def test_merge_ops_drop_the_mark_when_the_marked_one_is_the_argument(label, op):
    """同一組操作的另一個方向：被標記者只是**參數**時，標記被丟掉。兩版皆然。"""
    assert is_fetch_failed(op(_marked_series(), _clean_series())) is False, (
        f"{label}: 被標記者作為參數時標記應被丟掉"
    )


def test_fallback_chain_shape_inherits_the_mark_even_when_fallback_succeeded():
    """⚠️ 本 repo fallback chain 的**真實形狀**，也是這整段註解最要緊的實例。

    `primary.combine_first(fallback)` 是 §2.1 多源備援的標準寫法。
    主源失敗、備源成功時：**值是對的（備援確實生效），卻仍帶著失敗標記**
    → 那個正確的結果永遠不會入快取。這是效能病，不會有畫面出錯。
    """
    idx = pd.to_datetime(["2024-01-01", "2024-01-02"])
    primary_failed = mark_fetch_failed(pd.Series(dtype=float), "primary down")
    fallback_ok = pd.Series([9.0, 9.5], index=idx)

    merged = primary_failed.combine_first(fallback_ok)

    assert list(merged) == [9.0, 9.5], "備援沒生效，這個測試的前提就不成立"
    assert is_fetch_failed(merged) is True, (
        "fallback chain 不再繼承標記 —— 若 pandas 改了語意，"
        "infra/cache.py 的合併類操作段需同步更正"
    )
    # 逃生門要能救回它
    assert is_fetch_failed(clear_fetch_failed(merged)) is False


def test_concat_and_frame_construction_drop_the_mark_in_both_orders():
    """真正會清掉標記的操作 —— **兩種順序都量過**，兩版一致。

    它們沒有一個享有特權的 `self`，故一律不繼承。
    """
    c = _clean_series()
    assert is_fetch_failed(pd.concat([c, _marked_series()])) is False
    assert is_fetch_failed(pd.concat([_marked_series(), c])) is False
    assert is_fetch_failed(pd.DataFrame({"a": c, "b": _marked_series()})) is False
    assert is_fetch_failed(pd.DataFrame({"a": _marked_series(), "b": c})) is False


def test_parquet_roundtrip_keeps_attrs_but_csv_does_not(tmp_path):
    """⚠️ 反直覺：parquet 往返**保留** `.attrs`，CSV 不會 —— 兩版實測一致。

    本 repo 的凍結快照走 parquet（§5 可重現性），所以這件事會踩到。
    """
    df = _marked_series().to_frame(name="v")
    assert is_fetch_failed(df) is True

    pq = tmp_path / "t.parquet"
    try:
        df.to_parquet(pq)
    except Exception as e:                       # pyarrow 缺席的環境
        pytest.skip(f"parquet 引擎不可用: {type(e).__name__}")
    assert is_fetch_failed(pd.read_parquet(pq)) is True, "parquet 不再保留 attrs"

    csv = tmp_path / "t.csv"
    df.to_csv(csv)
    assert is_fetch_failed(pd.read_csv(csv, index_col=0)) is False


def test_clear_fetch_failed_is_the_escape_hatch():
    """module 註解叫新函式呼叫它 —— 它得真的有用。

    ⚠️ 這裡用 `marked * 2`（**兩版都會傳播**）而不是 `clean + marked`
    （2.x 不傳播）—— 前一版就是踩了這個坑，在 CI 的 2.x 上整條失去意義。
    """
    derived = _marked_series() * 2
    assert is_fetch_failed(derived) is True          # 繼承了不屬於自己的失敗
    out = clear_fetch_failed(derived)
    assert out is derived
    assert is_fetch_failed(out) is False

    # 對沒有 attrs 的東西是 no-op、不 raise（與 mark_fetch_failed 刻意不對稱）
    for obj in ({}, [], None, 42, "x"):
        assert clear_fetch_failed(obj) is obj


def test_derived_function_that_clears_the_mark_still_gets_cached():
    """把 module 註解描述的那個坑與它的解法，端到端跑一次。

    同上，用 `marked * 2` 這種**兩版都會傳播**的寫法當示範。
    """
    calls = {"n": 0}

    @_ttl_cache(ttl_sec=600)
    def derived_bad(_k):                              # 沒表態 → 繼承標記
        calls["n"] += 1
        return _marked_series() * 2

    derived_bad("a")
    derived_bad("a")
    assert calls["n"] == 2, "示範用例本身失效了：它應該要繼承標記而不入快取"

    calls2 = {"n": 0}

    @_ttl_cache(ttl_sec=600)
    def derived_good(_k):                             # 明確表態
        calls2["n"] += 1
        return clear_fetch_failed(_marked_series() * 2)

    derived_good("a")
    derived_good("a")
    assert calls2["n"] == 1, "clear_fetch_failed 沒有解除繼承來的標記"


# ══════════════════════════════════════════════════════════════
# 7. ⭐ AST 靜態掃描:回傳 pandas 的 @_ttl_cache 函式只有那 3 個
#    新增第 4 個就紅燈,強迫作者回去讀 infra/cache.py 的傳播警告。
# ══════════════════════════════════════════════════════════════

# 這三個是**已經被 mark_fetch_failed 標記、且確認不從被標記上游衍生**的。
_MARKED_PANDAS_TTL_FUNCS = {
    "fetch_yf_close",
    "fetch_fred",
    "fetch_defillama_stablecoin_mcap",
}


def _ttl_cache_decorator_names(tree):
    """這個模組裡，哪些名字實際綁到了 `_ttl_cache`？

    ⚠️ **2026-08-31 稽核 F4 修**：原本用 `"_ttl_cache" in ast.dump(d)` 比對，
    `from fund_fetcher import _ttl_cache as _tc` 之後寫 `@_tc(...)` **掃不到**
    （實測綠燈通過）。改為先讀模組的 import 別名，再用名字比對。
    """
    import ast
    names = {"_ttl_cache"}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for a in node.names:
                if a.name.split(".")[-1] == "_ttl_cache":
                    names.add(a.asname or a.name.split(".")[-1])
    return names


def _returns_pandas(node, deco_names):
    """這個函式看起來會回傳 pandas 嗎？**兩條線索取聯集**。

    ① 回傳型別註解含 `pd.` / `Series` / `DataFrame`（原本只看這一條）；
    ② 函式體內任一 `return` 敘述提到 `pd.Series` / `pd.DataFrame` /
       `Series(` / `DataFrame(`。

    ⚠️ **2026-08-31 稽核 F4 修**：原本只看 ①，於是「**不寫回傳註解**」就能
    整個繞過守衛（實測綠燈通過）。加上 ② 之後，這個繞道要成立必須同時
    不寫註解、且 return 敘述裡不出現任何 pandas 字樣（例如
    `out = pd.Series(...)` 之後 `return out`）—— **仍然做得到，見下方
    測試 docstring 對涵蓋範圍的誠實描述。**
    """
    import ast
    if not any(isinstance(d, ast.Name) and d.id in deco_names
               or isinstance(d, ast.Call) and isinstance(d.func, ast.Name)
               and d.func.id in deco_names
               or isinstance(d, ast.Attribute) and d.attr in deco_names
               or isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute)
               and d.func.attr in deco_names
               for d in node.decorator_list):
        return None
    if node.returns is not None:
        ret = ast.unparse(node.returns)
        if "pd." in ret or "DataFrame" in ret or "Series" in ret:
            return ret
    for sub in ast.walk(node):
        if isinstance(sub, ast.Return) and sub.value is not None:
            src = ast.unparse(sub.value)
            if ("pd.Series" in src or "pd.DataFrame" in src
                    or "Series(" in src or "DataFrame(" in src):
                return f"<return 敘述推定> {src[:60]}"
    return None


def _ttl_cached_defs_returning_pandas():
    """AST 掃全 repo,找出所有 `@_ttl_cache`(含 import 別名)且**看起來**回傳 pandas 的函式。

    刻意用 AST 而非 import + registry:registry 只含「已被 import 的模組」,
    測試若只 import 一部分就會少算 —— 那種漏算會讓守衛安靜失效。
    """
    import ast
    import pathlib

    root = pathlib.Path(__file__).resolve().parent.parent
    found = []
    for py in root.rglob("*.py"):
        rel = py.relative_to(root)
        if rel.parts[0] in {"tests", ".git"}:
            continue
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        deco_names = _ttl_cache_decorator_names(tree)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            ret = _returns_pandas(node, deco_names)
            if ret is not None:
                found.append((str(rel), node.name, ret))
    return found


@pytest.mark.parametrize("label, src, fn_name", [
    ("不寫回傳註解",
     "import pandas as pd\n"
     "from fund_fetcher import _ttl_cache\n"
     "@_ttl_cache(ttl_sec=60)\n"
     "def bypass_no_annotation(x):\n"
     "    return pd.Series(dtype=float)\n",
     "bypass_no_annotation"),
    ("裝飾器別名 import",
     "import pandas as pd\n"
     "from fund_fetcher import _ttl_cache as _tc\n"
     "@_tc(ttl_sec=60)\n"
     "def bypass_alias(x) -> pd.Series:\n"
     "    return pd.Series(dtype=float)\n",
     "bypass_alias"),
])
def test_scanner_catches_the_two_known_bypasses(label, src, fn_name):
    """⭐ 2026-08-31 稽核 F4:把兩個**實測繞得過**的寫法釘成回歸測試。

    修復前的掃描器對這兩種都是綠的:
      · 只看 `node.returns`,**不寫回傳註解**就整個看不見;
      · 用 `"_ttl_cache" in ast.dump(d)` 比對,`import ... as _tc` 之後
        `@_tc(...)` 比不到。

    ⚠️ **這條守的是掃描器自己的涵蓋範圍**,不是產品行為 —— 因為
    `test_only_the_three_marked_functions_return_pandas_from_ttl_cache`
    在**修好與沒修好時都是綠的**(白名單集合不變),它結構上抓不到自己的漏洞。
    ⚠️ **實證**:2026-08-31 突變 M-F4a / M-F4b(把掃描器改回舊版)在**只有那條
    白名單斷言**時是 **48 passed 全綠**的 —— 少了本條,掃描器退化不會有任何測試變紅。
    """
    import ast
    tree = ast.parse(src)
    deco_names = _ttl_cache_decorator_names(tree)
    target = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == fn_name)
    assert _returns_pandas(target, deco_names) is not None, (
        f"繞道「{label}」沒被抓到 —— 掃描器退回舊版了"
    )


def test_scanner_honestly_admits_what_it_cannot_catch():
    """反向釘:**掃描器抓不到的那一種,要真的抓不到。**

    docstring 明列了「`out = pd.Series(...)` 之後 `return out`」抓不到。
    這條把那句話固化成測試 —— 若哪天有人把掃描器加強到抓得到了,
    本條會紅,提醒他**回去把 docstring 的涵蓋範圍一起改**。
    否則就會出現「程式已加強、文件還在自認很弱」或反過來的漂移。
    """
    import ast
    src = ("import pandas as pd\n"
           "from fund_fetcher import _ttl_cache\n"
           "@_ttl_cache(ttl_sec=60)\n"
           "def hidden(x):\n"
           "    out = pd.Series(dtype=float)\n"
           "    return out\n")
    tree = ast.parse(src)
    target = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == "hidden")
    assert _returns_pandas(target, _ttl_cache_decorator_names(tree)) is None, (
        "掃描器現在抓得到『先賦值再 return』了 —— 這是好事,"
        "但請一併更新它 docstring 的『仍然抓不到』清單,別讓兩者漂移"
    )


def test_only_the_three_marked_functions_return_pandas_from_ttl_cache():
    """守住 `infra/cache.py` 傳播警告所依賴的那個前提。

    它今天成立(回 pandas 的恰好就是被標記的那 3 個),所以沒有下游會繼承標記。

    ⚠️ **這條紅了不代表新函式有錯** —— 它只代表「需要有人判斷一次」。
    確認過不從被標記上游衍生(或已呼叫 clear_fetch_failed)之後,
    把名字加進 `_MARKED_PANDAS_TTL_FUNCS` 即可。

    ## ⚠️ 涵蓋範圍：**這是靜態啟發式，不是完備守衛**（2026-08-31 稽核 F4 更正）

    ~~新增第 4 個就紅燈。~~ **那句是絕對句,實測不成立**,已就地更正
    (**有意識的更正,不是漏刪** · 日期 2026-08-31 · 決策者:AI 總管)。
    **舊表述想表達的意圖仍然成立**(這條確實是為了逼作者判斷一次),
    錯的是它把一個啟發式寫成保證。

    **抓得到**:
      · `@_ttl_cache(...)` 與 `@<import 別名>(...)`(F4 修,原本別名繞得過);
      · 有 pandas 回傳註解的;
      · 沒有註解、但 `return` 敘述裡出現 `pd.Series` / `pd.DataFrame` 的
        (F4 修,原本沒註解就整個看不見)。

    **仍然抓不到(誠實列出,不假裝窮舉)**:
      · `out = pd.Series(...)` … `return out` —— 註解與 return 敘述都不含
        pandas 字樣(型別推導才看得出來,AST 做不到);
      · 動態裝飾(`f = _ttl_cache(...)(f)`)、`getattr` / 條件式套用裝飾器;
      · 回傳 pandas 但包在 tuple / dict 裡的(例:`fetch_usdtwd_series` 回
        `tuple[pd.DataFrame, str]` —— 它走 `@st.cache_data` 不在本掃描範圍,
        但同型寫法若走 `@_ttl_cache` 一樣掃不到);
      · 從別的模組 re-export 進來、在本模組沒有 `def` 的。

    → **這條紅了要處理;它綠不代表沒有第 4 個。** 真正的保證只能靠 code review。
    """
    found = _ttl_cached_defs_returning_pandas()
    names = {name for _f, name, _r in found}
    assert names == _MARKED_PANDAS_TTL_FUNCS, (
        f"回傳 pandas 的 @_ttl_cache 函式集合變了。\n"
        f"實際: {sorted(names)}\n預期: {sorted(_MARKED_PANDAS_TTL_FUNCS)}\n"
        f"完整清單: {found}\n"
        f"→ 請先讀 infra/cache.py 的「.attrs 傳播」段,確認新函式的值"
        f"不是從被標記的上游算出來的(若是,回傳前呼叫 clear_fetch_failed)。"
    )


def test_the_three_are_actually_marked_in_source():
    """反向釘:那三個必須真的呼叫了 `mark_fetch_failed`。

    防的是「有人把標記拿掉、卻忘了把名字移出上面的白名單」——
    那會讓白名單從守衛退化成一張沒人維護的清單。
    """
    import ast
    import pathlib

    root = pathlib.Path(__file__).resolve().parent.parent
    srcs = {
        "fetch_yf_close": root / "repositories" / "macro" / "yf.py",
        "fetch_fred": root / "repositories" / "macro" / "fred.py",
        "fetch_defillama_stablecoin_mcap": root / "repositories" / "macro" / "alternate.py",
    }
    for fn_name, path in srcs.items():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        target = next(
            (n for n in ast.walk(tree)
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
             and n.name == fn_name),
            None,
        )
        assert target is not None, f"{path.name} 找不到 {fn_name}"
        # ⚠️ 用 AST 找**呼叫節點**，不是純文字 `"mark_fetch_failed(" in text`。
        # 後者會被 docstring / 註解裡提到的函式名餵成假陰性（今天三檔都沒有，
        # 但那是運氣不是保證），而假陰性在這裡的意思是「標記被拿掉了卻沒人叫」。
        # 2026-08-31 F1:三個 fetcher 改呼叫 `mark_fetch_failed_if_retryable`
        # (依失敗分類決定要不要標記,404/407 照舊快取)。兩個名字都算數 ——
        # 白名單守的是「這個函式有沒有在失敗分支表態」,不是「用了哪一個 API」。
        _MARK_APIS = {"mark_fetch_failed", "mark_fetch_failed_if_retryable"}
        called = any(
            isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id in _MARK_APIS
            for n in ast.walk(target)
        )
        assert called, (
            f"{fn_name} 函式體內已無 {' / '.join(sorted(_MARK_APIS))} 呼叫,"
            f"但它仍列在 _MARKED_PANDAS_TTL_FUNCS 白名單裡"
        )
