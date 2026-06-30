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

from shared.colors import GH_BG_CARD, GH_BG_PRIMARY, GH_BORDER, MATERIAL_GREEN, TRAFFIC_NEUTRAL
# F-GRAY-4 v19.179 PR-3:PMI mk_tolerance SSOT
from shared.macro_thresholds_v2 import PMI_THRESHOLDS as _PMI_THR_V2
_PMI_MK_EXPANSION = _PMI_THR_V2["mk_tolerance"]["expansion_above"]    # 50.5
_PMI_MK_CONTRACTION = _PMI_THR_V2["mk_tolerance"]["contraction_below"]  # 49.5


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
                  "color": MATERIAL_GREEN,
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
    "unknown":   {"zh": "資料不足", "icon": "❓",
                  "desc": "PMI / CPI 任一面向缺資料，無法定位四象限",
                  "alloc_eq": 50, "alloc_bd": 50,
                  "color": "#888888",
                  "advice": "請至 Tab1 點「載入總經指標」抓取 FRED 最新資料後再回來查看；勿以此狀態作投資依據。"},
}


def _trend_int(trend_str: str) -> int:
    """trend 字串轉 +1 / 0 / -1。"""
    t = (trend_str or "").lower()
    if t in ("up", "rising", "+", "↑"):
        return 1
    if t in ("down", "falling", "-", "↓"):
        return -1
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
    src = indicators or {}
    pmi_v = (src.get("PMI")      or {}).get("value")
    cpi_v = (src.get("CPI")      or {}).get("value")
    fed_v = (src.get("FED_RATE") or {}).get("value")
    pmi_t = _trend_int((src.get("PMI")      or {}).get("trend"))
    cpi_t = _trend_int((src.get("CPI")      or {}).get("trend"))
    fed_t = _trend_int((src.get("FED_RATE") or {}).get("trend"))

    # 美林時鐘核心兩面向：PMI（經濟）與 CPI（通膨）。任一缺失就無法定位
    # → 改回 "unknown" 而非默默落入 else 變衰退（這曾是長期誤判的根因）。
    missing = [k for k, v in (("PMI", pmi_v), ("CPI", cpi_v)) if v is None]
    if missing:
        meta = dict(_PHASE_META["unknown"])
        meta.update(pmi=pmi_v, cpi=cpi_v, fed=fed_v,
                    pmi_t=pmi_t, cpi_t=cpi_t, fed_t=fed_t,
                    rate_down=(fed_v is not None and fed_t < 0),
                    missing=missing)
        return "unknown", meta

    # PMI 50 邊界 ±0.5 噪音容忍：49.5~50.5 視為臨界，配合 trend 才判方向
    if pmi_v >= _PMI_MK_EXPANSION:
        econ_up = True
    elif pmi_v <= _PMI_MK_CONTRACTION:
        econ_up = pmi_t > 0   # 收縮區唯有趨勢上升才視為復甦動能
    else:
        econ_up = pmi_t >= 0  # 臨界區 trend 持平/上升 → 視為擴張側

    infl_up   = cpi_t > 0
    rate_down = fed_v is not None and fed_t < 0

    if econ_up and not infl_up:
        phase = "recovery"
    elif econ_up and infl_up:
        phase = "expansion"
    elif (not econ_up) and infl_up:
        phase = "slowdown"
    else:
        phase = "recession"

    meta = dict(_PHASE_META[phase])
    meta.update(pmi=pmi_v, cpi=cpi_v, fed=fed_v,
                pmi_t=pmi_t, cpi_t=cpi_t, fed_t=fed_t,
                rate_down=rate_down, missing=[])
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
    # 四象限填色（barpolar）— unknown 時全部維持淡色，提示「未定位」
    is_unknown = phase == "unknown"
    for key, theta_center, label in quadrants:
        meta = _PHASE_META[key]
        is_current = (key == phase)
        fig.add_trace(go.Barpolar(
            r=[1.0],
            theta=[theta_center],
            width=[90],
            marker=dict(
                color=meta["color"],
                opacity=0.20 if is_unknown else (1.0 if is_current else 0.30),
                line=dict(color="#fff" if is_current else "#444", width=2),
            ),
            name=f"{meta['icon']} {meta['zh']}",
            hovertemplate=f"<b>{meta['zh']}</b><br>{meta['desc']}<extra></extra>",
            showlegend=True,
        ))

    # 中心指針（unknown 時不畫，避免誤導使用者）
    if not is_unknown:
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
            bgcolor=GH_BG_PRIMARY,
        ),
        paper_bgcolor=GH_BG_PRIMARY,
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
            f"<div style='background:linear-gradient(135deg,{meta['color']}22,{GH_BG_PRIMARY});"
            f"border-left:6px solid {meta['color']};border-radius:10px;padding:18px 20px;"
            f"margin-bottom:14px'>"
            f"<div style='font-size:12px;color:{TRAFFIC_NEUTRAL};letter-spacing:2px'>當前景氣階段</div>"
            f"<div style='font-size:32px;font-weight:700;color:{meta['color']};margin:6px 0'>"
            f"{meta['icon']} {meta['zh']}</div>"
            f"<div style='font-size:13px;color:#aaa;margin-bottom:10px'>{meta['desc']}</div>"
            f"<div style='font-size:14px;color:#e0e0e0;line-height:1.7'>{meta['advice']}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

        # 三面向指標摘要 — 缺資料的欄位顯示「—」並標紅，避免假象
        def _fmt_cell(label: str, val, t_int: int, unit: str = "", fmt: str = "{:.1f}"):
            arrow = "↑" if t_int > 0 else ("↓" if t_int < 0 else "→")
            if val is None:
                num_html = "<span style='color:#ff7043'>—</span>"
                tag = "<div style='font-size:10px;color:#ff7043;margin-top:2px'>未抓到</div>"
            else:
                num_html = f"{fmt.format(val)}{unit} {arrow}"
                tag = ""
            return (
                f"<div style='background:{GH_BG_CARD};border:1px solid {GH_BORDER};border-radius:8px;padding:10px;text-align:center'>"
                f"<div style='font-size:11px;color:{TRAFFIC_NEUTRAL}'>{label}</div>"
                f"<div style='font-size:18px;font-weight:600;color:#e0e0e0'>{num_html}</div>"
                f"{tag}</div>"
            )

        st.markdown(
            f"<div style='font-size:12px;color:{TRAFFIC_NEUTRAL};margin-bottom:6px'>三面向訊號</div>"
            f"<div style='display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px'>"
            f"{_fmt_cell('基本面 PMI', meta.get('pmi'),  meta['pmi_t'], '',  '{:.1f}')}"
            f"{_fmt_cell('通膨 CPI',   meta.get('cpi'),  meta['cpi_t'], '%', '{:.2f}')}"
            f"{_fmt_cell('資金 利率',  meta.get('fed'),  meta['fed_t'], '%', '{:.2f}')}"
            f"</div>",
            unsafe_allow_html=True,
        )

        if meta.get("missing"):
            st.warning(
                f"⚠️ 缺少 {' / '.join(meta['missing'])} 資料，目前**無法定位四象限**。"
                "請至 Tab1 點「載入總經指標」抓取 FRED 最新資料後再回此區查看。",
                icon="⚠️",
            )

        # 配置條
        st.markdown(
            f"<div style='margin-top:14px;font-size:12px;color:{TRAFFIC_NEUTRAL}'>建議股債比例</div>"
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
