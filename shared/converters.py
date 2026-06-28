"""shared/converters.py — SSOT 容錯轉換 helpers(L0 純常數+純函式)。

v19.222 P1-1:深層稽核發現 12 處 `_safe_float` / `_safe_num` / `_fmt_pct`
散落 services / ui / helpers,收口到本 SSOT。caller 用 `as _safe_float`
alias import,inner code 0 改動。

提供 3 個 fn:
- safe_float(v, default=None) → Optional[float] | float
  None / NaN / inf / non-numeric → default(default=None 時回 None)
- safe_num(v) → Optional[float]
  寬鬆版,額外吃 "12.3%" / "1,234"(strip % 與 ,)→ float
- fmt_pct(v, plus=True, decimals=1, ratio=True) → str
  v(ratio 0.05 或 pct 5.0)→ "5.0%" 或 "+5.0%"
  ratio=True:輸入 0.05 表示 5%(內建 *100,crisis_ai_advisor 用法)
  ratio=False:輸入 5.0 已是百分比(tab2 用法)
"""
from __future__ import annotations

import math
from typing import Any, Optional


def safe_float(v: Any, default: Optional[float] = None) -> Optional[float]:
    """容錯 → float | default(None / NaN / inf / non-numeric → default)。"""
    if v is None:
        return default
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    if math.isnan(f) or math.isinf(f):
        return default
    return f


def safe_num(v: Any) -> Optional[float]:
    """寬鬆數值轉換:吃 float / '12.3%' / '1,234' / None → float | None。

    與 safe_float 不同:額外 strip '%' / ',' 字串,並排除 bool。
    """
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        try:
            f = float(v)
        except (TypeError, ValueError):
            return None
        return f if f == f and not math.isinf(f) else None
    try:
        f = float(str(v).replace("%", "").replace(",", "").strip())
        return f if f == f and not math.isinf(f) else None
    except (TypeError, ValueError):
        return None


def fmt_pct(v: Any, plus: bool = True, decimals: int = 1, ratio: bool = True) -> str:
    """v → 百分比字串。None / NaN → '—'。

    ratio=True(default):輸入 0.05 表示 5%(內建 *100)
    ratio=False:輸入 5.0 已是百分比
    plus=True:正數加 '+' 前綴
    """
    if v is None:
        return "—"
    try:
        x = float(v)
    except (TypeError, ValueError):
        return "—"
    if math.isnan(x) or math.isinf(x):
        return "—"
    pct = x * 100.0 if ratio else x
    sign = "+" if plus else ""
    return f"{pct:{sign}.{decimals}f}%"
