# -*- coding: utf-8 -*-
"""repositories/settings_sheet_repository.py 的單元測試（fast lane；假 gspread，不打網路）。

依據 docs/v2/50_settings_sheet_design.md 第 3～9 節與 B5 列的四個測試情境。
假物件見 tests/_fake_settings_sheet.py；上游往返一律以 `book.calls` 計數。
系統 python 沒有 gspread —— 本檔刻意不用 gspread 的例外型別（不需要 importorskip）：
暫時性錯誤用 `ConnectionError`（無狀態碼 → `is_transient_gspread_error` 判為暫時性），
非暫時性錯誤用只剩字串的配額錯誤（`is_quota_error` → 不重試、記在憑證鍵）。
"""

from __future__ import annotations

import secrets as _secrets
from datetime import datetime, timedelta, timezone

import pytest

from _fake_settings_sheet import FakeClient, FakeSpreadsheet, FakeWorksheet
from infra import gspread_retry as GR
from infra import source_backoff as SB
from repositories import settings_sheet_repository as R

MASK = "‹已遮蔽›"
SECRET = "k" + _secrets.token_hex(12)    # 現場隨機產生（ACCEPTANCE 7.5 末段）
SHEET = "sheet-under-test"

US_HEAD = ["setting_key", "setting_value", "value_kind", "updated_at"]
MI_HEAD = ["indicator_key", "obs_date", "release_date", "value_num", "value_unit",
           "source_tier", "is_revised", "fetched_at"]
FL_HEAD = ["log_id", "source_tier", "started_at", "finished_at", "outcome", "row_count", "message"]
FO_HEAD = FL_HEAD[:3]

T0 = datetime(2026, 9, 26, 3, 0, 0, tzinfo=timezone.utc)


def mask(text: str) -> str:
    return text.replace(SECRET, MASK)


class Clock:
    def __init__(self):
        self.mono = 1000.0
        self.now = T0

    def advance(self, seconds):
        self.mono += seconds
        self.now += timedelta(seconds=seconds)


@pytest.fixture
def env(monkeypatch):
    """回傳 (book, clock, secrets dict)。secrets dict 可在測試內改。"""
    book = FakeSpreadsheet()
    clock = Clock()
    secrets = {"SETTINGS_SHEET_ID": SHEET,
               "google_service_account": {"client_email": "sa@example.iam.gserviceaccount.com"}}
    monkeypatch.setattr(R, "get_secret", lambda key, default=None: secrets.get(key, default))
    monkeypatch.setattr(R, "_make_client", lambda creds: FakeClient(book))
    monkeypatch.setattr(R, "_clock", lambda: clock.mono)
    monkeypatch.setattr(R, "_utcnow", lambda: clock.now)
    monkeypatch.setattr(GR.time, "sleep", lambda _s: None)
    R.clear_cache()
    SB.reset_all()
    yield book, clock, secrets
    R.clear_cache()
    SB.reset_all()


def _quota_error(extra=""):
    return Exception(f"APIError: [429]: Quota exceeded for quota metric 'Read requests' {extra}")


def _mi(key="vol_index", obs="2026-09-01", rel=None, value=17.42, fetched="2026-09-25T06:00:00Z",
        revised=False, unit="index"):
    return {"indicator_key": key, "obs_date": obs, "release_date": rel or obs, "value_num": value,
            "value_unit": unit, "source_tier": "市場指標", "is_revised": revised,
            "fetched_at": fetched}


def _put(book, title, rows):
    book.tabs[title] = FakeWorksheet(book, title, rows)


# ═══════════════════════ 設定缺漏：fail loud、零往返 ═══════════════════════

@pytest.mark.parametrize("value", [None, "", "   "])
def test_沒設SETTINGS_SHEET_ID_報未設定且不打上游(env, value):
    book, _clock, secrets = env
    secrets["SETTINGS_SHEET_ID"] = value
    with pytest.raises(R.SettingsSheetError) as err:
        R.load_user_settings(mask=mask)
    assert err.value.code == "not_configured"
    assert "SETTINGS_SHEET_ID" in str(err.value)
    with pytest.raises(R.SettingsSheetError):
        R.save_user_setting("mkt_window_days", "90", "int", mask=mask)
    assert book.calls == []


def test_模組內沒有寫死任何預設ID(env):
    """正控：同一個讀法在有值時讀得到；負控：沒值時不退回任何字串。"""
    _book, _clock, secrets = env
    assert R.settings_sheet_id(mask=mask) == SHEET
    secrets.pop("SETTINGS_SHEET_ID")
    with pytest.raises(R.SettingsSheetError):
        R.settings_sheet_id(mask=mask)


def test_沒有服務帳戶_報未設定服務帳戶(env):
    book, _clock, secrets = env
    secrets.pop("google_service_account")
    with pytest.raises(R.SettingsSheetError) as err:
        R.load_fetch_log(mask=mask)
    assert err.value.code == "no_service_account"
    assert book.calls == []


def test_mask是必填參數():
    with pytest.raises(TypeError):
        R.load_user_settings()  # noqa —— 忘了傳 mask 必須當場炸，不能靜靜地不遮


# ═══════════════════════ user_setting ═══════════════════════

def test_分頁不存在_讀取是尚無資料不是錯誤(env):
    book, _c, _s = env
    out = R.load_user_settings(mask=mask)
    assert out["rows"] == {} and out["tab_missing"] is True
    assert book.writes() == []   # 讀取路徑不建分頁


def test_存檔_分頁不存在時建立並寫一次標頭_RAW_只追加(env):
    book, clock, _s = env
    row = R.save_user_setting("mkt_window_days", "90", "int", mask=mask)
    assert row["updated_at"] == "2026-09-26T03:00:00Z"
    assert book.data("user_setting_log") == [US_HEAD, ["mkt_window_days", "90", "int",
                                                       "2026-09-26T03:00:00Z"]]
    appends = [c for c in book.calls if c[0] == "append_rows"]
    assert appends and all(c[2] == "RAW" and c[3] == "INSERT_ROWS" for c in appends)


def test_每個鍵取最後一列_清除後回到空值(env):
    book, clock, _s = env
    R.save_user_setting("mkt_window_days", "90", "int", mask=mask)
    clock.advance(1)
    R.save_user_setting("mkt_baseline_date", "2026-01-02", "date", mask=mask)
    clock.advance(1)
    R.save_user_setting("mkt_window_days", "120", "int", mask=mask)
    out = R.load_user_settings(mask=mask)
    assert out["rows"]["mkt_window_days"]["setting_value"] == "120"
    assert out["rows"]["mkt_baseline_date"]["setting_value"] == "2026-01-02"
    clock.advance(1)
    R.save_user_setting("mkt_window_days", None, "int", mask=mask)
    out = R.load_user_settings(mask=mask)
    cleared = out["rows"]["mkt_window_days"]
    assert cleared["setting_value"] is None and cleared["updated_at"] == "2026-09-26T03:00:03Z"
    assert book.data("user_setting_log")[-1] == ["mkt_window_days", "", "int", "2026-09-26T03:00:03Z"]


@pytest.mark.parametrize("key,value,kind", [
    ("mkt_window_days", "", "int"),        # 空字串不是合法值；清除請傳 None
    ("mkt_window_days", 90, "int"),        # 非字串
    ("mkt_window_days", "90", "text"),     # value_kind 不在值域
    ("", "90", "int"),
    (" mkt_window_days", "90", "int"),
])
def test_存檔_值不合格就不寫(env, key, value, kind):
    book, _c, _s = env
    with pytest.raises(ValueError):
        R.save_user_setting(key, value, kind, mask=mask)
    assert book.calls == []


def test_存檔失敗不重試(env):
    book, _c, _s = env
    book.fail_next("append_rows", ConnectionError("reset"), title="user_setting_log", times=3)
    _put(book, "user_setting_log", [US_HEAD])
    with pytest.raises(R.SettingsSheetError) as err:
        R.save_user_setting("mkt_window_days", "90", "int", mask=mask)
    assert err.value.code == "api"
    appends = [c for c in book.calls if c[0] == "append_rows"]
    assert len(appends) == 1


def test_存檔回報失敗但其實已送達_重新讀取看得到(env):
    """`50` 第 8 節：可能其實已存進去；存檔不論成敗都清快取，所以重讀就看得到。"""
    book, _c, _s = env
    R.save_user_setting("mkt_window_days", "90", "int", mask=mask)
    assert R.load_user_settings(mask=mask)["rows"]["mkt_window_days"]["setting_value"] == "90"
    book.fail_next("append_rows", _quota_error(), title="user_setting_log", delivered=True)
    with pytest.raises(R.SettingsSheetError):
        R.save_user_setting("mkt_window_days", "120", "int", mask=mask)
    SB.reset_all()   # 解除 429 冷卻（冷卻期間讀取也被跳過，那是 `50` 第 8 節 429 列的行為）
    assert R.load_user_settings(mask=mask)["rows"]["mkt_window_days"]["setting_value"] == "120"


def test_最新一列壞掉的鍵_不退回較舊的值(env):
    book, _c, _s = env
    _put(book, "user_setting_log", [
        US_HEAD,
        ["mkt_window_days", "90", "int", "2026-09-26T03:00:00Z"],
        ["mkt_window_days", "120", "integer", "2026-09-26T03:00:01Z"],   # value_kind 不在值域
        ["alo_target_weights", "[]", "list", "2026-09-26 03:00:01"],        # 時間格式不符
        [],                                                                 # 空白列
        ["mkt_baseline_date", "2026-01-02", "date", "2026-09-26T03:00:02Z"],
    ])
    out = R.load_user_settings(mask=mask)
    assert set(out["rows"]) == {"mkt_baseline_date"}
    assert out["broken_keys"] == ["alo_target_weights", "mkt_window_days"]
    assert [b["row"] for b in out["bad_rows"]] == [3, 4]
    assert out["blank_rows"] == 1


# ═══════════════════════ 標頭：不符就停、不改寫 ═══════════════════════

def test_標頭不符_讀寫都停_不改寫標頭(env):
    book, _c, _s = env
    wrong = ["setting_key", "value", "value_kind", "updated_at"]
    _put(book, "user_setting_log", [wrong, ["a", "1", "int", "2026-09-26T03:00:00Z"]])
    with pytest.raises(R.SettingsSheetError) as err:
        R.load_user_settings(mask=mask)
    assert err.value.code == "header_mismatch"
    assert err.value.details["actual"] == wrong and err.value.details["expected"] == US_HEAD
    with pytest.raises(R.SettingsSheetError) as err2:
        R.save_user_setting("mkt_window_days", "90", "int", mask=mask)
    assert err2.value.code == "header_mismatch"
    assert book.writes() == []
    assert book.data("user_setting_log")[0] == wrong


def test_既有的空分頁_不代寫標頭(env):
    book, _c, _s = env
    _put(book, "fetch_log_open", [])
    with pytest.raises(R.SettingsSheetError) as err:
        R.open_fetch_log("市場指標", mask=mask)
    assert err.value.code == "header_mismatch"
    assert book.writes() == []


def test_標頭尾端空儲存格不算不符(env):
    book, _c, _s = env
    _put(book, "user_setting_log", [US_HEAD + ["", ""]])
    assert R.load_user_settings(mask=mask)["rows"] == {}


def test_標頭不符不登記冷卻(env):
    book, _c, _s = env
    _put(book, "user_setting_log", [["x"]])
    with pytest.raises(R.SettingsSheetError):
        R.load_user_settings(mask=mask)
    assert SB.get_backoff_state() == []


# ═══════════════════════ 快取（60 秒、只快取成功、寫後清）═══════════════════════

def _reads(book):
    return len([c for c in book.calls if c[0] == "values_batch_get"])


def test_讀取快取60秒(env):
    book, clock, _s = env
    _put(book, "user_setting_log", [US_HEAD])
    R.load_user_settings(mask=mask)
    R.load_user_settings(mask=mask)
    assert _reads(book) == 1
    clock.advance(59)
    R.load_user_settings(mask=mask)
    assert _reads(book) == 1
    clock.advance(2)
    R.load_user_settings(mask=mask)
    assert _reads(book) == 2


def test_失敗不進快取(env):
    book, _c, _s = env
    _put(book, "user_setting_log", [US_HEAD])
    book.fail_next("values_batch_get", _quota_error())
    with pytest.raises(R.SettingsSheetError):
        R.load_user_settings(mask=mask)
    SB.reset_all()
    before = len(book.calls)
    assert R.load_user_settings(mask=mask)["rows"] == {}
    assert len(book.calls) > before


@pytest.mark.parametrize("fail", [False, True])
def test_存檔不論成敗都清快取(env, fail):
    book, _c, _s = env
    _put(book, "user_setting_log", [US_HEAD])
    R.load_user_settings(mask=mask)
    if fail:
        book.fail_next("append_rows", ConnectionError("reset"), title="user_setting_log")
        with pytest.raises(R.SettingsSheetError):
            R.save_user_setting("mkt_window_days", "90", "int", mask=mask)
        SB.reset_all()
    else:
        R.save_user_setting("mkt_window_days", "90", "int", mask=mask)
    reads = _reads(book)
    R.load_user_settings(mask=mask)
    assert _reads(book) == reads + 1


def test_取數紀錄寫入後也清快取(env):
    book, _c, _s = env
    _put(book, "fetch_log", [FL_HEAD])
    _put(book, "fetch_log_open", [FO_HEAD])
    R.load_fetch_log(mask=mask)
    reads = _reads(book)
    R.open_fetch_log("市場指標", mask=mask)
    R.load_fetch_log(mask=mask)
    assert _reads(book) == reads + 2   # open_fetch_log 自己讀一次＋load 重讀一次


# ═══════════════════════ 冷卻、遮蔽 ═══════════════════════

def test_失敗後冷卻中不打上游(env):
    book, _c, _s = env
    book.fail_next("open_by_key", _quota_error())
    with pytest.raises(R.SettingsSheetError) as err:
        R.load_user_settings(mask=mask)
    assert err.value.code == "api"
    calls = len(book.calls)
    with pytest.raises(R.SettingsSheetError) as err2:
        R.load_user_settings(mask=mask)
    assert err2.value.code == "cooling" and err2.value.remaining_sec > 0
    assert "秒" in str(err2.value)
    assert len(book.calls) == calls


def test_錯誤訊息過mask且不帶出原始例外(env):
    book, _c, _s = env
    book.fail_next("open_by_key", _quota_error(extra=f"key={SECRET}"))
    with pytest.raises(R.SettingsSheetError) as err:
        R.load_user_settings(mask=mask)
    text = str(err.value)
    assert SECRET not in text and MASK in text
    assert err.value.__cause__ is None and err.value.__suppress_context__ is True


def test_404提示附服務帳戶信箱(env):
    book, _c, _s = env

    class SpreadsheetNotFound(Exception):
        pass

    book.fail_next("open_by_key", SpreadsheetNotFound(""), times=4)
    with pytest.raises(R.SettingsSheetError) as err:
        R.load_user_settings(mask=mask)
    assert "sa@example.iam.gserviceaccount.com" in err.value.hint


# ═══════════════════════ fetch_log ═══════════════════════

def test_取數紀錄_開始與結束_讀取合併(env):
    book, clock, _s = env
    opened = R.open_fetch_log("市場指標", mask=mask)
    assert opened["started_at"] == "2026-09-26T03:00:00Z"
    assert opened["log_id"].startswith("2026-09-26T03:00:00Z-") and len(opened["log_id"]) == 29
    clock.advance(5)
    R.close_fetch_log(opened, outcome="ok", row_count=3, message=None, mask=mask)
    out = R.load_fetch_log(mask=mask)
    assert out["rows"] == [{"log_id": opened["log_id"], "source_tier": "市場指標",
                            "started_at": "2026-09-26T03:00:00Z",
                            "finished_at": "2026-09-26T03:00:05Z", "outcome": "ok",
                            "row_count": 3, "message": None}]
    assert book.data("fetch_log")[1][5:] == ["3", ""]


def test_fetch_log追加可重試(env):
    book, _c, _s = env
    book.fail_next("append_rows", ConnectionError("reset"), title="fetch_log_open")
    R.open_fetch_log("市場指標", mask=mask)
    assert len([c for c in book.calls if c[0] == "append_rows" and c[1] == "fetch_log_open"]) == 3
    # 3 ＝ 建分頁後寫標頭 1 ＋ 資料列失敗 1 ＋ 重試 1
    assert len(book.data("fetch_log_open")) == 2


def test_B5d_同一log_id重送_讀取端取第一列並計數(env):
    book, _c, _s = env
    row = ["L1", "市場指標", "2026-09-26T02:00:00Z", "2026-09-26T02:00:05Z", "ok", "3", ""]
    _put(book, "fetch_log", [FL_HEAD, row, row[:4] + ["ok", "4", ""]])
    out = R.load_fetch_log(mask=mask)
    assert len(out["rows"]) == 1 and out["rows"][0]["row_count"] == 3
    assert out["duplicate_log_ids"] == 1


def test_中斷判定_超過時限才顯示為中斷_之前計入進行中(env):
    book, clock, _s = env
    stale = (T0 - timedelta(seconds=R.OPEN_LOG_STALE_SEC)).strftime("%Y-%m-%dT%H:%M:%SZ")
    fresh = (T0 - timedelta(seconds=R.OPEN_LOG_STALE_SEC - 1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    _put(book, "fetch_log_open", [FO_HEAD, ["A", "市場指標", stale], ["B", "市場指標", fresh],
                                  ["C", "市場指標", stale]])
    _put(book, "fetch_log", [FL_HEAD, ["C", "市場指標", stale, "2026-09-26T02:00:10Z", "ok", "1", ""]])
    out = R.load_fetch_log(mask=mask)
    by_id = {r["log_id"]: r for r in out["rows"]}
    assert set(by_id) == {"A", "C"}
    assert by_id["A"]["finished_at"] is None and by_id["A"]["outcome"] == "failed"
    assert by_id["A"]["message"] == R.INTERRUPTED_MESSAGE and by_id["A"]["row_count"] is None
    assert out["in_progress"] == 1


def test_fetch_log裡finished_at為空的列是中斷不是格式不符(env):
    book, _c, _s = env
    _put(book, "fetch_log", [FL_HEAD, ["X", "市場指標", "2026-09-26T02:00:00Z", "", "failed", "",
                                       "取數沒有結束紀錄"]])
    out = R.load_fetch_log(mask=mask)
    assert out["bad_rows"] == [] and out["rows"][0]["finished_at"] is None


@pytest.mark.parametrize("kw", [
    {"outcome": "ok", "row_count": None, "message": None},
    {"outcome": "ok", "row_count": 1, "message": "x"},
    {"outcome": "failed", "row_count": 1, "message": "x"},
    {"outcome": "failed", "row_count": None, "message": ""},
    {"outcome": "partial", "row_count": None, "message": "x"},
])
def test_fetch_log結束列不合規就不寫(env, kw):
    book, _c, _s = env
    opened = {"log_id": "L", "source_tier": "市場指標", "started_at": "2026-09-26T03:00:00Z"}
    with pytest.raises(ValueError):
        R.close_fetch_log(opened, mask=mask, **kw)
    assert book.calls == []


# ═══════════════════════ market_indicator ═══════════════════════

def test_寫入格式_浮點十進位字面_時間截到秒並轉世界協調時間(env):
    book, _c, _s = env
    R.append_market_indicator([
        _mi(obs="2026-09-01", value=17.42, fetched="2026-09-25T06:00:00.123456+00:00"),
        _mi(obs="2026-09-02", value=1e-05, fetched="2026-09-25T14:00:00+08:00"),
    ], mask=mask)
    data = book.data("market_indicator")
    assert data[0] == MI_HEAD
    assert data[1] == ["vol_index", "2026-09-01", "2026-09-01", "17.42", "index", "市場指標",
                       "FALSE", "2026-09-25T06:00:00Z"]
    assert data[2][3] == "0.00001" and data[2][7] == "2026-09-25T06:00:00Z"
    rows = R.load_market_indicator(mask=mask)["rows"]
    assert [r["value_num"] for r in rows] == [17.42, 1e-05]


def test_寫前去重_已存在同一筆不再追加(env):
    book, _c, _s = env
    R.append_market_indicator([_mi()], mask=mask)
    appends = len([c for c in book.calls if c[0] == "append_rows"])
    out = R.append_market_indicator([_mi(fetched="2026-09-26T06:00:00Z")], mask=mask)
    assert out == {"appended": 0, "already_present": 1, "conflicts": []}
    assert len([c for c in book.calls if c[0] == "append_rows"]) == appends


def test_修正值另起一列_is_revised為真_舊列不動(env):
    book, _c, _s = env
    R.append_market_indicator([_mi(obs="2026-08-01", rel="2026-08-02", value=17.0)], mask=mask)
    old = book.data("market_indicator")[1]
    out = R.append_market_indicator([_mi(obs="2026-08-01", rel="2026-08-09", value=17.5)], mask=mask)
    assert out["appended"] == 1
    data = book.data("market_indicator")
    assert data[1] == old and data[2][6] == "TRUE"
    rows = R.load_market_indicator(mask=mask)["rows"]
    assert [(r["release_date"], r["value_num"], r["is_revised"]) for r in rows] == [
        ("2026-08-02", 17.0, False), ("2026-08-09", 17.5, True)]


def test_寫前看到主鍵矛盾_整批不寫(env):
    book, _c, _s = env
    R.append_market_indicator([_mi(value=17.0)], mask=mask)
    before = book.data("market_indicator")
    out = R.append_market_indicator([_mi(obs="2026-09-02", value=18.0), _mi(value=17.5)], mask=mask)
    assert out["appended"] == 0 and len(out["conflicts"]) == 1
    c = out["conflicts"][0]
    assert c["key"] == ("vol_index", "2026-09-01", "2026-09-01")
    assert (c["existing_value_num"], c["new_value_num"]) == (17.0, 17.5)
    assert book.data("market_indicator") == before


def test_B5a_追加已送達但回報失敗而重試_讀取結果與只追加一次相同(env):
    book, _c, _s = env
    _put(book, "market_indicator", [MI_HEAD])
    book.fail_next("append_rows", ConnectionError("reset after send"), title="market_indicator",
                   delivered=True)
    R.append_market_indicator([_mi(obs="2026-09-01"), _mi(obs="2026-09-02", value=18.0)], mask=mask)
    assert len(book.data("market_indicator")) == 5            # 標頭＋兩列×2（重送）
    out = R.load_market_indicator(mask=mask)
    assert [(r["obs_date"], r["value_num"]) for r in out["rows"]] == [
        ("2026-09-01", 17.42), ("2026-09-02", 18.0)]
    assert out["duplicates_merged"] == 2 and out["conflicts"] == []


def test_B5b_兩個寫入者交錯寫同一筆_含is_revised不同_讀取端只留一筆(env):
    book, _c, _s = env
    a = ["vol_index", "2026-09-01", "2026-09-01", "17.42", "index", "市場指標", "FALSE",
         "2026-09-25T06:00:00Z"]
    b = a[:6] + ["TRUE", "2026-09-25T06:00:09Z"]
    _put(book, "market_indicator", [MI_HEAD, a, b])
    out = R.load_market_indicator(mask=mask)
    assert len(out["rows"]) == 1
    assert out["rows"][0]["is_revised"] is False and out["rows"][0]["fetched_at"] == a[7]
    assert out["duplicates_merged"] == 1 and out["is_revised_mismatch"] == 1


def test_B5c_同主鍵不同數值_讀取端整組不採用並計數(env):
    book, _c, _s = env
    a = ["vol_index", "2026-09-01", "2026-09-01", "17.42", "index", "市場指標", "FALSE",
         "2026-09-25T06:00:00Z"]
    b = a[:3] + ["17.5"] + a[4:]
    ok = ["vol_index", "2026-09-02", "2026-09-02", "18", "index", "市場指標", "FALSE",
          "2026-09-25T06:00:00Z"]
    _put(book, "market_indicator", [MI_HEAD, a, ok, b])
    out = R.load_market_indicator(mask=mask)
    assert [r["obs_date"] for r in out["rows"]] == ["2026-09-02"]
    assert len(out["conflicts"]) == 1 and [x["row"] for x in out["conflicts"][0]["rows"]] == [2, 4]


def test_解析不了的列不收並計數(env):
    book, _c, _s = env
    good = ["vol_index", "2026-09-01", "2026-09-01", "17.42", "index", "市場指標", "FALSE",
            "2026-09-25T06:00:00Z"]
    _put(book, "market_indicator", [
        MI_HEAD, good,
        good[:3] + ["1,234.5"] + good[4:],                 # 千分位
        good[:6] + ["false"] + good[7:],                   # 布林大小寫
        good[:5] + ["T1"] + good[6:],                      # source_tier 不在值域
        good + ["多一欄"],
    ])
    out = R.load_market_indicator(mask=mask)
    assert len(out["rows"]) == 1 and [b["row"] for b in out["bad_rows"]] == [3, 4, 5, 6]


def test_不合格的輸入列是呼叫端的bug_當場炸且不寫(env):
    book, _c, _s = env
    with pytest.raises(ValueError):
        R.append_market_indicator([_mi(value=float("nan"))], mask=mask)
    with pytest.raises(ValueError):
        R.append_market_indicator([dict(_mi(), extra=1)], mask=mask)
    assert book.calls == []
