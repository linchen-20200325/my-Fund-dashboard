# -*- coding: utf-8 -*-
"""單檔基金查詢呈現元件｜renderer（純呈現；不取數、不連線、不讀憑證、不寫任何東西）。

授權：`DEC-2026-11-18-04`（要點轉述，來源待核，NOT VERIFIED）。本檔是既有隔離預覽 renderer 的**複本**（Gate-M M-copy 第一段，客戶 2026-11-21 核准；#1296 comment 7063845090）：**尚未掛載**——不是 🔍 頁面、不掛 registry／`app_preview`／導覽、不接真實來源。

- 輸入是**注入式 ViewModel**（`ui_v3.viewmodels.fund_lookup.FundLookupView`）；本檔**不 import adapter、services、repositories、infra**，
  也不 import 任何網路或檔案相關模組。ViewModel 由 harness 經 adapter 產生，再交給本檔。
- HTML 組裝是純函式（可在沒有 Streamlit 的環境單測）；`streamlit` 只在 `render_*` 函式內 import。
- 使用者可控字串（`input_code`、`fund_name`、日期）一律 `safe()` 後才進 HTML（含 `$`，避免 Streamlit 的數學語法吃掉）。
- 顯示欄位只有五個（輸入代碼、基金名稱、配息方式、成立日期、經理費率），依這個順序；**沒有任何其他欄位**（幣別、淨值、報酬、績效、取得時間、供應者…）。
- 每個非 `NOT_QUERIED` 狀態都有獨立文案，**沒有任何一個說「基金不存在／查無」**；取數失敗、頁面無法確認、入口攔截彼此不混用。
- 缺值不寫成 0、「無」、「不配息」；`MISSING` 與 `CONFLICT` 各有獨立文案與 DOM 標記（`data-field-status`）。
- 色與尺寸一律經 `ui_v3.design.theme` 取 token，不寫死色碼。字樣取 `ui_v3.viewmodels.exp_lookup_wording`（新字樣皆 PendingWording）。
"""
from __future__ import annotations

from html import escape
from typing import Optional

from ui_v3.design import theme
from ui_v3.viewmodels import exp_lookup_wording as W
from ui_v3.viewmodels.exp_nav import DividendStatus, ExpNavView, MetricKind, MetricView, NavDisplay
from ui_v3.viewmodels.fund_lookup import FieldStatus, FieldView, FundLookupView, LookupState

KEY_INPUT = "fl_query_input"
KEY_VIEW = "fl_last_view"
KEY_NAV = "fl_last_nav"
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
.fl-page-fake{{border:1px dashed {border};border-radius:{radius};padding:{space1} {space2};margin:0 0 {space1} 0;font-weight:700;color:{text1}}}
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
.fl-sect{{margin:{space2} 0 0 0;padding-top:{space1};border-top:1px solid {border};font-size:{caption};color:{text2}}}
.fl-judge{{display:block;box-sizing:border-box;max-width:100%;margin:{space1} 0;border:1px solid {border};border-radius:{radius};padding:{space1} {space2};overflow-wrap:anywhere}}
.fl-judge .fl-jk{{display:block;font-size:{caption};color:{text2}}}
.fl-judge[data-judgement="fail-evidenced"]{{border-color:{red['border']};background:{red['background']};color:{red['text']}}}
.fl-judge[data-judgement="fail-evidenced"] .fl-jk{{color:{red['text']}}}
.fl-judge[data-judgement="undetermined"]{{border-color:{grey['border']};background:{grey['background']};color:{grey['text']}}}
.fl-judge[data-judgement="fact-no-dividend"]{{border-style:dashed;background:transparent}}
.fl-withheld{{display:block;box-sizing:border-box;margin:{space1} 0;border:1px solid {grey['border']};background:{grey['background']};color:{grey['text']};border-radius:{radius};padding:{space1} {space2};font-weight:700;overflow-wrap:anywhere}}
.fl-fold{{border-top:1px solid {border};padding-top:{space1};margin-top:{space1}}}
.fl-fold summary{{cursor:pointer;min-height:32px}}
.fl-slot{{box-sizing:border-box;max-width:100%;border:1px dashed {border};border-radius:{radius};padding:{space1} {space2};margin-top:{space2};color:{text2};font-size:{caption}}}
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


def idle_html(*, fake: bool = False) -> str:
    """查詢前（尚未送出）：整張卡只顯示『尚未查詢』，沒有任何欄位列。`fake=True` 時卡首出『FAKE 模擬』標籤（卡級 FAKE 恆顯）。"""
    tag = f'<span class="fl-tag" data-tag="fake">{W.pending("fake_tag")}</span>' if fake else ""
    return (f'<div class="uv3-card fl-card" data-block="lookup-idle" data-state="idle" role="region" aria-labelledby="{ID_STATUS}">'
            f'{tag}<div class="fl-status" id="{ID_STATUS}" data-row="idle" role="status">{W.pending("not_queried")}</div></div>')


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


_JUDGE_ATTR = {MetricKind.PASS_EVIDENCED: "pass-evidenced", MetricKind.FAIL_EVIDENCED: "fail-evidenced",
               MetricKind.FACT_NO_DIVIDEND: "fact-no-dividend", MetricKind.UNDETERMINED: "undetermined"}
_MISSING_BY_REASON = {"input_conflict": "miss_nav", "nav_not_admitted": "miss_nav", "dividend_not_obtained": "miss_dividend", "history_short": "miss_return_3y",
                      "rights_unverified": "miss_rights", "identity_unverified": "miss_class"}


def _nav_row(name: str, label_key: str, value_html: str) -> str:
    return (f'<div class="fl-row" data-row="{escape(name)}"><dt class="uv3-label">{W.pending(label_key)}</dt><dd>{value_html}</dd></div>')


def nav_block_html(nav: ExpNavView) -> str:
    """淨值區（sibling；純函式）。`nav_value` 只在 VERIFIED 才有（view model 強制）；時間欄位各列各自標示、不互相代填。"""
    n, j = nav.nav, nav.judgement
    rows = []
    status_html = ""
    if n.display is NavDisplay.VERIFIED:
        rows.append(_nav_row("nav-value", "nav_row_value", f'<span data-value="nav-value">{safe(n.nav_value)}</span> {safe(n.ccy)}'))
        rows.append(_nav_row("nav-date", "nav_row_date", f'<span data-value="nav-date">{safe(n.nav_date)}</span>'))
    elif n.display is NavDisplay.MISSING:
        status_html = f'<div class="fl-withheld" role="status" data-nav-note="missing">⬜ {W.pending("nav_missing")}</div>'
    else:
        key = "nav_withheld_conflict" if n.display is NavDisplay.WITHHELD_CONFLICT else "nav_withheld_not_admitted"
        status_html = f'<div class="fl-withheld" role="alert" data-nav-note="withheld">⬜ {W.pending(key)}</div>'
        if n.conflicts:
            if n.content_tier == "T1":
                c = n.conflicts[0]
                diag = W.pending("nav_diag_dates", a=c.a_date, b=c.b_date)
            else:
                diag = W.pending("nav_diag_t0")
            rows.append(_nav_row("nav-diag", "nav_diag", diag))
        others = [r for r in n.reason_codes if r != "input_conflict"]
        if others:
            rows.append(_nav_row("nav-reasons", "nav_row_reasons", "、".join(W.pending("nr_" + r) for r in others)))
    if n.source_label is not None:
        rows.append(_nav_row("nav-source", "nav_row_source", safe(n.source_label)))
    if n.cache_updated_at is not None:
        rows.append(_nav_row("nav-cache-at", "nav_row_cache", safe(n.cache_updated_at)))
    supplier = safe(n.supplier_fetched_at) if n.supplier_fetched_at else f'<span class="fl-value-missing" data-kind="unknown">{W.pending("nav_supplier_unknown")}</span>'
    if n.display is not NavDisplay.MISSING:
        rows.append(_nav_row("nav-supplier-at", "nav_row_supplier", supplier))
    if n.ccy_declared is not None and n.display is not NavDisplay.VERIFIED:
        rows.append(_nav_row("ccy-declared", "nav_row_ccy_declared", safe(n.ccy_declared)))
    if n.ccy_declared_at is not None:
        rows.append(_nav_row("ccy-declared-at", "nav_row_ccy_at", safe(n.ccy_declared_at)))
    div_key = {DividendStatus.MISSING: "nav_div_missing", DividendStatus.CONFIRMED_NONE: "nav_div_none", DividendStatus.PRESENT: "nav_div_present"}[j.dividend_status]
    rows.append(_nav_row("dividend-status", "nav_row_dividend", f'<span data-dividend="{j.dividend_status.value}">{"⬜ " if j.dividend_status is DividendStatus.MISSING else ""}{W.pending(div_key)}</span>'))
    note = f'<div class="uv3-note" data-note="time-differ">{W.pending("nav_time_differ")}</div>' if n.time_sources_differ else ""
    return (f'<section data-block="nav" data-nav-display="{n.display.value}"><div class="fl-sect">{W.pending("nav_section")}</div>'
            f'{status_html}<dl class="fl-list">{"".join(rows)}</dl>{note}</section>')


def _metric_html(metric: MetricView, row_name: str, label_key: str, pass_key: str, fail_key: str) -> str:
    """一列判定。符號只由 `kind` 決定：❌＝有證據的未通過、⬜＝無法判定、無配息事實＝無判定符號。renderer 不算、不改寫數值字串。"""
    attr = _JUDGE_ATTR[metric.kind]
    label = f'<span class="fl-jk">{W.pending(label_key)}</span>'
    ev = "；".join(f"{escape(a)} {safe(b)}" for a, b in metric.evidence)
    if metric.kind is MetricKind.PASS_EVIDENCED:
        body = f'✅ {W.pending(pass_key)}' + (f"：{ev}" if ev else "")
    elif metric.kind is MetricKind.FAIL_EVIDENCED:
        body = f'❌ {W.pending(fail_key)}' + (f"：{ev}" if ev else "")
    elif metric.kind is MetricKind.FACT_NO_DIVIDEND:
        body = f'{W.pending("nav_div_none")}；{W.pending("judge_eating_na")}'
    else:
        body = f'{W.status("undetermined")} {W.pending("mr_" + metric.reason_code)}' + (f"（{ev}）" if ev else "")
    return f'<span class="fl-judge" data-judgement="{attr}" data-metric="{escape(row_name)}">{label}{body}</span>'


def judgement_block_html(nav: ExpNavView) -> str:
    """輔助判定區：兩項各自獨立；層 F（淨值扣下）時兩項由 view model 強制為「無法判定」。"""
    j = nav.judgement
    return (f'<section data-block="judgement"><div class="fl-sect">{W.pending("judge_section")}</div>'
            f'{_metric_html(j.three_three_three, "333", "judge_row_333", "judge_pass_333", "judge_fail_333")}'
            f'{_metric_html(j.eating_principal, "eating", "judge_row_eating", "judge_pass_eating", "judge_fail_eating")}</section>')


def folds_html(nav: ExpNavView) -> str:
    """「為什麼／來源／限制」與「尚未取得」（預設收合；來源、日期已在卡面常駐，不收進這裡）。AI 使用權未核證只出現在這裡一行，不改主畫面。"""
    limit = W.pending("limit_verified" if nav.nav.display is NavDisplay.VERIFIED else "limit_withheld")
    ai = "" if nav.ai_usable else f'<div class="uv3-note" data-note="ai-unusable">{W.pending("limit_ai")}</div>'
    miss = []
    if nav.nav.display is not NavDisplay.VERIFIED:
        miss.append("miss_nav")
    if nav.judgement.dividend_status is DividendStatus.MISSING:
        miss.append("miss_dividend")
    for m in (nav.judgement.three_three_three, nav.judgement.eating_principal):
        key = _MISSING_BY_REASON.get(m.reason_code or "")
        if key:
            miss.append(key)
    for r in nav.nav.reason_codes:
        key = {"identity_unverified": "miss_class", "class_unverified": "miss_class", "rights_unverified": "miss_rights"}.get(r)
        if key:
            miss.append(key)
    seen = []
    for k in miss:
        if k not in seen:
            seen.append(k)
    miss_html = "、".join(W.pending(k) for k in seen) if seen else W.pending("fold_none")
    return (f'<details class="fl-fold" data-fold="why"><summary>{W.pending("fold_why")}</summary><div class="uv3-note">{limit}</div>{ai}</details>'
            f'<details class="fl-fold" data-fold="missing"><summary>{W.pending("fold_missing")}</summary><div class="uv3-note">{miss_html}</div></details>')


def onebrain_slot_html() -> str:
    """OneBrain 解釋槽：恆「未啟用」。不是 AI 結論、不用 ActionSlot、不依任何權利旗標改變。"""
    return (f'<div class="fl-slot" data-block="onebrain-slot" data-state="disabled" role="note"><b>{W.pending("slot_title")}</b><br>{W.pending("slot_body")}</div>')


def lookup_card_html(view: FundLookupView, *, fake: bool, nav: Optional[ExpNavView] = None) -> str:
    """依 ViewModel 組結果卡。`fake=True` 時卡首先出一個『FAKE 模擬』標籤（必在任何欄位列之前）。`NOT_QUERIED` → 『尚未查詢』卡。"""
    if not isinstance(view, FundLookupView):
        raise TypeError("view must be a FundLookupView")
    if view.state is LookupState.NOT_QUERIED:
        return idle_html(fake=fake)
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
    if nav is not None and view.state is LookupState.RESULT:      # sibling：五欄之後、單檔說明之前；其他狀態與無 sibling 時輸出與原來逐字相同
        if not isinstance(nav, ExpNavView):
            raise TypeError("nav must be an ExpNavView")
        parts.append(nav_block_html(nav))
        parts.append(judgement_block_html(nav))
        parts.append(folds_html(nav))
    parts.append(f'<div class="uv3-note" data-note="single">{W.pending("single_note")}</div>')
    reason_attr = f' data-reason="{escape(view.reason_code)}"' if view.reason_code else ""
    return (f'<div class="uv3-card fl-card" data-block="lookup-result" data-state="{name}"{reason_attr} role="region" aria-labelledby="{ID_STATUS}">'
            f'{"".join(parts)}</div>')


# ───────────────────────────── Streamlit 部分（widgets 與 session_state） ─────────────────────────────

def page_header_html(codes_hint: str) -> str:
    """頁級 FAKE 標示（每個狀態都在頁頂、永久可見）：標題下一條 FAKE 橫幅＋示範代碼提示。純函式。"""
    return (f'<div class="uv3-note fl-page-fake" data-block="page-fake" role="note">{W.pending("page_fake_banner")}</div>'
            f'<div class="uv3-note" data-note="demo-codes">{W.pending("page_fake_hint", codes=codes_hint)}</div>')


def render_page_header(codes_hint: str) -> None:
    import streamlit as st

    st.title(W.text("page_title"), anchor=False)
    st.markdown(page_header_html(codes_hint), unsafe_allow_html=True)


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


def render_card(view: FundLookupView, *, fake: bool, nav: Optional[ExpNavView] = None) -> None:
    import streamlit as st

    st.markdown(lookup_card_html(view, fake=fake, nav=nav), unsafe_allow_html=True)
    if nav is not None and view.state is LookupState.RESULT:
        st.markdown(onebrain_slot_html(), unsafe_allow_html=True)
