"""services/benchmark_compare.py — 基金 vs 大盤(基準)比較(v19.420)。

user 要「與大盤的比較」。兩個產物,皆**純價格對純價格**(基金 NAV 不含息 vs 指數不含息,
公平;user 2026-07-28 拍板),窗口**近 1 年**(日曆日 asof,不足 1 年 → 全期並標記):

- `excess_return`:vs 大盤% = 基金近1Y純價格報酬 − 大盤近1Y純價格報酬(百分點)。→ 健診/批次大表一欄。
- `rebased_pair`:兩序列在窗口起點重設 = 100 的對齊 DataFrame。→ Tab2 單一基金疊圖。

§1:缺料 / 序列太短 / 無共同期間 → None(不假精確)。§4.5:asof 對齊不規則 NAV,週末缺值不 ffill。
純函式,零 IO(基準序列由呼叫端傳入)。基準選擇(TWD→TWII / 其餘→SPX)見 services.capture_ratio。
"""
from __future__ import annotations

import pandas as pd

from shared.signal_thresholds import BENCHMARK_WINDOW_DAYS

_BLANK: dict = {"excess_pct": None, "fund_pct": None, "bench_pct": None, "full_period": False}


def _prep(nav) -> "pd.Series | None":
    """任意 NAV 序列 → 乾淨升冪 Series(tz-naive DatetimeIndex, 唯一, >0);<2 點 → None。

    §4.5:基金 NAV(TW UTC+8)可能 tz-aware、指數(Yahoo)tz-naive → 統一剝 tz 成 naive
    (否則 max()/min() 比較 tz-aware 與 naive 會 TypeError)。重複日期取最後(避免任意基準)。
    """
    if nav is None:
        return None
    s = pd.Series(nav).dropna()
    if len(s) < 2:
        return None
    idx = pd.to_datetime(s.index, errors="coerce")
    s = s[idx.notna()]
    idx = idx[idx.notna()]
    if getattr(idx, "tz", None) is not None:        # tz-aware → naive(wall-clock),跨源可比
        idx = idx.tz_localize(None)
    s.index = idx
    s = s.sort_index()
    s = s[~s.index.duplicated(keep="last")]         # 重複日期 → 取最後一筆
    s = s[s > 0]                                     # NAV 鐵則(§3.2);排除 0/負
    return s if len(s) >= 2 else None


def _common_window(f: "pd.Series", b: "pd.Series", days: int):
    """**共同交易日**(intersection)+ 近 `days` 窗口。回 (win_dates, full_period) 或 None。

    關鍵(F-BM-1 修):以兩序列**共同日期**為錨,兩邊在同一組日期量報酬 → 公平;
    不再各自 forward-slice(grid 不同時會製造假超額)。共同日 <2 → None。
    """
    common = f.index.intersection(b.index)
    if len(common) < 2:
        return None
    end = common[-1]
    overall_start = common[0]
    _asked = end - pd.Timedelta(days=days)
    full_period = _asked < overall_start            # 共同歷史不足 1 年 → 用全期並標記
    win_start = overall_start if full_period else _asked
    win = common[(common >= win_start) & (common <= end)]
    if len(win) < 2:
        return None
    return win, full_period


def excess_return(fund_nav, benchmark_nav, days: int = BENCHMARK_WINDOW_DAYS) -> dict:
    """{excess_pct, fund_pct, bench_pct, full_period}。

    excess_pct = (基金純價格報酬 − 大盤純價格報酬) × 100(百分點,正 = 跑贏)。
    兩者用**同一組共同交易日**的首/末點量報酬(近 `days` 窗口內)→ 公平、無 grid 錯配。
    excess_pct 由**已 round 的分量**相減 → 顯示對得起來(fund − bench = excess)。
    缺料 / 無共同期間 / 窗內共同日 <2 → 各值 None(§1)。
    """
    f = _prep(fund_nav)
    b = _prep(benchmark_nav)
    if f is None or b is None:
        return dict(_BLANK)
    _win = _common_window(f, b, days)
    if _win is None:
        return dict(_BLANK)
    win, full_period = _win
    d0, d1 = win[0], win[-1]                         # 同一組共同日期的首 / 末 → 公平
    fund_pct = round(float(f.loc[d1] / f.loc[d0] - 1.0) * 100.0, 1)
    bench_pct = round(float(b.loc[d1] / b.loc[d0] - 1.0) * 100.0, 1)
    return {
        "excess_pct": round(fund_pct - bench_pct, 1),   # 由分量相減 → 顯示一致
        "fund_pct": fund_pct,
        "bench_pct": bench_pct,
        "full_period": full_period,
    }


def rebased_pair(fund_nav, benchmark_nav, days: int = BENCHMARK_WINDOW_DAYS,
                 fund_label: str = "基金", bench_label: str = "大盤"):
    """回 DataFrame(index=日期, 兩欄=[基金, 大盤])—— 兩線在**共同錨日**重設 = 100,供疊圖。

    錨 = 窗內第一個共同交易日 → 兩線同起點 = 100(公平);各自畫完整 grid,outer join
    缺格留 NaN(line chart 斷點,**不 ffill 偽造**,§1)。缺料 / 窗內共同日 <2 → None。
    """
    f = _prep(fund_nav)
    b = _prep(benchmark_nav)
    if f is None or b is None:
        return None
    _win = _common_window(f, b, days)
    if _win is None:
        return None
    win, _ = _win
    anchor, end = win[0], win[-1]                    # 共同錨日 → 兩線同起點
    fseg = f[(f.index >= anchor) & (f.index <= end)]
    bseg = b[(b.index >= anchor) & (b.index <= end)]
    if len(fseg) < 2 or len(bseg) < 2:
        return None
    fr = fseg / float(f.loc[anchor]) * 100.0
    br = bseg / float(b.loc[anchor]) * 100.0
    return pd.DataFrame({fund_label: fr, bench_label: br})
