# A7 🌍 市場比較圖雙系列色票方案 A 實作證據｜2026-11-21

> Claude A 線單組產出，**未經第二組獨立複驗**（待 Work 對新 exact head 獨立 QA）。依據：客戶正式裁示 #1296 comment 7057582576（方案 A：第一系列 `#0a3f86` 實線、第二系列 `#d06a00` 虛線，僅用於比較圖雙系列識別）。
> 量測：本機 Chromium 153＋`tests/ui_v3/market_stubs.py` 合成 fixture（人造數值，不是市場資料）。**NOT VERIFIED：Cloud／真機／系統字級、色覺者研究、色覺模擬數值、CI（本報告撰寫當下尚未跑）。**

## 1. 改了什麼（production 3 檔、測試 3 檔）
| 檔 | 變更 |
|---|---|
| `ui_v3/design/tokens.py` | 新增 `chart.series.1`＝`#0a3f86`、`chart.series.2`＝`#d06a00`（source 註明客戶裁示）；其他 `chart.*`、狀態色、全站 palette **未動** |
| `ui_v3/pages/chart_svg.py` | `Line` 增選填 `color`（預設 `None`＝currentColor；只接受 `#rrggbb`，否則 `ValueError`）；線與末點圓用該色，**末點文字標籤與座標軸仍 currentColor**；有上色線時 SVG 內附 `@media (forced-colors:active)` 回退（線／圓回系統文字色） |
| `ui_v3/pages/mkt.py` | `primary_chart_html` 對「歸一化比較」圖的前兩條線帶 `tokens.value("chart.series.N")`；單序列檢視（VIX／美債）維持 currentColor。**⚠️ 這是派工單原文以外的 3 行**（派工只點名 tokens.py／chart_svg.py）：色彩要依「第幾條系列」而非「是否虛線」對應，chart_svg 無法自行知道哪張圖是比較圖；已就地標示，**請總管／Work 檢查是否可接受**，不接受則改以 chart_svg 依 `dashed` 旗標推斷（缺點：單序列實線檢視會誤上色） |
| 測試 | `test_ui_v3_market_series_palette_browser.py`（新，slow）、`test_ui_v3_market_chart_svg.py`（+5）、`test_ui_v3_design_tokens.py`（+2 行：逐字鎖兩個值；`UNVALUED` 檢查排除這兩個） |

## 2. 量測結果（FACT；`before_strokes.json`／`after_strokes.json` 與截圖）
- 色彩：390／1280 比較圖 computed stroke 修改前兩線同為 `rgb(23,32,51)`；修改後 **`rgb(10,63,134)` 實線（`none`）／`rgb(208,106,0)` 虛線（`6px, 4px`）**，末點圓同色，**末點文字標籤與文字色相同（不上色）**——橙對白底僅 3.66:1，不足文字 4.5:1，故標籤不上色。
- 對比（`recompute.py` 與測試共同）：深藍／橙對卡片底 `#fff` 10.15／3.66、對頁面底 `#f5f7fb` 9.47／3.41，皆 ≥3:1（非文字）；兩線亮度比 2.78 ≥2.5。
- 灰階：`html{filter:grayscale(1)}` 截圖 `after_gray_*`；兩線仍以實／虛線＋末點標籤分辨（亮度差另有 2.78）。
- forced-colors：**實測發現**——系統會收掉 `currentColor`，但不會改寫明確色碼，深藍在黑底高對比主題上會看不見。已加回退，修改後兩線回系統文字色（`rgb(0,0,0)`，emulation）、仍靠實／虛線分辨（`after_forced_*`）。
- 降級情境：`tw_missing` 只剩橙虛線、`us_failed` 只剩深藍實線（色彩跟系列走）；`both_missing` 不畫圖；VIX 單序列維持 currentColor。缺值不補、不畫零（既有 `market_page_browser` 守衛全綠）。
- 其他不變：既有 `test_ui_v3_market_page_browser.py`、top_nav、token 等 `tests/ui_v3` 全套（見 PR 本文）。

## 3. 負控（皆在記憶體內現編，不改 production）
改任一系列色碼（差 1 色階）、拿掉虛線、把標籤文字塗成系列色、移除 SVG 內 forced-colors 回退 → 判定函式各自必須報；`Line.color` 傳入非法值（`red`、`#fff`、含注入字串）→ `ValueError`。

## 4. 尚未做／限制
色覺模擬（protan／deutan／tritan）數值 NOT VERIFIED；橙色「可能被讀成警示」屬認知風險，無實測，客戶裁示已明載「橙色不得自動產生警告意思」——本實作只在比較圖兩線上使用、未碰任何狀態色／文案；暗色偏好下頁面仍為淺色（既有現況，不在範圍）。
