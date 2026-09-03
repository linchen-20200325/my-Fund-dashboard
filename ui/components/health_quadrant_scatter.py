"""ui/components/health_quadrant_scatter.py — 4D 健診四象限散佈圖（UI3b）。

一句話：**把「便宜嗎」（σ 位階）與「體質好嗎」（4D Score）畫在同一張圖上**，
讓「便宜但爛」和「貴但好」不再長得一樣。

軸與編碼
--------
- **X = σ rank**（`services/precision_service.calc_hwm_sigma_levels` 的 `sigma_rank`；
  負 = 在 HWM 下方 N 個 σ = 低基期）。
- **Y = 4D Score**，軸**固定 0–100**。不隨資料自動縮放 —— 自動縮放會讓
  「58 分」在一組爛基金裡看起來位在頂端。分數的意義是絕對的，軸就必須是絕對的。
- **點大小 = `invest_twd`**（投入本金）。
- **點色 = 4D Grade** → `ui.components.status.status_color`。
- **點形狀 = 級別**：核心 `circle` / 衛星 `diamond` / 未定 `x`
  （dataviz #4：不靠顏色單獨編碼）。

⚠️ `grade_levels` 為什麼是參數而不是寫死在這裡
----------------------------------------------
4D Grade 是 `A/B/C/D`，而 `status_color` 的別名表**不含** A/B/C/D
（實測：`status_color("A").level == "unknown"`）。在本元件內寫一張
`{"A":"ok","B":"warn",...}` 等於**憑空造出第二份評等嚴重度 SSOT**，
而「A 算不算綠燈」是後端評等的事，不是畫圖的事。
故：`grade_levels` 由呼叫端傳入；不傳 → 一律走 `status_color(grade)`，
未知 grade 誠實顯示為 ⬜ 灰（§1：不知道就不要假裝知道）。
**已登記建議後端具名化為 `FOUR_D_GRADE_LEVELS`。**

§1 Fail Loud
------------
- **缺 X 或 Y 的點不畫，但必須列出來。** `build_health_quadrant_figure()` 回傳
  `unplaceable` 名單，`render_*` 一定把它印成「⬜ N 檔無法定位：…」。
  **靜默消失就是違憲** —— 一檔沒有 σ 位階的基金從圖上消失，看圖的人會以為它不存在。
- **`invest_twd` 為 None／0 → 最小尺寸 + 空心邊**（`*-open` 符號），並在腳註說明
  「空心 = 沒填本金，不是本金為 0」。畫成實心最小點，會被讀成「有填、金額很小」。

✅ **允許 `degraded=True`**：本圖的每一個數值（σ rank / 4D Score / 本金 / 評等）
在健診大表裡另有出處，這張圖失敗時掉的**只有圖**。合乎
`ui/helpers/render_state.system_error` 的 chart-only 通過條件。

純函式邊界
----------
`split_placeable()` / `build_health_quadrant_figure()` 只依賴 plotly + `shared.colors`
+ `ui.components.*`，零 streamlit、零 session_state、零 cache、零 repository/service、零網路。
"""
from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

import plotly.graph_objects as go

from shared.colors import (
    BG_DARK_GREEN_1,
    BG_DARK_NAVY_4,
    BG_DARK_RED_2,
    GH_BORDER,
    GH_FG_MUTED,
)
from ui.components.chart_factory import PLOTLY_CONFIG, apply_dark_template
from ui.components.status import status_color

# 分隔線位置：σ rank -1.0（HWM 下方 1 個 σ）與 4D Score 50。
SIGMA_SPLIT: float = -1.0
SCORE_SPLIT: float = 50.0
SCORE_AXIS_RANGE: tuple[float, float] = (0.0, 100.0)

# 級別 → 符號。未定一律 `x`（不併進核心，也不併進衛星）。
_TIER_SYMBOL: dict[str, str] = {"core": "circle", "satellite": "diamond"}
_UNDETERMINED_SYMBOL: str = "x"
_TIER_LABEL: dict[str, str] = {"core": "核心", "satellite": "衛星"}
_UNDETERMINED_LABEL: str = "未定"

# 點大小尺標（px，sizemode="area" 的視覺上限／下限）。
_MAX_MARKER_PX: float = 42.0
_MIN_MARKER_PX: float = 9.0

QUADRANT_LEGEND_CAPTION: str = (
    "🟩 左上＝低基期且體質好　🟥 右下＝高基期且體質差　"
    "⚪ 圓=核心／◆ 菱形=衛星／✕ 未定級別　"
    "點大小＝投入本金，**空心＝沒填本金（不是本金為 0）**"
)


def _num(v: Any) -> float | None:
    """能轉成有限實數就回 float，否則 None（NaN / inf / 空字串 / None 都算缺）。"""
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _tier_key(row: Mapping[str, Any]) -> str:
    t = str(row.get("tier") or row.get("policy_tier") or "").strip().lower()
    return t if t in _TIER_SYMBOL else ""


def split_placeable(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[list[dict], list[str]]:
    """切成「畫得出來的點」與「無法定位的檔名」。

    無法定位 = `sigma_rank` 或 `score_4d` 任一缺（None / NaN / 非數）。
    這些點**不畫**，但名字一定回傳給呼叫端印出來（§1：不得靜默消失）。
    """
    placeable: list[dict] = []
    unplaceable: list[str] = []
    for raw in rows or []:
        row = raw or {}
        name = str(row.get("name") or row.get("fund_code") or "（未命名）")
        x = _num(row.get("sigma_rank"))
        y = _num(row.get("score_4d"))
        if x is None or y is None:
            unplaceable.append(name)
            continue
        amt = _num(row.get("invest_twd"))
        placeable.append({
            "name": name,
            "x": x,
            "y": y,
            # 0 與 None 一律視為「沒填本金」：0 元的持倉不是持倉。
            "amount": (amt if (amt is not None and amt > 0) else None),
            "grade": row.get("grade_4d", row.get("grade")),
            "tier": _tier_key(row),
        })
    return placeable, unplaceable


def _marker_sizes(points: Sequence[Mapping[str, Any]]) -> tuple[list[float], float]:
    """回傳 (size 陣列, sizeref)。沒填本金 → 固定最小尺寸。"""
    amounts = [p["amount"] for p in points if p["amount"] is not None]
    top = max(amounts) if amounts else 0.0
    # sizemode="area"：sizeref = 2*max/ (max_px**2)
    sizeref = (2.0 * top / (_MAX_MARKER_PX ** 2)) if top > 0 else 1.0
    floor_area = sizeref * (_MIN_MARKER_PX ** 2) / 2.0
    sizes = [(p["amount"] if p["amount"] is not None else floor_area) for p in points]
    return sizes, sizeref


def build_health_quadrant_figure(
    rows: Sequence[Mapping[str, Any]],
    *,
    grade_levels: Mapping[str, str] | None = None,
) -> tuple[go.Figure, list[str], int]:
    """建圖。回傳 `(fig, unplaceable_names, n_missing_amount)`。

    `grade_levels` : `{"A": "ok", ...}`。不傳 → 直接餵 `status_color(grade)`
                     （A/B/C/D 不是它的別名 → ⬜ 灰，誠實而非猜測）。
    """
    points, unplaceable = split_placeable(rows)
    n_missing_amount = sum(1 for p in points if p["amount"] is None)

    xs = [p["x"] for p in points]
    if xs:
        lo, hi = min(min(xs), SIGMA_SPLIT), max(max(xs), SIGMA_SPLIT)
        pad = max((hi - lo) * 0.12, 0.5)
        x_range = (lo - pad, hi + pad)
    else:
        # 沒有任何可定位的點：仍畫出座標系與象限，讓「一檔都定位不了」被看見。
        x_range = (SIGMA_SPLIT - 2.0, SIGMA_SPLIT + 2.0)

    fig = go.Figure()

    # ── 象限底色：半透明一律走 plotly 原生 opacity=，不寫 rgba 色字串 ──
    y0, y1 = SCORE_AXIS_RANGE
    _quadrants = (
        (x_range[0], SIGMA_SPLIT, SCORE_SPLIT, y1, BG_DARK_GREEN_1),   # 左上：低基期+高分
        (SIGMA_SPLIT, x_range[1], y0, SCORE_SPLIT, BG_DARK_RED_2),     # 右下：高基期+低分
        (x_range[0], SIGMA_SPLIT, y0, SCORE_SPLIT, BG_DARK_NAVY_4),    # 左下
        (SIGMA_SPLIT, x_range[1], SCORE_SPLIT, y1, BG_DARK_NAVY_4),    # 右上
    )
    for qx0, qx1, qy0, qy1, color in _quadrants:
        fig.add_shape(type="rect", x0=qx0, x1=qx1, y0=qy0, y1=qy1,
                      fillcolor=color, opacity=0.55, line_width=0, layer="below")

    fig.add_vline(x=SIGMA_SPLIT, line_color=GH_BORDER, line_dash="dash", line_width=1)
    fig.add_hline(y=SCORE_SPLIT, line_color=GH_BORDER, line_dash="dash", line_width=1)

    if points:
        sizes, sizeref = _marker_sizes(points)
        by_tier: dict[str, list[int]] = {}
        for i, p in enumerate(points):
            by_tier.setdefault(p["tier"], []).append(i)

        for tier, idxs in sorted(by_tier.items()):
            base_symbol = _TIER_SYMBOL.get(tier, _UNDETERMINED_SYMBOL)
            label = _TIER_LABEL.get(tier, _UNDETERMINED_LABEL)
            colors, symbols, texts, customs = [], [], [], []
            for i in idxs:
                p = points[i]
                lvl = (grade_levels or {}).get(str(p["grade"]).strip(), p["grade"])
                colors.append(status_color(lvl).hex)
                # 沒填本金 → 空心（`-open`），視覺上與「金額很小」區分開。
                symbols.append(base_symbol if p["amount"] is not None
                               else f"{base_symbol}-open")
                texts.append(p["name"])
                customs.append([
                    ("—" if p["grade"] is None else str(p["grade"])),
                    ("未填本金" if p["amount"] is None else f"{p['amount']:,.0f} TWD"),
                ])
            fig.add_trace(go.Scatter(
                x=[points[i]["x"] for i in idxs],
                y=[points[i]["y"] for i in idxs],
                mode="markers",
                name=label,
                text=texts,
                customdata=customs,
                marker=dict(
                    size=[sizes[i] for i in idxs],
                    sizemode="area", sizeref=sizeref, sizemin=_MIN_MARKER_PX / 2.0,
                    color=colors,
                    # 沒填本金的點在這裡變成空心（`*-open`）—— 與「金額很小」分辨開。
                    symbol=symbols,
                    line=dict(width=1, color=GH_BORDER),
                ),
                hovertemplate=("%{text}<br>σ位階 %{x:.2f}｜4D %{y:.0f}"
                               "<br>評等 %{customdata[0]}｜%{customdata[1]}<extra></extra>"),
            ))

    apply_dark_template(fig, height="tall", x_unified=False, legend=bool(points))
    fig.update_xaxes(title=dict(text="σ 位階（負 = 低基期）",
                                font=dict(color=GH_FG_MUTED, size=11)),
                     range=list(x_range))
    fig.update_yaxes(title=dict(text="4D Score", font=dict(color=GH_FG_MUTED, size=11)),
                     range=list(SCORE_AXIS_RANGE))
    return fig, unplaceable, n_missing_amount


def render_health_quadrant_scatter(
    rows: Sequence[Mapping[str, Any]],
    *,
    grade_levels: Mapping[str, str] | None = None,
) -> None:
    """薄殼：畫圖 + **強制**印出無法定位清單與沒填本金腳註。"""
    import streamlit as st  # lazy

    fig, unplaceable, n_missing_amount = build_health_quadrant_figure(
        rows, grade_levels=grade_levels)
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
    st.caption(QUADRANT_LEGEND_CAPTION)
    if unplaceable:
        # §1：不得靜默消失。名字一定要印出來。
        st.caption(f"⬜ {len(unplaceable)} 檔無法定位（缺 σ 位階或 4D Score，未畫在圖上）："
                   + "、".join(unplaceable))
    if n_missing_amount:
        st.caption(f"⬜ {n_missing_amount} 檔以**空心最小點**呈現：未填投入本金，"
                   "**不是本金為 0**；點大小無法反映其實際部位。")
