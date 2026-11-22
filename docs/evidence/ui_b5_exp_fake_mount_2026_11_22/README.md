# 🔍 找基金本地 FAKE 頁（Gate-M 方案 2a）— 390／1280 Chromium 證據

- 授權：客戶 #1296 comment 7073251388（選方案 B）；總管 #1296 comment 7073385776（核可 2a 唯一狹窄例外）。
- 這是**本地 Preview 的 FAKE 頁**：資料來自 `ui_v3/fixtures/exp_lookup_fake.py`，🌍 為 `market_stubs` 合成 fixture。
  **不是 Cloud、不是真機、不是真來源；FAKE 畫面 ≠ 線上可用或真取數可用。**
- 產生方式：本機 Chromium（`/opt/pw-browsers` 預裝版）＋ Streamlit 子行程，`tests/ui_v3/test_ui_v3_exp_fake_mount_browser.py` 的同一組腳本與選擇器；
  viewport 390×844（手機頁首五格）與 1280×844（桌機側欄），deviceScaleFactor 2。
- 檔案：`exp_idle_*`（尚未查詢）、`exp_result_*`（`FAKE-OK01`）、`exp_failed_*`（`FAKE-FAIL1`）；量測值見 `measure.json`
  （無橫向溢出、輸入框與送出鈕高度皆 48px、卡級 FAKE 標籤恆顯、🔍 頁沒有 🌍 Status Bar）。
