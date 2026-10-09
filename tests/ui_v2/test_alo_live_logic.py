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


def test_只有尚未接上寫入的存檔停用並寫出原因_其餘不動():
    """2026-10-09 更正（舊名 `test_會寫user_setting的按鈕停用並寫出原因_其餘不動`）：
    舊版斷言「凡是 `_writes` 非空的按鈕一律停用」—— 那正是客戶 2026-10-09 裁示要改掉的行為
    （ALO-1／ALO-4 的存檔接上寫入）。現行：只有要寫的鍵不全在 `SAVE_WIRED_KEYS` 的那一枚停用，
    實質就是 ALO-3（`alo_scenario_input`，存檔仍未授權）。匯出、導覽、新增列三類的比對一字未改。"""
    demo = logic.build_page_model(fixtures.scenario("full"))
    model = _live_model("full")
    disabled = [b for b in _buttons(model) if not b["_enabled"]]
    assert [b["_keys"] for b in disabled] == [("alo_scenario_input",)], disabled
    assert disabled[0]["disabled_reason"] == live.SAVE_DISABLED_REASON
    for code in ("ALO-1", "ALO-4"):
        save = [b for b in logic.find_block(model, code)["buttons"] if b["_writes"]]
        assert len(save) == 1 and save[0]["_enabled"] is True, code
        assert save[0]["disabled_reason"] == "", code
    # 匯出、導覽、新增列三類一字未動（連標籤與停用原因都與示範模式相同）。
    same = [(b["label"], b["_enabled"], b["disabled_reason"])
            for b in _buttons(model) if not b["_writes"]]
    assert same == [(b["label"], b["_enabled"], b["disabled_reason"])
                    for b in _buttons(demo) if not b["_writes"]]


def test_沒有寫入函式時_三枚存檔照舊全部停用():
    """`page.render` 沒拿到 `save_live` 時傳 `wired_keys=()`：那時按了不會存，一律停用（與接寫入之前相同）。"""
    model = live.apply_live_notes(logic.build_page_model(fixtures.scenario("full")), wired_keys=())
    saves = [b for b in _buttons(model) if b["_writes"]]
    assert len(saves) == 3
    assert all(not b["_enabled"] and b["disabled_reason"] == live.SAVE_DISABLED_REASON for b in saves)


def test_停用判斷看按鈕的鍵_不看塊代碼():
    """fail-closed：一枚會寫的按鈕只要有一個鍵沒接上（或根本沒帶鍵）就停用。"""
    model = logic.build_page_model(fixtures.scenario("full"))
    alo1_save = logic.find_block(model, "ALO-1")["buttons"][0]
    alo1_save["_keys"] = ("alo_target_weights", "alo_scenario_input")
    alo4_save = [b for b in logic.find_block(model, "ALO-4")["buttons"] if b["_writes"]][0]
    alo4_save["_keys"] = ()
    out = live.apply_live_notes(model)
    for code in ("ALO-1", "ALO-4"):
        save = [b for b in logic.find_block(out, code)["buttons"] if b["_writes"]][0]
        assert save["_enabled"] is False and save["disabled_reason"] == live.SAVE_DISABLED_REASON, code


def test_停用原因逐字等於客戶核准的那一句():
    """客戶 2026-09-28 逐字核准（草稿 `docs/wireframes/draft_alo_save_disabled.html`，PR #861）。
    ⛔ 不准加字、不准補後半句 —— 客戶砍掉「按了不會存下任何東西」，理由是本頁根本沒有存這個動作。"""
    assert live.SAVE_DISABLED_REASON == "存檔寫入端尚未接上，這一輪只讀不寫"


def test_停用原因刻意不沿用mkt那一句_因為那一句在本頁是假的():
    """`ui_v2/mkt/page.py` 有 2 個 `on_click`（真的寫 `st.session_state`）⇒ mkt 那句字面正確；
    同一句在本頁的 ALO-3 是假的 —— 它的鍵 `alo_scenario_input` 在本頁沒有任何寫入路徑。
    2026-10-09 更正：舊版另斷言 `ui_v2/alo/page.py` 的 `on_click` 為 0、`source.py` 沒有 save 函式；
    ALO-1／ALO-4 接上寫入後兩者都不再成立（那正是本次裁示要改的行為）。本句現在只停用在 ALO-3 上，
    所以改釘「ALO-3 的鍵不在已接上的集合裡」—— 那才是這一句仍然為真的前提。"""
    mkt_live = pytest.importorskip("ui_v2.mkt.live")
    assert live.SAVE_DISABLED_REASON != mkt_live.SAVE_DISABLED_REASON
    for implies_saved in ("存了", "留不到", "下次開頁"):
        assert implies_saved not in live.SAVE_DISABLED_REASON, implies_saved
    assert "alo_scenario_input" not in live.SAVE_WIRED_KEYS
    assert set(live.SAVE_WIRED_KEYS) == {"alo_target_weights", "alo_tolerance_pp",
                                         "alo_basis", "alo_bucket_names"}


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
    assert names == {"__future__", "__future__.annotations", "copy", "json", "math", "re", ".", ".logic"}, names


# ═══════════════════════ ALO-GAP-分母全缺：總管 2026-09-28 盯住的那條界線 ═══════════════════════
#
# 「只在『每一檔都沒有基準值、而且缺的理由只有一種』時改畫 ⬜，其餘照舊 raise」——
# 下面四條把界線的兩邊都釘住：放行的那一種要放行，不放行的兩種要照舊炸。


def _mv(dataset):
    for row in dataset["user_setting"]:
        if row["setting_key"] == "alo_basis":
            row["setting_value"] = logic.BASIS_MV
    return dataset


def test_分母全缺_理由只有一種_改畫來源缺而不是炸掉():
    """接真資料時真正會走到的那一種：`nav` 在 L2 是 PENDING_TABLES ⇒ 每一檔都沒有基準值。"""
    dataset = _mv(fixtures.scenario("full"))
    dataset["nav"] = []
    block = logic.find_block(logic.build_page_model(dataset), "ALO-2")
    assert block["placeholder"]["text"] == logic.empty_source_text(["nav"])
    assert block["placeholder"]["_empty_kind"] == "來源缺"
    assert block["_rows"] == []


def test_分母全缺_理由不只一種_照舊raise():
    """一類缺 `nav`、一類缺匯率 —— `44` 沒有這種情形的畫法，不准自己編一句。"""
    dataset = _mv(fixtures.scenario("full"))
    dataset["market_indicator"] = []                                     # 美元那幾類缺匯率
    dataset["nav"] = [r for r in dataset["nav"] if r["fund_code"] not in ("BBBB", "DDDD")]
    values = logic._category_values(dataset, logic.BASIS_MV,
                                    logic.setting_value(dataset, "alo_bucket_names"))
    assert len({v["reason"] for v in values.values()}) == 2, "前提沒成立：這個資料集沒有兩種理由"
    with pytest.raises(ValueError, match="分母為零或負"):
        logic.build_page_model(dataset)


def test_有值卻加起來不為正_照舊raise():
    dataset = fixtures.scenario("full")                                   # 成本基準
    for holding in dataset["holding"]:
        holding["cost_twd"] = 0
    with pytest.raises(ValueError, match="分母為零或負"):
        logic.build_page_model(dataset)


def test_負控_市值基準但有台幣淨值時分母為正_根本不走那個分支():
    """這一條記的是一次探針失誤：`full` 只拿掉 `market_indicator` 並不會讓分母為 0 ——
    現金那一類的 DDDD 是台幣、淨值還在，分母 ＝ 50050。**拿它當「界線沒鬆」的證據是錯的。**"""
    dataset = _mv(fixtures.scenario("full"))
    dataset["market_indicator"] = []
    values = logic._category_values(dataset, logic.BASIS_MV,
                                    logic.setting_value(dataset, "alo_bucket_names"))
    assert sum(v["value"] for v in values.values() if v["value"] is not None) > 0
    assert logic.find_block(logic.build_page_model(dataset), "ALO-2")["_rows"]     # 照常出列


# ═══════════════════════ 存檔組值（ALO-1／ALO-4，客戶 2026-10-09 裁示）═══════════════════════
#
# 畫面上的當下字串 → 要寫的試算表字串；寫之前先丟回 `_PARSERS` 解析，解析不過不寫、訊息用解析器原文。
# ⛔ 不 strip、不補 0、不把非數字當 null（`CLAUDE.md` §1）。

_ALO1_KEYS = ("alo_target_weights", "alo_tolerance_pp")
_ALO4_KEYS = ("alo_basis", "alo_bucket_names")


def _alo1_values(rows, tolerance):
    out = {"alo_tolerance_pp": tolerance}
    for index, (bucket, weight) in enumerate(rows):
        out[f"alo_target_{index}_bucket"] = bucket
        out[f"alo_target_{index}_weight"] = weight
    return out


def _entries(keys, values, **kw):
    return {e["key"]: e for e in live.save_entries(keys, values, **kw)}


def test_組值_ALO1正常_順序同畫面列序_原字照寫():
    out = _entries(_ALO1_KEYS, _alo1_values([(_CORE, "0.60"), (_SAT, "0.4")], "4"))
    assert out["alo_target_weights"] == {
        "key": "alo_target_weights", "value_kind": "list", "error": None,
        "value": '[{"bucket": "%s", "weight_ratio": 0.60}, {"bucket": "%s", "weight_ratio": 0.4}]' % (_CORE, _SAT),
    }
    assert out["alo_tolerance_pp"] == {"key": "alo_tolerance_pp", "value": "4", "value_kind": "float",
                                       "error": None}
    # 寫出去的字串讀回來就是原值（與讀取端同一支解析器）。
    assert live._PARSERS["alo_target_weights"](out["alo_target_weights"]["value"], "k") == [
        {"bucket": _CORE, "weight_ratio": 0.6}, {"bucket": _SAT, "weight_ratio": 0.4}]


def test_組值_比重留空寫成null():
    out = _entries(_ALO1_KEYS, _alo1_values([(_CORE, "0.6"), (_SAT, "")], "4"))
    assert out["alo_target_weights"]["error"] is None
    assert json.loads(out["alo_target_weights"]["value"])[1] == {"bucket": _SAT, "weight_ratio": None}


@pytest.mark.parametrize("weight", ["六成", "nan", ".6", "0,6", "1e999"])
def test_組值_比重不是有限的數_不寫_訊息是解析器原文(weight):
    out = _entries(_ALO1_KEYS, _alo1_values([(_CORE, weight)], "4"))
    entry = out["alo_target_weights"]
    with pytest.raises(live.BadSettingValue) as caught:
        live._PARSERS["alo_target_weights"](entry["value"], "alo_target_weights")
    assert entry["error"] == str(caught.value)
    assert "weight_ratio 不是有限的數" in entry["error"]
    assert out["alo_tolerance_pp"]["error"] is None             # 另一鍵不受牽連


def test_組值_比重寫成60而不是0點6_不寫():
    entry = _entries(_ALO1_KEYS, _alo1_values([(_CORE, "60")], "4"))["alo_target_weights"]
    assert entry["error"] == "alo_target_weights 第 1 個元素的 weight_ratio 不在 0 到 1（60.0）"


@pytest.mark.parametrize("weight", [" 0.6", "0.6 ", "\t0.6"])
def test_組值_比重前後有空白_不strip_不寫(weight):
    entry = _entries(_ALO1_KEYS, _alo1_values([(_CORE, weight)], "4"))["alo_target_weights"]
    assert entry["error"] is not None and "不是有限的數" in entry["error"]
    assert json.dumps(weight) in entry["value"]                 # 原字照嵌，沒有被修掉


def test_組值_容許帶空字串寫None_前後空白不寫():
    assert _entries(_ALO1_KEYS, _alo1_values([], ""))["alo_tolerance_pp"]["value"] is None
    entry = _entries(_ALO1_KEYS, _alo1_values([], " 4"))["alo_tolerance_pp"]
    assert entry["value"] == " 4"
    assert entry["error"] == "alo_tolerance_pp 的值不是前後無空白的字串"
    entry = _entries(_ALO1_KEYS, _alo1_values([], "四"))["alo_tolerance_pp"]
    assert entry["error"] == "alo_tolerance_pp 的值不是數（alo_tolerance_pp）"


def test_組值_一列也沒有_寫None清除():
    entry = _entries(_ALO1_KEYS, _alo1_values([], "4"))["alo_target_weights"]
    assert entry["value"] is None and entry["error"] is None


def test_組值_ALO4_比重基準與類別名稱():
    values = {"alo_basis": logic.BASIS_MV, "alo_bucket_name_0": _CORE, "alo_bucket_name_1": _SAT}
    out = _entries(_ALO4_KEYS, values)
    assert out["alo_basis"] == {"key": "alo_basis", "value": logic.BASIS_MV, "value_kind": "list",
                                "error": None}
    assert out["alo_bucket_names"]["value"] == json.dumps([_CORE, _SAT], ensure_ascii=False)
    assert json.loads(out["alo_bucket_names"]["value"]) == [_CORE, _SAT]
    assert out["alo_bucket_names"]["value_kind"] == "list" and out["alo_bucket_names"]["error"] is None


def test_組值_ALO4_基準未選寫None_類別名稱空白不寫():
    out = _entries(_ALO4_KEYS, {"alo_basis": None, "alo_bucket_name_0": ""})
    assert out["alo_basis"]["value"] is None and out["alo_basis"]["error"] is None
    assert out["alo_bucket_names"]["error"] == "alo_bucket_names 第 1 個元素不是非空字串"


def test_組值_設定讀失敗時一律不寫():
    """讀不到真值時畫面上沒有可編的已存值；寫了就是拿空白蓋掉讀不到的真值。"""
    assert live.save_entries(_ALO1_KEYS, {}, settings_failed=True) == []
    assert live.save_entries(_ALO4_KEYS, {}, settings_failed=True) == []


def test_組值_沒接上的鍵當場炸():
    with pytest.raises(ValueError, match="尚未接上"):
        live.save_entries(("alo_scenario_input",), {})


# ═══════════════════════ 逐鍵寫入與記帳 ═══════════════════════


def test_寫入_一鍵成功一鍵失敗_不rollback_訊息原文():
    calls = []

    def save(key, value, kind):
        calls.append((key, value, kind))
        if key == "alo_tolerance_pp":
            return {"status": "failed", "key": key, "message": "HTTP 503（已遮蔽）"}
        return {"status": "saved", "key": key, "row": {}}

    entries = live.save_entries(_ALO1_KEYS, _alo1_values([(_CORE, "1")], "4"))
    results = live.run_saves(entries, save)
    assert results == {"alo_target_weights": None, "alo_tolerance_pp": "HTTP 503（已遮蔽）"}
    assert [c[0] for c in calls] == list(_ALO1_KEYS)
    assert calls[1] == ("alo_tolerance_pp", "4", "float")


def test_寫入_解析不過的鍵不呼叫寫入_另一鍵照寫():
    calls = []

    def save(key, value, kind):
        calls.append(key)
        return {"status": "saved", "key": key}

    entries = live.save_entries(_ALO1_KEYS, _alo1_values([(_CORE, "abc")], "4"))
    results = live.run_saves(entries, save)
    assert calls == ["alo_tolerance_pp"]
    assert "不是有限的數" in results["alo_target_weights"] and results["alo_tolerance_pp"] is None


@pytest.mark.parametrize("status", ["kind_mismatch", "kind_missing", "failed"])
def test_寫入_非saved一律記為失敗(status):
    results = live.run_saves(
        [{"key": "alo_basis", "value": logic.BASIS_COST, "value_kind": "list", "error": None}],
        lambda *a: {"status": status, "key": "alo_basis", "message": f"（{status} 原文）"},
    )
    assert results == {"alo_basis": f"（{status} 原文）"}


def test_寫入_寫入以外的例外照樣往上拋():
    def save(*args):
        raise RuntimeError("boom")

    entries = live.save_entries(_ALO4_KEYS, {"alo_basis": logic.BASIS_COST})
    with pytest.raises(RuntimeError, match="boom"):
        live.run_saves(entries, save)


def test_記帳_成功移除_失敗寫入_不改呼叫端那一份():
    before = {"alo_basis": "舊的失敗", "alo_tolerance_pp": "舊的"}
    after = live.merge_save_results(before, {"alo_basis": None, "alo_bucket_names": "新的失敗"})
    assert after == {"alo_tolerance_pp": "舊的", "alo_bucket_names": "新的失敗"}
    assert before == {"alo_basis": "舊的失敗", "alo_tolerance_pp": "舊的"}
    assert live.merge_save_results(None, {}) == {}


def test_併進save_errors_不改呼叫端那一份():
    dataset = fixtures.scenario("full")
    out = live.dataset_with_save_errors(dataset, {"alo_basis": "x"})
    assert out["save_errors"] == {"alo_basis": "x"} and dataset["save_errors"] == {}
    assert live.dataset_with_save_errors(dataset, None)["save_errors"] == {}
