"""test_story_nav — v18.193 故事化敘事導覽列（純函式）

只測內容層 `story_nav_markdown`（不涉 streamlit）；`render_story_nav` 走 st.caption，
由 app smoke / AppTest 覆蓋。
"""
from __future__ import annotations

from ui.helpers.story_nav import _STEPS, story_nav_markdown


def test_story_nav_highlights_current_step():
    md = story_nav_markdown("portfolio")
    assert "**:blue[② 📊 核心/衛星配置]**" in md   # 目前站：藍色粗體
    assert ":gray[① 🌐 總經環境]" in md            # 其餘站：灰色
    assert "決定資產怎麼擺" in md                   # 目前站提示


def test_story_nav_all_three_steps_present():
    md = story_nav_markdown("macro")
    for _key, _label, _hint in _STEPS:
        assert _label in md
    assert "**:blue[① 🌐 總經環境]**" in md


def test_story_nav_invalid_current_no_highlight():
    md = story_nav_markdown("nope")
    assert ":blue[" not in md          # 沒有任何站被 highlight
    assert ":gray[" in md              # 三站都灰


def test_story_nav_order_macro_then_portfolio_then_fund():
    """順序必須是 總經 → 配置 → 單一基金（spec 敘事）。"""
    keys = [s[0] for s in _STEPS]
    assert keys == ["macro", "portfolio", "fund"]
