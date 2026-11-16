# -*- coding: utf-8 -*-
"""💼 我的資產頁的 renderer（隔離式 Preview 第一批：A00 來源狀態、A10 降級卡、A20 固定四格）。頁只吃 `AssetsPageModel`，不取數、不計算領域值。

- `streamlit` 只在函式內 import（import `ui_v3` 時不得載入 Streamlit）。HTML 組裝是純函式，可在沒有 Streamlit 的環境單測。
- 字樣：已核准字樣一律取規則表；尚未核准的取 `assets_page.ASSETS_PENDING_WORDING` 與 `assets_preview_wording`，並以 `data-pending-wording`
  標記。**本檔不硬寫任何中文字樣。** 色與尺寸一律經 `design/theme.py` 取 token。
- 畫面字只依「原因鍵」與「來源狀態」決定；**不讀**原因的分類欄位（類別 (a)(b) 由 view model 的順序表達，畫面各一行、不混成一句）。
- 失敗代碼、市值基準被擋的原因碼、內部鍵一律不上畫面。
- 沒有任何金額、百分比、合計、配置比例、風險判定或建議；沒有匯率換算、沒有跨幣別合計。
- 不畫「持倉入口」：現階段沒有合法的導向目標（持倉區尚未實作），所以即使 view model 帶有入口也不畫（有測試鎖定）。
- 首屏元素（供瀏覽器守衛點數）：A00 一個、A20 四格各一個；A10 的文字不計（標 `data-first-screen` 的只有這五個）。
- A30～A60 不在這一批，不畫。
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
.uv3-card h4{{margin:0 0 4px 0;font-size:{body}}}
.uv3-a20{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:{space};margin-bottom:{space}}}
.uv3-a20 > .uv3-card{{margin-bottom:0;min-width:0}}
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
    return f'<div class="uv3-card" data-block="a10"><h4>{_label("a10_title")}</h4>{rows}{spec}{limits}</div>'


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


# ───────────────────────────── 整頁 ─────────────────────────────

def page_html(model: vm.AssetsPageModel) -> str:
    """A00 → A10 → A20（順序固定）。A30～A60 不在這一批。"""
    if not isinstance(model, vm.AssetsPageModel):
        raise TypeError("model must be an AssetsPageModel")
    return a00_html(model.a00) + a10_html(model.a10, model.a00.source_state) + a20_html(model.a20)


def render(model: vm.AssetsPageModel) -> None:
    import streamlit as st

    st.markdown(CSS, unsafe_allow_html=True)
    st.title(PAGE_TITLE)
    st.markdown(page_html(model), unsafe_allow_html=True)
