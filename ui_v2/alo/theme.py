# -*- coding: utf-8 -*-
"""色票常數 ＋ WCAG 2.2 AA 對比計算。零 streamlit import。

客戶逐字指定三個色：深色 app 底色 `#0e1117`、青色主色 `#0f6b6c`（深）／`#5fd3d0`（亮）。
**這三個一個字都不動**；其餘的色與姊妹頁 `ui_v2/exp/theme.py` 同值（同一套 token），
本檔**不 import** 它（各頁自足，見 `__init__`），而是逐值抄一份、在本檔自己的 `CONTRAST_PAIRS` 裡重算。

客戶 2026-09-22【基金頁設計引導】：一般文字 ≥ 4.5；大文字 ≥ 3；非文字 UI 元件 ≥ 3。
`44` 第五節共通硬要求逐字「狀態不靠顏色單獨辨識」—— 本頁每一個狀態都另有圖示與文字（見 `logic`）。

⚠️ 登記：`44` 第五節卡片表只宣告四狀態的**顏色語意**（中性／灰／黃／紅），**沒有宣告任何色碼**。
下面的色碼屬畫法不屬規格；判定住在 `logic`，回傳的是語意字串不是色碼。

~~⚠️ 本頁沒有紅色（登記 ALO-GAP-無紅燈）：資產配置頁八塊沒有一塊宣告紅。~~
→ **2026-09-24 就地更正（獨立稽核指出）**：上句只對 `ALO-0` 那一枚燈成立 ——
`ALO-0` 規則欄只給灰與黃（`ALO-GAP-無紅燈`）；而 `44` 第五節第五小節「系統錯誤」的通用模板是紅，
本頁在取數失敗時照它畫在受影響的卡與展開區（`ALO-GAP-取數失敗`）。**舊句說「一個紅都沒有」是錯的。**
存檔寫入失敗的框用灰（客戶 2026-09-24 裁「失敗框改灰」，同 `ui_v2/exp` 的畫法）。

⚠️ **前提（ALO-GAP-深色主題前提）**：下面每一組對比、以及畫面層那條瀏覽器實測，
都是在 repo 根的 `.streamlit/config.toml`（`base = "dark"`、`textColor = "#e6edf3"`）之下成立的。
輸入欄、展開區標題、按鈕這些 Streamlit 元件的字色來自那份設定，不在本頁的檔案裡；
那份設定不在本頁的檔案邊界內，換成淺色主題時本檔的結論不成立。
"""

from __future__ import annotations

# ── 客戶逐字指定（不得更動） ──
APP_BG = "#0e1117"
TEAL_DARK = "#0f6b6c"
TEAL_BRIGHT = "#5fd3d0"

# ── 與姊妹頁同值的其餘色（皆已在本檔逐組算過對比，見 `CONTRAST_PAIRS`） ──
SURFACE = "#161b22"        # 卡底
INPUT_BG = "#11161d"       # 輸入框底／格底
BUTTON_BG = "#21262d"      # 按鈕底
BORDER = "#30363d"         # 純裝飾分隔線（不是 UI 元件，門檻不適用；見檔尾）
EDGE = "#6b7682"           # 可操作控制項與狀態容器的邊界
PLACEHOLDER = "#7d858e"    # 輸入提示字

TEXT_PRIMARY = "#e6edf3"
TEXT_SECOND = "#c9d1d9"
TEXT_MUTED = "#8b949e"

# ── 狀態顏色語意 → 色碼（語意見 `44` 5.1 卡片表；本頁只用到中性／灰／黃） ──
STATE_GRAY = "#8b949e"
STATE_GRAY_BG = "#11161d"
STATE_WARN = "#e3b341"
STATE_ERR = "#ff4b4b"      # 與姊妹頁 hld／exp 同一個紅（44 5.5 系統錯誤）

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
    STATE_GRAY_BG,
    STATE_WARN,
    STATE_ERR,
)


def tone_hex(tone: str) -> str:
    """把 logic 回傳的顏色語意換成色碼。

    查不到就**炸**，不退回中性色 —— 退回中性色會讓一個本頁沒有宣告過的狀態
    （例如有人新增了一種語意卻沒有登記色碼與對比）在畫面上看起來像 `ok`（§1 Fail Loud）。
    """
    if tone not in TONE_HEX:
        raise KeyError(f"本頁沒有宣告這個顏色語意：{tone!r}")
    return TONE_HEX[tone]


# ───────────────────────── WCAG 2.x 對比 ─────────────────────────


def _channel(value: int) -> float:
    c = value / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(hex_color: str) -> float:
    text = hex_color.lstrip("#")
    red, green, blue = (int(text[i : i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _channel(red) + 0.7152 * _channel(green) + 0.0722 * _channel(blue)


def contrast_ratio(foreground: str, background: str) -> float:
    first, second = relative_luminance(foreground), relative_luminance(background)
    lighter, darker = max(first, second), min(first, second)
    return (lighter + 0.05) / (darker + 0.05)


# 本檔沒有用到「大文字只要 3」那一級的寬限，文字一律拿 4.5 去驗。
TEXT_FLOOR = 4.5
UI_FLOOR = 3.0

CONTRAST_PAIRS = (
    # ── 一般文字（門檻 4.5） ──
    ("主文字／頁底", TEXT_PRIMARY, APP_BG, TEXT_FLOOR),
    ("主文字／卡底", TEXT_PRIMARY, SURFACE, TEXT_FLOOR),
    ("主文字／格底", TEXT_PRIMARY, INPUT_BG, TEXT_FLOOR),
    ("主文字／按鈕底", TEXT_PRIMARY, BUTTON_BG, TEXT_FLOOR),
    ("次文字／卡底", TEXT_SECOND, SURFACE, TEXT_FLOOR),
    ("次文字／頁底", TEXT_SECOND, APP_BG, TEXT_FLOOR),
    ("弱文字／頁底", TEXT_MUTED, APP_BG, TEXT_FLOOR),
    ("弱文字／卡底", TEXT_MUTED, SURFACE, TEXT_FLOOR),
    ("弱文字／格底", TEXT_MUTED, INPUT_BG, TEXT_FLOOR),
    ("弱文字／按鈕底", TEXT_MUTED, BUTTON_BG, TEXT_FLOOR),
    ("灰態文字／卡底", STATE_GRAY, SURFACE, TEXT_FLOOR),
    ("灰態文字／頁底", STATE_GRAY, APP_BG, TEXT_FLOOR),
    ("灰態文字／灰態框底", STATE_GRAY, STATE_GRAY_BG, TEXT_FLOOR),
    ("黃態文字／卡底", STATE_WARN, SURFACE, TEXT_FLOOR),
    ("黃態文字／頁底", STATE_WARN, APP_BG, TEXT_FLOOR),
    ("紅態文字／卡底", STATE_ERR, SURFACE, TEXT_FLOOR),
    ("紅態文字／頁底", STATE_ERR, APP_BG, TEXT_FLOOR),
    ("輸入提示字／輸入框底", PLACEHOLDER, INPUT_BG, TEXT_FLOOR),
    ("輸入提示字／頁底", PLACEHOLDER, APP_BG, TEXT_FLOOR),
    ("青色標題／頁底", TEAL_BRIGHT, APP_BG, TEXT_FLOOR),
    ("青色標題／卡底", TEAL_BRIGHT, SURFACE, TEXT_FLOOR),
    # ── 非文字 UI 元件（門檻 3） ──
    ("控制項邊界／頁底", EDGE, APP_BG, UI_FLOOR),
    ("控制項邊界／卡底", EDGE, SURFACE, UI_FLOOR),
    ("控制項邊界／輸入框底", EDGE, INPUT_BG, UI_FLOOR),
    ("控制項邊界／按鈕底", EDGE, BUTTON_BG, UI_FLOOR),
    ("灰態框線／卡底", STATE_GRAY, SURFACE, UI_FLOOR),
    ("灰態框線／灰態框底", STATE_GRAY, STATE_GRAY_BG, UI_FLOOR),
    ("黃態框線／頁底", STATE_WARN, APP_BG, UI_FLOOR),
    ("黃態框線／卡底", STATE_WARN, SURFACE, UI_FLOOR),
    ("紅態框線／頁底", STATE_ERR, APP_BG, UI_FLOOR),
    ("紅態框線／卡底", STATE_ERR, SURFACE, UI_FLOOR),
    ("青色髮絲線／頁底", TEAL_DARK, APP_BG, UI_FLOOR),
    # ~~("青色髮絲線／卡底", TEAL_BRIGHT, SURFACE)~~ —— 名稱與實值不符（亮青在卡底上是標題字，
    # 那一組已由「青色標題／卡底」以文字門檻驗過）；頁面上的青色髮絲線是 TEAL_DARK 畫在頁底上，見上一列。
)

# ⚠️ `BORDER`（`#30363d`）刻意**不在**上表裡：它只用在卡內分隔線與表格格線，
#    不是控制項、不表示任何狀態，拿掉之後每一個字與每一個數照樣讀得到 ——
#    與 `ui_v2/exp/theme.py` 同一個判斷（線框那一組的分類，客戶未逐字裁，可推翻）。
