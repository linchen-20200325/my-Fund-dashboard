"""v19.198 P1-6:⑥ 持股/產業相關性矩陣(從 fund_grp_health_extras 主檔抽出)。

v19.289:NAV 漲跌幅 Pearson 相關係數矩陣從「持股資料全缺時的 fallback」
升級為「恆算的第二面板」——持股重疊(jaccard/cosine)與走勢同步(NAV 相關
係數)是兩種不同意義的曝險,即使兩檔基金持股完全不同,若同受單一總經
因子驅動,回撤時仍會齊跌,值得獨立顯示、獨立判定,不合併成單一分數。
"""
from __future__ import annotations

import streamlit as st

from shared.colors import BG_DARK_RED_1, GH_FG_PRIMARY, MATERIAL_RED, MD_BLUE_500, STREAMLIT_BG, TRAFFIC_NEUTRAL
from shared.signal_thresholds import SHADOW_FUND_NAV_CORR_THRESHOLD_RATIO, SHADOW_FUND_THRESHOLD_RATIO


def _render_one_matrix(*, title: str, subtitle: str, result: "dict | None",
                        threshold: float, label: str, empty_caption: str) -> None:
    """單一矩陣面板(熱力圖 + 影子基金警示列表)的共用渲染邏輯(SSOT,兩面板共用)。"""
    st.markdown(f"#### {title}")
    st.caption(subtitle)

    if not result or result.get("matrix") is None:
        st.caption(empty_caption)
        return

    _shadow = result.get("shadow_pairs", []) or []

    try:
        import plotly.graph_objects as go
        _mx = result["matrix"]
        fig = go.Figure(data=go.Heatmap(
            z=_mx.values,
            x=list(_mx.columns),
            y=list(_mx.index),
            colorscale=[[0, STREAMLIT_BG], [0.5, MD_BLUE_500], [1, MATERIAL_RED]],
            zmin=0, zmax=1,
            text=[[f"{v:.2f}" for v in row] for row in _mx.values],
            texttemplate="%{text}",
            textfont={"size": 11, "color": "white"},
            hovertemplate="%{y} vs %{x}<br>" + label + ":%{z:.3f}<extra></extra>",
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

    if _shadow:
        st.markdown(f"**⚠️ 偵測到 {len(_shadow)} 對影子基金({label} ≥ {threshold})**")
        for _pair in _shadow:
            _a, _b, _score = _pair[0], _pair[1], _pair[2]
            st.markdown(
                f"<div style='background:{BG_DARK_RED_1};border-left:3px solid {MATERIAL_RED};"
                f"padding:6px 12px;margin:4px 0;border-radius:4px;'>"
                f"<b>{_a} ⟷ {_b}</b>　"
                f"<span style='color:{MATERIAL_RED};font-weight:700'>"
                f"{label} {_score:.3f}</span>　"
                f"<span style='color:{TRAFFIC_NEUTRAL};font-size:11px'>建議檢視是否該擇一持有</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
    else:
        st.success(f"✅ 本組合無影子基金({label} 皆 < {threshold})")


def _render_correlation_matrix(funds: list) -> None:
    """⑥ 持股/產業相關性矩陣 + 漲跌幅相關係數矩陣(兩個獨立面板)。

    面板 1:Jaccard(持股)×0.6 + Cosine(產業)×0.4,score ≥ 0.70 警示(持股重疊曝險)
    面板 2(v19.289 起恆算,不再只是面板 1 缺資料時的 fallback):
        NAV Pearson 漲跌幅相關係數,|r| ≥ 0.85 警示(走勢同步曝險)
    兩者意義不同,各自獨立判定、獨立顯示,不合併成單一分數。
    SSOT:services/portfolio_service.py + shared/signal_thresholds.py

    §1 Fail Loud:< 2 檔基金 → skip;任一來源資料不足 → 該面板顯示 caption 說明,
    不影響另一面板照常渲染。
    """
    if len(funds) < 2:
        st.divider()
        st.markdown("### 🔗 持股/產業相關性矩陣")
        st.caption("⬜ 至少需 2 檔基金才能計算相關性")
        return

    st.divider()
    st.markdown("### 🔗 基金相關性矩陣(持股重疊 + 漲跌幅同步,兩個獨立維度)")

    try:
        from services.portfolio_service import (
            calc_correlation_matrix,
            calc_holdings_overlap,
        )
    except Exception as e:
        st.caption(f"⬜ 相關性模組載入失敗:{type(e).__name__}: {e}")
        return

    # ── 面板 1:持股 Jaccard + 產業 Cosine ──
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
    _hov_result = calc_holdings_overlap(_hov_input)
    if _hov_result and _hov_result.get("matrix") is not None:
        _method = _hov_result.get("method", "?")
        _notes = _hov_result.get("notes", "")
        st.info(f"📌 面板 1 計算方式:**{_method}**({_notes})")
    _render_one_matrix(
        title="🏭 持股/產業相關性矩陣",
        subtitle="Jaccard(持股)×0.6 + Cosine(產業)×0.4;**重疊度 ≥ 0.70 = 影子基金警告**(隱性重複曝險)",
        result=_hov_result,
        threshold=SHADOW_FUND_THRESHOLD_RATIO,
        label="重疊度",
        empty_caption="⬜ 相關性計算失敗(持股 + 產業資料皆缺)",
    )

    # ── 面板 2(v19.289):NAV 漲跌幅 Pearson 相關係數,恆算 ──
    st.markdown("")
    _corr_input = [
        {"code": _f.get("code", "?"), "series": _f.get("series")}
        for _f in funds
    ]
    _corr_result = calc_correlation_matrix(_corr_input)
    if _corr_result and _corr_result.get("matrix") is not None:
        _freq = _corr_result.get("freq", "?")
        st.info(f"📌 面板 2 計算方式:NAV Pearson 相關係數({_freq}頻,自適應月→週→日)")
    _render_one_matrix(
        title="📈 淨值漲跌幅相關係數矩陣",
        subtitle="NAV 報酬 Pearson 相關係數(自適應月/週/日頻);**|r| ≥ 0.85 = 影子基金警告**(走勢同步曝險,即使持股不同)",
        result=_corr_result,
        threshold=SHADOW_FUND_NAV_CORR_THRESHOLD_RATIO,
        label="相關係數",
        empty_caption="⬜ 漲跌幅相關係數計算失敗(NAV 資料不足,需 ≥30 筆且共同交易日 ≥2)",
    )
