"""test_fund_history.py — v18.272 曾經查過的基金清單單元測試"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest


@pytest.fixture(autouse=True)
def _isolate_cache(tmp_path, monkeypatch):
    """每個 test 用 tmp_path 取代 cache/fund_history.json，避免污染。"""
    from services import fund_history
    fake = tmp_path / "fund_history.json"
    monkeypatch.setattr(fund_history, "_HIST_FILE", fake)
    monkeypatch.setattr(fund_history, "_CACHE_DIR", tmp_path)
    yield


def test_record_single_fund_creates_entry():
    from services.fund_history import get_history_df, record_fund
    record_fund("ACCP138", "聯博全球高收益基金", "Tab2")
    df = get_history_df()
    assert len(df) == 1
    assert df.iloc[0]["代號"] == "ACCP138"
    assert df.iloc[0]["名稱"] == "聯博全球高收益基金"
    assert df.iloc[0]["查詢次數"] == 1
    assert "Tab2" in df.iloc[0]["來源"]


def test_record_duplicate_increments_count_and_updates_last_seen():
    from services.fund_history import get_history_df, record_fund
    record_fund("ACCP138", "聯博", "Tab2")
    record_fund("ACCP138", "聯博", "Tab2")
    record_fund("ACCP138", "聯博", "Tab3")
    df = get_history_df()
    assert len(df) == 1
    assert df.iloc[0]["查詢次數"] == 3
    assert "Tab2" in df.iloc[0]["來源"] and "Tab3" in df.iloc[0]["來源"]


def test_record_normalizes_code_to_upper_and_strip():
    from services.fund_history import get_history_df, record_fund
    record_fund("  accp138  ", "test")
    record_fund("ACCP138", "test")  # 應視為同一檔
    df = get_history_df()
    assert len(df) == 1
    assert df.iloc[0]["代號"] == "ACCP138"
    assert df.iloc[0]["查詢次數"] == 2


def test_record_empty_code_is_noop():
    from services.fund_history import get_history_df, record_fund
    record_fund("", "test")
    record_fund(None, "test")  # type: ignore
    record_fund("   ", "test")
    df = get_history_df()
    assert df.empty


def test_name_preserved_when_subsequent_record_has_empty_name():
    """已有好名稱時，後續抓不到名稱不該覆蓋好名稱。"""
    from services.fund_history import get_history_df, record_fund
    record_fund("ACCP138", "聯博全球高收益基金", "Tab2")
    record_fund("ACCP138", "", "Tab3")  # 名稱抓不到
    df = get_history_df()
    assert df.iloc[0]["名稱"] == "聯博全球高收益基金"


def test_get_history_df_sorts_by_last_seen_desc():
    from services.fund_history import get_history_df, record_fund
    import time
    record_fund("FUND_A", "A 基金")
    time.sleep(1.0)  # 確保時間戳不同
    record_fund("FUND_B", "B 基金")
    df = get_history_df()
    assert df.iloc[0]["代號"] == "FUND_B"  # 最近查的在最上
    assert df.iloc[1]["代號"] == "FUND_A"


def test_empty_history_returns_df_with_6_columns():
    from services.fund_history import get_history_df
    df = get_history_df()
    assert df.empty
    assert list(df.columns) == ["代號", "名稱", "來源", "查詢次數", "首次查詢", "最近查詢"]


def test_clear_history_removes_file():
    from services.fund_history import clear_history, get_history_df, record_fund
    record_fund("ACCP138", "聯博")
    assert not get_history_df().empty
    clear_history()
    assert get_history_df().empty


def test_clear_history_safe_when_no_file():
    from services.fund_history import clear_history
    clear_history()  # 沒檔案也不該 raise


def test_history_size_matches_unique_count():
    from services.fund_history import history_size, record_fund
    record_fund("ACCP138", "聯博")
    record_fund("ACCP138", "聯博")  # 重複，不增加 size
    record_fund("LU0123456", "歐元基金")
    assert history_size() == 2


def test_jsonfile_actually_persists(tmp_path):
    """確認真的寫到磁碟（讀回 JSON 驗證內容）。"""
    from services import fund_history
    fund_history.record_fund("ACCP138", "聯博", "Tab2")
    data = json.loads(fund_history._HIST_FILE.read_text(encoding="utf-8"))
    assert "ACCP138" in data
    assert data["ACCP138"]["name"] == "聯博"
    assert data["ACCP138"]["sources"] == ["Tab2"]


def test_broken_json_returns_empty(monkeypatch, tmp_path):
    """JSON 檔損毀時不該 crash，回空 dict。"""
    from services import fund_history
    fund_history._HIST_FILE.parent.mkdir(parents=True, exist_ok=True)
    fund_history._HIST_FILE.write_text("not valid json {{{", encoding="utf-8")
    df = fund_history.get_history_df()
    assert df.empty
