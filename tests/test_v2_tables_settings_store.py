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
    monkeypatch.setattr(ND, "fetch_nav_with_error", lambda full_key, portal="": by_code[full_key])


def _nav_logs(book):
    return [r for r in book.data("fetch_log")[1:] if r[1] == "淨值"]


def test_淨值層_全部成功_一筆ok_row_count為取回列數_不寫任何表(book, monkeypatch):
    _stub_nav(monkeypatch, {_A: (_nav(3), None), _B: (_nav(2), None)})
    out = S.refetch_nav([SECRET])
    p = out["persist"]
    assert p["ok"] is True and p["stage"] == "done" and p["log_message"] is None
    assert len(out["table"]["rows"]) == 5
    logs = _nav_logs(book)
    assert len(logs) == 1 and logs[0][4:] == ["ok", "5", ""]
    assert set(book.tabs) == {"fetch_log", "fetch_log_open"}          # 沒有 nav 分頁，也沒寫市場指標
    assert len(book.data("fetch_log_open")) == 2                       # 標頭＋本次一列


def test_淨值層_row_count是過濾前的取回列數(book, monkeypatch):
    s = _nav(3)
    s.iloc[1] = -1.0                                                   # 一列不合理（不大於 0），被略過
    _stub_nav(monkeypatch, {_A: (s, None)})
    out = S.refetch_nav([SECRET])
    assert len(out["table"]["rows"]) == 2
    assert _nav_logs(book)[0][4:] == ["ok", "3", ""]


def test_淨值層_一檔失敗_整筆failed_逐檔原文_已遮蔽(book, monkeypatch):
    raw = f"fetch_nav('{_B}') 即時網址與預存檔皆失敗:\nhttps://x.invalid/q?apikey={SECRET} → 取數失敗(kind=cooling)"
    _stub_nav(monkeypatch, {_A: (_nav(2), None), _B: (pd.Series(dtype=float), raw)})
    out = S.refetch_nav([SECRET])
    p = out["persist"]
    logs = _nav_logs(book)
    assert len(logs) == 1 and logs[0][4] == "failed" and logs[0][5] == ""
    message = logs[0][6]
    assert message == p["log_message"] == f"{_B}: " + p["masked_errors"][_B]
    assert SECRET not in message and MASK in message and "kind=cooling" in message
    assert SECRET not in repr(p)
    assert out["table"]["errors"][_B] == raw                           # 表本身不遮（L2 轉換層原文）


def test_淨值層_兩檔都失敗_逐行列出(book, monkeypatch):
    _stub_nav(monkeypatch, {_A: (None, "HTTP 503 a"), _B: (None, "HTTP 503 b")})
    S.refetch_nav([SECRET])
    assert _nav_logs(book)[0][6] == f"{_A}: HTTP 503 a\n{_B}: HTTP 503 b"


def test_淨值層_整檔扣下_幣別缺_記failed附L2原因(book, monkeypatch):
    _stub_nav(monkeypatch, {_A: (_nav(2), None)}, ccy=None)
    S.refetch_nav([SECRET])
    log = _nav_logs(book)[0]
    assert log[4] == "failed" and log[6].startswith(f"{_A}: 來源未自報幣別") and "2 筆全部不寫" in log[6]


def test_淨值層_代碼解析失敗_記failed(book, monkeypatch):
    _holdings(monkeypatch, [{"fund_code": "壞 代碼", "ccy": "USD"}])
    S.refetch_nav([SECRET])
    log = _nav_logs(book)[0]
    assert log[4] == "failed" and log[6].startswith("壞 代碼: fund_code 含非 ASCII")


def test_淨值層_L1回空沒給原因_不算失敗_記ok_0列(book, monkeypatch):
    _stub_nav(monkeypatch, {_A: (pd.Series(dtype=float), None)})
    out = S.refetch_nav([SECRET])
    assert _nav_logs(book)[0][4:] == ["ok", "0", ""]
    assert out["persist"]["empty"] == {_A: mi.EMPTY_WITHOUT_REASON} and out["persist"]["masked_errors"] == {}


def test_淨值層_持倉讀不到_記failed_原文已遮蔽_不取數(book, monkeypatch):
    def boom(values):
        raise AH.PolicySupplementError(f"讀取失敗 https://x/{SECRET}", code="api")
    monkeypatch.setattr(AH, "load_alo_tables", boom)
    monkeypatch.setattr(ND, "fetch_nav_with_error", lambda *a, **k: pytest.fail("持倉讀不到時不得取數"))
    out = S.refetch_nav([SECRET])
    log = _nav_logs(book)[0]
    assert log[4] == "failed" and log[6].startswith("holding: 讀取失敗") and SECRET not in log[6]
    assert out["table"] is None and out["persist"]["log_message"] == log[6]


def test_淨值層_持倉為空_取數回空_記ok_0列(book, monkeypatch):
    _holdings(monkeypatch, [])
    monkeypatch.setattr(ND, "fetch_nav_with_error", lambda *a, **k: pytest.fail("沒有持倉不得取數"))
    out = S.refetch_nav([SECRET])
    assert _nav_logs(book)[0][4:] == ["ok", "0", ""]
    assert out["persist"]["empty"] and out["persist"]["masked_errors"] == {}


def test_淨值層_同一檔多張保單_取一次_每列持倉都交出幣別(book, monkeypatch):
    calls = []
    _holdings(monkeypatch, [{"fund_code": _A, "ccy": "USD"}, {"fund_code": _A, "ccy": "USD"}])
    monkeypatch.setattr(ND, "fetch_nav_with_error", lambda key, portal="": (calls.append(key) or (_nav(2), None)))
    S.refetch_nav([SECRET])
    assert calls == [_A] and _nav_logs(book)[0][4:] == ["ok", "2", ""]


def test_淨值層_沒設試算表ID_照常取數_不寫任何東西(book, monkeypatch):
    book.cfg.pop("SETTINGS_SHEET_ID")
    _stub_nav(monkeypatch, {_A: (None, f"x {SECRET}")})
    out = S.refetch_nav([SECRET])
    p = out["persist"]
    assert p["stage"] == "fetch_log_open" and p["error_code"] == "not_configured" and p["log_message"] is None
    assert SECRET not in p["masked_errors"][_A] and book.calls == []


def test_淨值層_清掉fetch_nav的快取_第二次真的再取_不動冷卻_不呼叫全域清除(book, monkeypatch):
    """走真的 `fetch_nav`（`_daily_cache`）；只把它往外的兩個出口換成替身：即時網址一律失敗、預存檔回一份序列。"""
    import infra.cache as IC
    calls = {"url": 0, "cache_file": 0}

    def fake_url(*a, **k):
        calls["url"] += 1
        return None

    def fake_cache_file(code):
        calls["cache_file"] += 1
        s = _nav(12)
        s.attrs.update(source=f"GitHubActions:cache/nav/{code}.json", cache_updated_at="2026-09-25T06:00:00+00:00")
        return s

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
    S.refetch_nav([SECRET])
    S.refetch_nav([SECRET])
    assert calls["cache_file"] == 3                                      # 兩次重新取數都真的再取
    assert SB.should_skip("some.nav.host")[0] is True                    # 冷卻原封不動
    assert [r[4:6] for r in _nav_logs(book)] == [["ok", "12"], ["ok", "12"]]
    NM.fetch_nav.cache_clear()


def test_淨值層_程式錯誤不被吞(book, monkeypatch):
    _holdings(monkeypatch, [{"fund_code": _A}])                          # 少了 ccy：本檔的呼叫契約被破壞
    with pytest.raises(KeyError):
        S.refetch_nav([SECRET])
