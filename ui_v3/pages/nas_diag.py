# -*- coding: utf-8 -*-
"""NAS 中繼站診斷頁的 renderer（隔離式離線預覽；只吃 `NasDiagView`，不取數、不連線、不讀憑證、不提供任何操作）。

- `streamlit` 只在函式內 import；HTML 組裝是純函式，可在沒有 Streamlit 的環境單測。
- 字樣：已核准字樣取規則表（尚未設定、無法判定、缺值）；其餘取 `nas_diag_wording` 的暫行字樣，並以 `data-pending-wording` 標記。
  **本檔不硬寫任何中文字樣。** 色與尺寸一律經 `design/theme.py` 取 token。
- 頁內順序：①NAS 設定狀態＋本次檢查結果（徽章：符號＋文字，不單靠顏色）→ ②並列「NAS 中繼檢查結果」與「目標網站本次回應」兩軸
  → ③實際使用路徑、HTTP 結果、檢查時間 → ④原因與建議（人話）→ ⑤預設收合的單一 `<details>`（詳細技術證據，不巢狀）→ 說明。
  「已降級直連」用醒目橫幅標示 NAS 並未正常，色與詞都和「本次連線成功」不同。
- 不顯示 proxy 主機、帳密、完整網址、標頭、任何例外文字；目標只顯示白名單標籤。
- 「立即測試連線」：**目前不渲染任何可操作的測試按鈕**（未來經核准後才出現；預留位置只寫在 README，不上畫面）。唯一的可互動元素是那個收合的 `<details>`。
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
# 「尚未設定」沿用規則表字樣，但 NAS 未設定不算故障：此預覽的徽章用中性灰（規則表 tone 不動；與規則表的差異見 README／回報）。
# 單一來源：鍵同時是狀態值與規則表鍵（`vm.STATE_NOT_CONFIGURED == "not_configured"`，測試鎖定），徽章與狀態字樣共用。
_PREVIEW_TONE_OVERRIDE: Mapping[str, str] = {vm.STATE_NOT_CONFIGURED: "grey"}


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
.uv3n-evidence{{box-sizing:border-box;margin:0 0 {space} 0;border:1px solid {border};border-radius:{theme.v("radius.card")};padding:0 12px}}
.uv3n-evidence > summary{{display:flex;align-items:center;min-height:48px;cursor:pointer;font-size:{body};font-weight:700;overflow-wrap:anywhere}}
.uv3n-evidence[open] > summary{{border-bottom:1px solid {border}}}
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
    tone = _PREVIEW_TONE_OVERRIDE.get(key, entry.tone)   # 未設定在本預覽不帶紅色語意 class（規則表不動）
    return f'<span class="uv3-st uv3-st-{tone}" data-status-key="{escape(key)}">{escape(entry.wording)}</span>'


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
    if state in _PREVIEW_TONE_OVERRIDE:
        return _PREVIEW_TONE_OVERRIDE[state]
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


_CONFIG_SOURCE: Mapping[str, Tuple[str, str]] = {
    vm.CONFIG_SET: ("pending", "config_set"), vm.CONFIG_NOT_SET: ("rule", "not_configured"), vm.CONFIG_UNKNOWN: ("rule", "undetermined")}


def status_block_html(view: vm.NasDiagView) -> str:
    """①NAS 設定狀態＋本次檢查結果（徽章）＋一句話結論。"""
    config = f'<div class="uv3-row" data-row="config" data-config="{escape(view.config_state)}">{_label("label_config")}{_sourced(_CONFIG_SOURCE[view.config_state])}</div>'
    result = f'<div class="uv3-row" data-row="result">{_label("label_result")}{badge_html(view)}</div>'
    return (f'<div class="uv3-card" data-block="nas-status" data-state="{escape(view.state)}">'
            f'{_title("section_status")}{config}{result}{conclusion_html(view)}</div>')


def nas_card_html(view: vm.NasDiagView) -> str:
    return (f'<div class="uv3-card" data-axis="nas" data-health="{escape(view.nas_health)}">{_title("label_nas_card")}'
            f'<div class="uv3-row">{_sourced(W.NAS_HEALTH_SOURCE[view.nas_health])}</div></div>')


def target_card_html(view: vm.NasDiagView) -> str:
    """目標卡：只放標籤與目標軸健康度。HTTP 結果與延遲移到③／證據區（目標軸「尚未測試」時它們屬於 NAS 這一段，不歸給目標）。"""
    rows = (f'<div class="uv3-row" data-row="target-name">{_label("label_target")}{escape(str(view.target_label))}</div>'
            f'<div class="uv3-row" data-row="target-health">{_sourced(W.TARGET_HEALTH_SOURCE[view.target_health])}</div>')
    return (f'<div class="uv3-card" data-axis="target" data-health="{escape(view.target_health)}">'
            f'{_title("label_target_card")}{rows}</div>')


def axes_html(view: vm.NasDiagView) -> str:
    return f'<div class="uv3n-axes" data-block="axes">{nas_card_html(view)}{target_card_html(view)}</div>'


def _http_result(view: vm.NasDiagView) -> str:
    """HTTP 結果：只有目標軸有結果（正常／失敗）才顯示狀態碼；其餘（含 407、無法判定）一律缺值，不拿 NAS 這一段的狀態碼冒充目標回應。"""
    if view.target_health in (vm.HEALTH_OK, vm.HEALTH_FAILED) and view.target_http_status is not None:
        return escape(str(view.target_http_status))
    return _missing()


def last_check_html(view: vm.NasDiagView) -> str:
    """③實際使用路徑、HTTP 結果、檢查時間。"""
    when = escape(str(vm.checked_at_display(view.checked_at))) if view.checked_at is not None else _missing()
    return (f'<div class="uv3-card" data-block="last-check">'
            f'<div class="uv3-row" data-row="route">{_label("label_route")}{_sourced(W.ROUTE_LABEL_SOURCE[view.route_code])}</div>'
            f'<div class="uv3-row" data-row="status-code">{_label("label_status_code")}{_http_result(view)}</div>'
            f'<div class="uv3-row" data-row="checked-at">{_label("label_checked_at")}{when}</div></div>')


def causes_html(view: vm.NasDiagView) -> str:
    """④人話原因與建議：只在有失敗分類時才畫（沒有失敗就不寫「沒有原因」，以免把「無法判定」說成正常）。
    無法歸屬任何一側的分類（逾時／名稱解析／TLS 經由 NAS）用中性說明，並標「NAS 或目標網站（無法區分）」。"""
    lines = []
    for who, cause in (("who_nas", view.nas_cause_key), ("who_target", view.target_cause_key)):
        if cause is not None:
            lines.append(f'<div class="uv3n-cause" data-cause="{escape(cause)}">{_label(who)}{_pending(cause)}</div>')
    if view.unattributed_cause_key is not None:
        text_key = W.UNATTRIBUTED_CAUSE_KEY[view.unattributed_cause_key]
        lines.append(f'<div class="uv3n-cause" data-cause="{escape(text_key)}">{_label("who_unknown")}{_pending(text_key)}</div>')
    if not lines:
        return ""
    return f'<div class="uv3-card" data-block="causes">{_title("label_next_step")}{"".join(lines)}</div>'


def evidence_html(view: vm.NasDiagView) -> str:
    """⑤預設收合的單一 `<details>`（不巢狀）：延遲與兩軸判定。只有字樣與數值，不放任何內部代碼。"""
    latency = f'{escape(str(view.latency_ms))} {_pending("unit_ms")}' if view.latency_ms is not None else _missing()
    rows = (f'<div class="uv3-note" data-note="evidence-scope">{_pending("evidence_scope")}</div>'
            f'<div class="uv3-row" data-row="latency">{_label("label_latency")}{latency}</div>'
            f'<div class="uv3-row" data-row="evidence-nas">{_label("label_nas_card")}{_sourced(W.NAS_HEALTH_SOURCE[view.nas_health])}</div>'
            f'<div class="uv3-row" data-row="evidence-target">{_label("label_target_card")}{_sourced(W.TARGET_HEALTH_SOURCE[view.target_health])}</div>')
    return (f'<details class="uv3n-evidence" data-block="evidence"><summary data-summary="evidence">{_pending("evidence_summary")}</summary>'
            f'{rows}</details>')


def notes_html() -> str:
    return (f'<div class="uv3-note" data-note="offline">{_pending("offline_note")}</div>'
            f'<div class="uv3-note" data-note="pending-wording">{_pending("pending_notice")}</div>')


# ───────────────────────────── 整頁 ─────────────────────────────

def page_html(view: vm.NasDiagView) -> str:
    """①設定＋結果 → ②兩軸 → ③路徑／HTTP／時間 → ④原因與建議 → ⑤收合證據 → 說明。**不含任何按鈕或連結（只有一個收合的 details）。**"""
    if not isinstance(view, vm.NasDiagView):
        raise TypeError("view must be a NasDiagView")
    return status_block_html(view) + axes_html(view) + last_check_html(view) + causes_html(view) + evidence_html(view) + notes_html()


def render(view: vm.NasDiagView) -> None:
    import streamlit as st

    st.markdown(CSS, unsafe_allow_html=True)
    st.title(W.nas_diag_wording("page_title").text, anchor=False)   # 不產生標題錨點連結（頁面不得有任何連結）
    st.markdown(page_html(view), unsafe_allow_html=True)
