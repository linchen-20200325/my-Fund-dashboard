"""選股池持久化(repositories/pool_repository.py,v19.428)。本地 JSON 後端 CRUD + 驗證。"""
import pytest

import repositories.pool_repository as P
from repositories.pool_repository import LocalJsonPoolStore, PoolEntry


@pytest.fixture
def store(tmp_path):
    return LocalJsonPoolStore(base_dir=tmp_path)


# ── CRUD ─────────────────────────────────────────────────
def test_add_list_roundtrip(store):
    store.upsert(PoolEntry(code="ABC123", name="測試基金", category="股票型"))
    pool = store.list_pool()
    assert len(pool) == 1 and pool[0].code == "ABC123" and pool[0].added_at   # added_at 自動補


def test_upsert_updates_by_code(store):
    store.upsert(PoolEntry(code="X", name="舊名"))
    store.upsert(PoolEntry(code="X", name="新名", note="改過"))
    pool = store.list_pool()
    assert len(pool) == 1 and pool[0].name == "新名" and pool[0].note == "改過"   # 同 code → 覆蓋不重複


def test_remove(store):
    store.upsert(PoolEntry(code="A"))
    store.upsert(PoolEntry(code="B"))
    store.remove("A")
    assert [e.code for e in store.list_pool()] == ["B"]


def test_empty_code_raises(store):
    with pytest.raises(ValueError):
        store.upsert(PoolEntry(code="  "))     # 空鍵 → §1 拒絕


# ── type_override 驗證 ───────────────────────────────────
def test_type_override_validation():
    assert PoolEntry(code="A", type_override="成長").type_override == "成長"
    assert PoolEntry(code="A", type_override="震盪").type_override == "震盪"
    assert PoolEntry(code="A", type_override="亂填").type_override == ""     # 非法 → 空(自動)
    assert PoolEntry(code="A").type_override == ""


def test_set_type_override(monkeypatch, store):
    monkeypatch.setattr(P, "get_pool_store", lambda: store)
    store.upsert(PoolEntry(code="Q", name="Q基金"))
    P.set_type_override("Q", "成長")
    assert store.list_pool()[0].type_override == "成長"
    P.set_type_override("Q", "亂填")                       # 非法 → 歸空(自動)
    assert store.list_pool()[0].type_override == ""


def test_set_type_override_missing_raises(monkeypatch, store):
    monkeypatch.setattr(P, "get_pool_store", lambda: store)
    with pytest.raises(KeyError):
        P.set_type_override("NOPE", "成長")


def test_corrupt_local_file_returns_empty(tmp_path):
    (tmp_path / "pool.json").write_text("{bad json", encoding="utf-8")
    assert LocalJsonPoolStore(base_dir=tmp_path).list_pool() == []   # 壞檔 → 空,不崩
