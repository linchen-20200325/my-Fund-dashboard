"""v19.198 P1-6:③ 真實收益 vs 配息率健康矩陣(從 fund_grp_health_extras 主檔抽出)。"""
from __future__ import annotations

import streamlit as st

from shared.colors import MATERIAL_GREEN, MATERIAL_ORANGE, MATERIAL_RED


def _render_dividend_matrix(funds: list) -> None:
    """③ 真實收益 vs 配息率 健康矩陣（從 tab3_portfolio L1796-1921 移植）。"""
    if not funds:
        return
    try:
        import plotly.graph_objects as go
        from ui.helpers.macro_helpers import compute_1y_total_return
    except ImportError as e:
        st.caption(f"⬜ 真實收益矩陣未渲染：{e}")
        return

    st.divider()
    st.markdown("### 📊 真實收益 vs 配息率健康矩陣")
    st.caption("長條高度 < 紅虛線 → 含息報酬不足以支撐配息 → 吃本金警示")

    _rc_names, _rc_ret, _rc_div, _rc_real, _rc_src = [], [], [], [], []
    for _f in funds:
        _mj = _f.get("moneydj_raw", {}) or {}
        _m = _f.get("metrics", {}) or {}
        _name = (_f.get("name") or _f.get("code", "?"))[:18]
        _ret_v, _src_label = compute_1y_total_return(_f)
        _is_real = _ret_v is not None
        try:
            _div = float(_mj.get("moneydj_div_yield") or _m.get("annual_div_rate") or 0)
        except (TypeError, ValueError):
            _div = 0.0
        if _div <= 0:
            _divs_f = _f.get("dividends") or []
            if _divs_f:
                try:
                    import datetime as _dt
                    _ctf = _dt.datetime.now() - _dt.timedelta(days=365)
                    _sa = 0.0
                    for _dd in _divs_f:
                        _ds = (_dd.get("date") or "").replace("/", "-")
                        try:
                            _dp = _dt.datetime.strptime(_ds[:10], "%Y-%m-%d")
                        except (ValueError, TypeError):
                            continue
                        if _dp >= _ctf:
                            _sa += float(_dd.get("amount", 0) or 0)
                    _nv = _m.get("nav") or _mj.get("nav_latest")
                    try:
                        _nv = float(_nv) if _nv is not None else None
                    except (TypeError, ValueError):
                        _nv = None
                    if _sa > 0 and _nv and _nv > 0:
                        _div = round((_sa / _nv) * 100.0, 2)
                except Exception:
                    pass
        _rc_names.append(_name)
        _rc_ret.append(round(_ret_v, 2) if _ret_v is not None else 0.0)
        _rc_div.append(round(_div, 2))
        _rc_real.append(_is_real)
        _rc_src.append(_src_label if _is_real else "資料不足")

    if not _rc_names:
        return

    _rc_colors = []
    for _r, _d, _real in zip(_rc_ret, _rc_div, _rc_real):
        if not _real:
            _rc_colors.append("#888")
        elif _d > 0 and _r < _d:
            _rc_colors.append(MATERIAL_RED)
        elif _d > 0 and _r < _d * 1.2:
            _rc_colors.append(MATERIAL_ORANGE)
        else:
            _rc_colors.append(MATERIAL_GREEN)

    fig_rc = go.Figure()
    _rc_ret_vis = [max(_r, 0.5) if (_d > 0 and _r < _d) else _r
                   for _r, _d in zip(_rc_ret, _rc_div)]
    fig_rc.add_trace(go.Bar(
        x=_rc_names, y=_rc_ret_vis,
        name="含息報酬率(1Y)%",
        marker_color=_rc_colors,
        text=[f"{v:.1f}%" for v in _rc_ret],
        textposition="outside",
        customdata=list(zip(_rc_ret, _rc_src)),
        hovertemplate=("%{x}<br>含息報酬：%{customdata[0]:.2f}%"
                       "<br>來源：%{customdata[1]}<extra></extra>")))
    if any(d > 0 for d in _rc_div):
        fig_rc.add_trace(go.Scatter(
            x=_rc_names, y=_rc_div,
            name="配息年化率%",
            mode="markers+lines",
            line=dict(color=MATERIAL_RED, width=1.5, dash="dot"),
            marker=dict(symbol="diamond", size=8, color=MATERIAL_RED),
            hovertemplate="%{x}<br>配息率：%{y:.2f}%<extra></extra>"))
    fig_rc.add_hline(y=0, line_color="#555", line_width=1)
    _y_max = max(max(_rc_ret_vis, default=10), max(_rc_div, default=10)) * 1.35
    for _i, (_r, _d, _n, _real) in enumerate(
        zip(_rc_ret, _rc_div, _rc_names, _rc_real)
    ):
        if _real and _d > 0 and _r < _d:
            fig_rc.add_vrect(
                x0=_i - 0.45, x1=_i + 0.45,
                fillcolor="rgba(244,67,54,0.08)",
                line_color="rgba(244,67,54,0.4)", line_width=1,
                layer="below")
            fig_rc.add_annotation(
                x=_n, y=_y_max,
                text=f"⚠️ 吃本金<br>缺口 {_d-_r:.1f}%",
                showarrow=False,
                font=dict(color=MATERIAL_RED, size=11),
                bgcolor="rgba(42,10,10,0.85)",
                bordercolor=MATERIAL_RED, borderwidth=1,
                borderpad=4)
        elif not _real and _d > 0:
            fig_rc.add_annotation(
                x=_n, y=_y_max,
                text="⬜ 1Y 資料不足<br>無法判定",
                showarrow=False,
                font=dict(color="#aaa", size=10),
                bgcolor="rgba(60,60,60,0.7)",
                bordercolor="#666", borderwidth=1,
                borderpad=4)
    fig_rc.update_layout(
        paper_bgcolor="#0e1117", plot_bgcolor="#161b22",
        font_color="#e6edf3", height=360,
        margin=dict(t=40, b=20, l=40, r=20),
        legend=dict(orientation="h", font_size=10, y=1.08),
        yaxis_title="報酬率 / 配息率 (%)",
        yaxis=dict(range=[min(0, min(_rc_ret, default=0)) - 2, _y_max]),
        bargap=0.35, hovermode="x unified")
    st.plotly_chart(fig_rc, use_container_width=True)

