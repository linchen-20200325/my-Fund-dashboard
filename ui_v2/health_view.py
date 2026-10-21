# -*- coding: utf-8 -*-
"""四頁頁首（主要原因＋另有；BL-0250 批次 3-C U9）、「前往設定與診斷」導覽 —— 畫法（Phase 3 P0-②）。

內容（字樣、判定）全部住在 `ui_v2/health.py`（純函式）；本檔只負責畫。

⛔ **導覽只換頁**（44 第五節第三小節 `導覽`、護欄 3）：`render_settings_link` 的函式本體只准呼叫
`st.page_link`、`st.caption`、`st.markdown`（AST 守衛：`tests/ui_v2/test_health_logic.py`），
不讀也不寫任何資料表，不觸發取數、重新整理、存檔或任何寫入。
"""

from __future__ import annotations

import functools
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


# 頁首各段的色調（色票沿用各頁 `theme.tone_hex`，不另立）：⛔ 紅、◇ 灰、◷ 與尚未設定（不加符號的那幾段）中性。
# ~~`render_status_line`（之七其二第 4 條的資料狀態行：◷／◇／⛔／尚未設定四類同類列一次）~~ → BL-0250 批次 3-C（U9；
# 44 第七節第三小節之十四；有意識的政策變更，不是漏刪；決策者：客戶 `DEC-2026-10-21-01`）：改畫主要原因＋另有，
# 內容由 `page_health.header_view` 交出（與設定與診斷頁總表的主要原因欄同一支 `main_reason`、同一份記錄）。
HEADER_TONES = {page_health.KIND_UNCONFIGURED: "紅", page_health.KIND_FETCH: "紅", page_health.KIND_MISSING: "灰",
                page_health.KIND_STALE: "中性"}
OTHER_TONES = {page_health.KIND_UNCONFIGURED: "中性", page_health.KIND_FETCH: "紅", page_health.KIND_MISSING: "灰",
               page_health.KIND_STALE: "中性"}


def render_page_header(slug: str, *, as_of, tone_hex, settings_page=None) -> None:
    """四頁頁首（U9）＋導覽。讀本頁剛由 `record_page_health` 記下的那一格（`page_health.recorded`），交給
    `page_health.header_view` 組字；本函式只負責畫。`tone_hex`：該頁 `theme.tone_hex`。"""
    view = page_health.header_view(page_health.recorded(st.session_state, slug), as_of=as_of)
    muted = tone_hex("灰")
    rows = []
    if view["inline"]:
        main = f'<span style="color:{tone_hex("中性")}">{_esc(view["main"])}</span>　' if view["main"] else ""
        rows.append(f'<div>{main}<span style="color:{muted}">{_esc(view["as_of"])}</span></div>')
    else:
        rows.append(f'<div style="color:{tone_hex(HEADER_TONES[view["main_kind"]])}">{_esc(view["main"])}</div>')
        if view["others"]:
            parts = page_health.HEADER_SEP.join(
                f'<span style="color:{tone_hex(OTHER_TONES[kind])}">{_esc(text)}</span>' for kind, text in view["others"])
            head, _sep, _rest = page_health.TEXT_OTHERS.partition("{parts}")
            rows.append(f"<div>{_esc(head)}{parts}</div>")
        rows.append(f'<div style="color:{muted}">{_esc(view["as_of"])}</div>')
    st.markdown(f'<div class="v2-status-line" role="status">{"".join(rows)}</div>', unsafe_allow_html=True)
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


# ~~`render_provenance`（④「核心卡的來源與新鮮度」展開區）~~ → BL-0250 批次 3-C（G2；線框第六版第 7 節第 2、7、11 列；
# 44 第七節第三小節之十四）：四頁不再畫這一枚，同一份來源與新鮮度在設定與診斷頁的各頁資料狀態總表明細；本函式沒有人用，
# 同次刪除（`CLAUDE.md` §-1.5.1c 判定 3；有意識的政策變更，不是漏刪；`DEC-2026-10-21-01`）。


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
        # 3-B 第二輪稽核回修 B：頁上畫成 ⬜ 的那幾處不計數，明細照抄頁上那一句（`health.boxed_entries`）。
        normal = health.normal_entries(display, cards, data_class=normal_class) + health.boxed_entries(display)
    except COLLECT_ERRORS as exc:
        _log.warning("ui_v2 %s 頁資料狀態無法彙整：%s", slug, type(exc).__name__)
        return {"error": type(exc).__name__}
    for where in unresolved:
        _log.warning("ui_v2 %s 頁有一句取數失敗認不出資料類：%s %s", slug, where.get("code"), where.get("field"))
    return {"items": items, "normal": normal}


def record_page_health(slug: str, display: dict, collected: dict, cards, *, as_of) -> None:
    """記下這一頁這一次畫出來的資料狀態，給設定與診斷頁的各頁資料狀態總表（BL-0250 批次 3-B；`ui_v2/page_health.py::record`）。
    `collected`：`collect_page_health` 的回傳；◷ 在這裡補（`move_card_provenance` 之後才看得到）。只記、不取數、不寫入任何資料表；
    記錄時間取當下（台北時間由總表換算）。收集或記錄出錯 → 這一頁整格改寫成收集失敗（不留上一次的記錄）、寫 log，頁面不受影響。"""
    now = datetime.now(timezone.utc)
    error = collected.get("error")
    if error is None:
        try:
            page_health.record(
                st.session_state, slug, list(collected["items"]) + health.stale_items(display, cards),
                as_of=as_of, now=now, normal=collected["normal"],
            )
            return
        except COLLECT_ERRORS as exc:
            error = type(exc).__name__
            _log.warning("ui_v2 %s 頁資料狀態無法彙整：%s", slug, error)
    page_health.record_collect_failure(st.session_state, slug, error, now=now)


def guard_page(slug: str):
    """四頁 `render` 的外框（3-B 第二輪稽核回修可選 3）：正式模式（有傳 `load_live`）畫頁時拋出例外 —— 不論是記錄之後畫頁崩潰，
    還是收集那一步拋出錯誤邊界以外的例外 —— 先把這一頁在總表的記錄整格改寫成收集失敗（總表不留上一筆正常記錄）、寫 log，
    然後照舊往上拋，不吞。Streamlit 的停止與重跑（`BaseException` 那一族）不接。示範模式不經過這一步。"""
    def decorate(render):
        @functools.wraps(render)
        def wrapped(*args, **kwargs):
            try:
                return render(*args, **kwargs)
            except Exception as exc:
                if kwargs.get("load_live") is not None and slug in page_health.PAGE_NAMES:
                    _log.warning("ui_v2 %s 頁畫頁失敗，總表記錄改寫為無法彙整：%s", slug, type(exc).__name__)
                    page_health.record_collect_failure(st.session_state, slug, type(exc).__name__,
                                                       now=datetime.now(timezone.utc))
                raise
        return wrapped
    return decorate


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
