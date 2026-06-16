"""指標卡片渲染（Sparkline + 教學文案 + 量化資料）。

設計原則
────────
- 純函式、無業務邏輯，可在 fund/stock 兩 repo 直接共用
- EDU 內容由呼叫端注入（dict by indicator key），本模組只負責渲染
- Plotly sparkline 含警戒線 + 當前值標記，無多餘軸線
- 不依賴 st.session_state，純參數驅動，方便單元測試

CANONICAL SOURCE: my-fund-dashboard/shared/macro_card.py
"""
from __future__ import annotations

import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from shared.colors import MATERIAL_GREEN, MATERIAL_ORANGE, MATERIAL_RED

EDU_FIELDS = ("meaning", "how_to_read", "pair_with",
              "historical_anchor", "upstream", "downstream")


# ═══════════════════════════════════════════════════════════════════════
# Z-Score / Sparkline 計算
# ═══════════════════════════════════════════════════════════════════════
def calc_z_score(series, current_value=None) -> float | None:
    """以全期間均值/標準差計算當前值 Z-Score；資料 < 10 筆 → None。"""
    if series is None:
        return None
    s = series if isinstance(series, pd.Series) else pd.Series(series)
    s = s.dropna()
    if len(s) < 10:
        return None
    mu, sigma = float(s.mean()), float(s.std())
    if sigma == 0:
        return None
    v = float(current_value) if current_value is not None else float(s.iloc[-1])
    return (v - mu) / sigma


def make_sparkline(
    series,
    *,
    threshold_warn=None,
    threshold_crit=None,
    high_is_bad: bool = True,
    lookback: int = 24,
    height: int = 80,
):
    """產生迷你趨勢圖。資料 < 2 筆 → None。"""
    if series is None:
        return None
    s = series if isinstance(series, pd.Series) else pd.Series(series)
    s = s.dropna().tail(lookback)
    if len(s) < 2:
        return None

    # 判斷整體走勢顏色
    last_v = float(s.iloc[-1])
    color = "#64b5f6"  # default 藍
    if threshold_crit is not None:
        if (high_is_bad and last_v >= threshold_crit) or (not high_is_bad and last_v <= threshold_crit):
            color = MATERIAL_RED
    if threshold_warn is not None and color == "#64b5f6":
        if (high_is_bad and last_v >= threshold_warn) or (not high_is_bad and last_v <= threshold_warn):
            color = MATERIAL_ORANGE

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=list(s.index), y=list(s.values),
        mode="lines",
        line=dict(color=color, width=2),
        hovertemplate="%{x|%Y-%m-%d}: %{y:.2f}<extra></extra>",
        showlegend=False,
    ))
    # 當前值標記點
    fig.add_trace(go.Scatter(
        x=[s.index[-1]], y=[last_v],
        mode="markers",
        marker=dict(color="#ffeb3b", size=8, line=dict(color="#000", width=1)),
        showlegend=False, hoverinfo="skip",
    ))
    # 警戒線
    if threshold_warn is not None:
        fig.add_hline(y=threshold_warn, line_dash="dot",
                      line_color=MATERIAL_ORANGE, opacity=0.55,
                      annotation_text=f"警戒 {threshold_warn}",
                      annotation_position="top right",
                      annotation_font=dict(size=9, color=MATERIAL_ORANGE))
    if threshold_crit is not None:
        fig.add_hline(y=threshold_crit, line_dash="dash",
                      line_color=MATERIAL_RED, opacity=0.7,
                      annotation_text=f"危險 {threshold_crit}",
                      annotation_position="bottom right",
                      annotation_font=dict(size=9, color=MATERIAL_RED))
    fig.update_layout(
        height=height,
        margin=dict(l=4, r=4, t=8, b=4),
        showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False, fixedrange=True),
        yaxis=dict(visible=False, fixedrange=True),
        hovermode="x unified",
    )
    return fig


# ═══════════════════════════════════════════════════════════════════════
# EDU 渲染
# ═══════════════════════════════════════════════════════════════════════
def _esc(x) -> str:
    if x is None:
        return ""
    return (str(x).replace("&", "&amp;").replace("<", "&lt;")
                  .replace(">", "&gt;").replace('"', "&quot;"))


def render_edu_markdown(edu: dict | None) -> str:
    """把 EDU dict 轉成 Markdown 教學區塊。空 dict → 提示尚未撰寫。"""
    if not edu:
        return "_📖 此指標教學內容尚未撰寫。可至 `shared/macro_card_edu.py` 補上。_"
    parts = []
    if edu.get("meaning"):
        parts.append(f"**💡 它是什麼**　{_esc(edu['meaning'])}")
    rows = edu.get("how_to_read")
    if rows:
        if isinstance(rows, list):
            lines = []
            for r in rows:
                if isinstance(r, (tuple, list)) and len(r) >= 2:
                    lines.append(f"- `{_esc(r[0])}` → {_esc(r[1])}")
                else:
                    lines.append(f"- {_esc(r)}")
            parts.append("**📐 怎麼判讀**\n" + "\n".join(lines))
        else:
            parts.append(f"**📐 怎麼判讀**　{_esc(rows)}")
    if edu.get("pair_with"):
        pw = edu["pair_with"]
        pw_s = " / ".join(_esc(x) for x in pw) if isinstance(pw, list) else _esc(pw)
        parts.append(f"**🔗 搭配看誰**　{pw_s}")
    if edu.get("historical_anchor"):
        parts.append(f"**📊 歷史錨點**　{_esc(edu['historical_anchor'])}")
    if edu.get("upstream"):
        parts.append(f"**⬆️ 上游因**　{_esc(edu['upstream'])}")
    if edu.get("downstream"):
        parts.append(f"**⬇️ 下游果**　{_esc(edu['downstream'])}")
    return "\n\n".join(parts)


# ═══════════════════════════════════════════════════════════════════════
# 卡片渲染
# ═══════════════════════════════════════════════════════════════════════
def _z_color(z, high_is_bad):
    if z is None:
        return "#888"
    if abs(z) >= 2:
        bad = (high_is_bad and z > 0) or (not high_is_bad and z < 0)
        return MATERIAL_RED if bad else MATERIAL_GREEN
    if abs(z) >= 1.5:
        return MATERIAL_ORANGE
    return "#64b5f6"


def render_macro_card(
    *,
    name: str,
    value,
    unit: str = "",
    decimals: int = 2,
    signal: str = "",
    series=None,
    edu: dict | None = None,
    z_score: float | None = None,
    threshold_warn=None,
    threshold_crit=None,
    high_is_bad: bool = True,
    edu_default_open: bool = False,
):
    """渲染一張指標卡片：標頭 + sparkline + 完整教學 expander。"""
    if isinstance(value, (int, float)):
        val_str = f"{value:.{decimals}f}{(' ' + unit) if unit else ''}"
    elif value is None:
        val_str = "—"
    else:
        val_str = str(value)
    z_str = f"Z={z_score:+.2f}" if z_score is not None else ""
    z_col = _z_color(z_score, high_is_bad)

    # 卡片標頭
    st.markdown(
        f"<div style='background:#11161e;border:1px solid #1f2933;"
        f"border-radius:10px 10px 0 0;padding:10px 12px;margin:6px 0 0'>"
        f"<div style='display:flex;justify-content:space-between;align-items:baseline;gap:8px'>"
        f"<div style='min-width:0;flex:1'>"
        f"<span style='font-size:16px;margin-right:4px'>{signal or ''}</span>"
        f"<b style='color:#e6edf3;font-size:14px'>{_esc(name)}</b></div>"
        f"<div style='white-space:nowrap'>"
        f"<span style='color:#e6edf3;font-size:14px;font-weight:600'>{val_str}</span>"
        f"<span style='color:{z_col};font-size:11px;margin-left:8px'>{z_str}</span>"
        f"</div></div></div>",
        unsafe_allow_html=True,
    )
    # Sparkline
    fig = make_sparkline(
        series, threshold_warn=threshold_warn,
        threshold_crit=threshold_crit, high_is_bad=high_is_bad,
    )
    if fig is not None:
        st.plotly_chart(fig, use_container_width=True,
                        config={"displayModeBar": False})
    else:
        st.caption("⚠️ 趨勢資料不足，僅顯示當前值")
    # EDU 教學
    with st.expander("📖 完整教學（白話 / 判讀 / 搭配 / 上下游 / 歷史）",
                     expanded=edu_default_open):
        st.markdown(render_edu_markdown(edu))


def render_macro_card_grid(cards: list[dict], columns: int = 2):
    """以 N 欄 grid 渲染多張指標卡。
    cards = [
      {name, value, unit, decimals, signal, series, edu,
       z_score, threshold_warn, threshold_crit, high_is_bad},
      ...
    ]
    """
    if not cards:
        st.info("（尚無可用指標）")
        return
    cols = st.columns(columns)
    for i, card in enumerate(cards):
        with cols[i % columns]:
            render_macro_card(**card)


# ═══════════════════════════════════════════════════════════════════════
# 整合輔助：從 indicators dict + EDU 字典批次組裝 cards
# ═══════════════════════════════════════════════════════════════════════
def build_cards_from_indicators(
    indicators: dict,
    spec: list[tuple],
    edu_map: dict | None = None,
) -> list[dict]:
    """根據 spec 從 indicators dict 拼出卡片參數。

    spec[i] = (key, display_name, unit, decimals, high_is_bad,
               threshold_warn, threshold_crit, edu_key)
    若 edu_key=None，預設用 key 查 edu_map。
    若 indicators[key] 不存在或 value=None，仍會渲染卡片但顯示 "—"。
    """
    edu_map = edu_map or {}
    out = []
    for tup in spec:
        key, name, unit, dec, hib, t_warn, t_crit, *rest = tup
        edu_key = rest[0] if rest else key
        d = indicators.get(key) or {}
        v = d.get("value")
        sig = d.get("signal", "")
        series = d.get("series")
        z = calc_z_score(series, v) if series is not None else None
        out.append(dict(
            name=name, value=v, unit=unit, decimals=dec,
            signal=sig, series=series,
            edu=edu_map.get(edu_key),
            z_score=z,
            threshold_warn=t_warn, threshold_crit=t_crit,
            high_is_bad=hib,
        ))
    return out
