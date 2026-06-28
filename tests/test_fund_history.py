"""test_fund_history.py — v18.272 曾經查過的基金清單單元測試"""
from __future__ import annotations

import json

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
    """v18.282 後 df 內含預設常用基金，user 紀錄會排最上面（count>0）。"""
    from services.fund_history import _DEFAULT_FUNDS, get_history_df, record_fund
    record_fund("XYZTEST", "測試基金", "Tab2")
    df = get_history_df()
    # 5 個 preset + 1 個 user = 6
    assert len(df) == len(_DEFAULT_FUNDS) + 1
    # user 紀錄排最上（count>0 in 預設前）
    assert df.iloc[0]["代號"] == "XYZTEST"
    assert df.iloc[0]["名稱"] == "測試基金"
    assert df.iloc[0]["查詢次數"] == 1
    assert "Tab2" in df.iloc[0]["來源"]


def test_record_duplicate_increments_count_and_updates_last_seen():
    from services.fund_history import _DEFAULT_FUNDS, get_history_df, record_fund
    record_fund("XYZTEST", "測試", "Tab2")
    record_fund("XYZTEST", "測試", "Tab2")
    record_fund("XYZTEST", "測試", "Tab3")
    df = get_history_df()
    assert len(df) == len(_DEFAULT_FUNDS) + 1
    _row = df[df["代號"] == "XYZTEST"].iloc[0]
    assert _row["查詢次數"] == 3
    assert "Tab2" in _row["來源"] and "Tab3" in _row["來源"]


def test_record_normalizes_code_to_upper_and_strip():
    from services.fund_history import _DEFAULT_FUNDS, get_history_df, record_fund
    record_fund("  xyztest  ", "test")
    record_fund("XYZTEST", "test")  # 應視為同一檔
    df = get_history_df()
    assert len(df) == len(_DEFAULT_FUNDS) + 1
    _row = df[df["代號"] == "XYZTEST"].iloc[0]
    assert _row["查詢次數"] == 2


def test_record_empty_code_is_noop():
    """空 code 不該創 user 紀錄；df 只剩 preset。"""
    from services.fund_history import _DEFAULT_FUNDS, get_history_df, record_fund
    record_fund("", "test")
    record_fund(None, "test")  # type: ignore
    record_fund("   ", "test")
    df = get_history_df()
    # 沒 user 紀錄 → df 只有 preset
    assert len(df) == len(_DEFAULT_FUNDS)
    # 全部 preset 的 count = 0
    assert (df["查詢次數"] == 0).all()


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


def test_empty_history_still_shows_defaults():
    """v18.282 後即使沒 user 紀錄，df 仍含預設常用基金（不會空）。"""
    from services.fund_history import _DEFAULT_FUNDS, get_history_df
    df = get_history_df()
    assert list(df.columns) == ["代號", "名稱", "來源", "查詢次數", "首次查詢", "最近查詢"]
    assert len(df) == len(_DEFAULT_FUNDS)
    # 全部 preset 來源
    for _, r in df.iterrows():
        assert "preset" in r["來源"]


def test_clear_history_keeps_defaults():
    """clear_history 清掉 user JSON 但預設仍在（reboot 不丟）。"""
    from services.fund_history import _DEFAULT_FUNDS, clear_history, get_history_df, record_fund
    record_fund("XYZTEST", "test")
    assert len(get_history_df()) == len(_DEFAULT_FUNDS) + 1
    clear_history()
    df = get_history_df()
    assert len(df) == len(_DEFAULT_FUNDS)  # preset 還在
    assert "XYZTEST" not in df["代號"].values


def test_clear_history_safe_when_no_file():
    from services.fund_history import clear_history
    clear_history()  # 沒檔案也不該 raise




def test_jsonfile_actually_persists(tmp_path):
    """確認真的寫到磁碟（讀回 JSON 驗證內容）。"""
    from services import fund_history
    fund_history.record_fund("ACCP138", "聯博", "Tab2")
    data = json.loads(fund_history._HIST_FILE.read_text(encoding="utf-8"))
    assert "ACCP138" in data
    assert data["ACCP138"]["name"] == "聯博"
    assert data["ACCP138"]["sources"] == ["Tab2"]


def test_broken_json_returns_defaults_only(monkeypatch, tmp_path):
    """JSON 檔損毀時不該 crash；user 紀錄歸 0 但預設仍在。"""
    from services import fund_history
    fund_history._HIST_FILE.parent.mkdir(parents=True, exist_ok=True)
    fund_history._HIST_FILE.write_text("not valid json {{{", encoding="utf-8")
    df = fund_history.get_history_df()
    # 壞 JSON → user 紀錄空 → df 仍含預設
    assert len(df) == len(fund_history._DEFAULT_FUNDS)


# v18.282：預設常用基金 + manual source
def test_default_funds_present_when_empty():
    """無 user 紀錄時 df 應有所有預設基金。"""
    from services.fund_history import _DEFAULT_FUNDS, get_history_df
    df = get_history_df()
    codes = set(df["代號"].values)
    for d in _DEFAULT_FUNDS:
        assert d["code"] in codes, f"預設基金 {d['code']} 應出現"


def test_user_record_overrides_preset_name():
    """user 抓過同 code 時，name 跟 source 走 user 的，但 preset 標記保留。"""
    from services.fund_history import get_history_df, record_fund
    record_fund("ACCP138", "user 自己的全名", "Tab2")
    df = get_history_df()
    _row = df[df["代號"] == "ACCP138"].iloc[0]
    assert _row["名稱"] == "user 自己的全名"
    assert _row["查詢次數"] >= 1
    # sources 聯集 preset + Tab2
    assert "Tab2" in _row["來源"] and "preset" in _row["來源"]


def test_manual_source_record_works():
    """user 在 Tab6 手動新增的 source="manual" 應正常 upsert。"""
    from services.fund_history import _DEFAULT_FUNDS, get_history_df, record_fund
    record_fund("MANUAL01", "手動加的", "manual")
    df = get_history_df()
    assert len(df) == len(_DEFAULT_FUNDS) + 1
    _row = df[df["代號"] == "MANUAL01"].iloc[0]
    assert _row["查詢次數"] == 1
    assert "manual" in _row["來源"]


def test_active_records_sort_above_presets():
    """user 抓過的 (count>0) 排在預設 (count=0) 上方。"""
    from services.fund_history import get_history_df, record_fund
    record_fund("ACTIVEUSER", "user 抓的", "Tab2")
    df = get_history_df()
    # 第一筆應是 user 抓過的
    assert df.iloc[0]["代號"] == "ACTIVEUSER"
    assert df.iloc[0]["查詢次數"] > 0
    # 後面的 preset 全 count=0
    preset_count = (df["查詢次數"] == 0).sum()
    assert preset_count >= 4  # 至少 4 個預設沒被覆蓋過
