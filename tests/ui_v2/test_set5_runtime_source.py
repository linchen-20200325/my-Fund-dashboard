# -*- coding: utf-8 -*-
"""SET-5 重新取數零寫入之後的讀取端（fast，不碰網路、不需 streamlit）。

依據：客戶 2026-10-26 正式裁示第 6 節（`docs/evidence/decisions/2026-10-26_ui_v2_implementation_security_gate_decisions.md`）：
重新取數的結果與取數紀錄只留在本次工作階段（`services/v2_tables/settings_store.py::RuntimeFetchStore`，
畫面層放在 `st.session_state`）；alo 與 set 讀取時有它就優先，畫面標來源，沒有就照試算表既有資料、Missing 照舊。
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ui_v2.alo import fixtures as alo_fx, live as alo_live, logic as alo_logic  # noqa: E402
from ui_v2.set import live as set_live  # noqa: E402


def _row(key, obs, value, rel=None):
    return {"indicator_key": key, "obs_date": obs, "release_date": rel or obs, "value_num": value,
            "value_unit": "TWD/USD", "source_tier": "市場指標", "is_revised": False,
            "fetched_at": "2026-10-26T01:00:00Z"}


def test_兩頁標來源用同一句():
    assert alo_live.TEXT_RUNTIME_SOURCE == set_live.TEXT_RUNTIME_SOURCE == "含本次工作階段取數，未存入試算表"
    # 2026-10-26 獨立稽核必修 1：試算表那一份讀取失敗時不說「含」
    assert alo_live.TEXT_RUNTIME_SOURCE_SHEET_FAILED == set_live.TEXT_RUNTIME_SOURCE_SHEET_FAILED \
        == "本次工作階段取數，未存入試算表；試算表讀取失敗"


# ~~test_alo_沒有本次工作階段的列_原樣且不標來源／test_alo_同主鍵以本次工作階段為準_用到匯率列才標來源~~
# → 2026-10-26 獨立稽核必修 2（有意識的行為變更，不是漏刪）：合併改由 L2 `merge_sheet_and_runtime_indicators`
#   沿用 `merge_market_indicator` 的規則（同主鍵不同值不覆蓋；測試見 tests/test_v2_tables_settings_store.py）；
#   本檔只測 alo 對合併結果的判讀。
def test_alo_用到匯率列才標來源():
    assert alo_live.runtime_fx_used([_row("fx_twd_per_usd", "2026-10-22", 32.3)]) is True
    assert alo_live.runtime_fx_used([_row("vol_index", "2026-10-22", 17.0)]) is False
    assert alo_live.runtime_fx_used([]) is False


def test_alo_匯率鍵主鍵矛盾_照失敗方式寫一句_非匯率鍵不計():
    fx = {"key": ("fx_twd_per_usd", "2026-10-21", "2026-10-21")}
    vol = {"key": ("vol_index", "2026-10-21", "2026-10-21")}
    assert alo_live.runtime_fx_conflict_text([fx, vol]) == \
        "主鍵矛盾 1 組（本次工作階段取數與試算表不同），未採用本次值"
    assert alo_live.runtime_fx_conflict_text([vol]) is None and alo_live.runtime_fx_conflict_text([]) is None


def test_set_標來源句_試算表讀取失敗時換句_沒有本次資料不標():
    ok = {"fetch_log": True, "market_indicator": False}
    assert set_live.runtime_source_line(ok, {}, ("fetch_log",)) == set_live.TEXT_RUNTIME_SOURCE
    assert set_live.runtime_source_line(ok, {"fetch_log": "讀不到"}, ("fetch_log",)) == \
        set_live.TEXT_RUNTIME_SOURCE_SHEET_FAILED
    assert set_live.runtime_source_line(ok, {"fetch_log": "讀不到"}, ("market_indicator",)) is None


def test_alo_標來源只加在ALO2說明行_沒有就不加_試算表失敗換句():
    model = alo_logic.build_page_model(alo_fx.scenario_with("full", save_failed=False))
    plain = alo_live.apply_live_notes(model)
    marked = alo_live.apply_live_notes(model, runtime_source=True)
    failed = alo_live.apply_live_notes(model, runtime_source=True, sheet_failed=True)
    where = [b["code"] for b in marked["blocks"] if alo_live.TEXT_RUNTIME_SOURCE in (b.get("detail_lines") or ())]
    assert where == ["ALO-2"]
    assert not [b for b in plain["blocks"] if alo_live.TEXT_RUNTIME_SOURCE in (b.get("detail_lines") or ())]
    alo2 = next(b for b in failed["blocks"] if b["code"] == "ALO-2")
    assert alo_live.TEXT_RUNTIME_SOURCE_SHEET_FAILED in alo2["detail_lines"]
    assert alo_live.TEXT_RUNTIME_SOURCE not in alo2["detail_lines"]
