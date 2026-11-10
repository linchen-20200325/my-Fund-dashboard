"""FRED 增量更新「候選方案」純函式模擬(僅供離線驗證,非 production)。

性質聲明(先讀):
- 本檔所有 A/B/B2/C 函式皆為**候選模擬**,不是 production 程式,**未獲任何核准**;
  不 import streamlit、不 import infra、不連網、不寫入 data_cache。
- 合成世界(WORLD)是測試者自行設計的「FRED 當下已公布觀測」模型:
  每筆 (觀測日, 值, 公布日);公布日與修訂版本皆為**假設**,對真實 FRED 行為 NOT VERIFIED。
- 方案定義
  baseline: 現行 production 語意——所有 series 共用「全表最大日期 + 1」為起點。
  A : 各 series 自己的最大日期 + 1;零列 series 起點 = 視窗起點(候選設計決定)。
  B : 各 series 自己的最大日期 - N 天(N 依頻率);合併 keep=last(靜默覆寫重疊區)。
  B2: 同 B 的起點,但重疊區值不同時記錄差異清單,不靜默覆寫(on_conflict 可選)。
  C : 取數前後的完整性診斷,只產生需補抓清單與 per-series 狀態,不改變起點。
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import math
import statistics
import sys
from pathlib import Path

import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))
_spec = importlib.util.spec_from_file_location(
    "umh_b1_sim_target", _REPO_ROOT / "scripts" / "update_macro_history.py")
PROD = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(PROD)

D = dt.date
COLS = ["date", "series_id", "value"]
ONE = dt.timedelta(days=1)

# 候選設計決定(皆未核准):各頻率的重疊天數 N、視窗年數、診斷門檻。
B_OVERLAP_DAYS = {"D": 7, "W": 21, "M": 100}
DEFAULT_YEARS = 15          # update_macro_history.yml 的 bootstrap 預設為 15
# 診斷「最新觀測日落後門檻」,取自本檔 CLAUDE.md §2.4 的紅燈分界(日 7 / 月 75),週頻 21 為候選
AGE_LIMIT_DAYS = {"D": 7, "W": 21, "M": 75}


# ── 世界模型 ────────────────────────────────────────────────
def obs(d, v, release=None):
    """(觀測日, 值, 公布日);未給公布日 = 觀測日隔天。"""
    return (d, float(v), release if release is not None else d + ONE)


def daily_world(start, end, base=1.0):
    return [obs(start + dt.timedelta(days=i), base + i)
            for i in range((end - start).days + 1)]


def periodic_world(start, end, step_days, base=1.0):
    out, d, i = [], start, 0
    while d <= end:
        out.append(obs(d, base + i))
        d += dt.timedelta(days=step_days)
        i += 1
    return out


def fetch_world(world, sid, start, end, today):
    """模擬 observation_start/end 過濾 + 只回 today 前已公布、同觀測日取最新公布版本。"""
    best = {}
    for d, v, rel in world.get(sid, []):
        if start <= d <= end and rel <= today:
            if d not in best or rel >= best[d][1]:
                best[d] = (v, rel)
    rows = sorted((d, vr[0]) for d, vr in best.items())
    return pd.DataFrame(rows, columns=["date", "value"])


def empty_table():
    return pd.DataFrame(columns=COLS)


def as_dates(df, sid):
    return sorted(pd.to_datetime(df[df.series_id == sid].date).dt.date)


def values(df, sid):
    sub = df[df.series_id == sid]
    return {pd.Timestamp(d).date(): v for d, v in zip(sub.date, sub.value)}


# ── 頻率與視窗 ──────────────────────────────────────────────
def freq_class(dates):
    """依資料自身中位數間距推頻率(D/W/M);不足 3 列回 None。推論,非宣告。"""
    ds = sorted(pd.to_datetime(list(dates)))
    if len(ds) < 3:
        return None
    med = statistics.median((b - a).days for a, b in zip(ds, ds[1:]))
    return "D" if med <= 4 else ("W" if med <= 10 else "M")


def window_start(today, years):
    return today - dt.timedelta(days=years * 365)


def _series_max(table, sid):
    if table is None or table.empty:
        return None
    sub = table[table.series_id == sid]
    return None if sub.empty else pd.to_datetime(sub.date).max().date()


def _n_days(table, sid, n_map):
    sub = table[table.series_id == sid] if table is not None and not table.empty else None
    f = freq_class(sub.date) if sub is not None else None
    return n_map.get(f or "M")      # 不足以推頻率 → 取最保守(最長)的 M


# ── 起點計算(各方案) ───────────────────────────────────────
def compute_starts(strategy, table, ids, today, years=DEFAULT_YEARS, n_map=None):
    n_map = n_map or B_OVERLAP_DAYS
    wstart = window_start(today, years)
    gmax = None
    if table is not None and not table.empty:
        gmax = pd.to_datetime(table.date).max().date()
    out = {}
    for sid in ids:
        smax = _series_max(table, sid)
        if strategy == "baseline":
            out[sid] = wstart if gmax is None else gmax + ONE
        elif strategy == "A":
            out[sid] = wstart if smax is None else smax + ONE
        elif strategy in ("B", "B2"):
            out[sid] = (wstart if smax is None
                        else max(wstart, smax - dt.timedelta(days=_n_days(table, sid, n_map))))
        else:
            raise ValueError(strategy)
    return out


# ── 完整性診斷 C ────────────────────────────────────────────
def diagnose(table, ids, today, years=DEFAULT_YEARS, prev_counts=None,
             age_limit=None, head_tol_days=30):
    """C:只診斷,不改起點。回 {sid: {"flags": [...], "suggest_start": date|None}}。"""
    age_limit = age_limit or AGE_LIMIT_DAYS
    wstart = window_start(today, years)
    res = {}
    for sid in ids:
        sub = table[table.series_id == sid] if table is not None and not table.empty else None
        flags, suggest = [], None
        if sub is None or sub.empty:
            flags.append("zero_rows")
            suggest = wstart
        else:
            ds = sorted(pd.to_datetime(sub.date))
            f = freq_class(ds) or "M"
            if (today - ds[-1].date()).days > age_limit[f]:
                flags.append("stale")
                suggest = ds[-1].date() + ONE
            if (ds[0].date() - wstart).days > head_tol_days:
                flags.append("head_gap")
                suggest = wstart
            if len(ds) >= 3:
                spacing = [(b - a).days for a, b in zip(ds, ds[1:])]
                med = statistics.median(spacing)
                limit = max(1.5 * med, med + 4)
                for a, b in zip(ds, ds[1:]):
                    if (b - a).days > limit:
                        flags.append("internal_gap")
                        suggest = a.date() if suggest is None else min(suggest, a.date())
                        break
            if prev_counts and sid in prev_counts and len(sub) < 0.9 * prev_counts[sid]:
                flags.append("row_drop")
        res[sid] = {"flags": flags, "suggest_start": suggest}
    return res


def needs_refetch(diag):
    return sorted(s for s, v in diag.items() if v["flags"])


# ── 合併 ────────────────────────────────────────────────────
def merge_keep_last(old, new):
    """與 production 同一函式(keep=last 靜默覆寫)。"""
    return PROD._merge_dedupe(old, new, key=["date", "series_id"])


def merge_log_conflicts(old, new, on_conflict="keep_old"):
    """B2:重疊區值不同時記錄差異;keep_old 保留舊值、apply_new 採新值,兩者都不靜默。"""
    diffs = []
    if old is None or old.empty:
        return merge_keep_last(old, new), diffs
    o = old.set_index(["date", "series_id"]).value
    n = new.set_index(["date", "series_id"]).value
    common = o.index.intersection(n.index)
    for key in common:
        if not math.isclose(o[key], n[key], rel_tol=1e-12, abs_tol=1e-12):
            diffs.append({"date": key[0], "series_id": key[1],
                          "old": float(o[key]), "new": float(n[key])})
    if on_conflict == "keep_old":
        keep = new.set_index(["date", "series_id"]).drop(index=common).reset_index()
        return merge_keep_last(old, keep[COLS]), diffs
    return merge_keep_last(old, new), diffs


# ── 一次增量(純函式) ───────────────────────────────────────
def pure_update(strategy, table, ids, today, world, fail=frozenset(),
                years=DEFAULT_YEARS, on_conflict="keep_old", n_map=None):
    """回 (新表, meta);meta 含 production 相同四欄 + 候選的 series_status / conflicts。"""
    starts = compute_starts(strategy, table, ids, today, years, n_map)
    frames, status = [], {}
    for sid in ids:
        st = starts[sid]
        if st > today:
            status[sid] = {"start": st, "fetched": 0, "status": "up_to_date"}
            continue
        df = pd.DataFrame(columns=["date", "value"]) if sid in fail \
            else fetch_world(world, sid, st, today, today)
        # 注意:production 的 _fred_get_single 對「失敗」與「無新資料」皆回空表,兩者不可區分
        status[sid] = {"start": st, "fetched": len(df),
                       "status": "ok" if len(df) else "empty_or_failed"}
        if len(df):
            df = df.copy()
            df["series_id"] = sid
            frames.append(df[COLS])
    new = pd.concat(frames, ignore_index=True) if frames else empty_table()
    meta = {"name": "fred_indicators", "last_updated": None, "row_count": 0,
            "last_error": None, "series_status": status, "conflicts": []}
    if new.empty:
        meta["last_error"] = "抓取結果為空"
        out = table
    else:
        if strategy == "B2":
            out, meta["conflicts"] = merge_log_conflicts(table, new, on_conflict)
        else:
            out = merge_keep_last(table, new)
    if out is not None and not out.empty:
        meta["last_updated"] = pd.to_datetime(out.date).max().date().isoformat()
        meta["row_count"] = len(out)
    return out, meta


# ── 時間線驅動(baseline 走 production update_one) ─────────
def run_timeline(strategy, runs, world, tmp_dir, initial=None, years=DEFAULT_YEARS,
                 on_conflict="keep_old", n_map=None):
    """runs: [{"today": date, "ids": (...), "fail": set}];
    回 (最終表, metas, 每輪起點)。baseline 使用 production update_one(真實函式,取數以假函式替換)。"""
    metas, starts_log = [], []
    if strategy in ("baseline", "C"):          # C 不改起點 → 表與 baseline 相同
        tmp_dir = Path(tmp_dir)
        PROD.CACHE_DIR = tmp_dir
        PROD.META_PATH = tmp_dir / "metadata.json"
        PROD._FRED_INTER_CALL_SLEEP_SEC = 0.0
        if initial is not None:
            initial.to_parquet(tmp_dir / "fred_indicators.parquet", compression="snappy", index=False)
        calls = []
        cur = {}

        def fake_get(sid, start, end, api_key):
            calls.append((sid, start, end))
            if sid in cur["fail"]:
                return pd.DataFrame()
            return fetch_world(world, sid, start, end, cur["today"])

        PROD._fred_get_single = fake_get
        for r in runs:
            PROD.FRED_SERIES_IDS = tuple(r["ids"])
            cur.update(today=r["today"], fail=set(r.get("fail", ())))
            n0 = len(calls)
            metas.append(PROD.update_one("fred_indicators", r["today"], False, years,
                                         "fake" + "key"))
            starts_log.append({c[0]: c[1] for c in calls[n0:]})
        path = tmp_dir / "fred_indicators.parquet"
        final = pd.read_parquet(path) if path.exists() else empty_table()
        return final, metas, starts_log
    table = initial
    for r in runs:
        starts_log.append(compute_starts(strategy, table, r["ids"], r["today"], years, n_map))
        table, meta = pure_update(strategy, table, r["ids"], r["today"], world,
                                  fail=set(r.get("fail", ())), years=years,
                                  on_conflict=on_conflict, n_map=n_map)
        metas.append(meta)
    return (table if table is not None else empty_table()), metas, starts_log


# ── 真實快取副本的離線起點算術(只算術,不預測值) ─────────────
SIM_DAY = D(2026, 11, 10)   # 固定模擬日常數,不使用 datetime.now


def real_copy_starts(table, ids, sim_day=SIM_DAY, years=DEFAULT_YEARS):
    """對記憶體中的快取副本,算各方案「若 sim_day 增量」的取數起點與 C 診斷旗標。"""
    t = table.copy()
    t["date"] = pd.to_datetime(t["date"]).dt.date
    rows = []
    st = {k: compute_starts(k, t, ids, sim_day, years) for k in ("baseline", "A", "B")}
    diag = diagnose(t, ids, sim_day, years)
    for sid in ids:
        sub = t[t.series_id == sid]
        ds = sorted(sub.date)
        rows.append({
            "series_id": sid, "rows": len(sub),
            "min": ds[0] if ds else None, "max": ds[-1] if ds else None,
            "cadence": freq_class(ds) if ds else None,
            "baseline": st["baseline"][sid], "A": st["A"][sid], "B": st["B"][sid],
            "C_flags": ",".join(diag[sid]["flags"]) or "-",
            "C_suggest": diag[sid]["suggest_start"],
        })
    return pd.DataFrame(rows)
