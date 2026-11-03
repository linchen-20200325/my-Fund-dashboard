# -*- coding: utf-8 -*-
"""ui_v2 與 New UI2 共用的領域計算層（L2；`docs/v2/80_new_ui2_architecture_proposal.md` 第 3.2 節 PORT 列、
第 3.3 節 (a) 方案 a2；客戶 `DEC-2026-11-02-05` NG-2 A：可把共用計算搬到 shared／domain 層，ui_v2 行為不變、
搬遷批需獨立稽核）。

本套件只放**純計算**：
- 不 import streamlit、不 import `ui`／`ui_v2`／New UI2 套件、不做任何 I/O（`CLAUDE.md` §8.2 L2 規則）；
- 不帶 ui_v2 的呈現形狀（block dict、`_state` 中文狀態字面、畫面字樣）—— 回傳值只有數字、`None`、
  中性代碼（英文小寫）或呼叫端傳進來的原物件；中文原因字與畫面字一律留在 ui_v2 的薄包裝裡對照；
- 自己丟的例外只帶中性英文訊息；ui_v2 包裝在原位置把它換回原本的例外型別與原字訊息。

模組：
- `nav_metrics`：區間報酬率、最大回撤、期間波動（原 `ui_v2/hld/logic.py`）。
- `holdings`：同鍵持倉合併（hld 與 alo 兩種規則各一支，**刻意不合併**）、最近一筆淨值、匯率對齊、
  類別歸屬、容許帶判定、目標合計（原 `ui_v2/hld/logic.py`、`ui_v2/alo/logic.py`）。
- `deviation`：門檻比較方向、差額、未列入原因的取數失敗優先（原 `ui_v2/hld/logic.py::deviation_rows` 的純計算部分）。
- `rule_filter`：缺值判定、三態比較、逐條累計篩選（原 `ui_v2/exp/logic.py`）。
- `periods`：期間切片（原 `ui_v2/mkt/chart.py`）。
- `freshness`：延遲日數（原 `ui_v2/mkt/logic.py`）。
- `normalization`：🌍 TAIEX vs S&P 500 歸一化比較（BL-0536-H1，2026-11-03 新寫；依 `DEC-2026-11-03-01` Q2-a／b／c A；
  不是 PORT，ui_v2 沒有對應實作；ui_v2 不 import 它）。

⚠️ `NAV_NOT_READY_DAYS`（淨值資料未備門檻 10 天）**本批未搬**，仍住 `ui_v2/thresholds.py`：
`tests/ui_v2/test_alo_live_logic.py::test_10天門檻_兩頁引用同一個共用常數_值為10` 鎖定「全 ui_v2 只有
`ui_v2/thresholds.py` 以字面值 10 給它值」（C 類 ownership lock）；改成 re-export 會讓該測試轉紅，放寬需總管／客戶裁示；本批不改。
"""
