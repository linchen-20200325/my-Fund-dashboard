# -*- coding: utf-8 -*-
"""Visual Fidelity 設定與 layout 檢查判定的單元測試（BL-0525 Batch A；fast lane，不需要瀏覽器、不需要 streamlit）。"""

from __future__ import annotations

import ast
import pathlib
import re
import sys

import pytest

_HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

import config  # noqa: E402
import layout_checks as LC  # noqa: E402


def _measure(**over):
    base = {
        "viewport": {"width": 390, "height": 844},
        "main_width": 358,
        "exceptions": 0, "code_blocks": 0,
        "doc_overflow": {"scroll": 390, "client": 390},
        "main_overflow": {"scroll": 390, "client": 390},
        "charts": [{"top": 200, "height": 260, "width": 350, "collapsed": False}],
        "chips_groups": [4, 3],
        "first_screen_chips": 4,
        "open_details": 0,
    }
    base.update(over)
    return base


def _by_id(results):
    return {r["id"]: r for r in results}


def test_全部合格時沒有任何失敗():
    results = LC.evaluate(_measure(), strict=True)
    assert [r["id"] for r in results] == ["V1", "V2", "V3", "V4", "V5", "V6", "V7", "V8"]
    assert all(r["status"] == "pass" for r in results), results
    assert LC.hard_failures(results) == [] and LC.advisory_gaps(results) == []


@pytest.mark.parametrize("over, cid", [
    ({"exceptions": 1}, "V1"),
    ({"code_blocks": 2}, "V2"),
    ({"doc_overflow": {"scroll": 500, "client": 390}}, "V3"),
    ({"main_overflow": {"scroll": 5878, "client": 390}}, "V3"),
])
def test_hard檢查失敗一律轉紅_不論strict(over, cid):
    for strict in (False, True):
        failed = [r["id"] for r in LC.hard_failures(LC.evaluate(_measure(**over), strict=strict))]
        assert failed == [cid], (strict, failed)


def test_圖表在收合展開區_非strict是缺口不轉紅_strict轉紅():
    m = _measure(charts=[{"top": 100, "height": 260, "width": 350, "collapsed": True}])
    assert LC.hard_failures(LC.evaluate(m)) == []
    assert "V4" in [r["id"] for r in LC.advisory_gaps(LC.evaluate(m))]
    assert [r["id"] for r in LC.hard_failures(LC.evaluate(m, strict=True))] == ["V4"]


def test_圖表太小_與chips超過上限():
    small = _measure(charts=[{"top": 100, "height": config.MIN_CHART_HEIGHT_PX - 1, "width": 350, "collapsed": False}])
    assert [r["id"] for r in LC.hard_failures(LC.evaluate(small, strict=True))] == ["V5"]
    narrow = _measure(charts=[{"top": 100, "height": 260, "width": 100, "collapsed": False}])   # 100 < 358 * 0.6
    assert [r["id"] for r in LC.hard_failures(LC.evaluate(narrow, strict=True))] == ["V5"]
    many = _measure(chips_groups=[config.MAX_CHIPS_PER_CARD + 1])
    assert [r["id"] for r in LC.hard_failures(LC.evaluate(many, strict=True))] == ["V6"]
    assert LC.hard_failures(LC.evaluate(many)) == []


def test_首屏沒有圖或chips太多_永遠只是缺口_不轉紅():
    m = _measure(charts=[{"top": 2000, "height": 260, "width": 350, "collapsed": False}], first_screen_chips=9)
    for strict in (False, True):
        results = LC.evaluate(m, strict=strict)
        assert LC.hard_failures(results) == []
        assert {r["id"] for r in LC.advisory_gaps(results)} == {"V7", "V8"}


def test_沒有圖表的頁_V4到V6不誤報():
    results = _by_id(LC.evaluate(_measure(charts=[], chips_groups=[]), strict=True))
    for cid in ("V4", "V5", "V6"):
        assert results[cid]["status"] == "pass", cid
    assert results["V7"]["status"] == "fail"   # 沒圖＝首屏沒有 Primary Visual，但只是缺口


def test_報告第一行標示兩層不得混用_且列出缺口():
    results = LC.evaluate(_measure(first_screen_chips=9))
    text = LC.render_report([{"scenario": "mkt", "viewport": "mobile390", "file": "ci-fixture__mkt__mobile390.png",
                              "results": results, "deterministic": True}])
    assert config.CI_FIXTURE_LABEL in text.splitlines()[2]
    assert "契約缺口" in text and "V8" in text
    assert "ci-fixture__mkt__mobile390.png" in text


def test_config_標示與URL():
    assert config.CI_FIXTURE_LABEL == "CI fixture screenshot ≠ production-like Cloud screenshot"
    assert config.CLOUD_BLOCKED_NOTE == "production-like Cloud capture blocked by current environment network policy"
    assert config.CLOUD_PREVIEW_URL.startswith("https://") and config.CLOUD_PREVIEW_URL.endswith(".streamlit.app/")
    assert set(config.VIEWPORTS) == {"desktop", "mobile390"} and config.VIEWPORTS["mobile390"]["width"] == 390
    assert config.CI_FILE_PREFIX != config.CLOUD_FILE_PREFIX and "NOT-production" in config.CI_ARTIFACT_NAME


def test_config不含任何疑似credential():
    text = (_HERE / "config.py").read_text(encoding="utf-8")
    assert not re.search(r"(?i)(token|secret|password|api[_-]?key)\s*=", text)
    tree = ast.parse(text)
    imported = {n.names[0].name for n in ast.walk(tree) if isinstance(n, ast.Import)} | \
               {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert imported <= {"__future__"}, imported   # 不 import 任何專案模組


def test_URL只登記在一處():
    """Cloud Preview URL 的單一位置是 `tests/visual_fidelity/config.py`；程式碼其他地方不得再寫死一份（文件可以指向它）。"""
    root = _HERE.parents[1]
    host = "my-fund-dashboard-3atbdymetmxyi2fbkxujtv"
    hits = []
    for path in list((root / "tests").rglob("*.py")) + list((root / "ui_v2").rglob("*.py")) + list((root / ".github").rglob("*.yml")):
        if host in path.read_text(encoding="utf-8", errors="replace"):
            hits.append(str(path.relative_to(root)))
    assert hits == ["tests/visual_fidelity/config.py", "tests/visual_fidelity/test_layout_checks_logic.py"], hits


def test_desktop_內容區比視窗窄_寬度比例量內容區不量視窗():
    wide = {"viewport": {"width": 1280, "height": 800}, "main_width": 730}
    ok = _measure(**wide, charts=[{"top": 100, "height": 260, "width": 700, "collapsed": False}])
    assert LC.hard_failures(LC.evaluate(ok, strict=True)) == []
    bad = _measure(**wide, charts=[{"top": 100, "height": 260, "width": 300, "collapsed": False}])
    assert [r["id"] for r in LC.hard_failures(LC.evaluate(bad, strict=True))] == ["V5"]


# ── cloud_capture（不需要瀏覽器的部分）──


def test_cloud_capture_網路被擋判定_與報告字樣():
    import cloud_capture as CC

    assert CC.is_network_block("Page.goto: net::ERR_TUNNEL_CONNECTION_FAILED at https://x/")
    assert CC.is_network_block("Page.goto: Timeout 45000ms exceeded.")
    assert not CC.is_network_block("Browser closed unexpectedly")      # 判不出來就不吞
    text = CC.report_text(url="https://x/", outcome=config.CLOUD_BLOCKED_NOTE, files=[], reason="net::ERR_TUNNEL_CONNECTION_FAILED")
    assert config.CLOUD_BLOCKED_NOTE in text and "production-like Cloud screenshot" in text
    assert config.CI_FILE_PREFIX not in text   # 兩層不混用：Cloud 報告不出現 CI 檔名前綴
