# 每週換股顧問健康週報 LINE — 設定指南（v19.441）

`scripts/weekly_switch_notify.py`：不靠你開 App，每週對「**持倉 ∪ 追蹤清單（觀察標的）**」跑一次
**同一套換股顧問**（與「組合健診 → 換股顧問」完全相同的邏輯），**有檔不健康才推一則 LINE**
（沒事不吵你），並附選股池建議替換。

> **v19.441 更新**：
> - **觀察範圍**擴為「持倉 ∪ 追蹤清單」（`WATCH_CSV_URL` 公開 CSV;未設 → 只跑持倉），依代號去重、每檔標 `[持倉]`/`[觀察]`。
> - **健康問題**含：🔴 **嚴重吃本金**（含息報酬 < 配息率）/ 🔄 **高基期該換**（震盪型貼近高基期）/ 🔴 成長看衰賣現金 / ⚠️ 跑輸大盤。修好「高配息掩蓋的吃本金原本會漏報」的漏洞。
> - **頻率**改**週日傍晚**（`0 18 * * 0` 台灣;或用 GitHub Actions `weekly_switch_notify.yml`）。

> ⚠️ **LINE Notify 已於 2025/03 停止服務**，本功能走 **LINE Messaging API**（自建 bot 推播給自己）。

---

## A. 建 LINE Messaging API bot（做一次，約 5 分鐘）

1. 開 **LINE Developers Console** → 用你的 LINE 登入。
2. 建一個 **Provider**（隨便取名，如「我的基金」）。
3. 在該 Provider 下 **Create a new channel** → 選 **Messaging API**，填名稱（如「基金換股提醒」）。
4. 進該 channel → **Messaging API** 分頁：
   - 找 **Channel access token（long-lived）** → 按發行 → 複製，這就是 `LINE_CHANNEL_TOKEN`。
   - 頁面上有這個 bot 的 **QR code / Bot basic ID** → 用你的 LINE **加它為好友**（一定要加，否則收不到）。
5. 拿你自己的 **userId**（`LINE_USER_ID`）：最快的方式 —
   - 進 channel 的 **Basic settings** 頁最下方有 **Your user ID**（就是你自己的），複製即可；
   - 若那裡沒有，開 **LINE Official Account Manager** 或用 webhook 收一則自己傳的訊息看 `source.userId`。

> 只推給你自己一個人，不需要開 webhook server、不需要審核。

---

## B. NAS / 本機設定（做一次）

前置：台灣 IP（直連即可）、`pip install -r requirements.txt`（streamlit 只是被 import，不會啟動）。

### 環境變數（5 個）
```bash
export google_service_account='<你的 Service Account 完整 JSON 字串>'
export macro_weights_sheet_id='<App 內部總經表 / nav_history 的 Google Sheet ID>'
export POLICY_SHEET_ID='<你的持倉 Sheet ID>'   # v19.462：選股池優先存這本的 _fund_pool 分頁
export LINE_CHANNEL_TOKEN='<A 步驟拿到的 channel access token>'
export LINE_USER_ID='<A 步驟拿到的 你的 userId>'
```
（GS 變數你 NAS 上跑 `accumulate_nav_tw.py` 時應該已經有了，沿用即可。）

> ⚠️ **v19.462：選股池位置變更**。選股池(換股顧問的候選替換來源)現在**優先存
> `POLICY_SHEET_ID`(你的持倉那本)的 `_fund_pool` 分頁**。所以：
> - 本 cron 必須也拿到 `POLICY_SHEET_ID`，否則它會讀到**另一本**(macro_weights)的舊/空池，
>   週報的替換建議就對不上你在 App 裡看到的選股池。
> - 那個 **Service Account 信箱要被加為 `POLICY_SHEET_ID` 這本 Sheet 的「編輯者」**(headless 用 SA 讀寫)。
> - 未設 `POLICY_SHEET_ID` → 選股池回退 macro_weights 本(行為同舊版)。

### 先手動驗證（**不會真的送**，只印訊息預覽）
```bash
cd /path/to/my-Fund-dashboard
python scripts/weekly_switch_notify.py --dry-run
```
- 看到「該通知=… / 表現差·建議 N 檔」與訊息預覽 = 流程通。
- 想測「即使無建議也送一則」心跳：加 `--notify-empty`。
- 想連「成長型看衰賣出」訊號也算（會多打 ~28 個 FRED 指標、需 `FRED_API_KEY`）：加 `--with-macro`。

### 排程（每週一傍晚，基金 NAV 多 T+1 傍晚更新）
```cron
30 18 * * 1  cd /path/to/my-Fund-dashboard && python scripts/weekly_switch_notify.py >> /var/log/switch_notify.log 2>&1
```
確認無誤後，把 `--dry-run` 拿掉（上面排程已是正式送出）。

---

## C. 行為與退出碼（§1 Fail-Loud，方便你在 NAS log 看狀態）

| 情況 | 行為 | 退出碼 |
|---|---|---|
| 缺 secret（GS / sheet id） | log + 中止，不送 | `2` |
| 帳本讀不到任何持倉代碼 | log + 中止 | `2` |
| 全部基金資料抓失敗 | log + 中止 | `1` |
| 單檔抓失敗 | 顯式 skip + 計數，其餘照跑（不偽造） | — |
| 有建議 → LINE 送失敗 | log + 中止 | `1` |
| 有建議 → 送成功 | 推一則 LINE | `0` |
| **無建議** | 不推（除非 `--notify-empty`） | `0` |

- **成長型賣出訊號**：headless 預設 `macro=None`（誠實降級，成長型不觸發賣出）—— 想要就加 `--with-macro`。
- 通知只在 **換股 / 賣轉現金 / 表現差（跑輸大盤或絕對虧損）** 時發；續抱 / 觀察 / 資料不足**不吵你**。
- **這是紀律工具、非獲利保證**；訊息尾端固定附此提醒。
