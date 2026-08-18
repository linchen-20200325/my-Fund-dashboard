"""基金代號對照表(repositories/id_map_repository.py,v19.469)。本地 JSON CRUD + resolve_secid。"""
import pytest

import repositories.id_map_repository as M
from repositories.id_map_repository import IdMapEntry, LocalJsonIdMapStore


@pytest.fixture
def store(tmp_path):
    return LocalJsonIdMapStore(base_dir=tmp_path)


# ── CRUD ─────────────────────────────────────────────────
def test_add_list_roundtrip(store):
    store.upsert(IdMapEntry(code="ALZF9", morningstar_secid="F00000P8WB",
                            isin="LU0766462157", currency="USD", name="安聯收益成長基金"))
    m = store.list_id_map()
    assert len(m) == 1 and m[0].code == "ALZF9" and m[0].morningstar_secid == "F00000P8WB"
    assert m[0].isin == "LU0766462157" and m[0].currency == "USD"


def test_code_uppercased_and_upsert_by_code(store):
    store.upsert(IdMapEntry(code="alzf9", morningstar_secid="OLD"))
    store.upsert(IdMapEntry(code="ALZF9", morningstar_secid="NEW", name="改過"))
    m = store.list_id_map()
    assert len(m) == 1 and m[0].morningstar_secid == "NEW" and m[0].name == "改過"   # 同 code 覆蓋


def test_remove(store):
    store.upsert(IdMapEntry(code="A", morningstar_secid="s1"))
    store.upsert(IdMapEntry(code="B", morningstar_secid="s2"))
    store.remove("a")                                  # 大小寫不分
    assert [e.code for e in store.list_id_map()] == ["B"]


def test_empty_code_raises(store):
    with pytest.raises(ValueError):
        store.upsert(IdMapEntry(code="  "))


def test_currency_defaults_usd():
    assert IdMapEntry(code="X").currency == "USD"
    assert IdMapEntry(code="X", currency="twd").currency == "TWD"


def test_corrupt_local_file_returns_empty(tmp_path):
    (tmp_path / "id_map.json").write_text("{bad json", encoding="utf-8")
    assert LocalJsonIdMapStore(base_dir=tmp_path).list_id_map() == []


def test_from_row_pads_and_skips_empty():
    assert IdMapEntry.from_row([]) is None
    assert IdMapEntry.from_row(["", "x"]) is None
    e = IdMapEntry.from_row(["ALZF9", "F00000P8WB"])   # 缺後 3 欄 → pad
    assert e.code == "ALZF9" and e.isin == "" and e.currency == "USD"


# ── resolve_secid(供 sources.py 合併查表)────────────────
def test_resolve_secid_hits_user_map(monkeypatch):
    monkeypatch.setattr(M, "list_id_map",
                        lambda: [IdMapEntry(code="ALZF9", morningstar_secid="F00000P8WB", currency="USD")])
    monkeypatch.setattr(M, "_cached_secid_map", M._load_secid_map)   # 繞過 streamlit 快取
    assert M.resolve_secid("alzf9") == ("F00000P8WB", "USD")         # 大小寫不分


def test_resolve_secid_none_when_no_secid(monkeypatch):
    # 有列但 secId 空 → 不算命中(退硬編/搜尋)
    monkeypatch.setattr(M, "list_id_map",
                        lambda: [IdMapEntry(code="ALZF9", morningstar_secid="", isin="LU0766462157")])
    monkeypatch.setattr(M, "_cached_secid_map", M._load_secid_map)
    assert M.resolve_secid("ALZF9") is None


def test_resolve_secid_none_when_not_in_map(monkeypatch):
    monkeypatch.setattr(M, "list_id_map", lambda: [])
    monkeypatch.setattr(M, "_cached_secid_map", M._load_secid_map)
    assert M.resolve_secid("NOPE") is None and M.resolve_secid("") is None


def test_resolve_secid_survives_repo_error(monkeypatch):
    def _boom():
        raise RuntimeError("GS down")
    monkeypatch.setattr(M, "list_id_map", _boom)
    monkeypatch.setattr(M, "_cached_secid_map", M._load_secid_map)
    assert M.resolve_secid("ALZF9") is None            # 讀不到 → None,不炸(不阻斷抓取鏈)


# ── 快取失效(稽核 #3:加/刪對照後立即生效)────────────────
def test_add_and_remove_clear_secid_cache(monkeypatch, tmp_path):
    _calls = []
    monkeypatch.setattr(M, "_clear_secid_cache", lambda: _calls.append(1))
    monkeypatch.setattr(M, "get_id_map_store", lambda: LocalJsonIdMapStore(base_dir=tmp_path))
    M.add_or_update(IdMapEntry(code="ALZF9", morningstar_secid="F00000P8WB"))
    M.remove_from_id_map("ALZF9")
    assert _calls == [1, 1]                            # add + remove 各清一次快取(否則最長等 30 分)


def test_clear_secid_cache_headless_no_crash():
    M._clear_secid_cache()                             # plain 版無 .clear() → try/except,不炸
