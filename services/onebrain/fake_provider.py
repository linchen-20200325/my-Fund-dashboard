"""OB-B 離線切片：離線 `FakeProvider`（測試專用）。

⛔ FAKE 輸出不得進入任何正式頁面或 production 路徑。
本檔的輸出是固定常數標記，不是 AI 分析，也不含任何投資判斷、方向語意、機率或信心數字。
無隨機、無時鐘、無 I/O、無環境變數；同一輸入永遠得到同一輸出。
"""

from __future__ import annotations

from enum import Enum

from services.onebrain.provider_interface import AnalysisProvider
from services.onebrain.provider_types import (
    ProviderErrorKind,
    ProviderFailure,
    ProviderOutcome,
    ProviderRequest,
    ProviderResponse,
)

FAKE_PROVIDER_NAME = "FAKE-OFFLINE-PROVIDER"

# 固定標記：必含「FAKE」與「非 AI 分析」。
FAKE_OUTPUT_MARKER = "FAKE｜離線測試標記，非 AI 分析"

_FAKE_FAILURE_MESSAGES = {
    ProviderErrorKind.TIMEOUT: "FAKE｜模擬逾時（離線測試情境，非真實 Provider）",
    ProviderErrorKind.RATE_LIMIT: "FAKE｜模擬頻率限制（離線測試情境，非真實 Provider）",
    ProviderErrorKind.PROVIDER_UNAVAILABLE: "FAKE｜模擬服務不可用（離線測試情境，非真實 Provider）",
    ProviderErrorKind.DEGRADED: "FAKE｜模擬降級（離線測試情境，非真實 Provider）",
}


class FakeScenario(Enum):
    """FakeProvider 的固定情境。"""

    MARKER = "marker"
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    UNAVAILABLE = "unavailable"
    DEGRADED = "degraded"


_SCENARIO_TO_KIND = {
    FakeScenario.TIMEOUT: ProviderErrorKind.TIMEOUT,
    FakeScenario.RATE_LIMIT: ProviderErrorKind.RATE_LIMIT,
    FakeScenario.UNAVAILABLE: ProviderErrorKind.PROVIDER_UNAVAILABLE,
    FakeScenario.DEGRADED: ProviderErrorKind.DEGRADED,
}


class FakeProvider(AnalysisProvider):
    """依固定情境回傳固定結果的離線 Provider。"""

    def __init__(self, scenario: FakeScenario = FakeScenario.MARKER) -> None:
        if not isinstance(scenario, FakeScenario):
            raise TypeError("scenario 必須是 FakeScenario")
        self._scenario = scenario

    @property
    def name(self) -> str:
        return FAKE_PROVIDER_NAME

    @property
    def scenario(self) -> FakeScenario:
        return self._scenario

    def invoke(self, request: ProviderRequest) -> ProviderOutcome:
        if not isinstance(request, ProviderRequest):
            raise TypeError("request 必須是 ProviderRequest")
        if self._scenario is FakeScenario.MARKER:
            return ProviderOutcome(
                response=ProviderResponse(
                    request_id=request.request_id,
                    provider_name=FAKE_PROVIDER_NAME,
                    model=request.model,
                    text=FAKE_OUTPUT_MARKER,
                    is_fake=True,
                )
            )
        kind = _SCENARIO_TO_KIND[self._scenario]
        return ProviderOutcome(
            failure=ProviderFailure(
                request_id=request.request_id,
                provider_name=FAKE_PROVIDER_NAME,
                kind=kind,
                message=_FAKE_FAILURE_MESSAGES[kind],
                is_fake=True,
            )
        )
