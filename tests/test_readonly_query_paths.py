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

⚠️ **2026-09-06 必修追加（第 6 節）：唯讀 ≠ 沉默。**
切除 ③ 的寫入時，`_ws()` 的唯讀分支寫成了裸 `except Exception → return None`，
於是 **403 未分享 / 429 配額 / 5xx / 連線中斷** 全被壓成 `list_pool() == []` ——
使用者看到的是「**你的選股池是空的**」，而不是「**這次讀不到**」。
那是憲法 §1「Fail Loud, Never Fake」直接點名的「空有兩義」，
也是客戶 2026-09-05 明示不接受的「假資料／缺資料」。
第 6 節守這一半，並且**同時**驗「失敗的路上寫入嘗試數 = 0」——
⛔ 修 §1 **不准**靠把寫入放回去來換。

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
3. **第 6 節只覆蓋選股池（③）這一條讀取鏈。** ①② 的讀取失敗（MoneyDJ / FundClear
   取數）**不在本檔射程內** —— 那是另一套 fetcher，有它自己的守衛。
4. **本檔不宣稱「pool_repository 已經沒有別的吞讀失敗處」。** 已知仍在的至少有：
   `LocalJsonPoolStore._read()`（壞 JSON / OSError → `[]` + stderr）與
   `_pool_map_or_empty()`（讀失敗 → `{}`，**那是刻意的「外譯」**，
   由 `test_the_nav_supplement_chain_is_still_not_blocked` 釘住不准弄壞）。
   兩者都**不是**本次 PR 造成的，也都不在本次授權的射程內。
5. 「查詢路徑上還有沒有第五處寫入」**本檔不宣稱**，那取決於「有沒有漏看」。
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


class FakeGspreadApiError(Exception):
    """模擬 gspread `APIError` 的**行為形狀**(403 / 429 / 5xx),刻意不 import gspread。

    ⚠️ 本 repo 的 CI 精簡環境**沒有裝 gspread**,`infra.gspread_retry.http_status_of`
    在那裡恆回 `None` —— 所以「這是不是 API 錯誤」的判定不能只靠狀態碼,
    必須靠**訊息形狀**。本假件因此把狀態碼寫進訊息裡,與真實 gspread 的
    `APIError: {'code': 403, ...}` 字串形狀一致。
    """


def _api_error(status: int, msg: str = "") -> FakeGspreadApiError:
    return FakeGspreadApiError(f"APIError {status} {msg}".strip())


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

#: 查詢／搜尋介面。① 查一檔基金;② 持倉體檢(輸入一串代號 → 看報表);
#: ③ 批次分析(貼一串代號 → 看大表)。
#:
#: ⚠️ **2026-09-06 補入 `ui/tab_batch_analysis.py`(第三個)** —— 它一直不在守衛射程內,
#:    卻和 ②**走同一條路**:`_run_batch` → `services/fund_row.py::process_one_fund`
#:    → `repositories/fund/sources.py` 的取數鏈。少列一個入口,規則就有一個天生的破口。
#:    (實測:補入當下該檔對本節既有兩條規則**本來就是乾淨的**,
#:     所以這是**純擴大射程**,沒有連帶改動任何 production 檔。)
_QUERY_SURFACES = ("ui/tab2_single_fund.py", "ui/tab_fund_grp_health.py",
                   "ui/tab_batch_analysis.py")

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


# ══════════════════════════════════════════════════════════════════════
# 6. ⭐ 唯讀 ≠ 沉默：讀失敗**不准**被講成「你的選股池是空的」
# ══════════════════════════════════════════════════════════════════════
#
# 本節是 2026-09-06 的**必修**。上面第 1 節把 `_ws()` 的建表/補表頭切掉了,
# 那一半是對的;但切的時候順手把**讀取失敗**也一起收進了同一個
# `except Exception → return None`,於是:
#
#   403 未分享 / 429 配額 / 5xx / 連線中斷
#        → `_ws()` 回 None → `list_pool()` 回 `[]`
#        → 使用者看到「**你的選股池是空的**」,而不是「**這次讀不到**」
#
# 那是 §1「Fail Loud, Never Fake」直接點名的「空有兩義」,而且它**不只是難看** ——
# 它會連鎖打壞兩個已經修好的東西(下面 `TestPoolReadFailureIsNotAnEmptyPool`
# 與 `TestReadFailureStillFeedsTheBackoffAndTheCache` 各驗一個):
#
#   (1) `_load_pool_map()` 的 `except → record_gspread_failure → raise` 進不去
#       → `record_gspread_success()` 對一次 403 蓋上「成功」
#       → **跨呼叫冷卻永遠學不到這次失敗**(v3 §02「失敗時退避,不連續轟炸來源」)。
#   (2) `_cached_pool_map` 是 `@st.cache_data` —— **例外不入快取、空值會**。
#       一次瞬斷把假的空池**鎖滿 TTL_30MIN**。
#       (`tests/test_st_cache_failure_not_cached.py` 把本站點登記在 `_RAISES`,
#        理由逐字寫著「_load_pool_map 失敗即 raise」—— 被吞掉之後那張表在說謊,
#        而它是 **AST 規則**、只檢查 `_load_pool_map` 裡有沒有 `raise` 節點,
#        **結構上看不到上游把訊號吞掉了**,所以它不會轉紅。)
#
# ⛔ **修法不是把寫入放回去。** 唯讀就是唯讀 ——
#    第 1、2、3 節(不建表 / 不補表頭 / 不建目錄 / 寫入路徑仍然可用)一條都沒有放寬,
#    本節每一條都額外驗「失敗的同時,寫入嘗試數 = 0」。


class _FailingSpreadsheet:
    """`worksheet()` 一律拋指定的例外;**所有寫入方法照樣是哨兵**。

    用途:同時驗兩件事 —— (a) 失敗有沒有浮出來、(b) 失敗的路上有沒有偷寫東西。
    """

    def __init__(self, exc: BaseException):
        self._exc = exc
        self.worksheet_calls = 0

    def worksheet(self, title):
        self.worksheet_calls += 1
        raise self._exc

    def add_worksheet(self, *a, **k):
        raise WriteAttempted(f"唯讀路徑在讀失敗之後還去建分頁:add_worksheet(*{a!r}, **{k!r})")

    def __getattr__(self, item):
        if item in _GSPREAD_WRITE_METHODS:
            return _tripwire(f"Spreadsheet.{item}")
        raise AttributeError(item)


#: 「這次讀不到」的各種樣子。**每一個都必須往上拋。**
_READ_FAILURES = [
    pytest.param(_api_error(403, "PERMISSION_DENIED: The caller does not have permission"),
                 id="403-未分享給這把憑證"),
    pytest.param(_api_error(429, "Quota exceeded for quota metric 'Read requests'"),
                 id="429-配額用盡"),
    pytest.param(_api_error(500, "Internal error encountered"), id="500-Google 自己壞了"),
    pytest.param(_api_error(503, "The service is currently unavailable"), id="503-暫時不可用"),
    pytest.param(ConnectionError("Connection aborted, RemoteDisconnected"), id="連線中斷"),
    pytest.param(TimeoutError("read timed out"), id="逾時"),
]


class TestMissingWorksheetClassifier:
    """⭐ 正對照/負對照:先證明「分頁沒建」與「讀不到」真的分得開。

    這一組如果壞了,下面所有測試都只是在自我安慰 —— 一個永遠回 True 的分類器
    會讓每一次失敗都被當成空池,而測試看起來還是綠的。
    """

    def test_a_real_missing_worksheet_is_recognised(self, pool_mod):
        """正對照:三種「分頁不存在」的寫法都要認得(否則整條規則等於恆 raise)。"""
        real_shape = type("WorksheetNotFound", (Exception,), {})("_fund_pool")
        assert pool_mod._is_missing_worksheet(real_shape) is True
        assert pool_mod._is_missing_worksheet(FakeWorksheetNotFound("_fund_pool")) is True
        # 本 repo `tests/test_policy_store.py` 既有的模擬慣例
        assert pool_mod._is_missing_worksheet(Exception("WorksheetNotFound")) is True

    @pytest.mark.parametrize("exc", _READ_FAILURES)
    def test_a_read_failure_is_never_mistaken_for_a_missing_worksheet(self, pool_mod, exc):
        """負對照:讀失敗一個都不准被歸類成「分頁不存在」。"""
        assert pool_mod._is_missing_worksheet(exc) is False, (
            f"{type(exc).__name__}: {exc} 被歸類成「分頁還沒建」→ "
            f"使用者會看到假的空池(§1 空有兩義)")

    def test_an_api_error_that_merely_mentions_the_words_still_raises(self, pool_mod):
        """訊息裡剛好出現 `WorksheetNotFound` 字樣的 **API 錯誤**,仍然算讀失敗。

        這就是分類器「先否定、再肯定」的順序在防的東西 ——
        只做字串比對會被一句錯誤訊息騙過去。
        """
        assert pool_mod._is_missing_worksheet(
            _api_error(429, "Quota exceeded while resolving WorksheetNotFound")) is False


class TestPoolReadFailureIsNotAnEmptyPool:
    """⭐ 本節主力:讀失敗必須往上拋,**不准**變成 `[]`。

    突變驗證(逐字):把 `repositories/pool_repository.py::_ws` 唯讀分支裡的
        if not _is_missing_worksheet(_e_ws):
            raise
    這兩行刪掉 → 本組每一條都轉紅(`Failed: DID NOT RAISE`)。
    """

    @pytest.mark.parametrize("exc", _READ_FAILURES)
    def test_store_list_pool_raises_instead_of_returning_empty(self, pool_mod, exc):
        sh = _FailingSpreadsheet(exc)
        store = _store(pool_mod, sh)
        with pytest.raises(type(exc)):
            store.list_pool()
        assert sh.worksheet_calls == 1, "輸入非空斷言:根本沒去讀,那這條測試什麼都沒驗到"

    @pytest.mark.parametrize("exc", _READ_FAILURES)
    def test_module_level_list_pool_raises_too(self, pool_mod, monkeypatch, exc):
        """UI 實際呼叫的是**模組級** `list_pool(oauth_client=...)`,那一層也要拋。

        `ui/helpers/fund_grp_health/switch_advisor_section.py` 已經寫好了
        `except → system_error("選股池讀取失敗", hint="選股池顯示為空不代表它是空的,
        可能只是這次讀不到。")` —— 這條測試保證那段紅燈**真的會被執行到**。
        """
        sh = _FailingSpreadsheet(exc)
        monkeypatch.setattr(pool_mod, "get_pool_store",
                            lambda oauth_client=None: _store(pool_mod, sh), raising=True)
        with pytest.raises(type(exc)):
            pool_mod.list_pool(oauth_client=object())

    @pytest.mark.parametrize("exc", _READ_FAILURES)
    def test_failing_read_still_writes_absolutely_nothing(self, pool_mod, exc):
        """⛔ 修 §1 **不准**把寫入放回去:失敗的路上一格都不能寫。

        `_FailingSpreadsheet` 的每個寫入方法都是哨兵 —— 若有人「順手補建分頁」
        當作 fallback,這裡會炸成 `WriteAttempted` 而不是原本的例外。
        """
        sh = _FailingSpreadsheet(exc)
        with pytest.raises(type(exc)) as ei:
            _store(pool_mod, sh).list_pool()
        assert not isinstance(ei.value, WriteAttempted), "唯讀路徑送出了寫入"

    def test_a_missing_worksheet_is_still_an_honest_empty_pool(self, pool_mod):
        """⭐ 反向護欄:別修過頭。

        「這本表上還沒有 `_fund_pool` 分頁」是**合法狀態**(使用者還沒建過選股池),
        它必須繼續回 `[]`、不准拋 —— 否則第一次用的人會吃到一個紅燈。
        (與第 1 節 `test_list_pool_does_not_create_the_worksheet_when_it_is_missing`
         同一個情境,這裡再驗一次「而且**沒有**被改成 raise」。)
        """
        sh = _TripwireSpreadsheet({})          # worksheet() 拋 FakeWorksheetNotFound
        assert _store(pool_mod, sh).list_pool() == []

    def test_a_normal_read_is_untouched(self, pool_mod):
        """正對照:正常讀取沒有被本次修正弄壞(否則「不拋」只是因為根本沒跑到)。"""
        ws = _TripwireWorksheet([
            list(pool_mod._HEADERS),
            ["AAA", "甲", "", "", "", "2026-01-01", "", "", "TWD", ""],
        ])
        assert len(ws.get_all_values()) == 2, "輸入非空斷言:假資料是空的"
        sh = _TripwireSpreadsheet({pool_mod._WS_POOL: ws})
        assert [e.code for e in _store(pool_mod, sh).list_pool()] == ["AAA"]


class TestReadFailureStillFeedsTheBackoffAndTheCache:
    """⭐ 這一組驗的是**連鎖後果**,不是 `_ws()` 本身。

    `_load_pool_map()` 的 2026-09-01 長註寫死了一個不變式:
    「失敗即 raise → 例外穿過 `@st.cache_data` 不入快取 → 假的空池不會被鎖滿 TTL」。
    上游一旦把失敗吞成 `[]`,那個 `except` **永遠進不去**,不變式當場作廢,
    而且 `record_gspread_success()` 會替一次 403 蓋上「成功」的章。

    突變驗證:同上(拿掉 `_ws` 的那兩行 raise)→ 本組轉紅,
    且 `test_..._never_says_success` 會印出「一次 403 被登記成成功」。
    """

    @pytest.fixture()
    def gs_backend(self, pool_mod, monkeypatch):
        """讓 `get_pool_store()` 一定選到 Google Sheets 後端(而不是本地 JSON)。"""
        monkeypatch.setattr(pool_mod, "_sa_present", lambda: True, raising=True)
        monkeypatch.setattr(pool_mod, "_pool_sheet_id", lambda: "FAKE_SHEET_ID", raising=True)
        return pool_mod

    @pytest.fixture()
    def backoff_spy(self, monkeypatch):
        """攔截跨呼叫冷卻的兩把鑰匙。**不碰真的 backoff 狀態**(不污染其他測試)。"""
        import infra.gspread_retry as GR
        seen = {"fail": [], "success": []}
        monkeypatch.setattr(GR, "record_gspread_failure",
                            lambda a, s, e: (seen["fail"].append((a, s, e)), ("k", 900.0))[1],
                            raising=True)
        monkeypatch.setattr(GR, "record_gspread_success",
                            lambda a, s: seen["success"].append((a, s)), raising=True)
        monkeypatch.setattr(GR, "should_skip_gspread",
                            lambda a, s: (False, 0.0, ""), raising=True)
        return seen

    def test_load_pool_map_reraises_so_the_failure_never_enters_the_cache(
            self, gs_backend, monkeypatch, backoff_spy):
        exc = _api_error(403, "PERMISSION_DENIED")
        sh = _FailingSpreadsheet(exc)
        monkeypatch.setattr(gs_backend, "_get_sheet", lambda oc=None: sh, raising=True)
        with pytest.raises(FakeGspreadApiError):
            gs_backend._load_pool_map()
        assert sh.worksheet_calls == 1, "輸入非空斷言:沒有真的去讀"

    def test_a_read_failure_registers_the_cooldown(
            self, gs_backend, monkeypatch, backoff_spy):
        sh = _FailingSpreadsheet(_api_error(429, "Quota exceeded"))
        monkeypatch.setattr(gs_backend, "_get_sheet", lambda oc=None: sh, raising=True)
        with pytest.raises(FakeGspreadApiError):
            gs_backend._load_pool_map()
        assert backoff_spy["fail"], (
            "讀失敗沒有登記跨呼叫冷卻 → 下一次 rerun 會再轟炸來源一次"
            "(v3 憲法 §02「失敗時退避,不連續轟炸來源」)")

    def test_a_read_failure_never_says_success(
            self, gs_backend, monkeypatch, backoff_spy):
        """**這條是本次必修的核心證據。**

        吞掉的版本會走完 `_load_pool_map` 的 happy path,
        於是一次 403 被 `record_gspread_success()` 蓋上「成功」的章 ——
        冷卻機制從此對這個來源永遠是瞎的。
        """
        sh = _FailingSpreadsheet(_api_error(403, "PERMISSION_DENIED"))
        monkeypatch.setattr(gs_backend, "_get_sheet", lambda oc=None: sh, raising=True)
        with pytest.raises(FakeGspreadApiError):
            gs_backend._load_pool_map()
        assert not backoff_spy["success"], (
            f"一次讀取失敗被登記成「成功」:{backoff_spy['success']} → "
            f"跨呼叫冷卻永遠學不到它")

    def test_a_successful_read_still_says_success(
            self, gs_backend, monkeypatch, backoff_spy):
        """正對照:成功時**仍然**會蓋成功章 —— 否則上一條的「沒有成功」毫無意義。"""
        ws = _TripwireWorksheet([list(gs_backend._HEADERS),
                                 ["AAA", "甲", "", "", "", "", "", "", "", ""]])
        sh = _TripwireSpreadsheet({gs_backend._WS_POOL: ws})
        monkeypatch.setattr(gs_backend, "_get_sheet", lambda oc=None: sh, raising=True)
        assert set(gs_backend._load_pool_map()) == {"AAA"}
        assert backoff_spy["success"], "成功也沒蓋章 → 這組 spy 根本沒接上"

    def test_the_nav_supplement_chain_is_still_not_blocked(
            self, gs_backend, monkeypatch, backoff_spy):
        """⚠️ 反向護欄:`_pool_map_or_empty()` 的「**外譯**」契約不准被本次修正弄壞。

        補淨值查表(`resolve_secid` / `resolve_isin` / `resolve_currency`)對
        `repositories/fund/sources.py` 的既有契約是「查不到 → None → 退硬編表/名稱搜尋」。
        §1 要的是「**在快取之內拋、在快取之外譯**」——
        `_load_pool_map` 拋(所以不入快取)、`_pool_map_or_empty` 譯成 `{}`(所以不斷鏈)。
        **兩者缺一不可**,本條守後半。
        """
        sh = _FailingSpreadsheet(_api_error(403, "PERMISSION_DENIED"))
        monkeypatch.setattr(gs_backend, "_get_sheet", lambda oc=None: sh, raising=True)
        assert gs_backend._pool_map_or_empty() == {}
        assert gs_backend.resolve_secid("AAA") is None
        assert backoff_spy["fail"], "外譯了,但沒有登記冷卻 → 等於默默吞掉"


class TestTheUiStillHasSomewhereToShowIt:
    """使用者**看得到**這件事,靠的是界外那一段既有程式碼 —— 用 AST 釘住它。

    `ui/helpers/fund_grp_health/switch_advisor_section.py` 是選股池的主要顯示面,
    它早就寫好了紅燈處理;本次修正的價值,就是讓那段程式碼**重新變得會被執行到**。
    ⛔ 本檔**不修改**該檔(它在別組的檔案邊界內),只斷言它還在。

    ⚠️ 三態顏色分離(客戶四大鐵律第 3 條):讀取失敗是「**系統真出錯**」→ 🔴 `system_error`;
    **不是**「前提不足」→ ⬜ `not_ready`。這裡順便釘住它沒有被降級成灰態。
    """

    _REL = "ui/helpers/fund_grp_health/switch_advisor_section.py"

    def _pool_read_handlers(self):
        """找出「try 內呼叫 list_pool」的那些 try,回傳其 handler 內呼叫到的函式名。"""
        tree = _parse(self._REL)
        out = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Try):
                continue
            calls_list_pool = any(
                isinstance(c, ast.Call)
                and ((isinstance(c.func, ast.Name) and c.func.id == "list_pool")
                     or (isinstance(c.func, ast.Attribute) and c.func.attr == "list_pool"))
                for stmt in node.body for c in ast.walk(stmt))
            if not calls_list_pool:
                continue
            names = set()
            for h in node.handlers:
                for c in ast.walk(h):
                    if isinstance(c, ast.Call):
                        f = c.func
                        names.add(f.attr if isinstance(f, ast.Attribute)
                                  else getattr(f, "id", ""))
            out.append(names)
        return out

    def test_the_pool_read_is_wrapped_in_a_red_system_error(self):
        handlers = self._pool_read_handlers()
        assert handlers, (
            f"正對照失效:在 {self._REL} 裡找不到任何「try 內讀 list_pool」的區塊 —— "
            f"要嘛檔案改了,要嘛這條規則壞了")
        assert all("system_error" in names for names in handlers), (
            f"{self._REL} 的選股池讀取有 try 但沒有 system_error:{handlers}\n"
            f"讀失敗必須讓使用者看見(§1);靜靜吞掉等於回到 2026-09-06 之前。")

    def test_the_pool_read_failure_is_red_not_grey(self):
        """讀失敗**不准**被畫成 ⬜ 灰態 —— 灰態的語意是「前提不足,你去補」,
        而這裡是「系統真出錯,不是你少做了什麼」。兩者混用即違反三態分離。
        """
        for names in self._pool_read_handlers():
            assert "not_ready" not in names, (
                "選股池讀取失敗被畫成灰態(not_ready)—— 那會叫使用者去『補資料』,"
                "但他什麼都沒少做,是系統讀不到。")



# ══════════════════════════════════════════════════════════════════════
# 7. ⭐ 守衛翻成 fail-closed：不再靠「函式名 ＋ import 來源白名單」
# ══════════════════════════════════════════════════════════════════════
#
# ⚠️ **本節與「查詢頁走不走得到選股池回寫」那個爭議無關,兩件事分開讀。**
#    本節修的是**守衛自己的缺陷**:第 4、5 節那兩條規則是
#    「**函式名(`_RECORD_NAMES`)＋ import 來源白名單(`_NAV_WRITE_MODULES`)**」,
#    而那種形狀有四個**已知**繞道(下面 `TestTheRuleSeesTheKnownBypasses` 逐一釘住):
#
#      (1) `from m import f as _g` 之後呼叫 `_g(...)`      ← 只比對 `Name.id == "f"` 看不到
#      (2) `importlib.import_module("a." + "b")`           ← 字串拼接,靜態看不到模組名
#      (3) `g = m.f` 之後呼叫 `g(...)`                      ← 賦值別名,不是 import 別名
#      (4) `getattr(m, "set_" + "secid")`                   ← 動態取名
#
#    **這四個缺陷成立與否,不取決於今天有沒有人真的在用它們** ——
#    一條「換個寫法就繞過去」的規則,它報的「0 命中」本來就不該被當成證據。
#
# **本節的做法**:不再擴充任何名字白名單,改成
#   **「這個檔案裡,有沒有任何名字最後綁到了 pool 的寫入符號、而且被呼叫了」**,
#   別名(import / 賦值)、模組屬性、動態取名**四種形狀一起認**;
#   認不出來的形狀(字串拼接)則**整個形狀禁掉**。
#
# ⛔ 本節**不主張**任何一條查詢路徑「已經切乾淨」——
#    `repositories/fund/sources.py` 目前**登記在待仲裁豁免表內**(見 `_PENDING_ARBITRATION`),
#    本節只保證「**它不會無聲地變多**」。

#: pool_repository 的**寫入面**。寧可多列、不可漏列 —— 漏一個就是一個繞道。
_POOL_WRITE_SYMBOLS = frozenset({
    "set_secid", "add_or_update", "remove_from_pool", "set_type_override",
    "upsert", "remove",
})

#: pool_repository 的**讀取面**。只用在**正對照**(證明掃描器沒瞎),不參與禁令。
_POOL_READ_SYMBOLS = frozenset({
    "list_pool", "resolve_secid", "resolve_isin", "resolve_currency",
    "pool_backend_status", "get_pool_store",
})

#: 受本節規則管的檔案 = 三個查詢面 ＋ 它們共用的取數鏈。
_NO_POOL_WRITE_FILES = ("repositories/fund/sources.py",
                        "repositories/fund/fund_orchestration.py",
                        "repositories/fund/nav_metrics.py",
                        "repositories/fund/fx_and_main.py",
                        "services/fund_row.py",
                        "services/fund_service.py") + _QUERY_SURFACES

#: ⚠️ **已知未修,附理由**(沿用 `tests/test_st_cache_failure_not_cached.py::_WHITELIST` 的體例)。
#:
#: 登記在這裡的**不是**「已判定合憲」,是「**還沒判定**」——
#: 規則對它們**不轉紅**,但它們的存在是**明寫在檔案裡**的,不會無聲消失。
#: ⛔ 要新增一筆,必須寫清楚:**誰在爭什麼**、**誰來裁**、**裁完之後怎麼移除**。
_PENDING_ARBITRATION: "dict[str, str]" = {
    "repositories/fund/sources.py": (
        "2026-09-06:`_src_morningstar_nav` 內 `set_secid as _cache_secid`、"
        "`_src_yahoo_finance_nav` 內 `set_secid as _wb_secid` 兩處回寫,"
        "**兩組獨立稽核結論相反**,已送第三組仲裁,爭點只有一個:"
        "**單基金查詢頁走不走得到那兩支**。\n"
        "本組(F3)實測到的:(a) 那兩個呼叫是活的、不是註解(別名感知 AST);"
        "(b) `set_secid` → `store.upsert` → `Worksheet.update` 是真寫入"
        "(離線 tripwire 實跑,見第 6 節同組假件);"
        "(c) 靜態呼叫鏈逐跳讀 code 確認得通,gate 是 "
        "`0 < span < 300 and (is_insurance_code or _pool_secid_or_isin(code))`。\n"
        "本組**沒有**實測到的:端對端**執行期**重現 —— "
        "`repositories.fund.sources` module-load 需要 pandas/bs4/requests,"
        "本組環境沒有,且**刻意不造假件替代**(假的 pandas 會讓結論變成假的)。\n"
        "⛔ 依派工指示「重現不出來就不要切」,本組**未切除**這兩處。\n"
        "**移除條件**:仲裁判定可達 → 切除兩處回寫、刪掉本筆登記(規則自動接管);"
        "判定不可達 → 仍應刪掉本筆並改為在此註明「不可達,故無須切除」,"
        "**不要讓一筆待仲裁豁免無限期留著**(§8.3.P 前言:待查證沒有出口 ＝ 實質永久豁免)。"
    ),
}


def _pool_symbol_bindings(tree: ast.Module, want) -> "tuple[dict, set]":
    """哪些名字在這個檔案裡**最後**綁到了 pool 的 `want` 那組符號。

    認四種形狀(前三種可解析,第四種另由 `_dynamic_backdoors` 整個禁掉):
      ① `from …pool_repository import set_secid`            → {"set_secid": "set_secid"}
      ② `from …pool_repository import set_secid as _g`      → {"_g": "set_secid"}
      ③ `import …pool_repository as P` → `P.set_secid(…)`   → modaliases={"P"}
      ④ `g = _g` / `g = P.set_secid` → `g(…)`               → 賦值別名,做到不動點

    回 (`{本檔名字: 原始符號}`, `{pool 模組別名}`)。
    """
    direct, modaliases = {}, set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").endswith("pool_repository"):
            for a in node.names:
                if a.name in want:
                    direct[a.asname or a.name] = a.name
                elif a.name == "*":
                    direct.update({w: w for w in want})
        elif isinstance(node, ast.Import):
            for a in node.names:
                if a.name.endswith("pool_repository"):
                    modaliases.add(a.asname or a.name.split(".")[0])

    # ④ 賦值別名 —— 反覆掃到不再長大為止(`g = _g; h = g` 這種鏈也要跟上)
    for _ in range(8):                       # 8 圈護欄,防病態輸入
        grew = False
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign) or len(node.targets) != 1:
                continue
            tgt, val = node.targets[0], node.value
            if not isinstance(tgt, ast.Name):
                continue
            orig = None
            if isinstance(val, ast.Name) and val.id in direct:
                orig = direct[val.id]
            elif (isinstance(val, ast.Attribute) and val.attr in want
                  and isinstance(val.value, ast.Name) and val.value.id in modaliases):
                orig = val.attr
            if orig and direct.get(tgt.id) != orig:
                direct[tgt.id] = orig
                grew = True
        if not grew:
            break
    return direct, modaliases


def _pool_symbol_calls(rel: str, want):
    """該檔內對 `want` 那組 pool 符號的**呼叫點**。回 [(原始符號, 實際寫法, 行號)]。"""
    tree = _parse(rel)
    direct, modaliases = _pool_symbol_bindings(tree, want)
    hits = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if isinstance(f, ast.Name) and f.id in direct:
            hits.append((direct[f.id], f.id, node.lineno))
        elif isinstance(f, ast.Attribute) and f.attr in want:
            base = f.value
            if isinstance(base, ast.Name) and base.id in modaliases:
                hits.append((f.attr, f"{base.id}.{f.attr}", node.lineno))
    return hits


def _dynamic_backdoors(rel: str):
    """靜態解析**看不穿**的兩種形狀 —— 不解析,整個形狀禁掉。

      (a) `getattr(<名字裡有 pool 的東西>, …)` —— 對象就是 pool 模組。
      (a2) `getattr(<任何東西>, <非字面字串>)` —— **屬性名在靜態期不存在**,
           `getattr(m, "set_" + "secid")` 正是這一種:對象叫 `m`,名字是拼出來的,
           兩邊都看不出 pool,只有「名字不是字面值」這件事看得出來。
           ⚠️ 實測(量測日 2026-09-06):9 個受管檔案目前**一處都沒有**這種寫法,
           所以這條禁令**不會**讓任何既有程式碼轉紅 —— 它擋的是未來的繞道。
      (b) `importlib.import_module(<非字面字串>)` 或 `import_module("…pool_repository")`
          —— 字串拼接讓模組名在靜態期不存在,任何名字白名單都掃不到。
    """
    tree = _parse(rel)
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
        if name == "getattr" and node.args:
            a0 = node.args[0]
            nm = getattr(a0, "id", "") or getattr(a0, "attr", "")
            if "pool" in nm.lower():
                out.append(("getattr(pool…)", node.lineno))
            elif len(node.args) >= 2:
                a1 = node.args[1]
                if not (isinstance(a1, ast.Constant) and isinstance(a1.value, str)):
                    out.append(("getattr(…, <非字面屬性名>)", node.lineno))
        elif name in ("import_module", "__import__") and node.args:
            a0 = node.args[0]
            if isinstance(a0, ast.Constant) and isinstance(a0.value, str):
                if a0.value.endswith("pool_repository"):
                    out.append((f'import_module("{a0.value}")', node.lineno))
            else:
                # 非字面字串(拼接 / 變數)→ 靜態不可解析 → 一律禁
                out.append(("import_module(<非字面字串>)", node.lineno))
    return out


class TestQueryPathNeverWritesBackToThePool:
    """規則本體。⚠️ **綠燈的意思是「沒有**新增**」,不是「已經切乾淨」** ——
    `_PENDING_ARBITRATION` 內的檔案被排除在禁令之外(但被下面兩條盯著不准變多)。

    突變驗證:在任一受管檔案裡加一行 pool 寫入(不論用哪種別名寫法)→ 本組轉紅。
    """

    @pytest.mark.parametrize("rel", _NO_POOL_WRITE_FILES)
    def test_no_pool_write_symbol_is_callable_on_a_query_path(self, rel):
        hits = _pool_symbol_calls(rel, _POOL_WRITE_SYMBOLS)
        if rel in _PENDING_ARBITRATION:
            pytest.skip(f"{rel} 待仲裁(見 _PENDING_ARBITRATION):"
                        f"目前 {len(hits)} 處,由 test_pending_arbitration_* 兩條盯著")
        assert not hits, (
            f"{rel} 在查詢鏈上回寫選股池:\n  "
            + "\n  ".join(f"{rel}:{ln} → {orig}()（寫成 {shown}）" for orig, shown, ln in hits)
            + "\n客戶 2026-09-06:查詢一律唯讀,絕對禁止反向寫入 Google Sheet。\n"
              "⚠️ 若這真的是使用者**明確按下**的動作,它就不該住在取數鏈上 —— "
              "請把它移到有按鈕的那一層（例:⑤ 設定頁的 `_render_pool_editor`）。")

    @pytest.mark.parametrize("rel", _NO_POOL_WRITE_FILES)
    def test_no_dynamic_backdoor(self, rel):
        """動態繞道**不分待仲裁與否,一律禁** —— 待仲裁的是「那兩處回寫」,不是「可以亂寫」。"""
        bad = _dynamic_backdoors(rel)
        assert not bad, (
            f"{rel} 出現靜態解析不了的取名形狀:{bad}\n"
            f"這是名字白名單天生看不穿的洞,所以整個形狀禁掉。")

    # ── 待仲裁豁免:盯著它不准變多、不准沒理由 ──────────────────────

    def test_pending_arbitration_entries_carry_a_reason(self):
        """豁免必須寫明「誰在爭什麼、誰來裁、怎麼移除」—— 沒理由的豁免就是永久豁免。"""
        for rel, why in _PENDING_ARBITRATION.items():
            assert (_REPO / rel).exists(), f"{rel} 已不存在 → 這筆豁免過期了,請刪掉"
            assert "仲裁" in why and "移除條件" in why, (
                f"{rel} 的豁免理由不完整(要有爭點與移除條件):{why[:80]}…")

    def test_the_pending_write_sites_do_not_multiply(self):
        """⭐ 待仲裁 ≠ 放行:**處數不准增加**。

        2026-09-06 量測:`repositories/fund/sources.py` 有 **2** 處
        (`_src_morningstar_nav::_cache_secid`、`_src_yahoo_finance_nav::_wb_secid`)。
        再多一處 → 本條轉紅。
        ⚠️ 這個數字**會漂移**:仲裁判定可達並切除後,它會變成 0,屆時請一併刪掉本條與豁免登記。
        """
        hits = _pool_symbol_calls("repositories/fund/sources.py", _POOL_WRITE_SYMBOLS)
        assert len(hits) <= 2, (
            f"待仲裁期間又新增了 pool 寫入(2026-09-06 量測為 2 處,現在 {len(hits)} 處):"
            f"{[(o, s, l) for o, s, l in hits]}")

    # ── 正對照:先證明這條規則看得見東西 ──────────────────────────────

    def test_the_rule_can_actually_see_a_pool_write(self):
        """⭐ 正對照:在一個**已知有** pool 寫入的檔案裡必須看得到,否則所有「0 命中」都不可信。

        `ui/helpers/fund_grp_health/switch_advisor_section.py::_render_pool_editor`
        是使用者**按存檔鈕**才走到的合法寫入 —— 它不受本節禁令管,只當「規則沒瞎」的證據。
        """
        hits = _pool_symbol_calls(
            "ui/helpers/fund_grp_health/switch_advisor_section.py", _POOL_WRITE_SYMBOLS)
        assert hits, "正對照失效:在一個已知有 pool 寫入的檔案裡什麼都沒看到"

    def test_reads_are_deliberately_left_alone(self):
        """⭐ 反向護欄:本節管的是「寫」,不是「用」。

        `repositories/fund/sources.py` 必須繼續讀得到選股池
        (`resolve_secid` / `resolve_isin` / `resolve_currency`)——
        沒有它們,使用者填的 ISIN 就串不起來,那是把功能砍掉而不是把副作用切掉。
        """
        reads = _pool_symbol_calls("repositories/fund/sources.py", _POOL_READ_SYMBOLS)
        assert {orig for orig, _s, _l in reads} >= {"resolve_isin", "resolve_secid"}, (
            f"ISIN→secId 的查表讀取不見了:目前只剩 {sorted({o for o, _s, _l in reads})}")


class TestTheRuleSeesTheKnownBypasses:
    """⭐ **本節最重要的一組**:逐一釘住第 4、5 節那種寫法**擋不住**的四個繞道。

    每一條都拿一段**合成的違規程式碼**餵給規則,規則必須看得見。
    ⚠️ 這四條與「查詢頁可達性」那個爭議**完全無關** ——
       不論仲裁怎麼裁,一條換個寫法就繞過去的規則都該修。
    """

    def test_bypass_1_import_alias(self):
        """`from m import set_secid as _g` → `_g(...)`(＝本次兩處回寫實際用的寫法)。"""
        tree = ast.parse("from repositories.pool_repository import set_secid as _cache_secid\n"
                         "def f(c, s):\n    _cache_secid(c, s, currency='USD')\n")
        direct, _ = _pool_symbol_bindings(tree, _POOL_WRITE_SYMBOLS)
        assert direct == {"_cache_secid": "set_secid"}, (
            "import 別名解析壞了 → 字面 grep `set_secid` 只掃得到 import 那一行,規則等於沒有")

    def test_bypass_2_module_attribute(self):
        """`import m as P` → `P.set_secid(...)`。"""
        tree = ast.parse("import repositories.pool_repository as P\n"
                         "def f(c, s):\n    P.set_secid(c, s)\n")
        _d, mods = _pool_symbol_bindings(tree, _POOL_WRITE_SYMBOLS)
        assert mods == {"P"}
        hits = [n.func.attr for n in ast.walk(tree)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr in _POOL_WRITE_SYMBOLS]
        assert hits == ["set_secid"]

    def test_bypass_3_assignment_alias(self):
        """`g = _cache_secid` → `g(...)` —— **賦值**別名,不是 import 別名。"""
        tree = ast.parse("from repositories.pool_repository import set_secid as _cache_secid\n"
                         "_g = _cache_secid\n"
                         "def f(c, s):\n    _g(c, s)\n")
        direct, _ = _pool_symbol_bindings(tree, _POOL_WRITE_SYMBOLS)
        assert direct.get("_g") == "set_secid", (
            f"賦值別名沒被解析到:{direct} —— 這是派工單點名的第三種繞道")

    def test_bypass_3b_assignment_from_module_attribute(self):
        """`g = P.set_secid` → `g(...)`。"""
        tree = ast.parse("import repositories.pool_repository as P\n"
                         "_g = P.set_secid\n"
                         "def f(c, s):\n    _g(c, s)\n")
        direct, _ = _pool_symbol_bindings(tree, _POOL_WRITE_SYMBOLS)
        assert direct.get("_g") == "set_secid", f"模組屬性賦值別名沒被解析到:{direct}"

    def test_bypass_4_dynamic_import_and_getattr_are_banned_outright(self, tmp_path):
        """`importlib.import_module("a"+"b")` / `getattr(pool_mod, …)` —— 靜態看不穿 → 整個形狀禁。

        ⚠️ 這一條刻意**在真的檔案上**驗規則(而不是只驗 helper),
        因為 `_dynamic_backdoors` 是走 `_parse(rel)` 讀 repo 內檔案的。
        """
        import pathlib as _pl
        rel = "tests/_f3_bypass_fixture_tmp.py"
        f = _REPO / rel
        f.write_text(
            "import importlib\n"
            "def a():\n"
            "    m = importlib.import_module('repositories.pool' + '_repository')\n"
            "    getattr(m, 'set_' + 'secid')('X', 'Y')\n"
            "def b():\n"
            "    importlib.import_module('repositories.pool_repository')\n",
            encoding="utf-8")
        try:
            kinds = {k for k, _ln in _dynamic_backdoors(rel)}
        finally:
            f.unlink()
        assert "import_module(<非字面字串>)" in kinds, "字串拼接的動態 import 沒被抓到"
        assert 'import_module("repositories.pool_repository")' in kinds, "字面動態 import 沒被抓到"
        assert "getattr(…, <非字面屬性名>)" in kinds, (
            f"getattr 動態取名沒被抓到:{kinds} —— "
            f"`getattr(m, 'set_' + 'secid')` 的對象叫 `m`、屬性名是拼出來的,"
            f"兩邊都看不出 pool,只能靠「屬性名不是字面值」抓")
        assert isinstance(_pl.Path(str(f)), _pl.Path)      # 純為讓 lint 看得見 import

    def test_the_old_name_whitelist_rules_would_have_missed_all_four(self):
        """⭐ 把「舊規則為什麼不夠」變成機器可驗的事實,而不是一句抱怨。

        第 5 節的 `_record_call_sites` 只認 `_RECORD_NAMES` 那兩個名字 ——
        對上面四種繞道**一律 0 命中**(因為它們碰的根本是另一個模組、另一個名字)。
        """
        src = ("from repositories.pool_repository import set_secid as _g\n"
               "def f(c, s):\n    _g(c, s)\n")
        tree = ast.parse(src)
        direct_old, _ = _bound_write_aliases(tree)          # 第 5 節那條規則的解析器
        assert direct_old == set(), (
            "舊規則竟然看得到 pool 寫入 —— 那本節的前提就錯了,請重寫本節說明")
        direct_new, _ = _pool_symbol_bindings(tree, _POOL_WRITE_SYMBOLS)
        assert direct_new == {"_g": "set_secid"}, "新規則反而看不到 → 本節白做了"
