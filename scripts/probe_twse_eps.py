#!/usr/bin/env python3
"""scripts/probe_twse_eps.py — BL-0509 EPS Data Source Probe（只讀探測，不接任何正式 signal）。

## 範圍
對 TWSE OpenAPI／公開網站／MOPS 的**公開端點**（一律 HTTPS GET）分別量兩條路徑：
  * `direct`    ：不設任何 proxy 的直連（GitHub runner IP；`trust_env=False`，不吃環境 proxy）；
  * `nas_proxy` ：`PROXY_URL` 環境變數 → requests Session 的 proxies（比照 `scripts/fetch_nav_cache.py`）。
                  未設 `PROXY_URL` → 該路徑記 `proxy_not_configured`，**不發請求、不補值**。
每個端點每條路徑記：HTTP status、content-type、latency、response bytes、top-level schema
（欄位名＋型別；只存前 N 筆 sample 與全量筆數）、來源自帶的日期欄位（source timestamp）、
missing／stale 判定（來源日期對比執行日；**不補 0、不猜值**）。

## 為什麼不用 `infra.proxy.fetch_url`
`infra.proxy.get_proxy_config()` 只讀 `st.secrets`，Actions 上讀不到 `PROXY_URL` 環境變數，
repo 內也沒有把環境變數橋接進 `infra.proxy` 的先例（`moneydj_basic_probe` 因此是 runner 直連）。
要「分辨實際走哪條路」就不能依賴 `fetch_url` 的自動降級（它會在 NAS 失敗時悄悄改直連）。
本腳本因此自建 Session，兩條路徑各自明確發一次；**不改 `infra/proxy.py`、不新增 API／proxy 架構**。
代價（據實揭露）：不經 `infra.source_backoff` 的冷卻狀態機；以「每請求最多 1 次重試、請求間隔 sleep」自律。

## 多日時序（2026-10-27 客戶裁示 A：BL-0509 再跑 3～5 個交易日的唯讀 probe）
每個資料端點另記 `timeseries`：回應列數、`schema_hash`（欄位名清單 hash）、前後各 N 筆的來源日期 min/max、
rwd 頂層 `date` 原字串、`latest_source_date`、各欄空字串／`-` 計數（**只計數，不補值**）；
報告頂層 `openapi_vs_rwd` 為同類資料 openapi 與 rwd 的 `latest_source_date` 差距（天；任一側缺值則為 null 並註明原因）。
跨 run 的分析見 `scripts/analyze_twse_probe_series.py`。

## 條款研究（`terms_reach` 群組；最小唯讀）
資料端點一律 `allow_redirects=False`。只有 `terms_reach` 群組（以及 swagger `info.description` 內出現的條款連結）
允許最多 `MAX_REDIRECT_HOPS`＝3 跳 redirect，**每一跳目標的 scheme／主機都必須通過同一份白名單**，
不通過即停並記 `blocked_redirect`。每跳只記（遮蔽後）host、status、path、content-type、body 長度與 sha256；
頁面文字只計「使用條款／授權／著作權／商業」四個關鍵詞的**出現次數**，**不存整頁文字**，**不下可否商用的結論**。
取不到正式條款內容 → 恆標「⬜ 授權條款尚未完成驗證」；關鍵詞存在只代表「頁面存在、含關鍵詞」，不等於已讀懂或已授權。

## 安全
* 絕不輸出或記錄 `PROXY_URL`、帳密、NAS host／port。報告只記 `proxy.enabled` 與各路徑結果。
  所有字串（含例外原文）寫入前先遮蔽；整份報告落盤前再整體掃一次。
* 只發 GET；URL 必須是 https 且主機在白名單（TWSE／MOPS 官方網域）。
* 唯一輸出是 `--out` 指定的 gzip JSON；不寫試算表、不碰使用者設定。

## 研究試算（`research_metric`，只記輸入是否齊備）
**不自創「市場 PE」**，也**不輸出** implied_trailing_index_earnings 數值：只記「來源是否提供市場整體 trailing PE 欄位」
與計算所需輸入是否齊備；universe／分母口徑一律標「待驗」。
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urljoin, urlsplit

SCHEMA_VERSION = 2   # v2：新增 timeseries／openapi_vs_rwd／terms_research
ALLOWED_HOSTS = frozenset({
    "openapi.twse.com.tw",
    "www.twse.com.tw",
    "mopsov.twse.com.tw",
    "mops.twse.com.tw",
})
TIMEOUT_SEC = 20
MAX_BYTES = 20 * 1024 * 1024
SAMPLE_ROWS = 3
SAMPLE_STR_LEN = 80
MAX_REDIRECT_HOPS = 3          # 僅 terms_reach 群組與 swagger 條款連結；資料端點恆不跟隨
FOLLOW_GROUPS = frozenset({"terms_reach"})
TERMS_KEYWORDS = ("使用條款", "授權", "著作權", "商業")
MAX_TERMS_LINKS = 2            # swagger 內條款連結最多追幾條（控制請求量）
HEAD_TAIL_N = 5
STALE_AFTER_DAYS = 7          # 探測用啟發式門檻（日曆日），非正式 freshness 規格
TRANSPORTS = ("direct", "nas_proxy")
TAIEX_NAME = "發行量加權股價指數"

_O = "https://openapi.twse.com.tw/v1"
_W = "https://www.twse.com.tw/rwd/zh/afterTrading"
# (id, group, url, kind)   kind: json | swagger | reach
ENDPOINTS = (
    ("openapi_MI_INDEX", "taiex", f"{_O}/exchangeReport/MI_INDEX", "json"),
    ("rwd_MI_INDEX_IND", "taiex", f"{_W}/MI_INDEX?type=IND&response=json", "json"),
    ("openapi_MI_5MINS_HIST", "taiex_history", f"{_O}/indicesReport/MI_5MINS_HIST", "json"),
    ("openapi_FMTQIK", "market_stats", f"{_O}/exchangeReport/FMTQIK", "json"),
    ("rwd_FMTQIK", "market_stats", f"{_W}/FMTQIK?response=json", "json"),
    ("openapi_BWIBBU_ALL", "pe", f"{_O}/exchangeReport/BWIBBU_ALL", "json"),
    ("rwd_BWIBBU_d", "pe", f"{_W}/BWIBBU_d?selectType=ALL&response=json", "json"),
    ("openapi_t187ap06_L", "financials", f"{_O}/opendata/t187ap06_L", "json"),
    ("openapi_t187ap14_L", "financials", f"{_O}/opendata/t187ap14_L", "json"),
    ("openapi_t187ap05_L", "financials", f"{_O}/opendata/t187ap05_L", "json"),
    ("openapi_t187ap06_L_ci", "financials", f"{_O}/opendata/t187ap06_L_ci", "json"),   # 候選：404 屬預期
    ("openapi_swagger", "swagger", f"{_O}/swagger.json", "swagger"),
    # 僅 HTTP 可達性（不解析內容）。條款頁網址為候選、未驗證；404 也是如實記錄。
    ("mopsov_index", "mops_reach", "https://mopsov.twse.com.tw/mops/web/index", "reach"),
    ("mops_index", "mops_reach", "https://mops.twse.com.tw/mops/web/index", "reach"),
    ("openapi_swagger_ui", "terms_reach", "https://openapi.twse.com.tw/", "reach"),
    ("twse_terms_candidate", "terms_reach", "https://www.twse.com.tw/zh/page/terms.html", "reach"),
)
SWAGGER_PATH_KEYWORDS = (
    "MI_INDEX", "FMTQIK", "BWIBBU", "t187ap06", "t187ap14", "t187ap05", "MI_5MINS_HIST",
)
SWAGGER_TEXT_KEYWORDS = ("本益比", "每股盈餘", "綜合損益", "加權股價指數")
# 端點路徑皆未經真實回應驗證；報告對下列端點與整個 financials 群組標 candidate=true（404 屬預期）。
CANDIDATE_IDS = frozenset({"openapi_t187ap06_L_ci", "twse_terms_candidate", "openapi_MI_5MINS_HIST"})
MARKET_LEVEL_IDS = frozenset({
    "openapi_MI_INDEX", "rwd_MI_INDEX_IND", "openapi_MI_5MINS_HIST", "openapi_FMTQIK", "rwd_FMTQIK",
})
_RE_USERINFO = re.compile(r"(?P<scheme>[A-Za-z][A-Za-z0-9+.-]*://)[^\s/@'\"]+@")
def _norm_field(name) -> str:
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]", "", str(name).lower())


def classify_field(name) -> str | None:
    """欄名正規化（小寫、去非字母數字）後分類：pe／pb／yield／None。"""
    n = _norm_field(name)
    if "本益比" in n or re.fullmatch(r"(trailing|forward)?pe(ratio)?", n):
        return "pe"
    if "股價淨值比" in n or re.fullmatch(r"pb(ratio)?", n):
        return "pb"
    if "殖利率" in n or n == "dividendyield":
        return "yield"
    return None


# ───────────────────────── 安全：遮蔽／白名單 ─────────────────────────

def secret_literals(strong_only: bool = False) -> tuple:
    """`PROXY_URL` 整串、帳密、host、port、netloc（任何可辨識 NAS 的片段）。

    `strong_only=True`：只回傳高熵長字串（整串、密碼、user:pass、host、host:port；短帳號與 port 不含），
    供「整份報告全域掃描」用 —— 低熵片段（如 port 3128）做全域子字串替換會改寫 sample 數值（如 23128.45）。
    """
    raw = os.environ.get("PROXY_URL", "").strip()
    if not raw:
        return ()
    out = [raw]
    minlen = 8 if strong_only else 3
    try:
        p = urlsplit(raw)
        for piece in (p.password, p.username, p.hostname, p.netloc,
                      f"{p.username}:{p.password}" if p.username and p.password else None):
            if piece and len(piece) >= minlen:
                out.append(piece)
        try:
            port = p.port
        except ValueError:
            port = None
        if port and len(str(port)) >= 4 and not strong_only:
            out.append(str(port))
        # netloc 去掉 userinfo 後的 host:port
        tail = p.netloc.split("@")[-1]
        if len(tail) >= minlen:
            out.append(tail)
    except ValueError:
        pass
    return tuple(dict.fromkeys(out))


def mask_text(text, secrets: tuple = ()) -> str:
    out = str(text)
    for s in sorted((s for s in secrets if s), key=len, reverse=True):
        out = out.replace(s, "***")
    return _RE_USERINFO.sub(lambda m: m.group("scheme") + "***@", out)


def is_allowed_url(url: str) -> bool:
    try:
        p = urlsplit(url)
    except ValueError:
        return False
    try:
        port_ok = p.port in (None, 443)
    except ValueError:
        return False
    return (p.scheme == "https" and (p.hostname or "").lower() in ALLOWED_HOSTS and not p.username
            and port_ok)


# ───────────────────────── 日期解析／stale 判定 ─────────────────────────

def parse_source_date(raw):
    """民國或西元日期字串 → date；無法解析回 None（不猜）。"""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    m = re.fullmatch(r"(\d{4})[-/.]?(\d{2})[-/.]?(\d{2})", s)           # 20261026 / 2026/10/26
    if m:
        y, mo, d = map(int, m.groups())
    else:
        m = re.fullmatch(r"(\d{2,3})[-/.]?(\d{2})[-/.]?(\d{2})", s)      # 1151026 / 115/10/26
        if m:
            y, mo, d = int(m.group(1)) + 1911, int(m.group(2)), int(m.group(3))
        else:
            m = re.fullmatch(r"(\d{2,3})年(\d{1,2})月(\d{1,2})日", s)
            if not m:
                return None
            y, mo, d = int(m.group(1)) + 1911, int(m.group(2)), int(m.group(3))
    try:
        return date(y, mo, d)
    except ValueError:
        return None


def is_date_field(name: str) -> bool:
    n = str(name)
    return ("日期" in n) or ("date" in n.lower())


def judge_freshness(source_dates, run_date: date, group: str = "") -> dict:
    """來源日期對比執行日（`heuristic` 恆 true，非正式 freshness 規格）。

    沒有來源日期 → `no_source_date`（不補值）。財報群組的「出表日期」是發布日而非財報期間，
    不下 fresh／stale 結論（`publication_date_not_period`）。
    """
    if not source_dates:
        return {"state": "no_source_date", "latest_source_date": None, "age_days": None, "heuristic": True}
    latest = max(source_dates)
    age = (run_date - latest).days
    if group == "financials":
        return {"state": "publication_date_not_period", "latest_source_date": latest.isoformat(),
                "age_days": age, "heuristic": True,
                "note": "出表日期為發布日，非財報期間；不判 fresh／stale"}
    return {
        "heuristic": True,
        "state": "stale" if age > STALE_AFTER_DAYS else "fresh",
        "latest_source_date": latest.isoformat(),
        "age_days": age,
        "stale_after_days": STALE_AFTER_DAYS,
    }


# ───────────────────────── schema 分析 ─────────────────────────

def _tname(v) -> str:
    if v is None:
        return "null"
    return type(v).__name__


def _trunc(v):
    if isinstance(v, str) and len(v) > SAMPLE_STR_LEN:
        return v[:SAMPLE_STR_LEN] + "…"
    if isinstance(v, (dict, list)):
        return _tname(v)
    return v


def _rows_schema(rows: list, field_names=None) -> tuple:
    """回傳 (schema, source_date_candidates(list[date]), source_fields(list[str]))。"""
    n = len(rows)
    schema = {"n_rows": n}
    dates, dfields = [], []
    if n == 0:
        schema["fields"] = []
        schema["sample"] = []
        return schema, dates, dfields
    first = rows[0]
    if isinstance(first, dict):
        names = list(first.keys())
        schema["fields"] = [{"name": k, "type": _tname(v)} for k, v in first.items()]
        schema["sample"] = [{k: _trunc(v) for k, v in r.items()} for r in rows[:SAMPLE_ROWS] if isinstance(r, dict)]
        dfields = [k for k in names if is_date_field(k)]
        for r in rows:
            if isinstance(r, dict):
                for k in dfields:
                    d = parse_source_date(r.get(k))
                    if d:
                        dates.append(d)
    elif isinstance(first, list):
        names = list(field_names or [])
        schema["fields"] = [
            {"name": (names[i] if i < len(names) else f"col{i}"), "type": _tname(v)} for i, v in enumerate(first)
        ]
        schema["sample"] = [[_trunc(v) for v in r] for r in rows[:SAMPLE_ROWS] if isinstance(r, list)]
        idx = [i for i, nm in enumerate(names) if is_date_field(nm)]
        dfields = [names[i] for i in idx]
        for r in rows:
            if isinstance(r, list):
                for i in idx:
                    if i < len(r):
                        d = parse_source_date(r[i])
                        if d:
                            dates.append(d)
    else:
        schema["fields"] = [{"name": "(scalar rows)", "type": _tname(first)}]
        schema["sample"] = [_trunc(v) for v in rows[:SAMPLE_ROWS]]
    return schema, dates, dfields


# ───────────────────────── 時序欄位（多日 probe 用） ─────────────────────────

def _iter_tables(obj):
    """回傳 [(label, field_names(list[str]), rows(list))]；label：`(list)`／`data`／`tables[i]`。"""
    out = []
    if isinstance(obj, list):
        names = list(obj[0].keys()) if obj and isinstance(obj[0], dict) else []
        out.append(("(list)", names, obj))
    elif isinstance(obj, dict):
        if isinstance(obj.get("data"), list):
            rows = obj["data"]
            if rows and isinstance(rows[0], dict):
                names = list(rows[0].keys())
            else:
                names = [str(x) for x in (obj.get("fields") or [])]
            out.append(("data", names, rows))
        if isinstance(obj.get("tables"), list):
            for i, t in enumerate(obj["tables"]):
                if not isinstance(t, dict):
                    continue
                rows = t.get("data") if isinstance(t.get("data"), list) else []
                if rows and isinstance(rows[0], dict):
                    names = list(rows[0].keys())
                else:
                    names = [str(x) for x in (t.get("fields") or [])]
                out.append((f"tables[{i}]", names, rows))
    return out


def _row_date(r, names):
    """單列的來源日期（該列所有日期欄解析後取最大）；無則 None。不猜。"""
    ds = []
    if isinstance(r, dict):
        ds = [parse_source_date(v) for k, v in r.items() if is_date_field(k)]
    elif isinstance(r, list):
        ds = [parse_source_date(r[i]) for i, nm in enumerate(names) if is_date_field(nm) and i < len(r)]
    ds = [d for d in ds if d]
    return max(ds) if ds else None


def _cells(r, names):
    if isinstance(r, dict):
        yield from r.items()
    elif isinstance(r, list):
        for i, v in enumerate(r):
            yield (names[i] if i < len(names) else f"col{i}"), v


def _iso(d):
    return d.isoformat() if d else None


def build_timeseries(obj, all_dates) -> dict:
    """多日比對用欄位。只計數、不補值：空字串／`-` 只記次數。"""
    tables = _iter_tables(obj)
    top_raw = obj.get("date") if isinstance(obj, dict) else None
    schema_basis = {
        "top_keys": list(obj.keys()) if isinstance(obj, dict) else None,
        "tables": {label: names for label, names, _r in tables},
    }
    schema_hash = hashlib.sha256(json.dumps(schema_basis, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    row_dates_all, head, tail = [], [], []
    rows_by_table, n_cells, empty, dash, null = {}, 0, 0, 0, 0
    empty_by_field: dict = {}
    for label, names, rows in tables:
        rows_by_table[label] = len(rows)
        rds = [_row_date(r, names) for r in rows]
        row_dates_all += [d for d in rds if d]
        head += [d for d in rds[:HEAD_TAIL_N] if d]
        tail += [d for d in rds[-HEAD_TAIL_N:] if d]
        for r in rows:
            for k, v in _cells(r, names):
                n_cells += 1
                kind = None
                if v is None:
                    null += 1
                    kind = "null"
                elif isinstance(v, str) and v.strip() == "":
                    empty += 1
                    kind = "empty"
                elif isinstance(v, str) and v.strip() in ("-", "--"):
                    dash += 1
                    kind = "dash"
                if kind:
                    key = str(k) if label in ("(list)", "data") else f"{label}:{k}"
                    empty_by_field.setdefault(key, {"empty": 0, "dash": 0, "null": 0})[kind] += 1
    first = next((d for d in row_dates_all[:1]), None)
    last = row_dates_all[-1] if row_dates_all else None
    if first is None or last is None or len(row_dates_all) < 2:
        order = "unknown"
    elif first < last:
        order = "ascending"
    elif first > last:
        order = "descending"
    else:
        order = "same_or_mixed"
    return {
        "row_count": sum(rows_by_table.values()),
        "rows_by_table": rows_by_table,
        "schema_hash": schema_hash,
        "top_level_date_raw": (str(top_raw) if top_raw is not None else None),
        "top_level_date": _iso(parse_source_date(top_raw)),
        "row_date_min": _iso(min(row_dates_all)) if row_dates_all else None,
        "row_date_max": _iso(max(row_dates_all)) if row_dates_all else None,
        "head_date_min": _iso(min(head)) if head else None,
        "head_date_max": _iso(max(head)) if head else None,
        "tail_date_min": _iso(min(tail)) if tail else None,
        "tail_date_max": _iso(max(tail)) if tail else None,
        "head_tail_n": HEAD_TAIL_N,
        "row_order": order,
        "latest_row_date": _iso(max(row_dates_all)) if row_dates_all else None,
        "latest_source_date": _iso(max(all_dates)) if all_dates else None,
        "n_cells": n_cells,
        "empty_string_cells": empty,
        "dash_cells": dash,
        "null_cells": null,
        "missing_by_field": empty_by_field,
        "note": "只計數，不補 0、不補值；latest_source_date＝列內日期與頂層 date 的最大值（與 freshness 同口徑）",
    }


def analyze_json(obj) -> dict:
    """top-level schema、來源日期、PE 類欄位名。"""
    dates, dfields, field_names = [], [], []
    if isinstance(obj, list):
        schema, dates, dfields = _rows_schema(obj)
        schema["top_level"] = "list"
        field_names = [f["name"] for f in schema.get("fields", [])]
    elif isinstance(obj, dict):
        schema = {"top_level": "dict",
                  "keys": [{"name": k, "type": _tname(v)} for k, v in obj.items()]}
        top_date = parse_source_date(obj.get("date"))
        if top_date:
            dates.append(top_date)
            dfields.append("(top-level) date")
        if isinstance(obj.get("data"), list):
            sub, d2, f2 = _rows_schema(obj["data"], obj.get("fields"))
            schema["data"] = sub
            dates += d2
            dfields += f2
            field_names += [f["name"] for f in sub.get("fields", [])]
        tables = obj.get("tables")
        if isinstance(tables, list):
            tinfo = []
            for t in tables:
                if not isinstance(t, dict):
                    continue
                rows = t.get("data") if isinstance(t.get("data"), list) else []
                sub, d2, f2 = _rows_schema(rows, t.get("fields"))
                tinfo.append({"title": _trunc(t.get("title")), "schema": sub})
                dates += d2
                dfields += f2
                field_names += [f["name"] for f in sub.get("fields", [])]
            schema["tables"] = tinfo
        if "stat" in obj:
            schema["stat"] = _trunc(obj.get("stat"))
    else:
        schema = {"top_level": _tname(obj)}
    text = json.dumps(obj, ensure_ascii=False)
    cls = {n: classify_field(n) for n in field_names}
    return {
        "schema": schema,
        "source_dates": dates,
        "source_date_fields": sorted(set(dfields)),
        "pe_like_field_names": sorted({n for n, c in cls.items() if c == "pe"}),
        "pb_like_field_names": sorted({n for n, c in cls.items() if c == "pb"}),
        "yield_like_field_names": sorted({n for n, c in cls.items() if c == "yield"}),
        "contains_taiex_row": TAIEX_NAME in text,
        "timeseries": build_timeseries(obj, dates),
    }


def summarize_swagger(obj) -> dict:
    if not isinstance(obj, dict):
        return {"outcome": "not_a_dict"}
    paths = obj.get("paths") if isinstance(obj.get("paths"), dict) else {}
    hits = []
    for p, spec in paths.items():
        spec = spec if isinstance(spec, dict) else {}
        blob = json.dumps(spec, ensure_ascii=False)
        if any(k.lower() in p.lower() for k in SWAGGER_PATH_KEYWORDS) or any(k in blob for k in SWAGGER_TEXT_KEYWORDS):
            methods = {}
            for m, ms in spec.items():
                if isinstance(ms, dict):
                    methods[m] = {"summary": _trunc(ms.get("summary")),
                                  "description": (str(ms.get("description"))[:200] if ms.get("description") else None)}
            hits.append({"path": p, "methods": methods})
    info = obj.get("info") if isinstance(obj.get("info"), dict) else {}
    return {
        "outcome": "ok",
        "info": {k: _trunc(info.get(k)) for k in ("title", "version", "description") if k in info},
        "n_paths_total": len(paths),
        "relevant_paths": hits,
        "note": "更新頻率／授權欄位是否存在以 relevant_paths 與 info 原文為準；本探測不做內容結論",
    }


# ───────────────────────── HTTP ─────────────────────────

def make_http_get(secrets: tuple):
    """回傳 http_get(url, transport) → dict(status, content_type, latency_ms, bytes, body, error)。"""
    import requests  # 延遲 import：測試以假 fetcher 取代，不需要 requests

    proxy_url = os.environ.get("PROXY_URL", "").strip()
    sessions = {}

    def _session(transport):
        s = sessions.get(transport)
        if s is None:
            s = requests.Session()
            s.trust_env = False
            s.headers.update({"User-Agent": "Mozilla/5.0 (compatible; fund-dashboard-probe/1.0)",
                              "Accept": "application/json,text/html;q=0.8,*/*;q=0.5"})
            if transport == "nas_proxy":
                s.proxies.update({"http": proxy_url, "https": proxy_url})
                s.verify = False   # Squid CONNECT 相容，比照 fetch_nav_cache.py
                try:
                    import urllib3
                    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                except Exception:
                    pass
            sessions[transport] = s
        return s

    def http_get(url, transport):
        out = {"status": None, "content_type": None, "latency_ms": None, "bytes": None, "body": None, "error": None}
        last_err = None
        for attempt in (0, 1):
            t0 = time.monotonic()
            try:
                r = _session(transport).get(url, timeout=TIMEOUT_SEC, stream=True, allow_redirects=False)
                if 300 <= r.status_code < 400:
                    # 不跟隨轉址、不讀 body；只記 Location 供判讀（遮蔽後）
                    loc = r.headers.get("Location")
                    r.close()
                    out.update(status=r.status_code, content_type=r.headers.get("Content-Type"),
                               latency_ms=round((time.monotonic() - t0) * 1000, 1), bytes=0, body=None,
                               location=mask_text(loc, secrets) if loc else None)
                    return out
                chunks, total = [], 0
                for ch in r.iter_content(65536):
                    total += len(ch)
                    if total > MAX_BYTES:
                        out["error"] = f"response exceeds {MAX_BYTES} bytes; truncated"
                        break
                    chunks.append(ch)
                r.close()
                out.update(status=r.status_code, content_type=r.headers.get("Content-Type"),
                           latency_ms=round((time.monotonic() - t0) * 1000, 1),
                           bytes=total, body=b"".join(chunks))
                if r.status_code >= 500 and attempt == 0:
                    time.sleep(2)
                    continue
                return out
            except Exception as e:  # noqa: BLE001 — 例外原文照錄（遮蔽後），Fail Loud
                last_err = mask_text(f"{type(e).__name__}: {e}", secrets)
                # 前一次的 5xx 狀態不得殘留到「重試丟例外」的結果
                out.update(status=None, content_type=None, bytes=None, body=None)
                out["latency_ms"] = round((time.monotonic() - t0) * 1000, 1)
                if attempt == 0:
                    time.sleep(2)
        out["error"] = last_err
        return out

    return http_get


# ───────────────────────── 條款研究：有限度跟隨 redirect ─────────────────────────

def count_terms_keywords(body: bytes) -> dict:
    """關鍵詞出現次數；**不回傳、不保存頁面文字**。"""
    text = body.decode("utf-8", errors="replace")
    counts = {k: text.count(k) for k in TERMS_KEYWORDS}
    return {"counts": counts, "any_present": any(counts.values()),
            "page_text_stored": False}


def _hop_entry(hop, url, r, secrets):
    sp = urlsplit(url)
    body = r.get("body")
    e = {
        "hop": hop,
        "host": mask_text((sp.hostname or "").lower(), secrets),
        "path": mask_text(sp.path or "/", secrets),
        "status": r.get("status"),
        "content_type": mask_text(r.get("content_type") or "", secrets) or None,
        "body_bytes": r.get("bytes"),
        "latency_ms": r.get("latency_ms"),
    }
    if body is not None:
        e["body_sha256"] = hashlib.sha256(body).hexdigest()
    if r.get("error"):
        e["error"] = mask_text(r["error"], secrets)
    return e


def follow_redirects(http_get, url, transport, secrets, hop_sleep=0.0):
    """最多 MAX_REDIRECT_HOPS 跳；每一跳目標都必須通過 `is_allowed_url`，否則停（blocked_redirect）。
    回傳 (chain, stop_reason, final_response)；stop_reason：final／blocked_redirect／redirect_limit_exceeded／
    redirect_loop／redirect_without_location。http_get 本身恆不自動跟隨（一次只發一跳）。"""
    chain, seen, cur = [], {url}, url
    for hop in range(MAX_REDIRECT_HOPS + 1):
        if hop > 0 and hop_sleep:
            time.sleep(hop_sleep)          # hop 之間同樣遵守請求間隔
        r = http_get(cur, transport)
        entry = _hop_entry(hop, cur, r, secrets)
        chain.append(entry)
        st = r.get("status")
        if st is None or not (300 <= st < 400):
            return chain, "final", r
        loc = r.get("location")
        if not loc:
            return chain, "redirect_without_location", r
        nxt = urljoin(cur, loc)
        nsp = urlsplit(nxt)
        entry["next_host"] = mask_text((nsp.hostname or "").lower(), secrets) or None
        entry["next_scheme"] = nsp.scheme or None
        if not is_allowed_url(nxt):
            entry["next_blocked"] = ("not_https" if nsp.scheme != "https" else "host_not_in_allowlist")
            return chain, "blocked_redirect", r
        if nxt in seen:
            return chain, "redirect_loop", r
        if hop >= MAX_REDIRECT_HOPS:
            return chain, "redirect_limit_exceeded", r
        seen.add(nxt)
        cur = nxt
    return chain, "redirect_limit_exceeded", None   # 理論上不會到這裡


def _probe_follow(http_get, ep, transport, secrets, hop_sleep=0.0) -> dict:
    """`terms_reach` 專用：有限度跟隨，只記每跳摘要與關鍵詞「存在與否／次數」。不下可否商用結論。"""
    _id, _group, url, _kind = ep
    res = {"transport": transport}
    chain, stop, last = follow_redirects(http_get, url, transport, secrets, hop_sleep)
    last = last or {}
    res.update(
        http_status=last.get("status"),
        content_type=mask_text(last.get("content_type") or "", secrets) or None,
        latency_ms=last.get("latency_ms"),
        response_bytes=last.get("bytes"),
        error=mask_text(last["error"], secrets) if last.get("error") else None,
        redirect_chain=chain,
        n_hops=len(chain) - 1,
        redirect_stop_reason=stop,
        final_host=chain[-1]["host"] if chain else None,
        final_path=chain[-1]["path"] if chain else None,
    )
    body = last.get("body")
    if body is not None:
        res["body_sha256"] = hashlib.sha256(body).hexdigest()
    st = last.get("status")
    if stop != "final":
        res["outcome"] = stop
    elif st is None:
        res["outcome"] = "unreachable"
    elif not (200 <= st < 300):
        res["outcome"] = "http_error"
    elif not body:
        res["outcome"] = "empty_response"
    else:
        res["outcome"] = "reachable"
        res["terms_page"] = count_terms_keywords(body)
        res["terms_page"]["status"] = ("page_exists_with_keywords" if res["terms_page"]["any_present"]
                                       else "page_exists_no_keywords")
    return res


_RE_URL = re.compile(r"https?://[^\s)\]\"'<>]+")


def _swagger_raw_urls(swagger_obj) -> list:
    """swagger info 內的原始 URL（未遮蔽；**只供發請求用，不得寫進報告**）。"""
    info = swagger_obj.get("info") if isinstance(swagger_obj, dict) and isinstance(swagger_obj.get("info"), dict) else {}
    desc = str(info.get("description") or "")
    urls = []
    for u in _RE_URL.findall(desc):
        u = u.rstrip(".,;")
        if u not in urls:
            urls.append(u)
    tos = info.get("termsOfService")
    if isinstance(tos, str) and tos.strip() and tos.strip() not in urls:
        urls.append(tos.strip())
    return urls


def extract_swagger_terms_links(swagger_obj, secrets: tuple = ()) -> dict:
    """swagger `info.description`／`info.termsOfService` 內的 URL（完整、不截斷）與其 host。
    回傳內的 url 是遮蔽後的記錄用值；請求用原值見 `_swagger_raw_urls`（與 links 同順序）。"""
    info = swagger_obj.get("info") if isinstance(swagger_obj, dict) and isinstance(swagger_obj.get("info"), dict) else {}
    desc = str(info.get("description") or "")
    tos = info.get("termsOfService")
    urls = _swagger_raw_urls(swagger_obj)
    links = []
    for u in urls:
        try:
            host = (urlsplit(u).hostname or "").lower()
        except ValueError:
            host = ""
        links.append({"url": mask_text(u, secrets), "host": mask_text(host, secrets) or None,
                      "allowed": is_allowed_url(u)})
    return {
        "description_len": len(desc),
        "description_sha256": hashlib.sha256(desc.encode("utf-8")).hexdigest() if desc else None,
        "terms_of_service_field_present": isinstance(tos, str) and bool(tos.strip()),
        "links": links,
    }


def build_terms_research(http_get, swagger_obj, static_urls, secrets, proxy_enabled, run_date,
                         sleep_sec=0.0) -> dict:
    """swagger 內條款連結 → 白名單內者（最多 MAX_TERMS_LINKS 條，且不與既有 terms_reach 端點重複）才發請求。"""
    base = {
        "license_verification": "⬜ 授權條款尚未完成驗證",
        "note": ("本欄只記『條款頁是否存在、是否含關鍵詞』；不構成授權或可否商用的結論。"
                 "正式條款內容須由人閱讀後判定。頁面文字不存。"),
        "swagger_description": None,
        "followed": [],
    }
    if swagger_obj is None:
        base["swagger_description"] = {"outcome": "swagger_missing"}
        return base
    info = extract_swagger_terms_links(swagger_obj, secrets)
    base["swagger_description"] = info
    raws = _swagger_raw_urls(swagger_obj)
    todo = [(raw, l["url"]) for raw, l in zip(raws, info["links"])
            if l["allowed"] and raw not in static_urls][:MAX_TERMS_LINKS]
    for i, (url, masked) in enumerate(todo):
        ep = (f"swagger_terms_link_{i + 1}", "terms_reach", url, "reach")   # 請求用原值
        entry = {"id": ep[0], "url": masked, "transports": {}}               # 記錄用遮蔽值
        for tr in TRANSPORTS:
            if tr == "nas_proxy" and not proxy_enabled:
                entry["transports"][tr] = {"transport": tr, "outcome": "proxy_not_configured", "http_status": None}
                continue
            if sleep_sec:
                time.sleep(sleep_sec)
            entry["transports"][tr] = _probe_follow(http_get, ep, tr, secrets, sleep_sec)
        base["followed"].append(entry)
    return base


OPENAPI_RWD_PAIRS = (
    ("MI_INDEX", "openapi_MI_INDEX", "rwd_MI_INDEX_IND"),
    ("FMTQIK", "openapi_FMTQIK", "rwd_FMTQIK"),
    ("BWIBBU", "openapi_BWIBBU_ALL", "rwd_BWIBBU_d"),
)


def build_openapi_vs_rwd(ep_results: dict) -> list:
    """同類資料 openapi vs rwd 的 latest_source_date 差距（天；rwd − openapi，正＝rwd 較新）。
    任一側沒有日期 → diff 為 None 並註明原因；不補值。"""
    out = []
    for name, oid, wid in OPENAPI_RWD_PAIRS:
        for tr in TRANSPORTS:
            ro = ep_results.get(oid, {}).get(tr) or {}
            rw = ep_results.get(wid, {}).get(tr) or {}
            to, tw = ro.get("timeseries") or {}, rw.get("timeseries") or {}
            row = {"pair": name, "transport": tr, "openapi_id": oid, "rwd_id": wid,
                   "openapi_latest_source_date": to.get("latest_source_date"),
                   "rwd_latest_source_date": tw.get("latest_source_date"),
                   "rwd_top_level_date": tw.get("top_level_date"),
                   "openapi_latest_row_date": to.get("latest_row_date"),
                   "rwd_latest_row_date": tw.get("latest_row_date")}
            lo, lw = parse_source_date(row["openapi_latest_source_date"]), parse_source_date(row["rwd_latest_source_date"])
            if lo and lw:
                row["diff_days"] = (lw - lo).days
            else:
                row["diff_days"] = None
                row["reason"] = (f"openapi:{ro.get('outcome')} rwd:{rw.get('outcome')}"
                                 if not (lo and lw) else None)
            ro_d, rw_d = parse_source_date(row["openapi_latest_row_date"]), parse_source_date(row["rwd_latest_row_date"])
            row["row_date_diff_days"] = (rw_d - ro_d).days if (ro_d and rw_d) else None
            out.append(row)
    return out


# ───────────────────────── 單端點／單路徑 ─────────────────────────

def probe_one(http_get, ep, transport, run_date, secrets, proxy_enabled, hop_sleep=0.0) -> tuple:
    """回傳 (report_dict, analysis_or_None, swagger_obj_or_None)。"""
    ep_id, group, url, kind = ep
    res = {"transport": transport}
    if transport == "nas_proxy" and not proxy_enabled:
        res.update(outcome="proxy_not_configured", http_status=None)
        return res, None, None
    if not is_allowed_url(url):
        res.update(outcome="blocked_by_allowlist", http_status=None)
        return res, None, None
    if group in FOLLOW_GROUPS and kind == "reach":
        return _probe_follow(http_get, ep, transport, secrets, hop_sleep), None, None
    r = http_get(url, transport)
    body = r.get("body")
    res.update(
        http_status=r.get("status"),
        content_type=mask_text(r.get("content_type") or "", secrets) or None,
        latency_ms=r.get("latency_ms"),
        response_bytes=r.get("bytes"),
        error=mask_text(r["error"], secrets) if r.get("error") else None,
    )
    if body is not None:
        res["body_sha256"] = hashlib.sha256(body).hexdigest()
    status = r.get("status")
    if status is not None and 300 <= status < 400:
        loc = r.get("location")
        host = (urlsplit(loc).hostname or "").lower() if loc else ""
        res["redirect_location_host"] = mask_text(host, secrets) or None
        res["outcome"] = "blocked_redirect" if (host and host not in ALLOWED_HOSTS) else "redirect_not_followed"
        return res, None, None
    if status is None:
        res["outcome"] = "unreachable"
        return res, None, None
    if not (200 <= status < 300):
        res["outcome"] = "http_error"
        return res, None, None
    if not body:
        res["outcome"] = "empty_response"
        return res, None, None
    if kind == "reach":
        res["outcome"] = "reachable"
        return res, None, None
    try:
        obj = json.loads(body.decode("utf-8-sig"))
    except (ValueError, UnicodeDecodeError) as e:
        res["outcome"] = "not_json"
        res["error"] = mask_text(f"{type(e).__name__}: {e}", secrets)
        return res, None, None
    if kind == "swagger":
        res["outcome"] = "ok"
        return res, None, obj
    a = analyze_json(obj)
    n_rows = None
    sc = a["schema"]
    if sc.get("top_level") == "list":
        n_rows = sc.get("n_rows")
    elif isinstance(sc.get("data"), dict):
        n_rows = sc["data"].get("n_rows")
    res["outcome"] = "ok" if (n_rows is None or n_rows > 0) else "empty_dataset"
    res["schema"] = sc
    res["source_date_fields"] = a["source_date_fields"]
    res["freshness"] = judge_freshness(a["source_dates"], run_date, group)
    res["pe_like_field_names"] = a["pe_like_field_names"]
    res["pb_like_field_names"] = a["pb_like_field_names"]
    res["yield_like_field_names"] = a["yield_like_field_names"]
    res["contains_taiex_row"] = a["contains_taiex_row"]
    res["timeseries"] = a["timeseries"]
    return res, a, None


def build_research_metric(ep_results: dict) -> dict:
    """只記錄輸入是否齊備；不自創市場 PE、不輸出 implied earnings 數值。"""
    market_pe_names, probed_ok = {}, []
    for ep_id in MARKET_LEVEL_IDS:
        per = ep_results.get(ep_id, {})
        for t, r in per.items():
            if r.get("outcome") == "ok":
                probed_ok.append(f"{ep_id}/{t}")
                if r.get("pe_like_field_names"):
                    market_pe_names[f"{ep_id}/{t}"] = r["pe_like_field_names"]
    if market_pe_names:
        provided = "present_in_field_names_unverified"
    elif probed_ok:
        provided = False
    else:
        provided = "indeterminate_no_market_level_endpoint_ok"
    taiex_present = [f"{k}/{t}" for k, per in ep_results.items() for t, r in per.items() if r.get("contains_taiex_row")]
    bw = {}
    for ep_id in ("openapi_BWIBBU_ALL", "rwd_BWIBBU_d"):
        for t, r in ep_results.get(ep_id, {}).items():
            if r.get("outcome") == "ok":
                sc = r.get("schema", {})
                n = sc.get("n_rows") if sc.get("top_level") == "list" else (sc.get("data") or {}).get("n_rows")
                bw[f"{ep_id}/{t}"] = {"n_rows": n, "pe_like_field_names": r.get("pe_like_field_names"),
                                      "pb_like_field_names": r.get("pb_like_field_names"),
                                      "yield_like_field_names": r.get("yield_like_field_names")}
    return {
        "market_level_trailing_pe_field_provided": provided,
        "market_level_pe_field_names": market_pe_names,
        "taiex_row_present_in": taiex_present,
        "per_security_pe_sources": bw,
        "inputs_ready_for_implied_trailing_index_earnings": "⬜ 無法判定（universe／分母口徑待驗）",
        "implied_trailing_index_earnings": None,
        "note": "不自創市場 PE；不輸出 implied earnings 數值；actual／trailing 不得冒充 forward。",
    }


# ───────────────────────── 報告 ─────────────────────────

def _env_or_none(name):
    v = os.environ.get(name, "").strip()
    return v or None


def write_report(report: dict, path: str, secrets: tuple) -> None:
    """落盤前整份再掃一次（深度防禦）再 gzip。只用高熵長字串做全域替換（`strong_only`），
    低熵片段（port、短帳號）已在 error／content_type 等文字欄位遮蔽，不得全域替換而改寫 sample 數值。"""
    text = json.dumps(report, ensure_ascii=False, default=str)
    text = mask_text(text, secret_literals(strong_only=True))
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with gzip.open(path, "wb", compresslevel=9) as f:
        f.write(text.encode("utf-8"))


def run_probe(http_get=None, out_path=None, sleep_sec=1.0, now=None, endpoints=ENDPOINTS) -> dict:
    secrets = secret_literals()
    proxy_enabled = bool(os.environ.get("PROXY_URL", "").strip())
    now = now or datetime.now(timezone.utc)
    run_date = (now + timedelta(hours=8)).date()
    if http_get is None:
        http_get = make_http_get(secrets)
    report = {
        "schema_version": SCHEMA_VERSION,
        "probe": "twse_eps",
        "backlog": "BL-0509",
        "generated_at_utc": now.isoformat(),
        "run_date_taipei": run_date.isoformat(),
        "trigger_sha": _env_or_none("GITHUB_SHA"),
        "executed_sha": _env_or_none("PROBE_EXECUTED_SHA"),
        "proxy": {"enabled": proxy_enabled},
        "network_path": "每個端點各自量 direct（runner IP 直連）與 nas_proxy（PROXY_URL 環境變數；未設則 proxy_not_configured）兩條，互不降級。",
        "stale_after_days": STALE_AFTER_DAYS,
        "endpoints": [],
        "swagger_summary": None,
        "research_metric": None,
        "openapi_vs_rwd": None,
        "terms_research": None,
        "complete": False,
    }
    ep_results: dict = {}
    swagger_obj = None
    for ep in endpoints:
        ep_id, group, url, kind = ep
        entry = {"id": ep_id, "group": group, "url": url, "kind": kind, "transports": {},
                 "candidate": (ep_id in CANDIDATE_IDS or group == "financials")}
        for tr in TRANSPORTS:
            if sleep_sec and not (tr == "nas_proxy" and not proxy_enabled):
                time.sleep(sleep_sec)
            res, _a, sw = probe_one(http_get, ep, tr, run_date, secrets, proxy_enabled, sleep_sec)
            entry["transports"][tr] = res
            ep_results.setdefault(ep_id, {})[tr] = res
            if sw is not None and swagger_obj is None:
                swagger_obj = sw
        t = entry["transports"]
        if all(t[x].get("body_sha256") for x in TRANSPORTS):
            entry["direct_vs_nas_same_body"] = t["direct"]["body_sha256"] == t["nas_proxy"]["body_sha256"]
        report["endpoints"].append(entry)
        if out_path:
            write_report(report, out_path, secrets)
    report["swagger_summary"] = summarize_swagger(swagger_obj) if swagger_obj is not None else {"outcome": "missing"}
    report["research_metric"] = build_research_metric(ep_results)
    report["openapi_vs_rwd"] = build_openapi_vs_rwd(ep_results)
    report["terms_research"] = build_terms_research(
        http_get, swagger_obj, {e[2] for e in endpoints}, secrets, proxy_enabled, run_date, sleep_sec)
    report["complete"] = True
    if out_path:
        write_report(report, out_path, secrets)
    return report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default="probe_out/twse_eps_report.json.gz")
    ap.add_argument("--sleep", type=float, default=1.0, help="請求間隔秒數")
    args = ap.parse_args(argv)
    report = run_probe(out_path=args.out, sleep_sec=args.sleep)
    for e in report["endpoints"]:
        print(e["id"], {t: (r.get("outcome"), r.get("http_status")) for t, r in e["transports"].items()})
    print(f"report: {args.out} (proxy enabled={report['proxy']['enabled']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
