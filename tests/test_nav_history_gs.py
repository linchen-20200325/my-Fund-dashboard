"""tests/test_nav_history_gs.py — v19.359 Track 2:App 端 NAV 累積到 Google Sheets。

守:
- append_points 真的寫入新筆 + (code,date) 去重(冪等,§5)
- §1 Fail Loud:nav<=0 / date 壞 / code 空 → 不寫;真 GS I/O 失敗 → raise NavHistoryError
- is_enabled 未齊 → 安靜 no-op(不 raise,不寫)
- _norm_date 容錯(斜線 / date 物件 / 帶時間 / 壞值)
- L3 helper _extract_point 取 SSOT(series 末優先,fallback metrics+nav_date,不足回 None)
"""
from __future__ import annotations

import datetime as _dt

import pandas as pd
import pytest

from services import nav_history_gs as M
from services.nav_history_gs import NavHistoryError


# ── Fake gspread ──────────────────────────────────────────────
class _FakeWS:
    def __init__(self, rows=None):
        # rows 含 header row(比照真 sheet)
        self.rows = rows if rows is not None else [list(M._NAV_HEADERS)]

    def get_all_values(self):
        return [[str(c) for c in r] for r in self.rows]

    def append_row(self, row, **k):
        self.rows.append(list(row))

    def append_rows(self, rows, **k):
        self.rows.extend([list(r) for r in rows])

    def update(self, rng, values):  # header 寫入 no-op
        pass


class _FakeSheet:
    """worksheet(name) 回既有 ws;missing=True 時第一次 raise → 觸發 add_worksheet。"""
    def __init__(self, ws=None, missing=False, raise_on_append=False):
        self._ws = ws if ws is not None else _FakeWS()
        self._missing = missing
        self._raise_on_append = raise_on_append
        self.added_title = None

    def worksheet(self, name):
        if self._missing:
            raise RuntimeError("worksheet not found")
        return self._ws

    def add_worksheet(self, title, rows, cols):
        self.added_title = title
        self._ws = _FakeWS(rows=[list(M._NAV_HEADERS)])
        self._missing = False
        if self._raise_on_append:
            def _boom(*a, **k):
                raise RuntimeError("gspread 429 quota")
            self._ws.append_rows = _boom  # type: ignore
        return self._ws


# ── append_points 核心 ────────────────────────────────────────
def test_append_points_writes_new_row():
    sh = _FakeSheet()
    res = M.append_points(
        [{"code": "TLZF9", "nav": 12.34, "nav_date": "2026-07-22", "fund_name": "安聯"}],
        _sheet=sh,
    )
    assert res == {"written": 1, "skipped": 0}
    # header + 1 資料列
    assert len(sh._ws.rows) == 2
    row = sh._ws.rows[1]
    assert row[0] == "TLZF9" and row[1] == "2026-07-22" and float(row[2]) == 12.34


def test_append_point_single_wrapper_returns_bool():
    sh = _FakeSheet()
    assert M.append_point("ANZ89", 9.87, "2026-07-22", _sheet=sh) is True
    # 同 (code,date) 再寫 → 冪等略過
    assert M.append_point("ANZ89", 9.99, "2026-07-22", _sheet=sh) is False


def test_dedup_against_existing_code_date():
    sh = _FakeSheet(_FakeWS(rows=[list(M._NAV_HEADERS),
                                  ["TLZF9", "2026-07-22", "12.34", "安聯", "app", "t"]]))
    res = M.append_points(
        [{"code": "TLZF9", "nav": 99.9, "nav_date": "2026-07-22"},   # 同日 → skip
         {"code": "TLZF9", "nav": 12.50, "nav_date": "2026-07-23"}], # 新日 → write
        _sheet=sh,
    )
    assert res["written"] == 1
    assert sh._ws.rows[-1][1] == "2026-07-23"


def test_dedup_within_same_batch():
    sh = _FakeSheet()
    res = M.append_points(
        [{"code": "JFZN3", "nav": 10.0, "nav_date": "2026-07-22"},
         {"code": "JFZN3", "nav": 10.1, "nav_date": "2026-07-22"}],  # 同批同日 → 只留 1
        _sheet=sh,
    )
    assert res["written"] == 1


def test_creates_worksheet_when_missing():
    sh = _FakeSheet(missing=True)
    res = M.append_points([{"code": "CTZP0", "nav": 5.5, "nav_date": "2026-07-22"}], _sheet=sh)
    assert res["written"] == 1
    assert sh.added_title == M._WS_NAV


# ── §1 Fail Loud:資料不足不寫 ────────────────────────────────
@pytest.mark.parametrize("bad", [
    {"code": "", "nav": 10.0, "nav_date": "2026-07-22"},        # 空 code
    {"code": "X", "nav": 0, "nav_date": "2026-07-22"},          # nav<=0
    {"code": "X", "nav": -1.0, "nav_date": "2026-07-22"},       # 負 nav
    {"code": "X", "nav": "abc", "nav_date": "2026-07-22"},      # nav 非數字
    {"code": "X", "nav": 10.0, "nav_date": "壞日期"},            # date 壞
    {"code": "X", "nav": 10.0, "nav_date": ""},                # date 空
])
def test_insufficient_data_not_written(bad):
    sh = _FakeSheet()
    res = M.append_points([bad], _sheet=sh)
    assert res["written"] == 0
    assert len(sh._ws.rows) == 1  # 只有 header,沒寫入


def test_gs_disabled_is_silent_noop(monkeypatch):
    monkeypatch.setattr(M, "is_enabled", lambda: False)
    # 不注入 _sheet → 走 is_enabled 判斷 → no-op,不 raise
    res = M.append_points([{"code": "X", "nav": 10.0, "nav_date": "2026-07-22"}])
    assert res["written"] == 0


def test_real_io_failure_raises_navhistoryerror():
    sh = _FakeSheet(missing=True, raise_on_append=True)
    with pytest.raises(NavHistoryError):
        M.append_points([{"code": "X", "nav": 10.0, "nav_date": "2026-07-22"}], _sheet=sh)


# ── _norm_date 容錯 ───────────────────────────────────────────
@pytest.mark.parametrize("inp,exp", [
    ("2026-07-22", "2026-07-22"),
    ("2026/07/22", "2026-07-22"),
    ("2026-07-22T04:31:00", "2026-07-22"),
    (_dt.date(2026, 7, 22), "2026-07-22"),
    (_dt.datetime(2026, 7, 22, 4, 31), "2026-07-22"),
    ("", ""),
    (None, ""),
    ("not-a-date", ""),
    ("07/22/2026", ""),   # 非 YYYY 開頭 → 拒(§1 不猜)
])
def test_norm_date(inp, exp):
    assert M._norm_date(inp) == exp


# ── load_points ───────────────────────────────────────────────
def test_load_points_filters_by_code():
    sh = _FakeSheet(_FakeWS(rows=[
        list(M._NAV_HEADERS),
        ["TLZF9", "2026-07-22", "12.34", "安聯", "app", "t1"],
        ["ANZ89", "2026-07-22", "9.87", "安聯", "app", "t2"],
    ]))
    got = M.load_points("TLZF9", _sheet=sh)
    assert len(got) == 1 and got[0]["code"] == "TLZF9" and got[0]["nav"] == 12.34


# ── L3 helper _extract_point(SSOT 取值)────────────────────────
def _mk_series():
    idx = pd.to_datetime(["2026-07-20", "2026-07-21", "2026-07-22"])
    return pd.Series([10.0, 10.5, 11.0], index=idx)


def test_extract_point_prefers_series_last():
    from ui.helpers.nav_history_hook import _extract_point
    fd = {"full_key": "TLZF9", "series": _mk_series(),
          "metrics": {"nav": 999.0}, "nav_date": "2000-01-01", "fund_name": "安聯"}
    p = _extract_point(fd)
    # SSOT:走 series 末(11.0 / 2026-07-22),不吃 metrics 的 999 或舊 nav_date
    assert p["code"] == "TLZF9" and p["nav"] == 11.0 and p["nav_date"] == "2026-07-22"


def test_extract_point_fallback_to_metrics_when_no_series():
    from ui.helpers.nav_history_hook import _extract_point
    fd = {"full_key": "ANZ89", "series": None,
          "metrics": {"nav": 9.87}, "nav_date": "2026-07-22"}
    p = _extract_point(fd)
    assert p["nav"] == 9.87 and p["nav_date"] == "2026-07-22"


def test_extract_point_code_hint_overrides():
    from ui.helpers.nav_history_hook import _extract_point
    fd = {"series": _mk_series()}  # 無 full_key
    p = _extract_point(fd, code_hint="JFZN3")
    assert p["code"] == "JFZN3"


@pytest.mark.parametrize("fd", [
    {"full_key": "", "series": _mk_series()},               # 無 code
    {"full_key": "X", "series": None, "metrics": {}},        # 無 nav 無 series
    {"full_key": "X", "series": None,
     "metrics": {"nav": 0}, "nav_date": "2026-07-22"},       # nav<=0
    {"full_key": "X", "series": None,
     "metrics": {"nav": 10.0}, "nav_date": ""},              # 無 date
    "not-a-dict",
])
def test_extract_point_returns_none_on_insufficient(fd):
    from ui.helpers.nav_history_hook import _extract_point
    assert _extract_point(fd) is None
