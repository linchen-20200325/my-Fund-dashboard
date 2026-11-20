"""OB-B 離線切片：Provider-neutral 請求／回應／錯誤型別。

只含不可變資料結構與列舉，不含任何行為政策：
- 沒有 token usage、cost、trace、structured-output capability、confidence、
  action、Risk Cap、configuration policy 等欄位（欄位集合由
  `tests/test_onebrain_provider_types.py` 釘死）。
- `timeout_seconds` / `max_retries` 僅為型別欄位；本套件沒有任何逾時或重試實作。
- `model` 僅為識別字串，不含 routing 政策。
- `input_text` 為不透明文字；本套件不定義 prompt 模板，也不假設 Digest 形狀。

建構時就拒絕不合法的值（raise），不做靜默修正（`CLAUDE.md` §1）。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ProviderErrorKind(Enum):
    """Provider 失敗／降級的分類（對應 `docs/v2/75` 第 4.1 節已列項）。"""

    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    DEGRADED = "degraded"


def _require_nonempty_str(value: object, field_name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} 必須是 str，收到 {type(value).__name__}")
    if not value.strip():
        raise ValueError(f"{field_name} 不可為空字串")


def _require_str(value: object, field_name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} 必須是 str，收到 {type(value).__name__}")


def _require_bool(value: object, field_name: str) -> None:
    if not isinstance(value, bool):
        raise TypeError(f"{field_name} 必須是 bool，收到 {type(value).__name__}")


@dataclass(frozen=True)
class ProviderRequest:
    """送往 Provider 的最小請求。"""

    request_id: str
    model: str
    input_text: str
    timeout_seconds: float
    max_retries: int

    def __post_init__(self) -> None:
        _require_nonempty_str(self.request_id, "request_id")
        _require_nonempty_str(self.model, "model")
        _require_str(self.input_text, "input_text")
        # bool 是 int 的子類，明確排除，避免 True 被當成 1 秒／1 次。
        if isinstance(self.timeout_seconds, bool) or not isinstance(
            self.timeout_seconds, (int, float)
        ):
            raise TypeError("timeout_seconds 必須是 int 或 float")
        if not self.timeout_seconds > 0:
            raise ValueError("timeout_seconds 必須大於 0")
        if isinstance(self.max_retries, bool) or not isinstance(self.max_retries, int):
            raise TypeError("max_retries 必須是 int")
        if self.max_retries < 0:
            raise ValueError("max_retries 不可為負")


@dataclass(frozen=True)
class ProviderResponse:
    """Provider 成功回應。`is_fake` 明標是否為離線假輸出。"""

    request_id: str
    provider_name: str
    model: str
    text: str
    is_fake: bool

    def __post_init__(self) -> None:
        _require_nonempty_str(self.request_id, "request_id")
        _require_nonempty_str(self.provider_name, "provider_name")
        _require_nonempty_str(self.model, "model")
        _require_str(self.text, "text")
        _require_bool(self.is_fake, "is_fake")


@dataclass(frozen=True)
class ProviderFailure:
    """Provider 失敗或降級的結構化結果（不夾帶原始例外物件或堆疊）。"""

    request_id: str
    provider_name: str
    kind: ProviderErrorKind
    message: str
    is_fake: bool

    def __post_init__(self) -> None:
        _require_nonempty_str(self.request_id, "request_id")
        _require_nonempty_str(self.provider_name, "provider_name")
        if not isinstance(self.kind, ProviderErrorKind):
            raise TypeError("kind 必須是 ProviderErrorKind")
        _require_nonempty_str(self.message, "message")
        _require_bool(self.is_fake, "is_fake")


@dataclass(frozen=True)
class ProviderOutcome:
    """一次呼叫的結果：`response` 與 `failure` 恰有一者非空。"""

    response: Optional[ProviderResponse] = None
    failure: Optional[ProviderFailure] = None

    def __post_init__(self) -> None:
        if self.response is not None and not isinstance(self.response, ProviderResponse):
            raise TypeError("response 必須是 ProviderResponse 或 None")
        if self.failure is not None and not isinstance(self.failure, ProviderFailure):
            raise TypeError("failure 必須是 ProviderFailure 或 None")
        if (self.response is None) == (self.failure is None):
            raise ValueError("response 與 failure 必須恰有一者非空")

    @property
    def is_success(self) -> bool:
        """是否為成功回應（屬性，不是欄位）。"""
        return self.response is not None
