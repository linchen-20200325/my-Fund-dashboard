"""ui/tab2_single_fund.py — 單一基金深度分析 Tab（v18.126 B-C.4）

從 app.py 抽出 Tab2（單一基金深度分析）的渲染邏輯。

設計：
- render_single_fund_tab() -> None **零閉包依賴**（與 Tab4/5/6 同設計）
- 外部 helper 從 ui.helpers.session import（_friendly_error / _is_core_fund / calc_data_health）

對外 API:
- render_single_fund_tab() -> None
"""
from __future__ import annotations

import concurrent.futures as _bt_cf  # 未必用到但與 backtest 同 pattern
import datetime
import os
import time as _time_mod

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from infra.proxy import get_proxy_config
from models.policy import fund_pk_str, make_pk
from repositories.fund_repository import (
    fetch_fund_from_moneydj_url,
    tdcc_search_fund,
)
from services.ai_service import (
    analyze_fund_json,
    event_impact_analysis,
)
from services.fund_service import (
    calc_metrics,
    calc_dividend_estimate,
)
from services.portfolio_service import dividend_safety as div_safety_check
from services.precision_service import (
    PrecisionStrategyEngine,
    calc_hwm_sigma_levels,
    risk_score_gauge_html,
    three_ratio_row_html,
)
from ui.helpers.macro_helpers import (
    mk_fund_signal,
    quartile_check as _quartile_check,
)
from ui.helpers.metric_explainers import render_metric_explainer
from ui.helpers.session import (
    friendly_error as _friendly_error,
    is_core_fund as _is_core_fund,
    calc_data_health as _calc_data_health_pure,
)

# 其他可能需要的 app.py module-level helpers — 用 lazy import 避免 circular
# fund_fetcher 內的 utility 函式（normalize_result_state / classify_fetch_status）
from fund_fetcher import (
    classify_fetch_status,
    normalize_result_state,
    clean_risk_table,
    safe_float,
)


def _calc_data_health(indicators=None):
    """同 app.py wrapper：indicators=None → 走 session_state。"""
    ind = indicators if indicators is not None else st.session_state.get("indicators", {})
    return _calc_data_health_pure(ind)


def render_single_fund_tab() -> None:
    """渲染單一基金深度分析 Tab — MoneyDJ 抓取 + 風險指標 + AI 分析。

    Caller 不需傳參數；Tab 內外部依賴透過 ui.helpers.session 等 import 自取。
    """
    # v18.126 B-C.4: GEMINI_KEY 走 env（app.py:_load_keys 已注入）
    GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")

    # v18.139: _update_data_registry / _zh_holding 已搬到 ui/helpers/
    # 改正規 import 取代 v18.129 sys.modules['__main__'] hack
    from ui.helpers.data_registry import _update_data_registry
    from ui.helpers.holdings import _zh_holding

    st.markdown("## 🔍 單一基金深度分析")
    st.caption("輸入 MoneyDJ 代碼或網址，即時抓取淨值 / 持股 / 配息 / 風險指標")

    # ── 輸入列（自動偵測境內/境外，移除 radio）────────────────────
    _t2_input_col, _t2_btn_col = st.columns([5.6, 1])
    with _t2_input_col:
        mj_url_input = st.text_input("MoneyDJ URL 或代碼",
            placeholder="輸入代碼（TLZF9 / ACTI94）或貼上完整 MoneyDJ 網址",
            label_visibility="collapsed", key="mj_url_input")
    with _t2_btn_col:
        do_load = st.button("🚀 分析", type="primary", use_container_width=True, key="btn_mj_load")

    def _build_moneydj_url(raw_input: str, page_type: str) -> str:
        _raw = raw_input.strip()
        if _raw.startswith("http"):
            return _raw
        return f"https://www.moneydj.com/funddj/ya/{page_type}.djhtm?a={_raw.upper()}"

    def _auto_fetch_moneydj(raw_input: str):
        """自動偵測境內/境外：URL 明確指定時直接用；純代碼先試境內，失敗再試境外。

        v18.120 issue 2 修法：原邏輯 partial 也立即 short-circuit return。
        對境外基金 TLZF9 試 yp010000 → 拿到 nav_latest + fund_name 但 series=0
        → 被當成 partial 直接 return → 不會試正確的 yp010001。
        新邏輯：partial 但 series 完全空 → 繼續試下一個 page_type；
        累計嘗試所有 page_type 後，選最佳結果（complete > partial-with-series > partial-empty）
        """
        _raw = raw_input.strip()
        # URL 已含 page_type 資訊
        if "yp010000" in _raw:
            return fetch_fund_from_moneydj_url(_raw), "yp010000"
        if "yp010001" in _raw:
            return fetch_fund_from_moneydj_url(_raw), "yp010001"
        # 純代碼：累計嘗試所有 page_type，挑最佳結果
        _attempts: list = []
        for _pt in ["yp010000", "yp010001"]:
            _url = _build_moneydj_url(_raw, _pt)
            _res = normalize_result_state(fetch_fund_from_moneydj_url(_url))
            _st  = _res.get("status", classify_fetch_status(_res))
            _ser = _res.get("series")
            _has_series = (_ser is not None and hasattr(_ser, "__len__")
                           and len(_ser) >= 10)
            # complete 直接 return（最佳結果）
            if not _res.get("error") and _st == "complete":
                return _res, _pt
            _attempts.append((_res, _pt, _has_series, _st))
        # 沒有 complete → 偏好 has_series 的 partial（境外基金真實 case）
        _with_series = [t for t in _attempts if t[2]]
        if _with_series:
            return _with_series[0][0], _with_series[0][1]
        # 全部都 partial 但都沒 series → 回第一個 partial（至少有 metadata）
        _partials = [t for t in _attempts if t[3] == "partial"]
        if _partials:
            return _partials[0][0], _partials[0][1]
        # 全 failed → 回最後一個（境外結果）
        return _attempts[-1][0], _attempts[-1][1]

    if do_load and mj_url_input.strip():
        # v18.60: 載入前清 fetch 快取，確保用最新 calc_metrics 邏輯
        try:
            from fund_fetcher import clear_all_caches as _cac_t2
            import repositories.macro_repository  # noqa: F401
            _cac_t2()
        except Exception:
            pass   # noqa: smoke-allow-pass
        with st.spinner("📡 自動偵測基金類型並抓取資料..."):
            fd_raw, _t2_page_type = _auto_fetch_moneydj(mj_url_input.strip())
            fd_raw  = normalize_result_state(fd_raw)
            _status = fd_raw.get("status", classify_fetch_status(fd_raw))
            st.session_state.fund_data = {
                "full_key":    fd_raw.get("full_key",""),
                "fund_name":   fd_raw.get("fund_name",""),
                "portal":      "www",
                "series":      fd_raw.get("series"),
                "dividends":   fd_raw.get("dividends",[]),
                "metrics":     fd_raw.get("metrics",{}),
                "error":       fd_raw.get("error"),
                "warning":     fd_raw.get("warning"),
                "status":      _status,
                "moneydj_raw": fd_raw,
                "page_type":   _t2_page_type,
                # v18.18: 補上 metadata 讓 Tab5 「資料診斷」footer 顯示完整
                "is_core":     _is_core_fund(fd_raw.get("fund_name","") or fd_raw.get("full_key","")),
                "currency":    fd_raw.get("currency","") or fd_raw.get("metrics",{}).get("currency",""),
            }
            _update_data_registry()
            if fd_raw.get("error"):
                st.error(f"❌ {fd_raw['error']}")
            elif _status == "partial":
                _p_fn = fd_raw.get("fund_name","") or fd_raw.get("full_key","")
                st.warning(f"🟡 **{_p_fn}** — 部分資料（歷史淨值未取得，詳情見下方）")
            elif _status == "complete":
                _c_fn = fd_raw.get("fund_name","") or fd_raw.get("full_key","")
                _c_n  = len(fd_raw.get("series")) if fd_raw.get("series") is not None else 0
                st.success(f"✅ **{_c_fn}** ｜ 淨值 {_c_n} 筆 資料已載入")

    # ── 關鍵字搜尋（折疊）──
    with st.expander("🔍 關鍵字搜尋境外基金（TDCC / FundClear）", expanded=False):
        c_kw, c_btn = st.columns([4,1])
        with c_kw:
            keyword = st.text_input("基金關鍵字", placeholder="安聯、收益成長、摩根、聯博...",
                label_visibility="collapsed", key="fund_keyword")
        with c_btn:
            do_search = st.button("🔍 搜尋", type="primary", use_container_width=True, key="btn_search")
        if do_search and keyword.strip():
            with st.spinner(f"搜尋「{keyword}」中..."):
                results = tdcc_search_fund(keyword.strip())
                st.session_state.tdcc_results = results
                if not results:
                    st.warning("⚠️ 查無結果，請直接使用上方 MoneyDJ 網址輸入")
                else:
                    st.success(f"✅ 找到 {len(results)} 檔基金")
        results = st.session_state.get("tdcc_results",[])
        if results:
            options = {f"{r.get('基金名稱','')} | {r.get('基金代碼','')}": r for r in results}
            sel = st.selectbox(f"選擇基金（{len(results)} 筆）", list(options.keys()), key="tdcc_select")
            fc  = options[sel].get("基金代碼","")
            st.info(f"💡 代碼：**{fc}** → 在上方輸入框貼入代碼即可分析")

    # ── 分析結果 ──
    fd = st.session_state.fund_data
    if fd:
        _status_fd = fd.get("status","")
        # v18.118 issue 1: partial 狀態（歷史 series 未取得）禁止顯示部分舊資料
        # 之前 partial 仍渲染 nav / metrics / chart → 使用者誤以為「已下載」
        # 修正：partial 比照 failed 處理，要求重新嘗試，不顯示誤導性的單點 metadata
        if _status_fd == "failed":
            st.error(f"❌ 資料抓取失敗：{fd.get('error','未知錯誤')}")
        elif _status_fd == "partial":
            _p_fn = fd.get("fund_name", "") or fd.get("full_key", "")
            st.error(
                f"❌ **{_p_fn}** — 資料不完整（歷史淨值序列未取得）\n\n"
                f"基金核心分析需完整 NAV 歷史，缺序列無法計算 Sharpe / σ 買賣點 / 配息率等指標。\n\n"
                f"**建議操作**：\n"
                f"- 點擊「🔄 重新下載」按鈕重試（網路波動常見）\n"
                f"- 確認 MoneyDJ 代碼正確（境外基金需用 wb01 頁面代碼）\n"
                f"- 若連續失敗，可至「📋 保單管理」改抓 FundClear 備援"
            )
            # v18.119/120 issue 4: 抓取診斷 — 列出哪些欄位有 / 沒有 + NAS Proxy 狀態
            with st.expander("🔍 抓取診斷細節（哪個源失敗 + NAS Proxy 狀態）", expanded=True):
                _mj_raw    = fd.get("moneydj_raw", {}) or {}
                _series    = fd.get("series")
                _series_n  = (len(_series) if _series is not None
                              and hasattr(_series, "__len__") else 0)
                _has_metrics = bool(fd.get("metrics"))
                _has_risk    = bool(_mj_raw.get("risk_metrics"))
                _has_div     = bool(fd.get("dividends"))
                _raw_warn = fd.get("warning") or _mj_raw.get("warning", "") or "—"
                _raw_err  = fd.get("error")   or _mj_raw.get("error",  "") or "—"
                # v18.120: NAS Proxy 狀態檢測（issue 4 user 切到 NAS 後仍失敗）
                try:
                    from infra.proxy import get_proxy_config as _gpc
                    _pxy_cfg = _gpc()
                    if _pxy_cfg:
                        _pxy_url = _pxy_cfg.get("https", "—")
                        # 隱藏密碼
                        import re as _re_pxy
                        _pxy_safe = _re_pxy.sub(
                            r"//[^:]+:[^@]+@", "//****:****@", _pxy_url)
                        _pxy_line = f"NAS Proxy: ✅ {_pxy_safe}"
                    else:
                        _pxy_line = "NAS Proxy: ❌ 未設定（走直連，Cloud IP 可能被封）"
                except Exception as _e_pxy:
                    _pxy_line = f"NAS Proxy: ⚠️ 讀取失敗 ({type(_e_pxy).__name__})"
                st.code(
                    f"{_pxy_line}\n"
                    f"────────────────────────\n"
                    f"狀態: {_status_fd}\n"
                    f"基金名稱: {_p_fn or '（未抓到）'}\n"
                    f"NAV 序列: {_series_n} 筆 "
                    f"{'✅' if _series_n >= 10 else '❌ (需 ≥10)'}\n"
                    f"指標 (calc_metrics): {'✅' if _has_metrics else '❌'}\n"
                    f"風險指標 (wb07):     {'✅' if _has_risk    else '❌'}\n"
                    f"配息歷史 (wb05):     {'✅' if _has_div     else '❌'}\n"
                    f"最新淨值: {_mj_raw.get('nav_latest', '—')}\n"
                    f"基金類別: {_mj_raw.get('fund_type',  '—')}\n"
                    f"page_type: {fd.get('page_type', '—')}\n"
                    f"────────────────────────\n"
                    f"warning: {_raw_warn}\n"
                    f"error:   {_raw_err}",
                    language=None,
                )
                st.caption(
                    "📌 **判讀**：\n"
                    "- Proxy ✅ + page_type yp010000 + NAV=0 → 路由錯（境外基金抓到境內頁）\n"
                    "- Proxy ✅ + page_type yp010001 + NAV=0 → 源真壞或 NAS 不通該基金\n"
                    "- Proxy ❌ → 至 Streamlit Cloud secrets 加 PROXY_URL = \"http://user:pwd@host:3128\""
                )
        else:
            s    = fd.get("series"); m = fd.get("metrics",{}); divs = fd.get("dividends",[])
            name = fd.get("fund_name",""); fk = fd.get("full_key","")
            mj_raw = fd.get("moneydj_raw",{}) or {}

            if s is None or (hasattr(s,"empty") and s.empty) or not m:
                # ── 部分資料視圖（series 缺失時仍顯示可用資訊）────────
                _p_name  = name or fk
                _p_nav   = mj_raw.get("nav_latest")
                _p_risk  = (mj_raw.get("risk_metrics") or {})
                _p_perf  = (mj_raw.get("perf") or {})
                _p_err   = fd.get("error") or fd.get("warning") or ""
                _p_cat   = mj_raw.get("category","")
                _p_fee   = mj_raw.get("mgmt_fee","")

                st.markdown(
                    f"<div style='background:#1a1500;border:1px solid #ff9800;"
                    f"border-radius:10px;padding:14px 18px;margin:8px 0'>"
                    f"<div style='color:#ff9800;font-weight:700;font-size:13px;margin-bottom:8px'>"
                    f"🟡 部分資料（歷史淨值序列未取得，下方顯示已有資訊）</div>"
                    + (f"<div style='color:#ccc;font-size:11px;margin-bottom:6px'>{_p_err}</div>"
                       if _p_err else "")
                    + (f"<div style='color:#888;font-size:11px;border-top:1px solid #2a1f00;padding-top:8px;margin-top:4px'>"
                    f"💡 系統已自動嘗試境內/境外雙路由。若仍失敗，可直接貼入完整 MoneyDJ 網址：<br>"
                    f"境內：<code>yp010000.djhtm?a={fk}</code>　"
                    f"境外：<code>yp010001.djhtm?a={fk}</code></div>"
                    f"</div>"),
                    unsafe_allow_html=True)

                # 顯示已取得的基本資料
                _pc1, _pc2, _pc3 = st.columns(3)
                with _pc1:
                    if _p_nav is not None:
                        st.metric("最新淨值", f"{float(_p_nav):.4f}")
                    else:
                        st.metric("最新淨值", "N/A")
                with _pc2:
                    st.metric("基金類別", _p_cat[:12] or "N/A")
                with _pc3:
                    st.metric("最高經理費", _p_fee or "N/A")

                # 若有風險指標，仍顯示
                if _p_risk.get("risk_table"):
                    st.markdown("#### 📊 風險指標（已取得）")
                    _rt = _p_risk["risk_table"]
                    _r1y = _rt.get("一年", {})
                    for lbl, val in [("標準差",_r1y.get("標準差","—")),
                                     ("Sharpe", _r1y.get("Sharpe","—")),
                                     ("Alpha",  _r1y.get("Alpha","—")),
                                     ("Beta",   _r1y.get("Beta","—"))]:
                        st.markdown(
                            f"<div style='display:flex;justify-content:space-between;padding:5px 10px;"
                            f"background:#161b22;border-radius:6px;margin:3px 0'>"
                            f"<span style='color:#888;font-size:12px'>{lbl}(1Y)</span>"
                            f"<span style='font-weight:700'>{val}</span></div>",
                            unsafe_allow_html=True)

                # 若有績效數據，顯示
                if _p_perf:
                    st.markdown("#### 📈 績效數據（已取得）")
                    _perf_cols = st.columns(len(_p_perf))
                    for _pi, (_pk, _pv) in enumerate(list(_p_perf.items())[:4]):
                        _perf_cols[_pi].metric(f"報酬率({_pk})", f"{_pv:.2f}%" if isinstance(_pv,(int,float)) else str(_pv))
            else:
                st.success(f"✅ **{name or fk}** ｜ 淨值 {len(s)} 筆 ‧ 配息 {len(divs)} 筆")

                # MK 訊號卡片
                phase_info_s = st.session_state.phase_info if st.session_state.macro_done else None
                if phase_info_s:
                    sig = mk_fund_signal(fd, phase_info_s["phase"], phase_info_s["score"])
                    _aa = sig.get("auto_alloc")
                    if _aa:
                        _aa_stk, _aa_bnd, _aa_lbl, _aa_c = _aa
                        st.markdown(f"<div style='background:#0d1b2a;border:1px solid {_aa_c};border-radius:8px;padding:8px 14px;margin:4px 0 8px 0;display:flex;align-items:center;gap:16px'>"
                            f"<span>📊</span><div><div style='color:{_aa_c};font-weight:700;font-size:12px'>總經自動配比建議：{_aa_lbl}</div>"
                            f"<div style='color:#ccc;font-size:12px'>股 {_aa_stk}% ／ 債 {_aa_bnd}%</div></div></div>", unsafe_allow_html=True)
                    _sig_style = sig["sig_style"]
                    st.markdown(f"<div style='background:#161b22;border:1px solid #30363d;border-radius:10px;padding:14px 18px;margin:8px 0;display:flex;align-items:center;gap:16px;flex-wrap:wrap'>"
                        f"<div><div style='color:#888;font-size:11px'>資產屬性</div><div style='font-size:14px;font-weight:700;color:#58a6ff'>{sig['asset_class']}</div></div>"
                        f"<div><div style='color:#888;font-size:11px'>策略3 操作訊號</div><span style='{_sig_style};padding:4px 12px;border-radius:20px;font-size:13px;font-weight:700;display:inline-block'>{sig['label']}</span></div>"
                        f"<div style='flex:1'><div style='color:#888;font-size:11px'>景氣位階（{phase_info_s['phase']} {phase_info_s['score']}/10）</div>"
                        f"<div style='font-size:12px;color:#c9d1d9'>{sig['reason']}</div></div></div>", unsafe_allow_html=True)

                # 淨值走勢圖（Bollinger Bands + 配息標記 v2.0 + V5 三合一）
                # V5: 微觀防護盾掃描後才出現右側三率動能柱（未掃描時主圖佔滿全寬）
                _shield_for_render = st.session_state.get(f"shield_{fk}")
                if _shield_for_render:
                    _v5_chart_col, _v5_mini_col = st.columns([3, 1])
                else:
                    _v5_chart_col = st.container()
                    _v5_mini_col = None
                with _v5_chart_col:
                    st.markdown("### 📈 三合一趨勢診斷圖")
                df_show = s.reset_index(); df_show.columns = ["date","nav"]
                fig_n = go.Figure()

                # ── Bollinger Bands（MA20 ±2σ，半透明填色）──────────────
                _bb_period = min(20, len(s))
                _bb_ma  = s.rolling(_bb_period).mean()
                _bb_std = s.rolling(_bb_period).std()
                _bb_up  = (_bb_ma + 2 * _bb_std).dropna()
                _bb_dn  = (_bb_ma - 2 * _bb_std).dropna()
                # 上軌（填色基準，先畫，不顯示圖例線條）
                fig_n.add_trace(go.Scatter(
                    x=_bb_up.index, y=_bb_up.values, name="BB上軌",
                    line=dict(color="rgba(33,150,243,0.25)", width=1),
                    showlegend=False))
                # 下軌 + fill to 上軌（半透明藍色通道）
                fig_n.add_trace(go.Scatter(
                    x=_bb_dn.index, y=_bb_dn.values, name="布林通道(±2σ)",
                    fill="tonexty",
                    fillcolor="rgba(33,150,243,0.08)",
                    line=dict(color="rgba(33,150,243,0.25)", width=1)))
                # MA20 中軌
                fig_n.add_trace(go.Scatter(
                    x=_bb_ma.dropna().index, y=_bb_ma.dropna().values,
                    name="MA20", line=dict(color="#ff9800", width=1, dash="dot")))
                # MA60
                _ma60 = s.rolling(60).mean()
                fig_n.add_trace(go.Scatter(
                    x=_ma60.dropna().index, y=_ma60.dropna().values,
                    name="MA60", line=dict(color="#9c27b0", width=1, dash="dot")))
                # 淨值主線（純線；不再 fill 到 0 以免 y 軸被自動拉到 0 壓扁走勢）
                fig_n.add_trace(go.Scatter(
                    x=df_show["date"], y=df_show["nav"],
                    name="淨值", mode="lines",
                    line=dict(color="#2196f3", width=2)))

                # ── 配息標記 💰（除息日垂直虛線 + marker）───────────────
                _chart_divs = mj_raw.get("dividends") or []
                _chart_divs = _chart_divs if isinstance(_chart_divs, list) else []
                _div_dates, _div_navs, _div_texts = [], [], []
                for _cd in _chart_divs:
                    try:
                        _cd_date = pd.Timestamp(_cd.get("date",""))
                        if _cd_date in s.index:
                            _cd_nav = float(s.loc[_cd_date])
                        else:
                            # 找最近交易日
                            _near = s.index[s.index.get_indexer([_cd_date], method="nearest")[0]]
                            _cd_nav = float(s.loc[_near])
                            _cd_date = _near
                        _cd_amt = _cd.get("amount") or _cd.get("dividend") or ""
                        _div_dates.append(_cd_date)
                        _div_navs.append(_cd_nav)
                        _div_texts.append(f"💰 配息 {_cd_amt}" if _cd_amt else "💰 配息")
                    except Exception:
                        continue
                if _div_dates:
                    fig_n.add_trace(go.Scatter(
                        x=_div_dates, y=_div_navs,
                        mode="markers+text",
                        name="配息日",
                        marker=dict(symbol="triangle-up", size=10, color="#ffd600"),
                        text=_div_texts,
                        textposition="top center",
                        textfont=dict(size=9, color="#ffd600"),
                        hovertemplate="%{text}<br>淨值：%{y:.4f}<extra></extra>"))

                # ── MK v3.0 買賣水平線（3 買 + 3 賣）────────────────────
                for bv, bl, bc in [
                    (m.get("buy1"), "買1 小跌(年高-1σ)", "#69f0ae"),
                    (m.get("buy2"), "買2 急跌(年高-2σ)", "#00c853"),
                    (m.get("buy3"), "買3 大跌(年高-3σ)", "#9c27b0"),
                ]:
                    if bv:
                        fig_n.add_hline(y=bv, line_color=bc, line_dash="dot",
                                        annotation_text=bl, annotation_font_color=bc,
                                        annotation_position="bottom right")
                for sv, sl, sc in [
                    (m.get("sell1"), "賣1 小漲(年低+1σ)", "#ffa726"),
                    (m.get("sell2"), "賣2 急漲(年低+2σ)", "#ff7043"),
                    (m.get("sell3"), "賣3 大漲(年低+3σ)", "#f44336"),
                ]:
                    if sv:
                        fig_n.add_hline(y=sv, line_color=sc, line_dash="dash",
                                        annotation_text=sl, annotation_font_color=sc,
                                        annotation_position="top right")

                # ── y 軸範圍：取 NAV / BB / 買賣線整體 min-max，留 5% 邊界 ──
                _y_vals = [float(v) for v in df_show["nav"].dropna().values]
                if len(_bb_up) > 0: _y_vals += [float(v) for v in _bb_up.values if pd.notna(v)]
                if len(_bb_dn) > 0: _y_vals += [float(v) for v in _bb_dn.values if pd.notna(v)]
                for _hv in (m.get("buy1"), m.get("buy2"), m.get("buy3"),
                            m.get("sell1"), m.get("sell2"), m.get("sell3")):
                    if _hv: _y_vals.append(float(_hv))
                if _y_vals:
                    _y_min, _y_max = min(_y_vals), max(_y_vals)
                    _y_pad = max((_y_max - _y_min) * 0.05, _y_max * 0.005, 1e-4)
                    _y_range = [_y_min - _y_pad, _y_max + _y_pad]
                else:
                    _y_range = None

                fig_n.update_layout(
                    paper_bgcolor="#0e1117", plot_bgcolor="#161b22",
                    font_color="#e6edf3", height=420,
                    margin=dict(t=15, b=30, l=40, r=20),
                    legend=dict(orientation="h", font_size=10, y=1.02),
                    hovermode="x unified", yaxis_title="淨值")
                if _y_range:
                    fig_n.update_yaxes(range=_y_range)
                # 左側主圖放入 column 中
                with _v5_chart_col:
                    st.plotly_chart(fig_n, use_container_width=True)

                # ── 右側側邊：持倉三率動能柱（僅在掃描後顯示）─────────────
                if _v5_mini_col is not None:
                    with _v5_mini_col:
                        st.markdown("**📊 三率動能**")
                        _mini_shield = _shield_for_render
                        _m_gd = sum(r.get("gross_margin_diff", 0) or 0 for r in _mini_shield)
                        _m_od = sum(r.get("op_margin_diff",    0) or 0 for r in _mini_shield)
                        _m_nd = sum(r.get("net_margin_diff",   0) or 0 for r in _mini_shield)
                        _n    = max(len(_mini_shield), 1)
                        _m_gd /= _n; _m_od /= _n; _m_nd /= _n
                        _mini_colors = [
                            "#00c853" if v > 0.5 else ("#f44336" if v < -0.5 else "#ff9800")
                            for v in [_m_gd, _m_od, _m_nd]]
                        fig_mini = go.Figure(go.Bar(
                            x=["毛利率", "營益率", "淨利率"],
                            y=[_m_gd, _m_od, _m_nd],
                            marker_color=_mini_colors,
                            text=[f"{v:+.1f}%" for v in [_m_gd, _m_od, _m_nd]],
                            textposition="outside",
                            textfont=dict(size=10)))
                        fig_mini.add_hline(y=0, line_color="#555", line_width=1)
                        fig_mini.update_layout(
                            paper_bgcolor="#0e1117", plot_bgcolor="#161b22",
                            font_color="#e6edf3", height=240,
                            margin=dict(t=10, b=10, l=5, r=5),
                            showlegend=False,
                            yaxis=dict(gridcolor="#1e2a3a", zeroline=False))
                        st.plotly_chart(fig_mini, use_container_width=True)
                        _tot_mom = _m_gd + _m_od + _m_nd
                        if _tot_mom > 2:
                            st.markdown("🟢 **三率雙升**<br>基本面防護", unsafe_allow_html=True)
                        elif _tot_mom < -2:
                            st.markdown("🔴 **三率衰退**<br>虛漲陷阱", unsafe_allow_html=True)
                        else:
                            st.markdown("🟡 **三率持平**<br>搭配布林研判", unsafe_allow_html=True)

                # ── MK 標準差買賣點分析 v3.0（3 買 + 3 賣 + 接近度）──
                _m_buy1 = m.get("buy1"); _m_buy2 = m.get("buy2"); _m_buy3 = m.get("buy3")
                _m_sell1 = m.get("sell1"); _m_sell2 = m.get("sell2"); _m_sell3 = m.get("sell3")
                _m_pl = m.get("pos_label",""); _m_pc = m.get("pos_color","#888")
                _m_mode = m.get("buy_mode",""); _m_std_src = m.get("std_source","nav")
                _m_nav_v = float(m.get("nav") or 0)
                _NEAR = float(m.get("near_threshold_pct") or 2.0)
                def _proximity_chip(nav_v, target, is_buy):
                    """買: nav≤target 觸發；賣: nav≥target 觸發；±NEAR% 為接近區"""
                    if (not target) or nav_v <= 0:
                        return ("—", "#666", "")
                    delta = (nav_v - target) / target * 100  # 正=高於 target
                    if is_buy:
                        if delta <= 0:           return ("🟢 觸發", "#00e676", f"{abs(delta):.2f}% 已破")
                        elif delta <= _NEAR:     return ("⚠️ 接近", "#ffa726", f"還差 {delta:.2f}%")
                        else:                    return ("▲ 距離", "#666",    f"還差 {delta:.2f}%")
                    else:
                        if delta >= 0:           return ("🔔 觸發", "#f44336", f"{delta:.2f}% 已過")
                        elif delta >= -_NEAR:    return ("⚠️ 接近", "#ffa726", f"還差 {-delta:.2f}%")
                        else:                    return ("▼ 距離", "#666",    f"還差 {-delta:.2f}%")
                if _m_buy1:
                    _rows = ""
                    for _bv, _bl, _bc, _is_buy in [
                        (_m_buy3,  "💧 大跌大買 (50%) 年高-3σ", "#9c27b0", True),
                        (_m_buy2,  "💧 急跌穩買 (30%) 年高-2σ", "#00c853", True),
                        (_m_buy1,  "💧 小跌小買 (20%) 年高-1σ", "#69f0ae", True),
                        (_m_sell1, "💰 小漲停利 (20%) 年低+1σ", "#ffa726", False),
                        (_m_sell2, "💰 急漲停利 (30%) 年低+2σ", "#ff7043", False),
                        (_m_sell3, "💰 大漲停利 (50%) 年低+3σ", "#f44336", False),
                    ]:
                        if not _bv: continue
                        _chip_lbl, _chip_color, _chip_dist = _proximity_chip(_m_nav_v, _bv, _is_buy)
                        _rows += (f"<div style='display:flex;align-items:center;justify-content:space-between;"
                                  f"padding:5px 12px;background:#0d1117;border-radius:6px;margin:3px 0;gap:8px'>"
                                  f"<span style='color:{_bc};font-size:12px;flex:1'>{_bl}</span>"
                                  f"<span style='font-weight:700;font-size:13px;min-width:64px;text-align:right'>{_bv:.4f}</span>"
                                  f"<span style='color:{_chip_color};font-size:11px;min-width:74px;text-align:right;font-weight:600'>{_chip_lbl}</span>"
                                  f"<span style='color:#666;font-size:10px;min-width:96px;text-align:right'>{_chip_dist}</span>"
                                  f"</div>")
                    st.markdown(
                        f"<div style='background:#161b22;border:1px solid #30363d;border-radius:10px;padding:12px 16px;margin:10px 0'>"
                        f"<div style='display:flex;align-items:center;justify-content:space-between;margin-bottom:8px'>"
                        f"<span style='color:#888;font-size:11px'>📍 策略3 標準差買賣點 v3.0（{_m_mode} ｜ σ 來源：{_m_std_src}）</span>"
                        f"<span style='background:#111;color:{_m_pc};border:1px solid {_m_pc};padding:2px 10px;"
                        f"border-radius:12px;font-size:12px;font-weight:700'>{_m_pl}</span>"
                        f"</div>"
                        + _rows
                        + f"<div style='color:#666;font-size:10px;margin-top:6px'>現值 {_m_nav_v:.4f} ｜ 接近閾值 ±{_NEAR:.1f}%</div>"
                        + "</div>", unsafe_allow_html=True)

                # ── V3-3: -2σ 超跌機會卡（布林下軌突破警報）────────────
                _boll_latest_low = float(_bb_dn.iloc[-1]) if len(_bb_dn) > 0 else None
                if _boll_latest_low is not None and _m_nav_v > 0 and _m_nav_v <= _boll_latest_low:
                    st.markdown(
                        f"<div style='background:linear-gradient(135deg,#061a06,#0d2a0d);"
                        f"border:2px solid #00e676;border-radius:12px;padding:14px 18px;margin:10px 0'>"
                        f"<div style='color:#00e676;font-size:14px;font-weight:700;margin-bottom:8px'>"
                        f"⚡ -2σ 超跌機會卡 — 布林下軌突破！</div>"
                        f"<div style='display:flex;gap:24px;flex-wrap:wrap;margin-bottom:8px'>"
                        f"<div><div style='color:#888;font-size:10px'>現值 NAV</div>"
                        f"<div style='color:#fff;font-weight:700;font-size:16px'>{_m_nav_v:.4f}</div></div>"
                        f"<div><div style='color:#888;font-size:10px'>布林下軌(-2σ)</div>"
                        f"<div style='color:#00e676;font-weight:700;font-size:16px'>{_boll_latest_low:.4f}</div></div>"
                        f"<div><div style='color:#888;font-size:10px'>跌破幅度</div>"
                        f"<div style='color:#69f0ae;font-weight:700;font-size:16px'>"
                        f"{(_boll_latest_low - _m_nav_v) / _boll_latest_low * 100:.2f}%</div></div>"
                        f"</div>"
                        f"<div style='color:#aaa;font-size:11px;border-top:1px solid #1a3a1a;padding-top:8px'>"
                        f"策略2：布林下軌突破 = 短期非理性超跌，適合左側交易分批承接。"
                        f"建議：小量試單（部位 ≤20%），並設停損於下軌下方 3%。</div>"
                        f"</div>", unsafe_allow_html=True)

                # ── T5: HWM σ 絕對位階卡 ─────────────────────────────────
                if s is not None and len(s) >= 30:
                    try:
                        from services.precision_service import calc_hwm_sigma_levels as _hwm_fn
                        _hwm = _hwm_fn(s, lookback=252)
                        if "error" not in _hwm:
                            _hc = _hwm["color"]
                            _hl = _hwm["label"]
                            _nav_h = _hwm["current_nav"]
                            _hwm_v = _hwm["hwm"]
                            _sig   = _hwm["sigma_abs"]
                            _sr    = _hwm["sigma_rank"]
                            _dist  = _hwm["dist_to_hwm_pct"]
                            _l1, _l2, _l3 = _hwm["level_1s"], _hwm["level_2s"], _hwm["level_3s"]
                            st.markdown(
                                f"<div style='background:#0d1b2a;border:2px solid {_hc};"
                                f"border-radius:12px;padding:14px 18px;margin:10px 0'>"
                                f"<div style='color:{_hc};font-size:13px;font-weight:800;margin-bottom:10px'>"
                                f"📐 HWM σ 絕對位階 — {_hl}</div>"
                                f"<div style='display:flex;gap:20px;flex-wrap:wrap;margin-bottom:10px'>"
                                f"<div><div style='color:#888;font-size:10px'>歷史最高(HWM)</div>"
                                f"<div style='color:#fff;font-weight:700;font-size:16px'>{_hwm_v:.4f}</div></div>"
                                f"<div><div style='color:#888;font-size:10px'>現值 NAV</div>"
                                f"<div style='color:{_hc};font-weight:700;font-size:16px'>{_nav_h:.4f}</div></div>"
                                f"<div><div style='color:#888;font-size:10px'>距 HWM</div>"
                                f"<div style='color:{_hc};font-weight:700;font-size:16px'>{_dist:+.2f}%</div></div>"
                                f"<div><div style='color:#888;font-size:10px'>σ 位階</div>"
                                f"<div style='color:{_hc};font-weight:700;font-size:16px'>{_sr:+.2f}σ</div></div>"
                                f"</div>"
                                f"<div style='display:flex;gap:12px;flex-wrap:wrap;font-size:11px'>"
                                f"<span style='color:#69f0ae'>HWM-1σ: {_l1:.4f}</span>"
                                f"<span style='color:#ff9800'>HWM-2σ: {_l2:.4f}</span>"
                                f"<span style='color:#f44336'>HWM-3σ: {_l3:.4f}</span>"
                                f"</div>"
                                f"<div style='color:#666;font-size:10px;margin-top:6px'>"
                                f"σ = HWM × 年化日報酬標準差（{len(s)} 筆淨值計算）</div>"
                                f"</div>", unsafe_allow_html=True)
                    except Exception:
                        pass  # noqa: smoke-allow-pass

                # ── v18.47: 📊 基金健康總覽（4 維度評分 + Overall Grade + 白話結論）──
                try:
                    # 共用 fallback chain：1Y 含息報酬
                    _g_tr1y = m.get("ret_1y")
                    if _g_tr1y is None:
                        _g_tr1y = (mj_raw.get("perf") or {}).get("1Y")
                    # v18.48 改成日期 index 找最接近 1Y 前的點（救週/月頻 NAV）
                    if _g_tr1y is None and s is not None and hasattr(s, "dropna"):
                        try:
                            import pandas as _pd_g
                            _ss_g = s.dropna()
                            if len(_ss_g) >= 3:
                                _now_t = _ss_g.index[-1]
                                _target_t = _now_t - _pd_g.Timedelta(days=365)
                                _idx_old = _ss_g.index.get_indexer([_target_t], method="nearest")[0]
                                if 0 <= _idx_old < len(_ss_g) - 1:
                                    _days_actual = (_now_t - _ss_g.index[_idx_old]).days
                                    if _days_actual >= 90:
                                        _vn_g = float(_ss_g.iloc[-1])
                                        _vo_g = float(_ss_g.iloc[_idx_old])
                                        if _vo_g > 0:
                                            _raw_g = (_vn_g / _vo_g - 1.0) * 100.0
                                            _g_tr1y = _raw_g * (365.0 / _days_actual)
                        except Exception:
                            pass  # noqa: smoke-allow-pass — NAV 1Y 估算失敗不影響其他維度
                    try: _g_tr1y = float(_g_tr1y) if _g_tr1y is not None else None
                    except (TypeError, ValueError): _g_tr1y = None

                    _g_dy = (mj_raw.get("moneydj_div_yield")
                             or m.get("annual_div_rate"))
                    try: _g_dy = float(_g_dy) if _g_dy is not None else None
                    except (TypeError, ValueError): _g_dy = None
                    # v18.49 第三層 fallback：從 divs[] 歷史推算（過去 12 個月配息合計 / 現價）
                    if (_g_dy is None or _g_dy <= 0) and divs:
                        try:
                            import datetime as _dt_dy
                            _cutoff = _dt_dy.datetime.now() - _dt_dy.timedelta(days=365)
                            _sum_amt = 0.0
                            for _dd in divs:
                                _dt_str = (_dd.get("date") or "").replace("/", "-")
                                try:
                                    _dt_p = _dt_dy.datetime.strptime(_dt_str[:10], "%Y-%m-%d")
                                except (ValueError, TypeError):
                                    continue
                                if _dt_p >= _cutoff:
                                    _sum_amt += float(_dd.get("amount", 0) or 0)
                            _nav_now = m.get("nav") or mj_raw.get("nav_latest")
                            try: _nav_now = float(_nav_now) if _nav_now is not None else None
                            except (TypeError, ValueError): _nav_now = None
                            if _sum_amt > 0 and _nav_now and _nav_now > 0:
                                _g_dy = (_sum_amt / _nav_now) * 100.0
                        except Exception:
                            pass  # noqa: smoke-allow-pass — divs 歷史推算失敗不影響其他維度

                    _g_sharpe = m.get("sharpe")
                    if _g_sharpe is None:
                        _g_sharpe = ((rm.get("risk_table") or {}).get("一年") or {}).get("Sharpe")
                    try: _g_sharpe = float(_g_sharpe) if _g_sharpe is not None else None
                    except (TypeError, ValueError): _g_sharpe = None

                    _g_sigma = m.get("std_1y")
                    if _g_sigma is None:
                        _g_sigma = ((rm.get("risk_table") or {}).get("一年") or {}).get("標準差")
                    try: _g_sigma = float(_g_sigma) if _g_sigma is not None else None
                    except (TypeError, ValueError): _g_sigma = None

                    # v18.48 改成日期窗口（取最後 60 天 NAV）— 救週/月頻 NAV
                    _g_ma_dir = None
                    try:
                        import pandas as _pd_g2
                        if s is not None and hasattr(s, "dropna"):
                            _ss_t = s.dropna()
                            if len(_ss_t) >= 3:
                                _last_t = _ss_t.index[-1]
                                _60d_ago = _last_t - _pd_g2.Timedelta(days=60)
                                _recent = _ss_t[_ss_t.index >= _60d_ago]
                                if len(_recent) >= 2:
                                    _v_start = float(_recent.iloc[0])
                                    _v_end = float(_recent.iloc[-1])
                                    if _v_start > 0:
                                        _g_ma_dir = "up" if _v_end > _v_start else "down"
                    except Exception:
                        pass  # noqa: smoke-allow-pass — 走勢方向估算失敗不影響其他維度

                    # 4 維度評分（0~100）
                    _d1_cov = None  # 配息健康度（Coverage）
                    if _g_dy and _g_dy > 0 and _g_tr1y is not None:
                        _cov_g = _g_tr1y / _g_dy
                        _d1_cov = (95 if _cov_g >= 1.5 else
                                   80 if _cov_g >= 1.2 else
                                   65 if _cov_g >= 1.0 else
                                   40 if _cov_g >= 0.5 else 15)

                    _d2_sh = None  # 風險調整報酬
                    if _g_sharpe is not None:
                        _d2_sh = (95 if _g_sharpe >= 1.5 else
                                  80 if _g_sharpe >= 1.0 else
                                  60 if _g_sharpe >= 0.5 else
                                  40 if _g_sharpe >= 0 else 15)

                    _d3_tr = None  # 走勢健康
                    if _g_ma_dir == "up" and (_g_tr1y or 0) > 0: _d3_tr = 85
                    elif _g_ma_dir == "up": _d3_tr = 70
                    elif _g_ma_dir == "down" and (_g_tr1y or 0) < 0: _d3_tr = 25
                    elif _g_ma_dir == "down": _d3_tr = 45
                    elif _g_tr1y is not None and _g_tr1y > 5: _d3_tr = 70
                    elif _g_tr1y is not None and _g_tr1y < -5: _d3_tr = 25

                    _d4_vol = None  # 低波動性（σ 越低越好）
                    if _g_sigma is not None:
                        _d4_vol = (90 if _g_sigma < 10 else
                                   75 if _g_sigma < 15 else
                                   55 if _g_sigma < 20 else
                                   35 if _g_sigma < 30 else 15)

                    _g_scores = [x for x in [_d1_cov, _d2_sh, _d3_tr, _d4_vol] if x is not None]
                    _g_overall = (sum(_g_scores) / len(_g_scores)) if _g_scores else None
                    if _g_overall is None:
                        _gr, _gr_c, _verd = "—", "#888", "資料不足以評等"
                    elif _g_overall >= 80:
                        _gr, _gr_c, _verd = "A", "#00c853", "✅ 健康優質基金"
                    elif _g_overall >= 65:
                        _gr, _gr_c, _verd = "B", "#69f0ae", "🟢 表現穩健"
                    elif _g_overall >= 50:
                        _gr, _gr_c, _verd = "C", "#ffeb3b", "🟡 中性，持續觀察"
                    elif _g_overall >= 35:
                        _gr, _gr_c, _verd = "D", "#ff9800", "🟠 警示偏弱"
                    else:
                        _gr, _gr_c, _verd = "F", "#f44336", "🔴 多項警示"

                    _eat_call = (" ⚠️ <b style='color:#f44336'>吃本金風險</b>"
                                 if (_d1_cov is not None and _d1_cov < 50) else "")

                    def _g_block(label, score):
                        if score is None:
                            return ("<div><div style='color:#666;font-size:10px'>" + label + "</div>"
                                    "<div style='color:#666;font-size:20px;font-weight:700'>—</div>"
                                    "<div style='color:#555;font-size:9px'>資料不足</div></div>")
                        _c = ("#00c853" if score >= 75 else "#69f0ae" if score >= 60 else
                              "#ffeb3b" if score >= 45 else "#ff9800" if score >= 30 else "#f44336")
                        return (f"<div><div style='color:#888;font-size:10px'>{label}</div>"
                                f"<div style='color:{_c};font-size:20px;font-weight:900'>{score:.0f}</div>"
                                f"<div style='color:#555;font-size:9px'>/ 100</div></div>")

                    st.markdown(
                        f"<div style='background:linear-gradient(135deg,#0d1117,#161b22);"
                        f"border:2px solid {_gr_c};border-radius:12px;padding:14px 18px;margin:8px 0 12px'>"
                        f"<div style='display:flex;align-items:center;gap:16px;margin-bottom:10px;flex-wrap:wrap'>"
                        f"<div style='color:{_gr_c};font-size:46px;font-weight:900;line-height:1'>{_gr}</div>"
                        f"<div style='flex:1;min-width:200px'>"
                        f"<div style='color:#aaa;font-size:11px'>📊 基金健康總覽</div>"
                        f"<div style='color:{_gr_c};font-size:16px;font-weight:800;margin-top:2px'>{_verd}{_eat_call}</div></div>"
                        f"<div style='color:#888;font-size:11px;text-align:right'>"
                        f"綜合評分<br><b style='color:{_gr_c};font-size:18px'>"
                        f"{('—' if _g_overall is None else f'{_g_overall:.0f}')}"
                        f"</b> / 100</div></div>"
                        f"<div style='display:grid;grid-template-columns:repeat(4,1fr);gap:14px;"
                        f"background:#0a0e14;border-radius:8px;padding:10px 14px'>"
                        f"{_g_block('💵 配息健康度', _d1_cov)}"
                        f"{_g_block('📈 風險調整報酬', _d2_sh)}"
                        f"{_g_block('📊 走勢健康', _d3_tr)}"
                        f"{_g_block('🛡️ 低波動性', _d4_vol)}"
                        f"</div></div>", unsafe_allow_html=True)
                except Exception:
                    pass  # noqa: smoke-allow-pass — 評分卡失敗不影響後續資訊

                # ── v18.20: 🔴 吃本金 KPI 紅綠燈（獨立 banner，主 KPI 列旁）──
                # 不依賴 divs[] 是否有資料；只要有 ret_1y + 任一配息率來源即顯示。
                # 無配息資料時顯示 ⬜ 不適用（累積型基金等）。
                try:
                    _kpi_mj_dy = mj_raw.get("moneydj_div_yield")
                    try:
                        _kpi_mj_dy = float(_kpi_mj_dy) if _kpi_mj_dy is not None else None
                    except (TypeError, ValueError):
                        _kpi_mj_dy = None
                    _kpi_adr = (_kpi_mj_dy if (_kpi_mj_dy and _kpi_mj_dy > 0)
                                else float(m.get("annual_div_rate", 0) or 0))
                    # v18.49 第三層 fallback：從 divs 歷史推算（12M 累積配息 / 現價）
                    if (_kpi_adr is None or _kpi_adr <= 0) and divs:
                        try:
                            import datetime as _dt_kdy
                            _cutoff_k = _dt_kdy.datetime.now() - _dt_kdy.timedelta(days=365)
                            _sum_k = 0.0
                            for _dd in divs:
                                _dt_str = (_dd.get("date") or "").replace("/", "-")
                                try:
                                    _dt_p = _dt_kdy.datetime.strptime(_dt_str[:10], "%Y-%m-%d")
                                except (ValueError, TypeError):
                                    continue
                                if _dt_p >= _cutoff_k:
                                    _sum_k += float(_dd.get("amount", 0) or 0)
                            _nav_k = m.get("nav") or mj_raw.get("nav_latest")
                            try: _nav_k = float(_nav_k) if _nav_k is not None else None
                            except (TypeError, ValueError): _nav_k = None
                            if _sum_k > 0 and _nav_k and _nav_k > 0:
                                _kpi_adr = (_sum_k / _nav_k) * 100.0
                        except Exception:
                            pass  # noqa: smoke-allow-pass — divs 歷史推算失敗不影響後續
                    # v18.134: 改用 compute_1y_total_return 共用 helper
                    # 修使用者反饋「Tab2 跟 Tab3 對同一基金顯示不同 1Y 報酬」
                    # 統一順序：perf["1Y"] > ret_1y_total > ret_1y > NAV
                    from ui.helpers.macro_helpers import compute_1y_total_return
                    _kpi_tr1y, _kpi_tr1y_src = compute_1y_total_return({
                        "metrics": m,
                        "moneydj_raw": mj_raw,
                        "series": s,
                        "perf_source": fd.get("perf_source") or mj_raw.get("perf_source"),
                    })

                    if _kpi_adr is None or _kpi_adr <= 0:
                        _kpi_icon, _kpi_color, _kpi_bg = "⬜", "#888", "#161b22"
                        _kpi_title = "吃本金檢查 — ⬜ 不適用"
                        _kpi_msg = "本基金無年化配息率資料（可能為累積型 / 不配息基金）"
                        _kpi_cov_txt = "—"
                    elif _kpi_tr1y is None:
                        _kpi_icon, _kpi_color, _kpi_bg = "⬜", "#888", "#161b22"
                        _kpi_title = "吃本金檢查 — ⬜ 資料不足"
                        _kpi_msg = "缺含息總報酬（1Y），無法計算 Coverage"
                        _kpi_cov_txt = "—"
                    else:
                        _kpi_ds = div_safety_check(
                            total_return=_kpi_tr1y,
                            dividend_yield=_kpi_adr,
                            nav_change=_kpi_tr1y,
                        )
                        _kpi_al = _kpi_ds.get("alert_level", "grey")
                        _kpi_cov = _kpi_ds.get("coverage")
                        _kpi_color = {"red": "#f44336", "yellow": "#ff9800",
                                      "green": "#00c853"}.get(_kpi_al, "#888")
                        _kpi_bg = {"red": "#2a0a0a", "yellow": "#2a1f00",
                                   "green": "#0a1a0a"}.get(_kpi_al, "#161b22")
                        _kpi_icon = {"red": "🔴", "yellow": "🟡",
                                     "green": "🟢"}.get(_kpi_al, "⬜")
                        _kpi_title = f"吃本金檢查 — {_kpi_icon} {_kpi_ds.get('status','')}"
                        _kpi_msg = _kpi_ds.get("message", "")
                        # v18.42 標示 1Y 報酬來源（非 metrics 才提示，避免雜訊）
                        if _kpi_tr1y_src and _kpi_tr1y_src != "metrics":
                            _src_note = {
                                "perf": "MoneyDJ 績效表",
                                "nav_actual": "由 NAV 自算（足 1Y）",
                            }.get(_kpi_tr1y_src, f"由 NAV 線性年化外推（樣本 {_kpi_tr1y_src.replace('nav_annualized_','')}）")
                            _kpi_msg = f"{_kpi_msg}　〔1Y 來源：{_src_note}〕"
                        _kpi_cov_txt = (f"{_kpi_cov:.2f}" if _kpi_cov is not None
                                        else "—")

                    st.markdown(
                        f"<div style='background:{_kpi_bg};border:2px solid {_kpi_color};"
                        f"border-radius:12px;padding:12px 16px;margin:10px 0'>"
                        f"<div style='color:{_kpi_color};font-size:13px;font-weight:800;"
                        f"margin-bottom:8px'>{_kpi_title}</div>"
                        f"<div style='display:flex;gap:24px;flex-wrap:wrap'>"
                        f"<div><div style='color:#888;font-size:10px'>1Y 含息報酬</div>"
                        f"<div style='color:#fff;font-weight:700;font-size:16px'>"
                        f"{(f'{_kpi_tr1y:.2f}%' if _kpi_tr1y is not None else '—')}</div></div>"
                        f"<div><div style='color:#888;font-size:10px'>年化配息率</div>"
                        f"<div style='color:#fff;font-weight:700;font-size:16px'>"
                        f"{(f'{_kpi_adr:.2f}%' if _kpi_adr and _kpi_adr > 0 else '—')}</div></div>"
                        f"<div><div style='color:#888;font-size:10px'>Coverage</div>"
                        f"<div style='color:{_kpi_color};font-weight:700;font-size:16px'>"
                        f"{_kpi_cov_txt}</div></div>"
                        f"</div>"
                        f"<div style='color:#aaa;font-size:11px;margin-top:6px'>{_kpi_msg}</div>"
                        f"</div>", unsafe_allow_html=True)
                except Exception as _kpi_e:  # noqa: BLE001
                    st.caption(f"吃本金 KPI 計算異常：{str(_kpi_e)[:60]}")

                # 關鍵指標 + 配息
                col_a, col_b = st.columns(2)
                with col_a:
                    st.markdown("#### 📊 風險指標")
                    risk_tbl = mj_raw.get("risk_metrics",{}).get("risk_table",{})
                    _r1y = risk_tbl.get("一年",{})
                    _std1 = _r1y.get("標準差","—"); _sh1 = _r1y.get("Sharpe","—")
                    _al1  = _r1y.get("Alpha","—");  _be1 = _r1y.get("Beta","—")
                    for lbl, val in [("波動 σ(1Y)", f"{_std1}%"),("Sharpe(1Y)",str(_sh1)),("Alpha(1Y)",str(_al1)),("Beta(1Y)",str(_be1))]:
                        st.markdown(f"<div style='display:flex;justify-content:space-between;padding:5px 10px;background:#161b22;border-radius:6px;margin:3px 0'><span style='color:#888;font-size:12px'>{lbl}</span><span style='font-weight:700'>{val}</span></div>", unsafe_allow_html=True)
                    # Sharpe 持久性說明（孫慶龍老師框架）
                    try:
                        _sh1_v = float(_sh1)
                        if _sh1_v > 0.5:
                            _sh_txt, _sh_c = "優秀（>0.5）持久創造超額報酬", "#00c853"
                        elif _sh1_v >= 0:
                            _sh_txt, _sh_c = "普通（0~0.5）勉強補償風險", "#ff9800"
                        else:
                            _sh_txt, _sh_c = "差勁（<0）不如持有現金", "#f44336"
                        st.markdown(
                            f"<div style='font-size:10px;color:{_sh_c};padding:3px 10px;"
                            f"background:#0d1117;border-radius:4px;margin:2px 0 6px 0'>"
                            f"策略2框架：{_sh_txt}</div>",
                            unsafe_allow_html=True)
                    except (ValueError, TypeError):
                        pass  # noqa: smoke-allow-pass
                    # 四分位
                    peer = mj_raw.get("risk_metrics",{}).get("peer_compare",{})
                    qr = _quartile_check(peer, risk_tbl)
                    if qr["quartile"]:
                        _qr_color = qr["color"]
                        _qr_adv = (f"<div style='color:#ff9800;font-size:11px;margin-top:4px'>{qr['advice']}</div>"
                                   if qr.get("advice") else "")
                        st.markdown(
                            f"<div style='background:#1a1f2e;border-radius:8px;padding:8px 12px;margin-top:6px'>"
                            f"<span style='color:{_qr_color};font-weight:700'>{qr['label']}</span>"
                            + _qr_adv + "</div>", unsafe_allow_html=True)
                    # v18.192：教學化 — 風險指標白話文（收合、不藏任何數據）
                    render_metric_explainer(["sharpe", "sigma", "alpha", "beta"])

                with col_b:
                    st.markdown("#### 💸 近期配息")
                    if divs and len(divs) >= 1:
                        _mj_dy = mj_raw.get("moneydj_div_yield")
                        try: _mj_dy = float(_mj_dy) if _mj_dy is not None else None
                        except: _mj_dy = None
                        _adr = _mj_dy if (_mj_dy and _mj_dy > 0) else (m.get("annual_div_rate",0) or 0)
                        try: _adr = float(_adr)
                        except: _adr = 0.0
                        st.metric("年化配息率", f"{_adr:.2f}%", help="MoneyDJ wb05 官方值（優先）或自算估值")
                        for d in divs[:6]:
                            _dt = d.get("date",""); _amt = d.get("amount",""); _yld = d.get("yield_pct","")
                            st.markdown(f"<div style='display:flex;justify-content:space-between;padding:4px 10px;background:#161b22;border-radius:6px;margin:2px 0'><span style='color:#888;font-size:11px'>{_dt}</span><span style='font-weight:700'>{_amt}</span><span style='color:#ff9800;font-size:11px'>{_yld}</span></div>", unsafe_allow_html=True)

                        # ── 🚨 吃本金警示（Core Protocol Ch.3.2）──
                        _tr1y = m.get("ret_1y")  # 含息總報酬率近 1 年（%）
                        if _tr1y is not None and _adr > 0:
                            _ds = div_safety_check(
                                total_return=float(_tr1y),
                                dividend_yield=float(_adr),
                                nav_change=float(m.get("ret_1y", 0) or 0),
                            )
                            _al = _ds.get("alert_level","grey")
                            _bg = {"red":"#2a0a0a","yellow":"#2a1f00","green":"#0a1a0a"}.get(_al,"#111")
                            _bc = {"red":"#f44336","yellow":"#ff9800","green":"#00c853"}.get(_al,"#888")
                            st.markdown(
                                f"<div style='background:{_bg};border:1px solid {_bc};border-radius:8px;"
                                f"padding:8px 12px;margin-top:8px'>"
                                f"<div style='color:{_bc};font-weight:700;font-size:12px'>{_ds['status']}</div>"
                                f"<div style='color:#ccc;font-size:11px;margin-top:2px'>{_ds['message']}</div>"
                                + (f"<div style='color:#ff9800;font-size:10px;margin-top:4px'>{_ds['nav_warning']}</div>" if _ds.get("nav_warning") else "")
                                + "</div>", unsafe_allow_html=True)

                        # ── 📖 配息覆蓋率講義卡（MK 郭俊宏《以息養股》）──
                        _tr1y_f = float(_tr1y) if _tr1y is not None else None
                        _adr_f  = float(_adr)  if _adr  else 0.0
                        if _tr1y_f is not None and _adr_f > 0:
                            _cov = _tr1y_f / _adr_f
                            _cov_c = "#00c853" if _cov >= 1.0 else ("#ff9800" if _cov >= 0.8 else "#f44336")
                            _cov_label = (
                                "🟢 安全 — 報酬足以支撐配息，無吃本金疑慮" if _cov >= 1.0 else
                                "🟡 注意 — 輕微侵蝕，需觀察趨勢" if _cov >= 0.8 else
                                "🔴 警示 — 嚴重吃本金，領息賠價差"
                            )
                            st.markdown(
                                f"<div style='background:#0d1117;border:1px dashed #30363d;"
                                f"border-radius:10px;padding:10px 14px;margin-top:8px'>"
                                f"<div style='color:#888;font-size:10px;letter-spacing:1px;margin-bottom:6px'>"
                                f"📖 配息覆蓋率講義 ── 策略3《以息養股》</div>"
                                f"<div style='color:#aaa;font-size:11px;font-style:italic;"
                                f"border-left:2px solid #444;padding-left:8px;margin-bottom:8px'>"
                                f"「高殖利率不等於高報酬，必須確認是否吃本金。」</div>"
                                f"<div style='font-family:monospace;font-size:12px;color:#e6edf3;margin-bottom:6px'>"
                                f"Coverage = TR₁Y ÷ 年化配息率<br>"
                                f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
                                f"= {_tr1y_f:.1f}% ÷ {_adr_f:.2f}%"
                                f" = <span style='color:{_cov_c};font-weight:700;font-size:14px'>{_cov:.2f}</span></div>"
                                f"<div style='color:{_cov_c};font-size:12px;font-weight:600;margin-bottom:6px'>"
                                f"{_cov_label}</div>"
                                f"<div style='color:#555;font-size:10px'>"
                                f"Coverage ≥ 1.0 = 安全 ｜ 0.8–1.0 = 注意 ｜ &lt; 0.8 = 高警示</div>"
                                f"</div>", unsafe_allow_html=True)

                    else:
                        st.info("無配息記錄")

                # ── V3-3: TER 費用率卡（對比同類均值）────────────────────
                _ter_raw = mj_raw.get("mgmt_fee","") or ""
                _ter_cat = mj_raw.get("category","") or ""
                if _ter_raw:
                    try:
                        _ter_val = float(str(_ter_raw).replace("%","").strip())
                    except (ValueError, TypeError):
                        _ter_val = None
                    if _ter_val is not None:
                        # 類別均值對照表（台灣基金市場常見估值）
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
                            _ter_c = "#f44336" if _ter_diff > 0.3 else ("#ff9800" if _ter_diff > 0 else "#00c853")
                            _ter_vs = f"高於均值 +{_ter_diff:.2f}%" if _ter_diff > 0 else f"低於均值 {abs(_ter_diff):.2f}%"
                            _ter_avg_html = (
                                f"<div><div style='color:#888;font-size:10px'>同類均值</div>"
                                f"<div style='color:#888;font-weight:700;font-size:16px'>{_ter_avg:.2f}%</div></div>"
                                f"<div><div style='color:#888;font-size:10px'>費用比較</div>"
                                f"<div style='color:{_ter_c};font-weight:700;font-size:16px'>{_ter_vs}</div></div>"
                            )
                        else:
                            _ter_c, _ter_avg_html = "#888", ""
                        st.markdown(
                            f"<div style='background:#161b22;border:1px solid #30363d;"
                            f"border-radius:10px;padding:10px 16px;margin:8px 0'>"
                            f"<div style='color:#888;font-size:11px;margin-bottom:6px'>💰 TER 費用率分析"
                            + (f" — {_ter_cat[:12]}" if _ter_cat else "") + "</div>"
                            f"<div style='display:flex;gap:24px;flex-wrap:wrap;margin-bottom:6px'>"
                            f"<div><div style='color:#888;font-size:10px'>最高經理費</div>"
                            f"<div style='color:{_ter_c};font-weight:700;font-size:16px'>{_ter_val:.2f}%</div></div>"
                            + _ter_avg_html +
                            f"</div>"
                            f"<div style='color:#555;font-size:10px'>"
                            f"費用率愈低，長期複利效益愈佳（費用每降 1%，20 年後終值多 ~25%）</div>"
                            f"</div>", unsafe_allow_html=True)

                # ── 持股分析（折疊）──
                _holdings = mj_raw.get("holdings", {}) or {}
                _sectors  = _holdings.get("sector_alloc", []) or []
                _tops     = _holdings.get("top_holdings", []) or []
                _hdate    = _holdings.get("data_date", "")
                if _sectors or _tops:
                    with st.expander(f"📂 持股分析" + (f"（{_hdate}）" if _hdate else ""), expanded=False):
                        _hc1, _hc2 = st.columns(2)
                        with _hc1:
                            if _sectors:
                                st.markdown("**🏭 產業配置**")
                                for _sec in _sectors[:10]:
                                    _sn = str(_sec.get("name",""))[:18]
                                    _sp = float(_sec.get("pct", 0) or 0)
                                    st.markdown(
                                        f"<div style='display:flex;align-items:center;gap:8px;margin:3px 0'>"
                                        f"<div style='color:#ccc;font-size:11px;width:95px;flex-shrink:0'>{_sn}</div>"
                                        f"<div style='flex:1;background:#1a1a2a;border-radius:3px;height:10px'>"
                                        f"<div style='background:#2196f3;width:{min(_sp*3,100):.0f}%;height:100%;border-radius:3px'></div></div>"
                                        f"<div style='color:#2196f3;font-size:11px;width:40px;text-align:right'>{_sp:.1f}%</div>"
                                        f"</div>", unsafe_allow_html=True)
                        with _hc2:
                            if _tops:
                                st.markdown("**🏆 前10大持股**")
                                for _i, _top in enumerate(_tops[:10], 1):
                                    _tn_raw = str(_top.get("name",""))
                                    _zh = _zh_holding(_tn_raw)
                                    _tn = _tn_raw[:22]
                                    _zh_html = (f"<span style='color:#ffb74d;font-size:10px;margin-left:6px'>({_zh})</span>"
                                                if _zh else "")
                                    _tp = float(_top.get("pct", 0) or 0)
                                    _ts = str(_top.get("sector",""))[:12]
                                    st.markdown(
                                        f"<div style='display:flex;gap:6px;padding:3px 8px;background:#161b22;border-radius:6px;margin:2px 0'>"
                                        f"<span style='color:#555;font-size:11px;width:16px'>#{_i}</span>"
                                        f"<span style='font-size:11px;flex:1'>{_tn}{_zh_html}</span>"
                                        f"<span style='color:#888;font-size:10px'>{_ts}</span>"
                                        f"<span style='color:#58a6ff;font-weight:700;font-size:11px;width:36px;text-align:right'>{_tp:.1f}%</span>"
                                        f"</div>", unsafe_allow_html=True)

                # ── V4: 微觀防護盾 — 前十大持倉三率檢核 ────────────────
                _shield_tops = (_holdings.get("top_holdings") or []) if _holdings else []
                if _shield_tops:
                    with st.expander("🛡️ 微觀防護盾 — 持倉三率穿透檢核（V4）", expanded=False):
                        st.caption(
                            "掃描前十大持倉個股毛利率 / 營業利益率 / 淨利率 QoQ 變化，"
                            "識別「估值虛漲（PE拉高）vs 實質獲利」的 K 型分化陷阱。"
                        )
                        _shield_key = f"shield_{fk}"
                        if st.button("🔍 執行三率穿透掃描", key=f"btn_shield_{fk}"):
                            from services.precision_service import (
                                PrecisionStrategyEngine as _PSE2,
                                three_ratio_row_html as _tr_html,
                            )
                            _pse2 = _PSE2()
                            _shield_results = []
                            with st.spinner(f"正在掃描 {len(_shield_tops)} 檔持倉財報…"):
                                for _sh_top in _shield_tops[:10]:
                                    _sh_name = _sh_top.get("name", "")
                                    _sh_data = _pse2.fetch_stock_three_ratios(_sh_name)
                                    if _sh_data:
                                        _shield_results.append(_sh_data)
                            st.session_state[_shield_key] = _shield_results

                        _cached_shield = st.session_state.get(_shield_key)
                        if _cached_shield is not None:
                            from services.precision_service import (
                                PrecisionStrategyEngine as _PSE2,
                                three_ratio_row_html as _tr_html,
                            )
                            _pse2 = _PSE2()
                            if _cached_shield:
                                # 彙總判斷
                                _overall_verdict = _pse2.evaluate_fund_three_ratios(_cached_shield)
                                _ov_color = ("#00c853" if "🟢" in _overall_verdict
                                             else "#f44336" if "🔴" in _overall_verdict
                                             else "#ff9800")
                                st.markdown(
                                    f"<div style='background:#0d1117;border:2px solid {_ov_color};"
                                    f"border-radius:10px;padding:10px 16px;margin:8px 0;"
                                    f"font-size:13px;font-weight:700;color:{_ov_color}'>"
                                    f"{_overall_verdict}</div>",
                                    unsafe_allow_html=True)
                                # 逐持倉明細
                                _shield_html = "".join(_tr_html(r) for r in _cached_shield)
                                st.markdown(_shield_html, unsafe_allow_html=True)
                                # 未能解析的持倉列表
                                _resolved_names = {r["stock"] for r in _cached_shield}
                                _failed = [t.get("name","") for t in _shield_tops[:10]
                                           if t.get("name","") not in _resolved_names]
                                if _failed:
                                    st.caption(f"以下持倉 Ticker 無法解析（外幣基金或罕見代碼）：{', '.join(_failed)}")
                            else:
                                st.warning("所有持倉均無法解析 Ticker 或 yfinance 暫無財報，請稍後再試。")

                # AI 基金分析
                st.divider()
                if GEMINI_KEY:
                    # ── 三色燈號阻斷（Core Protocol v2.0 Ch.1）─────────
                    # v18.78：紅燈不再隱藏按鈕，改用 override 讓使用者自選
                    #          原本紅燈時 AI 按鈕完全消失，使用者反饋「按鈕不見了」。
                    _ai_fd_pct, _ = _calc_data_health()
                    _ai_blocked = _ai_fd_pct < 50
                    _ai_override = False
                    if _ai_blocked:
                        st.markdown(
                            "<div style='border-left:4px solid #f44336;background:#1a1f2e;"
                            "border-radius:0 8px 8px 0;padding:10px 14px;font-size:13px;margin-bottom:8px'>"
                            "🔴 <b>紅燈阻斷</b>：總經資料完整率 "
                            f"<b>{_ai_fd_pct}%</b>（&lt;50%）— 建議先切到「🌐 總經」分頁按"
                            "「📡 全量抓取」載入指標後再分析（含景氣位階背景）。</div>",
                            unsafe_allow_html=True)
                        _ai_override = st.checkbox(
                            "略過阻斷 — 僅用基金本身資料分析（無總經背景，準確度降低）",
                            key=f"chk_ai_override_{fk}")
                    elif _ai_fd_pct < 80:
                        st.warning(f"🟡 資料完整率 **{_ai_fd_pct}%**（黃燈），AI 結果參考性降低。")

                    _ai_enabled = (not _ai_blocked) or _ai_override
                    _ai_btn_label = ("🤖 AI 基金分析（無總經背景）" if _ai_blocked and _ai_override
                                     else "🤖 AI 基金分析")
                    _ai_btn_help = ("總經紅燈中，僅用基金本身資料分析" if _ai_blocked and _ai_override
                                    else "先載入總經資料以獲得景氣背景分析" if _ai_blocked
                                    else None)
                    if st.button(_ai_btn_label, key="btn_fund_ai",
                                  disabled=not _ai_enabled, help=_ai_btn_help):
                        with st.spinner("Gemini 分析中（含 RSS 新聞抓取）..."):
                            # v18.135: 補傳真 holdings + 即時抓 RSS 新聞給 AI 第四節交叉分析
                            try:
                                from repositories.news_repository import fetch_market_news as _fetch_n_t2
                                _t2_news = _fetch_n_t2(max_per_feed=3) or []
                            except Exception:
                                _t2_news = []
                            _t2_holdings = (mj_raw.get("holdings") or {})
                            try:
                                _ai = analyze_fund_json(
                                    GEMINI_KEY, name or fk, m,
                                    mj_raw.get("perf", {}), phase_info_s,
                                    risk_metrics=mj_raw.get("risk_metrics"),
                                    holdings=_t2_holdings,
                                    view_mode=st.session_state.get("view_mode", "🔴 L3 老手沙盤"),
                                    news_items=_t2_news,
                                )
                                st.session_state.fund_ai_txt = _ai
                            except Exception as _e:
                                _friendly_error("AI 基金分析失敗", _e,
                                    hint="可能是 API 額度用完、網路斷線，或基金資料不全。請稍後重試。")
                    if st.session_state.get("fund_ai_txt"):
                        st.markdown(st.session_state.fund_ai_txt)

    # v18.159：通用 AI 白話文總結 widget（4 視角 selectbox）
    _render_tab2_ai_summary(GEMINI_KEY)


def _render_tab2_ai_summary(gemini_key: str) -> None:
    """v18.159 Tab2 末端：4 視角 AI 白話文總結 widget。"""
    from ui.helpers.ai_summary import render_ai_summary_widget  # noqa: PLC0415
    fd = st.session_state.get("fund_data") or {}
    if not fd:
        return  # 尚未載入基金，不顯示 widget
    m = fd.get("metrics") or {}
    name = fd.get("name", "") or fd.get("code", "") or "—"
    lines = [f"## 單一基金快照：{name}"]
    for k in ("nav", "ret_1m", "ret_3m", "ret_1y", "ret_1y_total",
              "annual_div_rate", "sharpe", "std_1y", "buy1", "buy2",
              "bb_upper", "ma60"):
        if k in m and m[k] not in (None, ""):
            lines.append(f"- {k}：{m[k]}")
    snapshot = "\n".join(lines) if len(lines) > 1 else ""
    headlines = [str(n.get("title", "") or n.get("headline", ""))
                 for n in st.session_state.get("news_items", []) or []
                 if isinstance(n, dict)][:8]
    render_ai_summary_widget(
        tab_key="tab2",
        tab_label=f"單一基金（{name}）",
        snapshot=snapshot,
        headlines=headlines,
        gemini_api_key=gemini_key,
    )


# ══════════════════════════════════════════════════════
# TAB 3 — 組合基金
