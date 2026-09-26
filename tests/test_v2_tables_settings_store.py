# -*- coding: utf-8 -*-
"""services/v2_tables/settings_store.py 的單元測試（fast lane；假 gspread ＋ 替身 L1 取數）。

走完整條：`run_market_indicator_fetch` → L1 寫 `fetch_log_open` → 真的
`build_market_indicator_table(sink=...)`（L1 取數以替身注入）→ sink 經 L1 寫
`market_indicator` 與 `fetch_log`。遮蔽用真的 `masking.mask_message`。
"""

from __future__ import annotations

import secrets as _secrets

import pandas as pd
import pytest

from _fake_settings_sheet import FakeClient, FakeSpreadsheet, FakeWorksheet
from infra import gspread_retry as GR
from infra import source_backoff as SB
from repositories import settings_sheet_repository as R
from services.v2_tables import market_indicator as mi
from services.v2_tables import settings_store as S
from services.v2_tables.masking import MASK

SECRET = "k" + _secrets.token_hex(12)
MI_HEAD = [n for n, _k, _nl in R.MARKET_INDICATOR_SPEC]


@pytest.fixture
def book(monkeypatch):
    fake = FakeSpreadsheet()
    cfg = {"SETTINGS_SHEET_ID": "sheet-under-test",
           "google_service_account": {"client_email": "sa@example.iam.gserviceaccount.com"}}
    monkeypatch.setattr(R, "get_secret", lambda key, default=None: cfg.get(key, default))
    monkeypatch.setattr(R, "_make_client", lambda creds: FakeClient(fake))
    monkeypatch.setattr(GR.time, "sleep", lambda _s: None)
    fake.cfg = cfg
    R.clear_cache()
    SB.reset_all()
    yield fake
    R.clear_cache()
    SB.reset_all()


def _vix(values, dates, fetched_at="2026-09-25T06:00:00.123456+00:00"):
    s = pd.Series(values, index=pd.to_datetime(dates), dtype=float, name="^VIX")
    s.attrs["fetched_at"] = fetched_at
    return s


def _stub(monkeypatch, series=None, error=None):
    monkeypatch.setattr(mi, "fetch_yf_close_with_error", lambda ticker, *a, **k: (series, error))


def test_成功_寫開始紀錄_寫列_寫ok結束紀錄(book, monkeypatch):
    _stub(monkeypatch, _vix([17.0, 18.5], ["2026-09-22", "2026-09-23"]))
    out = S.run_market_indicator_fetch([SECRET])
    assert len(out["table"]["rows"]) == 2
    p = out["persist"]
    assert p["ok"] is True and p["stage"] == "done" and p["appended"] == 2
    assert len(book.data("fetch_log_open")) == 2
    assert [r[0] for r in book.data("market_indicator")[1:]] == ["vol_index", "vol_index"]
    log = book.data("fetch_log")[1]
    assert log[0] == p["log_id"] and log[4:] == ["ok", "2", ""]
    # 讀回：兩列、`44` 形狀
    rows = S.load_market_indicator([SECRET])["rows"]
    assert [(r["obs_date"], r["value_num"]) for r in rows] == [("2026-09-22", 17.0), ("2026-09-23", 18.5)]
    assert S.load_fetch_log([SECRET])["rows"][0]["outcome"] == "ok"


def test_再取一次_不重複寫同一筆(book, monkeypatch):
    _stub(monkeypatch, _vix([17.0], ["2026-09-22"]))
    S.run_market_indicator_fetch([SECRET])
    out = S.run_market_indicator_fetch([SECRET])
    assert out["persist"]["appended"] == 0 and out["persist"]["already_present"] == 1
    assert len(book.data("market_indicator")) == 2
    assert [r[4] for r in book.data("fetch_log")[1:]] == ["ok", "ok"]


def test_來源失敗_failed_訊息遮蔽後與畫面用的字串相同(book, monkeypatch):
    raw = f"HTTPError: 401 for url https://example.invalid/q?apikey={SECRET}"
    _stub(monkeypatch, None, raw)
    out = S.run_market_indicator_fetch([SECRET])
    assert out["table"]["errors"]["vol_index"] == raw          # 表本身不遮（L2 轉換層原文）
    shown = out["persist"]["masked_errors"]["vol_index"]
    assert SECRET not in shown and MASK in shown
    log = book.data("fetch_log")[1]
    assert log[4] == "failed" and log[5] == ""
    assert log[6] == f"vol_index: {shown}"                    # fetch_log 與畫面同一份遮蔽後字串
    assert SECRET not in "".join(sum(book.data("fetch_log"), []))
    assert S.load_fetch_log([SECRET])["rows"][0]["message"] == log[6]


def test_沒設試算表ID_照常取數_不寫任何東西(book, monkeypatch):
    book.cfg.pop("SETTINGS_SHEET_ID")
    _stub(monkeypatch, _vix([17.0], ["2026-09-22"]))
    out = S.run_market_indicator_fetch([SECRET])
    assert len(out["table"]["rows"]) == 1
    p = out["persist"]
    assert p["ok"] is False and p["stage"] == "fetch_log_open" and p["error_code"] == "not_configured"
    assert book.calls == []


def test_主鍵矛盾_整批不寫_記failed(book, monkeypatch):
    book.tabs["market_indicator"] = FakeWorksheet(book, "market_indicator", [
        MI_HEAD, ["vol_index", "2026-09-22", "2026-09-22", "16", "index", "市場指標", "FALSE",
                  "2026-09-24T06:00:00Z"]])
    _stub(monkeypatch, _vix([17.0, 18.5], ["2026-09-22", "2026-09-23"]))
    out = S.run_market_indicator_fetch([SECRET])
    p = out["persist"]
    assert p["appended"] == 0 and len(p["conflicts"]) == 1
    assert len(book.data("market_indicator")) == 2
    log = book.data("fetch_log")[1]
    assert log[4] == "failed" and "主鍵矛盾" in log[6] and "2026-09-22" in log[6]


def test_寫表失敗_取數結果照常回傳_不遞迴寫紀錄(book, monkeypatch):
    _stub(monkeypatch, _vix([17.0], ["2026-09-22"]))
    book.fail_next("append_rows",
                   Exception(f"APIError: [429]: Quota exceeded key={SECRET}"),
                   title="market_indicator")
    out = S.run_market_indicator_fetch([SECRET])
    assert len(out["table"]["rows"]) == 1
    p = out["persist"]
    assert p["ok"] is False
    assert SECRET not in (p["message"] or "") and MASK in p["message"]
    # 429 記在憑證鍵 → 接著寫 fetch_log 被冷卻擋下（不重打、不遞迴），fetch_log 沒有列
    assert p["stage"] == "fetch_log" and p["error_code"] == "cooling"
    assert "fetch_log" not in book.tabs or len(book.data("fetch_log")) <= 1


def test_程式錯誤不被吞(book, monkeypatch):
    def broken_build(*, sink):
        sink({"rows": [{"indicator_key": "vol_index"}], "errors": {}})
        return {}
    with pytest.raises(ValueError):
        S.run_market_indicator_fetch([SECRET], build=broken_build)


def test_存檔與讀設定經L2遮蔽(book, monkeypatch):
    S.save_user_setting("mkt_window_days", "90", "int", [SECRET])
    assert S.load_user_settings([SECRET])["rows"]["mkt_window_days"]["setting_value"] == "90"
    book.fail_next("open_by_key", Exception(f"APIError: [429]: Quota exceeded {SECRET}"))
    R.clear_cache()
    with pytest.raises(S.SettingsSheetError) as err:
        S.load_user_settings([SECRET])
    assert SECRET not in str(err.value) and MASK in str(err.value)
