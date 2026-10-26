"""shared/active_sheet.py — 新 B UI 的 Active／Pending Sheet runtime 狀態機（L0，純邏輯）。

規格來源：
- 客戶 2026-10-26 正式裁示
  `docs/evidence/decisions/2026-10-26_ui_v2_implementation_security_gate_decisions.md`
  第 8 節（J-5：`st.session_state` ＝ Active Sheet runtime SSOT；Pending 與 Active 分開；
  驗證成功後才更新 Active；驗證失敗保留原 Active；不做跨 session 持久化；不寫回 Google Sheet）、
  第 9 節（J-7：不 fallback）、第 10 節（J-9：error code）、第 11 節（J-13：不自動用
  `POLICY_SHEET_ID`、不自動選第一本、不用舊 session 過期值）。
- `DEC-2026-10-25-04` J-4：Active Sheet ＝ 持倉／保單 workbook；Pending ≠ Active；
  驗證成功才切換；失敗保留舊 Active；不猜、不 fallback。

為什麼放在 shared/（不放 ui_v2/）：
`tests/ui_v2/test_ui_v2_live_import_guard.py` 第 (5) 條禁止 ui_v2 內任何檔 import 舊樹
（含 `shared`／`infra`），而本模組必須沿用 `infra/personal_oauth.py` 的 namespaced 鍵名與
`shared/ui_v2_error_codes.py` 的錯誤碼。放 shared/ 才能合法讀到兩者，且不必放寬任何白名單；
鍵名因此搬到 `shared/personal_oauth_keys.py`（personal_oauth 改從該處匯入）。

本模組的邊界：
- 不 import streamlit／infra／repositories／services／ui／ui_v2；不讀 secret、不讀環境變數、
  不呼叫任何 Google API、不寫檔。`state` 一律由呼叫端注入（任何 MutableMapping）。
- 唯讀驗證由呼叫端以 `verify(sheet_id) -> VerifyResult` 注入（下一批才接真的唯讀驗證）。
- 存進 `state` 的一律是純 dict（不是 dataclass），讀出時重新驗型；壞掉的紀錄視為「沒有」，不猜。

帳號切換的處理（擇一，理由寫明）：
Active 記下驗證當時的 `account_sub`。`get_active` 只在「目前有正式登入、且 sub 與驗證時相同」
才回 Active；否則回 None —— **不**另回一個「需重新驗證」的帶值狀態。理由：J-13 的畫面路徑
只有「⬜ 尚未選定持倉資料來源 → 前往 ⚙️ 設定」一條；若回帶值狀態，呼叫端就拿得到舊帳號的
sheet_id，正是 J-13「不得使用舊 session 過期值」與 J-7「不 fallback」要擋的形狀。
（實務上 `infra/personal_oauth.confirm_pending_login`／`logout` 換帳號時會先清整個 namespace，
本檢查是第二道防線。）`get_active` 不刪除過期紀錄（讀取無副作用）；它會在下一次登入確認、
登出或 `activate_pending` 成功時被覆寫或清掉。
"""
from __future__ import annotations

import time
from collections.abc import Callable, Mapping, MutableMapping
from dataclasses import dataclass

from shared import ui_v2_error_codes as ec
from shared.personal_oauth_keys import (
    KEY_ACCOUNT_SUB,
    KEY_ACTIVE_SHEET,
    KEY_PENDING_SHEET,
    KEY_TOKENS,
)


# ──────────────────────────────────────────────────────────────────────
# 型別
# ──────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class ActiveSheet:
    """已驗證、目前生效的持倉／保單 workbook。"""

    sheet_id: str
    name: str
    verified_at: float  # epoch 秒（驗證成功當下）
    account_sub: str  # 驗證當下的正式登入帳號 sub


@dataclass(frozen=True)
class PendingSheet:
    """使用者選了、尚未驗證的 workbook。Pending ≠ Active。"""

    sheet_id: str
    name: str


@dataclass(frozen=True)
class VerifyResult:
    """`verify(sheet_id)` 的回傳。`ok=False` 時 `error_code` 必屬九個 code 之一。

    `name`：驗證時讀到的試算表名稱（選填）；有給就以它為準，沒給沿用 Pending 的名稱。
    """

    ok: bool
    error_code: str | None = None
    name: str | None = None
    message: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.ok, bool):
            raise TypeError("VerifyResult.ok 必須是 bool")
        if self.ok and self.error_code is not None:
            raise ValueError("驗證成功時不得帶 error_code")
        if not self.ok and self.error_code not in ec.ALL_ERROR_CODES:
            raise ValueError(f"驗證失敗必須帶九個 error code 之一：{self.error_code!r}")


@dataclass(frozen=True)
class ActivationResult:
    """`activate_pending` 的回傳。失敗時 Active 不變、Pending 保留。"""

    ok: bool
    error_code: str | None = None
    active: ActiveSheet | None = None
    message: str = ""


# ──────────────────────────────────────────────────────────────────────
# 內部
# ──────────────────────────────────────────────────────────────────────
def _clean_str(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def current_account_sub(state: Mapping) -> str | None:
    """目前**正式**登入的帳號 sub；未登入（無 token、或 sub 缺／空白）→ None。

    待確認登入（`KEY_PENDING_LOGIN`）不算登入 —— 這裡只看正式登入的 `KEY_TOKENS` 與 `KEY_ACCOUNT_SUB`。
    """
    if not isinstance(state.get(KEY_TOKENS), Mapping):
        return None
    return _clean_str(state.get(KEY_ACCOUNT_SUB))


def _read_active_record(state: Mapping) -> ActiveSheet | None:
    rec = state.get(KEY_ACTIVE_SHEET)
    if not isinstance(rec, Mapping):
        return None
    sheet_id = _clean_str(rec.get("sheet_id"))
    sub = _clean_str(rec.get("account_sub"))
    name = rec.get("name")
    verified_at = rec.get("verified_at")
    if sheet_id is None or sub is None or not isinstance(name, str):
        return None
    if isinstance(verified_at, bool) or not isinstance(verified_at, (int, float)):
        return None
    return ActiveSheet(sheet_id=sheet_id, name=name, verified_at=float(verified_at), account_sub=sub)


# ──────────────────────────────────────────────────────────────────────
# 對外 API
# ──────────────────────────────────────────────────────────────────────
def get_active(state: Mapping) -> ActiveSheet | None:
    """目前生效的 Active Sheet；未登入、從未驗證、紀錄壞掉、或驗證時帳號 ≠ 目前帳號 → None。"""
    sub = current_account_sub(state)
    if sub is None:
        return None
    active = _read_active_record(state)
    if active is None or active.account_sub != sub:
        return None
    return active


def get_pending(state: Mapping) -> PendingSheet | None:
    """尚未驗證的 Pending Sheet；沒有或紀錄壞掉 → None。"""
    rec = state.get(KEY_PENDING_SHEET)
    if not isinstance(rec, Mapping):
        return None
    sheet_id = _clean_str(rec.get("sheet_id"))
    name = rec.get("name")
    if sheet_id is None or not isinstance(name, str):
        return None
    return PendingSheet(sheet_id=sheet_id, name=name)


def set_pending(state: MutableMapping, sheet_id: str, name: str) -> PendingSheet:
    """只改 Pending，不動 Active。sheet_id 必須是非空白字串、name 必須是字串，否則 ValueError。"""
    sid = _clean_str(sheet_id)
    if sid is None:
        raise ValueError("sheet_id 必須是非空白字串")
    if not isinstance(name, str):
        raise ValueError("name 必須是字串")
    pending = PendingSheet(sheet_id=sid, name=name.strip())
    state[KEY_PENDING_SHEET] = {"sheet_id": pending.sheet_id, "name": pending.name}
    return pending


def clear_pending(state: MutableMapping) -> None:
    """清掉 Pending；不動 Active。"""
    state.pop(KEY_PENDING_SHEET, None)


def activate_pending(
    state: MutableMapping,
    verify: Callable[[str], VerifyResult],
    now: float | None = None,
) -> ActivationResult:
    """驗證 Pending；成功才把它升為 Active（記驗證時間與當前 sub）並清 Pending。

    失敗一律：Active 不變、Pending 保留、回傳帶九個 code 之一的結果。
    - 未登入 → `AUTH_REQUIRED`（不呼叫 verify）。
    - 沒有 Pending → `UNAVAILABLE`（不呼叫 verify；沒有東西可驗）。
    - `verify` 回 `ok=False` → 原樣帶回它的 error_code。
    - 驗證期間帳號變了（登出或換人）→ `AUTH_REQUIRED`，不寫入。
    - 驗證期間 Pending 被換成別本 → `UNAVAILABLE`，不寫入（驗過的不是現在這本）。
    - `verify` 回的不是 `VerifyResult` → TypeError（呼叫端契約錯，不猜）。
    - `verify` 自己拋例外 → 原樣往上拋（§1 不吞）；此時尚未寫入任何東西，Active／Pending 皆不變。
    """
    sub = current_account_sub(state)
    if sub is None:
        return ActivationResult(ok=False, error_code=ec.AUTH_REQUIRED, message="尚未登入 Google")
    pending = get_pending(state)
    if pending is None:
        return ActivationResult(ok=False, error_code=ec.UNAVAILABLE, message="沒有待驗證的試算表")

    result = verify(pending.sheet_id)
    if not isinstance(result, VerifyResult):
        raise TypeError("verify 必須回傳 VerifyResult")
    if not result.ok:
        return ActivationResult(ok=False, error_code=result.error_code, message=result.message)

    if current_account_sub(state) != sub:
        return ActivationResult(ok=False, error_code=ec.AUTH_REQUIRED, message="驗證期間登入帳號已變更")
    if get_pending(state) != pending:
        return ActivationResult(ok=False, error_code=ec.UNAVAILABLE, message="驗證期間待驗證的試算表已變更")

    name = result.name.strip() if isinstance(result.name, str) and result.name.strip() else pending.name
    ts = time.time() if now is None else float(now)
    active = ActiveSheet(sheet_id=pending.sheet_id, name=name, verified_at=ts, account_sub=sub)
    state[KEY_ACTIVE_SHEET] = {
        "sheet_id": active.sheet_id,
        "name": active.name,
        "verified_at": active.verified_at,
        "account_sub": active.account_sub,
    }
    state.pop(KEY_PENDING_SHEET, None)
    return ActivationResult(ok=True, active=active)
