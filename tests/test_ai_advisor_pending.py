"""test_ai_advisor_pending.py — v19.0 explain + v19.9 recommend."""
from __future__ import annotations

from services.ai_advisor_pending import recommend_weights


def test_recommend_empty_candidates_returns_fallback(monkeypatch):
    """v19.9：無候選 → fallback 顯示 F3 全濾提示."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    out = recommend_weights([], {"oos_f1": 0.0})
    assert "數學摘要" in out
    assert "無有效候選" in out


def test_recommend_fallback_picks_top_plateau(monkeypatch):
    """v19.9：無 API key → fallback 取最高 plateau 為建議."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    candidates = [
        {"weights": {"VIX": 0.5, "HY_SPREAD": 0.5},
         "f1": 0.6, "sharpe": 0.3, "n_crossings": 8, "plateau_score": 0.45},
        {"weights": {"VIX": 1.0},
         "f1": 0.9, "sharpe": 0.5, "n_crossings": 1, "plateau_score": 0.30},
    ]
    out = recommend_weights(candidates, {"oos_f1": 0.25, "oos_sharpe": 0.4})
    assert "候選 1" in out  # 推薦最高 plateau（已 sort）
    assert "VIX=0.50" in out or "VIX=0.5" in out
    # n_crossings=8 → 不該觸發稀疏旗標
    assert "訊號偏稀疏" not in out


def test_recommend_fallback_sparsity_flag_triggers(monkeypatch):
    """v19.9：top 1 候選 n_crossings<5 → fallback 標稀疏旗標."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    candidates = [
        {"weights": {"VIX": 1.0}, "f1": 0.9, "sharpe": 0.5,
         "n_crossings": 2, "plateau_score": 0.30},
    ]
    out = recommend_weights(candidates, {"oos_f1": 0.0})
    assert "訊號偏稀疏" in out
    assert "OOS F1=0" in out  # OOS=0 也要 flag


def test_recommend_handles_api_failure_gracefully(monkeypatch):
    """v19.9：AI call 失敗 → fallback + 失敗註記，不 raise."""
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key-no-network")
    candidates = [
        {"weights": {"VIX": 0.5, "HY_SPREAD": 0.5},
         "f1": 0.6, "sharpe": 0.3, "n_crossings": 8, "plateau_score": 0.45},
    ]
    out = recommend_weights(candidates, {"oos_f1": 0.25})
    assert "候選 1" in out
    # 失敗註記（呼叫失敗 / 配額用盡 / 不可用）或 AI 成功
    assert (
        "AI 呼叫失敗" in out
        or "AI 全部 key 配額用盡" in out
        or "AI 不可用" in out
        or "🤖" in out
    )


# ─── v19.13.11: gemini_generate multi-key rotation ────────────────
def test_recommend_uses_gemini_generate_for_key_rotation(monkeypatch):
    """v19.13.11：recommend_weights 必須走 gemini_generate（multi-key rotation），
    不能像 v19.9-v19.13.10 那樣直接 genai.configure 單把 key — 否則 macro 用完
    同把 key 配額 → pullback 撞 ResourceExhausted 直接掉 fallback。"""
    import services.ai_advisor_pending as mod
    called: dict[str, object] = {}

    def _fake_gen(prompt: str, *args, **kwargs) -> str:
        called["prompt"] = prompt
        return "建議候選 1（mock AI 回應）"

    monkeypatch.setattr("services.ai_service.get_gemini_keys",
                        lambda: ["k1", "k2", "k3"])
    monkeypatch.setattr("services.ai_service.gemini_generate", _fake_gen)
    # 確保走 gemini_generate 而不是直接 genai.configure
    monkeypatch.delattr(mod, "__name__", raising=False) if False else None

    candidates = [
        {"weights": {"VIX": 1.0}, "f1": 0.7, "sharpe": 0.4,
         "n_crossings": 10, "plateau_score": 0.40},
    ]
    out = recommend_weights(candidates, {"oos_f1": 0.3})
    assert "mock AI 回應" in out, "應該走 gemini_generate 拿到 mock 回應"
    assert "prompt" in called, "gemini_generate 必須被呼叫"


def test_recommend_handles_all_keys_quota_exhausted(monkeypatch):
    """v19.13.11：所有 key 都撞配額 → gemini_generate 回 ❌ sentinel →
    fallback 帶「全部 key 配額用盡」標籤（user 知道是 quota 而非 bug）."""
    monkeypatch.setattr("services.ai_service.get_gemini_keys",
                        lambda: ["k1", "k2"])
    monkeypatch.setattr(
        "services.ai_service.gemini_generate",
        lambda *a, **kw: "❌ 所有 Gemini key 配額皆已用盡，請稍後再試。",
    )
    candidates = [
        {"weights": {"VIX": 1.0}, "f1": 0.7, "sharpe": 0.4,
         "n_crossings": 10, "plateau_score": 0.40},
    ]
    out = recommend_weights(candidates, {"oos_f1": 0.3})
    assert "全部 key 配額用盡" in out, "user 看得到 quota 訊息"
    assert "候選 1" in out, "fallback 仍要顯示"


def test_recommend_handles_no_keys_at_all(monkeypatch):
    """v19.13.11：沒設任何 Gemini key → 直接走 fallback 不嘗試呼叫."""
    monkeypatch.setattr("services.ai_service.get_gemini_keys", lambda: [])
    called: dict[str, bool] = {"gen": False}

    def _should_not_be_called(*a, **kw):
        called["gen"] = True
        return ""
    monkeypatch.setattr(
        "services.ai_service.gemini_generate", _should_not_be_called,
    )

    candidates = [
        {"weights": {"VIX": 1.0}, "f1": 0.7, "sharpe": 0.4,
         "n_crossings": 10, "plateau_score": 0.40},
    ]
    out = recommend_weights(candidates, {"oos_f1": 0.3})
    assert "候選 1" in out
    assert not called["gen"], "無 key 時不該呼叫 gemini_generate"
