"""services/macro/compass.py — Macro Compass 資料 L2 facade(v19.376 B2b 分層歸位)。

§8.2 硬規則 4:L3 UI 不得直接 import L1 fetcher(cache 須集中於 L2)。
`ui/components/macro_compass_top.py` 原本在「📡 抓取最新」按鈕的 `_do_fetch` 內直接
`from repositories.macro_repository import fetch_macro_compass`,並手動 `.cache_clear()`
+ 呼叫 —— UI 直接碰 L1 fetcher 及其 cache 內部,屬未登錄的 L3→L1 直呼。

本 facade 把「強制重抓」封裝於 L2(cache 集中原則):UI 只需呼叫 `refresh_macro_compass()`,
不再需要知道 L1 cache 的存在與清法。lazy import 避免 import-time L1 連鎖載入。
"""
from __future__ import annotations


def refresh_macro_compass() -> dict:
    """強制重抓 macro compass:清 L1 cache 後重新 fetch(L2 facade → L1 macro_repository)。

    「📡 抓取最新」按鈕語意 = 按鈕當下 = 盤面當下真實狀態,故先 `cache_clear()` 再 fetch,
    確保拿到即時盤面而非過時快取值。L1 fetch 失敗由 caller 端 try/except 處理(維持原
    UI fail-soft 行為,§1 不偽造)。
    """
    from repositories.macro_repository import fetch_macro_compass
    fetch_macro_compass.cache_clear()
    return fetch_macro_compass()
