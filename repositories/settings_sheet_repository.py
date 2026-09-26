# -*- coding: utf-8 -*-
"""設定與取數紀錄試算表的讀寫（L1；docs/v2/50_settings_sheet_design.md，`49` §6.3 N-2）。

本檔只做一件事：對客戶自建、分享給服務帳戶的那一本試算表（`SETTINGS_SHEET_ID`）
讀寫四張分頁 —— `user_setting_log`、`market_indicator`、`fetch_log`、`fetch_log_open`，
並在讀取端把儲存形態收斂回 `44` §4.5 的表形狀。**不做業務判定**（寫表的時機、
取數成功與否由 L2 `services/v2_tables/settings_store.py` 決定）。

規則出處（逐條對應 `50`）：
- 第 2 節：試算表 ID 只讀 secret `SETTINGS_SHEET_ID`（`st.secrets` → 環境變數，
  經 `infra.config.get_secret`）；**沒有預設值**，缺值 → `SettingsSheetError(code="not_configured")`。
  不退回本地檔、不自己建新試算表。憑證只用服務帳戶（`50` B7，本檔拍板：一律服務帳戶）。
- 第 4 節：寫入一律 `value_input_option="RAW"`；讀取一律取字串（`FORMATTED_VALUE`）後嚴格解析，
  解析不了的列不收、計數回報，不猜、不補。
- 第 5 節：`user_setting_log` 每個鍵取**最後一列**（依列號）；`market_indicator` 讀取端依主鍵去重、
  主鍵矛盾整組不採用、`is_revised` 以列集合重算；`fetch_log` 同一 `log_id` 取第一列並計數，
  與 `fetch_log_open` 合併出「中斷」列。
- 第 6 節：只做兩種寫入 —— `append_rows` 與「分頁剛由本檔建立時寫一次標頭」。
  `user_setting_log` 的追加**不重試**；`market_indicator`、`fetch_log`、`fetch_log_open` 的追加
  以 `infra.gspread_retry.with_gspread_retry` 重試。
- 第 7.1 節：每次讀寫都先比對第 1 列標頭，不符 → `SettingsSheetError(code="header_mismatch")`，
  該分頁不讀不寫，**不自動改寫標頭**。
- 第 8 節：冷卻沿用 `infra.gspread_retry` 的 `should_skip_gspread`／`record_gspread_failure`／
  `record_gspread_success`（actor 固定 `"sa"`）。
- 第 9.2 節：讀取端 60 秒手動快取（模組層 dict），**只快取成功的讀取**；
  任何一次寫入（存檔或取數紀錄）**不論成敗**都清掉該本的快取（派工單裁定，比 `50` 9.2 的
  「取數成功後清」更嚴）。

失敗訊息遮蔽（`ACCEPTANCE.md` 七）：本檔是 L1，**不得 import L2 的
`services/v2_tables/masking.py`**（`CLAUDE.md` §8.2 上行 import）。所以每一個公開函式都要求呼叫端
以關鍵字傳入 `mask`（字串 → 遮蔽後字串），本檔自己產生的每一句錯誤訊息都先過 `mask`；
例外一律 `raise ... from None`，不把未遮蔽的原始例外掛在 `__cause__` 上帶出去。
`mask` 沒有預設值：忘了傳就是 TypeError，不會靜靜地不遮。
⚠️ 寫進 `fetch_log.message` 的字串由 L2 遮好再交進來（`50` 7.2：讀寫模組不再遮第二次）。
"""

from __future__ import annotations

import math
import os
import re
import threading
import time
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Callable, Optional

from infra.config import get_secret

# ── 分頁名（`50` 第 3 節）─────────────────────────────────────────────
TAB_USER_SETTING = "user_setting_log"
TAB_MARKET_INDICATOR = "market_indicator"
TAB_FETCH_LOG = "fetch_log"
TAB_FETCH_LOG_OPEN = "fetch_log_open"

# ── 欄位規格（名, `44` 型別, 可空）。前三張是 `44` §4.5 的鏡像 ──────────
# ⚠️ 真相源是 `44`；`services/v2_tables/contract.py` 是另一份鏡像。L1 不得 import L2，
#    所以這裡另寫一份，由 tests/test_v2_tables_contract_settings.py 與 contract 逐欄比對。
USER_SETTING_SPEC = (
    ("setting_key", "字串", False),
    ("setting_value", "字串", True),
    ("value_kind", "字串", False),
    ("updated_at", "時間", True),
)
MARKET_INDICATOR_SPEC = (
    ("indicator_key", "字串", False),
    ("obs_date", "日期", False),
    ("release_date", "日期", False),
    ("value_num", "浮點", False),
    ("value_unit", "字串", False),
    ("source_tier", "字串", False),
    ("is_revised", "布林", False),
    ("fetched_at", "時間", False),
)
FETCH_LOG_SPEC = (
    ("log_id", "字串", False),
    ("source_tier", "字串", False),
    ("started_at", "時間", False),
    ("finished_at", "時間", True),
    ("outcome", "字串", False),
    ("row_count", "整數", True),
    ("message", "字串", True),
)
# `50` 4.4：輔助分頁，三欄借自 `fetch_log` 前三欄。
FETCH_LOG_OPEN_SPEC = FETCH_LOG_SPEC[:3]

TAB_SPECS = {
    TAB_USER_SETTING: USER_SETTING_SPEC,
    TAB_MARKET_INDICATOR: MARKET_INDICATOR_SPEC,
    TAB_FETCH_LOG: FETCH_LOG_SPEC,
    TAB_FETCH_LOG_OPEN: FETCH_LOG_OPEN_SPEC,
}

VALUE_KIND_VALUES = ("int", "float", "date", "ratio", "list", "rules")
SOURCE_TIER_VALUES = ("淨值", "配息", "市場指標", "其他")
OUTCOME_VALUES = ("ok", "failed")
_DOMAINS = {
    "value_kind": VALUE_KIND_VALUES,
    "source_tier": SOURCE_TIER_VALUES,
    "outcome": OUTCOME_VALUES,
}

SECRET_KEY = "SETTINGS_SHEET_ID"
ACTOR = "sa"                 # `50` B7：一律服務帳戶
CACHE_TTL_SEC = 60.0         # `50` 9.2
# `50` B3（本檔拍板）：`fetch_log_open` 有、`fetch_log` 沒有的 `log_id`，開始時間超過這個秒數
# 才判定為中斷。理由見 `OPEN_LOG_STALE_SEC` 下方註解。
OPEN_LOG_STALE_SEC = 3600
# 單次 `infra/proxy.py::fetch_url` 最壞約 3 分鐘（timeout 20s × 代理＋直連 × 1+3 次 429 重試，
# 另加 2/4/8s 退避）；`50` B3 建議「兩倍以上」。取 1 小時：七個鍵日後全部串行接上、每鍵都走到
# 最壞情形（約 20 分鐘）時仍有兩倍以上餘裕。代價是真正中斷的取數最多 1 小時後才在讀取端顯示為中斷，
# 這之前計入 `in_progress`（不偽裝成已結束）。本數字是推算，不是實測。
INTERRUPTED_MESSAGE = "取數沒有結束紀錄"   # `50` 5.3 的固定系統文字

_TIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_FLOAT_RE = re.compile(r"^-?\d+(\.\d+)?$")
_INT_RE = re.compile(r"^\d+$")

Mask = Callable[[str], str]


class SettingsSheetError(Exception):
    """設定試算表讀寫失敗。訊息已經過呼叫端傳入的 `mask`。

    `code`：`not_configured`（沒設 ID）／`no_service_account`／`header_mismatch`／
            `cooling`（冷卻中，未打上游）／`api`（上游讀寫失敗）。
    `http_status`：能從例外挖到的 HTTP 狀態碼（挖不到為 None）。
    `remaining_sec`：`cooling` 時的剩餘秒數。
    `hint`：`50` 第 8 節表中對 404／403 的提示（不含秘密值；`client_email` 依 ACCEPTANCE 7.2 丙不遮）。
    """

    def __init__(self, message: str, *, code: str, http_status: Optional[int] = None,
                 remaining_sec: Optional[float] = None, hint: Optional[str] = None,
                 details: Optional[dict] = None):
        super().__init__(message)
        self.code = code
        self.http_status = http_status
        self.remaining_sec = remaining_sec
        self.hint = hint
        self.details = details or {}


# ════════════════════════ 時間、儲存格格式 ════════════════════════

_clock = time.monotonic


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _stamp(moment: datetime) -> str:
    """`50` 第 4 節：ISO 8601、世界協調時間、秒為單位、結尾 `Z`。"""
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _format_cell(column: str, kind: str, nullable: bool, value: Any) -> str:
    """值 → 儲存格字串（`50` 第 4 節）。不合格就 ValueError（呼叫端的 bug，當場炸）。"""
    if value is None:
        if not nullable:
            raise ValueError(f"{column}：不可空的欄取不到值")
        return ""
    if kind == "字串":
        if not isinstance(value, str) or value == "":
            raise ValueError(f"{column}：須為非空字串（{value!r}）")
        return value
    if kind == "日期":
        if not isinstance(value, str) or not _is_iso_date(value):
            raise ValueError(f"{column}：日期須為 YYYY-MM-DD（{value!r}）")
        return value
    if kind == "時間":
        if not isinstance(value, str):
            raise ValueError(f"{column}：時間須為 ISO 字串（{value!r}）")
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError(f"{column}：時間格式不符（{value!r}）") from None
        if parsed.tzinfo is None:
            raise ValueError(f"{column}：時間沒有時區（{value!r}）")
        return _stamp(parsed)   # 同一瞬間、截到秒
    if kind == "浮點":
        if isinstance(value, bool) or not isinstance(value, (int, float)) \
                or not math.isfinite(float(value)):
            raise ValueError(f"{column}：須為有限數值（{value!r}）")
        text = format(Decimal(repr(float(value))), "f")  # 十進位字面，不用科學記號
        if "." in text:
            text = text.rstrip("0").rstrip(".") or "0"
        return "0" if text in ("-0",) else text
    if kind == "整數":
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{column}：須為非負整數（{value!r}）")
        return str(value)
    if kind == "布林":
        if not isinstance(value, bool):
            raise ValueError(f"{column}：須為布林（{value!r}）")
        return "TRUE" if value else "FALSE"
    raise ValueError(f"未知型別 {kind!r}（{column}）")


def _is_iso_date(text: str) -> bool:
    try:
        return date.fromisoformat(text).isoformat() == text
    except ValueError:
        return False


def _parse_cell(column: str, kind: str, nullable: bool, text: str):
    """儲存格字串 → (值, 問題)。問題非 None 表示這一列不收。"""
    if text == "":
        return (None, None) if nullable else (None, f"{column}：不可空")
    if kind == "字串":
        domain = _DOMAINS.get(column)
        if domain is not None and text not in domain:
            return None, f"{column}：不在值域（{text!r}）"
        return text, None
    if kind == "日期":
        return (text, None) if _is_iso_date(text) else (None, f"{column}：日期格式不符（{text!r}）")
    if kind == "時間":
        if not _TIME_RE.match(text):
            return None, f"{column}：時間格式不符（{text!r}）"
        try:
            datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None, f"{column}：時間格式不符（{text!r}）"
        return text, None
    if kind == "浮點":
        if not _FLOAT_RE.match(text):
            return None, f"{column}：數值格式不符（{text!r}）"
        return float(text), None
    if kind == "整數":
        if not _INT_RE.match(text):
            return None, f"{column}：整數格式不符（{text!r}）"
        return int(text), None
    if kind == "布林":
        if text == "TRUE":
            return True, None
        if text == "FALSE":
            return False, None
        return None, f"{column}：布林須為 TRUE 或 FALSE（{text!r}）"
    raise ValueError(f"未知型別 {kind!r}（{column}）")


def _parse_rows(spec, values: list):
    """分頁的資料列（不含標頭）→ (records, bad_rows, blank_rows)。

    record＝`{"_row": 試算表列號, "_raw": 補齊到欄數的字串列, 欄名: 值, ...}`。
    整列空白的列不是紀錄，只計數、不算格式不符。
    """
    width = len(spec)
    records, bad, blank = [], [], 0
    for offset, raw in enumerate(values):
        row_no = offset + 2   # 第 1 列是標頭
        cells = [str(c) for c in raw]
        if all(c == "" for c in cells):
            blank += 1
            continue
        if len(cells) > width and any(c != "" for c in cells[width:]):
            bad.append({"row": row_no, "reason": f"超出 {width} 欄的儲存格有值", "cells": cells})
            continue
        cells = (cells + [""] * width)[:width]
        record = {"_row": row_no, "_raw": tuple(cells)}
        problem = None
        for (name, kind, nullable), text in zip(spec, cells):
            value, problem = _parse_cell(name, kind, nullable, text)
            if problem:
                break
            record[name] = value
        if problem:
            bad.append({"row": row_no, "reason": problem, "cells": cells})
            continue
        records.append(record)
    return records, bad, blank


def _public(record: dict, spec) -> dict:
    return {name: record[name] for name, _k, _n in spec}


# ════════════════════════ 設定、連線、冷卻 ════════════════════════

def settings_sheet_id(*, mask: Mask) -> str:
    """`SETTINGS_SHEET_ID`：`st.secrets` → 環境變數；沒有預設值，缺值 fail loud。"""
    raw = get_secret(SECRET_KEY)
    text = raw.strip() if isinstance(raw, str) else ""
    if not text:
        raise SettingsSheetError(mask(f"未設定設定試算表的 ID（{SECRET_KEY}）"),
                                 code="not_configured")
    return text


def _service_account() -> Optional[Any]:
    raw = get_secret("google_service_account")
    if raw is None or raw == "" or (hasattr(raw, "__len__") and len(raw) == 0):
        return None
    return raw


def _client_email(creds) -> str:
    try:
        if isinstance(creds, str):
            import json
            creds = json.loads(creds)
        email = creds.get("client_email")
        return email if isinstance(email, str) else ""
    except Exception:  # noqa: BLE001 —— 只是拿來組提示，拿不到就不寫信箱
        return ""


def _make_client(creds):
    """服務帳戶 → gspread client（測試以 monkeypatch 換成假物件）。"""
    from repositories.policy._helpers import get_gspread_client
    return get_gspread_client(creds)


def _hint_for(exc: BaseException, status: Optional[int], email: str) -> Optional[str]:
    who = f" `{email}`" if email else ""
    if status == 404 or type(exc).__name__ == "SpreadsheetNotFound":
        return f"請確認試算表 ID，以及已分享給服務帳戶{who}"
    if status == 403 or type(exc).__name__ == "PermissionError":
        return "服務帳戶可能只有檢視權限，需要編輯者"
    return None


def _run(op: Callable, *, mask: Mask, write: bool):
    """開表 → 執行 op(spreadsheet)，外面包冷卻與失敗登記。回傳 (sheet_id, op 的結果)。

    - 冷卻中 → 不打上游，`code="cooling"`。
    - `SettingsSheetError`（例如標頭不符）不是上游失敗，不登記冷卻，原樣往上拋。
    - 其餘例外 → 登記冷卻，轉成 `code="api"`，訊息過 `mask`，`from None`（不帶出原始例外）。
    - 寫入（`write=True`）不論成敗都清掉該本的快取。
    """
    from infra.gspread_retry import (
        http_status_of, record_gspread_failure, record_gspread_success,
        should_skip_gspread, with_gspread_retry,
    )

    sheet_id = settings_sheet_id(mask=mask)
    creds = _service_account()
    if creds is None:
        raise SettingsSheetError(mask("未設定服務帳戶（google_service_account）"),
                                 code="no_service_account")
    try:
        skip, left, kind = should_skip_gspread(ACTOR, sheet_id)
        if skip:
            raise SettingsSheetError(
                mask(f"設定試算表暫停重試，還剩 {math.ceil(left)} 秒（上次失敗類別：{kind}）"),
                code="cooling", remaining_sec=left)
        try:
            client = _make_client(creds)
            spreadsheet = with_gspread_retry(client.open_by_key, sheet_id)
            result = op(spreadsheet)
        except SettingsSheetError:
            raise
        except Exception as exc:  # noqa: BLE001 —— 轉成帶原文的 SettingsSheetError，不吞
            status = http_status_of(exc)
            record_gspread_failure(ACTOR, sheet_id, exc)
            text = f"{type(exc).__name__}: {exc}"
            raise SettingsSheetError(
                mask(text), code="api", http_status=status,
                hint=_hint_for(exc, status, _client_email(creds))) from None
        record_gspread_success(ACTOR, sheet_id)
        return sheet_id, result
    finally:
        if write:
            clear_cache(sheet_id)


# ════════════════════════ 分頁讀取、標頭 ════════════════════════

def _a1_tab(name: str) -> str:
    return "'" + name.replace("'", "''") + "'"


def _read_tabs(spreadsheet, names) -> dict:
    """一次列出分頁、一次批次讀值。回傳 `{名: (worksheet 或 None, 全部列)}`；分頁不存在時為 (None, None)。"""
    from infra.gspread_retry import with_gspread_retry

    sheets = {ws.title: ws for ws in with_gspread_retry(spreadsheet.worksheets)}
    present = [n for n in names if n in sheets]
    out = {n: (None, None) for n in names}
    if present:
        resp = with_gspread_retry(
            spreadsheet.values_batch_get, [_a1_tab(n) for n in present],
            params={"valueRenderOption": "FORMATTED_VALUE"})
        ranges = (resp or {}).get("valueRanges", [])
        if len(ranges) != len(present):
            raise RuntimeError(f"批次讀取回傳 {len(ranges)} 段，預期 {len(present)} 段")
        for name, block in zip(present, ranges):
            out[name] = (sheets[name], [list(r) for r in block.get("values", [])])
    return out


def _check_header(name: str, values, *, mask: Mask) -> None:
    """`50` 7.1：第 1 列逐字等於規格欄名（尾端空白儲存格不算）；不符就停，不改寫。"""
    expected = [n for n, _k, _nl in TAB_SPECS[name]]
    header = [str(c) for c in (values[0] if values else [])]
    while header and header[-1] == "":
        header.pop()
    if header != expected:
        raise SettingsSheetError(
            mask(f"標頭與規格不符：分頁 {name}；規格 {expected}；試算表 {header}"),
            code="header_mismatch", details={"tab": name, "expected": expected, "actual": header})


def _worksheet_for_append(spreadsheet, name: str, tabs: dict, *, mask: Mask):
    """寫入前取分頁：已存在 → 比對標頭；不存在 → 建立並寫一次標頭（`50` 7.1）。"""
    from infra.gspread_retry import with_gspread_retry

    ws, values = tabs[name]
    if ws is not None:
        _check_header(name, values, mask=mask)
        return ws
    header = [n for n, _k, _nl in TAB_SPECS[name]]
    try:
        ws = spreadsheet.add_worksheet(title=name, rows=100, cols=len(header))
    except Exception:  # noqa: BLE001 —— 可能是別的行程剛建好；重讀後再判，判不出就拋原例外
        again = _read_tabs(spreadsheet, [name])
        if again[name][0] is None:
            raise
        _check_header(name, again[name][1], mask=mask)
        return again[name][0]
    with_gspread_retry(ws.append_rows, [header], value_input_option="RAW",
                       insert_data_option="INSERT_ROWS")
    return ws


def _append(ws, rows: list, *, retry: bool) -> None:
    from infra.gspread_retry import with_gspread_retry

    if not rows:
        return
    if retry:
        with_gspread_retry(ws.append_rows, rows, value_input_option="RAW",
                           insert_data_option="INSERT_ROWS")
    else:
        ws.append_rows(rows, value_input_option="RAW", insert_data_option="INSERT_ROWS")


def _serialize(spec, row: dict) -> list:
    names = [n for n, _k, _nl in spec]
    extra = [k for k in row if k not in names]
    if extra:
        raise ValueError(f"多出規格沒有的欄：{extra}")
    return [_format_cell(n, k, nl, row.get(n)) for n, k, nl in spec]


# ════════════════════════ 快取（`50` 9.2）════════════════════════

_CACHE: dict = {}
_CACHE_LOCK = threading.Lock()


def clear_cache(sheet_id: Optional[str] = None) -> None:
    """清掉某一本（或全部）的讀取快取。"""
    with _CACHE_LOCK:
        if sheet_id is None:
            _CACHE.clear()
        else:
            for key in [k for k in _CACHE if k[0] == sheet_id]:
                del _CACHE[key]


def _cached_read(what: str, names, reducer: Callable, *, mask: Mask) -> dict:
    """讀 names 幾張分頁 → 比對標頭 → reducer(tabs)。只快取成功結果，60 秒。"""
    sheet_id = settings_sheet_id(mask=mask)
    now = _clock()
    with _CACHE_LOCK:
        hit = _CACHE.get((sheet_id, what))
        if hit is not None and now - hit[0] < CACHE_TTL_SEC:
            return hit[1]

    def op(spreadsheet):
        tabs = _read_tabs(spreadsheet, names)
        for name in names:
            if tabs[name][0] is not None:
                _check_header(name, tabs[name][1], mask=mask)
        return tabs

    _sid, tabs = _run(op, mask=mask, write=False)
    result = reducer(tabs)
    with _CACHE_LOCK:
        _CACHE[(sheet_id, what)] = (_clock(), result)
    return result


def _data_rows(tabs, name):
    ws, values = tabs[name]
    return None if ws is None else values[1:]


# ════════════════════════ user_setting ════════════════════════

def _reduce_user_settings(tabs) -> dict:
    data = _data_rows(tabs, TAB_USER_SETTING)
    if data is None:
        return {"rows": {}, "bad_rows": [], "broken_keys": [], "blank_rows": 0,
                "tab_missing": True}
    records, bad, blank = _parse_rows(USER_SETTING_SPEC, data)
    last = {}
    for rec in records:                      # 依列號，後者覆蓋前者（`50` 5.1）
        last[rec["setting_key"]] = rec
    # 某個鍵在它最後一筆有效列之後，還有一列看得出鍵名、但其他欄解析不了 ——
    # 那一列才是最新的，而它壞了：不退回較舊的值，改列入 broken_keys（`50` 第 8 節）。
    broken = set()
    for item in bad:
        key = item["cells"][0] if item["cells"] else ""
        if key and (key not in last or item["row"] > last[key]["_row"]):
            broken.add(key)
    rows = {k: _public(v, USER_SETTING_SPEC) for k, v in last.items() if k not in broken}
    return {"rows": rows, "bad_rows": bad, "broken_keys": sorted(broken), "blank_rows": blank,
            "tab_missing": False}


def load_user_settings(*, mask: Mask) -> dict:
    """`user_setting` 表（每個鍵一列，`44` 形狀）。

    回傳 `{"rows": {鍵: 四欄 dict}, "bad_rows": [...], "broken_keys": [...],
    "blank_rows": N, "tab_missing": bool}`。分頁不存在＝尚無資料（`tab_missing`，不是錯誤）。
    `broken_keys`：最新一列解析不了的鍵 —— 畫面應顯示錯誤狀態，不是 `⬜ 未設定`。
    """
    return _cached_read("user_setting", (TAB_USER_SETTING,), _reduce_user_settings, mask=mask)


def save_user_setting(setting_key: str, setting_value: Optional[str], value_kind: str, *,
                      mask: Mask) -> dict:
    """追加一列到 `user_setting_log`（`setting_value=None` 即清除該鍵）。**不重試**（`50` 第 6 節）。

    值不合格（鍵名空、`value_kind` 不在值域、值為空字串或非字串）→ ValueError，不寫。
    成功回傳寫入的那一列（`44` 形狀）。存檔後不論成敗都清快取。
    """
    if not isinstance(setting_key, str) or setting_key.strip() == "" or setting_key != setting_key.strip():
        raise ValueError(f"setting_key 須為前後無空白的非空字串（{setting_key!r}）")
    if value_kind not in VALUE_KIND_VALUES:
        raise ValueError(f"value_kind 不在值域 {VALUE_KIND_VALUES}（{value_kind!r}）")
    if setting_value is not None and (not isinstance(setting_value, str) or setting_value == ""):
        raise ValueError("setting_value 須為非空字串；要清除請傳 None（`44`：清除後是空值，不是空字串）")
    row = {"setting_key": setting_key, "setting_value": setting_value,
           "value_kind": value_kind, "updated_at": _stamp(_utcnow())}
    cells = _serialize(USER_SETTING_SPEC, row)

    def op(spreadsheet):
        tabs = _read_tabs(spreadsheet, [TAB_USER_SETTING])
        ws = _worksheet_for_append(spreadsheet, TAB_USER_SETTING, tabs, mask=mask)
        _append(ws, [cells], retry=False)

    _run(op, mask=mask, write=True)
    return row


# ════════════════════════ fetch_log ════════════════════════

def open_fetch_log(source_tier: str, *, mask: Mask) -> dict:
    """一次取數開始：產生 `log_id`、追加一列到 `fetch_log_open`（可重試）。回傳三欄 dict。

    `log_id`＝`<started_at>-<8 個十六進位隨機字元>`（`50` 5.3）。
    """
    if source_tier not in SOURCE_TIER_VALUES:
        raise ValueError(f"source_tier 不在值域 {SOURCE_TIER_VALUES}（{source_tier!r}）")
    started = _stamp(_utcnow())
    opened = {"log_id": f"{started}-{os.urandom(4).hex()}", "source_tier": source_tier,
              "started_at": started}
    cells = _serialize(FETCH_LOG_OPEN_SPEC, opened)

    def op(spreadsheet):
        tabs = _read_tabs(spreadsheet, [TAB_FETCH_LOG_OPEN])
        ws = _worksheet_for_append(spreadsheet, TAB_FETCH_LOG_OPEN, tabs, mask=mask)
        _append(ws, [cells], retry=True)

    _run(op, mask=mask, write=True)
    return opened


def fetch_log_row(opened: dict, *, outcome: str, row_count: Optional[int],
                  message: Optional[str]) -> dict:
    """由開始紀錄與結果組出 `fetch_log` 一列（`finished_at`＝當下）。不合規就 ValueError。"""
    if outcome not in OUTCOME_VALUES:
        raise ValueError(f"outcome 不在值域 {OUTCOME_VALUES}（{outcome!r}）")
    if outcome == "ok" and (message is not None or not isinstance(row_count, int)):
        raise ValueError("outcome 為 ok 時 row_count 須為整數、message 須為空")
    if outcome == "failed" and (row_count is not None or not message):
        raise ValueError("outcome 為 failed 時 row_count 須為空、message 須非空")
    return {"log_id": opened["log_id"], "source_tier": opened["source_tier"],
            "started_at": opened["started_at"], "finished_at": _stamp(_utcnow()),
            "outcome": outcome, "row_count": row_count, "message": message}


def close_fetch_log(opened: dict, *, outcome: str, row_count: Optional[int],
                    message: Optional[str], mask: Mask) -> dict:
    """一次取數結束：追加一列到 `fetch_log`（可重試）。`message` 須已由呼叫端遮好。"""
    row = fetch_log_row(opened, outcome=outcome, row_count=row_count, message=message)
    cells = _serialize(FETCH_LOG_SPEC, row)

    def op(spreadsheet):
        tabs = _read_tabs(spreadsheet, [TAB_FETCH_LOG])
        ws = _worksheet_for_append(spreadsheet, TAB_FETCH_LOG, tabs, mask=mask)
        _append(ws, [cells], retry=True)

    _run(op, mask=mask, write=True)
    return row


def _parse_stamp(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def _reduce_fetch_log(tabs, now: datetime) -> dict:
    closed = _data_rows(tabs, TAB_FETCH_LOG)
    opened = _data_rows(tabs, TAB_FETCH_LOG_OPEN)
    recs, bad, blank = _parse_rows(FETCH_LOG_SPEC, closed or [])
    open_recs, open_bad, open_blank = _parse_rows(FETCH_LOG_OPEN_SPEC, opened or [])
    rows, seen, duplicates = [], set(), 0
    for rec in recs:
        if rec["log_id"] in seen:          # 重試造成的重複：取第一列並計數（`50` 5.3）
            duplicates += 1
            continue
        seen.add(rec["log_id"])
        rows.append(_public(rec, FETCH_LOG_SPEC))
    in_progress, open_seen = 0, set()
    for rec in open_recs:
        if rec["log_id"] in seen or rec["log_id"] in open_seen:
            continue
        open_seen.add(rec["log_id"])
        if (now - _parse_stamp(rec["started_at"])).total_seconds() >= OPEN_LOG_STALE_SEC:
            rows.append({"log_id": rec["log_id"], "source_tier": rec["source_tier"],
                         "started_at": rec["started_at"], "finished_at": None,
                         "outcome": "failed", "row_count": None,
                         "message": INTERRUPTED_MESSAGE})
        else:
            in_progress += 1
    rows.sort(key=lambda r: r["started_at"])   # 字面格式固定（秒＋Z），字串排序＝時間排序
    return {"rows": rows, "bad_rows": bad, "open_bad_rows": open_bad,
            "blank_rows": blank + open_blank, "duplicate_log_ids": duplicates,
            "in_progress": in_progress,
            "tab_missing": {TAB_FETCH_LOG: closed is None, TAB_FETCH_LOG_OPEN: opened is None}}


def load_fetch_log(*, mask: Mask) -> dict:
    """`fetch_log` 表（與 `fetch_log_open` 合併，`44` 形狀；依 `started_at` 排序）。

    回傳 `{"rows": [...], "bad_rows", "open_bad_rows", "blank_rows", "duplicate_log_ids",
    "in_progress", "tab_missing": {分頁: bool}}`。
    ⚠️ 中斷判定用讀取當下的時間；結果快取 60 秒，所以「進行中 → 中斷」的轉換最多晚 60 秒出現。
    """
    return _cached_read("fetch_log", (TAB_FETCH_LOG, TAB_FETCH_LOG_OPEN),
                        lambda tabs: _reduce_fetch_log(tabs, _utcnow()), mask=mask)


# ════════════════════════ market_indicator ════════════════════════

def _mi_pk(rec) -> tuple:
    return (rec["indicator_key"], rec["obs_date"], rec["release_date"])


# 同一筆的比較欄：排除 `fetched_at` 與 `is_revised`（`50` 5.2 複驗後更正）。
_MI_SAME_COLUMNS = ("value_num", "value_unit", "source_tier")


def _mi_same(a, b) -> bool:
    return all(a[c] == b[c] for c in _MI_SAME_COLUMNS)


def _mi_revised(pk, pks) -> bool:
    """同一 (indicator_key, obs_date) 已存在 release_date 較早的列 → TRUE（`50` 5.2）。"""
    key, obs, rel = pk
    return any(k == key and o == obs and r < rel for (k, o, r) in pks)


def _reduce_market_indicator(tabs) -> dict:
    data = _data_rows(tabs, TAB_MARKET_INDICATOR)
    if data is None:
        return {"rows": [], "bad_rows": [], "blank_rows": 0, "conflicts": [],
                "duplicates_merged": 0, "is_revised_mismatch": 0, "tab_missing": True}
    records, bad, blank = _parse_rows(MARKET_INDICATOR_SPEC, data)
    groups: dict = {}
    for rec in records:
        groups.setdefault(_mi_pk(rec), []).append(rec)
    all_pks = set(groups)
    rows, conflicts, merged, mismatch = [], [], 0, 0
    for pk, recs in groups.items():
        if any(not _mi_same(recs[0], r) for r in recs[1:]):
            conflicts.append({"key": pk, "rows": [
                {"row": r["_row"], "value_num": r["value_num"], "value_unit": r["value_unit"],
                 "source_tier": r["source_tier"]} for r in recs]})
            continue
        merged += len(recs) - 1
        first = min(recs, key=lambda r: r["_row"])
        revised = _mi_revised(pk, all_pks)
        if any(r["is_revised"] != revised for r in recs):
            mismatch += 1
        out = _public(first, MARKET_INDICATOR_SPEC)
        out["is_revised"] = revised
        rows.append((first["_row"], out))
    rows.sort(key=lambda item: item[0])
    return {"rows": [r for _n, r in rows], "bad_rows": bad, "blank_rows": blank,
            "conflicts": conflicts, "duplicates_merged": merged,
            "is_revised_mismatch": mismatch, "tab_missing": False}


def load_market_indicator(*, mask: Mask) -> dict:
    """`market_indicator` 表（讀取端依主鍵去重，`44` 形狀）。

    回傳 `{"rows", "bad_rows", "blank_rows", "conflicts"（主鍵相同、數值不同，整組不採用）,
    "duplicates_merged", "is_revised_mismatch"（儲存值與重算不符的主鍵數；以重算值為準）,
    "tab_missing"}`。
    """
    return _cached_read("market_indicator", (TAB_MARKET_INDICATOR,), _reduce_market_indicator,
                        mask=mask)


def append_market_indicator(rows: list, *, mask: Mask) -> dict:
    """寫入 `market_indicator`：先讀既有主鍵（盡力而為的寫前去重），只追加沒出現過的主鍵。

    - 同主鍵、同數值（除 `fetched_at`／`is_revised`）→ 不追加，計入 `already_present`。
    - 同主鍵、不同數值（與既有列，或同一批內互相矛盾）→ **整批都不追加**，回傳 `conflicts`
      （呼叫端據此把這次取數記為 failed；本檔拍板：failed 的取數不留下半批資料）。
    - `is_revised` 以「既有列＋本批」的主鍵集合重算後寫入（`50` 5.2）。
    - 追加可重試（`50` 第 6 節）。寫入後不論成敗都清快取。

    回傳 `{"appended": N, "already_present": N, "conflicts": [...]}`。
    """
    incoming = []
    for row in rows:
        cells = _serialize(MARKET_INDICATOR_SPEC, row)   # 不合格 → ValueError（呼叫端 bug）
        parsed, bad, _blank = _parse_rows(MARKET_INDICATOR_SPEC, [cells])
        if bad:
            raise ValueError(f"market_indicator 列格式化後無法解析：{bad[0]['reason']}")
        incoming.append(parsed[0])

    def op(spreadsheet):
        tabs = _read_tabs(spreadsheet, [TAB_MARKET_INDICATOR])
        ws, values = tabs[TAB_MARKET_INDICATOR]
        if ws is not None:
            _check_header(TAB_MARKET_INDICATOR, values, mask=mask)
            existing, _bad, _blank = _parse_rows(MARKET_INDICATOR_SPEC, values[1:])
        else:
            existing = []
        known: dict = {}
        for rec in existing:
            known.setdefault(_mi_pk(rec), rec)
        conflicts, fresh, present = [], {}, 0
        for rec in incoming:
            pk = _mi_pk(rec)
            other = known.get(pk) or fresh.get(pk)
            if other is not None:
                if _mi_same(other, rec):
                    present += 1
                else:
                    conflicts.append({"key": pk, "existing_value_num": other["value_num"],
                                      "new_value_num": rec["value_num"],
                                      "existing_value_unit": other["value_unit"],
                                      "new_value_unit": rec["value_unit"]})
                continue
            fresh[pk] = rec
        if conflicts or not fresh:
            return {"appended": 0, "already_present": present, "conflicts": conflicts}
        target = _worksheet_for_append(spreadsheet, TAB_MARKET_INDICATOR, tabs, mask=mask)
        all_pks = set(known) | set(fresh)
        out = []
        for pk, rec in fresh.items():
            row = _public(rec, MARKET_INDICATOR_SPEC)
            row["is_revised"] = _mi_revised(pk, all_pks)
            out.append(_serialize(MARKET_INDICATOR_SPEC, row))
        _append(target, out, retry=True)
        return {"appended": len(out), "already_present": present, "conflicts": []}

    _sid, result = _run(op, mask=mask, write=True)
    return result
