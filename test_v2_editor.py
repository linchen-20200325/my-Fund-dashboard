"""test_v2_editor — v18.150 PR B v2 native UI helpers 單元測試

只測 pure helpers（split / merge df / empty df shape）；render 路徑因為依賴
streamlit runtime + AppTest 又卡 plotly 環境問題，留 PR D smoke 測試補完。
"""
from __future__ import annotations

import pandas as pd

from ui.helpers.v2_editor import (
    _empty_cash_df,
    _empty_fund_df,
    _merge_policy_df,
    _split_policy_df,
)
from repositories.policy_repository import (
    ALL_COLS_V2,
    ITEM_TYPE_CASH,
    ITEM_TYPE_FUND,
)


def test_empty_fund_df_has_9_cols():
    """v18.153：fund 表加入 avg_nav_with_div（含息成本）。"""
    df = _empty_fund_df()
    assert list(df.columns) == [
        "fund_code", "fund_name", "units", "avg_nav", "avg_nav_with_div",
        "avg_fx", "currency", "tier", "invest_twd",
    ]
    assert df.empty


def test_empty_cash_df_has_2_cols():
    df = _empty_cash_df()
    assert list(df.columns) == ["currency", "amount"]
    assert df.empty


def test_split_policy_df_routes_fund_vs_cash_by_item_type():
    df = pd.DataFrame([
        {"policy_id": "p1", "item_type": "fund", "fund_code": "F1",
         "fund_name": "fund-1", "units": 100, "avg_nav": 10, "avg_fx": 30,
         "currency": "USD", "tier": "core", "amount": 0, "invest_twd": 30000},
        {"policy_id": "p1", "item_type": "fund", "fund_code": "F2",
         "fund_name": "fund-2", "units": 50, "avg_nav": 20, "avg_fx": 31,
         "currency": "USD", "tier": "satellite", "amount": 0, "invest_twd": 31000},
        {"policy_id": "p1", "item_type": "cash", "fund_code": "",
         "fund_name": "", "units": 0, "avg_nav": 0, "avg_fx": 0,
         "currency": "TWD", "tier": "", "amount": 500000, "invest_twd": 0},
    ], columns=list(ALL_COLS_V2))

    fund_df, cash_df = _split_policy_df(df)
    assert len(fund_df) == 2
    assert len(cash_df) == 1
    assert list(fund_df["fund_code"]) == ["F1", "F2"]
    assert cash_df.iloc[0]["currency"] == "TWD"
    assert cash_df.iloc[0]["amount"] == 500000


def test_split_policy_df_empty_input_returns_empty_df():
    df = pd.DataFrame(columns=list(ALL_COLS_V2))
    fund_df, cash_df = _split_policy_df(df)
    assert fund_df.empty
    assert cash_df.empty
    assert list(fund_df.columns) == [
        "fund_code", "fund_name", "units", "avg_nav", "avg_nav_with_div",
        "avg_fx", "currency", "tier", "invest_twd",
    ]


def test_merge_policy_df_produces_12_col_schema_with_auto_units():
    """v18.153：merged 是 12 欄；units **自動算**取代 user 給的（公式優先）。"""
    fund_df = pd.DataFrame([
        {"fund_code": "FIDXEQI", "fund_name": "富達世界", "units": 9999.9,
         "avg_nav": 12.345, "avg_nav_with_div": 10.5, "avg_fx": 31.2,
         "currency": "USD", "tier": "core", "invest_twd": 475000},
    ])
    cash_df = pd.DataFrame([
        {"currency": "TWD", "amount": 500000},
        {"currency": "USD", "amount": 10000},
    ])
    merged = _merge_policy_df("p1", fund_df, cash_df)
    assert list(merged.columns) == list(ALL_COLS_V2)
    assert len(merged) == 3
    assert merged.iloc[0]["item_type"] == ITEM_TYPE_FUND
    assert merged.iloc[0]["fund_code"] == "FIDXEQI"
    # units 公式自動算 = 475000 / (12.345 × 31.2) ≈ 1232.66（不是 user 給的 9999.9）
    _expected = 475000 / (12.345 * 31.2)
    assert abs(merged.iloc[0]["units"] - _expected) < 0.5
    assert merged.iloc[0]["avg_nav_with_div"] == 10.5
    # cash 列
    assert merged.iloc[1]["item_type"] == ITEM_TYPE_CASH
    assert merged.iloc[1]["currency"] == "TWD"
    assert merged.iloc[1]["amount"] == 500000
    assert merged.iloc[2]["currency"] == "USD"


def test_merge_policy_df_drops_empty_fund_code_and_zero_cash():
    """fund 列 fund_code 空 → 丟；cash 列 amount=0 → 丟。"""
    fund_df = pd.DataFrame([
        {"fund_code": "OK", "fund_name": "ok", "units": 100, "avg_nav": 10,
         "avg_fx": 30, "currency": "USD", "tier": "", "invest_twd": 30000},
        {"fund_code": "", "fund_name": "no-code", "units": 50, "avg_nav": 5,
         "avg_fx": 30, "currency": "USD", "tier": "", "invest_twd": 7500},
    ])
    cash_df = pd.DataFrame([
        {"currency": "TWD", "amount": 100000},
        {"currency": "USD", "amount": 0},          # zero → drop
        {"currency": "", "amount": 5000},           # no currency → drop
    ])
    merged = _merge_policy_df("p1", fund_df, cash_df)
    assert len(merged) == 2   # 1 fund + 1 cash
    assert merged.iloc[0]["fund_code"] == "OK"
    assert merged.iloc[1]["currency"] == "TWD"


def test_merge_policy_df_assigns_policy_id_to_all_rows():
    fund_df = pd.DataFrame([
        {"fund_code": "F1", "fund_name": "", "units": 100, "avg_nav": 10,
         "avg_fx": 30, "currency": "USD", "tier": "", "invest_twd": 30000},
    ])
    cash_df = pd.DataFrame([
        {"currency": "TWD", "amount": 50000},
    ])
    merged = _merge_policy_df("MyPolicy-A", fund_df, cash_df)
    assert all(merged["policy_id"] == "MyPolicy-A")


def test_split_merge_round_trip_preserves_data():
    """split → merge 來回應該不丟資料（不算 dtype 細節）。"""
    original = pd.DataFrame([
        {"policy_id": "p1", "item_type": ITEM_TYPE_FUND, "fund_code": "F1",
         "fund_name": "name-1", "units": 100.0, "avg_nav": 10.0, "avg_fx": 30.0,
         "currency": "USD", "tier": "core", "amount": "", "invest_twd": 30000},
        {"policy_id": "p1", "item_type": ITEM_TYPE_CASH, "fund_code": "",
         "fund_name": "", "units": "", "avg_nav": "", "avg_fx": "",
         "currency": "TWD", "tier": "", "amount": 500000.0, "invest_twd": ""},
    ], columns=list(ALL_COLS_V2))

    fund_df, cash_df = _split_policy_df(original)
    merged = _merge_policy_df("p1", fund_df, cash_df)
    assert len(merged) == 2
    assert set(merged["item_type"]) == {ITEM_TYPE_FUND, ITEM_TYPE_CASH}
    assert merged[merged["item_type"] == ITEM_TYPE_FUND].iloc[0]["fund_code"] == "F1"
    assert merged[merged["item_type"] == ITEM_TYPE_CASH].iloc[0]["amount"] == 500000.0
