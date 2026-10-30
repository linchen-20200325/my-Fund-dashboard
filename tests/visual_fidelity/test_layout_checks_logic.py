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

import vf_config as config  # noqa: E402
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
    text = (_HERE / "vf_config.py").read_text(encoding="utf-8")
    assert not re.search(r"(?i)(token|secret|password|api[_-]?key)\s*=", text)
    tree = ast.parse(text)
    imported = {n.names[0].name for n in ast.walk(tree) if isinstance(n, ast.Import)} | \
               {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert imported <= {"__future__"}, imported   # 不 import 任何專案模組


def test_URL只登記在一處():
    """Cloud Preview URL 的單一位置是 `tests/visual_fidelity/vf_config.py`；程式碼其他地方不得再寫死一份（文件可以指向它）。"""
    root = _HERE.parents[1]
    host = "my-fund-dashboard-3atbdymetmxyi2fbkxujtv"
    hits = []
    for path in list((root / "tests").rglob("*.py")) + list((root / "ui_v2").rglob("*.py")) + list((root / ".github").rglob("*.yml")):
        if host in path.read_text(encoding="utf-8", errors="replace"):
            hits.append(str(path.relative_to(root)))
    assert sorted(hits) == sorted(["tests/visual_fidelity/vf_config.py", "tests/visual_fidelity/test_layout_checks_logic.py"]), hits   # 與順序無關


def test_desktop_內容區比視窗窄_寬度比例量內容區不量視窗():
    wide = {"viewport": {"width": 1280, "height": 800}, "main_width": 730}
    ok = _measure(**wide, charts=[{"top": 100, "height": 260, "width": 700, "collapsed": False}])
    assert LC.hard_failures(LC.evaluate(ok, strict=True)) == []
    bad = _measure(**wide, charts=[{"top": 100, "height": 260, "width": 300, "collapsed": False}])
    assert [r["id"] for r in LC.hard_failures(LC.evaluate(bad, strict=True))] == ["V5"]


# ── cloud_capture（不需要瀏覽器的部分）──


def test_cloud_capture_只有明確網路層錯誤才算blocked():
    import cloud_capture as CC

    assert CC.is_network_block("Page.goto: net::ERR_TUNNEL_CONNECTION_FAILED at https://x/")
    assert CC.is_network_block("Page.goto: net::ERR_NAME_NOT_RESOLVED at https://x/")
    assert CC.is_network_block("Page.goto: net::ERR_PROXY_CONNECTION_FAILED at https://x/")
    # 這些不是網路政策阻擋：可能是 app 慢、站點狀態或被擋在別處 —— 不得冒充 blocked。
    assert not CC.is_network_block("Page.goto: Timeout 45000ms exceeded.")
    assert not CC.is_network_block("Page.wait_for_selector: Timeout 45000ms exceeded.")
    assert not CC.is_network_block("HTTP 403 Forbidden")
    assert not CC.is_network_block("Browser closed unexpectedly")


def test_cloud_capture_頁面內容檢查_休眠頁與非app不報captured():
    import cloud_capture as CC

    assert CC.assess_page(has_app_container=True, body_text="") == "app"
    assert CC.assess_page(has_app_container=False, body_text="This app has gone to sleep due to inactivity") == "sleeping"
    assert CC.assess_page(has_app_container=False, body_text="Yes, get this app back up!") == "sleeping"
    assert CC.assess_page(has_app_container=False, body_text="404 Not Found") == "not_app"
    assert CC.assess_page(has_app_container=False, body_text="") == "not_app"


def test_cloud_capture_狀態與exit_code要讓人看得到():
    import cloud_capture as CC

    assert CC.EXIT_OK == 0
    assert len({CC.EXIT_UNDETERMINABLE, CC.EXIT_NOT_APP, CC.EXIT_USAGE}) == 3 and 0 not in (CC.EXIT_UNDETERMINABLE, CC.EXIT_NOT_APP)
    assert "not determinable" in CC.NOT_DETERMINABLE_NOTE and "blocked" not in CC.NOT_DETERMINABLE_NOTE
    text = CC.report_text(url="https://x/", outcome=config.CLOUD_BLOCKED_NOTE, files=[], reason="net::ERR_TUNNEL_CONNECTION_FAILED")
    assert config.CLOUD_BLOCKED_NOTE in text and "production-like Cloud screenshot" in text
    assert config.CI_FILE_PREFIX not in text   # 兩層不混用：Cloud 報告不出現 CI 檔名前綴


# ── BL-0525 Batch C：🌍 頁專屬檢查（page="mkt"）──


def _mkt_measure(**over):
    """桌機 1280x800 的合格 🌍 頁量測：status chip → hero → Primary → Primary 圖 → Secondary ×3 → 依據卡，由上而下。"""
    base = _measure(
        viewport={"width": 1280, "height": 800}, main_width=730,
        charts=[{"top": 330, "height": 300, "width": 700, "collapsed": False}],
        chips_groups=[3, 3, 3, 3, 3], first_screen_chips=3,
        mkt={
            "status_chip": {"top": 120, "height": 36, "width": 200},
            "hero": {"top": 170, "height": 30, "width": 600},
            "primary": {"top": 220, "height": 520, "width": 730},
            "secondary": [{"top": 760, "height": 190, "width": 230}] * 3,
            "evidence": {"top": 1000, "height": 200, "width": 230},
            "page_date": False,
        },
    )
    base.update(over)
    return base


def test_mkt_合格頁面_V1到V8與M1到M6全部通過_且全部hard():
    results = LC.evaluate(_mkt_measure(), page="mkt")
    assert [r["id"] for r in results] == ["V1", "V2", "V3", "V4", "V5", "V6", "V7", "V8", "M1", "M2", "M3", "M4", "M5", "M6"]
    assert all(r["status"] == "pass" and r["hard"] for r in results), [r for r in results if r["status"] != "pass" or not r["hard"]]


def test_mkt_V7與V8對mkt是hard_對其他頁仍是advisory():
    m = _mkt_measure(charts=[{"top": 2000, "height": 300, "width": 700, "collapsed": False}], first_screen_chips=9)
    assert {"V7", "V8"} <= {r["id"] for r in LC.hard_failures(LC.evaluate(m, page="mkt"))}
    assert LC.hard_failures(LC.evaluate(m)) == []                       # 沒帶 page：舊行為不變
    assert {"V7", "V8"} == {r["id"] for r in LC.advisory_gaps(LC.evaluate(m, page="hld"))}


def test_mkt_順序錯誤_M1轉紅():
    swapped = _mkt_measure()
    swapped["mkt"] = {**swapped["mkt"], "hero": {"top": 700, "height": 30, "width": 600}}    # 一句主判讀跑到 Primary 之後
    assert "M1" in [r["id"] for r in LC.hard_failures(LC.evaluate(swapped, page="mkt"))]
    no_chip = _mkt_measure()
    no_chip["mkt"] = {**no_chip["mkt"], "status_chip": None}
    failed = [r for r in LC.hard_failures(LC.evaluate(no_chip, page="mkt")) if r["id"] == "M1"]
    assert failed and "status chip" in failed[0]["detail"]


def test_mkt_Secondary超過三個_或零個_M2轉紅():
    four = _mkt_measure()
    four["mkt"] = {**four["mkt"], "secondary": [{"top": 760, "height": 190, "width": 230}] * 4}
    zero = _mkt_measure()
    zero["mkt"] = {**zero["mkt"], "secondary": []}
    for m in (four, zero):
        assert "M2" in [r["id"] for r in LC.hard_failures(LC.evaluate(m, page="mkt"))]
    two = _mkt_measure()      # 2 個夠就不硬塞第三張：少於 3 是合格
    two["mkt"] = {**two["mkt"], "secondary": [{"top": 760, "height": 190, "width": 230}] * 2}
    assert "M2" not in [r["id"] for r in LC.hard_failures(LC.evaluate(two, page="mkt"))]


def test_mkt_頁級日期_M3轉紅():
    m = _mkt_measure()
    m["mkt"] = {**m["mkt"], "page_date": True}
    assert [r["id"] for r in LC.hard_failures(LC.evaluate(m, page="mkt"))] == ["M3"]


def test_mkt_Secondary比Primary圖高_M4轉紅():
    m = _mkt_measure()
    m["mkt"] = {**m["mkt"], "secondary": [{"top": 760, "height": 320, "width": 230}] * 3}
    assert "M4" in [r["id"] for r in LC.hard_failures(LC.evaluate(m, page="mkt"))]


def test_mkt_手機Secondary太高_M5轉紅_桌機不適用():
    mobile = _mkt_measure(viewport={"width": 390, "height": 844}, main_width=358)
    mobile["mkt"] = {**mobile["mkt"], "secondary": [{"top": 760, "height": 260, "width": 358}] * 3}
    assert "M5" in [r["id"] for r in LC.hard_failures(LC.evaluate(mobile, page="mkt"))]
    compact = _mkt_measure(viewport={"width": 390, "height": 844}, main_width=358)
    compact["mkt"] = {**compact["mkt"], "secondary": [{"top": 760, "height": 150, "width": 358}] * 3}
    assert "M5" not in [r["id"] for r in LC.hard_failures(LC.evaluate(compact, page="mkt"))]
    desktop = _mkt_measure()
    desktop["mkt"] = {**desktop["mkt"], "secondary": [{"top": 760, "height": 260, "width": 230}] * 3}
    assert "M5" not in [r["id"] for r in LC.hard_failures(LC.evaluate(desktop, page="mkt"))]


def test_mkt_圖表牆_兩張可見圖_M6轉紅():
    m = _mkt_measure(charts=[{"top": 330, "height": 300, "width": 700, "collapsed": False},
                             {"top": 800, "height": 200, "width": 700, "collapsed": False}])
    assert "M6" in [r["id"] for r in LC.hard_failures(LC.evaluate(m, page="mkt"))]


def test_mkt_圖表放進展開區_V4轉紅_圖不算外露():
    m = _mkt_measure(charts=[{"top": 330, "height": 300, "width": 700, "collapsed": True}])
    failed = {r["id"] for r in LC.hard_failures(LC.evaluate(m, page="mkt"))}
    assert {"V4", "M1", "M6"} <= failed


def test_量測腳本帶mkt專屬欄位_且選擇器對得上頁面():
    js = LC.MEASURE_JS
    for needle in (".mkt-light--chip", ".mkt-hero", "[data-section=primary]", ".mkt-sec-card", '[data-block="MKT-1"]'):
        assert needle in js, needle
    page = (_HERE.parents[1] / "ui_v2" / "mkt" / "page.py").read_text(encoding="utf-8")
    for cls in ("mkt-light--chip", "mkt-hero", "mkt-sec-card", 'data-section="primary"'):
        assert cls in page, cls


# ───────────────────────── 💼 我的資產頁（BL-0525 Batch D；A1～A6）─────────────────────────


def _ast_measure(**over):
    base = _measure(viewport={"width": 1280, "height": 800}, main_width=704, charts=[])
    base["ast"] = {
        "source": {"top": 100, "height": 40, "width": 700},
        "summary": {"top": 260, "height": 62, "width": 700},
        "slots": 4, "summaries": 1,
        "hero": {"top": 400, "height": 28, "width": 700},
        "primary": {"top": 430, "height": 600, "width": 700},
        "primary_chart": {"top": 560, "height": 300, "width": 680},
        "secondary": [{"top": 1050, "height": 300, "width": 340}, {"top": 1050, "height": 300, "width": 340}],
        "scrolls": [{"overflowY": "auto", "maxHeight": "240px"}, {"overflowY": "auto", "maxHeight": "240px"}],
        "nested_details": 0,
    }
    base["ast"].update(over)
    return base


def test_ast_合格頁面_A1到A6全部通過_且全部hard():
    results = LC.evaluate(_ast_measure(), page="ast")
    ids = [r["id"] for r in results]
    assert ids[:8] == ["V1", "V2", "V3", "V4", "V5", "V6", "V7", "V8"] and ids[-6:] == ["A1", "A2", "A3", "A4", "A5", "A6"]
    a_checks = [r for r in results if r["id"].startswith("A")]
    assert all(r["status"] == "pass" and r["hard"] for r in a_checks), a_checks
    assert LC.hard_failures(results) == []


def test_ast_順序錯誤_缺項_A1轉紅():
    swapped = _ast_measure(hero={"top": 90, "height": 28, "width": 700})     # 主判讀跑到 selector 之前
    assert "A1" in [r["id"] for r in LC.hard_failures(LC.evaluate(swapped, page="ast"))]
    no_source = _ast_measure(source=None)
    failed = [r for r in LC.hard_failures(LC.evaluate(no_source, page="ast")) if r["id"] == "A1"]
    assert failed and "持倉資料來源" in failed[0]["detail"]


@pytest.mark.parametrize("count", [0, 1, 3])
def test_ast_Secondary不是兩張_A2轉紅(count):
    m = _ast_measure(secondary=[{"top": 1050, "height": 300, "width": 340}] * count)
    assert "A2" in [r["id"] for r in LC.hard_failures(LC.evaluate(m, page="ast"))]


def test_ast_summary不是一個容器四格_A3轉紅():
    for over in ({"slots": 3}, {"slots": 5}, {"summaries": 4, "slots": 4}, {"summaries": 0}):
        assert "A3" in [r["id"] for r in LC.hard_failures(LC.evaluate(_ast_measure(**over), page="ast"))], over


def test_ast_巢狀展開區_A4轉紅():
    assert "A4" in [r["id"] for r in LC.hard_failures(LC.evaluate(_ast_measure(nested_details=1), page="ast"))]


def test_ast_手機summary太高_A5轉紅_桌機不適用():
    mobile_tall = _ast_measure()
    mobile_tall["viewport"] = {"width": 390, "height": 844}
    mobile_tall["ast"]["summary"] = {"top": 260, "height": 300, "width": 358}     # 四張大卡直排
    assert "A5" in [r["id"] for r in LC.hard_failures(LC.evaluate(mobile_tall, page="ast"))]
    mobile_ok = _ast_measure()
    mobile_ok["viewport"] = {"width": 390, "height": 844}
    mobile_ok["ast"]["summary"] = {"top": 260, "height": 110, "width": 358}
    assert "A5" not in [r["id"] for r in LC.hard_failures(LC.evaluate(mobile_ok, page="ast"))]
    desktop = _ast_measure()
    desktop["ast"]["summary"] = {"top": 260, "height": 300, "width": 700}
    assert "A5" not in [r["id"] for r in LC.hard_failures(LC.evaluate(desktop, page="ast"))]


def test_ast_清單沒有固定高度垂直捲動_A6轉紅():
    for scrolls in ([{"overflowY": "visible", "maxHeight": "240px"}] * 2,
                    [{"overflowY": "auto", "maxHeight": "none"}] * 2,
                    [{"overflowY": "auto", "maxHeight": "240px"}]):
        m = _ast_measure(scrolls=scrolls)
        assert "A6" in [r["id"] for r in LC.hard_failures(LC.evaluate(m, page="ast"))], scrolls


def test_ast_V7量Primary條圖_不在首屏轉紅():
    low = _ast_measure(primary_chart={"top": 1500, "height": 300, "width": 680})
    assert "V7" in [r["id"] for r in LC.hard_failures(LC.evaluate(low, page="ast"))]
    none = _ast_measure(primary_chart=None)
    assert "V7" in [r["id"] for r in LC.hard_failures(LC.evaluate(none, page="ast"))]


def test_ast_專屬檢查只在page_ast時評估_其他頁不變():
    m = _ast_measure()
    assert not [r for r in LC.evaluate(m, page="mkt") if r["id"].startswith("A")]
    assert not [r for r in LC.evaluate(m) if r["id"].startswith("A")]


def test_量測腳本帶ast專屬欄位_且選擇器對得上頁面():
    js = LC.MEASURE_JS
    for needle in (".st-key-ast_source", ".ast-summary", ".ast-hero", ".st-key-ast_primary",
                   ".st-key-ast_sec_share", ".st-key-ast_sec_returns", ".ast-scroll", "details details"):
        assert needle in js, needle
    page = (_HERE.parents[1] / "ui_v2" / "asset" / "page.py").read_text(encoding="utf-8")
    for cls in ('key="ast_source"', 'key="ast_primary"', 'key="ast_sec_share"', 'key="ast_sec_returns"',
                "ast-summary", "ast-hero", "ast-scroll"):
        assert cls in page, cls
