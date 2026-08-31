"""③ 基金研究（個基深掘 + 批次分析）合併頁的守衛。

線框（客戶已拍板）：`docs/wireframes/fund-wireframe-final.html` §03「③ 🔍 基金研究」。

## 為什麼這一組測試長這樣（方法先講清楚）

本 repo 已實證過**字串比對型守衛會被檔案自己的說明文字騙過**
（`CLAUDE.md §8.2.A` EX-PASSTHRU-1 該列：docstring 裡出現 `import yfinance`
這幾個字，守衛就以為還在 import）。故本檔一律用兩種尺，**不用純字串 grep**：

1. **sentinel（行為）**：把底層換成記錄器，跑一次渲染，驗「有沒有真的被呼叫」。
   —— 用在「批次面板不准在 gate 之前被載入」這條最貴的規則上。
2. **AST（結構）**：驗某個呼叫是不是**真的**被包在某個條件式底下。
   —— 用在「子頁的第二個標題 / 第二份搜尋框必須被合併頁的旗標關掉」。

## 每一條的突變實驗（拿掉約束必須轉紅）寫在各自的 docstring 裡。
"""
from __future__ import annotations

import ast
import contextlib
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


# ══════════════════════════════════════════════════════════════════
# 假 streamlit：讓 render 函式可以在 fast lane 裡跑完（不需 AppTest）
# ══════════════════════════════════════════════════════════════════
class _Rec:
    """記錄這一次渲染送出了什麼。只記形狀，不做逐字斷言。"""

    def __init__(self) -> None:
        self.calls: list[tuple] = []          # (api, first_arg)
        self.session: dict = {}

    def api(self, name: str):
        def _f(*a, **k):
            self.calls.append((name, a[0] if a else None))
            return None
        return _f

    def names(self) -> list[str]:
        return [n for n, _ in self.calls]

    def args_of(self, name: str) -> list:
        return [a for n, a in self.calls if n == name]


class _Col:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@contextlib.contextmanager
def _fake_streamlit(monkeypatch, *, radio: str | None = None,
                    checkbox: bool = False, button: bool = False,
                    text: str = "", selectbox_index: int = 0):
    """把 `streamlit` 模組上會用到的 API 換成受控的假貨。

    ⚠️ patch 的是 **`streamlit` 模組物件本身**，所以
    `ui/tab_fund_research.py`、`ui/helpers/fund_research/code_finder.py`
    與 `ui/helpers/render_state.py` 三邊的 `import streamlit as st` 全部吃到同一份。
    """
    import streamlit as st

    rec = _Rec()
    for _n in ("markdown", "caption", "info", "success", "warning", "error",
               "divider", "write", "metric", "dataframe"):
        monkeypatch.setattr(st, _n, rec.api(_n), raising=False)
    monkeypatch.setattr(st, "columns", lambda spec, **k: [_Col() for _ in range(
        spec if isinstance(spec, int) else len(spec))], raising=False)
    monkeypatch.setattr(st, "spinner", lambda *a, **k: _Col(), raising=False)
    monkeypatch.setattr(st, "session_state", rec.session, raising=False)

    def _text_input(*a, **k):
        rec.calls.append(("text_input", a[0] if a else None))
        return text
    def _button(*a, **k):
        rec.calls.append(("button", a[0] if a else None))
        return button
    def _checkbox(*a, **k):
        rec.calls.append(("checkbox", a[0] if a else None))
        return checkbox
    def _radio(label, options, **k):
        rec.calls.append(("radio", tuple(options)))
        return radio if radio is not None else list(options)[0]
    def _selectbox(label, options, **k):
        rec.calls.append(("selectbox", label))
        return list(options)[selectbox_index]

    monkeypatch.setattr(st, "text_input", _text_input, raising=False)
    monkeypatch.setattr(st, "button", _button, raising=False)
    monkeypatch.setattr(st, "checkbox", _checkbox, raising=False)
    monkeypatch.setattr(st, "radio", _radio, raising=False)
    monkeypatch.setattr(st, "selectbox", _selectbox, raising=False)
    yield rec


@pytest.fixture()
def stub_modes(monkeypatch):
    """把兩個子頁換成記錄器 —— sentinel 的核心：驗「有沒有真的被呼叫」。"""
    import ui.tab2_single_fund as _t2
    import ui.tab_batch_analysis as _tb

    hits: dict = {"single": 0, "batch": 0}
    monkeypatch.setattr(_t2, "render_single_fund_tab",
                        lambda: hits.__setitem__("single", hits["single"] + 1))
    monkeypatch.setattr(_tb, "render_batch_analysis_tab",
                        lambda: hits.__setitem__("batch", hits["batch"] + 1))
    return hits


# ══════════════════════════════════════════════════════════════════
# 1) 最貴的一條：批次掃描不准在 gate 之前被載入
# ══════════════════════════════════════════════════════════════════
def test_batch_panel_is_not_loaded_before_the_gate(monkeypatch, stub_modes):
    """切到「📦 批次掃描」但**沒有勾** gate → 批次面板一行都不准跑。

    批次是全站唯一 30~40 分鐘的長任務（面板本身還會讀磁碟 checkpoint）。
    「一切換過來就開始做事」是本次合併最容易踩爆的地方。

    突變實驗（2026-08-28 實跑）：把 `_render_batch_mode()` 裡的
    `if not gate_on: … return` 兩行刪掉（面板無條件載入）→ **本條轉紅**
    （`batch == 1`）。恢復後轉綠。
    """
    from ui.tab_fund_research import MODE_BATCH, render_fund_research_tab

    with _fake_streamlit(monkeypatch, radio=MODE_BATCH, checkbox=False) as rec:
        render_fund_research_tab()

    assert stub_modes["batch"] == 0, "gate 還沒勾，批次面板就被載入了"
    assert stub_modes["single"] == 0, "選了批次模式卻跑了單檔模式"
    # 三態顏色：未載入是 ⬜ 灰色說明，不是紅色錯誤（線框 §03 顏色規則）。
    _greys = [a for a in rec.args_of("caption") if isinstance(a, str) and a.startswith("⬜")]
    assert _greys, "未載入狀態沒有任何 ⬜ 灰色說明 —— 使用者看不出來為什麼是空的"
    assert "error" not in rec.names(), "未載入被畫成紅色錯誤（過度示警）"


def test_batch_panel_loads_once_when_the_gate_is_on(monkeypatch, stub_modes):
    """勾了 gate → 面板**恰好**載入一次。

    這條擋的是反方向的壞掉：一個永遠打不開的 gate 也是 bug
    （只驗「沒被呼叫」會讓「把呼叫整段刪掉」也是綠的）。

    突變實驗（2026-08-28 實跑）：把 `_render_batch_mode()` 末尾的
    `render_batch_analysis_tab()` 呼叫刪掉 → **本條轉紅**（`batch == 0`）。
    """
    from ui.tab_fund_research import MODE_BATCH, render_fund_research_tab

    with _fake_streamlit(monkeypatch, radio=MODE_BATCH, checkbox=True):
        render_fund_research_tab()

    assert stub_modes["batch"] == 1
    assert stub_modes["single"] == 0


def test_default_mode_is_single_fund_not_batch(monkeypatch, stub_modes):
    """進入本頁的預設模式是「🔍 單檔深掘」—— 第一道防線。

    `radio=None` 時假 streamlit 回**選項清單的第一個**，模擬 Streamlit 的預設值。

    突變實驗（2026-08-28 實跑）：把 `st.radio` 的 options 順序對調成
    `(MODE_BATCH, MODE_SINGLE)` → **本條轉紅**（`single == 0` 且 `batch` 走進 gate 分支）。
    """
    from ui.tab_fund_research import MODE_SINGLE, render_fund_research_tab

    with _fake_streamlit(monkeypatch, radio=None) as rec:
        render_fund_research_tab()

    assert stub_modes["single"] == 1, "預設沒有進單檔深掘模式"
    assert stub_modes["batch"] == 0, "預設就碰到了批次面板"
    assert rec.args_of("radio") and rec.args_of("radio")[0][0] == MODE_SINGLE, (
        "模式切換的第一個選項不是「單檔深掘」—— Streamlit 會把它當預設值")


def test_mode_switch_is_one_toggle_not_a_second_layer_of_tabs():
    """線框原文：「**單一切換鍵**，切換的是下方版面。**不是第二層分頁**」。

    AST 驗：本檔恰好一個 `st.radio`，且**沒有** `st.tabs`。

    突變實驗（2026-08-28 實跑）：把 `st.radio(...)` 改成
    `st.tabs([MODE_SINGLE, MODE_BATCH])` → **本條轉紅**（radio 0 個、tabs 1 個）。
    """
    tree = ast.parse((ROOT / "ui" / "tab_fund_research.py").read_text(encoding="utf-8"))
    attrs = [n.func.attr for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)]
    assert attrs.count("radio") == 1, f"模式切換鍵不是恰好一個 radio：{attrs.count('radio')}"
    assert "tabs" not in attrs, "合併頁又長出第二層分頁（線框明文禁止）"


# ══════════════════════════════════════════════════════════════════
# 2) 共用頂部：子頁的第二份標題 / 第二份搜尋框必須被關掉
# ══════════════════════════════════════════════════════════════════
#: 檔案 → 該檔的「頁面 render 函式」。守衛只看這支函式裡面，
#: 免得同檔其他函式裡剛好有一個被保護的呼叫就讓斷言過關。
_PAGE_RENDERERS: dict = {
    "ui/tab2_single_fund.py": "render_single_fund_tab",
    "ui/tab_batch_analysis.py": "render_batch_analysis_tab",
}


def _st_calls_in_page_renderer(relpath: str):
    """回傳該檔 render 函式內每個 `st.<attr>(...)` 呼叫的
    `(attr, 第一個參數的原始碼, 是否被 `_merged_page_owns(...)` 守住)`。

    ⚠️ **為什麼要連「第一個參數」一起回傳**（2026-08-28 稽核補強，理由寫下來免得改回去）：
    本函式的第一版只回傳 attr 名，斷言寫成「`markdown` 有出現在被守住的呼叫裡」。
    那條斷言**擋不住真正會發生的那種壞法** —— 實測突變：把真正的 `## 標題`
    移出守衛、另外在守衛底下塞一個 `st.markdown("decoy")`，
    **兩個 parametrize case 全部照樣綠燈**（2026-08-28 實跑，`P1` / `P2`）。
    也就是舊斷言驗的是「有沒有人被守住」，不是「**該被守住的那一個**有沒有被守住」。
    現在改成把每個呼叫的第一個參數一起取出來，由呼叫端指名要驗哪一個。

    AST 而非字串：註解或 docstring 裡寫 `_merged_page_owns` 不會讓本函式誤判。

    ⚠️ **「被守住」必須連極性一起驗**（2026-08-31 第三方複驗補強，理由寫下來免得改回去）：
    本函式的第二版把「整個 If 底下的所有節點」都算成被守住 —— 不看 `not`。
    實測突變：把 `if not _merged_page_owns(...)` 的 `not` 拿掉（極性反轉）→
    舊入口（app.py 今天就掛著的那個）**整個少掉 `##` 標題**、合併頁反而畫兩份，
    而本檔 14 條 + `test_tab2_single_fund` + `test_app_apptest` **全部照樣綠燈**
    （2026-08-31 實跑）。那正是這組守衛要防的「無聲消失」，只是換了一個突變方向。
    現在只認「合併頁**沒**持有時才畫」的那個分支：
    `if not _merged_page_owns(...)` 的 body，或 `if _merged_page_owns(...)` 的 else。
    條件式若被改寫成本函式認不得的形狀（例如併進複合條件），對應呼叫會被視為
    未守住而轉紅 —— fail-closed，逼人回來看這裡，而不是安靜放行。
    """
    tree = ast.parse((ROOT / relpath).read_text(encoding="utf-8"))
    fname = _PAGE_RENDERERS[relpath]
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == fname)

    def _is_owns_call(c) -> bool:
        return (isinstance(c, ast.Call)
                and getattr(c.func, "id", "") == "_merged_page_owns")

    guarded_ids: set = set()
    for node in ast.walk(fn):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        if (isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not)
                and _is_owns_call(test.operand)):
            branch = node.body          # if not owns(...): <這裡是被守住的>
        elif _is_owns_call(test):
            branch = node.orelse        # if owns(...): ... else: <這裡才是被守住的>
        else:
            continue
        for stmt in branch:
            for sub in ast.walk(stmt):
                guarded_ids.add(id(sub))

    out: list[tuple] = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            # `ast.unparse` 而非 `get_source_segment`：後者每次都要重切整份原始碼，
            # 在 2,700 行的 tab2 上會把這條測試從 0.3 秒拖到 15 秒。
            arg0 = ast.unparse(node.args[0]) if node.args else ""
            out.append((node.func.attr, arg0, id(node) in guarded_ids))
    return out


def _is_h2(arg_src: str) -> bool:
    """這個 `st.markdown` 的第一個參數是不是**頁面大標**（恰好兩個 `#`）？

    `ast.unparse` 後長這樣：`f'## {_tab_label_t2(\'fund\')}'` / `'### ① 基本資料'`。
    先剝掉 f 前綴與引號，再看是不是 `## ` 開頭（`###` 以下是區塊小標，不算）。
    """
    _t = arg_src.lstrip()
    while _t[:1] in ("f", "F", "r", "R", "b", "B"):
        _t = _t[1:]
    _t = _t.lstrip("\"'")
    return _t.startswith("## ")


@pytest.mark.parametrize("relpath", ["ui/tab2_single_fund.py",
                                     "ui/tab_batch_analysis.py"])
def test_sub_page_h2_title_is_behind_the_merge_guard(relpath):
    """合併頁自己畫大標時，子頁不准再畫第二個 `##`。

    驗的是「**該檔 render 函式內的每一個 `## ` 大標**都在守衛底下」，
    不是「有某個 markdown 在守衛底下」—— 後者擋不住「守錯人」那種壞法（見
    `_st_calls_in_page_renderer` 的 docstring，那裡記了實測會漏掉的突變）。

    突變實驗（2026-08-28 實跑）：
    - M5a/M5b：拿掉 `if not _merged_page_owns(_MERGED_PAGE_HEADER):` → **轉紅**（兩檔各一次）。
    - P1/P2（稽核加驗）：標題移出守衛、守衛底下改塞 `st.markdown("decoy")`
      → 舊斷言**綠燈**（漏掉）、本版**轉紅**。
    """
    _h2 = [(a, g) for attr, a, g in _st_calls_in_page_renderer(relpath)
           if attr == "markdown" and _is_h2(a)]
    # 先擋「標題被改名/刪掉 → 0 個 case 也算通過」這種無聲消失。
    assert _h2, f"{relpath} 的 render 函式裡找不到任何 `## ` 頁面大標 —— 斷言失去對象"
    _unguarded = [a for a, g in _h2 if not g]
    assert not _unguarded, (
        f"{relpath} 的頁面大標沒有被合併頁旗標保護 —— 合併後會出現兩個 `##` 標題："
        f"{_unguarded}")


def test_single_fund_keyword_search_is_behind_the_merge_guard():
    """「找代號」工具在合併頁升為共用頂部 → 子頁那份摺疊版必須被關掉。

    突變實驗（2026-08-28 實跑）：把 `if not _merged_page_owns(_MERGED_SHARED_SEARCH):`
    拿掉、expander 拉回原縮排 → **本條轉紅**（`expander` 不在被保護的呼叫裡）。
    """
    _calls = _st_calls_in_page_renderer("ui/tab2_single_fund.py")
    _search_expanders = [(a, g) for attr, a, g in _calls
                         if attr == "expander" and "關鍵字搜尋" in a]
    assert _search_expanders, (
        "找不到「關鍵字搜尋」的 expander —— 斷言失去對象（改名了？）")
    _unguarded = [a for a, g in _search_expanders if not g]
    assert not _unguarded, (
        f"個基深掘的關鍵字搜尋沒有被合併頁旗標保護 —— 合併後畫面上會有兩份搜尋框：{_unguarded}")
    # 搜尋框本體（輸入框 + 按鈕）也必須跟著被關掉，不能只關外層 expander。
    assert any(attr == "text_input" and g for attr, _a, g in _calls), (
        "關鍵字輸入框沒有被守住")


def test_merge_context_flag_is_scoped_and_restored_even_on_error():
    """旗標只在 context 內成立，例外路徑也要還原。

    沒有這條，`render_single_fund_tab()` 一旦中途丟例外，旗標會留在「合併頁持有」，
    **舊入口從此少掉標題**而沒有人知道。

    突變實驗（2026-08-28 實跑）：把 `merged_page_owns` 的 `try/finally` 拆成
    直接 `yield` + 之後還原（不用 finally）→ **本條轉紅**（例外後仍為 True）。
    """
    from ui.helpers.fund_research.merge_context import (
        PAGE_HEADER, merged_page_owns, owned_by_merged_page,
    )

    assert owned_by_merged_page(PAGE_HEADER) is False
    with pytest.raises(RuntimeError):
        with merged_page_owns(PAGE_HEADER):
            assert owned_by_merged_page(PAGE_HEADER) is True
            raise RuntimeError("boom")
    assert owned_by_merged_page(PAGE_HEADER) is False, "例外之後旗標沒有還原"


def test_merge_context_flag_does_not_leak_across_threads():
    """旗標必須是**每條執行緒各一份** —— 這是 2026-08-28 稽核抓到的真缺陷的守衛。

    為什麼這條非有不可（原設計為什麼會壞）
    --------------------------------------
    旗標原本是模組層 `set()`，理由寫的是「Streamlit 一次 rerun 是單執行緒由上而下跑完」。
    那句話**只在同一個 session 內成立**：Streamlit 是**一個 process、每個 session 一條
    ScriptRunner 執行緒**，模組層變數因此跨 session 共用。於是 session A 停在
    `merged_page_owns(...)` 區塊內（該區塊涵蓋整支 `render_single_fund_tab()`，
    含網路抓取，可以跑好幾秒）時，session B 從**舊入口**進同一支函式 → 讀到 A 的旗標 →
    **B 的頁面大標與搜尋框無聲消失**。

    突變實驗（2026-08-28 實跑）：把 `_STATE = threading.local()` / `_owned()` 改回
    模組層 `_OWNED: set = set()` → **本條轉紅**（另一條執行緒看到 True）。
    """
    import threading

    from ui.helpers.fund_research.merge_context import (
        PAGE_HEADER, merged_page_owns, owned_by_merged_page,
    )

    _entered, _may_exit = threading.Event(), threading.Event()
    seen_from_other_thread: list = []

    def _holder() -> None:
        with merged_page_owns(PAGE_HEADER):
            _entered.set()
            _may_exit.wait(timeout=5)

    t = threading.Thread(target=_holder, daemon=True)
    t.start()
    try:
        assert _entered.wait(timeout=5), "持有旗標的執行緒沒有起來"
        # 另一條執行緒（＝另一個 Streamlit session）此刻正持有旗標；本執行緒不該看見。
        seen_from_other_thread.append(owned_by_merged_page(PAGE_HEADER))
    finally:
        _may_exit.set()
        t.join(timeout=5)

    assert seen_from_other_thread == [False], (
        "合併頁的所有權旗標跨執行緒外洩 —— 另一個 session 的舊入口會無聲少掉標題與搜尋框")


def test_merge_context_rejects_unknown_part_names():
    """打錯字要當場炸掉，不要安靜回 False（§1 Fail Loud）。

    突變實驗（2026-08-28 實跑）：把 `_validate()` 的 raise 改成 `return` →
    **本條轉紅**（不再拋 ValueError）。
    """
    from ui.helpers.fund_research.merge_context import owned_by_merged_page

    with pytest.raises(ValueError):
        owned_by_merged_page("no_such_part")


# ══════════════════════════════════════════════════════════════════
# 3) §1 Fail Loud：找代號工具的失敗不准被吞
# ══════════════════════════════════════════════════════════════════
def test_code_finder_reports_fetch_failure_as_a_system_error(monkeypatch):
    """搜尋抓取失敗 → 紅色系統錯誤，**不得**寫入假清單、不得吞掉。

    突變實驗（2026-08-28 實跑）：把 `_search()` 的 `except` body 改成
    `pass`（吞掉）→ **本條轉紅**（`system_error` 未被呼叫）。
    另一組突變：改成 `st.session_state[RESULTS_KEY] = []` 假裝查無結果 →
    **也轉紅**（session 被寫了東西）。
    """
    import repositories.fund as _rf
    import ui.helpers.fund_research.code_finder as _cf

    def _boom(_kw):
        raise RuntimeError("upstream 503")

    monkeypatch.setattr(_rf, "tdcc_search_fund", _boom, raising=False)
    seen: list = []
    monkeypatch.setattr(_cf, "system_error",
                        lambda what, exc, **k: seen.append((what, exc)))

    with _fake_streamlit(monkeypatch, text="安聯", button=True) as rec:
        _cf.render_code_finder()

    assert seen, "搜尋失敗沒有走系統紅燈 —— 使用者會以為只是查無結果"
    assert isinstance(seen[0][1], RuntimeError)
    assert _cf.RESULTS_KEY not in rec.session, "失敗竟然寫了一份（空的）結果進 session"


def test_code_finder_failure_marks_previous_results_as_stale(monkeypatch):
    """搜尋失敗時**保留**上一次的結果是刻意的（清掉等於沒收使用者已經查到的東西），
    但那份清單會原樣留在下方、標題還寫「選擇基金（N 筆）」—— 看起來就像**這次**搜出來的。

    §2.4：過期資料可以回，但**必須帶 is_stale 旗標**；§1：不得讓畫面看起來像成功。
    旗標寫進既有的紅框 `hint`（使用者此刻正在看的地方），不新增視覺語彙。

    突變實驗（2026-08-28 實跑）：把 `_search()` except 分支裡的 `_stale` 判斷拿掉、
    hint 改回原本的固定字串 → **本條轉紅**（hint 沒有提到那是上一次的結果）。
    """
    import repositories.fund as _rf
    import ui.helpers.fund_research.code_finder as _cf

    monkeypatch.setattr(_rf, "tdcc_search_fund",
                        lambda _kw: (_ for _ in ()).throw(RuntimeError("upstream 503")),
                        raising=False)
    kwargs_seen: list = []
    monkeypatch.setattr(_cf, "system_error",
                        lambda what, exc, **k: kwargs_seen.append(k))

    with _fake_streamlit(monkeypatch, text="安聯", button=True) as rec:
        # 上一次成功搜尋留下來的兩筆
        rec.session[_cf.RESULTS_KEY] = [
            {"基金名稱": "舊的一檔", "基金代碼": "OLD1"},
            {"基金名稱": "舊的二檔", "基金代碼": "OLD2"},
        ]
        _cf.render_code_finder()

    assert kwargs_seen, "失敗沒有走 system_error"
    _hint = kwargs_seen[0].get("hint", "")
    assert "上一次" in _hint, (
        "紅框沒有講明下方那份清單是上一次的結果 —— 使用者會以為那是這次搜到的（§2.4 is_stale）")
    assert "2" in _hint, "沒有講清楚是幾筆過期資料"


def test_code_finder_not_searched_yet_is_grey_not_red(monkeypatch):
    """還沒搜尋 = ⬜ 灰色說明，不是紅色 / 橘色警示（線框 §03 三態規則）。

    突變實驗（2026-08-28 實跑）：把 `not_ready(...)` 換成 `st.error(...)` →
    **本條轉紅**（出現 `error` 呼叫、且沒有 ⬜ caption）。
    """
    import ui.helpers.fund_research.code_finder as _cf

    with _fake_streamlit(monkeypatch, button=False) as rec:
        _cf.render_code_finder()

    assert any(isinstance(a, str) and a.startswith("⬜") for a in rec.args_of("caption")), (
        "「還沒搜尋」沒有灰色說明")
    assert "error" not in rec.names() and "warning" not in rec.names(), (
        "「還沒搜尋」被畫成警示色（過度示警）")


# ══════════════════════════════════════════════════════════════════
# 4) 合併頁只是版面 —— 不准在這裡動計算 / 動取數
# ══════════════════════════════════════════════════════════════════
def test_merged_page_module_does_not_reach_into_data_or_compute_layers():
    """本次是**版面合併**，不是計算改動：合併頁自己不得 import L1/L2。

    （共用頂部的取數住在 `ui/helpers/fund_research/code_finder.py`，
    那是 EX-PASSTHRU-1 形態的 UI→L1 直呼，已在該檔 docstring 具名揭露。）

    突變實驗（2026-08-28 實跑）：在 `ui/tab_fund_research.py` 加一行
    `from services.fund_service import get_latest_fx` → **本條轉紅**。
    """
    tree = ast.parse((ROOT / "ui" / "tab_fund_research.py").read_text(encoding="utf-8"))
    bad = []
    for node in ast.walk(tree):
        mods = []
        if isinstance(node, ast.ImportFrom) and node.module:
            mods = [node.module]
        elif isinstance(node, ast.Import):
            mods = [a.name for a in node.names]
        bad += [m for m in mods
                if m.split(".")[0] in {"repositories", "services", "infra"}]
    assert not bad, f"合併頁自己去碰了資料 / 計算層：{sorted(set(bad))}"
