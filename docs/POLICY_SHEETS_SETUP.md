# 保單視圖 — Google Sheets 設定手冊

> 對應檔案：`policy_store.py`、`.streamlit/secrets.toml`
> 對應功能：保單視圖 P1.2（Sheets 儲存層）

本文件說明如何用 **GCP Service Account（OAuth 服務帳號）** 把 Google Sheets 接到儀表板。
**不會**接觸到你的 Google 個人帳密；Service Account 是一個獨立的「機器帳號」，只能讀寫你**主動分享**給它的 Sheet。

---

## 為何不用「輸入帳密下載 Sheet」？

| 風險 | 影響 |
|------|------|
| 把 Google 主帳號密碼存進儀表板 | 一旦 Streamlit Cloud / 本機環境被攻破，**整個** Google 帳號（Gmail / Drive / Photos）連帶失守 |
| 雙重驗證（2FA）會擋下程式登入 | 必須關 2FA → 等於把全帳號安全性降一級 |
| 違反 Google Terms of Service | 風險自負 |

Service Account 把「權限範圍」鎖到「**這張 Sheet**」，是 Google 官方推薦的程式存取方式。

---

## 一次性設定（約 10 分鐘）

### Step 1：建立 GCP 專案

1. 開 <https://console.cloud.google.com/> → 登入你的 Google 帳號
2. 上方下拉選單 → 「**新增專案**」
3. 名稱隨意（例：`my-fund-dashboard`），建立後在右上切到此專案

### Step 2：啟用 Sheets API + Drive API

1. 左側選單 → 「API 和服務 → 程式庫」
2. 搜尋 `Google Sheets API` → 點進去按「**啟用**」
3. 再搜尋 `Google Drive API` → 啟用（讀取分享權限需要）

### Step 3：建立 Service Account

1. 左側選單 → 「IAM 與管理 → 服務帳戶」
2. 上方「**+ 建立服務帳戶**」
3. 名稱：`my-fund-dashboard-bot`（隨意）
4. 角色：可不填（保持空白即可，因權限走 Sheet 共用機制）
5. 完成 → 看到帳號清單，**複製 `client_email`**（形如 `xxx@<project-id>.iam.gserviceaccount.com`）

### Step 4：下載 JSON 金鑰

1. 點進剛建的 Service Account → 上方「**金鑰**」分頁
2. 「新增金鑰 → 建立新金鑰 → JSON」→ 下載得到 `xxx.json`
3. **嚴禁** push 進 git；存到本機安全位置

### Step 5：把 Sheet 共用給 Service Account

1. 新建一張 Google Sheet（例：`保單追蹤表`）
2. 第一個分頁改名為 `Policies`（或保留任意名稱，下方對應改 `worksheet=` 參數）
3. 第 1 列填表頭（**前 8 欄順序必須相同**，第 9 欄為選填）：

   ```
   policy_id | policy_name | fund_url | invest_twd | invest_date | currency | fx_at_buy | notes | policy_tier
   ```

   `policy_tier` 為 P3 新增的選填欄；舊 8 欄表照常運作，新增此欄能啟用「保單級核心/衛星甜甜圈 + 自動配置建議」。

4. 右上「**共用**」→ 把 Step 3 抄下來的 `client_email` 貼進去，權限「編輯者」
5. 從網址列複製 Sheet ID（`https://docs.google.com/spreadsheets/d/【這段】/edit`）

### Step 6：把金鑰塞進 Streamlit secrets

本機開發：編輯 `.streamlit/secrets.toml`（沒有就 copy `.streamlit/secrets.toml.example`）：

```toml
POLICY_SHEET_ID = "你 Step 5 的 Sheet ID"

[google_service_account]
type = "service_account"
project_id = "your-project-id"
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "xxx@your-project-id.iam.gserviceaccount.com"
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "..."
```

> `private_key` 的 `\n` 一定要寫成 `\\n` **或** 用三引號包整段。Streamlit Cloud 介面建議直接貼整段 JSON 內容。

Streamlit Cloud：到 Settings → Secrets，貼上同樣內容即可。

---

## Schema 欄位定義

| 欄位 | 型別 | 必填 | 範例 | 備註 |
|------|------|------|------|------|
| `policy_id` | str | ✅ | `P1` | 保單唯一識別碼（自訂，建議短英數）|
| `policy_name` | str | ✅ | `南山UL01` | 顯示用名稱 |
| `fund_url` | str | ✅ | `TLZF9` 或 MoneyDJ URL | 程式會自動萃取代碼 |
| `invest_twd` | int | ✅ | `1000000` | 該檔基金的台幣投入額；空白視為 0 |
| `invest_date` | str | 選填 | `2024-03-01` | 進場日，顯示用 |
| `currency` | str | 選填 | `USD` / `TWD` | 顯示用 |
| `fx_at_buy` | float | 選填 | `31.5` | 進場匯率，未來算未實現匯損用 |
| `notes` | str | 選填 | `第一年` | 備註 |
| `policy_tier` | str | 選填 (P3) | `core` / `satellite` | 該基金在保單內定位；空白 fallback 為既有基金名啟發。大小寫不分，非法值視為空。|

**(policy_id, fund_url)** 是這張表的主鍵 — 即「同一張保單下不會有兩筆同檔基金的重複列」，但「同檔基金可以在不同保單裡各出現一次」。

**向後相容**：舊 8 欄 Sheet 不需立即加 `policy_tier`；儀表板會自動降級為空字串並使用既有基金名啟發判定核心/衛星。新建 Sheet 建議直接寫 9 欄完整 schema。

---

## 驗證連線是否 OK

```python
import streamlit as st
from policy_store import get_gspread_client, load_policies

client = get_gspread_client(dict(st.secrets["google_service_account"]))
df = load_policies(client, st.secrets["POLICY_SHEET_ID"])
print(df)
```

若拋 `PolicySheetError: 開啟 Sheet/Policies 失敗：...PermissionError...` — 多半是**忘了把 Sheet 共用給 `client_email`**（Step 5）。

---

## 安全注意事項

- ❌ **絕對不要** 把 `xxx.json` 或 `secrets.toml` commit 進 git
- ✅ `.gitignore` 已忽略 `.streamlit/secrets.toml`；確認 `git status` 看不到 `secrets.toml`
- ✅ Service Account 只能存取你**主動共用**的 Sheet — 取消共用即刻撤權
- ✅ 若 JSON 外洩，到 GCP Console → IAM → Service Accounts → 該帳號 → 金鑰，立刻撤銷舊金鑰並建新的

---

## 階段進度

- **P1 ✅**：基本同步 / 8 欄 schema / 保單分組視圖 + fund-level advisor
- **P2 ✅**：`t7_ledgers` 升級為 `(policy_id, fund_code)` 複合鍵 → 跨保單同檔基金可正確分帳
- **P3 ✅**：Schema 新增選填 `policy_tier`（core / satellite）+ 保單級核心衛星 mini 甜甜圈 + `recommend_policy()` 自動配置建議
