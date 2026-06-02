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


# v18.289：預設常用基金清單改讀 config/preset_funds.json，user 可直接編輯該檔
# Streamlit Cloud reboot 後仍會生效；讀不到 JSON 時 fallback 到最小硬編碼避免壞 app
_PRESET_FUNDS_JSON = Path("config") / "preset_funds.json"
_FALLBACK_DEFAULT_FUNDS: list[dict] = [
    {"code": "ACTI94", "name": "聯博基金（ACTI94）"},
]


def _load_default_funds() -> list[dict]:
    """讀 config/preset_funds.json → list[{code, name}]；壞檔/缺檔回 fallback。"""
    if not _PRESET_FUNDS_JSON.exists():
        return list(_FALLBACK_DEFAULT_FUNDS)
    try:
        data = json.loads(_PRESET_FUNDS_JSON.read_text(encoding="utf-8"))
        funds = data.get("funds", []) if isinstance(data, dict) else []
        out: list[dict] = []
        for d in funds:
            code = str(d.get("code", "") or "").strip().upper()
            if not code:
                continue
            out.append({"code": code, "name": str(d.get("name", "") or "").strip()})
        return out or list(_FALLBACK_DEFAULT_FUNDS)
    except Exception:
        return list(_FALLBACK_DEFAULT_FUNDS)


_DEFAULT_FUNDS: list[dict] = _load_default_funds()


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


def _load_with_defaults() -> dict[str, dict]:
    """v18.282：讀 user JSON + merge 內建預設 = 永遠不會「全空」。

    優先級：user 紀錄 > 預設（同 code 時保留 user count / timestamps，
    但 name 缺漏時用預設補；sources 聯集）。
    """
    user_data = _load()
    out: dict[str, dict] = {}
    # 先塞預設（次數 0 / 時間「—」表示「from preset, 尚未實際查過」）
    for d in _DEFAULT_FUNDS:
        code = str(d.get("code", "") or "").strip().upper()
        if not code:
            continue
        out[code] = {
            "code": code,
            "name": str(d.get("name", "") or ""),
            "first_seen": "—",
            "last_seen": "—",
            "count": 0,
            "sources": ["preset"],
        }
    # user 紀錄覆蓋（merge sources + name 缺漏補預設）
    for code, ent in user_data.items():
        code = str(code or "").strip().upper()
        if not code:
            continue
        if code in out:
            preset_ent = out[code]
            # name：user 有設用 user 的，否則用 preset 的
            if not ent.get("name") or ent.get("name") == code:
                ent["name"] = preset_ent.get("name", "")
            # sources 聯集 preset + user
            srcs = set(ent.get("sources", []) or []) | set(preset_ent.get("sources", []) or [])
            ent["sources"] = sorted(srcs)
        out[code] = ent
    return out


def get_history_df() -> pd.DataFrame:
    """回傳排序後 DataFrame（最近查詢在最上、preset 排最下避免擠掉 user 紀錄）。"""
    cols = ["代號", "名稱", "來源", "查詢次數", "首次查詢", "最近查詢"]
    data = _load_with_defaults()
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
    # 排序：count > 0 的 user 紀錄按最近查詢降序；count = 0 的 preset 排最後
    df["_is_active"] = df["查詢次數"] > 0
    df = df.sort_values(
        ["_is_active", "最近查詢"], ascending=[False, False]
    ).drop(columns=["_is_active"]).reset_index(drop=True)
    return df


def clear_history() -> None:
    """清空所有查過的紀錄（刪除 JSON 檔）。"""
    if _HIST_FILE.exists():
        try:
            _HIST_FILE.unlink()
        except Exception:
            pass


def delete_fund(code: str) -> bool:
    """v18.283：刪除單筆 user 紀錄。

    回傳 True 表示真的刪掉了；如果該 code 只在 _DEFAULT_FUNDS（hardcode）裡，
    delete 後仍會在清單顯示為 preset（這是設計：預設不該被 runtime 刪掉，
    要刪預設請改 services/fund_history.py:_DEFAULT_FUNDS）。
    """
    code = str(code or "").strip().upper()
    if not code:
        return False
    data = _load()
    if code in data:
        del data[code]
        try:
            _save(data)
            return True
        except Exception:
            return False
    return False


def delete_funds_bulk(codes: list[str]) -> dict:
    """批次刪除多檔（給 UI multiselect 用）。

    Returns:
        {deleted: int, not_found: list[str], preset_only: list[str]}
        preset_only: 那些 code 只存在預設清單裡，user 紀錄裡沒有可刪的
    """
    result = {"deleted": 0, "not_found": [], "preset_only": []}
    if not codes:
        return result
    preset_codes = {str(d.get("code", "") or "").strip().upper() for d in _DEFAULT_FUNDS}
    data = _load()
    for raw in codes:
        code = str(raw or "").strip().upper()
        if not code:
            continue
        if code in data:
            del data[code]
            result["deleted"] += 1
        elif code in preset_codes:
            result["preset_only"].append(code)
        else:
            result["not_found"].append(code)
    if result["deleted"] > 0:
        try:
            _save(data)
        except Exception:
            pass
    return result


def history_size() -> int:
    """回傳當前已記錄的唯一基金數。"""
    return len(_load())


def import_from_csv(csv_bytes: bytes) -> dict:
    """v18.280：從 user 之前下載的 CSV 還原紀錄（merge，不覆蓋）。

    Args:
        csv_bytes: 上傳的 CSV 檔內容（utf-8 或 utf-8-sig BOM 都吃）

    Returns:
        dict with: imported (新增筆數) / merged (重複疊代次數) / errors (錯誤訊息 list)
    """
    import io
    result = {"imported": 0, "merged": 0, "errors": []}
    if not csv_bytes:
        result["errors"].append("CSV 內容為空")
        return result
    try:
        # utf-8-sig 處理 Excel 開過的 BOM
        df = pd.read_csv(io.BytesIO(csv_bytes), encoding="utf-8-sig")
    except Exception as e1:
        try:
            df = pd.read_csv(io.BytesIO(csv_bytes), encoding="utf-8")
        except Exception as e2:
            result["errors"].append(f"CSV 解析失敗：{e1} / {e2}")
            return result
    # 容錯：支援既有 download CSV 的欄位名（中文）
    _col_map = {
        "代號": "code", "code": "code",
        "名稱": "name", "name": "name",
        "來源": "sources", "sources": "sources",
        "查詢次數": "count", "count": "count",
        "首次查詢": "first_seen", "first_seen": "first_seen",
        "最近查詢": "last_seen", "last_seen": "last_seen",
    }
    df = df.rename(columns=lambda c: _col_map.get(str(c).strip(), str(c).strip()))
    if "code" not in df.columns:
        result["errors"].append("CSV 缺「代號」欄（或 code）")
        return result
    data = _load()
    for _, row in df.iterrows():
        code = str(row.get("code", "") or "").strip().upper()
        if not code:
            continue
        name = str(row.get("name", "") or "").strip()
        # sources 欄位可能是 "Tab2 / Tab3" 格式，split 成 list
        srcs_raw = str(row.get("sources", "") or "").strip()
        srcs = [s.strip() for s in srcs_raw.replace("／", "/").split("/") if s.strip()] or ["imported"]
        try:
            count = int(row.get("count", 0) or 0)
        except (TypeError, ValueError):
            count = 0
        first_seen = str(row.get("first_seen", "") or "").strip()
        last_seen = str(row.get("last_seen", "") or "").strip()
        if code in data:
            # merge：取較舊 first_seen 與較新 last_seen + 累加 count + 聯集 sources
            ent = data[code]
            ent_first = ent.get("first_seen", "")
            ent_last = ent.get("last_seen", "")
            if first_seen and (not ent_first or first_seen < ent_first):
                ent["first_seen"] = first_seen
            if last_seen and (not ent_last or last_seen > ent_last):
                ent["last_seen"] = last_seen
            ent["count"] = int(ent.get("count", 0) or 0) + max(count, 0)
            srcs_set = set(ent.get("sources", []) or []) | set(srcs)
            ent["sources"] = sorted(srcs_set)
            if name and (not ent.get("name") or ent.get("name") == code):
                ent["name"] = name
            result["merged"] += 1
        else:
            data[code] = {
                "code": code, "name": name,
                "first_seen": first_seen or last_seen or "",
                "last_seen": last_seen or first_seen or "",
                "count": max(count, 1),
                "sources": sorted(set(srcs)) or ["imported"],
            }
            result["imported"] += 1
    try:
        _save(data)
    except Exception as e:
        result["errors"].append(f"寫回失敗：{e}")
    return result
