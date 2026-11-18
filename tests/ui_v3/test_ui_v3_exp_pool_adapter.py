# -*- coding: utf-8 -*-
"""S2-T0（`DEC-2026-11-17-04`）：選股池 adapter 測試——L2 回傳形狀適配、四狀態、fail-closed、不洩漏、不碰持久層。

本機執行：
    pytest tests/ui_v3/test_ui_v3_exp_pool_adapter.py -q --noconftest -p no:cacheprovider

⚠️ 全部輸入是**測試注入**的 dict／假取數函式；沒有讀 Google Sheet、沒有 secrets、沒有網路。
對照 L2 的方式：① 以 AST 讀 `services/v2_tables/exp_universe.py` 原始碼（不 import、不呼叫 `load_pool_codes`）鎖鍵集合與 status 字面；
② 在**獨立子程序**內 import L2 模組，只取它的純函式 `_empty`／`_codes_of` 做出真實回傳形狀（不呼叫 `load_pool_codes`、不碰 L1 實例）。
"""
from __future__ import annotations

import ast
import inspect
import json
import logging
import pathlib
import re
import subprocess
import sys

import pytest

import ui_v3_guard_lib as lib
from ui_v3.adapters import exp_pool as adapter
from ui_v3.adapters.exp_pool import PoolContractError, adapt_pool_result, load_pool_view
from ui_v3.viewmodels.exp_pool import (
    REASON_LOADER_RAISED,
    REASON_POOL_UNAVAILABLE,
    REASON_SOURCE_COOLING,
    REASON_SOURCE_FAILED,
    PoolSourceView,
    PoolState,
)

ADAPTER_REL = "ui_v3/adapters/exp_pool.py"
VIEWMODEL_REL = "ui_v3/viewmodels/exp_pool.py"
PROD_RELS = (ADAPTER_REL, VIEWMODEL_REL)
L2_PATH = lib.ROOT / "services" / "v2_tables" / "exp_universe.py"
READ_AT = "2026-11-17T10:00:00+00:00"
POISONS = ("secret-token-abc123", "https://sheets.example/spreadsheets/d/SHEET?key=SECRET", "KeyError: 'private_key'",
           "gspread.exceptions.APIError: 403 permission", "backend-sa-credentials")


# ───────────────────────── 以 L2 實際形狀做 fixture ─────────────────────────

def l2_ok(_codes=("A1", "B2"), **over) -> dict:
    raw = {"status": "ok", "backend": "google-sheets", "codes": list(_codes), "dropped_blank": 0, "duplicates": 0,
           "message": None, "read_at": READ_AT, "ttl_sec": 3600, "cooling": False}
    raw.update(over)
    return raw


def l2_not_ok(status="failed", *, cooling=False, message="選股池剛讀取失敗過", **over) -> dict:
    """L2 `_empty()` 的形狀：codes 空、統計 0、read_at None。"""
    raw = {"status": status, "backend": "google-sheets", "codes": [], "dropped_blank": 0, "duplicates": 0,
           "message": message, "read_at": None, "ttl_sec": 3600, "cooling": cooling}
    raw.update(over)
    return raw


# ───────────────────────── L2 形狀鎖（讀碼，不呼叫） ─────────────────────────

def _l2_tree() -> ast.Module:
    return ast.parse(L2_PATH.read_text(encoding="utf-8"))


def _dict_keys(node: ast.Dict) -> set:
    return {k.value for k in node.keys if isinstance(k, ast.Constant)}


def _function(tree: ast.Module, name: str) -> ast.FunctionDef:
    return next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)


def test_status_literals_equal_the_l2_constants():
    consts = {}
    for node in _l2_tree().body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and node.targets[0].id.startswith("STATUS_"):
            consts[node.targets[0].id] = node.value.value
    assert consts == {"STATUS_OK": "ok", "STATUS_NOT_CLOUD": "pool_not_cloud", "STATUS_FAILED": "failed"}
    assert (adapter.L2_STATUS_OK, adapter.L2_STATUS_NOT_CLOUD, adapter.L2_STATUS_FAILED) == ("ok", "pool_not_cloud", "failed")


def test_required_keys_equal_the_union_every_l2_return_path_carries():
    tree = _l2_tree()
    empty_keys = next(_dict_keys(n.value) for n in ast.walk(_function(tree, "_empty")) if isinstance(n, ast.Return))
    codes_of_keys = next(_dict_keys(n.value) for n in ast.walk(_function(tree, "_codes_of")) if isinstance(n, ast.Return))
    ok_keys = set()
    for n in ast.walk(_function(tree, "load_pool_codes")):
        if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and n.targets[0].id == "result" and isinstance(n.value, ast.Dict):
            assert any(k is None for k in n.value.keys), "成功結果應以 **_codes_of(...) 展開（L2 改了形狀，請重審本 adapter）"
            ok_keys = _dict_keys(n.value) | codes_of_keys
    assert ok_keys
    assert empty_keys == ok_keys == set(adapter.L2_REQUIRED_KEYS)
    assert len(adapter.L2_REQUIRED_KEYS) == len(set(adapter.L2_REQUIRED_KEYS))


def test_real_l2_shapes_are_adapted_without_calling_load_pool_codes():
    """獨立子程序內取 L2 純函式 `_empty`／`_codes_of` 產出真形狀（含 streamlit 等重依賴；缺依賴則跳過，CI 會跑）。"""
    code = (
        "import json\n"
        "from types import SimpleNamespace as NS\n"
        "from services.v2_tables import exp_universe as E\n"
        "ok = {'status': E.STATUS_OK, 'backend': 'google-sheets', 'message': None, 'read_at': '" + READ_AT + "',\n"
        "      'ttl_sec': E.SUCCESS_TTL_SEC, 'cooling': False, **E._codes_of([NS(code=' ab1 '), NS(code='AB1'), NS(code=''), NS(code='ab1')])}\n"
        "empty_ok = dict(ok, **E._codes_of([]))\n"
        "print(json.dumps({'ok': ok, 'empty_ok': empty_ok,\n"
        "  'failed': E._empty(E.STATUS_FAILED, 'google-sheets', 'x'),\n"
        "  'cooling': E._empty(E.STATUS_FAILED, 'google-sheets', 'x', cooling=True),\n"
        "  'not_cloud': E._empty(E.STATUS_NOT_CLOUD, 'local-json', E.TEXT_NOT_CLOUD)}))\n")
    proc = subprocess.run([sys.executable, "-s", "-c", code], capture_output=True, text=True, cwd=str(lib.ROOT),
                          env={"PYTHONPATH": str(lib.ROOT), "PATH": "/usr/bin:/bin"}, timeout=120)
    if proc.returncode != 0:
        pytest.skip("本機缺 L2 的依賴（streamlit／gspread 等），無法在子程序載入 exp_universe；CI 有完整依賴")
    shapes = json.loads(proc.stdout.strip().splitlines()[-1])
    assert adapt_pool_result(shapes["ok"]) == PoolSourceView(PoolState.OK, ("ab1", "AB1"), None, READ_AT)   # 去重、大小寫原樣
    assert adapt_pool_result(shapes["empty_ok"]).state is PoolState.EMPTY
    assert adapt_pool_result(shapes["failed"]) == PoolSourceView(PoolState.FAILED, (), REASON_SOURCE_FAILED, None)
    assert adapt_pool_result(shapes["cooling"]) == PoolSourceView(PoolState.FAILED, (), REASON_SOURCE_COOLING, None)
    assert adapt_pool_result(shapes["not_cloud"]) == PoolSourceView(PoolState.UNAVAILABLE, (), REASON_POOL_UNAVAILABLE, None)


# ───────────────────────── 四狀態可區分 ─────────────────────────

def test_four_l2_outcomes_map_to_four_distinct_states():
    ok = adapt_pool_result(l2_ok(("A1",)))
    empty = adapt_pool_result(l2_ok(()))
    failed = adapt_pool_result(l2_not_ok("failed"))
    unavailable = adapt_pool_result(l2_not_ok("pool_not_cloud"))
    assert [v.state for v in (ok, empty, failed, unavailable)] == [PoolState.OK, PoolState.EMPTY, PoolState.FAILED, PoolState.UNAVAILABLE]
    assert len({ok, empty, failed, unavailable}) == 4
    assert ok.codes == ("A1",) and empty.codes == failed.codes == unavailable.codes == ()
    assert (failed.reason_code, unavailable.reason_code) == (REASON_SOURCE_FAILED, REASON_POOL_UNAVAILABLE)


def test_pool_not_cloud_never_names_a_cause_whatever_the_message_says():
    """未設定／憑證無法使用 L2 分不出；不管 message 寫什麼，內部都是同一個可識別的 UNAVAILABLE。"""
    views = {adapt_pool_result(l2_not_ok("pool_not_cloud", message=m, backend=b))
             for m in ("選股池未設定雲端來源（沒有服務帳戶憑證），不讀本機暫存檔當母體", "選股池未設定雲端來源（部署端未設定選股池試算表），不讀本機暫存檔當母體", "x")
             for b in ("local-json", "google-sheets")}
    assert views == {PoolSourceView(PoolState.UNAVAILABLE, (), REASON_POOL_UNAVAILABLE, None)}


def test_failed_is_not_collapsed_into_empty_or_unavailable_and_cooling_is_a_separate_category():
    assert adapt_pool_result(l2_not_ok("failed", cooling=False)).reason_code == REASON_SOURCE_FAILED
    assert adapt_pool_result(l2_not_ok("failed", cooling=True)).reason_code == REASON_SOURCE_COOLING
    assert adapt_pool_result(l2_not_ok("failed")).state is not PoolState.EMPTY


def test_ok_with_codes_and_ok_without_codes_differ_and_stats_do_not_change_the_state():
    assert adapt_pool_result(l2_ok((), dropped_blank=3, duplicates=2)).state is PoolState.EMPTY   # 全被丟掉＝空池
    assert adapt_pool_result(l2_ok(("A1",), dropped_blank=3, duplicates=2)).state is PoolState.OK


def test_codes_pass_through_opaque_and_ordered():
    codes = ["zz", "AB1", "ab1", "AB 1", "ＡＢ１", "US0378331005", "0050", "基金甲"]
    view = adapt_pool_result(l2_ok(codes))
    assert view.codes == tuple(codes) and all(type(c) is str for c in view.codes)


def test_adapter_does_not_mutate_the_raw_result():
    raw = l2_ok(("A1", "B2"))
    snapshot = json.loads(json.dumps(raw))
    adapt_pool_result(raw)
    assert raw == snapshot


def test_extra_unknown_keys_are_ignored_not_carried():
    view = adapt_pool_result(l2_ok(("A1",), future_field=POISONS[0]))
    assert POISONS[0] not in repr(view)


# ───────────────────────── fail-closed ─────────────────────────

@pytest.mark.parametrize("raw", [None, [], (), "ok", 0, 1.5, b"ok", [("status", "ok")], object()])
def test_non_dict_results_fail_closed(raw):
    with pytest.raises(PoolContractError):
        adapt_pool_result(raw)


@pytest.mark.parametrize("key", adapter.L2_REQUIRED_KEYS)
def test_every_missing_key_fails_closed(key):
    for builder in (l2_ok, l2_not_ok):
        raw = builder()
        del raw[key]
        with pytest.raises(PoolContractError):
            adapt_pool_result(raw)


@pytest.mark.parametrize("status", ["OK", "Ok", "ok ", " ok", "", "error", "unknown", "pool_not_cloud ", "FAILED", "empty", "not_cloud", "success"])
def test_unknown_status_strings_fail_closed(status):
    with pytest.raises(PoolContractError):
        adapt_pool_result(l2_ok(("A1",), status=status))
    with pytest.raises(PoolContractError):
        adapt_pool_result(l2_not_ok(status=status))


@pytest.mark.parametrize("status", [None, 1, True, ["ok"], {"ok"}, b"ok", 0.0])
def test_non_string_status_fails_closed(status):
    with pytest.raises(PoolContractError):
        adapt_pool_result(l2_ok(("A1",), status=status))


@pytest.mark.parametrize("over", [
    dict(codes=None), dict(codes="A1"), dict(codes=("A1",)), dict(codes={"A1"}), dict(codes=[None]), dict(codes=[1]), dict(codes=[b"A1"]),
    dict(codes=[""]), dict(codes=["  "]), dict(codes=["A1", ""]), dict(codes=["A1", "A1"]), dict(codes=[["A1"]]),
    dict(backend=None), dict(backend=1), dict(backend=b"x"),
    dict(dropped_blank=None), dict(dropped_blank=-1), dict(dropped_blank=1.0), dict(dropped_blank=True), dict(dropped_blank="0"),
    dict(duplicates=None), dict(duplicates=-1), dict(duplicates=2.0), dict(duplicates=False), dict(duplicates="0"),
    dict(message="unexpected text on a success"), dict(message=""),
    dict(read_at="yesterday"), dict(read_at=1731800000), dict(read_at=1.5), dict(read_at=["x"]),
    dict(ttl_sec=None), dict(ttl_sec=0), dict(ttl_sec=-5), dict(ttl_sec="3600"), dict(ttl_sec=True),
    dict(cooling=None), dict(cooling=1), dict(cooling="False"), dict(cooling=True),
])
def test_ok_results_with_wrong_types_or_contradictions_fail_closed(over):
    with pytest.raises(PoolContractError):
        adapt_pool_result(l2_ok(("A1",), **over))


@pytest.mark.parametrize("status", ["failed", "pool_not_cloud"])
@pytest.mark.parametrize("over", [
    dict(codes=["A1"]), dict(codes=None), dict(codes="A1"),
    dict(message=None), dict(message=123), dict(message=["x"]),
    dict(read_at=READ_AT), dict(read_at="garbage"),
    dict(dropped_blank=1), dict(duplicates=1), dict(dropped_blank=True), dict(duplicates=None),
    dict(backend=None), dict(ttl_sec=None), dict(cooling="no"), dict(cooling=None),
])
def test_failed_or_unavailable_results_with_wrong_types_or_contradictions_fail_closed(status, over):
    with pytest.raises(PoolContractError):
        adapt_pool_result(l2_not_ok(status, **over))


def test_pool_not_cloud_cannot_claim_cooling():
    with pytest.raises(PoolContractError):
        adapt_pool_result(l2_not_ok("pool_not_cloud", cooling=True))


def test_ok_status_with_failure_shaped_payload_is_never_accepted_as_empty_or_ok():
    """矛盾組合：status=ok 卻帶失敗訊息／冷卻——絕不當成「空池」或「有資料」放行。"""
    for over in (dict(message="boom"), dict(cooling=True), dict(message="boom", cooling=True)):
        with pytest.raises(PoolContractError):
            adapt_pool_result(l2_ok((), **over))
        with pytest.raises(PoolContractError):
            adapt_pool_result(l2_ok(("A1",), **over))


@pytest.mark.parametrize("poison", POISONS)
def test_contract_error_messages_name_fields_and_types_only(poison):
    attempts = [
        l2_ok((poison, poison)), l2_ok((poison,), status=poison), l2_ok((poison,), read_at=poison), l2_ok((poison,), message=poison),
        l2_ok((poison,), backend=1, ttl_sec=poison), l2_not_ok(message=3, codes=[poison]), l2_not_ok(read_at=poison),
        l2_not_ok("pool_not_cloud", cooling=poison), poison, [poison], {poison: poison},
    ]
    for raw in attempts:
        with pytest.raises(PoolContractError) as info:
            adapt_pool_result(raw)
        assert poison not in str(info.value) and poison not in repr(info.value.args)
        assert info.value.__cause__ is None and info.value.__suppress_context__


# ───────────────────────── 不洩漏 ─────────────────────────

def _everything_visible(view) -> str:
    return repr(view) + " ".join(str(getattr(view, f.name)) for f in view.__dataclass_fields__.values())


@pytest.mark.parametrize("poison", POISONS)
def test_message_and_backend_never_reach_any_view_field(poison):
    for raw in (l2_not_ok("failed", message=poison, backend=poison), l2_not_ok("failed", cooling=True, message=poison),
                l2_not_ok("pool_not_cloud", message=poison, backend=poison)):
        assert poison not in _everything_visible(adapt_pool_result(raw))
    view = adapt_pool_result(l2_ok(("A1",), backend=poison))
    assert poison not in _everything_visible(view)


def _capture_logs():
    class Handler(logging.Handler):
        def __init__(self):
            super().__init__(logging.DEBUG)
            self.lines = []

        def emit(self, record):
            self.lines.append(record.getMessage())

    handler = Handler()
    root = logging.getLogger()
    previous = root.level
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)
    return handler, lambda: (root.removeHandler(handler), root.setLevel(previous))


class _Boom(Exception):
    pass


@pytest.mark.parametrize("poison", POISONS)
def test_loader_exception_becomes_failed_without_leaking_the_exception_text(poison):
    seen = []

    def loader(secret_values):
        seen.append(secret_values)
        raise _Boom(poison)

    handler, restore = _capture_logs()
    try:
        view = load_pool_view(loader, [poison])
    finally:
        restore()
    assert view == PoolSourceView(PoolState.FAILED, (), REASON_LOADER_RAISED, None)
    assert poison not in _everything_visible(view)
    assert all(poison not in line for line in handler.lines)            # log 也不帶例外字串
    assert any("_Boom" in line for line in handler.lines)               # 但留下型別名（不是靜默吞掉）
    assert seen == [[poison]]


@pytest.mark.parametrize("exc", [KeyError("private_key"), RuntimeError("x"), OSError(13, "denied"), ValueError("v"), PoolContractError("bad"),
                                 TypeError("t"), ZeroDivisionError()])
def test_any_ordinary_exception_from_the_loader_is_a_failed_state(exc):
    def loader(_):
        raise exc

    assert load_pool_view(loader, []).state is PoolState.FAILED


@pytest.mark.parametrize("exc", [KeyboardInterrupt, SystemExit, GeneratorExit])
def test_base_exceptions_are_not_swallowed(exc):
    def loader(_):
        raise exc()

    with pytest.raises(exc):
        load_pool_view(loader, [])


def test_contract_errors_from_a_misbehaving_loader_still_raise_and_are_not_turned_into_failed():
    for bad in (None, {}, {"status": "ok"}, l2_ok(("A1",), status="mystery"), [], "ok"):
        with pytest.raises(PoolContractError):
            load_pool_view(lambda _s, bad=bad: bad, [])


def test_loader_must_be_injected_there_is_no_default():
    params = inspect.signature(load_pool_view).parameters
    assert [p.default for p in params.values()] == [inspect.Parameter.empty] * len(params)
    assert list(params) == ["loader", "secret_values"]
    for bad in (None, "load_pool_codes", 42, ()):
        with pytest.raises(PoolContractError):
            load_pool_view(bad, [])                                       # type: ignore[arg-type]
    with pytest.raises(TypeError):
        load_pool_view()                                                  # type: ignore[call-arg]


def test_loader_receives_exactly_the_secret_values_passed_in_and_only_the_loader_is_called():
    calls = []

    def loader(secret_values):
        calls.append(secret_values)
        return l2_ok(("A1",))

    secrets = ["s1", "s2"]
    view = load_pool_view(loader, secrets)
    assert calls == [["s1", "s2"]] and secrets == ["s1", "s2"]
    assert view == PoolSourceView(PoolState.OK, ("A1",), None, READ_AT)
    assert "s1" not in _everything_visible(view)
    assert load_pool_view(loader, ("t1",)).state is PoolState.OK         # tuple 也可


@pytest.mark.parametrize("bad", [None, "secret", 3, ["ok", 1], [None], {"a"}, b"x"])
def test_secret_values_must_be_a_list_or_tuple_of_strings(bad):
    with pytest.raises(PoolContractError):
        load_pool_view(lambda _: l2_ok(), bad)                            # type: ignore[arg-type]


def test_loader_result_for_each_l2_outcome_goes_through_the_same_adaptation():
    results = {
        "ok": l2_ok(("A1",)), "empty": l2_ok(()), "failed": l2_not_ok("failed"), "unavailable": l2_not_ok("pool_not_cloud"),
    }
    states = {name: load_pool_view(lambda _s, raw=raw: raw, []).state for name, raw in results.items()}
    assert states == {"ok": PoolState.OK, "empty": PoolState.EMPTY, "failed": PoolState.FAILED, "unavailable": PoolState.UNAVAILABLE}


# ───────────────────────── 靜態：不碰持久層／環境／網路／身份解析 ─────────────────────────

_FORBIDDEN_NAMES = frozenset({
    "open", "environ", "getenv", "putenv", "session_state", "secrets", "st", "os", "sys", "subprocess", "socket", "requests", "httpx",
    "urlopen", "gspread", "write", "writelines", "write_text", "write_bytes", "dump", "dumps", "save", "commit", "exec", "eval",
    "resolve_full_keys", "fund_keys", "load_pool_codes", "list_pool", "get_pool_store", "pool_repository", "exp_universe",
})
_ALLOWED_IMPORTS = {
    ADAPTER_REL: {"__future__", "logging", "typing", "ui_v3.viewmodels.exp_pool"},
    VIEWMODEL_REL: {"__future__", "datetime", "dataclasses", "enum", "typing", "ui_v3.viewmodels.exp_counts"},
}


def static_problems(rel: str, source: str) -> list:
    """本批新檔的靜態規則：既有 ui_v3 守衛函式庫＋精確 import 白名單＋禁用名稱（環境變數、持久層、網路、身份解析、真實 L1／L2）。"""
    tree = ast.parse(source)
    out = list(lib.import_violations(rel, source)) + list(lib.write_surface_violations(rel, source)) + lib.module_level_side_effects(source)
    # `from X import Y` 會同時回 X 與 X.Y；只要每個模組名是「白名單本身」或「白名單模組的子名稱」就合規
    allowed = _ALLOWED_IMPORTS[rel]
    for module in set(lib.imports_of(tree, lib.package_of(rel))):
        if module not in allowed and not any(module.startswith(a + ".") for a in allowed):
            out.append(f"import 不在白名單：{module}")
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in _FORBIDDEN_NAMES:
            out.append(f"禁用名稱 {node.id}")
        elif isinstance(node, ast.Attribute) and node.attr in _FORBIDDEN_NAMES:
            out.append(f"禁用屬性 .{node.attr}")
        elif isinstance(node, ast.alias) and (node.name in _FORBIDDEN_NAMES or node.name.split(".")[-1] in _FORBIDDEN_NAMES):
            out.append(f"禁用 import 名稱 {node.name}")
    return out


@pytest.mark.parametrize("rel", PROD_RELS)
def test_new_production_files_pass_every_static_rule(rel):
    assert static_problems(rel, (lib.ROOT / rel).read_text(encoding="utf-8")) == []


@pytest.mark.parametrize("rel", PROD_RELS)
def test_new_files_are_inside_the_ui_v3_population_and_pass_the_existing_guards(rel):
    assert pathlib.Path(lib.ROOT / rel) in lib.population()
    source = lib.read(lib.ROOT / rel)
    assert lib.import_violations(rel, source) == [] and lib.write_surface_violations(rel, source) == []
    assert lib.module_level_side_effects(source) == []


@pytest.mark.parametrize("snippet", [
    "import os\n",
    "from os import environ\n",
    "x = os.environ['K']\n",
    "x = os.getenv('K')\n",
    "import streamlit as st\n",
    "st.session_state['k'] = 1\n",
    "def f():\n    st.secrets['k']\n",
    "def f():\n    open('x', 'w').write('1')\n",
    "def f(p):\n    p.write_text('1')\n",
    "import requests\n",
    "import urllib.request\n",
    "import gspread\n",
    "import sqlite3\n",
    "import json\n",
    "from services.v2_tables.fund_keys import resolve_full_keys\n",
    "from services.v2_tables import exp_universe\n",
    "def f():\n    from services.v2_tables.exp_universe import load_pool_codes\n    return load_pool_codes([])\n",
    "def f(x):\n    return resolve_full_keys(x)\n",
    "def f(s):\n    return s.get_pool_store()\n",
    "from repositories import pool_repository\n",
    "from shared import ttls\n",
    "import importlib\n",
])
@pytest.mark.parametrize("rel", PROD_RELS)
def test_static_rules_have_teeth_negative_controls_in_memory(rel, snippet):
    source = (lib.ROOT / rel).read_text(encoding="utf-8") + "\n" + snippet
    assert static_problems(rel, source), (rel, snippet)


def test_no_identity_parsing_or_r_id_imports_anywhere_in_the_new_files():
    for rel in PROD_RELS:
        tree = ast.parse((lib.ROOT / rel).read_text(encoding="utf-8"))
        modules = lib.imports_of(tree, lib.package_of(rel))
        assert not [m for m in modules if "fund_keys" in m or "identity" in m or m.startswith("services")]
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        assert not {n for n in names if "full_keys" in n or "resolve" in n or re.search(r"(^|_)isin($|_)", n.lower()) or "r_id" in n.lower()}


def test_importing_the_new_modules_loads_no_l1_l2_ui_or_network_modules():
    code = ("import sys\n"
            "import ui_v3.adapters.exp_pool\n"
            "print(','.join(sorted(n for n in sys.modules if n.split('.')[0] in "
            "{'streamlit','services','repositories','infra','shared','ui','ui_v2','gspread','requests','pandas','numpy','yfinance'})))\n"
            "print('ui_v3.viewmodels.exp_counts' in sys.modules)\n")
    proc = subprocess.run([sys.executable, "-s", "-c", code], capture_output=True, text=True, cwd=str(lib.ROOT),
                          env={"PYTHONPATH": str(lib.ROOT), "PATH": "/usr/bin:/bin"}, timeout=120)
    assert proc.returncode == 0, proc.stderr
    lines = proc.stdout.strip().splitlines()
    # `ui_v3.viewmodels` 套件本身（既有 `__init__`）會載入 `shared.ui_semantics`（批 2b 唯一開放的呈現規則表）；除此之外不得有任何舊樹／重依賴。
    loaded = [m for m in lines[0].split(",") if m]
    assert all(m == "shared" or m.startswith("shared.ui_semantics") for m in loaded), loaded
    assert lines[1] == "True", lines
