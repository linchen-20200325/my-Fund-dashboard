"""v19.64 I1：總經 → 組合基金 曝險聯動 banner（跨 Tab 訊號聯動首棒）。

在 Tab3（組合基金）配置總覽，讀 Tab1（總經）已算好的 phase_info /
systemic_risk_data（session_state），把景氣 regime + 建議資產配置 + 系統性
風險疊加到組合視圖，讓 user 不切 Tab 即看到「總經 → 建議配置」聯動。

誠實性：phase_info.alloc 是「股/債/現金」資產類別配置（calc_macro_phase
機構級評分），與組合的「核心/衛星」軸不同 → banner 分開呈現，不硬湊等號；
僅在防禦 regime + 高系統性風險 + 核心比例偏低時給輕量 nudge。

讀 session_state（Tab3 render 時 Tab1 可能尚未載入 → 容錯）：
  - macro_done：bool
  - phase_info：calc_macro_phase 結果（phase / score / alloc / advice /
    rec_prob / alerts / trend_arrow / next_phase / phase_color）
  - systemic_risk_data：{risk_level, risk_icon, risk_score}
"""
from __future__ import annotations

import streamlit as st

from shared.colors import TRAFFIC_NEUTRAL  # v19.253 Phase 4-B2 #888 SSOT


def render_macro_exposure_link(session_state, core_pct=None) -> None:
    """渲染總經→組合曝險聯動 banner（純顯示，零副作用，零新 IO）。

    core_pct: 組合實際核心(穩健)資產比例 %（Tab3 _core_pct_kpi），作 context。
    """
    if not session_state.get("macro_done"):
        st.caption("🧭 載入「總經」Tab 後，這裡會顯示景氣 → 建議配置聯動")
        return
    _phase = session_state.get("phase_info") or {}
    if not isinstance(_phase, dict) or not _phase.get("phase"):
        st.caption("🧭 載入「總經」Tab 後，這裡會顯示景氣 → 建議配置聯動")
        return

    _ph = str(_phase.get("phase", "?"))
    _score = _phase.get("score")
    _color = str(_phase.get("phase_color", "#58a6ff") or "#58a6ff")
    _alloc = _phase.get("alloc") or {}
    _advice = str(_phase.get("advice", "") or "")
    _arrow = str(_phase.get("trend_arrow", "") or "")
    _next = str(_phase.get("next_phase", "") or "")
    _recp = _phase.get("rec_prob")
    _alerts = _phase.get("alerts") or []

    _srd = session_state.get("systemic_risk_data") or {}
    _risk_icon = str(_srd.get("risk_icon", "") or "")
    _risk_lvl = str(_srd.get("risk_level", "") or "")

    # ── header：景氣 + 評分 + 轉折 + 衰退機率 + 系統性風險 ──
    _head = f"🧭 <b>總經景氣聯動</b>（來自 Tab1）：<b style='color:{_color}'>{_ph}</b>"
    if _score is not None:
        _head += f" {_score}/10"
    if _arrow and _next:
        _head += f" <span style='color:{TRAFFIC_NEUTRAL}'>{_arrow} {_next}</span>"
    if _recp is not None:
        try:
            _head += f"　衰退機率 {float(_recp):.0f}%"
        except (TypeError, ValueError):
            pass
    if _risk_lvl:
        _head += f"　系統性風險 {_risk_icon} {_risk_lvl}"

    # ── 建議配置（股/債/現金）+ 你的核心比例 context ──
    _alloc_str = " / ".join(f"{_k} {_v}%" for _k, _v in _alloc.items()) if _alloc else "—"
    _body = f"建議資產配置：<b style='color:#c9d1d9'>{_alloc_str}</b>"
    if core_pct is not None:
        try:
            _body += (f"　·　你目前核心(穩健) <b style='color:#64b5f6'>"
                      f"{float(core_pct):.1f}%</b>（核心/衛星軸，與股債配置不同）")
        except (TypeError, ValueError):
            pass

    st.markdown(
        f"<div style='background:#0d1117;border-left:4px solid {_color};"
        f"border-radius:4px;padding:8px 12px;margin-bottom:8px;font-size:12px;"
        f"color:#8b949e;line-height:1.7'>"
        f"{_head}<br/>{_body}"
        + (f"<br/><span style='color:#aaa;font-size:11px'>💡 {_advice}</span>"
           if _advice else "")
        + "</div>",
        unsafe_allow_html=True,
    )

    # ── 輕量 nudge：防禦 regime + 高系統性風險 + 核心偏低 ──
    _defensive = _ph in ("衰退", "高峰") or _risk_lvl == "HIGH"
    if _defensive and core_pct is not None:
        try:
            if float(core_pct) < 50:
                st.caption(
                    f"🟠 景氣偏防禦（{_ph}）／系統性風險偏高，而你的核心(穩健)"
                    f"僅 {float(core_pct):.1f}% → 可考慮提高核心、降衛星曝險"
                )
        except (TypeError, ValueError):
            pass

    # ── 總經風險警報（取前 2 條，避免洗版）──
    if _alerts:
        _top = [str(a) for a in _alerts[:2] if a]
        if _top:
            st.caption("　".join(_top))
