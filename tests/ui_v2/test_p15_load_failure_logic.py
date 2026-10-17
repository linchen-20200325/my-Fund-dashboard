# -*- coding: utf-8 -*-
"""Phase 3 P1-⑤（BL-0362）：正式模式 `load_live()` 拋例外時的純函式與靜態守衛（fast lane；不需要 streamlit）。

- `ui_v2/health.py::load_failure_line`：原文那一行「⛔ 取數失敗：<型別>：<遮蔽後訊息>」；沒有遮蔽函式、遮蔽壞了、
  `str(exc)` 壞了 ⇒ 只寫型別、不帶任何訊息內容（沒有遮蔽過的原文不收進進階診斷）。
- `ui_v2/plain.py::clear_raw`：只拿掉指定那一頁的原始訊息；沒有那一筆就一個字都不寫。
- 靜態守衛：市場總覽、標的探索、資產配置、設定與診斷、持倉體檢五頁的 `page.py` 裡，每一處 `load_live()` 呼叫都在
  一個接 `Exception` 的 `try` 裡（BL-0362：原本四頁沒有包，正式頁畫出帶堆疊的例外框）。
- 靜態守衛：`ui_v2/health_view.py::render_load_failure` 不碰任何讀寫（護欄 3：附帶的導覽只換頁）。
"""

import ast
import pathlib
import sys

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

from ui_v2 import health, plain  # noqa: E402

_SECRET = "zz-fake-secret-p15"
_MASK = "‹已遮蔽›"


def _fft(message):
    return "⛔ 取數失敗：" + message


def _mask(message):
    return message.replace(_SECRET, _MASK)


# ───────────────────────── load_failure_line ─────────────────────────


def test_有遮蔽函式_型別與遮蔽後訊息都在():
    line = health.load_failure_line(RuntimeError(f"上游讀取失敗 token={_SECRET}"), _mask, _fft)
    assert line == f"⛔ 取數失敗：RuntimeError：上游讀取失敗 token={_MASK}"


def test_型別名也經過遮蔽():
    exc = type(f"Err{_SECRET}", (Exception,), {})("x")
    line = health.load_failure_line(exc, _mask, _fft)
    assert _SECRET not in line and f"Err{_MASK}：x" in line


@pytest.mark.parametrize("mask", [None, lambda s: 1 / 0, lambda s: None], ids=["沒有遮蔽函式", "遮蔽拋例外", "遮蔽回非字串"])
def test_退路_只寫型別_不帶任何訊息內容(mask):
    line = health.load_failure_line(RuntimeError(f"上游讀取失敗 token={_SECRET}"), mask, _fft)
    assert line == "⛔ 取數失敗：RuntimeError"


def test_退路_str本身拋例外_只寫型別_不往外拋():
    class BadStr(Exception):
        def __str__(self):
            raise RuntimeError(f"str 也壞了 {_SECRET}")

    assert health.load_failure_line(BadStr(), _mask, _fft) == "⛔ 取數失敗：BadStr"


def test_模板取自呼叫端交的那一個函式_本模組不另寫一份():
    assert health.load_failure_line(ValueError("v"), _mask, lambda m: f"<{m}>") == "<ValueError：v>"


def test_各頁的取數失敗模板都是同一個字首():
    """呼叫端交的是各頁 `logic.fetch_failed_text`；一般畫面那一句（`plain.plain_error_line`）認的是這個字首。"""
    from ui_v2.alo import logic as alo
    from ui_v2.exp import logic as exp
    from ui_v2.mkt import logic as mkt
    from ui_v2.set import logic as set_logic

    for logic in (mkt, exp, alo, set_logic):
        assert logic.fetch_failed_text("x") == plain.FETCH_FAIL_PREFIX + "x", logic.__name__


def test_市場總覽的頁名與提問句抽成常數_字面沒有變():
    from ui_v2.mkt import fixtures, logic

    model = logic.build_page_model(fixtures.dataset_all_ok())
    assert (model["title"], model["answers"]) == (logic.PAGE_TITLE, logic.PAGE_ANSWERS)
    assert logic.PAGE_TITLE == "市場總覽"
    assert logic.PAGE_ANSWERS == "現在的市場環境，和我上次看的時候比，變了哪裡"


# ───────────────────────── clear_raw ─────────────────────────


def test_clear_raw_只拿掉那一頁():
    state = {}
    plain.record_raw(state, "set", [{"where": "設定與診斷", "text": "a"}], "t1")
    plain.record_raw(state, "mkt", [], "t2")
    plain.clear_raw(state, "set")
    assert list(state[plain.RAW_STATE]) == ["mkt"]


def test_clear_raw_沒有那一筆_一個字都不寫():
    state = {}
    plain.clear_raw(state, "set")
    assert state == {}
    plain.record_raw(state, "mkt", [], "t")
    before = dict(state[plain.RAW_STATE])
    plain.clear_raw(state, "set")
    assert state[plain.RAW_STATE] == before


# ───────────────────────── 靜態守衛：每一處 load_live() 都在接 Exception 的 try 裡 ─────────────────────────

_PAGES = ("mkt", "hld", "exp", "alo", "set")


def _load_live_calls_outside_try(tree):
    """回 `load_live()` 呼叫中，**沒有**被「handler 接 `Exception`（或更寬）的 `try` 本體」包住的那幾處行號。"""
    parents = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node

    def catches_exception(handler):
        return handler.type is None or ast.unparse(handler.type) in ("Exception", "BaseException")

    bad, total = [], 0
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "load_live"):
            continue
        total += 1
        child, parent, ok = node, parents.get(node), False
        while parent is not None:
            if isinstance(parent, ast.Try) and child in parent.body and any(
                    catches_exception(h) for h in parent.handlers):
                ok = True
                break
            child, parent = parent, parents.get(parent)
        if not ok:
            bad.append(node.lineno)
    return total, bad


@pytest.mark.parametrize("page", _PAGES)
def test_五頁每一處load_live呼叫都在接Exception的try裡(page):
    tree = ast.parse((_ROOT / "ui_v2" / page / "page.py").read_text(encoding="utf-8"))
    total, bad = _load_live_calls_outside_try(tree)
    assert total >= 1, (page, "空掃：本頁沒有找到 load_live() 呼叫")
    assert bad == [], (page, bad)


@pytest.mark.parametrize("code, ok", [
    ("def f(load_live):\n    x = load_live()\n", False),
    ("def f(load_live):\n    try:\n        x = load_live()\n    except ValueError:\n        pass\n", False),
    ("def f(load_live):\n    try:\n        x = load_live()\n    except Exception:\n        pass\n", True),
    ("def f(load_live):\n    try:\n        pass\n    except Exception:\n        x = load_live()\n", False),
])
def test_正控_守衛分得出有沒有包(code, ok):
    total, bad = _load_live_calls_outside_try(ast.parse(code))
    assert total == 1 and (bad == []) is ok


def test_整頁錯誤畫面不碰任何讀寫():
    """護欄 3：錯誤畫面附帶的「前往設定與診斷」只換頁；畫錯誤畫面本身也不存檔、不重新取數、不重跑。"""
    path = _ROOT / "ui_v2" / "health_view.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "render_load_failure")
    calls = {ast.unparse(c.func) for c in ast.walk(fn) if isinstance(c, ast.Call)}
    assert {c for c in calls if c.startswith("st.")} == {"st.markdown"}, calls
    assert "render_settings_link" in calls
    body = ast.get_source_segment(path.read_text(encoding="utf-8"), fn)
    code = body.split('"""', 2)[2]   # 不看 docstring
    for word in ("save", "refetch", "load_live", "button", "rerun", "switch_page", "cache"):
        assert word not in code, word
