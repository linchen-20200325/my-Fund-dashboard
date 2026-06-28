"""test_v2_editor_arrow_compat.py — v18.274 pyarrow ArrowInvalid 修補 regression

User Phase 1 debug log 揭露真因：
  pyarrow.lib.ArrowInvalid: Could not convert '' with type str: tried to convert to int64
  Conversion failed for column div_cash_pct with type object

ui/helpers/v2_editor.py:_merge_policy_df 對 cash 列把 div_cash_pct / units /
avg_nav 等基金欄位塞 "" 空字串，而 fund 列同欄位是 float。pyarrow Arrow 序列化
推斷 column type 時遇到 mixed str/float 直接 crash → Streamlit st.dataframe
無法 render → 整頁 widget 卡住（含 Tab2 FX 顯示舊狀態）。

修法：cash 列無基金欄位改 None（pyarrow 視為 nullable numeric，可正確序列化）。
"""
from __future__ import annotations

import pandas as pd
import pytest


def test_merge_policy_df_arrow_compatible_with_mixed_fund_cash():
    """混 fund + cash 兩列的合併 df 必須能被 pyarrow 序列化（regression）。"""
    pa = pytest.importorskip("pyarrow")
    from ui.helpers.v2_editor import _merge_policy_df

    fund_df = pd.DataFrame([
        {
            "fund_code": "ACCP138", "fund_name": "聯博",
            "units": 100.0, "avg_nav": 12.34, "avg_nav_with_div": 12.5,
            "avg_fx": 31.5, "currency": "USD", "tier": "core",
            "invest_twd": 1_000_000, "div_cash_pct": 80,
        },
    ])
    cash_df = pd.DataFrame([
        {"currency": "USD", "amount": 50_000.0},
        {"currency": "TWD", "amount": 100_000.0},
    ])

    merged = _merge_policy_df("policy_001", fund_df, cash_df)
    assert len(merged) == 3, "1 fund + 2 cash"

    # 關鍵驗證：pyarrow 能序列化（user 觸發 crash 的真實場景）
    table = pa.Table.from_pandas(merged)
    assert table.num_rows == 3


def test_merge_policy_df_cash_only_arrow_safe():
    """純 cash 列也應 Arrow 相容。"""
    pa = pytest.importorskip("pyarrow")
    from ui.helpers.v2_editor import _merge_policy_df

    fund_df = pd.DataFrame(columns=[
        "fund_code", "fund_name", "units", "avg_nav", "avg_nav_with_div",
        "avg_fx", "currency", "tier", "invest_twd", "div_cash_pct",
    ])
    cash_df = pd.DataFrame([
        {"currency": "USD", "amount": 50_000.0},
        {"currency": "EUR", "amount": 30_000.0},
    ])
    merged = _merge_policy_df("p001", fund_df, cash_df)
    assert len(merged) == 2
    table = pa.Table.from_pandas(merged)
    assert table.num_rows == 2


def test_merge_policy_df_fund_only_arrow_safe():
    """純 fund 列也應 Arrow 相容。"""
    pa = pytest.importorskip("pyarrow")
    from ui.helpers.v2_editor import _merge_policy_df

    fund_df = pd.DataFrame([
        {
            "fund_code": "ACCP138", "fund_name": "聯博",
            "units": 100.0, "avg_nav": 12.34, "avg_nav_with_div": 12.5,
            "avg_fx": 31.5, "currency": "USD", "tier": "core",
            "invest_twd": 1_000_000, "div_cash_pct": 100,
        },
    ])
    cash_df = pd.DataFrame(columns=["currency", "amount"])
    merged = _merge_policy_df("p001", fund_df, cash_df)
    assert len(merged) == 1
    table = pa.Table.from_pandas(merged)
    assert table.num_rows == 1


def test_cash_rows_have_none_not_empty_string_in_fund_columns():
    """精確驗證：cash 列的基金欄位是 None 而非空字串（防 regression）。"""
    from ui.helpers.v2_editor import _merge_policy_df

    fund_df = pd.DataFrame([
        {
            "fund_code": "X", "fund_name": "X", "units": 1.0,
            "avg_nav": 1.0, "avg_nav_with_div": 1.0, "avg_fx": 1.0,
            "currency": "USD", "tier": "", "invest_twd": 1, "div_cash_pct": 100,
        },
    ])
    cash_df = pd.DataFrame([{"currency": "USD", "amount": 1.0}])
    merged = _merge_policy_df("p001", fund_df, cash_df)
    # cash 列（最後一列）
    cash_row = merged.iloc[-1]
    for col in ("units", "avg_nav", "avg_nav_with_div", "avg_fx",
                "invest_twd", "div_cash_pct"):
        v = cash_row[col]
        # 必須是 None 或 NaN，**不可** 是空字串 ""
        assert v is None or pd.isna(v), f"cash 列 {col} 不該是 '{v}' (type={type(v).__name__})"


def test_fund_rows_have_none_for_amount_not_empty_string():
    """fund 列的 amount 也應該是 None 而非 ""。"""
    from ui.helpers.v2_editor import _merge_policy_df

    fund_df = pd.DataFrame([
        {
            "fund_code": "X", "fund_name": "X", "units": 1.0,
            "avg_nav": 1.0, "avg_nav_with_div": 1.0, "avg_fx": 1.0,
            "currency": "USD", "tier": "", "invest_twd": 1, "div_cash_pct": 100,
        },
    ])
    cash_df = pd.DataFrame(columns=["currency", "amount"])
    merged = _merge_policy_df("p001", fund_df, cash_df)
    fund_row = merged.iloc[0]
    assert fund_row["amount"] is None or pd.isna(fund_row["amount"])


def test_roundtrip_write_then_split_preserves_data():
    """_merge_policy_df → _split_policy_df 來回應保留 fund/cash 資料完整。"""
    from ui.helpers.v2_editor import _merge_policy_df, _split_policy_df

    fund_df = pd.DataFrame([
        {
            "fund_code": "ACCP138", "fund_name": "聯博",
            "units": 100.0, "avg_nav": 12.34, "avg_nav_with_div": 12.5,
            "avg_fx": 31.5, "currency": "USD", "tier": "core",
            "invest_twd": 1_000_000, "div_cash_pct": 80,
        },
    ])
    cash_df = pd.DataFrame([
        {"currency": "USD", "amount": 50_000.0},
    ])
    merged = _merge_policy_df("p001", fund_df, cash_df)
    fund2, cash2 = _split_policy_df(merged)
    assert len(fund2) == 1
    assert len(cash2) == 1
    assert fund2.iloc[0]["fund_code"] == "ACCP138"
    assert float(fund2.iloc[0]["div_cash_pct"]) == 80
    assert cash2.iloc[0]["currency"] == "USD"
    assert float(cash2.iloc[0]["amount"]) == 50_000.0
