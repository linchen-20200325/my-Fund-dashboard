"""換標決策引擎(v19.423)。驗:策略分、紅/黃/綠/灰燈、同類替換 argmax、大盤 regime、處置文字。"""
from services.switch_strategy import (
    GRAY,
    GREEN,
    RED,
    YELLOW,
    execution_advice,
    market_regime_alert,
    replacement_candidate,
    switch_score,
    switch_signal,
)


# ── 策略分 ──────────────────────────────────────────────
def test_score_max():
    assert switch_score(8.0, 1.0, -10.0, 5.0) == 100          # 35+30+20+15


def test_score_mid():
    assert switch_score(3.0, 0.5, -20.0, -2.0) == 55          # 25+20+10+0


def test_score_floor():
    assert switch_score(-15.0, -0.5, -30.0, None) == 0        # 0+0+0+0


def test_score_missing_core_is_none():
    assert switch_score(None, 1.0, -10.0, 5.0) is None        # 缺 1Y含息
    assert switch_score(8.0, None, -10.0, 5.0) is None        # 缺 Sharpe


def test_score_optional_missing_ok():
    # MaxDD / vs大盤 缺 → 該項 0,但仍給分(核心齊)
    assert switch_score(8.0, 1.0, None, None) == 65           # 35+30


# ── 燈號 ────────────────────────────────────────────────
def test_signal_red_both_negative():
    assert switch_signal(-5.0, -0.3, "🟡 警示", 1.0, -5.0, 20) == RED


def test_signal_red_severe_eat():
    assert switch_signal(3.0, 0.6, "🔴 嚴重的吃本金", 1.0, -5.0, 60) == RED


def test_signal_green():
    assert switch_signal(8.0, 1.0, "🟢🟢 健康", 5.0, -3.0, 85) == GREEN


def test_signal_gray_insufficient():
    assert switch_signal(8.0, 1.0, "健康", 5.0, -3.0, None) == GRAY
    assert switch_signal(None, 1.0, "健康", 5.0, -3.0, 80) == GRAY


def test_signal_yellow_default():
    # 非紅(tr>0)、非綠(分<70)、非灰 → 黃
    assert switch_signal(3.0, 0.5, "🟡 警示", -2.0, -25.0, 55) == YELLOW


def test_signal_high_score_but_not_healthy_is_yellow():
    # 分高但吃本金非健康 → 不綠 → 黃
    assert switch_signal(8.0, 1.0, "🟡 警示", 5.0, -3.0, 85) == YELLOW


# ── 替換引擎(同類別 argmax)────────────────────────────
def _cand(code, cat, sharpe, tr, sortino, exp=0.8, eat="🟢 健康"):
    return {"code": code, "基金類別": cat, "Sharpe 1Y": sharpe, "1Y 含息 %": tr,
            "Sortino": sortino, "費用率 %": exp, "吃本金燈號 (1Y · MK)": eat, "策略燈號": GREEN}


def test_replacement_picks_best_same_category():
    pool = [_cand("B", "股票型", 1.0, 8.0, 0.5),
            _cand("C", "股票型", 1.5, 10.0, 1.0),   # 最佳
            _cand("D", "債券型", 2.0, 20.0, 2.0)]   # 不同類 → 排除
    best = replacement_candidate("股票型", pool)
    assert best is not None and best["code"] == "C"


def test_replacement_excludes_unhealthy():
    pool = [_cand("B", "股票型", 0.3, 8.0, 0.5),          # Sharpe<0.5 排除
            _cand("C", "股票型", 1.0, -2.0, 0.5),         # 總報酬<0 排除
            _cand("D", "股票型", 1.0, 8.0, 0.5, exp=1.8)]  # 費用率≥1.5 排除
    assert replacement_candidate("股票型", pool) is None


def test_replacement_none_when_no_same_category():
    pool = [_cand("B", "債券型", 1.5, 10.0, 1.0)]
    assert replacement_candidate("股票型", pool) is None


# ── 大盤 regime filter ──────────────────────────────────
def test_regime_systemic_when_over_80pct_negative():
    rows = [{"Sharpe 1Y": v} for v in [-0.5, -0.3, -1.0, -0.2, 0.1]]   # 4/5 = 80%
    r = market_regime_alert(rows)
    assert r["systemic_risk"] is True and r["neg_pct"] == 80.0


def test_regime_not_systemic_when_healthy():
    rows = [{"Sharpe 1Y": v} for v in [0.8, 1.0, -0.3, 0.5]]           # 1/4 = 25%
    assert market_regime_alert(rows)["systemic_risk"] is False


def test_regime_no_valid_sharpe():
    assert market_regime_alert([{"Sharpe 1Y": None}])["systemic_risk"] is False


def test_regime_by_category():
    rows = [{"基金類別": "股票型", "Sharpe 1Y": -0.5},
            {"基金類別": "股票型", "Sharpe 1Y": -0.3},
            {"基金類別": "債券型", "Sharpe 1Y": 1.0}]
    assert market_regime_alert(rows, category="股票型")["systemic_risk"] is True


# ── 處置文字 ────────────────────────────────────────────
def test_execution_advice_covers_all_lights():
    assert "平轉" in execution_advice(RED)
    assert "暫停" in execution_advice(YELLOW)
    assert "續抱" in execution_advice(GREEN)
    assert "資料不足" in execution_advice(GRAY)
