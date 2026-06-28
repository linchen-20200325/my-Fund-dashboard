"""v19.186 Pandera Phase B — ForeignFlowSchema(外資買賣超序列契約)測試。

涵蓋:
1. 合法 df 通過
2. 空 df pass（fetch 失敗 token）
3. date 重複 / 非單調 → SchemaError
4. foreign_net_yi NaN → SchemaError
5. 單位異常（元 vs 億，|net| > 5000）→ SchemaError
6. 負值合法（賣超）
"""
from __future__ import annotations

import pandas as pd
import pytest

import pandera.errors as pa_errors

from shared.schemas import validate_foreign_flow, ForeignFlowSchema


def _mk(dates, vals):
    return pd.DataFrame({
        "date": pd.to_datetime(dates),
        "foreign_net_yi": [float(v) for v in vals],
    })


def test_valid_passes():
    df = _mk(["2026-06-23", "2026-06-24", "2026-06-25"], [120.5, -88.0, 5.0])
    out = validate_foreign_flow(df)
    assert len(out) == 3


def test_negative_net_is_valid():
    """賣超(負值)合法 — net = buy - sell 可負。"""
    df = _mk(["2026-06-23", "2026-06-24"], [-300.0, -150.5])
    assert len(validate_foreign_flow(df)) == 2


def test_empty_df_passes():
    """空 df（fetch 失敗）直接 pass（§1：caller 已從 error_msg 得知）。"""
    empty = pd.DataFrame(columns=["date", "foreign_net_yi"])
    out = validate_foreign_flow(empty)
    assert len(out) == 0


def test_none_passes():
    assert validate_foreign_flow(None) is None


def test_duplicate_date_raises():
    df = _mk(["2026-06-23", "2026-06-23"], [10.0, 20.0])
    with pytest.raises(pa_errors.SchemaError):
        validate_foreign_flow(df)


def test_non_monotonic_date_raises():
    df = _mk(["2026-06-25", "2026-06-23"], [10.0, 20.0])
    with pytest.raises(pa_errors.SchemaError):
        validate_foreign_flow(df)


def test_nan_net_raises():
    df = pd.DataFrame({
        "date": pd.to_datetime(["2026-06-23", "2026-06-24"]),
        "foreign_net_yi": [10.0, float("nan")],
    })
    with pytest.raises(pa_errors.SchemaError):
        validate_foreign_flow(df)


def test_unit_anomaly_raises():
    """|net| > 5000 億 = 疑單位錯誤（元未除 1e8）→ Fail Loud。"""
    df = _mk(["2026-06-23"], [99999999.0])
    with pytest.raises(pa_errors.SchemaError):
        validate_foreign_flow(df)


def test_fetcher_wires_schema():
    """fetch_foreign_flow_series 必須在出口呼叫 validate_foreign_flow。

    v19.196 P0-4-A:fetcher 從根目錄 hot_money.py 下沉 repositories.hot_money_repository。
    """
    from repositories import hot_money_repository
    src = open(hot_money_repository.__file__, encoding="utf-8").read()
    assert "validate_foreign_flow" in src
