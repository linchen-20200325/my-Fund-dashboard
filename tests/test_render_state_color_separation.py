"""顏色五態分離 —— 守「形狀」而不是守字面。

客戶 2026-08-28 拍板（線框 `fund-empty-state-wireframe.html` §03）：
> 嚴格分離「業務紅燈」與「系統真紅燈」，未載入／未設定一律改灰色說明，
> 把用灰字印的真失敗改回系統紅燈。

本檔**刻意不做逐字斷言**。逐字斷言守不到語意 —— 姊妹 repo 實證過：一句假話被逐字
釘住之後，測試天天綠、話卻一直是假的。這裡守的是三種**結構**：

1. 手上有 exception → 一定不能用灰色 widget（`st.caption` / `st.info`）印出去。
   （AST：except handler 綁定的變數，不得出現在灰色 widget 的參數裡。）
2. 「金鑰／資料源沒設定」這種分支 → 一定不能用警示色 widget（`st.error` / `st.warning`）。
3. 三個入口自己畫出來的 widget 種類必須是對的（否則上面兩條可以靠改 helper 內容繞過）。
4. （2026-08-28 批次二之一新增）**同一個失敗在不同分頁必須是同一個顏色入口**
   —— `test_twin_failures_wear_the_same_colour`。批次一只做了組合健診，於是有三組
   「文案逐字相同 / 同一個 render 函式 / 同一個 repository 呼叫」的失敗，
   在 A 分頁是 🔴、在 B 分頁是灰字。**顏色帶的資訊變成「你在哪個分頁」，
   而不是「這件事嚴不嚴重」** —— 那比一開始就全灰更糟，因為它連一致的預期都毀了。

⚠️ 第 1、2 條是**單向**的：它們抓的是「畫錯顏色」，不是「有沒有畫」。
一個 except handler 什麼都不印（靜默吞掉）**不會**被本檔抓到 —— 那屬 §1 Fail Loud 的
守備範圍，不是本檔的。寫在這裡是為了讓下一個人知道本檔的邊界在哪。
（第 4 條是這個單向性的**部分**補償：它要求那三組呼叫必須存在，刪掉就紅。
  但它只覆蓋那三組，不是全域。）

⚠️ **receiver 盲點：已知 5 種，補了 4 種（2026-08-28，稽核 A1 後更新）**
規則看不見的寫法，等於規則在那個方向上沒有生效。
**已補（每一種都有突變實證會轉紅）**：
  (a) `st.sidebar.error(...)` —— 屬性鏈（第三輪補）；
  (b) `_cols[2].error(...)` —— receiver 是 `ast.Subscript`（本批補，見 `_receiver_root`）；
  (c) `col1.error(...)` —— receiver 是 `st.columns()` 綁出來的名字（本批補，見 `_st_container_names`）；
  (d) `_st_c.caption(...)` —— `import streamlit as _st_c` 的**模組別名**（本批補，
      見 `_st_module_aliases`）。⚠️ 這個形狀**已經活在本批自己的 scope 裡**：
      `ui/tab1_macro.py:306`、`ui/helpers/macro/ndc.py:61`。
**未補（實測仍為綠，不要讀成已經補完）**：
  (e) `getattr(st, "sidebar").caption(...)` —— 動態取屬性，靜態看不出來；
  (f) `from streamlit import caption as _cap` 之後直接 `_cap(...)` —— 連 receiver 都沒有。
  兩者本輪各跑過一次突變確認**仍然全綠**（32 passed）。要補 (f) 需要追蹤
  `ImportFrom` 綁定，(e) 需要處理動態屬性 —— 已登記待後批。
⚠️ **另外兩個仍然看不見的方向**：跨函式傳進來的容器、存進 dict / list 的容器
（`_st_container_names` 只認同一檔內由 `<streamlit 名>.<factory>(...)` 直接綁出的名字）。
本批對 (b)(c)(d) 各跑了**負控制 / 突變**，確認是靠加寬才抓得到的，不是別的規則順手抓到。
"""
from __future__ import annotations

import ast
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]

# 第一批（客戶拍板）涵蓋的範圍：組合健診套件 + 它的 Tab 主檔。
HEALTH_SCOPE = sorted((ROOT / "ui" / "helpers" / "fund_grp_health").glob("*.py")) + [
    ROOT / "ui" / "tab_fund_grp_health.py"
]

# 第二批之一（2026-08-28）：把方向 A 擴到其餘分頁後，**本批實際逐處轉換完的檔案**。
# ⚠️ 這是「已經清乾淨、從此不准回頭」的清單，不是「打算要做」的清單 ——
# 沒清乾淨的檔案放進來只會讓 CI 紅，那正是它的用途。
# ⚠️ 全 repo 還沒清完的那幾處由 `test_a_caught_exception_backlog_only_shrinks`
# 的 ratchet 管，**不是**放進本清單然後假裝做完了。
BATCH2A_SCOPE_A = [ROOT / p for p in (
    "ui/helpers/nav_history_hook.py",
    "ui/helpers/portfolio_perf.py",
    "ui/hot_money.py",
    "ui/tab1_macro.py",
    "ui/tab1_macro_inflection.py",
    "ui/tab1_macro_longterm.py",
    "ui/tab1_macro_radar.py",
    "ui/tab2_single_fund.py",
    "ui/tab3_portfolio.py",
    "ui/tab3_t7_ledger.py",
    "ui/tab5_data_guard.py",
    "ui/tab6_manual.py",
    "ui/tab_batch_analysis.py",
    "ui/tab_manage.py",
)]

# 會把東西「印給使用者看」的呼叫：st.* 全部 + 專案自己的錯誤呈現入口。
# 「會把東西印到畫面上」的 st API。⚠️ 2026-08-28 第二輪稽核 A3：上一版漏了
# `metric` / `dataframe` / `table` / `json` / `latex` —— 用它們印例外一樣看得到，
# 卻不會被規則 1 抓到。集合漏一個，規則就在那個方向上是瞎的。
# ⚠️ **本集合現在仍然不完整（第三輪稽核 P6 實測放行）**：至少還漏
# `subheader` / `title` / `header`；`st.badge` 等新 API 也未納入。
# 上一輪只寫了「漏一個就瞎」這句話，卻沒把「它現在仍然漏著」列出來 ——
# 補在這裡，**不要讀成「已經補齊」**。補齊需要逐一對 Streamlit API 表，列第二批。
_ST_RENDER_ATTRS = {"caption", "info", "warning", "error", "success", "markdown",
                    "write", "text", "code", "toast", "exception",
                    "metric", "dataframe", "table", "json", "latex"}
_FUNC_RENDERERS = {"system_error", "friendly_error", "_friendly_error", "not_ready",
                   "business_alert"}
# 合格的「系統紅燈」入口（🔴 紅色錯誤框 + 可展開技術細節）。
RED_ENTRYPOINTS = {"system_error", "friendly_error", "_friendly_error", "st.error",
                   "st.exception"}


def _receiver_root(node: ast.AST) -> str | None:
    """把 `st` / `st.sidebar` / `st.sidebar.foo` / `_cols[2]` 剝到最左邊的名字。

    ⚠️ 2026-08-28 顏色批次二之一：上一版只剝 `ast.Attribute`，於是
    `_top_cols[2].error(...)`（receiver 是 `ast.Subscript`）回 None →
    **對本檔每一條規則都是隱形的**。這與第三輪 `st.sidebar.*` 那次是同一個病的
    第二種形狀：規則看不見的寫法，等於規則在那個方向上沒有生效。
    查證指令（本批實跑，量測日 2026-08-28 → **7 命中**）::

        python -c "
        import ast, pathlib
        R = {'caption','info','warning','error','success','markdown','write','text',
             'code','toast','exception','metric','dataframe','table','json','latex'}
        print([(str(p), n.lineno, ast.unparse(n.func))
               for p in pathlib.Path('ui').rglob('*.py')
               for n in ast.walk(ast.parse(p.read_text()))
               if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
               and n.func.attr in R and isinstance(n.func.value, ast.Subscript)])"

    其中 `ui/tab3_t7_ledger.py:1986` 的 `_top_cols[2].error(...)` **顏色本來就是對的**
    （抓不到基金 → 真失敗）—— 問題不在那一處畫錯，而在**本檔完全看不到它**。
    """
    while isinstance(node, (ast.Attribute, ast.Subscript)):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


# `st.columns(...)` / `st.tabs(...)` / `st.container()` … 綁出來的名字＝**還是 streamlit**。
# 少了這一層，`col1.error(...)` / `_cols[2].warning(...)` 對所有規則都是隱形的。
_ST_CONTAINER_FACTORIES = frozenset({
    "columns", "tabs", "container", "empty", "expander", "form",
    "popover", "status", "chat_message",
})


def _st_module_aliases(tree: ast.AST) -> frozenset[str]:
    """這個模組把 streamlit 綁成了哪些名字？（`import streamlit as st` / `as _st_c` …）

    ⚠️ 2026-08-28 稽核 A1：上一版把 `"st"` **硬編碼**在比對式裡，於是
    `import streamlit as _st_c` 之後的 `_st_c.caption(例外)` 對每一條規則都是隱形的。
    **這個形狀已經活在本批自己的 scope 裡**：`ui/tab1_macro.py:306`
    （`_render_macro_indicator_card` 內 `import streamlit as _st_c`）、
    `ui/helpers/macro/ndc.py:61`（`import streamlit as _st_mod`）。
    今天那兩處都是良性的（沒拿它印例外），但形狀在，規則就得看得見。
    """
    out = {"st"}
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                if a.name == "streamlit" and a.asname:
                    out.add(a.asname)
    return frozenset(out)


def _st_container_names(tree: ast.AST) -> frozenset[str]:
    """這個模組裡，哪些名字「就是 streamlit」？＝ 模組別名 ∪ 由它們綁出來的容器。

    （`c1, c2 = st.columns(2)` 之類；容器工廠也認別名，例：`c1 = _st_c.columns(2)`。）

    ⚠️ 刻意**只認同一個檔案內、由 `st.<factory>(...)` 直接綁出來的名字**：
    再往外推（跨函式傳遞、存進 dict）需要跨程序資料流分析，不在本批範圍內。
    也就是說本函式**縮小了**盲點，沒有消滅它 —— 別把它讀成「容器已經全看得到」。
    刻意不認 `logging.getLogger(__name__).warning(...)` 這種同形狀但非 streamlit 的
    呼叫，正是靠「名字必須綁自 `st.<factory>`」這條限制擋掉的
    （查證：`ui/tab1_macro_longterm.py:362` 的 `_lg_news.getLogger(...).warning`
      在本函式下**不會**被認成 streamlit，因為 `_lg_news` 綁的是 `import logging`）。
    """
    out: set[str] = set(_st_module_aliases(tree))
    for n in ast.walk(tree):
        pairs = []
        if isinstance(n, ast.Assign):
            pairs = [(t, n.value) for t in n.targets]
        elif isinstance(n, ast.With):
            pairs = [(i.optional_vars, i.context_expr)
                     for i in n.items if i.optional_vars is not None]
        for tgt, val in pairs:
            if not (isinstance(val, ast.Call) and isinstance(val.func, ast.Attribute)):
                continue
            if (_receiver_root(val.func.value) not in out
                    or val.func.attr not in _ST_CONTAINER_FACTORIES):
                continue
            for x in ast.walk(tgt):
                if isinstance(x, ast.Name):
                    out.add(x.id)
    return frozenset(out)


def _callee(call: ast.Call, containers: frozenset[str] = frozenset()) -> str:
    """呼叫的**正規化**名稱：st 屬性鏈一律收斂成 `st.<attr>`。

    ⚠️ 2026-08-28 第三輪稽核：上一版要求 receiver 是**裸** `ast.Name` 且 id == "st"，
    於是 `st.sidebar.error(...)` 的 `call.func.value` 是 `ast.Attribute`（`st.sidebar`）
    → 回 `"<?>"` → **規則 1／B1／B2／C／ratchet 全部看不見它**。
    這不是「少守一點」：本 PR 自己改過的 `ui/sidebar.py` 裡就有一個反例 ——
    第 76 行的「Proxy 未設定」被本批改成灰色，**六行之後**同一句話的
    `st.sidebar.error("Proxy 未設定")` 還是紅的，而「未設定」正是
    `NOT_CONFIGURED_PHRASES` 的第一個詞，B2 的設計意圖就是抓它。

    正規化成 `st.<attr>` 是刻意的：既有規則集（`RED_ENTRYPOINTS`、`_ST_RENDER_ATTRS`…）
    一個字都不用改，`st.sidebar.error` 自動被當成 `st.error` 處理 —— 它本來就是紅框。
    要在訊息裡顯示真實寫法時用 `_callee_src()`。
    """
    if isinstance(call.func, ast.Attribute):
        _root = _receiver_root(call.func.value)
        # `st.*` / `st.sidebar.*` / `col1.*` / `_cols[2].*` 一律收斂成 `st.<attr>`：
        # 由 `st.columns()` 綁出來的容器，畫出來的東西**就是 streamlit 元件**。
        if _root == "st" or (_root is not None and _root in containers):
            return f"st.{call.func.attr}"
        if isinstance(call.func.value, ast.Name):
            return f"{call.func.value.id}.{call.func.attr}"
        return "<?>"
    if isinstance(call.func, ast.Name):
        return call.func.id
    return "<?>"


def _callee_src(call: ast.Call) -> str:
    """訊息用：實際寫法（`st.sidebar.error`），不是正規化後的名字。"""
    try:
        return ast.unparse(call.func)
    except Exception:  # noqa: BLE001 — 只是訊息好看，壞了不該讓測試爆掉
        return _callee(call)


def _rendering_calls(node: ast.AST, containers: frozenset[str] = frozenset()):
    """node 底下所有「會印東西給使用者看」的呼叫。"""
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Call):
            continue
        name = _callee(sub, containers)
        if ((name.startswith("st.") and sub.func.attr in _ST_RENDER_ATTRS)
                or name in _FUNC_RENDERERS):
            yield sub


def _names_in(node: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


# 「這個值是從例外衍生來的」—— 不綁 `as e` 也能拿到例外內容的幾條路。
_EXC_DERIVED_CALLS = {"format_exc", "exc_info", "print_exc", "format_exception"}


def _contains(scope: ast.AST, target: ast.AST) -> bool:
    return any(n is target for n in ast.walk(scope))


def _visible_names(node: ast.AST) -> set[str]:
    """node 內用到的名字，**跳過被 comprehension 重新綁定的那些**。

    ⚠️ 2026-08-28 第二輪稽核 A2(a)：`except KeyError as e:` 之後寫
    `[x.name for e in entries]`／`[e.name for e in entries]` —— 那個 `e` 是
    comprehension **自己的**綁定，跟 handler 的 `e` 無關。而
    `for e in ...` **正是本 package 的現行慣例**（`switch_advisor_section` 就是），
    上一版會把這種完全合規的寫法叫去改成紅框。
    """
    shadow = []
    for sub in ast.walk(node):
        if isinstance(sub, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            bound = {n.id for gen in sub.generators for n in ast.walk(gen.target)
                     if isinstance(n, ast.Name)}
            if bound:
                shadow.append((sub, bound))
    out = set()
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Name):
            continue
        if any(sub.id in bound and _contains(scope, sub) for scope, bound in shadow):
            continue
        out.add(sub.id)
    return out


def _assign_pairs(node):
    """把賦值拆成 (目標, 來源值) 對；tuple 解包逐元素配對。

    ⚠️ 2026-08-28 第二輪稽核 A2(b)：`_reason, _n = str(e), len(rows)` ——
    上一版整條連坐，`_n`（只是筆數）也被當成帶著例外內容。
    """
    if isinstance(node, ast.Assign):
        value = node.value
        for tgt in node.targets:
            if (isinstance(tgt, (ast.Tuple, ast.List))
                    and isinstance(value, (ast.Tuple, ast.List))
                    and len(tgt.elts) == len(value.elts)):
                yield from zip(tgt.elts, value.elts)
            else:
                yield tgt, value
    elif isinstance(node, (ast.AnnAssign, ast.AugAssign)) and node.value is not None:
        yield node.target, node.value
    elif isinstance(node, ast.For):
        # `for line in traceback.format_exc().splitlines():` → line 帶著例外內容
        yield node.target, node.iter
    elif isinstance(node, ast.With):
        for item in node.items:
            if item.optional_vars is not None:
                yield item.optional_vars, item.context_expr


def _exception_tainted_names(handler: ast.ExceptHandler) -> set[str]:
    """這個 handler 裡，哪些名字「帶著例外的內容」？

    盲點 (a)（稽核組 2026-08-28 實測可繞過）：
        `except Exception as e:  _m = f"{type(e).__name__}: {e}";  st.caption(_m)`
    —— 印出去的是 `_m` 不是 `e`，只比對 `handler.name` 會放行。
    這裡做一次**傳遞閉包**：凡是賦值右邊碰到已污染的名字，左邊也污染，直到不動點。
    """
    tainted = {handler.name} if handler.name else set()
    changed = True
    while changed:
        changed = False
        for node in ast.walk(handler):
            for tgt, value in _assign_pairs(node):
                # 不綁 `as e` 但直接抓 traceback / exc_info 的，也算拿到例外內容
                derived = bool(_visible_names(value) & tainted) or any(
                    (isinstance(n, ast.Attribute) and n.attr in _EXC_DERIVED_CALLS)
                    or (isinstance(n, ast.Name) and n.id in _EXC_DERIVED_CALLS)
                    for n in ast.walk(value))
                if not derived:
                    continue
                for n in ast.walk(tgt):
                    if isinstance(n, ast.Name) and n.id not in tainted:
                        tainted.add(n.id)
                        changed = True
    return tainted


def _call_shows_exception(call: ast.Call, tainted: set[str]) -> bool:
    if _visible_names(call) & tainted:
        return True
    # 盲點 (b)：`except Exception:`（不綁）＋ 直接把 traceback 印出去
    return any(
        (isinstance(n, ast.Attribute) and n.attr in _EXC_DERIVED_CALLS)
        or (isinstance(n, ast.Name) and n.id in _EXC_DERIVED_CALLS)
        for arg in [*call.args, *(k.value for k in call.keywords)]
        for n in ast.walk(arg)
    )


def _direction_a_violations(path: pathlib.Path) -> list[str]:
    """方向 A 的違規：except handler 抓到例外、拿它去印，卻不是系統紅燈入口。

    逐檔規則與全域 ratchet **共用這一個函式** —— 兩把尺量同一件事卻各寫一份，
    是本檔第二輪稽核 A7 記載的那種「三把尺互相加減」的來源。
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    containers = _st_container_names(tree)
    parent = {}
    for n in ast.walk(tree):
        for c in ast.iter_child_nodes(n):
            parent[c] = n
    bad = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        tainted = _exception_tainted_names(node)
        for call in _rendering_calls(node, containers):
            if not _call_shows_exception(call, tainted):
                continue                      # 沒把例外拿給使用者看 → 不歸本檔管
            if _callee(call, containers) in RED_ENTRYPOINTS:
                continue                      # 已經是系統紅燈
            cur, fname = call, "<module>"
            while cur in parent:
                cur = parent[cur]
                if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    fname = cur.name
                    break
            bad.append(f"{path.relative_to(ROOT)}::{fname}()"
                       f"  (line {call.lineno} {_callee_src(call)})")
    return bad


def _direction_a_site_keys(path: pathlib.Path) -> list[str]:
    """違規站點的**結構鍵**：`相對路徑::函式()`，**不含行號**（行號會漂）。

    ratchet 拿它比「是哪幾處」，而不只是「有幾處」—— 見
    `test_a_caught_exception_backlog_only_shrinks` 對淨零置換的說明。
    """
    return [v.split("  (line ")[0] for v in _direction_a_violations(path)]


@pytest.mark.parametrize("path", HEALTH_SCOPE + BATCH2A_SCOPE_A, ids=lambda p: p.name)
def test_caught_exception_is_reported_as_a_system_failure(path: pathlib.Path):
    """真的壞掉了，畫面卻只是「還沒載入」—— 這是本批要修掉的那個 bug。

    判準（結構，不是字面）：這個 except handler **抓到了一個 exception，而且拿它去
    印給使用者看** → 那就是系統真出錯，印它的那個呼叫必須是「系統紅燈」入口。

    合格的系統紅燈入口只有兩個：
    - `ui.helpers.render_state.system_error()`（本批新增，走 friendly_error）
    - `st.error()` / `friendly_error()`（既有的正確寫法，未被本批動到的沿用）

    刻意**不**檢查訊息內容 —— 文案會被改寫，widget 種類不會。

    ⚠️ **本規則守得到什麼、守不到什麼（2026-08-28 稽核 T4 後更新，請照這個打折）**
    守得到：
      - 直接印 `as e` 綁定的名字；
      - 印一個**從 `e` 衍生**出來的中間變數（`_m = f"...{e}"` → `st.caption(_m)`），
        含 `for x in <衍生值>` 與 `with <衍生值> as x` 的綁定；
      - 不綁 `as e`、直接印 `traceback.format_exc()` / `sys.exc_info()`。
    不會誤抓（2026-08-28 稽核 A2 修正的兩個 false positive）：
      - comprehension 自己的綁定遮蔽 handler 名字（`[x for e in entries]`）；
      - tuple 解包時只有對應那一格被污染（`_reason, _n = str(e), len(rows)` → `_n` 乾淨）。
    **仍守不到**（已知盲點，不要以為守得住 —— 2026-08-28 稽核 A3 補第 4 種）：
      1. handler 什麼都不印（靜默吞掉）—— 屬 §1 Fail Loud 的守備範圍，不是本檔的；
      2. 例外內容先寫進 `dict` / `list` / `st.session_state` 再由**別的函式**印出去；
      3. ⭐ **同一個 handler 內**用容器累積後再印：`failures.append((code, e))` 之後
         印 `failures` —— 本檔只追蹤**名字之間**的傳遞，不追蹤「值進了容器」。
         ⚠️ 這正是本批新引進的 `_fetch_rich` / `_report_pool_fetch_failures` 的形狀
         （那一組是安全的：容器最後交給 `system_error`），但**規則沒有在守它**；
      4. 例外被轉成一個不含任何原名的字面字串（`st.caption("抓取失敗")`）——
         結構上與「這格沒資料」無法區分，只能靠 review；
      5. ⭐ **`except Exception:`（未綁 `as`）＋ 印出「函式參數裡的那個例外」**
         （2026-08-28 稽核 A2 揭露，本批**未修**）。實例：`ui/tab_manage.py`
         的 `_friendly(title, e, level=...)` —— 內層 `except Exception:` 沒有綁定，
         而 `st.caption(...)` 印的 `e` 是**外層函式的參數**。本檔的 taint 只從
         `handler.name` 出發，看不到「參數本身就是一個例外物件」這件事。
         ⚠️ **這正是兩把獨立的尺量出 47 vs 48 的唯一差額** —— 據實記在這裡，
         不要把 47 讀成「全部」。要補需要型別/命名推斷（哪個參數是 Exception），
         不在「只做顏色」這一批的範圍內。
    """
    bad = _direction_a_violations(path)
    assert not bad, (
        "以下位置把「抓到的例外」用非紅燈 widget 印出去，使用者會誤以為只是還沒載入、"
        "以為按一下就好；請改走 ui.helpers.render_state.system_error()：\n  "
        + "\n  ".join(bad)
    )


# ── 方向 A 的全域 ratchet：範圍外還沒清的，只准變少 ────────────────
# 2026-08-28 顏色批次二之一實測：`origin/main`（461f811）全 `ui/**` + `app.py`
# 共 **47 處**；本批轉換 43 處，**刻意留下 4 處**（不是漏改，各自就地寫了理由）：
#   ui/helpers/fund/checkup.py         逐檔迴圈 → 改紅會犯 M1「N 檔 N 個紅框」
#   ui/helpers/portfolio/fee_deduction.py  同上（逐保單迴圈）
#   ui/helpers/portfolio/load.py       逐檔進度 log，且失敗已由下方彙總上報
#   ui/sidebar.py                      下一行就是 st.rerun()，只有 toast 活得過去
# 這四處的正解都是**結構改動**（收集→彙總 / 跨 rerun 保存），不是換顏色。
# ⚠️ 這不是豁免清單，是**待辦的可見化**：數字只准往下走。
# ⚠️ 量測方法：`_direction_a_violations()`，與逐檔規則同一把尺（不要換尺再比大小）。
DIRECTION_A_RATCHET = 4

# ⚠️ **不只記「幾處」，還要記「是哪幾處」**（2026-08-28 稽核 X-4b 否證後補）：
# 只斷言數量時，「還一筆再借一筆」的**淨零置換**永遠不紅 —— 實測：正確修掉
# checkup.py 那處、同時在 tab_manage.py 新增一處全新灰字（總數仍 4）→ 1 passed。
# 鍵刻意用 `路徑::函式()` 而不是行號：行號每次重構都漂，函式名不會。
DIRECTION_A_SITES = frozenset({
    "ui/helpers/fund/checkup.py::render_fund_checkup()",
    "ui/helpers/portfolio/fee_deduction.py::render_fee_deduction_section()",
    "ui/helpers/portfolio/load.py::batch_load_unloaded_funds()",
    "ui/sidebar.py::render_sidebar()",
})


def test_a_caught_exception_backlog_only_shrinks():
    """範圍外的方向 A 殘留是 ratchet：可以慢慢還，不可以再借。

    ⚠️ 這條擋的是「**新增**一個把例外印成灰字的地方」；它擋不住
    「把既有的一處刪掉不印」（那屬 §1 Fail Loud 的守備範圍，本檔開頭已宣告邊界）。
    """
    found = [v for p in UI_SOURCES for v in _direction_a_violations(p)]
    total = len(found)
    assert total <= DIRECTION_A_RATCHET, (
        f"把捕捉到的例外印成非紅燈的地方從 {DIRECTION_A_RATCHET} 增為 {total} —— "
        "新的失敗請走 ui.helpers.render_state.system_error()。\n  "
        + "\n  ".join(found)
    )
    # ⚠️ **下限也要守**（2026-08-28 稽核 X-4b 否證後補）：
    # 原本只有 `<=`，於是「還一筆再借一筆」的**淨零置換**永遠不紅 ——
    # 實測：正確修掉 checkup.py 那處、同時在另一檔新增一處全新灰字（總數仍 4）→ 1 passed。
    # 而且真的把那 4 處清完之後，**沒有任何機制把 4 降下來**，等於留了 4 格永久額度。
    # 改成 `==` 之後：修好一處 → 本條轉紅 → 逼你把常數一起降。**紅燈在這裡是提醒不是責備。**
    sites = {k for p in UI_SOURCES for k in _direction_a_site_keys(p)}
    assert sites == DIRECTION_A_SITES, (
        "方向 A 的殘留**站點**變了（不只是數量）—— 這條擋的是「還一筆再借一筆」的淨零置換。\n"
        f"  只在現況有（新借的）：{sorted(sites - DIRECTION_A_SITES) or '無'}\n"
        f"  只在清單有（已還掉的）：{sorted(DIRECTION_A_SITES - sites) or '無'}\n"
        "還掉了就把 `DIRECTION_A_SITES` 與 `DIRECTION_A_RATCHET` 一起更新；"
        "新借的請改走 system_error()。"
    )
    assert total == DIRECTION_A_RATCHET, (
        f"方向 A 殘留剩 {total} 處，但 `DIRECTION_A_RATCHET` 還寫著 "
        f"{DIRECTION_A_RATCHET} —— 修好了就把常數一起降下來（這條紅燈是提醒不是責備）。\n"
        f"⚠️ 若你是**修好了**而看到這條：把常數改成 {total}。\n"
        f"⚠️ 若你是**把某處的告知整段刪掉**（靜默吞掉）才讓數字變小：那不算修好，\n"
        f"   請改走 system_error()（§1 Fail Loud —— 本檔規則抓不到「不印」，只抓「印錯顏色」）。\n"
        f"目前殘留：\n  " + "\n  ".join(found)
    )


def test_a_declared_batch_scope_still_exists():
    """`BATCH2A_SCOPE_A` 寫死了路徑 —— 檔案改名要出聲。

    不加這條，改個檔名就會讓上面的 parametrize case **無聲消失**（0 個 case 也算
    通過），而 ratchet 只擋得住「數字變大」，擋不住「規則整條蒸發」。
    （同 `test_c_declared_paths_still_exist` 的理由，換一組路徑。）
    """
    missing = sorted(str(p.relative_to(ROOT)) for p in BATCH2A_SCOPE_A if not p.is_file())
    assert not missing, f"下列路徑已不存在，本批的方向 A 規則正在對空氣生效：{missing}"
    # ⚠️ **清單長度也要守**（2026-08-28 稽核 A3 補）：上一版只檢查「列出來的路徑存在」，
    # 不檢查清單有沒有變短 —— 於是「刪掉一行 + 在該檔加 degraded=True」是**兩步繞過 N3**
    # 的完整路徑（方向 A 那邊有 ratchet 兜底，N3 這邊沒有）。
    # 用 `>=` 而不是 `==`：後續批次把更多檔清乾淨時應該**加**進來，那不該被擋。
    assert len(BATCH2A_SCOPE_A) >= 14, (
        f"`BATCH2A_SCOPE_A` 從 14 個檔縮成 {len(BATCH2A_SCOPE_A)} 個 —— "
        "本批清乾淨的檔不得從 scope 移走（移走 = 規則 1 與 N3 在那個檔上一起失效）。"
    )


# ══════════════════════════════════════════════════════════════════
# 塊 1：同一個失敗，不准兩種顏色
#
# 這是本批存在的理由。批次一只做了組合健診，於是有三組「文案逐字相同 /
# 同一個 render 函式 / 同一個 repository 呼叫」的失敗，在 A 分頁是 🔴、
# 在 B 分頁是灰字 —— 顏色帶的資訊變成「你在哪個分頁」而不是「這件事嚴不嚴重」。
#
# ⚠️ 守的是**兩邊都要是紅燈入口**，不是文案 —— 文案會被改寫，顏色語意不會。
# ⚠️ 這條同時是上面兩條的**反向護欄**：規則 1 可以靠「把整段刪掉不印」通過，
#    本條要求那個呼叫**必須存在**，刪掉就紅。
# ══════════════════════════════════════════════════════════════════
# (說明, [(檔案, 函式, 錨點呼叫, 必須出現的紅燈入口)…])
#
# ⚠️ **錨點為什麼是「函式 + 那個呼叫」，而不是「整個檔案」**（2026-08-28 稽核 Z 組否證後重寫）：
# 上一版三組 pair 各有一邊寫 `fn_name=None` ＝ 掃全檔，而那些檔案各自另有
# 3 / 12 / 5 個**不相干的** `system_error()` —— 於是本規則被那些不相干的呼叫
# **自證合格**。稽核組實測（跑全套，不只跑本條）：
#     Z-1  backtest_section 的 USDTWD 失敗整段改 `pass` → 370 passed（全綠）
#     Z-2  switch_advisor 的 list_pool 失敗整段改 `pass` → 370 passed（全綠）
#     Z-3  tab_batch_analysis 兩處都改 `pass`            → 1 failed（只有這組抓到）
# 也就是說：本條 docstring 原本寫的「刪掉就紅」，**對 6 個 side 有 3 個不成立**。
# 這是「掃整個範圍 → 被不相干的東西自證合格」在本 repo 的**第 6 次復發**，
# 而且復發在本批的旗艦新規則上，還附帶一句寫進檔案的錯誤強度宣稱。
#
# 現在的錨點：**找出「在 <函式> 裡、body 詞法上呼叫 <錨點> 的那個 try」，
# 要求它的 handler 走 <紅燈入口>**。不相干的 `system_error` 再多也自證不了，
# 因為它們不在那個 try 的 handler 裡。
# ⚠️ `tab_batch_analysis._render_existing_results` 自己就有 2 個 `system_error`，
#    所以「收窄到函式」還不夠 —— 錨點呼叫（`render_switch_section` /
#    `render_regime_fit_section`）才是把兩者分開的那一維。
_TWIN_FAILURES = [
    ("USDTWD 匯率抓不到 → 美元計價基金被排除（兩邊逐字同一句、後果相同）", [
        ("ui/helpers/fund_grp_health/backtest_section.py",
         "render_allocation_backtest_section", "fetch_usdtwd_frame", "system_error"),
        ("ui/helpers/portfolio_perf.py",
         "render_portfolio_performance", "fetch_usdtwd_frame", "system_error"),
    ]),
    ("換標決策區塊失敗（兩邊呼叫的是同一個 render_switch_section）", [
        ("ui/tab_fund_grp_health.py",
         "_render_health_table", "render_switch_section", "system_error"),
        ("ui/tab_batch_analysis.py",
         "_render_existing_results", "render_switch_section", "system_error"),
    ]),
    ("景氣適配區塊失敗（兩邊呼叫的是同一個 render_regime_fit_section）", [
        ("ui/tab_fund_grp_health.py",
         "_render_health_table", "render_regime_fit_section", "system_error"),
        ("ui/tab_batch_analysis.py",
         "_render_existing_results", "render_regime_fit_section", "system_error"),
    ]),
    ("選股池讀取失敗（後果：tab_manage 會靜靜漏掉整個選股池）", [
        # ⚠️ 這一檔有**兩個** list_pool 的 try：`_render_pool_editor`（訊息「選股池讀取失敗」，
        #    ＝ tab_manage 那處的真正雙生）與 `render_switch_advisor_section`（訊息
        #    「換股建議產生失敗」，是**另一個**失敗）。錨到後者會讓 Z-2 突變照樣全綠 ——
        #    本輪自己用稽核組的 Z-2 回打時抓到並更正。
        ("ui/helpers/fund_grp_health/switch_advisor_section.py",
         "_render_pool_editor", "list_pool", "system_error"),
        ("ui/tab_manage.py",
         "_sec_nav_backfill_auto", "list_pool", "system_error"),
    ]),
]


def _anchored_handler_reporters(rel: str, fn_name: str, anchor: str) -> list[list[str]] | None:
    """在 `rel::fn_name()` 裡，body 詞法上呼叫 `anchor` 的每一個 try，其 handler 用了哪些入口。

    回 None ＝ 連那個 try 都找不到（函式改名 / 呼叫搬走 / try 被拆掉）——
    那也要紅，否則規則會對空氣生效。
    """
    tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == fn_name),
              None)
    if fn is None:
        return None
    out: list[list[str]] = []
    for node in ast.walk(fn):
        if not isinstance(node, ast.Try):
            continue
        body_calls = {(c.func.attr if isinstance(c.func, ast.Attribute)
                       else getattr(c.func, "id", ""))
                      for b in node.body for c in ast.walk(b) if isinstance(c, ast.Call)}
        if anchor not in body_calls:
            continue
        out.append([_callee(c) for h in node.handlers for c in ast.walk(h)
                    if isinstance(c, ast.Call)])
    return out or None


@pytest.mark.parametrize("label,sides", _TWIN_FAILURES,
                         ids=lambda x: x if isinstance(x, str) else "")
def test_twin_failures_wear_the_same_colour(label, sides):
    """同一個失敗在不同分頁必須是同一個顏色入口。

    ⚠️ **本條的強度，據實寫（不要再寫成「刪掉就紅」那種全稱保證）**：
    守得到 —— 把**被錨定的那個 try** 的 handler 改成灰字、改成別的 widget、
    或整段改 `pass`（handler 內沒有任何 `system_error` 呼叫）→ 紅；
    把錨點函式改名、把錨點呼叫搬出那個 try → 紅（`_anchored_handler_reporters` 回 None）。
    **守不到** —— handler 裡呼叫一個**自己另外定義的 wrapper**，而那個 wrapper 內部
    才呼叫 `system_error`（跨函式呼叫圖，本檔一律不做）；以及把整個 try/except 連同
    錨點呼叫一起刪掉改走別的實作（那不是「顏色錯」，是功能被移除，屬 §1 的守備範圍）。
    """
    missing = []
    for rel, fn_name, anchor, entry in sides:
        got = _anchored_handler_reporters(rel, fn_name, anchor)
        if got is None:
            missing.append(f"{rel}::{fn_name}() 裡找不到「body 呼叫 {anchor}(...)」的 try "
                           f"—— 函式改名？呼叫搬走？try 拆掉？")
            continue
        for i, reporters in enumerate(got):
            if entry not in reporters:
                missing.append(f"{rel}::{fn_name}() 包住 {anchor}(...) 的第 {i + 1} 個 try，"
                               f"其 handler 沒有走 {entry}(...)（實際用了：{reporters or '什麼都沒有'}）")
    assert not missing, (
        f"「{label}」在不同分頁的顏色又分岔了 —— 同一個失敗兩種顏色，"
        "顏色帶的資訊就變成「你在哪個分頁」而不是「這件事嚴不嚴重」：\n  "
        + "\n  ".join(missing)
    )


# ══════════════════════════════════════════════════════════════════
# 三個入口自己畫出來的 widget 種類 —— 上面的 AST 規則靠這幾條才不會被
# 「把 system_error 內容偷偷換成 st.caption」繞過。
# ══════════════════════════════════════════════════════════════════
class _FakeST:
    """記錄被呼叫的 widget 名稱（不驗文案）。"""

    def __init__(self, expander_raises: bool = False):
        self.calls: list[str] = []
        self._expander_raises = expander_raises

    def __getattr__(self, name):
        def _rec(*a, **k):
            self.calls.append(name)
        return _rec

    def expander(self, *a, **k):
        if self._expander_raises:
            # Streamlit 真的會這樣炸：Expanders may not be nested inside other expanders
            raise RuntimeError("Expanders may not be nested inside other expanders")
        import contextlib
        self.calls.append("expander")
        return contextlib.nullcontext()


def _run(fn, *, expander_raises=False, **kw):
    """在假的 streamlit 下跑 fn，回傳它畫了哪些 widget。"""
    import sys

    import ui.helpers.render_state as rs
    fake = _FakeST(expander_raises=expander_raises)
    orig_rs, orig_mod = rs.st, sys.modules["streamlit"]
    rs.st = fake
    sys.modules["streamlit"] = fake          # friendly_error 是函式內 lazy import
    try:
        fn(**kw)
    finally:
        rs.st = orig_rs
        sys.modules["streamlit"] = orig_mod
    return fake.calls


def test_not_ready_is_grey_and_cannot_carry_an_exception():
    from ui.helpers.render_state import not_ready
    calls = _run(not_ready, message="還沒載入", where="🌐 市場定調")
    assert calls == ["caption"], calls
    # 型別層防呆：「還沒載入」不可能有 exception 可報。
    with pytest.raises(TypeError):
        not_ready(RuntimeError("boom"))          # type: ignore[arg-type]


def test_system_error_is_a_red_box_with_technical_detail():
    from ui.helpers.render_state import system_error
    calls = _run(system_error, what="X 渲染失敗", exc=ValueError("boom"))
    assert "error" in calls, calls                  # 🔴 紅色錯誤框
    assert "code" in calls, calls                   # 技術細節（traceback）
    assert "caption" not in calls, calls            # 不得退化成灰字


def test_system_error_survives_a_nested_expander():
    """區塊隔離用的錯誤呈現，本身不可以炸掉整頁。

    這些 handler 有一部分住在 `st.expander` 裡（逐檔展開區）；Streamlit 禁止巢狀
    expander，硬開會把「一個區塊失敗」升級成整頁 StreamlitAPIException。
    """
    from ui.helpers.render_state import system_error
    calls = _run(system_error, expander_raises=True,
                 what="X 渲染失敗", exc=ValueError("boom"))
    assert "error" in calls and "code" in calls, calls


def test_business_alert_is_not_an_error_box():
    """業務紅燈：分析成功了，答案很難看 —— 那是成果，不是故障。"""
    from ui.helpers.render_state import business_alert
    calls = _run(business_alert, title="🔴 淘汰候選 2 檔", lines=["- A", "- B"])
    assert "error" not in calls, calls
    assert "markdown" in calls, calls


# ══════════════════════════════════════════════════════════════════
# 方向 B：「還沒設定 / 還沒載入」不得畫成警示色
#
# 兩條規則刻意用**兩種不同的抓法**，因為任一條單獨都有死角：
#   B1 結構：`if not <某個金鑰變數>:` 這個分支裡不准出現警示色 widget。
#            —— 抓得到「條件對、顏色錯」，抓不到把條件寫成別的形狀的。
#   B2 語彙：警示色 widget 的字面訊息不得帶「還沒設定」這組詞。
#            —— 抓得到條件寫成任何形狀的，抓不到把文案整組換掉的。
# 兩條一起，要繞過必須同時改掉條件寫法**和**文案。
#
# ⚠️ **2026-08-28 第二輪稽核 A1：上一版在這裡寫「那已經不是回歸，是改設計」——
#    那句風險評估不成立，實測改兩行就繞得過**：條件寫成
#    `if not st.secrets.get("FRED_API_KEY"):`（B1 只認 `if not <名字>`，
#    這是 Call 不是 Name）＋ 文案換成不帶語彙的中性句（B2 只認語彙家族）。
#    事實部分（兩條各自的抓法互補）成立；**「繞不過去」那半是我自己加上去的、
#    沒有驗證的話**。依 §-2 規則 6 就地改為誠實揭露：
#    **B1／B2 提高了繞過的成本，但擋不住刻意繞過的人。**
#    已知缺口（沒修，據實登記）：
#      - 條件不是裸名字（`st.secrets.get(...)` / `os.environ.get(...)` / `cfg.key`）；
#      - 文案完全避開語彙家族（「請先完成設定」之類）。
#    要補的話是第三條規則（追蹤憑證值的資料流），不在「只做顏色」這一批的範圍內。
#
# ⚠️⚠️ **2026-08-28 第三輪稽核 P8：上一句「兩行就能繞過」說輕了，此處更正。**
#    我當時的隱含假設是「就算 B1／B2 被繞過，還有 ratchet 當後手」。**那不成立** ——
#    稽核組實測一個**完全自然的命名**就三條全繞：
#        `_setup_err = "請先完成資料源設定後再回到本頁。"` 然後 `st.error(_setup_err)`
#    → B1 不叫（條件不是裸名字）、B2 不叫（文案無語彙）、
#      **ratchet 也不叫**（變數名帶 `err` token ⇒ `_has_failure_evidence` 認為有失敗證據）。
#    **ratchet 不是這條規則的後手保險** —— 它用的是同一個「有沒有失敗證據」判準，
#    而那個判準恰好會被 `err` 這個常見字根餵飽。**三條是同源的，不是三層。**
# ══════════════════════════════════════════════════════════════════
ALARM_WIDGETS = {"error", "warning"}

# 「這是一個憑證 / 資料源設定」的變數命名家族（本 repo 實際用法）。
_CREDENTIAL_HINTS = ("_KEY", "KEY", "_TOKEN", "TOKEN", "SECRET", "CREDENTIAL")

# 「還沒設定」的語彙家族。放在測試裡而不是散在各檔，是為了讓它有一個可以被讀、
# 被增修的地方；新增一種說法時把它加進來，而不是去改十幾個 assert。
NOT_CONFIGURED_PHRASES = ("未設定", "未設置", "需設置", "尚未設定", "缺少必要金鑰",
                          "請在 Streamlit Cloud Secrets 填入")

UI_SOURCES = sorted((ROOT / "ui").rglob("*.py")) + [ROOT / "app.py"]


def _is_credential_name(name: str) -> bool:
    up = name.upper()
    return any(h in up for h in _CREDENTIAL_HINTS)


def _literal_text(call: ast.Call) -> str:
    """把呼叫參數裡所有字串常數串起來（f-string 的常數段也算）。"""
    out = []
    for sub in ast.walk(call):
        if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
            out.append(sub.value)
    return "".join(out)


@pytest.mark.parametrize("path", UI_SOURCES, ids=lambda p: str(p.name))
def test_b1_missing_credential_branch_is_never_alarm_coloured(path: pathlib.Path):
    """`if not FRED_KEY:` / `if not GEMINI_KEY:` 這種分支 → 一律灰色說明。

    金鑰沒填是「你還沒設定」，不是「系統壞了」。畫成紅／橘會把真紅燈的份量稀釋掉
    （線框 §03：同一個條件，全站曾經有五種畫法）。
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    containers = _st_container_names(tree)
    bad = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        if not (isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not)):
            continue
        names = [n for n in _names_in(test) if _is_credential_name(n)]
        if not names:
            continue
        for stmt in node.body:                      # 只看這個分支自己，不看巢狀 else
            for call in _st_calls_named(stmt, ALARM_WIDGETS, containers):
                bad.append(f"{path.relative_to(ROOT)}:{call.lineno} "
                           f"if not {names[0]}: → st.{call.func.attr}")
    assert not bad, (
        "「金鑰／憑證沒設定」被畫成警示色；請改走 "
        "ui.helpers.render_state.not_ready()：\n  " + "\n  ".join(bad)
    )


@pytest.mark.parametrize("path", UI_SOURCES, ids=lambda p: str(p.name))
def test_b2_not_configured_wording_is_never_alarm_coloured(path: pathlib.Path):
    """換個條件寫法就繞過 B1 —— 這一條從訊息本身抓。"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    bad = []
    for call in _st_calls_named(tree, ALARM_WIDGETS, _st_container_names(tree)):
        text = _literal_text(call)
        hit = [p for p in NOT_CONFIGURED_PHRASES if p in text]
        if hit:
            bad.append(f"{path.relative_to(ROOT)}:{call.lineno} "
                       f"st.{call.func.attr}(…{hit[0]}…)")
    assert not bad, (
        "「還沒設定」被畫成警示色；請改走 ui.helpers.render_state.not_ready()：\n  "
        + "\n  ".join(bad)
    )


def _st_calls_named(node: ast.AST, attrs: set[str],
                    containers: frozenset[str] = frozenset()):
    """node 底下所有 `st.<attr>(...)`，含 `st.sidebar.<attr>` 與 `col1.<attr>`。

    ⚠️ 見 `_callee` 的說明：只認裸 `st.` 會讓 `st.sidebar.*` 對全檔每一條規則隱形；
    只剝 Attribute 會讓 `_cols[2].*` 隱形；不認容器名會讓 `col1.*` 隱形。
    三者是同一個病的三種形狀，分別由第三輪（sidebar）與本批（下標 / 容器）補上。
    """
    for sub in ast.walk(node):
        if not (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)
                and sub.func.attr in attrs):
            continue
        _root = _receiver_root(sub.func.value)
        if _root == "st" or (_root is not None and _root in containers):
            yield sub


# ══════════════════════════════════════════════════════════════════
# 方向 C：業務紅燈 vs 系統紅燈
#
# 線框 §03 最重要的一條：
#   系統紅燈 = 「這個數字**不可信**」；業務紅燈 = 「這個數字**可信**，而且它很難看」。
#   兩者要使用者做的事完全相反 —— 前者要他別採信、去修；後者要他採信、去行動。
#   用同一個紅色，等於把「不要相信這個畫面」和「相信這個畫面並據以行動」畫成同一件事。
#
# 這裡守的形狀：`st.error`（＝系統紅框）**只給「這次執行出了問題」用**。
# 判準是**這個呼叫拿不拿得到失敗證據**，不是它的文案：
#   - 手上有 exception，或
#   - 訊息是從某個 error / 失敗欄位組出來的（`…["error"]`、`_err`、`load_error` …）
# 兩者皆無 → 它畫的是一個「分析成功之後的結論」或一則常駐警語，不該用系統紅框。
# ══════════════════════════════════════════════════════════════════
# ⚠️ 這是一個**完整詞**集合，不是子字串樣板 —— 比對方式見 `_has_failure_evidence`。
_FAILURE_EVIDENCE = frozenset({
    "error", "errors", "err", "errs",
    "fail", "failed", "failure", "failures",
    "exc", "exception", "exceptions",
    "traceback", "tb",
})

# 識別字/文案切詞：只取 ASCII 英數字段。`_gs_error` → {gs, error}；
# `_excluded` → {excluded}；「（Excel 匯出同理）」→ {excel}；中文整段是分隔符。
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _has_failure_evidence(call: ast.Call) -> bool:
    """這個呼叫手上有沒有「失敗的證據」？

    ⚠️ **兩個踩過的坑，都寫在這裡，因為它們都會讓這條規則安靜地失效。**

    坑 1（第一版）：掃了整個 call node —— 而 `st.error` 的 attr 本身就是 `"error"`，
    每一個 `st.error` 都自證有證據，規則當場失效、突變測試不會紅。
    → 改為只掃**參數**（`call.args` / `call.keywords`），不碰 `call.func`。

    坑 2（第二版，稽核組 2026-08-28 抓到）：比對方式是**裸子字串** `k in blob`，
    而 `_FAILURE_EVIDENCE` 裡有 `exc` / `err` / `fail` 這種短字根。實測後果：
      - 業務結論回退成 `st.error`，變數叫 `_excluded` → `"exc"` 命中 → **被豁免**
      - 常駐警語回退成 `st.error`，文案加「（Excel 匯出同理）」→ `"exc"` 命中 → **被豁免**
    也就是「ratchet 只准往下走」這句承重宣稱，對任何含 `exc`/`err`/`fail` 子字串的
    訊息或變數名**都不成立**，新的業務紅框可以無聲加進來。
    → 改為**完整詞**比對：把識別字與文案切成 ASCII 英數 token，再跟集合取交集。
    """
    tokens: set[str] = set()
    for arg in [*call.args, *(k.value for k in call.keywords)]:
        for sub in ast.walk(arg):
            if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                tokens |= set(_TOKEN_RE.findall(sub.value.lower()))
            elif isinstance(sub, ast.Name):
                tokens |= set(_TOKEN_RE.findall(sub.id.lower()))
            elif isinstance(sub, ast.Attribute):
                tokens |= set(_TOKEN_RE.findall(sub.attr.lower()))
    return bool(tokens & _FAILURE_EVIDENCE)


# 錯誤呈現的實作本身（它們就是那個紅框），不在受檢範圍內。
# ⚠️ 一律寫**相對路徑**不寫 basename：basename 相同的檔案在別的目錄下會被誤放行，
#    而改名會讓 parametrize case 無聲消失（下方 `test_c_declared_paths_still_exist` 擋這一半）。
_RED_BOX_IMPLEMENTATIONS = {"ui/helpers/session.py", "ui/helpers/render_state.py"}

# 本批（客戶拍板的第一批）實際轉換的兩處業務／常駐紅框所在檔案。
BATCH_SCOPE_C = {"ui/tab_fund_grp_health.py", "ui/tab6_manual.py"}


def _rel(path: pathlib.Path) -> str:
    return path.relative_to(ROOT).as_posix()

# 範圍外、**已登記待後批處理**的既有 bare `st.error`。
# ⚠️ 2026-08-28 稽核 A7：**三把不同的尺，不要互相加減**。實測 origin/main：
#   `ui/**` 不含 `app.py` ＝ 25／含 `app.py` ＝ 26／
#   **本規則自己的尺**（`UI_SOURCES` 再扣掉 `BATCH_SCOPE_C` 與 `_RED_BOX_IMPLEMENTATIONS`）＝ 23。
# 本批轉掉 4 處 → **本規則的尺由 23 降為 21**。（「25 − 4 = 21」是巧合，別再那樣寫。）
# ⚠️ 這不是豁免清單，是**待辦的可見化**：它是一個 ratchet，數字只准往下走。
# 多數是表單驗證與中文失敗訊息（「投入總額必須大於 0」「讀回失敗」），
# 判定要逐條看業務語意，不在「只做顏色」這一批的範圍內（§8.4 step 4：不自作主張擴大範圍）。
# ⭐ **2026-08-28 第三輪稽核：21 → 22，這是「修正量測誤差」，不是「放寬門檻」。**
# 兩者的差別必須寫清楚，否則後人會以為 ratchet 被偷偷調鬆過：
#   - 21 是 **receiver 判定放寬前**的量測值。當時規則只認**裸** `st.` receiver，
#     `st.sidebar.error(...)` 對每一條規則都是隱形的 → **量測值偏低**。
#   - 放寬後（`_callee` / `_st_calls_named` 改吃 st 屬性鏈）浮出 **2 個既有站點**，皆在 `ui/sidebar.py`：
#       `st.sidebar.error("Proxy 未設定")`   → **本批已修**（改走 `not_ready` 並補「去哪裡設」）
#       `st.sidebar.error("❌ 407：帳密錯誤")` → **真失敗，紅得對**；只是訊息是中文、
#         C1 的英文字根抓不到「證據」而被歸為 bare（與其餘 21 處同一個成因）。
#   - 淨值：23（浮出後）− 1（修掉 Proxy 那處）= **22**。差額 22 − 21 = +1，
#     **是原本隱形的既有站點，不是有人新借了額度。**
# ⛔ 不得為了讓 CI 綠而把新浮出的站點加進豁免清單、或把 receiver 判定改回去。
BARE_ERROR_RATCHET = 22


def _bare_error_calls(path: pathlib.Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    containers = _st_container_names(tree)
    inside_except = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            inside_except.update(id(c) for c in _st_calls_named(node, {"error"}, containers))
    return [c for c in _st_calls_named(tree, {"error"}, containers)
            if id(c) not in inside_except and not _has_failure_evidence(c)]


@pytest.mark.parametrize("path", sorted(p for p in UI_SOURCES if _rel(p) in BATCH_SCOPE_C),
                         ids=lambda p: str(p.name))
def test_c_system_red_box_is_reserved_for_actual_failures(path: pathlib.Path):
    """`st.error` 不得拿來畫「業務結論」或「常駐警語」。

    抓法刻意不看文案：只看這個呼叫**手上有沒有失敗證據**。
    「🔴 淘汰候選 N 檔」拿不到任何 exception / error 欄位 —— 因為分析成功了，
    它報的是成果；那就不該長得跟系統崩潰一樣。
    """
    bare = _bare_error_calls(path)
    assert not bare, (
        f"{path.relative_to(ROOT)}：st.error 拿不到任何失敗證據 —— "
        "業務結論／常駐警語不可與系統崩潰共用紅框。"
        "業務警訊走 render_state.business_alert()，常駐提醒走 st.warning()。\n  "
        + "\n  ".join(f"line {c.lineno}" for c in bare)
    )


def test_c_bare_error_backlog_only_shrinks():
    """範圍外的既有 bare `st.error` 是 ratchet：可以慢慢還，不可以再借。

    本批只做顏色，逐條判定那 22 處的業務語意不在範圍內（§8.4 step 4）；
    但新寫的 code 不准再往這個數字上加。

    ⚠️ **22 是「本規則自己這把尺」量出來的**（`UI_SOURCES` 再扣掉 `BATCH_SCOPE_C`
    與 `_RED_BOX_IMPLEMENTATIONS`）。換一把尺就是別的數字：`ui/**` 不含 `app.py` ＝ 25、
    含 `app.py` ＝ 26。**不要拿不同 scope 的數字互相加減。**
    數字沿革（21 → 22 是**修正量測誤差**，不是放寬門檻）見 `BARE_ERROR_RATCHET` 上方註解。
    """
    total = sum(len(_bare_error_calls(p)) for p in UI_SOURCES
                if _rel(p) not in BATCH_SCOPE_C | _RED_BOX_IMPLEMENTATIONS)
    assert total <= BARE_ERROR_RATCHET, (
        f"拿不到失敗證據的 st.error 從 {BARE_ERROR_RATCHET} 增為 {total} —— "
        "新的業務結論／常駐警語請走 business_alert() / st.warning()，不要再加進紅框。"
    )


def test_c_declared_paths_still_exist():
    """`BATCH_SCOPE_C` / `_RED_BOX_IMPLEMENTATIONS` 寫死了路徑 —— 檔案改名要出聲。

    不加這條的話，改個檔名就會讓上面的 parametrize case **無聲消失**（0 個 case
    也算通過），而 ratchet 只擋得住「數字變大」，擋不住「規則整條蒸發」。
    """
    missing = sorted(r for r in BATCH_SCOPE_C | _RED_BOX_IMPLEMENTATIONS
                     if not (ROOT / r).is_file())
    assert not missing, (
        f"下列路徑已不存在，本檔的 C 規則正在對空氣生效：{missing}"
    )


def test_c_business_verdict_uses_the_business_entrypoint():
    """反向護欄：上一條可以靠「整塊刪掉」通過，這一條擋掉那條逃生路。

    ⚠️ 用 **AST 找真正的呼叫**，不是 `"business_alert(" in src`。
    稽核組 2026-08-28 實測過那個字串版的破法：把方向 C 完整回退成 `st.error`、
    只留一行註解 `# TODO: 改回 business_alert(` —— 三條 C 規則同時失效、全綠。
    """
    tree = ast.parse((ROOT / "ui" / "tab_fund_grp_health.py").read_text(encoding="utf-8"))
    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call)
             and ((isinstance(n.func, ast.Name) and n.func.id == "business_alert")
                  or (isinstance(n.func, ast.Attribute) and n.func.attr == "business_alert"))]
    assert calls, (
        "健診頁的「淘汰候選」業務警訊不見了 —— 它是分析的主要成果，"
        "改顏色不等於可以拿掉（§1）。（註解裡寫 business_alert 不算數：本條看 AST。）"
    )


# ══════════════════════════════════════════════════════════════════
# 逐檔迴圈裡的紅燈 —— 修「示警不足」不可以修出「示警過度」
#
# 2026-08-28 稽核 M1：選股池補抓失敗原本是**就地**畫紅燈，而它住在
# `_pool_rows` 的逐檔迴圈裡。選股池 20 檔，遇 proxy 掛掉或 MoneyDJ 子網域 403
# （依 `CLAUDE.md §1` Fund 脈絡屬**例行**狀況）→ 一次 20 個滿版紅框，
# 每個底下各掛一塊技術細節。那正是線框 §03 要防的
# 「滿版警示讓真錯誤沒人看見」，只是換成紅色、更嚴重。
# ══════════════════════════════════════════════════════════════════
def test_m1_per_item_fetch_helper_renders_nothing_itself():
    """`_fetch_rich` 在迴圈裡被逐檔呼叫 → 它自己不准畫任何東西。

    守的是**位置**不是文案：只要這個函式體內出現任何渲染呼叫，
    N 檔失敗就會變成 N 個框。
    """
    src = (ROOT / "ui" / "helpers" / "fund_grp_health" / "switch_advisor_section.py")
    tree = ast.parse(src.read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "_fetch_rich")
    rendered = [f"line {c.lineno}: {_callee(c)}" for c in _rendering_calls(fn)]
    assert not rendered, (
        "`_fetch_rich` 住在 `_pool_rows` 的逐檔迴圈裡，就地渲染會讓 N 檔失敗噴 N 個框；"
        "請把失敗收進 `failures` 由呼叫端彙總成一則：\n  " + "\n  ".join(rendered)
    )


def test_m1_the_per_item_loop_itself_renders_nothing():
    """守的是**渲染位置**，不只是「哪個函式不准畫」。

    ⚠️ 2026-08-28 第二輪稽核 N5：上一版只守 `_fetch_rich` 的函式體。稽核組實測，
    把逐檔渲染**搬進 `_pool_rows` 的迴圈裡**、改用 `system_error()` ——
    「20 檔 = 20 個滿版紅框」的原病完整復發，三條 M1 測試**全綠**。
    （改用 `st.error` 會被 ratchet 攔到，但那是後手，不是 M1 在守。）

    現在的判準：**迴圈體內「詞法上直接寫出」`_fetch_rich(...)` 的那些迴圈，
    其迴圈體內不得出現渲染呼叫。** 收集在迴圈內、上報在迴圈外，是唯一正確的形狀。

    ⚠️ **只擋詞法直呼，一層 indirection 就繞得過**（2026-08-28 第三輪稽核 P4 實測）：
    把渲染抽成 `_note_one_failure(code)` helper、迴圈裡改呼叫它 → 本條全綠。
    上一版 docstring 寫「**任何**呼叫 `_fetch_rich` 的迴圈」，讀起來像完整保證 ——
    **它不是**。要真的擋住需要跨函式呼叫圖分析，不在「只做顏色」這一批的範圍內，
    已登記第二批。
    """
    src = ROOT / "ui" / "helpers" / "fund_grp_health" / "switch_advisor_section.py"
    tree = ast.parse(src.read_text(encoding="utf-8"))
    bad = []
    for loop in ast.walk(tree):
        if not isinstance(loop, (ast.For, ast.While)):
            continue
        calls_fetch = any(isinstance(c, ast.Call) and _callee(c) == "_fetch_rich"
                          for c in ast.walk(loop))
        if not calls_fetch:
            continue
        for c in _rendering_calls(loop):
            bad.append(f"{src.relative_to(ROOT)}:{c.lineno} {_callee(c)}()"
                       f"（在 line {loop.lineno} 的逐檔迴圈內）")
    assert not bad, (
        "逐檔迴圈內出現渲染呼叫 —— N 檔失敗就是 N 個框，正是線框 §03 要防的"
        "「滿版警示讓真錯誤沒人看見」；請收集到迴圈外再彙總成一則：\n  "
        + "\n  ".join(bad)
    )


def test_m1_pool_fetch_failures_are_reported_as_exactly_one_red_box(monkeypatch):
    """N 檔失敗 → **一則**系統紅燈，而且要把 N 個代號都講出來。"""
    from ui.helpers.fund_grp_health import switch_advisor_section as sas

    calls: list[tuple] = []
    monkeypatch.setattr(sas, "system_error",
                        lambda what, exc, **kw: calls.append((what, exc, kw)))
    sas._report_pool_fetch_failures(
        [("AAA", RuntimeError("boom")), ("BBB", RuntimeError("boom")),
         ("CCC", RuntimeError("boom"))])

    assert len(calls) == 1, f"應彙總成一則，實際 {len(calls)} 則"
    what = calls[0][0]
    for code in ("AAA", "BBB", "CCC"):
        assert code in what, f"彙總訊息漏掉 {code}：{what!r}"


def test_n1_ok_false_is_collected_not_silently_dropped(monkeypatch):
    """`process_one_fund` 回 `ok=False` 時，那一檔**不可以靜靜消失**。

    ⚠️ 2026-08-28 第二輪稽核 N1：上一輪的彙總機制只接 `except`，
    而 `services/fund_row.process_one_fund` **整段包在一個 try 裡、結尾一律
    `return {"ok": False, "error": ...}`（幾乎不 raise）** —— proxy 掛掉／403
    走的是 `fd["error"]` → `ok=False`。也就是說：我為一條**罕見**路徑蓋了彙總機制，
    而**主要**路徑（`ok=False` → `return None`）仍然整條靜默，`r["error"]` 被丟掉。
    這正是 `_report_pool_fetch_failures` 自己 docstring 寫的那個「示警不足」。
    """
    from ui.helpers.fund_grp_health import switch_advisor_section as sas

    monkeypatch.setattr(sas, "_pool_oauth_client", lambda: None)
    monkeypatch.setitem(
        __import__("sys").modules, "services.fund_row",
        type("M", (), {"process_one_fund":
                       staticmethod(lambda *a, **k: {"ok": False, "error": "NAV 抓不到"})})())

    failures: list = []
    assert sas._fetch_rich("AAA", "某基金", failures=failures) is None
    assert len(failures) == 1, "ok=False 沒有被收進 failures —— 該檔會靜靜消失"
    code, exc = failures[0]
    assert code == "AAA"
    assert "NAV 抓不到" in str(exc), f"上游的 error 訊息被丟掉了：{exc!r}"


def test_n1_failure_reasons_are_all_reported_not_just_the_first(monkeypatch):
    """N 檔失敗原因**各不相同**時，不可以只講第一個（§1：其餘等於被吞掉）。"""
    from ui.helpers.fund_grp_health import switch_advisor_section as sas
    calls: list[tuple] = []
    monkeypatch.setattr(sas, "system_error",
                        lambda what, exc, **kw: calls.append((what, exc, kw)))
    sas._report_pool_fetch_failures([("AAA", RuntimeError("NAV 抓不到")),
                                     ("BBB", RuntimeError("FX USDTWD 抓不到"))])
    assert len(calls) == 1
    blob = calls[0][0] + " " + str(calls[0][2].get("hint", ""))
    for reason in ("NAV 抓不到", "FX USDTWD 抓不到"):
        assert reason in blob, f"漏掉失敗原因 {reason!r}：{blob!r}"


def test_m1_no_failures_stays_silent(monkeypatch):
    """沒失敗就不要出聲（否則每次開頁都多一個框）。"""
    from ui.helpers.fund_grp_health import switch_advisor_section as sas
    calls: list = []
    monkeypatch.setattr(sas, "system_error", lambda *a, **k: calls.append(a))
    sas._report_pool_fetch_failures([])
    assert calls == []


def test_m3_degraded_is_orange_and_default_is_red():
    """M3：純圖失敗（數字全在且全對）→ 🟠；結論會變錯的失敗 → 🔴。

    兩者穿同一件衣服，等於把客戶 Q2 要建立的分辨力又抹平。
    """
    from ui.helpers.render_state import system_error
    assert "error" in _run(system_error, what="X", exc=ValueError("b"))
    assert "warning" in _run(system_error, what="X", exc=ValueError("b"), degraded=True)


# ══════════════════════════════════════════════════════════════════
# 同一句灰字不要印兩遍
#
# 2026-08-28 稽核 M2：`tab1_macro` 的「尚未設定 FRED 金鑰…」被兩個**平行**的
# `if`（同縮排，都會執行）各印一次。線框 §04① 要的是「把指錯對象的那句換掉」，
# 不是「再講一次」—— 同一句灰字印兩遍會把它變成雜訊。
# ══════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("path", UI_SOURCES, ids=lambda p: str(p.name))
def test_m2_same_grey_line_is_not_printed_twice_in_one_function(path: pathlib.Path):
    """同一個函式裡，不得有兩個 `not_ready()` 帶完全相同的訊息字面。

    守的是**重複**，不是文案內容：訊息想怎麼改都行，但不要同一句講兩遍。
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    dupes = []
    for fn in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
        seen: dict[str, int] = {}
        for call in ast.walk(fn):
            if not (isinstance(call, ast.Call) and _callee(call) == "not_ready"
                    and call.args):
                continue
            first = call.args[0]
            if not (isinstance(first, ast.Constant) and isinstance(first.value, str)):
                continue                       # f-string / 變數 → 不比（可能真的不同）
            if first.value in seen:
                dupes.append(f"{path.relative_to(ROOT)}:{seen[first.value]} 與 "
                             f":{call.lineno} 在 {fn.name}() 內印了同一句：{first.value!r}")
            else:
                seen[first.value] = call.lineno
    assert not dupes, "同一句灰色說明重複印出：\n  " + "\n  ".join(dupes)


_CHART_CALLS = {"plotly_chart", "pyplot", "line_chart", "bar_chart", "area_chart",
                "altair_chart", "map", "image"}

# 在「只畫圖」的 try 裡出現也無妨的裸函式呼叫：Python builtins ＋ 一個具名的純數值轉換。
_CHART_SAFE_BARE_CALLS = frozenset({
    "len", "list", "dict", "set", "tuple", "float", "int", "str", "bool",
    "min", "max", "sum", "abs", "round", "sorted", "enumerate", "zip", "range",
    "isinstance", "hasattr", "getattr", "any", "all", "reversed", "map", "filter",
    # 專案自己的純數值轉換（把值安全轉 float / None），不渲染、不產生新結論。
    # ⚠️ 要往這個集合加東西，先問：它會不會在畫面上產生一個「數字」？會就不准加。
    "_safe_num",
})


def _may_be_degraded(call: ast.Call) -> bool:
    """這個 `system_error(...)` 有沒有**可能**把 🔴 降成 🟠？

    ⚠️ **2026-08-28 稽核 N 組否證後改寫：上一版只認字面量 `True`，三種等效寫法全綠。**
    判定式原本是 `getattr(k.value, "value", False) is True`，而
    `render_state.system_error` 的實作是 `level="warning" if degraded else "error"`
    —— 只要 truthy 就降色。稽核組實測（對照組 `degraded=True` → 1 failed）：

        degraded=_dg（_dg = True）   → 32 passed  ← 綠，畫面真的變橘
        **{"degraded": True}         → 32 passed  ← 綠，畫面真的變橘
        degraded=1（truthy 非 bool）→ 32 passed  ← 綠，畫面真的變橘

    現在改成**保守方向**：只要「無法證明它不會降色」就算數 ——
      - 關鍵字 `degraded=<字面 falsy>`（`False` / `0` / `None` / `""`）→ 不算；
      - 關鍵字 `degraded=<其他任何東西>`（變數、呼叫、算式）→ **算**（證明不了）；
      - 出現 `**kwargs` 展開（`**{...}` 或 `**d`）→ **算**（裡面可能有 degraded）。
    方向是刻意的：本規則擋的是「不該降的降了」，寧可多攔一個要人寫清楚，
    也不要讓一個真的會降色的寫法從規則底下走過去。
    """
    for kw in call.keywords:
        if kw.arg is None:                     # `**something`
            return True
        if kw.arg != "degraded":
            continue
        v = kw.value
        if isinstance(v, ast.Constant) and not v.value:
            continue                           # 明確寫死 falsy → 不會降色
        return True
    return False


def _is_chart_only_try(node: ast.Try, containers: frozenset[str] = frozenset()) -> bool:
    """這個 `try:` 是不是「從頭到尾只在畫一張圖」？

    ⚠️ **2026-08-28 第二輪稽核 N4：上一版的判定是錯的，而且錯得會逼出錯誤的顏色。**
    上一版只看 `st.*` 呼叫 —— 於是這種 try 會被判成 chart-only：

        try:
            _rows = _build_ranking_table(nav, funds)   # 專案 helper，渲染數十個數字
            st.plotly_chart(_rows["fig"], ...)
        except Exception as e:
            system_error("排名表 + 疊圖失敗", e)        # 數字真的沒了 → 應該 🔴

    失敗時數字**真的消失**，卻被守衛要求改成 🟠。**「只認 st.*」等於把專案自己的
    render helper 當成隱形的。** 現在改成白名單：try 內每一個**裸函式呼叫**都必須是
    builtin 或具名的純數值轉換；只要出現一個不認識的裸呼叫（＝可能是專案 helper），
    就**不是** chart-only。方法呼叫（`fig.add_trace` / `_s.rolling` / `go.Figure`）
    不在此限 —— 它們作用在本地物件或繪圖／資料函式庫上。
    """
    st_calls = [c for b in node.body
                for c in _st_calls_named(b, _ST_RENDER_ATTRS | _CHART_CALLS, containers)]
    charts = [c for c in st_calls if c.func.attr in _CHART_CALLS]
    if not charts or len(charts) != len(st_calls):
        return False                       # 沒畫圖、或還畫了別的 st 輸出
    for b in node.body:
        for c in ast.walk(b):
            if (isinstance(c, ast.Call) and isinstance(c.func, ast.Name)
                    and c.func.id not in _CHART_SAFE_BARE_CALLS):
                return False               # 不認識的裸呼叫 → 可能是會產生數字的 helper
    return True


@pytest.mark.parametrize("path", HEALTH_SCOPE + BATCH2A_SCOPE_A, ids=lambda p: p.name)
def test_n3_degraded_is_not_a_one_way_escape_hatch(path: pathlib.Path):
    """`degraded=True`（🔴 → 🟠）**只准用在「只畫圖」的 try 上**。

    ⚠️ 2026-08-28 第二輪稽核 N3：`degraded=` 是整批 PR 裡**唯一能把紅變橘的槓桿**，
    而它上一輪**零守衛** —— 通過條件只寫在 docstring，機器不管。兩組稽核各自實測：
    把風險指標表（HWM σ）的真失敗、以及 `render_state` docstring 自己點名必須 🔴 的
    正例（USDTWD 不可用 → 美元計價基金被排除）加上 `degraded=True`，**全套件照樣全綠**。
    整批 PR 的論旨是「真失敗必須是紅的」，那條槓桿不能沒有鎖。

    ⚠️ 這是**單向**規則，刻意的：它擋「不該降的降了」，**不強迫**「該降的一定要降」。
    反方向的強迫規則（chart-only ⇒ 必須 degraded）上一輪存在過，被稽核 N4 打掉 ——
    它會把「數字真的消失」的區塊逼成橘色，正好是客戶 Q2 要建立的分辨力的反方向。
    代價據實揭露：**把某處的 `degraded=True` 拿掉不會有測試轉紅**（那個方向由 review 守）。

    ⚠️ **本鎖的兩個已知破口（2026-08-28 第三輪稽核 P2 實測，未修，登記第二批）**：
      1. 它只走 `ast.Try` 的 **handlers**。寫在 **try body** 裡的 `system_error(...)`
         看不到 —— `backtest_section` 的 USDTWD 那處就是這個形狀（`if _err: system_error(...)`
         寫在 try body 內），對它加 `degraded=True` **本規則全綠**。
      2. `degraded` 的值必須是**字面量 `True`** 才認得出；寫成 `degraded=_DEGRADE`
         這種變數就抓不到。
    **不要把本規則讀成「degraded 已經鎖死」** —— 它鎖住的是最常見的那個寫法。
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    containers = _st_container_names(tree)
    bad = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try) or _is_chart_only_try(node, containers):
            continue
        for handler in node.handlers:
            for call in ast.walk(handler):
                if (isinstance(call, ast.Call) and _callee(call) == "system_error"
                        and _may_be_degraded(call)):
                    bad.append(f"{path.relative_to(ROOT)}:{call.lineno}")
    assert not bad, (
        "以下 `system_error(degraded=True)` 所在的 try，**本規則無法確認它只在畫圖**"
        "（try 內出現了不認識的裸呼叫，可能是會產生數字的專案 helper）。\n"
        "⚠️ 這是**規則能力的陳述，不是事實斷言** —— 它不代表那裡的數字一定會消失"
        "（白名單有 false negative，方向是保守的：寧可多留一個 🔴）。"
        "若確認只畫圖，請把那個裸呼叫加進 `_CHART_SAFE_BARE_CALLS`（並先問：它會不會"
        "在畫面上產生一個數字？）；否則維持 🔴：\n  "
        + "\n  ".join(bad)
    )
