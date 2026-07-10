"""test_proxy_infra.py — infra/proxy.py 新增 API 測試（v18.115 B-A）

涵蓋 B-A 收口到 infra/proxy.py 的新公開介面：
- _proxies() / _ssl_verify() — convenience wrappers
- install_global_urllib_proxy() — 全域 urllib opener hook（mock urllib.request.install_opener）
- fund_fetcher / fund_repository 的 re-export 確實能拿到 callable
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

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
