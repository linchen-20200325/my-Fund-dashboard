"""tests/test_chart_danger.py — add_danger_hlines helper 測試 (v19.145 Phase B)

對齊 Stock 端 test_render_smoke 的 add_danger_hlines 測試,Fund 端獨立 helper
有自己的測試保護(SSOT 22 不被改回 25 之類的回歸 + yref multi-axis + band 4 線)。
"""
from __future__ import annotations

import pytest

# 沒裝 plotly 的環境(罕見)→ skip
plotly = pytest.importorskip("plotly")

import plotly.graph_objects as go

from ui.helpers.chart_danger import add_danger_hlines


def test_high_bad_two_lines_with_ssot_values():
    """high_bad 指標(VIX)應加 2 條線:黃 22 / 紅 30(SSOT MACRO_THRESHOLDS,
    非舊 inline 25/30)。"""
    fig = go.Figure()
    add_danger_hlines(fig, "vix")
    ys = sorted(s.y0 for s in fig.layout.shapes)
    assert 22.0 in ys, f"VIX 黃線應為 SSOT 22(非舊 25),實際 {ys}"
    assert 30.0 in ys, f"VIX 紅線應為 SSOT 30,實際 {ys}"
    assert 25.0 not in ys, "VIX 不該再用舊的 inline 25"
    assert len(fig.layout.shapes) == 2


def test_low_bad_yield_curve():
    """low_bad 指標(10Y-2Y):黃 0.5 / 紅 0(倒掛)。"""
    fig = go.Figure()
    add_danger_hlines(fig, "yield_10y2y")
    ys = sorted(s.y0 for s in fig.layout.shapes)
    assert 0.0 in ys and 0.5 in ys
    assert len(fig.layout.shapes) == 2


def test_pmi_low_bad():
    """PMI low_bad:黃 50(收縮)/ 紅 46(嚴重)。"""
    fig = go.Figure()
    add_danger_hlines(fig, "pmi")
    ys = sorted(s.y0 for s in fig.layout.shapes)
    assert 46.0 in ys and 50.0 in ys


def test_yref_y2_for_multi_axis():
    """多軸圖指定 yref='y2' 應寫入 shape 的 yref 屬性。"""
    fig = go.Figure()
    add_danger_hlines(fig, "vix", yref="y2")
    assert all(s.yref == "y2" for s in fig.layout.shapes), \
        f"yref 應為 y2,實際 {[s.yref for s in fig.layout.shapes]}"


def test_unknown_key_noop_no_raise():
    """未知 key(筆誤防護)→ no-op,不 raise。"""
    fig = go.Figure()
    add_danger_hlines(fig, "totally_not_a_real_key")
    assert len(fig.layout.shapes) == 0


def _ann_texts(fig) -> list[str]:
    """plotly add_hline 把 annotation 存進 fig.layout.annotations(獨立於 shapes)。"""
    return [a.text for a in fig.layout.annotations if a.text]


def test_annotation_has_unit_and_emoji():
    """annotation_text 應含 emoji + 值 + unit(e.g. '🔴 紅線 30')。"""
    fig = go.Figure()
    add_danger_hlines(fig, "cpi_yoy")
    texts = _ann_texts(fig)
    assert any("🔴" in t for t in texts), f"應有紅線 emoji,實際 {texts}"
    assert any("🟡" in t for t in texts), f"應有黃線 emoji,實際 {texts}"
    assert any("%" in t for t in texts), f"CPI 應帶 % 單位,實際 {texts}"


def test_integer_values_no_decimals():
    """整數門檻(VIX 22/30)應顯示 22 / 30,不是 22.0 / 30.0(避免冗餘)。"""
    fig = go.Figure()
    add_danger_hlines(fig, "vix")
    texts = " ".join(_ann_texts(fig))
    assert "22.0" not in texts and "30.0" not in texts, \
        f"整數值不該帶 .0,實際 {texts}"
    assert " 22" in texts and " 30" in texts


def test_news_systemic_zero_decimals():
    """新聞桶 news_systemic(則數)decimals=0,annotation 應顯示 1/2 不是 1.0/2.0。"""
    fig = go.Figure()
    add_danger_hlines(fig, "news_systemic")
    texts = " ".join(_ann_texts(fig))
    assert " 1則" in texts and " 2則" in texts, \
        f"則數應整數,實際 {texts}"


def test_helper_is_pure_no_side_effects():
    """重複呼叫不互相干擾(同一 spec 加兩次只是疊兩組線,不會破壞前一個)。"""
    fig = go.Figure()
    add_danger_hlines(fig, "vix")
    add_danger_hlines(fig, "vix")
    # 第二次呼叫應該加另外 2 條,總共 4 條(不會干擾既有)
    assert len(fig.layout.shapes) == 4
