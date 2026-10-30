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
_LIVE_PAGES = ("mkt", "hld", "exp", "alo", "set")   # live 單頁入口仍是五個（`ui_v2/app_<頁>_live.py`）
# → 2026-10-30 Batch D（`DEC-2026-10-30-02`；有意識的政策變更，不是漏刪）：預覽導覽把 `alo`、`hld` 併成一頁 `ast`，
#   「預覽的 `page.render` 注入與 live 入口逐一相同」只剩這三頁；`alo`／`hld` 兩側改由 `page_ast` 比對（見下方
#   `test_b_合併頁注入與兩個live入口同名同物件`）。舊守衛的比較一條都沒放寬：只是不再有 `page_alo`／`page_hld` 可比。
_PREVIEW_INJECTED = ("mkt", "exp", "set")
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


# 2026-10-17 Phase 3 P0-②：預覽入口另多傳一個 `settings_page`（設定與診斷那一頁的 `st.Page`，給「前往設定與診斷」），
# 只給這四頁；單頁的 live 入口沒有 `st.navigation`、不傳。抽取器把它記成「非 source 屬性」的那一個字串。
_SETTINGS_PAGE_KW = "settings_page"
_SETTINGS_PAGE_VALUE = "<非source屬性：_settings_page()>"
_SETTINGS_PAGE_PAGES = ("mkt", "exp")   # → Batch D：`hld`、`alo` 併入 `ast`（settings_page 另由合併頁測試守）
_PAGES_KW = "pages"
_PAGES_VALUE = "<非source屬性：_page_links()>"


@pytest.mark.parametrize("page", _PREVIEW_INJECTED)
def test_b_四頁注入與live入口逐一相同(page):
    """~~`preview == live`（逐一相同）~~ → 2026-10-17 P0-②（有意識的更正，不是漏刪）：預覽在四頁多傳一個
    `settings_page=_settings_page()`；**拿掉那一個之後**其餘仍與 live 入口逐一相同（關鍵字、source 屬性名一個不差）。
    其他比較一條都沒有放寬：多傳別的、少傳、換成別的物件，照舊當場不相等。"""
    live = _entry_injections(_ROOT / "ui_v2" / f"app_{page}_live.py", page)
    preview = _entry_injections(_PREVIEW, page)
    assert len(live) == 1, live            # live 入口只呼叫一次（守衛前提）
    assert live[0], live                   # 至少傳了 load_live（空字典＝比對沒有意義）
    assert "load_live" in live[0]
    assert _SETTINGS_PAGE_KW not in live[0], live   # 單頁入口不傳（換不了頁）
    assert len(preview) == 1, preview
    rest = dict(preview[0])
    if page in _SETTINGS_PAGE_PAGES:
        assert rest.pop(_SETTINGS_PAGE_KW) == _SETTINGS_PAGE_VALUE, (page, preview)
    # BL-0250 批次 3-B（44 第七節第三小節之十三其七；有意識的更正，不是漏刪）：設定與診斷頁另多傳一個 `pages=_page_links()`
    # （各頁資料狀態總表每列「前往<頁名>」，只換頁）；單頁入口不傳。拿掉它之後其餘照舊逐一相同。
    if page == "set":
        assert rest.pop(_PAGES_KW) == _PAGES_VALUE, (page, preview)
        assert _PAGES_KW not in live[0], live
    assert [rest] == live, (page, preview, live)


def test_b_設定與診斷頁本身不傳settings_page_四頁都傳():
    for page in _PREVIEW_INJECTED:
        preview = _entry_injections(_PREVIEW, page)[0]
        assert (_SETTINGS_PAGE_KW in preview) is (page in _SETTINGS_PAGE_PAGES), (page, preview)


def test_b_settings_page只建一個st_Page_取自PAGES_不碰任何source():
    """`_settings_page` 只換頁用：函式本體只准 `next(...)` 與 `st.Page(...)`，不得引用任何頁的 `source`
    （不讀不寫任何資料、不觸發取數；44 第五節第三小節 `導覽`、護欄 3）。"""
    fn = _function(_tree(_PREVIEW), "_settings_page")
    calls = {ast.unparse(c.func) for c in ast.walk(fn) if isinstance(c, ast.Call)}
    assert calls == {"next", "st.Page"}, calls
    names = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)}
    assert not any(name.endswith("_source") or name.endswith("_page") and name != "_settings_page"
                   for name in names), names
    assert "PAGES" in names


def _page_ast_render_kwargs() -> dict:
    """`page_ast` 裡 `asset_page.render(...)` 的關鍵字 → AST 節點。"""
    fn = _function(_tree(_PREVIEW), "page_ast")
    calls = [c for c in ast.walk(fn) if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
             and c.func.attr == "render" and isinstance(c.func.value, ast.Name) and c.func.value.id == "asset_page"]
    assert len(calls) == 1, calls
    assert not calls[0].args and all(k.arg for k in calls[0].keywords), ast.unparse(calls[0])
    return {k.arg: k.value for k in calls[0].keywords}


def _dict_of_source_attrs(node: ast.AST, source_alias: str) -> dict:
    assert isinstance(node, ast.Dict), ast.unparse(node)
    out = {}
    for key, value in zip(node.keys, node.values):
        assert isinstance(key, ast.Constant) and isinstance(key.value, str), ast.unparse(node)
        assert (isinstance(value, ast.Attribute) and isinstance(value.value, ast.Name)
                and value.value.id == source_alias), ast.unparse(value)
        out[key.value] = value.attr
    return out


@pytest.mark.parametrize("page, kw", [("alo", "alo_live"), ("hld", "hld_live")])
def test_b_合併頁注入與兩個live入口同名同物件(page, kw):
    """💼 我的資產（BL-0525 Batch D）：`page_ast` 傳給 `asset_page.render` 的 `alo_live`／`hld_live`，與各自單頁 live 入口
    （`app_alo_live.py`、`app_hld_live.py`）傳給 `page.render` 的 `load_live`／`save_live`／`mask_error` **同名同物件**
    （同一個 `source` 屬性）；取代 Batch D 前「預覽 `page.render` 注入與 live 入口逐一相同」對 `alo`、`hld` 的比對，一條都沒放寬。"""
    live = _entry_injections(_ROOT / "ui_v2" / f"app_{page}_live.py", page)[0]
    got = _dict_of_source_attrs(_page_ast_render_kwargs()[kw], f"{page}_source")
    want = {"load": live["load_live"], "save": live["save_live"], "mask": live["mask_error"]}
    assert got == want, (page, got, want)
    assert set(live) == {"load_live", "save_live", "mask_error"}, live      # live 入口多傳別的 → 先紅、回頭對合併頁


def test_b_合併頁的selector與換頁連結取自既有物件():
    kwargs = _page_ast_render_kwargs()
    assert set(kwargs) == {"alo_live", "hld_live", "picker_live", "settings_page"}, set(kwargs)
    assert ast.unparse(kwargs["picker_live"]) == "set_source.picker_live"       # 設定頁既有 picker，不碰 OAuth
    assert ast.unparse(kwargs["settings_page"]) == "_settings_page()"
    set_live = _entry_injections(_ROOT / "ui_v2" / "app_set_live.py", "set")[0]
    assert set_live["picker_live"] == "picker_live"


def test_b_標的探索的示範入口照舊不傳任何參數_預覽改走正式入口():
    """~~標的探索與示範入口一樣不傳任何參數~~ → 2026-10-13（狀態更新，不是漏刪）：預覽改與 `app_exp_live.py`
    逐一相同（上一條參數化守衛已含 exp）；示範入口 `app_exp.py` 不動、照舊不傳任何參數。"""
    demo = _entry_injections(_ROOT / "ui_v2" / "app_exp.py", "exp")
    preview = _entry_injections(_PREVIEW, "exp")
    assert demo == [{}]
    # 2026-10-17 P0-②：預覽另多傳 settings_page（上一條守衛只容許多這一個）。
    # ~~`[{"load_live": "load_live", "save_live": "save_setting", _SETTINGS_PAGE_KW: _SETTINGS_PAGE_VALUE}]`~~ →
    # 2026-10-17 P1-⑤（BL-0362；狀態更新，不是漏刪）：入口與預覽同步加傳 mask_error。
    assert preview == [{"load_live": "load_live", "save_live": "save_setting", "mask_error": "mask_error",
                        _SETTINGS_PAGE_KW: _SETTINGS_PAGE_VALUE}]


def test_b_live入口的注入本身沒有漂移_體檢四份的關鍵字集合():
    """記下量測當時四份 live 入口各傳什麼（量測日 2026-10-12）；live 入口一改，本條先紅，提醒回頭對預覽。"""
    got = {p: _entry_injections(_ROOT / "ui_v2" / f"app_{p}_live.py", p)[0] for p in _LIVE_PAGES}
    # 2026-10-13 狀態更新（不是漏刪）：客戶裁示市場總覽設定存檔接上 user_setting ——
    # ~~"mkt": {"load_live": "load_live"},~~ → mkt 入口與預覽同步加傳 save_live（上一條守衛比對兩者逐一相同）。
    # 2026-10-17 P1-⑤（BL-0362；狀態更新，不是漏刪）：mkt、exp、set 三份入口與預覽同步加傳 mask_error
    # （整頁載入失敗時原文經遮蔽才收進進階診斷）。舊值：mkt／exp 只有 load_live、save_live；set 沒有 mask_error。
    assert got == {
        "mkt": {"load_live": "load_live", "save_live": "save_setting", "mask_error": "mask_error"},
        # ~~"hld": {"load_live": "load_live", "mask_error": "mask_error"},~~ → 2026-10-16 客戶裁示第 2 點（狀態更新，不是漏刪）：
        # 持倉體檢存檔接上 user_setting，入口與預覽同步加傳 save_live。
        "hld": {"load_live": "load_live", "mask_error": "mask_error", "save_live": "save_setting"},
        "exp": {"load_live": "load_live", "save_live": "save_setting", "mask_error": "mask_error"},   # 2026-10-13 新增
        # 2026-10-16 總管判定（PR #976 稽核後）：資產配置入口與預覽同步加傳 mask_error（狀態更新，不是漏刪）。
        "alo": {"load_live": "load_live", "save_live": "save_setting", "mask_error": "mask_error"},
        # ~~"set": {…, "mask_error": "mask_error"},~~ → 2026-10-26 批 3b-2（狀態更新，不是漏刪）：設定頁入口與預覽同步加傳
        # login_live（Google 個人登入卡；`ui_v2/set/source.py::login_live`）。
        "set": {"load_live": "load_live", "save_live": "save_setting", "refetch_live": "refetch",
                "mask_error": "mask_error", "login_live": "login_live",
                "picker_live": "picker_live"},   # 2026-10-26 批 3b-3（狀態更新，不是漏刪）：加傳 picker_live
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


# ~~`_spec_page_names` 的 regex `^\| \*\*([^*|]+)\*\* \|`（只認「第一欄恰為粗體頁名」）~~
# → 2026-10-27 對齊批（BL-0478；有意識的政策變更，不是漏刪；決策者：客戶（`DEC-2026-10-27-02`））：44 五頁總表第一欄改成
#   「~~**舊頁名**~~ → **正式頁名**（日期註記）」，舊 regex 一列都抓不到。新 regex 一樣只認整個第一欄恰為這個形狀，
#   **而且要求表內每一列都是這個形狀**（`_SPEC_ROW` 對不上的列直接紅，不靠 findall 靜默跳過），斷言仍是逐字相等，沒有放寬。
_SPEC_ROW = re.compile(r"^\| ~~\*\*([^*|]+)\*\*~~ → \*\*([^*|]+)\*\*（[^|]*） \|")


def _spec_rows() -> list[tuple[str, str]]:
    """`docs/v2/44_fund_ui_ssot.md` 3.0 五頁總表第一欄 →（劃線的舊頁名, 正式頁名），依表內順序（＝正式頁序）。"""
    text = (_ROOT / "docs" / "v2" / "44_fund_ui_ssot.md").read_text(encoding="utf-8")
    section = text.split("### 3.0 五頁總表", 1)[1].split("### 3.1", 1)[0]
    lines = [ln for ln in section.split("\n") if ln.startswith("| ")]
    assert lines[0].startswith("| 頁 |"), lines[0]   # 表頭；第二行 `|---|` 不以 "| " 開頭
    rows = []
    for ln in lines[1:]:
        m = _SPEC_ROW.match(ln)
        assert m, f"44 五頁總表有一列的第一欄不是「~~**舊**~~ → **新**（註記）」的形狀：{ln[:60]}"
        rows.append((m.group(1), m.group(2)))
    return rows


def _spec_page_names() -> list[str]:
    """44 3.0 五頁總表第一欄箭頭後的正式頁名，依表內順序。"""
    return [new for _old, new in _spec_rows()]


_IA_ROW = re.compile(r"^\| (\d|最後) \| ([^|]+?) \|")


def _ia_page_names() -> list[str]:
    """`docs/v2/44_fund_ui_ssot.md` 第七節第三小節之二十「其一｜頁序與頁名」那張表的「正式頁名」欄，依表內順序。"""
    text = (_ROOT / "docs" / "v2" / "44_fund_ui_ssot.md").read_text(encoding="utf-8")
    section = text.split("**其一｜頁序與頁名", 1)[1].split("1. ⚖️ 資產配置不再是獨立頂層頁", 1)[0]
    rows = [m.group(2) for ln in section.split("\n") if (m := _IA_ROW.match(ln))]
    assert len(rows) == 4, rows   # 空掃防呆：之二十其一的表有四列
    return rows


def test_頁序與頁名逐字對44的五頁總表():
    # ~~assert spec == ["市場總覽", "持倉體檢", "標的探索", "資產配置", "設定與診斷"]  # 量測日 2026-10-12~~
    # → 2026-10-27 對齊批（BL-0478；決策者：客戶（`DEC-2026-10-27-02`））：正式頁序與頁名（44 之十七其二）。
    assert _spec_rows() == [
        ("市場總覽", "🌍 市場與趨勢"),
        ("資產配置", "⚖️ 資產配置"),
        ("持倉體檢", "💼 我的持股"),
        ("標的探索", "🔍 找基金"),
        ("設定與診斷", "⚙️ 設定"),
    ]  # 量測日 2026-10-27
    assert _spec_page_names() == ["🌍 市場與趨勢", "⚖️ 資產配置", "💼 我的持股", "🔍 找基金", "⚙️ 設定"]   # 44 那張表的字面本輪不動
    spec = _ia_page_names()   # → Batch D：預覽的頁清單改讀 44 之二十其一的正式頁序（內容頁 🌍、💼、🔍，最後 ⚙️）
    tree = _tree(_PREVIEW)  # PAGES 含函式名，不能整個 literal_eval，逐格讀
    node = next(n for n in tree.body if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "PAGES" for t in n.targets))
    rows = [(ast.literal_eval(e.elts[0]), ast.literal_eval(e.elts[1]), e.elts[2].id) for e in node.value.elts]
    assert [title for _slug, title, _fn in rows] == spec
    # url_path 不改（深連結、OAuth 落點 `/set`，BL-0465）；只換順序與頁名。
    # → 2026-10-30 Batch D（`DEC-2026-10-29-06`、`DEC-2026-10-30-02`；有意識的政策變更，不是漏刪；決策者：客戶）：⚖️ 資產配置與
    #   💼 我的持股併為一頁「💼 我的資產」（`ast`）；44 之二十其一的正式頁序（內容頁 🌍、💼、🔍，最後 ⚙️）改由下一條守衛逐字比對。
    #   上面那段 44 五頁總表的比對仍然成立（那一張表的字面本輪沒動，同 44 之二十其一第 3 條）；舊 rows 五列在寫下當時為真：
    #   ("alo", "⚖️ 資產配置", "page_alo")、("hld", "💼 我的持股", "page_hld")。
    assert rows == [
        ("mkt", "🌍 市場與趨勢", "page_mkt"),
        ("ast", "💼 我的資產", "page_ast"),
        ("exp", "🔍 找基金", "page_exp"),
        ("set", "⚙️ 設定", "page_set"),
    ]


@pytest.mark.parametrize("bad", [
    "| **市場總覽** | 問 | 誰 | 邊界 |",                                    # 舊形狀（沒劃線、沒箭頭）
    "| ~~**市場總覽**~~ → **🌍 市場與趨勢** | 問 | 誰 | 邊界 |",            # 少了日期註記
    "| ~~**市場總覽**~~ → **🌍 市場與趨勢**（註記） 多字 | 問 | 誰 | 邊界 |",  # 第一欄夾了別的字
    "| ~~市場總覽~~ → **🌍 市場與趨勢**（註記） | 問 | 誰 | 邊界 |",          # 舊頁名沒粗體
])
def test_正控_五頁總表第一欄不是對齊後的形狀就抓不到(bad):
    assert _SPEC_ROW.match(bad) is None


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
                                "alo_page._PENDING_INPUTS_STATE",  # 2026-10-16 客戶裁示方案 B 多一格
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
    alo_pending = _string_constant(_tree(_ROOT / "ui_v2" / "alo" / "page.py"), "_PENDING_INPUTS_STATE")
    assert alo_pending and alo_pending not in _PREVIEW.read_text(encoding="utf-8")


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
    for slug in ("mkt", "ast", "exp", "set"):   # → Batch D：`alo`、`hld` 併成 `ast`（`page_alo`／`page_hld` 已刪）
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


def test_換頁清單不含個人登入的任何狀態_2026_10_26_批3b2():
    """換頁時被 pop 的 key 一覽（`_PAGE_STATE_TO_DROP`）不得含個人 OAuth 的鍵（`b_oauth.` 命名空間）或設定頁登入卡的標記
    （notice、callback 已處理的 state、切換標記）：這些在換頁（例如離開設定頁再回來）時必須保留，否則登入狀態會被換頁洗掉。
    以 AST 讀清單的每個元素原文，不 import 預覽入口（不需要 streamlit）。"""
    tree = _tree(_PREVIEW)
    node = next(n for n in ast.walk(tree) if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "_PAGE_STATE_TO_DROP" for t in n.targets))
    texts = [ast.unparse(e).lower() for e in node.value.elts]
    assert texts, "清單讀不到元素"
    for text in texts:
        assert "oauth" not in text and "login" not in text, text
