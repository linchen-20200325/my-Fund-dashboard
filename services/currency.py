"""v19.71 services — 幣別正規化（single source of truth）。

抽自 services/ledger_service._norm_ccy_pure 與 ui/tab2_single_fund / ui/tab3_t7_ledger
重複的 `_CCY_NORMALIZE` 字典。User 反映「重複造輪子」實證：3 個 Tab 各寫一份同款字典，
組合健診 Tab 漏接 → 截圖 bug「FX 美元TWD 抓不到」。

對外 API：
- normalize_ccy(raw) -> str：中文/ISO 都統一回 ISO 3 碼；未知回原值大寫
- CCY_NORMALIZE：dict 常數（給 test / 既有 caller 直讀）

設計原則：純函式、零 IO、零依賴。任何新 Tab 都直接 import 用，不准再 copy 字典。
"""
from __future__ import annotations

CCY_NORMALIZE: dict[str, str] = {
    "美元": "USD", "美金": "USD",
    "歐元": "EUR",
    "港幣": "HKD", "港元": "HKD",
    "日圓": "JPY", "日元": "JPY",
    "澳幣": "AUD", "澳元": "AUD",
    "英鎊": "GBP",
    "人民幣": "CNY", "CNH": "CNY",
    "台幣": "TWD", "新台幣": "TWD", "新臺幣": "TWD",
    "瑞郎": "CHF", "瑞士法郎": "CHF",
    "新幣": "SGD", "新加坡幣": "SGD", "星幣": "SGD",
    "加幣": "CAD", "加元": "CAD",
    "紐幣": "NZD", "紐元": "NZD",
    "蘭特": "ZAR", "南非幣": "ZAR",
}


def normalize_ccy(raw, default: str = "USD") -> str:
    """幣別正規化：中文/ISO 都統一回 ISO 3 碼。

    Args:
        raw: 任意輸入（可能是「美元」/「USD」/None/空字串/亂碼）。
        default: raw 為空時的預設值（預設 USD — 保單最常見幣別）。

    Returns:
        ISO 3 碼字串，例：USD/TWD/EUR/JPY。未知中文 → 回原值大寫。
    """
    _u = str(raw or default).upper().strip()
    if not _u:
        return default
    return CCY_NORMALIZE.get(_u, _u)
