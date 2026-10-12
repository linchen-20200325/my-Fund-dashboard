"""守衛：`infer_asset_class` 只吃資料層的基金類別，不吃基金名稱（客戶裁示）。

背景：新聞篩選原本把「基金名稱 + 類別」串起來做關鍵字比對推資產類別；
tab3 讀的 `metrics.category` 恆空，實際是純名稱推定。客戶裁示：分類只能來自
可追溯的基金類別（MoneyDJ／FundClear 原始 `category`），缺值保持 unknown。

本檔守四件事：
  a. tab2／tab3 每一處呼叫的唯一參數都是 `.get('category', ...)`，且不含名稱；
  b. 引用 `infer_asset_class` 的 production 檔案集合固定（新增呼叫點 → 轉紅、逼人重審）；
  c. 缺類別 → 'unknown'，且 'unknown' 不篩選新聞（行為不變）；
  d. 名稱不能改變分類（用 tab3 實際的取值表達式驗證）。
"""
from __future__ import annotations

import ast
from pathlib import Path

from repositories.news_repository import (
    filter_news_by_asset_class,
    infer_asset_class,
)

_ROOT = Path(__file__).resolve().parents[1]
_DEF_FILE = "repositories/news_repository.py"
_TAB2 = "ui/tab2_single_fund.py"
_TAB3 = "ui/tab3_portfolio.py"
_CALL_NAMES = {"_infer_ac", "infer_asset_class"}
_NAME_IDENTS = {"name", "fund_name"}
_SKIP_DIRS = {"tests", "__pycache__", "node_modules", "venv", ".venv"}


def _calls_in(rel: str) -> list:
    tree = ast.parse((_ROOT / rel).read_text(encoding="utf-8"), filename=rel)
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        nm = fn.id if isinstance(fn, ast.Name) else (
            fn.attr if isinstance(fn, ast.Attribute) else None)
        if nm in _CALL_NAMES:
            out.append(node)
    return out


def _assert_category_only_arg(rel: str, call: ast.Call) -> None:
    where = f"{rel}:{call.lineno}"
    assert len(call.args) == 1 and not call.keywords, \
        f"{where}：infer_asset_class 只能有一個位置參數（基金類別）"
    arg = call.args[0]
    assert not isinstance(arg, (ast.JoinedStr, ast.BinOp)), \
        f"{where}：參數不得為 f-string／字串串接（禁止把名稱與類別併在一起）"
    for sub in ast.walk(arg):
        if isinstance(sub, ast.Name):
            assert sub.id not in _NAME_IDENTS, f"{where}：參數中出現名稱識別字 {sub.id!r}"
        if isinstance(sub, ast.Attribute):
            assert sub.attr not in _NAME_IDENTS, f"{where}：參數中出現名稱屬性 {sub.attr!r}"
        if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
            assert sub.value not in _NAME_IDENTS, f"{where}：參數中出現名稱鍵 {sub.value!r}"
    assert (isinstance(arg, ast.Call)
            and isinstance(arg.func, ast.Attribute)
            and arg.func.attr == "get"
            and arg.args
            and isinstance(arg.args[0], ast.Constant)
            and arg.args[0].value == "category"), \
        f"{where}：參數必須是 `.get('category', ...)`（資料層的基金類別原值）"


# ── a. 呼叫點只傳類別 ────────────────────────────────────────────────

def test_tab2_calls_pass_category_only():
    calls = _calls_in(_TAB2)
    assert calls, "tab2 找不到任何 infer_asset_class 呼叫（守衛空掃）"
    for c in calls:
        _assert_category_only_arg(_TAB2, c)


def test_tab3_calls_pass_category_only():
    calls = _calls_in(_TAB3)
    assert calls, "tab3 找不到任何 infer_asset_class 呼叫（守衛空掃）"
    for c in calls:
        _assert_category_only_arg(_TAB3, c)


# ── b. 呼叫點集合固定 ────────────────────────────────────────────────

def test_infer_asset_class_reference_set_is_fixed():
    hits = set()
    for p in _ROOT.rglob("*.py"):
        rel_parts = p.relative_to(_ROOT).parts
        if any(part in _SKIP_DIRS or part.startswith(".") for part in rel_parts[:-1]):
            continue
        try:
            txt = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if "infer_asset_class" in txt:
            hits.add(p.relative_to(_ROOT).as_posix())
    assert hits == {_DEF_FILE, _TAB2, _TAB3}, (
        f"引用 infer_asset_class 的檔案集合改變：{sorted(hits)}。"
        "新增呼叫點必須只傳資料層的基金類別（不得傳基金名稱），並更新本守衛。")


# ── c. 缺類別 → unknown；unknown 不篩選 ──────────────────────────────

def test_missing_category_is_unknown():
    for v in ("", None, "  ", "\t\n"):
        assert infer_asset_class(v) == "unknown"


def test_unknown_does_not_filter_news():
    news = [
        {"title": "Oil prices jump", "summary": ""},
        {"title": "Treasury yield rises", "summary": ""},
        {"title": "Fed holds", "summary": "", "is_systemic": True},
    ]
    assert filter_news_by_asset_class(news, "unknown") == news


# ── d. 名稱不能改變分類（用 tab3 實際的取值表達式）────────────────────

def _tab3_category_expr():
    calls = _calls_in(_TAB3)
    assert calls
    expr = ast.Expression(body=calls[0].args[0])
    ast.fix_missing_locations(expr)
    code = compile(expr, _TAB3, "eval")
    # 僅評估從 tab3 原始碼取出的取值式（與 production 同一個表達式）
    return lambda f: eval(code, {}, {"f": f})


def test_name_cannot_change_classification():
    get_cat = _tab3_category_expr()
    names = ("某某全球債券基金", "某某台灣股票基金", "某某美元貨幣基金")
    for cat, expected in (("股票型", "stock"), ("多重資產型", "macro"),
                          ("", "unknown")):
        results = {
            infer_asset_class(get_cat({"name": n, "moneydj_raw": {"category": cat}}))
            for n in names
        }
        assert results == {expected}, (cat, results)
    # moneydj_raw 缺／None → unknown，不從名稱補
    for f in ({"name": "某某全球債券基金"},
              {"name": "某某台灣股票基金", "moneydj_raw": None}):
        assert infer_asset_class(get_cat(f)) == "unknown"
