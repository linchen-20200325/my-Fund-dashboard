"""test_nav_history_store.py — v18.288 NAV 歷史 CSV 匯入/匯出/增量"""
from __future__ import annotations


import pandas as pd
import pytest


@pytest.fixture(autouse=True)
def _isolate_cache(tmp_path, monkeypatch):
    """每 test 換 tmp_path 不污染 cache/nav_history/。"""
    from services import nav_history_store
    monkeypatch.setattr(nav_history_store, "_CACHE_DIR", tmp_path / "nav_history")
    yield


# ─── parse 各種日期格式 ───────────────────────────
def test_parse_western_date_slash():
    from services.nav_history_store import _parse_roc_or_western_date
    assert _parse_roc_or_western_date("2024/03/15") == pd.Timestamp("2024-03-15")


def test_parse_western_date_iso():
    from services.nav_history_store import _parse_roc_or_western_date
    assert _parse_roc_or_western_date("2024-03-15") == pd.Timestamp("2024-03-15")


def test_parse_roc_date():
    """民國 113/03/15 → 2024-03-15。"""
    from services.nav_history_store import _parse_roc_or_western_date
    assert _parse_roc_or_western_date("113/03/15") == pd.Timestamp("2024-03-15")


def test_parse_invalid_returns_none():
    from services.nav_history_store import _parse_roc_or_western_date
    assert _parse_roc_or_western_date("") is None
    assert _parse_roc_or_western_date("not a date") is None


# ─── column detection ────────────────────────────
def test_detect_columns_english():
    from services.nav_history_store import _detect_columns
    df = pd.DataFrame({"date": ["2024-01-01"], "nav": [10.0]})
    dc, nc = _detect_columns(df)
    assert dc == "date" and nc == "nav"


def test_detect_columns_chinese():
    from services.nav_history_store import _detect_columns
    df = pd.DataFrame({"日期": ["2024-01-01"], "淨值": [10.0]})
    dc, nc = _detect_columns(df)
    assert dc == "日期" and nc == "淨值"


def test_detect_columns_fallback_to_first_two():
    from services.nav_history_store import _detect_columns
    df = pd.DataFrame({"foo": ["2024-01-01"], "bar": [10.0]})
    dc, nc = _detect_columns(df)
    assert dc == "foo" and nc == "bar"


# ─── import_nav_csv 主流程 ────────────────────────
def test_import_fresh_csv():
    """空 cache 匯入 → 全部算新增。"""
    from services.nav_history_store import get_cache_status, import_nav_csv
    csv = b"date,nav\n2024-01-01,10.5\n2024-01-02,10.6\n2024-01-03,10.7\n"
    r = import_nav_csv("TESTFUND", csv)
    assert r["errors"] == []
    assert r["imported"] == 3
    assert r["merged"] == 0
    assert r["total"] == 3
    status = get_cache_status("TESTFUND")
    assert status["count"] == 3
    assert status["date_min"] == "2024-01-01"
    assert status["date_max"] == "2024-01-03"


def test_import_merges_with_existing():
    """已有 cache → 重疊資料算 merge，新日期算 imported。"""
    from services.nav_history_store import import_nav_csv
    csv1 = b"date,nav\n2024-01-01,10.5\n2024-01-02,10.6\n"
    import_nav_csv("MERGE01", csv1)
    csv2 = b"date,nav\n2024-01-02,10.65\n2024-01-03,10.7\n"
    r = import_nav_csv("MERGE01", csv2)
    assert r["total"] == 3  # 2024-01-01/02/03
    assert r["imported"] == 1  # 只 2024-01-03 是新的
    assert r["merged"] == 1  # 2024-01-02 重疊


def test_import_roc_date_csv():
    """民國年 CSV 應正確 parse 成西元。"""
    from services.nav_history_store import import_nav_csv
    csv = b"date,nav\n113/01/01,10.5\n113/01/02,10.6\n"
    r = import_nav_csv("ROCFUND", csv)
    assert r["errors"] == []
    assert r["imported"] == 2
    assert r["date_min"] == "2024-01-01"


def test_import_chinese_column_names_csv():
    from services.nav_history_store import import_nav_csv
    csv = "日期,淨值\n2024-01-01,10.5\n2024-01-02,10.6\n".encode("utf-8-sig")
    r = import_nav_csv("ZHFUND", csv)
    assert r["errors"] == []
    assert r["imported"] == 2


def test_import_big5_encoding():
    """Big5 編碼 CSV（MoneyDJ 下載常見）應能讀。"""
    from services.nav_history_store import import_nav_csv
    csv = "日期,淨值\n2024/03/15,10.5\n".encode("big5")
    r = import_nav_csv("BIG5FUND", csv)
    assert r["errors"] == []
    assert r["imported"] == 1


def test_import_negative_nav_skipped():
    from services.nav_history_store import import_nav_csv
    csv = b"date,nav\n2024-01-01,10.5\n2024-01-02,-5.0\n2024-01-03,10.7\n"
    r = import_nav_csv("NEGFUND", csv)
    assert r["imported"] == 2  # 負值跳過


def test_import_empty_csv_returns_error():
    from services.nav_history_store import import_nav_csv
    r = import_nav_csv("EMPTY", b"")
    assert r["errors"]


def test_import_empty_code_returns_error():
    from services.nav_history_store import import_nav_csv
    r = import_nav_csv("", b"date,nav\n2024-01-01,10.0\n")
    assert r["errors"]


# ─── export ───────────────────────────────────────
def test_export_returns_csv_with_bom():
    from services.nav_history_store import export_nav_csv, import_nav_csv
    csv_in = b"date,nav\n2024-01-01,10.5\n"
    import_nav_csv("EXPORT01", csv_in)
    out = export_nav_csv("EXPORT01")
    assert out.startswith(b"\xef\xbb\xbf")  # utf-8-sig BOM
    assert b"2024-01-01" in out
    assert b"10.5" in out


def test_export_empty_cache_returns_empty_bytes():
    from services.nav_history_store import export_nav_csv
    assert export_nav_csv("NEVERSAVED") == b""


# ─── get_cache_status ─────────────────────────────
def test_status_when_empty():
    from services.nav_history_store import get_cache_status
    s = get_cache_status("NONE")
    assert s["exists"] is False
    assert s["count"] == 0


def test_status_when_populated():
    from services.nav_history_store import get_cache_status, import_nav_csv
    csv = b"date,nav\n2023-01-01,10.0\n2024-01-01,11.0\n"
    import_nav_csv("STATUS01", csv)
    s = get_cache_status("STATUS01")
    assert s["exists"] is True
    assert s["count"] == 2
    assert s["years_covered"] > 0.9


# ─── clear_cache ──────────────────────────────────
def test_clear_cache_removes_file():
    from services.nav_history_store import clear_cache, get_cache_status, import_nav_csv
    import_nav_csv("CLEAR01", b"date,nav\n2024-01-01,10.0\n")
    assert get_cache_status("CLEAR01")["exists"]
    assert clear_cache("CLEAR01") is True
    assert get_cache_status("CLEAR01")["exists"] is False


def test_clear_safe_when_no_file():
    from services.nav_history_store import clear_cache
    assert clear_cache("NEVERSAVED") is False
