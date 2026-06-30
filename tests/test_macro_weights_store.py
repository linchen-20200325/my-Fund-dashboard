"""test_macro_weights_store.py — Route C-2 active.json 注入器單測.

v19.250 B 後:pending review ceremony 已退役,本檔只測 active.json 注入機制。

驗證重點:
- load_active 缺檔 / corrupt / 缺必要欄位 fallback
- apply_weight_overrides 各邊界(空 ind / 缺 key / 非 dict / 非數字 weight / 不波及其他欄位)
- get_weight_override 單 key 查詢
- get_verdict_cutoffs / get_phase_thresholds 順序與型別驗證
- GS backend(active row3 only)
"""
from __future__ import annotations

import json

import pytest

# v19.202 P2-2:macro_weights_store 搬 services.macro.weights_store,test patch 用實際居所避免 shim 隔離
from services.macro import weights_store as store


@pytest.fixture(autouse=True)
def _redirect_paths(tmp_path, monkeypatch):
    """把 store 模組指向 tmp_path 避免污染真實 config/。"""
    monkeypatch.setattr(store, "_CONFIG_DIR", tmp_path)
    monkeypatch.setattr(store, "_ACTIVE_PATH", tmp_path / "macro_weights_active.json")
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


# ════════════════════════════════════════════════════════════════
# C-2 override 注入器測試
# ════════════════════════════════════════════════════════════════
def _write_active(payload: dict) -> None:
    """測試用:直接寫 active.json(已透過 fixture 重導向到 tmp_path)。"""
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
    """允許 caller 傳 custom fallback(給 calibration tests 隔離用)."""
    _write_active({"version": "v19.0", "indicators": {}})
    assert store.get_phase_thresholds(fallback=(9.0, 6.0, 4.0)) == (9.0, 6.0, 4.0)


# ─── 端對端:active 缺檔 / corrupt 都要 fallback ─────────────────
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
# v19.7:Google Sheets backend tests(MagicMock 模擬 worksheet,active row3 only)
# ════════════════════════════════════════════════════════════════
class _FakeWorksheet:
    """In-memory worksheet — 模擬 gspread.Worksheet 的 acell + update。
    v19.250 B:active row3 only;pending row2/row4 退役後不再參與測試。"""

    def __init__(self):
        self._cells: dict[str, str] = {
            "A1": "slot", "B1": "payload_json", "C1": "updated_at",
            "A3": "active", "B3": "", "C3": "",
        }

    def acell(self, ref: str):
        class _V:
            def __init__(self, v): self.value = v
        return _V(self._cells.get(ref, ""))

    def update(self, range_str: str, values):
        # 解析 "B3:C3" → 寫入 values[0]
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


def test_gs_load_active_empty_returns_empty_fallback(_gs_backend):
    out = store.load_active()
    assert isinstance(out, dict)
    assert out["indicators"] == {}


def test_gs_load_active_valid_payload(_gs_backend):
    """GS row3 含有效 payload → load_active 解析正常."""
    _gs_backend._cells["B3"] = json.dumps(
        {"version": "v19.0", "indicators": {"VIX": {"weight": 0.9}}}
    )
    out = store.load_active()
    assert out["indicators"]["VIX"]["weight"] == 0.9


def test_gs_load_active_corrupt_returns_empty(_gs_backend):
    """GS row3 corrupt → load_active 回 _empty_active 而非 raise."""
    _gs_backend._cells["B3"] = "{not valid json"
    out = store.load_active()
    assert out["indicators"] == {}


def test_gs_enabled_false_falls_back_to_fs():
    # _gs_enabled 預設 False(無 streamlit secrets)→ 走 FS path
    # 既有 FS test 全部用此 path,這裡只確認偵測函式預設行為
    assert store._gs_enabled() is False
