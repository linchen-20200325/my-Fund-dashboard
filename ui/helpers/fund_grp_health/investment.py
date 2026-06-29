"""v19.198 P1-6:④ 投資試算 + ⑤ TER/持股分析(從 fund_grp_health_extras 主檔抽出)。"""
from __future__ import annotations

import streamlit as st

from shared.colors import MATERIAL_GREEN, MATERIAL_ORANGE, MATERIAL_RED

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
