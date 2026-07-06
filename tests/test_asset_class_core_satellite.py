"""v19.327 — 基金「核心 / 衛星資產」分類 SSOT 測試。

守住兩層邏輯 + 來源標記:
1. 集中/主題型類別 → 衛星(覆蓋 3-3-3)
2. 3-3-3 通過 → 核心
3. 廣泛分散型類別 → 核心
4. 皆無法判 → 待定(不亂扣)
"""
from __future__ import annotations

import pytest

from services.health.asset_class import (
    classify_by_category,
    classify_core_satellite,
)


# ── classify_by_category ─────────────────────────────────
@pytest.mark.parametrize("cat,expect", [
    ("台灣智慧型股票", "衛星"),
    ("全球高收益債券", "衛星"),      # 高收益覆蓋全球
    ("新興市場債", "衛星"),
    ("大中華股票", "衛星"),
    ("生技醫療", "衛星"),
    ("全球股票", "核心"),
    ("多重收益平衡", "核心"),
    ("投資等級債券", "核心"),
    ("環球債券組合", "核心"),
    ("美國成長", "衛星"),            # v19.328 user:成長型追報酬 → 衛星
    ("科技成長", "衛星"),
    ("價值型股票", None),           # 純風格(非成長)無關鍵字 → 無法判
    ("", None),
    (None, None),
])
def test_classify_by_category(cat, expect):
    assert classify_by_category(cat) == expect


def test_growth_style_is_satellite():
    """v19.328 user 指定:美國成長 = 衛星(成長型追報酬)。"""
    r = classify_core_satellite("美國成長", passed_333=None)
    assert r["label"] == "衛星" and r["source"] == "類別"


# ── classify_core_satellite 兩層 + 來源 ───────────────────
def test_satellite_category_overrides_333_pass():
    """集中型即使 3-3-3 通過,角色仍是衛星(來源:類別)。"""
    r = classify_core_satellite("大中華股票", passed_333=True)
    assert r["label"] == "衛星" and r["source"] == "類別"


def test_333_pass_no_category_is_core_by_333():
    r = classify_core_satellite("", passed_333=True)
    assert r["label"] == "核心" and r["source"] == "3-3-3"


def test_broad_category_no_333_is_core_by_category():
    """3-3-3 抓不到(None)但廣泛型 → 核心(來源:類別)—— 補涵蓋率核心案例。"""
    r = classify_core_satellite("全球股票", passed_333=None)
    assert r["label"] == "核心" and r["source"] == "類別"


def test_broad_category_333_fail_still_core():
    """年輕廣泛型(3-3-3 False,成立<3年)不誤判衛星,由類別歸核心。"""
    r = classify_core_satellite("投資等級債", passed_333=False)
    assert r["label"] == "核心" and r["source"] == "類別"


@pytest.mark.parametrize("cat,p333", [
    ("價值型股票", None),   # 無關鍵字類別 + 無 3-3-3
    ("", None),
    ("價值型股票", False),  # 無關鍵字 + 未達 3-3-3
])
def test_undetermined_when_no_signal(cat, p333):
    r = classify_core_satellite(cat, passed_333=p333)
    assert r["label"] == "待定" and r["source"] is None


def test_display_and_emoji_shape():
    r = classify_core_satellite("全球股票", passed_333=None)
    assert r["display"].endswith("核心")
    assert r["emoji"] == "🟦"


# ── build_health_analysis_row 整合 ───────────────────────
def test_health_row_has_core_satellite_fields():
    from services.health.report import build_health_analysis_row, HEALTH_COLUMNS
    fd = {"fund_name": "測試衛星", "moneydj_raw": {"category": "生技醫療"},
          "metrics": {}, "perf": {}}
    row = build_health_analysis_row(fd, "X")
    assert row["基金類別"] == "生技醫療"
    assert "衛星" in row["核心/衛星"]
    assert row["分類依據"] == "類別"
    # schema:三欄排在基金名後、4D Grade 前
    i_name = HEALTH_COLUMNS.index("基金名")
    i_cat = HEALTH_COLUMNS.index("基金類別")
    i_cs = HEALTH_COLUMNS.index("核心/衛星")
    i_grade = HEALTH_COLUMNS.index("4D Grade")
    assert i_name < i_cat < i_cs < i_grade


def test_health_row_missing_category_is_undetermined():
    from services.health.report import build_health_analysis_row
    fd = {"fund_name": "無類別", "moneydj_raw": {}, "metrics": {}, "perf": {}}
    row = build_health_analysis_row(fd, "X")
    assert row["基金類別"] == "—"
    assert "待定" in row["核心/衛星"]
