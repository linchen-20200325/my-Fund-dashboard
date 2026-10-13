# -*- coding: utf-8 -*-
"""`services/v2_tables/exp_universe.py`（標的探索正式模式的母體：選股池代碼）單元測試。

不連網：`pool_repository.get_pool_store` 一律回替身 store。客戶 2026-10-13 裁示的三件事各有一條（含正控）：
1. 只取 `code` 欄 —— 其他欄一碰就炸的替身證明本層結構上沒讀它們；
2. 本機 store 不當母體（2026-10-13 稽核 K：直接看 store 型別，含「服務帳戶在、試算表 ID 空」的反例）；
3. 不過濾 `status`（`CLOSED` 也列）；代碼去空白、去重保持原順序；空字串丟棄並記數。
另有稽核 L 回修的快取與失敗冷卻（只快取成功、冷卻期內不重打、冷卻到期真的重試）。
"""

from __future__ import annotations

import secrets as _rnd

import pytest

from infra import source_backoff as SB
from repositories import pool_repository as POOL
from services.v2_tables import exp_universe as U

_KEY = ("sa", "sheet-exp-test")


class _OnlyCode:
    """只有 `code` 可以讀；`name`／`currency`／`category`／`type_override`／`status` 等任何其他屬性一碰就炸。"""

    def __init__(self, code):
        object.__setattr__(self, "_code", code)

    def __getattr__(self, name):
        if name == "code":
            return self._code
        raise AssertionError(f"exp_universe 讀了選股池的 {name} 欄（只准讀 code）")


class _CloudStore:
    backend_name = "google-sheets"

    def __init__(self, entries=(), error=None):
        self.entries, self.error, self.calls = list(entries), error, 0

    def list_pool(self):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return list(self.entries)


class _LocalStore(POOL.LocalJsonPoolStore):
    def __init__(self):  # 不碰檔案系統
        self.calls = 0

    def list_pool(self):
        self.calls += 1
        raise AssertionError("本機暫存檔被當母體讀了")


@pytest.fixture(autouse=True)
def _clean():
    U.clear_cache()
    SB.reset_all()
    yield
    U.clear_cache()
    SB.reset_all()


def _stub(monkeypatch, store):
    monkeypatch.setattr(U.pool_repository, "get_pool_store", lambda oauth_client=None: store)
    monkeypatch.setattr(U.pool_repository, "_pool_backoff_ident", lambda oauth_client=None: _KEY)
    return store


def test_只取代碼_其他欄一碰就炸也不炸(monkeypatch):
    _stub(monkeypatch, _CloudStore([_OnlyCode("B02"), _OnlyCode("A01")]))
    out = U.load_pool_codes([])
    assert out == {"status": U.STATUS_OK, "backend": "google-sheets", "codes": ["B02", "A01"],
                   "dropped_blank": 0, "duplicates": 0, "message": None}


def test_正控_替身真的會咬人():
    with pytest.raises(AssertionError):
        _OnlyCode("X").currency  # noqa: B018


def test_去空白_去重保持原順序_空字串丟棄並記數_大小寫原樣(monkeypatch):
    entries = [_OnlyCode(c) for c in (" b02 ", "A01", "", "b02", "   ", "A01", "a01", None)]
    _stub(monkeypatch, _CloudStore(entries))
    out = U.load_pool_codes([])
    assert out["status"] == U.STATUS_OK
    assert out["codes"] == ["b02", "A01", "a01"]
    assert out["dropped_blank"] == 3 and out["duplicates"] == 2


def test_不過濾status_CLOSED也列(monkeypatch):
    entries = [POOL.PoolEntry(code="X1", status="CLOSED"), POOL.PoolEntry(code="X2", status="WATCHING")]
    _stub(monkeypatch, _CloudStore(entries))
    assert U.load_pool_codes([])["codes"] == ["X1", "X2"]


def test_本機store時不讀本機JSON當母體_照實回未設定雲端(monkeypatch):
    store = _stub(monkeypatch, _LocalStore())
    out = U.load_pool_codes([])
    assert store.calls == 0
    assert out["status"] == U.STATUS_NOT_CLOUD and out["codes"] == []
    assert out["message"] == U.TEXT_NOT_CLOUD and "未設定雲端來源" in out["message"]


def test_稽核K反例_服務帳戶在但試算表ID空_store是本機_也不讀(monkeypatch):
    """不 stub `get_pool_store`：走真的 L1 選擇邏輯。`_sa_present` 為真、試算表 ID 為空 →
    `GoogleSheetsPoolStore.is_available()` 為假 → L1 交出本機 store；本層必須照樣回未設定雲端。
    （舊寫法只問 `pool_backend_status`，它此時回 `service_account`，就會把本機暫存檔當母體讀。）"""
    monkeypatch.setattr(POOL, "_sa_present", lambda: True)
    monkeypatch.setattr(POOL, "_pool_sheet_id", lambda: "")
    assert POOL.pool_backend_status() == "service_account"            # 反例的前提真的成立
    monkeypatch.setattr(POOL.LocalJsonPoolStore, "list_pool",
                        lambda self: (_ for _ in ()).throw(AssertionError("讀了本機暫存檔")))
    out = U.load_pool_codes([])
    assert out["status"] == U.STATUS_NOT_CLOUD and out["backend"] == "local-json"


def test_讀取失敗_照實回失敗_訊息遮蔽_帶例外型別名(monkeypatch):
    key = _rnd.token_hex(12)
    _stub(monkeypatch, _CloudStore(error=RuntimeError(f"403 forbidden token={key}")))
    out = U.load_pool_codes([key])
    assert out["status"] == U.STATUS_FAILED and out["codes"] == []
    assert out["message"].startswith("RuntimeError: 403 forbidden")
    assert key not in out["message"]


def test_空池_讀得到但沒有列_不是失敗(monkeypatch):
    _stub(monkeypatch, _CloudStore([]))
    out = U.load_pool_codes([])
    assert out["status"] == U.STATUS_OK and out["codes"] == [] and out["message"] is None


# ═════════════════════ 快取與失敗冷卻（稽核 L 回修） ═════════════════════


def test_只快取成功結果_TTL內不重讀_TTL到期重讀(monkeypatch):
    store = _stub(monkeypatch, _CloudStore([_OnlyCode("A01")]))
    assert U.load_pool_codes([], now=1000.0)["codes"] == ["A01"]
    store.entries = [_OnlyCode("B02")]
    assert U.load_pool_codes([], now=1000.0 + U.SUCCESS_TTL_SEC - 1)["codes"] == ["A01"]
    assert store.calls == 1
    assert U.load_pool_codes([], now=1000.0 + U.SUCCESS_TTL_SEC + 1)["codes"] == ["B02"]
    assert store.calls == 2


def test_失敗不入快取_冷卻期內不重打_回上次失敗原文並註明冷卻中(monkeypatch):
    secret = _rnd.token_hex(12)
    store = _stub(monkeypatch, _CloudStore(error=ConnectionError(f"連線中斷 {secret}")))
    first = U.load_pool_codes([secret])
    assert first["status"] == U.STATUS_FAILED and store.calls == 1
    second = U.load_pool_codes([secret])
    assert store.calls == 1                                              # 冷卻中：沒有再打
    assert second["status"] == U.STATUS_FAILED
    assert "冷卻中" in second["message"] and "連線中斷" in second["message"] and secret not in second["message"]


def test_冷卻到期會真的重試_成功後解除冷卻(monkeypatch):
    clock = [5000.0]
    monkeypatch.setattr(SB, "_clock", lambda: clock[0])                 # `infra.source_backoff` 的假時鐘注入點
    store = _stub(monkeypatch, _CloudStore(error=ConnectionError("連線中斷")))
    U.load_pool_codes([])
    U.load_pool_codes([])
    assert store.calls == 1                                              # 冷卻中
    clock[0] += 1801                                                     # 超過最長冷卻（1800 秒）
    store.error, store.entries = None, [_OnlyCode("A01")]
    out = U.load_pool_codes([])
    assert store.calls == 2 and out["codes"] == ["A01"]                  # 到期真的重打
    assert U.should_skip_gspread(*_KEY)[0] is False                      # 成功後解除冷卻


def test_冷卻短於成功TTL():
    from shared import backoff_policy as BP

    assert BP.BACKOFF_MAX_COOLDOWN_SEC < U.SUCCESS_TTL_SEC
    assert max(BP.BACKOFF_COOLDOWN_SEC.values()) < U.SUCCESS_TTL_SEC


def test_全域刷新會清掉這份快取(monkeypatch):
    from infra import cache as C

    store = _stub(monkeypatch, _CloudStore([_OnlyCode("A01")]))
    U.load_pool_codes([])
    C.clear_all_caches()
    U.load_pool_codes([])
    assert store.calls == 2
    info = U._REGISTERED.cache_info()
    assert set(info) >= set(C.CACHE_INFO_REQUIRED_KEYS) and not (set(info) & set(C.CACHE_INFO_STAT_KEYS))
