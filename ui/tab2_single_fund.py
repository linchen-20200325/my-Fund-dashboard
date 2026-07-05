"""ui/tab2_single_fund.py — 單一基金深度分析 Tab（v18.126 B-C.4）

從 app.py 抽出 Tab2（單一基金深度分析）的渲染邏輯。

設計：
- render_single_fund_tab() -> None **零閉包依賴**（與 Tab4/5/6 同設計）
- 外部 helper 從 ui.helpers.session import（_friendly_error / _is_core_fund / calc_data_health）

對外 API:
- render_single_fund_tab() -> None
"""
from __future__ import annotations

import os

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from shared.colors import BG_DARK_AMBER_1, BG_DARK_AMBER_3, BG_DARK_GREEN_1, BG_DARK_GREEN_2, BG_DARK_NAVY_1, BG_DARK_NAVY_3, BG_DARK_NAVY_4, BG_DARK_RED_1, CAUTION_YELLOW, CHIP_BG_NEAR_BLACK, GH_BG_CARD, GH_BG_PRIMARY, GH_BORDER, GH_FG_PRIMARY, GH_FG_SECONDARY, GRAY_44, GRAY_55, GRAY_66, GRAY_AA, GRAY_CC, INFO_BLUE, MATERIAL_GREEN, MATERIAL_ORANGE, MATERIAL_RED, MD_BLUE_500, MD_DEEP_ORANGE_400, MD_GREEN_A200, MD_GREEN_A400, MD_ORANGE_300, MD_PURPLE_500, STREAMLIT_BG, TRAFFIC_GREEN, TRAFFIC_NEUTRAL, TRAFFIC_RED, WARN_AMBER, WHITE

from repositories.fund import (
    tdcc_search_fund,
)
from services.portfolio_service import dividend_safety as div_safety_check
from services.precision_service import (
    calc_hwm_sigma_levels,
)
from ui.helpers.macro_helpers import (
    mk_fund_signal,
    quartile_check as _quartile_check,
)
from ui.helpers.metric_explainers import render_metric_explainer
from ui.helpers.session import (
    friendly_error as _friendly_error,  # noqa: F401 — re-export for tests / external import
    is_core_fund as _is_core_fund,
    calc_data_health as _calc_data_health_pure,
)

# 其他可能需要的 app.py module-level helpers — 用 lazy import 避免 circular
# fund_fetcher 內的 utility 函式（normalize_result_state / classify_fetch_status）
from fund_fetcher import (
    classify_fetch_status,
    normalize_result_state,
)
# v19.76 K3：MoneyDJ 自動偵測 SSOT（tab2 + tab5 共用）
from services.moneydj_fetcher import auto_fetch_moneydj


def _calc_data_health(indicators=None):
    """同 app.py wrapper：indicators=None → 走 session_state。"""
    ind = indicators if indicators is not None else st.session_state.get("indicators", {})
    return _calc_data_health_pure(ind)


# ── MK 3-3-3 原則評估（v19.295）────────────────────────────────────────────

def _render_333_fund_expander(
    nav_series: "pd.Series",
    metrics: dict,
    display_name: str,
) -> None:
    """MK 3-3-3 原則評估 expander（Tab2 單一基金）。

    C1 成立>3年 / C2 三年年化>7% / C3 同儕排名前1/3
    資料來源：nav_series (DatetimeIndex) + metrics.ret_3y_ann (MoneyDJ)。
    C3 目前顯示說明文字（無 portfolio peer 傳入時）。
    """
    from services.fund_screening import check_333_fund  # EX-PASSTHRU L3→L2 直呼 service

    with st.expander("🎯 MK 3-3-3 優質標的評估", expanded=False):
        st.caption(
            "**MK 郭俊宏核心篩選原則** — "
            "①成立 >3年（歷經牛熊）｜"
            "②3年年化報酬 >7%（真正定存替代品）｜"
            "③晨星3顆星 / 同儕前1/3（中前段班有潛力）"
        )

        r = check_333_fund(nav_series, metrics)

        def _icon(b) -> str:
            if b is True:  return '✅'
            if b is False: return '❌'
            return '❓'

        age   = r.get('c1_age_years')
        ret3y = r.get('c2_return_3y')
        src   = r.get('c2_source', '')

        age_str = f'{age:.1f} 年' if age is not None else 'N/A'
        if ret3y is not None:
            ret_str = f'{ret3y * 100:.1f}%'
            ret_note = f'（來源：{src}）' if src else ''
        else:
            ret_str  = 'N/A'
            ret_note = '（需 2.5 年以上 NAV 資料）'

        overall = r.get('overall_pass')
        if overall is True:
            bcolor  = '#16a085'
            verdict = '🏆 C1+C2 全過！符合 MK 3-3-3 初步篩選標準'
        elif overall is False:
            bcolor  = '#c0392b'
            verdict = '⚠️ 未達標 — 至少一項條件不符'
        else:
            bcolor  = '#586069'
            verdict = '📊 評估完成（C3 需人工核對晨星評級）'

        st.markdown(
            f'<div style="border-left:4px solid {bcolor};padding:14px 18px;'
            f'border-radius:6px;margin:10px 0;background:rgba(0,0,0,0.10);">'
            f'<div style="font-size:1.05em;font-weight:bold;margin-bottom:10px;">{verdict}</div>'
            '<table style="width:100%;border-collapse:collapse;font-size:0.95em;">'
            f'<tr><td style="padding:5px 0;color:#8b949e;width:55%">① 成立時間 &gt; 3 年</td>'
            f'<td>{_icon(r.get("c1_pass"))} &nbsp;<b>{age_str}</b></td></tr>'
            f'<tr><td style="padding:5px 0;color:#8b949e;">② 3 年年化報酬 &gt; 7%</td>'
            f'<td>{_icon(r.get("c2_pass"))} &nbsp;<b>{ret_str}</b>'
            f'<span style="font-size:0.85em;color:#8b949e;"> {ret_note}</span></td></tr>'
            '<tr><td style="padding:5px 0;color:#8b949e;">③ 晨星評級 / 同儕前 1/3</td>'
            '<td>❓ &nbsp;<span style="font-size:0.85em;color:#8b949e;">'
            '請至 <a href="https://www.morningstar.com.tw" target="_blank">Morningstar.com.tw</a>'
            ' 查詢同類評級</span></td></tr>'
            '</table></div>',
            unsafe_allow_html=True,
        )

        # 輔助提示
        if age is not None and not r.get('c1_pass'):
            remain = 3.0 - age
            st.caption(f'⏳ 距離 3 年門檻還需 {remain:.1f} 年（{int(remain * 12)} 個月）')
        if ret3y is not None and not r.get('c2_pass'):
            gap = 0.07 - ret3y
            st.caption(f'❗ 年化報酬距 7% 目標差 {gap * 100:.1f} 個百分點')
        if r.get('c2_pass') is True and r.get('c1_pass') is True:
            st.caption('💡 C1+C2 通過後，請至晨星確認 C3（同類前 40 名 ≈ 3 顆星以上）'
                       '，三項全過才是 MK 定義的「基優生」。')

        with st.expander('📖 3-3-3 原則說明', expanded=False):
            st.markdown(
                '**①成立 >3 年** — 足以歷經完整牛熊循環，有資本利得作為配息後盾，'
                '可透過歷史驗證抗跌能力。\n\n'
                '**②3 年年化報酬 >7%** — MK 核心目標：找「7% 以上的定存替代品」。'
                '長期穩定 7%+ 代表能透過資本利得+股息完整支付配息，不吃本金。\n\n'
                '**③晨星 3 顆星 / 同儕前 1/3** — 晨星 3 顆星 = 同類前 40 名。'
                '選中前段班而非頂尖，因為資優生落差大；中前段班費率、風控和績效已達標，'
                '更有持續往上的空間。'
            )


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
    from ui.helpers.story_nav import render_story_nav
    render_story_nav("fund")
    st.caption("輸入 MoneyDJ 代碼或網址，即時抓取淨值 / 持股 / 配息 / 風險指標")

    # ── 輸入列（自動偵測境內/境外，移除 radio）────────────────────
    _t2_input_col, _t2_btn_col = st.columns([5.6, 1])
    with _t2_input_col:
        mj_url_input = st.text_input("MoneyDJ URL 或代碼",
            placeholder="輸入代碼（TLZF9 / ACTI94）或貼上完整 MoneyDJ 網址",
            label_visibility="collapsed", key="mj_url_input")
    with _t2_btn_col:
        do_load = st.button("🚀 分析", type="primary", use_container_width=True, key="btn_mj_load")

    # v19.76 K3：原 38 行 _auto_fetch_moneydj + 4 行 _build_moneydj_url 已遷移至
    # services.moneydj_fetcher，tab2/tab5 共用同一份 fallback chain。

    if do_load and mj_url_input.strip():
        # v18.60: 載入前清 fetch 快取，確保用最新 calc_metrics 邏輯
        try:
            from fund_fetcher import clear_all_caches as _cac_t2
            import repositories.macro_repository  # noqa: F401
            _cac_t2()
        except Exception:
            pass   # smoke-allow-pass
        with st.spinner("📡 自動偵測基金類型並抓取資料..."):
            fd_raw, _t2_page_type = auto_fetch_moneydj(
                mj_url_input.strip(), return_page_type=True
            )
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
            # v18.272：記錄到「曾經查過的基金清單」（Tab6 說明書顯示）
            try:
                from services.fund_history import record_fund as _rec_fh
                _rec_fh(
                    fd_raw.get("full_key", ""),
                    fd_raw.get("fund_name", ""),
                    source="Tab2",
                )
            except Exception:
                pass  # 紀錄失敗不影響主流程
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
            # v19.60：partial = MoneyDJ 已抓到 perf/risk_metrics，僅 NAV 歷史序列失敗。
            # 紅色 st.error 與下方成功顯示的風險/績效表自相矛盾 → 降為黃色 warning。
            _p_fn = fd.get("fund_name", "") or fd.get("full_key", "")
            st.warning(
                f"⚠️ **{_p_fn}** — 部分數據已取得（歷史淨值序列未取得）\n\n"
                f"系統已抓到基本資料 / 績效 / 風險指標，下方可繼續查看。\n"
                f"但 Sharpe / σ 買賣點 / 配息率等需完整 NAV 歷史的核心分析會略過。\n\n"
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
                # v19.193 SSOT:呼叫 portfolio_service.get_factor_availability(),
                # 確保診斷 ✅/❌ ↔ calc_fund_factor_score 實際納入 factor 1-1 對齊。
                # 修正 v19.191 inline 走岔(mgmt_fee="N/A"/expense_ratio=0/tr1y="abc"/
                # annual_div_rate=None 等 case 的 ✅/❌ 偏差)。
                from services.portfolio_service import get_factor_availability as _gfa
                _m_diag = fd.get("metrics") or {}
                # 若 fd 未帶 risk_table 但 moneydj_raw 有 → 補上,匹配 calc_fund_factor_score
                # caller 慣例。
                _avail_fd = dict(fd)
                if "perf" not in _avail_fd:
                    _avail_fd["perf"] = _mj_raw.get("perf") or {}
                _avail = _gfa(_avail_fd, risk_table=_mj_raw.get("risk_metrics"))
                def _mk_bool(b: bool) -> str:
                    return "✅" if b else "—"
                _adv_3y = _m_diag.get("ret_3y_ann")
                _adv_5y = _m_diag.get("ret_5y_ann")
                def _mk(v):
                    return "✅" if v is not None else "—"
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
                    f"📊 進階指標(對齊 calc_fund_factor_score SSOT):\n"
                    f"  Sortino:     {_mk_bool(_avail['Sortino'])}  (需 ≥60 筆 + ≥5 筆負報酬)\n"
                    f"  Calmar:      {_mk_bool(_avail['Calmar'])}  (需 3Y 年化 / 或 1Y 報酬 + max_dd)\n"
                    f"  Alpha:       {_mk_bool(_avail['Alpha'])}  (perf.1Y 可解析;adr 預設 0)\n"
                    f"  費用率:      {_mk_bool(_avail['ExpenseRatio'])}  (arg/expense_ratio/mgmt_fee float 可解析)\n"
                    f"  3Y 年化:     {_mk(_adv_3y)}  (需 NAV ≥ 3 年,非 6F factor)\n"
                    f"  5Y 年化:     {_mk(_adv_5y)}  (需 NAV ≥ 5 年,非 6F factor)\n"
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
                    f"<div style='background:{BG_DARK_AMBER_3};border:1px solid {MATERIAL_ORANGE};"
                    f"border-radius:10px;padding:14px 18px;margin:8px 0'>"
                    f"<div style='color:{MATERIAL_ORANGE};font-weight:700;font-size:13px;margin-bottom:8px'>"
                    f"🟡 部分資料（歷史淨值序列未取得，下方顯示已有資訊）</div>"
                    + (f"<div style='color:{GRAY_CC};font-size:11px;margin-bottom:6px'>{_p_err}</div>"
                       if _p_err else "")
                    + (f"<div style='color:{TRAFFIC_NEUTRAL};font-size:11px;border-top:1px solid {BG_DARK_AMBER_1};padding-top:8px;margin-top:4px'>"
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
                            f"background:{GH_BG_CARD};border-radius:6px;margin:3px 0'>"
                            f"<span style='color:{TRAFFIC_NEUTRAL};font-size:12px'>{lbl}(1Y)</span>"
                            f"<span style='font-weight:700'>{val}</span></div>",
                            unsafe_allow_html=True)

                # 若有績效數據，顯示
                if _p_perf:
                    st.markdown("#### 📈 績效數據（已取得）")
                    _perf_cols = st.columns(len(_p_perf))
                    for _pi, (_pk, _pv) in enumerate(list(_p_perf.items())[:4]):
                        _perf_cols[_pi].metric(f"報酬率({_pk})", f"{_pv:.2f}%" if isinstance(_pv,(int,float)) else str(_pv))
            else:
                st.markdown("### ① 基本資料 & 淨值趨勢")
                # v19.283:NAV 來源 + 跨度攤在最顯眼處(不藏進 expander)。
                # 背景:user 反饋 TLZF9「成立 0.1 年」查無資料位置 → 根因是
                # _fetch_fund_single 用「筆數」把關導致短源(如 insurance_subdomain
                # ~1 月)搶先鎖定,連 span-extend(v19.281)有無觸發都無從得知。
                # 直接顯示 data_source(哪個 SSOT 來源贏)+ nav_span_days(v19.281
                # fund_orchestration._fetch_fund_single 算好、存在 result 裡的既有
                # 欄位,此處純讀取顯示,不重算 — 對齊 SSOT)。
                _nav_src = mj_raw.get("data_source") or "—"
                _nav_span_d = mj_raw.get("nav_span_days")
                _nav_span_txt = (
                    f" ‧ 跨度 {_nav_span_d} 天(≈{_nav_span_d / 365.25:.1f} 年)"
                    if isinstance(_nav_span_d, (int, float)) else ""
                )
                st.success(
                    f"✅ **{name or fk}** ｜ 淨值 {len(s)} 筆 ‧ 配息 {len(divs)} 筆"
                    f" ‧ 來源:`{_nav_src}`{_nav_span_txt}"
                )

                # v19.62 E3：MoneyDJ 資料新鮮度條（單檔，鏡像 Tab5 / Stock 個股）
                try:
                    from ui.helpers.freshness import render_mj_freshness_banner
                    render_mj_freshness_banner([{
                        "code": fk or fd.get("fund_code", "?"),
                        "name": name or fk,
                        "nav_date": fd.get("nav_date", ""),
                        "fetched_at": fd.get("_moneydj_fetched_at", ""),
                    }])
                except Exception:
                    pass

                # v19.65 I2：單檔 ↔ 組合持倉聯動（讀 Tab3 portfolio_funds，跨 Tab 訊號）
                try:
                    from ui.helpers.portfolio_linkage import render_fund_portfolio_membership
                    render_fund_portfolio_membership(
                        st.session_state,
                        fund_codes=[fk, fd.get("fund_code", ""), fd.get("full_key", "")],
                        fund_name=name,
                    )
                except Exception:
                    pass

                # MK 訊號卡片
                phase_info_s = st.session_state.phase_info if st.session_state.macro_done else None
                if phase_info_s:
                    sig = mk_fund_signal(fd, phase_info_s["phase"], phase_info_s["score"])
                    _aa = sig.get("auto_alloc")
                    if _aa:
                        _aa_stk, _aa_bnd, _aa_lbl, _aa_c = _aa
                        st.markdown(f"<div style='background:{BG_DARK_NAVY_1};border:1px solid {_aa_c};border-radius:8px;padding:8px 14px;margin:4px 0 8px 0;display:flex;align-items:center;gap:16px'>"
                            f"<span>📊</span><div><div style='color:{_aa_c};font-weight:700;font-size:12px'>總經自動配比建議：{_aa_lbl}</div>"
                            f"<div style='color:{GRAY_CC};font-size:12px'>股 {_aa_stk}% ／ 債 {_aa_bnd}%</div></div></div>", unsafe_allow_html=True)
                    _sig_style = sig["sig_style"]
                    # v19.273 Phase 2 TOP 2.1:卡片外框走 gh_card chrome SSOT(byte-identical)
                    from ui.components.cards import gh_card
                    st.markdown(gh_card(
                        f"<div><div style='color:{TRAFFIC_NEUTRAL};font-size:11px'>資產屬性</div><div style='font-size:14px;font-weight:700;color:{INFO_BLUE}'>{sig['asset_class']}</div></div>"
                        f"<div><div style='color:{TRAFFIC_NEUTRAL};font-size:11px'>策略3 操作訊號</div><span style='{_sig_style};padding:4px 12px;border-radius:20px;font-size:13px;font-weight:700;display:inline-block'>{sig['label']}</span></div>"
                        f"<div style='flex:1'><div style='color:{TRAFFIC_NEUTRAL};font-size:11px'>景氣位階（{phase_info_s['phase']} {phase_info_s['score']}/10）</div>"
                        f"<div style='font-size:12px;color:{GH_FG_SECONDARY}'>{sig['reason']}</div></div>",
                        radius=10, padding="14px 18px", margin="8px 0",
                        extra="display:flex;align-items:center;gap:16px;flex-wrap:wrap",
                    ), unsafe_allow_html=True)

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
                # v19.312 §1 Fail-Loud：帶點 < 2 時畫不出通道(tonexty 填色至少需 2 點成線;
                # rolling(20) 需 ≥21 個 NAV 點)→ 明講「資料不足」,不再默默省略讓 user 以為功能壞掉。
                _bb_drawable = len(_bb_up) >= 2 and len(_bb_dn) >= 2
                if _bb_drawable:
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
                else:
                    st.caption(
                        f"⚠️ 布林通道(±2σ)無法繪製 — 本檔 NAV 歷史僅 {len(s)} 點,"
                        "需 ≥21 點(20 日窗口)。此為**資料不足**非功能故障,"
                        "NAV 歷史補足後自動恢復。")
                # MA20 中軌
                fig_n.add_trace(go.Scatter(
                    x=_bb_ma.dropna().index, y=_bb_ma.dropna().values,
                    name="MA20", line=dict(color=MATERIAL_ORANGE, width=1, dash="dot")))
                # MA60
                _ma60 = s.rolling(60).mean()
                fig_n.add_trace(go.Scatter(
                    x=_ma60.dropna().index, y=_ma60.dropna().values,
                    name="MA60", line=dict(color=MD_PURPLE_500, width=1, dash="dot")))
                # 淨值主線（純線；不再 fill 到 0 以免 y 軸被自動拉到 0 壓扁走勢）
                fig_n.add_trace(go.Scatter(
                    x=df_show["date"], y=df_show["nav"],
                    name="淨值", mode="lines",
                    line=dict(color=MD_BLUE_500, width=2)))

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

                # ── MK v3.2 買賣水平線（回歸中樞 ± kσ；σ=近1年淨值統計標準差）────
                for bv, bl, bc in [
                    (m.get("buy1"), "買1 小跌(中樞-1σ)", MD_GREEN_A200),
                    (m.get("buy2"), "買2 急跌(中樞-2σ)", MATERIAL_GREEN),
                    (m.get("buy3"), "買3 大跌(中樞-3σ)", MD_PURPLE_500),
                ]:
                    if bv:
                        fig_n.add_hline(y=bv, line_color=bc, line_dash="dot",
                                        annotation_text=bl, annotation_font_color=bc,
                                        annotation_position="bottom right")
                for sv, sl, sc in [
                    (m.get("sell1"), "賣1 小漲(中樞+1σ)", WARN_AMBER),
                    (m.get("sell2"), "賣2 急漲(中樞+2σ)", MD_DEEP_ORANGE_400),
                    (m.get("sell3"), "賣3 大漲(中樞+3σ)", MATERIAL_RED),
                ]:
                    if sv:
                        fig_n.add_hline(y=sv, line_color=sc, line_dash="dash",
                                        annotation_text=sl, annotation_font_color=sc,
                                        annotation_position="top right")
                # 年高/年低參考線（區間脈絡；非 band 錨點）— A+B 的 A 面
                for _rv, _rl in [(m.get("high_1y"), "年高"), (m.get("low_1y"), "年低")]:
                    if _rv:
                        fig_n.add_hline(y=float(_rv), line_color=TRAFFIC_NEUTRAL,
                                        line_dash="longdash", line_width=1, opacity=0.55,
                                        annotation_text=_rl, annotation_font_color=TRAFFIC_NEUTRAL,
                                        annotation_font_size=9, annotation_position="top left")

                # ── y 軸範圍：取 NAV / BB / 買賣線 / 年高低整體 min-max，留 5% 邊界 ──
                _y_vals = [float(v) for v in df_show["nav"].dropna().values]
                if len(_bb_up) > 0: _y_vals += [float(v) for v in _bb_up.values if pd.notna(v)]
                if len(_bb_dn) > 0: _y_vals += [float(v) for v in _bb_dn.values if pd.notna(v)]
                for _hv in (m.get("buy1"), m.get("buy2"), m.get("buy3"),
                            m.get("sell1"), m.get("sell2"), m.get("sell3"),
                            m.get("high_1y"), m.get("low_1y")):
                    if _hv: _y_vals.append(float(_hv))
                if _y_vals:
                    _y_min, _y_max = min(_y_vals), max(_y_vals)
                    _y_pad = max((_y_max - _y_min) * 0.05, _y_max * 0.005, 1e-4)
                    _y_range = [_y_min - _y_pad, _y_max + _y_pad]
                else:
                    _y_range = None

                fig_n.update_layout(
                    paper_bgcolor=STREAMLIT_BG, plot_bgcolor=GH_BG_CARD,
                    font_color=GH_FG_PRIMARY, height=420,
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
                            MATERIAL_GREEN if v > 0.5 else (MATERIAL_RED if v < -0.5 else MATERIAL_ORANGE)
                            for v in [_m_gd, _m_od, _m_nd]]
                        fig_mini = go.Figure(go.Bar(
                            x=["毛利率", "營益率", "淨利率"],
                            y=[_m_gd, _m_od, _m_nd],
                            marker_color=_mini_colors,
                            text=[f"{v:+.1f}%" for v in [_m_gd, _m_od, _m_nd]],
                            textposition="outside",
                            textfont=dict(size=10)))
                        fig_mini.add_hline(y=0, line_color=GRAY_55, line_width=1)
                        fig_mini.update_layout(
                            paper_bgcolor=STREAMLIT_BG, plot_bgcolor=GH_BG_CARD,
                            font_color=GH_FG_PRIMARY, height=240,
                            margin=dict(t=10, b=10, l=5, r=5),
                            showlegend=False,
                            yaxis=dict(gridcolor=BG_DARK_NAVY_3, zeroline=False))
                        st.plotly_chart(fig_mini, use_container_width=True)
                        _tot_mom = _m_gd + _m_od + _m_nd
                        if _tot_mom > 2:
                            st.markdown("🟢 **三率雙升**<br>基本面防護", unsafe_allow_html=True)
                        elif _tot_mom < -2:
                            st.markdown("🔴 **三率衰退**<br>虛漲陷阱", unsafe_allow_html=True)
                        else:
                            st.markdown("🟡 **三率持平**<br>搭配布林研判", unsafe_allow_html=True)

                st.markdown("### ② 買賣點信號（標準差策略）")
                # ── MK 標準差買賣點分析 v3.0（3 買 + 3 賣 + 接近度）──
                _m_buy1 = m.get("buy1"); _m_buy2 = m.get("buy2"); _m_buy3 = m.get("buy3")
                _m_sell1 = m.get("sell1"); _m_sell2 = m.get("sell2"); _m_sell3 = m.get("sell3")
                _m_pl = m.get("pos_label",""); _m_pc = m.get("pos_color",TRAFFIC_NEUTRAL)
                _m_mode = m.get("buy_mode","")  # v19.313: 買賣 band σ 改區間基準,不再標 wb07
                _m_nav_v = float(m.get("nav") or 0)
                _NEAR = float(m.get("near_threshold_pct") or 2.0)
                def _proximity_chip(nav_v, target, is_buy):
                    """買: nav≤target 觸發；賣: nav≥target 觸發；±NEAR% 為接近區"""
                    if (not target) or nav_v <= 0:
                        return ("—", GRAY_66, "")
                    delta = (nav_v - target) / target * 100  # 正=高於 target
                    if is_buy:
                        if delta <= 0:           return ("🟢 觸發", MD_GREEN_A400, f"{abs(delta):.2f}% 已破")
                        elif delta <= _NEAR:     return ("⚠️ 接近", WARN_AMBER, f"還差 {delta:.2f}%")
                        else:                    return ("▲ 距離", GRAY_66,    f"還差 {delta:.2f}%")
                    else:
                        if delta >= 0:           return ("🔔 觸發", MATERIAL_RED, f"{delta:.2f}% 已過")
                        elif delta >= -_NEAR:    return ("⚠️ 接近", WARN_AMBER, f"還差 {-delta:.2f}%")
                        else:                    return ("▼ 距離", GRAY_66,    f"還差 {-delta:.2f}%")
                if _m_buy1:
                    _rows = ""
                    for _bv, _bl, _bc, _is_buy in [
                        (_m_buy3,  "💧 大跌大買 (50%) 中樞-3σ", MD_PURPLE_500, True),
                        (_m_buy2,  "💧 急跌穩買 (30%) 中樞-2σ", MATERIAL_GREEN, True),
                        (_m_buy1,  "💧 小跌小買 (20%) 中樞-1σ", MD_GREEN_A200, True),
                        (_m_sell1, "💰 小漲停利 (20%) 中樞+1σ", WARN_AMBER, False),
                        (_m_sell2, "💰 急漲停利 (30%) 中樞+2σ", MD_DEEP_ORANGE_400, False),
                        (_m_sell3, "💰 大漲停利 (50%) 中樞+3σ", MATERIAL_RED, False),
                    ]:
                        if not _bv: continue
                        _chip_lbl, _chip_color, _chip_dist = _proximity_chip(_m_nav_v, _bv, _is_buy)
                        _rows += (f"<div style='display:flex;align-items:center;justify-content:space-between;"
                                  f"padding:5px 12px;background:{GH_BG_PRIMARY};border-radius:6px;margin:3px 0;gap:8px'>"
                                  f"<span style='color:{_bc};font-size:12px;flex:1'>{_bl}</span>"
                                  f"<span style='font-weight:700;font-size:13px;min-width:64px;text-align:right'>{_bv:.4f}</span>"
                                  f"<span style='color:{_chip_color};font-size:11px;min-width:74px;text-align:right;font-weight:600'>{_chip_lbl}</span>"
                                  f"<span style='color:{GRAY_66};font-size:10px;min-width:96px;text-align:right'>{_chip_dist}</span>"
                                  f"</div>")
                    # v19.273 Phase 2 TOP 2.2:σ 買賣點卡外框走 gh_card chrome SSOT(byte-identical)
                    from ui.components.cards import gh_card
                    st.markdown(gh_card(
                        f"<div style='display:flex;align-items:center;justify-content:space-between;margin-bottom:8px'>"
                        f"<span style='color:{TRAFFIC_NEUTRAL};font-size:11px'>📍 策略3 標準差買賣點 v3.2（{_m_mode} ｜ σ=近1年淨值標準差 ｜ 中樞±kσ）</span>"
                        f"<span style='background:{CHIP_BG_NEAR_BLACK};color:{_m_pc};border:1px solid {_m_pc};padding:2px 10px;"
                        f"border-radius:12px;font-size:12px;font-weight:700'>{_m_pl}</span>"
                        f"</div>"
                        + _rows
                        + f"<div style='color:{GRAY_66};font-size:10px;margin-top:6px'>現值 {_m_nav_v:.4f} ｜ 接近閾值 ±{_NEAR:.1f}%</div>",
                        radius=10, padding="12px 16px", margin="10px 0",
                    ), unsafe_allow_html=True)

                # ── V3-3: -2σ 超跌機會卡（布林下軌突破警報）────────────
                _boll_latest_low = float(_bb_dn.iloc[-1]) if len(_bb_dn) > 0 else None
                if _boll_latest_low is not None and _m_nav_v > 0 and _m_nav_v <= _boll_latest_low:
                    st.markdown(
                        f"<div style='background:linear-gradient(135deg,{BG_DARK_GREEN_2},#0d2a0d);"
                        f"border:2px solid {MD_GREEN_A400};border-radius:12px;padding:14px 18px;margin:10px 0'>"
                        f"<div style='color:{MD_GREEN_A400};font-size:14px;font-weight:700;margin-bottom:8px'>"
                        f"⚡ -2σ 超跌機會卡 — 布林下軌突破！</div>"
                        f"<div style='display:flex;gap:24px;flex-wrap:wrap;margin-bottom:8px'>"
                        f"<div><div style='color:{TRAFFIC_NEUTRAL};font-size:10px'>現值 NAV</div>"
                        f"<div style='color:{WHITE};font-weight:700;font-size:16px'>{_m_nav_v:.4f}</div></div>"
                        f"<div><div style='color:{TRAFFIC_NEUTRAL};font-size:10px'>布林下軌(-2σ)</div>"
                        f"<div style='color:{MD_GREEN_A400};font-weight:700;font-size:16px'>{_boll_latest_low:.4f}</div></div>"
                        f"<div><div style='color:{TRAFFIC_NEUTRAL};font-size:10px'>跌破幅度</div>"
                        f"<div style='color:{MD_GREEN_A200};font-weight:700;font-size:16px'>"
                        f"{(_boll_latest_low - _m_nav_v) / _boll_latest_low * 100:.2f}%</div></div>"
                        f"</div>"
                        f"<div style='color:{GRAY_AA};font-size:11px;border-top:1px solid #1a3a1a;padding-top:8px'>"
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
                                f"<div style='background:{BG_DARK_NAVY_1};border:2px solid {_hc};"
                                f"border-radius:12px;padding:14px 18px;margin:10px 0'>"
                                f"<div style='color:{_hc};font-size:13px;font-weight:800;margin-bottom:10px'>"
                                f"📐 HWM σ 絕對位階 — {_hl}</div>"
                                f"<div style='display:flex;gap:20px;flex-wrap:wrap;margin-bottom:10px'>"
                                f"<div><div style='color:{TRAFFIC_NEUTRAL};font-size:10px'>歷史最高(HWM)</div>"
                                f"<div style='color:{WHITE};font-weight:700;font-size:16px'>{_hwm_v:.4f}</div></div>"
                                f"<div><div style='color:{TRAFFIC_NEUTRAL};font-size:10px'>現值 NAV</div>"
                                f"<div style='color:{_hc};font-weight:700;font-size:16px'>{_nav_h:.4f}</div></div>"
                                f"<div><div style='color:{TRAFFIC_NEUTRAL};font-size:10px'>距 HWM</div>"
                                f"<div style='color:{_hc};font-weight:700;font-size:16px'>{_dist:+.2f}%</div></div>"
                                f"<div><div style='color:{TRAFFIC_NEUTRAL};font-size:10px'>σ 位階</div>"
                                f"<div style='color:{_hc};font-weight:700;font-size:16px'>{_sr:+.2f}σ</div></div>"
                                f"</div>"
                                f"<div style='display:flex;gap:12px;flex-wrap:wrap;font-size:11px'>"
                                f"<span style='color:{MD_GREEN_A200}'>HWM-1σ: {_l1:.4f}</span>"
                                f"<span style='color:{MATERIAL_ORANGE}'>HWM-2σ: {_l2:.4f}</span>"
                                f"<span style='color:{MATERIAL_RED}'>HWM-3σ: {_l3:.4f}</span>"
                                f"</div>"
                                f"<div style='color:{GRAY_66};font-size:10px;margin-top:6px'>"
                                f"σ = HWM × 年化日報酬標準差（{len(s)} 筆淨值計算）</div>"
                                f"</div>", unsafe_allow_html=True)
                    except Exception:
                        pass  # smoke-allow-pass

                # ── v18.47: 📊 基金健康總覽（4 維度評分 + Overall Grade + 白話結論）──
                # v19.177 #3A+#4B：4D 評分 + grade 全走 services.health.grade.compute_4d_health SSOT,
                # input 走 _resolve_adr_with_fallback / compute_1y_total_return SSOT。
                # 原本 162 行 inline 邏輯(3 套 fallback chain + 4 套 score lookup + grade cutoff)
                # 收斂到 ~30 行,全站個檔健康度評等統一同源。
                try:
                    from services.health.dividend import _resolve_adr_with_fallback
                    from services.health.grade import compute_4d_health
                    from services.fund_total_return import compute_1y_total_return

                    _g_tr1y, _ = compute_1y_total_return({
                        "metrics": m,
                        "moneydj_raw": mj_raw,
                        "series": s,
                        "perf_source": fd.get("perf_source") or mj_raw.get("perf_source"),
                    })
                    _g_dy, _ = _resolve_adr_with_fallback({
                        "moneydj_raw": mj_raw,
                        "metrics": m,
                        "dividends": divs,
                    })
                    _rm = (mj_raw.get("risk_metrics") or {})
                    _g_sharpe = m.get("sharpe") or (
                        ((_rm.get("risk_table") or {}).get("一年") or {}).get("Sharpe")
                    )
                    _g_sigma = m.get("std_1y") or (
                        ((_rm.get("risk_table") or {}).get("一年") or {}).get("標準差")
                    )

                    # 60d MA 方向(UI 端算,因需 nav series 而非純 metrics)
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
                        pass  # smoke-allow-pass — MA 方向估算失敗不影響其他維度

                    _4d = compute_4d_health(
                        tr1y_pct=_g_tr1y, adr_pct=_g_dy,
                        sharpe=_g_sharpe, sigma_pct=_g_sigma, ma_dir=_g_ma_dir,
                    )
                    _d1_cov = _4d["factors"]["coverage"]
                    _d2_sh = _4d["factors"]["sharpe"]
                    _d3_tr = _4d["factors"]["trend"]
                    _d4_vol = _4d["factors"]["volatility"]
                    _g_overall = _4d["score"]
                    _gr, _gr_c, _verd = _4d["grade"], _4d["grade_color"], _4d["verdict"]
                    _eat_call = (f" ⚠️ <b style='color:{MATERIAL_RED}'>吃本金風險</b>"
                                 if _4d["eat_warn"] else "")

                    def _g_block(label, score):
                        if score is None:
                            return (f"<div><div style='color:{GRAY_66};font-size:10px'>" + label + "</div>"
                                    f"<div style='color:{GRAY_66};font-size:20px;font-weight:700'>—</div>"
                                    f"<div style='color:{GRAY_55};font-size:9px'>資料不足</div></div>")
                        _c = (MATERIAL_GREEN if score >= 75 else MD_GREEN_A200 if score >= 60 else
                              CAUTION_YELLOW if score >= 45 else MATERIAL_ORANGE if score >= 30 else MATERIAL_RED)
                        return (f"<div><div style='color:{TRAFFIC_NEUTRAL};font-size:10px'>{label}</div>"
                                f"<div style='color:{_c};font-size:20px;font-weight:900'>{score:.0f}</div>"
                                f"<div style='color:{GRAY_55};font-size:9px'>/ 100</div></div>")

                    st.markdown(
                        f"<div style='background:linear-gradient(135deg,{GH_BG_PRIMARY},{GH_BG_CARD});"
                        f"border:2px solid {_gr_c};border-radius:12px;padding:14px 18px;margin:8px 0 12px'>"
                        f"<div style='display:flex;align-items:center;gap:16px;margin-bottom:10px;flex-wrap:wrap'>"
                        f"<div style='color:{_gr_c};font-size:46px;font-weight:900;line-height:1'>{_gr}</div>"
                        f"<div style='flex:1;min-width:200px'>"
                        f"<div style='color:{GRAY_AA};font-size:11px'>📊 基金健康總覽</div>"
                        f"<div style='color:{_gr_c};font-size:16px;font-weight:800;margin-top:2px'>{_verd}{_eat_call}</div></div>"
                        f"<div style='color:{TRAFFIC_NEUTRAL};font-size:11px;text-align:right'>"
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
                    pass  # smoke-allow-pass — 評分卡失敗不影響後續資訊

                # ── v18.20: 🔴 吃本金 KPI 紅綠燈（獨立 banner，主 KPI 列旁）──
                # 不依賴 divs[] 是否有資料；只要有 ret_1y + 任一配息率來源即顯示。
                # 無配息資料時顯示 ⬜ 不適用（累積型基金等）。
                try:
                    # v19.177:adr 走 SSOT _resolve_adr_with_fallback 3 層 chain,
                    # 與健診總表 check_eating_principal_1y_mk 同源,免散落。
                    from services.health.dividend import _resolve_adr_with_fallback
                    _kpi_adr, _kpi_adr_src = _resolve_adr_with_fallback({
                        "moneydj_raw": mj_raw,
                        "metrics": m,
                        "dividends": divs,
                    })
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
                        _kpi_icon, _kpi_color, _kpi_bg = "⬜", TRAFFIC_NEUTRAL, GH_BG_CARD
                        _kpi_title = "吃本金檢查 — ⬜ 不適用"
                        _kpi_msg = "本基金無年化配息率資料（可能為累積型 / 不配息基金）"
                        _kpi_cov_txt = "—"
                    elif _kpi_tr1y is None:
                        _kpi_icon, _kpi_color, _kpi_bg = "⬜", TRAFFIC_NEUTRAL, GH_BG_CARD
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
                        _kpi_color = {"red": MATERIAL_RED, "yellow": MATERIAL_ORANGE,
                                      "green": MATERIAL_GREEN}.get(_kpi_al, TRAFFIC_NEUTRAL)
                        _kpi_bg = {"red": BG_DARK_RED_1, "yellow": BG_DARK_AMBER_1,
                                   "green": BG_DARK_GREEN_1}.get(_kpi_al, GH_BG_CARD)
                        _kpi_icon = {"red": "🔴", "yellow": "🟡",
                                     "green": "🟢"}.get(_kpi_al, "⬜")
                        _kpi_title = f"吃本金檢查 — {_kpi_icon} {_kpi_ds.get('status','')}"
                        _kpi_msg = _kpi_ds.get("message", "")
                        # v19.178:_src_note dict 過時清掉(舊 key 'perf'/'nav_actual'/
                        # 'nav_annualized_*' v19.175 後皆不命中 → fallback 文字「樣本 wb01
                        # (MoneyDJ 官方)」自相矛盾)。SSOT compute_1y_total_return 已回
                        # 人類可讀格式("wb01 (MoneyDJ 官方)" / "本地還原淨值法 (v18.71)" /
                        # "ret_1y_total (本地, Nd 窗口)" / "NAV 序列年化 (Nd 外推)" / "—"),
                        # 直接顯示即可。
                        if _kpi_tr1y_src and _kpi_tr1y_src not in ("metrics", "—", ""):
                            _kpi_msg = f"{_kpi_msg}　〔1Y 來源:{_kpi_tr1y_src}〕"
                        _kpi_cov_txt = (f"{_kpi_cov:.2f}" if _kpi_cov is not None
                                        else "—")

                    st.markdown(
                        f"<div style='background:{_kpi_bg};border:2px solid {_kpi_color};"
                        f"border-radius:12px;padding:12px 16px;margin:10px 0'>"
                        f"<div style='color:{_kpi_color};font-size:13px;font-weight:800;"
                        f"margin-bottom:8px'>{_kpi_title}</div>"
                        f"<div style='display:flex;gap:24px;flex-wrap:wrap'>"
                        f"<div><div style='color:{TRAFFIC_NEUTRAL};font-size:10px'>1Y 含息報酬</div>"
                        f"<div style='color:{WHITE};font-weight:700;font-size:16px'>"
                        f"{(f'{_kpi_tr1y:.2f}%' if _kpi_tr1y is not None else '—')}</div></div>"
                        f"<div><div style='color:{TRAFFIC_NEUTRAL};font-size:10px'>年化配息率</div>"
                        f"<div style='color:{WHITE};font-weight:700;font-size:16px'>"
                        f"{(f'{_kpi_adr:.2f}%' if _kpi_adr and _kpi_adr > 0 else '—')}</div></div>"
                        f"<div><div style='color:{TRAFFIC_NEUTRAL};font-size:10px'>Coverage</div>"
                        f"<div style='color:{_kpi_color};font-weight:700;font-size:16px'>"
                        f"{_kpi_cov_txt}</div></div>"
                        f"</div>"
                        f"<div style='color:{GRAY_AA};font-size:11px;margin-top:6px'>{_kpi_msg}</div>"
                        f"</div>", unsafe_allow_html=True)
                except Exception as _kpi_e:  # noqa: BLE001
                    st.caption(f"吃本金 KPI 計算異常：{str(_kpi_e)[:60]}")

                # v19.181:📊 進階指標(入門 KPI 之外的細項 — Sortino/Calmar/Alpha/Expense
                # /MaxDD/3Y-5Y 年化/3-3-3 篩/MK 換標的建議)— 共用 fund_health_report SSOT,
                # 跨 Tab3/健診 同源。
                try:
                    # v19.182:預設展開,user 第一眼就看到(原 v19.181 expanded=False 收起來
                    # 容易被忽略 — user 反饋「沒看到進階指標」)。
                    with st.expander(
                        "📊 進階指標(Sortino / Calmar / Alpha / Expense / 3Y-5Y / 3-3-3 / 換標的建議)",
                        expanded=True,
                    ):
                        from services.health.report import (
                            build_dividend_summary_row,
                            build_health_analysis_row,
                        )
                        _adv_fd = {
                            "moneydj_raw": mj_raw,
                            "metrics": m,
                            "series": s,
                            "dividends": divs,
                            "perf_source": fd.get("perf_source") or mj_raw.get("perf_source"),
                            "fund_name": fd.get("fund_name") or mj_raw.get("fund_name") or fk,
                        }
                        # v19.186 fix:本檔局部代碼變數為 fk(L234),非 code → 修 NameError
                        _adv_code = fk or fd.get("fund_code", "?")
                        _adv_h = build_health_analysis_row(_adv_fd, _adv_code)
                        _adv_d = build_dividend_summary_row(_adv_fd, _adv_code, principal_twd=None)

                        # v19.225 P1-1 leftover:inline _fmt_pct 收口至 shared/converters.fmt_pct SSOT
                        # (non-ratio + decimals=2 + plus=False 對應原 "{v:.2f}%")
                        def _fmt_pct(v):
                            from shared.converters import fmt_pct
                            return fmt_pct(v, plus=False, decimals=2, ratio=False)
                        def _fmt_num(v):
                            return f"{v:.2f}" if isinstance(v, (int, float)) else "—"

                        st.markdown("##### 🩺 健康分析(4D Grade + 6 進階指標)")
                        cA, cB, cC, cD = st.columns(4)
                        cA.metric("4D Grade", _adv_h.get("4D Grade") or "—",
                                  help="A≥80 / B≥65 / C≥50 / D≥35 / F<35(SSOT v19.177)")
                        cB.metric("4D Score", _fmt_num(_adv_h.get("4D Score")))
                        cC.metric("Sharpe 1Y", _fmt_num(_adv_h.get("Sharpe 1Y")),
                                  help="自計算(NAV 序列,用於 4D 評分);見下方風險指標對帳")
                        cD.metric("Sortino", _fmt_num(_adv_h.get("Sortino")))

                        cE, cF, cG, cH = st.columns(4)
                        cE.metric("Calmar", _fmt_num(_adv_h.get("Calmar")))
                        cF.metric("真實收益 %", _fmt_pct(_adv_h.get("Alpha %")),
                                  help="含息報酬率 − 年化配息率（≠ CAPM Alpha）")
                        cG.metric("費用率 %", _fmt_pct(_adv_h.get("費用率 %")))
                        cH.metric("Max DD %", _fmt_pct(_adv_h.get("Max DD %")))

                        cI, cJ, cK = st.columns(3)
                        cI.metric("3Y 年化 %", _fmt_pct(_adv_h.get("3Y 年化 %")))
                        cJ.metric("5Y 年化 %", _fmt_pct(_adv_h.get("5Y 年化 %")))
                        cK.metric("MK 3-3-3", _adv_h.get("MK 3-3-3", "⬜"))

                        st.markdown("##### 💰 換標的建議(MK 4 規則心型警結合)")
                        st.markdown(
                            f"**{_adv_d.get('換標的建議', '⬜ 資料不足')}**　"
                            f"<span style='color:{TRAFFIC_NEUTRAL};font-size:11px'>"
                            f"{_adv_d.get('_換標的 detail', '')}</span>",
                            unsafe_allow_html=True,
                        )
                        st.caption(
                            "MK 4 規則:(a) 吃本金且持有 ≥ 1 年 / (b) 4D Grade F / "
                            "(c) 3-3-3 未通過且持有 ≥ 3 年 / (d) Sharpe<0 且 max_dd<-30%。"
                            "任一中 → 🔴 換 / 1-2 觀察 → 🟡 / 全未中 → 🟢。"
                            "**Tab2 單檔無 user 持有期 → (a)(c) 用基金成立年數判定**。"
                        )
                        # v19.191:對齊「資料診斷」面板 — 進階指標各欄位「—」的原因揭露。
                        # user 看了知道是「資料源真沒提供」還是「歷史長度不足」。
                        _miss = []
                        if _adv_h.get("Sortino") is None:
                            _miss.append("Sortino(需 NAV ≥ 60 筆 + ≥5 筆負報酬)")
                        if _adv_h.get("Calmar") is None:
                            _miss.append("Calmar(需 3Y 年化 或 1Y 報酬 + max_dd)")
                        if _adv_h.get("Alpha %") is None:
                            _miss.append("真實收益(需 perf.1Y + 年化配息率)")
                        if _adv_h.get("費用率 %") is None:
                            _miss.append("費用率(MoneyDJ wb01 mgmt_fee fallback)")
                        if _adv_h.get("3Y 年化 %") is None:
                            _miss.append("3Y 年化(需 NAV ≥ 3 年)")
                        if _adv_h.get("5Y 年化 %") is None:
                            _miss.append("5Y 年化(需 NAV ≥ 5 年)")
                        if _miss:
                            st.caption(
                                "🔍 **「—」欄位原因**:"
                                + " · ".join(_miss)
                                + "(對齊資料診斷面板)"
                            )
                except Exception as _adv_e:  # noqa: BLE001
                    st.caption(f"⬜ 進階指標渲染失敗:{type(_adv_e).__name__}: {str(_adv_e)[:60]}")

                st.markdown("### ③ 風險指標 & 配息")
                # 關鍵指標 + 配息
                col_a, col_b = st.columns(2)
                with col_a:
                    st.markdown("#### 📊 風險指標")
                    risk_tbl = mj_raw.get("risk_metrics",{}).get("risk_table",{})
                    _r1y = risk_tbl.get("一年",{})
                    _std1 = _r1y.get("標準差","—"); _sh1 = _r1y.get("Sharpe","—")
                    _al1  = _r1y.get("Alpha","—");  _be1 = _r1y.get("Beta","—")
                    for lbl, val in [("波動 σ(1Y)", f"{_std1}%" if isinstance(_std1, (int, float)) else _std1),("Sharpe(1Y)",str(_sh1)),("Alpha(1Y)",str(_al1)),("Beta(1Y)",str(_be1))]:
                        st.markdown(f"<div style='display:flex;justify-content:space-between;padding:5px 10px;background:{GH_BG_CARD};border-radius:6px;margin:3px 0'><span style='color:{TRAFFIC_NEUTRAL};font-size:12px'>{lbl}</span><span style='font-weight:700'>{val}</span></div>", unsafe_allow_html=True)
                    # F-RECON-1 phase 6 v19.91 — Sharpe 對帳 chip(self-calc vs MoneyDJ wb07)
                    _sh_rec = (m or {}).get("sharpe_reconcile")
                    if isinstance(_sh_rec, dict) and _sh_rec.get("status") in ("agree", "disagree", "a_missing", "b_missing"):
                        _sh_emoji = {"agree": "✅", "disagree": "⚠️",
                                     "a_missing": "⬜", "b_missing": "⬜"}.get(_sh_rec.get("status"), "⬜")
                        _sh_color = {"agree": TRAFFIC_GREEN, "disagree": TRAFFIC_RED}.get(_sh_rec.get("status"), TRAFFIC_NEUTRAL)
                        _va, _vb = _sh_rec.get("value_a"), _sh_rec.get("value_b")
                        _va_t = f"{_va:.2f}" if isinstance(_va, (int, float)) else "—"
                        _vb_t = f"{_vb:.2f}" if isinstance(_vb, (int, float)) else "—"
                        st.markdown(
                            f"<div style='font-size:10px;color:{_sh_color};padding:3px 10px;"
                            f"background:{GH_BG_PRIMARY};border-radius:4px;margin:2px 0 6px 0'>"
                            f"{_sh_emoji} 對帳:自算={_va_t} vs MoneyDJ wb07={_vb_t} ({_sh_rec.get('status')})"
                            f"</div>",
                            unsafe_allow_html=True)
                    # Sharpe 持久性說明（孫慶龍老師框架）
                    try:
                        _sh1_v = float(_sh1)
                        if _sh1_v > 0.5:
                            _sh_txt, _sh_c = "優秀（>0.5）持久創造超額報酬", MATERIAL_GREEN
                        elif _sh1_v >= 0:
                            _sh_txt, _sh_c = "普通（0~0.5）勉強補償風險", MATERIAL_ORANGE
                        else:
                            _sh_txt, _sh_c = "差勁（<0）不如持有現金", MATERIAL_RED
                        st.markdown(
                            f"<div style='font-size:10px;color:{_sh_c};padding:3px 10px;"
                            f"background:{GH_BG_PRIMARY};border-radius:4px;margin:2px 0 6px 0'>"
                            f"策略2框架：{_sh_txt}</div>",
                            unsafe_allow_html=True)
                    except (ValueError, TypeError):
                        pass  # smoke-allow-pass
                    # 四分位
                    peer = mj_raw.get("risk_metrics",{}).get("peer_compare",{})
                    qr = _quartile_check(peer, risk_tbl)
                    if qr["quartile"]:
                        _qr_color = qr["color"]
                        _qr_adv = (f"<div style='color:{MATERIAL_ORANGE};font-size:11px;margin-top:4px'>{qr['advice']}</div>"
                                   if qr.get("advice") else "")
                        st.markdown(
                            f"<div style='background:{BG_DARK_NAVY_4};border-radius:8px;padding:8px 12px;margin-top:6px'>"
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
                        # F-RECON-1 phase 6 v19.91 — 配息殖利率對帳 chip(self-calc vs MoneyDJ)
                        _dy_rec = (m or {}).get("div_yield_reconcile")
                        if isinstance(_dy_rec, dict) and _dy_rec.get("status") in ("agree", "disagree", "a_missing", "b_missing"):
                            _dy_emoji = {"agree": "✅", "disagree": "⚠️",
                                         "a_missing": "⬜", "b_missing": "⬜"}.get(_dy_rec.get("status"), "⬜")
                            _dy_color = {"agree": TRAFFIC_GREEN, "disagree": TRAFFIC_RED}.get(_dy_rec.get("status"), TRAFFIC_NEUTRAL)
                            _dva, _dvb = _dy_rec.get("value_a"), _dy_rec.get("value_b")
                            _dva_t = f"{_dva*100:.2f}%" if isinstance(_dva, (int, float)) else "—"
                            _dvb_t = f"{_dvb*100:.2f}%" if isinstance(_dvb, (int, float)) else "—"
                            st.caption(
                                f"<span style='color:{_dy_color};font-size:10px'>"
                                f"{_dy_emoji} 對帳:自算={_dva_t} vs MoneyDJ={_dvb_t} ({_dy_rec.get('status')})</span>",
                                unsafe_allow_html=True)
                        # F-RECON-1 phase 6 v19.91 — 1Y 報酬對帳 chip(self-calc vs MoneyDJ wb01)
                        _r1y_rec = (m or {}).get("ret_1y_reconcile")
                        if isinstance(_r1y_rec, dict) and _r1y_rec.get("status") in ("agree", "disagree", "a_missing", "b_missing"):
                            _r1y_emoji = {"agree": "✅", "disagree": "⚠️",
                                          "a_missing": "⬜", "b_missing": "⬜"}.get(_r1y_rec.get("status"), "⬜")
                            _r1y_color = {"agree": TRAFFIC_GREEN, "disagree": TRAFFIC_RED}.get(_r1y_rec.get("status"), TRAFFIC_NEUTRAL)
                            _ra, _rb = _r1y_rec.get("value_a"), _r1y_rec.get("value_b")
                            _ra_t = f"{_ra*100:.2f}%" if isinstance(_ra, (int, float)) else "—"
                            _rb_t = f"{_rb*100:.2f}%" if isinstance(_rb, (int, float)) else "—"
                            st.caption(
                                f"<span style='color:{_r1y_color};font-size:10px'>"
                                f"{_r1y_emoji} 1Y 報酬對帳:自算={_ra_t} vs MoneyDJ wb01={_rb_t} ({_r1y_rec.get('status')})</span>",
                                unsafe_allow_html=True)
                        for d in divs[:6]:
                            _dt = d.get("date",""); _amt = d.get("amount",""); _yld = d.get("yield_pct","")
                            st.markdown(f"<div style='display:flex;justify-content:space-between;padding:4px 10px;background:{GH_BG_CARD};border-radius:6px;margin:2px 0'><span style='color:{TRAFFIC_NEUTRAL};font-size:11px'>{_dt}</span><span style='font-weight:700'>{_amt}</span><span style='color:{MATERIAL_ORANGE};font-size:11px'>{_yld}</span></div>", unsafe_allow_html=True)

                        # ── 🚨 吃本金警示（Core Protocol Ch.3.2）──
                        _tr1y = m.get("ret_1y")  # 含息總報酬率近 1 年（%）
                        if _tr1y is not None and _adr > 0:
                            _ds = div_safety_check(
                                total_return=float(_tr1y),
                                dividend_yield=float(_adr),
                                nav_change=float(m.get("ret_1y", 0) or 0),
                            )
                            _al = _ds.get("alert_level","grey")
                            _bg = {"red":BG_DARK_RED_1,"yellow":BG_DARK_AMBER_1,"green":BG_DARK_GREEN_1}.get(_al,CHIP_BG_NEAR_BLACK)
                            _bc = {"red":MATERIAL_RED,"yellow":MATERIAL_ORANGE,"green":MATERIAL_GREEN}.get(_al,TRAFFIC_NEUTRAL)
                            st.markdown(
                                f"<div style='background:{_bg};border:1px solid {_bc};border-radius:8px;"
                                f"padding:8px 12px;margin-top:8px'>"
                                f"<div style='color:{_bc};font-weight:700;font-size:12px'>{_ds['status']}</div>"
                                f"<div style='color:{GRAY_CC};font-size:11px;margin-top:2px'>{_ds['message']}</div>"
                                + (f"<div style='color:{MATERIAL_ORANGE};font-size:10px;margin-top:4px'>{_ds['nav_warning']}</div>" if _ds.get("nav_warning") else "")
                                + "</div>", unsafe_allow_html=True)

                        # ── 📖 配息覆蓋率講義卡（MK 郭俊宏《以息養股》）──
                        _tr1y_f = float(_tr1y) if _tr1y is not None else None
                        _adr_f  = float(_adr)  if _adr  else 0.0
                        if _tr1y_f is not None and _adr_f > 0:
                            _cov = _tr1y_f / _adr_f
                            _cov_c = MATERIAL_GREEN if _cov >= 1.0 else (MATERIAL_ORANGE if _cov >= 0.8 else MATERIAL_RED)
                            _cov_label = (
                                "🟢 安全 — 報酬足以支撐配息，無吃本金疑慮" if _cov >= 1.0 else
                                "🟡 注意 — 輕微侵蝕，需觀察趨勢" if _cov >= 0.8 else
                                "🔴 警示 — 嚴重吃本金，領息賠價差"
                            )
                            st.markdown(
                                f"<div style='background:{GH_BG_PRIMARY};border:1px dashed {GH_BORDER};"
                                f"border-radius:10px;padding:10px 14px;margin-top:8px'>"
                                f"<div style='color:{TRAFFIC_NEUTRAL};font-size:10px;letter-spacing:1px;margin-bottom:6px'>"
                                f"📖 配息覆蓋率講義 ── 策略3《以息養股》</div>"
                                f"<div style='color:{GRAY_AA};font-size:11px;font-style:italic;"
                                f"border-left:2px solid {GRAY_44};padding-left:8px;margin-bottom:8px'>"
                                f"「高殖利率不等於高報酬，必須確認是否吃本金。」</div>"
                                f"<div style='font-family:monospace;font-size:12px;color:{GH_FG_PRIMARY};margin-bottom:6px'>"
                                f"Coverage = TR₁Y ÷ 年化配息率<br>"
                                f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
                                f"= {_tr1y_f:.1f}% ÷ {_adr_f:.2f}%"
                                f" = <span style='color:{_cov_c};font-weight:700;font-size:14px'>{_cov:.2f}</span></div>"
                                f"<div style='color:{_cov_c};font-size:12px;font-weight:600;margin-bottom:6px'>"
                                f"{_cov_label}</div>"
                                f"<div style='color:{GRAY_55};font-size:10px'>"
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
                            _ter_c = MATERIAL_RED if _ter_diff > 0.3 else (MATERIAL_ORANGE if _ter_diff > 0 else MATERIAL_GREEN)
                            _ter_vs = f"高於均值 +{_ter_diff:.2f}%" if _ter_diff > 0 else f"低於均值 {abs(_ter_diff):.2f}%"
                            _ter_avg_html = (
                                f"<div><div style='color:{TRAFFIC_NEUTRAL};font-size:10px'>同類均值</div>"
                                f"<div style='color:{TRAFFIC_NEUTRAL};font-weight:700;font-size:16px'>{_ter_avg:.2f}%</div></div>"
                                f"<div><div style='color:{TRAFFIC_NEUTRAL};font-size:10px'>費用比較</div>"
                                f"<div style='color:{_ter_c};font-weight:700;font-size:16px'>{_ter_vs}</div></div>"
                            )
                        else:
                            _ter_c, _ter_avg_html = TRAFFIC_NEUTRAL, ""
                        st.markdown(
                            f"<div style='background:{GH_BG_CARD};border:1px solid {GH_BORDER};"
                            f"border-radius:10px;padding:10px 16px;margin:8px 0'>"
                            f"<div style='color:{TRAFFIC_NEUTRAL};font-size:11px;margin-bottom:6px'>💰 TER 費用率分析"
                            + (f" — {_ter_cat[:12]}" if _ter_cat else "") + "</div>"
                            f"<div style='display:flex;gap:24px;flex-wrap:wrap;margin-bottom:6px'>"
                            f"<div><div style='color:{TRAFFIC_NEUTRAL};font-size:10px'>最高經理費</div>"
                            f"<div style='color:{_ter_c};font-weight:700;font-size:16px'>{_ter_val:.2f}%</div></div>"
                            + _ter_avg_html +
                            f"</div>"
                            f"<div style='color:{GRAY_55};font-size:10px'>"
                            f"費用率愈低，長期複利效益愈佳（費用每降 1%，20 年後終值多 ~25%）</div>"
                            f"</div>", unsafe_allow_html=True)

                # ── 持股分析（折疊）── v19.282 SSOT:改呼共用 render_holdings_detail;
                # 空持股時顯示三源抓取診斷(不再靜默),expander 永遠顯示(user 要求
                # 單一基金也放持股資訊)。
                from ui.helpers.holdings import (
                    render_holdings_detail, render_holdings_diag,
                )
                _holdings = mj_raw.get("holdings", {}) or {}
                _tops     = _holdings.get("top_holdings", []) or []   # 下方個股新聞 / AI snapshot 用
                _sectors  = _holdings.get("sector_alloc", []) or []   # 下方 AI snapshot 用
                _hdate    = _holdings.get("data_date", "")
                _has_hold = bool(_sectors or _tops)
                with st.expander(
                    "📂 持股分析" + (f"（{_hdate}）" if _hdate else ""),
                    expanded=_has_hold,
                ):
                    if not render_holdings_detail(_holdings):
                        render_holdings_diag(_holdings)

                # ── 📰 個股新聞面（v18.206）：逐股 Google News 搜尋（按鈕）+ AI 新聞面分析 ──
                if _tops:
                    from repositories.news_repository import (  # noqa: PLC0415
                        fetch_stock_news as _fetch_stk,
                    )
                    _fund_key_sn = str(fk or name or "fund")[:40]
                    _ss_stk = f"_stknews_{_fund_key_sn}"
                    _hold_list = []   # (顯示名, 查詢字)
                    for _topn in _tops[:6]:
                        _nm = str(_topn.get("name", "")).strip()
                        if not _nm:
                            continue
                        _zh = _zh_holding(_nm)
                        _hold_list.append((_zh or _nm[:20], _zh or _nm))
                    with st.expander(f"📰 個股新聞面（前 {len(_hold_list)} 大持股）",
                                     expanded=False):
                        _snc1, _snc2 = st.columns([3, 1])
                        _snc1.caption("逐一搜尋 Google News（中文，走 NAS proxy）。"
                                      "廣義 RSS 常抓不到台股/冷門股，此按鈕直接針對每檔持股搜尋。")
                        _do_fetch = _snc2.button(
                            "📡 抓個股新聞", key=f"btn_stknews_{_fund_key_sn}",
                            use_container_width=True)
                        if _do_fetch:
                            _fetched: dict = {}
                            _prog = st.progress(0.0)
                            for _ci, (_disp, _q) in enumerate(_hold_list):
                                try:
                                    _items = _fetch_stk(_q, max_items=3)
                                except Exception:
                                    _items = []
                                if _items:
                                    _fetched[_disp] = _items
                                _prog.progress((_ci + 1) / max(len(_hold_list), 1))
                            _prog.empty()
                            st.session_state[_ss_stk] = _fetched
                        _stk_data = st.session_state.get(_ss_stk)
                        if _stk_data:
                            _tot = sum(len(v) for v in _stk_data.values())
                            st.caption(f"共 {_tot} 則個股新聞（{len(_stk_data)} 檔持股命中）")
                            for _disp_nm, _items in _stk_data.items():
                                for _it in _items:
                                    _u = _it.get("url", "")
                                    _ttl = _it.get("title", "")
                                    _src = _it.get("source", "")
                                    _lh = (f"<a href='{_u}' target='_blank' "
                                           f"style='color:{INFO_BLUE};text-decoration:none'>{_ttl}</a>"
                                           if _u else _ttl)
                                    st.markdown(
                                        f"<div style='padding:4px 8px;background:{GH_BG_CARD};"
                                        f"border-radius:6px;margin:2px 0;font-size:12px'>"
                                        f"<span style='color:{MD_ORANGE_300};font-weight:700'>{_disp_nm}</span>　"
                                        f"{_lh}<span style='color:{GRAY_66};font-size:10px;"
                                        f"margin-left:6px'>{_src}</span></div>",
                                        unsafe_allow_html=True)
                        elif _do_fetch:
                            st.caption("逐股搜尋後仍無結果（可能 NAS Proxy 斷線，"
                                       "或這些持股近期無中文新聞）。")
                        else:
                            st.caption("👆 點「📡 抓個股新聞」開始逐股搜尋。")
                    # v18.207：個股新聞的 AI 分析已併入下方唯一的「④ AI 深度解盤」
                    # （讀 session_state 的 _stknews 一起進全章節快照），此處不再單獨掛 AI。

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
                                _ov_color = (MATERIAL_GREEN if "🟢" in _overall_verdict
                                             else MATERIAL_RED if "🔴" in _overall_verdict
                                             else MATERIAL_ORANGE)
                                st.markdown(
                                    f"<div style='background:{GH_BG_PRIMARY};border:2px solid {_ov_color};"
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

                # v18.260p6：💰 投資試算 — 投入 TWD → 換原幣 → 單位數 / 月配息 TWD / 月配股
                with st.container(border=True):
                    st.markdown("#### 💰 投資試算 — 投入金額 → 單位數 / 配息估算")
                    _ccy_raw = (mj_raw.get("currency") or "TWD").strip() or "TWD"
                    # v19.75 K2：遷移到 services/currency SSOT（mode="yf" 保留 Tab2 既有
                    # 行為：人民幣→CNH 以走 yfinance 較可靠的 CNHTWD=X 報價）。
                    from services.currency import normalize_ccy as _norm_ccy
                    _ccy = _norm_ccy(_ccy_raw, default="TWD", mode="yf")
                    _nav_calc = m.get("nav")
                    # v19.181 Bug 1 fix: 與 fund_checkup.py:352-353 同源 — MoneyDJ wb05
                    # 官方年化配息率優先 → metrics.annual_div_rate fallback;
                    # 過去單一基金頁直接吃 metrics 導致與組合體檢表算出不同月配息(7.36% vs 7.49%)。
                    _mj_dy_raw = mj_raw.get("moneydj_div_yield")
                    try:
                        _mj_dy_calc = float(_mj_dy_raw) if _mj_dy_raw not in (None, "", "—") else None
                    except (TypeError, ValueError):
                        _mj_dy_calc = None
                    if _mj_dy_calc and _mj_dy_calc > 0:
                        _yield_calc = _mj_dy_calc
                    else:
                        _yield_calc = m.get("annual_div_rate")
                    try:
                        _nav_calc = float(_nav_calc) if _nav_calc not in (None, "", "—") else None
                    except (TypeError, ValueError):
                        _nav_calc = None
                    try:
                        _yield_calc = float(_yield_calc) if _yield_calc not in (None, "", "—") else None
                    except (TypeError, ValueError):
                        _yield_calc = None
                    # v18.259：非 TWD 基金抓即時 FX rate（5min TTL，走 NAS proxy）
                    # v18.264：Yahoo 失敗時走 FRED 第二來源（需 FRED_API_KEY）
                    # v18.265：secrets 讀取與 FX 抓取分開 try，避免 secrets 沒設時連 Yahoo 都沒試
                    # v18.278：TWD 基金（不論是「台幣」中文還是「TWD」ISO）直接 fx=1.0 跳過所有 FX 邏輯
                    _fx_to_twd = None
                    _fx_err = ""
                    _fx_manual = False
                    _fx_source = ""  # "Yahoo" / "FRED" / "手動"
                    if _ccy == "TWD":
                        _fx_to_twd = 1.0   # TWD 基金不需換匯
                    elif _ccy != "TWD":
                        # 先讀 FRED key（讀失敗只是少了 fallback，不該擋 Yahoo）
                        import os as _os
                        _fred_k = ""
                        try:
                            _fred_k = st.secrets.get("FRED_API_KEY", "")
                        except Exception:
                            _fred_k = ""
                        if not _fred_k:
                            _fred_k = _os.environ.get("FRED_API_KEY", "")

                        # 抓 FX（Yahoo → FRED fallback chain 內建於 get_latest_fx）
                        try:
                            from services.fund_service import get_latest_fx
                            _fx_to_twd = get_latest_fx(f"{_ccy}TWD=X", fred_api_key=_fred_k)
                            if _fx_to_twd is None or _fx_to_twd <= 0:
                                # v18.275：TWD pair 對應 chain 已精簡為 Yahoo + er-api（其他都已死掉）
                                _fx_err = f"Yahoo / er-api 都暫無 {_ccy}TWD 報價（請至「資料診斷」→ FX 來源診斷查具體失敗源；可能 NAS proxy 暫時不通）"
                                _fx_to_twd = None
                            else:
                                _fx_source = "即時"
                        except Exception as _e:
                            _fx_err = f"FX 抓取失敗：{_e}"
                    _ic1, _ic2 = st.columns([2, 1])
                    with _ic1:
                        _amount_twd = st.number_input(
                            "投入金額（新台幣 TWD）",
                            min_value=10_000, max_value=100_000_000,
                            value=1_000_000, step=100_000,
                            key=f"_calc_amt_{fk}",
                            help="以新台幣計價的投入本金；非 TWD 基金會用即時匯率換成原幣再算單位數與配息。"
                        )
                    with _ic2:
                        st.caption(f"NAV：{_nav_calc if _nav_calc is not None else '—'} {_ccy}")
                        st.caption(f"年化配息率：{_yield_calc if _yield_calc is not None else '—'} %")
                        # v18.278：normalize 後 _ccy 已是 ISO，TWD 基金 _fx_to_twd=1.0 不顯示 FX caption
                        if _ccy == "TWD":
                            st.caption("💰 此基金以新台幣計價（FX = 1）")
                        elif _fx_to_twd:
                            # 自動換匯成功 — user 要求「移除設定匯率的按鈕」
                            st.caption(f"💱 1 {_ccy} = **{_fx_to_twd:.4f}** TWD（即時匯率）")
                        else:
                            # 只有自動失敗才顯示手動 fallback
                            st.caption(f"⚠️ 無法取得 {_ccy}/TWD 即時匯率（{_fx_err}），切換手動模式：")
                            _fx_manual_val = st.number_input(
                                f"手動填 1 {_ccy} = ? TWD",
                                min_value=0.01, max_value=1000.0,
                                value=32.0, step=0.1,
                                key=f"_calc_fx_{fk}",
                                help="自動 FX 抓取失敗時的 fallback；估算僅供參考",
                            )
                            _fx_to_twd = float(_fx_manual_val) if _fx_manual_val > 0 else None
                            _fx_manual = True
                    if _nav_calc and _nav_calc > 0:
                        # TWD → 原幣本金（TWD 基金維持原值）
                        if _ccy != "TWD" and _fx_to_twd:
                            _amt_local = _amount_twd / _fx_to_twd
                        else:
                            _amt_local = float(_amount_twd)
                        _units = _amt_local / _nav_calc
                        _fx_tag = "即時（Yahoo / er-api 雙來源）" if not _fx_manual else "手動"
                        _mc1, _mc2, _mc3, _mc4 = st.columns(4)
                        _mc1.metric("可申購單位數", f"{_units:,.2f}")
                        if _yield_calc and _yield_calc > 0:
                            # 配息型：原幣算配息 → 換回 TWD；月配股 = 月配息 ÷ NAV
                            _ann_div = _amt_local * _yield_calc / 100.0
                            _mon_div = _ann_div / 12.0
                            _mon_units = _mon_div / _nav_calc
                            if _ccy != "TWD" and _fx_to_twd:
                                _ann_div_twd = _ann_div * _fx_to_twd
                                _mon_div_twd = _mon_div * _fx_to_twd
                            else:
                                _ann_div_twd = _ann_div
                                _mon_div_twd = _mon_div
                            _mc2.metric("月配息（TWD）", f"{_mon_div_twd:,.0f}")
                            _mc3.metric("月配股（單位）", f"{_mon_units:,.2f}",
                                        help="月配息若再投入可換得的單位數（月配息 ÷ NAV）")
                            _mc4.metric("年化配息率", f"{_yield_calc:.2f}%",
                                        help="年化配息率 = 年配息 / 投入本金（原幣）")
                            if _ccy != "TWD":
                                st.success(
                                    f"💱 **換算 TWD**（1 {_ccy} = {_fx_to_twd:.4f}，{_fx_tag}）："
                                    f"本金 {_amount_twd:,.0f} TWD → "
                                    f"原幣本金 **{_amt_local:,.2f}** {_ccy} → "
                                    f"可買 **{_units:,.2f}** 單位｜"
                                    f"年息 **{_ann_div_twd:,.0f}** TWD"
                                    f"（每月 ≈ **{_mon_div_twd:,.0f}** TWD"
                                    f" / 配股 ≈ **{_mon_units:,.2f}** 單位）"
                                )
                            else:
                                st.success(
                                    f"📌 本金 {_amount_twd:,.0f} TWD → 可買 **{_units:,.2f}** 單位｜"
                                    f"年息 **{_ann_div_twd:,.0f}** TWD"
                                    f"（每月 ≈ **{_mon_div_twd:,.0f}** TWD"
                                    f" / 配股 ≈ **{_mon_units:,.2f}** 單位）"
                                )

                            # v18.263：完整計算公式（含數字代入）— user 反饋「我要有公式的」
                            with st.expander("📐 完整計算公式（含數字代入）", expanded=False):
                                if _ccy != "TWD" and _fx_to_twd:
                                    _formula_text = (
                                        f"# 投入本金 / 單位數\n"
                                        f"原幣本金   = TWD ÷ FX\n"
                                        f"           = {_amount_twd:,.0f} ÷ {_fx_to_twd:.4f}\n"
                                        f"           = {_amt_local:,.2f} {_ccy}\n"
                                        f"\n"
                                        f"可申購單位 = 原幣本金 ÷ NAV\n"
                                        f"           = {_amt_local:,.2f} ÷ {_nav_calc:.4f}\n"
                                        f"           = {_units:,.2f} 單位\n"
                                        f"\n"
                                        f"# 配息（原幣）\n"
                                        f"年配息(原幣) = 原幣本金 × ADR%\n"
                                        f"             = {_amt_local:,.2f} × {_yield_calc:.2f}%\n"
                                        f"             = {_ann_div:,.2f} {_ccy}\n"
                                        f"\n"
                                        f"月配息(原幣) = 年配息(原幣) ÷ 12\n"
                                        f"             = {_ann_div:,.2f} ÷ 12\n"
                                        f"             = {_mon_div:,.2f} {_ccy}\n"
                                        f"\n"
                                        f"# 配息（換回 TWD）\n"
                                        f"年配息(TWD)  = 年配息(原幣) × FX\n"
                                        f"             = {_ann_div:,.2f} × {_fx_to_twd:.4f}\n"
                                        f"             = {_ann_div_twd:,.0f} TWD\n"
                                        f"\n"
                                        f"月配息(TWD)  = 年配息(TWD) ÷ 12\n"
                                        f"             = {_ann_div_twd:,.0f} ÷ 12\n"
                                        f"             = {_mon_div_twd:,.0f} TWD\n"
                                        f"\n"
                                        f"# 月配股（再投入單位）\n"
                                        f"月配股(單位) = 月配息(原幣) ÷ NAV\n"
                                        f"             = {_mon_div:,.2f} ÷ {_nav_calc:.4f}\n"
                                        f"             = {_mon_units:,.2f} 單位\n"
                                    )
                                else:
                                    _formula_text = (
                                        f"# 投入本金 / 單位數（TWD 計價基金）\n"
                                        f"可申購單位 = TWD ÷ NAV\n"
                                        f"           = {_amount_twd:,.0f} ÷ {_nav_calc:.4f}\n"
                                        f"           = {_units:,.2f} 單位\n"
                                        f"\n"
                                        f"# 配息\n"
                                        f"年配息(TWD) = TWD × ADR%\n"
                                        f"            = {_amount_twd:,.0f} × {_yield_calc:.2f}%\n"
                                        f"            = {_ann_div_twd:,.0f} TWD\n"
                                        f"\n"
                                        f"月配息(TWD) = 年配息(TWD) ÷ 12\n"
                                        f"            = {_ann_div_twd:,.0f} ÷ 12\n"
                                        f"            = {_mon_div_twd:,.0f} TWD\n"
                                        f"\n"
                                        f"# 月配股（再投入單位）\n"
                                        f"月配股(單位) = 月配息(TWD) ÷ NAV\n"
                                        f"             = {_mon_div_twd:,.0f} ÷ {_nav_calc:.4f}\n"
                                        f"             = {_mon_units:,.2f} 單位\n"
                                    )
                                st.code(_formula_text, language="text")
                                st.caption(
                                    "⚠️ 估算假設：(1) FX 全期不變 (2) NAV 全期不變 (3) ADR 等於宣告值 "
                                    "(4) 配息 100% 用於再投入計算月配股單位。實際配息以保險公司每月對帳單為準。"
                                )
                            try:
                                st.session_state[f"_calc_invest_{fk}"] = {
                                    "amount": float(_amount_twd),
                                    "amount_local": float(_amt_local),
                                    "currency": _ccy,
                                    "nav": float(_nav_calc),
                                    "units": float(_units),
                                    "annual_div_rate": float(_yield_calc),
                                    "annual_dividend": float(_ann_div),
                                    "monthly_dividend": float(_mon_div),
                                    "monthly_dividend_units": float(_mon_units),
                                    "fx_to_twd": float(_fx_to_twd) if _fx_to_twd else None,
                                    "fx_manual": bool(_fx_manual),
                                    "amount_twd": float(_amount_twd),
                                    "annual_dividend_twd": float(_ann_div_twd),
                                    "monthly_dividend_twd": float(_mon_div_twd),
                                    "fund_type": "income",
                                }
                            except Exception:
                                pass
                        else:
                            # v19.73 K1：累積型用 1Y 總報酬估市值 — 改走 SSOT compute_1y_total_return
                            # 修補 v18.134 漏接點（原本只用 ret_1y_total/ret_1y 跳過 perf["1Y"] 真 1Y）
                            from ui.helpers.macro_helpers import compute_1y_total_return
                            _ret_1y, _ = compute_1y_total_return({
                                "metrics": m, "moneydj_raw": mj_raw,
                            })
                            _proj_1y = None
                            _proj_1y_twd = None
                            if _ret_1y is not None:
                                _proj_1y = _amt_local * (1 + _ret_1y / 100.0)
                                if _ccy != "TWD" and _fx_to_twd:
                                    _proj_1y_twd = _proj_1y * _fx_to_twd
                                else:
                                    _proj_1y_twd = _proj_1y
                            _mc2.metric("基金類型", "累積型（無配息）")
                            if _proj_1y_twd is not None:
                                _mc3.metric("1Y 後預估市值（TWD）", f"{_proj_1y_twd:,.0f}",
                                            f"{_ret_1y:+.2f}%")
                                _mc4.metric("1Y 預估損益（TWD）",
                                            f"{(_proj_1y_twd - _amount_twd):+,.0f}")
                            else:
                                _mc3.metric("1Y 後預估市值（TWD）", "—")
                                _mc4.metric("1Y 預估損益（TWD）", "—")
                            if _ccy != "TWD":
                                _proj_str = (
                                    f"｜1Y 後預估 **{_proj_1y_twd:,.0f}** TWD"
                                    f"（損益 **{(_proj_1y_twd - _amount_twd):+,.0f}** TWD）"
                                    if _proj_1y_twd is not None else ""
                                )
                                st.success(
                                    f"💱 **換算 TWD**（1 {_ccy} = {_fx_to_twd:.4f}，{_fx_tag}）："
                                    f"本金 {_amount_twd:,.0f} TWD → "
                                    f"原幣本金 **{_amt_local:,.2f}** {_ccy} → "
                                    f"可買 **{_units:,.2f}** 單位"
                                    f"{_proj_str}"
                                )
                            else:
                                _proj_str = (
                                    f"｜1Y 後預估 **{_proj_1y_twd:,.0f}** TWD（{_ret_1y:+.2f}%）"
                                    if _proj_1y_twd is not None else ""
                                )
                                st.caption(
                                    f"📌 本金 {_amount_twd:,.0f} TWD → "
                                    f"可買 **{_units:,.2f}** 單位{_proj_str}"
                                )

                            # v18.263：累積型計算公式
                            with st.expander("📐 完整計算公式（含數字代入）", expanded=False):
                                if _ccy != "TWD" and _fx_to_twd:
                                    _formula_lines = [
                                        "# 投入本金 / 單位數",
                                        "原幣本金   = TWD ÷ FX",
                                        f"           = {_amount_twd:,.0f} ÷ {_fx_to_twd:.4f}",
                                        f"           = {_amt_local:,.2f} {_ccy}",
                                        "",
                                        "可申購單位 = 原幣本金 ÷ NAV",
                                        f"           = {_amt_local:,.2f} ÷ {_nav_calc:.4f}",
                                        f"           = {_units:,.2f} 單位",
                                    ]
                                    if _ret_1y is not None and _proj_1y is not None:
                                        _formula_lines += [
                                            "",
                                            "# 1Y 預估市值（用近 1Y 含息報酬推算）",
                                            "1Y 後原幣  = 原幣本金 × (1 + ret_1Y%)",
                                            f"           = {_amt_local:,.2f} × (1 + {_ret_1y:.2f}%)",
                                            f"           = {_proj_1y:,.2f} {_ccy}",
                                            "",
                                            "1Y 後 TWD  = 1Y 後原幣 × FX",
                                            f"           = {_proj_1y:,.2f} × {_fx_to_twd:.4f}",
                                            f"           = {_proj_1y_twd:,.0f} TWD",
                                            "",
                                            "1Y 預估損益 = 1Y 後 TWD − 本金",
                                            f"            = {_proj_1y_twd:,.0f} − {_amount_twd:,.0f}",
                                            f"            = {(_proj_1y_twd - _amount_twd):+,.0f} TWD",
                                        ]
                                    else:
                                        _formula_lines += [
                                            "",
                                            "# 1Y 預估市值：缺 1Y 含息報酬資料，無法推算",
                                        ]
                                else:
                                    _formula_lines = [
                                        "# 投入本金 / 單位數（TWD 計價基金）",
                                        "可申購單位 = TWD ÷ NAV",
                                        f"           = {_amount_twd:,.0f} ÷ {_nav_calc:.4f}",
                                        f"           = {_units:,.2f} 單位",
                                    ]
                                    if _ret_1y is not None and _proj_1y_twd is not None:
                                        _formula_lines += [
                                            "",
                                            "# 1Y 預估市值",
                                            "1Y 後 TWD  = TWD × (1 + ret_1Y%)",
                                            f"           = {_amount_twd:,.0f} × (1 + {_ret_1y:.2f}%)",
                                            f"           = {_proj_1y_twd:,.0f} TWD",
                                            "",
                                            "1Y 預估損益 = 1Y 後 TWD − 本金",
                                            f"            = {_proj_1y_twd:,.0f} − {_amount_twd:,.0f}",
                                            f"            = {(_proj_1y_twd - _amount_twd):+,.0f} TWD",
                                        ]
                                st.code("\n".join(_formula_lines), language="text")
                                st.caption(
                                    "⚠️ 估算假設：(1) FX 全期不變 (2) 未來報酬等於近 1Y 含息表現 "
                                    "(3) 累積型基金不配息、收益反映在 NAV 上漲。實際結果視市場波動而定。"
                                )
                            try:
                                st.session_state[f"_calc_invest_{fk}"] = {
                                    "amount": float(_amount_twd),
                                    "amount_local": float(_amt_local),
                                    "currency": _ccy,
                                    "nav": float(_nav_calc),
                                    "units": float(_units),
                                    "annual_div_rate": None,
                                    "ret_1y_total": _ret_1y,
                                    "fx_to_twd": float(_fx_to_twd) if _fx_to_twd else None,
                                    "fx_manual": bool(_fx_manual),
                                    "amount_twd": float(_amount_twd),
                                    "proj_1y_twd": float(_proj_1y_twd) if _proj_1y_twd else None,
                                    "fund_type": "accumulation",
                                }
                            except Exception:
                                pass
                    else:
                        st.info("⚠️ 此基金 NAV 未取得，無法試算單位數。請先確認基本資料區是否成功抓取淨值。")

                # ── MK 3-3-3 原則評估（v19.295）─────────────────────────────
                try:
                    _render_333_fund_expander(s, m, name or fk)
                except Exception as _e333:
                    import sys as _sys333
                    print(f'[tab2/333] render error: {_e333}', file=_sys333.stderr)

                st.markdown("### ④ AI 深度解盤")
                st.divider()
                # v18.207：Tab2「唯一」AI — 統一 render_ai_summary_widget（4 視角），
                # 吃「全章節快照」（基本/績效/風險/配息/買賣點/持股/產業/個股新聞/三率/總經位階）。
                # 原 v18.135 analyze_fund_json 按鈕、個股新聞 AI、末端重複 widget 已整併於此。
                if GEMINI_KEY:
                    from ui.helpers.ai_summary import render_ai_summary_widget  # noqa: PLC0415
                    from repositories.news_repository import (  # noqa: PLC0415
                        infer_asset_class as _infer_ac,
                        filter_news_by_asset_class as _filter_news,
                    )
                    _ai_fd_pct, _ = _calc_data_health()
                    if _ai_fd_pct < 50:
                        st.caption(f"🔴 總經資料完整率 {_ai_fd_pct}%：建議先到「🌐 總經」按全量抓取，"
                                   "AI 才有景氣位階背景（仍可直接生成、僅準確度略降）。")
                    elif _ai_fd_pct < 80:
                        st.caption(f"🟡 資料完整率 {_ai_fd_pct}%，AI 參考性略降。")

                    _rt1y = ((mj_raw.get("risk_metrics", {}) or {}).get("risk_table", {}) or {}).get("一年", {}) or {}
                    _snap = [f"## 單一基金全章節快照：{name or fk}"]
                    _snap.append(f"- 基本：類別={mj_raw.get('category','') or '—'}"
                                 f"｜幣別={mj_raw.get('currency','') or '—'}"
                                 f"｜最新淨值={m.get('nav','—')}"
                                 f"｜經理費={mj_raw.get('mgmt_fee','') or '—'}")
                    _perf_bits = [f"{_k}={m.get(_k)}" for _k in
                                  ("ret_1m", "ret_3m", "ret_6m", "ret_1y", "ret_1y_total", "ytd")
                                  if m.get(_k) not in (None, "")]
                    if _perf_bits:
                        _snap.append("- 績效：" + "｜".join(_perf_bits))
                    _risk_bits = [f"{_lbl}={_rt1y.get(_key)}" for _lbl, _key in
                                  (("σ", "標準差"), ("Sharpe", "Sharpe"),
                                   ("Alpha", "Alpha"), ("Beta", "Beta"))
                                  if _rt1y.get(_key) not in (None, "")]
                    if _risk_bits:
                        _snap.append("- 風險(1Y)：" + "｜".join(_risk_bits))
                    if m.get("annual_div_rate"):
                        _div_line = f"- 配息：年化配息率≈{m.get('annual_div_rate')}%，近期 {len(divs)} 筆"
                        try:  # 吃本金檢查（含息總報酬 vs 配息率）— Core Protocol Ch.3.2
                            _ds_ai = div_safety_check(
                                total_return=m.get("ret_1y_total"),
                                dividend_yield=m.get("annual_div_rate"),
                                nav_change=m.get("ret_1y_total"),
                            )
                            _cov_ai = _ds_ai.get("coverage")
                            if _cov_ai is not None:
                                _div_line += (f"｜吃本金 coverage={_cov_ai:.2f}"
                                              f"（{_ds_ai.get('alert_level','')}）")
                        except Exception:
                            pass
                        _snap.append(_div_line)
                    _bs = [f"{_k}={m.get(_k)}" for _k in
                           ("buy1", "buy2", "buy3", "sell1", "sell2", "sell3",
                            "bb_upper", "bb_lower", "ma60")
                           if m.get(_k) not in (None, "")]
                    if _bs:
                        _snap.append("- 買賣點/技術：" + "｜".join(_bs))
                    # σ 絕對位階（HWM）— 由淨值序列重算，AI 才知「現價 vs 歷史高點」
                    if s is not None:
                        try:
                            _hwm_ai = calc_hwm_sigma_levels(s, lookback=252)
                            if isinstance(_hwm_ai, dict) and "error" not in _hwm_ai:
                                _snap.append(
                                    f"- σ絕對位階：{_hwm_ai.get('label','')}"
                                    f"｜距HWM={_hwm_ai.get('dist_to_hwm_pct','')}%"
                                    f"｜σ_rank={_hwm_ai.get('sigma_rank','')}")
                        except Exception:
                            pass
                    if _tops:
                        _snap.append("- 前10大持股：" + "、".join(
                            f"{_zh_holding(str(_t.get('name',''))) or str(_t.get('name',''))[:14]}"
                            f"({float(_t.get('pct',0) or 0):.1f}%)" for _t in _tops[:10]))
                    if _sectors:
                        _snap.append("- 產業配置：" + "、".join(
                            f"{str(_s.get('name',''))[:8]} {float(_s.get('pct',0) or 0):.0f}%"
                            for _s in _sectors[:5]))
                    _shield_cache_ai = st.session_state.get(f"shield_{fk}")
                    if _shield_cache_ai:
                        _snap.append(f"- 持倉三率穿透：已掃 {len(_shield_cache_ai)} 檔（毛利/營益/淨利 QoQ）")
                    if phase_info_s:
                        _snap.append(f"- 總經背景：位階={phase_info_s.get('phase','')}"
                                     f"（分數 {phase_info_s.get('score','')}）")
                    # v18.260p6：投資試算 stash → AI 解盤可引用 TWD 月配息/月配股
                    _calc_stash = st.session_state.get(f"_calc_invest_{fk}") or {}
                    if _calc_stash:
                        _cs_ccy = _calc_stash.get("currency", "")
                        _cs_amt_twd = _calc_stash.get("amount_twd") or _calc_stash.get("amount", 0)
                        _cs_amt_local = _calc_stash.get("amount_local", 0)
                        _cs_units = _calc_stash.get("units", 0)
                        _cs_fx = _calc_stash.get("fx_to_twd")
                        _cs_fx_tag = "手動" if _calc_stash.get("fx_manual") else "Yahoo 即時"
                        if _calc_stash.get("fund_type") == "income":
                            _cs_ann_twd = _calc_stash.get("annual_dividend_twd", 0) or 0
                            _cs_mon_twd = _calc_stash.get("monthly_dividend_twd", 0) or 0
                            _cs_mon_units = _calc_stash.get("monthly_dividend_units", 0) or 0
                            _line = (
                                f"- 投資試算：本金 {_cs_amt_twd:,.0f} TWD"
                                f"（≈ {_cs_amt_local:,.2f} {_cs_ccy}）→ "
                                f"{_cs_units:,.2f} 單位｜年息 ≈ {_cs_ann_twd:,.0f} TWD"
                                f"（月 ≈ {_cs_mon_twd:,.0f} TWD"
                                f" / 月配股 ≈ {_cs_mon_units:,.2f} 單位）"
                                f"｜年化配息率 {_calc_stash.get('annual_div_rate',0):.2f}%"
                            )
                            if _cs_fx and _cs_ccy != "TWD":
                                _line += f"｜TWD 換算（1 {_cs_ccy}={_cs_fx:.4f}，{_cs_fx_tag}）"
                            _snap.append(_line)
                        else:
                            _ret = _calc_stash.get("ret_1y_total")
                            _ret_str = f"｜1Y 含息報酬 {_ret:+.2f}%" if _ret is not None else ""
                            _cs_proj_twd = _calc_stash.get("proj_1y_twd")
                            _proj_str = (
                                f"｜1Y 後預估 {_cs_proj_twd:,.0f} TWD"
                                if _cs_proj_twd else ""
                            )
                            _line = (
                                f"- 投資試算：本金 {_cs_amt_twd:,.0f} TWD"
                                f"（≈ {_cs_amt_local:,.2f} {_cs_ccy}）→ "
                                f"{_cs_units:,.2f} 單位（累積型，無配息）"
                                f"{_ret_str}{_proj_str}"
                            )
                            if _cs_fx and _cs_ccy != "TWD":
                                _line += f"｜TWD 換算（1 {_cs_ccy}={_cs_fx:.4f}，{_cs_fx_tag}）"
                            _snap.append(_line)
                    # 新聞：優先「已逐股抓的個股新聞」，否則退資產類別過濾的廣義新聞
                    _stk_news_ai = st.session_state.get(
                        f"_stknews_{str(fk or name or 'fund')[:40]}") or {}
                    if _stk_news_ai:
                        _hl = [it.get("title", "") for items in _stk_news_ai.values()
                               for it in items][:15]
                        _snap.append(f"- 個股新聞：{len(_hl)} 則（逐股 Google News）")
                    else:
                        _t2cls = _infer_ac(f"{name} {mj_raw.get('category','')}")
                        _hl = [str(n.get("title", "")) for n in
                               _filter_news(st.session_state.get("news_items", []) or [], _t2cls)
                               if isinstance(n, dict)][:8]
                    render_ai_summary_widget(
                        tab_key="tab2",
                        tab_label=f"單一基金（{name or fk}）",
                        snapshot="\n".join(_snap),
                        sections=[
                            "基本資料（類別/幣別/淨值/費用）",
                            "績效表現（近期報酬）",
                            "風險指標（波動/夏普等）",
                            "配息與吃本金檢查",
                            "投資試算（每百萬可申購單位與配息估算）",
                            "買賣點與價格位階",
                            "持股與產業配置",
                            "總經大環境背景",
                            "新聞時事影響",
                        ],
                        headlines=_hl,
                        gemini_api_key=GEMINI_KEY,
                    )


# ══════════════════════════════════════════════════════
# TAB 3 — 組合基金
