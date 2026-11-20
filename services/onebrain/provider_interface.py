"""OB-B 離線切片：Provider-neutral 抽象介面。

契約：
- `invoke` 對「Provider 層級的失敗或降級」**不 raise**，一律回傳帶 `failure` 的
  `ProviderOutcome`；只有程式錯誤（例如傳入非 `ProviderRequest`）才 raise。
- 本套件沒有預設 Provider、工廠或設定選擇器：呼叫端必須明確注入實例。
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from services.onebrain.provider_types import ProviderOutcome, ProviderRequest


class AnalysisProvider(ABC):
    """分析 Provider 的最小介面。"""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider 識別名稱。"""

    @abstractmethod
    def invoke(self, request: ProviderRequest) -> ProviderOutcome:
        """執行一次請求，回傳結構化結果。"""
