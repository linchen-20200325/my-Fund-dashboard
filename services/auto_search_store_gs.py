"""services/auto_search_store_gs.py — v19.10 AutoSearch Google Sheets store

跨 session resume — 把 jobs + results 寫到 Streamlit secrets 指向的 GS sheet。

Worksheet schema：
- `_autosearch_jobs`：A1 row = headers；後續每列 = 1 job
- `_autosearch_results`：A1 row = headers；後續每列 = 1 subset eval result

複用 `macro_weights_store._gs_enabled` + `repositories.policy_repository.get_gspread_client`。
"""
from __future__ import annotations

import json
from typing import Any

from services.auto_search import SearchJob, SearchResult

_WS_JOBS = "_autosearch_jobs"
_WS_RESULTS = "_autosearch_results"

_JOB_HEADERS = [
    "run_id", "factor_pool_hash", "factor_pool_json", "top_k", "max_size",
    "total", "done", "status", "started_at", "last_update",
    "next_phase", "selected_seed_json", "note",
]
_RESULT_HEADERS = [
    "run_id", "phase", "subset_json", "weights_json",
    "oos_f1", "oos_sharpe", "plateau_score", "train_f1",
    "n_crossings", "n_folds", "composite", "elapsed_sec", "ts",
]


def _enabled() -> bool:
    """重用 macro.weights_store 的 secrets 偵測（同一份 GS sheet）."""
    try:
        from services.macro.weights_store import _gs_enabled

        return _gs_enabled()
    except Exception:
        return False


def _get_sheet():
    """開啟 v19.7 同份 Google Sheet（複用 secrets）.

    v19.197 P1-2:走 infra.config wrapper,本檔不再直 import streamlit。
    """
    from infra.config import require_secret
    from repositories.policy_repository import get_gspread_client

    creds = dict(require_secret("google_service_account"))
    sheet_id = require_secret("macro_weights_sheet_id")
    client = get_gspread_client(creds)
    return client.open_by_key(sheet_id)


def _get_worksheet(sh, name: str, headers: list[str]):
    """取得 worksheet，不存在則建立 + 寫 header row."""
    try:
        return sh.worksheet(name)
    except Exception:
        ws = sh.add_worksheet(title=name, rows=200, cols=len(headers))
        ws.update("A1", [headers])
        return ws


def _ensure_header(ws, headers: list[str]) -> None:
    """確保第 1 列是 headers（worksheet 已存在但欄位缺失時補）."""
    row1 = ws.row_values(1)
    if row1[: len(headers)] != headers:
        ws.update("A1", [headers])


def _job_to_row(job: SearchJob) -> list[Any]:
    return [
        job.run_id, job.factor_pool_hash,
        json.dumps(job.factor_pool, ensure_ascii=False),
        int(job.top_k), int(job.max_size), int(job.total), int(job.done),
        job.status, job.started_at, job.last_update,
        job.next_phase,
        json.dumps(job.selected_seed, ensure_ascii=False),
        job.note or "",
    ]


def _row_to_job(row: list[Any]) -> SearchJob | None:
    if len(row) < len(_JOB_HEADERS):
        row = list(row) + [""] * (len(_JOB_HEADERS) - len(row))
    try:
        return SearchJob(
            run_id=str(row[0]),
            factor_pool_hash=str(row[1]),
            factor_pool=json.loads(row[2] or "[]"),
            top_k=int(row[3] or 0),
            max_size=int(row[4] or 0),
            total=int(row[5] or 0),
            done=int(row[6] or 0),
            status=str(row[7] or "paused"),
            started_at=str(row[8] or ""),
            last_update=str(row[9] or ""),
            next_phase=str(row[10] or "univariate"),
            selected_seed=json.loads(row[11] or "[]"),
            note=str(row[12] or ""),
        )
    except (ValueError, json.JSONDecodeError):
        return None


def _result_to_row(r: SearchResult) -> list[Any]:
    return [
        r.run_id, r.phase,
        json.dumps(r.subset, ensure_ascii=False),
        json.dumps(r.weights, ensure_ascii=False),
        float(r.oos_f1), float(r.oos_sharpe), float(r.plateau_score),
        float(r.train_f1), int(r.n_crossings), int(r.n_folds),
        float(r.composite), float(r.elapsed_sec), r.ts,
    ]


def _row_to_result(row: list[Any]) -> SearchResult | None:
    if len(row) < len(_RESULT_HEADERS):
        row = list(row) + [""] * (len(_RESULT_HEADERS) - len(row))
    try:
        return SearchResult(
            run_id=str(row[0]),
            phase=str(row[1] or "univariate"),
            subset=json.loads(row[2] or "[]"),
            weights=json.loads(row[3] or "{}"),
            oos_f1=float(row[4] or 0),
            oos_sharpe=float(row[5] or 0),
            plateau_score=float(row[6] or 0),
            train_f1=float(row[7] or 0),
            n_crossings=int(row[8] or 0),
            n_folds=int(row[9] or 0),
            composite=float(row[10] or 0),
            elapsed_sec=float(row[11] or 0),
            ts=str(row[12] or ""),
        )
    except (ValueError, json.JSONDecodeError):
        return None


class GoogleSheetsSearchStore:
    """GS-backed store — 每 op 都會 lazy 開 sheet，無 client cache（簡化測試）."""

    backend_name = "google-sheets"

    def __init__(self) -> None:
        self._sh = None

    def is_available(self) -> bool:
        return _enabled()

    def _sheet(self):
        if self._sh is None:
            self._sh = _get_sheet()
        return self._sh

    def _jobs_ws(self):
        ws = _get_worksheet(self._sheet(), _WS_JOBS, _JOB_HEADERS)
        _ensure_header(ws, _JOB_HEADERS)
        return ws

    def _results_ws(self):
        ws = _get_worksheet(self._sheet(), _WS_RESULTS, _RESULT_HEADERS)
        _ensure_header(ws, _RESULT_HEADERS)
        return ws

    def list_jobs(self) -> list[SearchJob]:
        ws = self._jobs_ws()
        rows = ws.get_all_values()[1:]
        out: list[SearchJob] = []
        for row in rows:
            j = _row_to_job(row)
            if j is not None:
                out.append(j)
        return list(reversed(out))  # 新 → 舊

    def load_job(self, run_id: str) -> SearchJob | None:
        for j in self.list_jobs():
            if j.run_id == run_id:
                return j
        return None

    def save_job(self, job: SearchJob) -> None:
        ws = self._jobs_ws()
        rows = ws.get_all_values()
        row_data = _job_to_row(job)
        for idx, row in enumerate(rows[1:], start=2):
            if row and row[0] == job.run_id:
                ws.update(f"A{idx}:{_col(len(_JOB_HEADERS))}{idx}", [row_data])
                return
        ws.append_row(row_data, value_input_option="USER_ENTERED")

    def append_result(self, result: SearchResult) -> None:
        ws = self._results_ws()
        ws.append_row(_result_to_row(result), value_input_option="USER_ENTERED")

    def list_results(self, run_id: str) -> list[SearchResult]:
        ws = self._results_ws()
        rows = ws.get_all_values()[1:]
        out: list[SearchResult] = []
        for row in rows:
            if not row or row[0] != run_id:
                continue
            r = _row_to_result(row)
            if r is not None:
                out.append(r)
        return out

    def delete_job(self, run_id: str) -> None:
        ws_jobs = self._jobs_ws()
        rows_j = ws_jobs.get_all_values()
        for idx, row in enumerate(rows_j[1:], start=2):
            if row and row[0] == run_id:
                ws_jobs.delete_rows(idx)
                break

        ws_res = self._results_ws()
        rows_r = ws_res.get_all_values()
        delete_idxs = [
            i for i, row in enumerate(rows_r[1:], start=2)
            if row and row[0] == run_id
        ]
        for idx in reversed(delete_idxs):
            ws_res.delete_rows(idx)


def _col(n: int) -> str:
    """欄號 → A/B/.../Z/AA letter."""
    out = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        out = chr(65 + r) + out
    return out


__all__ = ["GoogleSheetsSearchStore"]
