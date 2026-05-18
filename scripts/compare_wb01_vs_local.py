"""一次性對照腳本：MoneyDJ wb01 官方含息 vs 本地還原淨值法 vs 純 NAV。

用法：
    python scripts/compare_wb01_vs_local.py <FUND_CODE> [<FUND_CODE> ...]

例：
    python scripts/compare_wb01_vs_local.py JF53 JFZN3

需先在本機 .streamlit/secrets.toml 配好 cnyes / moneydj 來源（dashboard 平常能跑就行）。
"""
import sys
import pandas as pd

from fund_fetcher import (
    fetch_fund_full,
    calculate_fund_total_return,
    calc_metrics,
)


def _trailing_1y(s: pd.Series) -> tuple[float | None, int]:
    """純 NAV 1Y 變化（不含息）"""
    if s is None or len(s) < 20:
        return None, 0
    s = s.dropna().sort_index()
    end_dt = s.index[-1]
    start_dt = end_dt - pd.Timedelta(days=365)
    pos = s.index.searchsorted(start_dt)
    if pos >= len(s):
        return None, 0
    p0 = float(s.iloc[pos]); p1 = float(s.iloc[-1])
    span = (end_dt - s.index[pos]).days
    if p0 <= 0:
        return None, span
    return round((p1 / p0 - 1.0) * 100, 2), span


def compare(code: str) -> None:
    print(f"\n=== {code} ===")
    try:
        res = fetch_fund_full(code)
    except Exception as e:
        print(f"  fetch_fund_full 失敗：{e}")
        return

    perf = (res.get("moneydj_raw") or {}).get("perf") or {}
    perf_src = res.get("perf_source") or "(none)"
    wb01_1y = perf.get("1Y")
    name = res.get("name") or ""

    s = res.get("series")
    divs = res.get("dividends") or []

    nav_1y, nav_span = _trailing_1y(s)

    # 還原淨值法 1Y
    adj_1y = None
    if s is not None and len(s) >= 20:
        nav_df = pd.DataFrame({"Date": pd.to_datetime(s.index), "NAV": s.values.astype(float)})
        rows = []
        for d in divs:
            try:
                amt = float(d.get("amount", 0) or 0)
                if amt <= 0:
                    continue
                dt = pd.to_datetime(str(d.get("date", "") or "").replace("/", "-"))
                rows.append({"Date": dt, "Dividend": amt})
            except Exception:
                continue
        div_df = pd.DataFrame(rows) if rows else pd.DataFrame()
        tr = calculate_fund_total_return(nav_df, div_df)
        end_dt = pd.to_datetime(s.index[-1])
        start_dt = end_dt - pd.Timedelta(days=365)
        mask = tr["Date"] >= start_dt
        if mask.any():
            a0 = float(tr.loc[mask, "Adj_NAV"].iloc[0])
            a1 = float(tr["Adj_NAV"].iloc[-1])
            if a0 > 0:
                adj_1y = round((a1 / a0 - 1.0) * 100, 2)

    # 對照舊版單利加總（calc_metrics 也會回，但這裡走 ret_1y_total 已是新公式）
    m = calc_metrics(s, divs) if s is not None else {}
    ret_1y_total = m.get("ret_1y_total")
    ret_1y_window = m.get("ret_1y_window_days")

    n_div_12m = sum(1 for d in divs if pd.to_datetime(
        str(d.get("date", "") or "").replace("/", "-")) >= pd.Timestamp.now() - pd.Timedelta(days=365))
    sum_div_12m = sum(float(d.get("amount", 0) or 0) for d in divs if pd.to_datetime(
        str(d.get("date", "") or "").replace("/", "-")) >= pd.Timestamp.now() - pd.Timedelta(days=365))

    print(f"  名稱            : {name}")
    print(f"  perf_source     : {perf_src}")
    print(f"  NAV 點數         : {0 if s is None else len(s)}")
    print(f"  近 12M 配息次數  : {n_div_12m}（合計 {sum_div_12m:.4f}）")
    print(f"  ── 1Y 含息報酬對照 ──")
    print(f"  ① wb01 官方     : {wb01_1y}%")
    print(f"  ② 還原淨值法    : {adj_1y}%   (本地，v18.71)")
    print(f"  ③ ret_1y_total  : {ret_1y_total}%   (calc_metrics 內部，window={ret_1y_window}d)")
    print(f"  ④ 純 NAV 變化    : {nav_1y}%   (span={nav_span}d，不含息)")
    if wb01_1y is not None and adj_1y is not None:
        diff = round(adj_1y - float(wb01_1y), 2)
        print(f"  Δ(② − ①)        : {diff:+.2f}pp")


if __name__ == "__main__":
    codes = sys.argv[1:] or ["JF53"]
    for c in codes:
        compare(c.strip().upper())
