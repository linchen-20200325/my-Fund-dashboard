# Google OAuth 2.0 設定指引

讓使用者用自己的 Google 帳號直接連線 Google Sheets（取代原 Service Account 路徑）。
一次性 GCP 設定 ~ 5 分鐘，之後使用者只要在 app 內按「用 Google 登入」即可。

## 一次性 GCP 設定

### 1. 啟用 Google Sheets API

開啟 [GCP Console → APIs & Services → Library](https://console.cloud.google.com/apis/library)，
搜尋 `Google Sheets API` 並按「啟用」。同步啟用 `Google Drive API`（讓使用者能列搜尋 Sheet）。

### 2. 設定 OAuth consent screen

[APIs & Services → OAuth consent screen](https://console.cloud.google.com/apis/credentials/consent)：

- User Type: **External**（除非你是 Google Workspace 內部使用）
- App name: 基金戰情室（隨意）
- User support email: 你的 email
- Developer contact: 你的 email
- Scopes: 加入這四個
  - `https://www.googleapis.com/auth/spreadsheets`
  - `https://www.googleapis.com/auth/drive.file`
  - `openid`
  - `https://www.googleapis.com/auth/userinfo.email`
- Test users: 加入自己的 Gmail（External + Testing 階段限制，只有 test users 能登入）

如果是 production，要等 Google 審核（不上架商店則不需審核，但會看到「未驗證 app」警告，按進階繼續即可）。

### 3. 建立 OAuth Client ID

[APIs & Services → Credentials → Create Credentials → OAuth Client ID](https://console.cloud.google.com/apis/credentials)：

- Application type: **Web application**
- Name: Streamlit Web Client
- Authorized JavaScript origins:
  - `https://<your-app>.streamlit.app`（正式環境）
  - `http://localhost:8501`（本地開發，可選）
- Authorized redirect URIs:
  - `https://<your-app>.streamlit.app/`（注意尾巴的 `/`）
  - `http://localhost:8501/`（本地開發，可選）

點「建立」，會跳出 `Your Client ID` / `Your Client Secret` — 複製下來。

### 4. 寫入 Streamlit Secrets

`.streamlit/secrets.toml`（本地）或 Streamlit Cloud App settings → Secrets：

```toml
[google_oauth]
client_id     = "1234567890-xxxxx.apps.googleusercontent.com"
client_secret = "GOCSPX-xxxxxxxxxxxxxxxxxxxx"
redirect_uri  = "https://<your-app>.streamlit.app/"
```

注意：`client_secret` 是機密，不要 commit 到 git。

## 使用者端流程（無需 GCP）

1. 打開 app → Tab3「組合基金管理」→ 「📋 保單管理」expander
2. 按「🔐 用 Google 登入」→ 跳轉到 Google 授權頁
3. 選擇 Google 帳號 + 同意 spreadsheets/drive.file 權限
4. 自動跳回 app，已登入狀態
5. 貼上 Sheet ID（或選「建立新總表」自動建一個）
6. 開始建立保單分頁 + 加入基金 + 記錄交易

## 與既有 Service Account 路徑共存

新 OAuth 路徑與舊 SA 路徑**並存**，使用者可選任一：

- 有 `[google_oauth]` secrets → 顯示「用 Google 登入」按鈕
- 有 `[google_service_account]` secrets → 仍走原 SA 路徑（向後相容）
- 兩者皆有 → 預設 OAuth，可選 SA fallback

## 安全性

- Client Secret 存 Streamlit Secrets（不暴露給使用者）
- 使用者 OAuth tokens（access + refresh）暫存 `st.session_state`，**不寫到 Sheets / Git / 永久儲存**
- 重新整理 / 重啟 app 後使用者需要重新登入（access_token 有 1 小時效，refresh_token 可續期但目前 session_state 結束就失效）
- 後續可選加 cookie 持久化（`streamlit-cookies-controller`），目前刻意不做

## 疑難排解

| 症狀 | 原因 | 解法 |
|------|------|------|
| `redirect_uri_mismatch` | OAuth Client 沒加 streamlit app URL | 步驟 3 補上正確 redirect_uri，尾巴 `/` 要一致 |
| `access_denied` | OAuth consent screen 還在 Testing + 你不是 test user | 步驟 2 把自己加進 test users |
| token 過期看不到資料 | access_token 1 小時自動過期 | 程式碼會嘗試用 refresh_token 自動續，若失敗請重新登入 |
| 「未驗證 app」警告 | OAuth consent screen 還沒過 Google 審核 | Testing 階段正常，按「進階 → 繼續前往」即可 |
