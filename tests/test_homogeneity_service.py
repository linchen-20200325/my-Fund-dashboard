"""services/homogeneity.py 契約測試(2026-08-31 元件 A 計算層)。

守三件事(對應線框 06 節「資料需求」表的三個「現況沒有」):
  1. Q2 同質化分級:切點行為(含**恰好 20%** 的邊界)+ 樣本不足不硬判。
  2. 分母誠實:同質化比率的分母是**成功對數**,不是理論對數 N×(N−1)/2 ——
     兩者不同時,拿錯分母會判出**錯的等級**(突變方向:換分母 → 本檔紅)。
  3. 剔除名單誠實(§1):被靜默縮小比對範圍的檔,必須具名 + 帶原因出現在輸出。

⚠️ 突變驗證紀錄(2026-08-31,提交前實跑;「拿掉修復必須轉紅」):
  - `homogeneity_grade` 的 `ratio <= mid_max` 改 `<` → `test_grade_boundary_exactly_at_cut` 紅
  - `homogeneity_grade` 分母改 theoretical → `test_denominator_is_success_pairs_not_theoretical` 紅
  - `build_mutual_exclusion_summary` 的 excluded 恆回 [] → `test_excluded_funds_are_named_with_reasons` 紅
  - `_has_dims` 拿掉 pct>0 判定 → `test_mirror_lock_fabricated_zero_pairs_do_not_count_as_success` 紅
  - alert hits 不帶 threshold → `test_alert_pairs_carry_kind_and_threshold` 紅
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from services.homogeneity import (
    DIM_HOLDINGS,
    DIM_NAV,
    build_mutual_exclusion_summary,
    homogeneity_grade,
)
from services.portfolio_service import calc_correlation_matrix, calc_holdings_overlap
from shared.signal_thresholds import (
    HOMOGENEITY_MID_MAX_RATIO,
    HOMOGENEITY_MIN_PAIRS,
    SHADOW_FUND_NAV_CORR_THRESHOLD_RATIO,
    SHADOW_FUND_THRESHOLD_RATIO,
)

# ═══════════════════════════════════════════════════════════════════════
# 1. Q2 分級
# ═══════════════════════════════════════════════════════════════════════


def test_grade_zero_alerts_is_low():
    assert homogeneity_grade(0, 10) == {"grade": "low", "ratio": 0.0}


def test_grade_boundary_exactly_at_cut():
    """恰好等於切點(20%)→ **中**,不是高(Q2 原文「≤ 20% = 中」;突變 `<=`→`<` 轉紅)。"""
    g = homogeneity_grade(2, 10)
    assert g["grade"] == "mid" and g["ratio"] == pytest.approx(HOMOGENEITY_MID_MAX_RATIO)


def test_grade_above_cut_is_high():
    assert homogeneity_grade(3, 10)["grade"] == "high"


def test_grade_insufficient_sample_never_judges():
    """成功對數 < SSOT 門檻 → ⬜ 不硬判(含 0 對成功;ratio 必須是 None,不得假造 0)。"""
    for n_success in range(HOMOGENEITY_MIN_PAIRS):
        g = homogeneity_grade(1, n_success)
        assert g == {"grade": "insufficient", "ratio": None}
    # 剛好達門檻 → 開判(邊界的另一半)
    assert homogeneity_grade(0, HOMOGENEITY_MIN_PAIRS)["grade"] == "low"


def test_grade_cut_follows_ssot_constant():
    """切點吃 shared/signal_thresholds SSOT:模組內不得另養一把尺(§3.3)。"""
    just_above = int(HOMOGENEITY_MID_MAX_RATIO * 100) + 1
    assert homogeneity_grade(just_above, 100)["grade"] == "high"
    assert homogeneity_grade(just_above - 1, 100)["grade"] == "mid"


# ═══════════════════════════════════════════════════════════════════════
# 2. summary:分母 / 警示對 / 剔除名單
# ═══════════════════════════════════════════════════════════════════════


def _series(seed: int, n: int = 400) -> pd.Series:
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    rng = np.random.default_rng(seed)
    return pd.Series(100 + np.cumsum(rng.normal(0, 1, n)), index=idx)


def _battery():
    """4 檔:A/B 影子對(持股同 + 走勢同)、C 兩維度全缺、D NAV 太短。

    刻意讓「成功對數 ≠ 理論對數」:理論 6 對,實算成功 5 對
    (持股維度 {AB,AD,BD} ∪ NAV 維度 {AB,AC,BC})。
    """
    base = _series(0)
    hov_input = [
        {"code": "A", "name": "A基",
         "top_holdings": [{"name": "TSMC"}, {"name": "AAPL"}],
         "sector_alloc": [{"name": "tech", "pct": 80}]},
        {"code": "B", "name": "B基",
         "top_holdings": [{"name": "TSMC"}, {"name": "AAPL"}],
         "sector_alloc": [{"name": "tech", "pct": 80}]},
        {"code": "C", "name": "C基", "top_holdings": [], "sector_alloc": []},
        {"code": "D", "name": "D基",
         "top_holdings": [{"name": "NVDA"}],
         "sector_alloc": [{"name": "tech", "pct": 50}]},
    ]
    corr_input = [
        {"code": "A", "name": "A基", "series": base},
        {"code": "B", "name": "B基",
         "series": base * pd.Series(np.full(len(base), 1.0001)).cumprod().to_numpy()},
        {"code": "C", "name": "C基", "series": _series(7)},
        {"code": "D", "name": "D基", "series": base.head(5)},   # < 30 筆 → 被靜默濾掉
    ]
    return hov_input, corr_input


def _summary():
    hov_input, corr_input = _battery()
    return build_mutual_exclusion_summary(
        hov_input, corr_input,
        calc_holdings_overlap(hov_input),
        calc_correlation_matrix(corr_input))


def test_denominator_is_success_pairs_not_theoretical():
    """理論 6 對、實算成功 5 對 —— 分母必須是 5(突變:換 theoretical → 本測試紅)。"""
    s = _summary()
    assert s["theoretical_pairs"] == 6
    assert s["success_pairs_union"] == 5
    assert s["homogeneity"]["ratio"] == pytest.approx(
        s["alert_pair_count"] / s["success_pairs_union"])
    # 交叉錨:此 battery 下 1/5 = 20% = 恰好切點 → mid;拿理論分母會得 1/6 ≈ 17% 也是
    # mid —— 故再用一個分母不同會**翻等級**的網格釘死(alert=1、成功=3、理論=6):
    hov_input, corr_input = _battery()
    corr_input = corr_input[:2] + corr_input[3:]        # 拿掉 C 的序列 → NAV 只剩 {AB}
    s2 = build_mutual_exclusion_summary(
        hov_input, corr_input,
        calc_holdings_overlap(hov_input),
        calc_correlation_matrix(corr_input))
    assert s2["success_pairs_union"] == 3               # {AB,AD,BD} ∪ {AB}
    assert s2["theoretical_pairs"] == 6
    assert s2["homogeneity"]["grade"] == "high"         # 1/3 ≈ 33% > 20%;1/6 才會是 mid


def test_alert_pairs_carry_kind_and_threshold():
    """警示對逐 hit 帶型態 + 門檻(線框 06 節「現況沒有」的第一列;門檻對 SSOT)。"""
    s = _summary()
    assert s["alert_pair_count"] == 1
    (al,) = s["alerts"]
    assert {al["code_a"], al["code_b"]} == {"A", "B"}
    kinds = {h["kind"]: h for h in al["hits"]}
    assert set(kinds) == {DIM_HOLDINGS, DIM_NAV}        # 同一對兩維度 → 一筆、兩 hit
    assert kinds[DIM_HOLDINGS]["threshold"] == SHADOW_FUND_THRESHOLD_RATIO
    assert kinds[DIM_NAV]["threshold"] == SHADOW_FUND_NAV_CORR_THRESHOLD_RATIO
    for h in al["hits"]:
        assert h["value"] >= h["threshold"]             # 警示的定義本身


def test_excluded_funds_are_named_with_reasons():
    """§1:被靜默縮小比對範圍的檔必須具名 + 帶原因(突變:excluded 恆回 [] → 紅)。"""
    s = _summary()
    by_code = {x["code"]: x for x in s["excluded"]}
    assert "C" in by_code and by_code["C"]["name"] == "C基"
    assert any("持股" in r for r in by_code["C"]["reasons"])
    assert "D" in by_code
    assert any("NAV" in r for r in by_code["D"]["reasons"])
    assert "A" not in by_code and "B" not in by_code    # 有資料的不得被誤列


def test_mirror_lock_fabricated_zero_pairs_do_not_count_as_success():
    """鏡像鎖:calc_holdings_overlap 對「雙缺對」填 0.0 —— 那不是成功比對。

    A 只有持股、B 只有產業 → 該對 j_score/c_score 皆 None → calc 填 0.0;
    成功對數必須是 0,不得把捏造的 0.0 當「比對成功且不相關」(§1)。
    """
    hov_input = [
        {"code": "A", "name": "A", "top_holdings": [{"name": "X"}], "sector_alloc": []},
        {"code": "B", "name": "B", "top_holdings": [],
         "sector_alloc": [{"name": "tech", "pct": 50}]},
    ]
    hov = calc_holdings_overlap(hov_input)
    assert hov is not None and hov["matrix"] is not None      # calc 確實給了 0.0 矩陣
    assert float(hov["matrix"].iloc[0, 1]) == 0.0
    s = build_mutual_exclusion_summary(hov_input, [], hov, None)
    assert s["dims"][DIM_HOLDINGS]["computed"] is True
    assert s["dims"][DIM_HOLDINGS]["success_pairs"] == 0
    assert s["homogeneity"]["grade"] == "insufficient"        # 0 成功對 → 不硬判


def test_mirror_lock_zero_pct_sector_is_not_data():
    """鏡像鎖 2:sector pct=0 依 calc 正規化不算有資料 → 該檔入剔除名單。"""
    hov_input = [
        {"code": "A", "name": "A", "top_holdings": [],
         "sector_alloc": [{"name": "tech", "pct": 0}]},
        {"code": "B", "name": "B", "top_holdings": [{"name": "X"}],
         "sector_alloc": [{"name": "tech", "pct": 50}]},
    ]
    s = build_mutual_exclusion_summary(
        hov_input, [], calc_holdings_overlap(hov_input), None)
    assert [x["code"] for x in s["excluded"]] == ["A"]


def test_dim_not_computed_is_reported_not_faked():
    """corr_result=None(NAV 維度整組沒算成)→ computed=False、0 成功對,不假裝有算。"""
    hov_input, _ = _battery()
    s = build_mutual_exclusion_summary(
        hov_input, [], calc_holdings_overlap(hov_input), None)
    assert s["dims"][DIM_NAV]["computed"] is False
    assert s["dims"][DIM_NAV]["success_pairs"] == 0
