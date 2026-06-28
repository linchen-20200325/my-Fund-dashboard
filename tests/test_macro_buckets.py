"""test_macro_buckets.py — 五桶危險門檻 SSOT 註冊表測試 (v19.144)

對齊 Stock v18.284 同名測試結構。重點:
1. drift guard — 鏡像值必須 == macro_repository.MACRO_THRESHOLDS(§3.3 防漂移)
2. 註冊表結構完整性(bucket 合法 / key 唯一 / 紅黃線方向自洽)
3. import 既有 SSOT 常數的串接(SAHM/CFNAI)

v19.218 P0-3-#9 拔毒:`classify_danger` / `specs_for_bucket` /
`aggregate_level` / `fmt_value` 4 fn production 0 caller 已移除,
連動清 7 個 test。
"""
import pytest

from shared import macro_buckets as mb
from repositories.macro_repository import MACRO_THRESHOLDS


# ──────────────────────────────────────────────────────────
# 1. drift guard:鏡像值 == L1 SSOT 源
# ──────────────────────────────────────────────────────────
def test_mirror_matches_macro_repository():
    """鏡像於本檔的 _VIX_*/_CPI_*/_PMI_*/_HY_*/_US10Y_*/_M2_* 必須與
    repositories.macro_repository.MACRO_THRESHOLDS 完全一致,任一邊改動 CI 立擋。"""
    assert mb._VIX_YELLOW == MACRO_THRESHOLDS["VIX"]["yellow_above"]
    assert mb._VIX_RED == MACRO_THRESHOLDS["VIX"]["red_above"]
    assert mb._CPI_YELLOW == MACRO_THRESHOLDS["CPI"]["yellow_above"]
    assert mb._CPI_RED == MACRO_THRESHOLDS["CPI"]["red_above"]
    assert mb._PMI_YELLOW == MACRO_THRESHOLDS["PMI"]["yellow_below"]
    assert mb._PMI_RED == MACRO_THRESHOLDS["PMI"]["red_below"]
    # HY_SPREAD schema: {"green_below": 4.0, "yellow_below": 6.0, "red_above": 6.0}
    # 語意:< 4 green / 4-6 yellow / > 6 red。對映本 registry high_bad:
    #   yellow line = 綠/黃邊界 = MACRO_THRESHOLDS green_below(=4.0)
    #   red line    = 黃/紅邊界 = MACRO_THRESHOLDS red_above(=6.0)
    # (yellow_below=6.0 是「黃/紅邊界」舊命名,與 red_above 同值,非真黃線)
    assert mb._HY_YELLOW == MACRO_THRESHOLDS["HY_SPREAD"]["green_below"]
    assert mb._HY_RED == MACRO_THRESHOLDS["HY_SPREAD"]["red_above"]
    assert mb._US10Y_YELLOW == MACRO_THRESHOLDS["US10Y"]["yellow_above"]
    assert mb._US10Y_RED == MACRO_THRESHOLDS["US10Y"]["red_above"]
    assert mb._M2_RED == MACRO_THRESHOLDS["M2_YOY"]["red_below"]
    assert mb._M2_GREEN == MACRO_THRESHOLDS["M2_YOY"]["green_above"]


def test_imported_ssot_constants_used():
    """SAHM / CFNAI 紅線確實 import 自 signal_thresholds(非腦補)。"""
    from shared.signal_thresholds import (
        SAHM_RECESSION_THRESHOLD, CFNAI_RECESSION_THRESHOLD,
    )
    _sahm = mb.SPECS_BY_KEY["sahm"]
    assert _sahm.red == float(SAHM_RECESSION_THRESHOLD)
    _cfnai = mb.SPECS_BY_KEY["cfnai"]
    assert _cfnai.red == float(CFNAI_RECESSION_THRESHOLD)


# ──────────────────────────────────────────────────────────
# ──────────────────────────────────────────────────────────
# 3. 註冊表結構完整性
# ──────────────────────────────────────────────────────────
def test_all_specs_valid():
    seen_keys = set()
    for s in mb.BUCKET_DANGER_SPECS:
        assert s.bucket in mb.BUCKET_ORDER, f"{s.key} bucket 非法: {s.bucket}"
        assert s.direction in ("high_bad", "low_bad", "band"), f"{s.key} direction 非法"
        assert s.key not in seen_keys, f"{s.key} 重複"
        seen_keys.add(s.key)
        assert s.source, f"{s.key} 缺 source 標註"
        if s.direction == "band":
            assert s.yellow_lo is not None and s.red_lo is not None, f"{s.key} band 缺低側線"



def test_high_bad_red_ge_yellow():
    """high_bad:red 線應 >= yellow 線;low_bad 反之。"""
    for s in mb.BUCKET_DANGER_SPECS:
        if s.direction == "high_bad":
            assert s.red >= s.yellow, f"{s.key} high_bad red<yellow"
        elif s.direction == "low_bad":
            assert s.red <= s.yellow, f"{s.key} low_bad red>yellow"


def test_bucket_order_includes_news():
    """v19.144 第 5 桶 📰 新聞 = 與 Stock 五桶對齊但取代 Stock 的 🧩 籌碼桶
    (Fund 視角無 TW 籌碼)。"""
    assert mb.BUCKET_ORDER == ["long", "mid", "short", "inflection", "news"]
    assert mb.BUCKET_META["news"]["emoji"] == "📰"
    assert "news_systemic" in mb.SPECS_BY_KEY


# ──────────────────────────────────────────────────────────
