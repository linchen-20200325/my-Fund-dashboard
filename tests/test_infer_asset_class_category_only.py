"""守衛：`infer_asset_class` 只吃資料層的基金類別，不吃基金名稱（客戶裁示）。

背景：新聞篩選原本把「基金名稱 + 類別」串起來做關鍵字比對推資產類別；
tab3 讀的 `metrics.category` 恆空，實際是純名稱推定。客戶裁示：分類只能來自
可追溯的基金類別（MoneyDJ／FundClear 原始 `category`），缺值保持 unknown。

本檔守下列幾件事：
  a. tab2／tab3 各自恰有 1 處呼叫 `infer_asset_class`（含任何 import 別名，
     例如函式內 lazy import 的 `as _infer_ac`；也含 `模組.infer_asset_class(...)`
     屬性呼叫）；該處唯一參數必須是 `.get('category')` 或 `.get('category', '')`，
     且參數子樹中不得出現名稱識別字／名稱鍵；
  b. 引用 `infer_asset_class` 的 production 檔案集合固定（新增呼叫點 → 轉紅、逼人重審）；
  c. 缺類別 → 'unknown'，且 'unknown' 不篩選新聞（行為不變）；
  d. 名稱不能改變分類（用 tab3 實際的取值表達式驗證）；
  e. tab3 投票時 'unknown' 不參與（`_cls_votes.pop("unknown", None)` 必須存在）。

⚠️ 射程限制：本守衛只檢查 UI 呼叫端傳的是什麼表達式，**不涵蓋資料層把基金名稱
寫進 `category` 欄位的情形**（那要在資料層另行把關，本檔看不到）。
另：以 `getattr`、動態 import 等非字面寫法取得的函式，本守衛的 AST 掃描抓不到；
(b) 的檔案層字串掃描仍會把引用該名稱的新檔案擋下。
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
_FUNC = "infer_asset_class"
_NAME_IDENTS = {"name", "fund_name"}
_SKIP_DIRS = {"tests", "__pycache__", "node_modules", "venv", ".venv"}


def _tree(rel: str) -> ast.Module:
    return ast.parse((_ROOT / rel).read_text(encoding="utf-8"), filename=rel)


def _aliases(tree: ast.Module) -> set:
    """檔內所有指向 infer_asset_class 的本地名稱（含函式內 lazy import 與任意別名）。"""
    names = {_FUNC}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for a in node.names:
                if a.name == _FUNC:
                    names.add(a.asname or a.name)
    return names


def _calls_in(rel: str) -> list:
    tree = _tree(rel)
    aliases = _aliases(tree)
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if (isinstance(fn, ast.Name) and fn.id in aliases) or (
                isinstance(fn, ast.Attribute) and fn.attr == _FUNC):
            out.append(node)
    return sorted(out, key=lambda n: (n.lineno, n.col_offset))


def _assert_category_only_arg(rel: str, call: ast.Call) -> None:
    where = f"{rel}:{call.lineno}"
    assert len(call.args) == 1 and not call.keywords, \
        f"{where}：infer_asset_class 只能有一個位置參數（基金類別）"
    arg = call.args[0]
    assert not isinstance(arg, (ast.JoinedStr, ast.BinOp)), \
        f"{where}：參數不得為 f-string／字串串接（禁止把名稱與類別併在一起）"
    for sub in ast.walk(arg):
        if isinstance(sub, ast.Name):
            assert sub.id not in _NAME_IDENTS, \
                f"{where}：參數中出現名稱識別字 {sub.id!r}"
        if isinstance(sub, ast.Attribute):
            assert sub.attr not in _NAME_IDENTS, \
                f"{where}：參數中出現名稱屬性 {sub.attr!r}"
        if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
            assert sub.value not in _NAME_IDENTS, \
                f"{where}：參數中出現名稱鍵 {sub.value!r}"
    assert (isinstance(arg, ast.Call)
            and isinstance(arg.func, ast.Attribute)
            and arg.func.attr == "get"
            and not arg.keywords
            and 1 <= len(arg.args) <= 2
            and isinstance(arg.args[0], ast.Constant)
            and arg.args[0].value == "category"), \
        f"{where}：參數必須是 `.get('category')` 或 `.get('category', '')`"
    if len(arg.args) == 2:
        dflt = arg.args[1]
        assert isinstance(dflt, ast.Constant) and dflt.value == "", \
            f"{where}：`.get('category', DEFAULT)` 的預設值只能是空字串常數 ''"


# ── a. 呼叫點只傳類別（含別名），且每檔恰 1 處 ─────────────────────────

def _check_file(rel: str) -> None:
    aliases = _aliases(_tree(rel))
    assert aliases - {_FUNC}, f"{rel} 找不到 infer_asset_class 的 import（守衛空掃）"
    calls = _calls_in(rel)
    assert len(calls) == 1, (
        f"{rel} 對 infer_asset_class（含別名 {sorted(aliases)}）的呼叫數應為 1，"
        f"實際 {len(calls)}（行 {[c.lineno for c in calls]}）。新增呼叫點須重審並更新本守衛。")
    for c in calls:
        _assert_category_only_arg(rel, c)


def test_tab2_calls_pass_category_only():
    _check_file(_TAB2)


def test_tab3_calls_pass_category_only():
    _check_file(_TAB3)


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


# ── e. tab3：缺類別（unknown）不投票 ──────────────────────────────────

def test_tab3_unknown_does_not_vote():
    found = False
    for node in ast.walk(_tree(_TAB3)):
        if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "pop"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "_cls_votes"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and node.args[0].value == "unknown"):
            found = True
    assert found, 'tab3 必須有 `_cls_votes.pop("unknown", None)`（缺類別不主導投票）'
