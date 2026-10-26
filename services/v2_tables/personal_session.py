"""services/v2_tables/personal_session.py — 新 B UI Personal OAuth／Active Sheet 的 L2 薄橋接。

只把三塊已存在的東西接起來，不新增任何規則：
  `infra.personal_oauth`（登入／續期／登出，token HTTP 在那裡；本 L2 不 import requests）、
  `shared.active_sheet`（Pending／Active 狀態機）、
  `repositories.personal_drive_repository`（Drive 清單與唯讀驗證）。
`state` 一律由呼叫端注入（任何 MutableMapping）；本模組不 import streamlit／ui_v2，不讀
`st.user`／`st.experimental_user`，沒有 `POLICY_SHEET_ID`，不做任何 fallback（J-7／J-13）。

回傳慣例：除 `access_target` 外一律回純 dict；失敗是 `{"ok": False, "error_code": <九個 code 之一>}`，
不丟 `PersonalOAuthError`／`PersonalDriveError`（UI 以 code 比對，不比例外字串；J-9）。
`status()` 與任何回傳值都不含 token、code_verifier、授權碼。

驗證規則（沿用 `repositories/personal_drive_repository.py` docstring）：試算表中繼資料可讀
＋至少一個保單分頁（標題不以 `_` 開頭、且不等於 `Policies`）。65 第 E 節未明定必要條件，此為本批選擇，待覆核。

`login_state`：`pending_login`（有待確認登入，須使用者明確確認；優先於 logged_in 顯示，因為
換帳號時 UI 必須先讓使用者看見待確認的 email）／`logged_in`（正式登入）／`logged_out`。
`email` 只在正式登入時給；待確認的 email 放 `pending_login_email`。

Sheet Picker 的 id 白名單：`list_for_picker` 成功時把 `{account_sub, sheets:{id:name}}` 存在
`KEY_PICKER_IDS`；`select_pending` 只收這份清單內的 id（名稱以清單為準，不收呼叫端自帶的名稱），
所以不能用手打／猜的 ID 進 Pending。清單失敗時白名單一併清掉（不留過期清單可選）。
登出／換帳號由 `clear_session` 依前綴清空（該 key 在 `SESSION_KEYS`）。

Pending Sheet 本身不帶 account_sub；它只因「`clear_session` 在每一次換帳號／登出／確認新登入時整個
namespace 清空」而安全。第一階段 UI 必須一律經 `select_pending` 選本（不得直接以自由輸入的 id 呼叫
`shared.active_sheet.set_pending`）。

L1 回 AUTH_EXPIRED（Drive／Sheets 回 401，代表快取的 access_token 已被 Google 拒絕、但本機 expires_at
還沒到）時，`list_for_picker`／`use_pending` 會 `po.clear_session`（與 `ensure_fresh` 自己遇到
AUTH_EXPIRED 的語意一致：清整個 session、要求重新登入），否則下一次 `ensure_fresh` 會一直重用這顆死 token。
不改 `infra.personal_oauth` 的安全模型；不嘗試強制續期（該模組沒有公開的強制續期入口）。
"""
from __future__ import annotations

from typing import Any, MutableMapping

import infra.personal_oauth as po
from repositories import personal_drive_repository as drive
from repositories import personal_policy_reader as policy_cache
from shared import active_sheet as asheet
from shared import ui_v2_error_codes as ec
from shared.personal_oauth_keys import KEY_PICKER_IDS


class PersonalSessionError(Exception):
    """`access_target` 專用：只帶九個 code 之一，不含 token。"""

    def __init__(self, code: str) -> None:
        if code not in ec.ALL_ERROR_CODES:
            raise ValueError(f"非九個 error code 之一：{code!r}")
        self.code = code
        super().__init__(code)


def _fail(code: str) -> dict[str, Any]:
    return {"ok": False, "error_code": code}


def _active_dict(a: asheet.ActiveSheet | None) -> dict[str, Any] | None:
    if a is None:
        return None
    return {"name": a.name, "id": a.sheet_id, "verified_at": a.verified_at}


def status(state: MutableMapping) -> dict[str, Any]:
    """目前登入／Pending／Active 的純 dict 快照（無 token）。"""
    sub = asheet.current_account_sub(state)
    pending_login = po.get_pending_login(state)
    if pending_login is not None:
        login_state = "pending_login"
    elif sub is not None:
        login_state = "logged_in"
    else:
        login_state = "logged_out"
    email = state.get(po.KEY_ACCOUNT_EMAIL) if sub is not None else None
    pending = asheet.get_pending(state)
    return {
        "login_state": login_state,
        "email": email if isinstance(email, str) else None,
        "pending_login_email": pending_login.get("email") if pending_login else None,
        "pending_sheet": {"id": pending.sheet_id, "name": pending.name} if pending else None,
        "active_sheet": _active_dict(asheet.get_active(state)),
    }


def begin_login(state: MutableMapping) -> dict[str, Any]:
    try:
        r = po.begin_authorization(state)
    except po.PersonalOAuthError as e:
        return _fail(e.code)
    return {"ok": True, "authorize_url": r["authorize_url"]}


def complete_login(state: MutableMapping, code: Any, state_param: Any) -> dict[str, Any]:
    """callback；成功只進「待確認登入」（Pending login），不啟用。"""
    try:
        r = po.complete_authorization(state, code, state_param)
    except po.PersonalOAuthError as e:
        return _fail(e.code)
    return {"ok": True, "pending_login_email": r["email"]}


def _drop_account_cache(state: MutableMapping) -> None:
    """丟掉目前（舊）帳號在持倉讀取快取裡的內容：登出、換帳號、確認新登入、AUTH_EXPIRED 清 session 前呼叫。"""
    sub = asheet.current_account_sub(state)
    if sub is not None:
        policy_cache.drop_account(sub)


def current_sub(state: MutableMapping):
    """目前正式登入的帳號 sub（未登入 → None）。呼叫端在 `access_target`／`ensure_fresh` **之前**取，
    因為續期失敗時 `ensure_fresh` 會自己清 session，之後就讀不到 sub 了。"""
    return asheet.current_account_sub(state)


def handle_read_error(state: MutableMapping, code: str, prior_sub=None) -> None:
    """讀取失敗後的善後（`prior_sub`：失敗前取的帳號 sub，見 `current_sub`）。
    - `AUTH_EXPIRED`（401：本機 expires_at 還沒到、但 token 已被 Google 拒絕）→ 與 `list_for_picker`／`use_pending`
      同一個處置：丟該帳號的讀取快取、清整個 session（要求重新登入），否則下一次 `ensure_fresh` 會一直重用這顆死 token。
    - 其他 code：若 session 已被別處清掉（`ensure_fresh` 遇到 PERMISSION_DENIED／AUTH_EXPIRED 會自己清）而 sub 已讀不到，
      仍以 `prior_sub` 丟該帳號的快取。session 還在的其他失敗（網路、5xx…）不動。"""
    sub = prior_sub if isinstance(prior_sub, str) and prior_sub.strip() else asheet.current_account_sub(state)
    if code == ec.AUTH_EXPIRED:
        if sub is not None:
            policy_cache.drop_account(sub)
        po.clear_session(state)
    elif asheet.current_account_sub(state) is None and sub is not None:
        policy_cache.drop_account(sub)


def confirm_login(state: MutableMapping) -> dict[str, Any]:
    _drop_account_cache(state)   # 確認的可能是另一個帳號：舊帳號的讀取快取不留
    try:
        r = po.confirm_pending_login(state)
    except po.PersonalOAuthError as e:
        return _fail(e.code)
    return {"ok": True, "email": r["email"]}


def reject_login(state: MutableMapping) -> dict[str, Any]:
    r = po.reject_pending_login(state)
    return {"ok": True, "revoke_confirmed": r.revoke_confirmed}


def logout(state: MutableMapping) -> dict[str, Any]:
    _drop_account_cache(state)
    r = po.logout(state)
    return {"ok": True, "revoke_confirmed": r.revoke_confirmed}


def switch_account(state: MutableMapping) -> dict[str, Any]:
    """登出（清 Active／Pending）→ 開始新授權；不沿用舊 token。"""
    _drop_account_cache(state)
    try:
        r = po.begin_account_switch(state)
    except po.PersonalOAuthError as e:
        return _fail(e.code)
    return {"ok": True, "authorize_url": r["authorize_url"], "revoke_confirmed": r["logout"].revoke_confirmed}


def _fresh_token(state: MutableMapping) -> str:
    return po.ensure_fresh(state)["access_token"]


def list_for_picker(state: MutableMapping) -> dict[str, Any]:
    """續期 → 列出可存取的試算表。任何失敗都不 fallback，且清掉白名單。"""
    state.pop(KEY_PICKER_IDS, None)
    try:
        token = _fresh_token(state)
        sheets = drive.list_spreadsheets(token)
    except po.PersonalOAuthError as e:
        return _fail(e.code)
    except drive.PersonalDriveError as e:
        if e.code == ec.AUTH_EXPIRED:
            po.clear_session(state)
        return _fail(e.code)
    sub = asheet.current_account_sub(state)
    if sub is None:  # 續期失敗路徑會清 session；走到這裡仍無 sub ＝ 不可信
        return _fail(ec.AUTH_REQUIRED)
    state[KEY_PICKER_IDS] = {"account_sub": sub, "sheets": {s["id"]: s["name"] for s in sheets}}
    return {"ok": True, "sheets": sheets}


def select_pending(state: MutableMapping, sheet_id: str, name: str = "") -> dict[str, Any]:
    """把清單中的一本設為 Pending（≠ Active）。id 不在最近一次清單內 → 拒絕。

    `name` 參數僅為相容簽名；實際名稱取自清單。"""
    sub = asheet.current_account_sub(state)
    if sub is None:
        return _fail(ec.AUTH_REQUIRED)
    rec = state.get(KEY_PICKER_IDS)
    sheets = rec.get("sheets") if isinstance(rec, dict) and rec.get("account_sub") == sub else None
    if not isinstance(sheets, dict) or not isinstance(sheet_id, str) or sheet_id not in sheets:
        return _fail(ec.SHEET_NOT_FOUND)
    p = asheet.set_pending(state, sheet_id, sheets[sheet_id])
    return {"ok": True, "pending_sheet": {"id": p.sheet_id, "name": p.name}}


def use_pending(state: MutableMapping) -> dict[str, Any]:
    """［使用這一本］：續期 → 唯讀驗證 → 成功才升為 Active；失敗 Active 不變、Pending 保留。"""
    try:
        token = _fresh_token(state)
    except po.PersonalOAuthError as e:
        return _fail(e.code)
    res = asheet.activate_pending(state, lambda sid: drive.verify_spreadsheet(token, sid))
    if not res.ok:
        if res.error_code == ec.AUTH_EXPIRED:
            po.clear_session(state)  # 死 token：與 ensure_fresh 的 AUTH_EXPIRED 語意一致
        return _fail(res.error_code or ec.UNAVAILABLE)
    return {"ok": True, "active_sheet": _active_dict(res.active)}


def access_target(state: MutableMapping) -> tuple[str, str, str]:
    """（sheet_id, access_token, account_sub）供後續唯讀讀取；沒有可用的 Active → `PersonalSessionError`。

    未登入 → AUTH_REQUIRED；續期失敗 → 該 code；沒有（或帳號不符的）Active → UNAVAILABLE（J-13：
    不自動用任何預設／第一本）。"""
    try:
        token = _fresh_token(state)
    except po.PersonalOAuthError as e:
        raise PersonalSessionError(e.code) from None
    active = asheet.get_active(state)
    if active is None:
        raise PersonalSessionError(ec.UNAVAILABLE)
    return active.sheet_id, token, active.account_sub
