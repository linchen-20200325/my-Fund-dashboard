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
  4. NAV 序列年化    最後手段(跨度須 ≥ `RET_1Y_EXTRAPOLATE_MIN_DAYS`,scale cap 2x)

2026-08-14 稽核 E1:第 4 層原本 30 天就敢 ×12 外推,大表因此印出 +201% 的台幣基金。
現在跨度不足半年直接回 `(None, SRC_TOO_SHORT)`;四層出口另加合理性帶標記
(`is_implausible_1y`),離譜值不改不丟、但來源標籤會自己講話。門檻全走
`shared/signal_thresholds.py` SSOT。
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
# 稽核 E1(2026-08-14):跨度不足以外推 → 誠實留白,並把「為什麼是空的」寫在來源欄。
# 舊行為是拿 30 天漲幅 ×12 印一個 +201% 的數字出來(§1 禁止的「估一個合理值」)。
SRC_TOO_SHORT = "—（僅 {days} 天資料，不足以推算一年）"
# 值落在合理帶外時,**附加**在來源標籤後面(不改值、不丟值,只讓它自己講話)
SRC_IMPLAUSIBLE_SUFFIX = "　⚠️ 數值異常大，請先核對幣別與除息"


def is_implausible_1y(value) -> bool:
    """該 1Y 含息報酬是否落在合理帶外(§3.2 範圍檢查)。

    稽核 E1:大表出現 +201.65% / +190.64% 的**台幣**基金,在畫面上與正常數字
    長得一模一樣,還會因為數值大而排到最前面。這裡不改值也不丟值 —— 只回答
    「這格該不該打問號」,由呼叫端決定要在標籤 / 表格上怎麼標(§1 標記而非掩蓋)。

    門檻走 `shared.signal_thresholds` SSOT(§3.3 禁 inline magic)。
    """
    from shared.signal_thresholds import (
        RET_1Y_PLAUSIBLE_MAX_PCT,
        RET_1Y_PLAUSIBLE_MIN_PCT,
    )
    try:
        v = float(value)
    except (TypeError, ValueError):
        return False
    if v != v:  # NaN
        return False
    return v > RET_1Y_PLAUSIBLE_MAX_PCT or v < RET_1Y_PLAUSIBLE_MIN_PCT


def _flag_if_implausible(value, source_label: str) -> tuple[float, str]:
    """統一出口:值離譜就把警語黏在來源標籤上。所有 4 條 fallback 共用。

    ⚠️ `float(value)` 對無法轉數字的值會拋 ValueError/TypeError,而三條 caller
    外面各有一個 `except (TypeError, ValueError): pass` —— 也就是說壞值會**沉默地**
    降級到下一層 fallback。行為結果沒錯(下一層本來就該接手),但沉默不合 §3.3,
    故在這裡先攔下來記一筆 stderr,讓「這個源給了垃圾」留得下痕跡。
    """
    try:
        v = float(value)
    except (TypeError, ValueError):
        import sys as _sys
        print(f"[fund_total_return] 來源 {source_label!r} 給出無法轉數字的值 "
              f"{value!r} → 降級到下一層 fallback", file=_sys.stderr)
        raise
    if is_implausible_1y(v):
        return v, f"{source_label}{SRC_IMPLAUSIBLE_SUFFIX}"
    return v, source_label

# Tab2 吃本金 KPI 卡用:命中任一片語 = 「這個 1Y 是本站算的,且可能不足一整年」,
# 該卡會把欄名從「1Y 含息報酬」改標成實際天數。涵蓋範圍**刻意**與改文案前一致:
# 還原淨值法 / 自算含息 / 外推年化 三條會改標;SRC_SELF_NAV_ONLY 本身就是完整
# 一年的淨值變化,不在此列(改文案不順手改行為)。
LOCAL_WINDOW_SENSITIVE_HINTS = ("還原含息淨值", "自算含息", "外推年化")


def is_extrapolated_1y_source(source_label: str) -> bool:
    """該 tr1y 是否為『短窗淨值 ×最多12 外推年化』(`SRC_SELF_ANNUALIZED`)。

    v19.448 稽核修:這是 4 層 fallback 中**最不可靠**的一層 —— 拿短窗淨值算個跌幅
    再放大年化,(a) 不含配息、(b) 短窗外推會爆掉,且**根本不是真實一年報酬**。
    ACTI71 顯示的 −38.18% 就是這條:近一年淨值其實上漲,卻被外推成大負數 → 假 🔴 嚴重。
    吃本金判定端命中此來源時應**拒判**(⚪ 資料不足),不可拿它報紅燈(§1 Fail Loud)。

    2026-08-14 稽核 E1 後,外推門檻與倍數上限改走 `shared/signal_thresholds` SSOT
    (原本寫死 ≥30 天 / cap 12x)。跨度未達門檻者根本拿不到值,改由
    `is_too_short_1y_source()` 辨識 —— 本函式**不**涵蓋那一種。

    註:`SRC_SELF_NAV_ONLY`(純淨值不含配息,源#3)的「重複扣配息」是另一個較廣的議題
    (影響多檔 + SSOT 測試),待 user 核准範圍後另行處理,本函式**不**涵蓋。
    """
    return "外推年化" in str(source_label or "")


def is_too_short_1y_source(source_label: str) -> bool:
    """該 tr1y 之所以是 None,是不是因為「有淨值序列、但跨度不足以推算一年」?

    稽核 E1 後多出來的第五種狀態,必須與「**連序列都沒有**」分得開:
      - 沒有序列        → 這檔根本無從判定,維持既有契約回 None
      - 有序列但太短    → 這是「⚪ 資料不足」,消費端仍應顯示、仍拿得到年化配息率

    兩者混成同一個 None,會讓短窗那批基金的「換標的建議」從 🟢 保留掉成
    ⬜ 資料不足,而且 4D 的配息維度連帶失效(§1:兩種狀態要分得開)。
    """
    return "不足以推算一年" in str(source_label or "")


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
            # 稽核 E1:官方值也過閘 —— 抓錯欄 / 幣別搞混時 MoneyDJ 也會給出離譜數字
            return _flag_if_implausible(v, src)
    except (TypeError, ValueError):
        pass

    # 2. ret_1y_total (本地含息計算)
    try:
        v = m.get("ret_1y_total")
        if v is not None:
            _wd = m.get("ret_1y_window_days") or 365
            src = (f"{SRC_SELF_TOTAL}（僅 {_wd} 天窗口）" if _wd < 350
                   else SRC_SELF_TOTAL)
            return _flag_if_implausible(v, src)
    except (TypeError, ValueError):
        pass

    # 3. ret_1y (純 NAV 變化)
    try:
        v = m.get("ret_1y")
        if v is not None:
            return _flag_if_implausible(v, SRC_SELF_NAV_ONLY)
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
                    # ── 稽核 E1:外推門檻 30 → RET_1Y_EXTRAPOLATE_MIN_DAYS ──────
                    # 舊碼:30 天窗 × min(365/30, 12) = ×12。一檔 30 天漲 17% 的基金
                    # 會在大表印出「1Y 含息報酬 +201%」,而且因為數值大而排到最前面。
                    # 那不是量出來的一年報酬,是把一個月的運氣乘了十二次(§1 禁止)。
                    # 未達半年 → 誠實回 None,並在來源欄寫清楚只有幾天資料。
                    from shared.signal_thresholds import (
                        RET_1Y_EXTRAPOLATE_MAX_SCALE,
                        RET_1Y_EXTRAPOLATE_MIN_DAYS,
                    )
                    if d_actual < RET_1Y_EXTRAPOLATE_MIN_DAYS:
                        return None, SRC_TOO_SHORT.format(days=d_actual)
                    v_now = float(ss.iloc[-1])
                    v_old = float(ss.iloc[ix])
                    if v_old > 0:
                        ret = (v_now / v_old - 1.0) * 100.0
                        # 跨度 ≥ 半年後 scale 自然 ≤ 365/180 ≈ 2.03;cap 取 2.0 收口
                        scale = min(365.0 / d_actual, RET_1Y_EXTRAPOLATE_MAX_SCALE)
                        return _flag_if_implausible(
                            ret * scale, SRC_SELF_ANNUALIZED.format(days=d_actual))
    except Exception as _e:
        import sys as _sys
        print(f'[fund_total_return] nav annualize fallback fail: '
              f'{type(_e).__name__}: {_e}', file=_sys.stderr)

    return None, SRC_NONE
