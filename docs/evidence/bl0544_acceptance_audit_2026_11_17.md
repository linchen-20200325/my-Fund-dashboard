# BL-0544 post-merge evidence gap 唯讀驗收查核（2026-11-17）

> **性質**：唯讀查核。**單組產出，未經第二組獨立驗證；本檔含的全稱句（「僅有」「沒有其他」）一律未驗。** 不重做 #1164、不改任何程式／資料／來源、不部署、未存取 Streamlit Cloud 或真機。
> **基準**：`origin/main` `59b64760`。CI 數字來自 repo 內既有 evidence（總管轉述 GitHub Actions log），本組**未能自行驗證**，亦**未在本機重跑**瀏覽器測試（本機 Python 3.13、不裝依賴）。
> **三層不可混為一談**：(A) 本機／CI headless Chromium＋合成 fixture（slow lane，`continue-on-error`，非阻擋）≠ (B) Streamlit Cloud 真實驗收 ≠ (C) 真機／WebView。**本檔只可能對 (A) 給 PASS；(B)(C) 一律 NOT RUN。**

## 1. 驗收要求逐項
來源：`docs/BACKLOG.md` BL-0544 列；`DEC-2026-11-07-01`／`-02`（S1）；`DEC-2026-11-10-07` G1～G8；`DEC-2026-11-11-01`。

| # | 驗收要求 | 判定 | 證據出處 |
|---|---|---|---|
| 1 | 手機（≤768）頁首五格同列、全部可見、不重疊（fixture／CI Chromium） | **PASS（僅 A 層）** | `tests/ui_v3/test_ui_v3_top_nav_browser.py::test_mobile_top_nav_five_equal_visible_cells_at_least_48px`、`tests/ui_v3/test_ui_v3_market_page_browser.py::nav_violations`／`test_top_nav_s1_five_cells_mobile_and_sidebar_desktop`；`docs/evidence/bl0544_s1_chromium_fixture_2026_11_07/README.md` 結果摘要；CI 摘要同目錄 README 末節（Slow lane `1283 passed, 16 skipped`，#1233～#1236 head；總管轉述） |
| 2 | 無局部／整頁橫向溢出 390／768／1280 | **PASS（僅 A 層）** | `test_no_horizontal_overflow`（參數 390／768／1280 × 情境）、`overflow_violations`；top_nav 測試另有頁首不橫溢斷言 |
| 3 | 觸控目標 ≥48px | **PASS（僅 A 層，限頁首五格）**；市場頁其他可點控件（原生 radio 等）無 48px 斷言 → **NOT VERIFIED** | `nav_violations`：`cell["w"]<48 or cell["h"]<48`；top_nav `test_mobile_top_nav_five_equal_visible_cells_at_least_48px`（含未掛載項）。`test_native_radio_controls_inside_cards_are_operable_and_keep_state` 只斷言可操作與狀態保留，未量尺寸 |
| 4 | ≥769 維持側欄、頁首隱藏 | **PASS（僅 A 層）** | `nav_violations` width≥769 分支；`test_desktop_keeps_sidebar_and_hides_top_nav` |
| 5 | 手機首屏：390 結論 chip＋主圖／主數字可見 | **PASS（僅 A 層，相對基線）** | `firstscreen_violations`／`_FOLD_BASELINE`＝390／768／1280 ＝156.6／181.4／198.4px，容差 1px；390 主圖渲染寬 ≥354。**這是「不比改前差」的回歸守衛，不是客戶訂定的可見量門檻**（G5 明文暫行接受、不設門檻）；真實 Cloud 首屏 **NOT RUN** |
| 6 | 190% 字體不裁字 | **PASS（僅 A 層、CSS 模擬）**；OS textZoom **NOT RUN** | top_nav `test_top_nav_survives_190_percent_text_without_clipping_or_scrolling`；README「190% 是 CSS 模擬」 |
| 7 | 非 sticky、無貼底 fixed 元素、stHeader 不被蓋 | **PASS（僅 A 層）** | top_nav `test_top_nav_scrolls_away_with_the_page_flow`；README |
| 8 | 選取態非顏色唯一、aria、鍵盤焦點 | **PASS（僅 A 層、頁首）** | top_nav `test_mobile_top_nav_states_and_aria`；README（Tab 可聚焦、2px 外框） |
| 9 | **Streamlit Cloud（production-like）390 實測** | **NOT RUN** | 無截圖或量測；`DEC-2026-11-10-07` G7 明文「Cloud／WebView／真機另批」；README「NOT RUN」；`docs/evidence/new_ui2_five_page_status_2026_11_17.md` 第 11 行 |
| 10 | **Streamlit Cloud 1280 實測** | **NOT RUN** | 同上 |
| 11 | WebView（LINE 等）、safe-area | **NOT RUN** | README「NOT RUN」 |
| 12 | 真機 iOS／Android 觸控 | **NOT RUN** | 同上 |
| 13 | 螢幕閱讀器、OS 層 textZoom | **NOT RUN** | 同上 |
| 14 | 真資料畫面 | **NOT RUN**（A 層全為 `tests/ui_v3/market_stubs.py` 合成資料；README 明言） | README；`new_ui2_five_page_status_2026_11_17.md` 第 11 行（資料走 L2→L1 adapter，未驗真值） |
| 15 | 帳號入口不遮擋 | **NOT IMPLEMENTED**（Preview 無登入入口，無可量測對象） | README「NOT IMPLEMENTED」；BACKLOG BL-0544 列 |
| 16 | 非作者對 #1164 最後 head 的完整 QA（GitHub 證據） | **NOT VERIFIED** | BACKLOG BL-0544「非作者最後 head 完整 QA 的 GitHub 證據 NOT VERIFIED」；`docs/HANDOFF.md` L52。本組未查 GitHub review，repo 內無該 QA 回報 |

## 2. 現行 CI 守衛實際斷言（讀測試檔）
`tests/ui_v3/test_ui_v3_market_page_browser.py`（680 行，`pytestmark = slow`，需 streamlit＋Chromium，`importorskip`）：
- **寬度**：`_WIDTHS=(390,768,1280)`；有 5 個測試跨三寬度（溢出、主圖、頁首、區塊順序、容器／token、Secondary 對齊）；缺資料情境與 radio 操作僅 390／1280。**無 374／375／769 與 190% 在本檔**（那些在 `test_ui_v3_top_nav_browser.py`）。
- **橫向溢出**：有（`overflow_violations`，含 docScrollW／mainScrollW）。
- **觸控 48px**：只涵蓋頁首五格（≤768）；其他控件無。
- **變異驗證**：有（約 15 個 `test_mutation_*`，如縮小頁首格、強制寬卡、隱藏圖表）。
- **CI 位階**：`.github/workflows/pr-check.yml` slow-tests job `continue-on-error: true`（非阻擋，PR 狀態不反映其紅綠）。
- 本組未在本機重跑（見基準）；通過紀錄僅為 README 末節轉述。

## 3. 非作者 QA 紀錄（repo 內可見）
| 項目 | 狀況 |
|---|---|
| #1164（S1 Code） | **NOT VERIFIED**：最後 head 的非作者完整 QA 無 repo 內證據（BACKLOG／HANDOFF 自陳） |
| #1203（V1 視覺證據） | evidence 自陳「單組產出，未經第二組獨立驗證」，無 QA 紀錄 |
| #1205（V4 瀏覽器回歸） | repo 內未見獨立 QA 紀錄（NOT VERIFIED） |
| #1207（G3／G6 樣式） | 有：`docs/evidence/fund_newui2_market_g3_g6_build_evidence_2026_11_11.md` §10，轉記非作者 QA「MERGE-READY」；專案 AI 單組整理、未經第二組複驗；明列 hover／focus-visible 對比、Cloud／WebView／真機未驗 |

## 4. 結論
- **有 repo 內可驗證證據（僅 A 層 fixture／CI Chromium）**：#1、2、3（頁首）、4、5（相對基線）、6（模擬）、7、8。
- **必須由客戶或具 Cloud／真機權限者提供（NOT RUN）**：#9～14。**本組不索取存取權、不部署；僅列「若客戶要驗收」所需。**
- **NOT VERIFIED**：#3 頁首以外控件、#16 與 #1164／#1203／#1205 的非作者 QA。

### 若客戶要驗收，需提供（客觀清單）
1. 正式 Streamlit Cloud Preview 的 URL 與是否含真實資料之說明，或由具權限者提供截圖。
2. 390 與 1280 兩個寬度：首屏截圖、頁首五格是否同列、有無橫向捲動（整頁／局部）、主圖首屏可見量。
3. 真機（至少 iOS Safari、Android Chrome 各一）：頁首五格可點、觸控目標體感、安全區是否遮擋；若涉 LINE 內嵌，列 WebView 結果。
4. 每項標 PASS／FAIL／無法驗證，並註明測試者、日期、裝置、瀏覽器版本、是否真資料。
5. 非作者 QA：指定 #1164 最後 head 的獨立 QA 回報（GitHub review 或 evidence 檔）。
- 此為 `DEC-2026-11-10-07` G7 所述「另批」項，**需客戶 go**；本檔不構成授權。

## 5. 與現有敘述的差異（供總管判讀）
- 與 BACKLOG／HANDOFF **無矛盾**；補充：(a) 市場頁瀏覽器守衛的 48px 僅頁首；(b) 首屏為「不比基線差」非可見量門檻；(c) 本組未能重跑測試，CI 通過數為轉述。
- BACKLOG BL-0544 列「post-merge evidence gap 唯讀驗收」中的 Cloud 390／1280 證據，本組**無法取得**；結論為 NOT RUN，而非 PASS。

## NOT VERIFIED（本檔）
GitHub 上 #1164／#1203／#1205 的 review 狀態；CI log 數字；本機重跑結果；「僅頁首有 48px 斷言」為讀 `market_page_browser`／`top_nav_browser` 兩檔的單組判讀，未窮舉其他測試檔。
