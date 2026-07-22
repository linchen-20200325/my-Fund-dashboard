"""ui/helpers/nav_history_hook.py — v19.359 Track 2 UI 掛鉤(L3→L2)

把 App 成功抓到的當日 NAV append 進 Google Sheet nav_history(services.nav_history_gs)。
L3 只負責:(1) 從 fund dict 抽 SSOT 的 (code, date, nav)、(2) session 去重防每次 rerun 重寫、
(3) catch 錯誤顯示**非致命**提示;真正寫 sheet 由 L2 services.nav_history_gs 負責(§8.2)。

SSOT 取值原則(§4.1 避免量綱錯位):nav 與 date 一律取「**同一條 series 的最後一點**」,
不混用 metrics['nav'](series 末)與 nav_latest(wb01 scrape)—— 兩者可能不同日 → 錯位。
series 缺時才退 metrics['nav'] + nav_date,並照樣走 §1(不足回 None,不偽造)。
"""
from __future__ import annotations

from typing import Any


def _extract_point(fd: Any, code_hint: str | None = None) -> dict | None:
    """從 fund dict 抽 SSOT 的 (code, nav, date)。抽不到回 None(§1 不偽造)。"""
    if not isinstance(fd, dict):
        return None
    code = str(code_hint or fd.get("full_key") or fd.get("code") or "").strip().upper()
    if not code:
        return None

    nav = None
    date = ""
    series = fd.get("series")
    try:
        if series is not None and len(series) > 0:
            nav = float(series.iloc[-1])
            date = str(series.index[-1])[:10]
    except Exception:
        nav, date = None, ""

    if nav is None or not date:  # fallback:metrics['nav'] + nav_date
        try:
            nav = float((fd.get("metrics") or {}).get("nav"))
        except (TypeError, ValueError):
            nav = None
        date = str(fd.get("nav_date") or "")[:10]

    if nav is None or nav <= 0 or not date:
        return None
    return {"code": code, "nav": nav, "nav_date": date,
            "fund_name": str(fd.get("fund_name") or "")}


def record_fund_nav_point(fd: Any, source: str = "app", code: str | None = None) -> None:
    """Tab2 單檔:抓成功後記一筆。"""
    _record([(code, fd)], source)


def record_batch_nav_points(pairs: list, source: str = "app") -> None:
    """健診批次:一次記多檔。pairs = [(code, fd), ...]。"""
    _record(pairs, source)


def _record(pairs: list, source: str) -> None:
    """共用:抽點 → session 去重 → L2 批次寫 → 非致命提示。"""
    import streamlit as st

    pts: list[dict] = []
    for code, fd in pairs:
        p = _extract_point(fd, code)
        if p:
            p["source"] = source
            pts.append(p)
    if not pts:
        return

    written = st.session_state.setdefault("_nav_hist_written", set())
    fresh = [p for p in pts if (p["code"], p["nav_date"]) not in written]
    if not fresh:
        return

    try:
        from services.nav_history_gs import append_points, is_enabled
        if not is_enabled():
            return  # 無 GS secrets(local):安靜略過,不干擾
        res = append_points(fresh)
        for p in fresh:  # 標記 session,避免同 session 反覆 rerun 重寫
            written.add((p["code"], p["nav_date"]))
        if res.get("written"):
            st.caption(f"🗂️ NAV 累積:本次新存 {res['written']} 筆到 nav_history 分頁")
    except Exception as e:  # NavHistoryError 等 — 可見但非致命,不擋渲染
        st.caption(f"⬜ NAV 累積寫入失敗(不影響分析):[{type(e).__name__}] {str(e)[:80]}")


__all__ = ["record_fund_nav_point", "record_batch_nav_points", "_extract_point"]
