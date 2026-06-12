"""v19.58 — 💊 組合健檢 Tab 5 大貼圖區塊（從組合基金 / 單一基金移植）。

內容鏡像 tab3_portfolio.py（組合基金）與 tab2_single_fund.py（單一基金）的
視覺區塊，不重複既有計算邏輯，全部呼叫 fund_checkup 與 macro_helpers
共用 helper。

5 大區塊：
  ① 基金體檢 PK 表（render_fund_checkup → 含 ② 4 大健診卡）
  ③ 真實收益 vs 配息率 健康矩陣（Plotly Bar，吃本金警示）
  ④ 投資試算 — 投入金額 → 單位數 / 月配息 TWD
  ⑤ TER 費用率 + 持股分析（產業配置 / 前10大持股）

呼叫端：ui/tab_fund_grp_health.py：render_fund_grp_health_tab。
"""
from __future__ import annotations

import streamlit as st


def _build_fund_dict(fd_raw: dict, code: str, principal_twd: float) -> dict:
    """把 _auto_fetch_moneydj 回傳的 raw dict 包成 portfolio_funds 標準結構。

    對照 tab3_portfolio.py L1522-1533 的組合建構邏輯。
    invest_twd 欄位給 fund_checkup._compute_fund_health_kpis 算「月配息 TWD」用。
    """
    if not fd_raw:
        return {}
    return {
        "code": code,
        "name": fd_raw.get("fund_name") or code,
        "series": fd_raw.get("series"),
        "dividends": fd_raw.get("dividends", []) or [],
        "metrics": fd_raw.get("metrics", {}) or {},
        "moneydj_raw": fd_raw,
        "risk_metrics": fd_raw.get("risk_metrics", {}) or {},
        "currency": (fd_raw.get("currency", "")
                     or (fd_raw.get("metrics", {}) or {}).get("currency", "")),
        "loaded": True,
        "invest_twd": float(principal_twd or 0),
    }


def _safe_num(v):
    """寬鬆數值轉換：吃 float / "12.3%" / "1,234" / None → float 或 None。"""
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        try:
            f = float(v)
        except (TypeError, ValueError):
            return None
    else:
        try:
            f = float(str(v).replace("%", "").replace(",", "").strip())
        except (TypeError, ValueError):
            return None
    import math
    if math.isnan(f) or math.isinf(f):
        return None
    return f


def _render_dividend_matrix(funds: list) -> None:
    """③ 真實收益 vs 配息率 健康矩陣（從 tab3_portfolio L1796-1921 移植）。"""
    if not funds:
        return
    try:
        import plotly.graph_objects as go
        from ui.helpers.macro_helpers import compute_1y_total_return
    except ImportError as e:
        st.caption(f"⬜ 真實收益矩陣未渲染：{e}")
        return

    st.divider()
    st.markdown("### 📊 真實收益 vs 配息率健康矩陣")
    st.caption("長條高度 < 紅虛線 → 含息報酬不足以支撐配息 → 吃本金警示")

    _rc_names, _rc_ret, _rc_div, _rc_real, _rc_src = [], [], [], [], []
    for _f in funds:
        _mj = _f.get("moneydj_raw", {}) or {}
        _m = _f.get("metrics", {}) or {}
        _name = (_f.get("name") or _f.get("code", "?"))[:18]
        _ret_v, _src_label = compute_1y_total_return(_f)
        _is_real = _ret_v is not None
        try:
            _div = float(_mj.get("moneydj_div_yield") or _m.get("annual_div_rate") or 0)
        except (TypeError, ValueError):
            _div = 0.0
        if _div <= 0:
            _divs_f = _f.get("dividends") or []
            if _divs_f:
                try:
                    import datetime as _dt
                    _ctf = _dt.datetime.now() - _dt.timedelta(days=365)
                    _sa = 0.0
                    for _dd in _divs_f:
                        _ds = (_dd.get("date") or "").replace("/", "-")
                        try:
                            _dp = _dt.datetime.strptime(_ds[:10], "%Y-%m-%d")
                        except (ValueError, TypeError):
                            continue
                        if _dp >= _ctf:
                            _sa += float(_dd.get("amount", 0) or 0)
                    _nv = _m.get("nav") or _mj.get("nav_latest")
                    try:
                        _nv = float(_nv) if _nv is not None else None
                    except (TypeError, ValueError):
                        _nv = None
                    if _sa > 0 and _nv and _nv > 0:
                        _div = round((_sa / _nv) * 100.0, 2)
                except Exception:
                    pass
        _rc_names.append(_name)
        _rc_ret.append(round(_ret_v, 2) if _ret_v is not None else 0.0)
        _rc_div.append(round(_div, 2))
        _rc_real.append(_is_real)
        _rc_src.append(_src_label if _is_real else "資料不足")

    if not _rc_names:
        return

    _rc_colors = []
    for _r, _d, _real in zip(_rc_ret, _rc_div, _rc_real):
        if not _real:
            _rc_colors.append("#888")
        elif _d > 0 and _r < _d:
            _rc_colors.append("#f44336")
        elif _d > 0 and _r < _d * 1.2:
            _rc_colors.append("#ff9800")
        else:
            _rc_colors.append("#00c853")

    fig_rc = go.Figure()
    _rc_ret_vis = [max(_r, 0.5) if (_d > 0 and _r < _d) else _r
                   for _r, _d in zip(_rc_ret, _rc_div)]
    fig_rc.add_trace(go.Bar(
        x=_rc_names, y=_rc_ret_vis,
        name="含息報酬率(1Y)%",
        marker_color=_rc_colors,
        text=[f"{v:.1f}%" for v in _rc_ret],
        textposition="outside",
        customdata=list(zip(_rc_ret, _rc_src)),
        hovertemplate=("%{x}<br>含息報酬：%{customdata[0]:.2f}%"
                       "<br>來源：%{customdata[1]}<extra></extra>")))
    if any(d > 0 for d in _rc_div):
        fig_rc.add_trace(go.Scatter(
            x=_rc_names, y=_rc_div,
            name="配息年化率%",
            mode="markers+lines",
            line=dict(color="#f44336", width=1.5, dash="dot"),
            marker=dict(symbol="diamond", size=8, color="#f44336"),
            hovertemplate="%{x}<br>配息率：%{y:.2f}%<extra></extra>"))
    fig_rc.add_hline(y=0, line_color="#555", line_width=1)
    _y_max = max(max(_rc_ret_vis, default=10), max(_rc_div, default=10)) * 1.35
    for _i, (_r, _d, _n, _real) in enumerate(
        zip(_rc_ret, _rc_div, _rc_names, _rc_real)
    ):
        if _real and _d > 0 and _r < _d:
            fig_rc.add_vrect(
                x0=_i - 0.45, x1=_i + 0.45,
                fillcolor="rgba(244,67,54,0.08)",
                line_color="rgba(244,67,54,0.4)", line_width=1,
                layer="below")
            fig_rc.add_annotation(
                x=_n, y=_y_max,
                text=f"⚠️ 吃本金<br>缺口 {_d-_r:.1f}%",
                showarrow=False,
                font=dict(color="#f44336", size=11),
                bgcolor="rgba(42,10,10,0.85)",
                bordercolor="#f44336", borderwidth=1,
                borderpad=4)
        elif not _real and _d > 0:
            fig_rc.add_annotation(
                x=_n, y=_y_max,
                text="⬜ 1Y 資料不足<br>無法判定",
                showarrow=False,
                font=dict(color="#aaa", size=10),
                bgcolor="rgba(60,60,60,0.7)",
                bordercolor="#666", borderwidth=1,
                borderpad=4)
    fig_rc.update_layout(
        paper_bgcolor="#0e1117", plot_bgcolor="#161b22",
        font_color="#e6edf3", height=360,
        margin=dict(t=40, b=20, l=40, r=20),
        legend=dict(orientation="h", font_size=10, y=1.08),
        yaxis_title="報酬率 / 配息率 (%)",
        yaxis=dict(range=[min(0, min(_rc_ret, default=0)) - 2, _y_max]),
        bargap=0.35, hovermode="x unified")
    st.plotly_chart(fig_rc, use_container_width=True)


def _render_investment_calc(fund: dict, principal_twd: float) -> None:
    """④ 投資試算（從 tab2_single_fund L1195-1400 精簡）。

    顯示 NAV / 年化配息率 / 即時 FX → 可申購單位 / 月配 TWD / 年化配息率。
    本金固定吃 principal_twd（組合健檢 sidebar 共用），不再展示輸入欄位。
    """
    _mj = fund.get("moneydj_raw") or {}
    _m = fund.get("metrics") or {}
    _code = fund.get("code", "—")
    _ccy_raw = (_mj.get("currency") or fund.get("currency") or "TWD").strip() or "TWD"
    _CCY_NORMALIZE = {
        "台幣": "TWD", "新台幣": "TWD", "台": "TWD",
        "美元": "USD", "美金": "USD",
        "歐元": "EUR", "歐": "EUR",
        "日圓": "JPY", "日幣": "JPY", "日元": "JPY",
        "人民幣": "CNH",
        "港幣": "HKD", "港元": "HKD",
        "英鎊": "GBP",
        "澳幣": "AUD", "澳元": "AUD",
        "瑞士法郎": "CHF",
        "新加坡幣": "SGD", "新元": "SGD",
        "加拿大幣": "CAD", "加元": "CAD",
        "南非幣": "ZAR",
    }
    _ccy = _CCY_NORMALIZE.get(_ccy_raw, _ccy_raw.upper())
    _nav = _safe_num(_m.get("nav") or _mj.get("nav_latest"))
    _adr = _safe_num(_mj.get("moneydj_div_yield") or _m.get("annual_div_rate"))

    _fx = None
    if _ccy == "TWD":
        _fx = 1.0
    else:
        try:
            from repositories.fund_repository import get_latest_fx
            _fx = get_latest_fx(f"{_ccy}TWD=X")
            if _fx is None or _fx <= 0:
                _fx = None
        except Exception:
            _fx = None

    st.markdown(
        f"#### 💰 投資試算 — 投入金額 → 單位數 / 配息估算 "
        f"<span style='color:#888;font-size:11px'>{_code} / {_ccy}</span>",
        unsafe_allow_html=True,
    )
    _ic1, _ic2 = st.columns([2, 1])
    with _ic1:
        st.metric("投入金額（新台幣 TWD）", f"{float(principal_twd or 0):,.0f}")
    with _ic2:
        st.caption(f"NAV：{_nav if _nav is not None else '—'} {_ccy}")
        st.caption(f"年化配息率：{_adr if _adr is not None else '—'} %")
        if _ccy == "TWD":
            st.caption("💰 此基金以新台幣計價（FX = 1）")
        elif _fx:
            st.caption(f"💱 1 {_ccy} = **{_fx:.4f}** TWD（即時匯率）")
        else:
            st.caption(f"⚠️ 無法取得 {_ccy}/TWD 即時匯率")

    if not _nav or _nav <= 0:
        st.caption("⬜ NAV 缺失，無法試算")
        return
    if _ccy != "TWD" and not _fx:
        st.caption("⬜ FX 缺失，無法試算")
        return

    _amt_local = (float(principal_twd) / _fx) if (_ccy != "TWD" and _fx) else float(principal_twd)
    _units = _amt_local / _nav
    _mc1, _mc2, _mc3, _mc4 = st.columns(4)
    _mc1.metric("可申購單位數", f"{_units:,.2f}")
    if _adr and _adr > 0:
        _ann_div = _amt_local * _adr / 100.0
        _mon_div = _ann_div / 12.0
        _mon_units = _mon_div / _nav
        if _ccy != "TWD" and _fx:
            _ann_div_twd = _ann_div * _fx
            _mon_div_twd = _mon_div * _fx
        else:
            _ann_div_twd = _ann_div
            _mon_div_twd = _mon_div
        _mc2.metric("月配息（TWD）", f"{_mon_div_twd:,.0f}")
        _mc3.metric("月配股（單位）", f"{_mon_units:,.2f}",
                    help="月配息若再投入可換得的單位數（月配息 ÷ NAV）")
        _mc4.metric("年化配息率", f"{_adr:.2f}%",
                    help="年化配息率 = 年配息 / 投入本金（原幣）")
        if _ccy != "TWD":
            st.success(
                f"💱 **換算 TWD**（1 {_ccy} = {_fx:.4f}）："
                f"本金 {float(principal_twd):,.0f} TWD → "
                f"原幣本金 **{_amt_local:,.2f}** {_ccy} → "
                f"可買 **{_units:,.2f}** 單位｜年息 **{_ann_div_twd:,.0f}** TWD"
                f"（每月 ≈ **{_mon_div_twd:,.0f}** TWD / "
                f"配股 ≈ **{_mon_units:,.2f}** 單位）"
            )
        else:
            st.success(
                f"📌 本金 {float(principal_twd):,.0f} TWD → "
                f"可買 **{_units:,.2f}** 單位｜年息 **{_ann_div_twd:,.0f}** TWD"
                f"（每月 ≈ **{_mon_div_twd:,.0f}** TWD / "
                f"配股 ≈ **{_mon_units:,.2f}** 單位）"
            )
    else:
        st.caption("⬜ 此基金無年化配息率，無月配試算")


def _render_holdings_block(fund: dict) -> None:
    """⑤ TER 費用率分析 + 持股分析（從 tab2_single_fund L994-1076 移植）。"""
    _mj = fund.get("moneydj_raw") or {}
    _ter_raw = _mj.get("mgmt_fee", "") or ""
    _ter_cat = _mj.get("category", "") or ""
    if _ter_raw:
        try:
            _ter_val = float(str(_ter_raw).replace("%", "").strip())
        except (ValueError, TypeError):
            _ter_val = None
        if _ter_val is not None:
            _ter_avg_map = {
                "股票": 1.50, "全球股票": 1.50, "科技": 1.60,
                "亞太": 1.60, "新興市場": 1.70, "高收益": 1.00,
                "債券": 0.80, "全球債券": 0.80, "投資等級": 0.80,
                "平衡": 1.20, "貨幣": 0.30,
            }
            _ter_avg = next(
                (_v for _k, _v in _ter_avg_map.items() if _k in _ter_cat), None)
            if _ter_avg is not None:
                _ter_diff = _ter_val - _ter_avg
                _ter_c = ("#f44336" if _ter_diff > 0.3
                          else ("#ff9800" if _ter_diff > 0 else "#00c853"))
                _ter_vs = (f"高於均值 +{_ter_diff:.2f}%" if _ter_diff > 0
                           else f"低於均值 {abs(_ter_diff):.2f}%")
                _ter_avg_html = (
                    f"<div><div style='color:#888;font-size:10px'>同類均值</div>"
                    f"<div style='color:#888;font-weight:700;font-size:16px'>"
                    f"{_ter_avg:.2f}%</div></div>"
                    f"<div><div style='color:#888;font-size:10px'>費用比較</div>"
                    f"<div style='color:{_ter_c};font-weight:700;font-size:16px'>"
                    f"{_ter_vs}</div></div>"
                )
            else:
                _ter_c, _ter_avg_html = "#888", ""
            st.markdown(
                "<div style='background:#161b22;border:1px solid #30363d;"
                "border-radius:10px;padding:10px 16px;margin:8px 0'>"
                "<div style='color:#888;font-size:11px;margin-bottom:6px'>"
                "💰 TER 費用率分析"
                + (f" — {_ter_cat[:12]}" if _ter_cat else "") + "</div>"
                f"<div style='display:flex;gap:24px;flex-wrap:wrap;margin-bottom:6px'>"
                f"<div><div style='color:#888;font-size:10px'>最高經理費</div>"
                f"<div style='color:{_ter_c};font-weight:700;font-size:16px'>"
                f"{_ter_val:.2f}%</div></div>"
                + _ter_avg_html +
                "</div>"
                "<div style='color:#555;font-size:10px'>"
                "費用率愈低，長期複利效益愈佳（費用每降 1%，20 年後終值多 ~25%）</div>"
                "</div>", unsafe_allow_html=True)
    else:
        st.caption("💰 TER 費用率分析 — ⬜ 缺 mgmt_fee 資料")

    _holdings = _mj.get("holdings", {}) or {}
    _sectors = _holdings.get("sector_alloc", []) or []
    _tops = _holdings.get("top_holdings", []) or []
    _hdate = _holdings.get("data_date", "")
    if not (_sectors or _tops):
        st.caption("📂 持股分析 — ⬜ MoneyDJ 未提供持股 / 產業資料")
        return

    try:
        from ui.helpers.holdings import _zh_holding  # type: ignore
    except Exception:
        def _zh_holding(_n):  # type: ignore
            return ""

    st.markdown(
        "**📂 持股分析**"
        + (f"<span style='color:#888;font-size:11px;margin-left:8px'>"
           f"（{_hdate}）</span>" if _hdate else ""),
        unsafe_allow_html=True,
    )
    _hc1, _hc2 = st.columns(2)
    with _hc1:
        if _sectors:
            st.markdown("**🏭 產業配置**")
            for _sec in _sectors[:10]:
                _sn = str(_sec.get("name", ""))[:18]
                _sp = float(_sec.get("pct", 0) or 0)
                st.markdown(
                    f"<div style='display:flex;align-items:center;gap:8px;margin:3px 0'>"
                    f"<div style='color:#ccc;font-size:11px;width:95px;flex-shrink:0'>{_sn}</div>"
                    f"<div style='flex:1;background:#1a1a2a;border-radius:3px;height:10px'>"
                    f"<div style='background:#2196f3;width:{min(_sp*3,100):.0f}%;"
                    f"height:100%;border-radius:3px'></div></div>"
                    f"<div style='color:#2196f3;font-size:11px;width:40px;text-align:right'>"
                    f"{_sp:.1f}%</div></div>",
                    unsafe_allow_html=True)
    with _hc2:
        if _tops:
            st.markdown("**🏆 前10大持股**")
            for _i, _top in enumerate(_tops[:10], 1):
                _tn_raw = str(_top.get("name", ""))
                _zh = _zh_holding(_tn_raw)
                _tn = _tn_raw[:22]
                _zh_html = (f"<span style='color:#ffb74d;font-size:10px;margin-left:6px'>"
                            f"({_zh})</span>" if _zh else "")
                _tp = float(_top.get("pct", 0) or 0)
                _ts = str(_top.get("sector", ""))[:12]
                st.markdown(
                    f"<div style='display:flex;gap:6px;padding:3px 8px;"
                    f"background:#161b22;border-radius:6px;margin:2px 0'>"
                    f"<span style='color:#555;font-size:11px;width:16px'>#{_i}</span>"
                    f"<span style='font-size:11px;flex:1'>{_tn}{_zh_html}</span>"
                    f"<span style='color:#888;font-size:10px'>{_ts}</span>"
                    f"<span style='color:#58a6ff;font-weight:700;font-size:11px;"
                    f"width:36px;text-align:right'>{_tp:.1f}%</span>"
                    f"</div>", unsafe_allow_html=True)


def render_fund_grp_health_extras(funds: list, principal_twd: float) -> None:
    """組合健檢 5 大貼圖區塊 entry。

    區塊順序：
      ① 基金體檢 PK 表（render_fund_checkup 一站涵蓋體檢 PK + 4 大健診卡）
      ③ 真實收益矩陣
      ④ 投資試算（每檔 expander）
      ⑤ TER + 持股分析（每檔 expander）
    """
    if not funds:
        return

    st.divider()
    st.markdown("## 🔬 進階分析（移植自組合基金 / 單一基金）")

    try:
        from ui.helpers.fund_checkup import render_fund_checkup
        render_fund_checkup(funds)
    except Exception as e:
        st.caption(f"⬜ 基金體檢 PK 表渲染失敗：[{type(e).__name__}] {str(e)[:80]}")

    try:
        _render_dividend_matrix(funds)
    except Exception as e:
        st.caption(f"⬜ 真實收益矩陣渲染失敗：[{type(e).__name__}] {str(e)[:80]}")

    st.divider()
    st.markdown("### 💼 逐檔深度分析（投資試算 + TER + 持股）")
    for _f in funds:
        _code = _f.get("code", "?")
        _name = (_f.get("name") or _code)[:30]
        with st.expander(f"💎 {_name}　·　{_code}", expanded=False):
            try:
                _render_investment_calc(_f, principal_twd)
            except Exception as e:
                st.caption(f"⬜ 投資試算失敗：[{type(e).__name__}] {str(e)[:80]}")
            st.divider()
            try:
                _render_holdings_block(_f)
            except Exception as e:
                st.caption(f"⬜ TER/持股渲染失敗：[{type(e).__name__}] {str(e)[:80]}")
