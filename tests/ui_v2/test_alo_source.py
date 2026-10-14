# -*- coding: utf-8 -*-
"""ui_v2/alo/source.py 的接縫測試（fast lane；不打網路、不需要 streamlit 執行期）。

依據 docs/v2/49_data_integration_plan.md §3.3（`source.py` 那一列）、§4.7 第 2 點，
以及 ACCEPTANCE.md 七（秘密值在 L3 讀好再傳進 L2；遮蔽在寫出點做一次）。
L2 與 `st` 一律以替身注入（monkeypatch `source` 模組上的引用），不呼叫任何 L1。
"""

from __future__ import annotations

import json
import pathlib
import sys
import types

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

from ui_v2.alo import fixtures, live, logic  # noqa: E402

source = pytest.importorskip("ui_v2.alo.source")  # 需要 L1 的相依（streamlit、gspread 等）
pd = pytest.importorskip("pandas")

_CORE, _SAT = fixtures.CORE, fixtures.SATELLITE

_HOLDING = {
    "holding_id": "P001|AAAA|1", "policy_id": "P001", "fund_code": "AAAA",
    "fund_name": "某檔基金", "ccy": "TWD", "units_shares": 1000.0,
    "cost_orig_ccy": 700000.0, "cost_twd": 700000, "opened_on": "2021-04-01",
    "bucket": _CORE, "last_synced_at": "2026-09-23T04:00:00Z",
}
_POLICY = {
    "policy_id": "P001", "policy_name": "某張保單", "issuer": "某發行單位", "ccy": "TWD",
    "premium_paid_twd": 1000000, "fee_rate_pct": None, "opened_on": "2021-03-15",
    "status": "active",
}
_MI_ROW = {
    "indicator_key": "fx_twd_per_usd", "obs_date": "2026-09-22", "release_date": "2026-09-23",
    "value_num": 32.0, "value_unit": "TWD/USD", "source_tier": "市場指標",
    "is_revised": False, "fetched_at": "2026-09-23T01:30:00Z",
}


def _tables(**over):
    out = {"holding": [dict(_HOLDING)], "policy": [dict(_POLICY)], "direct": [], "warnings": [],
           "read_estimate": {"message": "（讀取量診斷）"}}
    for name in source._SKIP_GROUPS:
        out.setdefault(name, [])
    out.update(over)
    return out


def _settings(**values):
    rows = {key: {"setting_key": key, "setting_value": text, "value_kind": "list",
                  "updated_at": "2026-09-20T06:00:00Z"}
            for key, text in values.items()}
    return {"rows": rows, "bad_rows": [], "broken_keys": [], "blank_rows": 0, "tab_missing": False}


_GOOD_SETTINGS = dict(
    alo_target_weights=json.dumps([{"bucket": _CORE, "weight_ratio": 0.6},
                                   {"bucket": _SAT, "weight_ratio": 0.4}], ensure_ascii=False),
    alo_tolerance_pp="4",
    alo_basis=logic.BASIS_COST,
    alo_bucket_names=json.dumps([_CORE, _SAT], ensure_ascii=False),
)


@pytest.fixture
def wired(monkeypatch):
    """把 source 模組上的 `st` 與兩個 L2 模組全換成替身；預設全部成功。"""
    st = types.SimpleNamespace(secrets={}, session_state={})
    monkeypatch.setattr(source, "st", st)
    # ⚠️ 秘密值**逐呼叫點**記下來，不是只記一個。紅隊 2026-09-28 突變 M-S 證明：
    # 只記其中一個時，另外兩個呼叫點改成不傳秘密值，962 條測試沒有一條會紅 ——
    # 而那是一次**真的**秘密值外洩回歸（L2 的 `masker([])` 遮不掉任何東西，
    # 失敗訊息會原樣帶出 `SETTINGS_SHEET_ID`，見 ACCEPTANCE.md 七）。
    # ⛔ 不要改成「記最後一次」：那只是把 1 換成另一個 1。
    state = {"tables": _tables(), "settings": _settings(**_GOOD_SETTINGS),
             "indicators": {"rows": [dict(_MI_ROW)]}, "secret_values": {}}

    def _record(name, values):
        state["secret_values"][name] = values

    def _load_alo_tables(values):
        _record("alo_holdings.load_alo_tables", values)
        got = state["tables"]
        if isinstance(got, Exception):
            raise got
        return got

    def _load_user_settings(values):
        _record("settings_store.load_user_settings", values)
        got = state["settings"]
        if isinstance(got, Exception):
            raise got
        return got

    def _load_market_indicator(values):
        _record("settings_store.load_market_indicator", values)
        got = state["indicators"]
        if isinstance(got, Exception):
            raise got
        return got

    monkeypatch.setattr(source.alo_holdings, "load_alo_tables", _load_alo_tables)
    monkeypatch.setattr(source.settings_store, "load_user_settings", _load_user_settings)
    monkeypatch.setattr(source.settings_store, "load_market_indicator", _load_market_indicator)

    # ── 2026-10-13 淨值（A 鏈，同 hld）與非美元匯率（Q9）：真的 L2，只換最底下的取數 ──
    # 代碼對照：`key_fail` 裡的代碼回 ok=False；`resolve` 設成例外時 `resolve_full_keys` 直接拋。
    state.update(key_fail=(), resolve=None, series={}, chain_calls=[], fx_calls=[], fx={}, nav_table=None,
                 key_inputs=None, nav_error_token="上游逾時")

    def _resolve(codes, **_kw):
        state["key_inputs"] = list(codes)
        if isinstance(state["resolve"], Exception):
            raise state["resolve"]
        fail = state["key_fail"]
        return {"results": [{"input": c, "ok": c not in fail, "full_key": None if c in fail else "FK-" + c,
                             "portal": None if c in fail else "", "parsed_code": c,
                             "mapping_hit": c not in fail, "error": "查不到" if c in fail else None}
                            for c in codes], "provenance": {}}

    real_build = source.nav_dividend.build_nav_table

    def _build(funds, **kw):
        state["nav_table"] = real_build([dict(f) for f in funds], **kw)
        return state["nav_table"]

    def _fetch_nav(chain_code, full_key):
        state["chain_calls"].append((chain_code, full_key))
        got = state["series"].get(full_key)
        if got is None:
            return None, state["nav_error_token"]
        return got, None

    def _fetch_fx(ticker, *args, **kwargs):
        state["fx_calls"].append(ticker)
        return state["fx"][ticker]

    monkeypatch.setattr(source.fund_keys, "resolve_full_keys", _resolve)
    monkeypatch.setattr(source.nav_dividend, "build_nav_table", _build)
    monkeypatch.setattr(source.nav_dividend, "fetch_nav_chain_with_error", _fetch_nav)
    monkeypatch.setattr(source.market_indicator, "fetch_yf_close_with_error", _fetch_fx)
    # 第二輪 N-b：淨值日新鮮度以台灣日曆日判，固定「今天」（替身淨值日 2026-09-23 → 距今 2 天）。
    monkeypatch.setattr(source, "_today_tw", lambda: _TODAY)
    return state


_TODAY = __import__("datetime").date(2026, 9, 25)


_FAKE_SECRET = "zz-fake-secret-a10c"


def _nav_series(value, day="2026-09-23"):
    s = pd.Series([value], index=[pd.Timestamp(day)])
    s.attrs = {"source": "MoneyDJ:x", "fetched_at": "2026-09-23T01:30:00+00:00"}
    return s


def _mv_settings():
    return _settings(**dict(_GOOD_SETTINGS, alo_basis=logic.BASIS_MV))


# ═══════════════════════ dataset 的形狀 ═══════════════════════


def test_dataset與fixtures同形_而且build_page_model吃得下(wired):
    out = source.load_live()
    assert set(out) == {"dataset", "notes"}
    assert set(out["dataset"]) == set(fixtures.scenario("full"))
    model = logic.build_page_model(out["dataset"])
    assert model["title"] == logic.PAGE_TITLE
    assert logic.find_block(model, "ALO-2")["_rows"]
    assert out["dataset"]["holding"] == [_HOLDING] and out["dataset"]["policy"] == [_POLICY]
    assert out["dataset"]["market_indicator"] == [_MI_ROW]
    assert out["dataset"]["errors"] == {} and out["dataset"]["save_errors"] == {}


def test_成本基準不取淨值_空列表而且不進errors(wired):
    """~~`settings_store.PENDING_TABLES` 列了 `nav` —— 那是「還沒接」，不是「讀失敗」。~~
    → 2026-10-09 客戶裁示 Q1（不存 NAV、各頁需要時即時抓取）：L2 已把 `nav` 移出 `PENDING_TABLES`；
    但本頁取淨值未獲授權（裁示只到 hld、set），`nav` 照舊空列表、不進 `errors`（有意識的更正，不是漏刪）。
    → 2026-10-13 客戶裁示（資產配置必須是真資料）：本頁取淨值，但**只在已存基準為市值時**取；
    成本基準用不到淨值，不取、不呼叫代碼對照（舊名 `test_本頁不取淨值_空列表而且不進errors`；有意識的更正，不是漏刪）。"""
    out = source.load_live()
    assert out["dataset"]["nav"] == []
    assert "nav" not in out["dataset"]["errors"]
    assert wired["key_inputs"] is None and wired["chain_calls"] == []
    # ~~assert "nav" in out["notes"]["pending_tables"]~~
    assert out["notes"]["pending_tables"] == ["dividend"]


def test_市值基準_淨值取數失敗_原文經遮蔽進errors_nav_畫取數失敗_不偽造不退回成本(wired):
    """~~`test_市值基準下整片資料未備_不偽造不退回成本`：本頁不取淨值 ⇒ 整片「nav 尚無資料」。~~
    → 2026-10-13：本頁取淨值；替身的 A 鏈對每一檔都回失敗 ⇒ 那是取數失敗，不是資料未備（有意識的更正，不是漏刪）。"""
    source.st.secrets = {"SETTINGS_SHEET_ID": _FAKE_SECRET}
    wired["settings"] = _mv_settings()
    wired["nav_error_token"] = f"上游逾時 token={_FAKE_SECRET}"
    out = source.load_live()
    error = out["dataset"]["errors"]["nav"]
    assert error.startswith("AAAA：上游逾時") and _FAKE_SECRET not in error   # 原文經遮蔽才進 errors
    model = logic.build_page_model(out["dataset"])
    block = logic.find_block(model, "ALO-2")
    assert block["placeholder"]["text"] == logic.fetch_failed_text(error)
    assert block["_rows"] == []                       # 不拿成本值頂替
    # ALO-4 的比重基準仍是二選一，兩個選項都在（不准灰掉或移除）。
    basis_field = logic.find_block(model, "ALO-4")["inputs"][0]
    assert basis_field["_options"] == (logic.BASIS_COST, logic.BASIS_MV)


def test_市值基準_新臺幣淨值取到_市值照算(wired):
    wired["settings"] = _mv_settings()
    wired["series"] = {"FK-AAAA": _nav_series(712.5)}
    out = source.load_live()
    assert out["dataset"]["errors"] == {}
    assert [(r["fund_code"], r["nav_orig_ccy"], r["ccy"]) for r in out["dataset"]["nav"]] == [("AAAA", 712.5, "TWD")]
    assert wired["chain_calls"] == [("AAAA", "FK-AAAA")]           # 同 hld：chain_code ＝ parsed_code
    block = logic.find_block(logic.build_page_model(out["dataset"]), "ALO-2")
    assert block["placeholder"] is None
    assert block["_values"][_CORE]["value"] == 1000.0 * 712.5     # 單位數 × 淨值，不乘匯率
    assert wired["fx_calls"] == []


def test_市值基準_美元淨值_乘試算表上不晚於淨值日的匯率(wired):
    wired["tables"] = _tables(holding=[dict(_HOLDING, ccy="USD")])
    wired["settings"] = _mv_settings()
    wired["series"] = {"FK-AAAA": _nav_series(15.2)}
    out = source.load_live()
    block = logic.find_block(logic.build_page_model(out["dataset"]), "ALO-2")
    assert block["_values"][_CORE]["value"] == 1000.0 * 15.2 * 32.0
    assert wired["fx_calls"] == []                                  # 美元走試算表那一份，本頁不另取


def test_市值基準_歐元_閘門關閉_不取數_畫缺換算匯率鍵_不崩頁(wired):
    assert source.market_indicator.FX_OBS_DATE_RULE_VERIFIED is False
    wired["tables"] = _tables(holding=[dict(_HOLDING, ccy="EUR")])
    wired["settings"] = _mv_settings()
    wired["series"] = {"FK-AAAA": _nav_series(15.2)}
    out = source.load_live()
    assert wired["fx_calls"] == []                                  # 閘門關閉：EURTWD=X 不取數
    assert out["notes"]["fx_pending"] == {"fx_twd_per_eur": source.market_indicator.PENDING_FX_OBS_DATE_RULE}
    assert "market_indicator" not in out["dataset"]["errors"]       # pending 不是失敗
    model = logic.build_page_model(out["dataset"])
    block = logic.find_block(model, "ALO-2")
    assert block["placeholder"]["text"] == "⬜ 資料未備：缺換算匯率 fx_twd_per_eur"   # 只有一種理由 → 來源缺
    assert block["placeholder"]["_empty_kind"] == "來源缺"


def test_市值基準_歐元_閘門打開_取EURTWD換算(wired, monkeypatch):
    monkeypatch.setattr(source.market_indicator, "FX_OBS_DATE_RULE_VERIFIED", True)
    wired["tables"] = _tables(holding=[dict(_HOLDING, ccy="EUR")])
    wired["settings"] = _mv_settings()
    wired["series"] = {"FK-AAAA": _nav_series(15.2)}
    # 2026-10-13：替身改成匯率日線的真實形狀（夏令倫敦 00:00 ＝ UTC 前一天 23:00）並帶 L1 新增的
    # `exchange_tz`（客戶裁示：觀測日以交易所時區為準）；~~索引 `2026-09-22`／`2026-09-24`（UTC 午夜）~~
    # 在新規則下倫敦當地時刻是 01:00、且缺時區會整鍵不寫，故換例（不是漏刪）。觀測日仍是 09-22／09-24。
    # ~~兩根（倫敦 09-22 → 35.0、09-24 → 99.0）~~ → 2026-10-14（客戶裁示匯率採「前一交易日收盤」語意；
    # 有意識的更正，不是漏刪）：日 K 日期 D 的值寫成觀測日 D 的前一個平日，且外匯有最少根數門檻
    # （`FX_MIN_REFERENCE_VOTES`，判讀 A 的 A1），兩根整鍵不寫。改為 23 個倫敦平日 00:00 根（夏令＝UTC 前一天 23:00）：
    # D＝09-24（四）→ 觀測日 09-23（＝淨值日）35.0；D＝09-25（五）→ 觀測日 09-24（晚於淨值日）99.0；其餘 34.0。
    # 取得時間改為 09-28，讓 D＝09-25 那根已收盤（否則它是未收盤根，「晚於淨值日不取」就測不到）。
    days = pd.bdate_range(end="2026-09-25", periods=23)
    values = [35.0 if d.strftime("%m-%d") == "09-24" else 99.0 if d.strftime("%m-%d") == "09-25" else 34.0
              for d in days]
    fx = pd.Series(values, index=[d - pd.Timedelta(hours=1) for d in days], name="EURTWD=X")
    fx.attrs = {"source": "Yahoo:EURTWD=X", "fetched_at": "2026-09-28T06:00:00+00:00",
                "exchange_tz": "Europe/London"}
    wired["fx"] = {"EURTWD=X": (fx, None)}
    out = source.load_live()
    assert wired["fx_calls"] == ["EURTWD=X"]
    assert {r["indicator_key"] for r in out["dataset"]["market_indicator"]} == {"fx_twd_per_usd", "fx_twd_per_eur"}
    block = logic.find_block(logic.build_page_model(out["dataset"]), "ALO-2")
    fx_rows = {r["obs_date"]: r["value_num"] for r in out["dataset"]["market_indicator"]
               if r["indicator_key"] == "fx_twd_per_eur"}
    assert fx_rows["2026-09-23"] == 35.0 and fx_rows["2026-09-24"] == 99.0      # 觀測日＝日 K 日期的前一個平日
    assert block["_values"][_CORE]["value"] == 1000.0 * 15.2 * 35.0   # 09-24 那筆晚於淨值日，不取


def test_市值基準_歐元_閘門打開_取數失敗_原文經遮蔽進errors_market_indicator(wired, monkeypatch):
    monkeypatch.setattr(source.market_indicator, "FX_OBS_DATE_RULE_VERIFIED", True)
    source.st.secrets = {"SETTINGS_SHEET_ID": _FAKE_SECRET}
    wired["tables"] = _tables(holding=[dict(_HOLDING, ccy="EUR")])
    wired["settings"] = _mv_settings()
    wired["series"] = {"FK-AAAA": _nav_series(15.2)}
    wired["fx"] = {"EURTWD=X": (pd.Series(dtype=float), f"fetch_url returned None token={_FAKE_SECRET}")}
    out = source.load_live()
    error = out["dataset"]["errors"]["market_indicator"]
    assert error.startswith("fx_twd_per_eur：") and _FAKE_SECRET not in error
    block = logic.find_block(logic.build_page_model(out["dataset"]), "ALO-2")
    assert block["placeholder"]["_empty_kind"] == "系統錯誤"           # ALO-GAP-缺匯率從嚴


def test_市值基準_代碼對照查不到與幣別衝突_那一檔資料未備_不是取數失敗(wired):
    wired["tables"] = _tables(holding=[
        dict(_HOLDING),
        dict(_HOLDING, policy_id="P002", ccy="USD"),                   # 同檔兩列幣別不同 → L2 ccy_conflict
        dict(_HOLDING, fund_code="BBBB", holding_id="P001|BBBB|1"),
    ])
    wired["key_fail"] = ("BBBB",)
    wired["settings"] = _mv_settings()
    wired["series"] = {"FK-AAAA": _nav_series(15.2)}
    out = source.load_live()
    assert out["dataset"]["nav"] == [] and "nav" not in out["dataset"]["errors"]
    assert wired["nav_table"]["withheld"] == {"AAAA": source.nav_dividend.WITHHELD_CCY_CONFLICT}
    assert out["notes"]["nav"]["key_failed"] == ["BBBB"]
    block = logic.find_block(logic.build_page_model(out["dataset"]), "ALO-2")
    assert block["placeholder"]["text"] == logic.empty_source_text(["nav"])


def test_市值基準_代碼對照本身拋例外_原文經遮蔽進errors_nav_整頁畫得完(wired):
    """第二輪 N-a：只接取數類例外（OSError 家族）；~~RuntimeError~~ 改用 ConnectionError（有意識的更正，不是漏刪）。"""
    source.st.secrets = {"SETTINGS_SHEET_ID": _FAKE_SECRET}
    wired["settings"] = _mv_settings()
    wired["resolve"] = ConnectionError(f"對照表讀不到 {_FAKE_SECRET}")
    out = source.load_live()
    error = out["dataset"]["errors"]["nav"]
    assert error.startswith("ConnectionError: 對照表讀不到") and _FAKE_SECRET not in error
    assert logic.build_page_model(out["dataset"])["title"] == logic.PAGE_TITLE


def test_淨值扣下清單與hld同一份_不含input_conflict():
    hld_source = pytest.importorskip("ui_v2.hld.source")
    assert source._NAV_UNAVAILABLE_WITHHELD == hld_source._NAV_UNAVAILABLE_WITHHELD
    assert source.nav_dividend.WITHHELD_INPUT_CONFLICT not in source._NAV_UNAVAILABLE_WITHHELD


def test_dataset的errors鍵一律在build_page_model認得的那一組裡(wired):
    wired["tables"] = source.alo_holdings.PolicySupplementError("上游 503", code="api")
    wired["settings"] = source.settings_store.SettingsSheetError("讀不到設定", code="api")
    wired["indicators"] = source.settings_store.SettingsSheetError("讀不到市場指標", code="api")
    errors = source.load_live()["dataset"]["errors"]
    assert set(errors) <= set(logic.FETCHABLE_TABLES)


# ═══════════════════════ 逐表失敗：一個壞不拖垮其餘 ═══════════════════════


def test_holding與policy同時失敗_兩個鍵一起標(wired):
    """示範模式把兩者當可獨立失敗的鍵，正式模式它們是同一次呼叫的產物 —— 分不開就不假裝分得開。"""
    wired["tables"] = source.alo_holdings.PolicySupplementError("上游 503", code="api")
    out = source.load_live()
    assert out["dataset"]["errors"] == {"holding": "上游 503", "policy": "上游 503"}
    assert out["dataset"]["holding"] == [] and out["dataset"]["policy"] == []
    # 其餘兩張表照常交出來
    assert out["dataset"]["market_indicator"] == [_MI_ROW]
    assert out["dataset"]["user_setting"][0]["setting_value"] is not None
    assert logic.build_page_model(out["dataset"])["title"] == logic.PAGE_TITLE


def test_設定讀不到_只標user_setting_其餘照常(wired):
    wired["settings"] = source.settings_store.SettingsSheetError("讀不到設定", code="api")
    out = source.load_live()
    assert out["dataset"]["errors"] == {"user_setting": "讀不到設定"}
    assert out["dataset"]["user_setting"] == []       # 同 fixtures 的 settingfail 形狀
    assert out["dataset"]["holding"] == [_HOLDING]
    assert logic.settings_failure(out["dataset"]) is not None


def test_市場指標讀不到_只標market_indicator(wired):
    wired["indicators"] = source.settings_store.SettingsSheetError("讀不到市場指標", code="api")
    out = source.load_live()
    assert out["dataset"]["errors"] == {"market_indicator": "讀不到市場指標"}
    assert out["dataset"]["market_indicator"] == []


def test_設定值壞掉_走取數失敗那條路_不畫成尚未設定(wired):
    """⚠️ 本條原本寫成 `A or B`，而 B 在這個情境恆為真 ⇒ 整條恆真、A 永遠不被強制
    （紅隊 2026-09-28 實測：拿掉 `logic.py` 兩處 failure 守衛，本條仍 1 passed）。
    現改成兩件事各自斷言。"""
    wired["settings"] = _settings(**dict(_GOOD_SETTINGS, alo_tolerance_pp="四"))
    out = source.load_live()
    dataset = out["dataset"]
    assert "alo_tolerance_pp" in dataset["errors"]["user_setting"]
    assert dataset["user_setting"] == []
    # (1) 它必須被當成「取數失敗」，不是「沒設定」
    assert logic.settings_failure(dataset) is not None
    # (2) 讀設定的每一塊都不准出現「未設定」，而且不准畫輸入欄
    #     （判準同既有的 test_alo_logic.py::test_user_setting取數失敗_不說成未設定_不畫輸入欄）
    model = logic.build_page_model(dataset)
    for code in ("ALO-1", "ALO-3", "ALO-4"):
        block = logic.find_block(model, code)
        assert logic.TEXT_UNSET not in logic.collect_ui_strings(block), code
        assert block.get("inputs") == [], code


def test_三張表全失敗也畫得完(wired):
    wired["tables"] = source.alo_holdings.PolicySupplementError("上游 503", code="api")
    wired["settings"] = source.settings_store.SettingsSheetError("讀不到設定", code="api")
    wired["indicators"] = source.settings_store.SettingsSheetError("讀不到市場指標", code="api")
    out = source.load_live()
    assert set(out["dataset"]["errors"]) == {"holding", "policy", "user_setting", "market_indicator"}
    assert logic.build_page_model(out["dataset"])["title"] == logic.PAGE_TITLE


# ═══════════════════════ 秘密值與遮蔽 ═══════════════════════


def test_秘密值在L3讀好再傳進L2_本層不自己遮(wired):
    """ACCEPTANCE.md 七：秘密值在 L3 讀（`st.secrets`／環境變數／權杖），遮蔽由 L2 接到 L1 做一次。
    ⚠️ 據實寫明：`POLICY_SHEET_ID`（本頁讀表那一本）**不在**遮蔽字表裡 —— ACCEPTANCE 7.2 丙
    「試算表 ID 不遮」，只有 `SETTINGS_SHEET_ID` 是例外（`50` 第 2 節定案）。本條量的是
    「本層有沒有把讀到的秘密值往下傳」，不是「POLICY_SHEET_ID 會不會被遮」。"""
    import secrets as _rnd

    key = _rnd.token_hex(12)
    source.st.secrets = {"SETTINGS_SHEET_ID": key}
    source.load_live()
    seen = wired["secret_values"]
    assert set(seen) == {"alo_holdings.load_alo_tables",
                         "settings_store.load_user_settings",
                         "settings_store.load_market_indicator"}, seen
    # ⭐ 三個呼叫點**逐一**斷言 —— 少驗任何一個，那一個就可以悄悄不傳秘密值而全綠（紅隊 M-S）。
    for call, values in seen.items():
        assert values is not None, call
        assert key in values, f"{call} 沒有把秘密值傳進 L2 ⇒ L2 的 masker 遮不掉它"


def test_notes原樣轉交給下一輪_不判讀(wired):
    notes = source.load_live()["notes"]
    assert notes["mask_token"] == source.masking.MASK
    assert notes["read_estimate"] == {"message": "（讀取量診斷）"}
    assert "alo" in notes["pages_reading_settings"]
    assert set(notes["skipped"]) == set(source._SKIP_GROUPS)


def test_load_live的save_errors恆空_存檔只接ALO1與ALO4(wired):
    """2026-10-09 更正（舊名 `test_本輪不接寫_save_errors恆空`）：舊版另斷言「三枚存檔全部停用」——
    那正是客戶 2026-10-09 裁示要改掉的行為（ALO-1／ALO-4 接上寫入）。`save_errors` 仍由本函式回空：
    存檔成敗是按鈕那一次的事，由 page.py 記在 session 再併進來，不是讀表的結果。"""
    assert source.load_live()["dataset"]["save_errors"] == {}
    model = live.apply_live_notes(logic.build_page_model(source.load_live()["dataset"]),
                                  wired_keys=live.SAVE_WIRED_KEYS)
    saves = {b["_keys"]: b for block in model["blocks"] for b in (block.get("buttons") or ()) if b["_writes"]}
    assert set(saves) == {("alo_target_weights", "alo_tolerance_pp"), ("alo_basis", "alo_bucket_names"),
                          ("alo_scenario_input",)}
    assert saves[("alo_target_weights", "alo_tolerance_pp")]["_enabled"]
    assert saves[("alo_basis", "alo_bucket_names")]["_enabled"]
    assert not saves[("alo_scenario_input",)]["_enabled"]
    assert saves[("alo_scenario_input",)]["disabled_reason"] == live.SAVE_DISABLED_REASON


def test_notes交出各鍵的試算表原字串_讀失敗時為空(wired):
    """存檔時沒動過的欄位寫回這個原字串（2026-10-09 稽核回修）。"""
    raw = source.load_live()["notes"]["setting_raw"]
    assert raw == {**{k: None for k in live.SETTING_KEYS}, **_GOOD_SETTINGS}
    wired["settings"] = source.settings_store.SettingsSheetError("讀不到設定", code="api")
    assert source.load_live()["notes"]["setting_raw"] == {}


def test_save_setting_呼叫同一個L2函式_帶秘密值_回傳原樣交出(wired, monkeypatch):
    """體例同 `ui_v2/set/source.py::save_setting`：同一個 L2 `save_setting_for_page`、同一份秘密值。"""
    import secrets as _rnd

    key = _rnd.token_hex(12)
    monkeypatch.setattr(source.st, "secrets", {"SETTINGS_SHEET_ID": key})
    calls = []

    def _save(setting_key, setting_value, value_kind, values):
        calls.append((setting_key, setting_value, value_kind, values))
        return {"status": "failed", "key": setting_key, "message": "（已遮蔽的原文）"}

    monkeypatch.setattr(source.settings_store, "save_setting_for_page", _save)
    out = source.save_setting("alo_basis", logic.BASIS_MV, "list")
    assert out == {"status": "failed", "key": "alo_basis", "message": "（已遮蔽的原文）"}
    assert [c[:3] for c in calls] == [("alo_basis", logic.BASIS_MV, "list")]
    assert key in calls[0][3], "沒有把秘密值傳進 L2 ⇒ L2 的 masker 遮不掉它"


def test_save_setting_寫表以外的例外照樣往上拋(wired, monkeypatch):
    def _boom(*args):
        raise RuntimeError("boom")

    monkeypatch.setattr(source.settings_store, "save_setting_for_page", _boom)
    with pytest.raises(RuntimeError, match="boom"):
        source.save_setting("alo_tolerance_pp", "4", "float")


# ═══════════════════════ 2026-10-13 稽核 B2：except 只包取數呼叫；契約錯誤與組輸入錯誤照拋 ═══════════════════════


def test_B2_取數呼叫拋例外_記log_原文經遮蔽進errors(wired, caplog):
    source.st.secrets = {"SETTINGS_SHEET_ID": _FAKE_SECRET}
    wired["settings"] = _mv_settings()
    wired["resolve"] = OSError(f"對照表讀不到 {_FAKE_SECRET}")   # 第二輪 N-a：~~RuntimeError~~ → OSError
    with caplog.at_level("WARNING", logger=source.__name__):
        out = source.load_live()
    assert out["dataset"]["errors"]["nav"].startswith("OSError: 對照表讀不到")
    logged = [r.getMessage() for r in caplog.records if r.name == source.__name__]
    assert logged and "fund_keys.resolve_full_keys" in logged[0]
    assert _FAKE_SECRET not in "".join(logged)                         # log 也只記遮蔽後的原文


def test_B2_build_nav_table拋例外_同樣是取數失敗(wired, monkeypatch):
    wired["settings"] = _mv_settings()

    def boom(funds, **kw):
        raise ConnectionError("A 鏈斷線")

    monkeypatch.setattr(source.nav_dividend, "build_nav_table", boom)
    out = source.load_live()
    assert out["dataset"]["errors"]["nav"] == "ConnectionError: A 鏈斷線"
    assert out["dataset"]["nav"] == []


def test_B2_assemble_nav的契約錯誤照拋_不標成取數失敗(wired, monkeypatch):
    wired["settings"] = _mv_settings()

    def conflict(funds, **kw):
        return {"rows": [], "errors": {}, "withheld": {"AAAA": source.nav_dividend.WITHHELD_INPUT_CONFLICT},
                "skipped": {}, "fetched": {}, "skipped_rows": {}, "provenance": {}}

    monkeypatch.setattr(source.nav_dividend, "build_nav_table", conflict)
    with pytest.raises(ValueError, match="不在本頁約定的清單內"):
        source.load_live()


def test_B2_組輸入時的KeyError照拋(wired, monkeypatch):
    wired["settings"] = _mv_settings()

    def broken(codes, **_kw):
        return {"results": [{"input": c, "ok": True, "full_key": "FK-" + c, "portal": ""} for c in codes]}

    monkeypatch.setattr(source.fund_keys, "resolve_full_keys", broken)      # 少了 parsed_code
    with pytest.raises(KeyError, match="parsed_code"):
        source.load_live()


def test_N1_預存舊序列_在市值基準下不納入_畫資料未備(wired):
    wired["settings"] = _mv_settings()
    s = _nav_series(712.5)
    s.attrs = {"source": source.nav_dividend.CACHE_FALLBACK_SOURCE_PREFIX + "AAAA.json",
               "fetched_at": "2026-09-23T01:30:00+00:00", "cache_updated_at": "2026-09-22T01:30:00+00:00",
               "nav_quality": {"stale": True}}
    wired["series"] = {"FK-AAAA": s}
    out = source.load_live()
    assert wired["nav_table"]["rows"], "前提：L2 有寫列（預存序列的值是真的公布淨值）"
    assert out["dataset"]["nav"] == [] and out["notes"]["nav"]["not_fresh"] == ["AAAA"]
    block = logic.find_block(logic.build_page_model(out["dataset"]), "ALO-2")
    assert block["placeholder"]["text"] == logic.empty_source_text(["nav"])


# ═══════════════════════ 2026-10-13 第二輪 N-a：外層只接取數類例外 ═══════════════════════


def test_Na_L2拋AssertionError_往上拋_不標成取數失敗(wired, monkeypatch):
    wired["settings"] = _mv_settings()

    def broken(funds, **kw):
        raise AssertionError("nav 列的欄位與契約不符：['x']")

    monkeypatch.setattr(source.nav_dividend, "build_nav_table", broken)
    with pytest.raises(AssertionError, match="欄位與契約不符"):
        source.load_live()


def test_Na_對照拋ValueError_往上拋(wired):
    wired["settings"] = _mv_settings()
    wired["resolve"] = ValueError("mapping 的鍵不合格")
    with pytest.raises(ValueError, match="mapping 的鍵不合格"):
        source.load_live()


def test_Na_匯率L2拋ValueError_往上拋(wired, monkeypatch):
    """例：把美元交給 `build_fx_indicator_table` —— 程式錯誤，不是取數失敗。"""
    wired["tables"] = _tables(holding=[dict(_HOLDING, ccy="EUR")])
    wired["settings"] = _mv_settings()
    wired["series"] = {"FK-AAAA": _nav_series(15.2)}
    monkeypatch.setattr(source.live, "fx_ccys_needed", lambda rows: ["USD"])
    with pytest.raises(ValueError, match="不走這裡"):
        source.load_live()


def test_Na_匯率取數拋OSError_才是取數失敗(wired, monkeypatch):
    wired["tables"] = _tables(holding=[dict(_HOLDING, ccy="EUR")])
    wired["settings"] = _mv_settings()
    wired["series"] = {"FK-AAAA": _nav_series(15.2)}

    def down(ccys):
        raise TimeoutError("Yahoo 逾時")

    monkeypatch.setattr(source.market_indicator, "build_fx_indicator_table", down)
    assert source.load_live()["dataset"]["errors"]["market_indicator"] == "TimeoutError: Yahoo 逾時"


# ═══════════════════════ 2026-10-13 第二輪 N-b：淨值日期超過 SSOT 門檻不納入 ═══════════════════════


def test_Nb_門檻是客戶裁示的10天_不是MJ_FRESH_DAYS_YELLOW():
    """~~`test_Nb_門檻引用既有SSOT_不另立數字`：門檻 == MJ_FRESH_DAYS_YELLOW（7）~~
    → 第三輪總管裁定（有意識的更正，不是漏刪）：B 線已有客戶裁示的 10 天（`ui_v2/hld/live.py::NAV_FRESH_DAYS_YELLOW`），
    草稿 §D 明寫不要沿用 MJ_FRESH_DAYS_YELLOW。"""
    from ui_v2 import thresholds
    from ui_v2.hld import live as hld_live
    # 2026-10-13 客戶裁示（10 天單一共用定義）：兩頁同引 `ui_v2/thresholds.py::NAV_NOT_READY_DAYS`
    assert source.live.NAV_MAX_AGE_DAYS == hld_live.NAV_FRESH_DAYS_YELLOW == thresholds.NAV_NOT_READY_DAYS == 10
    assert source.live.thresholds is thresholds
    assert not hasattr(source, "contract")                                 # 不再經 contract 轉交


@pytest.mark.parametrize("utc_instant, taiwan_day, utc_day", [
    # UTC 前一天 16:30 ＝ 台北當天 00:30：台灣日期比 UTC 日期多一天
    ((2026, 10, 12, 16, 30), (2026, 10, 13), (2026, 10, 12)),
    # 跨年也一樣（另一個與今天無關的日期，免得替身時鐘漏接時剛好被真時鐘蒙混過關）
    ((2025, 12, 31, 23, 59), (2026, 1, 1), (2025, 12, 31)),
])
def test_第三輪_today_tw取台灣日曆日_UTC前一天16點半已是台灣隔天(monkeypatch, utc_instant, taiwan_day, utc_day):
    """決定性時鐘：替身把 `now`（帶或不帶時區）、`utcnow`、`today` 全部覆寫成同一個固定的 UTC 時刻，
    該時刻的台灣日期與 UTC 日期不同 → `_today_tw()` 必須回台灣那一天。

    ~~只覆寫 `now()`~~（2026-10-13 稽核：半決定性 —— `_today_tw` 若改用 `utcnow()`，替身沒接住、落到真時鐘，
    在真實日期剛好是台灣那天時照樣會過；有意識的更正，不是漏刪）。現在三種錯誤寫法都會轉紅：
    `utcnow()`、`now(timezone.utc)`、無時區 `now()`（替身模擬伺服器跑在 UTC，與 Streamlit Cloud 相同）。"""
    import datetime as _dt
    instant = _dt.datetime(*utc_instant, tzinfo=_dt.timezone.utc)
    naive_utc = instant.replace(tzinfo=None)
    assert instant.astimezone(source.nav_dividend.MARKET_DATE_TZ).date() == _dt.date(*taiwan_day)  # 前提
    assert naive_utc.date() == _dt.date(*utc_day) != _dt.date(*taiwan_day)                         # 前提：兩者不同

    class _Clock(_dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return naive_utc if tz is None else instant.astimezone(tz)

        @classmethod
        def utcnow(cls):
            return naive_utc

        @classmethod
        def today(cls):
            return naive_utc

    monkeypatch.setattr(source, "datetime", _Clock)
    assert source._today_tw() == _dt.date(*taiwan_day)


def test_Nb_即時取回但淨值日是四個月前_不納入市值_畫資料未備(wired):
    wired["settings"] = _mv_settings()
    s = _nav_series(712.5, day="2026-05-20")
    s.attrs["fetched_at"] = "2026-09-25T01:00:00+00:00"            # 取得時間是今天：不能拿它判新鮮
    wired["series"] = {"FK-AAAA": s}
    out = source.load_live()
    assert wired["nav_table"]["rows"], "前提：L2 有寫列"
    assert out["dataset"]["nav"] == [] and out["notes"]["nav"]["too_old"] == ["AAAA"]
    block = logic.find_block(logic.build_page_model(out["dataset"]), "ALO-2")
    # ~~`== logic.empty_source_text(["nav"])`~~ → 總管 2026-10-13 裁決（狀態更新，不是漏刪）：過期的檔有資料、只是過期，
    # 「nav 尚無資料」不實 ⇒ 改畫「最近淨值已超過 10 日」（天數取共用常數；期望值的 10 寫死，被測的是常數）。
    assert out["dataset"]["nav_not_ready"] == {"codes": ["AAAA"], "days": 10}
    assert block["placeholder"]["text"] == "⬜ 資料未備：最近淨值已超過 10 日"
    assert block["placeholder"]["text"] != logic.empty_source_text(["nav"])


def test_Nb_source交給assemble_nav的是客戶裁示門檻與台灣日曆日(wired, monkeypatch):
    wired["settings"] = _mv_settings()
    seen = {}
    real = source.live.assemble_nav

    def spy(**kw):
        seen.update(kw)
        return real(**kw)

    monkeypatch.setattr(source.live, "assemble_nav", spy)
    source.load_live()
    assert seen["max_age_days"] == source.live.NAV_MAX_AGE_DAYS and seen["today"] == _TODAY
    monkeypatch.undo()
    assert source._today_tw() == __import__("datetime").datetime.now(source.nav_dividend.MARKET_DATE_TZ).date()


def test_稽核D_A2_門檻常數換掉_source交出的天數與畫面字面跟著變(wired, monkeypatch):
    """`nav_not_ready.days` 取 `live.NAV_MAX_AGE_DAYS`（＝共用常數），不是寫死的 10。"""
    monkeypatch.setattr(source.live, "NAV_MAX_AGE_DAYS", 5)
    wired["settings"] = _mv_settings()
    s = _nav_series(712.5, day="2026-05-20")
    s.attrs["fetched_at"] = "2026-09-25T01:00:00+00:00"
    wired["series"] = {"FK-AAAA": s}
    out = source.load_live()
    assert out["dataset"]["nav_not_ready"] == {"codes": ["AAAA"], "days": 5}
    block = logic.find_block(logic.build_page_model(out["dataset"]), "ALO-2")
    assert block["placeholder"]["text"] == "⬜ 資料未備：最近淨值已超過 5 日"
