# -*- coding: utf-8 -*-
"""NAS 中繼站診斷預覽的**暫行**字樣（只供隔離式離線預覽的 renderer 使用；暫行·未核准）。

- 已核准字樣一律取規則表（`shared/ui_semantics/rules.py`）：
  `not_configured`（「尚未設定」：設定沒設、沒有執行取數）、`undetermined`（「無法判定」）、`missing`（缺值）。
  本檔**不得**複寫它們，也不得進規則表。
- 新狀態詞（尚未測試、連線成功、連線失敗、已降級直連）、兩軸的健康度詞、各失敗分類的人話原因與建議，全是 `PendingWording`
  （status 恆為 pending、帶出處）；畫面上以 `data-pending-wording` 標記並帶虛線底線，客戶定字後才搬進規則表。
- 人話原因要講清楚是 NAS、目標網站或憑證哪一邊的問題與下一步；**不要求**使用者把 NAS 管理介面開放到公網，也不建議關閉憑證驗證。
"""
from __future__ import annotations

from types import MappingProxyType
from typing import Mapping, Tuple

from ui_v3.viewmodels import nas_diag as vm
from ui_v3.viewmodels.preview_wording import STATUS_PENDING, PendingWording

_SRC = "執行組暫擬（NAS 診斷預覽，字樣待客戶裁示）"

# 狀態 → 標籤字樣來源：("rule", 規則鍵) 取已核准字樣；("pending", 本檔鍵) 取暫行字樣。
STATE_LABEL_SOURCE: Mapping[str, Tuple[str, str]] = MappingProxyType({
    vm.STATE_NOT_CONFIGURED: ("rule", "not_configured"),
    vm.STATE_UNDETERMINED: ("rule", "undetermined"),
    vm.STATE_NOT_TESTED: ("pending", "state_not_tested"),
    vm.STATE_OK: ("pending", "state_ok"),
    vm.STATE_FAILED: ("pending", "state_failed"),
    vm.STATE_DEGRADED: ("pending", "state_degraded"),
})

# 路徑 → 字樣來源。
ROUTE_LABEL_SOURCE: Mapping[str, Tuple[str, str]] = MappingProxyType({
    vm.ROUTE_NAS: ("pending", "route_nas"),
    vm.ROUTE_DIRECT: ("pending", "route_direct"),
    vm.ROUTE_FALLBACK: ("pending", "route_fallback_direct"),
    vm.ROUTE_UNTESTED: ("pending", "route_untested"),
    vm.ROUTE_NONE: ("pending", "route_none"),
    vm.ROUTE_UNKNOWN: ("rule", "undetermined"),
})

# 兩軸健康度 → 字樣來源（NAS 軸與目標軸的「正常／可用」用詞不同，所以分開兩張表）。
NAS_HEALTH_SOURCE: Mapping[str, Tuple[str, str]] = MappingProxyType({
    vm.HEALTH_OK: ("pending", "nas_health_ok"),
    vm.HEALTH_FAILED: ("pending", "nas_health_failed"),
    vm.HEALTH_NOT_TESTED: ("pending", "health_not_tested"),
    vm.HEALTH_NOT_CONFIGURED: ("rule", "not_configured"),
    vm.HEALTH_UNDETERMINED: ("rule", "undetermined"),
})
TARGET_HEALTH_SOURCE: Mapping[str, Tuple[str, str]] = MappingProxyType({
    vm.HEALTH_OK: ("pending", "target_health_ok"),
    vm.HEALTH_FAILED: ("pending", "target_health_failed"),
    vm.HEALTH_NOT_TESTED: ("pending", "health_not_tested"),
    vm.HEALTH_UNDETERMINED: ("rule", "undetermined"),
})

# 無法歸屬任何一側的失敗分類 → 人話原因（只在 no_side_evidence 用）。
UNATTRIBUTED_CAUSE_KEY: Mapping[str, str] = MappingProxyType({
    "cause_timeout": "cause_unattr_timeout", "cause_dns": "cause_unattr_dns", "cause_tls": "cause_unattr_tls"})

# 整體結論（一句話）：以 (state, reason_key) 查表。
CONCLUSION_KEY: Mapping[Tuple[str, str], str] = MappingProxyType({
    (vm.STATE_NOT_CONFIGURED, "not_configured"): "concl_not_configured",
    (vm.STATE_NOT_TESTED, "not_tested"): "concl_not_tested",
    (vm.STATE_OK, "ok"): "concl_ok",
    (vm.STATE_DEGRADED, "degraded"): "concl_degraded",
    (vm.STATE_FAILED, "target_failed"): "concl_target_failed",
    (vm.STATE_FAILED, "nas_failed"): "concl_nas_failed",
    (vm.STATE_FAILED, "both_failed"): "concl_both_failed",
    (vm.STATE_UNDETERMINED, "contradiction"): "concl_contradiction",
    (vm.STATE_UNDETERMINED, "incomplete"): "concl_incomplete",
    (vm.STATE_UNDETERMINED, "config_unknown"): "concl_config_unknown",
    (vm.STATE_UNDETERMINED, "no_timestamp"): "concl_no_timestamp",
    (vm.STATE_UNDETERMINED, "nas_not_evaluated"): "concl_nas_not_evaluated",
    (vm.STATE_UNDETERMINED, "no_side_evidence"): "concl_no_side_evidence",
})

_LIST = (
    PendingWording("page_title", "NAS 中繼站診斷", _SRC),
    PendingWording("section_status", "NAS 設定與本次檢查", _SRC),
    PendingWording("pending_notice", "暫行字樣，尚未核准", _SRC),
    PendingWording("offline_note", "本預覽為離線注入結果，沒有執行任何真實請求", _SRC),
    PendingWording("separator", "｜", _SRC),
    # 標籤
    PendingWording("label_route", "實際路徑", _SRC),
    PendingWording("label_target", "目標", _SRC),
    PendingWording("label_nas_card", "NAS 中繼檢查結果", _SRC),
    PendingWording("label_target_card", "目標網站本次回應", _SRC),
    PendingWording("label_status_code", "HTTP 結果", _SRC),
    PendingWording("label_latency", "延遲", _SRC),
    PendingWording("label_checked_at", "最近檢查", _SRC),
    PendingWording("label_result", "本次檢查結果", _SRC),
    PendingWording("label_config", "NAS 設定狀態", _SRC),
    PendingWording("config_set", "已設定", _SRC),
    PendingWording("evidence_summary", "詳細技術證據", _SRC),
    PendingWording("evidence_scope", "以下只代表這一次檢查的觀測，不代表 NAS 或目標網站之後的狀態", _SRC),
    PendingWording("who_unknown", "NAS 或目標網站（無法區分）", _SRC),
    PendingWording("label_next_step", "原因與建議", _SRC),
    PendingWording("unit_ms", "毫秒", _SRC),
    PendingWording("who_nas", "NAS 這一段", _SRC),
    PendingWording("who_target", "目標網站這一段", _SRC),
    # 新狀態詞
    PendingWording("state_not_tested", "◌ 尚未測試", _SRC),
    PendingWording("state_ok", "✓ 本次連線成功", _SRC),
    PendingWording("state_failed", "✕ 本次連線失敗", _SRC),
    PendingWording("state_degraded", "▲ 已降級直連", _SRC),
    # 路徑
    PendingWording("route_nas", "NAS 中繼", _SRC),
    PendingWording("route_direct", "直連", _SRC),
    PendingWording("route_fallback_direct", "降級直連", _SRC),
    PendingWording("route_untested", "未測試", _SRC),
    PendingWording("route_none", "沒有可用路徑", _SRC),
    # 兩軸健康度
    PendingWording("nas_health_ok", "本次檢查正常", _SRC),
    PendingWording("nas_health_failed", "異常，並未正常", _SRC),
    PendingWording("target_health_ok", "本次取得正常回應", _SRC),
    PendingWording("target_health_failed", "無法取得", _SRC),
    PendingWording("health_not_tested", "◌ 尚未測試", _SRC),
    # 一句話結論
    PendingWording("concl_not_configured", "尚未設定 NAS 中繼站，來源請求會改走直連（雲端出口可能被來源封鎖）；這不是故障", _SRC),
    PendingWording("concl_not_tested", "已設定 NAS 中繼站，但還沒有檢查過；目前沒有任何成功或失敗的證據", _SRC),
    PendingWording("concl_ok", "本次檢查中，經由 NAS 取得了目標網站的正常回應；這只代表這一次，不代表 NAS 之後都正常", _SRC),
    PendingWording("concl_degraded", "NAS 失敗，改走直連；NAS 並未正常", _SRC),
    PendingWording("concl_target_failed", "本次檢查中 NAS 中繼站有回應，但目標網站沒有取得正常回應", _SRC),
    PendingWording("concl_nas_failed", "本次檢查中 NAS 中繼站無法使用，尚未取得目標網站的結果", _SRC),
    PendingWording("concl_both_failed", "NAS 與直連都沒有取得目標網站的正常回應", _SRC),
    PendingWording("concl_contradiction", "收到互相矛盾的檢查結果，無法判定（不猜測）", _SRC),
    PendingWording("concl_incomplete", "檢查結果不完整，缺少判定所需的事實，無法判定", _SRC),
    PendingWording("concl_config_unknown", "不知道是否已設定 NAS 中繼站，無法判定", _SRC),
    PendingWording("concl_no_timestamp", "檢查結果沒有檢查時間，不知道是哪一次的證據，無法判定", _SRC),
    PendingWording("concl_no_side_evidence", "本次有經過 NAS 但沒有取得回應，缺少區分 NAS 這一段或目標網站這一段的證據，兩邊都無法判定", _SRC),
    PendingWording("concl_nas_not_evaluated", "這次檢查沒有經過 NAS，無法判定 NAS 的狀態", _SRC),
    # 各失敗分類的人話原因與建議（說明是哪一邊的問題）
    PendingWording("cause_auth_407", "代理驗證失敗（407）：NAS 中繼站拒絕了這次請求的驗證。請確認代理的帳號設定兩端一致；不需要把 NAS 管理介面開放到公網。", _SRC),
    PendingWording("cause_blocked_403", "被來源封鎖（403）：目標網站拒絕了 NAS 出口的請求（NAS 出口被目標網站封鎖），問題在目標網站端，不是 NAS 斷線。請稍後再試，或確認是否換個出口可取得。", _SRC),
    PendingWording("cause_rate_limited_429", "請求過多（429）：目標網站要求放慢速度。請稍後再試，不要連續重試。", _SRC),
    PendingWording("cause_timeout", "逾時：在時限內沒有收到回應，歸屬哪一段由前面的標籤依證據標示（直連失敗歸目標網站這一段）。請稍後再試。", _SRC),
    PendingWording("cause_dns", "名稱解析失敗：找不到位址。歸屬哪一段由前面的標籤依證據標示（直連失敗歸目標網站這一段）。請確認網路與名稱解析是否正常。", _SRC),
    PendingWording("cause_tls", "憑證或安全連線握手有問題：安全連線無法建立。請檢查憑證是否過期或被中間設備替換；不要為了通過而關閉憑證驗證。", _SRC),
    PendingWording("cause_nas_unreachable", "NAS 無法連線：連不到中繼站。請確認 NAS 是否開機、網路與連接埠設定；不需要把 NAS 管理介面開放到公網。", _SRC),
    # route=nas 的逾時／名稱解析／TLS：缺少區分兩側的證據，文字不歸給任何一側
    PendingWording("cause_unattr_timeout", "逾時：在時限內沒有收到回應。缺少證據區分是 NAS 這一段或目標網站這一段較慢，兩邊都無法判定。請稍後再試。", _SRC),
    PendingWording("cause_unattr_dns", "名稱解析失敗：缺少證據區分是 NAS 這一段或目標網站這一段的問題，兩邊都無法判定。請確認網路與名稱解析是否正常。", _SRC),
    PendingWording("cause_unattr_tls", "憑證或安全連線握手有問題：缺少證據區分是 NAS 這一段或目標網站這一段，兩邊都無法判定。請檢查憑證是否過期或被中間設備替換；不要為了通過而關閉憑證驗證。", _SRC),
    PendingWording("cause_other", "其他錯誤：對方回應了非預期的結果。請稍後再試。", _SRC),
)


def _index(items: Tuple[PendingWording, ...]) -> Mapping[str, PendingWording]:
    table = {w.key: w for w in items}
    if len(table) != len(items):
        raise ValueError("NAS_DIAG_WORDING 有重複鍵")
    for w in items:
        if w.status != STATUS_PENDING:
            raise ValueError(f"{w.key}: 暫行字樣的 status 只能是 pending")
    return MappingProxyType(table)


NAS_DIAG_WORDING: Mapping[str, PendingWording] = _index(_LIST)


def nas_diag_wording(key: str) -> PendingWording:
    """查暫行字樣；未知鍵 KeyError（不猜）。"""
    return NAS_DIAG_WORDING[key]
