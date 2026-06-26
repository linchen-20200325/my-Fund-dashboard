"""v19.58 — 💊 組合健檢 Tab 5 大貼圖區塊（從組合基金 / 單一基金移植）。

內容鏡像 tab3_portfolio.py（組合基金）與 tab2_single_fund.py（單一基金）的
視覺區塊，不重複既有計算邏輯，全部呼叫 fund_checkup 與 macro_helpers
共用 helper。

5 大區塊：
  ① 基金體檢 PK 表（render_fund_checkup → 含 ② 4 大健診卡）
  ③ 真實收益 vs 配息率 健康矩陣（Plotly Bar，吃本金警示）
  ④ 投資試算 — 投入金額 → 單位數 / 月配息 TWD
  ⑤ TER 費用率 + 持股分析（產業配置 / 前10大持股）

v19.120 新增 P0 4 區塊（多檔比較專屬）:
  ⑥ 持股/產業相關性矩陣（Jaccard+Cosine + Pearson fallback,影子基金警示）
  ⑦ HWM σ 位階表（現價距歷史高點 + σ rank）
  ⑧ 風險指標對比表（σ/Sharpe/Sortino/Alpha/Beta 多檔並排）
  ⑨ -2σ 超跌警示 badges（深度超跌基金一覽）

v19.121 新增 P1 視覺 2 區塊（跨檔操作訊號 + 深度詳圖）:
  ⑩ MK 買賣點對比表（資產屬性 / 操作訊號 / 買賣水平線 / 現價位階）
  ⑪ Bollinger 可展開詳圖（逐檔 expander,點開才 render）

v19.122 新增 P1 AI 1 區塊（跨檔統一評論）:
  ⑫ AI 跨檔評論（複用 render_ai_summary_widget,組裝 snapshot 送 Gemini）

v19.123 新增 P1 最後 2 區塊（per-fund lazy fetch,避免 timeout）:
  ⑬ 個股新聞（per-fund expander + 按鈕觸發逐股 Google News）
  ⑭ 三率穿透（per-fund expander + 按鈕觸發 yfinance 持股財報掃描）

呼叫端：ui/tab_fund_grp_health.py：render_fund_grp_health_tab。
"""
from __future__ import annotations

import streamlit as st

from shared.colors import MATERIAL_GREEN, MATERIAL_ORANGE, MATERIAL_RED


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
            _rc_colors.append(MATERIAL_RED)
        elif _d > 0 and _r < _d * 1.2:
            _rc_colors.append(MATERIAL_ORANGE)
        else:
            _rc_colors.append(MATERIAL_GREEN)

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
            line=dict(color=MATERIAL_RED, width=1.5, dash="dot"),
            marker=dict(symbol="diamond", size=8, color=MATERIAL_RED),
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
                font=dict(color=MATERIAL_RED, size=11),
                bgcolor="rgba(42,10,10,0.85)",
                bordercolor=MATERIAL_RED, borderwidth=1,
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
    # v19.75 K2：遷移到 services/currency SSOT（mode="yf" 保留 health_extras 既有人民幣→CNH 行為）。
    from services.currency import normalize_ccy as _norm_ccy
    _ccy = _norm_ccy(_ccy_raw, default="TWD", mode="yf")
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
                _ter_c = (MATERIAL_RED if _ter_diff > 0.3
                          else (MATERIAL_ORANGE if _ter_diff > 0 else MATERIAL_GREEN))
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


# ════════════════════════════════════════════════════════════════
# v19.120 P0 — 多檔比較專屬區塊
# ════════════════════════════════════════════════════════════════

def _render_correlation_matrix(funds: list) -> None:
    """⑥ 持股/產業相關性矩陣(N×N 熱力圖 + 影子基金警示)。

    主算法:Jaccard(持股)×0.6 + Cosine(產業)×0.4,score ≥ 0.70 警示
    Fallback:NAV Pearson(持股資料缺時),> 0.85 警示
    SSOT:services/portfolio_service.py + shared/signal_thresholds.py

    §1 Fail Loud:< 2 檔基金 → skip;持股全缺 → fallback;Pearson 失敗 → caption error
    """
    if len(funds) < 2:
        st.divider()
        st.markdown("### 🔗 持股/產業相關性矩陣")
        st.caption("⬜ 至少需 2 檔基金才能計算相關性")
        return

    st.divider()
    st.markdown("### 🔗 持股/產業相關性矩陣")
    st.caption("Jaccard(持股)×0.6 + Cosine(產業)×0.4;**重疊度 ≥ 0.70 = 影子基金警告**(隱性重複曝險)")

    try:
        from services.portfolio_service import (
            calc_correlation_matrix,
            calc_holdings_overlap,
        )
    except Exception as e:
        st.caption(f"⬜ 相關性模組載入失敗:{type(e).__name__}: {e}")
        return

    # 主算法:Jaccard + Cosine(需持股 + 產業資料)
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
    _result = calc_holdings_overlap(_hov_input)

    # Fallback:持股全缺 → NAV Pearson
    _is_fallback = False
    if (not _result) or _result.get("method") == "n/a":
        _corr_input = [
            {"code": _f.get("code", "?"), "series": _f.get("series")}
            for _f in funds
        ]
        _result = calc_correlation_matrix(_corr_input)
        if _result is not None:
            _result.setdefault("method", "nav_fallback")
            _is_fallback = True
            _result.setdefault(
                "notes",
                f"持股/產業資料皆缺,降級為 NAV Pearson 相關({_result.get('freq', '?')}頻;"
                f">= 0.85 為 shadow)",
            )

    if not _result or _result.get("matrix") is None:
        st.caption("⬜ 相關性計算失敗(持股 + NAV 兩源都缺)")
        return

    _method = _result.get("method", "?")
    _notes = _result.get("notes", "")
    _shadow = _result.get("shadow_pairs", []) or []
    _thr = 0.85 if _is_fallback else 0.70
    _label = "相關係數" if _is_fallback else "重疊度"
    st.info(f"📌 計算方式:**{_method}**({_notes})")

    # 熱力圖
    try:
        import plotly.graph_objects as go
        _mx = _result["matrix"]
        fig = go.Figure(data=go.Heatmap(
            z=_mx.values,
            x=list(_mx.columns),
            y=list(_mx.index),
            colorscale=[[0, "#0e1117"], [0.5, "#2196f3"], [1, "#f44336"]],
            zmin=0, zmax=1,
            text=[[f"{v:.2f}" for v in row] for row in _mx.values],
            texttemplate="%{text}",
            textfont={"size": 11, "color": "white"},
            hovertemplate="%{y} vs %{x}<br>" + _label + ":%{z:.3f}<extra></extra>",
        ))
        fig.update_layout(
            paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
            font_color="#e6edf3",
            height=max(280, len(_mx) * 50 + 100),
            margin=dict(t=20, b=20, l=80, r=20),
        )
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.caption(f"⬜ 熱力圖渲染失敗:{type(e).__name__}: {e}")

    # 影子基金警示列表
    if _shadow:
        st.markdown(f"#### ⚠️ 偵測到 {len(_shadow)} 對影子基金({_label} ≥ {_thr})")
        for _pair in _shadow:
            _a, _b, _score = _pair[0], _pair[1], _pair[2]
            st.markdown(
                f"<div style='background:#2a0a0a;border-left:3px solid {MATERIAL_RED};"
                f"padding:6px 12px;margin:4px 0;border-radius:4px;'>"
                f"<b>{_a} ⟷ {_b}</b>　"
                f"<span style='color:{MATERIAL_RED};font-weight:700'>"
                f"{_label} {_score:.3f}</span>　"
                f"<span style='color:#888;font-size:11px'>建議檢視是否該擇一持有</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
    else:
        st.success(f"✅ 本組合無影子基金({_label} 皆 < {_thr})")


def _render_hwm_sigma_table(funds: list) -> None:
    """⑦ HWM σ 位階表(現價距歷史高點 + σ rank)。

    SSOT:services/precision_service.py calc_hwm_sigma_levels
    每檔 NAV 序列 → HWM / σ / current / σ_rank / label
    """
    st.divider()
    st.markdown("### 📐 HWM σ 位階")
    st.caption("HWM = 過去 252 天歷史最高 NAV;σ_rank = 現價在 HWM 下方第幾個 σ(負值)。"
               "**-2σ 以下 = 深度超跌**(若基本面健康可能是機會),**+1σ 以上 = 過熱**。")

    try:
        from services.precision_service import calc_hwm_sigma_levels
    except Exception as e:
        st.caption(f"⬜ HWM σ 模組載入失敗:{type(e).__name__}: {e}")
        return

    _rows = []
    for _f in funds:
        _code = _f.get("code", "?")
        _name = (_f.get("name") or _code)[:24]
        _series = _f.get("series")
        if _series is None or len(_series) < 30:
            _rows.append({
                "基金": f"{_name} ({_code})",
                "現價": "—", "HWM": "—",
                "距 HWM %": "—", "σ rank": "—",
                "位階": "⬜ NAV 不足 30 天",
            })
            continue
        _r = calc_hwm_sigma_levels(_series)
        if _r.get("error"):
            _rows.append({
                "基金": f"{_name} ({_code})",
                "現價": "—", "HWM": "—",
                "距 HWM %": "—", "σ rank": "—",
                "位階": f"⬜ {_r['error']}",
            })
            continue
        _rows.append({
            "基金": f"{_name} ({_code})",
            "現價": f"{_r['current_nav']:.2f}",
            "HWM": f"{_r['hwm']:.2f}",
            "距 HWM %": f"{_r['dist_to_hwm_pct']:+.2f}%",
            "σ rank": f"{_r['sigma_rank']:+.2f}σ",
            "位階": f"{_r.get('label', '—')}",
        })

    try:
        import pandas as pd
        st.dataframe(pd.DataFrame(_rows), use_container_width=True, hide_index=True)
    except Exception as e:
        st.caption(f"⬜ HWM σ 表渲染失敗:{type(e).__name__}: {e}")


def _render_risk_compare_table(funds: list) -> None:
    """⑧ 風險指標對比表(σ / Sharpe / Sortino / Alpha / Beta 多檔並排)。

    資料源:MoneyDJ wb07 已抓的 risk_metrics + metrics dict(不重算)。
    缺項顯示 '—',不偽造數值(§1 Fail Loud)。
    """
    st.divider()
    st.markdown("### 📊 風險指標對比表")
    st.caption("資料源:MoneyDJ wb07 風險表(直接顯示,不重算)。**Sharpe 越高越好 / σ 越低越穩**。")

    # v19.181 Bug 3 fix: MoneyDJ wb07 risk_metrics 是 **nested** 結構
    # ({risk_table: {期間: {標準差/Sharpe/Alpha/Beta}}}),不是 flat dict;
    # 過去 `_rm.get("std_dev")` flat lookup 永遠 None,所有欄位顯示 — 。
    # 改為:metrics(本地算)優先 → wb07 risk_table 多期間 nested fallback。
    _PERIOD_KEYS = ("近一年", "一年", "近1年", "1年", "近三年", "三年", "近六月", "六個月")

    def _lookup_risk_table(rm: dict, *zh_keys: str):
        """從 risk_table 多期間找第一個非空值,zh_keys 對齊 MoneyDJ 中文欄位名。"""
        rt = (rm or {}).get("risk_table") or {}
        for _p in _PERIOD_KEYS:
            _row = rt.get(_p) or {}
            for _k in zh_keys:
                v = _row.get(_k)
                n = _safe_num(v)
                if n is not None:
                    return n
        return None

    _rows = []
    for _f in funds:
        _code = _f.get("code", "?")
        _name = (_f.get("name") or _code)[:24]
        _mj = _f.get("moneydj_raw") or {}
        _m = _f.get("metrics") or {}
        _rm = _f.get("risk_metrics") or _mj.get("risk_metrics") or {}

        # σ:本地算 std_1y 優先 → wb07 risk_table["一年"]["標準差"]
        _sigma = _safe_num(_m.get("std_1y"))
        if _sigma is None:
            _sigma = _lookup_risk_table(_rm, "標準差", "年化標準差")

        # Sharpe:metrics.sharpe 優先 → wb07 risk_table["一年"]["Sharpe"]
        _sharpe = _safe_num(_m.get("sharpe"))
        if _sharpe is None:
            _sharpe = _lookup_risk_table(_rm, "Sharpe", "Sharpe Ratio", "夏普值")

        # Sortino:wb07 無此欄位,本地未算 → §1 Fail Loud,顯示 —
        _sortino = _safe_num(_m.get("sortino"))

        # Alpha / Beta:本地未算 → 只能走 wb07 nested
        _alpha = _safe_num(_m.get("alpha")) or _lookup_risk_table(_rm, "Alpha", "α")
        _beta = _safe_num(_m.get("beta")) or _lookup_risk_table(_rm, "Beta", "β")

        def _fmt(v):
            return f"{v:.2f}" if v is not None else "—"

        _rows.append({
            "基金": f"{_name} ({_code})",
            "σ (年化%)": _fmt(_sigma),
            "Sharpe": _fmt(_sharpe),
            "Sortino": _fmt(_sortino),
            "Alpha": _fmt(_alpha),
            "Beta": _fmt(_beta),
        })

    try:
        import pandas as pd
        st.dataframe(pd.DataFrame(_rows), use_container_width=True, hide_index=True)
        # 統計:有資料的基金數 / 全部
        _has_sharpe = sum(1 for r in _rows if r["Sharpe"] != "—")
        if _has_sharpe < len(_rows):
            st.caption(
                f"⬜ {len(_rows) - _has_sharpe} / {len(_rows)} 檔基金 MoneyDJ 風險表"
                f"資料不全(顯示 '—',不偽造)"
            )
    except Exception as e:
        st.caption(f"⬜ 風險表渲染失敗:{type(e).__name__}: {e}")


def _render_oversold_badges(funds: list) -> None:
    """⑨ -2σ 超跌警示 badges(深度超跌基金一覽)。

    依 HWM σ rank 篩 σ ≤ -2.0 的基金。
    深度超跌 + 基本面健康 = 抄底機會;若基本面也差 = 真實衰退,不要接刀。
    """
    st.divider()
    st.markdown("### 🩸 -2σ 超跌警示")

    try:
        from services.precision_service import calc_hwm_sigma_levels
    except Exception as e:
        st.caption(f"⬜ σ 模組載入失敗:{type(e).__name__}: {e}")
        return

    _oversold = []
    for _f in funds:
        _code = _f.get("code", "?")
        _name = (_f.get("name") or _code)[:24]
        _series = _f.get("series")
        if _series is None or len(_series) < 30:
            continue
        _r = calc_hwm_sigma_levels(_series)
        if _r.get("error"):
            continue
        _sigma_rank = _r.get("sigma_rank")
        if _sigma_rank is not None and _sigma_rank <= -2.0:
            _oversold.append({
                "code": _code, "name": _name,
                "sigma_rank": _sigma_rank,
                "dist_pct": _r.get("dist_to_hwm_pct", 0),
                "current": _r.get("current_nav"),
                "hwm": _r.get("hwm"),
            })

    if not _oversold:
        st.success("✅ 目前無基金落入 -2σ 深度超跌區")
        return

    st.caption(f"⚠️ 偵測到 **{len(_oversold)} 檔基金** σ ≤ -2.0(歷史高點下方 2 個標準差以上)")
    for _o in _oversold:
        st.markdown(
            f"<div style='background:#2a0a0a;border-left:4px solid {MATERIAL_RED};"
            f"padding:8px 14px;margin:6px 0;border-radius:6px;'>"
            f"<b style='color:#ff6b6b'>🩸 {_o['name']} ({_o['code']})</b><br>"
            f"<span style='color:#ccc;font-size:12px'>"
            f"現價 {_o['current']:.2f} ｜ HWM {_o['hwm']:.2f} ｜ "
            f"距高點 <b style='color:{MATERIAL_RED}'>{_o['dist_pct']:+.2f}%</b> ｜ "
            f"σ rank <b style='color:{MATERIAL_RED}'>{_o['sigma_rank']:+.2f}σ</b>"
            f"</span><br>"
            f"<span style='color:#888;font-size:11px'>"
            f"💡 深度超跌:若基本面(評分/吃本金/Sharpe)仍健康 → 可考慮抄底;"
            f"基本面也轉差 → 不要接刀</span>"
            f"</div>",
            unsafe_allow_html=True,
        )


# ════════════════════════════════════════════════════════════════
# v19.121 P1 視覺 — MK 買賣點表 + Bollinger 可展開詳圖
# ════════════════════════════════════════════════════════════════

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
                        line=dict(color="#9c27b0", width=1, dash="dot"),
                    ))
                # NAV 主線
                fig.add_trace(go.Scatter(
                    x=_df["date"], y=_df["nav"], name="淨值",
                    mode="lines",
                    line=dict(color="#2196f3", width=2),
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
                    (_safe_num(_m.get("buy1")), "買1 (年高-1σ)", "#69f0ae"),
                    (_safe_num(_m.get("buy2")), "買2 (年高-2σ)", MATERIAL_GREEN),
                    (_safe_num(_m.get("buy3")), "買3 (年高-3σ)", "#9c27b0"),
                ]:
                    if _bv is not None:
                        fig.add_hline(y=_bv, line_color=_bc, line_dash="dot",
                                      annotation_text=_bl,
                                      annotation_font_color=_bc,
                                      annotation_position="bottom right")
                for _sv, _sl, _sc in [
                    (_safe_num(_m.get("sell1")), "賣1 (年低+1σ)", "#ffa726"),
                    (_safe_num(_m.get("sell2")), "賣2 (年低+2σ)", "#ff7043"),
                    (_safe_num(_m.get("sell3")), "賣3 (年低+3σ)", MATERIAL_RED),
                ]:
                    if _sv is not None:
                        fig.add_hline(y=_sv, line_color=_sc, line_dash="dash",
                                      annotation_text=_sl,
                                      annotation_font_color=_sc,
                                      annotation_position="top right")

                fig.update_layout(
                    paper_bgcolor="#0e1117", plot_bgcolor="#161b22",
                    font_color="#e6edf3", height=360,
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

def _build_cross_fund_snapshot(funds: list) -> tuple[str, int]:
    """組裝 N 檔基金的跨檔 snapshot 字串給 AI 解讀。

    內容:
      - 整組概況(檔數 / 平均覆蓋率 / 平均 σ rank / 超跌統計)
      - 逐檔簡表(代號 / 名稱 / 配息率 / 覆蓋率燈號 / σ rank / MK 操作建議)
      - 跨檔影子基金清單(若有)

    回傳:(snapshot_str, n_funds_with_data)
    """
    if not funds:
        return ("(無基金資料)", 0)

    _lines = [f"## 組合健檢全章節快照({len(funds)} 檔基金)"]

    # 取共享計算結果(避免每段重算)
    from services.fund_dividend_health import classify_eating_principal
    try:
        from services.precision_service import calc_hwm_sigma_levels
    except Exception:
        calc_hwm_sigma_levels = None

    _per_fund = []
    _eating_count = 0
    _oversold_count = 0
    _sigma_ranks = []
    for _f in funds:
        _code = _f.get("code", "?")
        _name = (_f.get("name") or _code)[:20]
        _m = _f.get("metrics") or {}
        _mj = _f.get("moneydj_raw") or {}

        # 配息覆蓋率
        _adr = _safe_num(_mj.get("moneydj_div_yield") or _m.get("annual_div_rate"))
        _ret1y = _safe_num(_m.get("ret_1y_total") or _m.get("ret_1y"))
        _core_div = classify_eating_principal(_ret1y, _adr)
        _div_status = "—"
        if _core_div.is_data_missing:
            _div_status = "資料不足"
        elif _core_div.is_no_dividend:
            _div_status = "無配息"
        elif _core_div.is_eating:
            _div_status = "🔴 吃本金"
            _eating_count += 1
        elif _core_div.coverage_ratio is not None and _core_div.coverage_ratio < 1.2:
            _div_status = "🟡 邊緣"
        else:
            _div_status = "🟢 健康"

        # σ 位階
        _sigma_label = "—"
        _sigma_rank = None
        _series = _f.get("series")
        if calc_hwm_sigma_levels and _series is not None and len(_series) >= 30:
            try:
                _hwm = calc_hwm_sigma_levels(_series)
                if not _hwm.get("error"):
                    _sigma_rank = _hwm.get("sigma_rank")
                    _sigma_label = _hwm.get("label", "—")
                    if _sigma_rank is not None and _sigma_rank <= -2.0:
                        _oversold_count += 1
                    if _sigma_rank is not None:
                        _sigma_ranks.append(_sigma_rank)
            except Exception:
                pass

        # 風險指標
        _rm = _f.get("risk_metrics") or _mj.get("risk_metrics") or {}
        _sharpe = _safe_num(_rm.get("sharpe") or _m.get("sharpe"))

        _per_fund.append({
            "code": _code, "name": _name,
            "div_pct": _adr, "ret1y": _ret1y, "div_status": _div_status,
            "coverage": _core_div.coverage_ratio,
            "sigma_label": _sigma_label, "sigma_rank": _sigma_rank,
            "sharpe": _sharpe,
        })

    # 整組概況
    _avg_sigma = (sum(_sigma_ranks) / len(_sigma_ranks)) if _sigma_ranks else None
    _lines.append("")
    _lines.append("### 整組概況")
    _lines.append(f"- 基金數:{len(funds)} 檔")
    _lines.append(f"- 🔴 吃本金:{_eating_count} 檔 / {len(funds)}")
    _lines.append(f"- 🩸 深度超跌(σ ≤ -2):{_oversold_count} 檔 / {len(funds)}")
    if _avg_sigma is not None:
        _lines.append(f"- 平均 σ rank:{_avg_sigma:+.2f}σ "
                      f"(負 = 整組偏離歷史高點下方)")

    # 逐檔簡表
    _lines.append("")
    _lines.append("### 逐檔健診")
    for _p in _per_fund:
        _bits = [f"{_p['name']} ({_p['code']})"]
        if _p["div_pct"] is not None:
            _bits.append(f"配息 {_p['div_pct']:.2f}%")
        if _p["ret1y"] is not None:
            _bits.append(f"1Y 含息 {_p['ret1y']:.2f}%")
        if _p["coverage"] is not None:
            _bits.append(f"覆蓋率 {_p['coverage']:.2f}")
        _bits.append(_p["div_status"])
        if _p["sigma_rank"] is not None:
            _bits.append(f"σ {_p['sigma_rank']:+.2f}")
        if _p["sharpe"] is not None:
            _bits.append(f"Sharpe {_p['sharpe']:.2f}")
        _lines.append(f"- {' ｜ '.join(_bits)}")

    # 跨檔相關性(影子基金)
    try:
        from services.portfolio_service import calc_holdings_overlap
        _hov_input = [
            {
                "code": _f.get("code", "?"),
                "name": _f.get("name") or _f.get("code"),
                "top_holdings": ((_f.get("moneydj_raw") or {}).get("holdings") or {}).get("top_holdings") or [],
                "sector_alloc": ((_f.get("moneydj_raw") or {}).get("holdings") or {}).get("sector_alloc") or [],
            }
            for _f in funds
        ]
        _hov = calc_holdings_overlap(_hov_input)
        _lines.append("")
        _lines.append("### 跨檔重疊度")
        if _hov and _hov.get("shadow_pairs"):
            _lines.append(f"- ⚠️ 偵測到 {len(_hov['shadow_pairs'])} 對影子基金(重疊度 ≥ 0.70):")
            for _pair in _hov["shadow_pairs"]:
                _lines.append(f"  - {_pair[0]} ⟷ {_pair[1]}:重疊度 {_pair[2]:.3f}")
        else:
            _lines.append("- ✅ 本組合無影子基金")
    except Exception:
        pass

    return ("\n".join(_lines), len(funds))


def _render_ai_cross_fund_evaluation(funds: list) -> None:
    """⑫ AI 跨檔統一評論(N 檔基金組合)。

    複用 ui/helpers/ai_summary.render_ai_summary_widget(已成熟,Gemini 多 key 輪替)。
    產出:逐段白話「整組是好是壞、哪幾檔該換、配息健康、影子基金、調整建議」。
    """
    st.divider()
    st.markdown("### 🤖 AI 跨檔統一評論")

    if not funds:
        st.caption("⬜ 無基金資料")
        return

    # GEMINI key 取得(沿用既有 pattern)
    import os
    _key = os.environ.get("GEMINI_API_KEY", "")
    if not _key and hasattr(st, "secrets"):
        try:
            _key = st.secrets.get("GEMINI_API_KEY", "") or ""
        except Exception:
            _key = ""
    if not _key:
        st.caption("⬜ 未設定 GEMINI_API_KEY(secrets / env),無法呼叫 AI")
        return

    # 組裝 snapshot
    try:
        _snap, _n = _build_cross_fund_snapshot(funds)
    except Exception as e:
        st.caption(f"⬜ Snapshot 組裝失敗:{type(e).__name__}: {e}")
        return

    # 呼叫共用 AI widget
    try:
        from ui.helpers.ai_summary import render_ai_summary_widget
        render_ai_summary_widget(
            tab_key="tab5_grp",
            tab_label=f"組合健檢({_n} 檔基金)",
            snapshot=_snap,
            sections=[
                "整組概況",
                "配息健康總覽",
                "風險位階 / 超跌警示",
                "跨檔重疊度 / 影子基金",
                "換手與調整建議",
            ],
            headlines=[],
            stale_note="本快照為當下抓取的瞬時值",
            gemini_api_key=_key,
            expanded=False,
        )
    except Exception as e:
        st.caption(f"⬜ AI widget 渲染失敗:{type(e).__name__}: {e}")


# ════════════════════════════════════════════════════════════════
# v19.123 P1 — 個股新聞 + 三率穿透(per-fund lazy expander)
# ════════════════════════════════════════════════════════════════

def _render_per_fund_news_expanders(funds: list) -> None:
    """⑬ 個股新聞 — 逐基金 expander,user 點按鈕才抓(避免 N×6 同時抓 timeout)。

    每檔基金:
      - expander 預設 collapsed,點開只顯示按鈕
      - 點「📡 抓持股新聞」才呼叫 fetch_stock_news 對前 6 大持股逐一搜尋
      - 結果存 session_state(tab5_grp 命名空間,避免與 Tab 2 衝突)

    SSOT:repositories.news_repository.fetch_stock_news
    """
    st.divider()
    st.markdown("### 📰 持股新聞(逐基金按需抓取)")
    st.caption("N 檔基金 × 6 大持股 ≈ 60+ API call → 改為**按基金 expander 點按鈕才抓**,避免 timeout。")

    if not funds:
        st.caption("⬜ 無基金資料")
        return

    try:
        from repositories.news_repository import fetch_stock_news
    except Exception as e:
        st.caption(f"⬜ 新聞模組載入失敗:{type(e).__name__}: {e}")
        return

    try:
        from ui.helpers.holdings import _zh_holding  # type: ignore
    except Exception:
        def _zh_holding(_n):  # type: ignore
            return ""

    for _f in funds:
        _code = _f.get("code", "?")
        _name = (_f.get("name") or _code)[:30]
        _mj = _f.get("moneydj_raw") or {}
        _holdings = _mj.get("holdings") or {}
        _tops = _holdings.get("top_holdings") or []

        with st.expander(f"📰 {_name}　·　{_code}", expanded=False):
            if not _tops:
                st.caption("⬜ MoneyDJ 未提供持股,無法抓新聞")
                continue

            # 前 6 大持股(顯示名, 查詢字)
            _hold_list = []
            for _topn in _tops[:6]:
                _nm = str(_topn.get("name", "")).strip()
                if not _nm:
                    continue
                _zh = _zh_holding(_nm)
                _hold_list.append((_zh or _nm[:20], _zh or _nm))

            if not _hold_list:
                st.caption("⬜ 持股名稱解析失敗")
                continue

            _ss_key = f"_tab5grp_stknews_{_code}"
            _btn_col, _info_col = st.columns([1, 3])
            with _btn_col:
                _do_fetch = st.button(
                    f"📡 抓 {len(_hold_list)} 檔持股新聞",
                    key=f"btn_tab5grp_stknews_{_code}",
                    use_container_width=True,
                )
            with _info_col:
                _existing = st.session_state.get(_ss_key)
                if _existing:
                    _tot = sum(len(v) for v in _existing.values())
                    st.caption(f"✅ 已快取 {_tot} 則新聞({len(_existing)} 檔持股命中)")
                else:
                    st.caption(f"逐一搜尋 Google News(中文,走 NAS proxy);最多 {len(_hold_list) * 3} 則")

            if _do_fetch:
                _fetched: dict = {}
                _prog = st.progress(0.0, text="📥 逐股搜尋中…")
                for _ci, (_disp, _q) in enumerate(_hold_list):
                    try:
                        _items = fetch_stock_news(_q, max_items=3)
                    except Exception as _e_news:
                        print(f"[tab5grp_news/{_code}/{_q}] {type(_e_news).__name__}: {_e_news}")
                        _items = []
                    if _items:
                        _fetched[_disp] = _items
                    _prog.progress((_ci + 1) / max(len(_hold_list), 1),
                                   text=f"📥 {_ci+1}/{len(_hold_list)}")
                _prog.empty()
                st.session_state[_ss_key] = _fetched

            _stk_data = st.session_state.get(_ss_key)
            if _stk_data:
                for _disp_nm, _items in _stk_data.items():
                    for _it in _items:
                        _u = _it.get("url", "")
                        _ttl = _it.get("title", "")
                        _src = _it.get("source", "")
                        _lh = (f"<a href='{_u}' target='_blank' "
                               f"style='color:#58a6ff;text-decoration:none'>{_ttl}</a>"
                               if _u else _ttl)
                        st.markdown(
                            f"<div style='padding:4px 8px;background:#161b22;"
                            f"border-radius:6px;margin:2px 0;font-size:12px'>"
                            f"<span style='color:#ffb74d;font-weight:700'>{_disp_nm}</span>　"
                            f"{_lh}<span style='color:#666;font-size:10px;"
                            f"margin-left:6px'>{_src}</span></div>",
                            unsafe_allow_html=True,
                        )
            elif _do_fetch:
                st.caption("⬜ 逐股搜尋後仍無結果(NAS Proxy 可能斷線 / 持股近期無中文新聞)")


def _render_per_fund_three_ratio_expanders(funds: list) -> None:
    """⑭ 三率穿透 — 逐基金 expander,user 點按鈕才掃(避免 N×10 yfinance timeout)。

    每檔基金:
      - expander 預設 collapsed
      - 點「🔍 三率穿透掃描」才呼叫 PSE.fetch_stock_three_ratios 對前 10 大持股逐一抓財報
      - 彙總 verdict + 逐持倉明細
      - session_state 隔離(tab5_grp 命名空間)

    SSOT:services.precision_service.PrecisionStrategyEngine
    """
    st.divider()
    st.markdown("### 🛡️ 微觀防護盾 — 持倉三率穿透(逐基金按需掃描)")
    st.caption(
        "對前 10 大持倉抓 yfinance 財報(毛利率 / 營業利益率 / 淨利率 QoQ),"
        "識別「估值虛漲 vs 實質獲利」陷阱。N 檔 × 10 持股 = 100+ API,故**按基金分開掃**。"
    )

    if not funds:
        st.caption("⬜ 無基金資料")
        return

    try:
        from services.precision_service import (
            PrecisionStrategyEngine as _PSE,
            three_ratio_row_html as _tr_html,
        )
    except Exception as e:
        st.caption(f"⬜ 三率模組載入失敗:{type(e).__name__}: {e}")
        return

    _pse = _PSE()

    for _f in funds:
        _code = _f.get("code", "?")
        _name = (_f.get("name") or _code)[:30]
        _mj = _f.get("moneydj_raw") or {}
        _holdings = _mj.get("holdings") or {}
        _tops = (_holdings.get("top_holdings") or [])[:10]

        with st.expander(f"🛡️ {_name}　·　{_code}", expanded=False):
            if not _tops:
                st.caption("⬜ MoneyDJ 未提供持股,無法掃三率")
                continue

            _ss_key = f"_tab5grp_shield_{_code}"
            _btn_col, _info_col = st.columns([1, 3])
            with _btn_col:
                _do_scan = st.button(
                    f"🔍 掃 {len(_tops)} 檔持股三率",
                    key=f"btn_tab5grp_shield_{_code}",
                    use_container_width=True,
                )
            with _info_col:
                _cached = st.session_state.get(_ss_key)
                if _cached is not None:
                    st.caption(f"✅ 已掃 {len(_cached)} 檔成功(共 {len(_tops)} 持股)")
                else:
                    st.caption("yfinance 抓財報 ~5-10s / 檔")

            if _do_scan:
                _results = []
                _prog = st.progress(0.0, text="🔍 掃描財報…")
                for _i, _top in enumerate(_tops):
                    _sh_name = _top.get("name", "")
                    try:
                        _data = _pse.fetch_stock_three_ratios(_sh_name)
                    except Exception as _e_sh:
                        print(f"[tab5grp_shield/{_code}/{_sh_name}] "
                              f"{type(_e_sh).__name__}: {_e_sh}")
                        _data = None
                    if _data:
                        _results.append(_data)
                    _prog.progress((_i + 1) / len(_tops),
                                   text=f"🔍 {_i+1}/{len(_tops)}")
                _prog.empty()
                st.session_state[_ss_key] = _results

            _cached = st.session_state.get(_ss_key)
            if _cached is not None and _cached:
                # 彙總 verdict
                try:
                    _verdict = _pse.evaluate_fund_three_ratios(_cached)
                    _vc = (MATERIAL_GREEN if "🟢" in _verdict
                           else MATERIAL_RED if "🔴" in _verdict
                           else MATERIAL_ORANGE)
                    st.markdown(
                        f"<div style='background:#0d1117;border:2px solid {_vc};"
                        f"border-radius:10px;padding:10px 16px;margin:8px 0;"
                        f"font-size:13px;font-weight:700;color:{_vc}'>"
                        f"{_verdict}</div>",
                        unsafe_allow_html=True,
                    )
                except Exception as _e_v:
                    st.caption(f"⬜ 彙總失敗:{type(_e_v).__name__}: {_e_v}")
                # 逐持倉明細
                try:
                    _html = "".join(_tr_html(r) for r in _cached)
                    st.markdown(_html, unsafe_allow_html=True)
                except Exception as _e_h:
                    st.caption(f"⬜ 明細渲染失敗:{type(_e_h).__name__}: {_e_h}")
                # 未解析持股
                _resolved = {r.get("stock") for r in _cached}
                _failed = [_t.get("name", "") for _t in _tops
                           if _t.get("name", "") not in _resolved]
                if _failed:
                    st.caption(
                        f"以下持倉 Ticker 無法解析(外幣基金/罕見代碼):"
                        f"{', '.join(_failed[:5])}"
                        + (f" ...等 {len(_failed)} 檔" if len(_failed) > 5 else "")
                    )
            elif _cached is not None and not _cached:
                st.warning("所有持倉均無法解析 Ticker 或 yfinance 暫無財報")


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

    # v19.120 P0 — 多檔比較專屬區塊(每個 try/except 不擋下一個)
    try:
        _render_correlation_matrix(funds)
    except Exception as e:
        st.caption(f"⬜ 相關性矩陣渲染失敗：[{type(e).__name__}] {str(e)[:80]}")
    try:
        _render_hwm_sigma_table(funds)
    except Exception as e:
        st.caption(f"⬜ HWM σ 表渲染失敗：[{type(e).__name__}] {str(e)[:80]}")
    try:
        _render_risk_compare_table(funds)
    except Exception as e:
        st.caption(f"⬜ 風險表渲染失敗：[{type(e).__name__}] {str(e)[:80]}")
    try:
        _render_oversold_badges(funds)
    except Exception as e:
        st.caption(f"⬜ 超跌警示渲染失敗：[{type(e).__name__}] {str(e)[:80]}")

    # v19.121 P1 視覺 — MK 買賣點對比 + Bollinger 可展開詳圖
    try:
        _render_mk_signal_table(funds)
    except Exception as e:
        st.caption(f"⬜ MK 買賣點對比渲染失敗：[{type(e).__name__}] {str(e)[:80]}")
    try:
        _render_bollinger_expanders(funds)
    except Exception as e:
        st.caption(f"⬜ Bollinger 詳圖渲染失敗：[{type(e).__name__}] {str(e)[:80]}")

    # v19.122 P1 AI — 跨檔統一評論
    try:
        _render_ai_cross_fund_evaluation(funds)
    except Exception as e:
        st.caption(f"⬜ AI 跨檔評論渲染失敗：[{type(e).__name__}] {str(e)[:80]}")

    # v19.123 P1 — 個股新聞 + 三率穿透(per-fund lazy)
    try:
        _render_per_fund_news_expanders(funds)
    except Exception as e:
        st.caption(f"⬜ 個股新聞渲染失敗：[{type(e).__name__}] {str(e)[:80]}")
    try:
        _render_per_fund_three_ratio_expanders(funds)
    except Exception as e:
        st.caption(f"⬜ 三率穿透渲染失敗：[{type(e).__name__}] {str(e)[:80]}")
