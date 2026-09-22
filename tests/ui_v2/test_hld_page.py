# -*- coding: utf-8 -*-
"""持倉體檢（HLD）渲染層測試。

需要 streamlit；本環境的系統 python3 匯入不到 streamlit，故缺 streamlit 時整檔 skip。
要跑起來：PYTHONPATH=<裝有 streamlit 的目錄> pytest tests/ui_v2/ -q --noconftest
"""

import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

pytest.importorskip("streamlit", reason="本環境系統 python3 匯入不到 streamlit")

from ui_v2.hld import fixtures, logic, page, theme  # noqa: E402

_ROOT = pathlib.Path(__file__).resolve().parents[2]
_APP = _ROOT / "ui_v2" / "app_hld.py"


def _run(scenario="full"):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(_APP), default_timeout=60)
    at.query_params["scenario"] = scenario
    at.run()
    return at


def _rendered(at):
    """渲染出來的畫面字串 —— 權威檢查掃的是這個，不是原始碼。

    ⚠️ **展開區的標題列也是畫面文字**。第一版這支只收 markdown／caption／button，
    於是 `HLD-4`～`HLD-8` 五塊的標題列整列掃不到 —— 紅線字表掃描會跟著瞎掉一半。
    是 `test_九塊的標題都畫出來了` 把它抓出來的。**寧可多抓，不可漏抓。**
    """
    out = []
    for element in at.markdown:
        out.append(element.value)
    for element in at.caption:
        out.append(element.value)
    for element in at.button:
        out.append(element.label)
    for element in at.expander:
        out.append(element.label)
    for element in at.text_input:
        out.append(element.label)
        if element.placeholder:
            out.append(element.placeholder)
        if element.value:
            out.append(str(element.value))
    for group in (at.title, at.text, at.error, at.warning, at.info, at.success):
        for element in group:
            out.append(element.value)
    return out


# ───────────────────────── 分離 ─────────────────────────


def test_page只呼叫logic與fixtures與theme_自己不做判定():
    source = pathlib.Path(page.__file__).read_text(encoding="utf-8")
    for banned in (
        "STATE_OK =",
        "def columns_for_width",
        "def main_value_state",
        "def conclusion_light",
        "def return_pct",
        "def drawdown_pct",
    ):
        assert banned not in source


def test_page沒有import舊repo模組也沒有網路字表():
    source = pathlib.Path(page.__file__).read_text(encoding="utf-8")
    for banned in (
        "from ui.",
        "from services.",
        "from repositories.",
        "from shared.",
        "from infra.",
        "import fund_fetcher",
        "requests",
        "httpx",
        "urllib",
        "yfinance",
        "gspread",
        "feedparser",
        "subprocess",
    ):
        assert banned not in source


def test_進入點沒有import舊repo模組():
    source = _APP.read_text(encoding="utf-8")
    for banned in ("from ui.", "from services.", "from repositories.", "from shared.", "from infra."):
        assert banned not in source


# ───────────────────────── 渲染 ─────────────────────────


def test_六種狀態各渲染一次都不炸():
    """任何一個丟例外就是紅燈（§1 Fail Loud：不吞例外）。"""
    for scenario in ("full", "srcmiss", "bizexc", "fetchfail", "nothr", "empty"):
        at = _run(scenario)
        assert not at.exception, scenario


def test_層三層四用expander且預設收合():
    source = pathlib.Path(page.__file__).read_text(encoding="utf-8")
    assert "st.expander" in source
    model = logic.build_page_model(fixtures.dataset_full())
    for code in ("HLD-4", "HLD-5", "HLD-6", "HLD-7", "HLD-8"):
        assert logic.find_block(model, code)["_default_open"] is False


def test_九塊的標題都畫出來了():
    at = _run("full")
    joined = "".join(_rendered(at))
    for code, title in logic.BLOCK_TITLES.items():
        assert code in joined, code
        assert title in joined, title


# ───────────────────────── 紅線（掃實際畫面字串） ─────────────────────────


def test_渲染出來的文字零方向詞零箭頭():
    for scenario in ("full", "srcmiss", "bizexc", "fetchfail", "nothr", "empty"):
        at = _run(scenario)
        assert logic.scan_forbidden(_rendered(at)) == {}, scenario


def test_渲染出來的按鈕標籤零禁詞():
    for scenario in ("full", "empty"):
        at = _run(scenario)
        for button in at.button:
            for word in logic.FORBIDDEN_BUTTON_WORDS:
                assert word not in button.label, (scenario, button.label)


def test_渲染出來的輸入欄沒有一個帶非空的預設值():
    """`44` 1.1 節判準後半句，驗的是真的 widget。"""
    at = _run("empty")
    for widget in list(at.text_input) + list(at.date_input) + list(at.number_input):
        assert widget.value in (None, "", []), widget.label


# ───────────────────────── 主題 ─────────────────────────


def test_theme色票就是客戶指定的三個色():
    assert theme.APP_BG == "#0e1117"
    assert theme.TEAL_DARK == "#0f6b6c"
    assert theme.TEAL_BRIGHT == "#5fd3d0"


def test_畫面用到的每一個色碼都登記在對比表裡():
    """防的是「在 page.py 裡隨手寫一個沒算過對比的色碼」。"""
    import re

    source = pathlib.Path(page.__file__).read_text(encoding="utf-8")
    hexes = {h.lower() for h in re.findall(r"#[0-9a-fA-F]{6}", source)}
    known = {c.lower() for c in theme.ALL_COLORS}
    assert hexes <= known, hexes - known
