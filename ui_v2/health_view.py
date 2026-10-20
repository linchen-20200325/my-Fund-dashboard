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

from . import health, page_health, plain

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


def render_attention(items, *, tone_hex, label_class: str) -> None:
    """③需要注意（Phase 3 P1-④；`ui_v2/sections.py::attention_items` 的回傳）：段標籤＋逐項一行，預設展開（不是展開區）。
    一項都沒有 → 整段不畫（之七其一第 2 條：沒有這類項目時不為了有內容而列）。"""
    if not items:
        return
    st.markdown(f'<div class="{_esc(label_class)}">{_esc(plain.LABEL_ATTENTION)}</div>', unsafe_allow_html=True)
    for item in items:
        text = (item["symbol"] + " " + item["text"]).strip()
        st.markdown(
            f'<div class="v2-attention" style="color:{tone_hex(item["_tone"])}">{_esc(text)}</div>',
            unsafe_allow_html=True,
        )


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


def record_load_failure(slug: str, raw_line: str) -> None:
    """整頁載不出來時記一筆（各頁資料狀態總表主要原因順位 1；設定與診斷頁自己不在總表裡，不記）。
    資料類取自那一行原文：認得出的已知訊息照它的資料類，認不出 → `plain.DATA_CLASS_DEFAULT`（與這一頁畫出來的那一句同一類）。"""
    if slug in page_health.PAGE_NAMES:
        page_health.record(st.session_state, slug, (), as_of=None, now=datetime.now(timezone.utc),
                           page_failure=plain.error_line_data_class(raw_line))


# 收集與記錄那兩步的錯誤邊界（3-B 稽核回修第 3 條）：接住這幾種，頁面照原樣畫完，這一頁的總表記錄改寫成「本頁狀態無法彙整」。
# 其他例外照舊往上拋（不吞）。
COLLECT_ERRORS = (health.MissingClassError, ValueError, KeyError)


def collect_page_health(slug: str, display: dict, summary: dict, fetch_events, cards, *, normal_class=None) -> dict:
    """收下這一頁已畫出的 ⛔／◇／尚未設定與「沒有異常」那幾列（`move_card_provenance` 之前；只讀、不改模型）。
    回 `{"items", "normal"}`；收集出錯 → 寫一筆 log（頁名＋例外類別）並回 `{"error": <例外類別>}`，頁面照原樣畫。
    認不出資料類的取數失敗（`collect_page_items` 的第二個回傳值）逐處寫 log，不再靜默丟掉。"""
    try:
        items, unresolved = health.collect_page_items(display, summary, fetch_events, cards)
        normal = health.normal_entries(display, cards, data_class=normal_class)
    except COLLECT_ERRORS as exc:
        _log.warning("ui_v2 %s 頁資料狀態無法彙整：%s", slug, type(exc).__name__)
        return {"error": type(exc).__name__}
    for where in unresolved:
        _log.warning("ui_v2 %s 頁有一句取數失敗認不出資料類：%s %s", slug, where.get("code"), where.get("field"))
    return {"items": items, "normal": normal}


def record_page_health(slug: str, display: dict, collected: dict, cards, status_line) -> None:
    """記下這一頁這一次畫出來的資料狀態，給設定與診斷頁的各頁資料狀態總表（BL-0250 批次 3-B；`ui_v2/page_health.py::record`）。
    `collected`：`collect_page_health` 的回傳；◷ 在這裡補（`move_card_provenance` 之後才看得到）。只記、不取數、不寫入任何資料表；
    記錄時間取當下（台北時間由總表換算）。收集或記錄出錯 → 這一頁整格改寫成收集失敗（不留上一次的記錄）、寫 log，頁面不受影響。"""
    now = datetime.now(timezone.utc)
    error = collected.get("error")
    if error is None:
        try:
            page_health.record(
                st.session_state, slug, list(collected["items"]) + health.stale_items(display, cards),
                as_of=status_line.get("as_of"), now=now, normal=collected["normal"],
            )
            return
        except COLLECT_ERRORS as exc:
            error = type(exc).__name__
            _log.warning("ui_v2 %s 頁資料狀態無法彙整：%s", slug, error)
    page_health.record_collect_failure(st.session_state, slug, error, now=now)


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
    record_load_failure(page, raw_line)
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
