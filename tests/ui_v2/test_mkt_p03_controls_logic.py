# -*- coding: utf-8 -*-
"""Phase 3 P0-③ 市場總覽控制項簡化的純函式測試（fast lane；不需要 streamlit、不需要 source）。

依據：44 第七節第三小節之七其二第 5、7 條（`MKT-5` 多選清單；正式模式不畫永遠停用的「套用」與「重新取數」，
`MKT-0` 三塊皆空改畫「前往設定與診斷」），以及兩筆既有 bug：
- BL-0228：`MKT-5` 從未存過且一個都沒選時按存檔會寫入 `"[]"`；
- BL-0289：只套天數時，`MKT-4` 印出「基準日 None」。

只走 `live`／`logic` 純函式（`page.render` 正式路徑呼叫的同一支 `live.build_live_model`）；畫面層另見
`test_mkt_p03_controls_page.py`（slow）。
"""

from __future__ import annotations

import pathlib
import sys

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

from ui_v2.mkt import fixtures, live, logic  # noqa: E402

_AVAILABLE = ["vol_index", "credit_spread_pct", "policy_rate_pct", "term_spread_pct"]


def _live_input(dataset=None, settings=None, settings_error=None):
    return {
        "dataset": dataset if dataset is not None else fixtures.dataset_all_ok(),
        "notes": {"settings": settings or {}, "available_keys": list(_AVAILABLE),
                  "settings_error": settings_error, "pending": {}, "masked_keys": [], "cooldowns": []},
    }


def _model(dataset=None, settings=None, settings_error=None, **fields):
    return live.build_live_model(_live_input(dataset, settings, settings_error), save_wired=True, **fields)


def _mkt5_save(model):
    (button,) = logic.find_block(model, "MKT-5")["buttons"]
    return button


# ───────────────────────── 第 7 條：正式模式不畫的兩種按鈕 ─────────────────────────


def _btn(kind, enabled):
    return {"_action_kind": kind, "_enabled": enabled}


@pytest.mark.parametrize("kind, enabled, hidden", [
    ("套用", False, True),
    ("取數", False, True),
    ("取數", True, False),     # 日後接上取數、變成可用 → 不藏（44 其二第 7 條末句：不預先授權隱藏可用的按鈕）
    ("套用", True, False),
    ("存檔", False, False),    # 其餘停用按鈕照舊不隱藏（44 5.3）
    ("導覽", True, False),
])
def test_正式模式只不畫停用中的套用與重新取數(kind, enabled, hidden):
    assert live.hidden_in_live(_btn(kind, enabled)) is hidden


def test_正式模式模型照舊帶著兩種按鈕_停用並寫原因_頁面模型不變():
    """只改畫不畫：模型裡的按鈕、停用狀態與原因一個都不動（44 其二第 7 條：頁面模型與資料判定不變）。"""
    model = _model(dataset=fixtures.all_datasets()["all_empty"])
    apply_button = logic.find_block(model, "MKT-4")["buttons"][0]
    assert apply_button["_action_kind"] == "套用" and apply_button["_enabled"] is False
    assert apply_button["disabled_reason"] == live.APPLY_DISABLED_REASON
    retries = [b for b in live._walk_buttons(model["blocks"]) if b["_action_kind"] == "取數"]
    assert len(retries) == 4                               # 三張卡各一枚 ＋ 燈上一枚（三塊皆空）
    assert all(not b["_enabled"] and b["disabled_reason"] == live.RETRY_DISABLED_REASON for b in retries)
    assert all(live.hidden_in_live(b) for b in retries) and live.hidden_in_live(apply_button)


def test_三塊皆空_燈改畫前往設定與診斷_其餘情形不畫():
    empty = _model(dataset=fixtures.all_datasets()["all_empty"])
    assert live.light_needs_settings_link(logic.find_block(empty, "MKT-0")) is True
    for name, dataset in fixtures.all_datasets().items():
        if name == "all_empty":
            continue
        model = _model(dataset=dataset)
        assert live.light_needs_settings_link(logic.find_block(model, "MKT-0")) is False, name


def test_示範模式模型不經過live_燈上的重新取數照舊可按():
    model = logic.build_page_model(fixtures.all_datasets()["all_empty"])
    (retry,) = logic.find_block(model, "MKT-0")["buttons"]
    assert retry["_action_kind"] == "取數" and retry["_enabled"] is True
    assert live.hidden_in_live(retry) is False


# ───────────────────────── 第 5 條：多選清單的初值 ─────────────────────────


def test_多選清單初值_從未存過或讀不到不填_已存過依已存清單且依可選清單順序():
    keys = list(_AVAILABLE)
    assert live.initial_picks({}, keys) is None
    assert live.initial_picks({"indicator_keys": ["vol_index"]}, keys, "讀不到") is None
    saved = {"indicator_keys": ["term_spread_pct", "vol_index", "已下架的鍵"]}
    assert live.initial_picks(saved, keys) == ["vol_index", "term_spread_pct"]
    assert live.initial_picks({"indicator_keys": []}, keys) == []


# ───────────────────────── BL-0228：從未存過不寫 "[]" ─────────────────────────


def test_BL0228_從未存過且一個都沒選_存檔停用並寫原因():
    save = _mkt5_save(_model(settings={}, field_selected_keys=[]))
    assert save["_enabled"] is False and save["disabled_reason"] == logic.TEXT_SAVE_NOTHING_PICKED


def test_BL0228_從未存過但選了_存檔可按():
    assert _mkt5_save(_model(settings={}, field_selected_keys=["vol_index"]))["_enabled"] is True


@pytest.mark.parametrize("saved", [[], ["vol_index"]])
def test_BL0228_已存過_含已存的空清單_清空再存照舊允許(saved):
    """44 `MKT-5` 判準「取消全部勾選並存檔、重新載入，下方明細出現『尚未選定任何指標』」要做得到。"""
    assert _mkt5_save(_model(settings={"indicator_keys": saved}, field_selected_keys=[]))["_enabled"] is True


def test_BL0228_示範模式畫面維持現行_從未存過一個都沒選照舊可按():
    model = logic.build_page_model(fixtures.dataset_all_ok(), field_selected_keys=[])
    assert _mkt5_save(model)["_enabled"] is True


def test_BL0228_第二道_從未存過一個都沒選_就算存檔被叫到也一鍵不寫():
    calls = []
    entries = live.mkt5_save_entry([], _AVAILABLE, never_saved=True)
    results = live.run_saves(entries, lambda *a: calls.append(a) or {"status": "saved"})
    assert calls == [] and results == {live.KEY_INDICATORS: logic.TEXT_SAVE_NOTHING_PICKED}


def test_BL0228_第二道_已存過清空再存_照舊寫空陣列_存檔格式不變():
    calls = []
    results = live.run_saves(live.mkt5_save_entry([], _AVAILABLE, never_saved=False),
                             lambda *a: calls.append(a) or {"status": "saved"})
    assert calls == [(live.KEY_INDICATORS, "[]", "list")] and results == {live.KEY_INDICATORS: None}
    calls.clear()
    live.run_saves(live.mkt5_save_entry(["vol_index", "credit_spread_pct"], _AVAILABLE, never_saved=True),
                   lambda *a: calls.append(a) or {"status": "saved"})
    assert calls == [(live.KEY_INDICATORS, '["credit_spread_pct", "vol_index"]', "list")]


def test_BL0228_判定照既有資料_已存的空陣列讀回仍是已存而非從未存過():
    rows = {live.KEY_INDICATORS: {"setting_value": "[]"}}
    settings, error = live.parse_user_settings(rows)
    assert error is None and settings["indicator_keys"] == []
    settings, error = live.parse_user_settings({})
    assert error is None and settings["indicator_keys"] is None


# ───────────────────────── BL-0289：只套天數不印「基準日 None」 ─────────────────────────


def _no_none(model):
    strings = logic.collect_ui_strings(model)
    assert strings
    return [s for s in strings if "None" in s]


def test_BL0289_示範模式只套天數_MKT4標題寫缺比較基準日_整頁沒有None():
    model = logic.build_page_model(fixtures.dataset_all_ok(), window_days=5, baseline_date=None,
                                   field_window_days=5, field_baseline_date=None)
    block = logic.find_block(model, "MKT-4")
    assert block["summary_text"] == logic.TEXT_INCOMPLETE_NO_BASELINE
    assert _no_none(model) == []


def test_BL0289_示範模式只套基準日_MKT4標題寫缺觀察窗_整頁沒有None():
    model = logic.build_page_model(fixtures.dataset_all_ok(), window_days=None, baseline_date="2026-09-21")
    assert logic.find_block(model, "MKT-4")["summary_text"] == logic.TEXT_INCOMPLETE_NO_WINDOW
    assert _no_none(model) == []


def test_BL0289_正式模式欄位只填天數_整頁沒有None():
    model = _model(settings={}, field_window_days=5, field_baseline_date=None)
    assert _no_none(model) == []
    assert logic.TEXT_SAVE_MISSING_BASELINE in logic.find_block(model, "MKT-4")["detail_lines"]
