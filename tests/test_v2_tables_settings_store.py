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
    assert p["log_message"] is None                             # ok：message 為空
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
    assert out["persist"]["log_message"] == log[6]           # persist 與 fetch_log.message 逐字相同
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


def test_主鍵矛盾_只擋那筆_其餘照寫_記failed含筆數與鍵(book, monkeypatch):
    book.tabs["market_indicator"] = FakeWorksheet(book, "market_indicator", [
        MI_HEAD, ["vol_index", "2026-09-22", "2026-09-22", "16", "index", "市場指標", "FALSE",
                  "2026-09-24T06:00:00Z"]])
    _stub(monkeypatch, _vix([17.0, 18.5], ["2026-09-22", "2026-09-23"]))
    out = S.run_market_indicator_fetch([SECRET])
    p = out["persist"]
    assert p["appended"] == 1 and len(p["conflicts"]) == 1
    assert [r[1] for r in book.data("market_indicator")[1:]] == ["2026-09-22", "2026-09-23"]
    log = book.data("fetch_log")[1]
    assert log[4] == "failed" and log[5] == ""
    assert "主鍵矛盾 1 筆" in log[6] and "(vol_index, 2026-09-22, 2026-09-22)" in log[6]


def test_row_count是取回的列數_過濾前(book, monkeypatch):
    # 三列取回；最後一列觀測日不早於取得日（未收盤）被略過 → rows 只有 2，row_count 仍是 3
    _stub(monkeypatch, _vix([17.0, 18.5, 19.0], ["2026-09-22", "2026-09-23", "2026-09-25"]))
    out = S.run_market_indicator_fetch([SECRET])
    assert len(out["table"]["rows"]) == 2 and out["table"]["fetched"] == {"vol_index": 3}
    assert book.data("fetch_log")[1][4:] == ["ok", "3", ""]


def test_取回有列但全部被丟棄_記failed並寫原因(book, monkeypatch):
    s = _vix([17.0, 18.5], ["2026-09-22", "2026-09-23"])
    del s.attrs["fetched_at"]
    _stub(monkeypatch, s)
    out = S.run_market_indicator_fetch([SECRET])
    assert out["table"]["rows"] == []
    log = book.data("fetch_log")[1]
    assert log[4] == "failed" and log[5] == ""
    assert "vol_index: 取回 2 列，全部未寫入" in log[6] and "fetched_at" in log[6]


def test_取數回空且L1沒給原因_記ok_row_count為0(book, monkeypatch):
    _stub(monkeypatch, _vix([], []))
    out = S.run_market_indicator_fetch([SECRET])
    assert out["table"]["errors"] == {"vol_index": mi.EMPTY_WITHOUT_REASON}
    assert book.data("fetch_log")[1][4:] == ["ok", "0", ""]
    assert out["persist"]["ok"] is True
    # 回修第 3 輪 6：回空與真錯誤分開列；真錯誤那一份就是 fetch_log.message 的字串
    assert out["persist"]["empty"] == {"vol_index": mi.EMPTY_WITHOUT_REASON}
    assert out["persist"]["masked_errors"] == {}


def test_取數回空但L1有錯誤原文_記failed(book, monkeypatch):
    _stub(monkeypatch, None, "HTTPError: 500 upstream")
    out = S.run_market_indicator_fetch([SECRET])
    assert out["persist"]["empty"] == {}
    assert out["persist"]["masked_errors"] == {"vol_index": "HTTPError: 500 upstream"}
    log = book.data("fetch_log")[1]
    assert log[4] == "failed" and log[6] == "vol_index: HTTPError: 500 upstream"
    shown = "\n".join(f"{k}: {v}" for k, v in out["persist"]["masked_errors"].items())
    assert shown == log[6]              # 畫面與 fetch_log 同一份字串


def test_masker拒收字串():
    with pytest.raises(TypeError):
        S.masker(SECRET)
    assert S.masker([SECRET])(f"a{SECRET}b") == f"a{MASK}b"


def test_SETTINGS_SHEET_ID歸在要遮():
    from services.v2_tables import masking
    sheet_id = "1" + _secrets.token_hex(20)
    values = masking.secret_values([{"SETTINGS_SHEET_ID": sheet_id}])
    assert values == [sheet_id]
    assert masking.mask_message(f"404 {sheet_id} not found", values) == f"404 {MASK} not found"
    assert "SETTINGS_SHEET_ID" not in masking.NOT_MASKED_KEYS


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
    # fetch_log 沒寫成，但本來要寫的那一份字串照樣交出來（回修第 4 輪 3）
    lm = p["log_message"]
    assert lm.startswith("market_indicator 寫入失敗：") and SECRET not in lm and MASK in lm


def test_market_indicator標頭不符_fetch_log照常寫failed且附原因(book, monkeypatch):
    """第 6 輪：標頭不符不是上游失敗、不登記冷卻 → fetch_log 不會被冷卻擋下（紅隊重現情境）。"""
    book.tabs["market_indicator"] = FakeWorksheet(book, "market_indicator", [["wrong", "header"]])
    _stub(monkeypatch, _vix([17.0], ["2026-09-22"]))
    out = S.run_market_indicator_fetch([SECRET])
    p = out["persist"]
    assert p["ok"] is False and p["stage"] == "market_indicator" and p["error_code"] == "header_mismatch"
    assert book.data("market_indicator") == [["wrong", "header"]]           # 不改寫、不追加
    log = book.data("fetch_log")[1]
    assert log[4] == "failed" and log[5] == ""
    assert log[6].startswith("market_indicator 寫入失敗：標頭與規格不符")
    assert log[6] == p["log_message"]
    assert SB.get_backoff_state() == []


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
