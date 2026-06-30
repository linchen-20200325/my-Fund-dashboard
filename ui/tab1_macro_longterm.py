"""ui/tab1_macro_longterm.py — v19.262 P3-A5 從 tab1_macro.py 抽出的 🌳 長期座標區塊。

從 `ui/tab1_macro.py:render_macro_tab()` body 內抽出獨立 section,降低主檔 LOC:
- `render_long_term_section(ind, fred_key, show_l3)` — render 入口

內容包含:
- 💵 美股流動性 6 卡片(短線雷達範本 + SPEC 線)
- MK 景氣時鐘 & 資產輪動(L2/L3 皆顯示)
- ⑥ 💵 美股流動性 × 熱錢監測 Raw data expander
- 📦 ARCHIVED 台股熱錢監測(降級 archive)
- 💰 資本防線 — 含息報酬 vs 配息率(L3 only,stash 給 AI)
- 📰 市場新聞折疊區(L3 only)

設計:
- 不依賴 render_macro_tab 的 closure local var,全部走參數注入
- `_render_macro_indicator_card` + `_MACRO_CARD_LIGHT_COLOR` lazy import 避循環
- §8.2:L3 UI helper,純渲染 + session_state 讀寫(stash _macro_capital_line)
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from shared.colors import (
    GH_BG_CARD,
    GH_BG_PRIMARY,
    GH_BORDER,
    GH_FG_PRIMARY,
    GRAY_55,
    GRAY_66,
    GRAY_AA,
    MATERIAL_GREEN,
    MATERIAL_ORANGE,
    MATERIAL_RED,
    STREAMLIT_BG,
    TRAFFIC_GREEN,
    TRAFFIC_NEUTRAL,
    TRAFFIC_RED,
    TRAFFIC_YELLOW,
)
from ui.components.mk_clock import render_mk_clock_section


def render_long_term_section(
    ind: dict,
    fred_key: str,
    show_l3: bool = True,
) -> None:
    """渲染 🌳 長期座標 section(美股流動性卡 + MK 時鐘 + 資本防線 + 新聞)。

    Args:
        ind: indicators dict(總經指標)
        fred_key: FRED API key str(可空)
        show_l3: L3 toggle,False 時跳過資本防線 + 新聞
    """
    from ui.tab1_macro import _render_macro_indicator_card, _MACRO_CARD_LIGHT_COLOR  # lazy 避循環

    st.divider()
    st.markdown("## 🌳 長期座標")
    st.caption("regime / 結構 ｜ 美林時鐘 + 美股流動性熱錢 + 資本防線")

    # ── v19.188 💵 美股流動性 6 卡片（短線雷達範本：燈號 + 值 + 白話 + mini sparkline + SPEC 線）──
    # user 2026-06-27:基金短線雷達為範本,長期桶也改成小圖+SPEC 卡片;Raw data 收進下方 expander。
    st.markdown("#### 💵 美股流動性 × 熱錢 — 流動性 × 信用 × 情緒")
    try:
        from services.us_liquidity_engine import fetch_us_liquidity_snapshot as _fetch_us_liq_cards  # noqa: PLC0415
        _us_liq_cards = _fetch_us_liq_cards(fred_key)
        # (engine_key, 卡片標題, sparkline spark_key, 白話 note)
        _us_card_specs = [
            ("m2_yoy",  "📊 M2 YoY",        "us_m2_yoy",  "貨幣供給年增；>4% 熱錢充裕、<0 緊縮"),
            ("walcl",   "🏦 Fed 資產負債表", "us_walcl",   "擴表=QE 放水、縮表=QT 回收"),
            ("rrp",     "💧 隔夜逆回購 RRP",  "us_rrp",     "流動性蓄水池；<100B 枯竭警示"),
            ("net_liq", "🌊 淨流動性",        "us_net_liq", "Fed資產−RRP−TGA；真正能流進股市的錢"),
            ("hy_oas",  "⚠️ HY 信用利差",     "us_hy_oas",  "高收益債利差；>5.5% 信用緊縮撤離"),
            ("hyg_lqd", "💰 HYG/LQD 比",      "us_hyg_lqd", "高收益/投等債比；升=risk-on 熱錢進股"),
            ("aaii",    "😱 AAII 情緒",       "us_aaii",    "散戶多空差(反指標)；>+20 過熱賣訊"),
        ]
        for _row_start in range(0, len(_us_card_specs), 3):
            _ucards = st.columns(3)
            for _ci, (_ek, _ctitle, _spk, _cnote) in enumerate(
                    _us_card_specs[_row_start:_row_start + 3]):
                with _ucards[_ci]:
                    _ud = _us_liq_cards.get(_ek, {}) if isinstance(_us_liq_cards, dict) else {}
                    if not _ud or "_err" in _ud:
                        _emsg = (_ud.get("_err", "未載入") if isinstance(_ud, dict) else "未載入")
                        _render_macro_indicator_card(
                            title=_ctitle, signal="⬜ 待取得",
                            color=_MACRO_CARD_LIGHT_COLOR["gray"],
                            value_str="—", note=_cnote,
                            label=f"❌ {str(_emsg)[:32]}", trend=None,
                            spark_key=_spk)
                        continue
                    _uval = _ud.get("value")
                    _uunit = _ud.get("unit", "")
                    _uval_str = (f"{_uval:+.2f}{_uunit}"
                                 if isinstance(_uval, (int, float)) else "—")
                    _render_macro_indicator_card(
                        title=_ctitle,
                        signal=_ud.get("label", "—"),
                        color=_ud.get("color", _MACRO_CARD_LIGHT_COLOR["gray"]),
                        value_str=_uval_str,
                        note=_cnote,
                        label=f"美股流動性 ｜ {_ud.get('date', '')}",
                        trend=_ud.get("series"),
                        spark_key=_spk)
    except Exception as _us_card_e:  # noqa: BLE001
        st.caption(f"💵 美股流動性卡片暫時無法顯示：[{type(_us_card_e).__name__}] {_us_card_e}")

    # ── MK 景氣時鐘 ＆ 資產輪動（v18.8）── L2/L3 皆顯示
    st.divider()
    render_mk_clock_section(ind)


    # ── 宏觀風險溫度計 + 景氣循環羅盤 + AI（僅 L3）──────────────
    import pandas as _pd_mac
    def _safe_series(s):
        if s is None: return None
        try:
            if not isinstance(s, _pd_mac.Series): s = _pd_mac.Series(s)
            return s.dropna().tail(60)
        except Exception: return None

    with st.expander("⑥ 💵 美股流動性 × 熱錢監測 — Raw data（metric 明細 + 新鮮度 + 強制重抓）",
                     expanded=False):
        st.caption(
            "💡 **為何重要**：境外美股基金 NAV 主受 ① 美元流動性（M2/RRP/WALCL）+ "
            "② 信用偏好（HY/HYG-LQD）+ ③ 散戶情緒（AAII）三軸驅動。"
            "**FED 升降息只是源頭**，熱錢 = 流動性 + 信用 + 情緒 三者綜合結果。"
        )
        try:
            from services.us_liquidity_engine import fetch_us_liquidity_snapshot  # noqa: PLC0415
            _us_liq = fetch_us_liquidity_snapshot(fred_key)

            # Row 1: 流動性 4 chips（v19.192 加淨流動性）
            _r1 = st.columns(4)
            _row1 = [
                ("m2_yoy", "📊 M2 YoY", "廣義貨幣供給年增（FRED M2SL）"),
                ("walcl", "🏦 Fed 資產負債表", "QE/QT pace（FRED WALCL）"),
                ("rrp", "💧 隔夜逆回購 RRP", "流動性蓄水池（FRED RRPONTSYD）"),
                ("net_liq", "🌊 淨流動性", "Fed資產−RRP−TGA（兆美元，真正進股市的錢）"),
            ]
            for _i, (_key, _title, _default_desc) in enumerate(_row1):
                with _r1[_i]:
                    _d = _us_liq.get(_key, {})
                    if "_err" in _d:
                        st.metric(_title, "待取得", help=f"{_default_desc}｜❌ {_d['_err'][:50]}")
                    else:
                        _val = _d["value"]
                        _unit = _d.get("unit", "")
                        _delta = _d.get("delta")
                        _delta_str = f"{_delta:+.2f}{_unit}" if _delta is not None else None
                        st.metric(_title, f"{_val:+.2f}{_unit}", delta=_delta_str,
                                  help=f"{_default_desc} ({_d.get('date','')})")
                        st.caption(f"<span style='color:{_d.get('color',TRAFFIC_NEUTRAL)}'>● {_d.get('label','')}</span>",
                                   unsafe_allow_html=True)

            # Row 2: 信用 + 情緒 3 chips
            _r2 = st.columns(3)
            _row2 = [
                ("hy_oas", "⚠️ HY 信用利差", "FRED BAMLH0A0HYM2 (% OAS)"),
                ("hyg_lqd", "💰 HYG/LQD 比", "高收益債 vs 投等債 — 風險偏好"),
                ("aaii", "😱 AAII 情緒 spread", "Bull − Bear（反指標）"),
            ]
            for _i, (_key, _title, _default_desc) in enumerate(_row2):
                with _r2[_i]:
                    _d = _us_liq.get(_key, {})
                    if "_err" in _d:
                        st.metric(_title, "待取得", help=f"{_default_desc}｜❌ {_d['_err'][:50]}")
                    else:
                        _val = _d["value"]
                        _unit = _d.get("unit", "")
                        st.metric(_title, f"{_val:+.2f}{_unit}",
                                  help=f"{_default_desc} ({_d.get('date','')})")
                        st.caption(f"<span style='color:{_d.get('color',TRAFFIC_NEUTRAL)}'>● {_d.get('label','')}</span>",
                                   unsafe_allow_html=True)

            # 失敗 fetcher 列表（仿 Stock v18.194 fail-trace）
            # v19.58：外層已是 expander → 改用原生 HTML <details> 避 StreamlitAPIException 巢狀爆
            _errs = {k: v["_err"] for k, v in _us_liq.items() if "_err" in v}
            if _errs:
                _err_items = "".join(
                    f"<li><b>{_ek}</b>：<code>{str(_ev).replace('<', '&lt;')[:120]}</code></li>"
                    for _ek, _ev in _errs.items()
                )
                st.markdown(
                    f"<details style='margin:8px 0;background:{GH_BG_PRIMARY};border:1px solid {GH_BORDER};"
                    f"border-radius:6px;padding:6px 12px'>"
                    f"<summary style='cursor:pointer;color:{TRAFFIC_YELLOW};font-size:12px'>"
                    f"🔍 載入失敗詳情（{len(_errs)} 項）</summary>"
                    f"<ul style='margin:6px 0 0 0;color:{GRAY_AA};font-size:11px'>{_err_items}</ul>"
                    f"<div style='color:{GRAY_66};font-size:10px;margin-top:6px'>"
                    f"💡 多半是 FRED key 未設 / AAII 頁面格式改版 / Yahoo timeout；非全部失敗不影響核心判讀</div>"
                    f"</details>",
                    unsafe_allow_html=True,
                )

            # v19.53 ══ 📊 資料新鮮度條 ══（traffic-light 掛「最舊指標 date 距今天數」，FRED 平日更新節奏 + 強制重抓）
            _us_today = pd.Timestamp.now(tz="Asia/Taipei").date()
            _us_dates = []
            for _v in _us_liq.values():
                _ds = _v.get("date") if isinstance(_v, dict) else None
                if _ds:
                    try:
                        _us_dates.append(pd.Timestamp(_ds).date())
                    except Exception:
                        pass
            if _us_dates:
                _us_cutoff = min(_us_dates)
                _us_days_old = (_us_today - _us_cutoff).days
                _us_color = TRAFFIC_GREEN if _us_days_old <= 2 else (TRAFFIC_YELLOW if _us_days_old <= 7 else TRAFFIC_RED)
                _us_age_txt = "今日" if _us_days_old <= 0 else f"{_us_days_old} 天前"
            else:
                _us_cutoff = None
                _us_color = TRAFFIC_NEUTRAL
                _us_age_txt = "—"
            _us_load_txt = pd.Timestamp.now(tz="Asia/Taipei").strftime("%m-%d %H:%M")
            _ucols = st.columns([5, 1])
            with _ucols[0]:
                st.markdown(
                    f"<div style='background:{GH_BG_PRIMARY};border-left:3px solid {_us_color};"
                    f"border-radius:0 6px 6px 0;padding:6px 12px;margin-top:8px;font-size:11px;color:{GRAY_AA}'>"
                    f"📅 最舊指標截止：<span style='color:{_us_color};font-weight:700'>{_us_cutoff or '—'}</span>"
                    f" · <span style='color:{_us_color}'>{_us_age_txt}</span>"
                    f"　|　🕐 本次載入：{_us_load_txt} (TW)"
                    f"　|　📡 來源 FRED / Yahoo / AAII"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            with _ucols[1]:
                if st.button("🔄 強制重抓", key="us_liq_force_refresh",
                             help="v19.57 C1：僅清 Tab1（FRED/Yahoo/AAII/熱錢）快取，"
                                  "Tab2~Tab5 基金/組合/政策快取不受影響"):
                    try:
                        from services.macro import clear_tab1_macro_caches
                        clear_tab1_macro_caches(session_state=st.session_state)
                    except Exception:
                        pass
                    st.rerun()
        except Exception as _us_e:
            st.error(f"美股流動性監測渲染失敗：[{type(_us_e).__name__}] {_us_e}")

    # ── 台股熱錢監測（v19.47 ARCHIVED：境外美股基金可略過｜原 ⑥ KEEP，user 反饋本土訊號非主驅力）──
    # 移除 ⑥ 編號 + 標題加 📦 ARCHIVED 前綴 + 模組保留磁碟便於日後復活
    st.divider()
    with st.expander("📦 ARCHIVED — 台股熱錢監測（境外美股基金可略過｜本土訊號）",
                     expanded=False):
        st.caption("⚠️ v19.47 降級為 archive：USD 計價境外美股基金，台幣升貶/外資台股淨買賣對 NAV 影響有限。如需此資料請點開。")
        try:
            # v19.196 P0-4-A:hot_money render 已搬 ui.hot_money
            from ui.hot_money import render_hot_money_section
            _finmind_tok = (st.secrets.get("FINMIND_TOKEN", "")
                             if hasattr(st, "secrets") else "") or ""
            render_hot_money_section(token=_finmind_tok,
                                      key_prefix="tab1_hm")
        except Exception as _hme:
            st.error(f"熱錢監測渲染失敗：[{type(_hme).__name__}] {_hme}")
    if show_l3:
        _pf_def = [f for f in st.session_state.get("portfolio_funds", []) if f.get("loaded")]
        if _pf_def:
            st.markdown("#### 💰 資本防線 — 含息報酬 vs 配息率")
            _def_names = [f.get("fund_name") or f.get("code","?") for f in _pf_def]
            _def_tr1y  = [float((f.get("metrics") or f.get("m") or {}).get("ret_1y") or 0) for f in _pf_def]
            _def_adr   = [float((f.get("metrics") or f.get("m") or {}).get("annual_div_rate") or 0) for f in _pf_def]
            _def_colors = [MATERIAL_RED if tr < adr else MATERIAL_GREEN
                           for tr, adr in zip(_def_tr1y, _def_adr)]
            _def_fig = go.Figure()
            _def_fig.add_trace(go.Bar(
                x=_def_names, y=_def_tr1y,
                marker_color=_def_colors,
                text=[f"{v:.1f}%" for v in _def_tr1y],
                textposition="outside",
                name="含息報酬率 TR1Y",
                customdata=list(zip(_def_adr, ["🚨 本金侵蝕" if tr < adr else "" for tr, adr in zip(_def_tr1y, _def_adr)])),
                hovertemplate="<b>%{x}</b><br>TR1Y: %{y:.1f}%<br>配息率: %{customdata[0]:.1f}%<br>%{customdata[1]}<extra></extra>",
            ))
            _def_fig.add_trace(go.Scatter(
                x=_def_names, y=_def_adr,
                mode="markers",
                marker=dict(symbol="line-ew", size=16, color=MATERIAL_ORANGE,
                            line=dict(width=3, color=MATERIAL_ORANGE)),
                name="配息年化率",
                hovertemplate="配息率: %{y:.1f}%<extra></extra>",
            ))
            _def_fig.update_layout(
                paper_bgcolor=STREAMLIT_BG, plot_bgcolor=GH_BG_CARD,
                font_color=GH_FG_PRIMARY, height=260,
                margin=dict(t=20, b=50, l=10, r=10),
                legend=dict(orientation="h", y=-0.35),
                xaxis=dict(tickfont=dict(size=11)),
                yaxis=dict(title="報酬率 (%)", ticksuffix="%"),
            )
            st.plotly_chart(_def_fig, use_container_width=True)
            st.caption("🟢 綠色 = TR1Y > 配息率（配息有保障）｜🔴 紅色 = TR1Y < 配息率（本金侵蝕警示）｜橙色橫線 = 配息年化率")
            # v18.255 stash 給 AI 白話總體檢
            try:
                _eroded = [(n, tr, adr) for n, tr, adr
                           in zip(_def_names, _def_tr1y, _def_adr)
                           if tr < adr]
                st.session_state["_macro_capital_line"] = {
                    "n_funds": len(_def_names),
                    "n_eroded": len(_eroded),
                    "eroded_funds": [{"name": n[:20], "tr1y": float(tr),
                                      "adr": float(adr)} for n, tr, adr in _eroded[:5]],
                }
            except Exception:
                pass

    # ── 市場新聞（折疊）── L3 only
    # v19.139：systemic 排前 + Top 8 顯著 + 其餘 nested expander(對齊 AI 實際讀的 ≤8 則)
    if show_l3:
        _news_items = st.session_state.get("news_items",[])
        if _news_items:
            _sys = [n for n in _news_items if n.get("is_systemic")]
            _gen = [n for n in _news_items if not n.get("is_systemic")]
            _ordered = _sys + _gen
            _n_sys = len(_sys)
            _expander_label = (f"📰 市場新聞（{len(_news_items)} 則"
                               + (f"，🚨 {_n_sys} 系統性風險" if _n_sys else "")
                               + "） — Top 8（AI 實際讀的）+ 其餘摺疊")
            def _render_news(_ni):
                _nt = _ni.get("title","")[:90]
                _ns = _ni.get("source","")
                _nu = _ni.get("url","") or _ni.get("link","")
                _nd = str(_ni.get("published",""))[:16]
                _flag = "🚨 " if _ni.get("is_systemic") else ""
                if _nu:
                    st.markdown(f"{_flag}**[{_nt}]({_nu})** <span style='color:{TRAFFIC_NEUTRAL};font-size:11px'>｜{_ns} {_nd}</span>", unsafe_allow_html=True)
                else:
                    st.markdown(f"{_flag}**{_nt}** <span style='color:{TRAFFIC_NEUTRAL};font-size:11px'>｜{_ns} {_nd}</span>", unsafe_allow_html=True)
            with st.expander(_expander_label, expanded=False):
                for _ni in _ordered[:8]:
                    _render_news(_ni)
                _rest = _ordered[8:]
                if _rest:
                    # v19.143 P0 fix:Streamlit 不准 nested expander
                    # (v19.139 把「其餘 N 則」做成 inner expander → 線上炸
                    # StreamlitAPIException: "Expanders may not be nested inside
                    # other expanders")。改用 inline divider + caption 分隔,
                    # rest 全部 inline 列出。外層 expander 預設折疊,user 點開
                    # 才看到 Top 8 + 分隔線 + 其餘,語意不變。
                    st.markdown(
                        f"<div style='border-top:1px dashed {GRAY_55};"
                        f"margin:10px 0 6px;padding-top:6px;color:{TRAFFIC_NEUTRAL};"
                        f"font-size:11px'>── 其餘 {len(_rest)} 則 "
                        "(AI 未讀,僅供參考)──</div>",
                        unsafe_allow_html=True,
                    )
                    for _ni in _rest:
                        _render_news(_ni)

    # ── v19.47 ⑥ 美股流動性 × 熱錢監測（user 反饋：基金 USD 計價，台股熱錢非主訊號） ──
    # 6 指標三角：流動性 (M2/WALCL/RRP) × 信用 (HY OAS / HYG-LQD) × 情緒 (AAII)
    st.divider()
