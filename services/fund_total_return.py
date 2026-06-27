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
            src = ("wb01 (MoneyDJ 官方)" if _ps == "wb01"
                   else "本地還原淨值法 (v18.71)" if _ps == "local_calc"
                   else "perf['1Y']")
            return float(v), src
    except (TypeError, ValueError):
        pass

    # 2. ret_1y_total (本地含息計算)
    try:
        v = m.get("ret_1y_total")
        if v is not None:
            _wd = m.get("ret_1y_window_days") or 365
            src = (f"ret_1y_total (本地, {_wd}d 窗口)" if _wd < 350
                   else "ret_1y_total (本地含息)")
            return float(v), src
    except (TypeError, ValueError):
        pass

    # 3. ret_1y (純 NAV 變化)
    try:
        v = m.get("ret_1y")
        if v is not None:
            return float(v), "ret_1y (純 NAV,不含息)"
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
                            return ret * scale, f"NAV 序列年化 ({d_actual}d 外推)"
    except Exception as _e:
        import sys as _sys
        print(f'[fund_total_return] nav annualize fallback fail: '
              f'{type(_e).__name__}: {_e}', file=_sys.stderr)

    return None, "—"
