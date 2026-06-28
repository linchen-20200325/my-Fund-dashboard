"""SSOT 漂移守衛(C)：fetch_all_indicators 卡片門檻 與 MACRO_THRESHOLDS 不得分歧。

緣由(A+B+C SSOT 收斂 Stage 2 / C):`fetch_all_indicators` 內 8 個指標的卡片燈號
門檻(signal/color/score 的 cutoff)與 `repositories.macro_repository.MACRO_THRESHOLDS`
**數字完全重複**(例:CONT_CLAIMS 1.7M/1.9M、ICSA 230k/300k、SAHM 0.3/0.5…)。

為何不直接合一(§8.5 停在已知地雷)：CLAUDE.md §3.3/§8.3 標記 `MACRO_THRESHOLDS`
為「**僅文件參考**、與 inline 語意不同源」,going-forward SSOT 是 `macro_thresholds_v2.py`,
且明訂門檻收斂須**逐指標**做(避免機械式 swap 悄悄改評分)。故本階段**不重構**,
改以「漂移守衛」釘住:這 8 個指標的 dict 門檻數字,必須仍以字面值出現在對應的
inline `R["KEY"] = dict(...)` 區塊裡——任一邊改了門檻、另一邊沒同步,CI 立即擋下。

(完整單一來源(card path 改讀 v2)為 F-GRAY-4 逐指標工作,待 user 指定指標再做。)
"""
from __future__ import annotations

import ast

from repositories.macro_repository import MACRO_THRESHOLDS

# 卡片燈號門檻與 MACRO_THRESHOLDS 重複的 8 個指標(2026-06-28 audit 確認)
_DUP_KEYS = [
    "JOBLESS", "CONT_CLAIMS", "CONSUMER_CONF", "SAHM",
    "SLOOS", "PERMIT_HOUSING", "LEI", "INFL_EXP_5Y",
]


def _indicator_dict_nodes():
    # P1-7 v19.205 拆檔後 fetch_all_indicators 搬至 services/macro/us_indicators.py
    tree = ast.parse(open("services/macro/us_indicators.py", encoding="utf-8").read())
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "fetch_all_indicators")
    out = {}
    for n in ast.walk(fn):
        if (isinstance(n, ast.Assign) and n.targets
                and isinstance(n.targets[0], ast.Subscript)
                and isinstance(n.targets[0].value, ast.Name)
                and n.targets[0].value.id == "R"
                and isinstance(n.value, ast.Call)):
            sl = n.targets[0].slice
            if isinstance(sl, ast.Constant):
                out[sl.value] = n.value
    return out


def _numeric_literals(node: ast.AST) -> set:
    out = set()
    for m in ast.walk(node):
        # 正數字面值
        if isinstance(m, ast.Constant) and isinstance(m.value, (int, float)) and not isinstance(m.value, bool):
            out.add(float(m.value))
        # 負數字面值在 AST 為 UnaryOp(USub, Constant)（如 -0.7）
        elif (isinstance(m, ast.UnaryOp) and isinstance(m.op, ast.USub)
              and isinstance(m.operand, ast.Constant)
              and isinstance(m.operand.value, (int, float))
              and not isinstance(m.operand.value, bool)):
            out.add(-float(m.operand.value))
    return out


def test_card_thresholds_match_macro_thresholds():
    nodes = _indicator_dict_nodes()
    problems = []
    for key in _DUP_KEYS:
        assert key in nodes, f"fetch_all_indicators 找不到 R[{key!r}]"
        assert key in MACRO_THRESHOLDS, f"MACRO_THRESHOLDS 缺 {key!r}"
        inline_nums = _numeric_literals(nodes[key])
        dict_vals = {float(v) for v in MACRO_THRESHOLDS[key].values()}
        missing = {v for v in dict_vals if v not in inline_nums}
        if missing:
            problems.append(f"{key}: MACRO_THRESHOLDS 門檻 {sorted(missing)} 未出現在 inline 卡片區塊")
    assert not problems, (
        "卡片門檻與 MACRO_THRESHOLDS 漂移(SSOT 不同步)：\n  " + "\n  ".join(problems)
        + "\n→ 改門檻時兩邊須同步(或執行 F-GRAY-4 逐指標單一來源遷移)。"
    )


def test_dup_keys_are_documented():
    """確保守衛涵蓋的 8 指標都還存在於 MACRO_THRESHOLDS(防止 key 改名後守衛空轉)。"""
    for key in _DUP_KEYS:
        assert key in MACRO_THRESHOLDS
