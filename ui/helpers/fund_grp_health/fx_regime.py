"""ui/helpers/fund_grp_health/fx_regime.py — 匯率位階抓取(fetch-once)v19.426。

抓一次 USDTWD 歷史(module 級 success-only 快取,400 檔批次不重抓)→ 算一次匯率位階,
供 `compute_nav_fx_column` 逐檔查(keyed by 幣別)。走 L2 facade(hot_money_service /
fund_service / nav_fx_switch),不直呼 L1(§8.2)。Phase 1 只支援 USD;缺料/失敗 → {} 允許重試。
"""
from __future__ import annotations

# {normalized_ccy: fx_regime dict};只快取成功結果(失敗不入 → 下次重試,§1)
_FX_REGIME_CACHE: dict = {}
_FX_CACHE_TS: dict = {"ts": 0.0}     # 上次成功計算時間(monotonic);TTL 到期則重算
_SUPPORTED_FX = ("USD",)             # Phase 1;擴充只需加幣別 + 對應 {ccy}TWD 序列來源


def fx_regime_by_ccy() -> dict:
    """→ {normalized_ccy: fx_regime dict}。抓一次 USDTWD(module cache)算一次位階;缺料 → {}。

    v19.426 稽核 Finding1:匯率位階是「**當前**」讀數(spot vs 近1年均值),不可永久凍結(§2.4)。
    加 TTL(TTL_10MIN,對齊 fetch_usdtwd_series 自身 TTL)—— 一輪批次內仍幾乎只抓一次(批次 <30 分,
    最多重算 2-3 次),但久駐 process 不會把「台幣強/弱」凍結數天。
    """
    import sys
    import time as _time

    from shared.ttls import TTL_10MIN

    _now = _time.monotonic()
    if _FX_REGIME_CACHE and (_now - _FX_CACHE_TS["ts"]) < TTL_10MIN:
        return _FX_REGIME_CACHE
    _FX_REGIME_CACHE.clear()                              # 到期 → 重算(過期不靜默沿用,§2.4)

    from services.fund_service import get_latest_fx
    from services.hot_money_service import fetch_usdtwd_frame
    from services.nav_fx_switch import fx_regime
    from shared.signal_thresholds import FX_REGIME_WINDOW_DAYS

    try:
        _df, _err = fetch_usdtwd_frame(FX_REGIME_WINDOW_DAYS)
        if _err or _df is None or getattr(_df, "empty", True):
            return {}                                        # 不 cache → 允許重試
        _s = _df.set_index("date")["usdtwd"]
        _r = fx_regime(_s, spot=get_latest_fx("USDTWD=X"))
        if _r.get("regime") is not None:
            _FX_REGIME_CACHE["USD"] = _r
            _FX_CACHE_TS["ts"] = _now
    except Exception as _e:  # noqa: BLE001 — 抓失敗不拖垮整表 extra 欄
        print(f"[fx_regime] USD 失敗: {type(_e).__name__}: {_e}", file=sys.stderr)
    return _FX_REGIME_CACHE
