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
