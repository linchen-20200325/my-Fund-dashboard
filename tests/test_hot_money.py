# -*- coding: utf-8 -*-
"""test_hot_money.py — 熱錢監測核心邏輯單元測試（基金倉版）

只測純函式（build_signals / _yf_series_to_df），不測 render UI（streamlit）
與 fetch FinMind / Yahoo（外部網路）。
"""
from __future__ import annotations

import pandas as pd

# v19.196 P0-4-A:hot_money.py 拆 2 檔
from repositories.hot_money_repository import _yf_series_to_df
from ui.hot_money import (
    DIVERGENCE_STATES,
    STATE_TEXT,
    build_signals,
)


# ────────────────────────────────────────────────────────────────────────
# build_signals — 9 個狀態分類向量化驗證
# ────────────────────────────────────────────────────────────────────────
def _make_flow_fx(dates, flows, fx_rates):
    flow = pd.DataFrame({"date": pd.to_datetime(dates), "foreign_net_yi": flows})
    fx = pd.DataFrame({"date": pd.to_datetime(dates), "usdtwd": fx_rates})
    return flow, fx


def test_build_signals_empty_inputs_returns_empty_df_with_schema():
    sig = build_signals(pd.DataFrame(), pd.DataFrame(), 5, 50, 0.5)
    assert sig.empty
    assert "state" in sig.columns
    assert "is_divergence" in sig.columns


def test_build_signals_sync_inflow_when_buy_and_twd_up():
    """連 10 天外資每天 +100 億 + 台幣升值 → 同步流入。"""
    dates = pd.bdate_range("2026-01-01", periods=10)
    flows = [100.0] * 10
    fx_rates = [31.0 - 0.1 * i for i in range(10)]
    flow_df, fx_df = _make_flow_fx(dates, flows, fx_rates)
    sig = build_signals(flow_df, fx_df, window=5, flow_thr=50, fx_thr=0.5)
    assert sig.iloc[-1]["state"] == "同步流入"
    assert not bool(sig.iloc[-1]["is_divergence"])


def test_build_signals_sync_outflow_when_sell_and_twd_down():
    dates = pd.bdate_range("2026-01-01", periods=10)
    flows = [-100.0] * 10
    fx_rates = [31.0 + 0.1 * i for i in range(10)]
    flow_df, fx_df = _make_flow_fx(dates, flows, fx_rates)
    sig = build_signals(flow_df, fx_df, window=5, flow_thr=50, fx_thr=0.5)
    assert sig.iloc[-1]["state"] == "同步流出"


def test_build_signals_hot_money_in_fx_divergence():
    """背離｜熱錢停泊匯市：台幣明顯升、外資沒買。"""
    dates = pd.bdate_range("2026-01-01", periods=10)
    flows = [-5.0] * 10
    fx_rates = [31.0 - 0.15 * i for i in range(10)]
    flow_df, fx_df = _make_flow_fx(dates, flows, fx_rates)
    sig = build_signals(flow_df, fx_df, window=5, flow_thr=50, fx_thr=0.5)
    assert sig.iloc[-1]["state"] == "背離｜熱錢停泊匯市"
    assert bool(sig.iloc[-1]["is_divergence"])


def test_build_signals_buy_masked_by_fx_divergence():
    """背離｜買盤遭拋匯掩蓋：外資買、台幣貶。"""
    dates = pd.bdate_range("2026-01-01", periods=10)
    flows = [100.0] * 10
    fx_rates = [31.0 + 0.15 * i for i in range(10)]
    flow_df, fx_df = _make_flow_fx(dates, flows, fx_rates)
    sig = build_signals(flow_df, fx_df, window=5, flow_thr=50, fx_thr=0.5)
    assert sig.iloc[-1]["state"] == "背離｜買盤遭拋匯掩蓋"
    assert bool(sig.iloc[-1]["is_divergence"])


def test_build_signals_fx_first_exit_divergence():
    """背離｜匯市先撤：台幣貶、外資沒賣。"""
    dates = pd.bdate_range("2026-01-01", periods=10)
    flows = [5.0] * 10
    fx_rates = [31.0 + 0.15 * i for i in range(10)]
    flow_df, fx_df = _make_flow_fx(dates, flows, fx_rates)
    sig = build_signals(flow_df, fx_df, window=5, flow_thr=50, fx_thr=0.5)
    assert sig.iloc[-1]["state"] == "背離｜匯市先撤"
    assert bool(sig.iloc[-1]["is_divergence"])


def test_build_signals_neutral_when_both_below_thresholds():
    dates = pd.bdate_range("2026-01-01", periods=10)
    flows = [1.0] * 10
    fx_rates = [31.0 + 0.001 * i for i in range(10)]
    flow_df, fx_df = _make_flow_fx(dates, flows, fx_rates)
    sig = build_signals(flow_df, fx_df, window=5, flow_thr=50, fx_thr=0.5)
    assert sig.iloc[-1]["state"] == "中性／觀望"
    assert not bool(sig.iloc[-1]["is_divergence"])


def test_build_signals_mild_inflow_with_only_flow_signal():
    dates = pd.bdate_range("2026-01-01", periods=10)
    flows = [50.0] * 10
    fx_rates = [31.000] * 10
    flow_df, fx_df = _make_flow_fx(dates, flows, fx_rates)
    sig = build_signals(flow_df, fx_df, window=5, flow_thr=50, fx_thr=0.5)
    assert sig.iloc[-1]["state"] == "溫和流入"


def test_build_signals_interpretation_matches_state_text():
    dates = pd.bdate_range("2026-01-01", periods=10)
    flows = [100.0] * 10
    fx_rates = [31.0 - 0.1 * i for i in range(10)]
    flow_df, fx_df = _make_flow_fx(dates, flows, fx_rates)
    sig = build_signals(flow_df, fx_df, window=5, flow_thr=50, fx_thr=0.5)
    for _, row in sig.iterrows():
        if row["state"] in STATE_TEXT:
            assert row["interpretation"] == STATE_TEXT[row["state"]]


def test_build_signals_divergence_states_set_matches_constant():
    assert DIVERGENCE_STATES == {
        "背離｜熱錢停泊匯市",
        "背離｜買盤遭拋匯掩蓋",
        "背離｜匯市先撤",
    }


def test_build_signals_no_overlap_dates_returns_empty():
    flow_df = pd.DataFrame({
        "date": pd.to_datetime(["2026-01-01", "2026-01-02"]),
        "foreign_net_yi": [10.0, 20.0],
    })
    fx_df = pd.DataFrame({
        "date": pd.to_datetime(["2027-01-01", "2027-01-02"]),
        "usdtwd": [30.0, 30.5],
    })
    sig = build_signals(flow_df, fx_df, window=5, flow_thr=50, fx_thr=0.5)
    assert sig.empty


# ────────────────────────────────────────────────────────────────────────
# _yf_series_to_df — yfinance / fetch_yf_close pd.Series 解析
# ────────────────────────────────────────────────────────────────────────
def test_yf_series_to_df_none_or_empty_returns_empty():
    assert _yf_series_to_df(None).empty
    assert _yf_series_to_df(pd.Series([], dtype=float)).empty


def test_yf_series_to_df_normal_series_round_trip():
    """有 datetime index 的正常 pd.Series → 標準 [date, usdtwd] df。"""
    idx = pd.date_range("2026-01-01", periods=5)
    series = pd.Series([31.0, 31.1, 31.2, 31.05, 30.9], index=idx)
    out = _yf_series_to_df(series)
    assert len(out) == 5
    assert list(out.columns) == ["date", "usdtwd"]
    assert out.iloc[0]["usdtwd"] == 31.0
    assert out.iloc[-1]["usdtwd"] == 30.9


def test_yf_series_to_df_drops_zero_and_negative_values():
    idx = pd.date_range("2026-01-01", periods=5)
    series = pd.Series([31.0, 0.0, 31.1, -1.0, 31.2], index=idx)
    out = _yf_series_to_df(series)
    assert len(out) == 3
    assert (out["usdtwd"] > 0).all()


def test_yf_series_to_df_handles_tz_aware_index():
    """tz-aware datetime index → 解 tz 後寫入。"""
    idx = pd.date_range("2026-01-01", periods=3, tz="Asia/Taipei")
    series = pd.Series([31.0, 31.1, 31.2], index=idx)
    out = _yf_series_to_df(series)
    assert len(out) == 3
    assert out["date"].iloc[0].tz is None


# ────────────────────────────────────────────────────────────────────────
# v18.240 regression：altair / typing_extensions chain smoke import
# ────────────────────────────────────────────────────────────────────────
def test_hot_money_module_imports_cleanly():
    """整個 hot_money + render 函式 import 不應炸 (TypedDict closed= 等)。

    v19.196 P0-4-A:UI/render 在 ui.hot_money,fetcher 在 repositories.hot_money_repository。
    """
    import importlib
    from repositories import hot_money_repository as _hm_repo
    from ui import hot_money as _hm
    importlib.reload(_hm_repo)
    importlib.reload(_hm)
    assert callable(_hm.render_hot_money_section)
    assert callable(_hm.build_signals)
    assert callable(_hm_repo._yf_series_to_df)
    assert callable(_hm_repo.fetch_foreign_flow_series)
    assert callable(_hm_repo.fetch_usdtwd_series)


def test_altair_import_chain_does_not_raise():
    """altair / narwhals / typing_extensions 全鏈 import 不可拋 TypeError
    (PR v18.240 修 _TypedDictMeta.__new__() got unexpected kwarg 'closed')。

    altair 6.x 重構移除 `altair.vegalite.v5.schema` 路徑 → 此情境直接 skip
    （TypedDict bug 與 schema 載入路徑無關，僅鎖死「import 不爆」）。"""
    import pytest
    try:
        import altair  # noqa: F401
        try:
            from altair.vegalite.v5.schema import _config  # noqa: F401
        except ModuleNotFoundError:
            pytest.skip("altair 6.x 已移除 vegalite.v5.schema 路徑")
    except TypeError as e:
        if "closed" in str(e):
            raise AssertionError(
                "altair _config import 踩到 TypedDict closed= bug "
                "(typing_extensions 太舊？)"
            ) from e
        raise
