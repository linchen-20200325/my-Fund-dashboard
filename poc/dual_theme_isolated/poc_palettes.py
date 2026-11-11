# -*- coding: utf-8 -*-
"""PoC 雙套色票（非 production、非核准色票）。

- light：複製自 `ui_v3/design/tokens.py` 的 G3 核准值（**複製成 fixture**，不 import ui_v3；
  `tests/poc_dual_theme/test_poc_dual_theme_guard.py` 唯讀比對兩邊相等，防漂移）。
- dark：研究示例（`docs/evidence/fund_newui2_dual_theme_b_design_gate_2026_11_11.md` §四）— **僅作隔離 PoC 測試**（DEC-2026-11-11-02 T4）。
  標「PoC-only 變體」者為本 PoC 另選的值（研究文件只給候選或寫「需重算」），**不是**研究示例、更不是核准值。
- 顏色不是唯一訊號：狀態 chip 一律「符號＋字樣」。
"""
from __future__ import annotations

from types import MappingProxyType

# 與 `ui_v3.design.tokens.TONE_KEYS` 同名的四個語意色名（只作 fixture 鍵名）。
TONE_KEYS = ("neutral", "grey", "yellow", "red")

_LIGHT_TONES = {
    "neutral": {"text": "#172033", "background": "#e6eaf3", "border": "#7f8ca6"},
    "grey": {"text": "#172033", "background": "#e6eaf3", "border": "#7f8ca6"},
    "yellow": {"text": "#6b4a0a", "background": "#fbf0d6", "border": "#b7791f"},
    "red": {"text": "#8a1f12", "background": "#fbe6e2", "border": "#c0392b"},
}

# 暗色：neutral／grey 沿用 light 的「共色」現況（grey／neutral 是否分開屬客戶另行裁示，PoC 不動）。
_DARK_TONES = {
    # PoC-only 變體：研究只給 text 候選，背景／邊為本 PoC 另選。
    "neutral": {"text": "#e6edf3", "background": "#222d4a", "border": "#8a9bc4"},
    "grey": {"text": "#e6edf3", "background": "#222d4a", "border": "#8a9bc4"},
    "yellow": {"text": "#e8b84a", "background": "#2d2610", "border": "#e8b84a"},  # text／border＝研究候選 #e8b84a；底為 PoC-only
    "red": {"text": "#ff8a7a", "background": "#3a1c1f", "border": "#ff8a7a"},      # text／border＝研究候選 #ff8a7a；底為 PoC-only
}

LIGHT = MappingProxyType({
    "mode": "light",
    "color_scheme": "light",
    "page_bg": "#f5f7fb",          # ui_v3 color.page.bg
    "surface": "#ffffff",          # ui_v3 color.surface
    "text": "#172033",             # ui_v3 color.text.primary
    "text2": "#4a5670",            # ui_v3 color.text.secondary
    "primary": "#1a5fd0",          # ui_v3 color.primary
    "card_border": "#7f8ca6",      # ui_v3 color.card.border
    "control_border": "#7f8ca6",   # PoC：原生控件邊界（light 沿用 card.border）
    "hover_bg": "#e9eef8",         # PoC-only（ui_v3 沒有 hover token）
    "focus_ring": "#1a5fd0",       # PoC-only（＝primary）
    "disabled_text": "#6b7690",    # PoC-only
    "sidebar_bg": "#101a33",       # ui_v3 color.sidebar.bg
    "sidebar_text": "#e6edf3",     # ui_v3 color.sidebar.text
    "sidebar_border": "#34466e",   # ui_v3 color.sidebar.border
    "tones": MappingProxyType({k: MappingProxyType(v) for k, v in _LIGHT_TONES.items()}),
})

DARK = MappingProxyType({
    "mode": "dark",
    "color_scheme": "dark",
    "page_bg": "#0f1626",          # 研究示例 頁面底
    "surface": "#172036",          # 研究示例 卡片面
    "text": "#e6edf3",             # 研究示例 主要文字
    "text2": "#a9b4c9",            # 研究示例 次要文字
    "primary": "#5b9dff",          # 研究示例 primary
    "card_border": "#5a6c94",      # 研究示例 卡片邊（對比由測試重算，見 evidence）
    "control_border": "#8a9bc4",   # PoC-only 變體：原生控件邊界需 ≥3:1，研究示例 #5a6c94 不足時改用
    "hover_bg": "#22304f",         # PoC-only
    "focus_ring": "#8bbaff",       # PoC-only
    "disabled_text": "#8d98b0",    # PoC-only
    "sidebar_bg": "#0a101f",       # PoC-only（深於頁面底，維持「側欄較深」層次）
    "sidebar_text": "#e6edf3",     # 沿用 light 側欄字
    "sidebar_border": "#34466e",   # 沿用 light 側欄邊
    "tones": MappingProxyType({k: MappingProxyType(v) for k, v in _DARK_TONES.items()}),
})

PALETTES = MappingProxyType({"light": LIGHT, "dark": DARK})
DEFAULT_MODE = "light"
MODES = ("light", "dark")


def get(mode: str):
    """未知模式一律 Fail Loud（不退回預設）。"""
    if mode not in PALETTES:
        raise ValueError(f"未知的 PoC 模式：{mode!r}（只接受 {MODES}）")
    return PALETTES[mode]


def all_hex(palette) -> set:
    """palette 內全部 #rrggbb 值（含 tones）。"""
    out = set()
    for k, v in palette.items():
        if isinstance(v, str) and v.startswith("#"):
            out.add(v.lower())
    for tone in palette["tones"].values():
        out.update(x.lower() for x in tone.values())
    return out
