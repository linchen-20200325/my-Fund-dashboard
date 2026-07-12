# -*- coding: utf-8 -*-
"""v19.350 — Tab5 資料診斷分類分組純函式回歸鎖（user 要求「參考台股」）。

三個最容易出錯的輸入(§6)：
1. 空 registry → 五類全 loaded=False（不炸、⚪ 提示可渲染）
2. 未知前綴的 key → 收進「其他」群組（§1：不讓已登記資料無聲消失）
3. 非 dict 值 / 缺 fresh_icon → 跳過 / 計入 ⚪，rollup 不炸
"""
from __future__ import annotations

from ui.helpers.io.registry_classify import (
    DIAG_CATEGORIES,
    classify_registry,
    rollup_caption,
)


def _row(icon, label="x", source="s", freq="monthly"):
    return {"label": label, "source": source, "freq": freq,
            "latest_date": "2026-07-01", "count": 3, "fresh_icon": icon,
            "fresh_label": "L", "fresh_color": "#fff"}


class TestClassify:
    def test_empty_registry_all_categories_unloaded(self):
        groups = classify_registry({})
        # 至少涵蓋 5 個已知類別，全部 loaded=False
        assert len(groups) == len(DIAG_CATEGORIES)
        assert all(not g["loaded"] for g in groups)
        assert all(g["rollup"] == {"🔴": 0, "🟡": 0, "🟢": 0, "⚪": 0}
                   for g in groups)

    def test_grouping_and_rollup(self):
        reg = {
            "總經_VIX":  _row("🟢"),
            "總經_PMI":  _row("🔴"),
            "總經_CPI":  _row("🟡"),
            "雷達_vix_level": _row("🟢", freq="daily"),
            "新聞_國際財經RSS": _row("🟢", freq="daily"),
        }
        groups = {g["prefix"]: g for g in classify_registry(reg)}
        assert groups["總經"]["loaded"] is True
        assert groups["總經"]["rollup"] == {"🔴": 1, "🟡": 1, "🟢": 1, "⚪": 0}
        # 排序：紅先於黃先於綠
        icons = [r["fresh_icon"] for r in groups["總經"]["rows"]]
        assert icons == ["🔴", "🟡", "🟢"]
        assert groups["雷達"]["loaded"] and groups["新聞"]["loaded"]
        assert groups["基金"]["loaded"] is False   # 未載入
        assert groups["組合"]["loaded"] is False

    def test_unknown_prefix_goes_to_other(self):
        reg = {"殭屍_XXX": _row("🟢")}
        groups = classify_registry(reg)
        other = [g for g in groups if g["prefix"] == "其他"]
        assert other, "未知前綴須收進『其他』群組，不得消失（§1）"
        assert other[0]["rows"][0]["key"] == "殭屍_XXX"

    def test_non_dict_and_missing_icon_no_crash(self):
        reg = {
            "總經_A": _row("🟢"),
            "總經_B": {"label": "no-icon"},        # 缺 fresh_icon → 計入 ⚪
            "總經_C": "not-a-dict",                # 非 dict → 跳過
        }
        g = {x["prefix"]: x for x in classify_registry(reg)}["總經"]
        assert g["rollup"]["🟢"] == 1 and g["rollup"]["⚪"] == 1
        assert len(g["rows"]) == 2   # 非 dict 的 C 被跳過

    def test_key_column_injected(self):
        g = {x["prefix"]: x for x in classify_registry({"總經_VIX": _row("🟢")})}["總經"]
        assert g["rows"][0]["key"] == "總經_VIX"   # 渲染端靠 key 查 _reg_filtered


class TestRollupCaption:
    def test_zero_lights_omitted(self):
        assert rollup_caption({"🔴": 0, "🟡": 0, "🟢": 3, "⚪": 0}) == "🟢3"
        assert rollup_caption({"🔴": 2, "🟡": 1, "🟢": 3, "⚪": 0}) == "🟢3　🟡1　🔴2"
        assert rollup_caption({"🔴": 0, "🟡": 0, "🟢": 0, "⚪": 0}) == "—"


def test_prefix_split_first_underscore_only():
    """基金_元大台灣50_淨值 這種多段 key 前綴只取第一段（基金）。"""
    reg = {"基金_元大台灣50_淨值": _row("🟢", freq="nav"),
           "基金_元大台灣50_配息": _row("🟡", freq="monthly")}
    g = {x["prefix"]: x for x in classify_registry(reg)}
    assert "基金" in g and g["基金"]["rollup"] == {"🔴": 0, "🟡": 1, "🟢": 1, "⚪": 0}
