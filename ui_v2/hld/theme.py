# -*- coding: utf-8 -*-
"""色票常數 ＋ WCAG 2.2 AA 對比計算。零 streamlit import。

客戶逐字指定三個色：深色 app 底色 `#0e1117`、青色主色 `#0f6b6c`（深）／`#5fd3d0`（亮）。
**這三個一個字都不動**；其餘的色由草稿 `ui_prototype_hld.html` §J 調校過並在本檔沿用。

客戶 2026-09-22【基金頁設計引導】逐字：
  「一般文字 ≥ 4.5:1；大文字 ≥ 3:1；非文字 UI 元件 ≥ 3:1」

本檔把「算對比」寫成可執行的函式，並把每一組前景／背景連同它該過的門檻
列進 `CONTRAST_PAIRS` —— 測試逐組算一次，未達標數必須為 0。
**不是目測、也不是引用草稿上的數字**：`contrast_ratio` 自己算，
而它算出來的值與草稿 §J 公布的數逐一對得上（測試裡釘了五組）。

⚠️ 登記（SSOT 未定，本檔未自行發明規格）：
`44` 第五節卡片表只宣告四狀態的**顏色語意**（中性／灰／黃／紅），**沒有宣告任何色碼**。
下面的色碼取自客戶已拍板的草稿 §J（那一節逐組算過對比），屬**畫法**不屬規格；
換色不影響任何判定 —— 判定住在 `logic.tone_for_state`，回傳的是語意字串不是色碼。

⚠️ 本檔只涵蓋**深色 app 螢幕**那一層。草稿另有淺色／深色「註記層」（審稿用的圖紙），
那一層在本實作裡**不存在**，故其對比組不在本檔的母體內。
"""

from __future__ import annotations

# ── 客戶逐字指定（不得更動） ──
APP_BG = "#0e1117"
TEAL_DARK = "#0f6b6c"
TEAL_BRIGHT = "#5fd3d0"

# ── 由草稿 §J 沿用的其餘色（皆已逐組算過對比） ──
SURFACE = "#161b22"        # 卡底
INPUT_BG = "#11161d"       # 輸入框底
BUTTON_BG = "#21262d"      # 按鈕底（對比最嚴的一組底色）
BORDER = "#30363d"         # 純裝飾分隔線（草稿 §J 判為非 UI 元件，門檻不適用）
EDGE = "#6b7682"           # 可操作控制項與狀態容器的邊界（≥3）
PLACEHOLDER = "#7d858e"    # 輸入提示字（草稿 §J：#5c666f → #7d858e）

TEXT_PRIMARY = "#e6edf3"
TEXT_SECOND = "#c9d1d9"
TEXT_MUTED = "#8b949e"

# ── 四狀態的顏色語意 → 色碼（語意見 `44` 5.1 卡片表） ──
STATE_GRAY = "#8b949e"
STATE_WARN = "#e3b341"
STATE_WARN_BG = "#241d07"
STATE_ERR = "#ff4b4b"
STATE_ERR_BG = "#2b1114"
ERR_MSG_FG = "#ffb4b4"     # 失敗訊息原文
ERR_MSG_BG = "#1b1114"
ERR_MSG_EDGE = "#a24651"   # 失敗訊息框線（草稿 §J：#4a2029 → #a24651）

TONE_HEX = {
    "中性": TEXT_PRIMARY,
    "灰": STATE_GRAY,
    "黃": STATE_WARN,
    "紅": STATE_ERR,
}

ALL_COLORS = (
    APP_BG,
    TEAL_DARK,
    TEAL_BRIGHT,
    SURFACE,
    INPUT_BG,
    BUTTON_BG,
    BORDER,
    EDGE,
    PLACEHOLDER,
    TEXT_PRIMARY,
    TEXT_SECOND,
    TEXT_MUTED,
    STATE_GRAY,
    STATE_WARN,
    STATE_WARN_BG,
    STATE_ERR,
    STATE_ERR_BG,
    ERR_MSG_FG,
    ERR_MSG_BG,
    ERR_MSG_EDGE,
)


def tone_hex(tone: str) -> str:
    """把 logic 回傳的顏色語意換成色碼。查不到就回中性色，不猜。"""
    return TONE_HEX.get(tone, TEXT_PRIMARY)


# ───────────────────────── WCAG 2.x 對比 ─────────────────────────


def _channel(value: int) -> float:
    c = value / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(hex_color: str) -> float:
    """WCAG 2.x 相對亮度。輸入為 `#rrggbb`。"""
    text = hex_color.lstrip("#")
    red, green, blue = (int(text[i : i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _channel(red) + 0.7152 * _channel(green) + 0.0722 * _channel(blue)


def contrast_ratio(foreground: str, background: str) -> float:
    """WCAG 2.x 對比值。回傳 1.0 ~ 21.0。"""
    first, second = relative_luminance(foreground), relative_luminance(background)
    lighter, darker = max(first, second), min(first, second)
    return (lighter + 0.05) / (darker + 0.05)


# 門檻：一般文字 4.5／非文字 UI 元件 3。
# ⚠️ 本檔**沒有用到「大文字只要 3」那一級的寬限** —— 頁面上最大的那幾個字
#    用的都是主文字色，算出來遠高於 4.5，所以一律拿 4.5 去驗（同草稿 §J 的做法）。
TEXT_FLOOR = 4.5
UI_FLOOR = 3.0

CONTRAST_PAIRS = (
    # ── 一般文字（門檻 4.5） ──
    ("主文字／頁底", TEXT_PRIMARY, APP_BG, TEXT_FLOOR),
    ("主文字／卡底", TEXT_PRIMARY, SURFACE, TEXT_FLOOR),
    ("次文字／卡底", TEXT_SECOND, SURFACE, TEXT_FLOOR),
    ("弱文字／頁底", TEXT_MUTED, APP_BG, TEXT_FLOOR),
    ("弱文字／卡底", TEXT_MUTED, SURFACE, TEXT_FLOOR),
    ("弱文字／輸入框底", TEXT_MUTED, INPUT_BG, TEXT_FLOOR),
    ("弱文字／按鈕底", TEXT_MUTED, BUTTON_BG, TEXT_FLOOR),
    ("資料未備的灰／卡底", STATE_GRAY, SURFACE, TEXT_FLOOR),
    ("資料未備的灰／頁底", STATE_GRAY, APP_BG, TEXT_FLOOR),
    ("不適用的黃／黃態卡底", STATE_WARN, STATE_WARN_BG, TEXT_FLOOR),
    ("不適用的黃／卡底", STATE_WARN, SURFACE, TEXT_FLOOR),
    ("不適用的黃／頁底", STATE_WARN, APP_BG, TEXT_FLOOR),
    ("取數失敗的紅／紅態卡底", STATE_ERR, STATE_ERR_BG, TEXT_FLOOR),
    ("取數失敗的紅／卡底", STATE_ERR, SURFACE, TEXT_FLOOR),
    ("取數失敗的紅／頁底", STATE_ERR, APP_BG, TEXT_FLOOR),
    ("失敗訊息原文／訊息底", ERR_MSG_FG, ERR_MSG_BG, TEXT_FLOOR),
    ("輸入提示字／輸入框底", PLACEHOLDER, INPUT_BG, TEXT_FLOOR),
    ("青色標題／頁底", TEAL_BRIGHT, APP_BG, TEXT_FLOOR),
    ("青色標題／卡底", TEAL_BRIGHT, SURFACE, TEXT_FLOOR),
    ("青色標題／按鈕底", TEAL_BRIGHT, BUTTON_BG, TEXT_FLOOR),
    # ── 非文字 UI 元件（門檻 3） ──
    ("控制項邊界／頁底", EDGE, APP_BG, UI_FLOOR),
    ("控制項邊界／卡底", EDGE, SURFACE, UI_FLOOR),
    ("控制項邊界／輸入框底", EDGE, INPUT_BG, UI_FLOOR),
    ("控制項邊界／按鈕底", EDGE, BUTTON_BG, UI_FLOOR),
    ("黃態卡框／頁底", STATE_WARN, APP_BG, UI_FLOOR),
    ("黃態卡框／黃態卡底", STATE_WARN, STATE_WARN_BG, UI_FLOOR),
    ("紅態卡框／頁底", STATE_ERR, APP_BG, UI_FLOOR),
    ("紅態卡框／紅態卡底", STATE_ERR, STATE_ERR_BG, UI_FLOOR),
    ("失敗訊息框線／訊息底", ERR_MSG_EDGE, ERR_MSG_BG, UI_FLOOR),
    ("灰燈圓點／卡底", STATE_GRAY, SURFACE, UI_FLOOR),
    ("青色髮絲線／頁底", TEAL_DARK, APP_BG, UI_FLOOR),
    ("青色髮絲線／卡底", TEAL_BRIGHT, SURFACE, UI_FLOOR),
)

# ⚠️ `BORDER`（`#30363d`）刻意**不在**上表裡：草稿 §J 把它與同型的幾條
#    逐條判為「純裝飾分隔線，不是非文字 UI 元件」（不是控制項、不表示任何狀態，
#    拿掉之後每一個字與每一個數照樣讀得到），門檻不適用。
#    **那是草稿那一組的分類判斷，客戶未逐字裁，可推翻** —— 本檔沿用並照實登記，
#    不自行把它改成「已達標」。
