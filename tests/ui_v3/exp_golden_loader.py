# -*- coding: utf-8 -*-
"""🔍 找基金：golden fixture 離線 loader 輔助（B-EXP-GOLDEN-OFFLINE-S1；**僅 tests，不進 production**）。

用途：證明「L1 `declared_profile.fetch_moneydj_basic_fields`（真解析碼）→ L2 `exp_profile.build_profiles`（真組裝碼）→
ui_v3 adapter `lookup_fund` → 五欄卡」在**完全離線**、以 `tests/fixtures/moneydj_basic/` 的**真實 MoneyDJ 頁面位元組**為輸入時可通。

⚠️ 邊界（逐條可由 `test_ui_v3_exp_golden_offline_wiring.py` 驗）：
- 網路層只有一個替身：`declared_profile.fetch_url_with_retry` → 依網址回 golden 位元組或指定失敗（不經 `infra.proxy`、不讀 secrets／NAS）。
- TDCC、FundClear 兩支 L1 以離線替身取代（`build_profiles` 固定三來源都查）；adapter 不讀它們的結果。
- 取數鍵不經 `resolve_full_keys`／別名表／ISIN：以手寫的 `key_results` 直接餵 `build_profiles`（身分契約 D2 不在本切片）。
- 本檔只在 `tests/`；production 不得 import 本檔、不得引用 `tests/fixtures`。
- 這是 **golden 離線證明**，不是真來源接線：真實來源行為、真實傳輸（NAS／TLS）、Cloud 均 NOT VERIFIED。
"""
from __future__ import annotations

import gzip
import hashlib
import json
import pathlib
from datetime import datetime, timezone
from typing import Callable, Dict, Optional

import infra.proxy as proxy_mod
import repositories.fund.declared_profile as dp
from repositories.fund import sources as src
from services.v2_tables import exp_profile as ep

FIX_DIR = pathlib.Path(__file__).resolve().parents[1] / "fixtures" / "moneydj_basic"
TCB = "tcbbankfund.moneydj.com"
WWW = "www.moneydj.com"

#: 固定的「台灣今天」來源（`build_profiles(now=...)`）：不用當下時間補任何值。
FIXED_NOW = datetime(2026, 11, 22, 0, 0, tzinfo=timezone.utc)

#: 報告實測的四欄原字面與 L2 對照後的預期（代碼 → (首選頁型, 名稱, 配息頻率原字面, 成立日期原字面)）。
#: 與 `tests/test_declared_profile.py::GOLDEN` 同源（manifest 的真實代碼）；本檔另存一份是因為該檔不可被 import，
#: 且由 `test_golden_expectations_match_manifest_and_bytes` 以 fixture 位元組實際解析核對，不靠抄寫。
GOLDEN_CODES = ("ACCP138", "ACTI71", "JFZN3", "JFZA6", "JFZA5", "JFZA3", "JFZK2", "TLZF9")


def fixture_path(name: str) -> pathlib.Path:
    return FIX_DIR / name


def fixture_bytes(name: str) -> bytes:
    return gzip.decompress(fixture_path(name).read_bytes())


def fixture_html(name: str, code: str = "") -> str:
    """同 requests 對 MoneyDJ 的解碼（big5，`errors="replace"`）；負控頁的 `__CODE__` 換成呼叫端現編的代碼。"""
    text = fixture_bytes(name).decode("big5", errors="replace")
    return text.replace("__CODE__", code) if code else text


def manifest() -> dict:
    return json.loads((FIX_DIR / "manifest.json").read_text(encoding="utf-8"))


def sha256_of(name: str) -> str:
    return hashlib.sha256(fixture_bytes(name)).hexdigest()


#: 各代碼「資料所在的首選頁型」（探測報告實測：境外預設序先試 yp011001，部分代碼的資料頁是 yp011000）。
#: 與 `tests/test_declared_profile.py::GOLDEN` 同源；`test_preferred_pages_exist_in_manifest` 核對兩種頁型的檔都在。
PREFERRED_PAGE = {"ACCP138": "yp011000", "ACTI71": "yp011000", "JFZN3": "yp011001", "JFZA6": "yp011001",
                  "JFZA5": "yp011001", "JFZA3": "yp011001", "JFZK2": "yp011001", "TLZF9": "yp011001"}


def preferred_page(code: str) -> str:
    """該代碼資料所在的首選頁型（yp011000／yp011001）。"""
    return PREFERRED_PAGE[code]


def other_page(page_type: str) -> str:
    return {"yp011000": "yp011001", "yp011001": "yp011000"}[page_type]


def mdj_url(host: str, page_type: str, code: str) -> str:
    return f"https://{host}/funddj/yp/{page_type}.djhtm?a={code}"


# ───────────────────────── 離線網路替身（唯一的取數入口） ─────────────────────────

class _Resp:
    def __init__(self, text: str, url: str):
        self.text = text
        self.url = url
        self.history: list = []

    def json(self):
        return json.loads(self.text)


class OfflineNet:
    """依網址回應的 `fetch_url_with_retry` 替身；`calls` 逐筆記錄被請求的網址。

    routes：url → ("html", str) | ("fail", kind) | ("empty",)。未登錄的網址 → 404 類失敗（不是 raise，不是真請求）。
    """

    def __init__(self, routes: Dict[str, tuple]):
        self.routes = dict(routes)
        self.calls: list = []

    def __call__(self, url, headers=None, params=None, timeout=20, retries=3, sleep_sec=2):
        self.calls.append(url)
        proxy_mod._TLS_FAIL.kind = ""                       # 同 `infra.proxy.fetch_url`：進場先清
        spec = self.routes.get(url, ("fail", "not_found"))
        if spec[0] == "html":
            return _Resp(spec[1], url)
        if spec[0] == "fail":
            proxy_mod._TLS_FAIL.kind = spec[1]
            return None
        return None                                         # empty：200 但內文空


def golden_routes(code: str, *, override: Optional[Dict[str, tuple]] = None) -> Dict[str, tuple]:
    """照報告實測：tcbbankfund 兩頁型 404、www 兩頁型回 fixture。`override`：url → spec，覆蓋預設。"""
    pref = preferred_page(code)
    sec = other_page(pref)
    routes = {
        mdj_url(TCB, pref, code): ("fail", "not_found"),
        mdj_url(TCB, sec, code): ("fail", "not_found"),
        mdj_url(WWW, pref, code): ("html", fixture_html(f"moneydj_{code}_{pref}.html.gz")),
        mdj_url(WWW, sec, code): ("html", fixture_html(f"moneydj_{code}_{sec}.html.gz")),
    }
    routes.update(override or {})
    return routes


# ───────────────────────── 另外兩個來源的離線替身 ─────────────────────────

def offline_tdcc(_full_key: str) -> dict:
    """TDCC 離線替身：不連線；回「未收錄」。adapter 不讀此來源。"""
    return {"status": dp.STATUS_NOT_LISTED, "fields": {}, "error": None, "cooling": False, "cooling_remaining_sec": None}


def offline_fundclear(_full_key: str) -> dict:
    """FundClear 離線替身：不連線；回「未收錄」。adapter 不讀此來源。"""
    return {"status": dp.STATUS_NOT_LISTED, "fields": {}, "error": None, "cooling": False, "cooling_remaining_sec": None}


# ───────────────────────── 隔離（測試前後都清；不留快取／失敗記憶） ─────────────────────────

def reset_l1_state() -> None:
    for fn in (dp.fetch_moneydj_basic_fields, dp.fetch_tdcc_listing, dp.fetch_fundclear_declared_ccy):
        fn.cache_clear()
    dp.clear_failure_memory()
    dp._TDCC_OBSERVED.clear()


# ───────────────────────── loader：adapter 的注入點 ─────────────────────────

class GoldenLoader:
    """`lookup_fund(loader, raw)` 的 loader：query_text →（真 L1 MoneyDJ 解析 ＋ 真 L2 `build_profiles`）→ L2 回傳 dict。

    - `key_ok=False`：模擬 L2 拒絕該鍵（取數鍵不被接受 → `source_status` 為空 → adapter 判 BLOCKED／key_rejected）。
    - `tamper`：`result -> result`，在回傳給 adapter 前改動 L2 回傳（只供「契約破壞」「分歧格」負控；預設不改）。
    - `calls`：被呼叫時收到的 query_text（攔截案例必須為空）。
    """

    def __init__(self, *, key_ok: bool = True, tamper: Optional[Callable[[dict], dict]] = None):
        self.key_ok = key_ok
        self.tamper = tamper
        self.calls: list = []

    def __call__(self, query_text: str) -> dict:
        self.calls.append(query_text)
        entry = ({"input": query_text, "ok": True, "full_key": query_text} if self.key_ok
                 else {"input": query_text, "ok": False, "error": "offline golden: key rejected"})
        fetchers = {"MoneyDJ": dp.fetch_moneydj_basic_fields, "TDCC": offline_tdcc, "FundClear": offline_fundclear}
        result = ep.build_profiles({"results": [entry]}, fetchers=fetchers, now=FIXED_NOW)
        return self.tamper(result) if self.tamper is not None else result


def real_is_domestic() -> Callable:
    """模組載入時的真 `_is_domestic_code`（供測試還原：L1 預設頁序依它決定；golden 代碼皆境外）。"""
    return src._is_domestic_code
