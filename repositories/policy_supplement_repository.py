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


COOLING_LIST_MAX_ACTUAL = 3     # 第 11 輪 3：冷卻訊息除觸發冷卻的那張外，最多再列幾張有實際錯誤的分頁


def _cooling_skip_summary(last) -> str:
    """冷卻訊息裡的略過清單（第 11 輪 3，B 組建議 2：截斷）。

    只列「觸發冷卻」的那張（標「（觸發冷卻）」），加上最多 `COOLING_LIST_MAX_ACTUAL` 張**實際讀取失敗**的分頁；
    其餘（未讀、冷卻中、超出上限的）合計寫「另有 N 張未讀或未列出」。存入時已過 mask。
    """
    triggers = [(tab, error) for tab, error, trigger, _actual in last if trigger]
    actual = [(tab, error) for tab, error, trigger, is_actual in last
              if is_actual and not trigger][:COOLING_LIST_MAX_ACTUAL]
    parts = [f"{tab}（觸發冷卻）：{error}" for tab, error in triggers]
    parts += [f"{tab}：{error}" for tab, error in actual]
    rest = len(last) - len(triggers) - len(actual)
    if rest > 0:
        parts.append(f"另有 {rest} 張未讀或未列出")
    return "；".join(parts)


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
            message += "；最後一次被略過的分頁：" + _cooling_skip_summary(last)
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
    也清掉冷卻訊息用的「最後一次被略過的分頁」（第 7 輪 3），以及本檔的分頁冷卻與其上次原因（第 8 輪 6）。
    ~~不碰 `infra.source_backoff` 的冷卻（配額鑰匙、整本鑰匙）。~~
    第 13 輪 4（B 建議 3）更正：**一併解除本檔讀過的每一本試算表的整本鑰匙**（`sheet_key`），並清掉降級狀態
    （`_DEGRADED`）—— 客戶修好試算表之後按重整就能立刻重讀，不必等 300 秒。
    **配額鑰匙仍不碰**：它是整把服務帳戶憑證共用的，解除它會讓其他試算表一起重打一個正在限流的來源。
    「本檔讀過的試算表」＝快取、分頁冷卻、降級狀態、最後略過清單裡出現過的試算表 ID，加上目前設定的
    `POLICY_SHEET_ID`（讀不到就略過，不拋錯）。"""
    global _CACHE_GEN
    sheet_ids = set(_LAST_SKIPPED)
    _LAST_SKIPPED.clear()
    with _CACHE_LOCK:
        sheet_ids |= {k[0] for k in _CACHE if isinstance(k, tuple) and k}
        sheet_ids |= {k[0] for k in _TAB_COOLDOWN}
        sheet_ids |= set(_DEGRADED)
        _TAB_COOLDOWN.clear()          # 第 8 輪 6：分頁冷卻住在本檔，清快取時一併清
        _TAB_LAST_ERROR.clear()
        _DEGRADED.clear()              # 第 13 輪 4
        _CACHE_GEN += 1
        _CACHE.clear()
    try:
        raw = get_secret(SECRET_KEY)
        if isinstance(raw, str) and raw.strip():
            sheet_ids.add(raw.strip())
    except Exception:  # noqa: BLE001 —— 清快取不因讀不到設定而失敗；只是少解一把鑰匙
        pass
    from infra.gspread_retry import sheet_key
    from infra.source_backoff import record_success
    for sid in sheet_ids:
        record_success(sheet_key(ACTOR, sid))     # 第 13 輪 4：只解整本鑰匙，不解配額鑰匙


class _SupplementCacheProxy:
    """把本檔的 60 秒快取登記進 `infra.cache._CACHE_REGISTRY`（「全域刷新」一併清掉）。
    `cache_clear` 走 `clear_cache`：~~只清本檔快取、不碰冷卻~~ 第 13 輪 4 起一併清分頁冷卻、降級狀態與
    本檔讀過之試算表的整本鑰匙（配額鑰匙不碰）。統計欄全無（缺席＝不適用，不是 0）。"""
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
    回傳 (rows, skipped_tabs, invest_twd_parse_errors, 分頁數, 讀成功的分頁數)。
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
    return rows, skipped, parse_errors, len(tabs), len(tabs) - len(skipped)


def _list_policy_tabs(client, sheet_id) -> list:
    """保單分頁清單（排除 `_` 開頭與 `Policies`）。`open_by_key`、`worksheets` 走 `with_gspread_retry`。"""
    from infra.gspread_retry import with_gspread_retry
    from repositories.policy import _helpers as H

    sh = with_gspread_retry(client.open_by_key, sheet_id)
    return [ws for ws in with_gspread_retry(sh.worksheets)
            if not ws.title.startswith("_") and ws.title != H.DEFAULT_WORKSHEET]


def _is_retryable_status(exc: BaseException) -> bool:
    """本檔逐分頁重試的判斷（第 8 輪 3）：**只看狀態碼** —— 429 或 5xx 才重試；拿不到狀態碼的不重試。"""
    from infra.gspread_retry import http_status_of
    status = http_status_of(exc)
    return status == 429 or (isinstance(status, int) and 500 <= status <= 599)


PER_CALL_SLEEP_BUDGET_SEC = 10.0
# 第 9 輪 1：單次呼叫（一次 `load_policy_holding_rows`）的逐分頁重試**總睡眠**上限。
# 理由：5xx／429 短路之後，最壞情形是「每張分頁都失敗幾次才成功」—— 每張各睡一點、加起來卻很長；
# 這條上限是第二道保險，讓一次畫面重跑不會卡太久。一張分頁最多睡 1＋2＋4＝7 秒，所以 10 秒
# 允許一張分頁把重試用完，再多一張就停。超過就拋出最後一次的例外，呼叫端其餘分頁一律不讀；
# 預算用完的那一張**不登記分頁冷卻**（第 10 輪 5：它不是自己壞，是本次的等待額度用完）。
# ⚠️ 射程（第 10 輪 4）：本預算**只涵蓋逐分頁讀取**（`_fetch_policy_tab`）。保單分頁的 `open_by_key`
# 與 `worksheets` 走共用的 `with_gspread_retry`，其重試等待**不計入**本預算 —— 所以單次呼叫的最壞等待
# 約 24 秒（本預算 10 秒＋那兩支共用重試的等待；本組依原始碼推算，未實測）；補充分頁的 `_run` 另有自己的
# 重試，也不計入。本輪不改共用的 `with_gspread_retry`。
# ⚠️ 讀取量（第 10 輪 6）：分頁數約 50 時，每分鐘讀取數本身就貼著配額上限（上限值來源同
# `_cached_policy_loader` docstring 的註記）—— 本預算只限制等待，不限制讀取數。


def _fetch_policy_tab(ws, budget=None, retry_5xx: bool = True) -> list:
    """一張分頁的原始紀錄（兩個本金欄保留原文，其餘欄交給下一步 numericise）。失敗就拋。

    重試（第 7b 輪總管裁定、第 8 輪 3 擴充）：**不經過**共用的
    `repositories/policy/_helpers.py::_with_quota_retry`，改用本檔的判斷 —— 只有狀態碼 **429 或 5xx**
    才依 `infra.gspread_retry.DEFAULT_QUOTA_BACKOFFS`（1／2／4／8 秒）退避重試；其他錯誤一律**第一次就拋出**。
    重試用完仍失敗 → 拋出原例外（不吞），交給呼叫端：429 → 配額冷卻；其他 → 分頁冷卻（或整本冷卻，見 op）。
    `retry_5xx=False`（降級模式，第 13 輪 1(a)）：5xx 不重試、只讀 1 次、不睡；429 照舊重試。

    ⚠️ 待辦（另開工單，本輪不改共用檔；兩件併成一張）：
    (1) 共用的 `_with_quota_retry` 以 `is_quota_error` 的**字串比對**（`429`／`Quota exceeded`／
        `RATE_LIMIT`／`RESOURCE_EXHAUSTED`）判斷要不要重試，
        舊 App 也受影響。2026-09-27 實測：訊息含 `'PX-429'!A1` 的 400 錯誤、以及內含「429」字樣的
        `ConnectionError`，都被白重試 4 次、睡 2＋4＋8＝14 秒。
    (2) 重試迴圈目前有三份（`infra.gspread_retry` 的兩支＋本函式）；日後收斂為 `with_quota_retry`
        接受「要不要重試」的判斷函式參數，三處共用。
    """
    from infra.gspread_retry import DEFAULT_QUOTA_BACKOFFS

    for attempt, delay in enumerate(DEFAULT_QUOTA_BACKOFFS):
        try:
            return ws.get_all_records(numericise_ignore=["all"]) or []
        except Exception as exc:  # noqa: BLE001 —— 只有 429／5xx 才重試，其餘原樣拋出
            if (not _is_retryable_status(exc) or (not retry_5xx and _is_server_error(exc))
                    or attempt == len(DEFAULT_QUOTA_BACKOFFS) - 1):
                raise
            if budget is not None and budget["slept"] + delay > PER_CALL_SLEEP_BUDGET_SEC:
                budget["exhausted"] = True       # 第 9 輪 1：總睡眠預算用完 → 不再睡，拋出這一次的例外
                raise
            del exc
        if budget is not None:
            budget["slept"] += delay
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


TAB_COOLDOWN_KIND = "unreachable"     # 冷卻長度取 `shared/backoff_policy.py` 的這一類：60 秒（第 7 輪 2）
TAB_COOLDOWN_KIND_5XX = "server_error"   # 5xx 造成的分頁冷卻：300 秒（第 10 輪 2）
SHEET_ESCALATION_KIND = "server_error"   # 5xx 短路升級整本時，整本鑰匙的冷卻類別（第 10 輪 1）


DEGRADED_WINDOW_FACTOR = 3     # 第 13 輪 1：降級模式的觀察期 ＝ 3 × `server_error` 冷卻（900 秒）
_DEGRADED: dict = {}           # 試算表 ID → 最近一次「5xx 短路或整本升級」的時間（`_tab_clock`）


def degraded_window_sec() -> float:
    """降級模式的觀察期（第 13 輪 1）：`DEGRADED_WINDOW_FACTOR` × `cooldown_for(server_error)`（3 × 300 ＝ 900 秒）。"""
    from infra.source_backoff import cooldown_for
    return DEGRADED_WINDOW_FACTOR * cooldown_for(SHEET_ESCALATION_KIND)


def is_degraded(sheet_id: str) -> bool:
    """這本試算表是否在降級模式（最近 `degraded_window_sec()` 秒內發生過 5xx 短路或整本升級）。到期的當場移除。"""
    with _CACHE_LOCK:
        since = _DEGRADED.get(sheet_id)
        if since is None:
            return False
        if _tab_clock() - since >= degraded_window_sec():
            _DEGRADED.pop(sheet_id, None)
            return False
        return True


def _mark_degraded(sheet_id: str) -> None:
    with _CACHE_LOCK:
        _DEGRADED[sheet_id] = _tab_clock()


def escalated_tab_cooldown_sec() -> float:
    """升級整本時，觸發短路那張與探測失敗那張的分頁冷卻（第 12 輪 1）：整本冷卻＋分頁 5xx 冷卻（300＋300＝600 秒）。

    理由：整本冷卻結束時這兩張仍在冷卻中，下一輪就跳過它們、改讀別張，打破「每 5 分鐘同兩張觸發升級」的循環。
    長度取自 `shared/backoff_policy.py`（`cooldown_for`），不寫死秒數。
    """
    from infra.source_backoff import cooldown_for
    return cooldown_for(SHEET_ESCALATION_KIND) + cooldown_for(TAB_COOLDOWN_KIND_5XX)
# 壞分頁短冷卻（第 8 輪 5 改存本檔）：鍵（試算表 ID, 分頁名）→ 到期時間。
# 理由：`infra/source_backoff` 全域最多記 `BACKOFF_MAX_TRACKED_HOSTS`（128）把鑰匙，滿了就擠掉最舊的一把 ——
# 大量壞分頁若也放進去，會把配額鑰匙、整本鑰匙擠掉，讓該冷卻的來源被照打。分頁冷卻只有本檔自己讀，放本檔即可。
# 時鐘沿用 `infra.source_backoff._clock`（同一個 monotonic；測試注入同一個假時鐘）。
# 為何不違背 `infra/gspread_retry.py` 排除 per-worksheet 粒度的理由（第 9 輪 6）：那段排除的是「把 403／配額
# 這類**整本或整把憑證**的錯誤切到分頁去記」—— 那會讓同一本壞掉的試算表每張分頁各被打一次。本 dict 只收
# **單張分頁自身**的錯誤（例如那一張標頭壞了）；整本錯誤走升級（改登記整本 sheet 鑰匙，兩種條件見
# `load_policy_holding_rows` 的 op），配額錯誤走配額鑰匙。
# 冷卻長度（第 10 輪 2）：5xx 造成的分頁冷卻取 `server_error`（300 秒）；其他分頁自身錯誤（例如標頭錯誤、
# 非 429／非 5xx 的 HTTP 錯誤）取 `unreachable`（60 秒）。
_TAB_COOLDOWN: dict = {}
_TAB_LAST_ERROR: dict = {}            # （試算表 ID, 分頁名）→ 上次失敗原因（**存入前已過 mask**）
QUOTA_UNREAD_TEXT = "配額冷卻中，未讀"
UPSTREAM_5XX_UNREAD_TEXT = "上游暫時失敗（5xx），未讀"
BUDGET_UNREAD_TEXT = "單次讀取的重試等待已達上限（10 秒），未讀"


def _invalidates_tab_list(exc: BaseException) -> bool:
    """讀取失敗要不要作廢分頁清單快取（第 12 輪 2）：非 HTTP 錯誤（拿不到狀態碼）或 4xx（429 除外）才作廢。"""
    from infra.gspread_retry import http_status_of
    status = http_status_of(exc)
    return status is None or (isinstance(status, int) and 400 <= status <= 499 and status != 429)


def _is_server_error(exc: BaseException) -> bool:
    from infra.gspread_retry import http_status_of
    status = http_status_of(exc)
    return isinstance(status, int) and 500 <= status <= 599


def _tab_clock() -> float:
    from infra import source_backoff
    return source_backoff._clock()


def tab_cooldown_key(sheet_id: str, title: str) -> tuple:
    """壞分頁短冷卻的鍵：只管這一張分頁，不碰整本鑰匙、也不碰配額鑰匙。"""
    return (sheet_id, title)


def tab_cooling(sheet_id: str, title: str) -> tuple:
    """(是否冷卻中, 剩餘秒數)。到期的當場移除。"""
    key = tab_cooldown_key(sheet_id, title)
    with _CACHE_LOCK:
        until = _TAB_COOLDOWN.get(key)
        if until is None:
            return False, 0.0
        left = until - _tab_clock()
        if left <= 0:
            _TAB_COOLDOWN.pop(key, None)
            _TAB_LAST_ERROR.pop(key, None)        # 第 9 輪 3：一起移除
            return False, 0.0
        return True, left


def _record_tab_cooldown(sheet_id: str, title: str, masked_error: str,
                         kind: str = TAB_COOLDOWN_KIND, seconds=None) -> None:
    """登記一張分頁的冷卻（長度依 `kind`）；寫入時順手清掉所有已到期的項目（第 9 輪 3）。

    第 10 輪 8 更正：本 dict **沒有硬上限**；項目數受限於「冷卻期內失敗過的分頁數」（到期項目在寫入與查詢時移除）。
    """
    from infra.source_backoff import cooldown_for
    key = tab_cooldown_key(sheet_id, title)
    with _CACHE_LOCK:
        now = _tab_clock()
        for old in [k for k, until in _TAB_COOLDOWN.items() if until <= now]:
            _TAB_COOLDOWN.pop(old, None)
            _TAB_LAST_ERROR.pop(old, None)
        for old in [k for k in _TAB_LAST_ERROR if k not in _TAB_COOLDOWN]:
            _TAB_LAST_ERROR.pop(old, None)
        _TAB_COOLDOWN[key] = now + (cooldown_for(kind) if seconds is None else seconds)
        _TAB_LAST_ERROR[key] = masked_error


def _status_class(status):
    """同類升級用的 HTTP 狀態碼分類（第 11 輪 2）：4xx 各碼各自一類、5xx 全部一類；其餘原值。"""
    if isinstance(status, int) and 500 <= status <= 599:
        return "5xx"
    return status


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

    壞分頁冷卻（第 7 輪 2；第 8 輪 5 改存本檔 `_TAB_COOLDOWN`；第 10 輪 2 分長短）：非 429 的分頁錯誤
    （5xx 已先經本檔重試）由呼叫端登記（試算表 ID, 分頁名）冷卻 —— 5xx 300 秒、其他 60 秒；
    例外：5xx 短路且本次沒有任何分頁產出資料 → 改登記整本（見 `load_policy_holding_rows`），
    ~~不登記分頁冷卻~~ 觸發短路與探測失敗的那兩張改登記 600 秒分頁冷卻（第 12 輪 1）；
    重試等待預算用完的那一張也不登記。冷卻期間**不重讀**該分頁，但照樣列在
    `skipped_tabs`，原因「冷卻中（還剩 N 秒），上次失敗：<經 mask 的原因>」。
    ⚠️ 讀取量：分頁約 50 張時，即使沒有壞分頁，每分鐘的讀取數也已接近 Google 試算表 API 的配額
    （每分鐘 60 次讀取；據 `infra/gspread_retry.py` 註記，取自官方頁的搜尋摘要，未讀到一手頁面；**本組未實測**）。

    ⚠️ 分頁清單快取的已知限制（第 7 輪 4）：
    - 60 秒內新增或刪除的分頁可能還讀不到／還在讀 —— L2 的孤兒判定可能因此過早；
    - 快取的 worksheet 物件綁定建立它的那個 client（快取期間不會換成新 client）。
    - ~~只要任一分頁**讀取失敗**（不含冷卻中的略過），就順手作廢分頁清單快取，下一次重列。~~
      第 12 輪 2 更正（B 建議 2、A 建議 2b）：只有**非 HTTP 錯誤或 4xx（不含 429）**的讀取失敗才作廢 ——
      那兩類可能代表分頁被刪或改名；5xx 與 429 是上游暫時狀況，與分頁清單無關，作廢只會讓每次重跑多 2 次讀取。

    短路（v3 `02`「失敗時退避，不連續轟炸來源」）：本次呼叫裡**還需要打上游**的其餘分頁一律不讀
    （已在分頁快取裡的照用），列入 `skipped_tabs`：
    - 任一分頁重試用完仍是 429 → 原因「配額冷卻中，未讀」（第 8 輪 2；配額冷卻由呼叫端登記）；
    - 任一分頁重試用完仍是 5xx → 原因「上游暫時失敗（5xx），未讀」（第 9 輪 1）；
    - 單次呼叫的逐分頁總睡眠超過 `PER_CALL_SLEEP_BUDGET_SEC` → 原因「單次讀取的重試等待已達上限（10 秒），未讀」。
    5xx 短路後若本次沒有任何分頁產出資料、且預算沒用完 → 探測一張未讀分頁（`_probe_after_5xx`，第 11 輪 1）。

    降級模式（第 13 輪 1，總管裁定；取代「反覆以一張探測推定整本故障」）：本試算表在最近
    `degraded_window_sec()`（3 × 300 ＝ 900 秒）內發生過 5xx 短路或整本升級時 ——
    (a) 5xx 不重試，只讀 1 次、不睡；(b) 不做 5xx 短路：需要打上游的分頁各讀 1 次（上限就是分頁數）；
    (c) 不再升級整本：讀失敗的分頁照登記分頁冷卻（5xx 300 秒）；(d) 好分頁照常讀、照常入快取。
    第 13b 輪：降級期間又有 5xx 讀取失敗 → 延長降級（後果見 `load_policy_holding_rows` docstring）。
    429 的重試、配額短路與總睡眠預算照舊。非降級模式維持探測與升級（冷啟動遇到整本故障仍升級 300 秒）。
    降級狀態的觸發點在 `load_policy_holding_rows` 的 op（本次有 5xx 短路或整本升級就記下時間）。
    回傳 (rows, skipped_tabs, invest_twd_parse_errors, 分頁數, 本次產出資料的分頁數〔快取命中＋新讀成功〕)。
    """
    list_key = (sheet_id, "policy_tab_list")
    found, tabs, generation = _cache_get(list_key, copy_value=False)
    if not found:
        tabs = _list_policy_tabs(client, sheet_id)
        _cache_put(list_key, tabs, generation, copy_value=False)
    rows, skipped, parse_errors = [], [], []
    read_failed = False
    halt_reason = ""          # 第 8 輪 2（429）、第 9 輪 1（5xx、總睡眠預算）：其餘要打上游的分頁不讀
    served = 0                # 本次產出資料的分頁數（快取命中＋新讀成功）
    budget = {"slept": 0.0, "exhausted": False}
    degraded = is_degraded(sheet_id)      # 第 13 輪 1：降級模式 → 5xx 不重試、不短路、不探測
    for ws in tabs:
        cooling, left = tab_cooling(sheet_id, ws.title)
        if cooling:
            last = _TAB_LAST_ERROR.get(tab_cooldown_key(sheet_id, ws.title), "")
            skipped.append({"tab": ws.title, "_cooling": True,
                            "error": f"冷卻中（還剩 {math.ceil(left)} 秒），上次失敗：{last}"})
            continue
        key = (sheet_id, "policy_tab", ws.title)
        found, cached, generation = _cache_get(key)
        if found:
            tab_rows, tab_errors = cached
        elif halt_reason:
            skipped.append({"tab": ws.title, "_halted": True, "_ws": ws, "error": halt_reason})
            continue
        else:
            try:
                raw_records = _fetch_policy_tab(ws, budget, retry_5xx=not degraded)
            except Exception as exc:  # noqa: BLE001 —— 失敗的分頁不入快取
                entry = {"tab": ws.title, "error": _tab_error_text(exc), "_exc": exc, "_degraded": degraded}
                skipped.append(entry)
                if _invalidates_tab_list(exc):
                    read_failed = True               # 第 12 輪 2：只有非 HTTP 錯誤或 4xx（非 429）才作廢清單
                if budget["exhausted"]:
                    halt_reason = BUDGET_UNREAD_TEXT
                    entry["_budget_cut"] = True              # 第 10 輪 5：這一張不登記分頁冷卻
                elif is_rate_limited(exc):
                    halt_reason = QUOTA_UNREAD_TEXT          # 第 8 輪 2
                elif _is_server_error(exc) and not degraded:   # 第 13 輪 1(b)：降級模式不做 5xx 短路
                    halt_reason = UPSTREAM_5XX_UNREAD_TEXT   # 第 9 輪 1：5xx 重試用完 → 短路
                    entry["_short_5xx"] = True               # 第 10 輪 1：呼叫端據此決定是否升級整本
                continue
            tab_rows, tab_errors = _process_policy_tab(ws.title, raw_records)
            _cache_put(key, (tab_rows, tab_errors), generation)
        served += 1
        rows.extend(tab_rows)
        parse_errors.extend(tab_errors)
    if (served == 0 and halt_reason == UPSTREAM_5XX_UNREAD_TEXT and not budget["exhausted"]):
        served += _probe_after_5xx(sheet_id, skipped, rows, parse_errors)
    if read_failed:
        with _CACHE_LOCK:
            _CACHE.pop(list_key, None)      # 第 7 輪 4：有分頁讀失敗 → 分頁清單快取作廢
    return rows, skipped, parse_errors, len(tabs), served


def _probe_after_5xx(sheet_id, skipped, rows, parse_errors) -> int:
    """5xx 短路後、升級整本之前的探測（第 11 輪 1）。回傳探測讀成功的分頁數（0 或 1）。

    只在「本次發生 5xx 短路、沒有任何分頁產出資料、總睡眠預算沒用完」時呼叫。
    從本次**因短路而未讀**的分頁（它們不在冷卻中、快取已過期 —— 否則早已列為冷卻或由快取產出）
    ~~挑**最後一張**（離觸發短路那張最遠；連續幾張一起壞時，較不會剛好挑到同一段）~~
    → 第 12b 輪總管改判：挑**中間那張**（`len(未讀) // 2`）。改判理由：挑最後一張時，頭尾兩端各有連續幾張
    壞分頁，每輪（約 5 分鐘）只消耗頭尾各一張，實測「5 壞＋40 好＋5 壞」12 分鐘內 0/118 有資料、
    好分頁要約 25 分鐘才讀得到；挑中間那張則 12 分鐘內每分鐘都有資料（紅隊與本組實測）。讀**一次、不重試、不睡**
    —— 所以探測不佔總睡眠預算（第 11 輪 1「探測的等待計入總預算」在本實作等於 0 秒）。
    - 成功 → 這一張照常入快取、交出資料，從略過清單移除；回傳 1（呼叫端據此不升級）。
      其餘未讀分頁本次仍不讀，原因照舊「上游暫時失敗（5xx），未讀」。
    - 失敗（任何錯誤）→ 該項改成實際原因並標 `_probe`（呼叫端照甲案升級，~~不另登記分頁冷卻~~
      第 12 輪 1 起登記 600 秒分頁冷卻）；回傳 0。
    - 沒有可探測的分頁 → 回傳 0（照甲案升級）。
    """
    candidates = [item for item in skipped if item.get("_halted")]
    if not candidates:
        return 0
    target = candidates[len(candidates) // 2]     # 第 12b 輪：中間那張（原為最後一張）
    ws = target["_ws"]
    key = (sheet_id, "policy_tab", ws.title)
    _found, _cached_value, generation = _cache_get(key)
    try:
        raw_records = ws.get_all_records(numericise_ignore=["all"]) or []
    except Exception as exc:  # noqa: BLE001 —— 探測失敗交給呼叫端升級；原因與例外一併交出
        target.pop("_halted", None)
        target.update({"error": _tab_error_text(exc), "_exc": exc, "_probe": True})
        return 0
    tab_rows, tab_errors = _process_policy_tab(ws.title, raw_records)
    _cache_put(key, (tab_rows, tab_errors), generation)
    skipped.remove(target)
    rows.extend(tab_rows)
    parse_errors.extend(tab_errors)
    return 1


_policy_loader = _cached_policy_loader


def _native(value):
    """numpy 純量 → Python 原生型別（L2 只認 int／float／str；`numpy.int64` 不是 `int`）。其餘原樣。"""
    if type(value).__module__ == "numpy" and hasattr(value, "item"):
        return value.item()
    return value


# 試算表 ID → [(分頁名, 已過 mask 的原因, 是否觸發冷卻〔配額或整本〕, 是否實際讀取失敗)]；
# 冷卻訊息用（第 6 輪 B 組 3、第 7 輪 3、第 11 輪 3 截斷）。
# 存入時就先過 mask，不保留未遮蔽的原文；整頁讀取成功時清除；`clear_cache`（含全域清除）一併清除。
_LAST_SKIPPED: dict = {}
ALL_TABS_FAILED_MESSAGE = "所有保單分頁都讀取失敗，不回空表"
BUDGET_UNREAD_COUNT_TEXT = "有 {n} 張因重試等待上限未讀"     # 第 13 輪 2


def load_policy_holding_rows(*, mask: Mask) -> dict:
    """同一本（`POLICY_SHEET_ID`）的保單分頁持倉列。

    回傳 `{"rows": [dict, ...], "skipped_tabs": [{"tab", "error", "unread"}], "invest_twd_parse_errors": [...]}`。
    `rows` 的欄名是 `ALL_COLS_V2` 加上 `_tab`、`_row`、`_blank`、`_invest_both`（該分頁兩個本金標頭並存）。
    `skipped_tabs[*]["error"]` 過 `mask`（ID 不遮，7.2 丙）；另有 `unread`（第 13 輪 5，見下）。

    快取（第 6 輪總管裁定；依據 v3 `02` 與 `49` §4.4）：**整頁結果不快取**；逐分頁快取成功讀到的分頁
    （見 `_cached_policy_loader`）。有任何分頁被略過就視為失敗：不呼叫 `record_gspread_success`。
    整頁結果不快取；逐分頁快取的每一筆都是成功結果；此粒度解讀為總管判斷，待第二組確認。
    - 分頁失敗若屬 429（**只看狀態碼**，`is_rate_limited`）→ 登記配額冷卻（第 3 輪裁定 3）；
      非 429 → 只對那一張分頁登記冷卻（5xx 300 秒、其他 60 秒；第 7 輪 2、第 10 輪 2；存在本檔，第 8 輪 5），
      不碰整本鑰匙與配額鑰匙；重試等待預算用完的那一張不登記（第 10 輪 5）。
      例外一（第 10 輪 1、第 11 輪 1）：本次發生 5xx 短路、且沒有任何分頁產出資料 → 先探測一張未讀分頁
      （讀一次、不重試）；探測成功就不升級（觸發短路的那張照登記 300 秒分頁冷卻，其餘未讀分頁本次仍不讀）；
      探測失敗（任何錯誤）或沒有可探測的分頁 → 改登記整本 sheet 鑰匙（`server_error`，300 秒），
      ~~觸發短路與探測的那兩張都不另登記分頁冷卻。~~
      觸發短路與探測失敗的那兩張另登記 `escalated_tab_cooldown_sec()`（300＋300＝600 秒）分頁冷卻（第 12 輪 1）。
      例外二（第 8 輪 4、第 9 輪 2、第 11 輪 2）：本次沒有任何分頁產出資料、且**實際讀取失敗**的分頁
      （不含預算截斷的那張、不含未讀）至少 2 張，全部屬同一類 HTTP 狀態碼（4xx 各碼各自一類、5xx 一類）
      → 改登記整本 sheet 鑰匙，冷卻類別照 `kind_for_gspread_error`。
    降級模式（第 13 輪 1，總管裁定）：本次有 5xx 短路或整本升級 → 記下時間（`_mark_degraded`）；
      之後 `degraded_window_sec()`（900 秒）內這本試算表走降級模式 —— 5xx 不重試、不短路、不探測、
      不升級整本（兩種升級都不做），讀失敗的分頁各自登記分頁冷卻（5xx 300 秒），好分頁照常讀、入快取。
      第 13b 輪（總管採用）：降級期間只要又發生 5xx 讀取失敗，就重新記時間、**延長**降級。後果（已知代價）：
      - 只要一直有分頁持續 5xx，這本試算表就一直停在降級模式，**不再升級整本**；5xx 停止後 900 秒才解除；
      - 那段期間 5xx 只讀 1 次、不重試 —— 暫時性 5xx 可能讓好分頁被誤判成壞分頁、冷卻 300 秒；
      - 整本全部 5xx 時，保單分頁每 5 分鐘最多讀 N 次（N ＝ 分頁數；每張讀失敗後冷卻 300 秒）。
      詳見 `_cached_policy_loader` docstring。
    ⚠️ 已知限制 —— 舊句逐段刪除線保留（不巢狀；有意識的更正，不是漏刪；決策者 AI 總管）：
      ~~（第 10／11 輪）冷啟動（沒有任何分頁快取）且觸發短路的那張與探測的那張（未讀分頁中的最後一張）都壞時，
      仍會推定整本故障、冷卻 5 分鐘，補充分頁一併擋下（同一把整本鑰匙）；屬總管裁定的取捨，不是 bug。~~
      → 第 12 輪更正：前提與事實不符，紅隊第 11 輪實測推翻（舊版形成永久循環，不是「冷卻 5 分鐘」）。
      ~~（第 12b 輪）冷啟動（或好分頁的快取剛好都過期）、而且壞分頁剛好落在頭（觸發短路）與中位位置（探測）時，
      整本先冷卻 300 秒；之後這兩張再冷卻 300 秒，下一輪改讀別張、改探別張。~~
      → 第 13 輪更正：紅隊 B-M1 實測推翻 —— 開頭 ≥2 張壞＋中段一塊壞時，兩組「頭＋中」輪流升級，30 分鐘 0% 有資料。
      ~~（第 12 輪）A 組例：奇數張單雙交錯壞時，只壞一半也會先冷卻 5 分鐘。~~
      ~~（第 12 輪）前後兩端各有連續 k 張壞時，約要 k 輪才讀到中間的好分頁。~~
      （上兩例描述的是「探測挑最後一張」時的行為，第 12b 輪起已不成立。）
      ~~（第 12b 輪）頭 1 張＋中段第 20～29 張壞：前 5 分鐘無資料，其後每 10 分鐘暗一段，全程 88/226。~~
    ⚠️ 已知限制 —— 下一段是第 13 輪實測（第 13b 輪起延長降級，其中「每 15 分鐘暗 5 分鐘」已不成立，見段末）：
      - 冷啟動遇到「頭部壞＋探測位置（中位）也壞」時，仍先升級整本 300 秒（非降級模式的規則，總管裁定保留）。
      - 降級模式的觸發只看「5xx 短路或整本升級」，而降級模式下本身不短路、不升級，所以 900 秒後自動解除。
        解除那一刻若**好分頁的快取同時到期**（它們是同一次讀進來的，每 60 秒一起過期；A 組建議 1）、
        頭部壞分頁的冷卻也剛好到期，就會再一次短路＋探測中位壞分頁 → 再升級，形成「每 15 分鐘暗 5 分鐘」。
        實測受影響的排列：B-M1 四種（頭 2／3／5／10 張壞＋中段一塊壞）、頭 1＋中段壞、51 張單雙交錯 ——
        ~~330 秒起有資料 388/489（79.3%），未達總管門檻 90%，以 `xfail(strict)` 標記。~~（第 13b 輪已不成立）
        頭尾各 5 張壞不受影響（489/489）。每分鐘讀取在所有排列下 ≤ 58。
      - 與 2c 工單（冷卻／快取抖動）相關：快取同時到期是成因之一，加抖動可以打散。
      → 第 13b 輪：降級期間 5xx 讀取失敗會延長降級，上述「900 秒後自動解除 → 再升級」在壞分頁持續時不再發生；
      第 13b 輪實測（同條件，50／51 張、每 3 秒重跑 30 分鐘；`test_第13輪1_三十分鐘每3秒_*`）：上列 7 種排列
      330 秒起有資料全部 490/490；每分鐘讀取最高 58；全部 5xx 時保單分頁讀取每 5 分鐘 ≤ N＋4。
      現行已知限制：冷啟動遇到「頭部壞＋中位也壞」時仍先升級整本 300 秒（第一輪），之後即進入降級模式。
    - 任一分頁重試用完仍 429／5xx → 其餘要打上游的分頁不讀（第 8 輪 2、第 9 輪 1）。
    - 冷卻中 → `code="cooling"`，訊息列出最後一次被略過的分頁（存入時已過 `mask`）：造成配額或整本冷卻的
      那張標「觸發冷卻」，再加最多 3 張實際讀取失敗的分頁，其餘寫「另有 N 張未讀或未列出」
      （第 6 輪 B 組 3、第 7 輪 3、第 11 輪 3）。
    - 全部分頁都在失敗或冷卻 → `code="api"`。~~但只要還有分頁因總睡眠預算用完而沒讀完，就改回傳部分結果
      （第 12 輪 3）。~~ 第 13 輪 2 撤回：**第 12 輪第 3 項為總管派工錯誤**（那個例外只可能回 0 列，等於回空表）；
      現行照舊拋 `api`，訊息附略過清單與「有 N 張因重試等待上限未讀」（`details["unread_by_budget"]`）。
    - `skipped_tabs[*]["unread"]`（第 13 輪 5）：False ＝ 本次實際讀取失敗；True ＝ 本次未讀（冷卻中、短路或預算）。
    - **所有分頁都失敗** → `code="api"`，訊息帶各分頁原因，不回空表（第 6 輪 B 組 2）。
    """
    def op(client, _spreadsheet, sid):
        from infra.gspread_retry import http_status_of, record_gspread_failure
        rows, skipped, parse_errors, tab_count, served = _policy_loader(client, sid)
        failures = [t for t in skipped if t.get("_exc") is not None]
        # 第 11 輪 2：同類升級只計入**實際讀取失敗**的分頁；預算截斷的那一張不算（它不是自己壞，是額度用完）
        judged = [t for t in failures if not t.get("_budget_cut")]
        non_quota = [t for t in judged if not is_rate_limited(t["_exc"])]
        # 第 10 輪 1（甲案）＋第 11 輪 1（先探測）：本次發生 5xx 短路、且探測之後仍沒有任何分頁產出資料
        # （served == 0；探測失敗或沒有可探測的分頁）→ 升級整本 sheet 鑰匙（`server_error`，300 秒）；
        # 不設「≥2 張」門檻。升級時觸發短路的那張與探測的那張都不另登記分頁冷卻；
        # served > 0（含探測成功）不升級，觸發短路的那張照登記 300 秒分頁冷卻。
        short_5xx = [t for t in failures if t.get("_short_5xx")]
        # 第 13 輪 1(c)：降級模式下不再升級整本（兩種升級都不做），讀失敗的分頁各自登記分頁冷卻
        degraded = any(t.get("_degraded") for t in failures)
        escalate_5xx = bool(short_5xx) and served == 0 and not degraded
        # 第 8 輪 4、第 9 輪 2：改登記整本 sheet 鑰匙（不逐張登記）的條件 ——
        # 本次**沒有任何分頁產出資料**（快取命中或新讀都沒有），且實際讀取失敗的分頁至少 2 張、
        # 全部是同一類 HTTP 錯誤、每張都有狀態碼。只要有一張分頁（含快取）產出資料，就證明這一本讀得到。
        # ⚠️ 已知限制：失敗若在時間上錯開（例如這次只有一張實際讀取、其他在快取或冷卻中），不會升級。
        # 第 11 輪 2：「同一類」改看 HTTP 狀態碼（`_status_class`：4xx 各碼各自一類、5xx 全部一類），
        # 不再用冷卻分類（`kind_for_gspread_error` 把 400 與 5xx 都歸成 server_error）。
        classes = {_status_class(http_status_of(t["_exc"])) for t in non_quota}
        sheet_wide = (not degraded and served == 0 and len(non_quota) >= 2 and len(non_quota) == len(judged)
                      and all(http_status_of(t["_exc"]) is not None for t in non_quota)
                      and len(classes) == 1)
        if sheet_wide:
            cause = non_quota[0]
        elif escalate_5xx:
            cause = short_5xx[0]
        else:
            cause = None
        public, last = [], []
        for item in skipped:
            exc = item.get("_exc")
            error = mask(str(item.get("error", "")))
            quota = exc is not None and is_rate_limited(exc)
            trigger = quota or item is cause          # 第 11 輪 3：造成配額或整本冷卻的那張標「觸發冷卻」
            if quota:
                record_gspread_failure(ACTOR, sid, exc)          # 真 429 → 配額冷卻（第 3 輪裁定 3）
            elif cause is not None and (item.get("_short_5xx") or item.get("_probe")):
                # 第 12 輪 1：5xx 升級整本時，這兩張冷卻「整本＋分頁 5xx」＝ 600 秒，打破循環
                _record_tab_cooldown(sid, item.get("tab"), error, seconds=escalated_tab_cooldown_sec())
            elif exc is not None and not sheet_wide and not item.get("_budget_cut"):
                # （第 12 輪：升級時那兩張已由上一個分支處理，原本排除它們的條件成為死碼，移除）
                # 非 429 → 只冷卻這一張（第 7 輪 2）；5xx 300 秒、其他 60 秒（第 10 輪 2）
                _record_tab_cooldown(sid, item.get("tab"), error,
                                     TAB_COOLDOWN_KIND_5XX if _is_server_error(exc) else TAB_COOLDOWN_KIND)
            # 第 13 輪 5：`unread` 區分「本次實際讀取失敗」（False）與「本次未讀：冷卻中、短路或預算」（True）
            public.append({"tab": item.get("tab"), "error": error, "unread": exc is None})
            last.append((item.get("tab"), error, trigger, exc is not None))
        if cause is not None:
            record_gspread_failure(ACTOR, sid, cause["_exc"])   # 整本 sheet 鑰匙（第 8 輪 4／第 10 輪 1）
        if short_5xx or cause is not None:
            _mark_degraded(sid)                                  # 第 13 輪 1：進入（或延長）降級模式
        elif degraded and any(_is_server_error(t["_exc"]) for t in failures):
            _mark_degraded(sid)            # 第 13b 輪：降級期間又有 5xx 讀取失敗 → 延長降級（總管採用）
        if last:
            _LAST_SKIPPED[sid] = last
        else:
            _LAST_SKIPPED.pop(sid, None)                         # 整頁讀取成功 → 清除
        # ~~第 12 輪 3（B 建議 3）：還有分頁因總睡眠預算用完而沒讀完 → 不算「全部失敗」，回傳部分結果並列出略過清單。~~
        # 第 13 輪 2 撤回（A-M1）：**第 12 輪第 3 項為總管派工錯誤** —— 能走進這個判斷的情形一定是 0 列，
        # 所謂「回部分結果」實際上是回空表，違反 §1 與本檔「不回空表」（第 6 輪 B 組 2）。
        # 現行：所有分頁都被略過 → 照舊拋 `api`；訊息附略過清單，另寫「有 N 張因重試等待上限未讀」。
        if skipped and len(skipped) == tab_count:
            detail = "；".join(f"{t['tab']}：{t['error']}" for t in public)
            unread_by_budget = sum(1 for t in skipped
                                   if t.get("_halted") and t.get("error") == BUDGET_UNREAD_TEXT)
            if unread_by_budget:
                detail += f"；{BUDGET_UNREAD_COUNT_TEXT.format(n=unread_by_budget)}"
            raise PolicySupplementError(mask(f"{ALL_TABS_FAILED_MESSAGE}：{detail}"), code="api",
                                        details={"skipped_tabs": public,
                                                 "unread_by_budget": unread_by_budget})
        return {"rows": rows, "skipped_tabs": public, "invest_twd_parse_errors": parse_errors}

    # 有分頁被略過時不算整次成功 —— 不呼叫 `record_gspread_success`，否則剛登記的配額冷卻會被當場解除。
    _sid, result = _run(op, mask=mask, open_sheet=False,
                        success_if=lambda r: not r["skipped_tabs"])
    return result
