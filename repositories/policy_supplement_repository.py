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
呼叫端以關鍵字傳入 `mask`；本檔自己產生的每一句錯誤訊息都先過 `mask`（秘密值由呼叫端決定）。
**試算表 ID 不遮**：依 `ACCEPTANCE.md` 7.2 丙，`POLICY_SHEET_ID` 屬「讀到了、但本規則不遮」的鍵
（不是憑證；設定頁要能顯示「目前讀的是哪一本」）。
~~試算表 ID 在這裡遮，是派工單的明文要求~~ → 2026-09-27 第 2 輪撤銷（決策者：AI 總管；有意識的更正，
不是漏刪）：上一輪派工單要求遮 ID 是總管的錯，與 7.2 丙牴觸，本輪依 7.2 丙改回不遮。
`PolicySupplementError` 一律在 `except` 區塊之外拋出，`__cause__`／`__context__` 為 None。

⚠️ 遮蔽射程只到錯誤訊息與 `details["actual"]`：讀取結果的 `bad_rows[*]["cells"]` 是儲存格原文，
不遮（那是客戶手填的保單資料，不是憑證）。
"""

from __future__ import annotations

import copy
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

# 只收 ASCII 數字（`\d` 會吃全形數字，規格 R1 第 2 點要拒收全形）。
_DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
_INT_RE = re.compile(r"^[0-9]+$")
_CCY_RE = re.compile(r"^[A-Z]{3}$")

Mask = Callable[[str], str]


class PolicySupplementError(Exception):
    """補充分頁讀取失敗。訊息已過呼叫端的 `mask`（試算表 ID 不遮，`ACCEPTANCE.md` 7.2 丙）。

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


def _run(op: Callable, *, mask: Mask, open_sheet: bool = True,
         success_if: Callable = lambda _r: True):
    """開表 → op(client, spreadsheet, sheet_id)（`open_sheet=False` 時 spreadsheet 為 None），外面包冷卻與失敗登記。回傳 (sheet_id, op 的結果)。

    - 冷卻中 → 不打上游，`code="cooling"`。
    - `PolicySupplementError`（例如標頭不符）不是上游失敗，不登記冷卻，原樣往上拋。
    - 其餘例外 → 登記冷卻，轉成 `code="api"`；訊息過 `mask`（ID 不遮，7.2 丙），不帶出原始例外。
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
        message = f"保單試算表暫停重試，還剩 {math.ceil(left)} 秒（上次失敗類別：{kind}）"
        last = _LAST_SKIPPED.get(sheet_id)
        if last:
            # 第 6 輪 B 組 3／第 7 輪 3：冷卻期間不讀、不回資料，但列出最後一次被略過的**全部**分頁與原因，
            # 造成 429 的那張標「觸發冷卻」。存入時已過 mask。
            parts = [f"{tab}{'（觸發冷卻）' if trigger else ''}：{error}" for tab, error, trigger in last]
            message += "；最後一次被略過的分頁：" + "；".join(parts)
        raise PolicySupplementError(mask(message), code="cooling", remaining_sec=left)
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
        failure = PolicySupplementError(mask(text), code="api",
                                        http_status=status)
        del exc
    if failure is not None:
        failure.__cause__ = None
        failure.__context__ = None
        failure.__traceback__ = None
        raise failure
    if success_if(result):      # 部分失敗不算成功，不解除冷卻（第 3 輪裁定 3）
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


def _check_header(name: str, values, *, mask: Mask) -> None:
    """第 1 列逐字等於規格標頭（尾端空儲存格不算）；不符就停，不猜、不改寫。"""
    expected = [h for h, _n, _k, _nl in TAB_SPECS[name]]
    header = [str(c) for c in values[0]]
    while header and header[-1] == "":
        header.pop()
    if header != expected:
        missing = [h for h in expected if h not in header]
        extra = [h for h in header if h not in expected]
        actual = [mask(c) for c in header]
        raise PolicySupplementError(
            mask(f"標頭與規格不符：分頁 {name}；規格 {expected}；試算表 {header}；"
                 f"缺 {missing}；多 {extra}"),
            code="header_mismatch",
            details={"tab": name, "expected": expected, "actual": actual})


# ════════════════════════ 快取（`49` §4.4）════════════════════════

_CACHE: dict = {}
_CACHE_LOCK = threading.Lock()
_CACHE_GEN = 0


def clear_cache() -> None:
    """清掉讀取快取並遞增世代計數（讀取期間被清過的結果不存快取）；
    也清掉冷卻訊息用的「最後一次被略過的分頁」（第 7 輪 3）。不碰冷卻本身。"""
    global _CACHE_GEN
    _LAST_SKIPPED.clear()
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
        return {"name": CACHE_PROXY_NAME, "size": size, "ttl_sec": CACHE_TTL_SEC}


CACHE_PROXY_NAME = "_POLICY_SUPPLEMENT_CACHE"


def _registry_name(entry) -> str:
    """登記項的名稱：看**實例**的 `cache_info()["name"]`。

    ⚠️ 2026-09-27 第 2 輪更正：上一版拿 `getattr(實例, "__name__")` 去比 `類別.__name__` ——
    類別本體寫的 `__name__ = "_POLICY_SUPPLEMENT_CACHE"` 只有**實例**取得到；對**類別**取 `__name__`
    拿到的是 type 自己的類別名 `_SupplementCacheProxy`，兩邊恆不相等，去重判斷恆為假
    （實測 reload 一次就登記兩份），是死碼。
    """
    try:
        info = entry.cache_info()
    except Exception:  # noqa: BLE001 —— 別人的登記項沒有 cache_info 或會拋，就不是本檔的
        return ""
    return info.get("name", "") if isinstance(info, dict) else ""


def _register_cache_proxy() -> None:
    """登記一份；已有同名的舊登記（模組 reload 留下的）就**換掉**，
    否則「全域刷新」清到的是舊模組的快取、新模組的快取清不到。"""
    from infra.cache import _CACHE_REGISTRY, register_cache
    for entry in [e for e in _CACHE_REGISTRY if _registry_name(e) == CACHE_PROXY_NAME]:
        _CACHE_REGISTRY.remove(entry)
    register_cache(_SupplementCacheProxy())


_register_cache_proxy()


def _cached(what: str, sheet_id: str, loader: Callable, *, cache_if: Callable = lambda _r: True):
    """鍵含試算表 ID：換一本就不會讀到舊本。命中與存入都交**副本**，呼叫端改不到快取內容。"""
    now = _clock()
    with _CACHE_LOCK:
        hit = _CACHE.get((sheet_id, what))
        if hit is not None and now - hit[0] < CACHE_TTL_SEC:
            return copy.deepcopy(hit[1])
        generation = _CACHE_GEN
    result = loader()
    with _CACHE_LOCK:
        if _CACHE_GEN == generation and cache_if(result):
            _CACHE[(sheet_id, what)] = (_clock(), copy.deepcopy(result))
    return result


def _reduce(name: str, values) -> dict:
    spec = TAB_SPECS[name]
    if not values:
        # 分頁不存在或完全零列 ＝ 尚未建立（不是錯誤，也不代寫標頭）
        return {"records": [], "bad_rows": [], "blank_rows": 0, "tab_missing": True}
    records, bad, blank = _parse_rows(spec, values[1:])
    for item in bad:
        item["tab"] = name          # 第 2 輪裁定 6：以「分頁名＋列號」標示
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
                    _check_header(name, tabs[name], mask=mask)
            return tabs

        _sid, tabs = _run(op, mask=mask)
        return {name: _reduce(name, tabs[name]) for name in names}

    return _cached("supplement_tabs", sheet_id, loader)


# ════════════════════════ 保單分頁（既有 10 欄）════════════════════════

POLICY_TAB_SOURCE = "保單分頁"


INVEST_TWD_HEADERS = ("invest_twd", "淨投資金額")   # v2/v1 英文、v2 中文（兩欄都不經 numericise）
# 整數部分：不加千分位，或逗號三位一組；小數部分只准全為 0（第 4 輪總管裁定 B-C）。
_INVEST_TEXT_RE = re.compile(r"^(-?)([0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)(?:\.0+)?$")
INVEST_MAX_DIGITS = 18       # 比照 `services/v2_tables/settings_store.py::INT_MAX_DIGITS`（第 4 輪 B-D）
HEADER_ERROR_TEXT = "第 1 列不是標頭，或標頭有空白或重複的欄位"


def _invest_twd_from_text(raw):
    """本金欄原始文字 → (值, 問題)。空白 → (None, None)。判斷看原始文字，只做在本檔，不改 `_helpers.py`。

    收：整數字面，可帶負號；千分位逗號必須三位一組（`1,000`、`12,345,678`）；
    小數部分**全為 0** 才收（`1000.0`、`1,000.00` → 1000；**第 4 輪總管裁定 B-C**，改寫第 3 輪的全拒）。
    拒（解析失敗，原因附**完整**原文，不截斷）：
    - 小數部分不為 0、科學記號（第 3 輪裁定 5：`1,000.7`、`1000.5`、`1e3`）；
    - 千分位分組不合法（`1,00,0`、`,1000`、`1000,`；第 4 輪 B-D）；
    - 整數部分超過 `INVEST_MAX_DIGITS`（18）位（第 4 輪 B-D）；
    - 其他字元（`NT$1,000`、`1000元`、全形數字）。
    ⚠️ 與既有 `parse_invest_twd` 的刻意差異（等價鎖定測試逐格列出）：它把逗號全刪再 `float()`，
    所以接受錯誤分組、任意位數、非零小數（捨去）與科學記號。
    """
    text = "" if raw is None else str(raw)
    if text.strip() == "":
        return None, None
    compact = text.strip()
    match = _INVEST_TEXT_RE.match(compact)
    if not match:
        return None, f"只收整數（千分位須三位一組、小數部分只能是 0、不收科學記號或其他字元）（原始值：{text}）"
    digits = match.group(2).replace(",", "")
    if len(digits.lstrip("0") or "0") > INVEST_MAX_DIGITS:
        return None, f"超過 {INVEST_MAX_DIGITS} 位數（原始值：{text}）"
    value = int(digits)
    return (-value if match.group(1) else value), None


def _tab_error_text(exc: BaseException) -> str:
    """分頁讀取失敗的原因。gspread 的標頭檢查例外改寫成中文（第 3 輪裁定 7），保留例外類別名稱。"""
    name = type(exc).__name__
    raw = str(exc)
    if name == "GSpreadException" and ("header" in raw or "expected_headers" in raw):
        return f"{name}: {HEADER_ERROR_TEXT}"
    # 第 6 輪 B 組 4：gspread 的 APIError 自己的字串已以「APIError: 」開頭，不再重複前綴（比照 `_run`）。
    return raw if raw.startswith(f"{name}:") else f"{name}: {raw}"


def _default_policy_loader(client, sheet_id):
    """逐分頁讀保單分頁，每一列帶「分頁名＋試算表列號」。

    欄名對映、v1 分頁相容、數值欄的正規化，逐項沿用 `repositories/policy/v2.py::load_all_policies_v2_with_error`
    的做法與常數（`ALL_COLS_V2`、`EN_HEADERS_V2`、`_LEGACY_ZH_ALIASES_V2`、`_v1_frame_to_v2`、
    `_normalize_float`、`_normalize_div_cash_pct`）；本金欄改由本檔 `_invest_twd_from_text` 判斷；**不改 `v2.py` 一個字**。
    ⚠️ 兩條路重複約 25 行，已登記 `EXCEPTIONS.md` 8.3.P `P-POLICYREADDUPE-1`（總管裁定方案 (b)）；
    兩路等價（除本金欄）由 `tests/test_policy_supplement_repository.py` 的等價鎖定測試釘住。

    與既有函式不同之處（刻意）：
    - 每列多 `_tab`（分頁名）、`_row`（試算表列號；`get_all_records` 保留中間空列、第 1 列是標頭，
      所以第 k 筆＝第 k+1 列 —— 讀 gspread 6.2.1 原始碼確認，沒有對真表實測）、
      `_blank`（該列**每一欄**原始值都空白）；
    - `invest_twd`：以 `numericise_ignore=["all"]` 取原始文字判斷（其餘欄照 gspread 預設逐格
      `numericise`，與既有函式同；兩個本金標頭並存時取英文欄，與既有函式同）；空白 → None；
      解析失敗（非零小數、科學記號、千分位分組錯、超過 18 位）→ None，
      並列入 `invest_twd_parse_errors`（`{"tab","row","raw","reason"}`，`raw` 不截斷）；
      **不寫** `repositories/policy/_helpers` 的全域登記表；
    - `open_by_key`、`worksheets` 用 `with_gspread_retry`（5xx／連線層重試，與補充分頁同一套）；
      逐分頁 `get_all_records` 由本檔 `_fetch_policy_tab` 重試：只有狀態碼 429 才重試（第 7b 輪），
      不經過共用的 `_with_quota_retry`；
    - 分頁讀取失敗的例外物件一併交回（`_exc`），由呼叫端決定是否登記冷卻；
      gspread 的標頭例外改寫成中文（`HEADER_ERROR_TEXT`）。
    - 仍把純數字字串轉成數字（gspread 預設）—— 改它是另一張工單；L2 依 U11 擋下。
    回傳 (rows, skipped_tabs, invest_twd_parse_errors, 分頁數)。
    """
    rows, skipped, parse_errors = [], [], []
    tabs = _list_policy_tabs(client, sheet_id)
    for ws in tabs:
        try:
            raw_records = _fetch_policy_tab(ws)
        except Exception as exc:  # noqa: BLE001 —— 與既有函式相同：單一分頁失敗略過，但分頁名與原因交出去
            skipped.append({"tab": ws.title, "error": _tab_error_text(exc), "_exc": exc})
            continue
        tab_rows, tab_errors = _process_policy_tab(ws.title, raw_records)
        rows.extend(tab_rows)
        parse_errors.extend(tab_errors)
    return rows, skipped, parse_errors, len(tabs)


def _list_policy_tabs(client, sheet_id) -> list:
    """保單分頁清單（排除 `_` 開頭與 `Policies`）。`open_by_key`、`worksheets` 走 `with_gspread_retry`。"""
    from infra.gspread_retry import with_gspread_retry
    from repositories.policy import _helpers as H

    sh = with_gspread_retry(client.open_by_key, sheet_id)
    return [ws for ws in with_gspread_retry(sh.worksheets)
            if not ws.title.startswith("_") and ws.title != H.DEFAULT_WORKSHEET]


def _fetch_policy_tab(ws) -> list:
    """一張分頁的原始紀錄（兩個本金欄保留原文，其餘欄交給下一步 numericise）。失敗就拋。

    重試（第 7b 輪總管裁定）：**不經過**共用的 `repositories/policy/_helpers.py::_with_quota_retry`，
    改用本檔的判斷 —— 只有 `is_rate_limited(exc)`（HTTP 狀態碼 429）才依
    `infra.gspread_retry.DEFAULT_QUOTA_BACKOFFS` 退避重試；其他錯誤一律**第一次就拋出**，
    交給呼叫端的略過與分頁冷卻流程。最後一次仍 429 → 拋出原例外（不吞）。

    ⚠️ 待辦（另開工單，本輪不改共用檔）：共用的 `_with_quota_retry` 以 `is_quota_error` 的**字串比對**
    （訊息含「429」）判斷要不要重試，舊 App 也受影響。2026-09-27 實測：訊息含 `'PX-429'!A1` 的 400 錯誤、
    以及內含「429」字樣的 `ConnectionError`，都被白重試 4 次、睡 2＋4＋8＝14 秒。
    """
    from infra.gspread_retry import DEFAULT_QUOTA_BACKOFFS

    for attempt, delay in enumerate(DEFAULT_QUOTA_BACKOFFS):
        try:
            return ws.get_all_records(numericise_ignore=["all"]) or []
        except Exception as exc:  # noqa: BLE001 —— 只有真 429 才重試，其餘原樣拋出
            if not is_rate_limited(exc) or attempt == len(DEFAULT_QUOTA_BACKOFFS) - 1:
                raise
            del exc
        time.sleep(delay)
    return []


def _process_policy_tab(title: str, raw_records: list):
    """一張分頁的原始紀錄 → (rows, parse_errors)。純運算，不打上游。"""
    import pandas as pd
    from gspread.utils import numericise
    from repositories.policy import _helpers as H
    from repositories.policy import v2 as V

    rows, parse_errors = [], []
    if not raw_records:
        return rows, parse_errors
    records = []
    for raw in raw_records:
        record = {}
        for key, value in raw.items():
            # 兩個本金標頭都保留原始文字；對映之後落在 `invest_twd` 的那一欄才是本金 ——
            # 與既有函式同一套規則（兩欄並存時英文欄優先，第 4 輪 B-E）。
            record[key] = value if key in INVEST_TWD_HEADERS else numericise(value)
        record["_blank"] = all(str(v).strip() == "" for v in raw.values())
        records.append(record)
    frame = pd.DataFrame(records)
    frame["_row"] = range(2, len(frame) + 2)
    # 第 5 輪 A 組 6：兩個本金標頭並存時，讀的是英文欄 `invest_twd`；記下來讓 L2 在原因裡寫明。
    frame["_invest_both"] = all(h in frame.columns for h in INVEST_TWD_HEADERS)
    columns = set(frame.columns)
    if "fund_code" in columns or "基金代號" in columns:
        zh2en = {**V.EN_HEADERS_V2, **V._LEGACY_ZH_ALIASES_V2}
        frame = frame.rename(columns={zh: en for zh, en in zh2en.items()
                                      if zh in frame.columns and en not in frame.columns})
    else:
        frame = V._v1_frame_to_v2(frame)
    for col in V.ALL_COLS_V2:
        if col not in frame.columns:
            frame[col] = ""
    keep = list(V.ALL_COLS_V2) + ["_row", "_blank", "_invest_both"]
    for record in frame[keep].to_dict(orient="records"):
        row = {k: _native(v) for k, v in record.items()}
        for col in ("units", "avg_nav", "avg_fx"):
            row[col] = H._normalize_float(row[col])
        row["div_cash_pct"] = V._normalize_div_cash_pct(row["div_cash_pct"])
        raw_invest = row["invest_twd"]
        value, reason = _invest_twd_from_text(raw_invest)
        row["invest_twd"] = value
        if reason is not None:
            parse_errors.append({"tab": title, "row": row["_row"], "raw": str(raw_invest),
                                 "reason": reason})
        row["_tab"] = title
        rows.append(row)
    return rows, parse_errors


def _cache_get(key, *, copy_value: bool = True):
    now = _clock()
    with _CACHE_LOCK:
        hit = _CACHE.get(key)
        if hit is not None and now - hit[0] < CACHE_TTL_SEC:
            return True, (copy.deepcopy(hit[1]) if copy_value else hit[1]), _CACHE_GEN
        return False, None, _CACHE_GEN


def _cache_put(key, value, generation, *, copy_value: bool = True) -> None:
    with _CACHE_LOCK:
        if _CACHE_GEN == generation:
            _CACHE[key] = (_clock(), copy.deepcopy(value) if copy_value else value)


TAB_COOLDOWN_KIND = "unreachable"     # `shared/backoff_policy.py`：60 秒（第 7 輪 2）
_TAB_LAST_ERROR: dict = {}            # 分頁冷卻鍵 → 上次失敗原因（**存入前已過 mask**）


def tab_cooldown_key(sheet_id: str, title: str) -> str:
    """壞分頁短冷卻的鍵（第 7 輪 2）：只管這一張分頁，不碰整本鑰匙、也不碰配額鑰匙。"""
    return f"gspread:tab:{ACTOR}:{sheet_id}:{title}"


def is_rate_limited(exc: BaseException) -> bool:
    """配額錯誤的判斷（第 7 輪 1）：**只看 HTTP 狀態碼 == 429**，不做字串比對。

    拿不到狀態碼的例外（例如 `ConnectionError`）一律不算配額。
    ⚠️ 不改共用的 `infra.gspread_retry.is_quota_error`（它看訊息字串是否含「429」）；
    本檔只在「要不要登記配額冷卻」這一步改用狀態碼。
    """
    from infra.gspread_retry import http_status_of
    return http_status_of(exc) == 429


def _cached_policy_loader(client, sheet_id):
    """`_default_policy_loader` 的逐分頁快取版（第 6 輪總管裁定，撤回第 5 輪「部分結果快取 60 秒」）。

    依據：v3 `02`「只快取成功結果」與 `49` §4.4（「只快取成功的結果：有任何一張分頁被略過就算失敗、不快取」，
    E-1(b) 客戶核准的方針）。
    - 快取單位是**成功讀到的單一分頁**：鍵（試算表 ID、分頁名），TTL 60 秒；命中交副本。
    - 分頁清單（`worksheets`）成功讀到時也快取 60 秒（存的是 worksheet 物件本身，不複製）。
    - 讀失敗的分頁**不入快取**。
    - **整頁結果（含 `skipped_tabs`）不快取**；有任何略過就視為失敗（呼叫端不呼叫 `record_gspread_success`）。
    整頁結果不快取；逐分頁快取的每一筆都是成功結果；**此粒度解讀為總管判斷，待第二組確認**。

    壞分頁短冷卻（第 7 輪 2）：非 429 的分頁錯誤（確定性、暫時性都算）由呼叫端登記
    `tab_cooldown_key(試算表 ID, 分頁名)` 60 秒冷卻；冷卻期間**不重讀**該分頁，但照樣列在
    `skipped_tabs`，原因「冷卻中（還剩 N 秒），上次失敗：<經 mask 的原因>」。
    ⚠️ 讀取量：分頁約 50 張時，即使沒有壞分頁，每分鐘的讀取數也已接近 Google 試算表 API 的配額
    （每分鐘 60 次讀取，出自 Google 公開文件，**本組未實測**）。

    ⚠️ 分頁清單快取的已知限制（第 7 輪 4）：
    - 60 秒內新增或刪除的分頁可能還讀不到／還在讀 —— L2 的孤兒判定可能因此過早；
    - 快取的 worksheet 物件綁定建立它的那個 client（快取期間不會換成新 client）。
    - 只要任一分頁**讀取失敗**（不含冷卻中的略過），就順手作廢分頁清單快取，下一次重列。
    """
    from infra import source_backoff

    list_key = (sheet_id, "policy_tab_list")
    found, tabs, generation = _cache_get(list_key, copy_value=False)
    if not found:
        tabs = _list_policy_tabs(client, sheet_id)
        _cache_put(list_key, tabs, generation, copy_value=False)
    rows, skipped, parse_errors = [], [], []
    read_failed = False
    for ws in tabs:
        cooling, left, _kind = source_backoff.should_skip(tab_cooldown_key(sheet_id, ws.title))
        if cooling:
            last = _TAB_LAST_ERROR.get(tab_cooldown_key(sheet_id, ws.title), "")
            skipped.append({"tab": ws.title, "_cooling": True,
                            "error": f"冷卻中（還剩 {math.ceil(left)} 秒），上次失敗：{last}"})
            continue
        key = (sheet_id, "policy_tab", ws.title)
        found, cached, generation = _cache_get(key)
        if found:
            tab_rows, tab_errors = cached
        else:
            try:
                raw_records = _fetch_policy_tab(ws)
            except Exception as exc:  # noqa: BLE001 —— 失敗的分頁不入快取
                skipped.append({"tab": ws.title, "error": _tab_error_text(exc), "_exc": exc})
                read_failed = True
                continue
            tab_rows, tab_errors = _process_policy_tab(ws.title, raw_records)
            _cache_put(key, (tab_rows, tab_errors), generation)
        rows.extend(tab_rows)
        parse_errors.extend(tab_errors)
    if read_failed:
        with _CACHE_LOCK:
            _CACHE.pop(list_key, None)      # 第 7 輪 4：有分頁讀失敗 → 分頁清單快取作廢
    return rows, skipped, parse_errors, len(tabs)


_policy_loader = _cached_policy_loader


def _native(value):
    """numpy 純量 → Python 原生型別（L2 只認 int／float／str；`numpy.int64` 不是 `int`）。其餘原樣。"""
    if type(value).__module__ == "numpy" and hasattr(value, "item"):
        return value.item()
    return value


# 試算表 ID → [(分頁名, 已過 mask 的原因, 是否觸發 429 冷卻)]；冷卻訊息用（第 6 輪 B 組 3、第 7 輪 3）。
# 存入時就先過 mask，不保留未遮蔽的原文；整頁讀取成功時清除；`clear_cache`（含全域清除）一併清除。
_LAST_SKIPPED: dict = {}
ALL_TABS_FAILED_MESSAGE = "所有保單分頁都讀取失敗，不回空表"


def load_policy_holding_rows(*, mask: Mask) -> dict:
    """同一本（`POLICY_SHEET_ID`）的保單分頁持倉列。

    回傳 `{"rows": [dict, ...], "skipped_tabs": [{"tab", "error"}], "invest_twd_parse_errors": [...]}`。
    `rows` 的欄名是 `ALL_COLS_V2` 加上 `_tab`、`_row`、`_blank`、`_invest_both`（該分頁兩個本金標頭並存）。
    `skipped_tabs[*]["error"]` 過 `mask`（ID 不遮，7.2 丙）。

    快取（第 6 輪總管裁定；依據 v3 `02` 與 `49` §4.4）：**整頁結果不快取**；逐分頁快取成功讀到的分頁
    （見 `_cached_policy_loader`）。有任何分頁被略過就視為失敗：不呼叫 `record_gspread_success`。
    整頁結果不快取；逐分頁快取的每一筆都是成功結果；此粒度解讀為總管判斷，待第二組確認。
    - 分頁失敗若屬 429（**只看狀態碼**，`is_rate_limited`）→ 登記配額冷卻（第 3 輪裁定 3）；
      非 429 → 只對那一張分頁登記 60 秒短冷卻（第 7 輪 2），不碰整本鑰匙與配額鑰匙。
    - 冷卻中 → `code="cooling"`，訊息列出最後一次被略過的全部分頁與原因（存入時已過 `mask`），
      造成 429 的那張標「觸發冷卻」（第 6 輪 B 組 3、第 7 輪 3）。
    - 全部分頁都在失敗或冷卻 → `code="api"`。
    - **所有分頁都失敗** → `code="api"`，訊息帶各分頁原因，不回空表（第 6 輪 B 組 2）。
    """
    def op(client, _spreadsheet, sid):
        from infra import source_backoff
        from infra.gspread_retry import record_gspread_failure
        rows, skipped, parse_errors, tab_count = _policy_loader(client, sid)
        public, last = [], []
        for item in skipped:
            exc = item.get("_exc")
            error = mask(str(item.get("error", "")))
            trigger = exc is not None and is_rate_limited(exc)
            if trigger:
                record_gspread_failure(ACTOR, sid, exc)          # 真 429 → 配額冷卻（第 3 輪裁定 3）
            elif exc is not None:
                key = tab_cooldown_key(sid, item.get("tab"))    # 非 429 → 只冷卻這一張分頁（第 7 輪 2）
                _TAB_LAST_ERROR[key] = error
                source_backoff.record_failure(key, TAB_COOLDOWN_KIND)
            public.append({"tab": item.get("tab"), "error": error})
            last.append((item.get("tab"), error, trigger))
        if last:
            _LAST_SKIPPED[sid] = last
        else:
            _LAST_SKIPPED.pop(sid, None)                         # 整頁讀取成功 → 清除
        if skipped and len(skipped) == tab_count:
            detail = "；".join(f"{t['tab']}：{t['error']}" for t in public)
            raise PolicySupplementError(mask(f"{ALL_TABS_FAILED_MESSAGE}：{detail}"), code="api",
                                        details={"skipped_tabs": public})
        return {"rows": rows, "skipped_tabs": public, "invest_twd_parse_errors": parse_errors}

    # 有分頁被略過時不算整次成功 —— 不呼叫 `record_gspread_success`，否則剛登記的配額冷卻會被當場解除。
    _sid, result = _run(op, mask=mask, open_sheet=False,
                        success_if=lambda r: not r["skipped_tabs"])
    return result
