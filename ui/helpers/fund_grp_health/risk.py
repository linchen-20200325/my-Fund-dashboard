"""v19.198 P1-6:⑦ HWM σ + ⑧ 風險對比 + ⑨ -2σ 警示(從 fund_grp_health_extras 主檔抽出)。"""
from __future__ import annotations

import streamlit as st

from ui.helpers.render_state import system_error

from shared.colors import BG_DARK_RED_1, GRAY_CC, MATERIAL_RED, TRAFFIC_NEUTRAL

# 2026-10-13 客戶裁示(LINE 推播與舊 UI 解耦):逐檔資料函式原封搬到 L2
# `services/fund_grp_health/risk.py`(週報排程不得依賴 UI 層);本檔只留表格渲染,
# 以下 re-export 同一份物件,舊呼叫點不必改(SSOT,不複製)。
from services.fund_grp_health.risk import (  # noqa: E402,F401
    _PERIOD_KEYS,
    _local_first,
    _lookup_risk_table,
    hwm_sigma_by_code,
    risk_compare_by_code,
)


def _render_hwm_sigma_table(funds: list) -> None:
    """⑦ HWM σ 位階表(獨立版,保留供直接呼叫 / 測試;主流程已併入健診總表)。"""
    st.divider()
    st.markdown("### 📐 HWM σ 位階")
    st.caption("HWM = 過去 252 天歷史最高 NAV;σ_rank = 現價在 HWM 下方第幾個 σ(負值)。"
               "**-2σ 以下 = 深度超跌**(若基本面健康可能是機會),**+1σ 以上 = 過熱**。")
    _data = hwm_sigma_by_code(funds)
    _rows = [
        {"基金": f"{(_f.get('name') or _f.get('code', '?'))[:24]} ({_f.get('code', '?')})",
         **_data.get(_f.get("code", "?"), {})}
        for _f in funds
    ]
    try:
        import pandas as pd
        st.dataframe(pd.DataFrame(_rows), use_container_width=True, hide_index=True)
    except Exception as e:  # noqa: BLE001
        system_error("HWM σ 表渲染失敗", e)


def _render_risk_compare_table(funds: list) -> None:
    """⑧ 風險指標對比表(獨立版,保留供直接呼叫 / 測試;主流程已併入健診總表)。"""
    st.divider()
    st.markdown("### 📊 風險指標對比表")
    st.caption("資料源:MoneyDJ wb07 風險表(直接顯示,不重算)。**Sharpe 越高越好 / σ 越低越穩**。")
    _data = risk_compare_by_code(funds)
    _rows = [
        {"基金": f"{(_f.get('name') or _f.get('code', '?'))[:24]} ({_f.get('code', '?')})",
         **_data.get(_f.get("code", "?"), {})}
        for _f in funds
    ]
    try:
        import pandas as pd
        st.dataframe(pd.DataFrame(_rows), use_container_width=True, hide_index=True)
        _has_sharpe = sum(1 for r in _rows if r.get("Sharpe", "—") != "—")
        if _has_sharpe < len(_rows):
            st.caption(f"⬜ {len(_rows) - _has_sharpe} / {len(_rows)} 檔基金 MoneyDJ 風險表"
                       f"資料不全(顯示 '—',不偽造)")
    except Exception as e:  # noqa: BLE001
        system_error("風險對比表渲染失敗", e)


def _render_oversold_badges(funds: list) -> None:
    """⑨ -2σ 超跌警示 badges(深度超跌基金一覽)。

    依 HWM σ rank 篩 σ ≤ -2.0 的基金。
    深度超跌 + 基本面健康 = 抄底機會;若基本面也差 = 真實衰退,不要接刀。
    """
    st.divider()
    st.markdown("### 🩸 -2σ 超跌警示")

    try:
        from services.precision_service import calc_hwm_sigma_levels
    except Exception as e:
        system_error("σ 模組載入失敗", e)
        return

    _oversold = []
    for _f in funds:
        _code = _f.get("code", "?")
        _name = (_f.get("name") or _code)[:24]
        _series = _f.get("series")
        if _series is None or len(_series) < 30:
            continue
        _r = calc_hwm_sigma_levels(_series)
        if _r.get("error"):
            continue
        _sigma_rank = _r.get("sigma_rank")
        if _sigma_rank is not None and _sigma_rank <= -2.0:
            _oversold.append({
                "code": _code, "name": _name,
                "sigma_rank": _sigma_rank,
                "dist_pct": _r.get("dist_to_hwm_pct", 0),
                "current": _r.get("current_nav"),
                "hwm": _r.get("hwm"),
            })

    if not _oversold:
        st.success("✅ 目前無基金落入 -2σ 深度超跌區")
        return

    st.caption(f"⚠️ 偵測到 **{len(_oversold)} 檔基金** σ ≤ -2.0(歷史高點下方 2 個標準差以上)")
    for _o in _oversold:
        st.markdown(
            f"<div style='background:{BG_DARK_RED_1};border-left:4px solid {MATERIAL_RED};"
            f"padding:8px 14px;margin:6px 0;border-radius:6px;'>"
            f"<b style='color:#ff6b6b'>🩸 {_o['name']} ({_o['code']})</b><br>"
            f"<span style='color:{GRAY_CC};font-size:12px'>"
            f"現價 {_o['current']:.2f} ｜ HWM {_o['hwm']:.2f} ｜ "
            f"距高點 <b style='color:{MATERIAL_RED}'>{_o['dist_pct']:+.2f}%</b> ｜ "
            f"σ rank <b style='color:{MATERIAL_RED}'>{_o['sigma_rank']:+.2f}σ</b>"
            f"</span><br>"
            f"<span style='color:{TRAFFIC_NEUTRAL};font-size:11px'>"
            f"💡 深度超跌:若基本面(評分/吃本金/Sharpe)仍健康 → 可考慮抄底;"
            f"基本面也轉差 → 不要接刀</span>"
            f"</div>",
            unsafe_allow_html=True,
        )


# ════════════════════════════════════════════════════════════════
# v19.121 P1 視覺 — 買賣點表 + Bollinger 可展開詳圖
# ════════════════════════════════════════════════════════════════
