"""v19.135 tests — tab5 資料診斷 API Key 遮罩 + 來源解析(學 Stock 偵測精度)."""
from __future__ import annotations

import os
import sys
import types


def _stub_deps():
    # stub plotly / pandas-free path(production import 需要,測試不需真渲染)
    for _m in ("plotly", "plotly.graph_objects"):
        if _m not in sys.modules:
            class _F:
                def __getattr__(self, n):
                    return lambda *a, **k: None
            sys.modules[_m] = _F()
    if "streamlit" in sys.modules and getattr(
        sys.modules["streamlit"], "_is_test_stub", False
    ):
        return
    _mod = types.ModuleType("streamlit")
    _mod._is_test_stub = True
    _mod.secrets = {}  # 預設空 secrets

    def _noop(*a, **k):
        return None
    for _n in ("markdown", "caption", "metric", "error", "divider",
               "columns", "warning", "success", "info"):
        setattr(_mod, _n, _noop)
    sys.modules["streamlit"] = _mod


# v19.174:module-top stub call 拿掉 — 改由 conftest._switch_streamlit_module_per_test
# fixture per-test 裝(避免 stub 污染後續 collect 的 test,例如 AppTest)。
# _stub_deps()


class TestMaskKey:
    def test_empty_returns_placeholder(self):
        from ui.tab5_data_guard import _mask_key
        assert _mask_key("") == "(空)"
        assert _mask_key(None) == "(空)"

    def test_short_key_fully_masked(self):
        from ui.tab5_data_guard import _mask_key
        r = _mask_key("abc")
        assert "***" in r and "len=3" in r
        # 短 key 不洩漏任何字元
        assert "abc" not in r

    def test_long_key_shows_head_tail(self):
        from ui.tab5_data_guard import _mask_key
        r = _mask_key("1234567890abcdef")
        assert r.startswith("1234")
        assert r.endswith("(len=16)")
        assert "cdef" in r
        # 中段不洩漏
        assert "567890" not in r

    def test_boundary_8_chars(self):
        """剛好 8 字 → 全遮罩(不露頭尾)"""
        from ui.tab5_data_guard import _mask_key
        r = _mask_key("12345678")
        assert "len=8" in r
        assert "1234" not in r  # 8 字以下全遮


class TestResolveKey:
    def test_env_source(self):
        from ui.tab5_data_guard import _resolve_key
        os.environ["_TEST_FUND_KEY"] = "envvalue1234"
        try:
            r = _resolve_key("_TEST_FUND_KEY")
            assert r["source"] == "os.environ"
            assert r["val"] == "envvalue1234"
            assert "envv" in r["preview"]
        finally:
            del os.environ["_TEST_FUND_KEY"]

    def test_missing_key(self):
        from ui.tab5_data_guard import _resolve_key
        r = _resolve_key("_NONEXISTENT_KEY_XYZ")
        assert r["source"] == "(無)"
        assert r["preview"] == "(未設定)"
        assert r["val"] == ""

    def test_secrets_precedence_over_env(self):
        """st.secrets 優先於 os.environ(對齊 _load_keys)"""
        import streamlit as st
        from ui.tab5_data_guard import _resolve_key
        st.secrets = {"_DUAL_KEY": "secretval1234"}
        os.environ["_DUAL_KEY"] = "envval5678"
        try:
            r = _resolve_key("_DUAL_KEY")
            assert r["source"] == "st.secrets"
            assert r["val"] == "secretval1234"
        finally:
            st.secrets = {}
            del os.environ["_DUAL_KEY"]


class TestSafeSecret:
    def test_toml_parse_error_no_raise(self):
        """st.secrets 拋例外(模擬 TOML 錯)→ 回 (None, err) 不 raise"""
        import streamlit as st
        from ui.tab5_data_guard import _safe_secret

        class _BrokenSecrets:
            def __contains__(self, k):
                raise ValueError("TOML parse error")
            def __getitem__(self, k):
                raise ValueError("TOML parse error")
        st.secrets = _BrokenSecrets()
        try:
            val, err = _safe_secret("ANY_KEY")
            assert val is None
            assert err is not None
            assert "ValueError" in err
        finally:
            st.secrets = {}

    def test_missing_returns_none_none(self):
        import streamlit as st
        from ui.tab5_data_guard import _safe_secret
        st.secrets = {}
        val, err = _safe_secret("NOT_THERE")
        assert val is None and err is None
