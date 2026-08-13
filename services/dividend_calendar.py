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
    day_std = _stats.pstdev(days) if len(days) > 1 else 0.0
    # 稽核 M2:跨月邊界(如除息日在 31 與 1 之間游移)時中位數會給「幻影中間日」(31,1→16)。
    # 離散大 → 改用最近一次實際除息日(較可信),並降信心,不送幻影日。
    if days and day_std > 8:
        ex_day = recs[-1]["ex"].day
    else:
        ex_day = round(_stats.median(days)) if days else None

    pay_gaps = [(r["pay"] - r["ex"]).days for r in recs
                if r["pay"] is not None and (r["pay"] - r["ex"]).days >= 0]
    pay_gap = round(_stats.median(pay_gaps)) if pay_gaps else None

    # confidence:「幾號」離散大 → low;月配 + 夠筆數 + 穩 → high;已知頻率 + ≥3 筆 → medium;其餘 low
    if day_std is not None and day_std > 8:
        conf = "low"
    elif cadence == "monthly" and n >= 6 and day_std <= 4:
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


_CADENCE_MONTHS = {"monthly": 1, "quarterly": 3, "semiannual": 6, "annual": 12}


def predict_ex_for_month(schedule: dict, year: int, month: int) -> "dict | None":
    """節奏 dict + 目標年月 → {ex_date, pay_date_est, confidence} 或 None(本月不配息/無法推估)。

    稽核 M1/H3 修:一律以**日曆月**逐週期推進(不再加固定 91 天,避免月底漂移錯月),並查**陳舊度**:
      - last_ex 距目標 > 3 個週期(疑停配/資料過舊)→ None(§1 不硬給高信心假日期)
      - 2~3 個週期 → 降信心 low
    除息日一律用 schedule['ex_day'](幾號)套目標月、超月底夾擠。single/irregular/none → None(不猜)。
    """
    cad = schedule.get("cadence")
    ex_day = schedule.get("ex_day")
    last_ex = schedule.get("last_ex")
    step = _CADENCE_MONTHS.get(cad)
    if step is None or ex_day is None or last_ex is None:
        return None

    cy, cm, periods = last_ex.year, last_ex.month, 0
    for _ in range(240):                     # 上限保護(240 月 = 20 年)
        if (cy, cm) == (year, month):
            if periods > 3:
                return None                  # 太久沒配 → 疑停配/資料過舊,不硬給(§1)
            _conf = "low" if periods >= 2 else schedule.get("confidence", "low")
            day = min(int(ex_day), _calendar.monthrange(year, month)[1])
            ex = _dt.date(year, month, day)
            gap = schedule.get("pay_gap_days")
            pay = ex + _dt.timedelta(days=gap) if isinstance(gap, int) else None
            return {"ex_date": ex, "pay_date_est": pay, "confidence": _conf}
        if (cy, cm) > (year, month):
            return None                      # 越過目標月(季/年配空月,或 last_ex 在目標之後)
        cm += step
        periods += 1
        while cm > 12:
            cm -= 12
            cy += 1
    return None


def build_month_calendar(funds: list, year: int, month: int) -> dict:
    """多檔基金(含 dividends)+ 目標年月 → 月曆結構。

    Args:
        funds: [{"code", "name", "house"(選填), "dividends": [...]}]
    Returns:
        {year, month, events[], by_day{day:[events]}, excluded[], unpredictable[], counts{}}
        event = {code, name, house, ex_date, pay_date_est, confidence, last_amount, last_yield, n}
        excluded     = {code, name, reason}(無配息 = 累積型/查無)
        unpredictable= {code, name, reason}(有配息史但本月無法推估:節奏不規則 / 疑停配過舊)
                       —— 稽核 M3:誠實揭露而非靜默消失。季/年配的「空月」不列此(合理不配)。
    """
    events: list = []
    excluded: list = []
    unpredictable: list = []
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
            if sch["cadence"] == "monthly":          # 月配卻推不出 = 陳舊/疑停配
                unpredictable.append({"code": code, "name": name,
                                      "reason": "最近無配息紀錄（疑停配 / 資料過舊），本月無法推估"})
            elif sch["cadence"] in ("single", "irregular"):
                unpredictable.append({"code": code, "name": name,
                                      "reason": "配息節奏不規則 / 資料不足，本月無法推估"})
            # 季/年配的空月 → 合理不配,不列也不算異常
            continue
        events.append({"code": code, "name": name, "house": house,
                       "ex_date": pred["ex_date"], "pay_date_est": pred["pay_date_est"],
                       "confidence": pred["confidence"], "last_amount": sch["last_amount"],
                       "last_yield": sch["last_yield"], "n": sch["n"]})

    events.sort(key=lambda e: (e["ex_date"], e["code"]))
    by_day: dict = {}
    for e in events:
        by_day.setdefault(e["ex_date"].day, []).append(e)
    return {"year": year, "month": month, "events": events, "by_day": by_day,
            "excluded": excluded, "unpredictable": unpredictable,
            "counts": {"events": len(events), "excluded": len(excluded),
                       "unpredictable": len(unpredictable)}}


# ── 基金公司偵測(從基金名關鍵字;供月曆分色/分組)──────────────────
_HOUSE_MAP = [
    (("聯博", "alliancebernstein"), "聯博"),
    (("安聯", "allianz"), "安聯"),
    (("摩根", "jpmorgan", "jpm", "jf "), "摩根"),
    (("施羅德", "schroder"), "施羅德"),
    (("瀚亞", "eastspring"), "瀚亞"),
    (("富蘭克林", "franklin", "坦伯頓", "templeton"), "富蘭克林"),
    (("貝萊德", "blackrock"), "貝萊德"),
    (("高盛", "goldman"), "高盛"),
    (("pimco", "品浩"), "PIMCO"),
    (("野村", "nomura"), "野村"),
    (("景順", "invesco"), "景順"),
    (("富達", "fidelity"), "富達"),
    (("法巴", "bnp"), "法巴"),
    (("m&g", "安聯m&g"), "M&G"),
    (("復華", "fh"), "復華"),
    (("國泰", "cathay"), "國泰"),
    (("群益",), "群益"),
]


def detect_house(name: str) -> str:
    """從基金名關鍵字判斷所屬投信/投顧;判不出 → ''(caller 顯示代號即可,§1 不亂猜)。"""
    _n = str(name or "").lower()
    for keys, house in _HOUSE_MAP:
        if any(k in _n for k in keys):
            return house
    return ""


# ── LINE 月初摘要文字(方式 C;純字串,零 IO)──────────────────
_CONF_ZH = {"high": "", "medium": "", "low": "（信心低）"}


def build_summary_text(cal: dict) -> str:
    """月曆結構 → LINE 月初提醒文字。無事件 → 誠實說本月無推估除息(§1)。"""
    y, m = cal.get("year"), cal.get("month")
    _roc = (y - 1911) if isinstance(y, int) else "?"
    lines = [f"🗓️ 基金除息行事曆 · 民國{_roc}年{m}月（推估）"]
    events = cal.get("events") or []
    if not events:
        lines.append("本月你的基金無推估除息日（或資料不足）。")
    else:
        for e in events:
            _ex = e["ex_date"]
            _tag = _CONF_ZH.get(e.get("confidence"), "")
            _house = f"{e.get('house')} " if e.get("house") else ""
            lines.append(f"• {_ex.month}/{_ex.day} {_house}{e.get('code')} 除息{_tag}")
    _exc = cal.get("excluded") or []
    _unp = cal.get("unpredictable") or []
    if _exc:
        lines.append(f"（{len(_exc)} 檔累積型/無配息未列）")
    if _unp:
        lines.append(f"（{len(_unp)} 檔節奏不規則/疑停配,無法推估）")
    lines.append("※ 推估非官方,實際以基金公司公告為準。")
    return "\n".join(lines)


__all__ = ["infer_schedule", "predict_ex_for_month", "build_month_calendar",
           "detect_house", "build_summary_text"]
