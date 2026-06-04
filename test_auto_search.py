"""test_auto_search.py — v19.10 AutoSearch unit tests."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from services.auto_search import (
    SearchJob,
    SearchResult,
    _global_best,
    _next_eval,
    _top_k_factors,
    auto_search_iter,
    composite_score,
    create_job,
    estimate_total_evals,
    factor_pool_hash,
    resume_or_create,
    top_n_winners,
)
from services.auto_search_store_local import LocalJsonSearchStore


def _mk_result(
    run_id: str = "r1", phase: str = "univariate",
    subset: list[str] | None = None, weights: dict | None = None,
    oos_f1: float = 0.0, plateau: float = 0.0,
    n_cross: int = 0, composite: float = 0.0,
) -> SearchResult:
    return SearchResult(
        run_id=run_id, phase=phase, subset=subset or ["VIX"],
        weights=weights or {"VIX": 1.0}, oos_f1=oos_f1, oos_sharpe=0.0,
        plateau_score=plateau, train_f1=0.0, n_crossings=n_cross,
        n_folds=0, composite=composite, elapsed_sec=0.1, ts="2026-06-05T00:00:00",
    )


# ════════════════════════════════════════════════════════════════
# Composite scoring
# ════════════════════════════════════════════════════════════════
def test_composite_zero_when_oos_f1_zero():
    assert composite_score(0.0, 0.5, 10) == 0.0


def test_composite_zero_when_n_crossings_zero():
    assert composite_score(0.5, 0.5, 0) == 0.0


def test_composite_clips_negative_plateau():
    assert composite_score(0.5, -0.3, 10) == 0.0


def test_composite_positive_when_all_positive():
    s = composite_score(0.4, 0.2, 10)
    assert s > 0


# ════════════════════════════════════════════════════════════════
# Hashing & estimation
# ════════════════════════════════════════════════════════════════
def test_factor_pool_hash_deterministic():
    h1 = factor_pool_hash(["VIX", "HY_SPREAD", "T10Y2Y"])
    h2 = factor_pool_hash(["T10Y2Y", "VIX", "HY_SPREAD"])
    assert h1 == h2  # sort-invariant


def test_factor_pool_hash_different_pools():
    assert factor_pool_hash(["VIX"]) != factor_pool_hash(["UNRATE"])


def test_estimate_total_evals_top_k_10_max_size_5():
    n = estimate_total_evals(top_k=10, max_size=5)
    # univariate=10 + greedy 9+8+7+6 + refine 5*5
    assert n == 10 + 30 + 25


# ════════════════════════════════════════════════════════════════
# Helper functions
# ════════════════════════════════════════════════════════════════
def test_top_k_factors_sorted_by_oos_f1():
    results = [
        _mk_result(subset=["A"], oos_f1=0.1),
        _mk_result(subset=["B"], oos_f1=0.5),
        _mk_result(subset=["C"], oos_f1=0.3),
    ]
    top2 = _top_k_factors(results, 2)
    assert top2 == ["B", "C"]


def test_global_best_picks_max_composite():
    results = [
        _mk_result(subset=["A"], composite=0.1),
        _mk_result(subset=["B", "C"], composite=0.5),
        _mk_result(subset=["D"], composite=0.3),
    ]
    assert _global_best(results) == ["B", "C"]


def test_global_best_returns_none_when_all_zero():
    results = [_mk_result(subset=["A"], composite=0.0)]
    assert _global_best(results) is None


def test_top_n_winners_dedup_by_sorted_subset():
    results = [
        _mk_result(subset=["A", "B"], composite=0.5),
        _mk_result(subset=["B", "A"], composite=0.3),  # same set, lower
        _mk_result(subset=["C"], composite=0.1),
    ]
    out = top_n_winners(results, n=10)
    assert len(out) == 2
    assert out[0].composite == 0.5


# ════════════════════════════════════════════════════════════════
# LocalJsonSearchStore — CRUD roundtrip
# ════════════════════════════════════════════════════════════════
def test_local_store_save_load_job(tmp_path: Path):
    store = LocalJsonSearchStore(base_dir=tmp_path)
    job = create_job(["VIX", "UNRATE", "PMI"], top_k=3, max_size=2)
    store.save_job(job)
    loaded = store.load_job(job.run_id)
    assert loaded is not None
    assert loaded.run_id == job.run_id
    assert loaded.factor_pool == ["VIX", "UNRATE", "PMI"]
    assert loaded.status == "running"


def test_local_store_append_results(tmp_path: Path):
    store = LocalJsonSearchStore(base_dir=tmp_path)
    job = create_job(["VIX", "UNRATE"], top_k=2, max_size=2)
    store.save_job(job)
    store.append_result(_mk_result(run_id=job.run_id, subset=["VIX"], oos_f1=0.3))
    store.append_result(_mk_result(run_id=job.run_id, subset=["UNRATE"], oos_f1=0.1))
    results = store.list_results(job.run_id)
    assert len(results) == 2
    assert [r.subset[0] for r in results] == ["VIX", "UNRATE"]


def test_local_store_list_jobs(tmp_path: Path):
    store = LocalJsonSearchStore(base_dir=tmp_path)
    j1 = create_job(["VIX"], top_k=1, max_size=1)
    j2 = create_job(["UNRATE"], top_k=1, max_size=1)
    # 確保 run_id 不同（差 1ms 應該夠）
    j2.run_id = j1.run_id + "_2"
    store.save_job(j1)
    store.save_job(j2)
    jobs = store.list_jobs()
    assert len(jobs) == 2


def test_local_store_delete_job(tmp_path: Path):
    store = LocalJsonSearchStore(base_dir=tmp_path)
    job = create_job(["VIX"], top_k=1, max_size=1)
    store.save_job(job)
    store.delete_job(job.run_id)
    assert store.load_job(job.run_id) is None


def test_local_store_corrupt_json_returns_none(tmp_path: Path):
    store = LocalJsonSearchStore(base_dir=tmp_path)
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json")
    assert store.load_job("bad") is None


# ════════════════════════════════════════════════════════════════
# Resume logic
# ════════════════════════════════════════════════════════════════
def test_resume_or_create_returns_existing_when_same_pool(tmp_path: Path):
    store = LocalJsonSearchStore(base_dir=tmp_path)
    j1 = resume_or_create(store, ["VIX", "UNRATE"], top_k=2, max_size=2)
    j2 = resume_or_create(store, ["UNRATE", "VIX"], top_k=2, max_size=2)  # 順序不同
    assert j1.run_id == j2.run_id


def test_resume_or_create_creates_new_for_different_pool(tmp_path: Path):
    store = LocalJsonSearchStore(base_dir=tmp_path)
    j1 = resume_or_create(store, ["VIX"], top_k=1, max_size=1)
    j2 = resume_or_create(store, ["UNRATE"], top_k=1, max_size=1)
    assert j1.run_id != j2.run_id


def test_resume_or_create_creates_new_when_existing_is_done(tmp_path: Path):
    store = LocalJsonSearchStore(base_dir=tmp_path)
    j1 = resume_or_create(store, ["VIX"], top_k=1, max_size=1)
    j1.status = "done"
    store.save_job(j1)
    j2 = resume_or_create(store, ["VIX"], top_k=1, max_size=1)
    assert j2.run_id != j1.run_id


# ════════════════════════════════════════════════════════════════
# Phase progression
# ════════════════════════════════════════════════════════════════
def test_next_eval_univariate_first():
    job = create_job(["VIX", "UNRATE", "PMI"], top_k=3, max_size=2)
    nxt = _next_eval(job, existing=[])
    assert nxt is not None
    subset, phase = nxt
    assert phase == "univariate"
    assert len(subset) == 1


def test_next_eval_advances_to_greedy_after_all_univariate():
    pool = ["VIX", "UNRATE", "PMI"]
    job = create_job(pool, top_k=3, max_size=2)
    existing = [
        _mk_result(subset=["VIX"], oos_f1=0.5, composite=0.3),
        _mk_result(subset=["UNRATE"], oos_f1=0.3, composite=0.1),
        _mk_result(subset=["PMI"], oos_f1=0.2, composite=0.05),
    ]
    nxt = _next_eval(job, existing)
    assert nxt is not None
    subset, phase = nxt
    assert phase == "greedy"
    assert len(subset) == 2
    assert "VIX" in subset  # best univariate


def test_next_eval_returns_none_when_all_done():
    """Pool 太小 → 全部跑完應該回 None."""
    pool = ["A", "B"]
    job = create_job(pool, top_k=2, max_size=2)
    # 跑完 univariate + greedy + refine（pool 太小 refine 沒事做）
    existing = [
        _mk_result(subset=["A"], phase="univariate", oos_f1=0.5, composite=0.3),
        _mk_result(subset=["B"], phase="univariate", oos_f1=0.3, composite=0.1),
        _mk_result(subset=["A", "B"], phase="greedy", oos_f1=0.6, composite=0.4),
    ]
    job.next_phase = "refine"
    job.selected_seed = ["A", "B"]
    nxt = _next_eval(job, existing)
    assert nxt is None


# ════════════════════════════════════════════════════════════════
# auto_search_iter — pause + time budget
# ════════════════════════════════════════════════════════════════
def test_auto_search_iter_respects_pause_check(tmp_path: Path, monkeypatch):
    """pause_check() → True → generator 第 1 輪就退出，job 標 paused."""
    store = LocalJsonSearchStore(base_dir=tmp_path)
    job = create_job(["VIX"], top_k=1, max_size=1)
    store.save_job(job)

    gen = auto_search_iter(
        job, store,
        series_by_key={"VIX": pd.Series(dtype=float)},
        returns=pd.Series(dtype=float),
        events=[],
        time_budget_sec=60.0,
        pause_check=lambda: True,
    )
    results = list(gen)
    assert results == []
    reloaded = store.load_job(job.run_id)
    assert reloaded.status == "paused"


def test_auto_search_iter_respects_zero_time_budget(tmp_path: Path):
    """time_budget=0 → 第 1 輪 budget check 就退出."""
    store = LocalJsonSearchStore(base_dir=tmp_path)
    job = create_job(["VIX"], top_k=1, max_size=1)
    store.save_job(job)

    gen = auto_search_iter(
        job, store,
        series_by_key={"VIX": pd.Series(dtype=float)},
        returns=pd.Series(dtype=float),
        events=[],
        time_budget_sec=0.0,
    )
    results = list(gen)
    assert results == []
    reloaded = store.load_job(job.run_id)
    assert reloaded.status == "paused"


# ════════════════════════════════════════════════════════════════
# SearchJob serialization
# ════════════════════════════════════════════════════════════════
def test_search_job_roundtrip():
    job = create_job(["VIX", "UNRATE"], top_k=2, max_size=3, note="test")
    d = job.to_dict()
    j2 = SearchJob.from_dict(d)
    assert j2.run_id == job.run_id
    assert j2.factor_pool == job.factor_pool
    assert j2.top_k == job.top_k


def test_search_result_roundtrip():
    r = _mk_result(subset=["A", "B"], weights={"A": 0.5, "B": 0.5}, oos_f1=0.42)
    d = r.to_dict()
    r2 = SearchResult.from_dict(d)
    assert r2.run_id == r.run_id
    assert r2.subset == r.subset
    assert r2.oos_f1 == r.oos_f1
