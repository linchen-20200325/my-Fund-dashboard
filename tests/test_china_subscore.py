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

from services.macro_service import (
    _score_cli,
    _score_cpi,
    _score_m2,
    _score_pmi,
    _score_usdcny,
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
