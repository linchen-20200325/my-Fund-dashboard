"""services/auto_search_store_local.py — v19.10 AutoSearch local JSON store

Fallback：當 GS 未設定時，把 jobs + results 寫 `cache/autosearch/<run_id>.json`。

注意：Streamlit Cloud FS ephemeral，reboot 後資料會掉。production 應走 GS。
"""
from __future__ import annotations

import json
from pathlib import Path

from services.auto_search import SearchJob, SearchResult

_CACHE_DIR = Path(__file__).resolve().parent.parent / "cache" / "autosearch"


def _job_path(run_id: str) -> Path:
    return _CACHE_DIR / f"{run_id}.json"


class LocalJsonSearchStore:
    """單檔 = 單 job + 該 job 的所有 results."""

    backend_name = "local-json"

    def __init__(self, base_dir: Path | None = None) -> None:
        self._dir = base_dir or _CACHE_DIR
        self._dir.mkdir(parents=True, exist_ok=True)

    def _read(self, run_id: str) -> dict | None:
        p = self._dir / f"{run_id}.json"
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def _write(self, run_id: str, data: dict) -> None:
        p = self._dir / f"{run_id}.json"
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def list_jobs(self) -> list[SearchJob]:
        out: list[SearchJob] = []
        for p in sorted(self._dir.glob("*.json"), reverse=True):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                job_d = data.get("job")
                if job_d:
                    out.append(SearchJob.from_dict(job_d))
            except (json.JSONDecodeError, OSError, KeyError, TypeError):
                continue
        return out

    def load_job(self, run_id: str) -> SearchJob | None:
        data = self._read(run_id)
        if not data or "job" not in data:
            return None
        try:
            return SearchJob.from_dict(data["job"])
        except (KeyError, TypeError):
            return None

    def save_job(self, job: SearchJob) -> None:
        data = self._read(job.run_id) or {"job": None, "results": []}
        data["job"] = job.to_dict()
        self._write(job.run_id, data)

    def append_result(self, result: SearchResult) -> None:
        data = self._read(result.run_id) or {"job": None, "results": []}
        data.setdefault("results", []).append(result.to_dict())
        self._write(result.run_id, data)

    def list_results(self, run_id: str) -> list[SearchResult]:
        data = self._read(run_id)
        if not data:
            return []
        out: list[SearchResult] = []
        for r in data.get("results", []):
            try:
                out.append(SearchResult.from_dict(r))
            except (KeyError, TypeError):
                continue
        return out

    def delete_job(self, run_id: str) -> None:
        p = self._dir / f"{run_id}.json"
        if p.exists():
            p.unlink()


__all__ = ["LocalJsonSearchStore"]
