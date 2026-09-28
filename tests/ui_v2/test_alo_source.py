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
    state = {"tables": _tables(), "settings": _settings(**_GOOD_SETTINGS),
             "indicators": {"rows": [dict(_MI_ROW)]}, "secret_values": None}

    def _load_alo_tables(values):
        state["secret_values"] = values
        got = state["tables"]
        if isinstance(got, Exception):
            raise got
        return got

    def _load_user_settings(values):
        got = state["settings"]
        if isinstance(got, Exception):
            raise got
        return got

    def _load_market_indicator(values):
        got = state["indicators"]
        if isinstance(got, Exception):
            raise got
        return got

    monkeypatch.setattr(source.alo_holdings, "load_alo_tables", _load_alo_tables)
    monkeypatch.setattr(source.settings_store, "load_user_settings", _load_user_settings)
    monkeypatch.setattr(source.settings_store, "load_market_indicator", _load_market_indicator)
    return state


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


def test_nav尚未接上_空列表而且不進errors(wired):
    """`settings_store.PENDING_TABLES` 列了 `nav` —— 那是「還沒接」，不是「讀失敗」。"""
    out = source.load_live()
    assert out["dataset"]["nav"] == []
    assert "nav" not in out["dataset"]["errors"]
    assert "nav" in out["notes"]["pending_tables"]


def test_市值基準下整片資料未備_不偽造不退回成本(wired):
    wired["settings"] = _settings(**dict(_GOOD_SETTINGS, alo_basis=logic.BASIS_MV))
    model = logic.build_page_model(source.load_live()["dataset"])
    block = logic.find_block(model, "ALO-2")
    assert block["placeholder"] is not None
    assert block["placeholder"]["text"] == logic.empty_source_text(["nav"])
    assert block["_rows"] == []                       # 不拿成本值頂替
    # ALO-4 的比重基準仍是二選一，兩個選項都在（不准灰掉或移除）。
    basis_field = logic.find_block(model, "ALO-4")["inputs"][0]
    assert basis_field["_options"] == (logic.BASIS_COST, logic.BASIS_MV)


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
    wired["settings"] = _settings(**dict(_GOOD_SETTINGS, alo_tolerance_pp="四"))
    out = source.load_live()
    assert "alo_tolerance_pp" in out["dataset"]["errors"]["user_setting"]
    assert out["dataset"]["user_setting"] == []
    model = logic.build_page_model(out["dataset"])
    text = "\n".join(str(v) for v in logic.find_block(model, "ALO-1").values())
    assert logic.TEXT_UNSET not in text or logic.settings_failure(out["dataset"]) is not None


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
    assert key in wired["secret_values"], "秘密值沒有傳進 L2 ⇒ L2 遮不掉它"


def test_notes原樣轉交給下一輪_不判讀(wired):
    notes = source.load_live()["notes"]
    assert notes["mask_token"] == source.masking.MASK
    assert notes["read_estimate"] == {"message": "（讀取量診斷）"}
    assert "alo" in notes["pages_reading_settings"]
    assert set(notes["skipped"]) == set(source._SKIP_GROUPS)


def test_本輪不接寫_save_errors恆空(wired):
    assert source.load_live()["dataset"]["save_errors"] == {}
    model = live.apply_live_notes(logic.build_page_model(source.load_live()["dataset"]))
    saves = [b for block in model["blocks"] for b in (block.get("buttons") or ()) if b["_writes"]]
    assert saves and all(not b["_enabled"] for b in saves)
