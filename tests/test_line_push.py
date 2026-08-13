"""L0 LINE Messaging API 推播(infra/line_push,v19.432)。

守:dry-run/缺憑證不送(§1 不假裝成功)、成功 payload 正確、HTTP 非 2xx / 網路錯誤 raise、
token 不外洩到例外訊息、空訊息不送、超長截斷。全程 fake poster 不觸網。
"""
from __future__ import annotations

import pytest

from infra.line_push import LinePushError, push_text


class _Resp:
    def __init__(self, status, text=""):
        self.status_code = status
        self.text = text


def _poster(status=200, text="", record=None, raise_exc=None):
    def _p(url, headers=None, json=None, timeout=None):
        if record is not None:
            record.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        if raise_exc is not None:
            raise raise_exc
        return _Resp(status, text)
    return _p


def _clean_env(monkeypatch):
    import infra.config as _cfg
    monkeypatch.setattr(_cfg, "get_secret", lambda k: None, raising=False)
    monkeypatch.delenv("LINE_CHANNEL_TOKEN", raising=False)
    monkeypatch.delenv("LINE_USER_ID", raising=False)


def test_dry_run_does_not_call_poster():
    rec: list = []
    out = push_text("hi", token="T", user_id="U", dry_run=True, _poster=_poster(record=rec))
    assert out["sent"] is False and out["dry_run"] is True
    assert rec == []                                    # 完全不觸網


def test_missing_token_not_sent(monkeypatch):
    _clean_env(monkeypatch)
    rec: list = []
    out = push_text("hi", user_id="U", _poster=_poster(record=rec))
    assert out["sent"] is False and "TOKEN" in out["reason"]
    assert rec == []


def test_missing_user_id_not_sent(monkeypatch):
    _clean_env(monkeypatch)
    out = push_text("hi", token="T", _poster=_poster())
    assert out["sent"] is False and "USER_ID" in out["reason"]


def test_token_alias_access_token_env(monkeypatch):
    """LINE_CHANNEL_TOKEN 未設但別名 LINE_CHANNEL_ACCESS_TOKEN 有 → 仍解析得 token 並送出。

    對應 user GitHub secret 名為 LINE_CHANNEL_ACCESS_TOKEN(spec 命名)不必改名。
    """
    _clean_env(monkeypatch)                              # get_secret→None、刪 LINE_CHANNEL_TOKEN/USER_ID
    monkeypatch.setenv("LINE_CHANNEL_ACCESS_TOKEN", "ACCESSTOK")
    monkeypatch.setenv("LINE_USER_ID", "Uxxx")
    rec: list = []
    out = push_text("hi", _poster=_poster(200, record=rec))
    assert out["sent"] is True
    assert rec and rec[0]["headers"]["Authorization"] == "Bearer ACCESSTOK"


def test_empty_text_not_sent():
    out = push_text("   ", token="T", user_id="U", _poster=_poster())
    assert out["sent"] is False and "未送" in out["reason"]


def test_success_payload_correct():
    rec: list = []
    out = push_text("換股週報", token="TOK", user_id="Uxxx", _poster=_poster(200, record=rec))
    assert out["sent"] is True and out["status"] == 200
    _call = rec[0]
    assert _call["json"]["to"] == "Uxxx"
    assert _call["json"]["messages"][0]["type"] == "text"
    assert _call["json"]["messages"][0]["text"] == "換股週報"
    assert _call["headers"]["Authorization"] == "Bearer TOK"


def test_http_error_raises_and_hides_token():
    with pytest.raises(LinePushError) as e:
        push_text("hi", token="SECRET_TOKEN", user_id="U", _poster=_poster(403, text="Forbidden"))
    _m = str(e.value)
    assert "403" in _m and "Forbidden" in _m
    assert "SECRET_TOKEN" not in _m                     # §1:token 不外洩


def test_network_error_raises():
    with pytest.raises(LinePushError):
        push_text("hi", token="T", user_id="U",
                  _poster=_poster(raise_exc=ConnectionError("boom")))


def test_long_text_truncated_below_line_limit():
    rec: list = []
    push_text("x" * 6000, token="T", user_id="U", _poster=_poster(200, record=rec))
    assert len(rec[0]["json"]["messages"][0]["text"]) <= 5000
