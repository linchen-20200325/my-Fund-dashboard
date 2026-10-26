"""shared/personal_oauth_keys.py — 新 B UI Personal OAuth 的 session_state 鍵名 SSOT（L0，純常數）。

出處：客戶 2026-10-26 正式裁示
`docs/evidence/decisions/2026-10-26_ui_v2_implementation_security_gate_decisions.md`
第 4 節（J-10：專屬 namespace，不重用舊 key）、第 8 節（J-5：Active Sheet runtime SSOT）。

為什麼住在 shared/（2026-10-26 由 `infra/personal_oauth.py` 搬來）：
Active／Pending Sheet 狀態機 `shared/active_sheet.py` 必須用同一組鍵名，而依 CLAUDE.md §8.2
「L0 Shared 不得依賴任何 L1+」，shared/ 不能 import infra/。唯一能讓兩邊共讀的位置就是
shared/。`infra/personal_oauth.py` 改從本模組匯入並原名 re-export，既有呼叫端
（`po.KEY_TOKENS` 等）不受影響。

本模組只放字串常數，不 import 任何 infra／repositories／services／ui／streamlit。
舊 UI 使用的 `gsheet_tokens`／`gsheet_email`／`_oauth_state` 一律不在這裡。
"""
from __future__ import annotations

SESSION_PREFIX: str = "b_oauth."
KEY_TOKENS: str = SESSION_PREFIX + "tokens"
KEY_ACCOUNT_SUB: str = SESSION_PREFIX + "account_sub"
KEY_ACCOUNT_EMAIL: str = SESSION_PREFIX + "account_email"
KEY_GRANTED_SCOPES: str = SESSION_PREFIX + "granted_scopes"
#: Active／Pending Sheet（裁示第 8 節 J-5）。讀寫邏輯見 `shared/active_sheet.py`；
#: `infra/personal_oauth.clear_session` 以前綴清除（登出／切換帳號時兩者皆清）。
KEY_ACTIVE_SHEET: str = SESSION_PREFIX + "active_sheet"
KEY_PENDING_SHEET: str = SESSION_PREFIX + "pending_sheet"
#: 本 session 已登記、尚未用掉的 OAuth state（B1：per-session 重用，不重複登記）。
KEY_AUTH_PENDING_STATE: str = SESSION_PREFIX + "pending_state"
KEY_AUTH_PENDING_EXPIRES: str = SESSION_PREFIX + "pending_state_expires_at"
#: 待確認登入（A1）：{"tokens", "sub", "email", "expires_at"}。get_tokens 不讀這個 key。
KEY_PENDING_LOGIN: str = SESSION_PREFIX + "pending_login"

SESSION_KEYS: tuple[str, ...] = (
    KEY_TOKENS,
    KEY_ACCOUNT_SUB,
    KEY_ACCOUNT_EMAIL,
    KEY_GRANTED_SCOPES,
    KEY_ACTIVE_SHEET,
    KEY_PENDING_SHEET,
    KEY_AUTH_PENDING_STATE,
    KEY_AUTH_PENDING_EXPIRES,
    KEY_PENDING_LOGIN,
)
