> 基準 origin/main 772d6e9a；單組作者草稿；獨立 QA 已完成一輪並已回修，見 PR #1177，非 QA 通過，合併前仍待 CI；不構成正式契約或裁示

> 修訂註記：QA 一輪已回修（M1、S1～S4、S7、NIT）；回修由同一作者執行並對 `origin/main` `772d6e9a` 自行重驗後落筆，未經第二輪獨立驗證。

# W3｜舊 UI 有價值邏輯比較（五項；唯讀盤點草稿，QA 一輪回修版）

- **基準**：`origin/main` `772d6e9a179413c3596f5a5150a6c07edb7a12af`。讀取只用 `git show origin/main:<檔>` 與 `git grep origin/main`，未改 repo、未 commit、未連網。
- **性質**：資料與判斷邏輯盤點（D2 唯讀資料需求草案的一部分）。**不是** UI 改版授權、不是實作建議、不是核准、不建議移植、不給門檻。舊 UI 依 `DEC-2026-11-02-02` 第 (1)～(4) 點（經 `DEC-2026-11-02-03` 修訂但 Old UI 邊界不變）永久只作 read-only logic reference。
- **標記**：每句結論後標 `FACT`（本組讀到該檔／符號的文字）／`INFERENCE`（本組推論）／`NOT VERIFIED`（未驗）。來源寫「檔名＋符號／節名」，不寫行號。
- **客戶已選方向（經派工轉達；Q3／Q4／身份對應的客戶原話本組 repo 內未查到，`NOT VERIFIED`）**：Q3 只比這五項；Q4 缺資料沿用既有「資料未備／無法判定」；Q5 FX 閘門保持關閉（`DEC-2026-11-08-02`，`FX_OBS_DATE_RULE_VERIFIED` 維持 False，`FACT`）；不得自行統一不同績效算法；NAV 10 日（`DEC-2026-11-05-03`）、報酬口徑（`BL-0524`）、身份對應維持待決。
- **差異標籤（只用四種）**：已保留／待核准沿用／不適用／無法查證。

## 本檔三條線的定義（M1：全篇一律用這三個名字，不再用籠統的「新 UI」）

| 線 | 範圍 | 是否掛在正式入口 | 依據 |
|---|---|---|---|
| **線 A｜舊分頁** | `app.py` 的五個現行分頁及其 `ui/tab*.py`：② `ui/tab_fund_grp_health.py`、③ `ui/tab_fund_research.py`（含 `ui/tab2_single_fund.py`、`ui/tab_batch_analysis.py`）、④ `ui/tab3_portfolio.py`（含 `ui/tab3_t7_ledger.py`） | 是 | `app.py` 的 `with tab_health／tab_research／tab_portfolio` 分支，`FACT` |
| **線 B｜`ui/views`「[新]」並行預覽** | `app.py` 第 ⑥～⑨ 格：`ui/views/page_02_health.py`（⑥）、`page_03_research.py`（⑧）、`page_04_portfolio.py`（⑨）、`page_05_settings.py`（⑦） | **是**（同一個 `st.tabs`，與舊分頁並列） | `app.py` 的 `with tab_preview_health／research／portfolio／settings` 分支，`FACT` |
| **線 C｜`ui_v2`／`ui_v3`** | `ui_v2/`（B 線預覽五頁；`DEC-2026-11-02-03` 稱 Legacy New UI／reuse candidate）與 `ui_v3/`（目前只見 `mkt` 頁）。New UI2 的 presentation 目標與本組讀到的 `ui_v3` 範圍是否一致，`NOT VERIFIED` | **否**（`app.py` 對 `ui_v2`、`ui_v3` 字面搜尋 0 命中；以 `ui_v2/app_preview.py` 等獨立入口存在） | `git grep` 單組結果，`FACT`／取決於未漏看 |

- `FACT`：`app.py` 現行 `st.tabs` 為九格（五現行＋四「[新]」）。
- **標籤的相對基準**：本檔每項在「標籤」欄分兩欄給——「線 B」欄與「線 C」欄；標籤語意＝**該線相對線 A 的該能力**：已保留（該線已有同碼或同 SSOT 的等價能力，且本組在該線側讀到符號證據）／待核准沿用（線 A 有、該線沒有或未確認，是否沿用待客戶核准）／不適用（有明確非格式性理由，如 DEC 已裁）／無法查證（本組沒有足夠證據）。「已保留」**不是**「已核准」，也不是「New UI2 契約已含」。

---

## 0. 結論先行（一頁）

| # | 項目 | 線 A 現況 | 線 B（⑥～⑨）現況 | 線 C（ui_v2／ui_v3）現況 | 涉投資語意 |
|---|---|---|---|---|---|
| 1 | 單檔基金深掘 | 可達：tab_research → `render_fund_research_tab` → `render_single_fund_tab` `FACT` | ⑧ `render_fund_research` 的「單一基金深度」區塊：淨值卡、1M～5Y 績效（wb01 或本地補算，標來源）、Sharpe／Sortino／Calmar／最大回撤／年化波動（缺值逐項附原因）、前十大持股、配息列、取數軌跡、投資試算；**未見**吃本金／3-3-3／4D／σ 位置／對帳／AI 解盤／個股新聞 `FACT`（檔內字面搜尋） | EXP-6 六欄基礎資料＋最近淨值＋近 12 個月配息佔淨值比；HLD-5 持倉單檔展開 `FACT` | 是 |
| 2 | 多檔基金健診 | 可達：tab_health、tab_research 批次模式 `FACT` | ⑥ 持倉健診：結論兩句、警示卡、逐檔體檢表 9 欄，另有閘門後的委派區（體檢 PK、互斥、配息矩陣、相關性、−2σ、回測、AI 跨檔）；⑧ 批次分析以 `BATCH_UNIFIED_COLUMNS` 逐檔 `build_batch_unified_row`，檔內自述「照搬全部欄位、不挑子集」（含 4D、吃本金、3-3-3、基期、換標的建議、捕捉率欄）`FACT` | EXP-3 並排最多 3 檔 4 列；HLD-1／2／3／8 `FACT` | 是 |
| 3 | 基金體檢表 | 可達：健診頁 `render_fund_checkup`（亦被 ④ 呼叫）`FACT` | ⑥ **不是無對應**：委派區在 Checkbox Gate（`DELEGATE_GATE_LABEL`，`value=False` 預設不勾）之後呼叫同一個 `render_fund_checkup`；另外 ⑥ 預設可見的「結論句②」經 `_peer_verdicts` 走同一支 `_grade`／`_extract_peer_1y` 數各判定桶 `FACT` | 無對應 `FACT`（本組未見同類平均、超額、短期績效符號） | 是 |
| 4 | 低基期篩選 | 可達：健診頁 `_render_low_base_screener`（唯一 ui 層 caller）`FACT` | ⑥、⑧ 均**無**篩選器；⑧ 批次大表有「基期」欄（欄骨架 `BATCH_UNIFIED_COLUMNS` 含之）；⑥ 委派區有「−2σ 超跌警示」`_render_oversold_badges` `FACT` | EXP-1 七欄字面條件，無衍生條件 `FACT` | 是 |
| 5 | 目前帳本 | 可達：tab_portfolio → `render_portfolio_tab` → `render_t7_section` `FACT` | ⑨ 的「交易帳本」區塊 `_render_ledger`：檔內自述為灰態、指路回舊分頁帳本（`REASON_LEDGER`）；ⓘ 實際執行畫面 `NOT VERIFIED` | ALO 有成本／市值兩基準的類別分布；HLD-5 單檔；無組合層損益與現金流 `FACT`（ALO 畫面細節 `NOT VERIFIED`） | 是 |

- **M1 重驗結論（成立）`FACT`**：QA 指出的事實全部屬實——⑥ `page_02_health.py` 在 `DELEGATED_ENTRIES` 與 `_render_delegated_sections` 內 lazy import `ui.helpers.fund.checkup.render_fund_checkup` 等舊模組；模組頂部 docstring 列有 `services.health.dividend.check_eating_principal_1y_mk`、`services.fund_total_return.compute_1y_total_return`、`services.fund_row.nav_freshness_label`、`services.portfolio_service.calc_holdings_overlap` 四個直接入口；`_compute_fund_health_kpis`、`_ret_1y_total`、`_extract_peer_1y`、`_grade` 亦列於委派／呼叫清單；caption 逐字為「與舊分頁同一份程式碼、同一條資料路徑」。本檔上一版「新 UI 的任何能力都不在正式站入口」**不實，已撤回**；改為只對線 C 成立。
- **舊邏輯在線 B 已掛正式入口，但不等於「已搬遷」`INFERENCE`**：線 B 是**委派／import 同一份舊程式**，舊檔不動；本組沒有發現「把舊邏輯搬進新位置並讓舊檔消失」的例子。
- **S7 重驗結論（成立）`FACT`**：`ui_v2/**`、`services/v2_tables/**`、`services/v2_domain/**` 對 `fund_service`、`services.health`、`fund_screening`、`fund_total_return`、`fund_position`、`reconcile`、`capture_ratio`、`rotation`、`ledger_service` 的**直接靜態 import** 為 0 命中（單組 `git grep`，只掃該字表）；**但這只對直接 import 成立**：`services/v2_tables/nav_dividend.py` 在 module 層 import `services.moneydj_fetcher.auto_fetch_moneydj`，而 `auto_fetch_moneydj` 函式內 lazy import `services.fund_service.fetch_fund_from_moneydj_url_enriched`，後者呼叫 `finalize_fund_metrics`。故線 C 取數鏈**執行期**會跑 `fund_service.finalize_fund_metrics`（`INFERENCE`：本組讀到呼叫鏈文字，未實跑；執行期是否每條路徑皆走到，`NOT VERIFIED`）。因此「線 C 沒有同名指標」不能解讀成「線 C 完全不碰舊指標程式」，也不能解讀成「線 C 讀得到那些指標」（`ui_v2` 只讀 L2 表的列，是否取用 `metrics` 內欄位本組未驗）。
- `services/v2_domain/nav_metrics.py` 的 `return_pct`／`drawdown_pct`／`vol_pct` 檔頭自述由 `ui_v2/hld/logic.py` 搬入 L2，**不是**從線 A 的 `calc_metrics` 搬來 `FACT`。

---

## 1. 單檔基金深掘

### 1.1 線 A 的有效資料與判斷邏輯

來源：`ui/tab2_single_fund.py::render_single_fund_tab`、`services/fund_service.py::calc_metrics／finalize_fund_metrics`、`services/health/*`、`services/reconcile.py`、`services/fund_screening.py`、`services/fund_position.py`。

| 區塊 | 資料欄位與判斷規則（現行文字所述） | 標記 |
|---|---|---|
| 取數與狀態 | 輸入 MoneyDJ 代碼或網址 → `auto_fetch_moneydj`；`fund_data` 含 `full_key／fund_name／series／dividends／metrics／moneydj_raw／status／page_type／currency`；`status` 分 complete／partial／error，partial 顯示「歷史淨值未取得」。 | FACT |
| 指標 SSOT 寫入點 | `calc_metrics` 自述為 `sharpe／sortino／calmar／std_1y~5y／max_drawdown／risk_metric_meta` 的唯一寫入點；任一指標樣本不足回 None＋`risk_metric_meta[<指標>]["reason"]`，不回 0。 | FACT |
| 報酬欄位 | `ret_1w／1m／3m／6m／1y` 為純淨值、以列數取窗（6／22／65／130／252 列）；`ret_1y_total` 為配息還原含息；`ret_3y_ann_tr` 為含息 3 年年化；`ret_3y`／`ret_5y` 標示為向後相容。 | FACT |
| 年化配息率 | `annual_div_rate`＝近 12 個月實際配息合計÷最新淨值；窗內無紀錄為 None；wb05 官方值只作對帳。 | FACT |
| 吃本金檢查 | `check_eating_principal_1y_mk`：近一年含息報酬（還原淨值法，窗口天數不足則不判）< 年化配息率 → 吃本金；任一輸入缺 → 灰色 `status="⬜ 資料未備／無法判定"` 並帶 `reason`（`dividend_data_missing`／`window_short`／`window_unknown`／`nav_missing`／`no_series`／`no_restored_value`）；**非配息基金：** 上游 `resolve_dividend_rate_12m` 回 `status="unavailable"`、`reason="no_dividend"`，而 `check_eating_principal_1y_mk` 見到該 reason 時整體回傳 `None`（不判）。（NIT 重驗：QA 所述的 `status=unavailable／reason=no_dividend` 屬上游函式的回傳，`check_eating_principal_1y_mk` 本身回 `None`，兩者並存；本檔兩層都寫明。） | FACT |
| 3-3-3 | 單一 SSOT `services/health/dividend.py::check_333_principle`：成立年數與 3 年年化含息報酬兩條；`services/fund_screening.py` 檔頭記載晨星／同儕第三條不屬正式規格、`check_333_fund` 已停止作為判斷 SSOT（`DEC-2026-10-23-02` 3A）。 | FACT |
| HWM σ 位置 | `compute_fund_position(fd, lookback=252)`：配息還原序列、fail closed；Tab2 以中性 label＋距 HWM %＋σ rank 呈現，AI 快照註明「位置證據非買賣建議」。 | FACT |
| 買賣點／買賣通道 | `calc_metrics` 寫 `buy1~3／sell1~3／pos_label`（σ 通道，仍讀原始 NAV）；Tab2 區塊「② 買賣點信號（標準差策略）」。`BL-0438` 登記此類仍讀 raw NAV、待客戶裁示。 | FACT（BL 登記）／NOT VERIFIED（現場畫面） |
| 健康度評分 | `services/health/grade.py::compute_4d_health`：維度為配息健康度、Sharpe、走勢、低波動、匯率風險（五維，函式名保留 4D），輸出含 `coverage`；等第切點取自 `GRADE_CUTOFFS_4D`；匯率風險對台幣計價標 n/a 而非 0 分。 | FACT |
| 換標的建議 | `services/health/replacement.py::check_replacement_recommendation`：四條規則；`DEC-2026-10-24-12`（DG-6）要求分類未判定時不得給換／留結論、判不動時不得顯示「保留」。 | FACT |
| 雙演算法對帳 | `finalize_fund_metrics` 注入 `sharpe_reconcile／ret_1y_reconcile／div_yield_reconcile`；`services/reconcile.py` 結果分 agree／disagree／a_missing／b_missing 四態。 | FACT |
| 其他區塊 | 淨值來源與跨度揭露、三合一趨勢圖、風險表、近期配息、前十大持股（空持股時顯示三源診斷）、個股新聞、投資試算（本金→單位數／配息估算，用 FX）、AI 深度解盤（Gemini）。 | FACT（區塊存在）／NOT VERIFIED（各區塊內部規則，本組未逐段讀） |

### 1.2 線 B（⑧）與線 C 現況

| 線 | 已有 | 仍缺（相對線 A） | 標記 |
|---|---|---|---|
| **線 B ⑧** `ui/views/page_03_research.py::_render_deep_dive` | 以 `services.moneydj_fetcher.auto_fetch_moneydj` 取數；`PERF_PERIODS`（1M／3M／6M／1Y／3Y／5Y，來源標 `wb01` 或 `local_calc`）；`RISK_METRICS`（Sharpe、Sortino、Calmar、最大回撤、年化波動，缺值逐項帶 `_risk_reason`，不補 0）；前十大持股；配息列（含幣別一致性 `reconcile_row_currencies`）；取數軌跡；投資試算（`services.fund_invest_calc`，客戶 2026-09-08 拍板搬入 ⑧，檔內自述） | 含息還原 1Y／3Y 報酬、雙演算法對帳 chip、吃本金、3-3-3、σ 位置、4D、換標的、個股新聞、AI 解盤（檔內字面搜尋未見，取決於未漏看） | FACT／INFERENCE |
| **線 C** | EXP-6 六欄基礎資料（`ui_v2/exp/logic.py::EXP6_FIELDS`）、EXP-2 最近淨值日／最近淨值／近 12 個月配息佔淨值比（比值細部算式本組未讀，`NOT VERIFIED`）；`services/v2_tables/exp_profile.py` 自述 `mgmt_fee_rate_pct` 恆為 None（最高經理費不冒充）；HLD-5／6／7 持倉單檔的區間報酬、波動、最大回撤、配息（算式文字 `ui_v2/hld/logic.py::FORMULA_TEXT`） | 同上，另缺持股、績效分期（1M／3M／6M）、投資試算 | FACT／INFERENCE |

### 1.3 不能直接沿用的上位規格／新裁示

- `docs/v2/44` 第一節 G1†／G2†／G3† 與「禁方向詞」：**只就線 C 的介面文案**——目前 B 線 v1 的介面文案不出現該方向詞串（2026-10-15 改寫為現況，非永久禁令），方向性輸出日後依第七節第三小節之四准入；舊決策矩陣已隨舊 UI 退役（`DEC-2026-10-19-01`）。`FACT`。**線 B 不受 44 約束的程度本組未判**（`NOT VERIFIED`）。
- 位置類指標讀原始 NAV：`DEC-2026-10-23-02`（2C，HWM σ 統一改讀配息還原序列；其「影響範圍」欄寫明範圍為 `services/`、`ui/` 舊站 consumer，且「不改 `ui_v2/`」）；非 HWM 類仍待裁（`BL-0438`）。`FACT`
- 缺資料／分類未判定不得產生行動：`DEC-2026-10-24-10`、`DEC-2026-10-24-12`。`FACT`
- 健康維度：`DEC-2026-11-06-02`（保留原指標與原評等，另外揭露覆蓋率與正式准入狀態）。`FACT`
- NAV 10 日：`DEC-2026-11-05-03`（既有實作事實保留、不得升格）；線 A 新鮮度警示（綠／黃，`MJ_FRESH_DAYS_GREEN／YELLOW`）與線 C 扣留（`NAV_NOT_READY_DAYS`）並存，見 `docs/v2/69` G-NAV-7。`FACT`
- 報酬口徑：`docs/v2/69` G-RET-1～G-RET-5、`BL-0524`。`FACT`

### 1.4 差異標籤（逐項；兩欄分別對線 B、線 C）

| 能力 | 線 B（⑧） | 線 C | 備註 |
|---|---|---|---|
| 取數狀態與「資料未備」揭露 | 已保留（⑧ 用同一條 `auto_fetch_moneydj`，`FACT`） | 無法查證（僅理念同向；線 C 有「資料未備」狀態語意，但與線 A 是否同判定規則本組未驗） | |
| 風險指標樣本不足回 None＋原因 | 已保留（⑧ `_risk_reason` 直接讀 `risk_metric_meta`，`FACT`） | 待核准沿用 | |
| 近期績效分期（1M～5Y） | 已保留（⑧ `PERF_PERIODS`；來源 wb01 或本地補算，與線 A 同為多口徑，`FACT`） | 待核准沿用（口徑待決，`BL-0524`） | |
| 含息 1Y／3Y 還原報酬、年化配息率 SSOT | 無法查證（⑧ 未見該欄；⑥ 逐檔表「近 1 年」呼叫 `compute_1y_total_return`，屬持倉頁，`FACT`） | 待核准沿用（涉報酬口徑） | |
| 吃本金檢查 | 無法查證（⑧ 單檔區塊未見；⑥ 以 `check_eating_principal_1y_mk` 呈現，`FACT`） | 待核准沿用（涉投資語意） | |
| 3-3-3 | 無法查證（⑧ 單檔區塊未見；⑧ 批次欄骨架含「3-3-3 篩」，`FACT`） | 待核准沿用（涉投資語意） | |
| HWM σ 位置（配息還原、fail closed） | 無法查證（⑧ 單檔未見；批次含「基期」欄，`FACT`） | 待核准沿用（`BL-0428`／`BL-0438` 未結） | |
| 買賣通道 buy／sell／倉位標籤 | 無法查證（⑧ 未見） | 無法查證（僅就介面用字：44 目前 B 線 v1 文案不出現方向詞；資料層是否保留待裁，且本欄屬投資語意，不給答案） | |
| 4D 健康度（含 coverage） | 無法查證（⑧ 單檔未見；⑧ 批次欄含 4D Grade／Score，`FACT`） | 待核准沿用（`DEC-2026-11-06-02`） | |
| 換標的建議 | 無法查證（⑧ 單檔未見；⑧ 批次欄含「換標的建議」，`FACT`） | 無法查證（僅就介面用字；`DEC-2026-10-24-12` 另規定判不動時的語意） | |
| 雙演算法對帳 chip | 無法查證（⑧ 未見對帳 chip） | 待核准沿用（對帳容差本組未讀） | |
| 前十大持股、配息列、投資試算 | 已保留（⑧ 有；投資試算涉 FX，閘門關閉下行為本組未驗，`NOT VERIFIED`） | 待核准沿用 | |
| 個股新聞／AI 解盤／三率穿透 | 無法查證（⑧ 未見；本組未讀線 A 內部規則） | 無法查證（AI 另涉 OneBrain 未授權） | |

### 1.5 牽涉未決 Gate／BL

`BL-0398`（A3，待客戶裁示）、`BL-0524`、`BL-0438`、`BL-0428`、`BL-0435`、`BL-0314`。`FACT`（取自 `docs/BACKLOG.md` 與 `docs/v2/62` §3）

### 1.6 是否涉及投資語意

**是——需客戶裁示。**（買賣通道、換標的、吃本金、3-3-3、位置判斷、報酬口徑。本組不給答案。）

---

## 2. 多檔基金健診

### 2.1 線 A 的有效資料與判斷邏輯

來源：`ui/tab_fund_grp_health.py::render_fund_grp_health_tab／_render_health_3tables`、`services/fund_row.py::process_one_fund／nav_freshness_label`、`services/health/report.py`、`ui/helpers/fund_grp_health/unified.py::BATCH_UNIFIED_COLUMNS`、`ui/tab_batch_analysis.py`、`services/capture_ratio.py`、`services/rotation.py`。

| 區塊 | 資料與規則 | 標記 |
|---|---|---|
| 輸入 | `st.text_area` 多檔代號（上限 `_MAX_CODES`）＋本金 TWD（用同一本金讓配息放同尺度）；可從「我的組合」帶入。 | FACT |
| 逐檔 worker | `process_one_fund`（L2，無 `st`）；任一步失敗回 `{code, ok: False, error}`，不矇預設值。 | FACT |
| 大表欄位 | 識別／健康分析／配息相關／延伸／基期；含 Sharpe、最大回撤、3Y／5Y 年化、年化配息率、上下檔捕捉、σ rank、基期、4D Grade／Score、吃本金燈號、換標的建議、3-3-3 篩（欄位 SSOT：`BATCH_UNIFIED_COLUMNS`；欄數 `docs/v2/62` 記 70+、⑧ 檔內自述實測 79，本組未逐欄計數，`NOT VERIFIED`）。 | FACT |
| 新鮮度欄 | `nav_freshness_label`：「🟢／🟠／🔴＋落後天數」，無日期回「⬜ 無淨值日期」；門檻取 `MJ_FRESH_DAYS_GREEN／YELLOW`。 | FACT |
| 樣本揭露 | `report.py::_nav_sample_label`：標示用幾筆淨值、跨多少天。 | FACT |
| 捕捉率 | 月底對齊後分大盤上漲月／下跌月複利比；基準依幣別（TWD→TWII、USD→SPX、其餘 None）；月數不足回 None；操盤評分由上下檔差導出。 | FACT |
| 核心／衛星 | 類別關鍵字與 3-3-3 推算；`DEC-2026-10-24-10` 分類未判定不得產生換／留。 | FACT |
| 批次 | `ui/tab_batch_analysis.py`：上傳／貼上代號 → 逐檔 `build_batch_unified_row` → 可續跑 → CSV 下載；失敗列留表內、數值留白不填 0。 | FACT |
| 其他 | 輪動配對（`services/rotation.py`，自標 legacy 行動語意，待 `BL-0428`）、換股顧問、配息明細、相關性、回測。 | FACT（存在）／NOT VERIFIED（細節） |

### 2.2 線 B 與線 C 現況

- **線 B ⑥**（`page_02_health.py`）：`FACT`
  - 輸入：持股一律從組合帶入（`portfolio_funds`），不保留手動輸入代號；診斷條件在單一 `applied_form`（σ／回看窗／只看衛星）。
  - 預設可見：結論兩句（配息／跟同類比，後者走 `_peer_verdicts`→`_grade`）、組合健康總分（灰態，評等定義未定）、警示卡、逐檔體檢表 `HEALTH_TABLE_COLUMNS` 9 欄（代碼、名稱、幣別、近 1 年、Sharpe、最大回撤、配息覆蓋、五桶評等〔恆 ⬜，檔內說明本站「五桶」是總經概念、逐檔無對應〕、資料日期）。
  - 閘門後（預設不勾）：委派 `render_fund_checkup`、互斥、配息矩陣、相關性矩陣、−2σ 超跌警示、配置回測、AI 跨檔評論；檔內 caption「與舊分頁同一份程式碼、同一條資料路徑」。
- **線 B ⑧ 批次**：`_render_batch` 以 `BATCH_UNIFIED_COLUMNS` 逐檔 `build_batch_unified_row(principal_twd=BATCH_PRINCIPAL_TWD)`，檔內自述「照搬全部欄位、不挑子集」「與舊批次分頁同一份」；只做貼上框、不做檔案上傳。`FACT`
- **線 C**：EXP-3 並排最多 3 檔，列為最近淨值日、最近淨值、近 12 個月配息佔淨值比、經理費率（`COMPARE_ROWS`，檔內自述沿用草稿、客戶可逐項推翻）；HLD-1／2／3／8；`services/v2_domain/rule_filter.py` 三態比較（缺值＝無法判定）。`FACT`
- 線 C 仍缺：逐檔健診寬表欄位、批次、新鮮度逐檔天數欄、樣本筆數與跨度揭露。`INFERENCE`（取決於未漏看）

### 2.3 不能直接沿用

- 不照抄 70 欄寬表：`docs/v2/62` B1 列（總管建議，非核准）；欄位集合屬 UI 取捨，`BL-0435`。`FACT`
- 排名／推薦字樣與預設排序：`docs/v2/44` 1.2「禁排名為推薦」——規定**不加冠推薦字樣、不預設排序欄位**，並非禁止排序（含 2026-10-27 最小解凍的具體化）。`FACT`
- 方向性輸出（輪動配對、換股）：同 1.3，只就線 C 介面文案。`FACT`
- 捕捉率基準：`docs/v2/69` G-BM-1 待裁。`FACT`
- NAV 新鮮度：`DEC-2026-11-05-03` 未授權重定義。`FACT`

### 2.4 差異標籤

| 能力 | 線 B | 線 C | 備註 |
|---|---|---|---|
| 逐檔失敗隔離、失敗列數值留白 | 已保留（⑧ 批次沿用同一 `build_batch_unified_row`，`FACT`） | 無法查證（僅理念同向；線 C 有逐檔 error 文案，與線 A 規則是否同源本組未驗） | |
| 單檔 worker（取數＋指標一體） | 已保留（⑧ 批次、⑥ 委派） | 待核准沿用 | |
| 統一欄位 SSOT（`BATCH_UNIFIED_COLUMNS`） | 已保留（⑧ 批次，`FACT`） | 待核准沿用（欄位取捨屬 UI Gate） | |
| 逐檔淨值新鮮度天數欄 | 已保留（⑥ 逐檔表「資料日期」呼叫 `nav_freshness_label`；⑧ 批次含新鮮度欄，`FACT`） | 待核准沿用（牽涉 NAV 10 日） | |
| 樣本筆數／跨度揭露 | 無法查證（⑧ 沿用大表欄位，是否含該欄本組未逐欄驗） | 待核准沿用 | |
| 上下檔捕捉率／操盤評分 | 已保留（欄骨架含捕捉率，⑧ 批次，`FACT`） | 待核准沿用（涉投資語意與基準口徑） | |
| 輪動配對、換股顧問 | 無法查證（⑧ 批次含「換標的建議」欄；輪動配對區塊本組未在線 B 找到） | 無法查證（僅就介面用字；投資語意） | |
| 核心／衛星分類 | 已保留（⑥ 診斷條件有「只看衛星」；⑨ 有核心／衛星彙總，`FACT`） | 待核准沿用（涉投資語意與身份對應） | |
| 批次上傳（約 400 檔）與續跑 | 無法查證（⑧ 只做貼上框、不做上傳；實際行為未驗） | 無法查證 | |

### 2.5 牽涉未決 Gate／BL

`BL-0399`（B1～B6，待客戶裁示，`FACT`）、`BL-0435`、`BL-0428`、`BL-0524`。

### 2.6 是否涉及投資語意

**是——需客戶裁示。**

---

## 3. 基金體檢表（PK）

### 3.1 線 A 的有效資料與判斷邏輯

來源：`ui/helpers/fund/checkup.py::build_checkup_dataframe／_grade／_extract_peer_1y／_period_ret／_compute_fund_health_kpis／_zone_cell`；掛載：`ui/tab_fund_grp_health.py` 與 `ui/tab3_portfolio.py`。

| 欄位／規則 | 內容 | 標記 |
|---|---|---|
| 展示欄 | 近 1M／3M／6M、近 1Y 含息、同類平均（1Y）、超額（pp）、夏普、年化波動、計價幣別、NAV（原幣）、即時匯率、可申購單位數、月配股、每月 100 萬配息（TWD）、本金試算三欄、買點、體檢判定。 | FACT（`_DISPLAY_COLS`） |
| 近 1M／3M／6M | `_period_ret`：先讀 MoneyDJ 官方績效頁值，缺才退本地 `calc_metrics`（列數窗）；同一欄兩種口徑混用。 | FACT |
| 近 1Y 含息 | 只讀 `compute_1y_total_return` SSOT；算不出 → None，不退官方值也不退純淨值（`DEC-2026-10-23-02` 1B）。 | FACT |
| 同類平均 | 取自 MoneyDJ `risk_metrics.peer_compare` 內含「平均」的鍵；檔頭自述約三成基金抓不到 → 標 ⬜。 | FACT（檔頭自述）／NOT VERIFIED（比例） |
| 體檢判定 | 超額＝1Y 含息−同類平均；依檔內常數 `_EXCESS_GOOD／_EXCESS_LAG` 分優等生／汰弱候選／普通生；任一缺 → 「⬜ 同類資料不足／報酬資料不足」。 | FACT |
| 買點 | `tag_price_zone`；`_zone_cell` 把未觸發與無法判定分開，區間σ fallback 時加註（`BL-0440`）。 | FACT |
| 費率 | 只顯示本檔 `mgmt_fee`；原「類別→費率」寫死表已移除（無來源）。 | FACT |
| 4 大健診卡 | 吃本金、月配息、年化配息率、TER；月配息＝本金×年化配息率÷12。 | FACT |

### 3.2 線 B（⑥）與線 C 現況（M1：本節重寫，原「新 UI 無對應」撤回）

| 線 | 現況 | 標記 |
|---|---|---|
| **線 B ⑥** | `_render_delegated_sections` 第一支委派即 `render_fund_checkup(_funds, expanded=True)`（`DELEGATED_ENTRIES` 逐字列出），被 `DELEGATE_GATE_LABEL`「載入逐檔健診與互斥分析（與舊分頁同一份程式碼）」的 Checkbox Gate 擋著，`value=False`，**預設看不到**；⚠️ 檔內自述的設計理由是雙軌並行時兩個分頁委派同一批舊模組，同一 run 內重複畫圖會觸發 `StreamlitDuplicateElementId`，故以閘門避免（本組讀文字，未重現，`NOT VERIFIED`）。 | FACT |
| 線 B ⑥（預設可見） | 「結論句②」`_render_verdict_line` 經 `_peer_verdicts` 呼叫 `ui.helpers.fund.checkup` 的 `_grade`／`_extract_peer_1y`，按 `_grade` 實際回傳的每個判定桶計數（含「同類持平」桶；檔內自述上游 `render_fund_checkup` 的摘要只數三桶、分母對不上，屬線 A 現有缺陷，本組未重現，`NOT VERIFIED`）；逐檔體檢表的「近 1 年」走 `compute_1y_total_return`、「配息覆蓋」走 `check_eating_principal_1y_mk` 的 coverage。⑥ **沒有**預設可見的 1M／3M／6M 短期績效欄。 | FACT |
| 線 B ⑧ | 單檔深度有 1M～5Y 績效分期，但無同類平均與超額。 | FACT |
| **線 C** | 無對應（`docs/v2/62` B3 列「無」；本組另在 `ui_v2` 以 `同類`、`peer` 等字面搜尋未做，故「無」依 62 的結論與本組讀 `COMPARE_ROWS`／`COLUMN_ORDER` 常數，取決於未漏看）。 | FACT（62 引文）／NOT VERIFIED（本組字面搜尋） |

### 3.3 不能直接沿用

- 同類平均資料源：`DEC-2026-10-23-02` 3A 與 `services/fund_screening.py` 檔頭：晨星／同儕不屬正式規格、不新增同儕資料來源、不參與任何判定；體檢表的同類平均取自 MoneyDJ 績效頁，與該裁示的關係本組**不判定**。`FACT`／`NOT VERIFIED`
- 「優等生／汰弱」字樣：只就線 C 介面用字——`docs/v2/44` 禁方向詞清單含「汰弱留強」，目前 B 線 v1 讀作現況。`FACT`
- 1M／3M／6M 口徑：`docs/v2/69` G-RET-1、`BL-0524`。`FACT`
- 可申購單位數與即時匯率：FX 閘門保持關閉（`DEC-2026-11-08-02`）。`FACT`

### 3.4 差異標籤（S3：同類平均、超額、判定三項各自一列）

| 能力 | 線 B | 線 C |
|---|---|---|
| 1M／3M／6M 短期績效 | 已保留（⑧ 單檔有 1M／3M／6M；⑥ 委派區的體檢 PK 閘門後才有，`FACT`） | 待核准沿用（口徑待決） |
| 近 1Y 含息只讀單一 SSOT、不退官方值 | 已保留（⑥ 逐檔表呼叫同一 SSOT，`FACT`） | 待核准沿用 |
| 同類平均（取數覆蓋率約三成缺為檔頭自述） | 已保留（⑥ 閘門後、結論句② 經同一 `_extract_peer_1y`，`FACT`）；覆蓋率 `NOT VERIFIED` | 無法查證（取得率未實測、3A 射程未判） |
| 超額（pp） | 已保留（閘門後的體檢 PK 欄；結論句②間接使用，`FACT`） | 無法查證 |
| 體檢判定（優等生／普通生／汰弱候選／資料不足） | 已保留（⑥ 結論句② 數判定桶，`FACT`） | 無法查證（僅就介面用字：44 目前 B 線 v1 文案不出現方向詞；判定本身屬投資語意，不給答案） |
| 「⚪ 未觸發」與「⬜ 無法判定」分開 | 無法查證（⑥ 閘門後體檢 PK 沿用同碼，預設不顯示；該區是否含買點欄未逐欄驗） | 無法查證（僅理念同向，未見線 C 側對應符號） |
| 本金試算（可申購單位、月配息） | 已保留（⑧ 投資試算；⑥ 持倉每月配息推估，`FACT`） | 待核准沿用（涉 FX 閘門、本金輸入語意） |
| 費率不編造、無同類費率均值 | 無法查證（⑧ 未驗是否顯示費率） | 已保留（`mgmt_fee_rate_pct` 恆 None，`FACT`；理念同向，僅就此一符號） |

### 3.5 牽涉未決 Gate／BL

`BL-0399`（B1～B6 含 B3，`FACT`）、`BL-0524`、`BL-0440`、`BL-0435`。

### 3.6 是否涉及投資語意

**是——需客戶裁示。**

---

## 4. 低基期篩選

### 4.1 線 A 的有效資料與判斷邏輯

來源：`ui/tab_fund_grp_health.py::_render_low_base_screener`、`services/fund_screening.py::screen_funds／compute_base_state`、`services/rotation.py::classify_base`、`services/health/dividend.py::check_eating_principal_1y_mk`。

| 規則 | 內容 | 標記 |
|---|---|---|
| 篩選輸入 | 對「已載入的基金」（重用健診已抓 NAV）：幣別多選、類別多選、「只留不吃本金」、「只留低基期」。 | FACT |
| 基期定位 | `compute_base_state`：σ rank 取自 `compute_fund_position`（配息還原、fail closed）；低基期 ⇔ σ rank ≤ `ROTATION_BUY_SIGMA`、高基期 ⇔ ≥ `ROTATION_SELL_SIGMA`（均在 `shared/signal_thresholds`；`DEC-2026-10-23-02` 寫明該兩值僅為既有相容／研究候選門檻、未校準、不代表客戶認可）；回看窗常數 `LOW_BASE_LOOKBACK_DEFAULT`、可信度常數 `LOW_BASE_MIN_POINTS`。 | FACT |
| 無法判定 | SSOT 回 unavailable（歷史不足／σ≈0／配息資料未備／貨幣市場型／還原失敗）→ `base="unknown"`、`is_low_base=None`、原因轉載到 `note`；`only_low_base=True` 一定濾掉。 | FACT |
| 不吃本金 | 僅保留 `eats_principal is False`；未知與吃本金皆濾掉。 | FACT |
| 排序 | 依 σ rank 由負至正，無法定位階者排最後。 | FACT |
| 檔頭自述 | 「低基期／進場點」為 legacy 行動語意，待 `BL-0428` 重新裁示。 | FACT |
| 註解過期 | `docs/v2/62` 2026-10-23 狀態更新記 `compute_base_state` docstring 仍寫 √len(s)、實碼為 √252（程式註解未改，`BL-0423`）。 | FACT（引文）／NOT VERIFIED（未重驗現況） |

### 4.2 線 B 與線 C 現況

- **線 B**：⑥、⑧ **沒有**篩選器——`screen_funds` 在 `ui/` 之下只有 `ui/tab_fund_grp_health.py` 一個 caller（`git grep`，單組）。⑧ 批次大表的欄骨架含「基期」欄；⑥ 委派區（閘門後）有「−2σ 超跌警示」`_render_oversold_badges`。`FACT`
- **線 C**：EXP-1 使用者自訂「欄位＋比較方向＋數值」條件列（七欄 `FUND_PROFILE_FIELDS`），無預設條件、無「常用條件」；EXP-7 篩選軌跡；三態判定。`FACT`。仍缺「基期」「不吃本金」這類衍生條件欄位（`docs/v2/62` C2 列）。`FACT`

### 4.3 不能直接沿用

- 「進場候選」「低基期」行動語意：`docs/v2/44` 禁方向詞與 G1†（只就線 C 介面用字；目前 B 線 v1 現況）；舊決策矩陣退役（`DEC-2026-10-19-01`）；`DEC-2026-10-23-02` 2C 另規定可買／可賣／加碼參考／超跌／買點／賣點不得再由 HWM evidence 產生，中性概念為接近高點／中段／遠離高點／⬜ 無法判定／不適用。`FACT`
- 排序：`docs/v2/44` 1.2 規定不加冠推薦字樣、不預設排序欄位，**並非禁排序**；依 σ rank 排序是否可用於線 C 屬投資語意與排名語意，本組不判。`FACT`
- 衍生條件進 EXP-1 屬欄位／語意新增，須 Gate。`FACT`（`docs/v2/62` C2 列）

### 4.4 差異標籤

| 能力 | 線 B | 線 C |
|---|---|---|
| 缺資料不得入候選、無法判定者排除並帶原因 | 無法查證（線 B 沒有篩選器；基期欄的 unknown 處理與線 A 同碼，未逐欄驗） | 無法查證（僅理念同向：線 C 三態「缺值＝無法判定」；無衍生條件可對照） |
| 幣別／類別多選濾鏡 | 待核准沿用（⑥⑧ 無） | 待核准沿用（EXP-1 有 `ccy` 字面條件；類別欄位未在 `fund_profile` 七欄中，`FACT`） |
| 「不吃本金」衍生條件 | 待核准沿用 | 待核准沿用（涉投資語意） |
| 「低基期」σ rank 衍生條件（`ROTATION_BUY_SIGMA`／`ROTATION_SELL_SIGMA`） | 無法查證（⑧ 批次有「基期」欄，篩選無） | 待核准沿用（涉投資語意；legacy 待 `BL-0428`）。**本組不建議任何門檻值** |
| 依 σ rank 排序 | 無法查證 | 無法查證（僅就介面用字：44 規定不加冠推薦字樣、不預設排序欄位；排序本身可否採用屬待裁） |
| 篩選母體＝「已載入基金」 | 無法查證 | 無法查證（線 C 母體來自 `fund_profile`／EXP-2，與線 A 母體差異本組未驗） |

### 4.5 牽涉未決 Gate／BL

`BL-0400`（C1 C2 C4，待客戶裁示，`FACT`）、`BL-0428`、`BL-0438`、`BL-0435`、`DEC-2026-10-22-02` G8。

### 4.6 是否涉及投資語意

**是——需客戶裁示。**

---

## 5. 目前帳本

### 5.1 線 A 的有效資料與判斷邏輯

來源：`ui/tab3_t7_ledger.py::render_t7_section`（「📒 目前帳本 + 以息養股現金流」）、`_latest_nav_fx_t7`、`services/satellite.py::satellite_stop_gain`、`services/ledger_service.py`、`repositories/ledger_repository.py`。

| 區塊 | 資料與規則 | 標記 |
|---|---|---|
| 逐檔表 | 保單、代碼、基金名稱、幣別、持有單位、平均買入淨值、含息成本、平均買入匯率、最新 NAV／FX、成本基礎 TWD、市值 TWD、未實現損益 TWD／%、累積已配息率、配息率、預估月配息／月配股、衛星停利。 | FACT |
| 市值與損益 | 市值＝`position.value_twd(nav, fx)`；損益＝市值−成本基礎（`net_investment_twd`）；成本≤0 時報酬率「⬜ 無法計算」。 | FACT |
| 三種缺值分流 | 無持倉（列入「未計入」）／有持倉但抓不到報價（市值整列留白，不計入總市值與總報酬，並說明視為 0 或視為成本皆為編造）／配息率未備（不計入年配息與月現金流，提示「不是不配息」）。 | FACT |
| 組合 KPI | 組合市值、整體未實現損益（含%）、預估年現金配息、月被動現金流、年配股；現金／配股拆分依各檔 `div_cash_pct`；顯示「已計入 N／M 檔」。 | FACT |
| 近似市值 | 無持倉明細時以 `invest_twd` 加總作近似，標「⚠️ 近似」。 | FACT |
| FX 取得 | `_latest_nav_fx_t7`：幣別未知或來源衝突 → 不查匯率（fx=0 走「抓不到」）；即時匯率缺 → 退 `fund.fx_rate` → 再退帳本平均買入匯率（記入 `_t7_fx_ledger_avg` 並 log）。 | FACT |
| 衛星停利 | `satellite_stop_gain`：只對明確衛星判燈，核心不判、未設定顯示「⬜ 未設定」、未填成本誠實無法判；分批／強制兩個門檻為 `SATELLITE_STOP_GAIN_BATCH_PCT`／`SATELLITE_STOP_GAIN_FORCE_PCT`（`shared/signal_thresholds`）。 | FACT |
| 帳本資料落點 | `_Ledgers`、`_T7_State` 等 Sheets 分頁；`docs/v2/62` 2026-10-23 更新：`replace_ledgers_for_policy` 編輯持倉時整段重寫該保單帳本；`calculate_xirr` 與 `GhostPortfolio` production caller 為 0（該稽核結果）。 | FACT（引文）／NOT VERIFIED（未重驗） |
| in-memory | 畫面自述「in-memory，隨頁面重整清空」。 | FACT |

### 5.2 線 B（⑨）與線 C 現況

- **線 B ⑨**（`page_04_portfolio.py`）：「交易帳本」區塊 `_render_ledger` 檔內自述為灰態（`REASON_LEDGER`，指路到舊分頁帳本；檔內並記「資料其實搆得到：`st.session_state["t7_ledgers"]`」但未接）；有核心／衛星彙總（`summarize_core_satellite`，檔內註明不是市值）。實際執行畫面 `NOT VERIFIED`。`FACT`（檔內自述）
- **線 C**：`HLD-5` 單檔展開含單位數、成本、類別（`docs/v2/62` E7 列）；`ui_v2/alo/` 有成本與市值兩基準的類別分布，缺淨值／缺匯率時該類別照實呈現資料未備（`ui_v2/alo/logic.py` 檔內說明）；`services/v2_domain/allocation_evidence.py` 檔頭自述為 BL-0542 G1-3 的 CANDIDATE design，名稱皆非核准詞彙。`FACT`
- 兩線皆缺：組合層市值彙總、未實現損益、年／月現金配息與配股、衛星停利。`INFERENCE`（取決於未漏看）

### 5.3 不能直接沿用

- FX 保底鏈：Q5 FX 閘門保持關閉、`DEC-2026-11-08-02`；任何匯率退路屬未授權。`FACT`
- 預估年配息＝市值×配息率：配息率口徑與 `BL-0524` 相關。`INFERENCE`
- 衛星停利燈：只就線 C 介面用字——44 禁方向詞含「停利」，目前 B 線 v1 讀作現況；停利燈是否保留屬投資語意。`FACT`
- 組合層彙總與現金水位：`BL-0393` (3)(4) Phase 5 Data Gap 待研究，登記非授權。`FACT`
- 「💼 我的資產」草案：`BL-0542`（G-1～G-5 仍待裁示）；`docs/v2/82` 本組未讀全文。`NOT VERIFIED`

### 5.4 差異標籤

| 能力 | 線 B | 線 C |
|---|---|---|
| 缺報價整列留白、不計入總市值、不以 0／成本頂替 | 無法查證（⑨ 帳本灰態，未接） | 無法查證（僅理念同向：ALO 缺值照實呈現；同判定規則與否未驗） |
| 「已計入 N／M 檔」覆蓋揭露 | 無法查證 | 待核准沿用（`DEC-2026-11-06-02` 對健康維度要求揭露分母；帳本同理的適用範圍未判） |
| 組合市值、未實現損益 TWD／% | 待核准沿用 | 待核准沿用（涉報酬口徑、FX） |
| 預估年現金配息、月被動現金流、配股拆分 | 待核准沿用 | 待核准沿用（涉配息率口徑、`div_cash_pct`） |
| 衛星停利燈與其兩個門檻常數 | 待核准沿用 | 無法查證（僅就介面用字；是否保留屬投資語意；本組不建議數字） |
| 近似市值（以 `invest_twd` 代替）並標近似 | 無法查證 | 無法查證（線 C 是否允許「近似」屬待決） |
| 幣別未知／衝突不查匯率 | 無法查證 | 無法查證（僅理念同向；未見線 C 側同規則符號） |
| FX 退路鏈 | 不適用（FX 閘門保持關閉，`DEC-2026-11-08-02`） | 不適用（同左） |
| 帳本事件重寫與 XIRR | 無法查證 | 無法查證（`docs/v2/62` 單組稽核結果，本組未重驗） |

### 5.5 牽涉未決 Gate／BL

`BL-0404`（E4 E7，待客戶裁示，交叉 `BL-0393` (3)(4)）、`BL-0393`、`BL-0542`、`BL-0524`、`DEC-2026-11-08-02`。`FACT`

### 5.6 是否涉及投資語意

**是——需客戶裁示。**

---

## 6. 舊 UI 具備的資料處理特性（S4：標題改中性；以下為本組整理的描述，**非核准、非建議保留**）

1. 缺資料或算不出來時回「資料未備／無法判定」並帶白話原因，而不是填 0 或沿用別的數字。
2. 同一個指標在線 A 讀單一口徑來源，並在畫面說明樣本筆數與跨度。
3. 一檔失敗不拖垮整批，失敗列留在結果裡並標原因。
4. 淨值日期與落後天數攤在表上，讓人分得出「週末沒開盤」和「早就停更」。
5. 年化配息率在線 A 取近 12 個月實際配息合計除以最新淨值，官方值只做對帳。⚠️ `DEC-2026-10-23-02` 1B 的落地範圍寫明為 `services/`、`ui/` **舊站 consumer**，且**不改 `ui_v2/`**；它對 New UI2 契約是否適用**未定**，本項只描述線 A 現況。
6. 含息報酬在線 A 用同一份還原序列算，窗口不足就不給數字。⚠️ 同第 5 項：1B 落地範圍為舊站 consumer、不改 `ui_v2/`，對 New UI2 契約是否適用未定；且「窗口」數字在線 A 內不同函式不一致（`docs/v2/69` G-RET-2 等），本組不判。
7. 同一個數字有第二種算法時，並列顯示一致／不一致／缺值四種狀態。
8. 3-3-3、吃本金這類條件在線 A 只留一個判斷來源，避免同一檔在不同頁面燈號不同。
9. 位置判斷以配息還原序列為準，無法判定時顯示原因而不是中性。
10. 使用者自訂條件篩選時（線 C），缺值既不算符合也不排除，並逐條記錄套用前後檔數。
11. 帳本缺報價時整列留白、不計入總額，並說明「已計入幾檔／共幾檔」。
12. 幣別未知或來源衝突時不查匯率、不假設美元。
13. 不編造沒有來源的同類費率；同類平均取不到時標資料不足。
14. 本金固定同一數字時，各檔配息才能放在同一尺度比較（線 A 批次以 100 萬 TWD 為口徑）。

（以上為本組整理的描述性清單，**未經客戶核准**；是否納入、放哪頁、用什麼名稱，皆屬 UI／Gate 決定。）

---

## 7. 限制與未涵蓋範圍

- 本組只讀程式與文件，**未實跑任何 UI**；可達性為靜態 import／呼叫追蹤（`app.py` 的 `st.tabs` 與 `with tab_*` 分支、`ui/tab_fund_research.py` 的模式分派、`ui/views/page_0*.py` 的檔內符號）。`FACT`（方法）
- 線 B 側只讀了 `page_02_health.py`、`page_03_research.py`、`page_04_portfolio.py` 的符號、常數與 docstring，**未逐行讀函式本體**；「⑧ 未見吃本金／3-3-3／4D／σ／對帳／AI」只代表 `page_03_research.py` 檔內字面搜尋無該詞，**不代表其下游 helper 沒有**。`NOT VERIFIED`
- 線 A 的 `ui/tab2_single_fund.py`、`ui/tab3_t7_ledger.py`、`ui/tab_fund_grp_health.py` 只讀與五項直接相關的區塊；三率穿透、持股來源診斷、AI prompt、投資試算內部公式、相關性／回測、換股顧問等未逐行讀。`NOT VERIFIED`
- 未讀 `docs/v2/44` 全文（只讀第一節與各塊標題、EXP／HLD 代表塊）；`docs/v2/45`、`docs/v2/46` 只讀標題與帳本相關列；`ui_v2` 各頁 `page.py` 與 `ui_v3`（除 `mkt` 路徑名外）未讀。`NOT VERIFIED`
- 「X 沒有」類陳述取決於是否漏看，未經第二組驗證；直接 import 字表只含 9 個模組名（見第 0 節）。
- 未重驗 `docs/v2/62`、`docs/v2/69`、`docs/DECISIONS.md` 內他組結論；BL／DEC 編號只確認正文直接出現者。
- 不涵蓋：市場總覽、資產配置模擬、設定與診斷（⑦）、資料來源取代、AI／OneBrain。
- 本檔未新增任何門檻、公式或判定、未建議移植、未把推論寫成核准。

## 8. 單組作者揭露

- 本檔由單一作者（執行組）產出：初稿一次、**QA 一輪已回修**（M1、S1～S4、S7、NIT）；回修內容經本組對 `origin/main` `772d6e9a` 重驗，**未經第二輪獨立驗證**。依 `CLAUDE.md` §-2 規則 6，全稱性敘述只能當待驗事項。
- 回修處置摘要：M1 成立（已重寫三線定義並重判各列）；S1 成立（改為「無法查證」或明寫「僅就介面用字」，排序處明寫 44 並非禁排序）；S2 成立（無線側符號證據者改「無法查證」，僅理念同向者明寫）；S3 成立（拆成每項一列）；S4 成立（標題改中性，第 5、6 項註明 1B 落地範圍）；S7 成立（`auto_fetch_moneydj`→`fetch_fund_from_moneydj_url_enriched`→`finalize_fund_metrics` 呼叫鏈已寫入第 0 節）；NIT 部分成立（`check_eating_principal_1y_mk` 本身回 `None`、上游 `resolve_dividend_rate_12m` 回 `unavailable／no_dividend`，兩層並寫）；常數名已改。
- 客戶選定方向中，僅 Q5（`DEC-2026-11-08-02`）與 NAV 10 日（`DEC-2026-11-05-03`）找到 repo 內文字佐證；Q3／Q4／身份對應原話未查證。
- 未連網、未改 repo、未 commit／push，未使用 checkout／reset／restore／stash；僅寫入 scratchpad。
