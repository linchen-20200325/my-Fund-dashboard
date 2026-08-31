#!/usr/bin/env python3
"""app.py — 基金戰情室 v18.0(重構版)
模組架構(2026-08-31 客戶拍板線框,7→5):
  ① 市場定調 → ② 組合健診 → ③ 基金研究 → ④ 我的配置 → ⑤ 設定與診斷
  (③ = 個基深掘 + 批次分析;⑤ = 我的管理室 + 資料診斷 + 說明書)
分頁名一律走 `ui/helpers/story_nav.tab_label()` SSOT,本檔不得再出現字面值。
快取策略(v19.333 對齊實作,review F10):L1 repository 以 @_ttl_cache / @_daily_cache
短 TTL 快取(infra/cache.py _CACHE_REGISTRY 集中註冊),
UI「全域刷新」clear_all_caches() 強制重抓 — 原「零快取」敘述與實作不符,已更正
失敗結果不入快取 — ⚠️ **這句在 2026-08-31 之前是無條件全稱句,而當時是假的**
  (`_ttl_cache` 無條件快取,一次上游瞬斷把空值鎖住整個 TTL)。**現行實況分三種機制**
  (2026-08-31 二次更正:第一版只寫了前兩種,漏掉 @st.cache_data — 同一個「全稱句
   蓋掉例外」的病在同一次修復裡換個位置又犯了一次,故本行改為逐一列出):
  · @_daily_cache — cache_if 預設過濾 None / 空集合 / dict 含 "...all_failed"
    (v19.253 R23)。⚠️ **它不認 mark_fetch_failed 標記** —— 用的是 len()==0 與
    dict 的 source 欄位去**猜**。這與 infra/cache.py module 註解的核心論證
    (「讓裝飾器去猜,猜錯哪一邊都違憲」)**不一致**;就地寫明,不留著裝沒看見。
    實務上它服務的多是回 dict 的 fetcher(有 all_failed marker 可讀),
    但「回空 Series 代表真的沒有」這種情形在它底下仍會被誤判成失敗。
  · @_ttl_cache  — **僅限自己呼叫 infra.proxy.mark_fetch_failed_if_retryable()
    的 fetcher**(現為 fetch_yf_close / fetch_fred / fetch_defillama_stablecoin_mcap),
    且**只對「重試有意義」的四種失敗生效** —— 404 / 407 依 shared/backoff_policy
    的 NO_COOLDOWN_KINDS **照舊入快取**(TTL 是它們唯一的節流器)。
    **其餘未標記的 fetcher 仍會快取空結果。**
  · @st.cache_data — **完全不在本機制涵蓋範圍內,失敗照樣鎖滿 TTL**。
    全 repo 8 個裝飾點,其中 **至少 5 處實測會把失敗鎖住**(⚠️ 本行為 2026-08-31
    **第四次**更正:第一版漏掉 @st.cache_data 整類、第二版只列 2 處、
    第三版寫成「4 處」且把 _cached_nh_coverage 的理由寫成假的 —— 同一段自己在
    檢討的病連犯四次,故本行改為逐處列出、逐處標明判定依據):
      鎖住 → repositories/hot_money_repository.fetch_foreign_flow_series(30 分)
             repositories/hot_money_repository.fetch_usdtwd_series      (10 分)
             repositories/pool_repository._cached_pool_map              (30 分;
               上游 _load_pool_map 自己把例外吞成 {} → 那個空 dict 被快取)
             ui/helpers/macro/ndc._cached_ndc_score                     (15 分)
             ui/tab5_data_guard._cached_nh_coverage                     ( 5 分;
               ⚠️ **第四次更正才補上**,見下)
      不鎖 → ui/helpers/v2_editor ×2(拋 PolicySheetError → 例外不入快取)、
             ui/tab5_data_guard._cached_nh_status(→ status(),只讀 get_secret,
               **確實無外部 HTTP** —— 這半句原本就對,不要跟著改)
    ⛔ **原文把 _cached_nh_coverage 也寫成「無外部 HTTP」,那是假的。**
    實測鏈路:_cached_nh_coverage → services/nav_history_gs.coverage_status
    → 同檔 load_points → _get_sheet() → sh.worksheet()(gspread 內部
    fetch_sheet_metadata)+ ws.get_all_values() —— **全是往返 Google Sheets API
    的遠端呼叫**。且 load_points 內層有 try: ws = sh.worksheet(...) / except: return []
    → 失敗回 {} 並入快取,實測第 2 次呼叫**上游未重跑** → **鎖 TTL_5MIN**。
    ⚠️ **本 repo 憲法 §8.2.A.1 已於 2026-08-28 第三輪稽核就地改寫過同一句措辭**,
    該處明寫「舊表述把它寫進『本地持久化』的括號裡,會讓讀者以為它不上網 ——
    **那是假的**」,並附逐成員表釘死 _cached_nh_coverage 遠端往返=是、
    _cached_nh_status=否。**憲法三天前已明文更正掉的假措辭,被我原樣寫回一次。**
    ⚠️ **這 8 處的清單與「鎖不鎖」的判定都是逐一實測跑出來的,不是讀 code 推定**
    (⚠️ 若只數 raw HTTP 會把 foreign_flow / pool_map / nh_coverage 三處都誤判成
     「未觸發」—— 它們的失敗都發生在 **HTTP 層之上**:一個在 fetch_url_with_retry、
     一個被上游吞成 {}、一個在 gspread SDK 內)。
    ⚠️ **清單來自字面掃描**;⚠️ **該指令直接跑會得 9 行**(多一個 SPEC.md 的文件範例),
    **必須加 `-- '*.py'` 才重現「8」**:
    (`git grep -nE "^[[:space:]]*@[A-Za-z_][A-Za-z0-9_]*\\.(cache_data|cache_resource)" -- '*.py'`)
    **且未涵蓋動態註冊 / getattr / 條件式套用等非字面寫法** —— 不得讀成「就這 8 處」。
    ⚠️ **ui/tab5_data_guard.py 在本 PR 的三次不同查核裡各被漏一次**
    (fetch_url caller 數、本清單、407 紅字出口)。**同一個檔、三次,不是巧合** ——
    它是**唯一同時有「診斷用 HTTP 呼叫 + 自建 cache + 錯誤紅字」的檔**,
    剛好落在每一種掃描字表的邊緣。**下次做這類窮舉時,這個檔要單獨看一遍。**
    本批**刻意不修**(機制不同:回傳 tuple 承載不了 .attrs、@st.cache_data 也不看標記),
    已登記為獨立待辦,使用者可見影響見 PR「刻意沒做」段。
  刻意做成 opt-in 而非預設過濾:「空」有「抓失敗」與「真的沒有」兩義、回傳值
  分不出來,讓裝飾器去猜任一邊都違 §1 — 機制、判準與各分支理由見
  infra/cache.py 的 module 註解與 infra/proxy.py::mark_fetch_failed_if_retryable
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
from ui.tab3_portfolio import render_portfolio_tab
# v19.314:危機回測室(tab_crisis_backtest + crisis_strategy_grid + crisis_ai_advisor)
# 自 v19.31 起即註解停用、進不去;user 確認不用 → 整功能拔除(2798 LOC)。
# ~~註:services/crisis_backtest.py(CrisisEvent/detect_crisis_events)保留,macro/calibration 仍用。~~
# ⚠️ 2026-08-31 狀態更新 + 事實更正,**不是漏刪**(WP-F 順手修;純註解、零行為影響)。
# 上面那句有**兩處與實況不符,而且是兩種不同的錯**,故分開講:
#   (1)「**macro** 仍用」—— **寫下當天就已經是假的,與任何後續刪碼無關**。
#       實測(AST,量測日 2026-08-31):`services/macro/` 底下**沒有任何一處
#       import `services.crisis_backtest`**;唯一命中的 `services/macro/validation.py`
#       是在 **docstring 裡提到它的名字**(「與既有 …detect_crisis_events 輸出對齊」),
#       那是設計說明,不是相依。**把 grep 命中的字串當成 import,正是這句話出錯的那一步。**
#   (2)「**calibration** 仍用」—— **寫下當時為真,但正在失效中**:
#       `services/calibration/multi_factor.py` 確實 `from services.crisis_backtest
#       import CrisisEvent`,而該檔已由 **#743 死碼清理(production 0 caller)**
#       提出整檔刪除、**稽核中、尚未合併**。
#       ⚠️ 本註解**刻意不寫成「已刪」** —— #743 合併前那是未來式,依 §-2 規則 6
#       不得把未落地的事寫成既成事實。#743 合併後,本項改為「已隨 #743 退場」。
#   (3) 它**漏掉了真正讓 crisis_backtest.py 活著的那個消費者**:
#       `ui/helpers/fund_grp_health/capture.py` → `from services.crisis_backtest
#       import fetch_market_series`(上/下檔捕捉率的基準抓取)。
#       **這一條與 #743 無關** —— 所以 `services/crisis_backtest.py` 在 #743
#       合併之後**依然要保留**,不是孤兒。
# → 現行讀法:`services/crisis_backtest.py` 保留;production 消費者是
#   **`ui/helpers/fund_grp_health/capture.py`**(＋ #743 合併前的
#   `services/calibration/multi_factor.py`)。
#   ⚠️ 消費者清單是**會漂移的量測值**,需要時**現場量測**,不要引用本行。查證方式:
#   `git grep -n "crisis_backtest" -- '*.py'` 後**逐一判讀是 import 還是 docstring 提及**
#   —— 只看 grep 命中數,就會複製 (1) 的錯誤。
from ui.tab_fund_grp_health import render_fund_grp_health_tab  # noqa: E402
# 2026-08-31 七→五接線:③ 與 ⑤ 是**合併頁**,由它們自己去 lazy import 五個舊入口
# (render_single_fund_tab / render_batch_analysis_tab / render_manage_tab /
#  render_data_guard_tab / render_manual_tab)。本檔**刻意不再直接 import 那五個** ——
# 留著會讓「app.py 到底掛了幾個入口」有兩種讀法,而那正是本次要消滅的東西。
from ui.tab_fund_research import render_fund_research_tab  # noqa: E402  (③ 基金研究)
from ui.tab_settings_diag import render_settings_diag_tab  # noqa: E402  (⑤ 設定與診斷)

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


# v18.136: _update_data_registry 搬至 ui/helpers/data_registry.py。
# 2026-08-31 七→五接線:本檔**不再 import、也不再呼叫**它 —— 它的唯一 caller 契約
# (「呼叫 render_data_guard_tab 前先更新註冊表」)已隨資料診斷一起搬進
# `ui/tab_settings_diag.py::_render_diag_section`,且**在 checkbox gate 之後**才跑。
# 留在這裡等於每次 rerun 都無條件更新註冊表(內含一次真的打網路的 USDTWD 抓取),
# 而使用者可能根本沒打開 ⑤。全 repo 無人 `from app import _update_data_registry`
# (2026-08-31 實測 grep,單組結論),故一併移除 import。


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
# 沿革(為什麼是 5 個、為什麼分頁名一定要走 SSOT)——舊條文保留,理由仍然成立:
# v19.130 舊 6-tab 故事化動線 → v19.405 Phase 4(IA 重分類 6→5)分頁改照「決策動線」
# 排序 + 命名,支援型的「資料診斷 + 說明書」合成一個「參考 / 診斷」分頁。
# 2026-08-05 稽核 必修 2:決策動線四站的分頁名改吃 `ui/helpers/story_nav` SSOT。
# 原本 app.py 與 story_nav 各寫死一份,導致各 Tab 的「請至 X 分頁」指路文案改名後
# 對不上(§3.3 反捏造)。
# 2026-08-14：原本「📦 批次分析 / 📋 我的管理室 / 📖 參考 / 診斷」三個因為
# 「不在決策動線 4 站內」而保留字面值 —— 但那理由只解釋了它們**不需要序號前綴**,
# 不代表分頁名可以有第二份來源。實機稽核在 sidebar 又抓到三處指路文案指向不存在
# 的分頁名(同一種病第二次發作)。故頂層分頁名全部收進 story_nav。
#
# ── 2026-08-31：七 → 五（客戶拍板線框 `docs/wireframes/fund-wireframe-final.html`）──
# ① 🌐 市場定調 / ② 💊 組合健診 / ③ 🔍 基金研究 / ④ 📊 我的配置 / ⑤ ⚙️ 設定與診斷
#   ③ = 舊「個基深掘」+「批次分析」(ui/tab_fund_research.py,單一模式切換鍵)
#   ⑤ = 舊「我的管理室」+「參考 / 診斷」內的資料診斷與說明書
#       (ui/tab_settings_diag.py,單頁 + 目錄錨點,**不再有巢狀 st.tabs**)
# ⚠️ 巢狀 st.tabs 一併消失 —— 舊「參考 / 診斷」是全站唯一的三層巢狀分頁入口。
#     檔首 CSS 那條「把巢狀 tab-list 還原 static」的規則**刻意保留**:說明書
#     (`ui/tab6_manual.py`)自己仍有一層 st.tabs,規則失效只會回到現況、不會壞。
from ui.helpers.story_nav import tab_label as _tab_label

# ⭐ 「🔍 抓取診斷細節」的所有權必須由**本檔**持有,不能讓 ⑤ 自己 with ——
#    這是七→五接線唯一一個「不做就會畫兩份」的地方,理由寫死在這裡:
#    旗標是 thread-local context manager(`ui/helpers/settings_diag/merge_context.py`),
#    只在 `with` 區塊內成立;而 Streamlit 的 `st.tabs` **一次 run 會把五個分頁的
#    body 全部執行過**,順序就是下面 with 區塊的順序 —— ③ 跑在 ⑤ 之前。
#    ⑤ 就算把自己整個包起來,那時 ③ 早就跑完了,回頭關不掉它已經畫出去的那一份。
#    → 由 app.py 在**進入第一個分頁之前**就宣告持有,五個分頁全程有效:
#      ③ 底下的 `ui/tab2_single_fund.py` 看到旗標 → 跳過那一塊;
#      ⑤ 的 `render_fetch_diag_from_session()` 是無條件渲染 → 全站只剩它那一份。
#    守衛:`tests/test_wpf_five_tab_wiring.py::test_fetch_diag_is_owned_by_app`
#         (突變:拿掉這個 with → 轉紅)。
from ui.helpers.settings_diag.merge_context import (  # noqa: E402
    FETCH_DIAG as _SD_FETCH_DIAG,
    settings_page_owns as _settings_page_owns,
)

tab_macro, tab_health, tab_research, tab_portfolio, tab_settings = st.tabs(
    [_tab_label("macro"), _tab_label("health"), _tab_label("research"),
     _tab_label("portfolio"), _tab_label("settings")])


# ⚠️ 五段 try/except **刻意逐段展開,不收成 helper** —— 這是一次「本來想收、實測之後
#    決定不收」的取捨,理由寫下來免得下一個人又想收一次:
#    (a) `tests/test_macro_tab_section_isolation.py::test_app_macro_tab_isolation_guard`
#        與 `tests/test_tab_isolation_v19502.py::test_every_tab_block_has_try_except`
#        要求 `with tab_*:` 的 body **第一層就看得到 `Try` 節點**。收成 helper 之後
#        try 躲進函式裡,那兩條守衛會轉紅 —— 而它們守的是 user 2026-08-21 實際回報過
#        的事故(「每個 Tab 小按鈕壓下就整個跳出來」),不該為了少寫幾行而讓它失效。
#    (b) 重複的**只有 try/except 骨架**;真正會漂移的東西(分頁名)已經走
#        `_tab_label(...)` SSOT,不再是五份手抄的中文字面值 —— 原本那五段各帶一份
#        「「🌐 市場定調」分頁渲染失敗」,分頁一改名就會有人漏改。
#    守衛:`tests/test_wpf_five_tab_wiring.py::test_tab_error_titles_go_through_tab_label`
#         (突變:把任一段的標題改回寫死字串 → 轉紅)。
_TAB_ISOLATION_HINT = ("此分頁已隔離,其他分頁不受影響;請展開「🔧 技術細節」把 traceback"
                       "(含 File \"...\", line N)回報,即可精準定位根因。")


# ⚠️ 這個 `with` 必須包住**全部五個**分頁(理由見上方 ⭐ 區塊)。
with _settings_page_owns(_SD_FETCH_DIAG):
    # ══════════════════════════════════════════════════════
    # TAB ① — 🌐 市場定調（決策動線第 1 站:加碼或防禦）
    # ══════════════════════════════════════════════════════
    with tab_macro:
        # §1 分頁隔離（v19.429）：st.tabs 單次 run 渲染全部分頁,任一分頁若拋未捕捉
        # 例外會中止整個 script → 其後所有分頁空白。外層 try 保證「一頁失敗不連坐
        # 其他頁」;內層各頁自己的 section 級隔離再做細粒度切分。
        # ⚠️ 2026-08-31 WP-F 就地更正(**有意識的更正,不是漏刪** · 決策者:AI 總管):
        #    舊句 ~~「內層各頁自己的 _safe_section 再做 section 級細粒度隔離」~~
        #    在寫下的當天對 ① 成立(`ui/tab1_macro.py::_safe_section`),但對**新合併的
        #    ③ 與 ⑤ 為假** —— 那兩頁當時一個 section 級 try 都沒有。七→五之後
        #    ⑤ 一頁裝著管理室 + 資料診斷 + 說明書:管理室當掉會**一併帶走**使用者
        #    出事時要去查的那兩塊。已於同批補上(`ui.helpers.render_state.safe_section`),
        #    本句自此為真。⚠️ ② 與 ④ **仍未逐 section 隔離**(它們自己有頁內 try/except,
        #    但不是統一的 section 級)—— 據實登記,本批未受指派、§-1 無觸發,未動。
        # 非靜默吞:friendly_error 顯式顯示 + stderr 鏡射進 Cloud log + traceback。
        #
        # 🧭 總經指南針:整條鏈已於 2026-08-05 移除(見本檔上方沿革區塊)。此處不再有
        # 任何指南針呼叫,元件模組本身也已退役 —— 在此還原呼叫會直接 ImportError。
        try:
            render_macro_tab()
        except Exception as _macro_tab_e:  # noqa: BLE001 — §1 分頁隔離,非靜默吞
            from ui.helpers.session import friendly_error as _fe_macro
            _fe_macro(f"「{_tab_label('macro')}」分頁渲染失敗", _macro_tab_e,
                      hint=_TAB_ISOLATION_HINT, level="error")

    # ══════════════════════════════════════════════════════
    # TAB ② — 💊 組合健診（決策動線第 2 站:手上哪幾檔健康 / 吃本金）
    # 以 100 萬 TWD 為基準逐檔模擬:原幣本金 / 持有份額 / 逐期配息折算 TWD / 吃本金判定。
    # ══════════════════════════════════════════════════════
    with tab_health:
        try:
            render_fund_grp_health_tab()
        except Exception as _health_tab_e:  # noqa: BLE001 — §1 分頁隔離,非靜默吞
            from ui.helpers.session import friendly_error as _fe_health
            _fe_health(f"「{_tab_label('health')}」分頁渲染失敗", _health_tab_e,
                       hint=_TAB_ISOLATION_HINT, level="error")

    # ══════════════════════════════════════════════════════
    # TAB ③ — 🔍 基金研究（決策動線第 3 站:還沒放進組合前,查一檔或掃一批的體質）
    # 合併頁(2026-08-31 七→五):共用「找代號」頂部 + 單一模式切換鍵
    # (🔍 單檔深掘 / 📦 批次掃描),**不是第二層分頁**。
    # 批次面板另有 checkbox gate —— 全站唯一 30~40 分鐘的長任務,切過來不會開跑。
    # ══════════════════════════════════════════════════════
    with tab_research:
        try:
            render_fund_research_tab()
        except Exception as _research_tab_e:  # noqa: BLE001 — §1 分頁隔離,非靜默吞
            from ui.helpers.session import friendly_error as _fe_research
            _fe_research(f"「{_tab_label('research')}」分頁渲染失敗", _research_tab_e,
                         hint=_TAB_ISOLATION_HINT, level="error")

    # ══════════════════════════════════════════════════════
    # TAB ④ — 📊 我的配置（決策動線第 4 站:記帳 + 再平衡）
    # ══════════════════════════════════════════════════════
    with tab_portfolio:
        try:
            render_portfolio_tab()
        except Exception as _portfolio_tab_e:  # noqa: BLE001 — §1 分頁隔離,非靜默吞
            from ui.helpers.session import friendly_error as _fe_portfolio
            _fe_portfolio(f"「{_tab_label('portfolio')}」分頁渲染失敗", _portfolio_tab_e,
                          hint=_TAB_ISOLATION_HINT, level="error")

    # ══════════════════════════════════════════════════════
    # TAB ⑤ — ⚙️ 設定與診斷（支援區:連線與帳號 / 資料維護與通報 / 資料診斷 / 說明書）
    # 合併頁(2026-08-31 七→五):單頁 + 目錄錨點,**不再有巢狀 st.tabs**。
    # 資料診斷整區在 checkbox gate 之後(含 `_update_data_registry()` 與那次
    # 無條件的匯率抓取)—— 本檔因此不再自己呼叫 `_update_data_registry()`。
    # v19.31 ARCHIVED: 📉 危機回測室,模組檔保留於磁碟,未來啟用解註即可。
    # ══════════════════════════════════════════════════════
    with tab_settings:
        try:
            render_settings_diag_tab()
        except Exception as _settings_tab_e:  # noqa: BLE001 — §1 分頁隔離,非靜默吞
            from ui.helpers.session import friendly_error as _fe_settings
            _fe_settings(f"「{_tab_label('settings')}」分頁渲染失敗", _settings_tab_e,
                         hint=_TAB_ISOLATION_HINT, level="error")
