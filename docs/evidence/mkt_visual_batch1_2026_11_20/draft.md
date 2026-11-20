單組產出，未經獨立複驗。截圖為 CI fixture（人造資料，tests/ui_v3/market_stubs），非 production-like，非 Cloud／真機；Chromium 1243、Streamlit 1.59.2、deviceScaleFactor 2、本機（有 Deploy 頂欄）。
# 🌍 市場頁視覺改善 第 1 批：草稿（第 1、3、4 項；第 2 項雙色線不做）
本目錄僅新增檔；repo 程式碼零修改。原型 CSS 只在截圖腳本內注入（scratchpad/ui_proto/proto.css），**不是**施工碼。
## 檔案
mkt_{390,1280}_{fold,full}_{before,after_DRAFT}.png（fold＝首屏 390x844／1280x800；full＝整頁）。已逐張用 Read 看過 390 fold before/after、1280 full before/after；390 full 與 1280 fold 兩組有產出但本組未逐張目視。
## 量測（Playwright getBoundingClientRect；fixture；1280 側欄 300px）
| 項目 | 390 before→after | 1280 before→after |
|---|---|---|
| stHeader 高 | 60→40 | 60→40 |
| h1 y | 187→173 | 126→112 |
| 檢視＋期間單選占高 | 136（2x68）→ 96（2x48，標籤內嵌同列） | 同 |
| 主圖 y | 684→630 | 574→519 |
| 首屏主圖露出 foldPx | 159.8→214.2（總高 237） | 226.4→280.8（總高 480） |
| 主圖 x／寬 | 17／356（不變） | 329→430／720（置中；寬不變） |
| 迷你圖寬 | 160→332（卡內寬） | 160→440 |
| 頁高 | 2293→2246 | 1927→1880 |
| Secondary 卡高 VIX／利率 | 192／250→192／258 | 同（利率卡因 pill 48px 多 8px，仍不等高、頂對齊） |
無橫向溢出（docScrollW＝vw）。主圖寬仍 ≤720（G3）。
## 變更項
**1 首屏壓縮**：(a) `[data-testid=stHeader]` 高 60→40，`.block-container` padding-top 3.4rem→2.5rem；(b) `stRadio` 改 flex 橫排，「檢視／期間」標籤與選項同列（label 13px、margin 0）。預計動：ui_v3/pages/mkt.py `_css()`（padding-top 兩處）、ui_v3/design/theme.py `app_css()`（stHeader 規則）。
**3 圖寬對齊**：迷你圖撐滿卡內寬；主圖 ≥769 置中（margin auto），≤768 維持卡內滿版。預計動：ui_v3/pages/chart_svg.py `SPARK_WIDTH`（建議 viewBox 改約 320x40 重算座標，而非本原型的 preserveAspectRatio=none，後者使末點圓變橢圓）、mkt.py `.uv3-spark`/`.uv3-chart`。主圖不放大。
**4 segmented/pill**：選項為 48px 高圓角膠囊、圓點隱藏（原生 radio input 保留，鍵盤方向鍵／焦點不變），選取＝primary 底白字，焦點＝2px primary 外框。預計動：theme.py `app_css()` 取代現有 radio 圓點 3 條規則。key uv3_mkt_period/_view/_rates 與 st.radio 呼叫不變。
選擇器：`[data-testid="stMain"] [data-testid="stRadio"]`、`[data-testid="stWidgetLabel"]`、`[data-testid="stRadioGroup"]`、`label[data-testid="stRadioOption"]`（含 `[data-selected="true"]`、`> div > div > div:first-child`＝圓點）、`[data-testid="stHeader"]`、`svg.uv3-spark`、`svg.uv3-chart`。
## 會受影響的現有守衛（逐一）
- test_ui_v3_market_page_browser.py：`_FOLD_BASELINE`（156.6/181.4/198.4）＋`firstscreen_violations`：新值遠高於基線，仍通過；**但須上調基線**，否則 `test_mutation_extra_top_spacing_pushing_chart_below_baseline_is_flagged`（summary margin-bottom 40px 期望被抓）會失效（214-40=174>156.6 不再報）。
- 同檔 `token_violations`：`radioSelectedBg` 量的是圓點（`label[selected] > div > div > div:first-child`）；pill 後圓點隱藏，量測目標須改為 label 本體背景；`test_mutation_legacy_theme_colours_are_flagged` 的注入選擇器需同步。
- 同檔 `container_violations`：`radioCount==3`、以 aria-label 找 radio、主圖不蓋卡邊（x≥卡x+1）——原型均滿足；`chart_violations` 圖寬 ≤720.5、390 圖寬 ≥354（356 滿足）。
- 同檔 `test_native_radio_controls_inside_cards_are_operable_and_keep_state`（390/1280）：以 label 文字 click、ArrowRight 鍵盤；隱藏圓點不影響，須實測 click 命中 pill。
- 同檔 `secondary_alignment_violations`：不強制等高仍成立（192 vs 258）。
- test_ui_v3_design_tokens.py:129：CSS 內 hex 須全在 token 表；pill 的色／圓角（999px）／48px 須先新增 token（原型為硬碼 #1a5fd0／#7f8ca6／#fff 僅供示意）。
- test_ui_v3_token_contrast.py `pairs()`：須新增「白字 on primary（文字 4.5:1）」「焦點環 on 卡面」並鎖期望值；現只有「白色內點 on primary」3:1。
- test_ui_v3_top_nav_browser.py:124-128：navTop ≥ stHeader.bottom 且 <200；header 40px 後仍成立，但需重跑確認 stHeader 未被蓋住（headerCovered）。
- test_ui_v3_market_chart_svg.py：若改 SPARK_WIDTH/viewBox，凡斷言迷你圖尺寸／座標處同步（本組僅 grep，未逐檔讀）。
- test_ui_v3_degraded_first_screen_budget.py、test_ui_v3_first_screen_c_and_wording_unify.py：本批不增減 chip／數字，預期不變，**未實跑**。
- AppTest（test_ui_v3_market_page_apptest.py）不載入 CSS，預期不受影響。
## 風險
1. 全部依賴 Streamlit 內部 data-testid 與 radio 內層 div 結構，升版可能壞（80 §17.1 已知）；browser 守衛是唯一防線。
2. 本機頂欄含 Deploy；Cloud 是否有此列未驗。縮高後 toolbar 按鈕在 40px 內仍可點，但未測觸控命中。
3. 隱藏圓點後「選取」只靠底色＋白字，色盲仍有色塊對比；是否需再加勾號／粗體由客戶定（目前不加內容）。
4. 迷你圖 viewBox 重算＝改 chart_svg.py，屬程式變更；末點圓需保持正圓。
5. 標籤內嵌在 390 剛好一行容得下（4 個 pill ≈ 270px）；字樣若定稿變長會折行（標籤與 pill 仍可用，只是少省高度）。
6. 單選改 pill、標籤內嵌屬版面異動，依 CLAUDE.md §-1.5.4 須客戶審此草稿後才動工。
## 驗收清單
- 390／1280：docScrollW≤vw；主圖寬 ≤720、390 ≥354；首屏主圖露出 ≥ 新基線（建議 390 設 ≥200，待客戶訂）。
- 每個 radio 選項高 ≥48px、寬 ≥44；觸控點擊切換；鍵盤 Tab 進入、方向鍵切換、焦點環可見；key 與狀態跨重跑保留。
- 迷你圖寬＝卡內寬、末點為正圓；1280 主圖水平置中；卡片外框／token 守衛全綠。
- 降級情境 tw_missing／both_missing／us_failed 三寬度同樣無溢出（本批未擷取，須施工時補）。
- Cloud／真機截圖（未驗）。
