# -*- coding: utf-8 -*-
"""🌍 折線圖元件 `ui_v2/mkt/chart.py` 的純函式測試（fast lane；不需要 streamlit）。

期間切片（3M／6M／1Y／3Y 邊界、資料不足）、缺段斷線不補零、全空空狀態、規格內無預測線／目標價／箭頭／方向詞。
"""

from __future__ import annotations

import pathlib
import sys
from datetime import date, timedelta

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

from ui_v2.mkt import chart, logic  # noqa: E402


def _daily(start: str, end: str, value=16.0):
    """每個日曆日一點（邊界測試用，簡化日曆）。"""
    d0, d1 = date.fromisoformat(start), date.fromisoformat(end)
    out, d = [], d0
    while d <= d1:
        out.append({"obs_date": d.isoformat(), "value_num": value})
        d += timedelta(days=1)
    return out


# ───────────────────────── 月份回推 ─────────────────────────


@pytest.mark.parametrize("day,months,expected", [
    ("2026-10-23", 3, "2026-07-23"),
    ("2026-10-23", 6, "2026-04-23"),
    ("2026-10-23", 12, "2025-10-23"),
    ("2026-10-23", 36, "2023-10-23"),
    ("2026-05-31", 3, "2026-02-28"),      # 目標月沒有 31 日 → 取該月最後一天
    ("2024-05-31", 3, "2024-02-29"),      # 閏年
    ("2026-01-15", 3, "2025-10-15"),      # 跨年
    ("2026-02-28", 12, "2025-02-28"),
])
def test_months_back(day, months, expected):
    assert chart.months_back(date.fromisoformat(day), months).isoformat() == expected


# ───────────────────────── 期間切片 ─────────────────────────


def test_期間常數與預設():
    assert chart.PERIODS == ("3M", "6M", "1Y", "3Y")
    assert chart.DEFAULT_PERIOD == "1Y"


@pytest.mark.parametrize("period,start", [("3M", "2026-07-23"), ("6M", "2026-04-23"),
                                          ("1Y", "2025-10-23"), ("3Y", "2023-10-23")])
def test_起點剛好等於視窗起點_可畫_視窗以最後觀測日往回推(period, start):
    points = _daily(start, "2026-10-23")
    sliced = chart.slice_period(points, period)
    assert sliced["status"] == chart.STATUS_OK
    assert sliced["window_start"] == start and sliced["window_end"] == "2026-10-23"
    assert sliced["points"][0]["obs_date"] == start and sliced["points"][-1]["obs_date"] == "2026-10-23"


@pytest.mark.parametrize("period,start", [("3M", "2026-07-23"), ("6M", "2026-04-23"),
                                          ("1Y", "2025-10-23"), ("3Y", "2023-10-23")])
def test_起點晚視窗起點一天_資料不足_不縮短冒充(period, start):
    first = (date.fromisoformat(start) + timedelta(days=1)).isoformat()
    sliced = chart.slice_period(_daily(first, "2026-10-23"), period)
    assert sliced["status"] == chart.STATUS_INSUFFICIENT
    assert sliced["points"] == []                      # 沒有「縮短版」
    assert chart.TEXT_INSUFFICIENT == "資料不足以呈現此期間"


def test_兩年資料_3Y不足_其餘可畫():
    points = _daily("2024-10-24", "2026-10-23")
    got = chart.availability(points)
    assert got == {"3M": True, "6M": True, "1Y": True, "3Y": False}


def test_視窗只含起點到最後觀測日_視窗外的舊資料不進圖():
    sliced = chart.slice_period(_daily("2023-01-01", "2026-10-23"), "3M")
    assert sliced["points"][0]["obs_date"] == "2026-07-23"
    assert len(sliced["points"]) == (date(2026, 10, 23) - date(2026, 7, 23)).days + 1


def test_無序輸入_先排序():
    points = list(reversed(_daily("2026-07-01", "2026-10-23")))
    sliced = chart.slice_period(points, "3M")
    dates = [p["obs_date"] for p in sliced["points"]]
    assert dates == sorted(dates)


def test_視窗以最後一筆有值的觀測日為準_尾端的None不當終點():
    points = _daily("2025-01-01", "2026-10-23")
    points += [{"obs_date": "2026-10-24", "value_num": None}]
    sliced = chart.slice_period(points, "1Y")
    assert sliced["window_end"] == "2026-10-23" and sliced["last_obs"] == "2026-10-23"


def test_不支援的期間_當場炸():
    with pytest.raises(ValueError):
        chart.slice_period(_daily("2026-01-01", "2026-10-23"), "5Y")


# ───────────────────────── 全空／缺段 ─────────────────────────


@pytest.mark.parametrize("points", [
    [],
    [{"obs_date": "2026-10-22", "value_num": None}],
    [{"obs_date": "2026-10-22", "value_num": float("nan")}, {"obs_date": "2026-10-23", "value_num": None}],
    [{"obs_date": "2026-10-22", "value_num": "abc"}],
])
def test_全空_空狀態_不畫圖(points):
    sliced = chart.slice_period(points, "1Y")
    assert sliced["status"] == chart.STATUS_EMPTY
    assert sliced["points"] == []
    assert all(v is False for v in chart.availability(points).values())


def test_缺段_None保留為null_規格在該處斷線_不補零不ffill():
    points = _daily("2025-06-01", "2026-10-23")
    gap = {p["obs_date"] for p in points[300:305]}
    for p in points:
        if p["obs_date"] in gap:
            p["value_num"] = None
    sliced = chart.slice_period(points, "1Y")
    assert sliced["status"] == chart.STATUS_OK
    spec = chart.build_spec(sliced["points"], label="VIX", value_title="指數點位（index）", color="#0f6b6c",
                            description="d")
    values = spec["data"]["values"]
    assert [v for v in values if v["date"] in gap] == [{"date": d, "value": None} for d in sorted(gap)]
    assert 0 not in [v["value"] for v in values] and 0.0 not in [v["value"] for v in values]
    line = spec["layer"][0]["mark"]
    assert line["type"] == "line" and line["invalid"] == "break-paths-filter-domains"
    # 缺值前後的值原樣（沒有被前值覆蓋）
    assert all(v["value"] == 16.0 for v in values if v["date"] not in gap)


def test_NaN轉成null_規格資料裡沒有NaN():
    pts = _daily("2025-06-01", "2026-10-23")
    pts[300]["value_num"] = float("nan")
    sliced = chart.slice_period(pts, "1Y")
    spec = chart.build_spec(sliced["points"], label="VIX", value_title="v", color="#000", description="d")
    import math
    assert not [v for v in spec["data"]["values"] if isinstance(v["value"], float) and math.isnan(v["value"])]
    assert [v for v in spec["data"]["values"] if v["date"] == pts[300]["obs_date"]] == [
        {"date": pts[300]["obs_date"], "value": None}]


def test_沒有點就不該畫圖_當場炸():
    with pytest.raises(ValueError):
        chart.build_spec([], label="VIX", value_title="v", color="#000", description="d")


# ───────────────────────── 規格內容：無預測、無目標價、無箭頭、非顏色線索 ─────────────────────────


def _spec():
    sliced = chart.slice_period(_daily("2025-10-23", "2026-10-23", 17.3), "1Y")
    return chart.build_spec(sliced["points"], label="VIX", value_title="指數點位（index）", color="#0f6b6c",
                            description="波動度指數近 1Y 日收盤折線圖，資料日期至 2026-10-23")


def test_規格只有實際觀測一條折線_觀測點_最後一點標籤():
    spec = _spec()
    assert [layer["mark"]["type"] for layer in spec["layer"]] == ["line", "point", "text"]
    assert spec["width"] == "container"
    for layer in spec["layer"]:       # 沒有 rule（水平／垂直參考線）、沒有 arrow、沒有 forecast
        assert layer["mark"]["type"] not in ("rule", "arrow", "trail", "area", "bar")


def test_最後一點有直接文字標籤_不靠顏色辨識():
    spec = _spec()
    text_layer = spec["layer"][2]
    assert text_layer["data"]["values"][0]["text"] == "VIX 17.30"
    assert text_layer["data"]["values"][0]["date"] == "2026-10-23"
    assert spec["layer"][1]["mark"]["shape"] == "circle"      # 觀測點有形狀


def test_規格字串無方向詞_箭頭_目標價_預測():
    strings = chart.spec_strings(_spec())
    assert strings
    assert logic.scan_forbidden(strings) == {}
    for word in ("目標價", "預測", "預估", "forecast", "target", "arrow"):
        assert not [s for s in strings if word in s.lower()], word


def test_y軸不強制從0開始_VIX不被壓扁():
    spec = _spec()
    assert spec["layer"][0]["encoding"]["y"]["scale"] == {"zero": False}


def test_chart_py不import_streamlit_也不import舊樹():
    import ast
    tree = ast.parse((_ROOT / "ui_v2" / "mkt" / "chart.py").read_text(encoding="utf-8"))
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            mods.add((node.module or "").split(".")[0])
    assert mods <= {"__future__", "math", "datetime", ""}, mods
