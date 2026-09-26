# -*- coding: utf-8 -*-
"""設定試算表測試用的假 gspread（只實作 `repositories/settings_sheet_repository.py` 用到的呼叫）。

不 import gspread：系統 python 沒有它，而本檔要模擬的只是呼叫形狀與「上游往返次數」。
往返一律記進 `FakeSpreadsheet.calls`，測試用它量「有沒有真的打上游」
（仿 tests/test_gspread_source_backoff.py：只有計數器分得出「沒重打」與「重打了但結果一樣」）。
"""

from __future__ import annotations


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
        return {"spreadsheetId": "fake", "valueRanges": out}

    def add_worksheet(self, title, rows, cols, index=None):
        self.calls.append(("add_worksheet", title))
        self._maybe_fail("add_worksheet")
        if title in self.tabs:
            raise Exception(f'A sheet with the name "{title}" already exists.')
        ws = FakeWorksheet(self, title)
        self.tabs[title] = ws
        return ws

    def data(self, title):
        """某分頁的全部列（含標頭），給測試斷言用。"""
        return [list(r) for r in self.tabs[title].rows]

    def writes(self):
        return [c for c in self.calls if c[0] in ("append_rows", "add_worksheet")]


class FakeClient:
    def __init__(self, book: FakeSpreadsheet):
        self.book = book
        self.opened = []

    def open_by_key(self, key):
        self.book.calls.append(("open_by_key", key))
        self.opened.append(key)
        self.book._maybe_fail("open_by_key")
        return self.book
