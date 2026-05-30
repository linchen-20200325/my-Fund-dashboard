"""
test_macro_service_inflection.py — v18.250 拐點偵測單元測試

驗證重點：
1. _detect_inflection 新增的 3 個拐點檢查（HY Spread / Sahm Rule / CFNAI）
   都會在符合條件時正確 emit signal + 加分。
2. detect_turning_points 新增的 3 個 dict key（hy_spread / sahm_rule / lei_cfnai）
   結構正確、source_ok=False 時仍可優雅降級。
"""
from __future__ import annotations

import pandas as pd
import pytest

from services.macro_service import _detect_inflection, detect_turning_points


# ════════════════════════════════════════════════════════════
# _detect_inflection 新增 3 條拐點規則
# ════════════════════════════════════════════════════════════

def test_hy_spread_high_position_reversal_emits_buy():
    """HY Spread 由 6.5% → 5.8% 高位首度回落 → emit buy 訊號 + score 加分。"""
    ind = {
        "HY_SPREAD": {"value": 5.8, "prev": 6.5},
    }
    r = _detect_inflection(ind)
    assert r["infl_score"] >= 3
    assert any("HY" in s["text"] and s["type"] == "buy" for s in r["signals"])


def test_sahm_rule_un_trigger_emits_strong_buy():
    """Sahm Rule 由 0.55 → 0.42 跌破 0.5 → emit 強買訊號 + score 加 4。"""
    ind = {
        "SAHM": {"value": 0.42, "prev": 0.55},
    }
    r = _detect_inflection(ind)
    assert r["infl_score"] >= 4
    assert any("薩姆" in s["text"] and s["type"] == "buy" for s in r["signals"])


def test_cfnai_negative_to_positive_emits_buy():
    """CFNAI 由 -0.1 → +0.2 由負轉正 → emit buy 訊號 + score 加 3。"""
    ind = {
        "LEI": {"value": 0.2, "prev": -0.1},
    }
    r = _detect_inflection(ind)
    assert r["infl_score"] >= 3
    assert any("CFNAI" in s["text"] and s["type"] == "buy" for s in r["signals"])


def test_no_new_indicators_does_not_crash():
    """沒有新增任何指標時，_detect_inflection 不應炸鍋（只是不加分）。"""
    r = _detect_inflection({})
    assert "infl_score" in r
    assert "signals" in r
    assert isinstance(r["signals"], list)


# ════════════════════════════════════════════════════════════
# detect_turning_points 結構驗證
# ════════════════════════════════════════════════════════════

def test_detect_turning_points_returns_5_keys():
    """無 fred_api_key 時 detect_turning_points 應回 5 個 key（原 2 + 新 3），
    且每個 value 都是 dict 有 source_ok=False。"""
    out = detect_turning_points("")
    expected_keys = {"pmi_diff", "yield_curve", "hy_spread", "sahm_rule", "lei_cfnai"}
    assert set(out.keys()) >= expected_keys
    for k in expected_keys:
        assert isinstance(out[k], dict)
        assert "signal" in out[k]
        assert "color" in out[k]
        assert "source_ok" in out[k]
        # 無 fred_api_key 時應全部 source_ok=False
        assert out[k]["source_ok"] is False


def test_detect_turning_points_safe_on_empty_dataframe(monkeypatch):
    """fetch_fred 全部回空 DataFrame 時不應拋例外，所有 key source_ok 都是 False。"""
    import services.macro_service as ms

    def _empty_fred(sid, key, n=250):
        return pd.DataFrame(columns=["date", "value"])

    monkeypatch.setattr(ms, "fetch_fred", _empty_fred)
    out = detect_turning_points("dummy-key")
    for k in ("pmi_diff", "yield_curve", "hy_spread", "sahm_rule", "lei_cfnai"):
        assert out[k]["source_ok"] is False
