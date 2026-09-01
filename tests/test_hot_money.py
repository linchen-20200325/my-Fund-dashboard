# -*- coding: utf-8 -*-
"""test_hot_money.py — 熱錢監測核心邏輯單元測試（基金倉版）

只測純函式（build_signals / _yf_series_to_df），不測 render UI（streamlit）
與 fetch FinMind / Yahoo（外部網路）。
"""
from __future__ import annotations

import pandas as pd

# v19.196 P0-4-A:hot_money.py 拆 2 檔
from repositories.hot_money_repository import (
    _yf_series_to_df,
    fetch_foreign_flow_series,
)
from ui.hot_money import (
    DIVERGENCE_STATES,
    STATE_TEXT,
    build_signals,
)


class _MockResp:
    """requests.Response mock。

    本檔原本沒有任何 HTTP mock（grep `status_code` / `def json` 皆 0 命中），
    FinMind 抓取路徑完全沒被測到。補上具真 `status_code` + 真 body 的 stub，
    避免用 MagicMock（`m.status_code` 會是 truthy 物件、`.get('status')` 回
    MagicMock）讓狀態碼檢查形同虛設。
    """

    def __init__(self, payload, status: int = 200):
        self._payload = payload
        self.status_code = status
        self.text = str(payload)[:500]

    def json(self):
        return self._payload


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
# fetch_foreign_flow_series — FinMind API 狀態碼（402 額度用盡）
# ────────────────────────────────────────────────────────────────────────
def _patch_finmind(monkeypatch, resp):
    """monkeypatch fund_fetcher.fetch_url_with_retry（fetcher 內 lazy import）。"""
    import fund_fetcher
    captured = {}

    def fake(url, params=None, timeout=15, retries=2, **kw):
        captured['url'] = url
        captured['params'] = params
        return resp

    monkeypatch.setattr(fund_fetcher, 'fetch_url_with_retry', fake)
    # @st.cache_data → 每測前清，避免跨測污染（各測另用相異 days 當 cache key 保險）
    if hasattr(fetch_foreign_flow_series, 'clear'):
        fetch_foreign_flow_series.clear()
    return captured


def test_foreign_flow_402_quota_exhausted_is_not_reported_as_no_data(monkeypatch):
    """本次稽核母題的核心迴歸測試。

    FinMind 免費額度用盡 → {"msg": "Requests reached the upper limit.", "status": 402}
    且 **不帶 data 欄**。修正前 `.get("data", [])` 吐 [] → 被歸類成
    「無資料回傳（可能為非交易日區間）」，於是「額度用盡」偽裝成「非交易日」，
    外資買賣超硬停在某一天長達數月而系統毫無警覺。
    """
    payload = {'msg': 'Requests reached the upper limit.', 'status': 402}
    _patch_finmind(monkeypatch, _MockResp(payload, status=402))

    df, err = fetch_foreign_flow_series(30)

    assert df.empty
    assert '402' in err, f"錯誤訊息必須帶狀態碼 402，實際：{err!r}"
    assert 'upper limit' in err, f"錯誤訊息必須帶 API msg，實際：{err!r}"
    # 反向鎖：不可再被說成「非交易日」
    assert '非交易日' not in err, f"402 被誤報成非交易日：{err!r}"


def test_foreign_flow_401_bad_token_surfaces_status(monkeypatch):
    payload = {'msg': 'token not valid', 'status': 401}
    _patch_finmind(monkeypatch, _MockResp(payload, status=401))
    df, err = fetch_foreign_flow_series(31, "bad-token")
    assert df.empty
    assert '401' in err


def test_foreign_flow_empty_data_is_reported_as_upstream_anomaly_not_holiday(monkeypatch):
    """~~status=200 + data 為空 → 才是真的「非交易日區間」，訊息不可被誤改。~~

    ⚠️ **2026-09-01 規格更正（有意識的政策變更，不是把測試改鬆）** ——
    原測試（`test_foreign_flow_empty_data_still_says_non_trading_day`）把
    「空 ⇒ 非交易日」釘成契約，但那個前提**經實測為假**：

      · production 的查詢視窗是 `days + 14`，而 `days` 來自 `ui/hot_money.py`
        的 `cc1.slider("回看天數", 60, 365, 180, step=30)`
        → **視窗恆為 74 ~ 379 個日曆日**；台灣最長連假約 9 天。
        一個 ≥ 74 天的視窗回傳 `data: []`，**不可能**是非交易日區間。
      · 於是舊訊息「無資料回傳（可能為非交易日區間）」在**唯一會發生的情境下
        是錯的歸因**，而且被 `@st.cache_data` 鎖 30 分鐘 —— 正是 §1
        「錯誤的數字比沒有數字更危險」，也正是憲法 §2.1 記載的
        `fetch_tw_export_yoy` 掛在不存在 dataset 上「恆無資料」活了好幾版的同型病。

    **本測試是加嚴不是放寬**：舊版只斷言 `df.empty` + 訊息含「非交易日」；
    新版另外釘住 (a) 反向鎖「不得再被說成非交易日」、(b) 訊息要帶得出視窗天數，
    以及 (c) **這次失敗有登記來源退避**（＝不會每次 rerun 都去打 FinMind，
    那才是當初「不敢改成 raise」的真正理由，現已由退避層承接）。
    """
    from infra import source_backoff as _sb
    _sb.reset_all()
    _patch_finmind(monkeypatch, _MockResp({'status': 200, 'data': []}))
    df, err = fetch_foreign_flow_series(32)
    assert df.empty
    # 反向鎖：與 402 那條同一個精神 —— 上游異常不得被說成休市
    assert '非交易日' not in err, f"上游異常被誤報成非交易日：{err!r}"
    assert '46' in err, f"訊息應帶出實際視窗天數（32+14=46），實際：{err!r}"
    # 失敗有被登記進來源冷卻 → 下一次 rerun 在 fetch_url 進場處就被擋下
    assert [d for d in _sb.get_backoff_state()
            if d['source'] == 'api.finmindtrade.com'], \
        f"應用層失敗未登記來源退避：{_sb.get_backoff_state()}"


def test_foreign_flow_none_response_mentions_proxy_log(monkeypatch):
    """fetch_url 全敗回 None → 訊息應指向 [proxy] log（狀態碼在那裡）。"""
    _patch_finmind(monkeypatch, None)
    df, err = fetch_foreign_flow_series(33)
    assert df.empty
    assert 'proxy' in err


def test_foreign_flow_token_forwarded(monkeypatch):
    """token 有傳才進 params（匿名 300 次/hr vs 具名 600 次/hr）。"""
    cap = _patch_finmind(monkeypatch, _MockResp({'status': 200, 'data': []}))
    fetch_foreign_flow_series(34, "tok-xyz")
    assert cap['params'].get('token') == 'tok-xyz'

    cap2 = _patch_finmind(monkeypatch, _MockResp({'status': 200, 'data': []}))
    fetch_foreign_flow_series(35)
    assert 'token' not in cap2['params']


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
