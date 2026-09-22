# -*- coding: utf-8 -*-
"""色票常數。零 streamlit import。

客戶逐字指定三個色：深色 app 底色 #0e1117、青色主色 #0f6b6c（深）／#5fd3d0（亮）。
其餘為由它們推導的中性色。

⚠️ 登記（SSOT 未定，本檔未自行發明規格）：
`44` 第五節卡片那張表只宣告四狀態的**顏色語意**（中性／灰／黃／紅），
**沒有宣告任何色碼**。下面 `TONE_HEX` 的四個十六進位值是為了在深色底上讀得出來
而挑的，屬畫法不屬規格；客戶要換直接換，換了不影響任何判定
（判定住在 logic.tone_for_state，回傳的是語意字串不是色碼）。
"""

# ── 客戶逐字指定 ──
APP_BG = "#0e1117"
TEAL_DARK = "#0f6b6c"
TEAL_BRIGHT = "#5fd3d0"

# ── 由上面三色推導的中性色（深色 app 螢幕用）──
TEXT_PRIMARY = "#e6edf3"
TEXT_MUTED = "#8b949e"
SURFACE = "#161b22"
BORDER = "#2d333b"

# ── 四狀態的顏色語意 → 色碼（語意見 `44` 第五節卡片表）──
TONE_HEX = {
    "中性": TEXT_PRIMARY,
    "灰": "#9aa4b2",
    "黃": "#e3b341",
    "紅": "#f85149",
}


def tone_hex(tone: str) -> str:
    """把 logic 回傳的顏色語意換成色碼。查不到就回中性色，不猜。"""
    return TONE_HEX.get(tone, TEXT_PRIMARY)
