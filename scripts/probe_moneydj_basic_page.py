#!/usr/bin/env python3
"""scripts/probe_moneydj_basic_page.py — 只讀探測：取 MoneyDJ 基本資料頁真實樣本，驗證 declared_profile 的解析與身分綁定前提。

## 為什麼要有這支

`repositories/fund/declared_profile.py::fetch_moneydj_basic_fields` 的標籤表結構**未以真實回應樣本驗證**，
而且「表格與代碼仍未綁定」（只確認頁面可見文字提到該代碼 ＋ 頁面上有一張含「基金名稱」的表）。
C2 擬以「**代碼以詞界出現在含『基金名稱』那張表自身的文字裡**」作為身分綁定規則 —— 那條規則能否成立，
要先看真實頁面。開發環境連 MoneyDJ 可能 403，故比照 `scripts/probe_fx_obs_date.py` 由 GitHub Actions
（`.github/workflows/moneydj_basic_probe.yml`）執行，報告推到 `probe/moneydj-basic-results`。

## ⚠️ 量到的是哪一條連線路徑（先讀這段）

`infra.proxy.get_proxy_config()` 只讀 `st.secrets`，Actions 上沒有 `secrets.toml` → **不走 NAS 代理，
以 GitHub runner IP 直連**。repo 內沒有任何先例把環境變數橋接進 `infra.proxy`（`scripts/fetch_nav_cache.py`
是自建 Session 讀 `PROXY_URL`，不經 `infra.proxy`），本探測也不新增。
⇒ **本報告量到的是 GitHub runner IP 直連的結果，與 production 經 NAS 代理的路徑不同**（報告頂層 `network_path` 同此）。

## 範圍（只讀，不改任何正式行為）

- **網址不在本檔新造**：一律由 `declared_profile._moneydj_urls(code)` 產生（yp011000／yp011001 ×
  tcbbankfund／www）。
- **連線不在本檔新寫**：照 `declared_profile` 的呼叫方式 `fetch_url_with_retry(url, timeout=20, retries=1)`
  （即 `fund_fetcher.fetch_url_with_retry` → `infra.proxy.fetch_url`），緊接著讀
  `infra.proxy.pop_last_fail_kind()`。不新增資料來源、不新增 API、不新增套件。
- **退避照守**：每次發請求前先查 `infra.source_backoff.should_skip`（與 `declared_profile._cooldown` 同一個判斷），
  冷卻中**一個封包都不發**。冷卻分類為 `unreachable`／`server_error` 時，在時間預算內**等冷卻自然到期再續**，
  每個主機最多等一次；`blocked`（403）、`rate_limited`（429）不等。每次等待（或不等的理由）記在 `waits`。
- **取數順序（先廣後深）**：代碼順序為「第一個實際代碼 → 負控 → 其餘實際代碼」；第一輪每個代碼只取首選頁型的
  網址（依 `_moneydj_urls` 的順序），第二輪再回頭取次要頁型。sleep（預設 1.5 秒）**只在確實要發請求前**。
- **解析借用正式函式**：`_parse_label_table`、`_mentions_code`、`is_valid_moneydj_page`。
- 公開函式只呼叫 `fetch_tdcc_listing` 與 `fetch_fundclear_declared_ccy`（各代碼一次，完整回傳照錄）。
  `fetch_moneydj_basic_fields` **不呼叫**：原始頁那一輪的 ~~`would_be_ok_now`~~ `would_be_ok_old_rule`／
  `would_be_ok_identity_rule` 已涵蓋它的判準（後者不含最終網址檢查，見下），再呼叫會加倍請求。
- TDCC 3-2：讀 `sources._tdcc_cache`（`fetch_tdcc_listing` 剛取到的同一份，**不另發請求**），比中規則與正式函式相同
  （只看第一個非空代碼欄）；整份清單 gzip＋base64 存進報告，預估超過 2 MB 時改存欄名與每列代碼／名稱欄。
- 不寫任何試算表、不碰使用者設定、不呼叫任何寫入函式。唯一的輸出是 `--out` 指定的 JSON 檔。
- 失敗只記錄不中止；例外原文照錄（§1 Fail Loud）。錯誤原文寫進報告前遮蔽 `PROXY_URL` 字面值與網址內帳密；
  **查詢字串刻意不遮**：本探測的端點，查詢字串只有基金代碼（`?a=`、`?FundCode=`），沒有金鑰。
- **報告逐步寫出**：每完成一個代碼的一步就覆寫一次報告檔（`complete=false`），最後一次為完整版
  （`complete=true`）；workflow 逾時時已取到的樣本不會整輪丟失。

## 負控代碼

依 `CLAUDE.md` §-2.A 第 8 款，負控字串**只在執行期生成、不寫進任何文件**：生成規則是
「`NX` ＋ 探測啟動時 Unix 秒的大寫十六進位」（`make_negative_control`）。報告記錄規則與當次實際值
（屬資料產出、每輪不同，不作為掃描用字表）。

## 報告怎麼讀（本檔**不下結論**）

`pages[<代碼>]` 逐網址：`outcome`（`fetched`／`cooldown`／`http_failed`／`empty_response`／`exception`）、
`http_status`（取回時為回應狀態碼；失敗時取自 `infra.proxy` 收尾 log 的 `last_seen_status`，來源記在
`http_status_source`）、`final_url`、`redirect_history`、`content_length_bytes`、`text_length`、
`raw_html_gzip_b64`（**原始位元組** gzip 後 base64；`raw_sha256` 為原始位元組雜湊）、`title_tag_html`（`<title>` 原文）、
`parse`：
- `fields`／`label_conflicts`：`_parse_label_table` 對整頁的結果；`page_text_mentions_code`：正式函式現行判準；
- `name_table_candidates`：**每一張**單獨餵給 `_parse_label_table` 會回結果的表（含「基金名稱」且值非空），
  逐張記 `mentions_incl_nested`（`_mentions_code(該表節點)`，含巢狀表文字）與 `mentions_own`
  （該表 `get_text` 扣掉其巢狀表的文字；含 `th`、`caption`，不含註解與 `script`／`style`）；
- `name_table`：候選中的第一張（＝ `_parse_label_table` 對整頁選中的那一張）。
  `consistent_with_whole_page_parse` **依構造恆真**（`_parse_label_table` 對每張表各自從空的狀態開始，逐張餵與整頁餵
  選中同一張）——它只防「正式函式的呼叫方式／內部選表規則」日後漂移，不是一項發現；
- ~~`would_be_ok_now`：正式函式現行條件；~~ → 2026-10-14 #967 修正輪（有意識的更正，不是漏刪；決策者：AI 總管）：改名 `would_be_ok_old_rule` ——
  它算的是**舊**判準（名稱非空＋頁面可見文字提到代碼），正式函式已改用身分判準（docs/v2/49 第 8 節 (aa)），
  名字說「現在」會誤導；`would_be_ok_with_table_binding_own`／`..._incl_nested`：
  改成 C2 擬議規則（代碼須出現在該表自身文字／含巢狀表文字）時會不會判 `ok`（同屬已推翻的舊擬議，照實保留）。
- `identity_rule`（2026-10-14 #967 修正輪（有意識的更正，不是漏刪；決策者：AI 總管） 新增）：`declared_profile._identify_name_table` 對整頁的結果（`problem`、含「基金名稱」
  標籤的表張數、其中非空張數）；`would_be_ok_identity_rule`＝`problem` 為 None。⚠️ **不含**正式函式的最終網址檢查
  （本腳本分析的是存下來的 HTML，最終網址另記在每頁的 `final_url`／`redirect_history`）。

CLI
===
    python scripts/probe_moneydj_basic_page.py --out probe_out/moneydj_basic_report.json

退出碼：報告一律先寫出；實際代碼一個 `fetched` 的頁面都沒有（含「只有負控取到頁面」）→ 1；
報告寫不成嚴格 JSON（已寬鬆寫出並標 `strict_json_error`）→ 1；寫檔失敗 → 例外直接炸。
"""
from __future__ import annotations

import argparse
import base64
import contextlib
import copy
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
from collections import Counter
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
NETWORK_PATH_NOTE = ("本報告量到的是 GitHub runner IP 直連的結果，與 production 經 NAS 代理的路徑不同"
                     "（infra.proxy.get_proxy_config 只讀 st.secrets；Actions 上沒有 secrets.toml，"
                     "repo 內也沒有把環境變數橋接進 infra.proxy 的先例）")
SLEEP_SEC = 1.5
#: 這兩種冷卻在預算內等它自然到期；blocked（403）、rate_limited（429）不等。
WAITABLE_KINDS = frozenset({"unreachable", "server_error"})
#: 等待時多等的秒數，避開冷卻剛好到期的邊界。
WAIT_PAD_SEC = 1.0
#: 從啟動起算的等待預算（秒）：超過就不再等。
#: ~~workflow 的 timeout-minutes 為 40，留 10 分鐘給其餘步驟。~~
#: → 2026-10-14 更正（有意識的更正，不是漏刪；依 #961 修正輪稽核）：workflow 的 timeout-minutes 已改為 60，
#:   扣 30 分鐘等待預算，其餘留給請求與前後步驟。舊句寫於逾時仍是 40 分鐘時，逾時調整後未同步。
WAIT_BUDGET_SEC = 30 * 60
#: 單頁原始位元組超過此值才截斷（並標 `raw_truncated`）。
#: ~~1 MB：最多 9 代碼 × 4 網址 = 36 頁，base64 後上界約 49 MB，低於 GitHub 單檔 50 MB 警告線~~
#: → 2026-10-14 更正（有意識的更正，不是漏刪；依 #961 修正輪稽核）：舊句沒算進 TDCC 清單。
#:   **推算、非實量**：36 頁 × 1 MB × 4/3（base64）≈ 48.0 MB，加 TDCC 完整清單上限 2 MB
#:   ≈ 50.0 MB（十進位）＝ 47.7 MiB，仍低於 GitHub 50 MiB 警告線；另有 JSON 其餘欄位的開銷未計。
#:   ⚠️ TDCC 改存精簡版時沒有大小上限（精簡版只留代碼與名稱欄，預期遠小於 2 MB，未實量）。
#: （原為 3 MB，依 #961 修正輪稽核下修；有意識的更正，不是漏刪）。
MAX_RAW_BYTES = 1_000_000
#: TDCC 整份清單 gzip＋base64 後的預估上限；超過改存精簡版。
TDCC_FULL_MAX_B64_BYTES = 2_000_000
SNIPPET_MAX = 5
SNIPPET_RADIUS = 40
TDCC_RELATED_ROWS_MAX = 20
#: 每頁「含基金名稱的候選表」最多存幾張（總張數另記，超過標 `name_table_candidates_truncated`）。
NAME_TABLE_CANDIDATES_MAX = 20
DEFAULT_OUT = Path("probe_out") / "moneydj_basic_report.json"
#: 照 `declared_profile._fetch_moneydj_basic_fields_cached` 的呼叫參數。
FETCH_TIMEOUT = 20
FETCH_RETRIES = 1

_RE_LAST_SEEN = re.compile(r"last_seen_status=(\d{3})")
_RE_USERINFO = re.compile(r"(?P<scheme>[A-Za-z][A-Za-z0-9+.-]*://)[^\s/@'\"]+@")


# ───────────────────────── 遮蔽 ─────────────────────────

def _secret_literals() -> tuple[str, ...]:
    """`PROXY_URL` 整串，以及其中的帳號密碼段（workflow 不傳它；保留遮蔽以防本機執行時有設）。"""
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


def order_codes(codes, negative_control: str) -> list:
    """代碼順序：第一個實際代碼 → 負控 → 其餘（負控排第 2：前面的主機冷卻較少波及它）。"""
    codes = list(dict.fromkeys(codes))
    if not codes:
        return [negative_control]
    return [codes[0], negative_control] + [c for c in codes[1:] if c != negative_control]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _host(url: str) -> str:
    """退避鍵（同 `infra.source_backoff.source_key`：host 小寫）。"""
    try:
        return urlsplit(str(url)).netloc.lower() or str(url)[:80]
    except Exception:
        return str(url)[:80]


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
    """文字中代碼出現處的前後文（最多 n 筆），供人工判讀出現在哪裡。"""
    out = []
    for m in code_pattern(code).finditer(text or ""):
        a, b = max(0, m.start() - radius), min(len(text), m.end() + radius)
        out.append(re.sub(r"\s+", " ", text[a:b]).strip())
        if len(out) >= n:
            break
    return out


class _OneTable:
    """把單一張表包成 `_parse_label_table` 認得的形狀（它只呼叫 `.find_all("table")`）。"""

    def __init__(self, tbl):
        self._tbl = tbl

    def find_all(self, name, *args, **kwargs):
        return [self._tbl]


def own_table_text(tbl) -> str:
    """該表 `get_text(" ")` 扣掉其巢狀表的文字：複製節點、拿掉內層所有 `table` 後取文字。
    含 `th`、`caption`；`get_text` 本來就不含註解與 `script`／`style`。結果必為整張表文字的子集。"""
    c = copy.copy(tbl)
    for inner in c.find_all("table"):
        inner.decompose()
    return c.get_text(" ")


def analyze_html(html: str, code: str, probe_codes=(), dp=None) -> dict:
    """以 declared_profile 的正式解析函式分析一頁。不打網路。"""
    if dp is None:
        from repositories.fund import declared_profile as dp
    from bs4 import BeautifulSoup
    from fund_fetcher import is_valid_moneydj_page

    soup = BeautifulSoup(html, "lxml")
    fields, conflicts = dp._parse_label_table(soup)
    page_mentions = dp._mentions_code(soup, code)
    pat = code_pattern(code)
    candidates = []
    for idx, tbl in enumerate(soup.find_all("table")):
        t_fields, t_conflicts = dp._parse_label_table(_OneTable(tbl))
        if t_fields is None:
            continue
        incl = tbl.get_text(" ")
        own = own_table_text(tbl)
        candidates.append({
            "index": idx,
            "fields": t_fields,
            "label_conflicts": t_conflicts,
            "nested_in_table": tbl.find_parent("table") is not None,
            "contains_nested_table": tbl.find("table") is not None,
            "mentions_incl_nested": dp._mentions_code(tbl, code),
            "mentions_own": bool(pat.search(own)),
            "own_text_is_subset": not (Counter(own.split()) - Counter(incl.split())),
            "code_snippets_incl_nested": code_snippets(incl, code),
            "code_snippets_own": code_snippets(own, code),
            "probe_codes_mentioned_incl_nested": [c for c in probe_codes if code_pattern(c).search(incl)],
            "text_length_incl_nested": len(incl),
            "text_length_own": len(own),
            "text_excerpt_own": re.sub(r"\s+", " ", own).strip()[:600],
        })
    chosen = candidates[0] if candidates else None
    if chosen is not None:
        chosen = dict(chosen)
        # 依構造恆真（見檔頭）；只防正式函式的呼叫方式／選表規則漂移。
        chosen["consistent_with_whole_page_parse"] = (chosen["fields"] == fields
                                                      and chosen["label_conflicts"] == conflicts)
    name_ok = bool(fields is not None and fields.get(dp._NAME_LABEL))
    nt = chosen or {}
    _ident = dp._identify_name_table(soup)
    identity = {"problem": _ident["problem"], "name_table_count": _ident["name_table_count"],
                "populated_name_table_count": _ident["populated_name_table_count"]}
    return {
        "fields": fields,
        "label_conflicts": conflicts,
        "page_text_mentions_code": page_mentions,
        "page_text_code_snippets": code_snippets(soup.get_text(" "), code),
        "looks_like_moneydj": is_valid_moneydj_page(html),
        "table_count": len(soup.find_all("table")),
        "title_tag_html": str(soup.title) if soup.title is not None else None,
        "title_text": soup.title.get_text() if soup.title is not None else None,
        "name_table_candidate_count": len(candidates),
        "name_table_candidates": candidates[:NAME_TABLE_CANDIDATES_MAX],
        "name_table_candidates_truncated": len(candidates) > NAME_TABLE_CANDIDATES_MAX,
        "name_table": chosen,
        # ~~"would_be_ok_now"~~ → 改名（舊判準，見檔頭）
        "would_be_ok_old_rule": bool(name_ok and page_mentions),
        "identity_rule": identity,
        "would_be_ok_identity_rule": identity["problem"] is None,
        "would_be_ok_with_table_binding_own": bool(name_ok and nt.get("mentions_own")),
        "would_be_ok_with_table_binding_incl_nested": bool(name_ok and nt.get("mentions_incl_nested")),
    }


# ───────────────────────── 退避等待 ─────────────────────────

class _Waiter:
    """在請求前查退避；可等的冷卻（unreachable／server_error）在預算內等一次（每主機一次）。"""

    def __init__(self, backoff_check, sleep_fn, clock, deadline):
        self.backoff_check = backoff_check
        self.sleep_fn = sleep_fn
        self.clock = clock
        self.deadline = deadline
        self.waited_hosts: set = set()
        self.log: list = []

    def check(self, url: str, context: str) -> tuple[bool, float, str]:
        """→ (仍在冷卻, 剩餘秒數, 分類)。可等時先等再重查。"""
        skip, left, kind = self.backoff_check(url)
        if not skip:
            return False, 0.0, kind
        host = _host(url)
        left = float(left or 0.0)
        entry = {"host": host, "kind": kind, "remaining_sec": round(left, 1), "context": context,
                 "at": _now_iso(), "waited_sec": None, "skip_reason": None, "after": None}
        if kind not in WAITABLE_KINDS:
            entry["skip_reason"] = f"分類 {kind} 不等（只等 {sorted(WAITABLE_KINDS)}）"
        elif host in self.waited_hosts:
            entry["skip_reason"] = "此主機已等過一次"
        elif self.clock() + left + WAIT_PAD_SEC > self.deadline:
            entry["skip_reason"] = "超過等待預算"
        else:
            self.waited_hosts.add(host)
            wait = left + WAIT_PAD_SEC
            self.sleep_fn(wait)
            entry["waited_sec"] = round(wait, 1)
            skip, left, kind = self.backoff_check(url)
            entry["after"] = {"still_cooling": bool(skip), "kind": kind, "remaining_sec": round(float(left or 0), 1)}
        self.log.append(entry)
        return bool(skip), float(left or 0.0), kind


# ───────────────────────── 取數（只讀） ─────────────────────────

def probe_page(code: str, host: str, page: str, url: str, *, fetcher, pop_fail_kind, waiter,
               analyzer, secrets, probe_codes, before_send=None) -> tuple[dict, bool]:
    """取一個網址並分析。回 (紀錄, 是否真的發了請求)。失敗只記錄不拋。
    `before_send`：確定要發請求（不在冷卻中）時、發請求之前呼叫一次（用來 sleep）。"""
    rec = {"url": url, "host": host, "page_type": page, "requested_at": None,
           "responded_at": None, "outcome": None, "fail_kind": None,
           "http_status": None, "http_status_source": None, "final_url": None,
           "redirect_history": [], "content_type": None, "encoding": None,
           "content_length_bytes": None, "text_length": None,
           "raw_sha256": None, "raw_truncated": False, "raw_html_gzip_b64": None,
           "fetch_log": [], "parse": None, "parse_error": None, "error": None}
    skip, left, origin = waiter.check(url, f"page:{code}")
    if skip:
        rec.update(outcome="cooldown", fail_kind="cooldown", cooldown_origin_kind=origin,
                   error=f"host 冷卻中（當初分類 {origin}，剩餘約 {left:.0f} 秒），未發請求")
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
    except Exception as e:   # 讀回應文字拋例外 → exception（不算取到頁面）
        rec.update(outcome="exception", fail_kind="exception", http_status=getattr(r, "status_code", None),
                   http_status_source="response", error=_exc_record(e, secrets))
        return rec, True
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


def tdcc_matches(data, code: str, code_keys) -> list:
    """比中規則與 `declared_profile._fetch_tdcc_listing_cached` 相同：只看第一個非空代碼欄。"""
    out = []
    for item in data:
        if not isinstance(item, dict):
            continue
        key = next((k for k in code_keys if item.get(k)), "")
        if key and str(item.get(key)).upper() == code:
            out.append({"code_key": key, "row": item})
    return out


def tdcc_listing_extract(data, codes, code_keys=("基金代碼", "境外基金代碼"),
                         name_keys=("基金名稱",), full_max_b64=TDCC_FULL_MAX_B64_BYTES) -> dict:
    """TDCC 3-2 整份清單 → 總筆數、欄名、相關列，以及整份清單（gzip＋base64；太大改存精簡版）。"""
    if data is None:
        return {"available": False,
                "note": "sources._tdcc_cache 沒有 3-2，本探測不另發請求；失敗原文見 "
                        "public_calls[<代碼>].fetch_tdcc_listing.result 的 error 與 attempts"}
    if not isinstance(data, list):
        return {"available": False, "note": f"3-2 快取不是串列（{type(data).__name__}）"}
    dict_rows = [x for x in data if isinstance(x, dict)]
    columns = sorted({k for row in dict_rows for k in row})
    exact, loose = {}, {}
    for c in codes:
        exact[c] = tdcc_matches(data, c, code_keys)
        pat = code_pattern(c)
        hits = [row for row in dict_rows if any(pat.search(str(v)) for v in row.values() if v is not None)]
        loose[c] = {"count": len(hits), "rows": hits[:TDCC_RELATED_ROWS_MAX],
                    "truncated": len(hits) > TDCC_RELATED_ROWS_MAX}
    full_json = json.dumps(data, ensure_ascii=False).encode("utf-8")
    full_b64 = base64.b64encode(gzip.compress(full_json, mtime=0)).decode("ascii")
    if len(full_b64) <= full_max_b64:
        full = {"form": "full_json_gzip_b64", "b64_bytes": len(full_b64), "data": full_b64}
    else:
        slim = [{k: row.get(k) for k in tuple(code_keys) + tuple(name_keys)} if isinstance(row, dict)
                else {"non_dict_row": repr(row)[:80]} for row in data]
        slim_b64 = base64.b64encode(gzip.compress(json.dumps(slim, ensure_ascii=False).encode("utf-8"),
                                                  mtime=0)).decode("ascii")
        full = {"form": "slim_code_and_name_gzip_b64", "full_b64_bytes_estimate": len(full_b64),
                "kept_keys": list(code_keys) + list(name_keys), "b64_bytes": len(slim_b64), "data": slim_b64}
    return {"available": True, "total_rows": len(data), "dict_rows": len(dict_rows),
            "non_dict_rows": len(data) - len(dict_rows), "columns": columns,
            "code_keys_used_by_declared_profile": list(code_keys),
            "rows_matching_like_declared_profile": exact,
            "rows_mentioning_code_any_field": loose,
            "full_listing": full}


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


def _default_backoff_check(url: str):
    from infra import source_backoff as sb
    return sb.should_skip(sb.source_key(url))


def _default_tdcc_list():
    from repositories.fund import sources as _src
    return _src._tdcc_cache.get("3-2")


def _default_backoff_state():
    from infra import source_backoff as sb
    return sb.get_backoff_state()


def _default_public_specs(dp) -> list:
    """(名稱, 函式, 代碼→會打的網址, 代碼→這次會不會真的發請求)。`fetch_moneydj_basic_fields` 刻意不列。"""
    from repositories.fund import sources as _src
    return [
        ("fetch_tdcc_listing", dp.fetch_tdcc_listing, lambda c: dp._TDCC_URL,
         lambda c: dp._TDCC_EP not in _src._tdcc_cache),
        ("fetch_fundclear_declared_ccy", dp.fetch_fundclear_declared_ccy,
         lambda c: dp._FUNDCLEAR_URL_FMT.format(code=c), lambda c: True),
    ]


def run(codes, *, url_builder=None, fetcher=None, pop_fail_kind=None, backoff_check=None,
        analyzer=None, public_specs=None, tdcc_list_getter=None, backoff_state_getter=None,
        sleep_fn: Optional[Callable[[float], None]] = None, sleep_sec: float = SLEEP_SEC,
        clock: Optional[Callable[[], float]] = None, wait_budget_sec: float = WAIT_BUDGET_SEC,
        negative_control: Optional[str] = None,
        on_progress: Optional[Callable[[dict], None]] = None) -> dict:
    """取數 ＋ 分析全部代號，回報告 dict。所有依賴可注入，測試不打網路。
    `on_progress(report)`：每完成一個代碼的一步呼叫一次（`main` 用它覆寫報告檔）。"""
    dp = None
    if url_builder is None or fetcher is None or pop_fail_kind is None or public_specs is None:
        from repositories.fund import declared_profile as dp
    url_builder = url_builder or dp._moneydj_urls
    fetcher = fetcher or dp.fetch_url_with_retry
    pop_fail_kind = pop_fail_kind or dp._proxy.pop_last_fail_kind
    backoff_check = backoff_check or _default_backoff_check
    analyzer = analyzer or analyze_html
    public_specs = _default_public_specs(dp) if public_specs is None else public_specs
    tdcc_list_getter = tdcc_list_getter or _default_tdcc_list
    backoff_state_getter = backoff_state_getter or _default_backoff_state
    sleep_fn = sleep_fn or time.sleep
    clock = clock or time.monotonic
    if negative_control is None:
        negative_control = make_negative_control(time.time())
    on_progress = on_progress or (lambda r: None)
    secrets = _secret_literals()
    all_codes = order_codes(codes, negative_control)
    probe_codes = tuple(all_codes)
    waiter = _Waiter(backoff_check, sleep_fn, clock, clock() + wait_budget_sec)

    report = {
        "complete": False,
        "progress": None,
        "generated_at_utc": _now_iso(),
        "purpose": "驗證 declared_profile.fetch_moneydj_basic_fields 的解析，以及「代碼以詞界出現在含『基金名稱』"
                   "那張表自身文字」能否作為 C2 身分綁定規則",
        "network_path": NETWORK_PATH_NOTE,
        "url_source": "repositories.fund.declared_profile._moneydj_urls",
        "fetch_call": f"declared_profile.fetch_url_with_retry(url, timeout={FETCH_TIMEOUT}, retries={FETCH_RETRIES})",
        "order": "第一個實際代碼 → 負控 → 其餘；第一輪各代碼首選頁型網址，第二輪次要頁型網址",
        "sleep_sec_between_requests": sleep_sec,
        "wait_policy": {"waitable_kinds": sorted(WAITABLE_KINDS), "per_host_max_waits": 1,
                        "budget_sec": wait_budget_sec, "pad_sec": WAIT_PAD_SEC},
        "codes_in_order": all_codes,
        "negative_control": {"code": negative_control, "rule": NEGATIVE_CONTROL_RULE,
                             "note": "本輪生成的負控值，屬資料產出、不作為掃描用字表"},
        "proxy_env_set": bool(os.environ.get("PROXY_URL", "").strip()),
        "proxy_used_by_infra": _proxy_used_by_infra(),
        "github_run_id": _env_or_none("GITHUB_RUN_ID"),
        # 觸發 SHA（按鈕分支那顆）≠ 實際執行的程式碼；後者看 executed_sha（同 probe_fx_obs_date）。
        "trigger_sha": _env_or_none("GITHUB_SHA"),
        "executed_sha": _env_or_none("PROBE_EXECUTED_SHA"),
        "event_name": _env_or_none("GITHUB_EVENT_NAME"),
        "pages": {c: [] for c in all_codes},
        "url_builder_errors": {},
        "public_calls": {},
        "waits": waiter.log,
        "tdcc_3_2_extract": None,
        "backoff_state_end": None,
    }

    plans = {}
    for code in all_codes:
        try:
            urls = list(url_builder(code))
        except Exception as e:
            report["url_builder_errors"][code] = _exc_record(e, secrets)
            urls = []
        first_page = urls[0][1] if urls else None
        plans[code] = ([u for u in urls if u[1] == first_page], [u for u in urls if u[1] != first_page])

    sent = {"any": False}

    def _before():
        if sent["any"]:
            sleep_fn(sleep_sec)
        sent["any"] = True

    # 第一輪（首選頁型）→ 第二輪（次要頁型）：先廣後深。
    for rnd in (0, 1):
        for code in all_codes:
            for host, page, url in plans[code][rnd]:
                rec, _s = probe_page(code, host, page, url, fetcher=fetcher, pop_fail_kind=pop_fail_kind,
                                     waiter=waiter, analyzer=analyzer, secrets=secrets,
                                     probe_codes=probe_codes, before_send=_before)
                rec["round"] = rnd + 1
                report["pages"][code].append(rec)
            report["progress"] = f"pages round {rnd + 1} done: {code}"
            on_progress(report)

    # 公開函式（TDCC、FundClear）；確實要發請求才 sleep。
    for code in all_codes:
        calls = {}
        for name, fn, url_for, will_request in public_specs:
            try:
                url = url_for(code)
                req = bool(will_request(code))
            except Exception as e:
                calls[name] = {"exception": _exc_record(e, secrets), "result": None}
                continue
            if req:
                skip, _left, _kind = waiter.check(url, f"public:{name}:{code}")
                if not skip:
                    _before()
            calls[name] = _call_public(fn, code, secrets)
        report["public_calls"][code] = calls
        report["progress"] = f"public calls done: {code}"
        on_progress(report)

    try:
        from repositories.fund import declared_profile as _dp2
        keys = tuple(_dp2._TDCC_CODE_KEYS)
    except Exception:
        keys = ("基金代碼", "境外基金代碼")
    try:
        report["tdcc_3_2_extract"] = tdcc_listing_extract(tdcc_list_getter(), all_codes, code_keys=keys)
    except Exception as e:
        report["tdcc_3_2_extract"] = {"available": False, "error": _exc_record(e, secrets)}
    try:
        report["backoff_state_end"] = backoff_state_getter()
    except Exception as e:
        report["backoff_state_end"] = {"error": _exc_record(e, secrets)}
    report["summary"] = summarize(report)
    report["complete"] = True
    report["progress"] = "complete"
    return report


def summarize(report: dict) -> dict:
    """逐代碼的精簡摘要（判讀仍以完整欄位為準）。"""
    out = {}
    neg = (report.get("negative_control") or {}).get("code")
    fetched_real = fetched_neg = 0
    for code, recs in report.get("pages", {}).items():
        rows = []
        for r in recs:
            p = r.get("parse") or {}
            nt = p.get("name_table") or {}
            if r.get("outcome") == "fetched":
                if code == neg:
                    fetched_neg += 1
                else:
                    fetched_real += 1
            rows.append({
                "url": r.get("url"), "round": r.get("round"), "outcome": r.get("outcome"),
                "http_status": r.get("http_status"), "len": r.get("content_length_bytes"),
                "name_table_candidates": p.get("name_table_candidate_count"),
                "page_mentions": p.get("page_text_mentions_code"),
                "table_mentions_own": nt.get("mentions_own"),
                "table_mentions_incl_nested": nt.get("mentions_incl_nested"),
                "would_be_ok_old_rule": p.get("would_be_ok_old_rule"),
                "would_be_ok_identity_rule": p.get("would_be_ok_identity_rule"),
                "would_be_ok_with_table_binding_own": p.get("would_be_ok_with_table_binding_own"),
                "would_be_ok_with_table_binding_incl_nested": p.get("would_be_ok_with_table_binding_incl_nested"),
            })
        pub = (report.get("public_calls", {}).get(code) or {})
        out[code] = {"pages": rows,
                     "public_status": {k: ((v.get("result") or {}).get("status")
                                           if v.get("exception") is None else "exception")
                                       for k, v in pub.items()}}
    return {"per_code": out, "fetched_page_count_real": fetched_real,
            "fetched_page_count_negative_control": fetched_neg, "wait_count": len(report.get("waits") or [])}


def _summary_lines(report: dict) -> list:
    s = report.get("summary") or {}
    lines = [f"proxy_env_set={report['proxy_env_set']} proxy_used_by_infra={report['proxy_used_by_infra']}",
             f"網路路徑：{report['network_path']}",
             f"負控規則：{report['negative_control']['rule']}",
             f"fetched 頁數：實際代碼={s.get('fetched_page_count_real')} 負控={s.get('fetched_page_count_negative_control')}"
             f" 冷卻紀錄={s.get('wait_count')}"]
    for code, v in (s.get("per_code") or {}).items():
        cells = [f"{r['outcome']}/{r['http_status']}/候選表={r['name_table_candidates']}/頁提={r['page_mentions']}"
                 f"/表提(自身)={r['table_mentions_own']}" for r in v["pages"]]
        lines.append(f"{code}: {' | '.join(cells)} || 公開函式={v['public_status']}")
    return lines


def _dump(report: dict) -> tuple[str, Optional[str]]:
    """嚴格 JSON（NaN／±inf→null、allow_nan=False）；寫不出時保底寬鬆寫出並回錯誤原文。"""
    try:
        return json.dumps(to_strict_json(report), ensure_ascii=False, indent=1, allow_nan=False), None
    except (ValueError, TypeError) as e:
        err = f"{type(e).__name__}: {e}"
        loose = dict(report, strict_json_error=err)
        return json.dumps(loose, ensure_ascii=False, indent=1, allow_nan=True, default=str), err


def write_report(report: dict, out: Path) -> Optional[str]:
    """覆寫報告檔（先寫暫存檔再改名，避免逾時中斷留下半個檔）。回嚴格 JSON 錯誤原文或 None。"""
    text, err = _dump(report)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".tmp")
    try:
        tmp.write_text(text + "\n", encoding="utf-8")
        os.replace(tmp, out)
    finally:
        # 寫到一半失敗時不留半個 .tmp（成功時 os.replace 已把它改名，這裡什麼都不做）。
        with contextlib.suppress(OSError):
            if tmp.exists():
                tmp.unlink()
    return err


def main(argv=None, **run_kwargs) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="報告輸出路徑（JSON）")
    args = ap.parse_args(argv)
    out = Path(args.out)

    report = run(PROBE_CODES, on_progress=lambda r: write_report(r, out), **run_kwargs)
    strict_error = write_report(report, out)
    for line in _summary_lines(report):
        print(line)
    print(f"報告：{out}")
    if strict_error:
        print(f"⚠️ 報告不是嚴格 JSON（已以寬鬆格式寫出）：{strict_error}")
        return 1
    return 0 if (report.get("summary") or {}).get("fetched_page_count_real") else 1


if __name__ == "__main__":
    sys.exit(main())
