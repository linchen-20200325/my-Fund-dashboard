"""v19.198 P1-6:⑩ MK 買賣點對比 + ⑪ Bollinger 詳圖(從 fund_grp_health_extras 主檔抽出)。"""
from __future__ import annotations

import streamlit as st

from shared.colors import GH_BG_CARD, GH_FG_PRIMARY, MATERIAL_GREEN, MATERIAL_ORANGE, MATERIAL_RED, MD_BLUE_500, MD_DEEP_ORANGE_400, MD_GREEN_A200, MD_PURPLE_500, STREAMLIT_BG, WARN_AMBER

from ui.helpers.fund_grp_health._utils import _safe_num


def _render_mk_signal_table(funds: list) -> None:
    """⑩ MK 買賣點表(跨檔對比)。

    每檔基金顯示:
      - 資產屬性(核心/衛星/混合)
      - 操作訊號(依目前景氣階段)
      - 自動配比建議(股/債%)
      - 買賣水平線(buy1~3 / sell1~3,sourced from precision metrics)
      - 現價在哪一段(用顏色暗示)

    依賴 st.session_state.phase_info(總經 Tab 載入後寫入);若缺則顯示提示。
    SSOT:ui/helpers/macro_helpers.mk_fund_signal
    """
    st.divider()
    st.markdown("### 🎯 MK 買賣點對比(跨檔)")

    _phase_info = st.session_state.get("phase_info") if hasattr(st, "session_state") else None
    if not _phase_info:
        st.caption("⬜ 需先到 🌐 總經 Tab 點選「載入總經資料」,才能算景氣位階 + MK 操作訊號")
        return

    try:
        from ui.helpers.macro_helpers import mk_fund_signal
    except Exception as e:
        st.caption(f"⬜ MK 訊號模組載入失敗:{type(e).__name__}: {e}")
        return

    _phase = _phase_info.get("phase") or "擴張"
    _score = _phase_info.get("score") or 5.0
    st.caption(
        f"目前景氣階段:**{_phase}**({_score}/10)。"
        "**買 1 / 賣 1** = 年高 -1σ / 年低 +1σ(輕微);"
        "**買 3 / 賣 3** = -3σ / +3σ(極端)。現價落在哪一段以紅綠標示。"
    )

    _rows = []
    for _f in funds:
        _code = _f.get("code", "?")
        _name = (_f.get("name") or _code)[:20]
        _m = _f.get("metrics") or {}
        _mj = _f.get("moneydj_raw") or {}

        # MK signal(依景氣階段)
        try:
            _sig = mk_fund_signal(_f, _phase, _score)
            _asset_class = _sig.get("asset_class", "—")
            _sig_label = _sig.get("label", "—")
        except Exception:
            _asset_class = "—"
            _sig_label = "—"

        # 買賣水平線
        _b1 = _safe_num(_m.get("buy1") or _mj.get("buy1"))
        _b3 = _safe_num(_m.get("buy3") or _mj.get("buy3"))
        _s1 = _safe_num(_m.get("sell1") or _mj.get("sell1"))
        _s3 = _safe_num(_m.get("sell3") or _mj.get("sell3"))
        _nav = _safe_num(_m.get("nav") or _mj.get("nav_latest"))

        # 現價區段判定(red=超跌, green=超漲, blue=區間內)
        if _nav is None:
            _zone = "—"
        elif _b3 is not None and _nav <= _b3:
            _zone = "🟢 ≤買3(深跌)"
        elif _b1 is not None and _nav <= _b1:
            _zone = "🟢 ≤買1(小跌)"
        elif _s3 is not None and _nav >= _s3:
            _zone = "🔴 ≥賣3(大漲)"
        elif _s1 is not None and _nav >= _s1:
            _zone = "🟡 ≥賣1(小漲)"
        else:
            _zone = "⚪ 區間內"

        _rows.append({
            "基金": f"{_name} ({_code})",
            "資產屬性": _asset_class,
            "操作訊號": _sig_label,
            "買 3 (深跌)": f"{_b3:.2f}" if _b3 is not None else "—",
            "買 1 (小跌)": f"{_b1:.2f}" if _b1 is not None else "—",
            "現價": f"{_nav:.2f}" if _nav is not None else "—",
            "賣 1 (小漲)": f"{_s1:.2f}" if _s1 is not None else "—",
            "賣 3 (大漲)": f"{_s3:.2f}" if _s3 is not None else "—",
            "現價位階": _zone,
        })

    try:
        import pandas as pd
        st.dataframe(pd.DataFrame(_rows), use_container_width=True, hide_index=True)
        _has_sig = sum(1 for r in _rows if r["操作訊號"] != "—")
        if _has_sig < len(_rows):
            st.caption(
                f"⬜ {len(_rows) - _has_sig} / {len(_rows)} 檔基金 MK 訊號計算失敗"
                "(可能 metrics 缺 buy/sell levels)"
            )
    except Exception as e:
        st.caption(f"⬜ MK 表渲染失敗:{type(e).__name__}: {e}")


def _render_bollinger_expanders(funds: list) -> None:
    """⑪ Bollinger 可展開詳圖(逐檔 expander,點開才 render)。

    UX 設計:N 檔基金不能同時 render 大 chart,改為每檔一個 collapsed expander,
    user 點開哪檔才畫該檔 chart(Streamlit 天然 lazy)。

    每檔 chart 內容:
      - NAV 主線
      - Bollinger ±2σ 通道(半透明填色)
      - MA20 / MA60 dotted line
      - 配息標記(triangle-up + 金額)
      - 買 1/2/3 + 賣 1/2/3 水平線

    對齊 Tab 2 line 339-413 邏輯,精簡掉副圖(三率動能柱)。
    """
    st.divider()
    st.markdown("### 📈 Bollinger 詳圖(點選展開)")
    st.caption("N 檔同時繪製會混亂 → 改為 expander,點開哪檔才 render(節省效能)。")

    try:
        import plotly.graph_objects as go
        import pandas as pd
    except Exception as e:
        st.caption(f"⬜ Plotly / pandas 載入失敗:{type(e).__name__}: {e}")
        return

    for _f in funds:
        _code = _f.get("code", "?")
        _name = (_f.get("name") or _code)[:30]
        _series = _f.get("series")

        with st.expander(f"📈 {_name}　·　{_code}", expanded=False):
            if _series is None or len(_series) < 20:
                st.caption("⬜ NAV 序列不足 20 天,無法繪 Bollinger")
                continue

            _m = _f.get("metrics") or {}
            _mj = _f.get("moneydj_raw") or {}
            try:
                _s = _series.dropna() if hasattr(_series, "dropna") else _series
                _df = _s.reset_index() if hasattr(_s, "reset_index") else pd.DataFrame(_s)
                _df.columns = ["date", "nav"]

                _bb_period = min(20, len(_s))
                _bb_ma = _s.rolling(_bb_period).mean()
                _bb_std = _s.rolling(_bb_period).std()
                _bb_up = (_bb_ma + 2 * _bb_std).dropna()
                _bb_dn = (_bb_ma - 2 * _bb_std).dropna()

                fig = go.Figure()
                # BB 上軌(隱形,只為了 fill)
                fig.add_trace(go.Scatter(
                    x=_bb_up.index, y=_bb_up.values, name="BB上軌",
                    line=dict(color="rgba(33,150,243,0.25)", width=1),
                    showlegend=False,
                ))
                # BB 下軌 + fill
                fig.add_trace(go.Scatter(
                    x=_bb_dn.index, y=_bb_dn.values, name="布林通道(±2σ)",
                    fill="tonexty",
                    fillcolor="rgba(33,150,243,0.08)",
                    line=dict(color="rgba(33,150,243,0.25)", width=1),
                ))
                # MA20
                fig.add_trace(go.Scatter(
                    x=_bb_ma.dropna().index, y=_bb_ma.dropna().values,
                    name="MA20",
                    line=dict(color=MATERIAL_ORANGE, width=1, dash="dot"),
                ))
                # MA60(若資料夠)
                if len(_s) >= 60:
                    _ma60 = _s.rolling(60).mean()
                    fig.add_trace(go.Scatter(
                        x=_ma60.dropna().index, y=_ma60.dropna().values,
                        name="MA60",
                        line=dict(color=MD_PURPLE_500, width=1, dash="dot"),
                    ))
                # NAV 主線
                fig.add_trace(go.Scatter(
                    x=_df["date"], y=_df["nav"], name="淨值",
                    mode="lines",
                    line=dict(color=MD_BLUE_500, width=2),
                ))

                # 配息標記
                _divs = _mj.get("dividends") or _f.get("dividends") or []
                _d_dates, _d_navs, _d_texts = [], [], []
                for _cd in (_divs if isinstance(_divs, list) else []):
                    try:
                        _cd_date = pd.Timestamp(_cd.get("date", ""))
                        if _cd_date in _s.index:
                            _cd_nav = float(_s.loc[_cd_date])
                        else:
                            _near = _s.index[_s.index.get_indexer(
                                [_cd_date], method="nearest")[0]]
                            _cd_nav = float(_s.loc[_near])
                            _cd_date = _near
                        _cd_amt = _cd.get("amount") or _cd.get("dividend") or ""
                        _d_dates.append(_cd_date)
                        _d_navs.append(_cd_nav)
                        _d_texts.append(f"💰 {_cd_amt}" if _cd_amt else "💰")
                    except Exception:
                        continue
                if _d_dates:
                    fig.add_trace(go.Scatter(
                        x=_d_dates, y=_d_navs,
                        mode="markers+text", name="配息日",
                        marker=dict(symbol="triangle-up", size=10, color="#ffd600"),
                        text=_d_texts, textposition="top center",
                        textfont=dict(size=9, color="#ffd600"),
                        hovertemplate="%{text}<br>淨值:%{y:.4f}<extra></extra>",
                    ))

                # MK 買賣水平線
                for _bv, _bl, _bc in [
                    (_safe_num(_m.get("buy1")), "買1 (年高-1σ)", MD_GREEN_A200),
                    (_safe_num(_m.get("buy2")), "買2 (年高-2σ)", MATERIAL_GREEN),
                    (_safe_num(_m.get("buy3")), "買3 (年高-3σ)", MD_PURPLE_500),
                ]:
                    if _bv is not None:
                        fig.add_hline(y=_bv, line_color=_bc, line_dash="dot",
                                      annotation_text=_bl,
                                      annotation_font_color=_bc,
                                      annotation_position="bottom right")
                for _sv, _sl, _sc in [
                    (_safe_num(_m.get("sell1")), "賣1 (年低+1σ)", WARN_AMBER),
                    (_safe_num(_m.get("sell2")), "賣2 (年低+2σ)", MD_DEEP_ORANGE_400),
                    (_safe_num(_m.get("sell3")), "賣3 (年低+3σ)", MATERIAL_RED),
                ]:
                    if _sv is not None:
                        fig.add_hline(y=_sv, line_color=_sc, line_dash="dash",
                                      annotation_text=_sl,
                                      annotation_font_color=_sc,
                                      annotation_position="top right")

                fig.update_layout(
                    paper_bgcolor=STREAMLIT_BG, plot_bgcolor=GH_BG_CARD,
                    font_color=GH_FG_PRIMARY, height=360,
                    margin=dict(t=20, b=20, l=40, r=20),
                    legend=dict(orientation="h", font_size=10, y=1.08),
                    hovermode="x unified",
                )
                st.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                st.caption(f"⬜ {_code} chart 渲染失敗:{type(e).__name__}: {e}")


# ════════════════════════════════════════════════════════════════
# v19.122 P1 AI — 跨檔統一評論
# ════════════════════════════════════════════════════════════════
