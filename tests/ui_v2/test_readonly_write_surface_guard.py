# -*- coding: utf-8 -*-
"""新 B UI 第一階段唯讀：寫入面守衛（fast，不碰網路）。

1. ui_v2/ 與 services/v2_tables/ 不得 import／呼叫已知寫入函式（pool／保單）。
2. gspread 寫入方法呼叫只允許白名單檔案（AST，不是字串 grep）。
3. ~~`UI_V2_READ_ONLY` 開關：真值 → `read_only` 且 repository 零呼叫；其他 → 現行路徑。~~
   → 2026-10-26 客戶裁示第 7 節（有意識的行為變更，不是漏刪）：`is_read_only()` 恆為 True，任何旗標值 → `read_only`、
   repository 零呼叫；休眠寫入路徑以 monkeypatch 模擬。
4. 五頁正式模式第一階段不畫寫入控制（`ui_v2/readonly.py`）：模型層（存檔鈕拿掉、說明改寫）＋ AST（五頁的接線點）。

已知寫入函式名單的來源（2026-10-26 讀 repositories 原始碼）：
- repositories/pool_repository.py：add_or_update、remove_from_pool、set_type_override、set_secid
- repositories/policy/v1.py：upsert_policy_row、delete_policy_row
- repositories/policy/v2.py：upsert_fund_in_policy、delete_fund_in_policy、delete_policy_worksheet、
  create_dashboard_sheet、write_policy_v2
（repositories/policy_supplement_repository.py 實測沒有公開寫入函式。）
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCAN_DIRS = ("ui_v2", "services/v2_tables")

KNOWN_WRITE_FUNCTIONS = frozenset({
    "add_or_update", "remove_from_pool", "set_type_override", "set_secid",
    "upsert_policy_row", "delete_policy_row",
    "upsert_fund_in_policy", "delete_fund_in_policy", "delete_policy_worksheet",
    "create_dashboard_sheet", "write_policy_v2",
    # 稽核補充（2026-10-26，已讀碼確認函式名與模組）：
    "rename_sheet",                                  # repositories/policy/v2.py
    "append_ledger_row",                             # repositories/ledger_repository.py
    "append_snapshot",                               # repositories/portfolio_perf_repository.py
    "save_all_ledgers_snapshot", "save_holdings_overview",   # repositories/snapshot_repository.py
})
WRITE_MODULES = ("repositories.pool_repository", "repositories.policy",
                 "repositories.policy_supplement_repository", "repositories.ledger_repository",
                 "repositories.portfolio_perf_repository", "repositories.snapshot_repository")

# 名稱本身只可能是 gspread 寫入者的方法；任何接收者都算。
GSPREAD_WRITE_UNAMBIGUOUS = frozenset({
    "append_rows", "append_row", "update_cell", "update_cells", "batch_update",
    "delete_rows", "add_worksheet", "del_worksheet",
})
# dict.update／cache.clear 同名，只在接收者名稱像 gspread 物件時才算。
GSPREAD_WRITE_AMBIGUOUS = frozenset({"update", "clear"})
_GSPREAD_RECEIVER_HINTS = ("sheet", "ws", "worksheet", "spreadsheet", "gc", "gspread")

# 白名單（repo 相對路徑，posix）。L1 repository 不在掃描目錄內，不用列。
# ~~GSPREAD_WRITE_ALLOWLIST = frozenset({"services/v2_tables/settings_store.py"})~~
# → 2026-10-26 客戶裁示第 6 節（Google Sheet 零寫入、不建立診斷寫入例外；有意識的收緊，不是漏刪）：清空。
#   `settings_store.py` 從來沒有直接呼叫 gspread（它經 L1 寫），所以它的 Google Sheet 寫入改由下方
#   「L1 寫入函式呼叫」守衛鎖（`test_no_settings_sheet_l1_write_calls`）。
GSPREAD_WRITE_ALLOWLIST = frozenset()


def _files():
    out = []
    for d in SCAN_DIRS:
        for p in sorted((ROOT / d).rglob("*.py")):
            if "tests" in p.relative_to(ROOT).parts:
                continue
            out.append(p)
    return out


def _tree(path):
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _receiver_name(node):
    while isinstance(node, ast.Attribute):
        node = node.value
    if isinstance(node, ast.Call):
        return _receiver_name(node.func)
    return node.id if isinstance(node, ast.Name) else ""


def test_scan_sets_are_not_empty():
    names = {p.relative_to(ROOT).as_posix() for p in _files()}
    assert "services/v2_tables/settings_store.py" in names
    assert any(n.startswith("ui_v2/") for n in names)


def test_no_known_write_function_imported_or_called():
    hits = []
    for path in _files():
        rel = path.relative_to(ROOT).as_posix()
        for node in ast.walk(_tree(path)):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith(WRITE_MODULES):
                for a in node.names:
                    if a.name in KNOWN_WRITE_FUNCTIONS:
                        hits.append(f"{rel}:{node.lineno} from {node.module} import {a.name}")
            elif isinstance(node, ast.Call):
                f = node.func
                name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", None)
                if name in KNOWN_WRITE_FUNCTIONS:
                    hits.append(f"{rel}:{node.lineno} call {name}")
    assert not hits, "新 B UI 第一階段唯讀，出現已知寫入函式：\n" + "\n".join(hits)


def test_gspread_write_calls_only_in_allowlist():
    hits = []
    for path in _files():
        rel = path.relative_to(ROOT).as_posix()
        if rel in GSPREAD_WRITE_ALLOWLIST:
            continue
        for node in ast.walk(_tree(path)):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                attr = node.func.attr
                recv = _receiver_name(node.func.value).lower()
                if attr in GSPREAD_WRITE_UNAMBIGUOUS or (
                        attr in GSPREAD_WRITE_AMBIGUOUS and any(h in recv for h in _GSPREAD_RECEIVER_HINTS)):
                    hits.append(f"{rel}:{node.lineno} .{attr}(")
    assert not hits, "白名單外的 gspread 寫入呼叫：\n" + "\n".join(hits)


# ───────── 2026-10-26 裁示第 6 節：ui_v2／services/v2_tables 不得呼叫設定試算表 L1 的寫入函式 ─────────
# L1 寫入函式名單不手抄：讀 `repositories/settings_sheet_repository.py`，凡函式本體以 `_run(..., write=True)` 打上游者即是
# （L1 日後新增寫入函式自動納入），另加兩個私有寫入輔助。下限釘住現有四個，名單縮水（偵測失效）就紅。
L1_SETTINGS_MODULE = "repositories.settings_sheet_repository"
_L1_PRIVATE_WRITERS = frozenset({"_run", "_append", "_worksheet_for_append"})
_L1_KNOWN_WRITERS = frozenset({"save_user_setting", "open_fetch_log", "close_fetch_log", "append_market_indicator"})


def _l1_write_functions():
    tree = _tree(ROOT / "repositories" / "settings_sheet_repository.py")
    out = set()
    for fn in tree.body:
        if not isinstance(fn, ast.FunctionDef):
            continue
        for node in ast.walk(fn):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_run"
                    and any(k.arg == "write" and isinstance(k.value, ast.Constant) and k.value.value is True
                            for k in node.keywords)):
                out.add(fn.name)
    return frozenset(out) | _L1_PRIVATE_WRITERS


def _l1_aliases(tree):
    """本檔把 L1 設定試算表模組叫做什麼（`from repositories import settings_sheet_repository as store` 之類）。"""
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "repositories":
            names |= {a.asname or a.name for a in node.names if a.name == "settings_sheet_repository"}
        elif isinstance(node, ast.Import):
            names |= {a.asname or a.name for a in node.names if a.name == L1_SETTINGS_MODULE}
    return names


def _short_circuit_index(fn):
    """`if store.is_read_only(): return ...` 在函式本體的第幾句（沒有 → None）。"""
    for i, stmt in enumerate(fn.body):
        if (isinstance(stmt, ast.If) and "is_read_only()" in ast.unparse(stmt.test)
                and stmt.body and isinstance(stmt.body[-1], ast.Return)):
            return i
    return None


def _l1_write_problems(source: str, rel: str, writers) -> list:
    """一個檔裡對 L1 寫入函式的違規呼叫／import。唯二放行（休眠的 `user_setting` 存檔路徑，且只在 settings_store）：
    (1) `store.save_user_setting(...)` 只能出現在 L2 同名函式 `save_user_setting` 本體；
    (2) L2 `save_user_setting(...)` 只能由 `save_setting_for_page` 在 `is_read_only()` 短路**之後**呼叫。"""
    tree = ast.parse(source)
    aliases = _l1_aliases(tree)
    parents = _parents(tree)
    problems = []

    def enclosing_fn(node):
        while node in parents:
            node = parents[node]
            if isinstance(node, ast.FunctionDef):
                return node
        return None

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == L1_SETTINGS_MODULE:
            for a in node.names:
                if a.name in writers:
                    problems.append(f"{rel}:{node.lineno} from {node.module} import {a.name}")
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        fn = enclosing_fn(node)
        # 接收者：別名（`store.x(...)`）或全路徑（`import repositories.settings_sheet_repository` 後的
        # `repositories.settings_sheet_repository.x(...)`；2026-10-26 獨立稽核建議補）。
        # ⚠️ 已知限制：`getattr(store, "open_fetch_log")(...)` 之類的動態取用不在偵測範圍。
        receiver = ast.unparse(f.value) if isinstance(f, ast.Attribute) else ""
        if isinstance(f, ast.Attribute) and (receiver in aliases or receiver == L1_SETTINGS_MODULE) \
                and f.attr in writers:
            ok = (rel == "services/v2_tables/settings_store.py" and f.attr == "save_user_setting"
                  and fn is not None and fn.name == "save_user_setting" and receiver in aliases)
            if not ok:
                problems.append(f"{rel}:{node.lineno} 呼叫 L1 寫入 {receiver}.{f.attr}(")
        elif isinstance(f, ast.Attribute) and f.attr == "save_user_setting":
            problems.append(f"{rel}:{node.lineno} 經別的模組呼叫 save_user_setting（{ast.unparse(f)}）")
        elif isinstance(f, ast.Name) and f.id == "save_user_setting":
            gate = _short_circuit_index(fn) if fn is not None else None
            top = node
            while fn is not None and parents.get(top) is not fn:
                top = parents[top]
            ok = (rel == "services/v2_tables/settings_store.py" and fn is not None
                  and fn.name == "save_setting_for_page" and gate is not None
                  and fn.body.index(top) > gate)
            if not ok:
                problems.append(f"{rel}:{node.lineno} save_user_setting 不在 is_read_only 短路之後")
    return problems


def test_l1_write_function_list_is_derived_and_complete():
    writers = _l1_write_functions()
    assert _L1_KNOWN_WRITERS <= writers, writers
    assert not ({"new_fetch_log_open", "fetch_log_row", "merge_market_indicator", "load_fetch_log",
                 "load_market_indicator", "load_user_settings"} & writers)


def test_no_settings_sheet_l1_write_calls():
    """2026-10-26 裁示第 6 節：SET-5 重新取數零寫入 —— ui_v2／services/v2_tables 不得呼叫 `open_fetch_log`、
    `close_fetch_log`、`append_market_indicator` 等；`save_user_setting` 只留休眠路徑（見 `_l1_write_problems`）。"""
    writers = _l1_write_functions()
    hits = []
    for path in _files():
        rel = path.relative_to(ROOT).as_posix()
        hits += _l1_write_problems(path.read_text(encoding="utf-8"), rel, writers)
    assert not hits, "設定試算表 L1 寫入呼叫：\n" + "\n".join(hits)


def test_l1_write_detector_catches_synthetic_violations():
    """負控（現編程式碼，不落檔）：把任一寫入加回、或把存檔移到短路之前，偵測器就抓得到。"""
    writers = _l1_write_functions()
    rel = "services/v2_tables/settings_store.py"
    head = "from repositories import settings_sheet_repository as store\n"
    ok = (head + "def save_user_setting(k):\n    return store.save_user_setting(k)\n"
          "def save_setting_for_page(k):\n    if store.is_read_only():\n        return 1\n"
          "    return save_user_setting(k)\n")
    assert _l1_write_problems(ok, rel, writers) == []
    for bad in ("def refetch(x):\n    store.open_fetch_log('市場指標', mask=x)\n",
                "def refetch(x):\n    store.close_fetch_log({}, outcome='ok', row_count=0, message=None, mask=x)\n",
                "def refetch(x):\n    store.append_market_indicator([], mask=x)\n",
                "def other(k):\n    return store.save_user_setting(k)\n"):
        assert _l1_write_problems(head + bad, rel, writers), bad
    early = ok.replace("    if store.is_read_only():\n        return 1\n    return save_user_setting(k)\n",
                       "    save_user_setting(k)\n    if store.is_read_only():\n        return 1\n")
    assert _l1_write_problems(early, rel, writers)
    assert _l1_write_problems("from repositories.settings_sheet_repository import open_fetch_log\n", rel, writers)
    assert _l1_write_problems("import x\nx.settings_store.save_user_setting(1)\n", "ui_v2/a.py", writers)
    full = ("import repositories.settings_sheet_repository\n"
            "def refetch(x):\n    repositories.settings_sheet_repository.open_fetch_log('市場指標', mask=x)\n")
    assert _l1_write_problems(full, rel, writers)
    assert _l1_write_problems(full.replace("open_fetch_log", "append_market_indicator"), "ui_v2/a.py", writers)


def test_detectors_catch_synthetic_violations():
    """負控：掃描器本身要抓得到（用現編程式碼，不落檔）。"""
    tree = ast.parse("from repositories.pool_repository import add_or_update\nws.append_rows(x)\n")
    imp = [n for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)][0]
    assert imp.module.startswith(WRITE_MODULES) and imp.names[0].name in KNOWN_WRITE_FUNCTIONS
    call = [n for n in ast.walk(tree) if isinstance(n, ast.Call)][0]
    assert call.func.attr in GSPREAD_WRITE_UNAMBIGUOUS


# ───────── 開關行為 ─────────
from services.v2_tables import settings_store as ss  # noqa: E402


class _FakeStore:
    """記錄對 L1 `save_user_setting` 的呼叫次數（只替換這一個函式，其餘沿用真 L1 模組）。"""

    def __init__(self):
        self.calls = 0

    def save_user_setting(self, key, value, kind, mask=None):
        self.calls += 1
        return {"key": key}


@pytest.fixture
def fake_store(monkeypatch):
    fake = _FakeStore()
    monkeypatch.setattr(ss.store, "save_user_setting", fake.save_user_setting)
    return fake


def _set_flag(monkeypatch, value):
    monkeypatch.setattr(
        ss.store, "get_secret",
        lambda key, default=None: value if key == ss.store.READ_ONLY_SECRET_KEY else default)


# 2026-10-26 客戶裁示第 7 節（預設唯讀）：`is_read_only()` 恆為 True，任何旗標值都不能讓它變可寫。
# ~~`test_read_only_non_string_false`／`test_read_only_false_keeps_current_path`（假值、未設定 → False、走現行寫入路徑）~~
# —— 有意識的行為變更，不是漏刪（決策者：客戶 2026-10-26）：那兩條釘的是 #1059「預設可寫、可關」的舊行為；
# 現改為斷言同一組旗標值一律唯讀、repository 零呼叫。休眠中的寫入路徑另以 monkeypatch 模擬（`test_dormant_write_path_*`）。
_ALL_FLAGS = ["1", "true", " TRUE ", "Yes", "on", True, 1,
              "", "0", "false", "maybe", None, False, 0, 2, -1, 1.0, ["1"]]


@pytest.mark.parametrize("flag", _ALL_FLAGS)
def test_read_only_always_true_whatever_the_flag(monkeypatch, fake_store, flag):
    _set_flag(monkeypatch, flag)
    assert ss.store.is_read_only() is True
    out = ss.save_setting_for_page("k", "5", "int", {})
    assert out == {"status": "read_only", "key": "k", "message": ss.READ_ONLY_MESSAGE}
    assert fake_store.calls == 0


def test_read_only_when_flag_unset(monkeypatch, fake_store):
    """旗標完全沒設（`get_secret` 回預設值）。"""
    monkeypatch.setattr(ss.store, "get_secret", lambda key, default=None: default)
    assert ss.store.is_read_only() is True
    assert ss.save_setting_for_page("k", "5", "int", {})["status"] == "read_only"
    assert fake_store.calls == 0


def test_is_read_only_does_not_read_any_flag():
    """結構守衛：`is_read_only` 不讀任何秘密值／環境變數（有人加回旗標解析就轉紅）。"""
    src = (ROOT / "repositories" / "settings_sheet_repository.py").read_text(encoding="utf-8")
    fn = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == "is_read_only")
    body = [n for n in fn.body if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant))]
    assert len(body) == 1 and isinstance(body[0], ast.Return)
    assert isinstance(body[0].value, ast.Constant) and body[0].value.value is True


def test_dormant_write_path_still_works_when_read_only_lifted(monkeypatch, fake_store):
    """休眠寫入路徑：唯讀解除（monkeypatch）時照舊交 L1 —— 寫入函式本體保留為休眠能力。"""
    monkeypatch.setattr(ss.store, "is_read_only", lambda: False)
    out = ss.save_setting_for_page("k", "5", "int", {})
    assert out["status"] == "saved"
    assert fake_store.calls == 1


# ───────── set 頁：read_only 不得靜默（不需 streamlit 的最小層；整頁版見 test_set_live_logic，CI 才跑得到） ─────────
def test_set_live_read_only_surfaces_message():
    live = pytest.importorskip("ui_v2.set.live")
    result = {"status": "read_only", "key": "k", "message": ss.READ_ONLY_MESSAGE, "attempted": "21"}
    out = live.dataset_with_save_results({"save_inputs": {}, "save_errors": {}}, {"k": result})
    assert out["save_errors"]["k"] == ss.READ_ONLY_MESSAGE
    assert out["save_inputs"]["k"] == "21"
    lines = live._save_fail_lines(result, "")
    assert ss.READ_ONLY_MESSAGE in lines[0]
    assert live.TEXT_SAVE_MAYBE_WRITTEN not in lines


# ═════════ 2026-10-26 裁示第 7 節：五頁正式模式第一階段不畫寫入控制（`ui_v2/readonly.py`） ═════════
# 依據：客戶 2026-10-26 正式裁示第 6、7 節；`DEC-2026-10-25-04` J-6、2026-10-26 J-14 補記（`SET-4` 不出現）。
# 兩層：(甲) 模型層 —— `readonly.strip_write_controls` 真的拿掉每一枚寫 `user_setting` 的按鈕、說明不再叫人存檔；
#       (乙) AST —— 五頁正式模式的渲染路徑真的接上它（拿掉接線點、或把它移到畫塊之後，就轉紅）。
from ui_v2 import plain, readonly  # noqa: E402
from ui_v2.alo import fixtures as alo_fx, live as alo_live, logic as alo_logic  # noqa: E402
from ui_v2.exp import fixtures as exp_fx, live as exp_live, logic as exp_logic  # noqa: E402
from ui_v2.hld import fixtures as hld_fx, live as hld_live, logic as hld_logic  # noqa: E402
from ui_v2.mkt import fixtures as mkt_fx, live as mkt_live, logic as mkt_logic  # noqa: E402
from ui_v2.set import fixtures as set_fx, logic as set_logic  # noqa: E402

PAGES = ("mkt", "hld", "alo", "exp", "set")


def _demo_models():
    """各頁一份帶全部存檔鈕的模型（示範情境；正式模式的按鈕清單由同一支 `logic._button` 組出）。"""
    exp_params = dict(exp_fx.scenario_with("full", save_failed=False))
    exp_dataset = exp_params.pop("dataset")
    return {
        "mkt": mkt_logic.build_page_model(mkt_fx.dataset_all_ok()),
        "hld": hld_logic.build_page_model(hld_fx.dataset_full()),
        "exp": exp_logic.build_page_model(exp_dataset, save_failed=False, **exp_params),
        "alo": alo_logic.build_page_model(alo_fx.scenario_with("full", save_failed=False)),
        "set": set_logic.build_page_model(set_fx.scenario_with("ok", save_failed=False)),
    }


def _button_nodes(node):
    if isinstance(node, dict):
        if "_action_kind" in node:
            yield node
        for value in node.values():
            yield from _button_nodes(value)
    elif isinstance(node, (list, tuple)):
        for item in node:
            yield from _button_nodes(item)


def test_write_controls_constant_is_off_and_not_configurable():
    """開關是常數 False，readonly.py 不讀任何旗標（除 `__future__` 外不 import 任何東西）。"""
    assert readonly.WRITE_CONTROLS_ENABLED is False
    tree = _tree(ROOT / "ui_v2" / "readonly.py")
    imported = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    imported |= {(n.module or "").split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert imported <= {"__future__"}, imported
    assigns = [n for n in tree.body if isinstance(n, ast.Assign)
               and any(isinstance(t, ast.Name) and t.id == "WRITE_CONTROLS_ENABLED" for t in n.targets)]
    assert len(assigns) == 1 and isinstance(assigns[0].value, ast.Constant) and assigns[0].value.value is False
    assert readonly.PHASE1_HIDDEN_CODES == {"SET-4"}


@pytest.mark.parametrize("page", PAGES)
def test_every_page_has_save_buttons_before_strip_and_none_after(page):
    model, _raw, _status = plain.plain_model(_demo_models()[page], page=page)
    before = [b for b in _button_nodes(model) if readonly.is_write_control(b)]
    assert before, f"{page}：拿掉之前就沒有存檔鈕，這條測試量不到東西"
    assert all(b["_action_kind"] == "存檔" for b in before)
    # 鍵穩定：寫入鈕一律在該塊按鈕清單的最後（拿掉後其他按鈕的序號 key 不變；畫面層用序號當 key）。
    for block in model["blocks"]:
        kinds = [readonly.is_write_control(b) for b in block.get("buttons") or ()]
        assert kinds == sorted(kinds), f"{page} {block['code']}：寫入鈕不在最後，拿掉會讓其他按鈕換 key"
    # 寫入鈕只出現在各塊的 `buttons` 清單（strip 只看這一層）。
    in_lists = sum(readonly.is_write_control(b) for blk in model["blocks"] for b in blk.get("buttons") or ())
    assert in_lists == len(before)
    readonly.strip_write_controls(model)
    assert model["_readonly_stripped"] == len(before)
    assert not [b for b in _button_nodes(model) if readonly.is_write_control(b)]
    assert not [b for b in _button_nodes(model) if b["_action_kind"] == "存檔"]


def test_strip_is_a_noop_when_controls_enabled(monkeypatch):
    """突變靈敏度：開關打開（模擬休眠寫入路徑）時一枚都不拿 —— 上一條量的確實是開關。"""
    monkeypatch.setattr(readonly, "WRITE_CONTROLS_ENABLED", True)
    model = _demo_models()["hld"]
    n = sum(readonly.is_write_control(b) for b in _button_nodes(model))
    readonly.strip_write_controls(model)
    assert n and model["_readonly_stripped"] == 0
    assert sum(readonly.is_write_control(b) for b in _button_nodes(model)) == n
    assert readonly.visible_codes(["SET-3", "SET-4"]) == ["SET-3", "SET-4"]


def test_visible_codes_hides_set4_only():
    assert readonly.visible_codes(["SET-3", "SET-4", "SET-5"]) == ["SET-3", "SET-5"]
    assert readonly.visible_codes(("SET-6", "SET-7")) == ["SET-6", "SET-7"]


# 會變成假話的說明：每一條改寫都要真的打到它的來源句（沒有死條目），改完不再叫人存檔。
_REWRITE_SOURCES = [
    ("mkt", "MKT-1", mkt_logic.TEXT_INCOMPLETE_INCONSISTENT, "⬜ 設定不完整：比較條件不一致"),
    ("mkt", "MKT-7", mkt_logic.TEXT_UNSAVED_NONE, "尚未選定任何指標"),
    # ~~期望值「勾選只決定下方指標明細顯示哪些指標；三張核心卡固定顯示。」~~ → 2026-10-26（J-14 精神）`MKT-5` 多選清單不畫，
    # 「勾選」改成不暗示可改的說法（`readonly.PHASE1_HIDDEN_INPUT_TEXT`；有意識的更正，不是漏刪）。
    ("mkt", "MKT-5", "勾選只決定下方指標明細顯示哪些指標；三張核心卡固定顯示。存檔後，下一次重新載入才生效。",
     "下方指標明細只顯示已存的指標；三張核心卡固定顯示。"),
    # ~~期望值「欄位的觀察窗與比較基準日和已存值不同」「勾選與已存清單不同」~~ → 2026-10-26：輸入元件不畫之後，
    # 「和已存值不同」指的是看不到的欄位 ⇒ 整句拿掉（期望值 "" ＝ 該行從清單移除；下同 exp 兩句）。
    ("mkt", "MKT-4", mkt_live.TEXT_UNSAVED_WINDOW, ""),
    ("mkt", "MKT-5", mkt_live.TEXT_UNSAVED_PICKS, ""),
    ("hld", "HLD-4", hld_live.TEXT_APPLY_NOT_SHOWN, "畫面上的結果只讀已存的設定。"),
    ("hld", "HLD-4", hld_logic.HLD4_SAVE_SCOPE_NOTE,
     "本頁不寫持倉、保單、淨值、配息四張表任何一張，也不代你填任何值、不把空欄補成任何候選值。"),
    ("alo", "ALO-4", alo_live.TEXT_ALO4_SHEETS, "類別在 Sheets 維護"),
    ("exp", "EXP-1", exp_logic.TEXT_UNSAVED_RULES, ""),
    ("exp", "EXP-4", exp_live.TEXT_UNSAVED_EXP4, ""),
    # ~~期望值 None（只驗不再叫人存檔）~~ → 2026-10-26：勾選框不畫之後連「取消勾基金名」那半句一併拿掉，釘住全文。
    ("exp", "EXP-4", exp_logic.LIVE_DEV_NOTE_EDITS[exp_logic.TEXT_EXP4_LIVE],
     "候選清單只吃已存的設定。正式模式的候選清單另有 基金代碼 一欄可辨認每一列。"),
    ("exp", "EXP-4", "本塊不提供推薦欄位組合；「存檔」只寫 user_setting，不寫入 holding、policy、nav、dividend（G1†）。",
     "本塊不提供推薦欄位組合；本頁不寫入 持倉、保單、淨值、配息。"),
]


@pytest.mark.parametrize("page, code, source_text, expected", _REWRITE_SOURCES)
def test_text_rewrites_hit_their_source_and_stop_asking_to_save(page, code, source_text, expected):
    shown = plain.plain_text(source_text, page=page, code=code)
    model = {"blocks": [{"code": code, "detail_lines": [shown]}]}
    readonly.strip_write_controls(model)
    lines = model["blocks"][0]["detail_lines"]
    assert "存檔" in shown and lines != [shown], f"改寫表沒有打到這一句：{shown}"
    if expected == "":
        assert lines == []          # 2026-10-26：整句拿掉，不留空行
        return
    out = lines[0]
    assert "存檔" not in out
    if expected is not None:
        assert out == expected


def test_every_rewrite_rule_is_used():
    """改寫表每一條都至少打到上面一句來源（沒有死條目）。"""
    shown = [plain.plain_text(t, page=p, code=c) for p, c, t, _e in _REWRITE_SOURCES]
    for old, _new in readonly.PHASE1_TEXT_REWRITES:
        assert any(old in text for text in shown), f"死條目：{old}"


def test_state_sentence_kept():
    """描述狀態的句子不改（只改「叫人存檔／承諾存檔後生效」的那一段）。"""
    model = {"blocks": [{"code": "MKT-5", "detail_lines": [mkt_logic.TEXT_SHOW_ALL_UNSAVED]}]}
    readonly.strip_write_controls(model)
    assert model["blocks"][0]["detail_lines"] == [mkt_logic.TEXT_SHOW_ALL_UNSAVED]


# ───────── (乙) AST：五頁正式模式的渲染路徑真的接上 `readonly` ─────────
_LIVE_RENDER_FN = {"mkt": "render", "hld": "render", "alo": "render", "exp": "_render_live", "set": "render"}
# 這幾種 `if` 為真時是示範模式；接線點不得落在它的 body 裡。
_DEMO_TESTS = ("load_live is None", "live_input is None")


def _parents(tree):
    out = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            out[child] = node
    return out


def _is_strip_call(node):
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == "strip_write_controls"
            and isinstance(node.func.value, ast.Name) and node.func.value.id == "readonly")


def _is_render_call(node):
    """畫一塊的呼叫：`_render_xxx(...)`、`_RENDERERS[code](...)`。"""
    if not isinstance(node, ast.Call):
        return False
    f = node.func
    if isinstance(f, ast.Name) and f.id.startswith("_render_"):
        return True
    return isinstance(f, ast.Subscript) and isinstance(f.value, ast.Name) and f.value.id == "_RENDERERS"


def _strip_problems(source: str, fn_name: str) -> list:
    tree = ast.parse(source)
    fn = next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == fn_name), None)
    if fn is None:
        return [f"找不到 {fn_name}"]
    parents = _parents(tree)
    strips = [n for n in ast.walk(fn) if _is_strip_call(n)]
    if len(strips) != 1:
        return [f"{fn_name} 內 readonly.strip_write_controls 呼叫 {len(strips)} 處（應為 1）"]
    strip = strips[0]
    problems = []
    node = strip
    while node is not fn:
        parent = parents[node]
        if isinstance(parent, ast.If) and ast.unparse(parent.test) in _DEMO_TESTS and node in parent.body:
            problems.append("接線點落在示範模式分支裡")
        node = parent
    # 錯誤畫面（`except` 裡的 `_render_live_error`、`_render_advanced_diag`）在載入或組模型失敗時才畫、畫完就 return，不算畫塊。
    def in_except(n):
        while n is not fn:
            n = parents[n]
            if isinstance(n, ast.ExceptHandler):
                return True
        return False

    renders = [n.lineno for n in ast.walk(fn) if _is_render_call(n) and not in_except(n)]
    if not renders:
        problems.append("找不到任何畫塊呼叫")
    elif strip.lineno > min(renders):
        problems.append(f"接線點（第 {strip.lineno} 行）在第一個畫塊呼叫（第 {min(renders)} 行）之後")
    return problems


# → 2026-10-30 BL-0525 Batch D（`DEC-2026-10-30-02`；有意識的更正，不是漏刪）：`hld`、`alo` 的「載入→組模型→收集→收合判定→
#   `readonly.strip_write_controls`」整段從 `render` 原樣抽進 `prepare_live`（單頁 `render` 與合併頁共用）。舊守衛的兩個性質照舊成立、
#   只是分成兩半驗：(1) `prepare_live` 內恰一處 strip、不在示範分支裡；(2) 單頁 `render` 在**第一個畫塊呼叫之前**先呼叫 `prepare_live`
#   （且是正式模式分支）；合併頁 `ui_v2/asset/page.py::_render` 同樣在第一個畫塊呼叫之前就把兩側 `prepare_live` 都跑完（`_prepare`）。
_PREPARED_PAGES = ("hld", "alo")


def _calls_before_first_render(source: str, fn_name: str, callee: str, *, live_branch: bool = False) -> list:
    """`callee` 的每一次呼叫都在第一個畫塊呼叫之前。`live_branch=True`（單頁 `render`）：另要求每一次呼叫都在正式模式分支——
    不得落在示範模式 `if`（`_DEMO_TESTS`）的 body 裡（示範模式不經 `prepare_live`，落在那裡等於正式路徑沒走到收起／唯讀那一整段）。"""
    tree = ast.parse(source)
    fn = next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == fn_name), None)
    if fn is None:
        return [f"找不到 {fn_name}"]
    parents = _parents(tree)

    def in_except(n):
        while n is not fn:
            n = parents[n]
            if isinstance(n, ast.ExceptHandler):
                return True
        return False

    def calls(name):
        return [n.lineno for n in ast.walk(fn) if isinstance(n, ast.Call)
                and ((isinstance(n.func, ast.Name) and n.func.id == name)
                     or (isinstance(n.func, ast.Attribute) and n.func.attr == name))]

    prepared = calls(callee)
    renders = [n.lineno for n in ast.walk(fn) if _is_render_call(n) and not in_except(n)]
    if not prepared:
        return [f"{fn_name} 沒有呼叫 {callee}"]
    if live_branch:
        for call in (n for n in ast.walk(fn) if isinstance(n, ast.Call) and n.lineno in prepared
                     and ((isinstance(n.func, ast.Name) and n.func.id == callee)
                          or (isinstance(n.func, ast.Attribute) and n.func.attr == callee))):
            node = call
            while node is not fn:
                parent = parents[node]
                if isinstance(parent, ast.If) and ast.unparse(parent.test) in _DEMO_TESTS and node in parent.body:
                    return [f"{callee} 的呼叫（第 {call.lineno} 行）落在示範模式分支裡"]
                node = parent
    if not renders:
        return ["找不到任何畫塊呼叫"]
    if max(prepared) > min(renders):
        return [f"{callee} 的呼叫（第 {max(prepared)} 行）在第一個畫塊呼叫（第 {min(renders)} 行）之後"]
    return []


@pytest.mark.parametrize("page", PAGES)
def test_live_render_path_strips_write_controls_before_rendering(page):
    source = (ROOT / "ui_v2" / page / "page.py").read_text(encoding="utf-8")
    if page in _PREPARED_PAGES:
        assert _strip_problems_prepare(source) == []
        assert _calls_before_first_render(source, _LIVE_RENDER_FN[page], "prepare_live", live_branch=True) == []
        return
    assert _strip_problems(source, _LIVE_RENDER_FN[page]) == []


def _strip_problems_prepare(source: str) -> list:
    """`prepare_live` 內恰一處 `readonly.strip_write_controls`、不落在示範分支裡（`prepare_live` 本身不含畫塊呼叫，順序性質由另一半驗）。"""
    tree = ast.parse(source)
    fn = next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "prepare_live"), None)
    if fn is None:
        return ["找不到 prepare_live"]
    strips = [n for n in ast.walk(fn) if _is_strip_call(n)]
    if len(strips) != 1:
        return [f"prepare_live 內 readonly.strip_write_controls 呼叫 {len(strips)} 處（應為 1）"]
    if any(_is_render_call(n) for n in ast.walk(fn)):
        return ["prepare_live 內不得有畫塊呼叫（畫塊屬 render）"]
    return []


def test_合併頁_兩側prepare_live都在第一個畫塊呼叫之前跑完_且只經prepare_live取模型():
    source = (ROOT / "ui_v2" / "asset" / "page.py").read_text(encoding="utf-8")
    assert _calls_before_first_render(source, "_render", "_prepare") == []
    tree = ast.parse(source)
    prepare = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_prepare")
    called = {ast.unparse(c.func) for c in ast.walk(prepare) if isinstance(c, ast.Call)}
    assert "page_mod.prepare_live" in called                      # 合併頁自己不建模型、不呼叫 build_page_model／build_live_model
    for banned in ("build_page_model", "build_live_model", "strip_write_controls"):
        assert banned not in source, banned


def test_set_page_hides_set4_in_live_layers():
    """set 頁正式模式層 3／層 4 的迴圈經 `readonly.visible_codes`（`SET-4` 整塊不畫）。"""
    tree = _tree(ROOT / "ui_v2" / "set" / "page.py")
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "render")
    loops = [ast.unparse(n.iter) for n in ast.walk(fn) if isinstance(n, ast.For)]
    assert any("readonly.visible_codes(layer3) if plain_mode" in it for it in loops), loops
    assert any("readonly.visible_codes(layer4) if plain_mode" in it for it in loops), loops
    # 塊代號表裡 `SET-4` 照舊在層 3（不是因為搬了層才沒畫）。
    model = set_logic.build_page_model(set_fx.scenario_with("ok", save_failed=False))
    assert "SET-4" in set_logic.codes_in_layer(model, 3) + set_logic.codes_in_layer(model, 4)


def test_prepare_live呼叫須在正式模式分支_負控偵測得到落在示範分支或畫塊之後():
    """負控（現編程式碼，不落檔）：`live_branch=True` 抓得到 `prepare_live` 落在 `if load_live is None:` 的 body 裡。"""
    ok = ("def render(load_live=None):\n"
          "    if load_live is None:\n        model = 1\n"
          "    else:\n        prep = prepare_live(load_live=load_live)\n"
          "    _render_x(1)\n")
    assert _calls_before_first_render(ok, "render", "prepare_live", live_branch=True) == []
    in_demo = ("def render(load_live=None):\n"
               "    if load_live is None:\n        prep = prepare_live(load_live=load_live)\n"
               "    else:\n        model = 2\n"
               "    _render_x(1)\n")
    assert _calls_before_first_render(in_demo, "render", "prepare_live", live_branch=True)
    assert _calls_before_first_render(in_demo, "render", "prepare_live") == []          # 沒開 live_branch 時只驗順序（舊行為不變）
    late = ("def render(load_live=None):\n"
            "    _render_x(1)\n"
            "    if load_live is not None:\n        prep = prepare_live(load_live=load_live)\n")
    assert _calls_before_first_render(late, "render", "prepare_live", live_branch=True)


def test_ast_detector_catches_missing_or_late_strip():
    """負控：偵測器本身抓得到（現編程式碼，不落檔）。"""
    ok = ("def render(load_live=None):\n"
          "    if load_live is None:\n        model = 1\n"
          "    else:\n        model = 2\n        readonly.strip_write_controls(model)\n"
          "    _render_x(model)\n")
    assert _strip_problems(ok, "render") == []
    missing = ok.replace("        readonly.strip_write_controls(model)\n", "")
    assert _strip_problems(missing, "render")
    late = missing + "    readonly.strip_write_controls(model)\n"
    assert _strip_problems(late, "render")
    demo_only = ("def render(load_live=None):\n"
                 "    if load_live is None:\n        readonly.strip_write_controls(1)\n"
                 "    _render_x(1)\n")
    assert _strip_problems(demo_only, "render")


# ═════════ 2026-10-26（J-14 精神）：存檔鈕拿掉後已無作用、但仍顯示的輸入元件，正式模式不畫 ═════════
# 依據：`DEC-2026-10-25-04` J-14（第一階段不出現暗示可修改的控制項）；各頁正式結果只讀已存設定
# （mkt／hld／exp `live.build_live_model`、alo `logic.build_page_model(dataset)`），這幾組輸入只影響存檔與「和已存值不同」提示。
# 保留：`ALO-3` 試算、`EXP-3`／`EXP-6` 的「對照」多選（會即時改畫面）。
# 兩層：(甲) 模型層 —— 旗標、改輸入列的按鈕拿掉；(乙) 執行期 —— 以記錄器替換 `st` 真的跑各塊渲染函式，輸入元件零枚
# （負控：同一塊不經 `strip_write_controls` 時 > 0）；(丙) AST —— 渲染函式裡每一個輸入元件呼叫都在 `inputs_hidden` 的條件之下。
HIDDEN_INPUT_CODES = {"MKT-4", "MKT-5", "HLD-4", "EXP-1", "EXP-4", "EXP-5", "ALO-1", "ALO-4"}


def _plain_models():
    return {page: plain.plain_model(model, page=page)[0] for page, model in _demo_models().items()}


def test_hidden_input_codes_are_exactly_the_audited_list():
    assert readonly.PHASE1_HIDDEN_INPUT_CODES == HIDDEN_INPUT_CODES
    assert not ({"ALO-3", "EXP-2", "EXP-3", "EXP-6", "SET-5"} & readonly.PHASE1_HIDDEN_INPUT_CODES)


def test_strip_flags_hidden_input_blocks_and_drops_row_edit_buttons():
    models = _plain_models()
    edit_before = sum(1 for m in models.values() for blk in m["blocks"] if blk["code"] in HIDDEN_INPUT_CODES
                      for b in list(blk.get("buttons") or ()) + list(blk.get("row_buttons") or ())
                      if b["_action_kind"] in readonly.INPUT_EDIT_KINDS)
    assert edit_before > 0, "拿掉之前就沒有新增列／清除鈕，這條量不到東西"
    seen = set()
    for model in models.values():
        readonly.strip_write_controls(model)
        for blk in model["blocks"]:
            if blk["code"] in HIDDEN_INPUT_CODES:
                seen.add(blk["code"])
                assert readonly.inputs_hidden(blk) is True
                assert not [b for b in blk.get("buttons") or () if b["_action_kind"] in readonly.INPUT_EDIT_KINDS]
                assert blk.get("row_buttons", []) == []
            else:
                assert not readonly.inputs_hidden(blk), blk["code"]
        assert set(model["_readonly_inputs_hidden"]) <= HIDDEN_INPUT_CODES
    assert seen == HIDDEN_INPUT_CODES


def test_hidden_inputs_noop_when_controls_enabled(monkeypatch):
    monkeypatch.setattr(readonly, "WRITE_CONTROLS_ENABLED", True)
    model = _plain_models()["exp"]
    readonly.strip_write_controls(model)
    assert model["_readonly_inputs_hidden"] == []
    assert not any(readonly.inputs_hidden(blk) for blk in model["blocks"])
    assert readonly.hides_inputs("EXP-5") is False


def test_hidden_input_text_rules_hit_and_drop_empty_lines():
    model = {"blocks": [{"code": "EXP-5", "summary_text": exp_logic.TEXT_NO_PICK, "detail_lines": []},
                        {"code": "EXP-3", "summary_text": exp_logic.TEXT_NO_PICK, "detail_lines": []},
                        {"code": "EXP-1", "notes": ["尚未新增任何條件列。"], "detail_lines": []},
                        {"code": "ALO-1", "intro_line": "目標在這裡輸入；對照與試算在上方「關鍵數字」。"}]}
    readonly.strip_write_controls(model)
    exp5, exp3, exp1, alo1 = model["blocks"]
    assert exp5["summary_text"] == "本頁唯讀" and exp3["summary_text"] == exp_logic.TEXT_NO_PICK   # 只改該塊
    assert exp1["notes"] == ["沒有已存的條件列。"]
    assert alo1["intro_line"] == "對照與試算在上方「關鍵數字」。"


# ───────── (乙) 執行期：記錄器替換 `st`，真的跑各塊渲染函式 ─────────
INPUT_WIDGETS = frozenset({"text_input", "number_input", "date_input", "multiselect", "checkbox", "selectbox",
                           "radio", "text_area", "slider", "toggle", "data_editor", "select_slider"})


class _Recorder:
    """極簡 `st` 替身：記下每一次呼叫（名稱、key），容器類回自己（可 `with`）。"""

    def __init__(self):
        self.calls = []
        self.session_state = {}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def columns(self, spec, **_kw):
        n = spec if isinstance(spec, int) else len(spec)
        return [self for _ in range(n)]

    def __getattr__(self, name):
        def call(*args, **kwargs):
            self.calls.append((name, kwargs.get("key")))
            return None if name in INPUT_WIDGETS or name == "button" else self
        return call

    def inputs(self):
        return [c for c in self.calls if c[0] in INPUT_WIDGETS]

    def row_edit_buttons(self):
        return [c for c in self.calls if c[0] == "button" and c[1] and ("_row_" in c[1] or "_clear_" in c[1])]


def _render_cases():
    pytest.importorskip("streamlit")
    from ui_v2.alo import page as alo_page
    from ui_v2.exp import page as exp_page
    from ui_v2.hld import page as hld_page
    from ui_v2.mkt import page as mkt_page

    def exp1_rows(blk):
        return [{"_id": i, "field": "", "op": "", "value": ""} for i in range(len(blk["_rows"]))]

    return {
        "MKT-4": (mkt_page, lambda blk: mkt_page._render_mkt4(blk, live_mode=True, save_click=None)),
        "MKT-5": (mkt_page, lambda blk: mkt_page._render_mkt5(blk, save_click=(None, ()), plain_mode=True)),
        "HLD-4": (hld_page, lambda blk: hld_page._render_hld4(blk, on_save=None, plain_mode=True)),
        "EXP-1": (exp_page, lambda blk: exp_page._render_exp1_live(blk, exp1_rows(blk), clicks={}, plain_mode=True)),
        "EXP-4": (exp_page, lambda blk: exp_page._render_exp4_live(blk, save_click=(None, ()), plain_mode=True)),
        "ALO-1": (alo_page, lambda blk: alo_page._render_alo1(blk, "live", None, plain_mode=True)),
        "ALO-4": (alo_page, lambda blk: alo_page._render_alo4(blk, "live", None, plain_mode=True)),
    }


_PAGE_OF = {"MKT": "mkt", "HLD": "hld", "EXP": "exp", "ALO": "alo"}


def _block_of(code, *, strip):
    model = _plain_models()[_PAGE_OF[code.split("-")[0]]]
    if strip:
        readonly.strip_write_controls(model)
    return next(b for b in model["blocks"] if b["code"] == code)


@pytest.mark.parametrize("code", ["MKT-4", "MKT-5", "HLD-4", "EXP-1", "EXP-4", "ALO-1", "ALO-4"])
def test_live_renderer_draws_zero_inputs_after_strip(monkeypatch, code):
    module, render = _render_cases()[code]
    before = _Recorder()
    monkeypatch.setattr(module, "st", before)
    render(_block_of(code, strip=False))
    assert before.inputs(), f"{code}：拿掉之前就沒畫任何輸入元件，這條量不到東西"
    after = _Recorder()
    monkeypatch.setattr(module, "st", after)
    render(_block_of(code, strip=True))
    assert after.inputs() == [], after.inputs()
    assert after.row_edit_buttons() == [], after.row_edit_buttons()


def test_exp_watch_picks_hidden_compare_picks_kept(monkeypatch):
    """`EXP-5` 的輸入（觀察清單多選）不畫；`EXP-3`／`EXP-6` 的「對照」多選會即時改畫面，照畫。"""
    _render_cases()
    from ui_v2.exp import page as exp_page
    exp2 = _block_of("EXP-2", strip=True)
    rec = _Recorder()
    monkeypatch.setattr(exp_page, "st", rec)
    exp_page._render_picks(exp2, hide_watch=False)
    keys_all = [k for name, k in rec.inputs() if name == "multiselect"]
    rec2 = _Recorder()
    monkeypatch.setattr(exp_page, "st", rec2)
    exp_page._render_picks(exp2, hide_watch=True)
    keys_hidden = [k for name, k in rec2.inputs() if name == "multiselect"]
    assert len(keys_all) == 2 and keys_hidden == [exp_page._PICK_KEYS[exp_logic.GROUP_COMPARE]]
    # 接線：正式頁傳的是 `EXP-5` 那一塊的旗標；組模型時 session 殘留的觀察清單勾選不交給模型。
    src = (ROOT / "ui_v2" / "exp" / "page.py").read_text(encoding="utf-8")
    assert '_render_exp2_live(exp2, hide_watch=readonly.inputs_hidden(logic.find_block(model, "EXP-5")))' in src
    assert 'watch_checked=() if readonly.hides_inputs("EXP-5") else' in src


# ───────── (丙) AST：渲染函式裡每一個輸入元件呼叫都在 `inputs_hidden` 的條件之下 ─────────
_GUARDED_RENDERERS = [
    ("mkt", "_render_mkt4"), ("mkt", "_render_mkt5_picks"), ("hld", "_render_hld4"),
    ("exp", "_render_exp1_live"), ("exp", "_render_exp4_live"), ("alo", "_render_alo1"), ("alo", "_render_alo4"),
]
_INPUT_HELPERS = frozenset({"_text_input", "_field_select"})


def _input_guard_problems(source: str, fn_name: str) -> list:
    tree = ast.parse(source)
    fn = next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == fn_name), None)
    if fn is None:
        return [f"找不到 {fn_name}"]
    parents = _parents(tree)
    hidden_names = {t.id for n in ast.walk(fn) if isinstance(n, ast.Assign) and "readonly.inputs_hidden(" in ast.unparse(n.value)
                    for t in n.targets if isinstance(t, ast.Name)}

    def guards(text):
        return "readonly.inputs_hidden(" in text or any(name in text.split() or f"not {name}" in text
                                                        or f"if {name}" in text for name in hidden_names)

    problems, found = [], 0
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", None)
        is_widget = (isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id == "st"
                     and name in INPUT_WIDGETS) or name in _INPUT_HELPERS
        if not is_widget:
            continue
        found += 1
        cur, ok = node, False
        while cur is not fn and not ok:
            parent = parents[cur]
            if isinstance(parent, ast.If) and cur in parent.body and guards(ast.unparse(parent.test)):
                ok = True
            elif isinstance(parent, ast.For) and cur in parent.body and guards(ast.unparse(parent.iter)):
                ok = True
            cur = parent
        if not ok:
            problems.append(f"{fn_name}:{node.lineno} 的 {name} 不在 inputs_hidden 條件之下")
    if not found:
        problems.append(f"{fn_name} 找不到任何輸入元件")
    return problems


@pytest.mark.parametrize("page, fn_name", _GUARDED_RENDERERS)
def test_input_widgets_sit_under_inputs_hidden(page, fn_name):
    source = (ROOT / "ui_v2" / page / "page.py").read_text(encoding="utf-8")
    assert _input_guard_problems(source, fn_name) == []


def test_input_guard_detector_catches_unguarded_widget():
    """負控（現編程式碼，不落檔）。"""
    ok = ("def f(block):\n    if not readonly.inputs_hidden(block):\n        st.text_input('a')\n")
    assert _input_guard_problems(ok, "f") == []
    ok2 = ("def f(block):\n    hidden = readonly.inputs_hidden(block)\n"
           "    for x in () if hidden else block['inputs']:\n        _text_input(x)\n")
    assert _input_guard_problems(ok2, "f") == []
    bad = "def f(block):\n    st.number_input('a')\n"
    assert _input_guard_problems(bad, "f")
    bad2 = ("def f(block):\n    if not readonly.inputs_hidden(block):\n        pass\n    st.multiselect('a')\n")
    assert _input_guard_problems(bad2, "f")
