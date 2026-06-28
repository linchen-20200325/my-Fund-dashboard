"""test_crisis_ai_advisor.py — Phase 5 AI 策略建議測試 (v18.260)

驗證：
- prompt builder 各區塊內容
- 空 events / 空 grid 邊界
- 無 API key 時 fallback 訊息
- generate_strategy_advice 路徑（mock gemini）
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from services.crisis_ai_advisor import (
    _summarize_events,
    _summarize_grid,
    _summarize_top,
    build_strategy_advice_prompt,
    generate_strategy_advice,
)


# ──────────────────────────────────────────────────────────────
# fixtures
# ──────────────────────────────────────────────────────────────
@dataclass
class _FakeEvent:
    peak_date: str
    trough_date: str
    drawdown_pct: float
    duration_days: int
    recovery_days: Optional[int]

    def to_dict(self) -> dict:
        return {
            "peak_date": self.peak_date,
            "trough_date": self.trough_date,
            "drawdown_pct": self.drawdown_pct,
            "duration_days": self.duration_days,
            "recovery_days": self.recovery_days,
        }


def _make_events() -> list:
    return [
        _FakeEvent("2020-02-19", "2020-03-23", -0.339, 33, 148),
        _FakeEvent("2022-01-03", "2022-10-12", -0.252, 282, 364),
    ]


def _make_grid_df() -> pd.DataFrame:
    rows = []
    for label, key in [("全程持有", "buy_and_hold"), ("訊號出場", "signal_exit"),
                       ("訊號減半", "signal_half"), ("訊號加碼低點", "buy_dip")]:
        for thr in [25.0, 30.0, 35.0]:
            rows.append({
                "strategy_key": key, "strategy_label": label, "threshold": thr,
                "final_value": 130.0, "total_return_pct": 0.30,
                "max_drawdown_pct": -0.15, "sharpe_ratio": 1.2,
                "crisis_return_pct": -0.05,
                "n_trigger_days": 80, "n_total_days": 252,
            })
    return pd.DataFrame(rows)


def _make_top() -> dict:
    return {
        "strategy_label": "訊號出場", "threshold": 30.0,
        "final_value": 145.5, "total_return_pct": 0.455,
        "max_drawdown_pct": -0.08, "sharpe_ratio": 1.85,
        "crisis_return_pct": 0.01,
        "n_trigger_days": 80, "n_total_days": 252,
    }


# ──────────────────────────────────────────────────────────────
# _summarize_events
# ──────────────────────────────────────────────────────────────
class TestSummarizeEvents:
    def test_empty(self):
        out = _summarize_events([])
        assert "沒有偵測到" in out

    def test_two_events(self):
        out = _summarize_events(_make_events())
        assert "2020-02-19" in out
        assert "-33.9%" in out
        assert "尚未回升" not in out

    def test_truncates_when_many(self):
        many = _make_events() * 5  # 10 筆
        out = _summarize_events(many)
        assert "另" in out and "略" in out


# ──────────────────────────────────────────────────────────────
# _summarize_grid
# ──────────────────────────────────────────────────────────────
class TestSummarizeGrid:
    def test_empty_df(self):
        out = _summarize_grid(pd.DataFrame())
        assert "無網格" in out

    def test_table_has_all_strategies(self):
        out = _summarize_grid(_make_grid_df())
        assert "全程持有" in out
        assert "訊號出場" in out
        assert "訊號加碼低點" in out
        assert "| 策略 |" in out  # markdown table header


# ──────────────────────────────────────────────────────────────
# _summarize_top
# ──────────────────────────────────────────────────────────────
class TestSummarizeTop:
    def test_none(self):
        assert "無最佳" in _summarize_top(None)

    def test_dict_input(self):
        out = _summarize_top(_make_top())
        assert "訊號出場" in out
        assert "+45.5%" in out
        assert "1.85" in out

    def test_series_input(self):
        out = _summarize_top(pd.Series(_make_top()))
        assert "訊號出場" in out


# ──────────────────────────────────────────────────────────────
# build_strategy_advice_prompt
# ──────────────────────────────────────────────────────────────
class TestBuildPrompt:
    def test_prompt_contains_all_sections(self):
        prompt = build_strategy_advice_prompt(
            events=_make_events(),
            grid_df=_make_grid_df(),
            top_result=_make_top(),
            signal_label="VIX > 25",
            market_label="SPX",
            metric_label="年化 Sharpe",
        )
        assert "VIX > 25" in prompt
        assert "SPX" in prompt
        assert "年化 Sharpe" in prompt
        assert "最佳策略解讀" in prompt
        assert "風險與盲點" in prompt
        assert "投資人該怎麼做" in prompt
        assert "一句話總結" in prompt

    def test_prompt_handles_empty_events(self):
        prompt = build_strategy_advice_prompt(
            events=[],
            grid_df=_make_grid_df(),
            top_result=_make_top(),
            signal_label="VIX > 25",
            market_label="SPX",
        )
        assert "沒有偵測到" in prompt


# ──────────────────────────────────────────────────────────────
# generate_strategy_advice
# ──────────────────────────────────────────────────────────────
class TestGenerateAdvice:
    def test_empty_grid_returns_warning(self):
        out = generate_strategy_advice(
            events=[], grid_df=pd.DataFrame(),
            top_result=None, signal_label="VIX", market_label="SPX",
        )
        assert "⚠️" in out and "網格" in out

    def test_no_api_key_returns_warning(self, monkeypatch):
        import services.ai_service as ai
        monkeypatch.setattr(ai, "get_gemini_keys", lambda: [])
        out = generate_strategy_advice(
            events=_make_events(), grid_df=_make_grid_df(),
            top_result=_make_top(),
            signal_label="VIX > 25", market_label="SPX",
        )
        assert "⚠️" in out and "Gemini" in out

    def test_calls_gemini_with_prompt(self, monkeypatch):
        import services.ai_service as ai
        captured = {}
        monkeypatch.setattr(ai, "get_gemini_keys", lambda: ["fake-key"])

        def _fake_gen(prompt, max_tokens=2000, keys=None, start=0):
            captured["p"] = prompt
            return "AI 回應"

        monkeypatch.setattr(ai, "gemini_generate", _fake_gen)
        out = generate_strategy_advice(
            events=_make_events(), grid_df=_make_grid_df(),
            top_result=_make_top(),
            signal_label="VIX > 25", market_label="SPX",
        )
        assert out == "AI 回應"
        assert "VIX > 25" in captured["p"]
        assert "訊號出場" in captured["p"]
