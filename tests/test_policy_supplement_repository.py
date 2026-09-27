# -*- coding: utf-8 -*-
"""repositories/policy_supplement_repository.py 的單元測試（fast lane；假 gspread，不打網路）。

依據：scratchpad 規格 `alo_sheet_tabs_spec.md`（定稿版）2.1、2.2 節；`49` 6.2 T6、§6.3 N-4。
假物件沿用 tests/_fake_settings_sheet.py（`values_batch_get` 仿 Sheets API 去尾端空格）。
每個測試名前綴標出它守的裁示（T6、R1、U6、U11、C4 …）。
"""

from __future__ import annotations

import pathlib
import secrets as _secrets

import pytest

from _fake_settings_sheet import FakeClient, FakeSpreadsheet, FakeWorksheet
from infra import cache as C
from infra import gspread_retry as GR
from infra import source_backoff as SB
from repositories import policy_supplement_repository as R

MASK = "‹已遮蔽›"
def _random_without_429(prefix: str, nbytes: int) -> str:
    """現場隨機產生（ACCEPTANCE 7.5），但排除含「429」的值（第 7 輪 1）：
    共用的 `is_quota_error` 以字串比對「429」，隨機值碰巧含它時約 1% 的機率造成隨機紅燈。"""
    while True:
        value = prefix + _secrets.token_hex(nbytes)
        if "429" not in value:
            return value


SECRET = _random_without_429("k", 12)
SHEET = _random_without_429("policy", 10)       # 不落任何真實 ID

HS_HEAD = ["保單編號", "基金代號", "持有起始日", "最後核對日", "類別"]
PP_HEAD = ["保單編號", "保單名稱", "發行單位", "計價幣別", "累計已繳保費（新臺幣元）", "生效日", "狀態"]


def _api_error(status: int, msg: str = "boom"):
    """帶真實 HTTP 狀態碼的 gspread APIError（仿 tests/test_gspread_source_backoff.py::_api_error）。"""
    import requests
    from gspread.exceptions import APIError
    response = requests.Response()
    response.status_code = status
    response._content = ('{"error":{"code":%d,"message":"%s","status":"X"}}' % (status, msg)).encode()
    return APIError(response)


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
    monkeypatch.setattr(SB, "_clock", lambda: clock.mono)      # 分頁短冷卻與配額冷卻走同一個測試時鐘
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


# ═══════════════════════ 失敗處理、遮蔽（第 2 輪：ID 不遮，`ACCEPTANCE.md` 7.2 丙）═══════════════════════

def test_遮蔽_上游失敗訊息_試算表ID原樣保留_秘密值被遮(env):
    book, _c, _s = env
    book.fail_next("open_by_key", PermissionError(f"no access to {SHEET} (ID {SHEET[:12]}…) key={SECRET}"),
                   times=10)
    with pytest.raises(R.PolicySupplementError) as err:
        R.load_supplement_tabs(mask=mask)
    text = str(err.value)
    assert err.value.code == "api"
    assert SHEET in text                        # 7.2 丙：POLICY_SHEET_ID 不遮
    assert SECRET not in text and MASK in text  # 秘密值照舊交給呼叫端的 mask
    assert err.value.__cause__ is None and err.value.__context__ is None


def test_遮蔽_標頭不符訊息_ID原樣保留_秘密值被遮(env):
    book, _c, _s = env
    _put(book, R.TAB_HOLDING_SUPPLEMENT, [[SHEET, SECRET]])
    with pytest.raises(R.PolicySupplementError) as err:
        R.load_supplement_tabs(mask=mask)
    assert SHEET in str(err.value) and SECRET not in str(err.value)
    assert err.value.details["actual"] == [SHEET, MASK]


def test_遮蔽_未設ID的訊息不含任何別本ID(env):
    _book, _c, secrets = env
    secrets.pop("POLICY_SHEET_ID")
    with pytest.raises(R.PolicySupplementError) as err:
        R.load_supplement_tabs(mask=mask)
    assert "other-book" not in str(err.value)


def test_遮蔽_本檔不再自帶ID遮蔽():
    assert not hasattr(R, "_hide_id") and not hasattr(R, "SHEET_ID_MASK")


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


def test_快取_換一本POLICY_SHEET_ID不會讀到舊本(env, monkeypatch):
    book, _clock, secrets = env
    _put(book, R.TAB_HOLDING_SUPPLEMENT, _hs(["PX-TEST-001", "ZZ9999", "2001-01-01", "2001-02-03", ""]))
    assert len(R.load_supplement_tabs(mask=mask)[R.TAB_HOLDING_SUPPLEMENT]["records"]) == 1
    other = FakeSpreadsheet()                      # 第二本：分頁不存在
    books = {SHEET: book, SHEET + "-second": other}

    class Router:
        def open_by_key(self, key):
            return FakeClient(books[key]).open_by_key(key)

    monkeypatch.setattr(R, "_make_client", lambda creds: Router())
    secrets["POLICY_SHEET_ID"] = SHEET + "-second"
    out = R.load_supplement_tabs(mask=mask)[R.TAB_HOLDING_SUPPLEMENT]
    assert out["tab_missing"] is True and out["records"] == []
    assert ("open_by_key", SHEET + "-second") in other.calls


def test_快取_命中時交副本_呼叫端改不到快取(env):
    book, _clock, _s = env
    _put(book, R.TAB_HOLDING_SUPPLEMENT, _hs(["PX-TEST-001", "ZZ9999", "2001-01-01", "2001-02-03", "甲"]))
    first = R.load_supplement_tabs(mask=mask)
    first[R.TAB_HOLDING_SUPPLEMENT]["records"][0]["bucket"] = "被改掉"
    first[R.TAB_HOLDING_SUPPLEMENT]["records"].clear()
    second = R.load_supplement_tabs(mask=mask)
    second[R.TAB_HOLDING_SUPPLEMENT]["records"][0]["bucket"] = "又被改"
    third = R.load_supplement_tabs(mask=mask)
    assert third[R.TAB_HOLDING_SUPPLEMENT]["records"][0]["bucket"] == "甲"


def test_快取登記_reload後只有一份且清得到新模組的快取():
    """在子行程裡真的 reload（同一行程 reload 會換掉例外類別，污染其他測試）。"""
    import subprocess
    import sys
    code = (
        "import importlib\n"
        "from infra import cache as C\n"
        "import repositories.policy_supplement_repository as R\n"
        "n = lambda m: sum(1 for f in C._CACHE_REGISTRY if m._registry_name(f) == m.CACHE_PROXY_NAME)\n"
        "assert n(R) == 1, n(R)\n"
        "M = importlib.reload(R)\n"
        "assert n(M) == 1, n(M)\n"
        "M._CACHE[('x', 'y')] = (0.0, {})\n"
        "C.clear_all_caches()\n"
        "assert M._CACHE == {}, M._CACHE\n"
        "print('ok')\n"
    )
    root = pathlib.Path(__file__).resolve().parents[1]
    done = subprocess.run([sys.executable, "-c", code], cwd=root, capture_output=True, text=True)
    assert done.returncode == 0 and done.stdout.strip().endswith("ok"), done.stderr[-2000:]


def test_快取登記_同名舊登記會被換掉(monkeypatch):
    class Stale:
        cleared = False

        def cache_clear(self):
            Stale.cleared = True

        def cache_info(self):
            return {"name": R.CACHE_PROXY_NAME, "size": 0}

    monkeypatch.setattr(C, "_CACHE_REGISTRY", list(C._CACHE_REGISTRY) + [Stale()])
    R._register_cache_proxy()
    entries = [f for f in C._CACHE_REGISTRY if R._registry_name(f) == R.CACHE_PROXY_NAME]
    assert len(entries) == 1 and not isinstance(entries[0], Stale)


def test_快取登記_名稱比對看實例():
    (entry,) = [f for f in C._CACHE_REGISTRY if R._registry_name(f) == R.CACHE_PROXY_NAME]
    assert entry.cache_info()["name"] == "_POLICY_SUPPLEMENT_CACHE"
    assert R._registry_name(object()) == ""


# ═══════════════════════ 保單分頁持倉列 ═══════════════════════

from gspread.worksheet import Worksheet as _GspreadWorksheet  # noqa: E402


class FakePolicyTab(_GspreadWorksheet):
    """假保單分頁：**用 gspread 真的 `Worksheet.get_all_records`**，只替換它底下的 `.get`
    （第 4 輪 A-5）。`__init__` 沒走 gspread 的（它要真的 HTTP client），只放 `title` 需要的 `_properties`。
    `.get` 照 `pad_values=True` 的語意把每列補齊到最寬那一列；空表回 `[[]]`（gspread 自己的空表形狀）。"""

    def __init__(self, title, rows):  # noqa: D401 —— 刻意不呼叫 super().__init__
        self._properties = {"title": title, "sheetId": 0, "index": 0}
        self.rows = rows
        self.calls = 0

    def get(self, *args, **kwargs):
        self.calls += 1
        width = max((len(r) for r in self.rows), default=0)
        return [list(r) + [""] * (width - len(r)) for r in self.rows] or [[]]


class FakePolicyBook:
    def __init__(self, tabs):
        self.tabs = tabs
        self.fail = {}          # 方法名 → 還要失敗幾次（用 ConnectionError 模擬 5xx／連線層）
        self.calls = []

    def _maybe_fail(self, name):
        self.calls.append(name)
        if self.fail.get(name, 0) > 0:
            self.fail[name] -= 1
            raise ConnectionError(f"{name}: 503 backend unavailable")

    def open_by_key(self, key):
        self._maybe_fail("open_by_key")
        return self

    def worksheets(self):
        self._maybe_fail("worksheets")
        return self.tabs


def _good_tab(title="PX-TEST-002"):
    return FakePolicyTab(title, [POLICY_HEAD,
        [title, "ZZ9999", "測試基金甲", "USD", "", "1", "", "1", "1", ""]])


POLICY_HEAD = ["保單編號", "基金代號", "基金名稱", "幣別", "級別", "淨投資金額", "現金給付%",
               "持有單位數", "平均買入單位成本", "平均買入匯率"]


@pytest.fixture
def policy_env(env, monkeypatch):
    book, clock, secrets = env
    holder = {}
    monkeypatch.setattr(R, "_make_client", lambda creds: holder["book"])
    return holder, clock, secrets


def test_保單分頁_真的讀取函式_每列帶分頁名與列號_本金空白與解析失敗分開(policy_env):
    holder, _c, _s = policy_env
    holder["book"] = FakePolicyBook([
        FakePolicyTab("_持倉補充", [["x"]]),                       # 底線分頁不讀
        FakePolicyTab("PX-TEST-001", [POLICY_HEAD,
                                     ["PX-TEST-001", "ZZ9999", "測試基金甲", "USD", "", "300,000", "", "1000", "10", "30"],
                                     ["", "", "", "", "", "", "", "", "", ""],
                                     ["PX-TEST-001", "ZZ8888", "測試基金乙", "USD", "", "", "", "1", "1", ""],
                                     ["PX-TEST-001", "ZZ7777", "測試基金丙", "USD", "", "NT$1,000", "", "1", "1", ""]]),
    ])
    out = R.load_policy_holding_rows(mask=mask)
    rows = out["rows"]
    assert [(r["_tab"], r["_row"]) for r in rows] == [("PX-TEST-001", n) for n in (2, 3, 4, 5)]
    assert rows[0]["invest_twd"] == 300000 and type(rows[0]["invest_twd"]) is int
    assert rows[2]["invest_twd"] is None                       # 空白 → None，不是 0
    assert rows[3]["invest_twd"] is None
    assert out["invest_twd_parse_errors"] == [
        {"tab": "PX-TEST-001", "row": 5, "raw": "NT$1,000",
         "reason": "只收整數（千分位須三位一組、小數部分只能是 0、不收科學記號或其他字元）（原始值：NT$1,000）"}]


def test_U11_真的讀取函式_純數字保單編號與代號被轉成數字_L2擋下並寫明原因(policy_env):
    from services.v2_tables import alo_holdings as A
    holder, _c, _s = policy_env
    holder["book"] = FakePolicyBook([FakePolicyTab("12345", [POLICY_HEAD,
        ["12345", "0050", "測試基金甲", "TWD", "", "300000", "", "1000", "10", ""]])])
    rows = R.load_policy_holding_rows(mask=mask)["rows"]
    assert rows[0]["policy_id"] == 12345 and rows[0]["fund_code"] == 50   # numericise 的結果，前導 0 已失
    empty = {"records": [], "bad_rows": [], "blank_rows": 0, "tab_missing": False}
    sup = {"_row": 2, "_raw": (), "policy_id": "12345", "fund_code": "0050", "opened_on": "2001-01-01",
           "last_checked_on": "2001-02-03", "bucket": None}
    out = A.build_alo_tables(rows, {R.TAB_HOLDING_SUPPLEMENT: dict(empty, records=[sup]),
                                    R.TAB_POLICY_PROFILE: empty})
    assert out["holding"] == []
    (skip,) = out["skipped_holdings"]
    assert skip["tab"] == "12345" and skip["row"] == 2
    assert "前導 0" in skip["reasons"][0]


def test_保單分頁_單一分頁讀失敗_略過並交出分頁名_ID不遮秘密值遮_整頁結果不快取(policy_env):
    holder, _c, _s = policy_env

    class Broken(FakePolicyTab):
        def get_all_records(self, **_kw):
            self.calls += 1
            raise ValueError(f"boom {SHEET} {SECRET}")

    broken = Broken("PX-TEST-009", [])
    holder["book"] = FakePolicyBook([broken, _good_tab()])
    out = R.load_policy_holding_rows(mask=mask)
    (sk,) = out["skipped_tabs"]
    assert sk["tab"] == "PX-TEST-009" and SHEET in sk["error"] and SECRET not in sk["error"]
    assert len(out["rows"]) == 1
    again = R.load_policy_holding_rows(mask=mask)          # 整頁結果不快取；壞分頁進 60 秒短冷卻（第 7 輪 2）
    (sk2,) = again["skipped_tabs"]
    assert sk2["error"].startswith("冷卻中（還剩 60 秒），上次失敗：ValueError: boom")
    assert SECRET not in sk2["error"] and broken.calls == 1


def test_保單分頁_整本打不開轉成api錯誤(policy_env, monkeypatch):
    def boom(client, sheet_id):
        raise RuntimeError(f"列保單分頁失敗：PermissionError (ID {sheet_id[:12]}…) {SECRET}")

    monkeypatch.setattr(R, "_policy_loader", boom)
    with pytest.raises(R.PolicySupplementError) as err:
        R.load_policy_holding_rows(mask=mask)
    assert err.value.code == "api" and SECRET not in str(err.value)


def test_保單分頁_快取命中交副本_換本不讀舊本(policy_env):
    holder, _c, secrets = policy_env
    holder["book"] = FakePolicyBook([FakePolicyTab("PX-TEST-001", [POLICY_HEAD,
        ["PX-TEST-001", "ZZ9999", "測試基金甲", "USD", "", "1", "", "1", "1", ""]])])
    first = R.load_policy_holding_rows(mask=mask)
    first["rows"][0]["fund_code"] = "被改掉"
    assert R.load_policy_holding_rows(mask=mask)["rows"][0]["fund_code"] == "ZZ9999"
    holder["book"] = FakePolicyBook([])
    secrets["POLICY_SHEET_ID"] = SHEET + "-second"
    assert R.load_policy_holding_rows(mask=mask)["rows"] == []


def test_numpy純量轉原生型別():
    import numpy as np
    assert type(R._native(np.int64(3))) is int and type(R._native(np.float64(1.5))) is float
    assert R._native("x") == "x"


# ═══════════════════════ 第 3 輪 ═══════════════════════

def _eq_book():
    from repositories.policy.v2 import ALL_COLS_V2, ZH_HEADERS_V2
    zh = [ZH_HEADERS_V2[c] for c in ALL_COLS_V2]
    en = list(ALL_COLS_V2)

    class Broken(FakePolicyTab):
        def get_all_records(self, **_kw):
            raise RuntimeError("boom")

    v2zh = [zh,
            ["PX-1", "ZZ9999", "基金甲", "USD", "core", "300,000", "80", "1,234.5", "10.2", "30.1"],
            ["PX-1", "0050", "基金乙", "TWD", "", "", "", "", "", ""],
            ["PX-1", "AB1", "基金丙", "USD", "satellite", "NT$1,000", "abc", "x", "", ""],
            ["", "", "", "", "", "", "", "", "", ""],
            ["12345678", "ZZ1", "基金丁", "USD", "core", "1000.9", "150", "5", "1", "1"],
            ["PX-1", "ZZ2", "基金戊", "USD", "core", "1e3", "", "1", "1", ""],
            ["PX-1", "ZZ3", "基金己", "USD", "core", "0", "", "1", "1", ""],
            ["PX-1", "ZZ4", "基金庚", "USD", "core", "1,00,0", "", "1", "1", ""],          # B-D 分組錯
            ["PX-1", "ZZ5", "基金辛", "USD", "core", "1" + "0" * 18, "", "1", "1", ""],    # B-D 19 位
            ["PX-1", "ZZ6", "基金壬", "USD", "core", "1,000.00", "", "1", "1", ""]]        # B-C 兩路都 1000
    v2en = [en, ["PX-2", "EN1", "英文基金", "USD", "core", "500", "100", "1", "1", "1"]]
    both = [zh + ["invest_twd"],                                                          # B-E 兩個本金標頭並存
            ["PX-5", "BO1", "雙欄基金", "USD", "core", "111", "", "1", "1", "", "222"]]
    legacy = [zh[:4] + ["類型", "平均買入含息單位成本", "金額"] + zh[4:],
              ["PX-3", "LG1", "舊基金", "USD", "fund", "9", "8", "core", "700", "50", "2", "3", "4"]]
    v1 = [["policy_id", "fund_url", "invest_date", "currency", "invest_twd", "policy_tier", "fx_avg",
           "units", "avg_nav", "notes"],
          ["PX-4", "https://www.moneydj.com/funddj/ya/yp010000.djhtm?a=ACTI71", "2020-01-01", "USD",
           "1000", "core", "31", "2", "3", ""],
          ["fund_url", "fund_url", "invest_date", "currency", "", "", "", "", "", ""],   # 鬼列
          ["PX-4", "ZZ7", "2020-01-01", "TWD", "", "satellite", "", "", "", ""]]
    return FakePolicyBook([
        FakePolicyTab("甲", v2zh), FakePolicyTab("乙", v2en), FakePolicyTab("丙", legacy),
        FakePolicyTab("戊", both),
        FakePolicyTab("丁", v1), Broken("壞分頁", []), FakePolicyTab("_持倉補充", [["x"], ["y"]]),
        FakePolicyTab("Policies", [en, ["PX-9"] + [""] * 9]), FakePolicyTab("空", [en])])


def _assert_equivalent(new_loader):
    import math

    from repositories.policy.v2 import ALL_COLS_V2, load_all_policies_v2_with_error
    book = _eq_book()
    df, old_skipped = load_all_policies_v2_with_error(book, "sid", cache_user=None)
    old = [{k: R._native(v) for k, v in r.items()} for r in df.to_dict(orient="records")]
    new, new_skipped, parse_errors, _tab_count, _read_ok = new_loader(book, "sid")
    assert [t["tab"] for t in old_skipped] == [t["tab"] for t in new_skipped] == ["壞分頁"]
    assert len(old) == len(new) == 15
    assert [r["_tab"] for r in new] == ["甲"] * 10 + ["乙", "丙", "戊", "丁", "丁"]
    assert [r["invest_twd"] for r in new if r["_tab"] == "戊"] == [222]      # B-E：英文欄優先，與舊路同
    assert [r["_row"] for r in new if r["_tab"] == "丁"] == [2, 4]   # 鬼列被濾掉，列號照舊
    failed = {(e["tab"], e["row"]) for e in parse_errors}
    invest_diffs = []
    for o, n in zip(old, new):
        for col in ALL_COLS_V2:
            a, b = o[col], n[col]
            same = (a == b and type(a) is type(b)) or (
                isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b))
            if same:
                continue
            assert col == "invest_twd", (n["_tab"], n["_row"], col, a, b)
            # 刻意差異只有兩種：空白（舊 0 → 新 None）；解析失敗（新 None，且列在清單上）
            assert b is None, (n["_tab"], n["_row"], a, b)
            assert a == 0 or (n["_tab"], n["_row"]) in failed, (n["_tab"], n["_row"], a)
            invest_diffs.append((n["_tab"], n["_row"]))
    # 刻意差異逐格說明（其餘每一格兩路完全相同）：
    #   甲3 空白（舊 0 → 新 None）；甲4 `NT$1,000`（兩路都解析失敗，舊記 0 → 新 None）；
    #   甲5 整列空白（舊 0 → 新 None）；甲6 `1000.9`（舊捨去成 1000 → 新拒收，第 3 輪裁定 5）；
    #   甲7 `1e3`（舊 1000 → 新拒收，第 3 輪裁定 5）；甲9 `1,00,0`（舊刪逗號成 1000 → 新拒收，第 4 輪 B-D）；
    #   甲10 19 位數（舊照收 → 新拒收，第 4 輪 B-D）；丁4 空白（舊 0 → 新 None）。
    #   甲8 `0` 兩路都 0；甲11 `1,000.00` 兩路都 1000（第 4 輪 B-C）；戊2 兩欄並存兩路都取英文欄 222（B-E）。
    assert sorted(invest_diffs) == sorted([("甲", 3), ("甲", 4), ("甲", 5), ("甲", 6), ("甲", 7),
                                           ("甲", 9), ("甲", 10), ("丁", 4)])
    assert sorted(failed) == [("甲", 4), ("甲", 6), ("甲", 7), ("甲", 9), ("甲", 10)]


def test_第3輪裁定1_等價鎖定_新舊兩條讀取路徑逐列逐欄相同_只差本金欄的刻意差異():
    """`P-POLICYREADDUPE-1`：兩條路重複約 25 行。任一邊改了欄名對映或分頁過濾而另一邊沒改，這裡轉紅。
    涵蓋：v2 中文標頭、英文標頭、舊中文別名（13 欄分頁）、兩個本金標頭並存、v1 分頁、鬼列、
    讀取失敗分頁、`_` 開頭分頁、`Policies` 分頁、只有標頭的空分頁。假分頁用 gspread 真的 `get_all_records`。"""
    _assert_equivalent(R._default_policy_loader)


@pytest.mark.parametrize("mutate", ["drop_row", "rename_value", "extra_tab_filter"])
def test_第3輪裁定1_等價鎖定的負控_新路任一處走樣就轉紅(mutate):
    def loader(book, sid):
        rows, skipped, errors, count, read_ok = R._default_policy_loader(book, sid)
        if mutate == "drop_row":
            rows = rows[:-1]
        elif mutate == "rename_value":
            rows[0] = dict(rows[0], fund_name="走樣")
        else:
            rows = [r for r in rows if r["_tab"] != "乙"]
        return rows, skipped, errors, count, read_ok

    with pytest.raises(AssertionError):
        _assert_equivalent(loader)


def test_第3輪裁定3_分頁持續429_連跑會進入冷卻_不會每次都打上游(policy_env):
    holder, _c, _s = policy_env

    class Quota(FakePolicyTab):
        def get_all_records(self, **_kw):
            self.calls += 1
            raise _api_error(429, f"Quota exceeded for quota metric 'Read requests' {SECRET}")

    tab = Quota("PX-TEST-001", [])
    holder["book"] = FakePolicyBook([_good_tab(), tab])   # 好分頁先讀；429 之後的分頁不讀（第 8 輪 2）
    reached, cooling = 0, 0
    for _ in range(21):
        try:
            R.load_policy_holding_rows(mask=mask)
            reached += 1
        except R.PolicySupplementError as err:
            assert err.code == "cooling"
            cooling += 1
            # 第 6 輪 B 組 3：冷卻訊息附最後一次被略過的分頁名與原因（經 mask）
            assert "最後一次被略過的分頁：PX-TEST-001" in str(err) and "429" in str(err)
            assert SECRET not in str(err) and MASK in str(err)
    assert reached <= 3 and cooling >= 18, (reached, cooling)
    assert SB.should_skip(GR.quota_key(R.ACTOR))[0]                    # 429 → 配額鑰匙
    assert not SB.should_skip(GR.sheet_key(R.ACTOR, SHEET))[0]          # 不另登記 sheet 冷卻


def test_第3輪裁定3_部分分頁失敗不解除既有冷卻(policy_env, monkeypatch):
    holder, _c, _s = policy_env
    called = []
    monkeypatch.setattr(GR, "record_gspread_success", lambda *a: called.append(a))

    class Broken(FakePolicyTab):
        def get_all_records(self, **_kw):
            raise ValueError("boom")

    holder["book"] = FakePolicyBook([Broken("PX-TEST-009", []), _good_tab()])
    R.load_policy_holding_rows(mask=mask)
    assert called == []
    _c.advance(60)     # 分頁清單快取 60 秒
    holder["book"] = FakePolicyBook([_good_tab()])
    R.load_policy_holding_rows(mask=mask)
    assert len(called) == 1                      # 全部分頁都讀到才算成功


def test_第3輪裁定4_open_by_key與worksheets遇5xx會重試(policy_env):
    holder, _c, _s = policy_env
    book = FakePolicyBook([FakePolicyTab("PX-TEST-001", [POLICY_HEAD,
        ["PX-TEST-001", "ZZ9999", "測試基金甲", "USD", "", "1", "", "1", "1", ""]])])
    book.fail = {"open_by_key": 1, "worksheets": 1}
    holder["book"] = book
    out = R.load_policy_holding_rows(mask=mask)
    assert len(out["rows"]) == 1
    assert book.calls.count("open_by_key") == 2 and book.calls.count("worksheets") == 2


# ⚠️ 第 4 輪總管裁定 B-C 改寫本測試：「小數部分全為 0」（`1000.0`、`1,000.00`）改為接受 → 1000；
#    其餘小數照舊拒收。第 3 輪原本把 `1000.0` 釘成拒收（有意識的更正，不是漏刪；決策者 AI 總管）。
# 第 4 輪 B-D 另加：千分位分組不合法、超過 18 位數 → 解析失敗。
@pytest.mark.parametrize("text,expected", [
    ("1,000.7", None), ("1000.5", None), ("1e3", None), ("1E3", None), ("1000.01", None),
    ("1000.0", 1000), ("1,000.00", 1000), ("1000.000", 1000),
    ("1,000", 1000), ("12,345,678", 12345678), ("300000", 300000), (" 42 ", 42), ("-5", -5),
    ("", None), ("   ", None),
    ("1,00,0", None), (",1000", None), ("1000,", None), ("1,0000", None), ("10,00", None),
    ("1000.", None), (".0", None), ("１０００", None),
    ("9" * 18, int("9" * 18)), ("9" * 19, None), ("0" + "9" * 18, int("9" * 18)),
    ("999,999,999,999,999,999", int("9" * 18)), ("1,000,000,000,000,000,000", None),
])
def test_第3輪裁定5_本金小數與科學記號列為解析失敗_不捨去(text, expected):
    value, reason = R._invest_twd_from_text(text)
    assert value == expected
    if text.strip() and expected is None:
        assert reason is not None and text in reason     # 原文，不截斷
    else:
        assert reason is None


def test_第3輪裁定5_原文不截斷(policy_env):
    holder, _c, _s = policy_env
    raw = "1000." + "5" * 60
    holder["book"] = FakePolicyBook([FakePolicyTab("PX-TEST-001", [POLICY_HEAD,
        ["PX-TEST-001", "ZZ9999", "測試基金甲", "USD", "", raw, "", "1", "1", ""]])])
    (err,) = R.load_policy_holding_rows(mask=mask)["invest_twd_parse_errors"]
    assert err["raw"] == raw and raw in err["reason"]


def test_第3輪裁定6_空白列旗標只看每一欄都空白(policy_env):
    holder, _c, _s = policy_env
    holder["book"] = FakePolicyBook([FakePolicyTab("PX-TEST-001", [POLICY_HEAD,
        [""] * 10, ["", "", "測試基金甲", "", "", "", "", "", "", ""]])])
    rows = R.load_policy_holding_rows(mask=mask)["rows"]
    assert [r["_blank"] for r in rows] == [True, False]


def test_第3輪裁定7_標頭重複_轉成中文且保留例外類別名稱(policy_env):
    holder, _c, _s = policy_env
    holder["book"] = FakePolicyBook([FakePolicyTab("PX-TEST-001", [["保單編號", "保單編號"], ["a", "b"]]),
                                     _good_tab()])
    (sk,) = R.load_policy_holding_rows(mask=mask)["skipped_tabs"]
    assert sk["error"] == "GSpreadException: 第 1 列不是標頭，或標頭有空白或重複的欄位"
    assert "expected_headers" not in sk["error"]


def test_第3輪裁定7_反例_其他例外照原文():
    assert R._tab_error_text(ValueError("x y")) == "ValueError: x y"


# ═══════════════════════ 第 4 輪 ═══════════════════════

def _bad_and_good_book():
    bad = FakePolicyTab("PX-TEST-001", [["保單編號", "保單編號"], ["a", "b"]])     # 永久性錯誤
    good = FakePolicyTab("PX-TEST-002", [POLICY_HEAD,
        ["PX-TEST-002", "ZZ9999", "測試基金甲", "USD", "", "1", "", "1", "1", ""]])
    return bad, good


def test_第7輪_永久壞分頁連跑_每次都有好分頁資料與壞分頁原因_壞分頁60秒內只讀1次(policy_env):
    holder, clock, _s = policy_env
    bad, good = _bad_and_good_book()
    holder["book"] = FakePolicyBook([bad, good])
    for _ in range(12):                       # 0、20、40 … 220 秒
        out = R.load_policy_holding_rows(mask=mask)
        assert len(out["rows"]) == 1 and out["rows"][0]["_tab"] == "PX-TEST-002"
        assert [t["tab"] for t in out["skipped_tabs"]] == ["PX-TEST-001"]
        assert "第 1 列不是標頭" in out["skipped_tabs"][0]["error"]    # 冷卻中也照樣帶上次原因
        clock.advance(20)
    assert bad.calls == 4                     # 第 7 輪 2：壞分頁 60 秒短冷卻 → 0、60、120、180 秒各讀一次
    assert good.calls == 4                    # 好分頁 0、60、120、180 秒各讀一次
    # 分頁清單：60 秒快取，但每次有分頁讀取失敗就作廢（第 7 輪 4）→ 0、20、80、140、200 秒各重列一次
    assert holder["book"].calls.count("worksheets") == 5


def test_第6輪_快取長度釘住60秒(policy_env):
    holder, clock, _s = policy_env
    assert R.CACHE_TTL_SEC == 60.0
    good = _good_tab()
    holder["book"] = FakePolicyBook([good])
    R.load_policy_holding_rows(mask=mask)
    clock.advance(59.9)
    R.load_policy_holding_rows(mask=mask)
    assert good.calls == 1
    clock.advance(0.1)
    R.load_policy_holding_rows(mask=mask)
    assert good.calls == 2


def test_第7輪_暫時性5xx_60秒內列為冷卻_到期後恢復(policy_env):
    holder, clock, _s = policy_env

    class Flaky(FakePolicyTab):
        fail_once = True

        def get(self, *args, **kwargs):
            if Flaky.fail_once:
                Flaky.fail_once = False
                self.calls += 1
                raise ConnectionError("503 backend unavailable")
            return super().get(*args, **kwargs)

    flaky = Flaky("PX-TEST-003", [POLICY_HEAD,
        ["PX-TEST-003", "ZZ1", "測試基金丙", "USD", "", "1", "", "1", "1", ""]])
    holder["book"] = FakePolicyBook([flaky, _good_tab()])
    first = R.load_policy_holding_rows(mask=mask)
    assert [t["tab"] for t in first["skipped_tabs"]] == ["PX-TEST-003"]
    second = R.load_policy_holding_rows(mask=mask)        # 時鐘沒動 → 仍在短冷卻
    assert [t["tab"] for t in second["skipped_tabs"]] == ["PX-TEST-003"]
    assert second["skipped_tabs"][0]["error"].startswith("冷卻中（還剩 60 秒），上次失敗：ConnectionError")
    assert flaky.calls == 1 and len(second["rows"]) == 1
    clock.advance(60)
    third = R.load_policy_holding_rows(mask=mask)
    assert third["skipped_tabs"] == [] and len(third["rows"]) == 2


def test_第6輪_分頁快取命中交副本(policy_env):
    holder, _c, _s = policy_env
    holder["book"] = FakePolicyBook([_good_tab()])
    first = R.load_policy_holding_rows(mask=mask)
    first["rows"][0]["fund_code"] = "被改掉"
    first["rows"].clear()
    second = R.load_policy_holding_rows(mask=mask)        # 快取命中
    assert second["rows"][0]["fund_code"] == "ZZ9999"
    second["rows"][0]["fund_code"] = "又被改掉"
    third = R.load_policy_holding_rows(mask=mask)
    assert third["rows"][0]["fund_code"] == "ZZ9999"


def test_第6輪_換ID_同名分頁不讀舊本的分頁快取(policy_env):
    holder, _c, secrets = policy_env
    holder["book"] = FakePolicyBook([_good_tab("PX-SAME")])
    assert R.load_policy_holding_rows(mask=mask)["rows"][0]["fund_name"] == "測試基金甲"
    other = FakePolicyTab("PX-SAME", [POLICY_HEAD,
        ["PX-SAME", "ZZ8888", "另一本的基金", "USD", "", "1", "", "1", "1", ""]])
    holder["book"] = FakePolicyBook([other])
    secrets["POLICY_SHEET_ID"] = SHEET + "-second"
    (row,) = R.load_policy_holding_rows(mask=mask)["rows"]
    assert row["fund_name"] == "另一本的基金" and other.calls == 1


def test_第6輪_全域清除會清掉分頁快取(policy_env):
    holder, _c, _s = policy_env
    good = _good_tab()
    holder["book"] = FakePolicyBook([good])
    R.load_policy_holding_rows(mask=mask)
    R.load_policy_holding_rows(mask=mask)
    assert good.calls == 1
    C.clear_all_caches()
    R.load_policy_holding_rows(mask=mask)
    assert good.calls == 2


def test_第6輪_所有分頁都失敗_拋api錯誤帶各分頁原因_不回空表(policy_env):
    holder, _c, _s = policy_env

    class Broken(FakePolicyTab):
        def get_all_records(self, **_kw):
            raise ValueError(f"boom-{self.title} {SECRET}")

    holder["book"] = FakePolicyBook([Broken("PX-A", []), Broken("PX-B", [])])
    with pytest.raises(R.PolicySupplementError) as err:
        R.load_policy_holding_rows(mask=mask)
    text = str(err.value)
    assert err.value.code == "api"
    assert "所有保單分頁都讀取失敗" in text and "boom-PX-A" in text and "boom-PX-B" in text
    assert SECRET not in text
    assert [t["tab"] for t in err.value.details["skipped_tabs"]] == ["PX-A", "PX-B"]


def test_第6輪_反例_沒有保單分頁不算全部失敗_回空表(policy_env):
    holder, _c, _s = policy_env
    holder["book"] = FakePolicyBook([])
    assert R.load_policy_holding_rows(mask=mask)["rows"] == []


def test_第6輪B4_略過原因前綴不重複():
    class APIError(Exception):
        pass

    assert R._tab_error_text(APIError("APIError: [500]: boom")) == "APIError: [500]: boom"
    assert R._tab_error_text(APIError("[500]: boom")) == "APIError: [500]: boom"


def test_第5輪改判_反例_非429的部分失敗不登記任何冷卻(policy_env):
    holder, _c, _s = policy_env
    bad, good = _bad_and_good_book()
    holder["book"] = FakePolicyBook([bad, good])
    R.load_policy_holding_rows(mask=mask)
    assert not SB.should_skip(GR.sheet_key(R.ACTOR, SHEET))[0]
    assert not SB.should_skip(GR.quota_key(R.ACTOR))[0]


def test_第5輪改判_反例_沒有分頁失敗也不登記冷卻(policy_env):
    holder, _c, _s = policy_env
    holder["book"] = FakePolicyBook([FakePolicyTab("PX-TEST-002", [POLICY_HEAD,
        ["PX-TEST-002", "ZZ9999", "測試基金甲", "USD", "", "1", "", "1", "1", ""]])])
    R.load_policy_holding_rows(mask=mask)
    assert not SB.should_skip(GR.sheet_key(R.ACTOR, SHEET))[0]


def test_第4輪BE_兩個本金標頭並存時取英文欄_與舊路相同(policy_env):
    from repositories.policy.v2 import ALL_COLS_V2, ZH_HEADERS_V2
    holder, _c, _s = policy_env
    zh = [ZH_HEADERS_V2[c] for c in ALL_COLS_V2]
    holder["book"] = FakePolicyBook([FakePolicyTab("PX-5", [zh + ["invest_twd"],
        ["PX-5", "BO1", "雙欄基金", "USD", "", "111", "", "1", "1", "", "222"]])])
    (row,) = R.load_policy_holding_rows(mask=mask)["rows"]
    assert row["invest_twd"] == 222


def test_第4輪A5_假分頁走的是gspread真的get_all_records():
    from gspread.worksheet import Worksheet
    assert FakePolicyTab.get_all_records is Worksheet.get_all_records


def test_第5輪A6_兩個本金欄並存_英文欄空白_L2原因寫明讀的是invest_twd欄(policy_env):
    from repositories.policy.v2 import ALL_COLS_V2, ZH_HEADERS_V2
    from services.v2_tables import alo_holdings as A
    holder, _c, _s = policy_env
    zh = [ZH_HEADERS_V2[c] for c in ALL_COLS_V2]
    holder["book"] = FakePolicyBook([FakePolicyTab("PX-5", [zh + ["invest_twd"],
        ["PX-5", "BO1", "雙欄基金", "USD", "", "111", "", "1", "1", "", ""]])])
    rows = R.load_policy_holding_rows(mask=mask)["rows"]
    assert rows[0]["invest_twd"] is None and rows[0]["_invest_both"] is True
    empty = {"records": [], "bad_rows": [], "blank_rows": 0, "tab_missing": False}
    sup = {"_row": 2, "_raw": (), "policy_id": "PX-5", "fund_code": "BO1", "opened_on": "2001-01-01",
           "last_checked_on": "2001-02-03", "bucket": None}
    out = A.build_alo_tables(rows, {R.TAB_HOLDING_SUPPLEMENT: dict(empty, records=[sup]),
                                    R.TAB_POLICY_PROFILE: empty})
    (skip,) = out["skipped_holdings"]
    assert "讀的是 invest_twd 欄" in skip["reasons"][0]


def test_第5輪A6_反例_只有一個本金欄時_原因不提兩欄(policy_env):
    holder, _c, _s = policy_env
    holder["book"] = FakePolicyBook([FakePolicyTab("PX-TEST-001", [POLICY_HEAD,
        ["PX-TEST-001", "ZZ9999", "測試基金甲", "USD", "", "", "", "1", "1", ""]])])
    (row,) = R.load_policy_holding_rows(mask=mask)["rows"]
    assert row["_invest_both"] is False


# ═══════════════════════ 第 7 輪 ═══════════════════════

class _Raising(FakePolicyTab):
    """每次讀取都拋同一個例外的假分頁。"""

    def __init__(self, title, exc):
        super().__init__(title, [])
        self.exc = exc

    def get(self, *args, **kwargs):
        self.calls += 1
        raise self.exc


def test_第7輪1_分頁名含429_實際回400_不算配額_只冷卻那一張(policy_env):
    holder, _c, _s = policy_env
    bad = _Raising("PX-429", _api_error(400, "Unable to parse range: 'PX-429'!A1"))
    holder["book"] = FakePolicyBook([bad, _good_tab()])
    out = R.load_policy_holding_rows(mask=mask)
    assert [t["tab"] for t in out["skipped_tabs"]] == ["PX-429"]
    assert not SB.should_skip(GR.quota_key(R.ACTOR))[0]
    assert R.tab_cooling(SHEET, "PX-429")[0]
    assert not SB.should_skip(GR.sheet_key(R.ACTOR, SHEET))[0]


def test_第7輪1_ID含429的連線錯誤_不登記配額冷卻(policy_env):
    holder, _c, secrets = policy_env
    secrets["POLICY_SHEET_ID"] = "sheet-with-429-inside"
    bad = _Raising("PX-A", ConnectionError("connect to sheet-with-429-inside failed"))
    holder["book"] = FakePolicyBook([bad, _good_tab()])
    R.load_policy_holding_rows(mask=mask)
    assert not SB.should_skip(GR.quota_key(R.ACTOR))[0]
    assert R.tab_cooling("sheet-with-429-inside", "PX-A")[0]


def test_第7輪1_真429照登記配額冷卻_不登記分頁冷卻(policy_env):
    holder, _c, _s = policy_env
    bad = _Raising("PX-A", _api_error(429, "Quota exceeded"))
    holder["book"] = FakePolicyBook([_good_tab(), bad])
    R.load_policy_holding_rows(mask=mask)
    assert SB.should_skip(GR.quota_key(R.ACTOR))[0]
    assert not R.tab_cooling(SHEET, "PX-A")[0]


@pytest.mark.parametrize("exc,expected", [
    (_api_error(429, "x"), True), (_api_error(400, "429"), False), (_api_error(500, "x"), False),
    (ConnectionError("429"), False), (Exception("APIError: [429]: Quota exceeded"), False),
])
def test_第7輪1_配額判斷只看狀態碼(exc, expected):
    assert R.is_rate_limited(exc) is expected


def test_第7輪2_全部分頁都在失敗或冷卻_照樣拋api(policy_env):
    holder, _c, _s = policy_env
    holder["book"] = FakePolicyBook([_Raising("PX-A", ValueError("a")), _Raising("PX-B", ValueError("b"))])
    for _ in range(2):                  # 第 1 次：都讀失敗；第 2 次：都在冷卻
        with pytest.raises(R.PolicySupplementError) as err:
            R.load_policy_holding_rows(mask=mask)
        assert err.value.code == "api"
    assert "冷卻中" in str(err.value)


def test_第7輪2_好分頁不受壞分頁冷卻影響(policy_env):
    holder, clock, _s = policy_env
    good = _good_tab()
    holder["book"] = FakePolicyBook([_Raising("PX-A", ValueError("a")), good])
    for _ in range(3):
        assert len(R.load_policy_holding_rows(mask=mask)["rows"]) == 1
        clock.advance(61)
    assert good.calls == 3


def test_第7輪3_最後被略過的分頁_存入前已遮蔽_整頁成功時清除(policy_env):
    holder, clock, _s = policy_env
    holder["book"] = FakePolicyBook([_Raising("PX-A", ValueError(f"boom {SECRET}")), _good_tab()])
    R.load_policy_holding_rows(mask=mask)
    stored = R._LAST_SKIPPED[SHEET]
    assert stored == [("PX-A", f"ValueError: boom {MASK}", False)]
    assert SECRET not in repr(R._LAST_SKIPPED)
    clock.advance(60)
    holder["book"] = FakePolicyBook([_good_tab()])
    R.load_policy_holding_rows(mask=mask)
    assert SHEET not in R._LAST_SKIPPED


@pytest.mark.parametrize("how", ["clear_cache", "clear_all_caches"])
def test_第7輪3_清快取時一併清除最後被略過的分頁(policy_env, how):
    holder, _c, _s = policy_env
    holder["book"] = FakePolicyBook([_Raising("PX-A", ValueError("a")), _good_tab()])
    R.load_policy_holding_rows(mask=mask)
    assert SHEET in R._LAST_SKIPPED
    R.clear_cache() if how == "clear_cache" else C.clear_all_caches()
    assert R._LAST_SKIPPED == {}


def test_第7輪3_冷卻訊息列出全部被略過的分頁_標出觸發冷卻的那張(policy_env):
    holder, _c, _s = policy_env
    holder["book"] = FakePolicyBook([_good_tab(), _Raising("PX-A", ValueError(f"a {SECRET}")),
                                     _Raising("PX-B", _api_error(429, "Quota exceeded"))])
    R.load_policy_holding_rows(mask=mask)
    with pytest.raises(R.PolicySupplementError) as err:
        R.load_policy_holding_rows(mask=mask)
    text = str(err.value)
    assert err.value.code == "cooling"
    assert "PX-A：ValueError: a" in text and "PX-B（觸發冷卻）：" in text
    assert "PX-A（觸發冷卻）" not in text and SECRET not in text


def test_第7輪4_任一分頁讀取失敗就作廢分頁清單快取(policy_env):
    holder, clock, _s = policy_env
    book = FakePolicyBook([_Raising("PX-A", ValueError("a")), _good_tab()])
    holder["book"] = book
    R.load_policy_holding_rows(mask=mask)
    assert book.calls.count("worksheets") == 1
    R.load_policy_holding_rows(mask=mask)        # 清單已作廢 → 重列；PX-A 在冷卻中，不算讀取失敗
    assert book.calls.count("worksheets") == 2
    R.load_policy_holding_rows(mask=mask)        # 上一次沒有讀取失敗 → 清單快取命中
    assert book.calls.count("worksheets") == 2


def test_第7輪4_反例_沒有讀取失敗時分頁清單快取照用(policy_env):
    holder, _c, _s = policy_env
    book = FakePolicyBook([_good_tab()])
    holder["book"] = book
    for _ in range(3):
        R.load_policy_holding_rows(mask=mask)
    assert book.calls.count("worksheets") == 1


def test_第7輪6_等價鎖定_快取版連跑兩次_第二次命中快取_兩次都與舊路等價(monkeypatch):
    R.clear_cache()
    SB.reset_all()
    try:
        _assert_equivalent(R._cached_policy_loader)
        fetched = []
        real = R._fetch_policy_tab
        monkeypatch.setattr(R, "_fetch_policy_tab", lambda ws: (fetched.append(ws.title), real(ws))[1])
        _assert_equivalent(R._cached_policy_loader)
        assert fetched == ["壞分頁"]          # 只有讀失敗的那張重讀，其餘全命中分頁快取
    finally:
        R.clear_cache()
        SB.reset_all()


# ═══════════════════════ 第 7b 輪：本檔自己的 429 重試 ═══════════════════════

@pytest.fixture
def slept(monkeypatch):
    record = []
    monkeypatch.setattr(GR.time, "sleep", lambda s: record.append(s))
    return record


def test_第7b輪_分頁名含429_實際回400_只試1次不睡(slept):
    tab = _Raising("PX-429", _api_error(400, "Unable to parse range: 'PX-429'!A1"))
    with pytest.raises(Exception):
        R._fetch_policy_tab(tab)
    assert tab.calls == 1 and slept == []


def test_第7b輪_連線錯誤含429字樣_只試1次不睡(slept):
    tab = _Raising("PX-A", ConnectionError("connect to sheet-with-429 failed"))
    with pytest.raises(ConnectionError):
        R._fetch_policy_tab(tab)
    assert tab.calls == 1 and slept == []


def test_第7b輪_真429照退避重試_用完才拋(slept):
    tab = _Raising("PX-A", _api_error(429, "Quota exceeded"))
    with pytest.raises(Exception):
        R._fetch_policy_tab(tab)
    assert tab.calls == len(GR.DEFAULT_QUOTA_BACKOFFS)
    assert slept == list(GR.DEFAULT_QUOTA_BACKOFFS[:-1])


def test_第7b輪_真429後恢復_回傳資料(slept):
    class Recovering(FakePolicyTab):
        attempts = 0

        def get(self, *args, **kwargs):
            Recovering.attempts += 1
            if Recovering.attempts <= 2:
                raise _api_error(429, "Quota exceeded")
            return super().get(*args, **kwargs)

    tab = Recovering("PX-B", [["a"], ["1"]])
    assert R._fetch_policy_tab(tab) == [{"a": "1"}]
    assert Recovering.attempts == 3 and slept == list(GR.DEFAULT_QUOTA_BACKOFFS[:2])


def test_第7b輪_不再經過共用的_with_quota_retry(monkeypatch):
    from repositories.policy import _helpers as H

    def forbidden(*_a, **_k):
        raise AssertionError("不得呼叫共用的 _with_quota_retry")

    monkeypatch.setattr(H, "_with_quota_retry", forbidden)
    assert R._fetch_policy_tab(_good_tab()) != []


# ═══════════════════════ 第 8 輪 ═══════════════════════

def test_第8輪2_五十張分頁同時429_打上游與睡眠都有上限_其餘分頁不讀(policy_env, slept):
    holder, _c, _s = policy_env
    tabs = [_Raising(f"PX-{i:02d}", _api_error(429, "Quota exceeded")) for i in range(50)]
    holder["book"] = FakePolicyBook(tabs)
    with pytest.raises(R.PolicySupplementError) as err:
        R.load_policy_holding_rows(mask=mask)
    assert err.value.code == "api"                                     # 沒有任何資料 → 不回空表
    upstream = sum(t.calls for t in tabs) + len(holder["book"].calls)
    assert upstream <= 6, upstream                                    # 4 次重試＋open_by_key＋worksheets
    assert sum(slept) <= 7.0, slept                                  # 1＋2＋4
    skipped = err.value.details["skipped_tabs"]
    assert len(skipped) == 50
    assert [t["error"] for t in skipped[1:]] == [R.QUOTA_UNREAD_TEXT] * 49
    assert SB.should_skip(GR.quota_key(R.ACTOR))[0]


def test_第8輪2_配額耗盡後_已在快取的分頁照用_要打上游的才不讀(policy_env, slept):
    holder, clock, _s = policy_env
    good, later = _good_tab("PX-GOOD"), _good_tab("PX-LATER")
    holder["book"] = FakePolicyBook([good])
    R.load_policy_holding_rows(mask=mask)                             # PX-GOOD 進分頁快取
    SB.reset_all()
    quota = _Raising("PX-429", _api_error(429, "Quota exceeded"))
    R._CACHE.pop((SHEET, "policy_tab_list"), None)
    holder["book"] = FakePolicyBook([quota, good, later])
    out = R.load_policy_holding_rows(mask=mask)
    assert [r["_tab"] for r in out["rows"]] == ["PX-GOOD"] and good.calls == 1
    assert {t["tab"]: t["error"] for t in out["skipped_tabs"]}["PX-LATER"] == R.QUOTA_UNREAD_TEXT
    assert later.calls == 0


def test_第8輪3_暫時性5xx先用本檔重試吃掉_不進分頁冷卻(policy_env, slept):
    holder, _c, _s = policy_env

    class Once5xx(FakePolicyTab):
        attempts = 0

        def get(self, *args, **kwargs):
            Once5xx.attempts += 1
            if Once5xx.attempts == 1:
                raise _api_error(503, "backend unavailable")
            return super().get(*args, **kwargs)

    tab = Once5xx("PX-B", [POLICY_HEAD, ["PX-B", "ZZ1", "測試基金", "USD", "", "1", "", "1", "1", ""]])
    holder["book"] = FakePolicyBook([tab])
    out = R.load_policy_holding_rows(mask=mask)
    assert out["skipped_tabs"] == [] and len(out["rows"]) == 1
    assert slept == [GR.DEFAULT_QUOTA_BACKOFFS[0]] and not R.tab_cooling(SHEET, "PX-B")[0]


def test_第8輪3_5xx重試用完仍失敗_才登記分頁冷卻(policy_env, slept):
    holder, _c, _s = policy_env
    bad = _Raising("PX-B", _api_error(503, "backend unavailable"))
    holder["book"] = FakePolicyBook([_good_tab(), bad])
    out = R.load_policy_holding_rows(mask=mask)
    assert bad.calls == len(GR.DEFAULT_QUOTA_BACKOFFS)
    assert [t["tab"] for t in out["skipped_tabs"]] == ["PX-B"]
    assert R.tab_cooling(SHEET, "PX-B")[0]


@pytest.mark.parametrize("status", [403, 500])
def test_第8輪4_實際讀取的分頁全部同一類HTTP錯誤_改登記整本鑰匙(policy_env, slept, status):
    holder, _c, _s = policy_env
    holder["book"] = FakePolicyBook([_Raising("PX-A", _api_error(status, "x")),
                                     _Raising("PX-B", _api_error(status, "y"))])
    with pytest.raises(R.PolicySupplementError):
        R.load_policy_holding_rows(mask=mask)
    assert SB.should_skip(GR.sheet_key(R.ACTOR, SHEET))[0]
    assert not R.tab_cooling(SHEET, "PX-A")[0] and not R.tab_cooling(SHEET, "PX-B")[0]
    assert not SB.should_skip(GR.quota_key(R.ACTOR))[0]


def test_第8輪4_反例_只有部分分頁失敗_仍逐分頁登記(policy_env, slept):
    holder, _c, _s = policy_env
    holder["book"] = FakePolicyBook([_Raising("PX-A", _api_error(403, "x")), _good_tab()])
    R.load_policy_holding_rows(mask=mask)
    assert not SB.should_skip(GR.sheet_key(R.ACTOR, SHEET))[0]
    assert R.tab_cooling(SHEET, "PX-A")[0]


def test_第8輪4_反例_錯誤類別不同_仍逐分頁登記(policy_env, slept):
    holder, _c, _s = policy_env
    holder["book"] = FakePolicyBook([_Raising("PX-A", _api_error(403, "x")),
                                     _Raising("PX-B", _api_error(500, "y"))])
    with pytest.raises(R.PolicySupplementError):
        R.load_policy_holding_rows(mask=mask)
    assert not SB.should_skip(GR.sheet_key(R.ACTOR, SHEET))[0]
    assert R.tab_cooling(SHEET, "PX-A")[0] and R.tab_cooling(SHEET, "PX-B")[0]


def test_第8輪4_反例_沒有狀態碼的錯誤不升級成整本(policy_env):
    holder, _c, _s = policy_env
    holder["book"] = FakePolicyBook([_Raising("PX-A", ValueError("a")), _Raising("PX-B", ValueError("b"))])
    with pytest.raises(R.PolicySupplementError):
        R.load_policy_holding_rows(mask=mask)
    assert not SB.should_skip(GR.sheet_key(R.ACTOR, SHEET))[0]
    assert R.tab_cooling(SHEET, "PX-A")[0]


def test_第8輪5_分頁冷卻存在本檔_不佔source_backoff的鑰匙(policy_env):
    holder, _c, _s = policy_env
    tabs = [_Raising(f"PX-{i:03d}", ValueError("bad")) for i in range(200)] + [_good_tab()]
    holder["book"] = FakePolicyBook(tabs)
    R.load_policy_holding_rows(mask=mask)
    assert len(R._TAB_COOLDOWN) == 200
    assert not [s for s in SB.get_backoff_state() if "tab" in s["source"]]
    SB.record_failure(GR.quota_key(R.ACTOR), "rate_limited")
    for i in range(300):                                   # 再多的壞分頁也擠不掉配額鑰匙
        R._record_tab_cooldown(SHEET, f"PX-X{i}", "x")
    assert SB.should_skip(GR.quota_key(R.ACTOR))[0]


@pytest.mark.parametrize("how", ["clear_cache", "clear_all_caches"])
def test_第8輪6_清快取時一併清掉分頁冷卻與上次原因(policy_env, how):
    holder, _c, _s = policy_env
    holder["book"] = FakePolicyBook([_Raising("PX-A", ValueError("a")), _good_tab()])
    R.load_policy_holding_rows(mask=mask)
    assert R._TAB_COOLDOWN and R._TAB_LAST_ERROR
    R.clear_cache() if how == "clear_cache" else C.clear_all_caches()
    assert R._TAB_COOLDOWN == {} and R._TAB_LAST_ERROR == {}
    assert not R.tab_cooling(SHEET, "PX-A")[0]


def test_第8輪7_換一本試算表不繼承同名分頁的冷卻(policy_env):
    holder, _c, secrets = policy_env
    holder["book"] = FakePolicyBook([_Raising("PX-A", ValueError("a")), _good_tab()])
    R.load_policy_holding_rows(mask=mask)
    assert R.tab_cooling(SHEET, "PX-A")[0]
    same_name = FakePolicyTab("PX-A", [POLICY_HEAD, ["PX-A", "ZZ1", "另一本", "USD", "", "1", "", "1", "1", ""]])
    holder["book"] = FakePolicyBook([same_name])
    secrets["POLICY_SHEET_ID"] = SHEET + "-second"
    out = R.load_policy_holding_rows(mask=mask)
    assert out["skipped_tabs"] == [] and same_name.calls == 1


def test_第8輪7_分頁上次原因存入時不含秘密值(policy_env):
    holder, _c, _s = policy_env
    holder["book"] = FakePolicyBook([_Raising("PX-A", ValueError(f"boom {SECRET}")), _good_tab()])
    R.load_policy_holding_rows(mask=mask)
    stored = R._TAB_LAST_ERROR[R.tab_cooldown_key(SHEET, "PX-A")]
    assert SECRET not in stored and MASK in stored
