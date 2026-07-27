"""repositories/ai_cache.py — AI 白話總體檢結果磁碟續存(reboot 不消失)。v19.410。

問題:各 Tab 的 AI 總結原本只存 `st.session_state`,app 一 reboot 就全清空,使用者以為
「AI 不見了」。本模組把 AI 結果落地 `data_cache/ai_cache.json`,keyed by (tab + snapshot
內容 hash),讓**重啟後同一份資料的 AI 立刻讀回**;資料變了(hash 變)自然 miss → 提示
重生成,**不顯示過期 AI**(避免拿舊資料的結論誤導)。

架構(§8.2.A EX-CRUD-1):L1 本地 JSON CRUD —— 無外部 HTTP、無 TTL cache,UI 可直呼。
§EX-AI-1:只存 / 回顯 AI 自己的 markdown 字串,**不從中萃取數字當 data input**。

§1:寫失敗 raise(呼叫端可降級成只記憶體);讀壞檔 → log + 當無 cache(可重生成)。
原子寫(temp + os.replace)。上限 _MAX_ENTRIES 條,滿了汰最舊(updated_at)。
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import tempfile
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_PATH = _REPO_ROOT / "data_cache" / "ai_cache.json"
_MAX_ENTRIES = 50
_TW = _dt.timezone(_dt.timedelta(hours=8))


def make_key(tab_key: str, snapshot: str) -> str:
    """(tab + snapshot 內容)→ 穩定 key。snapshot 變 → key 變 → 不回顯過期 AI。"""
    h = hashlib.sha1((snapshot or "").encode("utf-8")).hexdigest()[:16]
    return f"{tab_key}:{h}"


def _read_all() -> dict:
    if not _PATH.exists():
        return {}
    try:
        with open(_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception as e:  # noqa: BLE001 — 壞檔可重生成,不 crash
        print(f"[ai_cache] ⚠️ 讀 {_PATH.name} 失敗,當無 cache:{type(e).__name__}: {e}")
        return {}


def load(key: str) -> "str | None":
    """讀回該 key 的 AI markdown;無 → None。"""
    rec = _read_all().get(key)
    if isinstance(rec, dict):
        t = rec.get("text")
        return t if isinstance(t, str) and t.strip() else None
    return None


def save(key: str, text: str) -> None:
    """落地 AI 結果(原子寫)。滿 _MAX_ENTRIES 汰最舊。寫失敗 raise(§1)。"""
    data = _read_all()
    data[key] = {"text": text, "updated_at": _dt.datetime.now(_TW).strftime("%Y-%m-%d %H:%M")}
    if len(data) > _MAX_ENTRIES:
        # 依 updated_at 汰最舊(字串 YYYY-MM-DD HH:MM 可字典序比較)。
        # 非 dict 值(外部污染 valid-JSON)排最前先汰,避免 .get 對非 dict 拋 AttributeError。
        def _stamp(k):
            return data[k].get("updated_at", "") if isinstance(data[k], dict) else ""
        for _k in sorted(data, key=_stamp)[:len(data) - _MAX_ENTRIES]:
            data.pop(_k, None)
    _PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(_PATH.parent), prefix=".tmp_ai_", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, _PATH)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
