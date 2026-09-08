"""④「📈 組合績效追蹤」的**零寫入**守衛 —— 渲染不得動客戶的 Google Sheet。

客戶 2026-09-06 永久授權（逐字）
--------------------------------
> 「凡是『查詢/搜尋』功能，一律強制走純讀取（唯讀），**絕對禁止反向寫入我的 Google Sheet**。
>   不用問我，直接切斷寫入！」

本檔守的是那道「切斷」真的成立，而且**在兩個不同的位置各切一次**：

===== ================================================ ==========================================
①     `render_portfolio_tracking()` 渲染時**零寫入**    寫入只能發生在快照按鈕的 `if` 正分支
②     `load_snapshots()` 這條**讀**路徑零寫入            分頁不存在／表頭不符 → raise，不就地補建
===== ================================================ ==========================================


修這件事之前它長什麼樣（2026-09-06 離線實測，逐字紀錄，不是推測）
------------------------------------------------------------------
**① 渲染即寫。** `render_portfolio_tracking()` 無條件呼叫 `_maybe_snapshot()`，
唯一的閘門是 `st.session_state["_perf_snapshot_done"]`：

    按下的按鈕：0 顆        送出的 `ws.append_row`：1 筆

而那**不是壞掉的判斷，是當時刻意的設計** —— 舊 caption 自己寫著「每次開啟本區自動存一筆」。
所以要擋的不是一個 bug，是一個**設計**：任何把「自動」寫回來的改動都必須在這裡撞牆。

⛔ **session 旗標不是修法**（:func:`test_the_session_flag_is_not_a_write_gate` 就是為它存在的）：
它只把「每個 session 寫一次」變成「少寫幾次」，寫入依然發生在使用者沒有表達任何意圖的時候。
**少寫幾次不叫切斷。**

**② 名字是讀、實際會寫。** `load_snapshots()` → `_ws()` → 分頁不存在時
`add_worksheet` + `update("A1", …)` **兩筆寫入，藏在兩層底下**；分頁在、表頭不符時 `update("A1", …)` 一筆。
它**只在遠端狀態不符預期時才發作** —— 也就是本機測不到、看起來最像「它不會寫」的那一種。


這道守衛看得見什麼、看不見什麼（照實寫，不要讀成「守死了」）
------------------------------------------------------------
**看得見**

* **任何**打到試算表物件上的寫入 —— :class:`_DenyByDefaultWorksheet` 是**預設拒絕**的：
  只有 :data:`_PURE_READERS` 列出的純讀方法會放行，**其餘一律記成寫入**。
  ⇒ gspread 哪天多一個新的寫入方法、或有人改用 `batch_update` / `values_append`，
  **不必有人記得把它加進任何清單**就會被算到。這是本檔刻意不用「寫入方法名白名單」的理由：
  白名單漏一個名字就等於漏守，而名字清單永遠不會窮舉。
* **磁碟** —— `pathlib.Path.write_text/write_bytes/mkdir/touch/unlink`、`os.makedirs/mkdir/remove`
  在渲染那一小段被換成記名哨兵（本地 JSON 後端那一路）。
* **跨函式／動態呼叫** —— 上面兩層都是**行為**測試，渲染真的跑一輪；
  不管呼叫端怎麼 import、取什麼別名，只要真的動到就會撞上。
  ⇒ 這正是~~本檔~~ **行為層**（**2026-09-07 更正措辭，見下一則**）**不**做 `import` 來源白名單、
  也**不**比對函式名的原因：
  `from m import f as _g` / `importlib.import_module("a."+"b")` / `g = m.f` 再 `g()` / `getattr`
  這四種寫法在本 repo 都實測繞得過名字型守衛，但**繞不過「真的被呼叫到」**。
* **靜態層的別名、與「把寫入當值傳出去」** —— §7 的結構規則（:func:`_refs`）**2026-09-07**
  把命中條件由「只走 `ast.Call`、只比對字面名字」放寬為「**呼叫 ＋ 裸參照**」，並補上別名解析
  （import 別名／賦值別名做到不動點）。放寬前這兩種在靜態層是**全綠**的（當日實測）：

      _f = _sv ; _f(None)                     # 別名規避
      _with_quota_retry(ws.update, "A1", [])  # 當引數傳給包裝器（`ast.Attribute` 不是 `ast.Call`）

  ⚠️ 上一則原本寫「**本檔**不比對函式名」—— 那句話**對 §7 從來就不精確**（§7 一直在比對名字），
  2026-09-07 之後更不精確，故把主詞縮回**行為層**。**它想講的事沒有變**：
  行為層之所以擋得住，正是因為它不靠名字。

**看不見（已知缺口，不要當成保證）**

* **哨兵只在渲染那一小段生命週期內生效**；渲染之外的寫入本檔看不到。
* **靜態層看不到的，遠不只「執行期才拼出來的名字」** —— 本則 **2026-09-07 就地更正**
  （**有意識的更正，不是漏刪** · 日期 **2026-09-07** ·
  決策者：**AI 總管（依獨立稽核實測）**）。

  ~~⛔ 不要把 2026-09-07 那次放寬讀成「靜態層守得住了」—— 它補的是~~
  ~~「**名字寫得出來、只是換了個寫法**」那兩種，補不到「**名字根本不在原始碼裡**」。~~

  → **這條界線畫錯了。** ⚠️ 被推翻的是「**補上了多少**」這個**射程宣稱**，
  **不是修復本身** —— :func:`_refs` 的兩種繞道確實補起來了，:func:`_bindings`
  也真的解得開別名（:func:`test_bypass_1_alias_then_call_is_caught` /
  :func:`test_bypass_2_passed_as_an_argument_is_caught` 仍然有效）。
  錯的是把殘餘缺口說成**只剩**「動態組出的名字」。
  **舊敘述的用意仍然成立**（提醒讀者靜態層有邊界）；
  **被權衡掉的是它把那道邊界畫得太窄** —— 窄到會讓後人以為靜態層已經接近守得住。

  **實際補上的只有兩種綁定形狀**：**import 別名**（`from m import f as _g`）
  與**單目標賦值別名**（`_g = f` / `_g = ws.update`）。

  **下列六種，名字完整寫在原始碼裡、全是普通 Python，靜態層一樣看不到**
  （2026-09-07 逐一實跑，正對照 `_d = append_snapshot` 必須命中 ⇒ 規則是活的）：

      _a, _b = append_snapshot, 1                # ① tuple 解包
      _p = _q = append_snapshot                  # ② 鏈式賦值
      [_c] = [append_snapshot]                   # ③ list 解包
      _T = {"w": append_snapshot}                # ④ 容器承載 → _T["w"](None)
      _pf = functools.partial(append_snapshot)   # ⑤ 值是 Call
      getattr(ws, "update")("A1", [])            # ⑥ 字面字串，一點都不「動態組出」

  **根因分三種，不要混為一談**（2026-09-07 實測 AST 節點形狀）：
  ①②③ 敗在 :func:`_bindings` 只認 **`len(targets) == 1` 且 target 是 `ast.Name`**
  （①③ 的 target 是 `Tuple`／`List`，② 的 `len(targets)` 是 2）——
  **這一條從來沒有被寫下來過**，舊敘述描述的是**值**的形狀，沒描述**目標**的形狀；
  ④⑤ 敗在值不是裸 `Name`／`Attribute`（`Dict`／`Call`）——
  **這一條 :func:`_bindings` 的 ④ 已經寫了**，是刻意的取捨，不是新發現；
  ⑥ 敗在 `"update"` 是 `ast.Constant`，**從頭到尾不存在可比對的 `Name`／`Attribute` 節點**。

  ⚠️ **限定條件，不要往另一個方向誇大**：①~⑤ **只有在別名建在被掃節點之外**
  （模組層／別的函式）才逃得掉；建在被掃函式**之內**時，右側那個 `append_snapshot`
  仍會以 `ref` 命中（同日實測五種全中）。
  **⑥ 沒有這個限定 —— 它逃得掉與位置無關。**

  ⚠️ **原本點名的 `getattr(o, "a"+"b")` 與 `importlib.import_module("a."+"b")`
  依然看不到** —— 舊敘述沒有講錯它們，只是**把清單講短了**。

  ✅ **縱深防禦沒破（實測，不是推論）**：上列六種 ＋ 執行期拼名
  （`getattr(ws, "up" + "date")`）共七種，**在行為層逐一實跑，七種全部被
  :class:`_DenyByDefaultWorksheet` 記成寫入**；負對照 `get_all_values()` 靜默通過，
  證明哨兵不是「什麼都記」。

  ⛔ **不得以「靜態層有守」為由簡化、放寬或刪除行為層哨兵。**
  靜態層是 **code review 的輔助**，**不是**這條保證的承載者 ——
  上面六種形態證明它看不見的東西**遠多於**「動態組出的名字」。
  **真正擋住寫入的是行為層。**
  （此即憲法 §8.3.P `P-CALLSTATIC-1` 待答二選一的**後者**：
  2026-09-07 那批做了前者〔補靜態層〕卻只寫了較軟的「不要讀成守得住了」，
  本則補上後者〔明訂它只是輔助，並寫死這條禁令〕。）
  ⚠️ 對照 `tests/test_readonly_query_paths.py`（#796）：那一支守的是**沒有行為層可靠**的讀路徑，
  所以它多做一件事 —— 把整個形狀禁掉（`_dynamic_backdoors`）。
  **本檔刻意不照抄那一招**：這裡的動態寫法有行為層真的擋得住，
  再加一條形狀禁令只會禁到無辜的 `getattr`，而擋不到任何本檔擋不住的東西。
* **`_DenyByDefaultWorksheet` 只擋「經過這個假件」的寫入**。若有人繞過
  `get_perf_store()`／`_sh`、自己另開一個 gspread client，本檔的假件根本不在那條路上。
  磁碟哨兵沒有這個問題（它換的是 `pathlib` / `os` 本身）。
* **本檔不驗數字對不對** —— `services.portfolio_tracking` 是被替身頂掉的（見
  :func:`_collaborators`），本檔只問「有沒有寫」，走勢與指標的正確性由
  `tests/test_portfolio_tracking.py` 守。
* **哨兵一律「記名」不「拋例外」**：拋例外會被上層 `try/except` 吃掉，
  變成一個看起來很嚴格、實際上什麼都擋不住的守衛（本 repo 已有實證）。記名 + 事後斷言才擋得住。
"""
from __future__ import annotations

import ast
import builtins
import contextlib
import importlib
import importlib.machinery
import importlib.util
import os
import pathlib
import sys
import types
from typing import Any, Callable, Iterator

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:                       # 允許本檔在 `tests/` 之外被複製執行
    sys.path.insert(0, str(ROOT))

SECTION_REL = "ui/helpers/fund_grp_health/switch_advisor_section.py"
REPO_REL = "repositories/portfolio_perf_repository.py"


# ══════════════════════════════════════════════════════════════════════
# 0｜相依前置：真的有就用真的，沒有才用替身（替身絕不覆蓋真模組）
# ══════════════════════════════════════════════════════════════════════
def _install_stub_if_absent(name: str, build: "Callable[[], types.ModuleType]") -> bool:
    """`name` 匯入不到時才塞替身。回傳 True = 用了替身。

    ⚠️ **順序很重要**：`streamlit` 是 `switch_advisor_section` 的 module 層 import，
    不先備好連 import 都過不了。但**有真的就一定要用真的** —— 一個會覆蓋真模組的替身，
    會讓這道守衛在 CI 上量的是替身而不是產品。:func:`test_stubs_never_shadow_the_real_thing`
    就是在釘這件事。
    """
    if name in sys.modules or importlib.util.find_spec(name) is not None:
        return False
    sys.modules[name] = build()
    return True


def _build_streamlit_stub() -> types.ModuleType:
    mod = types.ModuleType("streamlit")

    class _SS(dict):
        def __getattr__(self, k: str) -> Any:
            try:
                return self[k]
            except KeyError:
                raise AttributeError(k) from None

        def __setattr__(self, k: str, v: Any) -> None:
            self[k] = v

    def _noop(*_a: Any, **_k: Any) -> None:
        return None

    def _cache(*a: Any, **_k: Any) -> Any:
        return a[0] if a and callable(a[0]) else (lambda f: f)

    mod.session_state = _SS()
    for _n in ("markdown", "caption", "info", "warning", "error", "success", "write",
               "line_chart", "divider", "subheader", "dataframe", "metric", "button",
               "columns", "container", "expander", "spinner", "form", "form_submit_button"):
        setattr(mod, _n, _noop)
    mod.cache_data = mod.cache_resource = _cache
    mod.secrets = {}
    return mod


def _build_pandas_stub() -> types.ModuleType:
    mod = types.ModuleType("pandas")

    class _DataFrame:
        def __init__(self, *_a: Any, **_k: Any) -> None:
            pass

        def dropna(self) -> "_DataFrame":
            return self

        def __len__(self) -> int:
            return 0

    mod.DataFrame = _DataFrame
    return mod


#: 哪些相依是用替身頂上的（本機沒裝 streamlit / pandas 時）。CI 上應為空。
STUBBED: dict[str, bool] = {
    "streamlit": _install_stub_if_absent("streamlit", _build_streamlit_stub),
    "pandas": _install_stub_if_absent("pandas", _build_pandas_stub),
}

import repositories.portfolio_perf_repository as PR            # noqa: E402
from repositories.portfolio_perf_repository import (           # noqa: E402
    _HEADERS,
    GoogleSheetsPerfStore,
    LocalJsonPerfStore,
    PerfSnapshot,
    SheetNotProvisioned,
)

SECTION = importlib.import_module("ui.helpers.fund_grp_health.switch_advisor_section")


# ══════════════════════════════════════════════════════════════════════
# 1｜預設拒絕的假試算表 —— 本檔的核心，刻意不是「寫入方法名白名單」
# ══════════════════════════════════════════════════════════════════════
#: gspread worksheet 上**確定不改動內容**的方法。**只有這幾個放行。**
#:
#: ⛔ 往這裡加名字之前先想清楚：加錯一個，這道守衛對那個方法就永遠瞎了。
#: 反過來，**漏加一個純讀方法只會讓測試紅**（偽陽性，會被立刻發現），
#: 而漏加一個寫入方法在白名單式守衛裡是**靜默放行**（永遠不會被發現）。
#: 這個不對稱就是選「預設拒絕」的全部理由。
_PURE_READERS = frozenset({
    "get_all_values", "get_all_records", "get_values", "get", "row_values", "col_values",
    "cell", "acell", "find", "findall", "get_note", "get_notes",
    "title", "id", "row_count", "col_count", "url",
})


class _DenyByDefaultWorksheet:
    """假 worksheet：純讀方法照常回值，**其餘一律記成寫入**。

    這不是「攔截已知的寫入方法」，是「**放行已知的讀方法**」——
    兩者在漏列一個名字時的行為正好相反（見 :data:`_PURE_READERS`）。
    """

    def __init__(self, rows: "list[list[str]]", trips: list[str]) -> None:
        self._rows = [list(r) for r in rows]
        self._trips = trips

    # ── 放行的純讀 ───────────────────────────────────────────
    def get_all_values(self) -> "list[list[str]]":
        return [list(r) for r in self._rows]

    def row_values(self, n: int) -> "list[str]":
        return list(self._rows[n - 1]) if len(self._rows) >= n else []

    # ── 其餘一律視為寫入 ─────────────────────────────────────
    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)

        def _recorder(*_a: Any, **_k: Any) -> None:
            self._trips.append(f"worksheet.{name}")
        return _recorder


class _DenyByDefaultSpreadsheet:
    """假 spreadsheet：`worksheet()` 是讀；`add_worksheet()` 等一律記成寫入。"""

    def __init__(self, ws: "_DenyByDefaultWorksheet | None", trips: list[str]) -> None:
        self._ws, self._trips = ws, trips

    def worksheet(self, title: str) -> "_DenyByDefaultWorksheet":
        if self._ws is None:
            raise Exception(f"WorksheetNotFound: {title}（離線假件，未連任何真表）")
        return self._ws

    def add_worksheet(self, **_k: Any) -> "_DenyByDefaultWorksheet":
        self._trips.append("spreadsheet.add_worksheet")
        self._ws = self._ws or _DenyByDefaultWorksheet([], self._trips)
        return self._ws

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)

        def _recorder(*_a: Any, **_k: Any) -> None:
            self._trips.append(f"spreadsheet.{name}")
        return _recorder


def _gs_store(rows: "list[list[str]] | None", trips: list[str]) -> GoogleSheetsPerfStore:
    """接上假件的 GS 後端。`rows=None` ＝ 遠端還沒有這個分頁。

    ⚠️ 只塞 `_sh`（已開好的試算表），**不碰 `_ws` / `_ws_for_write`** ——
    那兩個正是本批要驗的東西，patch 掉就變成自己驗自己。
    """
    store = GoogleSheetsPerfStore()
    store._sh = _DenyByDefaultSpreadsheet(
        None if rows is None else _DenyByDefaultWorksheet(rows, trips), trips)
    return store


# ══════════════════════════════════════════════════════════════════════
# 2｜磁碟哨兵（本地 JSON 後端那一路）
# ══════════════════════════════════════════════════════════════════════
_WRITE_MODES = "wxa+"


def _make_recorder(trips: list[str], tag: str) -> Callable[..., None]:
    """記名、**不拋例外**的哨兵。

    ⛔ 不要改成 `raise`：被測路徑外面包著 `try/except Exception` （誠實提示用），
    會 raise 的哨兵只會被吃掉，然後這道守衛變成永遠綠燈。
    """
    def _sentinel(*_a: Any, **_k: Any) -> None:
        trips.append(tag)
    return _sentinel


@contextlib.contextmanager
def _disk_sentinels(trips: list[str]) -> "Iterator[list[str]]":
    """把磁碟寫入 primitive 換成哨兵，只在 `with` 這一小段。

    ⚠️ `builtins.open` 是**觀察不是攔截**：全域攔截會把 pytest / importlib 的
    合法讀檔一起打死。只在 mode 含 `w`/`x`/`a`/`+` 時記一筆，然後放行。
    ⇒ 真的踩到時檔案會被寫出去，本檔保證的是**當場轉紅**，不是「沒發生」。
    """
    installed: list[str] = []
    undo: list[tuple[Any, str, Any]] = []

    def _block(owner: Any, attr: str, label: str) -> None:
        orig = getattr(owner, attr, None)
        if orig is None:
            return
        try:
            setattr(owner, attr, _make_recorder(trips, label))
        except (AttributeError, TypeError):                  # pragma: no cover
            return
        undo.append((owner, attr, orig))
        installed.append(label)

    for _n in ("write_text", "write_bytes", "mkdir", "touch", "unlink", "rename", "replace"):
        _block(pathlib.Path, _n, f"pathlib.Path.{_n}")
    for _n in ("makedirs", "mkdir", "remove", "unlink", "rename", "replace"):
        _block(os, _n, f"os.{_n}")

    _orig_open = builtins.open

    def _watch_open(*a: Any, **k: Any) -> Any:
        mode = k.get("mode") if "mode" in k else (a[1] if len(a) > 1 else "r")
        if any(c in str(mode or "r") for c in _WRITE_MODES):
            trips.append(f"builtins.open(mode={mode!r})")
        return _orig_open(*a, **k)

    builtins.open = _watch_open                              # type: ignore[assignment]
    undo.append((builtins, "open", _orig_open))
    installed.append("builtins.open")
    try:
        yield installed
    finally:
        for owner, attr, orig in reversed(undo):
            setattr(owner, attr, orig)


# ══════════════════════════════════════════════════════════════════════
# 3｜渲染用的錄影機 + 協作模組替身
# ══════════════════════════════════════════════════════════════════════
_ROW = {
    "date": "2026-09-06", "period_return_pct": 1.23, "cagr_pct": None, "ann_vol_pct": None,
    "sharpe": None, "max_drawdown_pct": -2.0, "n_funds": 2, "total_cost_twd": 1000.0,
    "is_equal_weight": False, "weights_hash": "h", "weights_json": "{}",
    "coverage_start": "2026-08-01", "coverage_end": "2026-09-06", "n_days": 20,
    "recorded_at": "2026-09-06T00:00:00+00:00",
}
_TREND = {
    "ok": True,
    "metrics": {"period_return_pct": 1.23, "cagr_pct": None,
                "ann_vol_pct": None, "max_drawdown_pct": -2.0},
    "curve": None, "annualized_suppressed": True, "low_confidence": False,
    "coverage_start": "2026-08-01", "coverage_end": "2026-09-06",
    "n_days": 20, "n_funds_used": 2, "excluded": [], "weights_norm": {"AAA": 0.5, "BBB": 0.5},
}
_FUNDS = [{"code": "AAA", "invest_twd": 500.0}, {"code": "BBB", "invest_twd": 500.0}]


class _SessionDict(dict):
    """`dict`，但同時吃屬性存取 —— 真 streamlit 的 `session_state` 就是這樣。"""

    def __getattr__(self, k: str) -> Any:
        try:
            return self[k]
        except KeyError:
            raise AttributeError(k) from None

    def __setattr__(self, k: str, v: Any) -> None:
        self[k] = v


class _Rec:
    """`st` 的錄影機：記下 caption / button，其餘一律 no-op。"""

    def __init__(self, pressed: "set[str] | None" = None) -> None:
        self.session_state = _SessionDict()
        self.captions: list[str] = []
        self.buttons: list[str] = []
        self._pressed = pressed or set()

    # 使用者的「按下」在這裡被完全控制 —— 預設什麼都沒按。
    def button(self, label: str = "", *_a: Any, **k: Any) -> bool:
        key = k.get("key") or label
        self.buttons.append(str(key))
        return str(key) in self._pressed

    def caption(self, msg: Any = "", *_a: Any, **_k: Any) -> None:
        self.captions.append(str(msg))

    def columns(self, n: Any = 1, **_k: Any) -> list:
        return [_Rec._Cell() for _ in range(n if isinstance(n, int) else len(n))]

    class _Cell:
        def metric(self, *_a: Any, **_k: Any) -> None:
            return None

        def __enter__(self) -> "_Rec._Cell":
            return self

        def __exit__(self, *_e: Any) -> bool:
            return False

    def __getattr__(self, _name: str) -> Any:
        def _noop(*_a: Any, **_k: Any) -> Any:
            return _Rec._Cell()
        return _noop


def _collaborators(monkeypatch) -> None:
    """把**純計算**的協作模組換成確定性替身（不是被測對象）。

    ⚠️ 被測對象只有兩個檔：`switch_advisor_section` 與 `portfolio_perf_repository`。
    走勢 / 指標的正確性由 `tests/test_portfolio_tracking.py` 守，本檔只問「有沒有寫」。
    """
    def _mod(name: str) -> types.ModuleType:
        try:
            return importlib.import_module(name)
        except Exception:                                    # 本機缺 numpy/pandas 時
            m = types.ModuleType(name)
            sys.modules[name] = m
            return m

    pp = _mod("ui.helpers.portfolio_perf")
    monkeypatch.setattr(pp, "_nav_weights_from_funds",
                        lambda funds: ({"AAA": object(), "BBB": object()},
                                       {"AAA": 0.5, "BBB": 0.5}, False), raising=False)
    pt = _mod("services.portfolio_tracking")
    monkeypatch.setattr(pt, "reconstruct_trend", lambda *a, **k: dict(_TREND), raising=False)
    monkeypatch.setattr(pt, "build_snapshot_row", lambda *a, **k: dict(_ROW), raising=False)
    hm = _mod("services.hot_money_service")
    monkeypatch.setattr(hm, "fetch_usdtwd_frame", lambda *a, **k: (None, "test"), raising=False)


#: 渲染路徑上所有**函式內 lazy import** 的模組。裝哨兵之前要先全部載入。
#:
#: ⚠️ **這不是保險起見，是一個會在 CI 上偶發、在本機永遠看不到的假紅燈。**
#: `_disk_sentinels` 會在渲染那一小段監看 `builtins.open`（寫入模式）與 `os.replace`。
#: 而 Python **第一次** import 一個模組時會寫 `__pycache__` —— 如果那次 import
#: 剛好發生在哨兵窗內（渲染路徑上的 lazy import 就是這種），哨兵會記到一筆
#: **與 Google Sheet 完全無關的磁碟寫入**，測試轉紅。
#: 本機看不到是因為這些模組早就被別的東西載過了；CI 上有 `pytest-randomly`，
#: 本檔可能是整個 session 第一個碰到它們的人 —— **順序一換就紅一次**。
#: ⇒ 先載完再裝哨兵：窗內就不會有 import，也就沒有 `__pycache__` 可寫。
_LAZY_ON_RENDER_PATH = (
    "repositories.portfolio_perf_repository",
    "services.portfolio_tracking",
    "ui.helpers.portfolio_perf",
    "ui.helpers.story_nav",
    "ui.helpers.render_state",
    "shared.signal_thresholds",
    "services.hot_money_service",
    "pandas",
)


def _prewarm() -> None:
    """把渲染路徑上的 lazy import 先載完（理由見 :data:`_LAZY_ON_RENDER_PATH`）。"""
    for _name in _LAZY_ON_RENDER_PATH:
        with contextlib.suppress(Exception):     # 本機缺 pandas/numpy → 略過，不影響斷言
            importlib.import_module(_name)


def _render(monkeypatch, *, rows: "list[list[str]] | None", pressed: "set[str] | None" = None
            ) -> "tuple[list[str], _Rec]":
    """裝好兩層哨兵 → 真的渲染一輪 → 回傳 (寫入紀錄, 錄影機)。"""
    trips: list[str] = []
    _prewarm()                                   # ← 必須在裝哨兵之前，理由見該函式
    _collaborators(monkeypatch)
    store = _gs_store(rows, trips)
    monkeypatch.setattr(PR, "get_perf_store", lambda: store, raising=False)

    rec = _Rec(pressed)
    targets = [m for n, m in list(sys.modules.items())
               if n.startswith("ui.") and m is not None and getattr(m, "st", None) is not None]
    assert targets, "一個帶 module 層 `st` 的 ui 模組都沒掃到 —— 錄影機沒接上"
    for m in targets:
        monkeypatch.setattr(m, "st", rec, raising=False)
    with contextlib.suppress(Exception):
        monkeypatch.setattr(importlib.import_module("streamlit"), "session_state",
                            rec.session_state, raising=False)

    with _disk_sentinels(trips):
        SECTION.render_portfolio_tracking(list(_FUNDS))
    return trips, rec


# ══════════════════════════════════════════════════════════════════════
# 4｜錨點 —— 先證明這台機器真的會抓到東西（否則下面全綠毫無意義）
# ══════════════════════════════════════════════════════════════════════
def test_the_fake_sheet_denies_by_default():
    """一個**沒有列在任何清單裡**的方法被呼叫 → 必須被記成寫入。

    這條在守「預設拒絕」這個設計本身。若有人把 :class:`_DenyByDefaultWorksheet`
    改成「攔截已知寫入方法名」，本條會紅 —— 因為 `some_method_nobody_listed`
    不在任何白名單裡，白名單式的實作**不會**記到它。

    突變驗證：把 `__getattr__` 改成只在 `name in {"append_row","update"}` 時記錄 → 本條轉紅。
    """
    trips: list[str] = []
    ws = _DenyByDefaultWorksheet([list(_HEADERS)], trips)
    ws.some_method_nobody_listed(1, 2, x=3)
    ws.batch_update([{"range": "A1"}])
    assert trips == ["worksheet.some_method_nobody_listed", "worksheet.batch_update"], (
        "假試算表沒有預設拒絕 —— 未列名的方法被靜默放行了。"
        "白名單式守衛漏一個名字就是漏守，這正是本檔不用白名單的原因。\n"
        f"實際記到：{trips}")
    assert ws.get_all_values() == [list(_HEADERS)], "純讀方法應照常回值，不得被記成寫入"
    assert trips == ["worksheet.some_method_nobody_listed", "worksheet.batch_update"], (
        f"純讀方法被誤記成寫入（偽陽性）：{trips}")


#: 渲染會走到的 production 函式（它們的函式內 import 就是「哨兵窗內的 import」）。
_RENDER_PATH_FUNCS = ("render_portfolio_tracking", "_snapshot_control", "_ccy_fx_for")


def test_prewarm_covers_every_lazy_import_on_the_render_path():
    """:data:`_LAZY_ON_RENDER_PATH` 必須**涵蓋**渲染路徑上每一個函式內 import。

    ⚠️ **本條刻意用 AST 比對「產品程式碼實際寫了哪些 lazy import」，
    而不是去問 `sys.modules` 有沒有載到** —— 後者是**循環的**：
    `_prewarm()` 自己就是用 `import_module` 載的，載完再問「載到了嗎」必然為真，
    那種斷言殺不掉任何突變（本條初版就是那樣寫的，寫完當場作廢）。

    這條真正要擋的漂移是：**有人在渲染路徑上新增一個 lazy import，卻沒加進
    :data:`_LAZY_ON_RENDER_PATH`** —— 那個模組會在哨兵窗內首次 import、寫 `__pycache__`，
    於是磁碟哨兵記到一筆與 Google Sheet 無關的寫入，測試變成**偶發假紅燈**
    （本機永遠重現不了，CI 隨機順序下才會發作）。

    突變驗證：從 `_LAZY_ON_RENDER_PATH` 拿掉任一項 → 本條轉紅。
    """
    tree = _tree(SECTION_REL)
    found: set[str] = set()
    for name in _RENDER_PATH_FUNCS:
        for node in ast.walk(_func(tree, name)):
            if isinstance(node, ast.Import):
                found |= {a.name for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                found.add(node.module)
    assert found, (
        f"在 {_RENDER_PATH_FUNCS} 裡一個函式內 import 都沒掃到 —— "
        "本條正在對空氣生效（產品程式碼改寫過？）")
    uncovered = sorted(found - set(_LAZY_ON_RENDER_PATH))
    assert not uncovered, (
        "渲染路徑上有 lazy import 沒被 `_prewarm()` 涵蓋，會在哨兵窗內首次 import、"
        f"寫 `__pycache__` → 偶發假紅燈：\n  {uncovered}\n"
        "請加進 `_LAZY_ON_RENDER_PATH`。")


def test_the_disk_sentinels_really_install_themselves():
    """磁碟哨兵真的換上去了 —— 否則「零寫入」只是因為機器沒開。

    突變驗證：把 `_disk_sentinels` 的 `_block` 迴圈整個拿掉 → 本條轉紅。
    """
    trips: list[str] = []
    with _disk_sentinels(trips) as installed:
        assert "pathlib.Path.write_text" in installed and "builtins.open" in installed, (
            f"磁碟哨兵沒裝上：{installed}")
        pathlib.Path("/tmp/never-actually-written-by-this-test").write_text("x")
    assert "pathlib.Path.write_text" in trips, f"哨兵裝了卻沒記到：{trips}"
    assert not pathlib.Path("/tmp/never-actually-written-by-this-test").exists(), (
        "哨兵應該攔下寫入（不放行），檔案不該真的被建出來")


def test_stubs_never_shadow_the_real_thing():
    """有真的 `streamlit` / `pandas` 就必須用真的，替身只在缺席時頂上。

    ⚠️ 這條是防止本檔在 CI 上**量到替身而不是產品**。本機沒裝那兩個套件時
    `STUBBED` 會是 True，那是誠實的降級；CI 上兩者皆在 `requirements.txt` 裡，
    一旦這裡變成 True 代表有人把替身塞進了真模組前面。
    """
    # ⚠️ 不能用 `importlib.util.find_spec` —— 替身一旦進了 `sys.modules`，
    #    它就會直接回那個 `__spec__ is None` 的替身並丟 `ValueError`（實測）。
    #    `PathFinder` **繞過 `sys.modules`、只看 `sys.path` 上真的有沒有那個套件**，
    #    正是這裡要問的問題。
    for name, stubbed in STUBBED.items():
        if not stubbed:
            continue
        found = importlib.machinery.PathFinder.find_spec(name, sys.path)
        assert found is None, (
            f"`{name}` 在 sys.path 上明明裝得到（{getattr(found, 'origin', '?')}），"
            "卻用了替身 —— 這道守衛會量到替身而不是產品")


# ══════════════════════════════════════════════════════════════════════
# 5｜①渲染零寫入（本檔的主結論）
# ══════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("rows, branch", [
    ([list(_HEADERS)], "sheet_ready"),          # 分頁已備妥
    (None, "sheet_missing"),                    # 遠端還沒有這個分頁 ← 舊版就是在這裡建分頁
    ([["date", "WRONG"]], "header_mismatch"),   # 表頭不符           ← 舊版在這裡補表頭
])
def test_rendering_the_tracking_block_writes_nothing(monkeypatch, rows, branch):
    """打開 ④ 的績效追蹤區塊、**什麼都不按** → 送出的寫入必須是 0 筆。

    三個分支缺一不可：舊版的兩筆隱藏寫入**只在遠端狀態不符預期時**才發作，
    只測 `sheet_ready` 會全綠放行（那正是它活到今天的原因）。

    突變驗證（兩次實跑，見 PR 描述）：
    把 `_snapshot_control` 的 `if not _clicked: return` 拿掉 → `sheet_ready` 轉紅；
    把 `load_snapshots` 走的 `_ws()` 換回會補建的 `_ws_for_write()` → 另兩個分支轉紅。
    """
    trips, rec = _render(monkeypatch, rows=rows)
    assert rec.buttons, "連快照按鈕都沒渲染出來 —— 使用者沒有任何方式可以主動存快照"
    assert trips == [], (
        f"渲染 ④「📈 組合績效追蹤」（分支 {branch}）在使用者什麼都沒按的情況下送出了寫入 ——\n"
        "客戶 2026-09-06 永久授權：查詢一律唯讀，絕對禁止反向寫入 Google Sheet。\n"
        f"實際送出：{trips}")


def test_the_sentinel_is_not_always_green(monkeypatch):
    """正對照：**按下**快照鈕 → 必須真的寫得出去。

    沒有這一條，上面那組「零寫入」可能只是因為哨兵恆假 / 功能被砍光。
    這條同時也是「按鈕真的接上寫入」的功能回歸。
    """
    trips, rec = _render(monkeypatch, rows=[list(_HEADERS)],
                         pressed={SECTION._SNAPSHOT_BTN_KEY})
    assert "worksheet.append_row" in trips, (
        "按下快照鈕之後沒有任何寫入 —— 要嘛哨兵是恆假的（上面那組零寫入不算數），"
        f"要嘛存快照這個功能被砍掉了。實際：{trips}")


def test_pressing_some_other_button_still_writes_nothing(monkeypatch):
    """按的是**別顆**按鈕 → 依然零寫入（證明閘門認的是那一顆，不是「有沒有人按過東西」）。"""
    trips, _ = _render(monkeypatch, rows=[list(_HEADERS)], pressed={"some_other_button"})
    assert trips == [], f"按了不相干的按鈕就寫入 —— 閘門沒有綁在快照鈕上：{trips}"


def test_the_session_flag_is_not_a_write_gate(monkeypatch):
    """⛔ 用 session 旗標去重**不算修好** —— 旗標為 False 時渲染依然必須零寫入。

    舊版的閘門就是 `if st.session_state.get("_perf_snapshot_done"): return`。
    它讓「每個 session 寫一次」變成「少寫幾次」，而使用者從頭到尾沒有表達任何意圖。
    **少寫幾次不叫切斷。**

    突變驗證：把 `_snapshot_control` 改回「旗標沒設就寫」→ 本條轉紅。
    """
    trips, rec = _render(monkeypatch, rows=[list(_HEADERS)])
    assert not rec.session_state.get("_perf_snapshot_done"), (
        "沒按任何按鈕，`_perf_snapshot_done` 卻被設起來了 —— "
        "那代表寫入路徑仍然在渲染時被走過（旗標是它留下的腳印）")
    assert trips == [], f"旗標未設時渲染就寫入 —— 這正是 2026-09-06 之前的病灶：{trips}"


# ══════════════════════════════════════════════════════════════════════
# 6｜②讀路徑零寫入（名字是讀，就不准寫）
# ══════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("rows, why", [
    (None, "遠端還沒有這個分頁"),
    ([["date", "WRONG"]], "表頭與欄位定義不符"),
    ([], "分頁是空的（連表頭都沒有）"),
])
def test_read_path_never_provisions_the_sheet(rows, why):
    """`load_snapshots()` 遇到未備妥的遠端 → **raise，不就地補建**，且零寫入。

    突變驗證：把 `_ws()` 內的 `raise SheetNotProvisioned` 換回
    `add_worksheet` + `update("A1", …)` → 本條三個分支同時轉紅。
    """
    trips: list[str] = []
    store = _gs_store(rows, trips)
    with pytest.raises(SheetNotProvisioned):
        store.load_snapshots()
    assert trips == [], (
        f"讀路徑（{why}）動到了試算表 —— 一個名字叫 `load_snapshots` 的函式不該寫任何東西：{trips}")


def test_read_path_does_not_swallow_it_into_an_empty_list():
    """⛔ 未備妥時**不得**靜默回 `[]`（`CLAUDE.md §1` Fail Loud）。

    回空 list 會讓畫面顯示一片空白，而使用者以為「本來就沒資料」——
    那是把「還沒建好」偽裝成「已經看過了，沒有東西」。
    """
    trips: list[str] = []
    with pytest.raises(SheetNotProvisioned) as ei:
        _gs_store(None, trips).load_snapshots()
    assert getattr(ei.value, "where", ""), (
        "`SheetNotProvisioned` 沒有帶「去哪補」—— 灰態三要素缺一角，"
        "使用者只會知道『沒東西』，不知道下一步要做什麼")


def test_read_path_reads_normally_when_the_sheet_is_ready():
    """正對照：分頁備妥時 `load_snapshots()` 照常回資料，且**仍然**零寫入。

    沒有這一條，上面那組「零寫入」可以靠「把讀取整個弄壞」達成。
    """
    trips: list[str] = []
    snap = PerfSnapshot(**_ROW)
    store = _gs_store([list(_HEADERS), snap.to_row()], trips)
    got = store.load_snapshots()
    assert [s.date for s in got] == [_ROW["date"]], f"備妥的分頁應該讀得出資料：{got}"
    assert trips == [], f"連讀都會寫：{trips}"


def test_write_path_still_provisions_the_sheet():
    """寫路徑**保留**補建能力 —— 這次修的是「誰有資格觸發」，不是把功能砍掉。

    使用者按下快照鈕、而遠端還沒有分頁時，必須幫他建好再寫，否則第一次存永遠失敗。
    """
    trips: list[str] = []
    _gs_store(None, trips).append_snapshot(PerfSnapshot(**_ROW))
    assert "spreadsheet.add_worksheet" in trips and "worksheet.update" in trips, (
        f"寫路徑不再補建分頁 —— 使用者第一次存快照會失敗：{trips}")
    assert "worksheet.append_row" in trips, f"補建了卻沒寫進去：{trips}"


def test_reading_local_snapshots_creates_no_directory(tmp_path):
    """本地 JSON 後端：**讀**不得在使用者磁碟上建目錄。

    與 GS 那條是同一個病的本地版 —— 舊版在 `__init__` 就 `mkdir`，
    而 `load_snapshots()` 每次都會 new 一個 store。

    突變驗證：把 `mkdir` 搬回 `__init__` → 本條轉紅。
    """
    base = tmp_path / "not-created-by-reading"
    assert LocalJsonPerfStore(base_dir=base).load_snapshots() == []
    assert not base.exists(), f"讀路徑在磁碟上建了目錄：{base}"
    LocalJsonPerfStore(base_dir=base).append_snapshot(PerfSnapshot(**_ROW))
    assert base.exists(), "寫路徑應該要建目錄（這次修的是讀，不是把寫也砍掉）"


# ══════════════════════════════════════════════════════════════════════
# 7｜結構 —— 寫入呼叫只能長在按鈕的 `if` 正分支裡
# ══════════════════════════════════════════════════════════════════════
#: 「渲染不得碰」的寫入入口（`_maybe_snapshot` 是 2026-09-06 之前那個無條件寫入的舊名字）。
_WRITE_ENTRIES = ("append_snapshot", "_maybe_snapshot")
#: 唯讀開啟器 `_ws()` 裡不得出現的寫入動詞。
_WS_WRITE_VERBS = ("add_worksheet", "update", "append_row", "batch_update")


def _tree(rel: str) -> ast.Module:
    return ast.parse((ROOT / rel).read_text(encoding="utf-8"))


def _func(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"找不到函式 {name}()")


def _method(tree: ast.Module, cls_name: str, name: str) -> ast.FunctionDef:
    cls = next(n for n in ast.walk(tree)
               if isinstance(n, ast.ClassDef) and n.name == cls_name)
    return next(n for n in cls.body
                if isinstance(n, ast.FunctionDef) and n.name == name)


def _src(node: ast.AST) -> str:
    """把節點還原成可讀的一小段原始碼，純為了錯誤訊息。"""
    try:
        return ast.unparse(node)
    except Exception:                       # pragma: no cover — 舊 runtime 沒有 ast.unparse
        return getattr(node, "attr", "") or getattr(node, "id", "") or "<expr>"


def _bindings(tree: ast.Module) -> "dict[str, str]":
    """這個檔案裡每個名字**最後**綁到的原始符號名 —— 別名解析。

    ⚠️ **做法沿用 `tests/test_readonly_query_paths.py::_pool_symbol_bindings`（#796）**，
    不是新發明的解析器；差別只有一處，寫在下面 ③。

    認的形狀：

      ① `from m import append_snapshot`          → ``{"append_snapshot": "append_snapshot"}``
      ② `from m import append_snapshot as _sv`   → ``{"_sv": "append_snapshot"}``
      ③ `import m as P` → `P.append_snapshot(…)` → **不需要模組別名表**：本檔的 want 是
         **裸符號名**（`update` / `button` / `_ws_for_write` 這些本來就長在任意物件上），
         所以 `ast.Attribute` 那一支直接比對 `.attr` 就命中。
         （#796 的 want 是「某個模組匯出的符號」，才需要限定 base 是該模組的別名。）
      ④ `g = _sv` / `g = ws.update` → `g(…)`     → 賦值別名，**做到不動點**
         （`g = _sv; h = g` 這種鏈也要跟上）。

    ⚠️ ④ 只認**值是裸 `Name` 或 `Attribute`** 的賦值 —— 也就是「把函式物件本身存起來」那一種。
    `x = f(...)`（值是 `ast.Call`）**不算**，否則整份檔案的每個區域變數都會被綁進來。

    ⚠️ **登記：本函式沒有 scope 概念（2026-09-07 實測，機制上會誤紅）**
    ---------------------------------------------------------------
    它 `ast.walk` **整棵模組樹**，把所有賦值收進**同一張平表** —— 不分函式、不分類別。
    於是同名區域變數會跨 scope 互相汙染：

        def writer(ws):
            _g = ws.update        # 這裡把 `_g` 綁成 `update`
            _g("A1", [])
        def innocent():
            _g = 5                # 值是 Constant → 不覆寫綁定
            return _g             # ← `_refs(innocent, …, ("update",))` **命中**：誤紅

    **實測**：上面這段 `_bindings` 回 ``{"_g": "update"}``；把 `writer()` 拿掉後
    `innocent()` 就乾淨了 —— 證明誤紅確實來自跨 scope 綁定，不是別的原因。

    ✅ **今天不是缺陷，因為前提不成立**：誤紅的必要前提是「**存在一個賦值別名解析到
    受管符號**」。全 repo **656 個 `.py`** 實測，這種別名 **0 個**
    （量測日 **2026-09-07**；正對照：合成一個 `_g = ws.update` 的檔案就驗得出來，
    證明偵測器是活的）。
    ⚠️ **這是會漂移的量測值** —— 要用請**現場重跑**，不要引用本行。
    **前提哪天成立了（有人寫出這種別名），這裡就會開始誤紅。**

    ⛔ **本則只是登記，不構成修改授權** —— 加 scope 是**行為變更**，需要重新稽核。
    """
    binds: "dict[str, str]" = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for a in node.names:
                if a.name != "*":
                    binds[a.asname or a.name] = a.name

    for _ in range(8):                      # 8 圈護欄，防病態輸入
        grew = False
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign) or len(node.targets) != 1:
                continue
            tgt, val = node.targets[0], node.value
            if not isinstance(tgt, ast.Name):
                continue
            if isinstance(val, ast.Name):
                orig = binds.get(val.id, val.id)
            elif isinstance(val, ast.Attribute):
                orig = val.attr
            else:
                continue
            if binds.get(tgt.id) != orig:
                binds[tgt.id] = orig
                grew = True
        if not grew:
            break
    return binds


def _refs(node: ast.AST, tree: ast.Module, want) -> "list[tuple[str, str, int, str]]":
    """`node` 這棵子樹裡，對 `want` 那組符號的**任何參照** —— 不只是呼叫。

    回 ``[(原始符號, 實際寫法, 行號, 形態)]``，形態為 ``"call"`` 或 ``"ref"``。

    ⚠️ **2026-09-07 由「只看呼叫」擴為「呼叫 ＋ 裸參照」，並補上別名解析**
    （**有意識的更正，不是漏刪** · 日期 **2026-09-07** · 決策者：**AI 執行組**，
    依憲法 §8.3.P 登記的 `P-CALLSTATIC-1`）。舊名 ``_calls()``。

    **舊寫法的理由仍然成立**：「有沒有被呼叫」是最直接的問法，訊息也最好讀。
    **被權衡掉的是它的射程** —— 它只走 `ast.Call` 節點、而且只比對字面名字，於是
    **兩種形態在靜態層整個看不見**（2026-09-07 於 `810ebc5` 實測，逐字紀錄，不是推測）：

        _f = _sv ; _f(None)                     # ← 舊規則 GREEN（別名規避）
        _with_quota_retry(ws.update, "A1", [])  # ← 舊規則 GREEN（當引數傳出去）

    第二種的根因是 `ws.update` 在 AST 上是**引數位置的 `ast.Attribute`，不是 `ast.Call`**。

    ⚠️ **這不是假想敵**：`repositories/snapshot_repository.py` 有 **12** 處
    `_with_quota_retry(ws.append_row, …)`、`repositories/policy/v2.py` 有 **3** 處
    （量測日 **2026-09-06**，數字引自 #796，本組未重新清點；⛔ 那兩檔是既有寫入面、
    有它們自己的正當用途，**不在本規則射程內**）。
    **一個只掃 `Call` 的掃描器，在那些檔上會回報 0。**

    **現行命中條件**：只要一個名字**最後綁到 `want` 裡的符號**，
    **不論它是被呼叫、還是被當成值傳出去／存起來**，一律命中。

    ⚠️ `Store` context 刻意排除：``_g = ws.update`` 這一行命中的是**右側**那個
    `ws.update`（ref），不是左側被賦值的 `_g` —— 否則同一處會被算兩次。
    **但「先存起來、之後才呼叫」不會因此漏掉**：後面那個 `_g` 是 `Load`，
    經 :func:`_bindings` 解析回 `update` 照樣命中
    （:func:`test_the_assigned_name_is_not_counted_twice` 就是釘這件事的）。

    ⚠️ **登記一：`Del` 沒有被排除（2026-09-07 實測）**
    -------------------------------------------------
    只排除了 `Store`，所以 ``del append_snapshot`` 會回一個 ``ref`` 命中。
    **刻意與 #796 保持一致、不自行加碼** —— 全 repo **656 個 `.py`** 實測，
    `del <受管符號>` **0 處**（量測日 **2026-09-07**），所以今天擋不到任何東西，
    也誤不到任何東西。**這是會漂移的量測值，要用請現場重跑。**

    ⚠️ **登記二：若日後把本規則指向 `tests/`，會大量誤紅（2026-09-07 實測）**
    ----------------------------------------------------------------------
    現行射程只有**受管兩檔**（`switch_advisor_section.py` /
    `portfolio_perf_repository.py`），在那兩檔上放寬後**新增 0 命中**
    （:func:`test_no_false_positive_on_the_managed_files` 釘住）。
    但**若有人擴大射程**，以本檔四組 `want` 的聯集全 repo 掃，`ref` 形態命中 **63** 個：

        repositories/   12   ← **真陽性**：`_with_quota_retry(ws.append_row, …)` 這一族
                              （`snapshot_repository.py` 10 ＋ `policy/v2.py` 2）
                              ⛔ 那是既有寫入面、有正當用途，**不在本規則射程內**
        tests/          51   ← **雜訊**：Mock 斷言（`ws.update` / `ws.append_row`）
                              與 AppTest 的 `at.button`（其中 `button` 共 12 個）

    ⛔ **擴大射程前必須先知道這件事** —— 直接把 `tests/` 納入會得到 51 個誤紅，
    然後**很可能被「加一張豁免表」解決掉**，而那正是本檔一路拒絕的做法。
    **真出現誤紅時正解是收窄規則，不是加豁免。**
    ⚠️ **這是會漂移的量測值（量測日 2026-09-07），要用請現場重跑。**

    ⛔ **上列兩則只是登記，不構成修改授權** —— 排除 `Del` 或擴大射程都是**行為變更**，
    需要重新稽核。
    """
    binds = _bindings(tree)
    # 先記住哪些節點站在「呼叫的 func 位置」，好把 call 與 ref 分開標（不重複計數）
    call_funcs = {id(n.func) for n in ast.walk(node) if isinstance(n, ast.Call)}

    hits: "list[tuple[str, str, int, str]]" = []
    for n in ast.walk(node):
        if isinstance(n, ast.Name):
            if isinstance(n.ctx, ast.Store):
                continue
            origin, spelled = binds.get(n.id, n.id), n.id
        elif isinstance(n, ast.Attribute):
            if isinstance(n.ctx, ast.Store):
                continue
            origin, spelled = n.attr, _src(n)
        else:
            continue
        if origin not in want:
            continue
        hits.append((origin, spelled, n.lineno,
                     "call" if id(n) in call_funcs else "ref"))
    return sorted(hits, key=lambda h: (h[2], h[1]))


def test_the_render_function_never_calls_the_writer_directly():
    """`render_portfolio_tracking()` 自己**不得**參照 `append_snapshot` ——
    寫入只能經由 :func:`_snapshot_control`（而它由按鈕守著）。

    ⚠️ ~~本條是**結構**輔助，不是主守衛：改個別名就繞得過去。~~
    → **2026-09-07 更正（有意識的更正，不是漏刪 · 決策者：AI 執行組）**：
    **「改個別名就繞得過去」已經不成立** —— :func:`_refs` 會把 import 別名與賦值別名
    解回原始符號（:func:`test_bypass_1_alias_then_call_is_caught` 釘住）。
    **舊敘述的用意仍然成立**（結構層本來就比行為層弱、不該被當成主守衛），
    **被權衡掉的只有它舉的那個例子** —— 它把一個**已經補上**的洞寫成永久性質，
    會讓後人以為這一層本來就守不住別名，而不去修它。
    ⚠️ ~~**現在仍然守不到的是「靜態期不存在的名字」**（`getattr(o, "a"+"b")` /
    `importlib.import_module`），那一類靠行為層擋，見模組 docstring。~~
    → **2026-09-07 再更正（有意識的更正，不是漏刪 · 日期 2026-09-07 ·
    決策者：AI 總管（依獨立稽核實測））**：**這句把殘餘缺口講得太小。**
    **被推翻的是「補上了多少」這個射程宣稱，不是本條的修復** ——
    別名那半確實補起來了（下面的突變驗證仍然成立）。
    **實際補上的只有 import 別名與單目標賦值別名**；
    **tuple／list 解包、鏈式賦值、dict 等容器承載、`functools.partial`、
    以及字面字串的 `getattr`** —— 這些即使名字完整寫在原始碼裡，
    靜態層**一樣看不到**（2026-09-07 六種逐一實跑，含正對照）。
    ⛔ 這些**一律靠行為層擋**，且**不得以「靜態層有守」為由簡化行為層哨兵** ——
    六種形態與行為層七種實測見模組 docstring「看不見」那一節。

    突變驗證（2026-09-07 實跑）：在 `render_portfolio_tracking` 內加一行
    `append_snapshot(...)` → 本條轉紅；改成 `_f = _sv; _f(...)` → **本條同樣轉紅**。
    """
    tree = _tree(SECTION_REL)
    bad = _refs(_func(tree, "render_portfolio_tracking"), tree, _WRITE_ENTRIES)
    assert not bad, (
        "`render_portfolio_tracking()` 參照了寫入函式 —— 渲染就會寫：\n  "
        f"{bad}\n（形態 `ref` ＝ 沒有直接呼叫，是把它當值傳出去／存起來）\n"
        "寫入只能放在 `_snapshot_control()` 內、按鈕的 `if` 正分支裡。")


def test_the_write_lives_inside_the_button_branch():
    """`append_snapshot` 必須在「按鈕回 True」的 `if` **正分支**底下。

    偵測方式：`_snapshot_control()` 內若有 `if not <clicked>: return` 這種提前退出，
    其後的 body 就等價於正分支。本條要求兩者之一成立，並且 `st.button` 真的存在。

    突變驗證：把 `if not _clicked: return` 拿掉 → 本條轉紅。
    """
    tree = _tree(SECTION_REL)
    fn = _func(tree, "_snapshot_control")
    assert _refs(fn, tree, ("button",)), (
        "`_snapshot_control()` 裡沒有 `st.button` —— 沒有任何明示動作可言")

    guards = [n for n in fn.body
              if isinstance(n, ast.If)
              and isinstance(n.test, ast.UnaryOp) and isinstance(n.test.op, ast.Not)
              and any(isinstance(s, ast.Return) for s in n.body)]
    assert guards, (
        "`_snapshot_control()` 沒有「沒按就 return」的提前退出 —— "
        "無法確認 `append_snapshot` 只在按下之後才走得到")
    guard_at = fn.body.index(guards[0])
    before = [h for stmt in fn.body[:guard_at] for h in _refs(stmt, tree, ("append_snapshot",))]
    assert not before, (
        f"`append_snapshot` 出現在「沒按就 return」之前 —— 那等於沒有閘門：{before}")
    after = [h for stmt in fn.body[guard_at + 1:] for h in _refs(stmt, tree, ("append_snapshot",))]
    assert after, (
        "閘門之後找不到 `append_snapshot` —— 按下按鈕也不會寫，功能是壞的")


def test_the_read_path_does_not_reach_the_provisioning_helper():
    """`GoogleSheetsPerfStore.load_snapshots()` 不得碰 `_ws_for_write`。

    突變驗證：把 `load_snapshots` 的 `self._ws()` 改成 `self._ws_for_write()` → 本條轉紅。
    """
    tree = _tree(REPO_REL)
    bad = _refs(_method(tree, "GoogleSheetsPerfStore", "load_snapshots"), tree, ("_ws_for_write",))
    assert not bad, (
        f"讀路徑走到了會補建分頁的 `_ws_for_write()` —— 那正是 2026-09-06 之前的病灶：{bad}")
    assert _refs(_method(tree, "GoogleSheetsPerfStore", "append_snapshot"), tree,
                 ("_ws_for_write",)), (
        "寫路徑沒有走 `_ws_for_write()` —— 遠端還沒有分頁時第一次存會失敗")


def test_the_readonly_opener_contains_no_write_verbs():
    """`_ws()`（唯讀開啟）內不得出現 `add_worksheet` / `update` 這類動詞。

    ⚠️ ~~這是**字面**檢查，改個別名就繞得過。~~
    → **2026-09-07 更正（有意識的更正，不是漏刪 · 決策者：AI 執行組）**：
    改為**參照**檢查 —— 把寫入方法**當引數傳出去**（`_with_quota_retry(ws.update, …)`）
    現在也會命中（:func:`test_bypass_2_passed_as_an_argument_is_caught` 釘住）。
    **舊敘述的用意仍然成立**（它想說「別把這一條當成唯一防線」），
    **被權衡掉的是它的事實面** —— 那句話在 2026-09-07 之前是對的。
    ⚠️ ~~現在只對「動態組出的名字」還成立。~~
    → **2026-09-07 同日再更正（有意識的更正，不是漏刪 · 日期 2026-09-07 ·
    決策者：AI 總管（依獨立稽核實測））**：**「只對動態組出的名字」這個射程是假的。**
    **被推翻的是「補上了多少」，不是本條的修復** —— 當引數傳出去那半確實補起來了。
    **實際補上的只有 import 別名與單目標賦值別名**；
    **tuple／list 解包、鏈式賦值、dict 等容器承載、`functools.partial`、
    以及字面字串的 `getattr`（`getattr(ws, "update")("A1", [])`）** ——
    名字完整寫在原始碼裡，靜態層**一樣看不到**（2026-09-07 六種逐一實跑）。
    ⛔ **不得以「靜態層有守」為由簡化行為層哨兵。**
    真正把所有形態都擋下的仍然是
    :func:`test_read_path_never_provisions_the_sheet`（行為，不看名字）——
    上列六種 ＋ 執行期拼名共七種，2026-09-07 在行為層實測**全部被記成寫入**。
    """
    tree = _tree(REPO_REL)
    bad = _refs(_method(tree, "GoogleSheetsPerfStore", "_ws"), tree, _WS_WRITE_VERBS)
    assert not bad, (
        f"唯讀開啟器 `_ws()` 裡出現了寫入動詞：{bad}\n"
        "（形態 `ref` ＝ 沒有直接呼叫，是把它當值傳給包裝器／存起來）")


# ══════════════════════════════════════════════════════════════════════
# 7b｜規則自己的守衛 —— 放寬命中條件之後，它到底看得見什麼
# ══════════════════════════════════════════════════════════════════════
#: 繞道 ①：import 別名 → 賦值別名 → 呼叫。舊規則（只走 `ast.Call` 比對字面名）**全綠**。
_FIXTURE_ALIAS = (
    "from repositories.portfolio_perf_repository import append_snapshot as _sv\n"
    "def render_portfolio_tracking():\n"
    "    _f = _sv\n"
    "    _f(None)\n"
)
#: 繞道 ②：把寫入方法當引數傳給包裝器 —— `ast.Attribute`，不是 `ast.Call`。舊規則**全綠**。
_FIXTURE_PASSED_ARG = (
    "class GoogleSheetsPerfStore:\n"
    "    def _ws(self):\n"
    "        ws = self._sh.worksheet('x')\n"
    "        _with_quota_retry(ws.update, 'A1', [])\n"
    "        return ws\n"
)


def test_bypass_1_alias_then_call_is_caught():
    """⭐ 繞道 ①（別名規避）—— 舊規則活得下來，新規則必須抓到。

        from … import append_snapshot as _sv
        _f = _sv          # ← 賦值別名
        _f(None)          # ← 呼叫的是 `_f`，字面上沒有 `append_snapshot`

    **兩處都要看到**：`_f = _sv` 的右側（ref）＋ 之後那次呼叫（call）——
    這正是「先存起來、之後才呼叫」的形態，排除 `Store` context 不得把它漏掉。
    """
    tree = ast.parse(_FIXTURE_ALIAS)
    hits = _refs(_func(tree, "render_portfolio_tracking"), tree, _WRITE_ENTRIES)
    assert [h[0] for h in hits] == ["append_snapshot", "append_snapshot"], (
        f"別名規避沒被完整抓到：{hits}")
    assert [h[3] for h in hits] == ["ref", "call"], (
        f"「先存起來、之後才呼叫」的兩個點沒有各記一次：{hits}")


def test_bypass_2_passed_as_an_argument_is_caught():
    """⭐ 繞道 ②（當引數傳出去）—— #796 稽核時七種繞道裡唯一活下來的那一種。

        _with_quota_retry(ws.update, "A1", [])      # 舊規則 GREEN

    根因：`ws.update` 在 AST 上是**引數位置的 `ast.Attribute`，不是 `ast.Call`**。
    """
    tree = ast.parse(_FIXTURE_PASSED_ARG)
    hits = _refs(_method(tree, "GoogleSheetsPerfStore", "_ws"), tree, _WS_WRITE_VERBS)
    assert [(h[0], h[1], h[3]) for h in hits] == [("update", "ws.update", "ref")], (
        f"把寫入方法當值傳出去仍然逃得掉：{hits}")


def test_a_call_is_still_reported_as_a_call():
    """⭐ 反向護欄：放寬之後，**直接呼叫**仍然被標成 `call`（訊息可讀性不得退化）。"""
    tree = ast.parse(
        "from repositories.portfolio_perf_repository import append_snapshot\n"
        "def render_portfolio_tracking():\n"
        "    append_snapshot(None)\n")
    hits = _refs(_func(tree, "render_portfolio_tracking"), tree, _WRITE_ENTRIES)
    assert [(h[0], h[3]) for h in hits] == [("append_snapshot", "call")], (
        f"直接呼叫被誤標成 ref：{hits}")


def test_the_assigned_name_is_not_counted_twice():
    """⭐ `Store` context 排除的是**左側**，不是整行。

        _g = ws.update      # 命中右側那個 `ws.update`（ref），左側的 `_g` 不算
        return _g           # 但 `_g` 在 Load 位置時照樣命中 —— 「存起來」不等於「逃掉」
    """
    tree = ast.parse("def f(ws):\n    _g = ws.update\n    return _g\n")
    hits = _refs(_func(tree, "f"), tree, ("update",))
    assert [(h[1], h[3]) for h in hits] == [("ws.update", "ref"), ("_g", "ref")], (
        f"左側被算了兩次、或「存起來之後」那一次被漏掉：{hits}")


def test_no_false_positive_on_the_managed_files():
    """⭐ **放寬規則最該擔心的事** —— 受管的每一個檔逐一實跑，確認沒有多出來的命中。

    ⚠️ 真出現誤紅時，**正解是收窄規則，不是加豁免** ——
    一張為了讓規則變綠而長出來的豁免表，等於把規則關掉。

    ⚠️ 本條**不是**「整個檔零命中」：這兩個檔本來就有正當的寫入面
    （`_ws_for_write()` 會 `add_worksheet` + `update`、`append_snapshot()` 會 `append_row`）。
    受管的是**節點**，不是整檔 —— 下面三處必須 0，另外兩處必須非 0
    （否則「0 命中」可能只是因為規則壞掉了在空掃）。
    """
    sec, rep = _tree(SECTION_REL), _tree(REPO_REL)
    assert (ROOT / SECTION_REL).exists() and (ROOT / REPO_REL).exists(), (
        "輸入非空斷言：受管檔案不存在 → 本條在空掃")

    zero = {
        "render_portfolio_tracking ✕ 寫入入口":
            _refs(_func(sec, "render_portfolio_tracking"), sec, _WRITE_ENTRIES),
        "load_snapshots ✕ _ws_for_write":
            _refs(_method(rep, "GoogleSheetsPerfStore", "load_snapshots"), rep, ("_ws_for_write",)),
        "_ws ✕ 寫入動詞":
            _refs(_method(rep, "GoogleSheetsPerfStore", "_ws"), rep, _WS_WRITE_VERBS),
    }
    assert not any(zero.values()), (
        f"放寬規則後出現命中 —— 先看規則是不是寫太寬，不要急著加豁免：{zero}")

    ctl = _func(sec, "_snapshot_control")
    assert _refs(ctl, sec, ("append_snapshot",)), (
        "正對照失敗：`_snapshot_control()` 裡看不到 `append_snapshot` —— 規則在空掃")
    assert _refs(_method(rep, "GoogleSheetsPerfStore", "_ws_for_write"), rep, _WS_WRITE_VERBS), (
        "正對照失敗：`_ws_for_write()` 裡看不到任何寫入動詞 —— 規則在空掃")
