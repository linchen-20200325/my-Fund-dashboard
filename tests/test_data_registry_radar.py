"""tests/test_data_registry_radar.py — v19.140 雷達 10 燈進診斷表回歸

背景：user 截圖顯示風險雷達 2 盞燈 ⬜ 無資料（VIX 期限結構 / Put/Call），但
資料診斷頁 28 個項目裡完全沒有這兩個 → 無法定位失敗在哪層 fallback。
根因：_update_data_registry() 從未讀 _radar_v1921_top。本檔回歸該行為。
"""
from __future__ import annotations

import streamlit as st

from ui.helpers.data_registry import _update_data_registry


def _reset():
    for k in list(st.session_state.keys()):
        del st.session_state[k]


def test_radar_lights_registered_when_session_has_them():
    """有 _radar_v1921_top → 10 盞燈進 registry，key 前綴雷達_。"""
    _reset()
    _radar = {
        "vix_level":       {"signal": "🟢 平靜", "value": 19.03,
                            "label": "Yahoo ^VIX 日線", "note": "ok",
                            "color": "#3fb950", "prev": 18.6, "trend": []},
        "vix_term_struct": {"signal": "⬜ 無資料", "value": None,
                            "label": "Yahoo ^VIX / VIX3M（全源失敗）",
                            "note": "VIX/VIX3M 全源失敗｜Yahoo ^VIX3M: empty",
                            "color": "#6e7681", "prev": None, "trend": []},
        "hy_oas_delta":    {"signal": "🟢 平靜", "value": 2.71,
                            "label": "FRED BAMLH0A0HYM2 日線", "note": "ok",
                            "color": "#3fb950", "prev": 2.65, "trend": []},
        "yield_10y_shock": {"signal": "🟢 平靜", "value": 4.5,
                            "label": "FRED DGS10 日線", "note": "ok",
                            "color": "#3fb950", "prev": 4.51, "trend": []},
        "move_level":      {"signal": "🟢 平靜", "value": 65.4,
                            "label": "Yahoo ^MOVE 日線", "note": "ok",
                            "color": "#3fb950", "prev": 64, "trend": []},
        "spx_trend_break": {"signal": "🟢 平靜", "value": 7392, "label": "Yahoo ^GSPC",
                            "note": "ok", "color": "#3fb950", "prev": 7400, "trend": []},
        "sox_drop":        {"signal": "🟢 平靜", "value": 13755, "label": "Yahoo ^SOX",
                            "note": "ok", "color": "#3fb950", "prev": 13700, "trend": []},
        "sector_rotation": {"signal": "🟡 警戒", "value": 2.26, "label": "Yahoo sector ETFs",
                            "note": "ok", "color": "#d29922", "prev": 2.20, "trend": []},
        "put_call_ratio":  {"signal": "⬜ 無資料", "value": None,
                            "label": "CBOE Put/Call chain（全源失敗）",
                            "note": "並行抓取失敗：TimeoutError",
                            "color": "#6e7681", "prev": None, "trend": []},
        "asia_overnight":  {"signal": "🟢 平靜", "value": 1.59, "label": "Yahoo ^N225 + ^HSI",
                            "note": "ok", "color": "#3fb950", "prev": 1.5, "trend": []},
    }
    st.session_state["_radar_v1921_top"] = (_radar, None)

    _update_data_registry()
    reg = st.session_state.get("data_registry", {})

    radar_keys = [k for k in reg if k.startswith("雷達_")]
    assert len(radar_keys) == 10, f"預期 10 盞燈，實際 {len(radar_keys)}: {radar_keys}"

    # 兩盞失敗燈：🔴 + note 透出
    e_vix3m = reg["雷達_vix_term_struct"]
    assert e_vix3m["fresh_icon"] == "🔴"
    assert "VIX3M" in e_vix3m["fresh_label"] or "全源失敗" in e_vix3m["fresh_label"]

    e_pcr = reg["雷達_put_call_ratio"]
    assert e_pcr["fresh_icon"] == "🔴"
    assert "TimeoutError" in e_pcr["fresh_label"]
    assert "CBOE" in e_pcr["source"]

    # 已取得燈：🟢 + value 在 fresh_label
    e_vix = reg["雷達_vix_level"]
    assert e_vix["fresh_icon"] == "🟢"
    assert e_vix["count"] == 1


def test_no_radar_in_session_no_entries():
    """無 _radar_v1921_top → 不影響其他 registry，雷達 entries 為空（不偽綠）。"""
    _reset()
    _update_data_registry()
    reg = st.session_state.get("data_registry", {})
    radar_keys = [k for k in reg if k.startswith("雷達_")]
    assert radar_keys == [], "未載入雷達不應出現任何雷達 entry"


def test_indicators_meta_underscore_keys_filtered():
    """v19.140: indicators dict 內 _ 前綴 key(macro_service._fred_sources 等 meta)
    不該進診斷表,否則 user 看到 '⬜ 未知日期 / 0 筆數' 幽靈列。"""
    _reset()
    st.session_state["indicators"] = {
        "VIX": {"name": "VIX 恐慌指數", "value": 19.0, "date": "2026-06-25",
                "series": None},
        "_fred_sources": {"VIX": "FRED VIXCLS", "PMI": "FRED NAPM"},  # meta dict
    }
    _update_data_registry()
    reg = st.session_state.get("data_registry", {})
    keys = list(reg.keys())
    assert "總經_VIX" in reg, "真實指標應入表"
    assert "總經__fred_sources" not in reg, "_ 前綴 meta 不該入表"
    assert not any(k.endswith("_fred_sources") for k in keys), \
        f"_fred_sources 不該以任何形式入表: {keys}"


def test_partial_radar_only_loaded_lights_registered():
    """部分燈缺 key（型錯）→ 其他正常處理，缺者跳過或失敗顯示。"""
    _reset()
    _radar = {
        "vix_level": {"signal": "🟢", "value": 19, "label": "Yahoo ^VIX",
                      "note": "ok", "color": "#3fb950", "prev": 18, "trend": []},
        "vix_term_struct": "not-a-dict",   # 型錯 → 應安全 skip
        "put_call_ratio": {"signal": "⬜", "value": None,
                           "label": "CBOE", "note": "fail",
                           "color": "#6e7681", "prev": None, "trend": []},
    }
    st.session_state["_radar_v1921_top"] = (_radar, None)
    _update_data_registry()
    reg = st.session_state.get("data_registry", {})
    assert "雷達_vix_level" in reg
    assert "雷達_vix_term_struct" not in reg, "型錯 entry 應被 skip 不入表"
    assert "雷達_put_call_ratio" in reg
    assert reg["雷達_put_call_ratio"]["fresh_icon"] == "🔴"
