# BL-0536 Navigation Shell＋H5 首屏量測（2026-11-03）

⚠️ **這些截圖與數字用的是測試端注入的人造資料，不是真實行情。** 每張圖頂端有黃字黑底標示 `INJECTED TEST DATA — NOT REAL MARKET DATA`。本環境對 Yahoo／FRED 的 HTTPS 受限，沒有對真實來源取數驗證。

| 項 | 內容 |
|---|---|
| 來源 | `launch_injected_data.py`（把 `ui_v3.adapters.market_page.load` 換成 `tests/ui_v3/market_stubs.py` 替身後啟動 `ui_v3/app_preview.py`，`?scenario=` 切情境）＋ `measure.js`（Playwright chromium、`deviceScaleFactor` 2，量 DOM 座標並截圖）。兩支腳本只用來重現，不在任何測試或 CI 路徑 |
| 量測日／基底 | 2026-11-03；工作樹基底 main `3b40cbfb`＋Navigation Shell 批未提交變更（提交後以該批 commit 為準） |
| 原始數字 | `measurements.jsonl`（每行一個情境：`scrollWidth`／`clientWidth`、底部導覽與側欄是否顯示及座標、導覽項高度、Status Bar 文字、首屏可視高度、首屏 chip 與核心數字個數、Primary 圖座標；390 常態另含捲到底後頁尾與底部導覽的座標） |
| 截圖 | `m_normal`、`m_partial`、`m_nokey`、`m_both_missing`（390×844）；`t768_normal`（768，仍是手機版面）、`t769_normal`（769，桌機版面）；`d_normal`、`d_failed`（1280×800） |
| 結論 | 見 `docs/v2/80` 第 17.5 節：390 與 1280（另 768、769）皆無橫向捲動；四項首屏資訊與 Primary 圖起點可見；底部導覽不遮內容；首屏 3 chip＋2 數字＝5（不含 Status Bar，該讀法待客戶確認） |
| 限制 | 只量 Chromium；沒有實機 iOS／Android；深色模式底部列未驗；`partial` 情境是 S&P 歷史不足，Status Bar 資料狀態維持原樣（資料狀態只算主要序列的取得與否） |
| 重現 | 在 repo 根目錄 `streamlit run docs/evidence/bl0536_shell_h5_2026-11-03/launch_injected_data.py --server.port 8599 --server.headless true`，再 `node measure.js <scenario> <width> <height> <out.png> [scroll]`（Playwright 路徑見腳本第一行） |
