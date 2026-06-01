#!/usr/bin/env python3
"""app.py — 基金戰情室 v18.0（重構版）
模組架構：總經 / 單一基金 / 組合基金 / 資料診斷 / 說明書
零快取：每次操作皆即時抓取，確保資料絕對最新
v18.176：移除回測 Tab（user 只需汰弱留強判斷換基金，回測拖速度且 NAV 歷史抓不全）
"""
import streamlit as st

# NOTE: st.set_page_config() MUST be the first Streamlit command. Hoisted
# above all other imports so module-level Streamlit calls in submodules
# (or accidental circular re-imports of app) cannot fire any st.* call first.
st.set_page_config(page_title="基金戰情室", page_icon="📊",
                   layout="wide", initial_sidebar_state="expanded")

import os, datetime, re, time as _time_mod
import plotly.graph_objects as go
import pandas as pd
import numpy as np

TW_TZ = datetime.timezone(datetime.timedelta(hours=8))
def _now_tw():
    return datetime.datetime.now(TW_TZ)

from services.macro_service import (
    fetch_all_indicators, calc_macro_phase,
    ENGINE_VERSION, detect_systemic_risk,
    detect_turning_points, backtest_turning_points,
    calc_sub_cycle_lights, build_macro_sankey_data,
    build_macro_sankey_dynamic, backtest_sub_cycle_lights,
    rank_macro_drivers,
)
from ui.components.mk_clock import render_mk_clock_section
from ui.components.mk_dashboard import render_mk_war_room
from ui.tab1_macro import render_macro_tab
from ui.tab2_single_fund import render_single_fund_tab
from ui.tab3_portfolio import render_portfolio_tab
from ui.tab5_data_guard import render_data_guard_tab
from ui.tab6_manual import render_manual_tab
from ui.tab_crisis_backtest import render_crisis_backtest_tab
from fund_fetcher  import (
    fetch_fund_by_key, search_moneydj_by_name,
    fetch_fund_structure, fetch_fund_from_moneydj_url,
    tdcc_search_fund, get_proxy_config,
    safe_float, classify_fetch_status, clean_risk_table,
    normalize_result_state, merge_non_empty, set_risk_free_rate,
    fetch_market_news,
)
from services.portfolio_service import (
    calc_fund_factor_score,
    dividend_safety as div_safety_check,
    risk_alert as portfolio_risk_alert,
    calc_correlation_matrix,
)
from services.policy_advisor_service import advise_fund, recommend_policy
from repositories.policy_repository import (
    ALL_COLS as POLICY_ALL_COLS,
    REQUIRED_COLS as POLICY_COLS,
    PolicySheetError,
    create_dashboard_sheet,
    delete_policy_row,
    get_gspread_client,
    get_gspread_client_from_oauth,
    get_sheet_title,
    list_policy_worksheets,
    list_user_sheets,
    rename_sheet,
    load_all_policy_worksheets,
    load_policies,
    sync_policies_to_portfolio_funds,
    upsert_fund_in_policy,
    upsert_policy_row,
)
from repositories.ledger_repository import (
    LEDGER_COLS,
    append_ledger_row,
    load_all_ledgers,
    load_ledgers_for_policy,
    replace_ledgers_for_policy,
)
from repositories.snapshot_repository import (
    T7_STATE_TAB,
    get_state_metadata,
    load_all_ledgers_snapshot,
    save_all_ledgers_snapshot,
)
from infra.oauth import (
    OAuthError,
    build_authorize_url,
    build_credentials_from_tokens,
    ensure_fresh_tokens,
    exchange_code_for_tokens,
)
from models.policy import (
    PK_SEP,
    fund_pk_str,
    make_pk,
    migrate_ledger_dict,
    parse_pk,
)

APP_VERSION = "v18.268_FxErApi_Tab5Diag"

# ══════════════════════════════════════════════════════
# 外國企業中文對照表（持股清單顯示用，零外呼）
# ══════════════════════════════════════════════════════
# v18.136: _HOLDING_ZH / _HOLDING_ZH_SUFFIXES / _zh_holding 搬至 ui/helpers/holdings.py
from ui.helpers.holdings import (  # noqa: F401
    _HOLDING_ZH,
    _HOLDING_ZH_SUFFIXES,
    _zh_holding,
)

# v18.125 B-C.3 shim：_parse_indicator_date 仍在 ui/helpers/session.py
from ui.helpers.session import parse_indicator_date as _parse_indicator_date  # noqa: F401

# ══════════════════════════════════════════════════════
# v15.1 友善錯誤 helper：白話 warning + 收合的技術細節
# 設計原則：新手看「發生什麼/該怎麼辦」、工程師展開看 traceback
# ══════════════════════════════════════════════════════
# v18.126 B-C.4: _friendly_error 已搬至 ui/helpers/session.py
from ui.helpers.session import friendly_error as _friendly_error  # noqa: F401


# ══════════════════════════════════════════════════════
# CSS（page_config 已於檔首 hoist，避免 StreamlitSetPageConfigMustBeFirstCommandError）
# ══════════════════════════════════════════════════════
st.markdown("""<style>
body,.stApp{background:#0e1117;color:#e6edf3}
.card{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:14px 18px;margin:6px 0}
.signal-buy{background:#1c3a2a;color:#3fb950;border:1px solid #3fb950;padding:4px 12px;border-radius:20px;font-size:12px;font-weight:600;display:inline-block}
.signal-sell{background:#3a1010;color:#f85149;border:1px solid #f85149;padding:4px 12px;border-radius:20px;font-size:12px;font-weight:600;display:inline-block}
.signal-hold{background:#1a3450;color:#58a6ff;border:1px solid #58a6ff;padding:4px 12px;border-radius:20px;font-size:12px;font-weight:600;display:inline-block}
.signal-switch{background:#3a2a10;color:#f0b132;border:1px solid #f0b132;padding:4px 12px;border-radius:20px;font-size:12px;font-weight:600;display:inline-block}
</style>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════
# Keys & Session State
# ══════════════════════════════════════════════════════
def _load_keys():
    fred = st.secrets.get("FRED_API_KEY","") or os.environ.get("FRED_API_KEY","")
    gem  = st.secrets.get("GEMINI_API_KEY","") or os.environ.get("GEMINI_API_KEY","")
    if fred: os.environ["FRED_API_KEY"]   = fred
    if gem:  os.environ["GEMINI_API_KEY"] = gem
    # v18.217: 多把 Gemini key（自動輪替）— 從 secrets 鏡像到 env 供 get_gemini_keys 讀
    for _gk in (["GEMINI_API_KEYS"] + [f"GEMINI_API_KEY_{_i}" for _i in range(1, 11)]):
        _gv = st.secrets.get(_gk, "") or os.environ.get(_gk, "")
        if _gv:
            os.environ[_gk] = _gv
    # v18.218: 只設多把（GEMINI_API_KEYS / _1..）卻沒設單把 GEMINI_API_KEY 時，
    # 拿池子第一把補進單把 — 讓 sidebar 指示燈 / 各 Tab 的單把 key 檢查照常通過。
    if not gem:
        from services.ai_service import get_gemini_keys  # noqa: PLC0415
        _pool = get_gemini_keys()
        if _pool:
            gem = _pool[0]
            os.environ["GEMINI_API_KEY"] = gem
    # v18.113 AI-3: 多 LLM provider fallback chain — 額外載 Anthropic / OpenAI keys
    # 有設就匯出到 env，infra/llm.py::call_llm 會自動讀；缺則該 provider 在 chain 中 skip
    for _llm_key in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        _v = st.secrets.get(_llm_key, "") or os.environ.get(_llm_key, "")
        if _v:
            os.environ[_llm_key] = _v
    return fred, gem

FRED_KEY, GEMINI_KEY = _load_keys()


def _check_secrets():
    _missing = []
    if not FRED_KEY:   _missing.append("FRED_API_KEY")
    if not GEMINI_KEY: _missing.append("GEMINI_API_KEY")
    if _missing:
        st.error(
            f"⚠️ 缺少必要金鑰：{', '.join(_missing)}。"
            "請至 Streamlit Cloud → Settings → Secrets 新增後重新部署。",
            icon="🔑",
        )

_check_secrets()

# v11.0 D-20: session_state 預設值初始化已抽至 ui/helpers/session.py
from ui.helpers.session import init_session_state as _init_session_state
_init_session_state(st.session_state)


# v18.139（清單 14）：_sync_invest_twd_from_ledgers 搬至 ui/helpers/data_registry.py
from ui.helpers.data_registry import _sync_invest_twd_from_ledgers  # noqa: F401


# v18.136: _update_data_registry 搬至 ui/helpers/data_registry.py
from ui.helpers.data_registry import _update_data_registry  # noqa: F401


# ── Tab5 完整率所需的 16 個關鍵指標(SAHM/SLOOS/PMI/.../COPPER) ──
# v11.0 D-20: _D5_KEYS / calc_data_health 已抽至 ui/helpers/session.py
from ui.helpers.session import _D5_KEYS, calc_data_health as _calc_data_health_pure


def _calc_data_health(indicators=None):
    """Thin wrapper：保留「indicators=None → 走 session_state」的呼叫站慣例。"""
    # 同 run 內直接從 indicators 計算，避免 Tab1 讀到 Tab5 上一輪寫入的舊值
    ind = indicators if indicators is not None else st.session_state.get("indicators", {})
    return _calc_data_health_pure(ind)


# ══════════════════════════════════════════════════════
# OAuth 設定解析（v18.75 hoist：sidebar 登入 UI 與 tab3 共用）
# ══════════════════════════════════════════════════════
# 雙模式 — OAuth（每保單一 worksheet）優先 + 舊 SA（單表 Policies）相容
# 配置來源：secrets.toml [google_oauth] 優先；缺則用 session_state in-app wizard
# v18.136: OAuth chain 搬至 ui/helpers/oauth_state.py
# v18.148: 先 refresh_oauth_state() 確保 module-level snapshot 是 fresh
#          （wizard 寫 session_state 後 rerun，若不 refresh 則 _oauth_configured
#          仍是 import 時的 False snapshot，sidebar 登入按鈕永遠不亮）。
from ui.helpers.oauth_state import refresh_oauth_state as _refresh_oauth_state
_refresh_oauth_state()
from ui.helpers.oauth_state import (  # noqa: F401
    _gsa_secret,
    _sheet_id_secret,
    _resolve_oauth_cfg,
    _oauth_cfg,
    _oauth_configured,
    _get_oauth_client,
    handle_oauth_callback as _oauth_callback,
)
# 觸發 OAuth callback (原 app.py:949-962)
_oauth_callback()

# ══════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## 📊 基金戰情室")
    _upd = st.session_state.get("macro_last_update")
    st.caption(f"📡 總經：{_upd.strftime('%m/%d %H:%M') if _upd else '未載入'}　|　{_now_tw().strftime('%m/%d %H:%M')} TW")
    st.markdown(f"<div style='background:#0d1117;border:1px solid #30363d;border-radius:8px;padding:8px 12px;font-size:11px;color:#888'>App {APP_VERSION} | Engine {ENGINE_VERSION} | Fetcher v6.24</div>", unsafe_allow_html=True)
    # v18.232.1：部署 beacon — 看到這個紅標代表 Cloud 已 reload 到 v18.232（C 區有「目的」selectbox）
    st.markdown(
        "<div style='background:linear-gradient(90deg,#7c3aed,#ec4899);"
        "border-radius:8px;padding:10px 14px;margin-top:8px;"
        "font-size:13px;color:#fff;font-weight:700;text-align:center;"
        "box-shadow:0 2px 8px rgba(124,58,237,0.4)'>"
        "✨ v18.250：PR C — 全部寫入/讀回自動偵測 schema → v2 路徑（v1 不動，向後相容）"
        "</div>",
        unsafe_allow_html=True,
    )
    st.divider()
    _proxy_cfg = get_proxy_config()
    _proxy_ep  = ""
    if _proxy_cfg:
        _m = re.search(r'@(.+)', _proxy_cfg.get("http",""))
        _proxy_ep = _m.group(1) if _m else "已設定"
    st.markdown(f"{'✅' if FRED_KEY else '❌'} FRED　　{'✅' if GEMINI_KEY else '❌'} Gemini　　{'✅' if _proxy_cfg else '⚠️'} Proxy")
    st.caption(f"🔒 {_proxy_ep}" if _proxy_cfg else "⚠️ Proxy 未設定（MoneyDJ 可能被擋）")
    st.divider()
    if st.sidebar.button("🔍 測試 Proxy 連線", use_container_width=True):
        import requests as _req
        _pcfg = get_proxy_config()
        if not _pcfg:
            st.sidebar.error("Proxy 未設定")
        else:
            for _nm, _url in [("MoneyDJ","https://www.moneydj.com/"),("TDCC","https://openapi.tdcc.com.tw/")]:
                try:
                    _r = _req.get(_url, proxies=_pcfg, timeout=25, allow_redirects=False, verify=False)
                    if _r.status_code in (200,301,302,403): st.sidebar.success(f"✅ {_nm} 可達！HTTP {_r.status_code}")
                    elif _r.status_code == 407: st.sidebar.error("❌ 407：帳密錯誤"); break
                    else: st.sidebar.warning(f"⚠️ {_nm} HTTP {_r.status_code}")
                except _req.exceptions.ProxyError as _e: st.sidebar.error(f"❌ {_nm} ProxyError：{str(_e)[:120]}")
                except _req.exceptions.Timeout: st.sidebar.error(f"❌ {_nm} Timeout（25s）")
                except Exception as _e: st.sidebar.error(f"❌ {_nm}：{str(_e)[:120]}")
    if st.sidebar.button("♻️ 強制同步 GitHub 最新邏輯", use_container_width=True):
        # v18.231：原本只 st.rerun() 不查版本；user 回報 Streamlit Cloud 卡舊版按了沒用。
        # 改成比對 local HEAD vs remote main → 不同步時給 Cloud Reboot 連結（容器無法 git pull）
        import subprocess as _sp
        _repo_dir = os.path.dirname(os.path.abspath(__file__))
        def _git(args: list[str], timeout: int = 8) -> str:
            try:
                return _sp.check_output(
                    ["git", *args], cwd=_repo_dir, timeout=timeout,
                    stderr=_sp.DEVNULL,
                ).decode().strip()
            except Exception:
                return ""
        with st.sidebar.status("檢查版本…", expanded=False):
            _local = _git(["rev-parse", "--short", "HEAD"]) or "(unknown)"
            _remote_raw = _git(["ls-remote", "origin", "main"], timeout=12)
            _remote = (_remote_raw.split()[0][:7] if _remote_raw else "(unknown)")
        if _local == "(unknown)":
            st.sidebar.warning("⚠️ 無法讀取本機 commit（git 不可用）")
        elif _remote == "(unknown)":
            st.sidebar.warning(f"⚠️ 無法查 remote main（網路或 git 限制）｜本機 `{_local}`")
        elif _local == _remote:
            st.sidebar.success(f"✅ 已是 main 最新版（`{_local}`）")
        else:
            st.sidebar.warning(
                f"📦 部署 `{_local}` ← main `{_remote}`\n\n"
                "Streamlit 不會自動 reload Python module，需重啟容器："
            )
            st.sidebar.link_button(
                "→ Streamlit Cloud Reboot",
                "https://share.streamlit.io",
                use_container_width=True,
            )
            st.sidebar.caption("本機請 Ctrl+C 後 `streamlit run app.py`")

    # ── v18.75 Google 帳號（從 Tab3 expander 搬上來，登入更顯眼）──
    st.divider()
    st.markdown("##### 🔐 Google 帳號")
    _logged_in_sb = bool(st.session_state.get("gsheet_tokens"))
    if _oauth_configured:
        if _logged_in_sb:
            st.success("🟢 已登入")
            if st.button("🚪 登出", key="btn_oauth_logout_sb",
                          use_container_width=True):
                st.session_state.pop("gsheet_tokens", None)
                st.session_state.pop("active_policy_id", None)
                st.rerun()
        else:
            _login_url_sb = build_authorize_url(
                _oauth_cfg["client_id"], _oauth_cfg["redirect_uri"])
            st.link_button("🔐 用 Google 登入", _login_url_sb,
                            use_container_width=True)
            st.caption("登入後 Tab3 即可雲端存取保單試算表")
    elif _gsa_secret and _sheet_id_secret:
        st.caption("ℹ️ 使用 Service Account（舊版單表）")
    else:
        st.caption("⚙️ OAuth Client 尚未設定 — 請至 Tab3「📊 組合基金」"
                   "→ 展開「📋 保單管理」設定")

    # ── v18.164：工作中帳本（Sheet ID 從 Tab3 expander hoist 到 sidebar）──
    if _logged_in_sb or (_gsa_secret and _sheet_id_secret):
        st.markdown("##### 📋 工作中帳本")
        _sid_default_sb = (st.session_state.get("policy_sheet_id")
                            or _sheet_id_secret or "")
        _sid_raw_sb = st.text_input(
            "Sheet ID 或完整 URL",
            value=_sid_default_sb, key="inp_sheet_id",
            help="貼 Google Sheet URL 會自動解析 ID",
        ).strip()
        _m_sb = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", _sid_raw_sb)
        _sid_sb = _m_sb.group(1) if _m_sb else _sid_raw_sb
        if _sid_sb and _sid_sb != _sid_default_sb:
            st.session_state["policy_sheet_id"] = _sid_sb
        if _sid_sb and _logged_in_sb:
            _title_cache_key = f"_t3_cur_sheet_title:{_sid_sb}"
            _cur_title_sb = st.session_state.get(_title_cache_key)
            if _cur_title_sb is None:
                try:
                    _cur_title_sb = get_sheet_title(
                        _get_oauth_client(), _sid_sb)
                    st.session_state[_title_cache_key] = _cur_title_sb
                except Exception:
                    _cur_title_sb = ""
            if _cur_title_sb:
                st.caption(f"📂 **{_cur_title_sb}**")
            else:
                st.caption(f"📂 ID `{_sid_sb[:14]}…`")
        elif not _sid_sb and _logged_in_sb:
            st.caption("⚠️ 尚未指定 — 至 Tab3「✨ 新增帳本」建立或挑一本")

# ══════════════════════════════════════════════════════
# HELPER: _is_core_fund
# ══════════════════════════════════════════════════════
# v18.126 B-C.4: _is_core_fund + 3 constants 已搬至 ui/helpers/session.py
from ui.helpers.session import (  # noqa: F401
    _CORE_WHITELIST,
    _CORE_KEYWORDS,
    _SAT_KEYWORDS,
    is_core_fund as _is_core_fund,
)

# ══════════════════════════════════════════════════════
# HELPER: v18.133 從本檔搬至 ui/helpers/macro_helpers.py（B-C 連環 hotfix 收尾）
# 留 shim re-export 給既有 callsite + tests 向後相容
# ══════════════════════════════════════════════════════
from ui.helpers.macro_helpers import (  # noqa: F401
    _CATEGORY_MAP,
    calculate_composite_score,
    composite_verdict,
    category_score,
    category_history,
    category_verdict,
    mk_fund_signal,
    quartile_check as _quartile_check,
)


def _unused_old_calculate_composite_score(ind: dict) -> float:
    """deprecated; kept as placeholder before edit boundary."""
    return ui.helpers.macro_helpers.calculate_composite_score(ind)


# ══════════════════════════════════════════════════════
# v15.2 全局指標關聯地圖（Sankey）— 方案 B：新人秒懂上下游傳導
# ══════════════════════════════════════════════════════
# v18.127 B-C.5: render_indicator_map 已搬至 ui/tab1_macro.py（Tab1 唯一 caller）
# 保留 shim 供任何外部 callsite（grep 過全 repo 無；shim 純為防禦）
from ui.tab1_macro import render_indicator_map  # noqa: F401


# ══════════════════════════════════════════════════════
# 🧭 總經指南針 (Top-Down Macro) — Phase 1 規格頂部三大美股指標
# ══════════════════════════════════════════════════════
def _render_compass_card(col, info, title, ticker, fmt='{:.2f}', unit='', show_ma=False):
    """單張指標卡：值 + Phase 1 訊號燈 + 60D sparkline。info=None 顯示降級訊息。"""
    if info is None:
        col.markdown(
            f'<div style="background:#0d1117;border:1px solid #21262d;border-radius:8px;padding:10px;height:84px;">'
            f'<div style="font-size:11px;color:#8b949e;">{title}（{ticker}）</div>'
            f'<div style="font-size:13px;color:#8b949e;margin-top:6px;">🔴 未取得（yfinance 暫時失敗）</div>'
            f'</div>', unsafe_allow_html=True)
        return
    val = info.get('value')
    sig = info.get('signal') or ('⚪', '無訊號', '#8b949e')
    light, label, color = sig[0], sig[1], sig[2]
    val_str = fmt.format(val) + unit if val is not None else 'N/A'
    extra = ''
    if show_ma and info.get('ma60') is not None:
        extra = f' <span style="font-size:10px;color:#8b949e;font-weight:400;">/ 60MA {fmt.format(info["ma60"])}</span>'
    col.markdown(
        f'<div style="background:#0d1117;border:1px solid {color};border-radius:8px;padding:10px;">'
        f'<div style="font-size:11px;color:#8b949e;">{title}（{ticker}）</div>'
        f'<div style="font-size:22px;font-weight:900;color:#e6edf3;margin:2px 0;">{val_str}{extra}</div>'
        f'<div style="font-size:11px;font-weight:700;color:{color};">{light} {label}</div>'
        f'</div>', unsafe_allow_html=True)
    ser = info.get('series') or []
    if ser:
        try:
            col.line_chart(pd.Series(ser, name=title), height=80, use_container_width=True)
        except Exception:
            pass  # noqa: smoke-allow-pass

def render_macro_compass():
    """頂部三卡：VIX 恐慌指數 × 美 10Y 殖利率 × S&P 500 vs 60MA。
    預設不抓資料（避免顯示過時值誤判），按「📡 抓取最新」按鈕才打 yfinance。
    語意：按鈕當下＝盤面當下＝決策當下真實狀態。"""
    import datetime as _dt_mc

    def _do_fetch():
        try:
            from repositories.macro_repository import fetch_macro_compass as _fmc
            _fmc.cache_clear()
            _data = _fmc()
        except Exception as e:
            print(f'[render_macro_compass] fetch failed: {e}')
            _data = {}
        st.session_state['_macro_compass_cache'] = {
            '_ts': _dt_mc.datetime.now(), 'data': _data,
        }

    _cache = st.session_state.get('_macro_compass_cache')
    _has_data = bool(_cache and _cache.get('data'))
    _ts_str = (_cache.get('_ts').strftime('%H:%M:%S')
               if _has_data and _cache.get('_ts') else '尚未抓取')

    _header = st.columns([6, 1])
    _header[0].markdown(
        '<div style="font-size:14px;font-weight:900;color:#e6edf3;margin:4px 0 4px;">'
        '🧭 總經指南針 (Top-Down Macro)'
        '<span style="font-size:10px;color:#8b949e;font-weight:400;margin-left:8px;">'
        f'VIX × 10Y × S&amp;P 500 — {"即將抓取（無快取）" if not _has_data else f"更新於 {_ts_str}"}'
        '</span></div>',
        unsafe_allow_html=True)
    _header[1].button('📡 抓取最新' if not _has_data else '🔄 重抓',
                       key='_compass_fetch_btn', on_click=_do_fetch,
                       use_container_width=True)

    if not _has_data:
        st.info('💡 點擊右上「📡 抓取最新」按鈕載入即時 VIX / 10Y / S&P 500')
        return

    data = _cache.get('data') or {}
    c1, c2, c3 = st.columns(3)
    _render_compass_card(c1, data.get('vix'),  'VIX 恐慌指數',     '^VIX',  fmt='{:.2f}')
    _render_compass_card(c2, data.get('tnx'),  '美 10Y 殖利率',    '^TNX',  fmt='{:.2f}', unit='%')
    _render_compass_card(c3, data.get('gspc'), 'S&P 500 vs 60MA',  '^GSPC', fmt='{:,.2f}', show_ma=True)

render_macro_compass()

# ══════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════
# 故事化動線（v18.193）：tab 順序依 spec 敘事 —
# 🌐 總經環境 → 📊 核心/衛星配置 → 🔍 單一基金深掘（原本「單一基金」在「組合」前，違反敘事）
tab_macro, tab_portfolio, tab_single, tab_crisis, tab5, tab6 = st.tabs(
    ["🌐 總經", "📊 組合基金", "🔍 單一基金", "📉 危機回測室", "🔬 資料診斷", "📖 說明書"])

# ══════════════════════════════════════════════════════
# TAB 1 — 🌐 總經環境（故事第 1 站）
# ══════════════════════════════════════════════════════
with tab_macro:
    # v18.127 B-C.5: 總經 Tab 內容已搬到 ui/tab1_macro.py
    render_macro_tab()

# ══════════════════════════════════════════════════════
# TAB 2 — 📊 核心/衛星資產配置（故事第 2 站）
# ══════════════════════════════════════════════════════
with tab_portfolio:
    # v18.128 B-C.6: 組合 Tab 內容（含 T5/T6/T7 子區）已搬到 ui/tab3_portfolio.py
    render_portfolio_tab()

# ══════════════════════════════════════════════════════
# TAB 3 — 🔍 單一基金深掘（故事第 3 站）
# ══════════════════════════════════════════════════════
with tab_single:
    # v18.126 B-C.4: 單一基金 Tab 內容已搬到 ui/tab2_single_fund.py
    render_single_fund_tab()

# ══════════════════════════════════════════════════════
# TAB 4 — 📉 危機回測室（v18.260 Phase 2）
# ══════════════════════════════════════════════════════
with tab_crisis:
    render_crisis_backtest_tab()

# ══════════════════════════════════════════════════════
# TAB 5 — 資料診斷
# ══════════════════════════════════════════════════════
with tab5:
    # v18.125 B-C.3 + v18.130 hotfix: Tab5 內容已全部搬到 ui/tab5_data_guard.py
    # （含原 Section 0/-1 header 24 行，PR #186 已補回 module 內）
    _update_data_registry()
    render_data_guard_tab()

# ══════════════════════════════════════════════════════
# TAB 6 — 說明書
# ══════════════════════════════════════════════════════
with tab6:
    # v18.117 B-C.1：說明書 Tab 內容已搬到 ui/tab6_manual.py
    render_manual_tab()
