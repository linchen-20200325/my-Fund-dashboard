"""services/capture_ratio.py — 上檔/下檔捕捉率 + 經理人操作評分(v19.414)。

衡量基金經理人操作能力:基金 NAV 與大盤(基準)按**月**對齊,分成「大盤上漲月」與
「大盤下跌月」兩組複利:
- **上檔捕捉%** = 大盤上漲月裡 基金複利報酬 / 大盤複利報酬 × 100(**越高越好**:追得上漲)
- **下檔捕捉%** = 大盤下跌月裡 基金複利報酬 / 大盤複利報酬 × 100(**越低越好**:抗得住跌)
- **操盤評分** = clamp(50 + (上檔 − 下檔) / 2, 0, 100)
  例:大盤−50/基金−10(下檔20)+ 追漲(上檔100)→ 90 分;下檔120(比大盤慘)→ 40 分。

§7:基準依幣別 —— TWD → 台股(TWII);其餘(USD/EUR/…)→ S&P500(SPX)。
§1:大盤上漲月 / 下跌月數任一 < min_months → None(不給假精確);計算異常 → None。
§4.5:月底 resample(closed/label 右閉,不引未來)後對齊共同月;§4.6 短歷史誠實 None。
純函式,零 IO(基準序列由呼叫端傳入)。
"""
from __future__ import annotations

import sys

import pandas as pd

_BLANK: dict = {"upside": None, "downside": None, "score": None, "n_up": 0, "n_down": 0}


def benchmark_for_currency(ccy: str) -> str:
    """依計價幣別選大盤基準:TWD → TWII(台股);其餘 → SPX(S&P500)。"""
    c = (ccy or "").strip().upper()
    if c in ("TWD", "NTD", "TW", "台幣", "新台幣"):
        return "TWII"
    return "SPX"


def _monthly_returns(nav) -> "pd.Series | None":
    """NAV 序列 → 月底 resample → 月報酬(DatetimeIndex,升冪)。

    有效性交給 compute_capture 的 n_up/n_down >= min_months 把關(短歷史 → 月數不足 → None),
    此處只做 DatetimeIndex 正規化 + resample;<2 筆月報酬直接 None。
    """
    s = pd.Series(nav).dropna()
    if len(s) < 3:
        return None
    s.index = pd.to_datetime(s.index, errors="coerce")
    s = s[s.index.notna()].sort_index()
    if s.empty:
        return None
    # F-CAP-2:**不**在 pct_change 前 dropna —— 缺月(停售/新基金)→ resample 產 NaN →
    # 跨缺口報酬變 NaN → 一併 dropna 丟掉「橫跨缺月的假單月報酬」(§1 不 ffill 偽造)。
    r = s.resample("ME").last().pct_change().dropna()
    return r if len(r) >= 2 else None


def compute_capture(fund_nav, benchmark_nav, min_months: int = 6) -> dict:
    """基金 NAV vs 基準 NAV → {upside, downside, score, n_up, n_down}。

    大盤上漲月 / 下跌月分組複利;任一組月數 < min_months → 三值 None(§1 不假精確)。
    """
    if fund_nav is None or benchmark_nav is None:
        return dict(_BLANK)
    try:
        rf = _monthly_returns(fund_nav)
        rb = _monthly_returns(benchmark_nav)
        if rf is None or rb is None:
            return dict(_BLANK)
        idx = rf.index.intersection(rb.index)
        rf = rf.loc[idx]
        rb = rb.loc[idx]
        up = rb > 0
        down = rb < 0
        n_up, n_down = int(up.sum()), int(down.sum())
        if n_up < min_months or n_down < min_months:
            return {**_BLANK, "n_up": n_up, "n_down": n_down}

        up_b = float((1 + rb[up]).prod() - 1)     # 大盤上漲月複利(> 0)
        up_f = float((1 + rf[up]).prod() - 1)     # 基金於同月複利
        dn_b = float((1 + rb[down]).prod() - 1)   # 大盤下跌月複利(< 0)
        dn_f = float((1 + rf[down]).prod() - 1)   # 基金於同月複利

        # F-CAP-3:先 round 捕捉率,評分再從「顯示值」算 → 使用者拿表上數字重算不會差 1。
        uc = round(up_f / up_b * 100.0, 1) if up_b > 0 else None
        dc = round(dn_f / dn_b * 100.0, 1) if dn_b < 0 else None   # 兩負相除 → 正
        score = None
        if uc is not None and dc is not None:
            score = round(max(0.0, min(100.0, 50.0 + (uc - dc) / 2.0)))

        return {"upside": uc, "downside": dc, "score": score,
                "n_up": n_up, "n_down": n_down}
    except Exception as e:  # noqa: BLE001 — 計算異常 → 誠實 None,不假精確(§1)
        print(f"[capture_ratio] 計算失敗: {type(e).__name__}: {e}", file=sys.stderr)
        return dict(_BLANK)
