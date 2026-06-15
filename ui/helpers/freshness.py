"""v19.62 E3：MoneyDJ 資料新鮮度 banner 共用 helper（從 tab_fund_grp_health 抽出）。

統一三個基金 Tab（Tab2 單一基金 / Tab3 組合基金 / Tab5 組合健檢）的
「📊 MoneyDJ 資料新鮮度」顯示，鏡像 Stock v18.197 個股新鮮度條。

每個 item dict 統一格式：{code, name, nav_date, fetched_at}（缺則容錯）。
traffic-light：🟢 ≤2d（含週末）/ 🟠 ≤7d（NAV 發布 T+1~2 + 假日放寬）/ 🔴 >7d。
"""
from __future__ import annotations

import datetime as _dt

import streamlit as st


def nav_age_emoji(nav_date_str, today=None):
    """共用 NAV traffic-light：🟢≤2d / 🟠≤7d / 🔴>7d / ⬜未知。

    回 (emoji, age|None)。供 banner 與 sidebar 全局健康共用。
    """
    _today = today or _dt.date.today()
    _s = str(nav_date_str or "").strip()
    if not _s:
        return "⬜", None
    try:
        _nd = _dt.datetime.strptime(_s[:10], "%Y-%m-%d").date()
        _age = (_today - _nd).days
        if _age <= 2:
            return "🟢", _age
        if _age <= 7:
            return "🟠", _age
        return "🔴", _age
    except (ValueError, TypeError):
        return "⬜", None


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


def _nav_counts(nav_dates, today):
    """聚合一組 nav_date 的紅綠燈統計，回 (emoji_headline, {green,yellow,red,unknown})。"""
    _c = {"green": 0, "yellow": 0, "red": 0, "unknown": 0}
    for _d in nav_dates:
        _e, _ = nav_age_emoji(_d, today)
        _c[{"🟢": "green", "🟠": "yellow", "🔴": "red", "⬜": "unknown"}[_e]] += 1
    if _c["red"]:
        _head = "🔴"
    elif _c["yellow"]:
        _head = "🟠"
    elif _c["green"]:
        _head = "🟢"
    else:
        _head = "⬜"
    return _head, _c


def render_sidebar_data_health(session_state, now_tw=None) -> None:
    """v19.63 F：Sidebar 全局資料健康總覽 — 聚合各 Tab 新鮮度訊號。

    讀 session_state（sidebar 先於 Tab render，故各 key 都可能未填 → 容錯）：
      - 總經 FRED：_fred_sources（命中率）+ macro_last_update（抓取 age）
      - 組合基金 NAV：portfolio_funds[i].moneydj_raw.nav_date
      - 單一基金 NAV：fund_data.nav_date
    整體 headline = 各域最差燈號；全空 → 顯「尚未載入」提示。
    """
    _today = (now_tw().date() if now_tw else _dt.date.today())
    _lines: list = []
    _domain_emojis: list = []

    # ── 總經 FRED ──
    _fred = session_state.get("_fred_sources") or {}
    if _fred:
        _ok = sum(1 for v in _fred.values() if (v or {}).get("success"))
        _tot = len(_fred)
        _emoji = "🟢" if _ok == _tot else ("🟠" if _ok > 0 else "🔴")
        _age_txt = ""
        _mlu = session_state.get("macro_last_update")
        if _mlu is not None and now_tw is not None:
            try:
                _age_h = (now_tw() - _mlu).total_seconds() / 3600
                _age_txt = (f" · {int(_age_h * 60)}分前" if _age_h < 1
                            else f" · {_age_h:.1f}h前")
                if _age_h > 4 and _emoji == "🟢":
                    _emoji = "🟠"
            except Exception:
                _age_txt = ""
        _domain_emojis.append(_emoji)
        _lines.append(f"{_emoji} 總經 FRED {_ok}/{_tot} 命中{_age_txt}")
    elif session_state.get("macro_done"):
        _domain_emojis.append("🟢")
        _lines.append("🟢 總經已載入")

    # ── 組合基金 NAV（portfolio_funds）──
    _pf = session_state.get("portfolio_funds") or []
    _pf_dates = []
    for _f in _pf:
        if not isinstance(_f, dict):
            continue
        _mj = _f.get("moneydj_raw") or {}
        _pf_dates.append(_mj.get("nav_date", ""))
    if _pf_dates:
        _head, _c = _nav_counts(_pf_dates, _today)
        _domain_emojis.append(_head)
        _lines.append(
            f"{_head} 組合 {len(_pf_dates)} 檔 · "
            f"🟢{_c['green']} 🟠{_c['yellow']} 🔴{_c['red']} ⬜{_c['unknown']}"
        )

    # ── 單一基金 NAV（fund_data）──
    _fd = session_state.get("fund_data") or {}
    if isinstance(_fd, dict):
        _fd_nav = _fd.get("nav_date") or (_fd.get("moneydj_raw") or {}).get("nav_date")
        if _fd_nav:
            _e, _a = nav_age_emoji(_fd_nav, _today)
            _nm = str(_fd.get("fund_name", "") or "單檔")[:10]
            _domain_emojis.append(_e)
            _age_s = f"{_a}d" if _a is not None else "?"
            _lines.append(f"{_e} 單檔 {_nm} · NAV {_age_s}")

    # ── headline + render ──
    st.markdown("##### 📊 全局資料健康")
    if not _lines:
        st.caption("⬜ 尚未載入任何資料；切換各 Tab 載入後這裡顯示總覽")
        return
    _head_order = {"🔴": 3, "🟠": 2, "🟢": 1, "⬜": 0}
    _headline = max(_domain_emojis, key=lambda e: _head_order.get(e, 0)) if _domain_emojis else "⬜"
    _body = "<br/>".join(_lines)
    _border = {"🔴": "#f85149", "🟠": "#d29922", "🟢": "#3fb950", "⬜": "#444"}.get(_headline, "#444")
    st.markdown(
        f"<div style='background:#0d1117;border-left:4px solid {_border};"
        f"border-radius:4px;padding:6px 10px;font-size:11px;color:#8b949e;"
        f"line-height:1.7'>{_body}</div>",
        unsafe_allow_html=True,
    )
    if _headline in ("🔴", "🟠"):
        st.caption("🟠 部分資料偏舊，可按下方「🧹 全域刷新」重抓最新")
