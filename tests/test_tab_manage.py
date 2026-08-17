"""📋 我的管理室(ui/tab_manage,v19.433)。

UI 難以單元測,鎖住:回寫前處理純函式、bare-mode 誠實降級、分頁註冊、選股池編輯器
已從換股顧問移除(避免 DuplicateWidgetID)。
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

import ui.tab_manage as M

_ROOT = Path(__file__).resolve().parent.parent


def test_today_tw_iso():
    assert re.match(r"^\d{4}-\d{2}-\d{2}$", M._today_tw())


def test_prepare_write_df_preserves_data_no_loss():
    """§1 防資料流失:回寫前處理補 policy_id、唯讀選填欄(avg_nav/units)照原樣保留不清空。

    v19.436:10 欄 schema(item_type 退役) → _prepare_write_df 僅補 policy_id;
    write_policy_v2 端會跳過無 fund_code 的列。"""
    df = pd.DataFrame([
        {"fund_code": "ACTI71", "avg_nav": "8.67", "units": "1781", "invest_twd": 100},
        {"fund_code": "NEW1", "invest_twd": 50},
    ])
    out = M._prepare_write_df(df, "P1")
    assert (out["policy_id"] == "P1").all()
    assert out[out["fund_code"] == "ACTI71"].iloc[0]["avg_nav"] == "8.67"      # 平均成本欄保留(不清空)
    assert out[out["fund_code"] == "ACTI71"].iloc[0]["units"] == "1781"        # 份額選填欄保留


def test_policy_client_and_sheet_bare_mode_degrades_not_crash():
    _c, _reason = M._policy_client_and_sheet()
    assert _c is None and isinstance(_reason, str) and "登入" in _reason   # 誠實提示,不崩


def test_manage_tab_registered_in_app():
    txt = (_ROOT / "app.py").read_text(encoding="utf-8")
    assert "from ui.tab_manage import render_manage_tab" in txt
    assert "📋 我的管理室" in txt and "with tab_manage:" in txt


def test_fund_history_section_fully_removed():
    """v19.461(user 2026-08-17「介面不友善→全拿掉」):曾經查過的基金清單整段**完全移除**,

    說明書 + 管理室兩邊都不得再有該 widget / 渲染函式 / 指路 stub(選股池編輯器本身即 watchlist)。
    """
    _t6 = (_ROOT / "ui" / "tab6_manual.py").read_text(encoding="utf-8")
    _tm = (_ROOT / "ui" / "tab_manage.py").read_text(encoding="utf-8")
    # 說明書:無該 widget、無指路 stub
    assert "_fh_add_form" not in _t6 and "_fh_promote_btn" not in _t6
    assert "曾經查過" not in _t6
    # 管理室:整段渲染函式 + widget 都已刪
    assert "def _render_fund_history" not in _tm and "_fh_add_form" not in _tm
    assert "_import_history_to_pool" not in _tm


def test_nav_csv_tool_moved_to_manage():
    """v19.461:🗄️ NAV 歷史資料管理(手動 CSV)由說明書搬到管理室(集中 NAV 補歷史)。"""
    _t6 = (_ROOT / "ui" / "tab6_manual.py").read_text(encoding="utf-8")
    _tm = (_ROOT / "ui" / "tab_manage.py").read_text(encoding="utf-8")
    assert "nav_history_store" not in _t6 and "_nh_upload_csv" not in _t6   # 說明書已移出
    assert "_nh_upload_csv" in _tm and "nav_history_store" in _tm            # 管理室已收入


def test_mk_clock_section_not_rendered():
    """v19.461(user 2026-08-17「這個也移除」):美林時鐘(策略3 景氣時鐘觀測站)不再於 UI 渲染。

    純邏輯 classify_phase + PMI SSOT 常數留在 mk_clock.py(SSOT-lock 測試用),但不得有 render 呼叫。
    """
    _lt = (_ROOT / "ui" / "tab1_macro_longterm.py").read_text(encoding="utf-8")
    _t1 = (_ROOT / "ui" / "tab1_macro.py").read_text(encoding="utf-8")
    assert "render_mk_clock_section" not in _lt   # 呼叫 + import 都已移除
    assert "render_mk_clock_section" not in _t1   # 死 import 也清掉


def test_pool_editor_no_longer_called_in_switch_advisor_section():
    """換股顧問區不得再直接呼叫 _render_pool_editor()(已移到管理室;避免同 run 雙渲染崩)。"""
    txt = (_ROOT / "ui" / "helpers" / "fund_grp_health" / "switch_advisor_section.py").read_text(encoding="utf-8")
    _fn = txt.split("def render_switch_advisor_section")[1]
    assert "_render_pool_editor()" not in _fn
