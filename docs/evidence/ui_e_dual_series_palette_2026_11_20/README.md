# UI-E：🌍 市場比較圖雙系列色票候選（docs-only 設計提案）｜2026-11-20

> **設計提案，尚未核准。** fixture 為人造波形（FAKE），不是真資料；本批**不等於 Cloud PASS**（未部署、未接線）。
> 單組產出，未經獨立複驗。使用者參考圖：**NOT PROVIDED**（本批沒有取得；候選為依既有 token 與公式獨立推導）。
> 基準：`origin/main` `8ebb5290`（含 #1298）。派工：#1301。

## 交付

| 檔案 | 說明 |
|---|---|
| `docs/design/ui_v3_market_dual_series_palette_review_2026_11_20.html` | 自包含離線 HTML（無外部資源）：三候選卡（390 手機頁首五格／1280 深色側欄＋淺色主區，同一頁響應式）、比較表、與既有狀態色距離、推薦、方法、NOT VERIFIED |
| `shot_390.png`／`shot_1280.png` | 真 Chromium 截圖（stage 區），128 色調色盤化（為 <400KB；**截圖色值因量化會有微小偏移，色值與對比以 measure.py 輸出為準**） |
| `measure.py` | `colors`（色彩量測）、`build`（產生 HTML）、`shoot`（截圖與版面量測） |

不改任何既有檔：未動 tokens.py、chart_svg.py、mkt.py、tests、docs/v2/44／81、DECISIONS／BACKLOG／HANDOFF、資料源與公式。`measure.py` 以 importlib 讀 `chart_svg.py` 檔案畫出與正式圖同幾何的折線，不 import `ui_v3` 套件，也不 import `ui_v3.fixtures`。

## 三個候選（series 1 實線／series 2 虛線）

| 候選 | series 1 | series 2 | 備註 |
|---|---|---|---|
| A 深藍＋橙 | `#0a3f86` | `#d06a00` | 建議（僅為建議，不代客戶選色） |
| B 靛紫＋青綠 | `#4b2fa8` | `#0a8f80` | 藍綠可能被讀成「綠＝好」；tritan 距離最弱 |
| C 深藍＋洋紅 | `#1a3f8f` | `#c2338e` | protan 距離最弱、灰階亮度比最低 |

三者皆不用紅／綠當好壞、保留實／虛線＋末點標籤＋文字數值、末點標籤文字維持文字色。完整風險與推薦在 HTML 比較表。

## 量測原文（`python docs/evidence/ui_e_dual_series_palette_2026_11_20/measure.py colors`）

```
== 底色：surface #ffffff ／page.bg #f5f7fb ／text #172033
== 基線（現況：兩線皆 currentColor＝#172033）：對 surface 16.27，兩線同色（ΔE76 0.0、灰階比 1.00），分辨完全靠實／虛線＋末點標籤

== 候選 A｜深藍＋橙｜series1 實線 #0a3f86、series2 虛線 #d06a00
  對 surface #ffffff 對比：s1 10.15、s2 3.66（參考 3:1：皆達）
  對 page.bg #f5f7fb 對比：s1 9.47、s2 3.41（參考 3:1：皆達）
  兩線距離 CIE76 ΔE：原色 113.9；protan 100.2；deutan 115.4；tritan 87.4
    protan 模擬色：s1 #0d4789、s2 #887700
    deutan 模擬色：s1 #003c85、s2 #a18f00
    tritan 模擬色：s1 #00505c、s2 #e5525a
  灰階：s1 #414141（L=0.0534）、s2 #868686（L=0.2372）；兩線灰階亮度比 2.80
  與「primary（選取 pill 填色） #1a5fd0」ΔE76：s1 26.5、s2 129.1
  與「yellow 狀態邊 #b7791f」ΔE76：s1 103.1、s2 20.3
  與「red 狀態邊 #c0392b」ΔE76：s1 94.1、s2 32.2
  與「grey／neutral 狀態邊 #7f8ca6」ΔE76：s1 43.6、s2 86.2
  與「sidebar accent #5fd3d0」ΔE76：s1 77.3、s2 102.1

== 候選 B｜靛紫＋青綠｜series1 實線 #4b2fa8、series2 虛線 #0a8f80
  對 surface #ffffff 對比：s1 9.25、s2 4.00（參考 3:1：皆達）
  對 page.bg #f5f7fb 對比：s1 8.62、s2 3.73（參考 3:1：皆達）
  兩線距離 CIE76 ΔE：原色 101.8；protan 68.9；deutan 61.0；tritan 38.3
    protan 模擬色：s1 #004aac、s2 #88867f
    deutan 模擬色：s1 #0044a6、s2 #787a81
    tritan 模擬色：s1 #224f68、s2 #00928a
  灰階：s1 #474747（L=0.0636）、s2 #7f7f7f（L=0.2127）；兩線灰階亮度比 2.32
  與「primary（選取 pill 填色） #1a5fd0」ΔE76：s1 25.1、s2 86.1
  與「yellow 狀態邊 #b7791f」ΔE76：s1 121.3、s2 76.8
  與「red 狀態邊 #c0392b」ΔE76：s1 101.3、s2 97.4
  與「grey／neutral 狀態邊 #7f8ca6」ΔE76：s1 68.2、s2 39.5
  與「sidebar accent #5fd3d0」ΔE76：s1 104.8、s2 26.1

== 候選 C｜深藍＋洋紅｜series1 實線 #1a3f8f、series2 虛線 #c2338e
  對 surface #ffffff 對比：s1 9.76、s2 5.05（參考 3:1：皆達）
  對 page.bg #f5f7fb 對比：s1 9.10、s2 4.71（參考 3:1：皆達）
  兩線距離 CIE76 ΔE：原色 57.5；protan 18.8；deutan 45.2；tritan 85.9
    protan 模擬色：s1 #004992、s2 #465f90
    deutan 模擬色：s1 #003f8d、s2 #71788b
    tritan 模擬色：s1 #005360、s2 #cf2f5c
  灰階：s1 #444444（L=0.0576）、s2 #6f6f6f（L=0.1579）；兩線灰階亮度比 1.94
  與「primary（選取 pill 填色） #1a5fd0」ΔE76：s1 21.6、s2 62.0
  與「yellow 狀態邊 #b7791f」ΔE76：s1 106.4、s2 86.8
  與「red 狀態邊 #c0392b」ΔE76：s1 95.2、s2 58.0
  與「grey／neutral 狀態邊 #7f8ca6」ΔE76：s1 47.0、s2 63.5
  與「sidebar accent #5fd3d0」ΔE76：s1 81.5、s2 102.4

== NOT RUN：真人色覺測試；實機螢幕／印表機／黑白列印；severity<1（部分色弱）；Brettel／Viénot 等其他演算法；achromatopsia 以外的單色視覺
```

演算法：相對亮度與對比為 WCAG 2.x；色覺模擬為 Machado、Oliveira、Fernandes 2009 的 protan／deutan／tritan 矩陣（severity 1.0，線性 RGB）；距離為 CIE76 ΔE（D65）；灰階＝相對亮度編回 sRGB。3:1 只是 WCAG 1.4.11 的**參考**門檻，本專案未核准該門檻，也沒有核准的 ΔE 門檻。

## 版面量測原文（`UI_V2_CHROMIUM=... python .../measure.py shoot`，Chromium，DPR 1）

```
== viewport 390: {'scrollWidth': 390, 'clientWidth': 390, 'fullHeight': 8169, 'htmlMinFontPx': 13, 'htmlTextNodesUnder13px': 0, 'touchTargets': 29, 'touchMinHeightPx': 48, 'touchUnder48': 0, 'overflowElements': 0, 'primaryCharts': 3, 'primaryChartWidthPx': 322, 'primaryChartSvgTextRenderedPx': [9.84, 10.73], 'sideDisplay': 'none', 'topnavDisplay': 'grid'}
screenshot shot_390.png: 390x3550px, 135333 bytes, palette 128 colors
== viewport 1280: {'scrollWidth': 1280, 'clientWidth': 1280, 'fullHeight': 4386, 'htmlMinFontPx': 13, 'htmlTextNodesUnder13px': 0, 'touchTargets': 29, 'touchMinHeightPx': 48, 'touchUnder48': 0, 'overflowElements': 0, 'primaryCharts': 3, 'primaryChartWidthPx': 590, 'primaryChartSvgTextRenderedPx': [18.03, 19.67], 'sideDisplay': 'block', 'topnavDisplay': 'none'}
screenshot shot_1280.png: 1280x2736px, 189789 bytes, palette 128 colors
```

- 橫向溢出：390／1280 皆 `scrollWidth == clientWidth`、`overflowElements 0`。
- HTML 文字最小字級 13px（`htmlTextNodesUnder13px 0`）；觸控目標（pill、summary、頁首格、側欄列）29 個，最小高 48px，`touchUnder48 0`。
- **SVG 內文字不計入上面的字級**：主圖用正式 `chart_svg` 幾何（viewBox 360×240、字 11／12 user units），渲染後 390 約 9.8–10.7px、1280 約 18.0–19.7px。390 的數字比 #1298 實測的 10.88／11.87px 更小，因為示意殼的外框與內距讓圖寬為 322px（正式頁 358px）；這是已知的 chart_svg 字級問題（#1298 R1 候選 C），本批不處理。
- 1280 的主圖欄與右側辨識列間距已加大到 28px。末點標籤在此示意殼的字型下會超出 viewBox 右緣，故示意頁對圖設 `overflow:visible`；正式頁字型不同，實際是否裁切**未驗**。
- 辨識列小圖無文字（裝飾，標籤在 HTML）。

## 測試

本批要求的三支與新增 .py 可能觸發的全 repo 掃描守衛（輸出原文見「測試輸出」）。

## NOT VERIFIED

Cloud `ui_v3` URL 與部署 SHA；iOS／Android／WebView 真機；真人色覺測試；實機螢幕與列印；severity 小於 1 與其他模擬演算法；示意殼是否與正式 Streamlit 頁一致（字型、末點標籤是否裁切）；客戶是否同意兩線不同色與色值；獨立稽核。

## 末點標籤與線尾／辨識列的距離（`measure.py labelcheck`，Chromium，DPR 1）

指令：`UI_V2_CHROMIUM=... python docs/evidence/ui_e_dual_series_palette_2026_11_20/measure.py labelcheck`（另設 `UIE_CROP_DIR` 可存 390 候選 B 的局部放大截圖，不入庫）。數值為像素，負數＝重疊或超出：

```
viewport 390: {'chart': 0, 'labels': ['台股 102.0', 'S&P 500 104.6'], 'labelLeftMinusLineRightPx': 5.4, 'labelsVerticalGapPx': 25.9, 'labelRightMinusSvgRightPx': 4.8, 'labelRightMinusCardInnerRightPx': 16.8, 'stripLeftMinusLabelRightPx': -314.8}
viewport 390: {'chart': 1, 'labels': ['台股 102.0', 'S&P 500 104.6'], 'labelLeftMinusLineRightPx': 5.4, 'labelsVerticalGapPx': 25.9, 'labelRightMinusSvgRightPx': 4.8, 'labelRightMinusCardInnerRightPx': 16.8, 'stripLeftMinusLabelRightPx': -314.8}
viewport 390: {'chart': 2, 'labels': ['台股 102.0', 'S&P 500 104.6'], 'labelLeftMinusLineRightPx': 5.4, 'labelsVerticalGapPx': 25.9, 'labelRightMinusSvgRightPx': 4.8, 'labelRightMinusCardInnerRightPx': 16.8, 'stripLeftMinusLabelRightPx': -314.8}
viewport 1280: {'chart': 0, 'labels': ['台股 102.0', 'S&P 500 104.6'], 'labelLeftMinusLineRightPx': 9.8, 'labelsVerticalGapPx': 46.3, 'labelRightMinusSvgRightPx': 8.9, 'labelRightMinusCardInnerRightPx': -249.1, 'stripLeftMinusLabelRightPx': 19.1}
viewport 1280: {'chart': 1, 'labels': ['台股 102.0', 'S&P 500 104.6'], 'labelLeftMinusLineRightPx': 9.8, 'labelsVerticalGapPx': 46.3, 'labelRightMinusSvgRightPx': 8.9, 'labelRightMinusCardInnerRightPx': -249.1, 'stripLeftMinusLabelRightPx': 19.1}
viewport 1280: {'chart': 2, 'labels': ['台股 102.0', 'S&P 500 104.6'], 'labelLeftMinusLineRightPx': 9.8, 'labelsVerticalGapPx': 46.3, 'labelRightMinusSvgRightPx': 8.9, 'labelRightMinusCardInnerRightPx': -249.1, 'stripLeftMinusLabelRightPx': 19.1}
```

- **390 候選 B 的「S&P 500 104.6」與虛線尾端沒有重疊**：標籤左緣比所有線的最右緣多 5.4px；兩個標籤上下相隔 25.9px，也沒有互相重疊（已用 390 局部放大截圖目視確認）。三個候選數字相同（共通，因為幾何相同）。
- **已知的示意殼瑕疵（三候選共通，未處理）**：390 時標籤右緣比 SVG 右緣多 4.8px、比卡片內容區右緣多 16.8px（卡片邊框加內距共 13px，所以約有 3.8px 越過卡片外緣）。原因是示意殼的字型（較寬的 fallback CJK 字型）與 `chart_svg` 的 84px 右側留白；這是既有版面（`chart_svg` 常數）問題，只調 CSS 無法在不縮字的前提下消除，本批不動。正式頁字型不同，**未驗**。
- 1280：標籤右緣超出 SVG 右緣 8.9px，但離卡片內緣還有 249px，離右側辨識列 19.1px，沒有貼住。

## 灰階比的小數差異

表中 A 的灰階亮度比 2.80 是用 8 位元量化後的灰階色值（`#414141`／`#868686`）算的；直接用未編碼的相對亮度 L（0.0534、0.2372）算約為 2.78。差異來自把亮度編回 8 位元時的四捨五入，不影響候選排序。HTML 的比較表下方也有同樣說明。

## 測試輸出

**歷次紀錄**：第一次（`eafae515`）與第二次（`a2f35630`）各跑過同樣兩組，皆全綠（113 passed／116 passed）。**以下是在 head `54ebb3a3`（本次修改的 commit）重跑的原文**；本 README 此段之後另有一個只改本段的 commit，其 SHA 以 `git log` 為準。環境：本機 scratchpad venv，**非 CI**；未跑全套與 CI 四項 check。

```
$ python -m pytest tests/test_canonical_rule_consistency.py tests/test_doc_counters.py tests/test_constitution_file_refs.py -q -p no:cacheprovider
........................................................................ [ 63%]
.........................................                                [100%]
113 passed in 88.97s (0:01:28)

$ python -m pytest tests/test_services_purity_contract.py tests/ui_v3/test_ui_v3_fixtures_are_fake_guard.py tests/ui_v3/test_ui_v3_import_guard.py -q -p no:cacheprovider
........................................................................ [ 62%]
............................................                             [100%]
116 passed in 9.02s
```
