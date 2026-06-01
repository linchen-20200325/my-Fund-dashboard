"""tab_crisis_backtest.py — 📉 危機回測室 (v18.260, Phase 2 + Phase 3 UI)

Phase 2：歷史危機事件清單 + 該基金當時跌幅對照（services/crisis_backtest.py）
Phase 3：總經訊號歷史回看 — 驗證 Tab1 訊號預測力（services/macro_signal_lookback.py）
"""
from __future__ import annotations

import os

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

        # ── Phase 3：總經訊號預測力驗證 ───────────────────────
        st.markdown("---")
        _render_signal_lookback_section(events, years)

    # 限制提示
    st.markdown("---")
    st.caption(
        "💡 **已知限制**：基金 NAV 來自 FundClear，通常只涵蓋近 ~400 天。"
        "舊事件（如 COVID、2018 升息、2008 海嘯）只能顯示大盤跌幅，"
        "該基金欄會顯示「—」。"
        "Phase 4 將加策略 grid_search，Phase 5 接 AI 策略建議。"
    )


# ──────────────────────────────────────────────────────────────
# Phase 3：總經訊號預測力驗證
# ──────────────────────────────────────────────────────────────
def _render_signal_lookback_section(events: list, years: int) -> None:
    """🚦 對每個歷史事件回看 VIX/HY/T10Y2Y/UNRATE 是否預先警戒。"""
    st.markdown("### 🚦 總經訊號預測力驗證（Phase 3）")
    st.caption(
        "對每個歷史危機事件回看 N 天前的總經訊號 → 量化「Tab1 訊號是否真的有預警」。"
    )

    col_a, col_b = st.columns(2)
    with col_a:
        lookback_days = st.slider(
            "點觀測 offset（峰前 N 天）",
            min_value=30, max_value=180, value=90, step=15,
            help="判斷峰日 N 天前訊號是否已在警戒區",
            key="crisis_signal_lookback_days",
        )
    with col_b:
        max_lookback_days = st.slider(
            "提前預警搜尋上限（峰前 M 天）",
            min_value=90, max_value=540, value=365, step=30,
            help="在峰前 M 天區間內，找最早一次進入警戒的日期 → 算提前天數",
            key="crisis_signal_max_lookback",
        )

    if not st.button("🚦 跑訊號回看", type="secondary", key="crisis_signal_run"):
        st.caption("⬆️ 按按鈕開始（會抓 FRED + Yahoo 多年歷史，需要 ~10 秒）")
        return

    fred_key = os.environ.get("FRED_API_KEY", "")
    if not fred_key:
        st.warning("⚠️ 未設定 FRED_API_KEY — 僅 VIX 可抓，T10Y2Y / HY / UNRATE 將跳過")

    from services.macro_signal_lookback import (
        DEFAULT_SIGNALS,
        compute_signal_hit_rate,
        fetch_signal_series,
        lookback_all_signals,
    )

    # 抓所有訊號序列（一次性，多訊號並列）
    series_by_key: dict[str, pd.Series] = {}
    with st.spinner(f"抓取 {len(DEFAULT_SIGNALS)} 個訊號 {years} 年歷史..."):
        for spec in DEFAULT_SIGNALS:
            s = fetch_signal_series(spec, years=max(years, 10), fred_api_key=fred_key)
            series_by_key[spec.key] = s

    results = lookback_all_signals(
        events, series_by_key,
        specs=DEFAULT_SIGNALS,
        lookback_days=lookback_days,
        max_lookback_days=max_lookback_days,
    )

    # 命中率總覽
    st.markdown("#### 📊 訊號命中率總覽")
    summary_rows = []
    for spec in DEFAULT_SIGNALS:
        lbs = results[spec.key]
        stat = compute_signal_hit_rate(lbs)
        summary_rows.append({
            "訊號": spec.label,
            "閾值": f"{spec.direction} {spec.threshold}{spec.unit}",
            "涵蓋事件": stat["n_covered"],
            "命中事件": stat["n_hit"],
            "命中率": f"{stat['hit_rate']:.0%}" if stat["hit_rate"] is not None else "—",
            "平均提前天數": f"{int(stat['avg_lead_days'])}" if stat["avg_lead_days"] is not None else "—",
            "解讀": spec.note,
        })
    st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

    # 逐事件 × 逐訊號明細
    st.markdown("#### 🔬 逐事件明細")
    detail_rows = []
    for i, ev in enumerate(events):
        peak_str = str(ev.peak_date.date()) if ev.peak_date is not None else "—"
        row = {"事件": _format_event_name(peak_str), "高點日": peak_str}
        for spec in DEFAULT_SIGNALS:
            lb = results[spec.key][i]
            if lb.value_at_lookback is None and lb.first_warning_date is None:
                row[spec.label] = "—"
            elif lb.lead_time_days is not None:
                row[spec.label] = f"✅ 提前 {lb.lead_time_days}d"
            else:
                v = lb.value_at_lookback
                row[spec.label] = f"❌ ({v:.2f}{spec.unit})" if v is not None else "❌"
        detail_rows.append(row)
    st.dataframe(pd.DataFrame(detail_rows), use_container_width=True, hide_index=True)

    st.caption(
        "✅ = 峰前搜尋上限區間內，訊號曾進入警戒區，並顯示提前天數；"
        "❌ = 訊號序列涵蓋但未警戒（顯示峰前 offset 觀測值）；"
        "— = 訊號歷史不涵蓋該事件（FRED key 缺漏 / 序列過短）。"
    )
