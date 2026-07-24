"""ui/components/chart_factory.py — Plotly 圖表統一 dark 版面工廠 (v19.388 V2)。

收斂目標(可視化稽核 ⑤ 系統級去重):原 22 張圖各自 inline `update_layout`,漂移出
5 種背景配方 / ~20 種 margin / 18 種高度 / font+modebar 不一致,且 `template` 0/22。
本檔提供**單一 dark 版面** + 高度/邊距尺標 + `apply_dark_template()`:呼叫端建完 traces
後套一次即可(V3 逐 Tab 接線)。顏色一律走 `shared.colors`;缺值一律留缺口(§1,不補 0)。

用法:
    fig = go.Figure(); fig.add_trace(...)
    apply_dark_template(fig, height="standard")
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
"""
from __future__ import annotations

import math

import plotly.graph_objects as go

from shared.colors import (
    GH_BG_CARD,
    GH_BORDER,
    GH_FG_MUTED,
    GH_FG_PRIMARY,
    INFO_BLUE,
    TRAFFIC_GREEN,
    TRAFFIC_NEUTRAL,
    TRAFFIC_RED,
)

# 高度尺標(取代原 18 種散值)
HEIGHTS = {"spark": 80, "compact": 140, "standard": 280, "tall": 360}
# 邊距尺標(取代原 ~20 種 dict)
MARGINS = {
    "tight":  dict(t=8,  b=8,  l=8,  r=8),
    "normal": dict(t=40, b=30, l=48, r=20),
    "spark":  dict(t=4,  b=4,  l=4,  r=4),
}
# st.plotly_chart(config=...) 統一政策:不顯示 modebar
PLOTLY_CONFIG = {"displayModeBar": False}


def _resolve(scale: dict, key, fallback):
    if key is None:
        return fallback
    if isinstance(key, str):
        return scale.get(key, fallback)
    return key  # 已是數值 / dict


def apply_dark_template(fig: go.Figure, *, height=None, margin: str = "normal",
                        legend: bool = True, x_unified: bool = True) -> go.Figure:
    """對已建好 traces 的 fig 套用統一 dark 版面(單一背景 / font / 軸樣式)。回傳同一 fig。

    height : "spark"/"compact"/"standard"/"tall" 或數值 px(None = 不設,交 Streamlit)。
    margin : "tight"/"normal"/"spark" 或 dict。
    legend : 是否顯示圖例(≥2 系列才需;單系列傳 False)。
    x_unified : 時序圖 crosshair(line/area 建議 True;bar/dot 傳 False)。
    """
    layout = dict(
        paper_bgcolor=GH_BG_CARD, plot_bgcolor=GH_BG_CARD,
        font=dict(color=GH_FG_PRIMARY, size=12),
        margin=_resolve(MARGINS, margin, MARGINS["normal"]),
        hovermode=("x unified" if x_unified else "closest"),
        showlegend=legend,
    )
    h = _resolve(HEIGHTS, height, None)
    if h is not None:
        layout["height"] = h
    if legend:
        layout["legend"] = dict(orientation="h", yanchor="bottom", y=1.02, x=0,
                                font=dict(color=GH_FG_MUTED, size=11))
    fig.update_layout(**layout)
    _axis = dict(gridcolor=GH_BORDER, zerolinecolor=GH_BORDER, linecolor=GH_BORDER,
                 tickfont=dict(color=GH_FG_MUTED, size=10))
    fig.update_xaxes(**_axis)
    fig.update_yaxes(**_axis)
    return fig


def sparkline_fig(y, x=None, *, color: str = INFO_BLUE) -> go.Figure:
    """極簡 sparkline(透明底、無軸、無 legend、單系列)。取代 3 份重複 sparkline 實作。"""
    fig = go.Figure(go.Scatter(
        y=list(y), x=(list(x) if x is not None else None),
        mode="lines", line=dict(color=color, width=2),
        hovertemplate="%{y:.2f}<extra></extra>"))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        height=HEIGHTS["spark"], margin=MARGINS["spark"], showlegend=False,
        xaxis=dict(visible=False), yaxis=dict(visible=False))
    return fig


def signed_bar_fig(x, y, *, height: str = "standard") -> go.Figure:
    """依號上色長條(正=綠 / 負=紅);**缺值(None)留缺口不補 0**(§1)。0 基準線。

    取代 Tab3 含息報酬圖等「負值造假 / 手動地板」的一次性寫法。
    """
    def _gap(v):  # None 與 pandas NaN 都視為缺口(V3 接真實 df 時 NaN 才不會被誤上紅色)
        return v is None or (isinstance(v, float) and math.isnan(v))
    colors = [TRAFFIC_NEUTRAL if _gap(v) else (TRAFFIC_GREEN if v >= 0 else TRAFFIC_RED)
              for v in y]
    fig = go.Figure(go.Bar(
        x=list(x), y=list(y), marker_color=colors,
        hovertemplate="%{x}: %{y:.2f}<extra></extra>"))
    fig.add_hline(y=0, line_color=GH_BORDER, line_width=1)
    return apply_dark_template(fig, height=height, x_unified=False, legend=False)
