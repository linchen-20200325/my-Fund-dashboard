"""v19.136 tests — tab6_manual 總經原理教室 sub-tab(從查證版還原)."""
from __future__ import annotations

import sys
import types


def _stub_deps():
    for _m in ("plotly", "plotly.graph_objects"):
        if _m not in sys.modules:
            class _F:
                def __getattr__(self, n):
                    return lambda *a, **k: None
            sys.modules[_m] = _F()
    if "streamlit" not in sys.modules:
        _s = types.ModuleType("streamlit")
        _s.__getattr__ = lambda n: (lambda *a, **k: None)  # type: ignore
        sys.modules["streamlit"] = _s


# v19.174:module-top stub call 拿掉 — 改由 conftest._switch_streamlit_module_per_test
# fixture per-test 裝(避免 stub 污染後續 collect 的 test,例如 AppTest)。
# _stub_deps()


class TestManualClassroom:
    def test_chapters_present_and_10(self):
        from ui.tab6_manual import _PRINCIPLE_CHAPTERS
        assert len(_PRINCIPLE_CHAPTERS) >= 10

    def test_chapters_have_formula_and_case(self):
        """每章須含 📐 公式 + 📜 案例(查證版深度)"""
        from ui.tab6_manual import _PRINCIPLE_CHAPTERS
        for _i, (_t, _b) in enumerate(_PRINCIPLE_CHAPTERS):
            assert "📐" in _b, f"第 {_i+1} 章缺 📐 數學定義"
            assert "📜" in _b, f"第 {_i+1} 章缺 📜 歷史案例"

    def test_fact_corrections_preserved(self):
        """v19.127 查證修正不可在還原時遺失(防退回錯誤版)"""
        from ui.tab6_manual import _PRINCIPLE_CHAPTERS
        _all = "\n".join(b for _, b in _PRINCIPLE_CHAPTERS)
        # 美林矩陣免責 + 倒掛非史上最深 + 無捏造 +5.7%
        assert "各方引用略有出入" in _all
        assert "1981 年來最深" in _all
        assert "+5.7%" not in _all

    def test_no_import_error(self):
        import ui.tab6_manual as m
        assert hasattr(m, "render_manual_tab")
        assert hasattr(m, "_PRINCIPLE_CHAPTERS")
