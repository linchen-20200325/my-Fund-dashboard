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


# ═══════════════════════ 2026-09-26 回修：strip、ASCII 數字、NaN／inf ═══════════════════════

_EDGE = [
    ("１２", "int"), ("٣", "int"), ("１.５", "float"), ("0.５", "ratio"), ("２０２６-09-26", "date"),
    ("[NaN]", "list"), ("[Infinity]", "list"), ("[-Infinity]", "rules"), ('[1, "NaN"]', "list"),
    ("  12  ", "int"), ("\n0.5\t", "ratio"), ("1.", "float"), ("-", "int"), ("", "int"), ("1.-5", "float"),
]


def test_邊界_兩份判定逐一相同():
    from ui_v2.set import logic
    for value, kind in _EDGE:
        assert S.value_matches_kind(value, kind) == logic.value_matches_kind(value, kind), (value, kind)


@pytest.mark.parametrize("value, kind", [("１２", "int"), ("٣", "int"), ("0.５", "ratio"),
                                          ("[NaN]", "list"), ("[Infinity]", "list"), ("[-Infinity]", "rules")])
def test_非ASCII數字與NaN_inf_拒收_不寫(book, value, kind):
    out = S.save_setting_for_page("k", value, kind, [SECRET])
    assert out["status"] == "kind_mismatch" and book.calls == []


def test_字串形式的NaN不是常數_照收():
    assert S.value_matches_kind('[1, "NaN"]', "list") is True


@pytest.mark.parametrize("value, kind", [("  21 \n", "int"), (" 0.5", "ratio"), ("2026-09-26 ", "date"),
                                         (' ["a"]', "list"), ("1.5\t", "float")])
def test_前後帶空白_一律型別不符_不寫_不靜默去掉(book, value, kind):
    from ui_v2.set import logic
    assert S.value_matches_kind(value, kind) is False and logic.value_matches_kind(value, kind) is False
    out = S.save_setting_for_page("set_max_age_days", value, kind, [SECRET])
    assert out["status"] == "kind_mismatch" and book.calls == []


def test_寫進去的就是原值(book):
    out = S.save_setting_for_page("set_max_age_days", "21", "int", [SECRET])
    assert out["status"] == "saved" and out["row"]["setting_value"] == "21"
    assert book.data("user_setting_log")[-1][:2] == ["set_max_age_days", "21"]


def test_只有空白_不存(book):
    out = S.save_setting_for_page("set_max_age_days", "   ", "int", [SECRET])
    assert out["status"] == "kind_mismatch" and book.calls == []


# ═══════════════════════ 2026-09-26 客戶裁示：alo_basis 枚舉 ═══════════════════════


def test_可選值寫死在L2_畫面那一份是同一份鏡像():
    from ui_v2.set import logic
    assert S.ENUM_SETTING_VALUES == {"alo_basis": ("成本", "市值")} and S.ENUM_KIND == "list"
    assert logic.ENUM_SETTING_VALUES == S.ENUM_SETTING_VALUES and logic.ENUM_KIND == S.ENUM_KIND


@pytest.mark.parametrize("value, ok", [("成本", True), ("市值", True), (" 成本\n", False), ("成本 ", False),
                                       ("cost", False), ("mv", False), ('["成本"]', False), ("市值成本", False),
                                       ("  ", False)])
def test_L2與畫面_枚舉判定一致(value, ok):
    from ui_v2.set import logic
    assert logic.value_matches_setting("alo_basis", value, "list") is ok
    if ok:
        S.check_setting_value(value, "list", setting_key="alo_basis")
    else:
        with pytest.raises(S.ValueKindMismatch):
            S.check_setting_value(value, "list", setting_key="alo_basis")


def test_枚舉鍵_value_kind不是list一律不符(book):
    out = S.save_setting_for_page("alo_basis", "成本", "int", [SECRET])
    assert out["status"] == "kind_mismatch" and book.calls == []
    from ui_v2.set import logic
    assert logic.value_matches_setting("alo_basis", "成本", "int") is False


def test_枚舉鍵_照存_清除也照存(book):
    assert S.save_setting_for_page("alo_basis", "市值", "list", [SECRET])["status"] == "saved"
    assert S.load_user_settings([SECRET])["rows"]["alo_basis"]["setting_value"] == "市值"
    assert S.save_setting_for_page("alo_basis", None, "list", [SECRET])["status"] == "saved"
    assert S.load_user_settings([SECRET])["rows"]["alo_basis"]["setting_value"] is None


def test_非枚舉鍵的list照舊_JSON陣列():
    S.check_setting_value('["a"]', "list", setting_key="alo_bucket_names")
    with pytest.raises(S.ValueKindMismatch):
        S.check_setting_value("成本", "list", setting_key="alo_bucket_names")



@pytest.mark.parametrize("value, kind", [("[1e999]", "list"), ("[-1e999]", "rules"), ('[["a", 1e400]]', "list"),
                                         ('[{"w": 1e999}]', "rules")])
def test_溢位成inf的數字_兩份一律拒收_不寫(book, value, kind):
    from ui_v2.set import logic
    assert S.value_matches_kind(value, kind) is False and logic.value_matches_kind(value, kind) is False
    out = S.save_setting_for_page("exp_watchlist", value, kind, [SECRET])
    assert out["status"] == "kind_mismatch" and book.calls == []


def test_大但有限的數字照收():
    from ui_v2.set import logic
    for value in ("[1e300]", '[["a", 0.5]]', '[{"w": 2}]'):
        assert S.value_matches_kind(value, "list") and logic.value_matches_kind(value, "list"), value



# ═══════════════════════ 2026-09-26 最後一輪回修 ═══════════════════════


def test_極深巢狀_兩份判法都判型別不符_不崩():
    from ui_v2.set import logic
    deep = "[" * 100000 + "]" * 100000
    for kind in ("list", "rules"):
        assert S.value_matches_kind(deep, kind) is False
        assert logic.value_matches_kind(deep, kind) is False
    with pytest.raises(S.ValueKindMismatch):
        S.check_setting_value(deep, "list", setting_key="exp_watchlist")


def test_極深巢狀_存檔回型別不符_不寫(book):
    out = S.save_setting_for_page("exp_watchlist", "[" * 100000 + "]" * 100000, "list", [SECRET])
    assert out["status"] == "kind_mismatch" and book.calls == []


def test_極深巢狀_試算表上已存的值_畫面照印型別不符不崩():
    from ui_v2.set import fixtures, logic
    dataset = fixtures.scenario("ok")
    deep = "[" * 100000 + "]" * 100000
    for row in dataset["user_setting"]:
        if row["setting_key"] == "exp_watchlist":
            row["setting_value"] = deep
    model = logic.build_page_model(dataset)
    row = [r for r in logic.find_block(model, "SET-3")["_rows"] if r["_key"] == "exp_watchlist"][0]
    assert row["value_text"] == logic.TEXT_NA_BAD_KIND


def test_L1讀取端不解析setting_value():
    """L1 不 json.loads 設定值（只解析服務帳戶憑證），所以讀取端沒有極深巢狀的崩潰點；值原樣交回。"""
    import ast
    import pathlib
    src = pathlib.Path(R.__file__).read_text(encoding="utf-8")
    loads = [n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Call)
             and getattr(n.func, "attr", "") == "loads"]
    assert len(loads) == 1                                              # 只有 _client_email 那一處
    assert "def _client_email" in src and "creds = json.loads(creds)" in src


def test_極深巢狀_讀回照原值_不崩(book):
    from _fake_settings_sheet import FakeWorksheet
    deep = "[" * 100000 + "]" * 100000
    head = [n for n, _k, _nl in R.USER_SETTING_SPEC]
    book.tabs["user_setting_log"] = FakeWorksheet(book, "user_setting_log", [
        head, ["exp_watchlist", deep, "list", "2026-09-20T00:00:00Z"]])
    assert S.load_user_settings([SECRET])["rows"]["exp_watchlist"]["setting_value"] == deep


def _alo_live_triggered(root, pages_reading) -> bool:
    """跨頁守衛的觸發條件（2026-09-26 放寬）：L2 宣告 alo 已讀設定，或 ui_v2 底下出現任何 alo 正式模式入口
    （`app_alo*live*.py`、`alo/source.py`、`alo/live.py`）。"""
    if "alo" in pages_reading:
        return True
    ui_v2 = root / "ui_v2"
    return any(ui_v2.glob("app_alo*live*.py")) or (ui_v2 / "alo" / "source.py").exists() \
        or (ui_v2 / "alo" / "live.py").exists()


def test_跨頁守衛的觸發條件_正控與負控(tmp_path):
    (tmp_path / "ui_v2" / "alo").mkdir(parents=True)
    assert _alo_live_triggered(tmp_path, ("set",)) is False
    assert _alo_live_triggered(tmp_path, ("set", "alo")) is True
    # 探針（稽核 A 實測的繞過手法）：入口改名成 app_alo_live_v2.py 也要擋下。
    for rel in ("ui_v2/app_alo_live.py", "ui_v2/app_alo_live_v2.py", "ui_v2/app_alo_live2.py",
                "ui_v2/alo/source.py", "ui_v2/alo/live.py"):
        (tmp_path / rel).write_text("", encoding="utf-8")
        assert _alo_live_triggered(tmp_path, ("set",)) is True, rel
        (tmp_path / rel).unlink()


def test_跨頁守衛_alo接正式模式時比重基準須與L2可選值一致():
    """據實登記的分歧（2026-09-26 稽核 A）：set 頁存「成本／市值」，ui_v2/alo 目前用 cost／mv。
    alo 還沒有正式入口時，這條只記錄分歧仍在；一旦 `ui_v2/app_alo_live.py` 出現，alo 的比重基準值
    必須改成 L2 這一份，否則紅。"""
    import pathlib
    from ui_v2.alo import logic as alo_logic
    root = pathlib.Path(__file__).resolve().parents[1]
    alo_values = (alo_logic.BASIS_COST, alo_logic.BASIS_MV)
    if _alo_live_triggered(root, S.PAGES_READING_SETTINGS):
        assert alo_values == S.ENUM_SETTING_VALUES["alo_basis"], alo_values
    else:
        assert alo_values == ("cost", "mv")                            # 分歧仍在：接正式模式前要改
        assert set(alo_values).isdisjoint(S.ENUM_SETTING_VALUES["alo_basis"])



# ═══════════════════════ 2026-09-26 紅隊最終複驗：超長整數、溢位的浮點 ═══════════════════════


def test_int位數上限_兩份相同_18位可_19位與4301位不可():
    from ui_v2.set import logic
    assert S.INT_MAX_DIGITS == logic.INT_MAX_DIGITS == 18
    for value, ok in (("9" * 18, True), ("-" + "9" * 18, True), ("9" * 19, False), ("-" + "9" * 19, False),
                      ("1" * 4301, False)):
        assert S.value_matches_kind(value, "int") is ok and logic.value_matches_kind(value, "int") is ok, value


def test_超長整數_從頁面存檔_型別不符不寫(book):
    out = S.save_setting_for_page("set_max_age_days", "1" * 4301, "int", [SECRET])
    assert out["status"] == "kind_mismatch" and book.calls == []


@pytest.mark.parametrize("value", ["1" * 4301, "9" * 19])
def test_超長整數_試算表裡已經有_頁面不崩_標值與型別不符(book, value):
    from _fake_settings_sheet import FakeWorksheet
    from ui_v2.set import fixtures, logic
    head = [n for n, _k, _nl in R.USER_SETTING_SPEC]
    book.tabs["user_setting_log"] = FakeWorksheet(book, "user_setting_log", [
        head, ["set_max_age_days", value, "int", "2026-09-20T00:00:00Z"],
        ["set_log_keep_rows", value, "int", "2026-09-20T00:00:00Z"]])
    rows = S.load_user_settings([SECRET])["rows"]
    dataset = fixtures.scenario("ok")
    dataset["user_setting"] = [r for r in dataset["user_setting"]
                               if r["setting_key"] not in ("set_max_age_days", "set_log_keep_rows")]
    dataset["user_setting"] += [dict(rows["set_max_age_days"]), dict(rows["set_log_keep_rows"])]
    model = logic.build_page_model(dataset)
    assert logic.find_block(model, "SET-0")["text"] == logic.TEXT_NA_BAD_KIND
    assert logic.find_block(model, "SET-1")["_limit_state"] == "bad"
    assert any(logic.TEXT_NA_BAD_KIND in line for line in logic.find_block(model, "SET-6")["tail_lines"])


def test_讀取時的int轉換失敗_也標值與型別不符(monkeypatch):
    """第二道：即使型別判法放行了（例如日後判法有漏），`_setting_state` 的 int() 失敗也要接住。"""
    from ui_v2.set import fixtures, logic
    monkeypatch.setattr(logic, "value_matches_kind", lambda value, kind: True)
    dataset = fixtures.scenario("ok")
    for row in dataset["user_setting"]:
        if row["setting_key"] == "set_max_age_days":
            row["setting_value"] = "1" * 4301
    model = logic.build_page_model(dataset)
    assert logic.find_block(model, "SET-1")["_limit_state"] == "bad"


@pytest.mark.parametrize("value, kind", [("9" * 400, "float"), ("-" + "9" * 400, "float"),
                                         ("1" + "0" * 400 + ".5", "ratio")])
def test_溢位成inf的浮點字面值_兩份拒收_不寫(book, value, kind):
    from ui_v2.set import logic
    assert S.value_matches_kind(value, kind) is False and logic.value_matches_kind(value, kind) is False
    out = S.save_setting_for_page("alo_tolerance_pp", value, kind, [SECRET])
    assert out["status"] == "kind_mismatch" and book.calls == []


def test_很大但有限的浮點照收():
    from ui_v2.set import logic
    value = "9" * 300
    assert S.value_matches_kind(value, "float") and logic.value_matches_kind(value, "float")
