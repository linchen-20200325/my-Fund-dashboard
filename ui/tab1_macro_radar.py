"""ui/tab1_macro_radar.py — v19.262 P3-A4 從 tab1_macro.py 抽出的 🎯 短線雷達區塊。

從 `ui/tab1_macro.py:render_macro_tab()` body 內抽出獨立 section,降低主檔 LOC:
- `render_short_radar_section(fred_key, show_l3)` — render 入口

內容包含:
- ④ ⚡ 短線風險雷達(10 燈 1-day 急殺早期警報)
- ⑤ 🌊 流動性壓力預警引擎(深水區 4 因子)— button-triggered, L3 only

設計:
- 不依賴 render_macro_tab 的 closure local var,全部走參數注入
- `_make_radar_sparkline` lazy import(避免循環依賴 tab1_macro)
- `_safe_series` 自定義(同邏輯;原為 render_macro_tab 內部函式)
- §8.2:L3 UI helper,純渲染 + session_state 讀寫(stash _macro_liquidity)
"""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from shared.colors import (
    GH_BG_PRIMARY,
    GH_BORDER,
    GRAY_55,
    GRAY_AA,
    MATERIAL_GREEN,
    MATERIAL_RED,
    TRAFFIC_GREEN,
    TRAFFIC_NEUTRAL,
    TRAFFIC_RED,
    WHITE,
)


def _safe_series(s):
    """v19.262 — 同 render_macro_tab 原 inline 函式;dropna + tail(60)。"""
    import pandas as _pd_mac
    if s is None:
        return None
    try:
        if not isinstance(s, _pd_mac.Series):
            s = _pd_mac.Series(s)
        return s.dropna().tail(60)
    except Exception:
        return None


def render_short_radar_section(
    fred_key: str,
    show_l3: bool = True,
) -> None:
    """渲染 🎯 短線雷達 section(10 燈雷達 + 流動性壓力預警引擎)。

    Args:
        fred_key: FRED API key str(可空,空時跳過網路呼叫)
        show_l3: L3 toggle,False 時隱藏流動性引擎按鈕
    """
    from ui.tab1_macro import _make_radar_sparkline  # lazy 避循環

    st.divider()
    st.markdown("## 🎯 短線雷達")
    st.caption("即時 risk-off ｜ 10 燈雷達 + 流動性壓力預警")

    # ── v19.20 ⚡ 短線風險雷達（10 燈 1-day 急殺早期警報）──
    st.divider()
    st.markdown("### ④ ⚡ 短線風險雷達（24H Risk-Off Velocity Radar ｜ 日級急殺確認）")
    st.caption("10 個 1-day 動量／情緒／位階訊號 — 補拐點偵測中心（月～季級慢）之短缺，"
               "捕捉 1-day 急殺前的早期警報："
               "VIX 級距+期限結構 ｜ HY 信用日變化 ｜ 10Y 殖利率衝擊 ｜ MOVE 債券恐慌 ｜ "
               "SPX 均線破口 ｜ SOX 半導體 ｜ 防禦/攻擊輪動 ｜ Put/Call ｜ 亞洲夜盤")
    # 真實 FRED API key 為 32 字元；短於 30 視為測試/未設定 → 跳過避免 16 次網路呼叫拖滿 AppTest budget
    # v19.21：頂部雙速合議已抓過雷達並 cache 在 session_state，這裡直接讀避免重複網路呼叫
    _top_cache = st.session_state.get("_radar_v1921_top")
    if _top_cache is not None:
        _radar, _radar_sum = _top_cache
    elif not fred_key or len(str(fred_key).strip()) < 30:
        _radar = None
        _radar_sum = None
    else:
        try:
            from services.risk_radar import detect_risk_radar, summarize_radar
            _radar = detect_risk_radar(fred_key)
            _radar_sum = summarize_radar(_radar)
            st.session_state["_radar_v1921_top"] = (_radar, _radar_sum)
        except Exception as _radar_e:  # noqa: BLE001
            _radar = None
            _radar_sum = None
            st.warning(f"⚠️ 風險雷達失敗：{str(_radar_e)[:120]}")

    if _radar and _radar_sum:
        st.markdown(
            f"<div style='background:{GH_BG_PRIMARY};border:2px solid {_radar_sum['color']};"
            f"border-radius:10px;padding:10px 16px;margin:6px 0'>"
            f"<span style='color:{_radar_sum['color']};font-size:18px;font-weight:800'>"
            f"整體狀態：{_radar_sum['level']}</span>"
            f"<span style='color:{GRAY_AA};margin-left:20px;font-size:13px'>"
            f"🔴 {_radar_sum['red']} ｜ 🟡 {_radar_sum['yellow']} ｜ "
            f"🟢 {_radar_sum['green']} ｜ ⬜ {_radar_sum['gray']}</span>"
            f"</div>", unsafe_allow_html=True)

        _radar_cards = [
            ("vix_level",       "🌪️ VIX 恐慌指數"),
            ("vix_term_struct", "📐 VIX 期限結構"),
            ("hy_oas_delta",    "💳 HY 信用日變化"),
            ("yield_10y_shock", "📈 10Y 殖利率衝擊"),
            ("move_level",      "🌊 MOVE 債市波動"),
            ("spx_trend_break", "📉 SPX 均線破口"),
            ("sox_drop",        "🔌 半導體單日跌幅"),
            ("sector_rotation", "🔄 防禦 vs 攻擊"),
            ("put_call_ratio",  "📊 Put/Call 比率"),
            ("asia_overnight",  "🌏 亞洲夜盤領先"),
        ]
        for _row in (_radar_cards[:5], _radar_cards[5:]):
            _cols_radar = st.columns(5)
            for _col_r, (_key_r, _title_r) in zip(_cols_radar, _row):
                _dr = _radar.get(_key_r) or {}
                _sig_r = _dr.get("signal", "⬜ 無資料")
                _col_c_r = _dr.get("color", TRAFFIC_NEUTRAL)
                _val_r = _dr.get("value")
                _note_r = _dr.get("note", "")
                _label_r = _dr.get("label", "")
                _trend_r = _dr.get("trend") or []  # v19.133: ~8 期 list
                _val_txt_r = "—" if _val_r is None else f"{_val_r}"
                # F-RECON-1 phase 2 v19.87 — 殖利率燈附「FRED vs Yahoo」對帳 chip
                _rec_chip_r = ''
                _rec_r = _dr.get('reconcile') if isinstance(_dr, dict) else None
                if isinstance(_rec_r, dict) and _rec_r.get('status') in ('agree', 'disagree', 'a_missing', 'b_missing'):
                    _rec_emoji_r = {'agree': '✅', 'disagree': '⚠️',
                                    'a_missing': '⬜', 'b_missing': '⬜'}.get(_rec_r.get('status'), '⬜')
                    _rec_col_r = {'agree': TRAFFIC_GREEN, 'disagree': TRAFFIC_RED}.get(
                        _rec_r.get('status'), TRAFFIC_NEUTRAL)
                    _rec_chip_r = (
                        f"<br/><span style='color:{_rec_col_r};font-size:9px;'>"
                        f"{_rec_emoji_r} 對帳：{_rec_r.get('status','')}</span>"
                    )
                with _col_r:
                    st.markdown(
                        f"<div style='background:{GH_BG_PRIMARY};border:2px solid {_col_c_r};"
                        f"border-radius:10px;padding:10px 12px 6px;margin:4px 0;"
                        f"min-height:165px;"
                        f"display:flex;flex-direction:column;justify-content:space-between'>"
                        f"<div>"
                        f"<div style='color:{TRAFFIC_NEUTRAL};font-size:10px;letter-spacing:1px'>"
                        f"{_title_r}</div>"
                        f"<div style='color:{_col_c_r};font-size:15px;font-weight:800;"
                        f"margin:4px 0 6px'>{_sig_r}</div>"
                        f"<div style='color:{WHITE};font-weight:700;font-size:14px'>"
                        f"值 {_val_txt_r}</div>"
                        f"</div>"
                        f"<div style='color:{GRAY_AA};font-size:9px;border-top:1px solid {GH_BORDER};"
                        f"padding-top:4px;margin-top:4px;line-height:1.3'>{_note_r}"
                        f"<br/><span style='color:{GRAY_55}'>{_label_r}</span>{_rec_chip_r}</div>"
                        f"</div>", unsafe_allow_html=True)
                    # v19.133 — 嵌入 sparkline + threshold(若有 trend)
                    _sp = _make_radar_sparkline(_trend_r, _key_r, _col_c_r)
                    if _sp is not None:
                        st.plotly_chart(_sp, use_container_width=True,
                                        key=f"radar_sp_{_key_r}",
                                        config={"displayModeBar": False})
        st.caption("📡 資料源：FRED + Yahoo Chart API（NAS proxy）｜閾值：🟢平靜 → 🟡警戒 → 🔴警報"
                   "｜v19.133 卡片底部 sparkline 含指標特定 threshold 線")



    # ── 🌊 流動性壓力預警引擎（v18.228：按鈕觸發，不塞總經主載入路徑）──
    def _load_liquidity_factors() -> None:
        with st.spinner("抓取 FRED / DefiLlama / Yahoo 流動性因子（約 10–30 秒）..."):
            try:
                from services.liquidity_engine import (
                    compute_liquidity_score, fetch_liquidity_factors)
                _f = fetch_liquidity_factors(fred_key)
                st.session_state.liquidity_factors = _f
                st.session_state.liquidity_score = compute_liquidity_score(_f)
            except Exception as _le:
                st.session_state.liquidity_factors = {}
                st.session_state.liquidity_score = None
                st.error(f"流動性因子載入失敗：{_le}")

    _liq_score = st.session_state.get("liquidity_score")
    _liq_facs  = st.session_state.get("liquidity_factors") or {}
    if show_l3 and not _liq_score:
        st.caption("🌊 **流動性壓力預警引擎**（深水區 4 因子）為進階觀察，"
                   "獨立抓取以免拖慢總經主載入。")
        if st.button("🌊 載入流動性壓力預警引擎", key="btn_load_liquidity"):
            _load_liquidity_factors()
            st.rerun()
    if _liq_score and show_l3:
        with st.expander("⑤ 🌊 流動性壓力預警引擎（深水區 4 因子 ｜ lead SPX 1-3 週）", expanded=False):
            from ui.components.macro_card import make_sparkline as _mk_sl2
            from services.liquidity_engine import liquidity_verdict
            if st.button("🔄 重新抓取流動性因子", key="btn_reload_liquidity"):
                _load_liquidity_factors()
                st.rerun()
            st.caption("⚠️ 進階觀察｜XCCY 為代理指標、權重未經真值校準，僅供方向性參考")
            st.info(liquidity_verdict(_liq_score, _liq_facs))
            # v18.255 stash 給 AI 白話總體檢
            try:
                _liq_top_contrib = []
                for _b in (_liq_score.get("breakdown") or [])[:3]:
                    _liq_top_contrib.append({
                        "name": str(_b.get("name", ""))[:20],
                        "contrib": float(_b.get("contrib", 0) or 0),
                    })
                st.session_state["_macro_liquidity"] = {
                    "value": float(_liq_score.get("value", 0) or 0),
                    "tier": str(_liq_score.get("tier", "—")),
                    "signal": str(_liq_score.get("signal", "")),
                    "verdict": liquidity_verdict(_liq_score, _liq_facs),
                    "top_contrib": _liq_top_contrib,
                }
            except Exception:
                pass

            # ── 壓力分數 + 分級 + 逐因子貢獻 ──────────────────
            _cs_l, _cs_r = st.columns([1, 2])
            with _cs_l:
                st.metric("流動性壓力分數", f"{_liq_score['value']:+.2f}",
                          _liq_score["tier"])
                st.markdown(
                    f"<div style='font-size:1.3rem'>{_liq_score['signal']} "
                    f"<b style='color:{_liq_score['color']}'>"
                    f"{_liq_score['tier']}</b></div>",
                    unsafe_allow_html=True)
            with _cs_r:
                st.markdown("**逐因子貢獻**（紅=推升壓力／綠=壓低）")
                _bd = _liq_score.get("breakdown") or []
                if _bd:
                    _bfig = go.Figure(go.Bar(
                        x=[b["name"][:10] for b in _bd],
                        y=[b["contrib"] for b in _bd],
                        marker_color=[MATERIAL_RED if b["contrib"] > 0
                                      else MATERIAL_GREEN for b in _bd],
                        hovertemplate="%{x}: 貢獻 %{y:+.3f}<extra></extra>"))
                    _bfig.add_hline(y=0, line_color=GRAY_55, line_width=1)
                    _bfig.update_layout(
                        height=170, margin=dict(t=4, b=40, l=4, r=4),
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)", showlegend=False,
                        xaxis=dict(showgrid=False, tickangle=-30,
                                   tickfont=dict(size=9), fixedrange=True),
                        yaxis=dict(showgrid=False, zeroline=False,
                                   fixedrange=True))
                    st.plotly_chart(_bfig, use_container_width=True,
                                    config={"displayModeBar": False})

            # ── 合成壓力分數歷史趨勢（警戒線 1／危機線 2）──────
            _scs = _safe_series(_liq_score.get("score_series"))
            if _scs is not None and len(_scs) >= 2:
                st.markdown("**📉 流動性壓力分數趨勢**")
                _trend = _mk_sl2(_scs, threshold_warn=1.0,
                                 threshold_crit=2.0, high_is_bad=True,
                                 lookback=120, height=160)
                if _trend is not None:
                    st.plotly_chart(_trend, use_container_width=True,
                                    config={"displayModeBar": False})
            st.divider()

            # ── 三個 risk-off 壓力因子卡 ─────────────────────
            _fcols = st.columns(3)
            for _col, _fk in zip(
                    _fcols, ("XCCY_PROXY", "CARRY_UNWIND", "MOVE_VIX")):
                _fe = _liq_facs.get(_fk)
                with _col:
                    if not _fe:
                        st.caption(f"（{_fk} 無資料）")
                        continue
                    _fz = _fe.get("zscore")
                    st.markdown(f"**{_fe['signal']} {_fe['name']}**")
                    st.markdown(
                        f"值 `{_fe['value']}{_fe.get('unit', '')}`　"
                        f"Z `{'—' if _fz is None else f'{_fz:+.2f}'}`")
                    _fs = _safe_series(_fe.get("series"))
                    _fsl = (_mk_sl2(_fs, high_is_bad=True, lookback=60,
                                    height=110)
                            if _fs is not None else None)
                    if _fsl is not None:
                        st.plotly_chart(_fsl, use_container_width=True,
                                        config={"displayModeBar": False})
                    st.caption(_fe.get("desc", ""))
            st.divider()

            # ── SSR 鏈上子彈水位（獨立，不計入壓力分數）──────
            _ssr = _liq_facs.get("SSR")
            if _ssr:
                _ssr_l, _ssr_r = st.columns([1.5, 1])
                with _ssr_l:
                    st.markdown(f"**🔫 {_ssr['name']}**")
                    _ssr_s = _safe_series(_ssr.get("series"))
                    _ssr_fig = (_mk_sl2(_ssr_s, high_is_bad=False,
                                        lookback=60, height=140)
                                if _ssr_s is not None else None)
                    if _ssr_fig is not None:
                        st.plotly_chart(_ssr_fig, use_container_width=True,
                                        config={"displayModeBar": False})
                    else:
                        st.caption("📡 資料載入中或筆數不足…")
                with _ssr_r:
                    _sz = _ssr.get("zscore")
                    st.markdown(
                        "**怎麼看？**　SSR = BTC市值 ÷ 穩定幣市值，"
                        "**獨立於壓力分數**（不計入）。\n\n"
                        f"**目前讀數**　{_ssr['signal']} SSR "
                        f"`{_ssr['value']}`，Z "
                        f"`{'—' if _sz is None else f'{_sz:+.2f}'}`\n\n"
                        "SSR 低(Z<0)=鏈上法幣子彈多=潛在買盤強；高=子彈耗盡")

