# -*- coding: utf-8 -*-
"""市場總覽設定（客戶 2026-10-13 裁示：設定存檔、MKT-5、Q-07）的測試（fast lane）。

**走真的 source → logic → page model**：`ui_v2/mkt/source.py::load_live` 與 `save_setting`
經**真的** L2 `services/v2_tables/settings_store`（含存檔前的型別檢查），只把 L1 的兩支
（`repositories.settings_sheet_repository.load_user_settings`／`save_user_setting`）換成記憶體替身，
再交 `ui_v2/mkt/live.build_live_model`（`page.render` 正式路徑呼叫的同一支）組出整頁模型。
市場指標表以 fixtures 的列替身（不打網路）。

需要 `ui_v2.mkt.source` 可匯入（streamlit 等相依）；匯入不到時整檔 skip，與 `test_mkt_source.py` 同。
純 `live`／`logic` 的幾條不需要 source，放在檔尾、不受 skip 影響的寫法另見 `_pure` 前綴。

裁示原意（總管轉達，2026-10-13）：
(二) 儲存成功後，下一次重新整理／重新載入資料時生效；未儲存的暫存設定不得影響正式結果。
MKT-5：三張核心卡固定顯示；勾選只控制下方指標明細；可勾清單只來自資料層；取消勾選 ≠ 資料未備。
Q-07：兩欄完整才能存；半套已存設定 → `⬜ 設定不完整：缺…`，不出任何比較數字、不觸發投資燈號。
"""

from __future__ import annotations

import copy
import pathlib
import re
import sys
import types

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

from ui_v2.mkt import fixtures, live, logic  # noqa: E402

source = pytest.importorskip("ui_v2.mkt.source")  # 需要 L1 的相依（pandas、streamlit 等）

from services.v2_tables import market_indicator as mi  # noqa: E402
from services.v2_tables import settings_store as S  # noqa: E402

_CARDS = ("MKT-1", "MKT-2", "MKT-3")
# 依賴「完整比較條件」才成立的副標（差值、方向、區間、被排除筆數、可用筆數）。
_COMPARISON_MARKERS = ("與觀察窗起點的差", "兩者同向", "兩者分歧", "觀察窗內區間", "排除", "可用筆數",
                       "觀察窗起點早於", "觀察窗內無任何觀測")
_GOOD_WINDOW, _GOOD_BASELINE = 5, "2026-09-21"   # fixtures 的日頻序列為 09-14～09-21


# ───────────────────────── 替身：L1 設定表（記憶體）與市場指標表 ─────────────────────────


class _FakeSheet:
    """`user_setting` 的 L1 記憶體替身：追加一列、讀時同鍵取最後一列（`50` 5.1）。"""

    def __init__(self):
        self.rows = {}
        self.writes = []
        self.fail_keys = set()
        self.read_error = None

    def load(self, *, mask):
        if self.read_error is not None:
            raise self.read_error
        return {"rows": {k: dict(v) for k, v in self.rows.items()}, "bad_rows": [], "broken_keys": [],
                "blank_rows": 0, "tab_missing": not self.rows}

    def save(self, setting_key, setting_value, value_kind, *, mask):
        if setting_key in self.fail_keys:
            raise S.store.SettingsSheetError(f"寫入 {setting_key} 失敗（替身）", code="api")
        row = {"setting_key": setting_key, "setting_value": setting_value, "value_kind": value_kind,
               "updated_at": "2026-10-13T00:00:00Z"}
        self.writes.append(row)
        self.rows[setting_key] = row
        return row

    def put(self, key, value):
        """直接放一列進試算表（模擬歷史遺留、或別頁存的值），不經本頁的存檔。"""
        self.rows[key] = {"setting_key": key, "setting_value": value,
                          "value_kind": live.VALUE_KINDS[key], "updated_at": "2026-10-01T00:00:00Z"}


def _rows_without(*keys):
    return [r for r in fixtures.dataset_all_ok()["rows"] if r["indicator_key"] not in keys]


@pytest.fixture
def sheet(monkeypatch):
    fake = _FakeSheet()
    monkeypatch.setattr(source, "st", types.SimpleNamespace(secrets={}, session_state={}))
    monkeypatch.setattr(S.store, "load_user_settings", fake.load)
    monkeypatch.setattr(S.store, "save_user_setting", fake.save)
    monkeypatch.setattr(source.market_indicator, "source_cooldowns", list)
    fake.table_rows = fixtures.dataset_all_ok()["rows"]

    def build(**_kwargs):
        return {"rows": [dict(r) for r in fake.table_rows], "errors": {}, "pending": {}, "skipped": {}}

    monkeypatch.setattr(source.market_indicator, "build_market_indicator_table", build)
    return fake


def _model(live_input, **fields):
    return live.build_live_model(live_input, save_wired=True, **fields)


def _card_lines(model):
    return {code: list(logic.find_block(model, code)["detail_lines"]) for code in _CARDS}


def _comparison_free(model) -> bool:
    return not any(marker in line for lines in _card_lines(model).values() for line in lines
                   for marker in _COMPARISON_MARKERS)


def _investment_view(model):
    """結論燈與三張核心卡的「燈色／狀態／主值」—— 設定狀態不得動到這些。"""
    light = logic.find_block(model, "MKT-0")
    out = [(light["_tone"], light["text"])]
    for code in _CARDS:
        card = logic.find_block(model, code)
        out.append((code, card["_state"], card["_tone"],
                    [(mv["_state"], mv["_tone"], mv["value_text"]) for mv in card["main_values"]]))
    return out


def _save(button_block, model):
    return next(b for b in logic.find_block(model, button_block)["buttons"] if b["_action_kind"] == "存檔")


# ───────────────────────── 裁示（二）：存檔後下一次重新載入才生效 ─────────────────────────


def test_二_存檔前後正式結果不同_而且要重新載入才變(sheet):
    before_load = source.load_live()
    unset = _model(before_load)
    assert unset["_comparison_state"] == logic.COMPARISON_UNSET
    assert all(lines[0] == "⬜ 不適用：尚未設定觀察窗" for lines in _card_lines(unset).values())

    results = live.run_saves(live.mkt4_save_entries(_GOOD_WINDOW, _GOOD_BASELINE), source.save_setting)
    assert results == {"mkt_window_days": None, "mkt_baseline_date": None}
    assert [w["setting_value"] for w in sheet.writes] == [str(_GOOD_WINDOW), _GOOD_BASELINE]

    # 存檔只更新已存值：手上這一份（存檔前載入的）組出來的正式結果不變
    stale = _model(before_load, field_window_days=_GOOD_WINDOW, field_baseline_date=_GOOD_BASELINE)
    assert _card_lines(stale) == _card_lines(unset)
    # 重新載入（rerun 時 load_live 重新讀 user_setting）才生效
    after = _model(source.load_live())
    assert after["_comparison_state"] == logic.COMPARISON_COMPLETE
    assert _card_lines(after) != _card_lines(unset)
    assert any("與觀察窗起點的差" in line for line in _card_lines(after)["MKT-1"])
    assert any(line in ("兩者同向", "兩者分歧") for line in _card_lines(after)["MKT-2"])
    assert any(line.startswith("觀察窗內區間") for line in _card_lines(after)["MKT-3"])


def test_二_未存的暫存值不影響正式結果(sheet):
    loaded = source.load_live()
    plain = _model(loaded)
    for fields in ({"field_window_days": 7, "field_baseline_date": "2026-09-15"},
                   {"field_window_days": 7, "field_baseline_date": None},
                   {"field_selected_keys": ["vol_index"]}):
        dirty = _model(loaded, **fields)
        for code in ("MKT-0", *_CARDS, "MKT-6", "MKT-7"):
            assert logic.find_block(dirty, code) == logic.find_block(plain, code), (fields, code)
        assert dirty["_display_states"] == plain["_display_states"]
        assert dirty["_comparison_state"] == plain["_comparison_state"]
    assert sheet.writes == []


def test_二_已存設定改了以後_正式結果跟著已存值_而不是欄位值(sheet):
    sheet.put("mkt_window_days", str(_GOOD_WINDOW))
    sheet.put("mkt_baseline_date", _GOOD_BASELINE)
    loaded = source.load_live()
    saved = _model(loaded)
    other_fields = _model(loaded, field_window_days=5, field_baseline_date="2026-08-01")
    assert _card_lines(other_fields) == _card_lines(saved)
    # 欄位值只影響 MKT-4 的欄位與摘要
    assert logic.find_block(other_fields, "MKT-4")["summary_text"] == "5 日曆日，基準日 2026-08-01"


def test_二_正式模式的套用停用並寫原因(sheet):
    model = _model(source.load_live(), field_window_days=30, field_baseline_date=_GOOD_BASELINE)
    applies = [b for b in logic.collect_buttons(model) if b["_action_kind"] == "套用"]
    assert applies and all(not b["_enabled"] and b["_visible"] for b in applies)
    assert {b["disabled_reason"] for b in applies} == {live.APPLY_DISABLED_REASON}
    assert _save("MKT-4", model)["_enabled"] is True


def test_二_存檔寫入失敗_欄位下方顯示原文_正式結果不變(sheet):
    sheet.fail_keys = {"mkt_baseline_date"}
    loaded = source.load_live()
    results = live.run_saves(live.mkt4_save_entries(_GOOD_WINDOW, _GOOD_BASELINE), source.save_setting)
    assert results["mkt_window_days"] is None and "寫入 mkt_baseline_date 失敗" in results["mkt_baseline_date"]
    model = _model(loaded, save_results=results)
    lines = logic.find_block(model, "MKT-4")["detail_lines"]
    assert any(line.startswith(live.TEXT_SAVE_FAILED + "mkt_baseline_date") for line in lines)
    assert live.TEXT_SAVED not in lines
    # 後一鍵失敗、前一鍵已落地 → 試算表上是半套；讀回時照 Q-07 判「設定不完整」，不出比較數字
    reread = _model(source.load_live())
    assert reread["_comparison_state"] == logic.COMPARISON_INCOMPLETE
    assert _comparison_free(reread)


def test_二_前一鍵寫入失敗就不寫後一鍵(sheet):
    sheet.fail_keys = {"mkt_window_days"}
    results = live.run_saves(live.mkt4_save_entries(_GOOD_WINDOW, _GOOD_BASELINE), source.save_setting)
    assert results["mkt_baseline_date"] == "前一個鍵存檔失敗，本鍵未寫入"
    assert sheet.writes == []


# ───────────────────────── Q-07：兩欄完整才能存 ─────────────────────────


@pytest.mark.parametrize("window, baseline, missing", [
    (30, None, "缺少：比較基準日"),
    (None, "2026-09-30", "缺少：觀察窗天數"),
])
def test_Q07_只填一欄_禁止存檔_存檔區寫明缺哪一欄(sheet, window, baseline, missing):
    model = _model(source.load_live(), field_window_days=window, field_baseline_date=baseline)
    block = logic.find_block(model, "MKT-4")
    save = _save("MKT-4", model)
    assert save["_enabled"] is False and save["disabled_reason"] == missing
    assert missing in block["detail_lines"]
    assert "None" not in block["summary_text"]          # 修正「基準日 None」
    # 第二道：就算存檔函式被叫到，也一鍵都不寫
    calls = []
    results = live.run_saves(live.mkt4_save_entries(window, baseline),
                             lambda *a: calls.append(a) or {"status": "saved"})
    assert calls == [] and set(results.values()) == {missing}
    assert sheet.writes == []


def test_Q07_兩欄都完整才可存(sheet):
    model = _model(source.load_live(), field_window_days=30, field_baseline_date=_GOOD_BASELINE)
    assert _save("MKT-4", model)["_enabled"] is True
    assert logic.find_block(model, "MKT-4")["summary_text"] == f"30 日曆日，基準日 {_GOOD_BASELINE}"


@pytest.mark.parametrize("stored, text", [
    ({"mkt_window_days": "30"}, "⬜ 設定不完整：缺比較基準日"),
    ({"mkt_baseline_date": "2026-09-30"}, "⬜ 設定不完整：缺觀察窗"),
])
def test_Q07_讀到半套已存設定_三張核心卡寫設定不完整_不出任何比較數字(sheet, stored, text):
    unset_view = _investment_view(_model(source.load_live()))
    for key, value in stored.items():
        sheet.put(key, value)
    model = _model(source.load_live())
    assert model["_comparison_state"] == logic.DISPLAY_INCOMPLETE_SETTING
    for code, lines in _card_lines(model).items():
        assert lines == [text], code
    assert _comparison_free(model)
    # 不是投資風險訊號：結論燈、卡片燈色、主值狀態與「未設定」時逐格相同
    assert _investment_view(model) == unset_view


def test_Q07_只有基準日時_景氣位置卡不再照算方向(sheet):
    """舊 `_mkt2_direction_lines` 只看基準日，半套照出「兩者同向／分歧」—— 本輪修掉的那一處。"""
    sheet.put("mkt_baseline_date", "2026-09-30")
    lines = _card_lines(_model(source.load_live()))["MKT-2"]
    assert not any(line in ("兩者同向", "兩者分歧") for line in lines)
    assert not any("排除" in line for line in lines)


def test_Q07_設定不完整不是風險語彙_全頁無禁詞與燈號字樣(sheet):
    sheet.put("mkt_window_days", "30")
    model = _model(source.load_live())
    strings = logic.collect_ui_strings(model)
    assert logic.scan_forbidden(strings) == {}
    for line in (x for lines in _card_lines(model).values() for x in lines):
        for word in ("風險", "警示", "紅燈", "黃燈", "取數失敗"):
            assert word not in line


# ───────────────────────── MKT-5：勾選只過濾下方明細 ─────────────────────────


def test_MKT5_勾選只影響下方明細_不影響三張核心卡(sheet):
    base = _model(source.load_live())
    sheet.put("mkt_indicator_keys", '["vol_index"]')
    model = _model(source.load_live())
    for code in ("MKT-0", *_CARDS):
        assert logic.find_block(model, code) == logic.find_block(base, code), code
    assert {r["indicator_key"] for r in logic.find_block(model, "MKT-6")["_rows"]} == {"vol_index"}
    assert [r["indicator_key"] for r in logic.find_block(model, "MKT-7")["_rows"]] == ["vol_index"]


def test_MKT5_一個都沒勾_明細區寫尚未選定任何指標_核心卡照常(sheet):
    base = _model(source.load_live())
    sheet.put("mkt_indicator_keys", "[]")
    model = _model(source.load_live())
    for code in ("MKT-0", *_CARDS):
        assert logic.find_block(model, code) == logic.find_block(base, code), code
    for code in ("MKT-6", "MKT-7"):
        block = logic.find_block(model, code)
        assert block["_rows"] == [] and logic.TEXT_NOTHING_SELECTED in block["detail_lines"]
        assert not any("資料未備" in line for line in block["detail_lines"])
    assert logic.find_block(model, "MKT-5")["summary_text"] == logic.TEXT_NOTHING_SELECTED


def test_MKT5_取消勾選與資料未備可區分(sheet):
    sheet.table_rows = _rows_without("leading_index")           # leading_index 資料未備
    sheet.put("mkt_indicator_keys", '["leading_index", "vol_index"]')   # credit_spread_pct 等被取消勾選
    model = _model(source.load_live())
    states = model["_display_states"]
    assert states["leading_index"] == logic.DISPLAY_NOT_READY
    assert states["vol_index"] == logic.DISPLAY_VALUE
    assert states["credit_spread_pct"] == logic.DISPLAY_USER_HIDDEN
    assert set(states.values()) <= set(logic.DISPLAY_STATES)
    mkt7 = {r["indicator_key"]: r for r in logic.find_block(model, "MKT-7")["_rows"]}
    assert [b["text"] for b in mkt7["leading_index"]["badges"]] == ["資料未備"]     # 資料未備：照列＋徽章
    assert "credit_spread_pct" not in mkt7                                       # 使用者選擇不顯示：不列
    hidden_lines = [line for line in logic.find_block(model, "MKT-7")["detail_lines"]
                    if line.startswith(logic.TEXT_USER_HIDDEN_PREFIX)]
    assert len(hidden_lines) == 1 and "credit_spread_pct" in hidden_lines[0]
    assert "leading_index" not in hidden_lines[0] and "資料未備" not in hidden_lines[0]
    items = {i["name"]: i for i in logic.find_block(model, "MKT-5")["_items"]}
    assert items["credit_spread_pct"]["_display_state"] == logic.DISPLAY_USER_HIDDEN
    assert items["credit_spread_pct"]["badges"] == []                          # 有資料，只是不顯示
    assert items["leading_index"]["_display_state"] == logic.DISPLAY_NOT_READY


def test_MKT5_可勾清單只來自資料層_不含假鍵(sheet):
    model = _model(source.load_live())
    names = [i["name"] for i in logic.find_block(model, "MKT-5")["_items"]]
    assert names == sorted(mi.INDICATOR_SPECS)                     # 七鍵，含 term_spread_pct
    assert "term_spread_pct" in names and len(names) == 7
    # 資料層沒有任何一筆的註冊鍵：仍列出，掛資料未備（44 MKT-5 空狀態第二句）
    sheet.table_rows = _rows_without("term_spread_pct")
    items = {i["name"]: i for i in logic.find_block(_model(source.load_live()), "MKT-5")["_items"]}
    assert [b["text"] for b in items["term_spread_pct"]["badges"]] == ["資料未備"]
    # 已存清單裡的假鍵：不成為選項、不顯示，MKT-5 寫一行點名
    sheet.put("mkt_indicator_keys", '["vol_index", "not_a_real_key"]')
    model = _model(source.load_live())
    block = logic.find_block(model, "MKT-5")
    assert "not_a_real_key" not in [i["name"] for i in block["_items"]]
    assert any("not_a_real_key" in line for line in block["detail_lines"])
    assert "not_a_real_key" not in model["_display_states"]


def test_MKT5_上限6_七鍵時第七項停用_存檔照判定(sheet):
    loaded = source.load_live()
    six = sorted(mi.INDICATOR_SPECS)[:6]
    model = _model(loaded, field_selected_keys=six)
    items = {i["name"]: i for i in logic.find_block(model, "MKT-5")["_items"]}
    seventh = sorted(mi.INDICATOR_SPECS)[6]
    assert items[seventh]["_enabled"] is False and items[seventh]["disabled_reason"]
    assert _save("MKT-5", model)["_enabled"] is True
    over = _model(loaded, field_selected_keys=sorted(mi.INDICATOR_SPECS))
    assert _save("MKT-5", over)["_enabled"] is False
    assert live.mkt5_save_entry(sorted(mi.INDICATOR_SPECS), sorted(mi.INDICATOR_SPECS))[0]["error"]


def test_MKT5_存檔寫進mkt_indicator_keys_重新載入後才過濾(sheet):
    loaded = source.load_live()
    keys = logic.selectable_keys(loaded["dataset"], loaded["notes"]["available_keys"])
    results = live.run_saves(live.mkt5_save_entry(["vol_index", "fx_twd_per_usd"], keys), source.save_setting)
    assert results == {"mkt_indicator_keys": None}
    assert sheet.writes[-1]["setting_value"] == '["fx_twd_per_usd", "vol_index"]'
    assert sheet.writes[-1]["value_kind"] == "list"
    stale = _model(loaded, field_selected_keys=["vol_index", "fx_twd_per_usd"])
    assert len(logic.find_block(stale, "MKT-7")["_rows"]) == 7                 # 未重新載入：照舊全列
    fresh = _model(source.load_live())
    assert [r["indicator_key"] for r in logic.find_block(fresh, "MKT-7")["_rows"]] == \
        ["fx_twd_per_usd", "vol_index"]


def test_MKT5_取消勾選不觸發投資燈號(sheet):
    base = _investment_view(_model(source.load_live()))
    sheet.put("mkt_indicator_keys", '["policy_rate_pct"]')
    assert _investment_view(_model(source.load_live())) == base


# ───────────────────────── 讀不到／解析不了 ─────────────────────────


def test_設定讀不到_不說未設定_不出比較數字_存檔停用(sheet):
    sheet.read_error = S.store.SettingsSheetError("設定試算表讀取失敗（替身）", code="api")
    loaded = source.load_live()
    assert loaded["notes"]["settings_error"] == "設定試算表讀取失敗（替身）"
    model = _model(loaded, field_window_days=30, field_baseline_date=_GOOD_BASELINE)
    assert model["_comparison_state"] == logic.COMPARISON_READ_FAILED
    for lines in _card_lines(model).values():
        assert lines == ["⬜ 不適用：比較條件讀不到"]
    assert _save("MKT-4", model)["_enabled"] is False
    assert _save("MKT-5", model)["_enabled"] is False
    assert any("設定試算表讀取失敗" in line for line in logic.find_block(model, "MKT-4")["detail_lines"])


@pytest.mark.parametrize("key, value", [
    ("mkt_window_days", "-5"), ("mkt_window_days", "3.5"), ("mkt_baseline_date", "2026/09/30"),
    ("mkt_indicator_keys", "vol_index"), ("mkt_indicator_keys", '["a", "a"]'),
    ("mkt_indicator_keys", '["a","b","c","d","e","f","g"]'),
])
def test_已存值形狀不對_當成讀取失敗_不當成未設定(sheet, key, value):
    sheet.put(key, value)
    loaded = source.load_live()
    assert loaded["notes"]["settings_error"] and key in loaded["notes"]["settings_error"]
    assert loaded["notes"]["settings"] == {"window_days": None, "baseline_date": None, "indicator_keys": None}


def test_L2型別檢查擋得下_value_kind與set頁一致(sheet):
    from ui_v2.set import spec

    kinds = dict(spec.SPEC_SETTING_KEYS)
    assert {k: kinds[k] for k in live.SETTING_KEYS} == live.VALUE_KINDS
    out = source.save_setting("mkt_window_days", "三十", "int")
    assert out["status"] == "kind_mismatch" and sheet.writes == []


def test_mkt已列入讀設定的頁():
    assert "mkt" in S.PAGES_READING_SETTINGS


def test_不改呼叫端手上的載入結果(sheet):
    sheet.put("mkt_indicator_keys", '["vol_index"]')
    loaded = source.load_live()
    snapshot = copy.deepcopy(loaded)
    _model(loaded, field_selected_keys=["fx_twd_per_usd"], save_results={"mkt_indicator_keys": None})
    assert loaded == snapshot


def test_模型字串沒有None字樣(sheet):
    sheet.put("mkt_window_days", "30")
    model = _model(source.load_live(), field_window_days=30, field_baseline_date=None)
    assert not [s for s in logic.collect_ui_strings(model) if re.search(r"\bNone\b", s)]
