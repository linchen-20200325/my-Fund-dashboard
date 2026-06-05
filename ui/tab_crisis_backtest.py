"""tab_crisis_backtest.py — 📉 危機回測室 (v18.260, Phase 2 + 3 + 3.5 + 4 UI)

Phase 2：歷史危機事件清單 + 該基金當時跌幅對照（services/crisis_backtest.py）
Phase 3：總經訊號歷史回看 — 驗證 Tab1 訊號預測力（services/macro_signal_lookback.py）
Phase 3.5：Tab1 Macro Score 預測力驗證 — 重算歷史 0-10 分對齊崩盤（services/macro_validation.py）
Phase 4：策略網格搜尋（4 策略 × 3 門檻）+ heatmap（services/crisis_strategy_grid.py）

v18.261 修：Phase 1 主按鈕原本是 click-only 一次性 gating（line 178~181），
按 Phase 3「跑訊號回看」/ Phase 4「跑網格」會觸發 rerun，Phase 1 button → False
→ 提前 return → Phase 3/4 sections 不再渲染 → button click 像沒反應。
改為三段 session_state cache + 參數 hash invalidation。
"""
from __future__ import annotations

import os

import pandas as pd
import streamlit as st


# v18.261：三段 cache key + 參數 hash gate（避免 click-only 一次性 gating bug）
_PHASE1_CACHE_KEY = "_crisis_phase1_cache"   # 主回測：events / mkt_series / labels
_PHASE3_CACHE_KEY = "_crisis_phase3_cache"   # 訊號回看結果
_GRID_CACHE_KEY = "_crisis_grid_cache"       # Phase 4 策略網格（既有，提到頂層管理）

# v19.13：雙軌 mode — 多因子權重最佳化 + AutoSearch apply 路由
MULTIFACTOR_MODES = ("macro", "pullback")
MULTIFACTOR_MODE_LABELS = {
    "macro": "🏔️ 總經長期 (lead 30-90d)",
    "pullback": "⚡ 短期回檔 (lead 5-30d)",
}
# v19.13.1：mode → walk-forward 評估窗口 (min, max) forward days
# 修 v19.13 bug：原本兩 mode 都吃 default max=365 → F1 全部退化到 base-rate
MULTIFACTOR_MODE_LEAD_DAYS: dict[str, tuple[int, int]] = {
    "macro": (30, 90),
    "pullback": (5, 30),
}


def route_apply_key_by_lead(max_lead_days: int | float) -> str:
    """v19.13：AutoSearch「採用 Top 1」依當前 lead time max 路由到對應 mode session_state.

    max_lead ≤ 30 → 短期回檔；否則 → 長期總經。
    回傳完整 session_state key（含 prefix）。
    """
    mode = "pullback" if float(max_lead_days) <= 30 else "macro"
    return f"multifactor_keys_{mode}"


def multifactor_keys_state_key(mode: str) -> str:
    """v19.13：mode → multiselect 綁定的 session_state key."""
    if mode not in MULTIFACTOR_MODES:
        raise ValueError(f"unknown mode: {mode!r}")
    return f"multifactor_keys_{mode}"


def multifactor_result_state_key(mode: str) -> str:
    """v19.13：mode → walk-forward 結果的 session_state cache key."""
    if mode not in MULTIFACTOR_MODES:
        raise ValueError(f"unknown mode: {mode!r}")
    return f"_multifactor_result_{mode}"


def mode_forward_days(mode: str) -> tuple[int, int]:
    """v19.13.1：mode → (min_forward_days, max_forward_days) for walk-forward 評估."""
    if mode not in MULTIFACTOR_MODES:
        raise ValueError(f"unknown mode: {mode!r}")
    return MULTIFACTOR_MODE_LEAD_DAYS[mode]


def _phase1_params_signature(market: str, threshold_pct: int, years: int, fund_key: str) -> str:
    return f"{market}|{threshold_pct}|{years}|{(fund_key or '').strip()}"


def _invalidate_phase1_chain() -> None:
    """Phase 1 參數變動時，連帶清掉 Phase 3 / Phase 4 cache（避免顯示與當前 input 不符的舊結果）。"""
    for _k in (_PHASE1_CACHE_KEY, _PHASE3_CACHE_KEY, _GRID_CACHE_KEY):
        st.session_state.pop(_k, None)


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
        st.caption("⚠️ 該基金 NAV 不涵蓋任何危機事件期間（基金 NAV 通常只有近 ~400 天）")
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

    # v18.261：參數 hash gating — 參數變動自動 invalidate 整條 cache（Phase 1/3/4）
    _params_sig = _phase1_params_signature(market, threshold_pct, years, fund_key)
    _cached_p1 = st.session_state.get(_PHASE1_CACHE_KEY)
    if _cached_p1 and _cached_p1.get("params_sig") != _params_sig:
        _invalidate_phase1_chain()
        _cached_p1 = None

    run = st.button("🚀 開始回測", type="primary", use_container_width=True)
    if run:
        # 點下按鈕 → 抓資料 + 算事件 + 寫 cache（後續 rerun 從 cache 渲染）
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

        fund_nav: pd.Series | None = None
        fund_display_name = default_name or "(未指定基金)"
        if fund_key.strip():
            # v18.283：危機回測需要多年 NAV 歷史，不能用 Tab2 stash 的 ~30 筆短序列。
            # 改走 fetch_nav_history_long(CnYES + MoneyDJ 歷史頁 + 24h disk cache)。
            # User 反饋 ACTI94 30 筆 NAV 不涵蓋 2018/2020/2022 危機事件 → 完全看不出影響。
            with st.spinner(f"抓取基金 {fund_key} 多年歷史 NAV（CnYES + MoneyDJ 歷史頁）..."):
                try:
                    from repositories.fund_repository import (
                        fetch_fund_by_key,
                        fetch_nav_history_long,
                    )
                    fund_nav = fetch_nav_history_long(fund_key.strip(), min_years=years)
                    # 雙重 fallback：fetch_fund_by_key（走完整 multi-source）
                    if fund_nav is None or fund_nav.empty:
                        try:
                            _fd2 = fetch_fund_by_key(fund_key.strip())
                            _s2 = (_fd2 or {}).get("series")
                            if _s2 is not None and len(_s2.dropna()) >= 10:
                                fund_nav = _s2
                        except Exception as _e2:
                            print(f"[crisis] fetch_fund_by_key fallback failed: {_e2}")

                    if fund_nav is None or fund_nav.empty:
                        st.warning(
                            f"⚠️ 基金 `{fund_key}` 取不到 NAV。已嘗試 CnYES + MoneyDJ 歷史頁 + 短期頁。"
                        )
                        fund_nav = None
                    else:
                        fund_display_name = default_name or fund_key
                        _n_days = len(fund_nav.dropna())
                        _span_yrs = ((fund_nav.index.max() - fund_nav.index.min()).days / 365.25
                                     if _n_days >= 2 else 0)
                        if _span_yrs >= 5:
                            st.success(
                                f"✅ 抓到 {_n_days} 筆 NAV（涵蓋 {_span_yrs:.1f} 年，"
                                f"{fund_nav.index.min().date()} ~ {fund_nav.index.max().date()}）"
                            )
                        else:
                            st.warning(
                                f"⚠️ 只抓到 {_n_days} 筆 NAV（涵蓋 {_span_yrs:.1f} 年）— "
                                "舊年份的危機事件該基金將顯示「—」。"
                                "如果 user 認為應該有更多歷史，請去 CnYES 或基金公司網站確認 / 回報。"
                            )
                except Exception as e:
                    st.warning(f"⚠️ 基金 NAV 抓取失敗：{e}")
                    fund_nav = None

        threshold = threshold_pct / 100.0
        events = summarize_events_with_fund(
            market_series=mkt_series,
            fund_nav=fund_nav,
            threshold=threshold,
            market=market,
        )
        st.session_state[_PHASE1_CACHE_KEY] = {
            "params_sig": _params_sig,
            "mkt_series": mkt_series,
            "events": events,
            "market_label": market_label,
            "market": market,
            "threshold_pct": threshold_pct,
            "years": years,
            "fund_nav_available": fund_nav is not None,
            "fund_display_name": fund_display_name,
        }
        # Phase 1 重跑時清掉 Phase 3/4 stale cache（避免事件清單變了但訊號回看還是舊的）
        st.session_state.pop(_PHASE3_CACHE_KEY, None)
        st.session_state.pop(_GRID_CACHE_KEY, None)
        _cached_p1 = st.session_state[_PHASE1_CACHE_KEY]

    if not _cached_p1:
        st.info("⬆️ 設定參數後按「開始回測」")
        return

    # ── 從 cache 渲染（每次 rerun 都會經過這裡，所以 Phase 3/4 button 點下後也能再渲染）──
    mkt_series = _cached_p1["mkt_series"]
    events = _cached_p1["events"]
    market_label = _cached_p1["market_label"]
    market = _cached_p1["market"]
    threshold_pct_disp = _cached_p1["threshold_pct"]
    years_disp = _cached_p1["years"]
    fund_display_name = _cached_p1["fund_display_name"]
    fund_nav_available = _cached_p1["fund_nav_available"]

    st.divider()
    st.markdown(f"### 📊 {market_label} 危機事件總覽（門檻 {threshold_pct_disp}% / 回看 {years_disp} 年）")
    _render_summary_metrics(events)

    if fund_nav_available and events:
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
                file_name=f"crisis_events_{market}_{years_disp}y.csv",
                mime="text/csv",
            )

        # ── Phase 3：總經訊號預測力驗證 ───────────────────────
        st.markdown("---")
        _render_signal_lookback_section(events, years_disp)

        # ── Phase 3.5：Tab1 Macro Score 預測力驗證 ────────────
        st.markdown("---")
        _render_score_validation_section(events, years_disp)

        # ── Phase 4：策略網格搜尋（AI 區塊已剝離至最尾）─────
        st.markdown("---")
        _render_strategy_grid_section(mkt_series, market_label, years_disp, events)

        # ── Phase E：全球 macro_score × 台股 TWII 對照 ─────────
        st.markdown("---")
        _render_phase_e_cross_source_section(events, years_disp)

        # ── Phase 5：AI 策略建議（固定壓底，綜覽前述所有結果）─
        st.markdown("---")
        _render_phase_5_ai_section()

    # 限制提示
    st.markdown("---")
    st.caption(
        "💡 **已知限制**：基金 NAV 來自 FundClear，通常只涵蓋近 ~400 天。"
        "舊事件（如 COVID、2018 升息、2008 海嘯）只能顯示大盤跌幅，"
        "該基金欄會顯示「—」。"
        "Phase E：全球 macro_score × 台股 TWII 對照（按「🌏 跑 Phase E」後出現）。"
        "Phase 5：Gemini AI 策略解讀（壓底；需先跑網格產生資料）。"
    )


# ──────────────────────────────────────────────────────────────
# Phase 3：總經訊號預測力驗證
# ──────────────────────────────────────────────────────────────
def _render_signal_lookback_section(events: list, years: int) -> None:
    """🚦 對每個歷史事件回看 VIX/HY/T10Y2Y/UNRATE 是否預先警戒。"""
    st.markdown("### 🚦 總經訊號預測力驗證（Phase 3 · v2 轉折偵測）")
    st.caption(
        "🔄 **v2 edge detection**：對每個歷史危機事件，在峰前 M 天區間內搜尋訊號"
        "**從非警戒跨越到警戒**的最早**轉折日**（不是「找最早一個觸發警戒的日子」），"
        "排除「常態性已在警戒 → 假預警」誤判 → 量化「Tab1 訊號是否真的有預警」。"
    )

    col_a, col_b, col_c = st.columns(3)
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
            help="在峰前 M 天內搜尋訊號『從非警戒跨越到警戒』的最早轉折日（edge detection）",
            key="crisis_signal_max_lookback",
        )
    with col_c:
        # v18.282：精確率追蹤期 — 訊號響起後 K 天內若有 crisis 算 TP
        max_forward_days = st.slider(
            "📐 精確率追蹤期（crossing 後 K 天）",
            min_value=90, max_value=540, value=365, step=30,
            help="訊號響起後 K 天內若有危機事件 → TP；無 → FP（誤報）"
                 "。改此 slider 即時重算精確率，不需重按按鈕。",
            key="crisis_signal_max_forward",
        )

    # v18.261：button + cache 雙軌 — click 時抓資料寫 cache，rerun 時從 cache 渲染
    _p3_sig = f"{lookback_days}|{max_lookback_days}|{len(events)}|{years}"
    _cached_p3 = st.session_state.get(_PHASE3_CACHE_KEY)
    if _cached_p3 and _cached_p3.get("sig") != _p3_sig:
        # 參數改了 → 失效（user 拉滑桿後想重看，要重新按 button）
        st.session_state.pop(_PHASE3_CACHE_KEY, None)
        _cached_p3 = None

    _btn_p3 = st.button("🚦 跑訊號回看", type="secondary", key="crisis_signal_run")
    if _btn_p3:
        fred_key = os.environ.get("FRED_API_KEY", "")
        if not fred_key:
            st.warning("⚠️ 未設定 FRED_API_KEY — 僅 VIX 可抓，T10Y2Y / HY / UNRATE 將跳過")

        from dataclasses import replace as _replace
        from services.macro_signal_lookback import (
            DEFAULT_SIGNALS,
            compute_signal_hit_rate,
            fetch_signal_series,
            lookback_all_signals,
        )

        # v18.283: 套用 session-only threshold overrides（若 user 已採用建議）
        _overrides = st.session_state.get("_phase3_overrides", {})
        active_specs = [_replace(s, threshold=_overrides[s.key])
                         if s.key in _overrides else s
                         for s in DEFAULT_SIGNALS]

        series_by_key: dict[str, pd.Series] = {}
        with st.spinner(f"抓取 {len(DEFAULT_SIGNALS)} 個訊號 {years} 年歷史..."):
            for spec in DEFAULT_SIGNALS:
                s = fetch_signal_series(spec, years=max(years, 10), fred_api_key=fred_key)
                series_by_key[spec.key] = s

        results = lookback_all_signals(
            events, series_by_key,
            specs=active_specs,
            lookback_days=lookback_days,
            max_lookback_days=max_lookback_days,
        )
        st.session_state[_PHASE3_CACHE_KEY] = {
            "sig": _p3_sig, "results": results,
            "series_by_key": series_by_key,
            "active_specs": active_specs,  # v18.283: 含 session overrides
        }
        _cached_p3 = st.session_state[_PHASE3_CACHE_KEY]

    if not _cached_p3:
        st.caption("⬆️ 按按鈕開始（會抓 FRED + Yahoo 多年歷史，需要 ~10 秒）")
        return

    # ── 從 cache 渲染 ──
    from services.macro_signal_lookback import DEFAULT_SIGNALS, compute_signal_hit_rate
    results = _cached_p3["results"]
    # v18.283: 優先用 cache 中 active_specs（含 overrides）；舊 cache 退回 DEFAULT
    cached_specs = _cached_p3.get("active_specs") or DEFAULT_SIGNALS

    # 命中率總覽
    st.markdown("#### 📊 訊號命中率總覽")
    summary_rows = []
    for spec in cached_specs:
        lbs = results[spec.key]
        stat = compute_signal_hit_rate(lbs)
        summary_rows.append({
            "訊號": spec.label,
            "閾值": f"{spec.direction} {spec.threshold}{spec.unit}",
            "涵蓋事件": stat["n_covered"],
            "命中事件": stat["n_hit"],
            "命中率": f"{stat['hit_rate']:.0%}" if stat["hit_rate"] is not None else "—",
            "平均提前轉折天數": f"{int(stat['avg_lead_days'])}" if stat["avg_lead_days"] is not None else "—",
            "解讀": spec.note,
        })
    st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

    # 逐事件 × 逐訊號明細
    st.markdown("#### 🔬 逐事件明細")
    detail_rows = []
    for i, ev in enumerate(events):
        peak_str = str(ev.peak_date.date()) if ev.peak_date is not None else "—"
        row = {"事件": _format_event_name(peak_str), "高點日": peak_str}
        for spec in cached_specs:
            lb = results[spec.key][i]
            if lb.value_at_lookback is None and lb.first_warning_date is None:
                row[spec.label] = "—"
            elif lb.lead_time_days is not None:
                row[spec.label] = f"✅ 轉折提前 {lb.lead_time_days}d"
            else:
                v = lb.value_at_lookback
                row[spec.label] = f"❌ ({v:.2f}{spec.unit})" if v is not None else "❌"
        detail_rows.append(row)
    st.dataframe(pd.DataFrame(detail_rows), use_container_width=True, hide_index=True)

    st.caption(
        "✅ = 峰前 M 天內偵測到訊號**從非警戒跨越到警戒**的轉折日，顯示提前天數；"
        "❌ = 訊號序列涵蓋但峰前未出現轉折（可能常態警戒 → 假預警 / 或全程平靜）；"
        "— = 訊號歷史不涵蓋該事件（FRED key 缺漏 / 序列過短）。"
    )

    # ── 📐 v18.282：訊號精確率分析（forward-looking）─────────────
    series_by_key = _cached_p3.get("series_by_key")
    if not series_by_key:
        return  # 舊 cache 沒存 series，等下次按按鈕
    from services.macro_signal_lookback import compute_signal_precision
    st.markdown("---")
    st.markdown("#### 📐 訊號精確率分析（forward-looking · v18.282）")
    st.caption(
        f"🔍 與上方「召回率」互補 — 遍歷歷史所有 crossings，檢查後 "
        f"**{max_forward_days} 天**內是否真的爆危機。"
        "**精確率高 = 訊號響起時相信它的勝率高**；**誤報率高 = 狼來了**。"
    )
    precision_rows = []
    for spec in cached_specs:
        series = series_by_key.get(spec.key)
        if series is None or series.empty:
            precision_rows.append({
                "訊號": spec.label, "歷史 crossings": "—",
                "真實預警 TP": "—", "假警報 FP": "—",
                "精確率": "—", "誤報率": "—", "TP 平均提前天數": "—",
            })
            continue
        stat = compute_signal_precision(series, events, spec, max_forward_days)
        precision_rows.append({
            "訊號": spec.label,
            "歷史 crossings": stat["n_crossings"],
            "真實預警 TP": stat["n_true_positives"],
            "假警報 FP": stat["n_false_positives"],
            "精確率": (f"{stat['precision_pct']:.1f}%"
                       if stat["precision_pct"] is not None else "—"),
            "誤報率": (f"{stat['false_alert_rate_pct']:.1f}%"
                       if stat["false_alert_rate_pct"] is not None else "—"),
            "TP 平均提前天數": (f"{stat['avg_lead_to_crisis_days']:.0f}"
                                  if stat["avg_lead_to_crisis_days"] is not None else "—"),
        })
    st.dataframe(pd.DataFrame(precision_rows),
                  use_container_width=True, hide_index=True)
    st.caption(
        "💡 解讀：召回率高 + 精確率高 = 神準預警；召回率高但精確率低 = 警鈴常響但只少數真的爆；"
        "兩者皆低 = 訊號失效。理想 ≥ 50% 精確率代表「賭一半以上」。"
    )

    # ── 🎯 v18.283：MT5-style 自動校準（walk-forward）────────────
    _render_phase3_auto_calibration_fund(events, cached_specs, series_by_key)

    # v19.6：多因子權重最佳化 hoist 到「🔬 回測找參數」獨立 tab
    # _render_phase3_multi_factor_optimization 仍定義在本檔（供新 tab import）


def _render_phase3_auto_calibration_fund(events, specs, series_by_key) -> None:
    """🎯 MT5-style threshold 自動校準 — walk-forward + 3 重 anti-overfit gate."""
    from services.signal_threshold_optimization import (
        make_default_grid, optimize_signal_threshold,
    )

    with st.expander(
            "🎯 MT5-style 自動校準（walk-forward + 3 重 anti-overfit gate）",
            expanded=False):
        st.caption(
            "🤖 對選定訊號跑 walk-forward 4 折回測：grid sweep × train/test "
            "OOS 驗證 × 折間票選 × drift > 30% 自動回退預設。**採用建議僅本 "
            "session 生效**，cloud reboot 後回原值。"
        )
        col_pick, col_grid = st.columns([2, 1])
        with col_pick:
            spec_by_label = {s.label: s for s in specs}
            sel_label = st.selectbox(
                "選擇訊號", options=list(spec_by_label.keys()),
                key="crisis_calib_signal",
            )
        with col_grid:
            n_steps = st.slider(
                "grid 步數", min_value=5, max_value=21, value=11, step=2,
                key="crisis_calib_n_steps",
                help="grid 範圍 = 預設 threshold ±50%；步數越多越細。",
            )

        if not st.button("🚀 跑 walk-forward 回測", type="primary",
                          key="crisis_calib_run"):
            _last = st.session_state.get("_phase3_calib_result")
            if not _last:
                st.caption("⬆️ 點按鈕開始（< 5 秒）")
                return
        else:
            sel_spec = spec_by_label[sel_label]
            series = series_by_key.get(sel_spec.key)
            if series is None or series.empty:
                st.warning(f"⚠️ {sel_label} series 為空，無法校準")
                return
            grid = make_default_grid(sel_spec.threshold, n_steps=n_steps)
            with st.spinner(f"跑 walk-forward × {n_steps} grid × "
                             f"{len(events)} events ..."):
                result = optimize_signal_threshold(
                    series, events, sel_spec, grid=grid,
                    n_folds=4, max_forward_days=365,
                )
            st.session_state["_phase3_calib_result"] = {
                "spec_key": sel_spec.key, "spec_label": sel_label,
                "current": result["current"],
                "recommended": result["recommended"],
                "current_metrics": result["current_metrics"],
                "recommended_metrics": result["recommended_metrics"],
                "walk_forward": result["walk_forward"],
                "status": result["status"],
                "drift_warning": result["drift_warning"],
            }

        last = st.session_state.get("_phase3_calib_result")
        if not last:
            return

        st.markdown(f"##### 📋 {last['spec_label']} 校準結果")
        status = last["status"]
        if status == "insufficient_events":
            st.error("❌ 危機事件數不足 ≥ 4，無法 4 折 walk-forward。"
                      "請先在 Phase 1 偵測更多事件（降回撤門檻或加長歷史）。")
            return
        if status == "fallback_overfit":
            st.warning(
                f"⚠️ **過擬合守門啟動**：過半折 drift > 30% → "
                f"建議**回退預設 {last['current']:g}**（不採用 grid 找到的值）。"
                f"樣本可能不足或週期偏移，需更多歷史資料。"
            )
        else:
            st.success(f"✅ **3 重 gate 全過** → 建議採用 "
                        f"**{last['recommended']:g}**")

        cur_m = last["current_metrics"] or {}
        rec_m = last["recommended_metrics"] or {}
        col_a, col_b = st.columns(2)
        col_a.metric(
            f"現行 threshold {last['current']:g}",
            f"F1 = {cur_m.get('f1', 0):.3f}",
            help=f"P = {cur_m.get('precision', 0):.1%} · "
                 f"R = {cur_m.get('recall', 0):.1%} · "
                 f"crossings = {cur_m.get('n_crossings', 0)}",
        )
        delta_f1 = rec_m.get("f1", 0) - cur_m.get("f1", 0)
        col_b.metric(
            f"建議 threshold {last['recommended']:g}",
            f"F1 = {rec_m.get('f1', 0):.3f}",
            delta=f"{delta_f1:+.3f}",
            help=f"P = {rec_m.get('precision', 0):.1%} · "
                 f"R = {rec_m.get('recall', 0):.1%} · "
                 f"crossings = {rec_m.get('n_crossings', 0)}",
        )

        if last["walk_forward"]:
            st.markdown("##### 🔄 Walk-forward 各折 (OOS)")
            wf_df = pd.DataFrame(last["walk_forward"])
            wf_df["drift_pct"] = wf_df["drift_pct"].round(1)
            wf_df["train_f1"] = wf_df["train_f1"].round(3)
            wf_df["test_f1"] = wf_df["test_f1"].round(3)
            wf_df = wf_df.rename(columns={
                "fold": "折",
                "n_train": "train 事件",
                "n_test": "test 事件",
                "train_best": "train 最佳 threshold",
                "train_f1": "Train F1",
                "test_f1": "OOS Test F1",
                "drift_pct": "Drift %",
            })
            st.dataframe(wf_df, use_container_width=True, hide_index=True)

        if (status == "adopted"
                and abs(last["recommended"] - last["current"]) > 1e-9):
            if st.button(
                    f"✅ 採用建議 threshold {last['recommended']:g}"
                    f"（本 session 生效）",
                    type="primary", key="crisis_calib_adopt"):
                overrides = st.session_state.get("_phase3_overrides", {})
                overrides[last["spec_key"]] = last["recommended"]
                st.session_state["_phase3_overrides"] = overrides
                st.session_state.pop(_PHASE3_CACHE_KEY, None)
                st.success(
                    f"✅ 已採用 {last['spec_label']} → "
                    f"{last['recommended']:g}。"
                    f"請按上方「🚦 跑訊號回看」重新計算（cache 已清）。"
                )
                st.rerun()

        ov = st.session_state.get("_phase3_overrides", {})
        if ov:
            ov_df = pd.DataFrame([
                {"訊號": k, "session override threshold": v} for k, v in ov.items()
            ])
            st.markdown("##### 📌 已採用 overrides（本 session）")
            st.dataframe(ov_df, use_container_width=True, hide_index=True)
            if st.button("🔄 清空 overrides（回預設）",
                          key="crisis_calib_clear"):
                st.session_state.pop("_phase3_overrides", None)
                st.session_state.pop(_PHASE3_CACHE_KEY, None)
                st.rerun()


# ──────────────────────────────────────────────────────────────
# 🔬 v18.285：多因子權重最佳化 + 高原區 + Walk-Forward OOS
# 不是找單一最高績效，而是找「參數高原區」+ 滾動前向 OOS 驗證穩定性
# ──────────────────────────────────────────────────────────────
def _render_dual_signal_summary_card() -> None:
    """v19.13：讀兩 mode 的 walk-forward cache，顯示 OOS F1/Sharpe 並列摘要.

    純歷史回測指標（v19.13 §3 選項 C）；即時訊號燈 + 決策矩陣留待 v19.14。
    """
    macro = st.session_state.get(multifactor_result_state_key("macro"))
    pullback = st.session_state.get(multifactor_result_state_key("pullback"))
    if not macro and not pullback:
        return  # 還沒跑過任何 mode，不顯示空卡
    st.markdown("### 📊 雙模型摘要卡（v19.13）")
    st.caption(
        "兩 mode 各自獨立的 walk-forward OOS 結果。即時訊號燈 + 決策矩陣為 v19.14 範圍。"
    )
    col_m, col_p = st.columns(2)
    for col, key, label in (
        (col_m, "macro", MULTIFACTOR_MODE_LABELS["macro"]),
        (col_p, "pullback", MULTIFACTOR_MODE_LABELS["pullback"]),
    ):
        with col:
            st.markdown(f"**{label}**")
            cached = st.session_state.get(multifactor_result_state_key(key))
            if not cached:
                st.info("尚未訓練 — 請在下方切此 mode 跑 walk-forward")
                continue
            wf = cached.get("wf") or {}
            f1 = float(wf.get("oos_f1", 0.0))
            sharpe = float(wf.get("oos_sharpe", 0.0))
            n_folds = int(wf.get("n_folds", 0))
            m1, m2 = st.columns(2)
            m1.metric("OOS F1", f"{f1:.3f}")
            m2.metric("OOS Sharpe", f"{sharpe:.3f}")
            st.caption(
                f"因子：{', '.join(cached.get('sel_keys', []))}　|　folds={n_folds}",
            )
    st.markdown("---")


def _render_phase3_multi_factor_optimization(events, series_by_key) -> None:
    """🔬 多因子權重最佳化 — 高原評分 + walk-forward OOS 驗證."""


    from services.multi_factor_optimization import (
        FACTOR_POOL_BY_KEY,
        build_plateau_heatmap_2d,
        build_plateau_surface_3d,
        evaluate_plateau,
        fetch_factor_series,
        find_plateau_optimum,
        grid_search_performance,
        walk_forward_validate,
    )

    # v19.13：雙模型摘要卡（在 expander 上方，唯讀）
    _render_dual_signal_summary_card()

    with st.expander(
            "🔬 多因子權重最佳化（高原區 + walk-forward OOS）",
            expanded=False):
        st.caption(
            "🤖 多因子加權綜合分數 S_t = Σ w_i × normalize(I_{i,t−1}) → 拐點偵測 → "
            "找**高原區**（不取單一最高 F1，而是鄰域 mean − λ × std 最大）→ "
            "walk-forward 滾動 train/test 串 OOS 權益曲線確認 robust。"
        )

        # v19.13：mode radio — 切「🏔️ 總經長期 / ⚡ 短期回檔」，下游 key 全部動態切換
        mode = st.radio(
            "模型 mode（兩 mode 獨立 multiselect / walk-forward 結果，互不覆蓋）",
            options=list(MULTIFACTOR_MODES),
            format_func=lambda k: MULTIFACTOR_MODE_LABELS[k],
            horizontal=True, key="multifactor_mode",
        )
        keys_state_key = multifactor_keys_state_key(mode)
        result_state_key = multifactor_result_state_key(mode)

        # v18.286: FACTOR_POOL 全 13 個都列出；Phase 1/2 已抓的標 ✓，缺的會在點 Run 時 lazy-fetch
        available_keys = list(FACTOR_POOL_BY_KEY.keys())
        ready_keys = {k for k in available_keys if k in series_by_key}
        if len(available_keys) < 2:
            st.warning(f"⚠️ FACTOR_POOL 不足 2 個（目前 {len(available_keys)} 個）。")
            return
        st.caption(
            f"📌 FACTOR_POOL 共 {len(available_keys)} 因子；"
            f"{len(ready_keys)} 個已在 Phase 1/2 cache，"
            f"{len(available_keys) - len(ready_keys)} 個會在點 Run 時 lazy-fetch。"
        )

        # v19.13：依 mode 給不同預設因子（pullback 偏 5D delta；macro 走既有日頻）
        if keys_state_key not in st.session_state:
            if mode == "pullback":
                preferred = [
                    k for k in ("VIX", "VIX_DELTA_5D",
                                "HY_SPREAD_DELTA_5D", "BREADTH_RSP_SPY_5D")
                    if k in available_keys
                ]
                default_sel = preferred[:6] or available_keys[:3]
            else:
                default_sel = available_keys[:min(3, len(available_keys))]
            st.session_state[keys_state_key] = default_sel

        col_pick, col_metric = st.columns([2, 1])
        with col_pick:
            sel_keys = st.multiselect(
                "選擇因子（最多 6 個 — simplex 點數隨 n 指數成長）",
                options=available_keys,
                max_selections=6,
                key=keys_state_key,
                format_func=lambda k: f"{FACTOR_POOL_BY_KEY[k].label} ({k})",
            )
        with col_metric:
            metric = st.radio(
                "Plateau 目標", options=["f1", "sharpe"],
                index=0, key="multifactor_metric",
                horizontal=True,
            )

        col_step, col_radius, col_lambda = st.columns(3)
        with col_step:
            step = st.slider(
                "Grid 步長", min_value=0.1, max_value=0.5, value=0.2, step=0.05,
                key="multifactor_step",
                help="權重 simplex 解析度；步長越小組合越多。",
            )
        with col_radius:
            radius = st.slider(
                "鄰域半徑", min_value=1, max_value=3, value=1, step=1,
                key="multifactor_radius",
                help="高原評分鄰域格數（chebyshev 距離）。",
            )
        with col_lambda:
            lambda_std = st.slider(
                "λ（std 懲罰係數）", min_value=0.0, max_value=2.0, value=0.5,
                step=0.1, key="multifactor_lambda",
                help="plateau_score = mean − λ × std；λ 越大越偏好平坦區。",
            )

        col_tr, col_te, col_th = st.columns(3)
        with col_tr:
            train_months = st.slider(
                "Train window（月）", min_value=12, max_value=72, value=36,
                step=6, key="multifactor_train_months",
            )
        with col_te:
            test_months = st.slider(
                "Test window（月）", min_value=3, max_value=24, value=12,
                step=3, key="multifactor_test_months",
            )
        with col_th:
            threshold = st.slider(
                "綜合分數警戒線", min_value=0.0, max_value=3.0, value=1.0,
                step=0.1, key="multifactor_threshold",
                help="S_t ≥ 此值即視為警戒；轉折日 = 由 <threshold 跨到 ≥threshold。",
            )

        if len(sel_keys) < 2:
            st.info("👆 請至少選 2 個因子才能跑最佳化。")
            return

        if st.button("🚀 跑多因子高原 + walk-forward",
                      type="primary", key="multifactor_run"):
            try:
                returns = _load_spx_returns()
            except FileNotFoundError:
                returns = pd.Series(dtype=float)
            # v18.286: lazy-fetch 不在 series_by_key cache 內的因子
            import os as _os
            _fred_key = _os.environ.get("FRED_API_KEY", "")
            sel_series: dict[str, pd.Series] = {}
            missing = [k for k in sel_keys if k not in series_by_key]
            if missing:
                with st.spinner(f"lazy-fetch {len(missing)} 個新因子（{', '.join(missing)}）..."):
                    for k in missing:
                        sel_series[k] = fetch_factor_series(
                            FACTOR_POOL_BY_KEY[k], years=20, fred_api_key=_fred_key,
                        )
            for k in sel_keys:
                if k not in sel_series:
                    sel_series[k] = series_by_key[k]
            # v19.13.1：依 mode 注入正確的 (min, max) forward days
            # 修 v19.13 bug：原本沒傳 → 兩 mode 都用 default max=365 → F1 退化
            min_fwd, max_fwd = mode_forward_days(mode)
            with st.spinner("跑 grid search + plateau + walk-forward 中..."):
                grid_result = grid_search_performance(
                    sel_series, returns, events, sel_keys,
                    threshold=threshold, step=step,
                    min_forward_days=min_fwd, max_forward_days=max_fwd,
                )
                plateau_scores = evaluate_plateau(
                    grid_result, sel_keys, step, radius, lambda_std, metric,
                )
                opt = find_plateau_optimum(grid_result, plateau_scores)
                wf = walk_forward_validate(
                    sel_series, returns, events, sel_keys,
                    train_months=train_months, test_months=test_months,
                    threshold=threshold, step=step, radius=radius,
                    lambda_std=lambda_std, metric=metric,
                    min_forward_days=min_fwd, max_forward_days=max_fwd,
                )
            st.session_state[result_state_key] = {
                "sel_keys": sel_keys,
                "grid": grid_result,
                "plateau": plateau_scores,
                "opt": opt,
                "wf": wf,
                "metric": metric,
                "step": step,
                "mode": mode,
            }
            st.success(
                f"✅ [{MULTIFACTOR_MODE_LABELS[mode]}] "
                f"完成 {len(grid_result['combos'])} 個權重組合 + "
                f"{wf['n_folds']} 折 walk-forward"
            )

        cached = st.session_state.get(result_state_key)
        if not cached:
            return
        sel_keys = cached["sel_keys"]
        opt = cached["opt"]
        wf = cached["wf"]
        plateau_scores = cached["plateau"]
        grid_result = cached["grid"]

        st.markdown("### 🏆 高原最佳權重（train 全期間）")
        opt_cols = st.columns(min(len(sel_keys), 4))
        for i, (k, w) in enumerate(opt["weights"].items()):
            with opt_cols[i % len(opt_cols)]:
                st.metric(k, f"{w:.2f}")
        c_f, c_s, c_p = st.columns(3)
        c_f.metric("Train F1", f"{opt['f1']:.3f}")
        c_s.metric("Train Sharpe", f"{opt['sharpe']:.3f}")
        c_p.metric("Plateau Score", f"{opt['plateau_score']:.3f}")

        st.markdown("### 📊 高原視覺化")
        if len(sel_keys) >= 2:
            col_x, col_y, col_viz = st.columns([1, 1, 1])
            with col_x:
                x_key = st.selectbox("X 軸因子", options=sel_keys,
                                     index=0, key="multifactor_x")
            with col_y:
                remaining = [k for k in sel_keys if k != x_key]
                y_key = st.selectbox("Y 軸因子", options=remaining,
                                     index=0, key="multifactor_y")
            with col_viz:
                viz_kind = st.radio(
                    "圖形類型", options=["2D heatmap", "3D surface"],
                    index=0, horizontal=True, key="multifactor_viz_kind",
                )
            metric_label = f"{cached['metric'].upper()} plateau"
            if viz_kind == "2D heatmap":
                fig = build_plateau_heatmap_2d(
                    grid_result, plateau_scores, sel_keys, (x_key, y_key),
                    metric_label,
                )
            else:
                fig = build_plateau_surface_3d(
                    grid_result, plateau_scores, sel_keys, (x_key, y_key),
                    metric_label,
                )
            st.plotly_chart(fig, use_container_width=True)

        if wf["folds"]:
            st.markdown("### 🚶 Walk-forward 各折（OOS 樣本外）")
            fold_rows = []
            for f in wf["folds"]:
                fold_rows.append({
                    "折": f["fold"],
                    "Train": f"{f['train_range'][0]} → {f['train_range'][1]}",
                    "Test": f"{f['test_range'][0]} → {f['test_range'][1]}",
                    "權重": ", ".join(f"{k}={v:.2f}" for k, v in f["weights"].items()),
                    "Train F1": f"{f['train_f1']:.3f}",
                    "Test F1": f"{f['test_f1']:.3f}",
                    "Train Sharpe": f"{f['train_sharpe']:.3f}",
                    "Test Sharpe": f"{f['test_sharpe']:.3f}",
                })
            st.dataframe(pd.DataFrame(fold_rows), use_container_width=True,
                         hide_index=True)
            c1, c2 = st.columns(2)
            c1.metric("OOS F1（全段）", f"{wf['oos_f1']:.3f}")
            c2.metric("OOS Sharpe（全段）", f"{wf['oos_sharpe']:.3f}")
        else:
            st.info(f"⚠️ Walk-forward 無有效折（status={wf.get('status')}）— "
                    "請調小 train/test 視窗或加長序列。")

        # ── 🤖 事前 AI 建議（v19.9，按鈕觸發避免燒 quota）─────────────
        _render_ai_recommendation_section(cached)

        # ── 📌 Route C-1：提交為待審權重（僅手動觸發）─────────────
        _render_pending_submit_section(cached)


def _render_ai_recommendation_section(cached: dict | None) -> None:
    """v19.9：在提交前讓 AI 比對 top-5 候選 → 建議提交哪組（含風險旗標）。

    與 ``_render_pending_submit_section`` 內的「事後 AI 解讀」是獨立兩條 AI 線。
    """
    st.markdown("---")
    st.markdown("### 🤖 事前 AI 建議參數")
    st.caption(
        "AI 比對 plateau top-5 候選 → 建議您提交哪一組（含 n_crossings / OOS F1 / "
        "權重分散度風險旗標）。**按鈕觸發，避免燒 quota。**"
    )

    if not cached or not (cached.get("opt") or {}).get("weights"):
        st.info("👆 請先跑完多因子高原 + walk-forward，才能取得 AI 建議。")
        return

    from services.ai_advisor_pending import recommend_weights
    from services.multi_factor_optimization import top_n_plateau_candidates

    advice_key = "_multifactor_ai_advice"
    if st.button("🤖 取得 AI 建議", key="multifactor_ai_recommend"):
        candidates = top_n_plateau_candidates(
            cached.get("grid") or {},
            cached.get("plateau"),
            n=5,
        )
        wf = cached.get("wf") or {}
        oos_metrics = {
            "oos_f1": float(wf.get("oos_f1", 0.0)),
            "oos_sharpe": float(wf.get("oos_sharpe", 0.0)),
            "n_folds": int(wf.get("n_folds", 0)),
        }
        with st.spinner("🤖 呼叫 AI 比對候選..."):
            advice = recommend_weights(candidates, oos_metrics)
        st.session_state[advice_key] = advice

    advice = st.session_state.get(advice_key)
    if advice:
        st.markdown(advice)


def _render_pending_submit_section(cached: dict | None) -> None:
    """🚀 Route C-1：把回測結果提交為「待審權重」，user 在總經面板批准才會生效。

    僅手動觸發 — 無排程、無自動寫回 active。
    """
    st.markdown("---")
    st.markdown("### 📌 提交為待審權重（Route C-1）")
    st.caption(
        "把上方最佳權重 + OOS 指標寫到 `config/macro_weights_pending.json`，"
        "請至「🌐 總經」Tab 頂部 banner 批准。**僅手動觸發**，無排程。"
    )

    if not cached or not (cached.get("opt") or {}).get("weights"):
        st.info("👆 請先按「🚀 跑多因子高原 + walk-forward」產出結果，才能提交。")
        return

    from services.ai_advisor_pending import explain_pending_weights
    from services.macro_weights_store import (
        build_payload_from_multifactor,
        has_pending,
        save_pending,
    )

    if has_pending():
        st.warning(
            "⚠️ 已有一筆待審權重在排隊。再次提交會**覆蓋**舊提交（單槽設計）。"
        )

    if st.button("📌 提交為待審權重", type="primary", key="multifactor_submit_pending"):
        opt = cached.get("opt") or {}
        wf = cached.get("wf") or {}
        sel_keys = cached.get("sel_keys") or []
        metric = cached.get("metric", "f1")
        oos_metrics = {
            "train_f1": float(opt.get("f1", 0.0)),
            "train_sharpe": float(opt.get("sharpe", 0.0)),
            "oos_f1": float(wf.get("oos_f1", 0.0)),
            "oos_sharpe": float(wf.get("oos_sharpe", 0.0)),
            "n_folds": int(wf.get("n_folds", 0)),
        }
        with st.spinner("🤖 呼叫 AI 解讀權重..."):
            ai_text = explain_pending_weights(opt.get("weights") or {}, oos_metrics)
        payload = build_payload_from_multifactor(
            opt, wf, sel_keys, metric, ai_explanation=ai_text,
        )
        try:
            p = save_pending(payload)
        except ValueError as e:
            st.error(f"❌ Schema 驗證失敗：{e}")
            return
        # v19.7: save_pending 回 Path（FS）或 str（GS worksheet ref）
        _loc = p.name if hasattr(p, "name") else str(p)
        st.success(
            f"✅ 已提交至 `{_loc}` — 請至「🌐 總經」Tab 頂部 banner 批准 / 拒絕。"
        )
        st.markdown("**🤖 AI 解讀（提交內容預覽）**")
        st.markdown(ai_text)


def _render_autosearch_section(events, series_by_key) -> None:
    """v19.10：AutoSearch 自動搜尋因子組合 — 跨 session 可暫停 / 可續跑。"""
    from services.auto_search import (
        auto_search_iter,
        get_default_store,
        resume_or_create,
    )
    from services.multi_factor_optimization import (
        FACTOR_POOL_BY_KEY,
        fetch_factor_series,
    )

    with st.expander(
        "🤖 v19.10 AutoSearch — 自動找最佳因子組合（跨 session 可續跑）",
        expanded=True,
    ):
        st.caption(
            "演算法：univariate 預篩 top-K → greedy forward selection → "
            "best subset neighborhood swap refinement。"
            "每次跑滿 N 分鐘自動暫停，狀態持久化到 Google Sheets / local JSON，"
            "下次打開可從中斷處續跑。"
        )

        try:
            store = get_default_store()
        except Exception as e:
            st.error(f"❌ Store 初始化失敗：{type(e).__name__}：{e}")
            return

        backend = getattr(store, "backend_name", "unknown")
        if backend == "google-sheets":
            st.success("💾 Backend：Google Sheets（跨 session 持久化 ✅）")
        else:
            st.warning(
                "💾 Backend：local JSON（Streamlit Cloud reboot 後資料會掉）— "
                "建議設定 v19.7 Google Sheets secrets 啟用跨 session resume。"
            )

        available = list(FACTOR_POOL_BY_KEY.keys())
        col_a, col_b, col_c, col_d = st.columns(4)
        with col_a:
            top_k = st.slider("預篩 top-K", 4, 15, 10, key="as_top_k")
        with col_b:
            max_size = st.slider("最大子集", 2, 6, 5, key="as_max_size")
        with col_c:
            time_budget_min = st.slider(
                "本次跑（分）", 1, 30, 5, key="as_time_budget",
            )
        with col_d:
            st.metric("總 eval 估計", _estimate_total(top_k, max_size))

        # v19.11：預警 lead time 窗口 — 訊號必須在事件前 [min, max] 天內觸發
        # v19.12：加 mode preset，一鍵切「短期 pullback / 長期 regime」
        col_short, col_long, _ = st.columns([1, 1, 2])
        with col_short:
            if st.button("⚡ 短期 pullback (5-30d)", key="as_preset_short",
                         help="短週期：抓 1-4 週短回檔，搭配 VIX_DELTA_5D / HY_SPREAD_DELTA_5D / BREADTH_RSP_SPY_5D"):
                st.session_state["as_min_lead"] = 5
                st.session_state["as_max_lead"] = 30
                st.rerun()
        with col_long:
            if st.button("🏔️ 長期 regime (30-90d)", key="as_preset_long",
                         help="長週期：抓 1-3 個月景氣轉折，搭配既有 VIX / HY_SPREAD / T10Y2Y / SAHM 等"):
                st.session_state["as_min_lead"] = 30
                st.session_state["as_max_lead"] = 90
                st.rerun()

        # v19.13.4：修「The widget with key X was created with a default value
        # but also had its value set via the Session State API」— slider 不再
        # 給 positional default（4th arg），改 session_state 預初始化 pattern
        if "as_min_lead" not in st.session_state:
            st.session_state["as_min_lead"] = 30
        if "as_max_lead" not in st.session_state:
            st.session_state["as_max_lead"] = 90

        col_lt_min, col_lt_max, _ = st.columns([1, 1, 1])
        with col_lt_min:
            min_lead = st.slider(
                "Lead time min（天）", 0, 60, key="as_min_lead",
                help="訊號至少要早於 SPX peak N 天才算 TP。0=只要早就行；30=前 1 個月才算",
            )
        with col_lt_max:
            max_lead = st.slider(
                "Lead time max（天）", 30, 365, key="as_max_lead",
                help="訊號太早也不算 TP（避免假領先）。預設 90=1-3 個月窗口",
            )
        st.caption(
            f"🎯 訊號要在 SPX peak 前 **{min_lead}-{max_lead} 天** 觸發才算命中；"
            "月頻因子套 freq_bonus 0.75 軟懲罰（不剔除）。"
            "v19.12：短期 / 長期 mode 用獨立 job（hash 含 lead time），互不污染"
        )

        st.markdown("---")
        st.markdown("**📋 既有 jobs**")
        try:
            jobs = store.list_jobs()
        except Exception as e:
            st.error(f"❌ list_jobs 失敗：{type(e).__name__}：{e}")
            jobs = []

        if not jobs:
            st.info("（尚無 job — 按下方「🚀 新搜尋」開始）")
        else:
            _render_jobs_table(jobs, store)

        st.markdown("---")
        col_new, col_clear = st.columns([3, 1])
        with col_new:
            new_clicked = st.button(
                "🚀 新搜尋 / 續跑（同 factor pool 自動續）",
                type="primary",
                key="as_run",
            )
        with col_clear:
            if st.button("🗑️ 清除所有 jobs", key="as_clear_all"):
                _clear_all_jobs(store, jobs)
                st.rerun()

        if not new_clicked:
            return

        try:
            job = resume_or_create(
                store, available, top_k=top_k, max_size=max_size,
                min_forward_days=int(min_lead),
                max_forward_days=int(max_lead),
            )
        except Exception as e:
            st.error(f"❌ resume_or_create 失敗：{type(e).__name__}：{e}")
            return

        if job.status == "paused":
            job.status = "running"
            store.save_job(job)

        # 預先確保所有因子 series 都有（lazy-fetch missing）
        import os as _os
        _fred = _os.environ.get("FRED_API_KEY", "")
        all_series = dict(series_by_key) if series_by_key else {}
        missing = [k for k in available if k not in all_series]
        if missing:
            with st.spinner(
                f"lazy-fetch {len(missing)} 個因子 series（{', '.join(missing[:5])}...）",
            ):
                for k in missing:
                    try:
                        all_series[k] = fetch_factor_series(
                            FACTOR_POOL_BY_KEY[k], years=20, fred_api_key=_fred,
                        )
                    except Exception:
                        continue

        returns = _load_spx_returns()
        progress = st.progress(
            min(job.done / max(job.total, 1), 1.0),
            text=f"進度 {job.done}/{job.total}",
        )
        live_msg = st.empty()
        winners_placeholder = st.empty()
        _render_live_winners(store.list_results(job.run_id), winners_placeholder)

        try:
            gen = auto_search_iter(
                job, store, all_series, returns, events,
                time_budget_sec=time_budget_min * 60.0,
                eval_kwargs={
                    "min_forward_days": int(min_lead),
                    "max_forward_days": int(max_lead),
                },
            )
            done_this_run = 0
            for r in gen:
                done_this_run += 1
                progress.progress(
                    min(job.done / max(job.total, 1), 1.0),
                    text=f"進度 {job.done}/{job.total}（本次 +{done_this_run}）",
                )
                live_msg.info(
                    f"剛跑完 [{r.phase}] **{', '.join(r.subset)}**："
                    f"OOS F1=`{r.oos_f1:.3f}` plateau=`{r.plateau_score:.3f}` "
                    f"n_cross=`{r.n_crossings}` composite=`{r.composite:.4f}` "
                    f"({r.elapsed_sec:.1f}s)"
                )
                if done_this_run % 5 == 0:
                    _render_live_winners(
                        store.list_results(job.run_id), winners_placeholder,
                    )
        except Exception as e:
            st.error(f"❌ Worker 例外：{type(e).__name__}：{e}")
            return

        reloaded = store.load_job(job.run_id) or job
        if reloaded.status == "done":
            st.success(f"✅ 全部跑完（{reloaded.done}/{reloaded.total}）— 看下方 winners")
        elif reloaded.status == "paused":
            st.info(
                f"⏸ 時間到自動暫停（{reloaded.done}/{reloaded.total}）— "
                "再按一次「🚀 新搜尋 / 續跑」繼續"
            )
        _render_live_winners(
            store.list_results(job.run_id), winners_placeholder,
            show_apply_btn=True,
        )


def _estimate_total(top_k: int, max_size: int) -> int:
    from services.auto_search import estimate_total_evals
    return estimate_total_evals(top_k, max_size)


def _render_jobs_table(jobs: list, store) -> None:
    rows = []
    for j in jobs[:10]:
        rows.append({
            "run_id": j.run_id,
            "factors": f"{len(j.factor_pool)} 個（hash={j.factor_pool_hash}）",
            "top_K": j.top_k,
            "max_size": j.max_size,
            "進度": f"{j.done}/{j.total}",
            "status": j.status,
            "更新": j.last_update,
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def _render_live_winners(
    results: list, placeholder, show_apply_btn: bool = False,
) -> None:
    # v19.12.1：show_apply_btn 只在 final render 為 True，避免 pre/mid-loop
    # 多次呼叫造成 `as_apply_{run_id}` key duplicate（Streamlit widget key
    # registry 在同一 script run 內不會因 placeholder.container() 替換而清掉）
    from services.auto_search import top_n_winners
    if not results:
        placeholder.empty()
        return
    winners = top_n_winners(results, n=10, by="composite")
    rows = []
    for i, w in enumerate(winners):
        rows.append({
            "排名": i + 1,
            "phase": w.phase,
            "subset": " + ".join(w.subset),
            "OOS F1": f"{w.oos_f1:.3f}",
            "OOS Sharpe": f"{w.oos_sharpe:.3f}",
            "plateau": f"{w.plateau_score:.3f}",
            "n_cross": w.n_crossings,
            "composite": f"{w.composite:.4f}",
        })
    with placeholder.container():
        st.markdown("**🏆 Top-10 winners（按 composite 排序）**")
        st.dataframe(
            pd.DataFrame(rows), use_container_width=True, hide_index=True,
        )
        # v19.13.5：AI 高原 vs Peak 判斷 — 只在 final render 顯示避免 widget
        # key 重複註冊；按鈕觸發避免燒 Gemini quota
        if show_apply_btn and winners:
            _render_autosearch_ai_section(winners)
        # 「採用 top 1」按鈕 — 寫回 multiselect 的 session_state
        # 只在 final render 顯示，避免 widget key 重複註冊
        # v19.13：依當前 AutoSearch lead time 自動路由到對應 mode 的 keys
        if show_apply_btn and winners:
            top = winners[0]
            max_lead = st.session_state.get("as_max_lead", 90)
            target_key = route_apply_key_by_lead(max_lead)
            target_mode = "短期回檔" if target_key.endswith("_pullback") else "總經長期"
            if st.button(
                f"✅ 採用 Top 1：{' + '.join(top.subset)} → {target_mode} mode",
                key=f"as_apply_{top.run_id}",
            ):
                st.session_state[target_key] = list(top.subset)
                st.success(
                    f"已寫入 `{target_key}`：{top.subset}。"
                    f"請到「多因子權重最佳化」expander 切「{target_mode}」mode "
                    "手動跑「🚀 跑多因子高原 + walk-forward」。"
                )


def _autosearch_winners_to_candidates(winners: list) -> list[dict]:
    """v19.13.5：把 AutoSearch SearchResult list 轉成 recommend_weights 需要的
    candidate dict shape（reuse v19.9 事前 AI advice prompt 機制）."""
    candidates: list[dict] = []
    for w in winners:
        candidates.append({
            "weights": dict(w.weights or {}),
            "plateau_score": float(w.plateau_score),
            "f1": float(w.oos_f1),
            "sharpe": float(w.oos_sharpe),
            "n_crossings": int(w.n_crossings),
        })
    return candidates


def _render_autosearch_ai_section(winners: list) -> None:
    """v19.13.5：AutoSearch top-5 winners → AI 高原 vs peak 判斷。

    Reuse v19.9 `recommend_weights`（事前比對 prompt）— 把 SearchResult 轉成
    plateau candidate shape 即可吃同一條 AI 線。
    """
    from services.ai_advisor_pending import recommend_weights

    if not winners:
        return

    top = winners[0]
    top5 = winners[:5]
    advice_key = f"_autosearch_ai_advice_{top.run_id}"

    st.markdown("---")
    st.markdown("### 🤖 AI 高原 vs Peak 判斷（事前比對 Top-5）")
    st.caption(
        "AI 比對 top-5 winners → 建議採用哪組（看 plateau 穩定度 + 風險旗標）。"
        "**按鈕觸發避免燒 quota**；advice 依 run_id cache 不互覆蓋。"
    )

    if st.button("🤖 取得 AI 建議", key=f"as_ai_recommend_{top.run_id}"):
        candidates = _autosearch_winners_to_candidates(top5)
        oos_metrics = {
            "oos_f1": float(top.oos_f1),
            "oos_sharpe": float(top.oos_sharpe),
            "n_folds": int(top.n_folds),
        }
        with st.spinner("🤖 呼叫 AI 比對 top-5 候選..."):
            advice = recommend_weights(candidates, oos_metrics)
        st.session_state[advice_key] = advice

    advice = st.session_state.get(advice_key)
    if advice:
        st.markdown(advice)


def _clear_all_jobs(store, jobs: list) -> None:
    for j in jobs:
        try:
            store.delete_job(j.run_id)
        except Exception:
            continue


def _load_spx_returns() -> pd.Series:
    """讀 SPX parquet 回傳 close 序列（給 Sharpe 計算用）."""
    from pathlib import Path
    p = Path(__file__).resolve().parent.parent / "data_cache" / "spx_history.parquet"
    if not p.exists():
        return pd.Series(dtype=float)
    df = pd.read_parquet(p)
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date")["close"]


# ──────────────────────────────────────────────────────────────
# Phase 3.5：Tab1 Macro Score 預測力驗證（v18.260 Phase 6a）
# v18.279 D 案修正版：加 VIX 閾值校準狀態 banner
# ──────────────────────────────────────────────────────────────
def _render_calibration_banner(cache_dir) -> None:
    """v18.279 D 案修正版：顯示 VIX 閾值校準狀態（5 重 anti-overfit gate）。"""
    import json as _json
    _path = cache_dir / "macro_thresholds_global.json"
    if not _path.exists():
        st.caption(
            "🤖 **VIX 閾值校準**：危機 `>30` / 警戒 `<18`（教科書預設，尚未校準）　|　"
            "下次季度校準：每季首日（1/4/7/10 月）"
        )
        return
    try:
        cfg = _json.loads(_path.read_text(encoding="utf-8"))
    except Exception:
        st.caption("🤖 **VIX 閾值校準**：JSON 解析失敗，使用教科書預設")
        return
    _c = cfg.get("VIX_CRISIS_THRESHOLD", 30.0)
    _w = cfg.get("VIX_WARNING_THRESHOLD", 18.0)
    _ts = cfg.get("last_calibrated", "—")
    _status = cfg.get("status", "—")
    _method = cfg.get("method", "")
    _holdout_rec = cfg.get("holdout_rec_corr")
    _holdout_def = cfg.get("holdout_default_corr")
    _ci_low = cfg.get("bootstrap_ci_low")

    _badge = "✅" if _status == "adopted" else "⚠️"
    st.caption(
        f"🤖 **VIX 閾值校準**：危機 `>{_c}` / 警戒 `<{_w}`　|　"
        f"{_badge} 狀態 `{_status}`　|　最後校準 `{_ts}`"
    )
    _bits = []
    if _method:
        _bits.append(_method)
    if _holdout_rec is not None and _holdout_def is not None:
        _bits.append(f"holdout Spearman rec/def = {_holdout_rec}/{_holdout_def}")
    if _ci_low is not None:
        _bits.append(f"bootstrap CI ≥ {_ci_low}")
    if _bits:
        st.caption("　　　　　　　　" + " | ".join(_bits))


def _render_score_validation_section(events: list, years: int) -> None:
    """📊 重算歷史 Macro Score → 與崩盤事件對齊 → 量化 Tab1 預警命中率。"""
    st.markdown("### 📊 Tab1 Macro Score 預測力驗證（Phase 3.5）")
    st.caption(
        "把 Tab1 那個 0-10 分用 9 個核心指標（PMI / 殖利率曲線 / HY / M2 / FED_BS / "
        "VIX / CPI / 失業率）的歷史 series 逐月重算，跟既有崩盤事件對齊 → 看「景氣變差時 "
        "Tab1 score 是否真的有下降」。"
    )
    # v18.279 D 案修正版：上方顯示校準狀態 banner
    from pathlib import Path as _PathBanner
    _render_calibration_banner(_PathBanner("data_cache"))

    # v18.276 Phase B.2：優先讀 data_cache Parquet（PR #160 v18.275 weekly cron 維護），
    # 不再強制要求 user 先進 Tab1 抓 FRED。Parquet 缺/壞才 fallback 到 session_state。
    from pathlib import Path as _PathSv
    _CACHE_DIR = _PathSv("data_cache")
    _has_parquet = (_CACHE_DIR / "fred_indicators.parquet").exists()
    indicators = st.session_state.get("indicators") or {}
    if _has_parquet:
        st.caption(
            f"📦 資料源：`{_CACHE_DIR}/fred_indicators.parquet`"
            + ("（Tab1 cache 補位 PMI）" if indicators else "（僅 Parquet，PMI 缺位）")
        )
    elif not indicators:
        st.info(
            "⬆️ Parquet 快取尚未生成 — 請等下次週日 cron（或手動觸發 "
            "`update_macro_history` workflow）；或先到「📊 總經 Dashboard」Tab 抓 FRED 後重試"
        )
        return
    else:
        st.caption("📦 資料源：Tab1 session_state（無 Parquet 快取）")

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        lead_months = st.slider(
            "預警觀測：峰前 N 月",
            min_value=3, max_value=12, value=6, step=1,
            help="比較 peak 月 score 與其前 N 個月 score 的降幅",
            key="crisis_score_lead_months",
        )
    with col_b:
        drop_pct = st.slider(
            "命中門檻：score 降幅 ≥",
            min_value=10, max_value=50, value=20, step=5,
            help="峰前→峰時 score 降幅達此 % 才算「預警成功」",
            key="crisis_score_drop_pct",
        )
    with col_c:
        score_years = st.slider(
            "重算年數",
            min_value=5, max_value=20, value=max(years, 15), step=1,
            help="重算 N 年每月 macro_score 序列（最大受限於各 series 涵蓋）",
            key="crisis_score_years",
        )

    if not st.button("📊 跑 Score 驗證", type="secondary", key="crisis_score_run"):
        st.caption("⬆️ 按按鈕開始（重算 ~180 個月，耗時 < 1 秒）")
        return

    from services.macro_validation import (
        SCORE_RULES,
        calc_macro_score_series,
        compute_period_stats,
        load_indicators_from_parquet,
        verify_score_vs_crises,
    )

    # 合併資料源覆蓋率（Parquet ∪ indicators_now）— Parquet 路徑也要驗
    _from_parquet = load_indicators_from_parquet(_CACHE_DIR) if _has_parquet else {}
    n_covered = sum(
        1 for k in SCORE_RULES
        if (_from_parquet.get(k, {}).get("series") is not None)
        or (indicators.get(k, {}).get("series") is not None)
    )
    if n_covered < 3:
        st.error(
            f"❌ 兩個資料源（Parquet + session_state）合計只覆蓋 "
            f"{n_covered}/{len(SCORE_RULES)} 個指標 — "
            "請等 cron bootstrap data_cache/，或到 Tab1 抓 FRED"
        )
        return

    with st.spinner(f"重算 {score_years} 年 macro_score 月序列..."):
        score_df = calc_macro_score_series(
            indicators, years=score_years, freq="ME",
            prefer_parquet=_has_parquet, cache_dir=_CACHE_DIR,
        )

    if score_df.empty:
        st.error("❌ 重算結果空 — indicators 缺 series 或日期範圍無交集")
        return

    st.caption(
        f"✅ 重算 {len(score_df)} 個月，"
        f"平均每月用 {score_df['n_indicators'].mean():.1f} 個指標打分"
    )

    # v18.276 Phase B.2：macro_score 時序 CSV 下載（含 BOM 解 Excel 中文亂碼）
    try:
        _csv_buf = score_df.reset_index().to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            label="📥 下載 macro_score 月序列 CSV",
            data=_csv_buf,
            file_name=f"macro_score_{score_years}y_{pd.Timestamp.today():%Y%m%d}.csv",
            mime="text/csv",
            key="crisis_score_csv_download",
            help="格式：date, score (0-10), phase, n_indicators",
        )
    except Exception as _e:
        st.caption(f"⚠️ CSV 匯出失敗：{_e}")

    # ── 走勢圖 + crisis vlines ─────────────────────────
    try:
        import plotly.graph_objects as go
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=score_df.index, y=score_df["score"],
            mode="lines", name="Macro Score",
            line=dict(color="#1976d2", width=2),
        ))
        # 分數區間參考線
        for y_val, label, color in [
            (8, "高峰", "#f44336"),
            (5, "擴張", "#00c853"),
            (3, "復甦", "#64b5f6"),
        ]:
            fig.add_hline(y=y_val, line_dash="dash", line_color=color,
                          opacity=0.3, annotation_text=label, annotation_position="right")
        # crisis peak vlines
        for ev in events:
            if ev.peak_date is None:
                continue
            peak = pd.Timestamp(ev.peak_date)
            if peak < score_df.index.min() or peak > score_df.index.max():
                continue
            fig.add_vline(x=peak, line_dash="dot", line_color="#d32f2f",
                          opacity=0.5,
                          annotation_text=str(peak.date())[:7],
                          annotation_position="top")
        fig.update_layout(
            height=380,
            yaxis=dict(title="Macro Score (0-10)", range=[0, 10]),
            xaxis=dict(title=""),
            margin=dict(l=20, r=20, t=20, b=20),
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.warning(f"⚠️ 走勢圖繪製失敗：{e}")

    # ── 命中表 ─────────────────────────────────────────
    verify = verify_score_vs_crises(
        score_df, events,
        lead_months=lead_months,
        drop_threshold=drop_pct / 100.0,
    )
    st.markdown("#### 🎯 事件命中表")
    if not verify:
        st.caption("（無事件落在重算範圍內）")
    else:
        rows = []
        for r in verify:
            rows.append({
                "事件": _format_event_name(str(r.peak_date.date())),
                "峰前 score": f"{r.score_lead:.1f}" if r.score_lead is not None else "—",
                "峰時 score": f"{r.score_peak:.1f}" if r.score_peak is not None else "—",
                "谷底 score": f"{r.score_trough:.1f}" if r.score_trough is not None else "—",
                "降幅": f"{r.score_drop_pct:+.1%}" if r.score_drop_pct is not None else "—",
                "預警": "✅" if r.hit else "❌",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        n_hit = sum(1 for r in verify if r.hit)
        n_total = sum(1 for r in verify if r.score_drop_pct is not None)
        if n_total > 0:
            st.metric(
                "Tab1 預警命中率",
                f"{n_hit}/{n_total} = {n_hit / n_total:.0%}",
                help=f"命中 = 峰前 {lead_months} 月 → 峰時 score 降幅 ≥ {drop_pct}%",
            )

    # ── 期間分佈統計 ───────────────────────────────────
    stats = compute_period_stats(score_df, events)
    st.markdown("#### 📊 危機期 vs 平時 score 分佈")
    col_x, col_y, col_z = st.columns(3)
    with col_x:
        cm = stats["crisis_mean"]
        st.metric("危機期平均", f"{cm:.2f}" if cm is not None else "—",
                  help=f"n = {stats['n_crisis']} 月")
    with col_y:
        nm = stats["normal_mean"]
        st.metric("平時平均", f"{nm:.2f}" if nm is not None else "—",
                  help=f"n = {stats['n_normal']} 月")
    with col_z:
        pv = stats["p_value"]
        if pv is not None:
            label = "✅ 顯著" if pv < 0.05 else "⚠️ 不顯著"
            st.metric("Welch t-test", f"p = {pv:.4f}", help=label)
        else:
            st.metric("Welch t-test", "—", help="樣本不足或 scipy 未裝")

    st.caption(
        f"📐 重算邏輯：對 {len(SCORE_RULES)} 個核心指標的歷史 series ffill 對齊月末 → "
        "套用與 fetch_all_indicators() 一致的閾值規則打分 → 聚合公式同 calc_macro_phase。"
        "不含 ADL/DXY/cross-rates（需 monthly change 計算，回測對齊複雜，留 6b）。"
    )


# ──────────────────────────────────────────────────────────────
# Phase 4：策略網格搜尋
# ──────────────────────────────────────────────────────────────
_SIGNAL_THRESHOLD_PRESETS: dict[str, list[float]] = {
    "VIX": [25.0, 30.0, 35.0],
    "HY_SPREAD": [5.0, 7.0, 9.0],
    "T10Y2Y": [0.5, 0.0, -0.5],
    "UNRATE": [4.5, 5.5, 6.5],
}




def _render_strategy_grid_section(
    market_series: pd.Series,
    market_label: str,
    years: int,
    events: list,
) -> None:
    """🧪 4 策略 × 3 門檻 grid search + heatmap + 🤖 AI 建議 (Phase 4+5)。"""
    st.markdown("### 🧪 策略網格搜尋（Phase 4）")
    st.caption(
        "用同一段大盤走勢回測 4 種策略 × 3 個訊號門檻 → 比較「期末資產 / 最大回撤 / Sharpe / 危機期報酬」。"
    )

    col_a, col_b, col_c = st.columns([1, 1, 1.2])
    with col_a:
        signal_key = st.selectbox(
            "訊號",
            options=list(_SIGNAL_THRESHOLD_PRESETS.keys()),
            index=0,
            help="VIX/HY/T10Y2Y/UNRATE 任一",
            key="crisis_grid_signal",
        )
    with col_b:
        metric_label = st.selectbox(
            "Heatmap metric",
            options=["年化 Sharpe", "期末資產", "最大回撤", "危機期報酬"],
            index=0,
            key="crisis_grid_metric",
        )
    with col_c:
        thresholds_str = st.text_input(
            "門檻組合（逗號分隔）",
            value=", ".join(str(x) for x in _SIGNAL_THRESHOLD_PRESETS[signal_key]),
            help="3 個門檻值（會覆蓋預設）",
            key="crisis_grid_thresholds",
        )

    button_clicked = st.button("🧪 跑網格", type="secondary", key="crisis_grid_run")

    from services.crisis_strategy_grid import (
        DEFAULT_STRATEGIES,
        build_heatmap_data,
        grid_search,
        rank_results,
        results_to_dataframe,
    )
    from services.macro_signal_lookback import DEFAULT_SIGNALS, fetch_signal_series

    if button_clicked:
        try:
            thresholds = [float(x.strip()) for x in thresholds_str.split(",") if x.strip()]
        except ValueError:
            st.error("❌ 門檻必須是數字（逗號分隔），例如 25, 30, 35")
            return
        if len(thresholds) < 1:
            st.error("❌ 至少需要 1 個門檻")
            return

        spec = next((s for s in DEFAULT_SIGNALS if s.key == signal_key), None)
        if spec is None:
            st.error(f"❌ 找不到訊號 spec：{signal_key}")
            return

        fred_key = os.environ.get("FRED_API_KEY", "")
        if spec.source == "fred" and not fred_key:
            st.warning(f"⚠️ {signal_key} 來自 FRED 但未設定 FRED_API_KEY — 無法跑")
            return

        with st.spinner(f"抓取 {signal_key} {years} 年歷史..."):
            sig_series = fetch_signal_series(spec, years=max(years, 10), fred_api_key=fred_key)
        if sig_series.empty:
            st.error(f"❌ 訊號 {signal_key} 抓取失敗或無資料")
            return

        with st.spinner(f"跑 {len(DEFAULT_STRATEGIES)} 策略 × {len(thresholds)} 門檻 = {len(DEFAULT_STRATEGIES) * len(thresholds)} 組..."):
            results = grid_search(
                market_series, sig_series, thresholds,
                specs=DEFAULT_STRATEGIES,
                direction=spec.direction,
            )

        st.session_state[_GRID_CACHE_KEY] = {
            "results": results,
            "events": events,
            "signal_key": signal_key,
            "signal_label": spec.label,
            "metric_label": metric_label,
            "market_label": market_label,
            "thresholds": thresholds,
        }

    cached = st.session_state.get(_GRID_CACHE_KEY)
    if not cached:
        st.caption("⬆️ 按按鈕開始（需先抓訊號序列，約 5 秒）")
        return

    results = cached["results"]
    metric_label = cached["metric_label"]
    signal_key = cached["signal_key"]
    market_label = cached["market_label"]

    metric_map = {
        "年化 Sharpe": ("sharpe_ratio", False, "%.2f"),
        "期末資產": ("final_value", False, "%.1f"),
        "最大回撤": ("max_drawdown_pct", True, "%.2%%"),  # asc=True：越淺越好
        "危機期報酬": ("crisis_return_pct", False, "%.2%%"),
    }
    metric_col, ascending, _fmt = metric_map[metric_label]

    # Heatmap
    st.markdown("#### 🔥 Heatmap")
    hm = build_heatmap_data(results, metric=metric_col)

    try:
        import plotly.express as px
        is_pct = metric_col in ("max_drawdown_pct", "crisis_return_pct")
        fig = px.imshow(
            hm.values,
            labels=dict(x=f"{signal_key} 門檻", y="策略", color=metric_label),
            x=[str(c) for c in hm.columns],
            y=list(hm.index),
            text_auto=".2f" if not is_pct else ".1%",
            color_continuous_scale="RdYlGn" if not ascending else "RdYlGn_r",
            aspect="auto",
        )
        fig.update_layout(
            title=f"{market_label} × {signal_key} × {metric_label}",
            height=380,
            margin=dict(l=40, r=20, t=50, b=40),
        )
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.warning(f"plotly heatmap 失敗：{e}，改用 DataFrame")
        st.dataframe(hm, use_container_width=True)

    # Top-N 排行
    st.markdown(f"#### 🏆 Top 5 by {metric_label}")
    top = rank_results(results, by=metric_col, top_n=5, ascending=ascending)
    if not top.empty:
        # 換算成人類可讀
        top_view = top[[
            "strategy_label", "threshold",
            "final_value", "total_return_pct",
            "max_drawdown_pct", "sharpe_ratio", "crisis_return_pct",
            "n_trigger_days",
        ]].copy()
        top_view.columns = [
            "策略", "門檻", "期末資產", "總報酬", "最大回撤", "年化 Sharpe", "危機期報酬", "觸發天數",
        ]
        for col, fmt in [
            ("總報酬", "{:+.1%}"),
            ("最大回撤", "{:.1%}"),
            ("危機期報酬", "{:+.1%}"),
            ("期末資產", "{:.1f}"),
            ("年化 Sharpe", "{:.2f}"),
        ]:
            top_view[col] = top_view[col].apply(lambda v, _f=fmt: _f.format(v) if pd.notna(v) else "—")
        st.dataframe(top_view, use_container_width=True, hide_index=True)

    # 完整 grid
    with st.expander("📋 完整網格（12 cells）"):
        df_full = results_to_dataframe(results)
        df_full_view = df_full[[
            "strategy_label", "threshold",
            "final_value", "total_return_pct",
            "max_drawdown_pct", "sharpe_ratio", "crisis_return_pct",
            "n_trigger_days", "n_total_days",
        ]].copy()
        df_full_view.columns = [
            "策略", "門檻", "期末資產", "總報酬", "最大回撤", "年化 Sharpe", "危機期報酬", "觸發天數", "總天數",
        ]
        st.dataframe(df_full_view, use_container_width=True, hide_index=True)

    st.caption(
        "📐 策略說明：buy_and_hold = baseline 滿倉；signal_exit = 訊號→全現金；"
        "signal_half = 訊號→半倉；buy_dip = 訊號 + 大盤跌 ≥5% → 1.5× 加碼。"
        "|  起始資產 = 100；倉位 t = f(訊號 t-1) 避免前視偏誤。"
    )


# ──────────────────────────────────────────────────────────────
# Phase E：全球 macro_score × 台股 TWII 對照
# ──────────────────────────────────────────────────────────────
def _render_phase_e_cross_source_section(events: list, years: int) -> None:
    """🌏 fund FRED 合成 macro_score × stock TWII 同框比對 + lead-lag 分析."""
    st.markdown("### 🌏 全球 macro_score × 台股 TWII 對照（Phase E）")
    st.caption(
        "把 fund 的全球 FRED 合成 0-10 macro_score 與台股 TWII 走勢同框 → "
        "用 cross-correlation 找 macro_score 領先 TWII 月變化率最強相關的月數，"
        "並列出每場 crisis 事件當下的 macro_score 平均。"
        "資料源：`data_cache/fred_indicators.parquet` + `data_cache/twii_history.parquet`"
        "（每週日 cron 更新）。"
    )

    from pathlib import Path
    cache_dir = Path("data_cache")
    twii_path = cache_dir / "twii_history.parquet"
    fred_path = cache_dir / "fred_indicators.parquet"
    if not twii_path.exists():
        st.info(
            "⏳ `data_cache/twii_history.parquet` 尚未生成。"
            "等下次每週日 cron / 或手動觸發 `update_macro_history.yml` "
            "workflow + bootstrap=true 即可填滿 15 年 TWII。"
        )
        return
    if not fred_path.exists():
        st.info(
            "⏳ `data_cache/fred_indicators.parquet` 尚未生成。"
            "等下次每週日 cron / 或手動觸發 workflow + bootstrap=true。"
        )
        return

    col_a, col_b = st.columns(2)
    with col_a:
        max_lag = st.slider(
            "Cross-correlation 最大 lag（±月）",
            min_value=3, max_value=18, value=12, step=1,
            help="正 lag = macro_score 領先 TWII；負 lag = 落後",
            key="phase_e_max_lag",
        )
    with col_b:
        lookback = st.slider(
            "Crisis 前回看月數（peak 前 N 月平均 score）",
            min_value=3, max_value=12, value=6, step=1,
            key="phase_e_lookback",
        )

    if not st.button("🌏 跑 Phase E 對照分析", type="secondary",
                     key="phase_e_run"):
        st.caption("⬆️ 按按鈕開始（讀 Parquet → 對齊月末 → 算 cross-correlation）")
        return

    # ── 跑分析 ──
    from services.cross_source_compare import (
        align_score_with_twii,
        compute_lead_lag_correlation,
        find_best_lead_lag,
        load_twii_from_parquet,
        summarize_crisis_score_around_events,
    )
    from services.macro_validation import calc_macro_score_series

    with st.spinner("讀 Parquet + 重算月度 macro_score ..."):
        score_df = calc_macro_score_series(
            indicators_now=None,
            years=int(years),
            freq="ME",
            prefer_parquet=True,
            cache_dir=cache_dir,
        )
        twii_s = load_twii_from_parquet(cache_dir)

    if score_df.empty:
        st.error("❌ macro_score series 為空 — 檢查 fred_indicators.parquet 是否完整")
        return
    if twii_s.empty:
        st.error("❌ TWII series 為空 — 檢查 twii_history.parquet 是否完整")
        return

    aligned = align_score_with_twii(score_df, twii_s, freq="ME")
    if aligned.empty:
        st.warning("⚠️ macro_score 與 TWII 月末無重疊期間 — 確認兩 Parquet 時間區間")
        return

    st.caption(
        f"📅 對齊區間：{aligned.index.min():%Y-%m} ~ {aligned.index.max():%Y-%m}"
        f"（{len(aligned)} 月）｜📊 TWII 區間：{twii_s.index.min():%Y-%m-%d} ~ "
        f"{twii_s.index.max():%Y-%m-%d}（{len(twii_s):,} 日）"
    )

    # ── Cross-correlation 統計 ──
    corr_df = compute_lead_lag_correlation(aligned, max_lag_months=int(max_lag))
    best_lag, best_corr = find_best_lead_lag(corr_df, prefer_positive=True)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("最佳領先期（月）",
                  f"{best_lag:+d}" if best_lag is not None else "—",
                  help="正值 = macro_score 領先 TWII 月變化率")
    with c2:
        st.metric("該期相關係數",
                  f"{best_corr:.3f}" if best_corr is not None else "—",
                  help="Pearson correlation，越接近 1 越強正相關")
    with c3:
        st.metric("分析月數", f"{len(aligned)}",
                  help="重疊月數（macro_score ∩ TWII 月末）")

    # ── 雙軸圖 ──
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots

        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(
            go.Scatter(x=aligned.index, y=aligned["score"],
                       mode="lines", name="macro_score",
                       line=dict(color="#1976d2", width=2)),
            secondary_y=False,
        )
        fig.add_trace(
            go.Scatter(x=aligned.index, y=aligned["twii_close"],
                       mode="lines", name="TWII 收盤",
                       line=dict(color="#d32f2f", width=1.5)),
            secondary_y=True,
        )
        # 加 crisis 紅區
        for ev in events or []:
            d = ev.to_dict() if hasattr(ev, "to_dict") else {}
            x0 = d.get("peak_date")
            x1 = d.get("recovery_date") or d.get("trough_date")
            if x0 and x1:
                fig.add_vrect(x0=x0, x1=x1,
                              fillcolor="#9e9e9e", opacity=0.10,
                              line_width=0)
        fig.update_layout(
            height=420,
            margin=dict(l=20, r=20, t=20, b=20),
            legend=dict(orientation="h", y=1.05),
        )
        fig.update_yaxes(title_text="macro_score (0-10)", secondary_y=False)
        fig.update_yaxes(title_text="TWII 收盤", secondary_y=True)
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:  # noqa: BLE001
        st.warning(f"⚠️ 雙軸圖繪製失敗：{e}")

    # ── Lead-lag 表 ──
    with st.expander("📐 Cross-correlation 完整表（lag → 相關係數）"):
        if corr_df.empty:
            st.caption("（無資料）")
        else:
            disp = corr_df.copy()
            disp["correlation"] = disp["correlation"].round(4)
            st.dataframe(disp, use_container_width=True, hide_index=True)

    # ── Crisis 對應 macro_score 平均 ──
    st.markdown("#### 🎯 每場 Crisis 事件對應的 macro_score")
    summary = summarize_crisis_score_around_events(
        events or [], score_df, lookback_months=int(lookback),
    )
    if not summary:
        st.caption("（無 crisis 事件 / 缺 macro_score 對應期）")
    else:
        df_sum = pd.DataFrame(summary)
        for col in ("score_lookback_avg", "score_at_peak",
                    "score_at_trough", "score_drop_from_avg"):
            if col in df_sum.columns:
                df_sum[col] = df_sum[col].apply(
                    lambda x: round(x, 2) if x is not None and pd.notna(x) else None)
        st.dataframe(df_sum, use_container_width=True, hide_index=True)

    # ── CSV 下載 ──
    try:
        ts = pd.Timestamp.today().strftime("%Y%m%d")
        st.download_button(
            "📥 對齊月資料 CSV（score × TWII × mom%）",
            data=aligned.to_csv().encode("utf-8-sig"),
            file_name=f"phase_e_aligned_{ts}.csv",
            mime="text/csv",
            key="phase_e_aligned_csv",
        )
    except Exception as e:  # noqa: BLE001
        st.caption(f"⚠️ CSV 匯出失敗：{e}")


# ──────────────────────────────────────────────────────────────
# Phase 5：AI 策略建議（移至 Phase E 之後，確保 AI 能讀完上方所有結果）
# ──────────────────────────────────────────────────────────────
def _render_phase_5_ai_section() -> None:
    """🤖 Phase 5 入口：從 session_state 取 grid cache、重算 top-5，餵給 AI 解讀。

    為何放最後：AI prompt 需要綜合 Phase 4 grid + Phase E macro_score 對照結果，
    所以 render 順序固定在最尾，避免 Gemini 看不到上半部 context。
    """
    cached = st.session_state.get(_GRID_CACHE_KEY)
    if not cached:
        st.markdown("### 🤖 AI 策略建議（Phase 5）")
        st.caption("⬆️ 請先按上方「🧪 跑網格」產生策略結果，再回來請 AI 解讀。")
        return

    # 重算 top-5（鏡像 _render_strategy_grid_section 內的 metric_map / rank_results）
    from services.crisis_strategy_grid import rank_results

    metric_label = cached["metric_label"]
    _metric_map = {
        "年化 Sharpe":  ("sharpe_ratio",     False),
        "期末資產":    ("final_value",      False),
        "最大回撤":    ("max_drawdown_pct", True),
        "危機期報酬":  ("crisis_return_pct", False),
    }
    metric_col, ascending = _metric_map.get(metric_label, ("sharpe_ratio", False))
    top = rank_results(cached["results"], by=metric_col, top_n=5, ascending=ascending)
    _render_ai_advice_block(cached, top)


def _render_ai_advice_block(cached: dict, top_df: pd.DataFrame) -> None:
    """🤖 把 Phase 1 危機事件 + Phase 4 grid + Top-1 丟給 Gemini 解讀。"""
    st.markdown("### 🤖 AI 策略建議（Phase 5）")
    st.caption(
        "把上面的歷史危機事件 + 4×N 網格結果 + Top-1 最佳 cell 丟給 Gemini，"
        "請它用白話講「為什麼這策略勝出 / 風險盲點 / 怎麼做」。"
    )

    from services.ai_service import get_gemini_keys

    keys = get_gemini_keys()
    if not keys:
        st.warning("⚠️ 未設定 Gemini API Key — 請設定環境變數 `GEMINI_API_KEY`（或 secrets）後再試。")
        return

    if not st.button("🤖 請 Gemini 解讀最佳策略", key="crisis_ai_advice_run"):
        st.caption(f"⬆️ 按按鈕請 AI 解讀（可用 key 數：{len(keys)}）")
        return

    from services.crisis_ai_advisor import generate_strategy_advice
    from services.crisis_strategy_grid import results_to_dataframe

    results = cached["results"]
    grid_df = results_to_dataframe(results)
    top_result = None
    if top_df is not None and not top_df.empty:
        top_result = top_df.iloc[0].to_dict()

    signal_label_full = f"{cached['signal_key']}（{cached.get('signal_label', '—')}）"

    with st.spinner("Gemini 解讀中（約 10-20 秒）..."):
        advice = generate_strategy_advice(
            events=cached.get("events", []),
            grid_df=grid_df,
            top_result=top_result,
            signal_label=signal_label_full,
            market_label=cached.get("market_label", "—"),
            metric_label=cached.get("metric_label", "Sharpe"),
        )
    st.markdown(advice)
