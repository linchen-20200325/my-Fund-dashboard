"""v19.22 Tier A 事件日曆 — FOMC / NFP / CPI 倒數日

設計動機（v19.22 epic）：
慢總經（v19.x 23 指標）+ 短線雷達（v19.20 10 燈）皆缺「時間軸」維度 —
重要 macro 事件（FOMC 利率決議 / NFP 非農就業 / CPI 通膨）發布前後波動率
顯著放大，user 需要看見距下次事件還有幾天以做倉位調整。

3 個事件：
  1. FOMC — 硬編碼 Fed 公告 schedule（每年 8 場）
  2. NFP  — 每月第一個週五規則（BLS Employment Situation）
  3. CPI  — BLS 月中規則，約 10-15 號工作日（用 10 號 + 週末延後近似）

色階：
  ≤ 3 天 → 🔴 倒數（紅）
  ≤ 7 天 → 🟠 接近（橘）
  ≤14 天 → 🟡 留意（黃）
  其他   → 🟢 平靜（綠）

純函式，零外部 IO → 不踩 quota、不需 mock，AppTest 安全。
"""
from __future__ import annotations

from datetime import date, timedelta

from shared.colors import (
    TRAFFIC_GREEN as GREEN,
    TRAFFIC_NEUTRAL as GRAY,
    TRAFFIC_ORANGE as ORANGE,
    TRAFFIC_RED as RED,
    TRAFFIC_YELLOW as YELLOW,
)

EVENT_KEYS = ("FOMC", "NFP", "CPI")

# Fed 官網公告 + 預估時間表（每年底需 update 下年度）
_FOMC_2026 = (
    date(2026, 1, 28),
    date(2026, 3, 18),
    date(2026, 4, 29),
    date(2026, 6, 17),
    date(2026, 7, 29),
    date(2026, 9, 16),
    date(2026, 10, 28),
    date(2026, 12, 9),
)
_FOMC_2027 = (
    date(2027, 1, 27),
    date(2027, 3, 17),
    date(2027, 4, 28),
    date(2027, 6, 16),
    date(2027, 7, 28),
    date(2027, 9, 22),
    date(2027, 10, 27),
    date(2027, 12, 15),
)
_FOMC_DATES: tuple[date, ...] = _FOMC_2026 + _FOMC_2027


def _badge_for(days_until: int) -> tuple[str, str]:
    """色階純函式：天數 → (signal, color)。"""
    if days_until <= 3:
        return ("🔴 倒數", RED)
    if days_until <= 7:
        return ("🟠 接近", ORANGE)
    if days_until <= 14:
        return ("🟡 留意", YELLOW)
    return ("🟢 平靜", GREEN)


def _first_friday_of(year: int, month: int) -> date:
    """回該月第一個週五（NFP BLS 發布日規則）。"""
    d = date(year, month, 1)
    offset = (4 - d.weekday()) % 7  # Mon=0 .. Fri=4
    return d.replace(day=1 + offset)


def _adjust_workday(d: date) -> date:
    """週末延後到下個工作日。"""
    while d.weekday() >= 5:  # Sat=5, Sun=6
        d = d + timedelta(days=1)
    return d


def _next_month(year: int, month: int) -> tuple[int, int]:
    if month < 12:
        return (year, month + 1)
    return (year + 1, 1)


def next_fomc_date(today: date) -> date | None:
    """回 today 之後（含當天）的下一場 FOMC；日曆耗盡回 None。"""
    for d in _FOMC_DATES:
        if d >= today:
            return d
    return None


def next_nfp_date(today: date) -> date:
    """回下一個 NFP 發布日（每月第一個週五）。"""
    candidate = _first_friday_of(today.year, today.month)
    if candidate >= today:
        return candidate
    ny, nm = _next_month(today.year, today.month)
    return _first_friday_of(ny, nm)


def next_cpi_date(today: date) -> date:
    """回下一個 CPI 發布日（BLS 月中近似：10 號工作日）。"""
    candidate = _adjust_workday(date(today.year, today.month, 10))
    if candidate >= today:
        return candidate
    ny, nm = _next_month(today.year, today.month)
    return _adjust_workday(date(ny, nm, 10))


def event_payload(event: str, target: date | None, today: date) -> dict:
    """單一事件 payload — 倒數天數 + 色階 + 顯示文案。"""
    if target is None:
        return {
            "event": event,
            "date": None,
            "days_until": None,
            "signal": "⬜ 日曆未維護",
            "color": GRAY,
            "note": f"目前 {event} 日曆已用盡，請更新 services/event_calendar.py 常量",
        }
    days = (target - today).days
    sig, color = _badge_for(days)
    return {
        "event": event,
        "date": target,
        "days_until": days,
        "signal": sig,
        "color": color,
        "note": f"距下次 {event} 還有 {days} 天 ({target.isoformat()})",
    }


def detect_event_calendar(today: date | None = None) -> dict:
    """彙整 3 事件倒數 dict — 純函式無 IO。"""
    if today is None:
        today = date.today()
    return {
        "FOMC": event_payload("FOMC", next_fomc_date(today), today),
        "NFP": event_payload("NFP", next_nfp_date(today), today),
        "CPI": event_payload("CPI", next_cpi_date(today), today),
    }


def summarize_calendar(payload: dict) -> dict:
    """聚合最緊迫事件給 UI 頂部 banner。"""
    pending = [p for p in payload.values() if p.get("days_until") is not None]
    if not pending:
        return {"level": "日曆未維護", "color": GRAY, "min_days": None, "nearest": None}
    nearest = min(pending, key=lambda p: p["days_until"])
    return {
        "level": nearest["signal"],
        "color": nearest["color"],
        "min_days": nearest["days_until"],
        "nearest": nearest["event"],
    }
