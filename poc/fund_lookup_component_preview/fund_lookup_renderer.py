# -*- coding: utf-8 -*-
"""單檔基金查詢呈現元件｜renderer（純呈現；不取數、不連線、不讀憑證、不寫任何東西）。

授權：`DEC-2026-11-18-04`（要點轉述，來源待核，NOT VERIFIED）。這是**隔離 poc**，不是 🔍 頁面、不掛 registry／`app_preview`／導覽。

- 輸入是**注入式 ViewModel**（`ui_v3.viewmodels.fund_lookup.FundLookupView`）；本檔**不 import adapter、services、repositories、infra**，
  也不 import 任何網路或檔案相關模組。ViewModel 由 harness 經 adapter 產生，再交給本檔。
- HTML 組裝是純函式（可在沒有 Streamlit 的環境單測）；`streamlit` 只在 `render_*` 函式內 import。
- 使用者可控字串（`input_code`、`fund_name`、日期）一律 `safe()` 後才進 HTML（含 `$`，避免 Streamlit 的數學語法吃掉）。
- 顯示欄位只有五個（輸入代碼、基金名稱、配息方式、成立日期、經理費率），依這個順序；**沒有任何其他欄位**（幣別、淨值、報酬、績效、取得時間、供應者…）。
- 每個非 `NOT_QUERIED` 狀態都有獨立文案，**沒有任何一個說「基金不存在／查無」**；取數失敗、頁面無法確認、入口攔截彼此不混用。
- 缺值不寫成 0、「無」、「不配息」；`MISSING` 與 `CONFLICT` 各有獨立文案與 DOM 標記（`data-field-status`）。
- 色與尺寸一律經 `ui_v3.design.theme` 取 token，不寫死色碼。字樣取 `fund_lookup_wording`（新字樣皆 PendingWording）。
"""
from __future__ import annotations

from html import escape
from typing import Optional

import fund_lookup_wording as W
from ui_v3.design import theme
from ui_v3.viewmodels.fund_lookup import FieldStatus, FieldView, FundLookupView, LookupState

KEY_INPUT = "fl_query_input"
KEY_VIEW = "fl_last_view"
KEY_FORM = "fl_lookup_form"
MAX_INPUT_CHARS = 100
ID_STATUS = "fl-status"

#: 顯示欄位（依客戶列出的順序）：(data-row 名稱, 標籤字樣鍵)。
ROWS = (
    ("input-code", "row_input_code"),
    ("name", "row_name"),
    ("dividend-mode", "row_dividend_mode"),
    ("inception", "row_inception"),
    ("mgmt-fee", "row_mgmt_fee"),
)
DIVIDEND_KEYS = {"dist": "div_mode_distributing", "accum": "div_mode_accumulating"}


def safe(value: object) -> str:
    """使用者可控字串 → HTML 安全文字（escape；另把 `$`、反斜線與換行轉成字元參照，避免 Streamlit markdown 的數學／跳脫語法介入）。"""
    return (escape(str(value), quote=True).replace("$", "&#36;").replace("\\", "&#92;")
            .replace("\n", "&#10;").replace("\r", "&#13;"))


def _css() -> str:
    gutter, page, body, caption = theme.v("gutter.mobile"), theme.v("type.page"), theme.v("type.body"), theme.v("type.caption")
    text1, text2, border, primary = theme.v("color.text.primary"), theme.v("color.text.secondary"), theme.v("color.card.border"), theme.v("color.primary")
    space1, space2, radius = theme.v("space.1"), theme.v("space.2"), theme.v("radius.card")
    grey, red = theme.m("color.tone.grey"), theme.m("color.tone.red")
    return f"""
<style>
{theme.app_css()}
.block-container,.stMainBlockContainer{{padding-top:3.4rem !important}}
.block-container{{max-width:720px;padding-left:{gutter};padding-right:{gutter};padding-top:3.4rem}}
h1{{font-size:{page} !important;padding:.2rem 0 !important}}
.uv3-pending{{border-bottom:1px dashed {border}}}
.uv3-row{{margin:{space1} 0;line-height:1.55;overflow-wrap:anywhere}}
.uv3-label{{font-size:{caption};color:{text2};margin-right:6px}}
.uv3-note{{font-size:{caption};color:{text2};line-height:1.5;margin:.15rem 0;overflow-wrap:anywhere}}
{theme.card_css(".uv3-card")}
.fl-card{{box-sizing:border-box;max-width:100%;color:{text1};font-size:{body}}}
.fl-tag{{display:inline-block;box-sizing:border-box;max-width:100%;border:1px solid {grey['border']};background:{grey['background']};color:{grey['text']};border-radius:{radius};padding:2px 8px;font-size:{caption};margin-bottom:{space1}}}
.fl-status{{margin:{space1} 0 {space2} 0;line-height:1.55;font-size:{body};font-weight:700;overflow-wrap:anywhere}}
.uv3-st{{display:inline-block;box-sizing:border-box;max-width:100%;border:1px solid {border};border-radius:{radius};padding:1px 8px;white-space:normal}}
.uv3-st-grey{{border-color:{grey['border']};background:{grey['background']};color:{grey['text']}}}
.uv3-st-red{{border-color:{red['border']};background:{red['background']};color:{red['text']}}}
.fl-list{{margin:0;padding:0}}
.fl-row{{margin:{space1} 0;line-height:1.55;overflow-wrap:anywhere}}
.fl-row dt{{display:inline;font-size:{caption};color:{text2};margin:0 6px 0 0}}
.fl-row dd{{display:inline;margin:0}}
.fl-value-missing,.fl-value-conflict{{color:{text2}}}
.fl-card[data-state="failed"]{{border-color:{red['border']}}}
.fl-card[data-state="unmatched"],.fl-card[data-state="blocked"]{{border-style:dashed;border-color:{text2}}}
/* 原生控制項的觸控目標 ≥48px；焦點環不靠瀏覽器預設（Streamlit 會改寫），改用 primary token 的 2px 外框 */
[data-testid="stTextInputRootElement"]{{min-height:48px;box-sizing:border-box;border:1px solid {border}}}
[data-testid="stTextInput"] input{{min-height:48px;box-sizing:border-box}}
[data-testid="stFormSubmitButton"] button{{min-height:48px;min-width:48px;border:1px solid {border}}}
[data-testid="stTextInput"] input:focus-visible,[data-testid="stFormSubmitButton"] button:focus-visible{{outline:2px solid {primary};outline-offset:2px}}
[data-testid="stForm"]{{padding:0}}
/* Streamlit 在表單輸入框內自帶「Press Enter to submit form」與字數計數，會蓋住長輸入；Enter 照常提交，只隱藏這行提示 */
[data-testid="InputInstructions"]{{display:none}}
</style>
"""


CSS = _css()


# ───────────────────────────── 純函式：HTML 片段 ─────────────────────────────

def isin_note_html() -> str:
    """輸入框正下方常駐一行、無狀態符號的 ISIN 未啟用說明。"""
    return f'<div class="uv3-note" data-block="isin-note">{W.pending("isin_note")}</div>'


def idle_html() -> str:
    """查詢前（尚未送出）：整張卡只顯示『尚未查詢』，沒有任何欄位列。"""
    return (f'<div class="uv3-card fl-card" data-block="lookup-idle" data-state="idle" role="region" aria-labelledby="{ID_STATUS}">'
            f'<div class="fl-status" id="{ID_STATUS}" data-row="idle" role="status">{W.pending("not_queried")}</div></div>')


def _dl_row(name: str, label_key: str, value_html: str, field_status: str) -> str:
    return (f'<div class="fl-row" data-row="{escape(name)}" data-field-status="{escape(field_status)}">'
            f'<dt class="uv3-label">{W.pending(label_key)}</dt><dd>{value_html}</dd></div>')


def _field_value(field: FieldView, text_html: Optional[str] = None) -> tuple:
    """欄位 → (值 HTML, 欄位狀態名)。VALUE＝值；MISSING／CONFLICT＝各自的暫行文案（不寫 0、不寫「無」）。"""
    if field.status is FieldStatus.VALUE:
        return (text_html if text_html is not None else safe(field.value)), "value"
    if field.status is FieldStatus.MISSING:
        return f'<span class="fl-value-missing" data-kind="missing">{W.pending("field_missing")}</span>', "missing"
    if field.status is FieldStatus.CONFLICT:
        return f'<span class="fl-value-conflict" data-kind="conflict">{W.pending("field_conflict")}</span>', "conflict"
    raise ValueError(f"未知的欄位狀態 {field.status!r}")


def _state_parts(view: FundLookupView) -> tuple:
    """狀態 → (state 名, 狀態列 HTML, 補充說明 HTML 列表, role)。每個狀態獨立文案；沒有任何『基金不存在』。"""
    s, reason = view.state, view.reason_code
    if s is LookupState.RESULT:
        return "result", W.pending("state_result"), [], "status"
    if s is LookupState.SOURCE_FAILED:
        return "failed", W.status("fetch_failed"), [W.pending("failed_impact"), W.pending(f"failed_{reason}"), W.pending("not_identity")], "alert"
    if s is LookupState.PAGE_UNMATCHED:
        return "unmatched", W.status("undetermined"), [W.pending("unmatched_impact"), W.pending(f"unmatched_{reason}"), W.pending("not_identity")], "status"
    if s is LookupState.BLOCKED:
        extra = [W.pending("blocked_impact"), W.pending(f"blocked_{reason}")]
        if reason == "isin_shape":
            extra.append(W.pending("blocked_isin_detail"))
        return "blocked", W.pending("blocked_impact"), extra[1:], "alert"
    raise ValueError(f"未知的查詢狀態 {s!r}")


def lookup_card_html(view: FundLookupView, *, fake: bool) -> str:
    """依 ViewModel 組結果卡。`fake=True` 時卡首先出一個『FAKE 模擬』標籤（必在任何欄位列之前）。`NOT_QUERIED` → 『尚未查詢』卡。"""
    if not isinstance(view, FundLookupView):
        raise TypeError("view must be a FundLookupView")
    if view.state is LookupState.NOT_QUERIED:
        return idle_html()
    name, status_html, extras, role = _state_parts(view)
    parts = []
    if fake:
        parts.append(f'<span class="fl-tag" data-tag="fake">{W.pending("fake_tag")}</span>')
    # 狀態列與可操作原因句放進同一個 live region 容器（role 在容器上），螢幕閱讀器一次讀完整段
    live = [f'<div class="fl-status" id="{ID_STATUS}" data-row="status" data-kind="state-line">{status_html}</div>']
    live += [f'<div class="uv3-note" data-note="extra">{x}</div>' for x in extras]
    parts.append(f'<div class="fl-live" data-live="true" role="{role}">{"".join(live)}</div>')
    rows = []
    echoed = view.input_code.strip(" ") if isinstance(view.input_code, str) else ""
    if echoed:                                           # 被安全攔截者結構上沒有回顯；全空白輸入也不畫輸入代碼列
        rows.append(_dl_row("input-code", "row_input_code", f'<span data-value="input-code">{safe(echoed)}</span>', "value"))
    if view.state is LookupState.RESULT:
        f = view.fields
        mode_html = None
        if f.dividend_policy.status is FieldStatus.VALUE:
            mode_html = W.pending(DIVIDEND_KEYS[f.dividend_policy.value])
        for row_name, label_key, field, shown in (("name", "row_name", f.fund_name, None), ("dividend-mode", "row_dividend_mode", f.dividend_policy, mode_html),
                                                  ("inception", "row_inception", f.inception_on, None), ("mgmt-fee", "row_mgmt_fee", f.mgmt_fee_rate_pct, None)):
            value_html, fs = _field_value(field, shown)
            rows.append(_dl_row(row_name, label_key, value_html, fs))
    if rows:
        parts.append(f'<dl class="fl-list" data-block="rows">{"".join(rows)}</dl>')
    parts.append(f'<div class="uv3-note" data-note="single">{W.pending("single_note")}</div>')
    reason_attr = f' data-reason="{escape(view.reason_code)}"' if view.reason_code else ""
    return (f'<div class="uv3-card fl-card" data-block="lookup-result" data-state="{name}"{reason_attr} role="region" aria-labelledby="{ID_STATUS}">'
            f'{"".join(parts)}</div>')


# ───────────────────────────── Streamlit 部分（widgets 與 session_state） ─────────────────────────────

def render_css() -> None:
    import streamlit as st

    st.markdown(CSS, unsafe_allow_html=True)


def render_form() -> Optional[str]:
    """表單：單一輸入框 → 常駐 ISIN 說明 → 查詢鈕（st.form，Enter 與點擊等效）。送出時回傳輸入原值；否則 None。"""
    import streamlit as st

    with st.form(KEY_FORM, border=False):
        raw = st.text_input(W.text("input_label"), key=KEY_INPUT, max_chars=MAX_INPUT_CHARS)
        st.markdown(isin_note_html(), unsafe_allow_html=True)
        submitted = st.form_submit_button(W.text("submit_label"))
    return raw if submitted else None


def render_card(view: FundLookupView, *, fake: bool) -> None:
    import streamlit as st

    st.markdown(lookup_card_html(view, fake=fake), unsafe_allow_html=True)
