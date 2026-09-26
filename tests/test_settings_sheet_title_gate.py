# -*- coding: utf-8 -*-
"""settings_sheet_repository 為 set 頁正式模式補的三件事（fast lane；假 gspread，不打網路）：

1. `load_sheet_title`：試算表標題（線框草稿 ★10）。取自打開試算表那一次呼叫，不另加一次讀取；
   沒記到才自己打開一次，走 `_run`（冷卻、失敗登記、遮蔽照舊）。
2. `gate_status`：寫入閘門（不打上游）—— 缺 ID／缺服務帳戶／冷卻中／可寫。
3. 上游失敗時 `details["client_email"]`（`50` 第 8 節 404 提示用；ACCEPTANCE 7.2 丙不遮）。
"""

from __future__ import annotations

import secrets as _secrets

import pytest

from _fake_settings_sheet import FakeClient, FakeSpreadsheet
from infra import gspread_retry as GR
from infra import source_backoff as SB
from repositories import settings_sheet_repository as R

MASK = "‹已遮蔽›"
SECRET = "k" + _secrets.token_hex(12)
SHEET = "sheet-" + _secrets.token_hex(6)


def mask(text: str) -> str:
    return text.replace(SECRET, MASK).replace(SHEET, MASK)


class TitledSpreadsheet(FakeSpreadsheet):
    def __init__(self, title="客戶的設定本", **kw):
        super().__init__(**kw)
        self._title = title

    @property
    def title(self):
        self.calls.append(("title",))
        return self._title


@pytest.fixture
def env(monkeypatch):
    book = TitledSpreadsheet()
    secrets = {"SETTINGS_SHEET_ID": SHEET,
               "google_service_account": {"client_email": "sa@example.iam.gserviceaccount.com"}}
    monkeypatch.setattr(R, "get_secret", lambda key, default=None: secrets.get(key, default))
    monkeypatch.setattr(R, "_make_client", lambda creds: FakeClient(book))
    monkeypatch.setattr(R, "_TITLES", {})
    monkeypatch.setattr(GR.time, "sleep", lambda _s: None)
    R.clear_cache()
    SB.reset_all()
    yield book, secrets
    R.clear_cache()
    SB.reset_all()


def _opens(book):
    return [c for c in book.calls if c[0] == "open_by_key"]


def test_標題取自讀設定那一次打開_不另加一次打開(env):
    book, _s = env
    R.load_user_settings(mask=mask)
    assert len(_opens(book)) == 1
    assert R.load_sheet_title(mask=mask) == "客戶的設定本"
    assert len(_opens(book)) == 1          # 沒有為了標題再打開一次


def test_沒記到標題時自己打開一次(env):
    book, _s = env
    assert R.load_sheet_title(mask=mask) == "客戶的設定本"
    assert len(_opens(book)) == 1
    assert R.load_sheet_title(mask=mask) == "客戶的設定本"
    assert len(_opens(book)) == 1          # 第二次用記下的


def test_讀標題失敗_訊息過遮蔽_登記冷卻_不帶出原例外(env):
    book, _s = env
    book.fail_next("open_by_key", Exception(f"APIError: [404]: https://docs.google.com/spreadsheets/d/{SHEET} key={SECRET}"),
                   times=4)
    with pytest.raises(R.SettingsSheetError) as err:
        R.load_sheet_title(mask=mask)
    text = str(err.value)
    assert SHEET not in text and SECRET not in text and MASK in text
    assert err.value.__cause__ is None and err.value.__context__ is None
    assert err.value.details["client_email"] == "sa@example.iam.gserviceaccount.com"
    assert R.gate_status(mask=mask)["state"] == "cooling"   # 沿用冷卻機制
    before = len(book.calls)
    with pytest.raises(R.SettingsSheetError) as again:
        R.load_sheet_title(mask=mask)
    assert again.value.code == "cooling" and len(book.calls) == before   # 冷卻中不打上游


def test_標題為空視為讀不到(env):
    book, _s = env
    book._title = ""
    with pytest.raises(R.SettingsSheetError) as err:
        R.load_sheet_title(mask=mask)
    assert err.value.code == "api" and "試算表標題為空" in str(err.value)


def test_沒設ID_標題與閘門都是同一句(env):
    _book, secrets = env
    secrets.pop("SETTINGS_SHEET_ID")
    with pytest.raises(R.SettingsSheetError) as err:
        R.load_sheet_title(mask=mask)
    assert err.value.code == "not_configured" and str(err.value) == "未設定試算表 ID，暫停寫入"
    assert R.gate_status(mask=mask) == {"state": "not_configured", "message": "未設定試算表 ID，暫停寫入",
                                        "remaining_sec": None}


def test_閘門_缺服務帳戶_可寫_都不打上游(env):
    book, secrets = env
    assert R.gate_status(mask=mask)["state"] == "ok"
    secrets.pop("google_service_account")
    gate = R.gate_status(mask=mask)
    assert gate["state"] == "no_service_account" and gate["message"] == R.NO_SERVICE_ACCOUNT_MESSAGE
    assert book.calls == []


def test_閘門_冷卻中帶剩餘秒數(env):
    book, _s = env
    book.fail_next("open_by_key", Exception("APIError: [429]: Quota exceeded"), times=4)
    with pytest.raises(R.SettingsSheetError):
        R.load_user_settings(mask=mask)
    gate = R.gate_status(mask=mask)
    assert gate["state"] == "cooling" and gate["remaining_sec"] > 0
    assert gate["message"].startswith("設定試算表暫停重試，還剩 ")
