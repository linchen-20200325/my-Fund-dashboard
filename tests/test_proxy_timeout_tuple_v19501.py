"""v19.501 §2:fetch_url 把 scalar timeout 拆成 (connect, read) tuple。

proxy 半死時 20s TCP 握手太久(user 2026-08-21 總經載入卡 10 分鐘的放大器之一)。
握手 5s 快速失敗→轉降級直連,read 保留完整秒數。呼叫端傳入值全部沿用。
"""
from unittest.mock import patch

from infra import proxy as ip


class _FakeResp:
    status_code = 200
    text = "ok"
    encoding = "utf-8"
    apparent_encoding = "utf-8"


class _FakeSess:
    def __init__(self, rec):
        self._rec = rec

    def get(self, url, **kw):
        self._rec.append(kw.get("timeout"))
        return _FakeResp()


def _capture_timeout(passed_timeout):
    ip._TLS_HTTP.__dict__.clear()
    rec: list = []
    try:
        with patch.object(ip, "make_retry_session", return_value=_FakeSess(rec)), \
             patch.object(ip, "get_proxy_config", return_value=None):
            ip.fetch_url("https://example.com/x", timeout=passed_timeout)
    finally:
        ip._TLS_HTTP.__dict__.clear()
    assert rec, "sess.get 應被呼叫至少一次"
    return rec[0]


def test_timeout_20_splits_to_5_20():
    assert _capture_timeout(20) == (5, 20)      # 握手 5s,read 20s


def test_timeout_15_splits_to_5_15():
    assert _capture_timeout(15) == (5, 15)


def test_timeout_below_5_keeps_read_equal_connect():
    # timeout=3 → min(5,3)=3 → (3,3);不放大 read
    assert _capture_timeout(3) == (3, 3)


def test_tuple_timeout_passthrough_unchanged():
    # 已是 tuple → 原樣傳(不重複包裝)
    ip._TLS_HTTP.__dict__.clear()
    rec: list = []
    try:
        with patch.object(ip, "make_retry_session", return_value=_FakeSess(rec)), \
             patch.object(ip, "get_proxy_config", return_value=None):
            ip.fetch_url("https://example.com/x", timeout=(2, 9))
    finally:
        ip._TLS_HTTP.__dict__.clear()
    assert rec[0] == (2, 9)
