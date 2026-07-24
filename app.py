#!/usr/bin/env python3
"""app.py — 基金戰情室 v18.0(重構版)
模組架構(v19.130):總經 → 單一基金 → 組合基金健診 → 組合配置 → 資料診斷 → 說明書
快取策略(v19.333 對齊實作,review F10):L1 repository 以 @_ttl_cache / @_daily_cache
短 TTL 快取(infra/cache.py _CACHE_REGISTRY 集中註冊;失敗結果不入快取),
UI「全域刷新」clear_all_caches() 強制重抓 — 原「零快取」敘述與實作不符,已更正
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
# v19.314:危機回測室(tab_crisis_backtest + crisis_strategy_grid + crisis_ai_advisor)
# 自 v19.31 起即註解停用、進不去;user 確認不用 → 整功能拔除(2798 LOC)。
# 註:services/crisis_backtest.py(CrisisEvent/detect_crisis_events)保留,macro/calibration 仍用。
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

APP_VERSION = "v19.392_VizV4b_DivLabels"


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

# B1 Fix: server cold restart 後 module-level _RF_ANNUAL 歸預設 4%;
# 若 session_state 已有 FED_RATE 快取,立即同步，不等 Tab1 button click。
_cached_ind = st.session_state.get("indicators", {})
if "FED_RATE" in _cached_ind:
    from services.fund_service import set_risk_free_rate as _set_rf
    _set_rf(_cached_ind["FED_RATE"].get("value", 4.0) / 100)


# v18.136: _update_data_registry 搬至 ui/helpers/data_registry.py
from ui.helpers.data_registry import _update_data_registry  # noqa: F401


# ── Tab5 完整率所需的 16 個關鍵指標(SAHM/SLOOS/PMI/.../COPPER) ──
# v11.0 D-20: _D5_KEYS / calc_data_health 已抽至 ui/helpers/session.py
# v19.342(第八份 review 屬實項):app.py 的 `_calc_data_health` thin wrapper
# 本檔 0 呼叫者(真 caller 在 ui/tab1_macro.py:305 自帶同款 wrapper;tab5 版
# v19.339 已刪)— import + wrapper 一併移除,session.py 純函式為唯一實作。


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
from ui.helpers.oauth_state import handle_oauth_callback as _oauth_callback
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

# F-GRAY-3 v19.81:`_unused_old_calculate_composite_score` 已刪(deprecated placeholder,
# grep 全 repo 唯一引用為定義本身;dead code)。CLAUDE.md §8.3 灰色地帶 audit 結案。


# ══════════════════════════════════════════════════════
# 🧭 總經指南針 (Top-Down Macro) — C3 v19.207 拆至 ui/components/macro_compass_top.py
# ══════════════════════════════════════════════════════
from ui.components.macro_compass_top import render_macro_compass


# v19.302: render_macro_compass() 移入 tab_macro — 僅在總經 Tab 顯示（不跨 Tab 污染）

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
    render_macro_compass()  # v19.302: 移入此處 — 僅在總經 Tab 顯示
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
