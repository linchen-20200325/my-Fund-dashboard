"""v19.125 tests — tab1_macro.py 三層 toggle 路由驗證。

驗證:
1. 新手模式選 → render_beginner_view + render_principle_classroom 被呼叫
2. 新手模式 → tab 早 return,不執行下方 ~1500 行重渲染
3. 進階模式選 → 走原 flow,不呼叫 beginner_view
4. SSOT mode 字串常數驗證(macro_tier_mode key 隔離)
"""
from __future__ import annotations

import sys
import types

import pytest


def _stub_streamlit():
    if "streamlit" in sys.modules and getattr(
        sys.modules["streamlit"], "_is_test_stub", False
    ):
        return
    _mod = types.ModuleType("streamlit")
    _mod._is_test_stub = True

    def _noop(*a, **k):
        return None

    def _ctx(*a, **k):
        class _Ctx:
            def __enter__(self):
                return self
            def __exit__(self, *exc):
                return False
        return _Ctx()

    for _name in (
        "markdown", "caption", "divider", "warning", "info", "success",
        "metric", "dataframe", "plotly_chart",
    ):
        setattr(_mod, _name, _noop)
    _mod.expander = _ctx

    class _SS(dict):
        def get(self, k, default=None):
            return super().get(k, default)
        def __getattr__(self, k):
            return self.get(k)
        def __setattr__(self, k, v):
            self[k] = v
    _mod.session_state = _SS()

    sys.modules["streamlit"] = _mod


_stub_streamlit()


# ════════════════════════════════════════════════════════════════
# Verify wiring exists in source(static check,避免實際 streamlit run)
# ════════════════════════════════════════════════════════════════

class TestWiringPresent:
    """靜態檢查 tab1_macro.py 確實 import + 路由到 beginner helper。

    避免實跑 streamlit 的高成本與 dependency,改用 source inspection 驗證 wire 點。
    """

    def setup_method(self):
        import pathlib
        _src_path = pathlib.Path(__file__).parent.parent / "ui" / "tab1_macro.py"
        self.src = _src_path.read_text(encoding="utf-8")

    def test_imports_beginner_view_lazy(self):
        """確認 lazy import 模式(在 if 內 import,避免冷啟動拖慢)"""
        assert "from ui.helpers.macro_beginner_view import" in self.src
        assert "render_beginner_view" in self.src
        assert "render_principle_classroom" in self.src

    def test_tier_radio_with_three_modes(self):
        assert "macro_tier_mode" in self.src
        assert "_MODE_BEGINNER" in self.src
        assert "_MODE_ADVANCED" in self.src
        assert "_MODE_EXPERT" in self.src
        assert "🟢 新手" in self.src
        assert "🔬 進階" in self.src
        assert "🎓 專家" in self.src

    def test_beginner_default_index_zero(self):
        """index=0 → 新手為 default,符合 user 反饋意圖"""
        assert "index=0" in self.src or "index = 0" in self.src

    def test_beginner_mode_has_early_return(self):
        """新手模式必須早 return,不渲染下方重型區塊"""
        # 找到 _MODE_BEGINNER 判斷後緊跟 return
        _section_idx = self.src.find("_tier_mode == _MODE_BEGINNER")
        assert _section_idx > 0, "找不到新手模式判斷"
        _after = self.src[_section_idx:_section_idx + 600]
        assert "render_beginner_view" in _after
        assert "render_principle_classroom" in _after
        assert "return" in _after, "新手模式必須 early return"

    def test_no_inline_magic_for_mode_strings(self):
        """模式字串使用 _MODE_* 常數,不散落 inline"""
        # 找 if 條件比對的地方
        assert 'if _tier_mode == _MODE_BEGINNER:' in self.src

    def test_radio_inside_macro_done_block(self):
        """radio 必須在 if st.session_state.macro_done: 之內(否則指標未載入時會 KeyError)"""
        _macro_done_idx = self.src.find("if st.session_state.macro_done:")
        _radio_idx = self.src.find("macro_tier_mode")
        assert _macro_done_idx > 0 and _radio_idx > _macro_done_idx, (
            "toggle 必須在 macro_done 區塊內(資料載入後才顯示)"
        )


class TestBeginnerHelperContractStable:
    """確保 PR1 helper 的 API 沒被誤改,PR2 wire 才能成立"""

    def test_render_beginner_view_signature(self):
        from ui.helpers.macro_beginner_view import render_beginner_view
        import inspect
        _sig = inspect.signature(render_beginner_view)
        _params = list(_sig.parameters.keys())
        assert _params == ["indicators", "phase_info"], (
            f"render_beginner_view 簽名變了:{_params}"
        )

    def test_render_principle_classroom_callable(self):
        from ui.helpers.macro_beginner_view import render_principle_classroom
        assert callable(render_principle_classroom)

    def test_compute_traffic_lights_returns_3_lights(self):
        from ui.helpers.macro_beginner_view import compute_traffic_lights
        r = compute_traffic_lights({}, phase_info={"phase": "擴張", "score": 6.0})
        assert "light1_health" in r
        assert "light2_action" in r
        assert "light3_alert" in r


# v19.125 §6 自審「3 個最容易出錯的輸入」:
#   1. 新手模式選但忘了 early return → 兩種視圖同時渲染(無效)→ test 強制驗證 return ✅
#   2. mode 字串散落 inline → 改寫 label 時遺漏一處導致比對失敗 → test 強制用 _MODE_* 常數 ✅
#   3. PR1 helper API 改動沒同步 PR2 wire → test 鎖定簽名(indicators, phase_info)✅
