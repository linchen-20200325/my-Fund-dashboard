# -*- coding: utf-8 -*-
"""🌍 市場與趨勢頁的折線圖元件（純函式；零 streamlit import、零網路、零舊樹 import）。

BL-0516 批 1（客戶裁示 C，`DEC-2026-10-27-41`；藍圖 `MK-7`、`SH-7` 的圖表元件）。
畫圖本身交給 `st.vega_lite_chart`（vega-lite 規格是一個 dict，所以本檔可以在沒有 streamlit 的環境完整測試）；
選 vega-lite 而不選 plotly 的依據見 PR 說明：streamlit 1.59 內建 vega-lite 前端，不必另載 plotly.js；
規格是純資料，期間切換只重送一份小 dict，不重算任何東西。

本檔守的規則（每一條都有測試）：
- **缺資料不補**：序列裡 `value_num` 是 None／NaN 的點保留為 null → 折線在那裡**斷開**，不補 0、不 ffill、不內插。
- **沒有的資料不畫**：全空 → 空狀態（`status == "empty"`），不畫空軸假裝有圖。
- **期間不足就說不足**：選的期間比序列涵蓋還長 → `status == "insufficient"`，**不**縮短區間冒充（客戶 2026-10-27 派工）。
  判定只有一條：最早一筆有值的觀測日**晚於**視窗起點 → 不足。視窗以「最後一筆有值的觀測日」往回推，不以今天推。
- **已知限制**：視窗起點落在週末／假日時，最早有值觀測日必晚於起點而被判不足（不另發明容忍規則）；
  本頁 VIX／TAIEX／S&P 500 取 5y（`market_view` 的 `*_RANGE`），殖利率取最新 1500 筆（`FRED_VIEW_OBSERVATION_LIMIT`），
  3Y 在來源涵蓋足夠時可用（B 線 `vol_index` 仍是預設 2y，不在本圖）；來源實際回得比預期短時才會判不足。
  ~~目前 L1 抓 2y，3Y 本來就不足~~（BL-0517 前為真，現已不成立；有意識的更正，不是漏刪）。正式路徑 L1 已 dropna，缺的日子是沒有點、折線直接連過，
  只有明確帶 None／NaN 的點才會斷線。
- **沒有預測線、目標價線、箭頭**：規格裡只有「實際觀測」一條折線＋觀測點＋最後一點的直接標籤。
- **不靠顏色分辨**：最後一點有文字標籤（`名稱 值`）、觀測點有形狀；單一序列時顏色只是裝飾。
- **不自創任何門檻**：新鮮度判定住在 `ui_v2/mkt/logic.py`（`delay_days`／`freshness_badge_text`），本檔不碰。
"""

from __future__ import annotations

import math
from datetime import date, timedelta

# 期間按鈕（客戶裁示：3M／6M／1Y／3Y；預設 1Y）。月數是定義，不是門檻。
PERIODS = ("3M", "6M", "1Y", "3Y")
PERIOD_MONTHS = {"3M": 3, "6M": 6, "1Y": 12, "3Y": 36}
DEFAULT_PERIOD = "1Y"

STATUS_OK = "ok"
STATUS_EMPTY = "empty"
STATUS_INSUFFICIENT = "insufficient"

# 固定文案（面向使用者；總管擬，待覆核）。
TEXT_INSUFFICIENT = "資料不足以呈現此期間"
TEXT_EMPTY = "⬜ 資料未取得，無法繪圖"


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _clean(points) -> list:
    """排序並把無效值（None／NaN／非數字）一律變成 None（保留這一天，折線在此斷開）。"""
    cleaned = [{"obs_date": p["obs_date"], "value_num": p["value_num"] if _is_number(p.get("value_num")) else None}
               for p in points]
    return sorted(cleaned, key=lambda p: p["obs_date"])


def months_back(day: date, months: int) -> date:
    """往回推整數個日曆月；目標月沒有該日（例 3/31 回推 1 個月）取該月最後一天。"""
    total = day.year * 12 + (day.month - 1) - months
    year, month = divmod(total, 12)
    month += 1
    # 該月最後一天
    next_first = date(year + (month == 12), (month % 12) + 1, 1)
    last_day = (next_first - timedelta(days=1)).day
    return date(year, month, min(day.day, last_day))


def slice_period(points, period: str) -> dict:
    """依期間切片。回傳 `{"status", "period", "points", "window_start", "window_end", "first_obs", "last_obs"}`。

    - `points`：`[{"obs_date": "YYYY-MM-DD", "value_num": float|None}, ...]`（可無序）。
    - `status == "empty"`：沒有任何有值的點；`points` 為 []。
    - `status == "insufficient"`：最早有值的觀測日晚於視窗起點；`points` 為 []（不縮短冒充）。
    - `status == "ok"`：`points` 為視窗內全部點（含 None 的點，供斷線）。
    """
    if period not in PERIOD_MONTHS:
        raise ValueError(f"period 須為 {PERIODS} 之一：{period!r}")
    cleaned = _clean(points)
    valued = [p for p in cleaned if p["value_num"] is not None]
    base = {"period": period, "points": [], "window_start": None, "window_end": None,
            "first_obs": None, "last_obs": None}
    if not valued:
        return {**base, "status": STATUS_EMPTY}
    first_obs, last_obs = valued[0]["obs_date"], valued[-1]["obs_date"]
    start = months_back(date.fromisoformat(last_obs), PERIOD_MONTHS[period]).isoformat()
    base.update(window_start=start, window_end=last_obs, first_obs=first_obs, last_obs=last_obs)
    if first_obs > start:
        return {**base, "status": STATUS_INSUFFICIENT}
    window = [p for p in cleaned if start <= p["obs_date"] <= last_obs]
    return {**base, "status": STATUS_OK, "points": window}


def availability(points) -> dict:
    """每個期間按鈕能不能畫：`{period: bool}`。供按鈕標示「資料不足」（不是縮短區間）。"""
    return {p: slice_period(points, p)["status"] == STATUS_OK for p in PERIODS}


def build_spec(points, *, label: str, value_title: str, color: str, description: str, height: int = 220) -> dict:
    """vega-lite 規格（dict）。`points` 必須是 `slice_period` 交回的 `status == "ok"` 的 `points`。

    只有一條「實際觀測」折線＋觀測點＋最後一個有值點的直接標籤；沒有預測線、目標價線、箭頭。
    折線 `invalid: break-paths-filter-domains`：null 值處斷線，不補零、不內插。
    """
    if not points:
        raise ValueError("沒有點不該畫圖（呼叫端應先看 slice_period 的 status）")
    values = [{"date": p["obs_date"], "value": p["value_num"]} for p in points]
    last = [v for v in values if v["value"] is not None][-1]
    x_enc = {"field": "date", "type": "temporal", "title": None,
             "axis": {"format": "%Y-%m", "labelOverlap": True, "grid": False}}
    y_enc = {"field": "value", "type": "quantitative", "title": value_title,
             "scale": {"zero": False}}
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v6.json",
        "description": description,
        "width": "container",
        "height": height,
        "data": {"values": values},
        "layer": [
            {"mark": {"type": "line", "color": color, "strokeWidth": 2,
                      "invalid": "break-paths-filter-domains"},
             "encoding": {"x": x_enc, "y": y_enc}},
            {"mark": {"type": "point", "color": color, "filled": True, "size": 12, "shape": "circle"},
             "encoding": {"x": x_enc, "y": y_enc}},
            {"data": {"values": [{"date": last["date"], "value": last["value"],
                                  "text": f"{label} {0.0 if abs(last['value']) < 0.005 else last['value']:.2f}"}]},
             "mark": {"type": "text", "align": "right", "dx": -6, "dy": -10, "fontSize": 12,
                      "color": color},
             "encoding": {"x": {"field": "date", "type": "temporal"},
                          "y": {"field": "value", "type": "quantitative"},
                          "text": {"field": "text"}}},
        ],
        "config": {"view": {"stroke": None}},
    }


def spec_strings(spec: dict) -> list:
    """規格裡所有面向使用者的字串（供禁詞／箭頭／目標價掃描）。"""
    out = []

    def walk(node):
        if isinstance(node, str):
            out.append(node)
        elif isinstance(node, dict):
            for key, value in node.items():
                if key == "$schema":
                    continue
                walk(value)
        elif isinstance(node, (list, tuple)):
            for value in node:
                walk(value)

    walk(spec)
    return out
