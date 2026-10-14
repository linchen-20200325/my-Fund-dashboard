"""repositories/fund/declared_profile.py — 基金「來源自報」基本資料取數（L1，exp 正式模式批 C 的 C1）。

只做一件事：把三個**既有**來源對某一檔基金「自己寫了什麼」原樣交出來，附出處、取得時間、
逐網址的嘗試紀錄與失敗原文。**不新增來源、不新增 API、不正規化、不推斷、不補值。**

三支公開函式（都回 dict，都帶 `status`）：

1. `fetch_moneydj_basic_fields(full_key)` —— MoneyDJ 基本資料頁 yp011000／yp011001
   （~~status ∈ {ok, failed}~~ → 2026-10-14 身分判準修訂：status ∈ {ok, unrecognized_page, not_found, failed}）。
2. `fetch_tdcc_listing(full_key)` —— TDCC OpenAPI 3-2（境外基金基本資料清單）
   （~~status ∈ {ok, not_listed, failed}~~ → 2026-10-14：status ∈ {ok, code_unmapped, failed}）。
3. `fetch_fundclear_declared_ccy(full_key)` —— FundClear `GetFundBasicInfo`（`_src_fundclear_meta` 用的同一支）
   （status ∈ {ok, not_listed, failed}）。

另有一支維護用函式 `reset_tdcc_list_cache_if_empty()`（2026-10-14 C2）：只在 `sources._tdcc_cache` 對 3-2 存的是
空清單 `[]` 時丟掉那一筆（set 頁「重新取數」用），不改 `_tdcc_get`。MoneyDJ 的 ok 結果另帶 `binding`（同日 C2，
表格與代碼的綁定；見 `_fetch_moneydj_basic_fields_cached`）。

## 客戶裁示（本檔的邊界，逐條落在程式裡）

- 幣別只取來源**自報**的值，可追溯；**不從名稱或代碼推斷**。本檔沒有任何一行看基金名稱或代碼去猜幣別。
- 成立日期只讀 MoneyDJ 基本資料頁的「成立日期」欄；**FundClear 那串猜鍵名的 or 鏈不使用**
  （`fetch_fundclear_declared_ccy` 完全不碰成立日期）。
- 「最高經理費」**不讀**：MoneyDJ 解析只保留四個標籤，其餘標籤（含「最高經理費(%)」）連存都不存。
- 缺值一律 `None`，不填 0、不填空字串、不用寫死的備援、不靜默換來源。
- 幣別字面**不在 L1 正規化**（「美元」「USD」「美金」照原字交出），交給 L2。

## status 的意思

- `ok`：來源有這一檔，且讀到了它的資料（各欄仍可能是 `None`＝來源沒寫或來源自相矛盾）。
- `not_listed`：來源**明確**回答沒有這一檔（判準見各函式）。**MoneyDJ 目前一律不判 not_listed**（見該函式）；
  **TDCC 自 2026-10-14 起也不判**（見 `code_unmapped`）。現在只有 FundClear 會交出它。
- ~~`failed`：取不到、或取到的東西無法判讀。**只要有一次無法判讀，就不得升格成 not_listed。**~~
  → 2026-10-14 身分判準修訂（有意識的更正，不是漏刪；決策者：AI 總管；依據：#961 探測報告
  `results/20261014T101710Z_run38548232056`）：「取到但無法判讀」與「取不到」是兩件事，混在一起會把
  正常取回、只是不是本檔的頁面在畫面上標成 ⛔ 取數失敗。舊句的用意（無法判讀就不得說成「沒有這一檔」）
  照舊成立 —— 下面兩個新狀態都**不是** not_listed。
- `failed`：**取不到**：網路錯誤、逾時、403／407／429、5xx、host 冷卻中（沒發請求）、非預期例外。
- `unrecognized_page`（只 MoneyDJ）：頁面**回來了**（200），但不符身分判準（見該函式）—— 空殼頁、
  「無資料」頁、頁型不符的空表、兩張以上含「基金名稱」的表、基金名稱自相矛盾、200 但內文空白。
- `not_found`（只 MoneyDJ）：兩種頁型、兩個主機**全部** 404，一頁都沒回來。
- `code_unmapped`（只 TDCC）：清單取得成功，但代碼在兩個代碼欄都 0 命中 —— 3-2 用的是另一套代碼體系
  （探測實測：5,295 列，例 `GLIACU`、`AGIF-FVGM`），0 命中**不證明**未收錄。**不以名稱比對去找對應**。

## 快取與失敗記憶

- 成功快取：內層 `@_ttl_cache(TTL_1HOUR, cache_if=只收 ok／not_listed／code_unmapped)`（2026-10-14 加 code_unmapped）並 `register_cache`，再交深拷貝
  （同 `fund_orchestration._deepcopy_result` 的做法）。命中快取時交出的是**當初那一份**，
  `fetched_at`／`observed_at` 不會變成當下時間。
- 代碼先正規化（去頭尾空白、轉大寫）再進快取：`" tlzf9"` 與 `"TLZF9"` 共用同一格。
- 失敗記憶：failed（2026-10-14 起含 unrecognized_page、not_found）結果另記 `FAILURE_MEMORY_SEC` 秒（理由見該常數）。記憶期間再呼叫**不發請求**，
  交回上一次的 failed 結果（原文、嘗試紀錄、時刻原樣），加 `cooling=True` 與 `cooling_remaining_sec`。
  以 `register_cache` 登記一個清除用的物件（`clear_all_caches()` 會清到），另有 `clear_failure_memory()`。

⚠️ 本檔的 HTML 標籤結構與 JSON 鍵名**未以真實回應樣本驗證**（repo 內沒有這三個來源的原始回應，
本環境也連不到）；判準是照 repo 既有解析碼（`_src_tcb_meta`／`_src_tdcc_meta`／`_src_fundclear_meta`）寫的。
→ 2026-10-14 補記：**MoneyDJ 基本資料頁已有真實樣本**（#961 探測報告，GitHub runner 直連；golden fixture 在
`tests/fixtures/moneydj_basic/`），身分判準依它修訂；TDCC 3-2 的欄名經同一份報告確認（代碼體系不同，見
`code_unmapped`）；**FundClear 仍未驗證**（探測 9/9 回應非 JSON，報告未存本文，見 docs/v2/49 第 8 節）。
production 經 NAS 代理的回應是否與直連相同，**未驗**。

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
    "STATUS_UNRECOGNIZED", "STATUS_NOT_FOUND", "STATUS_CODE_UNMAPPED", "MONEYDJ_BINDING_METHOD",
    "MONEYDJ_LABELS", "MONEYDJ_HOSTS", "FAILURE_MEMORY_SEC",
    "fetch_moneydj_basic_fields", "fetch_tdcc_listing", "fetch_fundclear_declared_ccy",
    "clear_failure_memory", "reset_tdcc_list_cache_if_empty",
]

STATUS_OK = "ok"
STATUS_NOT_LISTED = "not_listed"
STATUS_FAILED = "failed"
#: 以下三個 2026-10-14 身分判準修訂新增（見模組開頭「status 的意思」）。
STATUS_UNRECOGNIZED = "unrecognized_page"   # 只 MoneyDJ：頁面回來了，但不符身分判準
STATUS_NOT_FOUND = "not_found"              # 只 MoneyDJ：全部網址 404
STATUS_CODE_UNMAPPED = "code_unmapped"      # 只 TDCC：清單成功、代碼 0 命中（不同代碼體系）
#: 進 1 小時成功快取的狀態。`code_unmapped` 跟 not_listed 一樣是對「同一份清單」的確定答案。
#: `unrecognized_page`／`not_found` **不進**：維護頁、暫時的 404 都可能是短暫的（稽核 M 的理由照舊成立），
#: 改走失敗記憶（`FAILURE_MEMORY_SEC`）—— 否則每次 Streamlit rerun 都會重打全部網址（稽核 N-2）。
_CACHEABLE_STATUSES = frozenset({STATUS_OK, STATUS_NOT_LISTED, STATUS_CODE_UNMAPPED})
_MEMORIZED_STATUSES = frozenset({STATUS_FAILED, STATUS_UNRECOGNIZED, STATUS_NOT_FOUND})

#: failed（2026-10-14 起含 unrecognized_page、not_found，見 `_MEMORIZED_STATUSES`）結果的短期記憶秒數。
#: 理由：failed 不進 1 小時成功快取（下次要能拿到真答案），而 404／407 依
#: `shared/backoff_policy.NO_COOLDOWN_KINDS` 不冷卻 —— 兩者疊在一起，每次 Streamlit rerun 都會重打
#: 全部網址（稽核 N-2 實測：5 次呼叫打出 20 個請求）。5 分鐘遠短於成功 TTL（1 小時），
#: 來源恢復後最多晚 5 分鐘拿到真答案；與退避的 `server_error` 冷卻同量級，不另立新秒數。
FAILURE_MEMORY_SEC: int = TTL_5MIN

#: 只收字面**完全相同**（去頭尾空白後）的四個標籤。「設立日期」「成立日」等近似字不收。
#: ⛔ 「最高經理費」不在此列，也不得加入：客戶裁示它不能冒充經理費率，本檔一律不讀。
MONEYDJ_LABELS: tuple[str, ...] = ("基金名稱", "計價幣別", "配息頻率", "成立日期")
_NAME_LABEL = "基金名稱"
#: 2026-10-14 身分判準修訂：MoneyDJ ok 結果的 `binding["method"]`（判準名稱，見 `_identify_name_table`）。
MONEYDJ_BINDING_METHOD = "requested_code_populated_name_table"

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
    """`_ttl_cache(cache_if=...)`：只快取 `_CACHEABLE_STATUSES`；其餘交給失敗記憶（較短）。"""
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
        # ~~if result.get("status") == STATUS_FAILED:~~ → 2026-10-14：unrecognized_page／not_found 一併記憶（理由見
        # `_CACHEABLE_STATUSES`；有意識的更正，不是漏刪）。
        if result.get("status") in _MEMORIZED_STATUSES:
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
    """找第一張含「基金名稱」那一列的表 → `(fields 或 None, conflicts)`。**介面與行為同 C1，一字未改**
    （判法見 `_parse_label_table_with_node`，本函式只是丟掉第三個值）。

    ⚠️ 2026-10-14 C2 稽核 W（BLOCKING）：C2 第一版把本函式的回傳改成三個值，平行的 #961 探測腳本
    （`scripts/probe_moneydj_basic_page.py`）以兩個值接收，兩邊合併後會炸。現恢復兩值介面，要表格節點請用
    `_parse_label_table_with_node`（有意識的更正，不是漏刪；決策者：AI 總管）。
    """
    fields, conflicts, _tbl = _parse_label_table_with_node(soup)
    return fields, conflicts


def _parse_label_table_with_node(soup) -> "tuple[dict | None, list[dict], object]":
    """找第一張含「基金名稱」那一列（標籤字面完全相同、值非空）的表，只收 `MONEYDJ_LABELS` 四個標籤。

    列配對同 `sources._src_tcb_meta`：恰 2 格 → (0,1)；4 格以上 → (0,1)(2,3)…；其餘格數不收。
    與它不同的地方（刻意的）：
    - 標籤比對用**完全相同**（去頭尾空白後），不是子字串；
    - 只看表格自己的列（`_own_rows`）與列的**直接子** `td`，巢狀表不會串進外層；
    - 同一標籤出現兩次且值不同 → 該欄設 `None`，兩個值記進 conflicts（不取第一個、不取最後一個）。
    （2026-10-14 C2 新增的函式；判法即 C1 `_parse_label_table` 的本體，一字未改。）
    回傳 `(fields 或 None, conflicts, 該表格節點或 None)`；fields 的值是原始字面，標籤沒出現或自相矛盾 → `None`；
    第三個值是**被採用的那一張表**本身（沒有表時為 `None`），讓呼叫端檢查代碼是否出現在這張表自己的文字裡
    （docs/v2/49 第 8 節 (n)「C2 接上畫面前必須把表格與代碼綁定」）。
    """
    for tbl in soup.find_all("table"):
        seen = _label_values(tbl)
        if any(v for v in seen.get(_NAME_LABEL, [])):
            fields, conflicts = _fields_from(seen)
            return fields, conflicts, tbl
    return None, [], None


def _label_values(tbl) -> dict:
    """一張表**自己的**列裡，`MONEYDJ_LABELS` 四個標籤各自出現過的值（去頭尾空白後去重，保留出現順序）。
    標籤沒出現 → 不在回傳的 dict 裡；出現但值空白 → 值為 `""`。
    （2026-10-14 身分判準修訂：從 `_parse_label_table_with_node` 原樣抽出，判法一字未改，讓身分判定能逐表計數。）"""
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
    return seen


def _fields_from(seen: dict) -> "tuple[dict, list[dict]]":
    """`_label_values` 的結果 → `(fields, conflicts)`：只出現一個值 → 該值；沒出現或兩個以上不同值 → `None`。"""
    fields = {lb: (seen[lb][0] if len(seen.get(lb, [])) == 1 else None) for lb in MONEYDJ_LABELS}
    conflicts = [{"label": lb, "values": list(seen[lb])}
                 for lb in MONEYDJ_LABELS if len(seen.get(lb, [])) > 1]
    return fields, conflicts


def _blank(text) -> bool:
    """去除 `\\xa0` 與空白後是否為空（`str.strip()` 本來就去 `\\xa0`；這裡寫明，不靠讀者記得）。"""
    return not str(text).replace("\xa0", " ").strip()


def _identify_name_table(soup) -> dict:
    """2026-10-14 身分判準：頁面上**恰有一張**含「基金名稱」標籤（字面完全相同）的表，且該表「基金名稱」欄
    **只有一個值、去除 `\\xa0` 與空白後非空** → 採用這張表。

    回傳 `{"problem", "fields", "conflicts", "table", "name_table_count", "populated_name_table_count"}`：
    - `name_table_count`：含「基金名稱」標籤的表的張數（值空白的也算）；
    - `populated_name_table_count`：其中基金名稱非空的張數；
    - `problem`：None ＝ 通過；否則是不採用的具體原因（中文，進嘗試紀錄與畫面原因）。

    不採用的情形（逐一對應探測報告實測到的頁面）：
    - 0 張：空殼頁、「無資料」頁、境外代碼打到境內頁型（yp011000）時回的空殼；
    - 1 張但基金名稱空白：境內代碼打到境外頁型（yp011001）時回的空表（title 仍帶基金名稱 —— **不採用 title**）；
    - 1 張但基金名稱出現兩個不同值：自相矛盾；
    - 2 張以上：無法確認哪一張是本檔（**不挑第一張**，即使只有一張非空也不採用 —— 判準要求「恰一張含標籤的表」）。
    巢狀表只算它自己的列（`_own_rows`），外層表不會因為包著內層表而被算成含標籤。
    """
    found = []
    for tbl in soup.find_all("table"):
        seen = _label_values(tbl)
        if _NAME_LABEL in seen:
            found.append((tbl, seen))
    populated = [(t, s) for t, s in found if any(not _blank(v) for v in s[_NAME_LABEL])]
    out = {"problem": None, "fields": None, "conflicts": [], "table": None,
           "name_table_count": len(found), "populated_name_table_count": len(populated)}
    if not found:
        out["problem"] = "頁面沒有含「基金名稱」標籤的表"
    elif len(found) > 1:
        out["problem"] = (f"頁面有 {len(found)} 張含「基金名稱」標籤的表（其中 {len(populated)} 張非空白），"
                          "無法確認哪一張是本檔")
    else:
        tbl, seen = found[0]
        names = seen[_NAME_LABEL]
        if not populated:
            out["problem"] = "含「基金名稱」標籤的表，基金名稱欄為空白（頁型可能不符）"
        elif len(names) > 1:
            out["problem"] = f"「基金名稱」在同一張表出現不同的值：{names}"
        else:
            out["fields"], out["conflicts"] = _fields_from(seen)
            out["table"] = tbl
    return out


def _mentions_code(soup, code: str) -> bool:
    """頁面**可見文字**是否以完整詞提到該代碼（大小寫不分）。
    只看 `get_text()`（不含 href 等屬性值），前後不得緊接英數字：查 `TLZF9` 不會被 `TLZF90` 命中。

    ~~ok 判準的一半（頁面可見文字須提到代碼）~~ → 2026-10-14 身分判準修訂（有意識的更正，不是漏刪；
    決策者：AI 總管；依據：#961 探測報告）：**降為附加資訊**（ok 結果的 `binding["code_in_page_text"]`），
    不再是採用門檻。理由：8 個真實代碼的頁面可見文字（含那張表）**都沒有印代碼**，代碼只出現在 href／onclick
    與 `<script>`，而且是照請求網址原樣回顯 —— 不存在的代碼的空殼頁同樣出現相同數量的回顯。
    舊條件結構上不可能成立（8/8 失敗），而回顯也分不出真假，兩種用法都不能當身分證據。"""
    pat = _re.compile(rf"(?<![A-Za-z0-9]){_re.escape(code)}(?![A-Za-z0-9])", _re.IGNORECASE)
    return bool(pat.search(soup.get_text(" ")))


def _table_mentions_code(tbl, code: str) -> bool:
    """「含基金名稱那張表**自身**的文字」是否以完整詞提到該代碼（規則同 `_mentions_code`：只看可見文字、
    前後不得緊接英數字、大小寫不分）。**巢狀在這張表裡的內層表不算**（先複製再拿掉內層表，不動原頁面）——
    內層表可能是另一檔基金的表，算進來就等於沒有綁定。`tbl` 為 None → False。

    ~~L2 據此決定採不採用~~ → 2026-10-14 身分判準修訂（有意識的更正，不是漏刪；決策者：AI 總管）：
    **降為附加資訊**（`binding["code_in_label_table"]`，值照實）。探測報告實測 0/8 成立 —— 真實的那張表裡
    沒有代碼，這條要求結構上不可能成立。"""
    if tbl is None:
        return False
    clone = _copy.copy(tbl)          # bs4 Tag 的 copy 是整棵子樹的複本；拿掉內層表不影響原頁面
    for inner in clone.find_all("table"):
        inner.decompose()
    return _mentions_code(clone, code)


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
    ~~「讀到含『基金名稱』那一列的表，**且**頁面可見文字以完整詞提到該代碼」為止。~~
    「某一頁通過身分判準」為止（見下方「身分判準」）。
    `is_valid_moneydj_page` 靠不住（`sources._src_allianzgi_meta` 自註：任兩個常見中文詞就回 True），
    本函式只拿它記進嘗試紀錄的說明，從不用它判定任何 status。

    ~~⚠️ 表格與代碼**仍未綁定**：只確認「頁面可見文字提到該代碼」＋「頁面上有一張含基金名稱的表」，
    沒有確認那張表就是該代碼的表（真實頁面結構未以樣本驗證）。~~
    → 2026-10-14 C2（有意識的更正，不是漏刪；決策者：AI 總管）：**ok 判準不變**（仍只看上面兩件事），
    但 ok 結果多交一個 `binding`：`code_in_label_table`＝代碼是否以完整詞出現在**那張含基金名稱的表自身**的文字裡
    （`_table_mentions_code`，巢狀內層表不算）；`code_in_page_text` 在 ok 時恆為 True。
    綁定與否由 L2（`services/v2_tables/exp_profile.py`）決定採不採用。真實頁面上代碼是不是寫在那張表裡，
    **仍未以樣本驗證** —— 若真實頁面把代碼放在表外，L2 會把四欄一律判成資料未備（偏保守的那一側）。

    ## 身分判準（2026-10-14 修訂；有意識的更正，不是漏刪；決策者：AI 總管）

    依據：#961 探測報告 `results/20261014T101710Z_run38548232056`（GitHub runner 直連；18 頁原始 HTML、sha256 已核）。
    8 個真實代碼在 www 首選頁型都回 200、各有恰 1 張含「基金名稱」的表、四欄字面都讀得到；**但頁面可見文字
    （含那張表）完全沒有出現代碼** —— 代碼只在 href／onclick 與 `<script>` 裡、照請求網址原樣回顯，
    不存在的代碼的空殼頁回顯數量相同。舊判準（可見文字以詞界提到代碼）因此 8/8 失敗，
    上面那段 C2 的 `code_in_label_table` 也 0/8 成立：兩者結構上都不可能成立。

    **現行判準（`_identify_name_table`）**：以**請求的代碼**組出網址 → 回 200 → 該頁**恰有一張**含「基金名稱」
    標籤的表，且該表「基金名稱」欄只有一個值、去除 `\xa0` 與空白後非空。信任模型與本 repo A 鏈淨值取數相同：
    「代碼 → MoneyDJ 網址」本身就是身分。實測擋得住的頁：空殼頁、「無資料」頁、頁型不符的空表（title 仍帶
    基金名稱 —— **不得改用 title 取值**）。兩張以上含「基金名稱」的表 → 不採用。
    舊的兩項檢查（頁面可見文字、表自身文字是否提到代碼）**保留為附加資訊**，值照實記在 `binding`，不再是門檻。
    ⚠️ 未驗：production 經 NAS 代理的回應是否與直連相同；MoneyDJ 對不存在的代碼是否**永遠**不回某一檔的頁面
    （探測只有一個負控代碼）。

    ok 結果的 `binding`::

        {"method": MONEYDJ_BINDING_METHOD, "identity_confirmed": True,
         "name_table_count": 1, "populated_name_table_count": 1, "name_nonempty": True,
         "code_in_label_table": bool,   # 附加資訊（舊 C2 條件），值照實
         "code_in_page_text": bool}     # 附加資訊（舊 C1 條件），值照實；~~ok 時恆為 True~~

    逐網址結果（`attempts[i]["outcome"]`）：
    - ~~`ok`：有表、可見文字有代碼 → 採用並停止；~~ → `ok`：通過身分判準 → 採用並停止；
    - `not_found_404`：HTTP 404；
    - ~~`unrecognized_page`：取回但無法判讀（空殼、維護頁、有表沒代碼、有代碼沒表、基金名稱自相矛盾）；~~
      → `unrecognized_page`：200 但不符身分判準（具體原因寫在 `detail` 與 `problem`）；
    - `cooldown`：host 冷卻中，沒有發請求；`fail_kind="cooldown"`，當初的分類記在 `cooldown_origin_kind`；
    - `http_failed`：逾時／403／429／5xx／407，分類取自 `infra.proxy.pop_last_fail_kind()`；
    - `empty_response`：200 但內文為空（`fetch_url_with_retry` 回 None 且沒有失敗分類）；
    - `exception`：取數或解析拋例外（原文記在 detail）。
    不符身分判準、但頁面確實回來的嘗試另帶 `identity_check`（張數與附加資訊）。

    ~~status：任一網址 ok → `ok`；4 個網址**全部**屬「確定沒有」→ `not_listed`；其餘 → `failed`。~~
    ~~（「確定沒有」＝ 404，或正常頁但既沒有該代碼也沒有表）~~
    → **2026-10-14 有意識的更正，不是漏刪**（決策者：AI 總管；依據：稽核 M 的實跑反例 ——
    4 個網址都回空殼頁、或都回含「基金 淨值 績效」字樣的「系統維護中」頁、或 tcb 兩個 404 加 www 兩個空殼，
    舊判準都會判成 not_listed 並快取 1 小時，把「打失敗」說成「沒有這一檔」）。
    舊句的用意（來源明確說沒有時要能分辨）仍然成立；被權衡掉的是它的判準 —— 沒有真實的「查無此基金」頁面樣本，
    「正常頁」與 404 都證明不了「查無此代碼」（404 更像路徑或主機出問題，與 FundClear 那支的標準一致）。
    ~~**現行：任一網址 ok → `ok`；其餘一律 `failed`。在拿到真實樣本之前，本函式不判 not_listed。**~~
    → **2026-10-14 身分判準修訂（有意識的更正，不是漏刪；決策者：AI 總管）**：「其餘一律 failed」把正常取回、
    只是不符判準的頁面也說成取數失敗（探測實測：負控代碼與 8 個真實代碼的輸出完全相同，畫面全是 ⛔）。
    上一段「不判 not_listed」的理由照舊成立、照舊不判。**現行（沒有任何網址 ok 時，依序判）**：
    1. 有任一網址**取不到**（`http_failed`／`cooldown`／`exception`）→ `failed`
       —— 沒讀到的那一頁可能正是本檔，不能說「頁面不是本檔」；
    2. 否則有任一網址**回來了但不符判準**（`unrecognized_page`、`empty_response`）→ `unrecognized_page`；
       `empty_response`（200 但內文空白）歸這一類：它是 200 的回應，不是網路錯誤、逾時、5xx 或例外；
    3. 否則（四個網址全部 404）→ `not_found`。
    三者的 `error` 都是逐網址的結果原文，`reason` 是逐網址的白話摘要（`頁型@主機：原因`），L2 顯示用。

    `fetched_at`：ok 時為那一次回應的實際時刻；其餘為 `None`。
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
            ident = _identify_name_table(soup)
            mentions = _mentions_code(soup, code)
            check = {"name_table_count": ident["name_table_count"],
                     "populated_name_table_count": ident["populated_name_table_count"],
                     "code_in_page_text": mentions}
            att["identity_check"] = check
            # ~~if fields is not None and fields.get(_NAME_LABEL) and mentions:~~ → 2026-10-14 身分判準修訂
            # （有意識的更正，不是漏刪；理由見本函式 docstring「身分判準」）：可見文字提到代碼不再是門檻。
            if ident["problem"] is None:
                att.update(outcome="ok", detail=None)
                return {
                    "status": STATUS_OK, "source": f"MoneyDJ:{host}:{page}", "full_key": code,
                    "fields": ident["fields"], "label_conflicts": ident["conflicts"],
                    "binding": {"method": MONEYDJ_BINDING_METHOD, "identity_confirmed": True,
                                "name_table_count": ident["name_table_count"],
                                "populated_name_table_count": ident["populated_name_table_count"],
                                "name_nonempty": True,
                                # 附加資訊（舊條件，值照實；不再是門檻）
                                "code_in_label_table": _table_mentions_code(ident["table"], code),
                                "code_in_page_text": mentions},
                    "provenance": {"host": host, "page_type": page, "url": url},
                    "fetched_at": att["at"], "attempts": attempts, "error": None, "reason": None,
                }
            visible = soup.get_text(" ").strip()
            shown = f"、頁面可見文字僅「{visible}」" if len(visible) <= 20 else ""
            att.update(outcome="unrecognized_page", problem=ident["problem"] + shown,
                       detail=(f"不符身分判準：{ident['problem']}（含基金名稱標籤的表 {ident['name_table_count']} 張、"
                               f"非空 {ident['populated_name_table_count']} 張、mentions_code={mentions}、"
                               f"looks_like_moneydj={is_valid_moneydj_page(html)}、len={len(html)}{shown}）"))
        except Exception as e:   # 取數／解析例外：記原文，不吞（整體會判 failed）
            att.update(outcome="exception", fail_kind="exception", detail=f"{type(e).__name__}: {e}")
    return _moneydj_not_ok(code, attempts)


#: 「取不到」的嘗試結果：只要有一個，整體就是 failed（沒讀到的那一頁可能正是本檔）。
_MDJ_UNREADABLE_OUTCOMES = frozenset({"http_failed", "cooldown", "exception"})
#: 「回來了但不符判準」的嘗試結果。
_MDJ_UNRECOGNIZED_OUTCOMES = frozenset({"unrecognized_page", "empty_response"})


def _attempt_short(att: dict) -> str:
    """一筆嘗試 → `頁型@主機：白話原因`（L2 畫面用；完整原文在 `error`）。"""
    outcome = att.get("outcome")
    if outcome == "not_found_404":
        why = "HTTP 404"
    elif outcome == "unrecognized_page":
        why = att.get("problem") or "不符身分判準"
    elif outcome == "empty_response":
        why = "回應 200 但內文空白"
    elif outcome == "cooldown":
        why = f"主機冷卻中、未發請求（當初分類 {att.get('cooldown_origin_kind')}）"
    elif outcome == "http_failed":
        why = f"取數失敗（{att.get('fail_kind')}）"
    else:
        why = att.get("detail") or str(outcome)
    return f"{att.get('page_type')}@{att.get('host')}：{why}"


def _moneydj_not_ok(code: str, attempts: list) -> dict:
    """沒有任何網址 ok → 依序判 failed／unrecognized_page／not_found（判準見 `_fetch_moneydj_basic_fields_cached`）。"""
    outcomes = [a.get("outcome") for a in attempts]
    if any(o in _MDJ_UNREADABLE_OUTCOMES for o in outcomes):
        status = STATUS_FAILED
    elif any(o in _MDJ_UNRECOGNIZED_OUTCOMES for o in outcomes):
        status = STATUS_UNRECOGNIZED
    elif outcomes and all(o == "not_found_404" for o in outcomes):
        status = STATUS_NOT_FOUND
    else:   # 理論上走不到（每筆嘗試都有上列之一的 outcome）；走到就是程式錯，從嚴判 failed
        status = STATUS_FAILED
    err = "；".join(f"{a['url']} → {a['outcome']}（{a['detail']}）" for a in attempts)
    reason = "；".join(_attempt_short(a) for a in attempts)
    print(f"[declared_profile/moneydj] {code} {status}：{err}")
    return {
        "status": status, "source": "MoneyDJ", "full_key": code,
        "fields": {lb: None for lb in MONEYDJ_LABELS}, "label_conflicts": [],
        "provenance": None, "fetched_at": None, "attempts": attempts, "error": err, "reason": reason,
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
    - ~~清單非空、沒有這一檔 → `not_listed`；~~
      → 2026-10-14（有意識的更正，不是漏刪；決策者：AI 總管；依據：#961 探測報告 `tdcc_3_2_extract`）：
      清單非空、代碼 0 命中 → `code_unmapped`（代碼無法對照）。3-2 的 5,295 列用的是另一套代碼
      （例 `GLIACU`、`AGIF-FVGM`），探測的 9 個代碼在**全部欄位**都 0 命中 —— 0 命中證明不了「未收錄」。
      舊句的用意（清單裡確實沒有時要能分辨）仍成立，被權衡掉的是它的前提（兩邊用同一套代碼）。
      ⛔ **不以基金名稱模糊比對去找對應**（不從名稱推斷）。
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
        # ~~return _tdcc_result(code, STATUS_NOT_LISTED, ...)~~ → 2026-10-14：代碼無法對照（見 docstring）
        attempt["detail"] = (f"清單 {len(data)} 列，{'／'.join(_TDCC_CODE_KEYS)} 兩欄 0 命中；"
                             "TDCC 3-2 使用不同的代碼體系，0 命中不等於未收錄（不以名稱比對）")
        return _tdcc_result(code, STATUS_CODE_UNMAPPED, observed_at=observed, attempt=attempt)
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


def reset_tdcc_list_cache_if_empty() -> bool:
    """`sources._tdcc_cache` 對 3-2 存的若是空清單 `[]` → 丟掉那一筆，回 True；其餘（沒有這一筆、或是非空清單）
    一律不動，回 False。

    2026-10-14 C2（docs/v2/49 第 8 節 (q) 的後續）：`_tdcc_get` 把非清單回應**永久**快取成 `[]`，
    `fetch_tdcc_listing` 因此在該行程內恆判 failed、直到重啟。set 頁「重新取數」呼叫本函式，讓下一次真的重試。
    ⛔ **不改 `_tdcc_get`**、不清非空清單（那是 TDCC 真的交回的清單，清掉只會多打一次）、不動其他端點。
    鎖沿用 `sources._tdcc_lock`（與 `_tdcc_get` 讀寫快取同一把）。
    """
    with _src._tdcc_lock:
        if _TDCC_EP in _src._tdcc_cache and _src._tdcc_cache[_TDCC_EP] == []:
            del _src._tdcc_cache[_TDCC_EP]
            return True
    return False


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
    （`Success`／`IsSuccess` 為 False 或字串 `"false"`（大小寫不分）；或 `Data` 為空而 `Message` 非空）。
    其他非布林值（`0`、`"0"`、`"no"`…）不當成錯誤旗標，照其餘規則判。
    推定錯了的代價是把「沒有這一檔」判成 failed（偏保守），不會把失敗判成沒有。
    """
    for k in _FUNDCLEAR_SUCCESS_KEYS:
        v = payload.get(k)
        if v is False or (isinstance(v, str) and v.strip().lower() == "false"):
            return f"回應的 {k} 為 {v!r}（Message={payload.get('Message') or payload.get('message')!r}）"
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
