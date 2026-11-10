"""scripts/update_macro_history.py 例外訊息不得帶出網址查詢字串／api_key(2026-11-10 資安最小修補)。

假 Key 於執行期組成,不在原始碼寫出真實 Key 樣態字串;無真實 HTTP。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

pytest.importorskip("pandas")
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))
_spec = importlib.util.spec_from_file_location(
    "update_macro_history_leakcheck", _REPO_ROOT / "scripts" / "update_macro_history.py")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

_FAKE = "FAKE" + "KEY" * 4  # 執行期組字串


class _Resp:
    def __init__(self, status, text=""):
        self.status_code, self.text = status, text


def test_scrub_exc_removes_query_and_api_key():
    e = ConnectionError(
        f"HTTPSConnectionPool(host='x', port=443): Max retries exceeded with url: "
        f"/fred/series/observations?series_id=DGS10&api_key={_FAKE}&file_type=json (Caused by X)")
    out = _mod._scrub_exc(e)
    assert _FAKE not in out and "api_key=" not in out
    assert "Max retries exceeded" in out
    out2 = _mod._scrub_exc(ValueError(f"bad api_key={_FAKE} here"))
    assert _FAKE not in out2 and "api_key=<redacted>" in out2


def test_fred_connection_error_output_has_no_key(monkeypatch, capsys):
    def _boom(url, **kw):
        raise ConnectionError(f"Max retries exceeded with url: /x?api_key={_FAKE}&series_id=DGS10")
    monkeypatch.setattr(_mod.requests, "get", _boom)
    df = _mod._fred_get_single("DGS10", _mod._dt.date(2026, 1, 1), _mod._dt.date(2026, 1, 2), _FAKE)
    out = capsys.readouterr().out
    assert df.empty
    assert _FAKE not in out
    assert "DGS10" in out and "ConnectionError" in out


def test_fred_http_non_200_output_has_no_key(monkeypatch, capsys):
    monkeypatch.setattr(_mod.requests, "get", lambda url, **kw: _Resp(500, "server error"))
    df = _mod._fred_get_single("DGS10", _mod._dt.date(2026, 1, 1), _mod._dt.date(2026, 1, 2), _FAKE)
    out = capsys.readouterr().out
    assert df.empty and _FAKE not in out and "HTTP=500" in out


def test_fetch_fallback_direct_get_error_has_no_key(monkeypatch, capsys):
    import builtins
    real_import = builtins.__import__

    def _no_helpers(name, *a, **k):
        if name in ("infra.proxy_helper", "repositories.macro_repository"):
            raise ImportError(name)
        return real_import(name, *a, **k)
    monkeypatch.setattr(builtins, "__import__", _no_helpers)

    def _boom(url, **kw):
        raise ConnectionError(f"Max retries exceeded with url: /x?api_key={_FAKE}")
    monkeypatch.setattr(_mod.requests, "get", _boom)
    assert _mod._fetch_url_via_proxy("https://example.invalid/x", params={"api_key": _FAKE}) is None
    out = capsys.readouterr().out
    assert _FAKE not in out and "ConnectionError" in out
