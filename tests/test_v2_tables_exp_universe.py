# -*- coding: utf-8 -*-
"""`services/v2_tables/exp_universe.py`（標的探索正式模式的母體：選股池代碼）單元測試。

不連網：`pool_repository` 的兩個公開函式一律以替身注入。客戶 2026-10-13 裁示的三件事各有一條（含正控）：
1. 只取 `code` 欄 —— 其他欄一碰就炸的替身證明本層結構上沒讀它們；
2. `pool_backend_status` 回 `"local"` 時不讀本機 JSON 當母體（`list_pool` 一被呼叫就炸）；
3. 不過濾 `status`（`CLOSED` 也列）；代碼去空白、去重保持原順序；空字串丟棄並記數。
"""

from __future__ import annotations

import secrets as _rnd

import pytest

from services.v2_tables import exp_universe as U


class _OnlyCode:
    """只有 `code` 可以讀；`name`／`currency`／`category`／`type_override`／`status` 等任何其他屬性一碰就炸。"""

    def __init__(self, code):
        object.__setattr__(self, "_code", code)

    def __getattr__(self, name):
        if name == "code":
            return self._code
        raise AssertionError(f"exp_universe 讀了選股池的 {name} 欄（只准讀 code）")


def _stub(monkeypatch, *, backend="service_account", entries=(), error=None):
    calls = []

    def list_pool(oauth_client=None):
        calls.append(oauth_client)
        if error is not None:
            raise error
        return list(entries)

    monkeypatch.setattr(U.pool_repository, "pool_backend_status", lambda oauth_client=None: backend)
    monkeypatch.setattr(U.pool_repository, "list_pool", list_pool)
    return calls


def test_只取代碼_其他欄一碰就炸也不炸(monkeypatch):
    _stub(monkeypatch, entries=[_OnlyCode("B02"), _OnlyCode("A01")])
    out = U.load_pool_codes([])
    assert out == {"status": U.STATUS_OK, "backend": "service_account", "codes": ["B02", "A01"],
                   "dropped_blank": 0, "duplicates": 0, "message": None}


def test_正控_替身真的會咬人():
    with pytest.raises(AssertionError):
        _OnlyCode("X").currency  # noqa: B018


def test_去空白_去重保持原順序_空字串丟棄並記數_大小寫原樣(monkeypatch):
    entries = [_OnlyCode(c) for c in (" b02 ", "A01", "", "b02", "   ", "A01", "a01", None)]
    _stub(monkeypatch, entries=entries)
    out = U.load_pool_codes([])
    assert out["status"] == U.STATUS_OK
    assert out["codes"] == ["b02", "A01", "a01"]
    assert out["dropped_blank"] == 3 and out["duplicates"] == 2


def test_不過濾status_CLOSED也列(monkeypatch):
    from repositories.pool_repository import PoolEntry

    entries = [PoolEntry(code="X1", status="CLOSED"), PoolEntry(code="X2", status="WATCHING")]
    _stub(monkeypatch, entries=entries)
    assert U.load_pool_codes([])["codes"] == ["X1", "X2"]


def test_local時不讀本機JSON當母體_照實回未設定雲端(monkeypatch):
    calls = _stub(monkeypatch, backend="local", entries=[_OnlyCode("SHOULD-NOT-APPEAR")])
    out = U.load_pool_codes([])
    assert calls == []                                   # list_pool 一次都沒被呼叫
    assert out["status"] == U.STATUS_NOT_CLOUD and out["codes"] == []
    assert out["message"] == U.TEXT_NOT_CLOUD and "未設定雲端來源" in out["message"]


@pytest.mark.parametrize("backend", ["service_account", "oauth"])
def test_雲端後端才讀(monkeypatch, backend):
    calls = _stub(monkeypatch, backend=backend, entries=[_OnlyCode("A")])
    assert U.load_pool_codes([])["codes"] == ["A"] and calls == [None]


def test_讀取失敗_照實回失敗_訊息遮蔽_帶例外型別名(monkeypatch):
    key = _rnd.token_hex(12)
    _stub(monkeypatch, error=RuntimeError(f"403 forbidden token={key}"))
    out = U.load_pool_codes([key])
    assert out["status"] == U.STATUS_FAILED and out["codes"] == []
    assert out["message"].startswith("RuntimeError: 403 forbidden")
    assert key not in out["message"]


def test_空池_讀得到但沒有列_不是失敗(monkeypatch):
    _stub(monkeypatch, entries=[])
    out = U.load_pool_codes([])
    assert out["status"] == U.STATUS_OK and out["codes"] == [] and out["message"] is None
