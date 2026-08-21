"""services/capture_ratio.py — 上檔/下檔捕捉率 + 經理人操作評分(v19.414)。

衡量基金經理人操作能力:基金 NAV 與大盤(基準)按**月**對齊,分成「大盤上漲月」與
「大盤下跌月」兩組複利:
- **上檔捕捉%** = 大盤上漲月裡 基金複利報酬 / 大盤複利報酬 × 100(**越高越好**:追得上漲)
- **下檔捕捉%** = 大盤下跌月裡 基金複利報酬 / 大盤複利報酬 × 100(**越低越好**:抗得住跌)
- **操盤評分** = clamp(50 + (上檔 − 下檔) / 2, 0, 100)
  例:大盤−50/基金−10(下檔20)+ 追漲(上檔100)→ 90 分;下檔120(比大盤慘)→ 40 分。

§7 / §4.1:基準依幣別 —— TWD → 台股(TWII);USD → S&P500(SPX);
**其餘幣別(EUR/AUD/ZAR/CNH/JPY…)→ None(留白,不比)**。基金 NAV 是**原幣**,
S&P 500 是 USD 計價,直接相減等於把匯率變動算成經理人績效(2026-08-06 稽核 必修 7)。
§1:大盤上漲月 / 下跌月數任一 < min_months → None(不給假精確);計算異常 → None。
§4.5:月底 resample(closed/label 右閉,不引未來)後對齊共同月;§4.6 短歷史誠實 None。
純函式,零 IO(基準序列由呼叫端傳入)。
"""
from __future__ import annotations

import sys

import pandas as pd

from shared.signal_thresholds import (
    CAPTURE_MIN_MONTHS,
    CAPTURE_ROBUST_MONTHS,
    CAPTURE_SCORE_BASE,
)

_BLANK: dict = {"upside": None, "downside": None, "score": None,
                "n_up": 0, "n_down": 0, "low_confidence": False}


_TWD_ALIASES = ("TWD", "NTD", "TW", "台幣", "新台幣")
_USD_ALIASES = ("USD", "美元", "美金")


def benchmark_for_currency(ccy: str) -> "str | None":
    """依計價幣別選大盤基準:TWD → TWII(台股);USD → SPX(S&P500);**其餘 → None**。

    §4.1 跨幣別:基金 NAV 是**原幣**,指數是自己的計價幣。EUR / AUD / ZAR / CNH / JPY
    計價的保單連結基金若對 SPX 比,等於把「歐元兌美元變動」算進經理人的操作能力 ——
    上/下檔捕捉率、操盤評分、vs 大盤% 全被匯率污染,再往下傳到換標策略分的
    「vs 大盤 15 分」,足以把一檔基金推過 🔴 賣出/平轉 的門檻。

    **處置選擇(必修 7)**:回 None 留白,而非「把 NAV 換算成 USD 再比」。理由 ——
    (a) 換算需要**每日**歷史匯率序列,本站目前只有 USDTWD 一條(`fx_regime`),
        EUR/AUD/ZAR/JPY 兌 USD 的日頻歷史沒有現成來源 → 硬做只能用即期匯率回推,
        那是把今天的匯率套到過去,屬 §2.3 lookahead;
    (b) 即使換到 USD,對「該不該續抱這檔歐元保單基金」而言,正確的基準也是
        歐股指數而非 S&P 500 —— 換幣別解決不了**基準選錯**的問題;
    (c) §1:寧可留白讓 user 知道沒證據,也不給一個把匯率當績效的數字。
    留白後 `switch_score` 會把 vs 大盤 15 分**退出分母**(不是計 0 分),
    並在「策略分覆蓋」欄標明,不會誤傷這些基金的評分。
    """
    c = (ccy or "").strip().upper()
    if c in _TWD_ALIASES:
        return "TWII"
    if c in _USD_ALIASES:
        return "SPX"
    return None


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
    r = s.resample("ME").last().pct_change(fill_method=None).dropna()  # §1 不補值:缺月→NaN→丟,不偽造 0%
    return r if len(r) >= 2 else None


def compute_capture(fund_nav, benchmark_nav, min_months: int = CAPTURE_MIN_MONTHS) -> dict:
    """基金 NAV vs 基準 NAV → {upside, downside, score, n_up, n_down, low_confidence}。

    大盤上漲月 / 下跌月分組複利;任一組月數 < min_months → 三值 None(§1 不假精確)。
    `low_confidence`=True 當有分數但漲/跌月任一 < CAPTURE_ROBUST_MONTHS(3–5 月樣本少較噪,
    v19.419 放寬門檻後誠實標記,供 UI 提示「參考值」)。
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
            score = round(max(0.0, min(100.0, CAPTURE_SCORE_BASE + (uc - dc) / 2.0)))

        _low_conf = (n_up < CAPTURE_ROBUST_MONTHS) or (n_down < CAPTURE_ROBUST_MONTHS)
        return {"upside": uc, "downside": dc, "score": score,
                "n_up": n_up, "n_down": n_down, "low_confidence": _low_conf}
    except Exception as e:  # noqa: BLE001 — 計算異常 → 誠實 None,不假精確(§1)
        print(f"[capture_ratio] 計算失敗: {type(e).__name__}: {e}", file=sys.stderr)
        return dict(_BLANK)
