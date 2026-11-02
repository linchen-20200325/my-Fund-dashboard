# -*- coding: utf-8 -*-
"""ui_v2 通往 `services/v2_domain` 的**唯一**一個口子（2026-11-02 PORT，`docs/v2/80` 第 3.3 節 (a) 方案 a2）。

客戶 `DEC-2026-11-02-05` NG-2 A：ui_v2 maintenance-only；共用計算可以搬到 shared／domain 層，但 ui_v2 行為不變。
領域計算的本體搬到 `services/v2_domain/`；ui_v2 各頁 `logic.py`／`chart.py` 原位置保留同名公開符號
（re-export 或薄包裝），經本檔取用 L2 —— 各頁不直接 import `services`，所以 ui_v2 碰到 L2 的地方只有這一檔，
`tests/ui_v2/test_ui_v2_live_import_guard.py` 只替這一檔開逐檔白名單（只准 `services.v2_domain.*`）。

本檔只 re-export 模組物件，不寫任何邏輯；不 import streamlit、不 import 任何其他舊樹模組。
"""

from __future__ import annotations

from services.v2_domain import deviation, freshness, holdings, nav_metrics, periods, rule_filter

__all__ = ("deviation", "freshness", "holdings", "nav_metrics", "periods", "rule_filter")
