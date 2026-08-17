# 每日 NAV 自動累積(NAS / 本機 cron)— 設定指南（v19.461）

`scripts/accumulate_nav_tw.py`:不靠你開 App,由**台灣 IP 端(NAS 或本機)**每天自動抓一次
最新淨值,寫進 Google Sheet 的 `nav_history` 分頁。時間久了自然累積出完整歷史序列,解鎖
長期報酬 / 3Y / 5Y / Sortino / 低基期判斷 —— 也就是修掉「淨值**無法自動更新**」這件事。

> **為什麼一定要在台灣 IP 跑?**
> 境外/保單基金的歷史 NAV 從**美國 IP**(GitHub Actions)幾乎全抓不到(來源擋境外 IP)。
> 台灣端(NAS/本機)裝完整依賴後,直接走 App 已驗證的抓取鏈,抓得到「當日最新淨值」。
>
> **和 GitHub Actions 的 `fetch_nav_cache.py` 差在哪?**
> 那支跑在美國 IP、只寫**本機 `cache/`**(容器重啟就沒了),**不寫雲端 Google Sheet**。
> 所以光靠 GitHub 排程,你的雲端 `nav_history` 不會成長 —— 這份文件講的 NAS cron 才會。

---

## A. 準備 Google 服務帳戶(Service Account)+ Sheet 密鑰(做一次,約 10 分鐘)

雲端寫入用的是 **Service Account(服務帳戶)**,不是你個人 Google 登入(那是 App 內 OAuth 用的)。

1. 開 **Google Cloud Console**(<https://console.cloud.google.com>)→ 建一個 Project(或用現成的)。
2. 左側 **APIs & Services → Library** → 搜尋 **Google Drive API** → **啟用**
   (`gspread` 開表走 Drive API;沒啟用會開表失敗)。順手把 **Google Sheets API** 也啟用。
3. **APIs & Services → Credentials → Create Credentials → Service account** → 取個名(如 `nav-cron`)→ 建立。
4. 進該服務帳戶 → **Keys → Add key → Create new key → JSON** → 下載那個 **JSON 檔**。
   - 這個 JSON**就是** `google_service_account` 的內容,裡面有一欄 `client_email`
     (長得像 `nav-cron@xxxx.iam.gserviceaccount.com`)。**整份 JSON 都要**,不是只取某一欄。
5. **把 Sheet 分享給這個服務帳戶**:打開你那本 Google Sheet(政策 / 選股池 / `nav_history` **同一本**)
   → 右上「共用」→ 把上面那個 `client_email` 加為 **編輯者**。
   - ⚠️ 沒做這步 = 服務帳戶看不到表 → 寫入會報「找不到或無權限」。
6. 記下這本 Sheet 的 **ID**(網址 `docs.google.com/spreadsheets/d/`**`<這段就是 ID>`**`/edit`),
   這就是 `macro_weights_sheet_id`。

> 開表失敗時程式會直接告訴你缺哪一項(見 §D),照著補即可。三個要件:
> **(1) 服務帳戶信箱已加進 Sheet 的「共用 → 編輯者」;(2) sheet_id 正確;(3) 已啟用 Google Drive API。**

---

## B. NAS / 本機環境設定(做一次)

前置:**台灣 IP**(直連即可;有設 `PROXY_URL` 也相容)、`pip install -r requirements.txt`
(需完整依賴;`streamlit` 只是被 import,**不會啟動**網頁)。

### 環境變數(2 個)

程式讀密鑰的順序是 **Streamlit `st.secrets` → 環境變數**(`infra/config.py::get_secret`)。
NAS/cron 沒有 Streamlit,所以走**環境變數**,且 `google_service_account` 要放**完整 JSON 字串**:

```bash
export google_service_account='{"type":"service_account","project_id":"...","client_email":"nav-cron@xxxx.iam.gserviceaccount.com","private_key":"-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n", ...}'
export macro_weights_sheet_id='<你的 Google Sheet ID>'
```

> - 用**單引號**包整份 JSON,裡面的 `\n`(私鑰換行)原樣保留,不要自己改成真換行。
> - 這兩個變數若你已經在跑 `weekly_switch_notify.py`,**同一組沿用即可**(同一本 Sheet)。
> - 放 systemd/cron 時,建議寫進一個只有你能讀的檔(如 `chmod 600 ~/.nav_cron.env`)再 `source`,
>   別把私鑰貼進版本控制。

### 先驗證密鑰有沒有讀到(不會寫入任何資料)

```bash
cd /path/to/my-Fund-dashboard
python -c "from services.nav_history_gs import status; print(status())"
```

- 看到 `{'enabled': True, 'missing': [], 'diag': {'google_service_account': 'ok', ...}}` = 密鑰 OK。
- `enabled: False` 時看 `diag`(見 §D 對照表)照著修。

### 再手動跑一次(會真的抓 + 寫入,但 `(code,date)` 冪等,同日重跑不會灌水)

```bash
cd /path/to/my-Fund-dashboard
python scripts/accumulate_nav_tw.py
```

看到 `summary:total=… funds_ok=… written=… dup=…` 就是通了。`funds_ok` > 0 代表有抓到並寫入。

> **要抓哪些基金?** 程式自動用 `fetch_nav_cache._discover_fund_codes()` 的清單
> (內建 baseline ∪ 本機 cache ∪ 你的 Google Sheet 持倉),不用手動列。
> 真的載不到清單時,才退而用環境變數 `NAV_CODES="ACTI71,ALZF9,…"`(逗號分隔)。

---

## C. 排程(每天傍晚,基金 NAV 多為 T+1 傍晚才更新)

台灣時間平日傍晚跑一次即可(週末沒有新淨值,不用跑):

```cron
30 18 * * 1-5  cd /path/to/my-Fund-dashboard && python scripts/accumulate_nav_tw.py >> /var/log/nav_accumulate.log 2>&1
```

- `30 18 * * 1-5` = 週一到週五 18:30。請確認 **NAS 的時區是台灣時間(UTC+8)**;若 NAS 走 UTC,改成 `30 10 * * 1-5`。
- 把 §B 的 `export` 放進 cron 環境(或在指令前 `source ~/.nav_cron.env &&`),否則 cron 讀不到密鑰。
- Synology NAS 可用「控制台 → 任務排程 → 建立 → 使用者定義的指令碼」,貼上同一行(記得先 `source` 密鑰檔)。

---

## D. 行為與退出碼(§1 Fail-Loud,方便你在 NAS log 一眼看狀態)

| 情況 | 行為 | 退出碼 |
|---|---|---|
| 缺密鑰(`google_service_account` / `macro_weights_sheet_id`) | log 印出缺哪個 + 中止,**不靜默** | `2` |
| 抓不到任何基金代碼清單 | log + 中止 | `2` |
| 全部基金都抓失敗(網路 / 來源改版) | log + 中止 | `1` |
| 單檔抓失敗 | 顯式 skip + 計數,其餘照跑(**不偽造**) | — |
| 正常完成 | 印 summary,寫入 `nav_history`(來源標記 `nas_cron`) | `0` |

`status()` 的 `diag` 診斷模式(§B 驗證時對照):

| `diag['google_service_account']` | 意思 | 怎麼修 |
|---|---|---|
| `ok` | 讀到且是合法 SA JSON | ✅ |
| `absent` | 環境變數根本沒讀到 | `export` 沒生效 / cron 沒帶到環境變數 |
| `unparseable` | 有值但不是合法 JSON | 多半引號貼壞、私鑰 `\n` 被改成真換行 |
| `no_client_email` | 是 JSON 但缺 `client_email` | 下載的不是服務帳戶金鑰,重下 §A 步驟 4 的 JSON |

---

## E. 確認「真的有在累積」

- App 內 **「參考 / 診斷」分頁 → 🔭 資料診斷** 有一顆 **NAV 累積狀態燈**,會用 `status()` 把
  「密鑰沒設 = 其實沒在累積」這種靜默失敗變成看得見的紅燈。
- 或每天看一次 `/var/log/nav_accumulate.log` 最後一行的 `written=` 數字。
- 資料一旦進了雲端 `nav_history`,健診 / 個基體檢會**優先讀它**算真實長期報酬,不再靠不足資料外推
  (根治「假吃本金」誤判)。

---

## 附:寫入的資料長怎樣

Google Sheet `nav_history` 分頁,主鍵 `(code, date)`,欄位:

```
code | date | nav | fund_name | source | recorded_at
```

- `date` 一律 `YYYY-MM-DD`,且 v19.461 起會**擋掉未來日期 / 月日超範圍**的髒資料(不寫入,並在 log 標明),
  避免上游解析錯誤把不可能的日期靜默存進來。
- `source` 這條路寫入的標記是 `nas_cron`(和 App 端 / CSV 匯入區分)。
- 同日重跑同一檔 → `(code, date)` 去重,只留一筆,不灌水(§5 冪等)。

---

**相關文件**:`NAS_PROXY_GUIDE.md`(NAS 代理環境)、`docs/WEEKLY_SWITCH_NOTIFY_SETUP.md`(每週換股 LINE 週報,同一組 GS 密鑰)、`docs/POLICY_SHEETS_SETUP.md`(政策 Sheet 欄位)。
