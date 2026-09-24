# -*- coding: utf-8 -*-
"""市場總覽渲染層測試。

需要 streamlit；本環境的系統 python3 匯入不到 streamlit，故缺 streamlit 時整檔 skip。
要跑起來：PYTHONPATH=<裝有 streamlit 的目錄> pytest tests/ui_v2/ -q --noconftest
"""

import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

pytest.importorskip("streamlit", reason="本環境系統 python3 匯入不到 streamlit")

from ui_v2.mkt import fixtures, logic, page, theme  # noqa: E402

_ROOT = pathlib.Path(__file__).resolve().parents[2]
_APP = _ROOT / "ui_v2" / "app_mkt.py"


def _run(scenario="all_ok"):
    """把整頁真的跑起來（AppTest）。

    ⚠️ **本檔在 2026-09-24 之前沒有這支** —— 它只做原始碼層的檢查
    （「`page.py` 有沒有 import 到不該 import 的東西」那一類），
    **一次也沒有把這一頁真的渲染起來過**。
    稽核指出本輪往 `fixtures.all_datasets()` 加了兩個情境
    ＝ 替頁面新增了兩個對外可選的畫面，卻沒有任何測試渲染過它們 —— 本輪補上。
    """
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(_APP), default_timeout=60)
    at.query_params["scenario"] = scenario
    at.run()
    return at


def _rendered(at):
    """渲染出來的畫面字串。**寧可多抓，不可漏抓**（同 `hld` 那一份的教訓：
    展開區的標題列也是畫面文字，第一版漏收會讓字表掃描瞎掉一半）。"""
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


def test_page只呼叫logic與fixtures與theme_自己不做判定():
    """page.py 不得自己算四狀態、不得自己算欄數 —— 那些住在 logic。"""
    source = pathlib.Path(page.__file__).read_text(encoding="utf-8")
    for banned in ("STATE_OK =", "def columns_for_width", "def main_value_state", "def conclusion_light"):
        assert banned not in source


def test_page沒有import舊repo模組():
    source = pathlib.Path(page.__file__).read_text(encoding="utf-8")
    for banned in ("from ui.", "from services.", "from repositories.", "from shared.", "from infra.", "import fund_fetcher"):
        assert banned not in source


def test_theme色票就是客戶指定的三個色():
    assert theme.APP_BG == "#0e1117"
    assert theme.TEAL_DARK == "#0f6b6c"
    assert theme.TEAL_BRIGHT == "#5fd3d0"


def test_層三層四用expander且預設收合():
    source = pathlib.Path(page.__file__).read_text(encoding="utf-8")
    assert "st.expander" in source
    model = logic.build_page_model(fixtures.dataset_all_ok())
    for code in ("MKT-4", "MKT-5", "MKT-6", "MKT-7"):
        assert logic.find_block(model, code)["_default_open"] is False


def test_渲染全部情境不炸():
    """六個情境各渲染一次，任何一個丟例外就是紅燈（§1 Fail Loud：不吞例外）。"""
    from streamlit.testing.v1 import AppTest

    root = pathlib.Path(__file__).resolve().parents[2]
    at = AppTest.from_file(str(root / "ui_v2" / "app_mkt.py"), default_timeout=30)
    at.run()
    assert not at.exception


def test_渲染出來的文字零方向詞():
    from streamlit.testing.v1 import AppTest

    root = pathlib.Path(__file__).resolve().parents[2]
    at = AppTest.from_file(str(root / "ui_v2" / "app_mkt.py"), default_timeout=30)
    at.run()
    rendered = []
    for element in at.markdown:
        rendered.append(element.value)
    for element in at.caption:
        rendered.append(element.value)
    assert logic.scan_forbidden(rendered) == {}


def test_渲染出來的按鈕標籤零禁詞():
    from streamlit.testing.v1 import AppTest

    root = pathlib.Path(__file__).resolve().parents[2]
    at = AppTest.from_file(str(root / "ui_v2" / "app_mkt.py"), default_timeout=30)
    at.run()
    for button in at.button:
        for word in ("一鍵", "最佳", "推薦", "最適"):
            assert word not in button.label


# ═══════ 情境註冊表：新加的 fixture 等於替頁面新增了對外可選的情境 ═══════


def test_兩個同級情境_頁面挑得到而且渲染得出來():
    """⭐ **稽核 2026-09-24 指出的第 8 個呼叫端**：`mkt/page.py::_pick_dataset()`
    直接讀 `fixtures.all_datasets()` —— **那就是 `?scenario=` 的註冊表**。
    本輪往 `all_datasets()` 加了兩個 fixture，**等於替頁面新增了兩個對外可選的情境**，
    而在本條之前**沒有任何測試用它們渲染過頁面**。

    ⚠️ **本輪在 `hld` 那一邊明文推敲過同一個問題**（刻意把新 scenario 擋在
    `SCENARIO_NAMES` 之外，免得草稿那排鈕多長一顆），
    **卻沒有人對 `mkt` 這張註冊表問同一句話** —— 尺往外用了，沒往內用。本條補上。

    **判定：`mkt` 這兩個情境該留在註冊表裡。** 理由兩條：
      · 它們是**唯一**看得到本輪新畫面的入口（卡狀態排不出來、燈同時點名兩張卡）；
        看不到的畫面，客戶沒辦法驗收。
      · `mkt` 這一頁的副標印的是**情境名本身**，沒有像 `hld` 那樣的標籤表，
        所以多兩個名字**不會在畫面上長出任何新元件**（與 `hld` 那排鈕的情況不同）。

    ⭐ **2026-09-24 就地擴寫（本組自查）**：~~原本只跑手寫的那兩個名字。~~
    **改成跑 `fixtures.all_datasets()` 全部** —— 那張表**就是**頁面的註冊表，
    往後有人往它加東西，這條渲染測試**自動納入**，不必有人記得回來改這裡。
    ⇒ 這正是本件的教訓：**問題不是「那兩個沒被渲染過」，
    是「加情境的人與寫渲染測試的人之間沒有任何機械連結」。**
    """
    names = sorted(fixtures.all_datasets())
    assert {"mkt3_tied_in_one_card", "two_cards_tied"} <= set(names), names
    for name in names:
        at = _run(name)
        assert not at.exception, (name, at.exception)
        rendered = _rendered(at)
        assert rendered, name
        assert any(name in text for text in rendered), (
            name, "副標沒印出情境名 ⇒ 八成是被打回 `all_ok` 了")
        for text in rendered:
            assert "None" not in text, (name, text[:90])


def test_同級那兩張畫面_該說的話真的畫出來了():
    """不只是「不炸」—— 本輪新做的那兩句文案要真的上螢幕。"""
    at = _run("mkt3_tied_in_one_card")
    assert not at.exception, at.exception
    assert any("資金與匯率卡：資料未備／不適用" in t for t in _rendered(at)), \
        "卡內同級時那句兩個字面值的燈文案沒有畫出來"
    at = _run("two_cards_tied")
    assert not at.exception, at.exception
    assert any("風險情緒卡：資料未備；資金與匯率卡：不適用" in t for t in _rendered(at)), \
        "三塊之間同級時同時點名兩張卡的燈文案沒有畫出來"
