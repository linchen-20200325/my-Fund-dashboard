# -*- coding: utf-8 -*-
"""B 線共用 presentation primitives 的 Streamlit 畫法（BL-0525 Batch A；模型與字面在 `ui_v2/presentation.py`）。

三個函式，都**只畫呼叫端交來的模型**，不決定資料語意：

- `render_detail(detail, *, nested=False)`：「▸ 為什麼‧來源‧限制‧去哪補」。預設收合的 `st.expander`；
  `nested=True`（呼叫端已在另一枚展開區裡面，Streamlit 不允許巢狀展開區、44 之十九其六）時改畫純區塊，
  內容照樣完整保留 —— 它本來就在已收合的外層裡。
- `render_chart_card(model, *, draw_chart, nested=False)`：容器＋標題／chips／一句摘要 → **圖表（外露，由 `draw_chart()` 畫）** → detail。
  圖表絕不放進展開區，也不被長說明推到首屏以下（摘要至多一句由模型保證）。
- `render_missing_placeholder(model, *, nested=False)`：卡＋`◇ 資料未備` chip＋一句短原因＋detail。

⛔ 本檔**沒有被任何頁面呼叫**（頁面套用屬 Batch C～F）；加進頁面之前，不改變任何畫面。
"""

from __future__ import annotations

import streamlit as st

from ui_v2 import presentation


def _inject_css() -> None:
    st.markdown(f"<style>{presentation.PRESENTATION_CSS}</style>", unsafe_allow_html=True)


def render_detail(detail: dict, *, nested: bool = False) -> None:
    """畫 detail。沒有任何一組有內容 → 什麼都不畫（不為了有展開區而放空殼）。"""
    if not detail["groups"]:
        return
    body = presentation.detail_html(detail)
    if nested:
        st.markdown(f'<div class="pc-detail-nested">{body}</div>', unsafe_allow_html=True)
        return
    with st.expander(detail["title"], expanded=False):
        st.markdown(body, unsafe_allow_html=True)


def render_chart_card(model: dict, *, draw_chart, nested: bool = False) -> None:
    """畫圖卡。`draw_chart`：不帶參數的 callable，在卡內、detail 之前畫圖（例：`lambda: st.vega_lite_chart(spec, width="stretch")`）。"""
    if model.get("kind") != "chart_card":
        raise ValueError(f"不是圖卡模型：{model.get('kind')!r}")
    if not callable(draw_chart):
        raise ValueError("draw_chart 必須是可呼叫的")
    _inject_css()
    with st.container(border=True):
        st.markdown(presentation.chart_card_head_html(model), unsafe_allow_html=True)
        draw_chart()
        render_detail(model["detail"], nested=nested)


def render_missing_placeholder(model: dict, *, nested: bool = False) -> None:
    if model.get("kind") != "missing":
        raise ValueError(f"不是 Missing 模型：{model.get('kind')!r}")
    _inject_css()
    with st.container(border=True):
        st.markdown(presentation.missing_card_html(model), unsafe_allow_html=True)
        render_detail(model["detail"], nested=nested)
