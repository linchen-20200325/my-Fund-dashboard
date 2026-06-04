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
    assert "AI 呼叫失敗" in out or "🤖" in out  # 失敗註記 或 AI 成功
