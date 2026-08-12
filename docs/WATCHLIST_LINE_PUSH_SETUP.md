# 追蹤清單 → MoneyDJ 淨值 → LINE 推播 設定手冊

> 對應：`scripts/watchlist_push.py`、`.github/workflows/watchlist_push.yml`
> 架構：**公開 CSV 追蹤清單 → 排程 → 逐檔抓 MoneyDJ 淨值 → LINE Messaging API push**
> 特點：讀清單**零 GCP 金鑰**（公開 CSV）；LINE 沿用你週報同一組憑證。

---

## ⚠️ 先讀這段：美國 IP 抓不到 MoneyDJ

GitHub Actions 跑在**美國 IP**，MoneyDJ / 境外基金淨值從美國 IP **常被擋**（這是本專案一直在處理的老問題）。所以這條推播有兩種可行跑法：

| 跑法 | MoneyDJ 抓得到嗎 | 需要 |
|---|---|---|
| **A. GitHub Actions + NAS 代理** | ✅（走你 NAS 的台灣 IP） | 多設 `PROXY_URL` secret 指向 NAS 代理 |
| **B. GitHub Actions 直連** | ⚠️ 多半抓不到 → 該檔標「資料不足」 | 只設 3 個必要 secret |
| **C. 直接掛 NAS cron** | ✅（NAS 就是台灣 IP 直連） | 在 NAS 加一行 cron，不用 GitHub |

抓不到的檔會**誠實標「⚠️ 資料不足」**，不會捏造淨值（§1）。想每檔都有真淨值 → 用 **A 或 C**。

---

## 1. 追蹤清單：Google Sheet 發布為公開 CSV

### 1.1 你做一次（人做）
1. 打開你的 Google Sheet → 新增一個分頁（例：`追蹤清單`），**第一列填表頭 `代號`**，下面一列一檔：
   | 代號 |
   |---|
   | ACCP138 |
   | TLZF9 |
   | ACTI71 |
2. **檔案 → 共用 → 發布到網路** → 左邊選**這個分頁**、右邊選 **逗號分隔值 (.csv)** → **發布**。
3. 複製連結，形如 `https://docs.google.com/spreadsheets/d/e/{PUB_ID}/pub?output=csv`。

> **雷**：私有 Sheet 排程讀到的是登入頁 HTML，不是 CSV → **一定要發布/公開**。
> 發布的 CSV 一次只含一個分頁 → 清單集中在同一分頁。
> 也可以直接發布你的**選股池**分頁當清單，程式會自動讀「代號」欄。

---

## 2. LINE 憑證（沿用週報那組，不用新設）

本推播重用 `infra/line_push`，用的是**和 NAS 週報同一組** secret：
- `LINE_CHANNEL_TOKEN`：LINE 官方帳號的 channel access token
- `LINE_USER_ID`：你的 `U` 開頭 userId（要先加該官方帳號好友，否則收不到）

> LINE Notify 已於 2025/03 停用，本功能走 Messaging API push。

---

## 3A. 跑法 A/B：GitHub Actions

到 **Repo → Settings → Secrets and variables → Actions → New repository secret**：

| Secret | 值 | 必要 |
|---|---|---|
| `WATCH_CSV_URL` | 上面發布的公開 CSV 連結 | ✅ |
| `LINE_CHANNEL_TOKEN` | 同週報 | ✅ |
| `LINE_USER_ID` | 同週報 | ✅ |
| `PROXY_URL` | 你的 NAS 代理（要美國 IP 也抓得到 MoneyDJ 才需要） | 選填(A 需要) |

**驗證**：Actions → 「追蹤清單淨值推播 (LINE)」→ **Run workflow** → `dry_run` 保持 **`true`** →
看 log 印出「追蹤 N 檔」+ 訊息內容確認無誤 → 再跑一次填 **`false`** 實送一則到 LINE。

**排程**：預設 `cron: "0 0 * * 1"` = **每週一 08:00 台灣**（UTC 週一 00:00）。
要改頻率就改 `.github/workflows/watchlist_push.yml` 那行（例：每交易日早上 → `0 0 * * 1-5`）。
⚠️ GitHub cron 是 UTC，台灣 = UTC+8，記得換算。

## 3C. 跑法 C：NAS cron（台灣 IP，最穩）

在 NAS 設環境變數 `WATCH_CSV_URL` / `LINE_CHANNEL_TOKEN` / `LINE_USER_ID`，然後：

```bash
# 先驗證（不會真送）
python scripts/watchlist_push.py --dry-run
# 排程（每週一早上 8 點，台灣時間）
0 8 * * 1  cd /path/to/my-Fund-dashboard && python scripts/watchlist_push.py
```

---

## 4. 訊息長什麼樣

```
📈 追蹤清單淨值（2026-08-12）
共 3 檔

• ACCP138 聯博全球高收益債:12.3400（2026-08-11） ｜近5日 +0.8%
• TLZF9 安聯收益成長:15.6700（2026-08-11） ｜近5日 -1.2%
• ACTI71 …:⚠️ 資料不足（抓不到 MoneyDJ 淨值）
```

超過 LINE 單則上限（5000 字）會自動切成多則送出。

---

## 5. 踩雷總表（照做省事）
1. **Fail Loud**：URL 未設 / 解析 0 項 → 非零 exit、**不送空或假訊息**。
2. **只呈現真值**：某檔抓不到 → 標「資料不足」，**不填預設/捏造值**（§1）。
3. **時區**：GitHub cron 是 UTC，換算成台灣時間。
4. **Sheet 要公開**：私有讀到的是 HTML 登入頁。
5. **表頭鎖欄**：有「代號」欄就只讀那欄，避免把數量誤當代號。
6. **log 不洩漏**：例外只印「類型」，不整段印（可能內嵌 URL/token）。
7. **先 dry-run**：上線前先驗解析與訊息，確認再真送。
8. **清單維護零改動**：加/減追蹤項只改 Google Sheet，不動程式碼、不改 secret。
