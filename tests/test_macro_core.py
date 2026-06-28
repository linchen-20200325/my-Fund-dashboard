"""
test_macro_core.py — macro_core 單元測試

驗證重點:
1. 純數學函式正確(zscore / trend_arrow / recession_probability / spread_series)
2. **所有外部 HTTP 抓取(fetch_fred / fetch_yf_close)都會呼叫 proxy_helper.fetch_url**,
   也就是必走 NAS 中繼站,不會繞道直連 yfinance / requests。
3. snapshot schema 工具(make_indicator / flatten_snapshot)雙向相容。
"""
from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pandas as pd

import repositories.macro_repository as macro_core


# ══════════════════════════════════════════════════════════════
# 1. 純數學函式
# ══════════════════════════════════════════════════════════════

def test_zscore_basic():
    s = pd.Series([1, 2, 3, 4, 5])
    z = macro_core.zscore(s)
    assert abs(float(z.mean())) < 1e-9
    assert abs(float(z.std()) - 1.0) < 1e-9


def test_zscore_zero_std_no_div_zero():
    """W5-5 §1 對齊:std=0 退化情境改回全 NaN(原 (z==0).all() 為 §1 違憲掩蓋斷言)。"""
    s = pd.Series([5, 5, 5, 5])
    z = macro_core.zscore(s)
    assert z.isna().all()


def test_trend_arrow_strictly_up():
    assert macro_core.trend_arrow([1, 2, 3, 4, 5]) == "持續上升 ↑"


def test_trend_arrow_strictly_down():
    assert macro_core.trend_arrow([5, 4, 3, 2, 1]) == "持續下降 ↓"


def test_trend_arrow_recent_rebound():
    assert macro_core.trend_arrow([5, 4, 3, 2, 3]) == "最近反彈 ↗"


def test_trend_arrow_too_short():
    assert macro_core.trend_arrow([1, 2]) == ""


def test_recession_probability_inverted():
    # 倒掛 -1% → 機率應顯著 > 50%
    p = macro_core.recession_probability(-1.0)
    assert p is not None and p > 60


def test_recession_probability_normal():
    # 正斜率 1.5% → 機率應 < 10%
    p = macro_core.recession_probability(1.5)
    assert p is not None and p < 10


def test_recession_probability_none():
    assert macro_core.recession_probability(None) is None


def test_spread_series_basic():
    dates_long = pd.date_range("2024-01-01", periods=12, freq="MS")
    dates_short = pd.date_range("2024-01-01", periods=12, freq="MS")
    df_long  = pd.DataFrame({"date": dates_long,  "value": np.linspace(4.0, 5.0, 12)})
    df_short = pd.DataFrame({"date": dates_short, "value": np.linspace(3.0, 4.5, 12)})
    sp = macro_core.spread_series(df_long, df_short, n_pts=12)
    assert not sp.empty
    # 第一筆與最後一筆都應為正值(long > short)
    assert float(sp.iloc[0])  > 0
    assert float(sp.iloc[-1]) >= 0


def test_spread_series_empty_input():
    assert macro_core.spread_series(pd.DataFrame(), pd.DataFrame()).empty


# ══════════════════════════════════════════════════════════════
# 2. NAS Proxy 強制使用驗證
# ══════════════════════════════════════════════════════════════

def test_fetch_fred_goes_through_proxy_helper(monkeypatch):
    """
    確認 fetch_fred() 一定透過 proxy_helper.fetch_url(走 NAS),
    不會自己 import requests 或 yfinance 直連。
    """
    captured = {}

    def fake_fetch_url(url, headers=None, params=None, timeout=20):
        captured["url"] = url
        captured["params"] = params
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "observations": [
                {"date": "2025-01-01", "value": "50.5"},
                {"date": "2025-02-01", "value": "51.2"},
                {"date": "2025-03-01", "value": "52.0"},
            ]
        }
        return mock_resp

    monkeypatch.setattr("repositories.macro_repository.fetch_url", fake_fetch_url)
    df = macro_core.fetch_fred("NAPM", "fake_key", n=10)

    assert captured["url"] == macro_core.FRED_BASE
    assert captured["params"]["series_id"] == "NAPM"
    assert captured["params"]["api_key"] == "fake_key"
    assert len(df) == 3
    # v19.60 D1:fetch_fred 統一補 realtime_start 欄(API 無回則填 NaT)
    # F-PROV-1 v19.82:新增 source + fetched_at provenance 欄位(§2.2)
    assert {"date", "value", "realtime_start", "source", "fetched_at"}.issubset(df.columns)
    assert df["value"].dtype == float
    assert (df["source"] == "FRED:NAPM").all()
    assert df["fetched_at"].notna().all()


def test_fetch_fred_empty_key_no_network():
    """空 api_key 直接回傳空 DataFrame,不應觸發任何 HTTP 呼叫。"""
    df = macro_core.fetch_fred("NAPM", "", n=10)
    assert df.empty


def test_fetch_fred_proxy_unreachable(monkeypatch):
    """fetch_url 回 None(NAS 與直連都失敗)→ 回傳空 DataFrame,不可拋。"""
    monkeypatch.setattr("repositories.macro_repository.fetch_url", lambda *a, **kw: None)
    df = macro_core.fetch_fred("NAPM", "key", n=10)
    assert df.empty


def test_fetch_yf_close_goes_through_proxy_helper(monkeypatch):
    """
    確認 fetch_yf_close() 走 proxy_helper.fetch_url 打 Chart API,
    而非直接 import yfinance。
    """
    captured = {}
    timestamps = [1735689600, 1735776000, 1735862400]  # 2025-01-01..03 UTC
    closes = [28.5, 29.1, 27.8]

    def fake_fetch_url(url, headers=None, params=None, timeout=15):
        captured["url"] = url
        captured["params"] = params
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "chart": {
                "result": [{
                    "timestamp": timestamps,
                    "indicators": {"quote": [{"close": closes}]},
                }]
            }
        }
        return mock_resp

    monkeypatch.setattr("repositories.macro_repository.fetch_url", fake_fetch_url)
    s = macro_core.fetch_yf_close("^VIX", range_="5d")

    assert captured["url"].endswith("/^VIX")
    assert captured["params"]["range"] == "5d"
    assert len(s) == 3
    assert float(s.iloc[-1]) == 27.8
    assert s.name == "^VIX"


def test_fetch_yf_close_proxy_failure(monkeypatch):
    monkeypatch.setattr("repositories.macro_repository.fetch_url", lambda *a, **kw: None)
    s = macro_core.fetch_yf_close("^VIX")
    assert s.empty


def test_fetch_yf_latest_batch(monkeypatch):
    timestamps = [1735862400]
    def fake_fetch_url(url, headers=None, params=None, timeout=15):
        if "VIX" in url:
            close_val = [22.5]
        elif "DX-Y" in url:
            close_val = [104.3]
        else:
            close_val = [None]
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "chart": {"result": [{
                "timestamp": timestamps,
                "indicators": {"quote": [{"close": close_val}]},
            }]}
        }
        return mock_resp

    monkeypatch.setattr("repositories.macro_repository.fetch_url", fake_fetch_url)
    out = macro_core.fetch_yf_latest(("^VIX", "DX-Y.NYB"))
    assert out["^VIX"]     == 22.5
    assert out["DX-Y.NYB"] == 104.3


# ══════════════════════════════════════════════════════════════
# 3. snapshot schema 工具
# ══════════════════════════════════════════════════════════════

def test_make_indicator_basic():
    s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0],
                  index=pd.date_range("2025-01-01", periods=5))
    ind = macro_core.make_indicator(
        "PMI", "ISM 製造業 PMI", 52.5,
        prev=51.8, unit="", type_="領先",
        date="2025-04", series=s, weight=2.0,
    )
    assert ind["key"] == "PMI"
    assert ind["value"] == 52.5
    assert ind["weight"] == 2.0
    # 序列遞增 → trend 應為「持續上升」
    assert ind["trend"] == "持續上升 ↑"


def test_make_indicator_no_series_no_trend():
    ind = macro_core.make_indicator("VIX", "VIX 恐慌指數", 25.0)
    assert ind["trend"] == ""


def test_flatten_snapshot_round_trip():
    rich = {
        "VIX": macro_core.make_indicator("VIX", "VIX", 28.3),
        "CPI": macro_core.make_indicator("CPI", "CPI", 3.1, unit="%"),
    }
    flat = macro_core.flatten_snapshot(rich)
    assert flat == {"vix": 28.3, "cpi": 3.1}


def test_flatten_snapshot_skips_none():
    rich = {
        "VIX": macro_core.make_indicator("VIX", "VIX", 28.3),
        "CPI": {"value": None},
        "X":   "not a dict",  # 不該 crash
    }
    flat = macro_core.flatten_snapshot(rich)
    assert flat == {"vix": 28.3}


# ══════════════════════════════════════════════════════════════
# 4. 統一閾值表健全性
# ══════════════════════════════════════════════════════════════

def test_thresholds_table_present():
    keys = {"VIX", "CPI", "PMI", "HY_SPREAD", "YIELD_10Y2Y", "YIELD_10Y3M"}
    assert keys.issubset(macro_core.MACRO_THRESHOLDS.keys())


def test_thresholds_cross_rates_present():
    """v18.107 跨幣別三組 EURUSD / USDJPY / USDCNH 門檻必須存在。"""
    keys = {"EURUSD", "USDJPY", "USDCNH"}
    assert keys.issubset(macro_core.MACRO_THRESHOLDS.keys()), \
        f"跨幣別門檻缺失：{keys - set(macro_core.MACRO_THRESHOLDS.keys())}"
    # 各組必有 yellow 或 red 中至少一個門檻
    for k in keys:
        rule = macro_core.MACRO_THRESHOLDS[k]
        assert any(t in rule for t in
                   ("green_above", "green_below", "yellow_above", "yellow_below",
                    "red_above", "red_below")), \
            f"{k} 門檻表為空"


def test_thresholds_consistent_red_yellow_ordering():
    """red/yellow_above 應 red > yellow;red/yellow_below 應 red < yellow。"""
    for key, rule in macro_core.MACRO_THRESHOLDS.items():
        if "red_above" in rule and "yellow_above" in rule:
            assert rule["red_above"] >= rule["yellow_above"], f"{key} above 反序"
        if "red_below" in rule and "yellow_below" in rule:
            assert rule["red_below"] <= rule["yellow_below"], f"{key} below 反序"


# ══════════════════════════════════════════════════════════════
# 5. v18.21 倒掛翻正歷史回測（macro_engine.backtest_turning_points）
# ══════════════════════════════════════════════════════════════

def test_backtest_turning_points_no_key():
    """空 FRED key → source_ok=False，不丟例外。"""
    import services.macro_service as macro_engine
    r = macro_engine.backtest_turning_points("")
    assert r["source_ok"] is False
    assert r["summary"]["n_events"] == 0
    assert "FRED" in r["note"]


def _synth_t10y2y_with_inversions() -> pd.DataFrame:
    """合成 4 段倒掛 T10Y2Y 序列（對應 1990/2000/2008/2020）→ DataFrame。"""
    rng = pd.date_range("1989-01-01", "2023-12-31", freq="B")
    vals = np.full(len(rng), 0.5)
    # 預定 4 段倒掛：min_inversion_depth=-0.10 用 -0.4 深倒掛
    segments = [
        ("1989-06-01", "1989-12-15", "1990-01-15"),
        ("2000-01-01", "2000-12-15", "2001-01-15"),
        ("2006-08-01", "2007-05-15", "2007-06-01"),
        ("2019-08-01", "2019-10-15", "2019-11-01"),
    ]
    for inv_start, inv_end, _flip in segments:
        mask = (rng >= inv_start) & (rng <= inv_end)
        vals[mask] = -0.4
    # 翻正日後保持 +0.3（穩定翻正）
    return pd.DataFrame({"date": rng, "value": vals})


def _synth_spx_uptrend() -> pd.Series:
    """合成 SPX 序列：1989 至今每年 +10%，足以保證後續 6/12/18M 正報酬。"""
    rng = pd.date_range("1989-01-01", "2025-12-31", freq="B")
    # 起始 100 + 每日 10% / 252 ≈ 0.0397%
    daily = 0.10 / 252
    prices = 100.0 * np.cumprod(1 + np.full(len(rng), daily))
    return pd.Series(prices, index=rng, name="^GSPC")


def test_backtest_turning_points_event_detection(monkeypatch):
    """mock FRED + SPX，斷言識別到 4 個事件且 12M 報酬皆 > 0。"""
    import services.macro_service as macro_engine
    # v19.199 P1-7:fetch_fred 引用走 services.macro.turning_points(原 monkeypatch
    # services.macro_service 在 shim 化後無效)
    monkeypatch.setattr("services.macro.turning_points.fetch_fred",
                        lambda sid, key, n=250: _synth_t10y2y_with_inversions())
    monkeypatch.setattr("services.macro.turning_points.fetch_yf_close",
                        lambda t, range_="2y", interval="1d": _synth_spx_uptrend())

    r = macro_engine.backtest_turning_points(
        "FAKE_KEY", min_inversion_depth=-0.10, stable_days=5, cooldown_days=365,
    )
    assert r["source_ok"] is True
    assert r["summary"]["n_events"] == 4, f"expected 4 events, got {r['summary']['n_events']}"
    # 純上升 SPX → 全部 12M 報酬 > 0
    for ev in r["events"]:
        assert ev["ret_12m"] is not None and ev["ret_12m"] > 0
    assert r["summary"]["win_rate_12m"] == 100.0
    # 中位數 12M 應落在 9~11%（一年 ~10%）
    assert 8.0 < r["summary"]["median_12m"] < 12.0


def test_backtest_turning_points_incomplete_window(monkeypatch):
    """事件日 < 18M before today → complete=False，不污染 median_18m。"""
    import services.macro_service as macro_engine

    today = pd.Timestamp.today().normalize()
    # 製造 2 個事件：一個 2 年前（完整），一個 3 個月前（不完整）
    rng = pd.date_range("2020-01-01", today + pd.Timedelta(days=5), freq="B")
    vals = np.full(len(rng), 0.5)
    # 第一段倒掛：2 年前翻正
    flip1 = today - pd.Timedelta(days=730)
    inv1_start = flip1 - pd.Timedelta(days=180)
    mask = (rng >= inv1_start) & (rng < flip1)
    vals[mask] = -0.4
    # 第二段倒掛：3 個月前翻正
    flip2 = today - pd.Timedelta(days=90)
    inv2_start = flip2 - pd.Timedelta(days=180)
    mask = (rng >= inv2_start) & (rng < flip2)
    vals[mask] = -0.4
    df_t = pd.DataFrame({"date": rng, "value": vals})

    # v19.199 P1-7:fetch_fred 引用走 services.macro.turning_points(原 monkeypatch
    # services.macro_service 在 shim 化後無效)
    monkeypatch.setattr("services.macro.turning_points.fetch_fred",
                        lambda sid, key, n=250: df_t)
    monkeypatch.setattr("services.macro.turning_points.fetch_yf_close",
                        lambda t, range_="2y", interval="1d":
                        pd.Series(np.linspace(100, 200, len(rng)), index=rng))

    r = macro_engine.backtest_turning_points(
        "FAKE_KEY", min_inversion_depth=-0.10, stable_days=5, cooldown_days=180,
    )
    assert r["source_ok"] is True
    assert r["summary"]["n_events"] == 2
    # 第二個事件 18M 窗口未到期
    assert r["summary"]["n_complete_18m"] == 1
    # median_18m 只應算 complete 事件，不該包含 None
    if r["summary"]["median_18m"] is not None:
        # 只一個樣本，且為合成上升序列，必 > 0
        assert r["summary"]["median_18m"] > 0


# ════════════════════════════════════════════════════════════
# §6 景氣循環細項燈號（Phase 2 — v18.100）
# ════════════════════════════════════════════════════════════
def _make_synth_indicator(values: list, current: float = None) -> dict:
    """構造 indicators[key] 的簡化 dict（series + value）。"""
    import pandas as _pd
    s = _pd.Series(values, index=_pd.date_range("2020-01-01",
                                                 periods=len(values), freq="MS"))
    return {"series": s, "value": current if current is not None else values[-1]}


def test_calc_sub_cycle_lights_returns_seven_groups():
    """無論 indicators 是否齊全，回傳必為 7 個子領域。"""
    from services.macro_service import calc_sub_cycle_lights
    out = calc_sub_cycle_lights({})
    assert isinstance(out, list) and len(out) == 7
    # 全空 → 都應該是「資料不足」⬜
    for c in out:
        assert c["signal"] == "⬜"
        assert c["z_avg"] is None
        assert c["verdict"] == "資料不足"


def test_calc_sub_cycle_lights_healthy_signal():
    """製造業：PMI/LEI 都高於均值（high_is_bad=False）→ z_norm 負 → 🟢 健康。"""
    from services.macro_service import calc_sub_cycle_lights
    # PMI 12 期，均值 ~50；最新 60（+1.5σ 以上）
    pmi_hist = [50] * 11 + [60]
    lei_hist = [0] * 11 + [1.5]
    out = calc_sub_cycle_lights({
        "PMI": _make_synth_indicator(pmi_hist, current=60),
        "LEI": _make_synth_indicator(lei_hist, current=1.5),
    })
    mfg = next(c for c in out if c["name"] == "製造業")
    assert mfg["signal"] == "🟢"
    assert mfg["verdict"] == "健康"
    assert mfg["z_avg"] is not None and mfg["z_avg"] < -1.0


def test_calc_sub_cycle_lights_warning_signal():
    """信貸：SLOOS/HY_SPREAD 都顯著高於均值（high_is_bad=True）→ 🔴 警示。"""
    from services.macro_service import calc_sub_cycle_lights
    sloos_hist = [0] * 11 + [40]   # 最新 40，遠高於均值 0
    hy_hist    = [4.0] * 11 + [8.0]
    out = calc_sub_cycle_lights({
        "SLOOS": _make_synth_indicator(sloos_hist, current=40),
        "HY_SPREAD": _make_synth_indicator(hy_hist, current=8.0),
    })
    credit = next(c for c in out if c["name"] == "信貸")
    assert credit["signal"] == "🔴"
    assert credit["verdict"] == "警示"
    assert credit["z_avg"] is not None and credit["z_avg"] >= 1.0


def test_calc_sub_cycle_lights_partial_data():
    """單一指標可用 → 仍能算出 z_avg（不要因半成資料整組降為 ⬜）。"""
    from services.macro_service import calc_sub_cycle_lights
    permit_hist = [1400] * 11 + [1800]
    out = calc_sub_cycle_lights({
        "PERMIT_HOUSING": _make_synth_indicator(permit_hist, current=1800),
    })
    housing = next(c for c in out if c["name"] == "房市")
    assert housing["z_avg"] is not None
    assert len(housing["indicators"]) == 1


# ════════════════════════════════════════════════════════════
# §7 總經因果鏈 Sankey（Phase 2 — v18.101）
# ════════════════════════════════════════════════════════════
def test_build_macro_sankey_data_empty_indicators():
    """無 indicators → ok=False, 全部節點 z 為 None。"""
    from services.macro_service import build_macro_sankey_data
    out = build_macro_sankey_data({})
    assert out["ok"] is False
    assert len(out["labels"]) == 8
    assert len(out["sources"]) == len(out["targets"]) == len(out["values"]) == 9


def test_build_macro_sankey_data_partial_ok():
    """5/8 節點有 z（>=4=50%）→ ok=True，色彩依 high_is_bad 翻轉。"""
    from services.macro_service import build_macro_sankey_data
    base = [50] * 11 + [60]   # +z
    out = build_macro_sankey_data({
        "FED_RATE":       _make_synth_indicator(base, current=60),
        "SLOOS":          _make_synth_indicator(base, current=60),
        "HY_SPREAD":      _make_synth_indicator(base, current=60),
        "PERMIT_HOUSING": _make_synth_indicator(base, current=60),
        "JOBLESS":        _make_synth_indicator(base, current=60),
    })
    assert out["ok"] is True
    # FED_RATE high_is_bad=True，z>>0 → 應該紅
    fed_idx = next(i for i, l in enumerate(out["labels"]) if "聯準會" in l)
    assert out["node_colors"][fed_idx] == "#f44336"
    # PERMIT_HOUSING high_is_bad=False，z>>0 → 翻轉後 z_norm<<0 → 應該綠
    permit_idx = next(i for i, l in enumerate(out["labels"]) if "建照" in l)
    assert out["node_colors"][permit_idx] == "#4caf50"


def test_build_macro_sankey_data_link_values_use_zscore():
    """邊粗細＝起點 |z|（最小 0.3）；缺資料退化為 0.3。"""
    from services.macro_service import build_macro_sankey_data
    out = build_macro_sankey_data({})
    # 全空 → 所有 value 應為 0.3 floor
    assert all(v == 0.3 for v in out["values"])


# ════════════════════════════════════════════════════════════
# §8 總經指南針 Phase 3（v18.105）
#  (A) build_macro_sankey_dynamic — 動態權重 Sankey
#  (B) backtest_sub_cycle_lights  — 細項燈號歷史回測
# ════════════════════════════════════════════════════════════
def _make_long_series(n: int = 80, base: float = 50.0,
                      slope: float = 0.05, seed: int = 0) -> dict:
    """構造一個 n 期月頻 series 的 indicator dict。"""
    import pandas as _pd
    import numpy as _np
    _np.random.seed(seed)
    noise = _np.random.normal(0, 1.0, n)
    vals = base + slope * _np.arange(n) + noise
    idx = _pd.date_range("2020-01-01", periods=n, freq="MS")
    s = _pd.Series(vals, index=idx)
    return {"series": s, "value": float(s.iloc[-1])}


def test_build_macro_sankey_dynamic_empty():
    """無 indicators → fallback 同 build_macro_sankey_data，link_corrs 全 None。"""
    from services.macro_service import build_macro_sankey_dynamic
    out = build_macro_sankey_dynamic({})
    assert out["ok"] is False
    assert len(out["link_corrs"]) == 9
    assert all(c is None for c in out["link_corrs"])


def test_build_macro_sankey_dynamic_uses_correlation():
    """全節點有 series → values 應依 |corr| 變化，link_corrs 應有實數。"""
    from services.macro_service import build_macro_sankey_dynamic
    ind = {key: _make_long_series(seed=i)
           for i, (key, *_) in enumerate([
               ("FED_RATE", "", 0, True), ("SLOOS", "", 1, True),
               ("HY_SPREAD", "", 1, True), ("PERMIT_HOUSING", "", 2, False),
               ("JOBLESS", "", 2, True), ("PMI", "", 2, False),
               ("VIX", "", 3, True), ("DXY", "", 3, True),
           ])}
    out = build_macro_sankey_dynamic(ind)
    assert out["ok"] is True
    # 至少有 5 條邊有實際 corr 值
    n_with_corr = sum(1 for c in out["link_corrs"] if c is not None)
    assert n_with_corr >= 5
    # values 範圍 [0.3, 6.0]
    assert all(0.3 <= v <= 6.0 for v in out["values"])
    # 邊 label 有 corr 註記
    assert any("corr=" in lbl for lbl in out["link_labels"])


def test_backtest_sub_cycle_lights_no_target():
    """target_key 缺 series → 全部子領域回「資料不足」/「target 無 series」verdict。"""
    from services.macro_service import backtest_sub_cycle_lights
    out = backtest_sub_cycle_lights({}, target_key="LEI")
    assert len(out) == 7
    for c in out:
        assert c["n_obs"] == 0
        assert c["fwd_chg_red"] is None
        assert "資料不足" in c["verdict"] or "無 series" in c["verdict"]


def test_backtest_sub_cycle_lights_full_history():
    """製造業（PMI+LEI）+ target=LEI 有 80 期歷史 → 應產生分桶 + verdict 含 '紅燈後/綠燈後'。"""
    from services.macro_service import backtest_sub_cycle_lights
    ind = {
        "PMI": _make_long_series(n=80, base=50, slope=0.1, seed=1),
        "LEI": _make_long_series(n=80, base=0, slope=0.02, seed=2),
    }
    out = backtest_sub_cycle_lights(ind, target_key="LEI",
                                     window=24, forward_months=3)
    mfg = next(c for c in out if c["name"] == "製造業")
    assert mfg["n_obs"] > 0
    # 至少一個桶該有樣本
    total = mfg["n_red"] + mfg["n_orange"] + mfg["n_yellow"] + mfg["n_green"]
    assert total == mfg["n_obs"]


# ════════════════════════════════════════════════════════════
# §9 總經指南針 Phase 4（v18.108）— rank_macro_drivers
# ════════════════════════════════════════════════════════════
def test_rank_macro_drivers_empty():
    """無 indicators → ok=False, ranked=[]."""
    from services.macro_service import rank_macro_drivers
    out = rank_macro_drivers({}, target_key="LEI")
    assert out["ok"] is False
    assert out["ranked"] == []


def test_rank_macro_drivers_returns_sorted_by_abs_corr():
    """target+多 driver 都有 series → ranked 按 abs_corr 降序排列。"""
    from services.macro_service import rank_macro_drivers
    import pandas as _pd
    import numpy as _np

    n = 100
    _np.random.seed(42)
    idx = _pd.date_range("2018-01-01", periods=n, freq="ME")
    # target：LEI，純隨機
    lei = _pd.Series(_np.cumsum(_np.random.normal(0, 1, n)), index=idx)
    # 強 driver：高度同向相關（與 lei 加少量噪聲）
    strong = lei + _pd.Series(_np.random.normal(0, 0.3, n), index=idx)
    # 弱 driver：純隨機，與 lei 不相關
    weak = _pd.Series(_np.random.normal(0, 1, n), index=idx).cumsum()

    ind = {
        "LEI":   {"series": lei,    "value": float(lei.iloc[-1])},
        "PMI":   {"series": strong, "value": float(strong.iloc[-1])},
        "VIX":   {"series": weak,   "value": float(weak.iloc[-1])},
    }
    out = rank_macro_drivers(ind, target_key="LEI", lag_months=3, min_overlap=24)
    assert out["ok"] is True
    # PMI 應排第一
    assert out["ranked"][0]["key"] == "PMI", \
        f"預期 PMI 排名第一，實際: {[r['key'] for r in out['ranked']]}"
    # abs_corr 應降序
    abs_corrs = [r["abs_corr"] for r in out["ranked"]]
    assert abs_corrs == sorted(abs_corrs, reverse=True), \
        f"ranked 未按 abs_corr 降序: {abs_corrs}"


def test_rank_macro_drivers_skips_target_self():
    """target 自己不應出現在 ranked 列表。"""
    from services.macro_service import rank_macro_drivers
    import pandas as _pd
    import numpy as _np
    _np.random.seed(7)
    idx = _pd.date_range("2018-01-01", periods=60, freq="ME")
    # 用非 constant diff 的隨機 walk（避免 diff(lag) 後 variance=0 撞 NaN corr）
    s1 = _pd.Series(_np.cumsum(_np.random.normal(0, 1, 60)), index=idx)
    s2 = _pd.Series(_np.cumsum(_np.random.normal(0, 1, 60)), index=idx)
    ind = {
        "PMI": {"series": s1, "value": float(s1.iloc[-1])},
        "LEI": {"series": s2, "value": float(s2.iloc[-1])},
    }
    out = rank_macro_drivers(ind, target_key="PMI", lag_months=3, min_overlap=24)
    # target=PMI 不應出現在 ranked
    assert all(r["key"] != "PMI" for r in out["ranked"]), \
        f"target=PMI 不應出現在 ranked: {[r['key'] for r in out['ranked']]}"


def test_rank_macro_drivers_insufficient_overlap():
    """driver 樣本 < min_overlap → 應被跳過。"""
    from services.macro_service import rank_macro_drivers
    import pandas as _pd
    # target 60 期
    t = _pd.Series(range(60), index=_pd.date_range("2018-01-01", periods=60,
                                                     freq="ME"), dtype=float)
    # driver 只有 10 期（不到 min_overlap=24）
    short = _pd.Series(range(10), index=_pd.date_range("2018-01-01", periods=10,
                                                        freq="ME"), dtype=float)
    ind = {
        "LEI": {"series": t,     "value": 59.0},
        "PMI": {"series": short, "value": 9.0},
    }
    out = rank_macro_drivers(ind, target_key="LEI", lag_months=3, min_overlap=24)
    # PMI 樣本不足 → 不在 ranked 中
    assert all(r["key"] != "PMI" for r in out["ranked"])
