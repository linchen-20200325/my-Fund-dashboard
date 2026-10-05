# -*- coding: utf-8 -*-
"""hld「讀取失敗不說空」（客戶 2026-10-05 核准開工）：讀不到不是空。純函式測試，不需要 streamlit。

- 設定讀取失敗（`errors["user_setting"]` 有值、`user_setting` 為空列表）→ 不說「尚未設定區間」「尚未設定門檻」
  「門檻一列也沒有」，印「⛔ 取數失敗：<原文>」（客戶 2026-10-05 裁示）。
- 持倉表讀取失敗（`errors["holding"]` 有值、`holding` 為空列表）→ 不說「尚未建立任何持倉」
  （燈不說：失敗不等於空，說了就是造假 —— 客戶 2026-09-28 核准，alo 草稿第 16 題）。
- 示範模式輸出不得改變；修法沿用既有字句（客戶 2026-10-05 裁示）。

資料形狀照正式模式：一律走 `live.build_live_model`；假資料去掉示意字樣，掛在 `DIRECT_POLICY_ID` 下的持倉改掛到既有保單
（同 `test_hld_live_logic.py::_scenario_args`）。本檔不 import `services`、`repositories`：常數一律用 AST 讀。
"""

import ast
import copy
import functools
import hashlib
import json
import pathlib
import sys
import uuid
from datetime import date

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from ui_v2.hld import fixtures, live, logic  # noqa: E402

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def _module_constant(rel, name):
    """用 AST 從原始檔讀出一個常數（本檔不 import 那些模組，也不另抄一份字面）。"""
    path = _REPO_ROOT / rel
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError(f"{name} 不在 {rel}")


_DIRECT_ID = _module_constant("services/v2_tables/contract.py", "DIRECT_POLICY_ID")
_L1 = "repositories/policy_supplement_repository.py"
_POLICY_TAB = _module_constant(_L1, "POLICY_TAB_SOURCE")
_SOURCES = frozenset({
    _POLICY_TAB,
    _module_constant(_L1, "TAB_POLICY_PROFILE"),
    _module_constant(_L1, "TAB_HOLDING_SUPPLEMENT"),
})
_REHOME_POLICY = "P-001"
_TODAY = date(2026, 10, 2)

# 兩個讀取失敗的原文是資料，不是字句。設定那一句由解析器實際產生（正式模式寫進 `errors["user_setting"]` 的路之一）。
_S = live.parse_user_settings({
    "hld_window_start": {
        "setting_key": "hld_window_start", "setting_value": "2026/06/01", "value_kind": "date", "updated_at": None,
    },
})[1]
_H = "ConnectionError: 持倉表讀取逾時（測試用原文）"
_FF_S = logic.fetch_failed_text(_S)
_FF_H = logic.fetch_failed_text(_H)

_UNSET_PHRASES = ("尚未設定區間", "尚未設定門檻", "門檻一列也沒有")
_EMPTY_PHRASES = (logic.TEXT_NO_HOLDING, "holding 尚無資料")
_APPLIED = {
    "applied_window": (fixtures.WINDOW_START, fixtures.WINDOW_END),
    "applied_rules": [{"indicator": "最大回撤", "direction": "低於", "value": -10.0}],
}


def _scrub(node):
    """拿掉假資料本身帶的「（示意）」（同 `test_hld_live_logic.py::_scrub`）。"""
    if isinstance(node, str):
        return node.replace(logic.HINT, "")
    if isinstance(node, dict):
        return {k: _scrub(v) for k, v in node.items()}
    if isinstance(node, list):
        return [_scrub(v) for v in node]
    if isinstance(node, tuple):
        return tuple(_scrub(v) for v in node)
    return node


def _rehome(dataset):
    for holding in dataset.get("holding") or ():
        if holding["policy_id"] == _DIRECT_ID:
            holding["policy_id"] = _REHOME_POLICY
    return dataset


def _prov(dataset):
    """L2 `build_nav_table` 的 `provenance` 形狀：淨值表裡每一檔一筆，全部即時取回。"""
    return {
        row["fund_code"]: {
            "source": "MoneyDJ:x",
            "fetched_at": "2026-09-19T02:00:00+00:00",
            "ccy_source": "holding",
            "cache_fallback": False,
            "stale": None,
        }
        for row in dataset.get("nav") or ()
    }


def _build(dataset, **kw):
    return live.build_live_model(
        dataset, direct_policy_id=_DIRECT_ID, nav_provenance=_prov(dataset), today=_TODAY, **kw
    )


def _full():
    """`full` 情境的正式形狀。"""
    return _scrub(_rehome(copy.deepcopy(fixtures.dataset_full())))


def _s1():
    """只有設定讀取失敗：`user_setting` 空列表、`errors["user_setting"]` 帶原文（呼叫端契約）。"""
    ds = _full()
    ds["user_setting"] = []
    ds["errors"] = {"user_setting": _S}
    return ds


def _s2():
    """只有持倉表讀取失敗。形狀照 `live.assemble_live_load` 持倉讀取失敗那一支：
    持倉、保單、淨值都是空列表，`errors["holding"]` 帶原文；配息與基金資料照 `pending_tables` 尚未接上。"""
    ds = _full()
    for table in ("holding", "policy", "nav", "dividend", "fund_profile"):
        ds[table] = []
    ds["errors"] = {"holding": _H}
    ds["pending_tables"] = ["fund_profile", "dividend"]
    return ds


def _s3():
    """兩者同時。"""
    ds = _s2()
    ds["user_setting"] = []
    ds["errors"] = {"holding": _H, "user_setting": _S}
    return ds


def _unset():
    """真的沒設定：讀得到、三列的值都是空；沒有 `errors["user_setting"]`。"""
    ds = _full()
    ds["user_setting"] = fixtures.user_settings()
    ds["errors"] = {}
    return ds


def _empty():
    """真的沒有持倉：讀得到、零列；沒有 `errors["holding"]`。"""
    ds = _full()
    for table in ("holding", "policy", "nav", "dividend", "fund_profile"):
        ds[table] = []
    ds["errors"] = {}
    return ds


def _strings(node):
    return logic.collect_ui_strings(node)


def _hits(node, phrases):
    return [s for s in _strings(node) if any(p in s for p in phrases)]


def _block(model, code):
    return logic.find_block(model, code)


# ═══════════ 裁示 1：設定讀取失敗顯示「⛔ 取數失敗：<原文>」 ═══════════


def test_T1正_設定讀取失敗_讀設定的五塊印出原文_HLD1同一句只寫一次():
    assert _S, "解析器沒有回問題訊息 —— 這一組會變成空掃"
    model = _build(_s1())
    for code in ("HLD-1", "HLD-2", "HLD-3", "HLD-4", "HLD-8"):
        assert _FF_S in _block(model, code)["detail_lines"], code
    assert _block(model, "HLD-4")["summary_text"] == _FF_S
    hld1 = _block(model, "HLD-1")
    placeholder = hld1["_placeholder"]
    assert (placeholder["_state"], placeholder["text"], placeholder["reason_text"]) == (
        logic.STATE_ERROR, logic.ERR_TEXT, _S)
    assert (hld1["_state"], hld1["summary_text"]) == (logic.STATE_ERROR, _FF_S)
    assert hld1["detail_lines"] == [_FF_S, logic.PRINT_AS_IS_LINE]


def test_T1反_真的沒設定_不印取數失敗_照舊說未設定():
    model = _build(_unset())
    assert [s for s in _strings(model) if "⛔" in s] == []
    assert _block(model, "HLD-1")["_placeholder"]["text"] == logic.NA_NO_RULES
    assert _block(model, "HLD-4")["summary_text"] == "尚未設定區間；門檻一列也沒有；存檔停用"


# ═══════════ 裁示 2：`BLOCK_SOURCE_TABLES` 加 `user_setting` ═══════════


def test_T2a正_三塊的來源表最後一張是user_setting_兩支都回設定的原文_持倉表排在設定前面():
    s1 = _s1()
    empty_s1 = _empty()
    empty_s1["user_setting"] = []
    empty_s1["errors"] = {"user_setting": _S}
    for code in ("HLD-1", "HLD-2", "HLD-3"):
        assert logic.BLOCK_SOURCE_TABLES[code][-1] == "user_setting", code
        assert logic.unsurfaced_source_error(s1, code) == _S, code
        assert logic.source_error(empty_s1, code) == _S, code
    s3 = _s3()
    assert [logic.source_error(s3, code) for code in ("HLD-1", "HLD-2", "HLD-3")] == [_H, _S, _H]


def test_T2a反_只動那三塊_逐值清單不動():
    assert set(logic.BLOCK_SOURCE_TABLES) == {"HLD-1", "HLD-2", "HLD-3"}
    assert logic._SURFACED_PER_VALUE == ("nav", "dividend")


# ═══════════ 裁示 2：HLD-4／5／8 不得畫成「未設定」 ═══════════


def test_T2b正_設定讀取失敗_HLD4_5_8沒有任何未設定字句():
    model = _build(_s1())
    for code in ("HLD-4", "HLD-5", "HLD-8"):
        assert _hits(_block(model, code), _UNSET_PHRASES) == [], code


def test_T2b反_真的沒設定_HLD5與HLD8照舊印尚未設定區間():
    model = _build(_unset())
    assert logic.NA_NO_WINDOW in _block(model, "HLD-5")["detail_lines"]
    hld8 = _block(model, "HLD-8")
    assert logic.NA_NO_WINDOW in hld8["detail_lines"]
    assert {row[key]["text"] for row in hld8["_rows"] for key in ("drawdown", "principal")} == {logic.NA_NO_WINDOW}


# ═══════════ 總管 2026-10-05 裁定：「未設定」字句全面拿掉（HLD-0／1／2／3／7 也一樣） ═══════════


def test_全面正_設定讀取失敗_全頁沒有任何未設定字句_核心卡主值全是取數失敗():
    model = _build(_s1())
    assert _hits(model, _UNSET_PHRASES) == []
    for code in ("HLD-2", "HLD-3"):
        texts = {mv["text"] for group in _block(model, code)["fund_groups"] for mv in group["main_values"]}
        assert texts == {logic.ERR_TEXT}, code


def test_全面反_真的沒設定_全頁照舊說未設定():
    model = _build(_unset())
    assert _hits(model, ("尚未設定區間",)) and _hits(model, ("尚未設定門檻",))


def test_HLD7_設定讀取失敗_每一列的輸出與所在那一塊上的字串相同():
    model = _build(_s1())
    rows = _block(model, "HLD-7")["_rows"]
    assert rows, "一列也沒有 —— 這一條會變成空掃"
    for row in rows:
        shown = logic.value_shown_in_block(model, row["_owner_code"], row["_fund_code"], row["_indicator"])
        assert row["output_text"] == shown, (row["_indicator"], row["_fund_code"])


# ═══════════ HLD-0：兩句補述 ═══════════


def test_HLD0正_設定讀取失敗_紅燈不補述尚未設定門檻():
    lamp = _block(_build(_s1()), "HLD-0")
    assert lamp["_tone"] == "紅"
    assert [line for line in lamp["lines"] if logic.TEXT_NO_RULES in line] == []


def test_HLD0反_真的沒設門檻又有取數失敗_補述照留():
    ds = _unset()
    ds["errors"] = {"dividend": "ConnectionError: 配息讀取逾時（測試用原文）"}
    lamp = _block(_build(ds), "HLD-0")
    assert lamp["_tone"] == "紅"
    assert f"（另：{logic.TEXT_NO_RULES}。門檻由你自己輸入，這一頁不提任何候選值）" in lamp["lines"]


# ═══════════ 裁示 2：示範模式輸出不得改變 ═══════════
# 期望值在改動前的程式（`a43dd54`）上產生，**不從被測程式現撈** —— 現撈等於拿被測物當期望值，這一條就恆真。

_APPLIED_STATES = (
    {},
    {
        "applied_window": (fixtures.WINDOW_START, fixtures.WINDOW_END),
        "applied_rules": [{"indicator": "最大回撤", "direction": "低於", "value": -5.0}],
    },
    {"applied_window": (None, None), "applied_rules": []},
)


def _digest(obj) -> str:
    """與 `test_hld_logic.py::_cell_digest` 同一套正規化：dict 鍵排序、set 轉排序後的 list、tuple 轉 list、
    非 JSON 型別取 `repr`。"""
    def scrub(value):
        if isinstance(value, dict):
            return {k: scrub(v) for k, v in sorted(value.items())}
        if isinstance(value, (list, tuple)):
            return [scrub(v) for v in value]
        if isinstance(value, set):
            return sorted(scrub(v) for v in value)
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        return repr(value)

    blob = json.dumps(scrub(obj), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]


def _demo_models(name):
    """示範模式：每一個展開狀態（不展開＋每一筆持倉）× 三種套用狀態 × 示意字樣開／關。"""
    args = fixtures.scenario(name)
    open_ids = [None] + [h["holding_id"] for h in args["dataset"].get("holding") or ()]
    return [
        logic.build_page_model(**copy.deepcopy(args), open_fund=open_id, demo_hint=hint, **applied)
        for open_id in open_ids
        for applied in _APPLIED_STATES
        for hint in (True, False)
    ]


def _live_models(name):
    """正式模式：去掉示意字樣、改掛保單之後，三種套用狀態。"""
    args = _scrub(copy.deepcopy(fixtures.scenario(name)))
    _rehome(args["dataset"])
    return [
        live.build_live_model(
            **copy.deepcopy(args), direct_policy_id=_DIRECT_ID, nav_provenance=_prov(args["dataset"]),
            today=_TODAY, **applied,
        )
        for applied in _APPLIED_STATES
    ]


# 情境名 → (示範模式那一組模型的摘要, 正式模式那一組模型的摘要)。
# 量測於改動前的 `a43dd54`（`logic.py` 與 `cfd0c97` 相同，兩者算出的值一致；換 `PYTHONHASHSEED` 重算不變）。
_BASELINE = {
    "full": ("ce1fa071388d", "480956eb73ea"),
    "srcmiss": ("98c3aa0a5846", "0557ba93e77b"),
    "bizexc": ("0bc089371169", "632657e86044"),
    "fetchfail": ("e7fe488a14e1", "0803dd5d4def"),
    "nothr": ("1b35a61c8e15", "4fd09632f697"),
    "empty": ("9fed2f3a1d0a", "de19a6aaee05"),
    "emptyfail": ("87d83bb69775", "3231755732ce"),
    "noexceed": ("7be62e779b20", "7a6b9977ea59"),
    "other_window": ("ec72c9f259f7", "a54793d3f167"),
    "onenav": ("dcc5c9a80f00", "fbf120f7d7a3"),
    "tiedstate": ("ade666d29a29", "83911f05520d"),
    "twofail": ("c85fc20996ce", "fdc3c45c05f8"),
    "holdfail": ("414bbcd0de89", "6294a2551be9"),
    "profilefail": ("6908d62183c9", "b28c4f76b50c"),
    "holdfail_nothr": ("6c1b14dcb142", "0a3e78075e81"),
    "badrange": ("4459ac6ba99a", "f31b5ac86e6e"),
    "full_then_badrange": ("9bef6d167a52", "f09a6e57d685"),
}


def test_T2c正_十七個情境_示範與正式模式共423個模型_與改動前相同():
    assert set(_BASELINE) == set(fixtures.ALL_SCENARIO_NAMES)
    count = 0
    for name in fixtures.ALL_SCENARIO_NAMES:
        demo, real = _demo_models(name), _live_models(name)
        count += len(demo) + len(real)
        assert (_digest(demo), _digest(real)) == _BASELINE[name], name
    assert count == 423, count


def test_T2c反_同一個情境注入設定讀取失敗_模型真的會變():
    args = copy.deepcopy(fixtures.scenario("full"))
    before = logic.build_page_model(**copy.deepcopy(args))
    args["dataset"]["user_setting"] = []
    args["dataset"]["errors"] = {"user_setting": _S}
    assert logic.build_page_model(**args) != before


# ═══════════ 裁示 2：呼叫端契約（總管 2026-10-05 裁定：`logic` 直接 raise） ═══════════


def test_T2d正_帶著設定列又帶著設定讀取失敗_raise_訊息照寫():
    ds = _s1()
    ds["user_setting"] = fixtures.user_settings(
        window=(fixtures.WINDOW_START, fixtures.WINDOW_END), rules=fixtures._RULES_DEFAULT
    )
    expected = f"errors 帶 user_setting 時，user_setting 必須是空列表，收到：{ds['user_setting']!r}"
    with pytest.raises(ValueError) as info:
        logic.build_page_model(copy.deepcopy(ds), demo_hint=False)
    assert str(info.value) == expected
    with pytest.raises(ValueError) as info:
        _build(ds)
    assert str(info.value) == expected


def test_T2d反_沒有讀取失敗_設定列照用():
    summary = _block(_build(_full()), "HLD-4")["summary_text"]
    assert summary.startswith(f"區間 {fixtures.WINDOW_START} 至 {fixtures.WINDOW_END}")


# ═══════════ 裁示 3：持倉表讀取失敗 —— 燈不說，全頁也不說「尚未建立任何持倉」 ═══════════


@pytest.mark.parametrize("make", (_s2, _s3), ids=("持倉讀取失敗", "兩者同時"))
def test_T3正_持倉讀取失敗_全頁不說空_四塊印出原文_HLD8不掛鈕(make):
    model = _build(make())
    assert _hits(model, _EMPTY_PHRASES) == []
    assert _hits(model, _UNSET_PHRASES) == []
    for code in ("HLD-1", "HLD-3", "HLD-5", "HLD-8"):
        assert _FF_H in _block(model, code)["detail_lines"], code
    for code in ("HLD-5", "HLD-8"):
        block = _block(model, code)
        assert (block["_state"], block["summary_text"]) == (logic.STATE_ERROR, _FF_H), code
    assert _block(model, "HLD-8")["buttons"] == []
    assert _block(model, "HLD-0")["_tone"] == "紅"


def test_T3正_持倉讀取失敗_HLD2照自己的來源欄畫灰_資料未備():
    hld2 = _block(_build(_s2()), "HLD-2")
    assert (hld2["_state"], hld2["_tone"], hld2["summary_text"]) == (logic.STATE_MISSING, "灰", logic.ND_TEXT)
    assert logic.ND_TEXT in hld2["detail_lines"]


def test_真的沒有持倉又設定讀取失敗_不說未設定_照說沒有持倉():
    ds = _empty()
    ds["user_setting"] = []
    ds["errors"] = {"user_setting": _S}
    model = _build(ds)
    assert _hits(model, _UNSET_PHRASES) == []
    lamp = _block(model, "HLD-0")
    assert lamp["_tone"] == "紅"
    assert f"（另：{logic.TEXT_NO_HOLDING}。{logic.TEXT_SHEETS_READONLY}）" in lamp["lines"]
    for code in ("HLD-1", "HLD-2", "HLD-3"):
        assert _block(model, code)["detail_lines"][:3] == [_FF_S, logic.PRINT_AS_IS_LINE, logic.TEXT_NO_HOLDING], code


def test_T3反_真的沒有持倉_照舊說():
    assert _block(_build(_empty()), "HLD-0")["text"] == logic.TEXT_NO_HOLDING
    ds = _empty()
    ds["errors"] = {"dividend": "ConnectionError: 配息讀取逾時（測試用原文）"}
    model = _build(ds)
    assert f"（另：{logic.TEXT_NO_HOLDING}。{logic.TEXT_SHEETS_READONLY}）" in _block(model, "HLD-0")["lines"]
    assert logic.TEXT_NO_HOLDING in _block(model, "HLD-3")["detail_lines"]
    assert _block(model, "HLD-2")["summary_text"] == logic.TEXT_NO_HOLDING
    assert _block(model, "HLD-5")["summary_text"] == logic.TEXT_NO_HOLDING
    assert _block(model, "HLD-8")["summary_text"] == f"{logic.ND_TEXT}：{logic.TEXT_NO_HOLDING}"


_PENDINGS = (
    frozenset(),
    frozenset({"dividend"}),
    frozenset({"fund_profile"}),
    frozenset({"nav", "dividend", "fund_profile"}),
)


@pytest.mark.parametrize("pending", _PENDINGS)
@pytest.mark.parametrize("rules", (True, False), ids=("有門檻", "沒有門檻"))
@pytest.mark.parametrize("window", (True, False), ids=("有區間", "沒有區間"))
def test_T3組合_持倉讀取失敗乘pending乘門檻乘區間_帶不帶direct清單都不說空(pending, rules, window):
    """接手 `test_hld_live_logic.py` 組合測試拿掉的 `holding` 那 16 組。"""
    ds = fixtures._dataset(
        holding=[],
        window=(fixtures.WINDOW_START, fixtures.WINDOW_END) if window else None,
        rules=fixtures._RULES_DEFAULT if rules else None,
        errors={"holding": _H},
    )
    if pending:
        ds["pending_tables"] = pending
    base = _build(copy.deepcopy(ds))
    rows = (3, 5, 9)
    with_direct = _build(
        ds,
        direct=[{"source": _POLICY_TAB, "tab": _DIRECT_ID, "row": row} for row in rows],
        policy_tab_source=_POLICY_TAB,
        direct_sources=_SOURCES,
    )
    for model in (base, with_direct):
        assert _hits(model, _EMPTY_PHRASES) == []
        assert _block(model, "HLD-5")["summary_text"] == _FF_H
    for b, g in zip(logic.all_blocks(base), logic.all_blocks(with_direct)):
        assert (g["_state"], g["_tone"]) == (b["_state"], b["_tone"]), g["code"]
    notes = _block(with_direct, "HLD-5")["tail_notes"]
    assert [note["text"] for note in notes] == [live.DIRECT_EXCLUDED_TEXT.format(n=len(rows))] + [
        live.DIRECT_LOCATION_TEXT.format(tab=_DIRECT_ID, row=row) for row in rows
    ]


# ═══════════ 裁示 4：修法沿用既有字句 ═══════════


@functools.lru_cache(maxsize=None)
def _known_strings():
    """改動前就出現過的字句：十七個情境、423 個模型的全部字串（這些模型不變由 T2c 守著）。"""
    known = set()
    for name in fixtures.ALL_SCENARIO_NAMES:
        for model in _demo_models(name) + _live_models(name):
            known.update(s for s in _strings(model) if isinstance(s, str))
    return frozenset(known)


def test_T4正_三種讀取失敗下的字句都是既有字句_只多了原文本身():
    known = _known_strings() | {_S, _H, _FF_S, _FF_H}
    new = set()
    for make in (_s1, _s2, _s3):
        new.update(s for s in _strings(_build(make())) if isinstance(s, str))
    assert sorted(new - known) == []


def test_T4反_掃描抓得到一句新字句():
    model = _build(_s1())
    fresh = "新字句-" + uuid.uuid4().hex
    _block(model, "HLD-4")["detail_lines"].append(fresh)
    known = _known_strings() | {_S, _H, _FF_S, _FF_H}
    assert sorted(set(_strings(model)) - known) == [fresh]


# ═══════════ 「未知」只在值取自存過的設定時成立；套用之後仍是紅（總管 2026-10-05 裁定） ═══════════


def test_套用正_設定讀取失敗後按套用_主值照套用的值算_三張卡仍是紅的():
    model = _build(_s1(), **_APPLIED)
    states = {mv["_state"] for g in _block(model, "HLD-2")["fund_groups"] for mv in g["main_values"]}
    assert states == {logic.STATE_OK}
    for code in ("HLD-1", "HLD-2", "HLD-3"):
        block = _block(model, code)
        assert block["_state"] == logic.STATE_ERROR, code
        assert _FF_S in block["detail_lines"], code
    assert _block(model, "HLD-1")["_rows"], "套用的門檻應算出偏離列"
    hld4 = _block(model, "HLD-4")
    assert _FF_S in hld4["detail_lines"]
    assert hld4["summary_text"] == f"區間 {fixtures.WINDOW_START} 至 {fixtures.WINDOW_END} · 門檻 1 列"


def test_套用反_沒按套用_HLD8兩欄全是取數失敗():
    hld8 = _block(_build(_s1()), "HLD-8")
    assert {row[key]["text"] for row in hld8["_rows"] for key in ("drawdown", "principal")} == {logic.ERR_TEXT}


# ═══════════ HLD-5（總管 2026-10-05 裁定：說明區同一個位置換成原文；折線區印原文） ═══════════


def test_HLD5正_設定讀取失敗_說明區最前面是原文_折線區印原文():
    hld5 = _block(_build(_s1()), "HLD-5")
    assert hld5["detail_lines"][:2] == [_FF_S, logic.PRINT_AS_IS_LINE]
    assert logic.NA_NO_WINDOW not in hld5["detail_lines"]
    assert hld5["_items"], "一檔也沒有 —— 這一條會變成空掃"
    assert {item["nav_plot_text"] for item in hld5["_items"]} == {_FF_S}


def test_HLD5反_真的沒設定_說明區最前面照舊_折線區照舊是來源缺():
    hld5 = _block(_build(_unset()), "HLD-5")
    assert hld5["detail_lines"][0] == logic.NA_NO_WINDOW
    assert {item["nav_plot_text"] for item in hld5["_items"]} == {logic.empty_source_text(["nav"])}


# ═══════════ 有持倉、持倉表部分讀取失敗、設定也讀取失敗（正式資料會出現的組合） ═══════════


def test_有持倉又有兩種讀取失敗_HLD1兩句原文都印_各一次():
    """部分分頁讀不到時持倉照交、`errors["holding"]` 帶原文（`live.assemble_live_load`）。"""
    ds = _full()
    ds["user_setting"] = []
    ds["errors"] = {"holding": _H, "user_setting": _S}
    hld1 = _block(_build(ds), "HLD-1")
    assert hld1["_state"] == logic.STATE_ERROR
    assert hld1["detail_lines"] == [_FF_S, logic.PRINT_AS_IS_LINE, _FF_H, logic.PRINT_AS_IS_LINE]
