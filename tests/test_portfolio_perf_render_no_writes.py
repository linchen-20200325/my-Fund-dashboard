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
  ⇒ 這正是本檔**不**做 `import` 來源白名單、也**不**比對函式名的原因：
  `from m import f as _g` / `importlib.import_module("a."+"b")` / `g = m.f` 再 `g()` / `getattr`
  這四種寫法在本 repo 都實測繞得過名字型守衛，但**繞不過「真的被呼叫到」**。

**看不見（已知缺口，不要當成保證）**

* **哨兵只在渲染那一小段生命週期內生效**；渲染之外的寫入本檔看不到。
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


def _render(monkeypatch, *, rows: "list[list[str]] | None", pressed: "set[str] | None" = None
            ) -> "tuple[list[str], _Rec]":
    """裝好兩層哨兵 → 真的渲染一輪 → 回傳 (寫入紀錄, 錄影機)。"""
    trips: list[str] = []
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
def _tree(rel: str) -> ast.Module:
    return ast.parse((ROOT / rel).read_text(encoding="utf-8"))


def _func(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"找不到函式 {name}()")


def _calls(node: ast.AST) -> "list[str]":
    out = []
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            f = n.func
            out.append(f.id if isinstance(f, ast.Name)
                       else f.attr if isinstance(f, ast.Attribute) else "")
    return out


def test_the_render_function_never_calls_the_writer_directly():
    """`render_portfolio_tracking()` 自己**不得**出現 `append_snapshot` ——
    寫入只能經由 :func:`_snapshot_control`（而它由按鈕守著）。

    ⚠️ 本條是**結構**輔助，不是主守衛：改個別名就繞得過去。
    真正擋得住的是上面那組行為測試（哨兵不看名字，只看有沒有真的被呼叫到）。
    兩條並存的理由是**壞掉的方式不同** —— 結構這條會在 code review 的
    diff 上直接顯眼，行為那條會在 CI 上轉紅。

    突變驗證：在 `render_portfolio_tracking` 內加一行 `append_snapshot(...)` → 本條轉紅。
    """
    fn = _func(_tree(SECTION_REL), "render_portfolio_tracking")
    bad = [c for c in _calls(fn) if c in ("append_snapshot", "_maybe_snapshot")]
    assert not bad, (
        "`render_portfolio_tracking()` 直接呼叫了寫入函式 —— 渲染就會寫：\n  "
        f"{bad}\n寫入只能放在 `_snapshot_control()` 內、按鈕的 `if` 正分支裡。")


def test_the_write_lives_inside_the_button_branch():
    """`append_snapshot` 必須在「按鈕回 True」的 `if` **正分支**底下。

    偵測方式：`_snapshot_control()` 內若有 `if not <clicked>: return` 這種提前退出，
    其後的 body 就等價於正分支。本條要求兩者之一成立，並且 `st.button` 真的存在。

    突變驗證：把 `if not _clicked: return` 拿掉 → 本條轉紅。
    """
    fn = _func(_tree(SECTION_REL), "_snapshot_control")
    assert "button" in _calls(fn), "`_snapshot_control()` 裡沒有 `st.button` —— 沒有任何明示動作可言"

    guards = [n for n in fn.body
              if isinstance(n, ast.If)
              and isinstance(n.test, ast.UnaryOp) and isinstance(n.test.op, ast.Not)
              and any(isinstance(s, ast.Return) for s in n.body)]
    assert guards, (
        "`_snapshot_control()` 沒有「沒按就 return」的提前退出 —— "
        "無法確認 `append_snapshot` 只在按下之後才走得到")
    guard_at = fn.body.index(guards[0])
    before = [c for stmt in fn.body[:guard_at] for c in _calls(stmt)]
    assert "append_snapshot" not in before, (
        "`append_snapshot` 出現在「沒按就 return」之前 —— 那等於沒有閘門")
    after = [c for stmt in fn.body[guard_at + 1:] for c in _calls(stmt)]
    assert "append_snapshot" in after, (
        "閘門之後找不到 `append_snapshot` —— 按下按鈕也不會寫，功能是壞的")


def test_the_read_path_does_not_reach_the_provisioning_helper():
    """`GoogleSheetsPerfStore.load_snapshots()` 不得碰 `_ws_for_write`。

    突變驗證：把 `load_snapshots` 的 `self._ws()` 改成 `self._ws_for_write()` → 本條轉紅。
    """
    tree = _tree(REPO_REL)
    cls = next(n for n in ast.walk(tree)
               if isinstance(n, ast.ClassDef) and n.name == "GoogleSheetsPerfStore")
    load = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "load_snapshots")
    assert "_ws_for_write" not in _calls(load), (
        "讀路徑走到了會補建分頁的 `_ws_for_write()` —— 那正是 2026-09-06 之前的病灶")
    write = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "append_snapshot")
    assert "_ws_for_write" in _calls(write), (
        "寫路徑沒有走 `_ws_for_write()` —— 遠端還沒有分頁時第一次存會失敗")


def test_the_readonly_opener_contains_no_write_verbs():
    """`_ws()`（唯讀開啟）內不得出現 `add_worksheet` / `update` 這類動詞。

    ⚠️ 這是**字面**檢查，改個別名就繞得過 —— 它的價值在於讓「有人把補建搬回來」
    這件事在 diff 上一眼看得見。真正擋得住的是
    :func:`test_read_path_never_provisions_the_sheet`（行為，不看名字）。
    """
    cls = next(n for n in ast.walk(_tree(REPO_REL))
               if isinstance(n, ast.ClassDef) and n.name == "GoogleSheetsPerfStore")
    ws = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "_ws")
    bad = [c for c in _calls(ws) if c in ("add_worksheet", "update", "append_row", "batch_update")]
    assert not bad, f"唯讀開啟器 `_ws()` 裡出現了寫入動詞：{bad}"
