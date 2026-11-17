# ⚙️ NAS 中繼站診斷｜隔離式 FAKE Preview（非正式頁面、非正式資料）

- 授權範圍：客戶指示只做「**完全離線、注入假診斷結果**」的獨立可操作預覽。**不是**正式 ⚙️ 頁掛載（`ui_v3/shell/registry.py` 未動）、**不是**即時測試、60 秒冷卻、探測目標、新狀態詞正式化的核准，也**不是** Cloud／真機驗收。
- 啟動：`streamlit run poc/nas_diag_preview/app_nas_diag_preview.py`（在 repo 根目錄執行）。
- 頁頂固定一列「FAKE／測試資料（離線注入，未執行任何真實請求）」（屬 harness）；下拉選單（key `uvp_nas_scenario`）切換 13 個 FAKE 情境：
  ①未設定 ②已設定但尚未測試 ③NAS 成功＋目標 200 ④NAS 失敗＋直連成功（降級）⑤NAS 失敗＋直連也失敗 ⑥代理驗證失敗（407）
  ⑦a 目標 403（NAS 可用）⑦b NAS 路徑 403 後降級直連成功 ⑧逾時 ⑨TLS／憑證 ⑩名稱解析 ⑪矛盾輸入（無法判定）⑫請求過多（429）。

## 做了什麼

- `ui_v3/viewmodels/nas_diag.py`：輸入 `NasDiagObservation`（只收「已觀測的事實」，**沒有任何原始例外字串欄位**）→ `classify()` → `NasDiagView`。
  六態：未設定／尚未測試／連線成功／連線失敗／已降級直連／無法判定；**NAS 中繼健康度**與**目標網站可用性**兩軸分開判定。
  - NAS 失敗但直連成功 ≠ 成功：state＝已降級直連，NAS 軸＝失敗。
  - 缺值 ≠ 0 ≠ 成功：沒有證據是「尚未測試」或「無法判定」；任何矛盾輸入（例：路徑是 NAS 但 NAS 不可用）→ 無法判定，不猜。
  - `target_label` 只收白名單標籤；含網址分隔、`@`、`user:pass@` 形字串一律拒絕（訊息不回顯值）。
- `ui_v3/viewmodels/nas_diag_wording.py`：**暫行**字樣（`PendingWording`）。已核准字樣重用規則表：`not_configured`（尚未設定）、`undetermined`（無法判定）、`missing`（缺值）；
  其餘（尚未測試、連線成功、連線失敗、已降級直連、各失敗原因的人話說明）全是暫行，畫面有「暫行字樣，尚未核准」提示與虛線底線，**不進規則表**。
- `ui_v3/pages/nas_diag.py`：renderer。降級直連用醒目橫幅「NAS 失敗，改走直連；NAS 並未正常」＋黃色徽章，與連線成功不同色也不同詞。
  不顯示 proxy 主機、帳密、完整網址、標頭、例外文字。
- 「立即測試連線」：**沒有按鈕、沒有連結**，只放一段說明「即時測試尚未核准，本預覽為離線注入結果」。

## 失敗分類與 `shared/backoff_policy.py`

退避政策有六種失敗類型（unreachable／server_error／blocked／rate_limited／not_found／proxy_auth），其中 unreachable 把逾時、名稱解析、TLS、NAS 無法連線全歸一類，
診斷頁要區分它們，所以 VM 自己有一份分類（含 `BACKOFF_KIND_TO_CLASSES` 對映表）。`tests/ui_v3/test_ui_v3_nas_diag_viewmodel.py` 同時 import 兩邊並掃 `infra/proxy.py` 的 `_fail_kind` 指派，
分類名稱漂移會紅。VM 本身不 import 任何舊樹模組。

## NOT VERIFIED／已知落差（原樣呈現）

- 全部資料是人造的；**沒有**驗證 `infra/proxy.py` 真的能產出這些 observation 欄位（`nas_reachable`、`route_used`、`nas_error_class` 是本預覽的約定，不是現有函式的回傳；
  現有 `fetch_url` 只回 response 或 `None`，`pop_last_fail_kind()` 只有六種退避分類）。要接真實檢查需另行核准（探測目標、頻率、冷卻、掛載位置）。
- `nas_error_class` 是本預覽**新增**的選填欄位（NAS 這一段為何失敗），規格原欄位清單沒有；理由：只用一個 `error_class` 分不出「NAS 為什麼失敗」與「目標為什麼取不到」。
- 「尚未設定」直接重用已核准字樣 `⛔ 尚未設定`（紅色 tone）。舊畫面把未設定 NAS 視為正常降級（非故障）；紅色是否過重待客戶裁示，畫面內已用暫行說明句註明「這不是故障」。
- 新狀態詞（尚未測試、連線成功、連線失敗、已降級直連）、人話原因、探測目標（本預覽只有白名單標籤 `MoneyDJ`）、測試頻率／冷卻、正式掛載位置：**全部待客戶裁示**。
- 瀏覽器守衛只在本機 Chromium 驗；真實 Streamlit Cloud 與真機未驗。selectbox 屬 harness，高度為 Streamlit 預設（40px），未達 48px 觸控下限；renderer 本身沒有任何可互動元素。
- 斷網測試只攔 `socket.socket.connect` 與 `socket.create_connection`；讀憑證測試只攔 `os.environ.get`。措辭為「在上述攔截範圍內未偵測到」，不是「已證明不連網／不讀憑證」。
- renderer 經 `ui_v3.shell.nav`（取斷點常數）會間接載入 `ui_v3.shell.registry`；入口檔本身不直接 import 它（靜態守衛鎖定）。
