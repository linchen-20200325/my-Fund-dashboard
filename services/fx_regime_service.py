"""services/fx_regime_service.py — 匯率位階 fetch-once 快取（L2，2026-08-14 Layer 3-C）。

為什麼要下沉到 L2
================
原本這份 fetch-once 快取住在 `ui/helpers/fund_grp_health/fx_regime.py`（L3），
只服務大表的「匯率位階」欄。健康度加了第 5 維（匯率風險）之後出現一個問題：

**第 5 維會改變分數本身**（維度數 4→5，平均值跟著變）。
如果只有部分 caller 拿得到匯率資料，同一檔基金在「組合健診」是 5/5 的 B、
在「個基深掘」卻是 4/5 的 C —— 那正是這一輪一直在修的「跨畫面矛盾」。

而 `services/fund_batch.py`（L2）也是 caller，它**構不到 L3 的 helper**
（§8.2 禁 L2→L3）。所以快取必須住在 L2，L3 端改為薄轉呼。

§8.2 合規：本模組只呼叫其他 **L2 service facade**
（`hot_money_service` / `fund_service` / `nav_fx_switch`），
不 import requests / httpx / bs4，也不直呼 L1。

§2.4 新鮮度：匯率位階是「**當前**」讀數（spot vs 近一年均值），不可永久凍結。
TTL 對齊 `fetch_usdtwd_series` 自身的 TTL_10MIN —— 一輪 400 檔批次內幾乎只抓一次，
但久駐 process 不會把「台幣強/弱」凍結好幾天。

§1 fail-loud：抓失敗**不寫入快取**（下次重試），回 {} 讓消費端誠實留白。
"""
from __future__ import annotations

# {normalized_ccy: fx_regime dict}；只快取成功結果
_CACHE: dict = {}
_CACHE_TS: dict = {"ts": 0.0}

# Phase 1 只支援 USD。擴充只需加幣別 + 對應 {ccy}TWD 序列來源。
# ⚠️ 未支援的幣別（EUR / JPY / ZAR …）會**查不到** → 健康度第 5 維標 missing，
#    「評分覆蓋」欄會誠實顯示 ⚠️ 4/5（缺 匯率）。這是刻意的：
#    寧可講「我們還沒有這個幣別的匯率歷史」，也不要拿 USD 的波動去代打（§1）。
SUPPORTED_FX: tuple = ("USD",)


def fx_regime_by_ccy() -> dict:
    """→ `{幣別: fx_regime dict}`。抓一次算一次（module cache + TTL）；缺料 → {}。

    回傳的 dict 內含 `std` / `mean`，健康度第 5 維用
    `services.health.report.fx_cv_pct_from_regime()` 轉成變異係數。
    """
    import sys
    import time as _time

    from shared.ttls import TTL_10MIN

    _now = _time.monotonic()
    if _CACHE and (_now - _CACHE_TS["ts"]) < TTL_10MIN:
        return _CACHE
    _CACHE.clear()   # 到期 → 重算（過期不靜默沿用，§2.4）

    from services.fund_service import get_latest_fx
    from services.hot_money_service import fetch_usdtwd_frame
    from services.nav_fx_switch import fx_regime
    from shared.signal_thresholds import FX_REGIME_WINDOW_DAYS

    try:
        _df, _err = fetch_usdtwd_frame(FX_REGIME_WINDOW_DAYS)
        if _err or _df is None or getattr(_df, "empty", True):
            return {}                      # 不 cache → 允許重試
        _s = _df.set_index("date")["usdtwd"]
        _r = fx_regime(_s, spot=get_latest_fx("USDTWD=X"))
        if _r.get("regime") is not None:
            _CACHE["USD"] = _r
            _CACHE_TS["ts"] = _now
    except Exception as _e:  # noqa: BLE001 — 抓失敗不拖垮整表
        print(f"[fx_regime_service] USD 失敗: {type(_e).__name__}: {_e}",
              file=sys.stderr)
    return _CACHE


def clear_cache() -> None:
    """測試 / 「清快取」按鈕用。"""
    _CACHE.clear()
    _CACHE_TS["ts"] = 0.0
