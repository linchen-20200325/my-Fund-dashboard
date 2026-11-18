# -*- coding: utf-8 -*-
"""路徑 B（單檔基本資料查詢）內部 view model：狀態、欄位級狀態與嚴格不變式（純 Python，只用標準函式庫）。

授權與邊界：`DEC-2026-11-18-02`（限縮補充 `DEC-2026-11-18-01` R1；經 ChatGPT 總管派工單轉述客戶「同意」，**待核**），
僅內部 adapter／view model／離線注入測試。設計依據 `docs/evidence/gate_d_path_b_contract_package_2026_11_18.md` 第 4～8 節——
**該文件是未核准的設計參考，不是已核准契約**。本檔**不是**頁面、**不是**資料接線，不得以此宣稱「🔍 找基金」頁面或路徑 B 已完成。

本檔**不取數、不讀任何持久層、不碰 secrets 與環境變數、不發網路請求、不寫入任何東西**，也**不含任何顯示字樣**
（字樣屬 renderer／wording 層，待核准）。

狀態（`LookupState`，互斥）：`NOT_QUERIED`（尚未查詢）／`BLOCKED`（入口攔截，沒有呼叫取數函式）／`SOURCE_FAILED`（取不到）／
`PAGE_UNMATCHED`（頁面無法確認是這一檔）／`RESULT`（有結果）。**沒有任何一個狀態或原因碼表達「基金不存在／查無」**——
取數失敗、頁面無法確認、入口攔截都不是對基金存在與否的結論。欄位級狀態（`FieldStatus`）只在 `RESULT` 內存在：`VALUE`／`MISSING`／`CONFLICT`。

僅五個內部測試欄位：輸入代碼（`input_code`）、基金名稱、配息方式、成立日期、經理費率。
**結構上不存在**的欄位（由測試以 `dataclasses.fields` 與 AST 鎖死）：幣別、淨值、報酬、績效、取得時間、觀察時間、來源／供應者名稱、
來源等級、原始回應、網址、例外訊息、完整查詢鍵、任何密鑰。

輸入回顯（`input_code`）：只在輸入是「可印刷 ASCII、長度不超過 `INPUT_ECHO_MAX`、不是網址形、不是 ISIN 形」時才可存入；
其餘（含被安全攔截者）**結構上不保留**，是 `__post_init__` 強制，不是交給 renderer 決定。
⚠️ 取數鍵通過入口格式檢查，**不等於**基金身分已確認；`input_code` 不代表基金身分（不冒用 R-ID-1，也不升格 R-ID-2／R-ID-3）。

契約不符（型別錯、不變式矛盾）一律 fail-closed：raise `LookupContractError`，訊息只含欄位名與型別名，**絕不回顯收到的值**。

⚠️ 取捨：基金名稱不合格（過長、含控制類字元、網址形）是 **raise `LookupContractError`**，而非降級成 `name_unconfirmed`。
單一來源的名稱異常因此會讓整頁拋契約錯誤，日後頁面層的單一例外邊界需接住；是否改映 `name_unconfirmed` 待總管／客戶。
⚠️ 控制類字元判斷用 `unicodedata.category` 以 `C` 開頭（含未指派碼位 `Cn`），結果**相依 Python 的 unicodedata 版本**：
新版 Unicode 才指派的字元在舊版直譯器會被判為 `Cn` 而拒絕。
⚠️ 身分揭露（QA 必修）：真實 L2 `resolve_full_keys` 可能經別名表把輸入映為**不同的 full_key**；`RESULT` 欄位屬於 full_key，**不保證等於輸入代碼**。
adapter 看不到 full_key。日後 loader 是否要傳入 `mapping_hit`／full_key 是 Decision Gate，本切片不裁決。
⚠️ `MISSING` 同時涵蓋「來源沒提供」與「MoneyDJ 同標籤出現不同值」；`CONFLICT` 在現行真實 L2 對這四欄不可達（L2 只對幣別用 inconsistent）。
要區分需 L2 結構化旗標（待客戶）。

保守處理的未決題（記錄於此，不自行裁決）：
- Q5 缺值字樣／符號：本檔只有 `MISSING` 狀態，不含任何字樣；契約包建議的費率欄「契約上目前無來源」結構標記**沒有實作**（未核准）。
- Q6 `INPUT_ECHO_MAX`＝64 與 ISIN 形判斷前先移除所有非英數字元：採契約包建議值，待客戶／設計者確認。
  待客戶確認的已知邊界：①「ISIN 形再多一個字元」的變體（形如 2 字母＋10 碼數字＋1 個字母）與含 `-` 後綴者**放行並回顯**；
  ②ISIN 形判斷會誤攔帶連字號、移除後恰為 2 字母＋9 英數＋數字結尾的合法 12 字元代碼（只舉形狀，不舉真實代碼）；
  ③裸主機名／IPv4（形如 `example.com`）不視為網址形，走 `code_format` 並**可回顯**。
- 成立日期「不晚於台灣今天」需要時鐘：本檔無時鐘，只驗日期格式、存在與年份下限；未來日期的判定留在 L2（`exp_profile`），本檔不重複。
"""
from __future__ import annotations

import datetime as _dt
import re
import unicodedata
from dataclasses import dataclass
from enum import Enum
from typing import Optional

__all__ = (
    "LookupContractError", "LookupSourceError", "LookupState", "FieldStatus", "FieldView", "ProfileFields", "FundLookupView",
    "INPUT_ECHO_MAX", "NAME_MAX", "MIN_INCEPTION_YEAR", "DIVIDEND_POLICY_ACCUM", "DIVIDEND_POLICY_DIST",
    "REASON_BLANK", "REASON_CONTROL_OR_NON_ASCII", "REASON_URL_SHAPE", "REASON_ISIN_SHAPE", "REASON_CODE_FORMAT", "REASON_KEY_REJECTED",
    "REASON_SOURCE_FAILED", "REASON_SOURCE_COOLING", "REASON_LOADER_IO_ERROR",
    "REASON_UNRECOGNIZED_PAGE", "REASON_NO_PAGE", "REASON_SOURCE_NOT_LISTED", "REASON_NAME_UNCONFIRMED",
    "BLOCKED_REASONS", "SOURCE_FAILED_REASONS", "PAGE_UNMATCHED_REASONS",
    "is_ascii_printable", "looks_like_url", "looks_like_isin", "is_safe_echo",
)

#: 輸入回顯的字元數上限（契約包建議值；合法代碼上限為 51＝30＋1＋20，故只留餘裕）。
INPUT_ECHO_MAX = 64
#: 基金名稱長度上限（保守值，超過視為契約不符）；名稱不得含控制字元、不得為網址形。
NAME_MAX = 200
#: 成立日期年份下限（對齊 L2 `exp_profile.MIN_INCEPTION_YEAR`；測試對照原始碼鎖死）。
MIN_INCEPTION_YEAR = 1900
DIVIDEND_POLICY_ACCUM = "accum"
DIVIDEND_POLICY_DIST = "dist"
_DIVIDEND_POLICIES = frozenset({DIVIDEND_POLICY_ACCUM, DIVIDEND_POLICY_DIST})

# 固定類別碼（key 形；不是訊息、不上畫面；正式字樣待 Gate）。
REASON_BLANK = "blank"
REASON_CONTROL_OR_NON_ASCII = "control_or_non_ascii"
REASON_URL_SHAPE = "url_shape"
REASON_ISIN_SHAPE = "isin_shape"
REASON_CODE_FORMAT = "code_format"
REASON_KEY_REJECTED = "key_rejected"
REASON_SOURCE_FAILED = "source_failed"
REASON_SOURCE_COOLING = "source_cooling"
REASON_LOADER_IO_ERROR = "loader_io_error"
REASON_UNRECOGNIZED_PAGE = "unrecognized_page"
REASON_NO_PAGE = "no_page"
REASON_SOURCE_NOT_LISTED = "source_not_listed"
REASON_NAME_UNCONFIRMED = "name_unconfirmed"

BLOCKED_REASONS = frozenset({REASON_BLANK, REASON_CONTROL_OR_NON_ASCII, REASON_URL_SHAPE, REASON_ISIN_SHAPE, REASON_CODE_FORMAT,
                             REASON_KEY_REJECTED})
SOURCE_FAILED_REASONS = frozenset({REASON_SOURCE_FAILED, REASON_SOURCE_COOLING, REASON_LOADER_IO_ERROR})
PAGE_UNMATCHED_REASONS = frozenset({REASON_UNRECOGNIZED_PAGE, REASON_NO_PAGE, REASON_SOURCE_NOT_LISTED, REASON_NAME_UNCONFIRMED})
# 被安全攔截、輸入原值結構上不得保留的原因。
_NEVER_ECHO_REASONS = frozenset({REASON_CONTROL_OR_NON_ASCII, REASON_URL_SHAPE, REASON_ISIN_SHAPE})


class LookupContractError(ValueError):
    """路徑 B 契約不符（fail-closed）。view model 與 adapter 的輸入驗證所拋；訊息只含欄位名與型別名，**絕不回顯收到的值**。"""


class LookupSourceError(Exception):
    """組裝端 loader 包裝層用來表示「取數本身失敗」（把自己的網路例外轉成它）。adapter 把它轉成 `SOURCE_FAILED`；
    例外訊息不被讀取、不進 view、不進 log。"""


class LookupState(Enum):
    NOT_QUERIED = "not_queried"
    BLOCKED = "blocked"
    SOURCE_FAILED = "source_failed"
    PAGE_UNMATCHED = "page_unmatched"
    RESULT = "result"


class FieldStatus(Enum):
    VALUE = "value"
    MISSING = "missing"
    CONFLICT = "conflict"


def _kind(value: object) -> str:
    return type(value).__name__


def _need(ok: bool, field: str, expected: str, value: object) -> None:
    if not ok:
        raise LookupContractError(f"{field}: expected {expected}, got {_kind(value)}") from None


# ───────────────────────── 輸入形狀判斷（adapter 的攔截與 view model 的回顯不變式共用同一份） ─────────────────────────
_URL_CHARS = frozenset(":/\\?&=#%@")
_URL_SUBSTRINGS = ("http", "www.", "moneydj")
_ALNUM = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789")
_ISIN_SHAPE = re.compile(r"[A-Z]{2}[A-Z0-9]{9}[0-9]")


def is_ascii_printable(text: str) -> bool:
    """正向白名單：每個字元都在 0x20–0x7e（可印刷 ASCII）。零寬、全形、DEL、C1、tab、換行、各種空白一律不在白名單。"""
    return all(0x20 <= ord(c) <= 0x7E for c in text)


def looks_like_url(text: str) -> bool:
    """網址形：含任一字元 `: / \\ ? & = # % @`，或（不分大小寫）含子字串 `http`、`www.`、`moneydj`。"""
    lowered = text.lower()
    return any(c in _URL_CHARS for c in text) or any(s in lowered for s in _URL_SUBSTRINGS)


def looks_like_isin(text: str) -> bool:
    """ISIN 形（結構判斷，**不檢查檢查碼**）：判斷前暫時移除所有非英數字元並轉大寫，再整段比對 2 字母＋9 英數＋1 數字。"""
    squeezed = "".join(c for c in text if c in _ALNUM).upper()
    return _ISIN_SHAPE.fullmatch(squeezed) is not None


def is_safe_echo(text: object) -> bool:
    """可存入 view model 的輸入原值：字串、長度 ≤ `INPUT_ECHO_MAX`、可印刷 ASCII、非網址形、非 ISIN 形。"""
    return (isinstance(text, str) and len(text) <= INPUT_ECHO_MAX and is_ascii_printable(text)
            and not looks_like_url(text) and not looks_like_isin(text))


# ───────────────────────── view model ─────────────────────────

@dataclass(frozen=True)
class FieldView:
    """單一欄位。`VALUE` ⇔ `value` 為非空白字串；`MISSING`／`CONFLICT` 時 `value` 必為 None（缺值不寫成 0、「無」、「不配息」）。"""

    status: FieldStatus
    value: Optional[str] = None

    def __post_init__(self) -> None:
        _need(isinstance(self.status, FieldStatus), "status", "FieldStatus", self.status)
        if self.status is FieldStatus.VALUE:
            _need(isinstance(self.value, str) and self.value.strip() != "", "value", "non-blank str when status is VALUE", self.value)
        else:
            _need(self.value is None, "value", "None when status is not VALUE", self.value)


def _is_safe_name(text: str) -> bool:
    lowered = text.lower()
    return (len(text) <= NAME_MAX and not any(unicodedata.category(c).startswith("C") for c in text)
            and "http" not in lowered and "www." not in lowered)


def _is_iso_date(text: str) -> bool:
    if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", text) is None:
        return False
    try:
        parsed = _dt.date.fromisoformat(text)
    except ValueError:
        return False
    return parsed.year >= MIN_INCEPTION_YEAR


@dataclass(frozen=True)
class ProfileFields:
    """四個內部測試欄位（輸入代碼在 `FundLookupView`）。名稱是身分綁定證據，`RESULT` 內必為 `VALUE`；經理費率目前恆缺值。"""

    fund_name: FieldView
    dividend_policy: FieldView
    inception_on: FieldView
    mgmt_fee_rate_pct: FieldView

    def __post_init__(self) -> None:
        for name in ("fund_name", "dividend_policy", "inception_on", "mgmt_fee_rate_pct"):
            _need(isinstance(getattr(self, name), FieldView), name, "FieldView", getattr(self, name))
        _need(self.fund_name.status is FieldStatus.VALUE, "fund_name", "VALUE (identity-binding evidence)", self.fund_name)
        _need(isinstance(self.fund_name.value, str) and _is_safe_name(self.fund_name.value), "fund_name", "short text without control characters or url shape", self.fund_name.value)
        _need(self.mgmt_fee_rate_pct.status is FieldStatus.MISSING, "mgmt_fee_rate_pct", "MISSING (no source by contract)", self.mgmt_fee_rate_pct)
        if self.dividend_policy.status is FieldStatus.VALUE:
            _need(self.dividend_policy.value in _DIVIDEND_POLICIES, "dividend_policy", "accum or dist", self.dividend_policy.value)
        if self.inception_on.status is FieldStatus.VALUE:
            _need(_is_iso_date(self.inception_on.value), "inception_on", "ISO date YYYY-MM-DD", self.inception_on.value)


@dataclass(frozen=True)
class FundLookupView:
    """路徑 B 單一 view model。`fields` 只有 `RESULT` 才有；其餘狀態結構上不帶任何欄位值。"""

    state: LookupState
    input_code: Optional[str] = None
    reason_code: Optional[str] = None
    fields: Optional[ProfileFields] = None

    def __post_init__(self) -> None:
        _need(isinstance(self.state, LookupState), "state", "LookupState", self.state)
        if self.input_code is not None:
            _need(is_safe_echo(self.input_code), "input_code", "safe echo (printable ASCII, short, not url/ISIN shaped) or None", self.input_code)
        if self.state is LookupState.NOT_QUERIED:
            _need(self.input_code is None, "input_code", "None when state is not-queried", self.input_code)
            _need(self.reason_code is None, "reason_code", "None when state is not-queried", self.reason_code)
            _need(self.fields is None, "fields", "None when state is not-queried", self.fields)
            return
        if self.state is LookupState.RESULT:
            _need(self.reason_code is None, "reason_code", "None when state is RESULT", self.reason_code)
            _need(isinstance(self.fields, ProfileFields), "fields", "ProfileFields when state is RESULT", self.fields)
        else:
            allowed = {LookupState.BLOCKED: BLOCKED_REASONS, LookupState.SOURCE_FAILED: SOURCE_FAILED_REASONS,
                       LookupState.PAGE_UNMATCHED: PAGE_UNMATCHED_REASONS}[self.state]
            _need(isinstance(self.reason_code, str) and self.reason_code in allowed, "reason_code", "a known category code for this state", self.reason_code)
            _need(self.fields is None, "fields", "None when state is not RESULT", self.fields)
        if self.state is LookupState.BLOCKED:
            if self.reason_code in _NEVER_ECHO_REASONS:
                _need(self.input_code is None, "input_code", "None for a safety-blocked input", self.input_code)
            elif self.reason_code == REASON_BLANK:
                _need(isinstance(self.input_code, str) and self.input_code.strip(" ") == "", "input_code", "spaces-only str for blank", self.input_code)
            elif self.reason_code == REASON_KEY_REJECTED:
                _need(isinstance(self.input_code, str) and self.input_code.strip(" ") != "", "input_code", "str for key_rejected", self.input_code)
        else:
            # SOURCE_FAILED／PAGE_UNMATCHED／RESULT 只可能在輸入通過全部入口規則之後出現，所以輸入原值必保留。
            _need(isinstance(self.input_code, str) and self.input_code.strip(" ") != "", "input_code", "non-blank str once the input passed screening",
                  self.input_code)
