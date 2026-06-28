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

v19.74 K2：補充 _normalize_moneydj_url_for_cache() 正規化 URL key（防同基金不同 URL 重複抓）。
"""
from __future__ import annotations

import functools as _ft
import time as _time
import re as _re


def _normalize_moneydj_url_for_cache(url: str) -> str:
    """v19.74 K2：Cache key 正規化 — 不論 tcbbankfund 或 www，都變成 (code, page_type) 唯一識別。

    背景：同一基金代碼可能來自多個 URL（tcbbankfund、www、各家銀行冠名頁）。
    此函式將 URL 正規化為 (code, page_type) tuple key，避免「同基金不同 URL」重複 HTTP 抓取。

    範例：
      - https://...?a=ACDD01&yp=010000  → "fetch_fund|ACDD01|010000"
      - https://...?A=ACDD01&yp=010001  → "fetch_fund|ACDD01|010001"
      - 兩個 URL 共用同一 cache entry，第二次呼叫直接命中快取（K2 效能點）。
    """
    try:
        # 取代碼 &a=CODE 或 &A=CODE（MoneyDJ 大小寫混用）
        m = _re.search(r'[?&][aA]=([A-Z0-9\-]{3,30})', url)
        code = (m.group(1).upper() if m else "").strip()

        # 取頁面類型（yp=010000 = 基本資料；yp=010001 = 績效表等）
        m_pt = _re.search(r'[?&][yY][pP]=([0-9]{6})', url)
        page_type = (m_pt.group(1) if m_pt else "default").strip()

        # 最終 key = "fetch_fund|CODE|PAGE_TYPE"
        return f"fetch_fund|{code}|{page_type}"
    except Exception as e:
        # v19.187 F-MED:malformed URL → fallback 原 URL,留 stderr 軌跡
        import sys as _sys
        print(f'[cache] _normalize_moneydj_url_for_cache fail '
              f'(url={url[:80]!r}): {type(e).__name__}: {e}',
              file=_sys.stderr)
        return url


def _ttl_cache(ttl_sec: int, maxsize: int = 128, key_fn=None):
    """TTL + LRU 兩層快取裝飾器。

    cache key 由 (args, sorted kwargs) 組成；無法 hash 的引數（list/dict）跳過快取直走原 fn。
    v19.74 K2：新增 key_fn 參數，可自訂 key 生成邏輯（用於 URL normalize 等特殊場景）。

    Wrapper 暴露：cache_clear() / cache_info() → {size, maxsize, ttl_sec, hits, misses}
    """
    def decorator(fn):
        _cache: dict = {}
        _stats = {"hits": 0, "misses": 0}

        @_ft.wraps(fn)
        def wrapper(*args, **kwargs):
            # v19.74 K2：若有 key_fn，用它生成 cache key（否則用預設 args/kwargs）
            if key_fn is not None and len(args) > 0:
                try:
                    key = key_fn(args[0])  # 通常 args[0] 是 URL 或主要參數
                except Exception as e:
                    # v19.187 F-MED:key_fn 失敗 → 放棄快取(不影響業務),留 stderr
                    import sys as _sys
                    print(f'[cache] key_fn fail in {fn.__name__} '
                          f'(arg0={str(args[0])[:60]!r}): '
                          f'{type(e).__name__}: {e}', file=_sys.stderr)
                    key = None
            else:
                # 防 unhashable args/kwargs（如 list/dict 引數）→ 跳過快取直走原 fn
                try:
                    key = (args, tuple(sorted(kwargs.items())))
                    hash(key)
                except TypeError:
                    return fn(*args, **kwargs)

            if key is None:
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
        except Exception as e:
            # v19.187 F-MED:單一 cache clear 失敗不該中斷其他,留 stderr
            import sys as _sys
            print(f'[cache] clear_all_caches: '
                  f'{getattr(fn, "__name__", "?")} cache_clear fail: '
                  f'{type(e).__name__}: {e}', file=_sys.stderr)
    return len(_CACHE_REGISTRY)


def clear_caches_by_names(names) -> int:
    """v19.57 C1：精準清指定函式名稱的 TTL cache（不影響其他 Tab）。

    參數 names: 可迭代的函式名稱集合 (e.g. {"fetch_fred", "fetch_yf_close"})。
    回傳實際命中並清掉的函式數量。
    """
    _wanted = set(names or [])
    if not _wanted:
        return 0
    _hit = 0
    for fn in _CACHE_REGISTRY:
        try:
            if getattr(fn, "__name__", "") in _wanted:
                fn.cache_clear()
                _hit += 1
        except Exception as e:
            # v19.187 F-MED:單一 cache clear 失敗不影響其他,留 stderr
            import sys as _sys
            print(f'[cache] clear_caches_by_names: '
                  f'{getattr(fn, "__name__", "?")} fail: '
                  f'{type(e).__name__}: {e}', file=_sys.stderr)
    return _hit


def get_all_cache_info() -> list[dict]:
    """回傳所有註冊快取的狀態，給 UI 顯示「cache hit 率」/「entries」用。"""
    out = []
    for fn in _CACHE_REGISTRY:
        try:
            info = fn.cache_info()
            info["name"] = fn.__name__
            out.append(info)
        except Exception as e:
            # v19.187 F-MED:cache info 取不到不該擋整個 UI,留 stderr
            import sys as _sys
            print(f'[cache] get_all_cache_info: '
                  f'{getattr(fn, "__name__", "?")} fail: '
                  f'{type(e).__name__}: {e}', file=_sys.stderr)
    return out


# ════════════════════════════════════════════════════════════
# v19.59 C2：Sidebar 全域刷新總開關 — disk cache + 統一入口
# ════════════════════════════════════════════════════════════

# 跨 Tab session_state 殘留 keys（保留 OAuth/sheet 核心，避免用戶被踢出）
_GLOBAL_REFRESH_SESSION_KEYS = (
    # Tab1 總經
    "_radar_v1921_top", "_tp_v1948_top", "indicators",
    "phase_info", "news_items", "systemic_risk_data",
    "_fred_sources", "macro_done", "macro_last_update",
    # Tab2 / Tab3 基金 / 組合
    "_t3_cur_sheet_title", "_t3_groups_cache",
    # Tab5 健診
    "fund_grp_health_codes",
)

# 永遠保留的 session keys（OAuth/sheet 核心，砍了用戶要重登入）
_GLOBAL_REFRESH_KEEP_KEYS = frozenset({
    "gsheet_tokens", "policy_sheet_id", "active_policy_id",
})


def clear_disk_cache() -> dict:
    """v19.59 C2：清 /tmp/fund_cache 落地檔（NAV/DIV/META CSV+JSON）+ 記憶體 snapshot。

    嚴禁清 data_cache/ — 那是上游 cron 排程的歷史資料倉
    （SPX/TWII/VIX/FRED 8 series parquet），砍了要等下個 cron 才補。

    回傳 dict：files_removed / snapshot_cleared / dir_existed。
    """
    _stat = {"files_removed": 0, "snapshot_cleared": 0, "dir_existed": False}
    if _os.path.isdir(_CACHE_DIR):
        _stat["dir_existed"] = True
        try:
            for _fn in _os.listdir(_CACHE_DIR):
                if not (_fn.endswith(".csv") or _fn.endswith(".json")):
                    continue
                try:
                    _os.remove(_os.path.join(_CACHE_DIR, _fn))
                    _stat["files_removed"] += 1
                except Exception as e:
                    # v19.187 F-MED:單檔刪失敗(權限/併發)不擋全部
                    import sys as _sys
                    print(f'[cache] clear_disk_cache: rm {_fn} fail: '
                          f'{type(e).__name__}: {e}', file=_sys.stderr)
        except Exception as e:
            # v19.187 F-MED:listdir 失敗(權限)
            import sys as _sys
            print(f'[cache] clear_disk_cache: listdir({_CACHE_DIR}) fail: '
                  f'{type(e).__name__}: {e}', file=_sys.stderr)
    if _FUND_SNAPSHOT:
        _stat["snapshot_cleared"] = len(_FUND_SNAPSHOT)
        _FUND_SNAPSHOT.clear()
    return _stat


def global_refresh_all(session_state=None) -> dict:
    """v19.59 C2：Sidebar 全域刷新總開關統一入口。

    4 層清理：
      ① TTL caches（_CACHE_REGISTRY 全部）
      ② hot_money @st.cache_data（fetch_foreign_flow_series / fetch_usdtwd_series）
      ③ Disk cache（/tmp/fund_cache 落地 + _FUND_SNAPSHOT 記憶體最後防線）
      ④ Session state 跨 Tab 殘留（保留 OAuth/sheet 核心 keys）

    嚴禁清 data_cache/ — 上游 cron 歷史資料倉。

    回傳 dict：ttl_cleared / st_cache_cleared / disk_files_removed /
              snapshot_cleared / session_keys_popped。
    """
    _stat = {
        "ttl_cleared": 0, "st_cache_cleared": 0,
        "disk_files_removed": 0, "snapshot_cleared": 0,
        "session_keys_popped": 0,
    }
    import sys as _sys
    try:
        _stat["ttl_cleared"] = clear_all_caches()
    except Exception as e:
        # v19.187 F-MED:layer 1 失敗仍要嘗試 layer 2-4
        print(f'[cache] global_refresh_all L1 ttl fail: '
              f'{type(e).__name__}: {e}', file=_sys.stderr)
    try:
        # v19.196 P0-4-A:fetcher 已下沉 repositories.hot_money_repository
        from repositories.hot_money_repository import (
            fetch_foreign_flow_series, fetch_usdtwd_series,
        )
        for _fn in (fetch_foreign_flow_series, fetch_usdtwd_series):
            try:
                _fn.clear()
                _stat["st_cache_cleared"] += 1
            except Exception as e:
                # v19.187 F-MED:單一 st.cache_data clear fail
                print(f'[cache] global_refresh_all L2 {_fn.__name__} fail: '
                      f'{type(e).__name__}: {e}', file=_sys.stderr)
    except Exception as e:
        # v19.187 F-MED:hot_money_repository import fail(極罕見)
        print(f'[cache] global_refresh_all L2 import fail: '
              f'{type(e).__name__}: {e}', file=_sys.stderr)
    try:
        _disk = clear_disk_cache()
        _stat["disk_files_removed"] = _disk.get("files_removed", 0)
        _stat["snapshot_cleared"] = _disk.get("snapshot_cleared", 0)
    except Exception as e:
        # v19.187 F-MED:disk cache fail
        print(f'[cache] global_refresh_all L3 disk fail: '
              f'{type(e).__name__}: {e}', file=_sys.stderr)
    if session_state is not None:
        for _k in _GLOBAL_REFRESH_SESSION_KEYS:
            if _k in _GLOBAL_REFRESH_KEEP_KEYS:
                continue
            try:
                if _k in session_state:
                    session_state.pop(_k, None)
                    _stat["session_keys_popped"] += 1
            except Exception as e:
                # v19.187 F-MED:單一 session key pop fail
                print(f'[cache] global_refresh_all L4 pop {_k} fail: '
                      f'{type(e).__name__}: {e}', file=_sys.stderr)
    return _stat


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
