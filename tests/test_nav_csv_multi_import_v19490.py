"""v19.490:免代號多檔上傳 —— 代號讀自 CSV 第一欄,一個 CSV 可含多檔自動分檔。

user 2026-08-19「移除基金代號欄,代號由 CSV 帶入」。新增 import_nav_csv_multi:
偵測 code/date/nav 三欄 → 依 code 分組 → 逐檔併進各自 cache;回 points 供雲端同步。
"""
import pathlib

import pytest

import services.nav_history_store as ST


@pytest.fixture(autouse=True)
def _tmp_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(ST, "_CACHE_DIR", tmp_path / "nav_history")


# ── 多檔一次匯入 ───────────────────────────────────────────────────────
def test_multi_import_splits_by_code():
    csv = "\n".join([
        "ACDD19,2020/1/2,46.58", "ACDD19,2020/1/3,46.32",
        "ACTI71,2020/1/2,11.10", "ACTI71,2020/1/3,11.25", "ACTI71,2020/1/6,11.40",
        "TLZF9,2021/5/4,9.87",
    ]).encode("utf-8-sig")
    r = ST.import_nav_csv_multi(csv)
    assert r["errors"] == []
    assert r["codes"] == ["ACDD19", "ACTI71", "TLZF9"]
    assert r["results"]["ACDD19"]["total"] == 2
    assert r["results"]["ACTI71"]["total"] == 3
    assert r["results"]["TLZF9"]["total"] == 1
    # 各檔進各自 cache(load_series 讀得回)
    assert len(ST._load_cache_series("ACTI71")) == 3


def test_multi_import_points_carry_code_for_gs_sync():
    csv = b"ACDD19,2020/1/2,46.58\nACTI71,2020/1/3,11.25\n"
    r = ST.import_nav_csv_multi(csv)
    assert len(r["points"]) == 2
    assert {"code": "ACDD19", "nav": 46.58, "nav_date": "2020-01-02"} in r["points"]


def test_single_fund_with_code_column():
    csv = b"ACDD19,2020/1/2,46.58\nACDD19,2020/1/3,46.32\nACDD19,2020/1/6,45.81\n"
    r = ST.import_nav_csv_multi(csv)
    assert r["codes"] == ["ACDD19"] and r["results"]["ACDD19"]["total"] == 3


def test_list_cache_codes_reflects_imports():
    ST.import_nav_csv_multi(b"AAA,2020/1/2,10.0\nBBB,2020/1/2,20.0\n")
    assert ST.list_cache_codes() == ["AAA", "BBB"]


# ── 代號欄偵測 ─────────────────────────────────────────────────────────
def test_detect_code_column_3col():
    from services.nav_history_store import _detect_code_column, _read_csv_bytes
    df = _read_csv_bytes(b"ACDD19,2020/1/2,46.58\nACDD19,2020/1/3,46.32\n")
    assert _detect_code_column(df, 1, 2) == 0   # col0 = 代號


def test_detect_code_column_skips_timestamp_in_6col():
    """6 欄 GS 匯出(code|date|nav|name|source|fetched_at):代號=col0,不可挑到時間戳。"""
    from services.nav_history_store import _detect_code_column, _read_csv_bytes
    line = ("ACDD19,2020/1/2,46.58,安聯台灣智慧,backfill,2026-08-19T00:30:59+00:00\n"
            "ACDD19,2020/1/3,46.32,安聯台灣智慧,backfill,2026-08-19T00:30:59+00:00\n")
    df = _read_csv_bytes(line.encode("utf-8-sig"))
    assert _detect_code_column(df, 1, 2) == 0


# ── §1 誠實報錯 ────────────────────────────────────────────────────────
def test_no_code_column_errors_loud():
    r = ST.import_nav_csv_multi(b"date,nav\n2020/1/2,46.58\n2020/1/3,46.32\n")
    assert r["errors"] and r["codes"] == []


def test_empty_csv_errors():
    assert ST.import_nav_csv_multi(b"")["errors"]


# ── 併入去重(重複上傳不重複)────────────────────────────────────────────
def test_reimport_dedups():
    csv = b"ACDD19,2020/1/2,46.58\nACDD19,2020/1/3,46.32\n"
    ST.import_nav_csv_multi(csv)
    r2 = ST.import_nav_csv_multi(csv)             # 同一份再傳
    assert r2["results"]["ACDD19"]["imported"] == 0   # 全去重,無新增
    assert r2["results"]["ACDD19"]["total"] == 2
