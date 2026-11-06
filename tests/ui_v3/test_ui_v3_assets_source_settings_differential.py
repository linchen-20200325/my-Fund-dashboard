# -*- coding: utf-8 -*-
"""`ui_v3/adapters/assets_source.py::parse_settings` 對 `ui_v2/alo/live.py::parse_user_settings` 的差分測試。

ui_v3 不得 import ui_v2，所以 adapter 裡的設定解析是 ui_v2 的最小鏡像；本檔（測試可以 import ui_v2）把兩者**逐案**對照，
鎖住「同一個試算表字串，兩邊對『可用／不可用／未設定』與解出的值（含型別）判得一樣」。比對方式：
- 逐鍵：只放那一個鍵的列（避免別的鍵的問題掩蓋它），比 (解出的值、有沒有問題)；
- 組合：四個鍵一起（含 `broken_keys`），比「整體有沒有問題」與可用時四個鍵的值。
值用 `repr` 比（`1` 與 `1.0`、`True` 與 `1` 都要分得出來）。ui_v2 在某些輸入會**拋例外**（整頁崩潰）而不是回問題：
這些列在 `UI_V2_RAISES`，adapter 的處理是 fail-closed（當成不可用），逐案斷言，不算漏差。
"""
from __future__ import annotations

import pathlib
import random
import sys

import pytest

_HERE = pathlib.Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import assets_source_support as X  # noqa: E402
from ui_v3.adapters import assets_source as REAL  # noqa: E402

pytest.importorskip("streamlit")     # ui_v2.alo.live 的上層套件 import 鏈；沒有 streamlit 的直譯器跳過，CI 會跑
from ui_v2.alo import live as UI2    # noqa: E402

BIG_INT = "1" + "0" * 400            # JSON 合法的超大整數；ui_v2 在 math.isfinite 拋 OverflowError

BASIS = ["成本", "市值", "cost", "mv", "", " 成本", "成本 ", "成本市值", "Cost", "市值\n", None, 123, True, [], ["成本"], {"a": 1}, 1.5, b"x"]
TOLERANCE = ["5", "5.0", "0", "-0", "-5", "+5", "1e3", "1E-3", "1_0", "0x10", "٣", "5%", "5 ", " 5", "\t5", "5\n", "", " ", "abc", "nan", "NaN",
             "inf", "-inf", "Infinity", "1e999", "-1e999", ".5", "5.", "1,5", "１２", "0.1", "100", "3.14159", None, 5, 5.0, True, [], ["5"]]
JSON_PIECES_COMMON = ["[]", "null", "{}", "5", '"x"', "true", "[null]", "[1]", "[[]]", " []", "[] ", "\n[]", "[]\n", "[1,]", "[,]", "[", "]",
                      "NaN", "[NaN]", "[Infinity]", "[-Infinity]", "", " ", "not json", "'[]'", "[1e999]", f"[{BIG_INT}]"]
TARGETS = JSON_PIECES_COMMON + [
    '[{"bucket":"core","weight_ratio":0.5}]',
    '[{"bucket":"core","weight_ratio":0.5},{"bucket":"sat","weight_ratio":0.5}]',
    '[{"bucket":"core","weight_ratio":null}]',
    '[{"bucket":"core","weight_ratio":0}]',
    '[{"bucket":"core","weight_ratio":1}]',
    '[{"bucket":"core","weight_ratio":1.0}]',
    '[{"bucket":"core","weight_ratio":1.0000001}]',
    '[{"bucket":"core","weight_ratio":-0.0}]',
    '[{"bucket":"core","weight_ratio":-0.1}]',
    '[{"bucket":"core","weight_ratio":60}]',
    '[{"bucket":"core","weight_ratio":"0.5"}]',
    '[{"bucket":"core","weight_ratio":true}]',
    '[{"bucket":"core","weight_ratio":[0.5]}]',
    '[{"bucket":"core","weight_ratio":1e999}]',
    '[{"bucket":"core","weight_ratio":NaN}]',
    '[{"bucket":"core","weight_ratio":Infinity}]',
    f'[{{"bucket":"core","weight_ratio":{BIG_INT}}}]',
    '[{"bucket":"core"}]', '[{"weight_ratio":0.5}]', '[{"bucket":"core","weight_ratio":0.5,"extra":1}]',
    '[{"bucket":"","weight_ratio":0.5}]', '[{"bucket":"  ","weight_ratio":0.5}]', '[{"bucket":" core ","weight_ratio":0.5}]',
    '[{"bucket":1,"weight_ratio":0.5}]', '[{"bucket":null,"weight_ratio":0.5}]', '[{"bucket":"未分類","weight_ratio":0.3}]',
    '[{"bucket":"a","weight_ratio":0.5},{"bucket":"a","weight_ratio":0.5}]',
    '[{"bucket":"a","bucket":"b","weight_ratio":0.5}]', '[{"bucket":"core","weight_ratio":0.5},1]',
    '[{"bucket":"core","weight_ratio":0.5}] ', ' [{"bucket":"core","weight_ratio":0.5}]',
    '{"bucket":"core","weight_ratio":0.5}', '[["bucket","core"]]', "[" * 20000 + "]" * 20000,
    5, None, 0.5, True, [], {"bucket": "core"},
]
NAMES = JSON_PIECES_COMMON + [
    '["core"]', '["core","sat"]', '["core","core"]', '[" core"]', '["core "]', '[""]', '["  "]', '[1]', '[null]', '["a",1]', '["a",null]',
    '[["a"]]', '[{"bucket":"a"}]', '["未分類"]', '["\\u6838\\u5fc3"]', '["a\\nb"]', '["a"] ', ' ["a"]', "[\"a\"]\t",
    5, None, [], ["core"], True,
]
KEYS = {
    "alo_basis": BASIS, "alo_target_weights": TARGETS, "alo_tolerance_pp": TOLERANCE, "alo_bucket_names": NAMES,
}
NAME_OF = {"alo_basis": "basis", "alo_target_weights": "targets", "alo_tolerance_pp": "tolerance", "alo_bucket_names": "bucket_names"}


def _random_json_cases(n=120, seed=20261105):
    """隨機組合 targets／bucket_names 的 JSON 文字（固定種子，可重現）。"""
    rng = random.Random(seed)
    buckets = ["core", "sat", "", " ", "未分類", 1, None, "a b"]
    weights = [0, 0.1, 0.5, 1, 1.0, -0.1, 1.2, None, "0.5", True, 1e999, 10 ** 30]
    out_targets, out_names = [], []
    import json
    for _ in range(n):
        items = []
        for _i in range(rng.randint(0, 4)):
            item = {"bucket": rng.choice(buckets), "weight_ratio": rng.choice(weights)}
            if rng.random() < 0.1:
                item.pop(rng.choice(list(item)))
            if rng.random() < 0.1:
                item["extra"] = 1
            items.append(item)
        try:
            out_targets.append(json.dumps(items))
        except ValueError:
            out_targets.append("[]")
        out_names.append(json.dumps([rng.choice(buckets) for _ in range(rng.randint(0, 4))]))
    return out_targets, out_names


RAND_TARGETS, RAND_NAMES = _random_json_cases()
KEYS["alo_target_weights"] = TARGETS + RAND_TARGETS
KEYS["alo_bucket_names"] = NAMES + RAND_NAMES


def _ui2(rows, broken=()):
    return UI2.parse_user_settings(rows, broken)


def _one_key(key, raw, broken):
    rows = {key: X.setting_row(key, raw)}
    return rows, ([key] if broken else [])


def _ui2_one(key, raw, broken=False):
    """ui_v2 對單一鍵：(值的 repr, 有問題?) 或 ('RAISES', exc)。"""
    rows, bk = _one_key(key, raw, broken)
    try:
        out, problem = _ui2(rows, bk)
    except Exception as exc:  # noqa: BLE001 - 記錄 ui_v2 的崩潰型別
        return "RAISES", type(exc).__name__
    row = next(r for r in out if r["setting_key"] == key)
    return repr(row["setting_value"]), problem is not None


def _mine_one(key, raw, broken=False):
    rows, bk = _one_key(key, raw, broken)
    parsed = REAL.parse_settings(rows, bk)
    status = dict(parsed.statuses)[key]
    return repr(parsed.values[NAME_OF[key]]), status in (REAL.SETTING_INVALID, REAL.SETTING_BROKEN), status


CASES = [(k, raw) for k, raws in KEYS.items() for raw in raws]


def test_case_count_meets_the_floor():
    assert len(CASES) >= 300, len(CASES)


def single_key_mismatches(M=REAL):
    """每個 (鍵, 值) 一案；回傳不一致的案子（空 list ＝ 全一致）。ui_v2 崩潰的案子另計（見 `UI_V2_RAISES`）。"""
    bad = []
    for key, raw in CASES:
        ui = _ui2_one(key, raw)
        rows, bk = _one_key(key, raw, False)
        parsed = M.parse_settings(rows, bk)
        status = dict(parsed.statuses)[key]
        mine_problem = status in (M.SETTING_INVALID, M.SETTING_BROKEN)
        mine_value = repr(parsed.values[NAME_OF[key]])
        if ui[0] == "RAISES":
            if not (mine_problem and mine_value == "None"):
                bad.append((key, raw if not isinstance(raw, str) or len(raw) < 80 else raw[:80], "ui_v2 raises, adapter must be unusable", ui, status))
            continue
        ui_value, ui_problem = ui
        if mine_problem != ui_problem or (not ui_problem and mine_value != ui_value):
            bad.append((key, raw if not isinstance(raw, str) or len(raw) < 80 else raw[:80], ui, (mine_value, mine_problem, status)))
    return bad


def test_single_key_differential_over_all_cases():
    assert single_key_mismatches() == []


def test_unset_and_broken_rows_single_key():
    for key in KEYS:
        # 沒有這一列／值為 None → ui_v2 回 None 且沒有問題；adapter 是 unset（不是不可用）
        for rows in ({}, {key: X.setting_row(key, None)}, {key: {}}, {key: None}):
            out, problem = _ui2(rows, [])
            ui_value = next(r for r in out if r["setting_key"] == key)["setting_value"]
            parsed = REAL.parse_settings(rows, [])
            assert problem is None and ui_value is None
            assert dict(parsed.statuses)[key] == REAL.SETTING_UNSET and parsed.values[NAME_OF[key]] is None
        # 在 broken_keys 的鍵：不管列上有沒有值，ui_v2 都回問題＋值 None；adapter 是 broken_row
        for raw in (None, "x", KEYS[key][0] if isinstance(KEYS[key][0], str) else "5"):
            ui = _ui2_one(key, raw, broken=True)
            mine = _mine_one(key, raw, broken=True)
            assert ui == ("None", True) and mine == ("None", True, REAL.SETTING_BROKEN)


def test_combined_rows_differential_over_random_combinations():
    """四個鍵一起（含隨機的 broken_keys）：整體有沒有問題一致；沒問題時四個鍵的值逐一一致。1500 組，固定種子。"""
    rng = random.Random(7)
    pools = {k: [v for v in vs if not _ui2_raises(k, v)] for k, vs in KEYS.items()}
    good = {
        "alo_basis": ["成本", "市值"], "alo_tolerance_pp": ["5", "0", "2.5", "10"],
        "alo_target_weights": ['[]', '[{"bucket":"core","weight_ratio":0.6},{"bucket":"sat","weight_ratio":0.4}]',
                               '[{"bucket":"core","weight_ratio":null}]', '[{"bucket":"a","weight_ratio":1}]'],
        "alo_bucket_names": ['[]', '["core","sat"]', '["a"]'],
    }
    mismatches, checked, with_problem, without_problem = [], 0, 0, 0
    for _ in range(1500):
        rows, raws = {}, {}
        for key in KEYS:
            if rng.random() < 0.15:
                continue                                    # 這一列不存在
            raw = rng.choice(good[key]) if rng.random() < 0.85 else rng.choice(pools[key])
            raws[key] = raw
            rows[key] = X.setting_row(key, raw)
        broken = [k for k in KEYS if rng.random() < 0.08]
        out, problem = _ui2(rows, broken)
        parsed = REAL.parse_settings(rows, broken)
        checked += 1
        if (problem is not None) != (not parsed.usable):
            mismatches.append(("problem", rows, broken))
            continue
        if problem is None:
            without_problem += 1
            ui_values = {r["setting_key"]: r["setting_value"] for r in out}
            for key in KEYS:
                if repr(ui_values[key]) != repr(parsed.values[NAME_OF[key]]):
                    mismatches.append(("value", key, rows, broken))
        else:
            with_problem += 1
    assert mismatches == []
    assert checked == 1500 and with_problem > 100 and without_problem > 100      # 兩個方向都有被走到


def _ui2_raises(key, raw):
    return _ui2_one(key, raw)[0] == "RAISES"


def test_ui_v2_crash_inputs_are_unusable_in_the_adapter():
    """ui_v2 對這些輸入拋例外（整頁崩潰）；adapter 當成「不可用」（fail-closed）。唯一有意差異。"""
    raising = [(k, raw) for k, raw in CASES if _ui2_raises(k, raw)]
    assert raising, "預期至少有超大整數那幾案讓 ui_v2 拋 OverflowError"
    assert {_ui2_one(k, raw)[1] for k, raw in raising} == {"OverflowError"}
    for key, raw in raising:
        parsed = REAL.parse_settings({key: X.setting_row(key, raw)}, [])
        assert dict(parsed.statuses)[key] == REAL.SETTING_INVALID and parsed.values[NAME_OF[key]] is None and not parsed.usable
    assert len(raising) >= 1


def test_garbage_containers_are_unusable_not_unset():
    """列不是 mapping、rows 不是 mapping、broken_keys 型別不對：ui_v2 會崩潰；adapter 一律四鍵 invalid（絕不當成沒設定）。"""
    for rows in ("x", 5, [1], True):
        parsed = REAL.parse_settings(rows, [])
        assert not parsed.usable and {s for _k, s in parsed.statuses} == {REAL.SETTING_INVALID}
    for broken in ("alo_basis", 5, {"alo_basis": 1}, [["unhashable"]]):
        parsed = REAL.parse_settings({}, broken)
        assert not parsed.usable and {s for _k, s in parsed.statuses} == {REAL.SETTING_INVALID}
    parsed = REAL.parse_settings({"alo_basis": "成本"}, [])           # 非 mapping 的列
    assert dict(parsed.statuses)["alo_basis"] == REAL.SETTING_INVALID and not parsed.usable
    # 空 broken_keys／None 都是「沒有壞鍵」
    assert REAL.parse_settings({}, None).usable and REAL.parse_settings({}, ()).usable and REAL.parse_settings(None).usable


def test_scenario_input_key_is_not_an_evidence_input():
    """`alo_scenario_input` 不是證據輸入：它壞掉 ui_v2 整頁標問題，adapter 不看它（據實記錄的範圍差異）。"""
    rows = {"alo_scenario_input": X.setting_row("alo_scenario_input", "not json"), "alo_basis": X.setting_row("alo_basis", "成本")}
    _out, problem = _ui2(rows, [])
    parsed = REAL.parse_settings(rows, [])
    assert problem is not None and parsed.usable and parsed.values["basis"] == "成本"
    assert "alo_scenario_input" not in dict(parsed.statuses)


def test_inputs_are_not_mutated_and_result_has_four_keys_in_order():
    rows = X.settings_rows()
    import copy
    before = copy.deepcopy(rows)
    parsed = REAL.parse_settings(rows, ["x"])
    assert rows == before
    assert [k for k, _s in parsed.statuses] == ["alo_basis", "alo_target_weights", "alo_tolerance_pp", "alo_bucket_names"]
    assert set(parsed.values) == {"basis", "targets", "tolerance", "bucket_names"}


def test_known_good_values_round_trip_with_types():
    parsed = REAL.parse_settings(X.settings_rows(), [])
    assert parsed.usable and parsed.values == {
        "basis": "成本", "tolerance": 5.0, "bucket_names": ["core", "sat"],
        "targets": [{"bucket": "core", "weight_ratio": 0.75}, {"bucket": "sat", "weight_ratio": 0.25}]}
    assert type(parsed.values["tolerance"]) is float
    assert all(type(t["weight_ratio"]) is float for t in parsed.values["targets"])
    ints = REAL.parse_settings({"alo_target_weights": X.setting_row("alo_target_weights", '[{"bucket":"a","weight_ratio":1}]')}, [])
    assert type(ints.values["targets"][0]["weight_ratio"]) is float          # 1 → 1.0（ui_v2 同）
