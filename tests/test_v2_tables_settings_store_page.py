# -*- coding: utf-8 -*-
"""services/v2_tables/settings_store.py 為 set 頁正式模式補的入口（fast lane；假 gspread ＋ 替身 L1 取數）。

- `check_setting_value`／`save_user_setting`：存檔前在 L2 檢查 `setting_value` 與 `value_kind`，
  不符就不存（`44` SET-4）—— 不呼叫 L1、不打上游。
- `save_setting_for_page`：成敗收成純 dict（訊息已遮蔽），畫面依 `status` 選文案。
- `refetch_market_indicator`：只清本次會用到的 L1 取數函式自己的快取，不動來源冷卻（`50` B9）。
- `sheet_gate`／`sheet_title`：寫入閘門與試算表標題（標題過遮蔽）。
"""

from __future__ import annotations

import pathlib
import secrets as _secrets
import sys

import pandas as pd
import pytest

from _fake_settings_sheet import FakeClient, FakeSpreadsheet
from infra import gspread_retry as GR
from infra import source_backoff as SB
from repositories import settings_sheet_repository as R
from services.v2_tables import market_indicator as mi
from services.v2_tables import settings_store as S
from services.v2_tables.masking import MASK

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

SECRET = "k" + _secrets.token_hex(12)
SHEET = "sheet-" + _secrets.token_hex(6)


@pytest.fixture
def book(monkeypatch):
    fake = FakeSpreadsheet()
    cfg = {"SETTINGS_SHEET_ID": SHEET,
           "google_service_account": {"client_email": "sa@example.iam.gserviceaccount.com"}}
    monkeypatch.setattr(R, "get_secret", lambda key, default=None: cfg.get(key, default))
    monkeypatch.setattr(R, "_make_client", lambda creds: FakeClient(fake))
    monkeypatch.setattr(R, "_TITLES", {})
    monkeypatch.setattr(GR.time, "sleep", lambda _s: None)
    fake.cfg = cfg
    R.clear_cache()
    SB.reset_all()
    yield fake
    R.clear_cache()
    SB.reset_all()


# ═══════════════════════ 型別檢查 ═══════════════════════

_CORPUS = [
    ("12", "int"), ("-3", "int"), ("1.5", "int"), ("ninety", "int"), (" 7 ", "int"),
    ("1.5", "float"), ("-0.25", "float"), ("1e3", "float"), ("abc", "float"),
    ("0", "ratio"), ("1", "ratio"), ("0.6", "ratio"), ("1.01", "ratio"), ("-0.1", "ratio"),
    ("2026-09-26", "date"), ("2026-02-30", "date"), ("2026/09/26", "date"), ("20260926", "date"),
    ("1.", "float"), ("-", "int"), ("", "int"), ("\u0663", "int"), ("2026-9-26", "date"), ("-1", "ratio"),
    ('["a", "b"]', "list"), ('{"a": 1}', "list"), ("[", "list"), ("[]", "rules"), ('"x"', "rules"),
]


def test_L2型別判定與畫面那一份逐一相同():
    from ui_v2.set import logic
    for value, kind in _CORPUS:
        assert S.value_matches_kind(value, kind) == logic.value_matches_kind(value, kind), (value, kind)
    assert sum(S.value_matches_kind(v, k) for v, k in _CORPUS) >= 8   # 不是全假
    assert sum(not S.value_matches_kind(v, k) for v, k in _CORPUS) >= 8


def test_型別不符_不存_不呼叫L1_不打上游(book):
    out = S.save_setting_for_page("set_max_age_days", "ninety", "int", [SECRET])
    assert out["status"] == "kind_mismatch" and "不存檔" in out["message"]
    assert book.calls == []
    with pytest.raises(S.ValueKindMismatch):
        S.save_user_setting("set_max_age_days", "1.5", "int", [SECRET])
    assert book.calls == []


def test_型別未定_不存(book):
    out = S.save_setting_for_page("alo_basis", "cost", None, [SECRET])
    assert out["status"] == "kind_missing" and book.calls == []


def test_清除該鍵_None不判值_照存(book):
    out = S.save_setting_for_page("set_max_age_days", None, "int", [SECRET])
    assert out["status"] == "saved"
    rows = S.load_user_settings([SECRET])["rows"]
    assert rows["set_max_age_days"]["setting_value"] is None


def test_型別相符_存檔成功_讀回同值(book):
    out = S.save_setting_for_page("set_max_age_days", "21", "int", [SECRET])
    assert out["status"] == "saved" and out["row"]["setting_value"] == "21"
    assert S.load_user_settings([SECRET])["rows"]["set_max_age_days"]["setting_value"] == "21"


def test_存檔失敗_403_訊息已遮蔽_帶提示與信箱_快取照清(book):
    S.load_user_settings([SECRET])                               # 先讀一次，建立快取
    # 本環境的假 gspread 沒有 APIError 型別；L1 以例外型別名 PermissionError 判 403（`_hint_for`）。
    book.fail_next("append_rows", PermissionError(f"The caller does not have permission {SECRET}"),
                   title="user_setting_log")
    out = S.save_setting_for_page("set_max_age_days", "21", "int", [SECRET])
    assert out["status"] == "failed" and out["code"] == "api"
    assert SECRET not in out["message"] and MASK in out["message"]
    assert out["hint"] == "服務帳戶可能只有檢視權限，需要編輯者"
    assert out["client_email"] == "sa@example.iam.gserviceaccount.com"
    assert R._CACHE == {}                                        # 不論成敗都清快取（L1）


def test_存檔_冷卻中_不打上游(book):
    book.fail_next("open_by_key", Exception("APIError: [429]: Quota exceeded"), times=4)
    with pytest.raises(S.SettingsSheetError):
        S.load_user_settings([SECRET])
    before = len(book.calls)
    out = S.save_setting_for_page("set_max_age_days", "21", "int", [SECRET])
    assert out["status"] == "failed" and out["code"] == "cooling" and out["remaining_sec"] > 0
    assert len(book.calls) == before
    assert S.sheet_gate([SECRET])["state"] == "cooling"


def test_沒設ID_閘門與存檔都是同一句(book):
    book.cfg.pop("SETTINGS_SHEET_ID")
    assert S.sheet_gate([SECRET])["message"] == "未設定試算表 ID，暫停寫入"
    out = S.save_setting_for_page("set_max_age_days", "21", "int", [SECRET])
    assert out["status"] == "failed" and out["code"] == "not_configured"
    assert out["message"] == "未設定試算表 ID，暫停寫入"


def test_標題過遮蔽(book):
    book.title = f"設定本 {SHEET}"
    assert S.sheet_title([SHEET]) == f"設定本 {MASK}"


# ═══════════════════════ 重新取數 ═══════════════════════


class _FakeCached:
    def __init__(self):
        self.cleared = 0

    def cache_clear(self):
        self.cleared += 1


def _vix():
    s = pd.Series([17.0], index=pd.to_datetime(["2026-09-22"]), dtype=float, name="^VIX")
    s.attrs["fetched_at"] = "2026-09-25T06:00:00+00:00"
    return s


def test_要清的只有本次會取數的那一支L1():
    from repositories.macro.yf import fetch_yf_close
    assert S.refetch_cached_functions() == [fetch_yf_close]
    assert hasattr(fetch_yf_close, "cache_clear")


def test_來源沒登記要清哪一支_當場炸(monkeypatch):
    monkeypatch.setattr(S, "_CACHED_FETCHER_BY_SOURCE", {})
    with pytest.raises(KeyError):
        S.refetch_cached_functions()


def test_重新取數_先清那一支的快取_不動來源冷卻_不呼叫全域清除(book, monkeypatch):
    fake = _FakeCached()
    monkeypatch.setattr(S, "_CACHED_FETCHER_BY_SOURCE", {"Yahoo": fake})
    order = []
    monkeypatch.setattr(mi, "fetch_yf_close_with_error",
                        lambda ticker, *a, **k: (order.append(("fetch", fake.cleared)) or (_vix(), None)))
    import infra.cache as IC
    monkeypatch.setattr(IC, "clear_all_caches", lambda *a, **k: pytest.fail("不得呼叫全域清除"))
    SB.record_failure("some.other.host", "server_error")
    assert SB.should_skip("some.other.host")[0] is True
    out = S.refetch_market_indicator([SECRET])
    assert fake.cleared == 1 and order == [("fetch", 1)]          # 先清、後取
    assert SB.should_skip("some.other.host")[0] is True            # 冷卻原封不動
    assert out["persist"]["ok"] is True


def test_重新取數_真的清掉fetch_yf_close的快取(monkeypatch):
    from repositories.macro import yf
    yf.fetch_yf_close._cache_dict[(("^VIX", "2y", "1d"), ())] = (9e18, "舊的")
    monkeypatch.setattr(S, "run_market_indicator_fetch", lambda values, build=None: {"persist": {}, "table": {}})
    S.refetch_market_indicator([SECRET])
    assert (("^VIX", "2y", "1d"), ()) not in yf.fetch_yf_close._cache_dict
