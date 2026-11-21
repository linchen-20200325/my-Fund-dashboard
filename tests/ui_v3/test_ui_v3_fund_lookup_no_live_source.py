# -*- coding: utf-8 -*-
"""🔍 單碼入口離線注入接口的正反控制：四欄投影、以及「不觸發真實三源 build_profiles」。

不重做 #1311 的入口對照與 DomainStatus 反例；不改既有測試檔。全部離線：假 loader、現編隨機字串、網路守衛（autouse）。
"""
from __future__ import annotations

import ast
import pathlib
import secrets
import subprocess
import sys
import textwrap

import pytest

import fund_lookup_support as S
from fund_lookup_support import no_real_network  # noqa: F401 — autouse 網路守衛 fixture（定義於 support）
import ui_v3_guard_lib as lib
from ui_v3.adapters.fund_lookup import lookup_fund
from ui_v3.viewmodels.fund_lookup import FieldStatus, LookupState

ADAPTER = lib.ROOT / "ui_v3" / "adapters" / "fund_lookup.py"
#: 真取數層與重依賴：adapter 不得（直接或間接）載入。`shared` 不在內（viewmodels 依賴 shared.ui_semantics）。
FORBIDDEN_ROOTS = ("services", "repositories", "infra", "streamlit", "requests", "gspread", "yfinance", "fund_fetcher", "urllib3")
_ENV_KEYS = ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "SYSTEMROOT", "PYTHONIOENCODING", "VIRTUAL_ENV")


# ───────────────────────── 偵測器：同一支用在真 adapter（須綠）與變異版（須紅） ─────────────────────────

def static_violations(source: str) -> list:
    """AST：任何位置（含函式內延遲 import）的禁用根模組、`importlib`／`__import__` 動態載入。"""
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found += [a.name for a in node.names if a.name.split(".")[0] in FORBIDDEN_ROOTS]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and (node.module or "").split(".")[0] in FORBIDDEN_ROOTS:
            found.append(node.module)
        elif isinstance(node, ast.Name) and node.id in ("__import__", "importlib"):
            found.append(node.id)
        elif isinstance(node, ast.Attribute) and node.attr == "import_module":
            found.append("import_module")
    return found


_RUNTIME = r"""
import importlib.abc, importlib.util, sys
ROOTS = %r
attempts = []
class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if name.split('.')[0] in ROOTS:
            attempts.append(name)
            raise ImportError('LIVE-IMPORT ' + name)
sys.meta_path.insert(0, Block())
import socket
def _no(*a, **k):
    raise SystemExit('NETWORK-ATTEMPT')
socket.socket.connect = _no; socket.create_connection = _no; socket.getaddrinfo = _no
spec = importlib.util.spec_from_file_location('adapter_under_test', sys.argv[1])
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
calls = []
def loader(q):
    calls.append(q)
    raise ConnectionError('x')
views = [mod.lookup_fund(loader, 'ACTI71'), mod.lookup_fund(loader, 'https://x')]
try:
    mod.lookup_fund(None, 'ACTI71')      # 沒有 loader：不得退回預設真取數
except Exception:
    pass
print(sorted(set(attempts) | {n for n in sys.modules if n.split('.')[0] in ROOTS}))
print([v.state.value for v in views], calls)
"""


def runtime_run(path: pathlib.Path) -> subprocess.CompletedProcess:
    import os
    env = {k: os.environ[k] for k in _ENV_KEYS if k in os.environ}
    env.setdefault("PATH", "/usr/bin:/bin")
    env["PYTHONPATH"] = str(lib.ROOT)
    return subprocess.run([sys.executable, "-s", "-c", _RUNTIME % (FORBIDDEN_ROOTS,), str(path)], capture_output=True, text=True,
                          cwd=str(lib.ROOT), env=env, timeout=120)


def is_green(path: pathlib.Path) -> bool:
    """靜態＋執行期皆乾淨才算綠。"""
    if static_violations(path.read_text(encoding="utf-8")):
        return False
    proc = runtime_run(path)
    lines = proc.stdout.strip().splitlines()
    return proc.returncode == 0 and len(lines) == 2 and lines[0] == "[]" and lines[1] == "['source_failed', 'blocked'] ['ACTI71']"


# ───────────────────────── (1) 正控：五欄如實投影 ─────────────────────────

def test_positive_control_four_fields_and_source_state_are_projected_from_the_injected_loader():
    loader = S.CountingLoader(S.profile())
    view = lookup_fund(loader, " " + S.SAMPLE_CODE + " ")
    assert loader.calls == [S.SAMPLE_CODE]                                  # 只呼叫注入的 loader 一次
    assert view.state is LookupState.RESULT
    f = view.fields
    assert (f.fund_name.status, f.fund_name.value) == (FieldStatus.VALUE, S.SAMPLE_NAME)
    assert f.dividend_policy.status is FieldStatus.VALUE
    assert f.inception_on.value == S.SAMPLE_INCEPTION
    assert f.mgmt_fee_rate_pct.status is FieldStatus.MISSING                # 費率格沒有來源：缺值，不是數字


def test_missing_values_are_missing_not_zero_or_empty():
    loader = S.CountingLoader(S.profile(dividend_policy=S.cell("not_ready", None), inception_on=S.cell("not_ready", None)))
    f = lookup_fund(loader, S.SAMPLE_CODE).fields
    for fv in (f.dividend_policy, f.inception_on, f.mgmt_fee_rate_pct):
        assert fv.status is FieldStatus.MISSING and fv.value is None
        assert fv.value not in (0, 0.0, "", "0")


def test_other_sources_cannot_leak_into_the_projection_poisoned_extra_keys_are_ignored():
    poison = S.poisons()
    result = S.profile(fund_name=S.cell("ok", S.SAMPLE_NAME, reason=poison[0], raw={"k": poison[1]}), tdcc="failed", fundclear="failed")
    view = lookup_fund(S.CountingLoader(result), S.SAMPLE_CODE)
    assert view.state is LookupState.RESULT                                 # TDCC／FundClear 失敗不影響只讀 MoneyDJ 的投影
    assert not any(p in repr(view) for p in poison)


@pytest.mark.parametrize("exc", [ConnectionError("x"), TimeoutError("x")])
def test_loader_failure_is_source_failed_never_fund_not_found(exc):
    view = lookup_fund(S.CountingLoader(exc), S.SAMPLE_CODE)
    assert view.state is LookupState.SOURCE_FAILED
    assert view.state is not LookupState.PAGE_UNMATCHED and view.fields is None


def test_moneydj_failed_status_is_source_failed_and_not_page_unmatched():
    view = lookup_fund(S.CountingLoader(S.failed_profile()), S.SAMPLE_CODE)
    assert view.state is LookupState.SOURCE_FAILED and view.fields is None


# ───────────────────────── (2) 反控：不觸發預設 build_profiles／真取數 ─────────────────────────

def _install_spies(monkeypatch) -> list:
    """把 build_profiles 與 repositories.fund 的取數入口換成會 raise 的 spy，回傳命中紀錄。"""
    try:
        from services.v2_tables import exp_profile
        import repositories.fund as rf
    except Exception as exc:                                            # 依賴缺 → CI 內 fail、本機 skip（見 support）
        S.unavailable(f"L2／L1 無法載入，無法做 spy：{type(exc).__name__}")
    hits: list = []

    def spy(name):
        def _spy(*a, **k):
            hits.append(name)
            raise AssertionError(f"live path called: {name}")
        return _spy

    monkeypatch.setattr(exp_profile, "build_profiles", spy("exp_profile.build_profiles"))
    for attr in [a for a in dir(rf) if a.startswith(("fetch", "_src_"))]:
        if callable(getattr(rf, attr)):
            monkeypatch.setattr(rf, attr, spy("repositories.fund." + attr))
    return hits


def _load(path: pathlib.Path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("adapter_spy_target_" + secrets.token_hex(4), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_lookup_fund_never_calls_default_build_profiles_or_repositories_fund(monkeypatch, no_real_network):
    """跑完所有路徑（放行、攔截、失敗、無 loader）後 spy 命中必為 0；無 loader 只能是契約錯誤，不得退回預設。"""
    from ui_v3.viewmodels.fund_lookup import LookupContractError
    hits = _install_spies(monkeypatch)
    lookup_fund(S.CountingLoader(S.profile()), S.SAMPLE_CODE)
    lookup_fund(S.CountingLoader(ConnectionError("x")), S.SAMPLE_CODE)
    lookup_fund(S.sentinel_loader(), "https://example.invalid/x")
    with pytest.raises(LookupContractError):
        lookup_fund(None, S.SAMPLE_CODE)
    assert hits == [] and no_real_network == []


def test_spy_control_turns_red_when_adapter_defaults_to_the_live_build_profiles(monkeypatch, tmp_path):
    """變異負控：改接預設 loader 後，lookup_fund(None, …) 會觸發 spy（命中非空），證明上面的 spy 不是死的。"""
    hits = _install_spies(monkeypatch)
    path = tmp_path / "mutant_spy.py"
    path.write_text(_mutants()["lazy_default_loader"], encoding="utf-8")
    mod = _load(path)
    with pytest.raises(AssertionError, match="live path called"):
        mod.lookup_fund(None, S.SAMPLE_CODE)
    assert hits == ["exp_profile.build_profiles"]


def test_adapter_source_imports_nothing_from_the_live_fetch_layers():
    assert static_violations(ADAPTER.read_text(encoding="utf-8")) == []


def test_fresh_interpreter_with_import_blocker_runs_every_path_and_loads_no_live_layer():
    proc = runtime_run(ADAPTER)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip().splitlines() == ["[]", "['source_failed', 'blocked'] ['ACTI71']"]
    assert is_green(ADAPTER)


# ───────────────────────── (3) 變異負控：adapter 改接預設 loader → 必須轉紅（類別名現編，不寫進文件） ─────────────────────────

def _mutants() -> dict:
    src = ADAPTER.read_text(encoding="utf-8")
    tag = secrets.token_hex(4)
    head = "from ui_v3.viewmodels.fund_lookup import (\n    INPUT_ECHO_MAX,"
    assert head in src
    default_body = (
        "    if loader is None:\n"
        "        from services.v2_tables.exp_profile import build_profiles as _bp\n"
        f"        loader = lambda q: _bp([q])  # mutant {tag}\n"
    )
    anchor = '    _need(callable(loader), "loader", "callable", loader)\n'
    assert anchor in src
    return {
        "module_level_import": src.replace(head, "from services.v2_tables.exp_profile import build_profiles\n" + head, 1),
        "lazy_default_loader": src.replace(anchor, default_body + anchor, 1),
        "dynamic_import": src.replace(anchor, "    if loader is None:\n        import importlib\n"
                                      "        loader = importlib.import_module('repositories.fund').fetch_fund_multi_source\n" + anchor, 1),
        "requests_default": src.replace(head, "import requests\n" + head, 1),
    }


@pytest.mark.parametrize("name", ["module_level_import", "lazy_default_loader", "dynamic_import", "requests_default"])
def test_mutant_adapter_wired_to_a_default_live_loader_turns_the_guard_red(name, tmp_path):
    mutated = _mutants()[name]
    assert mutated != ADAPTER.read_text(encoding="utf-8")               # 變異確實生效
    path = tmp_path / "mutant_adapter.py"
    path.write_text(mutated, encoding="utf-8")
    assert static_violations(mutated), name                             # 靜態偵測轉紅
    assert is_green(path) is False                                      # 整體偵測轉紅
    assert is_green(ADAPTER) is True                                    # 對照：未變異版仍綠（偵測器不是恆紅）


def test_runtime_blocker_alone_catches_a_lazy_import_the_static_scan_would_miss(tmp_path):
    """執行期那層獨立有效：字串組出的延遲載入，靜態掃描判綠，僅 runtime 判紅，且紅燈來自 blocker 紀錄的被擋根模組。"""
    src = ADAPTER.read_text(encoding="utf-8")
    anchor = '    _need(callable(loader), "loader", "callable", loader)\n'
    sneaky = ("    if loader is None:\n"
              "        __builtins__['__im' + 'port__']('serv' + 'ices.v2_tables.exp_profile')\n")
    mutated = src.replace(anchor, sneaky + anchor, 1)
    assert mutated != src
    path = tmp_path / "sneaky.py"
    path.write_text(mutated, encoding="utf-8")
    assert static_violations(mutated) == []                             # 靜態層判綠（看不到）
    proc = runtime_run(path)
    assert proc.returncode == 0, proc.stderr
    blocked = proc.stdout.strip().splitlines()[0]
    assert "services" in blocked, blocked        # 紅燈確實來自 import blocker 擋下的 services 根
    assert is_green(path) is False
    assert is_green(ADAPTER) is True                                    # 對照：真 adapter 的 blocker 紀錄為空
