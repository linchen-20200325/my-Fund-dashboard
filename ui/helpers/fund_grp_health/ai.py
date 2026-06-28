"""v19.198 P1-6:⑫ AI 跨檔 + ⑬ 個股新聞 + ⑭ 三率穿透(從 fund_grp_health_extras 主檔抽出)。"""
from __future__ import annotations

import streamlit as st

from shared.colors import MATERIAL_GREEN, MATERIAL_ORANGE, MATERIAL_RED

from ui.helpers.fund_grp_health._utils import _safe_num


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
    from services.health.dividend import classify_eating_principal
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

