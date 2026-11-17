# -*- coding: utf-8 -*-
"""NAS 中繼站診斷預覽的 FAKE 輸入（純 dict；形狀＝`NasDiagObservation` 的建構參數）。

⚠️ 全部是人造的 FAKE 診斷結果：不是任何真實檢查、不代表任何真實 NAS 或來源的狀態。
不 import 任何 `ui_v3` 模組、`infra`、`services`、`requests`；不讀檔、不連網、不取憑證。
每個建構器每次呼叫都回傳全新的 dict。目標只用白名單標籤（不含網址）。
"""
from __future__ import annotations

FAKE_FIXTURE = True

FAKE_CHECKED_AT = "2026-11-16T10:30:00+08:00"
FAKE_TARGET = "MoneyDJ"


def _tested(**over) -> dict:
    base = {"proxy_configured": True, "nas_reachable": True, "route_used": "nas", "target_label": FAKE_TARGET,
            "target_http_status": 200, "error_class": "ok", "latency_ms": 380, "checked_at": FAKE_CHECKED_AT,
            "nas_error_class": None}
    base.update(over)
    return base


def not_configured() -> dict:
    """①未設定 NAS。"""
    return {"proxy_configured": False, "target_label": FAKE_TARGET}


def configured_untested() -> dict:
    """②已設定但尚未測試：沒有任何結果事實。"""
    return {"proxy_configured": True, "target_label": FAKE_TARGET}


def nas_ok() -> dict:
    """③NAS 成功、目標回 200。"""
    return _tested()


def degraded_direct() -> dict:
    """④NAS 失敗、直連成功。"""
    return _tested(nas_reachable=False, route_used="fallback_direct", latency_ms=1450, nas_error_class="proxy_unreachable")


def both_failed() -> dict:
    """⑤NAS 失敗、直連也失敗（逾時）。"""
    return _tested(nas_reachable=False, route_used="none", target_http_status=None, error_class="timeout",
                   latency_ms=15000, nas_error_class="proxy_unreachable")


def auth_407() -> dict:
    """⑥代理驗證失敗（407）：沒有任何目標嘗試。"""
    return _tested(nas_reachable=False, route_used="none", target_http_status=407, error_class="proxy_auth_407",
                   latency_ms=210, nas_error_class="proxy_auth_407")


def blocked_403() -> dict:
    """⑦a 目標回 403（NAS 可用、未降級）。"""
    return _tested(target_http_status=403, error_class="forbidden_403", latency_ms=520)


def blocked_403_then_direct() -> dict:
    """⑦b NAS 路徑被 403 後降級直連成功。"""
    return _tested(route_used="fallback_direct", latency_ms=1890, nas_error_class="forbidden_403")


def timeout() -> dict:
    """⑧NAS 可用、目標逾時。"""
    return _tested(target_http_status=None, error_class="timeout", latency_ms=15000)


def tls() -> dict:
    """⑨TLS／憑證問題。"""
    return _tested(target_http_status=None, error_class="tls", latency_ms=640)


def dns() -> dict:
    """⑩名稱解析失敗。"""
    return _tested(target_http_status=None, error_class="dns", latency_ms=95)


def contradiction() -> dict:
    """⑪矛盾輸入：路徑是 NAS，卻說 NAS 不可用。"""
    return _tested(nas_reachable=False, route_used="nas")


def rate_limited() -> dict:
    """⑫請求過多（429）。"""
    return _tested(target_http_status=429, error_class="rate_limited_429", latency_ms=300)


# 情境 id → (下拉選單標籤, 建構器)。順序即選單順序。
SCENARIOS = {
    "not_configured": ("①未設定 NAS", not_configured),
    "configured_untested": ("②已設定但尚未測試", configured_untested),
    "nas_ok": ("③NAS 成功＋目標 200", nas_ok),
    "degraded_direct": ("④NAS 失敗＋直連成功（降級）", degraded_direct),
    "both_failed": ("⑤NAS 失敗＋直連也失敗", both_failed),
    "auth_407": ("⑥代理驗證失敗（407）", auth_407),
    "blocked_403": ("⑦a 目標 403（NAS 可用）", blocked_403),
    "blocked_403_then_direct": ("⑦b NAS 路徑 403 後降級直連成功", blocked_403_then_direct),
    "timeout": ("⑧逾時", timeout),
    "tls": ("⑨TLS／憑證問題", tls),
    "dns": ("⑩名稱解析失敗", dns),
    "contradiction": ("⑪矛盾輸入（無法判定）", contradiction),
    "rate_limited": ("⑫請求過多（429）", rate_limited),
}
DEFAULT_SCENARIO = next(iter(SCENARIOS))


def build(scenario_id: str) -> dict:
    """情境 id → 全新的 observation 參數 dict；未知情境 KeyError（不猜）。"""
    return SCENARIOS[scenario_id][1]()
