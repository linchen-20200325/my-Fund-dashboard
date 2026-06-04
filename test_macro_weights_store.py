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


# ════════════════════════════════════════════════════════════════
# C-2 override 注入器測試
# ════════════════════════════════════════════════════════════════
def _write_active(payload: dict) -> None:
    """測試用：直接寫 active.json（已透過 fixture 重導向到 tmp_path）。"""
    store._ACTIVE_PATH.write_text(json.dumps(payload), encoding="utf-8")


# ─── apply_weight_overrides ──────────────────────────────────────
def test_apply_overrides_empty_ind_returns_empty():
    assert store.apply_weight_overrides({}) == {}
    assert store.apply_weight_overrides(None) == {}


def test_apply_overrides_active_empty_returns_input():
    """active.json 沒有 indicators → 原 ind 不動."""
    ind = {"VIX": {"score": 0.5, "weight": 1.0}}
    out = store.apply_weight_overrides(ind)
    assert out["VIX"]["weight"] == 1.0


def test_apply_overrides_active_overrides_weight():
    _write_active({"version": "v19.0", "indicators": {"VIX": {"weight": 2.5}}})
    ind = {"VIX": {"score": 0.5, "weight": 1.0}}
    out = store.apply_weight_overrides(ind)
    assert out["VIX"]["weight"] == 2.5
    # 原 dict 不被 mutate
    assert ind["VIX"]["weight"] == 1.0


def test_apply_overrides_key_missing_in_active_unchanged():
    _write_active({"version": "v19.0", "indicators": {"PMI": {"weight": 3.0}}})
    ind = {"VIX": {"score": 0.5, "weight": 1.0}}
    out = store.apply_weight_overrides(ind)
    assert out["VIX"]["weight"] == 1.0  # 沒被改


def test_apply_overrides_non_numeric_weight_skipped():
    _write_active({"version": "v19.0", "indicators": {"VIX": {"weight": "bad"}}})
    ind = {"VIX": {"score": 0.5, "weight": 1.0}}
    out = store.apply_weight_overrides(ind)
    assert out["VIX"]["weight"] == 1.0


def test_apply_overrides_non_dict_value_preserved():
    ind = {"VIX": "not_a_dict", "PMI": {"score": 0.3, "weight": 2.0}}
    _write_active({"version": "v19.0", "indicators": {"PMI": {"weight": 5.0}}})
    out = store.apply_weight_overrides(ind)
    assert out["VIX"] == "not_a_dict"
    assert out["PMI"]["weight"] == 5.0


def test_apply_overrides_preserves_other_fields():
    """override weight 不能波及 score / series 等其他欄位。"""
    _write_active({"version": "v19.0", "indicators": {"VIX": {"weight": 0.7}}})
    ind = {"VIX": {"score": 0.6, "weight": 1.0, "series": "fake", "extra": 42}}
    out = store.apply_weight_overrides(ind)
    assert out["VIX"]["weight"] == 0.7
    assert out["VIX"]["score"] == 0.6
    assert out["VIX"]["series"] == "fake"
    assert out["VIX"]["extra"] == 42


# ─── get_weight_override ─────────────────────────────────────────
def test_get_weight_override_returns_active_value():
    _write_active({"version": "v19.0", "indicators": {"PMI": {"weight": 4.2}}})
    assert store.get_weight_override("PMI", fallback=2.0) == 4.2


def test_get_weight_override_returns_fallback_when_missing():
    _write_active({"version": "v19.0", "indicators": {}})
    assert store.get_weight_override("PMI", fallback=2.0) == 2.0


def test_get_weight_override_returns_fallback_on_bad_value():
    _write_active({"version": "v19.0", "indicators": {"PMI": {"weight": None}}})
    assert store.get_weight_override("PMI", fallback=2.0) == 2.0


# ─── get_verdict_cutoffs ─────────────────────────────────────────
def test_get_verdict_cutoffs_null_returns_fallback():
    _write_active({"version": "v19.0", "indicators": {}, "verdict_cutoffs": None})
    assert store.get_verdict_cutoffs() == (10.0, 5.0, -5.0, -10.0)


def test_get_verdict_cutoffs_valid_returns_active():
    _write_active({"version": "v19.0", "indicators": {},
                   "verdict_cutoffs": [12.0, 6.0, -4.0, -11.0]})
    assert store.get_verdict_cutoffs() == (12.0, 6.0, -4.0, -11.0)


def test_get_verdict_cutoffs_not_descending_falls_back():
    _write_active({"version": "v19.0", "indicators": {},
                   "verdict_cutoffs": [5.0, 10.0, -5.0, -10.0]})  # 順序錯
    assert store.get_verdict_cutoffs() == (10.0, 5.0, -5.0, -10.0)


def test_get_verdict_cutoffs_wrong_length_falls_back():
    _write_active({"version": "v19.0", "indicators": {},
                   "verdict_cutoffs": [10.0, 5.0, -5.0]})  # 只有 3 個
    assert store.get_verdict_cutoffs() == (10.0, 5.0, -5.0, -10.0)


def test_get_verdict_cutoffs_non_numeric_falls_back():
    _write_active({"version": "v19.0", "indicators": {},
                   "verdict_cutoffs": ["a", "b", "c", "d"]})
    assert store.get_verdict_cutoffs() == (10.0, 5.0, -5.0, -10.0)


# ─── get_phase_thresholds ───────────────────────────────────────
def test_get_phase_thresholds_null_returns_fallback():
    _write_active({"version": "v19.0", "indicators": {}, "phase_thresholds": None})
    assert store.get_phase_thresholds() == (8.0, 5.0, 3.0)


def test_get_phase_thresholds_valid_returns_active():
    _write_active({"version": "v19.0", "indicators": {},
                   "phase_thresholds": [7.5, 4.5, 2.5]})
    assert store.get_phase_thresholds() == (7.5, 4.5, 2.5)


def test_get_phase_thresholds_corrupt_falls_back():
    _write_active({"version": "v19.0", "indicators": {},
                   "phase_thresholds": [3.0, 5.0, 8.0]})  # 順序錯
    assert store.get_phase_thresholds() == (8.0, 5.0, 3.0)


def test_get_phase_thresholds_custom_fallback():
    """允許 caller 傳 custom fallback（給 calibration tests 隔離用）."""
    _write_active({"version": "v19.0", "indicators": {}})
    assert store.get_phase_thresholds(fallback=(9.0, 6.0, 4.0)) == (9.0, 6.0, 4.0)


# ─── 端對端：active 缺檔 / corrupt 都要 fallback ─────────────────
def test_no_active_file_all_helpers_fallback():
    """active.json 不存在時三 helper 都該回 default。"""
    assert store._ACTIVE_PATH.exists() is False
    assert store.apply_weight_overrides({"VIX": {"weight": 1.0}})["VIX"]["weight"] == 1.0
    assert store.get_weight_override("VIX", fallback=1.5) == 1.5
    assert store.get_verdict_cutoffs() == (10.0, 5.0, -5.0, -10.0)
    assert store.get_phase_thresholds() == (8.0, 5.0, 3.0)


def test_corrupt_active_all_helpers_fallback():
    store._ACTIVE_PATH.write_text("garbage", encoding="utf-8")
    assert store.apply_weight_overrides({"VIX": {"weight": 1.0}})["VIX"]["weight"] == 1.0
    assert store.get_weight_override("VIX", fallback=1.5) == 1.5
    assert store.get_verdict_cutoffs() == (10.0, 5.0, -5.0, -10.0)
    assert store.get_phase_thresholds() == (8.0, 5.0, 3.0)
