"""OB 離線證據輸入器（C-OB-EVIDENCE-OFFLINE-1）：獨立純函式，不接任何 UI／Provider／Runtime。

授權：GPT 總管 #1296 comment 7132782309（限定離線切片；不核准 Digest schema／Runtime；D2-G2 未宣稱通過）。
本模組**只做三件事**：
1. `admit()`：接收「既有已驗收准入結果」（`support_refs`／`contradicting_evidence_refs`／
   `rejected_metrics`／`data_gaps`／可信邊界＋三條權利軸），**R2／R3／R4 任一軸非 `ALLOWED`
   或輸入自相矛盾即整筆拒收**（`RJ3:rights_unverified`／`input_inconsistent`），被拒內容**不進入**輸出；
   獲准者**原樣**保留支持證據、反證、資料缺口、可信邊界。三主題（風險防禦／現金流／趨勢觀察）
   **共用同一份獲准證據**，只是不同視圖。
2. `EvidenceBundle.by_lens()`：同一獲准集合的主題視圖（不複製、不改寫）。
3. `explain()`：把「某主題視圖」交給**呼叫端注入**的 `AnalysisProvider`（預設不啟用）。
   AI 停用／無證據／逾時／錯誤／例外 一律回結構化結果、**不 raise**，且**證據欄位與規則數值逐位不變**——
   UI 永遠可以只顯示 `result.evidence`，不依賴 AI 文字。

⛔ 不重算、不改寫任何正式投資規則；沒有 Digest schema；沒有風險等級／行動／預測；
沒有網路、檔案、時鐘、環境變數（受 `tests/test_onebrain_offline_guard.py` 的 AST 白名單約束）。
缺值不補 0；沒有任何「正常」「無異常」狀態值：證據不足時 `status` 只會是 `insufficient`。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Optional, Sequence

from services.onebrain.provider_interface import AnalysisProvider
from services.onebrain.provider_types import ProviderOutcome, ProviderRequest

LENS_RISK = "risk_defense"
LENS_CASHFLOW = "cashflow"
LENS_TREND = "trend_watch"
LENSES = (LENS_RISK, LENS_CASHFLOW, LENS_TREND)

RIGHT_AXES = ("R2", "R3", "R4")  # 進 OneBrain＝R2（顯示）∧R3（衍生）∧R4（AI 使用）
REASON_RJ3 = "RJ3:rights_unverified"
REASON_INCONSISTENT = "input_inconsistent"

CONTRADICTION_STATES = ("found", "not_found_in_window", "not_evaluable", "not_searched")
CARD_STATUSES = ("partial", "insufficient")
# 證據項裡不得出現的欄位（避免把結論／行動／評等夾帶進「證據」）
_FORBIDDEN_EVIDENCE_KEYS = frozenset(
    {"risk_level", "risk_cap", "action", "recommendation", "score", "rating", "verdict"}
)


class RightState(Enum):
    """權利值只有三種；`archived`／`DENY-SIGNAL`／`UNVERIFIED` 都不是授權值。"""

    ALLOWED = "ALLOWED"
    UNKNOWN = "UNKNOWN"
    DENY = "DENY"


@dataclass(frozen=True)
class RightGrant:
    """單一權利軸的宣告。`ALLOWED` 成立需：有依據引用、範圍涵蓋該軸、未過期未撤銷、非推論。"""

    state: str = "UNKNOWN"
    basis_ref: str = ""
    scope: tuple = ()
    synthetic: bool = False
    expired: bool = False
    revoked: bool = False
    inferred: bool = False


def effective_right(grant: object, axis: str, *, test_mode: bool = False) -> RightState:
    """把宣告折算成有效權利值（fail-closed：任何不確定都是 UNKNOWN）。"""
    if not isinstance(grant, RightGrant):
        return RightState.UNKNOWN
    raw = grant.state.strip().upper() if isinstance(grant.state, str) else ""
    if raw in ("DENY", "DENY-SIGNAL"):  # 舊詞 DENY-SIGNAL 正規化為 DENY（不是授權）
        return RightState.DENY
    if raw != "ALLOWED":
        return RightState.UNKNOWN
    if not (isinstance(grant.basis_ref, str) and grant.basis_ref.strip()):
        return RightState.UNKNOWN
    if axis not in tuple(grant.scope):
        return RightState.UNKNOWN
    if grant.expired is not False or grant.revoked is not False or grant.inferred is not False:
        return RightState.UNKNOWN
    if grant.synthetic is not False and not test_mode:  # 合成 ALLOWED 只在測試模式有效
        return RightState.UNKNOWN
    return RightState.ALLOWED


def _snapshot(obj: object) -> object:
    """深拷貝成純 dict／list／tuple／純量（輸出與輸入互不別名）。"""
    if isinstance(obj, Mapping):
        return {str(k): _snapshot(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_snapshot(v) for v in obj]
    if isinstance(obj, tuple):
        return tuple(_snapshot(v) for v in obj)
    return obj


def _ser(obj: object) -> str:
    """決定性序列化（排序鍵），供 provider 輸入文字與測試比對；不改寫任何值。"""
    if isinstance(obj, dict):
        return "{" + ",".join(f"{k}:{_ser(obj[k])}" for k in sorted(obj)) + "}"
    if isinstance(obj, (list, tuple)):
        return "[" + ",".join(_ser(v) for v in obj) + "]"
    return repr(obj)


@dataclass(frozen=True)
class AdmittedCard:
    """既有准入結果（輸入）。`rights` 的鍵為 R2／R3／R4。"""

    card_id: str
    lens: tuple
    support_refs: tuple = ()
    contradicting_evidence_refs: tuple = ()
    contradiction_search: str = "not_searched"
    rejected_metrics: tuple = ()
    data_gaps: tuple = ()
    credibility_boundary: Optional[Mapping] = None
    rights: Optional[Mapping] = None
    card_status: str = "insufficient"

    def __post_init__(self) -> None:
        if not isinstance(self.card_id, str) or not self.card_id.strip():
            raise ValueError("card_id 不可為空")
        if not isinstance(self.lens, (list, tuple)) or not self.lens:
            raise ValueError("lens 不可為空")
        for lens in self.lens:
            if lens not in LENSES:
                raise ValueError("未知主題")
        if self.contradiction_search not in CONTRADICTION_STATES:
            raise ValueError("未知 contradiction_search")
        if self.card_status not in CARD_STATUSES:
            raise ValueError("card_status 只能是 partial／insufficient")


@dataclass(frozen=True)
class ApprovedEvidence:
    """獲准進入 OneBrain 的證據（原樣保留）。"""

    card_id: str
    lens: tuple
    support_refs: tuple
    contradicting_evidence_refs: tuple
    contradiction_search: str
    rejected_metrics: tuple  # 上游已拒指標（只作追溯；不是證據）
    data_gaps: tuple
    credibility_boundary: dict
    card_status: str


@dataclass(frozen=True)
class RefusedEvidence:
    """被拒收者：只留原因碼與權利狀態，**不含任何證據內容**。"""

    card_id: str
    reason_codes: tuple
    rights_detail: tuple  # ((軸, 有效值字串), …)
    data_gaps: tuple


@dataclass(frozen=True)
class EvidenceBundle:
    approved: tuple
    refused: tuple

    @property
    def data_gaps(self) -> tuple:
        """彙總缺口（獲准者的缺口＋被拒者的缺口），以 `card_id:code` 標示來源。"""
        out = []
        for item in self.approved + self.refused:
            for code in item.data_gaps:
                out.append(f"{item.card_id}:{code}")
        return tuple(out)

    @property
    def status(self) -> str:
        """只有 `partial`／`insufficient`；**沒有任何『正常』『無異常』狀態**。"""
        return "partial" if any(a.support_refs for a in self.approved) else "insufficient"

    def by_lens(self, lens: str) -> tuple:
        """同一份獲准集合的主題視圖（回傳同一批物件，不複製、不改寫）。"""
        if lens not in LENSES:
            raise ValueError("未知主題")
        return tuple(a for a in self.approved if lens in a.lens)


def _inconsistent(card: AdmittedCard) -> bool:
    rejected_names = set()
    for r in card.rejected_metrics:
        if isinstance(r, Mapping) and isinstance(r.get("metric"), str):
            rejected_names.add(r["metric"])
    for ref in tuple(card.support_refs) + tuple(card.contradicting_evidence_refs):
        if not isinstance(ref, Mapping):
            return True
        if _FORBIDDEN_EVIDENCE_KEYS & set(ref.keys()):
            return True
        if ref.get("metric") in rejected_names:
            return True
    return False


def admit(cards: Sequence[AdmittedCard], *, test_mode: bool = False) -> EvidenceBundle:
    """逐筆准入。R2／R3／R4 任一非 `ALLOWED`，或輸入自相矛盾 → 拒收（不丟例外、不洩漏內容）。"""
    approved, refused = [], []
    for card in cards:
        if not isinstance(card, AdmittedCard):
            raise TypeError("cards 的每個元素必須是 AdmittedCard")
        rights = card.rights if isinstance(card.rights, Mapping) else {}
        states = [(axis, effective_right(rights.get(axis), axis, test_mode=test_mode)) for axis in RIGHT_AXES]
        reasons = []
        gaps = []
        if any(s is not RightState.ALLOWED for _, s in states):
            reasons.append(REASON_RJ3)
            gaps.append("rights_unverified")
        if _inconsistent(card):
            reasons.append(REASON_INCONSISTENT)
            gaps.append("input_inconsistent")
        if reasons:
            refused.append(
                RefusedEvidence(
                    card_id=card.card_id,
                    reason_codes=tuple(reasons),
                    rights_detail=tuple((a, s.value) for a, s in states),
                    data_gaps=tuple(gaps),
                )
            )
            continue
        boundary = _snapshot(card.credibility_boundary) if isinstance(card.credibility_boundary, Mapping) else {}
        approved.append(
            ApprovedEvidence(
                card_id=card.card_id,
                lens=tuple(card.lens),
                support_refs=_snapshot(card.support_refs),
                contradicting_evidence_refs=_snapshot(card.contradicting_evidence_refs),
                contradiction_search=card.contradiction_search,
                rejected_metrics=_snapshot(card.rejected_metrics),
                data_gaps=tuple(str(g) for g in card.data_gaps),
                credibility_boundary=boundary,
                card_status=card.card_status,
            )
        )
    return EvidenceBundle(approved=tuple(approved), refused=tuple(refused))


class ExplainStatus(Enum):
    DISABLED = "disabled"
    NO_EVIDENCE = "no_evidence"
    OK = "ok"
    FAILED = "failed"  # Provider 回報失敗／降級／逾時
    ERROR = "error"  # Provider 丟例外或回傳非預期型別


@dataclass(frozen=True)
class ExplanationResult:
    """`evidence` 永遠是同一份獲准證據視圖；`text` 只來自 Provider 且與證據分離。"""

    lens: str
    status: ExplainStatus
    evidence: tuple
    text: str = ""
    is_fake: bool = False
    failure_kind: str = ""


def _request_text(view: tuple) -> str:
    return "\n".join(
        _ser(
            {
                "card_id": a.card_id,
                "support_refs": a.support_refs,
                "contradicting_evidence_refs": a.contradicting_evidence_refs,
                "contradiction_search": a.contradiction_search,
                "data_gaps": a.data_gaps,
                "credibility_boundary": a.credibility_boundary,
            }
        )
        for a in view
    )


def explain(
    bundle: EvidenceBundle,
    lens: str,
    provider: Optional[AnalysisProvider] = None,
    *,
    enabled: bool = False,
    request_id: str = "ob-evidence-1",
    model: str = "ob-evidence-offline",
    timeout_seconds: float = 5.0,
) -> ExplanationResult:
    """取得某主題的解釋；任何 AI 問題都**不 raise、不影響 `evidence`**。"""
    if not isinstance(bundle, EvidenceBundle):
        raise TypeError("bundle 必須是 EvidenceBundle")
    view = bundle.by_lens(lens)
    if not enabled or provider is None:
        return ExplanationResult(lens=lens, status=ExplainStatus.DISABLED, evidence=view)
    if not any(a.support_refs for a in view):
        return ExplanationResult(lens=lens, status=ExplainStatus.NO_EVIDENCE, evidence=view)
    try:
        request = ProviderRequest(
            request_id=request_id,
            model=model,
            input_text=_request_text(view),
            timeout_seconds=timeout_seconds,
            max_retries=0,
        )
        outcome = provider.invoke(request)
    except TimeoutError:
        return ExplanationResult(lens=lens, status=ExplainStatus.FAILED, evidence=view, failure_kind="timeout")
    except Exception:  # noqa: BLE001 — Provider 層任何例外都不得阻塞 UI；只回類別，不夾帶訊息
        return ExplanationResult(lens=lens, status=ExplainStatus.ERROR, evidence=view)
    if not isinstance(outcome, ProviderOutcome):
        return ExplanationResult(lens=lens, status=ExplainStatus.ERROR, evidence=view)
    if outcome.failure is not None:
        return ExplanationResult(
            lens=lens,
            status=ExplainStatus.FAILED,
            evidence=view,
            is_fake=outcome.failure.is_fake,
            failure_kind=outcome.failure.kind.value,
        )
    return ExplanationResult(
        lens=lens,
        status=ExplainStatus.OK,
        evidence=view,
        text=outcome.response.text,
        is_fake=outcome.response.is_fake,
    )
