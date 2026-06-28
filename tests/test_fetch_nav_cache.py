"""test_fetch_nav_cache — v18.202：NAV 快取代碼自動彙整（self-heal + Sheet 選用）

只測 _discover_fund_codes / _codes_from_sheet 的「代碼來源彙整」純邏輯
（不打 MoneyDJ/Yahoo 網路；無 SA 憑證時 Sheet 同步略過）。
"""
from __future__ import annotations


def test_codes_from_sheet_no_creds_returns_empty(monkeypatch):
    for k in ("GOOGLE_SERVICE_ACCOUNT_JSON", "GSPREAD_SA_JSON",
              "POLICY_SHEET_ID", "SHEET_ID"):
        monkeypatch.delenv(k, raising=False)
    from scripts.fetch_nav_cache import _codes_from_sheet
    assert _codes_from_sheet() == set()   # 無憑證 → 空集合、不 import gspread


def test_discover_unions_baseline_and_cache_files(monkeypatch, tmp_path):
    import scripts.fetch_nav_cache as fnc
    (tmp_path / "NEWCODE.json").write_text("{}", encoding="utf-8")   # 既有 cache → self-heal
    (tmp_path / "_T7_State.json").write_text("{}", encoding="utf-8")  # _ 開頭系統檔應略過
    monkeypatch.setattr(fnc, "CACHE_DIR", tmp_path)
    for k in ("GOOGLE_SERVICE_ACCOUNT_JSON", "GSPREAD_SA_JSON",
              "POLICY_SHEET_ID", "SHEET_ID"):
        monkeypatch.delenv(k, raising=False)
    codes = fnc._discover_fund_codes()
    assert "NEWCODE" in codes                       # self-heal：cache 檔代碼帶進來
    assert all(not c.startswith("_") for c in codes)  # _ 開頭略過
    assert "TLZF9" in codes                          # 硬編碼 baseline 保留
