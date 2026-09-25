# -*- coding: utf-8 -*-
"""ui_v2 測試的 lane 與瀏覽器守衛（fast lane；不需要 streamlit、不需要瀏覽器）。

客戶 2026-09-25 裁示：
- `tests/ui_v2/test_*_page.py` 整檔標 slow，fast lane（pre-commit 的 `pytest -m "not slow"`）不跑；
  `test_*_logic.py` 維持 fast。
- 瀏覽器測試不寫死路徑：環境變數 `UI_V2_CHROMIUM` 或 playwright 預設解析；
  CI（`CI=true`）找不到瀏覽器要 fail，本機找不到 skip。
- CI slow lane 要裝 chromium，且 pytest 指令收得到 tests/ui_v2 的 slow 測試。
"""

import ast
import pathlib
import re
import sys

import pytest

_HERE = pathlib.Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
sys.path.insert(0, str(_HERE))

import _ui_v2_chromium  # noqa: E402

_PAGE_TESTS = sorted(_HERE.glob("test_*_page.py"))
_LOGIC_TESTS = sorted(_HERE.glob("test_*_logic.py"))


def _module_pytestmark(path):
    """回傳模組層 `pytestmark = ...` 右邊的原始碼字串；沒有就回 None。"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "pytestmark" for t in node.targets
        ):
            return ast.unparse(node.value)
    return None


def test_畫面測試檔每一支都整檔標slow():
    assert len(_PAGE_TESTS) >= 5, _PAGE_TESTS  # 空掃防呆：五頁各一支
    for path in _PAGE_TESTS:
        assert _module_pytestmark(path) == "pytest.mark.slow", path.name


def test_logic測試檔維持fast_沒有整檔標slow():
    assert len(_LOGIC_TESTS) >= 5, _LOGIC_TESTS
    for path in _LOGIC_TESTS:
        mark = _module_pytestmark(path)
        assert mark is None or "slow" not in mark, path.name


def test_tests底下不寫死瀏覽器路徑():
    # 字面刻意拆開組，免得本檔自己命中。
    needles = ("/opt/" + "pw-browsers", "chrome-" + "linux/chrome")
    scanned = 0
    for path in (_ROOT / "tests").rglob("*.py"):
        scanned += 1
        text = path.read_text(encoding="utf-8", errors="replace")
        for needle in needles:
            assert needle not in text, (path.relative_to(_ROOT), needle)
    assert scanned > 20, scanned  # 空掃防呆


def test_瀏覽器測試走共用解析_不自己帶執行檔路徑():
    users = [p for p in _PAGE_TESTS if "browser_page" in p.read_text(encoding="utf-8")]
    assert len(users) >= 2, users  # alo、set
    for path in users:
        text = path.read_text(encoding="utf-8")
        assert "_ui_v2_chromium.launch(" in text, path.name
        assert "_ui_v2_chromium.import_sync_api()" in text, path.name
        assert "executable_path" not in text, path.name


class _FakeChromium:
    def __init__(self, error=None):
        self.error = error
        self.calls = []

    def launch(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return "browser"


class _FakePlaywright:
    def __init__(self, error=None):
        self.chromium = _FakeChromium(error)


def _raised_by(call):
    """先用 BaseException 接住 —— 若實作退化成 skip，Skipped 例外不能穿出去把本守衛自己變成 SKIPPED。"""
    with pytest.raises(BaseException) as info:
        call()
    return info.value


def _assert_is_fail_not_skip(exc):
    assert isinstance(exc, pytest.fail.Exception), type(exc)
    assert not isinstance(exc, pytest.skip.Exception), type(exc)


def test_CI為true時in_ci為真():
    import os

    saved = os.environ.get("CI")
    try:
        os.environ["CI"] = "true"
        assert _ui_v2_chromium.in_ci() is True
        os.environ.pop("CI")
        assert _ui_v2_chromium.in_ci() is False
    finally:
        if saved is None:
            os.environ.pop("CI", None)
        else:
            os.environ["CI"] = saved


def test_CI上瀏覽器找不到是fail不是skip(monkeypatch, tmp_path):
    monkeypatch.setenv("CI", "true")
    monkeypatch.setenv(_ui_v2_chromium.ENV_VAR, str(tmp_path / "no-such-chrome"))
    _assert_is_fail_not_skip(_raised_by(lambda: _ui_v2_chromium.launch(_FakePlaywright())))
    monkeypatch.delenv(_ui_v2_chromium.ENV_VAR)
    _assert_is_fail_not_skip(_raised_by(
        lambda: _ui_v2_chromium.launch(_FakePlaywright(RuntimeError("Executable doesn't exist")))
    ))
    _assert_is_fail_not_skip(_raised_by(lambda: _ui_v2_chromium.unavailable("匯入不到 playwright")))


def test_本機瀏覽器找不到是skip(monkeypatch, tmp_path):
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setenv(_ui_v2_chromium.ENV_VAR, str(tmp_path / "no-such-chrome"))
    with pytest.raises(pytest.skip.Exception):
        _ui_v2_chromium.launch(_FakePlaywright())
    monkeypatch.delenv(_ui_v2_chromium.ENV_VAR)
    with pytest.raises(pytest.skip.Exception):
        _ui_v2_chromium.launch(_FakePlaywright(RuntimeError("Executable doesn't exist")))


def test_有環境變數就用它_沒有就交給playwright預設解析(monkeypatch, tmp_path):
    fake_exe = tmp_path / "chrome"
    fake_exe.write_text("")
    monkeypatch.setenv(_ui_v2_chromium.ENV_VAR, str(fake_exe))
    pw = _FakePlaywright()
    _ui_v2_chromium.launch(pw)
    assert pw.chromium.calls == [{"executable_path": str(fake_exe)}]
    monkeypatch.delenv(_ui_v2_chromium.ENV_VAR)
    pw = _FakePlaywright()
    _ui_v2_chromium.launch(pw)
    assert pw.chromium.calls == [{}]


def _slow_job_block():
    text = (_ROOT / ".github" / "workflows" / "pr-check.yml").read_text(encoding="utf-8")
    match = re.search(r"^  slow-tests:\n(.*?)(?=^  [A-Za-z0-9_-]+:\n|\Z)", text, re.M | re.S)
    assert match, "pr-check.yml 找不到 slow-tests job"
    return match.group(1)


def test_CI_slow_lane裝chromium_而且pytest指令收得到ui_v2的slow測試():
    block = _slow_job_block()
    assert "python -m playwright install --with-deps chromium" in block
    runs = re.findall(r"^\s*run:\s*(python -m pytest[^\n]*)$", block, re.M)
    assert runs, block
    for run in runs:
        assert '-m "slow"' in run, run
        # 不帶路徑參數 → 從 repo 根收集，tests/ui_v2 在範圍內；帶了路徑就必須含 tests/ui_v2 或 tests。
        paths = [tok for tok in run.split() if tok.startswith("tests")]
        assert not paths or any(p.rstrip("/") in ("tests", "tests/ui_v2") for p in paths), run
    # 安裝瀏覽器那一步要在跑 pytest 之前
    assert block.index("playwright install") < block.index("python -m pytest")


def test_playwright在requirements_dev裡():
    lines = (_ROOT / "requirements-dev.txt").read_text(encoding="utf-8").splitlines()
    assert any(re.match(r"^playwright\b", line.strip()) for line in lines)
