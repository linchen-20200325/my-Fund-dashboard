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


def clear_cache() -> None:
    global _CACHE_GEN
    with _CACHE_LOCK:
        _CACHE_GEN += 1
        _CACHE.clear()


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
    if not isinstance(sheet_id, str) or not drive._SHEET_ID_RE.match(sheet_id):
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
        raise drive.PersonalDriveError(ec.SCHEMA_INVALID)   # 沒有任何保單分頁：不是「空持倉」，是來源不符
    data = drive._get_json(
        token, f"{drive.SHEETS_URL}/{sheet_id}/values:batchGet",
        {"ranges": [sup._a1_tab(t) for t in wanted], "valueRenderOption": "FORMATTED_VALUE"})
    ranges = data.get("valueRanges")
    if not isinstance(ranges, list) or len(ranges) != len(wanted):
        raise drive.PersonalDriveError(ec.UPSTREAM_ERROR)
    out = {}
    for title, block in zip(wanted, ranges):
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
            _CACHE[key] = (_clock(), copy.deepcopy(values))
    return values


def _records(rows: list) -> list:
    """第 1 列＝欄名；之後每列一筆 dict（缺的補空字串、多的丟掉）。標頭有空白或重複 → ValueError。"""
    if not rows:
        return []
    header = [c for c in rows[0]]
    while header and header[-1] == "":
        header.pop()
    if not header or any(not h.strip() for h in header) or len(set(header)) != len(header):
        raise ValueError(sup.HEADER_ERROR_TEXT)
    out = []
    for row in rows[1:]:
        cells = list(row) + [""] * (len(header) - len(row))
        out.append(dict(zip(header, cells[:len(header)])))
    return out


def load_workbook_tables(target: tuple, *, account_sub: str, mask) -> dict:
    """讀 Active Sheet 的保單分頁與兩張補充分頁，回 `{"actor", "policy", "supplement"}`：

    - `policy`：同 `policy_supplement_repository.load_policy_holding_rows`（`rows`、`skipped_tabs`、
      `invest_twd_parse_errors`、`read_estimate`）；
    - `supplement`：同 `load_supplement_tabs`（`{分頁名: {"records","bad_rows","blank_rows","tab_missing"}}`）。
    失敗：`PersonalDriveError`（九 code 之一）；補充分頁標頭不符 → `PolicySupplementError(code="header_mismatch")`
    （訊息經 `mask`）。所有保單分頁都讀不成（標頭壞）→ `PersonalDriveError(SCHEMA_INVALID)`，不回空表。
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
        raise drive.PersonalDriveError(ec.SCHEMA_INVALID)
    names = (sup.TAB_HOLDING_SUPPLEMENT, sup.TAB_POLICY_PROFILE)
    for name in names:
        if values.get(name):
            sup._check_header(name, values[name], mask=mask)
    supplement = {name: sup._reduce(name, values.get(name)) for name in names}
    return {
        "actor": ACTOR,
        "policy": {"rows": rows, "skipped_tabs": skipped, "invest_twd_parse_errors": parse_errors,
                   "read_estimate": {"tab_count": tab_count, "requests_per_load": 2, "actor": ACTOR}},
        "supplement": supplement,
    }
