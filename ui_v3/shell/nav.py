# -*- coding: utf-8 -*-
"""全站共用 Navigation Shell 的**純邏輯與樣式字串**（BL-0536 Shell 批；選型見 `docs/v2/80` 第 17 節）。

零 streamlit import、零字樣（字樣在 `viewmodels/preview_wording.py`，由 `pages/chrome.py` 組裝）。本檔只決定：
導覽有哪五項、哪些可進、各項的圖示與頁名、手機斷點、以及 Shell 的 CSS。

- 五項與順序＝`registry.IA_PAGES`（已核准）；`available` ＝ `registered`（已有核准線框且已實作）。
  未掛載的項目**可見但不可進**：沒有任何 renderer、沒有空殼頁、不放假資料。
- 版面值（斷點、觸控高度）是 Preview 暫用的樣式值，不是 design token（`design/tokens.py` 值未定）。
- 舊 B 線（`ui_v2/shell_nav.py`）只作 IA／操作經驗參考：這裡不 import、不複製其 presentation code；
  兩邊都取 44 第二節 2.1 的 ≤768 斷點；本版依 BL-0544／DEC-2026-11-07-02 改為手機頁首 S1 五格，不搬運底部呈現。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from ui_v3.shell.registry import IA_PAGES, PageSlot

MOBILE_MAX_PX = 768          # 44 第二節 2.1：≤768 手機頁首、>768 原桌機側欄（兩者不同時出現）
TOUCH_MIN_PX = 48            # 觸控目標下限（Apple HIG／Material 取 44～48）
TOP_NAV_HEIGHT_PX = 60       # S1 頂部導覽最小高度；在文件流內 sticky，不壓住首屏／頁尾
TOP_KEY = "uv3-top-nav"
SIDEBAR_KEY = "uv3-sidebar-nav"


def split_title(title: str) -> tuple:
    """`"🌍 市場與趨勢"` → `("🌍", "市場與趨勢")`。沒有空白、或第一段含文字／數字（不是 emoji）就整串當名稱、圖示空字串（不猜）。"""
    icon, sep, name = title.partition(" ")
    if not sep or any(ch.isalnum() for ch in icon):
        return "", title
    return icon, name


@dataclass(frozen=True)
class NavItem:
    slug: str
    icon: str
    name: str            # 完整頁名（已核准；不含圖示）
    title: str           # 圖示＋空白＋頁名（＝ registry 的 title，原字）
    available: bool      # True＝可進；False＝可見但不可進（開發中；不是空殼頁）
    short_key: str       # 手機頁首導覽短字樣在規則表 `APPROVED_WORDING` 的鍵
    soon_key: str        # 未掛載時的標籤鍵：🤖 用「尚未開放」（Phase 7 前不可進）、其餘用「開發中」（客戶 2026-11-03，`DEC-2026-11-03-11`）


def nav_items(pages: Optional[Tuple[PageSlot, ...]] = None) -> Tuple[NavItem, ...]:
    """五頁導覽項（IA 順序）。`pages` 預設為正式登錄表；測試可在記憶體內傳入替代表。"""
    out = []
    for slot in (IA_PAGES if pages is None else pages):
        icon, name = split_title(slot.title)
        soon_key = "shell_nav_not_open" if slot.slug == "ai" else "shell_nav_soon"
        out.append(NavItem(slot.slug, icon, name, slot.title, slot.registered, f"shell_nav_short_{slot.slug}", soon_key))
    return tuple(out)


def shell_css() -> str:
    """Shell 的 CSS（Preview 暫用）：桌機／平板＝原左側側欄、手機＝頁首 sticky 五等分導覽，兩者不同時出現。"""
    mobile, touch, bar = MOBILE_MAX_PX, TOUCH_MIN_PX, TOP_NAV_HEIGHT_PX
    return f"""
<style>
.uv3-pending{{border-bottom:1px dashed rgba(128,128,128,.8)}}
.uv3-chip{{display:inline-block;border-radius:12px;padding:1px 10px;font-size:13px;border:1px solid rgba(128,128,128,.45);
  background:rgba(128,128,128,.12);white-space:normal}}
.uv3-tone-red{{border-color:#c0392b;background:rgba(192,57,43,.12)}}
.uv3-row{{margin:.25rem 0;line-height:1.55}}
/* 側欄固定（不給收合鈕；桌機／平板永遠看得到導覽） */
[data-testid="stSidebarCollapseButton"],[data-testid="stSidebarHeader"]{{display:none !important}}
[data-testid="stSidebarUserContent"]{{padding-top:1rem !important}}
.uv3-brand{{font-size:17px;font-weight:700;margin:0 0 .6rem 0;line-height:1.3}}
.uv3-nav-disabled{{display:flex;align-items:center;gap:.5rem;min-height:{touch}px;padding:0 .75rem;opacity:.55;cursor:not-allowed;
  border-radius:.5rem;font-size:15px}}
.uv3-nav-disabled .uv3-nav-soon{{font-size:12px;margin-left:auto;border:1px dashed rgba(128,128,128,.8);border-radius:10px;padding:0 6px}}
.uv3-side-block{{border-top:1px solid rgba(128,128,128,.35);margin-top:.8rem;padding-top:.6rem;font-size:13px;line-height:1.55}}
.uv3-side-block .uv3-label{{opacity:.75;margin-right:6px}}
.uv3-cta-note{{font-size:12px;opacity:.8;margin-top:.25rem}}
/* 目前頁：除了顏色，還有粗體＋左側色條（不只靠顏色） */
[class*="st-key-uv3-nav-now-side"] a[data-testid="stPageLink-NavLink"]{{font-weight:700;border-left:4px solid currentColor}}
[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"]{{min-height:{touch}px}}
/* Top／Status Bar：極薄一行（Shell 的一部分，不是頁級狀態 chip） */
.uv3-statusbar{{display:flex;flex-wrap:wrap;align-items:center;gap:2px 10px;font-size:12px;line-height:1.5;opacity:.9;margin:0 0 .25rem 0}}
.uv3-statusbar .uv3-tag{{font-weight:700;letter-spacing:.06em;border:1px solid currentColor;border-radius:4px;padding:0 5px;cursor:help}}
.uv3-footer{{font-size:12px;opacity:.7;margin-top:1.2rem}}
/* 頁首導覽：桌機／平板完全不顯示；手機佔用正常文流，sticky 不覆蓋登入／首屏 */
.st-key-{TOP_KEY}{{display:none !important}}
@media (max-width:{mobile}px){{
  [data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"],[data-testid="stExpandSidebarButton"]{{display:none !important}}
  .st-key-{TOP_KEY}{{display:flex !important;flex-direction:row !important;flex-wrap:nowrap !important;gap:0 !important;
    position:sticky;top:env(safe-area-inset-top);z-index:999990;width:100%;max-width:100%;min-height:{bar}px;
    box-sizing:border-box;overflow-x:hidden;margin:0;padding:0;
    background:var(--background-color,#ffffff);color:inherit;border-bottom:1px solid rgba(128,128,128,.45)}}
  .st-key-{TOP_KEY} [class*="st-key-uv3-nav-"],.st-key-{TOP_KEY} [data-testid="stElementContainer"]{{gap:0 !important;margin:0 !important;min-width:0 !important}}
  .st-key-{TOP_KEY} > div{{display:flex !important;flex:1 1 0 !important;min-width:0 !important;width:100% !important}}
  .st-key-{TOP_KEY} a[data-testid="stPageLink-NavLink"],.st-key-{TOP_KEY} .uv3-tn-disabled{{display:flex;flex-direction:column;align-items:center;
    justify-content:center;gap:1px;box-sizing:border-box;height:{bar}px;min-height:{touch}px;min-width:0;padding:2px 0;margin:0;
    text-align:center;border-radius:0;font-size:12px;line-height:1.2;color:inherit;text-decoration:none;
    border-bottom:3px solid transparent}}
  .st-key-{TOP_KEY} a[data-testid="stPageLink-NavLink"] p{{font-size:12px !important;margin:0;white-space:normal}}
  .st-key-{TOP_KEY} [class*="st-key-uv3-nav-now-top"] a[data-testid="stPageLink-NavLink"]{{font-weight:700;border-bottom:3px solid currentColor;
    text-decoration:underline;text-underline-offset:3px}}
  .st-key-{TOP_KEY} a[data-testid="stPageLink-NavLink"]:focus-visible{{outline:2px solid currentColor;outline-offset:-3px}}
  .st-key-{TOP_KEY} .uv3-tn-disabled{{opacity:.55;cursor:not-allowed;font-size:12px}}
  .st-key-{TOP_KEY} .uv3-tn-icon{{font-size:20px;line-height:1}}
  .st-key-{TOP_KEY} .uv3-tn-soon{{font-size:10px}}
}}
</style>
"""
