"""v19.507:fetch_url 加 backoff_on_429 開關 —— Yahoo 限流時快速跳過,不燒 2/4/8s 退避。

根因(user 2026-08-21 總經載入逾時):8 個 Yahoo 標的每個遇 429 走 14s 退避 = ~56s,
是 75s 逾時主因。限流不會在 14s 內解除 → 重試純白等。Yahoo 端傳 backoff_on_429=False
遇 429 直接回 None(指標誠實留空 §1)。預設 True → 契約/cron 行為不變。
"""
from unittest.mock import patch

from infra import proxy as ip


class _StatusResp:
    def __init__(self, code):
        self.status_code = code
        self.text = "x"


class _FakeSess429:
    def get(self, *a, **kw):
        return _StatusResp(429)


def _fresh():
    ip._TLS_HTTP.__dict__.clear()


def test_429_fail_fast_zero_sleep_when_disabled():
    """backoff_on_429=False:遇 429 立刻回 None、零 sleep。"""
    _fresh()
    sleeps = []
    try:
        with patch.object(ip, "make_retry_session", return_value=_FakeSess429()), \
             patch.object(ip, "get_proxy_config", return_value=None), \
             patch("time.sleep", side_effect=sleeps.append):
            r = ip.fetch_url("https://query1.finance.yahoo.com/x", backoff_on_429=False)
    finally:
        _fresh()
    assert r is None
    assert sleeps == []          # ★ 零退避(原本會 [2,4,8]=14s)


def test_429_default_still_full_backoff():
    """預設 backoff_on_429=True:契約序列 [2,4,8] 不變(cron/其餘來源仍韌性)。"""
    _fresh()
    sleeps = []
    try:
        with patch.object(ip, "make_retry_session", return_value=_FakeSess429()), \
             patch.object(ip, "get_proxy_config", return_value=None), \
             patch("time.sleep", side_effect=sleeps.append):
            r = ip.fetch_url("https://example.com/x", retries=3)
    finally:
        _fresh()
    assert r is None
    assert sleeps == [2.0, 4.0, 8.0]   # 預設行為零改動


def test_yf_close_passes_failfast_and_returns_empty_on_429():
    """fetch_yf_close 對 429 快速回空 Series(不 14s 退避)。"""
    from repositories.macro import yf
    _fresh()
    sleeps = []
    try:
        with patch.object(ip, "make_retry_session", return_value=_FakeSess429()), \
             patch.object(ip, "get_proxy_config", return_value=None), \
             patch("time.sleep", side_effect=sleeps.append):
            s = yf.fetch_yf_close("^VIX")
    finally:
        _fresh()
    assert s is not None and len(s) == 0    # 空 Series(§1 留空,不 fabricate)
    assert sleeps == []                      # Yahoo 端沒燒退避
