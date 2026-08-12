"""test_v2_editor_arrow_compat.py — v2 編輯器合併/拆分 regression

v19.436:schema 精簡 13 → 10 欄,**移除現金列(item_type/amount)** 後,`_merge_policy_df`
不再混 fund/cash 兩型 → 原 pyarrow mixed str/float ArrowInvalid 場景自然消失。本檔改鎖:
  - `_merge_policy_df(policy_id, fund_df)` → 10 欄、全基金列、pyarrow 可序列化
  - 無 fund_code 的列被跳過(§1 不寫幽靈列)
  - `_merge_policy_df → _split_policy_df` 來回保留核心資料
"""
from __future__ import annotations

import pandas as pd
import pytest

from repositories.policy_repository import ALL_COLS_V2

_FUND = {
    "fund_code": "ACCP138", "fund_name": "聯博",
    "units": 100.0, "avg_nav": 12.34, "avg_fx": 31.5,
    "currency": "USD", "tier": "core",
    "invest_twd": 1_000_000, "div_cash_pct": 80,
}


def test_merge_emits_exactly_10_cols_in_canonical_order():
    from ui.helpers.v2_editor import _merge_policy_df
    merged = _merge_policy_df("p001", pd.DataFrame([_FUND]))
    assert list(merged.columns) == list(ALL_COLS_V2)
    assert len(ALL_COLS_V2) == 10
    assert "item_type" not in merged.columns
    assert "amount" not in merged.columns
    assert "avg_nav_with_div" not in merged.columns


def test_merge_policy_df_arrow_serializable():
    """全基金列 df 必須能被 pyarrow 序列化（Streamlit st.dataframe render 前提）。"""
    pa = pytest.importorskip("pyarrow")
    from ui.helpers.v2_editor import _merge_policy_df
    merged = _merge_policy_df("p001", pd.DataFrame([_FUND, {**_FUND, "fund_code": "TLZF9"}]))
    assert len(merged) == 2
    table = pa.Table.from_pandas(merged)
    assert table.num_rows == 2


def test_merge_skips_blank_fund_code_rows():
    """§1:無 fund_code 的列(舊現金列 / 空列)被跳過,不寫幽靈列。"""
    from ui.helpers.v2_editor import _merge_policy_df
    df = pd.DataFrame([_FUND, {**_FUND, "fund_code": "  "}, {**_FUND, "fund_code": ""}])
    merged = _merge_policy_df("p001", df)
    assert len(merged) == 1
    assert merged.iloc[0]["fund_code"] == "ACCP138"


def test_roundtrip_merge_then_split_preserves_core_data():
    """_merge_policy_df → _split_policy_df 來回保留核心欄。"""
    from ui.helpers.v2_editor import _merge_policy_df, _split_policy_df
    merged = _merge_policy_df("p001", pd.DataFrame([_FUND]))
    fund2 = _split_policy_df(merged)
    assert len(fund2) == 1
    assert fund2.iloc[0]["fund_code"] == "ACCP138"
    assert float(fund2.iloc[0]["div_cash_pct"]) == 80
    assert float(fund2.iloc[0]["invest_twd"]) == 1_000_000
