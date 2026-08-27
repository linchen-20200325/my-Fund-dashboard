"""tests/test_source_backoff.py — v3 憲法 §02「失敗時退避，不連續轟炸來源」。

## 這組測試要釘死什麼

1. **不轟炸**：來源失敗後，冷卻期內的後續呼叫**一個封包都不發**（假時鐘 + 呼叫計數器）。
2. **§1 Fail Loud 不被破壞**：退避期內回的是 `None`，**不是**上次的值、不是假資料；
   整條 chain 都退避時照樣失敗。
3. **退避不可讓資料長期消失**：冷卻期上限、時鐘走完就自動完整重試、成功即解除、
   「全域刷新」一鍵清空。
4. **分類正確**：404 / 407 **刻意不退避**（否則會打死正常的多候選 URL 探測）。

## 突變測試（本檔的核心，`TestMutation_NoBackoffMeansBlasting`）

拿掉 `infra/proxy.py` 進場的退避檢查 → `test_second_pass_sends_zero_packets`
與 `test_nine_source_race_does_not_reblast_every_rerun` **必須轉紅**，
因為它們斷言的是「第二輪的網路呼叫次數 == 0」，沒有退避時那個數字會等於第一輪。

設計上刻意**不**用 mock 去斷言「有沒有呼叫 should_skip」—— 那種測試只驗到接線，
拿掉實作照樣綠。這裡直接量**真正的可觀測後果：對外送出的請求數**。
"""
from __future__ import annotations

import threading
import time

import pytest
import requests

from infra import cache as ic
from infra import proxy as ip
from infra import source_backoff as sb
from shared import backoff_policy as bp


# ════════════════════════════════════════════════════════════
# 測試替身：假時鐘 + 逐 host 呼叫計數器
# ════════════════════════════════════════════════════════════
class _FakeClock:
    """可手動推進的單調時鐘（注入 `sb._clock`）。

    退避的每一條斷言都是「過了多久」，用真實時間測 = 測試要睡 900 秒。
    """
    def __init__(self, t0: float = 1000.0):
        self.t = float(t0)

    def __call__(self) -> float:
        return self.t

    def advance(self, sec: float) -> None:
        self.t += float(sec)


class _StatusResp:
    def __init__(self, status: int, body: bytes = b"ok"):
        self.status_code = status
        self.content = body
        self.text = body.decode("utf-8", "replace")


class _CountingSession:
    """計算「實際送出幾個請求、送到哪個 host」的假 session。

    這個計數器就是突變測試的量測儀：退避有效 → 第二輪計數不增加；
    退避被拿掉 → 第二輪計數翻倍。
    """
    def __init__(self, behaviour):
        self.calls: list[str] = []
        self._behaviour = behaviour

    def get(self, url, **kw):
        self.calls.append(url)
        _b = self._behaviour(url) if callable(self._behaviour) else self._behaviour
        if isinstance(_b, Exception):
            raise _b
        return _b

    @property
    def n(self) -> int:
        return len(self.calls)

    def hosts(self) -> list[str]:
        from urllib.parse import urlsplit
        return [urlsplit(u).netloc for u in self.calls]


@pytest.fixture
def clock(monkeypatch):
    c = _FakeClock()
    monkeypatch.setattr(sb, "_clock", c)
    sb.reset_all()
    yield c
    sb.reset_all()


@pytest.fixture(autouse=True)
def _no_real_sleep_and_no_proxy(monkeypatch):
    """fetch_url 的重試 sleep 與 proxy 讀取在單元測試裡都不該真的發生。"""
    monkeypatch.setattr(time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(ip, "get_proxy_config", lambda: None)
    ip._TLS_HTTP.__dict__.clear()
    yield
    ip._TLS_HTTP.__dict__.clear()


def _install(monkeypatch, session) -> None:
    monkeypatch.setattr(ip, "make_retry_session", lambda: session)
    ip._TLS_HTTP.__dict__.clear()


# ════════════════════════════════════════════════════════════
# 1. 突變測試核心：沒有退避 = 連續轟炸
# ════════════════════════════════════════════════════════════
class TestMutation_NoBackoffMeansBlasting:
    """⚠️ 拿掉 `infra/proxy.py` fetch_url 進場的退避檢查，本類**必須**全紅。"""

    def test_second_pass_sends_zero_packets(self, monkeypatch, clock):
        """同一來源第二輪：網路呼叫數必須維持 0 增量。"""
        sess = _CountingSession(lambda u: requests.exceptions.Timeout("boom"))
        _install(monkeypatch, sess)

        assert ip.fetch_url("https://slow.example/x") is None
        _first = sess.n
        assert _first > 0, "第一輪本來就該真的打（退避不該影響首次嘗試）"

        # 第二輪：時鐘沒動，仍在冷卻期
        assert ip.fetch_url("https://slow.example/x") is None
        assert sess.n == _first, (
            f"退避失效：第二輪又送出 {sess.n - _first} 個請求 —— "
            f"這就是憲法 §02 所稱的『連續轟炸來源』"
        )

    def test_nine_source_race_does_not_reblast_every_rerun(self, monkeypatch, clock):
        """模擬 TW PMI 9 源賽跑：全敗後，下一次 rerun 不得把 9 個 host 再打一遍。

        這是本 repo 真實的放大器 —— Streamlit **每次互動都 rerun**，
        沒有退避時 9 源 × 每次點擊 = 無上限的重打。
        """
        hosts = [f"https://src{i}.example/pmi" for i in range(9)]
        sess = _CountingSession(lambda u: requests.exceptions.Timeout("down"))
        _install(monkeypatch, sess)

        for u in hosts:
            assert ip.fetch_url(u, retries=1) is None
        _first_round = sess.n
        assert _first_round == 9, "第一輪 9 源各打一次"

        for _rerun in range(5):          # 使用者連點 5 次
            for u in hosts:
                assert ip.fetch_url(u, retries=1) is None
        assert sess.n == _first_round, (
            f"5 次 rerun 多送了 {sess.n - _first_round} 個請求；"
            f"退避生效時應為 0"
        )

    def test_moneydj_chain_skips_sibling_page_types_on_same_host(self, monkeypatch, clock):
        """MoneyDJ 403：同一 host 的下一個 page_type 不該再打（§2.1 fallback chain）。

        403 是 host + 我方 IP 層級的封鎖，換 `yp=` 參數一樣被擋 ——
        退避粒度取 host 就是為了擋掉這一種「換個 query 再試一次」的轟炸。
        """
        sess = _CountingSession(_StatusResp(403))
        _install(monkeypatch, sess)

        base = "https://www.moneydj.com/funddj/yp/yp{pt}.djhtm?a=ACDD01"
        assert ip.fetch_url(base.format(pt="010000")) is None
        _after_first = sess.n
        assert ip.fetch_url(base.format(pt="010001")) is None
        assert sess.n == _after_first, "同 host 的兄弟 page_type 應被退避跳過"


# ════════════════════════════════════════════════════════════
# 2. §1 Fail Loud：退避不是「快取失敗值」
# ════════════════════════════════════════════════════════════
class TestFailLoudPreserved:
    def test_skipped_call_returns_none_not_a_stale_response(self, monkeypatch, clock):
        """先成功拿到 200，再讓來源掛掉 → 退避期內**不得**回上次那個 200。"""
        _mode = {"v": "ok"}
        sess = _CountingSession(
            lambda u: _StatusResp(200, b"REAL") if _mode["v"] == "ok"
            else requests.exceptions.Timeout("down")
        )
        _install(monkeypatch, sess)

        r = ip.fetch_url("https://flip.example/a")
        assert r is not None and r.content == b"REAL"

        _mode["v"] = "down"
        assert ip.fetch_url("https://flip.example/a") is None      # 真失敗 → 進退避
        _n = sess.n
        out = ip.fetch_url("https://flip.example/a")               # 退避期內
        assert out is None, "退避期內必須回 None，絕不可回上次的 Response（那是造假）"
        assert sess.n == _n

    def test_backoff_module_stores_no_payload(self):
        """退避狀態表**只存時間與分類**，不存任何回傳值 —— 結構上不可能造假。"""
        sb.reset_all()
        sb.record_failure("h.example", "blocked")
        state = sb.get_backoff_state()
        assert state and set(state[0]) == {
            "source", "kind", "remaining_sec", "cooldown_sec", "fails"
        }, f"退避狀態多出疑似 payload 的欄位：{state[0]}"
        sb.reset_all()

    def test_whole_chain_backed_off_still_fails_loud(self, monkeypatch, clock):
        """整條 chain 都在冷卻 → 每一段都回 None，chain 尾端照樣失敗（不回假資料）。"""
        chain = [f"https://s{i}.example/nav" for i in range(3)]
        sess = _CountingSession(lambda u: requests.exceptions.Timeout("x"))
        _install(monkeypatch, sess)
        for u in chain:
            ip.fetch_url(u, retries=1)

        results = [ip.fetch_url(u, retries=1) for u in chain]
        assert results == [None, None, None]


# ════════════════════════════════════════════════════════════
# 3. 退避不可讓資料長期消失
# ════════════════════════════════════════════════════════════
class TestBackoffCannotHideDataForever:
    def test_all_cooldowns_within_hard_cap(self):
        """任何冷卻期都不得超過上限（本 repo 最快來源為 Yahoo EOD 日頻，§2.3）。"""
        for kind, sec in bp.BACKOFF_COOLDOWN_SEC.items():
            assert 0 <= sec <= bp.BACKOFF_MAX_COOLDOWN_SEC, kind
        assert bp.BACKOFF_MAX_COOLDOWN_SEC == 1800

    def test_cooldown_values_are_ssot_locked(self):
        """漂移鎖：數值改動必須是**有意識的**，連帶更新 backoff_policy 的理由表。"""
        assert bp.BACKOFF_UNREACHABLE_SEC == 60
        assert bp.BACKOFF_SERVER_ERROR_SEC == 300
        assert bp.BACKOFF_BLOCKED_SEC == 900
        assert bp.BACKOFF_RATE_LIMITED_SEC == 1800

    def test_server_error_cooldown_equals_ttl_5min(self):
        """刻意與既有 `TTL_5MIN` 同值：退避不可讓資料比快取層本就允許的更舊。"""
        from shared.ttls import TTL_5MIN
        assert bp.BACKOFF_SERVER_ERROR_SEC == TTL_5MIN

    def test_full_retry_after_cooldown_expires(self, monkeypatch, clock):
        sess = _CountingSession(lambda u: requests.exceptions.Timeout("x"))
        _install(monkeypatch, sess)
        ip.fetch_url("https://t.example/a", retries=1)
        _n = sess.n
        clock.advance(bp.BACKOFF_UNREACHABLE_SEC - 1)
        ip.fetch_url("https://t.example/a", retries=1)
        assert sess.n == _n, "冷卻期尚未走完，不該重打"
        clock.advance(2)
        ip.fetch_url("https://t.example/a", retries=1)
        assert sess.n == _n + 1, "冷卻期走完必須完整重試"

    def test_no_exponential_escalation(self, clock):
        """連續失敗只刷新同一段冷卻期，**不會越退越久**（防資料被無限期藏起來）。"""
        for _ in range(5):
            assert sb.record_failure("e.example", "unreachable") == bp.BACKOFF_UNREACHABLE_SEC
        assert sb.get_backoff_state()[0]["fails"] == 5      # 次數仍如實記錄（可觀測）

    def test_success_clears_backoff_immediately(self, monkeypatch, clock):
        _mode = {"v": "down"}
        sess = _CountingSession(
            lambda u: requests.exceptions.Timeout("x") if _mode["v"] == "down"
            else _StatusResp(200)
        )
        _install(monkeypatch, sess)
        ip.fetch_url("https://r.example/a", retries=1)
        assert sb.get_backoff_state()
        clock.advance(bp.BACKOFF_UNREACHABLE_SEC + 1)
        _mode["v"] = "ok"
        assert ip.fetch_url("https://r.example/a", retries=1) is not None
        assert sb.get_backoff_state() == [], "成功後必須立刻解除退避"

    def test_success_during_cooldown_clears_backoff(self, monkeypatch, clock):
        """冷卻期**內**成功一次（診斷探測走 bypass）→ 必須立刻解封，不必等冷卻走完。

        ⚠️ 這條是補洞來的：原本只有 `test_success_clears_backoff_immediately`，
        它先把時鐘推過冷卻期才成功 —— 那時 entry 已被 `should_skip` 的到期清理
        移除，所以**把 `record_success` 整條拿掉、測試照樣全綠**（突變存活）。
        真正只有 `record_success` 能過的路徑，是「還在冷卻期內拿到 200」。
        """
        _mode = {"v": "down"}
        sess = _CountingSession(
            lambda u: requests.exceptions.Timeout("x") if _mode["v"] == "down"
            else _StatusResp(200)
        )
        _install(monkeypatch, sess)
        ip.fetch_url("https://rec.example/a", retries=1)
        assert sb.should_skip("rec.example")[0] is True

        _mode["v"] = "ok"                      # 來源復活，但冷卻期還沒走完
        clock.advance(1)
        assert ip.fetch_url("https://rec.example/a", retries=1,
                            bypass_backoff=True) is not None
        assert sb.should_skip("rec.example")[0] is False, (
            "冷卻期內確認來源已恢復，卻沒解除退避 —— 退避變成單向鎖，"
            "會把『已經好了的來源』繼續藏著（違反「退避不可讓資料長期消失」）"
        )

    def test_direct_fallback_success_also_clears_backoff(self, monkeypatch, clock):
        """降級直連成功也算來源活著 —— 否則「proxy 被擋、直連可用」的常態會被自己鎖死。"""
        _seen = {"n": 0}

        def _behave(url, **kw):
            _seen["n"] += 1
            return _StatusResp(403) if _seen["n"] <= 2 else _StatusResp(200)

        sess = _CountingSession(_behave)
        _install(monkeypatch, sess)
        monkeypatch.setattr(ip, "get_proxy_config", lambda: {"http": "http://p:3128",
                                                             "https": "http://p:3128"})
        # ⚠️ 必須先讓該 host 已在退避中,這條測試才驗得到東西 —— 否則
        # `get_backoff_state() == []` 會因為「本來就沒有 entry」而恆真（突變存活）。
        sb.record_failure("dc.example", "blocked")
        r = ip.fetch_url("https://dc.example/a", bypass_backoff=True)
        assert r is not None and r.status_code == 200
        assert sb.get_backoff_state() == [], "降級直連成功後仍留著退避 = 自己把自己鎖死"

    def test_global_refresh_clears_backoff(self, clock):
        """逃生門：sidebar「全域刷新」→ clear_all_caches() → 退避全清。"""
        sb.record_failure("g.example", "rate_limited")
        assert sb.should_skip("g.example")[0] is True
        ic.clear_all_caches()
        assert sb.should_skip("g.example")[0] is False

    def test_registered_in_cache_registry_for_observability(self, clock):
        """§5：退避狀態出現在既有的快取狀態表（Tab5 泛型渲染，零 UI 改動）。"""
        sb.record_failure("obs.example", "blocked")
        names = [i.get("name") for i in ic.get_all_cache_info()]
        assert "_SOURCE_BACKOFF" in names
        row = [i for i in ic.get_all_cache_info() if i.get("name") == "_SOURCE_BACKOFF"][0]
        assert row["currsize"] == 1
        assert row["backing_off"] == ["obs.example"]

    def test_uses_monotonic_clock_not_wall_clock(self):
        """NTP 校時 / 手動改系統時間不得讓來源提早解封或永遠鎖死。"""
        assert sb._clock is time.monotonic


# ════════════════════════════════════════════════════════════
# 4. 失敗分類
# ════════════════════════════════════════════════════════════
class TestFailureClassification:
    def test_404_does_not_back_off(self, monkeypatch, clock):
        """404 = 來源活著且明確回答 → URL 的問題，不是來源的問題。

        反例保護：`tw_pmi_repository._pmi_src_cier_en_monthly` 刻意輪 3 個月份
        slug，**舊月份 404 是正常流程**；若 404 退避整個 host，等於打死該來源。
        """
        sess = _CountingSession(_StatusResp(404))
        _install(monkeypatch, sess)
        ip.fetch_url("https://www.cier.edu.tw/en/eco/pmi-july-2026/", retries=1)
        assert sb.get_backoff_state() == []
        _n = sess.n
        ip.fetch_url("https://www.cier.edu.tw/en/eco/pmi-june-2026/", retries=1)
        assert sess.n == _n + 1, "同 host 的下一個候選 slug 必須照打"

    def test_407_does_not_back_off_source(self, monkeypatch, clock):
        """407 = 我方 proxy 帳密錯，請求沒到來源 → 罰來源是罰錯人。"""
        sess = _CountingSession(_StatusResp(407))
        _install(monkeypatch, sess)
        assert ip.fetch_url("https://any.example/a") is None
        assert sb.get_backoff_state() == []

    def test_403_classified_blocked(self, monkeypatch, clock):
        sess = _CountingSession(_StatusResp(403))
        _install(monkeypatch, sess)
        ip.fetch_url("https://blk.example/a")
        st = sb.get_backoff_state()[0]
        assert st["kind"] == "blocked"
        assert st["cooldown_sec"] == bp.BACKOFF_BLOCKED_SEC

    def test_429_classified_rate_limited(self, monkeypatch, clock):
        sess = _CountingSession(_StatusResp(429))
        _install(monkeypatch, sess)
        ip.fetch_url("https://rl.example/a")
        st = sb.get_backoff_state()[0]
        assert st["kind"] == "rate_limited"
        assert st["cooldown_sec"] == bp.BACKOFF_RATE_LIMITED_SEC

    def test_429_failfast_caller_still_records_source_cooldown(self, monkeypatch, clock):
        """`backoff_on_429=False` 只取消「本次呼叫內 sleep 重試」，不取消來源冷卻。"""
        sess = _CountingSession(_StatusResp(429))
        _install(monkeypatch, sess)
        ip.fetch_url("https://yf.example/a", backoff_on_429=False)
        assert sb.get_backoff_state()[0]["kind"] == "rate_limited"

    def test_5xx_classified_server_error(self, monkeypatch, clock):
        sess = _CountingSession(_StatusResp(503))
        _install(monkeypatch, sess)
        ip.fetch_url("https://s5.example/a", retries=1)
        assert sb.get_backoff_state()[0]["kind"] == "server_error"

    def test_timeout_classified_unreachable(self, monkeypatch, clock):
        sess = _CountingSession(lambda u: requests.exceptions.Timeout("t"))
        _install(monkeypatch, sess)
        ip.fetch_url("https://tm.example/a", retries=1)
        assert sb.get_backoff_state()[0]["kind"] == "unreachable"

    def test_unknown_kind_falls_back_to_shortest_cooldown(self, clock):
        """未知失敗**從寬**：寧可多打一次，也不要把資料藏起來。"""
        assert sb.cooldown_for("something_new") == bp.BACKOFF_UNREACHABLE_SEC

    def test_no_cooldown_kinds_are_explicit(self):
        assert bp.NO_COOLDOWN_KINDS == {"not_found", "proxy_auth"}
        for k in bp.NO_COOLDOWN_KINDS:
            assert sb.cooldown_for(k) == 0


# ════════════════════════════════════════════════════════════
# 5. 邊界 / 韌性（§6 自審：空集、單筆、異常型別、併發）
# ════════════════════════════════════════════════════════════
class TestEdgeCases:
    def test_bypass_backoff_forces_a_real_attempt(self, monkeypatch, clock):
        """診斷路徑要能無視退避逐源探測（介面先備好，本輪無 caller）。"""
        sess = _CountingSession(_StatusResp(403))
        _install(monkeypatch, sess)
        ip.fetch_url("https://dg.example/a")
        _n = sess.n
        ip.fetch_url("https://dg.example/a", bypass_backoff=True)
        assert sess.n > _n

    @pytest.mark.parametrize("bad", ["", "not a url", "://", None, 12345])
    def test_source_key_never_raises(self, bad):
        assert isinstance(sb.source_key(bad), str)

    def test_empty_state_is_clean(self, clock):
        sb.reset_all()
        assert sb.get_backoff_state() == []
        assert sb.should_skip("nobody.example") == (False, 0.0, "")

    def test_tracked_hosts_bounded(self, clock):
        sb.reset_all()
        for i in range(bp.BACKOFF_MAX_TRACKED_HOSTS * 2):
            sb.record_failure(f"h{i}.example", "blocked")
        assert len(sb.get_backoff_state()) <= bp.BACKOFF_MAX_TRACKED_HOSTS

    def test_concurrent_record_failure_is_thread_safe(self, clock):
        """TW PMI 9 源走 ThreadPoolExecutor 並行呼叫 fetch_url。"""
        sb.reset_all()
        errs: list = []

        def _work(i):
            try:
                for _ in range(50):
                    sb.record_failure(f"c{i % 7}.example", "unreachable")
                    sb.should_skip(f"c{i % 7}.example")
                    sb.get_backoff_state()
            except Exception as e:      # pragma: no cover
                errs.append(e)

        ts = [threading.Thread(target=_work, args=(i,)) for i in range(8)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        assert errs == []
        assert len(sb.get_backoff_state()) == 7


# ════════════════════════════════════════════════════════════
# 6. 與 v18.275 positive-only `_FX_CACHE` 的共存（協調者點名的張力）
# ════════════════════════════════════════════════════════════
class TestCoexistWithPositiveOnlyFxCache:
    """v18.275 防的是 **None-poisoning**（失敗值被快取成假答案）；
    退避防的是 **連續轟炸**（每次 rerun 重打整條 chain）。兩者必須同時成立。

    `get_latest_fx` 的 er-api / Frankfurter 兩段 v18.273 起**刻意不走 `fetch_url`**，
    所以在 `repositories/fund/fx_and_main.py` 內手動接上同一套冷卻 —— 本類釘住
    「接上之後 v18.275 一點都沒被推翻」。
    """

    @pytest.fixture
    def fx(self, monkeypatch, clock):
        import fund_fetcher  # noqa: F401  （conftest 已 prime，這裡只求可讀）
        from repositories.fund import fx_and_main as fx
        fx._clear_fx_cache()
        # Yahoo 段（走 fetch_yf_close）一律失敗，把控制權交給 er-api 段
        monkeypatch.setattr(
            "repositories.macro_repository.fetch_yf_close",
            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("yahoo down")),
        )
        yield fx
        fx._clear_fx_cache()

    def test_failed_fx_source_is_not_reblasted_and_cache_stays_empty(
            self, monkeypatch, clock, fx):
        calls = {"n": 0}

        def _fake_get(url, **kw):
            calls["n"] += 1
            return _StatusResp(503)

        monkeypatch.setattr(requests, "get", _fake_get)

        assert fx.get_latest_fx("USDTWD=X") is None
        _n = calls["n"]
        assert _n >= 1, "第一次必須真的打"

        assert fx.get_latest_fx("USDTWD=X") is None
        assert calls["n"] == _n, "退避期內不得重打 er-api"

        # v18.275 核心不變式：失敗**從來沒有**進 cache
        assert fx._FX_CACHE == {}, (
            "退避不得順手把失敗寫進 positive-only cache —— "
            "那正是 v18.275 要防的 None-poisoning"
        )

    def test_success_still_caches_positive_value_and_clears_backoff(
            self, monkeypatch, clock, fx):
        """v18.275 的 positive-only 行為一字未改：成功值照存、照命中。"""
        _mode = {"v": "down"}

        class _Json(_StatusResp):
            def json(self):
                return {"result": "success", "rates": {"TWD": 31.29}}

        def _fake_get(url, **kw):
            if _mode["v"] == "down":
                return _StatusResp(503)
            return _Json(200)

        monkeypatch.setattr(requests, "get", _fake_get)

        assert fx.get_latest_fx("USDTWD=X") is None
        assert sb.get_backoff_state(), "失敗後應進退避"

        clock.advance(bp.BACKOFF_SERVER_ERROR_SEC + 1)
        _mode["v"] = "ok"
        assert fx.get_latest_fx("USDTWD=X") == pytest.approx(31.29)
        assert sb.get_backoff_state() == [], "成功後退避須解除"
        assert list(fx._FX_CACHE.values())[0][1] == pytest.approx(31.29)

    def test_all_sources_backed_off_still_returns_none_not_a_number(
            self, monkeypatch, clock, fx):
        """整條 FX chain 都在冷卻 → 誠實回 None，**不是**任何預設數字（§1）。"""
        monkeypatch.setattr(requests, "get", lambda url, **kw: _StatusResp(503))
        assert fx.get_latest_fx("USDTWD=X") is None
        out = fx.get_latest_fx("USDTWD=X")
        assert out is None and not isinstance(out, (int, float))

    def test_diagnose_fx_sources_is_not_muted_by_backoff(
            self, monkeypatch, clock, fx):
        """Tab5 逐源診斷**刻意不接退避** —— 使用者按下去就是要知道「現在真的通嗎」。

        若診斷也被退避跳過，畫面會顯示「失敗」而其實根本沒打過，那是誤導。
        """
        calls = {"n": 0}

        def _fake_get(url, **kw):
            calls["n"] += 1
            return _StatusResp(503)

        monkeypatch.setattr(requests, "get", _fake_get)
        fx.get_latest_fx("USDTWD=X")          # 先讓 er-api 進退避
        _n = calls["n"]
        fx.diagnose_fx_sources("USDTWD=X")
        assert calls["n"] > _n, "診斷路徑必須實打，不得被退避靜音"
