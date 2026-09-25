# 現有資料庫盤點（線 1）

> **客戶 2026-09-21 指令**：確認現有資料庫有什麼 —— 表、欄位、樣本值；有值 / 空值 / 格式不一致；一張表，三欄。
>
> 本份是**現況描述**，不是設計。本文不寫「應該改成」「建議」「缺什麼要補」——
> 只寫**現在有什麼**、以及**本輪讀不到什麼**。
>
> ~~**量測基準 commit：`0b08201`**（本輪所有指令與輸出皆在此基準上實跑）。~~
> → **量測基準 commit 改為 `8e4ce6c`；全檔指令已於 2026-09-21 重跑一次。**
> （**有意識的更正，不是漏刪** · 日期 **2026-09-21** · 決策者：**E 組資料工程組** · 由獨立稽核 C 組指出）
>
> ⚠️ **舊表述為什麼非改不可**：「皆在此基準上實跑」是一句**承重的可重現性宣稱**，
> 而它被本文自己的輸出推翻了一格 —— §5.1 副檔名普查那格的 `53` 是 `8e4ce6c` 的數字，不是 `0b08201` 的。
> 實測：`git ls-tree -r --name-only 0b08201 | grep -c '\.md$'` → `52`；同一條指令在 `8e4ce6c` → `53`。
> **這是基準標籤寫舊，不是編造輸出** —— 其餘各條在兩個 revision 上各跑一次，結果相同。
>
> ⚠️ **為什麼換基準之後絕大多數數字不動，也寫出來讓人驗得出口徑**：
> `git diff --name-only 0b08201 8e4ce6c` 只回兩個 `.md` 檔
> （`docs/v2/21_decision_log.md`、`docs/v2/43_ui_draft_01_macro_target.md`），**無 `.py`、無資料檔**；
> 本盤點讀過的 15 個資料檔（含 `cache/nav/` 那一檔）與 `scripts/update_macro_history.py`，
> 以 `git rev-parse 0b08201:<path>` 對 `git rev-parse 8e4ce6c:<path>` 逐檔比對 blob hash **皆相同**。
> **但本輪沒有靠這個推論跳過實測** —— §5 各條是真的重跑過才改的。

---

## 0. 讀法：狀態欄的四個值（先寫死，避免各自解讀）

| 狀態 | 定義 |
|---|---|
| `有值` | 本輪實際讀到非空資料 |
| `空值` | 本輪實際讀到，但內容是空的／全 NaN／全 null／空字串／空容器 |
| `格式不一致` | 本輪讀到了，但同一欄出現多種型別／單位／格式 |
| `查不到` | **本輪讀不到** —— 沒有憑證、檔案不存在、或需要線上連線 |

**兩條判準（本表一致套用，寫出來讓客戶驗得出口徑）**：

1. **「部分 null」歸在 `有值`**，並在備註寫出 null 筆數。
   `空值` 保留給**整欄皆空**的情形。理由：只有整欄空才是「這個欄位沒有資料」。
2. **`格式不一致` 只給「已存在的值之間」的分歧**（單位不同、格式不同、鍵組不同）。
   null 與非 null 並存**不算**格式不一致 —— 那是缺值，不是格式。

---

## 1. 公開性處置（本 repo 為 public，先講清楚哪些值不寫）

| 資料類別 | 本文的寫法 |
|---|---|
| 市場資料（FRED 指標、VIX、SPX、TWII） | **寫真值** —— 公開市場資料 |
| 客戶個人資料（持倉金額、保單、帳本、政策設定、個人 Sheet 內容、基金代號清單） | **只寫格式樣本**：型別、長度、遮罩形狀（`9`＝數字、`A`＝英文字母、`C`＝中日文字、**其餘一切字元原樣保留**） |
| 憑證／金鑰／Sheet ID／token | **只寫欄位名，不寫值**，不寫遮蔽版 |

⚠️ 本文出現的 `<基金代號>`、`<policy_id>`、`<run_id>` 等角括號字樣皆為**佔位符**，非真值。
⚠️ 原始碼內有兩個**寫死的 Google Sheet ID 常數**（見 §2 表末兩列）；本文記其**常數名**，**不抄錄其值**。

⚠️ **2026-09-21 遮罩慣例統一 —— 舊版同一份文件裡有兩套，已就地改齊**
（**有意識的更正，不是漏刪** · 日期 **2026-09-21** · 決策者：**E 組資料工程組** · 由獨立稽核 C 組指出）。

**現行唯一慣例**：數字 → `9`、英文字母 → `A`、中日文字 → `C`、
**其餘一切字元（`-`／`/`／`.`／`:`／`%`／半形空格／全形括號…）一律原樣保留**。

**舊版的分歧**：§2.5 的幾格（`9999/99/99`、`99.999`、`999/99/99`、`9999-99-99A99:99:99`）保留字面標點，
而 §2.2／§2.3 的日期格卻把 `-`、`:`、半形空格也一律寫成 `A`。同一份文件裡，`A` 同時代表兩件事。

⚠️ **這套分歧是 §3 那個 `T` 錯誤的成因，不是無害的體例小事**：
`9999A99A99A99A99A99` 讀起來**就像**帶 `T` 的 ISO8601，
於是一個「`A` 代表什麼」的體例問題，變成一句**關於資料格式的假陳述**（見 §3 表下註）。

⚠️ **另一處具體代價，寫出來讓人看得見遮罩會吃掉什麼**：
`templates/portfolio_backup_sample.json` 的 `t7_ledgers` 外層鍵，舊版寫成 `AAA9AAAAAA99` ——
真實鍵裡有一個 `-` 和一組**字面 `::`** 分隔，被一律遮成 `A` 之後**那個結構事實就消失了**。
現行慣例下的遮罩是 `AA-9::AAAA99`，分隔結構看得見，而真值一樣沒有外洩。

---

## 2. 主表：表.欄位 ｜ 狀態 ｜ 備註

### 2.1 `data_cache/` —— ~~本輪唯一讀得到真實資料的一批~~ → **列數最大的一批**（parquet ＋ metadata）

| 表.欄位 | 狀態 | 備註 |
|---|---|---|
| `fred_indicators.parquet.date` | 有值 | `datetime.date` 物件（parquet date32），非字串。13654 列 0 null。跨 9 個 series 共 3932 個相異日期 |
| `fred_indicators.parquet.series_id` | 有值 | `str`，0 null，9 個相異值：`BAMLH0A0HYM2` `CPIAUCSL` `DGS10` `DGS2` `DGS3MO` `DTWEXBGS` `M2SL` `UNRATE` `WALCL`（公開 FRED 代號） |
| `fred_indicators.parquet.value` | 格式不一致 | `float64`，0 null，但**單位隨 `series_id` 改變，同一欄混放四種量綱**：百分比（`DGS10` 0.52–4.98、`UNRATE` 3.4–14.8）／指數（`CPIAUCSL` 224.8–332.4、`DTWEXBGS` 118.06–120.89）／十億美元（`M2SL` 9182–22804）／百萬美元（`WALCL` 2804457–8965487）。讀值前必須先看 `series_id` |
| `spx_history.parquet.date` | 有值 | `datetime.date`，3839 列 0 null，單調遞增且不重複；2011-06-07 → 2026-09-11。日差分布以 1 日與 3 日為主（週末不補值） |
| `spx_history.parquet.close` | 有值 | `float64`，0 null、無 0 值、無負值；1099.23 – 7798.99，平均 3302.27 |
| `twii_history.parquet.date` | 有值 | `datetime.date`，3726 列 0 null，單調遞增且不重複；2011-06-07 → 2026-09-11 |
| `twii_history.parquet.close` | 有值 | `float64`，0 null、無 0 值、無負值；6633.33 – 47741.51，平均 13861.03 |
| `vix_history.parquet.date` | 有值 | `datetime.date`，3841 列 0 null，單調遞增且不重複；2011-06-07 → 2026-09-11 |
| `vix_history.parquet.close` | 有值 | `float64`，0 null、無 0 值、無負值；9.14 – 82.69，平均 18.16 |
| `metadata.json.updated_at` | 有值 | `str`，ISO8601 帶時區，形狀 `YYYY-MM-DDTHH:MM:SS.ffffff+00:00` |
| `metadata.json.datasets.<ds>.name` | 有值 | `str`，4 個 dataset 各一，值等於 dataset 鍵名 |
| `metadata.json.datasets.<ds>.last_updated` | 有值 | `str`，形狀 `YYYY-MM-DD`（**與同目錄 parquet 的 `date` 欄不同型別**：這裡是字串，那裡是 date 物件） |
| `metadata.json.datasets.<ds>.row_count` | 有值 | `int`；與 parquet 實際列數逐一核對**四個 dataset 皆相符**（13654／3841／3839／3726，核對指令見 §5.2） |
| `metadata.json.datasets.<ds>.last_error` | 空值 | `NoneType`；4 個 dataset 此欄皆為 null |

**本批的覆蓋落差（實測，非推論）**：`fred_indicators` 各 series 的起訖與筆數差距很大 ——
`DGS10`／`DGS2`／`DGS3MO` 各 3816 筆（2011-06-07 起）、`WALCL` 797 筆、`BAMLH0A0HYM2` 858 筆（2023-06-05 起）、
`M2SL` 179 筆、`UNRATE` 181 筆、`CPIAUCSL` 178 筆、而 `DTWEXBGS` 僅 **13 筆**（2026-06-05 → 2026-09-04）。
各 series 的最新日期亦不一致：日頻序列到 2026-09-10，`UNRATE` 到 2026-08-01，`CPIAUCSL` 與 `M2SL` 到 2026-04-01。

⚠️ **2026-09-21 本節標題更正**（**有意識的更正，不是漏刪** · 日期 **2026-09-21** ·
決策者：**E 組資料工程組** · 由獨立稽核 C 組指出）：
舊標題「**本輪唯一讀得到真實資料的一批**」**被本文自己的 §2.2–§2.5 當場推翻** ——
那四節（`cache/nav/`、`snap.json`、`config/`、`templates/`）**是本輪真的讀到的**，
狀態欄填的就是 `有值`／`空值`／`格式不一致`，四節合計 73 列。

⚠️ **而 §5.6 是本文自己立的規矩**：「本文採分類敘述，
**不寫『只有 N 個資料落點』這種需要『沒有漏看』才成立的句子**」——
**舊標題正是那種句子**，而且它連「有沒有漏看」都不必問：推翻它的證據就印在同一份文件的下面四節。

**現行標題只留一個對照本文自己的表格就能驗的事實**：這一批的單檔列數是 3726–13654，
在 §2 各批裡最大（§2.2 為 10 筆、§2.3 為 8 檔 × 30 點、§2.5 單檔 2–10 筆）。

### 2.2 `cache/nav/<基金代號>.json` —— 單檔 NAV 快取（本輪磁碟上僅此一檔）

| 表.欄位 | 狀態 | 備註 |
|---|---|---|
| `cache/nav/<code>.json.code` | 有值 | `str`，長度 5。檔名即代號，故**檔名本身帶個資**，本文不抄錄 |
| `cache/nav/<code>.json.fund_name` | 空值 | `str` 但長度為 **0**（空字串）—— 有欄位、無內容 |
| `cache/nav/<code>.json.updated_at` | 有值 | `str`，長度 32，ISO8601 帶時區 |
| `cache/nav/<code>.json.source` | 有值 | `str`，長度 10 |
| `cache/nav/<code>.json.count` | 有值 | `int`，值為 10，與 `history` 長度相符 |
| `cache/nav/<code>.json.history[].date` | 有值 | `str`，10 筆 0 null，遮罩形狀 ~~`9999A99A99`~~ → **`9999-99-99`**（即 `YYYY-MM-DD`；2026-09-21 依 §1 統一後的遮罩慣例改寫，形態本身未變） |
| `cache/nav/<code>.json.history[].nav` | 有值 | `float`，10 筆 0 null |

### 2.3 `snap.json` —— 基金指標快照（repo 根目錄，8 檔基金）

| 表.欄位 | 狀態 | 備註 |
|---|---|---|
| `snap.json.dumped_at` | 有值 | `str`，長度 32，ISO8601 帶時區 |
| `snap.json.funds{}`（鍵） | 有值 | 8 個鍵，鍵即基金代號（個資，不抄錄）；遮罩形狀三種：`AAAA9`／`AAAA99`／`AAAA999` |
| `snap.json.funds{}.fund_name` | 有值 | `str`，8 筆 0 空；字元長度 8 – 61 |
| `snap.json.funds{}.category` | 格式不一致 | `str`，8 筆 0 空，但**同欄混放兩種東西**：字元長度為 3／3／3／12 的短分類標籤，與 266／268／383／762 字的公開說明書段落。同一欄既是分類碼也是長文 |
| `snap.json.funds{}.inception_date` | 有值 | `str`，8 筆 0 空，形狀 `YYYY-MM-DD` |
| `snap.json.funds{}.perf` | 格式不一致 | `dict`，8 筆皆為 dict 但**鍵組三種**：5 檔為**空 dict**；2 檔含 8 鍵（`1M` `3M` `6M` `1Y` `2Y` `3Y` `source` `fetched_at`）；1 檔含 7 鍵（**少 `3Y`**）。同一欄位的結構逐檔不同 |
| `snap.json.funds{}.perf_source` | 有值 | 3 筆 `str`、**5 筆 null**；非 null 者遮罩形狀 ~~`AA99` 與 `AAAA`~~ → **3 筆全為 `AA99`**（長度皆 4）。2026-09-21 重測更正：`AAAA` 這個形態**不存在**，逐值遮罩輸出見 §5.8 |
| `snap.json.funds{}.nav_points[]` | 有值 | `list`，8 檔各 30 筆、合計 240 筆；元素為長度 2 的 `list`。第 0 元素 `str`、遮罩 ~~`9999A99A99A99A99A99`~~ → **`9999-99-99 99:99:99`**（含時分秒；**日期與時間之間是半形空格，不是 `T`** —— 2026-09-21 重測更正，見 §3 表下註與 §5.8）；第 1 元素 `float`，0 null |
| `snap.json.funds{}.metrics.inception_date` | 有值 | `str`，8 筆 0 null |
| `snap.json.funds{}.metrics.sharpe` | 有值 | `float`，8 筆 0 null |
| `snap.json.funds{}.metrics.std_1y` | 有值 | `float`，8 筆 0 null |
| `snap.json.funds{}.metrics.nav` | 有值 | `float`，8 筆 0 null |
| `snap.json.funds{}.metrics.ret_3y` | 空值 | 8 檔此欄皆為 null |
| `snap.json.funds{}.metrics.ret_3y_ann` | 空值 | 8 檔此欄皆為 null |
| `snap.json.funds{}.metrics.ret_3y_cum` | 空值 | 8 檔此欄皆為 null |
| `snap.json.funds{}.metrics.ret_5y` | 空值 | 8 檔此欄皆為 null |
| `snap.json.funds{}.metrics.ret_5y_ann` | 空值 | 8 檔此欄皆為 null |
| `snap.json.funds{}.metrics.ret_5y_cum` | 空值 | 8 檔此欄皆為 null |
| `snap.json.funds{}.metrics.max_drawdown` | 空值 | 8 檔此欄皆為 null |

`metrics` 共 11 個子欄位，其中 4 個有值、**7 個整欄為 null**（逐欄統計見 §5.3）。

### 2.4 `config/` —— 設定與預設清單

| 表.欄位 | 狀態 | 備註 |
|---|---|---|
| `config/preset_funds.json._comment` | 有值 | `str`，長度 69 |
| `config/preset_funds.json.funds[].code` | 有值 | `str`，8 筆 0 空，長度 5 – 7（基金代號，個資，不抄錄） |
| `config/preset_funds.json.funds[].name` | 有值 | `str`，8 筆 0 空，長度 8 – 27 |
| `config/macro_weights_active.json.version` | 有值 | `str` |
| `config/macro_weights_active.json.horizon_months` | 有值 | `int` |
| `config/macro_weights_active.json.drawdown_threshold` | 有值 | `float` |
| `config/macro_weights_active.json.indicators` | 空值 | `dict`，長度 **0**（空 dict）—— 有欄位、無任何指標權重 |
| `config/macro_weights_active.json.calibrated_at` | 空值 | `null` |
| `config/macro_weights_active.json.calibration_method` | 空值 | `null` |
| `config/macro_weights_active.json.verdict_cutoffs` | 空值 | `null` |
| `config/macro_weights_active.json.phase_thresholds` | 空值 | `null` |
| `config/macro_weights_active.json.oos_metrics` | 空值 | `null` |
| `config/macro_weights_active.json.ai_explanation` | 空值 | `null` |
| `config/macro_weights_active.json.notes` | 有值 | `str` |
| `services/config/macro_weights_active.json.version` | 有值 | `str`，長度 5 |
| `services/config/macro_weights_active.json.indicators` | 有值 | `dict`，長度 1；唯一鍵 `VIX_DELTA_5D`，其值為含 `weight`（`float`）的 dict |

⚠️ **同名兩檔、內容不同（實測 `filecmp` 為 False）**：`config/macro_weights_active.json` 有 11 個頂層鍵（440 bytes）、
`services/config/macro_weights_active.json` 只有 2 個頂層鍵（96 bytes）。
兩者共同鍵 `version` 與 `indicators` 的**值也不同**；前者獨有 9 個鍵。這是**兩份不同 schema 共用一個檔名**的現況。

### 2.5 `templates/` —— 範本檔（供使用者複製用）

| 表.欄位 | 狀態 | 備註 |
|---|---|---|
| `templates/nav_history_sample.csv.date` | 有值 | 10 筆資料列；無 BOM；遮罩形狀 `9999/99/99`（西元、斜線） |
| `templates/nav_history_sample.csv.nav` | 有值 | 10 筆，遮罩形狀 `99.999` |
| `templates/nav_history_sample_roc.csv.日期` | 有值 | 10 筆；**有 UTF-8 BOM**；遮罩形狀 `999/99/99`（**民國年**） |
| `templates/nav_history_sample_roc.csv.單位淨值` | 有值 | 10 筆，遮罩形狀 `99.999` |
| `templates/fund_history_sample.csv.代號` | 有值 | 3 筆；**有 BOM**；遮罩兩種 `AAAA9`／`AAAA99` |
| `templates/fund_history_sample.csv.名稱` | 有值 | 3 筆，三種不同遮罩（含中文與全形／半形括號混用） |
| `templates/fund_history_sample.csv.來源` | 有值 | 3 筆，三種遮罩，其中一筆為兩個來源以 ` / ` 串接 |
| `templates/fund_history_sample.csv.查詢次數` | 有值 | 3 筆，遮罩 `9`（個位數整數） |
| `templates/fund_history_sample.csv.首次查詢` | 有值 | 3 筆，遮罩 `9999-99-99A99:99:99`（ISO8601 無時區） |
| `templates/fund_history_sample.csv.最近查詢` | 有值 | 3 筆，同上遮罩 |
| `templates/preset_funds_sample.json.funds[].{code,name}` | 有值 | 結構與 `config/preset_funds.json` 相同；**兩檔內容逐位元組相同**（`filecmp` 為 True） |
| `templates/portfolio_backup_sample.json.schema_version` | 有值 | `str`，長度 3 |
| `templates/portfolio_backup_sample.json.exported_at` | 有值 | `str`，長度 19（`YYYY-MM-DDTHH:MM:SS`，無時區、無微秒） |
| `templates/portfolio_backup_sample.json.portfolio_funds[].code` | 有值 | `str`，2 筆（基金代號，不抄錄） |
| `templates/portfolio_backup_sample.json.portfolio_funds[].name` | 有值 | `str`，2 筆 |
| `templates/portfolio_backup_sample.json.portfolio_funds[].invest_twd` | 有值 | `int`，2 筆 —— **金額欄，值不抄錄** |
| `templates/portfolio_backup_sample.json.portfolio_funds[].policy_id` | 有值 | `str`，2 筆 |
| `templates/portfolio_backup_sample.json.portfolio_funds[].policy_name` | 有值 | `str`，2 筆 |
| `templates/portfolio_backup_sample.json.portfolio_funds[].policy_tier` | 有值 | `str`，2 筆 |
| `templates/portfolio_backup_sample.json.portfolio_funds[].currency` | 有值 | `str`，2 筆 |
| `templates/portfolio_backup_sample.json.portfolio_funds[].is_core` | 有值 | `bool`，2 筆 |
| `templates/portfolio_backup_sample.json.portfolio_funds[].invest_date` | 有值 | `str`，2 筆 |
| `templates/portfolio_backup_sample.json.portfolio_funds[].fx_at_buy` | 有值 | `float`，2 筆 |
| `templates/portfolio_backup_sample.json.portfolio_funds[].avg_nav_with_div` | 有值 | `float`，2 筆 |
| `templates/portfolio_backup_sample.json.portfolio_funds[].div_cash_pct` | 有值 | `int`，2 筆 |
| `templates/portfolio_backup_sample.json.t7_ledgers{}.policy_id` | 有值 | 外層 1 個鍵（遮罩 ~~`AAA9AAAAAA99`~~ → **`AA-9::AAAA99`**；2026-09-21 依 §1 統一後的慣例重算，舊遮罩把一個 `-` 與一組**字面 `::`** 分隔一併吃掉了），內層 3 鍵（`code`／`events`／`policy_id`） |
| `templates/portfolio_backup_sample.json.t7_ledgers{}.code` | 有值 | `str` |
| `templates/portfolio_backup_sample.json.t7_ledgers{}.events[]` | 有值 | `list`，1 筆；元素鍵為 `date` `type` `amount_twd` `units` `nav` `fx` `note` |
| `templates/portfolio_backup_sample.json.t7_scenarios` | 空值 | `list`，長度 **0** |
| `templates/portfolio_backup_sample.json.active_policy_id` | 有值 | `str`，長度 4 |
| `templates/portfolio_backup_sample.json.policy_sheet_id` | 空值 | `str` 但長度 **0**（空字串）—— 範本刻意不帶 Sheet ID |

### 2.6 Google Sheets 類 —— 本輪一律 `查不到`

**讀不到的兩個實測原因（不是推測）**：(1) `.streamlit/secrets.toml` **不存在**（只有 `.example`）；
(2) `gspread` 與 `google.oauth2` 兩個套件在本環境 **import 失敗**。憑證與用戶端**兩邊都缺**，故無法取得任何實際值。
下列欄位名取自原始碼的表頭常數與設定手冊，屬 **schema**；**本輪沒有讀到任何一格內容**。

| 表.欄位 | 狀態 | 備註 |
|---|---|---|
| `Sheets:Policies.{policy_id, policy_name, fund_url, invest_twd, invest_date, currency, fx_at_buy, notes, policy_tier}` | 查不到 | 需 Google 憑證，本輪讀不到。V1 schema，9 欄（前 8 欄順序固定、第 9 欄選填）；分頁名常數 `DEFAULT_WORKSHEET`（`repositories/policy/_helpers.py`）。來源：`docs/POLICY_SHEETS_SETUP.md` Step 5 |
| `Sheets:<policy_id> 分頁`（V2 schema） | 查不到 | 需 Google 憑證，本輪讀不到。V2 為**每張保單一個 worksheet、分頁名即 `policy_id`**；`_` 開頭為保留系統分頁。來源：`repositories/policy/v2.py` |
| `Sheets:_fund_pool.{code, name, category, type_override, note, added_at, status, isin, currency, morningstar_secid}` | 查不到 | 需 Google 憑證，本輪讀不到。10 欄，取自 `repositories/pool_repository.py` 的 `_HEADERS`；分頁名常數 `_WS_POOL` |
| `Sheets:_portfolio_perf_history.{date, period_return_pct, cagr_pct, ann_vol_pct, sharpe, max_drawdown_pct, n_funds, total_cost_twd, is_equal_weight, weights_hash, weights_json, coverage_start, coverage_end, n_days, recorded_at}` | 查不到 | 需 Google 憑證，本輪讀不到。15 欄，取自 `repositories/portfolio_perf_repository.py` 的 `_HEADERS`；分頁名常數 `_WS_PERF` |
| `Sheets:nav_history.{code, date, nav, fund_name, source, recorded_at, currency}` | 查不到 | 需 Google 憑證，本輪讀不到。7 欄，取自 `services/nav_history_gs.py` 的 `_NAV_HEADERS`；分頁名常數 `_WS_NAV` |
| `Sheets:_macro_weights` | 查不到 | 需 Google 憑證，本輪讀不到。分頁名常數 `_GS_WORKSHEET`（`services/macro/weights_store.py`）；以列為槽位（`active` 槽對應固定列號） |
| `Sheets:_Ledgers.{policy_id, date, code, action, units, nav_at_action, twd, fee, note}` | 查不到 | **2026-09-21 補列。** 需 Google 憑證，本輪讀不到。9 欄，取自 `repositories/ledger_repository.py` 的 `LEDGER_COLS`；分頁名常數 `LEDGER_TAB`。**`action` 欄的取值清單常數 `KNOWN_ACTIONS` 含 `dividend`** —— 配息事件會以這個分頁的一列存在（**本文不宣稱它是唯一落點**，理由見表下註）。檔內 docstring 另自陳：主鍵為 `(policy_id, code, date, action, units)`；`KNOWN_ACTIONS` **不強制**（不在清單內視為自訂類型、不會被攔截） |
| `Sheets:_T7_State.{pk_str, fund_code, currency, policy_id, ledger_json, updated_at}` | 查不到 | **2026-09-21 補列。** 需 Google 憑證，本輪讀不到。6 欄，取自 `repositories/snapshot_repository.py` 的 `SNAPSHOT_COLS`；分頁名常數 `T7_STATE_TAB`。**`ledger_json` 欄存的是整個 `Ledger.to_dict()` 的 JSON 字串** —— 欄內嵌 JSON，與同分頁其餘純量欄不同型。檔內 docstring 自陳其與 `_Ledgers` 的分工：`_Ledgers` 是逐筆 audit trail，本分頁是每檔基金一列的 quick-restore snapshot |
| `Sheets:_持倉總覽.{保單號碼, 基金代碼, 基金名稱, 幣別, 級別, 持有單位數, 平均成本淨值, 平均含息成本, 平均匯率, 投資金額(TWD), 現金給付%, 累積已領配息(TWD), 更新時間}` | 查不到 | **2026-09-21 補列。** 需 Google 憑證，本輪讀不到。13 欄，取自 `repositories/snapshot_repository.py` 的 `HOLDINGS_COLS`；分頁名常數 `HOLDINGS_TAB`。**欄名為中文**，與其餘系統分頁的英文欄名是兩套慣例。檔內註解自陳：成本面、不含市值，給使用者直接打開 Sheet 看 |
| `repositories/pool_repository.py::_POOL_SHEET_ID_DEFAULT` | 查不到 | **原始碼內寫死的 Google Sheet ID 常數**。依 §1 處置，**只記常數名，不抄錄其值**。無憑證故無法讀其內容 |
| `services/nav_history_gs.py::_NAV_SHEET_ID_DEFAULT` | 查不到 | 同上，另一本 Sheet 的寫死 ID 常數。**值不抄錄** |
| `.streamlit/secrets.toml.{FRED_API_KEY, GEMINI_API_KEY, POLICY_SHEET_ID}` ＋ `[google_service_account].{type, project_id, private_key_id, private_key, client_email, client_id, auth_uri, token_uri, auth_provider_x509_cert_url, client_x509_cert_url}` | 查不到 | **檔案不存在**（僅存在 `.streamlit/secrets.toml.example`）。此處**只列欄位名**，不寫任何值 |

#### ⚠️ 上表有三列是 2026-09-21 補的 —— 連同「為什麼本輪第一次沒看到它們」

（**有意識的更正，不是漏刪** · 日期 **2026-09-21** · 決策者：**E 組資料工程組** · 由獨立稽核 C 組指出）

**漏了什麼**：`_Ledgers`／`_T7_State`／`_持倉總覽` 三個分頁在本文第一版**完全沒有出現**。
把分頁名、欄名常數與所在檔（`LEDGER_TAB`／`LEDGER_COLS`／`KNOWN_ACTIONS`／`T7_STATE_TAB`／
`HOLDINGS_TAB`／`HOLDINGS_COLS`／`SNAPSHOT_COLS`／`_Ledgers`／`_T7_State`／`_持倉總覽`／
`ledger_repository`／`snapshot_repository`）一起當字表去掃第一版全文，命中數是 `0`。
⚠️ **這一個數字，後人跑不出來，要講清楚**：本文第一版**沒有進過 git**（產出當下是未追蹤檔，
本輪直接就地改寫），所以它**沒有任何 revision 可以回去比對**。
上面那個 `0` 是**本輪動手改之前當場量的**，性質上是**本組的證詞，不是可重現的量測** ——
與本文其餘釘著 `8e4ce6c` 的數字**不同級**，引用時請照這個級別引用。
其中 `_Ledgers` 的份量與另外兩個不同：**配息事件會以這個分頁的一列存在**
（`action` 欄的取值常數 `KNOWN_ACTIONS` 含 `dividend`），而本文第一版的 §2.6 連這個分頁都沒有。
⚠️ 本文**不宣稱**它是配息事件在本 repo 的唯一落點 —— 那句話要成立得靠「沒有漏看」，
本輪沒有做那個查證（同 §5.6 的既有處置）。可以確定的只有：**這裡存得下配息事件，而本文第一版沒有記到它。**

**為什麼漏得掉（這一段比補上那三列更重要）**：§5.2 的兩條指令都是**檔案 I/O 面向**的字表 ——
一條掃 `to_parquet` `to_csv` `to_json` `json.dump` `sqlite3` 這類**落地 API**，
另一條掃 `_CACHE_DIR` `_DIR = Path` `DATA_CACHE` `data_cache` 這類**本機路徑常數**。
而 `_Ledgers` 走的是 gspread 的 `ws.update` 與 `append_row`、它的名字叫 `LEDGER_TAB` ——
**兩條字表在結構上都看不到它**。這不是這一輪運氣不好，是**同一條指令再跑一百次也一樣**。

⚠️ **更根本的一點，據實寫明**：§5 從頭到尾**沒有任何一條指令是用來產生 §2.6 那份 Sheets 清單的**。
§2.6 只說欄位名「取自原始碼的表頭常數與設定手冊」，**沒有說那 6 個分頁是怎麼被窮舉出來的** ——
也就是那份清單的**覆蓋率當時沒有任何方法背書**，它是讀出來的，不是掃出來的，而本文沒有寫明這件事。
本輪補的掃描見 **§5.7**。

📌 **對照 `CLAUDE.md` §-1.5.1c 判定 2 的既有教訓**：「**字表選錯，掃再多次都沒用**」。
該處記載的兩次實證是：先只 grep `import requests`，漏掉走 `infra.proxy.fetch_url` 的那處；
擴了字表再掃一次，又漏掉 `yfinance` 直抓的那處。
**本節是同一個病換一個面向的第三個實例** —— 前兩次漏的是「發網路請求的形態」，
這次漏的是「**資料存放的介質**」：字表全部指向本機檔案，於是**存在遠端分頁裡的東西一個都掃不到**。

---

### 2.7 程式宣告了、但本輪磁碟上不存在的落點 —— `查不到`

| 表.欄位 | 狀態 | 備註 |
|---|---|---|
| `data_cache/ai_cache.json` | 查不到 | 檔案不存在。宣告於 `repositories/ai_cache.py` 的 `_PATH`；`.gitignore` 明文排除，屬執行期產物 |
| `data_cache/batch/batch_<run_id>.json` | 查不到 | 目錄不存在。宣告於 `repositories/batch_checkpoint.py` 的 `_DIR`；`.gitignore` 明文排除 |
| `data_cache/macro_thresholds_global.json` | 查不到 | 檔案不存在。為 `scripts/calibrate_macro_score.py` 的 `--emit-json` 預設輸出路徑 |
| `cache/fund_pool/pool.json` | 查不到 | 目錄與檔案皆不存在。宣告於 `repositories/pool_repository.py` 的 `_CACHE_DIR` ＋ `_LOCAL_FILE`（Sheets 的本地鏡像） |
| `cache/portfolio_perf/perf_history.json` | 查不到 | 目錄與檔案皆不存在。宣告於 `repositories/portfolio_perf_repository.py` 的 `_CACHE_DIR` ＋ `_LOCAL_FILE` |
| `cache/nav_history/` | 查不到 | 目錄不存在。宣告於 `repositories/fund/nav_metrics.py` 的 `_NAV_HISTORY_CACHE_DIR` |
| `cache/fundclear/` | 查不到 | 目錄不存在。宣告於 `repositories/fundclear_offshore.py` 的 `_CACHE_DIR` |
| `cache/fred_release/` | 查不到 | 目錄不存在。宣告於 `repositories/macro/fred.py` 的 `_FRED_RELEASE_CACHE_DIR` |
| `/tmp/fund_cache`（或 `/content/fund_cache`） | 查不到 | 兩個路徑本輪皆不存在。宣告於 `infra/cache.py` 的 `_CACHE_DIR`，依 `/content` 是否存在二擇一 |
| `fred_indicators.parquet.series_id` 之 `PPIACO` | 查不到 | `scripts/update_macro_history.py` 的 `FRED_SERIES_IDS` 宣告了此 series，但 parquet 內**無此 `series_id`**。⚠️ **本列的 `查不到` 與其餘各列不同判準，見表下註** |
| `fred_indicators.parquet.series_id` 之 `PCOPPUSDM` | 查不到 | 同上：宣告於 `FRED_SERIES_IDS`，parquet 內無此 `series_id`。⚠️ **本列的 `查不到` 與其餘各列不同判準，見表下註** |

⚠️ `cache/*` 與部分 `data_cache/` 子項在 `.gitignore` 內被預設排除（`cache/*` 全擋、白名單放行單一 NAV 檔），
故上列落點在**這份 checkout** 上不存在。本文只陳述「本輪讀不到」，不推斷線上環境是否存在。

⚠️ **上表最後兩列（`PPIACO`／`PCOPPUSDM`）的 `查不到` 用的是另一套判準 —— 2026-09-21 就地寫明**
（**有意識的更正，不是漏刪** · 日期 **2026-09-21** · 決策者：**E 組資料工程組** · 由獨立稽核 C 組指出）。

§0 把 `查不到` 定義成「**本輪讀不到** —— 沒有憑證、檔案不存在、或需要線上連線」。
這兩列**不是讀不到**：`data_cache/fred_indicators.parquet` 本輪**成功讀到了**
（13654 列、0 null、9 個相異 `series_id`，輸出見 §5.4），只是**讀到的內容裡沒有這兩個 series**。

**「讀到了、裡面沒有」在 §0 的四值定義下沒有位置**：
它不是 `空值`（那條判準是「整欄皆空」，而 `series_id` 這一欄有 13654 筆非空值），
也不是 §0 所寫的 `查不到`。兩者記的其實是兩件事 ——
其餘各列記「**這個落點我打不開**」，這兩列記「**落點打開了，宣告的東西沒落地**」。

**本輪的處置：不新增第五個狀態值，改為就地寫明判準不同。**
理由是狀態欄是本文的核心契約，一旦加值，既有各列的口徑全部要重判，
而本文是現況描述、不做設計（§6 第 1 點：單組產出）。
⚠️ 依本文體例，這裡**不寫**「應該改成什麼」 —— 只把「同一格值底下混了兩種判準」這個事實寫出來。

---

## 3. 跨表對照：同一個「日期」目前有五種寫法

此項非單一欄位的問題，逐欄看不出來，故另列。以下皆為本輪實測到的形態：

| 落點 | 日期的實際型別／形狀 |
|---|---|
| `data_cache/*.parquet` 的 `date` | `datetime.date` 物件（binary，非字串） |
| `metadata.json` 的 `last_updated` | `str`，`YYYY-MM-DD` |
| `cache/nav/<code>.json` 的 `history[].date` | `str`，`YYYY-MM-DD` |
| `snap.json` 的 `nav_points[][0]` | `str`，~~`YYYY-MM-DDTHH:MM:SS`~~ → **`YYYY-MM-DD HH:MM:SS`**（帶時分秒；**分隔符是半形空格，不是 `T`** —— 2026-09-21 重測更正，見表下註） |
| `templates/nav_history_sample.csv` 的 `date` | `str`，`YYYY/MM/DD`（**斜線**） |
| `templates/nav_history_sample_roc.csv` 的 `日期` | `str`，`YYY/MM/DD`（**民國年**） |

時間戳欄位另有兩種：`updated_at`／`dumped_at` 為帶時區的 ISO8601（長度 32），
而 `exported_at`（`portfolio_backup_sample.json`）與 `fund_history_sample.csv` 的查詢時間為**無時區**形式（長度 19）。

⚠️ **2026-09-21 更正：`nav_points[][0]` 的日期與時間之間是半形空格，不是 `T`**
（**有意識的更正，不是漏刪** · 日期 **2026-09-21** · 決策者：**E 組資料工程組** · 由獨立稽核 C 組指出）。

**實測**（240 個元素逐一掃過，輸出見 §5.8）：長度全為 19、第 11 個字元（索引 10）全為半形空格
（`ord` ＝ 32）、相異遮罩只有一種 `9999-99-99 99:99:99`、**含 `T` 的元素是 0 個**。

⚠️ **舊表述的代價正好打在本節的存在理由上**：本節整節就是為了記「**同一個日期有幾種寫法**」，
而 `T` 分隔與空格分隔**長度都是 19**、只差那一個字元 ——
把後者寫成前者，等於**把本節要記的那個差異自己抹掉**，還順便讓它和下一段那兩個真的帶 `T` 的欄位混成一種。

**真正是 `T` 的是另外那兩處**：`templates/portfolio_backup_sample.json` 的 `exported_at`、
以及 `templates/fund_history_sample.csv` 的 `首次查詢`／`最近查詢`，
三者遮罩皆為 `9999-99-99A99:99:99`（依 §1 慣例，`T` 是英文字母故寫 `A`）。

📌 **「五種寫法」這個總數不受影響**：上表 6 個落點對應 5 種相異形態
（`date` 物件／`YYYY-MM-DD`／`YYYY-MM-DD HH:MM:SS`／`YYYY/MM/DD`／`YYY/MM/DD`），
更正前後都是 5 —— 換掉的是其中一種的長相，不是種類數。

---

## 4. 本輪的環境限制（影響哪些格子填 `查不到`）

實測結果，逐項列出：

| 套件／檔案 | 本環境狀態 | 連帶影響 |
|---|---|---|
| `pandas` / `pyarrow` | 系統環境**未安裝** | 本輪改以**安裝到暫存目錄**後讀取 parquet（未改動 repo 任何檔案）。派工單假設可直接使用，實測不成立 |
| `gspread` | import 失敗 | §2.6 全數 `查不到` |
| `google.oauth2` | import 失敗 | §2.6 全數 `查不到` |
| `streamlit` | import 失敗 | 無法走 `st.secrets` 取憑證 |
| `requests` | 可用 | 但本輪**未對外發出任何請求**（純唯讀盤點） |
| `.streamlit/secrets.toml` | **不存在** | §2.6 全數 `查不到` |

本輪**未改動任何 `.py`**，亦未執行任何會寫入 repo 的程式。

---

## 5. 方法：指令與逐字輸出

~~以下指令皆在 `0b08201` 上實跑，輸出照抄。~~
→ **以下指令皆在 `8e4ce6c` 上實跑，輸出照抄**（2026-09-21 全檔重跑；更正理由見本文開頭的基準註）。
⚠️ **重跑的結果**：除了 §5.1 副檔名普查那格的 `.md` 數之外，其餘各條輸出與換基準前**逐字相同**。

### 5.1 持久化落點的搜尋（副檔名面向）

⚠️ **2026-09-21：本節三條指令由 `git ls-files` 改寫為 `git ls-tree -r --name-only 8e4ce6c`**
（**有意識的更正，不是漏刪**；決策者：**E 組資料工程組**）。
**理由**：`git ls-files` 讀的是**索引**，會跟著工作樹跑 —— 它產出的數字**釘不住任何基準**，
而本文開頭那格寫錯基準的 `.md` 數**正是這樣進來的**。改用 `git ls-tree` 之後，
指令自己帶著基準，下一個人照跑必定拿到同一個數字。
✅ **兩種寫法本輪各跑一次、輸出逐行相同**（`diff` 三條皆無差異），所以下方輸出**一字未改**。

命令（基準 `8e4ce6c`）：

```
git ls-tree -r --name-only 8e4ce6c | grep -iE '\.(db|sqlite|sqlite3|csv|tsv|parquet|feather|pkl|pickle|h5|hdf5|xlsx|xls|duckdb)$'
```

輸出：

```
data_cache/fred_indicators.parquet
data_cache/spx_history.parquet
data_cache/twii_history.parquet
data_cache/vix_history.parquet
templates/fund_history_sample.csv
templates/nav_history_sample.csv
templates/nav_history_sample_roc.csv
```

⚠️ **這一條字表當時漏了 `.json`** —— 於是 `snap.json`、`cache/nav/`、`config/` 與兩個
`macro_weights_active.json` 在第一輪掃描中**完全沒有出現**。補掃的命令：

```
git ls-tree -r --name-only 8e4ce6c | grep '\.json$' | grep -v node_modules
```

輸出：

```
.devcontainer/devcontainer.json
cache/nav/<基金代號>.json          ← 本文遮蔽：原輸出此處為實際基金代號
config/macro_weights_active.json
config/preset_funds.json
data_cache/metadata.json
services/config/macro_weights_active.json
snap.json
templates/portfolio_backup_sample.json
templates/preset_funds_sample.json
tests/doc_counters_baseline.json
```

⚠️ **上一段輸出有一處遮蔽**：`cache/nav/` 底下那一檔的**檔名即基金代號**，依 §1 的公開性處置換成佔位符。
遮蔽處已就地標示，**未刪行、未改變行數**，其餘輸出逐字照抄。

全 repo 的副檔名普查（確認沒有第三類資料副檔名被漏掉）：

```
git ls-tree -r --name-only 8e4ce6c | sed 's/.*\///' | grep -oE '\.[A-Za-z0-9]+$' | sort | uniq -c | sort -rn
```

輸出（節錄承載資料的部分）：

```
    678 .py
     53 .md
     11 .html
     10 .json
      8 .yml
      4 .parquet
      3 .txt
      3 .csv
      2 .example
      1 .yaml
      1 .toml
      1 .sh
      1 .ini
```

⚠️ **上面這格就是本文開頭基準註在講的那一格**：`53 .md` 是 `8e4ce6c` 的數字，
同一條指令在 `0b08201` 回的是 `52`（兩個 revision 之間多了兩個 `.md` 檔）。
換基準之後這個數字**自己就對了**，故**不加刪除線** —— 本文體例：描述內容的計數就地改，
加刪除線的是被推翻的**表述**，不是被更新的**數字**。

`.txt` 三檔經 `git ls-tree -r --name-only 8e4ce6c | grep '\.txt$'` 確認為 `requirements.txt`／
`requirements-dev.txt`／`mcp_server/requirements.txt`（相依套件清單，非資料）；`.yml`／`.yaml` 為 CI workflow；
`.toml`／`.ini` 為 Streamlit 與 pytest 設定。此三類**不列入本盤點**。

### 5.2 落點的搜尋（寫入 API 面向）

副檔名只看得到**已經落地**的檔，看不到**程式宣告但尚未產生**的落點，故另跑一次 API 面向：

```
git grep -lE 'to_parquet|to_csv\(|to_json\(|to_pickle|read_parquet|read_csv\(|json\.dump|pickle\.dump|sqlite3|create_engine|duckdb|\.to_feather|h5py|shelve' -- '*.py' ':!tests/*'
```

此指令命中 28 個 `.py` 檔（基準 `8e4ce6c`，2026-09-21 重跑；同一條在 `0b08201` 亦為 28 檔），再以路徑常數掃描取得實際落點宣告：

```
git grep -nE '_CACHE_DIR *=|_DIR *= *Path|_LOCAL_FILE *=|DATA_CACHE|data_cache' -- '*.py' ':!tests/*'
```

落點存在性以 `os.path` 逐一檢查，輸出：

```
DIR   存在  data_cache                                     檔數=5
----  不存在 data_cache/ai_cache.json
----  不存在 data_cache/batch
----  不存在 data_cache/macro_thresholds_global.json
DIR   存在  cache                                          檔數=1
DIR   存在  cache/nav                                      檔數=1
----  不存在 cache/nav_history
----  不存在 cache/fundclear
----  不存在 cache/fred_release
----  不存在 cache/fund_pool
----  不存在 cache/fund_pool/pool.json
----  不存在 cache/portfolio_perf
----  不存在 cache/portfolio_perf/perf_history.json
----  不存在 /tmp/fund_cache
----  不存在 /content/fund_cache
----  不存在 .streamlit/secrets.toml
```

`metadata.json` 宣告列數與 parquet 實際列數的核對，輸出：

```
  fred_indicators    metadata= 13654 parquet= 13654 match=True
  vix_history        metadata=  3841 parquet=  3841 match=True
  spx_history        metadata=  3839 parquet=  3839 match=True
  twii_history       metadata=  3726 parquet=  3726 match=True
```

### 5.3 `snap.json` 的 `metrics` 逐欄 null 統計

輸出照抄（`present` ＝ 出現檔數，`null` ＝ 該欄為 null 的檔數，母體 8 檔）：

```
   inception_date   present=8  null=0  -> has values
   ret_3y_ann       present=8  null=8  -> ALL-NULL
   ret_3y_cum       present=8  null=8  -> ALL-NULL
   ret_3y           present=8  null=8  -> ALL-NULL
   sharpe           present=8  null=0  -> has values
   std_1y           present=8  null=0  -> has values
   max_drawdown     present=8  null=8  -> ALL-NULL
   ret_5y_ann       present=8  null=8  -> ALL-NULL
   ret_5y_cum       present=8  null=8  -> ALL-NULL
   ret_5y           present=8  null=8  -> ALL-NULL
   nav              present=8  null=0  -> has values
```

### 5.4 FRED series：宣告 vs 實有

以 AST 解析 `FRED_SERIES_IDS`（**刻意不用字串切割** —— 先前用 `split(')')` 會被註解裡的
`(Broad)` 括號截斷，得出錯誤結論），輸出：

```
AST 解析宣告 (n=11): ['DGS10', 'DGS2', 'DGS3MO', 'BAMLH0A0HYM2', 'M2SL', 'WALCL', 'CPIAUCSL', 'UNRATE', 'DTWEXBGS', 'PPIACO', 'PCOPPUSDM']
parquet 實有 (n=9): ['BAMLH0A0HYM2', 'CPIAUCSL', 'DGS10', 'DGS2', 'DGS3MO', 'DTWEXBGS', 'M2SL', 'UNRATE', 'WALCL']
宣告了但 parquet 沒有 : ['PCOPPUSDM', 'PPIACO']
parquet 有但未宣告   : []
```

### 5.5 正控與負控

- **正控**：`git grep -l 'data_cache' -- '*.py'` 命中 15 檔、`git grep -c 'to_parquet' -- '*.py'` 命中 13 檔（基準 `8e4ce6c`，2026-09-21 重跑；兩者在 `0b08201` 的數字相同）—— 掃描方法確實看得到東西。
- **負控**：**本組自訂隨機串，未列出** → 0 命中（基準 `8e4ce6c`，2026-09-21 重跑；`git grep` 與 `find -name` 兩種形態各跑一次，皆為 0）。

### 5.6 本輪字表**沒有**涵蓋的範圍（誠實揭露，不是免責）

- 動態組出的路徑（以變數或 f-string 拼接、未出現字面常數者）。
- 第三方 SDK 自帶的落地機制（`gspread` 本地快取、`yfinance` 快取等）。
- 環境變數指定的路徑（本輪環境未設定相關變數）。
- 執行期才產生、且不在 `.gitignore` 白名單內的檔案 —— 本 checkout 未跑過應用程式。
- 線上／雲端環境的實際內容（本輪僅看本機 checkout）。

⚠️ **2026-09-21 補一項本節原本沒寫、而且是本輪最貴的一項**：
上列五項講的都是「**檔案**可能漏掉哪些」 —— 本節**整段預設了資料落在檔案裡**。
`_Ledgers`／`_T7_State`／`_持倉總覽` 三個分頁就是從這個預設底下掉出去的：
它們不是檔案，也不是路徑，**是遠端試算表的分頁**，五項裡沒有一項描述得到它們。

- **存在本機檔案系統以外的落點** —— Google Sheets 分頁、外部 API 的遠端狀態。
  §5.7 補了一條分頁名常數掃描，但**那一條自己也有洞**（見 §5.7 末段逐項列出）。

因此本文採**分類敘述**，不寫「只有 N 個資料落點」這種需要「沒有漏看」才成立的句子。
§2 各表列出的是**本輪已知**的落點與欄位，可被後續補充。
⚠️ **本輪把這條規矩往回套到本文自己身上，改掉了兩處違反它的表述**：
一處是 §2.1 的舊標題（自稱是本輪「唯一」讀得到真實資料的一批），
另一處是本文開頭的舊基準註（自稱指令與輸出「皆」在該基準上實跑）。
兩句都是那種需要「沒有漏看」才成立的句子，而且兩句都被本文自己的內容當場推翻 ——
前者被 §2.2–§2.5 推翻，後者被 §5.1 的 `.md` 數推翻。

### 5.7 分頁（worksheet）名稱常數掃描 —— 2026-09-21 新增

§5.1／§5.2 的字表全部指向**本機檔案**，看不到「資料存放在 Google Sheets 的某個分頁裡」這種落點；
§2.6 那份 Sheets 清單在本節出現之前，**沒有任何指令為它的覆蓋率背書**（理由見 §2.6 表下註）。
本節補一條**常數宣告面向**的掃描。

命令（基準 `8e4ce6c`）：

```
git grep -nE '^[A-Z_0-9]*(TAB|WS|WORKSHEET)[A-Z_0-9]* *= *"' 8e4ce6c -- '*.py'
```

輸出（13 行，基準 `8e4ce6c`，逐字照抄）：

```
8e4ce6c:repositories/ledger_repository.py:32:LEDGER_TAB = "_Ledgers"
8e4ce6c:repositories/macro/alternate.py:35:DEFILLAMA_STABLECOIN_URL = "https://stablecoins.llama.fi/stablecoincharts/all"
8e4ce6c:repositories/news_repository.py:470:_GOOGLE_NEWS_RSS = "https://news.google.com/rss/search"
8e4ce6c:repositories/policy/_helpers.py:52:DEFAULT_WORKSHEET = "Policies"
8e4ce6c:repositories/policy/v2.py:45:_RESERVED_TAB_PREFIX = "_"
8e4ce6c:repositories/pool_repository.py:26:_WS_POOL = "_fund_pool"
8e4ce6c:repositories/portfolio_perf_repository.py:38:_WS_PERF = "_portfolio_perf_history"
8e4ce6c:repositories/snapshot_repository.py:34:T7_STATE_TAB = "_T7_State"
8e4ce6c:repositories/snapshot_repository.py:39:HOLDINGS_TAB = "_持倉總覽"
8e4ce6c:services/macro/weights_store.py:34:_GS_WORKSHEET = "_macro_weights"
8e4ce6c:services/nav_history_gs.py:65:_WS_NAV = "nav_history"
8e4ce6c:tests/test_wf03_research_batch.py:97:_SK_ROWS = "v03_research_batch_rows"
8e4ce6c:ui/tab_batch_analysis.py:56:_K_ROWS = "batch_rows"        # dict[str, row] 已完成結果(續跑用)
```

**人工判讀**（基準 `8e4ce6c`）：13 行裡 **9 行與分頁有關** ——
8 個分頁名常數（`LEDGER_TAB`／`DEFAULT_WORKSHEET`／`_WS_POOL`／`_WS_PERF`／`T7_STATE_TAB`／
`HOLDINGS_TAB`／`_GS_WORKSHEET`／`_WS_NAV`）＋ 1 個分頁命名規則（`_RESERVED_TAB_PREFIX`）。
另 **4 行是誤抓**：`STABLECOIN` 內含 `TAB`，`NEWS` 與 `ROWS` 內含 `WS`。
⚠️ **會多抓是設計，不是瑕疵** —— 同 `CLAUDE.md` §-1.5.1c 判定 2 的驗證指令慣例：
寧可多抓、不可漏抓，命中之後**人工逐一判讀**。為了乾淨而收窄字表，正是 §2.6 那次漏掉三個分頁的病因。

- **正控**：本條指令在 `8e4ce6c` 上看得見 §2.6 原本就登記過的 5 個分頁常數
  （`DEFAULT_WORKSHEET`／`_WS_POOL`／`_WS_PERF`／`_WS_NAV`／`_GS_WORKSHEET`）—— 方法確實看得到東西。
- **負控**：**本組自訂隨機串，未列出** → 0 命中（基準 `8e4ce6c`）。

#### ⚠️ 單一字表必漏 —— 本輪用兩種形態各跑一次，兩邊漏掉的東西不一樣

**第二法（呼叫點面向）**，命令（基準 `8e4ce6c`）：

```
git grep -nE '\.worksheet\(|add_worksheet\(title=' 8e4ce6c -- '*.py' ':!tests/*'
```

它在 `repositories/snapshot_repository.py` 上是 **0 命中**（`exit=1`，基準 `8e4ce6c`）——
因為該檔把 `sh.worksheet` 當**函式物件**傳進退避包裝（`_with_quota_retry(sh.worksheet, T7_STATE_TAB)`），
從頭到尾沒有寫出 `.worksheet(` 這個字面。
→ **`_T7_State` 與 `_持倉總覽` 兩個分頁，在第二法下完全隱形。**

**第一法漏的是另一邊**：獨立稽核 C 組回報它自己用的字表是
`^[A-Z_]*(TAB|WS|WORKSHEET)[A-Z_]* *= *"` —— **`[A-Z_]` 不含數字**，
於是 `T7_STATE_TAB`（`T7_` 裡有一個 `7`）**抓不到**；`_T7_State` 是它**定點閱讀**撿出來的，不是掃出來的。
本輪把兩式在同一基準上對跑（基準 `8e4ce6c`）：含數字版 13 行、不含數字版 12 行，
`diff` 的唯一差異就是 `repositories/snapshot_repository.py:34` 那一行。

→ **兩條字表的洞方向相反，任何一條單獨用都會漏掉至少一個分頁；第三個分頁靠的是讀檔，不是掃。**
這正是 `CLAUDE.md` §-2.A 第 8 款那條「清理與稽核一律用兩種方法；只用字串直掃，結構上必然漏」的同型實例。

#### ⚠️ 本條掃描**沒有**涵蓋的範圍（誠實揭露，不是免責）

- **動態組出的分頁名** —— V2 schema 的分頁名**就是 `policy_id` 本身**
  （`repositories/policy/v2.py` 的 `sh.worksheet(tab)`，`tab` 是執行期算出來的），沒有字面常數可掃。
  §2.6 該列是**讀 `v2.py` 才有的**，不是掃出來的。
- **行首以外的宣告** —— 本條釘 `^`，縮排的類別屬性、函式內區域變數、dict 的值一律看不到。
- **不叫 `TAB`／`WS`／`WORKSHEET` 的命名** —— 例如 `_SHEET`、`_PAGE`，或別的縮寫。
- **不是常數的字面值** —— `sh.worksheet("某分頁")` 這種直接寫死在呼叫點的形態。
- **非 `.py` 的宣告** —— 設定檔、環境變數、Apps Script、以及使用者自己在 Sheet 上手動開的分頁。
- **本輪只掃分頁名，不掃分頁內容** —— 無憑證，§2.6 全列仍為 `查不到`。

⛔ **因此本文不寫「Sheets 分頁已經窮舉」。**
§2.6 列出的是**本輪已知**的分頁 —— 兩種掃描形態 ＋ 定點閱讀三者的聯集，**可被後續補充**。

### 5.8 `snap.json` 字串形態複驗（2026-09-21 新增，對應 §2.3／§3 兩處更正）

讀取的是工作樹上的 `snap.json`；該檔在 `8e4ce6c` 與 `0b08201` 的 blob hash 相同，
且工作樹副本與 `8e4ce6c` 無差異（`git status --short -- snap.json` 無輸出）。

遮罩函式依 §1 統一後的慣例：數字 → `9`、英文字母 → `A`、**其餘字元原樣保留**。

命令：

```
python3 - <<'EOF'
import json, collections
funds = json.load(open('snap.json', encoding='utf-8'))['funds']
masks = collections.Counter(); idx10 = collections.Counter(); lens = collections.Counter()
n = withT = 0
for f in funds.values():
    for pt in f['nav_points']:
        s = pt[0]; n += 1; lens[len(s)] += 1
        if 'T' in s: withT += 1
        idx10[repr(s[10])] += 1
        masks[''.join('9' if c.isdigit() else ('A' if c.isalpha() else c) for c in s)] += 1
print('elements =', n); print('lengths  =', dict(lens))
print('char at idx10 =', dict(idx10)); print("elements containing 'T' =", withT)
print('distinct masks =', sorted(masks))
ps = [f['perf_source'] for f in funds.values() if f.get('perf_source')]
print('perf_source str =', len(ps), '| null =', len(funds) - len(ps))
print('perf_source masks =', dict(collections.Counter(
    ''.join('9' if c.isdigit() else ('A' if c.isalpha() else c) for c in v) for v in ps)))
EOF
```

輸出（逐字照抄）：

```
elements = 240
lengths  = {19: 240}
char at idx10 = {"' '": 240}
elements containing 'T' = 0
distinct masks = ['9999-99-99 99:99:99']
perf_source str = 3 | null = 5
perf_source masks = {'AA99': 3}
```

**這兩行輸出各推翻本文的一處舊表述**：
`elements containing 'T' = 0` 推翻 §3 的 `YYYY-MM-DDTHH:MM:SS`（B-M1）；
`perf_source masks = {'AA99': 3}` 推翻 §2.3 的「遮罩形狀 `AA99` 與 `AAAA`」——
`AAAA` 這個形態一次都沒出現（B-L1）。**「3 筆 str、5 筆 null」這半句本來就是對的，未動。**

⚠️ **本條讀的是資料內容、不是 repo 樹**，所以它不像 §5.1／§5.7 那樣能靠指令自己帶基準；
改以「blob hash 相同 ＋ 工作樹無差異」把它釘在 `8e4ce6c` 上（見本節開頭）。

---

## 6. 本份文件的已知限制

1. ~~**單組產出，未經第二組獨立複驗。**~~
   → **2026-09-21 狀態更新（不是漏刪）：已經過獨立稽核 C 組複驗，本輪依其回報修了 7 處。**
   ⚠️ **但這不等於「現在沒問題了」**，兩件事要分開讀：
   **(a)** C 組驗的是**本文第一版**；本輪新寫的 §5.7／§5.8、三列新增分頁、
   以及各處更正註，**本身沒有第三組看過**。
   **(b)** C 組自陳它的分頁字表也有洞（`[A-Z_]` 不含數字，抓不到 `T7_STATE_TAB`），
   `_T7_State` 是它定點閱讀撿出來的 —— **驗的人用的方法同樣不是窮舉**（見 §5.7 末段）。
2. §2.6 的欄位名取自原始碼常數與設定手冊，屬 schema；**本輪未讀到任何一格實際內容**，
   故其「有值／空值／格式不一致」狀態**無法判定**，一律填 `查不到`。
3. §2.2／§2.3 的樣本規模很小（1 檔 NAV 快取、8 檔基金快照），
   所述形狀僅代表**這批資料**，不代表欄位的完整值域。
4. 本文**未讀** `docs/v2/` 底下同批其他組正在產出的文件，兩份為獨立產出。
5. **§2.6 全列仍為 `查不到`，本輪沒有改變這件事。** 補上的三個分頁一樣只有 schema、沒有內容 ——
   本輪補的是「**這個分頁存在，而且本文漏掉了它**」，不是「本文現在讀得到 Sheets 了」。
6. **本輪讀的是這份 checkout 的工作樹，不是線上環境。** §2 各表描述的是
   `8e4ce6c` 這個 revision 上的檔案內容；線上 Sheets、線上快取與執行期產物**一律不在射程內**。
