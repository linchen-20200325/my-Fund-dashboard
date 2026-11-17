# -*- coding: utf-8 -*-
"""NAS 中繼站診斷的 view model（隔離式離線預覽用；純資料＋純函式，frozen、建構時驗證）。

- 輸入 `NasDiagObservation` 全是「已觀測的事實」，由呼叫端（本批只有離線注入的假資料）提供；本檔**不取數、不連線、不讀憑證**。
  只可 import 標準函式庫與 `ui_v3.viewmodels` 內部模組（刻意不 import 任何舊樹模組；失敗分類名稱與
  `shared/backoff_policy.py` 的差異由測試鎖定，不在這裡 import）。
- 輸入**沒有任何「原始例外字串」欄位**：外部例外文字可能夾帶帳密或內網位址，所以只收有限列舉的分類。
  建構時另掃每個字串欄位：含 `://`、`user:pass@` 形字串、或不在白名單字元內者，一律 `ValueError`（訊息不含欄位值）。
- `classify()` 分開判定「NAS 中繼健康度」與「目標網站可用性」兩軸；六態：未設定／尚未測試／連線成功／連線失敗／已降級直連／無法判定。
  - NAS 失敗但直連成功 ≠ NAS 成功：state＝已降級直連，NAS 軸＝失敗。
  - 缺值 ≠ 0 ≠ 成功：沒有證據就是「尚未測試」或「無法判定」，不會被當成成功。
  - 互相矛盾的輸入（例：路徑是 NAS 但 NAS 不可達）→ 無法判定，不猜。
- 暫行：六態的名稱、原因鍵都是預覽用，字樣見 `nas_diag_wording.py`（暫行、未核准）；本檔不放任何畫面字樣。

## 欄位語意（本預覽的約定；皆暫行）

- `proxy_configured`：是否已設定 NAS 中繼站（True／False／None＝不知道）。
- `nas_reachable`：**NAS 出口是否可用於取得目標**（網路可達、驗證通過，且出口沒有被目標網站封鎖；True／False／None＝沒檢查）。
  **採信標準（2026-11-17 明寫）**：`route_used=nas` 且 `nas_reachable=True`，最終結果是目標側回應（含 403／429／其他）時採信 NAS 軸 ok——
  因為已有「經由 NAS 收到目標網站回的 HTTP 回應」這個證據，代表 NAS 這一段至少轉得通。逾時／名稱解析／TLS 沒有收到任何 HTTP 回應，
  無法區分是 NAS 側或目標側，故兩軸皆無法判定。經 NAS 的 403／429／其他是否也該改無法判定，**待客戶／設計者裁示**（BL-0550 Pending (7)），本檔暫不改。
  所以「NAS 出口被目標 403 封鎖後降級直連」是 `nas_reachable=False`＋`nas_error_class=forbidden_403`；
  而目標網站直接回 403 給經由 NAS 的請求、且沒有降級（`route_used=nas`）時，NAS 出口仍被視為可用（目標軸失敗）——這是預覽約定。
  `route_used=nas` 時逾時／名稱解析／TLS **沒有證據區分是 NAS 側或目標側**：兩軸皆「無法判定」（reason＝no_side_evidence），
  該分類另存 `unattributed_cause_key`（不歸給任何一側）。（舊預覽約定「判 NAS 軸正常」已於 2026-11-17 移除。）
- 狀態碼與分類：407 允許沒有狀態碼；403／429 沒有狀態碼時以分類為準（目前**允許**，畫面狀態碼顯示缺值），不判矛盾。
- 目標軸為「尚未測試」（例：407，沒有任何目標嘗試）時，狀態碼與延遲屬於 NAS 這一段，目標卡不顯示。
- `route_used`：產出「最終目標結果」的路徑：`nas`／`direct`／`fallback_direct`（NAS 失敗後改走直連）／`none`（沒有任何路徑取得結果）。
- `nas_error_class`：**本預覽新增的選填欄位**——NAS 這一段失敗的分類（只在 `fallback_direct`／`none` 用）；`error_class` 則是「最終目標結果」的分類。
  這樣才分得出「NAS 為什麼失敗」與「目標網站為什麼取不到」。
- `route_used="none"` 時，若 `error_class` 是 NAS 自身故障類（407／NAS 無法連線）代表沒有任何目標嘗試（目標軸＝尚未測試）；
  若是目標側分類（逾時／名稱解析／TLS／403／429／其他）代表直連嘗試過但也失敗（目標軸＝失敗）。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Tuple

# ───────────────────────────── 列舉 ─────────────────────────────
ROUTES = ("nas", "direct", "fallback_direct", "none")
ERROR_CLASSES = ("ok", "proxy_auth_407", "forbidden_403", "rate_limited_429", "timeout", "dns", "tls",
                 "proxy_unreachable", "other")
NAS_FAULT_CLASSES = ("proxy_auth_407", "proxy_unreachable")          # 只可能是 NAS 這一段的故障
SIDE_AMBIGUOUS_CLASSES = ("timeout", "dns", "tls")                    # route=nas 時缺少區分 NAS 側／目標側的證據
TARGET_FAILURE_CLASSES = ("forbidden_403", "rate_limited_429", "timeout", "dns", "tls", "other")
NO_HTTP_STATUS_CLASSES = ("timeout", "dns", "tls", "proxy_unreachable")  # 沒有收到 HTTP 回應，不該有狀態碼

STATE_NOT_CONFIGURED = "not_configured"
STATE_NOT_TESTED = "not_tested"
STATE_OK = "ok"
STATE_FAILED = "failed"
STATE_DEGRADED = "degraded_direct"
STATE_UNDETERMINED = "undetermined"
STATES = (STATE_NOT_CONFIGURED, STATE_NOT_TESTED, STATE_OK, STATE_FAILED, STATE_DEGRADED, STATE_UNDETERMINED)

HEALTH_OK = "ok"
HEALTH_FAILED = "failed"
HEALTH_NOT_TESTED = "not_tested"
HEALTH_NOT_CONFIGURED = "not_configured"
HEALTH_UNDETERMINED = "undetermined"
NAS_HEALTHS = (HEALTH_OK, HEALTH_FAILED, HEALTH_NOT_TESTED, HEALTH_NOT_CONFIGURED, HEALTH_UNDETERMINED)
TARGET_HEALTHS = (HEALTH_OK, HEALTH_FAILED, HEALTH_NOT_TESTED, HEALTH_UNDETERMINED)

ROUTE_NAS = "route_nas"
ROUTE_DIRECT = "route_direct"
ROUTE_FALLBACK = "route_fallback_direct"
ROUTE_UNTESTED = "route_untested"
ROUTE_NONE = "route_none"
ROUTE_UNKNOWN = "route_unknown"
ROUTE_CODES = (ROUTE_NAS, ROUTE_DIRECT, ROUTE_FALLBACK, ROUTE_UNTESTED, ROUTE_NONE, ROUTE_UNKNOWN)

# reason_key＝整體結論的結構性原因（細節分類在 nas_cause_key／target_cause_key）。
REASON_KEYS = ("not_configured", "not_tested", "ok", "degraded", "target_failed", "nas_failed", "both_failed",
               "contradiction", "incomplete", "config_unknown", "no_timestamp", "nas_not_evaluated", "no_side_evidence")
CONFIG_SET = "configured"
CONFIG_NOT_SET = "not_configured"
CONFIG_UNKNOWN = "unknown"
CONFIG_STATES = (CONFIG_SET, CONFIG_NOT_SET, CONFIG_UNKNOWN)
# 原因分類鍵（人話原因查表用）：error_class → cause key。
CAUSE_OF_CLASS = {
    "proxy_auth_407": "cause_auth_407", "forbidden_403": "cause_blocked_403", "rate_limited_429": "cause_rate_limited_429",
    "timeout": "cause_timeout", "dns": "cause_dns", "tls": "cause_tls", "proxy_unreachable": "cause_nas_unreachable",
    "other": "cause_other",
}
CAUSE_KEYS = tuple(CAUSE_OF_CLASS.values())

# 與 `shared/backoff_policy.py` 失敗分類（退避冷卻 SSOT）的對映。本檔不 import 它；測試 import 兩邊，分類名稱漂移會紅。
# 退避分類沒有分「逾時／名稱解析／TLS」（都歸 unreachable），所以是多對一；`not_found` 是目標側回應，歸 other。
BACKOFF_KIND_TO_CLASSES = {
    "unreachable": ("timeout", "dns", "tls", "proxy_unreachable"),
    "server_error": ("other",),
    "blocked": ("forbidden_403",),
    "rate_limited": ("rate_limited_429",),
    "not_found": ("other",),
    "proxy_auth": ("proxy_auth_407",),
}

# 白名單標籤：英數、空白、連字號、中點與常用中日韓字元；長度 1～40。不含 `:`、`/`、`@`、`?`、`#`、`=`、`&`、`.`。
_LABEL_RE = re.compile(r"[A-Za-z0-9 \-·一-鿿]{1,40}")   # 一律 fullmatch（`$` 會放行結尾換行）
_CRED_SHAPE = re.compile(r"[^\s/@:]+:[^\s/@]+@")
_STATUS_CLASS = {403: "forbidden_403", 429: "rate_limited_429", 407: "proxy_auth_407"}


def _reject_leaky(name: str, value: str) -> None:
    """含網址分隔、憑證形或 `@` 的字串一律拒絕。訊息只寫欄位名，**不寫欄位值**（避免二次外洩）。"""
    if "://" in value or "@" in value or _CRED_SHAPE.search(value):
        raise ValueError(f"{name} 含網址或憑證形字串，已拒絕")


def _opt_bool(name: str, value: object) -> Optional[bool]:
    if value is not None and not isinstance(value, bool):
        raise TypeError(f"{name} 必須是 bool 或 None")
    return value


def _validate_label(value: object) -> None:
    if not isinstance(value, str):
        raise TypeError("target_label 必須是字串")
    _reject_leaky("target_label", value)
    if not _LABEL_RE.fullmatch(value):
        raise ValueError("target_label 不在白名單字元內（只准標籤，不准網址）")


def _validate_status(value: object) -> None:
    if value is not None and (isinstance(value, bool) or not isinstance(value, int) or not 100 <= value <= 599):
        raise ValueError("target_http_status 必須是 100～599 的整數或 None")


def _validate_latency(value: object) -> None:
    if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
        raise ValueError("latency_ms 必須是非負整數或 None（缺值不是 0）")


def _validate_checked_at(value: object) -> None:
    if value is None:
        return
    if not isinstance(value, str):
        raise TypeError("checked_at 必須是字串或 None")
    _reject_leaky("checked_at", value)
    parse_checked_at(value)


def _opt_in(name: str, value: object, allowed: Tuple[str, ...]) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str) or value not in allowed:
        raise ValueError(f"{name} 不在允許的列舉內")
    return value


def parse_checked_at(value: str) -> datetime:
    """ISO 時間（必須含時區）→ datetime；格式不符 ValueError（訊息不含值）。"""
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError("checked_at 必須是 ISO 時間") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("checked_at 必須含時區")
    return parsed


def checked_at_display(value: str) -> str:
    """ISO 時間 → `YYYY-MM-DD HH:MM（UTC±hh:mm）`；不轉換時區，原樣呈現觀測當地時間與偏移。"""
    parsed = parse_checked_at(value)
    offset = parsed.strftime("%z")
    return f"{parsed.strftime('%Y-%m-%d %H:%M')} UTC{offset[:3]}:{offset[3:]}"


@dataclass(frozen=True)
class NasDiagObservation:
    """離線注入的「已觀測事實」。沒有任何原始例外字串欄位。"""

    target_label: str   # 必填：不得預設成特定網站
    proxy_configured: Optional[bool] = None
    nas_reachable: Optional[bool] = None
    route_used: Optional[str] = None
    target_http_status: Optional[int] = None
    error_class: Optional[str] = None
    latency_ms: Optional[int] = None
    checked_at: Optional[str] = None
    nas_error_class: Optional[str] = None

    def __post_init__(self) -> None:
        _opt_bool("proxy_configured", self.proxy_configured)
        _opt_bool("nas_reachable", self.nas_reachable)
        _opt_in("route_used", self.route_used, ROUTES)
        _opt_in("error_class", self.error_class, ERROR_CLASSES)
        _opt_in("nas_error_class", self.nas_error_class, ERROR_CLASSES)
        _validate_label(self.target_label)
        _validate_status(self.target_http_status)
        _validate_latency(self.latency_ms)
        _validate_checked_at(self.checked_at)


@dataclass(frozen=True)
class NasDiagView:
    """`classify()` 的輸出：整體狀態＋兩條軸（NAS 中繼健康度／目標網站可用性）分開。只含可上畫面的事實，不含任何例外文字。"""

    state: str
    route_code: str
    reason_key: str
    nas_health: str
    target_health: str
    nas_cause_key: Optional[str]
    target_cause_key: Optional[str]
    target_label: str
    target_http_status: Optional[int]
    latency_ms: Optional[int]
    checked_at: Optional[str]
    config_state: str = CONFIG_UNKNOWN                      # NAS 設定狀態（與本次檢查結果分開呈現）
    unattributed_cause_key: Optional[str] = None            # 無法歸屬 NAS 側或目標側的失敗分類（只在 no_side_evidence 用）

    def __post_init__(self) -> None:
        if self.config_state not in CONFIG_STATES:
            raise ValueError("config_state 不在允許的列舉內")
        if self.unattributed_cause_key is not None and (self.unattributed_cause_key not in CAUSE_KEYS
                                                        or self.reason_key != "no_side_evidence"):
            raise ValueError("unattributed_cause_key 只能搭配 no_side_evidence 且須在允許的列舉內")
        if self.reason_key == "no_side_evidence" and (self.state != STATE_UNDETERMINED or self.nas_health != HEALTH_UNDETERMINED
                                                      or self.target_health != HEALTH_UNDETERMINED):
            raise ValueError("no_side_evidence 要求兩軸皆無法判定")
        if self.state not in STATES:
            raise ValueError("state 不在六態內")
        if self.route_code not in ROUTE_CODES:
            raise ValueError("route_code 不在允許的列舉內")
        if self.reason_key not in REASON_KEYS:
            raise ValueError("reason_key 不在允許的列舉內")
        if self.nas_health not in NAS_HEALTHS or self.target_health not in TARGET_HEALTHS:
            raise ValueError("健康度不在允許的列舉內")
        _validate_label(self.target_label)
        _validate_status(self.target_http_status)
        _validate_latency(self.latency_ms)
        _validate_checked_at(self.checked_at)
        for name in ("nas_cause_key", "target_cause_key"):
            value = getattr(self, name)
            if value is not None and value not in CAUSE_KEYS:
                raise ValueError(f"{name} 不在允許的列舉內")
        # 結構不變量：連線成功＝兩軸皆 ok；已降級直連＝NAS 軸必為失敗（NAS 並未正常）、目標軸必為 ok。
        if self.state == STATE_OK and (self.nas_health != HEALTH_OK or self.target_health != HEALTH_OK):
            raise ValueError("連線成功要求兩軸皆正常")
        if self.state == STATE_DEGRADED and (self.nas_health != HEALTH_FAILED or self.target_health != HEALTH_OK):
            raise ValueError("已降級直連要求 NAS 軸失敗、目標軸正常（NAS 失敗不得算成功）")
        if self.state == STATE_OK and self.route_code != ROUTE_NAS:
            raise ValueError("連線成功只能是經由 NAS 的路徑")


class _Contradiction(Exception):
    """內部用：輸入互相矛盾或不完整。只帶 reason_key，不帶任何輸入值。"""

    def __init__(self, reason_key: str) -> None:
        super().__init__(reason_key)
        self.reason_key = reason_key


def _is_2xx(status: Optional[int]) -> bool:
    return status is not None and 200 <= status <= 299


def _check_status_vs_class(status: Optional[int], error_class: Optional[str]) -> None:
    """狀態碼與分類必須一致；沒有 HTTP 回應的分類不得帶狀態碼。"""
    if error_class is None:
        return
    if error_class in NO_HTTP_STATUS_CLASSES and status is not None:
        raise _Contradiction("contradiction")
    if error_class == "ok" and status is not None and not _is_2xx(status):
        raise _Contradiction("contradiction")
    if status is not None and error_class != "ok":
        expected = _STATUS_CLASS.get(status)
        if status in _STATUS_CLASS and error_class != expected:
            raise _Contradiction("contradiction")
        if status not in _STATUS_CLASS and (error_class != "other" or _is_2xx(status)):
            raise _Contradiction("contradiction")
    if status is not None and error_class == "ok" and not _is_2xx(status):
        raise _Contradiction("contradiction")


def _target_axis(error_class: Optional[str], status: Optional[int]) -> Tuple[str, Optional[str]]:
    """最終目標結果 → (目標軸, 原因鍵)。ok 必須有 2xx 狀態碼（缺值不算成功）。"""
    if error_class is None:
        raise _Contradiction("incomplete")
    _check_status_vs_class(status, error_class)
    if error_class == "ok":
        if not _is_2xx(status):
            raise _Contradiction("incomplete")
        return HEALTH_OK, None
    return HEALTH_FAILED, CAUSE_OF_CLASS[error_class]


def _config_of(obs: NasDiagObservation) -> str:
    if obs.proxy_configured is None:
        return CONFIG_UNKNOWN
    return CONFIG_SET if obs.proxy_configured else CONFIG_NOT_SET


def _make(obs: NasDiagObservation, state: str, route_code: str, reason: str, nas: str, target: str,
          nas_cause: Optional[str] = None, target_cause: Optional[str] = None) -> NasDiagView:
    return NasDiagView(state=state, route_code=route_code, reason_key=reason, nas_health=nas, target_health=target,
                       nas_cause_key=nas_cause, target_cause_key=target_cause, target_label=obs.target_label,
                       target_http_status=obs.target_http_status, latency_ms=obs.latency_ms, checked_at=obs.checked_at,
                       config_state=_config_of(obs))


def _no_side_evidence(obs: NasDiagObservation) -> NasDiagView:
    """route=nas 的逾時／名稱解析／TLS：兩軸都不下結論；保留路徑、延遲與檢查時間（這些是事實），失敗分類不歸給任何一側。"""
    return NasDiagView(state=STATE_UNDETERMINED, route_code=ROUTE_NAS, reason_key="no_side_evidence", nas_health=HEALTH_UNDETERMINED,
                       target_health=HEALTH_UNDETERMINED, nas_cause_key=None, target_cause_key=None, target_label=obs.target_label,
                       target_http_status=None, latency_ms=obs.latency_ms, checked_at=obs.checked_at, config_state=_config_of(obs),
                       unattributed_cause_key=CAUSE_OF_CLASS[obs.error_class])


def _undetermined(obs: NasDiagObservation, reason: str) -> NasDiagView:
    """無法判定：兩軸都不下結論；不帶 route／原因分類／狀態碼／延遲（避免把矛盾或不完整的事實當證據）。"""
    return NasDiagView(state=STATE_UNDETERMINED, route_code=ROUTE_UNKNOWN, reason_key=reason, nas_health=HEALTH_UNDETERMINED,
                       target_health=HEALTH_UNDETERMINED, nas_cause_key=None, target_cause_key=None, target_label=obs.target_label,
                       target_http_status=None, latency_ms=None, checked_at=obs.checked_at, config_state=_config_of(obs))


def _no_result_facts(obs: NasDiagObservation) -> bool:
    return (obs.nas_reachable is None and obs.route_used in (None, "none") and obs.target_http_status is None
            and obs.error_class is None and obs.latency_ms is None and obs.nas_error_class is None)


def _classify_unconfigured(obs: NasDiagObservation) -> NasDiagView:
    if obs.nas_reachable is not None or obs.nas_error_class is not None or obs.route_used in ("nas", "fallback_direct"):
        raise _Contradiction("contradiction")   # 沒設定 NAS，卻聲稱經過／測過 NAS
    if obs.error_class in NAS_FAULT_CLASSES:
        raise _Contradiction("contradiction")   # 沒設定 NAS，卻回報 NAS 自身故障
    if obs.route_used == "direct" and obs.checked_at is not None and obs.error_class is not None:
        target, cause = _target_axis(obs.error_class, obs.target_http_status)
        return _make(obs, STATE_NOT_CONFIGURED, ROUTE_DIRECT, "not_configured", HEALTH_NOT_CONFIGURED, target, None, cause)
    if obs.target_http_status is not None or obs.error_class is not None or obs.latency_ms is not None or obs.route_used == "direct":
        raise _Contradiction("incomplete")      # 有結果碎片卻湊不出完整的直連結果
    return _make(obs, STATE_NOT_CONFIGURED, ROUTE_UNTESTED, "not_configured", HEALTH_NOT_CONFIGURED, HEALTH_NOT_TESTED)


def _classify_configured(obs: NasDiagObservation) -> NasDiagView:
    if obs.checked_at is None:
        if _no_result_facts(obs):
            return _make(obs, STATE_NOT_TESTED, ROUTE_UNTESTED, "not_tested", HEALTH_NOT_TESTED, HEALTH_NOT_TESTED)
        raise _Contradiction("no_timestamp")    # 有結果卻沒有時間：不知道是哪一次的證據
    route = obs.route_used
    if route == "direct":   # 已設定但這次走直連：NAS 沒被使用，不得對 NAS 下結論（要先於「缺值」檢查，否則永遠走不到）
        if obs.nas_reachable is not None or obs.nas_error_class is not None or obs.error_class in NAS_FAULT_CLASSES:
            raise _Contradiction("contradiction")
        if obs.error_class is None:
            raise _Contradiction("incomplete")
        _check_status_vs_class(obs.target_http_status, obs.error_class)
        raise _Contradiction("nas_not_evaluated")
    if route is None or obs.nas_reachable is None or obs.error_class is None:
        raise _Contradiction("incomplete")
    _check_status_vs_class(obs.target_http_status, obs.error_class)
    if route == "nas":
        if obs.nas_reachable is not True or obs.nas_error_class is not None or obs.error_class in NAS_FAULT_CLASSES:
            raise _Contradiction("contradiction")
        if obs.error_class in SIDE_AMBIGUOUS_CLASSES:
            return _no_side_evidence(obs)       # 沒有證據區分 NAS 側或目標側：兩軸皆不下結論
        target, cause = _target_axis(obs.error_class, obs.target_http_status)
        if target == HEALTH_OK:
            return _make(obs, STATE_OK, ROUTE_NAS, "ok", HEALTH_OK, HEALTH_OK)
        return _make(obs, STATE_FAILED, ROUTE_NAS, "target_failed", HEALTH_OK, HEALTH_FAILED, None, cause)
    nas_cls = obs.nas_error_class
    if nas_cls is None or nas_cls == "ok":
        raise _Contradiction("incomplete" if nas_cls is None else "contradiction")
    if nas_cls in NAS_FAULT_CLASSES and obs.nas_reachable is not False:
        raise _Contradiction("contradiction")   # NAS 自身故障（驗證失敗／無法連線）卻說 NAS 可用
    nas_cause = CAUSE_OF_CLASS[nas_cls]
    if route == "fallback_direct":
        if obs.nas_reachable is not False or obs.error_class in NAS_FAULT_CLASSES:
            raise _Contradiction("contradiction")  # 直連結果不可能是 NAS 自身故障
        target, cause = _target_axis(obs.error_class, obs.target_http_status)
        if target == HEALTH_OK:
            return _make(obs, STATE_DEGRADED, ROUTE_FALLBACK, "degraded", HEALTH_FAILED, HEALTH_OK, nas_cause, None)
        return _make(obs, STATE_FAILED, ROUTE_FALLBACK, "both_failed", HEALTH_FAILED, HEALTH_FAILED, nas_cause, cause)
    # route == "none"：沒有任何路徑取得目標結果；NAS 必為不可用
    if obs.nas_reachable is not False or obs.error_class == "ok":
        raise _Contradiction("contradiction")
    if obs.error_class in NAS_FAULT_CLASSES and nas_cls in NAS_FAULT_CLASSES and obs.error_class != nas_cls:
        raise _Contradiction("contradiction")   # 兩個都是 NAS 自身故障卻不相同（例：407 vs 無法連線）：同一段不可能同時是兩種故障
    if obs.error_class in NAS_FAULT_CLASSES:
        return _make(obs, STATE_FAILED, ROUTE_NONE, "nas_failed", HEALTH_FAILED, HEALTH_NOT_TESTED, nas_cause, None)
    return _make(obs, STATE_FAILED, ROUTE_NONE, "both_failed", HEALTH_FAILED, HEALTH_FAILED, nas_cause, CAUSE_OF_CLASS[obs.error_class])


def classify(obs: NasDiagObservation) -> NasDiagView:
    """已觀測事實 → 六態＋兩軸。純函式；任何矛盾或不完整都回「無法判定」，不猜、不補值。"""
    if not isinstance(obs, NasDiagObservation):
        raise TypeError("obs 必須是 NasDiagObservation")
    try:
        if obs.proxy_configured is None:
            return _undetermined(obs, "config_unknown")
        if obs.proxy_configured is False:
            return _classify_unconfigured(obs)
        return _classify_configured(obs)
    except _Contradiction as exc:
        return _undetermined(obs, exc.reason_key)
