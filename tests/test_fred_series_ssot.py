"""SSOT 守衛：fetch_all_indicators 不得用字面值 series id，必須走 shared/fred_series 常數。

緣由（接續 2026-06-28 SSOT 收斂）：FRED series id 的單一權威來源是
`shared/fred_series.py`（CLAUDE.md §2.1 / §3.3）。`fetch_all_indicators` 原本以
`_fred("CCSA", ...)` 等 17 處字面值硬寫 series id，與 SSOT 重複 → 任一字面值打錯
（如 "CCSA" 誤拼 "CSSA"）會靜默抓錯 series。已全部改為 `_fred(FRED_CCSA, ...)`。

本測試靜態守衛：`_fred(...)` 第一個引數不得是字串字面值（必須是 Name，即 FRED_* 常數）。
"""
from __future__ import annotations

import ast


def _macro_service_tree() -> ast.AST:
    return ast.parse(open("services/macro/us_indicators.py", encoding="utf-8").read())


def test_fred_calls_use_constants_not_literals():
    tree = _macro_service_tree()
    offenders = []
    for n in ast.walk(tree):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id == "_fred" and n.args):
            first = n.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                offenders.append((n.lineno, first.value))
    assert not offenders, (
        "_fred() 第一個引數出現字面值 series id（應改用 shared/fred_series.py 的 FRED_* 常數）："
        + ", ".join(f"L{ln}:{v!r}" for ln, v in offenders)
    )


def test_fred_constants_imported_from_ssot():
    """確認 us_indicators 確實有引入 FRED_* 常數(SSOT 來源正確,可走 services.macro._helpers re-export)。"""
    src = open("services/macro/us_indicators.py", encoding="utf-8").read()
    # P1-7 v19.205 拆檔後 FRED_* 從 services.macro._helpers re-export(該 helper 走 shared.fred_series 真 SSOT)
    assert ("from shared.fred_series import" in src
            or "from services.macro._helpers import" in src)
    # 確認 _helpers 端真的 re-export 自 shared.fred_series(SSOT 鏈閉環驗證)
    helpers_src = open("services/macro/_helpers.py", encoding="utf-8").read()
    assert "from shared.fred_series import" in helpers_src
    for const in ("FRED_CCSA", "FRED_ICSA", "FRED_CPI", "FRED_ISM_PMI"):
        assert const in src, f"{const} 應引入並使用"
