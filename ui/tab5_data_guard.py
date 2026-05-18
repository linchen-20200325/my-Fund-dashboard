"""ui/tab5_data_guard.py — 資料診斷 Tab（v18.125 B-C.3）

從 app.py 抽出 Tab5（資料診斷）的渲染邏輯。

設計準則：
- render_data_guard_tab() -> None **零閉包依賴**（與 Tab4/Tab6 相同）
- 外部 helper 處理：
  * _update_data_registry() → caller (app.py) 在呼叫本函式前先 call
  * _calc_data_health / _parse_indicator_date → 從 ui.helpers.session import
  * _now_tw → 本檔內 lambda 重定義
  * FRED_KEY / GEMINI_KEY → os.environ.get（app.py:_load_keys 已寫到 env）

對外 API:
- render_data_guard_tab() -> None
"""
from __future__ import annotations

import datetime
import os
import time as _time_mod
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from infra.proxy import get_proxy_config
from ui.helpers.session import (
    _D5_KEYS,
    calc_data_health as _calc_data_health_pure,
    parse_indicator_date as _parse_indicator_date,
)

_TW_TZ = ZoneInfo("Asia/Taipei")


def _now_tw():
    return datetime.datetime.now(_TW_TZ)


def _calc_data_health(indicators=None):
    """同 app.py 內 _calc_data_health：indicators=None → 走 session_state。"""
    ind = indicators if indicators is not None else st.session_state.get("indicators", {})
    return _calc_data_health_pure(ind)


def render_data_guard_tab() -> None:
    """渲染資料診斷 Tab — 全域 data_registry / API 延遲 / Phase 4-3B 狀態 /
    NAS Proxy / API Keys / 基金逐筆 / FRED next_release / 資料異常清單。

    Caller 注意：本函式不負責更新 data_registry，呼叫前請先 call
    `_update_data_registry()` 確保 st.session_state.data_registry 為最新。
    """
    # 局部 API key 變數（替代原 module-level FRED_KEY / GEMINI_KEY）
    _FRED_KEY = os.environ.get("FRED_API_KEY", "")
    _GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")

    # v18.128 hotfix: 補回 B-C.3 抽取漏掉的 Section 0 + Section -1 開頭 24 行
    _d5_hdr, _d5_btn = st.columns([3, 1])
    with _d5_hdr:
        st.markdown("## 🔬 資料診斷")
        st.caption("確認所有數據來源是否成功下載，方便排查問題")
    with _d5_btn:
        st.markdown("<div style='margin-top:20px'></div>", unsafe_allow_html=True)
        if st.button("🔄 重新載入總經", key="btn_d5_refresh"):
            st.session_state.macro_done = False
            st.rerun()

    # ── Section -1: 📥 第一手原始資料源總覽 ──
    st.markdown("### 📥 第一手原始資料源總覽")
    st.caption("系統實際下載的所有原始資料端點（依 ARCHITECTURE §5）— 顏色與筆數動態反映 session_state")

    _src_ind  = st.session_state.get("indicators") or {}
    _src_news = st.session_state.get("news_items") or []
    _src_cf   = st.session_state.get("current_fund") or st.session_state.get("fund_data") or {}
    _src_pf   = st.session_state.get("portfolio_funds") or []
    _src_pf_loaded = [f for f in _src_pf if f.get("loaded")]

    # ── Section 0: 全域資料健康總表 ──（caller 端 app.py 已先 call _update_data_registry()）
    _reg = st.session_state.get("data_registry", {})

    _FRED_KEYS = ["NAPM/PMI","DGS10","DGS2","DGS3MO","BAMLH0A0HYM2","M2SL","WALCL",
                  "CPIAUCSL","FEDFUNDS","UNRATE","PPIACO","UMCSENT","ICSA","HSN1F",
                  "SAHMREALTIME","DRTSCILM"]
    _FRED_INTERNAL = ["PMI","YIELD_10Y2Y","YIELD_10Y3M","HY_SPREAD","M2","FED_BS",
                      "CPI","FED_RATE","UNEMPLOYMENT","PPI","SAHM","SLOOS"]
    _YF_KEYS = ["VIX","DXY","ADL","COPPER"]
    _fred_ok = sum(1 for k in _FRED_INTERNAL
                   if (_src_ind.get(k) or {}).get("value") is not None)
    _yf_ok   = sum(1 for k in _YF_KEYS
                   if (_src_ind.get(k) or {}).get("value") is not None)
    _fund_n  = (1 if _src_cf else 0) + len(_src_pf_loaded)
    _nav_n   = sum(1 for f in _src_pf_loaded if f.get("series") is not None) \
               + (1 if _src_cf and (_src_cf.get("series") is not None) else 0)
    _div_n   = sum(1 for f in _src_pf_loaded if (f.get("dividends") or (f.get("moneydj_raw") or {}).get("dividends"))) \
               + (1 if _src_cf and (_src_cf.get("dividends") or _src_cf.get("dividends")) else 0)
    _hold_n  = sum(1 for f in _src_pf_loaded
                   if ((f.get("moneydj_raw") or {}).get("holdings") or {}).get("top_holdings")) \
               + (1 if _src_cf and (_src_cf.get("holdings") or {}).get("top_holdings") else 0)
    _ter_n   = sum(1 for f in _src_pf_loaded
                   if ((f.get("moneydj_raw") or {}).get("holdings") or {}).get("ter")
                   or (f.get("moneydj_raw") or {}).get("ter")) \
               + (1 if _src_cf and ((_src_cf.get("holdings") or {}).get("ter") or _src_cf.get("ter")) else 0)

    def _src_status(used: bool, ok_n: int = 0, total: int | None = None,
                    inactive_label: str = "尚未使用"):
        if used and ok_n > 0:
            tail = f" / {total}" if total else ""
            return ("🟢", f"已抓 {ok_n}{tail}", "#00c853")
        if used:
            return ("🟡", "已呼叫但無資料", "#ff9800")
        return ("⬜", inactive_label, "#666")

    _RAW_TABLE = [
        # (#, 類別, 用途, 端點/Ticker, NAS Proxy, status_tuple)
        ("1️⃣", "FRED API",            "美國總經 14+ 指標",
         "NAPM/DGS10/DGS2/DGS3MO/BAMLH0A0HYM2/M2SL/WALCL/CPIAUCSL/FEDFUNDS/UNRATE/PPIACO/UMCSENT/ICSA/HSN1F/SAHMREALTIME/DRTSCILM",
         "—", _src_status(bool(_src_ind), _fred_ok, len(_FRED_INTERNAL))),
        ("2️⃣", "Yahoo Chart REST",    "市場行情 4 項",
         "^VIX  /  RSP+SPY  /  DX-Y.NYB  /  HG=F",
         "—", _src_status(bool(_src_ind), _yf_ok, len(_YF_KEYS))),
        ("3️⃣", "MoneyDJ wb01/05/07",  "基金績效 / 配息率 / 風險評比 / TER",
         "yp401000.djhtm (wb01)  /  yp405000.djhtm (wb05)  /  yp407000.djhtm (wb07)",
         "✅", _src_status(_fund_n > 0, _fund_n)),
        ("4️⃣", "MoneyDJ NAV 頁",      "每日淨值歷史",
         "tcbbankfund.moneydj.com  /  funddj NAV 頁",
         "✅", _src_status(_nav_n > 0, _nav_n)),
        ("5️⃣", "TDCC openapi",        "境外基金清單 + 最新 NAV",
         "openapi.tdcc.com.tw/v1/opendata/3-1, 3-2, 3-4",
         "—", _src_status(_fund_n > 0, _fund_n,
                          inactive_label="由 fetcher fallback 鏈內部呼叫")),
        ("6️⃣", "Fundclear",            "境內基金搜尋",
         "fundclear.com.tw/investBase/goGetSearchFundList.action",
         "—", _src_status(_fund_n > 0, _fund_n,
                          inactive_label="由 fetcher fallback 鏈內部呼叫")),
        ("7️⃣", "cnyes 鉅亨",           "備援 NAV / 配息",
         "fund.api.cnyes.com/v2/funds/search、/{code}、/{code}/dividend",
         "—", _src_status(_fund_n > 0, _fund_n,
                          inactive_label="由 fetcher fallback 鏈內部呼叫")),
        ("8️⃣", "Allianz / Chubb",      "投資型保單 NAV 端點",
         "allianz / chubb 子網域（_ALLIANZ_NAV_ENDPOINT）",
         "—", _src_status(_fund_n > 0, _fund_n,
                          inactive_label="僅安聯/安達標的觸發")),
        ("9️⃣", "RSS 新聞 (8 來源)",    "國際財經事件",
         "Reuters / MarketWatch / FT / Yahoo / Investing / CNBC × 2",
         "—", _src_status(bool(_src_news), len(_src_news))),
        ("🔟", "yfinance 個股財報",     "三率 QoQ（precision_engine）",
         "yfinance.Ticker(...).quarterly_financials",
         "—", _src_status(False, 0, inactive_label="僅個股查詢觸發")),
    ]

    _src_th = ("font-size:10px;color:#888;font-weight:700;padding:6px 8px;"
               "border-bottom:1px solid #30363d")
    _src_td = "font-size:11px;padding:6px 8px;line-height:1.4"
    _src_html = (
        f"<div style='display:grid;grid-template-columns:38px 1.2fr 1.5fr 3fr 50px 1.4fr;"
        f"background:#0d1117;border-radius:6px 6px 0 0'>"
        f"<span style='{_src_th}'>#</span>"
        f"<span style='{_src_th}'>類別</span>"
        f"<span style='{_src_th}'>用途</span>"
        f"<span style='{_src_th}'>API 端點 / Ticker</span>"
        f"<span style='{_src_th};text-align:center'>Proxy</span>"
        f"<span style='{_src_th}'>連動狀態</span>"
        f"</div>"
    )
    for _no, _cat, _purp, _ep, _proxy, (_ic, _stxt, _sc) in _RAW_TABLE:
        _bg = "#0a1a0a" if _ic == "🟢" else ("#1a1200" if _ic == "🟡" else "#0d1117")
        _src_html += (
            f"<div style='display:grid;grid-template-columns:38px 1.2fr 1.5fr 3fr 50px 1.4fr;"
            f"background:{_bg};border-bottom:1px solid #21262d'>"
            f"<span style='{_src_td};color:#aaa'>{_no}</span>"
            f"<span style='{_src_td};color:#e6edf3;font-weight:600'>{_cat}</span>"
            f"<span style='{_src_td};color:#bbb'>{_purp}</span>"
            f"<span style='{_src_td};color:#7d8590;font-family:monospace;font-size:10px'>{_ep}</span>"
            f"<span style='{_src_td};text-align:center;color:#888'>{_proxy}</span>"
            f"<span style='{_src_td};color:{_sc};font-weight:600'>{_ic} {_stxt}</span>"
            f"</div>"
        )
    st.markdown(
        f"<div style='border:1px solid #30363d;border-radius:6px;overflow:hidden'>"
        f"{_src_html}</div>", unsafe_allow_html=True,
    )

    _src_used  = sum(1 for r in _RAW_TABLE if r[5][0] == "🟢")
    _src_warn  = sum(1 for r in _RAW_TABLE if r[5][0] == "🟡")
    _src_idle  = sum(1 for r in _RAW_TABLE if r[5][0] == "⬜")
    st.caption(
        f"共 10 大類原始資料源｜🟢 已抓取 {_src_used}　🟡 呼叫無回應 {_src_warn}　⬜ 尚未觸發 {_src_idle}　"
        f"｜基金子資料（配息 {_div_n} / 持股 {_hold_n} / TER {_ter_n}）詳見下方總表"
    )
    st.divider()

    st.markdown("### 📋 全域資料健康總表")

    _FREQ_LABEL = {
        "daily":     ("日",    "#42a5f5"),
        "weekly":    ("週",    "#ab47bc"),
        "monthly":   ("月",    "#ff9800"),
        "quarterly": ("季",    "#ef5350"),
        "nav":       ("日NAV", "#42a5f5"),
    }

    if not _reg:
        st.info("尚未載入任何數據。請先於 Tab1 載入總經資料，或於 Tab2/Tab3 載入基金資料。")
    else:
        # ── [v10.3 統一 UI] 三組篩選器（狀態 / 來源 / 頻率）─────────
        _opts_status = sorted({v.get("fresh_icon", "⬜") for v in _reg.values()})
        _opts_source = sorted({v.get("source", "") for v in _reg.values() if v.get("source")})
        _opts_freq   = sorted({v.get("freq", "") for v in _reg.values() if v.get("freq")})
        _flt_c1, _flt_c2, _flt_c3 = st.columns([1, 2, 1])
        with _flt_c1:
            _sel_status = st.multiselect(
                "狀態", _opts_status, default=_opts_status, key="reg_flt_status"
            )
        with _flt_c2:
            _sel_source = st.multiselect(
                "來源", _opts_source, default=_opts_source, key="reg_flt_source"
            )
        with _flt_c3:
            _freq_label_map = {f: _FREQ_LABEL.get(f, (f, "#555"))[0] for f in _opts_freq}
            _sel_freq = st.multiselect(
                "頻率", _opts_freq, default=_opts_freq,
                format_func=lambda f: _freq_label_map.get(f, f),
                key="reg_flt_freq",
            )

        _reg_filtered = {
            k: v for k, v in _reg.items()
            if v.get("fresh_icon", "⬜") in _sel_status
            and (v.get("source", "") in _sel_source or not v.get("source"))
            and (v.get("freq", "") in _sel_freq or not v.get("freq"))
        }

        # 表格標頭
        _th = ("font-size:10px;color:#888;font-weight:700;padding:4px 8px;"
               "border-bottom:1px solid #30363d")
        _td_base = "font-size:11px;padding:4px 8px"
        _hdr = (
            f"<div style='display:grid;grid-template-columns:2fr 1fr 1fr 1fr 3fr 1fr;"
            f"background:#0d1117;border-radius:6px 6px 0 0'>"
            f"<span style='{_th}'>資料名稱</span>"
            f"<span style='{_th}'>來源</span>"
            f"<span style='{_th}'>頻率</span>"
            f"<span style='{_th}'>最新日期</span>"
            f"<span style='{_th}'>新鮮度</span>"
            f"<span style='{_th}'>筆數</span>"
            f"</div>"
        )
        _rows_html = _hdr
        _stale_list = []
        for _rk, _rv in _reg_filtered.items():
            _rn    = _rv.get("count", 0)
            _rd    = _rv.get("latest_date", "N/A")
            _freq  = _rv.get("freq", "monthly")
            _ficon = _rv.get("fresh_icon", "⬜")
            _flbl  = _rv.get("fresh_label", "未知")
            _fcol  = _rv.get("fresh_color", "#555")
            _row_bg = "#161b22" if _ficon == "🟢" else ("#1a1200" if _ficon == "🟡" else "#1a0808")
            _rows_html += (
                f"<div style='display:grid;grid-template-columns:2fr 1fr 1fr 1fr 3fr 1fr;"
                f"background:{_row_bg};border-bottom:1px solid #21262d'>"
                f"<span style='{_td_base};color:#e6edf3'>{_rv.get('label', _rk)}</span>"
                f"<span style='{_td_base};color:#888'>{_rv.get('source','')}</span>"
                f"<span style='{_td_base}'>"
                f"<span style='background:{_FREQ_LABEL.get(_freq,('?','#555'))[1]}22;"
                f"color:{_FREQ_LABEL.get(_freq,('?','#555'))[1]};"
                f"border:1px solid {_FREQ_LABEL.get(_freq,('?','#555'))[1]};"
                f"border-radius:10px;padding:1px 7px;font-size:10px;font-weight:700'>"
                f"{_FREQ_LABEL.get(_freq,(_freq,'#555'))[0]}</span></span>"
                f"<span style='{_td_base};color:#aaa'>{_rd}</span>"
                f"<span style='{_td_base};color:{_fcol};font-weight:600'>{_ficon} {_flbl}</span>"
                f"<span style='{_td_base};color:#aaa'>{_rn}</span>"
                f"</div>"
            )
            if _ficon == "🔴":
                _stale_list.append(_rv.get("label", _rk))
        st.markdown(
            f"<div style='border:1px solid #30363d;border-radius:6px;overflow:hidden'>"
            f"{_rows_html}</div>",
            unsafe_allow_html=True,
        )
        _reg_total = len(_reg)
        _reg_shown = len(_reg_filtered)
        _reg_green = sum(1 for v in _reg.values() if v.get("fresh_icon") == "🟢")
        _reg_yellow = sum(1 for v in _reg.values() if v.get("fresh_icon") == "🟡")
        _reg_red   = sum(1 for v in _reg.values() if v.get("fresh_icon") == "🔴")
        _filter_tag = "" if _reg_shown == _reg_total else f"（已篩選：顯示 {_reg_shown}/{_reg_total}）"
        st.caption(
            f"共 {_reg_total} 個資料源{_filter_tag}｜🟢 最新 {_reg_green}　🟡 延遲 {_reg_yellow}　"
            f"🔴 過舊 {_reg_red}　| 自動掃描 session_state，無寫死標的"
        )
        # 過舊清單以全集合計算（不受篩選影響），避免使用者篩掉狀態後漏看
        _all_stale = [v.get("label", k) for k, v in _reg.items() if v.get("fresh_icon") == "🔴"]
        if _all_stale:
            st.warning(f"🔴 **過舊資料（建議重新抓取）**：{', '.join(_all_stale)}")

        # Snapshot Viewer
        with st.expander("🔍 資料抽查快照 (Snapshot Viewer)", expanded=False):
            _snap_keys = [k for k, v in _reg.items() if v.get("series") is not None and v.get("count", 0) > 0]
            if _snap_keys:
                _snap_sel = st.selectbox(
                    "選擇資料源查看原始資料（head 5，降冪排序）",
                    _snap_keys,
                    key="reg_snap_sel",
                )
                if _snap_sel:
                    _snap_s  = _reg[_snap_sel]["series"]
                    _snap_fq = _FREQ_LABEL.get(_reg[_snap_sel].get("freq",""), "")
                    try:
                        _snap_df = pd.DataFrame({
                            "日期":  _snap_s.index.astype(str),
                            "數值":  _snap_s.values,
                        }).head(5)
                        st.dataframe(_snap_df, use_container_width=True, hide_index=True)
                        st.caption(
                            f"資料鍵值：{_snap_sel}　頻率：{_snap_fq}　｜　"
                            f"共 {len(_snap_s)} 筆（已依時間降冪排序，顯示最新 5 筆）"
                        )
                    except Exception as _snap_e:
                        st.error(f"無法顯示快照：{_snap_e}")
            else:
                st.info("尚無含時間序列的資料可抽查。")

    st.divider()

    # ── Section 1: PMI fallback 失敗警告（v18.144 移除熱力圖區塊）─
    # ⚠️ v18.144：移除「資料完整度熱力圖」+「三色燈號」+「_D5_EXPECTED 規格表」
    #            — 資料診斷統一改走下方「⚠️ 資料異常清單」單一管道，
    #            消除熱力圖 schema warning 與 異常清單 freshness 訊號錯位。
    # ⚠️ v16.5：移除原「總經指標 (FRED/yfinance) 數值表」+「完整率進度條」等。
    _d5_ind = st.session_state.get("indicators", {})

    if _d5_ind and not _d5_ind.get("PMI"):
        st.info(
            "ℹ️ **PMI** 三層 fallback 全失敗：\n"
            "1. ISM NAPM → 2. ISM ISPMANPMI → 3. Phil Fed 擴散指數轉換\n\n"
            "可能原因：FRED API Key 失效 / NAS Proxy 中斷 / 三項皆當日斷線。"
            "領先指標部分仍可參考 Tab1 的 **CFNAI** 或 **LEI** 指標卡。"
        )

    # ── 資料完整度熱力圖：v18.144 已移除，改由下方「⚠️ 資料異常清單」承擔診斷職責 ──

    # ── Section 1b: API 延遲趨勢圖（Core Protocol v2.0 Ch.1）────────
    with st.expander("📡 API 連線延遲趨勢（近24次）", expanded=False):
        import requests as _req_lat
        # 手動測速按鈕
        if st.button("🕐 立即測試三源連線速度", key="btn_d5_ping"):
            _proxy = get_proxy_config() or {}
            _kw    = dict(proxies=_proxy, timeout=8, verify=False,
                          headers={"User-Agent": "Mozilla/5.0"})
            _ping_results: dict = {}
            for _src, _url in [
                ("FRED",     "https://fred.stlouisfed.org/"),
                ("MoneyDJ",  "https://www.moneydj.com/"),
                ("Yahoo/yf", "https://finance.yahoo.com/"),
            ]:
                try:
                    _t0p = _time_mod.time()
                    _req_lat.get(_url, **_kw)
                    _ping_results[_src] = round((_time_mod.time() - _t0p) * 1000)
                except Exception as _pe:
                    _ping_results[_src] = None  # 無法連線
            _lat_log_p = st.session_state.get("api_latency_log", [])
            _lat_log_p.append({
                "label":      _now_tw().strftime("%H:%M"),
                "macro_ms":   _ping_results.get("FRED"),
                "moneydj_ms": _ping_results.get("MoneyDJ"),
                "yf_ms":      _ping_results.get("Yahoo/yf"),
            })
            st.session_state["api_latency_log"] = _lat_log_p[-24:]
            # 即時顯示結果
            _pcols = st.columns(3)
            for _ci, (_sn, _ms) in enumerate(_ping_results.items()):
                _col_c = "#00c853" if (_ms and _ms < 1000) else ("#ff9800" if (_ms and _ms < 3000) else "#f44336")
                _pcols[_ci].markdown(
                    f"<div style='background:#1a1f2e;border-radius:8px;padding:10px;text-align:center'>"
                    f"<div style='font-size:11px;color:#888'>{_sn}</div>"
                    f"<div style='font-size:20px;font-weight:700;color:{_col_c}'>"
                    f"{'N/A' if _ms is None else f'{_ms} ms'}</div></div>",
                    unsafe_allow_html=True)

        # 延遲折線圖
        _lat_hist = st.session_state.get("api_latency_log", [])
        if len(_lat_hist) >= 2:
            _lh_x    = [r.get("label","") for r in _lat_hist]
            _lh_fred = [r.get("macro_ms")   for r in _lat_hist]
            _lh_mj   = [r.get("moneydj_ms") for r in _lat_hist]
            _lh_yf   = [r.get("yf_ms")      for r in _lat_hist]
            _fig_lat  = go.Figure()
            for _lt_name, _lt_y, _lt_color in [
                ("FRED/yfinance(載入)", _lh_fred, "#64b5f6"),
                ("MoneyDJ(測速)",       _lh_mj,   "#ff9800"),
                ("Yahoo/yf(測速)",      _lh_yf,   "#ce93d8"),
            ]:
                if any(v is not None for v in _lt_y):
                    _fig_lat.add_trace(go.Scatter(
                        x=_lh_x, y=_lt_y, name=_lt_name, mode="lines+markers",
                        line=dict(color=_lt_color, width=1.8),
                        marker=dict(size=5),
                        connectgaps=True,
                        hovertemplate="%{y} ms<extra>" + _lt_name + "</extra>"))
            # 警戒線：1000ms 黃 / 3000ms 紅
            _fig_lat.add_hline(y=1000, line_color="#ff9800", line_dash="dot",
                               line_width=1, annotation_text="1s 警示",
                               annotation_font_color="#ff9800",
                               annotation_position="bottom right")
            _fig_lat.add_hline(y=3000, line_color="#f44336", line_dash="dash",
                               line_width=1, annotation_text="3s 警戒",
                               annotation_font_color="#f44336",
                               annotation_position="bottom right")
            _fig_lat.update_layout(
                paper_bgcolor="#0e1117", plot_bgcolor="#161b22",
                font_color="#e6edf3", height=260,
                margin=dict(t=10, b=40, l=60, r=20),
                xaxis=dict(tickangle=-30, tickfont_size=9, gridcolor="#1e2a3a"),
                yaxis=dict(title="回應時間 (ms)", gridcolor="#1e2a3a"),
                legend=dict(orientation="h", font_size=10, y=1.05),
                hovermode="x unified")
            st.plotly_chart(_fig_lat, use_container_width=True)
        else:
            st.info("尚無延遲記錄。點擊「立即測試」或先於 Tab1 載入總經資料，系統將自動記錄 FRED/yfinance 回應時間。")

    st.divider()

    # ── v18.118 issue 4: Phase 4 / Phase 3-B 計算狀態監控 ──────────
    with st.expander("📊 Phase 4 變數重要性 / Phase 3-B 燈號回測 — 計算可用性", expanded=False):
        _d5_ind = st.session_state.get("indicators") or {}
        if not _d5_ind:
            st.info("尚未載入總經指標（請先至 Tab1 點「📡 載入總經資料」），無法檢測 Phase 4 / 3-B 狀態。")
        else:
            # ── A. 每個 target 候選 series 可用性 ──────────────────
            st.markdown("**A. Phase 4 變數重要性 target series 檢測**")
            _d5_p4_targets = ["LEI", "PMI", "CONSUMER_CONF", "PERMIT_HOUSING", "VIX"]
            _d5_p4_rows = []
            for _t in _d5_p4_targets:
                _iv = _d5_ind.get(_t) or {}
                _s  = _iv.get("series")
                _n  = (len(_s) if _s is not None and hasattr(_s, "__len__") else 0)
                _ok = (_n >= 27)   # min_overlap=24 + lag=3
                _d5_p4_rows.append({
                    "target": _t,
                    "series 長度": _n,
                    "Phase 4 (≥27)": "✅" if _ok else "❌",
                    "value": _iv.get("value", "—"),
                    "source": _iv.get("source", "—") if _t == "PMI" else "—",
                })
            st.dataframe(pd.DataFrame(_d5_p4_rows), use_container_width=True, hide_index=True)

            # ── B. Phase 3-B 7 子領域樣本量 ────────────────────────
            st.markdown("**B. Phase 3-B 7 子領域燈號回測樣本量**")
            try:
                from services.macro_service import backtest_sub_cycle_lights as _d5_bt
                _d5_bt_out = _d5_bt(_d5_ind, target_key="LEI", window=60, forward_months=3)
                _d5_bt_rows = []
                for c in _d5_bt_out:
                    _d5_bt_rows.append({
                        "子領域": f"{c['icon']} {c['name']}",
                        "n_obs": c["n_obs"],
                        "🟢 綠燈": c["n_green"],
                        "🟡 黃燈": c["n_yellow"],
                        "🟠 橙燈": c["n_orange"],
                        "🔴 紅燈": c["n_red"],
                        "狀態": "✅ 有結論" if c["n_obs"] > 0 else "❌ 資料不足",
                    })
                st.dataframe(pd.DataFrame(_d5_bt_rows), use_container_width=True, hide_index=True)
                _d5_ok_count = sum(1 for c in _d5_bt_out if c["n_obs"] > 0)
                st.caption(
                    f"⚙️ Phase 3-B 設計：window=60 月 expanding，需子領域內**至少 1 個指標** "
                    f"series 月頻 ≥ 60 期才有結論。目前 {_d5_ok_count}/7 子領域有結論。"
                )
            except Exception as _e_d5_bt:
                st.caption(f"⚠️ Phase 3-B 狀態檢測失敗：{str(_e_d5_bt)[:80]}")

            # ── C. PMI 源診斷（issue 3 修復後的可觀測性） ─────────
            st.markdown("**C. PMI 來源診斷**")
            _d5_pmi = _d5_ind.get("PMI") or {}
            _d5_pmi_src = _d5_pmi.get("source", "?")
            _d5_pmi_lbl = _d5_pmi.get("label", "?")
            _d5_pmi_proxy = _d5_pmi.get("is_proxy", False)
            _d5_pmi_s = _d5_pmi.get("series")
            _d5_pmi_n = len(_d5_pmi_s) if _d5_pmi_s is not None and hasattr(_d5_pmi_s, "__len__") else 0
            st.caption(
                f"來源：**{_d5_pmi_src}**（{_d5_pmi_lbl}）"
                f"｜value={_d5_pmi.get('value', '—')}"
                f"｜series 長度={_d5_pmi_n}"
                f"｜{'⚠️ proxy 源' if _d5_pmi_proxy else '✅ 原生源'}"
            )
            if _d5_pmi_n == 0:
                st.warning(
                    "⚠️ PMI series 為空 — v18.118 修復前是常見狀況（HTML 來源只回 value 不回歷史）。"
                    "若仍出現代表 FRED ISPMANPMI 補救路徑也失敗，需檢查 FRED_API_KEY。"
                )

    st.divider()

    # ── v18.120 issue 4: NAS Proxy 狀態檢測 ───────────────────────
    st.markdown("### 🌐 NAS Proxy 中繼站狀態")
    try:
        from infra.proxy import get_proxy_config as _gpc_d5
        _d5_pxy = _gpc_d5()
        if _d5_pxy:
            _d5_pxy_url = _d5_pxy.get("https", "—")
            import re as _re_d5_pxy
            _d5_pxy_safe = _re_d5_pxy.sub(
                r"//[^:]+:[^@]+@", "//****:****@", _d5_pxy_url)
            _d5_c1, _d5_c2 = st.columns([1, 3])
            with _d5_c1:
                st.markdown("**狀態**：🟢 已啟用")
            with _d5_c2:
                st.code(_d5_pxy_safe, language=None)
            st.caption(
                "✅ 所有 requests.get + urllib.urlopen 已透過 NAS Proxy 中繼。"
                "若仍下載失敗，可能是 NAS 連線到 MoneyDJ 也被封，或 NAS 本身斷線。"
            )
            # 連線測試按鈕
            if st.button("🧪 立即測 NAS Proxy 連線", key="btn_d5_proxy_test"):
                _d5_test_url = "https://www.moneydj.com/funddj/yp/yp010001.djhtm?a=TLZF9"
                with st.spinner(f"透過 NAS 中繼 GET {_d5_test_url[:60]}..."):
                    import time as _t_d5
                    _t0 = _t_d5.time()
                    try:
                        from infra.proxy import fetch_url as _fu_d5
                        _r = _fu_d5(_d5_test_url, timeout=15)
                        _ms = round((_t_d5.time() - _t0) * 1000)
                        if _r is not None and _r.status_code == 200:
                            _size = len(_r.text or "") if hasattr(_r, "text") else 0
                            st.success(
                                f"✅ NAS 連線成功 ({_ms}ms) — 回應 {_size:,} bytes "
                                f"(HTTP {_r.status_code})"
                            )
                        else:
                            st.error(
                                f"❌ NAS 連線失敗 ({_ms}ms) — "
                                f"{'HTTP ' + str(_r.status_code) if _r is not None else '無回應 (407/403/timeout)'}"
                            )
                    except Exception as _e_d5_test:
                        _ms = round((_t_d5.time() - _t0) * 1000)
                        st.error(
                            f"❌ NAS 連線異常 ({_ms}ms)：{type(_e_d5_test).__name__}: "
                            f"{str(_e_d5_test)[:120]}"
                        )
        else:
            st.warning(
                "🔴 **NAS Proxy 未設定** — 走直連模式。\n\n"
                "Streamlit Cloud IP 經常被 MoneyDJ 封鎖 → "
                "建議至 Streamlit Cloud secrets 加：\n\n"
                "```toml\nPROXY_URL = \"http://user:pwd@your-nas-host:3128\"\n```"
            )
    except Exception as _e_d5_pxy:
        st.error(f"⚠️ 讀取 Proxy 設定失敗：{type(_e_d5_pxy).__name__}: {str(_e_d5_pxy)[:80]}")

    st.divider()

    # ── Section 2: API Key 狀態 ───────────────────────────────────
    st.markdown("### 🔑 API 金鑰狀態")
    _d5_k1, _d5_k2 = st.columns(2)
    with _d5_k1:
        _d5_fred_ok = bool(_FRED_KEY)
        st.markdown(
            f"<div style='background:#1a1f2e;border-radius:8px;padding:12px'>"
            f"<div style='font-size:11px;color:#888'>FRED API Key</div>"
            f"<div style='font-size:16px;font-weight:700;"
            f"color:{'#00c853' if _d5_fred_ok else '#f44336'}'>"
            f"{'✅ 已設定' if _d5_fred_ok else '❌ 未填寫'}</div>"
            f"<div style='font-size:10px;color:#555'>"
            f"{'...' + _FRED_KEY[-6:] if _d5_fred_ok and len(_FRED_KEY) > 6 else '請在 secrets.toml 填入'}"
            f"</div></div>", unsafe_allow_html=True)
    with _d5_k2:
        _d5_gem_ok = bool(_GEMINI_KEY)
        st.markdown(
            f"<div style='background:#1a1f2e;border-radius:8px;padding:12px'>"
            f"<div style='font-size:11px;color:#888'>Gemini API Key</div>"
            f"<div style='font-size:16px;font-weight:700;"
            f"color:{'#00c853' if _d5_gem_ok else '#f44336'}'>"
            f"{'✅ 已設定' if _d5_gem_ok else '❌ 未填寫'}</div>"
            f"<div style='font-size:10px;color:#555'>"
            f"{'...' + _GEMINI_KEY[-6:] if _d5_gem_ok and len(_GEMINI_KEY) > 6 else '請在 secrets.toml 填入'}"
            f"</div></div>", unsafe_allow_html=True)

    st.divider()

    # ── Section 3: 基金逐筆診斷 ───────────────────────────────────
    st.markdown("### 📊 基金資料診斷")
    _d5_pf   = st.session_state.get("portfolio_funds", []) or []
    # v17.3：單一基金 Tab 寫入 fund_data，組合基金寫入 current_fund，兩者都要讀
    _d5_cf   = st.session_state.get("current_fund") or st.session_state.get("fund_data")

    # 合併組合基金 + 個別基金（去重）
    # v18.83: portfolio_funds 同 code 跨多保單會有多筆 entry（pid 不同但 NAV/配息一致），
    #         Tab5 是「資料診斷」性質（看抓取狀態），同 code 列多次純粹重複沒意義；
    #         按 code dedup 只保留第一筆，配上「N 保單共用」備註。
    _d5_seen: dict = {}
    _d5_dup_count: dict = {}
    for _ff in _d5_pf:
        _cd = str(_ff.get("code", "")).strip()
        if not _cd:
            continue
        if _cd not in _d5_seen:
            _d5_seen[_cd] = _ff
            _d5_dup_count[_cd] = 1
        else:
            _d5_dup_count[_cd] += 1
    _d5_list = list(_d5_seen.values())
    if _d5_cf:
        _d5_cf_code = _d5_cf.get("fund_code", "") or _d5_cf.get("full_key", "")
        if _d5_cf_code and _d5_cf_code not in _d5_seen:
            # v18.18: 對齊 portfolio_funds schema — moneydj_raw 取「內層巢狀」而非整包。
            _d5_list.append({
                "code": _d5_cf_code,
                "name": _d5_cf.get("fund_name", "") or _d5_cf_code,
                "loaded": True,
                "metrics": _d5_cf.get("metrics", {}),
                "moneydj_raw": _d5_cf.get("moneydj_raw", {}) or {},
                "dividends": _d5_cf.get("dividends", []),
                "series": _d5_cf.get("series"),
                "_source": "個別基金分析",
            })
            _d5_dup_count[_d5_cf_code] = 1

    _d5_dup_total = sum(_d5_dup_count.values()) - len(_d5_list)
    if _d5_dup_total > 0:
        st.caption(
            f"ℹ️ 已自動去重：{len(_d5_pf)} 筆 entry → **{len(_d5_list)} 個 unique code**"
            f"（移除 {_d5_dup_total} 筆同 code 跨保單重複，資料診斷以 code 為單位）"
        )

    if not _d5_list:
        st.info("尚未載入任何基金。請至「單一基金」或「組合基金」Tab 載入後再查看。")
    else:
        def _d5_cell(col, label, value, ok_cond=True, fmt=None):
            """v16.5：只顯示『資料是否取得』，不顯示具體數值（現況）。
            v18.53: value == "N/A" 視為「不適用」（如累積型基金無配息）顯灰色 ℹ️ 不視為缺失。
            符合「資料診斷 = 確認資料是否遺漏或過期」本意。fmt 參數保留兼容。
            """
            _empty = (value is None or value == "" or
                      (isinstance(value, (dict, list)) and not value))
            if value == "N/A":
                _ic, _vc, _vs = "ℹ️", "#888888", "N/A 不適用"
            elif _empty:
                _ic, _vc, _vs = "⚠️", "#ff9800", "缺失"
            elif not bool(ok_cond):
                _ic, _vc, _vs = "⚠️", "#ff9800", "資料不足"
            else:
                _ic, _vc, _vs = "✅", "#00c853", "已取得"
            col.markdown(
                f"<div style='background:#1a1f2e;border-radius:6px;padding:6px 8px'>"
                f"<div style='font-size:10px;color:#888'>{label}</div>"
                f"<div style='font-size:13px;color:{_vc};font-weight:700'>{_ic} {_vs}</div>"
                f"</div>", unsafe_allow_html=True)

        for _d5_fd in _d5_list:
            _d5_code  = _d5_fd.get("code", "?")
            _d5_fname = _d5_fd.get("name", "") or _d5_code
            _d5_mj    = _d5_fd.get("moneydj_raw", {}) or {}
            _d5_m     = _d5_fd.get("metrics", {}) or {}
            _d5_err   = _d5_fd.get("error", "") or _d5_mj.get("error", "")
            _d5_nav   = _d5_m.get("nav") or _d5_mj.get("nav")
            _d5_adr   = _d5_mj.get("moneydj_div_yield") or _d5_m.get("annual_div_rate")
            _d5_perf  = _d5_mj.get("perf", {}) or {}
            _d5_risk  = (_d5_mj.get("risk_metrics", {}) or {})
            _d5_r1y   = (_d5_risk.get("risk_table") or {}).get("一年", {}) or {}
            _d5_divs  = _d5_fd.get("dividends") or _d5_mj.get("dividends") or []
            _d5_divs  = _d5_divs if isinstance(_d5_divs, list) else []
            _d5_hold  = (_d5_mj.get("holdings") or {})
            _d5_sects = _d5_hold.get("sector_alloc", []) or []
            _d5_tops  = _d5_hold.get("top_holdings", []) or []

            _d5_raw_s = _d5_fd.get("series")
            if _d5_raw_s is None:
                _d5_raw_s = _d5_mj.get("series")
            try:
                import pandas as _pd_d5
                _d5_slen = len(_d5_raw_s) if isinstance(_d5_raw_s, _pd_d5.Series) else 0
            except Exception:
                _d5_slen = 0

            _d5_ok_icon = "✅" if _d5_fd.get("loaded") and not _d5_err else ("❌" if _d5_err else "⬜")
            # v18.53: 偵測累積型 / 不配息基金 — 名稱含「累積」「智慧」「Accumulation」
            # 或 MoneyDJ dividend_freq 明示「不配息」，diagnostic 顯「N/A 不配息」而非「缺失」
            _d5_acc_keywords = ("累積", "Accumulation", "Accum", "智慧", "智能")
            _d5_div_freq_raw = str(_d5_mj.get("dividend_freq", "") or "")
            _d5_is_accum = (
                any(k in _d5_fname for k in _d5_acc_keywords)
                or "不配息" in _d5_div_freq_raw
                or "累積" in _d5_div_freq_raw
            )

            _d5_dup_n = _d5_dup_count.get(_d5_code, 1)
            _d5_dup_tag = f"  ·  共 {_d5_dup_n} 保單共用" if _d5_dup_n > 1 else ""
            with st.expander(f"{_d5_ok_icon} {_d5_fname[:35]} ({_d5_code}){_d5_dup_tag}",
                             expanded=bool(_d5_err)):
                if _d5_is_accum:
                    st.caption("ℹ️ 此基金為**累積型 / 不配息**：年化配息率與配息記錄欄位 N/A 為正常現象")
                # Row 1: NAV / 配息率 / 1Y報酬 / 淨值筆數
                _r1 = st.columns(4)
                _d5_cell(_r1[0], "最新淨值 NAV",   _d5_nav,
                         ok_cond=(_d5_nav is not None and float(_d5_nav or 0) > 0),
                         fmt=lambda v: f"{float(v):.4f}")
                # 配息率：累積型 → 標 N/A 不配息 用佔位避免 cell empty
                _d5_cell(_r1[1], "年化配息率",
                         _d5_adr if not _d5_is_accum else "N/A",
                         ok_cond=(_d5_is_accum or (_d5_adr is not None and float(_d5_adr or 0) > 0)),
                         fmt=lambda v: f"{float(v):.2f}%")
                # v18.55: 1Y含息報酬 fallback 鏈 — 救已快取 session_state（pre-v18.53）
                # perf["1Y"] (wb01 / local_calc 注入) → metrics.ret_1y_total (本地計算原值)
                # v18.57: 加來源標籤，讓使用者一眼看出資料來自哪邊
                _d5_perf_1y = _d5_perf.get("1Y")
                _d5_perf_src_raw = str(_d5_mj.get("perf_source", "") or "").lower()
                _d5_perf_label = "1Y含息報酬"
                if _d5_perf_1y is not None:
                    # perf["1Y"] 已有值 — 來自 wb01（境外）或 local_calc（境內 v18.53+）
                    _d5_perf_label = (
                        "1Y含息報酬 [wb01]" if _d5_perf_src_raw == "wb01"
                        else ("1Y含息報酬 [本地]" if _d5_perf_src_raw == "local_calc"
                              else "1Y含息報酬")
                    )
                else:
                    # perf["1Y"] 缺 → 看 metrics.ret_1y_total（v18.55 cache 救援路徑）
                    _d5_perf_1y = _d5_m.get("ret_1y_total")
                    if _d5_perf_1y is not None:
                        _d5_perf_label = "1Y含息報酬 [本地·cache]"
                _d5_cell(_r1[2], _d5_perf_label,    _d5_perf_1y,
                         ok_cond=(_d5_perf_1y is not None),
                         fmt=lambda v: f"{v:.2f}%")
                _d5_cell(_r1[3], "淨值歷史筆數",    _d5_slen if _d5_slen > 0 else None,
                         ok_cond=(_d5_slen >= 30),
                         fmt=lambda v: f"{v} 筆")
                st.markdown("<div style='margin:4px 0'></div>", unsafe_allow_html=True)
                # Row 2: 配息筆數 / 標準差 / Sharpe / MoneyDJ wb01
                _r2 = st.columns(4)
                _d5_cell(_r2[0], "配息記錄筆數",
                         (len(_d5_divs) if _d5_divs else ("N/A" if _d5_is_accum else None)),
                         ok_cond=(_d5_is_accum or len(_d5_divs) >= 1),
                         fmt=lambda v: f"{v} 筆")
                _d5_cell(_r2[1], "標準差(1Y)",      _d5_r1y.get("標準差"),
                         ok_cond=(_d5_r1y.get("標準差") is not None),
                         fmt=lambda v: f"{v}%")
                _d5_cell(_r2[2], "Sharpe(1Y)",      _d5_r1y.get("Sharpe"),
                         ok_cond=(_d5_r1y.get("Sharpe") is not None),
                         fmt=lambda v: str(v))
                # wb01報酬資料 = 嚴格 perf["1Y"]（不含 local_calc fallback），呈現 MoneyDJ 原始來源
                _d5_cell(_r2[3], "wb01報酬資料",    _d5_perf.get("1Y"),
                         ok_cond=(_d5_perf.get("1Y") is not None),
                         fmt=lambda v: "已取得 ✓")
                st.markdown("<div style='margin:4px 0'></div>", unsafe_allow_html=True)
                # Row 3: holdings
                _r3 = st.columns(4)
                _d5_cell(_r3[0], "holdings物件",    _d5_hold or None,
                         ok_cond=bool(_d5_hold),
                         fmt=lambda v: "有資料 ✓")
                _d5_cell(_r3[1], "產業配置筆數",    len(_d5_sects) if _d5_sects else None,
                         ok_cond=(len(_d5_sects) >= 3),
                         fmt=lambda v: f"{v} 項")
                _d5_cell(_r3[2], "前10大持股",      len(_d5_tops) if _d5_tops else None,
                         ok_cond=(len(_d5_tops) >= 5),
                         fmt=lambda v: f"{v} 檔")
                # v18.19: 基本資料以 fallback chain 判定—任一欄有值即視為有取得
                # （部分 MoneyDJ 頁面只列「基金類型 / 投資區域」而無「投資標的」列）
                _d5_basic = (_d5_mj.get("investment_target")
                             or _d5_mj.get("category")
                             or _d5_mj.get("fund_type")
                             or _d5_mj.get("fund_region"))
                _d5_cell(_r3[3], "基本資料",        _d5_basic,
                         ok_cond=bool(_d5_basic),
                         fmt=lambda v: "已取得 ✓")

                st.markdown(
                    f"<span style='font-size:10px;color:#555'>"
                    f"來源：{_d5_fd.get('_source','投資組合')} | "
                    f"is_core: {_d5_fd.get('is_core','?')} | "
                    f"currency: {_d5_fd.get('currency', _d5_mj.get('currency','?'))}"
                    f"</span>", unsafe_allow_html=True)
                if _d5_err:
                    st.error(f"❌ 錯誤：{str(_d5_err)[:200]}")

    # ══════════════════════════════════════════════════════
    # 🔬 FRED next_release 診斷（v18.4 新增）
    # ══════════════════════════════════════════════════════
    st.divider()
    with st.expander("🔬 FRED next_release_date 診斷（排查月度/季度誤標 STALE）",
                     expanded=False):
        st.caption(
            "對映射到 FRED 的指標各打一次 `series/release` + `release/dates` API，"
            "列出取得的下次 release 日。**None = API 失敗 / 該 series 無未來 release 資料**，"
            "此時 `_freshness()` 會自動 fallback 到舊天數閾值。"
        )
        try:
            from repositories.macro_repository import fred_get_next_release_date as _diag_next_rel
            _diag_key = (st.secrets.get("FRED_API_KEY","")
                         or os.environ.get("FRED_API_KEY",""))
            if not _diag_key:
                st.warning("⚠️ FRED_API_KEY 未設置 → 全部會 fallback")
            _diag_targets = [
                ("CPI", "CPIAUCSL", "monthly"),
                ("PMI / NAPM", "NAPM", "monthly"),
                ("UNRATE", "UNRATE", "monthly"),
                ("CFNAI 領先指標 (LEI)", "CFNAI", "monthly"),
                ("HSN1F", "HSN1F", "monthly"),
                ("PERMIT", "PERMIT", "monthly"),
                ("UMCSENT", "UMCSENT", "monthly"),
                ("M2SL", "M2SL", "monthly"),
                ("CCSA 持續失業金", "CCSA", "weekly"),
                ("ICSA 初領失業金", "ICSA", "weekly"),
                ("T10Y3M 殖利率利差", "T10Y3M", "daily"),
                ("FEDFUNDS", "FEDFUNDS", "monthly"),
                ("DRTSCILM SLOOS", "DRTSCILM", "quarterly"),
            ]
            if st.button("🔍 立即診斷（會打 API，30 天 cache）", key="btn_fred_diag"):
                _diag_rows = []
                _today = datetime.date.today()
                for _label, _sid, _freq in _diag_targets:
                    _nrd = _diag_next_rel(_sid, _diag_key) if _diag_key else None
                    if _nrd is None:
                        _diag_rows.append({
                            "指標": _label, "series_id": _sid, "頻率": _freq,
                            "next_release": "❌ None (API 失敗 / 無資料)",
                            "距今": "—",
                        })
                    else:
                        _delta = (_nrd - _today).days
                        _status = ("🟢 未到" if _delta > 0
                                   else "🟡 已到 +5d 內" if _delta >= -5
                                   else "🔴 真延遲")
                        _diag_rows.append({
                            "指標": _label, "series_id": _sid, "頻率": _freq,
                            "next_release": f"{_nrd.isoformat()} ({_status})",
                            "距今": f"{_delta:+d} 天",
                        })
                st.dataframe(pd.DataFrame(_diag_rows),
                             use_container_width=True, hide_index=True)
                st.caption(
                    "💡 若某指標長期 None，可能：(1) FRED 未收錄該 series 的 release schedule "
                    "(2) proxy 連線有問題 (3) series_id 拼錯。對應修正：(1) 改 fallback 閾值 "
                    "(2) 修 NAS proxy (3) 對齊 _FRED_SERIES_MAP 條目。"
                )
        except Exception as _e_diag:
            st.error(f"❌ 診斷模組載入失敗：{_e_diag}")

    # ══════════════════════════════════════════════════════
    # ⚠️ 資料異常清單（最下方一覽，獨立於上方總表/體檢區）
    # ══════════════════════════════════════════════════════
    st.divider()
    st.markdown("### ⚠️ 資料異常清單")
    st.caption(
        "💡 v18.3 起：月度 / 季度指標的 stale 判斷改依 **FRED `next_release_date`** 動態計算，"
        "today < next_release → 🟢；release 期已到 +5 天內 → 🟡（屬於正常 release window）；"
        "超過 +5 天 → 🔴（真延遲）。FRED API 失敗才回退舊閾值。"
    )
    _anom_reg = st.session_state.get("data_registry", {})
    # 🟡 含 (a) 真延遲 (b) FRED release 期已到 +5d 內，第二類不應視為異常
    _anom_items = [(k, v) for k, v in _anom_reg.items()
                   if v.get("fresh_icon") == "🔴"
                   or (v.get("fresh_icon") == "🟡"
                       and "release 期已到" not in (v.get("fresh_label") or ""))]
    _anom_items.sort(key=lambda kv: (
        0 if kv[1].get("fresh_icon") == "🔴" else 1,
        kv[1].get("label", kv[0]),
    ))
    if not _anom_items:
        st.success("✅ 全數資料源狀態正常（🟢 最新 + 🟡 release window 內）")
    else:
        _anom_red = sum(1 for _, v in _anom_items if v.get("fresh_icon") == "🔴")
        _anom_yel = sum(1 for _, v in _anom_items if v.get("fresh_icon") == "🟡")
        st.caption(
            f"共 {len(_anom_items)} 筆異常　｜　🔴 真延遲 {_anom_red}　🟡 其他延遲 {_anom_yel}"
            f"　｜　依嚴重度排序（release window 內的 🟡 已自動排除）"
        )
        _th_a = ("font-size:10px;color:#888;font-weight:700;padding:4px 8px;"
                 "border-bottom:1px solid #30363d")
        _td_a = "font-size:11px;padding:4px 8px"
        _hdr_a = (
            f"<div style='display:grid;grid-template-columns:2.4fr 1.4fr 0.8fr 1.2fr 1.6fr;"
            f"background:#0d1117;border-radius:6px 6px 0 0'>"
            f"<span style='{_th_a}'>資料名稱</span>"
            f"<span style='{_th_a}'>來源</span>"
            f"<span style='{_th_a}'>頻率</span>"
            f"<span style='{_th_a}'>最新日期</span>"
            f"<span style='{_th_a}'>狀態</span>"
            f"</div>"
        )
        _rows_a = _hdr_a
        for _ak, _av in _anom_items:
            _aicon = _av.get("fresh_icon", "⬜")
            _albl  = _av.get("fresh_label", "未知")
            _acol  = _av.get("fresh_color", "#999")
            _afreq = _av.get("freq", "")
            _afq_lbl, _afq_col = _FREQ_LABEL.get(_afreq, (_afreq or "—", "#555"))
            _abg = "#1a0808" if _aicon == "🔴" else "#1a1200"
            _rows_a += (
                f"<div style='display:grid;grid-template-columns:2.4fr 1.4fr 0.8fr 1.2fr 1.6fr;"
                f"background:{_abg};border-bottom:1px solid #21262d'>"
                f"<span style='{_td_a};color:#e6edf3'>{_av.get('label', _ak)}</span>"
                f"<span style='{_td_a};color:#888'>{_av.get('source','—') or '—'}</span>"
                f"<span style='{_td_a}'>"
                f"<span style='background:{_afq_col}22;color:{_afq_col};"
                f"border:1px solid {_afq_col};border-radius:10px;padding:1px 7px;"
                f"font-size:10px;font-weight:700'>{_afq_lbl}</span></span>"
                f"<span style='{_td_a};color:#aaa'>{_av.get('latest_date','—') or '—'}</span>"
                f"<span style='{_td_a};color:{_acol};font-weight:600'>{_aicon} {_albl}</span>"
                f"</div>"
            )
        st.markdown(
            f"<div style='border:1px solid #30363d;border-radius:6px;overflow:hidden'>"
            f"{_rows_a}</div>",
            unsafe_allow_html=True,
        )
        st.caption("💡 建議：🔴 項目請優先重新抓取；🟡 為延遲，仍可使用但需注意時效。")


