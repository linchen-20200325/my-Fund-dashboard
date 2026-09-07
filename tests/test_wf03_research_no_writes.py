"""③ 標的探索的**零寫入**守衛 —— 渲染一輪不得動客戶的 Google Sheet 或磁碟。

客戶 2026-09-06 永久授權（逐字）
--------------------------------
> 「凡是『查詢/搜尋』功能，一律強制走純讀取（唯讀），**絕對禁止反向寫入我的 Google Sheet**。
>   不用問我，直接切斷寫入！」

③ 就是那句話裡的「查詢/搜尋」本身。**2026-09-07 批次接上真取數之後這道守衛才真的有事做** ——
在那之前這一頁沒有任何一條路徑會靠近寫入。

⛔ 為什麼**不能**照抄 ④ 的 `tests/test_wf04_portfolio_no_writes.py`（**實測，不是推測**）
------------------------------------------------------------------------------------
那一份是**純靜態**的：掃「頁面靜態 import 閉包」裡每一個 repo 模組，
找 `_WRITE_SINKS`（`append_row` / `update` / `write_text` / `clear` / `replace` …）
這些**低階寫入動作的名字**，再看它有沒有被按鈕擋住。

**它在 ④ 上可行，是因為 ④ 的閉包只有 11 個模組、`_WRITE_SINKS` 命中 0 個節點**
（該檔自己的缺口 6 就地記載了這件事）。**③ 的閉包是 56 個模組**（本組實測，
指令見 :func:`test_a_whole_closure_name_scan_would_be_useless_here`），
因為它經 `services.moneydj_fetcher` 一路連到 `repositories.fund.*` 與 `infra.*`。

把同一份 sink 名單套上去，**實測得到 106 個「未被擋住的寫入」**，而其中
壓倒性多數是 `str.replace()` / `dict.update()` / `set.clear()` / `os.makedirs()`
—— **全部是偽陽性**。一份 106 個偽陽性的守衛不會被讀，只會被關掉。

→ **本檔改走行為層**：真的把頁面渲染一輪，在**物件邊界**攔低階寫入動作本身。
   ⛔ **不用函式名白名單，也不用 import 來源白名單** —— 本 repo 已實測那種守衛
   擋不住 `from m import f as g` / `g = m.f` 再 `g()` / `getattr` / `importlib`
   四種寫法，而且**還有一個更近的洞**：分層守衛只黑名單「import 來源套件」，
   而 `services.nav_history_gs`（真正會寫 Google Sheet 的那一支）**在白名單內** ——
   把 `append_point(...)` 放進渲染函式，87 個測試照樣全綠。
   :func:`test_a_write_hidden_behind_a_whitelisted_module_is_still_caught` 就是為它寫的。

這道守衛看得見什麼、看不見什麼（照實寫，不要讀成「守死了」）
------------------------------------------------------------
**看得見**

* **任何**打到試算表物件上的寫入 —— :class:`_DenyByDefaultWorksheet` 是**預設拒絕**：
  只有 :data:`_PURE_READERS` 列出的純讀方法放行，**其餘一律記成寫入**。
  ⇒ gspread 哪天多一個新的寫入方法，**不必有人記得把它加進任何清單**就會被算到。
* **磁碟** —— `pathlib.Path.write_text/write_bytes/mkdir/touch/unlink/rename/replace`、
  `os.makedirs/mkdir/remove/...`，以及 `builtins.open(mode 含 w/x/a/+)`。
* **屬性被取出來當引數傳出去** —— 哨兵是靠 `__getattr__` 認的，
  `_with_quota_retry(ws.append_row, …)` 在**取屬性的那一刻**就被記了一筆，
  不必等它被呼叫（＝ ④ 那份 `ast.Attribute` 規則的行為層版本）。
* **名字是怎麼組出來的完全不重要** —— `getattr(ws, "append" + "_row")` 一樣撞上。

**看不見（已知缺口，逐條寫出來）**

1. **哨兵只在渲染那一小段生命週期內生效**；渲染之外的寫入本檔看不到。
2. **`builtins.open` 是觀察不是攔截** —— 全域攔截會把 pytest / importlib 的合法讀檔
   一起打死。只在 mode 含 `w`/`x`/`a`/`+` 時記一筆，然後放行。
   ⇒ 真的踩到時檔案**會**被寫出去，本檔保證的是**當場轉紅**，不是「沒發生」。
3. **不驗按下送出之後**。批次的 `_run_batch()` 一旦真的跑，就會走完整條 NAV 取數鏈
   （它自己會寫磁碟快取，那是**被使用者意圖擋住**的合法寫入）。
   本檔一律 `submitted=False` ＝ **純渲染**，那正是「使用者只是打開這一頁」的處境。
   ⇒ 「送出之後寫了什麼」不在本檔射程內。
4. **沒有靜態的 import 閉包規則。** 理由見上（106 個偽陽性）。
   ⇒ 一段**存在但這一輪沒被執行到**的寫入，本檔看不到它。
   `tests/test_wf03_research_skeleton.py::test_the_page_never_reaches_into_the_data_layer`
   守的是另一半（本頁不得 import `repositories` / `infra` / 網路函式庫），**兩者互補**。
5. **本地沒有 `streamlit` / `pandas`，本檔從未在真 pytest 下跑過**（見 PR 的自陳）。

⚠️ **本檔由執行組單組產出，未經第二組獨立複驗**（`CLAUDE.md §-2` 規則 6）。
   「除了這些以外沒有第 N+1 種繞道」本組**沒有查證，也不宣稱**。
"""
from __future__ import annotations

import ast
import builtins
import contextlib
import os
import pathlib
import sys
from typing import Any, Callable, Iterator

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from test_wf03_research_skeleton import _render  # noqa: E402

_REPO = pathlib.Path(__file__).resolve().parent.parent
_PAGE = "ui.views.page_03_research"
_APPLIED = {"term": "ACDD", "source": "全部"}

#: gspread worksheet 上**純讀**的方法。⭐ **本檔唯一的清單，而且方向是「放行」。**
#: 漏列一個名字的後果是**誤報**（把一個讀當成寫），不是漏報 —— 那正是要的方向。
_PURE_READERS = frozenset({
    "get_all_values", "get_all_records", "get_values", "get", "row_values",
    "col_values", "cell", "acell", "find", "findall", "get_note", "get_notes",
    "title", "id", "row_count", "col_count", "url",
})


class _DenyByDefaultWorksheet:
    """假 worksheet：純讀方法照常回值，**其餘一律記成寫入**。

    ⭐ **記名，不拋例外。** 會 `raise` 的哨兵遇到 `try/except Exception` 就被吃掉了 ——
    守衛沒響、畫面一切正常、而那一筆寫入**照樣送出去了**。
    `trips` 是外部可讀的證據，呼叫端無從吞掉它。
    ⭐ **`__getattr__` 在取屬性的那一刻就記**（不是等它被呼叫）——
    所以「把寫入方法當引數傳給包裝器」也逃不掉。
    """

    def __init__(self, rows: list[list[str]], trips: list[str]) -> None:
        self._rows = [list(_r) for _r in rows]
        self._trips = trips

    def get_all_values(self) -> list[list[str]]:
        return [list(_r) for _r in self._rows]

    def get_all_records(self) -> list[dict]:
        if not self._rows:
            return []
        _head, *_body = self._rows
        return [dict(zip(_head, _r)) for _r in _body]

    def row_values(self, n: int) -> list[str]:
        return list(self._rows[n - 1]) if len(self._rows) >= n else []

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        if name in _PURE_READERS:
            return lambda *_a, **_k: []
        self._trips.append(f"worksheet.{name}")   # ⭐ 取屬性即記名

        def _recorder(*_a: Any, **_k: Any) -> None:
            return None
        return _recorder


class _DenyByDefaultSpreadsheet:
    """假 spreadsheet：`worksheet()` 是讀；其餘一律記成寫入。"""

    def __init__(self, ws: _DenyByDefaultWorksheet | None, trips: list[str]) -> None:
        self._ws, self._trips = ws, trips

    def worksheet(self, title: str) -> _DenyByDefaultWorksheet:
        if self._ws is None:
            raise Exception(f"WorksheetNotFound: {title}（離線假件，未連任何真表）")
        return self._ws

    def worksheets(self) -> list:
        return [self._ws] if self._ws is not None else []

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        self._trips.append(f"spreadsheet.{name}")

        def _recorder(*_a: Any, **_k: Any) -> Any:
            return _DenyByDefaultWorksheet([], self._trips)
        return _recorder


def _recorder(trips: list[str], tag: str) -> Callable[..., None]:
    """記名、**不拋例外**的哨兵（理由見 :class:`_DenyByDefaultWorksheet`）。"""
    def _sentinel(*_a: Any, **_k: Any) -> None:
        trips.append(tag)
    return _sentinel


_WRITE_MODES = "wxa+"


@contextlib.contextmanager
def _sentinels(trips: list[str]) -> Iterator[list[str]]:
    """把磁碟 ＋ 試算表的寫入 primitive 換成哨兵，**只在 `with` 這一小段**。"""
    _installed: list[str] = []
    _undo: list[tuple[Any, str, Any]] = []

    def _block(owner: Any, attr: str, label: str) -> None:
        _orig = getattr(owner, attr, None)
        if _orig is None:
            return
        try:
            setattr(owner, attr, _recorder(trips, label))
        except (AttributeError, TypeError):        # pragma: no cover
            return
        _undo.append((owner, attr, _orig))
        _installed.append(label)

    for _n in ("write_text", "write_bytes", "mkdir", "touch", "unlink",
               "rename", "replace", "rmdir"):
        _block(pathlib.Path, _n, f"pathlib.Path.{_n}")
    for _n in ("makedirs", "mkdir", "remove", "unlink", "rename", "replace", "rmdir"):
        _block(os, _n, f"os.{_n}")

    _orig_open = builtins.open

    def _watch_open(*_a: Any, **_k: Any) -> Any:
        _mode = _k.get("mode") if "mode" in _k else (_a[1] if len(_a) > 1 else "r")
        if any(_c in str(_mode or "r") for _c in _WRITE_MODES):
            trips.append(f"builtins.open(mode={_mode!r})")
        return _orig_open(*_a, **_k)

    builtins.open = _watch_open                    # type: ignore[assignment]
    _undo.append((builtins, "open", _orig_open))
    _installed.append("builtins.open")

    # ── Google Sheets 那一路：換掉**憑證**與**傳輸**兩個 seam ─────────────────
    # ⭐ **為什麼連「憑證」也要假造 —— 這是本檔最容易被做錯的一步。**
    #    CI 上沒有 service account，`services.nav_history_gs.is_enabled()` 回 `False`，
    #    於是**任何**寫入都會安靜 no-op（`written=0`）。
    #    也就是說：**一道只在「沒有憑證」的環境下綠的零寫入守衛，是假的** ——
    #    它證明的是「這台機器連不上」，不是「這一頁不會寫」。
    #    本組實測：不假造憑證時，把 `append_point(...)` 塞進渲染路徑**照樣全綠**。
    # ⚠️ 換的是**憑證來源**與**取得 client 的入口**，不是某幾個寫入函式 ——
    #    後者就是「函式名白名單」，本檔明令不用。
    _sh = _DenyByDefaultSpreadsheet(
        _DenyByDefaultWorksheet([["code", "nav_date", "nav"]], trips), trips)

    class _FakeClient:
        def open_by_key(self, *_a: Any, **_k: Any) -> Any:
            return _sh

        def open(self, *_a: Any, **_k: Any) -> Any:
            return _sh

        def __getattr__(self, name: str) -> Any:
            if name.startswith("_"):
                raise AttributeError(name)
            trips.append(f"gspread_client.{name}")
            return lambda *_a, **_k: _sh

    _FAKE_SA = {"client_email": "sentinel@example.invalid", "type": "service_account",
                "private_key": "-----BEGIN PRIVATE KEY-----\nx\n-----END PRIVATE KEY-----\n",
                "token_uri": "https://oauth2.googleapis.invalid/token",
                "project_id": "sentinel"}

    try:
        import infra.config as _cfg
    except Exception:                              # pragma: no cover
        _cfg = None
    if _cfg is not None and hasattr(_cfg, "get_secret"):
        _real_get_secret = _cfg.get_secret

        def _fake_get_secret(name: str, *_a: Any, **_k: Any) -> Any:
            if name == "google_service_account":
                return dict(_FAKE_SA)
            if name.endswith("SHEET_ID"):
                return "sentinel-sheet-id"
            return _real_get_secret(name, *_a, **_k)

        _cfg.get_secret = _fake_get_secret         # type: ignore[assignment]
        _undo.append((_cfg, "get_secret", _real_get_secret))
        _installed.append("infra.config.get_secret")

    _stubbed_mods: list[str] = []
    for _modname, _fnname in (("repositories.policy_repository", "get_gspread_client"),
                              ("infra.oauth", "get_gspread_client")):
        try:
            __import__(_modname)
        except Exception:
            # ⚠️ **這一段是為了不讓守衛「因為環境缺套件」而假綠**（照實寫）：
            #    `repositories.policy_repository` 在**沒有 `pandas`** 的環境
            #    連 import 都過不了，於是 `_get_sheet()` 會拋 ImportError、
            #    整條 Sheets 寫入路徑**根本走不到哨兵** —— 主規則會綠得毫無根據。
            #    ⛔ **只有在真的 import 不起來時才塞替身**；CI 上那個模組 import 得動，
            #    這一段完全不會執行（`_installed` 會列出實際走了哪一條）。
            import types as _types
            _stub = _types.ModuleType(_modname)
            setattr(_stub, _fnname, lambda *_a, **_k: _FakeClient())
            sys.modules[_modname] = _stub
            _stubbed_mods.append(_modname)
            _installed.append(f"{_modname}.{_fnname}(stub:模組 import 不起來)")
            continue
        _mod = sys.modules.get(_modname)
        if _mod is not None and hasattr(_mod, _fnname):
            _orig_fn = getattr(_mod, _fnname)
            setattr(_mod, _fnname, lambda *_a, **_k: _FakeClient())
            _undo.append((_mod, _fnname, _orig_fn))
            _installed.append(f"{_modname}.{_fnname}")
    try:
        yield _installed
    finally:
        for _owner, _attr, _orig in reversed(_undo):
            setattr(_owner, _attr, _orig)
        for _m in _stubbed_mods:
            sys.modules.pop(_m, None)


def _render_and_watch(**kw: Any) -> list[str]:
    """渲染一輪（**沒有按任何按鈕**）並回傳哨兵記到的寫入。"""
    _trips: list[str] = []
    with _sentinels(_trips):
        _render(**kw)
    return _trips


# ══════════════════════════════════════════════════════════════════════
# 正對照 —— 哨兵沒瞎（沒有這一節，下面的「全綠」就沒有意義）
# ══════════════════════════════════════════════════════════════════════

def test_the_sentinel_records_instead_of_raising():
    """哨兵被碰到時**記一筆並回 None**，不得拋例外。"""
    _trips: list[str] = []
    _ws = _DenyByDefaultWorksheet([], _trips)
    _ws.append_row(["a"])
    _ws.update("A1", [["b"]])
    assert _trips == ["worksheet.append_row", "worksheet.update"], _trips


def test_a_swallowing_caller_cannot_hide_a_write():
    """⭐ 呼叫端包了 `try/except Exception` 也藏不住 —— 這就是「不拋例外」的用處。

    ⚠️ **對照組**：若哨兵改成拋例外，下面這個 `except Exception: pass`
    會把它整個吃掉，`trips` 是空的、測試通過、而寫入其實發生過。
    """
    _trips: list[str] = []
    _ws = _DenyByDefaultWorksheet([], _trips)
    try:
        _ws.append_rows([["x"]])
    except Exception:                              # noqa: BLE001
        pass
    assert _trips == ["worksheet.append_rows"]


def test_a_write_passed_as_an_argument_is_caught():
    """⭐ 把寫入方法**當引數傳給包裝器**，一樣要記到。

    這是 ④ 那份靜態規則的 `ast.Attribute` 那一半的**行為層版本**：
    `_with_quota_retry(ws.append_row, …)` 沒有以 `ws.append_row(...)` 的形狀出現，
    只看呼叫節點的偵測器看不到它。哨兵在**取屬性**時就記，所以看得到。
    """
    _trips: list[str] = []
    _ws = _DenyByDefaultWorksheet([], _trips)

    def _with_quota_retry(fn, *args):
        return fn(*args)

    _with_quota_retry(_ws.append_row, ["y"])
    assert _trips == ["worksheet.append_row"]


def test_a_name_assembled_at_runtime_is_caught():
    """⭐ `getattr(ws, "append" + "_row")` —— 名字怎麼組出來的，哨兵不在乎。

    ⚠️ ④ 那份靜態守衛就地登記「`getattr` 家族整族看不見」；
    **這一族只有行為層攔得到**，本條是那句話的證明。
    """
    _trips: list[str] = []
    _ws = _DenyByDefaultWorksheet([], _trips)
    getattr(_ws, "append" + "_row")(["z"])
    _m = "update_cell"
    getattr(_ws, _m)(1, 1, "v")
    assert _trips == ["worksheet.append_row", "worksheet.update_cell"]


def test_a_pure_read_is_not_recorded_as_a_write():
    """讀不算寫 —— 否則這道守衛會變成「只要碰試算表就紅」，沒人用得下去。"""
    _trips: list[str] = []
    _ws = _DenyByDefaultWorksheet([["a", "b"]], _trips)
    _ws.get_all_values()
    _ws.row_values(1)
    assert _trips == []


def test_the_disk_sentinels_really_install_themselves():
    """磁碟哨兵真的被裝上去了 —— 沒有這一條，下面的全綠可能只是沒裝。"""
    _trips: list[str] = []
    with _sentinels(_trips) as _installed:
        assert "pathlib.Path.write_text" in _installed, _installed
        assert "builtins.open" in _installed, _installed
        pathlib.Path("/tmp/never-written-by-this-test").write_text("x")
        os.makedirs("/tmp/never-made-by-this-test", exist_ok=True)
    assert "pathlib.Path.write_text" in _trips and "os.makedirs" in _trips, _trips
    assert not pathlib.Path("/tmp/never-written-by-this-test").exists(), (
        "哨兵沒有攔住 `write_text` —— 檔案真的被寫出去了。")


def test_the_sentinels_are_removed_afterwards():
    """`with` 出來之後一切還原 —— 一個沒還原的哨兵會污染同一輪的其他測試。"""
    _before = (pathlib.Path.write_text, os.makedirs, builtins.open)
    with _sentinels([]):
        pass
    assert (pathlib.Path.write_text, os.makedirs, builtins.open) == _before


# ══════════════════════════════════════════════════════════════════════
# 主規則 —— 打開這一頁不會動到任何東西
# ══════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("label,kw", [
    ("還沒搜尋", {}),
    ("送出了搜尋、取數全敗", {"applied": _APPLIED}),
    ("批次已送出、還沒跑完", {"applied": _APPLIED,
                             "session": {"v03_research_batch_codes": ["AAA"],
                                         "v03_research_batch_rows": {}}}),
    ("使用者在框裡打了字但沒按送出", {"applied": _APPLIED,
                                     "widget": {"基金代碼（每行一檔）": "AAA\nBBB"}}),
])
def test_rendering_this_page_writes_nothing(label: str, kw: dict):
    """⭐ **本檔的本體：使用者只是打開這一頁，不得動到磁碟或他的 Google Sheet。**

    四種處境各跑一次 —— **「沒按送出但框裡有字」那一格是刻意的**：
    它是「重運算沒有被 gate 住」最會發作的形狀，而寫入常常就跟在重運算後面。

    **紅了要做什麼**：看那一筆寫入是從哪裡來的。
    - 它應該被使用者的意圖擋住 → **把它移到 `if st.button(...)` / 送出閘門的正分支裡**。
    - 它是渲染必須的 → **那就是設計問題**，不是測試問題（客戶：「直接切斷寫入」）。

    ⛔ **絕對不要**用「加一個 session 旗標」讓本條變綠 ——
       那只把「每個 session 寫一次」變成「少寫幾次」，**少寫幾次不叫切斷**。
    """
    _trips = _render_and_watch(**kw)
    assert not _trips, (
        f"③（處境：{label}）只是被渲染一輪，就動到了下列東西：\n  "
        + "\n  ".join(_trips)
        + "\n\n客戶 2026-09-06 永久授權逐字：「絕對禁止反向寫入我的 Google Sheet…"
          "不用問我，直接切斷寫入！」")


def test_a_write_hidden_behind_a_whitelisted_module_is_still_caught():
    """⭐⭐ **本檔存在的第一理由：分層白名單擋不住的那個洞。**

    本 repo 實測過的缺口：分層守衛只黑名單「import 來源套件」
    （`repositories` / `infra` / `requests` / …），而 **`services.nav_history_gs`
    —— 真正會寫 Google Sheet 的那一支 —— 在白名單內**。
    把 `append_point(...)` 放進渲染函式，**87 個測試照樣全綠**。

    本條把那個洞做成一顆**常駐的突變**：把一支「名字完全清白、來源完全合法」的
    寫入函式塞進渲染路徑，本檔必須紅。

    ⚠️ **塞的是真的那一支，而且不注入任何替身參數** —— 它自己去要憑證、自己去開表，
    走的是 production 一模一樣的那條路；被換掉的只有**憑證來源**與**取得 client 的入口**
    （見 :func:`_sentinels` 的 ⭐ 段）。用假件只能證明「哨兵會記假件」，
    證不到「真的寫入路徑會撞上哨兵」。
    """
    import services.nav_history_gs as _nh
    assert hasattr(_nh, "append_point"), (
        "`services.nav_history_gs.append_point` 不見了（改名了？）—— "
        "本條的突變失去對象，請換一支**真的會寫**的函式，不要把本條刪掉。")

    _page = sys.modules[_PAGE]
    _orig = _page._render_batch

    def _leaky() -> None:
        _orig()
        # ⬇️ 名字清白、來源在白名單內、也沒有任何 `st.button` 擋著 —— 就是那個洞。
        _nh.append_point("AAA", 10.0, "2024-01-02")

    _page._render_batch = _leaky
    try:
        _trips = _render_and_watch(applied=_APPLIED)
    finally:
        _page._render_batch = _orig
    assert _trips, (
        "把 `services.nav_history_gs.append_point(...)` 放進渲染路徑之後，"
        "本檔**沒有轉紅** —— 這道守衛是空的。")
    assert any(_t.startswith("worksheet.") for _t in _trips), (
        f"記到的不是試算表寫入：{_trips}")
def test_the_same_write_behind_a_submit_is_allowed():
    """⭐ 反面：同一筆寫入**擋在按鈕後面**就不該紅。

    沒有這一條，上一條的紅只證明「哨兵會響」，證不到它響的是**正確的東西** ——
    一個「碰到就紅」的守衛會逼所有人把寫入拆掉，包括合法的那些。
    ⚠️ recorder 對按鈕恆回 `False` ＝ **沒有人按** ⇒ 那一行不會執行。
    """
    import streamlit as _st

    import services.nav_history_gs as _nh
    _page = sys.modules[_PAGE]
    _orig = _page._render_batch

    def _gated() -> None:
        _orig()
        if _st.button("寫一筆"):
            _nh.append_point("AAA", 10.0, "2024-01-02")

    _page._render_batch = _gated
    try:
        _trips = _render_and_watch(applied=_APPLIED)
    finally:
        _page._render_batch = _orig
    assert not _trips, (
        "寫入明明在 `if st.button(...)` 的正分支裡（而且沒有人按），卻被記成寫入：\n  "
        + "\n  ".join(_trips))
def test_a_plain_disk_write_from_the_render_path_is_caught():
    """⭐ 磁碟那一半也要能從**渲染路徑內**撞上哨兵，不只是在單元測試裡。

    ⚠️ 這一條與 :func:`test_the_disk_sentinels_really_install_themselves` **不同**：
    那一條驗「哨兵裝得上」，本條驗「哨兵在**渲染那一段**是活的」——
    中間任何一層（`safe_section` 的 try/except、模組替換的順序）出錯，
    都只會在這裡被看見。
    """
    _page = sys.modules[_PAGE]
    _orig = _page._render_batch

    def _leaky() -> None:
        _orig()
        pathlib.Path("/tmp/wf03-should-never-exist.txt").write_text("x")

    _page._render_batch = _leaky
    try:
        _trips = _render_and_watch(applied=_APPLIED)
    finally:
        _page._render_batch = _orig
    assert "pathlib.Path.write_text" in _trips, (
        f"渲染路徑裡的磁碟寫入沒有被記到：{_trips}")
    assert not pathlib.Path("/tmp/wf03-should-never-exist.txt").exists(), (
        "哨兵沒有攔住它 —— 檔案真的被寫出去了。")


def test_the_credential_seam_is_installed_or_says_why_not():
    """憑證 seam 有沒有真的換掉 —— **沒換掉的話整條 Sheets 路徑會因為「沒有憑證」而假綠。**

    ⚠️ 本條驗的是 :func:`_sentinels` 自己，不是被測頁。
    `infra.config.get_secret` 一定換得掉（純 stdlib）；
    `repositories.policy_repository.get_gspread_client` 在**缺 pandas 的環境**
    import 不起來，那時它不會被換 —— 本條把這個事實**寫出來**而不是靜靜放過。
    """
    _trips: list[str] = []
    with _sentinels(_trips) as _installed:
        assert "infra.config.get_secret" in _installed, (
            f"憑證來源沒有被換掉 —— Sheets 那一路會因為 `is_enabled()` 回 False "
            f"而全部安靜 no-op，整條守衛變成假綠。實際裝上的：{_installed}")
        import services.nav_history_gs as _nh
        assert _nh.is_enabled(), (
            "假憑證裝上了，但 `nav_history_gs.is_enabled()` 仍然是 False —— "
            "seam 換錯地方了。")
# ══════════════════════════════════════════════════════════════════════
# 為什麼不做靜態閉包掃描 —— 把理由變成一條可執行的斷言
# ══════════════════════════════════════════════════════════════════════

_SINK_NAMES = frozenset({
    "append_row", "append_rows", "update", "batch_update", "update_cell",
    "update_cells", "update_acell", "insert_row", "insert_rows", "add_worksheet",
    "del_worksheet", "delete_rows", "delete_columns", "clear", "resize",
    "values_append", "values_update", "values_clear",
    "write_text", "write_bytes", "mkdir", "makedirs", "touch", "unlink",
    "rmdir", "remove", "rename", "replace", "to_csv", "to_parquet", "to_json",
})
_REPO_ROOTS = ("ui", "services", "shared", "repositories", "infra")


def _closure(root: str = _PAGE) -> dict:
    def _path(mod: str):
        _p = _REPO / (mod.replace(".", "/") + ".py")
        if _p.exists():
            return _p
        _pkg = _REPO / mod.replace(".", "/") / "__init__.py"
        return _pkg if _pkg.exists() else None

    _seen: dict = {}
    _stack = [root]
    while _stack:
        _m = _stack.pop()
        if _m in _seen:
            continue
        _p = _path(_m)
        if _p is None:
            continue
        _seen[_m] = _p
        _tree = ast.parse(_p.read_text(encoding="utf-8"))
        for _n in ast.walk(_tree):
            _mods: list[str] = []
            if isinstance(_n, ast.Import):
                _mods = [_a.name for _a in _n.names]
            elif isinstance(_n, ast.ImportFrom) and _n.level == 0 and _n.module:
                _mods = [_n.module] + [f"{_n.module}.{_a.name}" for _a in _n.names]
            for _x in _mods:
                if _x.split(".")[0] in _REPO_ROOTS and _x not in _seen:
                    _stack.append(_x)
    return _seen


def test_a_whole_closure_name_scan_would_be_useless_here():
    """⭐ 把「為什麼不照抄 ④ 那份靜態守衛」變成**可執行的證據**，而不是一句宣稱。

    ⚠️ 這一條不守任何行為 —— 它守的是**模組 docstring 裡那段理由沒有腐爛**。
    哪天 ③ 的閉包縮小到跟 ④ 一樣乾淨（例如取數整條下沉到別的地方），
    本條會轉紅，而那正是「該回頭加上靜態層」的訊號。

    ⛔ **紅了不要把數字調大** —— 要問的是「閉包為什麼變小了 / 變大了」。
    """
    _c = _closure()
    assert _PAGE in _c, f"閉包裡沒有本頁自己 —— `{_PAGE}` 解析失敗了？"
    assert len(_c) >= 30, (
        f"③ 的 import 閉包只剩 {len(_c)} 個模組（本組 2026-09-07 實測是 56）。\n"
        "它若真的縮到跟 ④ 一樣小（11 個），靜態層就變得可行了 —— "
        "**請回頭評估要不要補上那一層**，不要只是把這個數字改掉。")
    _hits = 0
    for _p in _c.values():
        _tree = ast.parse(_p.read_text(encoding="utf-8"))
        _hits += sum(1 for _n in ast.walk(_tree)
                     if isinstance(_n, ast.Attribute) and _n.attr in _SINK_NAMES)
    assert _hits >= 50, (
        f"用 ④ 那份 sink 名單掃 ③ 的閉包只命中 {_hits} 個節點"
        "（本組 2026-09-07 實測是 106，壓倒性多數是 `str.replace` / `dict.update` / "
        "`set.clear` 這些偽陽性）。\n"
        "若它真的降到可以逐一判讀的量，靜態層就值得補上了。")
