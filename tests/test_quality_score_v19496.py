"""v19.496:同類相對品質分(Option A + 混合母體)L2 純函式測試。

驗證:百分位→因子分方向、缺因子退出分母重正規化(§1)、有效因子太少不給分、
貢獻分解加總=score、覆蓋率、bool 不當數字、權重覆蓋。
"""
import math

import pytest

from services.quality_score import (
    DEFAULT_WEIGHTS,
    MIN_FACTORS_FOR_SCORE,
    _pct_to_factor_score,
    compute_quality_score,
)

_ALL = {"報酬": 0.0, "Sharpe": 0.0, "下檔": 0.0, "操盤": 0.0, "配息": 0.0, "成本": 0.0}


# ── 方向:百分位 0=最佳 → 100 分,1=最差 → 0 分 ─────────────────────────
def test_pct_to_factor_score_direction():
    assert _pct_to_factor_score(0.0) == 100.0     # 同類第一 → 滿分
    assert _pct_to_factor_score(1.0) == 0.0       # 同類墊底 → 0
    assert _pct_to_factor_score(0.5) == 50.0
    assert _pct_to_factor_score(-0.3) == 100.0    # 越界 clip
    assert _pct_to_factor_score(1.7) == 0.0


def test_all_best_is_100():
    r = compute_quality_score(dict(_ALL))          # 全部同類第一
    assert r["score"] == 100.0
    assert r["n_used"] == 6 and r["coverage_pct"] == 100.0


def test_all_worst_is_0():
    r = compute_quality_score({k: 1.0 for k in _ALL})
    assert r["score"] == 0.0


def test_mid_is_50():
    r = compute_quality_score({k: 0.5 for k in _ALL})
    assert r["score"] == 50.0


# ── 貢獻分解加總 = score ────────────────────────────────────────────────
def test_contributions_sum_to_score():
    r = compute_quality_score({"報酬": 0.0, "Sharpe": 0.5, "下檔": 0.2,
                               "操盤": 1.0, "配息": 0.4, "成本": 0.6})
    assert math.isclose(sum(r["contributions"].values()), r["score"], abs_tol=0.3)
    assert set(r["contributions"]) == set(_ALL)    # 六項都有貢獻欄


# ── §1 缺因子:退出分母、權重重正規化(不填 0)──────────────────────────
def test_missing_factor_renormalizes_not_zero_filled():
    # 只有 報酬(0=最佳)+ Sharpe(0=最佳)→ 兩項都滿分 → score 應 = 100(非被缺項拉低)
    r = compute_quality_score({"報酬": 0.0, "Sharpe": 0.0, "下檔": 0.0})
    assert r["score"] == 100.0                      # 缺的沒被當 0 分(那會 <100)
    assert r["n_used"] == 3
    # 覆蓋率 = (25+25+20)/100 = 70%
    assert r["coverage_pct"] == 70.0


def test_missing_vs_worst_differ():
    # 缺 vs 同類最差(1.0)必須不同:缺=退出分母,最差=0 分進分母
    r_missing = compute_quality_score({"報酬": 0.0, "Sharpe": 0.0, "下檔": 0.0})
    r_worst = compute_quality_score({"報酬": 0.0, "Sharpe": 0.0, "下檔": 0.0,
                                     "操盤": 1.0, "配息": 1.0, "成本": 1.0})
    assert r_missing["score"] > r_worst["score"]    # 缺料不該等於墊底


# ── 有效因子太少 → 不給分(§1)──────────────────────────────────────────
def test_too_few_factors_no_score():
    r = compute_quality_score({"報酬": 0.0, "Sharpe": 0.2})   # 只有 2 項 < 3
    assert r["score"] is None
    assert r["n_used"] == 2
    assert "不給相對分" in r["note"]


def test_empty_no_score():
    r = compute_quality_score({})
    assert r["score"] is None and r["n_used"] == 0


def test_single_fund_4_moneydj_factors_still_scores():
    # 單一基金頁情境:只有 4 個 MoneyDJ 大母體因子,操盤/配息 小-universe 缺 → 仍達標給分
    r = compute_quality_score({"報酬": 0.1, "Sharpe": 0.2, "下檔": 0.3, "成本": 0.4,
                               "操盤": None, "配息": None})
    assert r["score"] is not None and r["n_used"] == 4
    assert r["coverage_pct"] == 80.0                # (25+25+20+10)/100


# ── §1:bool / None 不當數字 ────────────────────────────────────────────
def test_bool_not_counted_as_percentile():
    # True 是 int 子類,但不是合法百分位 → 必須排除,不當 1.0/最差
    r = compute_quality_score({"報酬": 0.0, "Sharpe": 0.0, "下檔": 0.0,
                               "操盤": True, "配息": False, "成本": None})
    assert r["n_used"] == 3                          # 只認 3 個 float


def test_min_factors_constant_is_3():
    assert MIN_FACTORS_FOR_SCORE == 3


# ── 權重覆蓋 ────────────────────────────────────────────────────────────
def test_custom_weights():
    # 只給 報酬 權重 → 報酬 percentile 決定一切
    r = compute_quality_score({"報酬": 0.25, "Sharpe": 0.9, "下檔": 0.9},
                              weights={"報酬": 100.0, "Sharpe": 0.0, "下檔": 0.0})
    # Sharpe/下檔 權重 0 → 不影響;score = (1-0.25)*100 = 75
    # n_used 只算權重>0 且有值的… 這裡權重 0 的仍在 names,但有值 → 進 avail
    # 設計上 weight=0 貢獻 0,故 score 由 報酬 主導
    assert 70 <= r["score"] <= 80


def test_default_weights_sum_100():
    assert math.isclose(sum(DEFAULT_WEIGHTS.values()), 100.0)


# ── 模組 2:quality_score_by_code(L3 assembler + 大表接線)──────────────────
def _fund(code, sharpe, sigma, tr1y, adr, fee, ret1y, peer_rank=None):
    # peer_rank「x/50」→ MoneyDJ 同類官方大母體排名(v19.496 稽核後「報酬」因子純用此,不退小 universe)
    _mj = {"mgmt_fee": fee, "perf": {"1Y": ret1y}}
    if peer_rank:
        _mj["risk_metrics"] = {"peer_compare": {"本基金": {"報酬排名": peer_rank}}}
    return {"code": code,
            "metrics": {"sharpe": sharpe, "std_1y": sigma, "ret_1y_total": tr1y,
                        "annual_div_rate": adr, "ret_1y": ret1y},
            "moneydj_raw": _mj, "series": None}


def _abcd():
    # A 最好 → D 最差(含 MoneyDJ 同類官方排名 1/15/30/45 of 50)
    return [_fund("A", 1.5, 8.0, 12.0, 6.0, 1.0, 12.0, peer_rank="1/50"),
            _fund("B", 1.0, 12.0, 9.0, 6.0, 1.5, 9.0, peer_rank="15/50"),
            _fund("C", 0.5, 16.0, 6.0, 6.0, 2.0, 6.0, peer_rank="30/50"),
            _fund("D", 0.1, 22.0, 3.0, 6.0, 2.5, 3.0, peer_rank="45/50")]


def test_by_code_monotonic_best_to_worst():
    from ui.helpers.fund_grp_health.quality import quality_score_by_code
    cap = {"A": {"操盤評分": 90}, "B": {"操盤評分": 70},
           "C": {"操盤評分": 50}, "D": {"操盤評分": 30}}
    res = quality_score_by_code(_abcd(), capture_map=cap)
    scores = {c: float(res[c]["相對品質分"].split(" ")[0]) for c in "ABCD"}
    assert scores["A"] > scores["B"] > scores["C"] > scores["D"]   # 全面最好 → 分最高
    assert "本組 4 檔" in res["A"]["相對品質分"]                    # 標樣本數


def test_by_code_small_sample_flag():
    from ui.helpers.fund_grp_health.quality import quality_score_by_code
    # 3 檔 < PEER_QUARTILE_MIN_N(4)→ 「・僅參考」
    res = quality_score_by_code(_abcd()[:3])
    assert "僅參考" in res["A"]["相對品質分"]


def test_by_code_missing_metrics_is_insufficient():
    from ui.helpers.fund_grp_health.quality import quality_score_by_code
    res = quality_score_by_code([{"code": "X", "metrics": {}, "moneydj_raw": {}}])
    assert res["X"]["相對品質分"] == "⬜ 資料不足"


def test_by_code_empty_and_no_code():
    from ui.helpers.fund_grp_health.quality import quality_score_by_code
    assert quality_score_by_code([]) == {}
    assert quality_score_by_code([{"metrics": {}}]) == {}          # 無 code → skip


def test_column_registered_in_schema():
    from ui.helpers.fund_grp_health.unified import BATCH_UNIFIED_COLUMNS, _UNIFIED_FRONT
    assert ("相對品質分", "extra") in _UNIFIED_FRONT
    assert "相對品質分" in BATCH_UNIFIED_COLUMNS                    # 自動流入批次寬表


def test_capture_map_none_drops_操盤_gracefully():
    from ui.helpers.fund_grp_health.quality import quality_score_by_code
    # 無 capture_map → 操盤因子退出分母,其餘 5 因子仍給分(§1)
    res = quality_score_by_code(_abcd(), capture_map=None)
    assert res["A"]["相對品質分"] != "⬜ 資料不足"


def test_return_factor_pure_large_universe_no_small_fallback():
    """v19.496 稽核修:報酬因子**純** MoneyDJ 大母體 —— 無官方排名 → 退出(None),
    不退小 universe(§4.1 同表不混大/小母體)。"""
    from ui.helpers.fund_grp_health.quality import _assemble_factor_pcts
    # 兩檔皆無 peer_rank(peer_compare 缺)→ 報酬 = None(退出,非小 universe rank)
    funds = [_fund("A", 1.5, 8, 12, 6, 1, 12), _fund("B", 0.5, 16, 6, 6, 2, 6)]
    pcts, _ = _assemble_factor_pcts(funds, None)
    assert pcts["A"]["報酬"] is None and pcts["B"]["報酬"] is None
    # 有 peer_rank「1/50」(第1名)→ 報酬 percentile 0(最佳)
    pcts2, _ = _assemble_factor_pcts([_fund("A", 1.5, 8, 12, 6, 1, 12, peer_rank="1/50")], None)
    assert pcts2["A"]["報酬"] == 0.0
