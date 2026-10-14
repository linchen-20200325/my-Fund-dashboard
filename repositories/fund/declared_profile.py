"""repositories/fund/declared_profile.py — 基金「來源自報」基本資料取數（L1，exp 正式模式批 C 的 C1）。

只做一件事：把三個**既有**來源對某一檔基金「自己寫了什麼」原樣交出來，附出處、取得時間、
逐網址的嘗試紀錄與失敗原文。**不新增來源、不新增 API、不正規化、不推斷、不補值。**

三支公開函式（都回 dict，都帶 `status`）：

1. `fetch_moneydj_basic_fields(full_key)` —— MoneyDJ 基本資料頁 yp011000／yp011001（status ∈ {ok, failed}）。
2. `fetch_tdcc_listing(full_key)` —— TDCC OpenAPI 3-2（境外基金基本資料清單）（status ∈ {ok, not_listed, failed}）。
3. `fetch_fundclear_declared_ccy(full_key)` —— FundClear `GetFundBasicInfo`（`_src_fundclear_meta` 用的同一支）
   （status ∈ {ok, not_listed, failed}）。

## 客戶裁示（本檔的邊界，逐條落在程式裡）

- 幣別只取來源**自報**的值，可追溯；**不從名稱或代碼推斷**。本檔沒有任何一行看基金名稱或代碼去猜幣別。
- 成立日期只讀 MoneyDJ 基本資料頁的「成立日期」欄；**FundClear 那串猜鍵名的 or 鏈不使用**
  （`fetch_fundclear_declared_ccy` 完全不碰成立日期）。
- 「最高經理費」**不讀**：MoneyDJ 解析只保留四個標籤，其餘標籤（含「最高經理費(%)」）連存都不存。
- 缺值一律 `None`，不填 0、不填空字串、不用寫死的備援、不靜默換來源。
- 幣別字面**不在 L1 正規化**（「美元」「USD」「美金」照原字交出），交給 L2。

## status 的意思

- `ok`：來源有這一檔，且讀到了它的資料（各欄仍可能是 `None`＝來源沒寫或來源自相矛盾）。
- `not_listed`：來源**明確**回答沒有這一檔（判準見各函式）。**MoneyDJ 目前一律不判 not_listed**（見該函式）。
- `failed`：取不到、或取到的東西無法判讀。**只要有一次無法判讀，就不得升格成 not_listed。**

## 快取與失敗記憶

- 成功快取：內層 `@_ttl_cache(TTL_1HOUR, cache_if=只收 ok／not_listed)` 並 `register_cache`，再交深拷貝
  （同 `fund_orchestration._deepcopy_result` 的做法）。命中快取時交出的是**當初那一份**，
  `fetched_at`／`observed_at` 不會變成當下時間。
- 代碼先正規化（去頭尾空白、轉大寫）再進快取：`" tlzf9"` 與 `"TLZF9"` 共用同一格。
- 失敗記憶：failed 結果另記 `FAILURE_MEMORY_SEC` 秒（理由見該常數）。記憶期間再呼叫**不發請求**，
  交回上一次的 failed 結果（原文、嘗試紀錄、時刻原樣），加 `cooling=True` 與 `cooling_remaining_sec`。
  以 `register_cache` 登記一個清除用的物件（`clear_all_caches()` 會清到），另有 `clear_failure_memory()`。

⚠️ 本檔的 HTML 標籤結構與 JSON 鍵名**未以真實回應樣本驗證**（repo 內沒有這三個來源的原始回應，
本環境也連不到）；判準是照 repo 既有解析碼（`_src_tcb_meta`／`_src_tdcc_meta`／`_src_fundclear_meta`）寫的。

⚠️ 已知的舊殼模式（只登記、不在本檔處理，見 docs/v2/49 第 8 節）：本檔經由 `fund_fetcher` 取用
`fetch_url_with_retry`，而 `fund_fetcher` 在 import 時會間接載入 streamlit 與 services。
"""
from __future__ import annotations

import copy as _copy
import functools as _functools
import re as _re
import threading as _threading
import time as _time
from datetime import datetime, timezone

from bs4 import BeautifulSoup

import infra.proxy as _proxy
import infra.source_backoff as _sb
from fund_fetcher import fetch_url_with_retry, is_valid_moneydj_page
from infra.cache import _ttl_cache, register_cache
from repositories.fund import sources as _src
from shared.ttls import TTL_1HOUR, TTL_5MIN

__all__ = [
    "STATUS_OK", "STATUS_NOT_LISTED", "STATUS_FAILED",
    "MONEYDJ_LABELS", "MONEYDJ_HOSTS", "FAILURE_MEMORY_SEC",
    "fetch_moneydj_basic_fields", "fetch_tdcc_listing", "fetch_fundclear_declared_ccy",
    "clear_failure_memory",
]

STATUS_OK = "ok"
STATUS_NOT_LISTED = "not_listed"
STATUS_FAILED = "failed"
_CACHEABLE_STATUSES = frozenset({STATUS_OK, STATUS_NOT_LISTED})

#: failed 結果的短期記憶秒數。
#: 理由：failed 不進 1 小時成功快取（下次要能拿到真答案），而 404／407 依
#: `shared/backoff_policy.NO_COOLDOWN_KINDS` 不冷卻 —— 兩者疊在一起，每次 Streamlit rerun 都會重打
#: 全部網址（稽核 N-2 實測：5 次呼叫打出 20 個請求）。5 分鐘遠短於成功 TTL（1 小時），
#: 來源恢復後最多晚 5 分鐘拿到真答案；與退避的 `server_error` 冷卻同量級，不另立新秒數。
FAILURE_MEMORY_SEC: int = TTL_5MIN

#: 只收字面**完全相同**（去頭尾空白後）的四個標籤。「設立日期」「成立日」等近似字不收。
#: ⛔ 「最高經理費」不在此列，也不得加入：客戶裁示它不能冒充經理費率，本檔一律不讀。
MONEYDJ_LABELS: tuple[str, ...] = ("基金名稱", "計價幣別", "配息頻率", "成立日期")
_NAME_LABEL = "基金名稱"

#: 每種頁型依序試的兩個 host（與 `fund_orchestration` 舊鏈、`_src_tcb_meta` 同序）。
MONEYDJ_HOSTS: tuple[str, ...] = ("tcbbankfund.moneydj.com", "www.moneydj.com")
_DOMESTIC_INFO_PAGE = "yp011000"
_OFFSHORE_INFO_PAGE = "yp011001"

_TDCC_EP = "3-2"
_TDCC_URL = f"https://openapi.tdcc.com.tw/v1/opendata/{_TDCC_EP}"
#: 比對代碼的欄名與順序同 `sources._src_tdcc_meta`（先「基金代碼」再「境外基金代碼」）。
_TDCC_CODE_KEYS: tuple[str, ...] = ("基金代碼", "境外基金代碼")
#: `_tdcc_get` 例外原文的開頭若是這些型別 → 有回應但內容不是可用的 JSON。
_TDCC_BAD_PAYLOAD_EXC: tuple[str, ...] = ("JSONDecodeError", "UnicodeDecodeError")

_FUNDCLEAR_URL_FMT = ("https://www.fundclear.com.tw/SmartFundAPI/api/FundAjax"
                      "/GetFundBasicInfo?FundCode={code}")
#: 幣別鍵：只在 `Data` 裡找，順序同 `_src_fundclear_meta`（`Currency` 先、`currency` 後）。
_FUNDCLEAR_CCY_KEYS: tuple[str, ...] = ("Currency", "currency")
_FUNDCLEAR_CODE_KEYS: tuple[str, ...] = ("FundCode", "fundCode")
#: 錯誤旗標鍵（保守推定：repo 內沒有 FundClear 錯誤回應樣本，鍵名照 .NET Web API 常見慣例）。
_FUNDCLEAR_SUCCESS_KEYS: tuple[str, ...] = ("Success", "success", "IsSuccess", "isSuccess")
_FUNDCLEAR_MESSAGE_KEYS: tuple[str, ...] = ("Message", "message")

_CODE_RE = _re.compile(r"^[A-Za-z0-9]+(?:-[A-Za-z0-9]+)?$")
_HTTP_STATUS_RE = _re.compile(r"HTTP Error (\d{3})")


def _now_iso() -> str:
    """實際時刻（UTC ISO-8601）。獨立成函式，測試才能讓時間前進、驗證命中快取時不被改寫。"""
    return datetime.now(timezone.utc).isoformat()


#: 失敗記憶用的時鐘（monotonic；同 `infra.source_backoff._clock`）。模組層變數讓測試能注入假時鐘。
_clock = _time.monotonic


def _normalize_code(full_key) -> str:
    """呼叫端契約：`full_key` 必須是代碼字串。不合格直接 raise（§1），不打任何網路、不進快取。"""
    if not isinstance(full_key, str):
        raise TypeError(f"full_key 必須是字串，收到 {type(full_key).__name__}")
    code = full_key.strip().upper()
    if not _CODE_RE.match(code):
        raise ValueError(f"full_key {full_key!r} 不是代碼形狀（英數，可帶一個 '-' 後綴）")
    return code


def _cacheable(result) -> bool:
    """`_ttl_cache(cache_if=...)`：只快取 ok 與 not_listed；failed 交給失敗記憶（較短）。"""
    return isinstance(result, dict) and result.get("status") in _CACHEABLE_STATUSES


def _deepcopy_result(fn):
    """每次交出深拷貝（命中與未命中都是）。`wraps` 帶出內層的 `cache_clear()`／`cache_info()`。"""
    @_functools.wraps(fn)
    def wrapper(*args, **kwargs):
        return _copy.deepcopy(fn(*args, **kwargs))
    return wrapper


def _cooldown(url: str):
    """查 host 是否在退避冷卻中 → `(skip, 當初的失敗分類)`。在冷卻中就一個封包都不發。"""
    skip, _left, kind = _sb.should_skip(_sb.source_key(url))
    return bool(skip), kind


# ── 失敗記憶 ─────────────────────────────────────────────────────────
#: (函式名, 正規化代碼) → (記下的時刻, failed 結果的深拷貝)
_FAILURE_MEMORY: dict = {}
_FAILURE_LOCK = _threading.Lock()


class _FailureMemoryCache:
    """給 `infra.cache` 的登記物件：`clear_all_caches()` 會呼叫 `cache_clear()`。
    `cache_info()` 照 `infra/cache.py` 的欄位契約只交 `name`／`size`（沒有命中率統計 —— 不湊 0）。"""

    __name__ = "declared_profile_failure_memory"

    def cache_clear(self) -> None:
        with _FAILURE_LOCK:
            _FAILURE_MEMORY.clear()

    def cache_info(self) -> dict:
        with _FAILURE_LOCK:
            return {"name": self.__name__, "size": len(_FAILURE_MEMORY), "ttl_sec": FAILURE_MEMORY_SEC}


_FAILURE_MEMORY_REGISTERED = register_cache(_FailureMemoryCache())


def clear_failure_memory() -> None:
    """清掉三支函式的失敗記憶（成功快取不動；要一起清請用各函式的 `cache_clear()`）。"""
    _FAILURE_MEMORY_REGISTERED.cache_clear()


def _public(cached_fn):
    """公開入口：正規化代碼 → 失敗記憶 → 成功快取（內層）。"""
    name = cached_fn.__name__.removeprefix("_").removesuffix("_cached")

    @_functools.wraps(cached_fn)
    def wrapper(full_key):
        code = _normalize_code(full_key)
        key = (name, code)
        now = _clock()
        with _FAILURE_LOCK:
            hit = _FAILURE_MEMORY.get(key)
            if hit is not None and now - hit[0] >= FAILURE_MEMORY_SEC:
                _FAILURE_MEMORY.pop(key, None)
                hit = None
        if hit is not None:
            out = _copy.deepcopy(hit[1])
            out["cooling"] = True
            out["cooling_remaining_sec"] = round(FAILURE_MEMORY_SEC - (now - hit[0]), 1)
            return out
        result = cached_fn(code)
        if result.get("status") == STATUS_FAILED:
            with _FAILURE_LOCK:
                _FAILURE_MEMORY[key] = (now, _copy.deepcopy(result))
        result["cooling"] = False
        result["cooling_remaining_sec"] = None
        return result

    def _clear():
        cached_fn.cache_clear()
        with _FAILURE_LOCK:
            for k in [k for k in _FAILURE_MEMORY if k[0] == name]:
                _FAILURE_MEMORY.pop(k, None)

    wrapper.__name__ = name
    wrapper.cache_clear = _clear              # type: ignore[attr-defined]
    wrapper.cache_info = cached_fn.cache_info  # type: ignore[attr-defined]
    return wrapper


# ═════════════════════════════════════════════════════════════════════
# 1. MoneyDJ 基本資料頁
# ═════════════════════════════════════════════════════════════════════

def _cell_text(cell) -> str:
    return cell.get_text().strip()


def _own_rows(tbl) -> list:
    """表格**自己的**列：直接子 `tr`，以及直接子 `thead`／`tbody`／`tfoot` 底下的直接子 `tr`。
    不遞迴，內層巢狀表的列不會被算進外層表。"""
    rows = list(tbl.find_all("tr", recursive=False))
    for sec in tbl.find_all(["thead", "tbody", "tfoot"], recursive=False):
        rows.extend(sec.find_all("tr", recursive=False))
    return rows


def _parse_label_table(soup) -> "tuple[dict | None, list[dict]]":
    """找第一張含「基金名稱」那一列（標籤字面完全相同、值非空）的表，只收 `MONEYDJ_LABELS` 四個標籤。

    列配對同 `sources._src_tcb_meta`：恰 2 格 → (0,1)；4 格以上 → (0,1)(2,3)…；其餘格數不收。
    與它不同的地方（刻意的）：
    - 標籤比對用**完全相同**（去頭尾空白後），不是子字串；
    - 只看表格自己的列（`_own_rows`）與列的**直接子** `td`，巢狀表不會串進外層；
    - 同一標籤出現兩次且值不同 → 該欄設 `None`，兩個值記進 conflicts（不取第一個、不取最後一個）。
    回傳 `(fields 或 None, conflicts)`；fields 的值是原始字面，標籤沒出現或自相矛盾 → `None`。
    """
    for tbl in soup.find_all("table"):
        seen: dict = {}
        for row in _own_rows(tbl):
            cells = row.find_all("td", recursive=False)
            if len(cells) == 2:
                pairs = [(cells[0], cells[1])]
            elif len(cells) >= 4:
                pairs = [(cells[i], cells[i + 1]) for i in range(0, len(cells) - 1, 2)]
            else:
                continue
            for k_cell, v_cell in pairs:
                label = _cell_text(k_cell)
                if label not in MONEYDJ_LABELS:
                    continue          # 其他標籤（含「最高經理費」）不讀、不存
                values = seen.setdefault(label, [])
                value = _cell_text(v_cell)
                if value not in values:
                    values.append(value)
        if any(v for v in seen.get(_NAME_LABEL, [])):
            fields = {lb: (seen[lb][0] if len(seen.get(lb, [])) == 1 else None) for lb in MONEYDJ_LABELS}
            conflicts = [{"label": lb, "values": list(seen[lb])}
                         for lb in MONEYDJ_LABELS if len(seen.get(lb, [])) > 1]
            return fields, conflicts
    return None, []


def _mentions_code(soup, code: str) -> bool:
    """頁面**可見文字**是否以完整詞提到該代碼（大小寫不分）。
    只看 `get_text()`（不含 href 等屬性值），前後不得緊接英數字：查 `TLZF9` 不會被 `TLZF90` 命中。"""
    pat = _re.compile(rf"(?<![A-Za-z0-9]){_re.escape(code)}(?![A-Za-z0-9])", _re.IGNORECASE)
    return bool(pat.search(soup.get_text(" ")))


def _moneydj_urls(code: str) -> list:
    first = _DOMESTIC_INFO_PAGE if _src._is_domestic_code(code) else _OFFSHORE_INFO_PAGE
    second = _OFFSHORE_INFO_PAGE if first == _DOMESTIC_INFO_PAGE else _DOMESTIC_INFO_PAGE
    return [(host, page, f"https://{host}/funddj/yp/{page}.djhtm?a={code}")
            for page in (first, second) for host in MONEYDJ_HOSTS]


@_deepcopy_result
@register_cache
@_ttl_cache(ttl_sec=TTL_1HOUR, maxsize=256, cache_if=_cacheable)
def _fetch_moneydj_basic_fields_cached(code: str) -> dict:
    """MoneyDJ 基本資料頁的四個自報欄位：「基金名稱」「計價幣別」「配息頻率」「成立日期」（原字面）。

    網址順序：先依 `sources._is_domestic_code(code)` 選首選頁型（境內 yp011000、境外 yp011001），
    再試另一種；每種頁型依序試 tcbbankfund、www 兩個 host，最多 4 個網址。

    ⛔ **不沿用舊鏈「長度 > 500 就停」**（`fund_orchestration.fetch_fund_from_moneydj_url` 基本資料段）：
    一頁長度夠但只是空殼時，舊鏈會停在它身上、讀不到任何欄位。本函式一路試到
    「讀到含『基金名稱』那一列的表，**且**頁面可見文字以完整詞提到該代碼」為止。
    `is_valid_moneydj_page` 靠不住（`sources._src_allianzgi_meta` 自註：任兩個常見中文詞就回 True），
    本函式只拿它記進嘗試紀錄的說明，從不用它判定任何 status。

    ⚠️ 表格與代碼**仍未綁定**：只確認「頁面可見文字提到該代碼」＋「頁面上有一張含基金名稱的表」，
    沒有確認那張表就是該代碼的表（真實頁面結構未以樣本驗證）。

    逐網址結果（`attempts[i]["outcome"]`）：
    - `ok`：有表、可見文字有代碼 → 採用並停止；
    - `not_found_404`：HTTP 404；
    - `unrecognized_page`：取回但無法判讀（空殼、維護頁、有表沒代碼、有代碼沒表、基金名稱自相矛盾）；
    - `cooldown`：host 冷卻中，沒有發請求；`fail_kind="cooldown"`，當初的分類記在 `cooldown_origin_kind`；
    - `http_failed`：逾時／403／429／5xx／407，分類取自 `infra.proxy.pop_last_fail_kind()`；
    - `empty_response`：200 但內文為空（`fetch_url_with_retry` 回 None 且沒有失敗分類）；
    - `exception`：取數或解析拋例外（原文記在 detail）。

    ~~status：任一網址 ok → `ok`；4 個網址**全部**屬「確定沒有」→ `not_listed`；其餘 → `failed`。~~
    ~~（「確定沒有」＝ 404，或正常頁但既沒有該代碼也沒有表）~~
    → **2026-10-14 有意識的更正，不是漏刪**（決策者：AI 總管；依據：稽核 M 的實跑反例 ——
    4 個網址都回空殼頁、或都回含「基金 淨值 績效」字樣的「系統維護中」頁、或 tcb 兩個 404 加 www 兩個空殼，
    舊判準都會判成 not_listed 並快取 1 小時，把「打失敗」說成「沒有這一檔」）。
    舊句的用意（來源明確說沒有時要能分辨）仍然成立；被權衡掉的是它的判準 —— 沒有真實的「查無此基金」頁面樣本，
    「正常頁」與 404 都證明不了「查無此代碼」（404 更像路徑或主機出問題，與 FundClear 那支的標準一致）。
    **現行：任一網址 ok → `ok`；其餘一律 `failed`。在拿到真實樣本之前，本函式不判 not_listed。**

    `fetched_at`：ok 時為那一次回應的實際時刻；failed 為 `None`。
    """
    attempts: list = []
    for host, page, url in _moneydj_urls(code):
        att = {"url": url, "host": host, "page_type": page, "at": _now_iso(),
               "outcome": None, "fail_kind": None, "detail": None}
        attempts.append(att)
        skip, origin = _cooldown(url)
        if skip:
            att.update(outcome="cooldown", fail_kind="cooldown", cooldown_origin_kind=origin,
                       detail=f"host 冷卻中（當初分類 {origin}），未發請求")
            continue
        try:
            r = fetch_url_with_retry(url, timeout=20, retries=1)
            # ⛔ 不變式（infra/proxy.py 模組註解）：分類必須緊接在自己的 fetch 之後讀，中間不得有其他分支。
            kind = _proxy.pop_last_fail_kind()
            att["at"] = _now_iso()           # 回應（或失敗）的實際時刻
            if r is None:
                if kind == "not_found":
                    att.update(outcome="not_found_404", fail_kind=kind, detail="HTTP 404（不當成查無此代碼）")
                elif kind:
                    att.update(outcome="http_failed", fail_kind=kind, detail=f"取數失敗（{kind}）")
                else:
                    att.update(outcome="empty_response", fail_kind="",
                               detail="回應 200 但內文為空（fetch_url_with_retry 回 None）")
                continue
            html = r.text or ""
            soup = BeautifulSoup(html, "lxml")
            fields, conflicts = _parse_label_table(soup)
            mentions = _mentions_code(soup, code)
            if fields is not None and fields.get(_NAME_LABEL) and mentions:
                att.update(outcome="ok", detail=None)
                return {
                    "status": STATUS_OK, "source": f"MoneyDJ:{host}:{page}", "full_key": code,
                    "fields": fields, "label_conflicts": conflicts,
                    "provenance": {"host": host, "page_type": page, "url": url},
                    "fetched_at": att["at"], "attempts": attempts, "error": None,
                }
            att.update(outcome="unrecognized_page",
                       detail=(f"無法判讀：has_table={fields is not None}、"
                               f"name_conflict={any(c['label'] == _NAME_LABEL for c in conflicts)}、"
                               f"mentions_code={mentions}、"
                               f"looks_like_moneydj={is_valid_moneydj_page(html)}、len={len(html)}"))
        except Exception as e:   # 取數／解析例外：記原文，不吞（整體會判 failed）
            att.update(outcome="exception", fail_kind="exception", detail=f"{type(e).__name__}: {e}")
    err = "；".join(f"{a['url']} → {a['outcome']}（{a['detail']}）" for a in attempts)
    print(f"[declared_profile/moneydj] {code} failed：{err}")
    return {
        "status": STATUS_FAILED, "source": "MoneyDJ", "full_key": code,
        "fields": {lb: None for lb in MONEYDJ_LABELS}, "label_conflicts": [],
        "provenance": None, "fetched_at": None, "attempts": attempts, "error": err,
    }


fetch_moneydj_basic_fields = _public(_fetch_moneydj_basic_fields_cached)


# ═════════════════════════════════════════════════════════════════════
# 2. TDCC OpenAPI 3-2
# ═════════════════════════════════════════════════════════════════════

#: ep → (本模組第一次觀察到的那個清單物件, 觀察時刻)。用物件身分比對：`_tdcc_get` 的快取若被換成
#: 另一份清單，視為新的一份、重記觀察時刻 —— 否則舊時刻會早於新清單的實際取得時間，「不晚於」就不成立。
_TDCC_OBSERVED: dict = {}
_TDCC_OBSERVED_LOCK = _threading.Lock()


def _tdcc_observed_at(ep: str, data: list) -> str:
    with _TDCC_OBSERVED_LOCK:
        prev = _TDCC_OBSERVED.get(ep)
        if prev is not None and prev[0] is data:
            return prev[1]
        ts = _now_iso()
        _TDCC_OBSERVED[ep] = (data, ts)
        return ts


def _tdcc_fail_kind(err_text: str) -> str:
    """`_tdcc_get` 的例外原文 → 冷卻分類（沿用 `shared/backoff_policy` 既有分類，不新增）。

    - 原文帶 HTTP 狀態碼 → `infra.source_backoff.kind_for_status`；
    - JSON／解碼例外（200 但內容不是可用的 JSON）→ `server_error`：來源**有回應**，所以不是
      `unreachable`；既有分類裡最接近「有回應但內容不可用」的是 `server_error`（該檔的定義：5xx／401／402
      等「對方回了、但回的東西不能用」）；
    - 其餘（逾時、連線錯誤）→ `unreachable`。
    """
    text = err_text or ""
    m = _HTTP_STATUS_RE.search(text)
    if m:
        return _sb.kind_for_status(int(m.group(1)))
    if text.startswith(_TDCC_BAD_PAYLOAD_EXC):
        return "server_error"
    return "unreachable"


def _tdcc_result(code, status, *, fields=None, provenance=None, observed_at=None,
                 attempt=None, error=None, match_count=0):
    return {
        "status": status, "source": f"TDCC:OpenAPI:{_TDCC_EP}", "full_key": code,
        "fields": fields or {"基金名稱": None, "計價幣別": None},
        "provenance": provenance,
        "fetched_at": None,                       # 不可考，見 docstring
        "observed_at": observed_at,
        "observed_at_semantics": "清單取得時間不晚於 observed_at（本模組在本行程內第一次觀察到這份清單的時刻）",
        "match_count": match_count,
        "attempts": [attempt] if attempt else [],
        "error": error,
    }


@_deepcopy_result
@register_cache
@_ttl_cache(ttl_sec=TTL_1HOUR, maxsize=256, cache_if=_cacheable)
def _fetch_tdcc_listing_cached(code: str) -> dict:
    """TDCC OpenAPI 3-2 清單裡這一檔的「基金名稱」「計價幣別」原字面。

    取數沿用 `sources._tdcc_get("3-2", error_out=...)`；代碼比對同 `sources._src_tdcc_meta`
    （`(item.get("基金代碼") or item.get("境外基金代碼") or "").upper() == 代碼`），比中的鍵記在
    `provenance["code_key"]`；清單裡不是 dict 的列跳過。

    status：
    - `_tdcc_get` 回 `[]` → **一律 failed**，包括讀到它行程內快取的 `[]`
      （判法同 `sources.tdcc_search_fund_with_error`：全市場清單是空的本身就不正常）；
    - 清單非空、沒有這一檔 → `not_listed`；
    - 比中一筆，或比中多筆但名稱與幣別都相同 → `ok`；比中多筆且名稱或幣別不同 → `failed`（不挑一筆冒充）。

    退避：TDCC 走 urllib，不經 `infra.proxy.fetch_url`，所以手動接 `infra.source_backoff`
    （慣例同 `repositories/fund/fx_and_main.get_latest_fx`）：呼叫前 `should_skip`，冷卻中不呼叫、判 failed；
    `_tdcc_get` 交出例外原文時 `record_failure`（分類見 `_tdcc_fail_kind`）；新取到非空清單時 `record_success`；
    `[]` 而沒有例外原文（快取的 `[]`，或 200 但不是清單）**不**記失敗 —— 前者沒有發請求，
    後者是來源活著但回應不可用（同 `get_latest_fx` 對 200 壞 payload 不退避的理由）。

    ⚠️ 已知限制（本 PR 刻意不改 `_tdcc_get`，登記於 docs/v2/49 第 8 節）：
    - `_tdcc_get` 把**非清單回應永久快取成 `[]`**，清單本身也**永不過期**（裸 dict、無 TTL）。
      前者讓本函式在該行程內恆判 failed（直到重啟）；後者讓本函式外層 1 小時 TTL 過期後拿到的仍是舊清單。
    - 因此**真正的取得時間不可考**：`fetched_at` 一律 `None`；改記 `observed_at` ——
      本模組在本行程內第一次觀察到這份清單（以物件身分判定同一份）的時刻，語意是「清單取得時間**不晚於**它」。
    """
    attempt = {"url": _TDCC_URL, "host": _sb.source_key(_TDCC_URL), "endpoint": _TDCC_EP,
               "at": _now_iso(), "outcome": None, "fail_kind": None, "detail": None}
    skip, origin = _cooldown(_TDCC_URL)
    if skip:
        attempt.update(outcome="cooldown", fail_kind="cooldown", cooldown_origin_kind=origin,
                       detail=f"host 冷卻中（當初分類 {origin}），未呼叫 _tdcc_get")
        return _tdcc_result(code, STATUS_FAILED, attempt=attempt, error=attempt["detail"])
    was_cached = _TDCC_EP in _src._tdcc_cache
    box: dict = {}
    data = _src._tdcc_get(_TDCC_EP, error_out=box)
    if not data:
        if box.get("error"):
            kind = _tdcc_fail_kind(box["error"])
            _sb.record_failure(_sb.source_key(_TDCC_URL), kind)
            attempt.update(outcome="http_failed", fail_kind=kind, detail=box["error"])
        elif was_cached:
            attempt.update(outcome="cached_empty_list", fail_kind="",
                           detail="_tdcc_get 行程內快取是空清單（原因只在當時的 stdout；重啟行程前不會重試）")
        else:
            attempt.update(outcome="empty_or_non_list", fail_kind="",
                           detail="_tdcc_get 回傳空清單（回應不是清單或真的為空，原因未提供）")
        print(f"[declared_profile/tdcc] {code} failed：{attempt['detail']}")
        return _tdcc_result(code, STATUS_FAILED, attempt=attempt, error=attempt["detail"])
    if not was_cached:
        _sb.record_success(_sb.source_key(_TDCC_URL))
    observed = _tdcc_observed_at(_TDCC_EP, data)
    matches = []
    for item in data:
        if not isinstance(item, dict):
            continue
        key = next((k for k in _TDCC_CODE_KEYS if item.get(k)), "")
        if key and str(item.get(key)).upper() == code:
            matches.append((key, item))
    attempt["outcome"] = "listed" if matches else "not_in_list"
    if not matches:
        return _tdcc_result(code, STATUS_NOT_LISTED, observed_at=observed, attempt=attempt)
    key, item = matches[0]
    fields = {"基金名稱": item.get("基金名稱"), "計價幣別": item.get("計價幣別")}
    prov = {"host": attempt["host"], "endpoint": _TDCC_EP, "url": _TDCC_URL, "code_key": key}
    distinct = {(m.get("基金名稱"), m.get("計價幣別")) for _k, m in matches}
    if len(distinct) > 1:
        err = f"代碼 {code} 在 TDCC 3-2 比中 {len(matches)} 筆且名稱或幣別不同：{sorted(map(str, distinct))}"
        attempt.update(outcome="ambiguous", detail=err)
        return _tdcc_result(code, STATUS_FAILED, observed_at=observed, attempt=attempt,
                            error=err, match_count=len(matches))
    return _tdcc_result(code, STATUS_OK, fields=fields, provenance=prov, observed_at=observed,
                        attempt=attempt, match_count=len(matches))


fetch_tdcc_listing = _public(_fetch_tdcc_listing_cached)


# ═════════════════════════════════════════════════════════════════════
# 3. FundClear GetFundBasicInfo（既有端點，非新 API）
# ═════════════════════════════════════════════════════════════════════

def _fundclear_result(code, status, url, *, currency=None, currency_key=None, fetched_at=None,
                      attempt=None, error=None):
    return {
        "status": status, "source": "FundClear:GetFundBasicInfo", "full_key": code,
        "fields": {"currency": currency},
        "currency_key": currency_key,
        "provenance": ({"host": _sb.source_key(url), "endpoint": "GetFundBasicInfo", "url": url}
                       if status == STATUS_OK else None),
        "fetched_at": fetched_at, "attempts": [attempt] if attempt else [], "error": error,
    }


def _fundclear_error_flag(payload: dict):
    """回應帶錯誤旗標 → 回說明字串，否則 None。

    ⚠️ **保守推定**：repo 內沒有 FundClear 錯誤回應樣本，鍵名照 .NET Web API 常見慣例
    （`Success`／`IsSuccess` 為 False；或 `Data` 為空而 `Message` 非空）。
    推定錯了的代價是把「沒有這一檔」判成 failed（偏保守），不會把失敗判成沒有。
    """
    for k in _FUNDCLEAR_SUCCESS_KEYS:
        if payload.get(k) is False:
            return f"回應的 {k} 為 False（Message={payload.get('Message') or payload.get('message')!r}）"
    data = payload.get("Data")
    msg_key = next((k for k in _FUNDCLEAR_MESSAGE_KEYS if payload.get(k)), None)
    if msg_key and (data is None or data == {} or data == []):
        return f"回應的 Data 為空且 {msg_key} 非空：{payload.get(msg_key)!r}"
    return None


@_deepcopy_result
@register_cache
@_ttl_cache(ttl_sec=TTL_1HOUR, maxsize=256, cache_if=_cacheable)
def _fetch_fundclear_declared_ccy_cached(code: str) -> dict:
    """FundClear `GetFundBasicInfo` 回應裡 `Data` 的幣別原字面（`Currency`，沒有再看 `currency`）。

    ⛔ 與 `sources._src_fundclear_meta` 不同的地方（刻意的）：
    - **只從 `Data` 取**。回應沒有 `Data` 鍵時判 failed，**不把整包當成 info**
      （舊寫法 `data.get("Data") or data.get("data") or data` 會把錯誤訊息包當成基金資料）。
      小寫 `data` 鍵也不收 —— 鍵名未以真實樣本驗證，寧可 failed 也不猜。
    - 回應帶錯誤旗標（見 `_fundclear_error_flag`，保守推定）→ failed，不判 not_listed。
    - `Data` 是串列時只收**恰好一筆**；多筆不挑第一筆冒充。
    - `Data` 裡若有 `FundCode`／`fundCode` 而與查詢代碼不同 → failed（避免跨基金污染）。
    - 成立日期**不讀**（客戶裁示：那串猜鍵名的 or 鏈不得使用）。

    status：
    - `ok`：`Data` 是非空 dict（或恰一筆的串列）；幣別鍵沒有或值為空 → `fields["currency"]` 為 `None`；
    - `not_listed`：回應有 `Data` 鍵，值是 `None`／空 dict／空串列，且沒有錯誤旗標；
    - `failed`：其餘（取數失敗含 404 —— API 端點的 404 不能當成「沒有這一檔」的確定回答；
      冷卻中；非 JSON；沒有 `Data` 鍵；錯誤旗標；多筆；代碼不符）。
    """
    url = _FUNDCLEAR_URL_FMT.format(code=code)
    attempt = {"url": url, "host": _sb.source_key(url), "at": _now_iso(),
               "outcome": None, "fail_kind": None, "detail": None}

    def _fail(outcome, detail, fail_kind=None):
        attempt.update(outcome=outcome, fail_kind=fail_kind, detail=detail)
        print(f"[declared_profile/fundclear] {code} failed：{detail}")
        return _fundclear_result(code, STATUS_FAILED, url, attempt=attempt, error=detail)

    skip, origin = _cooldown(url)
    if skip:
        attempt["cooldown_origin_kind"] = origin
        return _fail("cooldown", f"host 冷卻中（當初分類 {origin}），未發請求", "cooldown")
    try:
        r = fetch_url_with_retry(url, timeout=12, retries=2)
        # ⛔ 不變式：分類緊接在自己的 fetch 之後讀，中間不得有其他分支。
        kind = _proxy.pop_last_fail_kind()
        if r is None:
            if kind:
                return _fail("http_failed", f"取數失敗（{kind}）", kind)
            return _fail("empty_response", "回應 200 但內文為空（fetch_url_with_retry 回 None）", "")
        payload = r.json()
    except Exception as e:
        return _fail("exception", f"{type(e).__name__}: {e}", "exception")
    attempt["at"] = _now_iso()
    if not isinstance(payload, dict) or "Data" not in payload:
        _shape = type(payload).__name__ if not isinstance(payload, dict) else f"keys={sorted(payload)[:10]}"
        return _fail("no_data_key", f"回應沒有 Data 鍵（{_shape}），不把整包當成基金資料")
    flag = _fundclear_error_flag(payload)
    if flag:
        return _fail("error_flag", flag)
    info = payload["Data"]
    if info is None or info == {} or info == []:
        attempt.update(outcome="data_empty", detail="回應的 Data 為空")
        return _fundclear_result(code, STATUS_NOT_LISTED, url, fetched_at=attempt["at"], attempt=attempt)
    if isinstance(info, list):
        if len(info) != 1:
            return _fail("data_ambiguous", f"Data 是 {len(info)} 筆的串列，不挑一筆冒充")
        info = info[0]
    if not isinstance(info, dict):
        return _fail("data_not_dict", f"Data 不是物件（{type(info).__name__}）")
    _fc = next((info[k] for k in _FUNDCLEAR_CODE_KEYS if info.get(k) is not None), None)
    if _fc is not None and str(_fc).strip().upper() != code:
        return _fail("code_mismatch", f"Data 的 FundCode {_fc!r} 與查詢代碼 {code} 不符")
    ccy_key = next((k for k in _FUNDCLEAR_CCY_KEYS if info.get(k) not in (None, "")), None)
    attempt.update(outcome="ok")
    return _fundclear_result(code, STATUS_OK, url,
                             currency=info[ccy_key] if ccy_key else None, currency_key=ccy_key,
                             fetched_at=attempt["at"], attempt=attempt)


fetch_fundclear_declared_ccy = _public(_fetch_fundclear_declared_ccy_cached)
