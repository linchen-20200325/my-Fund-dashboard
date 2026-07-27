"""tests/test_ai_cache.py — AI 白話總體檢磁碟續存測試(v19.410)。

驗:make_key 對 (tab, snapshot) 穩定且 snapshot 變則 key 變;save→load round-trip;
壞檔容錯回 None;上限汰舊;snapshot 變 → 不回顯舊 AI(key miss)。
"""
from __future__ import annotations

import json

import pytest

from repositories import ai_cache


@pytest.fixture(autouse=True)
def _tmp_path_file(tmp_path, monkeypatch):
    monkeypatch.setattr(ai_cache, "_PATH", tmp_path / "ai_cache.json")
    return tmp_path / "ai_cache.json"


def test_make_key_stable_and_snapshot_sensitive():
    k1 = ai_cache.make_key("tab2", "snapshot A")
    k2 = ai_cache.make_key("tab2", "snapshot A")
    k3 = ai_cache.make_key("tab2", "snapshot B")     # 資料變 → key 變
    k4 = ai_cache.make_key("tab3", "snapshot A")     # tab 不同 → key 不同
    assert k1 == k2 and k1 != k3 and k1 != k4
    assert k1.startswith("tab2:")


def test_save_load_roundtrip():
    k = ai_cache.make_key("tab2", "snap")
    assert ai_cache.load(k) is None
    ai_cache.save(k, "### AI 結論\n很健康")
    assert ai_cache.load(k) == "### AI 結論\n很健康"


def test_snapshot_change_misses_old_ai():
    """資料變(snapshot 變)→ 新 key miss → 不回顯過期 AI。"""
    ai_cache.save(ai_cache.make_key("tab2", "old data"), "舊結論")
    assert ai_cache.load(ai_cache.make_key("tab2", "new data")) is None


def test_corrupt_file_returns_none(_tmp_path_file):
    _tmp_path_file.write_text("{not json", encoding="utf-8")
    assert ai_cache.load("tab2:abc") is None          # 不 raise


def test_cap_evicts_oldest(monkeypatch):
    monkeypatch.setattr(ai_cache, "_MAX_ENTRIES", 3)
    # 用遞增 updated_at 確保汰舊順序可預期
    stamps = iter(["2026-07-01 00:00", "2026-07-02 00:00", "2026-07-03 00:00",
                   "2026-07-04 00:00", "2026-07-05 00:00"])
    monkeypatch.setattr(ai_cache._dt, "datetime", type("D", (), {
        "now": staticmethod(lambda tz=None: type("T", (), {
            "strftime": staticmethod(lambda *_: next(stamps))})())}))
    for i in range(5):
        ai_cache.save(f"tab:{i}", f"text{i}")
    data = json.loads(_tmp_path_file_read())
    assert len(data) == 3
    assert "tab:0" not in data and "tab:4" in data     # 最舊被汰、最新保留


def test_eviction_survives_nondict_value(_tmp_path_file, monkeypatch):
    """外部污染:valid-JSON 但某值非 dict → 汰舊不可因 .get 拋 AttributeError。"""
    monkeypatch.setattr(ai_cache, "_MAX_ENTRIES", 2)
    _tmp_path_file.write_text(
        json.dumps({"bad": "not-a-dict",
                    "x": {"text": "a", "updated_at": "2026-07-01 00:00"}}),
        encoding="utf-8")
    ai_cache.save("y", "b")
    ai_cache.save("z", "c")           # 觸發 >2 汰舊,不可炸
    assert ai_cache.load("z") == "c"


def _tmp_path_file_read():
    return ai_cache._PATH.read_text(encoding="utf-8")
