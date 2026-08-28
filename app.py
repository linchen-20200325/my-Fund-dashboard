#!/usr/bin/env python3
"""app.py — 基金戰情室 v18.0(重構版)
模組架構(v19.405 6→5):市場定調 → 組合健診 → 個基深掘 → 配置 & 帳本 → 參考 / 診斷
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

# ⚠️ 一律放在 set_page_config 之後 —— 本檔的硬規則是「第一個 Streamlit 指令必須是
# set_page_config」,任何在它之前的 import 都可能在 submodule 頂層先射出一個 st.* 呼叫。

import os, datetime

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
from ui.tab_batch_analysis import render_batch_analysis_tab  # noqa: E402
from ui.tab_manage import render_manage_tab  # noqa: E402  (📋 我的管理室,v19.433)

APP_VERSION = "v19.405_IA_P4_TabRestructure"


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
/* ── sticky 頂層 tab bar(2026-08-05 稽核 必修 5)──────────────────────────
   Tab1 從頂捲到底需 60+ 次滾輪,tab bar 不 sticky → 換分頁要整路捲回去。
   ⚠️ Streamlit 內部 DOM(data-testid / data-baseweb)**無公開契約**,升版可能改名。
   故只用「選不到就什麼都不發生」的純 CSS(不寫任何 JS、不改寬度,失效 = 回到現況)。
   第 2 條規則把**巢狀** st.tabs(參考 / 診斷內的子頁)還原 static —— 否則子分頁列
   也會黏在畫面上互相打架。用 descendant(非 `>`)寫法,不假設 tab-list 是直接子節點。
   background 吃 STREAMLIT_BG SSOT(禁寫死 hex);top/z-index 為 CSS 佈局數值
   (同本區 .card 的 padding 慣例),top 取 Streamlit 固定 header 高度。 */
div[data-testid="stTabs"] div[data-baseweb="tab-list"]{{position:sticky;top:3.75rem;z-index:100;background:{STREAMLIT_BG};border-bottom:1px solid {GH_BORDER}}}
div[data-testid="stTabs"] div[data-testid="stTabs"] div[data-baseweb="tab-list"]{{position:static;background:transparent;border-bottom:none}}
</style>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════
# Keys & Session State
# ══════════════════════════════════════════════════════
# ── 2026-08-15：完全沒有 secrets 檔時,App 原本會在啟動就崩潰 ────────────────
# `st.secrets.get(k, "")` 看起來像「取不到就回預設值」的安全寫法,但 Streamlit 在
# **一個 secrets 檔都找不到**時,`.get()` 內部仍會去 `_parse()` → 直接
# `raise StreamlitSecretNotFoundError`。於是新 clone 下來的專案(secrets.toml 有被
# gitignore,本來就不會有)一跑就是滿版紅色 traceback,連「你缺什麼、去哪裡設」
# 都沒說 —— 而缺 key 這件事本來就有專門的地方在講(見下方「金鑰狀態的顯示位置」),
# 只是那些地方在啟動崩潰時全都跑不到。
#
# 修法走既有 SSOT `infra.config.get_secret`(它 :39-48 早就 try/except 包好,
# 且自帶 os.environ fallback)—— 不在本檔另寫一份(§2.1)。
# §1:不是掩蓋錯誤 —— 缺 key 這件事照樣會被講出來,只是**不在這裡講**
# (2026-08-28 Q3 起改由 Tab5 §④ 金鑰狀態 + 市場定調頁的 FRED 分支負責,
#  見下方「金鑰狀態的顯示位置」),而不是崩在啟動的第 105 行。
from infra.config import get_secret as _secret_raw  # noqa: E402


def _secret(key: str) -> str:
    """secret 值(str);缺 / 無 secrets 檔 → ""。env fallback 由 get_secret 內建。"""
    return str(_secret_raw(key, "") or "")


def _load_keys():
    fred = _secret("FRED_API_KEY")
    gem  = _secret("GEMINI_API_KEY")
    if fred: os.environ["FRED_API_KEY"]   = fred
    if gem:  os.environ["GEMINI_API_KEY"] = gem
    # v18.217: 多把 Gemini key（自動輪替）— 從 secrets 鏡像到 env 供 get_gemini_keys 讀
    for _gk in (["GEMINI_API_KEYS"] + [f"GEMINI_API_KEY_{_i}" for _i in range(1, 11)]):
        _gv = _secret(_gk)
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
        _v = _secret(_llm_key)
        if _v:
            os.environ[_llm_key] = _v
    return fred, gem

FRED_KEY, GEMINI_KEY = _load_keys()

# ── 金鑰狀態的顯示位置(2026-08-28 客戶拍板 Q3:「同意移走。移至『⑤ 設定與診斷』
#    的 API 金鑰狀態」)──────────────────────────────────────────────────────
# 這裡原本有一個 `_check_secrets()`,在 module top-level 無條件執行 → **五個分頁的
# 最上方都會看到**那一行,而它多半不代表任何故障(GEMINI 缺了只是少 AI 摘要,可降級)。
# 批次一已先把它從 🔴 改成 ⬜(只改顏色、不改位置);本批依 Q3 **整段移走**,
# 不是在兩邊各留一份。
#
# 搬去哪、以及為什麼資訊沒有變少(這三處都是既有的,不是本批新造):
#   1. 缺哪幾把 + 去哪裡設 → `ui/tab5_data_guard.py` §④「🔑 API 金鑰狀態」。
#      該表本來就逐把列出 FRED / GEMINI / FINMIND / PROXY / GOOGLE_SHEET_ID 的
#      來源與遮罩(比這裡多 3 把);本批只補上它唯一缺的那件事 ——「去哪裡設定」。
#   2. 缺 FRED(會擋住整個市場定調頁)→ `ui/tab1_macro.py` 的
#      `if not FRED_KEY:` 分支已印「尚未設定 FRED 金鑰,無法載入總經資料」+ 去哪裡補。
#   3. 缺 GEMINI(只影響 AI 區塊)→ 由各 AI 區塊自己在用得到的地方說。

# v11.0 D-20: session_state 預設值初始化已抽至 ui/helpers/session.py
from ui.helpers.session import init_session_state as _init_session_state
_init_session_state(st.session_state)

# B1 Fix: server cold restart 後 module-level _RF_ANNUAL 歸預設 4%;
# 若 session_state 已有 FED_RATE 快取,立即同步，不等 Tab1 button click。
#
# 稽核 D4（2026-08-14 修）：原本是 `.get("value", 4.0) / 100`。
# 問題有三：
#  (1) key 存在但 value 是 None（fetch 失敗的正常型態）時，捏造一個 4% 無風險
#      利率灌進**全站** Sharpe / Sortino —— §1 明令「錯誤的數字比沒有數字更危險」。
#  (2) 4.0 是 `services/fund_service.py:_RF_ANNUAL` 的第二份手抄副本，未走 SSOT。
#  (3) `None / 100` 會直接 TypeError，而這一段**不在任何 try 內** —— 一旦
#      FED_RATE 抓到 None，整個 app 在 import 期就掛掉。
# 改法：缺值就**不呼叫**，讓 fund_service 沿用它自己的 SSOT 預設，並寫 stderr
# 留痕（Streamlit Cloud 的 log 面板只看得到 stderr）。
_cached_ind = st.session_state.get("indicators", {})
_fed_v = (_cached_ind.get("FED_RATE") or {}).get("value")
if _fed_v is not None:
    from services.fund_service import set_risk_free_rate as _set_rf
    _set_rf(float(_fed_v) / 100)
elif "FED_RATE" in _cached_ind:
    import sys as _sys_rf
    print("[app] FED_RATE 存在但 value 為 None → 不設定無風險利率，"
          "沿用 services.fund_service._RF_ANNUAL 預設（不捏造）",
          file=_sys_rf.stderr)


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
# 🧭 總經指南針 (Top-Down Macro) — **整條鏈已於 2026-08-05 移除**。
#   沿革:v19.207 抽成獨立元件 → v19.302 由 app.py 移入總經 Tab →
#         v19.430 再下移到「🔎 詳細資料與說明」區 → 2026-08-05 稽核判定
#         三張卡與 🎯 短線雷達重複、且需再按一次自己的抓取鈕才有資料,整塊刪除。
#   L3 元件 / L2 facade / L1 fetcher 三層一併退役(PROCESS.md §4 0-consumer 條款)。
#   本檔沒有殘留 import 或呼叫;回退方式見 git history。
# ══════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════
# v19.130 舊 6-tab 故事化動線已由下方 v19.405 Phase 4 決策動線(6→5)取代。
# v19.405 Phase 4（IA 重分類 6→5）：分頁改照「決策動線」排序 + 命名,
# 支援型的「資料診斷 + 說明書」合成一個「參考 / 診斷」分頁(user 核准合區)。
# 決策動線:① 市場定調(加碼/防禦)→ ② 組合健診(哪幾檔健康/吃本金)→
#          ③ 個基深掘(細看被點名的那檔)→ ④ 配置 & 帳本(記帳/再平衡)→ ⑤ 參考/診斷。
# 2026-08-05 稽核 必修 2:決策動線四站的分頁名改吃 `ui/helpers/story_nav._STEPS`
# SSOT(`tab_label()` 去掉 ①②③④ 序號)。原本 app.py 與 story_nav 各寫死一份,
# 導致各 Tab 的「請至 X 分頁」指路文案改名後對不上(§3.3 反捏造)。
# 2026-08-14：原本「📦 批次分析 / 📋 我的管理室 / 📖 參考 / 診斷」三個因為
# 「不在決策動線 4 站內」而保留字面值 —— 但那理由只解釋了它們**不需要序號前綴**,
# 不代表分頁名可以有第二份來源。實機稽核在 sidebar 又抓到三處指路文案指向不存在
# 的分頁名(同一種病第二次發作)。故 7 個分頁名全部收進 story_nav._TAB_LABELS。
from ui.helpers.story_nav import tab_label as _tab_label
tab_macro, tab_health, tab_batch, tab_single, tab_portfolio, tab_manage, tab_ref = st.tabs(
    [_tab_label("macro"), _tab_label("health"), _tab_label("batch"),
     _tab_label("fund"), _tab_label("portfolio"), _tab_label("manage"),
     _tab_label("ref")])

# ══════════════════════════════════════════════════════
# TAB ① — 🌐 市場定調（決策動線第 1 站:加碼或防禦）
# ══════════════════════════════════════════════════════
with tab_macro:
    # §1 分頁隔離（v19.429）：st.tabs 單次 run 渲染全部分頁，總經（第 1 個 with
    # 區塊）若拋未捕捉例外會中止整個 script → 其後所有分頁空白。外層 try 保證「總經
    # 整體失敗不連坐其他分頁」；內層 tab1_macro._safe_section 再做 section 級細粒度
    # 隔離。非靜默吞：friendly_error 顯式顯示 + stderr 鏡射進 Cloud log + traceback。
    #
    # 🧭 總經指南針:整條鏈已於 2026-08-05 移除(見本檔上方沿革區塊)。此處不再有
    # 任何指南針呼叫,元件模組本身也已退役 —— 在此還原呼叫會直接 ImportError。
    try:
        # v18.127 B-C.5: 內容已搬到 ui/tab1_macro.py
        render_macro_tab()
    except Exception as _macro_tab_e:  # noqa: BLE001 — §1 分頁隔離，非靜默吞
        from ui.helpers.session import friendly_error as _fe_macro
        _fe_macro("「🌐 市場定調」分頁渲染失敗", _macro_tab_e,
                  hint="此分頁已隔離，其他分頁不受影響；請展開「🔧 技術細節」把 "
                       "traceback（含 File \"...\", line N）回報，即可精準定位根因。",
                  level="error")

# ══════════════════════════════════════════════════════
# TAB ② — 💊 組合健診（決策動線第 2 站:手上哪幾檔健康 / 吃本金)
# v19.405 Phase 4:提前至第 2 站(健診先於個基深掘,對齊「先看整體、再鑽個檔」動線)。
# 以 100 萬 TWD 為基準逐檔模擬:原幣本金 / 持有份額 / 逐期配息折算 TWD / 吃本金判定。
# ══════════════════════════════════════════════════════
with tab_health:
    try:
        render_fund_grp_health_tab()
    except Exception as _health_tab_e:  # noqa: BLE001 — §1 分頁隔離(v19.502),非靜默吞
        from ui.helpers.session import friendly_error as _fe_health
        _fe_health("「💊 組合健診」分頁渲染失敗", _health_tab_e,
                   hint="此分頁已隔離,其他分頁不受影響;請展開「🔧 技術細節」把 traceback"
                        "(含 File \"...\", line N)回報,即可精準定位根因。",
                   level="error")

# ══════════════════════════════════════════════════════
# TAB ②-B — 📦 批次分析（工具:一次上傳大量代號 → 報酬/風險/配息表 → 下載 CSV)
# 與「組合健診」同為基金分析,但規模不同:健診 ≤10 檔深看,批次為 400 檔淺掃導出。
# ══════════════════════════════════════════════════════
with tab_batch:
    try:
        render_batch_analysis_tab()
    except Exception as _batch_tab_e:  # noqa: BLE001 — §1 分頁隔離(v19.502),非靜默吞
        from ui.helpers.session import friendly_error as _fe_batch
        _fe_batch("「📦 批次分析」分頁渲染失敗", _batch_tab_e,
                  hint="此分頁已隔離,其他分頁不受影響;請展開「🔧 技術細節」把 traceback"
                       "(含 File \"...\", line N)回報,即可精準定位根因。",
                  level="error")

# ══════════════════════════════════════════════════════
# TAB ③ — 🔍 個基深掘（決策動線第 3 站:被健診點名的那檔,細看買賣點）
# ══════════════════════════════════════════════════════
with tab_single:
    # v18.126 B-C.4: 內容已搬到 ui/tab2_single_fund.py
    try:
        render_single_fund_tab()
    except Exception as _single_tab_e:  # noqa: BLE001 — §1 分頁隔離(v19.502),非靜默吞
        from ui.helpers.session import friendly_error as _fe_single
        _fe_single("「🔍 個基深掘」分頁渲染失敗", _single_tab_e,
                   hint="此分頁已隔離,其他分頁不受影響;請展開「🔧 技術細節」把 traceback"
                        "(含 File \"...\", line N)回報,即可精準定位根因。",
                   level="error")

# ══════════════════════════════════════════════════════
# TAB ④ — 📊 配置 & 帳本（決策動線第 4 站:記帳 + 再平衡）
# ══════════════════════════════════════════════════════
with tab_portfolio:
    # v18.128 B-C.6: 內容(含 T5/T6/T7 子區)已搬到 ui/tab3_portfolio.py
    try:
        render_portfolio_tab()
    except Exception as _portfolio_tab_e:  # noqa: BLE001 — §1 分頁隔離(v19.502),非靜默吞
        from ui.helpers.session import friendly_error as _fe_portfolio
        _fe_portfolio("「📊 配置 & 帳本」分頁渲染失敗", _portfolio_tab_e,
                      hint="此分頁已隔離,其他分頁不受影響;請展開「🔧 技術細節」把 traceback"
                           "(含 File \"...\", line N)回報,即可精準定位根因。",
                      level="error")

# ══════════════════════════════════════════════════════
# TAB ④-B — 📋 我的管理室（v19.433:選股池 + 投資組合 + 通報 一站集中管理）
# 不新增儲存;重用既有 L1/L2/L0(pool_repository / policy v2 讀寫 / switch_notify / line_push)。
# ══════════════════════════════════════════════════════
with tab_manage:
    try:
        render_manage_tab()
    except Exception as _manage_tab_e:  # noqa: BLE001 — §1 分頁隔離,非靜默吞
        from ui.helpers.session import friendly_error as _fe_manage
        _fe_manage("「📋 我的管理室」分頁渲染失敗", _manage_tab_e,
                   hint="此分頁已隔離,其他分頁不受影響;請展開「🔧 技術細節」回報 traceback。",
                   level="error")

# ══════════════════════════════════════════════════════
# TAB ⑤ — 📖 參考 / 診斷（支援區:資料診斷 + 說明書合區,v19.405 Phase 4）
# 二者皆為參考/支援型(非決策階段)→ user 核准收成一區,內用巢狀分頁分隔。
# v19.31 ARCHIVED: 📉 危機回測室,模組檔保留於磁碟,未來啟用解註即可。
# ══════════════════════════════════════════════════════
with tab_ref:
    try:
        _ref_diag, _ref_manual = st.tabs(["🔭 資料診斷", "📖 說明書"])
        with _ref_diag:
            # v18.125 B-C.3: 內容已搬到 ui/tab5_data_guard.py
            _update_data_registry()
            render_data_guard_tab()
        with _ref_manual:
            # v18.117 B-C.1: 內容已搬到 ui/tab6_manual.py
            render_manual_tab()
    except Exception as _ref_tab_e:  # noqa: BLE001 — §1 分頁隔離(v19.502),非靜默吞
        from ui.helpers.session import friendly_error as _fe_ref
        _fe_ref("「📖 參考 / 診斷」分頁渲染失敗", _ref_tab_e,
                hint="此分頁已隔離,其他分頁不受影響;請展開「🔧 技術細節」把 traceback"
                     "(含 File \"...\", line N)回報,即可精準定位根因。",
                level="error")
