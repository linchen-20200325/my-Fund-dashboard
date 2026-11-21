# A2 🌍 市場頁實際操作與行動裝置 QA 報告｜2026-11-21

> 單組執行 AI 產出，未經第二組獨立複驗。基準 main `bf3d61b2`。量測：本機 Chromium 對 CI fixture（Preview FAKE，DPR 1），腳本為一次性、未入 repo；`measure.json` 為其彙總。
> **NOT VERIFIED：Cloud `ui_v3` URL、真機（iOS／Android／WebView）、系統字級、第二組複驗、CI 四項 check。**

## 1. 結論

實際操作 390／768／1280（另 320／360／667×375／844×390／769／820／1024／1440）後，只找到 **1 項已存在、可修回既有慣例的使用阻擋**（已修）；另 2 項屬版面或 token 變更，列為 Gate 差額。其餘檢查項皆通過（見 §3）。

## 2. 阻擋項與處置

| # | 項目 | 類別 | 處置 |
|---|---|---|---|
| 1 | 標題錨點成為鍵盤停駐點 | FACT：改前每輪 Tab 17 站，其中 7 站是標題錨點（無文字、`aria-label` 為英文 `Link to heading`、平時 opacity 0）；💼 `assets.py`、`nas_diag.py` 早已用 `anchor=False`＋`role="heading"` 避免 | **已修**（`ui_v3/pages/mkt.py`）：改後每輪 10 站、錨點 0 站，三寬度皆同 |
| 2 | 頁面自有文字全用 px，不隨根字級放大 | FACT：模擬根字級 190% 後 `.uv3-row` 13px、chip 14px、`.uv3-metric` 20px 皆不變（Streamlit 原生字隨之放大，狀態／缺值揭露字沒有）。INFERENCE：真機 Android 字級／iOS 動態字級是否同樣不縮放 NOT VERIFIED | **Gate**（改 token 單位屬未核准 token 變更） |
| 3 | 橫向手機（844×390）套用桌機側欄 | FACT：側欄 300px 佔 36% 寬，主圖 y=558 超過視窗高 390，首屏露出 0px；667×375 則為頁首五格、圖 y=595、露出 0px（皆可捲動，非不可用） | **Gate**（導覽斷點／版面） |

### Gate 候選文字線框（未實作，供審）

```
#2 候選：type.* 由 px 改 rem（數值不變，只換單位）；需客戶核准 token 單位
#3 候選：橫向且高度 <= 500px 時改用頁首五格、不顯示側欄（導覽斷點加一條件）
        [頁首五格][PREVIEW 更新]
        [摘要卡][主圖 ...]
```

## 3. 通過項（FACT）

- 頁首五格：Tab 只停 🌍（`solid 2px` 焦點環），四個未掛載項 `aria-disabled`＋`aria-label` 且不可聚焦；各格 ≥48px。
- 三組單選：真觸控 tap 與方向鍵皆可切換、焦點保留、48×48；三個展開區滑鼠、Enter、Space 皆可開合（Streamlit 以高度開合，`details.open` 屬性不代表狀態）。
- 無橫向溢出：320／360／390／768／769／820／1024／1280／1440；390 與 320 加根字級 150%／190% 亦無（190% 時僅圖的負 margin 出界，屬設計）。
- 雙線：灰階下實線與 `6 4` 虛線＋末點直接標籤可辨；標籤碰撞由 `_spread` 處理。
- 來源／資料日／經過日數／缺值：`⬜`、`◇ 資料未備` 皆有文字，缺值不畫 0；四情境 aria 樹無 `NaN`。
- 與 BL-0559／0561／#1302 去重：三個展開列摘要 38px（候選 A）、頁首導覽 12／10px、SVG 刻度字 11（候選 B／C）已在批 2 report，本報告不重列。已知限制 `st.page_link` 無 `aria-current` 見 `docs/v2/80` §17.1，不重列。

## 4. 修正內容（`mkt.py`；測試 3 檔＋新檔 1）

`st.title(..., anchor=False)`；三個產生點的 `<h3>`／`<h4>` 改為 `<div class="uv3-hd uv3-hd3|4" role="heading" aria-level="3|4">`，CSS 以同值復刻（字級、行高、字距、內距）。未動色票、資料語意、公式、來源、stHeader、導覽、registry、`app_preview`、`.streamlit/`、`.github/`、frozen docs。

**computed style 全套比對（真 Chromium；base `bf3d61b2` 對本分支；normal／tw_missing×390／768／1280 共 6 組，每組 1 個 h1、1 個 3 級、5 個 4 級標題；22 個屬性，清單與逐組結果見 `measure.json` 的 `computed_style_base_vs_head`）**：
- 屬性含 font-size／weight／family／style、line-height、**letter-spacing**、color、四邊 margin 與 padding、display、text-align、text-transform、word-break、overflow-wrap、white-space、height。
- 第一次比對發現兩處差異：`word-break` 原為 `break-word`、新 div 為 `normal`（已補 `word-break:break-word`，重跑後消失）；4 級標題 `height` 42.3125px→42px（**未消除、據實保留**：原因 INFERENCE 為改前錨點圖示撐高行盒，未另行證明）。
- letter-spacing：3 級 `-0.096px` 前後相同；4 級原為 `normal`，`.uv3-hd4` 同為 `normal`，無差異，不需補。
- 修補後唯一殘餘差異＝4 級標題高度 0.3125px（6 組皆同一對值 42.3125→42，非逐標題量測）。

首屏／位置：以真 Chromium 於 base `bf3d61b2` 與本分支各重量一次主圖 SVG（`measure.json` 的 `geom_before`／`geom_after`，4 情境×3 寬度；`geom_chart_identical` 全為 true）。y 含 stMain 捲動量、與高為前後逐值相同：normal 390＝644.2／237.3、768＝594.6／480、1280＝533.6／480；tw_missing 390＝714.8／237.3、768＝645.3／480、1280＝584.3／480；us_failed 390＝754.3／237.3、768 與 1280 同 tw_missing；both_missing 無主圖（`null`）。首屏露出（`foldPx`）前後相同：normal 199.8／249.4／266.4、tw_missing 129.2／198.8／215.8。首屏以下元素有次像素位移：每個 4 級標題高 0.3125px 累積，整頁最大 y 位移（`geom_before`／`geom_after` 之外，先前一次量測，每情境一個最大值，非逐標題）390 為 1.6px、768／1280 為 0.7px。**此為已揭露的次像素差，非零差。**

測試：`test_ui_v3_mkt_heading_anchor_guard.py`（靜態，含負控）；瀏覽器檔新增 `test_no_heading_anchor_links_and_no_keyboard_stop_on_them`（三寬度；真 Tab 走訪 40 次）、`test_mutation_injected_heading_anchor_…`、`test_mutation_missing_heading_levels_…`；既有 h3／h4 選擇器改為 `role="heading"`。變異負控：把 production `anchor=False` 拿掉 → 靜態 1 條與瀏覽器 3 條轉紅（4 failed），還原後綠。

## 5. 測試輸出（原文）

`pytest tests/ui_v3/test_ui_v3_market_page_browser.py -q -p no:cacheprovider`：`123 passed in 247.91s (0:04:07)（補 `word-break` 前）`

`pytest tests/ui_v3 -q -p no:cacheprovider`（2026-11-20T23:12:14Z→23:18:28Z，**補 `word-break` 之前**）：`3147 passed, 769 warnings in 372.52s (0:06:12)`；補 `word-break` 後只重跑下一行兩檔，`tests/ui_v3` 全量**未重跑**。

補 `word-break:break-word` 後 `pytest tests/ui_v3/test_ui_v3_market_page_browser.py tests/ui_v3/test_ui_v3_mkt_heading_anchor_guard.py -q -p no:cacheprovider`：`133 passed in 240.30s (0:04:00)`；補 word-break 參數化負控後再跑同兩檔：`137 passed in 240.04s (0:04:00)`；四支治理守衛再跑：`120 passed in 80.69s (0:01:20)`

`pytest tests/test_canonical_rule_consistency.py tests/test_doc_counters.py tests/test_constitution_file_refs.py tests/test_retired_exception_ids.py -q -p no:cacheprovider`：`120 passed in 77.65s (0:01:17)`（補 `word-break` 後重跑：`120 passed in 74.09s (0:01:14)`）

環境：scratchpad venv（streamlit 1.59.2）、`UI_V2_CHROMIUM=/opt/pw-browsers/chromium-1243/chrome-linux64/chrome`。pre-commit 本機未安裝。

## 6. 證據檔

`tab_before_390_fold.png`／`after_390_fold.png`、`before_anchor_focus_390.png`（改前焦點落在錨點）、`gray_390_fold.png`／`gray_1280_fold.png`、`vp_844x390.png`、`zoom190_390.png`、`measure.json`。
