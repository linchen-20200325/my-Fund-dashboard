"""tests/test_mcp_server_smoke.py — MCP server PoC 冒煙測試。

覆蓋 §6「3 個最容易出錯的輸入」+ fail-loud 邊界 + JSON 可序列化:
1. 缺 FRED_API_KEY          → build_macro_snapshot raise(不回半空假分數,§1)
2. 全來源失敗(指標回 {})  → build_macro_snapshot raise(§1)
3. NaN / inf / Timestamp / numpy 型別 → to_json_safe 轉成 JSON-safe(不炸、NaN→None)

外加:error_envelope 把 raise 攔成 {"ok": False, ...}(fail-loud → 結構化);
happy path monkeypatch L2 → 回傳鍵齊全且 json.dumps 過關。

不打網路:全部 monkeypatch L2 函式。fastmcp 未安裝也能跑(只測 _serialize + tools_macro)。
"""
from __future__ import annotations

import datetime as dt
import json

import numpy as np
import pandas as pd
import pytest

from mcp_server import tools_macro
from mcp_server._serialize import error_envelope, to_json_safe
from mcp_server.tools_macro import MacroSnapshotError, build_macro_snapshot


# ───────────────────────── to_json_safe ─────────────────────────
def test_to_json_safe_nan_inf_become_none():
    """§1:NaN / ±inf 一律 None,不可偽造成 0。"""
    assert to_json_safe(float("nan")) is None
    assert to_json_safe(float("inf")) is None
    assert to_json_safe(float("-inf")) is None
    assert to_json_safe(np.nan) is None


def test_to_json_safe_numpy_and_time_types():
    assert to_json_safe(np.int64(7)) == 7 and isinstance(to_json_safe(np.int64(7)), int)
    assert to_json_safe(np.float64(1.5)) == 1.5
    assert to_json_safe(np.bool_(True)) is True
    ts = pd.Timestamp("2026-07-25")
    assert to_json_safe(ts) == ts.isoformat()
    assert to_json_safe(dt.date(2026, 7, 25)) == "2026-07-25"


def test_to_json_safe_containers_and_nesting():
    out = to_json_safe({"a": {1, 2}, "b": [np.int64(3), float("nan")], "c": ("x", None)})
    assert sorted(out["a"]) == [1, 2]          # set → list
    assert out["b"] == [3, None]               # NaN → None,numpy → int
    assert out["c"] == ["x", None]             # tuple → list
    # 整體必須 json 可序列化
    json.dumps(out)


def test_to_json_safe_series_and_dataframe():
    s = pd.Series({"x": np.float64(1.0), "y": float("nan")})
    assert to_json_safe(s) == {"x": 1.0, "y": None}
    df = pd.DataFrame({"v": [1, 2]}, index=["a", "b"])
    recs = to_json_safe(df)
    assert recs == [{"_index": "a", "v": 1}, {"_index": "b", "v": 2}]
    json.dumps(recs)


# ───────────────────────── error_envelope ───────────────────────
def test_error_envelope_success():
    env = error_envelope(lambda: {"n": np.int64(5), "bad": float("nan")})
    assert env["ok"] is True
    assert env["data"] == {"n": 5, "bad": None}
    json.dumps(env)


def test_error_envelope_catches_raise_as_structured():
    """fail-loud raise → {"ok": False, ...},不吞成假成功。"""
    def _boom():
        raise MacroSnapshotError("來源全掛")

    env = error_envelope(_boom)
    assert env["ok"] is False
    assert env["error_type"] == "MacroSnapshotError"
    assert "來源全掛" in env["error"]
    json.dumps(env)


# ─────────────────── build_macro_snapshot fail-loud ─────────────
def test_missing_fred_key_raises(monkeypatch):
    """輸入#1:缺 key → raise(§1 不回半空假分數)。"""
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    with pytest.raises(MacroSnapshotError, match="FRED_API_KEY"):
        build_macro_snapshot(fred_api_key="")


def test_all_sources_down_raises(monkeypatch):
    """輸入#2:全來源失敗(指標回 {})→ raise(§1)。"""
    monkeypatch.setattr(tools_macro, "fetch_all_indicators", lambda key: {})
    with pytest.raises(MacroSnapshotError, match="所有總經來源失敗"):
        build_macro_snapshot(fred_api_key="testkey")


# ─────────────────── build_macro_snapshot happy path ────────────
def _patch_l2(monkeypatch):
    """monkeypatch 全部 L2 依賴,回傳含 NaN / Timestamp / numpy 的結構(輸入#3)。"""
    def _fetch(key):
        return {"VIX": {"value": np.float64(15.0), "score": 1, "weight": 1,
                        "source": "yahoo", "fetched_at": "2026-07-25T00:00:00"}}

    def _score(ind, *, provenance_out=None):
        if provenance_out is not None:
            provenance_out.update(sources=["yahoo", "fred"],
                                  fetched_at_latest="2026-07-25T00:00:00",
                                  n_indicators=1)
        return 6.3

    monkeypatch.setattr(tools_macro, "fetch_all_indicators", _fetch)
    monkeypatch.setattr(tools_macro, "calculate_composite_score", _score)
    monkeypatch.setattr(tools_macro, "composite_verdict",
                        lambda t: ("🟢", "樂觀", "#00c853", "核心持有不動"))
    monkeypatch.setattr(tools_macro, "calc_macro_phase",
                        lambda ind: {"score": 6.5, "phase": "擴張", "phase_en": "Expansion",
                                     "rec_prob": np.float64(12.0), "alerts": ["⚠️ 測試警報"]})
    monkeypatch.setattr(tools_macro, "macro_action_light",
                        lambda ind, ps: {"light": "🟡", "action": "持有", "reasons": [], "override": False})
    # 故意塞 NaN + Timestamp 進 regime,驗證邊界序列化(輸入#3)
    monkeypatch.setattr(tools_macro, "identify_regime",
                        lambda ind: {"regime": "risk_on", "conf": float("nan"),
                                     "as_of": pd.Timestamp("2026-07-25")})
    monkeypatch.setattr(tools_macro, "reconcile_composite_score",
                        lambda ind: {"status": "agree", "vote_net_ratio": 0.5})


def test_snapshot_happy_path_keys(monkeypatch):
    _patch_l2(monkeypatch)
    snap = build_macro_snapshot(fred_api_key="testkey")
    assert snap["composite_score"] == 6.3
    assert snap["verdict"]["level"] == "樂觀"
    assert snap["phase"]["score_10"] == 6.5
    assert snap["phase"]["name"] == "擴張"
    assert snap["action_light"]["light"] == "🟡"
    assert snap["provenance"]["n_indicators"] == 1


def test_snapshot_through_envelope_is_json_safe(monkeypatch):
    """輸入#3:regime 內的 NaN/Timestamp 經 error_envelope→to_json_safe 後 json.dumps 過關。"""
    _patch_l2(monkeypatch)
    env = error_envelope(build_macro_snapshot, "testkey")
    assert env["ok"] is True
    data = env["data"]
    assert data["regime"]["conf"] is None                    # NaN → None
    assert data["regime"]["as_of"] == pd.Timestamp("2026-07-25").isoformat()
    json.dumps(env)                                           # 不可炸
