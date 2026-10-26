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
GSPREAD_WRITE_ALLOWLIST = frozenset({"services/v2_tables/settings_store.py"})


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
    ("mkt", "MKT-5", "勾選只決定下方指標明細顯示哪些指標；三張核心卡固定顯示。存檔後，下一次重新載入才生效。",
     "勾選只決定下方指標明細顯示哪些指標；三張核心卡固定顯示。"),
    ("mkt", "MKT-4", mkt_live.TEXT_UNSAVED_WINDOW, "欄位的觀察窗與比較基準日和已存值不同"),
    ("mkt", "MKT-5", mkt_live.TEXT_UNSAVED_PICKS, "勾選與已存清單不同"),
    ("hld", "HLD-4", hld_live.TEXT_APPLY_NOT_SHOWN, "畫面上的結果只讀已存的設定。"),
    ("hld", "HLD-4", hld_logic.HLD4_SAVE_SCOPE_NOTE,
     "本頁不寫持倉、保單、淨值、配息四張表任何一張，也不代你填任何值、不把空欄補成任何候選值。"),
    ("alo", "ALO-4", alo_live.TEXT_ALO4_SHEETS, "類別在 Sheets 維護"),
    ("exp", "EXP-1", exp_logic.TEXT_UNSAVED_RULES, "條件列與已存值不同"),
    ("exp", "EXP-4", exp_live.TEXT_UNSAVED_EXP4, "欄位勾選或排序欄位與已存值不同"),
    ("exp", "EXP-4", exp_logic.LIVE_DEV_NOTE_EDITS[exp_logic.TEXT_EXP4_LIVE], None),
    ("exp", "EXP-4", "本塊不提供推薦欄位組合；「存檔」只寫 user_setting，不寫入 holding、policy、nav、dividend（G1†）。",
     "本塊不提供推薦欄位組合；本頁不寫入 持倉、保單、淨值、配息。"),
]


@pytest.mark.parametrize("page, code, source_text, expected", _REWRITE_SOURCES)
def test_text_rewrites_hit_their_source_and_stop_asking_to_save(page, code, source_text, expected):
    shown = plain.plain_text(source_text, page=page, code=code)
    model = {"blocks": [{"code": code, "detail_lines": [shown]}]}
    readonly.strip_write_controls(model)
    out = model["blocks"][0]["detail_lines"][0]
    assert "存檔" in shown and out != shown, f"改寫表沒有打到這一句：{shown}"
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


@pytest.mark.parametrize("page", PAGES)
def test_live_render_path_strips_write_controls_before_rendering(page):
    source = (ROOT / "ui_v2" / page / "page.py").read_text(encoding="utf-8")
    assert _strip_problems(source, _LIVE_RENDER_FN[page]) == []


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
