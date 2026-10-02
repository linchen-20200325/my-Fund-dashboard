# -*- coding: utf-8 -*-
"""ui_v2 資料轉換層（L2）：把舊樹 L1 的回傳轉成 `44` 第四節的表列。

依據 docs/v2/49_data_integration_plan.md §3.3 方案 A（客戶 2026-09-26 裁示 Q11 同意新增檔）。

本套件只做一件事：呼叫 L1、把結果轉形成 `44` 第四節表格形狀的列，附 `fetched_at`
與失敗原文。**不做任何判定、不算任何指標、不另疊快取**（快取只在 L1，49 §4.4）。

- `contract`：`44` 第四節欄位契約的鏡像（真相源是 `44`，由測試逐欄重抽比對）。
- `market_indicator`：市場總覽（mkt）的 `market_indicator` 表。
- `settings_store`：設定與取數紀錄試算表的 L2 入口（遮蔽接到 L1、取數後寫 `market_indicator`／`fetch_log`；
  docs/v2/50_settings_sheet_design.md）。本檔只呼叫 L1 `repositories/settings_sheet_repository.py`，不碰 gspread。
- `alo_holdings`：資產配置頁讀表（`POLICY_SHEET_ID` 那一本的保單分頁＋`_持倉補充`＋`_保單資料`
  → `44` 4.1 `holding`、4.4 `policy`；`49` §6.3 N-4）。只呼叫 L1 `repositories/policy_supplement_repository.py`，
  本輪只讀、不接 UI。
- `nav_dividend`：持倉體檢頁要讀的 `44` 4.2 `nav`、4.3 `dividend`（L1 `fetch_nav_with_error`／
  `fetch_div_with_error` → 表列；Q12＝A 即時抓、快取只在 L1）。本輪只讀、不接 UI。

⚠️ 本套件不 import `ui_v2`（L2 不得上行 import，`CLAUDE.md` §8.2）；
   ui_v2 只經由 `ui_v2/<頁>/source.py` 碰到本套件。
"""
