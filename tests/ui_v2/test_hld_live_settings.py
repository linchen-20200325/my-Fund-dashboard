# -*- coding: utf-8 -*-
"""hld 正式模式的 `user_setting` 解析（S6b-2 第一塊；純函式，不需要 streamlit）。

體例照 tests/ui_v2/test_alo_live_logic.py 的 `parse_user_settings` 那幾條。
壞值、`broken_keys` 一律回訊息 —— **不得畫成「未設定」**（§1；比照 alo settingfail）。
"""

from __future__ import annotations

import json
import pathlib
import sys
from datetime import date

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

from ui_v2.hld import fixtures, live, logic  # noqa: E402

_KINDS = {"hld_window_start": "date", "hld_window_end": "date", "hld_deviation_rules": "rules"}
_RULES = [
    {"indicator": "最大回撤", "direction": "低於", "value": -30},
    {"indicator": "配息佔淨值比", "direction": "高於", "value": 20.5},
]
_PREFIX = "設定值讀不到可用的形狀："


def _rows(**values):
    return {
        key: {
            "setting_key": key,
            "setting_value": value,
            "value_kind": _KINDS.get(key, "str"),
            "updated_at": "2026-10-01T09:00:00+08:00",
        }
        for key, value in values.items()
    }


def _by_key(rows):
    return {row["setting_key"]: row["setting_value"] for row in rows}


def test_三鍵正常_解析成logic吃的原生值():
    rows, problem = live.parse_user_settings(_rows(
        hld_window_start="2026-06-01",
        hld_window_end="2026-09-30",
        hld_deviation_rules=json.dumps(_RULES, ensure_ascii=False),
    ))
    assert problem is None
    assert [r["setting_key"] for r in rows] == list(live.SETTING_KEYS)
    assert [r["value_kind"] for r in rows] == ["date", "date", "rules"]
    assert all(r["updated_at"] == "2026-10-01T09:00:00+08:00" for r in rows)
    dataset = {"user_setting": rows}
    assert logic.saved_window(dataset) == ("2026-06-01", "2026-09-30")
    assert logic.saved_rules(dataset) == [
        {"indicator": "最大回撤", "direction": "低於", "value": -30.0},
        {"indicator": "配息佔淨值比", "direction": "高於", "value": 20.5},
    ]


def test_與fixtures形狀一致_示範門檻來回一趟不變():
    window = ("2026-06-01", "2026-09-30")
    rules = list(fixtures._RULES_DEFAULT)
    rows, problem = live.parse_user_settings(_rows(
        hld_window_start=window[0],
        hld_window_end=window[1],
        hld_deviation_rules=json.dumps(rules, ensure_ascii=False),
    ))
    assert problem is None
    expected = fixtures.user_settings(window=window, rules=rules)
    assert [set(r) for r in rows] == [set(r) for r in expected]
    assert [(r["setting_key"], r["setting_value"], r["value_kind"]) for r in rows] == [
        (r["setting_key"], r["setting_value"], r["value_kind"]) for r in expected
    ]


def test_空陣列是零條門檻不是錯誤():
    rows, problem = live.parse_user_settings(_rows(hld_deviation_rules="[]"))
    assert problem is None
    assert _by_key(rows)["hld_deviation_rules"] == []


@pytest.mark.parametrize("raw", [None, ""])
def test_None與空字串_當未設定(raw):
    rows, problem = live.parse_user_settings(_rows(
        hld_window_start=raw, hld_window_end=raw, hld_deviation_rules=raw,
    ))
    assert problem is None
    assert _by_key(rows) == dict.fromkeys(live.SETTING_KEYS)
    assert logic.saved_window({"user_setting": rows}) == (None, None)
    assert logic.saved_rules({"user_setting": rows}) == []


def test_整張表沒有本頁的鍵_當未設定():
    rows, problem = live.parse_user_settings({})
    assert problem is None
    assert _by_key(rows) == dict.fromkeys(live.SETTING_KEYS)


@pytest.mark.parametrize("raw", [
    "20260601",            # 3.11 fromisoformat 收，本頁不收
    "2026-W23-1",
    "2026-6-1",
    "2026-06-01T00:00",
    " 2026-06-01",
    "2026-06-01 ",
    "２０２６-０６-０１",   # 全形數字
    "2026-02-30",          # 形狀對、日期不存在
    "2026/06/01",
    " ",
])
@pytest.mark.parametrize("key", ["hld_window_start", "hld_window_end"])
def test_壞日期_讀取失敗(key, raw):
    rows, problem = live.parse_user_settings(_rows(**{key: raw}))
    assert problem == f"{_PREFIX}{key} 這一列解析不了"
    assert _by_key(rows)[key] is None


@pytest.mark.parametrize("raw, tail", [
    ("[", "的值不是 JSON（JSONDecodeError）"),
    ("not json", "的值不是 JSON（JSONDecodeError）"),
    ('[{"indicator": "a", "direction": "低於", "value": NaN}]', "的值裡有 NaN"),
    ('[{"indicator": "a", "direction": "低於", "value": Infinity}]', "的值裡有 Infinity"),
    (" []", "的值前後有空白"),
    ('{"indicator": "a", "direction": "低於", "value": 1}', "的值不是 JSON 陣列"),
    ('"[]"', "的值不是 JSON 陣列"),
    ("3", "的值不是 JSON 陣列"),
])
def test_壞JSON與非陣列_讀取失敗(raw, tail):
    rows, problem = live.parse_user_settings(_rows(hld_deviation_rules=raw))
    assert problem == f"{_PREFIX}hld_deviation_rules {tail}"
    assert _by_key(rows)["hld_deviation_rules"] is None


@pytest.mark.parametrize("element", [
    {"indicator": "最大回撤", "direction": "低於"},                          # 缺 value
    {"indicator": "最大回撤", "value": 1},                                    # 缺 direction
    {"direction": "低於", "value": 1},                                        # 缺 indicator
    {"indicator": "最大回撤", "direction": "低於", "value": 1, "x": 2},       # 多一欄
    {"indicator": "", "direction": "低於", "value": 1},                       # 指標名空
    {"indicator": 3, "direction": "低於", "value": 1},                        # 指標名不是字串
    {"indicator": "最大回撤", "direction": "<", "value": 1},                  # 方向不合法
    {"indicator": "最大回撤", "direction": "低於 ", "value": 1},
    {"indicator": "最大回撤", "direction": None, "value": 1},
    {"indicator": "最大回撤", "direction": "低於", "value": "1"},             # 數值是字串
    {"indicator": "最大回撤", "direction": "低於", "value": True},            # bool 不當數
    {"indicator": "最大回撤", "direction": "低於", "value": None},
    "示意門檻一",
    ["最大回撤", "低於", 1],
    None,
])
def test_元素形狀不符_讀取失敗(element):
    raw = json.dumps([_RULES[0], element], ensure_ascii=False)
    rows, problem = live.parse_user_settings(_rows(hld_deviation_rules=raw))
    assert problem == f"{_PREFIX}hld_deviation_rules 這一列解析不了"
    assert _by_key(rows)["hld_deviation_rules"] is None


def test_數值溢位成inf_讀取失敗():
    # `1e400` 是合法 JSON 數字字面，`json.loads` 讀成 inf（不經 parse_constant）。
    raw = '[{"indicator": "最大回撤", "direction": "低於", "value": 1e400}]'
    rows, problem = live.parse_user_settings(_rows(hld_deviation_rules=raw))
    assert problem == f"{_PREFIX}hld_deviation_rules 這一列解析不了"
    assert _by_key(rows)["hld_deviation_rules"] is None


def test_set頁示意值_讀取失敗():
    # `ui_v2/set/fixtures.py` 那一筆示意值；正式模式萬一讀到同樣的字串，不能被當成門檻或未設定。
    rows, problem = live.parse_user_settings(_rows(hld_deviation_rules='["示意門檻一"]'))
    assert problem == f"{_PREFIX}hld_deviation_rules 這一列解析不了"
    assert _by_key(rows)["hld_deviation_rules"] is None


def test_broken_keys_讀取失敗_即使值看起來合法():
    rows, problem = live.parse_user_settings(
        _rows(hld_window_start="2026-06-01", hld_window_end="2026-09-30"),
        broken_keys=["hld_window_end"],
    )
    assert problem == f"{_PREFIX}hld_window_end 這一列解析不了"
    assert _by_key(rows) == {
        "hld_window_start": "2026-06-01", "hld_window_end": None, "hld_deviation_rules": None,
    }


def test_broken_keys_鍵不在rows裡也要報():
    _rows_out, problem = live.parse_user_settings({}, broken_keys=["hld_deviation_rules"])
    assert problem == f"{_PREFIX}hld_deviation_rules 這一列解析不了"


def test_未知鍵忽略_含別頁壞掉的鍵():
    rows, problem = live.parse_user_settings(
        _rows(alo_basis="cost", set_max_age_days="二十一", hld_window_start="2026-06-01"),
        broken_keys=["alo_tolerance_pp"],
    )
    assert problem is None
    assert [r["setting_key"] for r in rows] == list(live.SETTING_KEYS)
    assert _by_key(rows)["hld_window_start"] == "2026-06-01"


def test_多個壞值_全部列出():
    _rows_out, problem = live.parse_user_settings(
        _rows(hld_window_start="20260601", hld_deviation_rules="["),
        broken_keys=["hld_window_end"],
    )
    assert problem == (
        f"{_PREFIX}hld_window_end 這一列解析不了；"
        "hld_window_start 這一列解析不了；"
        "hld_deviation_rules 的值不是 JSON（JSONDecodeError）"
    )


# ───────────────────────── 稽核回修（M-1 與 1～6）─────────────────────────


def test_M1_超長整數門檻值_讀取失敗不是整頁錯誤():
    raw = '[{"indicator": "最大回撤", "direction": "低於", "value": ' + "9" * 400 + "}]"
    rows, problem = live.parse_user_settings(_rows(hld_deviation_rules=raw))
    assert problem == f"{_PREFIX}hld_deviation_rules 這一列解析不了"
    assert _by_key(rows)["hld_deviation_rules"] is None


def test_門檻值一律是float():
    raw = json.dumps([
        {"indicator": "最大回撤", "direction": "低於", "value": -30},
        {"indicator": "配息佔淨值比", "direction": "高於", "value": 20.5},
    ], ensure_ascii=False)
    rows, problem = live.parse_user_settings(_rows(hld_deviation_rules=raw))
    assert problem is None
    assert [type(rule["value"]) for rule in _by_key(rows)["hld_deviation_rules"]] == [float, float]


@pytest.mark.parametrize("rows", [None, [], ["hld_window_start"], "hld_window_start", 0])
def test_rows不是dict_三鍵讀取失敗(rows):
    out, problem = live.parse_user_settings(rows)
    assert problem == _PREFIX + "；".join(f"{key} 這一列解析不了" for key in live.SETTING_KEYS)
    assert _by_key(out) == dict.fromkeys(live.SETTING_KEYS)


@pytest.mark.parametrize("broken", ["hld_window_start", b"hld_window_start"])
def test_broken_keys是字串_呼叫端錯誤直接拋(broken):
    with pytest.raises(TypeError):
        live.parse_user_settings({}, broken_keys=broken)


@pytest.mark.parametrize("row", [
    None,
    {},
    {"setting_key": "hld_window_start", "value_kind": "date", "updated_at": None},
    "2026-06-01",
])
def test_該列存在卻缺setting_value_讀取失敗不是未設定(row):
    rows = {**_rows(hld_window_end="2026-09-30"), "hld_window_start": row}
    out, problem = live.parse_user_settings(rows)
    assert problem == f"{_PREFIX}hld_window_start 這一列解析不了"
    assert _by_key(out)["hld_window_start"] is None


def test_該列缺setting_value且也在broken_keys_只報一次():
    _out, problem = live.parse_user_settings({"hld_window_start": None}, broken_keys=["hld_window_start"])
    assert problem == f"{_PREFIX}hld_window_start 這一列解析不了"


def test_JSON物件重複鍵_讀取失敗():
    raw = '[{"indicator": "最大回撤", "direction": "低於", "value": 1, "value": 2}]'
    rows, problem = live.parse_user_settings(_rows(hld_deviation_rules=raw))
    assert problem == f"{_PREFIX}hld_deviation_rules 這一列解析不了"
    assert _by_key(rows)["hld_deviation_rules"] is None


@pytest.mark.parametrize("key", ["hld_window_start", "hld_window_end"])
@pytest.mark.parametrize("raw", [date(2026, 6, 1), 20260601, ["2026-06-01"]])
def test_非字串日期_讀取失敗(key, raw):
    rows, problem = live.parse_user_settings(_rows(**{key: raw}))
    assert problem == f"{_PREFIX}{key} 這一列解析不了"
    assert _by_key(rows)[key] is None


def _what_caller_hands_to_logic(rows, broken_keys=()):
    """呼叫端契約（同 `parse_user_settings` docstring 範例）：有訊息就交空列表，不交部分結果。"""
    out, problem = live.parse_user_settings(rows, broken_keys)
    return ([] if problem is not None else out), problem


def test_契約_有失敗時回傳裡可能留著部分結果_所以呼叫端必須交空列表():
    rows = _rows(hld_window_start="20260601", hld_window_end="2026-09-30")
    out, problem = live.parse_user_settings(rows)
    assert problem is not None
    # 解析器本身會留下解析成功的迄日 —— 這正是呼叫端不能直接交出去的原因。
    assert _by_key(out)["hld_window_end"] == "2026-09-30"
    handed, _ = _what_caller_hands_to_logic(rows)
    assert handed == []


def test_契約_沒有失敗時三列照交():
    rows = _rows(hld_window_start="2026-06-01", hld_window_end="2026-09-30")
    handed, problem = _what_caller_hands_to_logic(rows)
    assert problem is None
    assert logic.saved_window({"user_setting": handed}) == ("2026-06-01", "2026-09-30")


# ───────────────────────── R-7（客戶 2026-10-09 裁示）：讀不到的三種情形不說「尚未設定」─────────────────────────
# L1 `_reduce_user_settings` 的 `bad_rows` 一列的形狀（`_parse_rows`）：{"row", "reason", "cells"}。
_BLANK_KEY_BAD_ROW = {"row": 2, "reason": "setting_key：不可空", "cells": ["", "2026-06-01", "date", ""]}


def test_R7_分頁不存在_讀取失敗():
    rows, problem = live.parse_user_settings({}, [], tab_missing=True, bad_rows=[])
    assert problem == f"{_PREFIX}找不到設定分頁"
    assert _by_key(rows) == dict.fromkeys(live.SETTING_KEYS)


@pytest.mark.parametrize("form", ["bad_rows鍵欄空", "rows鍵只有空白", "broken_keys鍵只有空白"])
def test_R7_設定鍵空白_讀取失敗(form):
    rows = _rows(hld_window_start="2026-06-01", hld_window_end="2026-09-30")
    broken, bad = [], []
    if form == "bad_rows鍵欄空":
        bad = [_BLANK_KEY_BAD_ROW]
    elif form == "rows鍵只有空白":
        rows["  "] = {"setting_key": "  ", "setting_value": "x", "value_kind": "str", "updated_at": None}
    else:
        broken = ["　"]
    _out, problem = live.parse_user_settings(rows, broken, bad_rows=bad)
    assert problem == f"{_PREFIX}有一列設定鍵空白"


@pytest.mark.parametrize("key", live.SETTING_KEYS)
@pytest.mark.parametrize("pad", [" {} ", "{} ", " {}", "\t{}"])
def test_R7_鍵前後帶空白_讀取失敗_值不被拿去用(key, pad):
    good = {"hld_window_start": "2026-06-01", "hld_window_end": "2026-09-30",
            "hld_deviation_rules": json.dumps(_RULES, ensure_ascii=False)}
    rows = _rows(**{k: v for k, v in good.items() if k != key})
    padded = pad.format(key)
    rows[padded] = {"setting_key": padded, "setting_value": good[key], "value_kind": _KINDS[key], "updated_at": None}
    out, problem = live.parse_user_settings(rows)
    assert problem == f"{_PREFIX}{key} 前後帶空白"
    assert _by_key(out)[key] is None   # 不 strip 後照用


def test_R7_鍵前後帶空白_鍵在broken_keys裡也要報():
    _out, problem = live.parse_user_settings({}, [" hld_window_end"])
    assert problem == f"{_PREFIX}hld_window_end 前後帶空白"


def test_R7_別頁的鍵前後帶空白_忽略():
    rows = _rows(hld_window_start="2026-06-01")
    rows[" alo_basis"] = {"setting_key": " alo_basis", "setting_value": "成本", "value_kind": "list", "updated_at": None}
    _out, problem = live.parse_user_settings(rows, [" set_max_age_days"])
    assert problem is None


def test_R7_多種同時發生_全部列出_次序固定():
    rows = {" hld_window_start": {"setting_key": " hld_window_start", "setting_value": "2026-06-01",
                                  "value_kind": "date", "updated_at": None}}
    _out, problem = live.parse_user_settings(rows, ["hld_window_end"], tab_missing=True,
                                             bad_rows=[_BLANK_KEY_BAD_ROW])
    assert problem == (f"{_PREFIX}找不到設定分頁；有一列設定鍵空白；hld_window_start 前後帶空白；"
                       "hld_window_end 這一列解析不了")


def test_R7_反向_只有標頭零筆資料_仍是尚未設定():
    rows, problem = live.parse_user_settings({}, [], tab_missing=False, bad_rows=[])
    assert problem is None
    assert _by_key(rows) == dict.fromkeys(live.SETTING_KEYS)


def test_R7_反向_bad_rows鍵欄有值_不算鍵空白():
    bad = [{"row": 3, "reason": "value_kind：不可空", "cells": ["alo_basis", "成本", "", ""]}]
    _out, problem = live.parse_user_settings(_rows(hld_window_start="2026-06-01"), [], bad_rows=bad)
    assert problem is None
