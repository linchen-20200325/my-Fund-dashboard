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
    COVERAGE_OK,
    COVERAGE_UNRELIABLE,
    UNDETERMINED_UNRELIABLE_PCT,
    classify_by_category,
    classify_core_satellite,
    summarize_core_satellite_allocation,
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


# ── summarize_core_satellite_allocation ──────────────────
# 2026-08-07 user 裁決:本函式**降為純資訊** —— 只算屬性分布比例 + 分類涵蓋度,
# 不再對核心佔比高低給燈號 / 行動建議(唯一真相是 Sheet policy_tier 那條線)。
def test_alloc_weighted_by_amount():
    """依投入金額加權(非等權):核心 80萬 / 衛星 20萬 → 核心 80%。"""
    r = summarize_core_satellite_allocation([
        {"label": "🟦 核心", "weight": 800_000},
        {"label": "🟠 衛星", "weight": 200_000},
    ])
    assert r["core_pct"] == 80.0 and r["satellite_pct"] == 20.0
    assert r["n_core"] == 1 and r["n_satellite"] == 1


@pytest.mark.parametrize("core_w,sat_w", [
    (62, 38),    # 舊 🟢
    (30, 70),    # 舊 🔴「衛星過重」
    (90, 10),    # 舊 🟡「偏保守」
])
def test_alloc_never_judges_core_ratio(core_w, sat_w):
    """**修正前必紅(行為衝突)** —— 舊碼對這三組會分別回 🟢 / 🔴 / 🟡。

    核心佔比高低不再產生任何評價:只要分類涵蓋足夠,一律 `COVERAGE_OK`,
    且 note 不得出現行動語氣。這是「同一頁不再出現兩個相反再平衡結論」的根。
    """
    r = summarize_core_satellite_allocation([
        {"label": "核心", "weight": core_w}, {"label": "衛星", "weight": sat_w}])
    assert r["status"] == COVERAGE_OK
    assert "message" not in r, "行動建議欄位不得復活"
    for _banned in ("衛星過重", "偏保守", "配置穩健", "目標"):
        assert _banned not in r["coverage_note"], f"coverage_note 仍帶評價字樣「{_banned}」"


def test_alloc_coverage_unreliable_when_too_many_undetermined():
    """待定超標 → 分類涵蓋不足(資料品質陳述,不是配置評價)。"""
    r = summarize_core_satellite_allocation([
        {"label": "核心", "weight": 10}, {"label": "待定", "weight": 90}])
    assert r["status"] == COVERAGE_UNRELIABLE
    assert r["undetermined_pct"] > UNDETERMINED_UNRELIABLE_PCT
    assert "待定" in r["coverage_note"]


def test_alloc_skips_nonpositive_weight():
    """weight ≤ 0 / 非數 略過,不計入分母。

    **這條同時是「模擬本金不進配置比例」的地基**:呼叫端對未填金額的基金傳 0,
    就靠這裡把它擋在分母外(見 ui/tab_fund_grp_health._render_health_3tables)。
    """
    r = summarize_core_satellite_allocation([
        {"label": "核心", "weight": 100},
        {"label": "衛星", "weight": 0},
        {"label": "衛星", "weight": "x"},
    ])
    assert r["total_weight"] == 100 and r["core_pct"] == 100.0
    assert r["n_satellite"] == 0


def test_alloc_empty_is_coverage_unreliable():
    r = summarize_core_satellite_allocation([])
    assert r["status"] == COVERAGE_UNRELIABLE and r["total_weight"] == 0.0
    assert "message" not in r


def test_target_range_constants_are_gone():
    """**修正前必紅(ImportError 反向鎖)** —— 建議核心區間常數必須真的不存在。

    只要 `CORE_TARGET_MIN_PCT` / `CORE_TARGET_MAX_PCT` 還留在模組裡,下一個人
    就會把它接回畫面,兩把尺的打架就會復發。用 `hasattr` 而非 import 失敗,
    是為了讓失敗訊息直接指出是哪個常數復活。
    """
    import services.health.asset_class as _ac
    for _name in ("CORE_TARGET_MIN_PCT", "CORE_TARGET_MAX_PCT"):
        assert not hasattr(_ac, _name), (
            f"{_name} 復活了 —— 本表已降為純資訊,不得再持有建議核心佔比")
