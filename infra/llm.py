"""infra/llm.py — 多 LLM provider fallback chain client（v18.113 AI-3）

職責：把單一 LLM 呼叫升級成 fallback chain — Gemini fail → Claude → GPT。
解耦 services/ai_service.py，讓 prompt 構造（service 層）與實際發送（infra 層）分離。

設計：
- **純 I/O 層**：不 import streamlit / 不 import services；只發 HTTP + 處理錯誤
- **provider chain**：預設 ["gemini", "anthropic", "openai"]，第一個成功就回
- **API key 來源**：函式參數 → os.environ；缺 key → skip 該 provider 不算錯
- **錯誤匯總**：全部 fail → 回傳含每個 provider 失敗原因的彙整字串

公開 API：
- call_llm(prompt, max_tokens, ...) -> str   # 主要入口
- _call_gemini / _call_anthropic / _call_openai  # 各 provider 實作（_前綴 = 內部）
"""
from __future__ import annotations

import os
import time

import requests


# ── Provider 預設模型 ────────────────────────────────────
# Gemini: 與既有 services/ai_service.py 一致
_GEMINI_MODEL = "gemini-2.5-flash"
# Claude: Haiku 4.5（cheap + capable，對標 Gemini Flash）
_ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
_ANTHROPIC_VERSION = "2023-06-01"
# OpenAI: gpt-4o-mini（cheap parity）
_OPENAI_MODEL = "gpt-4o-mini"

_DEFAULT_CHAIN = ["gemini", "anthropic", "openai"]


# ════════════════════════════════════════════════════════════
# 主入口
# ════════════════════════════════════════════════════════════
def call_llm(prompt: str,
             max_tokens: int = 2000,
             retries: int = 2,
             timeout: int = 90,
             gemini_key: str = "",
             anthropic_key: str = "",
             openai_key: str = "",
             provider_chain: list[str] | None = None,
             response_format: str | None = None) -> str:
    """多 provider fallback chain LLM 呼叫。

    Args:
        prompt: 完整 prompt 字串
        max_tokens: 最大輸出 token（每個 provider 都會傳這個值）
        retries: 每個 provider 內部 retry 次數（非 chain retry）
        timeout: 單次 HTTP 請求 timeout（秒）
        gemini_key / anthropic_key / openai_key: 函式級 key override（優先於 env）
        provider_chain: 嘗試順序；預設 ["gemini", "anthropic", "openai"]
        response_format: None（預設純文字）或 "json"（請求結構化 JSON 輸出）
                        - Gemini: responseMimeType="application/json"
                        - OpenAI: response_format={"type": "json_object"}
                        - Anthropic: 僅靠 prompt 內指示（無 native json mode）

    Returns:
        成功 → LLM 回應字串
        全失敗 → "❌ **所有 LLM provider 都失敗**\n\n- gemini: ...\n- ..."

    Key 解析優先序：函式參數 → os.environ（GEMINI_API_KEY / ANTHROPIC_API_KEY /
                  OPENAI_API_KEY）→ 空字串則 skip 該 provider（不算失敗）
    """
    keys = {
        "gemini":    gemini_key    or os.environ.get("GEMINI_API_KEY", ""),
        "anthropic": anthropic_key or os.environ.get("ANTHROPIC_API_KEY", ""),
        "openai":    openai_key    or os.environ.get("OPENAI_API_KEY", ""),
    }
    chain = provider_chain or _DEFAULT_CHAIN
    errors: list[str] = []
    for provider in chain:
        key = keys.get(provider, "")
        if not key:
            errors.append(f"{provider}: 未設定 API key（跳過）")
            continue
        caller = _PROVIDER_CALLERS.get(provider)
        if caller is None:
            errors.append(f"{provider}: 未知 provider")
            continue
        try:
            result = caller(key, prompt, max_tokens, retries, timeout,
                            response_format)
            # 成功判定：非空 + 不以 ❌/⚠️ 開頭
            if result and not str(result).lstrip().startswith(("❌", "⚠️")):
                return result
            errors.append(f"{provider}: {str(result)[:100]}")
        except Exception as e:
            errors.append(f"{provider}: {type(e).__name__} {str(e)[:80]}")
    return (
        "❌ **所有 LLM provider 都失敗**\n\n"
        + "\n".join(f"- {e}" for e in errors)
        + "\n\n請至少設定 GEMINI_API_KEY / ANTHROPIC_API_KEY / OPENAI_API_KEY 其中一個。"
    )


# ════════════════════════════════════════════════════════════
# Gemini provider
# ════════════════════════════════════════════════════════════
def _call_gemini(api_key: str, prompt: str, max_tokens: int,
                 retries: int, timeout: int,
                 response_format: str | None = None) -> str:
    """Gemini 2.5 Flash API（thinkingBudget=0 關閉思考鏈，全 token 給輸出）。

    response_format="json" → 加 responseMimeType="application/json"（native JSON mode）。
    """
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{_GEMINI_MODEL}:generateContent?key={api_key}")
    gen_cfg = {
        "temperature": 0.7,
        "maxOutputTokens": max_tokens,
        "thinkingConfig": {"thinkingBudget": 0},
    }
    if response_format == "json":
        gen_cfg["responseMimeType"] = "application/json"
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": gen_cfg,
    }
    headers = {"Content-Type": "application/json"}
    for attempt in range(retries + 1):
        try:
            r = requests.post(url, json=body, headers=headers, timeout=timeout)
            if r.status_code == 200:
                cands = r.json().get("candidates", [])
                if cands:
                    parts = cands[0].get("content", {}).get("parts", [])
                    txt = "\n".join(p.get("text", "") for p in parts
                                    if "text" in p).strip()
                    return txt or "⚠️ Gemini 回傳空結果"
                return "⚠️ Gemini 回傳空結果"
            if r.status_code == 429:
                if attempt < retries:
                    time.sleep(20 * (attempt + 1)); continue
                return "❌ Gemini 配額已達上限（HTTP 429）"
            if attempt < retries:
                time.sleep(5); continue
            return f"❌ Gemini HTTP {r.status_code}：{r.text[:150]}"
        except requests.exceptions.Timeout:
            if attempt < retries:
                time.sleep(5); continue
            return "❌ Gemini 請求逾時"
        except Exception as e:
            if attempt < retries:
                time.sleep(3); continue
            return f"❌ Gemini {type(e).__name__}：{str(e)[:120]}"
    return "❌ Gemini 失敗（耗盡 retry）"


# ════════════════════════════════════════════════════════════
# Anthropic Claude provider
# ════════════════════════════════════════════════════════════
def _call_anthropic(api_key: str, prompt: str, max_tokens: int,
                    retries: int, timeout: int,
                    response_format: str | None = None) -> str:
    """Anthropic Messages API（claude-haiku-4-5）。

    response_format="json" → 無 native json mode，僅靠 caller 在 prompt 內指示
    （參數收下但不改 body，避免不相容；service 層後處理時做 JSON tolerant parse）。
    """
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": _ANTHROPIC_VERSION,
        "content-type": "application/json",
    }
    body = {
        "model": _ANTHROPIC_MODEL,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    for attempt in range(retries + 1):
        try:
            r = requests.post(url, json=body, headers=headers, timeout=timeout)
            if r.status_code == 200:
                content_blocks = r.json().get("content", [])
                txt = "\n".join(b.get("text", "") for b in content_blocks
                                if b.get("type") == "text").strip()
                return txt or "⚠️ Claude 回傳空結果"
            if r.status_code == 429:
                if attempt < retries:
                    time.sleep(20 * (attempt + 1)); continue
                return "❌ Claude 配額已達上限（HTTP 429）"
            if attempt < retries:
                time.sleep(5); continue
            return f"❌ Claude HTTP {r.status_code}：{r.text[:150]}"
        except requests.exceptions.Timeout:
            if attempt < retries:
                time.sleep(5); continue
            return "❌ Claude 請求逾時"
        except Exception as e:
            if attempt < retries:
                time.sleep(3); continue
            return f"❌ Claude {type(e).__name__}：{str(e)[:120]}"
    return "❌ Claude 失敗（耗盡 retry）"


# ════════════════════════════════════════════════════════════
# OpenAI GPT provider
# ════════════════════════════════════════════════════════════
def _call_openai(api_key: str, prompt: str, max_tokens: int,
                 retries: int, timeout: int,
                 response_format: str | None = None) -> str:
    """OpenAI Chat Completions API（gpt-4o-mini）。

    response_format="json" → response_format={"type": "json_object"}（native JSON mode）。
    """
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": _OPENAI_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.7,
    }
    if response_format == "json":
        body["response_format"] = {"type": "json_object"}
    for attempt in range(retries + 1):
        try:
            r = requests.post(url, json=body, headers=headers, timeout=timeout)
            if r.status_code == 200:
                choices = r.json().get("choices", [])
                if choices:
                    msg = choices[0].get("message", {})
                    txt = (msg.get("content") or "").strip()
                    return txt or "⚠️ GPT 回傳空結果"
                return "⚠️ GPT 回傳空結果"
            if r.status_code == 429:
                if attempt < retries:
                    time.sleep(20 * (attempt + 1)); continue
                return "❌ GPT 配額已達上限（HTTP 429）"
            if attempt < retries:
                time.sleep(5); continue
            return f"❌ GPT HTTP {r.status_code}：{r.text[:150]}"
        except requests.exceptions.Timeout:
            if attempt < retries:
                time.sleep(5); continue
            return "❌ GPT 請求逾時"
        except Exception as e:
            if attempt < retries:
                time.sleep(3); continue
            return f"❌ GPT {type(e).__name__}：{str(e)[:120]}"
    return "❌ GPT 失敗（耗盡 retry）"


_PROVIDER_CALLERS = {
    "gemini":    _call_gemini,
    "anthropic": _call_anthropic,
    "openai":    _call_openai,
}
