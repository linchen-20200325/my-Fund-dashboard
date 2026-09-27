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

class FakePolicyTab:
    """假保單分頁：`get_all_records` 用 gspread 真的 `numericise_all` 模擬（純數字字串會變數字）。"""

    def __init__(self, title, rows):
        self.title = title
        self.rows = rows

    def get_all_records(self):
        from gspread.utils import numericise_all, to_records
        keys, values = self.rows[0], self.rows[1:]
        width = len(keys)
        values = [numericise_all((list(r) + [""] * width)[:width]) for r in values]
        return to_records(keys, values)


class FakePolicyBook:
    def __init__(self, tabs):
        self.tabs = tabs

    def open_by_key(self, key):
        return self

    def worksheets(self):
        return self.tabs


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
        {"tab": "PX-TEST-001", "row": 5, "raw": "NT$1,000", "reason": "非數值（原始值：NT$1,000）"}]


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


def test_保單分頁_單一分頁讀失敗_略過並交出分頁名_ID不遮秘密值遮_且不快取(policy_env):
    holder, _c, _s = policy_env

    class Broken(FakePolicyTab):
        def get_all_records(self):
            raise ValueError(f"boom {SHEET} {SECRET}")

    holder["book"] = FakePolicyBook([Broken("PX-TEST-009", [])])
    out = R.load_policy_holding_rows(mask=mask)
    (sk,) = out["skipped_tabs"]
    assert sk["tab"] == "PX-TEST-009" and SHEET in sk["error"] and SECRET not in sk["error"]
    holder["book"] = FakePolicyBook([])
    assert R.load_policy_holding_rows(mask=mask)["skipped_tabs"] == []   # 有略過的結果沒被快取


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
