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
            help="在峰前 M 天內搜尋訊號『從非警戒跨越到警戒』的最早轉折日（edge detection）",
            key="crisis_signal_max_lookback",
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

        from services.macro_signal_lookback import (
            DEFAULT_SIGNALS,
            compute_signal_hit_rate,
            fetch_signal_series,
            lookback_all_signals,
        )

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
        st.session_state[_PHASE3_CACHE_KEY] = {"sig": _p3_sig, "results": results}
        _cached_p3 = st.session_state[_PHASE3_CACHE_KEY]

    if not _cached_p3:
        st.caption("⬆️ 按按鈕開始（會抓 FRED + Yahoo 多年歷史，需要 ~10 秒）")
        return

    # ── 從 cache 渲染 ──
    from services.macro_signal_lookback import DEFAULT_SIGNALS, compute_signal_hit_rate
    results = _cached_p3["results"]

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
        for spec in DEFAULT_SIGNALS:
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
