# -*- coding: utf-8 -*-
"""repositories/policy_supplement_repository.py 的單元測試（fast lane；假 gspread，不打網路）。

依據：scratchpad 規格 `alo_sheet_tabs_spec.md`（定稿版）2.1、2.2 節；`49` 6.2 T6、§6.3 N-4。
假物件沿用 tests/_fake_settings_sheet.py（`values_batch_get` 仿 Sheets API 去尾端空格）。
每個測試名前綴標出它守的裁示（T6、R1、U6、U11、C4 …）。
"""

from __future__ import annotations

import secrets as _secrets

import pytest

from _fake_settings_sheet import FakeClient, FakeSpreadsheet, FakeWorksheet
from infra import cache as C
from infra import gspread_retry as GR
from infra import source_backoff as SB
from repositories import policy_supplement_repository as R

MASK = "‹已遮蔽›"
SECRET = "k" + _secrets.token_hex(12)
SHEET = "policy" + _secrets.token_hex(10)       # 現場隨機產生，不落任何真實 ID

HS_HEAD = ["保單編號", "基金代號", "持有起始日", "最後核對日", "類別"]
PP_HEAD = ["保單編號", "保單名稱", "發行單位", "計價幣別", "累計已繳保費（新臺幣元）", "生效日", "狀態"]


def mask(text: str) -> str:
    return text.replace(SECRET, MASK)


class Clock:
    def __init__(self):
        self.mono = 1000.0

    def advance(self, seconds):
        self.mono += seconds


@pytest.fixture
def env(monkeypatch):
    book = FakeSpreadsheet()
    clock = Clock()
    secrets = {"POLICY_SHEET_ID": SHEET,
               "google_service_account": {"client_email": "sa@example.iam.gserviceaccount.com"},
               # 負控：別的試算表 ID 設了也不得被拿去用（T6：不 fallback）
               "macro_weights_sheet_id": "other-book-a", "SHEET_ID": "other-book-b",
               "policy_sheet_id": "other-book-c"}
    monkeypatch.setattr(R, "get_secret", lambda key, default=None: secrets.get(key, default))
    monkeypatch.setattr(R, "_make_client", lambda creds: FakeClient(book))
    monkeypatch.setattr(R, "_clock", lambda: clock.mono)
    monkeypatch.setattr(GR.time, "sleep", lambda _s: None)
    R.clear_cache()
    SB.reset_all()
    yield book, clock, secrets
    R.clear_cache()
    SB.reset_all()


def _put(book, title, rows):
    book.tabs[title] = FakeWorksheet(book, title, rows)


def _hs(*rows):
    return [HS_HEAD] + [list(r) for r in rows]


def _pp(*rows):
    return [PP_HEAD] + [list(r) for r in rows]


# ═══════════════════════ T6：只讀 POLICY_SHEET_ID，沒設就 fail loud ═══════════════════════

@pytest.mark.parametrize("value", [None, "", "   "])
def test_T6_反例_沒設POLICY_SHEET_ID_報錯且不退回別本也不打上游(env, value):
    book, _c, secrets = env
    if value is None:
        secrets.pop("POLICY_SHEET_ID")
    else:
        secrets["POLICY_SHEET_ID"] = value
    with pytest.raises(R.PolicySupplementError) as err:
        R.load_supplement_tabs(mask=mask)
    assert err.value.code == "not_configured"
    assert err.value.details == {"secret_key": "POLICY_SHEET_ID"}
    with pytest.raises(R.PolicySupplementError) as err2:
        R.load_policy_holding_rows(mask=mask)
    assert err2.value.code == "not_configured"
    assert book.calls == []          # 沒有打開任何一本（含 other-book-*）


def test_T6_正例_讀的是POLICY_SHEET_ID那一本(env):
    book, _c, _s = env
    _put(book, R.TAB_HOLDING_SUPPLEMENT, _hs(["PX-TEST-001", "ZZ9999", "2001-01-01", "2001-02-03", ""]))
    R.load_supplement_tabs(mask=mask)
    opened = [c[1] for c in book.calls if c[0] == "open_by_key"]
    assert opened == [SHEET]


def test_沒有服務帳戶_報錯不打上游(env):
    book, _c, secrets = env
    secrets.pop("google_service_account")
    with pytest.raises(R.PolicySupplementError) as err:
        R.load_supplement_tabs(mask=mask)
    assert err.value.code == "no_service_account"
    assert book.calls == []


def test_mask是必填參數():
    with pytest.raises(TypeError):
        R.load_supplement_tabs()  # noqa


# ═══════════════════════ 標頭 ═══════════════════════

def test_標頭_正例_逐字相符且尾端空格不算(env):
    book, _c, _s = env
    _put(book, R.TAB_HOLDING_SUPPLEMENT, [HS_HEAD + ["", ""],
                                          ["PX-TEST-001", "ZZ9999", "2001-01-01", "2001-02-03", "甲"]])
    out = R.load_supplement_tabs(mask=mask)[R.TAB_HOLDING_SUPPLEMENT]
    assert out["tab_missing"] is False and len(out["records"]) == 1


@pytest.mark.parametrize("header", [
    ["保單編號", "基金代號", "持有起始日", "最後對帳時間", "類別"],       # 改字
    ["基金代號", "保單編號", "持有起始日", "最後核對日", "類別"],         # 調換順序
    ["保單編號", "基金代號", "持有起始日", "最後核對日"],                 # 少一欄
    ["保單編號", "基金代號", "持有起始日", "最後核對日", "類別", "備註"],   # 多一欄
    ["保單編號 ", "基金代號", "持有起始日", "最後核對日", "類別"],        # 多餘空白
])
def test_標頭_反例_不符就raise不猜欄位也不改寫(env, header):
    book, _c, _s = env
    _put(book, R.TAB_HOLDING_SUPPLEMENT, [header, ["PX-TEST-001", "ZZ9999", "2001-01-01", "2001-02-03", "甲"]])
    with pytest.raises(R.PolicySupplementError) as err:
        R.load_supplement_tabs(mask=mask)
    assert err.value.code == "header_mismatch"
    assert err.value.details["tab"] == R.TAB_HOLDING_SUPPLEMENT
    assert err.value.details["expected"] == HS_HEAD
    assert book.data(R.TAB_HOLDING_SUPPLEMENT)[0] == header   # 沒被改寫
    assert book.writes() == []


def test_標頭_反例_保單資料標頭不符同樣raise(env):
    book, _c, _s = env
    _put(book, R.TAB_POLICY_PROFILE, [PP_HEAD[:-1] + ["status"]])
    with pytest.raises(R.PolicySupplementError) as err:
        R.load_supplement_tabs(mask=mask)
    assert err.value.code == "header_mismatch"


def test_標頭不符不登記冷卻_修好後立刻讀得到(env):
    book, _c, _s = env
    _put(book, R.TAB_HOLDING_SUPPLEMENT, [["錯"]])
    with pytest.raises(R.PolicySupplementError):
        R.load_supplement_tabs(mask=mask)
    _put(book, R.TAB_HOLDING_SUPPLEMENT, _hs())
    assert R.load_supplement_tabs(mask=mask)[R.TAB_HOLDING_SUPPLEMENT]["tab_missing"] is False


# ═══════════════════════ C4：只讀，不寫 ═══════════════════════

def test_C4_分頁不存在_尚未建立且不建分頁不寫標頭(env):
    book, _c, _s = env
    out = R.load_supplement_tabs(mask=mask)
    assert out[R.TAB_HOLDING_SUPPLEMENT]["tab_missing"] is True
    assert out[R.TAB_POLICY_PROFILE]["tab_missing"] is True
    assert book.writes() == []
    assert R.TAB_HOLDING_SUPPLEMENT not in book.tabs


def test_C4_分頁存在但零列_尚未建立且不代寫標頭(env):
    book, _c, _s = env
    _put(book, R.TAB_POLICY_PROFILE, [])
    out = R.load_supplement_tabs(mask=mask)
    assert out[R.TAB_POLICY_PROFILE]["tab_missing"] is True
    assert book.data(R.TAB_POLICY_PROFILE) == []
    assert book.writes() == []


def test_C4_模組沒有任何寫入函式():
    public = [n for n in dir(R) if not n.startswith("_")]
    for word in ("write", "save", "append", "update", "delete", "put"):
        assert not [n for n in public if word in n.lower()], word


# ═══════════════════════ 儲存格解析（型別層）═══════════════════════

def test_讀取用FORMATTED_VALUE(env):
    book, _c, _s = env
    _put(book, R.TAB_HOLDING_SUPPLEMENT, _hs())
    R.load_supplement_tabs(mask=mask)
    batch = [c for c in book.calls if c[0] == "values_batch_get"]
    assert batch and batch[0][2] == {"valueRenderOption": "FORMATTED_VALUE"}


def test_U11_正例_純數字基金代號以字串交回前導0保留(env):
    book, _c, _s = env
    _put(book, R.TAB_HOLDING_SUPPLEMENT, _hs(["00123", "0050", "2001-01-01", "2001-02-03", ""]))
    rec = R.load_supplement_tabs(mask=mask)[R.TAB_HOLDING_SUPPLEMENT]["records"][0]
    assert rec["fund_code"] == "0050" and rec["policy_id"] == "00123"
    assert isinstance(rec["fund_code"], str)


def test_持倉補充_正例_五欄解析與列號(env):
    book, _c, _s = env
    _put(book, R.TAB_HOLDING_SUPPLEMENT, _hs(
        ["PX-TEST-001", "ZZ9999", "2001-01-01", "2001-02-03", "測試類別甲"],
        ["", "", "", "", ""],
        [" PX-TEST-002 ", "ZZ8888", " 2001-01-02 ", "2001-02-04", ""]))
    out = R.load_supplement_tabs(mask=mask)[R.TAB_HOLDING_SUPPLEMENT]
    assert out["blank_rows"] == 1 and out["bad_rows"] == []
    first, second = out["records"]
    assert first["_row"] == 2 and first["bucket"] == "測試類別甲"
    assert first["last_checked_on"] == "2001-02-03"
    assert second["_row"] == 4 and second["policy_id"] == "PX-TEST-002"   # 只去前後空白
    assert second["opened_on"] == "2001-01-02" and second["bucket"] is None


@pytest.mark.parametrize("cell", [
    "2001/02/03", "2001-2-3", "20010203", "2001-02-03 10:00", "2001-02-03T04:00:00Z",
    "2001-02-30", "2001-13-01", "36925", "２００１-０２-０３", "2001-02-03T10:20:30",
    "2001-02-03T10:20:30+08:00", "民國90-02-03",
])
def test_R1_反例_最後核對日格式錯一律不收並寫出列號與原文(env, cell):
    book, _c, _s = env
    _put(book, R.TAB_HOLDING_SUPPLEMENT, _hs(["PX-TEST-001", "ZZ9999", "2001-01-01", cell, ""]))
    out = R.load_supplement_tabs(mask=mask)[R.TAB_HOLDING_SUPPLEMENT]
    assert out["records"] == []
    (bad,) = out["bad_rows"]
    assert bad["row"] == 2 and "最後核對日" in bad["reason"] and cell in bad["cells"]


@pytest.mark.parametrize("cell", ["2001-01-01", "2000-02-29", "2024-02-29", "2001-12-31"])
def test_R1_正例_合格日期照收(env, cell):
    book, _c, _s = env
    _put(book, R.TAB_HOLDING_SUPPLEMENT, _hs(["PX-TEST-001", "ZZ9999", "2001-01-01", cell, ""]))
    (rec,) = R.load_supplement_tabs(mask=mask)[R.TAB_HOLDING_SUPPLEMENT]["records"]
    assert rec["last_checked_on"] == cell


@pytest.mark.parametrize("cell", ["2001-02-29", "1900-02-29"])
def test_R1_反例_非閏年的2月29日不收(env, cell):
    book, _c, _s = env
    _put(book, R.TAB_HOLDING_SUPPLEMENT, _hs(["PX-TEST-001", "ZZ9999", "2001-01-01", cell, ""]))
    out = R.load_supplement_tabs(mask=mask)[R.TAB_HOLDING_SUPPLEMENT]
    assert out["records"] == [] and len(out["bad_rows"]) == 1


@pytest.mark.parametrize("col", [0, 1, 2, 3])
def test_持倉補充_反例_不可空欄空白該列不收(env, col):
    book, _c, _s = env
    row = ["PX-TEST-001", "ZZ9999", "2001-01-01", "2001-02-03", "甲"]
    row[col] = ""
    _put(book, R.TAB_HOLDING_SUPPLEMENT, _hs(row))
    out = R.load_supplement_tabs(mask=mask)[R.TAB_HOLDING_SUPPLEMENT]
    assert out["records"] == [] and "不可空" in out["bad_rows"][0]["reason"]


def test_持倉補充_反例_超出欄數有值該列不收(env):
    book, _c, _s = env
    _put(book, R.TAB_HOLDING_SUPPLEMENT, _hs(["PX-TEST-001", "ZZ9999", "2001-01-01", "2001-02-03", "", "備註"]))
    out = R.load_supplement_tabs(mask=mask)[R.TAB_HOLDING_SUPPLEMENT]
    assert out["records"] == [] and "超出" in out["bad_rows"][0]["reason"]


def test_保單資料_正例_七欄解析(env):
    book, _c, _s = env
    _put(book, R.TAB_POLICY_PROFILE, _pp(["PX-TEST-001", "測試保單甲", "測試人壽", "USD", "123456",
                                          "2001-01-01", "paid_up"]))
    (rec,) = R.load_supplement_tabs(mask=mask)[R.TAB_POLICY_PROFILE]["records"]
    assert rec["premium_paid_twd"] == 123456 and rec["status"] == "paid_up" and rec["ccy"] == "USD"


@pytest.mark.parametrize("col,cell", [
    (3, "usd"), (3, "US"), (3, "美元"),
    (4, "123,456"), (4, "-1"), (4, "12.5"), (4, "NT$100"), (4, "１２３"),
    (5, "2001/01/01"),
    (6, "Active"), (6, "繳費中"), (6, "lapsed"),
])
def test_保單資料_反例_格式不符該列不收(env, col, cell):
    book, _c, _s = env
    row = ["PX-TEST-001", "測試保單甲", "測試人壽", "USD", "123456", "2001-01-01", "active"]
    row[col] = cell
    _put(book, R.TAB_POLICY_PROFILE, _pp(row))
    out = R.load_supplement_tabs(mask=mask)[R.TAB_POLICY_PROFILE]
    assert out["records"] == [] and len(out["bad_rows"]) == 1


# ═══════════════════════ 失敗處理、遮蔽 ═══════════════════════

def test_遮蔽_上游失敗訊息裡的試算表ID與秘密值都被遮(env):
    book, _c, _s = env
    book.fail_next("open_by_key", PermissionError(f"no access to {SHEET} (ID {SHEET[:12]}…) key={SECRET}"), times=10)
    with pytest.raises(R.PolicySupplementError) as err:
        R.load_supplement_tabs(mask=mask)
    text = str(err.value)
    assert err.value.code == "api"
    assert SHEET not in text and SHEET[:12] not in text and SECRET not in text
    assert SHEET[12:] not in text          # 整串一次換掉，不是只遮掉開頭 12 字
    assert MASK in text
    assert err.value.__cause__ is None and err.value.__context__ is None


def test_遮蔽_標頭不符訊息裡出現的ID也被遮(env):
    book, _c, _s = env
    _put(book, R.TAB_HOLDING_SUPPLEMENT, [[SHEET, "基金代號"]])
    with pytest.raises(R.PolicySupplementError) as err:
        R.load_supplement_tabs(mask=mask)
    assert SHEET not in str(err.value)
    assert SHEET not in "".join(err.value.details["actual"])


def test_遮蔽_未設ID的訊息不含任何別本ID(env):
    _book, _c, secrets = env
    secrets.pop("POLICY_SHEET_ID")
    with pytest.raises(R.PolicySupplementError) as err:
        R.load_supplement_tabs(mask=mask)
    assert "other-book" not in str(err.value)


def test_遮蔽記號與L2的MASK逐字相同():
    from services.v2_tables.masking import MASK as L2_MASK
    assert R.SHEET_ID_MASK == L2_MASK


def test_上游失敗登記冷卻_冷卻中不再打上游(env):
    book, _c, _s = env
    book.fail_next("open_by_key", Exception("APIError: [429]: Quota exceeded for quota metric 'Read requests'"))
    with pytest.raises(R.PolicySupplementError):
        R.load_supplement_tabs(mask=mask)
    before = len(book.calls)
    with pytest.raises(R.PolicySupplementError) as err:
        R.load_supplement_tabs(mask=mask)
    assert err.value.code == "cooling"
    assert len(book.calls) == before


# ═══════════════════════ 快取 ═══════════════════════

def test_快取_成功讀取60秒內不重打_過期才重讀(env):
    book, clock, _s = env
    _put(book, R.TAB_HOLDING_SUPPLEMENT, _hs())
    R.load_supplement_tabs(mask=mask)
    n = len(book.calls)
    R.load_supplement_tabs(mask=mask)
    assert len(book.calls) == n
    clock.advance(61)
    R.load_supplement_tabs(mask=mask)
    assert len(book.calls) > n


def test_快取_失敗不快取(env):
    book, _clock, _s = env
    _put(book, R.TAB_HOLDING_SUPPLEMENT, [["錯"]])
    with pytest.raises(R.PolicySupplementError):
        R.load_supplement_tabs(mask=mask)
    _put(book, R.TAB_HOLDING_SUPPLEMENT, _hs(["PX-TEST-001", "ZZ9999", "2001-01-01", "2001-02-03", ""]))
    assert len(R.load_supplement_tabs(mask=mask)[R.TAB_HOLDING_SUPPLEMENT]["records"]) == 1


def test_快取_登記進CACHE_REGISTRY且全域清除會清掉(env):
    book, _clock, _s = env
    proxies = [f for f in C._CACHE_REGISTRY if getattr(f, "__name__", "") == "_POLICY_SUPPLEMENT_CACHE"]
    assert len(proxies) == 1
    _put(book, R.TAB_HOLDING_SUPPLEMENT, _hs())
    R.load_supplement_tabs(mask=mask)
    assert proxies[0].cache_info()["size"] == 1
    C.clear_all_caches()
    assert proxies[0].cache_info()["size"] == 0


# ═══════════════════════ 保單分頁持倉列（包既有讀取函式）═══════════════════════

def test_保單分頁_讀同一本並轉交略過分頁且遮ID(env, monkeypatch):
    import pandas as pd
    book, _c, _s = env
    seen = {}

    def fake_loader(client, sheet_id):
        seen["sheet_id"] = sheet_id
        df = pd.DataFrame([{"policy_id": "PX-TEST-001", "fund_code": "0050", "invest_twd": 0}])
        return df, [{"tab": "PX-TEST-009", "error": f"APIError: boom {SHEET}"}], [{"row": 2}]

    monkeypatch.setattr(R, "_policy_loader", fake_loader)
    out = R.load_policy_holding_rows(mask=mask)
    assert seen["sheet_id"] == SHEET
    assert out["rows"] == [{"policy_id": "PX-TEST-001", "fund_code": "0050", "invest_twd": 0}]
    assert SHEET not in out["skipped_tabs"][0]["error"] and MASK in out["skipped_tabs"][0]["error"]
    assert out["invest_twd_parse_errors"] == [{"row": 2}]
    assert [c for c in book.calls if c[0] == "open_by_key"] == []   # 不多開一次


def test_保單分頁_整本打不開轉成api錯誤且遮ID(env, monkeypatch):
    _book, _c, _s = env

    def boom(client, sheet_id):
        raise RuntimeError(f"列保單分頁失敗：PermissionError (ID {sheet_id[:12]}…)")

    monkeypatch.setattr(R, "_policy_loader", boom)
    with pytest.raises(R.PolicySupplementError) as err:
        R.load_policy_holding_rows(mask=mask)
    assert err.value.code == "api" and SHEET[:12] not in str(err.value)


def test_保單分頁_numpy整數轉成Python原生型別(env, monkeypatch):
    import numpy as np
    import pandas as pd
    df = pd.DataFrame({"policy_id": ["PX-TEST-001"], "invest_twd": np.array([300000], dtype="int64"),
                       "units": np.array([1.5])})
    monkeypatch.setattr(R, "_policy_loader", lambda client, sid: (df, [], []))
    (row,) = R.load_policy_holding_rows(mask=mask)["rows"]
    assert type(row["invest_twd"]) is int and type(row["units"]) is float
