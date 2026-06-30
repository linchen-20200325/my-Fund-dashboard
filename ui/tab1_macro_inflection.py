"""ui/tab1_macro_inflection.py — v19.262 P3-A6 從 tab1_macro.py 抽出的 ⚠️ 拐點警報區塊。

從 `ui/tab1_macro.py:render_macro_tab()` body 內抽出獨立 section,降低主檔 LOC:
- `render_inflection_alert_section(ind, phase, fred_key, show_l3)` — render 入口

內容包含:
- ① 🎯 全域導航塔(戰情室三儀表:薩姆 + SLOOS + 廣度)
- 🚦 持倉紅綠燈(讀 portfolio_funds session_state)
- 📋 本週操作清單(L1 新手 checklist)
- ② 🎯 拐點偵測中心(熊市預警 月級結構訊號 5 卡)
- 📊 歷史回測:倒掛翻正後 6/12/18M SPX 表現 expander

設計:
- 不依賴 render_macro_tab 的 closure local var,全部走參數注入
- phase 注入後內部 derive ph / alloc / advice(原 closure 邏輯)
- `_apply_tp_thresholds` lazy import 避循環
- §8.2:L3 UI helper,純渲染 + session_state 讀寫
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from services.macro import (
    backtest_turning_points,
    detect_turning_points,
)
from shared.colors import (
    BG_DARK_AMBER_1,
    BG_DARK_NAVY_4,
    BG_DARK_RED_1,
    BG_DARK_RED_2,
    GH_BG_CARD,
    GH_BG_PRIMARY,
    GH_BORDER,
    GH_FG_PRIMARY,
    GRAY_44,
    GRAY_55,
    GRAY_66,
    GRAY_AA,
    GRAY_CC,
    MATERIAL_GREEN,
    MATERIAL_ORANGE,
    MATERIAL_RED,
    MD_BLUE_300,
    MD_GREEN_A400,
    MD_PURPLE_500,
    STREAMLIT_BG,
    TRAFFIC_GREEN,
    TRAFFIC_NEUTRAL,
    WHITE,
)


def render_inflection_alert_section(
    ind: dict,
    phase: dict,
    fred_key: str,
    show_l3: bool = True,
) -> None:
    """渲染 ⚠️ 拐點警報 section(戰情室 + 持倉紅綠燈 + 拐點偵測中心 + 倒掛回測)。

    Args:
        ind: indicators dict(總經指標)
        phase: phase_info dict(由 calc_macro_phase 產出)
        fred_key: FRED API key str
        show_l3: L3 toggle(本 section 預設皆顯示;保留參數供未來細部 gating)
    """
    from ui.tab1_macro import _apply_tp_thresholds  # lazy 避循環

    ph = phase["phase"]
    alloc = phase["alloc"]
    advice = phase.get("advice", "")

    st.divider()
    st.markdown("## ⚠️ 拐點警報")
    st.caption("領先警報 3-9 月 ｜ 全域導航塔 + 拐點偵測中心")

    # ══════════════════════════════════════════════════
    # V5 全域導航塔（War Room）── 三圓形氣象儀表
    # ══════════════════════════════════════════════════
    st.markdown("### ① 🎯 全域導航塔（戰情室三儀表：薩姆 + SLOOS + 廣度）")
    _sahm_d  = ind.get("SAHM")  or {}
    _sloos_d = ind.get("SLOOS") or {}
    _adl_d   = ind.get("ADL")   or {}
    _sahm_v  = float(_sahm_d.get("value")  or 0)
    _sloos_v = float(_sloos_d.get("value") or 0)
    _adl_v   = float(_adl_d.get("value")   or 0)

    _gg1, _gg2, _gg3 = st.columns(3)

    def _make_gauge(val, title, suffix, rng, thresholds, danger_above=True):
        """thresholds: [(limit, color_hex), ...] 從低到高"""
        steps = []
        prev = rng[0]
        for lim, col in thresholds:
            steps.append({"range": [prev, lim], "color": col})
            prev = lim
        steps.append({"range": [prev, rng[1]], "color": thresholds[-1][1]})
        # 指針顏色：超過最後閾值的 limit 為警報色
        danger_lim = thresholds[-1][0]
        needle_c = (MATERIAL_RED if (danger_above and val >= danger_lim)
                    else (MATERIAL_GREEN if (not danger_above and val <= danger_lim)
                    else MATERIAL_ORANGE))
        f = go.Figure(go.Indicator(
            mode="gauge+number",
            value=val,
            title={"text": title, "font": {"size": 13, "color": GRAY_AA}},
            number={"suffix": suffix, "font": {"size": 22, "color": GH_FG_PRIMARY},
                    "valueformat": ".2f"},
            gauge={"axis": {"range": rng, "tickcolor": GRAY_44,
                            "tickfont": {"size": 9, "color": GRAY_66}},
                   "bar":  {"color": needle_c, "thickness": 0.25},
                   "bgcolor": GH_BG_CARD,
                   "bordercolor": GH_BORDER,
                   "steps": steps,
                   "threshold": {"line": {"color": MATERIAL_RED, "width": 3},
                                 "thickness": 0.8, "value": danger_lim}}))
        f.update_layout(paper_bgcolor=STREAMLIT_BG, font_color=GH_FG_PRIMARY,
                        height=200, margin=dict(t=40, b=5, l=15, r=15))
        return f

    with _gg1:
        st.plotly_chart(_make_gauge(
            _sahm_v, "薩姆規則<br>衰退機率", "pp", [0, 1.0],
            [(0.3, "#0a2a0a"), (0.5, BG_DARK_AMBER_1), (1.0, BG_DARK_RED_1)],
            danger_above=True), use_container_width=True)
        _sahm_sig = ("🔴 **衰退觸發** ≥0.5" if _sahm_v >= 0.5
                     else "🟡 警戒區 ≥0.3" if _sahm_v >= 0.3
                     else "🟢 安全 <0.3")
        st.markdown(f"<div style='text-align:center;font-size:12px'>{_sahm_sig}</div>",
                    unsafe_allow_html=True)
        if not _sahm_d:
            st.caption("⚠️ FRED SAHMREALTIME 未取得（API Key 或網路）")
        # T2: Tooltip
        with st.expander("ℹ️ 薩姆規則說明", expanded=False):
            st.markdown("**薩姆規則（Sahm Rule）**：當失業率的3個月滾動平均比過去12個月最低點高出 ≥0.5 百分點，代表美國進入衰退。⚠️ 新手白話：儀表板紅色時，代表景氣已經轉壞，建議降低高風險基金比重。")

    with _gg2:
        st.plotly_chart(_make_gauge(
            _sloos_v, "SLOOS 放貸寬鬆度<br>銀行信貸標準", "%", [-30, 60],
            [(-5, "#0a2a0a"), (20, BG_DARK_AMBER_1), (60, BG_DARK_RED_1)],
            danger_above=True), use_container_width=True)
        _sloos_sig = ("🔴 **銀行緊縮** >20%" if _sloos_v > 20
                      else "🟡 中性偏緊 >0%" if _sloos_v > 0
                      else "🟢 信貸寬鬆 <0%")
        st.markdown(f"<div style='text-align:center;font-size:12px'>{_sloos_sig}</div>",
                    unsafe_allow_html=True)
        if not _sloos_d:
            st.caption("⚠️ FRED DRTSCILM 未取得")
        # T2: Tooltip
        with st.expander("ℹ️ SLOOS 說明", expanded=False):
            st.markdown("**SLOOS（銀行放貸標準）**：美聯儲季度調查，正值=銀行收緊放貸（壞），負值=銀行放寬放貸（好）。⚠️ 新手白話：儀表板紅色時，代表銀行不願貸款，企業融資困難，景氣降溫訊號。")

    with _gg3:
        # ADL = RSP/SPY 市場寬度 (% MoM change, negative = narrowing breadth = bad)
        st.plotly_chart(_make_gauge(
            _adl_v, "市場健康度<br>RSP/SPY 廣度", "%", [-10, 10],
            [(-5, BG_DARK_RED_1), (0, BG_DARK_AMBER_1), (5, "#0a2a0a")],
            danger_above=False), use_container_width=True)
        _adl_sig = ("🟢 市場廣度健康" if _adl_v > 2
                    else "🔴 **廣度收窄** 虛假繁榮" if _adl_v < -2
                    else "🟡 市場廣度持平")
        st.markdown(f"<div style='text-align:center;font-size:12px'>{_adl_sig}</div>",
                    unsafe_allow_html=True)
        # T2: Tooltip
        with st.expander("ℹ️ 市場廣度說明", expanded=False):
            st.markdown("**RSP/SPY 廣度（市場廣度）**：RSP = 等權重標普500，SPY = 市值加權。RSP/SPY 比值上升 = 中小型股參與行情（健康），下降 = 只有大型股撐盤（虛胖）。⚠️ 新手白話：紅色時代表漲幅集中少數大股，市場不穩健，小心追高。")

    # ── 持倉紅綠燈列表（War Room Middle）──────────────────────────
    _pf_all = st.session_state.get("portfolio_funds", [])
    _pf_loaded = [f for f in _pf_all if f.get("loaded")]
    # v19.190：去重 — portfolio_funds 可能含同 code 重複載入（多次 reload 累積），
    # 導致紅綠燈同一檔列出 2-3 次。依 code 保留第一筆（upper-strip 正規化）。
    _seen_tl: set = set()
    _pf_dedup = []
    for _f in _pf_loaded:
        _c = str(_f.get("code", "") or "").strip().upper()
        if _c and _c in _seen_tl:
            continue
        _seen_tl.add(_c)
        _pf_dedup.append(_f)
    _pf_loaded = _pf_dedup
    if _pf_loaded:
        st.markdown("#### 🚦 持倉紅綠燈")
        _tl_html = ""
        for _pf in _pf_loaded:
            _pf_code  = _pf.get("code","?")
            _pf_name  = _pf.get("fund_name") or _pf_code
            _pf_m     = _pf.get("metrics") or _pf.get("m") or {}
            _pf_divs  = _pf.get("dividends") or []
            _pf_nav   = float(_pf_m.get("nav") or 0)
            _pf_b1    = float(_pf_m.get("buy1") or 0)   # v18.6: 年高-1σ（小跌）
            _pf_b2    = float(_pf_m.get("buy2") or 0)   # 年高-2σ（急跌）
            _pf_b3    = float(_pf_m.get("buy3") or 0)   # 年高-3σ（大跌）
            _pf_s1    = float(_pf_m.get("sell1") or 0)  # 年低+1σ
            _pf_bbd   = float(_pf_m.get("bb_lower") or 0)
            _pf_bbu   = float(_pf_m.get("bb_upper") or 0)
            _pf_ret1y = float(_pf_m.get("ret_1y") or 0)
            _pf_adr   = float(_pf_m.get("annual_div_rate") or 0)
            _pf_core  = "🛡️ 核" if _pf.get("is_core") else "⚡ 衛"
            # 燈號判定（v18.6: σ + 布林雙確認 升級）
            _tl_icon, _tl_bg, _tl_bc, _tl_reason = "🟢", "#061a06", MATERIAL_GREEN, "淨值穩定，含息報酬正常"
            # 雙確認買 = σ 買點觸發 + 布林下軌觸碰
            _double_buy = (_pf_b1 > 0 and _pf_nav > 0 and _pf_nav <= _pf_b1
                           and _pf_bbd > 0 and _pf_nav <= _pf_bbd)
            _double_sell = (_pf_s1 > 0 and _pf_nav > 0 and _pf_nav >= _pf_s1
                            and _pf_bbu > 0 and _pf_nav >= _pf_bbu)
            if _pf_adr > 0 and _pf_ret1y < _pf_adr:
                _tl_icon, _tl_bg, _tl_bc = "🔴", BG_DARK_RED_2, MATERIAL_RED
                _tl_reason = f"吃本金警示：含息報酬 {_pf_ret1y:.1f}% < 配息率 {_pf_adr:.1f}%"
            elif _double_buy:
                _tl_icon, _tl_bg, _tl_bc = "🟢🟢", "#0a3a1a", MD_GREEN_A400
                _tl_reason = f"σ+布林雙確認買 NAV {_pf_nav:.4f} ≤ 買1({_pf_b1:.4f}) & 布林下軌"
            elif _double_sell:
                _tl_icon, _tl_bg, _tl_bc = "🔔🔔", "#3a0a0a", MATERIAL_RED
                _tl_reason = f"σ+布林雙確認賣 NAV {_pf_nav:.4f} ≥ 賣1({_pf_s1:.4f}) & 布林上軌"
            elif _pf_b3 > 0 and _pf_nav > 0 and _pf_nav <= _pf_b3:
                _tl_icon, _tl_bg, _tl_bc = "🟡", "#1a0a2a", MD_PURPLE_500
                _tl_reason = f"大跌大買訊號 NAV {_pf_nav:.4f} ≤ 買3({_pf_b3:.4f})"
            elif _pf_b1 > 0 and _pf_nav > 0 and _pf_nav <= _pf_b1:
                _tl_icon, _tl_bg, _tl_bc = "🟡", "#1a1500", MATERIAL_ORANGE
                _tl_reason = f"小跌小買訊號 NAV {_pf_nav:.4f} ≤ 買1({_pf_b1:.4f})"
            elif not _pf_m:
                _tl_icon, _tl_bg, _tl_bc = "⬜", GH_BG_CARD, GRAY_55
                _tl_reason = "資料尚未載入"
            _tl_html += (
                f"<div style='background:{_tl_bg};border:1px solid {_tl_bc};"
                f"border-radius:8px;padding:8px 14px;margin:4px 0;"
                f"display:flex;align-items:center;gap:14px'>"
                f"<span style='font-size:20px'>{_tl_icon}</span>"
                f"<span style='color:{MD_BLUE_300};font-size:11px;width:32px'>{_pf_core}</span>"
                f"<span style='color:{GRAY_CC};font-size:12px;flex:1'>"
                f"<b>{_pf_name[:20]}</b></span>"
                f"<span style='color:{_tl_bc};font-size:11px'>{_tl_reason}</span>"
                f"</div>"
            )
        st.markdown(_tl_html, unsafe_allow_html=True)
    else:
        st.markdown(
            f"<div style='background:{GH_BG_CARD};border:1px solid {GH_BORDER};border-radius:8px;"
            f"padding:10px 16px;color:{GRAY_55};font-size:12px;text-align:center'>"
            "🚦 持倉紅綠燈：請先至「📊 組合基金」Tab 新增並載入基金，即可在此顯示即時燈號</div>",
            unsafe_allow_html=True)

    # ── AI 每日一句結論（v15.2 移除：使用者反饋過於簡略）──
    st.divider()

    # ══════════════════════════════════════════════════
    # L1 新手待辦清單（所有等級均顯示）
    # ══════════════════════════════════════════════════
    _w_icon2  = phase.get("weather_icon", "⛅")
    _w_label2 = phase.get("weather_label", "多雲")
    _l1_stock = alloc.get("股票", 50)
    _l1_bond  = alloc.get("債券", 30)
    _l1_cash  = alloc.get("現金", 20)
    _l1_checks = [
        f"確認核心部位是否符合 AI 建議：股 {_l1_stock}% / 債 {_l1_bond}% / 現金 {_l1_cash}%",
    ]
    if _sahm_v >= 0.5:
        _l1_checks.append(f"⚠️ **薩姆衰退警報已觸發**（{_sahm_v:.2f}pp）：暫停衛星加碼，保留防守型部位")
    if _sloos_v > 20:
        _l1_checks.append(f"📊 **銀行緊縮偵測**（SLOOS {_sloos_v:.1f}%）：高收益債基金降至 10% 以下")
    if _adl_v < -2:
        _l1_checks.append(f"🌍 **市場廣度警示**（RSP/SPY {_adl_v:.2f}%）：減少主題/集中型基金")
    _l1_checks.append("定期定額不停扣（除非景氣位階進入「高峰」且 VIX < 15）")
    _l1_checks.append(f"本週核心原則：景氣「{ph}」，{(advice or '均衡配置，嚴守紀律')[:40]}。")
    _l1_md = "\n".join(f"- [ ] {c}" for c in _l1_checks)
    st.markdown(
        f"<div style='background:{GH_BG_PRIMARY};border:1px solid {GH_BORDER};border-radius:12px;"
        f"padding:16px 20px;margin:8px 0'>"
        f"<div style='color:{GH_FG_PRIMARY};font-weight:700;margin-bottom:10px'>"
        f"📋 本週操作清單（{_w_label2} {_w_icon2}）</div></div>",
        unsafe_allow_html=True)
    st.markdown(_l1_md)

    # ══════════════════════════════════════════════════
    # ── v19.18 🎯 拐點偵測中心（合併 v18.20 PMI/yield + v18.250 三件套）──
    st.divider()
    st.markdown("### ② 🎯 拐點偵測中心（熊市預警主面板 ｜ 月級結構訊號）")
    st.caption("集中所有景氣翻轉訊號：製造業新訂單－庫存擴散 ｜ 10Y-2Y 殖利率倒掛翻正 ｜ "
               "HY 信用利差 ｜ 薩姆規則 ｜ CFNAI 領先指標 ｜ 歷史回測 ｜ 變數重要性")
    # v19.49：spinner block 已預抓並 cache 在 session_state，直接撈避免重複網路呼叫
    _tp = st.session_state.get("_tp_v1948_top")
    if _tp is None:
        try:
            _tp = detect_turning_points(fred_key)
            st.session_state["_tp_v1948_top"] = _tp
        except Exception as _tp_e:  # noqa: BLE001
            _tp = None
            st.warning(f"⚠️ 拐點偵測失敗：{str(_tp_e)[:120]}")

    if _tp:
        _tp_c1, _tp_c2 = st.columns(2)
        for _col, _key, _title in [
            (_tp_c1, "pmi_diff",    "🏭 新訂單 − 庫存擴散"),
            (_tp_c2, "yield_curve", "📉 10Y − 2Y 殖利率利差"),
        ]:
            _d = _tp[_key]
            _sig = _d.get("signal", "⬜")
            _col_c = _d.get("color", TRAFFIC_NEUTRAL)
            _val = _d.get("value")
            _prev = _d.get("prev")
            _trend = _d.get("trend") or []
            _note = _d.get("note", "")
            _label = _d.get("label", "")
            _val_txt = ("—" if _val is None else
                        (f"{_val:+.2f}pp" if _key == "pmi_diff"
                         else f"{_val:+.2f}%"))
            _prev_txt = ("—" if _prev is None else
                         (f"{_prev:+.2f}pp" if _key == "pmi_diff"
                          else f"{_prev:+.2f}%"))
            with _col:
                st.markdown(
                    f"<div style='background:{GH_BG_PRIMARY};border:2px solid {_col_c};"
                    f"border-radius:12px;padding:14px 18px;margin:6px 0'>"
                    f"<div style='color:{TRAFFIC_NEUTRAL};font-size:11px;letter-spacing:1px'>"
                    f"{_title}</div>"
                    f"<div style='color:{_col_c};font-size:18px;font-weight:800;"
                    f"margin:6px 0 10px'>{_sig}</div>"
                    f"<div style='display:flex;gap:24px;flex-wrap:wrap;margin-bottom:8px'>"
                    f"<div><div style='color:{TRAFFIC_NEUTRAL};font-size:10px'>本期</div>"
                    f"<div style='color:{WHITE};font-weight:700;font-size:16px'>{_val_txt}</div></div>"
                    f"<div><div style='color:{TRAFFIC_NEUTRAL};font-size:10px'>前期</div>"
                    f"<div style='color:{GRAY_AA};font-weight:700;font-size:16px'>{_prev_txt}</div></div>"
                    f"</div>"
                    f"<div style='color:{GRAY_AA};font-size:11px;border-top:1px solid {GH_BORDER};"
                    f"padding-top:6px;margin-top:4px'>{_note}</div>"
                    f"<div style='color:{GRAY_55};font-size:10px;margin-top:4px'>{_label}</div>"
                    f"</div>", unsafe_allow_html=True)
                # Sparkline（近 6~8 期）
                if _trend and len(_trend) >= 2:
                    try:
                        import plotly.graph_objects as _go_tp
                        _spfig = _go_tp.Figure()
                        _spfig.add_trace(_go_tp.Scatter(
                            y=_trend, mode="lines+markers",
                            line=dict(color=_col_c, width=2),
                            marker=dict(size=5, color=_col_c),
                            showlegend=False,
                        ))
                        # v19.132 — 指標特定 threshold lines(SSOT)
                        _apply_tp_thresholds(_spfig, _key)
                        _spfig.update_layout(
                            height=110, margin=dict(l=10, r=10, t=4, b=4),
                            plot_bgcolor=GH_BG_PRIMARY, paper_bgcolor=GH_BG_PRIMARY,
                            xaxis=dict(visible=False),
                            yaxis=dict(showgrid=False, color=GRAY_55,
                                       tickfont=dict(size=9)),
                        )
                        st.plotly_chart(_spfig, use_container_width=True,
                                        key=f"sp_tp_{_key}")
                    except Exception:
                        pass  # smoke-allow-pass
        st.caption(
            "💡 **拐點解讀**："
            "🚀 新訂單擴散由負轉正 = 製造業景氣領先指標反轉，通常領先 EPS 修正 1~2 季｜"
            "⚠️ 10Y-2Y 倒掛翻正 = 衰退末期，歷史經驗為股市底部累積區（1990/2000/2008/2020）"
        )

        # ── v18.250 第二排：信用 / 衰退 / 領先 三組景氣反轉拐點 ─────
        _tp_c3, _tp_c4, _tp_c5 = st.columns(3)
        for _col, _key, _title in [
            (_tp_c3, "hy_spread", "💳 HY 信用利差"),
            (_tp_c4, "sahm_rule", "📉 薩姆規則（衰退警報）"),
            (_tp_c5, "lei_cfnai", "🔭 CFNAI 領先指標"),
        ]:
            _d = _tp.get(_key)
            if not _d:
                continue
            _sig = _d.get("signal", "⬜")
            _col_c = _d.get("color", TRAFFIC_NEUTRAL)
            _val = _d.get("value")
            _prev = _d.get("prev")
            _trend = _d.get("trend") or []
            _note = _d.get("note", "")
            _label = _d.get("label", "")
            # 單位後綴隨指標調整
            _unit = "%" if _key == "hy_spread" else ""
            _val_txt = "—" if _val is None else f"{_val:+.2f}{_unit}"
            _prev_txt = "—" if _prev is None else f"{_prev:+.2f}{_unit}"
            with _col:
                st.markdown(
                    f"<div style='background:{GH_BG_PRIMARY};border:2px solid {_col_c};"
                    f"border-radius:12px;padding:14px 18px;margin:6px 0'>"
                    f"<div style='color:{TRAFFIC_NEUTRAL};font-size:11px;letter-spacing:1px'>"
                    f"{_title}</div>"
                    f"<div style='color:{_col_c};font-size:18px;font-weight:800;"
                    f"margin:6px 0 10px'>{_sig}</div>"
                    f"<div style='display:flex;gap:24px;flex-wrap:wrap;margin-bottom:8px'>"
                    f"<div><div style='color:{TRAFFIC_NEUTRAL};font-size:10px'>本期</div>"
                    f"<div style='color:{WHITE};font-weight:700;font-size:16px'>{_val_txt}</div></div>"
                    f"<div><div style='color:{TRAFFIC_NEUTRAL};font-size:10px'>前期</div>"
                    f"<div style='color:{GRAY_AA};font-weight:700;font-size:16px'>{_prev_txt}</div></div>"
                    f"</div>"
                    f"<div style='color:{GRAY_AA};font-size:11px;border-top:1px solid {GH_BORDER};"
                    f"padding-top:6px;margin-top:4px'>{_note}</div>"
                    f"<div style='color:{GRAY_55};font-size:10px;margin-top:4px'>{_label}</div>"
                    f"</div>", unsafe_allow_html=True)
                if _trend and len(_trend) >= 2:
                    try:
                        import plotly.graph_objects as _go_tp
                        _spfig = _go_tp.Figure()
                        _spfig.add_trace(_go_tp.Scatter(
                            y=_trend, mode="lines+markers",
                            line=dict(color=_col_c, width=2),
                            marker=dict(size=5, color=_col_c),
                            showlegend=False,
                        ))
                        # v19.132 — 指標特定 threshold lines(SSOT)
                        _apply_tp_thresholds(_spfig, _key)
                        _spfig.update_layout(
                            height=110, margin=dict(l=10, r=10, t=4, b=4),
                            plot_bgcolor=GH_BG_PRIMARY, paper_bgcolor=GH_BG_PRIMARY,
                            xaxis=dict(visible=False),
                            yaxis=dict(showgrid=False, color=GRAY_55,
                                       tickfont=dict(size=9)),
                        )
                        st.plotly_chart(_spfig, use_container_width=True,
                                        key=f"sp_tp_{_key}")
                    except Exception:
                        pass  # smoke-allow-pass
        st.caption(
            "🎯 **景氣反轉三件套**："
            "💳 HY 利差高位回落 = 信用市場開始正常化｜"
            "📉 薩姆規則跌破 0.5 = 衰退警報解除（底部布局訊號）｜"
            "🔭 CFNAI 3M 均值由負轉正 = 85 指標領先翻揚（擴張確認）"
        )

    # ── v18.21 📊 拐點訊號歷史回測（倒掛翻正 vs SPX）─────────────
    with st.expander(
        "📊 歷史回測：倒掛翻正後 6/12/18M SPX 表現",
        expanded=False,
    ):
        try:
            _bt = backtest_turning_points(fred_key)
        except Exception as _bt_e:  # noqa: BLE001
            _bt = {"source_ok": False, "note": str(_bt_e)[:120],
                   "events": [], "summary": {"n_events": 0},
                   "spx_series": None, "t10y2y_series": None}

        if not _bt.get("source_ok"):
            st.info(
                f"⚠️ FRED 或 ^GSPC 抓取失敗，回測暫不可用。"
                f"{_bt.get('note','')}"
            )
        elif _bt["summary"]["n_events"] == 0:
            st.info(f"近 30 年無符合條件之倒掛翻正事件（{_bt.get('note','')}）")
        else:
            _sm = _bt["summary"]
            _ev = _bt["events"]
            # ── KPI 列（5 欄）─────────────────────────────
            _bk1, _bk2, _bk3, _bk4, _bk5 = st.columns(5)
            _bk1.metric("事件數", f"{_sm['n_events']}",
                        help=f"完整 18M 窗口：{_sm['n_complete_18m']}")
            _bk2.metric(
                "6M 中位",
                f"{_sm['median_6m']:+.2f}%" if _sm.get('median_6m') is not None else "—",
                help=f"勝率 {_sm['win_rate_6m']:.0f}%" if _sm.get('win_rate_6m') is not None else "")
            _bk3.metric(
                "12M 中位",
                f"{_sm['median_12m']:+.2f}%" if _sm.get('median_12m') is not None else "—",
                help=f"勝率 {_sm['win_rate_12m']:.0f}%" if _sm.get('win_rate_12m') is not None else "")
            _bk4.metric(
                "18M 中位",
                f"{_sm['median_18m']:+.2f}%" if _sm.get('median_18m') is not None else "—",
                help=f"勝率 {_sm['win_rate_18m']:.0f}%" if _sm.get('win_rate_18m') is not None else "")
            _bk5.metric(
                "12M 勝率",
                f"{_sm['win_rate_12m']:.0f}%" if _sm.get('win_rate_12m') is not None else "—")
            # v18.255 stash 給 AI 白話總體檢
            try:
                st.session_state["_macro_inv_backtest"] = {
                    "n_events": int(_sm.get("n_events", 0)),
                    "median_6m": _sm.get("median_6m"),
                    "median_12m": _sm.get("median_12m"),
                    "median_18m": _sm.get("median_18m"),
                    "win_rate_12m": _sm.get("win_rate_12m"),
                }
            except Exception:
                pass

            # ── 事件表 ──────────────────────────────────
            _bt_df = pd.DataFrame([{
                "翻正日":        e["date"].strftime("%Y-%m-%d"),
                "倒掛最深 (%)":  e["t10y2y_min_pre"],
                "6M 報酬 (%)":   e["ret_6m"],
                "12M 報酬 (%)":  e["ret_12m"],
                "18M 報酬 (%)":  e["ret_18m"],
                "完整窗口":      "✅" if e["complete"] else "⏳",
            } for e in _ev])
            st.dataframe(
                _bt_df,
                column_config={
                    "倒掛最深 (%)": st.column_config.NumberColumn(format="%.2f"),
                    "6M 報酬 (%)":  st.column_config.NumberColumn(format="%.2f"),
                    "12M 報酬 (%)": st.column_config.NumberColumn(format="%.2f"),
                    "18M 報酬 (%)": st.column_config.NumberColumn(format="%.2f"),
                },
                use_container_width=True, hide_index=True,
            )

            # ── SPX log 走勢 + 翻正日垂直線 + NBER 衰退期紅陰影 ──
            _spx = _bt.get("spx_series")
            if _spx is not None and len(_spx) > 0:
                try:
                    _btfig = go.Figure()
                    _btfig.add_trace(go.Scatter(
                        x=_spx.index, y=_spx.values, mode="lines",
                        name="S&P 500", line=dict(color=MD_BLUE_300, width=1.5),
                    ))
                    # NBER 衰退期（與 app.py:1778 _crises 同源 + 1990/2001）
                    _bt_crises = [
                        ("1990-07-01", "1991-03-01", "1990 衰退"),
                        ("2001-03-01", "2001-11-01", "2001 衰退"),
                        ("2007-12-01", "2009-06-01", "2008 金融海嘯"),
                        ("2020-02-01", "2020-06-01", "2020 COVID"),
                    ]
                    for _cs, _ce, _cn in _bt_crises:
                        _btfig.add_vrect(
                            x0=_cs, x1=_ce,
                            fillcolor="rgba(244,67,54,0.12)",
                            line_width=0,
                            annotation_text=_cn,
                            annotation_position="top left",
                            annotation_font={"size": 9, "color": MATERIAL_RED},
                        )
                    # 翻正日綠虛線
                    for _e in _ev:
                        _btfig.add_vline(
                            x=_e["date"], line_dash="dash",
                            line_color=MATERIAL_GREEN, line_width=1, opacity=0.7,
                        )
                    _btfig.update_yaxes(type="log",
                                        gridcolor=BG_DARK_NAVY_4,
                                        color=TRAFFIC_NEUTRAL)
                    _btfig.update_xaxes(gridcolor=BG_DARK_NAVY_4, color=TRAFFIC_NEUTRAL)
                    _btfig.update_layout(
                        paper_bgcolor=GH_BG_PRIMARY, plot_bgcolor=GH_BG_PRIMARY,
                        font_color=GH_FG_PRIMARY, height=360,
                        margin=dict(t=20, b=30, l=50, r=20),
                        hovermode="x unified",
                        showlegend=False,
                    )
                    st.plotly_chart(_btfig, use_container_width=True,
                                    key="bt_tp_spx_chart")
                except Exception as _bt_fig_e:  # noqa: BLE001
                    st.caption(f"走勢圖繪製失敗：{str(_bt_fig_e)[:80]}")
            st.caption(
                f"樣本 n={_sm['n_events']}，僅供參考；"
                f"綠色虛線＝倒掛翻正日｜紅色陰影＝NBER 衰退期。"
                f"窗口未到期事件以 ⏳ 標記且不納入中位數/勝率統計。"
            )

    # ── v19.18: 7 子領域 Z-Score 健康度已搬到戰情首頁 ① 7-cluster 下方 ──
    # 原 v18.100 區塊整段移除，避免與 7-cluster 視覺重複（user 反饋）
