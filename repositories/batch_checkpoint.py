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


# ── 讀回時中和「名稱推定時代」存下的買賣句(客戶 2026-10-11 裁示)────────────────
# 舊版 `mk_fund_signal` 依基金名稱關鍵字猜核心／衛星，再輸出下列 8 句買賣操作句；
# 批次大表把它存進 checkpoint 的「操作訊號」格。名稱推定已停用，但舊存檔讀回後欄名沒變，
# 這些句子會原樣顯示、還和重跑的新列(「—」)並排 ⇒ 名稱推定結果從磁碟復活。
# 做法:讀回(`load`)時就地把這 8 句改成「—」，**不改寫磁碟檔**;「⚠️ …計算失敗／載入失敗」之類
# 的錯誤標記不是買賣句，原樣保留。
# 為何用白名單而非「非『—』且非『⚠️』一律覆寫」:這 8 句的值域已逐一核對 git 歷史
# (9dcab88f 初版 → 52c5243c 批次存檔上線 → 852cfb1e → 停用前)，全程不變;白名單只動
# 已知由名稱推定產生的值，不會把日後任何合法的新「操作訊號」值無聲抹掉。
# 舊欄「資產屬性」(名稱推定的核心資產／衛星資產／混合型)直接移除;新欄「基金屬性」
# 不替舊列補值(缺值不補，§1)。
_NAME_INFERRED_SIGNAL_LABELS = frozenset({
    "🟢 買進加碼", "🟢 積極買進", "⚪ 持有核心", "🟡 持有設停利",
    "🟡 持有減碼", "🔴 賣出獲利", "🟢 逢低買進", "⏸ 觀望等待",
})
_NEUTRALIZED_SIGNAL = "—"
_RETIRED_ATTR_KEY = "資產屬性"
_SIGNAL_KEY = "操作訊號"


def _norm_label(s: str) -> str:
    """去掉 emoji 變體選擇符 U+FE0F 與前後空白，避免「⏸️」與「⏸」字元差異漏網。"""
    return str(s).replace("\ufe0f", "").strip()


_NAME_INFERRED_NORM = frozenset(_norm_label(x) for x in _NAME_INFERRED_SIGNAL_LABELS)


def _neutralize_name_inferred_signals(rows: dict) -> None:
    """就地中和 rows(code -> row dict)裡名稱推定時代的「操作訊號」買賣句，並移除舊「資產屬性」鍵。"""
    for _row in rows.values():
        if not isinstance(_row, dict):
            continue
        _row.pop(_RETIRED_ATTR_KEY, None)
        _sig = _row.get(_SIGNAL_KEY)
        if isinstance(_sig, str) and _norm_label(_sig) in _NAME_INFERRED_NORM:
            _row[_SIGNAL_KEY] = _NEUTRALIZED_SIGNAL


def load(run_id: str) -> "dict | None":
    """讀回 checkpoint。不存在 → None;壞檔 / 結構不符 → log + None(可重跑,不炸)。

    讀回時中和名稱推定時代的買賣句(見 `_NAME_INFERRED_SIGNAL_LABELS`);磁碟檔內容不改。
    本模組所有回傳 rows 的讀回路徑只有本函式(`list_recent` 只回 meta，不含列內容)。
    """
    p = _path(run_id)
    if not p.exists():
        return None
    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or not isinstance(data.get("rows"), dict):
            raise ValueError("checkpoint 結構不符(缺 rows dict)")
        _neutralize_name_inferred_signals(data["rows"])
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
