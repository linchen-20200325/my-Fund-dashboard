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


def backfill_to_gs(codes, *, progress_cb=None) -> dict:
    """一鍵補全部缺淨值:多檔基金抓**完整可得歷史** → 本地 cache + 雲端 nav_history(永久)。

    用途(user 2026-08-18「前面資料有缺的都要補起來」):把「持倉 ∪ 選股池」逐檔淨值一次
    補齊並存進 Google Sheet(重開不丟)。抓取走 `auto_fetch_moneydj` **完整來源鏈**
    —— 與「產生換股建議」同一條,含選股池填的 **ISIN → 晨星 timeseries(最多 ~5.5 年,
    2000 天)**,故涵蓋 user 要求的「至少近 5 年」。

    §1 Fail Loud:抓不到 / 清乾淨後為空 / 雲端寫入失敗 → 該檔 `error` 誠實回報,
      **不偽造、不靜默 no-op**;呼叫端(UI)據此列出「哪幾檔抓不到」引導改用手動 CSV。
    §2.4:GS 未啟用(缺 Service Account / 未把 SA 加為 NAV Sheet 編輯者)→ `gs_enabled=False`
      + `gs_written=0`,UI 提示去授權(否則只存本機、容器重啟即清)。
    §3.2/§4.2 不變量:序列清洗為「唯一日期 × 非 NaN × NAV>0 × 遞增」後才採用/寫入。
    §5 效能:所有檔的點**收集後一次** `append_points`(讀一次去重 + 一次 append_rows),
      省 Sheets quota(60 reads/min),不逐檔各讀一次整張表。

    Args:
        codes: 基金代號 iterable(大小寫 / 重複由本函式正規化去重,§2.1 key upper)。
        progress_cb: 可選 callable(i, n, code) —— 每檔開抓前回呼,供 UI 更新進度條
                     (L2 不碰 streamlit;回呼自身壞掉不擋補淨值)。

    Returns:
        {
          "results": [{code, fetched, date_min, date_max, source, span_days, error|None}, ...],
          "gs_enabled": bool,      # 雲端是否啟用(SA + NAV_SHEET_ID)
          "gs_written": int,       # 本次去重後真正新增到雲端的列數
          "n_ok": int,             # 抓到淨值的檔數
          "n_fail": int,           # 抓不到的檔數
        }

    v19.475(user 2026-08-18 回報「不是抓半年的嗎」):實測 8 檔保單平台基金全落回
      MoneyDJ 30 天短窗 —— 根因是 `_span_extend_insurance_nav` 的長歷史救援**只對前綴在
      `_INSURANCE_SUBDOMAIN_HINTS` 的代碼觸發**(TL/JF/… 有,AC*/AL/PY 無),user 填的
      ISIN 對非保單前綴代碼**根本沒送去晨星**。本層加「ISIN 直驅長歷史救援」:凡池中
      有 ISIN 且 auto 抓到的跨度 < ~2 年,就**不管前綴**直接用 ISIN 試晨星 / CnYES,取
      跨度更長者;並逐檔回報實際 `source` + `span_days`(§5 讓 user 看得到到底抓到哪、
      多長,不再誤以為都是 5 年)。晨星 / CnYES 若對該檔仍無資料 → 誠實留 MoneyDJ 短窗,
      UI 引導改走手動 CSV(§1 不偽造長歷史)。
    """
    import datetime as _dt
    import sys as _sys

    from services import nav_history_gs
    from services.moneydj_fetcher import auto_fetch_moneydj

    # ── 正規化 + 去重(保序;§2.1 code 一律 upper)────────────────────────────
    _seen: set = set()
    uniq: list = []
    for raw in codes or []:
        c = str(raw or "").strip().upper()
        if c and c not in _seen:
            _seen.add(c)
            uniq.append(c)

    gs_on = nav_history_gs.is_enabled()
    # §1/§3.2:未來日上限用 TW 當日(對齊 nav_history_gs._norm_date 的未來日守衛;
    # 防上游把民國年 / 日月顛倒 misparse 成未來日污染 fetched/date_max/本地 cache)。
    _today_ts = pd.Timestamp(_dt.datetime.now(_dt.timezone(_dt.timedelta(hours=8))).date())
    # 跨度短於此(~2 年)且池中有 ISIN → 觸發 ISIN 直驅長歷史救援(繞過保單前綴 gate)。
    _SPAN_TARGET_DAYS = 730
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

    def _rescue_by_isin(code: str, s: "pd.Series", src: str) -> "tuple[pd.Series, str]":
        """auto 抓到的跨度太短 → 用池中 ISIN(晨星)/ 代碼(CnYES)試長歷史,取更長者。

        gate:池中有 ISIN 才觸發(user 「填 ISIN 解鎖補淨值」的設計)。晨星走 ISIN→secId;
        CnYES 內部其實以**代碼**解析(不吃 ISIN),此處一併試,同精神以長歷史救回短窗。

        §1:各源獨立 guard,單源壞掉只 log、不影響已抓到的 MoneyDJ 序列。
        採用門檻(稽核 F1 修正):≥10 筆 **且 跨度嚴格更長 且 有效點數不減** —— 對齊
        orchestration `_adopt_if_better` 的 `_effective_nav_len` 哲學,不可用「稀疏但跨度
        略長」的候選換掉「密集」的現有序列(否則下游 3Y/5Y 年化因點數不足而失真,§1 更糟)。
        `_clean` 已把序列正規化為唯一日期 × 有效值,故 `len` 即有效點數。
        """
        try:
            from repositories.pool_repository import resolve_isin
            _isin = resolve_isin(code)
        except Exception as _e:  # noqa: BLE001 — 讀 ISIN 失敗不擋(退回 MoneyDJ 短窗)
            print(f"[backfill_to_gs] {code} resolve_isin 失敗:{type(_e).__name__}: {_e}",
                  file=_sys.stderr)
            return s, src
        if not _isin:
            return s, src
        from repositories.fund.sources import _src_cnyes_nav, _src_morningstar_nav
        _cur = _span(s)
        for _name, _fn in (("morningstar", lambda: _src_morningstar_nav(code)),
                           ("cnyes", lambda: _src_cnyes_nav(code))):
            try:
                _cand = _clean(_fn())
            except Exception as _e:  # noqa: BLE001 — 單源失敗 log 後跳過,不擋整檔
                print(f"[backfill_to_gs] {code} {_name} 救援失敗:"
                      f"{type(_e).__name__}: {_e}", file=_sys.stderr)
                continue
            if len(_cand) >= 10 and _span(_cand) > _cur and len(_cand) >= len(s):
                s, src, _cur = _cand, f"{_name}(ISIN)", _span(_cand)
        return s, src

    for i, code in enumerate(uniq):
        if progress_cb is not None:
            try:
                progress_cb(i, n, code)
            except Exception:  # noqa: BLE001 — 進度回呼壞掉不該擋補抓
                pass
        r = {"code": code, "fetched": 0, "date_min": None, "date_max": None,
             "source": None, "span_days": 0, "error": None}
        # 逐檔全程 guard(§1「不擋整批」:任一檔抓取/清洗/組點爆掉 → 只記該檔 error)。
        try:
            fd = auto_fetch_moneydj(code)
            raw = fd.get("series") if isinstance(fd, dict) else None
            _had_raw = raw is not None and hasattr(raw, "__len__") and len(raw) > 0
            s = _clean(raw)
            src = "moneydj"
            # ISIN 直驅長歷史救援:auto 跨度短 → 不管前綴,用 ISIN 試晨星 / CnYES(§v19.475)
            if _span(s) < _SPAN_TARGET_DAYS:
                s, src = _rescue_by_isin(code, s, src)
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
                # 本地 cache 合併(快取;雲端重啟會清 → 非致命,不擋雲端寫入)
                try:
                    cached = _load_cache_series(code)
                    merged = s if cached.empty else pd.concat([cached, s])
                    merged = merged[~merged.index.duplicated(keep="last")].sort_index()
                    _save_cache_series(code, merged)
                except Exception as e:  # noqa: BLE001 — §1 記 log 不靜默,但不致命
                    print(f"[backfill_to_gs] {code} 本地 cache 寫入失敗(非致命):"
                          f"{type(e).__name__}: {e}", file=_sys.stderr)
                # 收集雲端點(最後一次 append,省 quota)
                for idx, v in s.items():
                    all_points.append({"code": code, "nav": float(v),
                                       "nav_date": idx.date(),
                                       "fund_name": fund_name, "source": "backfill"})
        except Exception as e:  # noqa: BLE001 — §1 逐檔誠實回報,不擋整批
            r["error"] = f"補抓失敗:{type(e).__name__}: {str(e)[:70]}"
        results.append(r)

    # ── 一次寫入 GS(讀一次去重 + 一次 append_rows)──────────────────────────
    # §1/§5:抓取成功 vs 雲端寫入失敗是**兩件事**,不可混為一談 —— 寫入失敗**不覆蓋**
    # 各檔 fetch 結果(否則 n_ok 歸零、UI 誤報「0 檔抓到」)。寫入狀態獨立走 gs_error。
    gs_written = 0
    gs_error = None
    if gs_on and all_points:
        try:
            _res = nav_history_gs.append_points(all_points)
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
    }
