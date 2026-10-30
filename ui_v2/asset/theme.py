# -*- coding: utf-8 -*-
"""💼 我的資產頁的色票：直接沿用 `ui_v2/alo/theme.py`（同一套淺色 token、四狀態語意；本檔不新增任何色碼）。零 streamlit import。"""

from __future__ import annotations

from ..alo.theme import (  # noqa: F401  —— 再輸出；對比由 alo 的 CONTRAST_PAIRS 守
    APP_BG, BORDER, EDGE, STATE_GRAY, STATE_GRAY_BG, SURFACE, TEAL_DARK, TEXT_MUTED, TEXT_PRIMARY, TEXT_SECOND, tone_hex,
)
