# -*- coding: utf-8 -*-
"""BL-0383：選股池 `_sa_present()` 認不得 Streamlit secrets 的 TOML table（AttrDict）。

2026-10-20 實測（streamlit 1.59.2）：`[google_service_account]` TOML table 經
`infra.config.get_secret` 取得的是 `streamlit.runtime.secrets.AttrDict` ——
MRO 為 (AttrDict, collections.abc.Mapping, ...)，**不是 dict 子類**。舊判斷
`isinstance(_sa, dict)` 因此恆假，選股池誤判「選股池的雲端來源尚未設定」。

本檔不連網、不讀 repo 的任何 secrets 檔：TOML 一律寫進 pytest 的 tmp_path，值全為假。
"""

from __future__ import annotations

import json

import pytest

import infra.config as CFG
from repositories import pool_repository as P

_FAKE_EMAIL = "fake-sa@example.iam.gserviceaccount.com"

_TOML = f'''
[google_service_account]
type = "service_account"
client_email = "{_FAKE_EMAIL}"
private_key = "FAKE"
'''

_TOML_NO_EMAIL = '''
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

    ⚠️ 隔離（同 `tests/test_nav_history_sa_mapping_bl0383.py` 的 `real_st_secrets`）：
    `Secrets.load_if_toml_exists()` 第一次解析時會呼叫 `streamlit.watcher.path_watcher.watch_file／
    watch_dir` 裝 poll 型檔案監看，留下常駐的 `ThreadPoolExecutor` 執行緒每 0.2 秒呼叫一次
    `time.sleep`，測試結束也不會停。本檔排在 `tests/test_policy_supplement_repository.py` 前面跑時，
    那支檔的 `_five_minutes` 把全域 `time.sleep` 換成推進假時鐘，會被這些背景執行緒在背後推進時鐘
    而轉紅（2026-10-20 實測 3 次：7／6／6 failed；單獨跑全綠）。這裡用 monkeypatch 把兩個監看函式
    換成 no-op（測試結束自動還原），並斷言解析前後執行緒數不變。
    （環境變數：本檔 TOML 沒有頂層字串，Streamlit 不會寫 `os.environ`，故不需另做還原。）
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


# ── 1. dict + client_email → True（相容不變）────────────────────────────
def test_dict_with_client_email(monkeypatch):
    _fake_get_secret(monkeypatch, {"google_service_account": {"client_email": _FAKE_EMAIL}})
    assert P._sa_present() is True


# ── 2. Streamlit 真 AttrDict（真的 st.secrets 解析 TOML table）+ client_email → True ──
def test_real_streamlit_toml_table_attrdict(real_st_secrets):
    real_st_secrets(_TOML)
    raw = CFG.get_secret("google_service_account")
    from collections.abc import Mapping
    # 前提真的成立：正式路徑拿到的是 Mapping 但不是 dict（舊判斷正是栽在這裡）
    assert isinstance(raw, Mapping) and not isinstance(raw, dict)
    assert type(raw).__name__ == "AttrDict"
    assert P._sa_present() is True


def test_attrdict_direct(monkeypatch):
    from streamlit.runtime.secrets import AttrDict
    _fake_get_secret(monkeypatch, {"google_service_account": AttrDict({"client_email": _FAKE_EMAIL})})
    assert P._sa_present() is True


# ── 3. JSON string + client_email → True（env fallback 形狀）────────────
def test_json_string_with_client_email(monkeypatch):
    _fake_get_secret(monkeypatch, {"google_service_account": json.dumps({"client_email": _FAKE_EMAIL})})
    assert P._sa_present() is True


# ── 4. mapping 缺 client_email → False ─────────────────────────────────
def test_mapping_missing_client_email(monkeypatch, real_st_secrets):
    real_st_secrets(_TOML_NO_EMAIL)
    assert P._sa_present() is False
    from streamlit.runtime.secrets import AttrDict
    _fake_get_secret(monkeypatch, {"google_service_account": AttrDict({"type": "service_account"})})
    assert P._sa_present() is False
    _fake_get_secret(monkeypatch, {"google_service_account": {"client_email": ""}})
    assert P._sa_present() is False


# ── 5. malformed JSON → False ──────────────────────────────────────────
@pytest.mark.parametrize("bad", ["{not json", "[1, 2]", '"just a string"', "null"])
def test_malformed_json(monkeypatch, bad):
    _fake_get_secret(monkeypatch, {"google_service_account": bad})
    assert P._sa_present() is False


# ── 6. 空字串／None／缺 secret → False ─────────────────────────────────
@pytest.mark.parametrize("mapping", [
    {"google_service_account": ""},
    {"google_service_account": "   "},
    {"google_service_account": None},
    {},
])
def test_empty_none_missing(monkeypatch, mapping):
    _fake_get_secret(monkeypatch, mapping)
    assert P._sa_present() is False


# ── 正式路徑：TOML table 形式的 SA → 標的探索母體不再回「選股池的雲端來源尚未設定」──
def test_exp_universe_with_toml_sa_is_not_not_cloud(monkeypatch, real_st_secrets):
    """不 stub `_sa_present`／`get_pool_store`：真的 st.secrets（TOML table）→ 真的 L1 選擇邏輯。

    只把 `GoogleSheetsPoolStore.list_pool` 換成不連網的替身（證明確實選到雲端 store）。
    """
    from services.v2_tables import exp_universe as U

    from infra import source_backoff as SB

    real_st_secrets(_TOML)
    # 2026-10-26 J-7：選股池無寫死預設本。不把 POOL_SHEET_ID 寫進 TOML 頂層（頂層字串會被 Streamlit
    # 寫進 os.environ，見 fixture 註解），改只替換 sheet id 讀取：SA 仍走真的 st.secrets。
    monkeypatch.setattr(P, "_pool_sheet_id", lambda: "FAKE_POOL_BOOK")
    U.clear_cache()
    SB.reset_all()
    try:
        calls = []

        class _E:
            code = "ABC123"

        def _fake_list(self):
            calls.append(type(self).__name__)
            return [_E()]

        monkeypatch.setattr(P.GoogleSheetsPoolStore, "list_pool", _fake_list)
        assert P.pool_backend_status() == "service_account"
        assert isinstance(P.get_pool_store(), P.GoogleSheetsPoolStore)
        out = U.load_pool_codes([])
        assert out["status"] != U.STATUS_NOT_CLOUD
        assert out["status"] == U.STATUS_OK and out["codes"] == ["ABC123"]
        assert "未設定雲端來源" not in str(out.get("message") or "")
        assert calls == ["GoogleSheetsPoolStore"]
    finally:
        U.clear_cache()
        SB.reset_all()
