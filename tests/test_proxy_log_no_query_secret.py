# -*- coding: utf-8 -*-
"""`infra/proxy.py::fetch_url` 印到 stdout 的例外訊息不得帶查詢字串（docs/v2/49 §4.9；2026-10-13）。

requests 的連線類例外會把完整網址（含 `params` 編進去的 `api_key=`）放進訊息。
`fetch_url` 有三處直接印例外：通用 `except Exception`、`ProxyError`、降級直連失敗。
本檔以**不可連線的本機位址**（127.0.0.1:9，discard 埠，沒有人在聽）觸發真的 requests 例外，
斷言 stdout 不含金鑰的值；同時釘住回傳值與失敗分類不變（只改印的東西）。
不打外部網路：目標與代理都指向本機。
"""
from __future__ import annotations

import secrets as _rnd
from unittest.mock import patch

import pytest

from infra import proxy as ip
from infra import source_backoff as sb

_DEAD = "http://127.0.0.1:9"


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    # 環境變數的代理（本沙箱有 HTTPS_PROXY）不得介入：本檔只打本機。
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    ip._TLS_HTTP.__dict__.clear()
    sb.reset_all()
    ip._TLS_FAIL.kind = ""
    yield
    ip._TLS_HTTP.__dict__.clear()
    sb.reset_all()
    ip._TLS_FAIL.kind = ""


def _call(key, proxy_cfg):
    with patch.object(ip, "get_proxy_config", return_value=proxy_cfg):
        return ip.fetch_url(f"{_DEAD}/fred/series/observations",
                            params={"series_id": "FEDFUNDS", "api_key": key},
                            timeout=2, retries=1, bypass_backoff=True)


def test_通用except分支_印出的例外不含金鑰(capsys):
    key = "k" + _rnd.token_hex(16)
    r = _call(key, None)
    out = capsys.readouterr().out
    assert r is None
    assert "[proxy] Error:" in out                     # 真的走到通用 except（空掃防呆）
    assert key not in out and "api_key=" not in out
    assert "127.0.0.1" in out                          # host 照留，除錯資訊不減


def test_ProxyError與降級直連失敗兩個分支_印出的例外不含金鑰(capsys):
    key = "k" + _rnd.token_hex(16)
    r = _call(key, {"http": _DEAD, "https": _DEAD})
    out = capsys.readouterr().out
    assert r is None
    assert "ProxyError attempt 1" in out and "[proxy] 直連失敗：" in out   # 兩個分支都走到
    assert key not in out and "api_key=" not in out


def test_回傳值與失敗分類不變_只改印的字串():
    r = _call("k" + _rnd.token_hex(8), None)
    assert r is None
    assert ip.pop_last_fail_kind() == "unreachable"


def test_去查詢字串_只砍問號之後_其餘逐字保留():
    msg = ("HTTPConnectionPool(host='127.0.0.1', port=9): Max retries exceeded with url: "
           "/fred/series/observations?series_id=X&api_key=SECRET (Caused by NewConnectionError('x'))")
    assert ip._exc_log(ValueError(msg)) == (
        "HTTPConnectionPool(host='127.0.0.1', port=9): Max retries exceeded with url: "
        "/fred/series/observations (Caused by NewConnectionError('x'))")
    assert ip._exc_log(ValueError("沒有網址的訊息")) == "沒有網址的訊息"
