# -*- coding: utf-8 -*-
"""repositories/personal_policy_reader.py — 新 B UI 持倉／保單的「個人 Active Sheet」唯讀讀取（L1）。

與 `repositories/policy_supplement_repository.py`（服務帳戶＋ `POLICY_SHEET_ID`）**完全分開**的一條新路徑，
給持倉體檢（hld）與資產配置（alo）用（批 3b-4；客戶 2026-10-26 裁示：J-1 唯讀、J-7 不 fallback、J-13 不自動用 `POLICY_SHEET_ID`）。

這條路徑的硬邊界（`tests/test_personal_policy_reader.py` 以原始碼與行為釘住）：
- 目標由呼叫端注入：`target=(sheet_id, access_token)`，另帶 `account_sub`（快取鍵用）。本檔**不讀任何設定、
  不讀環境變數、不讀服務帳戶**，沒有任何 fallback —— 沒有注入就沒有讀取（缺值 → `PersonalDriveError(AUTH_REQUIRED)`）。
- token 只放 `Authorization: Bearer` header（沿用 `personal_drive_repository._get_json`：不進 URL／log／例外文字、
  不跟轉址）。錯誤一律是 `PersonalDriveError`（只帶九個 error code 之一與固定安全訊息）；標頭不符是例外，見下。
- 快取：60 秒、**只快取成功**；鍵 ＝ `(account_sub, sheet_id, 種類)` —— **含帳號 sub**，換帳號讀同一個 sheet id
  不會讀到上一個帳號的內容（沒有跨帳號快取外洩）。快取內容不含 token。登記進 `infra.cache._CACHE_REGISTRY`（全域刷新清得掉）。
- 來源標示（provenance）：`ACTOR = "oauth"`（服務帳戶路徑是 `"sa"`）。
- 只讀：Sheets v4 `spreadsheets.get`（分頁名）與 `values:batchGet`（`FORMATTED_VALUE`）；沒有任何寫入呼叫。

回傳形狀與服務帳戶路徑的 `load_policy_holding_rows`／`load_supplement_tabs` 相同（下游 L2 `build_alo_tables` 照吃），
列的解析**重用** `policy_supplement_repository` 的 `_process_policy_tab`／`_reduce`／`_check_header`（同一套欄位對映與正規化，
不複製）。唯一差別：本路徑沒有 gspread，所以分頁原始紀錄由 `values` 自己組成（欄名＝第 1 列；缺的儲存格補空字串；
標頭有空白或重複的欄位 → 該分頁略過並列入 `skipped_tabs`，與 gspread `get_all_records` 的失敗同形）。

⚠️ 已知差異（據實，不是遺漏）：本路徑**沒有**服務帳戶路徑的整本／分頁冷卻、降級模式與 429 退避重試（那一套綁在
`infra.gspread_retry` 與服務帳戶 actor 上）。失敗不快取、下一次重繪會再打一次；第一階段每次載入只打兩個請求
（一次分頁名、一次批次讀值）。是否要為個人路徑補冷卻，留給後續批次裁示。
⚠️ 保單分頁定義與 `personal_drive_repository.verify_spreadsheet` 一致：標題不以 `_` 開頭、且不等於 `Policies`。
"""
from __future__ import annotations

import copy
import threading
import time
from typing import Any

from infra.cache import _CACHE_REGISTRY, register_cache
from repositories import personal_drive_repository as drive
from repositories import policy_supplement_repository as sup
from shared import ui_v2_error_codes as ec

ACTOR = "oauth"
CACHE_TTL_SEC = 60
CACHE_MAX_ENTRIES = 16     # 上限：寫入時先清過期、再超過就丟最舊的（不讓長時間多帳號使用把記憶體撐大）
BATCH_RANGES_MAX = 20      # `values:batchGet` 一次最多帶幾個分頁（分頁很多時分批請求，不一次塞成超長網址）
CACHE_PROXY_NAME = "_PERSONAL_POLICY_CACHE"
_WHAT = "workbook_values"

_CACHE: dict = {}
_CACHE_LOCK = threading.Lock()
_CACHE_GEN = 0


def _clock() -> float:
    return time.monotonic()


def cache_key(account_sub: str, sheet_id: str, what: str = _WHAT) -> tuple:
    """快取鍵：帳號 sub 在最前面。測試以它釘住「鍵含 sub」。"""
    if not isinstance(account_sub, str) or not account_sub.strip():
        raise drive.PersonalDriveError(ec.AUTH_REQUIRED)
    return (account_sub.strip(), sheet_id, what)


def drop_account(account_sub: str) -> None:
    """丟掉某個帳號的全部快取（登出、換帳號、確認新登入、AUTH_EXPIRED 清 session 時由 L2 呼叫）。"""
    if not isinstance(account_sub, str) or not account_sub.strip():
        return
    global _CACHE_GEN
    sub = account_sub.strip()
    with _CACHE_LOCK:
        _CACHE_GEN += 1    # 世代 +1：drop 之前已發出、尚在途中的讀取，回來後不得再把內容寫回快取（全域；多丟一次快取無害）
        for key in [k for k in _CACHE if k[0] == sub]:
            del _CACHE[key]


def clear_cache() -> None:
    global _CACHE_GEN
    with _CACHE_LOCK:
        _CACHE_GEN += 1
        _CACHE.clear()


class PersonalSchemaError(drive.PersonalDriveError):
    """`SCHEMA_INVALID` 的細分原因（仍是同一個 code，**不新增 code**）：`reason` ∈
    `no_policy_tab`（沒有任何保單分頁）／`policy_header`（所有保單分頁標頭都壞）／`supplement_header`
    （補充分頁標頭與規格不符；`tab` ＝ 該分頁名，是本檔常數、不是儲存格內容）。
    ⛔ 不帶試算表儲存格原文：標頭原文可能是使用者資料，不上畫面、不進例外。"""

    def __init__(self, reason: str, tab: str | None = None) -> None:
        super().__init__(ec.SCHEMA_INVALID)
        self.reason, self.tab = reason, tab


class _CacheProxy:
    __name__ = CACHE_PROXY_NAME

    @staticmethod
    def cache_clear() -> None:
        clear_cache()

    @staticmethod
    def cache_info() -> dict:
        with _CACHE_LOCK:
            size = len(_CACHE)
        return {"name": CACHE_PROXY_NAME, "size": size, "ttl_sec": CACHE_TTL_SEC}


def _register_cache_proxy() -> None:
    for entry in [e for e in _CACHE_REGISTRY if getattr(e, "cache_info", None)
                  and _safe_name(e) == CACHE_PROXY_NAME]:
        _CACHE_REGISTRY.remove(entry)
    register_cache(_CacheProxy())


def _safe_name(entry) -> str:
    try:
        info = entry.cache_info()
    except Exception:  # noqa: BLE001 —— 別人的登記項沒有 cache_info 或會拋，就不是本檔的
        return ""
    return info.get("name", "") if isinstance(info, dict) else ""


_register_cache_proxy()


# ════════════════════════ 讀取 ════════════════════════

def _is_policy_tab(title: str) -> bool:
    return not title.startswith("_") and title != drive._DEFAULT_POLICY_TAB


def _check_target(target: Any) -> tuple:
    if not (isinstance(target, tuple) and len(target) == 2):
        raise drive.PersonalDriveError(ec.AUTH_REQUIRED)
    sheet_id, token = target
    if not isinstance(token, str) or not token.strip():
        raise drive.PersonalDriveError(ec.AUTH_REQUIRED)
    if not isinstance(sheet_id, str) or not drive._SHEET_ID_RE.fullmatch(sheet_id):
        raise drive.PersonalDriveError(ec.SHEET_NOT_FOUND)
    return sheet_id, token


def _titles(token: str, sheet_id: str) -> list:
    data = drive._get_json(token, f"{drive.SHEETS_URL}/{sheet_id}", {"fields": "sheets.properties.title"})
    sheets = data.get("sheets")
    if not isinstance(sheets, list):
        raise drive.PersonalDriveError(ec.UPSTREAM_ERROR)
    out = []
    for item in sheets:
        props = item.get("properties") if isinstance(item, dict) else None
        title = props.get("title") if isinstance(props, dict) else None
        if not isinstance(title, str):
            raise drive.PersonalDriveError(ec.UPSTREAM_ERROR)
        out.append(title)
    return out


def _fetch_values(token: str, sheet_id: str) -> dict:
    """`{分頁名: 全部列}`：保單分頁（每張）與兩張補充分頁（有才讀；沒有就不在結果裡）。"""
    titles = _titles(token, sheet_id)
    wanted = [t for t in titles if _is_policy_tab(t) or t in (sup.TAB_HOLDING_SUPPLEMENT, sup.TAB_POLICY_PROFILE)]
    if not any(_is_policy_tab(t) for t in wanted):
        raise PersonalSchemaError("no_policy_tab")   # 沒有任何保單分頁：不是「空持倉」，是來源不符
    out = {}
    for start in range(0, len(wanted), BATCH_RANGES_MAX):
        chunk = wanted[start:start + BATCH_RANGES_MAX]
        data = drive._get_json(
            token, f"{drive.SHEETS_URL}/{sheet_id}/values:batchGet",
            {"ranges": [sup._a1_tab(t) for t in chunk], "valueRenderOption": "FORMATTED_VALUE"})
        ranges = data.get("valueRanges")
        if not isinstance(ranges, list) or len(ranges) != len(chunk):
            raise drive.PersonalDriveError(ec.UPSTREAM_ERROR)
        for title, block in zip(chunk, ranges):
            rows = block.get("values", []) if isinstance(block, dict) else None
            if not isinstance(rows, list):
                raise drive.PersonalDriveError(ec.UPSTREAM_ERROR)
            out[title] = [[("" if c is None else str(c)) for c in r] for r in rows if isinstance(r, list)]
    return out


def _cached_values(target: tuple, account_sub: str) -> dict:
    sheet_id, token = _check_target(target)
    key = cache_key(account_sub, sheet_id)
    now = _clock()
    with _CACHE_LOCK:
        hit = _CACHE.get(key)
        if hit is not None and now - hit[0] < CACHE_TTL_SEC:
            return copy.deepcopy(hit[1])
        generation = _CACHE_GEN
    values = _fetch_values(token, sheet_id)
    with _CACHE_LOCK:
        if _CACHE_GEN == generation:   # 讀取期間被清過的結果不存
            stamp = _clock()
            for k in [k for k, v in _CACHE.items() if stamp - v[0] >= CACHE_TTL_SEC]:
                del _CACHE[k]    # 寫入時順手清過期的
            while len(_CACHE) >= CACHE_MAX_ENTRIES:
                del _CACHE[min(_CACHE, key=lambda k: _CACHE[k][0])]   # 超過上限丟最舊的
            _CACHE[key] = (stamp, copy.deepcopy(values))
    return values


def _records(rows: list) -> list:
    """與服務帳戶路徑（逐列讀取整張分頁的既有做法）同一個邊界行為：所有列先補空字串到**最寬那一列**的寬度（含標頭列），
    之後標頭有重複（含兩個以上補出來的空欄名）→ ValueError（對應舊路徑的標頭例外）；
    只有一個空欄名則照收（欄名 `""`，下游以名稱取欄，不會用到）。多出標頭的資料欄因此會讓標頭多出空欄名，
    ≥2 個就是重複 → 該分頁略過（與舊路徑一致，不靜默丟資料欄）。等價由 `tests/test_personal_policy_reader.py` 逐案比對。"""
    if not rows:
        return []
    width = max(len(r) for r in rows)
    padded = [list(r) + [""] * (width - len(r)) for r in rows]
    header = padded[0]
    if len(set(header)) != len(header):
        raise ValueError(sup.HEADER_ERROR_TEXT)
    return [dict(zip(header, r)) for r in padded[1:]]


def load_workbook_tables(target: tuple, *, account_sub: str, mask) -> dict:
    """讀 Active Sheet 的保單分頁與兩張補充分頁，回 `{"actor", "policy", "supplement"}`：

    - `policy`：同 `policy_supplement_repository.load_policy_holding_rows`（`rows`、`skipped_tabs`、
      `invest_twd_parse_errors`、`read_estimate`）；
    - `supplement`：同 `load_supplement_tabs`（`{分頁名: {"records","bad_rows","blank_rows","tab_missing"}}`）。
    失敗：`PersonalDriveError`（九 code 之一）；補充分頁標頭不符 → `PersonalSchemaError("supplement_header")`（SCHEMA_INVALID，不帶標頭原文）。所有保單分頁都讀不成（標頭壞）→
    `PersonalSchemaError("policy_header")`，不回空表。
    """
    values = _cached_values(target, account_sub)
    rows, skipped, parse_errors, tab_count = [], [], [], 0
    for title, tab_values in values.items():
        if not _is_policy_tab(title):
            continue
        tab_count += 1
        try:
            raw = _records(tab_values)
        except ValueError as exc:
            skipped.append({"tab": title, "error": mask(str(exc)), "unread": False})
            continue
        tab_rows, tab_errors = sup._process_policy_tab(title, raw)
        rows.extend(tab_rows)
        parse_errors.extend(tab_errors)
    if tab_count and len(skipped) == tab_count:
        raise PersonalSchemaError("policy_header")
    names = (sup.TAB_HOLDING_SUPPLEMENT, sup.TAB_POLICY_PROFILE)
    for name in names:
        if values.get(name):
            try:
                sup._check_header(name, values[name], mask=mask)
            except sup.PolicySupplementError:
                failed = name
            else:
                continue
            raise PersonalSchemaError("supplement_header", failed) from None   # 不帶標頭原文（可能是使用者資料）
    supplement = {name: sup._reduce(name, values.get(name)) for name in names}
    return {
        "actor": ACTOR,
        "policy": {"rows": rows, "skipped_tabs": skipped, "invest_twd_parse_errors": parse_errors,
                   "read_estimate": {"tab_count": tab_count, "actor": ACTOR,
                          "requests_per_load": 1 + -(-(tab_count + len([n for n in names if values.get(n) is not None]))
                                                     // BATCH_RANGES_MAX)}},
        "supplement": supplement,
    }
