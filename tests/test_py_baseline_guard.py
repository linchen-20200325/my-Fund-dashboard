# -*- coding: utf-8 -*-
"""`tests/_py_baseline_guard.py`（CPython 版本守衛）的自測。純 Python；在 3.11（CI）與 3.12+（本機）行為相同。

涵蓋：(1) `decide` 三分支；(2) 裝飾器在 run／skip／fail 三種情況的實際行為（以假造的版本／環境變數）；
(3) 基準常數與黃金檔檔頭交叉驗證；(4) 10 條受影響測試「真的掛上了守衛」（AST，防日後被悄悄拿掉）。
"""

from __future__ import annotations

import ast
import json
import pathlib
import sys

import pytest

import _py_baseline_guard as guard

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_GOLDEN = _ROOT / "tests" / "fixtures" / "alo_core_golden_before.json"

#: 受 CPython float sum() 補償加總影響、被掛上守衛的測試（檔案 → 測試函式名）。
GUARDED = {
    "tests/test_alo_core_golden.py": [
        "test_整份矩陣_工作樹與黃金檔逐位元組相同",
        "test_逐情境相同",
        "test_額外對照_從git歷史的基準原始碼重算_等於黃金檔",
    ],
    "tests/test_alo_core_golden_mutations.py": [
        "test_對照組_未突變的載入器重現黃金檔",
        "test_突變被黃金檔抓到",   # 非基準版本時 `assert differ` 會因基準本身就不同而空泛為真（假綠燈）
    ],
    "tests/ui_v2/test_hld_logic.py": [
        "test_第2件反向控制_十二情境乘九塊一百零八格逐格未變",
        "test_第2件_三個新情境的整頁模型逐格釘住",
    ],
    "tests/ui_v2/test_hld_read_failure_logic.py": [
        "test_T2c正_十七個情境_示範與正式模式共389個模型_與改動前相同",
        "test_空白套用d反_設定讀得到_清空再套用照舊說未設定_本條修正不改這些頁面",
    ],
    "tests/ui_v2/test_rulings_2026_10_18b_logic.py": ["test_示範模式_持倉體檢與標的探索全情境模型_md5與動手前相同"],
}


# ═══════════════════════ decide：純函式三分支 ═══════════════════════


@pytest.mark.parametrize("py,ci,want", [
    ((3, 11), True, "run"),
    ((3, 11), False, "run"),
    ((3, 11, 18), True, "run"),          # 只看 (major, minor)
    ((3, 13), False, "skip"),
    ((3, 12), False, "skip"),
    ((3, 10), False, "skip"),
    ((3, 13), True, "fail"),             # tripwire：CI 非基準 ⇒ 失敗，不是 skip
    ((3, 12, 3), True, "fail"),
    ((3, 14), True, "fail"),
    ((2, 11), False, "skip"),
])
def test_decide_三分支(py, ci, want):
    assert guard.decide(py, ci) == want


def test_decide_基準可覆寫_且比對只看前兩碼():
    assert guard.decide((3, 13, 1), False, baseline=(3, 13, 9)) == "run"
    assert guard.decide((3, 11), True, baseline=(3, 13)) == "fail"


def test_ci_判定_只認_GITHUB_ACTIONS_等於字串true():
    assert guard.is_ci({"GITHUB_ACTIONS": "true"}) is True
    assert guard.is_ci({"GITHUB_ACTIONS": "false"}) is False
    assert guard.is_ci({"GITHUB_ACTIONS": "True"}) is False
    assert guard.is_ci({"CI": "true"}) is False
    assert guard.is_ci({}) is False


def test_is_ci_預設讀_os_environ(monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    assert guard.is_ci() is True
    monkeypatch.delenv("GITHUB_ACTIONS")
    assert guard.is_ci() is False


def test_current_python_讀_sys_version_info_前兩碼(monkeypatch):
    assert guard.current_python() == (sys.version_info[0], sys.version_info[1])
    real = sys.version_info
    monkeypatch.setattr(sys, "version_info", (3, 9, 1, "final", 0))
    try:
        got = guard.current_python()
    finally:
        monkeypatch.setattr(sys, "version_info", real)
    assert got == (3, 9)


# ═══════════════════════ 裝飾器：run／skip／fail 的實際行為 ═══════════════════════


def _make_target(calls):
    @guard.baseline_python_only
    def target(x, y=2):
        calls.append((x, y))
        return x + y
    return target


def test_裝飾器_基準版本_照跑且原樣回傳(monkeypatch):
    monkeypatch.setattr(guard, "current_python", lambda: (3, 11))
    for ci in ("true", "false"):
        monkeypatch.setenv("GITHUB_ACTIONS", ci)
        calls = []
        assert _make_target(calls)(1, y=5) == 6
        assert calls == [(1, 5)]


def test_裝飾器_非基準且非CI_skip_原因點名BL與sum補償加總(monkeypatch):
    monkeypatch.setattr(guard, "current_python", lambda: (3, 13))
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    calls = []
    with pytest.raises(pytest.skip.Exception) as ei:
        _make_target(calls)(1)
    assert calls == []   # 測試本體完全沒被執行
    msg = str(ei.value)
    assert "BL-0342" in msg and "BL-0453" in msg
    assert "3.11" in msg and "3.13" in msg and "sum()" in msg and "補償加總" in msg
    assert "不得重錄 Golden" in msg


def test_裝飾器_非基準且在CI_fail不是skip(monkeypatch):
    monkeypatch.setattr(guard, "current_python", lambda: (3, 12))
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    calls = []
    try:
        _make_target(calls)(1)
    except pytest.skip.Exception as exc:     # tripwire 被降級成 skip 時，必須是「這個測試失敗」，不是「這個測試也跟著 skip」
        raise AssertionError("tripwire 被降級成 skip") from exc
    except pytest.fail.Exception as exc:
        msg = str(exc)
    else:
        raise AssertionError("tripwire 沒有失敗，測試本體被執行了")
    assert calls == []
    assert "tripwire" in msg and "Decision Gate" in msg and "BL-0342" in msg


def test_裝飾器_保留簽名與名稱_pytest_參數化仍可用():
    import inspect
    calls = []
    t = _make_target(calls)
    assert t.__name__ == "target"
    assert list(inspect.signature(t).parameters) == ["x", "y"]
    assert getattr(t, "__baseline_python_only__", False) is True


# ═══════════════════════ 與黃金檔檔頭交叉驗證；受影響測試確實掛上守衛 ═══════════════════════


def test_基準常數與黃金檔檔頭python一致():
    header_python = json.loads(_GOLDEN.read_text(encoding="utf-8"))["header"]["python"]
    major, minor = (int(x) for x in header_python.split(".")[:2])
    assert (major, minor) == guard.BASELINE_PYTHON


def _decorator_names(fn: ast.FunctionDef) -> set[str]:
    out = set()
    for d in fn.decorator_list:
        node = d.func if isinstance(d, ast.Call) else d
        if isinstance(node, ast.Name):
            out.add(node.id)
        elif isinstance(node, ast.Attribute):
            out.add(node.attr)
    return out


@pytest.mark.parametrize("rel", sorted(GUARDED))
def test_受影響測試_全部掛上baseline_python_only(rel):
    tree = ast.parse((_ROOT / rel).read_text(encoding="utf-8"))
    funcs = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    for name in GUARDED[rel]:
        assert name in funcs, f"{rel}::{name} 不存在（改名了？同步更新本檔 GUARDED）"
        assert "baseline_python_only" in _decorator_names(funcs[name]), f"{rel}::{name} 沒有 @baseline_python_only"


def test_守衛名單_不含黃金檔本身的sha與檔頭等與版本無關的測試():
    """負向：與 Python 版本無關的 Golden 測試（sha256 釘死、檔頭、防空掃…）不得被掛上守衛，以免無端失去 3.12+ 上的保護。"""
    tree = ast.parse((_ROOT / "tests/test_alo_core_golden.py").read_text(encoding="utf-8"))
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name.startswith("test_") and n.name not in GUARDED["tests/test_alo_core_golden.py"]:
            assert "baseline_python_only" not in _decorator_names(n), n.name
