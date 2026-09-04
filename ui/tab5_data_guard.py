"""ui/tab5_data_guard.py — 資料診斷 Tab（v18.125 B-C.3）

從 app.py 抽出 Tab5（資料診斷）的渲染邏輯。

設計準則：
- render_data_guard_tab() -> None **零閉包依賴**（與 Tab4/Tab6 相同）
- 外部 helper 處理：
  * _update_data_registry() → caller (app.py) 在呼叫本函式前先 call
  * _parse_indicator_date → 從 ui.helpers.session import(v19.339:_calc_data_health wrapper 已刪,本檔 0 呼叫)
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
from shared.session_keys import HM_CARD_SESSION_KEYS as _HM_K3
from shared.ui_control_labels import (
    DATA_GUARD_HOT_MONEY_BTN as _LBL_D5_HOT_MONEY,
    DATA_GUARD_RELOAD_MACRO_BTN as _LBL_D5_RELOAD_MACRO,
)

from ui.helpers.ia import applied_form
from ui.helpers.render_state import not_ready, system_error

from shared.colors import BG_DARK_AMBER_2, BG_DARK_GREEN_1, BG_DARK_NAVY_3, BG_DARK_NAVY_4, BG_DARK_RED_2, GH_BG_CARD, GH_BG_HOVER, GH_BG_PRIMARY, GH_BORDER, GH_FG_PRIMARY, GRAY_55, GRAY_66, GRAY_AA, GRAY_BB, MATERIAL_GREEN, MATERIAL_ORANGE, MATERIAL_RED, MD_BLUE_300, STREAMLIT_BG, TRAFFIC_GREEN, TRAFFIC_NEUTRAL, TRAFFIC_RED, TRAFFIC_YELLOW  # v19.390 V3b:燈號收 TRAFFIC SSOT

from infra.proxy import get_proxy_config
from shared.converters import safe_float as _safe_float
from shared.signal_thresholds import TRADING_DAYS_PER_YEAR as _TD_1Y
from shared.ttls import TTL_5MIN  # 稽核 N1-d:TTL 走 SSOT,不在本檔寫死秒數
from ui.helpers.session import (
    parse_indicator_date as _parse_indicator_date,  # noqa: F401 — re-export for tests
)

_TW_TZ = ZoneInfo("Asia/Taipei")


def _now_tw():
    return datetime.datetime.now(_TW_TZ)


# ── 稽核 N1-d：nav_history 狀態查詢加 TTL 快取 ────────────────────────────────
# 原碼在「🗂️ NAV 歷史匯入與累積狀態」區塊直接呼叫 `nav_history_gs.status()` 與
# `coverage_status()`，兩者：
#   (a) 都會建 Service Account client + 讀 Google Sheets（`coverage_status` 讀整張
#       `nav_history` 分頁）；
#   (b) 服務層**沒有任何 cache**；
#   (c) 該區塊 v19.362 刻意從 expander 改成 `st.container()` —— 理由正確（狀態燈
#       不該可被收起來），但副作用是它變成**無條件執行**；
#   (d) `app.py:205` 自承「st.tabs 單次 run 渲染全部分頁」。
# 四者相乘 = 使用者在任何分頁做任何一次互動，都會打兩次 Google Sheets。
# 25 檔實測：rerun 起算 17 秒後 `WebSocket onclose`（2026-08-14 實機兩次重現）。
#
# 對策：在 L3 加薄快取層（TTL 走 shared/ttls.py SSOT，不寫死秒數）。狀態燈本身
# 仍常駐顯示 —— 這裡只擋掉「每次互動都重打 API」，不改變任何顯示語意。
# 寫入路徑（import_csv_text）成功後會顯式清這兩個快取，避免顯示舊的累積點數。
@st.cache_data(ttl=TTL_5MIN, show_spinner=False)
def _cached_nh_status() -> dict:
    from services.nav_history_gs import status as _s
    return _s()


@st.cache_data(ttl=TTL_5MIN, show_spinner=False)
def _cached_nh_coverage() -> dict:
    from services.nav_history_gs import coverage_status as _c
    return _c()


def _clear_nh_caches() -> None:
    """匯入寫入後呼叫 —— 否則畫面會顯示寫入前的累積點數（§1 不顯示過期值）。"""
    _cached_nh_status.clear()
    _cached_nh_coverage.clear()

# v19.339(第五份 review):刪死碼 _calc_data_health wrapper + calc_data_health
# import — 本檔 0 呼叫(⓪/②區直接數 indicators),tab1/2/3 各有自己的 wrapper。


# ════════════════════════════════════════════════════════════════
# v19.135 — API Key 遮罩 + secrets 驗證 + 來源解析
# 作法移植自 Stock 端 api_diagnostic.py(學 Stock 偵測精度)
# 解決「Key 已設但全站抓不到」的根因排查:來源 / 遮罩 / TOML 解析
# ════════════════════════════════════════════════════════════════

def _mask_key(val: str) -> str:
    """遮罩中段,保留前 4 + 後 4 字元 + 長度,避免診斷頁洩漏完整 key。"""
    if not val:
        return "(空)"
    s = str(val)
    n = len(s)
    if n <= 8:
        return f'{"*" * n} (len={n})'
    return f"{s[:4]}…{s[-4:]} (len={n})"


def _safe_secret(key: str):
    """安全讀 st.secrets[key]。回傳 (value, error_str)。TOML 解析錯不 raise。"""
    try:
        sec = getattr(st, "secrets", None)
        if sec is None:
            return None, "st.secrets 不存在"
        if key in sec:
            return sec[key], None
        return None, None
    except Exception as e:  # noqa: BLE001 — TOML parse error 等
        return None, f"{type(e).__name__}: {e}"


def _resolve_key(key: str) -> dict:
    """回傳一把 key 的完整解析:來源 / 值 / 遮罩 / 錯誤。

    優先序對齊 app.py:_load_keys(st.secrets 先,os.environ 備)。
    """
    sec_val, sec_err = _safe_secret(key)
    env_val = os.environ.get(key, "")
    if sec_val:
        return {"name": key, "source": "st.secrets", "val": str(sec_val),
                "preview": _mask_key(sec_val), "sec_err": sec_err,
                "env_preview": _mask_key(env_val)}
    if env_val:
        return {"name": key, "source": "os.environ", "val": env_val,
                "preview": _mask_key(env_val), "sec_err": sec_err,
                "env_preview": _mask_key(env_val)}
    return {"name": key, "source": "(無)", "val": "",
            "preview": "(未設定)", "sec_err": sec_err,
            "env_preview": _mask_key(env_val)}


def _get_holdings(fd: dict) -> dict:
    """持股物件統一取值路徑(B7 v19.332,review 監控盲區)。

    原三處判定路徑不一致(Section ⓪ 只看頂層 `holdings`、Section ① pf 看
    `moneydj_raw.holdings` / cf 看頂層、Section ⑤ 只看 moneydj_raw)→ 同一檔
    基金在不同 section 計數可能不同(統計偏差)。統一語意:頂層優先、
    moneydj_raw 補位(對齊 dividends 既有雙路徑 fallback 精神)。
    """
    if not fd:
        return {}
    return (fd.get("holdings")
            or (fd.get("moneydj_raw") or {}).get("holdings")
            or {})


def anomaly_view_state(registry: dict | None) -> tuple[str, list]:
    """Section ⑥「資料異常清單」的三態決策（純函式，供渲染端與測試共用）。

    回傳 `(state, items)`：
    - `"empty"`      — registry 空 → **還沒量**，不可宣稱正常（§1）
    - `"clean"`      — 有登錄資料且全部健康
    - `"anomaly"`    — 有異常項，`items` 為排序後的 `(key, meta)`

    🟡 分兩類：(a) 真延遲 (b) FRED release 期已到 +5d 內；後者屬正常 release
    window，不列入異常。

    稽核 C1（2026-08-14 修）
    -----------------------
    原本 (b) 的排除條件是 `"release 期已到" not in fresh_label`，但
    `data_registry._freshness` 產生的 🟡 label 實際是
    `"release lag N 天（預期 YYYY-MM-DD）"` —— **兩邊字面值從來沒對上**
    （已窮舉 `_freshness` 全部 14 種 return label 逐一比對確認）。
    條件恆為 True ⇒ 每次 FRED 月度指標發布後的 +2~+5 天，一批完全正常的 🟡
    會被列進「資料異常清單」，而 `st.success("✅ 全數正常")` 永遠不出現；
    同時本頁下方還白紙黑字寫著「release window 內的 🟡 已自動排除」。
    改吃 `RELEASE_WINDOW_LABEL_PREFIX` SSOT，由
    `tests/test_release_window_label.py` 鎖住兩端漂移。
    """
    from ui.helpers.io.data_registry import RELEASE_WINDOW_LABEL_PREFIX

    if not registry:
        return "empty", []
    items = [(k, v) for k, v in registry.items()
             if v.get("fresh_icon") == "🔴"
             or (v.get("fresh_icon") == "🟡"
                 and not str(v.get("fresh_label") or "").startswith(
                     RELEASE_WINDOW_LABEL_PREFIX))]
    items.sort(key=lambda kv: (
        0 if kv[1].get("fresh_icon") == "🔴" else 1,
        kv[1].get("label", kv[0]),
    ))
    return ("anomaly" if items else "clean"), items


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
        # ⑤ 設定與診斷合併頁（線框 §03 ⑤，WP-E）已畫分區標題時，這裡不再畫第二個 `##`。
        # 只讓掉標題那一行 —— caption / info / 右側按鈕一律照舊。
        # ~~旗標全空（現況，⑤ 未接線）→ 本頁行為與現在完全相同。~~
        # ⚠️ 2026-08-31 WP-F 接線後就地更正（**有意識的更正，不是漏刪** · 決策者：AI 總管）：**這句話現在是假的。** ⑤ 已接線，
        # 本函式的 production caller 是 `ui/tab_settings_diag.py::_render_diag_section()`
        # （在 `sd_diag_gate` checkbox 之後），它永遠帶著
        # `settings_page_owns(DATA_GUARD_HEADER)` → 下方畫 `##` 大標的分支
        # 在 production **恆不觸發**。分支刻意保留（契約實作，同 tab_manage）。
        from ui.helpers.settings_diag.merge_context import (
            DATA_GUARD_HEADER as _SD_DATA_GUARD_HEADER,
            NAV_HISTORY as _SD_NAV_HISTORY,
            owned_by_settings_page as _settings_page_owns,
        )
        if not _settings_page_owns(_SD_DATA_GUARD_HEADER):
            st.markdown("## 🔬 資料診斷")
        st.caption("📖 故事幕後站・資料守衛：投資決策背後的數據如何被抓取與守護 — 確認所有來源成功下載，方便排查問題")
        st.info(
            "🔧 **本頁大部分是維運診斷內容**（secrets / TOML 解析錯誤、NAS Proxy 連線測試、"
            "expanding window 樣本量、FRED release schedule…）。\n\n"
            "**一般使用只需要看兩個地方**：最上方 **⓪ 前 4 Tab 資料完整性檢查表**"
            "（哪個 Tab 缺資料）與最下方 **⑥ 資料異常清單**（哪些資料過期）。"
            "中間各區塊在你沒遇到問題時可以完全略過。"
        )
    with _d5_btn:
        st.markdown("<div style='margin-top:20px'></div>", unsafe_allow_html=True)
        if st.button(_LBL_D5_RELOAD_MACRO, key="btn_d5_refresh"):
            # ── 2026-09-04 第四輪稽核 R4-F4:這是**第五個**總經刷新入口 ──────────
            # A5 那一輪盤點出「三個入口」並宣稱都接上了,實測漏了這一顆:它把
            # `macro_done` 設回 False 讓整頁重載,**卻什麼快取／閘門都沒清** ——
            # 使用者按了「重新載入總經」,Tab ① 那張熱錢卡照樣抱著上一輪的失敗結果。
            # 它就在 A5 修好的那顆按鈕**上方 250 行、同一個檔案裡**。
            # ⚠️ 舊守衛是一份**列舉兩個入口的** parametrize —— 結構上不可能發現
            # 第三個入口;現在改成**結構性列舉**(掃所有把 `macro_done` 設 False
            # 的地方),見 `tests/test_batch2_top_card_grid.py`。
            for _hm_k3 in _HM_K3:
                st.session_state.pop(_hm_k3, None)
            st.session_state.macro_done = False
            st.rerun()

    _src_ind  = st.session_state.get("indicators") or {}
    _src_news = st.session_state.get("news_items") or []
    _src_cf   = st.session_state.get("current_fund") or st.session_state.get("fund_data") or {}
    _src_pf   = st.session_state.get("portfolio_funds") or []
    _src_pf_loaded = [f for f in _src_pf if f.get("loaded")]

    # ════════════════════════════════════════════════════════════
    # v19.131 Section 0 — 📊 前 4 Tab 資料完整性檢查表
    # User 2026-06-25 反饋:「資料診斷應該要去捕捉前面 Tab 的所有資料都有被抓取到」
    # 一眼看 Tab1/2/3/4 各需要什麼資料、現在抓到多少
    # ════════════════════════════════════════════════════════════
    st.markdown("### ⓪ 📊 前 4 Tab 資料完整性檢查表")
    st.caption("快速確認 4 個資料 Tab 各自的關鍵資料是否都已抓到 — 紅燈 = 缺資料,該 Tab 可能渲染不完整")

    # v19.195 SSOT:改 import ui.helpers.session.D5_FRED_KEYS / D5_YF_KEYS,
    # 取代原 hardcoded 12 + 4(同一份清單在本檔出現 2 次 + session.py 1 次 = 3 處重複)。
    from ui.helpers.session import D5_FRED_KEYS as _FRED_REQUIRED
    from ui.helpers.session import D5_YF_KEYS as _YF_REQUIRED
    _all_macro = list(_FRED_REQUIRED) + list(_YF_REQUIRED)
    _macro_have = sum(1 for k in _all_macro if (_src_ind.get(k) or {}).get("value") is not None)
    _macro_total = len(_all_macro)

    # 缺值清單顯示用中文名。原本直接印 internal key（PMI / YIELD_10Y2Y / SLOOS…），
    # 使用者看不懂哪個指標沒抓到、也就無從判斷該不該在意。
    # 取數優先序：indicators dict 內建的 `name`（總經抓取時附） → 本地對照表 → key 本身。
    _D5_ZH = {
        "PMI": "製造業 PMI", "YIELD_10Y2Y": "殖利率利差 10Y-2Y",
        "YIELD_10Y3M": "殖利率利差 10Y-3M", "HY_SPREAD": "高收益債信用利差",
        "M2": "M2 貨幣供給", "FED_BS": "Fed 資產負債表",
        "CPI": "消費者物價 CPI", "FED_RATE": "聯邦資金利率",
        "UNEMPLOYMENT": "失業率", "PPI": "生產者物價 PPI",
        "SAHM": "薩姆規則（衰退預警）", "SLOOS": "銀行放貸標準",
        "VIX": "VIX 恐慌指數", "DXY": "美元指數 DXY",
        "ADL": "市場廣度 RSP/SPY", "COPPER": "銅價（銅博士）",
    }

    def _macro_zh(key: str) -> str:
        _nm = (_src_ind.get(key) or {}).get("name")
        return f"{_nm or _D5_ZH.get(key, key)}（{key}）"

    _cf_have_nav  = bool(_src_cf and _src_cf.get("series") is not None)
    _cf_have_meta = bool(_src_cf and (_src_cf.get("fund_name") or _src_cf.get("name")))
    _cf_have_div  = bool(_src_cf and (_src_cf.get("dividends") or (_src_cf.get("moneydj_raw") or {}).get("dividends")))
    _cf_have_holdings = bool(_src_cf and _get_holdings(_src_cf).get("top_holdings"))  # B7 v19.332 統一路徑
    _single_have = sum([_cf_have_nav, _cf_have_meta, _cf_have_div, _cf_have_holdings])
    _single_total = 4

    _pf_total = len(_src_pf)
    _pf_loaded_n = len(_src_pf_loaded)
    _pf_nav_n = sum(1 for f in _src_pf_loaded if f.get("series") is not None)
    _pf_div_n = sum(1 for f in _src_pf_loaded
                    if (f.get("dividends") or (f.get("moneydj_raw") or {}).get("dividends")))

    # v19.194 修假紅燈:`usdtwd_rate` / `policy_funds` 這 4 個 session key
    # 整個 codebase 從未被任何代碼 set 過(grep 確認),原邏輯導致 Tab 4 永遠紅燈
    # 與實際資料健康度無關。
    # - FX:直接呼 cached get_latest_fx('USDTWD')(positive-only cache + 5min TTL,
    #   render 時若 cache 命中為純 dict lookup)
    # - 政策:真實檢查 (a) gservice_account secret(SA 模式),(b) OAuth configured
    #   + gsheet_tokens(OAuth 模式),(c) 兩者皆無才算 ✗
    try:
        from services.fund_service import get_latest_fx as _get_fx
        _fx_rate = _get_fx("USDTWD")
    except Exception:
        _fx_rate = None
    try:
        from ui.helpers.oauth_state import (
            _gsa_secret as _gs_sa_secret,
            _oauth_configured as _gs_oauth_cfg_ok,
        )
        _has_sa = bool(_gs_sa_secret)
        _has_oauth_login = bool(_gs_oauth_cfg_ok and st.session_state.get("gsheet_tokens"))
        _gs_policy = _has_sa or _has_oauth_login
    except Exception:
        _gs_policy = False
    _alloc_have = sum([_pf_loaded_n > 0, bool(_fx_rate), bool(_gs_policy)])
    _alloc_total = 3

    def _tab_status(have: int, total: int) -> tuple[str, str]:
        """回傳 (emoji, color) 依完整率"""
        if total == 0:
            return ("⬜", GRAY_66)
        _r = have / total
        if _r >= 0.85:
            return ("🟢", TRAFFIC_GREEN)
        elif _r >= 0.5:
            return ("🟡", TRAFFIC_YELLOW)   # v19.390 V3b:🟡 燈原配 MATERIAL_ORANGE(橘)→ 修為 TRAFFIC 黃,icon/色一致
        else:
            return ("🔴", TRAFFIC_RED)

    _t1_emoji, _t1_color = _tab_status(_macro_have, _macro_total)
    _t2_emoji, _t2_color = (
        _tab_status(_single_have, _single_total) if _src_cf else ("⬜", GRAY_66)
    )
    _t3_emoji, _t3_color = (
        _tab_status(_pf_loaded_n, _pf_total) if _pf_total else ("⬜", GRAY_66)
    )
    _t4_emoji, _t4_color = (
        _tab_status(_alloc_have, _alloc_total) if _pf_total else ("⬜", GRAY_66)
    )

    from ui.helpers.story_nav import where_to_find as _wtf
    def _wtf_health() -> str: return _wtf("health")
    def _wtf_portfolio() -> str: return _wtf("portfolio")

    _tab_table = [
        ("🌐 Tab 1 總經", _t1_emoji, _t1_color,
         f"{_macro_have}/{_macro_total} 指標",
         f"FRED {len(_FRED_REQUIRED)} / Yahoo {len(_YF_REQUIRED)} ｜ 缺值:"
         + (', '.join(_macro_zh(k) for k in _all_macro
                      if not (_src_ind.get(k) or {}).get('value')) or '無'),
         "若 < 85% → 按上方「重新載入總經」"),
        ("🔍 Tab 2 單一基金", _t2_emoji, _t2_color,
         f"{_single_have}/{_single_total} 欄位" if _src_cf else "未查",
         (f"NAV {'✓' if _cf_have_nav else '✗'} ｜ Meta {'✓' if _cf_have_meta else '✗'} ｜ "
          f"配息 {'✓' if _cf_have_div else '✗'} ｜ 持股 {'✓' if _cf_have_holdings else '✗'}")
         if _src_cf else "在 Tab 2 查詢基金代號觸發",
         "若 NAV ✗ → 檢查 MoneyDJ / Cnyes / TDCC fallback chain"),
        # ⚠️ 只有這一列走 SSOT，其餘三列**刻意未動** —— 它們是 `_KNOWN_DEBT` 已登記的
        #    既有債（「整張表重寫」在該表被明記為 scope 決定，不是本批能自己拍板的）。
        #    本列非改不可的理由：2026-09-01 改名把它從「站號錯」升級成「名字也不存在」，
        #    而它是**本批自己造成**的那一種，屬本批的收尾義務。
        #    ⚠️ 因此本表目前是混合風格（本列「② 💊 持倉體檢」vs 其餘「🌐 Tab 1 總經」）——
        #    據實登記，不假裝整齊；整張表要統一得先過 scope gate。
        (_wtf_health(), _t3_emoji, _t3_color,
         f"{_pf_loaded_n}/{_pf_total} 已載入" if _pf_total else "未設定持倉",
         (f"NAV {_pf_nav_n}/{_pf_loaded_n} ｜ 配息 {_pf_div_n}/{_pf_loaded_n}"
          if _pf_loaded_n else f"在 {_wtf_health()} / {_wtf_portfolio()} 加入持倉基金"),
         "若有未載入 → 該基金在 fallback chain 全敗"),
        ("📊 Tab 4 組合配置", _t4_emoji, _t4_color,
         f"{_alloc_have}/{_alloc_total} 元件" if _pf_total else "未設定",
         f"持倉 {'✓' if _pf_loaded_n else '✗'} ｜ FX {'✓' if _fx_rate else '✗'} ｜ Sheet 政策 {'✓' if _gs_policy else '✗'}",
         "FX 失敗 → 上方 Proxy 連線測試;Sheet → sidebar 登入 Google / 設 gservice_account secret"),
    ]

    _tab_th = f"font-size:10px;color:{TRAFFIC_NEUTRAL};font-weight:700;padding:8px 10px;border-bottom:1px solid {GH_BORDER}"
    _tab_td = "font-size:11px;padding:8px 10px;line-height:1.4"
    _t_html = (
        f"<div style='display:grid;grid-template-columns:1.3fr 0.5fr 0.9fr 2.8fr 2fr;"
        f"background:{GH_BG_PRIMARY};border-radius:6px 6px 0 0'>"
        f"<span style='{_tab_th}'>Tab</span>"
        f"<span style='{_tab_th};text-align:center'>狀態</span>"
        f"<span style='{_tab_th}'>覆蓋率</span>"
        f"<span style='{_tab_th}'>細項</span>"
        f"<span style='{_tab_th}'>缺資料時排查</span>"
        f"</div>"
    )
    for _name, _e, _c, _ratio, _detail, _action in _tab_table:
        _bg = BG_DARK_GREEN_1 if _e == "🟢" else (BG_DARK_AMBER_2 if _e == "🟡" else
              (BG_DARK_RED_2 if _e == "🔴" else GH_BG_PRIMARY))
        _t_html += (
            f"<div style='display:grid;grid-template-columns:1.3fr 0.5fr 0.9fr 2.8fr 2fr;"
            f"background:{_bg};border-bottom:1px solid {GH_BG_HOVER}'>"
            f"<span style='{_tab_td};color:{GH_FG_PRIMARY};font-weight:600'>{_name}</span>"
            f"<span style='{_tab_td};text-align:center;color:{_c};font-size:14px'>{_e}</span>"
            f"<span style='{_tab_td};color:{_c};font-weight:600'>{_ratio}</span>"
            f"<span style='{_tab_td};color:{GRAY_BB}'>{_detail}</span>"
            f"<span style='{_tab_td};color:{TRAFFIC_NEUTRAL};font-size:10px'>{_action}</span>"
            f"</div>"
        )
    st.markdown(
        f"<div style='border:1px solid {GH_BORDER};border-radius:6px;overflow:hidden'>"
        f"{_t_html}</div>", unsafe_allow_html=True,
    )
    # 整體狀態 summary
    _all_emojis = [_t1_emoji, _t2_emoji, _t3_emoji, _t4_emoji]
    _n_green = _all_emojis.count("🟢")
    _n_yellow = _all_emojis.count("🟡")
    _n_red = _all_emojis.count("🔴")
    _n_idle = _all_emojis.count("⬜")
    # v19.333 review F8:原「完整率 N/4」只數 🟢 — 3🟢1🟡 與 3🟢1🔴 同顯 3/4
    # 無法區分。🟡(部分資料)以 ½ 計入;0.5 為顯示語意權重,非業務門檻。
    _d5_full_ratio = _n_green + 0.5 * _n_yellow
    st.caption(
        f"全 4 個 Tab|🟢 完整 {_n_green}　🟡 部分 {_n_yellow}　🔴 缺失 {_n_red}　⬜ 未觸發 {_n_idle}　"
        f"完整率 {_d5_full_ratio:g}/4"
    )
    st.divider()

    # ── Section ①: 📥 第一手原始資料源總覽 ──
    st.markdown("### ① 📥 第一手原始資料源總覽")
    st.caption("系統實際下載的所有原始資料端點(依 ARCHITECTURE §5)— 顏色與筆數動態反映 session_state")

    # v19.152:外資/USDTWD 立即更新按鈕(避免 user 為了 refresh 還要點開 📦 ARCHIVED expander)
    # _macro_hot_money 卡舊資料的根因是 v19.47 把 hot_money panel 收進 ARCHIVED,
    # 不點開就不 refetch。本按鈕直接觸發 fetch + stash,提供獨立 refresh 路徑。
    _hm_existing = st.session_state.get("_macro_hot_money") or {}
    _hm_date = _hm_existing.get("date", "") if isinstance(_hm_existing, dict) else ""
    _hm_age_txt = ""
    if _hm_date:
        try:
            import datetime as _dt_hm_btn
            _hm_dt = _dt_hm_btn.date.fromisoformat(str(_hm_date)[:10])
            _today_tw = _dt_hm_btn.datetime.now(
                _dt_hm_btn.timezone(_dt_hm_btn.timedelta(hours=8))
            ).date()
            _age = (_today_tw - _hm_dt).days
            _hm_age_txt = f"(目前資料 {_age} 天前)"
        except (ValueError, TypeError):
            pass
    _bc1, _bc2 = st.columns([2, 5])
    with _bc1:
        _refetch_btn = st.button(
            _LBL_D5_HOT_MONEY,
            key="btn_refetch_hot_money_v19152",
            help="直接觸發 hot_money fetch + 寫 session_state._macro_hot_money。"
                 "不必點開 📦 ARCHIVED 台股熱錢監測 expander。",
            use_container_width=True,
        )
    with _bc2:
        st.caption(
            f"🇹🇼 外資買賣超 × USDTWD 同步判讀 {_hm_age_txt}|"
            f"v19.47 後 panel 收進 ARCHIVED expander,本按鈕為獨立 refresh 路徑。"
        )
    if _refetch_btn:
        try:
            # v19.342:fetch+stash 邏輯抽至 ui.hot_money.refresh_hot_money_data
            # (與 tab1 長期桶 >30 天自動補抓共用同一條資料路),本按鈕只留 UI 殼。
            # 2026-09-04 稽核 F3:token 讀取改走 `infra.config.get_secret`(§2.1 SSOT)。
            # 舊寫法 `st.secrets.get(...) if hasattr(st, "secrets") else ""` 有**兩個**
            # 分岔,而本按鈕最終打到的是與 Tab ① 熱錢卡**同一顆** L1 fetcher
            # (`refresh_hot_money_data` → `fetch_hot_money_frames(180, token)` →
            #  `fetch_foreign_flow_series(180, token)`,cache key = `(days, token)`):
            #   (a) **token 只存在於環境變數**時,裸讀回 `''`、`get_secret` 回
            #       `'TOK_ENV'` → 兩把不同 cache key → 同一個視窗被抓兩次,
            #       一次帶授權一次沒帶,同一頁上同一個量可能出現兩個值;
            #   (b) **完全沒有 `secrets.toml`** 時,`hasattr(st, "secrets")` 仍為 True,
            #       但 `.get()` 內部 `_parse()` 會 `raise StreamlitSecretNotFoundError`
            #       → 被下面的 `except` 吞成「refetch 失敗:[StreamlitSecretNotFoundError]」,
            #       而走 SSOT 的那一邊照常運作。
            # ⚠️ 前一輪把這裡漏掉的理由是「摺疊區、使用者不會點到」—— **不成立**:
            # 本按鈕不在 expander 裡,它存在的理由(見上方 v19.152 註解)正是
            # 「不必點開 ARCHIVED expander」。
            from infra.config import get_secret as _d5_get_secret
            from ui.hot_money import refresh_hot_money_data
            _finmind_tok = str(_d5_get_secret("FINMIND_TOKEN", "") or "")
            with st.spinner("📡 抓 FinMind 外資 + Yahoo USDTWD..."):
                _hm_ok, _hm_msg = refresh_hot_money_data(token=_finmind_tok)
            if _hm_ok:
                st.success(f"✅ 外資/USDTWD {_hm_msg}")
                st.rerun()
            else:
                st.error(f"更新失敗:{_hm_msg}")
        except Exception as _e_rf:
            st.error(f"refetch 失敗:[{type(_e_rf).__name__}] {_e_rf}")
        finally:
            # Tab ① 熱錢快覽卡每 session 只抓一次(F6 守衛),手動更新必須把它的
            # session stash 一起作廢,否則使用者按了「立即更新」、切回 ① 卻沒動。
            #
            # ⚠️ 2026-09-04 第三輪稽核 A5:這兩個 pop 原本在 `try` **裡面**、
            # 而且排在 `refresh_hot_money_data(...)` **之後** —— 那一行拋例外時
            # (例如 F3 記載的 `StreamlitSecretNotFoundError`,或任何上游 5xx),
            # 閘門**整個 session 都清不掉**,使用者在這一輪沒有任何復原路徑:
            # 按鈕看起來按了、錯誤訊息也出來了,但卡片會一直停在舊狀態。
            # 移進 `finally`:**不管成敗都作廢** —— 使用者按過「立即更新」這件事
            # 本身就足以構成「請重新嘗試」的意思表示。
            #
            # 鍵名走 L0 SSOT,不再逐字重寫(B2:原本這裡是三份字面值中的一份,
            # 而那條守衛比對的是 tab5 的字面值與**測試自己的**字面值,
            # 從頭到尾沒碰過生產端常數)。
            try:
                from shared.session_keys import HM_CARD_SESSION_KEYS as _HM_K2
                for _hm_k in _HM_K2:
                    st.session_state.pop(_hm_k, None)
            except Exception:  # noqa: BLE001 — 作廢失敗不得再蓋掉上面的錯誤訊息
                pass
    st.divider()

    # ── Section 0: 全域資料健康總表 ──（caller 端 app.py 已先 call _update_data_registry()）
    _reg = st.session_state.get("data_registry", {})

    # v19.195 SSOT:改 import D5_FRED_KEYS / D5_YF_KEYS,取代第 ② 區重複定義。
    # v19.339:刪 v19.195 遷移殘留的 16 元素 _FRED_KEYS 死清單(定義後 0 引用)。
    from ui.helpers.session import D5_FRED_KEYS as _FRED_INTERNAL
    from ui.helpers.session import D5_YF_KEYS as _YF_KEYS
    _fred_ok = sum(1 for k in _FRED_INTERNAL
                   if (_src_ind.get(k) or {}).get("value") is not None)
    _yf_ok   = sum(1 for k in _YF_KEYS
                   if (_src_ind.get(k) or {}).get("value") is not None)
    _fund_n  = (1 if _src_cf else 0) + len(_src_pf_loaded)
    _nav_n   = sum(1 for f in _src_pf_loaded if f.get("series") is not None) \
               + (1 if _src_cf and (_src_cf.get("series") is not None) else 0)
    _div_n   = sum(1 for f in _src_pf_loaded if (f.get("dividends") or (f.get("moneydj_raw") or {}).get("dividends"))) \
               + (1 if _src_cf and (_src_cf.get("dividends")
                                    or (_src_cf.get("moneydj_raw") or {}).get("dividends")) else 0)
    # ^ v19.331 review 修正:原第二項 `or _src_cf.get("dividends")` 對同 key or 自身
    #   (筆誤 dead fallback);對齊上一行 pf_loaded 的雙路徑語意(頂層 or moneydj_raw)。
    _hold_n  = sum(1 for f in _src_pf_loaded
                   if _get_holdings(f).get("top_holdings")) \
               + (1 if _src_cf and _get_holdings(_src_cf).get("top_holdings") else 0)  # B7 v19.332 統一路徑
    _ter_n   = sum(1 for f in _src_pf_loaded
                   if ((f.get("moneydj_raw") or {}).get("holdings") or {}).get("ter")
                   or (f.get("moneydj_raw") or {}).get("ter")) \
               + (1 if _src_cf and ((_src_cf.get("holdings") or {}).get("ter") or _src_cf.get("ter")) else 0)

    def _src_status(used: bool, ok_n: int = 0, total: int | None = None,
                    inactive_label: str = "尚未使用"):
        if used and ok_n > 0:
            tail = f" / {total}" if total else ""
            return ("🟢", f"已抓 {ok_n}{tail}", TRAFFIC_GREEN)
        if used:
            return ("🟡", "已呼叫但無資料", TRAFFIC_YELLOW)   # v19.390 V3b:🟡↔黃 一致
        return ("⬜", inactive_label, GRAY_66)

    _RAW_TABLE = [
        # (#, 類別, 用途, 端點/Ticker, NAS Proxy, status_tuple)
        # 端點欄原本一格塞 16 個裸 series id，擠成一團無法閱讀。改成
        # 「幾條 + 分類舉例」，完整逐條清單在下方「FRED 下次發布日診斷」區。
        ("1️⃣", "FRED API",            "美國總經 14+ 指標",
         # 2026-09-01：NAPM 移除（2016-08 停更，已從取數邏輯全數拔除），
         # 條數同步 16 → 15 —— 數字與括號內清單必須一致，否則這格自己會說謊。
         "15 條 series：利率/利差（DGS10, DGS2, DGS3MO）、信用（BAMLH0A0HYM2）、"
         "流動性（M2SL, WALCL）、物價（CPIAUCSL, PPIACO）、"
         "就業（UNRATE, ICSA, SAHMREALTIME）、其他（FEDFUNDS, UMCSENT, HSN1F, DRTSCILM）",
         "—", _src_status(bool(_src_ind), _fred_ok, len(_FRED_INTERNAL))),
        ("2️⃣", "Yahoo Chart REST",    "市場行情 4 項",
         "^VIX  /  RSP+SPY  /  DX-Y.NYB  /  HG=F",
         "—", _src_status(bool(_src_ind), _yf_ok, len(_YF_KEYS))),
        ("3️⃣", "MoneyDJ wb01/05/07",  "基金績效 / 配息率 / 風險評比 / TER",
         # 稽核 E5：原寫 yp401000 / yp405000 / yp407000 —— 這三個檔名**全 repo
         # 零命中**，是捏造的。真實路徑見 repositories/fund/nav_metrics.py:741,825
         # 與 sources.py:2136,2639-2641（境內配息另走 funddividend）。
         "/w/wb/wb01.djhtm  /  /yp/wb05.djhtm（境內 funddividend）  /  /yp/wb07.djhtm",
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
        ("9️⃣", "RSS 新聞 (5 來源)",    "國際財經事件",
         "MarketWatch / Yahoo Finance / CNBC × 2 / BBC World",  # v19.295: FT/Investing.com/Bloomberg removed (blocked/subscription)
         "—", _src_status(bool(_src_news), len(_src_news))),
        ("🔟", "yfinance 個股財報",     "三率 QoQ（precision_engine）",
         "yfinance.Ticker(...).quarterly_financials",
         "—", _src_status(False, 0, inactive_label="僅個股查詢觸發")),
    ]

    _src_th = (f"font-size:10px;color:{TRAFFIC_NEUTRAL};font-weight:700;padding:6px 8px;"
               f"border-bottom:1px solid {GH_BORDER}")
    _src_td = "font-size:11px;padding:6px 8px;line-height:1.4"
    _src_html = (
        f"<div style='display:grid;grid-template-columns:38px 1.2fr 1.5fr 3fr 50px 1.4fr;"
        f"background:{GH_BG_PRIMARY};border-radius:6px 6px 0 0'>"
        f"<span style='{_src_th}'>#</span>"
        f"<span style='{_src_th}'>類別</span>"
        f"<span style='{_src_th}'>用途</span>"
        f"<span style='{_src_th}'>API 端點 / Ticker</span>"
        f"<span style='{_src_th};text-align:center'>Proxy</span>"
        f"<span style='{_src_th}'>連動狀態</span>"
        f"</div>"
    )
    for _no, _cat, _purp, _ep, _proxy, (_ic, _stxt, _sc) in _RAW_TABLE:
        _bg = BG_DARK_GREEN_1 if _ic == "🟢" else (BG_DARK_AMBER_2 if _ic == "🟡" else GH_BG_PRIMARY)
        _src_html += (
            f"<div style='display:grid;grid-template-columns:38px 1.2fr 1.5fr 3fr 50px 1.4fr;"
            f"background:{_bg};border-bottom:1px solid {GH_BG_HOVER}'>"
            f"<span style='{_src_td};color:{GRAY_AA}'>{_no}</span>"
            f"<span style='{_src_td};color:{GH_FG_PRIMARY};font-weight:600'>{_cat}</span>"
            f"<span style='{_src_td};color:{GRAY_BB}'>{_purp}</span>"
            f"<span style='{_src_td};color:#7d8590;font-family:monospace;font-size:10px'>{_ep}</span>"
            f"<span style='{_src_td};text-align:center;color:{TRAFFIC_NEUTRAL}'>{_proxy}</span>"
            f"<span style='{_src_td};color:{_sc};font-weight:600'>{_ic} {_stxt}</span>"
            f"</div>"
        )
    st.markdown(
        f"<div style='border:1px solid {GH_BORDER};border-radius:6px;overflow:hidden'>"
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

    st.markdown("### ② 📋 全域資料健康總表")

    _FREQ_LABEL = {
        "daily":     ("日",    "#42a5f5"),
        "weekly":    ("週",    "#ab47bc"),
        "monthly":   ("月",    MATERIAL_ORANGE),
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
            _freq_label_map = {f: _FREQ_LABEL.get(f, (f, GRAY_55))[0] for f in _opts_freq}
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
        _th = (f"font-size:10px;color:{TRAFFIC_NEUTRAL};font-weight:700;padding:4px 8px;"
               f"border-bottom:1px solid {GH_BORDER}")
        _td_base = "font-size:11px;padding:4px 8px"
        _hdr = (
            f"<div style='display:grid;grid-template-columns:2fr 1fr 1fr 1fr 3fr 1fr;"
            f"background:{GH_BG_PRIMARY};border-radius:6px 6px 0 0'>"
            f"<span style='{_th}'>資料名稱</span>"
            f"<span style='{_th}'>來源</span>"
            f"<span style='{_th}'>頻率</span>"
            f"<span style='{_th}'>最新日期</span>"
            f"<span style='{_th}'>新鮮度</span>"
            f"<span style='{_th}'>筆數</span>"
            f"</div>"
        )
        # v19.350：依類別前綴分組渲染（user 要求「參考台股」— 台股 Tab5 診斷表
        # 依類別收合 +「（N 筆｜🟢x 🟡y 🔴z）」rollup）。rollup 反映**全類真實
        # 健康**（不受篩選影響，同台股截圖語義）；上方三篩選器改為「隱藏列」，
        # 謂詞複用既有 _reg_filtered（單一真相，零重複）。整類未載入 → ⚪ 誠實提示。
        from ui.helpers.io.registry_classify import classify_registry, rollup_caption

        def _row_html(_rk, _rv):
            _rn    = _rv.get("count", 0)
            _rd    = _rv.get("latest_date", "N/A")
            _freq  = _rv.get("freq", "monthly")
            _ficon = _rv.get("fresh_icon", "⬜")
            _flbl  = _rv.get("fresh_label", "未知")
            _fcol  = _rv.get("fresh_color", GRAY_55)
            _fqc   = _FREQ_LABEL.get(_freq, (_freq, GRAY_55))
            _row_bg = GH_BG_CARD if _ficon == "🟢" else (BG_DARK_AMBER_2 if _ficon == "🟡" else "#1a0808")
            return (
                f"<div style='display:grid;grid-template-columns:2fr 1fr 1fr 1fr 3fr 1fr;"
                f"background:{_row_bg};border-bottom:1px solid {GH_BG_HOVER}'>"
                f"<span style='{_td_base};color:{GH_FG_PRIMARY}'>{_rv.get('label', _rk)}</span>"
                f"<span style='{_td_base};color:{TRAFFIC_NEUTRAL}'>{_rv.get('source','')}</span>"
                f"<span style='{_td_base}'>"
                f"<span style='background:{_fqc[1]}22;color:{_fqc[1]};"
                f"border:1px solid {_fqc[1]};border-radius:10px;padding:1px 7px;"
                f"font-size:10px;font-weight:700'>{_fqc[0]}</span></span>"
                f"<span style='{_td_base};color:{GRAY_AA}'>{_rd}</span>"
                f"<span style='{_td_base};color:{_fcol};font-weight:600'>{_ficon} {_flbl}</span>"
                f"<span style='{_td_base};color:{GRAY_AA}'>{_rn}</span>"
                f"</div>"
            )

        _cat_css = (f"font-size:12px;font-weight:800;color:{GH_FG_PRIMARY};"
                    f"padding:7px 10px;background:{GH_BG_PRIMARY};"
                    f"border-top:2px solid {GH_BORDER}")
        _sections = ""
        for _grp in classify_registry(_reg):
            _cap = rollup_caption(_grp["rollup"])
            _n_full = len(_grp["rows"])
            _sections += (
                f"<div style='{_cat_css}'>{_grp['name']}"
                f"　<span style='font-weight:600;color:{TRAFFIC_NEUTRAL}'>"
                f"（{_n_full} 筆｜{_cap}）</span></div>"
            )
            if not _grp["loaded"]:
                _sections += (
                    f"<div style='{_td_base};color:{GRAY_AA};padding:8px 12px'>"
                    f"⚪ 尚未載入 — 請至 {_grp['hint']} 載入後回此檢視</div>"
                )
                continue
            _visible = [_r for _r in _grp["rows"] if _r["key"] in _reg_filtered]
            if not _visible:
                _sections += (
                    f"<div style='{_td_base};color:{GRAY_AA};padding:8px 12px'>"
                    f"（{_n_full} 筆已載入，全被上方篩選器隱藏）</div>"
                )
                continue
            for _r in _visible:
                _sections += _row_html(_r["key"], _r)
        st.markdown(
            f"<div style='border:1px solid {GH_BORDER};border-radius:6px;overflow:hidden'>"
            f"{_hdr}{_sections}</div>",
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
                # 稽核 N1-e：筆數走 data_registry 的 _SNAP_HEAD_N SSOT，
                # 不在本檔手抄「5」（原本 selectbox 標籤 / head(5) / caption
                # 各寫死一次，改常數不會連動 = §3.3 要防的第二份真相）。
                from ui.helpers.io.data_registry import _SNAP_HEAD_N as _SNAP_N
                _snap_sel = st.selectbox(
                    f"選擇資料源查看原始資料（head {_SNAP_N}，降冪排序）",
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
                        }).head(_SNAP_N)
                        st.dataframe(_snap_df, use_container_width=True, hide_index=True)
                        st.caption(
                            f"資料鍵值：{_snap_sel}　頻率：{_snap_fq}　｜　"
                            # 稽核 N1-e：registry 只留最新 N 筆(payload 瘦身),
                            # 總筆數改讀 entry 既有的 `count`,顯示語意不變。
                            f"共 {_reg[_snap_sel].get('count', len(_snap_s))} 筆"
                            f"（已依時間降冪排序，顯示最新 {_SNAP_N} 筆）"
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
        # 2026-09-01：原文寫「三層 fallback：1. ISM NAPM → 2. ISM ISPMANPMI →
        #   3. Phil Fed」。前兩段已於同批拔除（2016-08 起停更），若不同步改，
        #   這段**給使用者看的說明**會在合併當下變成假話。
        st.info(
            "ℹ️ **PMI** 五段 fallback 全失敗：\n"
            "1. MacroMicro → 2. ISM World 官方 → 3. DBnomics → "
            "4. Phil Fed 擴散指數轉換（代理值）→ 5. OECD 美國商業信心（代理值）\n\n"
            "可能原因：FRED API Key 失效 / NAS Proxy 中斷 / 五項皆當日斷線。"
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
                _col_c = MATERIAL_GREEN if (_ms and _ms < 1000) else (MATERIAL_ORANGE if (_ms and _ms < 3000) else MATERIAL_RED)
                _pcols[_ci].markdown(
                    f"<div style='background:{BG_DARK_NAVY_4};border-radius:8px;padding:10px;text-align:center'>"
                    f"<div style='font-size:11px;color:{TRAFFIC_NEUTRAL}'>{_sn}</div>"
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
                ("FRED/yfinance(載入)", _lh_fred, MD_BLUE_300),
                ("MoneyDJ(測速)",       _lh_mj,   MATERIAL_ORANGE),
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
            _fig_lat.add_hline(y=1000, line_color=MATERIAL_ORANGE, line_dash="dot",
                               line_width=1, annotation_text="1s 警示",
                               annotation_font_color=MATERIAL_ORANGE,
                               annotation_position="bottom right")
            _fig_lat.add_hline(y=3000, line_color=MATERIAL_RED, line_dash="dash",
                               line_width=1, annotation_text="3s 警戒",
                               annotation_font_color=MATERIAL_RED,
                               annotation_position="bottom right")
            _fig_lat.update_layout(
                paper_bgcolor=STREAMLIT_BG, plot_bgcolor=GH_BG_CARD,
                font_color=GH_FG_PRIMARY, height=260,
                margin=dict(t=10, b=40, l=60, r=20),
                xaxis=dict(tickangle=-30, tickfont_size=9, gridcolor=BG_DARK_NAVY_3),
                yaxis=dict(title="回應時間 (ms)", gridcolor=BG_DARK_NAVY_3),
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
            # ── 稽核 N1-c：改為按鈕觸發（原本無條件執行）───────────────────────
            # 原碼直接呼叫 `backtest_sub_cycle_lights(window=60)`：7 子領域 ×
            # 60 月 expanding window，而 `services/macro/causal_sankey.py` 內
            # **沒有任何 cache decorator**。關鍵是兩件事疊在一起：
            #   (1) `st.expander` 收合**不會**阻止 body 執行；
            #   (2) `app.py:205` 自承「st.tabs 單次 run 渲染全部分頁」。
            # → 使用者停在任何一頁、做任何一次互動，都會付一次這個成本。
            # 25 檔實測：rerun 起算 17 秒後 `WebSocket onclose`（2026-08-14 實機）。
            # 對策：按鈕觸發 + session 暫存，與本頁其他重運算探針（🔍 跑 FX 來源
            # 診斷 / 🔍 立即診斷）的既有慣例一致，不新造 pattern。
            if st.button("▶️ 執行 Phase 3-B 回測（7 子領域 × 60 月，需數秒）",
                         key="btn_d5_p3b",
                         help="本區屬維運診斷，**預設不自動計算** —— 它沒有快取，"
                              "而 Streamlit 每次互動都會重跑整份 script（含收合的 "
                              "expander），自動執行會拖垮全站回應。按一次算一次，"
                              "結果留在本次 session。"):
                try:
                    from services.macro import backtest_sub_cycle_lights as _d5_bt
                    with st.spinner("Phase 3-B 回測計算中…"):
                        st.session_state["_d5_p3b_out"] = _d5_bt(
                            _d5_ind, target_key="LEI", window=60, forward_months=3)
                except Exception as _e_d5_bt:
                    import sys as _sys_p3b
                    import traceback as _tb_p3b
                    print(f"[tab5/phase3b] {type(_e_d5_bt).__name__}: {_e_d5_bt}",
                          file=_sys_p3b.stderr)
                    _tb_p3b.print_exc(file=_sys_p3b.stderr)
                    # 稽核 §1：失敗要留成「失敗」，不可存 None ——
                    # 存 None 會讓下一輪 rerun 讀到後印「⬜ 尚未執行」，
                    # 把「算爆了」偽裝成「你還沒按」（掩蓋問題 = 違憲）。
                    st.session_state["_d5_p3b_out"] = {
                        "_error": f"[{type(_e_d5_bt).__name__}] {str(_e_d5_bt)[:200]}"
                    }
            _d5_bt_out = st.session_state.get("_d5_p3b_out")
            if _d5_bt_out is None:
                st.caption("⬜ 尚未執行 —— 按上方按鈕才會計算（避免每次操作都重跑一輪 60 月回測）。")
            elif isinstance(_d5_bt_out, dict) and _d5_bt_out.get("_error"):
                st.error(
                    f"❌ Phase 3-B 回測**失敗**（這不是「尚未執行」）："
                    f"{_d5_bt_out['_error']}　·　完整 traceback 見 Cloud log 的 "
                    "`[tab5/phase3b]`。可再按一次上方按鈕重試。"
                )
            else:
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
                # 2026-09-01：原文寫「代表 FRED ISPMANPMI 補救路徑也失敗，需檢查
                #   FRED_API_KEY」—— 那條補救路徑已於同批拔除（它補抓的
                #   ISPMANPMI 2016-08 起停更），留著會叫使用者去查一個**已經不存在**
                #   的東西，而且把責任誤導到 API Key 上。
                st.warning(
                    "⚠️ PMI series 為空 — 代表本次命中的是 **只回當期值、不回歷史序列**"
                    "的來源（MacroMicro / ISM World / DBnomics 三段 HTML/JSON 源）。\n\n"
                    "**這不是錯誤**：value 仍然有效，只是 Z-Score / 領先落後相關性這類"
                    "需要歷史序列的計算會跳過 PMI 這一格。命中 Phil Fed 或 OECD 兩段"
                    "（代理值）時則會帶回 120 期序列。"
                )

    st.divider()

    # ── v18.120 issue 4: NAS Proxy 狀態檢測 ───────────────────────
    st.markdown("### ③ 🌐 NAS Proxy 中繼站狀態")
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
            # 原本是 🔴 + st.warning:直連是「還沒設定 Proxy」的正常降級,不是故障。
            not_ready("NAS Proxy 未設定 — 走直連模式"
                      "（Streamlit Cloud IP 經常被 MoneyDJ 封鎖）",
                      where="Streamlit Cloud secrets 加 "
                            "`PROXY_URL = \"http://user:pwd@your-nas-host:3128\"`")
    except Exception as _e_d5_pxy:
        st.error(f"⚠️ 讀取 Proxy 設定失敗：{type(_e_d5_pxy).__name__}: {str(_e_d5_pxy)[:80]}")

    st.divider()

    # ── v18.268: FX 即時匯率來源診斷 ─────────────────────────────
    with st.expander("🌍 FX 即時匯率來源診斷 — 4 個來源逐一檢測", expanded=False):
        st.caption(
            "Tab2 投資試算的 FX 來源 chain（Yahoo → FRED → open.er-api → Frankfurter）。"
            "全掛時會 fallback 到手動模式（預設 32.0）。"
        )
        _fx_pair = st.selectbox(
            "幣別對",
            options=["USDTWD", "EURTWD", "JPYTWD", "CHFTWD", "CNHTWD"],
            index=0,
            key="_d5_fx_pair",
            help="跑診斷會逐一打 4 個 API（約 10-30 秒）",
        )
        if st.button("🔍 跑 FX 來源診斷", key="_d5_fx_btn"):
            try:
                from repositories.fund import diagnose_fx_sources
                import os as _os_fx
                _fred_k_diag = ""
                try:
                    _fred_k_diag = st.secrets.get("FRED_API_KEY", "")
                except Exception:
                    pass
                _fred_k_diag = _fred_k_diag or _os_fx.environ.get("FRED_API_KEY", "")
                with st.spinner(f"逐一檢測 {_fx_pair} 的 4 個來源..."):
                    _diag = diagnose_fx_sources(f"{_fx_pair}=X", fred_api_key=_fred_k_diag)
                _rows = []
                # v18.275：diag dict 動態欄位 — TWD pair 只有 yahoo/er_api（FRED/Frankfurter
                # 對 TWD 不適用已移除），其他 pair 還有 fred + frankfurter
                _source_zh = {
                    "yahoo":       "Yahoo Chart API",
                    "fred":        "FRED DEX* series",
                    "er_api":      "open.er-api.com",
                    "frankfurter": "Frankfurter (ECB)",
                }
                for _idx, _src_key in enumerate(_diag.keys(), start=1):
                    _r = _diag[_src_key]
                    _rows.append({
                        "順位": f"{_idx}. {_source_zh.get(_src_key, _src_key)}",
                        "狀態": "✅ 通" if _r.get("ok") else "❌ 失敗",
                        "匯率": f"{_r['rate']:.4f}" if _r.get("rate") else "—",
                        "錯誤訊息": _r.get("error") or "—",
                        "說明": _r.get("note") or "—",
                    })
                import pandas as _pd_fx
                st.dataframe(_pd_fx.DataFrame(_rows), use_container_width=True, hide_index=True)
                _n_total = len(_diag)
                _n_ok = sum(1 for _r in _diag.values() if _r.get("ok"))
                if _n_ok >= 1:
                    st.success(f"✅ {_n_ok}/{_n_total} 個來源可用 — Tab2 投資試算應能拿到即時匯率")
                else:
                    st.error(
                        f"❌ {_n_total} 個來源全部失敗 — Tab2 將 fallback 到手動模式。"
                        "可能是 NAS proxy 全域不通，或網路被擋"
                    )
            except Exception as _e_d5_fx:
                st.error(f"⚠️ FX 診斷異常：{type(_e_d5_fx).__name__}: {str(_e_d5_fx)[:80]}")
        else:
            st.caption("⬆️ 按按鈕開始（4 個來源各 1 個 HTTP call，總共 ~10-30 秒）")

    st.divider()

    # ── Section 2: API Key 狀態 ───────────────────────────────────
    # v19.135 升級(學 Stock 偵測精度):來源解析 + 遮罩 + secrets TOML 驗證
    st.markdown("### ④ 🔑 API 金鑰狀態")
    st.caption("排查「Key 已設但全站抓不到資料」根因:來源(st.secrets / os.environ)→ 遮罩比對 → TOML 解析狀態")

    # secrets 整體可讀性檢查(TOML 格式錯會整段 fallback 到空)
    _sec_obj = getattr(st, "secrets", None)
    _sec_keys: list = []
    _sec_parse_err = None
    try:
        if _sec_obj is not None:
            _sec_keys = list(_sec_obj.keys())
    except Exception as _e_sec:  # noqa: BLE001
        _sec_parse_err = f"{type(_e_sec).__name__}: {_e_sec}"

    _sc1, _sc2 = st.columns(2)
    _sc1.metric("st.secrets 可讀", "✅" if _sec_parse_err is None else "❌")
    _sc2.metric("Secrets keys 數", len(_sec_keys))
    if _sec_parse_err:
        st.error(
            f"⚠️ st.secrets 解析失敗:{_sec_parse_err}\n\n"
            "→ 通常是 TOML 格式錯(缺引號 / 用了 export / 特殊字元未跳脫)。"
            "Streamlit Cloud → App settings → Secrets 重貼,每個值都加雙引號。"
        )

    # 逐把 key 解析(遮罩 + 來源)
    _key_targets = ["FRED_API_KEY", "GEMINI_API_KEY", "FINMIND_TOKEN",
                    "PROXY_URL", "GOOGLE_SHEET_ID"]
    _key_rows = [_resolve_key(_k) for _k in _key_targets]
    _kt_th = (f"font-size:10px;color:{TRAFFIC_NEUTRAL};font-weight:700;padding:6px 10px;"
              f"border-bottom:1px solid {GH_BORDER}")
    _kt_td = "font-size:11px;padding:6px 10px;line-height:1.4"
    _kt_html = (
        f"<div style='display:grid;grid-template-columns:1.4fr 1fr 1.6fr 1.4fr;"
        f"background:{GH_BG_PRIMARY};border-radius:6px 6px 0 0'>"
        f"<span style='{_kt_th}'>API Key</span>"
        f"<span style='{_kt_th}'>使用來源</span>"
        f"<span style='{_kt_th}'>實際值(遮罩)</span>"
        f"<span style='{_kt_th}'>os.environ 同步</span>"
        f"</div>"
    )
    for _kr in _key_rows:
        _src_color = (TRAFFIC_GREEN if _kr["source"] != "(無)" else TRAFFIC_RED)  # v19.390 V3b:來源燈收 TRAFFIC
        _bg = BG_DARK_GREEN_1 if _kr["source"] != "(無)" else BG_DARK_RED_2
        _kt_html += (
            f"<div style='display:grid;grid-template-columns:1.4fr 1fr 1.6fr 1.4fr;"
            f"background:{_bg};border-bottom:1px solid {GH_BG_HOVER}'>"
            f"<span style='{_kt_td};color:{GH_FG_PRIMARY};font-weight:600'>{_kr['name']}</span>"
            f"<span style='{_kt_td};color:{_src_color};font-weight:600'>{_kr['source']}</span>"
            f"<span style='{_kt_td};color:{GRAY_BB};font-family:monospace;font-size:10px'>{_kr['preview']}</span>"
            f"<span style='{_kt_td};color:#7d8590;font-family:monospace;font-size:10px'>{_kr['env_preview']}</span>"
            f"</div>"
        )
    st.markdown(
        f"<div style='border:1px solid {GH_BORDER};border-radius:6px;overflow:hidden'>"
        f"{_kt_html}</div>", unsafe_allow_html=True,
    )
    st.caption(
        "「使用來源」= 程式實際取用的位置。若為 `(無)` → st.secrets 與 os.environ 都沒有,"
        "fallback 拿到空字串,下游 API 必然 401/403/missing token。"
        "「遮罩」顯示前 4 後 4 字 + 長度,可快速判「key 為空」vs「格式截斷」。"
    )

    # ── 「去哪裡設定」——2026-08-28 客戶拍板 Q3,自 app.py 首頁搬來的那件事 ──────
    # 原本 `app.py._check_secrets()` 在 module top-level 無條件跑,**五個分頁最上方**
    # 都會看到那一行。客戶裁示移到本節。
    # （原始文案是「缺少**必要**金鑰」——「必要」二字就是下面要修的那個事實錯誤；
    #   批次一已先把它從 🔴 改成 ⬜ 並改寫為「尚未設定金鑰：…」，位置沒動。
    #   2026-08-28 稽核更正:本註解原本引用的是**批次一之前**的舊文案。）
    # 上面那張表已經逐把列出「有沒有設、從哪讀到」(比原本多 3 把),**唯一沒有的就是
    # 「那要去哪裡設」** —— 所以搬過來的是這一句,不是再貼一張同樣的表(§2.1 SSOT:
    # 同一個事實不要有第二份實作)。
    # ⚠️ 順帶修掉原句的一個**事實錯誤**:它把 GEMINI 也稱為「**必要**」金鑰。
    #    兩者的後果不同,線框 §03 / Q3 點名的就是這件事 ——
    #    缺 FRED → 整個 🌐 市場定調頁不能用(擋路);缺 GEMINI → 只是少 AI 摘要(可降級)。
    #    故這裡分開講,不再用同一個詞蓋掉差別。
    _key_where = "Streamlit Cloud → Settings → Secrets 新增後重新部署"
    _unset = {_kr["name"] for _kr in _key_rows if _kr["source"] == "(無)"}
    if "FRED_API_KEY" in _unset:
        # 2026-08-31 WP-F：分頁名改吃 SSOT（同上，避免第二份標籤）。
        from ui.helpers.story_nav import tab_label as _tl_key  # noqa: PLC0415

        not_ready(f"尚未設定 FRED_API_KEY —— 整個「{_tl_key('macro')}」頁無法載入"
                  "(這一把缺了會擋路)",
                  where=_key_where)
    if "GEMINI_API_KEY" in _unset:
        not_ready("尚未設定 GEMINI_API_KEY —— 只影響各頁的 AI 摘要區塊,"
                  "其餘指標與健診照常運作(可降級,不擋路)",
                  where=_key_where)

    st.divider()

    # ── Section 3: 基金逐筆診斷 ───────────────────────────────────
    st.markdown("### ⑤ 📊 基金資料診斷")
    # v19.346(第九份 review):本區只讀 session_state 快取(單一/組合 Tab 載入時寫入),
    # 不即時重抓 — 原無說明,易被誤讀為「當下狀態」。誠實標示資料時點(§2.4 精神)。
    st.caption(
        "ℹ️ 本區讀取**本 session 已載入的快取**（單一基金／組合基金 Tab 載入時寫入），"
        "非即時重抓；抓取時間與新鮮度以上方 **① 原始資料源總覽** 的時間戳為準。"
    )
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
            """v16.5：只顯示『資料是否取得』；v18.53: "N/A" = 不適用（ℹ️ 灰）。
            v19.346（第九份 review + user「讓資料更完整」指示）：fmt 從保留參數
            轉為實作 — 狀態判定不變，但 fmt 有給且值可格式化時，於狀態後**附加**
            實際數值（✅ 已取得 · 12.3456），診斷表從「有/無」升級為可肉眼對值。
            fmt 失敗不掩蓋：留 stderr log、退回純狀態顯示（§3.3 不靜默）。
            """
            _empty = (value is None or value == "" or
                      (isinstance(value, (dict, list)) and not value))
            if value == "N/A":
                _ic, _vc, _vs = "ℹ️", TRAFFIC_NEUTRAL, "N/A 不適用"
            elif _empty:
                _ic, _vc, _vs = "⚠️", MATERIAL_ORANGE, "缺失"
            elif not bool(ok_cond):
                _ic, _vc, _vs = "⚠️", MATERIAL_ORANGE, "資料不足"
            else:
                _ic, _vc, _vs = "✅", MATERIAL_GREEN, "已取得"
            if fmt is not None and not _empty and value != "N/A":
                try:
                    _vs = f"{_vs} · {fmt(value)}"
                except Exception as _e_fmt:
                    import sys as _sys_d5
                    print(f'[tab5/_d5_cell] {label} fmt 失敗(退回純狀態): '
                          f'{type(_e_fmt).__name__}: {_e_fmt}', file=_sys_d5.stderr)
            col.markdown(
                f"<div style='background:{BG_DARK_NAVY_4};border-radius:6px;padding:6px 8px'>"
                f"<div style='font-size:10px;color:{TRAFFIC_NEUTRAL}'>{label}</div>"
                f"<div style='font-size:13px;color:{_vc};font-weight:700'>{_ic} {_vs}</div>"
                f"</div>", unsafe_allow_html=True)

        for _d5_fd in _d5_list:
            _d5_code  = _d5_fd.get("code", "?")
            _d5_fname = _d5_fd.get("name", "") or _d5_code
            _d5_mj    = _d5_fd.get("moneydj_raw", {}) or {}
            _d5_m     = _d5_fd.get("metrics", {}) or {}
            _d5_err   = _d5_fd.get("error", "") or _d5_mj.get("error", "")
            _d5_nav   = _d5_m.get("nav") or _d5_mj.get("nav")
            # v19.272 Phase 2 TOP 1.3:adr 走 SSOT 3 層 fallback chain(原行內 2 層收斂)
            from services.health.dividend import _resolve_adr_with_fallback
            _d5_adr, _ = _resolve_adr_with_fallback(_d5_fd)
            _d5_perf  = _d5_mj.get("perf", {}) or {}
            _d5_risk  = (_d5_mj.get("risk_metrics", {}) or {})
            _d5_r1y   = (_d5_risk.get("risk_table") or {}).get("一年", {}) or {}
            _d5_divs  = _d5_fd.get("dividends") or _d5_mj.get("dividends") or []
            _d5_divs  = _d5_divs if isinstance(_d5_divs, list) else []
            _d5_hold  = _get_holdings(_d5_fd)  # B7 v19.332 統一路徑(頂層優先 → moneydj_raw)
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
                # v19.333 review F1:裸 float() 為 eager 求值,來源若混入非數值字串
                # (如 "12.34 元")會 ValueError 炸掉整個 Tab5(逐檔迴圈無 try 包覆)。
                # 改 _safe_float(SSOT):非數值 → None → 顯「資料不足」而非崩潰。
                _d5_cell(_r1[0], "最新淨值 NAV",   _d5_nav,
                         ok_cond=((_safe_float(_d5_nav) or 0) > 0),
                         fmt=lambda v: f"{float(v):.4f}")
                # 配息率：累積型 → 標 N/A 不配息 用佔位避免 cell empty
                _d5_cell(_r1[1], "年化配息率",
                         _d5_adr if not _d5_is_accum else "N/A",
                         ok_cond=(_d5_is_accum or (_safe_float(_d5_adr) or 0) > 0),
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
                st.markdown("<div style='margin:4px 0'></div>", unsafe_allow_html=True)
                # Row 4(B6 v19.332,review 監控盲區):最大回撤 / Sortino / Calmar / 規模
                # 前三者 calc_metrics 一直有算(fund_service.py:599/404/433)只是診斷沒列格;
                # 規模 fund_scale 為 MoneyDJ 基本資料字串(可能含日期註記,原樣顯示前 18 字)
                _r4 = st.columns(4)
                _d5_mdd = _d5_m.get("max_drawdown")
                _d5_cell(_r4[0], "最大回撤",        _d5_mdd,
                         ok_cond=(_d5_mdd is not None),
                         fmt=lambda v: f"{float(v):.2f}%")
                _d5_sortino = _d5_m.get("sortino")
                _d5_cell(_r4[1], "Sortino",         _d5_sortino,
                         ok_cond=(_d5_sortino is not None),
                         fmt=lambda v: str(v))
                _d5_calmar = _d5_m.get("calmar")
                _d5_cell(_r4[2], "Calmar",          _d5_calmar,
                         ok_cond=(_d5_calmar is not None),
                         fmt=lambda v: str(v))
                _d5_scale = str(_d5_mj.get("fund_scale") or "").strip()
                _d5_cell(_r4[3], "基金規模",        _d5_scale or None,
                         ok_cond=bool(_d5_scale),
                         fmt=lambda v: str(v)[:18])
                st.markdown("<div style='margin:4px 0'></div>", unsafe_allow_html=True)
                # Row 5(v19.333 review F9):多年期報酬 calc_metrics 已算未列
                # (ret_3y_ann / ret_5y_ann / ret_6m);TER 原僅 Section① 聚合計數。
                # 歷史不足 → "N/A 不適用"(ℹ️)而非「缺失」(⚠️)— 新發行基金 3Y/5Y
                # 本來就算不出(§4.6),與「該有而沒有」語意區分(review 面向一
                # 亦點名「短序列靜默 None 未標示原因」)。252=_TD_1Y 交易日 SSOT。
                _r5 = st.columns(4)
                _d5_r3y = _d5_m.get("ret_3y_ann")
                _d5_cell(_r5[0], "3Y年化報酬",
                         _d5_r3y if _d5_r3y is not None
                         else ("N/A" if _d5_slen < 3 * _TD_1Y else None))
                _d5_r5y = _d5_m.get("ret_5y_ann")
                _d5_cell(_r5[1], "5Y年化報酬",
                         _d5_r5y if _d5_r5y is not None
                         else ("N/A" if _d5_slen < 5 * _TD_1Y else None))
                _d5_r6m = _d5_m.get("ret_6m")
                _d5_cell(_r5[2], "6M報酬",
                         _d5_r6m if _d5_r6m is not None
                         else ("N/A" if _d5_slen < _TD_1Y // 2 else None))
                # TER 取值鏡像 Section① _ter_n 的雙路徑(holdings.ter → 頂層 ter)
                _d5_ter = ((_d5_mj.get("holdings") or {}).get("ter")
                           or _d5_mj.get("ter"))
                _d5_cell(_r5[3], "TER費用率",       _d5_ter or None)

                st.markdown(
                    f"<span style='font-size:10px;color:{GRAY_55}'>"
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
            # EX-PASSTHRU-1(v19.377):同 data_registry,thin FRED 揭露日 helper 診斷用(見 CLAUDE.md §8.2.A)
            from repositories.macro_repository import fred_get_next_release_date as _diag_next_rel
            _diag_key = (st.secrets.get("FRED_API_KEY","")
                         or os.environ.get("FRED_API_KEY",""))
            if not _diag_key:
                not_ready("FRED_API_KEY 未設定 → 下方揭露日全部會走 fallback",
                          where="Streamlit Cloud → Settings → Secrets 的 `FRED_API_KEY`")
            # 12 個診斷目標一律「中文名 + series id」，不再有純英文 label
            # ⚠️ 2026-09-01：原本第 2 列是 ("PMI 製造業採購經理人指數", "NAPM",
            #   "monthly")，**已移除**（13 → 12）。理由：按下「立即診斷」會對清單裡
            #   每一條 series 呼叫 `fred_get_next_release_date` —— 對 NAPM 而言就是
            #   **對一條 2016-08 起停更的 series 發起查詢**，正是客戶指令所禁。
            #   PMI 已不從 FRED 取數（見 repositories/macro/alternate.py 檔頭），
            #   其新鮮度改走 data_registry 的天數閾值 fallback，本表不再適用。
            # （原本 UNRATE / HSN1F / PERMIT / UMCSENT / M2SL / FEDFUNDS 6 個
            #  只印 FRED 內部代號，看不懂就無從判斷該不該在意它延遲）
            _diag_targets = [
                ("CPI 消費者物價指數", "CPIAUCSL", "monthly"),
                ("失業率", "UNRATE", "monthly"),
                ("CFNAI 芝加哥聯儲全國活動指數", "CFNAI", "monthly"),
                ("成屋銷售", "HSN1F", "monthly"),
                ("新屋開工許可", "PERMIT", "monthly"),
                ("密大消費者信心", "UMCSENT", "monthly"),
                ("M2 貨幣供給", "M2SL", "monthly"),
                ("CCSA 續請失業金", "CCSA", "weekly"),
                ("ICSA 初領失業金", "ICSA", "weekly"),
                ("殖利率利差 10Y-3M", "T10Y3M", "daily"),
                ("聯邦資金利率", "FEDFUNDS", "monthly"),
                ("SLOOS 銀行放貸標準", "DRTSCILM", "quarterly"),
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
                st.dataframe(
                    pd.DataFrame(_diag_rows),
                    use_container_width=True, hide_index=True,
                    column_config={
                        "指標": st.column_config.TextColumn("指標", width="medium"),
                        "series_id": st.column_config.TextColumn(
                            "series_id", width="small",
                            help="FRED 內部代號，回報問題時附上它"),
                        "頻率": st.column_config.TextColumn("頻率", width="small"),
                        "next_release": st.column_config.TextColumn(
                            "下次發布日", width="medium",
                            help="FRED 公告的下一次資料發布日；None = API 失敗或該序列無排程"),
                        "距今": st.column_config.TextColumn(
                            "距今", width="small", help="正數 = 還沒到；負數 = 已過幾天"),
                    })
                st.caption(
                    "💡 若某指標長期 None，可能：(1) FRED 未收錄該 series 的 release schedule "
                    "(2) proxy 連線有問題 (3) series_id 拼錯。對應修正：(1) 改 fallback 閾值 "
                    "(2) 修 NAS proxy (3) 對齊 _FRED_SERIES_MAP 條目。"
                )
        except Exception as _e_diag:
            st.error(f"❌ 診斷模組載入失敗：{_e_diag}")

    # ══════════════════════════════════════════════════════
    # v19.361 PR-2(A)：保單對帳單 CSV 歷史匯入 → nav_history 累積(L3→L2)
    # 2026-09-02 線框 §03 ⑤ B「合一」：⑤ 持有 NAV_HISTORY 時，本頁**不畫**這一塊 ——
    # 它與管理室那塊在合併頁裡是同一件事，⑤ 的「🗄️ NAV 歷史」區塊畫唯一一份。
    # ⑤ 沒持有（舊路徑 / 直接呼叫本函式）→ 照舊完整渲染，行為一字未變。
    # ══════════════════════════════════════════════════════
    if not _settings_page_owns(_SD_NAV_HISTORY):
        st.divider()
        # 裡面第一行就是「🔴 累積未啟用」的致命狀態燈 —— 收起來的話使用者永遠不會知道
        # 歷史淨值根本沒在累積（原則 1）。原本靠「永遠展開的 expander」達成,但那層殼
        # 對使用者只是多一圈邊框 + 一個可以把狀態燈關掉的入口。改成標題 + container,
        # 狀態燈與匯入表單一律常駐。
        st.markdown("### 🗂️ NAV 歷史匯入與累積狀態（保單對帳單 CSV → nav_history）")
        with st.container():
            render_nav_accumulation_status()
            render_nav_statement_csv_import()

    # ══════════════════════════════════════════════════════
    # ⚠️ 資料異常清單（最下方一覽，獨立於上方總表/體檢區）
    # ══════════════════════════════════════════════════════
    st.divider()
    st.markdown("### ⑥ ⚠️ 資料異常清單")
    st.caption(
        "💡 v18.3 起：月度 / 季度指標的 stale 判斷改依 **FRED `next_release_date`** 動態計算，"
        "today < next_release → 🟢；release 期已到 +5 天內 → 🟡（屬於正常 release window）；"
        "超過 +5 天 → 🔴（真延遲）。FRED API 失敗才回退舊閾值。"
    )
    _anom_reg = st.session_state.get("data_registry", {})
    _anom_state, _anom_items = anomaly_view_state(_anom_reg)
    if _anom_state == "empty":
        # §1：registry 為空 = 「還沒量」，不是「量過都正常」。
        # 診斷頁在什麼都沒載入時印大綠燈，會讓來查證數字的使用者回頭懷疑自己的判讀。
        # 對齊 Section ② 的空 registry guard（本檔 `if not _reg:` 分支）。
        st.info(
            "尚未載入任何數據 → **無法判定資料是否異常**（這不等於「全部正常」）。"
            "請先於 Tab1 按「📡 載入總經資料」，或於 Tab2 / Tab3 載入基金資料後再回本區。"
        )
    elif _anom_state == "clean":
        # ⚠️ 2026-08-20:「已登錄的」這個限定詞很重要,但綠勾的視覺份量遠大於它。
        #    在同日的「缺席偵測」落地前,抓失敗的來源**不會產生任何一列**
        #    ⇒ 失敗越多、N 越小、越容易全綠。現在總經指標已改為與生產端契約
        #    (`EXPECTED_INDICATOR_KEYS`)做差集,缺席會顯式變成 🔴 列;
        #    **但其餘類別(基金 NAV / 配息 / 持股 / 雷達 / 新聞)仍是「列舉既有」**,
        #    那些若整個沒抓到,依然不會出現在這個 N 裡面。故文案必須說清楚
        #    這個綠勾覆蓋到哪、沒覆蓋到哪(§1:不讓使用者誤以為已全面體檢)。
        st.success(
            f"✅ 已登錄的 {len(_anom_reg)} 個資料源狀態正常"
            "（🟢 最新 + 🟡 release window 內）"
        )
        st.caption(
            "ℹ️ 總經指標已對照生產端契約檢查「該有而沒來」的項目（缺席會列為 🔴）；"
            "基金 NAV／配息／持股／雷達／新聞等類別目前仍只列舉「已抓到」的，"
            "整項未抓到時不會出現在上面的計數中。"
        )
    else:
        _anom_red = sum(1 for _, v in _anom_items if v.get("fresh_icon") == "🔴")
        _anom_yel = sum(1 for _, v in _anom_items if v.get("fresh_icon") == "🟡")
        st.caption(
            f"共 {len(_anom_items)} 筆異常　｜　🔴 真延遲 {_anom_red}　🟡 其他延遲 {_anom_yel}"
            f"　｜　依嚴重度排序（release window 內的 🟡 已自動排除）"
        )
        _th_a = (f"font-size:10px;color:{TRAFFIC_NEUTRAL};font-weight:700;padding:4px 8px;"
                 f"border-bottom:1px solid {GH_BORDER}")
        _td_a = "font-size:11px;padding:4px 8px"
        _hdr_a = (
            f"<div style='display:grid;grid-template-columns:2.4fr 1.4fr 0.8fr 1.2fr 1.6fr;"
            f"background:{GH_BG_PRIMARY};border-radius:6px 6px 0 0'>"
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
            _afq_lbl, _afq_col = _FREQ_LABEL.get(_afreq, (_afreq or "—", GRAY_55))
            _abg = "#1a0808" if _aicon == "🔴" else BG_DARK_AMBER_2
            _rows_a += (
                f"<div style='display:grid;grid-template-columns:2.4fr 1.4fr 0.8fr 1.2fr 1.6fr;"
                f"background:{_abg};border-bottom:1px solid {GH_BG_HOVER}'>"
                f"<span style='{_td_a};color:{GH_FG_PRIMARY}'>{_av.get('label', _ak)}</span>"
                f"<span style='{_td_a};color:{TRAFFIC_NEUTRAL}'>{_av.get('source','—') or '—'}</span>"
                f"<span style='{_td_a}'>"
                f"<span style='background:{_afq_col}22;color:{_afq_col};"
                f"border:1px solid {_afq_col};border-radius:10px;padding:1px 7px;"
                f"font-size:10px;font-weight:700'>{_afq_lbl}</span></span>"
                f"<span style='{_td_a};color:{GRAY_AA}'>{_av.get('latest_date','—') or '—'}</span>"
                f"<span style='{_td_a};color:{_acol};font-weight:600'>{_aicon} {_albl}</span>"
                f"</div>"
            )
        st.markdown(
            f"<div style='border:1px solid {GH_BORDER};border-radius:6px;overflow:hidden'>"
            f"{_rows_a}</div>",
            unsafe_allow_html=True,
        )
        st.caption("💡 建議：🔴 項目請優先重新抓取；🟡 為延遲，仍可使用但需注意時效。")

def render_nav_accumulation_status() -> None:
    """③ 累積狀態：能不能累（狀態燈）＋ 累了多少（逐檔涵蓋表）。

    2026-09-02 線框 `ia-wireframe.html` Tab 05 抽出，成為**唯讀**的「NAV 累積狀態」區塊。

    ⚠️ **它必須畫在「手動補資料」之前**（線框的區塊順序就是這樣排的）——
    雲端沒啟用時，那一區的三條寫入路徑**都寫不進雲端**。把狀態放在動作之後，
    使用者會先上傳完才發現東西沒存進去（`CLAUDE.md §1`：不可讓畫面看起來成功）。
    ⚠️ 兩區之間**夾著「連線與金鑰」**（線框順序），所以守衛錨的是**兩個區塊的相對順序**，
    不是「相鄰」—— 錨到相鄰會在 ⑤ 重組（T18）當天無故轉紅。

    ⭐ **三態顏色（2026-09-02 總管裁決；本函式最重要的一條）**
    ------------------------------------------------------------
    四大鐵則的三態是：**灰 ＝ 未載入／前提不足**、深莓紅左軌 ＝ 業務警示、
    **紅框 ＝ 系統真出錯**。「雲端沒設好 → 累積未啟用」是**前提不足**，
    ~~不是系統故障~~ —— 它以前畫成 `st.error` 紅框，那是**過度示警**：
    什麼都沒有壞，只是還沒設定。**有意識的更正，不是漏刪**（日期 2026-09-02 ·
    決策者：AI 總管 · 依據：`CLAUDE.md` 引 v3 §02「介面狀態嚴格分離：
    『未點擊載入』以灰色說明提示，『系統真出錯』才標註紅色警示，**杜絕假性錯誤滿版**」）。
    **舊寫法的用意仍然成立**（這件事很重要、使用者必須看到），
    **被權衡掉的是它的顏色** —— 重要不等於故障，而滿版假紅字會讓**真正的紅**沒人看得見。

    **兩種狀態都要畫得出來，而且各有守衛**：
    - **沒設定** → 灰色空狀態三要素（標題 / 缺什麼 / 去哪補），走 `not_ready()`。
    - **設定了但查詢真的爆掉** → `system_error()` 紅框（下方 `except` 分支，一字未動）。
    """
    # v19.362 ①:累積狀態燈 — 終結「secrets 沒設 = 靜默略過,以為在累積其實沒有」
    try:
        # 稽核 N1-d:改走本檔頂部的 TTL 快取包裝(顯示語意不變,只擋重複打 API)
        _ni_st = _cached_nh_status()
        if _ni_st["enabled"]:
            st.caption("🟢 **累積狀態:已啟用** — App 抓到的淨值會自動累積到 "
                       "Google Sheet `nav_history` 分頁")
        else:
            # v19.379:細分病因(放錯地方 / 引號貼壞 / 整份 secrets 沒生效)
            _diag = _ni_st.get("diag", {})
            _lines = []
            _sa_d = _diag.get("google_service_account")
            if _sa_d == "absent":
                _lines.append("• `google_service_account`:**App 完全沒讀到這把 key** → 檢查："
                              "有按 **Save** 嗎?有 **Reboot app** 嗎?名字是不是**全小寫**?"
                              "是不是存在**這個 App**(不是別的 App / 不是 GitHub)的 Secrets?")
            elif _sa_d == "unparseable":
                _lines.append("• `google_service_account`:**有讀到值,但 JSON 解析失敗** → "
                              "包 JSON 要用 `'''`(三個**單**引號,不是雙引號);檢查內容有沒有貼歪 / 缺字 / 結尾少了 `'''`。")
            elif _sa_d == "no_client_email":
                _lines.append("• `google_service_account`:JSON 有解析但**缺 client_email** → JSON 貼不完整。")
            if _diag.get("macro_weights_sheet_id") == "absent":
                _lines.append("• `macro_weights_sheet_id`:**沒讀到** → 同上(全小寫、放對 App、Save + Reboot)。")
            if _diag.get("st_secrets_alive") is False:
                _lines.append("⚠️ 連既有的 `FRED_API_KEY` 都讀不到 → **整份 secrets 沒生效**"
                              "(TOML 格式壞 / 放錯 App / 沒 reboot),不是這兩把單獨的問題。")
            elif _diag.get("st_secrets_alive") is True:
                _lines.append("✅ 旁證:`FRED_API_KEY` 讀得到 → secrets 本身有效,問題**只在上面這兩把**。")
            # ⬜ 灰色空狀態三要素（標題 / 缺什麼 / 去哪補）—— 不是紅框，理由見 docstring。
            # 「去哪補」指的是 Streamlit Secrets（App 設定），**不是**頁內某個分區：
            # 這兩把 key 今天只能在 Secrets 設，指去頁內任何區塊都是假指路。
            # ⚠️ 刻意**不手抄任何分區/分頁名** —— 手抄的那一刻它就開始漂移
            # （story_nav 整個模組存在的理由）。
            not_ready(
                f"NAV 累積未啟用：尚未設定 {', '.join(_ni_st['missing'])} "
                "→ 淨值不會累積、「手動補資料」也寫不進雲端",
                where="App 的 Secrets 設定")
            if _lines:
                # 細分病因（放錯地方 / 引號貼壞 / 整份 secrets 沒生效）——
                # 內容一字未改，只是跟著上面那則一起改走灰色。
                st.caption("\n\n".join(_lines))
    except Exception as _e_st:
        # 這顆燈答的是「能不能累積」。它自己掛掉時,畫面上沒有燈 ——
        # 與「燈是綠的」在灰字之下難以分辨。
        system_error("NAV 累積狀態檢查失敗", _e_st,
                     hint="這次查不出雲端 nav_history 能不能寫入,不代表它是好的。")

    # ── 2026-08-11:「累了多少」——上面那顆燈只答「能不能累」 ────────────────
    # 為什麼要加：燈是綠的、每次抓取都有「本次新存 N 筆」、序列卻可以好幾週
    # 一動不動 —— 因為累到的點還全部落在 live 的滾動窗內
    # (`fund_service._merge_nav_history_series` 的 `added <= 0` 分支)。
    # 這三件事同時成立時，畫面上原本**沒有任何地方**講得出中間的落差(§5 可觀測)。
    try:
        # 稽核 N1-d:同上,改走 TTL 快取包裝(這支會讀整張 nav_history 分頁,最貴)
        _cov_map = _cached_nh_coverage()   # 未啟用 / 無 tab → {}（≠ 0 點，語意不同）
        if _cov_map:
            import pandas as _pd_cov
            _cov_rows = [
                {"代碼": _c,
                 "累積點數": _v["points"],
                 "最早": _v["first"],
                 "最新": _v["last"],
                 "涵蓋天數": _v["span_days"],
                 "≈年": round(_v["span_days"] / 365.0, 2)}
                for _c, _v in sorted(_cov_map.items())
            ]
            st.caption(
                f"**目前累積：{len(_cov_map)} 檔**。"
                "⚠️ 「累積點數」不等於「序列變長」——當累到的點還落在 App 每次抓到的"
                "近期窗（約近 30 個交易日）之內時，合併後筆數不會增加。"
                "要等最舊的累積點掉出那個窗，序列才會開始真的加長。"
                "想立刻補回過去數年，用下面的 CSV 匯入。")
            st.dataframe(_pd_cov.DataFrame(_cov_rows),
                         hide_index=True, width="stretch")
        else:
            st.caption("⬜ `nav_history` 分頁目前讀不到任何累積點 —— "
                       "可能是尚未啟用（見上方狀態燈）或分頁還沒建立。"
                       "**這與「累積 0 點」不同**：讀不到就是不知道，不是沒有。")
    except Exception as _e_cov:
        # §1：讀失敗要講出來，不可留白讓人以為「沒累積」。
        # ⚠️ 對照上方 else 分支：「讀不到任何累積點 —— 可能尚未啟用」是**真的
        # 還沒有** → 維持灰色一字未動;這裡是**讀爆了**,整張涵蓋表消失。
        system_error("累積內容讀取失敗", _e_cov,
                     hint="這與「累積 0 點」不同 —— 讀不到就是不知道,不是沒有。"
                          "上方分析本身不受影響。")


def render_nav_statement_csv_import() -> None:
    """① 對帳單 CSV → 雲端 nav_history（單檔、代碼手填、可吃無代號欄的兩欄 CSV）。

    2026-09-02 線框 §03 ⑤ B「合一」抽出（**只搬位置，行為一行未改**）。

    ⚠️ **與 `ui/tab_manage.py::render_nav_csv_manage_section()` 不等價，不可互相取代**：
    本函式走 `nav_history_gs.import_csv_text` —— 代碼由使用者手填、**只寫雲端**、
    CSV 不需要代號欄（header 對欄，或第 1 欄=日期、第 2 欄=淨值），
    這正是保險公司對帳單匯出的形狀。那一條走 `import_nav_csv_multi` ——
    **必須有代號欄**、可一次多檔、而且**會寫本地 `cache/nav_history/{code}.json` 當基底**。
    線框要的是「三個功能**一個入口**」，不是「三個功能砍成一個」。

    ⚠️ **`tests/test_ia_tab5_nav_history_merge.py` 的「送出才寫」守衛（2026-09-03 稽核必修 1）
    射程只到「這一支 writer」，不是「任何雲端寫入」** —— 那對守衛用 spy 監看的是
    **`services.nav_history_gs.import_csv_text` 這個具體符號被呼叫幾次**，不是「有沒有東西
    寫進了 nav_history」。若程式碼改走同模組的 `append_points`（或任何不經
    `import_csv_text` 的路徑）直接寫雲端，該守衛**看不到**——本組已實測過一次
    側通道突變（把上面 `elif` 的 gate 判斷繞開、改呼叫 `append_points`），
    `test_statement_csv_does_not_write_until_submitted` /
    `test_statement_csv_writes_exactly_once_when_submitted` **兩條依然全綠**，
    因為它們的 spy 只掛在 `import_csv_text` 上。**這不是本次守衛的缺陷（它守的東西本來就是
    「這條路徑走它自己該走的函式」），只是讀者不該把它讀成一道「攔截所有寫入」的閘門。**
    """
    st.caption(
        "從保險公司網站 / 對帳單下載歷史淨值 CSV，一次灌入 Google Sheet "
        "`nav_history` 分頁 —— **立刻補回過去數年**，解鎖 3Y/5Y/低基期（不必等每日累積）。"
        "格式：header 含「日期/淨值」關鍵字自動對欄；無 header 則第 1 欄=日期、第 2 欄=淨值。"
        "民國(113/03/15)與西元日期都支援；同 (代碼,日期) 自動去重，重跑不灌水。")
    # 鐵則 02（線框 `ia-wireframe.html` Rule 02 ＋ Tab 05「手動補資料 → **寫入類**，
    # 全部 Form 封裝」）：三個輸入 + 一顆送出鈕。不包 form 的話使用者每打一個字整頁
    # 就重跑一次，而本頁的重跑會連帶更新資料註冊表、抓匯率。
    # ⚠️ 送出鈕的 `disabled=` **刻意拿掉**：form 內 widget 的值要等送出才拿得到，
    #    拿它算 disabled 會永遠停在初始值（按鈕永遠是 disabled）。
    #    改成送出後才驗，缺什麼就誠實講 —— 而且那是 ⬜ 前提不足，不是 🔴 故障。
    with applied_form("navhist_import_form",
                      submit_label="📥 匯入到 nav_history") as _ni_gate:
        _ni_c1, _ni_c2 = st.columns(2)
        with _ni_c1:
            _ni_code = st.text_input("基金代碼", key="navhist_import_code",
                                     placeholder="TLZF9 / ACTI71 ...")
        with _ni_c2:
            _ni_name = st.text_input("基金名稱（選填）", key="navhist_import_name")
        _ni_file = st.file_uploader("上傳歷史淨值 CSV", type=["csv", "txt"],
                                    key="navhist_import_file")
    if _ni_gate and not (_ni_file and (_ni_code or "").strip()):
        not_ready("還沒選好要匯入的東西：基金代碼與 CSV 檔**兩者都要有**",
                  where="上方「基金代碼」與「上傳歷史淨值 CSV」")
    elif _ni_gate:
        try:
            _ni_text = _ni_file.getvalue().decode("utf-8-sig", errors="replace")
            from services.nav_history_gs import import_csv_text
            _ni_res = import_csv_text(_ni_code.strip().upper(), _ni_text,
                                      fund_name=_ni_name.strip())
            if not _ni_res["enabled"]:
                # 「資料源未設定」屬 ⬜,不是 🔴 —— 匯入沒壞,是還沒接上(線框 §03)。
                not_ready("Google Sheets 未設定，無法匯入",
                          where="Secrets 的 `google_service_account` / "
                                "`macro_weights_sheet_id`")
            elif _ni_res["written"] > 0:
                # 稽核 N1-d:剛寫進去 → 立刻讓上方「累積狀態 / 累了多少」失效重讀,
                # 否則 TTL 內會顯示寫入前的點數（§1 不顯示過期值）。
                _clear_nh_caches()
                st.success(
                    f"✅ 匯入完成：{_ni_res['rows']} 列 → 解析 {_ni_res['parsed']} 筆 → "
                    f"**新寫入 {_ni_res['written']} 筆**"
                    f"（重複略過 {_ni_res['skipped_dup']}、壞列 {_ni_res['skipped_rows']}）。"
                    f"下次分析該基金時會自動併入計算。")
            else:
                st.warning(
                    f"⚠️ 0 筆新寫入：{_ni_res['rows']} 列 → 解析 {_ni_res['parsed']} 筆"
                    f"（重複略過 {_ni_res['skipped_dup']}、壞列 {_ni_res['skipped_rows']}）。"
                    f"請確認 CSV 欄位（日期/淨值）與代碼是否正確。")
        except Exception as _e_ni:
            st.error(f"❌ 匯入失敗：[{type(_e_ni).__name__}] {str(_e_ni)[:400]}")
