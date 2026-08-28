"""顏色五態分離 —— 守「形狀」而不是守字面。

客戶 2026-08-28 拍板（線框 `fund-empty-state-wireframe.html` §03）：
> 嚴格分離「業務紅燈」與「系統真紅燈」，未載入／未設定一律改灰色說明，
> 把用灰字印的真失敗改回系統紅燈。

本檔**刻意不做逐字斷言**。逐字斷言守不到語意 —— 姊妹 repo 實證過：一句假話被逐字
釘住之後，測試天天綠、話卻一直是假的。這裡守的是三種**結構**：

1. 手上有 exception → 一定不能用灰色 widget（`st.caption` / `st.info`）印出去。
   （AST：except handler 綁定的變數，不得出現在灰色 widget 的參數裡。）
2. 「金鑰／資料源沒設定」這種分支 → 一定不能用警示色 widget（`st.error` / `st.warning`）。
3. 三個入口自己畫出來的 widget 種類必須是對的（否則上面兩條可以靠改 helper 內容繞過）。

⚠️ 第 1、2 條是**單向**的：它們抓的是「畫錯顏色」，不是「有沒有畫」。
一個 except handler 什麼都不印（靜默吞掉）**不會**被本檔抓到 —— 那屬 §1 Fail Loud 的
守備範圍，不是本檔的。寫在這裡是為了讓下一個人知道本檔的邊界在哪。
"""
from __future__ import annotations

import ast
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]

# 本次（客戶拍板的第一批）涵蓋的範圍：組合健診套件 + 它的 Tab 主檔。
HEALTH_SCOPE = sorted((ROOT / "ui" / "helpers" / "fund_grp_health").glob("*.py")) + [
    ROOT / "ui" / "tab_fund_grp_health.py"
]

# 會把東西「印給使用者看」的呼叫：st.* 全部 + 專案自己的錯誤呈現入口。
_ST_RENDER_ATTRS = {"caption", "info", "warning", "error", "success", "markdown",
                    "write", "text", "code", "toast", "exception"}
_FUNC_RENDERERS = {"system_error", "friendly_error", "_friendly_error", "not_ready",
                   "business_alert"}
# 合格的「系統紅燈」入口（🔴 紅色錯誤框 + 可展開技術細節）。
RED_ENTRYPOINTS = {"system_error", "friendly_error", "_friendly_error", "st.error",
                   "st.exception"}


def _callee(call: ast.Call) -> str:
    if isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name):
        return f"{call.func.value.id}.{call.func.attr}"
    if isinstance(call.func, ast.Name):
        return call.func.id
    return "<?>"


def _rendering_calls(node: ast.AST):
    """node 底下所有「會印東西給使用者看」的呼叫。"""
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Call):
            continue
        name = _callee(sub)
        if ((name.startswith("st.") and sub.func.attr in _ST_RENDER_ATTRS)
                or name in _FUNC_RENDERERS):
            yield sub


def _names_in(node: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


@pytest.mark.parametrize("path", HEALTH_SCOPE, ids=lambda p: p.name)
def test_caught_exception_is_reported_as_a_system_failure(path: pathlib.Path):
    """真的壞掉了，畫面卻只是「還沒載入」—— 這是本批要修掉的那個 bug。

    判準（結構，不是字面）：這個 except handler **抓到了一個 exception，而且拿它去
    印給使用者看** → 那就是系統真出錯，印它的那個呼叫必須是「系統紅燈」入口。

    合格的系統紅燈入口只有兩個：
    - `ui.helpers.render_state.system_error()`（本批新增，走 friendly_error）
    - `st.error()` / `friendly_error()`（既有的正確寫法，未被本批動到的沿用）

    刻意**不**檢查訊息內容 —— 文案會被改寫，widget 種類不會。
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    bad = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler) or not node.name:
            continue
        for call in _rendering_calls(node):
            if node.name not in _names_in(call):
                continue                      # 沒把例外拿給使用者看 → 不歸本檔管
            if _callee(call) in RED_ENTRYPOINTS:
                continue                      # 已經是系統紅燈
            bad.append(f"{path.relative_to(ROOT)}:{call.lineno} "
                       f"{_callee(call)}(… {node.name} …)")
    assert not bad, (
        "以下位置把「抓到的例外」用非紅燈 widget 印出去，使用者會誤以為只是還沒載入、"
        "以為按一下就好；請改走 ui.helpers.render_state.system_error()：\n  "
        + "\n  ".join(bad)
    )


# ══════════════════════════════════════════════════════════════════
# 三個入口自己畫出來的 widget 種類 —— 上面的 AST 規則靠這幾條才不會被
# 「把 system_error 內容偷偷換成 st.caption」繞過。
# ══════════════════════════════════════════════════════════════════
class _FakeST:
    """記錄被呼叫的 widget 名稱（不驗文案）。"""

    def __init__(self, expander_raises: bool = False):
        self.calls: list[str] = []
        self._expander_raises = expander_raises

    def __getattr__(self, name):
        def _rec(*a, **k):
            self.calls.append(name)
        return _rec

    def expander(self, *a, **k):
        if self._expander_raises:
            # Streamlit 真的會這樣炸：Expanders may not be nested inside other expanders
            raise RuntimeError("Expanders may not be nested inside other expanders")
        import contextlib
        self.calls.append("expander")
        return contextlib.nullcontext()


def _run(fn, *, expander_raises=False, **kw):
    """在假的 streamlit 下跑 fn，回傳它畫了哪些 widget。"""
    import sys

    import ui.helpers.render_state as rs
    fake = _FakeST(expander_raises=expander_raises)
    orig_rs, orig_mod = rs.st, sys.modules["streamlit"]
    rs.st = fake
    sys.modules["streamlit"] = fake          # friendly_error 是函式內 lazy import
    try:
        fn(**kw)
    finally:
        rs.st = orig_rs
        sys.modules["streamlit"] = orig_mod
    return fake.calls


def test_not_ready_is_grey_and_cannot_carry_an_exception():
    from ui.helpers.render_state import not_ready
    calls = _run(not_ready, message="還沒載入", where="🌐 市場定調")
    assert calls == ["caption"], calls
    # 型別層防呆：「還沒載入」不可能有 exception 可報。
    with pytest.raises(TypeError):
        not_ready(RuntimeError("boom"))          # type: ignore[arg-type]


def test_system_error_is_a_red_box_with_technical_detail():
    from ui.helpers.render_state import system_error
    calls = _run(system_error, what="X 渲染失敗", exc=ValueError("boom"))
    assert "error" in calls, calls                  # 🔴 紅色錯誤框
    assert "code" in calls, calls                   # 技術細節（traceback）
    assert "caption" not in calls, calls            # 不得退化成灰字


def test_system_error_survives_a_nested_expander():
    """區塊隔離用的錯誤呈現，本身不可以炸掉整頁。

    這些 handler 有一部分住在 `st.expander` 裡（逐檔展開區）；Streamlit 禁止巢狀
    expander，硬開會把「一個區塊失敗」升級成整頁 StreamlitAPIException。
    """
    from ui.helpers.render_state import system_error
    calls = _run(system_error, expander_raises=True,
                 what="X 渲染失敗", exc=ValueError("boom"))
    assert "error" in calls and "code" in calls, calls


def test_business_alert_is_not_an_error_box():
    """業務紅燈：分析成功了，答案很難看 —— 那是成果，不是故障。"""
    from ui.helpers.render_state import business_alert
    calls = _run(business_alert, title="🔴 淘汰候選 2 檔", lines=["- A", "- B"])
    assert "error" not in calls, calls
    assert "markdown" in calls, calls
