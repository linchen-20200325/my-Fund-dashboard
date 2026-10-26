"""repositories/personal_drive_repository.py — 新 B UI Personal OAuth 的 Drive／Sheets 唯讀讀取（L1）。

規格來源：客戶 2026-10-26 裁示 `docs/evidence/decisions/2026-10-26_ui_v2_implementation_security_gate_decisions.md`
（J-1 唯讀 scope、J-5 Pending≠Active、J-7 不 fallback、J-9 九個 error code）與
`docs/v2/65_set_wireframe_and_cap_gate_01_02.md` 第 E 節（Sheet Picker／驗證三步）。

兩個函式，皆只用 `Authorization: Bearer` header（token 不進 URL／log／例外文字）：
- `list_spreadsheets(access_token)`：Drive v3 files.list（spreadsheet、trashed=false），
  依 (name, id) 決定性排序；空清單是合法的空，不是錯誤、也不補任何預設。
- `verify_spreadsheet(access_token, sheet_id)`：Sheets v4 spreadsheets.get 只讀中繼資料
  （fields=properties.title,sheets.properties.title），回 `shared.active_sheet.VerifyResult`。

驗證規則（65 第 E 節第 3 步「必要條件（必要分頁等，實作時另定）」未明定 → 本模組的選擇，須經客戶／總管覆核）：
  1. 試算表中繼資料可讀（spreadsheets.readonly）；
  2. 至少有一個「保單分頁」——標題不以 `_` 開頭、且不等於 `Policies`。
     這與 `repositories/policy_supplement_repository.py::_list_policy_tabs`（持倉讀取的唯一分頁來源）
     的保單分頁定義一致；`_持倉補充`／`_保單資料` 為選填補充分頁，缺少不算不合格。
  ⚠️ 此規則仍待客戶覆核，身分檢查偏弱：任何「有一個一般分頁」的試算表都會通過（不比對欄位表頭）。
  缺保單分頁 → `SCHEMA_INVALID`（驗證失敗，不是「找不到」）。不檢查欄位表頭（那需要讀儲存格內容，
  屬後續持倉讀取批次的責任）。

錯誤對應（九個 code 之內；不新增）：401→AUTH_EXPIRED、403→PERMISSION_DENIED、404→SHEET_NOT_FOUND、
429／5xx→UPSTREAM_ERROR、其他非 2xx→UPSTREAM_ERROR、逾時／連線失敗→NETWORK_ERROR、
回應不是 JSON／形狀不對→UPSTREAM_ERROR、缺保單分頁→SCHEMA_INVALID。
⚠️ Google 的 403 也可能是配額／速率限制或 API 未啟用，一律對應 PERMISSION_DENIED（本批維持，不細分）。
本批不設回應大小上限。
例外 `PersonalDriveError` 只帶 code 與固定的安全訊息，不回放回應內容。
"""
from __future__ import annotations

import re
from typing import Any

import requests

from shared import ui_v2_error_codes as ec
from shared.active_sheet import VerifyResult

DRIVE_FILES_URL = "https://www.googleapis.com/drive/v3/files"
SHEETS_URL = "https://sheets.googleapis.com/v4/spreadsheets"
HTTP_TIMEOUT: tuple[float, float] = (5.0, 15.0)  # (connect, read) 秒
PAGE_SIZE = 200
MAX_PAGES = 10  # 上限 2000 本；超過即截斷之外的不列（見 list_spreadsheets docstring）
_SHEET_ID_RE = re.compile(r"^[A-Za-z0-9_-]{10,200}$")
_DEFAULT_POLICY_TAB = "Policies"  # 與 repositories/policy/_helpers.py::DEFAULT_WORKSHEET 一致（測試鎖定）

_SAFE_MESSAGES = {
    ec.AUTH_EXPIRED: "Google 登入已過期，需要重新登入",
    ec.PERMISSION_DENIED: "沒有權限讀取該資源",
    ec.SHEET_NOT_FOUND: "找不到該試算表",
    ec.UPSTREAM_ERROR: "Google 服務回應異常",
    ec.NETWORK_ERROR: "無法連線到 Google",
    ec.SCHEMA_INVALID: "試算表不符合必要條件（缺少保單分頁）",
}


class PersonalDriveError(Exception):
    """只帶九個 code 之一與固定安全訊息；不含 token、URL、回應內容。"""

    def __init__(self, code: str) -> None:
        if code not in ec.ALL_ERROR_CODES:
            raise ValueError(f"非九個 error code 之一：{code!r}")
        self.code = code
        self.message = _SAFE_MESSAGES.get(code, "")
        super().__init__(f"{code}: {self.message}")


def _status_to_code(status: int) -> str:
    if status == 401:
        return ec.AUTH_EXPIRED
    if status == 403:
        return ec.PERMISSION_DENIED
    if status == 404:
        return ec.SHEET_NOT_FOUND
    return ec.UPSTREAM_ERROR  # 429、5xx、其他非 2xx


def _get_json(access_token: str, url: str, params: dict[str, Any]) -> dict:
    if not isinstance(access_token, str) or not access_token.strip():
        raise PersonalDriveError(ec.AUTH_REQUIRED)
    failure: str | None = None
    resp = None
    try:
        resp = requests.get(
            url,
            params=params,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=HTTP_TIMEOUT,
            allow_redirects=False,  # 不跟轉址：Authorization header 不會被帶去別的網域
        )
    except (requests.Timeout, requests.ConnectionError):
        failure = ec.NETWORK_ERROR
    except requests.RequestException:
        failure = ec.UPSTREAM_ERROR
    if failure is not None:
        # 在 except 區塊之外才拋：`__context__` 也是 None，`RequestException.request.headers`
        # （含 Authorization）從例外鏈走不到。
        raise PersonalDriveError(failure) from None
    status = getattr(resp, "status_code", None)
    if not isinstance(status, int) or not 200 <= status < 300:
        raise PersonalDriveError(_status_to_code(status if isinstance(status, int) else 0))
    try:
        data = resp.json()
    except ValueError:
        data = None
    if not isinstance(data, dict):
        raise PersonalDriveError(ec.UPSTREAM_ERROR)
    return data


def list_spreadsheets(access_token: str) -> list[dict[str, str]]:
    """列出目前帳號可存取、未進垃圾桶的試算表 `[{"id","name"}]`，依 (name, id) 排序。

    空清單回 `[]`（合法）。分頁最多 `MAX_PAGES` 頁；仍有下一頁卻達上限 → `UPSTREAM_ERROR`
    （不靜默截斷成「看起來完整」的清單）。缺 id／name 的項目屬回應異常 → `UPSTREAM_ERROR`。
    """
    params: dict[str, Any] = {
        "q": 'mimeType="application/vnd.google-apps.spreadsheet" and trashed=false',
        "pageSize": PAGE_SIZE,
        "supportsAllDrives": "true",
        "includeItemsFromAllDrives": "true",
        "fields": "nextPageToken,files(id,name)",
    }
    out: dict[str, str] = {}
    for _ in range(MAX_PAGES):
        data = _get_json(access_token, DRIVE_FILES_URL, params)
        files = data.get("files", [])
        if not isinstance(files, list):
            raise PersonalDriveError(ec.UPSTREAM_ERROR)
        for f in files:
            fid = f.get("id") if isinstance(f, dict) else None
            name = f.get("name") if isinstance(f, dict) else None
            if not (isinstance(fid, str) and fid and isinstance(name, str)):
                raise PersonalDriveError(ec.UPSTREAM_ERROR)
            out[fid] = name
        token = data.get("nextPageToken")
        if not token:
            return sorted(({"id": i, "name": n} for i, n in out.items()), key=lambda d: (d["name"], d["id"]))
        if not isinstance(token, str):
            raise PersonalDriveError(ec.UPSTREAM_ERROR)
        params = {**params, "pageToken": token}
    raise PersonalDriveError(ec.UPSTREAM_ERROR)


def _is_policy_tab(title: str) -> bool:
    return not title.startswith("_") and title != _DEFAULT_POLICY_TAB


def verify_spreadsheet(access_token: str, sheet_id: str) -> VerifyResult:
    """唯讀驗證一本試算表。成功 → `VerifyResult(ok=True, name=<試算表名稱>)`；失敗 → 帶 code。

    不拋 `PersonalDriveError`（一律轉成 `VerifyResult`，供 `activate_pending` 直接使用）。
    """
    if not isinstance(sheet_id, str) or not _SHEET_ID_RE.fullmatch(sheet_id):
        return VerifyResult(ok=False, error_code=ec.SHEET_NOT_FOUND, message=_SAFE_MESSAGES[ec.SHEET_NOT_FOUND])
    try:
        data = _get_json(
            access_token,
            f"{SHEETS_URL}/{sheet_id}",
            {"fields": "properties.title,sheets.properties.title"},
        )
        props = data.get("properties")
        title = props.get("title") if isinstance(props, dict) else None
        sheets = data.get("sheets")
        if not isinstance(title, str) or not isinstance(sheets, list):
            raise PersonalDriveError(ec.UPSTREAM_ERROR)
        tabs: list[str] = []
        for s in sheets:
            sp = s.get("properties") if isinstance(s, dict) else None
            t = sp.get("title") if isinstance(sp, dict) else None
            if not isinstance(t, str):
                raise PersonalDriveError(ec.UPSTREAM_ERROR)
            tabs.append(t)
    except PersonalDriveError as e:
        return VerifyResult(ok=False, error_code=e.code, message=e.message)
    if not any(_is_policy_tab(t) for t in tabs):
        return VerifyResult(ok=False, error_code=ec.SCHEMA_INVALID, message=_SAFE_MESSAGES[ec.SCHEMA_INVALID])
    return VerifyResult(ok=True, name=title)
