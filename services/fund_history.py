"""services/fund_history.py — 唯一基金標的清單 (v18.272)

User 需求：「在說明書上面新增唯一的基金標的清單，地方可以放基金代號跟基金名稱，
只要在單一基金跟組合基金找過的都要被記錄在這」。

設計：
- 純函式 module，session_state 為主 + JSON cache 為備
- Tab2 fetch 成功 → record_fund(code, name, "Tab2")
- Tab3 portfolio fund 載入成功 → record_fund(code, name, "Tab3")
- Tab6 顯示時呼叫 get_history_df() 取最新排序
- 每筆紀錄：{code, name, first_seen, last_seen, count, sources}

注意：JSON 寫在 cache/fund_history.json — Streamlit Cloud 容器重啟會清空，
是「短期累積看過」的工具不是長期備份；UI 提供匯出 CSV 給 user 自己保存。
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd

_CACHE_DIR = Path("cache")
_HIST_FILE = _CACHE_DIR / "fund_history.json"


def _load() -> dict[str, dict]:
    """讀 JSON → {code: entry}；缺檔/壞檔回空 dict。"""
    if not _HIST_FILE.exists():
        return {}
    try:
        data = json.loads(_HIST_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save(data: dict[str, dict]) -> None:
    """寫回 JSON（不存在則建 cache/ 目錄）。"""
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _HIST_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def record_fund(code: str, name: str = "", source: str = "Tab2") -> None:
    """記錄一筆「曾經查過的基金」。

    以 code 為 unique key upsert；已存在則疊代次數 + 來源、更新 last_seen。
    空 code 直接 noop（避免 placeholder 進 cache）。
    """
    code = str(code or "").strip().upper()
    if not code:
        return
    name = str(name or "").strip()
    source = str(source or "").strip() or "unknown"
    now = datetime.now().isoformat(timespec="seconds")
    data = _load()
    if code in data:
        entry = data[code]
        entry["last_seen"] = now
        entry["count"] = int(entry.get("count", 0)) + 1
        srcs = set(entry.get("sources", []) or [])
        srcs.add(source)
        entry["sources"] = sorted(srcs)
        # 名稱有更新才覆蓋（避免後續抓不到時把好名稱蓋掉）
        if name and (not entry.get("name") or entry.get("name") == code):
            entry["name"] = name
    else:
        data[code] = {
            "code": code,
            "name": name,
            "first_seen": now,
            "last_seen": now,
            "count": 1,
            "sources": [source],
        }
    try:
        _save(data)
    except Exception:
        pass  # 寫失敗不該擋住主流程


def get_history_df() -> pd.DataFrame:
    """回傳排序後 DataFrame（最近查詢在最上）。空則回空 DataFrame 含 6 欄。"""
    cols = ["代號", "名稱", "來源", "查詢次數", "首次查詢", "最近查詢"]
    data = _load()
    if not data:
        return pd.DataFrame(columns=cols)
    rows = []
    for code, entry in data.items():
        rows.append({
            "代號": code,
            "名稱": entry.get("name", "") or "",
            "來源": " / ".join(entry.get("sources", []) or []),
            "查詢次數": int(entry.get("count", 0)),
            "首次查詢": entry.get("first_seen", "") or "",
            "最近查詢": entry.get("last_seen", "") or "",
        })
    df = pd.DataFrame(rows, columns=cols)
    return df.sort_values("最近查詢", ascending=False).reset_index(drop=True)


def clear_history() -> None:
    """清空所有查過的紀錄（刪除 JSON 檔）。"""
    if _HIST_FILE.exists():
        try:
            _HIST_FILE.unlink()
        except Exception:
            pass


def history_size() -> int:
    """回傳當前已記錄的唯一基金數。"""
    return len(_load())
