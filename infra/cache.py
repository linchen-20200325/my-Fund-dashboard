"""infra/cache.py — TTL 快取裝飾器 + 集中註冊機制（v11.0 B-9a 從 fund_fetcher.py 抽出）

為什麼自己造輪子不用 @st.cache_data：
  (1) CLAUDE.md §4 全域禁用 st.cache_data（殘留 stale data 隱憂）
  (2) functools.lru_cache 沒有 TTL，會永久存活 → 盤中 NAV 變動讀不到新值
  (3) 此實作跨 Streamlit rerun 共享（module 不重 import），
      同一 session 多次 rerun 重複呼叫即時 dedupe。

使用：
    from infra.cache import _ttl_cache, register_cache

    @register_cache
    @_ttl_cache(ttl_sec=300, maxsize=32)
    def fetch_something(...): ...

    # UI「🔄 清空快取」按鈕
    from infra.cache import clear_all_caches
    n = clear_all_caches()    # 一鍵清所有註冊的快取

v11.0 分層歸位：本檔屬於 Infrastructure Layer，跨切的快取機制。
向後相容：fund_fetcher.py 仍 re-export _ttl_cache / register_cache / clear_all_caches /
        get_all_cache_info / _CACHE_REGISTRY，既有 caller 零修改。
"""
from __future__ import annotations

import functools as _ft
import time as _time


def _ttl_cache(ttl_sec: int, maxsize: int = 128):
    """TTL + LRU 兩層快取裝飾器。

    cache key 由 (args, sorted kwargs) 組成；無法 hash 的引數（list/dict）跳過快取直走原 fn。
    Wrapper 暴露：cache_clear() / cache_info() → {size, maxsize, ttl_sec, hits, misses}
    """
    def decorator(fn):
        _cache: dict = {}
        _stats = {"hits": 0, "misses": 0}

        @_ft.wraps(fn)
        def wrapper(*args, **kwargs):
            # 防 unhashable args/kwargs（如 list/dict 引數）→ 跳過快取直走原 fn
            try:
                key = (args, tuple(sorted(kwargs.items())))
                hash(key)
            except TypeError:
                return fn(*args, **kwargs)
            now = _time.time()
            hit = _cache.get(key)
            if hit and (now - hit[0]) < ttl_sec:
                _stats["hits"] += 1
                return hit[1]
            _stats["misses"] += 1
            result = fn(*args, **kwargs)
            _cache[key] = (now, result)
            # LRU 防呆：超過 maxsize 砍最舊
            if len(_cache) > maxsize:
                oldest_key = min(_cache.items(), key=lambda kv: kv[1][0])[0]
                _cache.pop(oldest_key, None)
            return result

        def _clear():
            _cache.clear()
            _stats["hits"] = 0
            _stats["misses"] = 0

        wrapper.cache_clear = _clear   # type: ignore[attr-defined]
        wrapper.cache_info = lambda: {   # type: ignore[attr-defined]
            "size": len(_cache), "maxsize": maxsize, "ttl_sec": ttl_sec,
            "hits": _stats["hits"], "misses": _stats["misses"],
        }
        wrapper._cache_dict = _cache   # type: ignore[attr-defined]   # for tests
        return wrapper

    return decorator


# 集中註冊：UI「🔄 清空快取」按鈕一鍵清所有快取
_CACHE_REGISTRY: list = []   # list of cached function wrappers


def register_cache(fn):
    """把 _ttl_cache 包過的函式註冊進去，clear_all_caches() 一次清。"""
    _CACHE_REGISTRY.append(fn)
    return fn


def clear_all_caches() -> int:
    """清空所有註冊的 TTL cache。回傳清空的函式數量。"""
    for fn in _CACHE_REGISTRY:
        try:
            fn.cache_clear()
        except Exception:
            pass
    return len(_CACHE_REGISTRY)


def get_all_cache_info() -> list[dict]:
    """回傳所有註冊快取的狀態，給 UI 顯示「cache hit 率」/「entries」用。"""
    out = []
    for fn in _CACHE_REGISTRY:
        try:
            info = fn.cache_info()
            info["name"] = fn.__name__
            out.append(info)
        except Exception:
            pass
    return out


# ════════════════════════════════════════════════════════════
# v11.0 B-9b-1：Disk cache helpers（從 fund_fetcher.py 抽出）
# 基金 NAV / 配息 / metadata 的本地 CSV+JSON 快取
# 環境自適應路徑（Colab → /content/fund_cache; 其他 → /tmp/fund_cache）
# pandas 採 lazy import（infra 層避免硬依賴 pandas）
# ════════════════════════════════════════════════════════════
import os as _os
import datetime as _datetime
import json as _json_mod

# ── 本地快取路徑（環境自適應：Colab → /content, Streamlit Cloud → /tmp）──
_CACHE_DIR = "/content/fund_cache" if _os.path.isdir("/content") else "/tmp/fund_cache"

# ── 記憶體快照：網路與檔案快取均失效時的最後一道防線（同 macro_engine._INDICATOR_SNAPSHOT）
_FUND_SNAPSHOT: dict = {}  # key=code.upper(), value=完整 result dict（不含 series）


def _cache_path(code: str, dtype: str) -> str:
    _os.makedirs(_CACHE_DIR, exist_ok=True)
    return f"{_CACHE_DIR}/{code.upper()}_{dtype}.csv"


def _cache_load_nav(code: str, max_age_hours: int = 20):
    """
    讀取本地 NAV 快取。
    若快取不存在或超過 max_age_hours，回傳 None（需重新抓取）。
    """
    fp = _cache_path(code, "nav")
    if not _os.path.exists(fp):
        return None
    try:
        import pandas as _pd  # lazy import: infra/ 避免硬依賴 pandas
        mtime = _os.path.getmtime(fp)
        age_h = (_datetime.datetime.now().timestamp() - mtime) / 3600
        if age_h > max_age_hours:
            return None
        df = _pd.read_csv(fp, index_col=0, parse_dates=True)
        if df.empty or len(df) < 5:
            return None
        s = df.iloc[:, 0].dropna()
        s.index = _pd.to_datetime(s.index)
        print(f"[cache] ✅ {code} NAV 快取命中 {len(s)} 筆（{age_h:.1f}小時前）")
        return s.sort_index()
    except Exception as e:
        print(f"[cache] load_nav 失敗: {e}")
        return None


def _cache_save_nav(code: str, s):
    """儲存 NAV 序列到本地快取（pandas.Series）"""
    if s is None or len(s) < 5:
        return
    try:
        fp = _cache_path(code, "nav")
        s.to_csv(fp, header=["nav"])
        print(f"[cache] 💾 {code} NAV {len(s)} 筆已快取")
    except Exception as e:
        print(f"[cache] save_nav 失敗: {e}")


def _cache_load_div(code: str, max_age_hours: int = 48):
    """讀取配息快取"""
    fp = _cache_path(code, "div")
    if not _os.path.exists(fp):
        return None
    try:
        age_h = (_datetime.datetime.now().timestamp() - _os.path.getmtime(fp)) / 3600
        if age_h > max_age_hours:
            return None
        with open(fp, "r", encoding="utf-8") as fh:
            data = _json_mod.load(fh)
        if data:
            print(f"[cache] ✅ {code} 配息快取命中 {len(data)} 筆")
            return data
    except Exception as e:
        print(f"[cache] load_div 失敗: {e}")
    return None


def _cache_save_div(code: str, divs: list):
    """儲存配息資料到本地快取"""
    if not divs:
        return
    try:
        fp = _cache_path(code, "div")
        with open(fp, "w", encoding="utf-8") as fh:
            _json_mod.dump(divs, fh, ensure_ascii=False, default=str)
        print(f"[cache] 💾 {code} 配息 {len(divs)} 筆已快取")
    except Exception as e:
        print(f"[cache] save_div 失敗: {e}")


def _cache_load_meta(code: str, max_age_hours: int = 48):
    """讀取基金基本資料快取"""
    fp = _cache_path(code, "meta")
    if not _os.path.exists(fp):
        return None
    try:
        age_h = (_datetime.datetime.now().timestamp() - _os.path.getmtime(fp)) / 3600
        if age_h > max_age_hours:
            return None
        with open(fp, "r", encoding="utf-8") as fh:
            data = _json_mod.load(fh)
        if data.get("fund_name"):
            print(f"[cache] ✅ {code} 基本資料快取命中: {data['fund_name'][:20]}")
            return data
    except Exception as e:
        print(f"[cache] load_meta 失敗: {e}")
    return None


def _cache_save_meta(code: str, meta: dict):
    """儲存基金基本資料到快取"""
    save_keys = ["fund_name", "currency", "risk_level", "dividend_freq",
                 "fund_scale", "category", "fund_region", "nav_latest",
                 "nav_date", "year_high_nav", "year_low_nav",
                 "moneydj_div_yield", "mgmt_fee"]
    try:
        fp = _cache_path(code, "meta")
        slim = {k: meta.get(k) for k in save_keys if meta.get(k) is not None}
        with open(fp, "w", encoding="utf-8") as fh:
            _json_mod.dump(slim, fh, ensure_ascii=False, default=str)
    except Exception as e:
        print(f"[cache] save_meta 失敗: {e}")
