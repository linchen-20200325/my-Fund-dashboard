# -*- coding: utf-8 -*-
"""持倉體檢（HLD）渲染層測試。

需要 streamlit；本環境的系統 python3 匯入不到 streamlit，故缺 streamlit 時整檔 skip。
要跑起來：PYTHONPATH=<裝有 streamlit 的目錄> pytest tests/ui_v2/ -q --noconftest
"""

import pathlib
import re
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


# ─────────── 第 5~8 輪裁示的回補 ＋ 本輪回修（渲染層正控） ───────────


def _source_tier_cells(at) -> list:
    """把 `HLD-6` 淨值表「來源層級」那一欄抽出來逐格回傳。

    掃整頁字串會被別處的同字命中（「淨值表」「單位淨值（原幣）」都含「淨值」），
    所以認的是**那一欄本身**：表頭找出欄位序，再取每一列同序的那一格。
    """
    for element in at.markdown:
        html_text = element.value
        if "淨值日期" not in html_text or "<table" not in html_text:
            continue
        heads = re.findall(r"<th>(.*?)</th>", html_text, re.S)
        if "來源層級" not in heads:
            return []
        index = heads.index("來源層級")
        cells = []
        for row in re.findall(r"<tr>(?!.*?<th>)(.*?)</tr>", html_text, re.S):
            tds = re.findall(r"<td>(.*?)</td>", row, re.S)
            if len(tds) > index:
                cells.append(re.sub(r"<[^>]+>", "", tds[index]).strip())
        return cells
    return []


def test_渲染出來的畫面沒有值域外的來源層級字面值():
    """`44` :1799 值域四個之一。⚠️ **本條第一版的防空掃守衛是假的**：`assert "淨值" in blob`
    —— 「淨值」也出現在「淨值表」「單位淨值（原幣）」，**把那一欄整個拿掉照樣通過**。
    現改為抽出該欄逐格看，並先斷言格數大於零。"""
    cells = _source_tier_cells(_run("full"))
    assert cells, "抽不到來源層級那一欄 —— 這一條會變成空掃"
    for cell in cells:
        assert cell in fixtures.SOURCE_TIERS, cell


def test_渲染出來的畫面不再出現被劃掉的那一句():
    """`44` :720（第五輪改寫）。"""
    for scenario in fixtures.SCENARIO_NAMES:
        blob = "\n".join(_rendered(_run(scenario)))
        assert "上面三張卡" not in blob, scenario
        if scenario == "full":
            assert "本頁那四塊用到的原始數字" in blob


def test_重新取數在畫面上的枚數與模型相等():
    """A3 撤回後的渲染層對照：釘模型與畫面不脫鉤，不釘「有幾枚」—— 客戶往哪邊裁都不擋。"""
    for scenario in ("srcmiss", "fetchfail"):
        model = logic.build_page_model(**fixtures.scenario(scenario))
        expected = sum(
            1 for block in logic.all_blocks(model)
            for b in block["buttons"] if b["label"] == "重新取數"
        )
        assert expected > 0, scenario
        rendered = sum(1 for b in _run(scenario).button if b.label == "重新取數")
        assert rendered == expected, (scenario, rendered, expected)


def test_HLD5是純文字列表_不巢狀_不自動展開_也沒有死鈕():
    """A4：`44` :707／§5.4「**展開區不巢狀第二層**」＋ :119／:128「**不自動展開**」
    ＋ :2420「**一枚按了不動的按鈕，比沒有按鈕更誤導**」。

    上一輪先是在塊層 expander 裡面又開一層（一檔一枚）、且第一檔初次載入就展開；
    改成 `展開` 類按鈕之後又留下一枚**按了不動的鈕**（`open_fund` 沒有任何呼叫端會傳值）。
    本輪退成純文字列表。既有的 `test_層三層四用expander且預設收合` 只驗塊層旗標與
    原始碼字串，**上述三件全部零覆蓋**。
    """
    at = _run("full")
    labels = [element.label for element in at.expander]
    model = logic.build_page_model(**fixtures.scenario("full"))
    expected = {
        f"{b['code']}　{b['title']}　—　{b['summary_text']}"
        for b in logic.all_blocks(model)
        if b["code"] in ("HLD-4", "HLD-5", "HLD-6", "HLD-7", "HLD-8")
    }
    # 不巢狀：畫面上的 expander 剛好是那五塊，沒有一枚是某一檔的標題。
    assert set(labels) == expected and len(labels) == 5, labels
    block = logic.find_block(model, "HLD-5")
    items = block["_items"]
    for item in items:
        assert item["head_text"] not in labels, item["head_text"]
    # 不自動展開。
    assert [b["code"] for b in logic.all_blocks(model) if b["_default_open"]] == [
        "HLD-0", "HLD-1", "HLD-2", "HLD-3"
    ]
    assert sum(1 for i in items if i["_open"]) == 0, "初次載入不得有任何一檔自己打開"
    # 沒有死鈕：本塊零按鈕，逐檔也不帶任何自擬的按鈕。
    assert block["buttons"] == [], block["buttons"]
    for item in items:
        assert not [k for k in item if "button" in k], item.keys()
    # 逐檔標題仍然畫得出來（否則這一條會退化成只驗「什麼都沒有」）。
    blob = "\n".join(_rendered(at))
    for item in items:
        assert item["head_text"] in blob, item["head_text"]
