# -*- coding: utf-8 -*-
"""NAS 中繼站診斷測試的共用支援（純資料；不 import ui_v3、不連網）。

`SCENARIO_KWARGS` 是 poc 的 FAKE 輸入（`poc/nas_diag_preview/nas_diag_fake_inputs.py`）的**獨立副本**，
由 `tests/poc_nas_diag_preview` 的 drift 測試鎖定兩邊逐一相等；`EXPECTED` 是各情境「應該判成什麼」的期望表。
"""
from __future__ import annotations

CHECKED_AT = "2026-11-16T10:30:00+08:00"
TARGET = "MoneyDJ"

# 污染欄位 sentinel（測試內現編；餵給 dataclass 必須被拒，且不得出現在任何輸出）
SECRET = "SECRET-pw-9f3a"
POISON_URL = "http://u:" + SECRET + "@h:3128"
POISON_HOST = "nas.internal.example"
POISON_TOKENS = (SECRET, "u:" + SECRET, "h:3128", POISON_HOST, "://", "@")


def _tested(**over) -> dict:
    base = {"proxy_configured": True, "nas_reachable": True, "route_used": "nas", "target_label": TARGET,
            "target_http_status": 200, "error_class": "ok", "latency_ms": 380, "checked_at": CHECKED_AT,
            "nas_error_class": None}
    base.update(over)
    return base


SCENARIO_KWARGS = {
    "not_configured": {"proxy_configured": False, "target_label": TARGET},
    "configured_untested": {"proxy_configured": True, "target_label": TARGET},
    "nas_ok": _tested(),
    "degraded_direct": _tested(nas_reachable=False, route_used="fallback_direct", latency_ms=1450, nas_error_class="proxy_unreachable"),
    "both_failed": _tested(nas_reachable=False, route_used="none", target_http_status=None, error_class="timeout", latency_ms=15000,
                           nas_error_class="proxy_unreachable"),
    "auth_407": _tested(nas_reachable=False, route_used="none", target_http_status=407, error_class="proxy_auth_407", latency_ms=210,
                        nas_error_class="proxy_auth_407"),
    "blocked_403": _tested(target_http_status=403, error_class="forbidden_403", latency_ms=520),
    "blocked_403_then_direct": _tested(route_used="fallback_direct", latency_ms=1890, nas_error_class="forbidden_403"),
    "timeout": _tested(target_http_status=None, error_class="timeout", latency_ms=15000),
    "tls": _tested(target_http_status=None, error_class="tls", latency_ms=640),
    "dns": _tested(target_http_status=None, error_class="dns", latency_ms=95),
    "contradiction": _tested(nas_reachable=False, route_used="nas"),
    "rate_limited": _tested(target_http_status=429, error_class="rate_limited_429", latency_ms=300),
}

# 情境 → (state, nas_health, target_health, reason_key)
EXPECTED = {
    "not_configured": ("not_configured", "not_configured", "not_tested", "not_configured"),
    "configured_untested": ("not_tested", "not_tested", "not_tested", "not_tested"),
    "nas_ok": ("ok", "ok", "ok", "ok"),
    "degraded_direct": ("degraded_direct", "failed", "ok", "degraded"),
    "both_failed": ("failed", "failed", "failed", "both_failed"),
    "auth_407": ("failed", "failed", "not_tested", "nas_failed"),
    "blocked_403": ("failed", "ok", "failed", "target_failed"),
    "blocked_403_then_direct": ("degraded_direct", "failed", "ok", "degraded"),
    "timeout": ("failed", "ok", "failed", "target_failed"),
    "tls": ("failed", "ok", "failed", "target_failed"),
    "dns": ("failed", "ok", "failed", "target_failed"),
    "contradiction": ("undetermined", "undetermined", "undetermined", "contradiction"),
    "rate_limited": ("failed", "ok", "failed", "target_failed"),
}


def kwargs(sid: str) -> dict:
    return dict(SCENARIO_KWARGS[sid])
