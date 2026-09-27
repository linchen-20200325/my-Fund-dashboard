# -*- coding: utf-8 -*-
"""保單試算表兩張補充分頁 `_持倉補充`、`_保單資料` 的讀取（L1；`49` §6.3 N-4）。

本檔只讀，不寫。對 `POLICY_SHEET_ID` 那一本（`49` 6.2 T6：客戶 2026-09-27 核准）讀兩張由客戶
手填的底線分頁，逐格做**型別層**的解析（字串、日期、整數、值域），交回列號與原始儲存格。
**不做業務判定**：鍵的比對、重複與孤兒列、`DIRECT`、`last_synced_at` 的換算，一律由
L2 `services/v2_tables/alo_holdings.py` 做。

規則出處：
- 分頁規格：scratchpad 規格文件 `alo_sheet_tabs_spec.md`（定稿版）2.1、2.2 節；
  標頭用中文、第 1 列逐字比對。
- T6：試算表 ID 只讀 secret `POLICY_SHEET_ID`（`st.secrets` → 環境變數，經 `infra.config.get_secret`）；
  **沒有預設值，不退回 session 的 `policy_sheet_id`，也不退回 `macro_weights_sheet_id`、`SHEET_ID`**。
  缺值 → `PolicySupplementError(code="not_configured")`。
- 憑證只用服務帳戶（`google_service_account`）。⚠️ `49` 6.2 T6 說憑證「仍可走 OAuth 或服務帳戶兩條路」，
  本檔本輪只接服務帳戶；OAuth 那一條沒有做（回報列為待裁）。
- 標頭（比照 `repositories/settings_sheet_repository.py::_check_header`）：去掉第 1 列尾端空儲存格後
  逐字、逐欄比對；不符 → `PolicySupplementError(code="header_mismatch")`，**不猜欄位、不改寫標頭、不代寫標頭**。
  分頁不存在或完全零列 → 「尚未建立」（`tab_missing`），不是錯誤，也**不建分頁、不寫標頭**
  （規格 0.2 節：本模組對這兩張分頁不得寫入任何東西，包括零列時寫標頭）。
- 讀取一律取 `FORMATTED_VALUE` 字串。基金代號這類純數字字串（例 `0050`）以字串交回，前導 0 保留（U11）。
- 快取：60 秒手動快取，**只快取成功的讀取**；登記進 `infra.cache._CACHE_REGISTRY`，
  「全域刷新」一併清掉。冷卻沿用 `infra.gspread_retry`（actor 固定 `"sa"`）。

失敗訊息遮蔽：本檔是 L1，不得 import L2 的 `services/v2_tables/masking.py`。每個公開函式要求
呼叫端以關鍵字傳入 `mask`；本檔自己產生的每一句錯誤訊息先把**試算表 ID**換成記號、再過 `mask`。
⚠️ 試算表 ID 在這裡遮，是派工單的明文要求；`ACCEPTANCE.md` 7.2 丙把 `POLICY_SHEET_ID` 列為「不遮」，
兩者不一致（回報列為待裁）。本檔只遮**本檔拋出的錯誤訊息**，不動 7.2 的遮蔽鍵表。
`PolicySupplementError` 一律在 `except` 區塊之外拋出，`__cause__`／`__context__` 為 None。

⚠️ 遮蔽射程只到錯誤訊息與 `details["actual"]`：讀取結果的 `bad_rows[*]["cells"]` 是儲存格原文，
不遮（那是客戶手填的保單資料，不是憑證）。
"""

from __future__ import annotations

import math
import re
import threading
import time
from datetime import date
from typing import Any, Callable, Optional

from infra.config import get_secret

# ── 分頁名（規格 2.1、2.2，逐字；第一個字是半形底線）──────────────────────
TAB_HOLDING_SUPPLEMENT = "_持倉補充"
TAB_POLICY_PROFILE = "_保單資料"

# ── 欄位規格：(中文標頭逐字, 讀出後的欄名, 型別, 可空) ─────────────────────
# 讀出後的欄名：鍵欄用 `policy_id`／`fund_code`，其餘用 `44` 的欄名（L2 以此填 `44` 列）。
# 型別只有本檔用得到的幾種：`字串`、`日期`（只收 YYYY-MM-DD）、`整數`（非負、十進位）、
# `幣別`（ISO 4217 三個大寫英文字母）、`狀態`（`44` 4.4 三選一）。
HOLDING_SUPPLEMENT_SPEC = (
    ("保單編號", "policy_id", "字串", False),
    ("基金代號", "fund_code", "字串", False),
    ("持有起始日", "opened_on", "日期", False),
    # R1＝B（客戶 2026-09-27）：客戶填日期，L2 換成當日 12:00 台灣時間。本層只驗日期格式。
    ("最後核對日", "last_checked_on", "日期", False),
    ("類別", "bucket", "字串", True),
)
POLICY_PROFILE_SPEC = (
    ("保單編號", "policy_id", "字串", False),
    ("保單名稱", "policy_name", "字串", False),
    ("發行單位", "issuer", "字串", False),
    ("計價幣別", "ccy", "幣別", False),
    ("累計已繳保費（新臺幣元）", "premium_paid_twd", "整數", False),
    ("生效日", "opened_on", "日期", False),
    ("狀態", "status", "狀態", False),
)
TAB_SPECS = {
    TAB_HOLDING_SUPPLEMENT: HOLDING_SUPPLEMENT_SPEC,
    TAB_POLICY_PROFILE: POLICY_PROFILE_SPEC,
}
# `44` 4.4 `policy.status` 值域（U8：英文代碼）。L1 不得 import L2 的 contract，另寫一份，
# 由 tests/test_v2_tables_alo_holdings.py 與 contract 逐字比對。
STATUS_VALUES = ("active", "paid_up", "closed")

SECRET_KEY = "POLICY_SHEET_ID"
ACTOR = "sa"
CACHE_TTL_SEC = 60.0          # `49` §4.4
NOT_CONFIGURED_MESSAGE = "未設定保單試算表 ID（POLICY_SHEET_ID），不讀取"
NO_SERVICE_ACCOUNT_MESSAGE = "未設定服務帳戶（google_service_account）"
# 本檔自己用的遮蔽記號，與 `services/v2_tables/masking.py::MASK` 逐字相同（L1 不得 import L2；
# 由測試比對兩者相同）。
SHEET_ID_MASK = "‹已遮蔽›"

# 只收 ASCII 數字（`\d` 會吃全形數字，規格 R1 第 2 點要拒收全形）。
_DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
_INT_RE = re.compile(r"^[0-9]+$")
_CCY_RE = re.compile(r"^[A-Z]{3}$")

Mask = Callable[[str], str]


class PolicySupplementError(Exception):
    """補充分頁讀取失敗。訊息已先遮試算表 ID、再過呼叫端的 `mask`。

    `code`：`not_configured`（沒設 `POLICY_SHEET_ID`）／`no_service_account`／`header_mismatch`／
            `cooling`（冷卻中，未打上游）／`api`（上游讀取失敗）。
    """

    def __init__(self, message: str, *, code: str, http_status: Optional[int] = None,
                 remaining_sec: Optional[float] = None, details: Optional[dict] = None):
        super().__init__(message)
        self.code = code
        self.http_status = http_status
        self.remaining_sec = remaining_sec
        self.details = details or {}


# ════════════════════════ 儲存格解析 ════════════════════════

_clock = time.monotonic


def is_iso_date(text: str) -> bool:
    """整格恰好 `YYYY-MM-DD`（ASCII 數字、補零），且是真實存在的日曆日期。"""
    if not isinstance(text, str) or not _DATE_RE.match(text):
        return False
    try:
        return date.fromisoformat(text).isoformat() == text
    except ValueError:
        return False


def _parse_cell(header: str, kind: str, nullable: bool, text: str):
    """儲存格字串 → (值, 問題)。問題非 None 表示這一列不收。"""
    if text == "":
        return (None, None) if nullable else (None, f"{header}：不可空")
    if kind == "字串":
        return text, None
    if kind == "日期":
        if is_iso_date(text):
            return text, None
        return None, f"{header}：只收 YYYY-MM-DD 日期（{text!r}）"
    if kind == "整數":
        if not _INT_RE.match(text):
            return None, f"{header}：整數格式不符，只收不加千分位的十進位數字（{text!r}）"
        return int(text), None
    if kind == "幣別":
        if not _CCY_RE.match(text):
            return None, f"{header}：須為 ISO 4217 三個大寫英文字母（{text!r}）"
        return text, None
    if kind == "狀態":
        if text not in STATUS_VALUES:
            return None, f"{header}：不在值域 {STATUS_VALUES}（{text!r}）"
        return text, None
    raise ValueError(f"未知型別 {kind!r}（{header}）")


def _parse_rows(spec, values: list):
    """資料列（不含標頭）→ (records, bad_rows, blank_rows)。

    每格先去掉前後空白（規格 R1 第 1 點；鍵欄比對同樣只去前後空白）。
    record＝`{"_row": 試算表列號, "_raw": 補齊到欄數的字串列, 欄名: 值, ...}`。
    整列空白不是紀錄，只計數；超出規格欄數的格子有值 → 該列不收。
    """
    width = len(spec)
    records, bad, blank = [], [], 0
    for offset, raw in enumerate(values):
        row_no = offset + 2
        cells = [str(c) for c in raw]
        if all(c.strip() == "" for c in cells):
            blank += 1
            continue
        if len(cells) > width and any(c.strip() != "" for c in cells[width:]):
            bad.append({"row": row_no, "reason": f"超出 {width} 欄的儲存格有值", "cells": cells})
            continue
        cells = (cells + [""] * width)[:width]
        record = {"_row": row_no, "_raw": tuple(cells)}
        problem = None
        for (header, name, kind, nullable), text in zip(spec, cells):
            value, problem = _parse_cell(header, kind, nullable, text.strip())
            if problem:
                break
            record[name] = value
        if problem:
            bad.append({"row": row_no, "reason": problem, "cells": cells})
            continue
        records.append(record)
    return records, bad, blank


# ════════════════════════ 設定、連線、冷卻 ════════════════════════

def _hide_id(text: str, sheet_id: Optional[str]) -> str:
    """把訊息裡的試算表 ID（全文，以及 `describe_sheet_exc` 會印的前 12 字）換成記號。"""
    if not sheet_id:
        return text
    out = text.replace(sheet_id, SHEET_ID_MASK)
    prefix = sheet_id[:12]
    if len(prefix) == 12 and prefix != sheet_id:
        out = out.replace(prefix, SHEET_ID_MASK)
    return out


def policy_sheet_id(*, mask: Mask) -> str:
    """`POLICY_SHEET_ID`：`st.secrets` → 環境變數；沒有預設值、不退回任何別的鍵，缺值 fail loud。"""
    raw = get_secret(SECRET_KEY)
    text = raw.strip() if isinstance(raw, str) else ""
    if not text:
        raise PolicySupplementError(mask(NOT_CONFIGURED_MESSAGE), code="not_configured",
                                    details={"secret_key": SECRET_KEY})
    return text


def _service_account() -> Optional[Any]:
    raw = get_secret("google_service_account")
    if raw is None or raw == "" or (hasattr(raw, "__len__") and len(raw) == 0):
        return None
    return raw


def _make_client(creds):
    """服務帳戶 → gspread client（測試以 monkeypatch 換成假物件）。"""
    from repositories.policy._helpers import get_gspread_client
    return get_gspread_client(creds)


def _run(op: Callable, *, mask: Mask, open_sheet: bool = True):
    """開表 → op(client, spreadsheet, sheet_id)（`open_sheet=False` 時 spreadsheet 為 None），外面包冷卻與失敗登記。回傳 (sheet_id, op 的結果)。

    - 冷卻中 → 不打上游，`code="cooling"`。
    - `PolicySupplementError`（例如標頭不符）不是上游失敗，不登記冷卻，原樣往上拋。
    - 其餘例外 → 登記冷卻，轉成 `code="api"`；訊息先遮 ID、再過 `mask`，不帶出原始例外。
    """
    from infra.gspread_retry import (
        http_status_of, record_gspread_failure, record_gspread_success,
        should_skip_gspread, with_gspread_retry,
    )

    sheet_id = policy_sheet_id(mask=mask)
    creds = _service_account()
    if creds is None:
        raise PolicySupplementError(mask(NO_SERVICE_ACCOUNT_MESSAGE), code="no_service_account")
    skip, left, kind = should_skip_gspread(ACTOR, sheet_id)
    if skip:
        raise PolicySupplementError(
            mask(f"保單試算表暫停重試，還剩 {math.ceil(left)} 秒（上次失敗類別：{kind}）"),
            code="cooling", remaining_sec=left)
    failure = None
    result = None
    try:
        client = _make_client(creds)
        spreadsheet = with_gspread_retry(client.open_by_key, sheet_id) if open_sheet else None
        result = op(client, spreadsheet, sheet_id)
    except PolicySupplementError as exc:
        failure = exc
    except Exception as exc:  # noqa: BLE001 —— 轉成帶原文的 PolicySupplementError，不吞
        status = http_status_of(exc)
        record_gspread_failure(ACTOR, sheet_id, exc)
        name, raw = type(exc).__name__, str(exc)
        text = raw if raw.startswith(f"{name}:") else f"{name}: {raw}"
        failure = PolicySupplementError(mask(_hide_id(text, sheet_id)), code="api",
                                        http_status=status)
        del exc
    if failure is not None:
        failure.__cause__ = None
        failure.__context__ = None
        failure.__traceback__ = None
        raise failure
    record_gspread_success(ACTOR, sheet_id)
    return sheet_id, result


# ════════════════════════ 分頁讀取、標頭 ════════════════════════

def _a1_tab(name: str) -> str:
    return "'" + name.replace("'", "''") + "'"


def _read_tabs(spreadsheet, names) -> dict:
    """一次列出分頁、一次批次讀值（`FORMATTED_VALUE`）。`{名: 全部列 或 None（分頁不存在）}`。"""
    from infra.gspread_retry import with_gspread_retry

    titles = {ws.title for ws in with_gspread_retry(spreadsheet.worksheets)}
    present = [n for n in names if n in titles]
    out = {n: None for n in names}
    if present:
        resp = with_gspread_retry(
            spreadsheet.values_batch_get, [_a1_tab(n) for n in present],
            params={"valueRenderOption": "FORMATTED_VALUE"})
        ranges = (resp or {}).get("valueRanges", [])
        if len(ranges) != len(present):
            raise RuntimeError(f"批次讀取回傳 {len(ranges)} 段，預期 {len(present)} 段")
        for name, block in zip(present, ranges):
            out[name] = [list(r) for r in block.get("values", [])]
    return out


def _check_header(name: str, values, *, mask: Mask, sheet_id: str) -> None:
    """第 1 列逐字等於規格標頭（尾端空儲存格不算）；不符就停，不猜、不改寫。"""
    expected = [h for h, _n, _k, _nl in TAB_SPECS[name]]
    header = [str(c) for c in values[0]]
    while header and header[-1] == "":
        header.pop()
    if header != expected:
        missing = [h for h in expected if h not in header]
        extra = [h for h in header if h not in expected]
        actual = [mask(_hide_id(c, sheet_id)) for c in header]
        raise PolicySupplementError(
            mask(_hide_id(f"標頭與規格不符：分頁 {name}；規格 {expected}；試算表 {header}；"
                          f"缺 {missing}；多 {extra}", sheet_id)),
            code="header_mismatch",
            details={"tab": name, "expected": expected, "actual": actual})


# ════════════════════════ 快取（`49` §4.4）════════════════════════

_CACHE: dict = {}
_CACHE_LOCK = threading.Lock()
_CACHE_GEN = 0


def clear_cache() -> None:
    """清掉讀取快取並遞增世代計數（讀取期間被清過的結果不存快取）。"""
    global _CACHE_GEN
    with _CACHE_LOCK:
        _CACHE_GEN += 1
        _CACHE.clear()


class _SupplementCacheProxy:
    """把本檔的 60 秒快取登記進 `infra.cache._CACHE_REGISTRY`（「全域刷新」一併清掉）。
    `cache_clear` 只清本檔快取、不碰冷卻。統計欄全無（缺席＝不適用，不是 0）。"""
    __name__ = "_POLICY_SUPPLEMENT_CACHE"

    @staticmethod
    def cache_clear() -> None:
        clear_cache()

    @staticmethod
    def cache_info() -> dict:
        with _CACHE_LOCK:
            size = len(_CACHE)
        return {"name": "_POLICY_SUPPLEMENT_CACHE", "size": size, "ttl_sec": CACHE_TTL_SEC}


def _register_cache_proxy() -> None:
    from infra.cache import _CACHE_REGISTRY, register_cache
    if not any(getattr(f, "__name__", "") == _SupplementCacheProxy.__name__
               for f in _CACHE_REGISTRY):
        register_cache(_SupplementCacheProxy())


_register_cache_proxy()


def _cached(what: str, sheet_id: str, loader: Callable):
    now = _clock()
    with _CACHE_LOCK:
        hit = _CACHE.get((sheet_id, what))
        if hit is not None and now - hit[0] < CACHE_TTL_SEC:
            return hit[1]
        generation = _CACHE_GEN
    result = loader()
    with _CACHE_LOCK:
        if _CACHE_GEN == generation:
            _CACHE[(sheet_id, what)] = (_clock(), result)
    return result


def _reduce(name: str, values) -> dict:
    spec = TAB_SPECS[name]
    if not values:
        # 分頁不存在或完全零列 ＝ 尚未建立（不是錯誤，也不代寫標頭）
        return {"records": [], "bad_rows": [], "blank_rows": 0, "tab_missing": True}
    records, bad, blank = _parse_rows(spec, values[1:])
    return {"records": records, "bad_rows": bad, "blank_rows": blank, "tab_missing": False}


def load_supplement_tabs(*, mask: Mask) -> dict:
    """讀 `_持倉補充` 與 `_保單資料`（一次批次讀取）。

    回傳 `{分頁名: {"records", "bad_rows", "blank_rows", "tab_missing"}}`。
    任一張標頭不符 → `PolicySupplementError(code="header_mismatch")`，兩張都不回（不猜）。
    """
    sheet_id = policy_sheet_id(mask=mask)
    names = (TAB_HOLDING_SUPPLEMENT, TAB_POLICY_PROFILE)

    def loader():
        def op(_client, spreadsheet, _sid):
            tabs = _read_tabs(spreadsheet, names)
            for name in names:
                if tabs[name]:
                    _check_header(name, tabs[name], mask=mask, sheet_id=sheet_id)
            return tabs

        _sid, tabs = _run(op, mask=mask)
        return {name: _reduce(name, tabs[name]) for name in names}

    return _cached("supplement_tabs", sheet_id, loader)


# ════════════════════════ 保單分頁（既有 10 欄）════════════════════════

def _default_policy_loader(client, sheet_id):
    from repositories.policy.v2 import load_all_policies_v2_with_error
    from repositories.policy._helpers import get_invest_twd_parse_errors
    df, skipped = load_all_policies_v2_with_error(client, sheet_id, cache_user=ACTOR)
    return df, skipped, list(get_invest_twd_parse_errors())


_policy_loader = _default_policy_loader


def _native(value):
    """numpy 純量 → Python 原生型別（L2 只認 int／float／str；`numpy.int64` 不是 `int`）。其餘原樣。"""
    if type(value).__module__ == "numpy" and hasattr(value, "item"):
        return value.item()
    return value


def load_policy_holding_rows(*, mask: Mask) -> dict:
    """同一本（`POLICY_SHEET_ID`）的保單分頁持倉列：包一層既有的
    `repositories/policy/v2.py::load_all_policies_v2_with_error`（該函式自己有 60 秒快取，本層不再疊）。

    回傳 `{"rows": [dict, ...], "skipped_tabs": [{"tab", "error"}], "invest_twd_parse_errors": [...]}`。
    `rows` 的欄名是 `ALL_COLS_V2`（`policy_id`、`fund_code`、`fund_name`、`currency`、`invest_twd`、
    `units`、`avg_nav` …），**值照既有讀取函式交回的樣子，不改**：
    ⚠️ 既有讀取把空白的 `淨投資金額`／`持有單位數`／`平均買入單位成本` 讀成 0（U10 由 L2 處理）；
    ⚠️ 既有讀取用 `get_all_records`，純數字的代號可能被轉成數字、前導 0 消失（U11 由 L2 擋）。
    `skipped_tabs[*]["error"]` 與整本打不開時的錯誤訊息，先遮試算表 ID、再過 `mask`。
    """
    def op(client, _spreadsheet, sheet_id):
        df, skipped, parse_errors = _policy_loader(client, sheet_id)
        rows = [{k: _native(v) for k, v in r.items()} for r in df.to_dict(orient="records")]
        return {"rows": rows,
                "skipped_tabs": [{"tab": s.get("tab"),
                                  "error": mask(_hide_id(str(s.get("error", "")), sheet_id))}
                                 for s in skipped],
                "invest_twd_parse_errors": parse_errors}

    _sid, result = _run(op, mask=mask, open_sheet=False)
    return result
