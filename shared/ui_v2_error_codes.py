"""shared/ui_v2_error_codes.py — 新 B UI 第一階段正式 error taxonomy（L0，純常數）。

出處：客戶 2026-10-26 正式裁示
`docs/evidence/decisions/2026-10-26_ui_v2_implementation_security_gate_decisions.md`
第 10 節（J-9）—— 至少建立以下九個 deterministic error categories。

規則（同裁示第 10 節）：
- error code 屬 domain/service contract；UI 再轉成人類可讀文字。
- 不以 exception string 作唯一邏輯 —— 呼叫端一律比對本模組的常數。
- Missing 與 Error 分開；Error 不得轉成 0／正常／安全／中性。

本模組是 L0 shared：只放字串常數，不 import 任何 infra／repositories／services／ui。
"""
from __future__ import annotations

AUTH_REQUIRED: str = "AUTH_REQUIRED"
AUTH_EXPIRED: str = "AUTH_EXPIRED"
AUTH_STATE_INVALID: str = "AUTH_STATE_INVALID"
PERMISSION_DENIED: str = "PERMISSION_DENIED"
SHEET_NOT_FOUND: str = "SHEET_NOT_FOUND"
SCHEMA_INVALID: str = "SCHEMA_INVALID"
NETWORK_ERROR: str = "NETWORK_ERROR"
UPSTREAM_ERROR: str = "UPSTREAM_ERROR"
UNAVAILABLE: str = "UNAVAILABLE"

#: 全集。新增 code 必須同時改裁示來源與本集合（測試鎖定恰為九個）。
ALL_ERROR_CODES: frozenset[str] = frozenset({
    AUTH_REQUIRED,
    AUTH_EXPIRED,
    AUTH_STATE_INVALID,
    PERMISSION_DENIED,
    SHEET_NOT_FOUND,
    SCHEMA_INVALID,
    NETWORK_ERROR,
    UPSTREAM_ERROR,
    UNAVAILABLE,
})
