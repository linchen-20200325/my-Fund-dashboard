# ⚙️ NAS 中繼站診斷｜隔離式 FAKE Preview（非正式頁面、非正式資料）

- 授權範圍：客戶指示只做「**完全離線、注入假診斷結果**」的獨立可操作預覽。**不是**正式 ⚙️ 頁掛載（`ui_v3/shell/registry.py` 未動）、**不是**即時測試、60 秒冷卻、探測目標、新狀態詞正式化的核准，也**不是** Cloud／真機驗收。
- 啟動：`streamlit run poc/nas_diag_preview/app_nas_diag_preview.py`（在 repo 根目錄執行）。
- 頁頂固定一列「FAKE／測試資料（離線注入，未執行任何真實請求）」（屬 harness）；下拉選單（key `uvp_nas_scenario`）切換 13 個 FAKE 情境：
  ①未設定 ②已設定但尚未測試 ③NAS 成功＋目標 200 ④NAS 失敗＋直連成功（降級）⑤NAS 失敗＋直連也失敗 ⑥代理驗證失敗（407）
  ⑦a 目標 403（NAS 可用）⑦b NAS 出口被 403 封鎖後降級直連成功 ⑧逾時 ⑨TLS／憑證 ⑩名稱解析 ⑪矛盾輸入（無法判定）⑫請求過多（429）。

## 做了什麼

- `ui_v3/viewmodels/nas_diag.py`：輸入 `NasDiagObservation`（只收「已觀測的事實」，**沒有任何原始例外字串欄位**）→ `classify()` → `NasDiagView`。
  六態：未設定／尚未測試／連線成功／連線失敗／已降級直連／無法判定；**NAS 中繼健康度**與**目標網站可用性**兩軸分開判定。
  - NAS 失敗但直連成功 ≠ 成功：state＝已降級直連，NAS 軸＝失敗。
  - 缺值 ≠ 0 ≠ 成功：沒有證據是「尚未測試」或「無法判定」；任何矛盾輸入（例：路徑是 NAS 但 NAS 不可用）→ 無法判定，不猜。
  - `target_label` 只收白名單標籤；含網址分隔、`@`、`user:pass@` 形字串一律拒絕（訊息不回顯值）。
- `ui_v3/viewmodels/nas_diag_wording.py`：**暫行**字樣（`PendingWording`）。已核准字樣重用規則表：`not_configured`（尚未設定）、`undetermined`（無法判定）、`missing`（缺值）；
  其餘（尚未測試、連線成功、連線失敗、已降級直連、各失敗原因的人話說明）全是暫行，畫面有「暫行字樣，尚未核准」提示與虛線底線，**不進規則表**。
- `ui_v3/pages/nas_diag.py`：renderer。降級直連用醒目橫幅「NAS 失敗，改走直連；NAS 並未正常」＋黃色徽章，與本次連線成功不同色也不同詞。
  不顯示 proxy 主機、帳密、完整網址、標頭、例外文字。
- **頁內順序（2026-11-17 UX 收斂，依「ChatGPT UI 設計方向 2026-11-17」；非客戶逐字裁示）**：
  ①NAS 設定狀態＋本次檢查結果（徽章）→ ②並列「NAS 中繼檢查結果」與「目標網站本次回應」兩軸 → ③實際使用路徑、HTTP 結果、檢查時間
  → ④原因與建議（人話）→ ⑤預設收合的單一 `<details>`「詳細技術證據」（不巢狀；摘要列高度 ≥48px）→ 說明。
- **徽章用「符號＋文字」區分六態，不單靠顏色**（neutral 與 grey 兩個 tone token 同色）：
  ⛔ 尚未設定（規則表字樣）／◌ 尚未測試／✓ 本次連線成功／✕ 本次連線失敗／▲ 已降級直連／⬜ 無法判定（規則表字樣）。
  成功與失敗一律用「本次」措辭，不暗示 NAS 永久健康。「尚未設定」徽章在本預覽用中性灰（NAS 未設定不算故障）；規則表 `not_configured` 的 tone 與字樣不動。
- **「立即測試連線」目前不渲染任何可操作的測試按鈕**（也沒有說明字樣）。預留位置：未來經客戶核准後，才會出現在 ③ 路徑／HTTP／時間區塊之後、④ 原因與建議之前；
  屆時須另行核准探測目標、頻率、冷卻、授權與掛載位置。renderer 內唯一的可互動元素是那個預設收合的 `<details>`。

## 失敗分類與 `shared/backoff_policy.py`

退避政策有六種失敗類型（unreachable／server_error／blocked／rate_limited／not_found／proxy_auth），其中 unreachable 把逾時、名稱解析、TLS、NAS 無法連線全歸一類，
診斷頁要區分它們，所以 VM 自己有一份分類（含 `BACKOFF_KIND_TO_CLASSES` 對映表）。`tests/ui_v3/test_ui_v3_nas_diag_viewmodel.py` 同時 import 兩邊並掃 `infra/proxy.py` 的 `_fail_kind` 指派，
分類名稱漂移會紅。VM 本身不 import 任何舊樹模組。

## NOT VERIFIED／已知落差（原樣呈現）

- 全部資料是人造的；**沒有**驗證 `infra/proxy.py` 真的能產出這些 observation 欄位（`nas_reachable`、`route_used`、`nas_error_class` 是本預覽的約定，不是現有函式的回傳；
  現有 `fetch_url` 只回 response 或 `None`，`pop_last_fail_kind()` 只有六種退避分類）。要接真實檢查需另行核准（探測目標、頻率、冷卻、掛載位置）。
- `nas_error_class` 是本預覽**新增**的選填欄位（NAS 這一段為何失敗），規格原欄位清單沒有；理由：只用一個 `error_class` 分不出「NAS 為什麼失敗」與「目標為什麼取不到」。
- 「尚未設定」重用已核准字樣 `⛔ 尚未設定`；規則表 `not_configured` 的 tone 是紅色，而 UI 設計方向要求「中性灰、不算故障」——兩者衝突。本預覽的徽章用灰色（僅預覽 CSS，規則表不動），字樣仍帶規則表的 ⛔ 符號；規則表 tone 與預覽灰色孰是，待客戶裁示，畫面內已用暫行說明句註明「這不是故障」。
- 新狀態詞（尚未測試、連線成功、連線失敗、已降級直連）、人話原因、探測目標（本預覽只有白名單標籤 `MoneyDJ`）、測試頻率／冷卻、正式掛載位置：**全部待客戶裁示**。
- 瀏覽器守衛只在本機 Chromium 驗；真實 Streamlit Cloud 與真機未驗。selectbox 屬 harness，高度為 Streamlit 預設（40px），未達 48px 觸控下限；renderer 本身沒有任何可互動元素。
- 斷網測試只攔 `socket.socket.connect` 與 `socket.create_connection`；讀憑證測試只攔 `os.environ.get`。措辭為「在上述攔截範圍內未偵測到」，不是「已證明不連網／不讀憑證」。
- renderer 經 `ui_v3.shell.nav`（取斷點常數）會間接載入 `ui_v3.shell.registry`；入口檔本身不直接 import 它（靜態守衛鎖定）。

## 追加揭露（QA 後補）

- **瀏覽器守衛屬 slow lane**：CI 的 slow lane 標了 `continue-on-error`，紅了不會擋 merge；它是證據，不是阻擋閘門。fast lane（AST、HTML 字串、CSS 規則、輸入乘積、AppTest）才會擋。
- **neutral 與 grey 兩個 tone token 同色**：「本次連線成功」「尚未測試」「無法判定」「尚未設定」徽章底色相同，**靠符號＋文字區分**；只有降級直連（黃）與連線失敗（紅）有不同底色。
- **語意改動（2026-11-17）**：`route_used=nas` 時的逾時／名稱解析／TLS **沒有證據區分是 NAS 側或目標側**，兩軸皆「⬜ 無法判定」（reason＝`no_side_evidence`），
  文字說明「缺少區分 NAS 這一段或目標網站這一段的證據」；失敗分類另存 `unattributed_cause_key`，原因區標「NAS 或目標網站（無法區分）」，不歸給任何一側。
  原「判 NAS 軸正常」的預覽約定已移除。
  **目前採信標準**：`route=nas` 且 `nas_reachable=True`、最終結果是目標側 HTTP 回應（含 403／429／其他）時採信 NAS 軸 ok——已有「經由 NAS 收到目標網站回應」的證據；
  逾時／名稱解析／TLS 沒收到任何 HTTP 回應，才無法區分兩側。經 NAS 的 403／429／其他是否也改無法判定，待裁示（BL-0550 Pending (7)）。
  fallback／none 路徑的逾時／名稱解析／TLS 是直連（無 NAS 參與）的失敗，歸目標側；NAS 這一段的失敗另依 `nas_error_class` 歸 NAS 側，原因字樣不再說「無法分辨」。降級後直連才失敗（沒有 NAS 參與的路徑）仍判目標軸失敗；403／429／其他 + route=nas 仍判 NAS 軸正常、目標軸失敗（本次未改，見回報）。
- **`nas_reachable` 的意義**：NAS 出口是否可用於取得目標（可達、驗證通過、出口未被目標封鎖）。因此 ⑦b（NAS 出口被目標 403 封鎖後降級直連）是 `nas_reachable=False`＋`nas_error_class=forbidden_403`，文案為「NAS 出口被目標網站封鎖」；
  ⑦a（目標對經由 NAS 的請求回 403、沒有降級）NAS 出口仍視為可用、目標軸失敗。403／429 沒有狀態碼時以分類為準（允許，狀態碼顯示缺值）；407 允許沒有狀態碼。
- **目標軸尚未測試（例：407）時目標卡不顯示狀態碼與延遲**：那是 proxy 回的，歸 NAS 這一段。
- **`not_configured` 可帶直連結果**：未設定 NAS 時仍可顯示直連的目標軸結果，這與規則表 `not_configured` 的原義（「設定沒設、沒有執行取數」）有落差；若客戶認為未設定時不該顯示任何取數結果，需另行裁示。
- **selectbox（harness，約 40px）是手機審核時唯一的操作面**；renderer 沒有任何可互動元素，也沒有連結。頁標題以 `anchor=False` 關閉錨點連結，卡片標題不用 h1～h6（Streamlit 會替它們自動加錨點連結）；瀏覽器守衛掃描整個主區（含頁標題）的連結數必須為 0。
- `target_label` 為必填（沒有預設網站），驗證一律 fullmatch（結尾換行也拒絕）；`NasDiagView` 建構時同樣驗證標籤、狀態碼、延遲、檢查時間，renderer 所有插值再 escape 一次（縱深防禦）。
