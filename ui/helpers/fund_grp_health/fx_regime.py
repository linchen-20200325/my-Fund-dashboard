"""ui/helpers/fund_grp_health/fx_regime.py — **已退役**，改用 `services.fx_regime_service`。

v19.426 原本在這裡實作匯率位階的 fetch-once module cache。
2026-08-14 Layer 3-C 下沉到 L2（`services/fx_regime_service.py`），理由：

健康度加了第 5 維（匯率風險）之後，**匯率資料會改變分數本身**。
而 `services/fund_batch.py`（L2）也是算等第的 caller，它**構不到 L3 的 helper**
（§8.2 禁 L2→L3）。若只有部分 caller 拿得到匯率資料，同一檔基金會在
「組合健診」是 5/5 的 B、在「批次分析」是 4/5 的 C —— 正是這一輪一直在修的
「跨畫面矛盾」。快取住在 L2，全站才可能拿到同一份。

**本檔只保留 re-export 供舊 import path 不炸**（production 已全數改指 L2）。
⚠️ 測試要 monkeypatch 時**請 patch `services.fx_regime_service`** ——
patch 這裡不會生效（production 不從這裡讀），會變成安靜地打真網路。
"""
from __future__ import annotations

from services.fx_regime_service import (  # noqa: F401  (向後相容 re-export)
    clear_cache,
    fx_regime_by_ccy,
)

__all__ = ["clear_cache", "fx_regime_by_ccy"]
