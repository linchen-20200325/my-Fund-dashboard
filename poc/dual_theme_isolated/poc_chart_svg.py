# -*- coding: utf-8 -*-
"""PoC 行內 SVG 折線圖（純字串；零 streamlit、零網路；只用標準函式庫）。

色一律走 CSS class（由 `poc_theme_css` 依目前 palette 產生），SVG 內不寫任何色碼；
非顏色辨識＝實線／虛線＋末點直接標籤＋圖例；有座標軸標籤與 <title>／<desc>。
"""
from __future__ import annotations

from html import escape

WIDTH, HEIGHT = 360, 240
_PL, _PR, _PT, _PB = 44, 74, 14, 30


def _pts(values, n, lo, hi):
    span = (hi - lo) or 1.0
    iw, ih = WIDTH - _PL - _PR, HEIGHT - _PT - _PB
    return [(_PL + iw * i / max(n - 1, 1), _PT + ih * (1 - (v - lo) / span)) for i, v in enumerate(values)]


def line_chart(lines, dates, *, title: str, desc: str) -> str:
    """lines：[(label, values, dashed)]；dates：與 values 等長。回 <svg> 字串。"""
    if not lines:
        raise ValueError("line_chart 需要至少一條線")
    n = len(dates)
    for label, values, _ in lines:
        if len(values) != n:
            raise ValueError(f"{label}: 數列長度與日期不一致")
    allv = [v for _, vals, _ in lines for v in vals]
    lo, hi = min(allv), max(allv)
    pad = (hi - lo) * 0.08 or 1.0
    lo, hi = lo - pad, hi + pad
    iw, ih = WIDTH - _PL - _PR, HEIGHT - _PT - _PB
    parts = [
        f'<svg class="poc-chart" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="poc-ct poc-cd" xmlns="http://www.w3.org/2000/svg">',
        f'<title id="poc-ct">{escape(title)}</title><desc id="poc-cd">{escape(desc)}</desc>',
        f'<line class="poc-axis" x1="{_PL}" y1="{_PT}" x2="{_PL}" y2="{_PT + ih}"/>',
        f'<line class="poc-axis" x1="{_PL}" y1="{_PT + ih}" x2="{_PL + iw}" y2="{_PT + ih}"/>',
    ]
    for frac in (0.0, 0.5, 1.0):
        v = lo + (hi - lo) * frac
        y = _PT + ih * (1 - frac)
        parts.append(f'<text class="poc-tick" x="{_PL - 6}" y="{y + 4:.1f}" text-anchor="end">{v:.0f}</text>')
    parts.append(f'<text class="poc-tick" x="{_PL}" y="{HEIGHT - 8}" text-anchor="start">{dates[0].isoformat()}</text>')
    parts.append(f'<text class="poc-tick" x="{_PL + iw}" y="{HEIGHT - 8}" text-anchor="end">{dates[-1].isoformat()}</text>')
    labels_y = []
    for label, values, dashed in lines:
        pts = _pts(values, n, lo, hi)
        d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        cls = "poc-line poc-dash" if dashed else "poc-line"
        parts.append(f'<path class="{cls}" d="{d}" fill="none"/>')
        ex, ey = pts[-1]
        while any(abs(ey - o) < 14 for o in labels_y):
            ey += 14
        labels_y.append(ey)
        parts.append(f'<text class="poc-endlabel" x="{ex + 5:.1f}" y="{ey + 4:.1f}">{escape(label)}</text>')
    parts.append("</svg>")
    return "".join(parts)


def legend(lines) -> str:
    """HTML 圖例：實線／虛線樣本＋文字（不靠顏色辨識）。"""
    items = []
    for label, _, dashed in lines:
        sample = "┄┄┄" if dashed else "───"
        kind = "虛線" if dashed else "實線"
        items.append(f'<span class="poc-legend-item"><span class="poc-legend-sample" aria-hidden="true">{sample}</span>{escape(label)}（{kind}）</span>')
    return '<div class="poc-legend">' + "".join(items) + "</div>"
