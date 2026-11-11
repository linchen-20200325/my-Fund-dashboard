# -*- coding: utf-8 -*-
"""PoC 頁（模仿 🌍 市場頁的元件組合；**全部合成資料**）。

模式權威＝**唯一**一個受控 session_state 鍵 `KEY_MODE`（`st.radio` 的 widget key）。
⚠️ 不用 `st.context.theme`：它不反映本 PoC 的 scoped CSS（#1209 QA 已查 1.59.1／1.59.2），不能當模式權威。
CSS 在腳本最前面依目前模式產生並注入（切換時 Streamlit 先把新值寫進 session_state 才重跑腳本，所以同一輪就是新色，沒有二次 rerun）。
"""
from __future__ import annotations

from html import escape

import streamlit as st

import poc_chart_svg as svg
import poc_fixtures as fx
import poc_palettes as pal
import poc_theme_css as css

KEY_MODE = "poc_theme_mode"
KEY_VIEW, KEY_PERIOD = "poc_view", "poc_period"
MODE_LABELS = {"light": "☀️ 淺色", "dark": "🌙 深色"}


def current_mode() -> str:
    """模式的唯一讀取點：session_state[KEY_MODE]；沒有（新 session）＝預設淺色。未知值 Fail Loud。"""
    mode = st.session_state.get(KEY_MODE, pal.DEFAULT_MODE)
    pal.get(mode)  # 驗證
    return mode


def chip_html(key: str, label: str, tone: str) -> str:
    return f'<span class="poc-chip poc-tone-{escape(tone)}" data-status-key="{escape(key)}">{escape(label)}</span>'


def _state_card(title: str, key: str, label: str, tone: str, note: str) -> str:
    return (f'<div class="poc-card-html" data-poc-state="{escape(key)}"><h4>{escape(title)}</h4>'
            f'<div class="poc-row">{chip_html(key, label, tone)}</div><div class="poc-note">{escape(note)}</div></div>')


def render() -> None:
    mode = current_mode()
    st.markdown(css.build_css(pal.get(mode)), unsafe_allow_html=True)

    with st.sidebar:
        st.markdown("**PoC 側欄**")
        st.caption("隔離技術 PoC（非 production）；側欄用於驗證原生側欄是否可被 CSS 重新著色。")
        st.button("側欄按鈕（示範）", key="poc_sidebar_btn")

    st.title("雙模式 PoC（隔離、合成資料）")
    st.markdown(f'<div class="poc-note" data-field="synthetic_note">{escape(fx.SYNTHETIC_NOTE)}</div>', unsafe_allow_html=True)

    # ── 模式切換：唯一權威鍵 ──
    with st.container(key="poc-card-switch"):
        st.radio("顯示模式（session-only，重載後回到預設淺色）", pal.MODES, key=KEY_MODE, horizontal=True,
                 format_func=lambda m: MODE_LABELS[m])
        st.markdown(f'<div class="poc-note" data-field="mode_state">目前模式：{escape(MODE_LABELS[mode])}</div>', unsafe_allow_html=True)

    # ── 摘要卡：chips ──
    with st.container(key="poc-card-summary"):
        st.markdown("<h4>狀態 chip（符號＋字樣；顏色不是唯一訊號）</h4>", unsafe_allow_html=True)
        st.markdown('<div class="poc-row" data-field="chips">' + "".join(chip_html(k, lbl, t) for k, lbl, t in fx.CHIPS) + "</div>",
                    unsafe_allow_html=True)

    # ── 主圖卡：radio + SVG ──
    with st.container(key="poc-card-chart"):
        st.markdown("<h3>走勢（正規化，起點 = 100）</h3>", unsafe_allow_html=True)
        view = st.radio("檢視", fx.VIEWS, key=KEY_VIEW, horizontal=True)
        period = st.radio("期間", fx.PERIODS, key=KEY_PERIOD, horizontal=True, index=fx.PERIODS.index(fx.DEFAULT_PERIOD))
        if view == fx.MISSING_VIEW:
            st.markdown('<div class="poc-row" data-field="chart_missing">丙　<span class="poc-chip poc-tone-grey" data-status-key="missing">◇ 資料未備</span></div>'
                        '<div class="poc-note">沒有數值，不畫線、不補零。</div>', unsafe_allow_html=True)
        else:
            names = ("甲", "乙") if view == "比較" else ("甲",)
            dates = None
            lines = []
            for i, name in enumerate(names):
                dates, vals = fx.window(name, period)
                lines.append((name, vals, i == 1))
            st.markdown(svg.line_chart(lines, dates, title=f"合成走勢（{period}）", desc="兩條合成指數的正規化走勢，起點為 100。")
                        + svg.legend(lines), unsafe_allow_html=True)
        st.markdown(f'<div class="poc-note" data-field="chart_note">{escape(fx.SYNTHETIC_NOTE)}｜期間 {escape(period)}</div>', unsafe_allow_html=True)

    # ── 狀態示範 ──
    with st.container(key="poc-card-states"):
        st.markdown("<h4>缺資料／取數失敗／不是最新（示範）</h4>", unsafe_allow_html=True)
        st.markdown(
            _state_card("台股示範", "missing", "◇ 資料未備", "grey", "沒有數值；不畫成零、不補值。")
            + _state_card("利率示範", "failed", "⛔ 利率資料 取數失敗", "red", "請稍後重試；未取得數值。")
            + _state_card("匯率示範", "stale", "◷ 不是最新", "yellow", "資料基準日 2024-01-05（合成日期）；非當日資料。"),
            unsafe_allow_html=True)

    # ── expander ＋ disabled ──
    with st.expander("來源與限制（expander 示範）"):
        st.markdown('<div class="poc-note">本頁所有數字皆為合成示範；PoC 不取數、不連 Sheet、不使用 JS 或 browser storage。</div>', unsafe_allow_html=True)
    with st.container(key="poc-card-disabled"):
        st.radio("停用的控制項（disabled 示範）", ("選項一", "選項二"), key="poc_disabled_radio", horizontal=True, disabled=True)
        st.button("停用的按鈕（disabled 示範）", key="poc_disabled_btn", disabled=True)
        st.button("可用的按鈕（hover／focus 示範）", key="poc_enabled_btn")
