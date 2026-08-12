"""ui/helpers/nav_history_hook.py — v19.359 Track 2 UI 掛鉤(L3→L2)

把 App 成功抓到的**整段近期 NAV 序列**append 進 Google Sheet nav_history(services.nav_history_gs)。
v19.437:改存整段(每日一點,去重、都是來源真實資料),取代原本只存 series 末點單點 ——
一次抓回的近期序列(數十~上百交易日)立刻全部累積,序列馬上變長(非偽造,§1)。
L3 只負責:(1) 從 fund dict 抽 SSOT 的 (code, date, nav) 序列、(2) session 去重防每次 rerun 重寫、
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


def _extract_points(fd: Any, code_hint: str | None = None) -> list[dict]:
    """v19.437:抽 fund dict 裡「**整段**」NAV 序列(每日一點,去重交給下游 append_points)。

    取代原本只存 `series.iloc[-1]` 單點 —— App/NAS 每次抓回的近期序列(數十~上百個交易日)
    本來就是**來源真實資料**,一次全部累積 → 序列立刻變長(非偽造,§1)。NaN / nav<=0 /
    壞日期的點顯式跳過(不猜)。series 缺 → 退單點 `_extract_point`(metrics+nav_date);
    都抽不到 → `[]`。回傳的點不帶 source(由 caller 標)。"""
    if not isinstance(fd, dict):
        return []
    code = str(code_hint or fd.get("full_key") or fd.get("code") or "").strip().upper()
    if not code:
        return []
    fund_name = str(fd.get("fund_name") or "")
    out: list[dict] = []
    series = fd.get("series")
    try:
        if series is not None and len(series) > 0:
            for _idx, _val in series.items():
                try:
                    nav = float(_val)
                except (TypeError, ValueError):
                    continue
                date = str(_idx)[:10]
                if nav > 0 and date:
                    out.append({"code": code, "nav": nav, "nav_date": date,
                                "fund_name": fund_name})
    except Exception:
        out = []
    if out:
        return out
    # series 缺 / 全無效 → 退單點(fallback 同 _extract_point:metrics['nav'] + nav_date)
    p = _extract_point(fd, code)
    return [p] if p else []


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
        for p in _extract_points(fd, code):   # v19.437:存整段序列(非只末點)
            p["source"] = source
            pts.append(p)
    if not pts:
        return

    written = st.session_state.setdefault("_nav_hist_written", set())
    fresh = [p for p in pts if (p["code"], p["nav_date"]) not in written]
    if not fresh:
        return

    try:
        from services.nav_history_gs import append_points, status as _nh_status
        _st = _nh_status()
        if not _st["enabled"]:
            # v19.362 ①:靜默失敗變可見 —— 一次性提示(session 旗標防洗版),
            # 終結「你以為在累積、其實沒有」(§5 可觀測)。
            if not st.session_state.get("_nav_hist_disabled_warned"):
                st.session_state["_nav_hist_disabled_warned"] = True
                st.caption(
                    f"⬜ NAV 累積未啟用:缺 secrets({', '.join(_st['missing'])})→ "
                    f"本次抓到的淨值不會累積。設定後自動恢復(詳見 Tab5 🗂️ NAV 歷史匯入)。")
            return
        res = append_points(fresh)
        for p in fresh:  # 標記 session,避免同 session 反覆 rerun 重寫
            written.add((p["code"], p["nav_date"]))
        if res.get("written"):
            st.caption(f"🗂️ NAV 累積:本次新存 {res['written']} 筆到 nav_history 分頁")
    except Exception as e:  # NavHistoryError 等 — 可見但非致命,不擋渲染
        st.caption(f"⬜ NAV 累積寫入失敗(不影響分析):[{type(e).__name__}] {str(e)[:80]}")


__all__ = ["record_fund_nav_point", "record_batch_nav_points",
           "_extract_point", "_extract_points"]
