# -*- coding: utf-8 -*-
"""🌍 頁用的行內 SVG 折線圖（純字串、零 streamlit、零網路、只用標準函式庫；不 import ui_v2）。

為什麼自己畫（Minimum-Cost 比較，PROJECT_RULES 9.2）：ui_v3 守衛禁止第三方套件（altair／pandas／plotly），而 `st.line_chart`
無法做「實線／虛線＋末點直接標籤＋各序列畫到自己的最後觀測日＋缺口斷線」；SVG 零依賴、可測、行動版 viewBox 可縮放。

規則（81 第 3.1、4 節；44 之十八其三）：
- 單 Y 軸、不畫 threshold／band／目標價線／方向箭頭、**不另畫 100 基準線**、不畫格線；
- x 軸依觀測日期等比例（休市與缺段如實留白）；缺值（None）處**斷線、不補、不畫零**；
- 非顏色辨識：實線／虛線＋末點直接標籤（預設顏色用 `currentColor`；只有呼叫端明確給 `Line.color`（客戶核准的 `chart.series.*`）時，
  線與末點圓用該色；**末點文字標籤一律 `currentColor`**，顏色只分辨哪一條、不代表好壞）；
- 每條線畫到**自己的**最後有效觀測日；末點標籤重疊時上下推開，**不縮字**。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from html import escape
from typing import Optional, Sequence, Tuple

WIDTH = 360
HEIGHT = 240
_PAD_LEFT, _PAD_RIGHT, _PAD_TOP, _PAD_BOTTOM = 40, 84, 14, 26
_LABEL_GAP = 14  # 末點標籤最小垂直間距（px）
# 迷你圖 viewBox 320×40（8:1）：CSS 讓它撐滿卡內寬、高度依比例（`height:auto`），**不**用 preserveAspectRatio="none"
# （那會讓末點圓變橢圓）；座標由 `spark_svg` 依 viewBox 重算，所以線與末點在任何卡寬都是等比縮放。
SPARK_WIDTH, SPARK_HEIGHT = 320, 40


@dataclass(frozen=True)
class Line:
    """一條線：`points` 為 `(obs_date ISO, value|None)`，日期嚴格遞增；`end_label` 為末點直接標籤（已格式化）。"""

    points: Tuple[Tuple[str, Optional[float]], ...]
    dashed: bool
    end_label: str
    color: Optional[str] = None   # None＝currentColor；否則須是 `#rrggbb`（客戶核准的 chart.series.* 值），不合法即 ValueError


_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


def _stroke_of(color: Optional[str]) -> str:
    if color is None:
        return "currentColor"
    if not _HEX_COLOR.match(color):
        raise ValueError(f"series 色必須是 #rrggbb：{color!r}")
    return color


def _ordinal(day: str) -> int:
    return date.fromisoformat(day).toordinal()


def _fmt_tick(value: float, span: float) -> str:
    return f"{value:.0f}" if span >= 20 else f"{value:.1f}" if span >= 2 else f"{value:.2f}"


def _segments(points, x_of, y_of) -> list:
    segments, current = [], []
    for day, value in points:
        if value is None:
            if current:
                segments.append(current)
            current = []
        else:
            current.append((x_of(_ordinal(day)), y_of(value)))
    if current:
        segments.append(current)
    return segments


def _path(segments) -> str:
    parts = []
    for seg in segments:
        if len(seg) == 1:   # 孤點：畫成一小段，不是消失
            x, y = seg[0]
            parts.append(f"M{x:.1f} {y:.1f}h0.01")
        else:
            parts.append("M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in seg))
    return " ".join(parts)


def _spread(ys: Sequence[float], lo: float, hi: float) -> list:
    """末點標籤的 y：由上而下排序後逐個至少隔 `_LABEL_GAP`，再整體夾回圖內。"""
    order = sorted(range(len(ys)), key=lambda i: ys[i])
    placed = {}
    prev = None
    for i in order:
        y = ys[i] if prev is None else max(ys[i], prev + _LABEL_GAP)
        placed[i] = y
        prev = y
    over = (max(placed.values()) - hi) if placed else 0
    if over > 0:
        placed = {i: max(lo, y - over) for i, y in placed.items()}
    return [placed[i] for i in range(len(ys))]


def line_chart_svg(lines: Sequence[Line], *, aria_label: str, width: int = WIDTH, height: int = HEIGHT) -> str:
    """多條線的折線圖。沒有任何有值的點 → `ValueError`（呼叫端先判，不畫空圖假裝有圖）。"""
    valued = [(d, v) for ln in lines for d, v in ln.points if v is not None]
    if not valued:
        raise ValueError("沒有任何有值的點不該畫圖（呼叫端應先判狀態）")
    days = [_ordinal(d) for ln in lines for d, _v in ln.points]
    lo_day, hi_day = min(days), max(days)
    vals = [v for _d, v in valued]
    lo_val, hi_val = min(vals), max(vals)
    if hi_val == lo_val:
        lo_val, hi_val = lo_val - 1.0, hi_val + 1.0
    pad = (hi_val - lo_val) * 0.06
    lo_val, hi_val = lo_val - pad, hi_val + pad
    left, right = _PAD_LEFT, width - _PAD_RIGHT
    top, bottom = _PAD_TOP, height - _PAD_BOTTOM

    def x_of(day: int) -> float:
        return (left + right) / 2 if hi_day == lo_day else left + (day - lo_day) / (hi_day - lo_day) * (right - left)

    def y_of(val: float) -> float:
        return top + (hi_val - val) / (hi_val - lo_val) * (bottom - top)

    out = [f'<svg class="uv3-chart" viewBox="0 0 {width} {height}" role="img" aria-label="{escape(aria_label, quote=True)}" '
           f'xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid meet">',
           f'<title>{escape(aria_label)}</title>']
    if any(ln.color is not None for ln in lines):
        # 高對比（forced-colors）：系統會收掉 currentColor 但不會改寫明確色碼；深藍在黑底高對比主題上會看不見 → 回到系統文字色，
        # 兩線改靠實線／虛線＋末點標籤分辨（非顏色辨識）
        out.append("<style>@media (forced-colors:active){.uv3-ln{stroke:CanvasText !important}.uv3-dot{fill:CanvasText !important}}</style>")
    span = hi_val - lo_val
    for tick in (hi_val - pad, (hi_val + lo_val) / 2, lo_val + pad):
        y = y_of(tick)
        out.append(f'<text x="{left - 6}" y="{y + 4:.1f}" text-anchor="end" font-size="11" fill="currentColor" '
                   f'opacity="0.7">{_fmt_tick(tick, span)}</text>')
    out.append(f'<line x1="{left}" y1="{bottom}" x2="{right}" y2="{bottom}" stroke="currentColor" opacity="0.35"/>')
    out.append(f'<text x="{left}" y="{height - 8}" text-anchor="start" font-size="11" fill="currentColor" opacity="0.7">'
               f'{date.fromordinal(lo_day).isoformat()}</text>')
    out.append(f'<text x="{right}" y="{height - 8}" text-anchor="end" font-size="11" fill="currentColor" opacity="0.7">'
               f'{date.fromordinal(hi_day).isoformat()}</text>')

    ends = []
    for ln in lines:
        segments = _segments(ln.points, x_of, y_of)
        dash = ' stroke-dasharray="6 4"' if ln.dashed else ""
        stroke = _stroke_of(ln.color)
        out.append(f'<path d="{_path(segments)}" fill="none" stroke="{stroke}" stroke-width="2"{dash} '
                   f'stroke-linejoin="round" stroke-linecap="round" class="uv3-ln"/>')
        last_x, last_y = segments[-1][-1] if segments else (None, None)
        ends.append((last_x, last_y, ln.end_label, stroke))
    labelled = [(x, y, t, c) for x, y, t, c in ends if x is not None]
    placed = _spread([y for _x, y, _t, _c in labelled], top + 6, bottom - 4)
    for (x, y, text, color), ly in zip(labelled, placed):
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{color}" class="uv3-dot"/>')
        out.append(f'<text x="{x + 6:.1f}" y="{ly + 4:.1f}" font-size="12" fill="currentColor">{escape(text)}</text>')
    out.append("</svg>")
    return "".join(out)


def spark_svg(points: Sequence[Tuple[str, Optional[float]]], *, aria_label: str,
              width: int = SPARK_WIDTH, height: int = SPARK_HEIGHT) -> str:
    """Secondary 迷你線：無座標軸、無文字；缺值斷線；最後一個有值點用圓點標出。"""
    valued = [(d, v) for d, v in points if v is not None]
    if not valued:
        raise ValueError("沒有任何有值的點不該畫迷你圖")
    lo_day, hi_day = _ordinal(points[0][0]), _ordinal(points[-1][0])
    vals = [v for _d, v in valued]
    lo, hi = min(vals), max(vals)
    pad = 3

    def x_of(day: int) -> float:
        return width / 2 if hi_day == lo_day else pad + (day - lo_day) / (hi_day - lo_day) * (width - 2 * pad)

    def y_of(val: float) -> float:
        return height / 2 if hi == lo else pad + (hi - val) / (hi - lo) * (height - 2 * pad)

    segments = _segments(points, x_of, y_of)
    last_x, last_y = segments[-1][-1]
    return (f'<svg class="uv3-spark" viewBox="0 0 {width} {height}" role="img" aria-label="{escape(aria_label, quote=True)}" '
            f'xmlns="http://www.w3.org/2000/svg"><title>{escape(aria_label)}</title>'
            f'<path d="{_path(segments)}" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>'
            f'<circle cx="{last_x:.1f}" cy="{last_y:.1f}" r="2.5" fill="currentColor"/></svg>')
