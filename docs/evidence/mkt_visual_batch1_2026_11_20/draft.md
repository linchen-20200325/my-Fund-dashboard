單組產出，未經獨立複驗。截圖為 CI fixture（人造資料，tests/ui_v3/market_stubs），非 production-like，非 Cloud／真機；Chromium 1243、Streamlit 1.59.2、deviceScaleFactor 2、本機（有 Deploy 頂欄）。
# 🌍 市場頁視覺改善 第 1 批：施工後實測（Preview-only，ui_v3）
授權範圍（ChatGPT 總管／客戶）：`mkt_page_visual_gap_analysis_2026_11_19.md` §4 第 1 項（**只做單選標籤內嵌／縮距，不縮 stHeader**）、第 3 項（迷你圖滿卡寬、主圖置中，主圖寬仍 ≤720）、第 4 項（單選 segmented／pill，純 CSS）。**第 2 項雙色線未做**（chart.* 色值未核准）。
## 施工內容
- `ui_v3/design/tokens.py`：新增 7 個 token（`color.pill.bg／border／selected.bg／selected.text／focus`、`radius.pill`＝999px、`size.touch.min`＝48px）；色值全部沿用 G3 已核准色票同一組值（無新色）。
- `ui_v3/design/theme.py`：新增 `pill_css()`（取代舊的 3 條圓點規則）。選項＝48px 膠囊、圓點隱藏（原生 radio input 仍在，Tab／方向鍵／焦點不變）；選取＝填 primary＋**粗體**（不只靠顏色）；鍵盤焦點＝2px primary 外框（`:has(input:focus-visible)`）；「檢視／期間／利率與信用」標籤與選項同列。
- `ui_v3/pages/chart_svg.py`：`SPARK_WIDTH` 160→320（viewBox 320×40，座標依 viewBox 重算；**不用** `preserveAspectRatio=none`，末點維持正圓）。
- `ui_v3/pages/mkt.py`：`.uv3-spark` 寬 100%、高 auto；≥769 主圖 `margin: auto` 置中（≤768 維持卡內滿版）；主圖最大寬 720 不動。
- 未動：資料、規則、來源、registry、導覽（頁首五格 ≥60px／觸控 ≥48px）、`.streamlit/config.toml`、`stHeader`、ui_v2、frozen 44、key `uv3_mkt_period／uv3_mkt_view／uv3_mkt_rates`、chip／數字／字樣。
## 量測（Playwright getBoundingClientRect；fixture；同腳本，施工前 origin/main 747c7585 vs 施工後；1280 側欄 300px）
| 項目 | 390 前→後 | 768 前→後 | 1280 前→後 |
|---|---|---|---|
| 檢視＋期間單選占高 | 136→96 | 136→96 | 136→96 |
| 單選每組高 | 68→48 | 68→48 | 68→48 |
| 主圖 y（視窗座標） | 684.2→644.2 | 634.6→594.6 | 573.6→533.6 |
| **首屏主圖露出 px（視窗 844／844／800）** | **159.8→199.8** | **209.4→249.4** | **226.4→266.4** |
| 主圖 x／寬 | 17／356→17／356 | 17／720→17／720 | 329／720→**430／720（置中）** |
| 迷你圖寬×高 | 160×40→332×41.5 | 160×40→334×41.8 | 160×40→440×55 |
| Primary 卡高 | 612→572 | 855→815 | 855→815 |
| VIX／利率卡高 | 192／250→194／260 | 192／250→194／260 | 192／250→207／273（迷你圖變高） |
| 整頁高 | 2293→2264 | 2010→1979 | 1927→1910 |
| 橫向溢出（docScrollW−vw） | 0→0 | 0→0 | 0→0 |

降級情境 `tw_missing`（台股缺；同樣 fixture）首屏主圖露出：390 89.2→129.2、768 158.8→198.8、1280 175.8→215.8；整頁高 2363→2334／2060→2030／1977→1960；三寬度無溢出。截圖同目錄 `mkt_tw_missing_*`。
利率卡因 pill 48px 多約 10px，兩卡仍頂對齊、不強制等高（G6 核准不變）。
## 檔案
`mkt_{390,768,1280}_{fold,full}_{before,after}.png`、`mkt_tw_missing_{390,768,1280}_{fold,full}_{before,after}.png`（fold＝首屏 390x844／768x844／1280x800；full＝整頁）；`measure_before.json`／`measure_after.json`（原始量測）。已逐張目視 390 fold／1280 full／tw_missing 390 full 的 after；其餘未逐張目視。
## 守衛同步（`tests/ui_v3`）
- `test_ui_v3_market_page_browser.py`：`_FOLD_BASELINE` 156.6／181.4／198.4 → **194／244／261**（依據＝本批施工後實測 199.8／249.4／266.4 各扣 5px 容字型差異；舊基線來自更早的 192848b，施工前實測已是 159.8／209.4／226.4）。這樣 summary +40px 的負控與退回舊版面都仍會被抓。`radioSelectedBg` 改量 label 本體（圓點已隱藏），對應突變測試注入選擇器同步；新增 `pill_violations`（11 項 ≥48×44、圓點隱藏、選取粗體＋填色、色／圓角＝token）、`spark_violations`（寬＝卡內寬、末點正圓）、`centered_violations`、鍵盤焦點環守衛，以及對應負控。
- `test_ui_v3_design_tokens.py`：核准清單加入 7 個 pill token，並新增「pill 色必須是既有色票值、48px＝頁首觸控下限」。
- `test_ui_v3_token_contrast.py`：新增 pill 選取文字 on 選取底 5.85:1（≥4.5）、未選文字 16.27:1、pill 邊線／選取底／焦點環（≥3）等 8 組配對與負控。
## 風險／未驗
1. 依賴 Streamlit 內部 `data-testid` 與 radio 內層 div 結構（80 §17.1 已知），升版可能壞；browser 守衛是唯一防線。
2. Cloud／真機／觸控命中皆 **NOT RUN**；本機頂欄含 Deploy，Cloud 是否有此列未驗。
3. 選取狀態＝填色＋粗體；粗體會讓選取項略寬（切換時 pill 寬度微變）。未加勾號（不增內容）。
4. 1280 迷你圖隨卡寬變為 440×55，視覺比例改變；筆畫以 `vector-effect: non-scaling-stroke` 維持 1.6px。
5. 標籤內嵌在 390 剛好一行；字樣若變長會折行（仍可用，少省高度）。
6. 單組產出，無獨立複驗；焦點環用 `:has()`，需 Chromium 105+／Safari 15.4+／Firefox 121+。
