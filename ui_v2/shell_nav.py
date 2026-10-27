# -*- coding: utf-8 -*-
"""預覽殼層（BL-0484／BL-0479；D1 方案 A；`DEC-2026-10-27-01`、`-09`、`-11`、`-12`）的**純邏輯與樣式字串**。

零 streamlit import、零舊樹 import（`tests/ui_v2/test_ui_v2_live_import_guard.py`；fast lane 可跑）。
畫面由 `ui_v2/shell.py` 負責；本檔只決定「導覽有哪幾項、哪一項是目前、樣式字串長什麼樣」。

**本檔不決定的事**（殼層批只做殼層）：
- 第一層的順序與頁名＝`ui_v2/app_preview.py::PAGES`（客戶 `DEC-2026-10-27-02`；本檔不另寫一份頁名，
  只切出「圖示」與「名稱」兩段，名稱逐字取自 `PAGES`）。
- 不放任何頁內內容、不放 AI 內容（`DEC-2026-10-27-25`：全站 AI 區屬殼層，但第 1 批不預留位置——不確定就不預留）。
- 不新增任何頁名、區段名或說明文案（UI 文案屬客戶定字）。

**第二層（「本頁區段」跳轉）本批沒有做**（spike 結論，見 PR 說明）：頁內各塊是各頁 `page.render` 以 `st.markdown`
畫出的 `<div>`，沒有任何 id；殼層在不改 `page.render` 內部的前提下，沒有原生辦法跳到某一塊。D1 草稿第 4 節已寫明
這種情形的退路：「驗不過就退回每類第二層只有 1 個整頁入口」。本檔的 `NOT_IN_NAV` 只是把客戶已裁示「不進導覽」的名稱
鎖成測試母體。
"""

from __future__ import annotations

# 手機斷點：44 第二節 2.1（客戶 2026-09-22 最終版）「≤768：單欄」。殼層以同一個值切「桌機側欄」與「手機底部導覽」。
MOBILE_MAX_PX = 768
# 觸控目標下限（客戶要求「觸控目標足夠大」；Apple HIG／Material 皆取 44～48）。
TOUCH_MIN_PX = 44
BOTTOM_NAV_ITEM_MIN_PX = 56

# 客戶已裁示「不進導覽」的名稱（鎖成測試母體，不是導覽內容）：
#   風險觀察＝`DEC-2026-10-27-12`（目前不顯示、不做空殼、不放「規劃中」）；
#   再平衡＝`DEC-2026-10-27-05`（不做一鍵再平衡）；
#   台股趨勢、國際趨勢＝`DEC-2026-10-27-03`（🌍 規格與實作完成前不進導覽，`docs/v2/66`）。
NOT_IN_NAV = ("風險觀察", "再平衡", "台股趨勢", "國際趨勢")

# 側欄與底部導覽的容器 key（Streamlit 會把 key 轉成 `st-key-<key>` 的 CSS class）。
SIDEBAR_KEY_PREFIX = "shell-side"
BOTTOM_KEY = "shell-bottom-nav"
BOTTOM_ITEM_PREFIX = "shell-bottom"
# 目前頁的容器 key 結尾（顏色以外的辨識另靠粗體、底線與色條，見 `shell_css`）。
CURRENT_SUFFIX = "-isnow"

# 深色側欄與底部導覽的色票（`DEC-2026-10-27-09`：深色主側欄；底色沿用客戶 2026-09 逐字指定的深色 app 底色 #0e1117，
# 文字與青色沿用同一套 token；與 `ui_v2/*/theme.py` 的淺色主內容區 token 無關，殼層自己的一組）。
NAV_BG = "#0e1117"
NAV_BG_RAISED = "#161b22"
NAV_BORDER = "#30363d"
NAV_TEXT = "#e6edf3"
NAV_TEXT_MUTED = "#9aa4b2"
NAV_ACCENT = "#5fd3d0"   # 客戶逐字指定的亮青（深色底上的強調色）


def split_title(title: str) -> tuple:
    """`"🌍 市場與趨勢"` → `("🌍", "市場與趨勢")`。頁名在 `PAGES` 裡是「圖示＋空白＋名稱」（44 之十七其二第 1 條）。

    沒有空白、或第一段含文字／數字（不是 emoji）就整串當名稱、圖示空字串 —— 不猜、不補
    （Streamlit 的 `icon` 收到不是 emoji 的字會直接拋例外，殼層不能讓一個沒有圖示的頁名把整頁弄壞）。
    """
    icon, sep, name = title.partition(" ")
    if not sep or any(ch.isalnum() for ch in icon):
        return "", title
    return icon, name


def build_items(pages, current_title: str) -> list:
    """`pages`：`[(slug, title), ...]`（照 `PAGES` 的順序）→ 導覽項。順序一個不動；`current` 只有符合的那一項為真。"""
    items = []
    for slug, title in pages:
        icon, name = split_title(title)
        items.append({
            "slug": slug,
            "title": title,
            "icon": icon,
            "name": name,
            "current": title == current_title,
        })
    return items


def container_key(prefix: str, slug: str, current: bool) -> str:
    return f"{prefix}-{slug}{CURRENT_SUFFIX if current else ''}"


def _side_css() -> str:
    # 深色側欄：頁面各自的 `<style>` 寫了 `.stApp p, .stApp span, .stApp label {color: …}`（淺色主內容區的字色），
    # 會一併吃到側欄裡的文字；這裡用 `!important` 把側欄文字拉回淺色。選取器限定在 `stSidebar` 之內。
    return f"""
    [data-testid="stSidebar"], [data-testid="stSidebar"] > div {{ background: {NAV_BG} !important; }}
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] span, [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] a {{ color: {NAV_TEXT} !important; }}
    [data-testid="stSidebar"] [data-testid="stPageLink-NavLink"] {{
      min-height: {TOUCH_MIN_PX}px; align-items: center; border-radius: 6px;
      border-left: 4px solid transparent; padding-left: .6rem;
    }}
    [data-testid="stSidebar"] [data-testid="stPageLink-NavLink"]:hover {{ background: {NAV_BG_RAISED} !important; }}
    [data-testid="stSidebar"] [class*="{CURRENT_SUFFIX}"] [data-testid="stPageLink-NavLink"] {{
      background: {NAV_BG_RAISED} !important; border-left: 4px solid {NAV_ACCENT};
    }}
    [data-testid="stSidebar"] [class*="{CURRENT_SUFFIX}"] [data-testid="stPageLink-NavLink"] p {{
      font-weight: 700 !important; text-decoration: underline; text-underline-offset: 4px;
    }}
    """


def _bottom_css() -> str:
    # 底部導覽：只在手機寬度（≤ MOBILE_MAX_PX）顯示；桌機完全不畫（display:none）。
    # 頁面自己的 `<style>` 對所有 `stHorizontalBlock` 寫了 `flex-wrap: wrap !important` 與窄寬度單欄堆疊，
    # 這裡用 `.st-key-…` 前綴把特異性拉高並一律 `!important`，五格才會固定同一列等寬。
    key = f".st-key-{BOTTOM_KEY}"
    return f"""
    {key} {{ display: none; }}
    @media (max-width: {MOBILE_MAX_PX}px) {{
      {key} {{
        display: block; position: fixed; left: 0; right: 0; bottom: 0; z-index: 999990;
        background: {NAV_BG}; border-top: 1px solid {NAV_BORDER};
        padding: 0 0 env(safe-area-inset-bottom, 0);
      }}
      {key} [data-testid="stHorizontalBlock"] {{ flex-wrap: nowrap !important; gap: 0 !important; }}
      {key} [data-testid="stColumn"], {key} [data-testid="column"] {{
        min-width: 0 !important; flex: 1 1 0 !important; width: 20% !important;
      }}
      {key} [data-testid="stElementContainer"], {key} [data-testid="stPageLink"],
      {key} [data-testid="stPageLink"] > div {{ width: 100% !important; margin: 0 !important; }}
      {key} [data-testid="stPageLink-NavLink"] {{
        width: 100%; box-sizing: border-box;
        display: flex; flex-direction: column; align-items: center; justify-content: center;
        min-height: {BOTTOM_NAV_ITEM_MIN_PX}px; padding: 6px 0 4px; gap: 2px;
        border-top: 3px solid transparent; border-radius: 0; text-align: center; margin: 0 !important;
      }}
      {key} [data-testid="stPageLink-NavLink"] p, {key} [data-testid="stPageLink-NavLink"] span {{
        color: {NAV_TEXT} !important; font-size: 11px !important; line-height: 1.2 !important;
        white-space: nowrap; margin: 0;
      }}
      {key} [data-testid="stIconEmoji"], {key} [data-testid="stIconEmoji"] span {{ font-size: 18px !important; }}
      {key} [class*="{CURRENT_SUFFIX}"] [data-testid="stPageLink-NavLink"] {{
        border-top: 3px solid {NAV_ACCENT}; background: {NAV_BG_RAISED} !important;
      }}
      {key} [class*="{CURRENT_SUFFIX}"] [data-testid="stPageLink-NavLink"] p {{
        font-weight: 700 !important; text-decoration: underline; text-underline-offset: 3px;
      }}
      [data-testid="stMainBlockContainer"], [data-testid="stMain"] .block-container {{
        padding-bottom: calc({BOTTOM_NAV_ITEM_MIN_PX}px + 2.5rem + env(safe-area-inset-bottom, 0)) !important;
      }}
    }}
    """


def shell_css() -> str:
    """殼層的整段 CSS（不含 `<style>` 標籤）。純常數字串組合、不依賴執行期狀態，呼叫端可整個快取。"""
    return _side_css() + _bottom_css()


SHELL_CSS = shell_css()
