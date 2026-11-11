# -*- coding: utf-8 -*-
"""WCAG 2.x 對比度計算（本 PoC 自寫；含 alpha 合成）。純標準函式庫、無 streamlit、無瀏覽器。

- 相對亮度：sRGB 轉線性（門檻 0.04045；<=門檻用 c/12.92，否則 ((c+0.055)/1.055)^2.4）。
- alpha：`composite(fg_rgba, bg_rgb)` 在 sRGB 空間線性混合（與瀏覽器繪製一致）；半透明前景先合成到底色才算比值。
- 判定：一般文字 ≥ 4.5；大字（≥24px，或 ≥18.66px 且粗體）≥ 3；非文字（功能性邊界／圖形）≥ 3。
"""
from __future__ import annotations

import re
from typing import Iterable, Sequence, Tuple

RGB = Tuple[float, float, float]
RGBA = Tuple[float, float, float, float]

_RGB_RE = re.compile(r"^rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)(?:\s*[,/]\s*([\d.]+%?))?\s*\)$")
_SRGB_RE = re.compile(r"^color\(\s*srgb\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)(?:\s*/\s*([\d.]+%?))?\s*\)$")


def _alpha(tok) -> float:
    if tok is None:
        return 1.0
    return float(tok[:-1]) / 100 if tok.endswith("%") else float(tok)


def parse_color(css: str) -> RGBA:
    """`rgb()`／`rgba()`／`color(srgb …)`／`#rrggbb` → (r,g,b,a)（r,g,b 0–255）。無法解析＝Fail Loud。"""
    s = css.strip().lower()
    if s == "transparent":
        return (0.0, 0.0, 0.0, 0.0)
    m = _RGB_RE.match(s)
    if m:
        return (float(m.group(1)), float(m.group(2)), float(m.group(3)), _alpha(m.group(4)))
    m = _SRGB_RE.match(s)
    if m:
        return (float(m.group(1)) * 255, float(m.group(2)) * 255, float(m.group(3)) * 255, _alpha(m.group(4)))
    if re.fullmatch(r"#[0-9a-f]{6}", s):
        return (int(s[1:3], 16), int(s[3:5], 16), int(s[5:7], 16), 1.0)
    raise ValueError(f"無法解析的顏色：{css!r}")


def _lin(c: float) -> float:
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(rgb: Sequence[float]) -> float:
    r, g, b = rgb[0], rgb[1], rgb[2]
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def ratio(a: Sequence[float], b: Sequence[float]) -> float:
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def composite(fg: RGBA, bg: RGB) -> RGB:
    a = fg[3]
    return tuple(fg[i] * a + bg[i] * (1 - a) for i in range(3))  # type: ignore[return-value]


def effective_background(chain: Iterable[Tuple[str, float]], canvas: RGB = (255.0, 255.0, 255.0)) -> RGB:
    """chain：由**最內層到最外層**的 (backgroundColor, opacity)；由外向內逐層合成（含各層 opacity）。"""
    layers = list(chain)[::-1]
    bg = canvas
    for color, opacity in layers:
        rgba = parse_color(color)
        a = rgba[3] * opacity
        if a > 0:
            bg = composite((rgba[0], rgba[1], rgba[2], a), bg)
    return bg


def text_ratio(fg_css: str, bg_rgb: RGB, opacity: float = 1.0) -> float:
    fg = parse_color(fg_css)
    fg = (fg[0], fg[1], fg[2], fg[3] * opacity)
    return ratio(composite(fg, bg_rgb), bg_rgb)


def is_large_text(font_px: float, weight: int) -> bool:
    return font_px >= 24 or (font_px >= 18.66 and weight >= 700)


def required_text_ratio(font_px: float, weight: int) -> float:
    return 3.0 if is_large_text(font_px, weight) else 4.5


NON_TEXT_MIN = 3.0
