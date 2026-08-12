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
    """§1 防資料流失:現金列 item_type 不被改 fund、唯讀欄(avg_nav)保留、新增基金列補類型。"""
    df = pd.DataFrame([
        {"item_type": "fund", "fund_code": "ACTI71", "avg_nav": "8.67", "invest_twd": 100},   # 既有,avg_nav 須留
        {"item_type": "cash", "fund_code": "", "amount": "5000", "invest_twd": ""},            # 現金列須留
        {"item_type": "", "fund_code": "NEW1", "invest_twd": 50},                              # 新增基金列(無類型)
    ])
    out = M._prepare_write_df(df, "P1")
    assert (out["policy_id"] == "P1").all()
    assert out[out["fund_code"] == ""].iloc[0]["item_type"] == "cash"          # 現金列不被改成 fund
    assert out[out["fund_code"] == "NEW1"].iloc[0]["item_type"] == "fund"      # 新增列補 fund
    assert out[out["fund_code"] == "ACTI71"].iloc[0]["avg_nav"] == "8.67"      # 平均成本欄保留(不清空)


def test_policy_client_and_sheet_bare_mode_degrades_not_crash():
    _c, _reason = M._policy_client_and_sheet()
    assert _c is None and isinstance(_reason, str) and "登入" in _reason   # 誠實提示,不崩


def test_manage_tab_registered_in_app():
    txt = (_ROOT / "app.py").read_text(encoding="utf-8")
    assert "from ui.tab_manage import render_manage_tab" in txt
    assert "📋 我的管理室" in txt and "with tab_manage:" in txt


def test_pool_editor_no_longer_called_in_switch_advisor_section():
    """換股顧問區不得再直接呼叫 _render_pool_editor()(已移到管理室;避免同 run 雙渲染崩)。"""
    txt = (_ROOT / "ui" / "helpers" / "fund_grp_health" / "switch_advisor_section.py").read_text(encoding="utf-8")
    _fn = txt.split("def render_switch_advisor_section")[1]
    assert "_render_pool_editor()" not in _fn
