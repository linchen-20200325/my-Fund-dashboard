#!/usr/bin/env python3
"""scripts/probe_fx_obs_date.py — 只讀探測：Yahoo 日線時間戳取觀測日的規則，是否等於交易日（新舊兩規則並列）。

> 📌 **2026-10-14 擴充（日 K 值對應哪個時刻）**：對 `HOURLY_TICKERS`（USDTWD=X、EURTWD=X、JPYTWD=X）
> 以**同一個端點**多取一份小時 K（`interval=60m`、`range=1mo`），逐根比對「標 D 的日 K close 對應哪個時刻」
> （見下方「日 K 值對應哪個時刻」一段與報告的 `daily_value_check`）；並存完整原始日 K（`raw_daily_full`）
> 與小時 K（`hourly.raw`），以及 meta 欄位原值（`meta_snapshot`、`hourly.meta_snapshot`）。
> 不新增資料來源、不改正式行為、不碰閘門。

## 為什麼要有這支

`services/v2_tables/market_indicator.py` 以 `_obs_date`（時間戳換成世界協調時間後取日期）
決定匯率列的觀測日，但這條規則**從未以真實資料驗證過**，所以 `FX_OBS_DATE_RULE_VERIFIED`
預設關、匯率不寫列（`tests/test_v2_tables_market_indicator.py` 的
`test_時間戳落在23點UTC_現行規則取世界協調時間的日期` 記載了疑慮：若 Yahoo 的匯率日線以
倫敦午夜為界，23:00 UTC 那一根其實代表隔天，現行規則就差一天）。
開發環境連不到 Yahoo，所以由 GitHub Actions 手動觸發本腳本取得真實回應，把觀察結果寫成報告。

> ⚠️ **2026-10-13 狀態更新（不是漏刪；客戶 2026-10-13 裁示）**：第一次探測
> （`results/20261013T185433Z_run38450455092/report.json`）證實上段疑慮成立 —— 匯率日線時間戳＝倫敦當地
> 00:00，以 UTC 取日在夏令時早一天。正式規則已改為「**以來源自報的交易所時區（`meta.exchangeTimezoneName`）
> 的當地日期為準**」（`market_indicator._obs_date(stamp, exchange_tz)`）。本腳本因此**兩條規則並列**：
> - **舊規則（世界協調時間取日）**：沿用原有報告鍵（`subsets` 及其子集、`fetched_day_utc`），
>   規則改在本檔以 `legacy_utc_obs_date_of_epoch` 重現（正式程式已不再有這一條），供與第一次報告逐欄比較；
> - **新規則（交易所時區取日）**：新增 `subsets_exchange_tz` 與 `obs_date_rule_diff`；
>   `production_rows` 改以正式 `rows_from_daily_close`（新規則）跑，Series 的 attrs 照 L1 掛上
>   `exchange_tz`（取自同一份回應的 `meta.exchangeTimezoneName`，非空字串才掛，與 L1 相同）。
> 合併後要**重跑本探測**，以新規則的結果確認後，才可以只改 `FX_OBS_DATE_RULE_VERIFIED` 那一格。

## 範圍（只讀，不改任何正式行為）

- 端點：`repositories/macro/yf.py::YF_CHART_BASE`；連線：`infra.proxy.fetch_url`（與 `fetch_yf_close`
  同樣的 `interval`／`range` 參數、同樣的 `timeout=15`、`backoff_on_429=False`）。不新增資料來源、不新增套件。
- 觀測日規則**直接呼叫** `services.v2_tables.market_indicator._obs_date`，時間戳建法照抄 `fetch_yf_close`
  （`pd.to_datetime(秒, unit="s")`，無時區＝世界協調時間）——**不在本檔另寫一份規則**，免得量到的是別的東西。
  ⚠️ 2026-10-13 起唯一的例外是**舊規則**（世界協調時間取日）：正式程式已不再有它，為了與第一次報告比較，
  在本檔以 `legacy_utc_obs_date_of_epoch` 重現（只用於對照欄，不影響 `production_rows`）。
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
⚠️ 2026-10-13 起，上面三項在 `subsets` 下算的是**舊規則**（世界協調時間取日）；同樣三項以**新規則**
（交易所時區取日）再算一次放在 `subsets_exchange_tz`（另含以正式 `not_closed_cutoff_day` 界線去掉未收盤根的 `non_null_closed`，界線記在 `fetched_day_exchange_tz`），
兩規則結果不同的根列在 `obs_date_rule_diff`。`production_rows` 一律是正式新規則。
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
from datetime import datetime, timedelta, timezone
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

def legacy_utc_obs_date_of_epoch() -> Callable[[int], str]:
    """回傳「Unix 秒 → **舊規則**（世界協調時間取日期）的觀測日字串」。

    正式程式 2026-10-13 起已改為交易所時區取日，這一條只為了與第一次探測報告逐欄比較而重現：
    時間戳建法同 `fetch_yf_close`（`pd.to_datetime(秒, unit="s")`，無時區＝世界協調時間），直接取 `.date()`
    （＝舊 `_obs_date` 對無時區時間戳的行為）。
    """
    import pandas as pd

    def _fn(sec: int) -> str:
        return pd.to_datetime(sec, unit="s").date().isoformat()

    return _fn


def production_obs_date_of_epoch(exchange_tz) -> Callable[[int], str]:
    """回傳「Unix 秒 → 現行正式規則（交易所時區取日）的觀測日字串」。

    時間戳建法照抄 `repositories/macro/yf.py::fetch_yf_close`（`pd.to_datetime(秒, unit="s")`，
    無時區＝世界協調時間），日期規則直接呼叫 `market_indicator._obs_date(…, exchange_tz)`，不另寫一份。
    `exchange_tz` 認不得時 `_obs_date` 會拋 `ValueError`（呼叫端先用 `zone_known` 檢查）。
    """
    import pandas as pd
    from services.v2_tables.market_indicator import _obs_date

    def _fn(sec: int) -> str:
        return _obs_date(pd.to_datetime(sec, unit="s"), exchange_tz)

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
    """認不認得這個交易所時區字串（不認得 → 該時區不參與分組，不讓整個代號分析失敗）。

    2026-10-14 起**直接借用正式判定** `market_indicator.exchange_zone`（不複製一份）：
    只接受 `Area/Location` 形式的 IANA 名稱、排除 `posix/`／`right/`、zoneinfo 拋 `OSError` 也算不認得。
    ~~舊判定：zoneinfo 建得出來就算認得（`Factory`、`posixrules`、`UTC` 也算）~~（有意識的更正，不是漏刪：
    探測與正式路徑必須用同一套判定，否則量到的是別的東西）。
    """
    from services.v2_tables.market_indicator import exchange_zone
    return exchange_zone(name) is not None


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


def production_rows_summary(ticker, timestamps, closes, fetched_at_utc, exchange_tz=None) -> dict:
    """以正式 `rows_from_daily_close` 跑一次（純函式，不寫任何地方）：會寫幾列、跳過什麼。

    Series 建法照抄 `fetch_yf_close`（非 null 根、索引 `pd.to_datetime(秒, unit="s")`、attrs 帶 fetched_at；
    2026-10-13 起另帶 `exchange_tz`＝回應的 `meta.exchangeTimezoneName` 原字串，**非空字串才掛**，與 L1 相同）。
    """
    import pandas as pd
    from repositories.macro.yf import EXCHANGE_TZ_ATTR
    from services.v2_tables.market_indicator import rows_from_daily_close
    s = pd.Series(closes, index=pd.to_datetime(timestamps, unit="s"), dtype=float, name=ticker)
    s.attrs["source"] = f"Yahoo:{ticker}"
    s.attrs["fetched_at"] = fetched_at_utc
    if isinstance(exchange_tz, str) and exchange_tz:
        s.attrs[EXCHANGE_TZ_ATTR] = exchange_tz
    rows, err, skipped = rows_from_daily_close(ticker, s, None, value_unit=_PROBE_VALUE_UNIT)
    obs = [r["obs_date"] for r in rows]
    return {
        "row_count": len(rows),
        "first_obs_date": obs[0] if obs else None,
        "last_obs_date": obs[-1] if obs else None,
        "error": err,
        "skipped": skipped,
    }


def _closed_subset(ts, closes, obs_date_fn, fetched_day, dst_zones, local_zones, day_key) -> dict:
    """去掉觀測日不早於取得日的根之後的子集（`day_key` 是記取得日那一欄的鍵名）。"""
    c_ts, c_cl, not_closed = [], [], []
    for t, c in zip(ts, closes):
        d = obs_date_fn(t)
        if d < fetched_day:
            c_ts.append(t)
            c_cl.append(c)
        else:
            not_closed.append(_example(t, d, close=c))
    closed = subset_stats(c_ts, c_cl, obs_date_fn, dst_zones, local_zones)
    closed[day_key] = fetched_day
    closed["excluded_not_closed_bars"] = not_closed
    return closed


def obs_date_rule_diff(timestamps, legacy_fn, new_fn) -> dict:
    """舊規則（世界協調時間取日）與新規則（交易所時區取日）結果不同的筆數與例子。"""
    bad = []
    for t in timestamps:
        old, new = legacy_fn(t), new_fn(t)
        if old != new:
            bad.append({"t": t, "utc": _utc(t).isoformat(), "legacy_utc_obs_date": old,
                        "exchange_tz_obs_date": new})
    return {"diff_count": len(bad), "total": len(timestamps), "examples": bad[:EXAMPLES_MAX]}


def analyze(payload, obs_date_fn=None, fetched_at_utc: Optional[str] = None, ticker: str = "probe") -> dict:
    """單一代號的完整分析（新舊兩規則並列）。

    `obs_date_fn`：**舊規則**（Unix 秒 → 觀測日字串）；None 時用 `legacy_utc_obs_date_of_epoch()`。
    它只驅動既有的對照欄（`subsets`）；新規則一律取同一份回應的 `meta.exchangeTimezoneName`
    走正式 `_obs_date`（`subsets_exchange_tz`、`obs_date_rule_diff`、`production_rows`）。
    `fetched_at_utc`：取得當下的世界協調時間 ISO 字串；給了才算 `non_null_closed` 子集與正式列數。
    """
    if obs_date_fn is None:
        obs_date_fn = legacy_utc_obs_date_of_epoch()
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
        # 2026-10-14：meta 欄位原值（缺的列進 absent）與完整原始日 K（每一根的 Unix 秒、OHLC，null 原樣）。
        "meta_snapshot": meta_snapshot(meta),
        "raw_daily_full": raw_series(extract_ohlc(payload)),
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
        out["warnings"] = [f"交易所時區不認得：{ex_tz!r}（不參與夏冬令分組與當地日期比對，其餘照常；"
                           f"新規則無法套用，正式路徑整鍵不寫）"]

    # 新規則（交易所時區取日）：時區認不得 → 不算（正式路徑同樣整鍵不寫，見 production_rows）。
    new_fn = production_obs_date_of_epoch(ex_tz) if ex_known else None
    if new_fn is not None:
        out["subsets_exchange_tz"] = {
            "exchange_tz": ex_tz,
            "non_null": subset_stats(ts, closes, new_fn, dst_zones, local_zones),
        }
        out["obs_date_rule_diff"] = obs_date_rule_diff(ts, obs_date_fn, new_fn)
    else:
        out["subsets_exchange_tz"] = None
        out["obs_date_rule_diff"] = None

    if fetched_at_utc:
        fetched_dt = datetime.fromisoformat(fetched_at_utc.replace("Z", "+00:00"))
        fetched_day = fetched_dt.astimezone(timezone.utc).date().isoformat()
        out["subsets"]["non_null_closed"] = _closed_subset(
            ts, closes, obs_date_fn, fetched_day, dst_zones, local_zones, "fetched_day_utc")
        if new_fn is not None:
            # 未收盤界線借用正式那一條（max(世界協調時間日期, 交易所當地日期)；AI 總管 2026-10-14 裁決），不另寫一份。
            from services.v2_tables.market_indicator import not_closed_cutoff_day
            fetched_local_day = not_closed_cutoff_day(fetched_at_utc, ZoneInfo(ex_tz))
            out["subsets_exchange_tz"]["non_null_closed"] = _closed_subset(
                ts, closes, new_fn, fetched_local_day, dst_zones, local_zones, "fetched_day_exchange_tz")
        out["production_rows"] = production_rows_summary(
            ticker, ts, closes, fetched_at_utc, exchange_tz=ex_tz)
    else:
        out["subsets"]["non_null_closed"] = None
        if new_fn is not None:
            out["subsets_exchange_tz"]["non_null_closed"] = None
    return out


# ───────────────────────── 日 K 值對應哪個時刻（2026-10-14 擴充；純函式，測試不連網） ─────────────────────────
# 起因：main 上重跑的探測（`results/20261014T041819Z_run38510633247/report.json`）判讀 B 發現，寫入的「10-13」
# 匯率值與 Yahoo 自報的同日收盤對不上（USD −0.61%、EUR −1.11%、JPY +0.30%，且都落在 10-14 當日高低區間之外），
# 而上一次探測的 USD 10-12 收盤幾乎等於這次寫入的「10-13」值。所以「標 D 的日 K 值」是 D 的收盤、前一天的收盤，
# 還是某個固定時刻的快照，目前定不下來。這一段用**同一個端點**多取一份小時 K，逐根找日 K close 對應的時刻。
# ⛔ 不新增資料來源：只打同一個 Yahoo chart 端點，只改 interval／range 參數（FRED、臺北外匯經紀等需客戶核准）。
#
# ⚠️ 小時級粒度的 range 上限**本環境無法查證**（連不到 Yahoo）。社群文件普遍記載 60m 可取到約 730 日，
#    `1mo` 遠在其內；實際 Yahoo 接不接受，以報告 `hourly.status`／`hourly.error` 的原文為準。
# ⚠️ **小時 K 時間戳的慣例是前提，未實證**（#960 稽核）：本段假設 Yahoo 小時 K 的時間戳是**區間起點**，
#    open 是起點價格、close 是**終點**（起點＋`HOURLY_BAR_SEC`）的價格。因此 close 對應以終點時刻計、
#    open 對應以起點時刻計；每根同時輸出起點與終點時刻，分布也兩種各出一份，前提若不成立，讀起點那一份。

HOURLY_INTERVAL = "60m"
HOURLY_RANGE = "1mo"
HOURLY_BAR_SEC = 3600         # 與 HOURLY_INTERVAL 一致：一根小時 K 的長度（秒）
HOURLY_TICKERS = ("USDTWD=X", "EURTWD=X", "JPYTWD=X")
MATCH_WINDOW_DAYS = 31        # 只比對最近這麼多個日曆日（交易所當地日）內、已收盤的日 K
# 每根日 K 的候選範圍：觀測日本身，加上前後各這麼多個「該小時序列中實際存在的交易所日」
# （#960 稽核：以日曆日 ±2 計時，週一找不到週五；改以有小時 K 的交易所日計）。
MATCH_SCOPE_DAYS = 2
MATCH_ZONES = ("Europe/London", "America/New_York", "Asia/Taipei")
# 「相等」與「入分布」的容差（相對值）：Yahoo 回的價格是 float32 精度（例：31.927799224853516 ＝ 31.9278 的 float32），
# 同一個來源值在日 K 與小時 K 之間只會差到約 1e-7 的相對量，1e-6 對此留約十倍餘裕。
# ~~又遠小於一個報價跳動（USD 約 32 時 0.0001 ≈ 3e-6、JPY 約 0.2 時 0.0001 ≈ 5e-4）。~~
# → 2026-10-14 #960 稽核更正（有意識的更正，不是漏刪）：對「一個報價跳動」的餘裕據實如下，**常數不變**：
#   - USD（約 32，跳動 0.0001）：跳動相對約 3e-6，1e-6 只有約 3 倍餘裕；
#   - JPY 實際多為 6 位小數（例 0.201395，跳動 1e-6）：跳動相對約 5e-6，餘裕約 5 倍（舊註寫的 500 倍是錯的）；
#   - EUR（約 36）沒有固定跳動，只到 float32 解析度：float32 在 36 附近的最小單位約 3.8e-6（相對約 1.06e-7），
#     1e-6 相對約等於 9 個 float32 最小單位 —— **相差在 1e-6 相對內的兩個不同價格會被當成相等**。
#   因此另輸出 1e-5、1e-4 兩級寬鬆計數只供診斷（`MATCH_LOOSE_RELS`），主分布仍以 1e-6 為準。
# 只有差距在此容差內、且同差距根數 ties＝1 的對應才入分布（#960 稽核：近似對應不該被當成證據計數）。
MATCH_EQ_REL = 1e-6
# 診斷用的寬鬆容差（相對值）：各級另出「最佳 close 對應在容差內」根數與分布（同樣只收 ties＝1、非 partial、非重複）。
MATCH_LOOSE_RELS = (1e-5, 1e-4)
# 報告要逐字留下的 meta 欄位（缺就列進 absent，不補值）。
META_FIELDS = ("regularMarketPrice", "chartPreviousClose", "previousClose", "regularMarketTime",
               "regularMarketDayHigh", "regularMarketDayLow", "fulldayPrice", "fulldayChange",
               "fulldayChangePercent", "regularMarketChangePercent", "regularMarketVolume",
               "currentTradingPeriod", "gmtoffset", "timezone", "exchangeTimezoneName",
               "dataGranularity", "range", "validRanges")
OHLC = ("open", "high", "low", "close")
HOURLY_TIMESTAMP_CONVENTION = (
    "假設（未實證）：小時 K 時間戳＝區間起點；open＝起點價格、close＝終點（起點＋HOURLY_BAR_SEC）價格。"
    "close 對應以終點時刻計、open 對應以起點時刻計；兩種時刻都輸出，分布各出一份。")


def _num(x) -> Optional[float]:
    """數值或 None（None／NaN／±inf／轉不成數值 → None；不補值）。"""
    if x is None or isinstance(x, bool):
        return None
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def extract_ohlc(payload) -> dict:
    """Yahoo Chart JSON → `{"meta", "t", "open", "high", "low", "close", "missing_fields"}`（null 原樣保留）。

    結構檢查同 `extract_chart`；`quote[0]` 缺某一欄 → 該欄整列為 None 並記進 `missing_fields`，不讓整個分析失敗。
    """
    chart = extract_chart(payload)   # 結構不符就照 extract_chart 的原因拋 ValueError
    q0 = payload["chart"]["result"][0]["indicators"]["quote"][0]
    out = {"meta": chart["meta"], "t": chart["timestamps"], "missing_fields": []}
    n = len(chart["timestamps"])
    for f in OHLC:
        col = q0.get(f)
        if not isinstance(col, list) or len(col) != n:
            out[f] = [None] * n
            out["missing_fields"].append(f)
        else:
            out[f] = list(col)
    return out


def raw_series(ohlc: dict) -> dict:
    """完整原始序列（每一根的 Unix 秒與 OHLC），以欄為單位存，省報告體積。
    null／NaN／±inf 一律存成 None（JSON 的 null），確保報告是嚴格 JSON（#960 稽核）。"""
    return {"count": len(ohlc["t"]), "t": [int(t) for t in ohlc["t"]],
            **{f: [_num(v) for v in ohlc[f]] for f in OHLC},
            "missing_fields": list(ohlc.get("missing_fields", []))}


def meta_snapshot(meta) -> dict:
    """`META_FIELDS` 逐字照錄；缺的列進 `absent`（不補值、不推算）。"""
    meta = meta if isinstance(meta, dict) else {}
    return {"values": {f: meta[f] for f in META_FIELDS if f in meta},
            "absent": [f for f in META_FIELDS if f not in meta]}


def _local_dt(sec: int, zone: str) -> datetime:
    return _utc(sec).astimezone(ZoneInfo(zone))


def _bars(ohlc: dict) -> list[dict]:
    return [{"t": int(t), **{f: _num(ohlc[f][i]) for f in OHLC}} for i, t in enumerate(ohlc["t"])]


def hourly_day_aggregate(hourly: dict, exchange_tz: str) -> dict:
    """小時 K 依交易所當地日（以起點時刻歸日）彙總：`{日: {first_t, last_t, bars, open, high, low, close}}`。

    open＝當日第一根非 null 的 open；close＝當日最後一根非 null 的 close；high／low＝非 null 的最大／最小。
    """
    days: dict = {}
    for b in _bars(hourly):
        d = _local_dt(b["t"], exchange_tz).date().isoformat()
        days.setdefault(d, []).append(b)
    out = {}
    for d, bs in sorted(days.items()):
        bs.sort(key=lambda x: x["t"])
        opens = [b["open"] for b in bs if b["open"] is not None]
        closes = [b["close"] for b in bs if b["close"] is not None]
        highs = [b["high"] for b in bs if b["high"] is not None]
        lows = [b["low"] for b in bs if b["low"] is not None]
        out[d] = {"first_t": bs[0]["t"], "last_t": bs[-1]["t"], "bars": len(bs),
                  "open": opens[0] if opens else None, "close": closes[-1] if closes else None,
                  "high": max(highs) if highs else None, "low": min(lows) if lows else None}
    return out


def _pct(a: Optional[float], b: Optional[float]) -> Optional[float]:
    """(a − b) / b × 100；任一缺或 b 為 0 → None。"""
    if a is None or b is None or b == 0:
        return None
    return (a - b) / b * 100.0


def _times(sec: int) -> dict:
    out = {"utc": _utc(sec).strftime("%Y-%m-%d %H:%M")}
    for z in MATCH_ZONES:
        out[z] = _local_dt(sec, z).strftime("%Y-%m-%d %H:%M")
    return out


def _best(candidates: list[dict], field: str, target: float, exchange_tz: str, obs: str) -> Optional[dict]:
    """候選小時 K 之中 `field` 最接近 `target` 的一根（相同差距者計入 `ties`，回最早的一根）。

    時刻：`start`＝時間戳（區間起點）、`end`＝起點＋`HOURLY_BAR_SEC`。close 對應的交易所日差與當地時:分
    以**終點**計、open 對應以**起點**計（前提見 `HOURLY_TIMESTAMP_CONVENTION`，未實證）。
    """
    usable = [b for b in candidates if b[field] is not None]
    if not usable:
        return None
    diffs = [(abs(b[field] - target), b["t"], b) for b in usable]
    diffs.sort(key=lambda x: (x[0], x[1]))
    best_abs, _t, b = diffs[0]
    tol = MATCH_EQ_REL * abs(target)
    ties = sum(1 for d, _tt, _b in diffs if d - best_abs <= tol)
    loose = {}
    for rel in MATCH_LOOSE_RELS:
        lt = rel * abs(target)
        loose[f"{rel:g}"] = {"within_tol": best_abs <= lt,
                             "ties": sum(1 for d, _tt, _b in diffs if d - best_abs <= lt)}
    start, end = b["t"], b["t"] + HOURLY_BAR_SEC
    at = end if field == "close" else start
    obs_d = datetime.strptime(obs, "%Y-%m-%d").date()
    return {"t": start, "start": _times(start), "end": _times(end), "value": b[field], "abs_diff": best_abs,
            "pct_diff": _pct(b[field], target), "within_tol": best_abs <= tol, "ties": ties, "loose": loose,
            "timed_by": "end" if field == "close" else "start",
            "exchange_day_offset": (_local_dt(at, exchange_tz).date() - obs_d).days,
            "exchange_hhmm": _local_dt(at, exchange_tz).strftime("%H:%M"),
            "start_exchange_day_offset": (_local_dt(start, exchange_tz).date() - obs_d).days,
            "start_exchange_hhmm": _local_dt(start, exchange_tz).strftime("%H:%M")}


def _neighbors(days: list[str], obs: str, n: int) -> tuple[list[str], list[str]]:
    """`days`（已排序、該小時序列中實際存在的交易所日）中，早於 `obs` 的最後 n 個、晚於 `obs` 的最前 n 個。"""
    before = [d for d in days if d < obs][-n:] if n else []
    after = [d for d in days if d > obs][:n] if n else []
    return before, after


def _median(xs: list[float]) -> Optional[float]:
    if not xs:
        return None
    s = sorted(xs)
    m = len(s) // 2
    return s[m] if len(s) % 2 else (s[m - 1] + s[m]) / 2


def match_daily_to_hourly(daily: dict, hourly: dict, exchange_tz: str, cutoff_day: str,
                          window_days: int = MATCH_WINDOW_DAYS, scope_days: int = MATCH_SCOPE_DAYS) -> dict:
    """逐根日 K（觀測日在 [cutoff−window_days, cutoff) 內的已收盤根）找出小時 K 對應的時刻。

    - 觀測日＝日 K 時間戳的交易所當地日期（同正式 `_obs_date`）；`cutoff_day` 由呼叫端以正式
      `not_closed_cutoff_day` 算好傳入（同正式路徑的未收盤界線）。
    - 候選範圍：觀測日本身，加上前後各 `scope_days` 個「該小時序列中實際存在的交易所日」（小時 K 以起點歸日）。
      前或後不足 `scope_days` 個（小時序列的頭尾）→ `partial_coverage=True`，不入分布。
    - `best_close_match`＝小時 close 最接近日 K close 的那一根（時刻以終點計）；`best_open_match`＝小時 open
      最接近日 K close 的那一根（時刻以起點計）。各附起點與終點的 UTC／倫敦／紐約／台北時刻、差距（絕對值與 %）、
      交易所日差、同差距根數 `ties`、是否在容差內 `within_tol`。
    - `vs_same_exchange_day`：日 K 的 OHLC 對同一交易所日小時 K 彙總的差距 %，以及日 K close 是否落在該日小時 K
      高低區間內（高或低缺 → None，不當成「不在區間內」）。
    - `close_vs_day_last_hourly_close`：日 K close 對前一個／當日／後一個**有小時 K 的平日**交易所日（跳過交易所當地週六、週日；
      #960 複驗）最後一根小時 close 的差距 %；實際取的日子列在 `close_vs_day_last_hourly_close_days`。
    - 分布只收：容差內、ties＝1、非 partial_coverage、觀測日不重複的根；另出配對精度統計。
    """
    hbars = [b for b in _bars(hourly) if b["close"] is not None or b["open"] is not None]
    agg = hourly_day_aggregate(hourly, exchange_tz)
    hdays = sorted(agg)
    # 前一日／後一日對照只取「有小時 K 的**平日**交易所日」（#960 複驗：週日傍晚有小時 K 時，週一的 −1 不得指到週日）。
    # ⚠️ 只改這組對照；最佳對應的候選範圍（`_neighbors`）照舊含週日，免得漏掉真實對應。
    hweekdays = [d for d in hdays if datetime.strptime(d, "%Y-%m-%d").weekday() < 5]
    day_of = {b["t"]: _local_dt(b["t"], exchange_tz).date().isoformat() for b in hbars}
    out = {"exchange_tz": exchange_tz, "cutoff_day": cutoff_day, "window_days": window_days,
           "scope_days": scope_days, "scope_unit": "該小時序列中實際存在的交易所日",
           "hourly_timestamp_convention": HOURLY_TIMESTAMP_CONVENTION,
           "distribution_tolerance_rel": MATCH_EQ_REL,
           "hourly_bar_count": len(hourly["t"]),
           "hourly_first_utc": _utc(min(hourly["t"])).isoformat() if hourly["t"] else None,
           "hourly_last_utc": _utc(max(hourly["t"])).isoformat() if hourly["t"] else None,
           "bars": [], "skipped": Counter()}
    cutoff = datetime.strptime(cutoff_day, "%Y-%m-%d").date()
    earliest = cutoff - timedelta(days=window_days)
    in_window = []
    for d in _bars(daily):
        obs_d = _local_dt(d["t"], exchange_tz).date()
        if obs_d >= cutoff:
            out["skipped"]["not_closed"] += 1
            continue
        if obs_d < earliest:
            continue
        if d["close"] is None:
            out["skipped"]["daily_close_null"] += 1     # 只計觀測窗內的 null（#960 稽核）
            continue
        in_window.append((d, obs_d.isoformat()))
    obs_count = Counter(obs for _d, obs in in_window)

    dist_end, dist_start, dist_utc_end, dist_open = Counter(), Counter(), Counter(), Counter()
    loose_within = {f"{rel:g}": 0 for rel in MATCH_LOOSE_RELS}
    loose_dist = {f"{rel:g}": Counter() for rel in MATCH_LOOSE_RELS}
    same_last_close_eq = prev_last_close_eq = 0
    abs_diffs, pct_diffs = [], []
    n_within = n_ties = n_partial = n_dup = 0
    for d, obs in in_window:
        before, after = _neighbors(hdays, obs, scope_days)
        scope = set(before) | set(after) | ({obs} if obs in agg else set())
        cand = [h for h in hbars if day_of[h["t"]] in scope]
        partial = len(before) < scope_days or len(after) < scope_days
        dup = obs_count[obs] > 1
        rec = {"t": d["t"], **_times(d["t"]), "obs_date": obs, **{f: d[f] for f in OHLC},
               "scope_exchange_days": sorted(scope), "partial_coverage": partial,
               "duplicate_obs_date": dup}
        if not cand:
            rec["status"] = "no_hourly_in_scope"
            out["skipped"]["no_hourly_in_scope"] += 1
            out["bars"].append(rec)
            continue
        rec["status"] = "ok"
        bc = _best(cand, "close", d["close"], exchange_tz, obs)
        bo = _best(cand, "open", d["close"], exchange_tz, obs)
        rec["best_close_match"], rec["best_open_match"] = bc, bo
        n_partial += partial
        n_dup += dup
        if bc:
            abs_diffs.append(bc["abs_diff"])
            pct_diffs.append(abs(bc["pct_diff"]) if bc["pct_diff"] is not None else None)
            n_within += bc["within_tol"]
            n_ties += bc["ties"] > 1
            for lvl, lv in bc["loose"].items():
                loose_within[lvl] += lv["within_tol"]
                if lv["within_tol"] and lv["ties"] == 1 and not partial and not dup:
                    loose_dist[lvl][f"{bc['exchange_day_offset']:+d} {bc['exchange_hhmm']}"] += 1
            if bc["within_tol"] and bc["ties"] == 1 and not partial and not dup:
                dist_end[f"{bc['exchange_day_offset']:+d} {bc['exchange_hhmm']}"] += 1
                dist_start[f"{bc['start_exchange_day_offset']:+d} {bc['start_exchange_hhmm']}"] += 1
                dist_utc_end[bc["end"]["utc"][-5:]] += 1
        if bo and bo["within_tol"] and bo["ties"] == 1 and not partial and not dup:
            dist_open[f"{bo['exchange_day_offset']:+d} {bo['exchange_hhmm']}"] += 1
        same = agg.get(obs)
        if same:
            rng = (None if same["low"] is None or same["high"] is None
                   else same["low"] <= d["close"] <= same["high"])
            rec["vs_same_exchange_day"] = {"hourly": same, **{f"{f}_pct_diff": _pct(d[f], same[f]) for f in OHLC},
                                           "close_within_hourly_range": rng}
        else:
            rec["vs_same_exchange_day"] = None
        wk_before, wk_after = _neighbors(hweekdays, obs, 1)
        prev_day = wk_before[-1] if wk_before else None
        next_day = wk_after[0] if wk_after else None
        last = {"-1": _pct(d["close"], (agg.get(prev_day) or {}).get("close")),
                "+0": _pct(d["close"], (agg.get(obs) or {}).get("close")),
                "+1": _pct(d["close"], (agg.get(next_day) or {}).get("close"))}
        rec["close_vs_day_last_hourly_close"] = last
        rec["close_vs_day_last_hourly_close_days"] = {"-1": prev_day, "+0": obs if obs in agg else None,
                                                      "+1": next_day}
        tol_pct = MATCH_EQ_REL * 100
        if last["+0"] is not None and abs(last["+0"]) <= tol_pct:
            same_last_close_eq += 1
        if last["-1"] is not None and abs(last["-1"]) <= tol_pct:
            prev_last_close_eq += 1
        out["bars"].append(rec)
    out["compared"] = sum(1 for r in out["bars"] if r.get("status") == "ok")
    out["best_close_match_distribution"] = _sorted_counter(dist_end)          # 以終點計（主要）
    out["best_close_match_distribution_by_start"] = _sorted_counter(dist_start)
    out["best_close_match_utc_distribution"] = _sorted_counter(dist_utc_end)  # 終點的 UTC 時:分
    out["best_open_match_distribution"] = _sorted_counter(dist_open)          # 以起點計
    pcts = [p for p in pct_diffs if p is not None]
    out["match_precision"] = {
        "median_abs_diff": _median(abs_diffs), "max_abs_diff": max(abs_diffs) if abs_diffs else None,
        "median_abs_pct_diff": _median(pcts), "max_abs_pct_diff": max(pcts) if pcts else None,
        "within_tol": n_within, "ties_gt_1": n_ties, "partial_coverage": n_partial,
        "duplicate_obs_date": n_dup, "in_distribution": sum(dist_end.values()),
        # 診斷用寬鬆級（主分布仍以 MATCH_EQ_REL 為準）：各級的容差內根數與分布（只收 ties＝1、非 partial、非重複）。
        "loose": {lvl: {"tolerance_rel": float(lvl), "within_tol": loose_within[lvl],
                        "distribution": _sorted_counter(loose_dist[lvl])} for lvl in loose_within},
    }
    out["close_equals_same_day_last_hourly_close"] = same_last_close_eq
    out["close_equals_prev_day_last_hourly_close"] = prev_last_close_eq
    out["skipped"] = dict(out["skipped"])
    return out


def daily_value_check(daily_payload, hourly_payload, daily_fetched_at_utc: str) -> dict:
    """日 K 回應＋小時 K 回應 → `match_daily_to_hourly` 的結果。

    交易所時區取自日 K 回應的 meta（認不得 → 不比）；未收盤界線一律走正式
    `services.v2_tables.market_indicator.not_closed_cutoff_day`（不另寫一份）。
    """
    from services.v2_tables import market_indicator as mi
    daily = extract_ohlc(daily_payload)
    hourly = extract_ohlc(hourly_payload)
    ex_tz = daily["meta"].get("exchangeTimezoneName")
    if not zone_known(ex_tz):
        return {"status": "exchange_tz_unknown", "exchange_tz": ex_tz}
    cutoff = mi.not_closed_cutoff_day(daily_fetched_at_utc, ZoneInfo(ex_tz))
    out = match_daily_to_hourly(daily, hourly, ex_tz, cutoff)
    out["status"] = "ok"
    return out


def to_strict_json(obj):
    """遞迴把 NaN／±inf 轉成 None，讓報告能以 `allow_nan=False` 寫出（嚴格 JSON；#960 稽核）。"""
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {k: to_strict_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_strict_json(v) for v in obj]
    return obj


# ───────────────────────── 取數（只讀） ─────────────────────────

def _default_backoff_check(url: str):
    from infra import source_backoff as sb
    return sb.should_skip(sb.source_key(url))


def fetch_chart(ticker: str, fetcher=None, pop_fail_kind=None, backoff_check=None,
                interval: str = INTERVAL, range_: str = RANGE) -> dict:
    """以 `fetch_url` 取一個代號（預設參數與 `fetch_yf_close` 相同；小時 K 另傳 `interval`／`range_`）。

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
            r = fetcher(url, params={"interval": interval, "range": range_},
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


def _env_or_none(name: str) -> Optional[str]:
    """環境變數值；未設或空白 → None（空字串不是 SHA，不當成值記錄、不猜）。"""
    v = os.environ.get(name)
    if v is None or not v.strip():
        return None
    return v.strip()


def run(tickers, fetcher=None, pop_fail_kind=None, obs_date_fn=None,
        backoff_check=None, rejected=None) -> dict:
    """取數 ＋ 分析全部代號，回報告 dict（不寫檔）。"""
    from repositories.macro.yf import YF_CHART_BASE
    from services.v2_tables import market_indicator as mi
    if obs_date_fn is None:
        obs_date_fn = legacy_utc_obs_date_of_epoch()
    secrets = _secret_literals()
    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "endpoint": YF_CHART_BASE,
        "range": RANGE,
        "interval": INTERVAL,
        # 2026-10-13：~~正式規則＝世界協調時間取日~~ → 改為交易所時區取日（客戶裁示；不是漏刪）。
        "obs_date_rule": "services.v2_tables.market_indicator._obs_date"
                         "（pd.to_datetime(秒, unit='s') 視為世界協調時間 → 換成 meta.exchangeTimezoneName"
                         " 的當地時刻 → 取日期）；結果見 subsets_exchange_tz／production_rows",
        "obs_date_rule_legacy": "世界協調時間取日期（第一次探測時的正式規則，本檔重現）；結果見 subsets",
        "fx_obs_date_rule_verified_at_run": bool(mi.FX_OBS_DATE_RULE_VERIFIED),
        "proxy_env_set": bool(os.environ.get("PROXY_URL", "").strip()),
        "proxy_used_by_infra": _proxy_used_by_infra(),
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        # ⚠️ `github_sha` 保留原鍵名以免破壞既有讀法，但它＝**觸發 SHA**（GITHUB_SHA），
        #    **不一定是實際執行的程式碼**：push 到按鈕分支觸發時，GITHUB_SHA 是按鈕分支那顆
        #    commit，而 workflow 一律 checkout 當下的 main。要知道跑的是哪份程式碼看 `executed_sha`。
        "github_sha": os.environ.get("GITHUB_SHA"),
        "trigger_sha": _env_or_none("GITHUB_SHA"),
        # workflow 在 checkout 後以 `git rev-parse HEAD` 寫入；缺（例如本機直接跑）→ None，不猜。
        "executed_sha": _env_or_none("PROBE_EXECUTED_SHA"),
        "event_name": _env_or_none("GITHUB_EVENT_NAME"),
        "rejected_tickers": list(rejected or []),
        "tickers": {},
    }
    # ⛔ 兩輪：**所有代號的日 K 全部取完，才進第二輪取小時 K**（#960 稽核 B1）。
    #    `infra.proxy.fetch_url` 失敗時以**主機**為鍵記冷卻（429 約 30 分、其他 4xx／5xx 約 5 分、逾時約 1 分）；
    #    若逐代號「日 K → 立即小時 K」，一次小時 K 失敗就會讓後面代號（含必取的 ^VIX）的日 K 全部被跳過。
    daily_got = {}
    for tk in tickers:
        got = fetch_chart(tk, fetcher=fetcher, pop_fail_kind=pop_fail_kind, backoff_check=backoff_check)
        daily_got[tk] = got
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
    for tk in tickers:
        entry = report["tickers"][tk]
        if entry["ok"] and tk in HOURLY_TICKERS:
            entry.update(_hourly_part(tk, daily_got[tk], fetcher, pop_fail_kind, backoff_check, secrets))
    return report


def _hourly_part(tk, daily_got, fetcher, pop_fail_kind, backoff_check, secrets) -> dict:
    """同一端點多取一份小時 K，附原始序列、meta 原值與 `daily_value_check`。

    ~~小時 K 失敗不影響日 K 的結果與退出碼。~~（#960 稽核 B1：前一版逐代號交錯取數時這句不成立 ——
    小時 K 失敗會讓 `fetch_url` 對同一主機記冷卻，後面代號的日 K 因而被跳過；有意識的更正，不是漏刪。）
    → 實際成立的範圍：`run` 在**所有代號的日 K 全部取完後**才呼叫本函式，故小時 K 失敗不影響本次任何日 K 的
    結果與退出碼；但小時 K 失敗仍會讓**後續代號的小時 K** 因同一主機冷卻而被跳過（狀態記為
    `skipped_backoff_no_request`，照實寫進 `hourly.status`）。
    """
    h = fetch_chart(tk, fetcher=fetcher, pop_fail_kind=pop_fail_kind, backoff_check=backoff_check,
                    interval=HOURLY_INTERVAL, range_=HOURLY_RANGE)
    hourly = {"status": h["status"], "error": h["error"], "fetch_log": h["fetch_log"],
              "fetched_at_utc": h["fetched_at_utc"], "interval": HOURLY_INTERVAL, "range": HOURLY_RANGE}
    check = None
    if h["status"] == STATUS_OK:
        try:
            ohlc = extract_ohlc(h["payload"])
            hourly["meta_snapshot"] = meta_snapshot(ohlc["meta"])
            hourly["raw"] = raw_series(ohlc)
            check = daily_value_check(daily_got["payload"], h["payload"], daily_got["fetched_at_utc"])
        except Exception as e:
            hourly["status"] = STATUS_ANALYSIS_FAILED
            hourly["error"] = mask_text(f"小時 K 分析失敗：{type(e).__name__}: {e}", secrets)
    return {"hourly": hourly, "daily_value_check": check}


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
        nx = ((e.get("subsets_exchange_tz") or {}).get("non_null") or {}).get("obs_date_weekday", {})
        diff = e.get("obs_date_rule_diff") or {}
        lines.append(
            f"{tk}: tz={ms['exchangeTimezoneName']} gmtoffset={ms['gmtoffset']} "
            f"bars={e['raw_bar_count']} null={e['null_close_count']} "
            f"hh:mm={nn.get('utc_hhmm', {}).get('all')} "
            f"[舊UTC] 週末={wd.get('weekend_count')} "
            f"缺週五週數={wd.get('iso_weeks_missing_friday_count')}/{wd.get('iso_weeks_considered')} "
            f"同日重複={wd.get('duplicate_obs_date_count')} "
            f"[新交易所時區] 週末={nx.get('weekend_count')} "
            f"缺週五週數={nx.get('iso_weeks_missing_friday_count')}/{nx.get('iso_weeks_considered')} "
            f"同日重複={nx.get('duplicate_obs_date_count')} "
            f"新舊不同={diff.get('diff_count')}/{diff.get('total')} "
            f"正式列數(新)={pr.get('row_count')} "
            f"最後一根=regularMarketTime:{e['last_bar']['equal']}"
        )
        if "hourly" in e:
            chk = e.get("daily_value_check") or {}
            lines.append(
                f"{tk}[日K值對應]: 小時K={e['hourly']['status']} 比對根數={chk.get('compared')} "
                f"最佳close對應(以終點計；交易所日差 當地時:分；只收容差內且ties=1)={chk.get('best_close_match_distribution')} "
                f"配對精度={chk.get('match_precision')} "
                f"等於當日最後一根小時close={chk.get('close_equals_same_day_last_hourly_close')} "
                f"等於前一日最後一根小時close={chk.get('close_equals_prev_day_last_hourly_close')}"
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
    # 嚴格 JSON：NaN／±inf 一律轉 null 後以 allow_nan=False 寫出（#960 稽核）。
    # 保底（#960 複驗）：若仍寫不出嚴格 JSON（例如 dict 鍵是 NaN、值是 Decimal 這類 to_strict_json 管不到的東西），
    # 改以 default=str、allow_nan=True 照樣寫出一份，報告頂層加 `strict_json_error`（例外原文），退出碼記為失敗 ——
    # 日 K 結果不得因序列化失敗而丟失。
    strict_error = None
    try:
        text = json.dumps(to_strict_json(report), ensure_ascii=False, indent=1, allow_nan=False)
    except (ValueError, TypeError) as e:
        strict_error = f"{type(e).__name__}: {e}"
        report["strict_json_error"] = strict_error
        text = json.dumps(report, ensure_ascii=False, indent=1, allow_nan=True, default=str)
    out.write_text(text + "\n", encoding="utf-8")
    for line in _summary_lines(report):
        print(line)
    print(f"報告：{out}")
    if strict_error:
        print(f"⚠️ 報告不是嚴格 JSON（已以寬鬆格式寫出）：{strict_error}")
        return 1
    return 0 if report["tickers"].get(PRIMARY_TICKER, {}).get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
