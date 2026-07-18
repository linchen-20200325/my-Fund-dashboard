"""test_macro_explain.py — v19.17 新手友善總經面板純函式單測

涵蓋：
- 常量結構守門（INDICATOR_FREQ_MAP / FREQ_LABEL）
- empty / None / 非 dict → ready=False 安全 fallback
- 完整 indicators → ready=True + top_n 排序 + verdict
- top_n 邊界（0 / -1 / 大於 indicators 數）
- contribution 排序（|score × weight| 降序）
- macro_edu 缺 key → fallback edu_meaning
- frequency 缺 key → fallback "—"
- NaN / 非數值 防呆
- why_bullets 至少 3 條
- verdict_oneline 包含關鍵字
- interpretation 7 級判讀
"""
from __future__ import annotations

from services.macro_explain import (
    INDICATOR_FREQ_MAP,
    FREQ_LABEL,
    build_beginner_payload,
)


# ════════════════════════════════════════════════
# 常量結構守門
# ════════════════════════════════════════════════
def test_v19_17_indicator_freq_map_includes_NFP_monthly():
    assert "NFP" in INDICATOR_FREQ_MAP
    assert INDICATOR_FREQ_MAP["NFP"] == "monthly"


def test_v19_17_freq_label_has_3_known_plus_unknown():
    assert set(FREQ_LABEL.keys()) == {"daily", "weekly", "monthly", "unknown"}
    for v in FREQ_LABEL.values():
        assert isinstance(v, str) and v


def test_v19_17_freq_map_values_are_valid_freq():
    for v in INDICATOR_FREQ_MAP.values():
        assert v in {"daily", "weekly", "monthly"}


def test_v19_17_daily_keys_include_vix_and_yields():
    # 拐點關鍵：VIX / YIELD_10Y2Y / HY_SPREAD 必須在日頻
    for k in ("VIX", "YIELD_10Y2Y", "YIELD_10Y3M", "HY_SPREAD", "DXY"):
        assert INDICATOR_FREQ_MAP[k] == "daily"


# ════════════════════════════════════════════════
# Empty / 邊界
# ════════════════════════════════════════════════
def test_v19_17_none_indicators_returns_not_ready():
    p = build_beginner_payload(None, {})
    assert p["ready"] is False
    assert p["score"] == 0.0
    assert p["active_factors"] == []
    assert p["why_bullets"] == []
    assert "請先按 sidebar" in p["verdict_action_text"]


def test_v19_17_empty_indicators_returns_not_ready():
    p = build_beginner_payload({}, {})
    assert p["ready"] is False


def test_v19_17_invalid_type_indicators_returns_not_ready():
    p = build_beginner_payload("not a dict", {})  # type: ignore[arg-type]
    assert p["ready"] is False


def test_v19_17_indicators_with_no_dict_values_filtered_out():
    """全是非 dict value → 一個都不收 → ready=False"""
    p = build_beginner_payload({"VIX": "bad", "CPI": None}, {})
    assert p["ready"] is False


# ════════════════════════════════════════════════
# 排序 / 取 top_n
# ════════════════════════════════════════════════
def _ind(name, score, weight=1.0, value=0, unit=""):
    return {
        "name": name, "score": score, "weight": weight,
        "value": value, "unit": unit, "type": "領先",
    }


def test_v19_17_contribution_sort_by_abs_descending():
    """top 應該按 |contribution| 降序"""
    indicators = {
        "VIX":        _ind("VIX 恐慌", score=1.0, weight=1.0),   # |1.0|
        "CPI":        _ind("CPI",      score=0.5, weight=2.0),   # |1.0|（tie）
        "HY_SPREAD":  _ind("HY 利差",  score=2.0, weight=1.5),   # |3.0| ← top
        "PMI":        _ind("PMI",      score=-0.2, weight=1.0),  # |0.2|
    }
    p = build_beginner_payload(indicators, {}, top_n=4)
    assert p["ready"] is True
    assert p["active_factors"][0]["key"] == "HY_SPREAD"  # 最大 contribution
    # 最後一個是 PMI（|0.2| 最小）
    assert p["active_factors"][-1]["key"] == "PMI"


def test_v19_17_top_n_caps_active_factors():
    indicators = {f"K{i}": _ind(f"K{i}", score=float(i), weight=1.0) for i in range(1, 11)}
    p = build_beginner_payload(indicators, {}, top_n=3)
    assert p["n_displayed"] == 3
    assert p["n_total"] == 10
    assert len(p["active_factors"]) == 3


def test_v19_17_top_n_zero_or_negative_returns_all():
    indicators = {f"K{i}": _ind(f"K{i}", score=1.0) for i in range(5)}
    p = build_beginner_payload(indicators, {}, top_n=0)
    assert p["n_displayed"] == 5
    p2 = build_beginner_payload(indicators, {}, top_n=-1)
    assert p2["n_displayed"] == 5


def test_v19_17_top_n_larger_than_total_caps_at_total():
    indicators = {"VIX": _ind("VIX", 1.0), "CPI": _ind("CPI", 0.5)}
    p = build_beginner_payload(indicators, {}, top_n=100)
    assert p["n_displayed"] == 2


# ════════════════════════════════════════════════
# verdict / score 計算
# ════════════════════════════════════════════════
def test_v19_17_total_score_sums_all_contributions():
    indicators = {
        "VIX":        _ind("VIX", score=2.0, weight=3.0),   # +6
        "HY_SPREAD":  _ind("HY",  score=-1.0, weight=2.0),  # -2
    }
    p = build_beginner_payload(indicators, {}, top_n=10)
    assert p["score"] == 4.0   # 6 + (-2)


def test_v19_17_verdict_level_matches_score_ranges():
    # 樂觀 (5 < x ≤ 10)
    indicators = {"VIX": _ind("VIX", score=7.0, weight=1.0)}
    p = build_beginner_payload(indicators, {}, top_n=1)
    assert p["verdict_level"] == "樂觀"
    # 中性 (-5 ≤ x ≤ 5)
    indicators = {"VIX": _ind("VIX", score=0.0, weight=1.0)}
    p = build_beginner_payload(indicators, {}, top_n=1)
    assert p["verdict_level"] == "中性"


def test_v19_17_verdict_oneline_contains_score_and_level():
    indicators = {"VIX": _ind("VIX", score=7.0, weight=1.0)}
    p = build_beginner_payload(indicators, {}, top_n=1)
    assert "+7.00" in p["verdict_oneline"]
    assert "樂觀" in p["verdict_oneline"]


# ════════════════════════════════════════════════
# 教學內容 / freq label
# ════════════════════════════════════════════════
def test_v19_17_edu_meaning_uses_macro_edu_when_present():
    indicators = {"VIX": _ind("VIX 恐慌", score=1.0, weight=1.0)}
    edu = {"VIX": {"meaning": "VIX 是 S&P 500 期權隱含波動率指標。"}}
    p = build_beginner_payload(indicators, edu, top_n=1)
    assert "S&P 500" in p["active_factors"][0]["edu_meaning"]


def test_v19_17_edu_meaning_fallback_when_macro_edu_missing():
    indicators = {"UNKNOWN_KEY": _ind("未知", score=1.0)}
    p = build_beginner_payload(indicators, {}, top_n=1)
    assert "暫無教學" in p["active_factors"][0]["edu_meaning"]


def test_v19_17_freq_label_correct_for_known_keys():
    indicators = {
        "VIX": _ind("VIX", 1.0),         # daily
        "JOBLESS": _ind("JOBLESS", 1.0), # weekly
        "PMI": _ind("PMI", 1.0),         # monthly
    }
    p = build_beginner_payload(indicators, {}, top_n=10)
    by_key = {r["key"]: r for r in p["active_factors"]}
    assert "🔥" in by_key["VIX"]["freq_label"]
    assert "📊" in by_key["JOBLESS"]["freq_label"]
    assert "🐌" in by_key["PMI"]["freq_label"]


def test_v19_17_freq_label_fallback_for_unknown_key():
    indicators = {"WEIRD_KEY": _ind("怪指標", 1.0)}
    p = build_beginner_payload(indicators, {}, top_n=1)
    assert p["active_factors"][0]["freq_label"] == FREQ_LABEL["unknown"]


# ════════════════════════════════════════════════
# why_bullets
# ════════════════════════════════════════════════
def test_v19_17_why_bullets_has_top_3_drivers():
    indicators = {
        f"K{i}": _ind(f"指標 {i}", score=float(10 - i), weight=1.0)
        for i in range(5)
    }
    p = build_beginner_payload(indicators, {}, top_n=5)
    assert len(p["why_bullets"]) == 3
    assert "🥇" in p["why_bullets"][0]
    assert "🥈" in p["why_bullets"][1]
    assert "🥉" in p["why_bullets"][2]


def test_v19_17_why_bullets_with_only_1_indicator_still_works():
    indicators = {"VIX": _ind("VIX", score=1.0)}
    p = build_beginner_payload(indicators, {}, top_n=1)
    assert len(p["why_bullets"]) == 1  # 不夠 3 個沒關係，至少 1
    assert "🥇" in p["why_bullets"][0]


# ════════════════════════════════════════════════
# NaN / 防呆
# ════════════════════════════════════════════════
def test_v19_17_nan_score_treated_as_zero():
    indicators = {"VIX": {"name": "VIX", "score": float("nan"), "weight": 1.0}}
    p = build_beginner_payload(indicators, {}, top_n=1)
    # NaN → 0，contribution 也 0
    assert p["active_factors"][0]["score"] == 0.0
    assert p["active_factors"][0]["contribution"] == 0.0


def test_v19_17_string_score_treated_as_zero():
    indicators = {"VIX": {"name": "VIX", "score": "bad", "weight": "x"}}
    p = build_beginner_payload(indicators, {}, top_n=1)
    assert p["active_factors"][0]["score"] == 0.0


def test_v19_17_indicator_without_score_key_skipped():
    """無 score 鍵 → 跳過（避免把 0.0 默認值當有效 score）"""
    indicators = {"VIX": {"name": "VIX 無 score", "weight": 1.0}}
    p = build_beginner_payload(indicators, {}, top_n=1)
    assert p["ready"] is False  # 唯一 indicator 被過濾 → empty


# ════════════════════════════════════════════════
# interpretation 7 級
# ════════════════════════════════════════════════
def test_v19_17_interpretation_extreme_bear_score():
    # v19.352 修正:fund 慣例負分 = 偏空/風險升高(對照 us_indicators 🔴=負分)
    indicators = {"VIX": _ind("VIX", score=-2.0)}
    p = build_beginner_payload(indicators, {}, top_n=1)
    assert "強烈偏空" in p["active_factors"][0]["interpretation"]


def test_v19_17_interpretation_neutral_zero_score():
    indicators = {"VIX": _ind("VIX", score=0.0)}
    p = build_beginner_payload(indicators, {}, top_n=1)
    assert "中性" in p["active_factors"][0]["interpretation"]


def test_v19_17_interpretation_strong_bull_score():
    # v19.352 修正:fund 慣例正分 = 偏多/風險下降(對照 us_indicators 🟢=正分)
    indicators = {"VIX": _ind("VIX", score=2.0)}
    p = build_beginner_payload(indicators, {}, top_n=1)
    assert "強烈偏多" in p["active_factors"][0]["interpretation"]
