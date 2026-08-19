"""L1 組合績效快照持久化(repositories/portfolio_perf_repository,v19.430)。

守:欄位↔_HEADERS 對齊、to_row/from_row round-trip(None↔空、bool)、本地 upsert 同日覆蓋 +
排序、空 date 拒收(§1)、GS 後端 upsert/load(fake worksheet,不觸網)。
"""
from __future__ import annotations


import pytest

from repositories.portfolio_perf_repository import (
    _HEADERS,
    GoogleSheetsPerfStore,
    LocalJsonPerfStore,
    PerfSnapshot,
)


def _snap(date="2026-08-11", **kw):
    base = dict(period_return_pct=3.5, cagr_pct=12.0, ann_vol_pct=8.0, sharpe=1.4,
                max_drawdown_pct=-6.2, n_funds=3, total_cost_twd=500000.0,
                is_equal_weight=False, weights_hash="abc", weights_json='{"A":0.6,"B":0.4}',
                coverage_start="2026-01-01", coverage_end=date, n_days=150,
                recorded_at="2026-08-11T09:00:00+00:00")
    base.update(kw)
    return PerfSnapshot(date=date, **base)


# ── schema 對齊 + round-trip ────────────────────────────────
def test_field_order_matches_headers():
    from dataclasses import fields
    assert [f.name for f in fields(PerfSnapshot)] == _HEADERS


def test_to_row_from_row_roundtrip():
    s = _snap()
    r = s.to_row()
    assert len(r) == len(_HEADERS)
    back = PerfSnapshot.from_row(r)
    assert back == s                                       # 完全還原


def test_none_numeric_roundtrips_as_none_not_zero():
    s = _snap(sharpe=None, cagr_pct=None, total_cost_twd=None)
    back = PerfSnapshot.from_row(s.to_row())
    assert back.sharpe is None and back.cagr_pct is None   # §1:缺值不變 0
    assert back.total_cost_twd is None


def test_bool_roundtrips():
    assert PerfSnapshot.from_row(_snap(is_equal_weight=True).to_row()).is_equal_weight is True
    assert PerfSnapshot.from_row(_snap(is_equal_weight=False).to_row()).is_equal_weight is False


def test_from_row_blank_date_is_none():
    assert PerfSnapshot.from_row(["", "1", "2"]) is None
    assert PerfSnapshot.from_dict({"date": "  "}) is None


# ── 本地 JSON 後端 ────────────────────────────────
def test_local_append_and_load_sorted(tmp_path):
    store = LocalJsonPerfStore(base_dir=tmp_path)
    store.append_snapshot(_snap("2026-08-11", cagr_pct=12.0))
    store.append_snapshot(_snap("2026-08-09", cagr_pct=9.0))
    store.append_snapshot(_snap("2026-08-10", cagr_pct=10.0))
    got = store.load_snapshots()
    assert [s.date for s in got] == ["2026-08-09", "2026-08-10", "2026-08-11"]  # 舊→新


def test_local_same_day_overwrites_last(tmp_path):
    store = LocalJsonPerfStore(base_dir=tmp_path)
    store.append_snapshot(_snap("2026-08-11", cagr_pct=12.0))
    store.append_snapshot(_snap("2026-08-11", cagr_pct=15.0))   # 同日 → 覆蓋
    got = store.load_snapshots()
    assert len(got) == 1 and got[0].cagr_pct == 15.0


def test_local_append_empty_date_raises(tmp_path):
    store = LocalJsonPerfStore(base_dir=tmp_path)
    with pytest.raises(ValueError):
        store.append_snapshot(PerfSnapshot(date=""))


def test_local_corrupt_file_treated_empty_not_overwritten(tmp_path):
    p = tmp_path / "perf_history.json"
    p.write_text("{bad json", encoding="utf-8")
    store = LocalJsonPerfStore(base_dir=tmp_path)
    assert store.load_snapshots() == []                    # 壞檔 → 視為空
    assert p.read_text(encoding="utf-8") == "{bad json"    # §1:未覆蓋原檔


def test_local_non_list_json_treated_empty(tmp_path):
    (tmp_path / "perf_history.json").write_text('{"date":"x"}', encoding="utf-8")
    assert LocalJsonPerfStore(base_dir=tmp_path).load_snapshots() == []


# ── Google Sheets 後端(fake worksheet,不觸網)────────────────
class _FakeWS:
    def __init__(self, rows):
        self.rows = [list(r) for r in rows]
        self.updates = []

    def get_all_values(self):
        return [list(r) for r in self.rows]

    def row_values(self, n):
        return list(self.rows[n - 1]) if len(self.rows) >= n else []

    def update(self, rng, values):
        self.updates.append((rng, values))
        # 模擬:A{idx} 起寫一列
        import re
        m = re.match(r"A(\d+)", rng)
        if m:
            idx = int(m.group(1)) - 1
            while len(self.rows) <= idx:
                self.rows.append([""] * len(_HEADERS))
            self.rows[idx] = list(values[0])

    def append_row(self, row, value_input_option="RAW"):
        row = list(row)
        if value_input_option == "USER_ENTERED":
            # 模擬 Google Sheets:ISO 日期字串會被解析成日期型,get_all_values 回顯示字串
            # (en_US → "M/D/YYYY")。用 RAW 才會保留字面值 "YYYY-MM-DD"(主鍵去重靠它)。
            import re
            if row and re.match(r"^\d{4}-\d{2}-\d{2}$", str(row[0])):
                _y, _m, _d = str(row[0]).split("-")
                row[0] = f"{int(_m)}/{int(_d)}/{_y}"
        self.rows.append(row)


def _gs_store_with(ws):
    store = GoogleSheetsPerfStore()
    store._ws = lambda: ws          # 繞過真 gspread
    return store


def test_gs_append_then_load():
    ws = _FakeWS([_HEADERS])
    store = _gs_store_with(ws)
    store.append_snapshot(_snap("2026-08-10", cagr_pct=10.0))
    store.append_snapshot(_snap("2026-08-11", cagr_pct=11.0))
    got = store.load_snapshots()
    assert [s.date for s in got] == ["2026-08-10", "2026-08-11"]
    assert got[1].cagr_pct == 11.0


def test_gs_same_day_updates_in_place():
    ws = _FakeWS([_HEADERS])
    store = _gs_store_with(ws)
    store.append_snapshot(_snap("2026-08-11", cagr_pct=10.0))
    store.append_snapshot(_snap("2026-08-11", cagr_pct=99.0))   # 同日 → update 既有列
    got = store.load_snapshots()
    assert len(got) == 1 and got[0].cagr_pct == 99.0
    assert any(u for u in ws.updates if u[0].startswith("A2"))   # 走了 update 而非 append


def test_gs_append_keeps_iso_date_literal_raw():
    """稽核 FINDING 1 回歸:append 必須走 RAW,主鍵 date 不得被 USER_ENTERED 轉成顯示字串,
    否則跨 session 同日會比對不到 → 重複列。_FakeWS 已模擬 USER_ENTERED 的日期強轉。"""
    ws = _FakeWS([_HEADERS])
    _gs_store_with(ws).append_snapshot(_snap("2026-08-11"))
    assert ws.rows[-1][0] == "2026-08-11"                        # 字面 ISO(非 "8/11/2026")
