"""tests/test_weights_store_read_no_writes.py — 總經權重 active override：讀路徑零寫入守衛。

**這個檔在守什麼(2026-09-07)**
------------------------------
`services/macro/weights_store.py` 曾經是本 repo「**名字像讀取、底下卻在寫客戶
Google Sheet**」的第三個(也是最後一個已知的)實例 —— 前兩個是
`repositories/pool_repository.py`(#796)與 `repositories/portfolio_perf_repository.py`(#800)。

病灶形狀:`load_active()` → `_gs_load()` → `_gs_get_worksheet()`,
最底下那層在**分頁不存在時** `add_worksheet(...)` + `update("A1:C3", ...)`。
`get_phase_thresholds` / `get_verdict_cutoffs` / `get_weight_override`
三個 getter **全部**經過 `load_active`,所以光是算一次總經分數就會寫一次表。
觸發條件綁在**遠端狀態**、不綁在使用者意圖 → 平常測不出來、log 也看不到。

**為什麼守衛長這樣(這一段比測試本身重要)**
------------------------------------------
⛔ **不是**攔函式名、**不是**攔 import 來源白名單。本 repo 已實測那種守衛擋不住
`from m import f as _g` / `importlib.import_module("a"+"b")` / `g = m.f` 再 `g()` / `getattr`,
而且曾在 bug 活著的時候 20/20 全綠。

✅ 本檔改為**在物件邊界上攔底層寫入動作本身**:餵給待測程式的假 spreadsheet /
worksheet 會記下**每一次對寫入方法的屬性存取**(`__getattr__`),而不只是呼叫。
- 這同時涵蓋 `ast.Call`(`ws.update(...)`)**與** `ast.Attribute`
  (`wrap(ws.update)` —— 把寫入方法**當引數傳給包裝器**)。
  後者正是 #796 的守衛被打穿的那一招(代號 M5c):只掃 `ast.Call` 看不到它。
- 不論呼叫端怎麼拼字、怎麼繞 import,只要那個方法被碰到就會留名。

⚠️ **哨兵記名、不拋例外**:會 raise 的哨兵會被上層 `try/except` 吃掉,等於沒有守衛。
本檔的哨兵一律「記下來、回一個 no-op」,由測試在事後檢查名單。

⚠️ **每一條零寫入斷言都配一個正對照**,否則「零」可能只是因為哨兵根本沒接上:
- :func:`test_sentinel_can_actually_see_a_write` —— 哨兵自我證明(看得到寫入);
- :func:`test_read_path_with_worksheet_present_also_writes_nothing` —— 分頁存在時
  同一條讀路徑照樣是零,證明零不是靠「一律短路」換來的。
"""
from __future__ import annotations

import ast
import json
import pathlib
import sys
import types

import pytest

from services.macro import weights_store as store

_TARGET = pathlib.Path(store.__file__)

# gspread 上會動到遠端試算表的方法名。寧可多列,不可漏列 —— 這裡漏一個,
# 就等於在守衛上開一個洞(同 CLAUDE.md §-1.5.1c 判定 2「字表選錯,掃再多次都沒用」)。
_WRITE_METHOD_NAMES = frozenset({
    "add_worksheet", "del_worksheet", "duplicate_sheet", "add_rows", "add_cols",
    "update", "update_acell", "update_cell", "update_cells", "update_title",
    "update_index", "append_row", "append_rows", "insert_row", "insert_rows",
    "insert_note", "batch_update", "batch_clear", "clear", "clear_note",
    "delete_rows", "delete_columns", "resize", "sort", "merge_cells", "format",
    "values_update", "values_append", "values_clear", "values_batch_update",
})


# ════════════════════════════════════════════════════════════════
# 哨兵與假件（全離線；⛔ 本檔不會、也不能連到任何真的 Google Sheet）
# ════════════════════════════════════════════════════════════════
class _WriteSentinel:
    """記名不拋例外的寫入哨兵。

    `touched` 記「屬性被取出來」(涵蓋把方法當引數傳走的形狀),
    `called` 記「真的被呼叫」。斷言看 `touched`,因為它是兩者的超集。
    """

    def __init__(self) -> None:
        self.touched: list[str] = []
        self.called: list[str] = []

    def touch(self, name: str) -> None:
        self.touched.append(name)

    def call(self, name: str) -> None:
        self.called.append(name)

    @property
    def writes_touched(self) -> list[str]:
        return [n for n in self.touched if n in _WRITE_METHOD_NAMES]


class _Cell:
    def __init__(self, value): self.value = value


class _FakeWorksheet:
    """只實作讀取方法；其餘一律經 `__getattr__` 留名後回 no-op。"""

    def __init__(self, sentinel: _WriteSentinel, title: str, cells=None) -> None:
        self.__dict__["_sentinel"] = sentinel
        self.__dict__["title"] = title
        self.__dict__["_cells"] = dict(cells or {})

    # ── 讀取（明確定義 → 不會走 __getattr__，也就不會被記名） ──
    def acell(self, ref: str) -> _Cell:
        return _Cell(self.__dict__["_cells"].get(ref))

    def row_values(self, n: int) -> list[str]:
        return ["slot", "payload_json", "updated_at"] if n == 1 else []

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        self.__dict__["_sentinel"].touch(name)
        sentinel = self.__dict__["_sentinel"]

        def _recorder(*_a, **_k):
            sentinel.call(name)
            return None
        return _recorder


class _FakeSpreadsheet:
    def __init__(self, sentinel, existing: dict, read_error=None) -> None:
        self.__dict__["_sentinel"] = sentinel
        self.__dict__["_existing"] = existing
        self.__dict__["_read_error"] = read_error

    def worksheet(self, title: str):
        err = self.__dict__["_read_error"]
        if err is not None:                       # 模擬 403/429/5xx/連線中斷
            raise err
        existing = self.__dict__["_existing"]
        if title not in existing:                 # 模擬 gspread WorksheetNotFound
            raise Exception(f"WorksheetNotFound: {title}")
        return existing[title]

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        sentinel = self.__dict__["_sentinel"]
        sentinel.touch(name)

        def _recorder(*a, **k):
            sentinel.call(name)
            if name == "add_worksheet":           # 建表成功 → 回一張新的假分頁
                ws = _FakeWorksheet(sentinel, k.get("title") or (a[0] if a else "?"))
                self.__dict__["_existing"][ws.title] = ws
                return ws
            return None
        return _recorder


def _install(monkeypatch, sentinel, existing: dict, read_error=None) -> None:
    """把 `_gs_get_worksheet` 內部兩個 lazy import 的來源模組換成假件。

    ⚠️ **刻意不 monkeypatch `store._gs_get_worksheet` 本身** —— 既有的
    `tests/test_macro_weights_store.py::_gs_backend` 就是整個換掉它，
    於是**這個 bug 在它底下活了下來**（那條路從來沒有被執行過）。
    本檔要跑的是**真的那一段**，所以只換它腳下的地基。
    """
    secrets = {"google_service_account": {"client_email": "svc@example.iam"},
               "macro_weights_sheet_id": "FAKE_SHEET_ID_NOT_A_REAL_SHEET"}
    cfg = types.ModuleType("infra.config")
    cfg.get_secret = lambda k, d=None: secrets.get(k, d)          # type: ignore[attr-defined]
    cfg.require_secret = lambda k: secrets[k]                     # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "infra.config", cfg)

    pol = types.ModuleType("repositories.policy_repository")
    pol.get_gspread_client = lambda creds: types.SimpleNamespace(  # type: ignore[attr-defined]
        open_by_key=lambda sid: _FakeSpreadsheet(sentinel, existing, read_error))
    monkeypatch.setitem(sys.modules, "repositories.policy_repository", pol)


_GOOD_PAYLOAD = '{"version": "v19.0", "indicators": {"vix": {"weight": 2.5}}}'


def _sheet_with_payload(sentinel, payload: str = _GOOD_PAYLOAD) -> dict:
    return {store._GS_WORKSHEET: _FakeWorksheet(
        sentinel, store._GS_WORKSHEET,
        {"A1": "slot", "B1": "payload_json", "C1": "updated_at",
         "A3": "active", "B3": payload, "C3": ""})}


# ════════════════════════════════════════════════════════════════
# 1. 哨兵自我證明（沒有這條，下面所有「零寫入」都可能是假的）
# ════════════════════════════════════════════════════════════════
def test_sentinel_can_actually_see_a_write(monkeypatch):
    """正對照：走**寫入**路徑時哨兵必須看得到 `add_worksheet` 與 `update`。

    這條同時是「寫入路徑沒有被切過頭」的驗收（⛔ 不要切過頭）：
    分頁不存在時 `for_write=True` 仍會建表 + 寫表頭，行為與修復前逐字相同。
    """
    sentinel = _WriteSentinel()
    _install(monkeypatch, sentinel, existing={})
    ws = store._gs_get_worksheet(for_write=True)
    assert ws is not None
    assert "add_worksheet" in sentinel.called, "寫入路徑不再建表 = 切過頭了"
    assert "update" in sentinel.called, "寫入路徑不再補表頭 = 切過頭了"
    assert sentinel.writes_touched, "哨兵沒接上：它連真的寫入都看不到，下面的斷言全是假的"


# ════════════════════════════════════════════════════════════════
# 2. 讀路徑零寫入（負對照 = 分頁不存在，正是舊 bug 的觸發條件）
# ════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("call", [
    pytest.param(lambda: store.load_active(), id="load_active"),
    pytest.param(lambda: store.get_phase_thresholds(), id="get_phase_thresholds"),
    pytest.param(lambda: store.get_verdict_cutoffs(), id="get_verdict_cutoffs"),
    pytest.param(lambda: store.get_weight_override("vix", 1.0), id="get_weight_override"),
    pytest.param(lambda: store.apply_weight_overrides({"vix": {"weight": 1.0}}),
                 id="apply_weight_overrides"),
])
def test_read_path_writes_nothing_when_worksheet_missing(monkeypatch, call):
    sentinel = _WriteSentinel()
    _install(monkeypatch, sentinel, existing={})
    call()
    assert sentinel.writes_touched == [], (
        f"讀路徑動到了客戶的試算表：{sentinel.writes_touched}（touched={sentinel.touched}）")


def test_read_path_with_worksheet_present_also_writes_nothing(monkeypatch):
    """正對照：分頁存在且表頭正確時，同一條讀路徑照樣零寫入，而且真的讀到 payload。

    有這條，上面的「零」才不會只是「短路了所以什麼都沒做」。
    """
    sentinel = _WriteSentinel()
    _install(monkeypatch, sentinel, existing=_sheet_with_payload(sentinel))
    out = store.load_active()
    assert out["indicators"]["vix"]["weight"] == 2.5, "正對照沒有真的讀到 payload"
    assert sentinel.writes_touched == []


def test_missing_worksheet_is_a_legal_empty_state(monkeypatch):
    """分頁不存在 = 合法的空狀態 → 回 `_empty_active()`，下游回退硬編碼，**不 raise**。"""
    sentinel = _WriteSentinel()
    _install(monkeypatch, sentinel, existing={})
    assert store.load_active()["indicators"] == {}
    assert store.get_phase_thresholds() == store._DEFAULT_PHASE_THRESHOLDS
    assert store.get_verdict_cutoffs() == store._DEFAULT_VERDICT_CUTOFFS
    assert sentinel.writes_touched == []


# ════════════════════════════════════════════════════════════════
# 3. §1 Fail Loud：讀失敗不得被壓成「沒有設定」
# ════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("exc", [
    pytest.param(Exception("APIError: [403] The caller does not have permission"), id="403"),
    pytest.param(Exception("APIError: [429] RESOURCE_EXHAUSTED: Quota exceeded"), id="429"),
    pytest.param(Exception("APIError: [500] Internal error encountered"), id="5xx"),
    pytest.param(ConnectionError("Connection reset by peer"), id="connection-reset"),
])
def test_read_failure_propagates_and_writes_nothing(monkeypatch, exc):
    """403 / 429 / 5xx / 連線中斷 → **往上拋**，而且過程中一格都不碰。

    ⛔ 不得靜默退回 `_empty_active()`：`load_active()` 的回傳是總經評分的
    active override，把「讀不到」講成「沒有設定」＝ 使用者以為自己的校準生效了，
    實際上分數正在用硬編碼預設值，畫面上不會有任何一處顯示異常（CLAUDE.md §1）。
    """
    sentinel = _WriteSentinel()
    _install(monkeypatch, sentinel, existing={}, read_error=exc)
    with pytest.raises(type(exc)):
        store.load_active()
    assert sentinel.writes_touched == [], "讀失敗時還去寫表：正是修復前的行為"


@pytest.mark.parametrize("exc", [
    pytest.param(Exception("APIError: [403] permission denied"), id="403"),
    pytest.param(ConnectionError("connection aborted"), id="connection-aborted"),
])
def test_read_failure_is_not_classified_as_missing_worksheet(exc):
    """`_is_missing_worksheet` 的**否定側**：讀失敗一律 False（＝往上拋）。"""
    assert store._is_missing_worksheet(exc) is False


def test_missing_worksheet_is_classified_as_missing():
    """`_is_missing_worksheet` 的**肯定側**：真的沒有分頁才 True。

    duck-typed（名字或訊息），因為 CI 精簡環境沒有裝 gspread。
    """
    assert store._is_missing_worksheet(Exception("WorksheetNotFound: _macro_weights")) is True

    class WorksheetNotFound(Exception):
        pass
    assert store._is_missing_worksheet(WorksheetNotFound("nope")) is True


# ════════════════════════════════════════════════════════════════
# 4. 結構守衛（AST）：寫入只准住在一個函式裡，且那個函式有 for_write 門
# ════════════════════════════════════════════════════════════════
def _write_name_nodes(tree: ast.AST) -> list[ast.Attribute]:
    """所有指向寫入方法的 `ast.Attribute` 節點。

    ⚠️ **刻意不是只掃 `ast.Call`** —— `wrap(ws.update)` 這種「把寫入方法當引數
    傳給包裝器」的形狀是 `ast.Attribute`，#796 的守衛就是被這一招打穿的（M5c）。
    `ast.Call` 的 func 本身就是 `ast.Attribute`，所以掃 Attribute 是兩者的超集。
    """
    return [n for n in ast.walk(tree)
            if isinstance(n, ast.Attribute) and n.attr in _WRITE_METHOD_NAMES]


def test_ast_scanner_is_not_vacuous():
    """掃描器三件套之一：**輸入非空** + **正對照** + **負對照**。"""
    src = _TARGET.read_text(encoding="utf-8")
    assert src.strip(), "輸入是空的：整組 AST 斷言會空轉"

    # 正對照：一份確定含寫入的來源，掃描器必須看得到（含 Attribute-only 形狀）
    positive = ast.parse("def f(sh):\n    wrap(sh.add_worksheet)\n    sh.worksheet('x').update('A1', [[1]])\n")
    got = sorted({n.attr for n in _write_name_nodes(positive)})
    assert got == ["add_worksheet", "update"], got

    # 負對照：一份確定不含寫入的來源，掃描器必須回空
    negative = ast.parse("def f(ws):\n    return ws.acell('B3').value\n")
    assert _write_name_nodes(negative) == []


def test_write_calls_are_confined_to_the_single_for_write_door():
    """全模組的寫入方法名，只准出現在 `_gs_get_worksheet` 裡。

    再多一個地方出現，就表示又有一條寫入偷偷長回讀路徑上。
    """
    tree = ast.parse(_TARGET.read_text(encoding="utf-8"))
    door = next((n for n in ast.walk(tree)
                 if isinstance(n, ast.FunctionDef) and n.name == "_gs_get_worksheet"), None)
    assert door is not None, "_gs_get_worksheet 不見了：這個守衛的前提已經不成立"

    inside = {id(n) for n in _write_name_nodes(door)}
    outside = [f"{n.attr}@line{n.lineno}" for n in _write_name_nodes(tree) if id(n) not in inside]
    assert outside == [], f"寫入方法出現在 `_gs_get_worksheet` 以外：{outside}"
    assert inside, "`_gs_get_worksheet` 裡一個寫入都沒有 → 建表能力被整個刪掉了（切過頭）"


def test_the_door_is_keyword_only_and_defaults_to_read_only():
    """`for_write` 必須是 **keyword-only** 且預設 `False`。

    keyword-only 是為了讓「不小心用位置參數把它打開」不可能發生；
    預設 False 是為了讓**忘記想這件事的人自動落在唯讀那一邊**。
    """
    tree = ast.parse(_TARGET.read_text(encoding="utf-8"))
    door = next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "_gs_get_worksheet")
    assert [a.arg for a in door.args.args] == [], "for_write 不得是位置參數"
    names = [a.arg for a in door.args.kwonlyargs]
    assert names == ["for_write"], names
    default = door.args.kw_defaults[names.index("for_write")]
    assert isinstance(default, ast.Constant) and default.value is False


def test_gs_load_returns_none_when_worksheet_missing(monkeypatch):
    """`_gs_load` 必須看得懂 `None`（分頁還沒建），而不是往 `None.acell` 撞上去。"""
    sentinel = _WriteSentinel()
    _install(monkeypatch, sentinel, existing={})
    assert store._gs_load("active") is None
    assert sentinel.writes_touched == []


def test_gs_load_reads_payload_when_worksheet_present(monkeypatch):
    sentinel = _WriteSentinel()
    _install(monkeypatch, sentinel, existing=_sheet_with_payload(sentinel))
    assert store._gs_load("active") == json.loads(_GOOD_PAYLOAD)
    assert sentinel.writes_touched == []
