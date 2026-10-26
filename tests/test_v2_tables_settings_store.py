# -*- coding: utf-8 -*-
"""services/v2_tables/settings_store.py 的單元測試（fast lane；假 gspread ＋ 替身 L1 取數）。

~~走完整條：`run_market_indicator_fetch` → L1 寫 `fetch_log_open` → 真的 `build_market_indicator_table(sink=...)`
→ sink 經 L1 寫 `market_indicator` 與 `fetch_log`。~~
→ 2026-10-26 客戶裁示第 6 節（有意識的行為變更，不是漏刪；決策者：客戶）：第一階段 Google Sheet 零寫入。
現在走：`run_market_indicator_fetch(runtime=rt)` → 真的 `build_market_indicator_table(sink=...)`（L1 取數以替身注入）
→ sink 把列與取數紀錄記進 `RuntimeFetchStore`（記憶體）。斷言改讀 `rt`（以 L1 的序列化把記憶體列排成與試算表
同形的儲存格列，原有的欄位斷言照用）；`book` 結束時一律斷言**假試算表零寫入**（存檔休眠路徑那一條除外）。
遮蔽用真的 `masking.mask_message`。
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
_FRED_KEYS = ("credit_spread_pct", "term_spread_pct", "policy_rate_pct")
_SPECS_AS_SHIPPED = dict(mi.INDICATOR_SPECS)


def fred_pending_specs():
    """FRED 三鍵改回 pending 的一份規格複本（只給測試用；正式碼不動）。"""
    specs = dict(mi.INDICATOR_SPECS)
    for key in _FRED_KEYS:
        specs[key] = {**specs[key], "phase1": "pending", "pending_reason": "測試：本檔以 VIX 為樣本",
                      "pending_code": mi.PENDING_FRED_RELEASE_DATE}
    return specs


@pytest.fixture(autouse=True)
def _vix_only(monkeypatch):
    """本檔測的是 sink／`fetch_log` 的寫表機制，以 VIX 一鍵為樣本（寫於 FRED 三鍵接上之前）。

    2026-10-13 起 FRED 三鍵在 L2 取數；本檔的呼叫不傳金鑰，那三鍵會成為「未設定 FRED_API_KEY」的取數失敗，
    改變本檔每一條的 outcome —— 那不是本檔要測的東西。故在本檔把 FRED 三鍵改回 pending（只在測試內）。
    FRED 接到這條寫表路徑的測試在本檔末段（`test_FRED接線_*`，那幾條自己把規格換回出貨版）；
    FRED 的轉換見 tests/test_v2_tables_market_indicator_fred.py。
    """
    monkeypatch.setattr(mi, "INDICATOR_SPECS", fred_pending_specs())


@pytest.fixture
def book(monkeypatch):
    fake = FakeSpreadsheet()
    cfg = {"SETTINGS_SHEET_ID": "sheet-under-test",
           "google_service_account": {"client_email": "sa@example.iam.gserviceaccount.com"}}
    monkeypatch.setattr(R, "get_secret", lambda key, default=None: cfg.get(key, default))
    monkeypatch.setattr(R, "_make_client", lambda creds: FakeClient(fake))
    monkeypatch.setattr(GR.time, "sleep", lambda _s: None)
    fake.cfg = cfg
    fake.allow_writes = False
    R.clear_cache()
    SB.reset_all()
    yield fake
    R.clear_cache()
    SB.reset_all()
    if not fake.allow_writes:
        # 2026-10-26 裁示第 6 節：重新取數對 Google Sheet 零寫入（本檔每一條取數測試都量這一件）。
        assert fake.writes() == [], fake.writes()


@pytest.fixture
def rt():
    return S.RuntimeFetchStore()


def _cells(spec, rows):
    """記憶體列 → 與試算表同形的儲存格列（含標頭；用 L1 的序列化），讓既有的逐欄斷言照用。"""
    return [[n for n, _k, _nl in spec]] + [R._serialize(spec, r) for r in rows]


def _logs(rt):
    return _cells(R.FETCH_LOG_SPEC, rt.log_rows)


def _opens(rt):
    return _cells(R.FETCH_LOG_OPEN_SPEC, rt.open_rows)


def _mis(rt):
    return _cells(R.MARKET_INDICATOR_SPEC, rt.indicator_rows)


def _vix(values, dates, fetched_at="2026-09-25T06:00:00.123456+00:00"):
    s = pd.Series(values, index=pd.to_datetime(dates), dtype=float, name="^VIX")
    s.attrs["fetched_at"] = fetched_at
    # 2026-10-13：L1 改帶來源自報的交易所時區（客戶裁示：觀測日以交易所時區為準；缺時區整鍵不寫）。
    # 本檔測的是寫表與取數紀錄，不是取日規則；替身寫 `Etc/UTC`（`exchange_zone` 不收不含 `/` 的 `UTC`），讓日期以世界協調時間午夜表示的既有例子
    # 觀測日不變（取日規則另見 tests/test_v2_tables_market_indicator_exchange_tz.py）。
    s.attrs["exchange_tz"] = "Etc/UTC"
    return s


def _stub(monkeypatch, series=None, error=None):
    monkeypatch.setattr(mi, "fetch_yf_close_with_error", lambda ticker, *a, **k: (series, error))


def test_成功_記開始紀錄_記列_記ok結束紀錄(book, rt, monkeypatch):
    # ~~test_成功_寫開始紀錄_寫列_寫ok結束紀錄（讀 `book.data(...)`）~~ → 2026-10-26 裁示第 6 節：改讀 `rt`，試算表零寫入
    _stub(monkeypatch, _vix([17.0, 18.5], ["2026-09-22", "2026-09-23"]))
    out = S.run_market_indicator_fetch([SECRET], runtime=rt)
    assert out["runtime"] is rt
    assert len(out["table"]["rows"]) == 2
    p = out["persist"]
    assert p["ok"] is True and p["stage"] == "done" and p["appended"] == 2
    assert len(_opens(rt)) == 2
    assert [r[0] for r in _mis(rt)[1:]] == ["vol_index", "vol_index"]
    log = _logs(rt)[1]
    assert log[0] == p["log_id"] and log[4:] == ["ok", "2", ""]
    assert p["log_message"] is None                             # ok：message 為空
    rows = rt.load_market_indicator()["rows"]
    assert [(r["obs_date"], r["value_num"]) for r in rows] == [("2026-09-22", 17.0), ("2026-09-23", 18.5)]
    assert rt.load_fetch_log()["rows"][0]["outcome"] == "ok"
    assert book.calls == []                                     # 連讀都不讀試算表


def test_沒給runtime_自己開一份_結果只在回傳值(book, monkeypatch):
    _stub(monkeypatch, _vix([17.0], ["2026-09-22"]))
    out = S.run_market_indicator_fetch([SECRET])
    assert isinstance(out["runtime"], S.RuntimeFetchStore)
    assert len(out["runtime"].indicator_rows) == 1 and book.calls == []


def test_session_runtime_沒有就放一份_有就沿用():
    state = {}
    first = S.session_runtime(state)
    assert state[S.RUNTIME_STATE_KEY] is first and S.session_runtime(state) is first
    state[S.RUNTIME_STATE_KEY] = "不是 RuntimeFetchStore"
    assert isinstance(S.session_runtime(state), S.RuntimeFetchStore)


def test_再取一次_不重複記同一筆(book, rt, monkeypatch):
    _stub(monkeypatch, _vix([17.0], ["2026-09-22"]))
    S.run_market_indicator_fetch([SECRET], runtime=rt)
    out = S.run_market_indicator_fetch([SECRET], runtime=rt)
    assert out["persist"]["appended"] == 0 and out["persist"]["already_present"] == 1
    assert len(_mis(rt)) == 2
    assert [r[4] for r in _logs(rt)[1:]] == ["ok", "ok"]


def test_來源失敗_failed_訊息遮蔽後與畫面用的字串相同(book, rt, monkeypatch):
    raw = f"HTTPError: 401 for url https://example.invalid/q?apikey={SECRET}"
    _stub(monkeypatch, None, raw)
    out = S.run_market_indicator_fetch([SECRET], runtime=rt)
    assert out["table"]["errors"]["vol_index"] == raw          # 表本身不遮（L2 轉換層原文）
    shown = out["persist"]["masked_errors"]["vol_index"]
    assert SECRET not in shown and MASK in shown
    log = _logs(rt)[1]
    assert log[4] == "failed" and log[5] == ""
    assert log[6] == f"vol_index: {shown}"                    # 取數紀錄與畫面同一份遮蔽後字串
    assert out["persist"]["log_message"] == log[6]           # persist 與 message 逐字相同
    assert SECRET not in "".join(sum(_logs(rt), []))
    assert rt.load_fetch_log()["rows"][0]["message"] == log[6]


def test_沒設試算表ID_照常取數_紀錄照記在本次工作階段(book, rt, monkeypatch):
    # ~~test_沒設試算表ID_照常取數_不寫任何東西（stage＝fetch_log_open、error_code＝not_configured）~~
    # → 2026-10-26 裁示第 6 節：取數紀錄不再依賴試算表，沒設 ID 也照記（只在記憶體）
    book.cfg.pop("SETTINGS_SHEET_ID")
    _stub(monkeypatch, _vix([17.0], ["2026-09-22"]))
    out = S.run_market_indicator_fetch([SECRET], runtime=rt)
    assert len(out["table"]["rows"]) == 1
    p = out["persist"]
    assert p["ok"] is True and p["stage"] == "done" and p["error_code"] is None
    assert _logs(rt)[1][4:] == ["ok", "1", ""]
    assert book.calls == []


def test_主鍵矛盾_只擋那筆_其餘照記_記failed含筆數與鍵(book, rt, monkeypatch):
    # ~~既有列放在試算表~~ → 2026-10-26：比對對象是本次工作階段已記的列（試算表不讀不寫）
    rt.append_market_indicator([{"indicator_key": "vol_index", "obs_date": "2026-09-22",
                                 "release_date": "2026-09-22", "value_num": 16.0, "value_unit": "index",
                                 "source_tier": "市場指標", "is_revised": False,
                                 "fetched_at": "2026-09-24T06:00:00Z"}])
    _stub(monkeypatch, _vix([17.0, 18.5], ["2026-09-22", "2026-09-23"]))
    out = S.run_market_indicator_fetch([SECRET], runtime=rt)
    p = out["persist"]
    assert p["appended"] == 1 and len(p["conflicts"]) == 1
    assert [r[1] for r in _mis(rt)[1:]] == ["2026-09-22", "2026-09-23"]
    assert [float(r[3]) for r in _mis(rt)[1:]] == [16.0, 18.5]     # 矛盾那筆不覆蓋
    log = _logs(rt)[1]
    assert log[4] == "failed" and log[5] == ""
    assert "主鍵矛盾 1 筆" in log[6] and "(vol_index, 2026-09-22, 2026-09-22)" in log[6]


def test_row_count是取回的列數_過濾前(book, rt, monkeypatch):
    # 三列取回；最後一列觀測日不早於取得日（未收盤）被略過 → rows 只有 2，row_count 仍是 3
    _stub(monkeypatch, _vix([17.0, 18.5, 19.0], ["2026-09-22", "2026-09-23", "2026-09-25"]))
    out = S.run_market_indicator_fetch([SECRET], runtime=rt)
    assert len(out["table"]["rows"]) == 2 and out["table"]["fetched"] == {"vol_index": 3}
    assert _logs(rt)[1][4:] == ["ok", "3", ""]


def test_取回有列但全部被丟棄_記failed並寫原因(book, rt, monkeypatch):
    s = _vix([17.0, 18.5], ["2026-09-22", "2026-09-23"])
    del s.attrs["fetched_at"]
    _stub(monkeypatch, s)
    out = S.run_market_indicator_fetch([SECRET], runtime=rt)
    assert out["table"]["rows"] == []
    log = _logs(rt)[1]
    assert log[4] == "failed" and log[5] == ""
    assert "vol_index: 取回 2 列，全部未寫入" in log[6] and "fetched_at" in log[6]


def test_取數回空且L1沒給原因_記ok_row_count為0(book, rt, monkeypatch):
    _stub(monkeypatch, _vix([], []))
    out = S.run_market_indicator_fetch([SECRET], runtime=rt)
    assert out["table"]["errors"] == {"vol_index": mi.EMPTY_WITHOUT_REASON}
    assert _logs(rt)[1][4:] == ["ok", "0", ""]
    assert out["persist"]["ok"] is True
    # 回修第 3 輪 6：回空與真錯誤分開列；真錯誤那一份就是取數紀錄 message 的字串
    assert out["persist"]["empty"] == {"vol_index": mi.EMPTY_WITHOUT_REASON}
    assert out["persist"]["masked_errors"] == {}


def test_取數回空但L1有錯誤原文_記failed(book, rt, monkeypatch):
    _stub(monkeypatch, None, "HTTPError: 500 upstream")
    out = S.run_market_indicator_fetch([SECRET], runtime=rt)
    assert out["persist"]["empty"] == {}
    assert out["persist"]["masked_errors"] == {"vol_index": "HTTPError: 500 upstream"}
    log = _logs(rt)[1]
    assert log[4] == "failed" and log[6] == "vol_index: HTTPError: 500 upstream"
    shown = "\n".join(f"{k}: {v}" for k, v in out["persist"]["masked_errors"].items())
    assert shown == log[6]              # 畫面與取數紀錄同一份字串


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


# ~~test_寫表失敗_取數結果照常回傳_不遞迴寫紀錄／test_market_indicator標頭不符_fetch_log照常寫failed且附原因~~
# → 2026-10-26 裁示第 6 節（有意識的行為變更，不是漏刪）：不再寫表，「寫表失敗」「標頭不符擋下寫入」不可能發生；
#   改守「試算表那邊壞了也碰不到本次取數」：寫入與讀取都不會被呼叫。
def test_試算表寫入會失敗或標頭壞了_重新取數照常完成_不碰試算表(book, rt, monkeypatch):
    from _fake_settings_sheet import FakeWorksheet
    book.tabs["market_indicator"] = FakeWorksheet(book, "market_indicator", [["wrong", "header"]])
    book.fail_next("append_rows", Exception(f"APIError: [429]: Quota exceeded key={SECRET}"),
                   title="market_indicator")
    _stub(monkeypatch, _vix([17.0], ["2026-09-22"]))
    out = S.run_market_indicator_fetch([SECRET], runtime=rt)
    p = out["persist"]
    assert p["ok"] is True and p["stage"] == "done" and p["message"] is None
    assert _logs(rt)[1][4:] == ["ok", "1", ""]
    assert book.data("market_indicator") == [["wrong", "header"]] and book.calls == []
    assert SB.get_backoff_state() == []


def test_程式錯誤不被吞(book, rt, monkeypatch):
    def broken_build(*, sink):
        sink({"rows": [{"indicator_key": "vol_index"}], "errors": {}})
        return {}
    with pytest.raises(ValueError):
        S.run_market_indicator_fetch([SECRET], runtime=rt, build=broken_build)


def test_存檔與讀設定經L2遮蔽(book, monkeypatch):
    book.allow_writes = True   # 本條測的是休眠中的 L2 `save_user_setting`（直接呼叫、不經唯讀短路），不是重新取數
    S.save_user_setting("mkt_window_days", "90", "int", [SECRET])
    assert S.load_user_settings([SECRET])["rows"]["mkt_window_days"]["setting_value"] == "90"
    book.fail_next("open_by_key", Exception(f"APIError: [429]: Quota exceeded {SECRET}"))
    R.clear_cache()
    with pytest.raises(S.SettingsSheetError) as err:
        S.load_user_settings([SECRET])
    assert SECRET not in str(err.value) and MASK in str(err.value)


# ═══════════════════════ 淨值層重新取數（客戶 2026-10-09 裁示 Q1～Q4） ═══════════════════════

from repositories.fund import nav_metrics as NM  # noqa: E402
from services.v2_tables import alo_holdings as AH  # noqa: E402
from services.v2_tables import nav_dividend as ND  # noqa: E402

_A, _B = "ZZNAVTESTA1", "ZZNAVTESTB2"


def _nav(n=2, fetched_at="2026-09-25T06:00:00+00:00"):
    days = pd.date_range("2026-09-10", periods=n, freq="D")
    s = pd.Series([10.0 + i for i in range(n)], index=days, dtype=float)
    s.attrs["fetched_at"] = fetched_at
    return s


def _holdings(monkeypatch, rows):
    monkeypatch.setattr(AH, "load_alo_tables", lambda values: {"holding": rows})


def _stub_nav(monkeypatch, by_code, ccy="USD"):
    _holdings(monkeypatch, [{"fund_code": c, "ccy": ccy} for c in by_code])
    # 2026-10-13：淨值改走 A 鏈，替身換成 `fetch_nav_chain_with_error(chain_code, full_key)`（有意識的更正，不是漏刪）
    monkeypatch.setattr(ND, "fetch_nav_chain_with_error", lambda chain_code, full_key: by_code[chain_code])


def _nav_logs(rt):
    return [r for r in _logs(rt)[1:] if r[1] == "淨值"]


def test_淨值層_全部成功_一筆ok_row_count為取回列數_不寫任何表(book, rt, monkeypatch):
    _stub_nav(monkeypatch, {_A: (_nav(3), None), _B: (_nav(2), None)})
    out = S.refetch_nav([SECRET], runtime=rt)
    p = out["persist"]
    assert p["ok"] is True and p["stage"] == "done" and p["log_message"] is None
    assert len(out["table"]["rows"]) == 5
    logs = _nav_logs(rt)
    assert len(logs) == 1 and logs[0][4:] == ["ok", "5", ""]
    # ~~set(book.tabs) == {"fetch_log", "fetch_log_open"}~~ → 2026-10-26 裁示第 6 節：連取數紀錄分頁都不寫
    assert book.tabs == {} and rt.indicator_rows == []                 # 沒有任何分頁，也沒記市場指標
    assert len(_opens(rt)) == 2                                        # 標頭＋本次一列


def test_淨值層_row_count是過濾前的取回列數(book, rt, monkeypatch):
    s = _nav(3)
    s.iloc[1] = -1.0                                                   # 一列不合理（不大於 0），被略過
    _stub_nav(monkeypatch, {_A: (s, None)})
    out = S.refetch_nav([SECRET], runtime=rt)
    assert len(out["table"]["rows"]) == 2
    assert _nav_logs(rt)[0][4:] == ["ok", "3", ""]


def test_淨值層_一檔失敗_整筆failed_逐檔原文_已遮蔽(book, rt, monkeypatch):
    raw = f"fetch_nav('{_B}') 即時網址與預存檔皆失敗:\nhttps://x.invalid/q?apikey={SECRET} → 取數失敗(kind=cooling)"
    _stub_nav(monkeypatch, {_A: (_nav(2), None), _B: (pd.Series(dtype=float), raw)})
    out = S.refetch_nav([SECRET], runtime=rt)
    p = out["persist"]
    logs = _nav_logs(rt)
    assert len(logs) == 1 and logs[0][4] == "failed" and logs[0][5] == ""
    message = logs[0][6]
    assert message == p["log_message"] == f"{_B}: " + p["masked_errors"][_B]
    assert SECRET not in message and MASK in message and "kind=cooling" in message
    assert SECRET not in repr(p)
    assert out["table"]["errors"][_B] == raw                           # 表本身不遮（L2 轉換層原文）


def test_淨值層_兩檔都失敗_逐行列出(book, rt, monkeypatch):
    _stub_nav(monkeypatch, {_A: (None, "HTTP 503 a"), _B: (None, "HTTP 503 b")})
    S.refetch_nav([SECRET], runtime=rt)
    assert _nav_logs(rt)[0][6] == f"{_A}: HTTP 503 a\n{_B}: HTTP 503 b"


def test_淨值層_整檔扣下_幣別缺_記failed附L2原因(book, rt, monkeypatch):
    _stub_nav(monkeypatch, {_A: (_nav(2), None)}, ccy=None)
    S.refetch_nav([SECRET], runtime=rt)
    log = _nav_logs(rt)[0]
    assert log[4] == "failed" and log[6].startswith(f"{_A}: 來源未自報幣別") and "2 筆全部不寫" in log[6]


def test_淨值層_代碼解析失敗_記failed(book, rt, monkeypatch):
    _holdings(monkeypatch, [{"fund_code": "壞 代碼", "ccy": "USD"}])
    S.refetch_nav([SECRET], runtime=rt)
    log = _nav_logs(rt)[0]
    assert log[4] == "failed" and log[6].startswith("壞 代碼: fund_code 含非 ASCII")


def test_淨值層_L1回空沒給原因_不算失敗_記ok_0列(book, rt, monkeypatch):
    _stub_nav(monkeypatch, {_A: (pd.Series(dtype=float), None)})
    out = S.refetch_nav([SECRET], runtime=rt)
    assert _nav_logs(rt)[0][4:] == ["ok", "0", ""]
    assert out["persist"]["empty"] == {_A: mi.EMPTY_WITHOUT_REASON} and out["persist"]["masked_errors"] == {}


def test_淨值層_持倉讀不到_記failed_原文已遮蔽_不取數(book, rt, monkeypatch):
    def boom(values):
        raise AH.PolicySupplementError(f"讀取失敗 https://x/{SECRET}", code="api")
    monkeypatch.setattr(AH, "load_alo_tables", boom)
    monkeypatch.setattr(ND, "fetch_nav_chain_with_error", lambda *a, **k: pytest.fail("持倉讀不到時不得取數"))
    out = S.refetch_nav([SECRET], runtime=rt)
    log = _nav_logs(rt)[0]
    assert log[4] == "failed" and log[6].startswith("holding: 讀取失敗") and SECRET not in log[6]
    assert out["table"] is None and out["persist"]["log_message"] == log[6]


def test_淨值層_持倉為空_取數回空_記ok_0列(book, rt, monkeypatch):
    _holdings(monkeypatch, [])
    monkeypatch.setattr(ND, "fetch_nav_chain_with_error", lambda *a, **k: pytest.fail("沒有持倉不得取數"))
    out = S.refetch_nav([SECRET], runtime=rt)
    assert _nav_logs(rt)[0][4:] == ["ok", "0", ""]
    assert out["persist"]["empty"] and out["persist"]["masked_errors"] == {}


def test_淨值層_同一檔多張保單_取一次_每列持倉都交出幣別(book, rt, monkeypatch):
    calls = []
    _holdings(monkeypatch, [{"fund_code": _A, "ccy": "USD"}, {"fund_code": _A, "ccy": "USD"}])
    monkeypatch.setattr(ND, "fetch_nav_chain_with_error",
                        lambda key, full_key: (calls.append(key) or (_nav(2), None)))
    S.refetch_nav([SECRET], runtime=rt)
    assert calls == [_A] and _nav_logs(rt)[0][4:] == ["ok", "2", ""]


def test_淨值層_沒設試算表ID_照常取數_紀錄照記在本次工作階段(book, rt, monkeypatch):
    # ~~test_淨值層_沒設試算表ID_照常取數_不寫任何東西（stage＝fetch_log_open、log_message 為 None）~~
    # → 2026-10-26 裁示第 6 節：取數紀錄不再依賴設定試算表，沒設 ID 也照記（只在記憶體）
    book.cfg.pop("SETTINGS_SHEET_ID")
    _stub_nav(monkeypatch, {_A: (None, f"x {SECRET}")})
    out = S.refetch_nav([SECRET], runtime=rt)
    p = out["persist"]
    assert p["stage"] == "done" and p["error_code"] is None and p["log_message"] == f"{_A}: " + p["masked_errors"][_A]
    assert SECRET not in p["masked_errors"][_A] and book.calls == []
    assert _nav_logs(rt)[0][4] == "failed" and out["runtime"] is rt


def test_淨值層_清掉fetch_nav的快取_第二次真的再取_不動冷卻_不呼叫全域清除(book, rt, monkeypatch):
    """走真的 A 鏈 → 真的 `fetch_nav`（L1 日快取）；A 鏈其他來源用 `tests/_a_chain_stub.py` 換成回空的替身，
    `fetch_nav` 只把往外的兩個出口換成替身：即時網址一律失敗、預存檔回一份序列。

    2026-10-13（有意識的更正，不是漏刪）：原本直接呼叫 L1 `fetch_nav`；淨值改走 A 鏈後，`fetch_nav` 是 A 鏈
    legacy 段的最終備援，本條改走整條 A 鏈，守的事不變：清快取、第二次真的再取、不動冷卻、不呼叫全域清除。"""
    import infra.cache as IC
    import repositories.fund.fund_orchestration as FO
    import _a_chain_stub as H
    calls = {"url": 0, "cache_file": 0}

    def fake_url(*a, **k):
        calls["url"] += 1
        return None

    def fake_cache_file(code):
        calls["cache_file"] += 1
        s = _nav(12)
        s.attrs.update(source=f"GitHubActions:cache/nav/{code}.json", cache_updated_at="2026-09-25T06:00:00+00:00")
        return s

    H.install(monkeypatch, {})
    monkeypatch.setattr(FO, "fetch_nav", NM.fetch_nav)                   # A 鏈最終備援用真的（有日快取）
    monkeypatch.setattr(NM, "fetch_url_with_retry", fake_url)
    monkeypatch.setattr(NM, "_src_cache_files", fake_cache_file)
    monkeypatch.setattr(IC, "clear_all_caches", lambda *a, **k: pytest.fail("不得呼叫全域清除"))
    _holdings(monkeypatch, [{"fund_code": _A, "ccy": "USD"}])
    NM.fetch_nav.cache_clear()
    # 負控：不清快取時，同一天第二次呼叫打到快取，不再往外取。
    NM.fetch_nav(_A, "")
    NM.fetch_nav(_A, "")
    assert calls["cache_file"] == 1
    SB.record_failure("some.nav.host", "server_error")
    assert SB.should_skip("some.nav.host")[0] is True
    S.refetch_nav([SECRET], runtime=rt)
    after_first = calls["cache_file"]
    S.refetch_nav([SECRET], runtime=rt)
    # 每次重新取數，A 鏈兩個頁型各走一次 legacy 最終備援：第一次清掉快取後真的再取一次，
    # 同一次的第二個頁型打到剛存進的日快取；第二次重新取數又清掉，再真的取一次。
    assert after_first == 2 and calls["cache_file"] == 3
    assert SB.should_skip("some.nav.host")[0] is True                    # 冷卻原封不動
    logs = _nav_logs(rt)
    assert [r[4:6] for r in logs] == [["failed", ""], ["failed", ""]]
    assert all(r[6].startswith(f"{_A}: ") and "取數失敗" in r[6] for r in logs)
    NM.fetch_nav.cache_clear()


def test_淨值層_重新取數清掉A鏈實際用到的全部快取_每個恰一次(book, rt, monkeypatch):
    cleared = []
    for fn in ND.CHAIN_CACHED_FUNCTIONS:
        monkeypatch.setattr(fn, "cache_clear", lambda _n=fn.__name__: cleared.append(_n))
    _stub_nav(monkeypatch, {_A: (_nav(2), None)})
    S.refetch_nav([SECRET], runtime=rt)
    assert sorted(cleared) == sorted(fn.__name__ for fn in ND.CHAIN_CACHED_FUNCTIONS)
    assert len(cleared) == 6 and len(_nav_logs(rt)) == 1                # 仍只寫一筆 fetch_log


def test_淨值層_重新取數一併清exp自報基本資料快取_失敗記憶_淨值記憶_TDCC空清單_不動冷卻(book, rt, monkeypatch):
    """2026-10-14 C2：走真的三支 L1 把成功快取與失敗記憶填好、真的 exp 淨值記憶填一筆、TDCC 行程內快取放 `[]`，
    重新取數後全部清空；`infra.source_backoff` 的冷卻原封不動。"""
    import infra.proxy as PX
    import repositories.fund.declared_profile as DP
    import repositories.fund.sources as SRC
    from services.v2_tables import exp_nav as EN
    from services.v2_tables import exp_profile as EP

    class _J:
        text = "{}"

        def json(self):
            return {"Data": {"Currency": "USD"}}

    def fake_fetch(url, **k):
        PX._TLS_FAIL.kind = ""
        if "fundclear" in url:
            return _J()
        # ~~MoneyDJ 四個網址全 404 → failed → 進失敗記憶~~ → 2026-10-14 身分判準修訂（有意識的更正，不是漏刪；
        # 決策者 AI 總管；docs/v2/49 第 8 節 (aa)）：全 404 改判 not_found，一樣進失敗記憶（本測試要守的清除行為不變）
        PX._TLS_FAIL.kind = "not_found"
        return None

    monkeypatch.setattr(DP, "fetch_url_with_retry", fake_fetch)
    monkeypatch.setattr(SRC, "_is_domestic_code", lambda code, page_type="": False)
    monkeypatch.setattr(SRC, "_tdcc_cache", {"3-2": [], "3-1": []})
    for fn in EP.DECLARED_CACHED_FUNCTIONS:
        fn.cache_clear()
    EN.clear_memo()
    assert DP.fetch_fundclear_declared_ccy("ZZEXP1")["status"] == "ok"
    assert DP.fetch_moneydj_basic_fields("ZZEXP1")["status"] == "not_found"     # 舊斷言 == "failed"（見上）
    assert DP.fetch_tdcc_listing("ZZEXP1")["status"] == "failed"
    ok_res = {"full_key": "ZZEXP1", "series": _nav(3), "dividends": [], "data_source": "x"}
    EN.load_nav_dividend(
        [{"fund_code": "ZZEXP1", "full_key": "ZZEXP1", "chain_code": "ZZEXP1", "portal": "",
          "declared_ccy": "USD", "declared_ccy_source": "meta:FundClear"}],
        chain_fetch=lambda c, f: (*ND._nav_from_chain(ok_res, "yp010000", c, f), ND._div_from_chain(ok_res, f)))
    # 負控：清之前都有東西
    assert DP.fetch_fundclear_declared_ccy.cache_info()["size"] == 1
    assert len(DP._FAILURE_MEMORY) == 2 and EN._REGISTERED.cache_info()["size"] == 1
    SB.record_failure("some.exp.host", "server_error")
    assert SB.should_skip("some.exp.host")[0] is True

    _stub_nav(monkeypatch, {_A: (_nav(2), None)})
    S.refetch_nav([SECRET], runtime=rt)

    assert DP.fetch_fundclear_declared_ccy.cache_info()["size"] == 0       # 成功快取清空
    assert DP._FAILURE_MEMORY == {}                                         # 失敗記憶清空
    assert EN._REGISTERED.cache_info()["size"] == 0                         # exp 淨值記憶清空
    assert "3-2" not in SRC._tdcc_cache and SRC._tdcc_cache["3-1"] == []    # 只丟 3-2 的 []
    assert SB.should_skip("some.exp.host")[0] is True                       # 冷卻原封不動
    assert len(_nav_logs(rt)) == 1


def test_淨值層_持倉讀不到_exp快取照樣清(book, rt, monkeypatch):
    """2026-10-14 稽核必修 8：清 exp 三支 L1、淨值記憶、TDCC 空清單，不依賴持倉讀取成功。"""
    import repositories.fund.declared_profile as DP
    import repositories.fund.sources as SRC
    from services.v2_tables import exp_nav as EN
    cleared = []
    for fn in (DP.fetch_moneydj_basic_fields, DP.fetch_tdcc_listing, DP.fetch_fundclear_declared_ccy):
        monkeypatch.setattr(fn, "cache_clear", lambda _n=fn.__name__: cleared.append(_n))
    monkeypatch.setattr(SRC, "_tdcc_cache", {"3-2": []})
    EN._MEMO[("佔位",)] = (0.0, EN.KIND_SUCCESS, {})

    def boom(values):
        raise AH.PolicySupplementError("讀取失敗", code="api")
    monkeypatch.setattr(AH, "load_alo_tables", boom)
    monkeypatch.setattr(ND, "fetch_nav_chain_with_error", lambda *a, **k: pytest.fail("持倉讀不到時不得取數"))
    S.refetch_nav([SECRET], runtime=rt)
    assert sorted(cleared) == sorted(["fetch_moneydj_basic_fields", "fetch_tdcc_listing",
                                      "fetch_fundclear_declared_ccy"])
    assert EN._REGISTERED.cache_info()["size"] == 0 and "3-2" not in SRC._tdcc_cache
    assert _nav_logs(rt)[0][4] == "failed"


def test_淨值層_持倉讀不到_A鏈快取也清_其餘行為不變(book, rt, monkeypatch):
    """2026-10-14 稽核 V／W 可選項：「重新取淨值」持倉讀不到時，A 鏈 L1（含 15 分鐘主入口）照樣清，
    否則 exp 記憶清了、下一次 exp 取數仍命中清除前的舊 L1。錯誤訊息、回傳值、fetch_log 筆數照舊
    （對照 `test_淨值層_持倉讀不到_記failed_原文已遮蔽_不取數`）。"""
    cleared = []
    for fn in ND.CHAIN_CACHED_FUNCTIONS:
        monkeypatch.setattr(fn, "cache_clear", lambda _n=fn.__name__: cleared.append(_n))

    def boom(values):
        raise AH.PolicySupplementError(f"讀取失敗 https://x/{SECRET}", code="api")
    monkeypatch.setattr(AH, "load_alo_tables", boom)
    monkeypatch.setattr(ND, "fetch_nav_chain_with_error", lambda *a, **k: pytest.fail("持倉讀不到時不得取數"))
    out = S.refetch_nav([SECRET], runtime=rt)
    assert sorted(cleared) == sorted(fn.__name__ for fn in ND.CHAIN_CACHED_FUNCTIONS) and len(cleared) == 6
    logs = _nav_logs(rt)
    assert len(logs) == 1 and logs[0][4] == "failed"
    assert logs[0][6].startswith("holding: 讀取失敗") and SECRET not in logs[0][6]
    assert out["table"] is None and list(out["persist"]["masked_errors"]) == ["holding"]
    assert out["persist"]["log_message"] == logs[0][6] and out["persist"]["empty"] == {}


def test_淨值層_A鏈快取在讀持倉之前清(book, rt, monkeypatch):
    order = []
    for fn in ND.CHAIN_CACHED_FUNCTIONS:
        monkeypatch.setattr(fn, "cache_clear", lambda _n=fn.__name__: order.append("clear"))
    _stub_nav(monkeypatch, {_A: (_nav(2), None)})
    inner = AH.load_alo_tables

    def spy(values):
        order.append("holding")
        return inner(values)
    monkeypatch.setattr(AH, "load_alo_tables", spy)
    S.refetch_nav([SECRET], runtime=rt)
    assert order == ["clear"] * 6 + ["holding"]
    assert _nav_logs(rt)[0][4:] == ["ok", "2", ""]


def test_淨值層_重新取數不清TDCC非空清單(book, rt, monkeypatch):
    import repositories.fund.sources as SRC
    data = [{"基金代碼": "X1"}]
    monkeypatch.setattr(SRC, "_tdcc_cache", {"3-2": data})
    _stub_nav(monkeypatch, {_A: (_nav(2), None)})
    S.refetch_nav([SECRET], runtime=rt)
    assert SRC._tdcc_cache["3-2"] is data


def test_淨值層_exp清除不在市場指標的重新取數清單():
    import repositories.fund.declared_profile as DP
    names = {getattr(f, "__name__", "") for f in S.refetch_cached_functions()}
    assert not names & {DP.fetch_moneydj_basic_fields.__name__, DP.fetch_tdcc_listing.__name__,
                        DP.fetch_fundclear_declared_ccy.__name__}


def test_淨值層_累積表讀取失敗_記failed_原文已遮蔽_即時部分照交_閘門開啟(book, rt, monkeypatch):
    """2026-10-13 第 6 條：A 鏈讀累積表失敗（含冷卻中不打）→ 照實記失敗，不吞。"""
    monkeypatch.setattr(ND, "NAV_HISTORY_PROVENANCE_VERIFIED", True)   # 閘門開啟的路徑（2026-10-13 起預設關閉）
    s = _nav(3)
    s.attrs[ND.CHAIN_ATTR] = {"page_type": "yp010001", "data_source": "FundClear", "fetched_at_from": "series_attrs"}
    s.attrs[ND.CHAIN_HIST_READ_ERROR_ATTR] = f"nav_history load 失敗:APIError 429 {SECRET}"
    _stub_nav(monkeypatch, {_A: (s, None)})
    out = S.refetch_nav([SECRET], runtime=rt)
    assert len(out["table"]["rows"]) == 3
    log = _nav_logs(rt)[0]
    assert log[4] == "failed" and log[6].startswith(f"{_A}: 累積表讀取失敗：") and "429" in log[6]
    assert SECRET not in log[6] and MASK in log[6]


def test_淨值層_序列全部來自累積表_本次即時失敗_記failed_閘門開啟(book, rt, monkeypatch):
    monkeypatch.setattr(ND, "NAV_HISTORY_PROVENANCE_VERIFIED", True)   # 閘門開啟的路徑（2026-10-13 起預設關閉）
    s = _nav(3)
    days = [d.date().isoformat() for d in s.index]
    s.attrs = {ND.HISTORY_MERGED_ATTR: "+3 pts", ND.HISTORY_DATES_ATTR: days,
               ND.HISTORY_RECORDED_AT_ATTR: {d: "2026-09-20T00:00:00+00:00" for d in days},
               ND.HISTORY_SOURCE_ATTR: "GoogleSheet:nav_history:X",
               ND.CHAIN_FAILURES_ATTR: "[yp010001] FundClear：回傳 0 筆，未達本步採用門檻 20 筆"}
    _stub_nav(monkeypatch, {_A: (s, None)})
    out = S.refetch_nav([SECRET], runtime=rt)
    assert len(out["table"]["rows"]) == 3 and out["table"]["provenance"][_A]["cache_fallback"] is True
    log = _nav_logs(rt)[0]
    assert log[4] == "failed" and "FundClear：回傳 0 筆" in log[6]


def test_淨值層_閘門關閉_累積表讀取失敗不算本次失敗_原文仍在provenance(book, rt, monkeypatch):
    s = _nav(3)
    s.attrs[ND.CHAIN_ATTR] = {"page_type": "yp010001", "data_source": "FundClear", "fetched_at_from": "series_attrs"}
    s.attrs[ND.CHAIN_HIST_READ_ERROR_ATTR] = "nav_history load 失敗:APIError 429"
    _stub_nav(monkeypatch, {_A: (s, None)})
    out = S.refetch_nav([SECRET], runtime=rt)
    assert _nav_logs(rt)[0][4:] == ["ok", "3", ""]
    assert "429" in out["table"]["provenance"][_A]["nav_history"]["read_error"]


def test_淨值層_閘門關閉_序列全部來自累積表_整檔不寫_記failed_附即時失敗原文(book, rt, monkeypatch):
    s = _nav(3)
    days = [d.date().isoformat() for d in s.index]
    s.attrs = {ND.HISTORY_MERGED_ATTR: "+3 pts", ND.HISTORY_DATES_ATTR: days,
               ND.HISTORY_RECORDED_AT_ATTR: {d: "2026-09-20T00:00:00+00:00" for d in days},
               ND.HISTORY_SOURCE_ATTR: "GoogleSheet:nav_history:X",
               ND.CHAIN_FAILURES_ATTR: "[yp010001] FundClear：回傳 0 筆，未達本步採用門檻 20 筆"}
    _stub_nav(monkeypatch, {_A: (s, None)})
    out = S.refetch_nav([SECRET], runtime=rt)
    assert out["table"]["rows"] == []
    log = _nav_logs(rt)[0]
    assert log[4] == "failed" and "FundClear：回傳 0 筆" in log[6] and "出處不可考" in log[6]


def test_淨值層_程式錯誤不被吞(book, rt, monkeypatch):
    _holdings(monkeypatch, [{"fund_code": _A}])                          # 少了 ccy：本檔的呼叫契約被破壞
    # ~~with pytest.raises(KeyError):~~ → 2026-10-09 協作助手複驗必修（狀態更新，不是漏刪）：
    #   例外改包成 `NavRefetchError`（訊息遮蔽、原類別名留在訊息開頭），照樣往上拋、不吞。
    with pytest.raises(S.NavRefetchError, match=r"^KeyError: "):
        S.refetch_nav([SECRET], runtime=rt)
    logs = _nav_logs(rt)
    assert len(logs) == 1 and logs[0][4:6] == ["failed", ""] and logs[0][6].startswith("KeyError: ")


# ── 2026-10-09 協作助手複驗必修：寫表以外的例外 → 先收斂 fetch_log 為 failed，再遮蔽後往上拋 ──

import traceback as _traceback  # noqa: E402


def _spy_close(monkeypatch, *, fail_with=None):
    """包住真的 `RuntimeFetchStore.close_fetch_log`：記下每次呼叫的參數；`fail_with` 給了就改拋它（不記）。
    ~~包住 L1 `close_fetch_log`~~ → 2026-10-26 裁示第 6 節：結束紀錄改記在記憶體，守的收斂行為不變。"""
    calls, real = [], S.RuntimeFetchStore.close_fetch_log

    def spy(self, opened, **kw):
        calls.append(kw)
        if fail_with is not None:
            raise fail_with
        return real(self, opened, **kw)

    monkeypatch.setattr(S.RuntimeFetchStore, "close_fetch_log", spy)
    return calls


def _no_secret_anywhere(exc):
    assert SECRET not in str(exc)
    assert SECRET not in "".join(_traceback.format_exception(exc))
    assert exc.__cause__ is None and exc.__context__ is None


def test_淨值層_build_nav_table拋錯_收斂為failed_訊息遮蔽_拋NavRefetchError(book, rt, monkeypatch):
    _holdings(monkeypatch, [{"fund_code": _A, "ccy": "USD"}])

    def boom(items):
        raise RuntimeError(f"轉換失敗 https://x.invalid/?key={SECRET}")
    monkeypatch.setattr(ND, "build_nav_table", boom)
    calls = _spy_close(monkeypatch)
    with pytest.raises(S.NavRefetchError) as info:
        S.refetch_nav([SECRET], runtime=rt)
    assert len(calls) == 1
    kw = calls[0]
    assert kw["outcome"] == "failed" and kw["row_count"] is None
    assert SECRET not in kw["message"] and MASK in kw["message"] and kw["message"].startswith("RuntimeError: 轉換失敗")
    assert str(info.value) == kw["message"]
    _no_secret_anywhere(info.value)
    assert any(f.name == "boom" for f in _traceback.extract_tb(info.value.__traceback__))   # 堆疊位置保留
    logs = _nav_logs(rt)
    assert len(logs) == 1 and logs[0][4:] == ["failed", "", kw["message"]]


def test_淨值層_resolve_full_keys拋錯_收斂為failed_訊息遮蔽(book, rt, monkeypatch):
    _holdings(monkeypatch, [{"fund_code": _A, "ccy": "USD"}])
    from services.v2_tables import fund_keys as FK

    def boom(codes):
        raise OSError(f"代碼對照表讀不到 {SECRET}")
    monkeypatch.setattr(FK, "resolve_full_keys", boom)
    calls = _spy_close(monkeypatch)
    with pytest.raises(S.NavRefetchError) as info:
        S.refetch_nav([SECRET], runtime=rt)
    assert len(calls) == 1 and calls[0]["outcome"] == "failed" and calls[0]["row_count"] is None
    assert calls[0]["message"].startswith("OSError: 代碼對照表讀不到") and MASK in calls[0]["message"]
    _no_secret_anywhere(info.value)
    assert len(_nav_logs(rt)) == 1


def test_淨值層_例外路徑補記結束列又失敗_兩段原文皆遮蔽後一併拋出(book, rt, monkeypatch):
    _holdings(monkeypatch, [{"fund_code": _A, "ccy": "USD"}])
    monkeypatch.setattr(ND, "build_nav_table", lambda items: (_ for _ in ()).throw(ValueError(f"甲 {SECRET}")))
    # ~~fail_with=R.SettingsSheetError(...)~~ → 2026-10-26：結束紀錄改記在記憶體，不會再有試算表錯誤；改以一般例外守同一條收斂
    calls = _spy_close(monkeypatch, fail_with=RuntimeError(f"寫入失敗 {SECRET}"))
    with pytest.raises(S.NavRefetchError) as info:
        S.refetch_nav([SECRET], runtime=rt)
    text = str(info.value)
    assert len(calls) == 1
    # ~~assert ... and "\n補記取數紀錄失敗：SettingsSheetError: 寫入失敗 " in text~~
    # → 2026-10-09 第二輪小修（狀態更新，不是漏刪）：不新增中文前綴，補記失敗只以換行接上「例外類別: 原文」。
    assert text.startswith("ValueError: 甲 ") and "\nRuntimeError: 寫入失敗 " in text
    assert "補記取數紀錄失敗" not in text
    assert text.count(MASK) == 2
    _no_secret_anywhere(info.value)


def test_淨值層_沒設試算表ID加後續例外_補記failed在本次工作階段_仍拋遮蔽後例外(book, rt, monkeypatch):
    # ~~test_淨值層_open失敗加後續例外_不寫任何紀錄（沒設 ID → 開始紀錄寫不進 → close 零呼叫）~~
    # → 2026-10-26 裁示第 6 節：開始紀錄改記在記憶體、不會因沒設 ID 失敗 ⇒ 照常補記一筆 failed（仍不碰試算表）
    book.cfg.pop("SETTINGS_SHEET_ID")
    _holdings(monkeypatch, [{"fund_code": _A, "ccy": "USD"}])
    monkeypatch.setattr(ND, "build_nav_table", lambda items: (_ for _ in ()).throw(RuntimeError(f"乙 {SECRET}")))
    calls = _spy_close(monkeypatch)
    with pytest.raises(S.NavRefetchError) as info:
        S.refetch_nav([SECRET], runtime=rt)
    assert [c["outcome"] for c in calls] == ["failed"] and book.calls == []
    assert str(info.value).startswith("RuntimeError: 乙 ") and MASK in str(info.value)
    _no_secret_anywhere(info.value)


def test_淨值層_正常成功與正常failed_close恰呼叫一次(book, rt, monkeypatch):
    calls = _spy_close(monkeypatch)
    _stub_nav(monkeypatch, {_A: (_nav(2), None)})
    S.refetch_nav([SECRET], runtime=rt)
    _stub_nav(monkeypatch, {_A: (None, "HTTP 503 a")})
    S.refetch_nav([SECRET], runtime=rt)
    assert [c["outcome"] for c in calls] == ["ok", "failed"]
    assert [r[4] for r in _nav_logs(rt)] == ["ok", "failed"]


# ~~def test_淨值層_正常路徑close拋非SettingsSheetError_只呼叫一次_拋遮蔽後例外~~
# → 2026-10-09 第二輪小修（狀態更新，不是漏刪）：旗標改為「結束列已確定」才設，正常路徑 close 拋
#   SettingsSheetError 以外的例外時要補記一次 failed —— 最多兩次、第二次為 failed。
def test_淨值層_正常路徑close拋非SettingsSheetError_最多兩次_第二次為failed_拋遮蔽後例外(book, rt, monkeypatch):
    _stub_nav(monkeypatch, {_A: (_nav(2), None)})
    calls = _spy_close(monkeypatch, fail_with=TypeError(f"序列化失敗 {SECRET}"))
    with pytest.raises(S.NavRefetchError) as info:
        S.refetch_nav([SECRET], runtime=rt)
    # ~~assert len(calls) == 1 and calls[0]["outcome"] == "ok"~~
    assert [c["outcome"] for c in calls] == ["ok", "failed"]
    assert calls[1]["row_count"] is None and calls[1]["message"].startswith("TypeError: 序列化失敗 ")
    assert SECRET not in calls[1]["message"]
    text = str(info.value)
    assert text.startswith("TypeError: 序列化失敗 ") and "\nTypeError: 序列化失敗 " in text and text.count(MASK) == 2
    _no_secret_anywhere(info.value)


def test_淨值層_KeyboardInterrupt_先收斂為failed_再原樣拋出(book, rt, monkeypatch):
    _holdings(monkeypatch, [{"fund_code": _A, "ccy": "USD"}])
    original = KeyboardInterrupt(f"中斷 {SECRET}")

    def boom(items):
        raise original
    monkeypatch.setattr(ND, "build_nav_table", boom)
    calls = _spy_close(monkeypatch)
    with pytest.raises(KeyboardInterrupt) as info:
        S.refetch_nav([SECRET], runtime=rt)
    assert info.value is original                                       # 原樣拋，不包裝
    assert len(calls) == 1 and calls[0]["outcome"] == "failed" and calls[0]["row_count"] is None
    assert calls[0]["message"].startswith("KeyboardInterrupt: 中斷 ") and SECRET not in calls[0]["message"]
    assert len(_nav_logs(rt)) == 1


# ── 2026-10-09 第二輪小修：open 也納入包裝、`str(exc)` 防呆、結束列「已確定」才標記、補記失敗不加前綴 ──

def _spy_close_seq(monkeypatch, actions):
    """依序對每次呼叫採取動作："write"＝真的寫；"raise_before"＝不寫、拋 TypeError；
    "write_then_raise"＝真的寫完再拋 TypeError。回傳每次呼叫的參數。"""
    calls, real = [], S.RuntimeFetchStore.close_fetch_log   # 2026-10-26：結束紀錄改記在記憶體

    def spy(self, opened, **kw):
        action = actions[len(calls)]
        calls.append(kw)
        if action == "raise_before":
            raise TypeError(f"寫入前驗證失敗 {SECRET}")
        row = real(self, opened, **kw)
        if action == "write_then_raise":
            raise TypeError(f"寫完才失敗 {SECRET}")
        return row

    monkeypatch.setattr(S.RuntimeFetchStore, "close_fetch_log", spy)
    return calls


def _nav_reader(rt):
    out = rt.load_fetch_log()
    return [r for r in out["rows"] if r["source_tier"] == "淨值"], out


def test_淨值層_open拋非SettingsSheetError_遮蔽後拋NavRefetchError_不帶原例外鏈_0筆紀錄(book, rt, monkeypatch):
    def boom(self, tier):
        try:
            raise RuntimeError(f"內層 {SECRET}")
        except RuntimeError:
            raise ValueError(f"helper 失敗 {SECRET}")               # 自帶含秘密值的 __context__
    monkeypatch.setattr(S.RuntimeFetchStore, "open_fetch_log", boom)   # 2026-10-26：開始紀錄改記在記憶體
    monkeypatch.setattr(AH, "load_alo_tables", lambda values: pytest.fail("open 拋錯後不得往下取數"))
    calls = _spy_close(monkeypatch)
    with pytest.raises(S.NavRefetchError) as info:
        S.refetch_nav([SECRET], runtime=rt)
    assert str(info.value).startswith("ValueError: helper 失敗 ") and MASK in str(info.value)
    _no_secret_anywhere(info.value)
    assert calls == [] and rt.open_rows == [] and rt.log_rows == [] and book.tabs == {}


class _StrRaises(Exception):
    def __str__(self):
        raise RuntimeError(f"str 也壞 {SECRET}")


def test_淨值層_例外的str本身拋錯_仍補記failed_拋NavRefetchError(book, rt, monkeypatch):
    _holdings(monkeypatch, [{"fund_code": _A, "ccy": "USD"}])

    def boom(items):
        raise _StrRaises()
    monkeypatch.setattr(ND, "build_nav_table", boom)
    calls = _spy_close(monkeypatch)
    with pytest.raises(S.NavRefetchError) as info:
        S.refetch_nav([SECRET], runtime=rt)
    assert len(calls) == 1 and calls[0]["outcome"] == "failed" and calls[0]["message"] == "_StrRaises"
    assert str(info.value) == "_StrRaises"
    _no_secret_anywhere(info.value)
    assert _nav_logs(rt)[0][4:] == ["failed", "", "_StrRaises"]


def test_淨值層_KeyboardInterrupt補記又失敗_note已遮蔽_原例外原樣拋出(book, rt, monkeypatch):
    _holdings(monkeypatch, [{"fund_code": _A, "ccy": "USD"}])
    original = KeyboardInterrupt("中斷")

    def boom(items):
        raise original
    monkeypatch.setattr(ND, "build_nav_table", boom)
    # ~~fail_with=R.SettingsSheetError(...)~~ → 2026-10-26：結束紀錄改記在記憶體；改以一般例外守同一條收斂
    calls = _spy_close(monkeypatch, fail_with=RuntimeError(f"寫入失敗 {SECRET}"))
    with pytest.raises(KeyboardInterrupt) as info:
        S.refetch_nav([SECRET], runtime=rt)
    assert info.value is original and len(calls) == 1
    notes = info.value.__notes__
    assert len(notes) == 1 and notes[0].startswith("RuntimeError: 寫入失敗 ")
    assert SECRET not in notes[0] and MASK in notes[0] and "補記取數紀錄失敗" not in notes[0]


def test_淨值層_正常close寫入前拋非SettingsSheetError_最終恰一筆failed_in_progress為0(book, rt, monkeypatch):
    _stub_nav(monkeypatch, {_A: (_nav(2), None)})
    calls = _spy_close_seq(monkeypatch, ["raise_before", "write"])
    with pytest.raises(S.NavRefetchError):
        S.refetch_nav([SECRET], runtime=rt)
    assert [c["outcome"] for c in calls] == ["ok", "failed"]
    rows, out = _nav_reader(rt)
    assert len(rows) == 1 and rows[0]["outcome"] == "failed" and rows[0]["row_count"] is None
    assert rows[0]["message"].startswith("TypeError: 寫入前驗證失敗 ") and SECRET not in rows[0]["message"]
    assert out["in_progress"] == 0 and out["duplicate_log_ids"] == 0


def test_淨值層_正常close已寫入才拋錯_同log_id兩列_讀取端取第一列ok_in_progress為0(book, rt, monkeypatch):
    """第二筆同 `log_id` 的 failed 由讀取端 `_reduce_fetch_log` 去重（取第一列）。"""
    _stub_nav(monkeypatch, {_A: (_nav(2), None)})
    calls = _spy_close_seq(monkeypatch, ["write_then_raise", "write"])
    with pytest.raises(S.NavRefetchError):
        S.refetch_nav([SECRET], runtime=rt)
    assert [c["outcome"] for c in calls] == ["ok", "failed"]
    raw = _nav_logs(rt)
    assert [r[4] for r in raw] == ["ok", "failed"] and raw[0][0] == raw[1][0]   # 同一 log_id 兩列
    rows, out = _nav_reader(rt)
    assert len(rows) == 1 and rows[0]["outcome"] == "ok" and rows[0]["row_count"] == 2
    assert out["in_progress"] == 0 and out["duplicate_log_ids"] == 1


# ── 2026-10-09 稽核回修 ──

def test_淨值層_持倉部分分頁讀取失敗_記failed_每張一段分頁名與L1原文_已遮蔽(book, rt, monkeypatch):
    """稽核紅隊 S-1：持倉不完整時不得記 ok、不得沒痕跡。"""
    monkeypatch.setattr(AH, "load_alo_tables", lambda values: {
        "holding": [{"fund_code": _A, "ccy": "USD"}],
        "skipped_tabs": [{"tab": "保單甲", "error": f"APIError 500 https://x/{SECRET}", "unread": False},
                         {"tab": "保單乙", "error": "冷卻中（還剩 30 秒）", "unread": True}]})
    monkeypatch.setattr(ND, "fetch_nav_chain_with_error", lambda key, full_key: (_nav(2), None))
    out = S.refetch_nav([SECRET], runtime=rt)
    log = _nav_logs(rt)[0]
    assert log[4] == "failed" and log[5] == ""
    lines = log[6].split("\n")
    assert lines[0].startswith("保單甲: APIError 500") and MASK in lines[0] and SECRET not in log[6]
    assert lines[1] == "保單乙: 冷卻中（還剩 30 秒）"
    assert out["persist"]["log_message"] == log[6]


def test_淨值層_代碼解析失敗_鍵與原文都經遮蔽(book, rt, monkeypatch):
    """持倉代碼本身帶秘密值、錯誤原文也引用了它：鍵與值兩處都要遮（拿掉任一處 mask 就紅）。"""
    bad = (SECRET,)                                                    # 非字串：錯誤原文會 repr 出輸入
    _holdings(monkeypatch, [{"fund_code": bad, "ccy": "USD"}])
    out = S.refetch_nav([SECRET], runtime=rt)
    log = _nav_logs(rt)[0]
    assert log[4] == "failed" and SECRET not in log[6] and log[6].count(MASK) == 2
    assert "fund_code 須為字串" in log[6]
    assert SECRET not in repr(out["persist"])


# ═══════════════════════ 2026-10-13：FRED 三鍵接到同一條寫表路徑 ═══════════════════════

def _fred_frame():
    """修正序列：2026-07-01 那一期 8/1 首次公布、9/1 修正（目前版本生效日 ≠ 首次公布日）。"""
    df = pd.DataFrame({
        "date": pd.to_datetime(["2026-07-01", "2026-07-01", "2026-08-01"]),
        "value": [4.33, 4.32, 4.30],
        "realtime_start": pd.to_datetime(["2026-08-01", "2026-09-01", "2026-09-02"]),
        "realtime_end": ["2026-08-31", "9999-12-31", "9999-12-31"],
    })
    df.attrs.update(fetched_at="2026-10-13T06:00:00+00:00", realtime_floor="2024-10-13",
                    source="FRED:X:vintages")
    return df


@pytest.fixture
def fred_on(monkeypatch):
    import datetime as _dt
    monkeypatch.setattr(mi, "INDICATOR_SPECS", _SPECS_AS_SHIPPED)
    monkeypatch.setattr(mi, "_utc_today", lambda: _dt.date(2026, 10, 13))
    seen = []
    monkeypatch.setattr(mi, "fetch_fred_vintages_with_error",
                        lambda sid, key, start: (seen.append(key) or (_fred_frame(), None)))
    return seen


def test_FRED接線_金鑰往下傳_首次公布列與修正列都寫入_讀回is_revised與重算一致(book, rt, monkeypatch, fred_on):
    _stub(monkeypatch, _vix([17.0, 18.5], ["2026-09-22", "2026-09-23"]))
    out = S.run_market_indicator_fetch([SECRET], runtime=rt, fred_api_key="KEY")
    assert fred_on == ["KEY", "KEY", "KEY"]
    p = out["persist"]
    assert p["ok"] is True and p["appended"] == 2 + 3 * 3
    assert _logs(rt)[1][4:] == ["ok", str(2 + 3 * 3), ""]   # row_count＝取回列數（過濾前）
    # ~~讀回試算表（is_revised_mismatch／conflicts）~~ → 2026-10-26：讀回本次工作階段那一份（is_revised 由 L1 純函式重算）
    assert p["conflicts"] == []
    back = rt.load_market_indicator()
    fed = sorted((r["obs_date"], r["release_date"], r["value_num"], r["is_revised"])
                 for r in back["rows"] if r["indicator_key"] == "policy_rate_pct")
    assert fed == [("2026-07-01", "2026-08-01", 4.33, False), ("2026-07-01", "2026-09-01", 4.32, True),
                   ("2026-08-01", "2026-09-02", 4.30, False)]


def test_FRED接線_沒給金鑰_FRED三鍵記failed_訊息逐字寫未設定FRED_API_KEY(book, rt, monkeypatch, fred_on):
    _stub(monkeypatch, _vix([17.0], ["2026-09-22"]))
    out = S.run_market_indicator_fetch([SECRET], runtime=rt)
    assert fred_on == []                                   # 沒金鑰不打 L1
    log = _logs(rt)[1]
    assert log[4] == "failed"
    for key in _FRED_KEYS:
        assert f"{key}: 未設定 FRED_API_KEY" in log[6]
    assert len(out["table"]["rows"]) == 1                   # VIX 照寫


def test_FRED接線_重新取數也把金鑰往下傳(book, rt, monkeypatch, fred_on):
    _stub(monkeypatch, _vix([17.0], ["2026-09-22"]))
    out = S.refetch_market_indicator([SECRET], runtime=rt, fred_api_key="KEY")
    assert fred_on == ["KEY", "KEY", "KEY"] and out["persist"]["ok"] is True


# ═══════════════════════ 2026-10-14 稽核 N／M：部分略過要看得見 ═══════════════════════


def test_部分略過_ok時記在persist_skipped_summary_fetch_log_message照44為空(book, rt, monkeypatch):
    """`44` `fetch_log.message`「成功時為空」（L1 `fetch_log_row` 也拒收 ok 帶訊息）⇒ ok 時只放 persist；
    `row_count` 照舊是取回列數（過濾前），不是寫入列數。"""
    _stub(monkeypatch, _vix([17.0, 18.5, 19.0], ["2026-09-22", "2026-09-23", "2026-09-25"]))
    out = S.run_market_indicator_fetch([SECRET], runtime=rt)
    p = out["persist"]
    log = _logs(rt)[1]
    assert log[4:] == ["ok", "3", ""]                       # 取回 3 列（過濾前）；寫入 2 列
    assert len(out["table"]["rows"]) == 2
    (line,) = p["skipped_summary"]
    assert line.startswith("vol_index: 取回 3 列、寫入 2 列；略過：") and "觀測日不早於取得日" in line


def test_部分略過_failed時附在fetch_log_message之後(book, rt, monkeypatch, fred_on):
    _stub(monkeypatch, _vix([17.0, 19.0], ["2026-09-22", "2026-09-25"]))
    out = S.run_market_indicator_fetch([SECRET], runtime=rt)                # 沒給 FRED 金鑰 ⇒ failed
    log = _logs(rt)[1]
    assert log[4] == "failed"
    assert "部分略過（該鍵其餘列照寫）：\nvol_index: 取回 2 列、寫入 1 列；略過：" in log[6]
    assert out["persist"]["log_message"] == log[6]           # 畫面讀的那一份與試算表逐字相同


def test_部分略過摘要_經遮蔽才放進persist與message(book, rt, monkeypatch, fred_on):
    """`skipped_summary` 與 failed 時的 message 都要經遮蔽（2026-10-14 稽核 N 的 O13）。"""
    from services.v2_tables import masking

    good_rows, _e, _s = mi.rows_from_daily_close("vol_index", _vix([17.0], ["2026-09-22"]), None,
                                                 value_unit="index", obs_date_rule=mi.OBS_DATE_SAME_DAY)

    def fake_build(sink, **_kw):
        table = {"rows": good_rows, "errors": {"credit_spread_pct": mi.MISSING_FRED_API_KEY},
                 "pending": {}, "fetched": {"vol_index": 2, "credit_spread_pct": 0},
                 "skipped": {"vol_index": [f"含憑證 token={SECRET} 的略過原因 1 筆不寫"]}}
        sink(table)
        return table

    out = S.run_market_indicator_fetch([SECRET], runtime=rt, build=fake_build)
    (line,) = out["persist"]["skipped_summary"]
    assert SECRET not in line and masking.MASK in line
    log = _logs(rt)[1]
    assert log[4] == "failed" and SECRET not in log[6] and masking.MASK in log[6]


def test_整鍵都沒寫入的鍵_只在失敗原因_不在部分略過摘要(book, rt, monkeypatch, fred_on):
    """`kept > 0` 條件（2026-10-14 稽核 N 的 O16）：取回 >0 列、一列都沒寫成的鍵只出現在失敗原因。"""
    s = _vix([17.0], ["2026-09-22"])
    del s.attrs["exchange_tz"]                               # 缺時區 ⇒ 整鍵不寫
    _stub(monkeypatch, s)
    out = S.run_market_indicator_fetch([SECRET], runtime=rt)
    assert out["persist"]["skipped_summary"] == []
    log = _logs(rt)[1]
    assert "vol_index: 取回 1 列，全部未寫入" in log[6]
    assert "寫入 0 列" not in log[6] and "部分略過" not in log[6]


# ═══════════════════════ 2026-10-26 獨立稽核必修 2：讀取端合併沿用同一套規則 ═══════════════════════

def _mi_row(obs, value, *, key="vol_index", rel=None, fetched="2026-09-25T06:00:00Z"):
    return {"indicator_key": key, "obs_date": obs, "release_date": rel or obs, "value_num": value,
            "value_unit": "index", "source_tier": "市場指標", "is_revised": False, "fetched_at": fetched}


def test_讀取端合併_同主鍵同值視為已存在_不同值不覆蓋列入conflicts_新主鍵採用():
    rt = S.RuntimeFetchStore()
    rt.append_market_indicator([_mi_row("2026-09-21", 15.0), _mi_row("2026-09-22", 17.0),
                                _mi_row("2026-09-23", 18.5)])
    sheet = [_mi_row("2026-09-21", 15.0, fetched="2026-09-24T06:00:00Z"), _mi_row("2026-09-22", 16.0)]
    out = S.merge_sheet_and_runtime_indicators(sheet, rt)
    assert [(r["obs_date"], r["value_num"]) for r in out["rows"]] == [
        ("2026-09-21", 15.0), ("2026-09-22", 16.0), ("2026-09-23", 18.5)]       # 矛盾那筆留試算表值
    assert out["rows"][0]["fetched_at"] == "2026-09-24T06:00:00Z"               # 同值：留試算表那一列
    assert [r["obs_date"] for r in out["runtime_rows"]] == ["2026-09-23"]
    assert [c["key"] for c in out["conflicts"]] == [("vol_index", "2026-09-22", "2026-09-22")]


def test_讀取端合併_is_revised以合併後主鍵集合重算():
    rt = S.RuntimeFetchStore()
    rt.append_market_indicator([_mi_row("2026-07-01", 4.32, key="policy_rate_pct", rel="2026-09-01")])
    sheet = [_mi_row("2026-07-01", 4.33, key="policy_rate_pct", rel="2026-08-01")]
    out = S.merge_sheet_and_runtime_indicators(sheet, rt)
    assert [(r["release_date"], r["is_revised"]) for r in out["rows"]] == [
        ("2026-08-01", False), ("2026-09-01", True)]
    assert out["conflicts"] == []


def test_讀取端合併_沒有本次資料_原樣():
    sheet = [_mi_row("2026-09-21", 15.0)]
    out = S.merge_sheet_and_runtime_indicators(sheet, S.RuntimeFetchStore())
    assert out == {"rows": sheet, "runtime_rows": [], "conflicts": []}


@pytest.mark.parametrize("existing, incoming", [
    ([], [_mi_row("2026-09-21", 15.0), _mi_row("2026-09-22", 16.0)]),
    ([_mi_row("2026-09-21", 15.0)], [_mi_row("2026-09-21", 15.0), _mi_row("2026-09-22", 16.0)]),
    ([_mi_row("2026-09-21", 15.0)], [_mi_row("2026-09-21", 15.5), _mi_row("2026-09-22", 16.0)]),
    ([], [_mi_row("2026-09-22", 16.0), _mi_row("2026-09-22", 16.1)]),                  # 同一批內互相矛盾
    ([], [_mi_row("2026-09-22", 16.0), _mi_row("2026-09-22", 16.0)]),                  # 同一批內重複
    ([_mi_row("2026-07-01", 4.33, rel="2026-08-01")], [_mi_row("2026-07-01", 4.32, rel="2026-09-01")]),
])
def test_merge_market_indicator與append_market_indicator同輸入同結果(book, existing, incoming):
    """純函式（記憶體）與休眠寫入函式（假試算表）對照：appended／already_present／conflicts 與寫進去的列一致。"""
    from _fake_settings_sheet import FakeWorksheet
    book.allow_writes = True   # 本條就是要走休眠中的 L1 寫入函式本體當對照組
    head = [n for n, _k, _nl in R.MARKET_INDICATOR_SPEC]
    book.tabs["market_indicator"] = FakeWorksheet(
        book, "market_indicator", [head] + [R._serialize(R.MARKET_INDICATOR_SPEC, r) for r in existing])
    sheet_out = R.append_market_indicator(incoming, mask=lambda m: m)
    mem_out = R.merge_market_indicator(existing, incoming)
    for k in ("appended", "already_present", "conflicts"):
        assert sheet_out[k] == mem_out[k], k
    R.clear_cache()
    sheet_rows = R.load_market_indicator(mask=lambda m: m)["rows"]

    def pick(rows):
        return sorted((r["indicator_key"], r["obs_date"], r["release_date"], r["value_num"], r["is_revised"])
                      for r in rows)
    assert pick(sheet_rows) == pick(mem_out["rows"])
