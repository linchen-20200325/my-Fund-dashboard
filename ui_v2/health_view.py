# -*- coding: utf-8 -*-
"""四頁頁首資料狀態行、「前往設定與診斷」導覽、④「證據／來源」裡的核心卡徽章 —— 畫法（Phase 3 P0-②）。

內容（字樣、判定）全部住在 `ui_v2/health.py`（純函式）；本檔只負責畫。

⛔ **導覽只換頁**（44 第五節第三小節 `導覽`、護欄 3）：`render_settings_link` 的函式本體只准呼叫
`st.page_link`、`st.caption`、`st.markdown`（AST 守衛：`tests/ui_v2/test_health_logic.py`），
不讀也不寫任何資料表，不觸發取數、重新整理、存檔或任何寫入。
"""

from __future__ import annotations

import html

import streamlit as st

from . import health


def _esc(value) -> str:
    return html.escape(str(value), quote=True)


def render_settings_link(settings_page=None) -> None:
    """「前往設定與診斷」：有 `settings_page`（`st.Page`，預覽入口傳進來）→ 一枚頁面連結；
    沒有（單頁入口，沒有 `st.navigation`，換不了頁）→ 只寫一行說明。"""
    if settings_page is not None:
        st.page_link(settings_page, label=health.SETTINGS_LINK_LABEL)
    else:
        st.caption(health.SETTINGS_ELSEWHERE_TEXT)


def render_status_line(line: dict, *, tone_hex, settings_page=None) -> None:
    """頁首資料狀態行（`health.status_line` 的回傳）＋導覽。`tone_hex`：該頁 `theme.tone_hex`（色票不另立）。"""
    muted = tone_hex("灰")
    if line["items"]:
        parts = [
            f'<span style="color:{tone_hex(tone)}">{_esc((symbol + " " + text).strip())}</span>'
            for symbol, text, tone in line["items"]
        ]
        body = (
            f'<span>{_esc(health.STATUS_LABEL)}</span>' + "　".join(parts)
            + f'<span style="color:{muted}">　·　{_esc(health.AS_OF_LABEL)} {_esc(line["as_of"])}</span>'
        )
    else:
        body = f'<span style="color:{muted}">{_esc(health.AS_OF_LABEL)} {_esc(line["as_of"])}</span>'
    st.markdown(f'<div class="v2-status-line" role="status">{body}</div>', unsafe_allow_html=True)
    render_settings_link(settings_page)


def render_provenance(rows) -> None:
    """④「證據／來源」：核心卡上拿下來的來源與新鮮度徽章（`health.move_card_provenance` 的回傳），預設收合。
    一筆都沒有 → 不畫（沒有東西被拿下來，就沒有東西要換位置）。"""
    if not rows:
        return
    with st.expander(health.PROVENANCE_TITLE, expanded=False):
        body = "".join(
            f"<tr><td>{_esc(card)}</td><td>{_esc(item)}</td><td>{_esc('　'.join(texts))}</td></tr>"
            for card, item, texts in rows
        )
        st.markdown(
            '<table class="v2-provenance"><thead><tr><th>卡</th><th>項目</th><th>來源與新鮮度</th></tr></thead>'
            f"<tbody>{body}</tbody></table>",
            unsafe_allow_html=True,
        )
