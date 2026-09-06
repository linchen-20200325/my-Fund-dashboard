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


⚠️ 這道守衛**看得見什麼、看不見什麼**（2026-09-06 回修：整段改寫，理由見下）
-----------------------------------------------------------------------------
**本檔初版（`bf5d229`）在這裡寫了三句過強的宣稱，獨立稽核組逐條證偽。**
依 `CLAUDE.md §-2` 規則 6（**沒查證的宣稱比沒有宣稱更危險**），三句一律改成
可自驗的敘述，**並且把守衛本身補到配得上新敘述為止**。三句的前後對照，
連同「哪一句是假的、假在哪裡」，逐條記在 :data:`_WHAT_THE_FIRST_CUT_CLAIMED`。

**看得見（每一條都有反向突變實跑證明，見各測試 docstring 的「突變驗證」欄）**

===================================== ======================================================
① 列名槽的**任何 import 形態**         `_install_named_sentinels` patch 的是**函式物件**，
                                      再以 `id()` 掃過 `sys.modules` 把**所有別名**一起換掉。
                                      `from m import f`（家風寫法）在 import 當下就把物件綁進
                                      消費模組的命名空間 —— **patch 來源模組碰不到它**，
                                      這正是初版最大的洞（稽核實測：接上去照樣 7 passed）。
                                      現行做法對 `from m import f` / `import m` 後 `m.f()` /
                                      `g = m.f` 取別名 **三種都成立**。
② 沒列名、但**真的寫下去**的東西       `_primitive_sentinels` 直接 patch **primitive 本身**
                                      （gspread 的寫入方法、`pathlib.Path.write_*`、
                                      `builtins.open` 寫入模式、`os` 刪改、`pandas.to_*`、
                                      `requests`/`httpx` 的 POST/PUT/PATCH/DELETE）。
                                      **不管呼叫端叫什麼名字、有沒有被列進清單**，
                                      只要真的動到雲端或磁碟就會撞上。
③ 靜態掃不到的跨函式／動態呼叫         ①② 都是**行為**測試，渲染真的跑一輪。
④ 別人的 session 鍵被就地改掉         渲染前後逐鍵 deepcopy 比對（增／減／**變值**）。
⑤ **兩條渲染分支**                    有持倉（三張卡＋逐檔表）與**空持倉**（空狀態）各跑一次。
                                      稽核 M10：初版只跑前者，寫入藏在空狀態分支裡不會紅。
===================================== ======================================================

**看不見（照實列，不要讀成「守死了」）**

* **本檔 primitive 字表以外的寫法** —— `sqlite3` / `subprocess` / 原始 `socket` /
  `os.write(fd, ...)` 這類 fd 級寫入、`http.client` 直接組請求、
  `httpx.AsyncClient` 以外的非同步 client、以及任何 C 擴充直接落盤。
  （HTTP 那一面目前守到 `requests.Session.request` / `httpx.Client` 與 `AsyncClient.request` /
  `urllib.request.urlopen` 三條；`urlopen` 是 2026-09-06 補的 ——
  本 repo 有真實的 urlopen 直連家風，只守前兩條會整條漏掉。）
* **哨兵一律「記名」不「拋例外」** —— 這不是風格偏好：本頁每一塊都包在
  `ui/helpers/render_state.py::safe_section` 裡，它**捕捉例外、印紅框、不外拋**。
  **實測**：換一個會 `raise` 的假函式進去，`render_holdings_health()` **正常返回**。
  ⇒ **會 raise 的哨兵在這一頁上等於沒有哨兵。** 詳見 :func:`_make_recorder`。
* **`builtins.open` 這一路是「觀察」不是「攔截」**：它會**放行**真正的呼叫
  （不放行會把渲染期間所有合法讀檔一起打死 —— 實測 patch 全域 `open` 會波及
  pytest／streamlit／importlib）。只在 mode 含 `w` / `x` / `a` / `+` 時記一筆。
  ⇒ 若真的踩到，**檔案會被寫出來**，本檔只保證**當場轉紅**、不保證沒發生。
* **primitive 哨兵只在 `render_holdings_health()` 那一小段生命週期內生效**
  （全程掛著會影響同進程的其他測試）。渲染之外的寫入本檔看不到。
* **`_sink_targets()` 的名字清單不是窮舉**，而且**刻意只收語意不含糊的名字** ——
  `update` / `clear` / `open` / `write` / `dump` 這些**故意不進字表**：
  它們同時是 `dict.update` / `list.clear` 的名字，收進來會在**無辜的函式**上裝哨兵，
  那一刻起任何渲染路徑碰到它就是**偽陽性紅燈**。
  ⚠️ **初版 docstring 寫「寧可多抓不可漏抓，多抓的代價只是多裝一個哨兵」——那句是錯的**：
  多抓的代價是**假紅燈**。含糊名字改由上表 ② 的 primitive 哨兵在**執行期**接住。
* **靜態那條的 widget `key=` 管道**（見 :func:`test_the_page_only_writes_its_own_session_namespace`
  的 docstring）在「自有鍵」那一輪**結構上不可能命中**；本檔另立
  :func:`test_no_widget_hijacks_a_foreign_session_contract_key` 專門讓它活起來。
* `tests/test_wf02_health_skeleton.py` 那條靜態委派守衛自陳的 `ImportFrom` 洞
  （`from ui import tab3_portfolio` 會綠燈）**本檔不修**（既有已登記缺口，非本批造成）；
  但上表 ①②③ 是行為測試 —— 不論用哪種 import 形態接上去，**只要真的呼叫到就會轉紅**。
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
"""
from __future__ import annotations

import ast
import builtins
import contextlib
import copy
import importlib
import io
import os
import pathlib
import sys
from typing import Any, Callable, Iterator, NamedTuple

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "ui" / "views" / "page_02_health.py"

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _ast_bindings import guarded_key_names, session_writes  # noqa: E402

# ⚠️ 錄影機與持股 fixture **一律沿用骨架守衛那一份**，不在這裡再造一台 ——
#    兩台錄影機必然漂移，而漂移的那一天沒有人會發現（`CLAUDE.md §2.1`）。
from test_wf02_health_skeleton import _Rec, RICH_HOLDINGS  # noqa: E402

from ui.views.page_02_health import render_holdings_health  # noqa: E402

#: 本檔初版（`bf5d229`）寫下、而 2026-09-06 獨立稽核**逐條證偽**的三句宣稱。
#:
#: ⚠️ **保留原文不是為了自責，是因為它們會被引用。** 一句過強的守衛宣稱
#: 會讓下一個人建立在假前提上繼續蓋 —— 這三句都曾以「已驗證」的語氣寫在
#: PR 描述與本檔 docstring 裡，實際上：
#:
#: 1. **「有人把它接上新頁的那一刻，這裡就要轉紅」** —— **假**。
#:    初版用 ``monkeypatch.setattr(來源模組, 函式名, 哨兵)``，而本 repo 的家風寫法是
#:    ``from ui.helpers.nav_history_hook import record_batch_nav_points``：
#:    import 當下就把**函式物件**綁進消費模組，之後 patch 來源模組**碰不到它**。
#:    稽核實測：照家風接上真正的寫入呼叫 → **7 passed，一片綠**。
#:    （初版自己做的那次突變剛好用了**函式內** import —— 唯一一種 patch 抓得到的形式。）
#:    → 現行：改成**掃 `sys.modules` 的物件別名**一起換掉，見 :func:`_install_named_sentinels`；
#:      並另加 primitive 哨兵當第二道。**兩者都有反向突變實跑。**
#: 2. **「四條管道」** —— **半真**。`_ast_bindings.session_writes` 確實認四條，
#:    但本檔在「自有鍵」那一輪傳的是 ``widget_key_names=_own``，於是管道 4（widget `key=`）
#:    **只可能命中自有鍵**，而自有鍵一定通過後面的文字檢查 ⇒ **管道 4 在那條測試裡零偵測力**。
#:    → 現行：那條 docstring 改為誠實敘述（「實際發揮作用的是前三條」），
#:      並新增 :func:`test_no_widget_hijacks_a_foreign_session_contract_key` 讓管道 4 真的有對象。
#: 3. **「掃出來的 ∪ 明列的」** —— **技術上為真、實質誤導**。初版的掃描器有三個結構性缺陷
#:    （`_closure` 只跟絕對 import ⇒ ``repositories.policy.v1``/``v2`` **從未被掃過**；
#:    `_sink_targets` 只走頂層 ``FunctionDef`` ⇒ class 方法寫入全部隱形；
#:    primitive 字表缺 ``add_worksheet`` / ``to_csv`` 等），實測 **14 個哨兵裡只有 2 個是掃出來的**。
#:    → 現行：三個缺陷都修了（相對 import／``ast.walk``／補字表），
#:      **掃描器貢獻的候選 2 → 20**（`_sink_targets()` 總數 14 → 32，其中 12 個一直是
#:      :data:`_ALWAYS_SENTINEL` 明列的；import 閉包 58 → 65 個模組。量測日 2026-09-06，
#:      複驗指令見 :func:`_sink_targets`）。
#:      **但仍不宣稱窮舉** —— 名字清單永遠不會窮舉，這正是 primitive 哨兵存在的理由。
_WHAT_THE_FIRST_CUT_CLAIMED = (
    "接上去就會轉紅（假：patch 來源模組抓不到 `from m import f`）",
    "四條管道（半真：管道 4 在自有鍵那一輪零偵測力）",
    "掃出來的 ∪ 明列的（誤導：14 個裡只有 2 個是掃出來的）",
)

#: 本頁自己的 session 命名空間前綴。
#: ⚠️ **不是在這裡挑一個好聽的前綴**：它必須與 `page_02_health.py` 的 `_SK_*` 常數對得上，
#:    由 :func:`test_the_prefix_separates_our_keys_from_the_foreign_contract_key` 釘住 ——
#:    **那條錨點刻意同時驗「涵蓋自有鍵」與「不涵蓋別人的鍵」**，因為初版只驗前者，
#:    於是 ``OWN_PREFIX = ""``（什麼都放行）**照樣全綠**。
OWN_PREFIX = "v02_health"

#: 別人擁有、本頁**只讀不寫**的 session 契約鍵（④ 寫入）。
FOREIGN_CONTRACT_KEY = "portfolio_funds"

#: 「寫入」的 primitive **名字**（給靜態掃描器用，找出「這個函式會動到雲端或磁碟」）。
#:
#: ⚠️ **刻意只收語意不含糊的名字，這是一個被想清楚的取捨，不是漏列。**
#: 初版 docstring 寫「寧可多抓不可漏抓（多抓的代價只是多裝一個哨兵）」—— **那句是錯的**：
#: 名字比對命中一個無辜的函式，本檔就會在它身上裝哨兵；渲染路徑一旦碰到它，
#: 得到的是**偽陽性紅燈**，而下一個人只會去加豁免。
#: ``update`` / ``clear`` / ``open`` / ``write`` / ``dump`` / ``rename`` 同時是
#: ``dict.update`` / ``list.clear`` / ``DataFrame.rename`` 的名字 ⇒ **不進本字表**，
#: 改由 :func:`_primitive_sentinels` 在**執行期**直接守 primitive 物件本身
#: （那一路不看名字，只看「有沒有真的被呼叫」，因此完全沒有這個問題）。
_WRITE_PRIMITIVES = frozenset({
    # ── gspread：真正打 Google Sheets 的方法名 ────────────────────────
    "append_row", "append_rows", "append_point", "append_points",
    "insert_row", "insert_rows", "insert_cols", "insert_note", "insert_notes",
    "update_cell", "update_acell", "update_cells", "update_note", "update_notes",
    "update_title", "update_index",
    "batch_update", "batch_clear",
    "delete_rows", "delete_columns", "delete_dimension",
    "add_worksheet", "del_worksheet", "del_worksheet_by_id", "add_rows", "add_cols",
    "values_append", "values_update", "values_clear",
    "values_batch_update", "values_batch_clear", "import_csv",
    # ── 磁碟 ──────────────────────────────────────────────────────────
    "write_text", "write_bytes", "unlink", "mkdir", "makedirs",
    "rmdir", "removedirs", "rmtree", "touch",
    # ── pandas 落盤 ───────────────────────────────────────────────────
    "to_parquet", "to_csv", "to_json", "to_excel", "to_pickle", "to_feather", "to_sql",
})

#: **一定要裝哨兵的寫入入口**，即使它現在不在 `page_02_health` 的 import 閉包裡。
#: ⚠️ 「不在閉包裡」正是它們要被列進來的理由：`ui.helpers.nav_history_hook` 是舊 ②
#:    那條唯一的雲端寫入路徑。
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
    # ↓ 2026-09-06 複驗補：這兩個模組**不在** `page_02_health` 的 import 閉包裡
    #   （實測 `_closure()` 皆為 False），原本只靠 primitive 那層兜底。
    #   「靠 primitive 兜得到」在 AST 上成立，但那是**推論**；列名是便宜又確定的那一半。
    ("repositories.ledger_repository", "append_ledger_row"),
    ("repositories.ledger_repository", "replace_ledgers_for_policy"),
    ("repositories.ledger_repository", "ensure_ledger_worksheet"),
    ("repositories.portfolio_perf_repository", "append_snapshot"),
)

#: **別人擁有的 session 契約鍵**（本頁一律只讀不寫）。
#: ⚠️ 這一份是**實測掃出來的**，不是想到什麼寫什麼：
#: ``git grep -ohE 'session_state\[...\]|session_state\.(get|setdefault|pop)\(...'``
#: 掃 `ui/**` `services/**` `repositories/**` 後人工判讀（量測日 2026-09-06）。
#: ⚠️ **仍不是窮舉**：`_nav_hist_*` 這類**前綴**族只列到實際出現過的兩個，
#: 動態組出來的鍵一律看不到。射程限制同步寫在模組 docstring 的 ⛔ 那一格。
_KNOWN_FOREIGN_KEYS: tuple[str, ...] = (
    "portfolio_funds", "portfolio_core_pct",
    "policy_sheet_id", "policy_tabs", "v2_new_policy_name",
    "_nav_hist_written", "_nav_hist_disabled_warned",
    "_perf_snapshot_done", "t7_ledgers",
)

_PKG_ROOTS = ("ui", "services", "repositories", "shared", "infra")


# ══════════════════════════════════════════════════════════════════════
# 0｜靜態掃描器 —— 產生哨兵候選
# ══════════════════════════════════════════════════════════════════════
def _module_path(mod: str) -> pathlib.Path | None:
    _p = ROOT / (mod.replace(".", "/"))
    for _cand in (_p.with_suffix(".py"), _p / "__init__.py"):
        if _cand.exists():
            return _cand
    return None


def _absolutise(mod: str, path: pathlib.Path, node: ast.ImportFrom) -> str:
    """把 `from . import x` / `from ..y import z` 解析成絕對模組名。

    ⚠️ **初版少了這一段，代價很具體**：`_closure` 只跟 ``_n.level == 0``，
    於是 ``repositories/policy/__init__.py`` 那一串 ``from .v1 import ...`` 全部斷掉，
    **`repositories.policy.v1` / `v2` 從來沒有被掃過** —— 而那正是本檔 docstring
    自己點名「禁止」的 policy 寫入面。（實測：修好之後閉包由 58 → 65 個模組。）
    """
    if node.level == 0:
        return node.module or ""
    # 套件的 `__init__.py`：它自己就是 package；一般模組：package 是它的父。
    _pkg = mod if path.name == "__init__.py" else mod.rpartition(".")[0]
    _bits = _pkg.split(".") if _pkg else []
    _drop = node.level - 1
    if _drop:
        _bits = _bits[:-_drop] if _drop <= len(_bits) else []
    if node.module:
        _bits = _bits + node.module.split(".")
    return ".".join(_bits)


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
            if isinstance(_n, ast.ImportFrom):
                _base = _absolutise(_m, _p, _n)
                if _base and _base.split(".")[0] in _PKG_ROOTS:
                    _stack.append(_base)
                    _stack.extend(f"{_base}.{_a.name}" for _a in _n.names)
            elif isinstance(_n, ast.Import):
                _stack.extend(_a.name for _a in _n.names
                              if _a.name.split(".")[0] in _PKG_ROOTS)
    return _seen


def _functions(node: ast.AST, prefix: str = "") -> "Iterator[tuple[str, ast.AST]]":
    """`node` 底下的函式，回傳 `(qualname, node)`；**含 class 方法**。

    ⚠️ **初版只走 `for _fn in _tree.body`（頂層 FunctionDef）**，於是
    `repositories/pool_repository.py` 的 ``GoogleSheetsPoolStore.upsert`` /
    ``LocalJsonPoolStore._write`` 這類 **class 方法寫入全部隱形**。
    """
    for _c in getattr(node, "body", []):
        if isinstance(_c, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield prefix + _c.name, _c
        elif isinstance(_c, ast.ClassDef):
            yield from _functions(_c, prefix + _c.name + ".")


def _sink_targets() -> list[tuple[str, str]]:
    """要裝哨兵的 `(module, qualname)`；qualname 可能是 ``Class.method``。

    **掃出來的 ∪ 明列的**，去重後排序。⚠️ **不宣稱窮舉** ——
    名字清單永遠不窮舉，那正是 :func:`_primitive_sentinels` 存在的理由。

    **量測（2026-09-06；下面這條指令可以直接重跑，也可以指到舊版做前後對照）**::

        python3 -c "import sys; sys.path.insert(0,'tests'); sys.path.insert(0,'.'); \\
            import test_wf02_health_no_writes as T; a=set(T._ALWAYS_SENTINEL); \\
            s=set(T._sink_targets()); print(len(s), len(a), len(s-a), \\
            len(T._closure('ui.views.page_02_health')))"

    ============================== ========== ==========
    項目                            `bf5d229`  本輪
    ============================== ========== ==========
    `_sink_targets()` 總數          14         **32**
    其中 :data:`_ALWAYS_SENTINEL`   12         12
    **掃描器貢獻**                  **2**      **20**
    import 閉包模組數               58         **65**
    ============================== ========== ==========

    新增看得到的東西包括 ``repositories.policy.v1`` / ``v2`` 的 5 個寫入函式
    （初版**從未掃過**，因為 `repositories/policy/__init__.py` 走的是相對 import）
    與 ``repositories.pool_repository`` 的 3 個 **class 方法**（初版只看頂層函式）。
    """
    _out: set[tuple[str, str]] = set(_ALWAYS_SENTINEL)
    for _mod, _path in _closure("ui.views.page_02_health").items():
        try:
            _tree = ast.parse(_path.read_text(encoding="utf-8"))
        except SyntaxError:                                  # pragma: no cover
            continue
        for _qual, _fn in _functions(_tree):
            for _n in ast.walk(_fn):
                if (isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute)
                        and _n.func.attr in _WRITE_PRIMITIVES):
                    _out.add((_mod, _qual))
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

    現行判準：**只有字面值以 :data:`OWN_PREFIX` 開頭的才算自有**（連同它的常數名）。
    """
    _tree = _page_tree()
    _all = guarded_key_names(_tree, "_SK_") | guarded_key_names(_tree, "_FORM_")
    _own: set[str] = {_v for _v in _all if _v.startswith(OWN_PREFIX)}
    # 把「字面值屬於自己」的那些常數**名字**也收進來（`st.session_state[_SK_APPLIED] = …`
    # 的 unparse 印出來的是常數名，不是字面值）。
    # ⚠️ **`ast.Assign` 與 `ast.AnnAssign` 兩種都要認** —— 被測檔寫的是
    #    `_SK_APPLIED: str = "v02_health_applied_filters"`（帶型別註記 ＝ `AnnAssign`）。
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


def _foreign_key_names() -> set[str]:
    """**別人的** session 契約鍵：常數名 ＋ 字面值（＝所有守衛鍵扣掉自有鍵）。"""
    _tree = _page_tree()
    _all = guarded_key_names(_tree, "_SK_") | guarded_key_names(_tree, "_FORM_")
    _own = _own_key_literals()
    _foreign = {_v for _v in _all if _v not in _own}
    _foreign.add(FOREIGN_CONTRACT_KEY)
    # ⚠️ **只靠「本頁的 `_SK_*` 扣掉自有」是不夠的**（2026-09-06 複驗抓到）：
    #    那樣算出來只有 `{_SK_PORTFOLIO, portfolio_funds}` 兩個，於是
    #    `key="policy_v2_cache"` / `key="_nav_hist_written"` 這種**指向別人契約鍵的 widget
    #    完全掃不到** —— 而模組 docstring 的 ⛔ 格明列了 policy 與 `_nav_hist_*`。
    #    宣稱與射程對不上，就是本輪要修的那種病。
    _foreign.update(_KNOWN_FOREIGN_KEYS)
    return _foreign


# ══════════════════════════════════════════════════════════════════════
# 0.5｜哨兵機器 —— 這一節是本輪回修的核心，改它之前先讀 `_install_named_sentinels`
# ══════════════════════════════════════════════════════════════════════
class _SessionDict(dict):
    """`dict`，但**同時吃屬性存取** —— 因為真 streamlit 就是這樣。

    ⚠️ **這不是為了方便，是 2026-09-06 複驗抓到的一個真盲點。**
    真 streamlit 的 ``SessionStateProxy.__setattr__`` 逐字是 ``self[key] = value``
    （實測 `inspect.getsource`）⇒ ``st.session_state.portfolio_funds = []`` 與
    ``setattr(st.session_state, "portfolio_funds", [])`` 在 **production 會真的寫下去**。
    而骨架守衛的 `_Rec.session_state` 是 **plain `dict`** ⇒ 同樣兩行在測試裡只會丟
    `AttributeError`，然後**被 `safe_section` 吃掉** ⇒ 快照比對前後一致 ⇒ **全綠放行**。

    ⚠️ `_ast_bindings.session_writes` 自己寫著：**屬性賦值是「本 repo `ui/**` production
    跨 6 檔 27 處的主流寫法」** —— 也就是漏的正好是最常見的那一種。

    ⛔ **不要把它改回 plain dict**，也不要以為「`_Rec` 是共用 fixture 所以不能動」：
    本檔沒有動 `_Rec`（那是骨架守衛的檔案，不在本批邊界內），只是在
    :func:`_render_with_sentinels` 裡把它的 `session_state` **換成本類的實例**。
    """

    def __getattr__(self, _k: str) -> Any:
        try:
            return self[_k]
        except KeyError:
            raise AttributeError(_k) from None

    def __setattr__(self, _k: str, _v: Any) -> None:
        self[_k] = _v

    def __delattr__(self, _k: str) -> None:
        try:
            del self[_k]
        except KeyError:
            raise AttributeError(_k) from None


class _Run(NamedTuple):
    """一次「裝哨兵 → 渲染 → 收工」的完整紀錄。

    ⚠️ **錨點測試一律驗這裡面的 `named` / `primitives`，不准去驗常數 tuple。**
    初版的錨點斷言 ``("ui.helpers.nav_history_hook", "record_batch_nav_points")
    in _sink_targets()`` —— 而那一項就寫死在 :data:`_ALWAYS_SENTINEL` 裡，
    **安裝迴圈整個癱瘓、一個哨兵都沒真的裝上，那條照樣綠**（稽核 A3-4 實測）。
    錨點要驗的是「**真的在跑的那台機器**」，不是「我自己重新宣告一次的那份清單」。
    """
    tripped: list[str]
    named: list[str]
    primitives: list[str]
    session: dict


def _make_recorder(trips: list[str], tag: str) -> Callable[..., None]:
    """一個**記名、不拋例外**的哨兵。

    ⛔ **不要把它改成 `raise`。** 這不是風格偏好，是一個實測出來的必要條件：
    :func:`ui.views.page_02_health.render_holdings_health` 的每一塊都包在
    `ui/helpers/render_state.py::safe_section` 裡，而那個函式**捕捉例外、印紅框、不外拋**
    （區塊級隔離，它的 docstring 自己寫明「不吞例外 —— 走 `system_error()` 顯式紅燈」，
    意思是**對使用者可見**，但**對呼叫端不外拋**）。

    **實測（2026-09-06）**：把 `_render_health_table` 換成一個 `raise AssertionError(...)`
    的假函式再跑 `render_holdings_health()` → **render 正常返回，例外被 `safe_section` 吃掉**。
    ⇒ **一個會 raise 的哨兵在這一頁上等於沒有哨兵。** 記名 + 事後斷言才擋得住。
    """
    def _sentinel(*_a: Any, **_kw: Any) -> None:
        trips.append(tag)
    _sentinel._wf02_sentinel = tag           # type: ignore[attr-defined]
    return _sentinel


def _resolve(root: Any, qualname: str) -> "tuple[Any, str, Any] | None":
    """`root` 上的 ``a.b.c`` → `(owner, attr, obj)`；找不到回 ``None``。"""
    _owner = root
    _parts = qualname.split(".")
    for _p in _parts[:-1]:
        _owner = getattr(_owner, _p, None)
        if _owner is None:
            return None
    _name = _parts[-1]
    if not hasattr(_owner, _name):
        return None
    return _owner, _name, getattr(_owner, _name)


def _install_named_sentinels(trips: list[str], monkeypatch) -> list[str]:
    """把 :func:`_sink_targets` 的每一個槽換成哨兵，**連同它的所有別名**。

    ⭐ **這一段是本輪最重要的修正，改之前務必讀完。**

    初版做的是 ``monkeypatch.setattr(來源模組, 函式名, 哨兵)`` —— 換掉的是
    **來源模組的屬性**。但本 repo 的家風寫法是在消費模組頂端::

        from ui.helpers.nav_history_hook import record_batch_nav_points

    那一行在 **import 當下**就把函式**物件**綁進 `page_02_health` 的命名空間；
    之後再去 patch 來源模組，**碰不到那個已經綁好的物件**。
    稽核實測：照這個寫法接上真正的寫入呼叫 → **7 passed / 40 passed，一片綠**。
    （初版自己那次突變剛好用了**函式內** import —— 唯一一種 patch 抓得到的形式，
    於是「已突變驗證」這句話成立，而它保證的東西不成立。）

    **現行做法**：先把每個槽的**原始函式物件**收起來，再掃一次 ``sys.modules``，
    凡是**指向同一個物件**（``val is orig``）的 module 層屬性**全部換掉**。
    於是三種綁定形態一起蓋住：

    ==================================== =========================================
    ``from m import f`` （家風）           消費模組的 ``f`` 被別名掃描換掉 ✅
    ``import m`` 之後 ``m.f()``            來源模組的 ``m.f`` 被換掉 ✅
    ``g = m.f`` 之後 ``g()``               ``g`` 若是 module 層屬性 → 換掉 ✅
                                          （**函式內**的區域別名換不掉 —— 但那是在
                                          渲染當下才從已被換掉的模組屬性取值，
                                          所以取到的本來就是哨兵 ✅）
    ==================================== =========================================

    ⚠️ **看不見**：在裝哨兵**之前**就把物件複製進某個容器（list／dict／類別屬性）
    再從那裡取用。本檔不宣稱涵蓋這種。

    :returns: **實際換掉的** ``"module.attr"`` 清單（錨點測試驗的就是這個）。
    """
    # (1) 收原始物件。key 用 id()，因為同一個函式可能被多個槽指到。
    _wanted: dict[int, tuple[Any, Callable[..., None]]] = {}
    _class_owned: list[tuple[Any, str, Any]] = []
    for _mod_name, _qual in _sink_targets():
        try:
            _m = importlib.import_module(_mod_name)
        except Exception:                                    # pragma: no cover
            continue                     # 匯入不了的槽本來就走不到，跳過
        _hit = _resolve(_m, _qual)
        if _hit is None:
            continue
        _owner, _attr, _obj = _hit
        if not callable(_obj):
            continue
        _tag = f"{_mod_name}.{_qual}"
        if id(_obj) not in _wanted:
            _wanted[id(_obj)] = (_obj, _make_recorder(trips, _tag))
        if "." in _qual:                 # class 方法：module 層掃不到，另外記著
            _class_owned.append((_owner, _attr, _tag))

    _installed: list[str] = []

    # (2) 別名掃描：sys.modules 裡每一個「指向同一個物件」的 module 層屬性。
    for _host_name, _host in list(sys.modules.items()):
        if _host is None:
            continue
        try:
            _attrs = list(vars(_host).items())
        except Exception:                                    # pragma: no cover
            continue
        for _attr, _val in _attrs:
            _ent = _wanted.get(id(_val))
            if _ent is not None and _val is _ent[0]:
                monkeypatch.setattr(_host, _attr, _ent[1], raising=False)
                _installed.append(f"{_host_name}.{_attr}")

    # (3) class 方法：`vars(module)` 看不到它們，逐一補裝。
    for _owner, _attr, _tag in _class_owned:
        _cur = getattr(_owner, _attr, None)
        _ent = _wanted.get(id(_cur))
        if _ent is not None:
            monkeypatch.setattr(_owner, _attr, _ent[1], raising=False)
            _installed.append(_tag)

    return sorted(set(_installed))


def _gspread_write_methods() -> "list[tuple[Any, str]]":
    """gspread 上會**改動試算表**的方法。與 `dir()` 取交集，跨版本不會炸。"""
    try:
        import gspread                                       # noqa: PLC0415
    except Exception:                                        # pragma: no cover
        return []
    _table = {
        "Worksheet": {
            "append_row", "append_rows", "insert_row", "insert_rows", "insert_cols",
            "insert_note", "insert_notes", "update", "update_cell", "update_acell",
            "update_cells", "update_note", "update_notes", "update_title",
            "update_index", "update_tab_color", "batch_update", "batch_clear",
            "batch_format", "batch_merge", "delete_rows", "delete_columns",
            "delete_dimension", "delete_named_range", "delete_protected_range",
            "clear", "clear_note", "clear_notes", "clear_basic_filter",
            "clear_tab_color", "add_rows", "add_cols", "add_protected_range",
            "add_validation", "resize", "format", "merge_cells", "unmerge_cells",
            "sort", "duplicate", "copy_to", "copy_range", "cut_range",
            "define_named_range", "set_basic_filter", "hide", "show", "freeze",
        },
        "Spreadsheet": {
            "add_worksheet", "del_worksheet", "del_worksheet_by_id", "batch_update",
            "values_append", "values_update", "values_batch_update", "values_clear",
            "values_batch_clear", "duplicate_sheet", "share", "remove_permissions",
            "update_title", "update_locale", "update_timezone", "reorder_worksheets",
            "transfer_ownership", "accept_ownership", "update_drive_metadata",
        },
        "Client": {
            "create", "copy", "del_spreadsheet", "import_csv",
            "insert_permission", "remove_permission",
        },
    }
    _out: list[tuple[Any, str]] = []
    for _cls_name, _names in _table.items():
        _cls = getattr(gspread, _cls_name, None)
        if _cls is None:                                     # pragma: no cover
            continue
        for _n in sorted(_names):
            if hasattr(_cls, _n):
                _out.append((_cls, _n))
    return _out


_WRITE_MODES = "wxa+"


class _FakeResponse:
    """`urlopen` 被攔下時回的無害假回應（理由見 :func:`_primitive_sentinels` 內的長註）。"""

    status = 200
    headers: dict = {}

    def read(self, *_a: Any) -> bytes:
        return b""

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *_exc: Any) -> bool:
        return False

    def close(self) -> None:
        return None


@contextlib.contextmanager
def _primitive_sentinels(trips: list[str]) -> Iterator[list[str]]:
    """把**寫入 primitive 本身**換成哨兵，只在 `with` 這一小段生命週期內。

    ⭐ **這一路不看名字。** 不管呼叫端怎麼 import、取什麼別名、有沒有被
    :func:`_sink_targets` 列到，只要它**真的**去寫雲端或磁碟，就會撞上這裡。
    ⇒ 這也是為什麼 :data:`_WRITE_PRIMITIVES` 那份**名字**清單可以（而且應該）
      保持保守：漏列一個函式名不再等於漏守。

    ⚠️ **三個刻意的取捨，每一個都有代價，寫在這裡不准省略：**

    1. **`builtins.open` / `Path.open` 是「觀察」不是「攔截」。**
       全域攔截 `open` 會連 pytest、streamlit、`importlib` 的**合法讀檔**一起打死
       （2026-09-06 實測：不收窄就炸整個 session）。現行收窄成
       **只在 mode 含 `w`/`x`/`a`/`+` 時記一筆，然後放行真正的呼叫**。
       ⇒ 若真的踩到，**檔案會被寫出去**；本檔保證的是**當場轉紅**，不是「沒發生」。
    2. **其餘 primitive 是攔截（記一筆之後回 `None`，不執行真正的寫入）。**
       代價：被攔的那一方可能因為拿到 `None` 而在稍後拋例外 —— 那**照樣是紅的**，
       只是訊息會變成別的形狀。取捨理由：**跑一次守衛測試不該真的動到使用者的 Google Sheet。**
    3. **只在渲染那一段生效。** 全程掛著會影響同進程的其他測試
       （本 repo 的測試會同進程跑上千條）。⇒ **渲染之外的寫入本檔看不見。**

    :returns: 實際換上的 primitive 標籤清單（錨點測試驗的就是這個）。
    """
    _installed: list[str] = []
    _undo: list[tuple[Any, str, Any]] = []

    def _block(owner: Any, attr: str, label: str) -> None:
        _orig = getattr(owner, attr, None)
        if _orig is None:
            return
        try:
            setattr(owner, attr, _make_recorder(trips, label))
        except (AttributeError, TypeError):                  # pragma: no cover
            return                       # 內建型別擋 setattr（例如 C 實作的類別）
        _undo.append((owner, attr, _orig))
        _installed.append(label)

    def _watch_open(owner: Any, attr: str, label: str, mode_pos: int) -> None:
        _orig = getattr(owner, attr, None)
        if _orig is None:                                    # pragma: no cover
            return

        def _watcher(*_a: Any, **_kw: Any) -> Any:
            _mode = _kw.get("mode")
            if _mode is None and len(_a) > mode_pos:
                _mode = _a[mode_pos]
            if any(_c in str(_mode or "r") for _c in _WRITE_MODES):
                trips.append(f"{label}(mode={_mode!r})")
            return _orig(*_a, **_kw)     # ← 刻意放行，理由見 docstring 取捨 1

        try:
            setattr(owner, attr, _watcher)
        except (AttributeError, TypeError):                  # pragma: no cover
            return
        _undo.append((owner, attr, _orig))
        _installed.append(label)

    # ① Google Sheets（gspread）—— 真正打雲端的那一層
    for _cls, _n in _gspread_write_methods():
        _block(_cls, _n, f"gspread.{_cls.__name__}.{_n}")

    # ② 磁碟 —— pathlib / os / shutil
    for _n in ("write_text", "write_bytes", "mkdir", "rmdir", "unlink",
               "rename", "replace", "touch", "symlink_to", "hardlink_to", "chmod"):
        _block(pathlib.Path, _n, f"pathlib.Path.{_n}")
    for _n in ("remove", "unlink", "rename", "replace", "makedirs", "mkdir",
               "rmdir", "removedirs", "truncate"):
        _block(os, _n, f"os.{_n}")
    try:
        import shutil                                        # noqa: PLC0415
        for _n in ("copy", "copy2", "copyfile", "copytree", "move", "rmtree"):
            _block(shutil, _n, f"shutil.{_n}")
    except Exception:                                        # pragma: no cover
        pass

    # ③ 序列化落盤
    for _mod_name in ("json", "pickle"):
        try:
            _mod = importlib.import_module(_mod_name)
        except Exception:                                    # pragma: no cover
            continue
        _block(_mod, "dump", f"{_mod_name}.dump")

    # ④ pandas 落盤
    try:
        import pandas as _pd                                 # noqa: PLC0415
        for _cls in (_pd.DataFrame, _pd.Series):
            for _n in ("to_csv", "to_parquet", "to_json", "to_excel",
                       "to_pickle", "to_feather", "to_hdf", "to_sql"):
                _block(_cls, _n, f"pandas.{_cls.__name__}.{_n}")
    except Exception:                                        # pragma: no cover
        pass

    # ⑤ 原始 HTTP 寫入動詞（繞過 gspread 直接打 Sheets API 也擋得到）
    #    ⚠️ `urllib.request.urlopen` **必須列進來**：本 repo 有真實的家風用它直打 HTTP
    #    （`repositories/fund/sources.py` 的 Yahoo v8 chart 就是 urlopen 直連，
    #    見 `CLAUDE.md §8.3.P` 的 `P-YFDUPE-1`）—— 只守 requests/httpx 會整條漏掉。
    #    判準：`data` 非 None（＝ POST body）或 Request 物件自報寫入動詞才算，
    #    否則一律放行（純 GET 取數不是寫入，攔了會製造偽陽性）。
    try:
        import urllib.request as _urlreq                      # noqa: PLC0415
        _orig_urlopen = _urlreq.urlopen

        def _urlopen(*_a: Any, **_kw: Any) -> Any:
            _data = _kw.get("data") if "data" in _kw else (_a[1] if len(_a) > 1 else None)
            _verb = ""
            _req = _a[0] if _a else _kw.get("url")
            _get_method = getattr(_req, "get_method", None)
            if callable(_get_method):
                try:
                    _verb = str(_get_method()).upper()
                except Exception:                            # pragma: no cover
                    _verb = ""
            if _data is not None or _verb in ("POST", "PUT", "PATCH", "DELETE"):
                trips.append(f"urllib.request.urlopen({_verb or 'data='})")
                # ⚠️ 回**無害的假回應**而不是 `None`：`urlopen` 的回傳值幾乎一定會被
                #    `.read()`／`with` 用掉，回 None 會讓紅燈變成一句
                #    `AttributeError: 'NoneType' object has no attribute 'read'`——
                #    **一樣是紅的（fail-closed），但訊息看不出「這裡有一個寫入」**。
                #    （其餘 primitive 回 `None`，因為它們的回傳值多半沒人用。）
                return _FakeResponse()
            return _orig_urlopen(*_a, **_kw)

        _urlreq.urlopen = _urlopen                            # type: ignore[assignment]
        _undo.append((_urlreq, "urlopen", _orig_urlopen))
        _installed.append("urllib.request.urlopen")
    except Exception:                                        # pragma: no cover
        pass

    for _mod_name, _paths in (("requests", (("Session", "request"),)),
                              ("httpx", (("Client", "request"),
                                         ("AsyncClient", "request")))):
        try:
            _mod = importlib.import_module(_mod_name)
        except Exception:                                    # pragma: no cover
            continue
        for _cls_name, _attr in _paths:
            _cls = getattr(_mod, _cls_name, None)
            if _cls is None:                                 # pragma: no cover
                continue
            _orig_req = getattr(_cls, _attr, None)
            if _orig_req is None:                            # pragma: no cover
                continue

            def _req(*_a: Any, __orig=_orig_req, __lbl=f"{_mod_name}.{_cls_name}.{_attr}",
                     **_kw: Any) -> Any:
                _method = str(_kw.get("method") or (_a[1] if len(_a) > 1 else "")).upper()
                if _method in ("POST", "PUT", "PATCH", "DELETE"):
                    trips.append(f"{__lbl}({_method})")
                    return None          # 寫入動詞：攔下，不真的送出去
                return __orig(*_a, **_kw)

            try:
                setattr(_cls, _attr, _req)
            except (AttributeError, TypeError):              # pragma: no cover
                continue
            _undo.append((_cls, _attr, _orig_req))
            _installed.append(f"{_mod_name}.{_cls_name}.{_attr}")

    # ⑥ 最後才是 open —— 只觀察、不攔截（理由見 docstring 取捨 1）
    #    ⚠️ **`io.open` 必須單獨列一格。** `io.open is builtins.open` 是 `True`
    #    （同一個函式物件），但 **`io` 模組自己持有一份 `open` 屬性**
    #    （實測 `"open" in vars(io)` 為 `True`）—— 只 rebind `builtins.open`
    #    **完全碰不到 `io.open`**，於是 `io.open(path, "w")` 整條漏掉。
    #    2026-09-06 複驗實測：補之前 → 全綠**而且檔案真的被寫出來**。
    #    它也**不在**本檔「看不見」那份例外清單裡（那裡列的是 `sqlite3` / `subprocess` /
    #    原始 socket / fd 級 `os.write` / C 擴充）—— `io.open` 是標準庫最正規的別名，
    #    **不屬於上述任何一類，所以它是漏掉、不是取捨。**
    _watch_open(builtins, "open", "builtins.open", 1)
    _watch_open(io, "open", "io.open", 1)
    _watch_open(pathlib.Path, "open", "pathlib.Path.open", 1)

    try:
        yield _installed
    finally:
        for _owner, _attr, _orig in reversed(_undo):
            try:
                setattr(_owner, _attr, _orig)
            except Exception:                                # pragma: no cover
                pass


def _render_with_sentinels(portfolio: list, monkeypatch, *,
                           extra_session: dict | None = None) -> _Run:
    """裝好**兩層**哨兵 → 渲染整頁 → 回傳完整紀錄。

    兩層是**刻意重疊**的，它們看不見的東西不同（見模組 docstring 的 ①②）：
    **列名槽的別名掃描**擋「已知的寫入函式被接上來」，
    **primitive 哨兵**擋「沒列名、但真的寫下去」。

    ⚠️ **`st` 的替換對象是「掃出來的」不是抄來的**：patch `sys.modules` 裡
    **每一個** module 層帶 `st` 的 `ui.*` 模組。骨架守衛那份是寫死的清單，
    新增一個 `ui.helpers.ia.*` 子模組時它會**靜默漏錄**。
    """
    _tripped: list[str] = []
    _named = _install_named_sentinels(_tripped, monkeypatch)

    # ⚠️ **`deepcopy` 不是保險起見，是一顆存活突變逼出來的。**
    #    初版直接把 module 層的 `RICH_HOLDINGS` **物件本身**塞進 session。突變
    #    「就地竄改使用者持股」(`_z['code'] = 'HACKED'`) 於是把那份**共用 fixture 改掉了**，
    #    後面的快照測試再 deepcopy 時拿到的已經是**被改過的**版本 → 前後一致 → **突變存活**。
    #    單獨跑那條會紅、整檔一起跑就綠 —— **最難發現的那一種假綠燈。**
    _rec = _Rec()
    # ⚠️ 換成 :class:`_SessionDict`（吃屬性存取）—— 理由見該類的 docstring。
    _rec.session_state = _SessionDict()
    _rec.session_state[FOREIGN_CONTRACT_KEY] = copy.deepcopy(portfolio)
    for _k, _v in (extra_session or {}).items():
        _rec.session_state[_k] = copy.deepcopy(_v)

    _targets = [_m for _n, _m in list(sys.modules.items())
                if _n.startswith("ui.") and _m is not None
                and getattr(_m, "st", None) is not None]
    assert _targets, "一個帶 module 層 `st` 的 ui 模組都沒掃到 —— 錄影機沒接上"
    for _m in _targets:
        monkeypatch.setattr(_m, "st", _rec, raising=False)

    # ⚠️ **再補一道：直接換掉 `streamlit.session_state` 本身。**
    #    上面那圈只換得掉「module 層有 `st`」的模組；渲染路徑上**確實有**沒有的
    #    （實測：`ui.helpers.story_nav` 是函式內 `import streamlit as st`）。
    #    那種模組寫進去的東西會流向**真的** session state，前後快照都看不到 ⇒ 全綠放行。
    #    `streamlit.session_state` 是 module 層屬性（實測 `"session_state" in vars(streamlit)`
    #    為 `True`），所以換得掉。
    try:
        import streamlit as _real_st                          # noqa: PLC0415
        monkeypatch.setattr(_real_st, "session_state", _rec.session_state, raising=False)
    except Exception:                                        # pragma: no cover
        pass

    with _primitive_sentinels(_tripped) as _prims:
        render_holdings_health()

    return _Run(tripped=_tripped, named=_named, primitives=_prims,
                session=_rec.session_state)


# ══════════════════════════════════════════════════════════════════════
# 1｜靜態 —— 本頁只准寫自己的命名空間
# ══════════════════════════════════════════════════════════════════════
def test_the_prefix_separates_our_keys_from_the_foreign_contract_key():
    """錨點：:data:`OWN_PREFIX` 必須**同時**做到兩件事。

    ⚠️ **初版只驗了第一件（「有沒有對到自己的鍵」），所以它是循環的、殺不死突變**：
    ``OWN_PREFIX = ""`` 之下，`_own_key_literals()` 是用 `OWN_PREFIX` 篩出來的 ⇒
    什麼都算「自有」⇒ 靜態守衛什麼都放行，而初版那條錨點**照樣綠**。
    現在補上第二件 —— **前綴不得涵蓋別人的契約鍵** —— ``""`` 於是當場紅。

    ⚠️ 而且斷言的對象是 :func:`_own_key_literals`（**下面那條測試真正在用的那個物件**），
    不是同檔上方重新宣告一次的常數。
    """
    from ui.views import page_02_health as _mod
    assert OWN_PREFIX, "`OWN_PREFIX` 是空字串 —— 那會讓每一個鍵都算『自有』，守衛全面失效"

    # ① 前綴要真的涵蓋本頁自己的鍵
    assert _mod._SK_APPLIED.startswith(OWN_PREFIX), (
        f"`OWN_PREFIX = {OWN_PREFIX!r}` 對不上本頁自有鍵 {_mod._SK_APPLIED!r}")
    # ② 前綴**絕不**能涵蓋別人的契約鍵
    assert not _mod._SK_PORTFOLIO.startswith(OWN_PREFIX), (
        f"`OWN_PREFIX = {OWN_PREFIX!r}` 把別人的契約鍵 {_mod._SK_PORTFOLIO!r} 也算成自有 —— "
        "那一刻起「清空使用者持股」會被靜態守衛放行。")
    # ③ 真正在用的那個集合，兩邊都要對
    _own = _own_key_literals()
    assert _mod._SK_APPLIED in _own, f"自有鍵集合漏了 {_mod._SK_APPLIED!r}：{sorted(_own)}"
    assert _mod._SK_PORTFOLIO not in _own, (
        f"自有鍵集合混進了別人的鍵 {_mod._SK_PORTFOLIO!r}：{sorted(_own)}")


def test_the_page_only_writes_its_own_session_namespace():
    """⛔ 本頁的每一處 session 寫入，都必須落在 `v02_health_*`。

    走 `tests/_ast_bindings.py::session_writes`，本檔不自己寫第五份掃描器。

    ⚠️ **誠實地講清楚這裡實際有幾條管道在作用**（初版寫「四條管道」，**半真**）：
    `session_writes` 本身認四條（下標賦值／屬性賦值／`update()`／widget `key=`），
    但本條傳的是 ``widget_key_names=_own`` ⇒ **管道 4 只可能命中自有鍵**，
    而自有鍵一定通過下面那個文字檢查 ⇒ **管道 4 在本條裡零偵測力**。
    ⇒ **本條實際發揮作用的是前三條。** 管道 4 的對象另立
    :func:`test_no_widget_hijacks_a_foreign_session_contract_key`。
    （為什麼不乾脆傳 ``None``：那會把每一個帶 `key=` 的合法 widget 都判成違規，
    見 `_ast_bindings.session_writes` 的 ``widget_key_names`` 長註。）

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


def test_no_widget_hijacks_a_foreign_session_contract_key():
    """⛔ 沒有任何 widget 的 `key=` 指向**別人的**契約鍵。

    這條讓 `session_writes` 的**管道 4** 真的有對象（見上一條的說明）。
    它為什麼是真違規：**streamlit 會代呼叫端把 widget 的值寫進 `session_state`** ——
    ``st.checkbox(..., key="portfolio_funds")`` 會**直接蓋掉使用者的持股**，
    而 AST 上它只是一個普通 `ast.Call`，任何「找賦值節點」的手段都收不到。

    ⚠️ **本條不會偽陽性**：它只在 `key=` 指到 :func:`_foreign_key_names` 裡那幾個
    **具名的別人契約鍵**時才命中；合法的 `key="隨便一個本頁 UI 鍵"` 完全不受影響
    （實測：本頁目前 `key=` 命中數為 0，量測日 2026-09-06）。
    """
    _foreign = _foreign_key_names()
    assert _foreign, "外來鍵集合是空的 —— 本條會對著空集合成立"
    _tree = _page_tree()
    _bad: list[str] = []
    for _fn in ast.walk(_tree):
        if not isinstance(_fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for _w in session_writes(_fn, widget_key_names=_foreign):
            _txt = ast.unparse(_w)
            if any(_f in _txt for _f in _foreign):
                _bad.append(f"{_fn.name}() 第 {_w.lineno} 行：{_txt[:120]}")
    assert not _bad, (
        "本頁有 widget／寫入指向**別人的** session 契約鍵：\n  " + "\n  ".join(_bad)
        + f"\n別人的鍵：{sorted(_foreign)}。streamlit 會拿 widget 值蓋掉它。")


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
@pytest.mark.parametrize("branch,portfolio", [
    ("有持倉", "RICH"),
    ("空持倉", "EMPTY"),
])
def test_rendering_the_page_touches_no_write_sink(branch, portfolio, monkeypatch):
    """⛔ 整頁渲染一輪，**一個寫入槽都不准被呼叫到**。

    ⚠️ **兩條分支都要跑，這是稽核 M10 逼出來的**：`render_holdings_health()` 在
    `if not _holdings():` 之後就 `return`，所以**空持倉**那一條走的是完全不同的路
    （`_render_no_holdings()`）。初版只用 `RICH_HOLDINGS` 渲染一次 ⇒
    **把寫入藏在空狀態分支裡不會紅**（稽核 M10 實測存活）。

    **突變驗證（2026-09-06 回修輪實跑，逐條指令與逐字輸出存檔於本輪 PR）**：

    ==== =============================================== ============= ========= =========
    #    突變                                             哪一層接住     初版      本輪
    ==== =============================================== ============= ========= =========
    M1   模組級 ``from ... import record_batch_nav_points`` 別名掃描      **全綠**  轉紅
         ＋ 呼叫（**本 repo 家風寫法**）
    M2   ``import ... as _nhh`` ＋ ``_nhh.record_...([])``  別名掃描      轉紅      轉紅
    M3   ``Path("/tmp/x").write_text(...)``                名字掃描 ※    **全綠**  轉紅
    M4   ``open("/tmp/x", "w")``                           primitive     **全綠**  轉紅
    M5   ``gspread.Worksheet.append_rows(...)``            名字掃描 ※    崩潰紅 ✱  轉紅
    M6   ``getattr(p, "write" + "_text")(...)``            **primitive** **全綠**  轉紅
         （動態組名，名字掃描**看不到**）
    M7   ``getattr(ws, "append" + "_rows")(...)``          **primitive** **全綠**  轉紅
    M8   ``json.dump(...)``（``dump`` 刻意不在名字字表）     **primitive** **全綠**  轉紅
    M9   ``requests.post(...)``（繞過 gspread 直打 API）    **primitive** **全綠**  轉紅
    M10  把寫入藏在**空持倉**分支                           兩層皆可      **全綠**  轉紅
    M11  ``st.session_state["portfolio_funds"] = []``      靜態          轉紅      轉紅
    M12  ``urllib.request.urlopen(url, data=...)``         **primitive** **全綠**  轉紅
    M13  ``urlopen(Request(..., method="DELETE"))``        **primitive** **全綠**  轉紅
    M14  同 M12，但打**本機 200 伺服器**（見下）             **primitive** **全綠**  轉紅
    M15  寫入放在 **`safe_section` 包住的區塊**裡           別名掃描      **全綠**  轉紅
         （見下方 ⛨ —— 這一顆是「記名 vs 拋例外」的對照組）
    ==== =============================================== ============= ========= =========

    ※ **M3／M5 是被「名字掃描」接住的，不是 primitive** —— 它們把一個**列名** primitive
    直接寫進被測頁，於是 :func:`_sink_targets` 掃到 ``render_holdings_health`` 自己、
    把整個 render 換成哨兵。**結果仍然 fail-closed（渲染沒跑 ⇒ 什麼都沒驗 ⇒ 但哨兵記了一筆 ⇒ 紅）**，
    只是訊息會指向 ``render_holdings_health`` 而不是那個 primitive。
    **M6／M7 是同樣的寫入、改成動態組名**，名字掃描完全看不到 —— 它們才是 primitive 那一層的單獨證明。
    ✱ M5 在初版也是紅的，但那是**未初始化的 `Worksheet` 自己 AttributeError 崩掉**，
    **不是守衛接住的** —— 意外的紅不是保證。

    ⚑ **M14 是 `urlopen` 那條的乾淨證明。** M12／M13 打的是外部 URL，**舊版之所以紅是因為
    遠端回了 400／DNS 失敗**（意外的紅，不是守衛接住的 —— 而且那代表**請求真的送出去了**）。
    M14 改打一個本機回 200 的伺服器：**舊版 11 passed 全綠**（寫入送出去了，沒人吭聲）、
    新版轉紅並印出 ``urllib.request.urlopen(data=)``。
    ⚠️ 本 repo 有真實的 `urlopen` 直連家風（`repositories/fund/sources.py` 的 Yahoo v8 chart），
    **只守 requests／httpx 會整條漏掉**。

    ⛨ **M15 證明「哨兵必須記名、不准 raise」不是風格偏好**（見 :func:`_make_recorder`）：
    同一顆突變（寫入放在 `safe_section` 包住的區塊裡），
    **記名版 → 紅**（訊息指名 `record_batch_nav_points`）、
    **改成 `raise` 版 → 2 passed 全綠**（例外被 `safe_section` 吃掉）。
    ⇒ **在這一頁上，一個會 raise 的哨兵等於沒有哨兵。**

    **初版全綠的那十二顆（M1／M3／M4／M6～M10／M12～M15）就是本輪賺回來的保證。**
    """
    _run = _render_with_sentinels(
        RICH_HOLDINGS if portfolio == "RICH" else [], monkeypatch)
    assert not _run.tripped, (
        f"本頁渲染（{branch}分支）時碰到了寫入槽："
        + ", ".join(sorted(set(_run.tripped)))
        + "\n總管 2026-09-06 裁決（讀法甲）：② **零寫入**。"
          "在 `nav_history` 涵蓋範圍調查有結論之前，**不得**新增任何寫使用者 Google Sheet 的路徑。")


def test_the_sentinel_machine_really_installed_itself(monkeypatch):
    """錨點：**驗真的裝上去的那台機器**，不是驗同檔上方的常數 tuple。

    ⚠️ **初版這條錨點是壞的，而且壞得很典型**：它斷言
    ``("ui.helpers.nav_history_hook", "record_batch_nav_points") in _sink_targets()``——
    而那一項就寫死在 :data:`_ALWAYS_SENTINEL` 裡。
    **安裝迴圈整個癱瘓、一個哨兵都沒真的裝上，它照樣綠**（稽核 A3-4 實測）。
    「錨點」的意義是「上面那條斷言不是對著空集合成立的」——
    所以它必須驗 :class:`_Run` 回報的**實際安裝結果**。

    三件事一起驗（缺一條就會有一種癱瘓方式漏網）：

    1. **列名哨兵真的裝上了**，而且涵蓋舊 ② 唯一的雲端寫入入口；
    2. **primitive 哨兵真的裝上了**，而且涵蓋 gspread 的 `append_rows` 與 `Path.write_text`；
    3. **裝上去的哨兵是活的** —— 直接呼叫它，會被記一筆（＝它真的取代了原函式）。
    """
    _run = _render_with_sentinels(RICH_HOLDINGS, monkeypatch)

    # 1｜列名哨兵
    assert _run.named, "一個列名哨兵都沒裝上 —— 零寫入斷言會對著空集合成立"
    assert any(_t.endswith(".record_batch_nav_points") for _t in _run.named), (
        "列名哨兵沒有涵蓋舊 ② 唯一的雲端寫入入口 `record_batch_nav_points`：\n  "
        + "\n  ".join(_run.named))
    assert any(_t.endswith(".append_points") for _t in _run.named), (
        "列名哨兵沒有涵蓋 `append_points`（真正打 Google Sheets 的那一層）。")

    # 2｜primitive 哨兵
    assert "gspread.Worksheet.append_rows" in _run.primitives, (
        f"primitive 哨兵沒守住 gspread 的 `append_rows`：{_run.primitives[:20]}")
    assert "pathlib.Path.write_text" in _run.primitives, (
        f"primitive 哨兵沒守住 `Path.write_text`：{_run.primitives[:20]}")
    assert "builtins.open" in _run.primitives, (
        f"primitive 哨兵沒守住 `open`：{_run.primitives[:20]}")

    # 3｜裝上去的是活的（monkeypatch 在本測試結束前都還沒還原）
    import ui.helpers.nav_history_hook as _hook
    _tripped_before = len(_run.tripped)
    _hook.record_batch_nav_points([])
    assert len(_run.tripped) == _tripped_before + 1, (
        "直接呼叫 `record_batch_nav_points` 沒有被記到 —— 哨兵沒有真的取代原函式，"
        "上面那些「已安裝」的回報是假的。")


def test_the_alias_sweep_catches_the_house_style_import(monkeypatch):
    """⭐ 錨點 —— **這條專門釘住本輪最重要的那個修正**，改壞它會當場紅。

    本 repo 的家風寫法是 ``from m import f``，它在 import 當下就把**函式物件**
    綁進消費模組的命名空間。初版 patch 的是**來源模組的屬性**，
    因此**完全碰不到**那個已經綁好的物件（稽核實測：接上去 7 passed 全綠）。

    本條造一個**假的消費模組**、照家風把物件綁進去，再跑一次安裝，
    斷言那個別名**也被換掉了**。
    ⇒ 若有人把 :func:`_install_named_sentinels` 改回 ``setattr(來源模組, 名字, 哨兵)``，
      本條立刻轉紅，**不必等到有人真的把寫入接上新頁才發現**。
    """
    import types
    import ui.helpers.nav_history_hook as _hook

    _orig = _hook.record_batch_nav_points
    _fake = types.ModuleType("wf02_house_style_consumer")
    # ↓ 這一行就是家風寫法在 import 之後留下的東西
    _fake.record_batch_nav_points = _orig
    monkeypatch.setitem(sys.modules, "wf02_house_style_consumer", _fake)

    _trips: list[str] = []
    _installed = _install_named_sentinels(_trips, monkeypatch)

    assert _fake.record_batch_nav_points is not _orig, (
        "別名掃描沒有換掉消費模組裡的 `record_batch_nav_points` —— "
        "`from m import f` 這種家風寫法會整個逃過哨兵，"
        "而那正是本檔初版最大的洞（稽核實測：接上去 7 passed 全綠）。")
    assert "wf02_house_style_consumer.record_batch_nav_points" in _installed, (
        f"安裝回報漏了那個別名：{_installed}")

    _fake.record_batch_nav_points([])
    assert _trips, "換上去的別名不是活哨兵 —— 呼叫它沒有被記到"


# ══════════════════════════════════════════════════════════════════════
# 3｜行為 —— 渲染前後，別人的 session 鍵一個都不准動
# ══════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("branch,portfolio", [
    ("有持倉", "RICH"),
    ("空持倉", "EMPTY"),
])
def test_rendering_the_page_leaves_every_foreign_session_key_alone(
        branch, portfolio, monkeypatch):
    """⛔ 渲染一輪之後，**不屬於本頁命名空間**的 session 鍵必須完全沒動。

    比對的是**增／減／變值**三種 —— 只驗「有沒有新鍵」會漏掉
    「就地改掉 `portfolio_funds` 的內容」這種最貴的一種（使用者的持股被改掉）。

    ⚠️ **空持倉那一條同樣要跑**（理由同 :func:`test_rendering_the_page_touches_no_write_sink`）。

    **突變驗證（實跑）**：在 `_holdings()` 內加
    `st.session_state["portfolio_funds"] = []` → 轉紅（`portfolio_funds` 變值）。
    """
    _extra = {
        "policy_v2_cache": {"P1": {"invest_twd": 123}},
        "_nav_hist_written": set(),
    }
    _seed_portfolio = RICH_HOLDINGS if portfolio == "RICH" else []
    _before = copy.deepcopy(
        {FOREIGN_CONTRACT_KEY: _seed_portfolio, **_extra})

    _run = _render_with_sentinels(_seed_portfolio, monkeypatch, extra_session=_extra)

    _after = {_k: _v for _k, _v in _run.session.items()
              if not _k.startswith(OWN_PREFIX)}
    _added = sorted(set(_after) - set(_before))
    _removed = sorted(set(_before) - set(_after))
    _changed = sorted(_k for _k in set(_before) & set(_after)
                      if _after[_k] != _before[_k])
    assert not (_added or _removed or _changed), (
        f"渲染（{branch}分支）動到了別人的 session 鍵 —— "
        f"新增 {_added}／消失 {_removed}／變值 {_changed}\n"
        f"本頁只准動 `{OWN_PREFIX}*`。")


def test_the_foreign_key_snapshot_actually_has_something_to_protect():
    """錨點：上面那條的 `_before` 不得是空的。

    空快照 ＝ 「沒有任何外來鍵被改到」恆真 —— 又一個「斷言做在空集合上」的形狀。
    ⚠️ 這條同時是 :data:`OWN_PREFIX` 的第二道保險：``OWN_PREFIX = ""`` 之下
    每一個鍵都會被當成「自己的」而濾掉 ⇒ 外來鍵集合變空 ⇒ 本條轉紅。
    """
    _rec = _Rec()
    _rec.session_state[FOREIGN_CONTRACT_KEY] = copy.deepcopy(RICH_HOLDINGS)
    _rec.session_state["policy_v2_cache"] = {"P1": {"invest_twd": 123}}
    _foreign = {_k for _k in _rec.session_state if not _k.startswith(OWN_PREFIX)}
    assert len(_foreign) >= 2, (
        f"外來鍵快照只有 {_foreign} —— 保護對象太少，突變殺不死這條守衛")
