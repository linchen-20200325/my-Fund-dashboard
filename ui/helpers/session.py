"""ui/helpers/session.py — Session state 共用 helper（v11.0 D-20 從 app.py 抽出）

設計原則：
- **純運算**：不直接 `import streamlit`、不讀寫 session_state
- caller 自行傳 indicators dict / session_state 物件，本層只算
- 避免「helper 內讀 module-level 全局」造成的測試難度

公開 API：
  - D5_FRED_KEYS               — v19.195 SSOT:12 個 FRED 指標代碼
  - D5_YF_KEYS                 — v19.195 SSOT:4 個 Yahoo 指標代碼
  - D5_KEYS                    — v19.195 SSOT:union 16 個(D5_FRED_KEYS + D5_YF_KEYS)
  - _D5_KEYS                   — backward compat alias = D5_KEYS
  - calc_data_health(ind)      — 純函式:16 指標填充率 → (pct, traffic)
  - INITIAL_SESSION_STATE      — Streamlit session_state 預設字典
  - init_session_state(ss)     — 為缺失 key 補預設值(caller 傳 st.session_state)

v11.0 分層歸位：本檔屬於 ui/helpers/,可被 ui/tab*.py 共用;
本身不 import streamlit,方便單測。

v19.195 SSOT 統一:Tab5(`ui/tab5_data_guard.py:135-138 第 ⓪ 區 + 347-349
第 ② 區`)原 hardcode 同一份 12 FRED + 4 Yahoo 共 16 keys × 2 處,改 import
本檔 D5_FRED_KEYS / D5_YF_KEYS 統一;`_D5_KEYS` 保留為 backward compat alias。
"""
from __future__ import annotations


# v19.195 SSOT:12 個 FRED 指標 internal key(與 fetch_all_indicators 一致)
D5_FRED_KEYS = ["PMI", "YIELD_10Y2Y", "YIELD_10Y3M", "HY_SPREAD",
                "M2", "FED_BS", "CPI", "FED_RATE", "UNEMPLOYMENT",
                "PPI", "SAHM", "SLOOS"]

# v19.195 SSOT:4 個 Yahoo 指標 internal key
D5_YF_KEYS = ["VIX", "DXY", "ADL", "COPPER"]

# v19.195 SSOT:union 16 keys — Data Guard 5 燈源(與 app.py Tab5 顯示一致)
D5_KEYS = D5_FRED_KEYS + D5_YF_KEYS

# backward compat alias(舊 caller 引用 _D5_KEYS)
_D5_KEYS = D5_KEYS


def calc_data_health(indicators: dict) -> tuple[int, str]:
    """16 個關鍵指標的填充率 → (pct, traffic)。

    Args:
        indicators: dict[str, dict]，每 key 對應 {"value": ..., ...}

    Returns:
        (pct, traffic): pct ∈ [0, 100]；traffic ∈ {"🔴", "🟡", "🟢"}
            <50% 🔴 / <80% 🟡 / ≥80% 🟢
    """
    ind = indicators or {}
    ok = 0
    for k in _D5_KEYS:
        v = (ind.get(k) or {}).get("value")
        # 三段檢查：非 None / 非空字串 / 非 NaN（v == v 為 False 當 NaN）
        if v is not None and str(v) != "" and v == v:
            ok += 1
    pct = round(ok / len(_D5_KEYS) * 100) if _D5_KEYS else 0
    traffic = "🔴" if pct < 50 else ("🟡" if pct < 80 else "🟢")
    return pct, traffic


# Streamlit session_state 啟動時注入的預設值
# 與 app.py:532-544 原 dict 1:1 對應
INITIAL_SESSION_STATE: dict = {
    "macro_done":         False,
    "indicators":         {},
    "phase_info":         {},
    "macro_last_update":  None,
    "macro_ai":           "",
    "prev_phase":         "",
    "phase_history":      [],
    "current_fund":       None,
    "fund_data":          None,
    "tdcc_results":       [],
    "mj_fund_data":       None,
    "portfolio_funds":    [],
    "portfolio_core_pct": 75,
    "news_items":         [],
    "systemic_risk_data": None,
    "api_latency_log":    [],
    "data_registry":      {},
}


def init_session_state(session_state) -> None:
    """為 session_state 中缺失的 key 補上預設值。

    Args:
        session_state: st.session_state（duck-typed；支援 `in` 與 `__setitem__`）
    """
    for _k, _v in INITIAL_SESSION_STATE.items():
        if _k not in session_state:
            session_state[_k] = _v


# ──────────────────────────────────────────────────────────────
# v18.126 B-C.4: 從 app.py 搬入 friendly_error / is_core_fund
# ──────────────────────────────────────────────────────────────
_CORE_WHITELIST = ["安聯收益成長","收益成長","多元收益","安聯多元入息","摩根多重收益","富達多重資產","聯博收益","柏瑞多重資產","施羅德多元收益","瀚亞多重資產","富蘭克林收益","先機多元收益"]
_CORE_KEYWORDS  = ["配息","高股息","投資等級債","非投資等級債","公司債","公債","債券","債","特別股","基建","公用事業","infrastructure","preferred","utility","corporate bond","income fund","bond fund","fixed income","收益","平衡","多元","多重資產","balanced","income","bond","fixed","dividend","多重收益","全球股息","全球高股息"]
_SAT_KEYWORDS   = ["科技","ai","半導體","生技","醫療","電動車","創新","綠能","機器人","網通","印度","越南","中國a股","a股","航太","theme","tech","growth","biotech","semiconductor","robot","ev","india","vietnam"]


def is_core_fund(fund_name: str) -> bool:
    """v18.126 從 app.py 搬入：依名稱關鍵字判斷核心 vs 衛星基金。"""
    name = (fund_name or "").lower()
    if any(w in name for w in _CORE_WHITELIST):
        return True
    if any(k in name for k in _CORE_KEYWORDS):
        return True
    if any(k in name for k in _SAT_KEYWORDS):
        return False
    return False


def friendly_error(title: str, exc: Exception, *, hint: str = "", level: str = "warning") -> None:
    """v18.126 從 app.py 搬入：統一錯誤呈現 — 避免 Terminal Traceback，但保留可展開技術細節。

    參數
    ----
    title : 白話標題（例如「基金 NAV 載入失敗」）
    exc   : 捕捉到的 Exception
    hint  : 給使用者的建議（可空）
    level : "warning" | "error" | "info"
    """
    import streamlit as st   # lazy import 避免 session.py 必要時可獨立測試
    import sys as _sys_mod
    import traceback as _tb_mod
    # v19.171:異常摘要(類型+首行訊息)上浮到主訊息,別藏在 expander 裡。
    # 過去使用者看到「總經指標載入失敗」+ 摺疊 expander → 不知道實際根因。
    # 現在直接顯示「SchemaError: date 不可重複」等關鍵字,並同步 print 到
    # stderr(Streamlit Cloud logs 抓得到,方便 user 截圖傳回。)
    _exc_label = f"`{type(exc).__name__}`"
    _exc_msg   = str(exc).strip().splitlines()[0] if str(exc).strip() else ""
    _exc_msg_short = _exc_msg[:200] + ("…" if len(_exc_msg) > 200 else "")
    body = f"**{title}** — {_exc_label}"
    if _exc_msg_short:
        body += f": {_exc_msg_short}"
    if hint:
        body += f"\n\n💡 {hint}"
    if level == "error":
        st.error(body)
    elif level == "info":
        st.info(body)
    else:
        st.warning(body)
    # stderr 鏡射(Streamlit Cloud log 可追)
    print(f"[friendly_error] {title} | {type(exc).__name__}: {exc}", file=_sys_mod.stderr)
    with st.expander("🔧 技術細節（給工程師）", expanded=False):
        st.code(f"{type(exc).__name__}: {exc}\n\n" + _tb_mod.format_exc(), language="python")


def parse_indicator_date(iv: dict) -> tuple[object, list[tuple[str, str]]]:
    """解析單一指標的最新資料日期，回 (idate or None, [(field, err_msg)...]).

    v18.125 B-C.3：從 app.py 搬出（原 _parse_indicator_date，line 418）。
    Tab5 熱力圖（PR #49 v18.16）內聯抽出，方便單元測試「日期解析失敗 → ⚠️ caption」
    這條 regression 路徑。
    優先序：series 最後一個日期 > iv.date 欄位。
    """
    import pandas as _pd_pid
    errs: list[tuple[str, str]] = []
    idate = None
    idate_raw = (iv or {}).get("date", "")
    if idate_raw:
        try:
            idate = _pd_pid.to_datetime(str(idate_raw)).date()
        except Exception as e:
            errs.append(("date", str(e)))
    iser = (iv or {}).get("series")
    if iser is not None:
        try:
            _s = _pd_pid.Series(iser).dropna()
            if len(_s) > 0:
                idate = _pd_pid.to_datetime(_s.index[-1]).date()
        except Exception as e:
            errs.append(("series", str(e)))
    return idate, errs
