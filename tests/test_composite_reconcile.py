"""tests/test_composite_reconcile.py — v19.367 6/8:健康度雙演算法對帳(F-RECON-1 收尾)。

守:
- agree:多數指標同向 + 加權同向 → status=agree
- disagree:單一大權重負指標拖著加權總分轉負、但多數指標為正 → 抓出反向(⚠️ 核心價值)
- neutral_mix:投票 60/40 內(|net_ratio|<=0.2)→ 中性,非衝突
- no_data:空 dict / 全壞值 → §1 誠實回 no_data
- 投票不吃權重(方法學獨立):同一組 score 改權重,vote_net_ratio 不變
"""
from __future__ import annotations

import pytest

from services.macro.composite_score import (
    calculate_composite_score,
    reconcile_composite_score,
)


def _ind(entries):
    """entries: list[(score, weight)] → ind dict。"""
    return {f"i{n}": {"score": s, "weight": w} for n, (s, w) in enumerate(entries)}


def test_agree_when_majority_and_weighted_same_direction():
    ind = _ind([(10, 1)] * 8 + [(-1, 1)] * 2)    # 加權 +78(遠超任何合理樂觀線);8多/2空 net+0.6
    rc = reconcile_composite_score(ind)
    assert rc["status"] == "agree"
    assert rc["dir_weighted"] == "pos" and rc["dir_vote"] == "pos"
    assert rc["n_pos"] == 8 and rc["n_neg"] == 2


def test_disagree_single_heavy_weight_drags_total():
    """核心場景:1 個大權重負指標(-2×20=-40)拖翻 9 個小正指標(+1×1 各) →
    加權大負(neg)但投票 9多/1空(pos)→ disagree ⚠️。"""
    ind = _ind([(1, 1)] * 9 + [(-2, 60)])        # 加權 9-120=-111(遠低任何合理悲觀線)
    rc = reconcile_composite_score(ind)
    assert rc["dir_weighted"] == "neg" and rc["dir_vote"] == "pos"
    assert rc["status"] == "disagree"
    assert "反向" in rc["note"]


def test_neutral_mix_weak_vote():
    """投票 6多/4空 → net_ratio=0.2 在中性帶內 → vote=neu;加權強正 → neutral_mix。"""
    ind = _ind([(30, 1)] * 6 + [(-3, 1)] * 4)    # 加權 +168(pos);net (6-4)/10=0.2 → neu
    rc = reconcile_composite_score(ind)
    assert rc["dir_vote"] == "neu"
    assert rc["status"] == "neutral_mix"


def test_no_data_honest():
    assert reconcile_composite_score({})["status"] == "no_data"
    assert reconcile_composite_score({"x": "not-a-dict"})["status"] == "no_data"
    assert reconcile_composite_score(None)["status"] == "no_data"


def test_vote_ignores_weights_methodological_independence():
    """同 score 不同 weight → 投票結果不變(第二演算法真的獨立於權重)。"""
    a = reconcile_composite_score(_ind([(1, 1)] * 5 + [(-1, 1)] * 2))
    b = reconcile_composite_score(_ind([(1, 99)] * 5 + [(-1, 0.01)] * 2))
    assert a["vote_net_ratio"] == b["vote_net_ratio"]
    assert a["n_pos"] == b["n_pos"] == 5


def test_weighted_total_matches_primary_algorithm():
    """對帳 dict 的 weighted_total 必須 == 主演算法輸出(同一 SSOT,不重算出岔)。"""
    ind = _ind([(2, 3), (-1, 2)])
    rc = reconcile_composite_score(ind)
    assert rc["weighted_total"] == calculate_composite_score(ind)
