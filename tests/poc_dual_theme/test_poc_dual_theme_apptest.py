# -*- coding: utf-8 -*-
"""雙模式隔離 PoC：AppTest（Streamlit 1.59.x，不開瀏覽器）。

驗：預設淺色、淺→深→淺、多次切換、rerun 後其他 widget 狀態保留、新 session 回到預設（session-only；**這不是持久化**）、
模式權威只有一個 session_state 鍵、未知模式 Fail Loud、缺資料檢視不出現數字、SVG 沒有寫死色碼。
"""
import pathlib
import re

import pytest

pytest.importorskip("streamlit", reason="本環境匯入不到 streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

_ROOT = pathlib.Path(__file__).resolve().parents[2]
_APP = str(_ROOT / "poc" / "dual_theme_isolated" / "app_poc.py")
KEY_MODE = "poc_theme_mode"
_STYLE = re.compile(r'data-poc-theme="(light|dark)"')


def _run() -> AppTest:
    at = AppTest.from_file(_APP, default_timeout=60).run()
    assert not at.exception, at.exception
    return at


def _css_mode(at: AppTest):
    found = [m.group(1) for md in at.markdown for m in [_STYLE.search(md.value)] if m]
    assert len(found) == 1, f"應該恰好一個 PoC 樣式區塊，實得 {found}"
    return found[0]


def _set_mode(at: AppTest, mode: str) -> AppTest:
    at.radio(key=KEY_MODE).set_value(mode).run()
    assert not at.exception, at.exception
    return at


def test_default_is_light_on_new_session():
    at = _run()
    assert at.radio(key=KEY_MODE).value == "light"
    assert _css_mode(at) == "light"


def test_light_dark_light_roundtrip():
    at = _run()
    _set_mode(at, "dark")
    assert at.radio(key=KEY_MODE).value == "dark" and _css_mode(at) == "dark"
    _set_mode(at, "light")
    assert at.radio(key=KEY_MODE).value == "light" and _css_mode(at) == "light"


def test_many_switches_stay_consistent():
    at = _run()
    for i in range(12):
        target = "dark" if i % 2 == 0 else "light"
        _set_mode(at, target)
        assert _css_mode(at) == target and at.session_state[KEY_MODE] == target


def test_other_widget_states_survive_switches():
    at = _run()
    at.radio(key="poc_view").set_value("甲").run()
    at.radio(key="poc_period").set_value("3M").run()
    for target in ("dark", "light", "dark", "light"):
        _set_mode(at, target)
        assert at.radio(key="poc_view").value == "甲", target
        assert at.radio(key="poc_period").value == "3M", target
        assert not at.exception


def test_new_session_resets_to_default_not_persisted():
    """session-only 的文件化：同一個 AppTest 內保留；**全新** AppTest（＝新 session）回到預設淺色。這不是持久化，也不應被讀成持久化。"""
    first = _run()
    _set_mode(first, "dark")
    assert _css_mode(first) == "dark"
    second = _run()
    assert second.radio(key=KEY_MODE).value == "light" and _css_mode(second) == "light"
    assert _css_mode(first) == "dark"  # 舊 session 不受影響


def test_mode_authority_is_the_single_session_state_key():
    """直接寫 session_state 的鍵就能決定模式（沒有第二個狀態來源）；`mode_state` 文字與 CSS 都跟著它。"""
    at = _run()
    at.session_state[KEY_MODE] = "dark"
    at.run()
    assert not at.exception
    assert _css_mode(at) == "dark"
    assert any("深色" in md.value and "目前模式" in md.value for md in at.markdown)


def test_unknown_mode_fails_loud():
    """`current_mode()` 讀到未知值必須 raise（不得靜默退回預設）。用最小腳本直接呼叫它（不經 radio，避免 AppTest 自己解析 radio 值而混淆來源）。"""
    script = f"""
import sys
sys.path.insert(0, {str(_ROOT / "poc" / "dual_theme_isolated")!r})
import streamlit as st
import poc_page
st.session_state[{KEY_MODE!r}] = "sepia"
poc_page.current_mode()
"""
    at = AppTest.from_string(script, default_timeout=30).run()
    assert at.exception and "sepia" in at.exception[0].value, "未知模式必須 Fail Loud"
    ok = AppTest.from_string(script.replace('"sepia"', '"dark"'), default_timeout=30).run()
    assert not ok.exception


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_missing_view_shows_no_numbers_and_no_chart(mode):
    at = _run()
    _set_mode(at, mode)
    at.radio(key="poc_view").set_value("丙（資料未備示範）").run()
    assert not at.exception
    html = "\n".join(md.value for md in at.markdown)
    assert "<svg" not in html, "缺資料檢視不得畫圖"
    m = re.search(r'data-field="chart_missing">(.*?)</div>', html, re.S)
    assert m, "找不到缺資料呈現區塊"
    text = re.sub(r"<[^>]+>", "", m.group(1))
    assert "◇ 資料未備" in text
    assert not re.search(r"\d", text), f"缺資料不得出現數字：{text!r}"


@pytest.mark.parametrize("period", ["3M", "6M", "1Y", "3Y"])
def test_all_periods_render_in_dark(period):
    at = _run()
    _set_mode(at, "dark")
    at.radio(key="poc_period").set_value(period).run()
    assert not at.exception
    assert any("<svg" in md.value for md in at.markdown)


def test_svg_has_no_hardcoded_colors_and_has_axis_labels_and_legend():
    at = _run()
    html = "\n".join(md.value for md in at.markdown)
    svg = re.search(r"<svg.*?</svg>", html, re.S).group(0)
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b|rgb\(|rgba\(|stroke=\"|fill=\"(?!none)", svg), "SVG 不得寫死色碼（色由 CSS class 決定）"
    assert "<title" in svg and "<desc" in svg and "poc-tick" in svg and "poc-endlabel" in svg
    assert "虛線" in html and "實線" in html, "圖例需有非顏色辨識"


def test_chips_carry_symbol_and_wording_in_both_modes():
    for mode in ("light", "dark"):
        at = _run()
        _set_mode(at, mode)
        html = "\n".join(md.value for md in at.markdown)
        chips = re.findall(r'<span class="poc-chip[^"]*" data-status-key="([a-z_]+)">([^<]+)</span>', html)
        keys = {k for k, _ in chips}
        assert {"attention", "missing", "undetermined", "failed", "stale", "neutral"} <= keys
        for key, label in chips:
            assert re.match(r"^[^\w\s]", label) and len(label) > 2, f"chip 需符號＋字樣：{key} {label!r}"
