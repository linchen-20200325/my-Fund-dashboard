"""v19.198 P1-6:③ 真實收益 vs 配息率健康矩陣(從 fund_grp_health_extras 主檔抽出)。"""
from __future__ import annotations

import streamlit as st

from ui.helpers.render_state import system_error

from shared.colors import GH_BG_CARD, GH_FG_PRIMARY, GRAY_55, GRAY_66, GRAY_AA, MATERIAL_GREEN, MATERIAL_ORANGE, MATERIAL_RED, STREAMLIT_BG, TRAFFIC_NEUTRAL


def _render_dividend_matrix(funds: list) -> None:
    """③ 真實收益 vs 配息率 健康矩陣（從 tab3_portfolio L1796-1921 移植）。"""
    if not funds:
        return
    try:
        import plotly.graph_objects as go
        from ui.helpers.macro_helpers import compute_1y_total_return
    except ImportError as e:
        system_error("真實收益矩陣模組載入失敗", e)
        return

    st.divider()
    st.markdown("### 📊 真實收益 vs 配息率健康矩陣")
    st.caption("長條高度 < 紅虛線 → 含息報酬不足以支撐配息 → 吃本金警示。"
               "**抓不到的值一律留缺口**(柱子不畫、紅點斷線),與「真的是 0%」分得出來。")

    # v19.177 SSOT:年化配息率走 `_resolve_adr_with_fallback`(wb05 → metrics → 12M 推算),
    # 取代本檔原本自己抄一份的 12M fallback(第 3 份 inline 實作,且用 `except: pass` 吞錯)。
    from services.health.dividend import _resolve_adr_with_fallback

    _rc_names, _rc_ret, _rc_div, _rc_real, _rc_src = [], [], [], [], []
    for _f in funds:
        _name = (_f.get("name") or _f.get("code", "?"))[:18]
        _ret_v, _src_label = compute_1y_total_return(_f)
        _is_real = _ret_v is not None
        try:
            _div, _ = _resolve_adr_with_fallback(_f)
        except Exception as _e_adr:  # noqa: BLE001 — 單檔配息率算爆 → 留 None + log,不冒充 0%
            import sys as _sys_adr
            print(f"[grp_health/dividend] {_f.get('code', '?')} adr 解析失敗:"
                  f"{type(_e_adr).__name__}: {_e_adr}", file=_sys_adr.stderr)
            _div = None
        _rc_names.append(_name)
        # §1:抓不到 ≠ 0%。原本 `_ret_v or 0.0` 讓「1Y 抓不到」畫成 0 高柱並在柱上印
        # 「0.0%」,與真的持平 0% 完全同形;配息率同理(0 會讓整條紅虛線消失,
        # 「沒抓到」與「這檔不配息」看起來一樣)。改為保留 None → Plotly 留缺口。
        _rc_ret.append(round(_ret_v, 2) if _ret_v is not None else None)
        _rc_div.append(round(_div, 2) if _div is not None else None)
        _rc_real.append(_is_real)
        _rc_src.append(_src_label if _is_real else "資料不足")

    if not _rc_names:
        return

    # v19.402 §1:改走 SSOT dividend_safety(gap 判定),取代 inline 1.2× coverage
    # 門檻 → 與 tab3_portfolio canonical 版 + 全站一致(L3→L2,修 §8.2 inline 分類)。
    from services.fund_total_return import is_extrapolated_1y_source
    from services.portfolio_service import dividend_safety
    _LVL_COLOR = {"red": MATERIAL_RED, "yellow": MATERIAL_ORANGE,
                  "green": MATERIAL_GREEN, "grey": TRAFFIC_NEUTRAL}
    _rc_levels = []
    for _r, _d, _real, _src in zip(_rc_ret, _rc_div, _rc_real, _rc_src):
        # v19.448 稽核:缺含息報酬 **或** 缺配息率 **或** 含息報酬走「短窗外推年化」
        # (最不可靠、外推爆掉,ACTI71 −38% bug)→ 一律無法判定,灰。
        # 不拿外推數字報紅燈(§1)。純淨值(源#3)雙扣議題待 user 核准另處理。
        if not _real or _d is None or is_extrapolated_1y_source(_src):
            _rc_levels.append("grey")
        else:
            _rc_levels.append(
                dividend_safety(_r, _d).get("alert_level", "grey"))
    _rc_colors = [_LVL_COLOR.get(_lv, TRAFFIC_NEUTRAL) for _lv in _rc_levels]

    fig_rc = go.Figure()
    # v19.394 V3 §1:含息報酬長條用真實值 _rc_ret(移除 max(_r,0.5) 地板 ——
    # 原本把吃本金的負報酬硬拉成正向長條、標籤卻標真負值,視覺與數據矛盾;
    # 與 tab3_portfolio.py:2245 canonical 版對齊)。負報酬向下、以 0 基準線呈現;
    # 顏色 _rc_colors 已把吃本金標紅。
    fig_rc.add_trace(go.Bar(
        x=_rc_names, y=_rc_ret,
        name="含息報酬率(1Y)%",
        marker_color=_rc_colors,
        # §1:None → 空字串,**不印 0.0%**(那讓「抓不到」與「真的持平」完全同形)。
        text=[(f"{v:.1f}%" if v is not None else "") for v in _rc_ret],
        textposition="outside",
        customdata=list(zip([("⬜ 無資料" if v is None else f"{v:.2f}%") for v in _rc_ret],
                            _rc_src)),
        hovertemplate=("%{x}<br>含息報酬：%{customdata[0]}"
                       "<br>來源：%{customdata[1]}<extra></extra>")))
    if any(d is not None and d > 0 for d in _rc_div):
        fig_rc.add_trace(go.Scatter(
            x=_rc_names, y=_rc_div,
            name="配息年化率%",
            mode="markers+lines",
            line=dict(color=MATERIAL_RED, width=1.5, dash="dot"),
            marker=dict(symbol="diamond", size=8, color=MATERIAL_RED),
            connectgaps=False,   # 缺配息率 → 斷線,不把兩端接起來偽造中間值
            hovertemplate="%{x}<br>配息率：%{y:.2f}%<extra></extra>"))
    fig_rc.add_hline(y=0, line_color=GRAY_55, line_width=1)
    _nz_ret = [v for v in _rc_ret if v is not None]
    _nz_div = [v for v in _rc_div if v is not None]
    _y_max = max(max(_nz_ret, default=10), max(_nz_div, default=10)) * 1.35
    for _i, (_r, _d, _n, _real, _lv) in enumerate(
        zip(_rc_ret, _rc_div, _rc_names, _rc_real, _rc_levels)
    ):
        if _lv == "red":
            fig_rc.add_vrect(
                x0=_i - 0.45, x1=_i + 0.45,
                fillcolor="rgba(244,67,54,0.08)",
                line_color="rgba(244,67,54,0.4)", line_width=1,
                layer="below")
            fig_rc.add_annotation(
                x=_n, y=_y_max,
                text=f"⚠️ 吃本金<br>缺口 {_d-_r:.1f}%",   # red 分支保證兩者皆非 None
                showarrow=False,
                font=dict(color=MATERIAL_RED, size=11),
                bgcolor="rgba(42,10,10,0.85)",
                bordercolor=MATERIAL_RED, borderwidth=1,
                borderpad=4)
        elif not _real or _d is None:
            # 原本註記只在「配息率 > 0」時才加 —— 配息率也缺的那批(最沒資料的一群)
            # 反而完全沒提示,柱子是灰的但沒人知道為什麼。改為兩邊任一缺就標,
            # 並講清楚缺的是哪一邊(§1 缺料要當場說明白)。
            _miss = "1Y 含息 + 配息率" if (not _real and _d is None) else (
                "1Y 含息" if not _real else "配息率")
            fig_rc.add_annotation(
                x=_n, y=_y_max,
                text=f"⬜ 缺 {_miss}<br>無法判定",
                showarrow=False,
                font=dict(color=GRAY_AA, size=10),
                bgcolor="rgba(60,60,60,0.7)",
                bordercolor=GRAY_66, borderwidth=1,
                borderpad=4)
    fig_rc.update_layout(
        paper_bgcolor=STREAMLIT_BG, plot_bgcolor=GH_BG_CARD,
        font_color=GH_FG_PRIMARY, height=360,
        margin=dict(t=40, b=20, l=40, r=20),
        legend=dict(orientation="h", font_size=10, y=1.08),
        yaxis_title="報酬率 / 配息率 (%)",
        yaxis=dict(range=[min(0, min(_nz_ret, default=0)) - 2, _y_max]),
        bargap=0.35, hovermode="x unified")
    st.plotly_chart(fig_rc, use_container_width=True)
    _n_missing = sum(1 for _r, _d in zip(_rc_ret, _rc_div)
                     if _r is None or _d is None)
    if _n_missing:
        st.caption(
            f"⬜ 其中 **{_n_missing} 檔**缺 1Y 含息報酬或年化配息率 → 該柱 / 該紅點"
            "**留缺口不畫**(不是 0%),吃本金燈號一律灰色不判定。"
        )
