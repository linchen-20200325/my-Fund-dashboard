# 範本檔案（templates/）

這個目錄存放所有「需要 user 自行上傳的資料」的範本檔。
每個範本都可以直接下載 → 改成你的真實資料 → 上傳到對應位置。

## 4 個範本對照表

| 範本 | 上傳位置 | 必要度 | 用途 |
|---|---|---|---|
| `nav_history_sample.csv` | Tab6「🗄️ NAV 歷史資料管理」 | ⭐⭐⭐ | 基金歷史淨值（西元日期版）|
| `nav_history_sample_roc.csv` | Tab6「🗄️ NAV 歷史資料管理」 | ⭐⭐⭐ | 基金歷史淨值（民國年版）|
| `fund_history_sample.csv` | Tab6「📥 上傳之前下載的 fund_history.csv」 | ⭐⭐ | 「曾經查過的基金」清單還原 |
| `preset_funds_sample.json` | Repo `config/preset_funds.json` | ⭐⭐⭐ | 預設基金清單（持久化）|
| `portfolio_backup_sample.json` | Tab3「📂 上傳 JSON 還原」 | ⭐⭐ | 持有組合 + 帳本 |

## 1. NAV 歷史 CSV（最重要）

**為何重要**：危機回測能看到基金真實跌幅，沒這個只有大盤線。

**格式容錯**：
- 編碼：utf-8 / utf-8-sig / big5 / cp950（MoneyDJ 下載常見）都吃
- 日期：西元 `2024/01/02` / `2024-01-02` 或民國 `113/01/02` 都吃
- 欄名：英文 (`date`, `nav`) 或中文 (`日期`, `淨值`, `單位淨值`) 都吃
- 沒欄名也吃：第一欄當日期、第二欄當淨值

**怎麼取**：
- CnYES：搜尋基金 → 歷史淨值 → 匯出 CSV
- MoneyDJ：基金頁 → 淨值走勢 → 下載
- FundClear（投信投顧公會）：用 ISIN 查

**上傳流程**：
```
Tab6 → 「🗄️ NAV 歷史資料管理」expander
→ 輸基金代號（例：ACTI94）
→ 上傳 CSV
→ 看到「✅ 匯入成功 N 筆」
```

## 2. fund_history.csv

**為何**：Streamlit Cloud reboot 後容器會清空，user 自己抓過的基金紀錄會消失（preset 永遠在）。

**Flow**：
```
Reboot 前：Tab6 → 「💾 下載 CSV」
Reboot 後：Tab6 → 上傳同一個 CSV → 紀錄還原
```

## 3. preset_funds.json

**為何**：「預設常用基金」清單存在 git repo，每次 reboot 後仍然有。

**Flow**：
```
Tab6 「⭐ 升等為預設」加新基金
→ 「💾 下載 preset_funds.json」
→ 用此檔取代 repo 的 config/preset_funds.json
→ git commit + push（或用 ./scripts/quick_merge.sh）
→ 下次 reboot 後仍是預設
```

## 4. portfolio_backup.json

**為何**：你的真實持有組合（買多少、什麼日期、什麼匯率）+ 帳本 ledger。

**Flow**：
```
平常：Tab3 → IO panel → 「💾 下載 JSON」
Reboot 後：Tab3 → 「📂 上傳 JSON 還原」
```

## §4 自省 — 為何要這 4 個

| 上傳 | 影響 |
|---|---|
| NAV 歷史 CSV | **準度** — 危機回測能看到基金真實軌跡 |
| fund_history.csv | **UI 持久化** — 查過的紀錄不消失 |
| preset_funds.json | **UI 持久化** — 預設清單跨 reboot |
| portfolio_backup.json | **資料持久化** — 你的真實組合不消失 |

只有 **NAV 歷史 CSV** 真的影響「總經 / 回測準度」。其他 3 個是「reboot 不丟資料」。
