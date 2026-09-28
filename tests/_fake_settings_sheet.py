# -*- coding: utf-8 -*-
"""設定試算表測試用的假 gspread（只實作 `repositories/settings_sheet_repository.py` 用到的呼叫）。

不 import gspread：系統 python 沒有它，而本檔要模擬的只是呼叫形狀與「上游往返次數」。
往返一律記進 `FakeSpreadsheet.calls`，測試用它量「有沒有真的打上游」
（仿 tests/test_gspread_source_backoff.py：只有計數器分得出「沒重打」與「重打了但結果一樣」）。
"""

from __future__ import annotations


# ── 寫入型方法一覽（`FakeSpreadsheet.writes()` 的真相源；第 14 輪假斷言 3）──────────────
#
# ⚠️ 為什麼要有這份清單：`writes()` 原本只認 `append_rows`／`add_worksheet`／`del_worksheet`，
# 名字卻叫「writes」。`update`／`batch_update`／`clear`／`delete_rows` 這些 gspread 的寫入方法
# **不在清單內** —— 實作若改成用它們寫入，`writes()` 會回 `[]`，「只讀不寫」的斷言當場變成假的。
# 當時擋住這件事的是「`FakeWorksheet` 沒有這些方法會 `AttributeError`」，**那是運氣，不是設計**：
# 一旦有人為了別的測試補上其中任何一個方法，這道保護就無聲消失。
# 現在改成：**明確攔截並記錄**，讓寫入真的走得到、而且一定被 `writes()` 看見。
# 攔截到的方法一律只記錄、不改資料（回傳 `{}`），這樣測試流程會繼續走到 `writes()` 的斷言，
# 而不是先死在 `AttributeError` 上、留下一個看不出原因的紅燈。
WRITE_METHODS_WORKSHEET = (
    "append_row", "append_rows", "insert_row", "insert_rows",
    "update", "update_cell", "update_cells", "update_acell", "batch_update",
    "clear", "batch_clear", "delete_rows", "delete_row", "delete_columns",
    "resize", "add_rows", "add_cols", "update_title", "sort", "format",
    "merge_cells", "unmerge_cells", "update_note", "clear_note",
    "copy_range", "cut_range",
)
WRITE_METHODS_SPREADSHEET = (
    "add_worksheet", "del_worksheet", "duplicate_sheet",
    "batch_update", "values_update", "values_append", "values_clear",
    "values_batch_update", "values_batch_clear", "batch_clear", "update_title",
)
WRITE_METHODS = tuple(sorted(set(WRITE_METHODS_WORKSHEET) | set(WRITE_METHODS_SPREADSHEET)))


def _install_write_interceptors(cls, names):
    """把 `names` 裡還沒有實作的方法補成「記錄一筆、不改資料」的攔截器。

    已經有真實作的（`append_rows`／`add_worksheet`／`del_worksheet`）**不覆蓋** —— 那幾支要保留
    原本的行為（含 `fail_next` 注入失敗、真的把列寫進去），既有測試靠它們。
    """
    for name in names:
        if hasattr(cls, name):
            continue

        def _make(method_name):
            def _intercept(self, *args, **kwargs):
                book = getattr(self, "book", self)
                title = getattr(self, "title", None)
                book.calls.append((method_name, title, args, tuple(sorted(kwargs))))
                book._maybe_fail(method_name, title)
                return {}
            _intercept.__name__ = method_name
            return _intercept

        setattr(cls, name, _make(name))


class FakeWorksheet:
    def __init__(self, book: "FakeSpreadsheet", title: str, rows=None):
        self.book = book
        self.title = title
        self.rows = [list(r) for r in (rows or [])]

    def append_rows(self, values, value_input_option=None, insert_data_option=None, **_kw):
        self.book.calls.append(("append_rows", self.title, value_input_option, insert_data_option))
        failure = self.book.pop_failure("append_rows", self.title)
        if failure is not None:
            delivered, exc = failure
            if delivered:                                    # 已送達、但回報失敗
                self.rows.extend([list(v) for v in values])
            raise exc
        self.rows.extend([list(v) for v in values])
        return {}


class FakeSpreadsheet:
    def __init__(self, tabs=None):
        self.calls = []
        self.tabs = {}
        self._failures = []       # [(method, title 或 None, delivered, exc)]
        self.on_batch_get = None  # 批次讀取回傳前呼叫的鉤子（測試用來模擬「讀取期間有人寫入」）
        for title, rows in (tabs or {}).items():
            self.tabs[title] = FakeWorksheet(self, title, rows)

    # ── 注入失敗 ──
    def fail_next(self, method: str, exc: BaseException, *, title=None, delivered=False, times=1):
        for _ in range(times):
            self._failures.append((method, title, delivered, exc))

    def pop_failure(self, method, title=None):
        for i, (m, t, delivered, exc) in enumerate(self._failures):
            if m == method and (t is None or t == title):
                del self._failures[i]
                return delivered, exc
        return None

    def _maybe_fail(self, method, title=None):
        failure = self.pop_failure(method, title)
        if failure is not None:
            raise failure[1]

    # ── gspread 介面 ──
    def worksheets(self, exclude_hidden=False):
        self.calls.append(("worksheets",))
        self._maybe_fail("worksheets")
        return list(self.tabs.values())

    def values_batch_get(self, ranges, params=None):
        self.calls.append(("values_batch_get", tuple(ranges), dict(params or {})))
        self._maybe_fail("values_batch_get")
        out = []
        for rng in ranges:
            title = rng[1:-1].replace("''", "'")
            rows = [list(r) for r in self.tabs[title].rows]
            # 仿 Sheets API：每列去掉尾端空儲存格、整張表去掉尾端空列；空表沒有 values 鍵
            trimmed = []
            for r in rows:
                while r and r[-1] == "":
                    r.pop()
                trimmed.append(r)
            while trimmed and trimmed[-1] == []:
                trimmed.pop()
            block = {"range": rng}
            if trimmed:
                block["values"] = trimmed
            out.append(block)
        if self.on_batch_get is not None:
            self.on_batch_get()
        return {"spreadsheetId": "fake", "valueRanges": out}

    def add_worksheet(self, title, rows, cols, index=None):
        self.calls.append(("add_worksheet", title))
        self._maybe_fail("add_worksheet")
        if title in self.tabs:
            raise Exception(f'A sheet with the name "{title}" already exists.')
        ws = FakeWorksheet(self, title)
        self.tabs[title] = ws
        return ws

    # 防回歸用：實作不得刪分頁（`50` 第 6 節；回修第 3 輪撤銷了刪分頁路徑）。保留這個假方法，
    # 讓「加回刪分頁」的突變真的能執行、被 `test_標頭已送達但回報失敗_…` 等測試抓到，而不是先死在 AttributeError。
    def del_worksheet(self, worksheet):
        self.calls.append(("del_worksheet", worksheet.title))
        self._maybe_fail("del_worksheet")
        del self.tabs[worksheet.title]

    def data(self, title):
        """某分頁的全部列（含標頭），給測試斷言用。"""
        return [list(r) for r in self.tabs[title].rows]

    def writes(self):
        """所有寫入型往返。真相源是 `WRITE_METHODS`（第 14 輪假斷言 3：原本只認三個名字）。"""
        return [c for c in self.calls if c[0] in WRITE_METHODS]


_install_write_interceptors(FakeWorksheet, WRITE_METHODS_WORKSHEET)
_install_write_interceptors(FakeSpreadsheet, WRITE_METHODS_SPREADSHEET)


class FakeClient:
    def __init__(self, book: FakeSpreadsheet):
        self.book = book
        self.opened = []

    def open_by_key(self, key):
        self.book.calls.append(("open_by_key", key))
        self.opened.append(key)
        self.book._maybe_fail("open_by_key")
        return self.book
