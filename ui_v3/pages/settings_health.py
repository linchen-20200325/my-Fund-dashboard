# -*- coding: utf-8 -*-
"""⚙️ 設定→資料健康度 第一階段 renderer（BL-0540 Phase 1A；客戶 2026-11-21 裁示 #7056447977）。

- **唯讀**：只吃 `SettingsHealthModel`（由市場頁已產生的 `DomainStatus` 快照組出）；不取數、不連線、不讀憑證、不提供任何操作。
  沒有快照 → 如實寫「尚未評估」並給市場入口；不自行觸發讀取、不偽造成功、不補現在時間、不給全站總數。
- **範圍**：頁首明示只涵蓋「市場與利率」，不是全站健康度；與 🌍 市場頁的必要揭露**並存**（市場頁一字不動）。
- 字樣：狀態符號與字樣取規則表（缺資料／取數失敗／尚未設定／無法判定）；其餘為 `preview_wording` 的暫時字樣（標 `data-pending-wording`）。
  本檔不硬寫中文字樣。失敗／未評估／未設定／缺資料各自獨立，不互相冒充。
- 只用 `streamlit`（函式內 import）／`html`／標準庫；HTML 組裝是純函式，可在沒有 Streamlit 的環境單測。
"""
from __future__ import annotations

from html import escape
from typing import Optional

from shared.ui_semantics import rules
from ui_v3.design import theme
from ui_v3.pages import chrome, mkt
from ui_v3.shell.registry import IA_PAGES
from ui_v3.viewmodels import preview_wording as W
from ui_v3.viewmodels import settings_health as vm
from ui_v3.viewmodels.common import STATUS_FAILED, STATUS_MISSING, STATUS_UNDETERMINED

PAGE_TITLE = next(p.title for p in IA_PAGES if p.slug == "set")
MARKET_TITLE = next(p.title for p in IA_PAGES if p.slug == "mkt")
BACK_KEY = "uv3-health-back"

_STATE_TO_STATUS = {vm.STATE_MISSING: STATUS_MISSING, vm.STATE_FAILED: STATUS_FAILED,
                    vm.STATE_NOT_CONFIGURED: STATUS_FAILED, vm.STATE_UNDETERMINED: STATUS_UNDETERMINED}


def css() -> str:
    caption, text2, focus = theme.v("type.caption"), theme.v("color.text.secondary"), theme.v("color.pill.focus")
    link = f'.st-key-{BACK_KEY} a[data-testid="stPageLink-NavLink"]'
    return (f"<style>{theme.card_css('.uv3-health-row')}"
            # 返回市場連結：觸控高度 ≥48px、鍵盤焦點外框可見（Streamlit 預設兩者皆不足；真 Chromium 實測 28px、outline none）
            f"{link}{{min-height:48px;display:flex;align-items:center}}"
            f"{link}:focus-visible{{outline:2px solid {focus};outline-offset:2px}}"
            f".uv3-health-row .uv3-row{{overflow-wrap:anywhere}}"
            f".uv3-health-label{{font-size:{caption};color:{text2};margin-right:6px}}"
            f".uv3-health-scope{{margin:.4rem 0;line-height:1.55}}</style>")


def _missing_html() -> str:
    entry = rules.entry("missing")
    return f'<span data-status-key="missing">{escape(entry.wording)}</span>'


def _value_html(value: Optional[str]) -> str:
    return escape(value) if value else _missing_html()     # 缺值一律寫規則表的缺資料字樣：不是 0、不補現在、不以他欄代替


def _fetched_html(stamp: Optional[str]) -> str:
    if not stamp:
        return _missing_html()
    shown = chrome.format_taipei(stamp, full=True)
    if shown is None:                                          # 不帶時區／無法解析：不猜、不改寫成台北時間，寫規則表的「無法判定」
        entry = rules.entry("undetermined")
        return f'<span data-status-key="undetermined">{escape(entry.wording)}</span>'
    return escape(shown)


def _state_html(row: vm.HealthRow) -> str:
    if row.state == vm.STATE_OK:
        return f'<span class="uv3-st" data-status-key="ok">{W.span("health_state_ok")}</span>'
    return mkt.status_html(_STATE_TO_STATUS[row.state], row.reason_code, row.label_key, plain=True)


def row_html(row: vm.HealthRow) -> str:
    """② 一列：序列名＋狀態，下方來源、資料日、取得時間。純函式，只由該列自身決定（與其他列無關）。"""
    def line(label_key: str, value_html: str) -> str:
        return f'<div class="uv3-row"><span class="uv3-health-label">{W.span(label_key)}</span>{value_html}</div>'

    attrs = (f'data-health-key="{escape(row.key)}" data-health-state="{escape(row.state)}" '
             f'data-reason="{escape(row.reason_code or "")}" data-as-of="{escape(row.as_of or "")}" '
             f'data-fetched-at="{escape(row.fetched_at or "")}" data-gaps="{escape(",".join(row.gaps))}"')
    head = f'<div class="uv3-row"><strong>{escape(W.text(row.label_key))}</strong> {_state_html(row)}</div>'
    body = (line("health_field_source", _value_html(row.source)) + line("health_field_as_of", _value_html(row.as_of))
            + line("health_field_fetched", _fetched_html(row.fetched_at)))
    return f'<div class="uv3-card uv3-health-row" {attrs}>{head}{body}</div>'


def scope_html(model: vm.SettingsHealthModel) -> str:
    tally = [c.tally for c in model.categories if c.tally is not None]
    total = {name: sum(getattr(t, name) for t in tally) for name in vm.HEALTH_STATES}
    n = sum(total.values())
    return (f'<div class="uv3-health-scope" data-health="scope" data-covered="{escape(",".join(model.covered_keys))}">'
            f'<div class="uv3-row">{W.span("health_scope", n=n)}</div>'
            f'<div class="uv3-row" data-health="tally">{W.span("health_tally", ok=total["ok"], gone=total["missing"], fail=total["failed"],
                                                          unset=total["not_configured"], undet=total["undetermined"])}</div>'
            f'<div class="uv3-row">{W.span("health_scope_note")}</div></div>')


def no_snapshot_html() -> str:
    return f'<div class="uv3-row" data-health="no-snapshot">{W.span("health_no_snapshot")}</div>'


def render(model: Optional[vm.SettingsHealthModel], *, market_page: object = None) -> None:
    """`model is None` ＝ 這個 session 還沒有快照。`market_page`：🌍 的 `st.Page`（給返回入口；沒有就不畫連結）。"""
    import streamlit as st

    md = lambda html: st.markdown(html, unsafe_allow_html=True)  # noqa: E731
    md(css())
    st.title(PAGE_TITLE, anchor=False)
    md(f'<h3 data-health="title">{W.span("health_title")}</h3>')
    if model is None:
        md(no_snapshot_html())
    else:
        md(scope_html(model))
        md("".join(row_html(r) for r in model.rows))
    if market_page is not None:
        with st.container(key=BACK_KEY):
            st.page_link(market_page, label=MARKET_TITLE)
    chrome.render_footer()
