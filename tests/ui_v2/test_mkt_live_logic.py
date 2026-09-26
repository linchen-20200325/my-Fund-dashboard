# -*- coding: utf-8 -*-
"""ui_v2/mkt/live.py：正式模式畫面調整的純函式測試（fast lane；不需要 streamlit）。

對照客戶 2026-09-26 核准的文字線框草稿第 2~6 處。示範模式不經過 live.py，
其不變由既有 `test_mkt_logic.py`／`test_mkt_page.py` 全數照舊通過來證明。
"""

from __future__ import annotations

import copy
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from ui_v2.mkt import fixtures, live, logic  # noqa: E402

_ALL_PENDING = {
    "fx_twd_per_usd": "fx_obs_date_rule",
    "credit_spread_pct": "fred_release_date",
    "term_spread_pct": "fred_release_date",
    "policy_rate_pct": "fred_release_date",
    "leading_index": "ndc_no_release_date",
    "coincident_index": "ndc_no_release_date",
}


def _phase1_dataset(errors=None):
    """第一階段的形狀：只有 vol_index 有列。"""
    rows = [r for r in fixtures.dataset_all_ok()["rows"] if r["indicator_key"] == "vol_index"]
    return {"rows": rows, "errors": dict(errors or {})}


def _notes(**kw):
    base = {"pending": dict(_ALL_PENDING), "masked_keys": [], "cooldowns": []}
    base.update(kw)
    return base


def _mv(model, code, key):
    return [m for m in logic.find_block(model, code)["main_values"] if m["_source_key"] == key][0]


def test_草稿3_資料未備的值下一行寫原因_文案逐字():
    model = live.apply_live_notes(logic.build_page_model(_phase1_dataset()), _notes())
    assert _mv(model, "MKT-1", "credit_spread_pct")["note_lines"] == ["原因：公布日尚未接上，暫不寫入"]
    assert _mv(model, "MKT-2", "leading_index")["note_lines"] == ["原因：來源不提供公布日"]
    assert _mv(model, "MKT-3", "fx_twd_per_usd")["note_lines"] == ["原因：觀測日切日規則待以真實資料驗證"]
    assert _mv(model, "MKT-3", "policy_rate_pct")["note_lines"] == ["原因：公布日尚未接上，暫不寫入"]
    assert "note_lines" not in _mv(model, "MKT-1", "vol_index")  # 有值的不加
    mkt7 = logic.find_block(model, "MKT-7")
    assert "leading_index　原因：來源不提供公布日" in mkt7["detail_lines"]
    assert not any(line.startswith("vol_index") for line in mkt7["detail_lines"])


def test_模板那一行逐字不動():
    base = logic.build_page_model(_phase1_dataset())
    model = live.apply_live_notes(base, _notes())
    for code in ("MKT-1", "MKT-2", "MKT-3"):
        for before, after in zip(logic.find_block(base, code)["main_values"],
                                 logic.find_block(model, code)["main_values"]):
            assert before["value_text"] == after["value_text"]


def test_草稿2_含遮蔽記號才加註_已遮蔽憑證():
    ds = _phase1_dataset({"vol_index": "x ‹已遮蔽› y"})
    model = live.apply_live_notes(logic.build_page_model(ds), _notes(masked_keys=["vol_index"]))
    mv = _mv(model, "MKT-1", "vol_index")
    assert mv["value_text"] == "⛔ 取數失敗：x ‹已遮蔽› y"   # 訊息本身不帶註記
    assert mv["note_lines"] == ["已遮蔽憑證"]
    ds = _phase1_dataset({"vol_index": "沒有秘密"})
    model = live.apply_live_notes(logic.build_page_model(ds), _notes())
    assert "note_lines" not in _mv(model, "MKT-1", "vol_index")


def test_草稿4_存檔停用並寫原因():
    model = live.apply_live_notes(
        logic.build_page_model(_phase1_dataset(), window_days=30, baseline_date="2026-09-20"),
        _notes())
    save = [b for b in logic.find_block(model, "MKT-4")["buttons"] if b["_action_kind"] == "存檔"]
    assert len(save) == 1
    assert save[0]["_enabled"] is False and save[0]["_visible"] is True
    assert save[0]["disabled_reason"] == "設定存檔尚未接上，存了也留不到下次開頁"
    apply = [b for b in logic.find_block(model, "MKT-4")["buttons"] if b["_action_kind"] == "套用"]
    assert apply[0]["_enabled"] is True  # 套用不受影響


def test_草稿5_重新取數停用_無後端與冷卻中兩種原因():
    empty = {"rows": [], "errors": {}}
    model = live.apply_live_notes(logic.build_page_model(empty), _notes())
    retry = [b for b in logic.collect_buttons(model) if b["_action_kind"] == "取數"]
    assert retry, "空狀態應有重新取數鈕（空掃防呆）"
    assert all(b["_enabled"] is False and b["disabled_reason"] == "重新取數尚未接上" for b in retry)
    cool = [{"source": "query1.finance.yahoo.com", "remaining_sec": 44.2},
            {"source": "b.example.test", "remaining_sec": 10.0},
            {"source": "c.example.test", "remaining_sec": 3.0}]
    model = live.apply_live_notes(logic.build_page_model(empty), _notes(cooldowns=cool))
    reasons = {b["disabled_reason"] for b in logic.collect_buttons(model) if b["_action_kind"] == "取數"}
    assert reasons == {"來源冷卻中：query1.finance.yahoo.com，約剩 45 秒，另有 2 個來源冷卻中"}
    assert live.cooldown_reason(cool[:1]) == "來源冷卻中：query1.finance.yahoo.com，約剩 45 秒"
    assert live.cooldown_reason([{"source": "x", "remaining_sec": 0}]) is None


def test_草稿6_不新增舊資料字樣_且零禁詞():
    model = live.apply_live_notes(logic.build_page_model(_phase1_dataset()),
                                  _notes(cooldowns=[{"source": "h", "remaining_sec": 5}]))
    strings = logic.collect_ui_strings(model)
    assert not any("舊資料" in s for s in strings)
    assert logic.scan_forbidden(strings) == {}
    for button in logic.collect_buttons(model):
        for word in logic.FORBIDDEN_BUTTON_WORDS:
            assert word not in button["label"] and word not in button["disabled_reason"]


def test_不改呼叫端手上的模型_未知原因代碼當場炸():
    base = logic.build_page_model(_phase1_dataset())
    snapshot = copy.deepcopy(base)
    live.apply_live_notes(base, _notes())
    assert base == snapshot
    try:
        live.apply_live_notes(base, _notes(pending={"leading_index": "沒有核准文案"}))
    except KeyError:
        pass
    else:
        raise AssertionError("未知原因代碼應當場 KeyError")


def test_原因代碼與L2一致():
    """L2 的 PENDING_* 常數與本檔 REASON_TEXT 的鍵一致（L2 不在時略過這一條）。"""
    import pytest

    mi = pytest.importorskip("services.v2_tables.market_indicator")
    codes = {mi.PENDING_FRED_RELEASE_DATE, mi.PENDING_NDC_NO_RELEASE_DATE, mi.PENDING_FX_OBS_DATE_RULE}
    assert codes == set(live.REASON_TEXT)
    assert {spec["pending_code"] for spec in mi.INDICATOR_SPECS.values()} - {None} == codes
