# -*- coding: utf-8 -*-
"""持倉體檢正式模式呈現層（`ui_v2/hld/live.py`）的純函式測試。hld 接真資料 S3。

依據：客戶 2026-10-02 裁示（`docs/wireframes/draft_hld_live.html` §G 第 2 題 2-A、第 4 題 4-C）
與客戶 2026-10-02 裁示 A（「存檔」「重新取數」停用原因，逐字）。

本輪不接取數：正式模式的模型拿假資料的 dataset 跑。本檔不 import streamlit。
"""

import ast
import copy
import pathlib
import re
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from ui_v2.hld import fixtures, live, logic  # noqa: E402

_LIVE_PY = pathlib.Path(__file__).resolve().parents[2] / "ui_v2" / "hld" / "live.py"


def _scrub(node):
    """把假資料**本身**帶的「（示意）」拿掉（基金名、類別、保單名、錯誤訊息）。

    正式模式不讀 fixtures，那些字不會出現（草稿 §E P16）；這裡拿掉它們，
    好讓「模型裡一個（示意）都沒有」這件事只量得到**程式自己接上去的**字尾。
    """
    if isinstance(node, str):
        return node.replace(logic.HINT, "")
    if isinstance(node, dict):
        return {k: _scrub(v) for k, v in node.items()}
    if isinstance(node, list):
        return [_scrub(v) for v in node]
    if isinstance(node, tuple):
        return tuple(_scrub(v) for v in node)
    return node


def _scenario_args(name, *, scrub=True):
    args = copy.deepcopy(fixtures.scenario(name))
    return _scrub(args) if scrub else args


def _first_holding(dataset):
    holdings = dataset.get("holding") or []
    return holdings[0]["holding_id"] if holdings else None


def _live(name, **kw):
    return live.build_live_model(**_scenario_args(name), **kw)


def _demo(name, **kw):
    return logic.build_page_model(**_scenario_args(name), **kw)


_ALL = fixtures.ALL_SCENARIO_NAMES


# ───────────────────────── 1. 示意字樣（裁示 2-A） ─────────────────────────


@pytest.mark.parametrize("name", _ALL)
def test_正式模式_全頁模型沒有任何一個示意字樣(name):
    args = _scenario_args(name)
    model = live.build_live_model(**args, open_fund=_first_holding(args["dataset"]))
    hits = [s for s in logic.collect_ui_strings(model) if "示意" in s]
    assert hits == []


@pytest.mark.parametrize("name", _ALL)
def test_示範模式_同一份去字資料_照舊帶示意字樣(name):
    """正控：上一條若只是因為資料裡沒有示意字樣才過，這一條會紅。
    空持倉的情境畫面上沒有任何一個數字，本來就沒有字尾可接 —— 那幾個只驗「沒有」。"""
    args = _scenario_args(name)
    if not args["dataset"].get("holding"):
        pytest.skip("空持倉：畫面上沒有數字，示範模式本來就沒有字尾")
    model = logic.build_page_model(**args, open_fund=_first_holding(args["dataset"]))
    assert any(logic.HINT in s for s in logic.collect_ui_strings(model))


def test_HLD1收合摘要_寫死的那一處示意字面_正式模式也拿掉():
    """草稿 §E P7：「N 列（示意）」原本寫死、沒有走 HINT，只把 HINT 改空會漏。"""
    live_hld1 = logic.find_block(_live("full"), "HLD-1")
    demo_hld1 = logic.find_block(_demo("full"), "HLD-1")
    n = len(demo_hld1["_rows"])
    assert n > 0
    assert demo_hld1["summary_text"] == f"{n} 列（示意）"
    assert live_hld1["summary_text"] == f"{n} 列"


def test_示範模式_demo_hint預設為真_與明傳True逐字相同():
    args = _scenario_args("full", scrub=False)
    assert logic.build_page_model(**args) == logic.build_page_model(**copy.deepcopy(args), demo_hint=True)


def test_正式模式組完之後_示範模式不被污染():
    """開關住在 ContextVar；`build_page_model` 結束一定要還原，否則下一個示範模式的呼叫會少字。"""
    _live("full")
    assert logic._hint() == logic.HINT
    # 不拿「組正式模式之前」那一份當基準：前面任何一條測試若已污染，前後兩份會一樣地少字而照樣相等。
    assert logic.find_block(_demo("full"), "HLD-1")["summary_text"].endswith(logic.HINT)


def test_組模型中途炸掉_開關照樣還原():
    bad = _scenario_args("full")
    bad["dataset"]["holding"].append(dict(bad["dataset"]["holding"][0]))  # holding_id 重複 → raise
    with pytest.raises(Exception):
        logic.build_page_model(**bad, demo_hint=False)
    assert logic._hint() == logic.HINT
    assert logic.find_block(_demo("full"), "HLD-1")["summary_text"].endswith(logic.HINT)


@pytest.mark.parametrize("name", _ALL)
def test_正式模式只差三件事_其餘逐字與示範模式相同(name):
    """示範模型 → 去示意字尾 → 改欄名 → 停用兩類按鈕，必須恰好等於正式模型。
    正式模式若多改了任何一格（新增按鈕、改了別的字），這一條會紅。"""
    args = _scenario_args(name)
    open_fund = _first_holding(args["dataset"])
    demo = logic.build_page_model(**copy.deepcopy(args), open_fund=open_fund)
    expected = live.apply_live_notes(_scrub(demo))
    got = live.build_live_model(**args, open_fund=open_fund)
    assert got == expected


# ───────────────────────── 2. 最後核對日（裁示 4-C） ─────────────────────────


def _hld5_fields(model):
    return [item["_fields"] for item in logic.find_block(model, "HLD-5")["_items"]]


def test_正式模式_HLD5欄名改為最後核對日只記日期_值只有日期():
    args = _scenario_args("full")
    holdings = {h["holding_id"]: h for h in args["dataset"]["holding"]}
    block = logic.find_block(live.build_live_model(**args), "HLD-5")
    assert block["_items"]
    for item in block["_items"]:
        labels = [label for label, _ in item["_fields"]]
        assert "最後核對日（只記日期）" in labels
        assert "最後對帳" not in labels
        value = dict(item["_fields"])["最後核對日（只記日期）"]
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)
        assert value == holdings[item["_holding_id"]]["last_synced_at"][:10]


def test_正式模式_欄位順序不變_只換那一格的名字():
    demo = [[label for label, _ in f] for f in _hld5_fields(_demo("full"))]
    got = [[label for label, _ in f] for f in _hld5_fields(_live("full"))]
    assert got == [
        ["最後核對日（只記日期）" if label == "最後對帳" else label for label in row] for row in demo
    ]


def test_示範模式_HLD5欄名照舊是最後對帳():
    """草稿 §G 第 4 題只裁正式版；假資料版沒寫 ⇒ 不動。"""
    for fields in _hld5_fields(_demo("full")):
        labels = [label for label, _ in fields]
        assert "最後對帳" in labels
        assert "最後核對日（只記日期）" not in labels


@pytest.mark.parametrize("bad", ["2026-09-1", "2026-13-01", "2026/09/15", "", None, "2026-09-15T"])
def test_最後核對日不是日期_寧可炸掉(bad):
    with pytest.raises(ValueError):
        live._date_only(bad)


def test_最後核對日是日期_原樣照印():
    assert live._date_only("2026-09-15") == "2026-09-15"


def test_last_synced_at壞掉時_正式模式炸掉不照印():
    args = _scenario_args("full")
    args["dataset"]["holding"][0]["last_synced_at"] = "九月十五日中午十二點"
    with pytest.raises(ValueError):
        live.build_live_model(**args)


# ───────────────────────── 3. 按鈕（裁示 A） ─────────────────────────


def test_停用原因逐字照裁示A():
    assert live.SAVE_DISABLED_REASON == "存檔寫入端尚未接上，這一輪只讀不寫"
    assert live.REFETCH_DISABLED_REASON == "重新取數尚未接上"


def test_存檔停用原因_與alo頁逐字相同():
    from ui_v2.alo import live as alo_live

    assert live.SAVE_DISABLED_REASON == alo_live.SAVE_DISABLED_REASON


def test_停用原因沒有指示動作的句子():
    for reason in (live.SAVE_DISABLED_REASON, live.REFETCH_DISABLED_REASON):
        assert "請" not in reason


def _buttons_by_block(model):
    return {
        block["code"]: [b for b in logic.collect_buttons(block)] for block in logic.all_blocks(model)
    }


@pytest.mark.parametrize("name", _ALL)
def test_存檔一律停用_原因逐字(name):
    saves = [b for b in logic.collect_buttons(_live(name)) if b["_action_kind"] == "存檔"]
    assert len(saves) == 1
    assert saves[0]["label"] == "存檔"
    assert saves[0]["_enabled"] is False
    assert saves[0]["_visible"] is True
    assert saves[0]["disabled_reason"] == live.SAVE_DISABLED_REASON


@pytest.mark.parametrize("name", _ALL)
def test_重新取數一律停用_原因逐字(name):
    for button in logic.collect_buttons(_live(name)):
        if button["_action_kind"] == "取數":
            assert button["label"] == "重新取數"
            assert button["_enabled"] is False
            assert button["_visible"] is True
            assert button["disabled_reason"] == live.REFETCH_DISABLED_REASON


def test_重新取數有出現的情境_確實停用了():
    """正控：上一條在沒有任何一枚重新取數的情境下會空轉過關；這裡釘住至少一個情境真的有。"""
    found = [
        name for name in _ALL
        if any(b["_action_kind"] == "取數" for b in logic.collect_buttons(_live(name)))
    ]
    assert "srcmiss" in found and "fetchfail" in found


@pytest.mark.parametrize("name", _ALL)
def test_按鈕出現在哪幾塊_正式與示範一枚不差(name):
    demo = _buttons_by_block(_demo(name))
    got = _buttons_by_block(_live(name))
    assert {k: [b["label"] for b in v] for k, v in got.items()} == {
        k: [b["label"] for b in v] for k, v in demo.items()
    }


@pytest.mark.parametrize("name", _ALL)
def test_HLD1到3不掛重新取數_HLD8依值狀態掛(name):
    model = _live(name)
    for code in ("HLD-1", "HLD-2", "HLD-3"):
        assert not [
            b for b in logic.collect_buttons(logic.find_block(model, code)) if b["_action_kind"] == "取數"
        ]
    hld8 = logic.find_block(model, "HLD-8")
    states = [
        row[key]["_state"] for row in hld8.get("_rows", []) for key in ("drawdown", "principal")
    ]
    has_retry = any(b["_action_kind"] == "取數" for b in logic.collect_buttons(hld8))
    assert has_retry == any(s in (logic.STATE_MISSING, logic.STATE_ERROR) for s in states)


@pytest.mark.parametrize("name", _ALL)
def test_其他類按鈕的啟用狀態_一格不動(name):
    demo = logic.collect_buttons(_demo(name))
    got = logic.collect_buttons(_live(name))
    assert len(demo) == len(got)
    for d, g in zip(demo, got):
        assert d["_action_kind"] == g["_action_kind"]
        if g["_action_kind"] not in ("存檔", "取數"):
            assert (g["_enabled"], g["disabled_reason"]) == (d["_enabled"], d["disabled_reason"])


def test_apply_live_notes不改呼叫端那一份():
    model = logic.build_page_model(**_scenario_args("srcmiss"), demo_hint=False)
    snapshot = copy.deepcopy(model)
    live.apply_live_notes(model)
    assert model == snapshot


# ───────────────────────── 4. 全頁守衛 ─────────────────────────


_BANNED = ("一鍵", "最佳", "推薦", "最適", "買進", "賣出", "加碼", "減碼")


@pytest.mark.parametrize("name", _ALL)
def test_正式模式全頁_禁詞零命中(name):
    strings = logic.collect_ui_strings(_live(name))
    assert logic.scan_forbidden(strings) == {}
    assert [s for s in strings if any(w in s for w in _BANNED)] == []


@pytest.mark.parametrize("name", _ALL)
def test_正式模式全頁_狀態徽章只用那七個字(name):
    for badge in logic.collect_badges(_live(name)):
        if badge["_kind"] == "狀態":
            assert badge["text"] in logic.STATUS_BADGE_LITERALS


@pytest.mark.parametrize("name", _ALL)
def test_正式模式全頁_識別碼零命中(name):
    strings = logic.collect_ui_strings(_live(name))
    assert [s for s in strings if re.search(r"session_[0-9A-Za-z]{16,}|claude\.ai/code", s)] == []


def test_live模組不import_streamlit_也不import_fixtures():
    tree = ast.parse(_LIVE_PY.read_text(encoding="utf-8"))
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names += [f"{node.module or ''}.{a.name}" for a in node.names]
    assert not [n for n in names if "streamlit" in n or "fixtures" in n]
