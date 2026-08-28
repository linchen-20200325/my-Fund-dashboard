"""ui/components/nav_sigma_channel.py — 淨值走勢 + HWM σ 位階通道（UI3b）。

一句話：**把「現在的淨值站在歷史高點的下方幾個 σ」畫成通道**，
讓「跌了 12%」變成「在 -2σ 區」這種跨檔可比的說法。

⚠️ 本元件**絕不自行實作 σ**
---------------------------
σ 的定義（HWM、固定 `lookback` 年化、σ≈0 的處置）住在
`services/precision_service.calc_hwm_sigma_levels`，那裡有一段用血換來的註解
（v19.482 稽核 H5：`sqrt(len(s))` vs `sqrt(lookback)` 會系統性把建議導向短歷史檔）。
本元件**只吃它的原樣回傳**，一個乘除都不做。自己算一次 = 製造第二份 σ SSOT。

⚠️ 第一行就檢查 `"error" in levels`（全站既有契約鐵則）
------------------------------------------------------
`calc_hwm_sigma_levels` 的失敗回傳是 `{"error": str}`，**不是拋例外、也不是回 0**。
全站 caller 都先看 `"error" in r`。本元件同樣。

⚠️ **σ≈0 絕不可當成 0 畫**（本元件最重要的一條）
------------------------------------------------
`error == "NAV 無波動(σ≈0),無法定位階"` 的意思是「這檔淨值完全不動」——
可能已停售／清算／剛成立填平值。**舊版曾把它當 `sigma_rank = 0.0` 回傳，
而 0.0 ≥ -0.5 會一路被 `services/rotation.classify_base` 判成 "high"（🔴 高基期、偏貴）
並列進賣出候選** —— 一檔已經停售、不動如山的基金，被系統寫成「太貴了，賣掉」。
本元件在這個 mode 下**只畫水平的真實 NAV 線 + 明講原因**，一條 σ 線都不畫。

§1 Fail Loud 的其餘邊界（逐條）
------------------------------
| 情況 | 做法 |
|---|---|
| NAV 只有 1 筆 | `not_ready` —— **不畫單點，也不畫水平線**。單點連成的水平線＝**假地平線** |
| NAV < 20 點 | `not_ready` —— 連折線都不畫（點太少的折線會被當成趨勢讀） |
| `levels` 有 error 且為「資料不足／報酬率序列不足」 | 只畫 NAV 折線，**一條 σ 線都不畫** + caption 說明點數不足 |
| `levels` 有 error 且為 σ≈0 | 畫水平 NAV 線 + 明講「淨值完全不動（可能已停售／清算／剛成立）→ 無 σ 位階」 |
| 週末／假日缺值 | `connectgaps=False` —— **絕不 ffill**。基金 NAV 為 T+1~T+3，週末無資料是**正常**，補值等於捏造交易日 |
| `dividends` 為空 | **不畫也不加 caption**（屬 ➖ 結構上不適用，不是 ⬜ 缺資料） |

純函式邊界
----------
`nav_sigma_state()` / `build_nav_sigma_figure()` 零 streamlit、零 session_state、
零 cache、零 repository/service import、零網路。
"""
from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

import plotly.graph_objects as go

from shared.colors import (
    GH_FG_MUTED,
    INFO_BLUE,
    MATERIAL_ORANGE,
    MATERIAL_RED,
    MD_BLUE_300,
    MD_GREEN_A200,
)
from ui.components.chart_factory import PLOTLY_CONFIG, apply_dark_template

# 少於這個點數，連折線都不畫（畫出來會被當趨勢讀）。
MIN_POINTS_FOR_LINE: int = 20

# 四種呈現模式。
MODE_NOT_READY: str = "not_ready"      # 連折線都不畫
MODE_FLAT: str = "flat"                # σ≈0：只畫真實（水平的）NAV 線
MODE_LINE_ONLY: str = "line_only"      # 有 NAV，但 σ 算不出來
MODE_FULL: str = "full"                # NAV + σ 通道

# σ 帶狀填色的透明度：一律走 plotly 原生 opacity=，**不寫 rgba 色字串**。
_BAND_OPACITY: float = 0.06

_FLAT_CAPTION: str = (
    "本檔淨值完全不動（可能已停售／清算／剛成立）→ **無 σ 位階**。"
    "此處刻意不畫任何 σ 線：把「不動」當成 0σ 會讓它被判成「高基期、偏貴」而列入賣出候選。"
)


def _valid_points(series: Any) -> int:
    """有效（非 NaN／非 None）觀測數。缺值不算點 —— 週末的空格不是一天的淨值。"""
    if series is None:
        return 0
    try:
        vals = list(series.values)          # pandas Series
    except AttributeError:
        vals = list(series)
    n = 0
    for v in vals:
        if v is None:
            continue
        try:
            if math.isnan(float(v)):
                continue
        except (TypeError, ValueError):
            continue
        n += 1
    return n


def _is_flat_error(err: str) -> bool:
    """是不是「σ≈0 / NAV 無波動」那一種 error（≠ 資料不足）。"""
    e = str(err)
    return ("無波動" in e) or ("σ≈0" in e) or ("σ ≈ 0" in e)


def nav_sigma_state(series: Any, levels: Mapping[str, Any] | None) -> tuple[str, str]:
    """回傳 `(mode, message)`。**不畫圖**，讓「該畫什麼」可以被單獨測試。

    檢查順序是刻意的：先看 NAV 夠不夠畫，再看 σ 算不算得出來。
    """
    n = _valid_points(series)
    if n == 0:
        return MODE_NOT_READY, "尚無淨值資料"
    if n == 1:
        # 單點連成的水平線＝假地平線（§1）。寧可什麼都不畫。
        return MODE_NOT_READY, "只有 1 筆淨值 —— 單點無法構成走勢（畫成水平線會是假地平線）"
    if n < MIN_POINTS_FOR_LINE:
        return MODE_NOT_READY, (
            f"淨值僅 {n} 筆（少於 {MIN_POINTS_FOR_LINE} 筆）—— 點數太少，"
            "折線會被誤讀成趨勢，故不繪製")

    if not levels:
        return MODE_LINE_ONLY, "未取得 σ 位階結果 —— 只畫淨值走勢，不畫 σ 通道"
    # 全站既有契約：先檢查 error，再取值。
    if "error" in levels:
        err = str(levels.get("error") or "")
        if _is_flat_error(err):
            return MODE_FLAT, _FLAT_CAPTION
        return MODE_LINE_ONLY, (
            f"σ 位階無法計算（{err}）—— 只畫淨值走勢，不畫 σ 通道。"
            "此為歷史點數不足，重跑不會改變結果。")
    return MODE_FULL, ""


def build_nav_sigma_figure(
    series: Any,
    levels: Mapping[str, Any] | None,
    dividends: Sequence[Any] | None = None,
) -> go.Figure | None:
    """建圖。`mode == not_ready` → 回 `None`（呼叫端走 `not_ready()`，不畫空圖）。"""
    mode, _msg = nav_sigma_state(series, levels)
    if mode == MODE_NOT_READY:
        return None

    x = list(getattr(series, "index", range(len(list(series)))))
    try:
        y = list(series.values)
    except AttributeError:
        y = list(series)

    fig = go.Figure()

    # ── σ 通道帶狀填色（僅 full 模式）：opacity= 為 plotly 原生參數，不寫 rgba 字串 ──
    if mode == MODE_FULL:
        hwm = float(levels["hwm"])
        l1, l2, l3 = (float(levels["level_1s"]), float(levels["level_2s"]),
                      float(levels["level_3s"]))
        for lo, hi, color in ((l1, hwm, MD_GREEN_A200),
                              (l2, l1, MATERIAL_ORANGE),
                              (l3, l2, MATERIAL_RED)):
            fig.add_hrect(y0=lo, y1=hi, fillcolor=color, opacity=_BAND_OPACITY,
                          line_width=0, layer="below")
        for yv, color, name in ((hwm, GH_FG_MUTED, "HWM"),
                                (l1, MD_GREEN_A200, "-1σ"),
                                (l2, MATERIAL_ORANGE, "-2σ"),
                                (l3, MATERIAL_RED, "-3σ")):
            fig.add_hline(y=yv, line_color=color, line_dash="dot", line_width=1,
                          annotation_text=name, annotation_position="right",
                          annotation_font=dict(color=color, size=10))

    fig.add_trace(go.Scatter(
        x=x, y=y, mode="lines", name="淨值",
        line=dict(color=INFO_BLUE, width=2),
        # §1：週末／假日缺值留缺口。**絕不 ffill** —— 基金 NAV 為 T+1~T+3，
        # 補值等於捏造出不存在的交易日淨值。
        connectgaps=False,
        hovertemplate="%{x}｜%{y:.4f}<extra></extra>",
    ))

    # 配息除息日標記。空 → 什麼都不加（➖ 結構上不適用，不是 ⬜ 缺資料）。
    div_list = [d for d in (dividends or []) if d is not None]
    if div_list:
        fig.add_trace(go.Scatter(
            x=div_list, y=[None] * len(div_list), mode="markers",
            name="除息日", marker=dict(color=MD_BLUE_300, symbol="triangle-up", size=9),
            hovertemplate="除息日 %{x}<extra></extra>",
        ))
        for d in div_list:
            fig.add_vline(x=d, line_color=MD_BLUE_300, line_dash="dot", line_width=1)

    apply_dark_template(fig, height="tall", legend=(mode == MODE_FULL or bool(div_list)))
    return fig


def render_nav_sigma_channel(
    series: Any,
    levels: Mapping[str, Any] | None,
    dividends: Sequence[Any] | None = None,
    *,
    where: str = "🩺 基金健診 → 載入淨值",
) -> None:
    """薄殼：三態分流 + 畫圖 + 強制 caption。"""
    import streamlit as st  # lazy

    from ui.helpers.render_state import not_ready

    mode, message = nav_sigma_state(series, levels)
    if mode == MODE_NOT_READY:
        not_ready(message, where=where)
        return
    fig = build_nav_sigma_figure(series, levels, dividends)
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
    if message:
        st.caption(f"⬜ {message}")
