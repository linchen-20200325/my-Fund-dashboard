"""⑨ `[新] 資產配置` 掛載守衛 —— **「不加閘門」這個決定的前提還成不成立**。

本檔存在的理由（先讀這段，否則會以為它只是又一份 key 掃描）
==========================================================
客戶 2026-09-07「雙軌並行」之下，⑥ / ⑦ 各有一個 Checkbox Gate，⑧ / ⑨ 沒有。
**gate 不是禮貌，是有碰撞才付的成本**（多按一下 ＋ 一塊灰態版面）。
⑨ 沒有 gate，是因為 2026-09-08 掃描的結論是「**真的沒有東西可撞**」——
而**那個結論會過期**：⑨ 只要開始委派舊模組、或加一個顯式 `key=`、或多一條
動態派發讓掃描器看不見，前提就不成立了。**本檔就是那個前提的哨兵。**

⛔ **本檔不是「⑨ 應該有 gate」的待辦**。它轉紅時的正解有兩個方向，
   由當時的人依證據選：(a) 把新引入的碰撞源移除；(b) 補一個 gate。
   **⛔ 不准選 (c)「放寬本檔」** —— 那是把尺改短，不是把問題修對。

掃描器的射程與已知盲點（⚠️ 不宣稱窮舉）
--------------------------------------
`_reach()` 走「模組層 ＋ 函式內 lazy import ＋ 裸參照（把函式當值傳出去）」，
**並且會追進 re-export shim**（見 :func:`test_the_scanner_follows_a_re_export_shim`）。
**看不到的形態**（下列任一出現在 ⑨ 的鏈上，本檔的結論即失效）：

* `getattr` / 字典派發 / 字串組出來的動態呼叫
* 類別實例方法（`obj.method()`，`obj` 的型別要靠推論）
* 以參數傳進去的 callable（高階函式）
* 模組 `__getattr__` 動態屬性
* **過近似**：本掃描器不看分支可達性，`if False:` 底下的東西照收
  （方向是**寧可多抓**，這是刻意的）

⭐ **正因為射程有限，:func:`test_the_new_chain_is_fully_resolved` 才是本檔的錨** ——
   它要求 ⑨ 的鏈上**未解析呼叫數為 0**。一旦有人在 ⑨ 引入動態派發，
   那條會先轉紅，告訴你「這份掃描從此不可信」，而不是讓其餘幾條**安靜地假綠**。

碰撞機制（2026-09-08 自 wheel 原始碼導出，非轉述）
--------------------------------------------------
`st.tabs` 一次 run 會把**所有**分頁 body 執行過，所以九格是同一個
element-id 命名空間。`streamlit/elements/lib/utils.py::_register_element_id`：

* 使用者給的 `key` 重複 → `StreamlitDuplicateElementKey`（**無條件**）
* 整個 element id 重複 → `StreamlitDuplicateElementId`（**無條件**）
* element id ＝ hash(型別 ＋ 各 kwargs ＋ `form_id` ＋ **root container**)。
  ⚠️ **`root container` 只分「主畫面 / sidebar」，不分 tab** ——
  也就是說「在不同分頁」**不會**讓兩個無 key 的同型同參數元素分開。
* `st.form(key)`：`form_id` 就是 key 本身，重複 → `StreamlitAPIException`（無條件）
* 只有帶 `key` 才註冊的：`container` / `tabs` / `expander` / `popover`
* 只有 `on_select != "ignore"` 才註冊的：`dataframe`

**版本涵蓋**：`requirements.txt` 釘 `streamlit>=1.59.1,<1.60.0`，區間內只有
1.59.1 / 1.59.2，而兩版 wheel 內 **365 個 `.py` 檔全部 byte-identical**
（2026-09-08 實測 sha256），故上述導出涵蓋整個區間。
"""
from __future__ import annotations

import ast
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]

#: 九格的渲染鏈進入點。**手列，不從 `app.py` 讀** —— 否則就變成拿 app.py 驗 app.py。
CHAINS: dict[str, tuple[str, str]] = {
    "①舊 市場總覽":  ("ui.views.page_01_macro", "render_market_overview"),
    "②舊 持倉體檢":  ("ui.tab_fund_grp_health", "render_fund_grp_health_tab"),
    "③舊 標的探索":  ("ui.tab_fund_research", "render_fund_research_tab"),
    "④舊 資產配置":  ("ui.tab3_portfolio", "render_portfolio_tab"),
    "⑤舊 設定與診斷": ("ui.tab_settings_diag", "render_settings_diag_tab"),
    "⑥新 持倉體檢":  ("ui.views.page_02_health", "render_holdings_health"),
    "⑦新 設定與診斷": ("ui.views.page_05_settings", "render_settings_and_diagnostics"),
    "⑧新 標的探索":  ("ui.views.page_03_research", "render_fund_research"),
    "⑨新 資產配置":  ("ui.views.page_04_portfolio", "render_asset_allocation"),
}
NEW9 = "⑨新 資產配置"

#: **無條件註冊 element id** 的 streamlit 公開元素名。
#: 出處：對 streamlit 1.59.1 wheel 全檔 AST，找 `compute_and_register_element_id(...)`
#: 的呼叫點並檢查其祖先鏈有無條件節點 —— 42 個呼叫點中 29 個無條件。
#: ⚠️ 這張表**寧可多列**：多列會讓守衛更嚴（誤報），少列會讓它假綠（漏報）。
REGISTERS_UNCONDITIONALLY: frozenset[str] = frozenset({
    "audio_input", "button", "camera_input", "chat_input", "checkbox", "color_picker",
    "data_editor", "date_input", "datetime_input", "download_button", "feedback",
    "file_uploader", "form_submit_button", "menu_button", "multiselect", "number_input",
    "pagination", "pills", "plotly_chart", "radio", "segmented_control", "select_slider",
    "selectbox", "slider", "text_area", "text_input", "time_input", "toggle",
})
#: 只有帶 `key` 才註冊 —— 無 key 用法是安全的。
REGISTERS_ONLY_WITH_KEY: frozenset[str] = frozenset({
    "container", "expander", "popover", "tabs"})

#: ⑨ 不得到達的層。**它一到達，「每次 run 都跑 ⑨ 的 body」就變成每次互動都取數。**
IO_MODULE_PREFIXES: tuple[str, ...] = ("repositories.", "infra.proxy", "infra.gspread")


# ══════════════════════════════════════════════════════════════════
# 掃描器（**追得進 re-export shim** —— 這是與 repo 內既有 `_reach` 的關鍵差別）
# ══════════════════════════════════════════════════════════════════
_TREES: dict[str, ast.Module | None] = {}


def _mod_path(mod: str) -> pathlib.Path | None:
    p = ROOT / (mod.replace(".", "/") + ".py")
    if p.is_file():
        return p
    p = ROOT / mod.replace(".", "/") / "__init__.py"
    return p if p.is_file() else None


def _tree(mod: str) -> ast.Module | None:
    if mod not in _TREES:
        p = _mod_path(mod)
        try:
            _TREES[mod] = ast.parse(p.read_text(encoding="utf-8")) if p else None
        except SyntaxError:
            _TREES[mod] = None
    return _TREES[mod]


def _defs(mod: str) -> dict[str, ast.AST]:
    t, out = _tree(mod), {}
    if t is None:
        return out
    for n in t.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out[n.name] = n
        elif isinstance(n, ast.ClassDef):
            out[n.name] = n
            for m in n.body:
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    out[f"{n.name}.{m.name}"] = m
    return out


def _imports(mod: str, scope: ast.AST | None = None):
    t = _tree(mod) if scope is None else scope
    names: dict[str, tuple[str, str]] = {}
    mods: dict[str, str] = {}
    if t is None:
        return names, mods
    for n in ast.walk(t):
        if isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
            for a in n.names:
                if a.name == "*":
                    continue
                names[a.asname or a.name] = (n.module, a.name)
                mods[a.asname or a.name] = f"{n.module}.{a.name}"
        elif isinstance(n, ast.Import):
            for a in n.names:
                mods[a.asname or a.name.split(".")[0]] = a.name
    return names, mods


def _resolve(mod: str, name: str, depth: int = 0) -> tuple[str, str] | None:
    """把 `(模組, 名字)` 解析到**真正 `def` 它的**模組 —— 逐層追過 re-export shim。

    ⭐ **這幾行就是與既有 `_reach` 的差別**：純 re-export 模組（只有 `from X import Y`、
       一個 `def` 都沒有）在「查不到 def 就放棄」的作法下會讓追蹤**安靜地斷掉**，
       於是掃描結果是**假的低估**。正對照見
       :func:`test_the_scanner_follows_a_re_export_shim`。
    """
    if depth > 25 or _mod_path(mod) is None:
        return None
    if name in _defs(mod):
        return (mod, name)
    names, _ = _imports(mod)
    if name in names and names[name] != (mod, name):
        return _resolve(*names[name], depth=depth + 1)
    return None


def _reach(entry: tuple[str, str]) -> tuple[set[tuple[str, str]], list[str]]:
    """回傳 (可達的 `(模組, 函式)` 集合, **未解析呼叫**清單)。"""
    seen: set[tuple[str, str]] = set()
    unresolved: list[str] = []
    start = _resolve(*entry)
    assert start is not None, f"進入點解析不到：{entry}"
    stack = [start]
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        mod, fname = cur
        node = _defs(mod).get(fname)
        if node is None:
            continue
        mn, mm = _imports(mod)
        ln, lm = _imports(mod, node)
        names, mods, local = {**mn, **ln}, {**mm, **lm}, _defs(mod)
        for n in ast.walk(node):
            if isinstance(n, ast.Call):
                f = n.func
                if isinstance(f, ast.Name):
                    if f.id in local:
                        stack.append((mod, f.id))
                    elif f.id in names:
                        r = _resolve(*names[f.id])
                        if r:
                            stack.append(r)
                        elif _mod_path(names[f.id][0]):
                            unresolved.append(f"{mod}::{fname}:{n.lineno} -> "
                                              f"{names[f.id][0]}.{names[f.id][1]}")
                elif isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name):
                    base = f.value.id
                    tgt = mods.get(base) or (
                        f"{names[base][0]}.{names[base][1]}" if base in names else None)
                    if tgt:
                        r = _resolve(tgt, f.attr)
                        if r:
                            stack.append(r)
            elif isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
                # 裸參照：`safe_section("x", _render_foo)` 這種把函式當值傳出去的。
                if n.id in local:
                    stack.append((mod, n.id))
                elif n.id in names:
                    r = _resolve(*names[n.id])
                    if r:
                        stack.append(r)
    return seen, unresolved


def _st_calls(mod: str, fname: str):
    """該函式體內所有 `<something>.<st 元素名>(...)` 呼叫。"""
    node = _defs(mod).get(fname)
    if node is None:
        return
    for n in ast.walk(node):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
            yield n.func.attr, n


def _kwarg(call: ast.Call, name: str):
    return next((k.value for k in call.keywords if k.arg == name), None)


def _const_str(node, mod: str, depth: int = 0) -> str | None:
    """把 label / key 解析成字面值；解不出回 `None`，f-string 未知段以 `{?}` 表示。"""
    if depth > 4 or node is None:
        return None
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        t = _tree(mod)
        if t is not None:
            for n in t.body:
                tgts = ([x for x in n.targets if isinstance(x, ast.Name)]
                        if isinstance(n, ast.Assign)
                        else [n.target] if (isinstance(n, ast.AnnAssign)
                                            and isinstance(n.target, ast.Name)) else [])
                v = getattr(n, "value", None)
                if any(x.id == node.id for x in tgts) and isinstance(v, ast.Constant):
                    return v.value if isinstance(v.value, str) else None
        return None
    if isinstance(node, ast.JoinedStr):
        out = []
        for v in node.values:
            if isinstance(v, ast.Constant):
                out.append(str(v.value))
            elif isinstance(v, ast.FormattedValue):
                out.append(_const_str(v.value, mod, depth + 1) or "{?}")
            else:
                out.append("{?}")
        return "".join(out)
    if isinstance(node, ast.Call):
        f = node.func
        nm = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "?")
        arg = node.args[0].value if (node.args
                                     and isinstance(node.args[0], ast.Constant)) else ""
        return f"<{nm}({arg!r})>"
    return None


def _is_param_of(mod: str, fname: str, node) -> bool:
    """`node` 是不是 `mod::fname` 這個函式**自己的參數**？（解不出一律 `False`）"""
    fn = _defs(mod).get(fname)
    if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return False
    params = {a.arg for a in
              fn.args.posonlyargs + fn.args.args + fn.args.kwonlyargs}
    if fn.args.vararg:
        params.add(fn.args.vararg.arg)
    if fn.args.kwarg:
        params.add(fn.args.kwarg.arg)
    return isinstance(node, ast.Name) and node.id in params


def _surface(entry: tuple[str, str]) -> dict:
    """一條鏈的**碰撞面**：顯式 key / form key / 無 key 但會註冊的元素 / 動態 key。"""
    seen, unresolved = _reach(entry)
    keys, forms, keyless, dynamic = [], [], [], []
    for mod, fname in sorted(seen):
        for nm, call in _st_calls(mod, fname):
            site = f"{mod}::{fname}:{call.lineno}"
            kv = _kwarg(call, "key")
            if nm == "form":
                fk = kv if kv is not None else (call.args[0] if call.args else None)
                lit = _const_str(fk, mod)
                if lit:
                    forms.append((lit, site))
                elif _is_param_of(mod, fname, fk):
                    # **參數化的 form helper**（如 `ia.gated_form.applied_form`）：
                    # key 由呼叫端決定，實際值在下面的 `applied_form(<literal>)` 一跳收。
                    # ⛔ 這不是豁免 —— 若某個呼叫端傳的不是字面值，那一跳會記進
                    #    `dynamic` 並讓守衛轉紅。
                    pass
                else:
                    dynamic.append((f"form@{site}", site))
                continue
            if nm == "dataframe":
                if _kwarg(call, "on_select") is not None:
                    keyless.append(("dataframe(on_select)", None, site))
                continue
            if nm in REGISTERS_ONLY_WITH_KEY:
                if isinstance(kv, ast.Constant):
                    keys.append((str(kv.value), nm, site))
                continue
            if nm not in REGISTERS_UNCONDITIONALLY:
                continue
            if kv is None:
                _lbl_node = call.args[0] if call.args else _kwarg(call, "label")
                _lbl = _const_str(_lbl_node, mod)
                if _lbl is not None:
                    keyless.append((nm, _lbl, site))
                elif _is_param_of(mod, fname, _lbl_node):
                    # **參數化的共用 helper**：label 由呼叫端決定，兩個呼叫端傳不同字
                    # ⇒ id 不同。機制由 `test_..._shares_no_id_registering_function_...`
                    # 驗，實際值由 form key 那一條驗。
                    # ⛔ 不是豁免：label 若寫死或解不出來，會落到下面那一支變成紅燈。
                    pass
                else:
                    # 既非字面值也非參數 ⇒ 靜態掃描讀不到它的識別資訊。
                    dynamic.append((f"{nm}(label 解析不出)@{site}", site))
            elif isinstance(kv, ast.Constant):
                keys.append((str(kv.value), nm, site))
            else:
                dynamic.append((f"{nm}(dynamic key)", site))
    # `applied_form(<literal>)` —— form key 由 helper 轉手，多追一跳。
    for mod, fname in sorted(seen):
        node = _defs(mod).get(fname)
        for n in (ast.walk(node) if node else ()):
            if isinstance(n, ast.Call):
                f = n.func
                nm = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
                if nm == "applied_form":
                    site2 = f"{mod}::{fname}:{n.lineno}"
                    lit = _const_str(n.args[0], mod) if n.args else None
                    if lit:
                        forms.append((lit, site2))
                    elif not _is_param_of(mod, fname, n.args[0] if n.args else None):
                        # 呼叫端沒有給字面 key ⇒ 靜態掃描讀不到它會用哪個 form_id。
                        dynamic.append((f"applied_form(dynamic key)@{site2}", site2))
    return dict(seen=seen, unresolved=unresolved, keys=keys, forms=forms,
                keyless=keyless, dynamic=dynamic)


# ══════════════════════════════════════════════════════════════════
# 0) 掃描器自身的正／負對照 —— 先證明它會動，再拿它的結論當證據
# ══════════════════════════════════════════════════════════════════
def test_the_scanner_follows_a_re_export_shim():
    """⭐ **正對照** —— 這正是 repo 內既有掃描器斷掉的那個案例。

    `ui/helpers/fund_grp_health_extras.py` 是一個**純 re-export shim**（一個 `def`
    都沒有），而它 re-export 的來源 `ui/helpers/fund_grp_health/__init__.py`
    **本身又是一層 re-export**。也就是說這條路要連追**兩跳**才到得了真正的 `def`。

    ⛔ 這條測試不是裝飾：2026-09-07 的實測顯示，追不進 shim 的掃描器對三個
    危險模組**只看得見一個**，於是它算出來的「交集」是**假的低估**。
    **一份會低估的掃描，比沒有掃描更危險** —— 它會被當成「查過了」。
    """
    shim = "ui.helpers.fund_grp_health_extras"
    assert _mod_path(shim) is not None, "shim 檔不見了 —— 本正對照失去對象，請換一個"
    assert not _defs(shim), (
        f"{shim} 現在有自己的 `def` 了 —— 它不再是純 re-export shim，"
        "本正對照已失去它要對照的東西，請改挑另一個 shim。")
    for sym in ("_render_correlation_matrix", "_render_dividend_matrix"):
        got = _resolve(shim, sym)
        assert got is not None, (
            f"掃描器追不進 re-export shim：{shim}.{sym} 解析成 None。"
            "→ 本檔其餘所有『交集為空』的結論全部不可信，先修掃描器。")
        assert got[0].startswith("ui.helpers.fund_grp_health."), (
            f"{sym} 解析到 {got}，不是預期的子模組")


def test_the_scanner_says_no_when_there_is_nothing_there():
    """**負對照** —— 掃描器不會對不存在的東西回傳成功（否則正對照沒有意義）。"""
    assert _resolve("ui.helpers.fund_grp_health_extras", "_definitely_not_a_symbol") is None
    assert _resolve("ui.no.such.module.at.all", "anything") is None


def test_every_chain_entrypoint_resolves():
    """**輸入非空斷言** —— 九條鏈都要真的解析得到，空集合不得被讀成『沒有碰撞』。"""
    for name, entry in CHAINS.items():
        assert _resolve(*entry) is not None, f"{name} 的進入點 {entry} 解析不到"
        seen, _ = _reach(entry)
        assert len(seen) >= 10, f"{name} 只掃到 {len(seen)} 個函式 —— 掃描器八成壞了"


# ══════════════════════════════════════════════════════════════════
# 1) 「⑨ 不加閘門」的五條前提
# ══════════════════════════════════════════════════════════════════
#: ⑨ 的鏈上**已知的動態派發點**（`模組::函式`）。**這是白名單，也是快門。**
#:
#: ⚠️ **為什麼需要這張表**：本檔第一版的錨只斷言「未解析呼叫 == 0」，而那是
#: **fail-open** 的 —— 突變測試 B6 當場證明：把
#: `safe_section(BLOCK_MIX, _render_mix)` 換成
#: `getattr(__import__("..."), "_render_mix")()`，掃描器**一個 unresolved 都不會記**
#: （它根本沒看見那個呼叫），於是那條錨**綠著放行**。
#: **「沒有偵測到失敗」不等於「沒有東西被漏掉」** —— 這是本檔最重要的一課。
#:
#: 現有兩筆都是**對資料物件的屬性探測**，不是函式派發，本組逐一開檔判讀過：
#:   * `ia.layout::_is_empty` —— `getattr(data, "empty", None)`（pandas 判空）
#:   * `session::friendly_error` —— `getattr(exc, "__traceback__", None)`
#: 兩者都在**九條鏈共用**的 helper 裡，且都不可能是渲染器。
KNOWN_DYNAMIC_DISPATCH: frozenset[str] = frozenset({
    "ui.helpers.ia.layout::_is_empty",
    "ui.helpers.session::friendly_error",
})

#: 會讓靜態追蹤斷掉的呼叫形態。⛔ 只增不減。
_DYNAMIC_CALL_NAMES: frozenset[str] = frozenset({
    "getattr", "setattr", "__import__", "eval", "exec", "globals", "locals", "vars"})


def _dynamic_dispatch_sites(entry: tuple[str, str]) -> dict[str, list[str]]:
    """該鏈上所有**會讓靜態追蹤斷掉**的呼叫形態，依 `模組::函式` 歸戶。"""
    seen, _ = _reach(entry)
    out: dict[str, list[str]] = {}
    for mod, fname in sorted(seen):
        node = _defs(mod).get(fname)
        for n in (ast.walk(node) if node else ()):
            if not isinstance(n, ast.Call):
                continue
            f, why = n.func, None
            if isinstance(f, ast.Name) and f.id in _DYNAMIC_CALL_NAMES:
                why = f"{f.id}()"
            elif isinstance(f, ast.Attribute) and f.attr == "import_module":
                why = "importlib.import_module()"
            elif isinstance(f, ast.Subscript):
                why = "字典／序列派發 D[k]()"
            elif isinstance(f, ast.Call):
                why = "高階回傳值直接呼叫 f()()"
            if why:
                out.setdefault(f"{mod}::{fname}", []).append(f"{why}@{n.lineno}")
    return out


def test_the_new_chain_has_no_new_blind_spot():
    """⭐ **本檔的錨** —— ⑨ 的鏈上不得出現**新的**動態派發點。

    其餘幾條前提都是「交集為空」型的**否定句**，而否定句最容易假綠：
    掃描器看不見的東西，在它眼裡就是不存在。這一條把「**看不見**」本身變成紅燈。

    ⛔ **轉紅時的正解不是把新的那一筆加進 :data:`KNOWN_DYNAMIC_DISPATCH`。**
       那等於把尺改短。正解依序是：
       (1) 把新引入的動態派發改回靜態可追的形態（絕大多數情況都做得到）；
       (2) 真的必要時 —— **開檔判讀它到底會不會派發到渲染器**，
           把判讀結果寫進那張表的註解，**並且**重新評估 ⑨ 要不要補 gate，
           因為本檔其餘幾條「沒有碰撞」的結論**已經不再涵蓋整條鏈**。
    """
    got = _dynamic_dispatch_sites(CHAINS[NEW9])
    new_sites = sorted(set(got) - KNOWN_DYNAMIC_DISPATCH)
    assert not new_sites, (
        "⑨ 的渲染鏈出現**新的**動態派發點，靜態掃描到此為止：\n  "
        + "\n  ".join(f"{k} -> {got[k]}" for k in new_sites)
        + "\n→ 本檔其餘『沒有碰撞』的結論**自此不再涵蓋整條鏈**，不可再當成證據。"
          "\n⛔ 不准把它加進白名單了事，先讀 KNOWN_DYNAMIC_DISPATCH 上方那段。")
    stale = sorted(KNOWN_DYNAMIC_DISPATCH - set(got))
    assert not stale, (
        f"白名單裡這幾筆已經不在 ⑨ 的鏈上了：{stale} —— 請從 "
        "`KNOWN_DYNAMIC_DISPATCH` 移除，否則它會替未來新增的同名項目**預先開好門**。")
    # 輸入非空斷言：白名單若整個掃不到，代表掃描器壞了而不是「很乾淨」。
    assert got, ("一個動態派發點都沒掃到 —— 連已知的兩筆 `getattr` 都不見了，"
                 "掃描器八成壞了，這是假綠不是通過。")


def test_the_new_chain_reports_no_unresolved_call():
    """⑨ 的鏈上，掃描器**偵測得到**的追蹤失敗必須是 0。

    ⚠️ **這一條比較弱，不要單獨依賴它** —— 它只涵蓋「我看見了一個 import 目標
    但找不到它的 def」這一種。「我根本沒看見那個呼叫」由
    :func:`test_the_new_chain_has_no_new_blind_spot` 負責。**兩條一起才是錨。**
    """
    _, unresolved = _reach(CHAINS[NEW9])
    assert unresolved == [], (
        f"⑨ 的渲染鏈出現 {len(unresolved)} 個掃描器追不到的呼叫：{unresolved[:5]}")


def test_the_new_chain_declares_no_explicit_widget_key():
    """⑨ 不得出現顯式 `key=` —— 顯式 key 相撞是**無條件**拋例外的那一種。"""
    s = _surface(CHAINS[NEW9])
    assert s["keys"] == [], (
        f"⑨ 新增了顯式 `key=`：{s['keys']}\n"
        "→ 必須逐一比對它與其餘八條鏈的 key 是否相撞（相撞即 "
        "StreamlitDuplicateElementKey，無條件拋）。")
    assert s["dynamic"] == [], (
        f"⑨ 出現掃描器讀不到值的動態 key：{s['dynamic']}\n"
        "→ 靜態掃描到此為止，這條鏈的碰撞面必須改用別的手段確認。")


def test_the_new_chain_touches_no_io_layer():
    """⑨ 不得到達 I/O 層。

    `st.tabs` 每一次 run 都會執行**所有**分頁的 body ——
    ⑨ 一旦能到達取數層，使用者在**任何**分頁上的每一次互動都會付那個成本，
    而且他人在 ⑨ 上什麼都沒做。這正是 ⑥ / ⑦ 之所以要 gate 的另一半理由。
    """
    seen, _ = _reach(CHAINS[NEW9])
    hits = sorted({f"{m}::{f}" for m, f in seen
                   if any(m.startswith(p) for p in IO_MODULE_PREFIXES)})
    assert hits == [], (
        f"⑨ 的渲染鏈到達了 I/O 層：{hits}\n"
        "→ 「⑨ 不必 gate」的理由之一（打開分頁不取數）已不成立，請重新評估。")


def _identity_is_caller_parameterised(mod: str, fname: str, call: ast.Call) -> bool:
    """這個註冊型元素的 **element id 是不是由呼叫端決定的**？

    element id ＝ hash(型別 ＋ 各 kwargs ＋ `form_id` ＋ root container)。
    所以一個**共用**函式裡的註冊型元素，只有在它的識別資訊**來自該函式的參數**時，
    兩個不同呼叫端才會拿到不同的 id。判準（**兩者都必須成立才算安全**）：

    1. 第一個位置引數（label）是該函式的**參數名**，而不是字面值或模組常數；
    2. 若它包在同一函式內的 `st.form(...)` 裡，那個 form 的 key 也必須是參數名。

    ⛔ **預設不安全**：解不出來、或識別資訊寫死在函式裡 → 一律回 `False`。
       這一點是刻意的 —— 「看不懂就放行」正是本 repo 反覆吃虧的形狀。
    """
    node = _defs(mod).get(fname)
    if node is None or not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return False
    params = {a.arg for a in
              node.args.posonlyargs + node.args.args + node.args.kwonlyargs}
    if node.args.vararg:
        params.add(node.args.vararg.arg)
    if node.args.kwarg:
        params.add(node.args.kwarg.arg)

    def _from_param(x) -> bool:
        return isinstance(x, ast.Name) and x.id in params

    label = call.args[0] if call.args else _kwarg(call, "label")
    if not _from_param(label):
        return False
    # 同一函式內的 `st.form(...)`：它的 key 也必須來自參數，否則兩個呼叫端會共用 form_id。
    for nm2, c2 in _st_calls(mod, fname):
        if nm2 == "form":
            fk = c2.args[0] if c2.args else _kwarg(c2, "key")
            if not _from_param(fk):
                return False
    return True


def test_the_new_chain_shares_no_id_registering_function_with_any_other_tab():
    """⑨ 與其他八條鏈的**共用函式**中，註冊型元素的 id 必須由**呼叫端**決定。

    共用函式是最硬的碰撞：同一個 call site 在同一次 run 被執行兩次 ——
    若型別、參數、`form_id`、root container 全部相同，element id **必然**相同。
    ⚠️ `expander` / `container` 不在此列：它們**只有帶 key 才註冊**（已實測）。

    ⭐ **為什麼不是「共用即紅」（第一版就是，被自己的測試擋下來了，值得記一筆）**
    ---------------------------------------------------------------------------
    `ui/helpers/ia/gated_form.py::applied_form` 是**九條鏈共用**的表單 helper，
    它裡面確實有 `st.form_submit_button(...)`。但它的 id **完全由呼叫端決定** ——
    送出鈕的 label 是參數 `submit_label`，而它所在的 `st.form(key)` 的 key
    也是參數。兩個呼叫端傳不同的 key ⇒ `form_id` 不同 ⇒ element id 不同。

    ⛔ **這不是替它開豁免**（那會是「把尺改短」）。差別在：本函式改成去驗
    **機制本身** —— 識別資訊有沒有被呼叫端參數化。一旦有人把 `applied_form`
    的送出鈕標籤寫死成字面值，或把 form key 寫死，**本條立刻轉紅**。
    ⚠️ 而「呼叫端傳進去的值到底重不重複」是**另一條**在驗
    （:func:`test_the_new_chain_collides_with_no_other_tab` 比對實際的 form key）。
    **兩條合起來才完整：一條驗機制，一條驗實際值。**
    """
    new_seen, _ = _reach(CHAINS[NEW9])
    bad, parameterised = [], []
    for name, entry in CHAINS.items():
        if name == NEW9:
            continue
        for mod, fname in sorted(new_seen & _reach(entry)[0]):
            for nm, call in _st_calls(mod, fname):
                if nm not in REGISTERS_UNCONDITIONALLY:
                    continue
                if _identity_is_caller_parameterised(mod, fname, call):
                    parameterised.append(f"{mod}::{fname} → st.{nm}")
                else:
                    bad.append(f"{name} ∩ ⑨ 共用 {mod}::{fname}:{call.lineno} → st.{nm}")
    assert bad == [], (
        "⑨ 與其他分頁共用了會註冊 element id、**且 id 不由呼叫端決定**的函式：\n  "
        + "\n  ".join(sorted(set(bad)))
        + "\n→ 同一次 run 會畫兩份、id 完全相同 ⇒ StreamlitDuplicateElementId。"
          "\n正解是把識別資訊參數化、移除共用，或替 ⑨ 補 gate。"
          "⛔ 不准把本條放寬。")
    # 輸入非空斷言：本條若因為「一個共用註冊型元素都沒掃到」而綠，那是假綠。
    assert parameterised, (
        "本條沒有掃到任何『共用且會註冊 id』的函式 —— 連已知的 "
        "`ui.helpers.ia.gated_form::applied_form` 都沒掃到，掃描器八成壞了，"
        "這是假綠不是通過。")


@pytest.mark.parametrize("other", [k for k in CHAINS if k != NEW9])
def test_the_new_chain_collides_with_no_other_tab(other):
    """⑨ 的 form key 與「無 key 但會註冊」的元素，都不得與任何一條鏈重複。

    ⚠️ **無 key 的元素同樣會撞** —— element id ＝ hash(型別 ＋ 參數 ＋ `form_id`
    ＋ root container)，而 **root container 不分 tab**。「它們在不同分頁」
    **不是**理由，這是本 repo 最容易誤判的一點。
    """
    new, oth = _surface(CHAINS[NEW9]), _surface(CHAINS[other])
    dup_forms = {k for k, _ in new["forms"]} & {k for k, _ in oth["forms"]}
    assert not dup_forms, (
        f"⑨ 與 {other} 的 `st.form` key 相撞：{sorted(dup_forms)} "
        "→ form_id 就是 key，重複即 StreamlitAPIException（無條件）。")
    dup_kl = {(t, l) for t, l, _ in new["keyless"]} & {(t, l) for t, l, _ in oth["keyless"]}
    assert not dup_kl, (
        f"⑨ 與 {other} 有同型別同標籤的無 key 元素：{sorted(dup_kl, key=str)} "
        "→ 兩邊同一次 run 都會畫 ⇒ StreamlitDuplicateElementId。")


#: ⭐ **⑨ 唯一准許寫入的「別人的」session 契約鍵，連同准許寫它的那一支函式一起釘。**
#:
#: ## 為什麼 2026-09-08 要開這個洞（決策者：**客戶**，不是本組）
#:
#: 客戶拍板逐字：「**加入基金入口：拍板整合至 ⑨「保單與扣款標的」，
#: 無持倉時直接就地展開輸入表單。**」並指定它是退場順序（⑦→⑥→⑧→⑨）的
#: **第一前置**。
#: → 「加入一檔基金」這件事**在定義上**就是往 `portfolio_funds` 寫一筆；
#:   本條原本的「一個字都不准回寫」與那個拍板**直接互斥**。
#:
#: ## 舊條為什麼是對的（它的理由一個字都沒被推翻）
#:
#: 舊 docstring 逐字：「這一條擋的是 widget-key 掃描**結構上看不到**的那種雙軌事故：
#: 新頁安靜地覆寫舊頁的狀態。」**這個顧慮今天完全成立** ——
#: 差別只在「**安靜地**」三個字：本項是客戶點名要的、寫在畫面上按鈕後面的、
#: 而且**寫的是同一份使用者資料本來就該長的樣子**（`loaded=False` 骨架，
#: 與 `repositories/policy/v1.py::sync_policies_to_portfolio_funds` 逐欄位同構）。
#:
#: ## ⛔ 這個豁免有多窄（三道，缺一不可）
#:
#: 1. **只有這一個鍵**（`portfolio_funds`）。`policy_sheet_id` / `t7_ledgers` /
#:    `_t3_cur_sheet_title` 等**照舊一個字都不准寫**。
#: 2. **只有這一支函式**（`_render_add_fund`）。同一頁別處寫同一個鍵**照樣紅** ——
#:    那才是「安靜覆寫」真正會發生的形狀。
#: 3. 由 :func:`test_the_foreign_write_allowlist_is_exact_and_named` 釘住清單本身：
#:    多一項就要有人來改那一條，**那個「要有人來改」就是這道關卡**。
_FOREIGN_WRITE_OK: frozenset[tuple[str, str, str]] = frozenset({
    ("ui.views.page_04_portfolio", "_render_add_fund", "portfolio_funds"),
})


def test_the_foreign_write_allowlist_is_exact_and_named():
    """⭐ 上面那個放行清單本身要被守住。**恰好一項，而且三個欄位都要對。**

    ⛔ 清空它 → 本條紅（那會撤銷客戶 2026-09-08 的拍板）；
    ⛔ 多一項 → 本條紅（多一處寫入就要有人負責）。
    ⚠️ **本條不渲染**，在沒有 streamlit 的環境也跑得到。
    """
    assert _FOREIGN_WRITE_OK == frozenset({
        ("ui.views.page_04_portfolio", "_render_add_fund", "portfolio_funds"),
    }), (
        f"放行清單被改成 {sorted(_FOREIGN_WRITE_OK)}。\n"
        "⛔ 客戶 2026-09-08 只點名了「加入基金入口」這一件事 —— "
        "多一項就要有人來改這一條，那個「要有人來改」就是這道關卡本身。")
    for _mod, _fn, _key in _FOREIGN_WRITE_OK:
        assert not _key.startswith("v04_"), (
            f"`{_key}` 是 ⑨ 自己的命名空間，本來就准寫 —— "
            "把它放進豁免清單只會讓清單看起來比實際需要的長。")


def test_the_new_chain_writes_only_its_own_session_namespace():
    """⑨ 只准寫自己命名空間的 session key —— 讀別人的可以，寫別人的**原則上**不行。

    這一條擋的是 widget-key 掃描**結構上看不到**的那種雙軌事故：
    新頁安靜地覆寫舊頁的狀態。⑨ 讀 `portfolio_funds` / `policy_sheet_id` 等
    由舊 ④ 寫入的鍵是**刻意**的（同一份使用者資料）。

    ## ⚠️ 2026-09-08：多了**一個**具名例外，理由與邊界見 :data:`_FOREIGN_WRITE_OK`

    ~~「但它一個字都不准回寫。」~~ —— **有意識的政策變更，不是漏刪**
    （決策者：**客戶**，2026-09-08 拍板「加入基金入口整合至 ⑨」）。
    **放行的是 `(模組, 函式, 鍵)` 三元組**，不是「那個鍵」也不是「那一頁」——
    同一頁別的函式寫同一個鍵，本條照樣紅。

    ⛔ **實作端不准用掃描器看不到的寫法繞過本條。**
       `st.session_state["portfolio_funds"].append(...)` 在 AST 上**不是**對
       `session_state[...]` 的指派，本條**看不到它** —— 被測檔就地註解已寫明
       它刻意用整份指派而不是 `.append`，理由逐字是
       「用一個掃描器看不到的寫法把寫入偷渡進來，比違規本身更糟」。
       ⚠️ **這是一個已知缺口，不是保證**：本條擋得住「明目張膽的指派」，
       擋不住「就地變異」。**照實寫在這裡，不假裝守死了。**

    ## ⭐ 2026-09-08：補起**第二個**盲點 —— 屬性指派（獨立稽核突變抓到）

    在此之前本條只看 `ast.Subscript` 目標，也就是 `session_state["k"] = …`。
    稽核的突變 `st.session_state.portfolio_funds = …`（**屬性指派**）
    **完全沒有被殺**。而那個盲點**正好開在最可能被用到的形狀上** ——
    舊 ④ `ui/tab3_portfolio.py` 與 `ui/helpers/portfolio/load.py` 的慣用寫法
    就是屬性式（例：`st.session_state.portfolio_funds = []`）。
    也就是說：一個從舊 ④ 複製過來的寫法，會**直接穿過**這道守衛。

    → 本輪把 `ast.Attribute` 目標一起收（`t.attr` 就是鍵名）。
    ⚠️ **這是把守衛改嚴，不是改鬆**：收進來的形狀只會**多**紅、不會少紅。
       實測補之前補之後 ⑨ 的可達集合都是 **0 個違規**（新鏈一處屬性指派都沒有），
       所以本次強化**不靠放寬任何既有斷言換綠燈**。
    ⚠️ **仍然沒有補起來的是 `.append` / `.pop` 那種「就地變異」**（上一段那個缺口）——
       兩個盲點是**不同**的東西，補了這個不代表那個也好了。**不要合併讀。**
    """
    seen, _ = _reach(CHAINS[NEW9])
    own_prefix = "v04_"
    bad: list[str] = []
    for mod, fname in sorted(seen):
        node = _defs(mod).get(fname)
        for n in (ast.walk(node) if node else ()):
            tgts = (n.targets if isinstance(n, ast.Assign)
                    else [n.target] if isinstance(n, (ast.AugAssign, ast.AnnAssign))
                    else [])
            for t in tgts:
                # 形態 1：`session_state["k"] = …`（下標）
                if (isinstance(t, ast.Subscript)
                        and "session_state" in ast.dump(t.value)):
                    key = _const_str(t.slice, mod)
                # 形態 2：`session_state.k = …`（**屬性**，2026-09-08 補）
                elif (isinstance(t, ast.Attribute)
                      and "session_state" in ast.dump(t.value)):
                    key = t.attr
                else:
                    continue
                if key is not None and key.startswith(own_prefix):
                    continue
                if (mod, fname, key) in _FOREIGN_WRITE_OK:
                    continue          # 具名豁免，見 `_FOREIGN_WRITE_OK` 的長註
                bad.append(f"{mod}::{fname}:{n.lineno} 寫入 session_state[{key!r}]")
    assert bad == [], (
        "⑨ 寫入了不屬於自己命名空間（`v04_` 前綴）、也不在具名豁免清單裡的 "
        "session key：\n  "
        + "\n  ".join(bad)
        + "\n→ 雙軌之下這會讓新頁安靜地覆寫舊 ④ 的狀態，"
          "而任何 widget-key 掃描都看不到它。"
        + f"\n（唯一的具名豁免：{sorted(_FOREIGN_WRITE_OK)} —— "
          "見 `_FOREIGN_WRITE_OK` 的長註）")


# ══════════════════════════════════════════════════════════════════
# 2) 接線本身
# ══════════════════════════════════════════════════════════════════
def test_app_mounts_the_ninth_tab_through_the_preview_namespace():
    """⑨ 必須經 `preview_tab_label('portfolio')` 掛載，`app.py` 內零字面值。"""
    src = (ROOT / "app.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and n.func.attr == "tabs"]
    assert len(calls) == 1, f"app.py 的 `st.tabs` 呼叫不是恰好 1 個，而是 {len(calls)}"
    elts = calls[0].args[0].elts
    last = elts[-1]
    assert isinstance(last, ast.Call), "分頁列最後一格不是函式呼叫"
    fn = last.func.attr if isinstance(last.func, ast.Attribute) else last.func.id
    assert fn.lstrip("_") == "preview_tab_label", (
        f"⑨ 不是走 `preview_tab_label`，而是 {fn} —— "
        "預覽分頁的名字必須與正式分頁分屬兩個命名空間。")
    assert last.args[0].value == "portfolio", (
        f"最後一格的 key 是 {last.args[0].value!r}，不是 'portfolio'")
    from ui.helpers.story_nav import PREVIEW_TAB_LABELS, tab_label
    # ⚠️ 只看**活字串**（AST 的 `ast.Constant`），不看註解 —— 與既有守衛
    #    `test_no_live_string_hardcodes_a_tab_name` 同一個判準。
    #    ⛔ 拿原始碼文字直接 `in` 會把 `# TAB ④ — 📊 資產配置（…）` 這種**註解**
    #       算成違規（本檔第一版就是這樣，當場被自己的測試擋下來）。
    #       註解裡寫分頁名是**對的**：它不會被渲染，改名時也不會指錯人。
    _live = {n.value for n in ast.walk(tree)
             if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    _leaked = sorted(v for v in _live if tab_label("portfolio") in v)
    assert not _leaked, (
        f"⑨ 的分頁名出現在 app.py 的活字串裡：{_leaked} —— "
        "那正是本 repo 發作過三次的第二份標籤。")
    assert PREVIEW_TAB_LABELS["portfolio"] not in _live, (
        "⑨ 的預覽標籤以活字串寫死在 app.py，沒有走 `preview_tab_label`。")
    assert PREVIEW_TAB_LABELS["portfolio"].endswith(tab_label("portfolio")), (
        "預覽標籤沒有從 `_TAB_LABELS` 導出 —— 正式分頁改名時它不會跟上。")


def test_the_ninth_tab_stays_inside_the_fetch_diag_owner_block():
    """⑨ 的 `with tab_preview_portfolio:` 必須在 owner 區塊內。

    ⚠️ **理由與 ⑦ 不同，不要照抄**：⑦ 是因為它自己會畫抓取診斷；
    ⑨ 底下一塊都沒有。⑨ 要留在裡面，純粹是因為
    `test_fetch_diag_is_owned_by_app` 要求「**全檔每一個** `with tab_*:`」
    都在 owner 區塊內 —— 那條規則刻意不開例外。
    """
    tree = ast.parse((ROOT / "app.py").read_text(encoding="utf-8"))
    owner = [n for n in ast.walk(tree) if isinstance(n, ast.With) and any(
        isinstance(i.context_expr, ast.Call)
        and getattr(i.context_expr.func, "id", "").lstrip("_") == "settings_page_owns"
        for i in n.items)]
    assert len(owner) == 1, f"owner 區塊不是恰好 1 個，而是 {len(owner)}"
    inside = {n.items[0].context_expr.id for n in ast.walk(owner[0])
              if isinstance(n, ast.With) and isinstance(n.items[0].context_expr, ast.Name)}
    assert "tab_preview_portfolio" in inside, (
        "`with tab_preview_portfolio:` 不在 `settings_page_owns(FETCH_DIAG)` 區塊內 —— "
        "`test_fetch_diag_is_owned_by_app` 會轉紅。")


def test_the_ninth_tab_is_isolated_like_every_other_tab():
    """⑨ 的 body **第一層**要看得到 `Try`，錯誤標題要走 `_preview_tab_label`。

    ⛔ 不得把 try/except 收成 helper：兩條既有守衛要求第一層就有 `Try` 節點，
    而它們守的是 user 實際回報過的「小按鈕壓下就整頁跳出來」事故。
    """
    tree = ast.parse((ROOT / "app.py").read_text(encoding="utf-8"))
    blk = next(n for n in ast.walk(tree)
               if isinstance(n, ast.With) and isinstance(n.items[0].context_expr, ast.Name)
               and n.items[0].context_expr.id == "tab_preview_portfolio")
    assert any(isinstance(x, ast.Try) for x in blk.body), (
        "⑨ 的 body 第一層沒有 `Try` —— 分頁隔離守衛會轉紅。")
    dumped = ast.dump(blk)
    assert "preview_tab_label" in dumped, "⑨ 的錯誤標題沒走 `_preview_tab_label`"
    assert "render_asset_allocation" in dumped, "⑨ 沒有呼叫 `render_asset_allocation`"
