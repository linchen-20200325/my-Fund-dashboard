# -*- coding: utf-8 -*-
"""BL-0383：淨值歷史 `_sa_to_dict()`／`status()` 認不得 Streamlit secrets 的 TOML table（AttrDict）。

2026-10-20 實測（streamlit 1.59.2）：`[google_service_account]` TOML table 經
`infra.config.get_secret` 取得的是 `streamlit.runtime.secrets.AttrDict` ——
MRO 為 (AttrDict, collections.abc.Mapping, ...)，**不是 dict 子類**。舊 `_sa_to_dict`
只認 dict／JSON 字串，AttrDict 落到「其他型別 → {}」，`status()` 因而回
`enabled=False`、`diag["google_service_account"]="unparseable"`（Tab5 顯示「JSON 解析失敗」）。

本檔不連網、不讀 repo 的任何 secrets 檔：TOML 一律寫進 pytest 的 tmp_path，值全為假。
"""

from __future__ import annotations

import json
from collections.abc import Mapping

import pytest

import infra.config as CFG
from services import nav_history_gs as N

_FAKE_EMAIL = "fake-sa@example.iam.gserviceaccount.com"

_TOML = f'''
FRED_API_KEY = "FAKE"

[google_service_account]
type = "service_account"
client_email = "{_FAKE_EMAIL}"
private_key = "FAKE"
'''

_TOML_NO_EMAIL = '''
FRED_API_KEY = "FAKE"

[google_service_account]
type = "service_account"
private_key = "FAKE"
'''


def _fake_get_secret(monkeypatch, mapping):
    monkeypatch.setattr(CFG, "get_secret", lambda k, default=None: mapping.get(k, default))


@pytest.fixture
def real_st_secrets(monkeypatch, tmp_path):
    """用真的 `streamlit.runtime.secrets.Secrets` 解析一份暫時 secrets.toml，掛到 `st.secrets`。

    走的是正式路徑 `infra.config.get_secret` → `st.secrets.get(...)`，不替換 get_secret。

    ⚠️ 隔離：`Secrets.load_if_toml_exists()` 第一次解析時會呼叫
    `streamlit.watcher.path_watcher.watch_file／watch_dir` 裝 poll 型檔案監看，留下常駐的
    `ThreadPoolExecutor` 執行緒每 0.2 秒呼叫一次 `time.sleep`，測試結束也不會停。後面的測試
    （例：`tests/test_policy_supplement_repository.py` 的 `_five_minutes` 把全域 `time.sleep`
    換成推進假時鐘）會被這些背景執行緒在背後推進時鐘而轉紅。這裡用 monkeypatch 把兩個監看
    函式換成 no-op（測試結束自動還原），並斷言解析前後執行緒數不變。
    """
    import threading

    import streamlit as st
    import streamlit.watcher.path_watcher as _pw
    from streamlit import config as st_config
    from streamlit.runtime.secrets import Secrets

    monkeypatch.setattr(_pw, "watch_file", lambda *a, **k: False)
    monkeypatch.setattr(_pw, "watch_dir", lambda *a, **k: False)

    def _load(toml_text: str):
        threads_before = threading.active_count()
        path = tmp_path / "secrets.toml"
        path.write_text(toml_text, encoding="utf-8")
        old = st_config.get_option("secrets.files")
        st_config.set_option("secrets.files", [str(path)])
        try:
            sec = Secrets()
            sec.load_if_toml_exists()
        finally:
            st_config.set_option("secrets.files", old)
        assert threading.active_count() == threads_before, "解析 secrets 不得留下背景執行緒"
        monkeypatch.setattr(st, "secrets", sec)
        return sec

    return _load


# ── 1. dict + client_email → 原樣（相容不變）──────────────────────────
def test_dict_with_client_email():
    d = {"client_email": _FAKE_EMAIL}
    out = N._sa_to_dict(d)
    assert out is d
    assert out.get("client_email") == _FAKE_EMAIL


# ── 2. 真 st.secrets 解析 TOML table 得 AttrDict + client_email → dict ──
def test_real_streamlit_toml_table_attrdict(real_st_secrets):
    real_st_secrets(_TOML)
    raw = CFG.get_secret("google_service_account")
    # 前提真的成立：正式路徑拿到的是 Mapping 但不是 dict（舊判斷正是栽在這裡）
    assert isinstance(raw, Mapping) and not isinstance(raw, dict)
    assert type(raw).__name__ == "AttrDict"
    out = N._sa_to_dict(raw)
    assert isinstance(out, dict)
    assert out.get("client_email") == _FAKE_EMAIL


def test_attrdict_direct():
    from streamlit.runtime.secrets import AttrDict
    out = N._sa_to_dict(AttrDict({"client_email": _FAKE_EMAIL}))
    assert isinstance(out, dict) and out.get("client_email") == _FAKE_EMAIL


# ── 3. JSON string + client_email → dict（env fallback 形狀）─────────────
def test_json_string_with_client_email():
    out = N._sa_to_dict(json.dumps({"client_email": _FAKE_EMAIL}))
    assert out.get("client_email") == _FAKE_EMAIL


# ── 4. Mapping 缺 client_email → 不得判為有效（diag=no_client_email）─────
def test_mapping_missing_client_email(monkeypatch, real_st_secrets):
    real_st_secrets(_TOML_NO_EMAIL)
    st_ = N.status()
    assert st_["enabled"] is False
    assert "google_service_account" in st_["missing"]
    assert st_["diag"]["google_service_account"] == "no_client_email"

    from streamlit.runtime.secrets import AttrDict
    _fake_get_secret(monkeypatch, {"google_service_account": AttrDict({"type": "service_account"})})
    assert N.status()["enabled"] is False
    assert N.status()["diag"]["google_service_account"] == "no_client_email"

    _fake_get_secret(monkeypatch, {"google_service_account": {"client_email": ""}})
    assert N.status()["enabled"] is False


# ── 5. malformed JSON → {}，status 仍為 unparseable（既有診斷不變）───────
@pytest.mark.parametrize("bad", ["{not json", "[1, 2]", '"just a string"', "null"])
def test_malformed_json_still_unparseable(monkeypatch, bad):
    assert N._sa_to_dict(bad) == {}
    _fake_get_secret(monkeypatch, {"google_service_account": bad})
    st_ = N.status()
    assert st_["enabled"] is False
    assert st_["diag"]["google_service_account"] == "unparseable"


# ── 6. 空值／缺 secret → 不得判為有效（diag=absent）────────────────────
@pytest.mark.parametrize("mapping", [
    {"google_service_account": ""},
    {"google_service_account": "   "},
    {"google_service_account": None},
    {},
])
def test_empty_none_missing(monkeypatch, mapping):
    _fake_get_secret(monkeypatch, mapping)
    st_ = N.status()
    assert st_["enabled"] is False
    assert st_["diag"]["google_service_account"] == "absent"
    assert N._sa_to_dict(mapping.get("google_service_account")) == {}


# ── 7. 正式啟用路徑：合法 TOML table → enabled，診斷不再是 unparseable ──
def test_status_enabled_with_toml_table(real_st_secrets):
    real_st_secrets(_TOML)
    st_ = N.status()
    assert st_["enabled"] is True
    assert st_["missing"] == []
    assert st_["diag"]["google_service_account"] == "ok"
    assert st_["diag"]["google_service_account"] != "unparseable"
    assert st_["diag"]["st_secrets_alive"] is True
    assert N.is_enabled() is True
