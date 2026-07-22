"""tests/test_nav_history_import.py — v19.361 PR-2(A):保單對帳單 CSV 匯入 nav_history。

守:
- header CSV(西元)/ ROC 民國日期 / 無 header 兩欄 → 都能解析寫入
- 千分位逗號 nav / 壞列(爛日期、nav<=0、缺欄)顯式 skip + 計數(§1)
- (code,date) 對既有列去重(§5 冪等,重跑不灌水)
- GS 未啟用 → enabled=False、不寫(誠實回報,UI 顯示錯誤)
"""
from __future__ import annotations

import pytest

from services import nav_history_gs as M


class _WS:
    def __init__(self, rows=None):
        self.rows = rows if rows is not None else [list(M._NAV_HEADERS)]

    def get_all_values(self):
        return [[str(c) for c in r] for r in self.rows]

    def append_rows(self, rows, **k):
        self.rows.extend([list(r) for r in rows])

    def update(self, rng, values):
        pass


class _Sheet:
    def __init__(self, ws=None):
        self._ws = ws or _WS()

    def worksheet(self, name):
        return self._ws

    def add_worksheet(self, title, rows, cols):
        return self._ws


def test_import_header_csv_western_dates():
    sh = _Sheet()
    csv = "日期,淨值\n2024/03/15,12.34\n2024/03/16,12.40\n"
    res = M.import_csv_text("TLZF9", csv, _sheet=sh)
    assert res["parsed"] == 2 and res["written"] == 2 and res["skipped_rows"] == 0
    assert sh._ws.rows[1][0] == "TLZF9" and sh._ws.rows[1][1] == "2024-03-15"


def test_import_roc_dates():
    sh = _Sheet()
    csv = "淨值日期,單位淨值\n113/03/15,10.5\n113.03.18,10.6\n"
    res = M.import_csv_text("ACTI71", csv, _sheet=sh)
    assert res["written"] == 2
    dates = {r[1] for r in sh._ws.rows[1:]}
    assert dates == {"2024-03-15", "2024-03-18"}       # 民國 113 = 西元 2024


def test_import_headerless_two_columns():
    sh = _Sheet()
    csv = "2024-03-15,12.34\n2024-03-16,12.40\n"
    res = M.import_csv_text("X", csv, _sheet=sh)
    assert res["parsed"] == 2 and res["written"] == 2


def test_import_thousand_separator_and_bad_rows_counted():
    sh = _Sheet()
    csv = ("date,nav\n"
           "2024-03-15,\"1,234.5\"\n"     # 千分位 → 1234.5
           "壞日期,10.0\n"                 # 爛日期 → skip
           "2024-03-17,0\n"               # nav<=0 → skip
           "2024-03-18\n")                # 缺欄 → skip
    res = M.import_csv_text("X", csv, _sheet=sh)
    assert res["written"] == 1 and res["skipped_rows"] == 3
    assert float(sh._ws.rows[1][2]) == 1234.5


def test_import_dedup_against_existing():
    ws = _WS(rows=[list(M._NAV_HEADERS),
                   ["TLZF9", "2024-03-15", "12.34", "", "app", "t"]])
    sh = _Sheet(ws)
    csv = "date,nav\n2024/03/15,99.9\n2024/03/16,12.40\n"
    res = M.import_csv_text("TLZF9", csv, _sheet=sh)
    assert res["written"] == 1 and res["skipped_dup"] == 1   # 撞日不覆蓋、不灌水
    assert len(ws.rows) == 3


def test_import_gs_disabled_honest(monkeypatch):
    monkeypatch.setattr(M, "is_enabled", lambda: False)
    res = M.import_csv_text("X", "date,nav\n2024-03-15,10.0\n")  # 不注入 _sheet
    assert res["enabled"] is False and res["written"] == 0 and res["parsed"] == 1


def test_import_empty_text():
    res = M.import_csv_text("X", "", _sheet=_Sheet())
    assert res["rows"] == 0 and res["written"] == 0
