"""MK 景氣時鐘觀測站（v18.10）

依「MK 郭俊宏《景氣三面向與資產配置策略》」實作美林時鐘四象限定位。

整合策略：
- 重用 app.py session_state["indicators"]（PMI / CPI / FED_RATE / VIX 等），
  不重複呼叫 FRED。
- 主入口：render_mk_clock_section(indicators)，其餘為內部 helper。
"""
from __future__ import annotations

import datetime as _dt
from typing import Optional

import plotly.graph_objects as go
import streamlit as st


# ══════════════════════════════════════════════════════════════════
# Phase Classification（美林時鐘四象限）
# ══════════════════════════════════════════════════════════════════

# 預設 mock：API 全失敗時保證 UI 仍能跑
_MOCK_INDICATORS = {
    "PMI":      {"value": 49.0, "trend": "down"},
    "CPI":      {"value": 2.8,  "trend": "flat"},
    "FED_RATE": {"value": 4.5,  "trend": "down"},
}

# 四象限定義（按 MK 教材）
_PHASE_META = {
    "recovery":  {"zh": "復甦期", "icon": "🌱",
                  "desc": "通膨降 / 利率降 / 經濟升",
                  "alloc_eq": 70, "alloc_bd": 30,
                  "color": "#00c853",
                  "advice": "股優於債（建議 股 7 : 債 3）｜衛星佈局：週期成長 / 科技 / 非必需消費"},
    "expansion": {"zh": "繁榮期", "icon": "🔥",
                  "desc": "通膨升 / 利率升 / 經濟升",
                  "alloc_eq": 60, "alloc_bd": 40,
                  "color": "#ffb300",
                  "advice": "股優於債（建議 股 6 : 債 4）｜衛星佈局：原物料 / 中小型成長 / 工業"},
    "slowdown":  {"zh": "趨緩期", "icon": "⚠️",
                  "desc": "通膨升 / 利率升 / 經濟降（停滯性通膨）",
                  "alloc_eq": 40, "alloc_bd": 60,
                  "color": "#ff7043",
                  "advice": "現金 / 債優於股（建議 股 4 : 債 6）｜核心轉向：防禦型 / 高股息 / 醫療 / 公用事業"},
    "recession": {"zh": "衰退期", "icon": "❄️",
                  "desc": "通膨降 / 利率降 / 經濟降",
                  "alloc_eq": 30, "alloc_bd": 70,
                  "color": "#42a5f5",
                  "advice": "債優於股（建議 股 3 : 債 7）｜核心加碼：美國公債 / 投資等級債"},
}


def _trend_int(trend_str: str) -> int:
    """trend 字串轉 +1 / 0 / -1。"""
    t = (trend_str or "").lower()
    if t in ("up", "rising", "+", "↑"):   return 1
    if t in ("down", "falling", "-", "↓"): return -1
    return 0


def classify_phase(indicators: dict) -> tuple[str, dict]:
    """依 PMI 水位 + CPI 趨勢 + FED_RATE 趨勢 判定四象限。

    判定規則（簡化版美林時鐘）：
      - 經濟方向 = PMI > 50（擴張）或 PMI < 50（收縮）；趨勢補強
      - 通膨方向 = CPI 趨勢（up=升 / down=降）
      → 復甦：PMI ↑ 收縮反彈 + CPI ↓
      → 繁榮：PMI > 50 擴張 + CPI ↑
      → 趨緩：PMI < 50 走弱 + CPI ↑（停滯性通膨）
      → 衰退：PMI < 50 + CPI ↓

    Returns
    -------
    (phase_key, meta_dict)  meta_dict 含 zh / icon / advice / alloc_eq / alloc_bd
    """
    src = indicators or _MOCK_INDICATORS
    pmi_v   = (src.get("PMI")      or {}).get("value")
    pmi_t   = _trend_int((src.get("PMI") or {}).get("trend"))
    cpi_t   = _trend_int((src.get("CPI") or {}).get("trend"))
    fed_t   = _trend_int((src.get("FED_RATE") or {}).get("trend"))

    # PMI 缺失 → 用 mock 值避免崩潰
    if pmi_v is None:
        pmi_v = _MOCK_INDICATORS["PMI"]["value"]

    econ_up   = pmi_v >= 50 or pmi_t > 0
    infl_up   = cpi_t > 0
    rate_down = fed_t < 0

    if econ_up and not infl_up:
        phase = "recovery"
    elif econ_up and infl_up:
        phase = "expansion"
    elif (not econ_up) and infl_up:
        phase = "slowdown"
    else:
        phase = "recession"

    meta = dict(_PHASE_META[phase])
    meta["pmi"]    = pmi_v
    meta["pmi_t"]  = pmi_t
    meta["cpi_t"]  = cpi_t
    meta["fed_t"]  = fed_t
    meta["rate_down"] = rate_down
    return phase, meta


# ══════════════════════════════════════════════════════════════════
# Module 1 — 美林時鐘視覺化
# ══════════════════════════════════════════════════════════════════

def _build_clock_figure(phase: str) -> go.Figure:
    """繪製極座標版美林時鐘（4 象限 + 當前指針）。"""
    quadrants = [
        ("recovery",  90,  "🌱 復甦期"),
        ("expansion", 0,   "🔥 繁榮期"),
        ("slowdown",  -90, "⚠️ 趨緩期"),
        ("recession", 180, "❄️ 衰退期"),
    ]

    fig = go.Figure()
    # 四象限填色（barpolar）
    for key, theta_center, label in quadrants:
        meta = _PHASE_META[key]
        is_current = (key == phase)
        fig.add_trace(go.Barpolar(
            r=[1.0],
            theta=[theta_center],
            width=[90],
            marker=dict(
                color=meta["color"],
                opacity=1.0 if is_current else 0.30,
                line=dict(color="#fff" if is_current else "#444", width=2),
            ),
            name=f"{meta['icon']} {meta['zh']}",
            hovertemplate=f"<b>{meta['zh']}</b><br>{meta['desc']}<extra></extra>",
            showlegend=True,
        ))

    # 中心指針
    cur_theta = next(t for k, t, _ in quadrants if k == phase)
    fig.add_trace(go.Scatterpolar(
        r=[0, 0.85],
        theta=[0, cur_theta],
        mode="lines+markers",
        line=dict(color="#fff", width=4),
        marker=dict(size=[8, 14], color="#fff", symbol=["circle", "arrow"]),
        name="當前位置",
        showlegend=False,
        hoverinfo="skip",
    ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=False, range=[0, 1.05]),
            angularaxis=dict(
                tickmode="array",
                tickvals=[90, 0, -90, 180],
                ticktext=["🌱 復甦", "🔥 繁榮", "⚠️ 趨緩", "❄️ 衰退"],
                tickfont=dict(size=14, color="#ddd"),
                rotation=90, direction="counterclockwise",
            ),
            bgcolor="#0d1117",
        ),
        paper_bgcolor="#0d1117",
        height=420, margin=dict(t=20, b=20, l=20, r=20),
        legend=dict(orientation="h", y=-0.05, font=dict(size=11, color="#aaa")),
    )
    return fig


def render_macro_clock(indicators: dict) -> tuple[str, dict]:
    """Module 1：渲染美林時鐘 + 配置建議大字卡。回傳 (phase_key, meta)。"""
    phase, meta = classify_phase(indicators)

    c1, c2 = st.columns([1.2, 1])
    with c1:
        st.plotly_chart(_build_clock_figure(phase), use_container_width=True,
                        key="mk_clock_polar")

    with c2:
        # 配置建議大字卡
        st.markdown(
            f"<div style='background:linear-gradient(135deg,{meta['color']}22,#0d1117);"
            f"border-left:6px solid {meta['color']};border-radius:10px;padding:18px 20px;"
            f"margin-bottom:14px'>"
            f"<div style='font-size:12px;color:#888;letter-spacing:2px'>當前景氣階段</div>"
            f"<div style='font-size:32px;font-weight:700;color:{meta['color']};margin:6px 0'>"
            f"{meta['icon']} {meta['zh']}</div>"
            f"<div style='font-size:13px;color:#aaa;margin-bottom:10px'>{meta['desc']}</div>"
            f"<div style='font-size:14px;color:#e0e0e0;line-height:1.7'>{meta['advice']}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

        # 三面向指標摘要
        pmi_arrow = "↑" if meta["pmi_t"] > 0 else ("↓" if meta["pmi_t"] < 0 else "→")
        cpi_arrow = "↑" if meta["cpi_t"] > 0 else ("↓" if meta["cpi_t"] < 0 else "→")
        fed_arrow = "↑" if meta["fed_t"] > 0 else ("↓" if meta["fed_t"] < 0 else "→")
        st.markdown(
            f"<div style='font-size:12px;color:#888;margin-bottom:6px'>三面向訊號</div>"
            f"<div style='display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px'>"
            f"<div style='background:#161b22;border:1px solid #30363d;border-radius:8px;padding:10px;text-align:center'>"
            f"<div style='font-size:11px;color:#888'>基本面 PMI</div>"
            f"<div style='font-size:18px;font-weight:600;color:#e0e0e0'>{meta['pmi']:.1f} {pmi_arrow}</div></div>"
            f"<div style='background:#161b22;border:1px solid #30363d;border-radius:8px;padding:10px;text-align:center'>"
            f"<div style='font-size:11px;color:#888'>通膨 CPI</div>"
            f"<div style='font-size:18px;font-weight:600;color:#e0e0e0'>{cpi_arrow}</div></div>"
            f"<div style='background:#161b22;border:1px solid #30363d;border-radius:8px;padding:10px;text-align:center'>"
            f"<div style='font-size:11px;color:#888'>資金 利率</div>"
            f"<div style='font-size:18px;font-weight:600;color:#e0e0e0'>{fed_arrow}</div></div>"
            f"</div>",
            unsafe_allow_html=True,
        )

        # 配置條
        st.markdown(
            f"<div style='margin-top:14px;font-size:12px;color:#888'>建議股債比例</div>"
            f"<div style='display:flex;height:28px;border-radius:6px;overflow:hidden;margin-top:4px'>"
            f"<div style='width:{meta['alloc_eq']}%;background:#26a69a;display:flex;align-items:center;"
            f"justify-content:center;color:#fff;font-size:12px;font-weight:600'>股 {meta['alloc_eq']}%</div>"
            f"<div style='width:{meta['alloc_bd']}%;background:#5c6bc0;display:flex;align-items:center;"
            f"justify-content:center;color:#fff;font-size:12px;font-weight:600'>債 {meta['alloc_bd']}%</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    return phase, meta



# ══════════════════════════════════════════════════════════════════
# 主入口
# ══════════════════════════════════════════════════════════════════

def render_mk_clock_section(indicators: Optional[dict] = None):
    """主入口：在 Tab1 折疊式呈現完整 MK 景氣時鐘區塊。

    Parameters
    ----------
    indicators : dict | None
        st.session_state["indicators"] 的內容；None 時走 mock。
    """
    with st.expander("🕒 **策略3 景氣時鐘觀測站**（依《景氣三面向》）",
                     expanded=False):
        st.caption(
            f"資料時點：{_dt.date.today().isoformat()}　｜　"
            "三面向：基本面 PMI ／ 通膨 CPI ／ 資金面 利率　｜　"
            "依美林時鐘四象限自動定位"
        )

        st.markdown("#### 🧭 美林時鐘定位器")
        render_macro_clock(indicators or {})

        st.caption(
            "ℹ️ 本區塊為 **教學示意**，依 策略3 教材簡化模型；"
            "實際投資請結合個人風險屬性與更完整的研究流程。"
        )
