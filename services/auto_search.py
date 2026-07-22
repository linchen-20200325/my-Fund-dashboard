"""services/auto_search.py — v19.10 AutoSearch

自動搜尋 (因子組合, 權重) — 跨 session 可暫停 / 可續跑 / 進度持久化。

設計：
- 演算法：hybrid greedy forward selection + best-subset neighborhood swap
- Store：Protocol 介面 + GS / Local JSON 兩種實作（自動 fallback）
- Worker：generator pattern，每完成 1 個 subset 立刻 yield → caller 寫 store
- 時間預算：每次跑滿 N 分鐘自動暫停，狀態存 store，下次 resume 從 done 接續
"""
from __future__ import annotations

import hashlib
import math
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone  # v19.74 W1-D: timezone for utcnow() migration
from typing import Iterator, Literal, Optional, Protocol

import numpy as np
import pandas as pd

from services.multi_factor_optimization import (
    DEFAULT_GRID_STEP,
    DEFAULT_LAMBDA_STD,
    DEFAULT_MIN_CROSSINGS,
    DEFAULT_PLATEAU_RADIUS,
    DEFAULT_TEST_MONTHS,
    DEFAULT_THRESHOLD,
    DEFAULT_TRAIN_MONTHS,
    FACTOR_POOL_BY_KEY,
    CrisisEvent,
    FactorSpec,
    evaluate_plateau,
    find_plateau_optimum,
    grid_search_performance,
    walk_forward_validate,
)

JobStatus = Literal["running", "paused", "done", "cancelled"]
Phase = Literal["univariate", "greedy", "refine"]


# ════════════════════════════════════════════════════════════════
# Dataclasses
# ════════════════════════════════════════════════════════════════
@dataclass
class SearchJob:
    """單次搜尋的 manifest — 一列 GS / 一檔 local JSON 對應一個 job."""

    run_id: str
    factor_pool_hash: str
    factor_pool: list[str]
    top_k: int
    max_size: int
    total: int  # 預估總 eval 次數
    done: int  # 已完成 eval 次數
    status: JobStatus
    started_at: str
    last_update: str
    next_phase: Phase = "univariate"
    selected_seed: list[str] = field(default_factory=list)
    note: str = ""
    lead_time_min: int = 30
    lead_time_max: int = 90

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> SearchJob:
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})


@dataclass
class SearchResult:
    """單一 subset eval 結果 — 一列 GS / 一個 entry local JSON."""

    run_id: str
    phase: Phase
    subset: list[str]
    weights: dict[str, float]
    oos_f1: float
    oos_sharpe: float
    plateau_score: float
    train_f1: float
    n_crossings: int
    n_folds: int
    composite: float
    elapsed_sec: float
    ts: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> SearchResult:
        return cls(**{k: d.get(k) for k in cls.__dataclass_fields__})


# ════════════════════════════════════════════════════════════════
# Store Protocol
# ════════════════════════════════════════════════════════════════
class SearchStore(Protocol):
    """跨 session 持久化抽象 — GS / Local JSON 兩種實作."""

    backend_name: str

    def list_jobs(self) -> list[SearchJob]: ...
    def load_job(self, run_id: str) -> Optional[SearchJob]: ...
    def save_job(self, job: SearchJob) -> None: ...
    def append_result(self, result: SearchResult) -> None: ...
    def list_results(self, run_id: str) -> list[SearchResult]: ...
    def delete_job(self, run_id: str) -> None: ...


def get_default_store() -> SearchStore:
    """優先 GS，fallback local JSON — 不 raise，永遠回可用 store."""
    try:
        from services.auto_search_store_gs import GoogleSheetsSearchStore

        store = GoogleSheetsSearchStore()
        if store.is_available():
            return store
    except Exception:
        pass
    from services.auto_search_store_local import LocalJsonSearchStore

    return LocalJsonSearchStore()


# ════════════════════════════════════════════════════════════════
# Scoring
# ════════════════════════════════════════════════════════════════
FREQ_BONUS: dict[str, float] = {"daily": 1.0, "weekly": 0.9, "monthly": 0.75}


def composite_score(
    oos_f1: float, plateau_score: float, n_crossings: int,
    freq_bonus: float = 1.0,
) -> float:
    """綜合分數：OOS_F1 × max(plateau, 0) × log1p(n_crossings) × freq_bonus.

    - n_crossings=0 → log1p=0 → composite=0（懲罰沒訊號的）
    - plateau<0 → clip 0（高原退化解不該被選）
    - freq_bonus：v19.11，子集最慢頻率因子的 bonus（daily 1.0 / weekly 0.9 / monthly 0.75）
    """
    p = max(float(plateau_score), 0.0)
    nc = max(int(n_crossings), 0)
    return float(oos_f1) * p * math.log1p(nc) * float(freq_bonus)


def freq_bonus_for_subset(subset: list[str]) -> float:
    """子集中**最慢頻率**因子的 bonus — 一顆月頻就拉低整組（軟懲罰，不剔除）."""
    bonuses = []
    for k in subset:
        spec = FACTOR_POOL_BY_KEY.get(k)
        freq = getattr(spec, "frequency", "daily") if spec else "daily"
        bonuses.append(FREQ_BONUS.get(freq, 1.0))
    return min(bonuses) if bonuses else 1.0


def factor_pool_hash(keys: list[str]) -> str:
    """sorted keys → SHA1 prefix，給 resume 判斷 factor pool 一致性."""
    h = hashlib.sha1(",".join(sorted(keys)).encode("utf-8")).hexdigest()
    return h[:12]


def job_signature(
    keys: list[str], min_forward_days: int, max_forward_days: int,
) -> str:
    """v19.12：含 lead time 的 job 簽章 — 不同 lead time → 不同 job，避免長/短期 pool 互污染。"""
    payload = (
        f"{factor_pool_hash(keys)}|lt={int(min_forward_days)}-{int(max_forward_days)}"
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]


# ════════════════════════════════════════════════════════════════
# Single subset evaluator
# ════════════════════════════════════════════════════════════════
def evaluate_subset(
    subset: list[str],
    series_by_key: dict[str, pd.Series],
    returns: pd.Series,
    events: list[CrisisEvent],
    specs_by_key: dict[str, FactorSpec],
    *,
    phase: Phase,
    run_id: str,
    threshold: float = DEFAULT_THRESHOLD,
    step: float = DEFAULT_GRID_STEP,
    radius: int = DEFAULT_PLATEAU_RADIUS,
    lambda_std: float = DEFAULT_LAMBDA_STD,
    metric: Literal["f1", "sharpe"] = "f1",
    min_crossings: int = DEFAULT_MIN_CROSSINGS,
    train_months: int = DEFAULT_TRAIN_MONTHS,
    test_months: int = DEFAULT_TEST_MONTHS,
    min_forward_days: int = 30,
    max_forward_days: int = 90,
) -> SearchResult:
    """單一 subset 跑 grid+plateau+walk-forward → SearchResult."""
    start = time.perf_counter()
    sel_series = {k: series_by_key[k] for k in subset if k in series_by_key}

    if len(sel_series) < len(subset):
        return _empty_result(
            run_id, phase, subset, start, note_zero=True,
        )

    if len(subset) == 1:
        # 單因子：直接固定 weight=1.0 跑 walk-forward
        weights = {subset[0]: 1.0}
        plateau_val = 0.0
        train_f1 = 0.0
        n_cross = 0
    else:
        grid = grid_search_performance(
            sel_series, returns, events, list(subset),
            threshold=threshold, step=step, specs_by_key=specs_by_key,
            min_forward_days=min_forward_days,
            max_forward_days=max_forward_days,
        )
        if not grid.get("combos"):
            return _empty_result(run_id, phase, subset, start)
        plateau_arr = evaluate_plateau(
            grid, list(subset), step=step, radius=radius,
            lambda_std=lambda_std, metric=metric, min_crossings=min_crossings,
        )
        opt = find_plateau_optimum(grid, plateau_arr)
        if not opt.get("weights"):
            return _empty_result(run_id, phase, subset, start)
        weights = opt["weights"]
        plateau_val = float(opt.get("plateau_score", 0.0))
        train_f1 = float(opt.get(metric, 0.0))
        idx = int(opt.get("argmax_idx", -1))
        n_cross_arr = grid.get("n_crossings", np.array([]))
        n_cross = int(n_cross_arr[idx]) if 0 <= idx < len(n_cross_arr) else 0

    wf = walk_forward_validate(
        sel_series, returns, events, list(subset),
        train_months=train_months, test_months=test_months,
        threshold=threshold, step=step, radius=radius,
        lambda_std=lambda_std, metric=metric,
        specs_by_key=specs_by_key,
        min_forward_days=min_forward_days,
        max_forward_days=max_forward_days,
    )
    oos_f1 = float(wf.get("oos_f1", 0.0))
    oos_sharpe = float(wf.get("oos_sharpe", 0.0))
    n_folds = int(wf.get("n_folds", 0))

    elapsed = time.perf_counter() - start
    fb = freq_bonus_for_subset(list(subset))
    return SearchResult(
        run_id=run_id,
        phase=phase,
        subset=list(subset),
        weights=weights,
        oos_f1=oos_f1,
        oos_sharpe=oos_sharpe,
        plateau_score=plateau_val,
        train_f1=train_f1,
        n_crossings=n_cross,
        n_folds=n_folds,
        composite=composite_score(oos_f1, plateau_val, n_cross, fb),
        elapsed_sec=elapsed,
        ts=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


def _empty_result(
    run_id: str,
    phase: Phase,
    subset: list[str],
    start: float,
    note_zero: bool = False,
) -> SearchResult:
    """無法評估的 subset 回 0 result（不 raise，保 generator 不中斷）."""
    return SearchResult(
        run_id=run_id, phase=phase, subset=list(subset), weights={},
        oos_f1=0.0, oos_sharpe=0.0, plateau_score=0.0, train_f1=0.0,
        n_crossings=0, n_folds=0, composite=0.0,
        elapsed_sec=time.perf_counter() - start,
        ts=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


# v19.378 D1:_plan_univariate / _plan_greedy / _plan_refine 拔毒(全 repo 0 caller,
# 只有 def 自身;plan generator 從未接線)。estimate_total_evals 保留(progress bar 用)。
def estimate_total_evals(top_k: int, max_size: int) -> int:
    """估算 hybrid 總 eval 次數（給 progress bar 用）."""
    univariate = top_k
    greedy = sum(max(top_k - i, 0) for i in range(1, max_size))
    refine = max_size * max(top_k - max_size, 0)
    return univariate + greedy + refine


# ════════════════════════════════════════════════════════════════
# Job lifecycle
# ════════════════════════════════════════════════════════════════
def create_job(
    factor_pool: list[str],
    top_k: int = 10,
    max_size: int = 5,
    note: str = "",
    *,
    min_forward_days: int = 30,
    max_forward_days: int = 90,
) -> SearchJob:
    """新建 job — run_id = 時間戳 + job_signature 短碼（含 lead time）."""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    sig = job_signature(factor_pool, min_forward_days, max_forward_days)
    run_id = f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}_{sig[:6]}"
    return SearchJob(
        run_id=run_id,
        factor_pool_hash=sig,
        factor_pool=list(factor_pool),
        top_k=int(top_k),
        max_size=int(max_size),
        total=estimate_total_evals(top_k, max_size),
        done=0,
        status="running",
        started_at=now,
        last_update=now,
        next_phase="univariate",
        selected_seed=[],
        note=note,
        lead_time_min=int(min_forward_days),
        lead_time_max=int(max_forward_days),
    )


def resume_or_create(
    store: SearchStore,
    factor_pool: list[str],
    top_k: int = 10,
    max_size: int = 5,
    *,
    min_forward_days: int = 30,
    max_forward_days: int = 90,
) -> SearchJob:
    """同 factor_pool + lead time + top_k + max_size 的 paused/running job → resume，否則新建。

    v19.12：sig 改用 job_signature（含 lead time），避免短期 / 長期 pool 共用同 job。
    """
    sig = job_signature(factor_pool, min_forward_days, max_forward_days)
    jobs = store.list_jobs()
    for job in jobs:
        if (
            job.factor_pool_hash == sig
            and job.top_k == top_k
            and job.max_size == max_size
            and job.status in ("running", "paused")
        ):
            return job
    job = create_job(
        factor_pool, top_k, max_size,
        min_forward_days=min_forward_days,
        max_forward_days=max_forward_days,
    )
    store.save_job(job)
    return job


# ════════════════════════════════════════════════════════════════
# Main iterator — 每次跑 N 分鐘 / 跑到完
# ════════════════════════════════════════════════════════════════
def auto_search_iter(
    job: SearchJob,
    store: SearchStore,
    series_by_key: dict[str, pd.Series],
    returns: pd.Series,
    events: list[CrisisEvent],
    *,
    time_budget_sec: float = 300.0,
    eval_kwargs: Optional[dict] = None,
    pause_check: Optional[callable] = None,
) -> Iterator[SearchResult]:
    """主 generator — 每完成 1 個 subset yield 1 個 result，並寫 store.

    終止條件（任一）：
    - 時間預算用完
    - pause_check() 回 True
    - 所有 phase 跑完 (next_phase = "done")
    """
    eval_kwargs = eval_kwargs or {}
    specs = {k: FACTOR_POOL_BY_KEY[k] for k in job.factor_pool if k in FACTOR_POOL_BY_KEY}
    start = time.perf_counter()

    while job.status == "running":
        if time.perf_counter() - start >= time_budget_sec:
            job.status = "paused"
            job.note = "time budget reached"
            store.save_job(job)
            return
        if pause_check and pause_check():
            job.status = "paused"
            job.note = "user paused"
            store.save_job(job)
            return

        existing = store.list_results(job.run_id)
        next_plan = _next_eval(job, existing)
        if next_plan is None:
            job.status = "done"
            job.last_update = datetime.now(timezone.utc).isoformat(timespec="seconds")
            store.save_job(job)
            return

        subset, phase = next_plan
        result = evaluate_subset(
            subset, series_by_key, returns, events, specs,
            phase=phase, run_id=job.run_id, **eval_kwargs,
        )
        store.append_result(result)
        job.done += 1
        job.last_update = datetime.now(timezone.utc).isoformat(timespec="seconds")
        _advance_phase(job, existing + [result])
        store.save_job(job)
        yield result


def _next_eval(
    job: SearchJob, existing: list[SearchResult],
) -> Optional[tuple[list[str], Phase]]:
    """根據 job.next_phase + existing results 推算下一個要跑的 subset.

    - univariate：每個 pool key 跑 1 次
    - greedy：在 selected_seed 上加 1 個（pick 自 top_k 預篩後池）
    - refine：對 best subset 各 position 與池內 swap
    - 全跑完 → None
    """
    tried = {tuple(r.subset) for r in existing}

    if job.next_phase == "univariate":
        for k in job.factor_pool:
            if (k,) not in tried:
                return [k], "univariate"
        return _next_eval_greedy(job, existing, tried)

    if job.next_phase == "greedy":
        return _next_eval_greedy(job, existing, tried)

    if job.next_phase == "refine":
        return _next_eval_refine(job, existing, tried)

    return None


def _next_eval_greedy(
    job: SearchJob,
    existing: list[SearchResult],
    tried: set[tuple[str, ...]],
) -> Optional[tuple[list[str], Phase]]:
    """Greedy phase：根據 univariate top_K 預篩 → 逐輪加最佳."""
    univariate = [r for r in existing if r.phase == "univariate"]
    if len(univariate) < len(job.factor_pool):
        # 還在 univariate 階段
        return None

    top_k_pool = _top_k_factors(univariate, job.top_k)

    # 推算當前 seed：取最高 composite 的 greedy result（含 univariate 最佳 size=1）
    greedy_done = [r for r in existing if r.phase == "greedy"]
    all_seed_candidates = univariate + greedy_done
    if not all_seed_candidates:
        return None

    # 各 size 取 best
    by_size: dict[int, SearchResult] = {}
    for r in all_seed_candidates:
        n = len(r.subset)
        if n not in by_size or r.composite > by_size[n].composite:
            by_size[n] = r

    # 找下一個要做的 size
    next_size = None
    for s in range(2, job.max_size + 1):
        if s not in by_size:
            next_size = s
            break
        # size s 已有，但要確認 round 跑完（所有 top_K 候選都試過）
        seed = by_size[s - 1].subset if (s - 1) in by_size else []
        round_candidates = [k for k in top_k_pool if k not in seed]
        round_subsets = [tuple(sorted(seed + [k])) for k in round_candidates]
        round_tried = {tuple(sorted(r.subset)) for r in greedy_done if len(r.subset) == s}
        if not all(rs in round_tried for rs in round_subsets):
            next_size = s
            break

    if next_size is None:
        # Greedy 全跑完，進 refine
        job.next_phase = "refine"
        best_subset = _global_best(existing)
        job.selected_seed = list(best_subset) if best_subset else []
        return _next_eval_refine(job, existing, tried)

    seed = by_size[next_size - 1].subset if (next_size - 1) in by_size else []
    for k in top_k_pool:
        if k in seed:
            continue
        cand_subset = seed + [k]
        if tuple(cand_subset) not in tried and tuple(sorted(cand_subset)) not in {
            tuple(sorted(t)) for t in tried
        }:
            job.next_phase = "greedy"
            return cand_subset, "greedy"

    job.next_phase = "refine"
    best_subset = _global_best(existing)
    job.selected_seed = list(best_subset) if best_subset else []
    return _next_eval_refine(job, existing, tried)


def _next_eval_refine(
    job: SearchJob,
    existing: list[SearchResult],
    tried: set[tuple[str, ...]],
) -> Optional[tuple[list[str], Phase]]:
    """Refine phase：對全域 best subset 做 swap."""
    best_subset = job.selected_seed or list(_global_best(existing) or [])
    if not best_subset:
        return None
    if len(best_subset) < 2:
        return None

    univariate = [r for r in existing if r.phase == "univariate"]
    top_k_pool = _top_k_factors(univariate, job.top_k) if univariate else job.factor_pool

    for i in range(len(best_subset)):
        for cand in top_k_pool:
            if cand in best_subset:
                continue
            swapped = best_subset[:i] + [cand] + best_subset[i + 1:]
            if tuple(sorted(swapped)) in {tuple(sorted(t)) for t in tried}:
                continue
            return swapped, "refine"
    return None


def _top_k_factors(univariate_results: list[SearchResult], top_k: int) -> list[str]:
    """從 univariate results 取 OOS_F1 top_K 的 factor keys."""
    sorted_r = sorted(univariate_results, key=lambda r: -r.oos_f1)
    return [r.subset[0] for r in sorted_r[:top_k]]


def _global_best(results: list[SearchResult]) -> Optional[list[str]]:
    """全 results 取 composite 最高的 subset."""
    if not results:
        return None
    best = max(results, key=lambda r: r.composite)
    return list(best.subset) if best.composite > 0 else None


def _advance_phase(job: SearchJob, results: list[SearchResult]) -> None:
    """根據已有 results 推進 job.next_phase（在 _next_eval 已寫的補強）."""
    n_univariate = sum(1 for r in results if r.phase == "univariate")
    if job.next_phase == "univariate" and n_univariate >= len(job.factor_pool):
        job.next_phase = "greedy"


def top_n_winners(
    results: list[SearchResult], n: int = 10, by: str = "composite",
) -> list[SearchResult]:
    """從 results 取 top-N（去重複 subset，按 sorted tuple 識別）."""
    seen: set[tuple[str, ...]] = set()
    unique: list[SearchResult] = []
    sorted_r = sorted(results, key=lambda r: -getattr(r, by, 0.0))
    for r in sorted_r:
        key = tuple(sorted(r.subset))
        if key in seen:
            continue
        seen.add(key)
        unique.append(r)
        if len(unique) >= n:
            break
    return unique


__all__ = [
    "SearchJob",
    "SearchResult",
    "SearchStore",
    "Phase",
    "JobStatus",
    "FREQ_BONUS",
    "get_default_store",
    "composite_score",
    "freq_bonus_for_subset",
    "factor_pool_hash",
    "evaluate_subset",
    "estimate_total_evals",
    "create_job",
    "resume_or_create",
    "auto_search_iter",
    "top_n_winners",
]
