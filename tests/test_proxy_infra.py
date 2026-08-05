"""test_proxy_infra.py — infra/proxy.py 新增 API 測試（v18.115 B-A）

涵蓋 B-A 收口到 infra/proxy.py 的新公開介面：
- _proxies() / _ssl_verify() — convenience wrappers
- install_global_urllib_proxy() — 全域 urllib opener hook（mock urllib.request.install_opener）
- fund_fetcher / fund_repository 的 re-export 確實能拿到 callable
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
import requests   # QA 條件 1/3 新測需要 requests.exceptions.Timeout 模擬混合失敗

from infra import proxy as ip


@pytest.fixture(autouse=True)
def _fresh_thread_session():
    """v19.333 F6:fetch_url 改用 thread-local session 複用後,
    patch make_retry_session 需先清本執行緒快取才會生效;
    測後再清,避免 _FakeSess 殘留污染後續測試。"""
    ip._TLS_HTTP.__dict__.clear()
    yield
    ip._TLS_HTTP.__dict__.clear()


# ════════════════════════════════════════════════════════════
# _proxies / _ssl_verify — 依賴 get_proxy_config 結果
# ════════════════════════════════════════════════════════════
def test_proxies_returns_empty_dict_when_no_config():
    with patch.object(ip, "get_proxy_config", return_value=None):
        assert ip._proxies() == {}


def test_proxies_returns_dict_when_config_present():
    cfg = {"http": "http://x:y@h:3128", "https": "http://x:y@h:3128"}
    with patch.object(ip, "get_proxy_config", return_value=cfg):
        assert ip._proxies() == cfg


def test_ssl_verify_true_when_no_proxy():
    """無 proxy 模式 → 正常驗證 SSL（True）。"""
    with patch.object(ip, "get_proxy_config", return_value=None):
        assert ip._ssl_verify() is True


def test_ssl_verify_false_when_proxy_enabled():
    """proxy 模式 → 跳過 SSL（False，Squid CONNECT 相容）。"""
    with patch.object(ip, "get_proxy_config", return_value={"http": "x"}):
        assert ip._ssl_verify() is False


# ════════════════════════════════════════════════════════════
# install_global_urllib_proxy
# ════════════════════════════════════════════════════════════
def test_install_global_urllib_proxy_no_config_marks_done():
    """無 proxy config → 不呼叫 install_opener，但標記 installed 避免反覆讀 secrets。"""
    # 重置 module-level flag
    ip._URLLIB_OPENER_INSTALLED = False
    with patch.object(ip, "get_proxy_config", return_value=None), \
         patch("urllib.request.install_opener") as mock_install:
        ip.install_global_urllib_proxy()
        assert mock_install.call_count == 0
    assert ip._URLLIB_OPENER_INSTALLED is True
    # 重置以免影響其他測試
    ip._URLLIB_OPENER_INSTALLED = False


def test_install_global_urllib_proxy_with_config_installs_opener():
    """有 proxy config → 呼叫 install_opener 一次。"""
    ip._URLLIB_OPENER_INSTALLED = False
    cfg = {"http": "http://x:y@h:3128", "https": "http://x:y@h:3128"}
    with patch.object(ip, "get_proxy_config", return_value=cfg), \
         patch("urllib.request.install_opener") as mock_install:
        ip.install_global_urllib_proxy()
        assert mock_install.call_count == 1
    assert ip._URLLIB_OPENER_INSTALLED is True
    ip._URLLIB_OPENER_INSTALLED = False


def test_install_global_urllib_proxy_idempotent():
    """已標記 installed → 第二次呼叫直接 return，零副作用。"""
    ip._URLLIB_OPENER_INSTALLED = True
    with patch.object(ip, "get_proxy_config") as mock_cfg, \
         patch("urllib.request.install_opener") as mock_install:
        ip.install_global_urllib_proxy()
        assert mock_cfg.call_count == 0
        assert mock_install.call_count == 0
    ip._URLLIB_OPENER_INSTALLED = False


# ════════════════════════════════════════════════════════════
# Re-export 對齊：fund_fetcher / fund_repository 拿到相同 callable
# ════════════════════════════════════════════════════════════
def test_fund_fetcher_reexports_same_callables_as_infra_proxy():
    import fund_fetcher
    assert fund_fetcher._proxies is ip._proxies
    assert fund_fetcher._ssl_verify is ip._ssl_verify
    assert fund_fetcher.get_proxy_config is ip.get_proxy_config
    assert fund_fetcher.reset_proxy_cache is ip.reset_proxy_cache


def test_fund_repository_has_proxies_and_ssl_verify_in_namespace():
    """B-A 之前 fund_repository 內 30+ 處用 _proxies()/_ssl_verify() 但沒 import
    → NameError 隱藏 bug。B-A 後從 infra.proxy 直接 import，namespace 應該齊全。

    v19.235 R1:shim repositories/fund_repository.py 已刪,改驗 sub-package
    repositories.fund namespace。"""
    from repositories import fund as fr
    assert hasattr(fr, "_proxies") and callable(fr._proxies)
    assert hasattr(fr, "_ssl_verify") and callable(fr._ssl_verify)


# ════════════════════════════════════════════════════════════
# fetch_url_with_retry MoneyDJ-specific behavior
# ════════════════════════════════════════════════════════════
class _FakeResp:
    def __init__(self, text: str = "<html>淨值 100</html>", status: int = 200):
        self.text = text
        self.status_code = status
        self.encoding = None
        self.apparent_encoding = "utf-8"


def test_fetch_url_with_retry_sets_big5_for_moneydj():
    """MoneyDJ URL → encoding 強制 big5。"""
    import fund_fetcher
    with patch.object(ip, "fetch_url", return_value=_FakeResp()) as mock_fu:
        resp = fund_fetcher.fetch_url_with_retry(
            "https://www.moneydj.com/funddj/yp/yp010000.djhtm?a=ACDD",
        )
    assert resp is not None
    assert resp.encoding == "big5"
    # Referer 應被自動帶上
    headers_passed = mock_fu.call_args.kwargs.get("headers", {})
    assert "Referer" in headers_passed
    assert "moneydj.com" in headers_passed["Referer"]


def test_fetch_url_with_retry_uses_apparent_encoding_for_non_moneydj():
    """非 MoneyDJ URL → encoding 用 apparent_encoding。"""
    import fund_fetcher
    fake = _FakeResp()
    fake.apparent_encoding = "utf-8"
    with patch.object(ip, "fetch_url", return_value=fake):
        resp = fund_fetcher.fetch_url_with_retry(
            "https://api.cnyes.com/fund/api/v2/funds/search?key=ACDD",
        )
    assert resp.encoding == "utf-8"


def test_fetch_url_with_retry_none_on_empty_body():
    """空 body → 回 None（避免上層拿到空頁面誤判 success）。"""
    import fund_fetcher
    fake = _FakeResp(text="   ")
    with patch.object(ip, "fetch_url", return_value=fake):
        resp = fund_fetcher.fetch_url_with_retry("https://www.moneydj.com/x")
    assert resp is None


def test_fetch_url_with_retry_none_when_infra_returns_none():
    """infra fetch_url 回 None（407/全失敗）→ 也回 None。"""
    import fund_fetcher
    with patch.object(ip, "fetch_url", return_value=None):
        resp = fund_fetcher.fetch_url_with_retry("https://www.moneydj.com/x")
    assert resp is None


def test_fetch_url_with_retry_custom_headers_merge():
    """caller 傳 headers 應 merge 到 default（不覆蓋）。"""
    import fund_fetcher
    captured = {}

    def _capture(url, **kw):
        captured.update(kw)
        return _FakeResp()

    with patch.object(ip, "fetch_url", side_effect=_capture):
        fund_fetcher.fetch_url_with_retry(
            "https://www.moneydj.com/x",
            headers={"X-Custom": "yes"},
        )
    sent_headers = captured.get("headers", {})
    assert sent_headers.get("X-Custom") == "yes"
    assert "Referer" in sent_headers  # default 沒被蓋掉


def test_fund_repository_fx_nav_use_chart_api_not_direct_yfinance():
    """v18.201：fund_repository 的 FX/NAV 改走 Yahoo Chart API（fetch_yf_close +
    NAS proxy），不再直連 yf.Ticker（避免 Cloud IP 403/限流）。整檔掃描，最穩。

    B1 v19.205 / P1-5:repositories/fund_repository.py 已拆 repositories/fund/ 子套件,
    改讀整個子套件 concat。
    """
    import pathlib
    src = "\n".join(p.read_text(encoding="utf-8")
                    for p in sorted(pathlib.Path("repositories/fund").glob("*.py")))
    assert "yf.Ticker" not in src, "fund_repository 不應再直連 yf.Ticker"
    assert src.count("fetch_yf_close") >= 2, "FX + NAV 應都走 fetch_yf_close（Chart API）"


def test_fund_repository_has_re_and_requests_module_imported():
    """v18.203：re / requests 必須在 fund_repository 模組層 import — 原本缺，導致
    多處 HTML 解析（re.findall）與 requests.get fetch 路徑被呼叫時 NameError→靜默失敗。"""
    import fund_fetcher  # noqa: F401  先載解 circular
    import repositories.fund as fr
    assert getattr(fr, "re", None) is not None, "fund_repository 缺 import re"
    assert getattr(fr, "requests", None) is not None, "fund_repository 缺 import requests"


# ════════════════════════════════════════════════════════════
# v18.278 — fetch_url 429 rate-limit exponential backoff
# ════════════════════════════════════════════════════════════
class _StatusResp:
    """Mock requests.Response with controllable status_code only."""
    def __init__(self, status):
        self.status_code = status


def test_fetch_url_429_then_200_succeeds_with_backoff_sleeps():
    """429 → 200：第 1 次 429 sleep 2s，第 2 次 200 成功回傳，sleep 序列 = [2.0]。"""
    responses = [_StatusResp(429), _StatusResp(200)]
    sleeps = []

    class _FakeSess:
        def get(self, *a, **kw):
            return responses.pop(0)

    with patch.object(ip, "make_retry_session", return_value=_FakeSess()), \
         patch.object(ip, "get_proxy_config", return_value=None), \
         patch("time.sleep", side_effect=sleeps.append):
        r = ip.fetch_url("https://example.com/x")

    assert r is not None
    assert r.status_code == 200
    assert sleeps == [2.0]


def test_fetch_url_429_exhausts_returns_none_with_full_backoff_sequence():
    """連續 4 個 429：sleep 序列 = [2.0, 4.0, 8.0]，retries=3 額度耗盡 → None。"""
    responses = [_StatusResp(429)] * 6   # 給足 4xx，跑滿外圈 retries 都還是 429
    sleeps = []

    class _FakeSess:
        def get(self, *a, **kw):
            return responses.pop(0)

    with patch.object(ip, "make_retry_session", return_value=_FakeSess()), \
         patch.object(ip, "get_proxy_config", return_value=None), \
         patch("time.sleep", side_effect=sleeps.append):
        r = ip.fetch_url("https://example.com/x", retries=3)

    assert r is None
    # 完整 backoff 序列 = (2.0, 4.0, 8.0)
    assert sleeps == [2.0, 4.0, 8.0]


def test_fetch_url_429_then_200_after_two_retries():
    """三次 retry 才放行：sleep 序列 = [2.0, 4.0]，第 3 次 200。"""
    responses = [_StatusResp(429), _StatusResp(429), _StatusResp(200)]
    sleeps = []

    class _FakeSess:
        def get(self, *a, **kw):
            return responses.pop(0)

    with patch.object(ip, "make_retry_session", return_value=_FakeSess()), \
         patch.object(ip, "get_proxy_config", return_value=None), \
         patch("time.sleep", side_effect=sleeps.append):
        r = ip.fetch_url("https://example.com/x")

    assert r is not None and r.status_code == 200
    assert sleeps == [2.0, 4.0]


def test_fetch_url_429_backoff_constant_is_2_4_8():
    """v18.277 cron job 鎖死的 backoff 序列：infra.proxy 與其對齊，避免漂移。"""
    assert ip._RATE_LIMIT_BACKOFF_SEC == (2.0, 4.0, 8.0)


def test_fetch_url_407_not_affected_by_429_branch():
    """407 Auth 應立即回 None，不進 429 backoff 路徑。"""
    sleeps = []

    class _FakeSess:
        def get(self, *a, **kw):
            return _StatusResp(407)

    with patch.object(ip, "make_retry_session", return_value=_FakeSess()), \
         patch.object(ip, "get_proxy_config", return_value=None), \
         patch("time.sleep", side_effect=sleeps.append):
        r = ip.fetch_url("https://example.com/x")

    assert r is None
    assert sleeps == []   # 不該為 429 sleep


def test_fetch_url_proxy_error_fails_fast_without_sleep():
    """ProxyError = **proxy 本身**連不上 → 立刻降級直連,不 sleep 不重試。

    修正前:每次 ProxyError `sleep(2)` 且重試滿 3 次 = 每個 URL 白等 6 秒。
    NAS proxy 離線時,28 個總經指標 + 逐檔基金抓取累積數分鐘純睡眠;
    `tests/test_app_apptest.py` 的 `_force_network_refused`(刻意把 proxy 指向
    127.0.0.1:9 讓它「快速」失敗)也因此被推過 60s timeout 而整組紅。

    fetch_url docstring 的行為矩陣本來就寫「ProxyError → 降級直連」,
    此測釘住實作與文件一致。對照組:429 是對端限流,sleep 後重試有意義
    (見 test_fetch_url_429_then_200_succeeds_with_backoff_sleeps),
    ProxyError 是中繼站不存在,重試沒有任何狀態會改變。
    """
    sleeps: list = []
    calls: list = []

    class _FakeSess:
        def get(self, *a, **kw):
            calls.append(kw.get("proxies"))
            raise requests.exceptions.ProxyError("Unable to connect to proxy")

    with patch.object(ip, "make_retry_session", return_value=_FakeSess()), \
         patch.object(ip, "get_proxy_config",
                      return_value={"https": "http://127.0.0.1:9"}), \
         patch("time.sleep", side_effect=sleeps.append):
        r = ip.fetch_url("https://example.com/x")

    assert r is None
    assert sleeps == [], f"ProxyError 不該 sleep,實際 sleep 了 {sleeps}"
    # 修正前:3 次 proxy 嘗試 + 1 次降級直連 = 4;修正後:1 + 1 = 2
    assert len(calls) == 2, f"應只嘗試 1 次 proxy + 1 次直連,實際 {len(calls)} 次"
    assert calls[0] == {"https": "http://127.0.0.1:9"}, "第 1 次必須走 proxy"
    assert calls[-1] == {}, "最後一次必須是降級直連(proxies={})"


# ════════════════════════════════════════════════════════════
# 狀態碼黑洞修補 — 402 / 403 / 收尾 log
#
# 原 if 鏈只處理 407 / 403 / 429 / 200，其餘狀態碼（402 額度用盡、401、404、
# 5xx）掉出 if 鏈就進下一輪重試，最後 `return None` 零 log。FinMind 免費額度
# 402 就是走這條路被吞掉的（狀態碼與 API msg 全部遺失，呼叫端只能報「無回應」）。
# ════════════════════════════════════════════════════════════
class _BodyResp:
    """帶 body 的 mock，模擬 FinMind 402 回應。

    ⚠️ `content`（bytes）必須提供：真實 `requests.Response` 一定有這個屬性，而
    infra.proxy 的未預期狀態碼 log 已改讀 bytes（不觸發 apparent_encoding 全文
    編碼偵測、切片後才 decode）。只 stub `text` 的 mock 與真實契約不符。
    """
    def __init__(self, status, text=""):
        self.status_code = status
        self.text = text
        self.content = text.encode("utf-8")


def test_fetch_url_402_logs_status_and_body(capsys):
    """402 額度用盡：狀態碼 + body（含 API msg）都必須出現在 log。"""
    body = '{"msg": "Requests reached the upper limit.", "status": 402}'
    responses = [_BodyResp(402, body)] * 3

    class _FakeSess:
        def get(self, *a, **kw):
            return responses.pop(0)

    with patch.object(ip, "make_retry_session", return_value=_FakeSess()), \
         patch.object(ip, "get_proxy_config", return_value=None):
        r = ip.fetch_url("https://api.finmindtrade.com/api/v4/data")

    out = capsys.readouterr().out
    assert r is None                       # 回傳型別不變（零 caller 需改）
    assert "402" in out, "402 狀態碼必須被 log 出來"
    assert "upper limit" in out, "API msg（body）必須被 log 出來"
    assert "全部嘗試失敗" in out, "收尾必須有 log，不可零輸出 return None"
    assert "status=402" in out, "收尾 log 必須帶最後看到的狀態碼"


def test_fetch_url_404_also_logged_not_silent(capsys):
    """404（dataset 改名 / endpoint 掛掉）同樣不可靜默。"""
    responses = [_BodyResp(404, "not found")] * 3

    class _FakeSess:
        def get(self, *a, **kw):
            return responses.pop(0)

    with patch.object(ip, "make_retry_session", return_value=_FakeSess()), \
         patch.object(ip, "get_proxy_config", return_value=None):
        r = ip.fetch_url("https://example.com/x")

    out = capsys.readouterr().out
    assert r is None
    assert "404" in out and "status=404" in out


def test_fetch_url_403_now_logged(capsys):
    """§2.1 MoneyDJ 子網域 403 fallback chain 是核心情境，原本零 log。"""
    class _FakeSess:
        def get(self, *a, **kw):
            return _StatusResp(403)

    with patch.object(ip, "make_retry_session", return_value=_FakeSess()), \
         patch.object(ip, "get_proxy_config", return_value=None), \
         patch("time.sleep", side_effect=lambda _s: None):
        r = ip.fetch_url("https://www.moneydj.com/funddj/yp/yp010000.djhtm")

    out = capsys.readouterr().out
    assert r is None
    assert "403" in out
    assert "moneydj.com" in out


def test_fetch_url_200_returns_response_without_failure_log(capsys):
    """200 成功路徑不得被新 log 污染（也確認控制流未變）。"""
    class _FakeSess:
        def get(self, *a, **kw):
            return _StatusResp(200)

    with patch.object(ip, "make_retry_session", return_value=_FakeSess()), \
         patch.object(ip, "get_proxy_config", return_value=None):
        r = ip.fetch_url("https://example.com/ok")

    out = capsys.readouterr().out
    assert r is not None and r.status_code == 200
    assert "全部嘗試失敗" not in out
    assert "未預期狀態碼" not in out


# ════════════════════════════════════════════════════════════
# QA 條件 1 — 「加 log 自殘」防護：body 取用不得反噬控制流
#
# 舊寫法 `str(getattr(r, "text", "") or "")[:200]` 的 default **只攔
# AttributeError**，攔不住 property getter 內部拋的例外（stream 中斷 /
# charset_normalizer 解碼例外 / 非標準 Response）。那行在 try 內 → 例外冒泡到
# `except Exception: break`，本該 retry 3 次的路徑立刻中斷，且 _perr/_block/_tmo
# 全 0 → 降級直連條件不成立 → 直接 return None。
# 新寫法讀 `r.content`（bytes，不觸發 apparent_encoding）+ 內層 try 兜底。
# ════════════════════════════════════════════════════════════
class _TextExplodesResp:
    """`.text` property 會拋非 AttributeError；`.content` 正常（真實串流/編碼例外情境）。"""
    def __init__(self, status, content: bytes = b""):
        self.status_code = status
        self.content = content

    @property
    def text(self):
        raise RuntimeError("charset detection blew up mid-stream")


class _BodyFullyUnavailableResp:
    """`.text` 與 `.content` 兩者皆拋 —— 最壞情況也不得影響控制流。"""
    def __init__(self, status):
        self.status_code = status

    @property
    def text(self):
        raise RuntimeError("boom-text")

    @property
    def content(self):
        raise RuntimeError("boom-content")


def test_fetch_url_text_property_exception_does_not_abort_retry_loop(capsys):
    """修正前會紅：`.text` 拋 RuntimeError → 舊碼 break，get 只被呼叫 1 次。

    修正後讀 `.content`，retries=3 全部跑完，body 也照樣進 log。
    """
    calls = {"n": 0}

    class _FakeSess:
        def get(self, *a, **kw):
            calls["n"] += 1
            return _TextExplodesResp(
                402, b'{"msg": "Requests reached the upper limit.", "status": 402}')

    with patch.object(ip, "make_retry_session", return_value=_FakeSess()), \
         patch.object(ip, "get_proxy_config", return_value=None):
        r = ip.fetch_url("https://api.finmindtrade.com/api/v4/data", retries=3)

    out = capsys.readouterr().out
    assert r is None
    assert calls["n"] == 3, "body 取用炸掉不得吃掉 retry 額度（舊碼此處為 1）"
    assert "upper limit" in out, "content 路徑仍應把 API msg log 出來"
    assert "[proxy] Error:" not in out, "不該掉進通用 except（那條會 break）"
    assert "全部嘗試失敗" in out


def test_fetch_url_body_fully_unavailable_still_retries_and_logs(capsys):
    """修正前會紅：`.text` 拋 → break（1 次）。

    修正後 content 也拋時走 `<body unavailable>` 佔位，retry 與收尾 log 完全不受影響。
    """
    calls = {"n": 0}

    class _FakeSess:
        def get(self, *a, **kw):
            calls["n"] += 1
            return _BodyFullyUnavailableResp(500)

    with patch.object(ip, "make_retry_session", return_value=_FakeSess()), \
         patch.object(ip, "get_proxy_config", return_value=None):
        r = ip.fetch_url("https://example.com/x", retries=3)

    out = capsys.readouterr().out
    assert r is None
    assert calls["n"] == 3
    assert "<body unavailable>" in out, "body 抓不到要誠實標示，不可靜默（§1）"
    assert "未預期狀態碼 500" in out
    assert "[proxy] Error:" not in out


def test_fetch_url_body_read_failure_still_allows_direct_fallback(capsys):
    """修正前會紅：`.text` 炸 → break 且 _perr/_block/_tmo 全 0 → **降級直連不觸發**。

    修正後 proxy 逾時計數照常累積，降級直連照常執行（本測以 Timeout 觸發）。
    """
    seq = [_TextExplodesResp(404, b"nope"), requests.exceptions.Timeout()]

    class _FakeSess:
        def __init__(self):
            self.n = 0

        def get(self, *a, **kw):
            # 第 3 次呼叫 = 降級直連（proxies={}）
            if self.n >= len(seq):
                return _BodyResp(200, "ok-direct")
            item = seq[self.n]
            self.n += 1
            if isinstance(item, Exception):
                raise item
            return item

    with patch.object(ip, "make_retry_session", return_value=_FakeSess()), \
         patch.object(ip, "get_proxy_config",
                      return_value={"http": "http://nas:3128", "https": "http://nas:3128"}), \
         patch("time.sleep", side_effect=lambda _s: None):
        r = ip.fetch_url("https://example.com/x", retries=2)

    out = capsys.readouterr().out
    assert "降級直連" in out, "body 取用炸掉不得讓降級直連失效"
    assert r is not None and r.status_code == 200


# ════════════════════════════════════════════════════════════
# QA 條件 2 — log 一律遮罩 query string（資安預防）
#
# 現況 FinMind token / FRED api_key 都走 `params=`，不進 url 字串 → 目前無洩漏；
# 但 fetch_url 是全站 30+ caller 的公用入口，任何未來把 key 塞進 query 的 caller
# 都會把 secret 印進 stdout（Streamlit Cloud log 為 collaborator 可見）。
# ════════════════════════════════════════════════════════════
_SECRET_URL = "https://api.example.com/v4/data?token=SUPERSECRET&dataset=Foo"


def test_fetch_url_unexpected_status_log_masks_query_string(capsys):
    """修正前會紅：`url[:80]` 全長 <80 → SUPERSECRET 原樣印出。"""
    responses = [_BodyResp(402, "quota")] * 3

    class _FakeSess:
        def get(self, *a, **kw):
            return responses.pop(0)

    with patch.object(ip, "make_retry_session", return_value=_FakeSess()), \
         patch.object(ip, "get_proxy_config", return_value=None):
        ip.fetch_url(_SECRET_URL)

    out = capsys.readouterr().out
    assert "SUPERSECRET" not in out and "token=" not in out
    assert "?" not in out.split("body=")[0], "URL 的 query string 不得進 log"
    # 遮罩後仍須保留除錯價值：看得出是哪個 host / path
    assert "https://api.example.com/v4/data" in out


def test_fetch_url_final_log_masks_query_string(capsys):
    """收尾 log（全部嘗試失敗）同樣不得洩漏 query string。修正前會紅。"""
    responses = [_BodyResp(404, "nf")] * 3

    class _FakeSess:
        def get(self, *a, **kw):
            return responses.pop(0)

    with patch.object(ip, "make_retry_session", return_value=_FakeSess()), \
         patch.object(ip, "get_proxy_config", return_value=None):
        ip.fetch_url(_SECRET_URL)

    tail = [ln for ln in capsys.readouterr().out.splitlines() if "全部嘗試失敗" in ln]
    assert tail, "收尾 log 必須存在"
    assert "SUPERSECRET" not in tail[0] and "?" not in tail[0]
    assert "api.example.com" in tail[0]


def test_fetch_url_403_log_masks_query_string(capsys):
    """403 fallback chain log 也要遮罩。修正前會紅。"""
    class _FakeSess:
        def get(self, *a, **kw):
            return _StatusResp(403)

    with patch.object(ip, "make_retry_session", return_value=_FakeSess()), \
         patch.object(ip, "get_proxy_config", return_value=None), \
         patch("time.sleep", side_effect=lambda _s: None):
        ip.fetch_url("https://www.moneydj.com/funddj/yp/yp010000.djhtm?a=ACDD&key=SUPERSECRET")

    out = capsys.readouterr().out
    assert "SUPERSECRET" not in out
    assert "moneydj.com" in out, "遮罩後仍看得出來源 host（除錯價值不減）"


def test_fetch_url_429_giveup_log_masks_query_string(capsys):
    """429 放棄 log 也要遮罩。修正前會紅。"""
    class _FakeSess:
        def get(self, *a, **kw):
            return _StatusResp(429)

    with patch.object(ip, "make_retry_session", return_value=_FakeSess()), \
         patch.object(ip, "get_proxy_config", return_value=None), \
         patch("time.sleep", side_effect=lambda _s: None):
        ip.fetch_url(_SECRET_URL, retries=5)

    out = capsys.readouterr().out
    assert "SUPERSECRET" not in out and "token=" not in out
    assert "api.example.com" in out


# ════════════════════════════════════════════════════════════
# QA 條件 3 — 收尾 log 欄位改 `last_seen_status=`（純措辭，邏輯不動）
#
# `_last_status` 只在 sess.get 有回傳 Response 時更新：attempt 1 拿 404、
# attempt 2 逾時 → 舊 log 印 `status=404, tmo=1`，讀 log 的人會誤判最後一次是 404。
# ════════════════════════════════════════════════════════════
def test_final_log_field_named_last_seen_status(capsys):
    """修正前會紅：舊 log 是「最後 status=404」，無 `last_seen_status=` 字樣。"""
    responses = [_BodyResp(404, "nf")] * 3

    class _FakeSess:
        def get(self, *a, **kw):
            return responses.pop(0)

    with patch.object(ip, "make_retry_session", return_value=_FakeSess()), \
         patch.object(ip, "get_proxy_config", return_value=None):
        ip.fetch_url("https://example.com/x")

    out = capsys.readouterr().out
    assert "last_seen_status=404" in out
    assert "最後 status=" not in out, "舊措辭不得殘留"


def test_final_log_mixed_failure_wording_is_not_misleading(capsys):
    """404 後逾時的混合失敗：同一行同時有狀態碼與 tmo=1，措辭須自證是「最後看到的」。

    修正前會紅（欄位名為 `status=`，讀者會誤判最後一次是 404）。
    """
    seq = [_BodyResp(404, "nf"), requests.exceptions.Timeout()]

    class _FakeSess:
        def __init__(self):
            self.n = 0

        def get(self, *a, **kw):
            item = seq[self.n]
            self.n += 1
            if isinstance(item, Exception):
                raise item
            return item

    with patch.object(ip, "make_retry_session", return_value=_FakeSess()), \
         patch.object(ip, "get_proxy_config", return_value=None), \
         patch("time.sleep", side_effect=lambda _s: None):
        r = ip.fetch_url("https://example.com/x", retries=2)

    tail = [ln for ln in capsys.readouterr().out.splitlines() if "全部嘗試失敗" in ln]
    assert r is None and tail
    assert "last_seen_status=404" in tail[0] and "tmo=1" in tail[0]


def test_proxy_source_has_no_bare_url_slice_in_logs():
    """source-text 鎖：infra/proxy.py 不得再出現未遮罩的 `url[:` log 切片。"""
    import pathlib
    src = pathlib.Path("infra/proxy.py").read_text(encoding="utf-8")
    assert '_url_log = url.split("?")[0]' in src, "缺 query string 遮罩 SSOT"
    assert "{url[:" not in src, "log 不得直接切原始 url（會帶出 query string 內的 secret）"
    # body 取用必須是「bytes 切片後才 decode」——不得回退到會自殘 + 觸發全文編碼偵測的 text 路徑
    assert 'r.content[:200].decode("utf-8", errors="replace")' in src
