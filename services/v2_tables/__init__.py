# -*- coding: utf-8 -*-
"""ui_v2 資料轉換層（L2）：把舊樹 L1 的回傳轉成 `44` 第四節的表列。

依據 docs/v2/49_data_integration_plan.md §3.3 方案 A（客戶 2026-09-26 裁示 Q11 同意新增檔）。

本套件只做一件事：呼叫 L1、把結果轉形成 `44` 第四節表格形狀的列，附 `fetched_at`
與失敗原文。**不做任何判定、不算任何指標、~~不另疊快取~~**（快取只在 L1，49 §4.4）。
→ 2026-10-14 更正（有意識的更正，不是漏刪 · 決策者 AI 總管；exp C2 稽核 V／W 必修 10）：「不另疊快取」已有
**兩處有意識的偏離** —— `exp_universe`（選股池代碼，2026-10-13）與 `exp_nav`（淨值逐檔記憶，2026-10-14）；
內容、理由與撤銷條件見 49 §3.3 第 3 步資料流圖下方註記與第 8 節 (t)。舊句的用意（快取集中在 L1）仍然成立。

- `contract`：`44` 第四節欄位契約的鏡像（真相源是 `44`，由測試逐欄重抽比對）。
- `market_indicator`：市場總覽（mkt）的 `market_indicator` 表。
- `settings_store`：設定與取數紀錄試算表的 L2 入口（遮蔽接到 L1、取數後寫 `market_indicator`／`fetch_log`；
  docs/v2/50_settings_sheet_design.md）。本檔只呼叫 L1 `repositories/settings_sheet_repository.py`，不碰 gspread。
- `alo_holdings`：資產配置頁讀表（`POLICY_SHEET_ID` 那一本的保單分頁＋`_持倉補充`＋`_保單資料`
  → `44` 4.1 `holding`、4.4 `policy`；`49` §6.3 N-4）。只呼叫 L1 `repositories/policy_supplement_repository.py`，
  本輪只讀、不接 UI。
- `nav_dividend`：持倉體檢頁要讀的 `44` 4.2 `nav`、4.3 `dividend`（L1 `fetch_nav_with_error`／
  `fetch_div_with_error` → 表列；Q12＝A 即時抓、快取只在 L1）。本輪只讀、不接 UI。
- `fund_keys`：試算表 `fund_code` → MoneyDJ `full_key`／`portal` 的決定性對照（hld 接真資料 S1；
  strip → upper → L1 `parse_moneydj_input` → `load_fund_code_mapping`，對不上回錯誤、不截斷不猜）。不接 UI。
- `masking`：失敗原文的秘密值遮蔽（寫出點用）。
- `exp_universe`：標的探索（exp）正式模式的候選母體 —— 選股池只取代碼（L2 快取成功、失敗沿用 L1 冷卻鑰匙）。
- `exp_profile`：exp 的 `fund_profile` 逐欄出處（C1 三支自報 L1 → 每格 ok／⬜／⛔ 與來源、原字、取得時間、原因；
  2026-10-14 C2，尚未接 UI）。
- `exp_nav`：exp 的淨值與配息 —— `nav_dividend.build_nav_dividend_tables` 外的逐檔記憶（2026-10-14 C2，
  49 §4.4 的有意偏離，尚未接 UI）。
- （本清單於 2026-10-14 補上 `masking`、`exp_universe`、`exp_profile`、`exp_nav`；`alo_holdings` 等條目的
  「本輪只讀、不接 UI」是各自寫下當時的狀態，本次未逐條重驗。）

⚠️ 本套件不 import `ui_v2`（L2 不得上行 import，`CLAUDE.md` §8.2）；
   ui_v2 只經由 `ui_v2/<頁>/source.py` 碰到本套件。
"""
