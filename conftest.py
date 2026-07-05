"""pytest conftest — 跨 test 共用 fixture

v18.58: TTL fetch cache 是模組層 dict，跨 test 會互相污染（A 測試 mock
fetcher 回 X，B 測試以為 mock 自己的 fetcher 但 cache hit 拿到 A 的 X）。
這裡 autouse fixture 在每個 test 開始前清空所有快取。

v19.174:`_complete_streamlit_stub()` helper — 8 個 test 檔在 import-time
注入 streamlit stub 到 sys.modules,但 stub 缺 `secrets` / `cache_data` /
`cache_resource` / `session_state` 等屬性,導致**之後 collect 的 test**
(不裝 stub 的)拿到不完整 module → `AttributeError: module 'streamlit' has
no attribute 'session_state'` 等。本 helper 提供完整補強,8 個 stub 改用
單一進入點,確保 surface 統一。
"""
import sys
import types
from typing import Any

import pytest


# ════════════════════════════════════════════════════════════════
# v19.174 Group A:streamlit stub completeness helper
# ════════════════════════════════════════════════════════════════
class _FakeSessionState(dict):
    """模擬 st.session_state:dict + attribute 雙存取。"""
    def __getattr__(self, k):
        return self.get(k)
    def __setattr__(self, k, v):
        self[k] = v


def _stub_noop(*a, **k):
    """no-op 替身,通用 streamlit render 函式。"""
    return None


def _stub_ctx(*a, **k):
    """no-op context manager 替身(`with st.expander(...)` / `with st.container()`等)。"""
    class _Ctx:
        def __enter__(self): return self
        def __exit__(self, *e): return False
    return _Ctx()


def _stub_cache_decorator(*args, **kwargs):
    """pass-through decorator,支援 `@st.cache_data` 與 `@st.cache_data(ttl=...)` 兩種寫法。"""
    if args and callable(args[0]):
        return args[0]
    return lambda f: f


def _complete_streamlit_stub(mod: types.ModuleType) -> types.ModuleType:
    """補強 streamlit stub 到「核心 surface 全有」狀態。

    7 個 test 檔(test_fund_grp_health_extras_p0/p1_*、test_macro_beginner_view、
    test_tab1_threshold_lines、test_tab5_key_diagnostic)
    在 import-time `sys.modules['streamlit'] = mod`。若 mod 缺常用屬性,後 collect
    的 test 拿不到 → AttributeError 連鎖。本函式做 idempotent 補強,只加缺的屬性,
    不覆寫既有(各 stub 可以保有自己客製過的特定函式)。

    Returns
    -------
    同一個 mod(就地補,不複製)。
    """
    # ── State + cache 核心 4 件 ─────────────────────────
    if not hasattr(mod, "session_state"):
        mod.session_state = _FakeSessionState()
    if not hasattr(mod, "secrets"):
        mod.secrets = {}
    if not hasattr(mod, "cache_data"):
        mod.cache_data = _stub_cache_decorator
        mod.cache_data.clear = _stub_noop
    if not hasattr(mod, "cache_resource"):
        mod.cache_resource = _stub_cache_decorator
        mod.cache_resource.clear = _stub_noop

    # ── 常用 render 函式(no-op) ─────────────────────────
    for _name in (
        "markdown", "caption", "divider", "info", "success", "warning", "error",
        "metric", "dataframe", "plotly_chart", "code", "write", "text", "table",
        "header", "subheader", "title", "json", "image", "video", "audio",
        "toast", "balloons", "snow", "stop", "rerun", "set_page_config",
        "sidebar", "altair_chart", "bokeh_chart", "graphviz_chart", "map",
        "pyplot", "vega_lite_chart", "latex", "echo", "help", "exception",
        "experimental_rerun", "experimental_set_query_params",
        "experimental_get_query_params", "experimental_singleton",
        "experimental_memo", "switch_page", "page_link", "link_button",
    ):
        if not hasattr(mod, _name):
            setattr(mod, _name, _stub_noop)

    # ── 互動 input(回傳預設值,不真實渲染) ───────────────
    for _name, _default in (
        ("button", False), ("checkbox", False), ("radio", None),
        ("selectbox", None), ("slider", None), ("number_input", 0),
        ("text_input", ""), ("text_area", ""),
        ("date_input", None), ("time_input", None),
        ("file_uploader", None), ("color_picker", "#000000"),
        ("download_button", False),
    ):
        if not hasattr(mod, _name):
            setattr(mod, _name, (lambda *a, _d=_default, **k: _d))

    # ── Context managers ────────────────────────────────
    for _name in ("expander", "container", "spinner", "empty", "form"):
        if not hasattr(mod, _name):
            setattr(mod, _name, _stub_ctx)
    if not hasattr(mod, "tabs"):
        mod.tabs = lambda labels: [_stub_ctx() for _ in labels]
    if not hasattr(mod, "columns"):
        mod.columns = lambda spec, **k: [_stub_ctx() for _ in range(spec if isinstance(spec, int) else len(spec))]
    if not hasattr(mod, "progress"):
        mod.progress = lambda *a, **k: _stub_ctx()

    return mod


def install_streamlit_stub() -> types.ModuleType:
    """8 個 stub-installer test 檔的統一入口。

    若 `streamlit` 已存在 + 是測試 stub → 直接補強並回。
    若是真 streamlit → 不動(避免污染需要真 streamlit 的 test)。
    若不存在 → 建新 stub 並補強。
    """
    existing = sys.modules.get("streamlit")
    if existing is not None and getattr(existing, "_is_test_stub", False):
        return _complete_streamlit_stub(existing)
    if existing is not None and not getattr(existing, "_is_test_stub", False):
        # 真 streamlit 已 import → 不動,呼叫端應自行 monkeypatch
        return existing
    mod = types.ModuleType("streamlit")
    mod._is_test_stub = True
    _complete_streamlit_stub(mod)
    sys.modules["streamlit"] = mod
    return mod


@pytest.fixture(autouse=True)
def _clear_fetch_cache_between_tests():
    """每個 test 前後清空模組層 TTL cache，避免測試污染。"""
    try:
        from fund_fetcher import clear_all_caches as _cac
        _cac()
    except Exception:
        pass
    yield
    try:
        from fund_fetcher import clear_all_caches as _cac
        _cac()
    except Exception:
        pass


# ════════════════════════════════════════════════════════════════
# v19.174 Group A:capture 真 streamlit + dynamic switch per test
# ════════════════════════════════════════════════════════════════
# 在 conftest import 早期捕捉真 streamlit。7 個 stub-installer test 檔
# (test_fund_grp_health_extras_p0 / p1_ai / p1_news_ratio / p1_visual、
#  test_macro_beginner_view、test_tab1_threshold_lines、
#  test_tab5_key_diagnostic)在 import-time 把 stub 蓋進 sys.modules,
# 之後跑「需要真 streamlit」的 test(如 AppTest)會炸。
# autouse fixture 在每個 test 之前,根據 test path 動態切換正確的 module。
try:
    import streamlit as _REAL_ST
    if not getattr(_REAL_ST, "_is_test_stub", False):
        _CAPTURED_REAL_STREAMLIT = _REAL_ST
    else:
        _CAPTURED_REAL_STREAMLIT = None
except Exception:
    _CAPTURED_REAL_STREAMLIT = None

# 已知安裝 stub 的 7 個 test 檔(由 grep 確認):這些 test 要 stub
# (v19.317:test_manual_classroom.py 隨總經原理教室瘦身退役,已從清單移除)
_STUB_INSTALLER_FILES = frozenset({
    "test_fund_grp_health_extras_p0.py",
    "test_fund_grp_health_extras_p1_ai.py",
    "test_fund_grp_health_extras_p1_news_ratio.py",
    "test_fund_grp_health_extras_p1_visual.py",
    "test_macro_beginner_view.py",
    "test_tab1_threshold_lines.py",
    "test_tab5_key_diagnostic.py",
})


@pytest.fixture(autouse=True)
def _switch_streamlit_module_per_test(request):
    """v19.174 Group A:per-test 切換正確的 streamlit module。

    - test 屬於 8 個 stub-installer 檔之一 → 確保 sys.modules['streamlit'] 是 stub
      (該 test 檔 import 時已 install,本 fixture 確保是完整 stub)
    - 其他 test → 還原真 streamlit(避免被 8 個檔的 stub 污染)
    """
    test_file = request.node.fspath.basename if hasattr(request.node, "fspath") else ""
    mod = sys.modules.get("streamlit")

    if test_file in _STUB_INSTALLER_FILES:
        # 該 test 預期使用 stub。若已是 stub,補強;若不是(被前面 fixture 改回真),重建 stub
        if mod is None or not getattr(mod, "_is_test_stub", False):
            install_streamlit_stub()
        else:
            _complete_streamlit_stub(mod)
    else:
        # 該 test 預期使用真 streamlit。若 streamlit 是 stub,還原真 module
        if mod is not None and getattr(mod, "_is_test_stub", False):
            if _CAPTURED_REAL_STREAMLIT is not None:
                sys.modules["streamlit"] = _CAPTURED_REAL_STREAMLIT
    yield
