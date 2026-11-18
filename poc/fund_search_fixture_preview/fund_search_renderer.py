# -*- coding: utf-8 -*-
"""🔍 找一檔基金／依條件篩選｜隔離式 FAKE Preview 的 renderer（不取數、不連線、不讀憑證、不寫任何東西）。

- HTML 組裝是純函式（可在沒有 Streamlit 的環境單測）；`streamlit` 只在函式內 import。
- 使用者輸入（輸入原值）一律 `escape` 後才進 HTML（含 `$`，避免 Streamlit 的數學語法吃掉）；本檔不硬寫任何中文字樣，字樣取 `fund_search_wording`。
- 色與尺寸一律經 `ui_v3.design.theme` 取 token。
- 版面（單欄、手機優先）：上區「找一檔基金」→ 分隔 →「依條件篩選」EXP-0 → EXP-1 → EXP-2 → EXP-7。
"""
from __future__ import annotations

from html import escape
from typing import Optional

import fund_search_logic as L
import fund_search_wording as W
from ui_v3.design import theme
from ui_v3.viewmodels import exp_counts

KEY_INPUT = "fs_query_input"
KEY_QUERY = "fs_last_query"
KEY_FORM = "fs_lookup_form"
KEY_COND = "fs_cond_{n}"
MAX_INPUT_CHARS = 100


def safe(value: object) -> str:
    """使用者可控字串 → HTML 安全文字（escape；另把 `$`、反斜線與換行轉成字元參照，避免 Streamlit markdown 的數學／跳脫語法介入）。"""
    return (escape(str(value), quote=True).replace("$", "&#36;").replace("\\", "&#92;")
            .replace("\n", "&#10;").replace("\r", "&#13;"))


def _css() -> str:
    gutter, page, section = theme.v("gutter.mobile"), theme.v("type.page"), theme.v("type.section")
    caption, body = theme.v("type.caption"), theme.v("type.body")
    text2, border, space = theme.v("color.text.secondary"), theme.v("color.card.border"), theme.v("space.2")
    radius = theme.v("radius.card")
    grey = theme.m("color.tone.grey")
    return f"""
<style>
{theme.app_css()}
.block-container,.stMainBlockContainer{{padding-top:3.4rem !important}}
.block-container{{max-width:1100px;padding-left:{gutter};padding-right:{gutter};padding-top:3.4rem}}
h1{{font-size:{page} !important;padding:.2rem 0 !important}}
.uv3-pending{{border-bottom:1px dashed {border}}}
.uv3-st{{white-space:normal}}
.uv3-st-red{{font-weight:700}}
.uv3-row{{margin:{theme.v("space.1")} 0;line-height:1.55;overflow-wrap:anywhere}}
.uv3-label{{font-size:{caption};color:{text2};margin-right:6px}}
.uv3-note{{font-size:{caption};color:{text2};line-height:1.5;margin:.15rem 0;overflow-wrap:anywhere}}
{theme.card_css(".uv3-card")}
.fs-title{{margin:0 0 4px 0;font-size:{body};font-weight:700}}
.fs-h2{{margin:{space} 0;font-size:{section};font-weight:700;line-height:1.4}}
.fs-divider{{border-top:2px solid {border};margin:{theme.v("space.4")} 0 {space} 0;padding-top:{space}}}
.fs-tag{{display:inline-block;box-sizing:border-box;max-width:100%;border:1px solid {grey['border']};background:{grey['background']};color:{grey['text']};border-radius:{radius};padding:2px 8px;font-size:{caption};margin-bottom:{theme.v("space.1")}}}
.fs-notice{{box-sizing:border-box;border:1px solid {border};border-radius:{radius};padding:10px 12px;margin-bottom:{space};line-height:1.55;overflow-wrap:anywhere}}
.fs-details{{box-sizing:border-box;margin:0 0 {space} 0;border:1px solid {border};border-radius:{radius};padding:0 12px}}
.fs-details > summary{{display:flex;align-items:center;min-height:48px;cursor:pointer;font-size:{body};font-weight:700;overflow-wrap:anywhere}}
.fs-details[open] > summary{{border-bottom:1px solid {border}}}
.fs-fund{{box-sizing:border-box;border:1px solid {border};border-radius:{radius};padding:10px 12px;margin-bottom:{space}}}
.fs-cells{{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,150px),1fr));gap:2px {space}}}
.fs-cell{{min-width:0;line-height:1.55;overflow-wrap:anywhere}}
.fs-stats{{display:flex;flex-wrap:wrap;gap:4px 16px}}
.fs-note-box{{margin:{space} 0;padding:0}}
/* 選股池為空（0 檔）的結果卡＝虛線框＋灰底（不單獨靠它們傳達狀態：卡內另有符號＋文字標記 data-marker="pool-empty"）；整檔無法判定的列＝虛線框（列內另有『⬜ 無法判定』符號＋字樣）。
   DEC-2026-11-17-03：虛線邊框對比 ≥3:1（實測見 README 與瀏覽器守衛）；空池卡灰底上原 card.border 只有約 2.8:1，改用既有 token color.text.secondary（不新增色票）。有基金但沒有符合者另用實線（見 data-pool-size） */
.uv3-card[data-pool-size="0"]{{border-style:dashed;background:{grey['background']}}}
.uv3-card[data-pool-size="0"]{{border-color:{text2}}}
.fs-fund[data-row-state="undetermined"]{{border-style:dashed}}
[data-testid="stCheckbox"]{{margin-bottom:-.5rem}}
/* 原生控制項的觸控目標 ≥48px（輸入框、查詢鈕、條件勾選）；harness 的 selectbox 不在此列 */
[data-testid="stTextInputRootElement"]{{min-height:48px;box-sizing:border-box}}
[data-testid="stTextInput"] input{{min-height:48px;box-sizing:border-box}}
[data-testid="stFormSubmitButton"] button{{min-height:48px;min-width:48px}}
[data-testid="stCheckbox"] label{{min-height:48px;align-items:center}}
[data-testid="stForm"]{{padding:0}}
/* Streamlit 在表單輸入框內自帶「Press Enter to submit form」與字數計數，會蓋住長輸入；Enter 照常提交，只隱藏這行提示 */
[data-testid="InputInstructions"]{{display:none}}
</style>
"""


CSS = _css()


# ───────────────────────────── 上區：找一檔基金 ─────────────────────────────

def isin_note_html() -> str:
    """輸入框正下方常駐一行、無狀態符號的 ISIN 未啟用說明。"""
    return f'<div class="uv3-note" data-block="isin-note">{W.pending("isin_note")}</div>'


def _row(label_key: str, value_html: str, name: str) -> str:
    return f'<div class="uv3-row" data-row="{escape(name)}"><span class="uv3-label">{W.pending(label_key)}</span>{value_html}</div>'


def isin_result_html() -> str:
    """ISIN 形的輸入：只顯示未啟用說明（不出結果卡、不解析、不取數、不回顯輸入）。"""
    return (f'<div class="fs-notice" data-block="isin-notice" role="status">{W.pending("isin_inactive_result")}'
            f'<div class="uv3-note">{W.pending("isin_inactive_detail")}</div></div>')


# 配息方式候選值 → 字樣鍵（DEC-2026-11-18-01）。其他值一律視為錯誤，不猜。
DIVIDEND_MODE_KEYS = {"distributing": "div_mode_distributing", "accumulating": "div_mode_accumulating"}


def lookup_idle_html() -> str:
    """查詢前（尚未送出）：只顯示『尚未查詢』，沒有任何欄位列。"""
    return f'<div class="uv3-card" data-block="lookup-idle"><div class="uv3-row" data-row="idle">{W.pending("not_queried")}</div></div>'


def lookup_card_html(result: L.LookupResult, found_name: str, dividend_mode: Optional[str] = None) -> str:
    """單檔查詢結果卡。`found_name` 是 fixture 給的 FAKE 名稱（只有 `found` 才會顯示）。
    結果欄位只有五個（DEC-2026-11-18-01）：輸入代碼、基金名稱、配息方式、成立日期、經理費率；其他欄位一律不畫。
    `dividend_mode`：None（缺值）或 `DIVIDEND_MODE_KEYS` 的鍵（配息型／累積型候選）；只有 `found` 才使用，其他結果一律缺值。"""
    if not isinstance(result, L.LookupResult):
        raise TypeError("result must be a LookupResult")
    if dividend_mode is not None and dividend_mode not in DIVIDEND_MODE_KEYS:
        raise ValueError(f"未知的配息方式候選值 {dividend_mode!r}")
    out = result.outcome
    if out == L.OUT_ISIN:
        raise ValueError("ISIN 形的輸入不出結果卡；請用 isin_result_html()")
    if out == L.OUT_FOUND:
        status = W.pending("result_found")
    elif out == L.OUT_INSUFFICIENT:
        status = W.plain("insufficient")
    elif out == L.OUT_FAILED:
        status = (W.status("fetch_failed") + f'<div class="uv3-note">{W.pending("fail_impact")}</div>'
                  f'<div class="uv3-note">{W.pending("fail_not_identity")}</div>')
    elif out == L.OUT_UNRECOGNIZED:
        status = W.undetermined() + W.pending("suffix_unrecognized")
    elif out == L.OUT_NO_FIXTURE:
        status = W.undetermined() + W.pending("suffix_no_fixture")
    else:
        raise ValueError(f"未知的查詢結果種類 {out!r}")
    shown_input = safe(result.raw) if result.raw.strip() else W.missing_cell()
    # 狀態訊息列不是欄位（沒有標籤）；它只陳述這次查詢的結果種類
    rows = [
        f'<div class="uv3-row" data-row="result">{status}</div>',
        _row("row_input_code", f'<span data-value="input-code">{shown_input}</span>', "input-code"),
    ]
    if out in (L.OUT_FOUND, L.OUT_INSUFFICIENT):
        found = out == L.OUT_FOUND
        name_html = safe(found_name) if found else W.missing_cell()
        mode_html = W.pending(DIVIDEND_MODE_KEYS[dividend_mode]) if found and dividend_mode is not None else W.missing_cell()
        rows += [
            _row("row_name", name_html, "name"),
            _row("row_dividend_mode", mode_html, "dividend-mode"),
            _row("row_inception", W.missing_cell(), "inception"),
            _row("row_mgmt_fee", W.missing_cell(), "mgmt-fee"),
        ]
    rows.append(f'<div class="uv3-note" data-note="single">{W.pending("single_note")}</div>')
    return (f'<div class="uv3-card" data-block="lookup-result" data-outcome="{escape(out)}">'
            f'<span class="fs-tag" data-tag="fake">{W.pending("fake_tag")}</span>{"".join(rows)}</div>')


def basic_info_details_html() -> str:
    """預設收合、不巢狀的單一 `<details>`：只放限制說明；不含任何欄位列（來源／備援來源／資料日已於 DEC-2026-11-18-01 移除）。"""
    body = f'<div class="uv3-note" data-note="limits">{W.pending("limits_note")}</div>'
    return (f'<details class="fs-details" data-block="basic-info"><summary data-summary="basic-info">'
            f'{W.pending("details_title")}</summary>{body}</details>')


# ───────────────────────────── 下區：依條件篩選 ─────────────────────────────

def divider_html() -> str:
    return (f'<div class="fs-divider" data-block="exp-divider" role="separator"></div>'
            f'<div class="fs-h2" role="heading" aria-level="2" data-block="exp-title">{W.pending("section_exp_title")}</div>')


def _title(key: str) -> str:
    """卡片標題。刻意不用 h1～h6（Streamlit 會替它們自動加錨點連結）。"""
    return f'<div class="fs-title" role="heading" aria-level="3">{W.pending(key)}</div>'


def _failed_block(block: str, title_key: str) -> str:
    return (f'<div class="uv3-card" data-block="{escape(block)}" data-state="failed">{_title(title_key)}'
            f'<div class="uv3-row">{W.status("fetch_failed")}</div>'
            f'<div class="uv3-note">{W.pending("exp_fail_impact")}</div></div>')


def _pool_marker(view: Optional[L.FilterView]) -> str:
    """選股池為空（套用前 0 檔）時，在結果卡標題下加一列非顏色標記（符號＋短語）；有基金或沒有條件（無軌跡）時不加。"""
    if view is not None and view.trace and int(view.trace[0].before) == 0:
        return f'<div class="uv3-row" data-marker="pool-empty">{W.pending("pool_empty_marker")}</div>'
    return ""


def _pool_attr(view: Optional[L.FilterView]) -> str:
    return f' data-pool-size="{int(view.trace[0].before)}"' if view is not None and view.trace else ""


def exp0_html(view: Optional[L.FilterView], failed: bool) -> str:
    """EXP-0：文案一律取 `exp_counts` 的結論列。來源失敗 → 失敗字樣，不展示 N／M。"""
    if failed:
        return _failed_block("exp0", "exp0_title")
    if view is None:
        raise ValueError("view 不得為 None（非失敗情境）")
    c = view.conclusion
    stats = ""
    if c.counts_shown:
        stats = (f'<div class="fs-stats"><div class="uv3-row" data-row="matched"><span class="uv3-label">{W.pending("col_matched")}</span>'
                 f'<span data-value="matched">{int(c.matched)}</span></div>'
                 f'<div class="uv3-row" data-row="undetermined"><span class="uv3-label">{W.pending("col_undetermined")}</span>'
                 f'<span data-value="undetermined">{int(c.undetermined)}</span></div></div>')
    shown = "yes" if c.counts_shown else "no"
    pool = _pool_attr(view)   # 套用前的池大小：0＝選股池為空，≠ 有基金但零符合
    return (f'<div class="uv3-card" data-block="exp0" data-state="ok" data-conditions="{len(view.conditions)}" data-counts-shown="{shown}"{pool}'
            + (f' data-matched="{int(c.matched)}" data-undetermined="{int(c.undetermined)}"' if c.counts_shown else "")
            + f'>{_title("exp0_title")}{_pool_marker(view)}<div class="uv3-row" data-row="conclusion">{escape(c.text)}</div>{stats}</div>')


def exp1_head_html() -> str:
    return (f'<div class="uv3-card" data-block="exp1">{_title("exp1_title")}'
            f'<div class="uv3-note" data-note="session-only">{W.pending("exp1_note")}</div></div>')


_COL_KEYS = (("code", "col_code"), ("name", "col_name"), ("ccy", "col_ccy"), ("nav_date", "col_nav_date"), ("nav", "col_nav"), ("div", "col_div"))


def exp2_html(view: Optional[L.FilterView], failed: bool) -> str:
    """EXP-2：一列一檔（卡片，不橫向捲動）；列數 = N＋M；無法判定的列標規則表的『⬜ 無法判定』；缺值格是規則表缺值字樣，不是 0。"""
    if failed:
        return _failed_block("exp2", "exp2_title")
    if view is None:
        raise ValueError("view 不得為 None（非失敗情境）")
    if not view.conclusion.counts_shown:
        body = f'<div class="uv3-row" data-row="empty">{escape(exp_counts.TEXT_NO_CONDITION)}</div>'
        return f'<div class="uv3-card" data-block="exp2" data-state="no-conditions" data-rows="0"{_pool_attr(view)}>{_title("exp2_title")}{body}</div>'
    n, m = int(view.conclusion.matched), int(view.conclusion.undetermined)
    exp_counts.verify_exp2_row_count(len(view.rows), n, m)
    if not view.rows:
        body = f'<div class="uv3-row" data-row="empty">{escape(exp_counts.TEXT_NO_MATCH)}</div>'
        return f'<div class="uv3-card" data-block="exp2" data-state="empty" data-rows="0"{_pool_attr(view)}>{_title("exp2_title")}{_pool_marker(view)}{body}</div>'
    items = []
    for r in view.rows:
        tag = ""
        if r.state == L.UNDET:
            tag = f'<div class="uv3-row" data-row="undetermined">{W.undetermined()}{W.pending("row_undetermined_suffix")}</div>'
        cells = "".join(
            f'<div class="fs-cell" data-col="{escape(col)}"><span class="uv3-label">{W.pending(label)}</span>'
            + (safe(r.cell(col)) if r.cell(col) is not None else W.missing_cell()) + "</div>"
            for col, label in _COL_KEYS)
        items.append(f'<div class="fs-fund" data-fund="{escape(r.code)}" data-row-state="{escape(r.state)}">{tag}<div class="fs-cells">{cells}</div></div>')
    return (f'<div class="uv3-card" data-block="exp2" data-state="rows" data-rows="{len(view.rows)}"{_pool_attr(view)}>{_title("exp2_title")}{_pool_marker(view)}{"".join(items)}</div>')


def exp7_html(view: Optional[L.FilterView], failed: bool) -> str:
    """EXP-7：逐條件的 N／M 軌跡；最後一列必須與 EXP-0 一致（由 `build_filter_view` 驗證，這裡再驗一次）。"""
    if failed:
        return _failed_block("exp7", "exp7_title")
    if view is None:
        raise ValueError("view 不得為 None（非失敗情境）")
    if not view.conclusion.counts_shown:
        body = f'<div class="uv3-row" data-row="empty">{escape(exp_counts.TEXT_NO_CONDITION)}</div>'
        return f'<div class="uv3-card" data-block="exp7" data-state="no-conditions" data-rows="0"{_pool_attr(view)}>{_title("exp7_title")}{body}</div>'
    exp_counts.verify_exp7_last_row([(t.matched, t.undetermined) for t in view.trace], view.conclusion.matched, view.conclusion.undetermined)
    items = []
    for t in view.trace:
        items.append(
            f'<div class="fs-fund" data-trace="{t.index}"><div class="fs-cells">'
            f'<div class="fs-cell" data-col="cond"><span class="uv3-label">{W.pending("col_cond")}</span>{W.pending("cond_label", n=t.index)}</div>'
            f'<div class="fs-cell" data-col="before"><span class="uv3-label">{W.pending("col_before")}</span>{int(t.before)}</div>'
            f'<div class="fs-cell" data-col="matched"><span class="uv3-label">{W.pending("col_matched")}</span>{int(t.matched)}</div>'
            f'<div class="fs-cell" data-col="undetermined"><span class="uv3-label">{W.pending("col_undetermined")}</span>{int(t.undetermined)}</div>'
            f'</div></div>')
    return f'<div class="uv3-card" data-block="exp7" data-state="rows" data-rows="{len(view.trace)}"{_pool_attr(view)}>{_title("exp7_title")}{_pool_marker(view)}{"".join(items)}</div>'


# ───────────────────────────── Streamlit 部分（widgets 與 session_state） ─────────────────────────────

def render_css() -> None:
    import streamlit as st

    st.markdown(CSS, unsafe_allow_html=True)


def render_lookup(fixtures: dict, found_name: str, dividend_modes: Optional[dict] = None) -> None:
    """上區：標題 → 單一輸入框 → 常駐 ISIN 說明 → 查詢鈕（st.form，Enter 與點擊等效）→ 結果卡（查詢前只顯示『尚未查詢』）→ 預設收合的限制說明。"""
    import streamlit as st

    st.title(W.text("page_title"), anchor=False)
    with st.form(KEY_FORM, border=False):
        raw = st.text_input(W.text("input_label"), key=KEY_INPUT, max_chars=MAX_INPUT_CHARS)
        st.markdown(isin_note_html(), unsafe_allow_html=True)
        submitted = st.form_submit_button(W.text("submit_label"))
    if submitted:
        st.session_state[KEY_QUERY] = raw
    query = st.session_state.get(KEY_QUERY)
    if query is None:
        html = lookup_idle_html()
    else:
        result = L.classify_lookup(query, fixtures)
        mode = (dividend_modes or {}).get(query.strip().upper()) if result.outcome == L.OUT_FOUND else None
        html = isin_result_html() if result.outcome == L.OUT_ISIN else lookup_card_html(result, found_name, mode)
    st.markdown(html, unsafe_allow_html=True)
    st.markdown(basic_info_details_html(), unsafe_allow_html=True)


def active_conditions(count: int) -> tuple:
    """目前勾選的條件序號（依畫面順序；未勾選 → 空）。只讀本次 session_state，不寫任何持久層。"""
    import streamlit as st

    return tuple(n for n in range(1, count + 1) if st.session_state.get(KEY_COND.format(n=n), False) is True)


def render_exp(scenario: dict, condition_count: int) -> None:
    """下區：EXP-0 → EXP-1（本次瀏覽暫時條件）→ EXP-2 → EXP-7。"""
    import streamlit as st

    failed = bool(scenario["failed"])
    active = active_conditions(condition_count)
    view = None if failed else L.build_filter_view(scenario["pool"], active, condition_count)
    st.markdown(exp0_html(view, failed), unsafe_allow_html=True)
    st.markdown(exp1_head_html(), unsafe_allow_html=True)
    for n in range(1, condition_count + 1):
        st.checkbox(W.text("cond_label", n=n), key=KEY_COND.format(n=n))
    st.markdown(exp2_html(view, failed), unsafe_allow_html=True)
    st.markdown(exp7_html(view, failed), unsafe_allow_html=True)
