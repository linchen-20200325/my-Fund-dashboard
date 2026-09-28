# -*- coding: utf-8 -*-
"""ui_v2/alo/live.py 的純函式測試（fast lane；不需要 streamlit、不碰舊樹、不打網路）。

依據 docs/v2/49_data_integration_plan.md §3.4 第 6 項（正式入口不帶示意字樣）、
2026-09-28 客戶核准的 docs/wireframes/draft_alo_live.html，以及 `CLAUDE.md` §1（Fail Loud）。
"""

from __future__ import annotations

import json
import pathlib
import sys

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

from ui_v2.alo import fixtures, live, logic  # noqa: E402

_CORE, _SAT, _CASH = fixtures.CORE, fixtures.SATELLITE, fixtures.CASH


def _weights(pairs):
    return json.dumps([{"bucket": b, "weight_ratio": w} for b, w in pairs], ensure_ascii=False)


def _rows(**values):
    """做出 L2 `load_user_settings()["rows"]` 的形狀（`setting_value` 是試算表上的原字串）。"""
    return {key: {"setting_key": key, "setting_value": text, "value_kind": "list",
                  "updated_at": "2026-09-20T06:00:00Z"}
            for key, text in values.items()}


def _by_key(rows):
    return {r["setting_key"]: r for r in rows}


# ═══════════════════════ 設定值解析：好的那一邊 ═══════════════════════


def test_五個鍵一定都在_沒設定的那一列值為None():
    rows, problem = live.parse_user_settings({})
    assert problem is None
    assert [r["setting_key"] for r in rows] == list(live.SETTING_KEYS)
    assert all(r["setting_value"] is None and r["updated_at"] is None for r in rows)
    # `logic._setting_row` 讀不到鍵會 KeyError —— 五列都在才不會炸。
    dataset = dict(fixtures.scenario("full"), user_setting=rows)
    assert logic.build_page_model(dataset)["title"] == logic.PAGE_TITLE


def test_五個鍵都解析得出來_而且吃得進build_page_model():
    rows, problem = live.parse_user_settings(_rows(
        alo_target_weights=_weights([(_CORE, 0.6), (_SAT, 0.3), (_CASH, None)]),
        alo_tolerance_pp="4",
        alo_basis=logic.BASIS_COST,
        alo_bucket_names=json.dumps([_CORE, _SAT, _CASH], ensure_ascii=False),
        alo_scenario_input=json.dumps([{"bucket": _SAT, "amount_twd": 100000}], ensure_ascii=False),
    ))
    assert problem is None
    got = _by_key(rows)
    assert got["alo_target_weights"]["setting_value"] == [
        {"bucket": _CORE, "weight_ratio": 0.6},
        {"bucket": _SAT, "weight_ratio": 0.3},
        {"bucket": _CASH, "weight_ratio": None},
    ]
    assert got["alo_tolerance_pp"]["setting_value"] == 4.0
    assert got["alo_basis"]["setting_value"] == logic.BASIS_COST
    assert got["alo_bucket_names"]["setting_value"] == [_CORE, _SAT, _CASH]
    assert got["alo_scenario_input"]["setting_value"] == [{"bucket": _SAT, "amount_twd": 100000}]
    model = logic.build_page_model(dict(fixtures.scenario("full"), user_setting=rows))
    assert logic.find_block(model, "ALO-2")["_rows"], "解析出來的目標沒有進 ALO-2"


def test_解析出來的形狀與fixtures那一份逐欄相同():
    """示範模式的 `user_setting` 列長什麼樣，正式模式就要長什麼樣（同一個 `logic` 吃）。"""
    rows, _ = live.parse_user_settings({})
    demo = fixtures.user_settings(targets=fixtures.TARGETS, tolerance=fixtures.TOLERANCE,
                                  basis=fixtures.BASIS_COST, bucket_names=fixtures.BUCKET_NAMES,
                                  scenario_rows=fixtures.SCENARIO_ROWS)
    assert [r["setting_key"] for r in rows] == [r["setting_key"] for r in demo]
    assert all(set(r) == set(demo[0]) for r in rows)


def test_浮點金額剛好是整數時照收_同一個數不是換算():
    rows, problem = live.parse_user_settings(_rows(
        alo_scenario_input=json.dumps([{"bucket": _SAT, "amount_twd": 100000.0}], ensure_ascii=False)))
    assert problem is None
    assert _by_key(rows)["alo_scenario_input"]["setting_value"] == [{"bucket": _SAT, "amount_twd": 100000}]


# ═══════════════════════ 設定值解析：壞的那一邊（一律 fail loud，不當成「尚未設定」）═══════════════════════


@pytest.mark.parametrize("key, text, why", [
    ("alo_target_weights", "不是 JSON", "不是 JSON"),
    ("alo_target_weights", '{"bucket": "x"}', "不是陣列"),
    ("alo_target_weights", '[{"bucket": "x"}]', "少一個欄位"),
    ("alo_target_weights", '[{"bucket": "x", "weight_ratio": 0.5, "zz": 1}]', "多一個欄位"),
    ("alo_target_weights", '[{"bucket": "", "weight_ratio": 0.5}]', "bucket 空字串"),
    ("alo_target_weights", '[{"bucket": "x", "weight_ratio": 60}]', "百分比寫成整數 → 100 倍誤差"),
    ("alo_target_weights", '[{"bucket": "x", "weight_ratio": -0.1}]', "負數"),
    ("alo_target_weights", '[{"bucket": "x", "weight_ratio": NaN}]', "NaN"),
    ("alo_target_weights", '[{"bucket": "x", "weight_ratio": Infinity}]', "Infinity"),
    ("alo_target_weights", '[{"bucket": "x", "weight_ratio": true}]', "布林不是數"),
    ("alo_target_weights", ' [] ', "前後有空白"),
    ("alo_tolerance_pp", "四", "不是數"),
    ("alo_tolerance_pp", "nan", "NaN"),
    ("alo_tolerance_pp", "1e999", "溢位成 inf"),
    ("alo_tolerance_pp", " 4 ", "前後有空白"),
    ("alo_basis", "cost", "舊存值"),
    ("alo_basis", "成本 ", "帶空白"),
    ("alo_basis", "市值成本", "兩個接起來"),
    ("alo_bucket_names", '["a", 1]', "元素不是字串"),
    ("alo_bucket_names", '["a", "  "]', "元素只有空白"),
    ("alo_scenario_input", '[{"bucket": "x", "amount_twd": 1.5}]', "金額不是整數"),
    ("alo_scenario_input", '[{"bucket": "x", "amount_twd": "100"}]', "金額是字串"),
])
def test_壞值一律回訊息_而且該鍵不會被說成尚未設定(key, text, why):
    rows, problem = live.parse_user_settings(_rows(**{key: text}))
    assert problem is not None, (key, text, why)
    assert key in problem, (key, why)
    # 值一律不交出去 —— 由 `source.py` 把整張 `user_setting` 清空、改走取數失敗那條路。
    assert _by_key(rows)[key]["setting_value"] is None


def test_極深巢狀不崩_當成壞值():
    rows, problem = live.parse_user_settings(_rows(alo_bucket_names="[" * 100000 + "]" * 100000))
    assert problem is not None and _by_key(rows)["alo_bucket_names"]["setting_value"] is None


def test_L1說這一列解析不了_就不是尚未設定():
    """L1 `load_user_settings` docstring 逐字：`broken_keys` 的鍵「畫面應顯示錯誤狀態，不是 ⬜ 未設定」。"""
    rows, problem = live.parse_user_settings({}, broken_keys=["alo_tolerance_pp"])
    assert problem is not None and "alo_tolerance_pp" in problem
    assert _by_key(rows)["alo_tolerance_pp"]["setting_value"] is None


def test_不是本頁的鍵不影響():
    rows, problem = live.parse_user_settings(_rows(set_max_age_days="21"), broken_keys=["set_max_age_days"])
    assert problem is None and len(rows) == len(live.SETTING_KEYS)


def test_多個問題一起回報_不是只回第一個():
    _rows_out, problem = live.parse_user_settings(_rows(alo_tolerance_pp="四", alo_basis="cost"))
    assert "alo_tolerance_pp" in problem and "alo_basis" in problem


# ═══════════════════════ 兩張表一起失敗（示範模式分得開、正式模式分不開）═══════════════════════


def test_holding與policy一起標失敗():
    out = live.tables_failed_together("上游 503")
    assert out == {"holding": "上游 503", "policy": "上游 503"}
    assert set(out) <= set(logic.FETCHABLE_TABLES)     # build_page_model 認得這兩個鍵
    model = logic.build_page_model(dict(fixtures.scenario("full"), errors=out, holding=[], policy=[]))
    assert model["title"] == logic.PAGE_TITLE


# ═══════════════════════ 正式模式的模型調整 ═══════════════════════


def _live_model(name="full"):
    return live.apply_live_notes(logic.build_page_model(fixtures.scenario(name)))


def _all_strings(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for value in node.values():
            yield from _all_strings(value)
    elif isinstance(node, (list, tuple, set)):
        for value in node:
            yield from _all_strings(value)


@pytest.mark.parametrize("name", fixtures.ALL_SCENARIO_NAMES)
def test_示意字樣在正式模式的模型裡一個都不剩(name):
    model = _live_model(name)
    assert model["hint_note"] == ""
    strings = list(_all_strings(model))
    assert logic.HINT_NOTE not in strings
    assert not any(logic.PAGE_HINT_NOTE in s for s in strings)


def test_正控_示範模式的模型本來就有示意字樣():
    model = logic.build_page_model(fixtures.scenario("full"))
    assert model["hint_note"] == logic.PAGE_HINT_NOTE
    assert sum(logic.HINT_NOTE in b["detail_lines"] for b in model["blocks"]) >= 6


def test_不改呼叫端手上的那一份():
    model = logic.build_page_model(fixtures.scenario("full"))
    before = logic.find_block(model, "ALO-1")["detail_lines"][:]
    live.apply_live_notes(model)
    assert logic.find_block(model, "ALO-1")["detail_lines"] == before
    assert model["hint_note"] == logic.PAGE_HINT_NOTE


def _buttons(model):
    out = []
    for block in model["blocks"]:
        out.extend(block.get("buttons", ()) or ())
    return out


def test_會寫user_setting的按鈕停用並寫出原因_其餘不動():
    demo = logic.build_page_model(fixtures.scenario("full"))
    model = _live_model("full")
    kinds = {b["_action_kind"] for b in _buttons(model) if not b["_enabled"]}
    assert kinds == {"存檔"}, kinds
    for button in _buttons(model):
        if button["_writes"]:
            assert button["_enabled"] is False
            assert button["disabled_reason"] == live.SAVE_DISABLED_REASON
    # 匯出、導覽、新增列三類一字未動（連標籤與停用原因都與示範模式相同）。
    same = [(b["label"], b["_enabled"], b["disabled_reason"])
            for b in _buttons(model) if not b["_writes"]]
    assert same == [(b["label"], b["_enabled"], b["disabled_reason"])
                    for b in _buttons(demo) if not b["_writes"]]


def test_停用原因與mkt頁那一句逐字相同_不另編一句():
    mkt_live = pytest.importorskip("ui_v2.mkt.live")
    assert live.SAVE_DISABLED_REASON == mkt_live.SAVE_DISABLED_REASON


def test_正式模式的模型零禁詞_零方向詞零箭頭():
    for name in fixtures.ALL_SCENARIO_NAMES:
        text = "\n".join(_all_strings(_live_model(name)))
        for word in logic.FORBIDDEN_DIRECTION_WORDS + logic.FORBIDDEN_ADVICE_WORDS:
            assert word not in text, (name, word)
        for arrow in logic.FORBIDDEN_ARROWS:
            assert arrow not in text, (name, arrow)
        for word in logic.FORBIDDEN_BUTTON_WORDS:
            assert word not in [b["label"] for b in _buttons(_live_model(name))], (name, word)


def test_live的import就是那幾個_純函式模組():
    """⚠️ 刻意用 AST 不用字面掃描：本檔的 docstring 自己就寫著「不 import streamlit」，
    字面掃描會掃到那一句話而誤報（`CLAUDE.md` §-1.5.1c 判定 2：字表選錯，掃再多次都沒用）。
    整個 `ui_v2/` 的 import 隔離另有 fail-closed 守衛 tests/ui_v2/test_ui_v2_live_import_guard.py。"""
    import ast

    tree = ast.parse((_ROOT / "ui_v2" / "alo" / "live.py").read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            prefix = ("." * node.level) + (node.module or "")
            names.add(prefix)
            names.update(prefix + ("." if node.module else "") + a.name for a in node.names)
    assert names == {"__future__", "__future__.annotations", "copy", "json", "math", ".", ".logic"}, names
