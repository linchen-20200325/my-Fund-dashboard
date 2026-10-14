#!/usr/bin/env python3
"""scripts/probe_moneydj_basic_page.py — 只讀探測：取 MoneyDJ 基本資料頁真實樣本，驗證 declared_profile 的解析與身分綁定前提。

## 為什麼要有這支

`repositories/fund/declared_profile.py::fetch_moneydj_basic_fields` 的標籤表結構**未以真實回應樣本驗證**，
而且「表格與代碼仍未綁定」（只確認頁面可見文字提到該代碼 ＋ 頁面上有一張含「基金名稱」的表）。
C2 擬以「**代碼是否以詞界出現在含『基金名稱』那張表自身的文字裡**」作為身分綁定規則 —— 那條規則能否成立，
要先看真實頁面。開發環境連 MoneyDJ 可能 403，故比照 `scripts/probe_fx_obs_date.py` 由 GitHub Actions
（`.github/workflows/moneydj_basic_probe.yml`）執行，報告推到 `probe/moneydj-basic-results`。

## 範圍（只讀，不改任何正式行為）

- **網址不在本檔新造**：一律由 `declared_profile._moneydj_urls(code)` 產生（yp011000／yp011001 ×
  tcbbankfund／www，順序與正式函式相同）。
- **連線不在本檔新寫**：照 `declared_profile` 的呼叫方式 `fetch_url_with_retry(url, timeout=20, retries=1)`
  （即 `fund_fetcher.fetch_url_with_retry` → `infra.proxy.fetch_url`），緊接著讀
  `infra.proxy.pop_last_fail_kind()`。不新增資料來源、不新增 API、不新增套件。
- **退避照守**：每個網址先問 `declared_profile._cooldown(url)`（＝ `infra.source_backoff.should_skip`），
  冷卻中**一個封包都不發**，報告記 `outcome="cooldown"`。只有真的發了請求才 sleep（預設 1.5 秒）。
- **解析借用正式函式**：`_parse_label_table`、`_mentions_code`、`_own_rows`、`is_valid_moneydj_page`，
  不在本檔另寫一份規則，免得量到的是別的東西。
- 另各代碼呼叫一次公開的 `fetch_moneydj_basic_fields`、`fetch_tdcc_listing`、`fetch_fundclear_declared_ccy`，
  完整回傳照錄。TDCC 3-2 回整份清單時，只存與這些代碼相關的列、欄名清單與總筆數
  （讀 `sources._tdcc_cache`，那是 `fetch_tdcc_listing` 剛取到的同一份，**不另發請求**）。
- 不寫任何試算表、不碰使用者設定、不呼叫任何寫入函式。唯一的輸出是 `--out` 指定的 JSON 檔。
- 失敗只記錄不中止；例外原文照錄（§1 Fail Loud）。錯誤原文寫進報告前遮蔽 `PROXY_URL` 字面值與網址內帳密；
  **查詢字串刻意不遮**：本探測的三個端點，查詢字串只有基金代碼（`?a=`、`?FundCode=`），沒有金鑰。

## 負控代碼

除 8 個實際代碼外，另加一個**確定不存在**的代碼當負控。依 `CLAUDE.md` §-2.A 第 8 款，負控字串**只在執行期生成、
不寫進任何文件**：生成規則是「`NX` ＋ 探測啟動時 Unix 秒的大寫十六進位」（見 `make_negative_control`）。
報告記錄生成規則與當次實際值（報告不是文件，每跑一次就換一個值）。

## 報告怎麼讀（本檔**不下結論**）

`pages[<代碼>]` 逐網址：`outcome`（`fetched`／`cooldown`／`http_failed`／`empty_response`／`exception`）、
`http_status`（取回時為回應狀態碼；失敗時取自 `infra.proxy` 收尾 log 的 `last_seen_status`，來源記在
`http_status_source`）、`final_url`、`redirect_history`、`content_length_bytes`、`text_length`、
`raw_html_gzip_b64`（**原始位元組** gzip 後 base64；`raw_sha256` 為原始位元組雜湊）、`title_tag_html`（`<title>` 原文）、
`parse`：
- `fields`／`label_conflicts`：`_parse_label_table` 對整頁的結果（四個標籤值原字面）；
- `page_text_mentions_code`：`_mentions_code(整頁, 代碼)`（＝正式函式現行的判準）；
- `name_table`：含「基金名稱」那張表（與 `_parse_label_table` 選中的同一張）——
  `table_text_mentions_code`（`_mentions_code(該表節點, 代碼)`，含巢狀表的文字）、
  `own_rows_text_mentions_code`（只看該表自己的列，不含巢狀表）、`nested_in_table`、`index`、`text_excerpt`、
  `probe_codes_mentioned`（該表文字提到本次探測清單裡的哪些代碼）；
- `would_be_ok_now`：依正式函式現行條件會不會判 `ok`；`would_be_ok_with_table_binding`：
  若改成 C2 擬議的「代碼須出現在該表自身文字」會不會判 `ok`。
「C2 規則能否成立」要拿實際代碼與負控兩邊的 `name_table.table_text_mentions_code` 對照判讀。

CLI
===
    python scripts/probe_moneydj_basic_page.py
    python scripts/probe_moneydj_basic_page.py --out probe_out/moneydj_basic_report.json

退出碼：報告一律先寫出；一個 `fetched` 的頁面都沒有 → 1（沒有樣本，不能當成功）；
報告寫不成嚴格 JSON（已寬鬆寫出並標 `strict_json_error`）→ 1；寫檔失敗 → 例外直接炸。
"""
from __future__ import annotations

import argparse
import base64
import contextlib
import gzip
import hashlib
import io
import json
import math
import os
import re
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlsplit

# scripts/ 下執行也能 import repositories.* / infra.*（同 scripts/probe_fx_obs_date.py）
_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

#: 探測對象（派工單指定）：ACCP138 為境內，其餘為境外／保單平台代碼。
PROBE_CODES: tuple[str, ...] = ("ACCP138", "JFZN3", "JFZA6", "JFZA5", "JFZA3",
                                "JFZK2", "TLZF9", "ACTI71")
NEGATIVE_CONTROL_RULE = "NX ＋ 探測啟動時 Unix 秒（整數）的大寫十六進位"
SLEEP_SEC = 1.5
#: 單頁原始位元組超過此值才截斷（並標 `raw_truncated`）；MoneyDJ 基本資料頁遠小於此值。
MAX_RAW_BYTES = 3_000_000
SNIPPET_MAX = 5
SNIPPET_RADIUS = 40
TDCC_RELATED_ROWS_MAX = 20
DEFAULT_OUT = Path("probe_out") / "moneydj_basic_report.json"
#: 照 `declared_profile._fetch_moneydj_basic_fields_cached` 的呼叫參數。
FETCH_TIMEOUT = 20
FETCH_RETRIES = 1

_RE_LAST_SEEN = re.compile(r"last_seen_status=(\d{3})")
_RE_USERINFO = re.compile(r"(?P<scheme>[A-Za-z][A-Za-z0-9+.-]*://)[^\s/@'\"]+@")


# ───────────────────────── 遮蔽 ─────────────────────────

def _secret_literals() -> tuple[str, ...]:
    """`PROXY_URL` 整串，以及其中的帳號密碼段。"""
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


def mask_text(text, secrets: tuple[str, ...] = ()) -> str:
    """遮蔽明列的秘密字面值與網址內的帳密（`scheme://帳:密@`）。查詢字串不遮（理由見檔頭）。"""
    out = str(text)
    for s in sorted((s for s in secrets if s), key=len, reverse=True):
        out = out.replace(s, "***")
    return _RE_USERINFO.sub(lambda m: m.group("scheme") + "***@", out)


# ───────────────────────── 小工具 ─────────────────────────

def make_negative_control(now_sec: float) -> str:
    """負控代碼：`NX` ＋ Unix 秒的大寫十六進位（規則見 `NEGATIVE_CONTROL_RULE`；字串不落文件）。"""
    return "NX" + format(int(now_sec), "X")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def to_strict_json(obj):
    """遞迴把 NaN／±inf 轉成 None，讓報告能以 `allow_nan=False` 寫出（同 probe_fx_obs_date）。"""
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {k: to_strict_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_strict_json(v) for v in obj]
    return obj


def _exc_record(e: BaseException, secrets) -> dict:
    """例外原文照錄：型別、訊息、traceback（已遮蔽）。"""
    return {"type": type(e).__name__,
            "message": mask_text(str(e), secrets),
            "traceback": mask_text("".join(traceback.format_exception(type(e), e, e.__traceback__)),
                                   secrets)}


def _log_lines(buf: io.StringIO, secrets) -> list:
    return [mask_text(x, secrets) for x in buf.getvalue().splitlines() if x.strip()]


def http_status_from_log(lines) -> Optional[int]:
    """失敗時 `infra.proxy.fetch_url` 收尾 log 的 `last_seen_status=NNN`（最後一筆）；沒有 → None（不猜）。"""
    found = None
    for ln in lines:
        m = _RE_LAST_SEEN.search(ln)
        if m:
            found = int(m.group(1))
    return found


def code_pattern(code: str) -> "re.Pattern":
    """與 `declared_profile._mentions_code` 同一條詞界規則（前後不得緊接英數字，大小寫不分）。"""
    return re.compile(rf"(?<![A-Za-z0-9]){re.escape(code)}(?![A-Za-z0-9])", re.IGNORECASE)


def code_snippets(text: str, code: str, n: int = SNIPPET_MAX, radius: int = SNIPPET_RADIUS) -> list:
    """可見文字中代碼出現處的前後文（最多 n 筆），供人工判讀出現在哪裡。"""
    out = []
    for m in code_pattern(code).finditer(text or ""):
        a, b = max(0, m.start() - radius), min(len(text), m.end() + radius)
        out.append(re.sub(r"\s+", " ", text[a:b]).strip())
        if len(out) >= n:
            break
    return out


class _OneTable:
    """把單一張表包成 `_parse_label_table` 認得的形狀（它只呼叫 `.find_all("table")`）。
    `_parse_label_table` 對每張表各自從空的 `seen` 開始，所以逐張餵進去、取第一張回非 None 的，
    就是它對整頁選中的那一張（`analyze_html` 另行比對兩者一致）。"""

    def __init__(self, tbl):
        self._tbl = tbl

    def find_all(self, name, *args, **kwargs):
        return [self._tbl]


def _own_rows_text(dp, tbl) -> str:
    """表格**自己的**列（`_own_rows`，不含巢狀表的列）、列的直接子 td 文字，以空白串起。"""
    parts = []
    for row in dp._own_rows(tbl):
        for cell in row.find_all("td", recursive=False):
            # 只取該格自己的文字，不含格內巢狀表
            texts = [s for s in cell.find_all(string=True)
                     if s.find_parent("table") is tbl]
            parts.append(" ".join(t.strip() for t in texts if t.strip()))
    return " ".join(p for p in parts if p)


def analyze_html(html: str, code: str, probe_codes=PROBE_CODES, dp=None) -> dict:
    """以 declared_profile 的正式解析函式分析一頁。不打網路。"""
    if dp is None:
        from repositories.fund import declared_profile as dp
    from bs4 import BeautifulSoup
    from fund_fetcher import is_valid_moneydj_page

    soup = BeautifulSoup(html, "lxml")
    fields, conflicts = dp._parse_label_table(soup)
    page_mentions = dp._mentions_code(soup, code)
    page_text = soup.get_text(" ")
    out = {
        "fields": fields,
        "label_conflicts": conflicts,
        "page_text_mentions_code": page_mentions,
        "page_text_code_snippets": code_snippets(page_text, code),
        "looks_like_moneydj": is_valid_moneydj_page(html),
        "table_count": len(soup.find_all("table")),
        "title_tag_html": str(soup.title) if soup.title is not None else None,
        "title_text": soup.title.get_text() if soup.title is not None else None,
        "name_table": None,
    }
    for idx, tbl in enumerate(soup.find_all("table")):
        t_fields, t_conflicts = dp._parse_label_table(_OneTable(tbl))
        if t_fields is None:
            continue
        tbl_text = tbl.get_text(" ")
        own_text = _own_rows_text(dp, tbl)
        out["name_table"] = {
            "index": idx,
            "consistent_with_whole_page_parse": (t_fields == fields and t_conflicts == conflicts),
            "nested_in_table": tbl.find_parent("table") is not None,
            "contains_nested_table": tbl.find("table") is not None,
            "table_text_mentions_code": dp._mentions_code(tbl, code),
            "own_rows_text_mentions_code": bool(code_pattern(code).search(own_text)),
            "table_text_code_snippets": code_snippets(tbl_text, code),
            "probe_codes_mentioned": [c for c in probe_codes if code_pattern(c).search(tbl_text)],
            "text_length": len(tbl_text),
            "text_excerpt": re.sub(r"\s+", " ", tbl_text).strip()[:600],
        }
        break
    name_ok = bool(fields is not None and fields.get(dp._NAME_LABEL))
    nt = out["name_table"] or {}
    out["would_be_ok_now"] = bool(name_ok and page_mentions)
    out["would_be_ok_with_table_binding"] = bool(name_ok and nt.get("table_text_mentions_code"))
    return out


# ───────────────────────── 取數（只讀） ─────────────────────────

def probe_page(code: str, host: str, page: str, url: str, *, fetcher, pop_fail_kind, backoff_check,
               analyzer, secrets, probe_codes, before_send=None) -> tuple[dict, bool]:
    """取一個網址並分析。回 (紀錄, 是否真的發了請求)。失敗只記錄不拋。
    `before_send`：確定要發請求（不在冷卻中）時、發請求之前呼叫一次（用來 sleep；冷卻跳過的網址不 sleep）。"""
    rec = {"url": url, "host": host, "page_type": page, "requested_at": _now_iso(),
           "responded_at": None, "outcome": None, "fail_kind": None,
           "http_status": None, "http_status_source": None, "final_url": None,
           "redirect_history": [], "content_type": None, "encoding": None,
           "content_length_bytes": None, "text_length": None,
           "raw_sha256": None, "raw_truncated": False, "raw_html_gzip_b64": None,
           "fetch_log": [], "parse": None, "parse_error": None, "error": None}
    skip, origin = backoff_check(url)
    if skip:
        rec.update(outcome="cooldown", fail_kind="cooldown", cooldown_origin_kind=origin,
                   error=f"host 冷卻中（當初分類 {origin}），未發請求")
        return rec, False
    if before_send is not None:
        before_send()
    rec["requested_at"] = _now_iso()
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            r = fetcher(url, timeout=FETCH_TIMEOUT, retries=FETCH_RETRIES)
            # 不變式（infra/proxy.py）：分類緊接在自己的 fetch 之後讀。
            kind = pop_fail_kind()
    except Exception as e:   # 照錄原文，不吞
        rec["fetch_log"] = _log_lines(buf, secrets)
        rec.update(outcome="exception", fail_kind="exception", responded_at=_now_iso(),
                   error=_exc_record(e, secrets))
        return rec, True
    rec["responded_at"] = _now_iso()
    rec["fetch_log"] = _log_lines(buf, secrets)
    if r is None:
        st = http_status_from_log(rec["fetch_log"])
        rec.update(http_status=st, http_status_source=("fetch_log:last_seen_status" if st else None))
        if kind:
            rec.update(outcome="http_failed", fail_kind=kind,
                       error=f"fetch_url_with_retry 回 None（失敗分類：{kind}）")
        else:
            rec.update(outcome="empty_response", fail_kind="",
                       error="fetch_url_with_retry 回 None 且無失敗分類（200 但內文為空白）")
        return rec, True
    try:
        content = bytes(getattr(r, "content", b"") or b"")
        text = r.text or ""
        rec.update(outcome="fetched", http_status=getattr(r, "status_code", None),
                   http_status_source="response", final_url=getattr(r, "url", None),
                   redirect_history=[{"status": getattr(h, "status_code", None), "url": getattr(h, "url", None)}
                                     for h in (getattr(r, "history", None) or [])],
                   content_type=(getattr(r, "headers", None) or {}).get("Content-Type"),
                   encoding=getattr(r, "encoding", None),
                   content_length_bytes=len(content), text_length=len(text),
                   raw_sha256=hashlib.sha256(content).hexdigest())
        stored = content
        if len(stored) > MAX_RAW_BYTES:
            stored = stored[:MAX_RAW_BYTES]
            rec["raw_truncated"] = True
        rec["raw_html_gzip_b64"] = base64.b64encode(gzip.compress(stored, mtime=0)).decode("ascii")
    except Exception as e:
        rec["error"] = _exc_record(e, secrets)
        return rec, True
    try:
        rec["parse"] = analyzer(text, code, probe_codes)
    except Exception as e:   # 解析例外照錄，頁面原文已存
        rec["parse_error"] = _exc_record(e, secrets)
    return rec, True


def _call_public(fn, code: str, secrets) -> dict:
    """呼叫一支公開函式，完整回傳照錄；例外原文照錄、不拋。"""
    buf = io.StringIO()
    out = {"called_at": _now_iso(), "returned_at": None, "result": None, "exception": None, "log": []}
    try:
        with contextlib.redirect_stdout(buf):
            out["result"] = fn(code)
    except Exception as e:
        out["exception"] = _exc_record(e, secrets)
    out["returned_at"] = _now_iso()
    out["log"] = _log_lines(buf, secrets)
    return out


def tdcc_listing_extract(data, codes) -> dict:
    """TDCC 3-2 整份清單 → 總筆數、欄名、與這些代碼相關的列（不存整份）。"""
    if data is None:
        return {"available": False, "note": "sources._tdcc_cache 沒有 3-2（取數失敗或未取到），不另發請求"}
    if not isinstance(data, list):
        return {"available": False, "note": f"3-2 快取不是串列（{type(data).__name__}）"}
    from repositories.fund import declared_profile as dp
    dict_rows = [x for x in data if isinstance(x, dict)]
    columns = sorted({k for row in dict_rows for k in row})
    first_keys = list(dict_rows[0].keys()) if dict_rows else []
    exact, loose = {}, {}
    for c in codes:
        pat = code_pattern(c)
        exact[c] = [row for row in dict_rows
                    if any(str(row.get(k) or "").upper() == c for k in dp._TDCC_CODE_KEYS)]
        hits = [row for row in dict_rows
                if any(pat.search(str(v)) for v in row.values() if v is not None)]
        loose[c] = {"count": len(hits), "rows": hits[:TDCC_RELATED_ROWS_MAX],
                    "truncated": len(hits) > TDCC_RELATED_ROWS_MAX}
    return {"available": True, "total_rows": len(data), "dict_rows": len(dict_rows),
            "non_dict_rows": len(data) - len(dict_rows), "columns": columns,
            "first_row_key_order": first_keys,
            "code_keys_used_by_declared_profile": list(dp._TDCC_CODE_KEYS),
            "rows_matching_code_keys": exact,
            "rows_mentioning_code_any_field": loose}


def _proxy_used_by_infra() -> Optional[bool]:
    try:
        from infra.proxy import get_proxy_config
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return get_proxy_config() is not None
    except Exception:
        return None


def _env_or_none(name: str) -> Optional[str]:
    v = os.environ.get(name)
    if v is None or not v.strip():
        return None
    return v.strip()


def _default_tdcc_list():
    from repositories.fund import sources as _src
    return _src._tdcc_cache.get("3-2")


def _default_backoff_state():
    from infra import source_backoff as sb
    return sb.get_backoff_state()


def run(codes, *, url_builder=None, fetcher=None, pop_fail_kind=None, backoff_check=None,
        analyzer=None, public_fns=None, tdcc_list_getter=None, backoff_state_getter=None,
        sleep_fn: Optional[Callable[[float], None]] = None, sleep_sec: float = SLEEP_SEC,
        negative_control: Optional[str] = None) -> dict:
    """取數 ＋ 分析全部代號，回報告 dict（不寫檔）。所有依賴可注入，測試不打網路。"""
    need_dp = any(x is None for x in (url_builder, fetcher, pop_fail_kind, backoff_check, public_fns))
    dp = None
    if need_dp:
        from repositories.fund import declared_profile as dp
    url_builder = url_builder or dp._moneydj_urls
    fetcher = fetcher or dp.fetch_url_with_retry
    pop_fail_kind = pop_fail_kind or dp._proxy.pop_last_fail_kind
    backoff_check = backoff_check or dp._cooldown
    analyzer = analyzer or (lambda html, code, pc: analyze_html(html, code, pc))
    if public_fns is None:
        public_fns = {"fetch_moneydj_basic_fields": dp.fetch_moneydj_basic_fields,
                      "fetch_tdcc_listing": dp.fetch_tdcc_listing,
                      "fetch_fundclear_declared_ccy": dp.fetch_fundclear_declared_ccy}
    tdcc_list_getter = tdcc_list_getter or _default_tdcc_list
    backoff_state_getter = backoff_state_getter or _default_backoff_state
    sleep_fn = sleep_fn or time.sleep
    if negative_control is None:
        negative_control = make_negative_control(time.time())
    secrets = _secret_literals()
    all_codes = list(dict.fromkeys(list(codes) + [negative_control]))
    probe_codes = tuple(all_codes)

    report = {
        "generated_at_utc": _now_iso(),
        "purpose": "驗證 declared_profile.fetch_moneydj_basic_fields 的解析，以及「代碼以詞界出現在含『基金名稱』"
                   "那張表自身文字」能否作為 C2 身分綁定規則",
        "url_source": "repositories.fund.declared_profile._moneydj_urls",
        "fetch_call": f"declared_profile.fetch_url_with_retry(url, timeout={FETCH_TIMEOUT}, retries={FETCH_RETRIES})",
        "sleep_sec_between_requests": sleep_sec,
        "codes": list(codes),
        "negative_control": {"code": negative_control, "rule": NEGATIVE_CONTROL_RULE},
        "proxy_env_set": bool(os.environ.get("PROXY_URL", "").strip()),
        "proxy_used_by_infra": _proxy_used_by_infra(),
        "github_run_id": _env_or_none("GITHUB_RUN_ID"),
        # 觸發 SHA（按鈕分支那顆）≠ 實際執行的程式碼；後者看 executed_sha（同 probe_fx_obs_date）。
        "trigger_sha": _env_or_none("GITHUB_SHA"),
        "executed_sha": _env_or_none("PROBE_EXECUTED_SHA"),
        "event_name": _env_or_none("GITHUB_EVENT_NAME"),
        "pages": {},
        "public_calls": {},
        "tdcc_3_2_extract": None,
        "backoff_state_end": None,
    }

    # 第一輪：逐網址取原始頁（網址組全部試完，不因 ok 停止 —— 要的是樣本）。
    sent_any = False
    for code in all_codes:
        recs = []
        try:
            urls = list(url_builder(code))
        except Exception as e:
            report["pages"][code] = {"url_builder_error": _exc_record(e, secrets)}
            continue
        for host, page, url in urls:
            rec, sent = probe_page(code, host, page, url, fetcher=fetcher, pop_fail_kind=pop_fail_kind,
                                   backoff_check=backoff_check, analyzer=analyzer, secrets=secrets,
                                   probe_codes=probe_codes,
                                   before_send=(lambda: sleep_fn(sleep_sec)) if sent_any else None)
            sent_any = sent_any or sent
            recs.append(rec)
        report["pages"][code] = recs

    # 第二輪：公開函式各呼叫一次（完整回傳照錄）。
    for code in all_codes:
        calls = {}
        for name, fn in public_fns.items():
            sleep_fn(sleep_sec)
            calls[name] = _call_public(fn, code, secrets)
        report["public_calls"][code] = calls

    try:
        report["tdcc_3_2_extract"] = tdcc_listing_extract(tdcc_list_getter(), all_codes)
    except Exception as e:
        report["tdcc_3_2_extract"] = {"available": False, "error": _exc_record(e, secrets)}
    try:
        report["backoff_state_end"] = backoff_state_getter()
    except Exception as e:
        report["backoff_state_end"] = {"error": _exc_record(e, secrets)}
    report["summary"] = summarize(report)
    return report


def summarize(report: dict) -> dict:
    """逐代碼的精簡摘要（判讀仍以完整欄位為準）。"""
    out = {}
    for code, recs in report.get("pages", {}).items():
        if not isinstance(recs, list):
            out[code] = {"error": "url_builder_error"}
            continue
        rows = []
        for r in recs:
            p = r.get("parse") or {}
            nt = p.get("name_table") or {}
            rows.append({
                "url": r.get("url"), "outcome": r.get("outcome"), "http_status": r.get("http_status"),
                "len": r.get("content_length_bytes"),
                "has_name_table": bool(p.get("name_table")),
                "page_mentions": p.get("page_text_mentions_code"),
                "table_mentions": nt.get("table_text_mentions_code"),
                "would_be_ok_now": p.get("would_be_ok_now"),
                "would_be_ok_with_table_binding": p.get("would_be_ok_with_table_binding"),
            })
        pub = (report.get("public_calls", {}).get(code) or {})
        out[code] = {"pages": rows,
                     "public_status": {k: ((v.get("result") or {}).get("status")
                                           if v.get("exception") is None else "exception")
                                       for k, v in pub.items()}}
    out["fetched_page_count"] = sum(1 for recs in report.get("pages", {}).values() if isinstance(recs, list)
                                    for r in recs if r.get("outcome") == "fetched")
    return out


def _summary_lines(report: dict) -> list:
    s = report.get("summary") or {}
    lines = [f"proxy_env_set={report['proxy_env_set']} proxy_used_by_infra={report['proxy_used_by_infra']}",
             f"負控規則：{report['negative_control']['rule']}",
             f"fetched 頁數={s.get('fetched_page_count')}"]
    for code, v in s.items():
        if not isinstance(v, dict) or "pages" not in v:
            continue
        cells = [f"{r['outcome']}/{r['http_status']}/表={r['has_name_table']}/頁提={r['page_mentions']}"
                 f"/表提={r['table_mentions']}" for r in v["pages"]]
        lines.append(f"{code}: {' | '.join(cells)} || 公開函式={v['public_status']}")
    return lines


def main(argv=None, **run_kwargs) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="報告輸出路徑（JSON）")
    args = ap.parse_args(argv)

    report = run(PROBE_CODES, **run_kwargs)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    # 嚴格 JSON：NaN／±inf 轉 null 後以 allow_nan=False 寫出；寫不出時保底寬鬆寫出並標 strict_json_error。
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
    return 0 if (report.get("summary") or {}).get("fetched_page_count") else 1


if __name__ == "__main__":
    sys.exit(main())
