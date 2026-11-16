# 💼 我的資產｜隔離式 FAKE Preview（非正式頁面、非正式資料）

- 授權：客戶已授權本批（A00 來源狀態、A10 降級卡、A20 固定四格；2026-11-16 起另含 A50 單一容器四欄唯讀持倉，見 `DEC-2026-11-16-01`；僅假資料）。**不是**我的資產頁的正式施工授權，也**不是** T6、正式資料契約、正式 UI 掛載或 FX Gate 的核准，也**不是** Cloud／真機驗收。
- 啟動：`streamlit run poc/assets_fixture_preview/app_assets_preview.py`（在 repo 根目錄執行）。
- 頁頂固定一列「FAKE／測試資料（非真實持倉，不代表任何實際資料）」；下拉選單切換九個 FAKE 情境（①～⑦沿用，⑧⑨為 A50 新增）。
  1. 完整（新臺幣＋美元）：fake 輸入含 TWD、USD 兩列；A50 容器內以逐檔原值顯示幣別與單位數（預設收合）；畫面不做匯率換算、不合計。這只是隔離 Preview 內的 fake 呈現，**不代表目前正式畫面已顯示逐檔原幣**。
  2. 來源完整但沒有持倉列。
  3. 市值基準未開放（載入端不讀持倉）。
  4. 局部缺漏：**現行 view model 沒有逐檔淨值／配息／1 年報酬的概念**，因此以「略過分頁／略過列」代表局部缺漏，不是淨值或配息缺漏。
  5. 未選定來源。
  6. 讀取失敗（失敗代碼不上畫面）。
  7. 略過證據未提供（沒有列；刻意不帶列，避免重現已登記的落差，見下）。
  8. 多保單同基金：同 fund_code、不同 policy_id ＝ 兩列、兩個 holding_id（不合併）。
  9. 大量列（50 列）：第 1 列基金名稱含 `<>&"` 與 `<script>`，測 escape 與容器內捲動。

## 這一批做了什麼、沒做什麼

- 做了：A00 單一來源狀態容器、A10 降級卡（`◇ 資料未備` 純文字、每個原因一行、基準一列、限制一列）、A20 固定四格（恆為 `◇ 資料未備`，沒有任何正式值）、**A50 單一展開容器**（見下）。
- **沒做**：A30、A40、A51、A52、A60 一律沒有；沒有圖；沒有任何金額、百分比、合計、配置比例、風險判定或建議；沒有匯率換算或跨幣別合計。
- **持倉入口沒有畫**：A10 的「查看持倉明細」入口暫不畫無效連結（DEC-2026-11-16-01）；正式入口及焦點／定位另經技術 Gate。即使 view model 帶有入口也不畫（有測試鎖定）。

## A50：單一展開容器、四欄唯讀持倉（DEC-2026-11-16-01；全部暫行）

- 單一 HTML `<details>`／`<summary>`（零 rerun）。逐檔**不**再展開、不巢狀、不放進其他展開容器（A51 不在本批）。
- **預設收合——暫行**（DEC「待確認」(c)：是否沿用 `DEC-2026-11-09-03` S1-2 的「手機收合／桌面條件式展開」未裁，故先固定收合，避免與既有裁示形成雙軌）。
- 每列四欄：基金名稱、基金代號、幣別、單位數（`fund_name`／`fund_code`／`ccy`／`units_shares`）。欄名與容器標題是 `PendingWording`（畫面有「暫行字樣，尚未核准」提示），不進已核准字樣表。
- 缺值／不可用一律 `◇ 資料未備`（走規則表），**不顯示 0 或空白**。`units_shares` 以原值字串輸出（不做千分位或換算）——**顯示格式未裁，暫行**。文字內的連續空白（含換行）會摺成單一空格，以免空行截斷 Markdown 的 HTML 區塊。
- 不顯示：金額、台幣總額、占比、報酬、配息、建議、`holding_id`、`cost_*`；A50 區沒有合計或換算。限制行為客戶指定字樣「此預覽不提供匯率換算或跨幣別合計」（`PendingWording`，出處為 DEC 要點轉述；是否定稿待客戶確認）。
- 只有有列（`a50.state == rows`）才畫容器；`status_only`（未選 Active／讀取失敗／零有效列／市值基準 blocked／無法判定且無列）只畫一列引用 A00 狀態的文字，不畫空表、不寫「持倉 0」。
- 身份鍵 `holding_id`：VM 與 adapter 必填驗證（非空字串、無前後空白、唯一；違反 → `ValueError`，訊息不含資料值），不上畫面、不進 DOM（列以 ordinal 做 `data-row`）。與 `ui_v2/hld/logic.py::_check_holding_ids` 有差異測試（`tests/ui_v3/test_ui_v3_assets_holding_id_identity.py`）。已登記的範圍差異：問題碼提早回傳的路徑（未選 Active／讀取失敗）不看列，所以不驗身份鍵。
- A50 不標 `data-first-screen`，390px 首屏仍恰為 5 個標記。
- A20 四格標籤（總資產、總損益、報酬、配息）取自程式現行標籤，**暫行、未核准**，畫面上有「暫行」說明；虛線底線的字樣都是暫時字樣。
- 資料全部是 FAKE（`assets_fake_inputs.py`，與測試支援檔同形，有 drift 測試）；設計上不取數、不寫檔，以下為測試實際攔截範圍（見 `tests/poc_assets_preview/test_assets_preview_apptest.py`），措辭為「在上述攔截範圍內未偵測到」，不是「已證明不連網／不讀憑證」：
  - 斷網測試只攔 `socket.socket.connect` 與 `socket.create_connection`（不含 `connect_ex`、`getaddrinfo`、asyncio `sock_connect`）。
  - 讀憑證測試只攔 `os.environ.get`（含經它的 `os.getenv`；不含 `os.environ[...]`、`in`、迭代）；`st.secrets` 只靠入口檔 AST 掃字串。
  - 環境變數 spy 以 regex `KEY|TOKEN|SECRET|CRED` 比對名稱，可能抓到 Streamlit 自己讀的環境變數而誤紅（誤紅風險，未驗證）。

## 已知落差（原樣呈現，不在本批處置）

- `blocked_basis_state_without_value`：市值基準未開放時，A10 的基準狀態可能是「已設定」但沒有值，畫面上顯示 `◇ 資料未備`。
- `limit_no_fx_conversion_always_present`：限制列（現為客戶指定字樣「此預覽不提供匯率換算或跨幣別合計」）在所有情境都出現（含無持倉列的情境）。
- `undetermined_with_rows_claims_viewable_holdings`：證據不足但有列時，原因會出現「已有持倉資料可查看」。本 Preview 的第七個情境刻意不帶列，所以畫面上看不到這個落差；它仍存在於 view model。

- 舊限制行字樣「目前未做匯率換算，各檔原幣數值不合計」可能暗示有逐檔持倉，已依客戶 `DEC-2026-11-16-01` 改為「此預覽不提供匯率換算或跨幣別合計」（暫行字樣）。

## 其他限制

- 本 Preview 須相容 Python 3.11（CI 版本）：不得使用 3.12 才有的語法（例如 f-string 內重用同種引號）。
- renderer 會 import `ui_v3.shell.registry`（取 `IA_PAGES` 的頁名）與 `ui_v3.shell.nav`，所以隔離入口會「間接」載入 registry（只讀、registry 未被修改）；入口的靜態白名單禁止的是入口檔**直接** import。

- 驗證範圍：AppTest 與本機 Chromium 的版面守衛；真實 Streamlit Cloud 與真機（390px 實機高度）**未驗**。
- 首屏元素點數（A00 一個、A20 四格各一個＝5）採 A10 文字不計入（卡 1 方案 A）；若 A10 原因句與入口也計入，數字會不同，該口徑屬待 UI Review，本 Preview 只量測、不下結論（`tests/poc_assets_preview/test_assets_preview_browser.py` 同時回報另外的口徑數字，不作斷言）。A50 不計入首屏。
- 本目錄不得有 `pages/` 子目錄、不得做成可 import 的 package；不得被正式路徑引用（有測試鎖定）。

## 實測（A50 `<details>`；本機 Chromium、Python 3.11、Streamlit 版本以 `requirements.txt` 宣告為準；2026-11-16）

以下由 `tests/poc_assets_preview/test_assets_preview_browser.py`（slow lane）實測，**只代表本機 Chromium 與 headless 條件**：

- `<details>`／`<summary>` 經 `st.markdown(unsafe_allow_html=True)` 後**屬性與結構保留**，頁面恰一個 `<details>`、一個 `<summary>`，無巢狀、不在其他 `<details>` 內；預設 `open=false`。
- 點擊 summary 可開合；開合前後 websocket **client→server 訊息數不變**（以 `page.on("websocket")` 的 `framesent` 計數；正控：切換情境會讓計數增加，所以「0」不是空綠）。
- 鍵盤：summary 聚焦後 Enter、Space 各可開合，同樣不產生 client→server 訊息。
- 390×844、768×844、1280×800：收合與展開狀態皆無水平溢出；summary 高度 48px（`ui_v3.shell.nav.TOUCH_MIN_PX`），中心點未被其他元素蓋住。
- 50 列：容器 `max-height:70vh` 內垂直捲動，捲到底最後一列完整可見、不截斷；整頁無水平溢出。
- 特殊字元：基金名稱的 `<b>`、`&`、引號、`<script>` 以文字顯示，DOM 中沒有被解析出的 `b`／`script` 元素。`holding_id`／`policy_id` 不進 DOM（因此改以基金名稱測 escape）。
- 變異驗證：過寬列、縮小 summary、第二個 `<details>` 三條各自獨立注入，判定函式都各自報紅（在記憶體現編，不寫檔）。

**NOT VERIFIED（未驗，不得當成已驗）**：真實 Streamlit Cloud、真機（390px 實機高度、iOS／Android 觸控與瀏覽器行為）、非 Chromium 瀏覽器、螢幕閱讀器朗讀 `<details>` 的行為、深色模式下的對比；DEC 待確認 (d)「`<details>` 是否算巢狀展開」仍待客戶裁示（本實作是單層、不巢狀）。

## 已知限制（如實揭露，由客戶決定是否處置）

- **值不是逐字原值**：A50 文字值用 `str.split()` 摺疊空白，會把 U+3000（全形空格）、NBSP 等也摺成 ASCII 空格並修剪頭尾，所以畫面上的基金名稱等不一定與來源逐字相同（有單元測試鎖現況）。
- **暫行提示在容器內**：`a50_labels_note`（「欄名與單位數顯示為暫行字樣，尚未核准」）位於 `<details>` 內，預設收合時看不到（A20 的暫行提示在首屏外區仍可見）。登記為已知限制，是否移出由客戶決定；本批不移動。
- **早期回傳路徑不驗身份鍵**：登記項 `early_return_skips_row_and_coverage_validation` 的範圍包含 `holding_id`——問題碼 `no_active_source`／`holding_read_failed` 提早回傳時不看列，所以不驗 `holding_id`（ui_v2 一律先驗）。
