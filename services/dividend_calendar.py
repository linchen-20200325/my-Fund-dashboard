"""services/dividend_calendar.py — 基金除息/配息行事曆推估(v19.443)。L2 純函式,零 IO。

用途:吃每檔基金的**配息歷史**,推估「本月除息日 + 配息入帳日」,產生月曆結構供 L3 渲染。
資料由 L1 抓好傳入(reuse `repositories.fund` 的 dividends);本層不碰網路、不 import streamlit。

§7 推估方法(誠實:是**推估**,非官方公告 —— 月配基金節奏穩才可靠,輸出帶 confidence)：
  1. 判頻率  : 相鄰除息日間隔中位數 → 月配(≈30)/季配(≈90)/半年(≈182)/年配(≈365)/不規則。
  2. 推除息日: 月配 → 近 N 筆除息日「幾號」中位數 = 每月固定除息日 → 套目標月(超月底取月底)。
              季/年配 → 從上次除息 + 週期往後推,剛好落在目標月才列,否則本月不顯示。
  3. 推入帳日: 除息日 + 歷史「除息→發放」間隔中位數(缺 pay_date → None,不硬編)。
  4. confidence: 筆數 + 「幾號」離散度(std)。少筆/離散大 → low(§1 不硬給精準日)。

§1 Fail-Loud:無配息紀錄(累積型/查無)→ cadence="none" → caller 落「已排除」,不偽造日期;
             欄位缺 ex_date → 退 date;pay_date 缺 → 入帳日 None(標「約」窗或留白,不捏造)。
"""
from __future__ import annotations

import calendar as _calendar
import datetime as _dt
import statistics as _stats
from typing import Any

# 頻率判定的間隔(天)容忍窗
_CADENCE_BANDS = [
    ("monthly", 20, 40),
    ("quarterly", 75, 105),
    ("semiannual", 160, 200),
    ("annual", 320, 400),
]
_RECENT_N = 12          # 推「幾號」與離散度只看近 12 筆(近期節奏最相關)


def _pdate(v: Any) -> "_dt.date | None":
    """'YYYY-MM-DD' / 'YYYY/MM/DD' → date;壞值 → None(§1 不猜)。"""
    s = str(v or "").strip()[:10].replace("/", "-")
    try:
        y, m, d = (int(x) for x in s.split("-"))
        return _dt.date(y, m, d)
    except (ValueError, TypeError):
        return None


def _pfloat(v: Any) -> "float | None":
    try:
        f = float(v)
        return f if f == f else None      # NaN → None
    except (TypeError, ValueError):
        return None


def _parse_records(dividends: list) -> list:
    """配息紀錄 → [{ex, pay, amount, yield_pct}](ex 升冪、同除息日去重 keep-last)。

    容錯:優先 ex_date、退 date;pay_date 缺 → None。ex 解析不出 → 丟該筆(§1 不猜)。
    """
    out: list = []
    for r in dividends or []:
        if not isinstance(r, dict):
            continue
        ex = _pdate(r.get("ex_date") or r.get("date"))
        if ex is None:
            continue
        pay = _pdate(r.get("pay_date"))
        out.append({"ex": ex, "pay": pay,
                    "amount": _pfloat(r.get("amount")),
                    "yield_pct": _pfloat(r.get("yield_pct"))})
    dedup: dict = {}
    for r in out:                          # 同除息日 keep-last
        dedup[r["ex"]] = r
    return [dedup[k] for k in sorted(dedup)]


def _cadence_from_gap(med_gap: "float | None") -> str:
    if med_gap is None:
        return "single"
    for name, lo, hi in _CADENCE_BANDS:
        if lo <= med_gap <= hi:
            return name
    return "irregular"


def _cadence_days(cadence: str) -> "int | None":
    return {"monthly": 30, "quarterly": 91, "semiannual": 182, "annual": 365}.get(cadence)


def infer_schedule(dividends: list) -> dict:
    """配息史 → 節奏推估 dict。

    Returns:
        {cadence, ex_day, pay_gap_days, n, confidence, day_std,
         last_ex, last_amount, last_yield, med_gap}
        cadence ∈ {none, single, monthly, quarterly, semiannual, annual, irregular}
        confidence ∈ {none, low, medium, high}
    """
    recs = _parse_records(dividends)
    n = len(recs)
    if n == 0:
        return {"cadence": "none", "ex_day": None, "pay_gap_days": None, "n": 0,
                "confidence": "none", "day_std": None, "last_ex": None,
                "last_amount": None, "last_yield": None, "med_gap": None}

    gaps = [(recs[i]["ex"] - recs[i - 1]["ex"]).days for i in range(1, n)]
    med_gap = _stats.median(gaps) if gaps else None
    cadence = _cadence_from_gap(med_gap)

    recent = recs[-_RECENT_N:]
    days = [r["ex"].day for r in recent]
    ex_day = round(_stats.median(days)) if days else None
    day_std = _stats.pstdev(days) if len(days) > 1 else 0.0

    pay_gaps = [(r["pay"] - r["ex"]).days for r in recs
                if r["pay"] is not None and (r["pay"] - r["ex"]).days >= 0]
    pay_gap = round(_stats.median(pay_gaps)) if pay_gaps else None

    # confidence:月配 + 夠筆數 + 「幾號」穩 → high;已知頻率 + ≥3 筆 → medium;其餘 low
    if cadence == "monthly" and n >= 6 and day_std is not None and day_std <= 4:
        conf = "high"
    elif cadence in ("monthly", "quarterly", "semiannual", "annual") and n >= 3:
        conf = "medium"
    else:
        conf = "low"

    last = recs[-1]
    return {"cadence": cadence, "ex_day": ex_day, "pay_gap_days": pay_gap, "n": n,
            "confidence": conf, "day_std": day_std, "last_ex": last["ex"],
            "last_amount": last["amount"], "last_yield": last["yield_pct"],
            "med_gap": med_gap}


def predict_ex_for_month(schedule: dict, year: int, month: int) -> "dict | None":
    """節奏 dict + 目標年月 → {ex_date, pay_date_est, confidence} 或 None(本月不配息)。

    月配:目標月的固定除息日(超月底取月底)。季/年配:上次除息 + 週期恰落本月才回,否則 None。
    single/irregular/none → None(§1:節奏不明就不猜本月日期)。
    """
    cad = schedule.get("cadence")
    conf = schedule.get("confidence", "low")

    def _mk(ex: _dt.date) -> dict:
        gap = schedule.get("pay_gap_days")
        pay = ex + _dt.timedelta(days=gap) if isinstance(gap, int) else None
        return {"ex_date": ex, "pay_date_est": pay, "confidence": conf}

    if cad == "monthly" and schedule.get("ex_day"):
        day = min(int(schedule["ex_day"]), _calendar.monthrange(year, month)[1])
        return _mk(_dt.date(year, month, day))

    if cad in ("quarterly", "semiannual", "annual"):
        last_ex = schedule.get("last_ex")
        step = _cadence_days(cad)
        if last_ex is None or step is None:
            return None
        # 從上次除息往後推,找是否有一次落在目標月(±半個週期容忍拉到該月)
        cur = last_ex
        for _ in range(24):                # 上限保護:最多推 24 個週期
            if cur.year == year and cur.month == month:
                return _mk(cur)
            if (cur.year, cur.month) > (year, month):
                break
            cur = cur + _dt.timedelta(days=step)
        return None

    return None


def build_month_calendar(funds: list, year: int, month: int) -> dict:
    """多檔基金(含 dividends)+ 目標年月 → 月曆結構。

    Args:
        funds: [{"code", "name", "house"(選填), "dividends": [...]}]
    Returns:
        {year, month, events[], by_day{day:[events]}, excluded[], counts{}}
        event = {code, name, house, ex_date, pay_date_est, confidence,
                 last_amount, last_yield, n}
        excluded = {code, name, reason}(無配息 = 累積型/查無)
    """
    events: list = []
    excluded: list = []
    for f in funds:
        code = str((f or {}).get("code") or "").strip()
        name = str((f or {}).get("name") or code)
        house = str((f or {}).get("house") or "")
        sch = infer_schedule((f or {}).get("dividends"))
        if sch["cadence"] == "none":
            excluded.append({"code": code, "name": name,
                             "reason": "無配息紀錄（累積型 / 查無配息）"})
            continue
        pred = predict_ex_for_month(sch, year, month)
        if pred is None:
            continue                       # 本月不配息(季/年配的空月)→ 不列也不算排除
        events.append({"code": code, "name": name, "house": house,
                       "ex_date": pred["ex_date"], "pay_date_est": pred["pay_date_est"],
                       "confidence": pred["confidence"], "last_amount": sch["last_amount"],
                       "last_yield": sch["last_yield"], "n": sch["n"]})

    events.sort(key=lambda e: (e["ex_date"], e["code"]))
    by_day: dict = {}
    for e in events:
        by_day.setdefault(e["ex_date"].day, []).append(e)
    return {"year": year, "month": month, "events": events, "by_day": by_day,
            "excluded": excluded,
            "counts": {"events": len(events), "excluded": len(excluded)}}


__all__ = ["infer_schedule", "predict_ex_for_month", "build_month_calendar"]
