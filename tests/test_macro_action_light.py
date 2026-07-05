"""回歸網 — v19.316 總經「現在能不能買」總結燈(services/macro/action_light.py)。

守 user 批准的融合邏輯:
1. 硬衰退/恐慌訊號(倒掛 / Sahm≥0.5 / VIX≥30)任一亮 → 🔴 override(不管景氣位階多高)。
2. 無 override → 依景氣位階 0-10:≥6.5 🟢 / 4.0~6.5 🟡 / <4.0 🔴。
3. 位階缺 → 🟡 資料不足(§1 不下假綠燈)。
"""
from __future__ import annotations

from services.macro.action_light import macro_action_light


def _ind(**kw):
    """快速造 indicators dict:_ind(VIX=35, YIELD_10Y2Y=-0.3)。"""
    return {k: {"value": v} for k, v in kw.items()}


def test_yield_inversion_forces_red_override():
    r = macro_action_light(_ind(YIELD_10Y2Y=-0.30), phase_score_10=9.0)  # 位階很高
    assert r["light"] == "🔴" and r["override"] is True
    assert any("倒掛" in x for x in r["reasons"])


def test_sahm_forces_red_override():
    r = macro_action_light(_ind(SAHM=0.6), phase_score_10=8.0)
    assert r["light"] == "🔴" and r["override"] is True
    assert any("Sahm" in x for x in r["reasons"])


def test_vix_panic_forces_red_override():
    r = macro_action_light(_ind(VIX=32), phase_score_10=8.0)
    assert r["light"] == "🔴" and r["override"] is True
    assert any("VIX" in x for x in r["reasons"])


def test_high_phase_no_signal_is_green():
    r = macro_action_light(_ind(VIX=15, YIELD_10Y2Y=0.8, SAHM=0.1), phase_score_10=7.2)
    assert r["light"] == "🟢" and r["override"] is False


def test_mid_phase_is_yellow():
    r = macro_action_light(_ind(VIX=15, YIELD_10Y2Y=0.8, SAHM=0.1), phase_score_10=5.0)
    assert r["light"] == "🟡"


def test_low_phase_is_red_no_override():
    r = macro_action_light(_ind(VIX=15, YIELD_10Y2Y=0.8, SAHM=0.1), phase_score_10=2.0)
    assert r["light"] == "🔴" and r["override"] is False


def test_missing_score_is_yellow_unknown():
    r = macro_action_light(_ind(VIX=15, YIELD_10Y2Y=0.8), phase_score_10=None)
    assert r["light"] == "🟡" and "資料不足" in r["action"]


def test_missing_indicators_do_not_crash():
    r = macro_action_light({}, phase_score_10=6.6)
    assert r["light"] == "🟢"  # 無訊號 + 高位階
    r2 = macro_action_light(None, phase_score_10=None)
    assert r2["light"] == "🟡"
