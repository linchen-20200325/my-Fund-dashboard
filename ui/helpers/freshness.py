"""v19.62 E3：MoneyDJ 資料新鮮度 banner 共用 helper（從 tab_fund_grp_health 抽出）。

統一三個基金 Tab（Tab2 單一基金 / Tab3 組合基金 / Tab5 組合健檢）的
「📊 MoneyDJ 資料新鮮度」顯示，鏡像 Stock v18.197 個股新鮮度條。

每個 item dict 統一格式：{code, name, nav_date, fetched_at}（缺則容錯）。
traffic-light：🟢 ≤2d（含週末）/ 🟠 ≤7d（NAV 發布 T+1~2 + 假日放寬）/ 🔴 >7d。
"""
from __future__ import annotations

import datetime as _dt

import streamlit as st


def render_mj_freshness_banner(items: list, title: str = "MoneyDJ 資料新鮮度") -> None:
    """渲染 MoneyDJ 資料新鮮度 banner（純顯示，零副作用）。

    items: list of dict，每個含 code / name / nav_date / fetched_at。
    title: banner 標題（Tab2 可傳「單檔資料新鮮度」等客製字串）。
    """
    if not items:
        return
    _today = _dt.date.today()
    _parts: list = []
    _stats = {"green": 0, "yellow": 0, "red": 0, "unknown": 0}
    for _it in items:
        _code = str(_it.get("code", "?") or "?")
        _nm = str(_it.get("name", "") or _code)[:14]
        _nav_d = str(_it.get("nav_date", "") or "").strip()
        _fetched = str(_it.get("fetched_at", "") or "").strip()
        _emoji = "⬜"
        _age_txt = "—"
        if _nav_d:
            try:
                _nd = _dt.datetime.strptime(_nav_d[:10], "%Y-%m-%d").date()
                _age = (_today - _nd).days
                if _age <= 2:
                    _emoji = "🟢"
                    _stats["green"] += 1
                elif _age <= 7:
                    _emoji = "🟠"
                    _stats["yellow"] += 1
                else:
                    _emoji = "🔴"
                    _stats["red"] += 1
                _age_txt = f"{_age}d"
            except (ValueError, TypeError):
                _stats["unknown"] += 1
        else:
            _stats["unknown"] += 1
        _fetch_short = _fetched[11:16] if len(_fetched) >= 16 else "—"
        _nav_show = _nav_d if _nav_d else "未知"
        _fetched_show = _fetched if _fetched else "—"
        _nav_inline = _nav_d if _nav_d else "?"
        _parts.append(
            f"<span title='{_code} ｜ NAV {_nav_show} ｜ 抓取於 "
            f"{_fetched_show} ｜ 延遲 {_age_txt}'>"
            f"{_emoji} <b>{_nm}</b> "
            f"<span style='color:#888'>{_nav_inline}/{_fetch_short}/{_age_txt}</span>"
            f"</span>"
        )
    _summary = (
        f"🟢 {_stats['green']} ｜ 🟠 {_stats['yellow']} ｜ "
        f"🔴 {_stats['red']} ｜ ⬜ {_stats['unknown']}"
    )
    st.markdown(
        f"<div style='background:#0d1117;border-left:4px solid #58a6ff;"
        f"border-radius:4px;padding:6px 12px;margin-bottom:8px;"
        f"font-size:11px;color:#8b949e;line-height:1.7'>"
        f"📊 <b>{title}</b>　{_summary}　"
        f"<span style='color:#666;font-size:10px'>"
        f"（hover chip 看完整時戳 ｜ 規則：🟢 ≤2d / 🟠 ≤7d / 🔴 >7d）</span><br/>"
        f"{' ｜ '.join(_parts)}"
        f"</div>",
        unsafe_allow_html=True,
    )
