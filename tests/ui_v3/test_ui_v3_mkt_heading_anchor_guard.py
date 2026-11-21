# -*- coding: utf-8 -*-
"""🌍 市場頁不得產生 Streamlit 標題錨點連結（靜態守衛；不需瀏覽器）。

背景（A2 實際操作 QA，`docs/evidence/ui_a2_mkt_ops_qa_2026_11_21/report.md`）：`st.markdown` 內的 `<h3>`／`<h4>` 與未帶 `anchor=False` 的 `st.title`
會被 Streamlit 加上 `Link to heading` 錨點連結——平時看不見（hover 才現），但每個都是一個**鍵盤停駐點**，焦點環看不見、名稱是英文。
💼 `assets.py` 與 `nas_diag.py` 早已改成 `st.title(..., anchor=False)` 加 `<div role="heading" aria-level>`；🌍 頁補齊同一慣例。
瀏覽器級（真的 Tab 走一遍）見 `test_ui_v3_market_page_browser.py::test_no_heading_anchor_links_and_no_keyboard_stop_on_them`。
"""
import ast
import pathlib
import re

import pytest

_SRC = (pathlib.Path(__file__).resolve().parents[2] / "ui_v3" / "pages" / "mkt.py").read_text(encoding="utf-8")
HEADING_TAG = re.compile(r"<h[1-6][\s>]", re.IGNORECASE)


def _title_calls(src):
    out = []
    for node in ast.walk(ast.parse(src)):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in ("title", "header", "subheader")
                and isinstance(node.func.value, ast.Name) and node.func.value.id == "st"):
            out.append({k.arg: ast.literal_eval(k.value) if isinstance(k.value, ast.Constant) else None for k in node.keywords})
    return out


def test_mkt_page_source_has_no_markdown_heading_tag():
    assert not HEADING_TAG.search(_SRC)


def test_mkt_page_title_calls_disable_the_anchor():
    calls = _title_calls(_SRC)
    assert calls and all(c.get("anchor") is False for c in calls), calls


def test_mkt_headings_keep_semantics_via_role_and_level():
    assert _SRC.count('role="heading" aria-level="3"') == 1 and _SRC.count('role="heading" aria-level="4"') == 2   # 3 個產生點（Secondary 卡、依據卡各 1 個 4 級來源）


@pytest.mark.parametrize("src", ['import streamlit as st\nst.title("x")\n', 'import streamlit as st\nst.title("x", anchor=True)\n',
                                 'import streamlit as st\nst.subheader("x")\n'])
def test_negative_control_title_anchor_checker_turns_red(src):
    assert not all(c.get("anchor") is False for c in _title_calls(src))


@pytest.mark.parametrize("snippet", ["<h3>x</h3>", "<H4 id=a>x</H4>", "<h1\n>x</h1>"])
def test_negative_control_heading_tag_checker_turns_red(snippet):
    assert HEADING_TAG.search("md('" + snippet + "')")


WORD_BREAK_RULE = re.compile(r"\.uv3-hd\{\{[^}]*word-break:break-word")


def test_mkt_heading_css_keeps_the_streamlit_heading_word_break():
    """改成 role=heading 的 div 後，仍須與原 h3／h4 同為 `word-break:break-word`（真瀏覽器 computed style 比對發現的唯一非預期差異）。"""
    assert WORD_BREAK_RULE.search(_SRC)


@pytest.mark.parametrize("css", [".uv3-hd{{display:block;font-weight:600}}", ".uv3-hd{{display:block;word-break:normal}}",
                                 ".uv3-hd{{display:block}} .x{{word-break:break-word}}", ".uv3-hd4{{word-break:break-word}}"])
def test_negative_control_word_break_checker_turns_red(css):
    assert not WORD_BREAK_RULE.search(css)
