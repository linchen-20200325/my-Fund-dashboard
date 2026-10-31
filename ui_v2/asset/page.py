# -*- coding: utf-8 -*-
"""💼 我的資產的 Streamlit 渲染層（BL-0525 Batch D；`DEC-2026-10-30-02`；線框 `docs/v2/73_assets_wireframe_batch_d.md`）。

⚖️ 資產配置與 💼 我的持股合成一頁（`DEC-2026-10-29-06`）。本檔**只負責畫與組合**：兩頁的「載入 → 組模型 → 資料狀態收集」
直接呼叫 `ui_v2/alo/page.py::prepare_live`、`ui_v2/hld/page.py::prepare_live`（單頁 `render` 原樣抽出的同一段，判定、字樣、
資料狀態記錄一個都沒改）；區塊的畫法沿用兩頁既有的 `_render_*`（層 3／層 4 的塊以 `flat=True` 畫成小標題段落，不巢狀展開區）。
圖是 presentation component（D-7）：只讀既有 block output。

由上而下（客戶 2026-10-30 正式產品結構）：
1 持倉資料來源（頁頂獨立一列，D-8）→ 頁名與提問句 → 2 summary strip（總資產／總損益／報酬／配息，四格 Missing，D-5）→
4 一句主判讀（C2，D-10）→ 5 Primary（資產配置 現況 vs 目標，內含 `ALO-0` 一行與 `ALO-3` 入口）→ 6 Secondary ×2（基金占比、各檔區間報酬）→
7 需要注意 → 8 持股明細（`HLD-0` 一行＋`HLD-2`／`HLD-3`）→ 9 層 3 grouped containers（3a）→ 10 層 4 grouped containers（4a）→ 11 ▸ 尚未取得 → 頁尾。

~~**3（page-level combined status）暫停**（客戶 D-3：待最小 Formula Gate 落盤）：本頁**沒有**任何合併燈、合讀規則、排序或聚合；~~
→ 2026-10-31 狀態更新（有意識的更正，不是漏刪；客戶 2026-10-30 裁示 P3／β，`DEC-2026-10-30-04`）：**3（頁級狀態）已實作，待獨立稽核**——
頁頂一個狀態容器（`_render_page_status`，Visual Budget 計 1 個），頭條依 β 階梯、另一區固定照印為第二行；純函式 `ui_v2/asset/page_status.py::aggregate`
只讀 `HLD-0`／`ALO-0` 的分類鍵 `_page_class`，**不回寫、不改任何 rule result**；頭條不是 rule result、不進 Digest、不是 Risk Cap 的輸入或輸出。
~~`HLD-0` 與 `ALO-0` 各自維持既有燈、字樣、判定，仍各放在其所屬區段（持股明細／Primary）既有位置（容器是**另外**的一個頁級彙整，不取代兩枚燈）。~~
→ 2026-10-31 狀態更新（有意識的更正，不是漏刪；客戶 `DEC-2026-10-31-01`／`-02`，V7 Layout A）：**頁級 P3 容器取代合併頁內兩枚燈的重複 presentation**——合併頁不再畫
`ALO-0`／`HLD-0` 的燈元件（presentation de-duplication）；兩個 domain block 的身分、`_page_class`／`_state`／`_tone`、字樣與判定不動，各留一個 `data-block` 錨點與
原區段的說明行／前往 Sheets 鈕（Primary 圖下方、持股明細開頭）。單獨 HLD／ALO 頁照舊畫燈。

⛔ 不改 OAuth（`infra/personal_oauth.py`、`services/v2_tables/personal_session.py`、`ui_v2/set/source.py` 的 callback 流程一律不動）：
頁頂的「持倉資料來源」只重用設定頁既有的 picker（`picker_live`＝`ui_v2/set/source.py::picker_live`，由預覽入口傳進來）與其讀模型
`ui_v2/set/live.py::picker_view`，只用既有 token。
"""

from __future__ import annotations

import functools
import html
from datetime import datetime, timezone

import streamlit as st

from .. import active_gate, health_view, page_health, plain, presentation, presentation_view, sections
from ..alo import logic as alo_logic
from ..alo import page as alo_page
from ..hld import logic as hld_logic
from ..hld import page as hld_page
from ..set import live as set_live
from . import overview as OV
from . import page_status as PS
from . import theme

PICKER_WIDGET_KEY = "set_picker_select"    # 與 `ui_v2/set/source.py::_KEY_PICKER_WIDGET` 同值（widget id 另含頁雜湊，不與設定頁互帶值）
SOURCE_LABEL = "持倉資料來源"                  # 44 之二十其三第 2 條的字面（「持倉資料來源 ▼」）
LAYER_KEY = "live"


def _esc(value) -> str:
    return html.escape(str(value), quote=True)


def _css() -> str:
    return f"""
    .ast-title {{ font-size: 1.45rem; font-weight: 700; letter-spacing: .04em; color: {theme.TEAL_DARK};
      border-bottom: 2px solid {theme.TEAL_DARK}; padding-bottom: .4rem; margin-bottom: .2rem; }}
    .ast-sub {{ color: {theme.TEXT_MUTED}; font-size: .82rem; margin-bottom: .6rem; }}
    .ast-source-label {{ color: {theme.TEAL_DARK}; font-size: .8rem; font-weight: 700; margin: 0 0 .15rem; }}
    .ast-section-label {{ color: {theme.TEAL_DARK}; font-size: .72rem; letter-spacing: .18em; margin: 1.1rem 0 .35rem; }}
    .ast-summary {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: .4rem .8rem;
      border: 1px solid {theme.BORDER}; background: {theme.SURFACE}; border-radius: 8px; padding: .55rem .8rem; margin: .4rem 0; }}
    .ast-slot {{ display: flex; flex-direction: column; min-width: 0; }}
    .ast-slot-label {{ font-size: .74rem; color: {theme.TEXT_MUTED}; }}
    .ast-slot-value {{ font-size: .95rem; font-weight: 600; overflow-wrap: anywhere; }}
    @media (max-width: 560px) {{ .ast-summary {{ grid-template-columns: repeat(2, minmax(0, 1fr)); padding: .4rem .6rem; }} }}
    .ast-pstatus {{ border: 1px solid {theme.BORDER}; border-left: 6px solid {theme.EDGE}; background: {theme.SURFACE};
      border-radius: 6px; padding: .25rem .6rem; margin: .25rem 0; overflow-wrap: anywhere; line-height: 1.3; }}
    .ast-pstatus-head {{ font-size: .88rem; font-weight: 700; color: {theme.TEXT_PRIMARY}; }}
    .ast-pstatus-second {{ font-size: .8rem; font-weight: 500; color: {theme.TEXT_PRIMARY}; margin-top: .2rem;
      padding-top: .2rem; border-top: 1px dashed {theme.BORDER}; }}
    .ast-pstatus .ast-note {{ font-size: .72rem; margin: .05rem 0; }}
    .ast-entry {{ margin: .1rem 0; }}
    .ast-hero {{ font-size: 1rem; font-weight: 600; color: {theme.TEXT_PRIMARY}; margin: .5rem 0 .6rem; overflow-wrap: anywhere; }}
    .ast-card-title {{ font-weight: 700; color: {theme.TEAL_DARK}; margin: 0 0 .25rem; }}
    .ast-bars {{ margin: .3rem 0; }}
    .ast-bar-row {{ margin: .45rem 0 .6rem; }}
    .ast-bar-name {{ font-size: .84rem; font-weight: 600; overflow-wrap: anywhere; }}
    .ast-bar-line {{ display: flex; align-items: center; gap: .5rem; margin: .12rem 0; }}
    .ast-bar-tag {{ flex: 0 0 2.2rem; font-size: .72rem; color: {theme.TEXT_MUTED}; }}
    .ast-track {{ flex: 1 1 auto; min-width: 0; height: .7rem; border: 1px solid {theme.EDGE}; border-radius: 3px; background: {theme.SURFACE}; }}
    .ast-fill {{ display: block; height: 100%; background: {theme.TEAL_DARK}; border-radius: 2px; }}
    .ast-fill-target {{ display: block; height: 100%; border-right: 3px solid {theme.TEAL_DARK};
      background: repeating-linear-gradient(135deg, transparent 0 4px, {theme.BORDER} 4px 6px); }}
    .ast-val {{ flex: 0 1 9rem; font-size: .78rem; text-align: right; overflow-wrap: anywhere; }}
    .ast-bar-meta {{ font-size: .74rem; color: {theme.TEXT_MUTED}; overflow-wrap: anywhere; }}
    .ast-scroll {{ max-height: 15rem; overflow-y: auto; overflow-x: hidden; padding-right: .3rem;
      border-top: 1px solid {theme.BORDER}; border-bottom: 1px solid {theme.BORDER}; }}
    .ast-row {{ margin: .35rem 0; }}
    .ast-row-name {{ font-size: .8rem; overflow-wrap: anywhere; }}
    .ast-axis {{ flex: 1 1 auto; min-width: 0; display: flex; height: .7rem; border: 1px solid {theme.EDGE}; border-radius: 3px; background: {theme.SURFACE}; }}
    .ast-half {{ flex: 0 0 50%; display: flex; height: 100%; }}
    .ast-half-neg {{ justify-content: flex-end; border-right: 2px solid {theme.TEXT_PRIMARY}; box-sizing: border-box; }}
    .ast-bar {{ display: block; height: 100%; background: {theme.TEAL_DARK}; }}
    .ast-bar-hatch {{ background: repeating-linear-gradient(135deg, {theme.TEAL_DARK} 0 3px, {theme.SURFACE} 3px 6px); }}
    .ast-note {{ font-size: .76rem; color: {theme.TEXT_MUTED}; margin: .2rem 0; overflow-wrap: anywhere; }}
    .ast-err {{ color: {theme.tone_hex("紅")}; font-size: .85rem; margin: .3rem 0; overflow-wrap: anywhere; }}
    .ast-status {{ font-size: .85rem; margin: .3rem 0; overflow-wrap: anywhere; }}
    .ast-block-head {{ font-weight: 700; font-size: .84rem; color: {theme.TEAL_DARK}; margin: .9rem 0 .3rem;
      border-top: 1px dashed {theme.BORDER}; padding-top: .5rem; overflow-wrap: anywhere; }}
    .ast-missing-item {{ font-size: .82rem; margin: .2rem 0; overflow-wrap: anywhere; }}
    .ast-footer {{ margin-top: 1.4rem; border-top: 1px solid {theme.BORDER}; padding-top: .7rem; color: {theme.TEXT_MUTED}; font-size: .78rem; }}
    [data-testid="stHorizontalBlock"] {{ flex-wrap: wrap !important; gap: 12px; }}
    [data-testid="stHorizontalBlock"] > [data-testid="stColumn"], [data-testid="stHorizontalBlock"] > [data-testid="column"] {{
      flex: 1 1 100% !important; min-width: 0 !important; }}
    @media (min-width: 769px) {{
      .st-key-ast_pair [data-testid="stHorizontalBlock"] > [data-testid="stColumn"],
      .st-key-ast_pair [data-testid="stHorizontalBlock"] > [data-testid="column"],
      .st-key-ast_pair_hold [data-testid="stHorizontalBlock"] > [data-testid="stColumn"],
      .st-key-ast_pair_hold [data-testid="stHorizontalBlock"] > [data-testid="column"] {{ flex: 1 1 calc(50% - 12px) !important; }}
    }}
    """


def _inject_css() -> None:
    st.markdown(
        f"<style>{alo_page._base_css()}{hld_page._base_css()}{presentation.PRESENTATION_CSS}{_css()}</style>",
        unsafe_allow_html=True)


# ───────────────────────── 1 持倉資料來源（D-8：頁頂獨立一列）─────────────────────────


def _render_source_row(picker_live, picker_data, no_active: bool, settings_page) -> None:
    """頁頂一列「持倉資料來源」。已登入 → 重用設定頁既有的 picker（同一份讀模型、同一組動作；不碰 OAuth）；
    未登入／沒有 Active → 沿用 `active_gate` 既有字樣「⬜ 尚未選定持倉資料來源」與「前往 ⚙️ 設定」連結。"""
    with st.container(key="ast_source"):
        st.markdown(f'<div class="ast-source-label">{_esc(SOURCE_LABEL)}</div>', unsafe_allow_html=True)
        view = set_live.picker_view(picker_data) if picker_live is not None else {"state": "hidden"}
        if view["state"] != "hidden":
            for line in view["lines"]:
                st.markdown(f'<div class="ast-note">{_esc(line)}</div>', unsafe_allow_html=True)
            if view["options"]:
                ids = [o["id"] for o in view["options"]]
                labels = {o["id"]: o["label"] for o in view["options"]}
                st.selectbox(SOURCE_LABEL, ids, index=view["selected"], format_func=labels.__getitem__,
                             placeholder=set_live.PICKER_PLACEHOLDER, key=PICKER_WIDGET_KEY, label_visibility="collapsed",
                             on_change=lambda: picker_live["act"]("select", st.session_state.get(PICKER_WIDGET_KEY)))
            for button in view["buttons"]:
                st.button(button["label"], key=f"ast_picker_{button['action']}", on_click=picker_live["act"],
                          args=(button["action"], *((button["arg"],) if "arg" in button else ())))
        if no_active:
            active_gate.render_no_active_status(tone_hex=theme.tone_hex, settings_page=settings_page)


# ───────────────────────── 載入（兩側各自 prepare；一側失敗不拖垮另一側）─────────────────────────


def _prepare(page_mod, slug: str, live: dict) -> dict:
    """一側的「載入 → 組模型 → 資料狀態收集」。一側的取數失敗只讓**這一側**改畫狀態、另一側照常：
    `LiveFailed`（`prepare_live` 內「去拿」與「組模型」兩步失敗；已包好）與 `sections.HoldingCountsInconsistent`
    （`prepare_live` 內 `sections.hld_counts` 的持倉體檢計數不成立：n < m ＋ j）一律原文進進階診斷、記進總表、寫 log（`record_live_error`），
    一般畫面只畫一句狀態——不吞、不往另一側擴散。

    **只接這兩種。** `prepare_live` 在 try 之外（或其他地方）拋的其他例外（包括別的 `ValueError`）是本檔案自己的 bug，不是取數失敗，
    不得畫成取數失敗——照舊往上浮出，由 `render` 的 `_record_collect_failure` 記一筆再往上拋（同單頁 `guard_page` 的體例）。
    `NoActiveSource` 是第三種狀態，不是失敗（J-13）。"""
    try:
        if slug == "alo":
            prep = page_mod.prepare_live(load_live=live["load"], save_live=live.get("save"))
        else:
            prep = page_mod.prepare_live(load_live=live["load"])
    except active_gate.NoActiveSource:
        return {"state": "no_active", "line": active_gate.TEXT_NO_ACTIVE}
    except page_mod.LiveFailed as failed:   # 不是吞：原文進進階診斷、記進總表（同單頁）；區段改畫一句狀態
        return {"state": "error", "line": page_mod.record_live_error(failed.exc, live.get("mask"))}
    except sections.HoldingCountsInconsistent as exc:   # 不是吞：同上（這一種單頁沒人接、會炸整頁；合併頁不讓它拖垮另一側）
        return {"state": "error", "line": page_mod.record_live_error(exc, live.get("mask"))}
    holding_n = None
    if slug == "hld":   # 持倉來源本身有錯時 n 建立在不完整持倉上 → 不當成「持有 n 檔」（OV.hero_holding_count；D-10）
        holding_n = OV.hero_holding_count(sections.hld_holding_count(prep["model"]), prep["holding_error"])
    return {"state": "ok", "holding_n": holding_n, **prep}


def _state_div(side: dict, text: str) -> None:
    """一側沒載入的那一句：載入失敗（紅、`role="alert"`）與「沒有 Active Sheet」（灰、`role="status"`，同 `active_gate.render_no_active_status`）
    分開畫——J-13 的三種狀態（有資料／沒有 Active／系統出錯）在合併頁混合情形下也不能被畫成同一種紅。"""
    if side["state"] == "no_active":
        st.markdown(f'<div class="ast-status" role="status" style="color:{theme.tone_hex("灰")}">{_esc(text)}</div>',
                    unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="ast-err" role="alert">{_esc(text)}</div>', unsafe_allow_html=True)


def _error_line(side: dict) -> None:
    """這一側沒載入的完整那一句（頁首每側只畫一次）：載入失敗＝一般畫面那句取數失敗、沒有 Active＝既有的「⬜ 尚未選定持倉資料來源」。"""
    _state_div(side, side["line"])


def _short_state(side: dict) -> str:
    """區段內標示「這一區沒載入」的短句：沿用既有狀態族字面（`sections.LINE_FETCH_FAILED`、`active_gate.TEXT_NO_ACTIVE`），
    完整那一句只在頁首畫一次（單頁整頁也只有一句）。"""
    return sections.LINE_FETCH_FAILED if side["state"] == "error" else active_gate.TEXT_NO_ACTIVE


def _side_notice(side: dict, label=None) -> None:
    text = _short_state(side)
    if label:
        text = f"{label}　{text}"
    _state_div(side, text)


def _label(text: str) -> None:
    st.markdown(f'<div class="ast-section-label">{_esc(text)}</div>', unsafe_allow_html=True)


# ───────────────────────── 圖（presentation component；只讀既有 block output）─────────────────────────


def _clamp_pct(value) -> float:
    return min(max(float(value), 0.0), 100.0)


def primary_bars_html(rows: list, labels) -> str:
    """每類兩條：實心＝現況、斜線＋右緣粗線＝目標；直接標籤（數字與「現況／目標」字樣），不靠顏色。缺值那一格不畫條、只印原字。"""
    diff_label, band_label = (labels[3], labels[4]) if len(labels) >= 5 else ("差額", "容許帶")
    out = []
    for row in rows:
        def line(tag, pct, text, klass):
            bar = "" if pct is None else f'<span class="{klass}" style="width:{_clamp_pct(pct):.1f}%"></span>'
            return (f'<div class="ast-bar-line"><span class="ast-bar-tag">{_esc(tag)}</span>'
                    f'<span class="ast-track">{bar}</span><span class="ast-val">{_esc(text)}</span></div>')
        out.append(
            f'<div class="ast-bar-row" data-bucket="{_esc(row["bucket"])}"><div class="ast-bar-name">{_esc(row["bucket"])}</div>'
            + line(OV.TEXT_CURRENT, row["current_pct"], row["current_text"], "ast-fill")
            + line(OV.TEXT_TARGET, row["target_pct"], row["target_text"], "ast-fill-target")
            + f'<div class="ast-bar-meta">{_esc(diff_label)} {_esc(row["diff_text"])}　{_esc(band_label)} {_esc(row["band_text"])}</div></div>')
    return f'<div class="ast-bars" data-chart="primary">{"".join(out)}</div>'


def share_bars_html(rows: list) -> str:
    out = []
    for row in rows:
        bar = "" if row["ratio"] is None else f'<span class="ast-fill" style="width:{_clamp_pct(row["ratio"] * 100):.1f}%"></span>'
        out.append(f'<div class="ast-row"><div class="ast-row-name">{_esc(row["label"])}　{_esc(row["bucket"])}</div>'
                   f'<div class="ast-bar-line"><span class="ast-track">{bar}</span><span class="ast-val">{_esc(row["text"])}</span></div></div>')
    return f'<div class="ast-scroll" tabindex="0" data-chart="share">{"".join(out)}</div>'


def returns_bars_html(rows: list) -> str:
    scale = OV.return_scale(rows)
    out = []
    for row in rows:
        if row["value"] is None:
            axis = '<span class="ast-axis"><span class="ast-half ast-half-neg"></span><span class="ast-half"></span></span>'
        else:
            width = min(abs(row["value"]) / scale * 100.0, 100.0)
            bar = f'<span class="ast-bar" style="width:{width:.1f}%"></span>'
            neg, pos = (bar, "") if row["value"] < 0 else ("", bar)
            axis = f'<span class="ast-axis"><span class="ast-half ast-half-neg">{neg}</span><span class="ast-half">{pos}</span></span>'
        out.append(f'<div class="ast-row"><div class="ast-row-name">{_esc(row["label"])}</div>'
                   f'<div class="ast-bar-line">{axis}<span class="ast-val">{_esc(row["text"])}</span></div></div>')
    return f'<div class="ast-scroll" tabindex="0" data-chart="returns">{"".join(out)}</div>'


# ───────────────────────── 區段 ─────────────────────────


def _render_summary() -> None:
    strip = OV.summary_strip()
    slots = "".join(
        f'<div class="ast-slot" data-slot="{_esc(s["label"])}"><span class="ast-slot-label">{_esc(s["label"])}</span>'
        f'<span class="ast-slot-value" style="color:{theme.tone_hex(s["tone"])}">{_esc(s["value"])}</span></div>'
        for s in strip["slots"])
    st.markdown(f'<div class="ast-summary" data-section="summary">{slots}</div>', unsafe_allow_html=True)
    presentation_view.render_detail(strip["detail"])


def _render_page_status(hld: dict, alo: dict) -> None:
    """頁級狀態容器（P3；`DEC-2026-10-30-04`；字樣與合成行邊界待客戶確認，74 F-5）。一個整體符號＝頭條那一行自己的符號與狀態字；
    另一區固定照印為第二行，含它自己的附行。每一行都有符號＋狀態字＋字樣（不靠顏色單獨辨識）。
    前往 Sheets 鈕不在容器內畫：它仍由 `HLD-0` 所屬的持股明細區段畫一次（本頁只有那一處）。"""
    status = PS.aggregate(hld, alo)
    head = status["container"]
    rows_html = []
    for index, row in enumerate(status["rows"]):
        label = PS.row_label(row)
        lines = "".join(f'<div class="ast-note">{_esc(line)}</div>' for line in row["lines"])
        klass = "ast-pstatus-head" if index == 0 else "ast-pstatus-second"
        rows_html.append(f'<div class="{klass}" data-row="{_esc(row["class"])}" data-area="{_esc(row["area"] or "合併")}">'
                         f'<div>{_esc(label)}</div>{lines}</div>')
    st.markdown(
        f'<div class="ast-pstatus" data-section="page-status" data-kind="{_esc(status["kind"])}" '
        f'style="border-left-color:{theme.tone_hex(head["tone"])}">{"".join(rows_html)}</div>',
        unsafe_allow_html=True)


ALO0_READS_PLAIN = "本燈只讀 目標對照卡 算出的差距，不指出方向。"        # 單獨 ALO 頁（與 `ui_v2/alo/logic.py` 常數經 `plain` 轉換後）的原字樣；單頁不動
ALO0_READS_MERGED = "此配置判讀只讀 目標對照卡 算出的差距，不指出方向。"  # 合併頁專屬字樣（客戶 2026-10-31 線框裁示：該位置已沒有獨立「燈」元件）


def alo0_entry_lines(block: dict) -> list:
    """`ALO-0` 在合併頁 Primary 圖下方留的說明行（只讀 block，不回寫）：「回答什麼」那句＋ `detail_lines` 中非附行的部分。
    附行（前 `_attached_n` 行）已由頁級容器「配置：」那一行照印，這裡不重複。只有合併頁專屬字串轉換——說明句「本燈只讀…」改為
    「此配置判讀只讀…」；單獨 ALO 頁的 `_render_alo0` 與其常數、測試一個字都不動。其餘字樣一律原樣。"""
    attached = block.get("_attached_n", 0)
    tail = block["detail_lines"][attached:]
    if ALO0_READS_PLAIN not in tail:   # Fail Loud：上游說明句改了字，不得靜默退回「本燈」（客戶只核准這一句的改字；其餘不順改）
        raise ValueError(f"ALO-0 非附行說明句不含預期原字樣 {ALO0_READS_PLAIN!r}：{tail!r}（上游字樣已變，請更新 ALO0_READS_PLAIN 並回報）")
    rest = [ALO0_READS_MERGED if line == ALO0_READS_PLAIN else line for line in tail]
    return [block["answers"], *rest]


def hld0_entry_lines(block: dict) -> list:
    """`HLD-0` 在合併頁持股明細留的說明行：「回答什麼」那句＋全部 `detail_lines`。`lines` 不重畫（頁級容器持股行已照印）。"""
    return [block["answers"], *block["detail_lines"]]


def _render_block_entry(block: dict, lines: list, css: str, rest_css: str = None) -> None:
    """Domain Block Identity ≠ Presentation Instance（客戶 2026-10-31）：燈元件不再畫，但 `data-block` 錨點恰留一個在這個說明容器上。"""
    inner = "".join(f'<div class="{css if index == 0 else (rest_css or css)}">{_esc(line)}</div>' for index, line in enumerate(lines))
    st.markdown(f'<div class="ast-entry" data-block="{_esc(block["code"])}">{inner}</div>', unsafe_allow_html=True)


def _render_primary(alo: dict, settings_page) -> None:
    with st.container(border=True, key="ast_primary"):
        st.markdown(f'<div class="ast-card-title" data-section="primary">{_esc(OV.PRIMARY_TITLE)}</div>', unsafe_allow_html=True)
        if alo["state"] != "ok":
            _side_notice(alo)
            return
        model, ctx, quiet = alo["model"], alo["ctx"], alo["quiet"]
        alo2, alo1, alo4 = (alo_logic.find_block(model, c) for c in ("ALO-2", "ALO-1", "ALO-4"))
        alo0 = alo_logic.find_block(model, "ALO-0")   # A（DEC-2026-10-31-01）：燈元件在合併頁不畫（狀態由頁級容器承擔）；說明行移到圖下方
        alo_page._lines(model["top_lines"], "alo-topline")   # 單頁頁面頂端那一行灰字（例：「目標合計 90%」）；合併頁放在現況 vs 目標之上
        if quiet.get("ALO-2") is not None:
            alo_page._render_alo2(alo2, LAYER_KEY, ctx, plain_mode=True, quiet=quiet["ALO-2"])
            _render_block_entry(alo0, alo0_entry_lines(alo0), "alo-note")
        else:
            st.markdown(presentation.chips_html(OV.primary_chips(alo1, alo4, alo["as_of"])), unsafe_allow_html=True)
            alo_page._placeholder(alo2)
            rows = OV.primary_rows(alo2)
            if rows:
                st.markdown(primary_bars_html(rows, alo2["column_labels"]), unsafe_allow_html=True)
            _render_block_entry(alo0, alo0_entry_lines(alo0), "alo-note")
            with st.expander(OV.PRIMARY_DETAIL_TITLE, expanded=False):
                alo_page._render_alo2(alo2, LAYER_KEY, ctx, plain_mode=True)
        alo3 = alo_logic.find_block(model, sections.ALO_SCENARIO_CODE)
        with st.expander(sections.alo3_entry_title(alo3), expanded=False):   # ALO-3：層 2 入口現況照舊（存檔停用；本頁不新增任何寫入控制）
            alo_page._render_alo3(alo3, LAYER_KEY, ctx, plain_mode=True, quiet=quiet.get("ALO-3"))


def _secondary_share(alo: dict) -> None:
    with st.container(border=True, key="ast_sec_share"):
        st.markdown(f'<div class="ast-card-title" data-section="secondary">{_esc(OV.SHARE_TITLE)}</div>', unsafe_allow_html=True)
        if alo["state"] != "ok":
            _side_notice(alo)
            return
        model, details = alo["model"], alo["details"]
        alo6, alo4 = alo_logic.find_block(model, "ALO-6"), alo_logic.find_block(model, "ALO-4")
        if "ALO-6" in details:
            alo_page._render_detail_quiet(details["ALO-6"], flat=True)
            return
        rows = OV.share_rows(alo6)
        # D-3 第二輪（稽核 S2；DEC-2026-10-30-04 F-18）：有持倉列被略過時，件數與合計不假裝覆蓋完整集合。
        omitted = OV.share_omitted_lines(alo_logic.find_block(model, "ALO-2"))
        st.markdown(presentation.chips_html(OV.share_chips(alo4, rows, omitted_lines=omitted)), unsafe_allow_html=True)
        alo_page._placeholder(alo6)
        if rows:
            st.markdown(share_bars_html(rows), unsafe_allow_html=True)
        presentation_view.render_detail(OV.share_detail(alo6))   # 略過的列已在 ALO-6 表尾（D-3 第三輪，不另接）


def _secondary_returns(hld: dict) -> None:
    with st.container(border=True, key="ast_sec_returns"):
        st.markdown(f'<div class="ast-card-title" data-section="secondary">{_esc(OV.RETURNS_TITLE)}</div>', unsafe_allow_html=True)
        if hld["state"] != "ok":
            _side_notice(hld)
            return
        model, quiet = hld["model"], hld["quiet"]
        hld2, hld4 = hld_logic.find_block(model, "HLD-2"), hld_logic.find_block(model, "HLD-4")
        if quiet.get("HLD-2") is not None:
            hld_page._render_core_card(hld2, plain_mode=True, quiet=quiet["HLD-2"])
            return
        rows = OV.return_rows(hld2)
        st.markdown(presentation.chips_html(OV.return_chips(hld4, rows)), unsafe_allow_html=True)
        if rows:
            st.markdown(returns_bars_html(rows), unsafe_allow_html=True)
        presentation_view.render_detail(OV.returns_detail(hld2))


def _render_attention(alo: dict, hld: dict) -> None:
    _label(plain.LABEL_ATTENTION)
    if alo["state"] == "ok":
        for item in alo["attention"]:
            text = (item["symbol"] + " " + item["text"]).strip()
            st.markdown(f'<div class="v2-attention" style="color:{theme.tone_hex(item["_tone"])}">{_esc(text)}</div>',
                        unsafe_allow_html=True)
    else:
        _side_notice(alo, OV.ALLOC_LABEL)
    if hld["state"] == "ok":
        hld_page._render_hld1(hld_logic.find_block(hld["model"], sections.HLD_ATTENTION_CODE), plain_mode=True,
                              quiet=hld["quiet"].get(sections.HLD_ATTENTION_CODE))
    else:
        _side_notice(hld, OV.HOLDINGS_LABEL)


def _render_holdings(hld: dict) -> None:
    _label(OV.HOLDINGS_LABEL)
    if hld["state"] != "ok":
        _side_notice(hld)
        return
    model, quiet = hld["model"], hld["quiet"]
    hld0 = hld_logic.find_block(model, "HLD-0")   # A（DEC-2026-10-31-01）：燈元件在合併頁不畫；按鈕（key 不變）與說明行留在持股明細開頭
    hld_page._buttons(hld0, hld0["code"])
    _render_block_entry(hld0, hld0_entry_lines(hld0), "hld-note", "hld-line")   # 字級同燈下原畫法：answers=hld-note、detail=hld-line
    if hld["counts_line"]:
        st.markdown(f'<div class="hld-lamp-text">{_esc(hld["counts_line"])}</div>', unsafe_allow_html=True)
    with st.container(key="ast_pair_hold"):
        for column, code in zip(st.columns(2), ("HLD-2", "HLD-3")):
            with column:
                hld_page._render_core_card(hld_logic.find_block(model, code), plain_mode=True, quiet=quiet.get(code))


def _render_alo_block(alo: dict, code: str, *, flat: bool) -> None:
    """規則順序同單頁 `alo/page.py::render` 層 3：`ALO-1` 先（展開區標題帶摘要）、再看收合區比照、最後各塊自己的畫法。"""
    model, ctx, details = alo["model"], alo["ctx"], alo["details"]
    block = alo_logic.find_block(model, code)
    if code == "ALO-1":
        head = f"{block['title']}　—　{sections.alo1_summary(block)}"
        if flat:
            with presentation_view.flat_block(head, code=code):
                alo_page._RENDERERS[code](block, LAYER_KEY, ctx, plain_mode=True)
        else:
            with st.expander(head, expanded=block["_default_open"]):
                alo_page._RENDERERS[code](block, LAYER_KEY, ctx, plain_mode=True)
    elif code in details:
        alo_page._render_detail_quiet(details[code], flat=flat)
    else:
        alo_page._RENDERERS[code](block, LAYER_KEY, ctx, plain_mode=True, flat=flat)


def _render_hld_block(hld: dict, code: str, *, flat: bool, on_save) -> None:
    """規則順序同單頁 `hld/page.py::render` 層 3：`HLD-4` 先、再看收合區比照、最後各塊自己的畫法。"""
    block = hld_logic.find_block(hld["model"], code)
    if code == "HLD-4":
        hld_page._render_hld4(block, on_save=on_save, plain_mode=True, flat=flat)
    elif code in hld["details"]:
        hld_page._render_detail_quiet(hld["details"][code], flat=flat)
    else:
        hld_page._RENDERERS[code](block, plain_mode=True, flat=flat)


def _block_state(side: dict, code: str):
    """這一塊在單頁展開區標題「—」後面那一句（有狀態才回；正常回 None）。取法與單頁一致：`ALO-1` 讀 `sections.alo1_summary`、
    收合區比照的塊讀它那一行原因、其餘讀 `summary_text`；這一側沒載入 → 既有狀態族短句。"""
    if side["state"] != "ok":
        return _short_state(side)
    mod = alo_logic if code.startswith("ALO") else hld_logic
    block = mod.find_block(side["model"], code)
    if code == "ALO-1":
        summary = sections.alo1_summary(block)
    elif code != "HLD-4" and code in side["details"]:
        return side["details"][code]["line"]["text"]
    else:
        summary = block["summary_text"]
    return OV.block_state(block, summary)


def _render_group(name, codes, alo: dict, hld: dict, on_save) -> None:
    """一個 presentation container（D-1 R-C）。多塊容器＝一個預設收合的展開區，**其內**各塊以小標題分組（`flat=True`，不巢狀展開區）；
    單塊容器＝該塊自己的展開區（標題就是塊的正式標題）。標題列帶出容器內有狀態的塊（取數失敗、資料未備…；同單頁標題的字面）。
    某側沒載入 → 該側的塊不畫，容器內每一側只畫一句短狀態（標題列已點名是哪幾塊，不逐塊重複）。"""
    sides = {"ALO": alo, "HLD": hld}
    titles, states = {}, {}
    for code in codes:
        side = sides[code[:3]]
        mod = alo_logic if code.startswith("ALO") else hld_logic
        titles[code] = mod.find_block(side["model"], code)["title"] if side["state"] == "ok" else mod.BLOCK_TITLES[code]
        states[code] = _block_state(side, code)

    if name is None:
        code = codes[0]
        side = sides[code[:3]]
        if side["state"] != "ok":
            _state_div(side, f"{titles[code]}　—　{states[code]}")
        elif code.startswith("ALO"):
            _render_alo_block(side, code, flat=False)
        else:
            _render_hld_block(side, code, flat=False, on_save=on_save)
        return
    noticed = set()
    with st.expander(OV.container_title(name, codes, titles, states), expanded=False):
        for code in codes:
            side = sides[code[:3]]
            if side["state"] != "ok":
                if code[:3] not in noticed:
                    noticed.add(code[:3])
                    _side_notice(side, OV.ALLOC_LABEL if code.startswith("ALO") else OV.HOLDINGS_LABEL)
            elif code.startswith("ALO"):
                _render_alo_block(side, code, flat=True)
            else:
                _render_hld_block(side, code, flat=True, on_save=on_save)


def _record_collect_failure(exc: Exception) -> None:
    for slug in ("alo", "hld"):
        page_health.record_collect_failure(st.session_state, slug, type(exc).__name__, now=datetime.now(timezone.utc))


def render(*, alo_live: dict, hld_live: dict, picker_live=None, settings_page=None) -> None:
    """畫整頁。

    alo_live／hld_live：`{"load": 載入函式, "save": 寫入函式或 None, "mask": 遮蔽函式或 None}`，與各自單頁 `render` 的
    `load_live`／`save_live`／`mask_error` 同名同物件（預覽入口 `ui_v2/app_preview.py` 傳 `alo.source`、`hld.source` 的那三支）。
    picker_live：設定頁既有的 `{"load", "act"}`（`ui_v2/set/source.py::picker_live`）；不傳＝不畫選單（只畫沒有 Active 的狀態）。
    settings_page：選填 `st.Page`（只換頁）。
    """
    try:
        _render(alo_live, hld_live, picker_live, settings_page)
    except Exception as exc:   # 同單頁 `guard_page`：畫頁崩潰時總表不留上一筆正常記錄，然後照舊往上拋（不吞）
        _record_collect_failure(exc)
        raise


def _render_header_state(alo: dict, hld: dict, settings_page) -> None:
    """頁首資料狀態：每側（配置、持股）各一組——載入成功的側先畫單頁頁首同一支「主要原因／另有」，再畫該側的資料日
    （「資料截至 ‹日期›」，字樣取 `page_health`；沒有日期寫「—」，不補、不借另一側的）；沒載入的側畫「資料截至 —」與完整的那一句狀態
    （載入失敗＝一般畫面那句取數失敗，沒有 Active＝既有字樣）。兩側日期各自誠實，不合成一個頁級日期。"""
    for slug, side, label in (("alo", alo, OV.ALLOC_LABEL), ("hld", hld, OV.HOLDINGS_LABEL)):
        if side["state"] == "ok":
            health_view.render_header_reasons(slug, as_of=side["as_of"], tone_hex=theme.tone_hex)
        as_of = side["as_of"] if side["state"] == "ok" else None
        st.markdown(f'<div class="v2-status-line" role="status" style="color:{theme.tone_hex("灰")}">'
                    f'{_esc(OV.data_date_line(label, as_of))}</div>', unsafe_allow_html=True)
        if side["state"] != "ok":
            _error_line(side)
    health_view.render_settings_link(settings_page)


def _render(alo_live, hld_live, picker_live, settings_page) -> None:
    _inject_css()
    # 先讀 picker（列清單遇到登入失效會清整個 session，兩側載入才看得到清掉之後的狀態；同設定頁的順序理由）。
    picker_data = picker_live["load"]() if picker_live is not None else None
    alo = _prepare(alo_page, "alo", alo_live)
    hld = _prepare(hld_page, "hld", hld_live)
    no_active_slugs = [slug for slug, side in (("alo", alo), ("hld", hld)) if side["state"] == "no_active"]
    failed = any(side["state"] == "error" for side in (alo, hld))
    # 取數失敗優先於「尚未設定」：任何一側載入失敗，整頁就不是「沒有 Active Sheet」——失敗那一側的記錄（`record_live_error`）與錯誤句
    # 照留，不得被「尚未設定：持倉資料來源」覆寫成另一種狀態；沒有 Active 的那一側（若有）只記它自己。
    whole_page_no_active = bool(no_active_slugs) and not failed

    _render_source_row(picker_live, picker_data, bool(no_active_slugs), settings_page)
    st.markdown(f'<div class="ast-title">{_esc(OV.PAGE_TITLE)}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="ast-sub">{_esc(OV.PAGE_ANSWERS)}</div>', unsafe_allow_html=True)
    # 沒有 Active Sheet ＝ 明確的第三種狀態（批 3b-4 J-13）：不是 0、不是中性、不是空持倉；總表記一筆「尚未設定：持倉資料來源」。
    # 整頁畫成「尚未選定」（沒有任何一側失敗、至少一側沒有 Active）時，兩格都記尚未設定——使用者看到的整頁就是「尚未選定」，
    # 總表不能還留著另一側「載入成功」的記錄（parent aba1ee1a 的行為）。混合（有一側失敗）時才只記沒有 Active 的那一側。
    for slug in ("alo", "hld") if whole_page_no_active else no_active_slugs:
        active_gate.record_no_active(slug)
    if whole_page_no_active:
        return

    _render_header_state(alo, hld, settings_page)

    _render_page_status(hld, alo)   # 頁級狀態（P3）：頭條＋另一行；兩枚燈各自的字樣與判定不動、仍在各自區段
    _render_summary()
    n = hld["holding_n"] if hld["state"] == "ok" else None
    alo0 = alo_logic.find_block(alo["model"], "ALO-0") if alo["state"] == "ok" else None
    incomplete = alo["state"] == "ok" and OV.allocation_incomplete(alo0, alo_logic.find_block(alo["model"], "ALO-2"))
    st.markdown(f'<div class="ast-hero" data-section="hero">{_esc(OV.hero_sentence(n, alo0, incomplete=incomplete))}</div>',
                unsafe_allow_html=True)

    _render_primary(alo, settings_page)
    with st.container(key="ast_pair"):
        left, right = st.columns(2)
        with left:
            _secondary_share(alo)
        with right:
            _secondary_returns(hld)
    _render_attention(alo, hld)
    _render_holdings(hld)

    on_save = None
    if hld["state"] == "ok" and hld_live.get("save") is not None:
        on_save = functools.partial(hld_page._on_save_live, hld_live["save"])
    _label(plain.LABEL_DETAILS)
    _label(plain.LABEL_LAYER3)
    for name, codes in OV.LAYER3_CONTAINERS:
        _render_group(name, codes, alo, hld, on_save)
    _label(plain.LABEL_LAYER4)
    for name, codes in OV.LAYER4_CONTAINERS:
        _render_group(name, codes, alo, hld, on_save)

    group = OV.missing_group()
    with st.expander(group["title"], expanded=False):
        for item in group["items"]:
            st.markdown(f'<div class="ast-missing-item">{_esc(item["name"])}　{presentation.chip_html(item["chip"])}　{_esc(item["reason"])}</div>',
                        unsafe_allow_html=True)

    sides = [side["model"]["footer_lines"] for side in (alo, hld) if side["state"] == "ok"]
    if sides:   # 兩區「不負責什麼」都保留（`overview.footer_text`：只去重複與指向本頁自己的半句）；本頁不新增結論
        st.markdown(f'<div class="ast-footer">{_esc(OV.footer_text(sides))}</div>', unsafe_allow_html=True)
