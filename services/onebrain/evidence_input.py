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


def effective_right(grant: object, axis: str, *, test_mode: object = False) -> RightState:
    """把宣告折算成有效權利值（fail-closed：任何不確定、畸形或讀取例外都折成 UNKNOWN，不丟例外）。"""
    try:
        return _effective_right(grant, axis, test_mode)
    except Exception:  # noqa: BLE001 — 權利檢查中的任何例外（含容器 __contains__／__iter__）一律 UNKNOWN
        return RightState.UNKNOWN


def _effective_right(grant: object, axis: str, test_mode: object) -> RightState:
    if not isinstance(grant, RightGrant):
        return RightState.UNKNOWN
    raw = grant.state.strip().upper() if isinstance(grant.state, str) else ""
    if raw in ("DENY", "DENY-SIGNAL"):  # 舊詞 DENY-SIGNAL 正規化為 DENY（不是授權）
        return RightState.DENY
    if raw != "ALLOWED":
        return RightState.UNKNOWN
    if not (isinstance(grant.basis_ref, str) and grant.basis_ref.strip()):
        return RightState.UNKNOWN
    scope = grant.scope
    # scope 必須是 tuple／list／set／frozenset 確切型別（不是 str：避免 "R2R3R4" 子字串誤判）；
    # **完整校驗**：逐一走訪成純 tuple，每個元素都必須是 str（["R4", None] 不得獲准）；
    # 之後只對這個純 tuple 做成員判斷，**不呼叫容器自己的 __contains__**（子類可說謊或拋例外）。
    # 只認內建確切型別（不收子類：子類可覆寫 __contains__／__iter__ 說謊或拋例外 → fail-closed）
    if type(scope) not in (tuple, list, set, frozenset):
        return RightState.UNKNOWN
    elems = tuple(scope)
    # 元素也限確切內建 str（`type(x) is str`）：str 子類可覆寫 __eq__ 冒充任何軸，比較前先拒絕
    if not all(type(x) is str for x in elems) or type(axis) is not str or axis not in elems:
        return RightState.UNKNOWN
    if grant.expired is not False or grant.revoked is not False or grant.inferred is not False:
        return RightState.UNKNOWN
    # 合成 ALLOWED 只在「明示布林 True」的測試模式有效；"false"／1／None／物件等非布林值一律不放行
    if grant.synthetic is not False and test_mode is not True:
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


@dataclass(frozen=True, slots=True)
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
        # 驗證時只迭代一次並固定成不可變 tuple：之後即使原 list 被改動或迭代會拋錯，路由用主題也不再變
        frozen = tuple(self.lens)
        if not frozen:
            raise ValueError("lens 不可為空")
        for lens in frozen:
            if type(lens) is not str or lens not in LENSES:
                raise ValueError("未知主題")
        object.__setattr__(self, "lens", frozen)
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
    lens: tuple = ()  # 路由用主題（建構時已驗證的卡屬性，非證據內容）；供短解釋保留各主題的固定拒收缺口


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
    """證據結構是否自相矛盾或畸形（fail-closed：任何無法確認的結構都視為矛盾；不丟例外、不夾帶內容）。"""
    try:
        seqs = (card.support_refs, card.contradicting_evidence_refs, card.rejected_metrics, card.data_gaps)
        if not all(isinstance(x, (tuple, list)) for x in seqs):
            return True
        rejected_names = set()
        for r in card.rejected_metrics:
            if not isinstance(r, Mapping):
                return True
            name = r.get("metric")
            if not isinstance(name, str):
                return True
            rejected_names.add(name)
        for ref in tuple(card.support_refs) + tuple(card.contradicting_evidence_refs):
            if not isinstance(ref, Mapping):
                return True
            if _FORBIDDEN_EVIDENCE_KEYS & set(ref.keys()):
                return True
            metric = ref.get("metric")
            if metric is not None and not isinstance(metric, str):
                return True
            if isinstance(metric, str) and metric in rejected_names:
                return True
        return False
    except Exception:  # noqa: BLE001 — 無法確認即視為矛盾
        return True


def _card_right_states(card: AdmittedCard, test_mode: object) -> list:
    """逐軸折算權利；任何讀取例外（含 rights 對映的 get）→ 該卡三軸全 UNKNOWN（RJ3），不中斷批次。"""
    try:
        rights = card.rights if isinstance(card.rights, Mapping) else {}
        return [(axis, effective_right(rights.get(axis), axis, test_mode=test_mode)) for axis in RIGHT_AXES]
    except Exception:  # noqa: BLE001
        return [(axis, RightState.UNKNOWN) for axis in RIGHT_AXES]


def _routing_lens(card: AdmittedCard) -> tuple:
    """路由主題：直接從**基底類別**的 slot 描述器取建構時 `__post_init__` 已驗證寫入的不可變 tuple。

    `AdmittedCard` 為 `slots=True`：值存在 slot，不在實例 `__dict__`；此處以 `AdmittedCard.lens.__get__(card)`
    顯式走基底描述器，**不經** `card.lens`／子類覆寫的 `__getattribute__`／同名 property／子類 `__dict__` 描述器，
    子類無法在建構後讓此處回傳另一個合法主題。任何異常或型別不符 → ()（單卡隔離，不中斷批次）。
    （刻意不防禦惡意同程序反射，如以 `object.__setattr__` 繞過 frozen 直接改 slot——不在威脅邊界內。）
    """
    try:
        lens = AdmittedCard.lens.__get__(card)
        if type(lens) is tuple and lens and all(type(x) is str and x in LENSES for x in lens):
            return lens
    except Exception:  # noqa: BLE001
        pass
    return ()


def admit(cards: Sequence[AdmittedCard], *, test_mode: bool = False) -> EvidenceBundle:
    """逐筆准入。R2／R3／R4 任一非 `ALLOWED`，或輸入自相矛盾 → 拒收（不丟例外、不洩漏內容）。"""
    approved, refused = [], []
    for card in cards:
        if not isinstance(card, AdmittedCard):
            raise TypeError("cards 的每個元素必須是 AdmittedCard")
        states = _card_right_states(card, test_mode)
        fixed_lens = _routing_lens(card)
        reasons = []
        gaps = []
        if any(s is not RightState.ALLOWED for _, s in states):
            # 權利不合：只回固定 RJ3；**不檢視證據內容**（不論其結構是否畸形，不外洩、不拋例外）
            reasons.append(REASON_RJ3)
            gaps.append("rights_unverified")
        elif _inconsistent(card):
            reasons.append(REASON_INCONSISTENT)
            gaps.append("input_inconsistent")
        if reasons:
            refused.append(
                RefusedEvidence(
                    card_id=card.card_id,
                    reason_codes=tuple(reasons),
                    rights_detail=tuple((a, s.value) for a, s in states),
                    data_gaps=tuple(gaps),
                    lens=fixed_lens,
                )
            )
            continue
        try:
            if not fixed_lens:
                raise ValueError("lens 無法固定")  # 無固定主題者不得獲准（落入下方固定 input_inconsistent 拒收）
            boundary = _snapshot(card.credibility_boundary) if isinstance(card.credibility_boundary, Mapping) else {}
            item = ApprovedEvidence(
                card_id=card.card_id,
                lens=fixed_lens,
                support_refs=_snapshot(card.support_refs),
                contradicting_evidence_refs=_snapshot(card.contradicting_evidence_refs),
                contradiction_search=card.contradiction_search,
                rejected_metrics=_snapshot(card.rejected_metrics),
                data_gaps=tuple(str(g) for g in card.data_gaps),
                credibility_boundary=boundary,
                card_status=card.card_status,
            )
        except Exception:  # noqa: BLE001 — 快照失敗：按卡回固定 input_inconsistent；不夾帶例外訊息／內容、不中斷其他卡
            refused.append(
                RefusedEvidence(
                    card_id=card.card_id,
                    reason_codes=(REASON_INCONSISTENT,),
                    rights_detail=tuple((a, s.value) for a, s in states),
                    data_gaps=("input_inconsistent",),
                    lens=fixed_lens,
                )
            )
            continue
        approved.append(item)
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


# ═════════════ 三主題短解釋（確定性骨架；AI 文字只是附帶欄位） ═════════════
# 「結論」只由獲准證據的**狀態**決定（固定句型），不是投資判斷、不是風險等級、不由 AI 產生。
CONCLUSION_INSUFFICIENT = "證據不足：本主題沒有任何獲准的支持證據。"
CONCLUSION_PARTIAL = "僅陳述證據狀態：已有獲准支持證據，另見反證與資料缺口；不構成投資判斷或行動建議。"
CONTRADICTION_TEXT = {
    "found": "有反面證據",
    "not_found_in_window": "未找到反面證據（不等於無反證）",
    "not_evaluable": "反證無法評估",
    "not_searched": "未搜尋反證",
}
# AI 附帶文字若含下列詞彙（行動／評等／無異常類），整段捨棄；AI 不得改寫結論或風控決策
_AI_TEXT_FORBIDDEN = ("買進", "賣出", "加碼", "減碼", "持有", "停損", "建議", "無異常", "低風險", "高風險",
                      "安全", "正常", "保證", "必漲", "必跌", "預測")


@dataclass(frozen=True)
class LensBrief:
    """某主題的短解釋：結論（確定性）＋證據＋反證＋缺口＋可信邊界；AI 文字另列、可為空。"""

    lens: str
    conclusion: str
    evidence: tuple
    counter_evidence: tuple
    contradiction_states: tuple
    contradiction_summary: tuple
    data_gaps: tuple
    credibility_boundary: dict
    ai_status: str
    ai_text: str = ""
    ai_is_fake: bool = False


def _boundary_summary(view: tuple) -> dict:
    """可信邊界彙總：只彙總不改寫；`not_forecast` 恆為 True，不可被輸入覆寫。"""
    windows = []
    n_sources = 0
    for a in view:
        b = a.credibility_boundary if isinstance(a.credibility_boundary, dict) else {}
        w = b.get("window_hours")
        if type(w) is int:
            windows.append(w)
        ns = b.get("n_sources")
        if type(ns) is int:
            n_sources += ns
    return {"n_cards": len(view), "n_sources": n_sources,
            "window_hours": (min(windows) if windows else None), "not_forecast": True}


def _clean_ai_text(text: str) -> str:
    return "" if any(w in text for w in _AI_TEXT_FORBIDDEN) else text


def brief_for_lens(bundle: EvidenceBundle, lens: str, provider: Optional[AnalysisProvider] = None, *,
                   enabled: bool = False, **explain_kwargs) -> LensBrief:
    """產出單一主題的短解釋。AI 未啟用／失敗／逾時／例外 → `ai_text=""`，其餘欄位完整、不阻塞。"""
    exp = explain(bundle, lens, provider, enabled=enabled, **explain_kwargs)
    view = exp.evidence
    support = tuple(ref for a in view for ref in a.support_refs)
    counter = tuple(ref for a in view for ref in a.contradicting_evidence_refs)
    states = tuple(a.contradiction_search for a in view)
    summary = tuple(CONTRADICTION_TEXT[s] for s in dict.fromkeys(states))
    gaps = tuple(f"{a.card_id}:{g}" for a in view for g in a.data_gaps)
    # 保留本主題有權取得的固定 reasons-only 拒收缺口（只有固定缺口碼；不讀、不洩露拒收內容，不添 support）
    gaps += tuple(f"{r.card_id}:{g}" for r in bundle.refused if lens in r.lens for g in r.data_gaps)
    text = _clean_ai_text(exp.text) if exp.status is ExplainStatus.OK else ""
    status = "text_rejected" if (exp.status is ExplainStatus.OK and exp.text and not text) else exp.status.value
    return LensBrief(
        lens=lens,
        conclusion=CONCLUSION_PARTIAL if support else CONCLUSION_INSUFFICIENT,
        evidence=support,
        counter_evidence=counter,
        contradiction_states=states,
        contradiction_summary=summary,
        data_gaps=gaps,
        credibility_boundary=_boundary_summary(view),
        ai_status=status,
        ai_text=text,
        ai_is_fake=exp.is_fake if text else False,
    )


def briefs_for_all_lenses(bundle: EvidenceBundle, provider: Optional[AnalysisProvider] = None, *,
                          enabled: bool = False, **explain_kwargs) -> dict:
    """三主題共用同一份 `bundle`；每個主題各自一份短解釋（Provider 至多各呼叫一次）。"""
    return {lens: brief_for_lens(bundle, lens, provider, enabled=enabled, **explain_kwargs) for lens in LENSES}
