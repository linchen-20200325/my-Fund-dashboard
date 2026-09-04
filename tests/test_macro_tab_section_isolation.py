"""v19.429 — 總經 Tab section 級 Fail-Loud 隔離 的**接線驗證**(`PROCESS.md §4`)。

背景:線上回報「總經」分頁渲染 `TypeError: 'NoneType' object is not iterable`,
且「已隔離、其他分頁不受影響」。`app.py` 以 `st.tabs` 單次 run 渲染全部分頁,總經
(第 1 個 `with` 區塊)未捕捉的例外會中止整個 script → 其後分頁全數空白;而總經
Tab 內的四時域 section 原本是**裸呼叫**,任一 section 失敗會連坐整塊。

本檔用 **AST 檢查呼叫端**(非只檢查函式能不能跑 —— 後者在 caller 沒改時照樣綠,
等於沒測,見 `PROCESS.md §4`「算對了但沒接出去」):
  1. `_safe_section` 存在、且是 Fail-Loud(try/except + 呼叫 `friendly_error`,
     **非**靜默 `pass`)。
  2. 5 個 section renderer + 即時決策矩陣 **一律經 `_safe_section` 包裹**,
     不得再有任何裸呼叫。
  3. `app.py` 的 `with tab_macro:` 有外層 try/except 分頁隔離,try 包住 ① 的 render
     函式(2026-09-04 起為 `render_market_overview`,WF-IA-1 新 View)、
     except 走 `friendly_error`。
  4. `ui/tab1_macro_longterm.py` 的 `news_items` 取值改 `or []`(修 `get(k,
     default)` 對「值為 None」失效的洞),不再以兩參 `get("news_items", …)` 為唯一防線。
"""
from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_TAB1 = _ROOT / "ui" / "tab1_macro.py"
_LONG = _ROOT / "ui" / "tab1_macro_longterm.py"
_APP = _ROOT / "app.py"

# 總經 Tab 內、必須被 _safe_section 隔離的 section renderer + 即時決策矩陣。
_SECTION_FNS = {
    "render_long_term_section",
    "render_mid_cycle_section",
    "render_short_radar_section",
    "render_inflection_alert_section",
    "render_ai_summary_section",
    "_render_realtime_decision_dashboard",
}


# ══════════════════════════════════════════════════════════════
# 共用 AST 工具
# ══════════════════════════════════════════════════════════════
def _tree(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"))


def _call_name(call: ast.Call) -> str:
    f = call.func
    if isinstance(f, ast.Name):
        return f.id
    return str(getattr(f, "attr", ""))


def _funcdef(tree: ast.AST, name: str) -> ast.FunctionDef | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def _import_aliases(tree: ast.AST, orig_name: str) -> set[str]:
    """回傳 `from … import <orig_name> as X` 的所有本地別名 X(含未改名者)。"""
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for a in node.names:
                if a.name == orig_name:
                    out.add(a.asname or a.name)
    return out


# ══════════════════════════════════════════════════════════════
# 1) _safe_section 存在且 Fail-Loud
# ══════════════════════════════════════════════════════════════
def test_safe_section_defined_and_fail_loud():
    """修正前紅在哪:section 裸呼叫,無 _safe_section → 本測 collect 不到函式。"""
    tree = _tree(_TAB1)
    fn = _funcdef(tree, "_safe_section")
    assert fn is not None, "ui/tab1_macro.py 未定義 _safe_section"

    tries = [n for n in ast.walk(fn) if isinstance(n, ast.Try)]
    assert tries, "_safe_section 缺 try/except(無法隔離子區塊例外)"

    fe_aliases = _import_aliases(tree, "friendly_error") or {"friendly_error"}
    handler_ok = False
    for t in tries:
        for h in t.handlers:
            body_calls = {
                _call_name(c) for c in ast.walk(h) if isinstance(c, ast.Call)
            }
            if body_calls & fe_aliases:
                # §1:except 不得只是 pass / ...(靜默吞例外)
                only_noop = all(
                    isinstance(s, ast.Pass)
                    or (isinstance(s, ast.Expr)
                        and isinstance(s.value, ast.Constant))
                    for s in h.body
                )
                assert not only_noop, "_safe_section 的 except 疑似靜默吞(§1 違憲)"
                handler_ok = True
    assert handler_ok, (
        "_safe_section 的 except 未呼叫 friendly_error"
        "(Fail-Loud:顯式顯示 + stderr 鏡射 + traceback expander)")


# ══════════════════════════════════════════════════════════════
# 2) 5 section + 即時決策矩陣 一律經 _safe_section(無裸呼叫)
# ══════════════════════════════════════════════════════════════
def test_no_bare_section_calls():
    """修正前紅在哪:render_XXX_section(...) 為直接 Call → 例外連坐整塊 + 上炸分頁。"""
    tree = _tree(_TAB1)
    bare = sorted({
        _call_name(node)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and _call_name(node) in _SECTION_FNS
    })
    assert not bare, f"這些 section 仍被裸呼叫(未過 _safe_section):{bare}"


def test_sections_wired_via_safe_section():
    """每個 section renderer 都必須以引數形式出現在某個 _safe_section(...) 呼叫。"""
    tree = _tree(_TAB1)
    wired: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _call_name(node) == "_safe_section":
            for a in node.args:
                if isinstance(a, ast.Name) and a.id in _SECTION_FNS:
                    wired.add(a.id)
    missing = _SECTION_FNS - wired
    assert not missing, f"這些 section 未接進 _safe_section:{sorted(missing)}"


# ══════════════════════════════════════════════════════════════
# 3) app.py 分頁級外層隔離
# ══════════════════════════════════════════════════════════════
def test_app_macro_tab_isolation_guard():
    """修正前紅在哪:`with tab_macro:` 直呼 render_macro_tab,無 try → 例外中止
    整個 script,其後所有分頁空白(user 回報的『其他分頁』風險本源)。"""
    tree = _tree(_APP)
    with_macro = None
    for node in ast.walk(tree):
        if isinstance(node, ast.With):
            for item in node.items:
                ctx = item.context_expr
                if isinstance(ctx, ast.Name) and ctx.id == "tab_macro":
                    with_macro = node
    assert with_macro is not None, "app.py 找不到 `with tab_macro:` 區塊"

    tries = [n for n in ast.walk(with_macro) if isinstance(n, ast.Try)]
    assert tries, "`with tab_macro:` 內缺 try/except 分頁隔離"

    body_calls = {
        _call_name(c)
        for t in tries for c in ast.walk(t) if isinstance(c, ast.Call)
    }
    # 2026-09-04 五分頁動線重構（WF-IA-1）：① 的 render 函式換成
    # `ui/views/page_01_macro.py::render_market_overview`。
    # ⚠️ **本條守的東西一字未減**：`with tab_macro:` 仍然必須有 try/except 分頁隔離、
    #    try 仍然必須包住那個 render 呼叫、except 仍然必須走 `friendly_error`。
    #    改的只是**被包住的那個函式叫什麼名字**；拆掉 try 照樣紅。
    assert "render_market_overview" in body_calls, \
        "分頁隔離 try 未包住 render_market_overview"

    fe_aliases = _import_aliases(tree, "friendly_error") or {"friendly_error"}
    assert body_calls & fe_aliases, "分頁隔離 except 未呼叫 friendly_error(Fail-Loud)"


# ══════════════════════════════════════════════════════════════
# 4) longterm news_items 的 None 洞已補
# ══════════════════════════════════════════════════════════════
def test_longterm_news_items_none_guarded():
    """修正前紅在哪:`get("news_items", [])` 在『key 存在但值為 None』時仍回 None
    (default 只在 key 缺席時生效)→ 下方 list 運算 / n.get 拋 TypeError。"""
    tree = _tree(_LONG)

    # (a) 不得再以兩參 get("news_items", <default>) 當唯一防線
    two_arg = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and _call_name(node) == "get"
        and node.args and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == "news_items" and len(node.args) >= 2
    ]
    assert not two_arg, (
        f"news_items 仍用 get(k, default)(值為 None 時漏接):line {two_arg}")

    # (b) 需有 `st.session_state.get("news_items") or []` 的顯式 or-fallback
    has_or_fallback = False
    for node in ast.walk(tree):
        if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or):
            left = node.values[0]
            if isinstance(left, ast.Call) and _call_name(left) == "get" \
                    and left.args and isinstance(left.args[0], ast.Constant) \
                    and left.args[0].value == "news_items":
                has_or_fallback = True
    assert has_or_fallback, (
        "news_items 取值缺 `get('news_items') or []` 的 None-safe fallback")
