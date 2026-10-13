#!/usr/bin/env python3
"""scripts/probe_fx_obs_date.py — 只讀探測：Yahoo 日線時間戳以世界協調時間取日期，是否等於交易日。

## 為什麼要有這支

`services/v2_tables/market_indicator.py` 以 `_obs_date`（時間戳換成世界協調時間後取日期）
決定匯率列的觀測日，但這條規則**從未以真實資料驗證過**，所以 `FX_OBS_DATE_RULE_VERIFIED`
預設關、匯率不寫列（`tests/test_v2_tables_market_indicator.py` 的
`test_時間戳落在23點UTC_現行規則取世界協調時間的日期` 記載了疑慮：若 Yahoo 的匯率日線以
倫敦午夜為界，23:00 UTC 那一根其實代表隔天，現行規則就差一天）。
開發環境連不到 Yahoo，所以由 GitHub Actions 手動觸發本腳本取得真實回應，把觀察結果寫成報告。

## 範圍（只讀，不改任何正式行為）

- 端點：`repositories/macro/yf.py::YF_CHART_BASE`；連線：`infra.proxy.fetch_url`（與 `fetch_yf_close`
  同樣的 `interval`／`range` 參數、同樣的 `timeout=15`、`backoff_on_429=False`）。不新增資料來源、不新增套件。
- 觀測日規則**直接呼叫** `services.v2_tables.market_indicator._obs_date`，時間戳建法照抄 `fetch_yf_close`
  （`pd.to_datetime(秒, unit="s")`，無時區＝世界協調時間）——**不在本檔另寫一份規則**，免得量到的是別的東西。
- **分析只用收盤非 null 的根**：正式 `fetch_yf_close` 會 `.dropna()` 丟掉那些根，算進來會造成假的
  週末／重複警訊。被排除的根另列 `null_close_bars`。
- 另以正式 `rows_from_daily_close` 實際跑一次（純函式、不寫任何地方），列出「正式路徑會寫幾列、跳過什麼」。
- 不寫任何試算表、不碰使用者設定、不呼叫任何寫入函式；**不改** `FX_OBS_DATE_RULE_VERIFIED`。
  唯一的輸出是 `--out` 指定的 JSON 檔。
- 失敗原文照錄（`fetch_url` 印出的那幾行 ＋ 失敗分類），寫進報告前遮蔽查詢字串、代理帳密與 `PROXY_URL` 字面值。
- 代號先過白名單（`TICKER_RE`），不合格直接拒絕、寫進報告，不發請求。

## 報告怎麼讀（本檔**不下結論**，結論要人看完報告後另外判定）

每個代號的 `status`：`ok`／`skipped_backoff_no_request`（來源在冷卻期，**一個封包都沒發**）／
`request_failed`（真的發了請求但失敗）／`response_unparseable`（HTTP 200 但 JSON 解不開）／
`analysis_failed`（回應結構不符）。

`subsets.non_null`（去掉 null 收盤後）與 `subsets.non_null_closed`（再去掉觀測日不早於取得日的根，
對齊 `rows_from_daily_close` 的過濾）各有：
- `utc_hhmm`：時間戳的世界協調時間時分分布，依該時區當下是否為夏令時間分組。
  若匯率日線全落在 `23:00`（夏令）／`00:00`（冬令）之類的倫敦午夜，代表一根 K 線以倫敦日界切。
- `obs_date_weekday`：以現行規則取日期後的星期分布。出現週六／週日、或缺週五，都是規則與交易日錯位的跡象。
- `obs_date_vs_local_date`：現行規則的日期與各時區當地日期不一致的筆數與例子。
另有 `last_bar`（最後一根時間戳是否等於 `meta.regularMarketTime`；相等多半表示最後一根是盤中即時值）
與 `raw_excerpt`（頭尾各 30 根原始回應，含 null）。
「有沒有差一天」要拿 `raw_excerpt` 的收盤值對照已知交易日行情再判定。

CLI
===
    python scripts/probe_fx_obs_date.py                            # 預設代號
    python scripts/probe_fx_obs_date.py --tickers "USDTWD=X,^VIX,GBPTWD=X"
    python scripts/probe_fx_obs_date.py --out probe_out/fx_obs_date_report.json

退出碼：報告一律先寫出；`USDTWD=X` 取不到或解析失敗 → 1（本探測的主要對象沒有資料，不能當成功）；
寫檔失敗 → 例外直接炸。
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import math
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

# scripts/ 下執行也能 import repositories.* / services.*（同 scripts/update_macro_history.py）
_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

PRIMARY_TICKER = "USDTWD=X"
# 必取兩個（USDTWD=X 是閘門的對象；^VIX 是同一條 `_obs_date` 的另一個使用者），其餘只供觀察。
REQUIRED_TICKERS = (PRIMARY_TICKER, "^VIX")
DEFAULT_TICKERS = REQUIRED_TICKERS + ("EURTWD=X", "JPYTWD=X", "CNYTWD=X", "CNHTWD=X")
# 代號白名單：只准大寫英數與 ^ = . -，長度 1~20；另擋含 `..` 者（路徑點段，會打到同主機其他端點）。
# 不含 `:` 與 `/`，所以也不可能以 `::` 開頭被 Actions 當成 workflow command。
TICKER_RE = re.compile(r"^[A-Z0-9^=.\-]{1,20}$")
RANGE = "2y"
INTERVAL = "1d"
EXCERPT_N = 30
# 依夏令／冬令分組用的時區：交易所時區（取自 meta）＋ 倫敦 ＋ 紐約（兩地夏令切換日不同，分開看）。
DST_ZONES = ("Europe/London", "America/New_York")
# 比對「現行規則的日期 vs 當地日期」用的時區（另加交易所時區）。
LOCAL_DATE_ZONES = ("Asia/Taipei", "Europe/London", "America/New_York")
EXAMPLES_MAX = 20
WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
DEFAULT_OUT = Path("probe_out") / "fx_obs_date_report.json"
# `rows_from_daily_close` 的 value_unit 只影響列內容，不影響過濾；用一個中性字面值即可。
_PROBE_VALUE_UNIT = "index"

STATUS_OK = "ok"
STATUS_SKIPPED_BACKOFF = "skipped_backoff_no_request"
STATUS_REQUEST_FAILED = "request_failed"
STATUS_UNPARSEABLE = "response_unparseable"
STATUS_ANALYSIS_FAILED = "analysis_failed"


# ───────────────────────── 遮蔽 ─────────────────────────

_RE_QUERY = re.compile(r"\?[^\s'\"<>)]*")
_RE_USERINFO = re.compile(r"(?P<scheme>[A-Za-z][A-Za-z0-9+.-]*://)[^\s/@'\"]+@")


def mask_text(text, secrets: tuple[str, ...] = ()) -> str:
    """遮蔽明列的秘密字面值、網址內的帳密（`scheme://帳:密@`）、查詢字串（`?` 起到空白為止）。"""
    out = str(text)
    for s in sorted((s for s in secrets if s), key=len, reverse=True):
        out = out.replace(s, "***")
    out = _RE_USERINFO.sub(lambda m: m.group("scheme") + "***@", out)
    out = _RE_QUERY.sub("?***", out)
    return out


def _secret_literals() -> tuple[str, ...]:
    """`PROXY_URL` 整串，以及其中的帳號密碼段（任一形式出現在錯誤原文裡都要遮）。"""
    raw = os.environ.get("PROXY_URL", "").strip()
    if not raw:
        return ()
    out = [raw]
    try:
        parts = urlsplit(raw)
        if parts.password and len(parts.password) >= 3:
            out.append(parts.password)
        if parts.username and parts.password:
            out.append(f"{parts.username}:{parts.password}")
    except ValueError:
        pass
    return tuple(out)


# ───────────────────────── 代號白名單 ─────────────────────────

def validate_tickers(items) -> tuple[list[str], list[dict]]:
    """→ (合格代號, 拒絕清單)。拒絕清單只存 `repr` 前 60 字，不原樣回顯（防 workflow command 注入）。"""
    ok, rejected = [], []
    for raw in items:
        s = str(raw).strip()
        if not s:
            continue
        if not TICKER_RE.fullmatch(s):
            rejected.append({"input_repr": repr(s)[:60], "reason": "不符白名單 " + TICKER_RE.pattern})
        elif ".." in s or s.strip(".") == "":
            rejected.append({"input_repr": repr(s)[:60], "reason": "含路徑點段（..）或只有點"})
        else:
            ok.append(s)
    return ok, rejected


# ───────────────────────── 觀測日規則（借用正式那一條） ─────────────────────────

def production_obs_date_of_epoch() -> Callable[[int], str]:
    """回傳「Unix 秒 → 現行規則的觀測日字串」。

    時間戳建法照抄 `repositories/macro/yf.py::fetch_yf_close`（`pd.to_datetime(秒, unit="s")`，
    無時區＝世界協調時間），日期規則直接呼叫 `market_indicator._obs_date`，不另寫一份。
    """
    import pandas as pd
    from services.v2_tables.market_indicator import _obs_date

    def _fn(sec: int) -> str:
        return _obs_date(pd.to_datetime(sec, unit="s"))

    return _fn


# ───────────────────────── 解析與分析（純函式，測試不連網） ─────────────────────────

def extract_chart(payload) -> dict:
    """Yahoo Chart JSON → `{"meta", "timestamps", "closes"}`；結構不符 → `ValueError`（附原因）。"""
    if not isinstance(payload, dict) or not isinstance(payload.get("chart"), dict):
        raise ValueError("回應不是 {'chart': {...}} 結構")
    chart = payload["chart"]
    if chart.get("error"):
        raise ValueError(f"chart.error：{json.dumps(chart['error'], ensure_ascii=False)}")
    result = chart.get("result")
    if not result:
        raise ValueError(f"chart.result 為空：{result!r}")
    r0 = result[0]
    meta = r0.get("meta") or {}
    ts = r0.get("timestamp")
    if not ts:
        raise ValueError("result[0].timestamp 缺或為空")
    try:
        closes = r0["indicators"]["quote"][0]["close"]
    except (KeyError, IndexError, TypeError) as e:
        raise ValueError(f"result[0].indicators.quote[0].close 取不到：{type(e).__name__}: {e}") from e
    if len(closes) != len(ts):
        raise ValueError(f"timestamp 與 close 長度不一致：{len(ts)} vs {len(closes)}")
    return {"meta": meta, "timestamps": [int(t) for t in ts], "closes": list(closes)}


def _is_null_close(c) -> bool:
    """與 `fetch_yf_close` 的 `pd.Series(close, dtype=float).dropna()` 同義：None／NaN 即 null。"""
    if c is None:
        return True
    try:
        return math.isnan(float(c))
    except (TypeError, ValueError):
        return True   # 轉不成數值：正式那邊 dtype=float 會直接炸；這裡當成不可用的根排除並列出


def split_null_closes(timestamps, closes) -> tuple[list[int], list, list[dict]]:
    """→ (非 null 時間戳, 對應收盤, null 根清單[{t, utc, close_repr}])。"""
    kept_t, kept_c, nulls = [], [], []
    for t, c in zip(timestamps, closes):
        if _is_null_close(c):
            nulls.append({"t": t, "utc": _utc(t).isoformat(), "close_repr": repr(c)[:40]})
        else:
            kept_t.append(t)
            kept_c.append(c)
    return kept_t, kept_c, nulls


def _utc(sec: int) -> datetime:
    return datetime.fromtimestamp(sec, tz=timezone.utc)


def zone_known(name) -> bool:
    """zoneinfo 認不認得這個時區字串（不認得 → 該時區不參與分組，不讓整個代號分析失敗）。"""
    if not isinstance(name, str) or not name:
        return False
    try:
        ZoneInfo(name)
        return True
    except Exception:   # ZoneInfoNotFoundError（KeyError 子類）、ValueError（非法字串）等
        return False


def _is_dst(sec: int, zone: str) -> bool:
    off = _utc(sec).astimezone(ZoneInfo(zone)).dst()
    return bool(off) and off.total_seconds() != 0


def _sorted_counter(c: Counter) -> dict:
    return {k: c[k] for k in sorted(c)}


def utc_hhmm_distribution(timestamps, zones) -> dict:
    """世界協調時間時分分布：`all` 不分組；`by_zone[時區]` 依該時區當下夏令（dst）／冬令（std）分組。"""
    all_c = Counter(_utc(t).strftime("%H:%M") for t in timestamps)
    by_zone = {}
    for z in zones:
        dst_c, std_c = Counter(), Counter()
        for t in timestamps:
            (dst_c if _is_dst(t, z) else std_c)[_utc(t).strftime("%H:%M")] += 1
        by_zone[z] = {"dst": _sorted_counter(dst_c), "std": _sorted_counter(std_c)}
    return {"all": _sorted_counter(all_c), "by_zone": by_zone}


def _example(sec: int, obs_date: str, **extra) -> dict:
    return {"t": sec, "utc": _utc(sec).isoformat(), "obs_date": obs_date, **extra}


def weekday_distribution(timestamps, obs_date_fn, closes=None) -> dict:
    """以現行規則取日期後的星期分布、週末筆數、同日重複、缺週五的 ISO 週。

    `closes` 給了就附在週末與重複的例子上（與時間戳逐一對應）。
    缺週五：只看「該週有觀測但沒有任何一筆落在週五」的 ISO 週，**不計第一週與最後一週**
    （區間頭尾被截斷，會誤判）。假日也會造成缺週五，名單要人工對照假日再判讀。
    """
    if closes is None:
        closes = [None] * len(timestamps)
    obs = [(t, obs_date_fn(t), c) for t, c in zip(timestamps, closes)]
    wd_c = Counter()
    weekend, by_date = [], {}
    weeks: dict[tuple[int, int], set] = {}
    for t, d, c in obs:
        dd = datetime.strptime(d, "%Y-%m-%d").date()
        wd = WEEKDAYS[dd.weekday()]
        wd_c[wd] += 1
        if dd.weekday() >= 5:
            weekend.append(_example(t, d, weekday=wd, close=c))
        by_date.setdefault(d, []).append((t, c))
        iso = dd.isocalendar()
        weeks.setdefault((iso[0], iso[1]), set()).add(dd.weekday())
    dupes = {d: tc for d, tc in by_date.items() if len(tc) > 1}
    ordered_weeks = sorted(weeks)
    inner = ordered_weeks[1:-1]
    missing_fri = [f"{y}-W{w:02d}" for (y, w) in inner if 4 not in weeks[(y, w)]]
    return {
        "counts": {w: wd_c.get(w, 0) for w in WEEKDAYS},
        "weekend_count": len(weekend),
        "weekend_examples": weekend[:EXAMPLES_MAX],
        "duplicate_obs_date_count": len(dupes),
        "duplicate_obs_date_examples": [
            {"obs_date": d, "timestamps": [x for x, _ in tc],
             "utc": [_utc(x).isoformat() for x, _ in tc], "closes": [c for _, c in tc]}
            for d, tc in sorted(dupes.items())[:EXAMPLES_MAX]
        ],
        "iso_weeks_considered": len(inner),
        "iso_weeks_missing_friday_count": len(missing_fri),
        "iso_weeks_missing_friday": missing_fri,
    }


def local_date_mismatch(timestamps, obs_date_fn, zones) -> dict:
    """現行規則的日期 vs 各時區當地日期：不一致筆數與例子。"""
    out = {}
    for z in zones:
        bad = []
        for t in timestamps:
            d = obs_date_fn(t)
            local = _utc(t).astimezone(ZoneInfo(z)).date().isoformat()
            if local != d:
                bad.append(_example(t, d, local_date=local))
        out[z] = {"mismatch_count": len(bad), "total": len(timestamps),
                  "examples": bad[:EXAMPLES_MAX]}
    return out


def last_bar_check(timestamps, meta) -> dict:
    """最後一根時間戳是否等於 `meta.regularMarketTime`。"""
    last = timestamps[-1] if timestamps else None
    rmt = meta.get("regularMarketTime")
    rmt_ok = isinstance(rmt, (int, float)) and not isinstance(rmt, bool)
    equal = last is not None and rmt_ok and int(rmt) == last
    return {
        "last_timestamp": last,
        "last_utc": _utc(last).isoformat() if last is not None else None,
        "regular_market_time": rmt,
        "regular_market_time_utc": _utc(int(rmt)).isoformat() if rmt_ok else None,
        "equal": bool(equal),
        "diff_sec": (int(rmt) - last) if (last is not None and rmt_ok) else None,
    }


def excerpt(timestamps, closes, n=EXCERPT_N) -> dict:
    """原始回應節錄：頭尾各 n 根（時間戳、世界協調時間、收盤；含 null）。"""
    rows = [{"t": t, "utc": _utc(t).isoformat(), "close": c} for t, c in zip(timestamps, closes)]
    if len(rows) <= 2 * n:
        return {"total": len(rows), "head": rows, "tail": []}
    return {"total": len(rows), "head": rows[:n], "tail": rows[-n:]}


def subset_stats(timestamps, closes, obs_date_fn, dst_zones, local_zones) -> dict:
    """同一套分布統計，套在某個子集上。"""
    if not timestamps:
        return {"bar_count": 0}
    return {
        "bar_count": len(timestamps),
        "first_utc": _utc(timestamps[0]).isoformat(),
        "last_utc": _utc(timestamps[-1]).isoformat(),
        "utc_hhmm": utc_hhmm_distribution(timestamps, dst_zones),
        "obs_date_weekday": weekday_distribution(timestamps, obs_date_fn, closes),
        "obs_date_vs_local_date": local_date_mismatch(timestamps, obs_date_fn, local_zones),
    }


def production_rows_summary(ticker, timestamps, closes, fetched_at_utc) -> dict:
    """以正式 `rows_from_daily_close` 跑一次（純函式，不寫任何地方）：會寫幾列、跳過什麼。

    Series 建法照抄 `fetch_yf_close`（非 null 根、索引 `pd.to_datetime(秒, unit="s")`、attrs 帶 fetched_at）。
    """
    import pandas as pd
    from services.v2_tables.market_indicator import rows_from_daily_close
    s = pd.Series(closes, index=pd.to_datetime(timestamps, unit="s"), dtype=float, name=ticker)
    s.attrs["source"] = f"Yahoo:{ticker}"
    s.attrs["fetched_at"] = fetched_at_utc
    rows, err, skipped = rows_from_daily_close(ticker, s, None, value_unit=_PROBE_VALUE_UNIT)
    obs = [r["obs_date"] for r in rows]
    return {
        "row_count": len(rows),
        "first_obs_date": obs[0] if obs else None,
        "last_obs_date": obs[-1] if obs else None,
        "error": err,
        "skipped": skipped,
    }


def analyze(payload, obs_date_fn, fetched_at_utc: Optional[str] = None, ticker: str = "probe") -> dict:
    """單一代號的完整分析。

    `obs_date_fn`：Unix 秒 → 觀測日字串（正式跑時用 `production_obs_date_of_epoch()`）。
    `fetched_at_utc`：取得當下的世界協調時間 ISO 字串；給了才算 `non_null_closed` 子集與正式列數。
    """
    chart = extract_chart(payload)
    meta, ts_all, closes_all = chart["meta"], chart["timestamps"], chart["closes"]
    ex_tz = meta.get("exchangeTimezoneName")
    ex_known = zone_known(ex_tz)
    extra = [ex_tz] if ex_known else []
    dst_zones = tuple(dict.fromkeys(extra + list(DST_ZONES)))
    local_zones = tuple(dict.fromkeys(extra + list(LOCAL_DATE_ZONES)))

    ts, closes, nulls = split_null_closes(ts_all, closes_all)
    out = {
        "meta_summary": {
            "exchangeTimezoneName": ex_tz,
            "exchangeTimezoneName_known": ex_known,
            "timezone": meta.get("timezone"),
            "gmtoffset": meta.get("gmtoffset"),
            "regularMarketTime": meta.get("regularMarketTime"),
            "currentTradingPeriod": meta.get("currentTradingPeriod"),
            "dataGranularity": meta.get("dataGranularity"),
            "range": meta.get("range"),
            "instrumentType": meta.get("instrumentType"),
            "exchangeName": meta.get("exchangeName"),
        },
        "meta": meta,
        "raw_bar_count": len(ts_all),
        "null_close_count": len(nulls),
        "null_close_bars": nulls,
        "fetched_at_utc": fetched_at_utc,
        "subsets": {"non_null": subset_stats(ts, closes, obs_date_fn, dst_zones, local_zones)},
        "last_bar": last_bar_check(ts_all, meta),
        "last_non_null_utc": _utc(ts[-1]).isoformat() if ts else None,
        "raw_excerpt": excerpt(ts_all, closes_all),
    }
    if not ex_known:
        out["warnings"] = [f"交易所時區不認得：{ex_tz!r}（不參與夏冬令分組與當地日期比對，其餘照常）"]

    if fetched_at_utc:
        fetched_day = datetime.fromisoformat(fetched_at_utc.replace("Z", "+00:00")) \
            .astimezone(timezone.utc).date().isoformat()
        c_ts, c_cl, not_closed = [], [], []
        for t, c in zip(ts, closes):
            d = obs_date_fn(t)
            if d < fetched_day:
                c_ts.append(t)
                c_cl.append(c)
            else:
                not_closed.append(_example(t, d, close=c))
        closed = subset_stats(c_ts, c_cl, obs_date_fn, dst_zones, local_zones)
        closed["fetched_day_utc"] = fetched_day
        closed["excluded_not_closed_bars"] = not_closed
        out["subsets"]["non_null_closed"] = closed
        out["production_rows"] = production_rows_summary(
            ticker, ts, closes, fetched_at_utc)
    else:
        out["subsets"]["non_null_closed"] = None
    return out


# ───────────────────────── 取數（只讀） ─────────────────────────

def _default_backoff_check(url: str):
    from infra import source_backoff as sb
    return sb.should_skip(sb.source_key(url))


def fetch_chart(ticker: str, fetcher=None, pop_fail_kind=None, backoff_check=None) -> dict:
    """以 `fetch_url` 取一個代號（參數與 `fetch_yf_close` 相同）。

    回 `{"status", "payload", "error", "fetch_log", "fetched_at_utc"}`；`fetch_log` 是 `fetch_url`
    印出的那幾行（已遮蔽）。來源在冷卻期時**不呼叫** `fetch_url`（它也不會發請求），狀態另記，
    讓報告分得出「沒發請求」與「發了但失敗」。
    """
    from repositories.macro.yf import YF_CHART_BASE
    if fetcher is None:
        from infra.proxy import fetch_url as fetcher
    if pop_fail_kind is None:
        from infra.proxy import pop_last_fail_kind as pop_fail_kind
    if backoff_check is None:
        backoff_check = _default_backoff_check
    secrets = _secret_literals()
    url = f"{YF_CHART_BASE}/{ticker}"
    res = {"status": None, "payload": None, "error": None, "fetch_log": [], "fetched_at_utc": None}

    skip, left, kind = backoff_check(url)
    if skip:
        res["status"] = STATUS_SKIPPED_BACKOFF
        res["error"] = f"來源冷卻中，未發請求（分類：{kind}，剩餘約 {float(left):.0f} 秒）"
        return res

    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            r = fetcher(url, params={"interval": INTERVAL, "range": RANGE},
                        timeout=15, backoff_on_429=False)
    except Exception as e:   # 照錄原文，不吞：寫進報告的 error
        res["fetch_log"] = [mask_text(x, secrets) for x in buf.getvalue().splitlines() if x.strip()]
        res["status"] = STATUS_REQUEST_FAILED
        res["error"] = mask_text(f"fetch_url 拋例外：{type(e).__name__}: {e}", secrets)
        return res
    res["fetched_at_utc"] = datetime.now(timezone.utc).isoformat()
    res["fetch_log"] = [mask_text(x, secrets) for x in buf.getvalue().splitlines() if x.strip()]
    if r is None:
        kind = pop_fail_kind() or "(無分類；404/407 或未分類)"
        res["status"] = STATUS_REQUEST_FAILED
        res["error"] = mask_text(f"fetch_url 回 None（失敗分類：{kind}）", secrets)
        return res
    try:
        res["payload"] = r.json()
    except Exception as e:
        try:
            body = r.content[:200].decode("utf-8", errors="replace")
        except Exception:
            body = "<body unavailable>"
        res["status"] = STATUS_UNPARSEABLE
        res["error"] = mask_text(f"HTTP 200 但 JSON 解析失敗：{type(e).__name__}: {e} | body={body}", secrets)
        return res
    res["status"] = STATUS_OK
    return res


def _proxy_used_by_infra() -> Optional[bool]:
    """`infra.proxy.get_proxy_config()` 是否回設定（只回布林，不輸出設定本身）。"""
    try:
        from infra.proxy import get_proxy_config
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return get_proxy_config() is not None
    except Exception:
        return None


def run(tickers, fetcher=None, pop_fail_kind=None, obs_date_fn=None,
        backoff_check=None, rejected=None) -> dict:
    """取數 ＋ 分析全部代號，回報告 dict（不寫檔）。"""
    from repositories.macro.yf import YF_CHART_BASE
    from services.v2_tables import market_indicator as mi
    if obs_date_fn is None:
        obs_date_fn = production_obs_date_of_epoch()
    secrets = _secret_literals()
    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "endpoint": YF_CHART_BASE,
        "range": RANGE,
        "interval": INTERVAL,
        "obs_date_rule": "services.v2_tables.market_indicator._obs_date"
                         "（pd.to_datetime(秒, unit='s') → 世界協調時間取日期）",
        "fx_obs_date_rule_verified_at_run": bool(mi.FX_OBS_DATE_RULE_VERIFIED),
        "proxy_env_set": bool(os.environ.get("PROXY_URL", "").strip()),
        "proxy_used_by_infra": _proxy_used_by_infra(),
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_sha": os.environ.get("GITHUB_SHA"),
        "rejected_tickers": list(rejected or []),
        "tickers": {},
    }
    for tk in tickers:
        got = fetch_chart(tk, fetcher=fetcher, pop_fail_kind=pop_fail_kind, backoff_check=backoff_check)
        entry = {"ok": False, "status": got["status"], "error": got["error"],
                 "fetch_log": got["fetch_log"]}
        if got["status"] == STATUS_OK:
            try:
                entry.update(analyze(got["payload"], obs_date_fn, got["fetched_at_utc"], tk))
                entry["ok"] = True
            except Exception as e:
                entry["status"] = STATUS_ANALYSIS_FAILED
                entry["error"] = mask_text(f"分析失敗：{type(e).__name__}: {e}", secrets)
        report["tickers"][tk] = entry
    return report


def _summary_lines(report: dict) -> list[str]:
    lines = [f"proxy_env_set={report['proxy_env_set']} proxy_used_by_infra={report['proxy_used_by_infra']}",
             f"rejected_tickers={len(report['rejected_tickers'])}（內容見報告，不回顯）"]
    for tk, e in report["tickers"].items():
        if not e.get("ok"):
            lines.append(f"{tk}: {e.get('status')} —— {e.get('error')}")
            continue
        ms = e["meta_summary"]
        nn = e["subsets"]["non_null"]
        wd = nn.get("obs_date_weekday", {})
        pr = e.get("production_rows") or {}
        lines.append(
            f"{tk}: tz={ms['exchangeTimezoneName']} gmtoffset={ms['gmtoffset']} "
            f"bars={e['raw_bar_count']} null={e['null_close_count']} "
            f"hh:mm={nn.get('utc_hhmm', {}).get('all')} 週末={wd.get('weekend_count')} "
            f"缺週五週數={wd.get('iso_weeks_missing_friday_count')}/{wd.get('iso_weeks_considered')} "
            f"同日重複={wd.get('duplicate_obs_date_count')} 正式列數={pr.get('row_count')} "
            f"最後一根=regularMarketTime:{e['last_bar']['equal']}"
        )
    return lines


def _parse_tickers(raw: Optional[str]) -> tuple[list[str], list[dict]]:
    items = raw.split(",") if raw else list(DEFAULT_TICKERS)
    ok, rejected = validate_tickers(items)
    # 必取兩個永遠在、排最前；其餘去重保序。
    return list(dict.fromkeys(list(REQUIRED_TICKERS) + ok)), rejected


def main(argv=None, fetcher=None, pop_fail_kind=None, obs_date_fn=None, backoff_check=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tickers", default=None,
                    help="逗號分隔；USDTWD=X 與 ^VIX 一律納入。預設：" + ",".join(DEFAULT_TICKERS))
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="報告輸出路徑（JSON）")
    args = ap.parse_args(argv)

    tickers, rejected = _parse_tickers(args.tickers)
    report = run(tickers, fetcher=fetcher, pop_fail_kind=pop_fail_kind,
                 obs_date_fn=obs_date_fn, backoff_check=backoff_check, rejected=rejected)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for line in _summary_lines(report):
        print(line)
    print(f"報告：{out}")
    return 0 if report["tickers"].get(PRIMARY_TICKER, {}).get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
