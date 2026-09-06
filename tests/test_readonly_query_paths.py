"""tests/test_readonly_query_paths.py — 「查詢即唯讀」守衛（2026-09-06）

客戶 2026-09-06 永久授權，逐字：
「凡是『查詢/搜尋』功能，一律強制走『純讀取（唯讀）』，絕對禁止反向寫入我的
Google Sheet。不用問我，直接切斷寫入！」

本檔守三處已切除的副作用寫入，不讓它們無聲復活：

  ① `ui/tab2_single_fund.py`      查一檔基金查成功就 `record_fund_nav_point`
  ② `ui/tab_fund_grp_health.py`   健診批次跑完就 `record_batch_nav_points`
  ③ `repositories/pool_repository.py`
                                   一個叫 `list_pool` 的**讀取**函式，會經由
                                   `_ws()` 建表 / 補表頭 → 改到使用者的試算表

────────────────────────────────────────────────────────────────────────
⚠️ 這個 repo 剛學到一課，本檔刻意避開兩種**擋不住的**寫法
────────────────────────────────────────────────────────────────────────

**(a) 擋「函式名」擋不住。** module 級 `from x import f` 會把**函式物件**綁進
消費模組的命名空間；事後 patch 來源模組 `x.f` 碰不到那個已綁定的名字。
同理，`from x import f as _g` 之後，只掃 `Name.id == "f"` 的 AST 規則**看不到**
`_g(...)` 這個呼叫。
→ **實證就在本次任務裡**：本組第一版掃描器只比對 `Name.id`，
   對 `ui/tab2_single_fund.py` 的 `from services.fund_history import record_fund as _rec_fh`
   **只掃到 import、沒掃到那個 `_rec_fh(...)` 呼叫**。
   本檔的 AST 規則因此**先解析別名、再比對呼叫**（見 `_bound_write_aliases`）。

**(b) 擋「import 來源套件」擋不住。** 分層守衛那種「黑名單套件名」的做法，
對 `services.*` 一律放行 —— 而寫入正是經由 `services.nav_history_gs` 發生的。

**→ 真正擋得住的是攔底層寫入動作本身。** 本檔的 ③ 全部走
`_TripwireWorksheet` / `_TripwireSpreadsheet`：**每一個 gspread 寫入方法都會炸**。
不管中間隔幾層、改幾次名字、用什麼別名，只要那條路徑最後真的送出寫入，就會被抓到。
本地 JSON 後端同理，用 `Path` 是否被建立當哨兵。

⛔ **本檔一行都不會碰到真的 Google Sheet**：全部走假件，`_get_sheet` / `_sa_present`
   / `_pool_sheet_id` 一律 monkeypatch 掉。

────────────────────────────────────────────────────────────────────────
⚠️ 本檔守不到什麼（誠實揭露，§-2 規則 6）
────────────────────────────────────────────────────────────────────────
1. AST 規則（`TestNoNavHistoryWriteFromQueryPaths` / `TestNoRecordNavCallers`）
   對**動態組出來的 module path**（字串拼接、`getattr` 鏈）無效。
   它們是**第二道**，不是唯一一道；第一道是 tripwire。
2. tripwire 只覆蓋 ③ 的選股池路徑。①② 沒有等價的 tripwire ——
   要跑到那兩處的真實寫入，得把整個 Streamlit 頁面渲染起來。
   ①② 因此靠「**模組根本到不了**」（不 import → 不可能呼叫）＋ 別名感知的呼叫掃描。
3. 「查詢路徑上還有沒有第五處寫入」**本檔不宣稱**，那取決於「有沒有漏看」。
   已登記的第四處見 PR 描述（`services/fund_history.record_fund`，
   寫的是本機 `cache/fund_history.json`，**不是** Google Sheet，故不在客戶授權的
   字面射程內 → 只登記、不修）。
"""
from __future__ import annotations

import ast
import pathlib

import pytest

_REPO = pathlib.Path(__file__).resolve().parent.parent


# ══════════════════════════════════════════════════════════════════════
# 假件：每一個寫入方法都會炸的 gspread 三件組
# ══════════════════════════════════════════════════════════════════════

#: gspread 的寫入面。**寧可多列、不可漏列** —— 漏一個就是一個繞道。
_GSPREAD_WRITE_METHODS = (
    "update", "update_acell", "update_cell", "update_cells", "update_title",
    "append_row", "append_rows", "insert_row", "insert_rows",
    "delete_row", "delete_rows", "delete_columns", "batch_clear", "clear",
    "resize", "add_rows", "add_cols", "sort", "format", "batch_update",
    "add_worksheet", "del_worksheet", "duplicate_sheet",
)


class WriteAttempted(AssertionError):
    """唯讀路徑上有人送出了寫入 —— 這就是本檔要抓的東西。"""


class FakeWorksheetNotFound(Exception):
    """模擬 gspread 找不到分頁時拋的東西。

    ⚠️ 刻意**不** import 真的 `gspread.exceptions.WorksheetNotFound` ——
    `pool_repository._ws` 接的是裸 `except Exception`,對型別不敏感;
    用假的可以讓本檔完全不依賴 gspread 是否安裝。
    """


def _tripwire(name):
    def _boom(*a, **k):
        raise WriteAttempted(
            f"唯讀路徑送出了 Google Sheets 寫入:{name}(*{a!r}, **{k!r})"
        )
    return _boom


class _TripwireWorksheet:
    """讀方法照常回值；**所有**寫方法一律炸。"""

    def __init__(self, values):
        self._values = [list(r) for r in values]

    # ── 讀（允許）──
    def get_all_values(self):
        return [list(r) for r in self._values]

    def row_values(self, n):
        return list(self._values[n - 1]) if 0 < n <= len(self._values) else []

    # ── 寫（一律炸）──
    def __getattr__(self, item):
        if item in _GSPREAD_WRITE_METHODS:
            return _tripwire(f"Worksheet.{item}")
        raise AttributeError(item)


class _TripwireSpreadsheet:
    def __init__(self, sheets: dict):
        self._sheets = dict(sheets)

    def worksheet(self, title):
        if title not in self._sheets:
            raise FakeWorksheetNotFound(title)          # gspread 的行為形狀
        return self._sheets[title]

    def add_worksheet(self, *a, **k):
        raise WriteAttempted(f"唯讀路徑建立了新分頁:add_worksheet(*{a!r}, **{k!r})")


class _TripwireClient:
    def __init__(self, sh):
        self._sh = sh

    def open_by_key(self, _key):      # 開表本身是讀，允許
        return self._sh


# ── 記錄型假件（正對照用：證明寫入路徑**還活著**）─────────────────────

class _RecordingWorksheet(_TripwireWorksheet):
    def __init__(self, values):
        super().__init__(values)
        self.calls: list = []

    def __getattr__(self, item):
        if item in _GSPREAD_WRITE_METHODS:
            def _rec(*a, **k):
                self.calls.append((item, a, k))
            return _rec
        raise AttributeError(item)


class _RecordingSpreadsheet:
    def __init__(self, sheets: dict):
        self._sheets = dict(sheets)
        self.calls: list = []

    def worksheet(self, title):
        if title not in self._sheets:
            raise FakeWorksheetNotFound(title)
        return self._sheets[title]

    def add_worksheet(self, *a, **k):
        self.calls.append(("add_worksheet", a, k))
        ws = _RecordingWorksheet([])
        self._sheets[k.get("title") or a[0]] = ws
        return ws


@pytest.fixture()
def pool_mod(monkeypatch):
    """`repositories.pool_repository`，且**保證碰不到真的 Google Sheet / 真的 secrets**。"""
    import repositories.pool_repository as P
    monkeypatch.setattr(P, "_sa_present", lambda: False, raising=True)
    monkeypatch.setattr(P, "_pool_sheet_id", lambda: "FAKE_SHEET_ID", raising=True)
    return P


def _store(pool_mod, sh):
    return pool_mod.GoogleSheetsPoolStore(oauth_client=_TripwireClient(sh))


# ══════════════════════════════════════════════════════════════════════
# 0. 正對照 —— 先證明哨兵是活的
# ══════════════════════════════════════════════════════════════════════

class TestTripwireItself:
    """「沒有寫入被攔到」如果是因為**哨兵壞了**，下面所有測試都只是在自我安慰。

    所以先證明：只要真的送出寫入，哨兵一定炸。
    """

    def test_worksheet_write_methods_all_raise(self):
        ws = _TripwireWorksheet([["code"], ["A"]])
        for m in _GSPREAD_WRITE_METHODS:
            if m in ("add_worksheet", "del_worksheet", "duplicate_sheet"):
                continue                      # 那是 Spreadsheet 面
            with pytest.raises(WriteAttempted):
                getattr(ws, m)("A1", [["x"]])

    def test_spreadsheet_add_worksheet_raises(self):
        with pytest.raises(WriteAttempted):
            _TripwireSpreadsheet({}).add_worksheet(title="x", rows=1, cols=1)

    def test_reads_are_allowed(self):
        ws = _TripwireWorksheet([["code", "name"], ["A", "甲"]])
        assert ws.get_all_values() == [["code", "name"], ["A", "甲"]]
        assert ws.row_values(1) == ["code", "name"]


# ══════════════════════════════════════════════════════════════════════
# 1. ③ 選股池：list_pool 是**讀**，一格都不准寫
# ══════════════════════════════════════════════════════════════════════

class TestPoolListIsReadOnly:

    def test_list_pool_does_not_create_the_worksheet_when_it_is_missing(self, pool_mod):
        """**沒用過選股池的人**打開 ⑤ → 舊寫法會 `add_worksheet` + 寫表頭。

        突變驗證:把 `_ws()` 的 `if not for_write: return None` 拿掉 → 本條轉紅
        (`WriteAttempted: 唯讀路徑建立了新分頁`)。
        """
        sh = _TripwireSpreadsheet({})                      # `_fund_pool` 不存在
        assert _store(pool_mod, sh).list_pool() == []      # 空池，且沒有炸

    def test_list_pool_does_not_rewrite_headers_the_user_renamed(self, pool_mod):
        """**自己在 Sheet 上改過表頭文字的人**打開 ⑤ → 舊寫法會整排改回去。

        突變驗證:把 `for_write and` 從表頭判斷式拿掉 → 本條轉紅
        (`WriteAttempted: Worksheet.update`)。
        """
        ws = _TripwireWorksheet([
            ["代號", "名稱", "分類", "型態", "備註", "加入日", "狀態",
             "ISIN", "幣別", "晨星ID"],                    # 使用者自己取的欄名
            ["ALZF9", "安聯", "", "", "", "2026-01-01", "WATCHING",
             "LU0766462157", "USD", ""],
        ])
        sh = _TripwireSpreadsheet({pool_mod._WS_POOL: ws})
        pool = _store(pool_mod, sh).list_pool()
        # 功能沒有消失：資料是**按位置**讀的，表頭文字對程式沒有作用
        assert [e.code for e in pool] == ["ALZF9"]
        assert pool[0].isin == "LU0766462157"
        assert pool[0].currency == "USD"

    def test_list_pool_reads_normally_when_headers_match(self, pool_mod):
        ws = _TripwireWorksheet([
            list(pool_mod._HEADERS),
            ["AAA", "甲", "", "成長", "", "2026-01-01", "HOLDING", "", "TWD", "S1"],
            ["BBB", "乙", "", "", "", "2026-01-02", "", "", "", ""],
        ])
        sh = _TripwireSpreadsheet({pool_mod._WS_POOL: ws})
        pool = _store(pool_mod, sh).list_pool()
        assert [e.code for e in pool] == ["AAA", "BBB"]
        assert pool[0].type_override == "成長"
        assert pool[1].status == "WATCHING"          # 空 → 預設，向後相容未變

    def test_module_level_list_pool_helper_is_also_read_only(self, pool_mod, monkeypatch):
        """對外入口 `list_pool(oauth_client=...)`（UI 實際呼叫的那個）同樣唯讀。"""
        sh = _TripwireSpreadsheet({})
        monkeypatch.setattr(
            pool_mod, "get_pool_store",
            lambda oauth_client=None: _store(pool_mod, sh), raising=True)
        assert pool_mod.list_pool(oauth_client=object()) == []


# ══════════════════════════════════════════════════════════════════════
# 2. ③ 的反面：使用者**明確按下按鈕**的寫入路徑不得被弄消失
# ══════════════════════════════════════════════════════════════════════

class TestPoolWritePathStillWorks:
    """客戶禁的是「查詢的副作用寫入」，不是「我按了存檔」。

    若只把 `_ws()` 裡的建表/補表頭整段刪掉（而不是加 `for_write` 分流），
    本組會轉紅 —— 這是防「切過頭」的那一半。
    """

    def _store_rec(self, pool_mod, sh):
        return pool_mod.GoogleSheetsPoolStore(oauth_client=_TripwireClient(sh))

    def test_upsert_still_creates_the_worksheet_and_writes_headers(self, pool_mod):
        sh = _RecordingSpreadsheet({})
        store = self._store_rec(pool_mod, sh)
        store.upsert(pool_mod.PoolEntry(code="AAA", name="甲"))
        assert [c[0] for c in sh.calls] == ["add_worksheet"]
        ws = sh._sheets[pool_mod._WS_POOL]
        assert ("update", ("A1", [list(pool_mod._HEADERS)]), {}) in ws.calls
        assert any(c[0] == "append_row" for c in ws.calls)

    def test_upsert_still_repairs_a_short_header_row(self, pool_mod):
        ws = _RecordingWorksheet([["code", "name"]])          # 欄位缺失
        sh = _RecordingSpreadsheet({pool_mod._WS_POOL: ws})
        self._store_rec(pool_mod, sh).upsert(pool_mod.PoolEntry(code="AAA"))
        assert ("update", ("A1", [list(pool_mod._HEADERS)]), {}) in ws.calls

    def test_remove_still_goes_through_the_write_path(self, pool_mod):
        ws = _RecordingWorksheet([list(pool_mod._HEADERS),
                                  ["AAA", "", "", "", "", "", "", "", "", ""]])
        sh = _RecordingSpreadsheet({pool_mod._WS_POOL: ws})
        self._store_rec(pool_mod, sh).remove("AAA")
        assert any(c[0] == "delete_rows" for c in ws.calls)


# ══════════════════════════════════════════════════════════════════════
# 3. ③ 本地 JSON 後端：讀取路徑不得在磁碟上長出東西
# ══════════════════════════════════════════════════════════════════════

class TestLocalPoolStoreReadIsSideEffectFree:

    def test_listing_an_empty_local_pool_creates_nothing(self, tmp_path):
        from repositories.pool_repository import LocalJsonPoolStore
        d = tmp_path / "never_created"
        assert LocalJsonPoolStore(base_dir=d).list_pool() == []
        # 突變驗證:把 mkdir 放回 `__init__` → 本條轉紅
        assert not d.exists(), f"唯讀路徑在磁碟上建了目錄:{d}"

    def test_upsert_still_creates_the_dir_and_the_file(self, tmp_path):
        from repositories.pool_repository import LocalJsonPoolStore, PoolEntry
        d = tmp_path / "made_on_write"
        store = LocalJsonPoolStore(base_dir=d)
        store.upsert(PoolEntry(code="AAA", name="甲"))
        assert (d / "pool.json").exists()
        assert [e.code for e in LocalJsonPoolStore(base_dir=d).list_pool()] == ["AAA"]


# ══════════════════════════════════════════════════════════════════════
# 4. ①② 查詢頁面：連**到得了寫入的那條路**都不准有
# ══════════════════════════════════════════════════════════════════════

#: 兩個查詢／搜尋介面。① 查一檔基金；② 持倉體檢（輸入一串代號 → 看報表）。
_QUERY_SURFACES = ("ui/tab2_single_fund.py", "ui/tab_fund_grp_health.py")

#: 只要 import 得到，就有可能被呼叫 —— 所以連 import 都不准有。
_NAV_WRITE_MODULES = (
    "ui.helpers.nav_history_hook",
    "services.nav_history_gs",
    "services.nav_history_store",
)


def _parse(rel: str) -> ast.Module:
    return ast.parse((_REPO / rel).read_text(encoding="utf-8"), filename=rel)


def _imported_modules(tree: ast.Module):
    """檔案裡（任何位置，含函式內 lazy import）import 到的 module path。"""
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            out.append((node.module, node.lineno))
        elif isinstance(node, ast.Import):
            out.extend((a.name, node.lineno) for a in node.names)
    return out


def _dynamic_import_strings(tree: ast.Module):
    """`importlib.import_module("…")` / `__import__("…")` 的字串引數。

    只看**呼叫的引數**，不看註解與 docstring —— 註解根本不進 AST，
    而 docstring 是 Constant，掃它會把本檔自己的說明文字也算成違規。
    """
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        name = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else "")
        if name in ("import_module", "__import__"):
            for a in node.args:
                if isinstance(a, ast.Constant) and isinstance(a.value, str):
                    out.append((a.value, node.lineno))
    return out


class TestNoNavHistoryWriteFromQueryPaths:
    """①② —— 查詢頁面不得**到得了** nav_history 的寫入面。

    突變驗證:把 `record_fund_nav_point` 那段還原回 `ui/tab2_single_fund.py` → 本組轉紅。
    """

    @pytest.mark.parametrize("rel", _QUERY_SURFACES)
    def test_no_static_import_of_nav_history_write_modules(self, rel):
        bad = [(m, ln) for m, ln in _imported_modules(_parse(rel))
               if any(m == w or m.startswith(w + ".") for w in _NAV_WRITE_MODULES)]
        assert not bad, (
            f"{rel} 又 import 了 nav_history 的寫入面:{bad}\n"
            f"客戶 2026-09-06:查詢一律唯讀,禁止反向寫入 Google Sheet。")

    @pytest.mark.parametrize("rel", _QUERY_SURFACES)
    def test_no_dynamic_import_of_nav_history_write_modules(self, rel):
        bad = [(s, ln) for s, ln in _dynamic_import_strings(_parse(rel))
               if any(s == w or s.startswith(w + ".") for w in _NAV_WRITE_MODULES)]
        assert not bad, f"{rel} 以動態 import 繞道到 nav_history 寫入面:{bad}"

    def test_the_rule_can_actually_see_an_import(self):
        """正對照:規則本身看得見 import,否則「0 命中」只是規則壞了。

        拿一個**已知有** `nav_history` 寫入的 production 檔來驗。
        """
        mods = [m for m, _ in _imported_modules(_parse("ui/tab_manage.py"))]
        assert any(m.startswith("services.nav_history") for m in mods), (
            "正對照失效:掃描器在一個已知有 nav_history 寫入的檔案裡什麼都沒看到")


# ══════════════════════════════════════════════════════════════════════
# 5. 別名感知：`record_*` 在 production 一個呼叫點都不准有
# ══════════════════════════════════════════════════════════════════════

_RECORD_NAMES = ("record_fund_nav_point", "record_batch_nav_points")

#: 允許呼叫 `record_*` 的地方。**目前是空的。**
#:
#: 要新增一筆，請同時寫清楚「**使用者是按了哪一顆按鈕/勾了哪個框**才走到這裡」——
#: 客戶禁的是**查詢的副作用寫入**，不是使用者明確要求的寫入。
#: 一個沒有使用者確認元件的呼叫點，不該被加進這張表。
_RECORD_CALLER_ALLOWLIST: tuple = ()

#: 掃描範圍。刻意**不含 `scripts/`**：`record_*` 內部依賴 `st.session_state`，
#: headless 腳本呼叫它本來就會炸，不是本規則的射程；
#: 也**不含 `tests/`**（測試 monkeypatch 它是正當的）。
_PROD_DIRS = ("ui", "services", "repositories", "shared", "infra")


def _production_files():
    out = [_REPO / "app.py"]
    for d in _PROD_DIRS:
        out.extend(sorted((_REPO / d).rglob("*.py")))
    return [p for p in out if p.exists()]


def _bound_write_aliases(tree: ast.Module):
    """解析**別名**：哪些名字在這個檔案裡指向 `record_*`。

    ⚠️ 這一步就是本檔開頭那條教訓的落地 —— 只比對 `Name.id == "record_…"`
    會被 `from … import record_fund_nav_point as _r` 一行繞過。
    回 (直接名字集合, 模組別名集合)。
    """
    direct, modaliases = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod.endswith("nav_history_hook"):
                for a in node.names:
                    if a.name in _RECORD_NAMES:
                        direct.add(a.asname or a.name)
                    elif a.name == "*":
                        direct.update(_RECORD_NAMES)
            elif mod.endswith("ui.helpers") or mod == "ui.helpers":
                for a in node.names:
                    if a.name == "nav_history_hook":
                        modaliases.add(a.asname or a.name)
        elif isinstance(node, ast.Import):
            for a in node.names:
                if a.name.endswith("nav_history_hook"):
                    modaliases.add(a.asname or a.name.split(".")[0])
    return direct, modaliases


def _record_call_sites(path: pathlib.Path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    direct, _modaliases = _bound_write_aliases(tree)
    hits = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if isinstance(f, ast.Name) and f.id in direct:
            hits.append((f.id, node.lineno))
        elif isinstance(f, ast.Attribute) and f.attr in _RECORD_NAMES:
            # `mod.record_fund_nav_point(...)` —— 不論 mod 叫什麼別名
            hits.append((f.attr, node.lineno))
    return hits


class TestNoRecordNavCallers:

    def test_no_production_caller_of_record_nav_helpers(self):
        """突變驗證:把 ① 或 ② 的呼叫還原 → 本條轉紅並印出檔名行號。"""
        bad = []
        for p in _production_files():
            rel = p.relative_to(_REPO).as_posix()
            if rel in _RECORD_CALLER_ALLOWLIST:
                continue
            for name, ln in _record_call_sites(p):
                bad.append(f"{rel}:{ln} → {name}()")
        assert not bad, (
            "有人把「查完順手寫進 Google Sheet」接回來了:\n  "
            + "\n  ".join(bad)
            + "\n客戶 2026-09-06:查詢一律唯讀。若這真的是使用者明確按下的動作,"
              "請把它加進 `_RECORD_CALLER_ALLOWLIST` 並寫明是哪一顆按鈕。")

    def test_alias_resolution_actually_works(self):
        """正對照:規則看得懂 `as` 別名 —— 這正是本組第一版漏掉的那個洞。"""
        src = (
            "from ui.helpers.nav_history_hook import record_fund_nav_point as _r\n"
            "def f(fd):\n"
            "    _r(fd, source='X')\n"
        )
        tree = ast.parse(src)
        direct, _ = _bound_write_aliases(tree)
        assert direct == {"_r"}
        hits = [n.func.id for n in ast.walk(tree)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id in direct]
        assert hits == ["_r"], "別名解析壞了 → 整條規則等於沒有"

    def test_module_alias_form_is_also_seen(self):
        """`import ui.helpers.nav_history_hook as H` + `H.record_batch_nav_points(...)`。"""
        src = ("import ui.helpers.nav_history_hook as H\n"
               "def f(p):\n    H.record_batch_nav_points(p)\n")
        tree = ast.parse(src)
        hits = [n.func.attr for n in ast.walk(tree)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr in _RECORD_NAMES]
        assert hits == ["record_batch_nav_points"]
