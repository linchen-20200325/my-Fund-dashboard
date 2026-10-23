"""v19.198 P1-6:⑦ HWM σ + ⑧ 風險對比 + ⑨ 遠離高點清單(從 fund_grp_health_extras 主檔抽出)。

2026-10-23 裁示 2C(BL-0426):HWM σ 一律取自 `services/fund_position.compute_fund_position`
(配息還原序列、fail closed、中性三態);本檔只渲染,不自己算 σ。
"""
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
    st.caption("HWM = 過去 252 天配息還原(含息)淨值的最高點;σ_rank = 現價在 HWM 下方第幾個 σ(負值),"
               "以配息還原淨值計算。位階分三段:接近高點 / 中段 / 遠離高點(切點為研究候選、未校準);"
               "這是相對自身近一年高點的位置證據,不是買賣建議。開頭 ⬜ = 無法判定或不適用。")
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
    """⑨ 遠離高點清單(σ rank ≤ −1.5,配息還原基準)。

    2026-10-23 裁示 2C(BL-0426):~~依 HWM σ rank 篩 σ ≤ -2.0~~ → 依 SSOT
    `compute_fund_position` 的 `position == "far_from_high"` 篩(客戶同意改用既有的 −1.5 切點;
    研究候選門檻、未校準)。只陳述位置,**不給任何買賣建議**;無法判定的基金不列入。
    (函式名沿用舊名,避免呼叫端改動;元件與排版不變,只改條件與文字。)
    """
    st.divider()
    st.markdown("### 📍 遠離高點清單（≤ −1.5σ，研究候選門檻、未校準）")

    try:
        from services.fund_position import compute_fund_position
    except Exception as e:
        system_error("σ 模組載入失敗", e)
        return

    _oversold = []
    _n_unknown = 0          # BL-0428 DG-1 A:⬜(位置無法判定)檔數,另列、不當成「不在遠離高點區」
    for _f in funds:
        _code = _f.get("code", "?")
        _name = (_f.get("name") or _code)[:24]
        _r = compute_fund_position(_f)
        if _r.get("status") != "ok":
            _n_unknown += 1
            continue
        if _r.get("position") == "far_from_high":
            _oversold.append({
                "code": _code, "name": _name,
                "sigma_rank": _r.get("sigma_rank"),
                "dist_pct": _r.get("dist_to_hwm_pct"),
                "current": _r.get("current_nav"),
                "hwm": _r.get("hwm_tr"),
            })

    # BL-0428 DG-1 A(2026-10-23):有 ⬜ 時不得用綠色成功框說「目前無基金位於遠離高點區」——
    # ⬜ 的基金不是「不在遠離高點區」,是「不知道」。改灰色說明 + 另列 ⬜ 檔數(沿用既有用字)。
    _unk_note = (f"⬜ 另有 {_n_unknown} 檔位置無法判定(資料不足／無法判定),未列入本清單。"
                 if _n_unknown else "")
    if not _oversold:
        if _n_unknown >= len(funds):
            st.caption(f"⬜ 全部 {_n_unknown} 檔位置無法判定(資料不足／無法判定),"
                       "無法列出遠離高點清單。")
        elif _n_unknown:
            st.caption("可判定的基金中,目前無基金位於遠離高點區。" + _unk_note)
        else:
            st.success("目前無基金位於遠離高點區")
        return

    st.caption(f"偵測到 **{len(_oversold)} 檔基金** 位於遠離高點區"
               f"(σ rank ≤ −1.5,以配息還原淨值計算;切點 −0.5σ／−1.5σ 為研究候選、未校準,"
               f"非正式投資門檻)" + (f"。{_unk_note}" if _unk_note else ""))
    for _o in _oversold:
        st.markdown(
            f"<div style='background:{BG_DARK_RED_1};border-left:4px solid {MATERIAL_RED};"
            f"padding:8px 14px;margin:6px 0;border-radius:6px;'>"
            f"<b style='color:#ff6b6b'>📍 {_o['name']} ({_o['code']})</b><br>"
            f"<span style='color:{GRAY_CC};font-size:12px'>"
            f"現價 {_o['current']:.2f} ｜ HWM(配息還原) {_o['hwm']:.2f} ｜ "
            f"距高點 <b style='color:{MATERIAL_RED}'>{_o['dist_pct']:+.2f}%</b> ｜ "
            f"σ rank <b style='color:{MATERIAL_RED}'>{_o['sigma_rank']:+.2f}σ</b>"
            f"</span><br>"
            f"<span style='color:{TRAFFIC_NEUTRAL};font-size:11px'>"
            f"📍 相對自身近一年高點的位置證據,不是買賣建議;"
            f"切點 −1.5σ 為研究候選門檻、未校準</span>"
            f"</div>",
            unsafe_allow_html=True,
        )


# ════════════════════════════════════════════════════════════════
# v19.121 P1 視覺 — 買賣點表 + Bollinger 可展開詳圖
# ════════════════════════════════════════════════════════════════
