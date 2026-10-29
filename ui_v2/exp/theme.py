# -*- coding: utf-8 -*-
"""色票常數 ＋ WCAG 2.2 AA 對比計算。零 streamlit import。

客戶逐字指定三個色：~~深色 app 底色 `#0e1117`~~、青色主色 `#0f6b6c`（深）／`#5fd3d0`（亮）。
（⚠️ 2026-10-27 更正，`DEC-2026-10-27-09`，決策者：客戶：「深色 app 底色」一項已取代為淺色主內容區（深色只在殼層側欄）；
本句與下面「這三個一個字都不動」描述的是當時的指定，青色兩值仍然有效。見下方 token 區的說明。）
**這三個一個字都不動**；其餘的色逐值取自已拍板的草稿 `ui_prototype_exp.html`
（該檔自陳「視覺參考 ui_prototype_hld.html（同一套 token，未改一字）」）。

客戶 2026-09-22【基金頁設計引導】逐字：
  「一般文字 ≥ 4.5:1；大文字 ≥ 3:1；非文字 UI 元件 ≥ 3:1」

本檔把「算對比」寫成可執行的函式，並把每一組前景／背景連同它該過的門檻
列進 `CONTRAST_PAIRS` —— 測試逐組算一次，未達標數必須為 0。
**不是目測、也不是引用草稿上的數字**：`contrast_ratio` 自己算。

⚠️ 登記（SSOT 未定，本檔未自行發明規格）：
`44` 第五節卡片表只宣告四狀態的**顏色語意**（中性／灰／黃／紅），**沒有宣告任何色碼**。
下面的色碼屬**畫法**不屬規格；換色不影響任何判定 —— 判定住在 `logic.tone_for_state`，
回傳的是語意字串不是色碼。

⚠️ **紅色這一組的來歷，據實寫明（本組判讀，可推翻）**：
已拍板的草稿 `ui_prototype_exp.html` 的 §J 自陳「app 螢幕裡沒有紅色狀態色」，
理由是它畫的那七種狀態裡沒有取數失敗那一種。
**但 `44` 的 `EXP-0` 規則欄逐字要求「本塊讀到的那兩塊任一為 `系統錯誤` → 燈為紅」** ——
草稿與 `44` 在這一點上不一致，而**那份草稿自己的頁尾寫著兩者衝突時以 `44` 為準**。
故本頁**必須**有一組紅。本檔取的是姊妹頁 `ui_v2/hld/theme.py` 已經逐組算過對比的那一組
（`#ff4b4b` 系），**不自行調一組新的**。**這是本組的取法，客戶沒有裁過。**

⚠️ 本檔只涵蓋**深色 app 螢幕**那一層。草稿另有淺色／深色「註記層」（審稿用的圖紙），
那一層在本實作裡**不存在**，故其對比組不在本檔的母體內。
"""

from __future__ import annotations

# ── 2026-10-27 殼層批（BL-0484；`DEC-2026-10-27-09`，決策者：客戶；**只限視覺 theme**）：主內容區改淺色（深色在側欄，殼層自己的一組色）。
# 下面各 token 的值由深色版換成淺色版；舊值在寫下當時為真，被權衡掉的是「主內容區也深色」。**未動**：客戶逐字指定的青色
# `TEAL_DARK`／`TEAL_BRIGHT` 兩個值（`TEAL_DARK` 在淺底上當青色標題字，`TEAL_BRIGHT` 留給深色側欄）、任何判定、文案、44 塊定義。
# 每一組前景／背景的對比仍由本檔的 `CONTRAST_PAIRS` 逐組重算（測試母體），數值取自 GitHub Primer 的淺色色階。 ──
# ── 客戶逐字指定（青色兩值不得更動；`APP_BG` 的深色已由 `DEC-2026-10-27-09` 取代為淺色，見上方說明） ──
APP_BG = "#f6f8fa"
TEAL_DARK = "#0f6b6c"
TEAL_BRIGHT = "#5fd3d0"

# ── 由草稿沿用的其餘色（皆已逐組算過對比，見 `CONTRAST_PAIRS`） ──
SURFACE = "#ffffff"        # 卡底（草稿 --app-card）
INPUT_BG = "#ffffff"       # 輸入框底／格底（草稿 --st-gray-bg，與格底同值）
BUTTON_BG = "#eaeef2"      # 按鈕底（對比最嚴的一組底色）
BORDER = "#d0d7de"         # 純裝飾分隔線（草稿 §J 判為非 UI 元件，門檻不適用）
EDGE = "#6e7781"           # 可操作控制項與狀態容器的邊界（≥3，草稿 --app-edge）
PLACEHOLDER = "#59636e"    # 輸入提示字（草稿 --app-ph）

TEXT_PRIMARY = "#1f2328"   # 草稿 --app-fg
TEXT_SECOND = "#424a53"
TEXT_MUTED = "#59636e"     # 草稿 --app-muted

# ── 四狀態的顏色語意 → 色碼（語意見 `44` 5.1 卡片表） ──
STATE_GRAY = "#59636e"     # 草稿 --st-gray
STATE_GRAY_BG = "#eef1f4"  # 草稿 --st-gray-bg（客戶 2026-09-24 裁「失敗框改灰」用的底）
STATE_WARN = "#8a5a00"     # 草稿 --st-warn-fg
STATE_WARN_BG = "#fff8c5"  # 草稿 --st-warn-bg
STATE_ERR = "#cf222e"
STATE_ERR_BG = "#ffebe9"
ERR_MSG_FG = "#82071e"     # 失敗訊息原文
ERR_MSG_BG = "#fff1f0"
ERR_MSG_EDGE = "#cf222e"   # 失敗訊息框線

TONE_HEX = {
    "中性": TEXT_PRIMARY,
    "灰": STATE_GRAY,
    "黃": STATE_WARN,
    "紅": STATE_ERR,
}

ALL_COLORS = (
    APP_BG,
    TEAL_DARK,
    # `TEAL_BRIGHT`（客戶逐字指定的亮青）2026-10-27 起不再畫在主內容區（淺底上改用 `TEAL_DARK` 當青色標題字，見上方說明），
    # 只留給殼層的深色側欄（`ui_v2/shell_nav.py::NAV_ACCENT`，同值）；故不在本母體裡。常數本身仍保留（值仍鎖在測試裡）。
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
    STATE_WARN_BG,
    STATE_ERR,
    STATE_ERR_BG,
    ERR_MSG_FG,
    ERR_MSG_BG,
    ERR_MSG_EDGE,
)


# 規則 10（客戶 2026-10-14 裁示：來源要顯示、但不新增主表欄位）：值旁的簡短來源標示 `.exp-src`。
# 顏色用弱文字 `TEXT_MUTED`（上方對比表「弱文字／卡底」「弱文字／格底」兩組已算過 ≥ 4.5）；
# 刻意**不是**藥丸形、沒有框線 —— 它不是 `44` 5.2 的徽章（徽章是封閉列舉，來源標示不在其中）。
# `page.py` 把它接在 `<style>` 最後；完整說明在 tooltip（`title` 屬性），這裡只管樣式。
SOURCE_TAG_CSS = f"""
    .stApp .exp-src, .exp-src {{
      display: block; max-width: 6.5em;
      overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
      margin-top: .1rem; font-size: .66rem; font-weight: 400;
      color: {TEXT_MUTED};
    }}
    .exp-table td {{ overflow-wrap: anywhere; }}
    """
# ~~`white-space: nowrap`（不限寬）~~ → 2026-10-14 修正輪（Q O1；有意識的更正，不是漏刪；決策者：AI 總管）：
# 長來源名（例 `FundClear:GetFundNAV`）不折行，把 1600 寬桌機的候選表撐到要橫捲。改為**值下方另起一行**、
# 限寬 6.5em ＋ 省略號（行內接在值後面時，值與標示之間沒有斷行點，兩者寬度相加仍會撐開欄寬），
# 完整文字在 tooltip（`title`）；寬度量測見 tests/ui_v2/test_exp_live_page.py 的瀏覽器測試。
# 同輪另加 `.exp-table td { overflow-wrap: anywhere; }`（體例同 hld：長字串靠折行，不截斷）——
# 原因句裡的 ASCII 長字（`MoneyDJ+TDCC`、`<script>…`）沒有斷行點，會把欄寬撐大。


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
#    用的都是主文字色，算出來遠高於 4.5，所以一律拿 4.5 去驗。
TEXT_FLOOR = 4.5
UI_FLOOR = 3.0

CONTRAST_PAIRS = (
    # ── 一般文字（門檻 4.5） ──
    ("主文字／頁底", TEXT_PRIMARY, APP_BG, TEXT_FLOOR),
    ("主文字／卡底", TEXT_PRIMARY, SURFACE, TEXT_FLOOR),
    ("主文字／格底", TEXT_PRIMARY, INPUT_BG, TEXT_FLOOR),
    ("次文字／卡底", TEXT_SECOND, SURFACE, TEXT_FLOOR),
    ("次文字／頁底", TEXT_SECOND, APP_BG, TEXT_FLOOR),
    ("弱文字／頁底", TEXT_MUTED, APP_BG, TEXT_FLOOR),
    ("弱文字／卡底", TEXT_MUTED, SURFACE, TEXT_FLOOR),
    ("弱文字／格底", TEXT_MUTED, INPUT_BG, TEXT_FLOOR),
    ("弱文字／按鈕底", TEXT_MUTED, BUTTON_BG, TEXT_FLOOR),
    ("資料未備的灰／卡底", STATE_GRAY, SURFACE, TEXT_FLOOR),
    ("資料未備的灰／頁底", STATE_GRAY, APP_BG, TEXT_FLOOR),
    ("資料未備的灰／灰態框底", STATE_GRAY, STATE_GRAY_BG, TEXT_FLOOR),
    ("警示黃／黃態卡底", STATE_WARN, STATE_WARN_BG, TEXT_FLOOR),
    ("警示黃／卡底", STATE_WARN, SURFACE, TEXT_FLOOR),
    ("警示黃／頁底", STATE_WARN, APP_BG, TEXT_FLOOR),
    ("取數失敗的紅／紅態卡底", STATE_ERR, STATE_ERR_BG, TEXT_FLOOR),
    ("取數失敗的紅／卡底", STATE_ERR, SURFACE, TEXT_FLOOR),
    ("取數失敗的紅／頁底", STATE_ERR, APP_BG, TEXT_FLOOR),
    ("失敗訊息原文／訊息底", ERR_MSG_FG, ERR_MSG_BG, TEXT_FLOOR),
    ("輸入提示字／輸入框底", PLACEHOLDER, INPUT_BG, TEXT_FLOOR),
    ("輸入提示字／頁底", PLACEHOLDER, APP_BG, TEXT_FLOOR),
    ("青色標題／頁底", TEAL_DARK, APP_BG, TEXT_FLOOR),
    ("青色標題／卡底", TEAL_DARK, SURFACE, TEXT_FLOOR),
    ("青色標題／按鈕底", TEAL_DARK, BUTTON_BG, TEXT_FLOOR),
    # ── 非文字 UI 元件（門檻 3） ──
    ("控制項邊界／頁底", EDGE, APP_BG, UI_FLOOR),
    ("控制項邊界／卡底", EDGE, SURFACE, UI_FLOOR),
    ("控制項邊界／輸入框底", EDGE, INPUT_BG, UI_FLOOR),
    ("控制項邊界／按鈕底", EDGE, BUTTON_BG, UI_FLOOR),
    ("灰態框線／卡底", STATE_GRAY, SURFACE, UI_FLOOR),
    ("灰態框線／灰態框底", STATE_GRAY, STATE_GRAY_BG, UI_FLOOR),
    ("黃態框線／頁底", STATE_WARN, APP_BG, UI_FLOOR),
    ("黃態框線／黃態卡底", STATE_WARN, STATE_WARN_BG, UI_FLOOR),
    ("紅態框線／頁底", STATE_ERR, APP_BG, UI_FLOOR),
    ("紅態框線／紅態卡底", STATE_ERR, STATE_ERR_BG, UI_FLOOR),
    ("失敗訊息框線／訊息底", ERR_MSG_EDGE, ERR_MSG_BG, UI_FLOOR),
    ("灰燈圓點／卡底", STATE_GRAY, SURFACE, UI_FLOOR),
    ("青色髮絲線／頁底", TEAL_DARK, APP_BG, UI_FLOOR),
    ("青色髮絲線／卡底", TEAL_DARK, SURFACE, UI_FLOOR),
)

# ⚠️ `BORDER`（`#30363d`）刻意**不在**上表裡：草稿 §J 把它與同型的幾條
#    逐條判為「純裝飾分隔線，不是非文字 UI 元件」（不是控制項、不表示任何狀態，
#    拿掉之後每一個字與每一個數照樣讀得到），門檻不適用。
#    **那是草稿那一組的分類判斷，客戶未逐字裁，可推翻** —— 本檔沿用並照實登記，
#    不自行把它改成「已達標」。
