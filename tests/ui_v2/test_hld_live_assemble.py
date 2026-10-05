# -*- coding: utf-8 -*-
"""hld 正式模式：L2 輸出 → `load_live` 回傳值的組裝（S6b-2 第二塊）。純函式測試，不需要 streamlit。

被測：`ui_v2/hld/live.py::assemble_live_load`。它把 L2 的輸出（持倉三表、設定、代碼對照、淨值表）
組成 `ui_v2/hld/page.py::render(load_live=)` 要的 `{"dataset", "live_args"}`。本輪不建 `source.py`、不接取數。

⚠️ 本檔不 import `services`，唯一例外是 `contract`（T8 要呼叫三個列契約檢查）。
   L2／L1 的常數（空來源訊息、扣下原因代碼、`DIRECT` 字面……）一律用 AST 從原始檔讀，
   不另抄一份字面；讀不到就紅，不退回寫死。
⚠️ 「測試內現編」的值（標記字串、自訂訊息）一律在執行期產生，不寫成固定字面。
"""

import ast
import copy
import inspect
import json
import pathlib
import sys
import uuid
from datetime import date

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from services.v2_tables import contract  # noqa: E402  只為 T8，不 import 其他 services
from ui_v2.hld import fixtures, live, logic  # noqa: E402

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_LIVE_PY = _REPO_ROOT / "ui_v2" / "hld" / "live.py"


def _module_constant(rel, name):
    """用 AST 從舊樹原始檔讀出一個常數（本檔不 import 舊樹，也不另抄一份字面）。"""
    path = _REPO_ROOT / rel
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError(f"{name} 不在 {rel}")


# ───────────────────────── L2／L1 的常數（AST 讀；讀不到就紅） ─────────────────────────

_V2 = "services/v2_tables/"
_ND = _V2 + "nav_dividend.py"
_L1 = "repositories/policy_supplement_repository.py"

_DIRECT_ID = _module_constant(_V2 + "contract.py", "DIRECT_POLICY_ID")
# 來源字面取自 L1（⚠️ 不從 `alo_holdings.py` 讀：那裡是 `repo.xxx` 轉指派，AST 讀不到）。
_POLICY_TAB = _module_constant(_L1, "POLICY_TAB_SOURCE")
_TAB_PROFILE = _module_constant(_L1, "TAB_POLICY_PROFILE")
_TAB_SUPPLEMENT = _module_constant(_L1, "TAB_HOLDING_SUPPLEMENT")
_SOURCES = {_POLICY_TAB, _TAB_PROFILE, _TAB_SUPPLEMENT}
# ⚠️ 不從 `nav_dividend.py` 讀：那裡是 import 進來的。
_EMPTY = _module_constant(_V2 + "market_indicator.py", "EMPTY_WITHOUT_REASON")
_DIV_VERIFIED = _module_constant(_ND, "DIV_DATE_IS_EX_DATE_VERIFIED")
_TYPE_ERROR_PREFIX = _module_constant(_ND, "TYPE_ERROR_PREFIX")
_W_CCY_MISSING = _module_constant(_ND, "WITHHELD_CCY_MISSING")
_W_CCY_CONFLICT = _module_constant(_ND, "WITHHELD_CCY_CONFLICT")
_W_AT_MISSING = _module_constant(_ND, "WITHHELD_FETCHED_AT_MISSING")
_W_AT_FUTURE = _module_constant(_ND, "WITHHELD_FETCHED_AT_FUTURE")
_W_INPUT_CONFLICT = _module_constant(_ND, "WITHHELD_INPUT_CONFLICT")
_NAV_UNAVAILABLE = (_W_CCY_MISSING, _W_CCY_CONFLICT, _W_AT_MISSING, _W_AT_FUTURE, _W_INPUT_CONFLICT)
_PENDING_TABLES = _module_constant(_V2 + "settings_store.py", "PENDING_TABLES")

# 整串比對用：本檔掃 `live.py` 的字串常數時，這些值一個都不能出現（T2a）。
_L2_STRINGS = {
    "DIRECT_POLICY_ID": _DIRECT_ID,
    "POLICY_TAB_SOURCE": _POLICY_TAB,
    "TAB_POLICY_PROFILE": _TAB_PROFILE,
    "TAB_HOLDING_SUPPLEMENT": _TAB_SUPPLEMENT,
    "EMPTY_WITHOUT_REASON": _EMPTY,
    "TYPE_ERROR_PREFIX": _TYPE_ERROR_PREFIX,
    "WITHHELD_CCY_MISSING": _W_CCY_MISSING,
    "WITHHELD_CCY_CONFLICT": _W_CCY_CONFLICT,
    "WITHHELD_FETCHED_AT_MISSING": _W_AT_MISSING,
    "WITHHELD_FETCHED_AT_FUTURE": _W_AT_FUTURE,
    "WITHHELD_INPUT_CONFLICT": _W_INPUT_CONFLICT,
}


# ───────────────────────── 假輸入：L2／L1 的回傳形狀 ─────────────────────────

_TODAY = date(2026, 10, 2)
_WINDOW = (fixtures.WINDOW_START, fixtures.WINDOW_END)
_UPDATED_AT = "2026-10-01T09:00:00+08:00"
_RULES = [
    {"indicator": "最大回撤", "direction": "低於", "value": -10.0},
    {"indicator": "配息佔淨值比", "direction": "高於", "value": 6.0},
]
# 假資料裡掛在 DIRECT 下的持倉改掛到這張既有保單（L2 不為 DIRECT 產生 `holding` 列，
# 正式模式拿到 DIRECT 持倉會 raise；同 `test_hld_live_logic.py` 的 `_REHOME_POLICY`）。
_REHOME_POLICY = "P-001"
# full 情境只在 import 時算一次；用到時一律 deepcopy。
_FULL = fixtures.scenario("full")["dataset"]
_CODES = tuple(sorted(h["fund_code"] for h in _FULL["holding"]))
_OK_CODE, _MID_CODE, _BAD_CODE = _CODES   # 健康檔、另一檔、被測的那一檔
# 持倉裡沒有的代碼（執行期現編，不寫成固定字面）。
_STRAY_CODE = "ZZ" + uuid.uuid4().hex[:6].upper()


def _l2_holding_tables(*, direct=()):
    """L2 `load_alo_tables` 回傳形狀（只放本檔用到的三個鍵）。
    policy 濾掉 DIRECT 的列（L2 不產生 DIRECT 的 policy 列）；DIRECT 持倉改掛既有保單。"""
    holding = copy.deepcopy(_FULL["holding"])
    for row in holding:
        if row["policy_id"] == _DIRECT_ID:
            row["policy_id"] = _REHOME_POLICY
    policy = [copy.deepcopy(p) for p in _FULL["policy"] if p["policy_id"] != _DIRECT_ID]
    return {"holding": holding, "policy": policy, "direct": list(direct)}


def _l2_direct():
    """L2 `direct` 清單三種來源的形狀（同 `test_hld_live_logic.py::_l2_direct`）。"""
    return [
        {"source": _TAB_PROFILE, "tab": _TAB_PROFILE, "row": 7, "policy_id": _DIRECT_ID},
        {"source": _TAB_SUPPLEMENT, "tab": _TAB_SUPPLEMENT, "row": 31, "policy_id": _DIRECT_ID},
        {"source": _POLICY_TAB, "tab": "DIRECT", "row": 3, "policy_id": _DIRECT_ID,
         "fund_code": "J1", "fund_name": "J"},
        {"source": _POLICY_TAB, "tab": "DIRECT", "row": 5, "policy_id": _DIRECT_ID,
         "fund_code": "K1", "fund_name": "K"},
    ]


def _key_results(holdings, *, fail=None):
    """L1 `resolve_full_keys(...)["results"]` 的形狀：與持倉同序、同長度，重複代碼各自一筆。
    `fail`：`{代碼: 錯誤文字}`，列在裡面的代碼 `ok` 為 False。"""
    fail = fail or {}
    out = []
    for row in holdings:
        code = row["fund_code"]
        bad = code in fail
        out.append({
            "input": code,
            "ok": not bad,
            "full_key": None if bad else "FK-" + code,
            "portal": None if bad else "",
            "parsed_code": None if bad else code,
            "mapping_hit": not bad,
            "error": fail[code] if bad else None,
        })
    return out


def _prov_entry(*, fallback=False, stale=None):
    """L2 `build_nav_table` 的 `provenance[code]` 形狀。"""
    return {
        "source": "GitHubActions:cache/nav/x" if fallback else "MoneyDJ:x",
        "fetched_at": "2026-09-19T02:00:00+00:00",
        "ccy_source": "holding",
        "cache_fallback": fallback,
        "stale": stale if fallback else None,
    }


def _empty_nav_table():
    return {"rows": [], "errors": {}, "withheld": {}, "skipped": {}, "fetched": {},
            "skipped_rows": {}, "provenance": {}}


def _nav_table(*, healthy=_CODES, failed=None, empty=(), withheld=None, rows_override=None):
    """L2 `build_nav_table` 的回傳形狀（七個鍵，除 `rows` 外皆以 fund_code 為鍵）。

    - `healthy`：取得淨值的檔（有列、有 fetched、有 provenance）；`rows_override` 可換掉某檔的列；
    - `failed`：`{代碼: L1 失敗原文}`；`empty`：來源回空的檔（訊息是 `EMPTY_WITHOUT_REASON`）。
      兩者都沒有列、`fetched` 為 0、沒有 provenance；
    - `withheld`：`{代碼: 原因代碼}`，整檔不寫列。`input_conflict` 沒有呼叫 L1，所以沒有
      `fetched`／`skipped_rows`／`provenance`（L2 `build_nav_table` 的 docstring 寫明）；其餘四種都有。
    """
    all_rows = _FULL["nav"]
    table = _empty_nav_table()
    for code in healthy:
        rows = copy.deepcopy((rows_override or {}).get(code, [r for r in all_rows if r["fund_code"] == code]))
        table["rows"].extend(rows)
        table["fetched"][code] = len(rows)
        table["skipped_rows"][code] = 0
        table["provenance"][code] = _prov_entry()
    for code, message in (failed or {}).items():
        table["errors"][code] = message
        table["fetched"][code] = 0
        table["skipped_rows"][code] = 0
    for code in empty:
        table["errors"][code] = _EMPTY
        table["fetched"][code] = 0
        table["skipped_rows"][code] = 0
    for code, reason in (withheld or {}).items():
        table["withheld"][code] = reason
        table["skipped"][code] = [reason + "：整檔不寫列"]
        if reason != _W_INPUT_CONFLICT:
            n = sum(1 for r in all_rows if r["fund_code"] == code)
            table["fetched"][code] = n
            table["skipped_rows"][code] = n
            table["provenance"][code] = _prov_entry()
    return table


def _settings(*, window=_WINDOW, rules=_RULES, broken=()):
    """L1 `load_user_settings()` 的形狀：`rows` 是 `{鍵: 列}`，`setting_value` 一律是 L1 讀回來的原字串。"""
    def row(key, value, kind):
        return {"setting_key": key, "setting_value": value, "value_kind": kind, "updated_at": _UPDATED_AT}

    start, end = window if window else (None, None)
    return {
        "rows": {
            "hld_window_start": row("hld_window_start", start, "date"),
            "hld_window_end": row("hld_window_end", end, "date"),
            "hld_deviation_rules": row(
                "hld_deviation_rules", json.dumps(rules, ensure_ascii=False) if rules is not None else None, "rules"
            ),
        },
        "broken_keys": set(broken),
    }


def _native_user_setting(*, window=_WINDOW, rules=_RULES):
    """`_settings` 解析後 `logic` 吃的原生值（手寫，不經 `parse_user_settings`）。"""
    start, end = window if window else (None, None)

    def row(key, value, kind):
        return {"setting_key": key, "setting_value": value, "value_kind": kind, "updated_at": _UPDATED_AT}

    return [
        row("hld_window_start", start, "date"),
        row("hld_window_end", end, "date"),
        row("hld_deviation_rules", [dict(r) for r in rules] if rules is not None else None, "rules"),
    ]


def _identity_mask(text):
    return text


def _kwargs(**over):
    """`assemble_live_load` 的一組合格輸入（全部走快樂路徑）；`over` 蓋掉其中幾個。"""
    tables = _l2_holding_tables()
    kw = dict(
        holding_tables=tables,
        holding_error=None,
        settings=_settings(),
        settings_error=None,
        key_results=_key_results(tables["holding"]),
        nav_table=_nav_table(),
        direct_policy_id=_DIRECT_ID,
        policy_tab_source=_POLICY_TAB,
        direct_sources=_SOURCES,
        empty_without_reason=_EMPTY,
        nav_unavailable_withheld=_NAV_UNAVAILABLE,
        dividend_gate_open=False,
        mask=_identity_mask,
    )
    kw.update(over)
    return kw


def _assemble(**over):
    return live.assemble_live_load(**_kwargs(**over))


def _build_model(loaded, *, window=_WINDOW):
    """`ui_v2/hld/page.py::render` 正式模式呼叫 `live.build_live_model` 的形狀（`**loaded["live_args"]`），
    另帶固定的 `today`，結果不隨時鐘變。"""
    return live.build_live_model(
        loaded["dataset"],
        open_fund=None,
        fields=None,
        applied_window=window,
        applied_rules=None,
        today=_TODAY,
        **loaded["live_args"],
    )


def _strings(model):
    return logic.collect_ui_strings(model)


def _hld2_texts(model, code):
    group = logic.fund_group(logic.find_block(model, "HLD-2"), code)
    return [mv["text"] for mv in group["main_values"]]


def _hld8_drawdown_text(model, code):
    return logic.find_row(logic.find_block(model, "HLD-8"), code)["drawdown"]["text"]


def _assert_nav_unavailable(model, code):
    """T5a 的主值斷言：該檔 HLD-2 兩個主值與 HLD-8 最大回撤都是「⬜ 資料未備」。"""
    assert _hld2_texts(model, code) == [logic.ND_TEXT, logic.ND_TEXT]
    assert _hld8_drawdown_text(model, code) == logic.ND_TEXT


def _raises(kw, exc_type, message):
    with pytest.raises(Exception) as info:
        live.assemble_live_load(**kw)
    assert type(info.value) is exc_type, (type(info.value), info.value)
    assert str(info.value) == message


def _unique(prefix):
    return prefix + "-" + uuid.uuid4().hex


# ───────────────────────── 六種輸入情形（T1a、T7c 共用） ─────────────────────────

_CASE_NAMES = ("快樂路徑", "持倉讀取失敗", "設定讀取失敗", "設定解析失敗", "持倉零列", "有DIRECT清單")


def _case_kwargs(name):
    if name == "快樂路徑":
        return _kwargs()
    if name == "持倉讀取失敗":
        return _kwargs(holding_tables=None, holding_error=_unique("持倉讀取失敗"), key_results=None, nav_table=None)
    if name == "設定讀取失敗":
        return _kwargs(settings=None, settings_error=_unique("設定讀取失敗"))
    if name == "設定解析失敗":
        return _kwargs(settings=_settings(window=("2026-02-30", fixtures.WINDOW_END)))
    if name == "持倉零列":
        return _kwargs(
            holding_tables={"holding": [], "policy": [], "direct": []}, key_results=[], nav_table=_empty_nav_table()
        )
    if name == "有DIRECT清單":
        tables = _l2_holding_tables(direct=_l2_direct())
        return _kwargs(holding_tables=tables, key_results=_key_results(tables["holding"]))
    raise AssertionError(name)


# ═════════════════════════ T0　簽名：全部 keyword-only、順序照規定、沒有預設值 ═════════════════════════


def test_T0_簽名_全部keyword_only_參數順序照規定_沒有預設值():
    params = list(inspect.signature(live.assemble_live_load).parameters.values())
    assert [p.name for p in params] == [
        "holding_tables", "holding_error", "settings", "settings_error",
        "key_results", "nav_table",
        "direct_policy_id", "policy_tab_source", "direct_sources",
        "empty_without_reason", "nav_unavailable_withheld", "dividend_gate_open", "mask",
    ]
    assert all(p.kind is inspect.Parameter.KEYWORD_ONLY for p in params)
    assert all(p.default is inspect.Parameter.empty for p in params)


# ═════════════════════════ T1　純函式：同輸入同輸出、不改輸入、不讀時鐘、不新增 import ═════════════════════════


@pytest.mark.parametrize("name", _CASE_NAMES)
def test_T1a_同一份輸入呼叫兩次_輸出相等_而且不改輸入(name):
    kw = _case_kwargs(name)
    before = copy.deepcopy(kw)
    first, second = copy.deepcopy(kw), copy.deepcopy(kw)
    out_first = live.assemble_live_load(**first)
    out_second = live.assemble_live_load(**second)
    assert out_first == out_second
    assert first == before
    assert second == before


def test_T1b_不讀時鐘_taiwan_today被換成一呼叫就raise的函式_照常回傳(monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("assemble_live_load 不得讀時鐘")

    monkeypatch.setattr(live, "taiwan_today", boom)
    out = _assemble()
    assert list(out) == ["dataset", "live_args"]


def test_T1c_live_py的import恰為既有七行_沒有新增任何模組():
    tree = ast.parse(_LIVE_PY.read_text(encoding="utf-8"))
    found = sorted(ast.unparse(n) for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom)))
    assert found == sorted([
        "from __future__ import annotations",
        "import copy",
        "import json",
        "import math",
        "import re",
        "from datetime import date, datetime, timedelta, timezone",
        "from . import logic",
    ])


# ═════════════════════════ T2　L2 的常數一律由參數交進來，本檔不寫字面 ═════════════════════════


def _string_literals(source):
    return [n.value for n in ast.walk(ast.parse(source)) if isinstance(n, ast.Constant) and isinstance(n.value, str)]


def test_T2a_live_py的字串常數沒有任何一個整串等於L2或L1的常數值():
    literals = _string_literals(_LIVE_PY.read_text(encoding="utf-8"))
    assert len(literals) > 100, len(literals)   # 空掃防呆（量測日 2026-10-05，改動前為 326）
    assert {name: value for name, value in _L2_STRINGS.items() if value in literals} == {}


def test_T2a_正控_掃描方法抓得到整串相等的字串():
    """負控的另一面：同一支掃描遇到「整串相等」就會報，不是掃不到東西。"""
    for name, value in _L2_STRINGS.items():
        assert value in _string_literals(f"x = {value!r}\n"), name
    # 只是「包含」不算整串相等：掃描不得因此誤報。
    assert _EMPTY not in _string_literals(f"x = {(_EMPTY + '。')!r}\n")


def test_T2b_empty_without_reason由參數決定_不是寫死在live_py裡():
    injected = _unique("自訂")
    assert injected != _EMPTY
    out = _assemble(
        empty_without_reason=injected,
        nav_table=_nav_table(healthy=(_OK_CODE, _MID_CODE), empty=(_BAD_CODE,)),   # 錯誤原文是真的 EMPTY 字串
    )
    assert out["dataset"]["fund_errors"] == {"nav": {_BAD_CODE: _EMPTY}}


def test_T2c_扣下原因以參數為準_清單只放ccy_conflict時_ccy_missing照樣raise():
    kw = _kwargs(
        nav_unavailable_withheld=(_W_CCY_CONFLICT,),
        nav_table=_nav_table(healthy=(_OK_CODE, _MID_CODE), withheld={_BAD_CODE: _W_CCY_MISSING}),
    )
    _raises(kw, ValueError, f"淨值扣下原因 {_W_CCY_MISSING!r} 不在本頁約定的清單內：{_BAD_CODE!r}")


# ═════════════════════════ T3　pending_tables 固定、配息閘門 ═════════════════════════


def test_T3a_配息閘門是關的_pending_tables固定為fund_profile與dividend():
    # 前提：L2 的 `DIV_DATE_IS_EX_DATE_VERIFIED` 目前是 False。哪天它翻成 True，這一條先紅 ——
    # 表示配息怎麼組要重新規定，不是把這一條改過去。
    assert _DIV_VERIFIED is False
    out = _assemble(dividend_gate_open=_DIV_VERIFIED)
    assert out["dataset"]["pending_tables"] == ["fund_profile", "dividend"]
    assert out["dataset"]["dividend"] == []
    assert out["dataset"]["fund_profile"] == []


@pytest.mark.parametrize("name", ("持倉讀取失敗", "持倉零列"))
def test_T3b_持倉讀取失敗或持倉零列_pending_tables一樣固定(name):
    out = live.assemble_live_load(**_case_kwargs(name))
    assert out["dataset"]["pending_tables"] == ["fund_profile", "dividend"]


@pytest.mark.parametrize("name", _CASE_NAMES)
def test_T3c_pending_tables不含nav_淨值已經接上(name):
    assert "nav" in _PENDING_TABLES   # L2 的清單還含 nav；本頁的清單不含，是因為本輪把 nav 接上了
    out = live.assemble_live_load(**_case_kwargs(name))
    assert "nav" not in out["dataset"]["pending_tables"]


def test_T3d_配息閘門已打開_raise():
    _raises(_kwargs(dividend_gate_open=True), ValueError, "配息閘門已打開，本頁尚未規定配息怎麼組")


def test_T3e_端到端_淨值只留區間起點之後的列_兩個主值都是資料未備_HLD1寫出fund_profile缺():
    later = [r for r in _FULL["nav"] if r["fund_code"] == _MID_CODE and r["nav_date"] > "2026-03-01"]
    first_kept = min(r["nav_date"] for r in later)
    assert first_kept > _WINDOW[0]   # 最早一筆晚於區間起點
    loaded = _assemble(nav_table=_nav_table(rows_override={_MID_CODE: later}))
    model = _build_model(loaded)
    assert _hld2_texts(model, _MID_CODE) == [logic.ND_TEXT, logic.ND_TEXT]
    hld1 = logic.find_block(model, "HLD-1")
    assert logic.empty_source_text(["fund_profile"]) in hld1["detail_lines"]
    # 其他兩檔的列都從區間起點之前就有，不受影響：主值不是資料未備。
    for code in (_OK_CODE, _BAD_CODE):
        assert logic.ND_TEXT not in _hld2_texts(model, code)


def test_T3f_端到端_配息表尚未接上_HLD3每檔主值都是資料未備_不是區間內無配息():
    model = _build_model(_assemble())
    groups = logic.find_block(model, "HLD-3")["fund_groups"]
    assert len(groups) == len(_CODES)
    for group in groups:
        assert [mv["text"] for mv in group["main_values"]] == [logic.ND_TEXT, logic.ND_TEXT], group["_fund_code"]
    assert not [s for s in _strings(model) if "區間內無配息" in s]


# ═════════════════════════ T4　取數失敗：只有真的失敗才進 fund_errors，而且只遮放進去的那一筆 ═════════════════════════


def test_T4a_某檔取數失敗_fund_errors放遮蔽後的原文_端到端全頁印出同一句且不含原文():
    secret = _unique("秘密")
    raw = f"ConnectionError: token={secret}"

    def mask(text):
        return text.replace(secret, "***")

    out = _assemble(nav_table=_nav_table(healthy=(_OK_CODE, _MID_CODE), failed={_BAD_CODE: raw}), mask=mask)
    assert out["dataset"]["fund_errors"] == {"nav": {_BAD_CODE: mask(raw)}}
    strings = _strings(_build_model(out))
    assert logic.fund_fetch_failed_text(_BAD_CODE, mask(raw)) in strings
    assert not [s for s in strings if secret in s]


def test_T4b_一般連線錯誤原文_進fund_errors():
    out = _assemble(nav_table=_nav_table(healthy=(_OK_CODE, _MID_CODE), failed={_BAD_CODE: "ConnectionError: boom"}))
    assert out["dataset"]["fund_errors"] == {"nav": {_BAD_CODE: "ConnectionError: boom"}}


def test_T4c_L1回傳型別不符_照樣進fund_errors_不raise():
    message = _TYPE_ERROR_PREFIX + "：預期 pd.Series，收到 NoneType"
    out = _assemble(nav_table=_nav_table(healthy=(_OK_CODE, _MID_CODE), failed={_BAD_CODE: message}))
    assert out["dataset"]["fund_errors"] == {"nav": {_BAD_CODE: message}}


def test_T4d_來源回空_訊息恰為EMPTY_而且沒取到任何列_不放進fund_errors():
    out = _assemble(nav_table=_nav_table(healthy=(_OK_CODE, _MID_CODE), empty=(_BAD_CODE,)))
    assert out["dataset"]["fund_errors"] == {}


@pytest.mark.parametrize("kind", ("扣下", "代碼對照失敗"))
def test_T4e_被扣下的檔與代碼對照失敗的檔_都不在fund_errors(kind):
    if kind == "扣下":
        kw = _kwargs(nav_table=_nav_table(healthy=(_OK_CODE, _MID_CODE), withheld={_BAD_CODE: _W_CCY_CONFLICT}))
    else:
        tables = _l2_holding_tables()
        kw = _kwargs(
            holding_tables=tables,
            key_results=_key_results(tables["holding"], fail={_BAD_CODE: _unique("對照失敗")}),
            nav_table=_nav_table(healthy=(_OK_CODE, _MID_CODE)),
        )
    assert live.assemble_live_load(**kw)["dataset"]["fund_errors"] == {}


def test_T4f_訊息恰為EMPTY_可是fetched不是0_就不是回空_進fund_errors():
    table = _nav_table(healthy=(_OK_CODE, _MID_CODE), empty=(_BAD_CODE,))
    table["fetched"][_BAD_CODE] = 3
    out = _assemble(nav_table=table)
    assert out["dataset"]["fund_errors"] == {"nav": {_BAD_CODE: _EMPTY}}


def test_T4g_持倉讀取失敗_fund_errors是空的():
    out = live.assemble_live_load(**_case_kwargs("持倉讀取失敗"))
    assert out["dataset"]["fund_errors"] == {}


def test_T4h_mask只套在放進fund_errors的那一筆_其餘的錯誤訊息不再遮():
    marker = _unique("標記")

    def wrapped(text):
        return marker + text + marker

    originals = {_MID_CODE: _unique("ConnectionError"), _BAD_CODE: _unique("Timeout")}
    out = _assemble(nav_table=_nav_table(healthy=(_OK_CODE,), failed=originals), mask=wrapped)
    assert out["dataset"]["fund_errors"] == {"nav": {code: marker + text + marker for code, text in originals.items()}}

    # 呼叫端傳進來的兩則（持倉、設定讀取失敗）本來就已遮蔽，本函式不再遮。
    holding_error, settings_error = _unique("持倉讀取失敗"), _unique("設定讀取失敗")
    out = _assemble(
        holding_tables=None, holding_error=holding_error, key_results=None, nav_table=None,
        settings=None, settings_error=settings_error, mask=wrapped,
    )
    assert out["dataset"]["errors"] == {"holding": holding_error, "user_setting": settings_error}
    # 設定解析失敗的訊息是本檔自己（`parse_user_settings`）寫的，也不在 `mask` 的射程內。
    out = _assemble(settings=_settings(window=("2026-02-30", fixtures.WINDOW_END)), mask=wrapped)
    assert marker not in out["dataset"]["errors"]["user_setting"]


def test_T4i_判斷用原文_遮蔽只影響放進去的那一筆():
    # 遮蔽函式加了標記：訊息原文恰為 EMPTY，照樣是回空（不能拿遮蔽後的字串去比）。
    marker = _unique("標記")
    out = _assemble(
        nav_table=_nav_table(healthy=(_OK_CODE, _MID_CODE), empty=(_BAD_CODE,)),
        mask=lambda text: marker + text,
    )
    assert out["dataset"]["fund_errors"] == {}
    # 反過來：遮蔽函式把真的失敗原文換成 EMPTY 字串，它仍然是失敗（原文不等於 EMPTY）。
    out = _assemble(
        nav_table=_nav_table(healthy=(_OK_CODE, _MID_CODE), failed={_BAD_CODE: "ConnectionError: boom"}),
        mask=lambda text: _EMPTY,
    )
    assert out["dataset"]["fund_errors"] == {"nav": {_BAD_CODE: _EMPTY}}


# ═════════════════════════ T5　被扣下、代碼對照失敗、來源回空：一律只是「沒有淨值列、也不在 fund_errors」 ═════════════════════════


def test_T5a_端到端_ccy_conflict_三個值都是資料未備_全頁沒有原因代碼():
    loaded = _assemble(nav_table=_nav_table(healthy=(_OK_CODE, _MID_CODE), withheld={_BAD_CODE: _W_CCY_CONFLICT}))
    model = _build_model(loaded)
    _assert_nav_unavailable(model, _BAD_CODE)
    assert not [s for s in _strings(model) if _W_CCY_CONFLICT in s]


def test_T5b_端到端_代碼對照失敗_三個值都是資料未備_全頁沒有那段錯誤文字():
    reason = _unique("對照失敗原因")
    tables = _l2_holding_tables()
    loaded = _assemble(
        holding_tables=tables,
        key_results=_key_results(tables["holding"], fail={_BAD_CODE: reason}),
        nav_table=_nav_table(healthy=(_OK_CODE, _MID_CODE)),
    )
    model = _build_model(loaded)
    _assert_nav_unavailable(model, _BAD_CODE)
    assert not [s for s in _strings(model) if reason in s]


def test_T5c_端到端_來源回空_三個值都是資料未備_全頁沒有那句回空訊息():
    loaded = _assemble(nav_table=_nav_table(healthy=(_OK_CODE, _MID_CODE), empty=(_BAD_CODE,)))
    model = _build_model(loaded)
    _assert_nav_unavailable(model, _BAD_CODE)
    assert not [s for s in _strings(model) if _EMPTY in s]


def _hand_written_model(omit_code):
    """手寫的 dataset：同樣的持倉、同樣的設定，只有 `omit_code` 那一檔沒有淨值列、也不在 `fund_errors`。"""
    tables = _l2_holding_tables()
    others = [c for c in _CODES if c != omit_code]
    dataset = {
        "holding": tables["holding"],
        "nav": [r for r in copy.deepcopy(_FULL["nav"]) if r["fund_code"] != omit_code],
        "dividend": [],
        "policy": tables["policy"],
        "fund_profile": [],
        "user_setting": _native_user_setting(),
        "errors": {},
        "pending_tables": ["fund_profile", "dividend"],
        "fund_errors": {},
    }
    return live.build_live_model(
        dataset,
        open_fund=None,
        fields=None,
        applied_window=_WINDOW,
        applied_rules=None,
        today=_TODAY,
        direct_policy_id=_DIRECT_ID,
        direct=[],
        policy_tab_source=_POLICY_TAB,
        direct_sources=_SOURCES,
        nav_provenance={code: _prov_entry() for code in others},
    )


def _loaded_without_nav(kind, *, code=_BAD_CODE, reason=_W_CCY_CONFLICT, **over):
    """同一檔的三種沒有淨值：被扣下、代碼對照失敗、來源回空。其餘各檔都取得淨值。"""
    others = tuple(c for c in _CODES if c != code)
    if kind == "被扣下":
        return _assemble(nav_table=_nav_table(healthy=others, withheld={code: reason}), **over)
    if kind == "代碼對照失敗":
        tables = _l2_holding_tables()
        results = _key_results(tables["holding"], fail={code: _unique("對照失敗原因")})
        return _assemble(holding_tables=tables, key_results=results, nav_table=_nav_table(healthy=others), **over)
    if kind == "來源回空":
        return _assemble(nav_table=_nav_table(healthy=others, empty=(code,)), **over)
    raise AssertionError(kind)


@pytest.mark.parametrize("kind", ("被扣下", "代碼對照失敗", "來源回空"))
def test_T5d_三種沒有淨值的組裝結果_與手寫的沒淨值dataset算出同一份模型(kind):
    assert _build_model(_loaded_without_nav(kind)) == _hand_written_model(_BAD_CODE)


@pytest.mark.parametrize("reason", _NAV_UNAVAILABLE)
def test_T5d_五種扣下原因各自的組裝結果_也與手寫的沒淨值dataset算出同一份模型(reason):
    loaded = _assemble(nav_table=_nav_table(healthy=(_OK_CODE, _MID_CODE), withheld={_BAD_CODE: reason}))
    assert _build_model(loaded) == _hand_written_model(_BAD_CODE)


def test_T5e_同一檔改成真的取數失敗_全頁印出取數失敗_而且不是資料未備():
    loaded = _assemble(
        nav_table=_nav_table(healthy=(_OK_CODE, _MID_CODE), failed={_BAD_CODE: "ConnectionError: boom"})
    )
    model = _build_model(loaded)
    assert [s for s in _strings(model) if "⛔ 取數失敗" in s]
    assert logic.ND_TEXT not in _hld2_texts(model, _BAD_CODE)


@pytest.mark.parametrize("reason", _NAV_UNAVAILABLE)
def test_T5f_五個扣下原因各一_三個值都是資料未備(reason):
    loaded = _assemble(nav_table=_nav_table(healthy=(_OK_CODE, _MID_CODE), withheld={_BAD_CODE: reason}))
    model = _build_model(loaded)
    _assert_nav_unavailable(model, _BAD_CODE)
    assert not [s for s in _strings(model) if reason in s]


def test_T5g_扣下原因不在五碼內_raise():
    stray = _unique("not_a_known_reason")
    assert stray not in _NAV_UNAVAILABLE
    kw = _kwargs(nav_table=_nav_table(healthy=(_OK_CODE, _MID_CODE), withheld={_BAD_CODE: stray}))
    _raises(kw, ValueError, f"淨值扣下原因 {stray!r} 不在本頁約定的清單內：{_BAD_CODE!r}")


@pytest.mark.parametrize("kind", ("被扣下", "代碼對照失敗", "來源回空"))
def test_T5h_未設區間時_沒有淨值的那一檔與健康檔的兩個主值逐字相同(kind):
    loaded = _loaded_without_nav(kind, settings=_settings(window=None, rules=None))
    model = _build_model(loaded, window=None)
    healthy_texts = _hld2_texts(model, _OK_CODE)
    assert len(healthy_texts) == 2
    assert _hld2_texts(model, _BAD_CODE) == healthy_texts


# ═════════════════════════ T7　形狀、鍵序、各種輸入都能交給 build_live_model、錯誤與一致性檢查 ═════════════════════════

_DATASET_KEYS = ["holding", "nav", "dividend", "policy", "fund_profile", "user_setting", "errors",
                 "pending_tables", "fund_errors"]
_LIVE_ARGS_KEYS = ["direct_policy_id", "direct", "policy_tab_source", "direct_sources", "nav_provenance"]


def test_T7a_回傳值的鍵與鍵序逐一照規定():
    out = _assemble()
    assert list(out) == ["dataset", "live_args"]
    assert list(out["dataset"]) == _DATASET_KEYS
    assert list(out["live_args"]) == _LIVE_ARGS_KEYS


def test_T7b_live_args不含頁面自己帶的參數():
    out = _assemble()
    for name in ("open_fund", "fields", "applied_window", "applied_rules", "today"):
        assert name not in out["live_args"], name
        assert name not in out["dataset"], name


@pytest.mark.parametrize("name", _CASE_NAMES)
def test_T7c_每一種輸入組出來的回傳值_都能照page_py的呼叫形狀交給build_live_model_不raise(name):
    loaded = live.assemble_live_load(**_case_kwargs(name))
    model = _build_model(loaded)
    assert isinstance(model, dict) and model["blocks"]


def test_T7c_有DIRECT清單時_live_args把direct原樣帶給build_live_model():
    kw = _case_kwargs("有DIRECT清單")
    out = live.assemble_live_load(**kw)
    assert out["live_args"]["direct"] == _l2_direct()
    assert out["live_args"]["policy_tab_source"] == _POLICY_TAB
    assert out["live_args"]["direct_sources"] == _SOURCES
    assert out["live_args"]["direct_policy_id"] == _DIRECT_ID
    # holding 裡沒有 DIRECT 列（L2 不產生）；本頁用 `direct` 清單另列。
    assert all(r["policy_id"] != _DIRECT_ID for r in out["dataset"]["holding"])


def test_T7d_設定解析失敗_交空列表_訊息與parse_user_settings給的逐字相同():
    settings = _settings(window=("2026-02-30", fixtures.WINDOW_END))
    out = _assemble(settings=settings)
    problem = live.parse_user_settings(settings["rows"], settings["broken_keys"])[1]
    assert problem is not None
    assert out["dataset"]["user_setting"] == []
    assert out["dataset"]["errors"] == {"user_setting": problem}
    # 另一種：鍵在 broken_keys 裡（L1 讀不出那一列）。
    broken = _settings(broken=("hld_window_end",))
    out = _assemble(settings=broken)
    problem = live.parse_user_settings(broken["rows"], broken["broken_keys"])[1]
    assert problem is not None
    assert out["dataset"]["user_setting"] == []
    assert out["dataset"]["errors"] == {"user_setting": problem}


def test_T7d_設定正常_交解析後的三列_errors沒有user_setting():
    out = _assemble()
    assert out["dataset"]["user_setting"] == _native_user_setting()
    assert out["dataset"]["errors"] == {}


def test_T7d_設定讀取失敗_交空列表_錯誤訊息原樣放進errors():
    message = _unique("設定讀取失敗")
    out = _assemble(settings=None, settings_error=message)
    assert out["dataset"]["user_setting"] == []
    assert out["dataset"]["errors"] == {"user_setting": message}


def test_T7e_持倉讀取失敗_四張表都是空的_direct與provenance也是空的():
    holding_error = _unique("持倉讀取失敗")
    out = _assemble(holding_tables=None, holding_error=holding_error, key_results=None, nav_table=None)
    dataset = out["dataset"]
    assert dataset["holding"] == [] and dataset["policy"] == [] and dataset["nav"] == [] and dataset["dividend"] == []
    assert out["live_args"]["direct"] == []
    assert out["live_args"]["nav_provenance"] == {}
    assert dataset["errors"] == {"holding": holding_error}


def test_T7f_有被扣下的檔_nav_provenance等於傳入的provenance_含被扣下那一檔():
    table = _nav_table(healthy=(_OK_CODE, _MID_CODE), withheld={_BAD_CODE: _W_CCY_CONFLICT})
    assert _BAD_CODE in table["provenance"]
    out = _assemble(nav_table=table)
    assert out["live_args"]["nav_provenance"] == table["provenance"]
    assert _BAD_CODE in out["live_args"]["nav_provenance"]
    assert out["live_args"]["nav_provenance"] is not table["provenance"]   # 複本：之後怎麼改都碰不到 L2 的那一份


def test_T7f_input_conflict沒有呼叫L1_沒有fetched與provenance_照樣組得出來():
    table = _nav_table(healthy=(_OK_CODE, _MID_CODE), withheld={_BAD_CODE: _W_INPUT_CONFLICT})
    assert _BAD_CODE not in table["fetched"] and _BAD_CODE not in table["provenance"]
    out = _assemble(nav_table=table)
    assert _BAD_CODE not in out["live_args"]["nav_provenance"]
    _assert_nav_unavailable(_build_model(out), _BAD_CODE)


def test_T7f_同一檔基金掛在兩張保單下_key_results有重複代碼_照樣組得出來():
    tables = _l2_holding_tables()
    extra = copy.deepcopy(tables["holding"][0])
    extra["holding_id"] = extra["holding_id"] + "-2"
    extra["policy_id"] = "P-002"
    tables["holding"].append(extra)
    results = _key_results(tables["holding"])
    assert [r["input"] for r in results].count(extra["fund_code"]) == 2   # 重複輸入各自一筆（L1 的規定）
    out = _assemble(holding_tables=tables, key_results=results)
    assert [r["fund_code"] for r in out["dataset"]["holding"]].count(extra["fund_code"]) == 2
    assert _build_model(out)["blocks"]


def test_T7f_key_results給tuple也行():
    tables = _l2_holding_tables()
    out = _assemble(holding_tables=tables, key_results=tuple(_key_results(tables["holding"])))
    assert out["dataset"]["holding"]


_PARAM_CASES = [
    # (編號與情形, 蓋掉的輸入, 例外型別, 訊息)
    ("R1 兩個都給", dict(holding_error="x"), ValueError, "holding_tables 與 holding_error 要恰好給一個"),
    ("R1 兩個都沒給", dict(holding_tables=None, key_results=None, nav_table=None),
     ValueError, "holding_tables 與 holding_error 要恰好給一個"),
    ("R2 兩個都給", dict(settings_error="x"), ValueError, "settings 與 settings_error 要恰好給一個"),
    ("R2 兩個都沒給", dict(settings=None), ValueError, "settings 與 settings_error 要恰好給一個"),
    ("R3 holding_error 不是字串", dict(holding_tables=None, holding_error=123, key_results=None, nav_table=None),
     TypeError, "holding_error 應為字串：123"),
    ("R3 holding_error 是空白", dict(holding_tables=None, holding_error="  ", key_results=None, nav_table=None),
     ValueError, "holding_error 是空字串：'  '"),
    ("R3 settings_error 不是字串", dict(settings=None, settings_error=["x"]),
     TypeError, "settings_error 應為字串：['x']"),
    ("R3 settings_error 是空字串", dict(settings=None, settings_error=""),
     ValueError, "settings_error 是空字串：''"),
    ("R4 持倉失敗卻給 key_results", dict(holding_tables=None, holding_error="x", nav_table=None),
     ValueError, "持倉表讀取失敗時，key_results、nav_table 一律不得給"),
    ("R4 持倉失敗卻給 nav_table", dict(holding_tables=None, holding_error="x", key_results=None),
     ValueError, "持倉表讀取失敗時，key_results、nav_table 一律不得給"),
    ("R5 持倉成功卻沒給 key_results", dict(key_results=None),
     ValueError, "持倉表讀取成功時，key_results、nav_table 一律要給"),
    ("R5 持倉成功卻沒給 nav_table", dict(nav_table=None),
     ValueError, "持倉表讀取成功時，key_results、nav_table 一律要給"),
    ("R6 dividend_gate_open 是 0", dict(dividend_gate_open=0), TypeError, "dividend_gate_open 應為 bool：0"),
    ("R6 dividend_gate_open 是 None", dict(dividend_gate_open=None),
     TypeError, "dividend_gate_open 應為 bool：None"),
    ("R7 empty_without_reason 不是字串", dict(empty_without_reason=None),
     TypeError, "empty_without_reason 應為字串：None"),
    ("R7 empty_without_reason 是空白", dict(empty_without_reason=" "),
     ValueError, "empty_without_reason 是空字串：' '"),
    ("R8 nav_unavailable_withheld 是字串", dict(nav_unavailable_withheld="ccy_conflict"),
     TypeError, "nav_unavailable_withheld 應為集合：str"),
    ("R8 nav_unavailable_withheld 是 bytes", dict(nav_unavailable_withheld=b"x"),
     TypeError, "nav_unavailable_withheld 應為集合：bytes"),
    ("R8 nav_unavailable_withheld 是 dict", dict(nav_unavailable_withheld={"a": 1}),
     TypeError, "nav_unavailable_withheld 應為集合：dict"),
    ("R8 nav_unavailable_withheld 是 None", dict(nav_unavailable_withheld=None),
     TypeError, "nav_unavailable_withheld 應為集合：NoneType"),
    ("R8 元素不是字串", dict(nav_unavailable_withheld=("ccy_missing", 5)),
     TypeError, "nav_unavailable_withheld 的元素 應為字串：5"),
    ("R8 元素是空字串", dict(nav_unavailable_withheld=("ccy_missing", "")),
     ValueError, "nav_unavailable_withheld 的元素 是空字串：''"),
    ("R12 mask 是字串", dict(mask="x"), TypeError, "mask 應為可呼叫：str"),
    ("R12 mask 是 None", dict(mask=None), TypeError, "mask 應為可呼叫：NoneType"),
    ("R9 配息閘門已打開", dict(dividend_gate_open=True), ValueError, "配息閘門已打開，本頁尚未規定配息怎麼組"),
]


@pytest.mark.parametrize("over, exc_type, message", [c[1:] for c in _PARAM_CASES], ids=[c[0] for c in _PARAM_CASES])
def test_T7g_參數檢查_例外型別與訊息逐字(over, exc_type, message):
    _raises(_kwargs(**over), exc_type, message)


def test_T7g_參數都合格時不raise_list_tuple_set_frozenset都收_空清單也行():
    for collection in (list(_NAV_UNAVAILABLE), tuple(_NAV_UNAVAILABLE), set(_NAV_UNAVAILABLE),
                       frozenset(_NAV_UNAVAILABLE), ()):
        out = _assemble(nav_unavailable_withheld=collection)
        assert list(out) == ["dataset", "live_args"]


_ORDER_CASES = [
    # 同時違反兩條時，先報表裡排前面的那一條。
    ("R1 先於 R2", dict(holding_error="x", settings_error="x"), "holding_tables 與 holding_error 要恰好給一個"),
    ("R2 先於 R3",
     dict(holding_tables=None, holding_error="", key_results=None, nav_table=None, settings_error="x"),
     "settings 與 settings_error 要恰好給一個"),
    ("R3 先於 R4", dict(holding_tables=None, holding_error=""), "holding_error 是空字串：''"),
    ("R3 的 holding_error 先於 settings_error",
     dict(holding_tables=None, holding_error="", key_results=None, nav_table=None, settings=None, settings_error=""),
     "holding_error 是空字串：''"),
    ("R4 先於 R6", dict(holding_tables=None, holding_error="x", dividend_gate_open=0),
     "持倉表讀取失敗時，key_results、nav_table 一律不得給"),
    ("R5 先於 R6", dict(key_results=None, dividend_gate_open=0), "持倉表讀取成功時，key_results、nav_table 一律要給"),
    ("R6 先於 R7", dict(dividend_gate_open=0, empty_without_reason=""), "dividend_gate_open 應為 bool：0"),
    ("R7 先於 R8", dict(empty_without_reason="", nav_unavailable_withheld="x"), "empty_without_reason 是空字串：''"),
    ("R8 先於 R12", dict(nav_unavailable_withheld="x", mask=None), "nav_unavailable_withheld 應為集合：str"),
    ("R12 先於 R9", dict(mask=None, dividend_gate_open=True), "mask 應為可呼叫：NoneType"),
    ("R9 先於 R13", dict(dividend_gate_open=True, nav_table=dict(_nav_table(), errors={_STRAY_CODE: "x"})),
     "配息閘門已打開，本頁尚未規定配息怎麼組"),
]


@pytest.mark.parametrize("over, message", [c[1:] for c in _ORDER_CASES], ids=[c[0] for c in _ORDER_CASES])
def test_T7g_參數檢查的先後次序_同時違反兩條時先報前面那一條(over, message):
    with pytest.raises(Exception) as info:
        live.assemble_live_load(**_kwargs(**over))
    assert str(info.value) == message


def _nav_table_with_extra(place, code):
    """合格的淨值表，另在 `place` 那一處多放一個持倉沒有的代碼。"""
    table = _nav_table()
    if place == "rows":
        row = copy.deepcopy(table["rows"][0])
        row["fund_code"] = code
        table["rows"].append(row)
    elif place == "errors":
        table["errors"][code] = "x"
    elif place == "withheld":
        table["withheld"][code] = _W_CCY_CONFLICT
    elif place == "skipped":
        table["skipped"][code] = ["x"]
    elif place in ("fetched", "skipped_rows"):
        table[place][code] = 0
    elif place == "provenance":
        table["provenance"][code] = _prov_entry()
    else:
        raise AssertionError(place)
    return table


@pytest.mark.parametrize("place", ("rows", "errors", "withheld", "skipped", "fetched", "skipped_rows", "provenance"))
def test_T7h_R13_淨值表任何一處出現持倉沒有的代碼_raise(place):
    stray = "ZZ" + uuid.uuid4().hex[:6].upper()
    kw = _kwargs(nav_table=_nav_table_with_extra(place, stray))
    _raises(kw, ValueError, f"淨值表出現持倉裡沒有的代碼：{[stray]!r}")


@pytest.mark.parametrize("bad", (1, 0, None, "True", "false"))
def test_T7h_R14_ok不是bool_TypeError(bad):
    tables = _l2_holding_tables()
    results = _key_results(tables["holding"])
    results[1]["ok"] = bad
    _raises(_kwargs(holding_tables=tables, key_results=results), TypeError,
            f"代碼對照的 ok 應為 bool：{results[1]['input']!r}")


def test_T7h_R14_代碼對照少了一檔_raise():
    tables = _l2_holding_tables()
    results = [r for r in _key_results(tables["holding"]) if r["input"] != _BAD_CODE]
    _raises(_kwargs(holding_tables=tables, key_results=results), ValueError,
            f"代碼對照的輸入與持倉代碼不一致：多 {[]!r}、少 {[_BAD_CODE]!r}")


def test_T7h_R14_代碼對照多了一檔_raise():
    tables = _l2_holding_tables()
    results = _key_results(tables["holding"])
    results.append(dict(results[0], input=_STRAY_CODE))
    _raises(_kwargs(holding_tables=tables, key_results=results), ValueError,
            f"代碼對照的輸入與持倉代碼不一致：多 {[_STRAY_CODE]!r}、少 {[]!r}")


def test_T7h_key_results不是list也不是tuple_TypeError():
    for value in ({}, "abc", iter(())):
        _raises(_kwargs(key_results=value), TypeError, f"key_results 應為 list：{type(value).__name__}")


@pytest.mark.parametrize("place", ("healthy", "withheld", "errors"))
def test_T7h_R15_代碼對照失敗的代碼出現在淨值表_raise(place):
    tables = _l2_holding_tables()
    results = _key_results(tables["holding"], fail={_BAD_CODE: _unique("對照失敗")})
    if place == "healthy":
        table = _nav_table()
    elif place == "withheld":
        table = _nav_table(healthy=(_OK_CODE, _MID_CODE), withheld={_BAD_CODE: _W_CCY_CONFLICT})
    else:
        table = _nav_table(healthy=(_OK_CODE, _MID_CODE), failed={_BAD_CODE: "x"})
    _raises(_kwargs(holding_tables=tables, key_results=results, nav_table=table), ValueError,
            f"代碼對照失敗的代碼不得出現在淨值表：{[_BAD_CODE]!r}")


def _nav_table_without_handover(place):
    """`_BAD_CODE` 沒有交給淨值表（不在 fetched、也不在 withheld），只出現在 `place` 那一處。"""
    table = _nav_table(healthy=(_OK_CODE, _MID_CODE))
    if place == "errors":
        table["errors"][_BAD_CODE] = "x"
    elif place == "skipped_rows":
        table["skipped_rows"][_BAD_CODE] = 0
    elif place == "skipped":
        table["skipped"][_BAD_CODE] = ["x"]
    return table


@pytest.mark.parametrize("place", ("沒有出現在任何一處", "errors", "skipped_rows", "skipped"))
def test_T7h_R16_代碼對照成功卻沒有交給淨值表_raise(place):
    table = _nav_table_without_handover(place)
    _raises(_kwargs(nav_table=table), ValueError, f"代碼對照成功、卻沒有交給淨值表的代碼：{[_BAD_CODE]!r}")


@pytest.mark.parametrize("handover", ("fetched", "withheld"))
def test_T7h_R16_只要在fetched或withheld其中一處就算交給了(handover):
    table = _nav_table(healthy=(_OK_CODE, _MID_CODE))
    if handover == "fetched":
        table["fetched"][_BAD_CODE] = 0
    else:
        table["withheld"][_BAD_CODE] = _W_INPUT_CONFLICT
    out = _assemble(nav_table=table)
    assert list(out) == ["dataset", "live_args"]


_CHECK_ORDER_CASES = [
    # 一致性檢查的先後：R13 → R14 → R15 → R16；同時違反兩條時先報前面那一條。
    ("R13 先於 R14", "stray_and_missing_input"),
    ("R14 的 ok 型別先於輸入集合", "bad_ok_and_missing_input"),
    ("R14 先於 R15", "missing_input_and_key_failed_in_table"),
    ("R15 先於 R16", "key_failed_in_table_and_not_handed"),
]


@pytest.mark.parametrize("which", [c[1] for c in _CHECK_ORDER_CASES], ids=[c[0] for c in _CHECK_ORDER_CASES])
def test_T7h_一致性檢查的先後次序(which):
    tables = _l2_holding_tables()
    results = _key_results(tables["holding"])
    table = _nav_table()
    if which == "stray_and_missing_input":
        table["errors"][_STRAY_CODE] = "x"
        results = [r for r in results if r["input"] != _BAD_CODE]
        expected = (ValueError, f"淨值表出現持倉裡沒有的代碼：{[_STRAY_CODE]!r}")
    elif which == "bad_ok_and_missing_input":
        results[0]["ok"] = 1
        results = results[:2]   # 另外少了最後一檔：型別檢查要先於輸入集合的比對
        expected = (TypeError, f"代碼對照的 ok 應為 bool：{results[0]['input']!r}")
    elif which == "missing_input_and_key_failed_in_table":
        results = [r for r in results if r["input"] != _BAD_CODE]
        results[0]["ok"] = False
        expected = (ValueError, f"代碼對照的輸入與持倉代碼不一致：多 {[]!r}、少 {[_BAD_CODE]!r}")
    else:
        results[0]["ok"] = False
        del table["fetched"][_BAD_CODE]
        expected = (ValueError, f"代碼對照失敗的代碼不得出現在淨值表：{[results[0]['input']]!r}")
    _raises(_kwargs(holding_tables=tables, key_results=results, nav_table=table), *expected)


# ═════════════════════════ T8　交出去的三張表，每一列都過 L2 的列契約 ═════════════════════════


def test_T8_快樂路徑輸出的holding_policy_nav_每一列都過列契約():
    out = _assemble()
    dataset = out["dataset"]
    checks = (
        ("holding", contract.holding_row_problems),
        ("policy", contract.policy_row_problems),
        ("nav", contract.nav_row_problems),
    )
    for table, check in checks:
        assert dataset[table], table   # 空掃防呆：假輸入真的有列
        for index, row in enumerate(dataset[table]):
            assert check(row) == [], (table, index, row)
