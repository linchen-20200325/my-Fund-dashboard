> 基準 origin/main 772d6e9a；單組作者草稿；非作者獨立 QA 進行中；不構成正式契約或裁示

# W3｜舊 UI 有價值邏輯比較（五項；唯讀盤點草稿）

- **基準**：`origin/main` `772d6e9a179413c3596f5a5150a6c07edb7a12af`（2026-11-08 fetch 後確認）。全部讀取用 `git show origin/main:<檔>` 與 `git grep origin/main`，未改 repo、未 commit、未連網。
- **性質**：資料與判斷邏輯盤點（D2 唯讀資料需求草案的一部分）。**不是** UI 改版授權、不是實作建議、不是核准。舊 UI 依 `DEC-2026-11-02-02`（第 (1)～(4) 點，經 `DEC-2026-11-02-03` 修訂但 Old UI 邊界不變）永久只作 read-only logic reference。
- **標記**：每句結論後標 `FACT`（本組讀到該檔／符號的文字）／`INFERENCE`（本組推論）／`NOT VERIFIED`（未驗）。來源寫「檔名＋符號／節名」，不寫行號。
- **客戶已選方向（經派工轉達，repo 內本組未見逐字檔，`NOT VERIFIED`）**：Q3 只比這五項；Q4 缺資料沿用既有「資料未備／無法判定」；Q5 FX 閘門保持關閉（`DEC-2026-11-08-02`：`FX_OBS_DATE_RULE_VERIFIED` 維持 False，此點 `FACT`，見 `docs/DECISIONS.md`）；不得自行統一不同績效算法；NAV 10 日、報酬口徑、身份對應維持待決。
- **差異標籤（只用四種）**：已保留／待核准沿用／不適用／無法查證。

---

## 0. 結論先行（一頁）

| # | 項目 | 舊 UI 可達性 | 新 UI 現況（一句） | 主要差異標籤 | 涉投資語意 |
|---|---|---|---|---|---|
| 1 | 單檔基金深掘 | 正式入口可達（`app.py` tab_research → `render_fund_research_tab` → 單檔模式 → `render_single_fund_tab`）`FACT` | `ui_v2` 只有 EXP-6 六欄基礎資料＋最近淨值＋近 12 個月配息佔淨值比；HLD-5 為持倉單檔展開（區間報酬／波動／最大回撤／配息）`FACT` | 多數待核准沿用；少數不適用；少數無法查證 | 是（需客戶裁示） |
| 2 | 多檔基金健診 | 正式入口可達（tab_health → `render_fund_grp_health_tab`；tab_research 批次模式 → `render_batch_analysis_tab`）`FACT` | EXP-3 並排對照最多 3 檔、4 列；HLD-1／2／3／8 為使用者門檻下的持倉區間指標 `FACT` | 待核准沿用為主 | 是（需客戶裁示） |
| 3 | 基金體檢表 | 正式入口可達（健診頁內 `render_fund_checkup`；tab_portfolio 亦呼叫）`FACT` | 新 UI 無對應（無短期報酬、無同類平均、無超額）`FACT` | 待核准沿用／無法查證 | 是（需客戶裁示） |
| 4 | 低基期篩選 | 正式入口可達（健診頁 `_render_low_base_screener`）`FACT` | EXP-1 為七欄字面條件篩選，無衍生條件 `FACT` | 不適用（語意不同）／待核准沿用 | 是（需客戶裁示） |
| 5 | 目前帳本 | 正式入口可達（tab_portfolio → `render_portfolio_tab` → `render_t7_section`）`FACT` | ALO 有市值／成本基準的類別分布；HLD 有單檔持倉；無組合層損益與現金流 `FACT`（ALO 細節 `NOT VERIFIED`） | 待核准沿用／無法查證 | 是（需客戶裁示） |

- `FACT`：`app.py` 現行 `st.tabs` 為九格（五現行＋四「[新]」預覽），`app.py` 全檔對 `ui_v2`、`ui_v3` 的字面搜尋無命中（單組 `git grep`）；`ui_v2` 以 `ui_v2/app_preview.py` 等獨立預覽入口存在，`ui_v3` 目前只見 `mkt` 頁（`ui_v3/pages/mkt.py`）。故**新 UI 的任何能力都不在正式站入口**；舊 UI 五項仍掛在正式入口。
- `FACT`：`ui_v2/**`、`services/v2_tables/**`、`services/v2_domain/**` 內對 `fund_service`、`services.health`、`fund_screening`、`fund_total_return`、`fund_position`、`reconcile`、`capture_ratio`、`rotation`、`ledger_service` 的 import 字面搜尋 0 命中（單組 `git grep`，只掃該字表）。`INFERENCE`：因此「新 UI 有同名指標」不等於「舊邏輯已搬遷」；`services/v2_domain/nav_metrics.py` 的 `return_pct`／`drawdown_pct`／`vol_pct` 是由 `ui_v2/hld/logic.py` 搬入 L2（檔頭自述），**不是**從舊 UI 的 `calc_metrics` 搬來。
- **本組沒有發現任何一項可標「已搬遷」的舊 UI 邏輯**（`INFERENCE`，取決於未漏看；見第 7 節限制）。下列「已保留」只指「新 UI 已有同語意且已核准的等價能力」，並逐項說明，不等於舊邏輯已搬。

---

## 1. 單檔基金深掘

### 1.1 舊 UI 有效資料與判斷邏輯

來源：`ui/tab2_single_fund.py::render_single_fund_tab`、`services/fund_service.py::calc_metrics／finalize_fund_metrics`、`services/health/*`、`services/reconcile.py`、`services/fund_screening.py`、`services/fund_position.py`。

| 區塊 | 資料欄位與判斷規則（現行文字所述） | 標記 |
|---|---|---|
| 取數與狀態 | 輸入 MoneyDJ 代碼或網址 → `auto_fetch_moneydj`；`fund_data` 含 `full_key／fund_name／series／dividends／metrics／moneydj_raw／status／page_type／currency`；`status` 分 complete／partial／error，partial 顯示「歷史淨值未取得」。 | FACT |
| 指標 SSOT 寫入點 | `calc_metrics` 自述為 `sharpe／sortino／calmar／std_1y~5y／max_drawdown／risk_metric_meta` 的唯一寫入點；任一指標樣本不足回 None＋`risk_metric_meta[<指標>]["reason"]`，不回 0。 | FACT |
| 報酬欄位 | `ret_1w／1m／3m／6m／1y` 為純淨值、以列數取窗（6／22／65／130／252 列）；`ret_1y_total` 為配息還原含息；`ret_3y_ann_tr` 為含息 3 年年化；`ret_3y`／`ret_5y` 標示為向後相容。 | FACT |
| 年化配息率 | `annual_div_rate`＝近 12 個月實際配息合計÷最新淨值；窗內無紀錄為 None；wb05 官方值只作對帳。 | FACT |
| 吃本金檢查 | `check_eating_principal_1y_mk`：近一年含息報酬（還原淨值法，窗口天數不足則不判）< 年化配息率 → 吃本金；任一輸入缺 → 灰色「⬜ 資料未備／無法判定」並帶 reason（`dividend_data_missing`／`window_short`／`window_unknown`／`nav_missing`／`no_series`／`no_restored_value`）；非配息基金回 None（不判）。 | FACT |
| 3-3-3 | 單一 SSOT `services/health/dividend.py::check_333_principle`：成立年數與 3 年年化含息報酬兩條；`services/fund_screening.py` 檔頭記載晨星／同儕第三條不屬正式規格、`check_333_fund` 已停止作為判斷 SSOT。 | FACT |
| HWM σ 位置 | `compute_fund_position(fd, lookback=252)`：配息還原序列、fail closed；Tab2 以中性 label＋距 HWM %＋σ rank 呈現，AI 快照註明「位置證據非買賣建議」。 | FACT |
| 買賣點／買賣通道 | `calc_metrics` 寫 `buy1~3／sell1~3／pos_label`（σ 通道，仍讀原始 NAV）；Tab2 區塊「② 買賣點信號（標準差策略）」。BL-0438 登記此類仍讀 raw NAV、待客戶裁示。 | FACT（BL 登記）／NOT VERIFIED（現場畫面） |
| 健康度評分 | `services/health/grade.py::compute_4d_health`：維度為配息健康度、Sharpe、走勢、低波動、匯率風險（五維，函式名保留 4D），輸出含 `coverage`（幾維有證據／適用）；等第切點取自 `GRADE_CUTOFFS_4D`；匯率風險對台幣計價標 n/a 而非 0 分。 | FACT |
| 換標的建議 | `services/health/replacement.py::check_replacement_recommendation`：四條規則（吃本金且持有期、4D 等第、3-3-3 且持有期、Sharpe×最大回撤）；`DEC-2026-10-24-12`（DG-6）要求分類未判定時不得給換／留結論、判不動時不得顯示「保留」。 | FACT |
| 雙演算法對帳 | `finalize_fund_metrics` 注入 `sharpe_reconcile／ret_1y_reconcile／div_yield_reconcile`；`services/reconcile.py` 提供 `reconcile_pair／reconcile_sharpe／reconcile_fund_annual_return／reconcile_dividend_yield`，結果分 agree／disagree／a_missing／b_missing 四態（UI 渲染見 `docs/v2/62` A3 列）。 | FACT |
| 其他區塊 | 淨值來源與跨度揭露、三合一趨勢圖（MA／布林／配息標記）、風險表、近期配息、前十大持股（空持股時顯示三源診斷）、個股新聞、投資試算（本金→單位數／配息估算，用 FX）、AI 深度解盤（Gemini）。 | FACT（區塊存在）／NOT VERIFIED（各區塊內部規則，本組未逐段讀） |

### 1.2 新 UI 已有／已搬遷／仍缺

| 項 | 內容 | 標記 |
|---|---|---|
| 已有 | `EXP-6` 單檔基礎資料：基金全名、代碼、幣別、成立日、配息方式、費率（`ui_v2/exp/logic.py::EXP6_FIELDS`）；`EXP-2` 最近淨值日、最近淨值、近 12 個月配息佔淨值比。 | FACT |
| 已有（費率） | `services/v2_tables/exp_profile.py` 自述「最高經理費不冒充經理費率 → `mgmt_fee_rate_pct` 恆為 None」。 | FACT |
| 已有（持倉單檔） | `HLD-5`／`HLD-6`／`HLD-7`：區間報酬率（區間首末單位淨值）、期間波動（日報酬標準差×√252）、最大回撤、期間配息合計、配息佔淨值比；算式文字見 `ui_v2/hld/logic.py::FORMULA_TEXT`。 | FACT |
| 已搬遷 | 舊 UI 邏輯：本組未發現。 | INFERENCE |
| 仍缺 | 含息還原報酬、Sharpe／Sortino／Calmar、雙演算法對帳、吃本金檢查、3-3-3、HWM σ 位置、4D 健康度、換標的建議、持股／新聞、AI 解盤、投資試算。 | FACT（無對應符號）／INFERENCE（取決於未漏看） |

### 1.3 不能直接沿用的上位規格／新裁示

- 方向性輸出（買賣點、換標的、AI 解盤）：`docs/v2/44` 第一節 G1†／G2†／G3† 與「禁方向詞」，目前 B 線 v1 讀作現況（2026-10-15 改寫），日後依第七節第三小節之四准入；舊決策矩陣已隨舊 UI 退役（`DEC-2026-10-19-01`）。`FACT`
- 位置類指標讀原始 NAV 的問題：`DEC-2026-10-23-06`（HWM σ consumer 統一改讀 SSOT）；非 HWM 類仍待裁（BL-0438）。`FACT`
- 缺資料／分類未判定不得產生行動：`DEC-2026-10-24-10`、`DEC-2026-10-24-12`。`FACT`
- 健康維度：`DEC-2026-11-06-02`（保留原指標與原評等，另外揭露覆蓋率與正式准入狀態；原字母評級 ≠ 覆蓋完整 ≠ 正式准入）。`FACT`
- NAV 10 日：`DEC-2026-11-05-03`（既有實作事實保留、不得升格為正式全頁規則）。`FACT`；舊 UI 的新鮮度警示（綠／黃門檻 2／7 日）與新 UI 扣留（10 日）並存，見 `docs/v2/69` G-NAV-7。`FACT`
- 報酬口徑：`docs/v2/69` G-RET-1～G-RET-5、`BL-0524` 登記同名「近 1M／1Y」存在多套定義，待 Decision Gate。`FACT`

### 1.4 差異標籤（逐項）

| 能力 | 標籤 |
|---|---|
| 取數狀態三態與「歷史淨值未取得」揭露 | 已保留（新 UI 以「資料未備」等狀態語意涵蓋；非同一程式，`INFERENCE`） |
| 風險指標樣本不足回 None＋原因（不填 0） | 待核准沿用 |
| 含息 1Y／3Y 還原報酬、年化配息率 SSOT | 待核准沿用（涉報酬口徑，BL-0524） |
| 吃本金檢查（含灰色 reason 集合） | 待核准沿用（涉投資語意） |
| 3-3-3 | 待核准沿用（涉投資語意；現行單一 SSOT） |
| HWM σ 位置（配息還原、fail closed） | 待核准沿用（涉投資語意；BL-0428／BL-0438 未結） |
| 買賣通道 buy／sell／倉位標籤 | 不適用（新 UI 禁方向詞；舊決策矩陣退役）。注意：此為依現行規格的讀法，`INFERENCE`，可被客戶推翻 |
| 4D 健康度（含 coverage） | 待核准沿用（`DEC-2026-11-06-02` 要求另外揭露覆蓋率） |
| 換標的建議 | 不適用（方向性輸出；`DEC-2026-10-24-12` 規則另在） |
| 雙演算法對帳 chip | 待核准沿用（資料能力；對帳容差本組未讀，`NOT VERIFIED`） |
| 前十大持股／新聞／AI 解盤／投資試算 | 無法查證（本組未逐段讀其內部規則；AI 與投資試算另涉 FX 閘門與 OneBrain 未授權） |

### 1.5 牽涉未決 Gate／BL

BL-0398（A3 單檔內容，待客戶裁示）、BL-0524（口徑統一）、BL-0438（非 HWM 位置類）、BL-0428（legacy 行動語意重裁）、BL-0435（UI/UX Blueprint）、BL-0314（方向性輸出正式規格）。`FACT`（列名取自 `docs/BACKLOG.md`）

### 1.6 是否涉及投資語意

**是——需客戶裁示。**（買賣通道、換標的、吃本金、3-3-3、位置判斷、報酬口徑。本組不給答案。）

---

## 2. 多檔基金健診

### 2.1 舊 UI 有效資料與判斷邏輯

來源：`ui/tab_fund_grp_health.py::render_fund_grp_health_tab／_render_health_3tables`、`services/fund_row.py::process_one_fund／nav_freshness_label`、`services/health/report.py::build_health_analysis_row／build_dividend_summary_row`、`ui/helpers/fund_grp_health/unified.py::BATCH_UNIFIED_COLUMNS`、`ui/tab_batch_analysis.py`、`services/capture_ratio.py`、`services/rotation.py`。

| 區塊 | 資料與規則 | 標記 |
|---|---|---|
| 輸入 | `st.text_area` 多檔代號（上限 `_MAX_CODES`）＋本金 TWD（`number_input`，用同一本金讓配息放同尺度）；可從「我的組合」帶入。 | FACT |
| 逐檔 worker | `process_one_fund`（L2，無 `st`）；任一步失敗回 `{code, ok: False, error}`，不矇預設值；缺幣別／NAV／FX 誠實回 error。 | FACT |
| 大表欄位 | 識別／健康分析／配息相關／延伸／基期五段，含 Sharpe、最大回撤、3Y／5Y 年化、年化配息率、上下檔捕捉、σ rank、基期、4D Grade／Score、吃本金燈號、3-3-3 篩（欄位 SSOT：`BATCH_UNIFIED_COLUMNS`；總欄數 `docs/v2/62` B1 列記 70+，本組未逐欄計數）。 | FACT／NOT VERIFIED（欄數） |
| 新鮮度欄 | `nav_freshness_label` 把淨值日換成「🟢／🟠／🔴＋落後天數」，無日期回「⬜ 無淨值日期」；門檻取 `MJ_FRESH_DAYS_GREEN／YELLOW`（`shared/signal_thresholds`）。 | FACT |
| 樣本揭露 | `report.py::_nav_sample_label` 在大表標示「用幾筆淨值、跨多少天」，避免留白被讀成沒有風險。 | FACT |
| 捕捉率 | 月底對齊後分大盤上漲月／下跌月複利比；基準依幣別（TWD→TWII、USD→SPX、其餘 None）；上下檔月數不足門檻回 None；操盤評分由上下檔差導出。 | FACT |
| 核心／衛星 | 類別關鍵字與 3-3-3 推算（待定者不亂扣）；`DEC-2026-10-24-10` 分類未判定不得產生換／留。 | FACT |
| 批次 | `ui/tab_batch_analysis.py`：上傳／貼上代號 → 逐檔 `build_batch_unified_row` → 可續跑 → CSV 下載；失敗檔完整留在表裡，數值留白不填 0。 | FACT |
| 其他區塊 | 輪動配對（`services/rotation.py`，自標 legacy 行動語意、待 BL-0428）、換股顧問、配息明細、相關性、回測區塊。 | FACT（存在）／NOT VERIFIED（細節） |

### 2.2 新 UI 已有／已搬遷／仍缺

- 已有：`EXP-3` 並排對照最多 3 檔，列為最近淨值日、最近淨值、近 12 個月配息佔淨值比、經理費率（`ui_v2/exp/logic.py::COMPARE_ROWS`，檔內自述沿用已拍板草稿、客戶可逐項推翻）`FACT`。
- 已有：`HLD-1`（使用者門檻偏離）、`HLD-2`／`HLD-3`／`HLD-8`（使用者區間下的報酬、波動、配息、最大回撤、本金類配息佔比）`FACT`。
- 已有：`services/v2_domain/rule_filter.py` 三態比較（缺值＝無法判定，不算符合也不排除）`FACT`。
- 已搬遷（舊 UI 邏輯）：未發現 `INFERENCE`。
- 仍缺：逐檔健診寬表（Sharpe／3Y 5Y 年化／捕捉率／σ rank／4D／吃本金／3-3-3／核心衛星）、批次上傳與續跑、淨值新鮮度逐檔天數欄、樣本筆數與跨度揭露。`INFERENCE`

### 2.3 不能直接沿用

- 不照抄 70 欄寬表：`docs/v2/62` B1 列建議（總管建議，非核准）；欄位集合屬 UI 取捨，BL-0435。`FACT`
- 排名／推薦字樣與預設排序：`docs/v2/44` 第一節 1.2「禁排名為推薦」（含 2026-10-27 最小解凍的具體化，不含預設排序欄位）。`FACT`
- 方向性輸出（輪動配對、換股）：同 1.3。`FACT`
- 捕捉率基準與跨幣別：`docs/v2/69` G-BM-1（benchmark 三種定義）待裁。`FACT`
- NAV 新鮮度：舊 2／7 日警示 vs 新 10 日扣留，`DEC-2026-11-05-03` 未授權重定義。`FACT`

### 2.4 差異標籤

| 能力 | 標籤 |
|---|---|
| 逐檔失敗隔離、失敗列留在表內且數值留白 | 已保留（新 UI 有逐檔 error 與「資料未備」；`INFERENCE`） |
| 單檔 worker `process_one_fund`（取數＋指標一體） | 待核准沿用 |
| 統一欄位 SSOT（`BATCH_UNIFIED_COLUMNS`） | 待核准沿用（欄位取捨屬 UI Gate） |
| 逐檔淨值新鮮度天數欄 | 待核准沿用（牽涉 NAV 10 日，待決） |
| 樣本筆數／跨度揭露 | 待核准沿用 |
| 上下檔捕捉率／操盤評分 | 待核准沿用（涉投資語意與基準口徑） |
| 輪動配對、換股顧問 | 不適用（方向性輸出，依現行規格讀法，`INFERENCE`） |
| 核心／衛星分類 | 待核准沿用（涉投資語意與身份對應） |
| 批次上傳（約 400 檔）與續跑 | 無法查證（本組未驗其在現行資料量下的實際行為，`NOT VERIFIED`） |

### 2.5 牽涉未決 Gate／BL

BL-0399（`docs/v2/62` §3：B1～B6，待客戶裁示 `FACT`）、BL-0435、BL-0428、BL-0524。

### 2.6 是否涉及投資語意

**是——需客戶裁示。**（欄位取捨為 UI；捕捉率、輪動、核心衛星為投資語意。）

---

## 3. 基金體檢表（PK）

### 3.1 舊 UI 有效資料與判斷邏輯

來源：`ui/helpers/fund/checkup.py::build_checkup_dataframe／_grade／_extract_peer_1y／_period_ret／_compute_fund_health_kpis／_zone_cell`；掛載：`ui/tab_fund_grp_health.py`（健診頁）與 `ui/tab3_portfolio.py`。

| 欄位／規則 | 內容 | 標記 |
|---|---|---|
| 展示欄 | 近 1M／3M／6M、近 1Y 含息、同類平均（1Y）、超額（pp）、夏普、年化波動、計價幣別、NAV（原幣）、即時匯率、可申購單位數、月配股、每月 100 萬配息（TWD）、本金試算三欄、買點、體檢判定。 | FACT（`_DISPLAY_COLS`） |
| 近 1M／3M／6M | `_period_ret`：先讀 MoneyDJ 官方績效頁值，缺才退本地 `calc_metrics`（列數窗）。**同一欄兩種口徑混用** | FACT |
| 近 1Y 含息 | 只讀 `compute_1y_total_return` SSOT；算不出 → None，不退官方值也不退純淨值（2026-10-23 裁示 1B）。 | FACT |
| 同類平均 | 取自 MoneyDJ `risk_metrics.peer_compare` 內含「平均」的鍵；檔頭自述約三成基金抓不到 → 標 ⬜。 | FACT（檔頭自述）／NOT VERIFIED（三成比例，未實測） |
| 體檢判定 | 超額＝1Y 含息−同類平均；≥ +2 優等生、≤ −2 汰弱候選、其間普通生；任一缺 → 「⬜ 同類資料不足／報酬資料不足」。門檻 ±2pp 為檔內常數 `_EXCESS_GOOD／_EXCESS_LAG`。 | FACT |
| 買點 | `tag_price_zone`；`_zone_cell` 把未觸發與無法判定分開（⚪ 未觸發 vs ⬜ 無法判定），區間σ fallback 時加註（BL-0440）。 | FACT |
| 費率 | 只顯示本檔 `mgmt_fee`，原本的「類別→費率」寫死表已移除（因無來源）。 | FACT |
| 4 大健診卡 | 吃本金、月配息、年化配息率、TER；月配息＝本金×年化配息率÷12。 | FACT |

### 3.2 新 UI 已有／已搬遷／仍缺

- 新 UI 無對應（`docs/v2/62` B3 列「無」、Gap 標「舊有B無」）。`FACT`（62 §1 B3 列）；本組以 `ui_v2` 檔名／符號未見 `peer`、`同類` 字樣佐證 `NOT VERIFIED`（未另跑 grep）。
- 已搬遷：無。`INFERENCE`
- 仍缺：1M／3M／6M 短期績效、同類平均與超額、體檢判定、以本金為基準的月配息／可申購單位試算。`FACT`／`INFERENCE`

### 3.3 不能直接沿用

- 同類平均資料源：`DEC-2026-10-23`（3A）與 `services/fund_screening.py` 檔頭：晨星／同儕不屬正式規格、不新增同儕資料來源、不參與任何判定；體檢表的同類平均取自 MoneyDJ 績效頁，與該裁示的關係**本組不判定**。`FACT`（檔頭）／`NOT VERIFIED`（裁示對體檢表的射程）
- 「優等生／汰弱」字樣：`docs/v2/44` 禁方向詞清單含「汰弱留強」，目前 B 線 v1 讀作現況。`FACT`
- 1M／3M／6M 口徑：`docs/v2/69` G-RET-1、`BL-0524`（口徑不得自行統一）。`FACT`
- 可申購單位數與即時匯率：FX 閘門保持關閉（`DEC-2026-11-08-02`）。`FACT`

### 3.4 差異標籤

| 能力 | 標籤 |
|---|---|
| 1M／3M／6M 短期績效 | 待核准沿用（口徑待決） |
| 近 1Y 含息只讀單一 SSOT、不退官方值 | 待核准沿用 |
| 同類平均／超額／優等生·汰弱判定 | 無法查證（來源覆蓋率未實測；3A 射程未判）；判定字樣依現行規格讀為不適用（`INFERENCE`） |
| 「⚪ 未觸發」與「⬜ 無法判定」分開 | 已保留（Q4 沿用既有資料未備語意；新 UI 有相同三態概念，`INFERENCE`） |
| 本金試算（可申購單位、月配息） | 待核准沿用（涉 FX 閘門、本金輸入語意） |
| 費率不編造、無同類費率均值 | 已保留（新 UI `mgmt_fee_rate_pct` 恆 None 的同向做法，`FACT`／`INFERENCE`） |

### 3.5 牽涉未決 Gate／BL

BL-0399（`docs/v2/62` §3：B1～B6 含 B3，`FACT`）、BL-0524、BL-0440（買點無法判定三態）、BL-0435。

### 3.6 是否涉及投資語意

**是——需客戶裁示。**（同類比較、超額門檻、買點。）

---

## 4. 低基期篩選

### 4.1 舊 UI 有效資料與判斷邏輯

來源：`ui/tab_fund_grp_health.py::_render_low_base_screener`、`services/fund_screening.py::screen_funds／compute_base_state`、`services/rotation.py::classify_base`、`services/health/dividend.py::check_eating_principal_1y_mk`。

| 規則 | 內容 | 標記 |
|---|---|---|
| 篩選輸入 | 對「已載入的基金」（重用健診已抓 NAV，不新增外部抓取）：幣別多選、類別多選、「只留不吃本金」、「只留低基期」。 | FACT |
| 基期定位 | `compute_base_state`：σ rank 取自 `compute_fund_position`（配息還原、fail closed）；低基期 ⇔ σ rank ≤ 買點門檻、高基期 ⇔ ≥ 賣點門檻（常數 `ROTATION_BUY_SIGMA／ROTATION_SELL_SIGMA` 在 `shared/signal_thresholds`）；回看窗 252、可信度門檻 60 點。 | FACT |
| 無法判定 | SSOT 回 unavailable（歷史不足／σ≈0／配息資料未備／貨幣市場型／還原失敗）→ `base="unknown"`、`is_low_base=None`、原因轉載到 `note`；`only_low_base=True` 一定濾掉。 | FACT |
| 不吃本金 | 僅保留 `eats_principal is False`（明確不吃）；未知與吃本金皆濾掉。 | FACT |
| 排序 | 依 σ rank 由負至正，無法定位階者排最後。**注意：此排序在新 UI 規格下屬排名／預設排序議題。** | FACT／INFERENCE |
| 檔頭自述 | 「低基期／進場點」為 legacy 行動語意，規則、門檻、用字未改，待 BL-0428 重新裁示。 | FACT |
| 註解過期 | `docs/v2/62` 2026-10-23 狀態更新記：`compute_base_state` docstring 仍寫 √len(s)、實碼為 √252（程式註解，未改）。 | FACT（引文）／NOT VERIFIED（本組未重驗該註解現況） |

### 4.2 新 UI 已有／已搬遷／仍缺

- 已有：`EXP-1` 使用者自訂「欄位＋比較方向＋數值」條件列（七欄 `FUND_PROFILE_FIELDS`），無預設條件、無「常用條件」；`EXP-7` 篩選軌跡逐條記錄套用前後檔數；三態判定（缺值＝無法判定）。`FACT`
- 已搬遷：舊低基期／不吃本金邏輯，無。`INFERENCE`
- 仍缺：「基期」「不吃本金」這類衍生條件欄位（`docs/v2/62` C2 列已點出）。`FACT`

### 4.3 不能直接沿用

- 「進場候選」「低基期」行動語意：`docs/v2/44` 禁方向詞與 G1†（目前 B 線 v1 現況）；舊決策矩陣退役（`DEC-2026-10-19-01`）。`FACT`
- 預設排序／排名：`docs/v2/44` 1.2「禁排名為推薦」。`FACT`
- σ 位置口徑：`DEC-2026-10-23-06`；非 HWM 類另見 BL-0438。`FACT`
- 衍生條件進 EXP-1 屬欄位／語意新增，須 Gate（`docs/v2/62` C2 列：屬投資語意）。`FACT`

### 4.4 差異標籤

| 能力 | 標籤 |
|---|---|
| 缺資料不得入候選、無法判定者一律排除並帶原因 | 已保留（與 Q4 及 EXP 三態同向；`INFERENCE`） |
| 幣別／類別多選濾鏡 | 待核准沿用（新 EXP-1 已有 `ccy` 字面條件；類別欄位在 `fund_profile` 七欄中**未見**，`FACT`） |
| 「不吃本金」衍生條件 | 待核准沿用（涉投資語意） |
| 「低基期」σ rank 衍生條件與 −1.5／−0.5 切點 | 待核准沿用（涉投資語意；legacy 待 BL-0428）。**本組不建議任何門檻值** |
| 依 σ rank 排序 | 不適用（依現行 44 規格讀法，`INFERENCE`） |
| 篩選只在「已載入基金」集合內 | 無法查證（新 UI 候選母體來源為 `fund_profile`／`EXP-2`，兩者母體差異本組未驗，`NOT VERIFIED`） |

### 4.5 牽涉未決 Gate／BL

BL-0400（`docs/v2/62` §3：C1 C2 C4，待客戶裁示 `FACT`）、BL-0428、BL-0438、BL-0435、`DEC-2026-10-22-02` G8（暫不核准 UI 改版）。

### 4.6 是否涉及投資語意

**是——需客戶裁示。**（低基期定義、不吃本金條件、σ 切點、排序。）

---

## 5. 目前帳本

### 5.1 舊 UI 有效資料與判斷邏輯

來源：`ui/tab3_t7_ledger.py::render_t7_section`（「📒 目前帳本 + 以息養股現金流」區塊）、`_latest_nav_fx_t7`、`services/satellite.py::satellite_stop_gain`、`services/ledger_service.py`、`repositories/ledger_repository.py`。

| 區塊 | 資料與規則 | 標記 |
|---|---|---|
| 逐檔表 | 欄位：保單、代碼、基金名稱、幣別、持有單位、平均買入淨值、含息成本、平均買入匯率、最新 NAV、最新 FX、成本基礎 TWD、市值 TWD、未實現損益 TWD／%、累積已配息率、配息率、預估月配息、預估月配股、衛星停利。 | FACT |
| 市值與損益 | 市值＝`position.value_twd(nav, fx)`；損益＝市值−成本基礎（`net_investment_twd`）；報酬率在成本≤0 時顯示「⬜ 無法計算」。 | FACT |
| 三種缺值分流 | 無持倉（列入「未計入」）／有持倉但抓不到報價（市值整列留白，且**不計入**總市值與總報酬，並以警示說明理由：視為 0 會變 −100%、視為成本會變打平，皆編造）／配息率未備（不計入年配息與月現金流，提示「不是不配息」）。 | FACT |
| 組合 KPI | 組合市值、整體未實現損益（含%）、預估年現金配息、月被動現金流、年配股；現金／配股拆分依各檔 `div_cash_pct`；KPI 顯示「已計入 N／M 檔」。 | FACT |
| 近似市值 | 無任何持倉明細時，組合市值以 `invest_twd` 加總作近似，標「⚠️ 近似」。 | FACT |
| FX 取得 | `_latest_nav_fx_t7`：幣別未知或 Sheet／來源衝突 → 不查匯率（fx=0，走「抓不到」）；即時匯率缺 → 退 `fund.fx_rate` → 再退帳本平均買入匯率，退到平均買入匯率時記入 `_t7_fx_ledger_avg` 並 log（行為保留、補旗標）。 | FACT |
| 衛星停利 | `satellite_stop_gain`：只對明確衛星判燈，核心不判、未設定顯示「⬜ 未設定」、未填成本誠實無法判；分批／強制兩個門檻為 `SATELLITE_STOP_GAIN_BATCH_PCT／FORCE_PCT`（檔頭 15%／20%）。 | FACT |
| 帳本資料落點 | `_Ledgers`（事件列）、`_T7_State` 等 Sheets 分頁；`docs/v2/62` 2026-10-23 狀態更新：`replace_ledgers_for_policy` 編輯持倉時整段重寫該保單帳本（不是純 append-only）；`calculate_xirr` 與 `GhostPortfolio` production caller 為 0（該稽核補驗結果）。 | FACT（引文）／NOT VERIFIED（本組未重驗） |
| in-memory | 畫面自述「in-memory，隨頁面重整清空；已同步至 Google Sheet 的部分見存讀面板」。 | FACT |

### 5.2 新 UI 已有／已搬遷／仍缺

- 已有：`HLD-5` 單檔展開含單位數、成本、類別（`docs/v2/62` E7 列）；`ui_v2/alo/` 有成本與市值兩種基準的類別分布、缺淨值／缺匯率時該類別照實呈現資料未備（`ui_v2/alo/logic.py` 檔內說明）。`FACT`
- 已有（候選，未核准）：`services/v2_domain/allocation_evidence.py` 檔頭自述為 BL-0542 G1-3 的「CANDIDATE design」，所有名稱皆為內部候選非核准詞彙。`FACT`
- 已搬遷：舊帳本的組合市值／損益／現金流邏輯，無。`INFERENCE`
- 仍缺：組合層市值彙總與未實現損益、年／月現金配息與配股、衛星停利。`FACT`（62 E7 列）／`INFERENCE`

### 5.3 不能直接沿用

- 缺報價不得以 0 或成本頂替：舊 UI 已如此，與新 UI「缺值不是零」同向，無衝突。`FACT`／`INFERENCE`
- FX 保底鏈（`fund.fx_rate`、帳本平均買入匯率）：Q5 FX 閘門保持關閉、`DEC-2026-11-08-02` 禁止以相同方法重跑；新 UI 要不要有任何匯率退路屬未授權。`FACT`
- 預估年配息＝市值×配息率：配息率口徑（年化配息率 SSOT）與 `BL-0524` 待決口徑相關。`INFERENCE`
- 衛星停利燈：屬方向性輸出（停利）；`docs/v2/44` 禁方向詞含「停利」，目前 B 線 v1 讀作現況。`FACT`
- 組合層彙總與現金水位：BL-0393 (3)(4)（持倉頂層概況與含息報酬定義、現金水位與配置分母）為 Phase 5 Data Gap 待研究，登記非授權。`FACT`
- 「💼 我的資產」新 UI2 草案：BL-0542（G-1～G-5 仍待裁示）與 `docs/v2/82`。`FACT`（BL 登記）；本組未讀 82 全文 `NOT VERIFIED`。

### 5.4 差異標籤

| 能力 | 標籤 |
|---|---|
| 缺報價整列留白、不計入總市值、不以 0／成本頂替 | 已保留（理念同向；新 ALO 對缺淨值／缺匯率照實呈現，`INFERENCE`） |
| 「已計入 N／M 檔」覆蓋揭露 | 待核准沿用（`DEC-2026-11-06-02` 對健康維度要求揭露分母，帳本同理的適用範圍本組未判） |
| 組合市值、未實現損益 TWD／% | 待核准沿用（涉報酬口徑、FX） |
| 預估年現金配息、月被動現金流、配股拆分 | 待核准沿用（涉配息率口徑、`div_cash_pct`） |
| 衛星停利燈與 15%／20% 門檻 | 不適用（方向性）；門檻值本組不建議任何數字 |
| 近似市值（以 `invest_twd` 代替）並標近似 | 無法查證（新 UI 是否允許「近似」屬待決；本組未見對應規格） |
| 幣別未知／衝突不查匯率 | 已保留（Q4 同向；2026-10-10 客戶裁示 Q1／Q4 為檔內註解所述，`FACT`） |
| FX 退路鏈 | 不適用（FX 閘門保持關閉） |
| 帳本事件重寫與 XIRR | 無法查證（`docs/v2/62` 更新為單組稽核結果，本組未重驗） |

### 5.5 牽涉未決 Gate／BL

BL-0404（組合層彙總缺口，待客戶裁示，交叉 BL-0393 (3)(4)）、BL-0393、BL-0542、BL-0524、`DEC-2026-11-08-02`（FX）。`FACT`

### 5.6 是否涉及投資語意

**是——需客戶裁示。**（損益與報酬口徑、停利、現金流與配息率。）

---

## 6. 值得保留的資料能力清單（**作者候選，非核准**；白話，每項一句）

1. 缺資料或算不出來時回「資料未備／無法判定」並帶白話原因，而不是填 0 或沿用別的數字。
2. 同一個指標只留一個口徑來源，並在畫面上說明樣本筆數與跨度。
3. 一檔失敗不拖垮整批，失敗列留在結果裡並標原因。
4. 淨值日期與落後天數攤在表上，讓人分得出「週末沒開盤」和「早就停更」。
5. 年化配息率用近 12 個月實際配息合計除以最新淨值，官方值只做對帳。
6. 含息報酬用同一份還原序列算，窗口不足就不給數字。
7. 同一個數字有第二種算法時，並列顯示一致／不一致／缺值四種狀態。
8. 3-3-3、吃本金這類篩選條件只保留一個判斷來源，避免同一檔在不同頁面燈號不同。
9. 位置判斷以配息還原序列為準，無法判定時顯示原因而不是中性。
10. 使用者自訂條件篩選時，缺值既不算符合也不排除，並逐條記錄套用前後檔數。
11. 帳本缺報價時整列留白、不計入總額，並說明「已計入幾檔／共幾檔」。
12. 幣別未知或來源衝突時不查匯率、不假設美元。
13. 不編造沒有來源的同類費率或同類平均。
14. 本金固定同一數字時，各檔配息才能放在同一尺度比較。

（以上 14 項為本組整理的候選，**未經客戶核准**；是否納入、放哪頁、用什麼名稱，皆屬 UI／Gate 決定。）

---

## 7. 限制與未涵蓋範圍

- 本組只讀程式與文件，**未實跑任何 UI**、未起 Streamlit、無 secrets；可達性為靜態 import／呼叫追蹤（`app.py` 的 `st.tabs` 區塊與 `with tab_*` 分支，及 `ui/tab_fund_research.py` 的模式分派）。`FACT`（方法）
- `ui/tab2_single_fund.py`（約 2.9 千行）、`ui/tab3_t7_ledger.py`（約 3.5 千行）、`ui/tab_fund_grp_health.py` 只讀了與五項直接相關的區塊與符號；三率穿透、持股來源診斷、AI 解盤 prompt、投資試算內部公式、相關性／回測區塊、換股顧問等**未逐行讀**。`NOT VERIFIED`
- 未讀 `docs/v2/44` 全文（只讀第一節與各塊標題、EXP／HLD 代表塊）；`docs/v2/45`、`docs/v2/46` 只讀標題與帳本相關列（本組未在 46 的六列中找到與本五項相關者，取決於未漏看）。`NOT VERIFIED`
- 新 UI 側只讀 `ui_v2/exp`、`ui_v2/hld`、`ui_v2/alo` 的 `logic.py` 常數／符號與 `services/v2_domain`、`services/v2_tables` 的檔頭；`ui_v2/alo/page.py`、`hld/page.py`、`exp/page.py` 的實際畫面行為未讀。`NOT VERIFIED`
- 「新 UI 沒有 X」類陳述皆為本組以檔名／符號／字表檢視的結果，其正確性取決於是否漏看，**未經第二組驗證**；字表覆蓋見第 0 節（僅九個模組名）。
- 未重驗 `docs/v2/62`、`docs/v2/69`、`docs/DECISIONS.md` 內他組結論（只引用並標注來源）；BL 與 DEC 的編號對應僅確認了正文中直接出現者，其餘標 `NOT VERIFIED`。
- 不涵蓋：市場總覽、資產配置模擬、設定與診斷、資料來源取代、AI／OneBrain、`ui_v3` 非 `mkt` 頁。
- 本檔所有敘述皆為資料與判斷邏輯的現況描述；**未新增任何門檻、公式或判定、未建議移植、未把推論寫成核准**。

## 8. 單組作者揭露

- 本檔由單一作者（執行組）一次產出，**未經第二組獨立驗證**；之後預定有獨立 QA。依 `CLAUDE.md` §-2 規則 6，本檔的全稱性敘述只能當待驗事項，不得作為後續動作的前提。
- 引用的客戶選定方向（Q3／Q4／Q5、NAV 10 日、報酬口徑、身份對應維持待決）為派工單所述，本組僅對 Q5 在 `DEC-2026-11-08-02` 與 NAV 10 日在 `DEC-2026-11-05-03` 找到 repo 內文字佐證；Q3／Q4／身份對應的客戶原話 repo 內本組未查證。
- 未連網、未改 repo、未 commit／push，未使用 checkout／reset／restore／stash；僅寫入 scratchpad。
