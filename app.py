#!/usr/bin/env python3
"""app.py — 基金戰情室 v18.0(重構版)
模組架構(v19.130):總經 → 單一基金 → 組合基金健診 → 組合配置 → 資料診斷 → 說明書
零快取:每次操作皆即時抓取,確保資料絕對最新
v18.176:移除回測 Tab(user 只需汰弱留強判斷換基金,回測拖速度且 NAV 歷史抓不全)
v19.130:tab 重排 + 改名 + 刪除「💼 配置模擬器」
"""
import streamlit as st

# NOTE: st.set_page_config() MUST be the first Streamlit command. Hoisted
# above all other imports so module-level Streamlit calls in submodules
# (or accidental circular re-imports of app) cannot fire any st.* call first.
st.set_page_config(page_title="基金戰情室", page_icon="📊",
                   layout="wide", initial_sidebar_state="expanded")

import os, datetime, re
import pandas as pd

TW_TZ = datetime.timezone(datetime.timedelta(hours=8))
def _now_tw():
    return datetime.datetime.now(TW_TZ)

from shared.colors import GH_BG_CARD, GH_BORDER, GH_FG_PRIMARY, INFO_BLUE, STREAMLIT_BG, TRAFFIC_GREEN, TRAFFIC_RED
from services.macro import (
    ENGINE_VERSION,
)
from ui.tab1_macro import render_macro_tab
from ui.tab2_single_fund import render_single_fund_tab
from ui.tab3_portfolio import render_portfolio_tab
from ui.tab5_data_guard import render_data_guard_tab
from ui.tab6_manual import render_manual_tab
# v19.31 ARCHIVED: 📉 危機回測室,未來啟用時取消下行註解
# from ui.tab_crisis_backtest import render_crisis_backtest_tab
from ui.tab_fund_grp_health import render_fund_grp_health_tab  # noqa: E402
from fund_fetcher  import (
    get_proxy_config,
)
from repositories.policy_repository import (
    get_sheet_title,
)
from infra.oauth import (
    build_authorize_url,
)

APP_VERSION = "v19.45_MacroNavigator"

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
# v19.252 Phase 4A:signal-buy/sell 走 TRAFFIC SSOT(原 inline #3fb950 / #f85149)
st.markdown(f"""<style>
body,.stApp{{background:{STREAMLIT_BG};color:{GH_FG_PRIMARY}}}
.card{{background:{GH_BG_CARD};border:1px solid {GH_BORDER};border-radius:10px;padding:14px 18px;margin:6px 0}}
.signal-buy{{background:#1c3a2a;color:{TRAFFIC_GREEN};border:1px solid {TRAFFIC_GREEN};padding:4px 12px;border-radius:20px;font-size:12px;font-weight:600;display:inline-block}}
.signal-sell{{background:#3a1010;color:{TRAFFIC_RED};border:1px solid {TRAFFIC_RED};padding:4px 12px;border-radius:20px;font-size:12px;font-weight:600;display:inline-block}}
.signal-hold{{background:#1a3450;color:{INFO_BLUE};border:1px solid {INFO_BLUE};padding:4px 12px;border-radius:20px;font-size:12px;font-weight:600;display:inline-block}}
.signal-switch{{background:#3a2a10;color:#f0b132;border:1px solid #f0b132;padding:4px 12px;border-radius:20px;font-size:12px;font-weight:600;display:inline-block}}
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
from ui.helpers.session import calc_data_health as _calc_data_health_pure


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
# SIDEBAR (C 第二輪 v19.229: 抽至 ui/sidebar.py)
# ══════════════════════════════════════════════════════
from ui.sidebar import render_sidebar
render_sidebar(
    app_version=APP_VERSION,
    engine_version=ENGINE_VERSION,
    fred_key=FRED_KEY,
    gemini_key=GEMINI_KEY,
    now_tw_fn=_now_tw,
)

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


# F-GRAY-3 v19.81:`_unused_old_calculate_composite_score` 已刪(deprecated placeholder,
# grep 全 repo 唯一引用為定義本身;dead code)。CLAUDE.md §8.3 灰色地帶 audit 結案。


# ══════════════════════════════════════════════════════
# v15.2 全局指標關聯地圖（Sankey）— 方案 B：新人秒懂上下游傳導
# ══════════════════════════════════════════════════════
# v18.127 B-C.5: render_indicator_map 已搬至 ui/tab1_macro.py（Tab1 唯一 caller）
# 保留 shim 供任何外部 callsite（grep 過全 repo 無；shim 純為防禦）
from ui.tab1_macro import render_indicator_map  # noqa: F401


# ══════════════════════════════════════════════════════
# 🧭 總經指南針 (Top-Down Macro) — C3 v19.207 拆至 ui/components/macro_compass_top.py
# ══════════════════════════════════════════════════════
from ui.components.macro_compass_top import render_macro_compass


render_macro_compass()

# ══════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════
# v19.130 故事化動線(2026-06-25 user 反饋,重排 + 改名 + 刪 配置模擬器):
# 🌐 總經 → 🔍 單一基金(深掘)→ 💊 組合基金健診(原「組合健診」)
#         → 📊 組合配置(原「組合基金」)→ 🔭 資料診斷 → 📖 說明書
# 敘事:總經背景 → 個基細查 → 持有組合健康 → 配置決策 → 診斷 → 文件
tab_macro, tab_single, tab_health, tab_portfolio, tab5, tab6 = st.tabs(
    ["🌐 總經", "🔍 單一基金", "💊 組合基金健診",
     "📊 組合配置", "🔭 資料診斷", "📖 說明書"])

# ══════════════════════════════════════════════════════
# TAB 1 — 🌐 總經環境（故事第 1 站）
# ══════════════════════════════════════════════════════
with tab_macro:
    # v18.127 B-C.5: 總經 Tab 內容已搬到 ui/tab1_macro.py
    render_macro_tab()

# ══════════════════════════════════════════════════════
# TAB 2 — 🔍 單一基金深掘(故事第 2 站,v19.130 提前)
# ══════════════════════════════════════════════════════
with tab_single:
    # v18.126 B-C.4: 單一基金 Tab 內容已搬到 ui/tab2_single_fund.py
    render_single_fund_tab()

# ══════════════════════════════════════════════════════
# TAB 3 — 💊 組合基金健診(故事第 3 站,v19.37 / v19.130 改名)
# 以 100 萬 TWD 為基準逐檔模擬:原幣本金 / 持有份額 / 逐期配息折算 TWD / 吃本金判定
# 純函式核心 services/fund_dividend_calculator.py(zero-IO 可單測)
# ══════════════════════════════════════════════════════
with tab_health:
    render_fund_grp_health_tab()

# ══════════════════════════════════════════════════════
# TAB 4 — 📊 組合配置(故事第 4 站,v18.128 / v19.130 改名「組合基金」→「組合配置」)
# ══════════════════════════════════════════════════════
with tab_portfolio:
    # v18.128 B-C.6: 組合 Tab 內容(含 T5/T6/T7 子區)已搬到 ui/tab3_portfolio.py
    render_portfolio_tab()

# ══════════════════════════════════════════════════════
# v19.31 ARCHIVED: 📉 危機回測室,模組檔保留於磁碟,未來啟用解註 import + with-block
# ══════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════
# TAB 8 — 資料診斷
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
