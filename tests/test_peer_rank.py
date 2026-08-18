"""同類四分位排名(services/peer_rank.py,v19.464 架構缺口 #2)。

鎖住:年化報酬正確性 + 資料不足/短窗退場、四分位樣本量三態(<2 / 2-3 / ≥4)、Q 邊界對映、
並列可重現、便捷入口端到端。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from services.peer_rank import (
    annualized_return,
    peer_annualized_returns,
    peer_quartile,
    peer_quartile_labels,
    quartile_rank,
)


def _series(cagr: float, years: float = 3.0, start: float = 100.0) -> pd.Series:
    """幾何成長合成 NAV(每日),年化 = cagr。"""
    days = int(years * 365.25)
    idx = pd.date_range("2022-01-01", periods=days, freq="D")
    end = start * (1 + cagr) ** years
    vals = start * (end / start) ** np.linspace(0.0, 1.0, days)
    return pd.Series(vals, index=idx)


# ── annualized_return ────────────────────────────────────────
def test_annualized_return_matches_known_cagr():
    r = annualized_return(_series(0.10, 3.0), 3.0)
    assert r is not None and abs(r - 0.10) < 0.01     # ~10%/yr


def test_annualized_return_insufficient_obs_none():
    s = pd.Series([100, 101, 102], index=pd.date_range("2024-01-01", periods=3))
    assert annualized_return(s, 1.0) is None          # < PEER_MIN_OBS


def test_annualized_return_short_span_none():
    # ~3.5 個月(≥50 點)但要 1Y 窗 → 跨度不足 → None
    assert annualized_return(_series(0.10, 0.3), 1.0) is None


def test_annualized_return_pit_uses_series_own_last_date():
    # 序列 2022 起、2 年;用自身末日回推,不受「今天」影響 → 仍算得出
    r = annualized_return(_series(0.05, 2.0), 2.0)
    assert r is not None and abs(r - 0.05) < 0.01


# ── quartile_rank 樣本量三態 ─────────────────────────────────
def test_quartile_rank_lt2_no_compare():
    r = quartile_rank("A", {"A": 0.1})
    assert r["rank"] is None and r["enough_sample"] is False and "無同類" in r["label"]


def test_quartile_rank_small_sample_ranks_but_no_quartile():
    r = quartile_rank("A", {"A": 0.2, "B": 0.1, "C": 0.05})   # 3 檔
    assert r["rank"] == 1 and r["n"] == 3
    assert r["quartile"] is None and r["enough_sample"] is False and "樣本少" in r["label"]


def test_quartile_rank_full_quartile_best_and_worst():
    rets = {c: (0.30 - i * 0.03) for i, c in enumerate("ABCDEFGH")}  # A 最佳 → H 最差
    best = quartile_rank("A", rets)
    assert best["rank"] == 1 and best["n"] == 8 and best["quartile"] == "Q1" and best["percentile"] == 0.0
    worst = quartile_rank("H", rets)
    assert worst["rank"] == 8 and worst["quartile"] == "Q4" and worst["percentile"] == 1.0


def test_quartile_mapping_boundaries():
    rets = {c: (1.0 - i) for i, c in enumerate("ABCDEFGH")}   # n=8
    q = {c: quartile_rank(c, rets)["quartile"] for c in "ABCDEFGH"}
    assert q["A"] == "Q1" and q["B"] == "Q1"    # top 25%
    assert q["C"] == "Q2" and q["D"] == "Q2"
    assert q["E"] == "Q3" and q["F"] == "Q3"
    assert q["G"] == "Q4" and q["H"] == "Q4"    # bottom 25%


def test_quartile_rank_target_not_in_returns():
    r = quartile_rank("Z", {"A": 0.1, "B": 0.2, "C": 0.3, "D": 0.4})
    assert r["rank"] is None and r["enough_sample"] is False


def test_quartile_rank_tie_break_reproducible():
    m = {"A": 0.1, "B": 0.1, "C": 0.1, "D": 0.1}
    assert quartile_rank("B", m) == quartile_rank("B", m)   # 並列穩定可重現(§5)


# ── peer_annualized_returns / peer_quartile ──────────────────
def test_peer_annualized_returns_skips_uncomputable():
    m = {"good": _series(0.10, 3.0), "short": _series(0.10, 0.3), "none": None}
    out = peer_annualized_returns(m, 1.0)
    assert "good" in out and "short" not in out and "none" not in out


def test_peer_quartile_end_to_end():
    m = {c: _series(0.30 - i * 0.05, 3.0) for i, c in enumerate("ABCD")}
    r = peer_quartile("A", m, 3.0)
    assert r["n"] == 4 and r["quartile"] == "Q1" and r["window_years"] == 3.0


# ── peer_quartile_labels(組合健診 post-pass 實際呼叫的邏輯)──────
def test_peer_quartile_labels_groups_by_asset_bucket():
    """4 股票同桶 → 真四分位;債券單檔 → 無同類;ok=False 不算。"""
    rows = [
        {"code": "A", "ok": True, "_fund_raw": {"category": "全球股票型", "series": _series(0.20, 3.0)}},
        {"code": "B", "ok": True, "_fund_raw": {"category": "美國股票型", "series": _series(0.15, 3.0)}},
        {"code": "C", "ok": True, "_fund_raw": {"category": "科技股票型", "series": _series(0.10, 3.0)}},
        {"code": "D", "ok": True, "_fund_raw": {"category": "歐洲股票型", "series": _series(0.05, 3.0)}},
        {"code": "E", "ok": True, "_fund_raw": {"category": "新興市場債券", "series": _series(0.08, 3.0)}},
        {"code": "F", "ok": False, "_fund_raw": {}},
    ]
    labels = peer_quartile_labels(rows, 3.0)
    assert "Q1" in labels["A"] and "同類 4 檔" in labels["A"]   # 股票組報酬最高 → Q1
    assert "Q4" in labels["D"]                                  # 股票組最低 → Q4
    assert "無同類可比" in labels["E"]                          # 防禦債單檔,不硬分
    assert "F" not in labels                                    # ok=False 不進


def test_peer_quartile_labels_unmapped_category_excluded():
    """category 對不到 asset_bucket(空/亂字串)→ 不進任何組(呼叫端退無同類)。"""
    rows = [
        {"code": "X", "ok": True, "_fund_raw": {"category": "", "series": _series(0.1, 3.0)}},
        {"code": "Y", "ok": True, "_fund_raw": {"category": "???亂填", "series": _series(0.1, 3.0)}},
    ]
    labels = peer_quartile_labels(rows, 3.0)
    assert "X" not in labels and "Y" not in labels             # 未分類不硬歸股票(§1)


def _short() -> pd.Series:
    """< PEER_MIN_OBS(50)點的短序列 → 年化算不出。"""
    return pd.Series([100.0 + i for i in range(10)],
                     index=pd.date_range("2024-01-01", periods=10, freq="D"))


def test_peer_quartile_labels_self_no_valid_return_branch():
    """桶內 ≥2 檔可算、但某檔 obs 不足 → 該檔誠實『自身無有效年化報酬』(非硬給名次)。"""
    rows = [
        {"code": "A", "ok": True, "_fund_raw": {"category": "全球股票型", "series": _series(0.20, 3.0)}},
        {"code": "B", "ok": True, "_fund_raw": {"category": "美國股票型", "series": _series(0.10, 3.0)}},
        {"code": "C", "ok": True, "_fund_raw": {"category": "科技股票型", "series": _short()}},  # obs 不足
    ]
    labels = peer_quartile_labels(rows, 3.0)
    assert "第 1/2 名" in labels["A"]                       # A/B 可算 → 2 檔相對排名
    assert "自身無有效年化報酬" in labels["C"]              # C 算不出 → 誠實退,不硬排


def test_peer_quartile_labels_single_computable_in_bucket_no_compare():
    """桶內只 1 檔算得出年化(其餘 obs 不足)→ 全退『無同類可比(<2 檔)』。"""
    rows = [
        {"code": "A", "ok": True, "_fund_raw": {"category": "全球股票型", "series": _series(0.2, 3.0)}},
        {"code": "B", "ok": True, "_fund_raw": {"category": "美國股票型", "series": _short()}},
    ]
    labels = peer_quartile_labels(rows, 3.0)
    assert "無同類可比" in labels["A"] and "無同類可比" in labels["B"]


def test_peer_quartile_labels_moneydj_raw_category_read():
    """category 藏在 _fund_raw.moneydj_raw.category 也讀得到。"""
    rows = [
        {"code": "A", "ok": True, "_fund_raw": {"moneydj_raw": {"category": "全球股票型"},
                                                "series": _series(0.2, 3.0)}},
        {"code": "B", "ok": True, "_fund_raw": {"moneydj_raw": {"category": "美國股票型"},
                                                "series": _series(0.1, 3.0)}},
    ]
    labels = peer_quartile_labels(rows, 3.0)
    assert "A" in labels and "B" in labels and "第 1/2 名" in labels["A"]   # 2 檔 → 只給排名
