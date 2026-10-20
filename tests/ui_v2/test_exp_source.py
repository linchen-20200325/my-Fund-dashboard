# -*- coding: utf-8 -*-
"""ui_v2/exp/source.py 的接縫測試（fast lane；不打網路、不需要 streamlit 執行期）。

L2 與 `st` 一律以替身注入（monkeypatch `source` 模組上的引用），不呼叫任何 L1。體例同 tests/ui_v2/test_mkt_source.py。
"""

from __future__ import annotations

import json
import pathlib
import secrets as _rnd
import sys
import types

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

from ui_v2.exp import fixtures, live  # noqa: E402

source = pytest.importorskip("ui_v2.exp.source")  # 需要 L1 的相依（gspread、streamlit 等）

_OK_POOL = {"status": "ok", "backend": "service_account", "codes": ["B02", "A01"], "dropped_blank": 0,
            "duplicates": 0, "message": None}


@pytest.fixture
def fake_st(monkeypatch):
    st = types.SimpleNamespace(secrets={}, session_state={})
    monkeypatch.setattr(source, "st", st)
    return st


sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _exp_wired_fixture as WF  # noqa: E402


@pytest.fixture(autouse=True)
def _fixed_taipei_now(monkeypatch):
    """把 `source.load_live` 的「台灣今天」固定成 fixture 設計日 `WF.TODAY`（2026-10-14）。

    ⚠️ 測試隔離（2026-10-20/21 發現；不改產品碼、斷言與 10 日門檻）：`load_live` 以
    `datetime.now(live.TAIPEI)` 取「今天」，而 `_exp_wired_fixture` 的淨值日期是照 `TODAY = 2026-10-14`
    設計的（例：A01 最近淨值 2026-10-10 ＝ 4 天前、應為正常）。不固定時，真實日期一過 2026-10-20，
    A01 就變成「⬜ 資料未備：最近一筆淨值 2026-10-10，已超過 10 日」，測試隨系統日期轉紅。
    這裡只換掉 `source` 模組上的 `datetime` 名稱（`now(tz)` 回固定時刻，其餘行為同 `datetime`）。
    守衛：`test_今天固定為fixture設計日_不依賴系統日期`。
    """
    from datetime import datetime as _dt

    class _FixedDatetime(_dt):
        @classmethod
        def now(cls, tz=None):
            return _dt(WF.TODAY.year, WF.TODAY.month, WF.TODAY.day, 9, 0, tzinfo=tz)

    monkeypatch.setattr(source, "datetime", _FixedDatetime)


def _keys(codes):
    return {"results": [{"input": c, "ok": True, "full_key": c, "portal": "", "parsed_code": c, "error": None}
                        for c in codes]}


@pytest.fixture(autouse=True)
def l2_calls(monkeypatch):
    """2026-10-14 C2 接線後 `load_live` 會再呼叫三支 L2；本檔一律換成替身（不打網路），並記下呼叫。"""
    calls = {"keys": [], "profiles": [], "nav": [], "now": []}

    def resolve(codes):
        calls["keys"].append(list(codes))
        return _keys(codes)

    def build(key_results, *, fetchers=None, now=None):   # 簽章同 `exp_profile.build_profiles`（#965 起有 now）
        calls["profiles"].append([r["input"] for r in key_results])
        calls["now"].append(("profile", now))
        return WF.profiles(codes=[r["input"] for r in key_results])

    def load_nav(funds, *, now=None):
        calls["nav"].append([dict(f) for f in funds])
        calls["now"].append(("nav", now))
        return WF.nav_out(codes=[f["fund_code"] for f in funds])

    monkeypatch.setattr(source.fund_keys, "resolve_full_keys", resolve)
    monkeypatch.setattr(source.exp_profile, "build_profiles", build)
    monkeypatch.setattr(source.exp_nav, "load_nav_dividend", load_nav)
    return calls


def _settings_rows(**values):
    return {"rows": {k: {"setting_key": k, "setting_value": v} for k, v in values.items()},
            "bad_rows": [], "broken_keys": [], "blank_rows": 0, "tab_missing": False}


def test_load_live形狀_dataset與fixtures同形_母體只來自L2的代碼(monkeypatch, fake_st):
    seen = []
    monkeypatch.setattr(source.exp_universe, "load_pool_codes",
                        lambda values, oauth_client=None: seen.append(oauth_client) or dict(_OK_POOL))
    monkeypatch.setattr(source.settings_store, "load_user_settings",
                        lambda values: _settings_rows(exp_watchlist='["A01"]'))
    data = source.load_live()
    assert set(data) == {"dataset", "notes"}
    assert set(data["dataset"]) == set(fixtures.scenario("full")["dataset"])
    assert [r["fund_code"] for r in data["dataset"]["fund_profile"]] == ["B02", "A01"]
    assert data["notes"]["pool"] == _OK_POOL
    assert data["notes"]["settings"][live.KEY_WATCH] == ("A01",)
    assert data["notes"]["settings_error"] is None
    assert seen == [None]                                    # ui_v2 沒有取登入者 client 的途徑，恆傳 None


def test_設定讀不到_回訊息_與沒設定分開(monkeypatch, fake_st):
    monkeypatch.setattr(source.exp_universe, "load_pool_codes", lambda values, oauth_client=None: dict(_OK_POOL))

    def boom(values):
        raise source.settings_store.SettingsSheetError("讀設定失敗（測試）", code="api")

    monkeypatch.setattr(source.settings_store, "load_user_settings", boom)
    data = source.load_live()
    assert data["notes"]["settings_error"] == "讀設定失敗（測試）"
    assert data["notes"]["settings"] == live.EMPTY_SETTINGS


def test_分頁不存在是沒設定_不是錯誤(monkeypatch, fake_st):
    monkeypatch.setattr(source.exp_universe, "load_pool_codes", lambda values, oauth_client=None: dict(_OK_POOL))
    monkeypatch.setattr(source.settings_store, "load_user_settings",
                        lambda values: {"rows": {}, "bad_rows": [], "broken_keys": [], "blank_rows": 0,
                                        "tab_missing": True})
    data = source.load_live()
    assert data["notes"]["settings_error"] is None and data["notes"]["settings"] == live.EMPTY_SETTINGS


def test_秘密值取自st_secrets_環境變數與登入權杖_交給L2(monkeypatch, fake_st):
    key, token = _rnd.token_hex(12), _rnd.token_hex(12)
    fake_st.secrets = {"FRED_API_KEY": key}
    fake_st.session_state = {"gsheet_tokens": {"access_token": token}}
    got = {}
    monkeypatch.setattr(source.exp_universe, "load_pool_codes",
                        lambda values, oauth_client=None: got.setdefault("pool", list(values)) and dict(_OK_POOL))
    monkeypatch.setattr(source.settings_store, "load_user_settings",
                        lambda values: got.setdefault("settings", list(values)) and _settings_rows())
    monkeypatch.setattr(source.settings_store, "save_setting_for_page",
                        lambda k, v, kind, values: got.setdefault("save", (k, v, kind, list(values))) and
                        {"status": "saved", "key": k})
    source.load_live()
    assert key in got["pool"] and token in got["pool"] and key in got["settings"]
    out = source.save_setting("exp_watchlist", json.dumps(["A01"]), "list")
    assert out["status"] == "saved"
    assert got["save"][:3] == ("exp_watchlist", '["A01"]', "list") and key in got["save"][3]


def test_source不import_fixtures():
    import ast

    tree = ast.parse(pathlib.Path(source.__file__).read_text(encoding="utf-8"))
    names = [a.name for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom)) for a in n.names]
    assert names and "fixtures" not in names


# ───────────────────────── 2026-10-14 C2 接線 ─────────────────────────

_POOL8 = dict(_OK_POOL, codes=list(WF.CODES))


def test_兩段取數_基本資料取全部母體_淨值只取篩選後會列出的檔(monkeypatch, fake_st, l2_calls):
    monkeypatch.setattr(source.exp_universe, "load_pool_codes", lambda values, oauth_client=None: dict(_POOL8))
    rules = json.dumps([{"field": "dividend_policy", "op": "等於", "value": "dist"}], ensure_ascii=False)
    monkeypatch.setattr(source.settings_store, "load_user_settings",
                        lambda values: _settings_rows(exp_filter_rules=rules))
    data = source.load_live()
    assert l2_calls["profiles"] == [list(WF.CODES)]
    nav_codes = [f["fund_code"] for f in l2_calls["nav"][0]]
    assert "G07" in nav_codes                                         # 配息方式取數失敗 → 無法判定，照列、照取
    f06 = next(f for f in l2_calls["nav"][0] if f["fund_code"] == "F06")
    assert f06["declared_ccy"] is None and f06["declared_ccy_source"] is None   # 幣別未確定 → 交資料層隔離
    a01 = next(f for f in l2_calls["nav"][0] if f["fund_code"] == "A01")
    assert (a01["declared_ccy"], a01["declared_ccy_source"]) == ("USD", "meta:MoneyDJ+TDCC")
    assert a01["chain_code"] == "A01" and a01["portal"] == ""
    assert data["notes"]["cells"]["A01"]["div_ratio_pct"]["text"] is None
    assert data["dataset"]["div_ratio_pct"]["A01"] == pytest.approx(6.0)


def test_篩選後列不到的檔_不取淨值(monkeypatch, fake_st, l2_calls):
    monkeypatch.setattr(source.exp_universe, "load_pool_codes", lambda values, oauth_client=None: dict(_POOL8))
    rules = json.dumps([{"field": "fund_code", "op": "等於", "value": "A01"}], ensure_ascii=False)
    monkeypatch.setattr(source.settings_store, "load_user_settings",
                        lambda values: _settings_rows(exp_filter_rules=rules))
    source.load_live()
    assert [[f["fund_code"] for f in funds] for funds in l2_calls["nav"]] == [["A01"]]


def test_基本資料與淨值吃同一個now_畫面的今天由它而來(monkeypatch, fake_st, l2_calls):
    monkeypatch.setattr(source.exp_universe, "load_pool_codes", lambda values, oauth_client=None: dict(_POOL8))
    rules = json.dumps([{"field": "fund_code", "op": "等於", "value": "A01"}], ensure_ascii=False)
    monkeypatch.setattr(source.settings_store, "load_user_settings",
                        lambda values: _settings_rows(exp_filter_rules=rules))
    source.load_live()
    (kind1, now1), (kind2, now2) = l2_calls["now"]
    assert (kind1, kind2) == ("profile", "nav") and now1 is now2
    assert now1.tzinfo is not None and now1.utcoffset().total_seconds() == 8 * 3600


def test_今天固定為fixture設計日_不依賴系統日期(monkeypatch, fake_st, l2_calls):
    monkeypatch.setattr(source.exp_universe, "load_pool_codes", lambda values, oauth_client=None: dict(_POOL8))
    monkeypatch.setattr(source.settings_store, "load_user_settings", lambda values: _settings_rows())
    source.load_live()
    assert [now.date() for _, now in l2_calls["now"]] == [WF.TODAY]


def test_沒有條件_不取淨值(monkeypatch, fake_st, l2_calls):
    monkeypatch.setattr(source.exp_universe, "load_pool_codes", lambda values, oauth_client=None: dict(_POOL8))
    monkeypatch.setattr(source.settings_store, "load_user_settings", lambda values: _settings_rows())
    source.load_live()
    assert l2_calls["profiles"] == [list(WF.CODES)] and l2_calls["nav"] == []


def test_每一格的原因用秘密值遮蔽(monkeypatch, fake_st, l2_calls):
    fake_st.secrets = {"FRED_API_KEY": WF.SECRET}
    monkeypatch.setattr(source.exp_universe, "load_pool_codes", lambda values, oauth_client=None: dict(_POOL8))
    rules = json.dumps([{"field": "fund_code", "op": "等於", "value": "G07"}], ensure_ascii=False)
    monkeypatch.setattr(source.settings_store, "load_user_settings",
                        lambda values: _settings_rows(exp_filter_rules=rules))
    data = source.load_live()
    cells = data["notes"]["cells"]["G07"]
    flat = json.dumps(cells, ensure_ascii=False)
    assert WF.SECRET not in flat and "‹已遮蔽›" in cells["nav_date"]["text"]


def test_代碼對照表讀不到_記log_摘要據實(monkeypatch, fake_st, l2_calls, caplog):
    fake_st.secrets = {"FRED_API_KEY": WF.SECRET}
    monkeypatch.setattr(source.exp_universe, "load_pool_codes", lambda values, oauth_client=None: dict(_POOL8))
    monkeypatch.setattr(source.settings_store, "load_user_settings", lambda values: _settings_rows())

    def boom(codes):
        raise OSError(f"讀不到對照表 {WF.SECRET}")

    monkeypatch.setattr(source.fund_keys, "resolve_full_keys", boom)
    with caplog.at_level("ERROR", logger=source.__name__):
        data = source.load_live()
    assert any("代碼對照表讀取失敗" in r.getMessage() and WF.SECRET not in r.getMessage() for r in caplog.records)
    # 修正輪 3（獨立稽核小修）：log 帶 traceback（找得到出錯的那一行），而且 traceback 同樣遮蔽 ——
    # 以 handler 實際會寫出的字串（`Formatter().format`，含 exc_info 附加的段落）檢查，不只看 getMessage()。
    import logging

    written = "\n".join(logging.Formatter().format(r) for r in caplog.records)
    assert "Traceback (most recent call last)" in written and "in boom" in written
    assert WF.SECRET not in written and "‹已遮蔽›" in written
    assert data["notes"]["wiring_error"].startswith("代碼對照表讀取失敗")
    model = live.build_live_model(data, save_wired=True)
    from ui_v2.exp import logic
    # 合併修正輪 D4：驗卡內實際印出的失敗行（summary 在層 2 核心卡不上畫面）。
    notes = logic.find_block(model, "EXP-2")["notes"]
    assert len(notes) == 1 and notes[0].startswith("fund_profile：⛔ 取數失敗：代碼對照表讀取失敗：OSError")


def test_代碼對照結果形狀不對_照常raise_不當成讀取失敗(monkeypatch, fake_st, l2_calls):
    monkeypatch.setattr(source.exp_universe, "load_pool_codes", lambda values, oauth_client=None: dict(_POOL8))
    monkeypatch.setattr(source.settings_store, "load_user_settings", lambda values: _settings_rows())
    monkeypatch.setattr(source.fund_keys, "resolve_full_keys", lambda codes: {"rows": []})   # 少了 results
    with pytest.raises(KeyError):
        source.load_live()


def test_代碼對照表讀不到_整批取數失敗_訊息遮蔽(monkeypatch, fake_st, l2_calls):
    fake_st.secrets = {"FRED_API_KEY": WF.SECRET}
    monkeypatch.setattr(source.exp_universe, "load_pool_codes", lambda values, oauth_client=None: dict(_POOL8))
    monkeypatch.setattr(source.settings_store, "load_user_settings", lambda values: _settings_rows())

    def boom(codes):
        raise OSError(f"讀不到對照表 {WF.SECRET}")

    monkeypatch.setattr(source.fund_keys, "resolve_full_keys", boom)
    data = source.load_live()
    message = data["dataset"]["errors"]["fund_profile"]
    assert message.startswith("代碼對照表讀取失敗：OSError: 讀不到對照表") and WF.SECRET not in message
    assert data["dataset"]["fund_profile"] == [] and l2_calls["profiles"] == []


def test_母體讀不到_不取基本資料也不取淨值(monkeypatch, fake_st, l2_calls):
    monkeypatch.setattr(source.exp_universe, "load_pool_codes",
                        lambda values, oauth_client=None: {"status": "failed", "backend": "x", "codes": [],
                                                           "dropped_blank": 0, "duplicates": 0, "message": "boom"})
    monkeypatch.setattr(source.settings_store, "load_user_settings", lambda values: _settings_rows())
    data = source.load_live()
    assert l2_calls == {"keys": [], "profiles": [], "nav": [], "now": []} and data["notes"]["cells"] is None


def test_扣下代碼清單是封閉的_含幣別未確定():
    exp_nav = pytest.importorskip("services.v2_tables.exp_nav")
    nav_dividend = pytest.importorskip("services.v2_tables.nav_dividend")
    assert source._NAV_UNAVAILABLE_WITHHELD == {
        nav_dividend.WITHHELD_CCY_MISSING: None, nav_dividend.WITHHELD_CCY_CONFLICT: None,
        nav_dividend.WITHHELD_FETCHED_AT_MISSING: None, nav_dividend.WITHHELD_FETCHED_AT_FUTURE: None,
        # ~~exp_nav.TEXT_CCY_UNDETERMINED~~ → 2026-10-14 修正輪（P 必修 2；有意識的更正，不是漏刪）：
        # L2 原文含內部名稱 `declared_ccy_source`，畫面改用 `live.TEXT_CCY_UNDETERMINED`（白話）。
        exp_nav.WITHHELD_CCY_UNDETERMINED: live.TEXT_CCY_UNDETERMINED}
    assert "declared_ccy_source" not in live.TEXT_CCY_UNDETERMINED
    assert nav_dividend.WITHHELD_INPUT_CONFLICT not in source._NAV_UNAVAILABLE_WITHHELD
