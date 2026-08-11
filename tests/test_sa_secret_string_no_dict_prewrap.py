"""SA secret 為 JSON 字串時,GS 取數 call site 不得 `dict()` 預包(v19.430)。

背景(接續 tab3 開場崩 hotfix):
`get_gspread_client` 已於 main 收 `_coerce_sa_credentials`(str→json.loads / dict 原樣 /
fail-loud)。但仍有 3 個 call site 在**進 get_gspread_client 之前**就 `dict(require_secret(...))`:
secret 存成 JSON 字串時 `dict("...")` 直接拋 ValueError(且 Streamlit Cloud 遮蔽訊息),
使用者用到「選股池 / 換股顧問 / 總經權重 / auto-search」就會炸。

本測試以**行為**鎖住修正:把 secret 餵成字串,3 個 sheet-getter 必須把**原字串**
一路傳到 get_gspread_client(用 stub 攔截),全程不拋 ValueError。
"""
from __future__ import annotations

import json

import pytest

_SA_JSON = json.dumps({
    "type": "service_account",
    "project_id": "p",
    "private_key": "-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----\n",
    "client_email": "x@x.iam.gserviceaccount.com",
})


def _fake_require_secret(key: str):
    if key == "google_service_account":
        return _SA_JSON                       # ← 關鍵:字串形狀(不是 dict)
    if key == "macro_weights_sheet_id":
        return "SHEET_ID"
    raise KeyError(key)


class _FakeSheet:
    def worksheet(self, *a, **k):
        return "WS"

    def add_worksheet(self, *a, **k):
        return "WS"


class _FakeClient:
    def open_by_key(self, key):
        assert key == "SHEET_ID"
        return _FakeSheet()


def _patch(monkeypatch):
    """patch require_secret + get_gspread_client,回收到的 creds list。"""
    import infra.config as _cfg
    import repositories.policy_repository as _polrepo

    received: list = []

    def _stub_get_client(creds):
        received.append(creds)
        return _FakeClient()

    monkeypatch.setattr(_cfg, "require_secret", _fake_require_secret)
    monkeypatch.setattr(_polrepo, "get_gspread_client", _stub_get_client)
    return received


def test_pool_repository_passes_string_secret_untouched(monkeypatch):
    received = _patch(monkeypatch)
    import repositories.pool_repository as _pool

    sh = _pool._get_sheet()                    # 有 dict() bug 時這行會拋 ValueError
    assert isinstance(sh, _FakeSheet)
    assert received == [_SA_JSON], "SA 字串應原樣傳給 get_gspread_client(不得先 dict())"


def test_auto_search_store_passes_string_secret_untouched(monkeypatch):
    received = _patch(monkeypatch)
    import services.auto_search_store_gs as _ass

    sh = _ass._get_sheet()
    assert isinstance(sh, _FakeSheet)
    assert received == [_SA_JSON]


def test_weights_store_passes_string_secret_untouched(monkeypatch):
    received = _patch(monkeypatch)
    import services.macro.weights_store as _ws

    ws = _ws._gs_get_worksheet()
    assert ws == "WS"
    assert received == [_SA_JSON]


def test_no_dict_prewrap_source_lock():
    """回歸鎖:3 檔皆不得再出現 `dict(require_secret("google_service_account"))`。"""
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    targets = [
        root / "repositories" / "pool_repository.py",
        root / "services" / "auto_search_store_gs.py",
        root / "services" / "macro" / "weights_store.py",
    ]
    bad = 'dict(require_secret("google_service_account"))'
    offenders = [str(p.relative_to(root)) for p in targets if bad in p.read_text(encoding="utf-8")]
    assert not offenders, f"這些檔又出現 dict() 預包(secret 為字串時會崩):{offenders}"
