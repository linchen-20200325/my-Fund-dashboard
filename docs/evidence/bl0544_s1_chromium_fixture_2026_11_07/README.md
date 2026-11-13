# BL-0544 S1 手機頁首五格：Chromium 合成 fixture 量測（2026-11-07）

> **本目錄是「本機合成 fixture ＋ Chromium 153」量測。非 production、非 Streamlit Cloud、非 WebView、非真機、非真資料。**
> 畫面中的數字與狀態來自 `tests/ui_v3/market_stubs.py` 的合成資料（結論 chip 顯示「無法判定」是 fixture 的結果，不是市場判斷）。
> 不得把本目錄引用為 production PASS 或 Visual Fidelity Gate 通過。

## 驗的是什麼
`DEC-2026-11-07-02` S1：手機（≤768px）頁首一排五格、全部可見、不左右滑動、觸控 ≥48px；≥769px 維持側欄；客戶定案**非 sticky**（頁首在文件流內，隨頁面捲動移走，不貼定位）。

## 結果摘要（合成 fixture，Chromium 153.0.8010.12，viewport 高 844）
| 寬度 | 頁首 | 五格寬 | 格高 | 備註 |
|---|---|---|---|---|
| 374 | flex，position:static，y≈70.4（stHeader 高 60 之下） | 各 68.4 | 60 | 無橫溢、五格不重疊 |
| 375 | 同上 | 各 68.6 | 60 | 同上 |
| 390 | 同上 | 各 71.6 | 60 | 同上 |
| 768 | 同上 | 各 147.2 | 60 | 同上 |
| 769 | display:none | — | — | 側欄顯示（300px） |
| 1280 | display:none | — | — | 側欄顯示（300px） |
| 374／390 ＋190% 字體（**模擬**） | 五格全在視窗內，字換行不裁，頁首無捲動 | 同上 | 97～120（隨內容長） | 模擬方式見下 |

- 🌍 選取態：粗體 700＋底線＋3px 底色條（不只靠顏色）。未掛載四項：`aria-disabled="true"`、無 href、鍵盤不可聚焦；🤖 標「尚未開放」。Tab 可聚焦 🌍，焦點外框 2px solid（`fixture_w390_focus.png`）。
- 頁首與 Streamlit 自帶 stHeader 的 bounding box 不重疊（stHeader 0–60，頁首自 y≈70.4 起），stHeader 未被蓋住；手機無貼底 fixed 元素。
- 190% 字體是以 CSS 放大 root font-size 與頁首字級**模擬**，不是 OS textZoom。

## 檔案
- `fixture_w{374,375,390,768,769,1280}_top.png`：各寬度首屏截圖。
- `fixture_w390_focus.png`：390 寬鍵盤聚焦 🌍 的截圖。
- `fixture_w{374,390}_textzoom190_sim_top.png`：190% 模擬。
- `measure_fixture_normal.json`、`measure_fixture_textzoom190_sim.json`：每寬度的 getBoundingClientRect／computed style 量測（含逐格寬高、overlaps、stHeader、捲動後位置、Tab 序列）。
- `measure_reference.py`、`app_fixture_reference.py`：產生上列 JSON／PNG 的原始腳本（路徑寫死為作者本機暫存目錄，僅供對照，不是 CI 腳本）。
- PNG 皆 <500KB（最大約 263KB；check-added-large-files 只看新增檔，上限 500KB）。為控制體積只留各寬度首屏圖，不留 full-page／捲動後／底部截圖（其數據仍在 JSON）。

## 可重跑指令（repo 根目錄；需 streamlit、playwright、Chromium）
```
UI_V2_CHROMIUM=<chromium 執行檔> python -m pytest tests/ui_v3/test_ui_v3_top_nav_browser.py -q
```
該測試（slow lane）自起 streamlit、用同一份 fixture，斷言上表各項（等寬、≥48、無橫溢、無貼底 overlay、非 sticky、stHeader 不重疊、選取態、aria、鍵盤、190% 模擬）。對舊 CSS（含 sticky、固定高度、未撐滿的 stMarkdown）反跑會失敗。

## 環境
Python 3.13、Streamlit 1.59.2（requirements `>=1.59.1,<1.60.0`）、playwright（Python）1.64.1、Chromium 153.0.8010.12、Linux。

## NOT RUN
- Streamlit Cloud／production-like 截圖
- WebView（含 LINE／訊息 App 內嵌）
- 真機（iOS／Android）與安全區（safe-area）實測
- 螢幕閱讀器
- OS 層級 textZoom（190% 只是 CSS 模擬）
- 真資料畫面（本機無 FRED 金鑰與外網）

## NOT IMPLEMENTED
- 帳號入口：Preview（`ui_v3`）沒有登入入口（`git grep` 登入／帳號／OAuth 只有說明文字與 fixture 名稱），因此「帳號入口不遮擋」沒有可量測對象。

## 2026-11-13 CI 與本機補測摘要

### CI 事實（來源：GitHub Actions job log；由總管讀 step log 轉述，本文作者未能自行驗證）
- Slow lane 在四個 PR head 皆為 `1283 passed, 16 skipped, 19930 deselected`：`1a35359c`（#1233，run 43415198998）、`5b7ab4ed`（#1234，run 43422084231）、`2a95ae21`（#1235，run 43431573322）、`7fb9321e`（#1236，run 43444106501）。
- `tests/ui_v3/test_ui_v3_top_nav_browser.py` 與 `tests/ui_v3/test_ui_v3_market_page_browser.py` 於上述 Slow lane 中逐案 PASSED（寬度 374／375／390／768／769／1280 與 190% 字體 CSS 模擬等案例，依總管轉述）。
- Slow lane 標了 `continue-on-error`，PR 狀態不反映其紅綠；本節數字取自 step log 末行，不是 `mergeable_state`。

### 本機補測：NOT RUN
- 本機環境限制（Python 版本與 CI 不同、依賴未齊、依限制不大量安裝），未在本機重跑 browser 測試。

### 性質與限度
- 這是 **CI Chromium＋合成 fixture** 的結果。**不是** Streamlit Cloud、真機、WebView、safe-area、OS 層級字放大、螢幕閱讀器或實資料的 PASS（上列各項仍為 NOT RUN；Cloud／真機等缺口仍 NOT VERIFIED）。
- 不改 BL-0544 狀態；不重開 #1164。
- 「非作者對最後 head 的完整 QA」之 GitHub 證據仍為 **NOT VERIFIED**。
