# A5 🌍 市場頁使用者端調整（文字間距／高對比／鍵盤可逆）驗收報告｜2026-11-21

> Claude A 線（🌍 市場／UI 操作）單組執行 AI 產出，**未經第二組獨立複驗**。基準 main `41647fdb`（#1314 merge）。
> 量測：本機 Chromium 153 ＋ `tests/ui_v3/market_stubs.py` 合成 fixture（Preview FAKE，人造數值；未連任何外部來源）。
> **NOT VERIFIED：Cloud `ui_v3` URL、真機（iOS／Android／WebView）、系統字級、第二組複驗、CI 四項 check（本報告撰寫當下 PR 尚未跑 CI）。**
> **本批不改任何 production 檔、token、registry、`app_preview`、導覽、色票、資料／公式／來源。** 僅新增測試 1 檔、證據 1 資料夾，並補 #1309／#1314 兩項殘留 nit 的註記。

## 1. 與既有證據的去重（先讀，不重做）

| 項目 | 既有證據 | 本批是否重做 |
|---|---|---|
| 標題錨點鍵盤停駐、Tab 站數、單選方向鍵、展開區 Enter／Space、無橫向溢出（320–1440）、根字級 150%／190% 無溢出、灰階雙線 | `docs/evidence/ui_a2_mkt_ops_qa_2026_11_21/report.md` §3 | **否** |
| 頁自有文字 px 不隨根字級放大（Gate #2）、橫向手機 844×390 套桌機側欄（Gate #3） | 同上 §2 | **否**（仍為 Gate 差額，本批不碰 token 單位／導覽斷點） |
| 同快照來源分離 | `docs/evidence/ui_a4_mkt_source_separation_2026_11_21/` | **否** |

## 2. 本批新增且**無需新 Gate**的三項（已寫成可重跑測試）

`tests/ui_v3/test_ui_v3_market_adaptation_browser.py`（slow lane；（本 PR 修後共 20 條；下列 §2 敘述為替代 PR 當時狀態，桌機焦點項以 §9 為準））。

| # | 檢查 | 判定標準 | 結果（本機 Chromium＋合成 fixture） |
|---|---|---|---|
| 1 | WCAG 1.4.12 文字間距覆寫（行高 1.5、字距 .12em、詞距 .16em、段距 2em）× `normal`／`us_failed` × 390／1280 | 整頁與主內容區無橫向溢出；被裁切容器數不得多於覆寫前 | **PASS**（4 組：docScrollW＝視窗寬；覆寫前後被裁切容器數皆 11，`measure.json` 記錄皆為 1×1px 的 `<span>`；視覺隱藏（`clip`／`clip-path`）僅後續探針抽樣前 3 個確認、未留存，其餘未逐一查證；「與覆寫無關」為推論）。截圖 `textspacing_normal_390.png` 目視：折行、無重疊 |
| 2 | forced-colors（高對比）× 390／1280 | 主圖兩條線至少 stroke-dasharray 不同（顏色被系統收掉後仍可分辨） | **PASS**：實線 `none`／虛線 `6px, 4px`，stroke 同為黑；截圖 `forced_colors_390.png` 目視：兩線可分、選取 pill 仍為粗體＋黑框 |
| 3 | 鍵盤順序可逆：Tab 10 站、Shift+Tab 9 站（測試檔設定；`measure.json` 的 `tab/*` 是另一次 14 站走訪原始輸出） | 逆向逐站為正向的鏡像；無空站 | **PASS**（390／1280） |
| 4 | 導覽連結可見焦點指示（WCAG 2.4.7） | 聚焦（`:focus-visible`）後須有 ≥2px 實線環、或 box-shadow、或背景／底線變化 | **390 PASS**（`ui_v3/shell/nav.py` 的 `:focus-visible{outline:2px solid currentColor}`；底線與淡背景是「目前頁」本來的樣式，不是焦點指示）；**1280 修前 FAIL（修前曾鎖為 `xfail(strict)` known-gap；已由 §9 取代為真 PASS）**：側欄導覽連結聚焦前後 `outline-style:none`、`box-shadow:none`、背景同為 `rgb(24,37,74)`、無底線＝**無任何可見焦點指示**（`navfocus_1280.png`；`measure.json` 的 `tab/1280`）。真 DOM 變異：桌機加 `outline:2px solid` → 轉綠；手機只拿掉 `:focus-visible` 的 outline（不強制其他樣式）→ 轉紅。未聚焦基準取自「被聚焦的同一個元素」（初版取 DOM 第一個導覽連結，經獨立 QA 指出後已改）。**來源：未入庫探針的 computed style 數值，`measure.json` 只留有 outline，其餘欄位未留存** |

負控（記憶體內現編，不改 production）：文字間距下卡片 `min-width:900px` → 判溢出；forced-colors 下 `stroke-dasharray:none` → 判「僅靠顏色」；走訪結果反轉／插入空站 → 判不可逆（**判定函式層級**；正 tabindex 仍是可逆順序，不能當負控，檔內已據實標明）。

本機重跑指令（需 streamlit、playwright、`UI_V2_CHROMIUM`）：
`pytest tests/ui_v3/test_ui_v3_market_adaptation_browser.py -q -p no:cacheprovider` → 見 §7（2026-11-21，scratchpad venv、streamlit 1.59.2、`UI_V2_CHROMIUM=/opt/pw-browsers/chromium-1243/chrome-linux64/chrome`）。

## 3. 只記錄、不鎖測試的觀察（FACT；`measure.json` 與截圖為原始證據）

| 觀察 | FACT | 為何不鎖 |
|---|---|---|
| 暗色偏好（`prefers-color-scheme: dark`） | `measure.json` 的 dark 與 reduced_motion 兩組版面／主圖線色數值相同；`dark_scheme_390.png` 目視為淺色、可讀。**未記錄 `matchMedia` 確認模擬生效**，「暗色偏好沒有效果」是**推論** | 暗色不在任何核准規格內；鎖「不支援暗色」等於替客戶裁示 |
| `prefers-reduced-motion: reduce` | 版面無溢出、主圖兩線仍在。**未量動畫數量**，不宣稱「無動畫」 | 沒有量到的東西不寫成通過 |
| Chromium 給可捲動容器的 Tab 停駐點 | 兩個寬度（390／1280）都是 `<section data-testid="stMain" tabindex="0">`（`overflow:auto`，探針輸出，`measure.json` 未留存這些屬性），`outline-style:none`；**僅量 outline，未量 box-shadow／背景，不宣稱沒有任何焦點外觀**。單選 pill 與頁首導覽連結有環；**展開區（summary）在 `measure.json` 同為 `outline:none`，是否另有 box-shadow 等焦點外觀未量，不下結論** | 屬 Streamlit／瀏覽器原生行為；要補環＝新增視覺元件，列為 **Gate 差額**（見 §4），本批不動 |
| Streamlit 開發工具列兩站（`Deploy`、`Main menu`） | 出現在本機開發伺服器 Tab 序列；與 `ui_a2` 的 10 站記錄一致 | 部署環境是否同樣出現 NOT VERIFIED |

## 4. 仍需 Gate／未驗的差額（本批不代決）

1. 頁自有文字 px→rem（A2 Gate #2）：需客戶核准 token 單位。**本批沒有新證據可改變該 Gate。**
2. 橫向手機導覽斷點（A2 Gate #3）：需版面／導覽 Gate。
3. **≥769 側欄導覽連結無可見焦點指示（本批新發現；修前曾鎖 known-gap，**已由 §9 修復並改為真 PASS**）**：手機頁首已有 `outline:2px solid currentColor` 的焦點慣例（`ui_v3/shell/nav.py` 的 `TOP_KEY` 區塊 `a[data-testid="stPageLink-NavLink"]:focus-visible{outline:2px solid currentColor;…}`；符號式引用，不寫行號），桌機側欄沒有。
   - **候選最小修法（未實作、未核准）**：桌機側欄連結 `:focus-visible` 沿用手機同一組焦點樣式（同 token，不新增色、不改尺寸／間距／導覽斷點）。判定歸屬：把壞掉的鍵盤可見性修回既有慣例（A2 接合 A2「修正錯誤」）vs 導覽樣式變更——**我方讀法可被推翻**：因會動導覽殼的樣式，先不施工。
   - 現行驗收依據：`tests/ui_v3/test_ui_v3_market_adaptation_browser.py::test_desktop_sidebar_nav_link_shows_visible_focus_indicator`（修前名稱為 `…_known_gap`，已改名）（修好會 XPASS strict→紅，提醒移除標記）。
   - **單一最小決策題（待總管排入，不由本線直接問客戶）**：「桌機側欄導覽的鍵盤焦點，是否沿用手機頁首的同一組焦點樣式？」推薦：是（僅 CSS、無版面變更）；未授權範圍：導覽斷點、尺寸、色票。
4. 可捲動容器（`stMain`）Tab 停駐點的可見焦點環：新視覺元件＋需確認是否歸 Streamlit 上游；**候選、未提出核准請求**（避免一次丟多個問題；與上一項合併處理）。
5. Cloud／真機／系統字級／真實輔助科技（螢幕閱讀器）：全部 NOT VERIFIED。本批是自動化量測，不等於人工輔助科技驗收。

## 5. 同批殘留 nit 補註（只補註，不改結論）

- `ui_a4_mkt_source_separation_2026_11_21/measure.json`：新增 `tested_head_note`（#1314 最終 exact-head＝`bcae4f77`；量測當下 head 未記錄，不宣稱相同）。
- `ui_a2_mkt_ops_qa_2026_11_21/measure.json`：新增 `geom_rev_note`（#1309 最終 exact-head＝`d29fb52c`；`rev` 當時未填；並補 `us_failed` foldPx 前後相同 89.7／198.8／215.8）。
- 未處理：#1309 `report.md` 本文的 `us_failed` foldPx 句未改（值已記於上列 `measure.json` 註記，避免改動已被獨立 QA 看過的報告本文）。

## 6. 證據檔

`measure.json`（一次性探針原始輸出：文字間距前後、forced-colors／reduced-motion／dark 的版面與主圖線型、Tab 正逆走訪；一次性腳本在 scratchpad **未入庫**，repo 內可重跑的只有上述測試檔，其涵蓋 §2 三項，**不含 §3 的觀察**）、`textspacing_normal_390.png`、`forced_colors_390.png`、`dark_scheme_390.png`、`navfocus_1280.png`（桌機側欄連結聚焦時，與未聚焦無可見差異；截圖本身肉眼難辨，判定依據是 computed style 數值）。

## 7. 獨立 QA 後的修正（2026-11-21）

非作者 QA（唯讀）NEEDS-FIX：Must-Fix 1（焦點基準取錯元素；舊手機負控的背景色是配合錯誤基準調出來的，已刪除並改為只拿掉 outline 的真負控）、2（展開區焦點環宣稱）、3（dark 推論當 FACT）已修；Should-Fix 4／5／6／8 已修或降級為推論並註明來源；`xfail` 已加 `raises=AssertionError`。修正後本機：`pytest tests/ui_v3/test_ui_v3_market_adaptation_browser.py tests/test_doc_counters.py tests/test_constitution_file_refs.py` → `98 passed, 1 xfailed`（2026-11-21）。
未處理：`_N_STOPS` 寫死與站辨識以標籤＋前 12 字（Tab 可逆測試對一般 DOM 近乎同義反覆，檔頭已承認）；forced-colors 的 dasharray 差異在一般模式同樣成立（該測試非 forced-colors 專屬）；`nClipped` 只比數量。

## 8. 替代 PR 說明（總管裁示，#1296 comment 7056635038）

本檔內容原在 Draft #1318（head `d1f8186a`）。#1318 的首個 commit 訊息含工具附加的共同作者行與 session 網址，違反倉庫衛生規則；**未重寫歷史、未 force push、原 commit 仍留在 #1318 與其遠端分支**，只是**不會被帶進 main**。本 PR 以 `origin/main`（`41647fdb`）為基底、重新提交同一組允許 diff（1 個測試檔、本資料夾、兩個既存 `measure.json` 註記）。
桌機側欄焦點環（§4 第 3 項）依裁示另以最小獨立 PR 實作；實作後該 `xfail(strict)` 改為真 PASS。

## 9. 桌機側欄焦點環已修（獨立最小 PR；總管裁示 #1296 comment 7056635038）

`ui_v3/shell/nav.py` 新增一條規則：`[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"]:focus-visible{outline:2px solid currentColor;outline-offset:-3px}`（與手機頁首同一組焦點樣式；只在 `:focus-visible`；不改 hover／尺寸／斷點／色票／registry／`app_preview`）。
`xfail(strict)` 已改為真 PASS；新增驗收：1280 normal／dark／forced-colors 聚焦可見、Shift+Tab 走回仍可見、「開發中」項目不可聚焦、拿掉規則的真負控會轉紅；手機頁首既有 `top_nav_browser` 等 226 條回歸測試全綠。
本機：`test_ui_v3_market_adaptation_browser.py` → `20 passed in 61.78s`；`top_nav_browser／navigation_shell／token_contrast／design_tokens／preview_navigation_pages_guard／page_registry_guard／readonly_guard／import_guard` → `226 passed`（2026-11-21）。Cloud／真機／輔助科技仍 NOT VERIFIED。

（§9 補註：QA 差額複驗 Should-Fix 已修——補「開發中項目存在」前置斷言避免空洞通過；移除失效的『桌機加環轉綠』負控；§2／§4 舊敘述加註由 §9 取代。）
