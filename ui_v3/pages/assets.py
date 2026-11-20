# -*- coding: utf-8 -*-
"""💼 我的資產頁的 renderer（隔離式 Preview：A00 來源狀態、A10 降級卡、A20 固定四格、A50 單一容器四欄唯讀持倉、A60 來源與缺項證據）。頁只吃 `AssetsPageModel`，不取數、不計算領域值。

- `streamlit` 只在函式內 import（import `ui_v3` 時不得載入 Streamlit）。HTML 組裝是純函式，可在沒有 Streamlit 的環境單測。
- 字樣：已核准字樣一律取規則表；尚未核准的取 `assets_page.ASSETS_PENDING_WORDING` 與 `assets_preview_wording`，並以 `data-pending-wording`
  標記。**本檔不硬寫任何中文字樣。** 色與尺寸一律經 `design/theme.py` 取 token。
- 畫面字只依「原因鍵」與「來源狀態」決定；**不讀**原因的分類欄位（類別 (a)(b) 由 view model 的順序表達，畫面各一行、不混成一句）。
- 失敗代碼、市值基準被擋的原因碼、內部鍵一律不上畫面。
- 沒有任何金額、百分比、合計、配置比例、風險判定或建議；沒有匯率換算、沒有跨幣別合計（A50 的 fund_code／ccy／units_shares 是原值，不是合計）。
- 不畫「持倉入口」：現階段沒有合法的導向目標（A10 入口的正式目標另經技術 Gate），所以即使 view model 帶有入口也不畫（有測試鎖定）。
- 首屏元素（供瀏覽器守衛點數）：A00 一個、A20 四格各一個；A10 的文字不計（標 `data-first-screen` 的只有這五個）。A50 不標首屏。
- A50（DEC-2026-11-16-01）：**單一** HTML `<details>` 展開容器（零 rerun；逐檔不再展開、不巢狀、不放進任何其他展開容器；A51 不在本批），
  內含逐檔唯讀列，每列四欄 `fund_name`／`fund_code`／`ccy`／`units_shares`。**暫行**：預設收合（DEC 待確認 (c) 未裁）；`units_shares` 以原值字串輸出
  （不做千分位或換算，顯示格式未裁）。缺值／不可用一律 `◇ 資料未備`（走規則表），絕不顯示 0 或空白。`holding_id` 只作身份鍵：不上畫面、不進 DOM（列以 ordinal 做 `data-row`）。
  A50 區沒有合計、換算、金額、占比、報酬、配息、建議。**只有 `model.a50.state == rows` 才畫容器**；`status_only` 只畫一列引用 A00 狀態的文字
  （不畫空表、不畫導向空內容的入口、不寫「持倉 0」）。
- A60（DEC-2026-11-17-01，D1～D8）：A50 之後的**獨立** `<details>`（預設收合、與 A50 並列、不巢狀、不標首屏；不新增 A00 指向入口、不畫 A52）。只呈現「略過分頁數」「略過列數」
  （整數照顯示，0 也顯示 0 但**不得因此宣稱來源完整**；None → 已核准的 `◇ 資料未備`，絕不顯示 0）、一行依來源狀態的暫行說明，以及（不重複的）說明句；(a) 原因不另列。
  說明句只留四類（出處 ChatGPT UI 設計方向 2026-11-17）：讀取失敗、部分略過（須至少一個件數 > 0）、完整但沒有有效持倉列（只在 complete_no_rows 且兩個件數皆為整數 0 才說）、
  其餘（含 complete 有持倉列、未選定來源、blocked 未讀取、證據不足）一律「無法判定」（規則表 `undetermined`）；complete 不得聲稱已完整讀取，也不另創原因句。**不讀**原因的分類欄位；內部問題碼（`problem_codes`）、`cause_key`、失敗代碼、略過的原始字串、網址、試算表 ID、例外
  一律不上畫面。(b)「計算口徑未核准」原因不放進 A60（遇到即 ValueError）。新增字樣全是 `PendingWording`。
- A30、A40、A51、A52 不在這一批，不畫。
"""
from __future__ import annotations

from html import escape

from shared.ui_semantics import rules
from ui_v3.design import theme
from ui_v3.shell import nav
from ui_v3.shell.registry import IA_PAGES
from ui_v3.viewmodels import assets_page as vm
from ui_v3.viewmodels import assets_preview_wording as AW

PAGE_TITLE = next(p.title for p in IA_PAGES if p.slug == "ast")


def _css() -> str:
    gutter, page, section = theme.v("gutter.mobile"), theme.v("type.page"), theme.v("type.section")
    caption, body = theme.v("type.caption"), theme.v("type.body")
    text2, border, space = theme.v("color.text.secondary"), theme.v("color.card.border"), theme.v("space.2")
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
.uv3-card-title{{margin:0 0 4px 0;padding:.5rem 0 1rem 0;font-size:{body};font-weight:600;line-height:1.2}}
.uv3-a20{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:{space};margin-bottom:{space}}}
.uv3-a20 > .uv3-card{{margin-bottom:0;min-width:0}}
.uv3-a50,.uv3-a60{{margin-bottom:{space}}}
.uv3-a50 > summary,.uv3-a60 > summary{{box-sizing:border-box;min-height:{nav.TOUCH_MIN_PX}px;padding:12px 0;cursor:pointer;font-size:{body};font-weight:600}}
.uv3-a50-body{{max-height:70vh;overflow-y:auto;overflow-x:hidden;overscroll-behavior:contain}}
.uv3-a60-body{{max-height:70vh;overflow-y:auto;overflow-x:hidden;overscroll-behavior:contain}}
.uv3-a50-row{{border-top:1px solid {border};padding:{theme.v("space.1")} 0}}
.uv3-a50-field{{margin:2px 0;line-height:1.5;overflow-wrap:anywhere;word-break:break-word}}
@media (min-width:{nav.MOBILE_MAX_PX + 1}px){{
  .uv3-a20{{grid-template-columns:repeat(4,minmax(0,1fr))}}
}}
</style>
"""


# 頁面 CSS（只在 `render()` 注入）。
CSS = _css()


# ───────────────────────────── 小工具（純字串） ─────────────────────────────

def _pending(key: str) -> str:
    """狀態與原因句的暫時字樣（`assets_page.ASSETS_PENDING_WORDING`）。"""
    item = vm.pending_wording(key)
    return f'<span class="uv3-pending" data-pending-wording="{escape(key)}">{escape(item.text)}</span>'


def _label(key: str) -> str:
    """版面標籤的暫行字樣（`assets_preview_wording`）。"""
    item = AW.preview_wording(key)
    return f'<span class="uv3-pending" data-pending-wording="{escape(key)}">{escape(item.text)}</span>'


def _status(key: str) -> str:
    """規則表的已核准狀態（符號＋字樣，純文字、不是 chip 形式元素）。"""
    entry = rules.entry(key)
    return f'<span class="uv3-st uv3-st-{entry.tone}" data-status-key="{escape(key)}">{escape(entry.wording)}</span>'


def _missing() -> str:
    return _status("missing")


# ───────────────────────────── A00 ─────────────────────────────

def source_state_html(source_state: str) -> str:
    """來源狀態 → A00 的狀態文字。只依來源狀態分派；失敗代碼與原因碼不上畫面。"""
    if source_state == vm.SRC_COMPLETE:
        return _pending("a00_complete")
    if source_state == vm.SRC_PARTIAL:
        return _pending("a00_partial")
    if source_state == vm.SRC_NOT_SELECTED:
        return _pending("a00_not_selected")
    if source_state == vm.SRC_COMPLETE_NO_ROWS:
        return _pending("a00_complete") + " " + _pending("a00_complete_no_rows")
    if source_state == vm.SRC_READ_FAILED:
        return _status("fetch_failed")
    if source_state in (vm.SRC_UNDETERMINED, vm.SRC_NOT_READ):   # 未讀取（市值基準被擋）也不得聲稱來源已讀完
        return _status("undetermined")
    raise ValueError(f"unknown source_state {source_state!r}")


def a00_html(a00: vm.A00Status) -> str:
    return (f'<div class="uv3-card" data-block="a00" data-first-screen="a00" data-source-state="{escape(a00.source_state)}">'
            f'<span class="uv3-label">{_label("a00_label")}</span>{source_state_html(a00.source_state)}</div>')


# ───────────────────────────── A10 ─────────────────────────────

def _same_as_source_html(source_state: str) -> str:
    """原因＝引用來源狀態：與 A00 同一句（complete_no_rows 只重複第二句，不重複展開）。"""
    if source_state == vm.SRC_COMPLETE_NO_ROWS:
        return _pending("a00_complete_no_rows")
    if source_state in (vm.SRC_NOT_SELECTED, vm.SRC_READ_FAILED, vm.SRC_UNDETERMINED):
        return source_state_html(source_state)
    raise ValueError(f"source_state {source_state!r} cannot reference its own status as a cause")


def cause_html(cause: vm.CauseFact, source_state: str) -> str:
    """一個缺值原因 → 一句話。只依原因鍵與來源狀態決定，不讀原因的分類欄位。"""
    key = cause.cause_key
    if key == vm.CAUSE_PARTIAL_SOURCE:
        return _pending("cause_partial_source")
    if key == vm.CAUSE_SAME_AS_SOURCE_STATUS:
        return _same_as_source_html(source_state)
    if key == vm.CAUSE_BASIS_NOT_APPROVED_WITH_ROWS:
        return _pending("cause_basis_not_approved_with_rows")
    if key == vm.CAUSE_BASIS_NOT_APPROVED:
        return _pending("cause_basis_not_approved")
    raise ValueError(f"unsupported cause_key {key!r} in A10")


def _basis_html(a10: vm.A10Card) -> str:
    state = a10.basis_state
    if state == "set":
        # 使用者自己設定的原值（使用者資料）；取不到值（例如市值基準被擋、沒有證據）就誠實缺值。
        return escape(a10.basis_value) if a10.basis_value is not None else _missing()
    if state == "unset":
        return _status("user_param_unset")
    if state == "read_failed":
        return _status("fetch_failed")
    return _status("undetermined")   # invalid／broken_row


def _limit_html(code: str) -> str:
    if code == vm.LIMIT_NO_FX_CONVERSION:
        return _pending("limit_no_fx_conversion")
    raise ValueError(f"unknown limit code {code!r}")


def a10_html(a10: vm.A10Card, source_state: str) -> str:
    """降級卡：`◇ 資料未備` 純文字（不是 chip）＋每個原因一行＋基準一列＋限制一列。**不畫入口**；文字不計入首屏元素。"""
    sep = _label("separator")
    rows = "".join(
        f'<div class="uv3-row" data-a10="cause">{_missing()}{sep}{cause_html(c, source_state)}</div>' for c in a10.missing.causes)
    spec = f'<div class="uv3-row" data-a10="spec"><span class="uv3-label">{_label("a10_basis_label")}</span>{_basis_html(a10)}</div>'
    limits = "".join(f'<div class="uv3-row" data-a10="limit">{_limit_html(c)}</div>' for c in a10.limit_codes)
    return (f'<div class="uv3-card" data-block="a10"><div class="uv3-card-title" role="heading" aria-level="4">{_label("a10_title")}</div>'
            f'{rows}{spec}{limits}</div>')   # 刻意不用 h4：Streamlit 會替 markdown 裡的 h1～h6 自動加錨點連結（多出看不見的 Tab 停駐點）；樣式與原 h4 等價


# ───────────────────────────── A20 ─────────────────────────────

def a20_html(a20: vm.A20Summary) -> str:
    """固定四格；本階段沒有任何正式值（公式未核准），每格只有 `◇ 資料未備`，絕不轉 0。"""
    labels = dict(AW.A20_LABEL_KEYS)
    cells = []
    for cell in a20.cells:
        if cell.value is not None:   # 正式值未核准；view model 本來就拒絕，這裡再擋一次，不畫任何數字
            raise ValueError("A20 must not carry a value (formula not approved)")
        cells.append(f'<div class="uv3-card" data-cell="{escape(cell.cell_code)}" data-first-screen="{escape(cell.cell_code)}">'
                     f'<div class="uv3-label">{_label(labels[cell.cell_code])}</div><div class="uv3-row">{_missing()}</div></div>')
    note = f'<div class="uv3-note" data-a20="labels-note">{_label("a20_labels_note")}</div>'
    return f'<div class="uv3-a20" data-block="a20">{"".join(cells)}</div>{note}'


# ───────────────────────────── A50 ─────────────────────────────

def _cell_html(fact: vm.RowFact) -> str:
    """一個欄位事實 → 值的 HTML。present：原值轉字串（不做千分位或換算；空白摺成單一空格，避免空行截斷 HTML 區塊）並 escape；
    missing：已核准的 `◇ 資料未備`（絕不是 0 或空白）。"""
    if fact.state == vm.ROW_STATE_MISSING:
        return _missing()
    return escape(" ".join(str(fact.value).split()))


def a50_row_html(row: vm.HoldingRow) -> str:
    """一列四欄。列以 ordinal 做 `data-row`；`holding_id` 不進 DOM。欄位集合不是 A50 四欄 → ValueError（不猜）。"""
    labels = dict(AW.A50_FIELD_LABEL_KEYS)
    fields = []
    for fact in row.facts:
        if fact.field_code not in labels:
            raise ValueError(f"unsupported A50 field_code {fact.field_code!r}")
        fields.append(f'<div class="uv3-a50-field" data-field="{escape(fact.field_code)}"><span class="uv3-label">{_label(labels[fact.field_code])}</span>'
                      f'{_cell_html(fact)}</div>')
    return f'<div class="uv3-a50-row" data-row="{row.ordinal}">{"".join(fields)}</div>'


def a50_html(a50: vm.A50Section, source_state: str) -> str:
    """A50：有列才畫單一 `<details>`（預設收合，暫行）；`status_only` 只畫一列引用 A00 狀態的文字。**全程不產生 HTML 空行**（空行會截斷 Markdown 的 HTML 區塊）。"""
    if a50.state == vm.A50_STATUS_ONLY:
        return f'<div class="uv3-row" data-a50="status-only"><span class="uv3-label">{_label("a50_title")}</span>{source_state_html(source_state)}</div>'
    rows = "".join(a50_row_html(r) for r in a50.rows)
    note = f'<div class="uv3-note" data-a50="labels-note">{_label("a50_labels_note")}</div>'
    return (f'<details class="uv3-a50" data-block="a50"><summary>{_label("a50_title")}</summary>'
            f'{note}<div class="uv3-a50-body" data-a50="body">{rows}</div></details>')


# ───────────────────────────── A60 ─────────────────────────────

def _a60_count_html(value) -> str:
    """略過件數：整數照顯示（0 也顯示 0）；None（來源沒提供）→ 已核准的 `◇ 資料未備`，絕不顯示 0。"""
    if value is None:
        return _missing()
    if type(value) is not int:
        raise ValueError("A60 counts must be int or None")
    return str(value)


def _a60_effective_state(a60: vm.A60Evidence, source_state: str) -> str:
    """A60 說明列採用的狀態（fail-closed，只留四類說明句）：read_failed／partial／complete_no_rows／undetermined。
    partial 須至少一個件數 > 0；complete_no_rows 須兩個件數皆為整數 0；其餘（complete 有持倉列、未選定來源、未讀取、證據不足、未知）一律 `undetermined`
    （`⬜ 無法判定`）。件數為 0 不能單獨證明來源完整，complete 也不聲稱「已完整讀取」。只看來源狀態與件數，不讀原因的分類欄位。"""
    tabs, rows = a60.skipped_tab_count, a60.skipped_row_count
    both_zero = type(tabs) is int and type(rows) is int and tabs == 0 and rows == 0
    if source_state == vm.SRC_READ_FAILED:
        return "read_failed"
    if source_state == vm.SRC_PARTIAL:
        return "partial" if ((tabs or 0) > 0 or (rows or 0) > 0) else "undetermined"
    if source_state == vm.SRC_COMPLETE_NO_ROWS:
        return "complete_no_rows" if both_zero else "undetermined"
    if source_state in (vm.SRC_COMPLETE, vm.SRC_NOT_SELECTED, vm.SRC_NOT_READ, vm.SRC_UNDETERMINED):
        return "undetermined"
    raise ValueError(f"unknown source_state {source_state!r}")


_A60_STATE_WORDING = {
    "read_failed": "a60_state_read_failed", "partial": "a60_state_partial", "complete_no_rows": "a60_state_complete_no_rows",
}


def _a60_state_html(state: str) -> str:
    return _status("undetermined") if state == "undetermined" else _label(_A60_STATE_WORDING[state])


def _a60_check_causes(causes) -> None:
    """A60 不另畫原因列（「部分略過」說明已由說明列的 partial 句承擔，不重複）；仍只依原因鍵檢查、不讀分類欄位：
    (b) 的原因鍵（計算口徑未核准）或未知鍵遇到即 ValueError，不放進 A60。引用 A00 同一狀態的原因與部分略過原因都不另列（本函式不輸出任何 HTML）。"""
    for cause in causes:
        if cause.cause_key not in (vm.CAUSE_SAME_AS_SOURCE_STATUS, vm.CAUSE_PARTIAL_SOURCE):
            raise ValueError(f"unsupported cause_key {cause.cause_key!r} in A60")


def a60_html(a60: vm.A60Evidence, source_state: str) -> str:
    """A60：A50 之後的獨立 `<details>`（預設收合；不巢狀、不標首屏）。全程不產生 HTML 空行。`problem_codes` 與其他內部代碼不輸出。"""
    if not isinstance(a60, vm.A60Evidence):
        raise TypeError("a60 must be an A60Evidence")
    state = _a60_effective_state(a60, source_state)
    note = f'<div class="uv3-note" data-a60="labels-note">{_label("a60_labels_note")}</div>'
    tabs = (f'<div class="uv3-row" data-a60="skipped-tabs"><span class="uv3-label">{_label("a60_label_skipped_tabs")}</span>'
            f'{_a60_count_html(a60.skipped_tab_count)}</div>')
    rows = (f'<div class="uv3-row" data-a60="skipped-rows"><span class="uv3-label">{_label("a60_label_skipped_rows")}</span>'
            f'{_a60_count_html(a60.skipped_row_count)}</div>')
    _a60_check_causes(a60.causes)
    line = f'<div class="uv3-row" data-a60="state" data-a60-state="{state}">{_a60_state_html(state)}</div>'
    return (f'<details class="uv3-a60" data-block="a60"><summary>{_label("a60_title")}</summary>{note}'
            f'<div class="uv3-a60-body" data-a60="body">{tabs}{rows}{line}</div></details>')


# ───────────────────────────── 整頁 ─────────────────────────────

def page_html(model: vm.AssetsPageModel) -> str:
    """A00 → A10 → A20 → A50 → A60（順序固定；A60 在最後）。A30／A40／A51／A52 不在這一批。"""
    if not isinstance(model, vm.AssetsPageModel):
        raise TypeError("model must be an AssetsPageModel")
    return a00_html(model.a00) + a10_html(model.a10, model.a00.source_state) + a20_html(model.a20) + a50_html(model.a50, model.a00.source_state) \
        + a60_html(model.a60, model.a00.source_state)


def render(model: vm.AssetsPageModel) -> None:
    import streamlit as st

    st.markdown(CSS, unsafe_allow_html=True)
    st.title(PAGE_TITLE, anchor=False)   # 不產生標題錨點連結（與 nas_diag／🔍 預覽一致；避免多出看不見的 Tab 停駐點）
    st.markdown(page_html(model), unsafe_allow_html=True)
