"""Yahoo 指數日線受控唯讀探測（方案 B「S＋P」，客戶授權 2026-11-09，DEC-2026-11-09-08）。

## 這支腳本做什麼

對 Yahoo Finance chart v8 端點（非 TWSE／CBOE 官方）依序發出**恰好四個**授權請求，
把每個成功回應的原始位元組、sha256、白名單標頭與純描述性解析結果寫成一份 JSON 報告。

1. ``^GSPC`` range=2y interval=1d
2. ``^VIX``  range=2y interval=1d
3. ``^TWII`` range=2y interval=1d
4. ``^VIX``  period1=2026-05-29T00:00Z period2=2026-06-09T00:00Z interval=1d

## 為什麼 HTTP 實發次數可證明不超過 4

* 四個請求硬編碼在 ``AUTHORIZED_REQUESTS``，沒有任何 CLI 參數或環境變數能增減代號、range、interval。
* 全程只有 ``_send_one`` 會呼叫 opener；它在送出**之前**先呼叫 ``RequestBudget.before_send``，
  計數達 ``HARD_LIMIT``（＝4）後再呼叫一律 ``raise HardCapExceeded``，不論呼叫端邏輯有無 bug。
* 預設 opener 用標準庫 ``urllib``：單次 GET、不重試、不跟隨轉址（3xx 一律視為失敗並停止）、
  不讀環境代理設定（``ProxyHandler({})``），因此沒有任何會在底層悄悄多發請求的機制。
* 任何失敗立即停止；後續請求記為 ``skipped_not_attempted``，不補值、不重試。

## 不做什麼

不 import ``infra.proxy`` ／ ``fetch_url``（它預設帶重試且可能降級直連）、不用 ``PROXY_URL``、
不寫 ``data_cache``、不寫 Sheet、不做任何日期規則判定。純描述；單次探測不得判定永久日期規則。
"""
from __future__ import annotations

import argparse
import base64
import calendar
import datetime as _dt
import gzip
import hashlib
import json
import os
import re
import sys
import time
import zlib
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

AUTH_REF = "DEC-2026-11-09-08"
AUTH_CODE = "yahoo_indices_sp_20261109"
DATA_SOURCE_NOTE = "Yahoo Finance chart v8（非 TWSE／CBOE 官方）"
YF_CHART_BASE = "https://query1.finance.yahoo.com/v8/finance/chart"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
ACCEPT_LANGUAGE = "zh-TW,zh;q=0.9"
MIN_INTERVAL_S = 5.0
TIMEOUT_S = 30
COOLDOWN_MINUTES = 30
DEFAULT_OUT = f"probe_out/{AUTH_CODE}.json"

PERIOD1_ISO = "2026-05-29T00:00:00Z"
PERIOD2_ISO = "2026-06-09T00:00:00Z"
PERIOD1_EPOCH = calendar.timegm((2026, 5, 29, 0, 0, 0))
PERIOD2_EPOCH = calendar.timegm((2026, 6, 9, 0, 0, 0))
TARGET_DATE = "2026-06-03"

# 唯一授權的四個請求。tuple of (key, value) 以固定參數順序組 query string。
AUTHORIZED_REQUESTS: Tuple[Dict[str, Any], ...] = (
    {"index": 1, "symbol": "^GSPC", "params": (("interval", "1d"), ("range", "2y"))},
    {"index": 2, "symbol": "^VIX", "params": (("interval", "1d"), ("range", "2y"))},
    {"index": 3, "symbol": "^TWII", "params": (("interval", "1d"), ("range", "2y"))},
    {
        "index": 4,
        "symbol": "^VIX",
        "params": (
            ("period1", str(PERIOD1_EPOCH)),
            ("period2", str(PERIOD2_EPOCH)),
            ("interval", "1d"),
        ),
    },
)
HARD_LIMIT = 4
assert len(AUTHORIZED_REQUESTS) == HARD_LIMIT

HEADER_WHITELIST = (
    "date", "content-type", "content-length", "cache-control", "age",
    "expires", "last-modified", "etag", "content-encoding", "vary",
    "x-yahoo-request-id", "server",
)
COOLDOWN_STATUSES = (401, 403, 429, 999)
# 專案 AI 建議值（非客戶裁示）：單一回應讀取與 gzip 解壓縮的位元組上限。
MAX_RESPONSE_BYTES = 5 * 1024 * 1024

# 交易所時區的後備（僅在回應 meta 缺 exchangeTimezoneName 時**不**使用；缺就記缺）。
_WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


class ResponseTooLarge(RuntimeError):
    """回應（或解壓縮後）超過 MAX_RESPONSE_BYTES。"""


class HardCapExceeded(RuntimeError):
    """第 HARD_LIMIT + 1 次送出被程式層拒絕。"""


class RequestBudget:
    """HTTP 實發次數計數器；送出前遞增，達上限後拒絕。"""

    def __init__(self, limit: int = HARD_LIMIT) -> None:
        self.limit = min(int(limit), HARD_LIMIT)
        self.http_requests_attempted = 0

    def before_send(self) -> None:
        if self.http_requests_attempted >= self.limit:
            raise HardCapExceeded(
                f"hard cap {self.limit} reached; refusing request "
                f"#{self.http_requests_attempted + 1}"
            )
        self.http_requests_attempted += 1


# ---------------------------------------------------------------------------
# 遮罩
# ---------------------------------------------------------------------------
_SENSITIVE_ENV_HINTS = (
    "AUTHORIZATION", "TOKEN", "SECRET", "PASSWORD", "COOKIE", "PROXY", "API_KEY", "APIKEY",
    "PRIVATE_KEY", "ACCESS_KEY",
)
# 明確非敏感（授權代碼、路徑、分支名）：其值要原樣出現在報告中。
_NON_SENSITIVE_ENV_NAMES = ("AUTH_CODE", "REPORT_PATH", "RESULT_BRANCH")
_MASK_PATTERNS = (
    (re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=\-]+"), "Bearer ***"),
    (re.compile(r"(?i)\bBasic\s+[A-Za-z0-9+/=]{8,}"), "Basic ***"),
    (re.compile(r"(?i)(authorization\s*[:=]\s*)[^\s,;]+(\s+[^\s,;]+)?"), r"\1***"),
    (re.compile(r"(?i)\b(set-cookie|cookie)\s*[:=]\s*[^\r\n]+"), r"\1: ***"),
    (re.compile(r"(?i)\b(token|access_token|api[_-]?key|apikey|secret|password|passwd|key)=([^&\s\"']+)"),
     r"\1=***"),
    (re.compile(r"(?i)\b(PROXY_URL|HTTPS?_PROXY|ALL_PROXY)\s*[=:]\s*\S+"), r"\1=***"),
    (re.compile(r"(?i)\b([a-z][a-z0-9+.\-]*://)[^/\s:@]+:[^/\s@]+@"), r"\1***:***@"),
    (re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"), "***"),
)


def _sensitive_env_values(env: Optional[Dict[str, str]] = None) -> List[str]:
    src = os.environ if env is None else env
    vals: List[str] = []
    for k, v in src.items():
        ku = k.upper()
        if ku in _NON_SENSITIVE_ENV_NAMES:
            continue
        if v and len(v) >= 6 and any(h in ku for h in _SENSITIVE_ENV_HINTS):
            vals.append(v)
    return sorted(set(vals), key=len, reverse=True)


def mask(text: Any, env: Optional[Dict[str, str]] = None) -> str:
    """遮罩 token／Authorization／cookie／代理網址與敏感環境變數的值。"""
    s = "" if text is None else str(text)
    for v in _sensitive_env_values(env):
        s = s.replace(v, "***")
    for pat, repl in _MASK_PATTERNS:
        s = pat.sub(repl, s)
    return s


# ---------------------------------------------------------------------------
# 網路層（預設 opener：標準庫單次 GET、不重試、不跟隨轉址、不用環境代理）
# ---------------------------------------------------------------------------
class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


Opener = Callable[[str, Dict[str, str], float], Tuple[int, Dict[str, str], bytes]]


def default_opener(url: str, headers: Dict[str, str], timeout: float) -> Tuple[int, Dict[str, str], bytes]:
    """單次 GET；回傳 (status, headers, body)。3xx 不跟隨，原樣回傳。"""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with opener.open(req, timeout=timeout) as resp:
            body = resp.read(MAX_RESPONSE_BYTES + 1)
            if len(body) > MAX_RESPONSE_BYTES:
                raise ResponseTooLarge(f"回應超過 {MAX_RESPONSE_BYTES} bytes")
            return resp.status, {k.lower(): v for k, v in resp.getheaders()}, body
    except urllib.error.HTTPError as e:
        try:
            body = e.read(MAX_RESPONSE_BYTES + 1)[:MAX_RESPONSE_BYTES]
        except Exception:  # noqa: BLE001
            body = b""
        return e.code, {k.lower(): v for k, v in (e.headers or {}).items()}, body


def build_url(req: Dict[str, Any]) -> str:
    sym = urllib.parse.quote(req["symbol"], safe="")
    qs = "&".join(f"{k}={v}" for k, v in req["params"])
    return f"{YF_CHART_BASE}/{sym}?{qs}"


def _utc_iso(dt: _dt.datetime) -> str:
    return dt.astimezone(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


# ---------------------------------------------------------------------------
# 解析（純描述）
# ---------------------------------------------------------------------------
class SchemaError(ValueError):
    pass


def _load_json(body: bytes, content_encoding: str = "") -> Any:
    data = body
    if "gzip" in (content_encoding or "").lower():
        d = zlib.decompressobj(wbits=31)
        data = d.decompress(body, MAX_RESPONSE_BYTES + 1)
        if len(data) > MAX_RESPONSE_BYTES or d.unconsumed_tail:
            raise ResponseTooLarge(f"解壓縮後超過 {MAX_RESPONSE_BYTES} bytes")
    return json.loads(data.decode("utf-8"))


def parse_chart(obj: Any) -> Dict[str, Any]:
    """從 chart v8 JSON 抽出 meta 摘要與逐根時間戳描述；schema 異常 raise SchemaError。"""
    try:
        result = obj["chart"]["result"][0]
        meta = result["meta"]
        ts = result["timestamp"]
        close = result["indicators"]["quote"][0]["close"]
    except (KeyError, IndexError, TypeError) as e:
        raise SchemaError(f"schema 缺欄位：{type(e).__name__}: {e}") from e
    if not isinstance(ts, list) or not isinstance(close, list):
        raise SchemaError("timestamp 或 close 不是陣列")
    if len(ts) == 0:
        raise SchemaError("timestamp 為空陣列")
    if len(ts) != len(close):
        raise SchemaError(f"timestamp 長度 {len(ts)} ≠ close 長度 {len(close)}")
    prev = None
    for i, t in enumerate(ts):
        if isinstance(t, bool) or not isinstance(t, (int, float)):
            raise SchemaError(f"timestamp[{i}] 非數值")
        if prev is not None and t <= prev:
            raise SchemaError(f"timestamp 非嚴格單調遞增：index {i}")
        prev = t

    tzname = meta.get("exchangeTimezoneName")
    tz = None
    tz_error = None
    if tzname:
        try:
            from zoneinfo import ZoneInfo

            tz = ZoneInfo(tzname)
        except Exception as e:  # noqa: BLE001
            tz_error = f"{type(e).__name__}: {e}"
    gmtoffset = meta.get("gmtoffset")

    bars: List[Dict[str, Any]] = []
    null_idx: List[int] = []
    for i, (t, c) in enumerate(zip(ts, close)):
        utc = _dt.datetime.fromtimestamp(t, tz=_dt.timezone.utc)
        row: Dict[str, Any] = {
            "i": i,
            "ts": t,
            "utc_iso": _utc_iso(utc),
            "utc_date": utc.strftime("%Y-%m-%d"),
            "close": c,
        }
        if tz is not None:
            loc = utc.astimezone(tz)
            row["exchange_local_date"] = loc.strftime("%Y-%m-%d")
            row["exchange_local_weekday"] = _WEEKDAYS[loc.weekday()]
        else:
            row["exchange_local_date"] = None
            row["exchange_local_weekday"] = None
        if c is None:
            null_idx.append(i)
        bars.append(row)

    return {
        "meta": {
            "exchangeTimezoneName": tzname,
            "gmtoffset": gmtoffset,
            "timezone": meta.get("timezone"),
            "instrumentType": meta.get("instrumentType"),
            "regularMarketTime": meta.get("regularMarketTime"),
            "regularMarketTime_utc_iso": (
                _utc_iso(_dt.datetime.fromtimestamp(meta["regularMarketTime"], tz=_dt.timezone.utc))
                if isinstance(meta.get("regularMarketTime"), (int, float)) else None
            ),
            "dataGranularity": meta.get("dataGranularity"),
            "validRanges": meta.get("validRanges"),
            "symbol": meta.get("symbol"),
            "range": meta.get("range"),
        },
        "tz_error": tz_error,
        "n_bars": len(bars),
        "first_utc_iso": bars[0]["utc_iso"],
        "last_utc_iso": bars[-1]["utc_iso"],
        "close_null_indexes": null_idx,
        "bars": bars,
    }


def consistency_check(parsed: Dict[str, Any], body: bytes, content_encoding: str = "") -> Dict[str, Any]:
    """獨立重讀原始位元組，核對解析後長度與原始 JSON 對應陣列長度一致。"""
    raw = _load_json(body, content_encoding)
    res = raw["chart"]["result"][0]
    raw_ts = res["timestamp"]
    raw_close = res["indicators"]["quote"][0]["close"]
    ok = (
        len(parsed["bars"]) == len(raw_ts) == len(raw_close)
        and [b["ts"] for b in parsed["bars"]] == raw_ts
        and [b["close"] for b in parsed["bars"]] == raw_close
    )
    return {
        "raw_timestamp_len": len(raw_ts),
        "raw_close_len": len(raw_close),
        "parsed_bars_len": len(parsed["bars"]),
        "consistent": bool(ok),
    }


def window_contains_target(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """純描述：有哪些 bar 的 UTC 日期／交易所本地日期等於 2026-06-03（不做規則判定）。"""
    return {
        "target_date": TARGET_DATE,
        "bars_with_utc_date": [b["i"] for b in parsed["bars"] if b["utc_date"] == TARGET_DATE],
        "bars_with_exchange_local_date": [
            b["i"] for b in parsed["bars"] if b["exchange_local_date"] == TARGET_DATE
        ],
    }


# ---------------------------------------------------------------------------
# 單次送出
# ---------------------------------------------------------------------------
def _send_one(
    req: Dict[str, Any],
    budget: RequestBudget,
    opener: Opener,
    now: Callable[[], _dt.datetime],
    env: Optional[Dict[str, str]],
) -> Dict[str, Any]:
    """送出單一授權請求並回傳該請求的紀錄（ok 欄位表示是否可繼續）。唯一呼叫 opener 的地方。"""
    url = build_url(req)
    headers = {"User-Agent": USER_AGENT, "Accept-Language": ACCEPT_LANGUAGE}
    rec: Dict[str, Any] = {
        "request_index": req["index"],
        "requested_index": req["symbol"],
        "url": url,
        "request_headers_sent": dict(headers),
        "ok": False,
    }
    budget.before_send()  # ← 先計數、後送出；達上限直接 raise
    rec["http_requests_attempted_after_this"] = budget.http_requests_attempted
    rec["sent_at_utc"] = _utc_iso(now())
    try:
        status, resp_headers, body = opener(url, headers, TIMEOUT_S)
    except HardCapExceeded:
        raise
    except ResponseTooLarge as e:
        rec["received_at_utc"] = _utc_iso(now())
        rec["http_status"] = None
        rec["error"] = mask(str(e), env)
        rec["failure_kind"] = "response_too_large"
        return rec
    except Exception as e:  # noqa: BLE001
        rec["received_at_utc"] = _utc_iso(now())
        rec["http_status"] = None
        rec["error"] = mask(f"{type(e).__name__}: {e}", env)
        rec["failure_kind"] = "exception"
        return rec
    if len(body) > MAX_RESPONSE_BYTES:
        rec["received_at_utc"] = _utc_iso(now())
        rec["http_status"] = status
        rec["error"] = f"回應超過 {MAX_RESPONSE_BYTES} bytes"
        rec["failure_kind"] = "response_too_large"
        return rec
    rec["received_at_utc"] = _utc_iso(now())
    rec["http_status"] = status
    rec["response_headers"] = {
        k: mask(v, env) for k, v in resp_headers.items() if k.lower() in HEADER_WHITELIST
    }
    rec["body_bytes"] = len(body)
    rec["raw_sha256"] = hashlib.sha256(body).hexdigest()

    if 300 <= status < 400:
        rec["failure_kind"] = "redirect_not_followed"
        rec["error"] = f"HTTP {status}（不跟隨轉址，視為失敗）"
        return rec
    if not (200 <= status < 300):
        rec["failure_kind"] = "http_status"
        rec["error"] = mask(f"HTTP {status}: {body[:300].decode('utf-8', 'replace')}", env)
        return rec
    if len(body) == 0:
        rec["failure_kind"] = "empty_body"
        rec["error"] = "空回應"
        return rec

    ce = resp_headers.get("content-encoding", "")
    try:
        obj = _load_json(body, ce)
    except ResponseTooLarge as e:
        rec["failure_kind"] = "response_too_large"
        rec["error"] = mask(str(e), env)
        return rec
    except Exception as e:  # noqa: BLE001
        rec["failure_kind"] = "json_parse"
        rec["error"] = mask(f"JSON 解析失敗：{type(e).__name__}: {e}", env)
        return rec
    try:
        parsed = parse_chart(obj)
        check = consistency_check(parsed, body, ce)
    except SchemaError as e:
        rec["failure_kind"] = "schema"
        rec["error"] = mask(str(e), env)
        return rec
    except Exception as e:  # noqa: BLE001
        rec["failure_kind"] = "schema"
        rec["error"] = mask(f"{type(e).__name__}: {e}", env)
        return rec

    rec["raw_gzip_b64"] = base64.b64encode(gzip.compress(body, mtime=0)).decode("ascii")
    rec["parsed"] = parsed
    rec["raw_consistency"] = check
    if req["index"] == 4:
        rec["window_target_check"] = window_contains_target(parsed)
    rec["ok"] = bool(check["consistent"])
    if not rec["ok"]:
        rec["failure_kind"] = "schema"
        rec["error"] = "解析結果與原始 JSON 陣列不一致"
    return rec


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def run_probe(
    opener: Opener = default_opener,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], _dt.datetime] = lambda: _dt.datetime.now(_dt.timezone.utc),
    env: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    environ = os.environ if env is None else env
    budget = RequestBudget()
    started = now()
    report: Dict[str, Any] = {
        "probe": AUTH_CODE,
        "authorization_ref": AUTH_REF,
        "data_source": DATA_SOURCE_NOTE,
        "workflow": environ.get("GITHUB_WORKFLOW"),
        "trigger_sha": environ.get("GITHUB_SHA"),
        "executed_sha": environ.get("PROBE_EXECUTED_SHA"),
        "run_id": environ.get("GITHUB_RUN_ID"),
        "run_attempt": environ.get("GITHUB_RUN_ATTEMPT"),
        "started_at_utc": _utc_iso(started),
        "hard_limit": HARD_LIMIT,
        "min_interval_seconds": MIN_INTERVAL_S,
        "uses_proxy": False,
        "retries": 0,
        "period1": PERIOD1_ISO,
        "period2": PERIOD2_ISO,
        "requests": [],
        "stop_reason": None,
        "failed_request_index": None,
        "skipped_not_attempted": [],
        "interpretation_limits": (
            "純描述；單次探測不得判定永久日期規則；不變更 Eligibility／母集合／分母／日期轉換／"
            "FX_OBS_DATE_RULE_VERIFIED=False；不自動啟動第二批。"
        ),
    }
    stopped_at: Optional[int] = None
    try:
        for pos, req in enumerate(AUTHORIZED_REQUESTS):
            if pos > 0:
                sleep(MIN_INTERVAL_S)
            rec = _send_one(req, budget, opener, now, environ)
            report["requests"].append(rec)
            if not rec["ok"]:
                stopped_at = pos
                report["stop_reason"] = f"{rec.get('failure_kind')}: {rec.get('error')}"
                report["failed_request_index"] = req["index"]
                if rec.get("http_status") in COOLDOWN_STATUSES:
                    report["cooldown_notice"] = (
                        f"疑似限流或封鎖（HTTP {rec.get('http_status')}）：{COOLDOWN_MINUTES} 分鐘內不得重跑；"
                        "再次執行須重新取得客戶授權。"
                    )
                break
    except HardCapExceeded as e:
        stopped_at = len(report["requests"])
        report["stop_reason"] = f"hard_cap: {e}"
    except Exception as e:  # noqa: BLE001  任何未預期例外：盡力保留已發請求的證據
        stopped_at = len(report["requests"])
        report["stop_reason"] = mask(f"unhandled_exception: {type(e).__name__}: {e}", environ)
        report["failed_request_index"] = stopped_at + 1
    if stopped_at is None:
        report["stop_reason"] = "completed_all_authorized_requests"
    else:
        for req in AUTHORIZED_REQUESTS[stopped_at + 1:]:
            report["skipped_not_attempted"].append({
                "request_index": req["index"],
                "requested_index": req["symbol"],
                "reason": "not_attempted_after_stop",
                "status": "skipped_not_attempted",
            })
    report["http_requests_attempted"] = budget.http_requests_attempted
    report["finished_at_utc"] = _utc_iso(now())
    return report


def mask_obj(obj: Any, env: Optional[Dict[str, str]] = None) -> Any:
    """遞迴遮罩所有字串值；原始位元組欄位（raw_gzip_b64）與數值不動。"""
    if isinstance(obj, dict):
        return {k: (v if k == "raw_gzip_b64" else mask_obj(v, env)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [mask_obj(v, env) for v in obj]
    if isinstance(obj, str):
        return mask(obj, env)
    return obj


def write_report(report: Dict[str, Any], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(mask_obj(report), ensure_ascii=False, indent=1, sort_keys=False) + "\n"
    with open(out_path, "x", encoding="utf-8") as f:  # "x"：已存在就拒絕
        f.write(text)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Yahoo 指數日線受控唯讀探測（固定四個請求）")
    ap.add_argument("--out", default=DEFAULT_OUT, help="報告輸出路徑（已存在則拒絕）")
    ap.add_argument("--dry-run", action="store_true", help="不發任何請求，只印出將發的四個 URL")
    args = ap.parse_args(argv)

    if args.dry_run:
        for req in AUTHORIZED_REQUESTS:
            print(build_url(req))
        return 0

    out = Path(args.out)
    if out.exists():
        print(f"拒絕執行：輸出路徑已存在（{out}）；再次執行須重新授權。0 次請求。", file=sys.stderr)
        return 2

    try:
        report = run_probe()
    except BaseException as e:  # noqa: BLE001  run_probe 外層崩潰也要留報告
        report = {
            "probe": AUTH_CODE, "authorization_ref": AUTH_REF, "data_source": DATA_SOURCE_NOTE,
            "stop_reason": mask(f"unhandled_exception: {type(e).__name__}: {e}"),
            "http_requests_attempted": None,
            "note": "run_probe 外層例外，已發請求數未知（見 claim 與 Actions log）",
            "skipped_not_attempted": [],
        }
    write_report(report, out)
    print(
        f"stop_reason={mask(report['stop_reason'])} "
        f"http_requests_attempted={report['http_requests_attempted']} out={out}"
    )
    return 0 if report["stop_reason"] == "completed_all_authorized_requests" else 1


if __name__ == "__main__":
    sys.exit(main())
