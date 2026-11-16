# 💼 我的資產｜隔離式 FAKE Preview（非正式頁面、非正式資料）

- 授權：客戶已授權本批（A00 來源狀態、A10 降級卡、A20 固定四格；僅假資料）。**不是**我的資產頁的正式施工授權，也**不是** Cloud／真機驗收。
- 啟動：`streamlit run poc/assets_fixture_preview/app_assets_preview.py`（在 repo 根目錄執行）。
- 頁頂固定一列「FAKE／測試資料（非真實持倉，不代表任何實際資料）」；下拉選單切換七個 FAKE 情境。
  1. 完整（新臺幣＋美元）：fake 輸入含 TWD、USD 兩列；**畫面不顯示持倉列，TWD／USD 只存在輸入與 VM 層，使用者目前不能從畫面查看逐檔原幣持倉（待 A50 授權）**；畫面不做匯率換算、不合計。
  2. 來源完整但沒有持倉列。
  3. 市值基準未開放（載入端不讀持倉）。
  4. 局部缺漏：**現行 view model 沒有逐檔淨值／配息／1 年報酬的概念**，因此以「略過分頁／略過列」代表局部缺漏，不是淨值或配息缺漏。
  5. 未選定來源。
  6. 讀取失敗（失敗代碼不上畫面）。
  7. 略過證據未提供（沒有列；刻意不帶列，避免重現已登記的落差，見下）。

## 這一批做了什麼、沒做什麼

- 做了：A00 單一來源狀態容器、A10 降級卡（`◇ 資料未備` 純文字、每個原因一行、基準一列、限制一列）、A20 固定四格（恆為 `◇ 資料未備`，沒有任何正式值）。
- **沒做**：A30～A60（偏離、事件、完整持倉、設定、證據）一律沒有；沒有圖；沒有任何金額、百分比、合計、配置比例、風險判定或建議；沒有匯率換算或跨幣別合計。
- **持倉入口沒有畫**：A10 的「查看持倉明細」入口目前沒有合法的導向目標（持倉區尚未實作），所以即使 view model 帶有入口也不畫（有測試鎖定）。
- A20 四格標籤（總資產、總損益、報酬、配息）取自程式現行標籤，**暫行、未核准**，畫面上有「暫行」說明；虛線底線的字樣都是暫時字樣。
- 資料全部是 FAKE（`assets_fake_inputs.py`，與測試支援檔同形，有 drift 測試）；設計上不取數、不寫檔，以下為測試實際攔截範圍（見 `tests/poc_assets_preview/test_assets_preview_apptest.py`），措辭為「在上述攔截範圍內未偵測到」，不是「已證明不連網／不讀憑證」：
  - 斷網測試只攔 `socket.socket.connect` 與 `socket.create_connection`（不含 `connect_ex`、`getaddrinfo`、asyncio `sock_connect`）。
  - 讀憑證測試只攔 `os.environ.get`（含經它的 `os.getenv`；不含 `os.environ[...]`、`in`、迭代）；`st.secrets` 只靠入口檔 AST 掃字串。
  - 環境變數 spy 以 regex `KEY|TOKEN|SECRET|CRED` 比對名稱，可能抓到 Streamlit 自己讀的環境變數而誤紅（誤紅風險，未驗證）。

## 已知落差（原樣呈現，不在本批處置）

- `blocked_basis_state_without_value`：市值基準未開放時，A10 的基準狀態可能是「已設定」但沒有值，畫面上顯示 `◇ 資料未備`。
- `limit_no_fx_conversion_always_present`：「目前未做匯率換算」的限制列在所有情境都出現（含無持倉列的情境）。
- `undetermined_with_rows_claims_viewable_holdings`：證據不足但有列時，原因會出現「已有持倉資料可查看」。本 Preview 的第七個情境刻意不帶列，所以畫面上看不到這個落差；它仍存在於 view model。

- `limit_no_fx_conversion` 字樣「各檔原幣數值不合計」在未讀取（市值基準）、未選定來源、讀取失敗、來源完整但沒有列的情境也會出現；「各檔原幣數值」可能暗示有逐檔持倉。這是字樣問題，待客戶裁示，本 PR 不改。

## 其他限制

- 本 Preview 須相容 Python 3.11（CI 版本）：不得使用 3.12 才有的語法（例如 f-string 內重用同種引號）。
- renderer 會 import `ui_v3.shell.registry`（取 `IA_PAGES` 的頁名）與 `ui_v3.shell.nav`，所以隔離入口會「間接」載入 registry（只讀、registry 未被修改）；入口的靜態白名單禁止的是入口檔**直接** import。

- 驗證範圍：AppTest 與本機 Chromium 的版面守衛；真實 Streamlit Cloud 與真機（390px 實機高度）**未驗**。
- 首屏元素點數（A00 一個、A20 四格各一個＝5）採 A10 文字不計入；若 A10 原因句與入口也計入，數字會不同，該口徑屬待 UI Review，本 Preview 只量測、不下結論。
- 本目錄不得有 `pages/` 子目錄、不得做成可 import 的 package；不得被正式路徑引用（有測試鎖定）。
