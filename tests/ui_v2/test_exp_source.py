# -*- coding: utf-8 -*-
"""ui_v2/exp/source.py 的接縫測試（fast lane；不打網路、不需要 streamlit 執行期）。

L2 與 `st` 一律以替身注入（monkeypatch `source` 模組上的引用），不呼叫任何 L1。體例同 tests/ui_v2/test_mkt_source.py。
"""

from __future__ import annotations

import json
import pathlib
import secrets as _rnd
import sys
import types

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

from ui_v2.exp import fixtures, live  # noqa: E402

source = pytest.importorskip("ui_v2.exp.source")  # 需要 L1 的相依（gspread、streamlit 等）

_OK_POOL = {"status": "ok", "backend": "service_account", "codes": ["B02", "A01"], "dropped_blank": 0,
            "duplicates": 0, "message": None}


@pytest.fixture
def fake_st(monkeypatch):
    st = types.SimpleNamespace(secrets={}, session_state={})
    monkeypatch.setattr(source, "st", st)
    return st


def _settings_rows(**values):
    return {"rows": {k: {"setting_key": k, "setting_value": v} for k, v in values.items()},
            "bad_rows": [], "broken_keys": [], "blank_rows": 0, "tab_missing": False}


def test_load_live形狀_dataset與fixtures同形_母體只來自L2的代碼(monkeypatch, fake_st):
    seen = []
    monkeypatch.setattr(source.exp_universe, "load_pool_codes",
                        lambda values, oauth_client=None: seen.append(oauth_client) or dict(_OK_POOL))
    monkeypatch.setattr(source.settings_store, "load_user_settings",
                        lambda values: _settings_rows(exp_watchlist='["A01"]'))
    data = source.load_live()
    assert set(data) == {"dataset", "notes"}
    assert set(data["dataset"]) == set(fixtures.scenario("full")["dataset"])
    assert [r["fund_code"] for r in data["dataset"]["fund_profile"]] == ["B02", "A01"]
    assert data["notes"]["pool"] == _OK_POOL
    assert data["notes"]["settings"][live.KEY_WATCH] == ("A01",)
    assert data["notes"]["settings_error"] is None
    assert seen == [None]                                    # ui_v2 沒有取登入者 client 的途徑，恆傳 None


def test_設定讀不到_回訊息_與沒設定分開(monkeypatch, fake_st):
    monkeypatch.setattr(source.exp_universe, "load_pool_codes", lambda values, oauth_client=None: dict(_OK_POOL))

    def boom(values):
        raise source.settings_store.SettingsSheetError("讀設定失敗（測試）", code="api")

    monkeypatch.setattr(source.settings_store, "load_user_settings", boom)
    data = source.load_live()
    assert data["notes"]["settings_error"] == "讀設定失敗（測試）"
    assert data["notes"]["settings"] == live.EMPTY_SETTINGS


def test_分頁不存在是沒設定_不是錯誤(monkeypatch, fake_st):
    monkeypatch.setattr(source.exp_universe, "load_pool_codes", lambda values, oauth_client=None: dict(_OK_POOL))
    monkeypatch.setattr(source.settings_store, "load_user_settings",
                        lambda values: {"rows": {}, "bad_rows": [], "broken_keys": [], "blank_rows": 0,
                                        "tab_missing": True})
    data = source.load_live()
    assert data["notes"]["settings_error"] is None and data["notes"]["settings"] == live.EMPTY_SETTINGS


def test_秘密值取自st_secrets_環境變數與登入權杖_交給L2(monkeypatch, fake_st):
    key, token = _rnd.token_hex(12), _rnd.token_hex(12)
    fake_st.secrets = {"FRED_API_KEY": key}
    fake_st.session_state = {"gsheet_tokens": {"access_token": token}}
    got = {}
    monkeypatch.setattr(source.exp_universe, "load_pool_codes",
                        lambda values, oauth_client=None: got.setdefault("pool", list(values)) and dict(_OK_POOL))
    monkeypatch.setattr(source.settings_store, "load_user_settings",
                        lambda values: got.setdefault("settings", list(values)) and _settings_rows())
    monkeypatch.setattr(source.settings_store, "save_setting_for_page",
                        lambda k, v, kind, values: got.setdefault("save", (k, v, kind, list(values))) and
                        {"status": "saved", "key": k})
    source.load_live()
    assert key in got["pool"] and token in got["pool"] and key in got["settings"]
    out = source.save_setting("exp_watchlist", json.dumps(["A01"]), "list")
    assert out["status"] == "saved"
    assert got["save"][:3] == ("exp_watchlist", '["A01"]', "list") and key in got["save"][3]


def test_source不import_fixtures():
    import ast

    tree = ast.parse(pathlib.Path(source.__file__).read_text(encoding="utf-8"))
    names = [a.name for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom)) for a in n.names]
    assert names and "fixtures" not in names
