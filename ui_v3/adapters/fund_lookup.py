# -*- coding: utf-8 -*-
"""路徑 B（單檔基本資料查詢）內部 adapter：入口攔截 ＋ L2 `build_profiles` 回傳形狀 → `FundLookupView`
（`DEC-2026-11-18-02`，限縮補充 `DEC-2026-11-18-01` R1；經 ChatGPT 總管派工單轉述客戶「同意」，**待核**；僅內部切片）。

設計依據 `docs/evidence/gate_d_path_b_contract_package_2026_11_18.md` 第 4～8 節——**該文件是未核准的設計參考，不是已核准契約**。
本檔**不是**頁面、**不是**資料接線；注入測試輸入不等於資料接線，不得以此宣稱路徑 B 已完成。

這個檔**不 import 任何 services／repositories／infra／shared／streamlit／網路／環境變數**：
- 取數函式（形如「把查詢字串交給 L2 `resolve_full_keys` 再交給 `build_profiles`、回傳其原樣 dict」的組裝端包裝）**必須由呼叫端明確注入**；
  本檔**不提供會觸發真實取數的預設**，不讀環境變數、不碰 secrets、不發網路請求、不寫任何持久層、不使用 ISIN resolver、不使用別名表。
- L2 的 status 字面與回傳鍵在本檔另存一份，由測試以 AST 讀 L2 原始碼鎖死（adapters 層不得 import `shared`，也不為了常數去載入 L2）。
- ⚠️ `build_profiles` 固定查 MoneyDJ、TDCC、FundClear 三個來源；本檔**只讀** MoneyDJ 來源狀態與四個欄位格（基金名稱、配息方式、成立日期、經理費率），
  **不讀**其餘來源與幣別格、`declared`、`table_wide_failed`、`rows`、任何 reason／raw／error 文字，也不解析自由文字推斷資料分歧。
  因此不得把本檔描述成「只用 MoneyDJ 取數」——上游取數仍會涉及三個來源（資料來源範圍屬契約包 Q4，未決）。

入口攔截（`screen_input`，次序固定、第一個命中者決定原因；全部發生在呼叫 loader **之前**，攔截案例 loader 呼叫次數為 0）：
0 非字串 → raise；1a 原始字串（未經任何 strip）總長度 > `INPUT_ECHO_MAX` → `code_format`；1 空字串或全 ASCII 空格 → `blank`；
2 含可印刷 ASCII 以外的任何字元 → `control_or_non_ascii`；3 網址形 → `url_shape`；4 ISIN 形（判斷前移除所有非英數字元，不檢查檢查碼）→ `isin_shape`；
5 `strip(' ')` 並轉大寫後以 `fullmatch` 比對 L2 的純代碼格式，不符 → `code_format`；6 放行，以 `raw.strip(' ')`（保留大小寫）呼叫 loader。
⚠️ 取數鍵通過這些檢查，**不等於**基金身分已確認，也不代表基金存在。

取數例外：只有 `LookupSourceError`（view model 層定義）與內建 `ConnectionError`／`TimeoutError` 轉成 `SOURCE_FAILED`（原因碼不含例外文字，log 只記型別名）；
**其餘例外（`TypeError`／`ValueError`／`KeyError` 等程式或契約錯誤）一律往外拋，不轉任何狀態**；不使用廣義 `OSError`／`Exception`。
（與 `exp_pool` 切片刻意不同。⚠️「程式錯誤不被偽裝成來源失敗」**僅對 adapter 層成立**；端到端**不成立**：真實 L2 `exp_profile._call` 會把 L1 的任何例外轉成 `failed` 結果，
最終仍呈現為 `SOURCE_FAILED`。）
⚠️ 取捨：基金名稱不合格（過長、含控制類字元、網址形）是 **raise `LookupContractError`**，而非降級成 `name_unconfirmed`。
單一來源的名稱異常因此會讓整頁拋契約錯誤，日後頁面層的單一例外邊界需接住；是否改映 `name_unconfirmed` 待總管／客戶。
⚠️ 控制類字元判斷用 `unicodedata.category` 以 `C` 開頭（含未指派碼位 `Cn`），結果**相依 Python 的 unicodedata 版本**：
新版 Unicode 才指派的字元在舊版直譯器會被判為 `Cn` 而拒絕。
⚠️ 身分揭露：真實 L2 `resolve_full_keys` 可能經別名表把輸入映為不同的 full_key；`RESULT` 欄位屬於 full_key，**不保證等於輸入代碼**，adapter 看不到 full_key。
日後 loader 是否要傳入 `mapping_hit`／full_key 是 Decision Gate，本切片不裁決。
⚠️ `MISSING` 涵蓋「來源沒提供」與「MoneyDJ 同標籤出現不同值」；`CONFLICT` 在現行真實 L2 對四欄不可達；要區分需 L2 結構化旗標（待客戶）。
⚠️ Q6 待客戶確認：ISIN 形多一字元的變體與含 `-` 後綴者放行並回顯；ISIN 形判斷會誤攔帶連字號的合法 12 字元代碼；裸主機名／IPv4（形如 `example.com`）不視為網址形，走 `code_format` 並可回顯。
契約不符一律 fail-closed：raise `LookupContractError`（訊息只含欄位名與型別名）。頁面層的單一例外邊界屬日後頁面的責任，本檔不攔截。

保守處理的未決題：Q5 缺值字樣／費率欄標記（本檔只輸出 `MISSING`，不含字樣）、Q6 `INPUT_ECHO_MAX` 與 ISIN 形判斷前移除分隔符、
S4-c 現行 L2 只對幣別使用 `inconsistent`（四個被讀的格若出現則映為 `CONFLICT`，不挑一個顯示）。
基金名稱格若為 `inconsistent` → 視同名稱未確認（`name_unconfirmed`）：名稱是身分綁定證據，不能是分歧狀態。
"""
from __future__ import annotations

import logging
import re
from typing import Callable, Optional

from ui_v3.viewmodels.fund_lookup import (
    INPUT_ECHO_MAX,
    REASON_BLANK,
    REASON_CODE_FORMAT,
    REASON_CONTROL_OR_NON_ASCII,
    REASON_ISIN_SHAPE,
    REASON_KEY_REJECTED,
    REASON_LOADER_IO_ERROR,
    REASON_NAME_UNCONFIRMED,
    REASON_NO_PAGE,
    REASON_SOURCE_COOLING,
    REASON_SOURCE_FAILED,
    REASON_SOURCE_NOT_LISTED,
    REASON_UNRECOGNIZED_PAGE,
    REASON_URL_SHAPE,
    FieldStatus,
    FieldView,
    FundLookupView,
    LookupContractError,
    LookupSourceError,
    LookupState,
    ProfileFields,
    is_ascii_printable,
    is_safe_echo,
    looks_like_isin,
    looks_like_url,
)

__all__ = ("L2_CELL_OK", "L2_CELL_NOT_READY", "L2_CELL_FETCH_FAILED", "L2_CELL_INCONSISTENT", "L2_SOURCE_OK", "L2_SOURCE_NOT_LISTED",
           "L2_SOURCE_FAILED", "L2_SOURCE_UNRECOGNIZED", "L2_SOURCE_NOT_FOUND", "L2_READ_CELL_FIELDS", "L2_PURE_CODE_PATTERN",
           "LookupContractError", "LookupSourceError", "screen_input", "adapt_profile_result", "lookup_fund", "not_queried")

# ＝ `services.v2_tables.exp_profile.STATUS_*`（儲存格狀態；測試以 AST 對照 L2 原始碼鎖死）。
L2_CELL_OK = "ok"
L2_CELL_NOT_READY = "not_ready"
L2_CELL_FETCH_FAILED = "fetch_failed"
L2_CELL_INCONSISTENT = "inconsistent"
_CELL_STATUSES = frozenset({L2_CELL_OK, L2_CELL_NOT_READY, L2_CELL_FETCH_FAILED, L2_CELL_INCONSISTENT})
# ＝ MoneyDJ 來源 status 字面（`exp_profile._L1_STATUSES["MoneyDJ"]` ＝ `declared_profile.STATUS_*`；測試鎖死）。
L2_SOURCE_OK = "ok"
L2_SOURCE_NOT_LISTED = "not_listed"
L2_SOURCE_FAILED = "failed"
L2_SOURCE_UNRECOGNIZED = "unrecognized_page"
L2_SOURCE_NOT_FOUND = "not_found"
_SOURCE_STATUSES = frozenset({L2_SOURCE_OK, L2_SOURCE_NOT_LISTED, L2_SOURCE_FAILED, L2_SOURCE_UNRECOGNIZED, L2_SOURCE_NOT_FOUND})
# 頁面無法確認的三種來源狀態 → 原因碼；每個來源 status 字面恰有一個去處（窮舉表測試）。
_UNMATCHED_BY_SOURCE_STATUS = {
    L2_SOURCE_UNRECOGNIZED: REASON_UNRECOGNIZED_PAGE,
    L2_SOURCE_NOT_FOUND: REASON_NO_PAGE,
    L2_SOURCE_NOT_LISTED: REASON_SOURCE_NOT_LISTED,
}
_SOURCE_KEY = "MoneyDJ"
#: 本檔實際讀取的四個儲存格（L2 還有一個幣別格，本檔不讀）。
L2_READ_CELL_FIELDS = ("fund_name", "dividend_policy", "inception_on", "mgmt_fee_rate_pct")
#: ＝ `services.v2_tables.fund_keys.PURE_CODE_PATTERN`（測試以 AST 對照 L2 原始碼鎖死）。
L2_PURE_CODE_PATTERN = r"^([A-Z0-9]{3,30}(?:-[A-Z0-9]{2,20})?)$"
_PURE_CODE = re.compile(L2_PURE_CODE_PATTERN)

_LOG = logging.getLogger(__name__)


def _need(ok: bool, field: str, expected: str, value: object) -> None:
    if not ok:
        raise LookupContractError(f"{field}: expected {expected}, got {type(value).__name__}") from None


def not_queried() -> FundLookupView:
    """頁面剛載入、使用者尚未送出：不帶任何值。"""
    return FundLookupView(LookupState.NOT_QUERIED)


def screen_input(raw: object) -> Optional[str]:
    """入口攔截（純函式；不呼叫任何外部東西）。回傳原因碼；放行回 None。非字串 → raise `LookupContractError`（程式錯誤，不轉成狀態）。"""
    _need(isinstance(raw, str), "raw_input", "str", raw)
    if len(raw) > INPUT_ECHO_MAX:                       # 1a：作用於未 strip 的原始字串，先於一切處理
        return REASON_CODE_FORMAT
    if raw.strip(" ") == "":                            # 1：空字串或全 ASCII 空格（tab、換行不屬 blank，歸規則 2）
        return REASON_BLANK
    if not is_ascii_printable(raw):                     # 2：正向白名單；作用於未 strip 的原始字串（不先 strip）
        return REASON_CONTROL_OR_NON_ASCII
    if looks_like_url(raw):                             # 3
        return REASON_URL_SHAPE
    if looks_like_isin(raw):                            # 4
        return REASON_ISIN_SHAPE
    if _PURE_CODE.fullmatch(raw.strip(" ").upper()) is None:   # 5：整段完全符合；只去 ASCII 空格
        return REASON_CODE_FORMAT
    return None


def _echo(raw: str) -> Optional[str]:
    """被攔截時要不要保留輸入原值：只有通過安全回顯檢查者保留，其餘一律 None（結構上不帶）。"""
    return raw if is_safe_echo(raw) else None


def _read_cell(cell_map: dict, field: str) -> tuple:
    """讀一個儲存格的 (status, value)；只看這兩個鍵，不讀 reason／raw／來源名／時間。"""
    _need(field in cell_map, f"cells.{field}", "present", cell_map)
    cell = cell_map[field]
    _need(isinstance(cell, dict), f"cells.{field}", "dict", cell)
    _need("status" in cell and "value" in cell, f"cells.{field}", "dict with status and value", cell)
    status, value = cell["status"], cell["value"]
    _need(isinstance(status, str) and status in _CELL_STATUSES, f"cells.{field}.status", "a known cell status", status)
    if status == L2_CELL_OK:
        _need(value is not None, f"cells.{field}.value", "non-None when status is ok", value)
    else:
        _need(value is None, f"cells.{field}.value", "None when status is not ok", value)
    return status, value


def _field(status: str, value: object) -> FieldView:
    if status == L2_CELL_OK:
        return FieldView(FieldStatus.VALUE, value)      # type: ignore[arg-type] — 型別由 FieldView 驗
    if status == L2_CELL_NOT_READY:
        return FieldView(FieldStatus.MISSING, None)
    if status == L2_CELL_INCONSISTENT:
        return FieldView(FieldStatus.CONFLICT, None)
    raise LookupContractError("cell status: fetch_failed is not allowed once the source is ok") from None


def adapt_profile_result(input_code: str, query_text: str, raw_result: object) -> FundLookupView:
    """L2 `build_profiles` 形狀的 dict → `FundLookupView`（純函式；不呼叫任何外部東西）。契約不符一律 raise `LookupContractError`。

    只讀 `cells[query_text]` 的四格（status、value）與 `source_status[query_text]["MoneyDJ"]` 的 status／cooling。
    狀態判定次序：L2 拒絕該鍵（來源狀態為空）→ 取不到 → 頁面無法確認 → 名稱未確認 → 有結果。
    """
    _need(isinstance(input_code, str), "input_code", "str", input_code)
    _need(screen_input(input_code) is None, "input_code", "an input that passed screening", input_code)
    _need(isinstance(query_text, str) and query_text == input_code.strip(" "), "query_text", "input_code stripped of ASCII spaces", query_text)
    _need(isinstance(raw_result, dict), "result", "dict", raw_result)
    missing = [key for key in ("cells", "source_status") if key not in raw_result]
    if missing:
        raise LookupContractError(f"result: missing keys {missing}") from None
    cells, statuses = raw_result["cells"], raw_result["source_status"]
    _need(isinstance(cells, dict) and set(cells) == {query_text}, "cells", "dict whose only key is the queried code", cells)
    _need(isinstance(statuses, dict) and set(statuses) == {query_text}, "source_status", "dict whose only key is the queried code", statuses)
    cell_map, entry = cells[query_text], statuses[query_text]
    _need(isinstance(cell_map, dict), "cells[code]", "dict", cell_map)
    _need(isinstance(entry, dict), "source_status[code]", "dict", entry)

    if not entry:                                       # L2 已拒絕該鍵、未取數
        return FundLookupView(LookupState.BLOCKED, input_code, REASON_KEY_REJECTED, None)

    _need(_SOURCE_KEY in entry, "source_status[code]", "an entry for the primary source", entry)
    source = entry[_SOURCE_KEY]
    _need(isinstance(source, dict), "source entry", "dict", source)
    _need("status" in source and "cooling" in source, "source entry", "dict with status and cooling", source)
    status, cooling = source["status"], source["cooling"]
    _need(isinstance(status, str) and status in _SOURCE_STATUSES, "source entry.status", "a known source status", status)
    _need(isinstance(cooling, bool), "source entry.cooling", "bool", cooling)

    if status == L2_SOURCE_FAILED:
        return FundLookupView(LookupState.SOURCE_FAILED, input_code, REASON_SOURCE_COOLING if cooling else REASON_SOURCE_FAILED, None)
    if status in _UNMATCHED_BY_SOURCE_STATUS:
        return FundLookupView(LookupState.PAGE_UNMATCHED, input_code, _UNMATCHED_BY_SOURCE_STATUS[status], None)

    # 來源 ok：先把四格全部驗過（形狀、與 value 的一致性），再決定狀態——未知一律 raise，不降級成缺值或失敗。
    cell_pairs = {field: _read_cell(cell_map, field) for field in L2_READ_CELL_FIELDS}
    for field, (cell_status, _value) in cell_pairs.items():
        _need(cell_status != L2_CELL_FETCH_FAILED, f"cells.{field}.status", "not fetch_failed when the source is ok", cell_status)
    _need(cell_pairs["mgmt_fee_rate_pct"][0] == L2_CELL_NOT_READY, "cells.mgmt_fee_rate_pct.status", "not_ready (no source by contract)",
          cell_pairs["mgmt_fee_rate_pct"][0])
    if cell_pairs["fund_name"][0] != L2_CELL_OK:        # 名稱是身分綁定證據：沒有它就不展示其他欄
        return FundLookupView(LookupState.PAGE_UNMATCHED, input_code, REASON_NAME_UNCONFIRMED, None)
    fields = ProfileFields(*(_field(*cell_pairs[field]) for field in L2_READ_CELL_FIELDS))
    return FundLookupView(LookupState.RESULT, input_code, None, fields)


def lookup_fund(loader: Callable[[str], object], raw_input: object) -> FundLookupView:
    """先攔截，再呼叫**呼叫端注入**的 `loader(query_text)`，把回傳適配成 `FundLookupView`。

    - `loader` 沒有預設值：本檔不知道、也不 import 真實的 L1／L2。
    - 攔截命中 → `BLOCKED`，**不呼叫 loader**；被安全攔截的輸入內容不進 view。
    - `loader` 拋 `LookupSourceError`／內建 `ConnectionError`／`TimeoutError` → `SOURCE_FAILED`（`loader_io_error`），例外字串丟棄、log 只記型別名；
      其餘例外原樣往外拋。回傳形狀不符 → `LookupContractError` 照樣往外拋（不吞、不轉成 `SOURCE_FAILED`）。
    """
    _need(callable(loader), "loader", "callable", loader)
    reason = screen_input(raw_input)
    if reason is not None:
        return FundLookupView(LookupState.BLOCKED, _echo(raw_input), reason, None)    # type: ignore[arg-type]
    query_text = raw_input.strip(" ")                   # type: ignore[union-attr] — screen_input 已保證是 str
    try:
        result = loader(query_text)
    except (LookupSourceError, ConnectionError, TimeoutError) as exc:
        _LOG.warning("fund lookup loader raised %s", type(exc).__name__)
        return FundLookupView(LookupState.SOURCE_FAILED, raw_input, REASON_LOADER_IO_ERROR, None)    # type: ignore[arg-type]
    return adapt_profile_result(raw_input, query_text, result)                         # type: ignore[arg-type]
