"""ui/helpers/fund_grp_health/quality.py — 舊路徑別名(2026-10-13)。

客戶 2026-10-13 裁示(LINE 推播與舊 UI 解耦):本檔內容**原封搬到 L2 `services/fund_grp_health/quality.py`**
(`build_merged_extra_columns` 的依賴,本來就零 streamlit),每週換檔推播 `scripts/weekly_switch_notify.py`(經 `build_merged_extra_columns`) 改直接 import 那裡,不再載入 UI 層。

舊 UI 呼叫點不必改:本模組在載入時把自己在 `sys.modules` 的位置**換成 L2 那個模組物件**,
所以 `import ui.helpers.fund_grp_health.quality` 與 `import services.fund_grp_health.quality` 拿到的是**同一個模組**
(不是複製一份、也不是逐名轉出 —— 逐名轉出會讓 monkeypatch 只改到其中一份,
SSOT 就在測試替身這一層悄悄裂成兩份)。
⛔ 不要在這裡新增任何程式碼;要改邏輯請改 `services/fund_grp_health/quality.py`。
"""
import sys as _sys

from services.fund_grp_health import quality as _impl

_sys.modules[__name__] = _impl
