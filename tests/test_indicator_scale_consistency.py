"""SSOT 守衛：fetch_all_indicators 每個指標的 value/prev 與 series 必須同尺度。

緣由：2026-06-28 「持續失業金 Z=+57324」假極端 bug 的根因是 CONT_CLAIMS 的
`series=s/10000`（萬人）但 `value=int(v)` 仍是原始人數 → 單位錯位讓 Z-Score 爆量，
並汙染就業子循環與整體景氣評分。修正後 value/prev 也 /10000 與 series 一致。

評分矩陣（中期循環 Z-Score）與資料診斷 tab 同讀 st.session_state["indicators"]
（= fetch_all_indicators 輸出），是單一資料來源；本測試把「value/prev 與 series
同尺度」釘成跨全部指標的不變量，讓任何 CCSA 類單位漂移在 CI 就被擋下、不會再讓
兩邊（評分 / 診斷）看到不一致或爆量的數字。

做法：靜態 AST 分析 fetch_all_indicators 內每個 `R["KEY"] = dict(...)` 構造，
擷取 value / prev / series 三個運算式裡「除以常數」的 scale 因子集合；只要 series
有 scale（如 /10000），value 與 prev 的 scale 因子集合就必須與 series 一致。
（series 無 scale 的指標不施加約束，避免誤判 YoY/%/原值類指標。）
"""
from __future__ import annotations

import ast


def _fetch_all_indicators_fn() -> ast.FunctionDef:
    tree = ast.parse(open("services/macro_service.py", encoding="utf-8").read())
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "fetch_all_indicators":
            return node
    raise AssertionError("找不到 fetch_all_indicators")


def _const_divisors(expr: ast.AST) -> set:
    """擷取運算式內所有『除以整數常數』的 divisor（scale 因子）。"""
    out = set()
    for n in ast.walk(expr):
        if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div) and isinstance(n.right, ast.Constant):
            if isinstance(n.right.value, (int, float)):
                out.add(n.right.value)
    return out


def _iter_indicator_dicts(fn: ast.FunctionDef):
    """yield (key, keywords_dict) for each R["KEY"] = dict(...) 構造。"""
    for n in ast.walk(fn):
        if (isinstance(n, ast.Assign) and n.targets
                and isinstance(n.targets[0], ast.Subscript)
                and isinstance(n.targets[0].value, ast.Name)
                and n.targets[0].value.id == "R"
                and isinstance(n.value, ast.Call)):
            sl = n.targets[0].slice
            key = sl.value if isinstance(sl, ast.Constant) else "<dynamic>"
            kw = {k.arg: k.value for k in n.value.keywords if k.arg}
            yield key, kw


def test_value_series_same_scale_for_all_indicators():
    fn = _fetch_all_indicators_fn()
    seen = 0
    for key, kw in _iter_indicator_dicts(fn):
        if "series" not in kw:
            continue
        s_div = _const_divisors(kw["series"])
        if not s_div:
            continue  # series 無 scale → 不約束（YoY/%/原值類）
        seen += 1
        v_div = _const_divisors(kw["value"]) if "value" in kw else set()
        assert v_div == s_div, (
            f'{key}: value 的 scale 因子 {v_div} 與 series {s_div} 不一致 → '
            f'Z-Score / 顯示單位會錯位（CCSA 類 bug）。value 應套用相同 /scale。'
        )
        if "prev" in kw:
            p_div = _const_divisors(kw["prev"])
            assert p_div == s_div, (
                f'{key}: prev 的 scale 因子 {p_div} 與 series {s_div} 不一致。'
            )
    # 目前 JOBLESS + CONT_CLAIMS 兩個指標用 /10000 scale；確保測試真的有掃到
    assert seen >= 2, f"預期至少 2 個含 scale 的指標被檢查，實際 {seen}（測試可能失效）"


def test_cont_claims_specifically_scaled():
    """明確釘 CONT_CLAIMS（本次 bug 主角）：series 與 value 皆 /10000（萬人）。"""
    fn = _fetch_all_indicators_fn()
    for key, kw in _iter_indicator_dicts(fn):
        if key == "CONT_CLAIMS":
            assert _const_divisors(kw["series"]) == {10000}
            assert _const_divisors(kw["value"]) == {10000}, "CONT_CLAIMS value 必須 /10000（萬人）"
            return
    raise AssertionError("找不到 CONT_CLAIMS 指標")
