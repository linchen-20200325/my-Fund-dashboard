"""services/adjusted_nav.py — 配息還原 NAV 序列(L2 純函式,v19.167)

CLAUDE.md §4.5 ⚠️:
> 配息切割(ex-date NAV 下跳)為基金特有業務調整,須評估是否做還原 NAV 序列
> (目前未實作,直接用源數據)。

§4.6 配息切割(ex-date 跳空):NAV 跳空 → 視業務需求做還原 NAV 或保留原序列
(目前保留原序列,但 Sharpe / σ 計算須警示)。

本模組實作配息還原(dividend-adjusted NAV),caller 在計算 Sharpe / σ 時可選用
還原序列以排除 ex-date 跳空雜訊。

設計(§8.1)
============
**單一職責**:把配息日 NAV 跳空填回去,還原「如未配息」的純漲跌序列。

**演算法**(由近至遠,累積放大):
```
For each dividend d_i with ex-date e_i and amount a_i:
    nav_before = nav_series[date < e_i].iloc[-1]   # ex-date 前一筆
    factor_i   = (nav_before + a_i) / nav_before    # > 1.0(因配息後 NAV 下跳)
    adj_nav[date < e_i] *= factor_i                 # ex-date 之前序列放大

回傳 adj_nav(維持 attrs)
```

**邊界**:
- 空 NAV / 空 dividends → 回傳原序列(不複製)
- dividends 含 ex-date 不在 NAV 範圍內 → skip(log warning)
- nav_before <= 0 → skip(避免 ÷0 + 負 factor)

**為什麼不用 pandas.DataFrame.adjust** 之類現成 API?
- pandas 無直接 dividend-adjust API(只有 split adjustment 在 yfinance/AdjClose)
- 基金 NAV 不像股價有 AdjClose 欄,須自算

**caller integration**(後續 follow-up,§-1 strict)
=================================================
本 PR 純加 helper + tests,**不**自動塞進 calc_metrics(避免改變既有 Sharpe / σ
數值,user 須先 review 是否切換)。caller 自行決定:
```python
adj_nav = adjust_nav_for_dividends(nav, divs)
metrics = calc_metrics(adj_nav, divs=[])   # 用還原序列,divs 傳空避免重複計入
```
"""
from __future__ import annotations

from typing import Any, Optional

import pandas as pd


def adjust_nav_for_dividends(
    nav_series: pd.Series,
    dividends: list[dict],
) -> pd.Series:
    """配息還原 NAV 序列(累積放大 ex-date 之前的 NAV)。

    Parameters
    ----------
    nav_series : pd.Series
        DatetimeIndex,values = NAV(>0)。
    dividends : list[dict]
        [{"date": "YYYY-MM-DD" 或 datetime, "amount": float >0}, ...]
        ex-date 順序不重要,演算法內部排序。

    Returns
    -------
    pd.Series
        Adjusted NAV(同 index,values 放大)。保留原 series 的 attrs(provenance)。
        空 series / 空 divs → 回原序列(不複製,但 attrs 保留)。

    Raises
    ------
    ValueError:dividends 格式錯(缺 date/amount key,或 date 不可 parse)。

    Notes
    -----
    - §1 Fail Loud:nav_before <= 0 / dividend amount <= 0 → skip + print warning,
      **不**偽造修正(避免 divisor 異常)
    - 演算法時間複雜度 O(N × D),N=NAV 長度,D=配息筆數(通常 D <= 24)
    """
    if nav_series is None or nav_series.empty:
        return nav_series
    if not dividends:
        return nav_series

    # 正規化 dividends 為 [(Timestamp, float)] 並按 ex-date 升序
    norm_divs: list[tuple[pd.Timestamp, float]] = []
    for d in dividends:
        if not isinstance(d, dict):
            raise ValueError(f"adjust_nav_for_dividends: dividend 必須為 dict,實際 {type(d).__name__}")
        if "date" not in d or "amount" not in d:
            raise ValueError(f"adjust_nav_for_dividends: dividend 缺 date/amount key:{d}")
        try:
            ex_date = pd.to_datetime(d["date"])
        except Exception as e:
            raise ValueError(f"adjust_nav_for_dividends: date 無法 parse {d['date']!r}: {e}") from e
        try:
            amt = float(d["amount"])
        except (TypeError, ValueError) as e:
            raise ValueError(f"adjust_nav_for_dividends: amount 無法轉 float {d['amount']!r}: {e}") from e
        if amt <= 0:
            # §1 Fail Loud:0 / 負配息 skip + log,**不**偽造
            print(f"[adjust_nav] skip 非正配息: {ex_date.date()} amount={amt}")
            continue
        norm_divs.append((ex_date, amt))

    if not norm_divs:
        return nav_series

    norm_divs.sort(key=lambda x: x[0])  # 升序

    # 從原 series 出發,逐筆配息放大 ex-date 之前的 values
    # 複製 series(避免 mutate caller 的 nav),保留 attrs
    adj = nav_series.copy()
    adj.attrs = dict(nav_series.attrs)  # explicit copy(避免 copy() 漏 attrs)

    for ex_date, amt in norm_divs:
        # 找 ex-date 前一筆 NAV(嚴格 <,不含 ex_date 當日)
        before_mask = adj.index < ex_date
        if not before_mask.any():
            print(f"[adjust_nav] skip ex_date {ex_date.date()}:NAV 範圍內無前筆")
            continue
        nav_before = float(adj.loc[before_mask].iloc[-1])
        if nav_before <= 0:
            print(f"[adjust_nav] skip ex_date {ex_date.date()}:nav_before={nav_before} <= 0")
            continue
        factor = (nav_before + amt) / nav_before
        # 放大 ex-date 之前所有(boolean indexing)
        adj.loc[before_mask] = adj.loc[before_mask] * factor

    return adj


def is_nav_likely_dividend_adjusted(
    nav_series: pd.Series,
    dividends: list[dict],
    drop_threshold_pct: float = 1.5,
) -> bool:
    """heuristic:判斷 NAV 序列是否「看起來已配息還原」。

    用於警告 caller 不要對已還原序列重複還原(double-adjust)。

    判斷:對每個配息 ex-date,若該日相對前一日的 pct change 跌幅 > threshold,
    視為**未還原**(因配息會造成 NAV 跳空下跌)。所有 ex-date 都未現跌空 → 視為
    已還原或配息影響極小。

    Parameters
    ----------
    nav_series : pd.Series
    dividends : list[dict]
    drop_threshold_pct : float
        ex-date NAV 跌幅閾值(%),預設 1.5%。配息率高於此值通常會在 NAV 看到跳空。

    Returns
    -------
    bool
        True = 看起來已還原(NAV 在 ex-date 沒有預期跳空)
        False = 看起來未還原(NAV 在 ex-date 有跳空,符合原始序列特徵)
    """
    if nav_series is None or nav_series.empty or not dividends:
        return False

    pct_change = nav_series.pct_change()
    drop_threshold = -drop_threshold_pct / 100.0

    any_drop_at_ex_date = False
    for d in dividends:
        try:
            ex_date = pd.to_datetime(d["date"])
        except (KeyError, ValueError):
            continue
        # 找 ex_date 當日或最近後一日
        on_or_after = nav_series.index >= ex_date
        if not on_or_after.any():
            continue
        ex_idx = nav_series.index[on_or_after][0]
        change = pct_change.loc[ex_idx]
        if pd.notna(change) and change < drop_threshold:
            any_drop_at_ex_date = True
            break

    # 有任何 ex-date 看到跌空 → 未還原(回 False)
    # 完全沒跌空 → 可能已還原(回 True)
    return not any_drop_at_ex_date
