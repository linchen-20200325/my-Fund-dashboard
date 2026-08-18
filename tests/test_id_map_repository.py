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


# ── resolve_secid / resolve_isin(供 sources.py ISIN 驅動查表)────────────────
def _patch_cache(monkeypatch, entries):
    monkeypatch.setattr(M, "list_id_map", lambda: entries)
    monkeypatch.setattr(M, "_cached_id_map", M._load_id_map_dict)   # 繞過 streamlit 快取


def test_resolve_secid_hits_user_map(monkeypatch):
    _patch_cache(monkeypatch, [IdMapEntry(code="ALZF9", morningstar_secid="F00000P8WB", currency="USD")])
    assert M.resolve_secid("alzf9") == ("F00000P8WB", "USD")         # 大小寫不分


def test_resolve_secid_none_when_no_secid(monkeypatch):
    # 有列但 secId 空 → 不算命中(退 ISIN 搜尋)
    _patch_cache(monkeypatch, [IdMapEntry(code="ALZF9", morningstar_secid="", isin="LU0766462157")])
    assert M.resolve_secid("ALZF9") is None


def test_resolve_isin_hits_when_only_isin(monkeypatch):
    # 只填 ISIN 沒 secId → resolve_isin 命中(供晨星用 ISIN 搜 secId)
    _patch_cache(monkeypatch, [IdMapEntry(code="ALZF9", isin="LU0766462157")])
    assert M.resolve_isin("alzf9") == "LU0766462157"
    assert M.resolve_secid("ALZF9") is None            # 同一列:有 ISIN 沒 secId


def test_resolve_isin_none_when_no_isin(monkeypatch):
    _patch_cache(monkeypatch, [IdMapEntry(code="ALZF9", morningstar_secid="X")])
    assert M.resolve_isin("ALZF9") is None and M.resolve_isin("NOPE") is None


def test_resolvers_none_when_not_in_map(monkeypatch):
    _patch_cache(monkeypatch, [])
    assert M.resolve_secid("NOPE") is None and M.resolve_isin("") is None


def test_resolvers_survive_repo_error(monkeypatch):
    def _boom():
        raise RuntimeError("GS down")
    monkeypatch.setattr(M, "list_id_map", _boom)
    monkeypatch.setattr(M, "_cached_id_map", M._load_id_map_dict)
    assert M.resolve_secid("ALZF9") is None and M.resolve_isin("ALZF9") is None   # 不炸


# ── set_secid:ISIN 搜到 secId 後回存 ───────────────────────
def test_set_secid_writes_back_keeps_isin(monkeypatch, tmp_path):
    store = LocalJsonIdMapStore(base_dir=tmp_path)
    store.upsert(IdMapEntry(code="ALZF9", isin="LU0766462157", name="安聯"))   # 先只有 ISIN
    monkeypatch.setattr(M, "get_id_map_store", lambda: store)
    monkeypatch.setattr(M, "_clear_id_map_cache", lambda: None)
    M.set_secid("alzf9", "F00000P8WB", "USD")
    e = store.list_id_map()[0]
    assert e.morningstar_secid == "F00000P8WB" and e.isin == "LU0766462157" and e.name == "安聯"


def test_set_secid_no_op_when_code_absent(monkeypatch, tmp_path):
    store = LocalJsonIdMapStore(base_dir=tmp_path)
    monkeypatch.setattr(M, "get_id_map_store", lambda: store)
    monkeypatch.setattr(M, "_clear_id_map_cache", lambda: None)
    M.set_secid("NOPE", "X")                           # 不在表 → 不硬建列(§1)
    assert store.list_id_map() == []


# ── currency(稽核 v19.471:ISIN 路徑不覆蓋使用者幣別)────────────
def test_resolve_currency(monkeypatch):
    _patch_cache(monkeypatch, [IdMapEntry(code="X", isin="TW123", currency="TWD")])
    assert M.resolve_currency("x") == "TWD" and M.resolve_currency("NOPE") is None


def test_set_secid_empty_currency_preserves(monkeypatch, tmp_path):
    # ISIN 路徑回存 secId 時不傳幣別 → 沿用使用者填的 TWD(不被打成 USD)
    store = LocalJsonIdMapStore(base_dir=tmp_path)
    store.upsert(IdMapEntry(code="X", isin="TW123", currency="TWD"))
    monkeypatch.setattr(M, "get_id_map_store", lambda: store)
    monkeypatch.setattr(M, "_clear_id_map_cache", lambda: None)
    M.set_secid("X", "0P00SEC")                        # 不傳 currency
    e = store.list_id_map()[0]
    assert e.morningstar_secid == "0P00SEC" and e.currency == "TWD"   # 幣別保留


def test_set_secid_explicit_currency_overrides(monkeypatch, tmp_path):
    store = LocalJsonIdMapStore(base_dir=tmp_path)
    store.upsert(IdMapEntry(code="X", isin="TW123", currency="TWD"))
    monkeypatch.setattr(M, "get_id_map_store", lambda: store)
    monkeypatch.setattr(M, "_clear_id_map_cache", lambda: None)
    M.set_secid("X", "0P00SEC", "EUR")                 # 明確傳幣別 → 覆蓋
    assert store.list_id_map()[0].currency == "EUR"


# ── 快取失效(稽核 #3:加/刪對照後立即生效)────────────────
def test_add_and_remove_clear_cache(monkeypatch, tmp_path):
    _calls = []
    monkeypatch.setattr(M, "_clear_id_map_cache", lambda: _calls.append(1))
    monkeypatch.setattr(M, "get_id_map_store", lambda: LocalJsonIdMapStore(base_dir=tmp_path))
    M.add_or_update(IdMapEntry(code="ALZF9", isin="LU0766462157"))
    M.remove_from_id_map("ALZF9")
    assert _calls == [1, 1]                            # add + remove 各清一次(否則最長等 30 分)


def test_clear_cache_headless_no_crash():
    M._clear_id_map_cache()                            # plain 版無 .clear() → try/except,不炸
