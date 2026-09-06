"""② 持倉體檢新頁的**零寫入**守衛 —— (A) 路線讀法甲的可執行版本。

這一份在守什麼（先講清楚，免得下一個人以為它守的是「有沒有委派」）
------------------------------------------------------------------
客戶方針（2026-09-04）第 1 條：**「資料路徑一行都不動，確保 Google Sheet 零風險」。**
總管 2026-09-06 裁決取**讀法甲**：(A) 在 ② 身上 ＝ **新頁零寫入、舊模組不動**。

理由是一個**實測出來的事實，不是設計偏好**：② 全鏈路只有一處雲端寫入
（`ui/helpers/nav_history_hook.py::record_batch_nav_points` → `services/nav_history_gs.py::append_points`
→ `ws.append_rows(...)`），而它是「健診自己去抓 NAV」的副產物；新頁的資料來源是
`portfolio_funds`（④ 寫入的 session 契約，:func:`~ui.views.page_02_health._holdings` 只讀不寫），
**根本不抓 NAV** ⇒ **沒有東西可委派**。

⇒ 於是「委派真的有發生」這條守衛**在甲之下沒有對象**，本檔把它翻成**反面**：
   **驗這一頁真的一次寫入都沒有。**

⛔ 本檔**不**驗「有沒有 import 舊 ②」—— 那是
   `tests/test_wf02_health_skeleton.py::test_the_page_does_not_delegate_to_the_old_tab`
   的職責，在這裡再抄一份就是第二把尺（`CLAUDE.md §2.1`）。
   ⚠️ **但那條守衛自陳有一個洞**（見它的 docstring）：`ImportFrom` 只吐 `_n.module`，
   所以 `from ui import tab3_portfolio` / `from ui.helpers import fund_grp_health`
   **會綠燈通過**。本檔**不修那個洞**（既有已登記缺口，非本批造成），
   但下面的 :func:`test_rendering_the_page_touches_no_write_sink` 是**行為**測試 ——
   不論用哪種 import 形態接上去，只要真的**呼叫**到寫入就會轉紅。
   兩者的關係要講準：**靜態那條擋「接線」、本檔擋「真的寫下去」，本檔不是它的替代品。**

「零寫入」的精確定義（不精確就會被讀成「連 form 狀態都不能存」）
--------------------------------------------------------------
**零寫入 ＝ 零「別人的」寫入**，不是「一個 session key 都不准動」：

===================================== ============================================
✅ 允許                                本頁**自己命名空間**的 UI 狀態
                                      （`v02_health_*`，見 `_SK_APPLIED`）——
                                      那是 form 的已套用值，只活在瀏覽器 session 裡，
                                      碰不到任何雲端／磁碟。
⛔ 禁止                                Google Sheets／本地磁碟快取／
                                      **別人擁有的 session 契約鍵**
                                      （`portfolio_funds`、policy、`_nav_hist_*` …）
===================================== ============================================

三條互補的守法（**刻意重疊**，因為它們各自看不見的東西不同）
------------------------------------------------------------
1. :func:`test_the_page_only_writes_its_own_session_namespace` —— **靜態**。
   走 `tests/_ast_bindings.py::session_writes`（四條管道的那一份 SSOT，
   含屬性賦值／`update()`／widget `key=`），不自己寫第五份掃描器。
   **看不見**：跨函式（把 `st.session_state` 傳出去由別人寫）、動態 `setattr`。
2. :func:`test_rendering_the_page_touches_no_write_sink` —— **行為 · 哨兵**。
   把寫入槽全部換成「一被呼叫就 fail」的哨兵，渲染整頁，斷言零呼叫。
   **看得見** 1. 看不見的跨函式與動態呼叫；**看不見**本檔沒列進哨兵的槽。
3. :func:`test_rendering_the_page_leaves_every_foreign_session_key_alone` —— **行為 · 快照**。
   渲染前後逐鍵比對，任何**不屬於本頁命名空間**的鍵有增／減／變值即紅。
   **看得見** 2. 沒列到的 session 寫入；**看不見**繞過被替換 `st` 的模組。

⚠️ **哨兵清單是「掃出來的 ＋ 明列的」，不是純手抄，但也不宣稱窮舉。**
   :func:`_sink_targets` 會先掃 `page_02_health` 的轉移 import 閉包，
   找出**函式體內含寫入 primitive** 的模組，再補上一批**已知的寫入入口**
   （即使它們目前不在閉包裡 —— 那正是重點：有人接上去時要當場轉紅）。
   **未涵蓋**：本檔 primitive 字表以外的寫法、動態 import 後才出現的槽。
"""
from __future__ import annotations

import ast
import copy
import importlib
import pathlib
import sys
from typing import Any

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "ui" / "views" / "page_02_health.py"

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _ast_bindings import guarded_key_names, session_writes  # noqa: E402

# ⚠️ 錄影機與持股 fixture **一律沿用骨架守衛那一份**，不在這裡再造一台 ——
#    兩台錄影機必然漂移，而漂移的那一天沒有人會發現（`CLAUDE.md §2.1`）。
from test_wf02_health_skeleton import _Rec, RICH_HOLDINGS  # noqa: E402

from ui.views.page_02_health import render_holdings_health  # noqa: E402

#: 本頁自己的 session 命名空間前綴。
#: ⚠️ **不是在這裡挑一個好聽的前綴**：它必須與 `page_02_health.py` 的 `_SK_*` 常數對得上，
#:    由 :func:`test_the_prefix_really_covers_this_pages_own_keys` 釘住。
OWN_PREFIX = "v02_health"

#: 「寫入」的 primitive —— 出現在函式體內就代表那個函式會動到雲端或磁碟。
#: ⚠️ 這是**屬性呼叫名**，刻意寧可多抓不可漏抓（多抓的代價只是多裝一個哨兵）。
_WRITE_PRIMITIVES = frozenset({
    "append_row", "append_rows", "append_points", "append_point",
    "batch_update", "update_cell", "update_acell", "insert_row", "delete_rows",
    "write_text", "write_bytes", "to_parquet", "unlink", "mkdir",
})

#: **一定要裝哨兵的寫入入口**，即使它現在不在 `page_02_health` 的 import 閉包裡。
#: ⚠️ 「不在閉包裡」正是它們要被列進來的理由：`ui.helpers.nav_history_hook` 是舊 ②
#:    那條唯一的雲端寫入路徑，**有人把它接上新頁的那一刻，這裡就要轉紅**。
_ALWAYS_SENTINEL: tuple[tuple[str, str], ...] = (
    ("ui.helpers.nav_history_hook", "record_batch_nav_points"),
    ("ui.helpers.nav_history_hook", "record_fund_nav_point"),
    ("services.nav_history_gs", "append_points"),
    ("services.nav_history_gs", "append_point"),
    ("services.nav_history_gs", "import_csv_text"),
    ("services.nav_history_store", "import_nav_csv"),
    ("services.nav_history_store", "import_nav_csv_multi"),
    ("services.nav_history_store", "clear_cache"),
    ("services.nav_history_store", "backfill_to_gs"),
    ("repositories.pool_repository", "add_or_update"),
    ("repositories.pool_repository", "remove_from_pool"),
    ("repositories.pool_repository", "set_type_override"),
)


def _module_path(mod: str) -> pathlib.Path | None:
    _p = ROOT / (mod.replace(".", "/"))
    for _cand in (_p.with_suffix(".py"), _p / "__init__.py"):
        if _cand.exists():
            return _cand
    return None


def _closure(entry: str) -> dict[str, pathlib.Path]:
    """`entry` 的**靜態** import 轉移閉包（只含本 repo 的套件）。

    ⚠️ 靜態閉包 ≠ 呼叫可達；它只用來**產生哨兵候選**，不用來下「有沒有寫入」的結論。
    """
    _seen: dict[str, pathlib.Path] = {}
    _stack = [entry]
    while _stack:
        _m = _stack.pop()
        if _m in _seen:
            continue
        _p = _module_path(_m)
        if _p is None:
            continue
        _seen[_m] = _p
        try:
            _tree = ast.parse(_p.read_text(encoding="utf-8"))
        except SyntaxError:                                  # pragma: no cover
            continue
        for _n in ast.walk(_tree):
            if isinstance(_n, ast.ImportFrom) and _n.module and _n.level == 0:
                if _n.module.split(".")[0] in ("ui", "services", "repositories",
                                               "shared", "infra"):
                    _stack.append(_n.module)
                    _stack.extend(f"{_n.module}.{_a.name}" for _a in _n.names)
            elif isinstance(_n, ast.Import):
                _stack.extend(_a.name for _a in _n.names
                              if _a.name.split(".")[0] in (
                                  "ui", "services", "repositories", "shared", "infra"))
    return _seen


def _sink_targets() -> list[tuple[str, str]]:
    """要裝哨兵的 `(module, function)`。**掃出來的 ∪ 明列的**，去重後排序。"""
    _out: set[tuple[str, str]] = set(_ALWAYS_SENTINEL)
    for _mod, _path in _closure("ui.views.page_02_health").items():
        try:
            _tree = ast.parse(_path.read_text(encoding="utf-8"))
        except SyntaxError:                                  # pragma: no cover
            continue
        for _fn in _tree.body:
            if not isinstance(_fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for _n in ast.walk(_fn):
                if (isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute)
                        and _n.func.attr in _WRITE_PRIMITIVES):
                    _out.add((_mod, _fn.name))
                    break
    return sorted(_out)


def _page_tree() -> ast.Module:
    return ast.parse(SRC.read_text(encoding="utf-8"))


def _own_key_literals() -> set[str]:
    """本頁**自己擁有**的 session 鍵：常數名 ＋ 字面值。

    ⛔ **不是「所有 `_SK_*` 常數」—— 這一點是被一顆存活的突變逼出來的，別再改回去。**

    本檔初版寫的是 ``guarded_key_names(tree, "_SK_")``，它回傳
    ``{_SK_APPLIED, v02_health_applied_filters, _SK_PORTFOLIO, portfolio_funds}``——
    **`portfolio_funds` 混進了「自有鍵」**。於是突變
    ``st.session_state["portfolio_funds"] = []``（把使用者的持股清空，
    正是本檔最該擋的那一種）**靜態守衛全綠放行**，只有行為快照那條紅了。
    ⚠️ `_SK_PORTFOLIO` 是**別人的**契約（④ 寫入，本頁**只讀不寫**，見被測檔該常數的註解）——
    「本頁有一個常數指向它」與「本頁擁有它」是兩件事。

    現行判準：**只有字面值以 :data:`OWN_PREFIX` 開頭的才算自有**（連同它的常數名）。
    仍走 `guarded_key_names` 取字面值（不自己再寫一份解析），只是**多一道過濾**。
    """
    _tree = _page_tree()
    _all = guarded_key_names(_tree, "_SK_") | guarded_key_names(_tree, "_FORM_")
    _own: set[str] = {_v for _v in _all if _v.startswith(OWN_PREFIX)}
    # 把「字面值屬於自己」的那些常數**名字**也收進來（`st.session_state[_SK_APPLIED] = …`
    # 的 unparse 印出來的是常數名，不是字面值）。
    # ⚠️ **`ast.Assign` 與 `ast.AnnAssign` 兩種都要認** —— 被測檔寫的是
    #    `_SK_APPLIED: str = "v02_health_applied_filters"`（帶型別註記 ＝ `AnnAssign`），
    #    只認 `Assign` 會**漏掉本頁全部的自有鍵常數**，於是連合法的 form 寫入都被誤判成違規
    #    （本檔實跑撞過這個偽陽性）。同一種病在派工單裡被點名過四次：
    #    **字面 pattern 假設了唯一一種寫法。**
    for _n in ast.walk(_tree):
        if isinstance(_n, ast.Assign):
            _val, _tgts = _n.value, _n.targets
        elif isinstance(_n, ast.AnnAssign):
            _val, _tgts = _n.value, [_n.target]
        else:
            continue
        if isinstance(_val, ast.Constant) and isinstance(_val.value, str) \
                and _val.value.startswith(OWN_PREFIX):
            _own.update(_t.id for _t in _tgts if isinstance(_t, ast.Name))
    return _own


# ══════════════════════════════════════════════════════════════════════
# 1｜靜態 —— 本頁只准寫自己的命名空間
# ══════════════════════════════════════════════════════════════════════
def test_the_prefix_really_covers_this_pages_own_keys():
    """錨點：:data:`OWN_PREFIX` 必須真的對得上本頁的 `_SK_*` 常數。

    ⚠️ **沒有這條，下面那條會靜默失效** —— 前綴若寫錯（例如頁面改名成 `v2h_*`），
    「本頁自己的鍵」會變成空集合，於是**任何**寫入都被判成違規…或反過來，
    前綴放寬成 `""` 就**什麼都放行**。這條把前綴釘在被測檔的常數上。
    """
    from ui.views import page_02_health as _mod
    _own = [_v for _k, _v in vars(_mod).items()
            if _k.startswith("_SK_") and isinstance(_v, str)]
    assert _own, "被測檔一個 `_SK_*` 常數都沒有 —— 前綴斷言失去對象"
    _mine = [_v for _v in _own if _v.startswith(OWN_PREFIX)]
    assert _mine, (
        f"`OWN_PREFIX = {OWN_PREFIX!r}` 對不上本頁任何 `_SK_*` 常數：{_own}\n"
        "前綴一旦對不上，零寫入守衛會靜默失效（見本函式 docstring）。")


def test_the_page_only_writes_its_own_session_namespace():
    """⛔ 本頁的每一處 session 寫入，都必須落在 `v02_health_*`。

    走 `tests/_ast_bindings.py::session_writes` —— 它認得**四條管道**
    （下標賦值／屬性賦值／`update()`／widget `key=`），本檔不自己寫第五份。

    **突變驗證（實跑）**：在 `_render_filter_form()` 內加
    `st.session_state["portfolio_funds"] = []` → 轉紅。
    """
    _tree = _page_tree()
    _own = _own_key_literals()
    _bad: list[str] = []
    for _fn in ast.walk(_tree):
        if not isinstance(_fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for _w in session_writes(_fn, widget_key_names=_own):
            _txt = ast.unparse(_w)
            if not any(_o in _txt for _o in _own):
                _bad.append(f"{_fn.name}() 第 {_w.lineno} 行：{_txt[:90]}")
    assert not _bad, (
        "本頁寫進了**不屬於自己命名空間**的 session 鍵：\n  "
        + "\n  ".join(_bad)
        + f"\n本頁只准寫 `{OWN_PREFIX}*`（本檔認得的自有鍵：{sorted(_own)}）。\n"
          "客戶方針第 1 條：資料路徑一行都不動 —— 別人的 session 契約也是路徑的一部分。")


def test_the_read_only_portfolio_key_is_not_treated_as_ours():
    """⛔ 錨點 —— `portfolio_funds` **絕不**算本頁的自有鍵。

    這條釘住的是本檔初版真的犯過的 fail-open（見 :func:`_own_key_literals` 的長註）：
    把「所有 `_SK_*` 常數」當成自有鍵，於是
    ``st.session_state["portfolio_funds"] = []`` 靜態全綠放行。
    **突變驗證（實跑）**：把 :func:`_own_key_literals` 改回
    ``guarded_key_names(_page_tree(), "_SK_")`` → 本條轉紅。
    """
    from ui.views import page_02_health as _mod
    _own = _own_key_literals()
    assert _mod._SK_PORTFOLIO not in _own, (
        f"`{_mod._SK_PORTFOLIO}` 被當成本頁的自有鍵 —— 那是 ④ 寫入的契約，本頁只讀。\n"
        "一旦它算自有，『清空使用者持股』這種寫入會被靜態守衛放行。")
    assert _own, "自有鍵集合是空的 —— 反過來會把合法的 form 狀態誤判成違規"


# ══════════════════════════════════════════════════════════════════════
# 2｜行為 —— 渲染整頁，一個寫入槽都不准被碰到
# ══════════════════════════════════════════════════════════════════════
def _render_with_sentinels(portfolio: list, monkeypatch) -> list[str]:
    """裝好哨兵 → 渲染整頁 → 回傳被觸發的槽（空 list ＝ 乾淨）。

    ⚠️ **`st` 的替換對象是「掃出來的」不是抄來的**：patch `sys.modules` 裡
    **每一個** module 層帶 `st` 的 `ui.*` 模組。骨架守衛那份是寫死的清單，
    新增一個 `ui.helpers.ia.*` 子模組時它會**靜默漏錄**；這裡改成掃描，
    順便讓「渲染真的跑到哪些模組」不再是假設。
    """
    _tripped: list[str] = []

    for _mod_name, _fn_name in _sink_targets():
        try:
            _m = importlib.import_module(_mod_name)
        except Exception:                                    # pragma: no cover
            continue                     # 匯入不了的槽本來就走不到，跳過
        if not hasattr(_m, _fn_name):
            continue

        def _sentinel(*_a: Any, _tag: str = f"{_mod_name}.{_fn_name}",
                      **_kw: Any) -> None:
            _tripped.append(_tag)

        monkeypatch.setattr(_m, _fn_name, _sentinel, raising=False)

    # ⚠️ **`deepcopy` 不是保險起見，是一顆存活突變逼出來的。**
    #    初版直接把 module 層的 `RICH_HOLDINGS` **物件本身**塞進 session。突變
    #    「就地竄改使用者持股」(`_z['code'] = 'HACKED'`) 於是把那份**共用 fixture 改掉了**，
    #    後面 :func:`test_rendering_the_page_leaves_every_foreign_session_key_alone`
    #    再 deepcopy 時拿到的已經是**被改過的**版本 → 前後一致 → **突變存活、全綠**。
    #    單獨跑那條會紅、整檔一起跑就綠 —— **最難發現的那一種假綠燈。**
    _rec = _Rec()
    _rec.session_state["portfolio_funds"] = copy.deepcopy(portfolio)

    _targets = [_m for _n, _m in list(sys.modules.items())
                if _n.startswith("ui.") and _m is not None
                and getattr(_m, "st", None) is not None]
    assert _targets, "一個帶 module 層 `st` 的 ui 模組都沒掃到 —— 錄影機沒接上"
    for _m in _targets:
        monkeypatch.setattr(_m, "st", _rec, raising=False)

    render_holdings_health()
    return _tripped


def test_rendering_the_page_touches_no_write_sink(monkeypatch):
    """⛔ 整頁渲染一輪，**一個寫入槽都不准被呼叫到**。

    這是三條裡唯一擋得住「靜態掃不到的寫入」的一條 ——
    跨函式傳遞、動態 import、以及靜態守衛那個已登記的 `ImportFrom` 洞。

    **突變驗證（實跑）**：在 `render_holdings_health()` 開頭加
    `from ui.helpers.nav_history_hook import record_batch_nav_points;
    record_batch_nav_points([])` → 轉紅並印出被碰到的槽。
    """
    _tripped = _render_with_sentinels(RICH_HOLDINGS, monkeypatch)
    assert not _tripped, (
        "本頁渲染時呼叫了寫入槽：" + ", ".join(sorted(set(_tripped)))
        + "\n總管 2026-09-06 裁決（讀法甲）：② **零寫入**。"
          "在 `nav_history` 涵蓋範圍調查有結論之前，**不得**新增任何寫使用者 Google Sheet 的路徑。")


def test_the_sentinel_list_is_not_empty_and_covers_the_known_cloud_write():
    """錨點：哨兵清單不得是空的，而且**一定**要含舊 ② 那條唯一的雲端寫入路徑。

    ⚠️ 沒有這條，上面那條會在「一個哨兵都沒裝上」時**照樣全綠** ——
    那是本 repo 已經被抓到過的形狀（斷言做在空集合上）。
    """
    _targets = set(_sink_targets())
    assert _targets, "哨兵清單是空的 —— 零寫入斷言會對著空集合成立"
    assert ("ui.helpers.nav_history_hook", "record_batch_nav_points") in _targets, (
        "哨兵沒有涵蓋舊 ② 唯一的雲端寫入入口 `record_batch_nav_points` —— "
        "那正是本批最需要擋住的那一條。")
    assert ("services.nav_history_gs", "append_points") in _targets, (
        "哨兵沒有涵蓋 `append_points`（真正打 Google Sheets 的那一層）。")


# ══════════════════════════════════════════════════════════════════════
# 3｜行為 —— 渲染前後，別人的 session 鍵一個都不准動
# ══════════════════════════════════════════════════════════════════════
def test_rendering_the_page_leaves_every_foreign_session_key_alone(monkeypatch):
    """⛔ 渲染一輪之後，**不屬於本頁命名空間**的 session 鍵必須完全沒動。

    比對的是**增／減／變值**三種 —— 只驗「有沒有新鍵」會漏掉
    「就地改掉 `portfolio_funds` 的內容」這種最貴的一種（使用者的持股被改掉）。

    **突變驗證（實跑）**：在 `_holdings()` 內加
    `st.session_state["portfolio_funds"] = []` → 轉紅（`portfolio_funds` 變值）。
    """
    import copy

    _tripped: list[str] = []
    for _mod_name, _fn_name in _sink_targets():
        try:
            _m = importlib.import_module(_mod_name)
        except Exception:                                    # pragma: no cover
            continue
        if hasattr(_m, _fn_name):
            monkeypatch.setattr(_m, _fn_name,
                                lambda *_a, **_kw: _tripped.append(_fn_name),
                                raising=False)

    _rec = _Rec()
    _rec.session_state["portfolio_funds"] = copy.deepcopy(RICH_HOLDINGS)
    _rec.session_state["policy_v2_cache"] = {"P1": {"invest_twd": 123}}
    _rec.session_state["_nav_hist_written"] = set()
    _before = copy.deepcopy({_k: _v for _k, _v in _rec.session_state.items()
                             if not _k.startswith(OWN_PREFIX)})

    _targets = [_m for _n, _m in list(sys.modules.items())
                if _n.startswith("ui.") and _m is not None
                and getattr(_m, "st", None) is not None]
    for _m in _targets:
        monkeypatch.setattr(_m, "st", _rec, raising=False)
    render_holdings_health()

    _after = {_k: _v for _k, _v in _rec.session_state.items()
              if not _k.startswith(OWN_PREFIX)}
    _added = sorted(set(_after) - set(_before))
    _removed = sorted(set(_before) - set(_after))
    _changed = sorted(_k for _k in set(_before) & set(_after)
                      if _after[_k] != _before[_k])
    assert not (_added or _removed or _changed), (
        f"渲染動到了別人的 session 鍵 —— 新增 {_added}／消失 {_removed}／變值 {_changed}\n"
        f"本頁只准動 `{OWN_PREFIX}*`。")


def test_the_foreign_key_snapshot_actually_has_something_to_protect():
    """錨點：上面那條的 `_before` 不得是空的。

    空快照 ＝ 「沒有任何外來鍵被改到」恆真 —— 又一個「斷言做在空集合上」的形狀。
    """
    _rec = _Rec()
    _rec.session_state["portfolio_funds"] = copy.deepcopy(RICH_HOLDINGS)
    _rec.session_state["policy_v2_cache"] = {"P1": {"invest_twd": 123}}
    _foreign = {_k for _k in _rec.session_state if not _k.startswith(OWN_PREFIX)}
    assert len(_foreign) >= 2, (
        f"外來鍵快照只有 {_foreign} —— 保護對象太少，突變殺不死這條守衛")
