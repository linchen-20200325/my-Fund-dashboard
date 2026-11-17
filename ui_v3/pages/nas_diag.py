# -*- coding: utf-8 -*-
"""NAS 中繼站診斷頁的 renderer（隔離式離線預覽；只吃 `NasDiagView`，不取數、不連線、不讀憑證、不提供任何操作）。

- `streamlit` 只在函式內 import；HTML 組裝是純函式，可在沒有 Streamlit 的環境單測。
- 字樣：已核准字樣取規則表（尚未設定、無法判定、缺值）；其餘取 `nas_diag_wording` 的暫行字樣，並以 `data-pending-wording` 標記。
  **本檔不硬寫任何中文字樣。** 色與尺寸一律經 `design/theme.py` 取 token。
- 畫面：「NAS 中繼站狀態」區塊（六態徽章＋一句話結論＋實際路徑）、兩軸卡片（NAS 中繼健康度／目標網站可用性）、最近檢查、人話原因與建議。
  「已降級直連」用醒目橫幅標示 NAS 並未正常，色與詞都和「連線成功」不同。
- 不顯示 proxy 主機、帳密、完整網址、標頭、任何例外文字；目標只顯示白名單標籤。
- 「立即測試連線」：此預覽**沒有**按鈕或連結，只放一段說明（即時測試尚未核准）。
"""
from __future__ import annotations

from html import escape
from typing import Mapping, Tuple

from shared.ui_semantics import rules
from ui_v3.design import theme, tokens
from ui_v3.shell import nav
from ui_v3.viewmodels import nas_diag as vm
from ui_v3.viewmodels import nas_diag_wording as W

# 狀態 → tone 鍵（顏色只是輔助，每個狀態都有各自的文字）。規則表來源的狀態取規則表的 tone，其餘暫行。
_PENDING_STATE_TONE: Mapping[str, str] = {
    vm.STATE_NOT_TESTED: "grey", vm.STATE_OK: "neutral", vm.STATE_FAILED: "red", vm.STATE_DEGRADED: "yellow"}


def _css() -> str:
    gutter, page, section = theme.v("gutter.mobile"), theme.v("type.page"), theme.v("type.section")
    caption, body = theme.v("type.caption"), theme.v("type.body")
    text2, border, space = theme.v("color.text.secondary"), theme.v("color.card.border"), theme.v("space.2")
    tone_rules = []
    for tone in tokens.TONE_KEYS:
        t = theme.m("color.tone." + tone)
        tone_rules.append(".uv3n-tone-" + tone + "{color:" + t["text"] + ";background:" + t["background"] + ";border-color:" + t["border"] + "}\n")
    tones = "".join(tone_rules)
    yellow = theme.m("color.tone.yellow")
    return f"""
<style>
{theme.app_css()}
.block-container,.stMainBlockContainer{{padding-top:3.4rem !important}}
.block-container{{max-width:1100px;padding-left:{gutter};padding-right:{gutter};padding-top:3.4rem}}
h1{{font-size:{page} !important;padding:.2rem 0 !important}}
h3{{font-size:{section} !important}}
.uv3-pending{{border-bottom:1px dashed {border}}}
.uv3-st{{white-space:normal}}
.uv3-st-red{{font-weight:700}}
.uv3-row{{margin:{theme.v("space.1")} 0;line-height:1.55;overflow-wrap:anywhere}}
.uv3-label{{font-size:{caption};color:{text2};margin-right:6px}}
.uv3-note{{font-size:{caption};color:{text2};line-height:1.5;margin:.15rem 0;overflow-wrap:anywhere}}
{theme.card_css(".uv3-card")}
.uv3n-title{{margin:0 0 4px 0;font-size:{body};font-weight:700}}
.uv3n-badge{{display:inline-block;box-sizing:border-box;max-width:100%;border:2px solid {border};border-radius:{theme.v("radius.card")};padding:4px 12px;font-size:{body};font-weight:700;overflow-wrap:anywhere}}
{tones}.uv3n-banner{{box-sizing:border-box;margin:{space} 0;padding:10px 12px;border-left:8px solid {yellow['border']};background:{yellow['background']};color:{yellow['text']};font-size:{body};font-weight:700;line-height:1.5;overflow-wrap:anywhere}}
.uv3n-axes{{display:grid;grid-template-columns:minmax(0,1fr);gap:{space};margin-bottom:{space}}}
.uv3n-axes > .uv3-card{{margin-bottom:0;min-width:0}}
.uv3n-cause{{border-top:1px solid {border};padding:{theme.v("space.1")} 0;line-height:1.55;overflow-wrap:anywhere}}
@media (min-width:{nav.MOBILE_MAX_PX + 1}px){{
  .uv3n-axes{{grid-template-columns:repeat(2,minmax(0,1fr))}}
}}
</style>
"""


# 頁面 CSS（只在 `render()` 注入）。
CSS = _css()


# ───────────────────────────── 小工具（純字串） ─────────────────────────────

def _pending(key: str) -> str:
    item = W.nas_diag_wording(key)
    return f'<span class="uv3-pending" data-pending-wording="{escape(key)}">{escape(item.text)}</span>'


def _title(key: str) -> str:
    """卡片標題。刻意不用 h4：Streamlit 會替 markdown 裡的 h1～h6 自動加上錨點連結（多出可聚焦的連結，與「沒有連結」衝突）。"""
    return f'<div class="uv3n-title" role="heading" aria-level="4">{_pending(key)}</div>'


def _status(key: str) -> str:
    entry = rules.entry(key)
    return f'<span class="uv3-st uv3-st-{entry.tone}" data-status-key="{escape(key)}">{escape(entry.wording)}</span>'


def _label(key: str) -> str:
    return f'<span class="uv3-label">{_pending(key)}</span>'


def _sourced(source: Tuple[str, str]) -> str:
    kind, key = source
    if kind == "rule":
        return _status(key)
    if kind == "pending":
        return _pending(key)
    raise ValueError("unknown wording source")


def _missing() -> str:
    return _status("missing")


def state_tone(state: str) -> str:
    source = W.STATE_LABEL_SOURCE[state]
    return rules.entry(source[1]).tone if source[0] == "rule" else _PENDING_STATE_TONE[state]


# ───────────────────────────── 區塊 ─────────────────────────────

def badge_html(view: vm.NasDiagView) -> str:
    return (f'<span class="uv3n-badge uv3n-tone-{state_tone(view.state)}" data-badge="state" data-state="{escape(view.state)}">'
            f'{_sourced(W.STATE_LABEL_SOURCE[view.state])}</span>')


def conclusion_html(view: vm.NasDiagView) -> str:
    key = W.CONCLUSION_KEY[(view.state, view.reason_key)]
    if view.state == vm.STATE_DEGRADED:   # 醒目橫幅：NAS 並未正常
        return f'<div class="uv3n-banner" role="status" data-conclusion="degraded">{_pending(key)}</div>'
    return f'<div class="uv3-row" data-conclusion="{escape(view.state)}">{_pending(key)}</div>'


def status_block_html(view: vm.NasDiagView) -> str:
    route = f'<div class="uv3-row" data-row="route">{_label("label_route")}{_sourced(W.ROUTE_LABEL_SOURCE[view.route_code])}</div>'
    return (f'<div class="uv3-card" data-block="nas-status" data-state="{escape(view.state)}">'
            f'{_title("section_status")}{badge_html(view)}{conclusion_html(view)}{route}</div>')


def nas_card_html(view: vm.NasDiagView) -> str:
    return (f'<div class="uv3-card" data-axis="nas" data-health="{escape(view.nas_health)}">{_title("label_nas_card")}'
            f'<div class="uv3-row">{_sourced(W.NAS_HEALTH_SOURCE[view.nas_health])}</div></div>')


def target_card_html(view: vm.NasDiagView) -> str:
    """目標卡。目標軸「尚未測試」（例：407，沒有任何目標嘗試）時只顯示標籤與健康度：狀態碼與延遲屬於 NAS 這一段，不歸給目標。"""
    rows = (f'<div class="uv3-row" data-row="target-name">{_label("label_target")}{escape(str(view.target_label))}</div>'
            f'<div class="uv3-row" data-row="target-health">{_sourced(W.TARGET_HEALTH_SOURCE[view.target_health])}</div>')
    if view.target_health in (vm.HEALTH_OK, vm.HEALTH_FAILED):
        status = escape(str(view.target_http_status)) if view.target_http_status is not None else _missing()
        latency = f'{escape(str(view.latency_ms))} {_pending("unit_ms")}' if view.latency_ms is not None else _missing()
        rows += (f'<div class="uv3-row" data-row="status-code">{_label("label_status_code")}{status}</div>'
                 f'<div class="uv3-row" data-row="latency">{_label("label_latency")}{latency}</div>')
    else:
        rows += f'<div class="uv3-row" data-row="no-target-result">{_missing()}</div>'
    return (f'<div class="uv3-card" data-axis="target" data-health="{escape(view.target_health)}">'
            f'{_title("label_target_card")}{rows}</div>')


def axes_html(view: vm.NasDiagView) -> str:
    return f'<div class="uv3n-axes" data-block="axes">{nas_card_html(view)}{target_card_html(view)}</div>'


def last_check_html(view: vm.NasDiagView) -> str:
    when = escape(str(vm.checked_at_display(view.checked_at))) if view.checked_at is not None else _missing()
    return (f'<div class="uv3-card" data-block="last-check"><div class="uv3-row">{_label("label_checked_at")}{when}'
            f'{_pending("separator")}{_label("label_result")}{_sourced(W.STATE_LABEL_SOURCE[view.state])}</div></div>')


def causes_html(view: vm.NasDiagView) -> str:
    """人話原因與建議：只在有失敗分類時才畫（沒有失敗就不寫「沒有原因」，以免把「無法判定」說成正常）。"""
    lines = []
    for who, cause in (("who_nas", view.nas_cause_key), ("who_target", view.target_cause_key)):
        if cause is not None:
            lines.append(f'<div class="uv3n-cause" data-cause="{escape(cause)}">{_label(who)}{_pending(cause)}</div>')
    if not lines:
        return ""
    return f'<div class="uv3-card" data-block="causes">{_title("label_next_step")}{"".join(lines)}</div>'


def notes_html() -> str:
    return (f'<div class="uv3-note" data-note="live-test">{_pending("live_test_note")}</div>'
            f'<div class="uv3-note" data-note="pending-wording">{_pending("pending_notice")}</div>')


# ───────────────────────────── 整頁 ─────────────────────────────

def page_html(view: vm.NasDiagView) -> str:
    """狀態區塊 → 兩軸卡片 → 最近檢查 → 原因與建議 → 說明。**不含任何按鈕或連結。**"""
    if not isinstance(view, vm.NasDiagView):
        raise TypeError("view must be a NasDiagView")
    return status_block_html(view) + axes_html(view) + last_check_html(view) + causes_html(view) + notes_html()


def render(view: vm.NasDiagView) -> None:
    import streamlit as st

    st.markdown(CSS, unsafe_allow_html=True)
    st.title(W.nas_diag_wording("page_title").text, anchor=False)   # 不產生標題錨點連結（頁面不得有任何連結）
    st.markdown(page_html(view), unsafe_allow_html=True)
