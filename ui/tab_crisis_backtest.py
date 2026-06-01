"""tab_crisis_backtest.py — 📉 危機回測室 (v18.260, Phase 2 UI)

User 需求第 2 階段：在新 Tab 顯示歷史危機事件清單 + 該基金當時跌幅對照。
資料引擎在 services/crisis_backtest.py（Phase 1 已 merged）。

本檔職能：純 UI/呈現層
- 4 input：market / threshold / years / fund override
- 跑 summarize_events_with_fund → 顯示
- 大盤走勢 plotly 圖（紅色 shaded crisis 區）
- 事件清單 DataFrame + 統計卡片
"""
from __future__ import annotations

import pandas as pd
import streamlit as st


def _format_pct(x: float | None) -> str:
    if x is None or pd.isna(x):
        return "—"
    return f"{x:+.1%}"


def _format_event_name(peak_date_str: str | None) -> str:
    """從 peak_date YYYY-MM-DD 抓年份當事件編號。"""
    if not peak_date_str:
        return "—"
    try:
        return peak_date_str[:7]  # YYYY-MM
    except Exception:
        return peak_date_str


def _events_to_dataframe(events: list, market_label: str) -> pd.DataFrame:
    """事件清單 → 顯示用 DataFrame。"""
    rows = []
    for ev in events:
        d = ev.to_dict()
        rows.append({
            "事件期": _format_event_name(d["peak_date"]),
            "市場": market_label,
            "高點日": d["peak_date"],
            "低點日": d["trough_date"],
            "回升日": d["recovery_date"] or "尚未回升",
            "大盤跌幅": _format_pct(d["drawdown_pct"]),
            "下跌天數": d["duration_days"],
            "回升天數": d["recovery_days"] if d["recovery_days"] is not None else "—",
            "該基金跌幅": _format_pct(d["fund_drawdown_pct"]),
            "該基金反彈": _format_pct(d["fund_recovery_pct"]),
        })
    return pd.DataFrame(rows)


def _plot_market_with_crises(series: pd.Series, events: list, market_label: str):
    """plotly 走勢圖 + 紅色 shaded 危機區。"""
    try:
        import plotly.graph_objects as go
    except ImportError:
        st.warning("plotly 未安裝，無法顯示走勢圖")
        return

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=series.index,
        y=series.values,
        mode="lines",
        name=market_label,
        line=dict(color="#1f77b4", width=1.2),
    ))

    for ev in events:
        d = ev.to_dict()
        x0 = d["peak_date"]
        x1 = d["recovery_date"] or d["trough_date"]
        fig.add_vrect(
            x0=x0, x1=x1,
            fillcolor="red", opacity=0.15,
            line_width=0,
            annotation_text=f"{_format_event_name(d['peak_date'])} ({d['drawdown_pct']:+.1%})",
            annotation_position="top left",
            annotation=dict(font_size=10),
        )

    fig.update_layout(
        title=f"{market_label} 歷史走勢與危機事件",
        xaxis_title="日期",
        yaxis_title="收盤價",
        height=420,
        hovermode="x unified",
        margin=dict(l=10, r=10, t=50, b=10),
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_summary_metrics(events: list):
    """事件統計卡片：總數 / 平均跌幅 / 最深跌幅 / 平均回升天數。"""
    n = len(events)
    if n == 0:
        st.info("此門檻下未偵測到危機事件，可嘗試降低門檻（例如 -5%）。")
        return

    dds = [ev.drawdown_pct for ev in events]
    avg_dd = sum(dds) / n
    worst_dd = min(dds)
    recovery_days = [ev.recovery_days for ev in events if ev.recovery_days is not None]
    avg_rec = sum(recovery_days) / len(recovery_days) if recovery_days else None

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("危機事件數", f"{n}")
    c2.metric("平均跌幅", f"{avg_dd:+.1%}")
    c3.metric("最深跌幅", f"{worst_dd:+.1%}")
    c4.metric("平均回升天數", f"{int(avg_rec)}" if avg_rec else "—")


def _render_fund_dd_metrics(events: list, fund_name: str):
    """該基金統計卡片。"""
    fund_dds = [ev.fund_drawdown_pct for ev in events if ev.fund_drawdown_pct is not None]
    if not fund_dds:
        st.caption(f"⚠️ 該基金 NAV 不涵蓋任何危機事件期間（基金 NAV 通常只有近 ~400 天）")
        return

    fund_recs = [ev.fund_recovery_pct for ev in events if ev.fund_recovery_pct is not None]
    avg_dd = sum(fund_dds) / len(fund_dds)
    worst_dd = min(fund_dds)

    c1, c2, c3 = st.columns(3)
    c1.metric(f"📦 {fund_name} 涵蓋事件", f"{len(fund_dds)}")
    c2.metric("該基金平均跌幅", f"{avg_dd:+.1%}")
    c3.metric("該基金最深跌幅", f"{worst_dd:+.1%}")

    if fund_recs:
        avg_rec = sum(fund_recs) / len(fund_recs)
        st.caption(f"📈 該基金在這些事件後平均反彈 {avg_rec:+.1%}")


def render_crisis_backtest_tab() -> None:
    """主入口：📉 危機回測室 Tab。"""
    st.markdown("## 📉 危機回測室")
    st.caption(
        "回看歷史大盤崩盤事件，量化該基金在每次危機中的真實跌幅。"
        "🚧 Phase 2 — 後續會加上總經訊號預測力驗證、策略 grid_search、AI 建議。"
    )

    # ── Input row ──────────────────────────────────
    col1, col2, col3 = st.columns([1, 1.2, 1.2])
    with col1:
        market = st.radio(
            "市場",
            options=["SPX", "TWII"],
            horizontal=True,
            help="SPX = 美股 S&P 500；TWII = 台股加權",
            key="crisis_market",
        )
    with col2:
        threshold_pct = st.slider(
            "危機門檻（跌幅%）",
            min_value=-30, max_value=-5, value=-10, step=1,
            help="MaxDD ≥ 此門檻才算危機事件",
            key="crisis_threshold",
        )
    with col3:
        years = st.slider(
            "回看年數",
            min_value=3, max_value=20, value=10, step=1,
            key="crisis_years",
        )

    # ── 取使用者已選基金 ──────────────────────────────
    fund_data = st.session_state.get("fund_data") or {}
    default_key = fund_data.get("full_key") or ""
    default_name = fund_data.get("fund_name") or ""

    fund_key = st.text_input(
        "基金代號（full_key）",
        value=default_key,
        placeholder="例如：00940 / 富蘭克林坦伯頓全球...",
        help="預設帶入 Tab『🔍 單一基金』中已選的基金；可手動改",
        key="crisis_fund_key",
    )

    run = st.button("🚀 開始回測", type="primary", use_container_width=True)
    if not run:
        st.info("⬆️ 設定參數後按「開始回測」")
        return

    # ── 抓資料 ─────────────────────────────────────
    market_label = {"SPX": "S&P 500", "TWII": "台股加權"}[market]

    with st.spinner(f"抓取 {market_label} {years} 年走勢..."):
        from services.crisis_backtest import (
            fetch_market_series,
            summarize_events_with_fund,
        )
        mkt_series = fetch_market_series(market=market, years=years)

    if mkt_series.empty:
        st.error(f"❌ 無法取得 {market_label} 歷史資料（NAS proxy / Yahoo API 失敗）")
        return

    # 抓基金 NAV（可選）
    fund_nav: pd.Series | None = None
    fund_display_name = default_name or "(未指定基金)"
    if fund_key.strip():
        with st.spinner(f"抓取基金 {fund_key} NAV..."):
            try:
                from repositories.fund_repository import fetch_nav
                fund_nav = fetch_nav(fund_key.strip())
                if fund_nav is None or fund_nav.empty:
                    st.warning(f"⚠️ 基金 `{fund_key}` 取不到 NAV，僅顯示大盤事件")
                    fund_nav = None
                else:
                    fund_display_name = default_name or fund_key
            except Exception as e:
                st.warning(f"⚠️ 基金 NAV 抓取失敗：{e}")
                fund_nav = None

    # ── 跑引擎 ─────────────────────────────────────
    threshold = threshold_pct / 100.0
    events = summarize_events_with_fund(
        market_series=mkt_series,
        fund_nav=fund_nav,
        threshold=threshold,
        market=market,
    )

    # ── 呈現 ───────────────────────────────────────
    st.divider()
    st.markdown(f"### 📊 {market_label} 危機事件總覽（門檻 {threshold_pct}% / 回看 {years} 年）")
    _render_summary_metrics(events)

    if fund_nav is not None and events:
        st.markdown("---")
        _render_fund_dd_metrics(events, fund_display_name)

    if events:
        st.markdown("---")
        st.markdown("#### 📈 走勢與危機區")
        _plot_market_with_crises(mkt_series, events, market_label)

        st.markdown("#### 📋 事件清單")
        df = _events_to_dataframe(events, market_label)
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
        )

        with st.expander("💾 下載 CSV / JSON"):
            csv = df.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                "下載事件清單（CSV）",
                csv,
                file_name=f"crisis_events_{market}_{years}y.csv",
                mime="text/csv",
            )

    # 限制提示
    st.markdown("---")
    st.caption(
        "💡 **已知限制**：基金 NAV 來自 FundClear，通常只涵蓋近 ~400 天。"
        "舊事件（如 COVID、2018 升息、2008 海嘯）只能顯示大盤跌幅，"
        "該基金欄會顯示「—」。Phase 3 將補上總經訊號歷史回看，"
        "Phase 4 加策略 grid_search，Phase 5 接 AI 策略建議。"
    )
