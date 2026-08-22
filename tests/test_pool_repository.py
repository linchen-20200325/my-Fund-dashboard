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
    monkeypatch.setattr(P, "get_pool_store", lambda oauth_client=None: store)
    store.upsert(PoolEntry(code="Q", name="Q基金"))
    P.set_type_override("Q", "成長")
    assert store.list_pool()[0].type_override == "成長"
    P.set_type_override("Q", "亂填")                       # 非法 → 歸空(自動)
    assert store.list_pool()[0].type_override == ""


def test_set_type_override_missing_raises(monkeypatch, store):
    monkeypatch.setattr(P, "get_pool_store", lambda oauth_client=None: store)
    with pytest.raises(KeyError):
        P.set_type_override("NOPE", "成長")


def test_corrupt_local_file_returns_empty(tmp_path):
    (tmp_path / "pool.json").write_text("{bad json", encoding="utf-8")
    assert LocalJsonPoolStore(base_dir=tmp_path).list_pool() == []   # 壞檔 → 空,不崩


# ── v19.472:選股池目標 Sheet = 獨立一本(POOL_SHEET_ID → baked 預設,不共用持倉)──────
def _fake_secrets(monkeypatch, mapping):
    import infra.config as _cfg
    monkeypatch.setattr(_cfg, "get_secret", lambda k, default=None: mapping.get(k, default))


def test_pool_sheet_id_prefers_pool_sheet_secret(monkeypatch):
    _fake_secrets(monkeypatch, {"POOL_SHEET_ID": "my_pool_book",
                                "POLICY_SHEET_ID": "policy_book"})
    assert P._pool_sheet_id() == "my_pool_book"       # 優先 POOL_SHEET_ID(不動持倉那本)


def test_pool_sheet_id_falls_back_to_baked_default(monkeypatch):
    _fake_secrets(monkeypatch, {"POLICY_SHEET_ID": "policy_book"})   # 無 POOL_SHEET_ID
    assert P._pool_sheet_id() == P._POOL_SHEET_ID_DEFAULT            # 回退 baked,**不**回退持倉


def test_pool_sheet_id_never_uses_policy_sheet(monkeypatch):
    # 核心不變量(user 2026-08-18「不能共上方的 id」):即使只有 POLICY_SHEET_ID 也不採用
    _fake_secrets(monkeypatch, {"POLICY_SHEET_ID": "policy_book"})
    assert P._pool_sheet_id() != "policy_book"


def test_gs_enabled_needs_sa_only_sheet_always_present(monkeypatch):
    # baked 預設讓 sheet 恆在 → SA 為唯一 gate(v19.472)
    _fake_secrets(monkeypatch, {"google_service_account": {"client_email": "sa@x.iam"}})
    assert P._gs_enabled() is True                    # 只要 SA 在 → 啟用(sheet 走 baked)
    _fake_secrets(monkeypatch, {"google_service_account": {}})
    assert P._gs_enabled() is False                   # SA 缺 client_email → 走本地
    _fake_secrets(monkeypatch, {})
    assert P._gs_enabled() is False                   # 無 SA → 走本地


def test_sa_present_accepts_json_string(monkeypatch):
    import json as _json
    _fake_secrets(monkeypatch, {"google_service_account": _json.dumps({"client_email": "sa@x.iam"})})
    assert P._sa_present() is True                     # env 字串 SA(NAS cron)也認得


# ── v19.472:併入對照表 —— isin/currency/secid 欄 + resolve_* + set_secid(退役 id_map)──────
def test_new_columns_roundtrip(store):
    store.upsert(PoolEntry(code="ALZF9", isin="lu0766462157", currency="usd",
                           morningstar_secid="F00000P8WB"))
    e = store.list_pool()[0]
    assert e.isin == "LU0766462157" and e.currency == "USD"   # 大寫正規化
    assert e.morningstar_secid == "F00000P8WB"


def test_old_row_pads_new_columns():
    e = PoolEntry.from_row(["ALZF9", "安聯", "股票"])        # 舊 3 欄列
    assert e.isin == "" and e.currency == "" and e.morningstar_secid == ""


def _patch_pool_cache(monkeypatch, entries):
    monkeypatch.setattr(P, "list_pool", lambda: entries)
    monkeypatch.setattr(P, "_cached_pool_map", P._load_pool_map)   # 繞過 streamlit 快取


def test_resolve_secid_hits_and_currency(monkeypatch):
    _patch_pool_cache(monkeypatch, [PoolEntry(code="ALZF9", morningstar_secid="SEC1", currency="TWD")])
    assert P.resolve_secid("alzf9") == ("SEC1", "TWD")            # 大小寫不分 + 帶幣別
    _patch_pool_cache(monkeypatch, [PoolEntry(code="X", morningstar_secid="SEC2")])
    assert P.resolve_secid("X") == ("SEC2", "USD")               # 幣別空 → 抓取退 USD


def test_resolve_secid_none_when_no_secid(monkeypatch):
    _patch_pool_cache(monkeypatch, [PoolEntry(code="ALZF9", isin="LU0766462157")])
    assert P.resolve_secid("ALZF9") is None                       # 有 ISIN 沒 secId → 不算命中


def test_resolve_isin_and_currency(monkeypatch):
    _patch_pool_cache(monkeypatch, [PoolEntry(code="ALZF9", isin="LU0766462157", currency="TWD")])
    assert P.resolve_isin("alzf9") == "LU0766462157"
    assert P.resolve_currency("ALZF9") == "TWD"
    assert P.resolve_isin("NOPE") is None and P.resolve_currency("NOPE") is None


def test_resolvers_survive_repo_error(monkeypatch):
    def _boom():
        raise RuntimeError("GS down")
    monkeypatch.setattr(P, "list_pool", _boom)
    monkeypatch.setattr(P, "_cached_pool_map", P._load_pool_map)
    assert P.resolve_secid("ALZF9") is None and P.resolve_isin("ALZF9") is None   # 不炸


def test_set_secid_writes_back_keeps_isin_and_currency(monkeypatch, tmp_path):
    store = LocalJsonPoolStore(base_dir=tmp_path)
    store.upsert(PoolEntry(code="X", isin="TW123", currency="TWD", name="測試"))
    monkeypatch.setattr(P, "get_pool_store", lambda oauth_client=None: store)
    monkeypatch.setattr(P, "_clear_pool_cache", lambda: None)
    P.set_secid("x", "0P00SEC")                                   # 不傳幣別 → 沿用 TWD
    e = store.list_pool()[0]
    assert e.morningstar_secid == "0P00SEC" and e.isin == "TW123"
    assert e.currency == "TWD" and e.name == "測試"               # 幣別/名稱保留


def test_set_secid_no_op_when_code_absent(monkeypatch, tmp_path):
    store = LocalJsonPoolStore(base_dir=tmp_path)
    monkeypatch.setattr(P, "get_pool_store", lambda oauth_client=None: store)
    monkeypatch.setattr(P, "_clear_pool_cache", lambda: None)
    P.set_secid("NOPE", "SEC")                                    # 不在池 → 不硬建列(§1)
    assert store.list_pool() == []


def test_add_remove_clear_pool_cache(monkeypatch, tmp_path):
    _calls = []
    monkeypatch.setattr(P, "_clear_pool_cache", lambda: _calls.append(1))
    monkeypatch.setattr(P, "get_pool_store", lambda oauth_client=None: LocalJsonPoolStore(base_dir=tmp_path))
    P.add_or_update(PoolEntry(code="ALZF9", isin="LU0766462157"))
    P.remove_from_pool("ALZF9")
    assert _calls == [1, 1]                                       # 加/刪各清一次(立即生效)


def test_clear_pool_cache_headless_no_crash():
    P._clear_pool_cache()                                         # plain 版無 .clear() → 不炸
