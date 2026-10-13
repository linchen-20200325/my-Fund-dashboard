# -*- coding: utf-8 -*-
"""標的探索正式模式的執行期測試（slow lane；需要 streamlit）。

依據客戶 2026-10-13 裁示（B 線標的探索正式模式第一批）與 docs/v2/49_data_integration_plan.md §4.7 第 4 點：
- 把 `page` 模組上的 `fixtures` 換成「一存取就拋錯」的替身，正式模式照樣渲染完成（正控：示範模式必炸）；
- 篩選條件**只有成功儲存的才生效**：輸入欄填了不存 → 結論列與候選清單不動；按存檔 → 下一次重跑才套用；
- 基本資料缺欄：基金照列、缺的格「⬜ 資料未備：<原因>」，畫面上沒有示意字樣、沒有 None；
- `EXP-4` 一成一敗：畫面照實寫哪一鍵成功、哪一鍵失敗。

載入與寫入函式用替身（`tests/ui_v2/_exp_live_stub.py`），不呼叫 `source`、不打任何網路。
"""

import html
import json
import pathlib
import re
import sys

import pytest

# 整檔標 slow：畫面測試不進 fast lane（守衛：tests/ui_v2/test_ui_v2_lane_guards.py）。
pytestmark = pytest.mark.slow

_ROOT = pathlib.Path(__file__).resolve().parents[2]
_HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_HERE))

pytest.importorskip("streamlit", reason="本環境系統 python3 匯入不到 streamlit")

import _exp_live_stub as STUB  # noqa: E402
from ui_v2.exp import live, logic, page  # noqa: E402

_MARK = "正式路徑碰到 fixtures"


class _FixturesThatBite:
    def __getattr__(self, name):
        raise RuntimeError(f"{_MARK}：{name}")


_SCRIPT_LIVE = f"""
import sys
sys.path.insert(0, {str(_ROOT)!r})
sys.path.insert(0, {str(_HERE)!r})
import _exp_live_stub as STUB
from ui_v2.exp import page
page.render(load_live=STUB.load_live, save_live=STUB.save_setting)
"""

_SCRIPT_DEMO = f"""
import sys
sys.path.insert(0, {str(_ROOT)!r})
from ui_v2.exp import page
page.render()
"""


@pytest.fixture(autouse=True)
def _clean_stub():
    STUB.reset()
    yield
    STUB.reset()


def _run(script, monkeypatch):
    from streamlit.testing.v1 import AppTest

    monkeypatch.setattr(page, "fixtures", _FixturesThatBite())
    at = AppTest.from_string(script, default_timeout=60)
    at.run()
    return at


def _text(at) -> str:
    out = [html.unescape(e.value) for e in at.markdown] + [e.value for e in at.caption]
    out += [e.label for e in at.button] + [e.label for e in at.expander] + [e.label for e in at.checkbox]
    return "\n".join(out)


def _lamp(at) -> str:
    hits = [m.group(1) for e in at.markdown for m in re.finditer(r'class="exp-lamp-text">(.*?)</span>', e.value)]
    assert len(hits) == 1, hits
    return html.unescape(hits[0])


def _ok(at):
    assert not at.exception, [e.value for e in at.exception]
    return at


def test_正式模式_fixtures一碰就炸也照樣渲染_缺欄照寫_沒有示意字樣(monkeypatch):
    STUB.STORE["exp_filter_rules"] = json.dumps([{"field": "fund_code", "op": "不等於", "value": "C03"}],
                                                ensure_ascii=False)
    STUB.STORE["exp_visible_columns"] = json.dumps(list(logic.COLUMN_ORDER))
    at = _ok(_run(_SCRIPT_LIVE, monkeypatch))
    text = _text(at)
    assert _MARK not in text
    assert _lamp(at) == "目前條件下有 2 檔"
    assert "⬜ 資料未備：基本資料尚未接入" in text and "⬜ 資料未備：淨值尚未接入" in text
    assert "<th>fund_code</th>" in text and ">A01</td>" in text and ">B02</td>" in text and ">C03</td>" not in text
    assert "示意" not in text and "None" not in text
    assert not at.warning  # 沒有 session state 與 widget 預設值相衝的警告
    assert not re.search(r"·\s*情境 ", text)


def test_正控_同一個替身之下示範模式一定會炸(monkeypatch):
    at = _run(_SCRIPT_DEMO, monkeypatch)
    assert at.exception and any(_MARK in e.value for e in at.exception)


def test_只吃已存值_填了不存不生效_存檔後下一次重跑才套用(monkeypatch):
    at = _ok(_run(_SCRIPT_LIVE, monkeypatch))
    assert _lamp(at) == logic.TEXT_NO_CONDITION
    at.button(key="exp1live_btn_0").click().run()            # 新增條件
    _ok(at)
    at.text_input(key="exp1live_1_field").input("fund_code")
    at.text_input(key="exp1live_1_op").input("等於")
    at.text_input(key="exp1live_1_value").input("A01").run()
    _ok(at)
    assert _lamp(at) == logic.TEXT_NO_CONDITION              # 未存：正式結果不動
    assert logic.TEXT_UNSAVED_RULES in _text(at)
    assert STUB.SAVES == []
    at.button(key="exp1live_btn_1").click().run()            # 存檔
    _ok(at)
    assert STUB.SAVES == [("exp_filter_rules", '[{"field": "fund_code", "op": "等於", "value": "A01"}]', "rules")]
    assert _lamp(at) == "目前條件下有 1 檔"                    # 重跑重新讀已存值 → 生效
    assert logic.TEXT_UNSAVED_RULES not in _text(at)
    assert live.TEXT_SAVED in _text(at)


def test_存檔失敗_條件列留在畫面上_正式結果不變(monkeypatch):
    STUB.FAIL_KEYS.add("exp_filter_rules")
    at = _ok(_run(_SCRIPT_LIVE, monkeypatch))
    at.button(key="exp1live_btn_0").click().run()
    at.text_input(key="exp1live_1_field").input("fund_code")
    at.text_input(key="exp1live_1_op").input("等於")
    at.text_input(key="exp1live_1_value").input("A01").run()
    at.button(key="exp1live_btn_1").click().run()
    _ok(at)
    text = _text(at)
    assert "存檔寫入失敗：exp_filter_rules：exp_filter_rules 寫入失敗（測試注入）" in text
    assert at.text_input(key="exp1live_1_value").value == "A01"
    assert _lamp(at) == logic.TEXT_NO_CONDITION


def test_EXP4一成一敗_畫面照實寫哪一鍵成功哪一鍵失敗(monkeypatch):
    STUB.FAIL_KEYS.add("exp_sort_column")
    at = _ok(_run(_SCRIPT_LIVE, monkeypatch))
    at.checkbox(key="exp4live_col_ccy").check().run()
    _ok(at)
    assert live.TEXT_UNSAVED_EXP4 in _text(at)
    at.button(key="exp4live_btn_0").click().run()
    _ok(at)
    text = _text(at)
    assert "exp_visible_columns：已存檔" in text
    assert "存檔寫入失敗：exp_sort_column：exp_sort_column 寫入失敗（測試注入）" in text
    assert STUB.STORE == {"exp_visible_columns": '["ccy"]'}


def test_EXP5加入觀察清單_寫已存與勾起的聯集(monkeypatch):
    STUB.STORE["exp_filter_rules"] = json.dumps([{"field": "fund_code", "op": "不等於", "value": "C03"}],
                                                ensure_ascii=False)
    STUB.STORE["exp_watchlist"] = '["Z09"]'
    at = _ok(_run(_SCRIPT_LIVE, monkeypatch))
    at.checkbox(key="exp2_觀察清單_A01__live").check().run()
    _ok(at)
    at.button(key="exp5live_btn_0").click().run()
    _ok(at)
    assert STUB.STORE["exp_watchlist"] == '["A01", "Z09"]'
