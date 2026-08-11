# 每週換股顧問 LINE 週報 — 設定指南（v19.432）

`scripts/weekly_switch_notify.py`：不靠你開 App，在**台灣端 NAS**每週跑一次**同一套換股顧問**
（與「組合健診 → 換股顧問」完全相同的邏輯），**有建議才推一則 LINE**（沒事不吵你）。

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

### 環境變數（4 個）
```bash
export google_service_account='<你的 Service Account 完整 JSON 字串>'
export macro_weights_sheet_id='<你的 Google Sheet ID>'   # 政策/選股池/nav_history 共用那本
export LINE_CHANNEL_TOKEN='<A 步驟拿到的 channel access token>'
export LINE_USER_ID='<A 步驟拿到的 你的 userId>'
```
（這兩個 GS 變數你 NAS 上跑 `accumulate_nav_tw.py` 時應該已經有了，沿用即可。）

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
