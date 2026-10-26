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


def test_alo_沒有本次工作階段的列_原樣且不標來源():
    sheet = [_row("fx_twd_per_usd", "2026-10-20", 32.0)]
    rows, used = alo_live.merge_runtime_indicators(sheet, [])
    assert rows == sheet and used is False


def test_alo_同主鍵以本次工作階段為準_用到匯率列才標來源():
    sheet = [_row("fx_twd_per_usd", "2026-10-20", 32.0), _row("fx_twd_per_usd", "2026-10-21", 32.1)]
    runtime = [_row("fx_twd_per_usd", "2026-10-21", 32.2), _row("fx_twd_per_usd", "2026-10-22", 32.3)]
    rows, used = alo_live.merge_runtime_indicators(sheet, runtime)
    assert [(r["obs_date"], r["value_num"]) for r in rows] == [
        ("2026-10-20", 32.0), ("2026-10-21", 32.2), ("2026-10-22", 32.3)]
    assert used is True
    # 非匯率鍵（本頁用不到）不標來源
    _rows, used = alo_live.merge_runtime_indicators(sheet, [_row("vol_index", "2026-10-22", 17.0)])
    assert used is False


def test_alo_標來源只加在ALO2說明行_沒有就不加():
    model = alo_logic.build_page_model(alo_fx.scenario_with("full", save_failed=False))
    plain = alo_live.apply_live_notes(model)
    marked = alo_live.apply_live_notes(model, runtime_source=True)
    where = [b["code"] for b in marked["blocks"] if alo_live.TEXT_RUNTIME_SOURCE in (b.get("detail_lines") or ())]
    assert where == ["ALO-2"]
    assert not [b for b in plain["blocks"] if alo_live.TEXT_RUNTIME_SOURCE in (b.get("detail_lines") or ())]
