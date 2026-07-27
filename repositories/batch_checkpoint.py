"""repositories/batch_checkpoint.py — 批次分析磁碟續存(本地 JSON checkpoint)。

L1 本地持久化(讀+寫同檔),**無外部 HTTP、無 TTL cache** → 適用 §8.2.A **EX-CRUD-1**
(L3 UI 可直呼,加 L2 pass-through 反成 §8.1 step 6 多餘抽象)。

職責:把批次分析「code → row」已完成結果落地成 `data_cache/batch/batch_<run_id>.json`,
讓**關分頁 / 伺服器重啟**後仍能讀回續跑 / 下載。

§1 Fail Loud 分工:
- `save` 寫檔失敗 → **raise**(誠實,不靜默);呼叫端(UI)決定要不要降級成「只記憶體」。
- `load` 壞檔 / 結構不符 → **log + 回 None**(當作無存檔,可重跑;不 crash 分頁、不假裝有資料)。

原子性:temp 檔 + `os.replace` → 崩在寫一半也不會留下壞的正式檔。

⚠️ 持久性依部署:本機 / NAS = 完全持久(關分頁、重啟都在);Streamlit Cloud 檔案系統為
暫時,redeploy / 容器回收會清(仍涵蓋關分頁 / session 逾時的常見情境)。
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import tempfile
from pathlib import Path

# 錨定 repo root(不依賴 cwd;tests 可 monkeypatch 本模組 _DIR 指向 tmp_path)
_REPO_ROOT = Path(__file__).resolve().parent.parent
_DIR = _REPO_ROOT / "data_cache" / "batch"

_TW = _dt.timezone(_dt.timedelta(hours=8))


def _now_iso() -> str:
    return _dt.datetime.now(_TW).strftime("%Y-%m-%d %H:%M")


def _ensure_dir() -> Path:
    _DIR.mkdir(parents=True, exist_ok=True)
    return _DIR


def compute_run_id(codes: list[str]) -> str:
    """同一份清單(不論輸入順序 / 大小寫 / 重複)→ 同一個 run_id(sha1 前 12)。

    這樣「重開分頁上傳同一份清單」就會命中同一個 checkpoint 自動續跑。
    """
    norm = sorted({(c or "").strip().upper() for c in (codes or []) if (c or "").strip()})
    digest = hashlib.sha1("\n".join(norm).encode("utf-8")).hexdigest()
    return digest[:12]


def _path(run_id: str) -> Path:
    return _DIR / f"batch_{run_id}.json"


def save(run_id: str, codes: list, rows: dict) -> None:
    """原子寫入 checkpoint。寫失敗 raise(§1),呼叫端負責降級。"""
    _ensure_dir()
    payload = {
        "run_id": run_id,
        "codes": list(codes),
        "rows": rows,
        "updated_at": _now_iso(),
        "n_done": len(rows),
    }
    target = _path(run_id)
    fd, tmp = tempfile.mkstemp(dir=str(_DIR), prefix=".tmp_batch_", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
        os.replace(tmp, target)   # 原子:同目錄 rename
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def load(run_id: str) -> "dict | None":
    """讀回 checkpoint。不存在 → None;壞檔 / 結構不符 → log + None(可重跑,不炸)。"""
    p = _path(run_id)
    if not p.exists():
        return None
    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or not isinstance(data.get("rows"), dict):
            raise ValueError("checkpoint 結構不符(缺 rows dict)")
        return data
    except Exception as e:  # noqa: BLE001 — 壞 cache 可重跑,不 crash 分頁
        print(f"[batch_checkpoint] ⚠️ 讀 {p.name} 失敗,當作無存檔:{type(e).__name__}: {e}")
        return None


def delete(run_id: str) -> None:
    """刪 checkpoint(不存在 → 靜默,已達目標狀態)。"""
    try:
        _path(run_id).unlink()
    except FileNotFoundError:
        pass


def list_recent(limit: int = 10) -> list:
    """列現有 checkpoint meta(run_id / n_done / n_codes / updated_at),新→舊。壞檔跳過。"""
    if not _DIR.exists():
        return []
    out = []
    for p in _DIR.glob("batch_*.json"):
        try:
            with open(p, encoding="utf-8") as f:
                d = json.load(f)
            out.append({
                "run_id": d.get("run_id") or p.stem.replace("batch_", ""),
                "n_done": int(d.get("n_done", len(d.get("rows", {}) or {}))),
                "n_codes": len(d.get("codes", []) or []),
                "updated_at": d.get("updated_at", ""),
                "mtime": p.stat().st_mtime,
            })
        except Exception:  # noqa: BLE001 — 壞檔不列
            continue
    out.sort(key=lambda x: x["mtime"], reverse=True)
    return out[:limit]
