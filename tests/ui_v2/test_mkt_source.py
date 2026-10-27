# -*- coding: utf-8 -*-
"""ui_v2/mkt/source.py 的接縫測試（fast lane；不打網路、不需要 streamlit 執行期）。

依據 docs/v2/49_data_integration_plan.md §3.3（`source.py` 那一列）、§4.7 第 2 點，
以及 ACCEPTANCE.md 七（遮蔽在寫出點做一次；秘密值在 L3 讀好再傳進 L2）。
L2 與 `st` 一律以替身注入（monkeypatch `source` 模組上的引用），不呼叫任何 L1。
"""

from __future__ import annotations

import pathlib
import secrets as _rnd
import sys
import types

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

from ui_v2.mkt import fixtures, live, logic  # noqa: E402

source = pytest.importorskip("ui_v2.mkt.source")  # 需要 L1 的相依（pandas、streamlit 等）

_ROW = {
    "indicator_key": "vol_index", "obs_date": "2026-09-24", "release_date": "2026-09-24",
    "value_num": 16.5, "value_unit": "index", "source_tier": "市場指標",
    "is_revised": False, "fetched_at": "2026-09-25T06:00:00+00:00",
}


_STUB_VIEW = {"domains": [], "provenance": {"readonly": True}}


@pytest.fixture
def fake_st(monkeypatch):
    st = types.SimpleNamespace(secrets={}, session_state={})
    monkeypatch.setattr(source, "st", st)
    monkeypatch.setattr(source.market_indicator, "source_cooldowns", lambda: [])
    # 2026-10-27 BL-0516 批 1：load_live 另向 L2 `market_view` 要「市場趨勢」區段的 Data View（會呼叫 L1 取 VIX）；
    # 本檔是接縫測試、不打網路 → 換成固定替身（市場趨勢區段本身的測試在 tests/ui_v2/test_mkt_market_section_*.py）。
    monkeypatch.setattr(source.market_view, "build_market_view", lambda: dict(_STUB_VIEW))
    # 2026-10-13 起 load_live 另讀已存設定（客戶裁示：市場總覽設定存檔接上）；本檔不測設定，給一張空表。
    # 設定那一段的測試在 tests/ui_v2/test_mkt_settings_logic.py。
    monkeypatch.setattr(source.settings_store, "load_user_settings",
                        lambda _values: {"rows": {}, "bad_rows": [], "broken_keys": [], "blank_rows": 0,
                                         "tab_missing": True})
    return st


def _fake_table(rows, errors=None, pending=None):
    def build(**_kwargs):
        return {"rows": rows, "errors": dict(errors or {}), "pending": dict(pending or {}),
                "skipped": {}}
    return build


def test_dataset與fixtures同形_只有rows與errors兩鍵(monkeypatch, fake_st):
    monkeypatch.setattr(source.market_indicator, "build_market_indicator_table",
                        _fake_table([_ROW], {"fx_twd_per_usd": "原文"},
                                    {"leading_index": "ndc_no_release_date"}))
    data = source.load_live()
    assert set(data) == {"dataset", "notes"}
    assert set(data["dataset"]) == set(fixtures.dataset_all_ok()) == {"rows", "errors"}
    assert data["dataset"]["rows"] == [_ROW]
    assert data["dataset"]["errors"] == {"fx_twd_per_usd": "原文"}
    # ~~assert data["notes"] == {"pending": …, "masked_keys": [], "cooldowns": []}~~
    # → 2026-10-13 狀態更新（不是漏刪）：notes 另交可勾清單與已存設定（客戶裁示 MKT-5／設定存檔）。
    assert data["notes"] == {"pending": {"leading_index": "ndc_no_release_date"},
                             "masked_keys": [], "cooldowns": [],
                             # 2026-10-13 稽核 G N3：排除 L2 交回的 pending 鍵（狀態更新，不是漏刪）
                             "available_keys": [k for k in source.market_indicator.INDICATOR_SPECS
                                                if k != "leading_index"],
                             "settings": {"window_days": None, "baseline_date": None, "indicator_keys": None,
                                          "pair_consistent": None},
                             "settings_error": None,
                             # 2026-10-27 BL-0516 批 1：另交 L2 Data View（狀態更新，不是漏刪）
                             "market_view": _STUB_VIEW}
    for row in data["dataset"]["rows"]:
        assert list(row) == list(fixtures.observation("vol_index"))


def test_錯誤原文在本層遮蔽_秘密值取自st_secrets_環境變數與登入權杖(monkeypatch, fake_st):
    key_a, key_b, token = (_rnd.token_hex(12) for _ in range(3))
    fake_st.secrets = {"FRED_API_KEY": key_a}
    fake_st.session_state = {"gsheet_tokens": {"access_token": token}}
    monkeypatch.setenv("FINMIND_TOKEN", key_b)
    raw = f"GET ?api_key={key_a}&token={key_b} bearer {token} 其餘照留"
    monkeypatch.setattr(source.market_indicator, "build_market_indicator_table",
                        _fake_table([], {"vol_index": raw, "fx_twd_per_usd": "沒有秘密"}))
    data = source.load_live()
    masked = data["dataset"]["errors"]["vol_index"]
    for secret in (key_a, key_b, token):
        assert secret not in masked
    assert masked.endswith("其餘照留")
    assert data["dataset"]["errors"]["fx_twd_per_usd"] == "沒有秘密"
    assert data["notes"]["masked_keys"] == ["vol_index"]


def test_輸出丟進既有logic_與fixtures走同一批判準(monkeypatch, fake_st):
    monkeypatch.setattr(source.market_indicator, "build_market_indicator_table",
                        _fake_table([_ROW], {"credit_spread_pct": "HTTP 失敗原文"}))
    data = source.load_live()
    model = live.apply_live_notes(logic.build_page_model(data["dataset"]), data["notes"])
    mkt1 = logic.find_block(model, "MKT-1")
    values = {mv["label"]: mv for mv in mkt1["main_values"]}
    assert values["波動度指數"]["value_text"] == "16.5"
    assert values["高收益信用利差"]["_state"] == logic.STATE_ERROR
    assert logic.scan_forbidden(logic.collect_ui_strings(model)) == {}


def test_每次呼叫都向L2要一次_本層不快取(monkeypatch, fake_st):
    calls = []

    def build(**_kwargs):
        calls.append(1)
        return {"rows": [], "errors": {}, "pending": {}, "skipped": {}}

    monkeypatch.setattr(source.market_indicator, "build_market_indicator_table", build)
    source.load_live()
    source.load_live()
    assert len(calls) == 2  # 49 §4.4：快取只在 L1，L3 不放快取


def test_回傳的是複本_改它不會改到L2的結果(monkeypatch, fake_st):
    table_rows = [dict(_ROW)]
    pending = {"leading_index": "ndc_no_release_date"}

    def build(**_kwargs):
        return {"rows": table_rows, "errors": {}, "pending": pending, "skipped": {}}

    monkeypatch.setattr(source.market_indicator, "build_market_indicator_table", build)
    data = source.load_live()
    data["dataset"]["rows"].append({})
    data["notes"]["pending"]["x"] = "y"
    assert len(table_rows) == 1 and pending == {"leading_index": "ndc_no_release_date"}


def test_market_view的失敗原文經真實_mask_view與load_live遮蔽_不含secret(monkeypatch, fake_st):
    """BL-0516 稽核必修：不以固定替身繞過遮蔽——L2 回含 secret 的 reason，走真的 load_live → _mask_view。"""
    key = _rnd.token_hex(12)
    fake_st.secrets = {"FRED_API_KEY": key}
    raw = f"Yahoo failed key={key} <script>alert(1)</script> 其餘照留"
    view = {"domains": [
        {"domain": "vix", "status": "系統錯誤", "reason": raw, "reason_code": None, "source": None,
         "fetched_at": None, "obs_date": None, "value_unit": None, "points": []},
        {"domain": "taiex", "status": "資料未備", "reason": "沒有秘密", "reason_code": "x", "source": None,
         "fetched_at": None, "obs_date": None, "value_unit": None, "points": []}],
        "provenance": {}}
    monkeypatch.setattr(source.market_view, "build_market_view", lambda: view)
    monkeypatch.setattr(source.market_indicator, "build_market_indicator_table",
                        _fake_table([], {}, {}))
    out = source.load_live()["notes"]["market_view"]
    assert key not in repr(out)
    assert out["domains"][0]["reason"].endswith("其餘照留")
    assert out["domains"][1]["reason"] == "沒有秘密"
    assert key in repr(view)          # 原物件未被改動（複本）
