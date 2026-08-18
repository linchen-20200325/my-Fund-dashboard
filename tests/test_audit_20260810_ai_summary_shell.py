"""2026-08-10 稽核 — 共用「AI 白話總體檢」widget 的摺疊空殼拆除(第 8 個同型現場)。

前七個現場(Tab① 決策矩陣 / 中國拖累 / 流動性引擎、Tab②  3-3-3 / 抓取診斷 /
進階指標、Tab③ FX 曝險、Tab⑤ NAV 匯入、Tab⑥ 兩處)已在
`test_audit_20260810_tab1_shells.py` 與 `test_audit_20260810_tab2356_shells.py` 收掉。
本檔補的是 **`ui/helpers/ai_summary.py`** —— 它之所以拖到最後,是因為它被四個
呼叫端共用,拆殼會同時動到四個畫面。

守三件事:

* **B1-8 空殼** —— widget 內容不得再被關進任何可收合容器。
  `expanded=True`(Tab①)的殼從一開始就是開的,從沒擋住任何東西,只多印一次標題並
  留一個誤點就收合的把手;`expanded=False`(其餘)則是把「已經花 10-20 秒生成、
  而且已經落地磁碟」的結論預設藏起來。兩種都不划算。
* **標題不重複** —— 拆殼後 widget 自己印標題,呼叫端若有逐字相同的第二份副本就必須收掉
  (同型判例:決策矩陣同一句話連印三次)。
* **`expanded` 參數 0 consumer 即刪** —— `PROCESS.md §4`:留著沒人讀的參數等於
  假裝有一個開關。連同**所有**呼叫端一起清乾淨。

⚠️ 位置 / 結構類斷言走 AST 或 runtime 錄製,不掃原始碼子字串 —— 這幾個檔的沿革
註解大量引述「expander」「摺疊」等字眼,`in src` 會提前命中註解變成假通過。
"""
from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_WIDGET = _ROOT / "ui" / "helpers" / "ai_summary.py"
_TAB1_AI = _ROOT / "ui" / "tab1_macro_ai.py"

# 呼叫端全集(2026-08-10 grep `render_ai_summary_widget` 的結果)。
# ⚠️ `ui/tab3_portfolio.py` 屬另一位開發者的所有權範圍,本輪**不修改**該檔 ——
#    它本來就沒傳 `expanded`,拿掉參數對它零影響;列在這裡是為了讓「日後有人
#    在任何呼叫端把參數加回來」也會紅。
_CALLERS = (
    _TAB1_AI,
    _ROOT / "ui" / "tab2_single_fund.py",
    _ROOT / "ui" / "tab3_portfolio.py",
    _ROOT / "ui" / "helpers" / "fund_grp_health" / "ai.py",
)

# Streamlit 這幾個 primitive 都渲染成「可收合容器」(同 tests/test_app_smoke.py 的清單)
_COLLAPSIBLE_ATTRS = ("expander", "status", "popover", "dialog")


# ══════════════════════════════════════════════════════════════
# 共用工具
# ══════════════════════════════════════════════════════════════
def _tree(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _fn_name(call: ast.Call) -> str:
    if isinstance(call.func, ast.Name):
        return call.func.id
    return str(getattr(call.func, "attr", ""))


def _static_text(node: ast.AST | None) -> str:
    """Constant / f-string 的**常數片段**接起來(動態片段以空字串代入)。"""
    if isinstance(node, ast.Constant):
        return node.value if isinstance(node.value, str) else ""
    if isinstance(node, ast.JoinedStr):
        return "".join(v.value for v in node.values
                       if isinstance(v, ast.Constant) and isinstance(v.value, str))
    return ""


def _md_headings(path: Path) -> list[str]:
    """該檔所有 `st.markdown("#…")` 的標題(含 f-string 的常數片段)。"""
    out: list[str] = []
    for _n in ast.walk(_tree(path)):
        if (isinstance(_n, ast.Call) and _fn_name(_n) == "markdown" and _n.args):
            _txt = _static_text(_n.args[0])
            if _txt.startswith("#"):
                out.append(_txt)
    return out


def _heading_level(text: str) -> int:
    return len(text) - len(text.lstrip("#"))


class _NullCtx:
    """`with st.container():` 的替身 —— 只要能進出即可。"""

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


class _RecorderST:
    """把所有 `st.<name>(...)` 呼叫錄下來的假 streamlit。

    刻意用 `__getattr__` 全捕捉:未來 widget 換用別的 primitive 也錄得到,
    不會因為「測試沒列到那個名字」而靜默漏測。
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple, dict]] = []

    def __getattr__(self, name: str):
        def _rec(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            return _NullCtx()
        return _rec

    def names(self) -> list[str]:
        return [c[0] for c in self.calls]


# ══════════════════════════════════════════════════════════════
# B1-8 — 內容不得在可收合容器內
# ══════════════════════════════════════════════════════════════
def test_widget_source_has_no_collapsible_primitive() -> None:
    """**修正前必紅**(舊行為衝突):整個 widget body 原本包在 `st.expander(...)` 裡。

    靜態面:這個檔案不該再出現任何可收合容器 primitive。
    """
    _bad = [(_n.lineno, _fn_name(_n)) for _n in ast.walk(_tree(_WIDGET))
            if isinstance(_n, ast.Call) and _fn_name(_n) in _COLLAPSIBLE_ATTRS]
    assert not _bad, (
        f"ui/helpers/ai_summary.py 又出現可收合容器 {_bad} —— "
        "AI 總結是使用者主動按鈕、等 10-20 秒換來的結論,不該再被闔起來")


def test_widget_body_renders_outside_any_collapsible_container(monkeypatch) -> None:
    """**修正前必紅**(舊行為衝突):執行期會呼叫 `st.expander`,且沒有任何 markdown 標題。

    行為面(比上一條強):真的把 widget 跑一次,錄下它對 streamlit 的每一個呼叫。
    走「快照為空」那條早退路徑 —— 它在 `with` 內,足以驗證外框是哪一種容器,
    又不會碰到按鈕 / Gemini / 磁碟快取。
    """
    import ui.helpers.ai_summary as _mod

    _rec = _RecorderST()
    monkeypatch.setattr(_mod, "st", _rec)
    _mod.render_ai_summary_widget(
        tab_key="pytest_tab", tab_label="測試分頁", snapshot="")

    _names = _rec.names()
    _bad = [n for n in _names if n in _COLLAPSIBLE_ATTRS]
    assert not _bad, f"widget 執行期仍用了可收合容器:{_bad}"
    assert "container" in _names, (
        "拆掉摺疊殼後仍應留 `st.container()` 當版面分界(既有 pattern),實際呼叫:"
        f"{_names}")
    assert "caption" in _names, "快照為空時必須照實說『沒有可分析的資料』(§1)"


def test_widget_prints_its_own_heading_at_runtime(monkeypatch) -> None:
    """**修正前必紅**(舊行為衝突):標題原本是 expander 的**標籤**,不是 markdown 標題。

    拆殼不可以順手把標題弄丟 —— 四個呼叫端裡有一個(Tab③ 組合戰情室)完全沒有
    自己的區塊標題,標題若下放給呼叫端,那一頁會變成一坨沒有名字的按鈕。
    """
    import ui.helpers.ai_summary as _mod

    _rec = _RecorderST()
    monkeypatch.setattr(_mod, "st", _rec)
    _mod.render_ai_summary_widget(
        tab_key="pytest_tab", tab_label="測試分頁", snapshot="")

    _heads = [str(c[1][0]) for c in _rec.calls
              if c[0] == "markdown" and c[1] and str(c[1][0]).startswith("#")]
    assert _heads, f"widget 沒印出任何標題,實際呼叫:{_rec.names()}"
    assert any("測試分頁" in h for h in _heads), (
        f"標題未帶 tab_label,使用者無從得知這段 AI 在講哪一頁:{_heads}")
    assert all(_heading_level(h) == 4 for h in _heads), (
        f"widget 標題應為第 4 級(呼叫端區塊標題的下一層),實際 {_heads}")


# ══════════════════════════════════════════════════════════════
# `expanded` 參數 0 consumer → 從 signature 與所有呼叫端清除
# ══════════════════════════════════════════════════════════════
def test_expanded_param_is_gone_from_signature() -> None:
    """**修正前必紅**(舊行為衝突):`expanded: bool = False` 原本在 signature 上。"""
    from ui.helpers.ai_summary import render_ai_summary_widget

    _params = inspect.signature(render_ai_summary_widget).parameters
    assert "expanded" not in _params, (
        "沒有摺疊容器了還留著 `expanded` 參數 = 假裝有一個開關(PROCESS §4)")


@pytest.mark.parametrize("path", _CALLERS, ids=[p.name for p in _CALLERS])
def test_no_caller_passes_expanded(path: Path) -> None:
    """**修正前必紅**(舊行為衝突):Tab① 傳 `expanded=True`、組合健檢傳 `expanded=False`。

    ⚠️ 本條同時涵蓋 `ui/tab3_portfolio.py`(本輪未修改該檔 —— 它原本就沒傳)。
    """
    _bad = [_n.lineno for _n in ast.walk(_tree(path))
            if isinstance(_n, ast.Call) and _fn_name(_n) == "render_ai_summary_widget"
            for _kw in _n.keywords if _kw.arg == "expanded"]
    assert not _bad, f"{path.name} 仍對共用 AI widget 傳 `expanded`(行 {_bad})"


# ══════════════════════════════════════════════════════════════
# 標題重複 — Tab① 原本同一句話連印三次
# ══════════════════════════════════════════════════════════════
def test_tab1_ai_section_title_is_printed_exactly_once() -> None:
    """**修正前必紅**(舊行為衝突):修正前 `ui/tab1_macro_ai.py` 自己就印了兩次
    逐字相同的「🤖 AI 景氣判斷總結」(一次 `##` 區塊標題、一次 `###`),
    加上 widget 自己的標題共三份。

    留下來的必須是**區塊級**那個 —— 三條早退路徑(未設 key / 紅燈阻斷 / L3 關閉)
    都靠它當標題,拿掉會變成沒有抬頭的一段警告。
    """
    _hits = [h for h in _md_headings(_TAB1_AI) if "AI 景氣判斷總結" in h]
    assert len(_hits) == 1, f"Tab① AI 區塊標題應恰好一處,實際 {_hits}"
    assert _heading_level(_hits[0]) == 2, (
        f"留下來的應是區塊級(兩個井號)那一個,實際 {_hits[0]!r}")
