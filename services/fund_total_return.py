"""v19.175 — 1Y 含息報酬率統一 fallback chain(L2 純函式,zero-IO)。

從 `ui/helpers/macro_helpers.py` 搬入,理由:
- 函式無 streamlit 依賴,本就是純函式
- L2 service(`services/fund_dividend_health.py`)需要呼叫它做吃本金燈號判定
  → §8.2 規定 L2 不得 import L3 → 搬到 L2 才能合法 SSOT 化

caller:
- `ui/helpers/macro_helpers.py` shim re-export 保持向後相容
- `services/fund_dividend_health.check_eating_principal_1y_mk()` 直接呼叫

precedence(最權威 → 次選):
  1. perf["1Y"]      wb01 真 1Y / 本地還原淨值法注入(v18.65/v18.71)
  2. ret_1y_total    本地含息計算(可能短窗口年化)
  3. ret_1y          純 NAV 變化率(不含息)
  4. NAV 序列年化    最後手段(≥30d 才用,scale cap 12x)
"""
from __future__ import annotations

# ── 「1Y 來源」欄 / Tab2 KPI 卡的顯示值(SSOT;呼叫端與測試一律 import)────────
# 2026-08-10 user 拍板:這些字串會**原樣印給使用者看**,不能是內部代號。
# 原本印的是外站網頁代號、內部欄位名與內部版號,使用者完全無從判斷這個報酬率
# 到底是「官方公布的」還是「本站自己推算的」—— 而那正是本欄唯一的用途(§2.2)。
#
# 規則同「Sharpe 來源」欄:官方值以「MoneyDJ 官方」開頭、自算值以「自算」開頭,
# 括號裡補上口徑差異(含不含配息 / 樣本只有幾天)。可靠度由高到低即宣告順序。
SRC_OFFICIAL = "MoneyDJ 官方"                      # 官方績效表現成數字,最可信
SRC_SELF_RESTORED = "自算（還原含息淨值）"          # 官方沒給 → 用淨值 + 配息記錄還原
SRC_PERF_UNLABELED = "績效表（來源未標註）"         # 有績效值但沒標來源 → 誠實說不知道(§1)
SRC_SELF_TOTAL = "自算含息"                        # 短窗時 → f"{SRC_SELF_TOTAL}（僅 N 天窗口）"
SRC_SELF_NAV_ONLY = "自算（僅淨值，不含配息）"
SRC_SELF_ANNUALIZED = "自算（{days} 天資料外推年化）"   # 最不可靠的一層
SRC_NONE = "—"

# Tab2 吃本金 KPI 卡用:命中任一片語 = 「這個 1Y 是本站算的,且可能不足一整年」,
# 該卡會把欄名從「1Y 含息報酬」改標成實際天數。涵蓋範圍**刻意**與改文案前一致:
# 還原淨值法 / 自算含息 / 外推年化 三條會改標;SRC_SELF_NAV_ONLY 本身就是完整
# 一年的淨值變化,不在此列(改文案不順手改行為)。
LOCAL_WINDOW_SENSITIVE_HINTS = ("還原含息淨值", "自算含息", "外推年化")


def is_extrapolated_1y_source(source_label: str) -> bool:
    """該 tr1y 是否為『短窗淨值 ×最多12 外推年化』(`SRC_SELF_ANNUALIZED`)。

    v19.448 稽核修:這是 4 層 fallback 中**最不可靠**的一層 —— 拿幾十天淨值算個跌幅
    再 ×最多 12 倍年化,(a) 不含配息、(b) 短窗外推會爆掉,且**根本不是真實一年報酬**。
    ACTI71 顯示的 −38.18% 就是這條:近一年淨值其實上漲,卻被外推成大負數 → 假 🔴 嚴重。
    吃本金判定端命中此來源時應**拒判**(⚪ 資料不足),不可拿它報紅燈(§1 Fail Loud)。

    註:`SRC_SELF_NAV_ONLY`(純淨值不含配息,源#3)的「重複扣配息」是另一個較廣的議題
    (影響多檔 + SSOT 測試),待 user 核准範圍後另行處理,本函式**不**涵蓋。
    """
    return "外推年化" in str(source_label or "")


def compute_1y_total_return(fund_obj: dict) -> tuple[float | None, str]:
    """從 fund object 取「1Y 含息報酬率(%)」+ 來源標籤。

    Args:
        fund_obj: 支援 **3 種 shape**:
          - **Nested**(Tab2 / Tab3):`{metrics, moneydj_raw: {perf, ...}, series, perf_source}`
          - **Flat**(健診表 v19.178+ via `_auto_fetch_moneydj()` 直接結果):
            `{perf, series, metrics, dividends, perf_source, ...}` — 整包就是 MoneyDJ raw
          - **Hybrid**(legacy):mixed
        v19.178 入口加 shape detect:flat → 自動 wrap 成 nested,避免拿不到 perf['1Y'] 走錯 fallback。

    Returns:
        (value, source_label)
        value=None 表示所有來源均無資料
    """
    # v19.178 shape normalize:flat fd(top-level 有 perf 但無 moneydj_raw)
    # → 把整包當 moneydj_raw,後續 mj.get("perf") 路徑能命中。
    # 修「健診表 _auto_fetch_moneydj 平坦 fd 強迫走 NAV 序列年化 fallback,
    # 跟 Tab2 nested 拿 wb01 perf['1Y'] 結論不同(🟢 vs 🔴)」。
    if "moneydj_raw" not in fund_obj and "perf" in fund_obj:
        fund_obj = {
            "moneydj_raw": fund_obj,
            "metrics": fund_obj.get("metrics") or {},
            "series": fund_obj.get("series"),
            "perf_source": fund_obj.get("perf_source"),
        }

    m = fund_obj.get("metrics") or {}
    mj = fund_obj.get("moneydj_raw") or {}
    pf = mj.get("perf") or {}

    # 1. perf["1Y"] (wb01 / local_calc 注入) — 最權威
    try:
        v = pf.get("1Y")
        if v is not None:
            _ps = str(fund_obj.get("perf_source") or mj.get("perf_source") or "").lower()
            src = (SRC_OFFICIAL if _ps == "wb01"
                   else SRC_SELF_RESTORED if _ps == "local_calc"
                   else SRC_PERF_UNLABELED)
            return float(v), src
    except (TypeError, ValueError):
        pass

    # 2. ret_1y_total (本地含息計算)
    try:
        v = m.get("ret_1y_total")
        if v is not None:
            _wd = m.get("ret_1y_window_days") or 365
            src = (f"{SRC_SELF_TOTAL}（僅 {_wd} 天窗口）" if _wd < 350
                   else SRC_SELF_TOTAL)
            return float(v), src
    except (TypeError, ValueError):
        pass

    # 3. ret_1y (純 NAV 變化)
    try:
        v = m.get("ret_1y")
        if v is not None:
            return float(v), SRC_SELF_NAV_ONLY
    except (TypeError, ValueError):
        pass

    # 4. NAV 序列年化 fallback
    try:
        import pandas as _pd
        s = fund_obj.get("series")
        if s is not None and hasattr(s, "dropna"):
            ss = s.dropna()
            if len(ss) >= 3:
                t_now = ss.index[-1]
                t_tgt = t_now - _pd.Timedelta(days=365)
                ix = ss.index.get_indexer([t_tgt], method="nearest")[0]
                if 0 <= ix < len(ss) - 1:
                    d_actual = (t_now - ss.index[ix]).days
                    if d_actual >= 30:
                        v_now = float(ss.iloc[-1])
                        v_old = float(ss.iloc[ix])
                        if v_old > 0:
                            ret = (v_now / v_old - 1.0) * 100.0
                            # 短窗口 cap 12x 避免極端外推
                            scale = min(365.0 / d_actual, 12.0)
                            return ret * scale, SRC_SELF_ANNUALIZED.format(days=d_actual)
    except Exception as _e:
        import sys as _sys
        print(f'[fund_total_return] nav annualize fallback fail: '
              f'{type(_e).__name__}: {_e}', file=_sys.stderr)

    return None, SRC_NONE
