"""test_story_nav — 決策動線敘事導覽列（純函式）v19.405 Phase 4 對齊 6→5 分頁

只測內容層 `story_nav_markdown`（不涉 streamlit）；`render_story_nav` 走 st.caption，
由 app smoke / AppTest 覆蓋。
"""
from __future__ import annotations

from ui.helpers.story_nav import _STEPS, story_nav_markdown


def test_story_nav_highlights_current_step():
    md = story_nav_markdown("portfolio")
    assert "**:blue[④ 📊 配置 & 帳本]**" in md    # 目前站：藍色粗體
    assert ":gray[① 🌐 市場定調]" in md            # 其餘站：灰色
    assert "記帳 + 再平衡" in md                    # 目前站提示


def test_story_nav_all_steps_present():
    md = story_nav_markdown("macro")
    for _key, _label, _hint in _STEPS:
        assert _label in md
    assert "**:blue[① 🌐 市場定調]**" in md


def test_story_nav_health_step_valid():
    """v19.405 Phase 4 新增第 2 站『組合健診』→ health 為合法 current key。"""
    md = story_nav_markdown("health")
    assert "**:blue[② 💊 組合健診]**" in md
    assert "吃本金" in md


def test_story_nav_invalid_current_no_highlight():
    md = story_nav_markdown("nope")
    assert ":blue[" not in md          # 沒有任何站被 highlight
    assert ":gray[" in md              # 四站都灰


def test_story_nav_order_decision_flow():
    """順序必須是 市場定調 → 組合健診 → 個基深掘 → 配置&帳本（決策動線）。"""
    keys = [s[0] for s in _STEPS]
    assert keys == ["macro", "health", "fund", "portfolio"]
