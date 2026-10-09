# -*- coding: utf-8 -*-
"""ui_v2/hld/source.py 的接縫測試（hld S6b-3；體例同 tests/ui_v2/test_alo_source.py）。

L2 的讀表函式與 `st` 以替身注入（monkeypatch `source` 模組上的引用）；`build_nav_table` 用真的 L2，
只把它呼叫的 L1 `fetch_nav_with_error` 換成替身。不打網路。
"""

from __future__ import annotations

import ast
import copy
import pathlib
import sys
import types

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

from ui_v2.hld import fixtures, live, logic  # noqa: E402

source = pytest.importorskip("ui_v2.hld.source")  # 需要 L1 的相依（streamlit、gspread 等）
pd = pytest.importorskip("pandas")

_SECRET = "zz-fake-secret-5c1e"


def _module_constant(rel, name):
    """用 AST 從原始檔讀出一個常數（`alo_holdings` 的三個分頁名是 `repo.xxx` 轉指派，AST 讀不到，改讀 L1）。"""
    for node in ast.parse((_ROOT / rel).read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError(f"{name} 不在 {rel}")


_L1 = "repositories/policy_supplement_repository.py"
_ND = "services/v2_tables/nav_dividend.py"
_FOUR_WITHHELD = frozenset(_module_constant(_ND, n) for n in (
    "WITHHELD_CCY_MISSING", "WITHHELD_CCY_CONFLICT", "WITHHELD_FETCHED_AT_MISSING", "WITHHELD_FETCHED_AT_FUTURE",
))
_INPUT_CONFLICT = _module_constant(_ND, "WITHHELD_INPUT_CONFLICT")


def _holdings():
    """fixtures `full` 的持倉；DIRECT 持倉改掛既有保單（L2 不為 DIRECT 產生 holding 列）。"""
    rows = copy.deepcopy(fixtures.scenario("full")["dataset"]["holding"])
    for row in rows:
        if row["policy_id"] == "DIRECT":
            row["policy_id"] = "P-001"
    return rows


def _tables(holding=None):
    policy = [copy.deepcopy(p) for p in fixtures.scenario("full")["dataset"]["policy"] if p["policy_id"] != "DIRECT"]
    return {"holding": _holdings() if holding is None else holding, "policy": policy, "direct": [],
            "skipped_tabs": []}


def _settings():
    return {"rows": {}, "broken_keys": [], "tab_missing": False, "bad_rows": []}


def _key_results(codes, fail=()):
    return [{"input": c, "ok": c not in fail, "full_key": None if c in fail else "FK-" + c,
             "portal": None if c in fail else "", "parsed_code": c, "mapping_hit": c not in fail,
             "error": "查不到" if c in fail else None} for c in codes]


@pytest.fixture
def wired(monkeypatch):
    monkeypatch.setattr(source, "st", types.SimpleNamespace(secrets={"SETTINGS_SHEET_ID": _SECRET}, session_state={}))
    state = {"tables": _tables(), "settings": _settings(), "fail": (), "series": {}, "secret_values": {},
             "funds": None, "nav_table": None, "key_inputs": None}

    def _load(name, key):
        def fn(values):
            state["secret_values"][name] = values
            got = state[key]
            if isinstance(got, Exception):
                raise got
            return got
        return fn

    def _resolve(codes, **_kw):
        state["key_inputs"] = list(codes)
        if isinstance(state["fail"], Exception):
            raise state["fail"]
        return {"results": _key_results(codes, state["fail"]), "provenance": {}}

    real_build = source.nav_dividend.build_nav_table

    def _build(funds, **kw):
        state["funds"] = [dict(f) for f in funds]
        state["nav_table"] = real_build(state["funds"], **kw)
        return state["nav_table"]

    def _fetch(full_key, portal):
        if full_key in state["series"]:
            return state["series"][full_key], None
        return None, f"上游逾時 token={_SECRET}"

    monkeypatch.setattr(source.alo_holdings, "load_alo_tables", _load("load_alo_tables", "tables"))
    monkeypatch.setattr(source.settings_store, "load_user_settings", _load("load_user_settings", "settings"))
    monkeypatch.setattr(source.fund_keys, "resolve_full_keys", _resolve)
    monkeypatch.setattr(source.nav_dividend, "build_nav_table", _build)
    monkeypatch.setattr(source.nav_dividend, "fetch_nav_with_error", _fetch)
    return state


def _series():
    s = pd.Series([10.0], index=[pd.Timestamp("2026-09-30")])
    s.attrs = {"source": "MoneyDJ:x"}
    return s


# ═══════════════════════ 組 L2 輸入（funds） ═══════════════════════


def test_每一筆持倉列對應一筆fund_帶holding_ccy_不去重(wired):
    holding = _holdings()
    dup = dict(holding[0], policy_id="P-002", ccy="EUR" if holding[0]["ccy"] != "EUR" else "USD")
    holding.insert(1, dup)
    wired["tables"] = _tables(holding)
    source.load_live()
    assert [(f["fund_code"], f["holding_ccy"]) for f in wired["funds"]] == [(h["fund_code"], h["ccy"]) for h in holding]
    assert all(f["full_key"] == "FK-" + f["fund_code"] for f in wired["funds"])


def test_同檔兩列幣別不同_L2判成ccy_conflict(wired):
    """不去重、帶 holding_ccy 兩件事一起成立，L2 才看得到兩種幣別（去重會變 fetched_at_missing、漏傳會變 ccy_missing）。"""
    holding = _holdings()
    code = holding[0]["fund_code"]
    holding.insert(1, dict(holding[0], policy_id="P-002", ccy="EUR" if holding[0]["ccy"] != "EUR" else "USD"))
    wired["tables"] = _tables(holding)
    wired["series"] = {"FK-" + code: _series()}
    out = source.load_live()
    assert wired["nav_table"]["withheld"] == {code: _module_constant(_ND, "WITHHELD_CCY_CONFLICT")}
    assert code not in out["dataset"]["fund_errors"].get("nav", {})


def test_代碼對照ok為False的檔不交給L2_不以full_key_None交出(wired):
    codes = [h["fund_code"] for h in _holdings()]
    wired["fail"] = (codes[0],)
    out = source.load_live()
    assert wired["key_inputs"] == codes
    assert codes[0] not in {f["fund_code"] for f in wired["funds"]}
    assert all(f["full_key"] is not None for f in wired["funds"])
    assert codes[0] not in out["dataset"]["fund_errors"].get("nav", {})


# ═══════════════════════ L2 常數以參數注入 ═══════════════════════


def test_常數注入_扣下清單恰為四碼_不含input_conflict_其餘照L2(monkeypatch, wired):
    seen = {}
    sentinel = object()

    def spy(**kw):
        seen.update(kw)
        return sentinel

    monkeypatch.setattr(source.live, "assemble_live_load", spy)
    assert source.load_live() is sentinel   # 回傳原樣交出，source 不另組 pending_tables 等
    assert set(seen["nav_unavailable_withheld"]) == _FOUR_WITHHELD
    assert _INPUT_CONFLICT not in seen["nav_unavailable_withheld"]
    assert seen["empty_without_reason"] == _module_constant(
        "services/v2_tables/market_indicator.py", "EMPTY_WITHOUT_REASON")
    assert seen["dividend_gate_open"] is _module_constant(_ND, "DIV_DATE_IS_EX_DATE_VERIFIED")
    assert seen["direct_policy_id"] == _module_constant("services/v2_tables/contract.py", "DIRECT_POLICY_ID")
    assert seen["policy_tab_source"] == _module_constant(_L1, "POLICY_TAB_SOURCE")
    assert set(seen["direct_sources"]) == {_module_constant(_L1, n) for n in (
        "POLICY_TAB_SOURCE", "TAB_POLICY_PROFILE", "TAB_HOLDING_SUPPLEMENT")}


def test_組出的回傳值build_live_model吃得下(wired):
    out = source.load_live()
    model = live.build_live_model(out["dataset"], **out["live_args"])
    assert model["title"] == logic.PAGE_TITLE


# ═══════════════════════ 秘密值與遮蔽 ═══════════════════════


def test_秘密值在L3讀好再傳進L2(wired):
    source.load_live()
    assert set(wired["secret_values"]) == {"load_alo_tables", "load_user_settings"}
    for call, values in wired["secret_values"].items():
        assert _SECRET in values, call


def test_持倉與設定讀取失敗_各進對應錯誤_訊息經遮蔽(wired):
    wired["tables"] = source.alo_holdings.PolicySupplementError(f"上游 503 {_SECRET}", code="api")
    wired["settings"] = source.settings_store.SettingsSheetError(f"讀不到設定 {_SECRET}", code="api")
    errors = source.load_live()["dataset"]["errors"]
    assert set(errors) == {"holding", "user_setting"}
    for value in errors.values():
        assert _SECRET not in value and source.masking.MASK in value


def test_淨值取數失敗訊息經遮蔽(wired):
    failures = source.load_live()["dataset"]["fund_errors"]["nav"]
    assert failures and all(_SECRET not in v and source.masking.MASK in v for v in failures.values())


def test_mask_error遮掉秘密值(wired):
    assert source.mask_error(f"x {_SECRET} y") == f"x {source.masking.MASK} y"


def test_代碼對照拋L1例外_往上拋給page的try(wired):
    wired["fail"] = RuntimeError(f"對照表讀不到 {_SECRET}")
    with pytest.raises(RuntimeError):
        source.load_live()


@pytest.mark.slow
def test_代碼對照拋L1例外_正式入口畫錯誤畫面_不印Traceback_不帶秘密值_沒有按鈕(wired):
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    wired["fail"] = RuntimeError(f"對照表讀不到 {_SECRET}")

    def _app():
        from ui_v2.hld import page, source

        page.render(load_live=source.load_live, mask_error=source.mask_error)

    at = AppTest.from_function(_app, default_timeout=60)
    at.run()
    assert len(at.exception) == 0
    md = "\n".join(m.value for m in at.markdown)
    assert "Traceback" not in md and _SECRET not in md
    assert "RuntimeError：對照表讀不到 " + source.masking.MASK in md
    assert [b.label for b in at.button] == []
