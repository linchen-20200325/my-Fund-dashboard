# -*- coding: utf-8 -*-
"""四頁頁首資料狀態行、「前往設定與診斷」導覽、④「證據／來源」裡的核心卡徽章 —— 畫法（Phase 3 P0-②）。

內容（字樣、判定）全部住在 `ui_v2/health.py`（純函式）；本檔只負責畫。

⛔ **導覽只換頁**（44 第五節第三小節 `導覽`、護欄 3）：`render_settings_link` 的函式本體只准呼叫
`st.page_link`、`st.caption`、`st.markdown`（AST 守衛：`tests/ui_v2/test_health_logic.py`），
不讀也不寫任何資料表，不觸發取數、重新整理、存檔或任何寫入。
"""

from __future__ import annotations

import html
import logging
from datetime import datetime, timezone

import streamlit as st

from . import health, plain

_log = logging.getLogger(__name__)


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


def render_load_failure(page: str, exc: BaseException, mask_error, *, fetch_failed_text, title: str, answers: str,
                        title_class: str, sub_class: str, tone_hex, settings_page=None, link: bool = True) -> None:
    """正式模式 `load_live()` 拋例外時的整頁畫面（BL-0362；Phase 3 P1-⑤）。體例照持倉體檢既有的
    `ui_v2/hld/page.py::_render_live_error`：頁名、提問句、一行狀態句（紅、`⛔`），其餘塊不畫；不印 Traceback、不吞。

    - 一般畫面那一行：`plain.plain_error_line`（P0-① 既有的字：「⛔ <資料類> 取數失敗：<一句狀態>」），不帶例外型別與原文；
    - 原文（`health.load_failure_line`：型別＋遮蔽後訊息）收進跨頁的原始訊息（`plain.record_raw`，設定與診斷頁的進階診斷照印），
      並寫一筆 log（`CLAUDE.md` 第三節第三小節：接住例外至少要 log）；
    - `link`：四頁接一枚「前往設定與診斷」（`render_settings_link`，只換頁；44 第七節第三小節之七其五第 2 條）；
      設定與診斷頁自己傳 `False`（它就是那一頁）。
    """
    raw_line = health.load_failure_line(exc, mask_error, fetch_failed_text)
    plain_line, raw = plain.plain_error_line(raw_line, page=page)
    plain.record_raw(st.session_state, page, raw, datetime.now(timezone.utc))
    _log.warning("ui_v2 %s 正式頁載入失敗：%s", page, raw_line)
    st.markdown(f'<div class="{_esc(title_class)}">{_esc(title)}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="{_esc(sub_class)}">{_esc(answers)}</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="v2-load-failure" role="alert" style="color:{tone_hex("紅")};font-weight:700">'
        f"{_esc(plain_line)}</div>",
        unsafe_allow_html=True,
    )
    if link:
        render_settings_link(settings_page)
