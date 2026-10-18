# -*- coding: utf-8 -*-
"""設定與診斷頁正式模式重排的純函式（Phase 3 P1-⑥；`ui_v2/sections.py` 的 `set_*`）。

依據 `docs/v2/44_fund_ui_ssot.md` 第七節第三小節之八其二 (b-1)～(b-4)、其三 (c-1)（`DEC-2026-10-17-07`）。
不需要 streamlit（fast lane）。畫面層見 `tests/ui_v2/test_set_reshape_page.py`。
"""

from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import re

import pytest

from ui_v2 import sections
from ui_v2.set import fixtures as set_fixtures
from ui_v2.set import live as set_live
from ui_v2.set import logic as set_logic

_D44 = pathlib.Path(__file__).resolve().parents[2] / "docs" / "v2" / "44_fund_ui_ssot.md"
_ALL = [(n, sf) for n in set_fixtures.ALL_SCENARIO_NAMES for sf in (False, True)]


def _model(name="ok", save_failed=False):
    return set_logic.build_page_model(set_fixtures.scenario_with(name, save_failed=save_failed))


def _reshaped(name="ok", *, sheet_configured=True, save_failed=False):
    model = _model(name, save_failed)
    sections.set_reshape(model, sheet_configured=sheet_configured)
    return model


def _b(model, code):
    return set_logic.find_block(model, code)


# ───────────────────────── 鏡像常數、44 字面 ─────────────────────────


def test_鏡像常數逐字等於真身():
    assert sections.SET_TEXT_OUT == set_logic.TEXT_OUT
    assert sections.SET_EMPTY_GLYPH == set_logic.EMPTY_GLYPH
    light = _b(_model("stale"), "SET-0")
    assert light["_state"] == sections.SET_STATE_OVERDUE and light["_tone"] == "黃"
    empty = _b(_model("nolimit"), "SET-0")
    assert empty["_state"] == sections.SET_STATE_EMPTY and empty["state_word"] == sections.SET_STATE_WORD_EMPTY
    assert empty["glyph"] == sections.SET_EMPTY_GLYPH
    unset_row = [r for r in _b(_model("first"), "SET-3")["_rows"] if r["value_text"] == set_logic.TEXT_UNSET]
    assert unset_row and set_logic.TEXT_UNSET == f"{sections.SET_EMPTY_GLYPH} 未設定"
    assert set_logic.TEXT_NA_BAD_KIND == f"{sections.SET_EMPTY_GLYPH} 不適用：值與型別不符"


def test_兩句新文案都在44現行文字裡_不在刪除線內():
    live44 = re.sub(r"~~.*?~~", "", _D44.read_text(encoding="utf-8"), flags=re.DOTALL)
    assert sections.SET_OVERDUE_TEXT.replace("{n}", "N") in live44
    assert sections.SET_NO_SHEET_TEXT in live44


def test_SET0舊黃燈句_正式模式劃線_示範模式照舊在現行文字裡():
    text = _D44.read_text(encoding="utf-8")
    assert "~~「有 N 筆資料超過你設定的新鮮度上限」~~" in text
    live44 = re.sub(r"~~.*?~~", "", text, flags=re.DOTALL)
    assert "示範模式照舊「有 N 筆資料超過你設定的新鮮度上限」" in live44


# ───────────────────────── ④ 搬卡 ─────────────────────────


def test_SET2到層4_SET3到層3_預設收合_層2只留SET1():
    model = _reshaped()
    assert set_logic.codes_in_layer(model, 1) == ["SET-0"]
    assert set_logic.codes_in_layer(model, 2) == ["SET-1"]
    assert set_logic.codes_in_layer(model, 3) == ["SET-3", "SET-4", "SET-5"]
    assert set_logic.codes_in_layer(model, 4) == ["SET-2", "SET-6", "SET-7"]
    assert [b["code"] for b in model["blocks"] if b["_default_open"]] == ["SET-0", "SET-1"]
    assert all(len(set_logic.codes_in_layer(model, layer)) <= 3 for layer in (2, 3, 4))   # 44 第二節每層上限三


# ───────────────────────── ① SET-0 ─────────────────────────


def test_黃燈改寫成類數句_N照SET1的逾期數_燈色與警告號照舊():
    model = _reshaped("stale")
    light = _b(model, "SET-0")
    overdue = _b(model, "SET-1")["_overdue"]
    assert overdue > 0
    assert light["text"] == f"◷ {overdue} 類資料超過你設的上限"
    assert light["_tone"] == "黃" and light["glyph"] == set_logic.WARN_GLYPH   # 之七其四第 5 條：黃燈 ⚠ 不改
    assert "其餘正常" not in light["text"] and "筆資料" not in light["text"]


def test_上限設0日_N等於3():
    assert _b(_reshaped("zero"), "SET-0")["text"] == "◷ 3 類資料超過你設的上限"


@pytest.mark.parametrize("name, sf", _ALL)
def test_非黃燈的燈一字不動(name, sf):
    before = _b(_model(name, sf), "SET-0")
    after = _b(_reshaped(name, save_failed=sf), "SET-0")
    if before["_state"] == sections.SET_STATE_OVERDUE:
        assert after["text"] != before["text"]
        assert {k: v for k, v in after.items() if k != "text"} == {k: v for k, v in before.items() if k != "text"}
    else:
        assert after == before


def test_BL0371_兩個計數皆為零_燈上不寫文案_只留狀態字_示範與正式皆同():
    """客戶 2026-10-18 裁示 BL-0371（`DEC-2026-10-18-01`）：移除「資料齊、來源皆可達」，不限正式模式（logic 本身不寫）。
    （舊測試 `test_資料齊那一句照舊不改` 在寫下當時為真 —— BL-0371 那時待客戶另裁；被推翻的是它的前提。）"""
    for light in (_b(_model("ok"), "SET-0"), _b(_reshaped("ok"), "SET-0")):
        assert light["_state"] == "齊" and light["text"] == ""
        assert light["state_word"] == "狀態：無逾期、無失敗來源" and light["_tone"] == "灰"


@pytest.mark.parametrize("name, sf", _ALL)
def test_BL0371_全情境SET0燈不寫資料齊或來源皆可達_示範與正式皆同(name, sf):
    for light in (_b(_model(name, sf), "SET-0"), _b(_reshaped(name, save_failed=sf), "SET-0")):
        text = json.dumps(light, ensure_ascii=False)
        assert "資料齊" not in text and "來源皆可達" not in text, (name, light["text"])


@pytest.mark.parametrize("name", ["ok", "stale", "failed", "logfail", "nolimit", "first", "settingfail"])
def test_設定試算表未設定_燈灰_第三句優先(name):
    light = _b(_reshaped(name, sheet_configured=False), "SET-0")
    assert light["_tone"] == "灰"
    assert light["text"] == "⬜ 無法判定：尚未設定設定試算表"
    assert light["glyph"] == set_logic.EMPTY_GLYPH and light["state_word"] == "狀態：尚不足以判定"
    assert light["note_lines"] == []
    assert "請" not in light["text"] and "暫停" not in light["text"]   # 只寫狀態，不寫操作指引


@pytest.mark.parametrize("name", ["ok", "stale", "failed", "logfail", "nolimit", "first", "settingfail"])
def test_S1C1_設定試算表與服務帳戶皆未設定_燈維持紅_不出第三句(name):
    """客戶 2026-10-18 裁示 C1（`DEC-2026-10-18-01`）：缺服務帳戶維持 ⛔，不改成第三句；兩者同時未設定時取保守 ⛔
    （總管指定讀法）。燈由 `live.apply_live_notes` 畫好（見 `test_set_live_logic.py`），本函式不動它。"""
    model = _model(name)
    light = _b(model, "SET-0")
    light.update(_tone="紅", _state="讀取失敗", glyph="⛔", state_word="狀態：取數失敗", text="⛔ 取數失敗：未設定服務帳戶")
    before = copy.deepcopy(light)
    sections.set_reshape(model, sheet_configured=False, service_account_configured=False)
    assert _b(model, "SET-0") == before
    assert sections.SET_NO_SHEET_TEXT not in json.dumps(_b(model, "SET-0"), ensure_ascii=False)


def test_S1C1_兩者皆未設定而燈不是紅_當場炸():
    with pytest.raises(ValueError):
        sections.set_reshape(_model("ok"), sheet_configured=False, service_account_configured=False)


def test_服務帳戶有沒有設定_閘門不是not_configured時不讀_是時缺鍵就炸():
    for state in ("ok", "cooling", "no_service_account"):
        assert set_live.service_account_configured({"gate": {"state": state}}) is True
    gate = {"state": "not_configured"}
    assert set_live.service_account_configured({"gate": gate, "service_account": {"configured": True}}) is True
    assert set_live.service_account_configured({"gate": gate, "service_account": {"configured": False}}) is False
    with pytest.raises(KeyError):
        set_live.service_account_configured({"gate": gate})


def test_設定試算表有沒有設定_只看寫入閘門的not_configured():
    for state in ("ok", "cooling", "no_service_account"):
        assert set_live.sheet_configured({"gate": {"state": state}}) is True
    assert set_live.sheet_configured({"gate": {"state": "not_configured"}}) is False
    with pytest.raises(KeyError):
        set_live.sheet_configured({})


def test_黃燈但逾期數為零_當場炸():
    model = _model("stale")
    _b(model, "SET-1")["_overdue"] = 0
    with pytest.raises(ValueError):
        sections.set_conclusion(model, sheet_configured=True)


# ───────────────────────── ② SET-1 ─────────────────────────


def test_SET1外加時鐘_內與不適用不動():
    assert [r["compare_text"] for r in _b(_reshaped("zero"), "SET-1")["_rows"]] == ["◷ 外"] * 3
    compares = [r["compare_text"] for r in _b(_reshaped("ok"), "SET-1")["_rows"]]
    assert compares and all(c == set_logic.TEXT_IN for c in compares)
    assert {r["compare_text"] for r in _b(_reshaped("nolimit"), "SET-1")["_rows"]} <= {set_logic.TEXT_NA_NO_LIMIT, "⬜"}
    assert len(_b(_reshaped("ok"), "SET-1")["_rows"]) == 3   # 照舊三列，「其他」不上（BL-0370）


@pytest.mark.parametrize("name, sf", _ALL)
def test_全情境不出現勾與一切正常字樣(name, sf):
    text = "\n".join(set_logic.collect_ui_strings(_reshaped(name, save_failed=sf)))
    for word in ("✓", "其餘正常", "沒有例外"):
        assert word not in text, word


def test_重排冪等_時鐘不重複加():
    model = _reshaped("zero")
    sections.mark_set1_rows(model)
    assert [r["compare_text"] for r in _b(model, "SET-1")["_rows"]] == ["◷ 外"] * 3


# ───────────────────────── ③ 需要注意 ─────────────────────────


def test_需要注意列SET1的外那幾列_沒有就不列():
    model = _reshaped("stale")
    rows = [r for r in _b(model, "SET-1")["_rows"] if r["compare_text"] == "◷ 外"]
    items = sections.attention_items(model, "set")
    assert len(items) == len(rows) == _b(model, "SET-1")["_overdue"] > 0
    for item, row in zip(items, rows):
        assert item == {"symbol": "◷", "text": f"{row['_kind_label']}：距今 {row['_days']} 日，超過你設的上限",
                        "_tone": "黃"}
    for name in ("ok", "nolimit", "first", "settingfail"):   # failed 情境同時有逾期，見 test_set_logic
        assert sections.attention_items(_reshaped(name), "set") == [], name


def test_需要注意不靠時鐘那一步():
    """③ 只讀 SET-1 的比較結果；沒先加 ◷ 也讀得到「外」。"""
    assert len(sections.set_attention(_model("zero"))) == 3


# ───────────────────────── 護欄：判定、按鈕、寫入不動 ─────────────────────────


@pytest.mark.parametrize("name, sf", _ALL)
def test_重排不碰判定_不新增按鈕(name, sf):
    before = _model(name, sf)
    after = copy.deepcopy(before)
    sections.set_reshape(after, sheet_configured=True)
    for code in ("SET-1", "SET-2", "SET-3", "SET-4", "SET-5", "SET-6", "SET-7"):
        b, a = _b(before, code), _b(after, code)
        assert set(a) == set(b), code
        for key in b:
            if key in ("_layer", "_default_open", "_rows"):
                continue
            assert a[key] == b[key], (code, key)
    for rb, ra in zip(_b(before, "SET-1")["_rows"], _b(after, "SET-1")["_rows"]):
        assert {k: v for k, v in ra.items() if k != "compare_text"} == {k: v for k, v in rb.items() if k != "compare_text"}
    assert [b["buttons"] for b in before["blocks"]] == [b["buttons"] for b in after["blocks"]]
    assert set_logic.collect_buttons(before) == set_logic.collect_buttons(after)


# ───────────────────────── ④ 收合摘要 ─────────────────────────


def test_SET2摘要_失敗與未備看得見():
    failed = _b(_model("failed"), "SET-2")
    summary = sections.set2_summary(failed)
    assert failed["_failed_tiers"] and "⛔ 最近一次取數失敗：" + "、".join(failed["_failed_tiers"]) in summary
    notier = _b(_model("notier"), "SET-2")
    missing = [r["tier_text"] for r in notier["_rows"] if r["result_text"] == "⬜"]
    assert missing and ("◇ 資料未備：" + "、".join(missing)) in sections.set2_summary(notier)
    first = _b(_model("first"), "SET-2")
    assert first["placeholder"] and set_logic.TEXT_NO_RECORDS in sections.set2_summary(first)
    assert sections.set2_summary(_b(_model("logfail"), "SET-2")).startswith("⛔ 取數失敗：")


@pytest.mark.parametrize("name, sf", _ALL)
def test_SET2與SET3摘要不寫正常_不為空(name, sf):
    model = _model(name, sf)
    for summary in (sections.set2_summary(_b(model, "SET-2")), sections.set3_summary(_b(model, "SET-3"))):
        assert summary and "正常" not in summary and "✓" not in summary


def test_SET3摘要_未設定與型別不符的鍵名寫出來():
    first = _b(_model("first"), "SET-3")
    unset = [r["key_text"] for r in first["_rows"] if r["value_text"] == set_logic.TEXT_UNSET]
    assert unset and f"{len(unset)} 個未設定：" + "、".join(unset) in sections.set3_summary(first)
    bad = _b(_model("badkind"), "SET-3")
    wrong = [r["key_text"] for r in bad["_rows"] if r["value_text"] == set_logic.TEXT_NA_BAD_KIND]
    assert wrong and f"{len(wrong)} 個值與型別不符：" + "、".join(wrong) in sections.set3_summary(bad)
    assert sections.set3_summary(_b(_model("settingfail"), "SET-3")).startswith("⛔ 取數失敗：")
    ok = _b(_model("ok"), "SET-3")
    assert sections.set3_summary(ok).startswith(f"{len(ok['_rows'])} 個鍵")


# ───────────────────────── 示範模式 ─────────────────────────


def test_示範模型逐位元組不變():
    """示範模式不經過重排（44 之八開頭第 4 條）：logic 交出的示範模型序列化後的 md5 與 P1-⑥ 動工前相同。
    基準值於 c44e1551（P1-④ 稽核通過版）量得：17 情境 × 存檔失敗開關，共 34 個模型。"""
    models = {f"{n}|{sf}": _model(n, sf) for n, sf in _ALL}
    assert len(models) == 34
    # 客戶 2026-10-18 裁示 BL-0371（`DEC-2026-10-18-01`）：示範模式同樣不寫「資料齊、來源皆可達」。
    # 證明「示範模型只差這一句」：把 `SET-0` 齊那一支的文案還原成舊字面，md5 必須回到舊基準值；其餘一格不動。
    restored = copy.deepcopy(models)
    changed = 0
    for model in restored.values():
        light = _b(model, "SET-0")
        if light["_state"] == "齊":
            assert light["text"] == ""
            light["text"] = "資料齊、來源皆可達"
            changed += 1
    assert changed > 0
    blob = json.dumps(restored, ensure_ascii=False, sort_keys=True, default=repr).encode()
    assert hashlib.md5(blob).hexdigest() == "e5f44896d645c8b04e342ac1dd720ce0"   # 舊基準值（c44e1551）


# ───────────────────────── 2026-10-18 獨立稽核回修（M1、S2、S6） ─────────────────────────


def test_壞列字面與來源缺字面逐字等於真身():
    assert sections.SET_BAD_ROW_TEXT == set_live.TEXT_BAD_ROWS.format(n=1)
    assert sections.SET_LOG_TABLE in set_logic.FETCHABLE_TABLES
    assert set_logic._placeholder(set_logic.TEXT_NO_RECORDS, "來源缺")["_empty_kind"] == sections.SET_EMPTY_KIND_NO_SOURCE


def test_SET3摘要_沒有列而卡頭有紅字_寫紅字不寫0個鍵():
    block = {"placeholder": None, "_rows": [],
             "head_lines": [{"text": "⛔ 未設定試算表 ID，暫停寫入", "_tone": "紅"}], "live_lines": []}
    assert sections.set3_summary(block) == "⛔ 未設定試算表 ID，暫停寫入"
    block["head_lines"] = [{"text": "設定試算表：本", "_tone": "中性"}]
    assert sections.set3_summary(block) == "0 個鍵"   # 沒有紅字時照舊寫鍵數


def test_SET3摘要_壞列與結構檢查行帶進摘要_標點用逗號():
    block = {"placeholder": None,
             "_rows": [{"key_text": "a", "value_text": "⬜ 未設定"}, {"key_text": "b", "value_text": sections.SET_BAD_ROW_TEXT},
                       {"key_text": "c", "value_text": "3"}],
             "head_lines": [{"text": "設定試算表：本", "_tone": "中性"}],
             "live_lines": [{"text": "⚠ 2 列格式不符，未採用", "_tone": "黃"}]}
    assert sections.set3_summary(block) == "3 個鍵，1 個未設定：a，1 個格式不符未採用：b，⚠ 2 列格式不符，未採用"


def test_SET2摘要_來源缺寫出缺的來源鍵():
    first = _b(_model("first"), "SET-2")
    assert first["placeholder"]["_empty_kind"] == "來源缺"
    assert sections.set2_summary(first).startswith("缺 fetch_log：")
    assert set_logic.TEXT_NO_RECORDS in sections.set2_summary(first)
    assert sections.set2_summary(_b(_model("logfail"), "SET-2")).startswith("⛔ 取數失敗：")   # 取數失敗不是來源缺
