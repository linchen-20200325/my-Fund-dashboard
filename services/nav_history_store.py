"""services/nav_history_store.py — v18.288 NAV 歷史 CSV 匯入 / 匯出 / 增量更新

User 反饋：「我先找到基金淨值歷史資料，做成 CSV 檔，存回資料庫，
接下來由系統自動更新 這樣可以嗎？」→ 是。架構：

  user 從 CnYES/MoneyDJ 下載 CSV
       ↓
  import_nav_csv(code, csv_bytes)  ← 匯入 + merge cache
       ↓
  cache/nav_history/{code}.json
       ↓
  incremental_update(code)          ← 只抓 cache 最後日期之後的新資料
       ↓
  merge save 回 cache

公開 API：
- import_nav_csv(code, csv_bytes) → 解析 + merge + 寫 cache
- export_nav_csv(code) → bytes (utf-8-sig BOM 給 Excel)
- incremental_update(code) → 從 fetch_nav 抓最新幾天疊代
- get_cache_status(code) → 顯示當前 cache 狀態
"""

from __future__ import annotations

import io
import json
import time
from pathlib import Path

import pandas as pd

_CACHE_DIR = Path("cache") / "nav_history"


def _path(code: str) -> Path:
    """code → cache file path（自動 normalize）。"""
    return _CACHE_DIR / f"{str(code or '').strip().upper()}.json"


def _load_cache_series(code: str) -> pd.Series:
    """讀 cache → pd.Series；空時回空 Series（不靠 v18.283 TTL 過期）。"""
    p = _path(code)
    if not p.exists():
        return pd.Series(dtype=float)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        dates = pd.to_datetime(data.get("dates", []))
        values = data.get("values", [])
        s = pd.Series(values, index=dates, dtype=float)
        return s[~s.index.duplicated(keep="last")].sort_index()
    except Exception as e:
        # F-MED v19.170: silent → stderr log;cache 存在但解析失敗應被記錄
        import sys as _sys
        print(f'[nav_history_store/_load_cache_series] cache parse fail {p}: {type(e).__name__}: {e}', file=_sys.stderr)
        return pd.Series(dtype=float)


def _save_cache_series(code: str, s: pd.Series) -> None:
    """寫回 cache（無 TTL — manual import 視為永久有效直到 user 清除）。"""
    if s is None or s.empty:
        return
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    s = s.dropna().sort_index()
    s = s[~s.index.duplicated(keep="last")]
    _path(code).write_text(json.dumps({
        "timestamp": time.time(),
        "dates": [str(d.date()) for d in s.index],
        "values": [float(v) for v in s.values],
    }, ensure_ascii=False), encoding="utf-8")


def _parse_roc_or_western_date(s: str) -> "pd.Timestamp | None":
    """支援西元 (2024/03/15、2024-03-15) 與民國 (113/03/15、113.03.15) 雙格式。

    必須**先檢測 ROC** — 因為 pd.to_datetime("113/03/15") 會誤判成 0113-03-15
    或 2113-03-15，所以遇到第一段是 3 位數字（民國 50~200）必先當 ROC 處理。
    """
    s = str(s).strip()
    if not s:
        return None
    # 1. ROC 檢測：第一段是 2-3 位數字且範圍合理 → 民國年
    for sep in ("/", "-", "."):
        if sep in s:
            parts = s.split(sep)
            if len(parts) == 3:
                try:
                    yr_raw = int(parts[0])
                    if 50 < yr_raw < 200:  # 民國 50 ~ 200 年
                        return pd.Timestamp(
                            year=yr_raw + 1911,
                            month=int(parts[1]),
                            day=int(parts[2]),
                        )
                except Exception:
                    pass
            break  # 找到第一個 sep 就結束（一個日期應只有一種分隔）
    # 2. 西元 fallback
    try:
        return pd.to_datetime(s)
    except Exception:
        return None


def _detect_columns(df: pd.DataFrame) -> tuple[str | None, str | None]:
    """從 CSV 欄位名自動偵測 date / nav 欄。"""
    if df is None or df.empty:
        return None, None
    _lower_to_orig = {str(c).strip().lower(): c for c in df.columns}
    # date 候選名
    _date_candidates = ["date", "日期", "trade_date", "nav_date", "publish_date",
                        "datetime", "time", "資料日期", "淨值日期"]
    _nav_candidates = ["nav", "淨值", "value", "price", "close", "單位淨值",
                       "netassetvalue", "net_asset_value", "基金淨值"]

    _date_col = None
    for cand in _date_candidates:
        if cand in _lower_to_orig:
            _date_col = _lower_to_orig[cand]
            break
    _nav_col = None
    for cand in _nav_candidates:
        if cand in _lower_to_orig:
            _nav_col = _lower_to_orig[cand]
            break

    # 退路：第一欄當 date、第二欄當 nav
    if _date_col is None and len(df.columns) >= 1:
        _date_col = df.columns[0]
    if _nav_col is None and len(df.columns) >= 2:
        _nav_col = df.columns[1]
    return _date_col, _nav_col


def import_nav_csv(code: str, csv_bytes: bytes) -> dict:
    """從 CSV bytes 匯入 NAV 歷史並 merge 進 cache。

    Args:
        code: 基金代號（cache key）
        csv_bytes: CSV 內容 (utf-8 / utf-8-sig / big5 都吃)

    Returns:
        {imported, merged, total, date_min, date_max, errors}
    """
    result = {
        "imported": 0, "merged": 0, "total": 0,
        "date_min": None, "date_max": None, "errors": [],
    }
    code = str(code or "").strip().upper()
    if not code:
        result["errors"].append("基金代號不可空")
        return result
    if not csv_bytes:
        result["errors"].append("CSV 內容為空")
        return result

    # 多 encoding 嘗試
    df = None
    for enc in ("utf-8-sig", "utf-8", "big5", "cp950"):
        try:
            df = pd.read_csv(io.BytesIO(csv_bytes), encoding=enc)
            if not df.empty:
                break
        except Exception:
            continue
    if df is None or df.empty:
        result["errors"].append("CSV 解析失敗（試了 utf-8 / big5 / cp950）")
        return result

    date_col, nav_col = _detect_columns(df)
    if not date_col or not nav_col:
        result["errors"].append(
            f"無法偵測 date/nav 欄位（找到的欄：{list(df.columns)[:6]}）"
        )
        return result

    new_dates, new_vals = [], []
    for _, row in df.iterrows():
        dt = _parse_roc_or_western_date(row.get(date_col, ""))
        if dt is None:
            continue
        try:
            v = float(str(row.get(nav_col, "")).replace(",", "").strip())
            if v <= 0:
                continue
            new_dates.append(dt)
            new_vals.append(v)
        except (TypeError, ValueError):
            continue

    if not new_dates:
        result["errors"].append(
            f"全部 row 都解析不出有效 NAV（date_col={date_col} nav_col={nav_col}）"
        )
        return result

    new_s = pd.Series(new_vals, index=pd.DatetimeIndex(new_dates), dtype=float)
    new_s = new_s[~new_s.index.duplicated(keep="last")].sort_index()
    n_new_total = len(new_s)

    # Merge 進 cache
    cached = _load_cache_series(code)
    if cached.empty:
        merged = new_s
        result["imported"] = n_new_total
        result["merged"] = 0
    else:
        before_n = len(cached)
        merged = pd.concat([cached, new_s])
        merged = merged[~merged.index.duplicated(keep="last")].sort_index()
        after_n = len(merged)
        # 純新增 = after - before；merged 疊代 = 兩集合 intersection size
        result["imported"] = max(0, after_n - before_n)
        result["merged"] = max(0, n_new_total - result["imported"])

    _save_cache_series(code, merged)
    result["total"] = len(merged)
    result["date_min"] = str(merged.index.min().date())
    result["date_max"] = str(merged.index.max().date())
    return result


def export_nav_csv(code: str) -> bytes:
    """匯出當前 cache 成 CSV bytes（utf-8-sig BOM 給 Excel 正確顯示中文）。"""
    s = _load_cache_series(code)
    if s.empty:
        return b""
    df = pd.DataFrame({
        "date": [str(d.date()) for d in s.index],
        "nav": [float(v) for v in s.values],
    })
    return df.to_csv(index=False).encode("utf-8-sig")


def get_cache_status(code: str) -> dict:
    """回傳 cache 當前狀態（給 UI 顯示）。"""
    s = _load_cache_series(code)
    if s.empty:
        return {"exists": False, "count": 0, "date_min": None,
                "date_max": None, "years_covered": 0.0}
    span_days = (s.index.max() - s.index.min()).days
    return {
        "exists": True,
        "count": len(s),
        "date_min": str(s.index.min().date()),
        "date_max": str(s.index.max().date()),
        "years_covered": round(span_days / 365.25, 2),
    }


def incremental_update(code: str) -> dict:
    """從 fetch_nav 抓最新幾天 → merge 進 cache（不全量重抓）。

    Returns:
        {fetched, new_rows, total, date_max, errors}
    """
    result = {"fetched": 0, "new_rows": 0, "total": 0,
              "date_max": None, "errors": []}
    code = str(code or "").strip().upper()
    if not code:
        result["errors"].append("基金代號不可空")
        return result

    # Lazy import 避免循環
    try:
        from repositories.fund_repository import fetch_nav
    except Exception as e:
        result["errors"].append(f"import 失敗：{e}")
        return result

    new_s = fetch_nav(code)
    if new_s is None or new_s.empty:
        result["errors"].append(
            "fetch_nav 拿不到資料（MoneyDJ 暫時掛 / NAS proxy / 代碼不對）"
        )
        cached = _load_cache_series(code)
        result["total"] = len(cached)
        if not cached.empty:
            result["date_max"] = str(cached.index.max().date())
        return result

    result["fetched"] = len(new_s)
    cached = _load_cache_series(code)
    before_n = len(cached)
    if cached.empty:
        merged = new_s
    else:
        merged = pd.concat([cached, new_s])
        merged = merged[~merged.index.duplicated(keep="last")].sort_index()
    after_n = len(merged)
    result["new_rows"] = max(0, after_n - before_n)
    _save_cache_series(code, merged)
    result["total"] = after_n
    result["date_max"] = str(merged.index.max().date())
    return result


def clear_cache(code: str) -> bool:
    """刪除某 code 的 cache 檔（給「重新匯入」用）。"""
    code = str(code or "").strip().upper()
    if not code:
        return False
    p = _path(code)
    if p.exists():
        try:
            p.unlink()
            return True
        except Exception:
            pass
    return False
