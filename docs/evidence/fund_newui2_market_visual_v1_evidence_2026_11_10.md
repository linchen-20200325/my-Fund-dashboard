# 基金 New UI2「🌍 市場與趨勢」V1 視覺證據歸檔：Current 側（2026-11-10）

> **性質**：V1 證據歸檔；**不是**設計 SSOT、**不新增** token 或視覺規格、**不啟動 UI 施工**，不修改 `ui_v3`／`ui_v2`／入口／`services`／workflow／`data_cache`。
>
> **Reference 側 NOT VERIFIED**：股票 HTML 原檔在客戶的 ChatGPT 對話，本批（Claude Code）未取得，故 Reference 欄一律「NOT VERIFIED（轉引 #1200）」，Delta 欄一律「無法判定（Reference 未取得）」。轉引來源為 #1200 文件 `docs/evidence/fund_newui2_vs_stock_html_visual_gap_2026_11_10.md`（其參考側描述本身亦是轉述）。
>
> **標記**：FACT＝本批實測或讀檔；INFERENCE＝推論，可被推翻；NOT VERIFIED＝本批未驗。
>
> **證據限制**：資料為 `tests/ui_v3/market_stubs.py` 的人造數值（合成資料，非市場資料），不連任何外部來源；由本機 headless Chromium 產生；**不是** Streamlit Cloud、WebView 或真機證據。圖檔與產生方式見 `docs/evidence/fixtures/fund_newui2_market_visual_v1_2026_11_10/README.md`。
>
> **來源**：客戶已核准 G1／V1（見 `docs/evidence/fund_newui2_market_visual_acceptance_plan_2026_11_10.md` §0.2）。本檔為單組產出，未經第二組獨立驗證。

基準：`origin/main` 的 `d49f1937`（`ui_v3` 程式碼與該基準一致）；Streamlit 1.59.2；`deviceScaleFactor` 1。

---

## 1. 客戶裁示對 Delta 的約束

- FACT（客戶裁示，引自驗收規劃文件）：G2 維持「淺色主內容＋深色側欄」（`DEC-2026-10-27-09`）；G4 桌機維持左側欄；G5 暫時接受現況（手機首屏主圖露出 157／239px），不設門檻。
- 因此：Reference 的 dark-only 與頂端頁籤（轉述）即使日後被驗證存在，也**不構成**改版授權；本檔不提改版建議。

## 2. 截圖清單（情境：`normal`＝人造資料齊全；`missing`＝人造資料缺台股）

資料夾：`docs/evidence/fixtures/fund_newui2_market_visual_v1_2026_11_10/`。每個寬度×情境各一張首屏（`first`）與一張整頁（`full`），共 12 張，總量約 2.0MB，單檔最大約 256KB。

| 寬度 | normal 首屏 | normal 整頁 | missing 首屏 | missing 整頁 |
|---|---|---|---|---|
| 390 | `w390_normal_first.png` | `w390_normal_full.png` | `w390_missing_first.png` | `w390_missing_full.png` |
| 768 | `w768_normal_first.png` | `w768_normal_full.png` | `w768_missing_first.png` | `w768_missing_full.png` |
| 1280 | `w1280_normal_first.png` | `w1280_normal_full.png` | `w1280_missing_first.png` | `w1280_missing_full.png` |

整頁高度（CSS px，`normal`／`missing`）：390＝2426／2497；768＝2175／2225；1280＝2092／2142。三寬度皆無整頁橫向溢出（`scrollWidth` 等於視窗寬，兩情境皆同）。

## 3. Reference／Current／Delta（六面向×三寬度）

Reference 欄：NOT VERIFIED（轉引 #1200）。Delta 欄：無法判定（Reference 未取得）。Current 欄皆為 FACT（`measure.json` 數值，本批重跑）；「同」表示該寬度與上一列相同。

| 面向 | 寬度 | Reference | Current（FACT） | Delta |
|---|---|---|---|---|
| 色票 | 390 | NOT VERIFIED（轉引 #1200） | 主內容背景 rgb(246,248,250)、文字 rgb(31,35,40)；chip 底 rgba(128,128,128,.12)、邊線 rgba(128,128,128,.45)；側欄隱藏 | 無法判定（Reference 未取得） |
| 色票 | 768 | NOT VERIFIED（轉引 #1200） | 同 390；側欄隱藏 | 無法判定（Reference 未取得） |
| 色票 | 1280 | NOT VERIFIED（轉引 #1200） | 主內容色同上；側欄顯示，背景 rgb(14,17,23) | 無法判定（Reference 未取得） |
| 卡片 | 390 | NOT VERIFIED（轉引 #1200） | 圓角 8px、內距 10×12px、下距 8px、1px 邊線 rgba(128,128,128,.35)、背景透明；全部單欄（寬 358） | 無法判定（Reference 未取得） |
| 卡片 | 768 | NOT VERIFIED（轉引 #1200） | 樣式同 390；Secondary 兩卡並排各 360 寬；依據卡三張並排各 234.7 寬 | 無法判定（Reference 未取得） |
| 卡片 | 1280 | NOT VERIFIED（轉引 #1200） | 樣式同 390；Secondary 兩卡各 466 寬；依據卡三張各 305.3 寬 | 無法判定（Reference 未取得） |
| 間距 | 390 | NOT VERIFIED（轉引 #1200） | 主區左右 16px、上 54.4px；max-width 1100px；本文列 13px／行高 20.15px；h1 27.2px／700；主數字 20px | 無法判定（Reference 未取得） |
| 間距 | 768 | NOT VERIFIED（轉引 #1200） | 同 390（內容寬 736） | 無法判定（Reference 未取得） |
| 間距 | 1280 | NOT VERIFIED（轉引 #1200） | 同 390 的 padding 與字級；主區寬 980（自 x＝300 起） | 無法判定（Reference 未取得） |
| 圖表 | 390 | NOT VERIFIED（轉引 #1200） | Primary 圖 358×238.7；縮放 0.994、刻度字約 10.9px、末點標籤字約 11.9px；缺台股時仍畫單序列 | 無法判定（Reference 未取得） |
| 圖表 | 768 | NOT VERIFIED（轉引 #1200） | 720×480；縮放 2、刻度字 22px、末點標籤字 24px；缺台股情境同形態 | 無法判定（Reference 未取得） |
| 圖表 | 1280 | NOT VERIFIED（轉引 #1200） | 720×480；數值同 768（圖寬被上限 720 限住） | 無法判定（Reference 未取得） |
| 頁首 | 390 | NOT VERIFIED（轉引 #1200） | 框架頂列高 60；頁首五格橫排，容器 358×61（y＝70.4），每格 71.6×60，全部可見；無側欄 | 無法判定（Reference 未取得） |
| 頁首 | 768 | NOT VERIFIED（轉引 #1200） | 頂列高 60；頁首五格，容器 736×61，每格 147.2×60 | 無法判定（Reference 未取得） |
| 頁首 | 1280 | NOT VERIFIED（轉引 #1200） | 頁首五格不顯示；左側欄寬 300；頂列自 x＝300 起、寬 980、高 60 | 無法判定（Reference 未取得） |
| 手機首屏 | 390（844 高） | NOT VERIFIED（轉引 #1200） | 結論 chip 在首屏；主圖頂 y＝687.4、首屏露出約 157／238.7px（missing 情境：圖頂 758、露出約 86px） | 無法判定（Reference 未取得） |
| 手機首屏 | 768（1024 高） | NOT VERIFIED（轉引 #1200） | 圖頂 y＝662.6、露出約 361／480px（missing：圖頂 713.3、約 311px） | 無法判定（Reference 未取得） |
| 手機首屏 | 1280（800 高） | NOT VERIFIED（轉引 #1200） | 圖頂 y＝601.6、露出約 198／480px（missing：圖頂 652.3、約 148px）；此寬度為桌機，列出僅供對照 | 無法判定（Reference 未取得） |

## 4. Current 側 FACT 量測補充

1. **頁首五格**：390 為各 71.6×60、768 為各 147.2×60，皆全可見、無橫向溢出；1280 不顯示頁首。
2. **橫向溢出**：三寬度、兩情境皆無（`scrollWidth`＝視窗寬）。
3. **首屏主圖露出量（G5：客戶暫時接受現況，不設門檻，僅記錄）**：390＝約 157／239px（normal）；其餘寬度見 §3。missing 情境因多一段缺項說明，露出量較少。
4. **Secondary 卡高度差**：兩卡高度皆 192.1px；768 與 1280 並排時，利率卡頂比 VIX 卡頂低 84px（兩情境同）；390 為單欄上下堆疊，不適用。
5. **<48px 的可互動元素數**（`normal`；`missing` 同數；本批使用預設 Streamlit 工具列，含 Deploy／選單鈕）：390＝23、768＝23、1280＝24。逐項（390 與 768 相同）：標題錨點連結 16×16 共 7 個、radio 的 input 13×13 共 11 個、expander summary 高 38px 共 3 個、框架 Deploy 鈕 57×28、框架選單鈕 28×28。1280 多一個側欄「更新資料」按鈕 240×40（頁面自繪的 CTA）。以 44px 為界的數字與 48px 相同。
6. **含框架元件的說明**：上列多數是 Streamlit 框架元件（錨點連結、radio input、工具列鈕）；expander summary 與「更新資料」鈕由頁面使用，但外框為 Streamlit 元件。哪些元件屬「頁內控制項觸控下限」的適用範圍＝INFERENCE，驗收規劃文件 MV-14 亦記為「未訂」。Cloud 是否顯示 Deploy／選單鈕＝NOT VERIFIED。
7. **chip 總數**：頁內 `.uv3-chip` 在 normal 為 13、missing 為 15；頁級首屏預算口徑不在本檔判斷。

## 5. 重量一致性

FACT：本批重跑的 `measure.json` 與先前離線量測（驗收規劃文件 §3 所據的那一份，預設工具列、`deviceScaleFactor` 2）逐欄比對，六個寬度×情境組合的所有量測欄位完全相同（僅本批新增 `fullPageH`、`fullPageOverflowX` 兩欄）。尺寸為 CSS px，不受縮放 1 或 2 影響。

## 6. 未涵蓋與限制

- NOT VERIFIED：Reference 側任何描述；股票 HTML 原檔未取得，Delta 無法判定。如客戶日後提供原檔或截圖，另批補 Reference 與 Delta。
- NOT VERIFIED：Streamlit Cloud、WebView、真機（iOS／Android）的呈現；本批只有本機 Chromium。
- 只涵蓋 `normal`、`missing`（缺台股）兩個合成情境；未涵蓋缺 S&P 500、兩條皆缺、取數失敗、淺色之外的外觀。
- `deviceScaleFactor` 1 的圖檔細字不如 2 銳利；數字以 `measure.json` 為準。
- 合成資料的曲線形狀與數值無任何市場意義，不得據以判讀市場。
- 本檔不評斷優劣、不提出 token 或版面建議；任何視覺改版仍須客戶先裁示（G2／G3／G6）與 UI 草稿先行（`CLAUDE.md` §-1.5.4）。
- 重現路徑依本機而異，未在別台機器驗證（INFERENCE）。
