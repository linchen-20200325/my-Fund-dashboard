# -*- coding: utf-8 -*-
"""B 線預覽入口 `ui_v2/app_preview.py` 的靜態守衛（fast lane；純 AST，不需要 streamlit、pandas）。

客戶 2026-10-12 核准新增預覽入口。本檔釘住派工單的五件事（執行期的對應證據在
`tests/ui_v2/test_preview_page.py`，slow lane）：

- (a) 預覽入口不被 `app.py`／`ui/**`（以及 tests 以外任何正式程式）import；
- (b) ~~四頁~~ 五頁（2026-10-13 起標的探索也接上正式模式；狀態更新，不是漏刪）真資料傳給 `page.render` 的
      注入函式，與各自的 `ui_v2/app_<頁>_live.py` 逐一相同、不多不少；
      ~~標的探索與 `ui_v2/app_exp.py` 一樣不傳任何參數；~~
- (c) 預覽入口本身不 import、不引用任何 `fixtures`；
- (d) ~~標的探索那一頁在 `exp_page.render()` 之前先畫示意資料標示……~~ → 2026-10-13 撤下（狀態更新，不是漏刪）：
      標的探索接上正式資料，正式資料不加示意標示（比照 hld 2026-10-02）；改驗「預覽入口不再有示意資料標示」；
- 另：頁序與頁名逐字對 `docs/v2/44_fund_ui_ssot.md` 3.0 五頁總表；`st.set_page_config` 全樹只有
  預覽入口的 `main()` 呼叫一次；檔頭列的試算表 secret 鍵名與 L1 實際讀的鍵名相同；
  換頁要 pop 的狀態清單（資產配置引用 page 常數、市場總覽的字面值確實住在 mkt/page.py）；
  預覽入口不用 `getattr`／`__import__`／`importlib`／`globals()`；側邊欄說明的字面。

每一條都附正控（守衛真的抓得到），避免它在結構上就是空的。
"""

from __future__ import annotations

import ast
import pathlib
import re

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
_PREVIEW = _ROOT / "ui_v2" / "app_preview.py"
# ~~_LIVE_PAGES = ("mkt", "hld", "alo", "set")~~ → 2026-10-13 加 exp（狀態更新，不是漏刪）。
_LIVE_PAGES = ("mkt", "hld", "exp", "alo", "set")
_PREVIEW_MODULE = "ui_v2.app_preview"


def _tree(path: pathlib.Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


# ═══════════════════════ (a) 不被正式程式 import ═══════════════════════


def imports_preview(tree: ast.AST) -> list[str]:
    """一棵 AST 裡 import 到預覽入口的寫法（含 `from ui_v2 import app_preview`）。"""
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out += [a.name for a in node.names if a.name == _PREVIEW_MODULE or a.name.startswith(_PREVIEW_MODULE + ".")]
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module == _PREVIEW_MODULE or node.module.startswith(_PREVIEW_MODULE + "."):
                out.append(node.module)
            elif node.module == "ui_v2" and any(a.name == "app_preview" for a in node.names):
                out.append("ui_v2.app_preview")
    return out


def _production_files() -> list[pathlib.Path]:
    """repo 內 tests 以外的全部 .py（不含隱藏目錄、__pycache__、預覽入口自己）。"""
    out = []
    for path in _ROOT.rglob("*.py"):
        rel = path.relative_to(_ROOT)
        if any(part.startswith(".") or part == "__pycache__" for part in rel.parts):
            continue
        if rel.parts[0] == "tests" or path == _PREVIEW:
            continue
        out.append(path)
    return sorted(out)


def test_a_正式程式沒有任何一處import預覽入口():
    files = _production_files()
    rels = {p.relative_to(_ROOT).as_posix() for p in files}
    assert "app.py" in rels and any(r.startswith("ui/") for r in rels)  # 空掃防呆
    assert len(files) > 100, len(files)
    hits = {}
    for path in files:
        found = imports_preview(_tree(path))
        if found:
            hits[path.relative_to(_ROOT).as_posix()] = found
    assert hits == {}


def test_a_app_py與ui底下連字串都不提預覽入口():
    """`st.switch_page("ui_v2/app_preview.py")`、`runpy` 之類的字串寫法 AST import 掃描看不到，另掃字面。"""
    targets = [_ROOT / "app.py"] + sorted((_ROOT / "ui").rglob("*.py"))
    assert len(targets) > 20, len(targets)  # 空掃防呆
    hits = [p.relative_to(_ROOT).as_posix() for p in targets
            if "app_preview" in p.read_text(encoding="utf-8", errors="replace")]
    assert hits == []


@pytest.mark.parametrize("code", [
    "import ui_v2.app_preview",
    "from ui_v2 import app_preview",
    "from ui_v2.app_preview import PAGES",
    "def f():\n    from ui_v2 import app_mkt, app_preview",
])
def test_a_正控_各種import寫法都抓得到(code):
    assert imports_preview(ast.parse(code))


def test_a_負控_別的進入點不誤報():
    assert imports_preview(ast.parse("from ui_v2 import app_mkt\nimport ui_v2.app_previewer")) == []


# ═══════════════════════ (b) 注入函式與各 live 入口一致 ═══════════════════════


def _render_injections(tree: ast.AST, page_alias: str, source_alias: str | None) -> list[dict]:
    """找出 `<page_alias>.render(...)` 的每一次呼叫，回傳 `{關鍵字: source 上的屬性名}`。

    不是 `<source_alias>.<屬性>` 形狀的關鍵字值、位置參數、`**kwargs` 一律記成字串 `"<非source屬性>"`
    之類，讓比對當場不相等（不靜默略過）。
    """
    calls = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "render" and isinstance(node.func.value, ast.Name)
                and node.func.value.id == page_alias):
            continue
        got = {}
        if node.args:
            got["<位置參數>"] = len(node.args)
        for kw in node.keywords:
            value = kw.value
            if kw.arg is None:
                got["<**kwargs>"] = ast.unparse(value)
            elif (isinstance(value, ast.Attribute) and isinstance(value.value, ast.Name)
                  and source_alias is not None and value.value.id == source_alias):
                got[kw.arg] = value.attr
            else:
                got[kw.arg] = f"<非source屬性：{ast.unparse(value)}>"
        calls.append(got)
    return calls


def _aliases(tree: ast.AST, page: str) -> tuple[str | None, str | None]:
    """`from ui_v2.<頁> import page as X, source as Y` → (X, Y)。"""
    page_alias = source_alias = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == f"ui_v2.{page}":
            for alias in node.names:
                if alias.name == "page":
                    page_alias = alias.asname or "page"
                elif alias.name == "source":
                    source_alias = alias.asname or "source"
    return page_alias, source_alias


def _entry_injections(path: pathlib.Path, page: str) -> list[dict]:
    tree = _tree(path)
    page_alias, source_alias = _aliases(tree, page)
    assert page_alias is not None, (path.name, page)
    return _render_injections(tree, page_alias, source_alias)


@pytest.mark.parametrize("page", _LIVE_PAGES)
def test_b_四頁注入與live入口逐一相同(page):
    live = _entry_injections(_ROOT / "ui_v2" / f"app_{page}_live.py", page)
    preview = _entry_injections(_PREVIEW, page)
    assert len(live) == 1, live            # live 入口只呼叫一次（守衛前提）
    assert live[0], live                   # 至少傳了 load_live（空字典＝比對沒有意義）
    assert "load_live" in live[0]
    assert preview == live, (page, preview, live)


def test_b_標的探索的示範入口照舊不傳任何參數_預覽改走正式入口():
    """~~標的探索與示範入口一樣不傳任何參數~~ → 2026-10-13（狀態更新，不是漏刪）：預覽改與 `app_exp_live.py`
    逐一相同（上一條參數化守衛已含 exp）；示範入口 `app_exp.py` 不動、照舊不傳任何參數。"""
    demo = _entry_injections(_ROOT / "ui_v2" / "app_exp.py", "exp")
    preview = _entry_injections(_PREVIEW, "exp")
    assert demo == [{}]
    assert preview == [{"load_live": "load_live", "save_live": "save_setting"}]


def test_b_live入口的注入本身沒有漂移_體檢四份的關鍵字集合():
    """記下量測當時四份 live 入口各傳什麼（量測日 2026-10-12）；live 入口一改，本條先紅，提醒回頭對預覽。"""
    got = {p: _entry_injections(_ROOT / "ui_v2" / f"app_{p}_live.py", p)[0] for p in _LIVE_PAGES}
    # 2026-10-13 狀態更新（不是漏刪）：客戶裁示市場總覽設定存檔接上 user_setting ——
    # ~~"mkt": {"load_live": "load_live"},~~ → mkt 入口與預覽同步加傳 save_live（上一條守衛比對兩者逐一相同）。
    assert got == {
        "mkt": {"load_live": "load_live", "save_live": "save_setting"},
        # ~~"hld": {"load_live": "load_live", "mask_error": "mask_error"},~~ → 2026-10-16 客戶裁示第 2 點（狀態更新，不是漏刪）：
        # 持倉體檢存檔接上 user_setting，入口與預覽同步加傳 save_live。
        "hld": {"load_live": "load_live", "mask_error": "mask_error", "save_live": "save_setting"},
        "exp": {"load_live": "load_live", "save_live": "save_setting"},   # 2026-10-13 新增
        "alo": {"load_live": "load_live", "save_live": "save_setting"},
        "set": {"load_live": "load_live", "save_live": "save_setting", "refetch_live": "refetch"},
    }


@pytest.mark.parametrize("code, want", [
    # 少傳一個
    ("from ui_v2.hld import page as P, source as S\nP.render(load_live=S.load_live)",
     [{"load_live": "load_live"}]),
    # 改傳 fixtures 的東西
    ("from ui_v2.mkt import page as P, source as S, fixtures as F\nP.render(load_live=F.all_datasets)",
     [{"load_live": "<非source屬性：F.all_datasets>"}]),
    # 換成 lambda 包一層
    ("from ui_v2.mkt import page as P, source as S\nP.render(load_live=lambda: S.load_live())",
     [{"load_live": "<非source屬性：lambda: S.load_live()>"}]),
    # **kwargs
    ("from ui_v2.mkt import page as P, source as S\nP.render(**{'load_live': S.load_live})",
     [{"<**kwargs>": "{'load_live': S.load_live}"}]),
])
def test_b_正控_抽取器看得出每一種偏離(code, want):
    tree = ast.parse(code)
    page = re.search(r"ui_v2\.(\w+)", code).group(1)
    page_alias, source_alias = _aliases(tree, page)
    assert _render_injections(tree, page_alias, source_alias) == want


# ═══════════════════════ (c) 預覽入口不碰 fixtures ═══════════════════════


def fixtures_mentions(tree: ast.AST) -> list[str]:
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and "fixtures" in node.module.split("."):
            out.append(node.module)
        elif isinstance(node, ast.ImportFrom) and any(a.name == "fixtures" for a in node.names):
            out.append(f"{node.module}.fixtures")
        elif isinstance(node, ast.Import) and any("fixtures" in a.name.split(".") for a in node.names):
            out.append(",".join(a.name for a in node.names))
        elif isinstance(node, ast.Attribute) and node.attr == "fixtures":
            out.append(ast.unparse(node))
        elif isinstance(node, ast.Name) and node.id == "fixtures":
            out.append("fixtures")
    return out


def test_c_預覽入口不import也不引用任何fixtures():
    assert fixtures_mentions(_tree(_PREVIEW)) == []


@pytest.mark.parametrize("code", [
    "from ui_v2.mkt import fixtures",
    "import ui_v2.hld.fixtures",
    "from ui_v2.alo.fixtures import scenario",
    "from ui_v2.mkt import page\nx = page.fixtures",
])
def test_c_正控_各種寫法都抓得到(code):
    assert fixtures_mentions(ast.parse(code))


# ═══════════════════════ (d) 標的探索的示意資料標示 ═══════════════════════


def _function(tree: ast.Module, name: str) -> ast.FunctionDef:
    found = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name]
    assert len(found) == 1, name
    return found[0]


def _string_constant(tree: ast.Module, name: str) -> str:
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError(f"找不到常數 {name}")


def banner_before_render(func: ast.FunctionDef) -> bool:
    """函式本體依序走：第一個 `st.*` 畫面呼叫必須是 `st.warning(EXP_DEMO_BANNER, ...)`，而且在 `exp_page.render()` 之前。"""
    for stmt in func.body:
        call = stmt.value if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call) else None
        if call is None or not isinstance(call.func, ast.Attribute):
            continue
        owner = call.func.value
        if isinstance(owner, ast.Name) and owner.id == "exp_page" and call.func.attr == "render":
            return False                                   # render 先到 ⇒ 標示不在最上方
        if isinstance(owner, ast.Name) and owner.id == "st":
            return (call.func.attr == "warning" and bool(call.args)
                    and isinstance(call.args[0], ast.Name) and call.args[0].id == "EXP_DEMO_BANNER")
    return False


# ~~def test_d_標的探索先畫標示再畫頁面(): assert banner_before_render(_function(_tree(_PREVIEW), "page_exp"))~~
# ~~def test_d_標示字面寫明示意資料_不是真實資料_尚未接真資料(): …~~
# → 2026-10-13 撤下（狀態更新，不是漏刪；客戶裁示 B 線標的探索正式模式第一批）：示意資料標示只在標的探索
#   畫假資料時才是真話；接上正式資料後那一句（「本頁為示意資料、不是真實資料」）就是假的。兩條在寫下當時為真。
#   `banner_before_render` 與它的正控留著：它是「這一頁不准再有示意標示」那一條的偵測器。


def test_d_標的探索不再畫示意資料標示_常數也已撤下():
    tree = _tree(_PREVIEW)
    func = _function(tree, "page_exp")
    assert banner_before_render(func) is False
    assert _calls_named(func, "warning") == 0
    names = {t.id for n in tree.body if isinstance(n, ast.Assign) for t in n.targets if isinstance(t, ast.Name)}
    assert "EXP_DEMO_BANNER" not in names


@pytest.mark.parametrize("body", [
    "def page_exp():\n    exp_page.render()",                                       # 拿掉標示
    "def page_exp():\n    exp_page.render()\n    st.warning(EXP_DEMO_BANNER)",        # 標示放到頁面後面
    "def page_exp():\n    st.caption(EXP_DEMO_BANNER)\n    exp_page.render()",          # 不醒目的寫法
    "def page_exp():\n    st.markdown('x')\n    st.warning(EXP_DEMO_BANNER)\n    exp_page.render()",
])
def test_d_正控_標示不在最上方就紅(body):
    assert banner_before_render(ast.parse(body).body[0]) is False


# ═══════════════════════ 其他：頁序、頁名、set_page_config、secret 鍵名 ═══════════════════════


def _spec_page_names() -> list[str]:
    """`docs/v2/44_fund_ui_ssot.md` 3.0 五頁總表第一欄（`| **頁名** |`），依表內順序。"""
    text = (_ROOT / "docs" / "v2" / "44_fund_ui_ssot.md").read_text(encoding="utf-8")
    section = text.split("### 3.0 五頁總表", 1)[1].split("### 3.1", 1)[0]
    return re.findall(r"^\| \*\*([^*|]+)\*\* \|", section, flags=re.MULTILINE)


def test_頁序與頁名逐字對44的五頁總表():
    spec = _spec_page_names()
    assert spec == ["市場總覽", "持倉體檢", "標的探索", "資產配置", "設定與診斷"]  # 量測日 2026-10-12
    tree = _tree(_PREVIEW)  # PAGES 含函式名，不能整個 literal_eval，逐格讀
    node = next(n for n in tree.body if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "PAGES" for t in n.targets))
    rows = [(ast.literal_eval(e.elts[0]), ast.literal_eval(e.elts[1]), e.elts[2].id) for e in node.value.elts]
    assert [title for _slug, title, _fn in rows] == spec
    assert rows == [
        ("mkt", "市場總覽", "page_mkt"),
        ("hld", "持倉體檢", "page_hld"),
        ("exp", "標的探索", "page_exp"),
        ("alo", "資產配置", "page_alo"),
        ("set", "設定與診斷", "page_set"),
    ]


def _calls_named(tree: ast.AST, attr: str) -> int:
    return sum(1 for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
               and n.func.attr == attr)


def test_set_page_config全樹只有預覽入口的main呼叫一次():
    tree = _tree(_PREVIEW)
    assert _calls_named(tree, "set_page_config") == 1
    assert _calls_named(_function(tree, "main"), "set_page_config") == 1
    page_modules = sorted((_ROOT / "ui_v2").glob("*/*.py"))
    assert len(page_modules) >= 25, len(page_modules)  # 空掃防呆
    offenders = [p.relative_to(_ROOT).as_posix() for p in page_modules if _calls_named(_tree(p), "set_page_config")]
    assert offenders == []


def test_檔頭列的試算表secret鍵名與L1實際讀的相同():
    doc = ast.get_docstring(_tree(_PREVIEW))
    for rel in ("repositories/settings_sheet_repository.py", "repositories/policy_supplement_repository.py"):
        key = _string_constant(_tree(_ROOT / rel), "SECRET_KEY")
        assert f"`{key}`" in doc, (rel, key)
        assert 'get_secret("google_service_account")' in (_ROOT / rel).read_text(encoding="utf-8"), rel
    assert "`google_service_account`" in doc
    assert "不得被 `app.py`" in doc


def _drop_list(tree: ast.Module) -> list[str]:
    """`_PAGE_STATE_TO_DROP = (...)` 的每一格原始碼（常數引用照原樣、字面值帶引號）。"""
    node = next(n for n in tree.body if isinstance(n, ast.Assign)
                and any(isinstance(x, ast.Name) and x.id == "_PAGE_STATE_TO_DROP" for x in n.targets))
    return [ast.unparse(e) for e in node.value.elts]


def _pops_each_drop_key(func: ast.FunctionDef) -> bool:
    """`_on_page` 裡要有 `for key in _PAGE_STATE_TO_DROP: st.session_state.pop(key, ...)`。"""
    for node in ast.walk(func):
        if (isinstance(node, ast.For) and ast.unparse(node.iter) == "_PAGE_STATE_TO_DROP"
                and isinstance(node.target, ast.Name)):
            for inner in ast.walk(node):
                if (isinstance(inner, ast.Call) and isinstance(inner.func, ast.Attribute)
                        and inner.func.attr == "pop" and ast.unparse(inner.func.value) == "st.session_state"
                        and inner.args and ast.unparse(inner.args[0]) == node.target.id):
                    return True
    return False


def test_換頁時pop的狀態清單_資產配置引用常數_市場總覽為字面值():
    tree = _tree(_PREVIEW)
    # ~~assert _drop_list(tree) == ["alo_page._SAVE_ERRORS_STATE", "'_mkt_applied'"]~~
    # → 2026-10-13 狀態更新（不是漏刪）：市場總覽存檔接上後多一格「存檔逐鍵結果」，引用 page 的常數。
    # ~~assert _drop_list(tree) == [… "mkt_page._SAVE_RESULTS_STATE"]~~ → 2026-10-13 標的探索接上正式模式後多兩格（狀態更新，不是漏刪）。
    assert _drop_list(tree) == ["alo_page._SAVE_ERRORS_STATE", "'_mkt_applied'", "mkt_page._SAVE_RESULTS_STATE",
                                "exp_page._SAVE_RESULTS_STATE", "exp_page._RULES_STATE",
                                "exp_page._SEEDED_STATE",  # 2026-10-13 稽核 L 回修多一格
                                "hld_page._SAVE_RESULTS_STATE"]  # 2026-10-16 客戶裁示第 2 點：持倉體檢存檔接上後多一格
    hld_key = _string_constant(_tree(_ROOT / "ui_v2" / "hld" / "page.py"), "_SAVE_RESULTS_STATE")
    assert hld_key and hld_key not in _PREVIEW.read_text(encoding="utf-8")
    for name in ("_SAVE_RESULTS_STATE", "_RULES_STATE", "_SEEDED_STATE"):
        exp_key = _string_constant(_tree(_ROOT / "ui_v2" / "exp" / "page.py"), name)
        assert exp_key and exp_key not in _PREVIEW.read_text(encoding="utf-8"), name
    mkt_key = _string_constant(_tree(_ROOT / "ui_v2" / "mkt" / "page.py"), "_SAVE_RESULTS_STATE")
    assert mkt_key and mkt_key not in _PREVIEW.read_text(encoding="utf-8")
    assert _pops_each_drop_key(_function(tree, "_on_page"))
    alo_key = _string_constant(_tree(_ROOT / "ui_v2" / "alo" / "page.py"), "_SAVE_ERRORS_STATE")
    assert alo_key and alo_key not in _PREVIEW.read_text(encoding="utf-8")  # 常數存在，本檔沒有寫死同一個字串


def test_市場總覽的套用key字面值確實住在mkt的page_py():
    """`ui_v2/mkt/page.py` 沒有常數，預覽入口只能寫字面值；那一頁改了 key 名，本條就紅。"""
    text = (_ROOT / "ui_v2" / "mkt" / "page.py").read_text(encoding="utf-8")
    assert 'st.session_state["_mkt_applied"] = ' in text            # 「套用」寫入點
    assert 'st.session_state.get("_mkt_applied", {})' in text       # render 讀取點


@pytest.mark.parametrize("body", [
    "def _on_page(slug):\n    st.session_state.pop('_alo_live_save_errors', None)",   # 沒走清單
    "def _on_page(slug):\n    for key in _PAGE_STATE_TO_DROP:\n        print(key)",       # 走了清單卻沒 pop
    "def _on_page(slug):\n    pass",
])
def test_正控_沒有逐一pop清單就紅(body):
    assert _pops_each_drop_key(ast.parse(body).body[0]) is False


def test_每一頁函式第一句都是_on_page且slug對得上():
    tree = _tree(_PREVIEW)
    for slug in ("mkt", "hld", "exp", "alo", "set"):
        first = _function(tree, f"page_{slug}").body[0]
        assert ast.unparse(first) == f"_on_page({slug!r})", (slug, ast.unparse(first))


def test_預覽入口沒有清除live前綴輸入欄的程式():
    """2026-10-12 紅隊推翻「同名輸入欄會跨頁寫入」後移除；不得被加回來當成防護（真正的防護在 widget id 算法，
    由 slow lane 的回歸測試看守）。"""
    text = _PREVIEW.read_text(encoding="utf-8")
    assert "startswith(\"live_\")" not in text and "SHARED_LIVE_INPUT_PREFIX" not in text


def dynamic_uses(tree: ast.AST) -> list[str]:
    """`getattr`、`__import__`、`importlib`、`globals()` —— 這些寫法能繞過本檔所有靜態比對。"""
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in ("getattr", "__import__", "globals"):
            out.append(node.id)
        elif isinstance(node, ast.Attribute) and node.attr in ("__import__", "import_module"):
            out.append(node.attr)
        elif isinstance(node, ast.Import) and any(a.name.split(".")[0] == "importlib" for a in node.names):
            out.append("import importlib")
        elif isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == "importlib":
            out.append("from importlib")
    return out


def test_預覽入口不用動態寫法():
    assert dynamic_uses(_tree(_PREVIEW)) == []


@pytest.mark.parametrize("code", [
    'x = getattr(mkt_page, "fixtures")',
    "m = __import__('ui_v2.mkt.fixtures')",
    "import importlib\nm = importlib.import_module('ui_v2.mkt.fixtures')",
    "from importlib import import_module",
    "g = globals()['mkt_page']",
])
def test_正控_動態寫法都抓得到(code):
    assert dynamic_uses(ast.parse(code))


def test_側邊欄說明的字面():
    note = _string_constant(_tree(_PREVIEW), "PREVIEW_NOTE")
    # ~~"標的探索為示意資料"~~ → 2026-10-13 標的探索接上正式模式（狀態更新，不是漏刪）。
    # ~~"標的探索目前只接上選股池的基金代碼"~~ → 2026-10-15（狀態更新，不是漏刪）：#966 起標的探索也接上基本資料與淨值，
    #   那一句已過時、自 PREVIEW_NOTE 刪除；改驗它不再出現。
    for needle in ("B 線 UI 預覽（非正式站）", "五頁皆讀真資料",
                   "讀不到資料時照實顯示缺失。", "和各頁單獨啟動時不同", "重新取數"):
        assert needle in note, needle
    assert "只接上選股池的基金代碼" not in note and "其餘欄位顯示資料未備" not in note
    assert "示意資料" not in note
    assert "正式上線" not in note   # 49 4.8：正式部署形態查不到，不得斷言
