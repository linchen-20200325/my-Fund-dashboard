"""test_macro_weights_store.py — Route C-1 儲存層單測.

驗證重點：
- load_active / load_pending 缺檔 fallback
- save_pending schema 驗證 + 覆蓋行為
- approve_pending = 升格 + 刪 pending
- reject_pending = 刪 pending 不動 active
- build_payload_from_multifactor schema 完整
"""
from __future__ import annotations

import json

import pytest

import services.macro_weights_store as store


@pytest.fixture(autouse=True)
def _redirect_paths(tmp_path, monkeypatch):
    """把 store 模組指向 tmp_path 避免污染真實 config/。"""
    monkeypatch.setattr(store, "_CONFIG_DIR", tmp_path)
    monkeypatch.setattr(store, "_ACTIVE_PATH", tmp_path / "macro_weights_active.json")
    monkeypatch.setattr(store, "_PENDING_PATH", tmp_path / "macro_weights_pending.json")
    yield


# ─── load_active ──────────────────────────────────────────────────
def test_load_active_missing_returns_empty():
    out = store.load_active()
    assert isinstance(out, dict)
    assert out["indicators"] == {}
    assert "empty" in out["version"]


def test_load_active_valid_returns_payload(tmp_path):
    payload = {"version": "v19.0", "indicators": {"VIX": {"weight": 1.0}}}
    store._ACTIVE_PATH.write_text(json.dumps(payload), encoding="utf-8")
    out = store.load_active()
    assert out["indicators"]["VIX"]["weight"] == 1.0


def test_load_active_corrupt_returns_empty(tmp_path):
    store._ACTIVE_PATH.write_text("{not valid json", encoding="utf-8")
    out = store.load_active()
    assert out["indicators"] == {}


def test_load_active_missing_required_key(tmp_path):
    store._ACTIVE_PATH.write_text('{"version": "v19.0"}', encoding="utf-8")
    out = store.load_active()
    assert out["indicators"] == {}  # fallback


# ─── load_pending / has_pending ───────────────────────────────────
def test_load_pending_missing_returns_none():
    assert store.load_pending() is None
    assert store.has_pending() is False


def test_load_pending_valid(tmp_path):
    payload = {"version": "v19.0", "indicators": {"VIX": {"weight": 0.5}}}
    store._PENDING_PATH.write_text(json.dumps(payload), encoding="utf-8")
    assert store.has_pending() is True
    out = store.load_pending()
    assert out["indicators"]["VIX"]["weight"] == 0.5


def test_load_pending_corrupt_returns_none(tmp_path):
    store._PENDING_PATH.write_text("garbage", encoding="utf-8")
    assert store.load_pending() is None


# ─── save_pending ─────────────────────────────────────────────────
def test_save_pending_writes_file(tmp_path):
    payload = {"version": "v19.0", "indicators": {"PMI": {"weight": 2.0}}}
    p = store.save_pending(payload)
    assert p.exists()
    out = json.loads(p.read_text(encoding="utf-8"))
    assert out["indicators"]["PMI"]["weight"] == 2.0


def test_save_pending_invalid_raises(tmp_path):
    with pytest.raises(ValueError):
        store.save_pending({"missing": "version"})
    with pytest.raises(ValueError):
        store.save_pending({"version": "x", "indicators": "not a dict"})


def test_save_pending_overwrites(tmp_path):
    store.save_pending({"version": "v19.0", "indicators": {"A": {"weight": 1.0}}})
    store.save_pending({"version": "v19.0", "indicators": {"B": {"weight": 2.0}}})
    out = store.load_pending()
    assert "A" not in out["indicators"]
    assert out["indicators"]["B"]["weight"] == 2.0


# ─── approve_pending ──────────────────────────────────────────────
def test_approve_pending_promotes_and_deletes(tmp_path):
    payload = {"version": "v19.0", "indicators": {"VIX": {"weight": 0.7}}}
    store.save_pending(payload)
    ok = store.approve_pending()
    assert ok is True
    assert not store.has_pending()
    active = store.load_active()
    assert active["indicators"]["VIX"]["weight"] == 0.7


def test_approve_no_pending_returns_false():
    assert store.approve_pending() is False


def test_approve_corrupt_pending_returns_false(tmp_path):
    store._PENDING_PATH.write_text("garbage", encoding="utf-8")
    assert store.approve_pending() is False
    # active 不應被覆蓋
    assert not store._ACTIVE_PATH.exists()


# ─── reject_pending ───────────────────────────────────────────────
def test_reject_pending_deletes(tmp_path):
    store.save_pending({"version": "v19.0", "indicators": {}})
    assert store.has_pending() is True
    ok = store.reject_pending()
    assert ok is True
    assert not store.has_pending()


def test_reject_no_pending_returns_false():
    assert store.reject_pending() is False


def test_reject_does_not_touch_active(tmp_path):
    active = {"version": "v19.0", "indicators": {"VIX": {"weight": 1.0}}}
    store._ACTIVE_PATH.write_text(json.dumps(active), encoding="utf-8")
    store.save_pending({"version": "v19.0", "indicators": {"PMI": {"weight": 2.0}}})
    store.reject_pending()
    after = store.load_active()
    assert after["indicators"]["VIX"]["weight"] == 1.0


# ─── build_payload_from_multifactor ──────────────────────────────
def test_build_payload_schema_complete():
    opt = {"weights": {"VIX": 0.5, "HY": 0.3, "PMI": 0.2},
           "f1": 0.7, "sharpe": 1.2, "plateau_score": 0.65}
    wf = {"oos_f1": 0.6, "oos_sharpe": 0.9, "n_folds": 4}
    payload = store.build_payload_from_multifactor(
        opt, wf, ["VIX", "HY", "PMI"], "f1",
        ai_explanation="test explanation",
    )
    assert payload["version"] == "v19.0"
    assert payload["calibration_method"] == "multi_factor_plateau_f1"
    assert set(payload["indicators"].keys()) == {"VIX", "HY", "PMI"}
    assert payload["indicators"]["VIX"]["weight"] == 0.5
    assert payload["oos_metrics"]["oos_f1"] == 0.6
    assert payload["oos_metrics"]["n_folds"] == 4
    assert payload["ai_explanation"] == "test explanation"
    # 通過 schema 驗證可直接 save
    store.save_pending(payload)
    assert store.has_pending()


def test_build_payload_handles_missing_fields():
    payload = store.build_payload_from_multifactor(
        opt={}, wf={}, sel_keys=["VIX"], metric="sharpe",
    )
    assert payload["indicators"]["VIX"]["weight"] == 0.0
    assert payload["oos_metrics"]["oos_f1"] == 0.0
    assert payload["ai_explanation"] is None
