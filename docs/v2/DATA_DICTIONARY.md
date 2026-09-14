# v2 資料字典與指標 SSOT（階段 1 交付物）

> **狀態**：階段 1 文件交付物。**不含任何實作**。
> **base**：`origin/main` = `9cbf03776f2a0ee6bdb5a649efb93352c40baba6`（量測日 **2026-09-14**）
> **涵蓋**：終審令階段 1 檢查表第 **1**（可用資料庫白皮書）、第 **2**（指標 SSOT 附錄）、第 **5**（持倉與交易資料模型）項。

---

## §0. 射程宣告（承重段，先讀這一段）

**本文件只涵蓋「基金儀表板」（`my-Fund-dashboard`）。**
股票／ETF 戰情室由另一條線負責；跨儀表板共用的 `v2_holdings` 契約，
**在此僅記載基金側的需求與待協調項**，**不替股票側決定任何欄位**。

⚠️ **這一段是承重的。** 少了它，下一個人會把這份白皮書當成全系統的資料字典，
然後在一份**只量過一半**的文件上做決定 —— 那正是本專案 `CLAUDE.md §-2.A` 反覆記載的事故形狀。

**具體邊界**：

| 範圍 | 本文件的處理 |
|---|---|
| 基金側資料源、欄位、指標 | ✅ 本文件盤點並定義 |
| `v2_transactions`（基金側交易） | ✅ 本文件定義完整欄位 |
| `v2_holdings` 的**基金側需求**與**唯讀引用方式** | ✅ 本文件定義 |
| `v2_holdings` 的 `asset_class` 完整列舉、ETF 專屬欄位 | ⛔ **不決定** → 見 §4.7 跨儀表板待協調項 |
| 股票／ETF 指標（本益比 TTM 等） | ⛔ 不盤點。**例外**：若基金側自己也在用，則以基金側實際用法為準（實測結果見 §3.1.3） |

> 📌 **一則過程揭露（`CLAUDE.md §-2` 規則 6）**：本任務的**第一版派工單**要求一併盤點姊妹 repo
> `my-stock-dashboard`，該指示**事後被總管撤回**（客戶明示本 session 只負責基金儀表板）。
> 撤回前姊妹 repo 已被 clone 至 `/home/user/linchen-20200325/my-stock-dashboard`，
> **本文件未讀取、未量測、未引用該 repo 任何內容**。本文件所有數字**一律出自 `my-Fund-dashboard`**。

---

## §1. 量測方法與其射程（先講怎麼量的，再看數字）

本文件的每一個數字都附「怎麼量的」。**量不到的一律寫「量不到」並說明射程，不估數字**（`CLAUDE.md §1` Fail Loud）。

### 1.1 環境限制（決定了哪些東西量得到）

| 限制 | 後果 |
|---|---|
| ⛔ 禁止打任何外部 API（TDCC／FundClear／MoneyDJ／FinMind／FRED／Yahoo…） | **所有「實際回應延遲」皆無法量測**。§2.4 的延遲一律是**程式碼宣告值**（timeout／retries／backoff），**不是實測牆鐘時間** |
| ⛔ 禁止對 Google Sheets 做任何寫入；且本環境無憑證 | **Google Sheets 上的實際資料列數、實際缺漏率無法量測**（見 §2.3.3） |
| ⛔ 禁止 `pip install`；環境無 `pandas`／`pyarrow`／`numpy`／`snappy` | `data_cache/*.parquet` 無法用標準工具讀取 → 本文件**自行以純 Python 實作 snappy + thrift-compact + parquet 解碼器**取得數字（驗證方式見 1.2） |

### 1.2 parquet 解碼器的正確性驗證（為什麼可以信這些數字）

`CLAUDE.md` 記載本專案累計十次以上「假檢查」，形狀一律是**工具沒量到它宣稱在量的東西**。
故本文件對自製解碼器做了**四道獨立驗證**，四道全過才採用其輸出：

| # | 驗證 | 結果 |
|---|---|---|
| 1 | 解碼器回報的 `num_rows` vs `data_cache/metadata.json` 宣告的 `row_count` | ✅ 四檔全部一致 |
| 2 | 解碼出的 `max(date)` vs `metadata.json` 的 `last_updated` | ✅ 一致（vix/spx/twii = 2026-09-11；fred = 2026-09-10） |
| 3 | **外部世界事實**：VIX 歷史最高收盤 | ✅ 解碼得 **82.69 於 2020-03-16** —— 與真實 COVID 紀錄相符 |
| 4 | **holiday 形狀**：TWII 的長缺口是否落在農曆年 | ✅ 最長 5 個缺口為 2023-01-17→01-30(13d)、2012-01-18→01-30(12d)、2013-02-06→02-18(12d)、2016-02-03→02-15(12d)、2019-01-30→02-11(12d) —— **全部是農曆春節** |

> ⚠️ **一次真實的假檢查，就地記錄（這比上面的數字更值得讀）**
> 本文件的**第一版** FRED 涵蓋度檢查，用「4-byte 小端長度前綴 + 字串」去比對 parquet bytes，
> 並跑了**負向對照**（`ZZZZFAKE`／`NAPM`／`DGS10_NOT_REAL` 全部回 `False`）→ 看起來很嚴謹，
> 結論是「41 個宣告 series 中 **7** 個在快取裡」。
> **那個 7 是錯的，正確答案是 9。**
> **成因**：dictionary page 是 **snappy 壓縮**的，`DGS2`／`DGS3MO` 的長度前綴被壓成了 back-reference，
> 字面上不存在 → 檢查恆假。
> ⛔ **關鍵教訓**：**負向對照只能證明「沒有偽陽性」，永遠證不出「沒有偽陰性」。**
> 抓到它的不是負向對照，是一個**矛盾**：`strings` 看得到 `DGS2`，而我的檢查說看不到。
> → 本文件其餘所有「N 個之中有 M 個」的數字，一律附**正向對照 + 矛盾交叉檢查**，不只附負向對照。

### 1.3 本文件明確**未**涵蓋的範圍（誠實揭露，不是免責）

- **未讀** `SPEC.md` / `ARCHITECTURE.md` / `STATE.md` / `BACKLOG.md` / `TODO.md` 全文（僅針對性查證）。
- **未讀**姊妹 repo 任何內容（§0 已述）。
- **未執行**任何測試、未啟動任何 UI、未做任何 runtime 量測。
- **未查證** Google Sheets 上的實際資料（無憑證，且禁止寫入）。
- 本文件所有盤點**均為單組產出，未經第二組獨立複驗**（`CLAUDE.md §-2` 規則 6）。
  ⛔ 在獨立稽核完成前，**不得**把本文件任何一句當成「已查證的事實」去支撐下一步實作決策。

⚠️ **本文件刻意不寫「只有 N 處」「全部都是 X」這類能被一條 grep 推翻的全稱句**
（`CLAUDE.md §-1.5.1c 判定 2` 的方法教訓）。凡是盤點，一律寫成**分類敘述 ＋ 明列未涵蓋範圍**。

---

## §2. 第 1 項｜可用資料庫白皮書

### 2.1 實體來源總表

**權威分級沿用 `CLAUDE.md §2.1` 的 5-Tier**（衝突時上層贏，**禁止平均**）。
⚠️ `CLAUDE.md §2.1` 那張表的多處 evidence 路徑**已知過期並就地更正過**；
下表路徑為**本輪重新量測**（`git grep` + `ls` 實跑，量測日 2026-09-14），**未照抄該表**。

| Tier | 來源 | 基金側用途 | 現行實作位置（本輪實測） | 更新頻率 |
|---|---|---|---|---|
| T1 | **FundClear** 境外基金資訊觀測站 | 境外 NAV／meta／配息 | `repositories/fund/sources.py::_src_fundclear_nav`／`_src_fundclear_meta`／`_src_fundclear_div`；另 `repositories/fundclear_offshore.py` | T+1 |
| T1 | **TDCC** 集保 OpenAPI | 境內 NAV／基金清單／meta | `repositories/fund/sources.py::_src_tdcc_meta`／`_tdcc_get`（3-2／3-4 兩個 endpoint） | T+1 |
| T1 | **SITCA** 投信投顧公會 | 境內 meta（`fund_name`／`nav_latest`） | `repositories/fund/sources.py::_src_sitca_meta`／`_src_sitca_nav` | T+1 |
| T1 | **FRED** | 總經指標、無風險利率來源 | `repositories/macro/fred.py::fetch_fred`／`fetch_fred_batch` | 各 series 不同（見 `CLAUDE.md §2.3`） |
| T2 | **FinMind** | TW 總經（NDC 景氣）、外資買賣超 | `repositories/macro_tw_local_repository.py`、`repositories/hot_money_repository.py` | T+1 ～ 月 |
| T2 | **Yahoo Finance** | FX、指數、基準（SPY／QQQ） | `repositories/macro/yf.py::fetch_yf_close`／`fetch_benchmark_close` | EOD |
| T3 | **MoneyDJ**（主站 + `tcbbankfund` + `chubb` 等子網域） | NAV 歷史、績效 wb01、風險 wb07、配息 wb05、持股 | `repositories/fund/nav_metrics.py`（`fetch_nav`／`fetch_performance_wb01`／`fetch_risk_metrics`／`fetch_holdings`） | T+1 ～ T+3；wb01/wb05/wb07 為**月更** |
| T3 | **Cnyes 鉅亨** | NAV／配息／持股 fallback | `repositories/fund/sources.py::fetch_nav_cnyes`／`fetch_div_cnyes`／`fetch_holdings_cnyes` | T+1 |
| T3 | **Morningstar** | NAV／持股／secid 解析 fallback | `repositories/fund/sources.py::_src_morningstar_nav`／`fetch_holdings_morningstar` | T+1 |
| T3 | **保單發行商子網域**（Allianz／台灣人壽／富蘭克林／JPMorgan…） | 保單連結基金 NAV | `sources.py::_src_allianzgi_nav`／`_src_taiwanlife_nav`／`_src_franklin_nav`／`_src_jpmorgan_nav` | T+1 |
| T5 | **Google Sheets** | 保單政策、交易帳、NAV 歷史、選股池、組合績效 | `repositories/policy/`、`repositories/ledger_repository.py`、`services/nav_history_gs.py`、`repositories/pool_repository.py`、`repositories/portfolio_perf_repository.py` | 使用者寫入即時 |

⚠️ **本表是「本輪查到的」，不是窮舉。** 未涵蓋：`repositories/external_market_repository.py`（stooq／cboe，風險雷達用）、
`repositories/news_repository.py`（RSS，非數值）、`repositories/ai_cache.py`、`repositories/snapshot_repository.py` 的上游。

### 2.2 欄位字典（逐儲存體）

#### 2.2.1 `_Ledgers`（v1 交易帳，Google Sheets）— **v2_transactions 的直接前身**

SSOT：`repositories/ledger_repository.py::LEDGER_COLS`（實測 9 欄）

| 欄位 | 型別 | 必填 | 語意 | 幣別 | v2 對應 |
|---|---|---|---|---|---|
| `policy_id` | str | ✅ | 保單識別碼 | — | `v2_transactions.account_id` |
| `date` | str(ISO) | ✅ | 交易日 | — | `trade_date` |
| `code` | str | ✅ | 基金代碼 | — | `instrument_code` |
| `action` | str | ✅ | `buy`／`sell`／`dividend`／`fee`／`fx` | — | `txn_type`（需擴充，見 §4.1） |
| `units` | float | ✅ | 單位數 | 單位 | `units` |
| `nav_at_action` | float | 選填 | 當日淨值 | **原幣** | `price_orig` |
| `twd` | float | 選填 | 台幣金額 | **TWD** | `amount_twd` |
| `fee` | float | 選填 | 費用 | ⚠️ **未宣告幣別** | `fee_orig` ＋ `fee_ccy`（見 §5 缺口 G-4） |
| `note` | str | 選填 | 備註 | — | `note` |

- **主鍵（程式碼自陳）**：`(policy_id, code, date, action, units)`
- `KNOWN_ACTIONS = ("buy","sell","dividend","fee","fx")`；程式碼自陳**不在列表內不攔截**（「呼叫端自由」）→ ⚠️ 這是 v2 必須收緊的點（見 §4.1）。

#### 2.2.2 保單政策表（v1，Google Sheets，每保單一個 worksheet）

SSOT：`docs/POLICY_SHEETS_SETUP.md`（9 欄）＋ `repositories/policy/v2.py`

| 欄位 | 型別 | 必填 | 語意 | 幣別 |
|---|---|---|---|---|
| `policy_id` | str | ✅ | 保單唯一識別碼 | — |
| `policy_name` | str | ✅ | 顯示名稱 | — |
| `fund_url` | str | ✅ | 基金代碼或 MoneyDJ URL（程式自動萃取代碼） | — |
| `invest_twd` | int | ✅ | 台幣投入**金額**（**不是權重**；空白視為 0） | **TWD** |
| `invest_date` | str | 選填 | 進場日 | — |
| `currency` | str | 選填 | 計價幣別 | — |
| `fx_at_buy` | float | 選填 | **進場匯率** | TWD/原幣 |
| `notes` | str | 選填 | 備註 | — |
| `policy_tier` | str | 選填 | `core`／`satellite`；空→退基金名啟發 | — |

- ⚠️ **複合主鍵 `(policy_id, fund_url)`**，同一保單同一檔基金分多筆買 → `invest_twd` **加總**（`CLAUDE.md §4.6` 已就地更正過此處的舊錯誤描述）。
- ⚠️ **權重是算出來的、不是存的**：核心／衛星比例 = Σ `invest_twd` 加權。Sheet 端**不存任何 0~1 權重**。

#### 2.2.3 `nav_history`（v1，獨立一本 Google Sheet）

SSOT：`services/nav_history_gs.py::_NAV_HEADERS`（實測 7 欄）

`code` | `date` | `nav` | `fund_name` | `source` | `recorded_at` | `currency`

- ⚠️ 程式碼自陳既有分頁可能只有 **6 欄**（`currency` 為後加），有「只補缺的那幾格」的 header 修補邏輯 → **v2 ETL 必須容忍 6 欄與 7 欄兩種歷史形狀**（見 §2.5）。

#### 2.2.4 `snap.json`（v1 本地快照，repo 根目錄）

實測：8 檔基金，`dumped_at = 2026-08-10T18:50:54Z`。
每檔 7 個 key：`fund_name`／`category`／`inception_date`／`nav_points`／`metrics`(11)／`perf`(8)／`perf_source`。

### 2.3 歷史缺漏率統計（**實測**）

> **量測方法**：對 `data_cache/*.parquet` 以自製解碼器（驗證見 §1.2）取出完整 `date` 欄，
> 以 **Mon–Fri 平日**為分母計算涵蓋率。
> ⚠️ **分母不排除市場假日與國定假日** → 因此「涵蓋率」是**下界**、「缺漏率」是**上界**。
> ⚠️ **量測日 2026-09-14。此為會漂移的量測值 —— 引用前請現場重量，不要引用本表。**

#### 2.3.1 指數／波動度序列

| 資料集 | 列數 | 期間 | 平日數 | 涵蓋率（下界） | 缺漏率（上界） | null | 最長缺口 |
|---|---|---|---|---|---|---|---|
| `vix_history` | 3841 | 2011-06-07 ～ 2026-09-11 | 3984 | 96.41% | **3.59%** | 0 | 5d |
| `spx_history` | 3839 | 2011-06-07 ～ 2026-09-11 | 3984 | 96.36% | **3.64%** | 0 | 5d |
| `twii_history` | 3726 | 2011-06-07 ～ 2026-09-11 | 3984 | 93.52% | **6.48%** | 0 | **13d** |

**判讀（這才是重點，不是三個百分比）**：
- TWII 缺漏率（6.48%）顯著高於 SPX（3.64%），**差值 ≈ 2.84 個百分點 ≈ 每年 7 個交易日** ——
  與台灣多出的**農曆春節連假**吻合（§1.2 驗證 4 已逐一列出那 5 個 12–13 天缺口）。
- ⇒ **這三個數字幾乎全部是「正常休市」，不是「抓取失敗」。**
  ⛔ **不得**把它們當成資料品質指標直接搬進 v2 的告警門檻。
- ⚠️ **要得到真正的「抓取失敗率」，必須有交易日曆**；而 `CLAUDE.md §4.5` 明載本專案
  **不使用**任何第三方 trading calendar lib（`requirements.txt` 無 `pandas_market_calendars`／`exchange_calendars`）。
  → **本文件量不到「排除假日後的真實缺漏率」**，這是 v2 的待決缺口（見 §5 缺口 G-6）。

#### 2.3.2 FRED 指標快取（`fred_indicators.parquet`，13654 列）

**涵蓋度**：`shared/fred_series.py` 宣告 **41** 個 unique series ID，快取內實際出現 **9** 個。
> **量測方法**：對 41 個宣告值逐一做 raw bytes 比對；
> **正向對照** `DGS10` → 命中；**負向對照** `ZZZZFAKE`／`NAPM`／`ISPMANPMI`／`T10Y2Y`／`ICSA` → 全部未命中；
> **偽陽性審計**：程式檢查「任一 ID 是否為另一 ID 的子字串」→ 無警告，故 raw 比對在此安全。
> （第一版用長度前綴比對得到 7，**已證實為偽陰性**，成因與教訓見 §1.2。）

| series | 列數 | 期間 | null | 推得頻率 |
|---|---|---|---|---|
| `DGS10` | 3816 | 2011-06-07 ～ 2026-09-10 | 0 | 日（交易日） |
| `DGS2` | 3816 | 2011-06-07 ～ 2026-09-10 | 0 | 日（交易日） |
| `DGS3MO` | 3816 | 2011-06-07 ～ 2026-09-10 | 0 | 日（交易日） |
| `BAMLH0A0HYM2` | 858 | **2023-06-05** ～ 2026-09-10 | 0 | 日（交易日） |
| `WALCL` | 797 | 2011-06-08 ～ 2026-09-09 | 0 | 週 |
| `UNRATE` | 181 | 2011-06-01 ～ **2026-08-01** | 0 | 月 |
| `M2SL` | 179 | 2011-06-01 ～ **2026-04-01** | 0 | 月 |
| `CPIAUCSL` | 178 | 2011-06-01 ～ **2026-04-01** | 0 | 月 |
| `DTWEXBGS` | **13** | **2026-06-05** ～ 2026-09-04 | 0 | 週 |

**判讀**：
- **快取內 0 個 null cell** —— 這個快取是「只存成功結果」的（與 `CLAUDE.md §-1.5.1c 判定 4` 記載的
  positive-only 快取設計一致）。⇒ **缺漏在此快取中不可見，它被表達為「那一列根本不存在」。**
  ⛔ 這代表**不能**用 null 率衡量此資料源的品質。
- **三條月頻序列的最後一期落差很大**：`UNRATE` 到 2026-08，`M2SL`／`CPIAUCSL` 只到 **2026-04** ——
  相對量測日 2026-09-14 已落後約 **5 個月**，遠超 `CLAUDE.md §2.4` 的月度 🔴 門檻（> 75 天）。
  ⚠️ **本文件不宣稱這是 bug** —— 它可能是「這份離線快取不是 production 取數路徑」。
  **未查證**：production 是否改走即時 FRED API 而非此快取。列為 §5 缺口 G-7。
- `DTWEXBGS` 僅 13 列、起自 2026-06-05 → **明顯是近期才加入的 series**。

#### 2.3.3 基金 NAV 的缺漏率 —— ⚠️ **量不到，且原因必須寫清楚**

**實測**：`cache/nav/` 目錄下**只有 1 個檔案**：`cache/nav/TLZF9.json`。
其內容為 `count: 10`，10 個點的日期為
2026-04-23、2026-04-22、2020-10-01、2020-02-03、2015-03-18、2013-05-02、2013-03-01、2012-10-16、2012-10-15、2011-11-18
（`source: "cache_only"`）。

⛔ **這不是一份可用來統計缺漏率的語料**：10 個點橫跨 15 年，是**稀疏降級快取**，不是日頻 NAV 序列。
**拿它算出來的任何「缺漏率」都會是一個沒有意義的數字。**

**基金 NAV 的真實歷史存放在 Google Sheets（`nav_history` 本）**，而本環境
**無憑證且被禁止寫入** → **本文件無法量測基金 NAV 的歷史缺漏率**。

**替代量測（這個量得到，且更有價值）** —— 用 `snap.json` 這份真實 v1 快照量**指標層級的缺漏**：

| 指標 | 8 檔中為 `None` 的檔數 | 缺漏率 |
|---|---|---|
| `ret_3y` / `ret_3y_ann` / `ret_3y_cum` | **8/8** | **100%** |
| `ret_5y` / `ret_5y_ann` / `ret_5y_cum` | **8/8** | **100%** |
| `max_drawdown` | **8/8** | **100%** |
| `sharpe` / `std_1y` / `nav` / `inception_date` | 0/8 | 0% |
| `perf`（wb01 績效區塊） | **5/8 無資料**（`perf_source = None`） | **62.5%** |

**成因（實測，非推測）**：該快照中 **8/8 檔的 `nav_points` 都剛好是 30 筆**，
實際日期跨度僅約 **43 個日曆日**（例：`TLZF9` 2026-06-26 ～ 2026-08-07）。
- 3Y／5Y 指標需要 3～5 年序列 → 30 筆必然算不出來 → 全部 `None`。**這是正確的 Fail Loud 行為，不是 bug。**
- ⚠️ **但它對 v2 是承重的**：`services/fund_service.py::MIN_OBS_SHARPE_SORTINO = 250`
  要求 **250 個交易日**才准自算 Sharpe/Sortino，而預設取數路徑只給 30 筆。
  ⇒ **v2 若要自算風險指標，必須先解決「長序列從哪來」**，見 §5 缺口 G-1。

#### 2.3.4 一個實測到的 v1 資料品質缺陷（直接影響第 2 項的「同類中位數」）

`snap.json` 的 `category` 欄位，**8 檔中有 5 檔存的不是類別，而是公開說明書的投資範圍段落**：

| 代碼 | `category` 長度 | 內容判定 |
|---|---|---|
| `ACCP138` | 266 字 | ⛔ 說明書段落（「1.本基金投資於國內證券投資信託事業…」） |
| `ACDD01` | 383 字 | ⛔ 說明書段落 |
| `ACDD19` | 12 字 | ⛔ 說明書片段（「中華民國境內之有價證券。」） |
| `ACTI71` | 268 字 | ⛔ 說明書段落 |
| `ACTI94` | 762 字 | ⛔ 說明書段落 |
| `JFZN3` | 3 字 | ✅ `平衡型` |
| `TLZF9` | 3 字 | ✅ `平衡型` |
| `ALBT8` | 3 字 | ✅ `股票型` |

**分布**：5 檔**境內**代碼（`ACxx`）全部污染；3 檔**境外／保單**代碼全部正常。
⚠️ **本文件不宣稱「境內代碼一律污染」** —— 樣本只有 8 檔，且**只有這一份快照**。
這是**分類敘述**：在這份 2026-08-10 的快照中，污染與「境內代碼」100% 共現。

⛔ **對 v2 的承重後果**：客戶指定「基金淨值與中位數採**同類**中位數」——
**同類分組的鍵就是 `category`**。在 5/8 的樣本上這個鍵是一段說明書文字，
**任何依它做的分組都會把每一檔基金分成自己一類，中位數 = 它自己**。
→ 見 §3.1.2 與 §5 缺口 G-2。

### 2.4 冷／熱載入延遲標註

> ⛔ **以下全部是「程式碼宣告值」，不是實測牆鐘時間。**
> 理由：本階段禁止打外部 API（§1.1）。**任何實測延遲數字都必須在解禁後重新量。**
> **量測方法**：讀 `infra/proxy.py`、`shared/ttls.py`、`shared/backoff_policy.py`、
> `infra/cache.py` 與各 fetcher 的裝飾器宣告（量測日 2026-09-14）。

#### 2.4.1 熱載入（cache hit）

| 快取型態 | 實作 | 存活時間 | 適用 |
|---|---|---|---|
| `@_ttl_cache(ttl_sec=N)` | `infra/cache.py`，自製 | `shared/ttls.py` SSOT：60／300／600／900／1800／3600 秒 | FRED、Yahoo、FX、流動性引擎 |
| `@_daily_cache` | `infra/cache.py` | **保存當日（TW UTC+8），隔日 00:00 自動 miss** | `fetch_nav`／`fetch_div`／`fetch_performance_wb01`／`fetch_risk_metrics`／`fetch_holdings` |
| `@st.cache_data` | Streamlit | 依 `ttl` 參數 | L1 `hot_money_repository`；L3 見 `EXCEPTIONS.md EX-UICACHE-1` |

**熱載入延遲**：cache hit **0 次 HTTP**（`infra/cache.py` 對 `_daily_cache` 的自陳：「同日多次呼叫：cache hit，0 HTTP」）。
實際耗時為 dict 查表，**本文件未量測，但可視為與網路無關**。

⚠️ **失敗結果不入快取**（`_daily_cache` 的 `cache_if`，v19.253 R23）：
空 Series／空 list／`{}`／`source` 含 `all_failed` 的 dict **不入 cache**。
⇒ **失敗路徑沒有熱載入，每次都會重新付出冷載入成本。** 這是 v2 做延遲預算時最容易漏掉的一項。

#### 2.4.2 冷載入（cache miss）—— 單次 HTTP 的宣告上界

`infra/proxy.py::fetch_url_with_retry` 預設：`timeout=20`、`retries=3`、`backoff_on_429=True`
- **timeout 實際被拆成 `(connect, read) = (min(5, timeout), timeout)`**
  —— 程式碼自陳理由：proxy 半死時 20s TCP 握手太久，曾是「總經載入卡 10 分鐘」的放大器之一。
- **429 退避序列**：`_RATE_LIMIT_BACKOFF_SEC = (2.0, 4.0, 8.0)` 秒

**NAV 取數的冷載入上界（`repositories/fund/nav_metrics.py::fetch_nav`，實測其呼叫參數）**：
該函式以 `timeout=25, retries=2` 逐一嘗試一個 URL 清單：

| 情境 | URL 數 | 宣告上界 |
|---|---|---|
| 境內基金（`_is_domestic_code` 為真） | 2～3 | 3 URL × 2 retries × 25s ≈ **150 秒** |
| 境外基金 | 4～5 | 5 URL × 2 retries × 25s ≈ **250 秒** |

⚠️ **這是最壞情況的宣告上界，不是預期值。** 實際會因 connect timeout 5s 快速失敗而遠低於此。
⛔ **本文件量不到預期值**（需實際打 API）。

#### 2.4.3 來源失敗冷卻（跨呼叫）

SSOT：`shared/backoff_policy.py`（實測）

| 失敗類型 | 冷卻秒數 |
|---|---|
| `unreachable` | 60 |
| `server_error` | 300 |
| `blocked` | 900 |
| `rate_limited` | 1800 |
| `not_found`(404)／`proxy_auth`(407) | **不退避**（`NO_COOLDOWN_KINDS`） |

上限 `BACKOFF_MAX_COOLDOWN_SEC = 1800`。

#### 2.4.4 零快取路徑

`services/ledger_service.py` 檔頭自陳「**§4 零快取（無 `@st.cache_data`）**」
⇒ **帳務計算每次都重算**。對 v2 的意義：`v2_holdings` 若由 `v2_transactions` 即時推導，
**延遲正比於交易筆數**，需要在 §4.2 決定是否物化（materialize）。

### 2.5 v1 → v2 遷移路徑（ETL vs 手動）

| v1 資料 | 位置 | v2 目標 | 路徑 | 理由 |
|---|---|---|---|---|
| `_Ledgers` 交易帳 | Google Sheets | `v2_transactions` | **ETL（自動）** | 9 欄對 9 欄，語意一一對應（§2.2.1），`action` 需做值域映射 |
| 保單政策表 | Google Sheets（每保單一分頁） | `v2_transactions`（推導初始買進）＋帳戶維度 | **ETL（自動）＋人工覆核** | `invest_twd` 是**金額**不是權重；但**無 `units`、無 `nav_at_buy`** → 無法單獨還原單位數，見下方 ⚠️ |
| `nav_history` | 獨立 Google Sheet | v2 價格表 | **ETL（自動）** | 需容忍 **6 欄／7 欄**兩種歷史 header 形狀（§2.2.3） |
| `snap.json` | repo 根目錄 | 不遷移 | **丟棄** | 為 2026-08-10 的一次性 debug 快照，非權威來源 |
| `cache/nav/*.json` | repo | 不遷移 | **丟棄** | 稀疏降級快取（§2.3.3），非權威 |
| `data_cache/*.parquet` | repo | 總經快取 | **可選 ETL** | 僅 9/41 series，且月頻序列已落後數月（§2.3.2） |
| 選股池 `pool_repository` | Google Sheets | v2 watchlist | **ETL（自動）** | 本輪**未逐欄盤點**（射程外） |
| 組合績效 `portfolio_perf_repository` | Google Sheets | v2 績效快照 | **ETL（自動）** | 本輪**未逐欄盤點**（射程外） |

⚠️ **保單政策表無法純自動遷移，這是本節最重要的一句**：
政策表有 `invest_twd`（台幣金額）、`fx_at_buy`（進場匯率）、`invest_date`，
但**沒有 `units`（單位數）也沒有 `nav_at_buy`（進場淨值）**。
而 `v2_transactions` 的加權移動平均成本法**需要 `units`**。
- 若用 `units = invest_twd / (fx_at_buy × nav_at_invest_date)` 回推 → **需要當日 NAV**，
  而該 NAV 必須來自 `nav_history`，**且該日可能沒有資料**（T+1／假日）。
- ⇒ **判定：政策表遷移為「ETL 回推 ＋ 人工覆核」**，且回推失敗者**必須標記，不得靜默估值**（`CLAUDE.md §1`）。
- ⇒ 這是 §5 缺口 **G-3**。

### 2.6 多幣別：原幣／台幣儲存格式與匯率結算點

#### 2.6.1 幣別正規化（v1 已有 SSOT，v2 沿用）

`services/currency.py::normalize_ccy` / `CCY_NORMALIZE`（實測）：
中文與 ISO 皆統一回 **ISO 4217 三碼**；未知值回原值大寫。
- 支援 alias：美元/美金→USD、日圓/日元/日幣→JPY、台幣/新台幣/新臺幣→TWD、人民幣→CNY 等。
- **`mode="yf"` 覆寫**：`CNY → CNH`（程式碼自陳離岸人民幣在 yfinance 較可靠）。
  ⚠️ **這是一個真實的單位陷阱**：**同一檔基金在「儲存」與「報價」時幣別碼不同**。
  ⇒ v2 **必須分開存** `ccy_iso`（帳務用）與 `ccy_quote`（報價用），**不得共用一欄**。

#### 2.6.2 儲存格式規範（v2 硬規則）

依 `CLAUDE.md §4.1` 單位陷阱與 §2.2.1 實測到的 `fee` 未宣告幣別問題，v2 一律採：

> **每一個金額欄位，都必須與一個幣別欄位成對出現；且欄名必須編碼單位。**

| 規範 | 說明 |
|---|---|
| 原幣金額 | `*_orig` ＋ 必要的 `*_ccy`（例：`amount_orig` ＋ `amount_ccy`） |
| 台幣金額 | `*_twd`（**幣別隱含為 TWD，不另設欄**） |
| 匯率 | `fx_<base>_twd`，語意固定為 **「1 單位原幣 = N 台幣」**（TWD per unit of original currency） |
| 單位數 | `units`（無幣別） |
| 比率 | `*_ratio`（0~1）；百分比 `*_pct`（0~100）。**禁止混用**（`CLAUDE.md §4.1`：混用 = 100× 誤差） |

⚠️ **`fx_avg` 的方向必須釘死**：v1 `services/ledger_service.py` 的 CHUBB 公式
`net_investment_twd = cost_unit × units × fx_avg` ⇒ `fx_avg` 為 **TWD per 原幣**。
v2 沿用此方向，**不得**存倒數（`CLAUDE.md §4.4` 已列 FX 倒數為精度與 ÷0 陷阱）。

#### 2.6.3 匯率結算點（settlement point）

**這是客戶明確要求「明定」的項目。** v1 現況（實測）：

| 場景 | v1 用哪個匯率 | 位置 |
|---|---|---|
| 買進（申購） | **交易當日即期匯率**，存入 `fx_avg` 加權平均 | `ledger_service.subscribe(fx_rate=...)` |
| 配息（現金） | **除息當日匯率** | `ledger_service.dividend_cash(fx_rate=...)` |
| 配息（再投資） | `fx_avg` **不變**（只增單位數） | `ledger_service.dividend_reinvest` |
| 轉換（同幣別） | **嚴格繼承** A 端 `fx_avg` | `SwitchResult.fx_avg_inherited` |
| 轉換（跨幣別） | **當日 B 幣對 TWD 即期**，並記錄 `cross_rate` | 同上 |
| 現值評價 | **當下即期** `fx_current`（呼叫端傳入） | CHUBB 公式 (7)(8) |

**v2 規範（沿用 v1 且補上 v1 沒寫死的部分）**：

1. **成本側匯率錨定點 = 交易日即期匯率**，寫入該筆 `v2_transactions.fx_rate`，**永久凍結、不可回溯改寫**
   （`CLAUDE.md §2.3` Point-in-Time：禁止用未來匯率回填過去決策）。
2. **評價側匯率 = 評價當下即期**，**不入 `v2_transactions`**，只在 `v2_holdings` 的衍生欄即時取用。
3. **同幣別轉換繼承 `fx_avg`**；跨幣別轉換以 **TWD 歷史成本守恆**反推 B 端成本
   （v1 已實作：`cost_unit_b = (n_redeem × cost_unit_a × fx_avg_a) / (n_added × fx_avg_b)`）。
4. ⚠️ **交易日無匯率報價時（假日／來源失敗）**：**必須 Fail Loud**，
   標記 `fx_is_imputed = true` ＋ `fx_source`，**禁止靜默用前一日**（`CLAUDE.md §1`）。
   ⇒ v1 **未實作**此旗標 → §5 缺口 **G-5**。

**匯率來源與 fallback（實測 `repositories/fund/fx_and_main.py::get_latest_fx`）**：

| pair 類型 | fallback chain |
|---|---|
| **TWD pair**（USDTWD／EURTWD…） | Yahoo → `open.er-api.com` |
| **非 TWD pair** | Yahoo → FRED `DEX*` → `open.er-api.com` → Frankfurter(ECB) |

⚠️ 程式碼自陳：**TWD pair 刻意跳過 FRED 與 Frankfurter** ——
理由是 FRED `DEXTWUS` 已停發、ECB 無 TWD 報價，對 TWD 場景**全是 dead path**。
⇒ **v2 不得「為了對稱」把這兩條加回 TWD 路徑**，那會是一次無意義的延遲放大。

---

## §3. 第 2 項｜指標 SSOT 附錄

### 3.1 客戶逐字指定的四條（照辦，不改寫）

#### 3.1.1 Sharpe Ratio

**客戶指定（逐字照錄）**：
> 年化 252 日；台股無風險利率採「台灣央行 1 年期定存利率」、海外標的採「美國 3 個月國債殖利率（DTB3）」；
> **台幣投海外資產統一以 DTB3 為主、台幣定存為 fallback 並標註**。

**v2 規格**：

| 項目 | 規格 |
|---|---|
| 公式 | `Sharpe = (r̄ − rf) / σ × √252`，`r̄`／`σ` 取自**日對數報酬** |
| 年化 | **252 交易日**（**非** 365 日曆日） |
| 幣別 | 報酬以**原幣** NAV 計算；rf 依標的屬性選取（見下） |
| rf（台股標的） | **台灣央行 1 年期定存利率** |
| rf（海外標的） | **美國 3 個月國債殖利率 `DTB3`** |
| rf（台幣投海外資產） | **`DTB3` 為主**；台幣定存為 **fallback**，且**必須標註**採用了哪一個 |
| 最小樣本 | **250 個交易日**（沿用 v1 `MIN_OBS_SHARPE_SORTINO`） |
| 不足樣本 | 回 `N/A`，**不得**用短窗年化冒充（見 §3.3） |

⛔ **實測到的三個 gap（這一節最重要的部分）**：

**(a) `DTB3` 在本 repo 完全不存在。**
> **量測**：`git grep -n "DTB3" -- '*.py' '*.md'` → **0 命中**（量測日 2026-09-14）。
> `shared/fred_series.py` 宣告的 3 個月期 series 是 **`DGS3MO`**（3-Month Treasury *Constant Maturity*），
> **不是** `DTB3`（3-Month Treasury Bill, Secondary Market）。**兩者是不同的 FRED series。**
⇒ v2 必須**新增** `FRED_DTB3 = "DTB3"` 至 `shared/fred_series.py`。

**(b) 台灣央行 1 年期定存利率 —— 本 repo 無任何取數來源。**
> **量測**：`git grep -niE "定存|deposit_rate|TW_RF|rediscount|重貼現" -- '*.py'`
> → 命中全部為 UI 說明文字（如「定存替代品」）或**子字串偽陽性**
> （`一定存在` 這個詞包含 `定存`，在 `sources.py`／`tests/` 命中多次）。
> **逐一人工判讀後，無任何一處是台灣利率取數。**
> 另：`CLAUDE.md §2.1` 已記載 CBC `ms1.json` 取數實作**已於 Phase 1.4 實體刪除**，
> 且刪除後「全 repo 已無 CBC ms1.json / EF15M01 的取數實作」。
⇒ v2 必須**新建**一個台灣利率 L1 fetcher。**來源未定** → §5 缺口 **G-8**（需客戶或架構組拍板）。

**(c) v1 現行 rf 用的是 `FEDFUNDS`，且是單一全域值。**
> **量測**：`services/fund_service.py::_RF_ANNUAL`，預設 `0.04`，
> 由 `app.py` / `ui/tab1_macro.py` 呼叫 `set_risk_free_rate(FED_RATE/100)` 注入。
> 程式碼自陳「注入即時無風險利率（**FEDFUNDS**/100）」。
⇒ 與客戶指定的 `DTB3` / 台灣定存**皆不符**。
⇒ 更關鍵：**`_RF_ANNUAL` 是 module-level 全域變數，全站所有基金共用同一個 rf**，
  而客戶要求的是**依標的屬性分流**（台股 vs 海外）。
  ⇒ **v2 必須把 rf 從全域變數改為「每檔標的解析一次」的參數**，這是結構性變更，不是換個常數。
  ⚠️ v1 程式碼自陳此全域變數曾造成**跨測試污染**（測試塞 `value: 50.0` → rf = 50%/年 →
  同 process 內所有 Sharpe 分子被扣 50%），並已加 `[0, 0.25]` 值域防護。
  **v2 的 per-asset 設計同樣必須保留此值域防護。**

#### 3.1.2 基金淨值與同類中位數

**客戶指定（逐字照錄）**：
> 採還原權值（含息），同類中位數錨定公會／晨星標準並標註更新週期。

**v2 規格**：

| 項目 | 規格 |
|---|---|
| NAV | **還原權值（含息）** —— 即配息再投資還原後的序列 |
| 同類中位數 | 錨定**公會（SITCA）／晨星（Morningstar）**的分類標準 |
| 標註 | **必須標註更新週期** |

**v1 現況（實測）**：

- ✅ **還原權值已有實作**：`services/fund_service.py` 自陳
  「把配息『再投資複利』還原進 NAV 序列，供風險指標（σ / Sharpe / Sortino / max_drawdown）用」，
  理由是**除息日 NAV 跳空會被誤判為暴跌** → 高估波動、放大 max_drawdown、壓低 Sharpe。
  ⇒ **v2 沿用，並明定：風險指標一律吃還原序列，顯示用淨值吃原始序列。**

- ⛔ **同類中位數：本 repo 無任何實作。**
  > **量測**：`git grep -niE "同類中位|category_median|peer_median|類別中位" -- '*.py'` → **0 命中**。

- ⛔ **`_src_sitca_meta` 只回傳 `fund_name` 與 `nav_latest`**（逐行讀該函式確認），
  **不回傳任何分類或同類統計**。

- ⚠️ **現有最接近的東西是 `services/peer_rank.py`，但它不是「公會／晨星標準」**：
  它對**「持倉 ∪ 選股池」這個本地小 universe** 做四分位排名，
  程式碼自陳這是「用持倉 ∪ 選股池的同類小 universe 呼叫」。
  ⇒ **分母是使用者自己的基金清單，不是全市場同類** → **不符客戶指定的錨定標準**。

- ⛔ **且 §2.3.4 已實測出 `category` 欄位在 5/8 樣本上是說明書段落而非類別**
  ⇒ 即使接上中位數演算法，**分組鍵本身是壞的**。

⇒ 綜合 §5 缺口 **G-2**：同類中位數需要 (i) 一個乾淨的 category SSOT、(ii) 一個全市場同類 universe 來源、
(iii) 該來源的更新週期。**三者本 repo 皆無。**

**`peer_rank.py` 既有的樣本量誠實規則（v2 應保留，實測）**：

| 同類檔數 n | 輸出 |
|---|---|
| n < 2 | **不給名次**（無從比較） |
| 2 ≤ n ≤ 3 | **只給相對排名 X/n，不分四分位**（程式碼自陳「3 檔捏不出 Q1~Q4，硬分就是造假」） |
| n ≥ 4（`PEER_QUARTILE_MIN_N`） | 真四分位 ＋ **揭露分母「同類 n 檔」** |

另：`PEER_MIN_OBS = 50`（一檔要參與排名的最低有效 NAV 點數）、
`PEER_MIN_SPAN_RATIO = 0.6`（實際跨越年數需 ≥ 視窗 × 0.6）。

#### 3.1.3 本益比（TTM）—— ⚠️ **基金側目前不使用，照客戶更正後的射程處理**

**客戶指定（逐字照錄）**：
> 近四季 EPS 總和；**EPS ≤ 0 統一標註 `N/A（虧損）`**。

**基金側實測結果**：

> **量測 1**：`git grep -niE "本益比|forward_pe|pe_ttm|per_ttm|trailing_pe" -- 'services/*.py' 'repositories/*.py' 'repositories/**/*.py'`
> → 唯一命中是 `repositories/external_market_repository.py` 的一行**退役註解**：
> 「⚠️ 2026-08-28 退役（**有意識的移除，不是漏刪**）：`fetch_yf_forward_pe` / …」
> （與 `CLAUDE.md §2.2` 記載的「兩 fn 已整段刪除」一致）。
>
> **量測 2**：`repositories/financial_repository.py` 是本 repo 唯一抓個股財報的模組，
> 逐行讀其公開 API → `resolve_ticker` 與 `fetch_stock_three_ratios`（**毛利率／營益率／淨利率** QoQ），
> **不含 EPS、不含本益比**。

⇒ **判定：本益比（TTM）在基金儀表板側無實作、無消費端。**
依 §0 射程，**本文件不為它定義規格** —— 它屬股票／ETF 戰情室。

⚠️ **但有一個真實的交界，必須具名列出，不得當作不存在**：
基金的**持股明細**（`fetch_holdings`）內容**就是個股**，
且 `financial_repository` 已在為這些持股抓財報三率。
⇒ **若 v2 要在基金的持股明細上顯示本益比，那一刻它就落入基金側。**
⇒ 列為 §4.7 跨儀表板待協調項 **X-3**（**本文件不單方決定**）。

#### 3.1.4 配息殖利率

**客戶指定（逐字照錄）**：
> 近一年累計已除息總額 / 最新收盤價；**不配息標的顯示 `N/A`**。

**v2 規格**：

| 項目 | 規格 |
|---|---|
| 公式 | `div_yield_pct = Σ(近一年已除息金額) / 最新淨值 × 100` |
| 分子 | **近一年累計「已除息」總額** —— 只算已過除息日者，**未來配息不計** |
| 分母 | **最新收盤價（淨值）** |
| 幣別 | 分子分母**同為原幣**（比率，故單位無關；但**禁止**跨幣別混算） |
| 不配息標的 | **`N/A`**（不得顯示 0%） |

**v1 現況（實測，與客戶指定一致）**：
- `services/fund_service.py`：`div_yield_pct = round(annual_div / nav_current * 100, 2)`，
  就地註解自陳「殖利率：配息 ÷ **現值**（定義）」 ⇒ **分母定義與客戶一致**。
- **來源優先序**：`services/health/dividend.py` 自陳
  「1. **MoneyDJ wb05 官方** `moneydj_div_yield`」為主，**本算為 fallback**
  （`services/fund_invest_calc.py` 就地自陳「本算 fallback；主源 moneydj_div_yield wb05」）。
- ✅ **已有雙演算法對帳**：`services/reconcile.py::reconcile_dividend_yield`，
  `services/fund_service.py` 注入 `div_yield_reconcile`，
  判準為「絕對 0.1 個百分點／相對 5%」（`fund_invest_calc.py` 自陳）。
  ⇒ **v2 沿用此對帳，並在 UI 顯示 agree／disagree 四態**（v1 已有此 chip）。

⚠️ **一個 v1 與客戶指定的潛在落差，具名列出但不自行拍板**：
客戶寫「近一年**累計已除息總額**」，而 v1 主源是 **MoneyDJ wb05 掛牌的 `moneydj_div_yield`**
（`fund_invest_calc.py` 自陳「不是掛牌值」指的是本算 fallback）。
**掛牌殖利率的定義可能是「年化配息率」而非「近一年實際累計」** —— 兩者在配息頻率變動時會不同。
⛔ **本文件未查證 MoneyDJ wb05 的確切定義**（需打外部 API，本階段禁止）→ §5 缺口 **G-9**。

### 3.2 其餘基金側指標（本輪盤點到的）

> ⚠️ **本節是分類敘述，不是窮舉。** 未涵蓋：`services/` 底下約 50 個模組中未被本輪讀取者。

| 指標 | 公式／規則 | 來源 | 頻率 | 幣別 | fallback |
|---|---|---|---|---|---|
| **Sortino** | `(r̄ − MAR) / σ_D × √252`，`σ_D = √((1/N)·Σ[min(0, rₜ−MAR)]²)`，**MAR = rf（與 Sharpe 分子相同）** | 自算 | 日 | 原幣 | MoneyDJ wb07 |
| **σ（年化波動）** | 日報酬標準差 × √252 | 自算（**吃配息還原序列**） | 日 | 原幣 | wb07 |
| **max_drawdown** | 峰谷最大跌幅 | 自算（**吃配息還原序列**） | 日 | 原幣 | wb07 |
| **1Y 含息報酬** | 四層 fallback（見下） | `services/fund_total_return.py` | 日 | 原幣 | 見下 |
| **四分位排名** | 同類年化報酬排序 → 四分位 | `services/peer_rank.py` | 日 | 原幣 | 樣本不足則降級 |
| **吃本金判定** | `real_return_pct = total_return_pct − div_yield_pct`；含息報酬 < 配息率 → 配息來自本金 | `services/fund_service.py::classify_eating_principal` | 日 | 原幣 | — |

**1Y 含息報酬的四層 fallback（`services/fund_total_return.py` 自陳，權威→次選）**：
1. `perf["1Y"]` —— wb01 真 1Y／本地還原淨值法注入
2. `ret_1y_total` —— 本地含息計算（可能短窗年化）
3. `ret_1y` —— 純 NAV 變化率（**不含息**）
4. NAV 序列年化 —— **最後手段**，跨度須 ≥ `RET_1Y_EXTRAPOLATE_MIN_DAYS`，scale cap 2×

⚠️ **v1 就地記載的事故（v2 必須保留此防線）**：
> 2026-08-14 稽核 E1：第 4 層原本 **30 天就敢 ×12 外推**，大表因此印出 **+201%** 的台幣基金。
> 現在跨度不足半年直接回 `(None, SRC_TOO_SHORT)`。

⇒ **v2 規範：任何外推必須有最小跨度閘門 ＋ scale cap，且來源標籤必須自己講話。**
v1 已把「來源標籤」做成**會印給使用者看的字串**（官方值以「MoneyDJ 官方」開頭、自算值以「自算」開頭），
程式碼自陳理由是「使用者完全無從判斷這個報酬率到底是官方公布的還是本站推算的」。**v2 沿用。**

### 3.3 `N/A` 觸發條件完整表

> **這是客戶明確要求的「各指標觸發 `N/A` 的完整條件表」。**
> ⚠️ 下表為**本輪從程式碼與客戶指令彙整**；**未涵蓋**未被本輪讀取的模組（§3.2 前言）。

| 指標 | `N/A` 觸發條件 | 顯示 | 依據 |
|---|---|---|---|
| **Sharpe** | 有效觀測 < **250** 交易日 | `N/A（樣本不足 n/250）` | `MIN_OBS_SHARPE_SORTINO` |
| **Sharpe** | rf 解析失敗或超出 `[0, 0.25]` | `N/A（無風險利率不可用）` | `_RF_ANNUAL_MAX` 防護 |
| **Sortino** | 同 Sharpe，**且**低於 MAR 的樣本 < 5 筆 | `N/A（下檔樣本不足）` | v1 docstring |
| **σ / max_drawdown** | NAV 序列 < 最小點數 | `N/A（序列過短）` | — |
| **任何年化指標** | NAV 來自 `cache/nav/` 稀疏快取且 `supports_annualized = False` | `N/A（序列稀疏，年化不可信）` | `fetch_nav` 就地判定 |
| **本益比 TTM** | **EPS ≤ 0** | **`N/A（虧損）`** | **客戶逐字指定** |
| **本益比 TTM** | 近四季 EPS 不足四季 | `N/A（季數不足）` | 客戶指定的延伸 |
| **配息殖利率** | **標的不配息** | **`N/A`**（**不得顯示 0%**） | **客戶逐字指定** |
| **配息殖利率** | 最新淨值 ≤ 0 或缺值 | `N/A（無淨值）` | `CLAUDE.md §4.4` 大數除小數 guard |
| **同類中位數／四分位** | 同類 n < 2 | `N/A（無同類可比）` | `peer_rank.py` |
| **四分位** | 2 ≤ n ≤ 3 | **只給 X/n，不給四分位** | `peer_rank.py`（非 N/A，是降級） |
| **四分位** | 該檔有效 NAV 點數 < **50** | 該檔不參與排名 | `PEER_MIN_OBS` |
| **1Y 含息報酬** | 四層全敗，或跨度 < 最小外推門檻 | `N/A（期間不足）`＋`SRC_TOO_SHORT` | `fund_total_return.py` |
| **任何指標** | 上游全部 fallback 失敗 | **`raise` 或回 `None` ＋ 來源旗標**，⛔ **禁止 `fillna(0)`** | `CLAUDE.md §1` |

**v2 硬規則（三條，來自 `CLAUDE.md §1`）**：
1. `N/A` **必須帶原因**。光一個 `N/A` 不合格 —— 使用者無從判斷是「還沒載入」還是「算不出來」。
2. **`N/A` ≠ 0 ≠ 空白**。三者在 UI 上必須可區分（v1 已有 `⬜ 資料不足` 慣例，實測 `services/`／`shared/` 下
   `資料不足` 113 處、`⬜` 83 處）。
3. **「未點擊載入」用灰色、「系統真出錯」才用紅色**（`CLAUDE.md §-1.5.1c` v3 `02`）。

---

## §4. 第 5 項｜持倉與交易資料模型

### 4.1 `v2_transactions`

**定位**：append-only 事件流水帳。**唯一的事實輸入**；`v2_holdings` 由它推導。

| 欄位 | 型別 | 必填 | 語意 | 來源 |
|---|---|---|---|---|
| `txn_id` | str (UUID) | ✅ | 主鍵 | 新生成 |
| `account_id` | str | ✅ | 保單／帳戶識別碼 | v1 `policy_id` |
| `asset_class` | str | ✅ | **`fund`**（基金側只寫此值） | ⚠️ 完整列舉見 §4.7 X-1 |
| `instrument_code` | str | ✅ | 基金代碼 | v1 `code` |
| `txn_type` | str | ✅ | 見下方值域 | v1 `action` 映射 |
| `trade_date` | date | ✅ | 交易日（**除息以除息日為準**） | v1 `date` |
| `units` | float | 條件 | 單位數（±） | v1 `units` |
| `price_orig` | float | 條件 | 成交淨值（**原幣**） | v1 `nav_at_action` |
| `price_ccy` | str | ✅ | `price_orig` 的 ISO 幣別 | v1 政策表 `currency` |
| `fx_rate` | float | ✅ | **交易日即期，TWD per 原幣**（**凍結，不可回溯改寫**） | v1 `fx_avg` 輸入 |
| `fx_is_imputed` | bool | ✅ | 匯率是否為補值 | ⛔ **v1 無此欄**（§5 G-5） |
| `fx_source` | str | ✅ | 匯率來源（`yahoo`／`er_api`…） | `get_latest_fx` |
| `amount_twd` | float | 條件 | 台幣金額 | v1 `twd` |
| `fee_orig` | float | 選填 | 費用（原幣） | v1 `fee` |
| `fee_ccy` | str | 條件 | 費用幣別 | ⛔ **v1 未宣告**（§5 G-4） |
| `div_per_unit` | float | 條件 | 每單位配息（原幣） | v1 `models/ledger.Transaction` |
| `note` | str | 選填 | 備註 | v1 `note` |
| `source` | str | ✅ | provenance | `CLAUDE.md §2.2` |
| `recorded_at` | datetime | ✅ | 寫入時間（UTC） | — |

**`txn_type` 值域（v2，封閉列舉）**：

| v2 值 | 語意 | v1 對應 |
|---|---|---|
| `buy` | 申購／買進 | `buy`、`subscribe` |
| `sell` | 贖回／賣出 | `sell` |
| `dividend_cash` | 現金配息 | `dividend`、`dividend_cash` |
| `dividend_reinvest` | 配息再投資 | `dividend_reinvest` |
| `switch_out` | 轉換出 | `switch_out` |
| `switch_in` | 轉換入 | `switch_in` |
| `fee` | 單獨收取的費用 | `fee` |
| `import` | 期初匯入（遷移用） | 無（新增） |

⚠️ **v1 有兩套並存的型別命名，v2 必須收斂成一套**（實測）：
- `repositories/ledger_repository.py::KNOWN_ACTIONS` = `buy`／`sell`／`dividend`／`fee`／`fx`
- `models/ledger.py::_TXN_TYPES` = `subscribe`／`dividend_cash`／`dividend_reinvest`／`switch_out`／`switch_in`

**兩套不一致**：Sheets 端有 `fx` 但無 switch；dataclass 端有 switch 但無 `fx`／`sell`。
⛔ 且 `ledger_repository` 自陳「**不在列表內視為自訂類型（不會被攔截**，但統計時可能漏算）」
⇒ **v2 必須改為封閉列舉 ＋ 寫入時 reject**（`models/ledger.Transaction.__post_init__` 已有 `raise` 前例，沿用該做法）。
⇒ 列為 §5 缺口 **G-10**（`fx` 這個 v1 類型的語意本文件**未查證**，不自行映射）。

### 4.2 `v2_holdings`

**定位（母法明訂）**：**全系統持倉單一事實來源**，由 `v2_transactions` 推導；
基金與 ETF **皆寫入此表**，以 `asset_class` 區分。**⛔ 嚴禁在各儀表板端各自算一套。**

| 欄位 | 型別 | 語意 | 推導自 |
|---|---|---|---|
| `account_id` | str | ┐ 複合主鍵 | — |
| `asset_class` | str | │ | — |
| `instrument_code` | str | ┘ | — |
| `units` | float | 持有單位數 | Σ 交易 |
| `cost_unit_orig` | float | **加權移動平均**單位成本（原幣） | §4.3 |
| `cost_ccy` | str | 成本幣別 | — |
| `fx_avg` | float | **加權移動平均**買入匯率（TWD per 原幣） | §4.3 |
| `cost_unit_with_div` | float | 含息平均單位成本（原幣） | §4.4 |
| `net_investment_twd` | float | 淨投資額 = `cost_unit_orig × units × fx_avg` | CHUBB (4) |
| `dividends_received_twd` | float | 累計已領現金配息（TWD） | Σ 配息 |
| `realized_pnl_twd` | float | 已實現損益（TWD） | §4.3 |
| `last_txn_date` | date | 最後一筆交易日 | max |
| `derived_at` | datetime | 推導時間 | — |

**衍生欄（不落地，評價時即時算）**：
`nav_current`(5)／`value_orig`(6) = `units × nav_current`／`fx_current`(7)／
`value_twd`(8) = `value_orig × fx_current`／`roi_price`(9) = (8)/(4) − 1／
`roi_total`(11) = (8) / (`units × fx_avg × cost_unit_with_div`) − 1

> **這 11 條編號直接沿用 v1 `services/ledger_service.py` 檔頭自陳的「CHUBB 安達人壽 11 欄位公式（圖片實證）」**，
> **未改寫**。v1 已完整實作，v2 的工作是**把它從 service 層的記憶體物件變成持久化的表**。

⚠️ **物化 vs 即時推導（需拍板，本文件給推薦但不單方決定）**：
v1 `ledger_service` **零快取**，每次重算（§2.4.4）。
**總管推薦：物化 `v2_holdings` ＋ 由 `v2_transactions` 的寫入觸發重算。**
理由：(a) 母法要求它是「單一事實來源」，一個每次重算的記憶體物件不構成「來源」；
(b) 延遲正比於交易筆數，隨帳齡線性劣化。
⚠️ **代價**：物化引入「表與流水帳不同步」的風險 → **必須有一致性檢查**（重算並比對）。

### 4.3 成本計算：加權移動平均法（客戶定死）

**客戶指定**：成本計算統一強制採「**加權移動平均法**」，已實現／未實現損益演算法全站統一。

✅ **v1 已完整實作此法**（實測 `services/ledger_service.py`），v2 **沿用公式、不重新發明**：

**買進（增加單位）** —— 三個量同時做單位數加權平均：
```
cost_unit_new        = (old_units × cost_unit_old        + new_units × nav) / (old_units + new_units)
fx_avg_new           = (old_units × fx_avg_old           + new_units × fx_rate) / (old_units + new_units)
cost_unit_with_div_new = (old_units × cost_unit_with_div_old + new_units × nav) / (old_units + new_units)
```
> ⚠️ 首次買入時 `cost_unit` 與 `cost_unit_with_div` **必相等**（v1 docstring 自陳）。

**賣出（減少單位）**：
```
cost_unit / fx_avg / cost_unit_with_div  →  【不變】   （加權平均按比例贖回保持）
units                                     →  減少
realized_pnl_twd += units_sold × (nav_sell × fx_sell − cost_unit × fx_avg)
```
> **這是加權移動平均法與 FIFO 的分水嶺**：賣出**不消耗特定批次**，只按比例縮減部位，
> 單位成本**維持不變**。⇒ 見 §4.6 對帳差異。

**轉換（switch）**：
- **同幣別**：B 端 `fx_avg` **嚴格繼承** A 端 `fx_avg`（TWD 視角損益不失真）
- **跨幣別**：B 端 `fx_avg` 採當日 B 幣對 TWD 即期，並記錄 `cross_rate`
- **A 端**：`cost_unit` / `fx_avg` / `cost_unit_with_div` **皆不變**，`units` 減少
- **B 端成本反推（TWD 歷史成本守恆）**：
  ```
  cost_unit_b = (n_redeem × cost_unit_a × fx_avg_a) / (n_added × fx_avg_b)
  ratio = cost_unit_with_div_a / cost_unit_a
  cost_unit_with_div_b = cost_unit_b × ratio
  ```

### 4.4 除息（現金 vs 成本扣減）與配息再投資滾入

**客戶要求「明定」**，v1 已有實作（CHUBB 規範），v2 照錄：

#### (a) 現金配息 `dividend_cash`
```
dividends_received_twd += div_per_unit × units × fx_rate
units                   →  【不變】
cost_unit               →  【不變】          ← 帳面成本不動
cost_unit_with_div      →  【下調】          ← 只動含息成本
```
**下調公式（CHUBB 規範，v1 逐字實作）**：
```
virtual_units      = (div_per_unit × units) / nav_at_div      ← 虛擬再投資單位數
new_cost_with_div  = old_cost_with_div × units / (units + virtual_units)
```
⚠️ **`nav_at_div` 為 `None` 時**：v1 **只累計 TWD 配息、不下調 `cost_unit_with_div`**。
⇒ **v2 必須在此加旗標**（否則含息報酬會偏高卻無人知道），見 §5 G-11。

> **語意**：現金配息**不扣減帳面成本**（`cost_unit` 不變），
> 但**會扣減含息成本**（`cost_unit_with_div` 下調）——
> 因此 `roi_price`(9) 與 `roi_total`(11) **刻意給出不同的數字**，這是設計，不是 bug。

#### (b) 配息再投資 `dividend_reinvest`
```
new_units          = (div_per_unit × units) / nav_at_div
units              += new_units
cost_unit          →  加權平均滾入（以 nav_at_div 為新單位成本）
cost_unit_with_div →  加權平均滾入（同上）
fx_avg             →  【不變】                ← 再投資不涉及新的台幣匯入
```
> ⚠️ **`fx_avg` 不變是關鍵**：再投資沒有新的台幣換匯行為，
> 若在此更新 `fx_avg`，`net_investment_twd` 會憑空變大。

### 4.5 多幣別換算匯率錨定點

見 **§2.6.3**（成本側＝交易日即期並凍結；評價側＝當下即期；轉換依同幣別／跨幣別分流）。

### 4.6 與券商常見 FIFO 對帳單的差異說明（**文案草稿**）

> **以下為要顯示給使用者看的文案草稿**。客戶指定要附，此處為初稿，**待 UI 線框階段定版**。

---
**為什麼這裡的成本和你的對帳單不一樣？**

我們用的是「**加權平均成本法**」，而多數券商／保險公司的對帳單用「**先進先出法（FIFO）**」。
**兩種算法都是對的，只是看事情的角度不同。**

**差在哪裡**

假設你分兩次買進同一檔基金：
- 第 1 次：100 單位，每單位 10 元
- 第 2 次：100 單位，每單位 20 元

接著你賣掉 100 單位，當時淨值 25 元。

| | 加權平均法（本站） | FIFO（常見對帳單） |
|---|---|---|
| 賣出時認定的成本 | 每單位 **15 元**（(10+20)÷2） | 每單位 **10 元**（先買的先賣） |
| 這筆已實現損益 | (25−15) × 100 = **1,000 元** | (25−10) × 100 = **1,500 元** |
| 剩下 100 單位的成本 | 每單位 **15 元** | 每單位 **20 元** |

**重點：兩邊的「總損益」最後會一樣，差的只是「什麼時候認列」。**
FIFO 會讓你在早期賣出時看到比較大的已實現獲利，但留下成本比較高的部位；
加權平均法則讓每一次賣出都反映你的**平均持有成本**。

**為什麼本站選加權平均法**

1. 你的部位常常來自**定期定額**與**配息再投資**，批次多到難以逐筆追蹤，
   平均成本更能回答「我這檔基金平均買在哪裡」。
2. 你的保單帳戶本來就是用平均成本結算的（安達 CHUBB 格式），**與你的保單對帳單一致**。
3. 跨幣別時，平均匯率（`fx_avg`）能讓「台幣投入 vs 台幣現值」的比較不失真。

**所以你該看哪一個？**
- 想核對**券商／保險公司帳務** → 看對方的對帳單。
- 想知道**自己買得好不好、現在賺賠多少** → 看本站。

⚠️ **本站不會、也不應該用來報稅。** 稅務認列請以發行機構出具的正式文件為準。

---

> ⚠️ **文案草稿的一項未查證事項**：上文宣稱「你的保單帳戶本來就是用平均成本結算的（安達 CHUBB 格式）」。
> 此句依據為 v1 `services/ledger_service.py` 檔頭自陳「對齊 CHUBB 安達人壽 11 欄位公式（**圖片實證**）」。
> **本文件未見到該圖片，未獨立查證**（`CLAUDE.md §-2` 規則 6）。
> ⛔ **定版前必須向客戶確認**，否則這是一句對使用者講的、沒有出處的話。

### 4.7 跨儀表板待協調項（⛔ 本文件不單方決定）

> 母法明訂 `v2_holdings` 是**全系統**單一事實來源，基金與 ETF 皆寫入。
> 以下欄位**跨儀表板才能拍板**，本文件**只列出基金側的需求與不能單方決定的理由**。

| ID | 項目 | 基金側的需求 | 為什麼不能由我們單方決定 |
|---|---|---|---|
| **X-1** | `asset_class` **完整列舉** | 基金側只需寫入 `fund` 一個值；需要它是**封閉列舉**且**基金側的值不會被改名** | 完整列舉必須涵蓋股票／ETF 側的所有類別（`stock`／`etf`／…）。本文件**未讀**股票側，列舉若由我們定，必然遺漏 |
| **X-2** | **ETF 專屬欄位** | 基金側**不需要**，但需保證這些欄位對 `asset_class='fund'` 列**可為 NULL**、且不影響基金側推導 | ETF 需要哪些欄位只有股票側知道 |
| **X-3** | 基金**持股明細**上的個股指標（本益比 TTM 等） | 若 v2 要在基金持股明細顯示個股本益比，需要股票側的 EPS／PE SSOT | 基金側**無 EPS／PE 實作**（§3.1.3 實測）。重複實作一套 = 違反母法「嚴禁各自算一套」 |
| **X-4** | `instrument_code` **命名空間** | 基金代碼形態多樣（6 碼數字境內、英數保單商代碼如 `TLZF9`、MoneyDJ 複合 key `xxx-yyy`） | 與股票 ticker（`2330.TW`／`SPY`）**可能碰撞**。需要跨側的唯一鍵策略（前綴？複合鍵？） |
| **X-5** | **已實現損益的統一演算法** | 基金側採加權移動平均（客戶定死，§4.3） | 母法要求「已實現／未實現損益演算法**全站統一**」⇒ 股票／ETF 側**必須採同一法**。需確認股票側不是 FIFO |
| **X-6** | `v2_holdings` **寫入權責** | 基金側需要「基金列由基金側推導寫入」 | 若兩側各自寫同一張表，需要明確的寫入邊界與衝突處理（`CLAUDE.md` `PROCESS.md §3` 寫入端序列化） |

**基金側的唯讀引用方式（母法：基金儀表板只以「收益視角摘要卡片」唯讀引用 `v2_holdings`，點擊 Deep Link 跳轉）**：

| 項目 | 規格 |
|---|---|
| 讀取 | 只讀 `asset_class IN ('fund', …)`；**摘要卡片不寫入** |
| 欄位 | 只需 `instrument_code`／`units`／`net_investment_twd`／`value_twd`／`roi_total` |
| Deep Link | 由基金側提供 `instrument_code` → 基金詳情頁的連結；**跨側跳轉的 URL 契約需 X-1 先定案** |
| ⛔ 禁止 | **不得**在摘要卡片端重算任何損益（母法：嚴禁各自算一套） |

---

## §5. 缺口清單（需拍板／需另行派工）

> **本節是本文件最重要的輸出之一。** 每一列都是「客戶指定的規格與 repo 實況對不上」的具名落差。
> ⛔ **本節不構成動工授權**（`CLAUDE.md §-1`）。

| ID | 缺口 | 證據（本輪實測） | 性質 |
|---|---|---|---|
| **G-1** | 自算風險指標需 **250** 交易日，但預設取數只給 **30** 筆 | `MIN_OBS_SHARPE_SORTINO=250`；`snap.json` 8/8 檔 `nav_points=30` | 架構（長序列來源） |
| **G-2** | **同類中位數無實作、無來源、且分組鍵 `category` 已污染** | `同類中位\|category_median\|peer_median` → 0 命中；`_src_sitca_meta` 只回 `fund_name`/`nav_latest`；`snap.json` 5/8 `category` 為說明書段落 | **客戶指定項無法實現** |
| **G-3** | 保單政策表**無 `units`／無 `nav_at_buy`**，無法純自動遷移 | `docs/POLICY_SHEETS_SETUP.md` 9 欄 | 遷移 |
| **G-4** | v1 `fee` 欄**未宣告幣別** | `LEDGER_COLS` 9 欄無 `fee_ccy` | 資料模型 |
| **G-5** | 匯率補值**無旗標** | v1 無 `fx_is_imputed` | 違 `CLAUDE.md §1` |
| **G-6** | 無交易日曆 → **算不出真實缺漏率** | `CLAUDE.md §4.5` 自陳無 calendar lib | 量測能力 |
| **G-7** | `data_cache` 月頻序列落後約 5 個月 | `M2SL`／`CPIAUCSL` 最後一期 2026-04-01 vs 量測日 2026-09-14 | **未查證**是否為 production 路徑 |
| **G-8** | **台灣央行 1 年期定存利率無任何取數來源** | `DTB3` 0 命中；`定存` 命中全為 UI 文案或 `一定存在` 偽陽性；CBC 取數已刪除 | **客戶指定項無來源** |
| **G-9** | MoneyDJ wb05 `moneydj_div_yield` 的**確切定義未查證** | 需打外部 API，本階段禁止 | 定義風險 |
| **G-10** | v1 交易型別**兩套並存且不一致**，且**不攔截未知值** | `KNOWN_ACTIONS` vs `_TXN_TYPES`；`ledger_repository` 自陳不攔截 | 資料完整性 |
| **G-11** | 現金配息在 `nav_at_div=None` 時**不下調含息成本且無旗標** | `ledger_service` 自陳 | 違 `CLAUDE.md §1` |
| **G-12** | rf 是 **module 全域**，無法 per-asset 分流 | `_RF_ANNUAL`；客戶要求台股／海外分流 | 結構性 |

---

## §6. 母法修正提案單

**本階段無母法修正提案。**

本文件的產出**未觸及任何既有檔案** —— 只新增 `docs/v2/DATA_DICTIONARY.md`。
§5 的 12 個缺口**全部可以在階段 2 之後、於母法現行條文內處理**，**不需要修改母法**。

⚠️ 惟 **G-2** 與 **G-8** 是「**客戶逐字指定的規格，在本 repo 沒有可實現的資料來源**」，
**不是**母法問題，而是**需要客戶裁決的業務需求衝突**
（`CLAUDE.md §-1.5.1c` v3 `03`-2 ②「核心付費資料源永久失效的替代方案」的同型情境）。

**總管推薦方案（依 `CLAUDE.md §-1.5.1b` 裁決二，請示必須附推薦，不得只丟選項）**：

- **G-8（台灣無風險利率）**：**建議先以 FRED 可取得的台灣利率替代序列上線，並在 UI 明確標註「非央行定存牌告利率」**，
  待央行來源接上後替換。理由：Sharpe 對 rf 的敏感度遠低於對 σ 的敏感度，
  但「**完全沒有 rf**」會讓台股標的的 Sharpe 整條算不出來，代價更大。
  ⚠️ **本推薦未查證 FRED 是否真有合適的台灣利率 series**（需打 API），**屬待驗事項**。
- **G-2（同類中位數）**：**建議階段 2 先交付「四分位排名（本地 universe）＋ 明確標註分母」**，
  **不冒充公會／晨星中位數**；同時另案評估 SITCA／Morningstar 的分類與同類統計取得方式。
  理由：`peer_rank.py` 已有樣本量誠實規則，可立即用；
  而冒充一個沒有來源的「同類中位數」正是 `CLAUDE.md §1` 明禁的造假。

---

## §7. 交件自陳：做了什麼／刻意沒做什麼／沒量到什麼

### 7.1 做了什麼

- 盤點基金側資料源（§2.1）、逐儲存體欄位字典（§2.2）、實測歷史缺漏率（§2.3）、
  冷熱載入延遲（§2.4）、v1→v2 遷移路徑（§2.5）、多幣別與匯率錨定點（§2.6）。
- 指標 SSOT：客戶逐字指定的四條逐條落規格（§3.1）、其餘基金側指標（§3.2）、`N/A` 完整條件表（§3.3）。
- `v2_transactions` 完整欄位（§4.1）、`v2_holdings` 與 CHUBB 11 式（§4.2）、
  加權移動平均法（§4.3）、除息與再投資滾入（§4.4）、FIFO 差異文案草稿（§4.6）、
  跨儀表板待協調項 6 項（§4.7）。
- 具名缺口 12 項（§5）。
- **自行實作 pure-python parquet 解碼器**並做四道驗證（§1.2），否則 `data_cache/` 的數字全部拿不到。

### 7.2 ⛔ 刻意沒做什麼

- **沒有建立任何 `.py`／`src/`／`v2_migrations/`**，沒有動任何資料庫。
- **沒有繪製高保真視覺稿，沒有寫任何前端代碼。**
- **沒有修改任何既有檔案** —— 本 PR 只新增 `docs/v2/DATA_DICTIONARY.md` 一個檔。
- **沒有動 16 個 `ui/tab*.py`，沒有動五個 `ui/views/page_0*.py`**（已實測確認五頁均被 `app.py` import ＝ 線上 UI）。
- **沒有對 Google Sheets 做任何操作**（含唯讀 —— 本環境無憑證）。
- **沒有打任何外部 API。**
- **沒有讀取姊妹 repo** `my-stock-dashboard` 任何內容（scope 更正後，clone 留置未動）。
- **沒有替股票／ETF 側決定任何欄位**（改列 §4.7 待協調）。
- **沒有為本益比 TTM 定義基金側規格**（實測其無基金側消費端，§3.1.3）。

### 7.3 ⚠️ 沒量到什麼（以及為什麼）

| 沒量到 | 為什麼 |
|---|---|
| **實際網路延遲**（冷／熱載入的牆鐘時間） | 禁止打外部 API。§2.4 全部是**程式碼宣告值** |
| **Google Sheets 上的實際列數與缺漏率** | 無憑證，且禁止寫入 |
| **基金 NAV 的歷史缺漏率** | 唯一本地語料 `cache/nav/` **只有 1 檔、10 個點橫跨 15 年**，不是可統計的語料（§2.3.3） |
| **排除假日後的真實抓取失敗率** | 無交易日曆（G-6）。§2.3.1 的百分比是**含假日的上界** |
| `fred_indicators.parquet` 是否為 production 路徑 | 未查證（G-7） |
| MoneyDJ wb05 殖利率的確切定義 | 需打 API（G-9） |
| v1 `action='fx'` 的語意 | 未查證，故 §4.1 **未自行映射**（G-10） |
| CHUBB「圖片實證」的原始出處 | 未見到該圖片（§4.6 末） |
| `pool_repository` / `portfolio_perf_repository` 逐欄 schema | 射程外，§2.5 標為「未逐欄盤點」 |

### 7.4 ⚠️ 本文件的效力限制

- **單組產出，未經第二組獨立複驗**（`CLAUDE.md §-2` 規則 6）。
- 所有量測值**標日期、標範圍**；**引用前請現場重量**（`CLAUDE.md §8.2.A.0` 規則 4 的同一精神）。
- 本文件**刻意不寫**「只有 N 處」「全部都是 X」這類可被一條 grep 推翻的全稱句；
  凡盤點一律為**分類敘述 ＋ 明列未涵蓋範圍**。
- ⛔ 在獨立稽核完成前，本文件任一句**不得**被當成「已查證的事實」去支撐實作決策。

### 7.5 本文件自身的路徑引用：已逐一驗證，但**無機器守衛**

本 repo 有一支守衛 `tests/test_constitution_file_refs.py`，會讓「引用了不存在的檔案」在 CI 轉紅燈。
**但它掃的是一份寫死的清單 —— `CLAUDE.md` 與 `EXCEPTIONS.md` 兩檔而已**（實測其 `_CONST_FILES`）。
⇒ **本文件不在其射程內，它的路徑引用沒有任何機器在守。**

**故本輪以人工 ＋ 腳本逐一驗證**（量測日 2026-09-14）：
本文件以反引號引用的 path-like token 共 **54** 個 —— **45 個直接存在**；
另 **9 個**逐一判讀後全部成立：

- **6 個是「只寫檔名」的簡寫**，各自唯一解析到一個真實檔案：
  `fred_indicators.parquet`→`data_cache/`、`metadata.json`→`data_cache/`、
  `sources.py`→`repositories/fund/`、`peer_rank.py`／`fund_total_return.py`／`fund_invest_calc.py`→`services/`。
- **3 個是「刻意引用一個不存在的東西」**，且本文件正是在陳述它不存在：
  `src/`（階段 1 禁止建立）、`v2_migrations/`（同上）、`ms1.json`（CBC 取數已被刪除）。

> ⚠️ **這個檢查本身也做了對照**：負向對照 `repositories/DOES_NOT_EXIST.py` 回 `False`、
> 正向對照 `CLAUDE.md` 回 `True` —— 確認它不是一個恆真的假檢查。
> ⚠️ **但它只驗「檔案存不存在」，不驗「那個符號是不是它自稱的東西」** ——
> 這正是 `CLAUDE.md §2.1` 記載的、該守衛自己登記的射程外缺口。**讀者請據此打折信任本文件的符號引用。**
> ⚠️ **本文件刻意不寫任何行號**（沿用 `CLAUDE.md §8.2.A.0` 規則 1 的精神）：
> 行號在任何一次重構後就失效，而**重構不會觸發本文件更新**。
