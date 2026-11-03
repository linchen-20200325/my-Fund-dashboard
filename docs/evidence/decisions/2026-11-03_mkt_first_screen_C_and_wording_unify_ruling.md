# 客戶 2026-11-03 裁示：🌍 首屏採 C、用字統一（逐字）

- **來源**：客戶 2026-11-03 裁示，經總管於派工單內逐字轉交；執行組照抄，未見客戶對話本身（repo 內無另一份原文可做逐位元組比對）。
- **性質**：正式裁示（presentation hierarchy＋wording；不改 formula、data semantics、資料來源、門檻、狀態判定或投資語意；不修訂 frozen 44）。
- **遮蔽**：無。本文沒有作者或老師姓名，也沒有 secret。
- **決策登記**：`docs/DECISIONS.md` `DEC-2026-11-03-09`（解決 `DEC-2026-11-03-07` 第 (2) 項未落地的 Decision Gate）
- **存檔日期**：2026-11-03
- **依據規則**：`PROJECT_RULES.md` 12.1 新裁示同批 GitHub 落盤、12.2 GitHub Discussion Persistence Gate。
- **落地位置**：`shared/ui_semantics/rules.py`（`NOT_CONFIGURED_RATES_SOURCE_TEXT`、`APPROVED_WORDING["series_us10y"／"series_us2y"]`）；`ui_v3/pages/mkt.py`；`ui_v3/viewmodels/preview_wording.py`；`tests/ui_v3/test_ui_v3_first_screen_c_and_wording_unify.py`；`docs/v2/81_new_ui2_wireframe_01_market.md`（第 10 節）；`docs/BACKLOG.md` BL-0536；`docs/HANDOFF.md`。
- **歷史檔不改字**：先前逐字存檔（例：`2026-11-03_vix_secondary_yield_ruling.md`、`2026-11-03_mkt_wireframe_ruling.md`）內的舊寫法保留原樣，是當時裁示的原文；現行用字以本檔與 `DEC-2026-11-03-09` 為準。

```text
1. 首屏採 C：『市場狀態』與『是否需注意』拆成兩個獨立欄位／兩枚獨立 chip；『基準日』不再佔 chip 預算，改放在圖表附近的 SPEC／純文字揭露行；原有字樣與資料語意不變；首屏核心數字＋chip 總數仍維持 frozen 44 的 ≤5；不修訂 frozen 44，也不把其他頁的首屏上限放寬到 6。這只是 presentation hierarchy 調整，不是 formula／data semantics 變更。
2. 用字統一：正式使用『⛔ 利率資料來源尚未設定』『美10Y』『美2Y』；不要再使用『⛔ 尚未設定：利率資料來源』『美 10Y』『美 2Y』。請同步更新：current wording SSOT、對應 tests／guards、docs/DECISIONS.md、docs/BACKLOG.md、docs/HANDOFF.md、docs/v2/81、evidence。#1132 scope 已涵蓋，直接併入。若碰到 frozen 44 實質語意、formula 或 data semantics，另送 Gate 並 STOP。
```
