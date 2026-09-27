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


def _run(op: Callable, *, mask: Mask, open_sheet: bool = True):
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
        failure = PolicySupplementError(mask(text), code="api",
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


def _default_policy_loader(client, sheet_id):
    """逐分頁讀保單分頁，每一列帶「分頁名＋試算表列號」。

    欄名對映、v1 分頁相容、數值欄的正規化，逐項沿用 `repositories/policy/v2.py::load_all_policies_v2_with_error`
    的做法與常數（`ALL_COLS_V2`、`EN_HEADERS_V2`、`_LEGACY_ZH_ALIASES_V2`、`_v1_frame_to_v2`、
    `_normalize_float`、`_normalize_div_cash_pct`、`parse_invest_twd`）；**不改 `v2.py` 一個字**。
    自己逐分頁讀的理由（第 2 輪總管裁定 5、6）：既有函式把各分頁 concat 後，列就只剩 concat 之後的 index，
    看不出是哪一分頁第幾列；本金欄也已經把「空白」「解析失敗」都變成 0。

    與既有函式不同的三處（刻意）：
    - 每列多 `_tab`（分頁名）、`_row`（試算表列號；`get_all_records` 保留中間空列，第 1 列是標頭，
      所以第 k 筆＝第 k+1 列 —— 讀 gspread 6.2.1 原始碼確認，沒有對真表實測）；
    - `invest_twd`：空白 → None（不是 0）；解析失敗 → None，並列入 `invest_twd_parse_errors`
      （`{"tab","row","raw","reason"}`）；**不寫** `repositories/policy/_helpers` 的全域登記表；
    - 沿用 `get_all_records` 的預設（會把純數字字串轉成數字）—— 改它是另一張工單；L2 依 U11 擋下。
    回傳 (rows, skipped_tabs, invest_twd_parse_errors)。
    """
    import pandas as pd
    from repositories.policy import _helpers as H
    from repositories.policy import v2 as V

    sh = H._with_quota_retry(client.open_by_key, sheet_id)
    tabs = [ws for ws in H._with_quota_retry(sh.worksheets)
            if not ws.title.startswith("_") and ws.title != H.DEFAULT_WORKSHEET]
    rows, skipped, parse_errors = [], [], []
    for ws in tabs:
        try:
            records = H._with_quota_retry(ws.get_all_records) or []
        except Exception as exc:  # noqa: BLE001 —— 與既有函式相同：單一分頁失敗略過，但分頁名與原因交出去
            skipped.append({"tab": ws.title, "error": f"{type(exc).__name__}: {exc}"})
            continue
        if not records:
            continue
        frame = pd.DataFrame(records)
        frame["_row"] = range(2, len(frame) + 2)
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
        for record in frame[list(V.ALL_COLS_V2) + ["_row"]].to_dict(orient="records"):
            row = {k: _native(v) for k, v in record.items()}
            for col in ("units", "avg_nav", "avg_fx"):
                row[col] = H._normalize_float(row[col])
            row["div_cash_pct"] = V._normalize_div_cash_pct(row["div_cash_pct"])
            raw = row["invest_twd"]
            if raw is None or (isinstance(raw, str) and raw.strip() == "") \
                    or (isinstance(raw, float) and math.isnan(raw)):
                row["invest_twd"] = None
            else:
                value, reason = H.parse_invest_twd(raw)
                row["invest_twd"] = value
                if reason is not None:
                    parse_errors.append({"tab": ws.title, "row": row["_row"], "raw": str(raw),
                                         "reason": reason})
            row["_tab"] = ws.title
            rows.append(row)
    return rows, skipped, parse_errors


_policy_loader = _default_policy_loader


def _native(value):
    """numpy 純量 → Python 原生型別（L2 只認 int／float／str；`numpy.int64` 不是 `int`）。其餘原樣。"""
    if type(value).__module__ == "numpy" and hasattr(value, "item"):
        return value.item()
    return value


def load_policy_holding_rows(*, mask: Mask) -> dict:
    """同一本（`POLICY_SHEET_ID`）的保單分頁持倉列（`_default_policy_loader`）。

    回傳 `{"rows": [dict, ...], "skipped_tabs": [{"tab", "error"}], "invest_twd_parse_errors": [...]}`。
    `rows` 的欄名是 `ALL_COLS_V2` 加上 `_tab`、`_row`。60 秒快取，鍵含試算表 ID；
    有任何分頁被略過就不快取（比照既有函式）。`skipped_tabs[*]["error"]` 過 `mask`（ID 不遮，7.2 丙）。
    """
    sheet_id = policy_sheet_id(mask=mask)

    def loader():
        def op(client, _spreadsheet, sid):
            rows, skipped, parse_errors = _policy_loader(client, sid)
            return {"rows": rows,
                    "skipped_tabs": [{"tab": t.get("tab"), "error": mask(str(t.get("error", "")))}
                                     for t in skipped],
                    "invest_twd_parse_errors": parse_errors}

        _sid, result = _run(op, mask=mask, open_sheet=False)
        return result

    return _cached("policy_rows", sheet_id, loader, cache_if=lambda r: not r["skipped_tabs"])
