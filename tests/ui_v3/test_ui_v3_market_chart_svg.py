# -*- coding: utf-8 -*-
"""🌍 行內 SVG 圖（`ui_v3/pages/chart_svg.py`）：缺口斷線不補、實線／虛線、各畫到自己的最後一天、不畫 100 基準線／格線、標籤不重疊。"""
from __future__ import annotations

import re

import pytest

from ui_v3.pages import chart_svg as svg


def _line(points, dashed=False, label="L"):
    return svg.Line(tuple(points), dashed, label)


def _paths(html):
    return re.findall(r'<path d="([^"]*)"', html)


def test_gap_breaks_the_path_and_is_never_filled():
    html = svg.line_chart_svg([_line([("2026-01-01", 100.0), ("2026-01-02", 101.0), ("2026-01-05", None),
                                      ("2026-01-06", 103.0), ("2026-01-07", 104.0)])], aria_label="t")
    (d,) = _paths(html)
    assert d.count("M") == 2, d   # 兩段，缺口處斷開


def test_single_isolated_point_is_still_drawn():
    html = svg.line_chart_svg([_line([("2026-01-01", 100.0), ("2026-01-02", None), ("2026-01-03", 101.0),
                                      ("2026-01-04", None)])], aria_label="t")
    assert _paths(html)[0].count("M") == 2


def test_second_line_is_dashed_and_first_is_solid():
    html = svg.line_chart_svg([_line([("2026-01-01", 1.0), ("2026-01-02", 2.0)]),
                               _line([("2026-01-01", 1.0), ("2026-01-02", 3.0)], dashed=True)], aria_label="t")
    paths = re.findall(r"<path [^>]*>", html)
    assert "stroke-dasharray" not in paths[0] and "stroke-dasharray" in paths[1]
    assert "stroke=\"currentColor\"" in paths[0]   # 不指定色碼


def test_no_baseline_grid_or_threshold_elements():
    html = svg.line_chart_svg([_line([("2026-01-01", 100.0), ("2026-01-02", 110.0)])], aria_label="t")
    assert html.count("<line ") == 1   # 只有底部座標軸線；沒有格線／基準線／band
    assert "<rect" not in html and "polygon" not in html and "marker" not in html


def test_each_line_ends_at_its_own_last_date_and_x_is_proportional_to_dates():
    a = _line([("2026-01-01", 100.0), ("2026-01-11", 110.0)], label="A")
    b = _line([("2026-01-01", 100.0), ("2026-01-06", 105.0)], label="B")
    html = svg.line_chart_svg([a, b], aria_label="t")
    pa, pb = (re.findall(r"[ML]([\d.]+) ", p) for p in _paths(html))
    assert float(pb[-1]) < float(pa[-1])
    # B 在 A 的一半日期（5/10 天）→ x 約在中點
    left, right = svg._PAD_LEFT, svg.WIDTH - svg._PAD_RIGHT
    assert float(pb[-1]) == pytest.approx(left + (right - left) / 2, abs=0.2)
    assert float(pa[-1]) == pytest.approx(right, abs=0.2)


def test_end_labels_do_not_overlap_even_when_values_are_equal():
    lines = [_line([("2026-01-01", 100.0), ("2026-01-10", 120.0)], label="台股 120.0"),
             _line([("2026-01-01", 100.0), ("2026-01-10", 120.0)], dashed=True, label="S&amp;P 120.0")]
    ys = [float(y) for y in re.findall(r'<text x="[\d.]+" y="([\d.]+)" font-size="12"', svg.line_chart_svg(lines, aria_label="t"))]
    assert len(ys) == 2 and abs(ys[0] - ys[1]) >= svg._LABEL_GAP - 0.01


def test_labels_are_escaped_and_axis_dates_are_iso():
    html = svg.line_chart_svg([_line([("2026-01-01", 1.0), ("2026-01-09", 2.0)], label="S&P <500>")], aria_label='a"b')
    assert "S&amp;P &lt;500&gt;" in html and 'aria-label="a&quot;b"' in html
    assert "2026-01-01" in html and "2026-01-09" in html


def test_no_valued_points_fails_loud_instead_of_drawing_an_empty_chart():
    with pytest.raises(ValueError):
        svg.line_chart_svg([_line([("2026-01-01", None)])], aria_label="t")
    with pytest.raises(ValueError):
        svg.spark_svg([("2026-01-01", None), ("2026-01-02", None)], aria_label="t")


def test_flat_series_does_not_divide_by_zero():
    assert "<svg" in svg.line_chart_svg([_line([("2026-01-01", 5.0), ("2026-01-02", 5.0)])], aria_label="t")
    assert "<svg" in svg.spark_svg([("2026-01-01", 5.0), ("2026-01-02", 5.0)], aria_label="t")


def test_spark_is_axisless_and_breaks_at_gaps():
    html = svg.spark_svg([("2026-01-01", 1.0), ("2026-01-02", None), ("2026-01-03", 2.0), ("2026-01-04", 3.0)], aria_label="t")
    assert "<text" not in html and "<line" not in html
    assert _paths(html)[0].count("M") == 2


# ───────── 比較圖雙系列色票方案 A（客戶 2026-11-21 正式裁示；Line.color 只接受 #rrggbb，預設 currentColor）─────────

def test_line_color_default_is_current_color_for_path_and_end_dot():
    html = svg.line_chart_svg([_line([("2026-01-01", 1.0), ("2026-01-02", 2.0)])], aria_label="t")
    assert 'stroke="currentColor"' in html and '<circle' in html and 'fill="currentColor" class="uv3-dot"/>' in html


def test_line_color_applies_to_path_and_end_dot_but_never_to_label_text_or_axes():
    a = svg.Line((("2026-01-01", 1.0), ("2026-01-02", 2.0)), False, "台股 2.0", "#0a3f86")
    b = svg.Line((("2026-01-01", 1.0), ("2026-01-02", 3.0)), True, "S&P 500 3.0", "#d06a00")
    html = svg.line_chart_svg([a, b], aria_label="t")
    paths = re.findall(r"<path [^>]*>", html)
    assert 'stroke="#0a3f86"' in paths[0] and "stroke-dasharray" not in paths[0]
    assert 'stroke="#d06a00"' in paths[1] and 'stroke-dasharray="6 4"' in paths[1]
    assert 'fill="#0a3f86"' in html and 'fill="#d06a00"' in html            # 末點圓
    for label in re.findall(r"<text [^>]*>[^<]*(?:台股|S&amp;P)[^<]*</text>", html):
        assert 'fill="currentColor"' in label, label                        # 文字標籤不上色（橙對白僅 3.66:1，不足文字 4.5:1）
    assert 'stroke="currentColor" opacity="0.35"' in html                    # x 軸線不上色


@pytest.mark.parametrize("bad", ["red", "#fff", "#12345g", "#0a3f86; fill:red", 'x" onload="y'])
def test_line_color_rejects_anything_but_hex6(bad):
    with pytest.raises(ValueError):
        svg.line_chart_svg([svg.Line((("2026-01-01", 1.0), ("2026-01-02", 2.0)), False, "L", bad)], aria_label="t")


def test_series_tokens_are_exactly_the_approved_values_and_other_chart_tokens_stay_unvalued():
    from ui_v3.design import tokens
    assert tokens.value("chart.series.1") == "#0a3f86" and tokens.value("chart.series.2") == "#d06a00"
    for name in ("chart.height.primary", "chart.height.secondary", "chart.period"):
        assert tokens.TOKENS[name].value is None, name


def test_forced_colors_fallback_style_present_only_when_a_series_colour_is_given():
    plain = svg.line_chart_svg([_line([("2026-01-01", 1.0), ("2026-01-02", 2.0)])], aria_label="t")
    coloured = svg.line_chart_svg([svg.Line((("2026-01-01", 1.0), ("2026-01-02", 2.0)), False, "L", "#0a3f86")], aria_label="t")
    assert "forced-colors" not in plain and "forced-colors" in coloured and "CanvasText" in coloured
