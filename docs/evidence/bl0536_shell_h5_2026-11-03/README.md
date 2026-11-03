# BL-0536 Navigation Shell＋H5 首屏量測（2026-11-03）

⚠️ **這些截圖與數字用的是測試端注入的人造資料，不是真實行情。** 每張圖頂端有黃字黑底標示 `INJECTED TEST DATA — NOT REAL MARKET DATA`。本環境對 Yahoo／FRED 的 HTTPS 受限，沒有對真實來源取數驗證。

| 項 | 內容 |
|---|---|
| 來源 | `launch_injected_data.py`（把 `ui_v3.adapters.market_page.load` 換成 `tests/ui_v3/market_stubs.py` 替身後啟動 `ui_v3/app_preview.py`，`?scenario=` 切情境；情境：normal、partial、missing、failed、both_missing、nokey、stale、all_missing、all_failed）＋ `measure.js`（Playwright chromium、`deviceScaleFactor` 2，量 DOM 座標並截圖；可選第 6 參數點選主圖檢視標籤，環境變數 `PORT` 指定埠）。兩支腳本只用來重現，不在任何測試或 CI 路徑 |
| 量測日／基底 | 初版 2026-11-03（#1134）。**本次重拍（Shell 定字與降級首屏收尾批，`DEC-2026-11-03-11`）**：2026-11-03；基底 main `875b1955`＋本批變更。`measurements_before_875b1955.jsonl` 是同一支 `measure.js` 對 `875b1955` 乾淨樹（臨時 git worktree，用完已移除）的重量，作為「前」 |
| 原始數字 | `measurements.jsonl`（後）與 `measurements_before_875b1955.jsonl`（前）：每行一個情境×視窗；欄位含 `scrollWidth`／`clientWidth`、底部導覽與側欄是否顯示及座標、Status Bar 文字、首屏可視高度、**`firstScreenSlots`＝獨立 chip＋核心數字格（格內的 chip 不重複計；含 Status Bar 與側欄內的 chip）**、`standaloneChips`、`evidenceSlots`、`chromeChips`、`seriesStatusSummaryVisible`、`visibleWarning`。`chipsInFirstScreen`／`evidenceNumbersInFirstScreen` 是 #1134 的舊量法（巢狀 chip 重複計），保留供對照 |
| 截圖 | 390×844：`m_<情境>.png`；1280×800：`d_<情境>.png`；768／769：`t768_normal`、`t769_normal`；`*_us10y`、`*_VIX` 為點選該檢視後的首屏。所有圖頂端有注入資料標示 |
| 結論 | 見 `docs/v2/81` 第 10.2 節（降級情境前後計數與方案比較）與 `docs/v2/80` 第 17.5 節：後：九個情境在 390 與 1280 的第一屏名額皆為 5（前：both_missing、all_missing、all_failed 為 7）；Status Bar 與側欄零 chip；無橫向捲動；底部導覽不遮頁尾；五頁導覽與「開發中」「尚未開放」字樣；更新資料按鈕停用且原因為正式字樣「預覽版尚未開放更新資料」 |
| 限制 | 只量 Chromium；沒有實機 iOS／Android、Safari；深色模式底部列未驗；Yahoo／FRED 未連線（人造資料）；Streamlit 升版後導覽相容性未驗（CSS 依賴內部 `data-testid`）；`partial` 情境是 S&P 歷史不足，Status Bar 資料狀態維持原樣（資料狀態只算主要序列的取得與否）。以上皆在 BL-0536 待驗證清單，**不得宣稱已通過** |
| 重現 | 在 repo 根目錄 `streamlit run docs/evidence/bl0536_shell_h5_2026-11-03/launch_injected_data.py --server.port 8599 --server.headless true`，再 `node measure.js <scenario> <width> <height> <out.png> [scroll] [viewLabel]`（Playwright 路徑見腳本第一行；`launch_injected_data.py` 的 `ROOT` 寫死為本機 checkout 路徑） |
