"""test_llm.py — infra/llm.py 多 provider fallback chain 測試（v18.113 AI-3）

純函式測試（mock requests.post）— 不打真 API：
- 各 provider 個別 success / HTTP 4xx / timeout
- chain 順序：第一個成功就回
- skip 缺 key 的 provider 不算錯
- 全 fail 回彙整錯誤訊息
- provider_chain 自訂順序生效
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from infra import llm


# ════════════════════════════════════════════════════════════
# Helpers — 造 mock response
# ════════════════════════════════════════════════════════════
def _gemini_resp(text: str, status: int = 200) -> MagicMock:
    m = MagicMock()
    m.status_code = status
    m.text = text
    m.json.return_value = {"candidates": [{"content": {"parts": [{"text": text}]}}]}
    return m


def _anthropic_resp(text: str, status: int = 200) -> MagicMock:
    m = MagicMock()
    m.status_code = status
    m.text = text
    m.json.return_value = {"content": [{"type": "text", "text": text}]}
    return m


def _openai_resp(text: str, status: int = 200) -> MagicMock:
    m = MagicMock()
    m.status_code = status
    m.text = text
    m.json.return_value = {"choices": [{"message": {"content": text}}]}
    return m


def _err_resp(status: int, body: str = "server error") -> MagicMock:
    m = MagicMock()
    m.status_code = status
    m.text = body
    m.json.return_value = {}
    return m


# ════════════════════════════════════════════════════════════
# call_llm — fallback chain 行為
# ════════════════════════════════════════════════════════════
def test_call_llm_uses_gemini_first_when_all_keys_set(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with patch.object(llm.requests, "post", return_value=_gemini_resp("Gemini OK")) as mp:
        out = llm.call_llm("test", gemini_key="GK", anthropic_key="AK", openai_key="OK")
    assert out == "Gemini OK"
    # 只打 Gemini API
    assert mp.call_count == 1
    assert "generativelanguage.googleapis.com" in mp.call_args[0][0]


def test_call_llm_falls_back_to_anthropic_when_gemini_500(monkeypatch):
    """Gemini 連兩次 500 → fallback to Anthropic（成功）。"""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    responses = [
        _err_resp(500), _err_resp(500), _err_resp(500),    # Gemini 3 attempts
        _anthropic_resp("Claude OK"),                       # Anthropic 1st OK
    ]
    with patch.object(llm.requests, "post", side_effect=responses), \
         patch.object(llm.time, "sleep"):   # 跳過 retry sleep
        out = llm.call_llm("test", gemini_key="GK", anthropic_key="AK",
                           retries=2, timeout=10)
    assert out == "Claude OK"


def test_call_llm_falls_back_to_openai_when_gemini_anthropic_both_fail(monkeypatch):
    """Gemini 500 → Anthropic 500 → OpenAI success。"""
    responses = (
        [_err_resp(500)] * 3   # Gemini 3 attempts fail
        + [_err_resp(500)] * 3 # Anthropic 3 attempts fail
        + [_openai_resp("GPT OK")]
    )
    with patch.object(llm.requests, "post", side_effect=responses), \
         patch.object(llm.time, "sleep"):
        out = llm.call_llm("test", gemini_key="GK", anthropic_key="AK", openai_key="OK",
                           retries=2, timeout=10)
    assert out == "GPT OK"


def test_call_llm_skip_provider_without_key(monkeypatch):
    """無 gemini_key → 直接從 Anthropic 開始（不算失敗）。"""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with patch.object(llm.requests, "post", return_value=_anthropic_resp("Claude OK")) as mp:
        out = llm.call_llm("test", anthropic_key="AK")
    assert out == "Claude OK"
    # 只打 Anthropic
    assert mp.call_count == 1
    assert "api.anthropic.com" in mp.call_args[0][0]


def test_call_llm_all_keys_missing_returns_aggregated_error(monkeypatch):
    """全無 key → 不打 API，直接回彙整錯誤。"""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with patch.object(llm.requests, "post") as mp:
        out = llm.call_llm("test")
    assert mp.call_count == 0
    assert out.startswith("❌ **所有 LLM provider 都失敗**")
    assert "gemini: 未設定 API key" in out
    assert "anthropic: 未設定 API key" in out
    assert "openai: 未設定 API key" in out


def test_call_llm_all_providers_500_returns_aggregated_error():
    """3 個都 HTTP 500（key 都有） → 回彙整錯誤含 3 個 provider 的失敗原因。"""
    responses = [_err_resp(500, "server boom")] * 9   # 3 providers * 3 attempts
    with patch.object(llm.requests, "post", side_effect=responses), \
         patch.object(llm.time, "sleep"):
        out = llm.call_llm("test", gemini_key="GK", anthropic_key="AK", openai_key="OK",
                           retries=2, timeout=10)
    assert out.startswith("❌ **所有 LLM provider 都失敗**")
    assert "gemini:" in out
    assert "anthropic:" in out
    assert "openai:" in out


def test_call_llm_429_quota_skips_to_next_provider():
    """Gemini 429 → Anthropic 拿到 200 → 成功。"""
    responses = (
        [_err_resp(429, "quota exceeded")] * 3   # Gemini 429 x3
        + [_anthropic_resp("Claude saves the day")]
    )
    with patch.object(llm.requests, "post", side_effect=responses), \
         patch.object(llm.time, "sleep"):
        out = llm.call_llm("test", gemini_key="GK", anthropic_key="AK",
                           retries=2, timeout=10)
    assert out == "Claude saves the day"


def test_call_llm_custom_provider_chain():
    """provider_chain=['openai'] → 只試 OpenAI，跳過 Gemini / Anthropic。"""
    with patch.object(llm.requests, "post", return_value=_openai_resp("GPT only")) as mp:
        out = llm.call_llm("test", gemini_key="GK", anthropic_key="AK", openai_key="OK",
                           provider_chain=["openai"])
    assert out == "GPT only"
    assert mp.call_count == 1
    assert "api.openai.com" in mp.call_args[0][0]


# ════════════════════════════════════════════════════════════
# 各 provider 單獨呼叫的 happy / error 路徑
# ════════════════════════════════════════════════════════════
def test_call_gemini_happy_path():
    with patch.object(llm.requests, "post", return_value=_gemini_resp("hi")):
        out = llm._call_gemini("k", "p", 100, retries=0, timeout=5)
    assert out == "hi"


def test_call_anthropic_happy_path():
    with patch.object(llm.requests, "post", return_value=_anthropic_resp("hi")):
        out = llm._call_anthropic("k", "p", 100, retries=0, timeout=5)
    assert out == "hi"


def test_call_openai_happy_path():
    with patch.object(llm.requests, "post", return_value=_openai_resp("hi")):
        out = llm._call_openai("k", "p", 100, retries=0, timeout=5)
    assert out == "hi"


def test_call_gemini_429_returns_error():
    with patch.object(llm.requests, "post", return_value=_err_resp(429)), \
         patch.object(llm.time, "sleep"):
        out = llm._call_gemini("k", "p", 100, retries=0, timeout=5)
    assert "429" in out and out.startswith("❌")


@pytest.mark.parametrize("caller_name", ["_call_gemini", "_call_anthropic", "_call_openai"])
def test_provider_timeout_returns_error(caller_name):
    caller = getattr(llm, caller_name)
    import requests as _req
    with patch.object(llm.requests, "post", side_effect=_req.exceptions.Timeout()), \
         patch.object(llm.time, "sleep"):
        out = caller("k", "p", 100, retries=0, timeout=5)
    assert out.startswith("❌") and "逾時" in out


# ════════════════════════════════════════════════════════════
# response_format="json" — v18.114 AI-4 native JSON mode
# ════════════════════════════════════════════════════════════
def test_gemini_response_format_json_adds_response_mime_type():
    """response_format='json' → Gemini body 內 generationConfig 加 responseMimeType。"""
    captured = {}
    def _capture(url, json=None, **kw):
        captured["body"] = json
        return _gemini_resp('{"ok": true}')
    with patch.object(llm.requests, "post", side_effect=_capture):
        llm._call_gemini("k", "p", 100, 0, 5, response_format="json")
    cfg = captured["body"]["generationConfig"]
    assert cfg.get("responseMimeType") == "application/json"


def test_openai_response_format_json_adds_json_object():
    """response_format='json' → OpenAI body 加 response_format={'type':'json_object'}。"""
    captured = {}
    def _capture(url, json=None, **kw):
        captured["body"] = json
        return _openai_resp('{"ok": true}')
    with patch.object(llm.requests, "post", side_effect=_capture):
        llm._call_openai("k", "p", 100, 0, 5, response_format="json")
    assert captured["body"].get("response_format") == {"type": "json_object"}


def test_anthropic_response_format_json_no_native_change():
    """Anthropic 無 native JSON mode → body 不變（caller 靠 prompt 指示）。"""
    captured = {}
    def _capture(url, json=None, **kw):
        captured["body"] = json
        return _anthropic_resp('{"ok": true}')
    with patch.object(llm.requests, "post", side_effect=_capture):
        llm._call_anthropic("k", "p", 100, 0, 5, response_format="json")
    # 不應出現 response_format / responseMimeType 欄位
    assert "response_format" not in captured["body"]
    assert "responseMimeType" not in captured["body"]


def test_call_llm_response_format_propagates_to_provider():
    """call_llm(response_format='json') 應傳到所選 provider。"""
    captured = {}
    def _capture(url, json=None, **kw):
        captured["body"] = json
        return _gemini_resp('{"ok": true}')
    with patch.object(llm.requests, "post", side_effect=_capture):
        out = llm.call_llm("p", gemini_key="GK", response_format="json")
    assert out == '{"ok": true}'
    assert captured["body"]["generationConfig"]["responseMimeType"] == "application/json"
