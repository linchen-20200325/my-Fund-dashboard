"""tests/test_rotation.py — 輪動配對建議(賣高基期 → 買低基期健康)v19.415。

驗:同類健康配對、爛買方排除(4D=F / 吃本金 / 操盤評分低)、異類不配、無買方回 None、
σ 門檻分類、距 HWM% → 潛在差價%、σ rank 帶「σ」字尾也能解析。
"""
from __future__ import annotations

from services.rotation import (
    classify_base,
    is_healthy_buy,
    revert_upside_pct,
    suggest_rotation_pairs,
)


def _f(code, cat, sig, grade="B", eat="🟢 健康", score=70, dist="-18%"):
    return {"code": code, "name": code, "基金類別": cat, "σ rank": sig,
            "4D Grade": grade, "吃本金燈號": eat, "操盤評分": score, "距 HWM %": dist}


def test_basic_pairing_same_category_healthy():
    pool = [_f("A", "股票型", "-0.2σ"), _f("B", "股票型", "-2.0σ")]
    pairs = suggest_rotation_pairs(pool)
    assert len(pairs) == 1
    assert pairs[0]["sell_code"] == "A" and pairs[0]["buy_code"] == "B"
    assert abs(pairs[0]["potential_pct"] - 22.0) < 0.5   # -18% 回高點 ≈ +22%


def test_unhealthy_buy_excluded_4d_f():
    pool = [_f("A", "股票型", "-0.2σ"), _f("B", "股票型", "-2.0σ", grade="F")]
    assert suggest_rotation_pairs(pool)[0]["buy_code"] is None   # 賣方在,但無健康買方


def test_eat_principal_buy_excluded():
    pool = [_f("A", "股票型", "-0.2σ"), _f("B", "股票型", "-2.0σ", eat="🔴 吃本金")]
    assert suggest_rotation_pairs(pool)[0]["buy_code"] is None


def test_low_score_buy_excluded():
    pool = [_f("A", "股票型", "-0.2σ"), _f("B", "股票型", "-2.0σ", score=30)]
    assert suggest_rotation_pairs(pool)[0]["buy_code"] is None


def test_different_category_not_paired():
    pool = [_f("A", "股票型", "-0.2σ"), _f("B", "債券型", "-2.0σ")]
    assert suggest_rotation_pairs(pool)[0]["buy_code"] is None


def test_no_high_base_no_pairs():
    pool = [_f("A", "股票型", "-2.0σ"), _f("B", "股票型", "-2.5σ")]
    assert suggest_rotation_pairs(pool) == []       # 無高基期賣方


def test_deepest_buy_chosen():
    pool = [_f("A", "股票型", "-0.2σ"),
            _f("B", "股票型", "-1.6σ"), _f("C", "股票型", "-2.8σ")]
    assert suggest_rotation_pairs(pool)[0]["buy_code"] == "C"   # 跌最深


def test_classify_base_thresholds():
    assert classify_base("-0.2σ") == "high"
    assert classify_base("-2.0σ") == "low"
    assert classify_base("-1.0σ") == "mid"
    assert classify_base(None) == "unknown"


def test_revert_upside():
    assert revert_upside_pct("-18%") == 22.0
    assert revert_upside_pct("0%") is None          # 已在高點,無差價
    assert revert_upside_pct(None) is None


def test_is_healthy_buy_positive():
    assert is_healthy_buy({"4D Grade": "C", "吃本金燈號": "🟢 健康", "操盤評分": 55})
    assert is_healthy_buy({"4D Grade": "B", "吃本金燈號": "🟡 警示", "操盤評分": None})  # 🟡 + 缺評分 → 允許


def test_is_healthy_buy_fail_closed():
    """§1 fail-closed:資料不足不得當健康(接刀防護)。"""
    assert not is_healthy_buy({})                                        # 全缺 → 擋
    assert not is_healthy_buy({"4D Grade": "—", "吃本金燈號": "", "操盤評分": None})  # 403 深跌缺料
    assert not is_healthy_buy({"4D Grade": "B", "吃本金燈號": "⚪ 資料不足"})  # 無健康燈 → 擋
    assert not is_healthy_buy({"4D Grade": "D", "吃本金燈號": "🟢 健康"})      # D 評等 → 擋
    assert not is_healthy_buy({"4D Grade": "F"})
    assert not is_healthy_buy({"操盤評分": 20})


def test_missing_data_buy_not_recommended():
    """低基期但資料不足的深跌檔,不得被推薦為『低基期健康』(接刀)。"""
    pool = [_f("A", "股票型", "-0.2σ"),
            {"code": "B", "name": "B", "基金類別": "股票型", "σ rank": "-2.5σ",
             "4D Grade": "—", "吃本金燈號": "", "操盤評分": None, "距 HWM %": "-30%"}]
    assert suggest_rotation_pairs(pool)[0]["buy_code"] is None
