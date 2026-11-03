# BL-0536 🌍 市場與趨勢 Preview rendering 截圖（2026-11-03）

⚠️ **這些截圖用的是測試端注入的人造資料，不是真實行情。** 每張圖底部有黃字黑底標示 `INJECTED TEST DATA — NOT REAL MARKET DATA`。
本環境對 Yahoo／FRED 的 HTTPS 受限，沒有對真實來源取數驗證。

⚠️ **2026-11-03 過期註記（`DEC-2026-11-03-07`）**：本批截圖拍於客戶正式字樣裁示**之前**。畫面字樣已變（例：「頻率：日」多冒號、檢視標籤「美10Y」「美2Y」、主判讀不再有英文 aggregation rule、「⛔ 尚未設定：」後接「利率資料來源」而非環境變數名、依據卡標籤與 MKT-2 兩列、已核准字樣不再有虛線底線）；`m_nokey` 圖內仍是舊的環境變數名。**這些圖未重拍，僅作版面（390／1280 無橫向捲動）參考，不得當作現行字樣證據。**重拍用同目錄 `launch_injected_data.py`＋`shot.js`（本批環境未重拍）。

- 產生方式：`launch_injected_data.py`（把 `ui_v3.adapters.market_page.load` 換成 `tests/ui_v3/market_stubs.py` 的替身後啟動 `ui_v3/app_preview.py`，
  用 `?scenario=` 切情境）＋ `shot.js`（Playwright chromium，`deviceScaleFactor` 2）。兩支腳本只是重現用，不在任何測試或 CI 路徑。
- 手機 `m_*`：視窗 390 px 寬（輸出 780×4600，為了一張圖看完整頁而拉高視窗；不代表首屏高度，V7 量測屬 BL-0536-H5，尚未做）；桌機 `d_*`：1280 px 寬。
- 無橫向捲動：每次截圖前後 `scrollWidth == clientWidth`（390、1280）。

| 檔 | 情境 |
|---|---|
| `m_normal` | 兩條序列皆 ok（比較圖、基準日、資料日一行） |
| `m_missing` | 台股缺資料（`◇ 資料未備`；只畫 S&P，單序列說明） |
| `m_failed` | S&P 取數失敗（`⛔ S&P 500 取數失敗`，不冒充缺資料） |
| `m_both_missing` | 兩條都缺（空狀態，不畫空座標軸） |
| `m_stale` | S&P 最後觀測日較舊（各畫到自己最後一天；不判舊、無 ◷） |
| `m_partial` | S&P 歷史不足（此圖為預設 1Y、S&P 約 2 年歷史，仍涵蓋 1Y；切 3Y 才會退回單序列） |
| `m_nokey` | 缺 FRED 金鑰（`⛔ 尚未設定：FRED_API_KEY`） |
| `m_negative` | 取得時間早於觀測日（`⬜ 不適用：取得時間早於觀測日`） |
| `m_vix` | Primary 檢視切到 VIX（Secondary VIX 卡讓位） |
| `d_normal`、`d_partial` | 桌機 1280 |
