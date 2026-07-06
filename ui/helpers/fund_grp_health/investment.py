"""v19.198 P1-6:④ 投資試算 + ⑤ TER/持股分析(從 fund_grp_health_extras 主檔抽出)。"""
from __future__ import annotations

import streamlit as st

from shared.colors import GH_BG_CARD, GH_BORDER, GRAY_55, MATERIAL_GREEN, MATERIAL_ORANGE, MATERIAL_RED, TRAFFIC_NEUTRAL

from ui.helpers.fund_grp_health._utils import _safe_num


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
            from services.fund_service import get_latest_fx
            _fx = get_latest_fx(f"{_ccy}TWD=X")
            if _fx is None or _fx <= 0:
                _fx = None
        except Exception:
            _fx = None

    st.markdown(
        f"#### 💰 投資試算 — 投入金額 → 單位數 / 配息估算 "
        f"<span style='color:{TRAFFIC_NEUTRAL};font-size:11px'>{_code} / {_ccy}</span>",
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
    # v19.324→v19.325:月配息 / 每月配息單位數優先「最近一筆真實配息記錄」,
    # 真實記錄缺 → 年化配息率估算 fallback,並註記來源(真實/估算)。
    # 全站(Tab2 / Tab3 / 健檢 ②)同源走 dividend_calc.monthly_dividend_from_records。
    from services.health.dividend_calc import monthly_dividend_from_records
    _fx_eff = _fx if (_ccy != "TWD" and _fx) else 1.0
    _divs = fund.get("dividends") or _mj.get("dividends") or []
    _mdiv = monthly_dividend_from_records(_divs, _units, _nav, _fx_eff, adr_pct=_adr)
    _src = _mdiv["source"]
    _latest = _mdiv["latest_div_per_unit"]
    _mon_div_twd = _mdiv["mon_div_twd"]
    _mon_units = _mdiv["mon_div_units"]
    if _mon_units is not None:
        _src_lbl = "真實記錄" if _src == "records" else "年化估算"
        _mc2.metric("月配息（TWD）", f"{_mon_div_twd:,.0f}" if _mon_div_twd else "—")
        _mc3.metric("每月配息單位數", f"{_mon_units:,.2f}",
                    help=f"最近一筆實際配息 × 持有單位 ÷ NAV（來源：{_src_lbl}）")
        _mc4.metric("年化配息率", f"{_adr:.2f}%" if _adr else "—",
                    help="MoneyDJ wb05 官方年化配息率")
        if _src == "records":
            _note = f"📊 配息來源：**真實記錄**（最近一筆實配 {_latest:,.4f} {_ccy}/單位）"
        else:
            _note = (f"〜 配息來源：**年化估算**（無逐筆配息記錄，"
                     f"以年化配息率 {_adr:.2f}% ÷ 12 攤平，季配/年配某些月實際為 0）")
        if _ccy != "TWD":
            st.success(
                f"💱 **換算 TWD**（1 {_ccy} = {_fx:.4f}）："
                f"本金 {float(principal_twd):,.0f} TWD → "
                f"原幣本金 **{_amt_local:,.2f}** {_ccy} → "
                f"可買 **{_units:,.2f}** 單位"
                f"（每月 ≈ **{_mon_div_twd:,.0f}** TWD / "
                f"配息單位 ≈ **{_mon_units:,.2f}** 單位）\n\n{_note}"
            )
        else:
            st.success(
                f"📌 本金 {float(principal_twd):,.0f} TWD → "
                f"可買 **{_units:,.2f}** 單位"
                f"（每月 ≈ **{_mon_div_twd:,.0f}** TWD / "
                f"配息單位 ≈ **{_mon_units:,.2f}** 單位）\n\n{_note}"
            )
    else:
        st.caption("⬜ 無配息記錄且無年化配息率，無月配試算")


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
                    f"<div><div style='color:{TRAFFIC_NEUTRAL};font-size:10px'>同類均值</div>"
                    f"<div style='color:{TRAFFIC_NEUTRAL};font-weight:700;font-size:16px'>"
                    f"{_ter_avg:.2f}%</div></div>"
                    f"<div><div style='color:{TRAFFIC_NEUTRAL};font-size:10px'>費用比較</div>"
                    f"<div style='color:{_ter_c};font-weight:700;font-size:16px'>"
                    f"{_ter_vs}</div></div>"
                )
            else:
                _ter_c, _ter_avg_html = TRAFFIC_NEUTRAL, ""
            st.markdown(
                f"<div style='background:{GH_BG_CARD};border:1px solid {GH_BORDER};"
                "border-radius:10px;padding:10px 16px;margin:8px 0'>"
                f"<div style='color:{TRAFFIC_NEUTRAL};font-size:11px;margin-bottom:6px'>"
                "💰 TER 費用率分析"
                + (f" — {_ter_cat[:12]}" if _ter_cat else "") + "</div>"
                f"<div style='display:flex;gap:24px;flex-wrap:wrap;margin-bottom:6px'>"
                f"<div><div style='color:{TRAFFIC_NEUTRAL};font-size:10px'>最高經理費</div>"
                f"<div style='color:{_ter_c};font-weight:700;font-size:16px'>"
                f"{_ter_val:.2f}%</div></div>"
                + _ter_avg_html +
                "</div>"
                f"<div style='color:{GRAY_55};font-size:10px'>"
                "費用率愈低，長期複利效益愈佳（費用每降 1%，20 年後終值多 ~25%）</div>"
                "</div>", unsafe_allow_html=True)
    else:
        st.caption("💰 TER 費用率分析 — ⬜ 缺 mgmt_fee 資料")

    # v19.282 SSOT:持股明細改呼共用 render(ui.helpers.holdings),不再各寫一份
    from ui.helpers.holdings import render_holdings_detail
    _holdings = _mj.get("holdings", {}) or {}
    _hdate = _holdings.get("data_date", "")
    if not (_holdings.get("sector_alloc") or _holdings.get("top_holdings")):
        st.caption("📂 持股分析 — ⬜ MoneyDJ 未提供持股 / 產業資料")
        return
    st.markdown(
        "**📂 持股分析**"
        + (f"<span style='color:{TRAFFIC_NEUTRAL};font-size:11px;margin-left:8px'>"
           f"（{_hdate}）</span>" if _hdate else ""),
        unsafe_allow_html=True,
    )
    render_holdings_detail(_holdings)
