"""test_china_subscore.py — v19.114 China 副盤 subscore + regime

驗證:
1. 5 因子各自打分(CLI/PMI/CPI/M2/USDCNY)邊界正確
2. subscore 等權平均 + 缺項重分配(不偽 50)
3. regime 4 級 + USDCNY > 7.4 flag 獨立判讀
4. 全缺 → None / 部分缺 → 用有效項算
"""
from __future__ import annotations

import pandas as pd
import pytest

import math

from services.macro_service import (
    CHINA_MODIFIER_FLOOR,
    CHINA_MODIFIER_RANGE,
    _score_cli,
    _score_cpi,
    _score_m2,
    _score_pmi,
    _score_usdcny,
    apply_china_modifier,
    classify_china_regime,
    compute_china_subscore,
)


# ══════════════════════════════════════════════════════════════
# 1. 各因子打分邊界
# ══════════════════════════════════════════════════════════════

@pytest.mark.parametrize("v,expected", [
    (101.0, 100.0),  # 擴張
    (99.5,  50.0),   # 中性
    (98.5,  25.0),   # 收縮邊緣
    (97.0,  0.0),    # 衰退
    (None,  None),
])
def test_score_cli(v, expected):
    assert _score_cli(v) == expected


def test_score_pmi_mirrors_cli():
    """PMI proxy 與 CLI 同結構"""
    for v in (101.0, 99.5, 98.5, 97.0):
        assert _score_pmi(v) == _score_cli(v)


@pytest.mark.parametrize("v,expected", [
    (2.0,  100.0),   # 理想區
    (1.5,  100.0),   # 理想區邊緣
    (0.5,  50.0),    # 偏低
    (3.5,  50.0),    # 偏高
    (5.0,  0.0),     # 過熱
    (-1.0, 0.0),     # 通縮
    (None, None),
])
def test_score_cpi(v, expected):
    assert _score_cpi(v) == expected


@pytest.mark.parametrize("v,expected", [
    (10.0, 100.0),   # 寬鬆
    (9.0,  100.0),   # 邊界
    (7.0,  50.0),    # 中性
    (4.0,  0.0),     # 緊縮
    (None, None),
])
def test_score_m2(v, expected):
    assert _score_m2(v) == expected


@pytest.mark.parametrize("v,expected", [
    (6.5, 100.0),    # 強勢
    (7.1, 50.0),     # 中性
    (7.3, 25.0),     # 偏弱
    (7.5, 0.0),      # 大貶
    (None, None),
])
def test_score_usdcny(v, expected):
    assert _score_usdcny(v) == expected


def test_score_handles_nan():
    """NaN 與 None 對等處理"""
    nan = float("nan")
    assert _score_cli(nan) is None
    assert _score_cpi(nan) is None
    assert _score_usdcny(nan) is None


# ══════════════════════════════════════════════════════════════
# 2. compute_china_subscore
# ══════════════════════════════════════════════════════════════

def _snap(cli=None, pmi=None, cpi=None, m2=None, usdcny=None) -> dict:
    def _e(v):
        return {"value": v, "date": None, "zone": "", "source": None}
    return {
        "cli":     _e(cli),
        "pmi":     _e(pmi),
        "cpi_yoy": _e(cpi),
        "m2_yoy":  _e(m2),
        "usdcny":  _e(usdcny),
    }


def test_subscore_empty_snapshot_returns_none():
    """空 snapshot → None(§1 fail loud,不偽 50)"""
    assert compute_china_subscore({}) is None
    assert compute_china_subscore(_snap()) is None  # 5 個都 None


def test_subscore_all_green():
    """5 因子全綠 → 100"""
    out = compute_china_subscore(_snap(cli=101, pmi=101, cpi=2.0, m2=10.0, usdcny=6.8))
    assert out["score"] == 100.0
    assert out["n_available"] == 5


def test_subscore_all_red():
    """5 因子全紅 → 0"""
    out = compute_china_subscore(_snap(cli=97, pmi=97, cpi=5.5, m2=4.0, usdcny=7.5))
    assert out["score"] == 0.0
    assert out["n_available"] == 5


def test_subscore_mixed():
    """3 綠 2 紅 → (100+100+100+0+0)/5 = 60"""
    out = compute_china_subscore(_snap(cli=101, pmi=101, cpi=2.0, m2=4.0, usdcny=7.5))
    assert out["score"] == 60.0


def test_subscore_partial_missing_redistributes():
    """3 缺 2 有 → 只平均有效項(USDCNY 100 + CPI 100)/2 = 100"""
    out = compute_china_subscore(_snap(cpi=2.0, usdcny=6.8))
    assert out["score"] == 100.0
    assert out["n_available"] == 2
    assert out["factors"]["cli"]["score"] is None
    assert out["factors"]["pmi"]["score"] is None
    assert out["factors"]["m2"]["score"] is None


def test_subscore_factor_detail_complete():
    out = compute_china_subscore(_snap(cli=99.5, usdcny=7.5))
    assert out["factors"]["cli"] == {"value": 99.5, "score": 50.0}
    assert out["factors"]["usdcny"] == {"value": 7.5, "score": 0.0}
    assert out["score"] == 25.0  # (50 + 0) / 2


# ══════════════════════════════════════════════════════════════
# 3. classify_china_regime
# ══════════════════════════════════════════════════════════════

def test_regime_empty_snapshot():
    out = classify_china_regime({})
    assert out["regime"] == "⬜ 資料不足"
    assert out["fx_alert"] is False


def test_regime_cli_pmi_both_missing():
    """CLI/PMI 雙缺 → 資料不足(M2 有也不行,因為衰退/緊縮判斷需 CLI/PMI 並進)"""
    out = classify_china_regime(_snap(m2=10.0, cpi=2.0, usdcny=6.8))
    assert out["regime"] == "⬜ 資料不足"


def test_regime_green_expansion():
    out = classify_china_regime(_snap(cli=101, pmi=101, m2=10.0, cpi=2.0))
    assert out["regime"] == "🟢 擴張"
    assert out["fx_alert"] is False


def test_regime_red_recession_via_cli_pmi():
    out = classify_china_regime(_snap(cli=97, pmi=97, m2=8.0))
    assert out["regime"] == "🔴 衰退/緊縮"


def test_regime_red_via_m2_tight():
    """M2 < 5% 即使 CLI/PMI 正常也是紅(信用緊縮)"""
    out = classify_china_regime(_snap(cli=101, pmi=101, m2=4.0))
    assert out["regime"] == "🔴 衰退/緊縮"
    assert "緊縮" in out["reason"]


def test_regime_yellow_slowdown():
    out = classify_china_regime(_snap(cli=98.5, pmi=99.5, m2=8.0))
    assert out["regime"] == "🟡 減速"


def test_regime_neutral():
    """CLI 與 PMI 都 99-100 之間"""
    out = classify_china_regime(_snap(cli=99.5, pmi=99.5, m2=8.0))
    assert out["regime"] == "⚪ 中性"


def test_regime_fx_alert_independent():
    """USDCNY > 7.4 → fx_alert=True,獨立於主 regime"""
    out = classify_china_regime(_snap(cli=101, pmi=101, m2=10.0, usdcny=7.5))
    assert out["regime"] == "🟢 擴張"
    assert out["fx_alert"] is True


def test_regime_fx_alert_at_boundary():
    """USDCNY = 7.4 不觸發(嚴格 >)"""
    out = classify_china_regime(_snap(cli=101, pmi=101, usdcny=7.4))
    assert out["fx_alert"] is False


def test_regime_fx_alert_when_data_short():
    """主 regime 資料不足時 fx_alert 仍可獨立亮"""
    out = classify_china_regime(_snap(usdcny=7.5))
    assert out["regime"] == "⬜ 資料不足"
    assert out["fx_alert"] is True


# ══════════════════════════════════════════════════════════════
# 4. apply_china_modifier — v19.116 乘法不對稱 blend
#    composite = main × (0.7 + 0.3 × china/100),只懲罰不加成
# ══════════════════════════════════════════════════════════════

def test_modifier_constants_match_design():
    """SSOT 守衛:floor=0.70(30% 最大懲罰)+ range=0.30(China 100→1.0×)"""
    assert math.isclose(CHINA_MODIFIER_FLOOR, 0.70, abs_tol=1e-12)
    assert math.isclose(CHINA_MODIFIER_RANGE, 0.30, abs_tol=1e-12)
    # 不變量:floor + range = 1.0(China=100 時 multiplier=1.0,不加成)
    assert math.isclose(
        CHINA_MODIFIER_FLOOR + CHINA_MODIFIER_RANGE, 1.0, abs_tol=1e-12,
    )


@pytest.mark.parametrize("china,expected", [
    (100.0, 60.00),  # multiplier=1.00 → main 原值
    (50.0,  51.00),  # multiplier=0.85 → 60×0.85
    (0.0,   42.00),  # multiplier=0.70 → 60×0.70(最大懲罰)
    (75.0,  55.50),  # multiplier=0.925 → 60×0.925
    (25.0,  46.50),  # multiplier=0.775 → 60×0.775
])
def test_modifier_main_60(china, expected):
    """main=60 各 china 值對應的 composite(浮點容差)"""
    got = apply_china_modifier(60.0, china)
    assert math.isclose(got, expected, abs_tol=1e-9), (
        f"main=60 china={china}: got {got}, expected {expected}"
    )


def test_modifier_china_none_returns_main_unchanged():
    """§1 Fail-safe:無中國資料 → main 原值通過(不偽造懲罰)"""
    assert apply_china_modifier(75.0, None) == 75.0
    assert apply_china_modifier(0.0, None) == 0.0
    assert apply_china_modifier(100.0, None) == 100.0


def test_modifier_main_none_returns_none():
    """無主分 → None(無從乘起)"""
    assert apply_china_modifier(None, 50.0) is None
    assert apply_china_modifier(None, None) is None


def test_modifier_china_clipped_to_valid_range():
    """china 越界(< 0 或 > 100)→ clip 到邊界,不 raise"""
    # china=-10 → clip 到 0 → multiplier=0.70
    assert math.isclose(
        apply_china_modifier(60.0, -10.0), 42.0, abs_tol=1e-9,
    )
    # china=150 → clip 到 100 → multiplier=1.00
    assert math.isclose(
        apply_china_modifier(60.0, 150.0), 60.0, abs_tol=1e-9,
    )


def test_modifier_composite_clipped_to_0_100():
    """composite 落在 [0, 100](防 main 越界帶來的結果越界)"""
    # main=200 china=100 → 200×1.0=200 → clip 100
    assert apply_china_modifier(200.0, 100.0) == 100.0
    # main=-50 → -50×any=負數 → clip 0
    assert apply_china_modifier(-50.0, 50.0) == 0.0


def test_modifier_invalid_types_return_none():
    """非數值輸入 → None(不靜默回 0,不 raise)"""
    assert apply_china_modifier("abc", 50.0) is None
    assert apply_china_modifier(60.0, "xyz") is None


def test_modifier_no_boost_property():
    """Property:對任何 (main, china) ∈ [0,100]²,composite ≤ main(只懲罰不加成)"""
    for main in (0, 25, 50, 75, 100):
        for china in (0, 25, 50, 75, 100):
            composite = apply_china_modifier(float(main), float(china))
            # 容差 1e-9 處理 china=100 的等號情況
            assert composite <= main + 1e-9, (
                f"main={main} china={china} composite={composite} > main 違反不加成屬性"
            )


def test_modifier_monotonic_in_china():
    """Property:固定 main,composite 對 china 單調遞增(china 越好懲罰越輕)"""
    main = 80.0
    prev = -1.0
    for china in (0, 10, 30, 50, 70, 90, 100):
        composite = apply_china_modifier(main, float(china))
        assert composite >= prev, f"china={china} composite={composite} < prev={prev}"
        prev = composite


# v19.116 §6 自審「3 個最容易出錯的輸入」:
#   1. china=None (Fail-safe 不懲罰) ✅ test_modifier_china_none_returns_main_unchanged
#   2. china 越界 < 0 或 > 100 (clip,不 raise) ✅ test_modifier_china_clipped_to_valid_range
#   3. main 越界 / 非數值 (clip 到 [0,100] / 回 None) ✅ test_modifier_composite_clipped + invalid_types
