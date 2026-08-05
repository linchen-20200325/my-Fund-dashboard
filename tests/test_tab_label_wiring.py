"""test_tab_label_wiring — 分頁名 SSOT + **接線驗證**(`PROCESS.md §4`)。

背景(2026-08-05 稽核 🔴 必修 2):三處「請至 X 分頁」指路文案指向**不存在的分頁名**
(「📦 投資組合」/「📊 組合基金」/ Tab2「單檔基金」),根因是 `app.py` 的
`st.tabs([...])` 與各文案各自寫死字串,沒有共同來源。修法是把
`ui/helpers/story_nav._STEPS` 升為唯一來源、加 `tab_label()` 導出去序號的分頁名。

⚠️ 本檔核心是 `test_app_tabs_are_wired_to_story_nav`:
   **「`tab_label()` 寫好但 caller 沒改」時必須變紅**。
   單純斷言「app.py 的字串 ⊇ _STEPS 的字串」不合格 —— 兩邊現值恰好相同,
   caller 沒接也照樣綠(這正是本 repo 四次「算對了沒接出去」的形狀)。
   所以這裡用 AST 檢查那 4 個 slot **是不是 `tab_label(...)` 呼叫**,而非字面值。
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ui.helpers.story_nav import _STEPS, tab_label

_ROOT = Path(__file__).resolve().parents[1]
_APP = _ROOT / "app.py"
_GRP_HEALTH = _ROOT / "ui" / "tab_fund_grp_health.py"


# ══════════════════════════════════════════════════════════════
# 1) tab_label 純函式
# ══════════════════════════════════════════════════════════════
class TestTabLabel:
    def test_strips_ordinal_prefix(self):
        assert tab_label("macro") == "🌐 市場定調"
        assert tab_label("health") == "💊 組合健診"
        assert tab_label("fund") == "🔍 個基深掘"
        assert tab_label("portfolio") == "📊 配置 & 帳本"

    def test_derived_from_steps_not_a_second_copy(self):
        """每個 label 都必須是 `_STEPS` 該站字串去掉序號後的結果(不得另寫一份)。"""
        for _key, _label, _hint in _STEPS:
            assert _label.endswith(tab_label(_key)), (
                f"tab_label('{_key}') 與 _STEPS 的『{_label}』對不上 → 又出現第二份標籤")

    def test_unknown_key_raises(self):
        """§1 Fail Loud:未知 key 不得靜默回空字串/猜名(那是 bug 再次靜默的入口)。"""
        with pytest.raises(KeyError):
            tab_label("nope")


# ══════════════════════════════════════════════════════════════
# 2) 接線驗證 — app.py 的 st.tabs 真的吃 tab_label()
# ══════════════════════════════════════════════════════════════
def _top_level_tabs_elts() -> list:
    """回 app.py 頂層 `st.tabs([...])` 的 list 元素(巢狀子分頁元素較少,取最長者)。"""
    tree = ast.parse(_APP.read_text(encoding="utf-8"))
    lists: list[list] = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "tabs"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "st"
                and node.args
                and isinstance(node.args[0], ast.List)):
            lists.append(node.args[0].elts)
    assert lists, "app.py 找不到任何 st.tabs([...]) 呼叫"
    return max(lists, key=len)


def _resolve(elt) -> tuple:
    """(kind, label):('call', tab_label 導出值) / ('const', 字面值) / ('other', None)。"""
    if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
        return "const", elt.value
    if isinstance(elt, ast.Call) and elt.args and isinstance(elt.args[0], ast.Constant):
        _fn = elt.func.id if isinstance(elt.func, ast.Name) else getattr(elt.func, "attr", "")
        if str(_fn).lstrip("_") == "tab_label":
            return "call", tab_label(elt.args[0].value)
    return "other", None


def test_app_tab_labels_superset_of_story_nav():
    """app.py 的分頁名 ⊇ `_STEPS` 四站 —— 指路文案指得到的分頁一定存在。"""
    _resolved = [_resolve(e) for e in _top_level_tabs_elts()]
    _labels = {v for _k, v in _resolved if v is not None}
    _want = {tab_label(k) for k, _, _ in _STEPS}
    assert _want <= _labels, f"app.py 分頁名缺少決策動線站別:{sorted(_want - _labels)}"


def test_app_tabs_are_wired_to_story_nav():
    """**修正前必紅** —— 4 個決策站的 slot 必須是 `tab_label(...)` 呼叫,不是寫死字串。

    修正前 app.py 寫的是 `["🌐 市場定調", ...]` 字面值:字面值與 `_STEPS` 現值相同,
    上面那條 superset 測試照樣綠,但兩份標籤依舊各自維護 → 下次改名再次漂移。
    """
    _resolved = [_resolve(e) for e in _top_level_tabs_elts()]
    for _key, _lbl, _hint in _STEPS:
        _want = tab_label(_key)
        _kind = next((k for k, v in _resolved if v == _want), None)
        assert _kind == "call", (
            f"app.py 的「{_want}」分頁仍是寫死字串(kind={_kind}) —— "
            f"story_nav.tab_label() 存在但沒被 st.tabs 接出去,"
            f"app.py 與 story_nav 仍是兩份標籤(PROCESS.md §4 接線驗證)。")


# ══════════════════════════════════════════════════════════════
# 3) 示範 caller — 組合健診的指路文案
# ══════════════════════════════════════════════════════════════
def test_grp_health_hint_uses_tab_label():
    """**修正前必紅**:組合健診的「先至 X Tab 載入資料」原本寫死「🌐 市場定調」。"""
    src = _GRP_HEALTH.read_text(encoding="utf-8")
    assert "tab_label" in src, "tab_fund_grp_health.py 未接 story_nav.tab_label()"
    assert "先至「🌐 市場定調」" not in src, "指路文案仍寫死分頁名"
    assert "_tab_label('macro')" in src or '_tab_label("macro")' in src


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__, "-v"]))
