"""淨值×匯率 二維買賣切換(v19.426)。驗:匯率位階 z 分類、邊界、缺料;2D 矩陣兩角有向 + 守衛。"""
import numpy as np
import pandas as pd

from services.nav_fx_switch import fx_regime, nav_fx_signal

_D = pd.date_range("2023-01-02", periods=260, freq="B")


def _fx(mean=32.0, std=0.5, n=250, seed=0):
    rng = np.random.default_rng(seed)
    return pd.Series(np.clip(rng.normal(mean, std, n), 1.0, None), index=_D[:n])


# ── fx_regime ───────────────────────────────────────────
def test_strong_twd_low_usdtwd():
    s = _fx()
    _m, _sd = float(s.mean()), float(s.std())
    r = fx_regime(s, spot=_m - 1.0 * _sd)
    assert r["regime"] == "strong_twd" and r["z"] < -0.7 and r["robust"] is True


def test_weak_twd_high_usdtwd():
    s = _fx()
    _m, _sd = float(s.mean()), float(s.std())
    assert fx_regime(s, spot=_m + 1.0 * _sd)["regime"] == "weak_twd"


def test_neutral():
    s = _fx()
    assert fx_regime(s, spot=float(s.mean()))["regime"] == "neutral"


def test_boundary_past_cutoff():
    s = _fx()
    _m, _sd = float(s.mean()), float(s.std())
    # 剛好 ±0.7σ 因浮點抵消(m 大)不可靠 → 測略過門檻(−0.71 / +0.71)確認分類正確
    assert fx_regime(s, spot=_m - 0.71 * _sd)["regime"] == "strong_twd"
    assert fx_regime(s, spot=_m + 0.71 * _sd)["regime"] == "weak_twd"
    assert fx_regime(s, spot=_m - 0.5 * _sd)["regime"] == "neutral"      # 門檻內 → 中性


def test_short_history_none():
    r = fx_regime(_fx(n=40))
    assert r["regime"] is None and "不足" in r["error"] and r["n"] == 40


def test_degenerate_std_zero_none():
    r = fx_regime(pd.Series([32.0] * 100, index=_D[:100]))
    assert r["regime"] is None and "σ=0" in r["error"]


def test_spot_fallback_to_last():
    s = _fx()
    r = fx_regime(s, spot=None)
    assert r["cur"] == round(float(s.iloc[-1]), 4)
    assert fx_regime(s, spot=-1)["cur"] == round(float(s.iloc[-1]), 4)   # 非正 → fallback


def test_none_series():
    assert fx_regime(None)["regime"] is None


# ── nav_fx_signal 3×3 + 守衛 ────────────────────────────
def test_buy_corner():
    r = nav_fx_signal("low", "strong_twd")
    assert r["tier"] == "buy" and "進場" in r["signal"]


def test_sell_corner():
    r = nav_fx_signal("high", "weak_twd")
    assert r["tier"] == "sell" and "出場" in r["signal"]


def test_watch_cells():
    for _nav, _fx in [("low", "weak_twd"), ("high", "strong_twd"), ("mid", "neutral"),
                      ("low", "neutral"), ("mid", "strong_twd"), ("mid", "weak_twd"),
                      ("high", "neutral")]:
        assert nav_fx_signal(_nav, _fx)["tier"] == "watch"


def test_na_guards():
    assert nav_fx_signal("unknown", "strong_twd")["tier"] == "na"
    assert nav_fx_signal(None, "weak_twd")["tier"] == "na"
    assert nav_fx_signal("low", None)["tier"] == "na"


def test_matrix_exactly_two_directional():
    """9 格中恰 2 格有向(低+強=買、高+弱=賣),其餘皆觀望。"""
    _navs = ("high", "mid", "low")
    _fxs = ("strong_twd", "neutral", "weak_twd")
    _directional = [(n, f) for n in _navs for f in _fxs
                    if nav_fx_signal(n, f)["tier"] in ("buy", "sell")]
    assert set(_directional) == {("low", "strong_twd"), ("high", "weak_twd")}


# ── L3 compute_nav_fx_column(欄名契約 + 各幣別)──────────
def test_compute_nav_fx_column_cases():
    from ui.helpers.fund_grp_health.unified import compute_nav_fx_column
    _m = {"USD": {"regime": "strong_twd", "robust": True}}
    assert compute_nav_fx_column({"ccy": "TWD"}, _m)["匯率位階"] == "➖ 台幣計價"
    _r = compute_nav_fx_column({"ccy": "USD", "σ rank": "-2.00σ"}, _m)
    assert _r["匯率位階"] == "台幣強" and "進場" in _r["淨值×匯率"]
    assert compute_nav_fx_column({"ccy": "EUR", "σ rank": "-2.00σ"}, _m)["匯率位階"] == "⬜ 無法判定"
    # 缺基期 → NAV 軸 ⬜,但匯率位階仍顯示(獨立軸)
    _r2 = compute_nav_fx_column({"ccy": "USD", "σ rank": None}, _m)
    assert _r2["匯率位階"] == "台幣強" and _r2["淨值×匯率"] == "⬜ 無法判定"
    # robust False → 星號;中文「美元」→ USD
    assert compute_nav_fx_column({"ccy": "USD", "σ rank": "-2σ"},
                                 {"USD": {"regime": "neutral", "robust": False}})["匯率位階"] == "中性*"
    assert compute_nav_fx_column({"ccy": "美元", "σ rank": "-2σ"}, _m)["匯率位階"] == "台幣強"


# ── fetch-once module cache ─────────────────────────────
# ⚠️ 2026-08-14 Layer 3-C:快取由 `ui/helpers/fund_grp_health/fx_regime.py`(L3)
# 下沉到 `services/fx_regime_service.py`(L2)。原因見該模組 docstring ——
# 健康度第 5 維會改變分數,而 `services/fund_batch.py`(L2)構不到 L3 helper。
# 內部快取字典也一併改名(`_FX_REGIME_CACHE` → `_CACHE`),並提供 `clear_cache()`,
# 測試不必再戳私有變數。
def test_fetch_once_dedupes_usdtwd(monkeypatch):
    import services.fund_service as _fs
    import services.fx_regime_service as _fr
    import services.hot_money_service as _hms
    _fr.clear_cache()
    _calls = {"n": 0}
    _df = pd.DataFrame({"date": _D[:250], "usdtwd": _fx().to_numpy()})

    def _fake(days):
        _calls["n"] += 1
        return _df, ""
    monkeypatch.setattr(_hms, "fetch_usdtwd_frame", _fake)
    monkeypatch.setattr(_fs, "get_latest_fx", lambda pair: 31.0)
    for _ in range(5):
        _fr.fx_regime_by_ccy()
    assert _calls["n"] == 1, f"fetch-once 失效:抓了 {_calls['n']} 次"
    assert _fr.fx_regime_by_ccy().get("USD", {}).get("regime") is not None
    _fr.clear_cache()


def test_fetch_empty_not_cached(monkeypatch):
    import services.fx_regime_service as _fr
    import services.hot_money_service as _hms
    _fr.clear_cache()
    monkeypatch.setattr(_hms, "fetch_usdtwd_frame", lambda days: (pd.DataFrame(), "err"))
    assert _fr.fx_regime_by_ccy() == {}       # 不 cache → 允許重試
    assert _fr.fx_regime_by_ccy() == {}       # 再叫一次仍是空(沒有把失敗結果凍住)
    _fr.clear_cache()


# ⚠️ 2026-08-28:`test_l3_shim_shares_the_l2_cache` 整個刪除(**測試對象消失,
# 不是為了讓 CI 綠**)。它斷言的是 `ui/helpers/fund_grp_health/fx_regime.py`
# 這個 re-export shim 與 L2 指到同一個 function object;該 shim 本輪已整檔刪除
# (production 0 caller),沒有「薄轉呼」這個東西可以驗了。
# 它原本要防的失效模式(有人在 L3 自己再存一份快取 → monkeypatch L2 失效 →
# 安靜打真網路)**仍然被守著**:見 `tests/test_flow_layer3c.py::
# test_fx_cache_lives_in_l2_so_every_caller_can_reach_it` 的 AST 掃描,
# 它直接檢查 production 檔有沒有從 `fund_grp_health.fx_regime` import。
