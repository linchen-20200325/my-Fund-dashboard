"""v19.79 K6：TWD 貨幣格式化 SSOT 純函式模組。

Phase 1 audit 找到 `NT$...:,.0f` 散落在 Tab3 portfolio / T7 ledger / portfolio_linkage
等 UI render 層（64 處），STATE.md K6 待辦。本模組收「TWD 千分位金額顯示」SSOT。

不收：plotly `hovertemplate` 內的 `%{value:,.0f}` — 那是 plotly 模板語法、
由 plotly 在 render time 解析，**不可** 用 Python 函式取代。

設計：純函式、零 import 依賴；caller 用
`from services.format_helpers import fmt_twd`。

對外 API：
- fmt_twd(amount, *, sign=False, precision=0, prefix="NT$") -> str

行為：
- None / NaN          → "—"
- 整數金額（精度 0）   → "NT$1,234"
- 帶小數（精度 N）     → "NT$1,234.56"
- sign=True 強制 +/-  → "NT$+1,234" / "NT$-1,234"
- prefix=""           → 純千分位、無 NT$ 前綴（HTML 拼接場景）
"""
from __future__ import annotations

import math
from typing import Union

Number = Union[int, float, None]


def fmt_twd(
    amount: Number,
    *,
    sign: bool = False,
    precision: int = 0,
    prefix: str = "NT$",
) -> str:
    """TWD 千分位金額格式化。

    Args:
        amount: 金額；None / NaN → "—"
        sign:   True 時強制顯示 +/- 號（用於損益、月差等場景）
        precision: 小數位數（預設 0）
        prefix: 貨幣前綴；預設 "NT$"，傳 "" 時純千分位

    Returns:
        格式化字串；空值統一 "—" 避免 caller 額外判 None。
    """
    if amount is None:
        return "—"
    try:
        v = float(amount)
    except (TypeError, ValueError):
        return "—"
    if math.isnan(v) or math.isinf(v):
        return "—"
    spec = f"{'+' if sign else ''},.{precision}f"
    return f"{prefix}{format(v, spec)}"
