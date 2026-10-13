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
- 不寫任何試算表、不碰使用者設定、不呼叫任何寫入函式；**不改** `FX_OBS_DATE_RULE_VERIFIED`。
  唯一的輸出是 `--out` 指定的 JSON 檔。
- 失敗原文照錄（`fetch_url` 印出的那幾行 ＋ 失敗分類），寫進報告前遮蔽查詢字串與代理帳密。

## 報告怎麼讀（本檔**不下結論**，結論要人看完報告後另外判定）

- `utc_hhmm`：時間戳的世界協調時間時分分布，依該時區當下是否為夏令時間分組。
  若匯率日線全落在 `23:00`（夏令）／`00:00`（冬令）之類的倫敦午夜，代表一根 K 線以倫敦日界切。
- `obs_date_weekday`：以現行規則取日期後的星期分布。出現週六／週日、或缺週五，都是規則與交易日錯位的跡象。
- `obs_date_vs_local_date`：現行規則的日期與各時區當地日期不一致的筆數與例子。
- `last_bar`：最後一根時間戳是否等於 `meta.regularMarketTime`（相等多半表示最後一根是盤中即時值，不是收盤）。
- 報告只是觀察，「有沒有差一天」要拿 `raw_excerpt` 的收盤值對照已知交易日行情再判定。

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
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional
from zoneinfo import ZoneInfo

# scripts/ 下執行也能 import repositories.* / services.*（同 scripts/update_macro_history.py）
_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

PRIMARY_TICKER = "USDTWD=X"
# 必取兩個（USDTWD=X 是閘門的對象；^VIX 是同一條 `_obs_date` 的另一個使用者），其餘只供觀察。
REQUIRED_TICKERS = (PRIMARY_TICKER, "^VIX")
DEFAULT_TICKERS = REQUIRED_TICKERS + ("EURTWD=X", "JPYTWD=X", "CNYTWD=X", "CNHTWD=X")
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


# ───────────────────────── 遮蔽 ─────────────────────────

_RE_QUERY = re.compile(r"\?[^\s'\"<>)]*")
_RE_USERINFO = re.compile(r"(?P<scheme>[A-Za-z][A-Za-z0-9+.-]*://)[^\s/@'\"]+@")


def mask_text(text: str, secrets: tuple[str, ...] = ()) -> str:
    """遮蔽查詢字串（`?` 起到空白為止）、網址內的帳密（`scheme://帳:密@`），以及明列的秘密字面值。"""
    out = str(text)
    for s in secrets:
        if s:
            out = out.replace(s, "***")
    out = _RE_USERINFO.sub(lambda m: m.group("scheme") + "***@", out)
    out = _RE_QUERY.sub("?***", out)
    return out


def _secret_literals() -> tuple[str, ...]:
    return tuple(v for v in (os.environ.get("PROXY_URL", "").strip(),) if v)


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


def _utc(sec: int) -> datetime:
    return datetime.fromtimestamp(sec, tz=timezone.utc)


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


def weekday_distribution(timestamps, obs_date_fn) -> dict:
    """以現行規則取日期後的星期分布、週末筆數、同日重複、缺週五的 ISO 週。

    缺週五：只看「該週有觀測但沒有任何一筆落在週五」的 ISO 週，**不計第一週與最後一週**
    （區間頭尾被截斷，會誤判）。假日也會造成缺週五，名單要人工對照假日再判讀。
    """
    obs = [(t, obs_date_fn(t)) for t in timestamps]
    wd_c = Counter()
    weekend, by_date = [], {}
    weeks: dict[tuple[int, int], set] = {}
    for t, d in obs:
        dd = datetime.strptime(d, "%Y-%m-%d").date()
        wd = WEEKDAYS[dd.weekday()]
        wd_c[wd] += 1
        if dd.weekday() >= 5:
            weekend.append(_example(t, d, weekday=wd))
        by_date.setdefault(d, []).append(t)
        iso = dd.isocalendar()
        weeks.setdefault((iso[0], iso[1]), set()).add(dd.weekday())
    dupes = {d: ts for d, ts in by_date.items() if len(ts) > 1}
    ordered_weeks = sorted(weeks)
    inner = ordered_weeks[1:-1]
    missing_fri = [f"{y}-W{w:02d}" for (y, w) in inner if 4 not in weeks[(y, w)]]
    return {
        "counts": {w: wd_c.get(w, 0) for w in WEEKDAYS},
        "weekend_count": len(weekend),
        "weekend_examples": weekend[:EXAMPLES_MAX],
        "duplicate_obs_date_count": len(dupes),
        "duplicate_obs_date_examples": [
            {"obs_date": d, "timestamps": ts, "utc": [_utc(x).isoformat() for x in ts]}
            for d, ts in sorted(dupes.items())[:EXAMPLES_MAX]
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
    equal = (last is not None and isinstance(rmt, (int, float)) and int(rmt) == last)
    return {
        "last_timestamp": last,
        "last_utc": _utc(last).isoformat() if last is not None else None,
        "regular_market_time": rmt,
        "regular_market_time_utc": (_utc(int(rmt)).isoformat()
                                    if isinstance(rmt, (int, float)) else None),
        "equal": bool(equal),
        "diff_sec": (int(rmt) - last) if (last is not None and isinstance(rmt, (int, float))) else None,
    }


def excerpt(timestamps, closes, n=EXCERPT_N) -> dict:
    """原始回應節錄：頭尾各 n 根（時間戳、世界協調時間、收盤）。"""
    rows = [{"t": t, "utc": _utc(t).isoformat(), "close": c} for t, c in zip(timestamps, closes)]
    if len(rows) <= 2 * n:
        return {"total": len(rows), "head": rows, "tail": []}
    return {"total": len(rows), "head": rows[:n], "tail": rows[-n:]}


def analyze(payload, obs_date_fn) -> dict:
    """單一代號的完整分析。`obs_date_fn`：Unix 秒 → 觀測日字串（正式跑時用 `production_obs_date_of_epoch()`）。"""
    chart = extract_chart(payload)
    meta, ts, closes = chart["meta"], chart["timestamps"], chart["closes"]
    ex_tz = meta.get("exchangeTimezoneName")
    dst_zones = tuple(dict.fromkeys(([ex_tz] if ex_tz else []) + list(DST_ZONES)))
    local_zones = tuple(dict.fromkeys(([ex_tz] if ex_tz else []) + list(LOCAL_DATE_ZONES)))
    return {
        "meta_summary": {
            "exchangeTimezoneName": ex_tz,
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
        "bar_count": len(ts),
        "null_close_count": sum(1 for c in closes if c is None),
        "first_utc": _utc(ts[0]).isoformat(),
        "last_utc": _utc(ts[-1]).isoformat(),
        "utc_hhmm": utc_hhmm_distribution(ts, dst_zones),
        "obs_date_weekday": weekday_distribution(ts, obs_date_fn),
        "obs_date_vs_local_date": local_date_mismatch(ts, obs_date_fn, local_zones),
        "last_bar": last_bar_check(ts, meta),
        "raw_excerpt": excerpt(ts, closes),
    }


# ───────────────────────── 取數（只讀） ─────────────────────────

def fetch_chart(ticker: str, fetcher=None, pop_fail_kind=None):
    """以 `fetch_url` 取一個代號（參數與 `fetch_yf_close` 相同）。

    回 `(payload | None, error | None, log_lines)`；`log_lines` 是 `fetch_url` 印出的那幾行（已遮蔽）。
    """
    from repositories.macro.yf import YF_CHART_BASE
    if fetcher is None:
        from infra.proxy import fetch_url as fetcher
    if pop_fail_kind is None:
        from infra.proxy import pop_last_fail_kind as pop_fail_kind
    secrets = _secret_literals()
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            r = fetcher(f"{YF_CHART_BASE}/{ticker}",
                        params={"interval": INTERVAL, "range": RANGE},
                        timeout=15, backoff_on_429=False)
    except Exception as e:   # 照錄原文，不吞：寫進報告的 error
        logs = [mask_text(x, secrets) for x in buf.getvalue().splitlines() if x.strip()]
        return None, mask_text(f"fetch_url 拋例外：{type(e).__name__}: {e}", secrets), logs
    logs = [mask_text(x, secrets) for x in buf.getvalue().splitlines() if x.strip()]
    if r is None:
        kind = pop_fail_kind() or "(無分類；404/407 或未分類)"
        return None, f"fetch_url 回 None（失敗分類：{kind}）", logs
    try:
        payload = r.json()
    except Exception as e:
        body = ""
        try:
            body = r.content[:200].decode("utf-8", errors="replace")
        except Exception:
            body = "<body unavailable>"
        return None, mask_text(f"HTTP 200 但 JSON 解析失敗：{type(e).__name__}: {e} | body={body}", secrets), logs
    return payload, None, logs


def _proxy_used_by_infra() -> Optional[bool]:
    """`infra.proxy.get_proxy_config()` 是否回設定（只回布林，不輸出設定本身）。"""
    try:
        from infra.proxy import get_proxy_config
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return get_proxy_config() is not None
    except Exception:
        return None


def run(tickers, fetcher=None, pop_fail_kind=None, obs_date_fn=None) -> dict:
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
        "tickers": {},
    }
    for tk in tickers:
        payload, err, logs = fetch_chart(tk, fetcher=fetcher, pop_fail_kind=pop_fail_kind)
        entry = {"ok": False, "error": err, "fetch_log": logs}
        if payload is not None:
            try:
                entry.update(analyze(payload, obs_date_fn))
                entry["ok"] = True
            except Exception as e:
                entry["error"] = mask_text(f"分析失敗：{type(e).__name__}: {e}", secrets)
        report["tickers"][tk] = entry
    return report


def _summary_lines(report: dict) -> list[str]:
    lines = [f"proxy_env_set={report['proxy_env_set']} proxy_used_by_infra={report['proxy_used_by_infra']}"]
    for tk, e in report["tickers"].items():
        if not e.get("ok"):
            lines.append(f"{tk}: 失敗 —— {e.get('error')}")
            continue
        ms = e["meta_summary"]
        wd = e["obs_date_weekday"]
        lb = e["last_bar"]
        lines.append(
            f"{tk}: tz={ms['exchangeTimezoneName']} gmtoffset={ms['gmtoffset']} bars={e['bar_count']} "
            f"hh:mm={e['utc_hhmm']['all']} 週末={wd['weekend_count']} "
            f"缺週五週數={wd['iso_weeks_missing_friday_count']}/{wd['iso_weeks_considered']} "
            f"同日重複={wd['duplicate_obs_date_count']} 最後一根=regularMarketTime:{lb['equal']}"
        )
    return lines


def _parse_tickers(raw: Optional[str]) -> list[str]:
    items = [x.strip() for x in (raw.split(",") if raw else DEFAULT_TICKERS) if x.strip()]
    # 必取兩個永遠在、排最前；其餘去重保序。
    return list(dict.fromkeys(list(REQUIRED_TICKERS) + items))


def main(argv=None, fetcher=None, pop_fail_kind=None, obs_date_fn=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tickers", default=None,
                    help="逗號分隔；USDTWD=X 與 ^VIX 一律納入。預設：" + ",".join(DEFAULT_TICKERS))
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="報告輸出路徑（JSON）")
    args = ap.parse_args(argv)

    report = run(_parse_tickers(args.tickers), fetcher=fetcher,
                 pop_fail_kind=pop_fail_kind, obs_date_fn=obs_date_fn)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1, sort_keys=False) + "\n",
                   encoding="utf-8")
    for line in _summary_lines(report):
        print(line)
    print(f"報告：{out}")
    return 0 if report["tickers"].get(PRIMARY_TICKER, {}).get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
