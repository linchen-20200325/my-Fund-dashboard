"""test_v2_editor — v2 native UI helpers 單元測試

v19.436:schema 精簡 13 → 10 欄,**移除現金列(item_type/amount)與含息成本**。
`_split_policy_df` 改回單一 fund 視圖;`_merge_policy_df(policy_id, fund_df)` 單參數。
只測 pure helpers（split / merge df / empty df shape）。
"""
from __future__ import annotations

import pathlib

import pandas as pd

import ui.helpers.v2_editor as _v2_editor_mod
from ui.helpers.v2_editor import (
    _FUND_EDIT_COLS,
    _empty_fund_df,
    _merge_policy_df,
    _split_policy_df,
)
from repositories.policy_repository import ALL_COLS_V2


def test_empty_fund_df_has_9_edit_cols():
    """v19.436:fund 編輯視圖 9 欄(去掉 avg_nav_with_div)。"""
    df = _empty_fund_df()
    assert list(df.columns) == [
        "fund_code", "fund_name", "units", "avg_nav",
        "avg_fx", "currency", "tier", "invest_twd", "div_cash_pct",
    ]
    assert list(df.columns) == list(_FUND_EDIT_COLS)
    assert "avg_nav_with_div" not in df.columns
    assert df.empty


def test_split_policy_df_returns_fund_view():
    df = pd.DataFrame([
        {"policy_id": "p1", "fund_code": "F1", "fund_name": "fund-1",
         "currency": "USD", "tier": "core", "invest_twd": 30000,
         "div_cash_pct": 100, "units": 100, "avg_nav": 10, "avg_fx": 30},
        {"policy_id": "p1", "fund_code": "F2", "fund_name": "fund-2",
         "currency": "USD", "tier": "satellite", "invest_twd": 31000,
         "div_cash_pct": 100, "units": 50, "avg_nav": 20, "avg_fx": 31},
    ], columns=list(ALL_COLS_V2))
    fund_df = _split_policy_df(df)
    assert list(fund_df["fund_code"]) == ["F1", "F2"]
    assert list(fund_df.columns) == list(_FUND_EDIT_COLS)


def test_split_policy_df_empty_input_returns_empty_fund_view():
    fund_df = _split_policy_df(pd.DataFrame(columns=list(ALL_COLS_V2)))
    assert fund_df.empty
    assert list(fund_df.columns) == list(_FUND_EDIT_COLS)


def test_merge_policy_df_produces_10_col_schema_with_auto_units():
    """merged 為 10 欄;units **自動算**取代 user 給的(公式優先)。"""
    fund_df = pd.DataFrame([
        {"fund_code": "FIDXEQI", "fund_name": "富達世界", "units": 9999.9,
         "avg_nav": 12.345, "avg_fx": 31.2,
         "currency": "USD", "tier": "core", "invest_twd": 475000},
    ])
    merged = _merge_policy_df("p1", fund_df)
    assert list(merged.columns) == list(ALL_COLS_V2)
    assert len(merged) == 1
    assert merged.iloc[0]["fund_code"] == "FIDXEQI"
    # units 公式自動算 = 475000 / (12.345 × 31.2) ≈ 1232.66（不是 user 給的 9999.9）
    _expected = 475000 / (12.345 * 31.2)
    assert abs(merged.iloc[0]["units"] - _expected) < 0.5


def test_merge_policy_df_preserves_div_cash_pct_with_default_100():
    fund_df = pd.DataFrame([
        {"fund_code": "USDEQ5110", "fund_name": "聯博多元",
         "units": 0, "avg_nav": 10.0, "avg_fx": 31.0, "currency": "USD",
         "tier": "core", "invest_twd": 1_000_000, "div_cash_pct": 80},
        {"fund_code": "FIDXEQI", "fund_name": "富達",
         "units": 0, "avg_nav": 12.0, "avg_fx": 31.0, "currency": "USD",
         "tier": "core", "invest_twd": 500_000},   # 故意不放 div_cash_pct
    ])
    merged = _merge_policy_df("p1", fund_df)
    assert len(merged) == 2
    assert merged.iloc[0]["div_cash_pct"] == 80
    assert merged.iloc[1]["div_cash_pct"] == 100   # 預設值


def test_merge_policy_df_clips_div_cash_pct_to_0_100():
    fund_df = pd.DataFrame([
        {"fund_code": "A", "fund_name": "a", "units": 0, "avg_nav": 10,
         "avg_fx": 30, "currency": "USD", "tier": "", "invest_twd": 100_000,
         "div_cash_pct": 150},   # 超界
        {"fund_code": "B", "fund_name": "b", "units": 0, "avg_nav": 10,
         "avg_fx": 30, "currency": "USD", "tier": "", "invest_twd": 100_000,
         "div_cash_pct": -20},   # 負值
    ])
    merged = _merge_policy_df("p1", fund_df)
    assert merged.iloc[0]["div_cash_pct"] == 100
    assert merged.iloc[1]["div_cash_pct"] == 0


def test_merge_policy_df_drops_empty_fund_code():
    fund_df = pd.DataFrame([
        {"fund_code": "OK", "fund_name": "ok", "units": 100, "avg_nav": 10,
         "avg_fx": 30, "currency": "USD", "tier": "", "invest_twd": 30000},
        {"fund_code": "", "fund_name": "no-code", "units": 50, "avg_nav": 5,
         "avg_fx": 30, "currency": "USD", "tier": "", "invest_twd": 7500},
    ])
    merged = _merge_policy_df("p1", fund_df)
    assert len(merged) == 1
    assert merged.iloc[0]["fund_code"] == "OK"


def test_merge_policy_df_assigns_policy_id_to_all_rows():
    fund_df = pd.DataFrame([
        {"fund_code": "F1", "fund_name": "", "units": 100, "avg_nav": 10,
         "avg_fx": 30, "currency": "USD", "tier": "", "invest_twd": 30000},
    ])
    merged = _merge_policy_df("MyPolicy-A", fund_df)
    assert all(merged["policy_id"] == "MyPolicy-A")


def test_split_merge_round_trip_preserves_data():
    """split → merge 來回應該不丟核心資料。"""
    original = pd.DataFrame([
        {"policy_id": "p1", "fund_code": "F1", "fund_name": "name-1",
         "currency": "USD", "tier": "core", "invest_twd": 30000,
         "div_cash_pct": 100, "units": 100.0, "avg_nav": 10.0, "avg_fx": 30.0},
    ], columns=list(ALL_COLS_V2))
    fund_df = _split_policy_df(original)
    merged = _merge_policy_df("p1", fund_df)
    assert len(merged) == 1
    assert merged.iloc[0]["fund_code"] == "F1"
    assert merged.iloc[0]["invest_twd"] == 30000


def test_v2_editor_uses_no_st_expander():
    """v19.346 回歸守門:v2 編輯器**整段**從 tab3「保單管理」st.expander 內渲染
    (render_v2_section docstring 明載)。Streamlit 規則:expander 內任何深度都
    不得再有 expander,否則 StreamlitAPIException 炸掉整個 v2 編輯 UI。
    """
    src = pathlib.Path(_v2_editor_mod.__file__).read_text(encoding="utf-8")
    assert "st.expander(" not in src, (
        "ui/helpers/v2_editor.py 不得使用 st.expander()——它從 tab3 expander 內"
        "渲染,巢狀 expander 會 crash。請改用 st.container(border=True)。"
    )
