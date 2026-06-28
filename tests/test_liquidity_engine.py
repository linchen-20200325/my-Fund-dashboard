"""test_liquidity_engine.py — v18.224 流動性預警引擎數據獲取層測試。

全部 mock repositories 抓取器，不打網路；驗證 Z-Score 邊界、dict schema、
四因子建構與失敗隔離。
"""
import numpy as np
import pandas as pd

import services.liquidity_engine as le


def _dates(n: int) -> pd.DatetimeIndex:
    return pd.date_range(end="2026-05-20", periods=n, freq="D")


# ── rolling_zscore：邊界防禦 ──────────────────────────────────
def test_zscore_normal_spike_high() -> None:
    s = pd.Series([1.0] * 250 + [1.0, 1.1, 0.9, 1.0, 5.0])  # 末點暴衝
    z = le.rolling_zscore(s)
    assert z is not None and z > 2


def test_zscore_insufficient_samples_none() -> None:
    assert le.rolling_zscore(pd.Series([1.0, 2.0, 3.0])) is None   # < 60


def test_zscore_flat_line_zero_std_none() -> None:
    assert le.rolling_zscore(pd.Series([3.14] * 200)) is None      # std=0


def test_zscore_handles_inf_nan() -> None:
    s = pd.Series([1.0] * 100 + [np.inf, np.nan] + [2.0] * 100)
    assert le.rolling_zscore(s) is not None   # inf/nan 被清掉不崩潰


# ── _sig_color_score：方向與門檻 ─────────────────────────────
def test_sig_high_z_is_red() -> None:
    assert le._sig_color_score(2.5)[0] == "🔴"
    assert le._sig_color_score(2.5)[2] == -1


def test_sig_invert_high_z_is_green() -> None:
    assert le._sig_color_score(2.5, invert=True)[0] == "🟢"


def test_sig_none_is_blank_neutral() -> None:
    assert le._sig_color_score(None) == ("⬜", "#666", 0)


# ── 四因子建構（mock 抓取器）────────────────────────────────
def _fred_df(series_id, api_key, n=250):
    base = {"DTWEXBGS": 120.0, "DEXJPUS": 150.0, "DEXSZUS": 0.9}.get(series_id, 100.0)
    rng = np.linspace(0, 1, 300)
    vals = base * (1 + 0.05 * np.sin(rng * 20) + 0.1 * rng)
    return pd.DataFrame({"date": _dates(300), "value": vals})


def _yf(ticker, range_="2y", interval="1d"):
    base = {"^MOVE": 110.0, "^VIX": 16.0, "BTC-USD": 60000.0}.get(ticker, 50.0)
    rng = np.linspace(0, 1, 300)
    vals = base * (1 + 0.1 * np.sin(rng * 15) + 0.05 * rng)
    return pd.Series(vals, index=_dates(300), name=ticker)


def _stable():
    rng = np.linspace(0, 1, 300)
    return pd.Series(150e9 * (1 + 0.2 * rng), index=_dates(300), name="stablecoin_mcap")


_REQUIRED_KEYS = {"name", "value", "prev", "unit", "type", "desc",
                  "signal", "color", "score", "weight", "series", "zscore"}


def _assert_schema(entry: dict) -> None:
    assert _REQUIRED_KEYS <= set(entry), set(entry)
    assert entry["signal"] in {"🟢", "🟡", "🔴", "⬜"}
    assert isinstance(entry["series"], pd.Series)
    assert isinstance(entry["score"], int) and entry["score"] in (-1, 0, 1)


def test_build_xccy_proxy(monkeypatch) -> None:
    monkeypatch.setattr(le, "fetch_fred", _fred_df)
    e = le.build_xccy_proxy("KEY")
    assert e is not None
    _assert_schema(e)
    assert "代理" in e["name"] and "代理" in e["desc"]   # 誠實標註


def test_build_carry_unwind(monkeypatch) -> None:
    monkeypatch.setattr(le, "fetch_fred", _fred_df)
    e = le.build_carry_unwind("KEY")
    assert e is not None
    _assert_schema(e)


def test_build_move_vix(monkeypatch) -> None:
    monkeypatch.setattr(le, "fetch_yf_close", _yf)
    e = le.build_move_vix()
    assert e is not None
    _assert_schema(e)
    assert e["value"] > 0   # MOVE/VIX 比值為正


def test_build_ssr(monkeypatch) -> None:
    monkeypatch.setattr(le, "fetch_defillama_stablecoin_mcap", _stable)
    monkeypatch.setattr(le, "fetch_yf_close", _yf)
    e = le.build_ssr()
    assert e is not None
    _assert_schema(e)


# ── 邊界：抓不到資料 → None，不崩潰 ─────────────────────────
def test_builders_empty_source_returns_none(monkeypatch) -> None:
    monkeypatch.setattr(le, "fetch_fred", lambda *a, **k: pd.DataFrame())
    monkeypatch.setattr(le, "fetch_yf_close", lambda *a, **k: pd.Series(dtype=float))
    monkeypatch.setattr(le, "fetch_defillama_stablecoin_mcap",
                        lambda: pd.Series(dtype=float))
    assert le.build_xccy_proxy("K") is None
    assert le.build_carry_unwind("K") is None
    assert le.build_move_vix() is None
    assert le.build_ssr() is None


# ── 入口：聚合 + 失敗隔離 ───────────────────────────────────
def test_fetch_liquidity_factors_aggregates(monkeypatch) -> None:
    monkeypatch.setattr(le, "fetch_fred", _fred_df)
    monkeypatch.setattr(le, "fetch_yf_close", _yf)
    monkeypatch.setattr(le, "fetch_defillama_stablecoin_mcap", _stable)
    out = le.fetch_liquidity_factors("KEY")
    # v19.233 F-PROV-1 cluster C:_provenance key schema-additive,排除後比對 builder set
    factor_keys = {k for k in out if not k.startswith("_")}
    assert factor_keys == {"XCCY_PROXY", "CARRY_UNWIND", "SSR", "MOVE_VIX"}
    assert "_provenance" in out
    assert "sources" in out["_provenance"] and "fetched_at" in out["_provenance"]


def test_fetch_liquidity_factors_isolates_failure(monkeypatch) -> None:
    monkeypatch.setattr(le, "fetch_fred", _fred_df)
    monkeypatch.setattr(le, "fetch_yf_close", _yf)

    def _boom():
        raise RuntimeError("defillama down")

    monkeypatch.setattr(le, "fetch_defillama_stablecoin_mcap", _boom)
    out = le.fetch_liquidity_factors("KEY")
    assert "SSR" not in out                       # 失敗的略過
    assert {"XCCY_PROXY", "CARRY_UNWIND", "MOVE_VIX"} <= set(out)   # 其餘正常


# ── 融合層：compute_liquidity_score（B 案：SSR 不計入）─────────
def _fac(z, name="f"):
    return {"zscore": z, "name": name, "value": z, "signal": "🟡"}


def test_score_weighted_sum() -> None:
    # 預設權重 0.4/0.3/0.3：2*.4 + 1*.3 + 0*.3 = 1.1 → 警戒
    out = le.compute_liquidity_score({
        "XCCY_PROXY": _fac(2.0), "CARRY_UNWIND": _fac(1.0), "MOVE_VIX": _fac(0.0),
    })
    assert out is not None
    assert abs(out["value"] - 1.1) < 1e-6
    assert out["tier"] == "警戒"
    assert abs(sum(b["contrib"] for b in out["breakdown"]) - out["value"]) < 1e-6


def test_score_clips_extreme_z() -> None:
    # z=10 應被 clip 到 3；單因子在線 → 權重正規化為 1 → 分數=3
    out = le.compute_liquidity_score({"XCCY_PROXY": _fac(10.0)})
    assert out["value"] == 3.0
    assert out["breakdown"][0]["z"] == 3.0


def test_score_ssr_excluded() -> None:
    # SSR 極端值不得影響壓力分數（B 案）
    base = le.compute_liquidity_score({
        "XCCY_PROXY": _fac(1.0), "CARRY_UNWIND": _fac(1.0), "MOVE_VIX": _fac(1.0),
    })
    with_ssr = le.compute_liquidity_score({
        "XCCY_PROXY": _fac(1.0), "CARRY_UNWIND": _fac(1.0), "MOVE_VIX": _fac(1.0),
        "SSR": _fac(9.0, "ssr"),
    })
    assert base["value"] == with_ssr["value"]        # SSR 不進總分
    assert with_ssr["ssr"] is not None               # 但有附掛對照
    assert with_ssr["ssr"]["zscore"] == 9.0


def test_score_missing_factor_renormalizes() -> None:
    # 只剩兩因子：權重 0.4/0.3 重正規化 → 0.571/0.429；2*.571+0*.429≈1.143
    out = le.compute_liquidity_score({
        "XCCY_PROXY": _fac(2.0), "MOVE_VIX": _fac(0.0),
    })
    assert abs(sum(out["weights"].values()) - 1.0) < 1e-6
    assert abs(out["value"] - 2.0 * (0.4 / 0.7)) < 1e-3


def test_score_skips_none_zscore() -> None:
    out = le.compute_liquidity_score({
        "XCCY_PROXY": _fac(None), "CARRY_UNWIND": _fac(2.0), "MOVE_VIX": _fac(2.0),
    })
    assert set(out["weights"]) == {"CARRY_UNWIND", "MOVE_VIX"}   # None 被略過


def test_score_all_missing_none() -> None:
    assert le.compute_liquidity_score({}) is None
    assert le.compute_liquidity_score({"SSR": _fac(1.0)}) is None   # 只有 SSR 不算


def test_score_tiers() -> None:
    # 單因子在線 → 分數=clip(z)，逐檔驗門檻
    assert le.compute_liquidity_score({"XCCY_PROXY": _fac(2.5)})["tier"] == "流動性危機"
    assert le.compute_liquidity_score({"XCCY_PROXY": _fac(1.5)})["tier"] == "警戒"
    assert le.compute_liquidity_score({"XCCY_PROXY": _fac(0.7)})["tier"] == "正常偏緊"
    assert le.compute_liquidity_score({"XCCY_PROXY": _fac(0.1)})["tier"] == "寬鬆充裕"
    assert le.compute_liquidity_score({"XCCY_PROXY": _fac(-2.0)})["tier"] == "寬鬆充裕"


# ── rolling_zscore_series：整條序列 ─────────────────────────
def test_zscore_series_last_matches_scalar() -> None:
    s = pd.Series(np.random.RandomState(0).randn(300).cumsum(),
                  index=_dates(300))
    zs = le.rolling_zscore_series(s)
    assert isinstance(zs, pd.Series) and len(zs) > 0
    assert abs(float(zs.iloc[-1]) - le.rolling_zscore(s)) < 1e-9   # 末點一致


def test_zscore_series_insufficient_empty() -> None:
    assert le.rolling_zscore_series(pd.Series([1.0, 2.0])).empty
    assert le.rolling_zscore_series(pd.Series([5.0] * 200)).empty   # 全平


# ── 合成歷史序列 score_series ───────────────────────────────
def _fac_z(z, name="f"):
    """帶 z_series 的因子（末點=zscore，供合成序列）。"""
    zs = pd.Series(np.linspace(z - 1, z, 120), index=_dates(120))
    return {"zscore": z, "name": name, "value": z, "signal": "🟡", "z_series": zs}


def test_score_series_built_and_consistent() -> None:
    out = le.compute_liquidity_score({
        "XCCY_PROXY": _fac_z(2.0), "CARRY_UNWIND": _fac_z(1.0),
        "MOVE_VIX": _fac_z(0.0),
    })
    ss = out["score_series"]
    assert isinstance(ss, pd.Series) and len(ss) > 0
    # 末點 ≈ 純量 score（同 clip+權重）
    assert abs(float(ss.iloc[-1]) - out["value"]) < 0.05


def test_score_series_empty_when_no_zseries() -> None:
    out = le.compute_liquidity_score({"XCCY_PROXY": _fac(1.0)})   # 無 z_series
    assert out["score_series"].empty


# ── liquidity_verdict：研判文字 ─────────────────────────────
def test_verdict_none_safe() -> None:
    assert "資料不足" in le.liquidity_verdict(None)


def test_verdict_mentions_tier_and_driver() -> None:
    out = le.compute_liquidity_score({
        "XCCY_PROXY": _fac(2.5), "CARRY_UNWIND": _fac(0.0), "MOVE_VIX": _fac(0.0),
        "SSR": _fac(-2.0, "ssr"),
    })
    txt = le.liquidity_verdict(out, {})
    assert out["tier"] in txt                       # 含分級
    assert "主導因子" in txt                          # 含主導因子
    assert "子彈水位充裕" in txt                       # SSR Z<-1 → 充裕
