"""v19.198 P1-6:⑥ 持股/產業相關性矩陣(從 fund_grp_health_extras 主檔抽出)。"""
from __future__ import annotations

import streamlit as st

from shared.colors import BG_DARK_RED_1, GH_FG_PRIMARY, MATERIAL_RED, MD_BLUE_500, STREAMLIT_BG, TRAFFIC_NEUTRAL


def _render_correlation_matrix(funds: list) -> None:
    """⑥ 持股/產業相關性矩陣(N×N 熱力圖 + 影子基金警示)。

    主算法:Jaccard(持股)×0.6 + Cosine(產業)×0.4,score ≥ 0.70 警示
    Fallback:NAV Pearson(持股資料缺時),> 0.85 警示
    SSOT:services/portfolio_service.py + shared/signal_thresholds.py

    §1 Fail Loud:< 2 檔基金 → skip;持股全缺 → fallback;Pearson 失敗 → caption error
    """
    if len(funds) < 2:
        st.divider()
        st.markdown("### 🔗 持股/產業相關性矩陣")
        st.caption("⬜ 至少需 2 檔基金才能計算相關性")
        return

    st.divider()
    st.markdown("### 🔗 持股/產業相關性矩陣")
    st.caption("Jaccard(持股)×0.6 + Cosine(產業)×0.4;**重疊度 ≥ 0.70 = 影子基金警告**(隱性重複曝險)")

    try:
        from services.portfolio_service import (
            calc_correlation_matrix,
            calc_holdings_overlap,
        )
    except Exception as e:
        st.caption(f"⬜ 相關性模組載入失敗:{type(e).__name__}: {e}")
        return

    # 主算法:Jaccard + Cosine(需持股 + 產業資料)
    _hov_input = []
    for _f in funds:
        _mj = _f.get("moneydj_raw") or {}
        _h = _mj.get("holdings") or {}
        _hov_input.append({
            "code": _f.get("code", "?"),
            "name": _f.get("name") or _f.get("code"),
            "top_holdings": _h.get("top_holdings") or [],
            "sector_alloc": _h.get("sector_alloc") or [],
        })
    _result = calc_holdings_overlap(_hov_input)

    # Fallback:持股全缺 → NAV Pearson
    _is_fallback = False
    if (not _result) or _result.get("method") == "n/a":
        _corr_input = [
            {"code": _f.get("code", "?"), "series": _f.get("series")}
            for _f in funds
        ]
        _result = calc_correlation_matrix(_corr_input)
        if _result is not None:
            _result.setdefault("method", "nav_fallback")
            _is_fallback = True
            _result.setdefault(
                "notes",
                f"持股/產業資料皆缺,降級為 NAV Pearson 相關({_result.get('freq', '?')}頻;"
                f">= 0.85 為 shadow)",
            )

    if not _result or _result.get("matrix") is None:
        st.caption("⬜ 相關性計算失敗(持股 + NAV 兩源都缺)")
        return

    _method = _result.get("method", "?")
    _notes = _result.get("notes", "")
    _shadow = _result.get("shadow_pairs", []) or []
    _thr = 0.85 if _is_fallback else 0.70
    _label = "相關係數" if _is_fallback else "重疊度"
    st.info(f"📌 計算方式:**{_method}**({_notes})")

    # 熱力圖
    try:
        import plotly.graph_objects as go
        _mx = _result["matrix"]
        fig = go.Figure(data=go.Heatmap(
            z=_mx.values,
            x=list(_mx.columns),
            y=list(_mx.index),
            colorscale=[[0, STREAMLIT_BG], [0.5, MD_BLUE_500], [1, "#f44336"]],
            zmin=0, zmax=1,
            text=[[f"{v:.2f}" for v in row] for row in _mx.values],
            texttemplate="%{text}",
            textfont={"size": 11, "color": "white"},
            hovertemplate="%{y} vs %{x}<br>" + _label + ":%{z:.3f}<extra></extra>",
        ))
        fig.update_layout(
            paper_bgcolor=STREAMLIT_BG, plot_bgcolor=STREAMLIT_BG,
            font_color=GH_FG_PRIMARY,
            height=max(280, len(_mx) * 50 + 100),
            margin=dict(t=20, b=20, l=80, r=20),
        )
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.caption(f"⬜ 熱力圖渲染失敗:{type(e).__name__}: {e}")

    # 影子基金警示列表
    if _shadow:
        st.markdown(f"#### ⚠️ 偵測到 {len(_shadow)} 對影子基金({_label} ≥ {_thr})")
        for _pair in _shadow:
            _a, _b, _score = _pair[0], _pair[1], _pair[2]
            st.markdown(
                f"<div style='background:{BG_DARK_RED_1};border-left:3px solid {MATERIAL_RED};"
                f"padding:6px 12px;margin:4px 0;border-radius:4px;'>"
                f"<b>{_a} ⟷ {_b}</b>　"
                f"<span style='color:{MATERIAL_RED};font-weight:700'>"
                f"{_label} {_score:.3f}</span>　"
                f"<span style='color:{TRAFFIC_NEUTRAL};font-size:11px'>建議檢視是否該擇一持有</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
    else:
        st.success(f"✅ 本組合無影子基金({_label} 皆 < {_thr})")
