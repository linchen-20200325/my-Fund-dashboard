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
- backfill_to_gs(codes) → 一鍵補全部缺淨值:多檔抓完整歷史(含選股池 ISIN→晨星 ~5.5 年)
                          → 本地 cache + 雲端 nav_history(永久),逐檔誠實回報(§1)
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


def _detect_columns(df: "pd.DataFrame") -> tuple:
    """依**內容**偵測 date / nav 欄(不靠 header 名)。df 須以 `header=None, dtype=str` 讀入。

    v19.488:改內容偵測,修「無表頭 cache-export CSV 上傳解析失敗」——
    原本靠欄名 + 位置退路(第一欄 date、第二欄 nav)。app 自己「下載當前 cache 為 CSV」
    產出的是**無表頭、code 開頭**的 6-7 欄格式(code,date,nav,name,source,fetched_at),
    pandas 預設把第一列資料當表頭 → 退路挑到 code 欄當 date、date 值當 nav → 全 row 失敗。
    改為掃每欄實際值:
      - date 欄 = 值多數可解析為(西元/民國)日期、且非數字;多個日期欄(如 fetched_at
        時間戳也解析成日期)取**相異值最多**者(真淨值日序列 vs 常數時間戳),平手取最左。
      - nav 欄 = 值多數為正浮點、且非日期;排除 date 欄,取占比最高、最左。
    有表頭的舊格式(date,nav / 日期,淨值 / 民國)仍正確:表頭字串那一列解析不出日期,
    僅稀釋比例(門檻 0.7 容忍),且在匯入迴圈自然被 skip(§round-trip 相容)。
    """
    if df is None or df.empty:
        return None, None
    _cols = list(df.columns)

    # 若第 0 列是**表頭**(含已知 date/nav 欄名 token,中英文)→ 從內容取樣排除,
    # 避免少數列時表頭字串稀釋日期/數值占比(§header-dilution;無表頭 code-first 不受影響)。
    _header_tokens = {
        "date", "日期", "trade_date", "nav_date", "publish_date", "datetime",
        "time", "資料日期", "淨值日期", "nav", "淨值", "value", "price", "close",
        "單位淨值", "netassetvalue", "net_asset_value", "基金淨值", "code", "source",
        "fetched_at",
    }
    _row0 = [str(v).strip().lower() for v in df.iloc[0].tolist()]
    _has_header = any(tok in _header_tokens for tok in _row0)
    _body = df.iloc[1:] if (_has_header and len(df) > 1) else df
    _sample = _body.head(200)

    def _clean(v) -> str:
        v = str(v).strip()
        return "" if (not v or v.lower() == "nan") else v

    def _is_float(v: str) -> bool:
        # 偵測「是否數值欄」用**任意正負浮點**——正負篩選留給匯入迴圈(v<=0 skip),
        # 否則含少數負值/異常的 nav 欄會被誤判非數值欄(§edge:負 NAV 混入)。
        try:
            float(v.replace(",", ""))
            return True
        except (TypeError, ValueError):
            return False

    _date_frac, _date_uniq, _num_frac = {}, {}, {}
    for c in _cols:
        _vals = [x for x in (_clean(v) for v in _sample[c].tolist()) if x]
        if not _vals:
            continue
        _dts = [_parse_roc_or_western_date(v) for v in _vals]
        _date_frac[c] = sum(d is not None for d in _dts) / len(_vals)
        _date_uniq[c] = len({d for d in _dts if d is not None})
        _num_frac[c] = sum(_is_float(v) for v in _vals) / len(_vals)

    # date 欄:多數為日期且非數字;平手(fetched_at 也是日期)取相異值最多、最左
    _date_cands = [c for c in _date_frac
                   if _date_frac[c] >= 0.7 and _num_frac.get(c, 0.0) < 0.5]
    date_col = (max(_date_cands, key=lambda c: (_date_uniq[c], -_cols.index(c)))
                if _date_cands else None)
    # nav 欄:多數為正浮點且非日期;排除 date 欄,取占比最高、最左
    _nav_cands = [c for c in _num_frac
                  if c != date_col and _num_frac[c] >= 0.7 and _date_frac.get(c, 0.0) < 0.5]
    nav_col = (max(_nav_cands, key=lambda c: (_num_frac[c], -_cols.index(c)))
               if _nav_cands else None)
    return date_col, nav_col


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

    # 多 encoding 嘗試。v19.488:header=None + dtype=str —— 無表頭 cache-export CSV
    # 不可被 pandas 當第一列是表頭而吃掉一整列資料;欄位改由 _detect_columns 依內容判。
    df = None
    for enc in ("utf-8-sig", "utf-8", "big5", "cp950"):
        try:
            df = pd.read_csv(io.BytesIO(csv_bytes), encoding=enc,
                             header=None, dtype=str)
            if not df.empty:
                break
        except Exception:
            continue
    if df is None or df.empty:
        result["errors"].append("CSV 解析失敗（試了 utf-8 / big5 / cp950）")
        return result

    date_col, nav_col = _detect_columns(df)
    # v19.488:須用 `is None` —— 欄索引為整數,第 0 欄的 `not 0` 為 True 會誤判偵測失敗。
    if date_col is None or nav_col is None:
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

    _res = _merge_pairs_into_cache(code, new_dates, new_vals)
    for _k in ("imported", "merged", "total", "date_min", "date_max"):
        result[_k] = _res[_k]
    return result


def _merge_pairs_into_cache(code: str, new_dates: list, new_vals: list) -> dict:
    """把 (dates, vals) 併進 `code` 的本地 cache(同日 keep-last、昇冪),回統計 dict。

    v19.490:自 import_nav_csv 抽出,供單檔 / 多檔(import_nav_csv_multi)共用同一套併入邏輯。
    """
    res = {"imported": 0, "merged": 0, "total": 0, "date_min": None, "date_max": None}
    if not new_dates:
        return res
    new_s = pd.Series(new_vals, index=pd.DatetimeIndex(new_dates), dtype=float)
    new_s = new_s[~new_s.index.duplicated(keep="last")].sort_index()
    n_new_total = len(new_s)
    cached = _load_cache_series(code)
    if cached.empty:
        merged = new_s
        res["imported"] = n_new_total
    else:
        before_n = len(cached)
        merged = pd.concat([cached, new_s])
        merged = merged[~merged.index.duplicated(keep="last")].sort_index()
        res["imported"] = max(0, len(merged) - before_n)
        res["merged"] = max(0, n_new_total - res["imported"])
    _save_cache_series(code, merged)
    res["total"] = len(merged)
    res["date_min"] = str(merged.index.min().date())
    res["date_max"] = str(merged.index.max().date())
    return res


def _read_csv_bytes(csv_bytes: bytes):
    """多 encoding 讀 CSV → DataFrame(header=None, dtype=str);全失敗回 None。"""
    import io as _io
    for enc in ("utf-8-sig", "utf-8", "big5", "cp950"):
        try:
            df = pd.read_csv(_io.BytesIO(csv_bytes), encoding=enc, header=None, dtype=str)
            if not df.empty:
                return df
        except Exception:
            continue
    return None


def _detect_code_column(df, date_col, nav_col):
    """偵測**代號欄**(非 date/nav):值為短識別碼(≤15 字、含英數,排除長中文名 / 時間戳),
    取最左符合者。找不到回 None(呼叫端據此要求「代號|日期|淨值」格式或退單檔上傳)。"""
    _sample = df.head(200)

    def _clean(v):
        v = str(v).strip()
        return "" if (not v or v.lower() == "nan") else v

    for c in df.columns:
        if c == date_col or c == nav_col:
            continue
        _vals = [x for x in (_clean(v) for v in _sample[c].tolist()) if x]
        if not _vals:
            continue
        _short = sum(1 for v in _vals if len(v) <= 15 and any(ch.isalnum() for ch in v)) / len(_vals)
        if _short >= 0.7:
            return c
    return None


def import_nav_csv_multi(csv_bytes: bytes) -> dict:
    """**免指定代號**:從 CSV 的代號欄自動分組,逐檔併進各自 cache(代號|日期|淨值 格式)。

    回 {codes:[...], results:{code:{imported,merged,total,date_min,date_max}}, points:[...], errors:[...]}。
    points = [{code, nav, nav_date}]:供呼叫端一次同步進雲端 nav_history(append_points)。
    §1:代號空 / 日期壞 / nav<=0 的 row 全丟;無代號欄或無有效 row → errors。
    """
    out: dict = {"codes": [], "results": {}, "points": [], "errors": []}
    if not csv_bytes:
        out["errors"].append("CSV 內容為空")
        return out
    df = _read_csv_bytes(csv_bytes)
    if df is None or df.empty:
        out["errors"].append("CSV 解析失敗（試了 utf-8 / big5 / cp950）")
        return out
    date_col, nav_col = _detect_columns(df)
    if date_col is None or nav_col is None:
        out["errors"].append(f"無法偵測 date/nav 欄位（找到的欄:{list(df.columns)[:6]}）")
        return out
    code_col = _detect_code_column(df, date_col, nav_col)
    if code_col is None:
        out["errors"].append("找不到代號欄 —— 需 `代號|日期|淨值` 格式（每列第一欄是基金代號）")
        return out

    groups: dict = {}   # code -> ([dates], [vals])
    for _, row in df.iterrows():
        code = str(row.get(code_col, "")).strip().upper()
        if not code:
            continue
        dt = _parse_roc_or_western_date(row.get(date_col, ""))
        if dt is None:
            continue
        try:
            v = float(str(row.get(nav_col, "")).replace(",", "").strip())
        except (TypeError, ValueError):
            continue
        if v <= 0:
            continue
        g = groups.setdefault(code, ([], []))
        g[0].append(dt)
        g[1].append(v)
        out["points"].append({"code": code, "nav": v, "nav_date": dt.strftime("%Y-%m-%d")})

    if not groups:
        out["errors"].append(
            f"全部 row 都解析不出有效 (代號,日期,NAV)（code_col={code_col} "
            f"date_col={date_col} nav_col={nav_col}）")
        return out

    for code, (dates, vals) in groups.items():
        out["results"][code] = _merge_pairs_into_cache(code, dates, vals)
        out["codes"].append(code)
    out["codes"].sort()
    return out


def list_cache_codes() -> list:
    """列出本地 cache 已有的代號(供 UI 選單:增量更新 / 下載 / 清除 目標)。"""
    try:
        return sorted(p.stem for p in _CACHE_DIR.glob("*.json"))
    except Exception:  # noqa: BLE001
        return []


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
        from repositories.fund import fetch_nav
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


# ── Gate 0 共用常數 / helper（2026-08-28 稽核修正）────────────────────────────
# **白名單**，不是黑名單:只有這兩個 verdict 是「確定安全」。舊版寫 `== "conflict"` 才擋
# → `"unknown"`（讀不到既有資料 / 既有列全不可解析）與**任何日後新增的 verdict**
# 都會靜默放行,fail-open。§1:不知道 ≠ 安全。
_GATE0_SAFE_VERDICTS = ("clean", "duplicate")
_GATE0_MODES = ("enforce", "observe", "off")


def _gate0_mode() -> str:
    """Gate 0 運行模式（`NAV_GATE0_MODE` secret / env）—— **關掉不必改 code**。

    為什麼要有這個開關（2026-08-28 稽核）:這道閘門長在**每天 20:00 都在跑**的排程上,
    而在此之前**沒有任何旗標** —— 要關掉只能改 code → 開 PR → 等 CI → 合併,
    那是數小時的 MTTR,期間每天都在丟當日淨值。

    - `enforce`（**預設**）:不安全的 verdict → 該檔擋下不寫（雲端與本地 cache 皆不寫）。
    - `observe`:**照常判定、照常回報、但不擋**。兩個用途 ——
      (a) 誤擋時的止血（改一個 env 就好）;(b) 讓「先量真實觸發頻率再調門檻」變得可能
      （C1 的比例門檻沒有真實資料可校準,盲調風險更大）。
    - `off`:完全不判定（連讀既有歷史都省下）。⚠️ 等於沒有護欄,只該用於確認閘門本身
      是不是故障來源。
    不認得的值 → **退回 `enforce` 並印一行**（§1:打錯字不該靜默變成沒有護欄）。
    """
    import sys as _sys
    try:
        from infra.config import get_secret
        _raw = str(get_secret("NAV_GATE0_MODE") or "").strip().lower()
    except Exception as _e:  # noqa: BLE001 — 讀不到設定 → 走預設（最安全那邊）
        print(f"[backfill_to_gs] 讀 NAV_GATE0_MODE 失敗,退回 enforce:"
              f"{type(_e).__name__}: {_e}", file=_sys.stderr)
        return "enforce"
    if not _raw:
        return "enforce"
    if _raw not in _GATE0_MODES:
        print(f"[backfill_to_gs] NAV_GATE0_MODE={_raw!r} 不認得（可用:"
              f"{'/'.join(_GATE0_MODES)}）→ 退回 enforce", file=_sys.stderr)
        return "enforce"
    return _raw


def _gate0_reason(cf: dict, *, blocked: bool) -> str:
    """把 verdict 轉成給人看的一句話。`blocked=False`（observe 模式）不得寫「已擋下」。"""
    _tail = "已擋下未寫入" if blocked else "⚠️ observe 模式:**沒有擋**,已照常寫入"
    if cf.get("verdict") == "conflict":
        _s0 = (cf.get("samples") or [{}])[0]
        return (f"與既有 nav_history 衝突:重疊 {cf.get('n_overlap')} 日、"
                f"{cf.get('n_conflict')} 日對不上"
                f"(如 {_s0.get('date', '?')} 既有 {_s0.get('existing', '?')}"
                f" vs 這次 {_s0.get('incoming', '?')})"
                f" —— 極可能抓到別的級別/幣別,{_tail}")
    _why = str(cf.get("reason") or "")[:80]
    return (f"無法與既有 nav_history 對帳(verdict={cf.get('verdict')!r}"
            f"{'：' + _why if _why else ''}) —— 不知道 ≠ 安全（§1）,{_tail}")


def _expected_currency(code: str, fd) -> str:
    """這檔基金**應該**是哪一種計價幣別 → ISO 三碼;判不出來回 `""`(未知,§1 不猜)。

    順序:抓取結果自帶的 `currency`(已經過 `fund_orchestration._ensure_currency` 修過
    死預設 USD 的那一層)→ 選股池使用者填的 `currency`。中文別名先過 L2
    `services.currency.normalize_ccy`(本層是 L2,可以用),再由 L0 收成 ISO 三碼。

    ⚠️ 這個值證明的是「上游**宣告**的幣別」,不是「宣告正確」——
    見 `shared/data_quality.py` 該節「保護不到什麼」b 項。
    """
    import sys as _sys

    from shared.data_quality import normalize_iso_ccy

    def _norm(_raw) -> str:
        try:
            from services.currency import normalize_ccy
            return normalize_iso_ccy(normalize_ccy(_raw, default=""))
        except Exception as _e:  # noqa: BLE001 — 正規化失敗不得擋抓取,退「未知」
            print(f"[backfill_to_gs] {code} 幣別正規化失敗:{type(_e).__name__}: {_e}",
                  file=_sys.stderr)
            return ""

    _c = _norm((fd or {}).get("currency") if isinstance(fd, dict) else "")
    if _c:
        return _c
    try:
        from repositories.pool_repository import resolve_currency
        return _norm(resolve_currency(code) or "")
    except Exception as _e:  # noqa: BLE001 — 讀不到選股池 → 未知(不擋、不猜)
        print(f"[backfill_to_gs] {code} 讀選股池幣別失敗:{type(_e).__name__}: {_e}",
              file=_sys.stderr)
        return ""


def backfill_to_gs(codes, *, progress_cb=None, oauth_client=None) -> dict:
    """一鍵補全部缺淨值:多檔基金抓**完整可得歷史** → 本地 cache + 雲端 nav_history(永久)。

    用途(user 2026-08-18「前面資料有缺的都要補起來」):把「持倉 ∪ 選股池」逐檔淨值一次
    補齊並存進 Google Sheet(重開不丟)。抓取走 `auto_fetch_moneydj` **完整來源鏈**
    —— 與「產生換股建議」同一條,含選股池填的 **ISIN → 晨星 timeseries(最多 ~5.5 年,
    2000 天)**,故涵蓋 user 要求的「至少近 5 年」。

    §1 Fail Loud:抓不到 / 清乾淨後為空 / 雲端寫入失敗 → 該檔 `error` 誠實回報,
      **不偽造、不靜默 no-op**;呼叫端(UI)據此列出「哪幾檔抓不到」引導改用手動 CSV。
    Gate 0(2026-08-28):寫入前逐檔與既有 nav_history 對帳(重疊日淨值),對不上 → 該檔
      **不寫**(雲端與本地 cache 皆不寫)+ `error` 誠實回報,其餘檔照跑;讀不到既有歷史
      → 本次**不寫雲端**、走 `gs_error`(fail-closed)。判定採**白名單**:只有 `clean` /
      `duplicate` 放行,`unknown` 與日後新增的 verdict 一律擋(§1 不知道 ≠ 安全)。
      被擋的檔帶 `blocked=True`(呼叫端據此把「被擋下」與「抓不到」分開報)。
    幣別守門(2026-09-01):長歷史救援換源**之前**先比幣別 —— 候選宣告的幣別與本檔
      預期幣別明確不一致 → **不換源**(原本那條序列不受影響,照既有流程往下走)+ 該檔
      `ccy_refused` 誠實記錄理由。⚠️ 與 `blocked` 不同:這不是整檔被擋,
      是**只拒絕那次替換**。⛔ 一律不做換匯(§4.1:禁止跨幣別直接混寫)。
      ⛔ **不得**把它讀成「所以這一檔有寫入」——`ccy_refused` 是在 `if s.empty`
      **之前**、也在 Gate 0 **之前**設定的,同一檔可以再疊上「清乾淨後為空」或
      「被 Gate 0 擋下」而**完全沒有寫入**(兩支都以實跑 probe 複驗過)。
      要判「今天到底有沒有寫入」請看 `fetched` / `blocked`,不是看本旗標。
      可用 `NAV_GATE0_MODE` env/secret 切 `enforce`(預設)/`observe`(判定但不擋)/`off`
      —— 見 `_gate0_mode`。⚠️ **這道閘門保護不到的情形是開放式的**(已知至少五類,
      含零重疊、code key 不一致、`gs_on=False`、其餘寫入路徑、模式被關掉)——
      詳見函式內註解,**那是已知分類不是窮舉**。
    幣別欄(2026-09-01):寫進 `nav_history` 的每一點都帶 `currency` —— 值**只取「量測線」**
      (被採用的那條序列自己宣告的 `attrs["currency"]`,且必須在 `_clean` **之前**讀,
      `pd.Series(raw)` 會殺 attrs);換源時**跟著換**。量不到 → `""`(誠實的未知)。
      ⛔ **不得**退回 `fd["currency"]`(宣告線:上游有死預設、`_correct_currency` 還會
      覆蓋量到的正確值)。⚠️ 本輪**沒有任何下游消費者讀這一欄**,先封堵污染而已。
    §2.4:GS 未啟用(缺 Service Account / 未把 SA 加為 NAV Sheet 編輯者)→ `gs_enabled=False`
      + `gs_written=0`,UI 提示去授權(否則只存本機、容器重啟即清)。
    §3.2/§4.2 不變量:序列清洗為「唯一日期 × 非 NaN × NAV>0 × 遞增」後才採用/寫入。
    §5 效能:所有檔的點**收集後一次** `append_points`(讀一次去重 + 一次 append_rows),
      省 Sheets quota(60 reads/min),不逐檔各讀一次整張表。

    Args:
        codes: 基金代號 iterable(大小寫 / 重複由本函式正規化去重,§2.1 key upper)。
        progress_cb: 可選 callable(i, n, code) —— 每檔開抓前回呼,供 UI 更新進度條
                     (L2 不碰 streamlit;回呼自身壞掉不擋補淨值)。
        oauth_client: v19.509 選填 —— SA 缺(手機無 Service Account)時,UI 傳入登入者
                     gspread client → 用使用者身分把補回的歷史寫進雲端(重開不丟)。
                     None → 純 SA(缺 SA 則 gs 未啟用,只存本地)。cron 不傳 → 行為不變。

    Returns:
        {
          "results": [{code, fetched, date_min, date_max, source, span_days,
                       error|None, blocked: bool, gate_observed: str|None,
                       ccy_refused: str|None}, ...],
          "gs_enabled": bool,      # 雲端是否啟用(SA + NAV_SHEET_ID)
          "gs_written": int,       # 本次去重後真正新增到雲端的列數
          "gs_error": str|None,    # 雲端寫入 / 寫入前對帳讀取失敗訊息
          "n_ok": int,             # 抓到淨值且沒有 error 的檔數
          "n_fail": int,           # **有 error 的檔數(含抓不到 + 被 Gate 0 擋下)**
          "n_blocked": int,        # 其中被 Gate 0 擋下的檔數 → 純「抓不到」= n_fail - n_blocked
          "n_ccy_refused": int,    # 因**幣別不一致**而拒絕換源的檔數(**不是**沒寫入)
          "gate_mode": str,        # 本次 Gate 0 模式:enforce / observe / off
        }
        ⚠️ 呼叫端**必須**用 `blocked` / `n_blocked` 區分「被擋下」與「抓不到」:
        被擋下的檔是**抓得好好的**,把它報成「抓不到 → 用手動 CSV 補」是說謊,
        而且手動 CSV 正是 `nav_history` 各寫入路徑中**沒有這道閘門**的那一條。

    v19.475(user 2026-08-18 回報「不是抓半年的嗎」):實測 8 檔保單平台基金全落回
      MoneyDJ 30 天短窗 —— 根因是 `_span_extend_insurance_nav` 的長歷史救援**只對前綴在
      `_INSURANCE_SUBDOMAIN_HINTS` 的代碼觸發**(TL/JF/… 有,AC*/AL/PY 無),user 填的
      ISIN 對非保單前綴代碼**根本沒送去晨星**。本層加「ISIN 直驅長歷史救援」:凡池中
      有 ISIN 且 auto 抓到的跨度 **< ~5 年(目標,user 2026-08-18)**,就**不管前綴**直接
      用 ISIN 試晨星 / CnYES,取跨度更長者;並逐檔回報實際 `source` + `span_days`(§5
      讓 user 看得到到底抓到哪、
      多長,不再誤以為都是 5 年)。晨星 / CnYES 若對該檔仍無資料 → 誠實留 MoneyDJ 短窗,
      UI 引導改走手動 CSV(§1 不偽造長歷史)。
    """
    import datetime as _dt
    import sys as _sys

    from services import nav_history_gs
    from services.fundclear_backfill import analyze_backfill_conflict
    from services.moneydj_fetcher import auto_fetch_moneydj
    from shared.data_quality import assess_nav_series_swap as _assess_swap
    from shared.data_quality import nav_series_currency as _series_ccy

    # ── 正規化 + 去重(保序;§2.1 code 一律 upper)────────────────────────────
    _seen: set = set()
    uniq: list = []
    for raw in codes or []:
        c = str(raw or "").strip().upper()
        if c and c not in _seen:
            _seen.add(c)
            uniq.append(c)

    # v19.509:SA 齊備**或**注入了使用者 OAuth → 雲端可寫(手機免設 SA)。
    gs_on = nav_history_gs.is_enabled() or oauth_client is not None
    # §1/§3.2:未來日上限用 TW 當日(對齊 nav_history_gs._norm_date 的未來日守衛;
    # 防上游把民國年 / 日月顛倒 misparse 成未來日污染 fetched/date_max/本地 cache)。
    _today_ts = pd.Timestamp(_dt.datetime.now(_dt.timezone(_dt.timedelta(hours=8))).date())
    # 目標跨度 5 年(user 2026-08-18「淨值等相關資料延長至 5 年」):auto 抓到 < ~5 年
    # 且池中有 ISIN → 觸發 ISIN 直驅長歷史救援(繞過保單前綴 gate),試把歷史補到 5 年。
    # 1825 天 < 各來源抓取視窗 2000 天(~5.5 年),故 5 年目標可達;採用門檻的「點數不減」
    # 護欄(稽核 F1)確保拉高門檻不會用稀疏候選換掉密集現有序列。
    _SPAN_TARGET_DAYS = 1825

    # ── Gate 0（2026-08-28）:寫進 nav_history 之前先跟既有歷史對帳 ──────────
    # 為什麼:`_rescue_by_isin` 的採用條件只看「筆數 × 跨度」,**沒有任何幣別條件**。
    # ⚠️ **2026-09-01 更新:上面這句已經不完全成立,但這道閘門一點都沒有變得不必要。**
    #    `_rescue_by_isin` 現在**多了一個幣別條件**(候選宣告的幣別與本檔預期幣別
    #    明確不一致 → 拒絕換源,見該函式 docstring)。它擋掉的是「**兩邊都宣告了、
    #    而且對不上**」那一種;擋不掉的至少有:候選來源根本不宣告幣別(cnyes)、
    #    上游 meta 的幣別本身就是錯的(死預設 USD)、以及**不經過 `_rescue_by_isin`
    #    的其餘寫入路徑**。故 Gate 0 仍是最後一道,原文保留不刪。
    # 同一檔基金的美元 / 歐元 / 避險級別在晨星、Yahoo 都查得到,跨度更長就整條換掉;
    # 而 nav_history 的去重鍵是 `(code, date)` 且**永不刪除** —— 錯的先寫進去,
    # 對的就永遠寫不進來,下游 1Y 報酬 / Sharpe / σ 全部照錯的算,而畫面不會有警示
    # (§1:錯誤的數字比沒有數字更危險;該分頁在說明書上標「無法從任何來源重建」)。
    # 手段:重用已測過的 `fundclear_backfill.analyze_backfill_conflict`,比對**重疊
    # 日期**的淨值,差幅超過 SSOT 容差就整檔擋下。
    #
    # ⚠️ **這道閘門保護不到什麼(必讀,不要以為補完了)**
    #    ⛔ 以下是**已知分類,不是窮舉清單**。上一版把它寫成封閉列舉(「只有新代碼首次
    #    回填」),稽核實測至少還有四項 —— 本 repo 已因「誠實揭露之後順手接一句沒查證的
    #    保證」連錯三次(病史見 `ui/helpers/render_state.py`)。**不要再寫「只有這 N 項」。**
    #    a) **零重疊**:只比對重疊日期 → 某個 code **第一次**回填時與既有資料零重疊 →
    #       verdict 恆為 `"clean"` → 對它完全無效。保護的是「**已經有歷史的 code**」。
    #    b) **key 不是同一個東西**:比對以 `code` 為 key,而同一檔基金在不同網站的代碼
    #       不同(MoneyDJ 內部碼 vs ISIN,見 `ui/tab_manage.py` 選股池說明)——
    #       歷史以 A 碼存、回填以 B 碼寫 → 零重疊 → 零保護。
    #    c) **`gs_on=False` 時整道閘門不跑**:沒有 SA 也沒有 OAuth → 不讀既有歷史、
    #       不判定,錯幣別序列照樣進本地 cache(`ui/tab_manage.py` 在 `backend_status`
    #       為 `local` 時按鈕仍可按)。
    #    d) **只守住 `nav_history` 多條寫入路徑中的這一條**。其餘路徑目前沒有閘門,
    #       其中 `ui/helpers/nav_history_hook.py` 在使用者每次看基金時就寫入整段序列
    #       (掛在 `ui/tab2_single_fund.py` 與 `ui/tab_fund_grp_health.py`)。
    #       →「其餘路徑要不要一起接」屬 §8.4 step 4 的**範圍決定**,已登記,本輪不做。
    #    e) **模式被關掉時不擋**:`NAV_GATE0_MODE=observe/off`(見 `_gate0_mode`)。
    #    ✅ 已修但留紀錄(2026-08-28):日期兩側不同尺(手填 `'2020/1/2'` 永遠對不上)、
    #       既有列全不可解析時謊報 `clean`、以及 `== "conflict"` 的 fail-open 黑名單。
    #
    # §5 配額:`load_points` 每次都是 `get_all_values()` 讀整張表 —— 逐檔各讀一次會把
    # 60 reads/min 吃光(與本函式「一次讀 + 一次寫」的設計相反),故**整批只讀一次**,
    # 再把各檔的既有點注入(`existing_points=`)。
    _gate_by_code: "dict | None" = None      # None = 讀不到既有歷史 → 不敢寫雲端
    _gate_error = None
    _gate_mode = _gate0_mode()               # enforce(預設) / observe / off,見 `_gate0_mode`
    if _gate_mode == "off":
        print("[backfill_to_gs] ⚠️ NAV_GATE0_MODE=off:Gate 0 完全停用,本次不做任何對帳",
              file=_sys.stderr)
    if gs_on and _gate_mode != "off":
        try:
            _gate_by_code = {}
            for _p in (nav_history_gs.load_points(oauth_client=oauth_client) or []):
                _gate_by_code.setdefault(
                    str(_p.get("code") or "").strip().upper(), []).append(_p)
        except Exception as e:  # noqa: BLE001 — §1:讀不到就不宣稱安全,更不往裡面寫
            _gate_by_code = None
            _gate_error = (f"寫入前讀不到既有 nav_history,本次**不寫雲端**"
                           f"(fail-closed,§1 不盲寫無法重建的表):"
                           f"{type(e).__name__}: {str(e)[:60]}")
            print(f"[backfill_to_gs] {_gate_error}", file=_sys.stderr)

    # ⚠️ 「**沒讀**」與「**讀失敗**」要分開:`off` 模式是刻意不讀(閘門停用),
    #    不是讀不到 —— 若混為一談,`off` 會讓 `_gate_by_code is None` 恆成立,
    #    連帶把雲端寫入整個關掉(本來只是想關掉閘門)。
    _gate_read_failed = bool(gs_on and _gate_mode != "off" and _gate_by_code is None)

    results: list = []
    all_points: list = []
    n = len(uniq)

    def _clean(raw) -> "pd.Series":
        """清洗:先驗值(非 NaN × >0)再去重(§3.2 稽核 F5:同日有效+壞值不整日丟失),
        擋未來日(§1),最後唯一日期 × 遞增。index 非日期會拋 → 由呼叫端 guard。"""
        if raw is None or not hasattr(raw, "__len__") or len(raw) == 0:
            return pd.Series(dtype=float)
        x = pd.Series(raw).dropna()
        x = x[x > 0]
        # tz-aware index → 轉 naive 對齊 _today_ts(稽核 Low:某些源可能回 tz-aware,
        # 直接與 naive Timestamp 比較會拋;非 DatetimeIndex 則無 tz 屬性 → 交由呼叫端 guard)。
        if getattr(x.index, "tz", None) is not None:
            x.index = x.index.tz_localize(None)
        x = x[x.index <= _today_ts]
        return x[~x.index.duplicated(keep="last")].sort_index()

    def _span(x: "pd.Series") -> int:
        """序列跨度(日曆日);< 2 筆回 0。"""
        return int((x.index.max() - x.index.min()).days) if len(x) >= 2 else 0

    def _rescue_by_isin(code: str, s: "pd.Series", src: str,
                        expected_ccy: str = "", cur_ccy: str = "",
                        ) -> "tuple[pd.Series, str, list, str]":
        """auto 抓到的跨度太短 → 用池中 ISIN(晨星)/ 代碼(CnYES)試長歷史,取更長者。

        gate:池中有 ISIN 才觸發(user 「填 ISIN 解鎖補淨值」的設計)。晨星走 ISIN→secId;
        CnYES 內部其實以**代碼**解析(不吃 ISIN),此處一併試,同精神以長歷史救回短窗。

        §1:各源獨立 guard,單源壞掉只 log、不影響已抓到的 MoneyDJ 序列。
        採用門檻(稽核 F1 修正):≥10 筆 **且 跨度嚴格更長 且 有效點數不減** —— 對齊
        orchestration `_adopt_if_better` 的 `_effective_nav_len` 哲學,不可用「稀疏但跨度
        略長」的候選換掉「密集」的現有序列(否則下游 3Y/5Y 年化因點數不足而失真,§1 更糟)。
        `_clean` 已把序列正規化為唯一日期 × 有效值,故 `len` 即有效點數。

        **幣別守門(2026-09-01 新增,§1 / §4.1)**:上列三個門檻**一個字都沒提到幣別**,
        而候選來源正是最會換幣別的兩個(晨星 `currencyId` 換算後淨值、Yahoo `{secId}.F`
        法蘭克福掛牌)。候選宣告的幣別與本檔預期幣別**明確不一致** → **拒絕採用**
        (顯式拒寫 + log,**絕不換算**:在寫入端偷偷換匯會做出一條「看起來連續、
        實際混過兩種幣別」的序列,比拒絕替換危險得多)。幣別未知 → 照舊採用,
        由 Gate 0 當第二道 —— 理由與已知破口見 `shared/data_quality.py` 該節。

        Returns:
            `(series, source, ccy_notes, adopted_ccy)` —— `adopted_ccy` 是**最後被採用的
            那一條序列自己宣告的幣別**(ISO 三碼或 `""`),供寫入端把觀測值存進
            `nav_history.currency`(2026-09-01 第 7 欄)。⚠️ **一定要跟著換源一起換**:
            換源之後那條序列的每一列都來自候選來源,再掛 MoneyDJ 的宣告就是憑空編一句
            (§1)。沒換源 → 原封回傳傳進來的 `cur_ccy`。
            `ccy_notes` 是被拒絕的候選說明清單
            (空 list = 沒有任何候選因幣別被拒)。⚠️ **消費者現況(2026-09-01 實測,不美化)**:
            只有 cron `scripts/weekly_nav_backfill.py` 讀它(逐檔 log ＋ 完成行聚合 ＋
            Step Summary 表)。**`ui/tab_manage.py` 的一鍵補抓沒有讀** —— 在 UI 端加渲染
            屬 §-1.5 v3 §03-2 ① 的畫面異動,要先出線框給客戶拍板,故本輪不做、就地登記。
            ⛔ 不要在別處寫「cron / UI 都看得到」—— 那是上一版犯過的那種未查證宣稱。
        """
        _ccy_notes: list = []
        try:
            from repositories.pool_repository import resolve_isin
            _isin = resolve_isin(code)
        except Exception as _e:  # noqa: BLE001 — 讀 ISIN 失敗不擋(退回 MoneyDJ 短窗)
            print(f"[backfill_to_gs] {code} resolve_isin 失敗:{type(_e).__name__}: {_e}",
                  file=_sys.stderr)
            return s, src, _ccy_notes, cur_ccy
        if not _isin:
            return s, src, _ccy_notes, cur_ccy
        # v19.477(user 提醒流程 code→ISIN→secId→**Yahoo chart** 抓 NAV):加 Yahoo 候選。
        # `_src_yahoo_finance_nav` 用池中 secId 組 `{secId}.F` 打 Yahoo v8 chart(range=10y,
        # 美國 IP 可用) —— 這是 user 明指的主路徑;晨星 timeseries / CnYES 為輔。三源都試,
        # 取跨度最長者(§ 採用門檻:≥10 筆 且 跨度更長 且 點數不減)。
        from repositories.fund.sources import (
            _src_cnyes_nav, _src_morningstar_nav, _src_yahoo_finance_nav,
        )
        _cur = _span(s)
        for _name, _fn in (("yahoo", lambda: _src_yahoo_finance_nav(code)),
                           ("morningstar", lambda: _src_morningstar_nav(code)),
                           ("cnyes", lambda: _src_cnyes_nav(code))):
            try:
                # ⚠️ 幣別要在**清洗之前**讀:`_clean` 走 dropna / 布林索引 / 排序,
                #    pandas 的 `attrs` 不保證在這些運算後還在。
                _raw_cand = _fn()
                _cand_ccy = _series_ccy(_raw_cand)
                _cand = _clean(_raw_cand)
            except Exception as _e:  # noqa: BLE001 — 單源失敗 log 後跳過,不擋整檔
                print(f"[backfill_to_gs] {code} {_name} 救援失敗:"
                      f"{type(_e).__name__}: {_e}", file=_sys.stderr)
                continue
            if len(_cand) >= 10 and _span(_cand) > _cur and len(_cand) >= len(s):
                _sw = _assess_swap(expected_ccy=expected_ccy,
                                   candidate_ccy=_cand_ccy,
                                   candidate_source=f"{_name}(ISIN)",
                                   current_source=src)
                if not _sw["safe"]:
                    # 顯式拒寫 + log(§1)。拒絕的代價只是「歷史維持原本的跨度」;
                    # 放行的代價是一條混過兩種幣別、且因 (code,date) 去重而**永遠
                    # 改不掉**的 nav_history。兩邊不對等 → fail-closed。
                    print(f"[backfill_to_gs] ⛔ {code} 拒絕 ISIN 救援換源:"
                          f"{_sw['reason']}", file=_sys.stderr)
                    _ccy_notes.append(_sw["reason"])
                    continue
                # 幣別跟著序列一起換:被採用的每一列都來自這個候選來源(見 Returns)。
                s, src, _cur, cur_ccy = (_cand, f"{_name}(ISIN)",
                                         _span(_cand), _cand_ccy)
        return s, src, _ccy_notes, cur_ccy

    for i, code in enumerate(uniq):
        if progress_cb is not None:
            try:
                progress_cb(i, n, code)
            except Exception:  # noqa: BLE001 — 進度回呼壞掉不該擋補抓
                pass
        r = {"code": code, "fetched": 0, "date_min": None, "date_max": None,
             "source": None, "span_days": 0, "error": None,
             # 2026-08-28:被 Gate 0 擋下 ≠ 抓不到。呼叫端(cron / UI)必須分得開,
             # 否則會把「抓得好好的但被擋下」講成「抓不到」,還把使用者導向手動 CSV
             # ——那正是七條寫入路徑裡**唯一沒有閘門**的那一條。用旗標而不是比對
             # 中文錯誤字串(字串一改,呼叫端就靜默失準)。
             "blocked": False,
             "gate_observed": None,
             # 2026-09-01:因**幣別不一致**而被拒絕的長歷史候選(§1 顯式拒寫要被看見)。
             # None = 沒有任何候選因幣別被拒。⚠️ 這與 `blocked` 是兩回事:`blocked` 是
             # 「整檔沒寫入」,本欄是「換源被拒、但原本那條(正確幣別的)照樣寫入」。
             "ccy_refused": None}
        # 逐檔全程 guard(§1「不擋整批」:任一檔抓取/清洗/組點爆掉 → 只記該檔 error)。
        try:
            fd = auto_fetch_moneydj(code, oauth_client=oauth_client)
            raw = fd.get("series") if isinstance(fd, dict) else None
            _had_raw = raw is not None and hasattr(raw, "__len__") and len(raw) > 0
            # ⚠️ 幣別要在 **`_clean(raw)` 之前**讀:`_clean` 第一行就是 `pd.Series(raw)`,
            #    那個建構會**殺掉 attrs**(pandas 只在輸入 attrs 完全相同時才保留)。
            #    這是「量測線」——序列自己宣告的幣別;量不到就 `""`(誠實的未知)。
            #    ⛔ 不得退回 `fd["currency"]`(宣告線):它分不出量測與猜測,
            #       上游有死預設、`_correct_currency` 還會覆蓋量到的正確值。
            _ccy = _series_ccy(raw)
            s = _clean(raw)
            src = "moneydj"
            # ISIN 直驅長歷史救援:auto 跨度短 → 不管前綴,用 ISIN 試晨星 / CnYES(§v19.475)
            if _span(s) < _SPAN_TARGET_DAYS:
                s, src, _ccy_notes, _ccy = _rescue_by_isin(
                    code, s, src, _expected_currency(code, fd), _ccy)
                if _ccy_notes:
                    r["ccy_refused"] = "；".join(_ccy_notes)
            if s.empty:
                r["error"] = (
                    "抓到序列但清乾淨後為空(全 NaN / 非正值 / 皆未來日)" if _had_raw
                    else str((fd.get("error") if isinstance(fd, dict) else "")
                             or "抓不到淨值(晨星/CnYES 查無 ISIN / MoneyDJ 掛 / 代碼不對)")[:70]
                )
            else:
                r["fetched"] = int(len(s))
                r["date_min"] = str(s.index.min().date())
                r["date_max"] = str(s.index.max().date())
                r["source"] = src
                r["span_days"] = _span(s)
                fund_name = (str(fd.get("fund_name") or fd.get("full_key") or "")
                             if isinstance(fd, dict) else "")
                _points = [{"code": code, "nav": float(v), "nav_date": idx.date(),
                            "fund_name": fund_name, "source": "backfill",
                            # 2026-09-01 nav_history 第 7 欄(見上方 `_ccy`)。
                            # 空字串 = 誠實的未知,**不是失敗** —— 全 repo 只有晨星 /
                            # Yahoo / FundClear 會宣告幣別,MoneyDJ 主線不宣告。
                            "currency": _ccy}
                           for idx, v in s.items()]
                # ── Gate 0:與既有歷史對帳(理由與「保護不到什麼」見本函式上方註解)──
                _cf = (analyze_backfill_conflict(
                           code, _points, existing_points=_gate_by_code.get(code, []))
                       if (gs_on and _gate_by_code is not None) else None)
                # 2026-08-28 稽核修正:**白名單 fail-closed**。舊版寫 `== "conflict"` 才擋
                # → `"unknown"`(讀不到 / 既有列全不可解析)與**任何日後新增的 verdict**
                # 一律靜默放行。同日 `analyze_backfill_conflict` 讓 `unknown` 更常出現,
                # 留著黑名單等於當場開一個新洞（§1:不知道 ≠ 安全）。
                _unsafe = (_cf is not None
                           and _cf.get("verdict") not in _GATE0_SAFE_VERDICTS)
                if _unsafe and _gate_mode == "enforce":
                    # fail-closed:重疊日的淨值對不上 = 幾乎必然抓到別的級別 / 幣別。
                    # **本地 cache 也不寫** —— 這條序列本身可疑,不該進任何一層。
                    r["blocked"] = True
                    r["error"] = _gate0_reason(_cf, blocked=True)
                else:
                    if _unsafe:      # observe 模式:判定了、報了,但**不擋**（見 `_gate0_mode`）
                        r["gate_observed"] = _gate0_reason(_cf, blocked=False)
                        print(f"[backfill_to_gs] {code} {r['gate_observed']}",
                              file=_sys.stderr)
                    # 本地 cache 合併(快取;雲端重啟會清 → 非致命,不擋雲端寫入)
                    try:
                        cached = _load_cache_series(code)
                        merged = s if cached.empty else pd.concat([cached, s])
                        merged = merged[~merged.index.duplicated(keep="last")].sort_index()
                        _save_cache_series(code, merged)
                    except Exception as e:  # noqa: BLE001 — §1 記 log 不靜默,但不致命
                        print(f"[backfill_to_gs] {code} 本地 cache 寫入失敗(非致命):"
                              f"{type(e).__name__}: {e}", file=_sys.stderr)
                    # 收集雲端點(最後一次 append,省 quota)。
                    # §1:閘門讀不到既有歷史時**不往雲端寫**,但抓取本身是成功的 ——
                    # 沿用本函式既有原則「抓取成功 vs 雲端寫入失敗是兩件事」,不覆蓋
                    # 各檔 fetch 結果(否則 n_ok 歸零、UI 誤報「0 檔抓到」),
                    # 寫入端狀態獨立走 gs_error;本地 cache 可重建,照寫。
                    if not _gate_read_failed:
                        all_points.extend(_points)
        except Exception as e:  # noqa: BLE001 — §1 逐檔誠實回報,不擋整批
            r["error"] = f"補抓失敗:{type(e).__name__}: {str(e)[:70]}"
        results.append(r)

    # ── 一次寫入 GS(讀一次去重 + 一次 append_rows)──────────────────────────
    # §1/§5:抓取成功 vs 雲端寫入失敗是**兩件事**,不可混為一談 —— 寫入失敗**不覆蓋**
    # 各檔 fetch 結果(否則 n_ok 歸零、UI 誤報「0 檔抓到」)。寫入狀態獨立走 gs_error。
    gs_written = 0
    gs_error = _gate_error          # 閘門讀不到既有歷史 → 本次不寫雲端,誠實回報
    if gs_on and all_points:
        try:
            _res = nav_history_gs.append_points(all_points, oauth_client=oauth_client)
            gs_written = int(_res.get("written", 0))
        except Exception as e:  # noqa: BLE001
            gs_error = f"雲端寫入失敗:{type(e).__name__}: {str(e)[:60]}"

    if progress_cb is not None:
        try:
            progress_cb(n, n, "")
        except Exception:  # noqa: BLE001
            pass

    return {
        "results": results,
        "gs_enabled": gs_on,
        "gs_written": gs_written,
        "gs_error": gs_error,                                     # 雲端寫入失敗訊息(None=正常)
        "n_ok": sum(1 for r in results if r["error"] is None and r["fetched"]),
        "n_fail": sum(1 for r in results if r["error"]),
        # 2026-08-28:被 Gate 0 擋下的檔數。**`n_fail` 含這一類** —— 純粹「抓不到」的
        # 檔數是 `n_fail - n_blocked`。分開的理由:被擋的檔**抓得好好的**,把它講成
        # 「抓不到」是說謊,而且會把使用者導向手動 CSV(唯一沒有閘門的那條路)。
        "n_blocked": sum(1 for r in results if r.get("blocked")),
        # 2026-09-01:因幣別不一致而**拒絕換源**的檔數。⚠️ 與 `n_blocked` 是兩件事 ——
        # 它只表示「**沒有換成更長的候選**」。⛔ **不是**「這些檔都有寫入」:本旗標設在
        # `if s.empty` 之前、也在 Gate 0 之前,可與兩者同時成立(實跑 probe 複驗過)。
        # 之所以要聚合出來:呼叫端要能一眼看到次數,不必去掃 results;只把理由塞進
        # results 而沒有人讀,等於「揭露了但沒人看得見」(§5)——上一版就是這樣,
        # 而且 PR 還宣稱「讓 cron 看得見」,被稽核抓到。
        # ⚠️ 現況:**cron 已接、UI 未接**(見 `_rescue_by_isin` docstring 的消費者現況)。
        # 生產端讀者(2026-09-01 實測):`scripts/weekly_nav_backfill.py::main` 的完成行,
        # 與三行外的 `res.get("n_blocked")` 對稱。⚠️ 它只是**計數** ——「哪幾檔、
        # 各自的結局是什麼」仍要掃 `results`(逐檔結局走該檔的 `_ccy_outcome`)。
        "n_ccy_refused": sum(1 for r in results if r.get("ccy_refused")),
        "gate_mode": _gate_mode,          # enforce / observe / off（誠實回報這次跑在哪個模式）
    }
