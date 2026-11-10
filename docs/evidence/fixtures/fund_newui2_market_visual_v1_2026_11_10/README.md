# 🌍 市場與趨勢 V1 視覺證據（Current 側，合成資料）

> 性質：V1 證據歸檔的圖檔區；非設計 SSOT，不新增 token 或視覺規格。對應文件：`docs/evidence/fund_newui2_market_visual_v1_evidence_2026_11_10.md`。

## 這些圖是什麼、不是什麼

- FACT：資料全是 `tests/ui_v3/market_stubs.py` 的人造數值（合成資料），**不是市場資料**；沒有連 FRED、Yahoo 或任何外部來源。
- FACT：由本機 headless Chromium 對本機 Streamlit Preview 產生。**不是** Streamlit Cloud、WebView 或真機證據。
- 本資料夾只有 Current 側；Reference（股票 HTML）側 NOT VERIFIED，原因見證據文件。

## 檔名規則

`w<寬度>_<情境>_<first|full>.png`

- 寬度：390（視窗 390x844）、768（768x1024）、1280（1280x800）。
- 情境：`normal`＝人造資料齊全（ok）；`missing`＝人造資料缺台股（`market_stubs.view(tw="missing")`）。
- `first`＝首屏（視窗大小）；`full`＝把視窗拉到整頁高度後截圖（Streamlit 內部捲動，不能用 Playwright `fullPage`）。
- 縮放：`deviceScaleFactor` 1（圖檔像素＝CSS px）。選 1 是為了控制檔案大小；細字在圖上較不銳利，數字以 `measure.json` 為準。

## 附檔

- `measure.json`：每個寬度×情境的 DOM 量測（`getBoundingClientRect`／`getComputedStyle`），含 `fullPageH`、`fullPageOverflowX`。
- `harness_launch.py`、`harness_shot.js`：產生用腳本，本批在 scratchpad 執行後原樣入庫（僅 `harness_launch.py` 的 worktree 路徑改為佔位 `<WORKTREE_ROOT>`）。`harness_shot.js` 內寫死 Playwright 路徑 `/opt/node-tools/node_modules/playwright`、連線埠 8613，重現時須自行改為本機的 Playwright 路徑。

## 重現（INFERENCE：路徑依本機而異，未在別台機器驗證）

1. 以 `origin/main`（`d49f1937`）建 worktree，安裝 Streamlit 1.59.2 與 repo 依賴到一個獨立 site 目錄。
2. 在 worktree 根目錄執行：
   `PYTHONPATH=<site> python3 -m streamlit run harness_launch.py --server.port 8613 --server.headless true --global.developmentMode false --server.fileWatcherType none`
   （`harness_launch.py` 內 `<WORKTREE_ROOT>` 換成 worktree 絕對路徑）
3. 修改 `harness_shot.js` 的 Playwright 路徑後：`CHROME=<chromium 路徑> node harness_shot.js <輸出資料夾> 1`。

## harness 版本

Streamlit 1.59.2；Chromium headless（`--no-sandbox`）；Playwright（node）；Current 程式碼＝`origin/main` `d49f1937` 的 `ui_v3`。
