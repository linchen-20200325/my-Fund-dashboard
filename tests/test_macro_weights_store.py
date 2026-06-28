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
    # v19.14：雙軌 pending — pullback 槽
    monkeypatch.setattr(
        store, "_PENDING_PULLBACK_PATH",
        tmp_path / "macro_weights_pending_pullback.json",
    )
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


# ════════════════════════════════════════════════════════════════
# v19.7：Google Sheets backend tests（MagicMock 模擬 worksheet）
# ════════════════════════════════════════════════════════════════
class _FakeWorksheet:
    """In-memory worksheet — 模擬 gspread.Worksheet 的 acell + update。"""

    def __init__(self):
        # 預建 schema：A1/B1/C1 header, B2/C2=pending, B3/C3=active
        # v19.14：A4/B4/C4=pending_pullback（雙軌 mode）
        self._cells: dict[str, str] = {
            "A1": "slot", "B1": "payload_json", "C1": "updated_at",
            "A2": "pending", "B2": "", "C2": "",
            "A3": "active",  "B3": "", "C3": "",
            "A4": "pending_pullback", "B4": "", "C4": "",
        }

    def acell(self, ref: str):
        class _V:
            def __init__(self, v): self.value = v
        return _V(self._cells.get(ref, ""))

    def update(self, range_str: str, values):
        # 解析 "B2:C2" → 寫入 values[0]
        if ":" in range_str:
            start, end = range_str.split(":")
            self._cells[start] = values[0][0]
            self._cells[end] = values[0][1]
        else:
            self._cells[range_str] = values[0][0]


@pytest.fixture
def _gs_backend(monkeypatch):
    """模擬 GS 已啟用 — 用 FakeWorksheet 取代真實 gspread 呼叫。"""
    fake_ws = _FakeWorksheet()
    monkeypatch.setattr(store, "_gs_enabled", lambda: True)
    monkeypatch.setattr(store, "_gs_get_worksheet", lambda: fake_ws)
    return fake_ws


def test_gs_save_and_load_pending_roundtrip(_gs_backend):
    payload = {"version": "v19.0", "indicators": {"VIX": {"weight": 1.0}}}
    ref = store.save_pending(payload)
    assert "_macro_weights!B" in str(ref)
    loaded = store.load_pending()
    assert loaded is not None
    assert loaded["indicators"]["VIX"]["weight"] == 1.0


def test_gs_has_pending_reflects_state(_gs_backend):
    assert store.has_pending() is False
    store.save_pending({"version": "v19.0", "indicators": {}})
    assert store.has_pending() is True


def test_gs_approve_promotes_and_clears(_gs_backend):
    payload = {"version": "v19.0", "indicators": {"VIX": {"weight": 1.0}}}
    store.save_pending(payload)
    assert store.approve_pending() is True
    assert store.load_pending() is None
    assert store.load_active()["indicators"]["VIX"]["weight"] == 1.0


def test_gs_approve_no_pending_returns_false(_gs_backend):
    assert store.approve_pending() is False


def test_gs_reject_deletes(_gs_backend):
    store.save_pending({"version": "v19.0", "indicators": {}})
    assert store.reject_pending() is True
    assert store.has_pending() is False
    assert store.reject_pending() is False


def test_gs_load_active_empty_returns_empty_fallback(_gs_backend):
    out = store.load_active()
    assert isinstance(out, dict)
    assert out["indicators"] == {}


def test_gs_save_pending_overwrites(_gs_backend):
    store.save_pending({"version": "v19.0", "indicators": {"A": {"weight": 1}}})
    store.save_pending({"version": "v19.0", "indicators": {"B": {"weight": 1}}})
    loaded = store.load_pending()
    assert loaded is not None
    assert "B" in loaded["indicators"]
    assert "A" not in loaded["indicators"]


def test_gs_corrupt_payload_returns_none(_gs_backend):
    # 直接寫進 fake worksheet 模擬 corrupt
    _gs_backend._cells["B2"] = "{not valid json"
    assert store.load_pending() is None
    assert store.has_pending() is False


def test_gs_enabled_false_falls_back_to_fs():
    # _gs_enabled 預設 False（無 streamlit secrets）→ 走 FS path
    # 既有 FS test 全部用此 path，這裡只確認偵測函式預設行為
    assert store._gs_enabled() is False


# ════════════════════════════════════════════════════════════════
# v19.14：雙軌 pending mode 路由測試
# ════════════════════════════════════════════════════════════════
_PAYLOAD_M = {"version": "v19.0", "indicators": {"VIX": {"weight": 0.6}}}
_PAYLOAD_P = {"version": "v19.0", "indicators": {"VIX_DELTA_5D": {"weight": 0.8}}}


def test_v19_14_pending_modes_constant_exposes_two_modes():
    """PENDING_MODES 對外 expose 兩 mode，順序固定（macro, pullback）— banner 顯示用."""
    assert store.PENDING_MODES == ("macro", "pullback")


def test_v19_14_save_pending_mode_macro_writes_legacy_path():
    """mode='macro' → 同 None，寫 legacy `_PENDING_PATH`（v19.0 向後相容）."""
    p = store.save_pending(_PAYLOAD_M, mode="macro")
    assert p == store._PENDING_PATH
    assert store._PENDING_PATH.exists()
    assert not store._PENDING_PULLBACK_PATH.exists()


def test_v19_14_save_pending_mode_none_equivalent_to_macro():
    """mode=None（legacy 簽名）→ 仍寫 legacy `_PENDING_PATH`."""
    p = store.save_pending(_PAYLOAD_M)
    assert p == store._PENDING_PATH


def test_v19_14_save_pending_mode_pullback_writes_new_path():
    """mode='pullback' → 寫獨立新檔，不污染 legacy 槽."""
    p = store.save_pending(_PAYLOAD_P, mode="pullback")
    assert p == store._PENDING_PULLBACK_PATH
    assert store._PENDING_PULLBACK_PATH.exists()
    assert not store._PENDING_PATH.exists()


def test_v19_14_save_pending_mode_unknown_raises():
    """mode 非 macro / pullback / None → ValueError，避免 typo 寫錯槽."""
    with pytest.raises(ValueError):
        store.save_pending(_PAYLOAD_M, mode="daily")
    with pytest.raises(ValueError):
        store.save_pending(_PAYLOAD_M, mode="")


def test_v19_14_dual_pending_slots_coexist():
    """雙 mode 各自寫入後同時存在 — 解 user 痛點「總經提交後 pullback 又提交把 macro 覆蓋」."""
    store.save_pending(_PAYLOAD_M, mode="macro")
    store.save_pending(_PAYLOAD_P, mode="pullback")
    assert store.has_pending(mode="macro") is True
    assert store.has_pending(mode="pullback") is True
    m = store.load_pending(mode="macro")
    p = store.load_pending(mode="pullback")
    assert "VIX" in m["indicators"]
    assert "VIX_DELTA_5D" in p["indicators"]


def test_v19_14_has_pending_mode_only_sees_own_slot():
    """has_pending(mode=A) 不會因 mode=B 槽存在而誤回 True."""
    store.save_pending(_PAYLOAD_M, mode="macro")
    assert store.has_pending(mode="macro") is True
    assert store.has_pending(mode="pullback") is False


def test_v19_14_load_pending_mode_only_sees_own_slot():
    """load_pending(mode=A) 拿不到 mode=B 槽的 payload."""
    store.save_pending(_PAYLOAD_P, mode="pullback")
    assert store.load_pending(mode="macro") is None
    out = store.load_pending(mode="pullback")
    assert out is not None
    assert "VIX_DELTA_5D" in out["indicators"]


def test_v19_14_approve_pending_pullback_only_clears_pullback_slot():
    """approve_pending(mode='pullback') 升格至共用 active，但不動 macro pending 槽."""
    store.save_pending(_PAYLOAD_M, mode="macro")
    store.save_pending(_PAYLOAD_P, mode="pullback")
    ok = store.approve_pending(mode="pullback")
    assert ok is True
    assert store.has_pending(mode="pullback") is False
    # macro 槽不受影響
    assert store.has_pending(mode="macro") is True
    # active 為 pullback payload（共用單槽）
    active = store.load_active()
    assert "VIX_DELTA_5D" in active["indicators"]


def test_v19_14_reject_pending_pullback_only_clears_pullback_slot():
    """reject_pending(mode='pullback') 不會誤刪 macro 槽."""
    store.save_pending(_PAYLOAD_M, mode="macro")
    store.save_pending(_PAYLOAD_P, mode="pullback")
    ok = store.reject_pending(mode="pullback")
    assert ok is True
    assert store.has_pending(mode="pullback") is False
    assert store.has_pending(mode="macro") is True


def test_v19_14_approve_no_pending_in_mode_returns_false():
    """指定 mode 槽空 → approve_pending 回 False，不動 active."""
    assert store.approve_pending(mode="pullback") is False
    active_path = store._ACTIVE_PATH
    assert not active_path.exists()


def test_v19_14_save_overwrite_within_same_mode():
    """同 mode 重複 save → 覆蓋；不影響另一 mode."""
    store.save_pending(_PAYLOAD_M, mode="macro")
    store.save_pending(
        {"version": "v19.0", "indicators": {"PMI": {"weight": 1.5}}},
        mode="macro",
    )
    out = store.load_pending(mode="macro")
    assert "VIX" not in out["indicators"]
    assert "PMI" in out["indicators"]


# ─── v19.14: GS backend mode routing ─────────────────────────────
def test_v19_14_gs_pullback_uses_row4(_gs_backend):
    """GS backend：pullback mode → 寫 row 4，不撞 row 2 (legacy/macro) / row 3 (active)."""
    ref = store.save_pending(_PAYLOAD_P, mode="pullback")
    assert "_macro_weights!B4" == ref
    # row 2 (legacy/macro pending) 仍空
    assert _gs_backend._cells.get("B2", "") == ""
    # row 4 已寫入
    assert _gs_backend._cells.get("B4")


def test_v19_14_gs_dual_pending_coexist(_gs_backend):
    """GS backend：macro 與 pullback 各自獨立 row，並存無覆蓋."""
    store.save_pending(_PAYLOAD_M, mode="macro")
    store.save_pending(_PAYLOAD_P, mode="pullback")
    assert store.has_pending(mode="macro") is True
    assert store.has_pending(mode="pullback") is True


def test_v19_14_gs_approve_pullback_only_clears_row4(_gs_backend):
    """GS backend：approve pullback 只清 row 4，row 2 (macro pending) 不動."""
    store.save_pending(_PAYLOAD_M, mode="macro")
    store.save_pending(_PAYLOAD_P, mode="pullback")
    assert store.approve_pending(mode="pullback") is True
    assert store.has_pending(mode="pullback") is False
    assert store.has_pending(mode="macro") is True


# ─── v19.14: pure helpers ─────────────────────────────────────────
def test_v19_14_pending_slot_for_mode_routing():
    """mode → GS slot key 路由助手（None / 'macro' 同槽 / 'pullback' 獨立槽）."""
    assert store._pending_slot_for_mode(None) == "pending"
    assert store._pending_slot_for_mode("macro") == "pending"
    assert store._pending_slot_for_mode("pullback") == "pending_pullback"
    with pytest.raises(ValueError):
        store._pending_slot_for_mode("daily")


def test_v19_14_pending_path_for_mode_routing():
    """mode → FS 路徑路由助手."""
    assert store._pending_path_for_mode(None) == store._PENDING_PATH
    assert store._pending_path_for_mode("macro") == store._PENDING_PATH
    assert store._pending_path_for_mode("pullback") == store._PENDING_PULLBACK_PATH
    with pytest.raises(ValueError):
        store._pending_path_for_mode("daily")
