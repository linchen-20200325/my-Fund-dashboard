"""ui/components/macro_compass_top.py — 🧭 總經指南針(已於 2026-08-05 移除)。

本檔**刻意只剩這段說明,沒有任何可執行程式碼**。留檔而不留實作的理由:
本機工具鏈此輪無法實體刪檔(見交付報告的跨所有權待辦),但依 `PROCESS.md §4`
「0 consumer → 接線或刪除,**不得留著假裝有揭露**」,實作必須先消失 ——
任何 `from ui.components.macro_compass_top import render_macro_compass`
會直接 ImportError 當場炸(§1 Fail Loud),不會靜默沿用一份沒人呼叫的舊畫面。

移除原因(2026-08-05 稽核 🔴 必修 6;user 原則 2「重複的移除」+ 原則 3
「一直抓不到又不影響判斷的移除」):

1. **三張卡全部重複**。逐張查證後,同一個問題在 🎯 短線雷達都有現成的燈,
   而且雷達是主載入按鈕就一併抓好的(零額外點擊):
     · VIX 恐慌指數      → `services/risk_radar.py::_signal_vix_level`
                           (且總表 ② 依據表的 🎯 短線列也是同一顆)
     · 美 10Y 殖利率      → `services/risk_radar.py::_signal_yield_10y_shock`
                           (FRED DGS10,另含 vs Yahoo ^TNX 的雙源對帳 chip)
     · S&P 500 vs 60MA   → `services/risk_radar.py::_signal_spx_trend_break`
                           同一支 ^GSPC、同一個「站上/跌破均線」語意,
                           而且列的是 50DMA / 200DMA 兩條**有燈號分級**的線。
   原稽核假設「只有 S&P 500 vs 60MA 全頁獨有,應併進雷達」——查證後推翻:
   併進去會讓同一個區塊出現三個 SPX 均線讀數,反而製造新的重複。

2. **本身就是原則 3 點名的那種區塊**:它有自己的「📡 抓取最新」按鈕
   (`_compass_fetch_btn`),且 `_do_fetch` 先 `cache_clear()` 再抓 —— 使用者
   剛按完「載入總經資料」還得再按一次,沒按時整塊只是一句「請按右上按鈕載入」。
   三條獨立抓取路徑(② 依據表 / 指南針 / 雷達)還可能同時顯示三個不同的 VIX。

下游連帶(**不在本輪所有權內,已列交付報告待辦**):
  - `services/macro/compass.py::refresh_macro_compass` → production 0 consumer
  - `repositories/macro/alternate.py::fetch_macro_compass` → 隨之 0 consumer
    (它唯一的呼叫端就是上面那個 facade)

回退方式:git history 保有完整元件(`_trend_dir` / `_render_compass_card` /
`render_macro_compass`)與 `ui/tab1_macro.py` 的呼叫站。
"""
