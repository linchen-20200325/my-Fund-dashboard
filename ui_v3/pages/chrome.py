# -*- coding: utf-8 -*-
"""全站共用 Navigation Shell 的畫面（BL-0536 Shell 批；選型 Route C 見 `docs/v2/80` 第 17 節）。

- 導覽：`st.navigation(position="hidden")` 只負責 routing／頁登錄（沿用 `app_preview`）；側欄與手機頁首 S1 導覽由本檔自畫
  （`st.sidebar`＋`st.page_link`；頁首五格由 `st.container(key=…, horizontal=True)` 在文件流內呈現（不吸頂，隨頁面捲動移走））。
  五頁全部可見；已掛載的頁是真連結（`st.page_link`），未掛載的頁是**不可點的文字項**（`aria-disabled`、標「開發中」），
  沒有 renderer、沒有空殼頁、沒有假資料；🤖 在 Phase 7 前不可進（登錄表建構時就擋）。
- Status Bar：純文字「PREVIEW」＋（有缺資料時）資料狀態一句＋更新時間（不放 chip 形式元素；客戶 2026-11-03 裁示第一項）；內容全來自 `ShellStatus`（既有 health／provenance），沒有自造狀態；
  沒有取得時間就寫規則表的缺資料字樣（純文字、零 chip；`_missing_text`），不推估。⚠️ 資料全部取得時**不寫「正常」「資料齊」**（`rules.entry("ok")` 刻意無字，44 頁首資料狀態行規則）。
- 更新資料 CTA：本批沒有安全可接的正式 refresh 流程 → 不可用＋一句原因（一般使用者看得懂；不外漏工程資訊）。
- 字樣：Shell 字樣已於客戶 2026-11-03 裁示核准（`DEC-2026-11-03-11`），一律取規則表 `APPROVED_WORDING`（`W.span` 輸出純文字、不標 pending）；五頁頁名取登錄表（已核准）。只用 `streamlit`／`html`／標準庫。
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Mapping, Optional
from zoneinfo import ZoneInfo

from shared.ui_semantics import rules
from ui_v3.shell import nav
from ui_v3.viewmodels import preview_wording as W
from ui_v3.viewmodels.shell import LEVEL_OK, ShellStatus

TAIPEI = ZoneInfo("Asia/Taipei")


# ───────────────────────────── 純字串（可單元測試） ─────────────────────────────

def format_taipei(stamp: Optional[str], *, today=None, full: bool = False) -> Optional[str]:
    """取得時間（帶時區的 ISO）→ 台北時間字串；不帶時區或無法解析 → None（不猜）。
    `full`＝`YYYY-MM-DD HH:MM`；否則同一個台北日只寫 `HH:MM`，不同日寫 `MM-DD HH:MM`。"""
    if not stamp:
        return None
    try:
        moment = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is None:
        return None
    local = moment.astimezone(TAIPEI)
    if full:
        return local.strftime("%Y-%m-%d %H:%M")
    day = today if today is not None else datetime.now(TAIPEI).date()
    return local.strftime("%H:%M") if local.date() == day else local.strftime("%m-%d %H:%M")


def _missing_text() -> str:
    """沒有取得時間時的缺資料字樣（規則表符號＋字樣）。**純文字、不是 chip**：Shell chrome 不放 chip 形式元素（客戶 2026-11-03 裁示第一項）。"""
    entry = rules.entry("missing")
    return f'<span data-status-key="missing">{escape(entry.wording)}</span>'


def status_phrase_html(status: ShellStatus) -> str:
    """資料狀態一句（全部取得時回空字串：不寫「正常」）。純文字、符號取規則表缺資料符號；取數失敗另列一句，不冒充缺資料。
    計數分母＝本次檢查涵蓋的已登錄項目數（`status.total`），不寫成全系統結論。"""
    if status.level == LEVEL_OK:
        return ""
    symbol = rules.entry("missing").symbol
    if status.level == "partial":
        out = f'{escape(symbol)} {W.span("shell_status_partial", ok=status.ok_count, total=status.total)}'
    else:   # 一項也沒取得：客戶已核准的計數字樣（不另造「全缺」句型）
        out = f'{escape(symbol)} {W.span("shell_status_counts", ok=status.ok_count, total=status.total)}'
    if status.failed_count:
        out += f'（{W.span("shell_status_failed_note", n=status.failed_count)}）'
    return out


def status_bar_html(status: ShellStatus, *, today=None) -> str:
    """Status Bar：純文字一行（PREVIEW 標籤、資料狀態句、更新時間）；**不含任何 chip 形式元素或核心數字元素**（守衛鎖）。"""
    tip = escape(W.text("shell_preview_tip"))
    tag = f'<span class="uv3-tag" title="{tip}">{escape(W.text("shell_preview_tag"))}</span>'
    phrase = status_phrase_html(status)
    stamp = format_taipei(status.last_fetched_at, today=today)
    if stamp:
        updated = W.span("shell_updated", time=stamp)
    else:   # 沒有取得時間：寫缺資料字樣，不推估
        updated = W.span_html("shell_updated", time=_missing_text())
    parts = [tag] + ([f"<span>{phrase}</span>"] if phrase else []) + [f"<span>{updated}</span>"]
    return f'<div class="uv3-statusbar" role="status" data-shell="status-bar">{"".join(parts)}</div>'


def sidebar_status_html(status: ShellStatus) -> str:
    """側欄資料狀態區：取得計數（事實）＋缺資料／失敗說明＋最後更新時間（取得時間，完整）。純文字，不放 chip。"""
    counts = W.span("shell_status_counts", ok=status.ok_count, total=status.total)
    extra = ""
    if status.level != LEVEL_OK:
        extra = f'<div class="uv3-row">{status_phrase_html(status)}</div>'
    stamp = format_taipei(status.last_fetched_at, full=True)
    when = escape(stamp) if stamp else _missing_text()
    return (f'<div class="uv3-side-block" data-shell="side-status">'
            f'<div class="uv3-row"><span class="uv3-label">{W.span("shell_data_status_label")}</span>{counts}</div>{extra}'
            f'<div class="uv3-row"><span class="uv3-label">{W.span("shell_updated_label")}</span>{when}</div></div>')


def disabled_side_html(item: nav.NavItem) -> str:
    """未掛載頁的側欄項：可見、不可點（沒有連結、沒有 renderer）。`aria-label` 讓螢幕閱讀器念出「開發中」。"""
    label = escape(f"{item.title}（{W.text(item.soon_key)}）")
    return (f'<div class="uv3-nav-disabled" role="link" aria-disabled="true" aria-label="{label}" data-nav="{escape(item.slug)}">'
            f'<span>{escape(item.icon)}</span><span>{escape(item.name)}</span>'
            f'<span class="uv3-nav-soon">{W.span(item.soon_key)}</span></div>')


def disabled_top_html(item: nav.NavItem) -> str:
    label = escape(f"{item.title}（{W.text(item.soon_key)}）")
    return (f'<div class="uv3-tn-disabled" role="link" aria-disabled="true" aria-label="{label}" data-nav="{escape(item.slug)}">'
            f'<span class="uv3-tn-icon">{escape(item.icon)}</span><span>{W.span(item.short_key)}</span>'
            f'<span class="uv3-tn-soon">{W.span(item.soon_key)}</span></div>')


# ───────────────────────────── Streamlit 畫面 ─────────────────────────────

def render_navigation(pages: Mapping[str, object], current_slug: Optional[str] = None) -> None:
    """畫側欄（桌機／平板）與 S1 頁首五格（手機）。`pages`：已掛載頁的 `slug → st.Page`。兩者都在 DOM，CSS 依斷點二選一。"""
    import streamlit as st

    items = nav.nav_items()
    st.markdown(nav.shell_css(), unsafe_allow_html=True)
    with st.sidebar:
        st.markdown(f'<div class="uv3-brand">{W.span("shell_app_title")}</div>', unsafe_allow_html=True)
        for item in items:
            if item.available:
                with st.container(key=_now_key("side", item.slug, current_slug)):
                    st.page_link(pages[item.slug], label=item.name, icon=item.icon or None)
            else:
                st.markdown(disabled_side_html(item), unsafe_allow_html=True)
    with st.container(key=nav.TOP_KEY, horizontal=True, gap="small"):
        for item in items:
            if item.available:
                with st.container(key=_now_key("top", item.slug, current_slug)):
                    st.page_link(pages[item.slug], label=W.text(item.short_key), icon=item.icon or None, width="stretch")
            else:
                st.markdown(disabled_top_html(item), unsafe_allow_html=True)


def _now_key(where: str, slug: str, current_slug: Optional[str]) -> str:
    """目前頁的容器 key 帶 `uv3-nav-now`（CSS 以它畫粗體＋色條／上緣線＋底線；Streamlit 的 page_link 沒有 aria-current 可依）。"""
    return f"uv3-nav-{'now-' if slug == current_slug else ''}{where}-{slug}"


def render_status(status: ShellStatus, *, key: str = "uv3_shell_refresh") -> None:
    """Status Bar（主區頂端一行）＋側欄資料狀態區＋更新資料 CTA。`status` 來自 adapter（既有 health／provenance）。"""
    import streamlit as st

    st.markdown(status_bar_html(status), unsafe_allow_html=True)
    with st.sidebar:
        st.markdown(sidebar_status_html(status), unsafe_allow_html=True)
        st.button(W.text("shell_refresh_cta"), key=key, disabled=not status.refresh_available, width="stretch")
        if not status.refresh_available:
            st.markdown(f'<div class="uv3-cta-note">{W.span("shell_refresh_unavailable")}</div>', unsafe_allow_html=True)


def render_footer() -> None:
    """長說明移到頁尾（不搶首屏）：Preview 與暫時字樣的說明。"""
    import streamlit as st

    st.markdown(f'<div class="uv3-footer" data-shell="footer">{W.span("preview_banner")}</div>', unsafe_allow_html=True)
