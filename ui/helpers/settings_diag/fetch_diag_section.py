"""「🔍 抓取診斷細節（哪個源失敗 + NAS Proxy 狀態）」區塊 —— 原封抽自個基頁。

**這個檔案是「原封搬家」的產物，不是新寫的功能。** `render_fetch_diag_section()`
的 body 逐字取自 `ui/tab2_single_fund.py::render_single_fund_tab()` 的
partial 分支（搬遷前的 :419-510，量測日 2026-08-31），搬移過程**只做
「換檔案 + 把 3 個 caller-local 名字改成參數」**，渲染邏輯、判斷式、文案、
例外處理**一個字都沒有改**（`CLAUDE.md §-1.5.3 C` 禁止把行為變更夾帶在搬遷裡）。

為什麼要抽出來（客戶已拍板的線框 `docs/wireframes/fund-wireframe-final.html` §03）
--------------------------------------------------------------------------------
線框在「② 🔍 個基深掘」頁把這一塊標為搬走：

> 🔍 抓取診斷細節（哪個源失敗 + NAS Proxy 狀態）——
> 這是**維運資訊**，卻長在使用者的分析主線上。搬到 ⑤ 設定與診斷 ——
> 那裡本來就是診斷的家（tab2_single_fund.py:386）

並在「⑤ ⚙️ 設定與診斷」的「A · 🔌 連線與帳號」分區列為「搬入」項。

本批（WP-E）的處置：**抽出共用，不切換**
----------------------------------------
- 個基頁改為呼叫本函式，外面包 ⑤ 的所有權旗標
  （`merge_context.FETCH_DIAG`）—— **旗標全空時個基頁行為與抽出前完全相同**。
- ⑤ 透過 `render_fetch_diag_from_session()` 渲染同一塊（讀 `st.session_state`
  裡個基頁抓完留下的 `fund_data`；還沒抓過任何基金時走 ⬜ 灰色說明，不是紅燈）。
- 真正把個基頁那份關掉（⑤ 接線後由 caller 持有 `FETCH_DIAG` 旗標）屬接線批次。

已知登記、本批**不修**的事（禁止夾帶）
--------------------------------------
- 區塊內 `except Exception as _e_pxy` 把 proxy 設定讀取失敗降為一行文字 ——
  這是搬遷前既有行為，是否該改走 `system_error()` 屬另案，本批原樣保留。
"""
from __future__ import annotations

import streamlit as st

from ui.helpers.render_state import not_ready


def render_fetch_diag_section(fd: dict, status_fd: str, fund_name: str) -> None:
    """渲染「🔍 抓取診斷細節」區塊本體（逐字搬自個基頁 partial 分支）。

    Parameters
    ----------
    fd        : 個基頁抓取結果 dict（`st.session_state.fund_data` 的那一份）。
    status_fd : 抓取狀態字串（搬遷前 caller-local `_status_fd`）。
    fund_name : 顯示用基金名（搬遷前 caller-local `_p_fn`，
                即 `fd.get("fund_name","") or fd.get("full_key","")`）。
    """
    # ── 搬遷前的 caller-local 名字，在此原名綁定 ──────────────────────────
    # 刻意保留底線開頭的原名，讓下方區塊與搬遷前**逐字相同**、可直接 diff 比對。
    _status_fd = status_fd
    _p_fn = fund_name

    st.markdown("##### 🔍 抓取診斷細節（哪個源失敗 + NAS Proxy 狀態）")
    with st.container():
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
        # 必修 4:門檻文案改**直接 import SSOT 常數**渲染,不再寫死數字。
        # 舊文案寫的樣本門檻(60)與 Calmar 的一年期退路皆已過時
        # ⚠️ 本註解**刻意不引用舊文案原字串** —— `test_stale_threshold_copy_removed`
        #    是對整檔原始碼做子字串掃描,註解裡引用等於自己讓自己紅。
        # (實際 250 / 756,且 1Y fallback 已取消)→ user 看到「我有 100 筆
        # 應該夠」但畫面顯示「—」= §1 要防的「無法察覺的矛盾」。
        from services.fund_service import (
            MIN_DOWNSIDE_OBS_SORTINO as _MIN_DOWN,
            MIN_OBS_CALMAR as _MIN_CALMAR,
            MIN_OBS_MAX_DRAWDOWN as _MIN_MDD,
            MIN_OBS_SHARPE_SORTINO as _MIN_SS,
        )
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
            f"  Sortino:     {_mk_bool(_avail['Sortino'])}  "
            f"(需 ≥{_MIN_SS} 交易日 + ≥{_MIN_DOWN} 筆低於 MAR 的報酬)\n"
            f"  Calmar:      {_mk_bool(_avail['Calmar'])}  "
            f"(需 ≥{_MIN_CALMAR} 交易日 = 3Y;**無** 1Y fallback)\n"
            f"  Max DD:      {_mk(_m_diag.get('max_drawdown'))}  "
            f"(需 ≥{_MIN_MDD} 交易日)\n"
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


def render_fetch_diag_from_session() -> None:
    """⑤ 端入口：讀個基頁留在 session 的抓取結果，渲染同一塊診斷。

    - 還沒抓過任何基金 → ⬜ 灰色說明（不是紅燈：什麼都沒壞，只是還沒有東西可診斷）。
    - 有抓取結果 → 不分 complete / partial / failed 一律照印 ——
      這裡是診斷頁，狀態本身就是要看的資訊（區塊第一行就印 `狀態:`）。
      個基頁維持搬遷前行為（只在 partial 顯示），兩邊的**區塊本體是同一份**。
    """
    fd = st.session_state.get("fund_data")
    if not fd:
        not_ready(
            "尚無抓取紀錄可診斷 —— 先在個基頁分析過一檔基金，這裡才有東西可看",
            where="🔍 個基深掘 → 輸入代碼 → 🚀 分析",
        )
        return
    _status_fd = fd.get("status", "")
    _p_fn = fd.get("fund_name", "") or fd.get("full_key", "")
    render_fetch_diag_section(fd, _status_fd, _p_fn)
