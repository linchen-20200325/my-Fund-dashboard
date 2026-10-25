# 62｜舊 UI → B 版功能 Gap Matrix（2026-10-22 盤點與登記）

- **建立日**：2026-10-22。**量測 SHA**：`d2cd3bb`（＝ `origin/main`，PR #1019 合併後；四組盤點與本檔皆以此 SHA 為準）。
- **性質**：本檔是**盤點與登記**，**不是規格、不是核准、不解凍 `docs/v2/44_fund_ui_ssot.md`**。各表「建議」欄一律是總管建議，**不是客戶核准**；標「需客戶裁示」者在客戶裁示前不得動工。本檔不凌駕 44，不改任何畫面規則；與 `docs/DECISIONS.md` `DEC-2026-10-22-02` G8（暫不核准任何 UI 改版）併讀——本檔是 G8 核准前的**輸入**，不解除 G8。
- **決策登記**：`docs/DECISIONS.md` `DEC-2026-10-22-04`（客戶確認 B 版設計原則：舊 UI 為功能與已驗證投資邏輯的參考、舊畫面不直接移植、B 版 UI/UX 重新設計、舊版重要功能不得無故消失）。**待辦登記**：`docs/BACKLOG.md` BL-0397～BL-0414（登記不構成動工授權、也不構成 UI 改版核准）。
- **誰寫、誰驗過**：四組盤點（舊 UI A 組：① 市場總覽／單檔基金／sidebar／`app.py` 分頁結構；舊 UI B 組：③ 標的探索／多檔比較／② 持倉體檢；舊 UI C 組：④ 資產配置／持倉＋⑤ 設定與診斷；B 版組：`ui_v2/` 五頁）**各自單組讀碼**；總管依四份盤點彙整為本檔 §1～§3 的判斷（`CLAUDE.md` §-2 規則 6：總管單方產出）；本檔由文件組照總管規格落盤，**落盤後另派獨立稽核**。**四組皆未實跑任何 UI**（未起 Streamlit、無 secrets、未看畫面）；「可達／不可達」皆為**靜態 import 追蹤**（從 `app.py` 的 `st.tabs` 區塊往下追 import／呼叫，未以 AST 驗證動態 import）。凡「只有／沒有／全部／0 caller」類全稱句皆為**單組 grep**，未經第二組驗證。
- **客戶指示的出處**：客戶 2026-10-22 指示（查一檔只要直接輸入代碼、明確需要多檔比較、搜尋偏好簡單、投資語意保留、舊 T7 畫面不搬）經總管派工單轉達；**repo 內無逐字存檔**；文件組未見客戶對話本身。
- **體例**：舊條文不刪、狀態更新加「狀態更新，不是漏刪」；會漂移的數字附量測日與 SHA；不寫任何 secret 值；程式位置寫「檔案＋符號」，不寫行號（行號在重構後失效）。

- **2026-10-23 狀態更新（不是漏刪；量測 SHA `bde2468`；出處 `docs/v2/64_v2_ssot_convergence.md`、`DEC-2026-10-23-01`；唯讀稽核結論，單組實測＋總管抽驗，未經第二組逐條驗證）**：
  - **B2**：`services/fund_batch*` 不存在（Phase 1.4 已刪）；批次續跑判定在 `ui/tab_batch_analysis.py`，L1 只有 `repositories/batch_checkpoint.py`。
  - **`_Ledgers` 不是純 append-only**：`repositories/ledger_repository.py::replace_ledgers_for_policy` 在編輯持倉時整段重寫該保單的帳本。E1 列「`_Ledgers` append」只描述新投入那一條路徑。
  - **XIRR 與 `GhostPortfolio`**：XIRR 實際在 `services/ledger_service.py::calculate_xirr`；兩者 production caller 為 0（本檔 §4 末段原寫「未全 repo 驗證」，此為 2026-10-23 稽核補驗結果）。
  - **基期定義的舊說明已過期**：`ui/helpers/fund_grp_health/columns.py` 基期欄 help 文字「與篩選器不是同一套定義」已過期（2026-08-07 已統一）；`services/fund_screening.py::compute_base_state` docstring 仍寫 √len(s)，實碼為 √252。兩處屬程式註解，本批不改（→ BL-0423）。

- **2026-10-25 狀態更新（不是漏刪；量測 SHA `7d41705f`；出處 `DEC-2026-10-25-01`）**：新增 **§6 New UI Capability Matrix 與驗收條件**（⚙️ 設定／🔍 找基金／💼 我的持股／五頁 Refresh／Retry；局部 ID `CAP-*` 不是 BL ID）。性質同本檔：規劃與收斂，**不構成 production 動工授權**、不解除 G8、不解凍 44；版面類變更仍須 UI 草稿先行。§1～§5 一字未改。

---

## §0 三層 UI 的事實（量測 SHA `d2cd3bb`，2026-10-22）

- **舊 UI** ＝ `app.py` 五個現行分頁（① `ui/views/page_01_macro.py`、② `ui/tab_fund_grp_health.py`、③ `ui/tab_fund_research.py`（內含單檔深掘 `ui/tab2_single_fund.py` 與批次 `ui/tab_batch_analysis.py`）、④ `ui/tab3_portfolio.py`（含 T7 `ui/tab3_t7_ledger.py`、保單管理）、⑤ `ui/tab_settings_diag.py`（含 `tab_manage`／`tab5_data_guard`／`tab6_manual`））＋ `ui/sidebar.py`。
- 同一個 `app.py` 另掛四格「[新]」雙軌預覽 `ui/views/page_02/03/04/05_*.py`（客戶 2026-09-07 雙軌裁示）——這是**第三層**，**不是** B 版。
- **B 版** ＝ `ui_v2/` 五頁（`app_preview.py` → mkt／hld／exp／alo／set），只 import `services.v2_tables.*`（單組 grep）。
- 舊 `ui/tab1_macro.py::render_macro_tab` 與其四個子模組（longterm／radar／inflection／ai）主線不可達（暫留），只有 midcycle 與 `render_indicator_map` 間接可達（單組 grep）。
- `app.py` 字面現況為 **9 格** `st.tabs`（5 現行＋4「[新]」預覽）；派工單所稱「①市場總覽、②單檔基金」是七分頁時期的編號，現行 ② 是持倉體檢、單檔基金在 ③ 內。

---

## §1 Gap Matrix

欄位：舊功能｜舊邏輯／用途｜資料來源｜B 版目前狀態｜Gap｜建議｜需客戶裁示。

Gap 類型標籤：`[舊有B無]` `[縮水]` `[找不到入口]` `[過時/重複]` `[投資語意]` `[新資料來源]` `[L3]`；另有 `[兩版皆無]`（登記為新需求候選，不是舊功能回填）、`[方向衝突]`、`[未盤]`。

### A 查一檔

| # | 舊功能 | 舊邏輯／用途 | 資料來源 | B 版目前狀態 | Gap | 建議 | 需客戶裁示 |
|---|---|---|---|---|---|---|---|
| A1 | 代碼直接查（③ 模式 A `mj_url_input`＋「🚀 分析」；可貼 MoneyDJ URL） | `services.moneydj_fetcher.auto_fetch_moneydj` → `services.fund_service.fetch_fund_from_moneydj_url_enriched` → L1 `repositories/fund/fund_orchestration.fetch_fund_from_moneydj_url`（純代碼依序試境內／境外 page_type；多源 fallback） | MoneyDJ 主＋TDCC／FundClear／Cnyes 備援 | **無單檔查詢框**。唯一路徑 EXP-1「fund_code 等於 ACTI71」→ 存檔 → 重跑；且**只限選股池內代碼** | [舊有B無] | 保留取數鏈邏輯；B 版需一個「輸入代碼即查」入口（客戶明示只要簡單輸入），可查池外代碼 | 是（UI 設計＋池外查詢範圍） |
| A2 | 找代號（關鍵字 → TDCC/FundClear 搜尋 → 下拉選） | L1 `repositories.fund.tdcc_search_fund`；結果只顯示代碼、不自動帶入 | TDCC OpenAPI／FundClear | 無名稱搜尋（EXP-1 只有 `fund_name 等於 完整名稱`，無「包含」） | [舊有B無] | 保留 `tdcc_search_fund`；改造：結果應能直接帶入查詢，不要求手抄 | 是（UI） |
| A3 | 單檔深掘內容（基本資料、三合一趨勢圖 MA20/60＋布林＋配息標記、vs 大盤疊圖、σ 買賣點、4D 健診、進階指標 Sortino/Calmar/Alpha、換標的建議、3-3-3、風險表＋Sharpe 對帳 chip、配息＋配息率／1Y 報酬對帳 chip、前十大持股、個股新聞、三率穿透、投資試算、AI 解盤） | `services.fund_service.calc_metrics／finalize_fund_metrics`（注入三個 `*_reconcile`）、`services.reconcile.*`、`services.precision_service.calc_hwm_sigma_levels`、`services.health.*`、`services.fund_screening.check_333_fund`、`services.benchmark_compare`、`services.capture_ratio`、`services.fund_total_return` | MoneyDJ wb01/wb05/wb07＋NAV、Yahoo 基準、yfinance 財報、Google News、Gemini | 只有 EXP-6 六欄基本資料（名稱／代碼／幣別／成立日／配息方式／費率恆 ⬜）；無績效／風險／配息序列／持股／對帳 | [縮水]（最大單點縮水） | 保留 L2 邏輯（已驗證、含雙演算法對帳）；B 版需設計「單檔頁」要納入哪些子區塊。**買賣點／換標的建議／AI 解盤屬方向性輸出**，受 `44` G1†、修正案 #8、`DEC-2026-10-19-01`（舊決策矩陣退役）約束 | 是（區塊取捨＝UI；方向性輸出＝投資語意） |
| A4 | 查過的基金紀錄 `services.fund_history.record_fund` | 寫 `cache/fund_history.json` | 本機 | 無 | [過時/重複] | 讀取端 `get_history_df` 在 `ui/` 0 caller（單組 grep），淘汰候選 | 否（登記即可） |

### B 多檔比較

| # | 舊功能 | 舊邏輯／用途 | 資料來源 | B 版目前狀態 | Gap | 建議 | 需客戶裁示 |
|---|---|---|---|---|---|---|---|
| B1 | ② 持倉體檢：text_area 多檔代號＋本金 → 健診寬表（識別／health／div／extra／base 五段，70+ 欄，含 Sharpe 1Y、Max DD、3Y/5Y 年化、年化配息率、上/下檔捕捉、σ rank、基期、策略燈號…） | `services.fund_row.process_one_fund`（4 並行）；`services/health/report.build_health_analysis_row／build_dividend_summary_row`；`services/fund_grp_health/unified.build_merged_extra_columns`；`ui/helpers/fund_grp_health/unified.py::BATCH_UNIFIED_COLUMNS` | 同 A1 取數鏈 | EXP-3 並排對照**最多 3 檔、只有 4 列**（最近淨值日、最近淨值、近 12 個月配息比、經理費率恆 ⬜） | [縮水] | 保留 `process_one_fund` 與欄位 SSOT；B 版比較表需重新設計欄位集合（客戶明確要多檔比較），不照抄 70 欄 | 是（欄位取捨） |
| B2 | ③ 批次掃描：貼多代碼／上傳 CSV → 序列抓取＋磁碟 checkpoint＋續跑／重試＋CSV 下載 | `ui/tab_batch_analysis._parse_codes`；L1 `repositories/batch_checkpoint`；`build_batch_unified_row`（2026-10-23 補註，狀態更新，不是漏刪：`services/fund_batch*` 不存在，續跑判定在 `ui/tab_batch_analysis.py`，見檔頭 2026-10-23 狀態更新） | 同上；`data_cache/batch/` | 無批次輸入（EXP-1 多列 AND 條件） | [舊有B無] | 保留 checkpoint／續跑邏輯；入口形式待設計 | 是（UI） |
| B3 | 🩺 基金體檢表 PK（近1M/3M/6M/1Y 含息、同類平均、超額 pp、夏普、年化波動、可申購單位、每月配息、體檢判定） | `ui/helpers/fund/checkup.build_checkup_dataframe`；peer 來自 MoneyDJ `risk_metrics.peer_compare` | MoneyDJ 績效評比頁（約三成抓不到） | 無 | [舊有B無] | 1M/3M/6M 短期績效與同類比較是 B 版完全沒有的維度；納入候選 | 是 |
| B4 | 進階區：真實收益 vs 配息率矩陣、相關性／持股重疊矩陣、−2σ 超跌、輪動配對、Bollinger 詳圖、AI 跨檔評論、互補配對探索、換標決策 | `services.portfolio_service.calc_holdings_overlap／calc_correlation_matrix`、`services.rotation.suggest_rotation_pairs`、`services.switch_strategy.*`、`services.homogeneity` | 大表 df | 無 | [舊有B無]；輪動配對／換標決策／互補配對屬 [投資語意] | 相關性／重疊度為描述性可保留；配對建議類受方向性輸出限制 | 是（方向性部分） |
| B5 | 期間：舊版全固定（1Y／252 lookback；本金固定 100 萬或可改） | — | — | B 版亦無期間選擇（hld 區間只管持倉） | [兩版皆無] | 客戶問「比較哪些期間」——登記為待設計需求，不是舊功能回填 | 是 |
| B6 | 多檔疊圖 | 舊版 0 處（只有單檔 Bollinger；單組 grep） | — | 無 | [兩版皆無] | 同上，待設計 | 是 |

### C 找標的／基金池

| # | 舊功能 | 舊邏輯／用途 | 資料來源 | B 版目前狀態 | Gap | 建議 | 需客戶裁示 |
|---|---|---|---|---|---|---|---|
| C1 | 選股池編輯（⑤ 管理室：加入／更新／移除／型態覆寫／存晨星代碼；status WATCHING→TRIGGERED→HOLDING→CLOSED） | L1 `repositories/pool_repository`（EX-CRUD-1） | 獨立一本 Sheet `POOL_SHEET_ID`→`_fund_pool`（無 SA 時本機 JSON） | exp 只讀 `code` 欄當母體；無加入／移除／狀態；本機 JSON 池拒當母體 | [縮水]＋[找不到入口] | 保留 pool_repository；B 版需「加入／移出池」最小入口（客戶偏好簡單） | 是（UI；是否允許 B 版寫池＝寫入邊界，交叉 BL-0349 READ/WRITE boundary） |
| C2 | 低基期篩選器（幣別、類別、只留不吃本金、只留低基期） | `services.fund_screening.screen_funds` → `compute_base_state`（HWM σ）、`check_eating_principal_1y_mk` | 已抓 NAV | EXP-1 七欄「等於／大於…」字面條件；無「不吃本金」「低基期」這類衍生條件 | [縮水]（語意不同） | 兩套篩選語意不同：舊版是投資語意篩，B 版是欄位字面篩。要不要在 B 版加衍生指標篩選屬投資語意 | 是 |
| C3 | 候選標的產生：互補配對（賣高基期→買別類別低基期）、換標決策紅燈替換、換股顧問（池 × 持倉） | `services.rotation`、`services.switch_strategy.replacement_candidate`、`services.switch_advisor.advise_switches` | 池＋持倉 | 無 | [舊有B無][投資語意] | 三項皆為方向性建議；依 `44` G1†／修正案 #8／BL-0314 Phase 5～8 路線，不得提前進 B 版 | 是 |
| C4 | NAV 歷史資料維護（一鍵補全 `backfill_to_gs`、對帳單 CSV 匯入、本地 CSV 多檔匯入、增量更新、下載、清除、累積狀態） | `services.nav_history_store`、`services.nav_history_gs` | 本機 `cache/nav_history/` ＋ 雲端 `NAV_SHEET_ID`→`nav_history` | SET-5 只接「市場指標」與「淨值」（淨值只寫 fetch_log、不落地）；配息／其他「尚未接上」 | [縮水] | 保留兩個 service；B 版需「補資料」最小入口；淨值落地與否交叉 BL-0363 | 是 |
| C5 | 新 ⑧ `ui/views/page_03_research.py` 用 `services.fund_search.search_funds`（thin L2） | — | — | B 版未用 | 可復用 | 登記為可復用入口 | 否 |
| C6 | 新 ⑧（[新] 標的探索）與舊 ③ 的功能差異 | — | — | 本輪未盤 | [未盤] | 登記待查 | 否 |

### D Google／Sheet

| # | 舊功能 | 舊邏輯／用途 | 資料來源 | B 版目前狀態 | Gap | 建議 | 需客戶裁示 |
|---|---|---|---|---|---|---|---|
| D1 | Google OAuth 登入／登出（sidebar）＋ in-app OAuth 設定引導（④） | `infra.oauth.build_authorize_url`、`ui/helpers/io/oauth_state`（secrets `[google_oauth]` 或 session cfg） | Google OAuth | 無任何登入元件；只走服務帳戶 secret | [舊有B無] | 已登記 BL-0349（移至 Phase 3 結案後）、BL-0381；本輪不重登，但要在 UX gap 列交叉 | 是（已登記待裁） |
| D2 | Sheet 選擇／切換：sidebar `inp_sheet_id`（貼 ID/URL）、④「從 Drive 挑帳本」、「✨ 新增帳本」自動建 Sheet | `repositories/policy/v2.list_user_sheets／list_user_folders／create_dashboard_sheet`；`session_state["policy_sheet_id"]` 優先於 secret | Google Drive／Sheets | 無；`POLICY_SHEET_ID` 綁死 secret | [舊有B無] | 已登記 BL-0392（待客戶裁示）；交叉 | 是（已登記） |
| D3 | 目前連到哪份：sidebar「📂 **Sheet 標題**」、④ caption「📂 帳本：title｜本地持倉 N 檔｜上次讀回」 | `repositories/policy/v2.get_sheet_title` | Sheets API | 只有 SET-3 顯示**設定試算表**標題；`POLICY_SHEET_ID`／`POOL_SHEET_ID` 的試算表名稱不顯示 | [縮水] | B 版應顯示三本試算表各自連到哪份（名稱）；這是客戶「不知道叫出自己的 Sheet」的直接成因之一 | 是（UI） |
| D4 | 持倉維護入口：④ 📋 保單管理 expander、v2 編輯器（唯讀）、說明書 Sheet 結構章 | — | — | 「前往 Sheets 維護持倉」按鈕（ALO-4 常駐、HLD-0 持倉空時）**無 on_click、無連結**；G5(b) 裁示先移除（BL-0389 blocked） | [找不到入口] | B 版唯讀是裁示（客戶 2026-09-21、2026-10-13），但「去哪裡維護」的指路必須存在：至少顯示 Sheet 名稱＋可開啟連結。目的地不得自行新增（G5(b)） | 是（指路形式） |
| D5 | SA 與 OAuth 雙模式（`_t3_sheet_client` SA 失敗回退 OAuth） | `oauth_state` | — | 只 SA | [舊有B無] | 併入 D1 | 是 |
| D6 | 📦 立即全部寫入／📥 立即全部讀回／JSON 備份還原 | `ui/helpers/cloud_io.dump_all_to_sheet／load_all_from_sheet`（v2 整 tab clear+覆寫） | 保單分頁、`_T7_State`、`_持倉總覽` | 無（B 唯讀） | [過時/重複] | **淘汰**：客戶 Q4(d) 已同意以 Sheets 為權威（出處：`docs/v2/49_data_integration_plan.md` 6.1 Q4 (d)，客戶 2026-09-26 同意）、不再用「📦 立即全部寫入」；`ws.clear` 覆寫是 49 Q4 記載的資料遺失風險 | 否（已裁示） |
| D7 | v1→v2 遷移工具（🔍 偵測格式／🚀 升級到 v2） | `scripts/migrate_v149_schema.py` | 保單分頁、`_T7_State` | 無 | [過時/重複] | **淘汰候選**：不適用 B 版格式（不寫 `_持倉補充`）、空白幣別猜 `USD` 違 §1；子法 1 F6 凍結腳本故不刪，只不接入 B | 否 |
| D8 | ✨ 自動建立 Sheet（整本） | `create_dashboard_sheet` | Drive | 無 | [舊有B無] | 併入 D2／BL-0392 | 是 |

### E 投資／持倉操作

| # | 舊功能 | 舊邏輯／用途 | 資料來源 | B 版目前狀態 | Gap | 建議 | 需客戶裁示 |
|---|---|---|---|---|---|---|---|
| E1 | A 新投入（既有基金：TWD 金額或目標單位；新增基金：代碼＋金額；暫存方案／直接套用） | `services.ledger_service.Ledger.subscribe(amount_twd, fx, nav, date)`：`new_units=(amount/fx)/nav`，cost_unit／fx_avg 單位加權；落帳後 `_sync_invest_twd_from_ledgers` 寫回 `invest_twd=net_investment_twd`；`_Ledgers` append `action="buy"` | 即時 NAV/FX（含寫死保底匯率 `_FX_FALLBACK`） | 無任何持倉操作；B 唯讀（`READONLY_TABLES`、`BUTTON_KINDS` 封閉） | [舊有B無][投資語意] | **投資語意保留**：新投入＝外部本金增加（`txn_type="subscribe"`，XIRR 負現金流）。B 版要不要有操作入口、還是持倉一律在 Sheets 手動維護＋B 只讀——這是產品方向 | 是 |
| E2 | B 投入再平衡（總額依缺口比例分配：`gap_i=max(v_post×w_i−v_i,0)`，單位檔先扣固定金額；任一檔市值未知 fail-closed） | `ui/tab3_t7_ledger.py` 內算（非 services） | 同上 | ALO-3 情境試算只畫面、存檔停用（Phase 4）；ALO 無再平衡動作（G1†） | [縮水] | 分配公式可下沉 services 保留；是否進 B 版＝產品方向 | 是 |
| E3 | C 轉換再平衡 Switch A→B（同保單；賣出 %＝部分／100%＝全部；買方 ≤5 權重；同幣別繼承 fx_avg、跨幣別 cross_rate；TWD 成本守恆反推 B 成本） | `services.ledger_service.Switch.switch_same_currency／switch_cross_currency／_do_switch`；`txn_type` `switch_out`／`switch_in`（amount_twd＝移轉的歷史成本，**不是**市值）；`calculate_xirr` 忽略 switch_*；組合總 `invest_twd` 不變 | 同上 | 無 | [舊有B無][投資語意] | **投資語意保留**：A→B＝既有資產內部移動，不得算新投入（程式以 `txn_type` 區分，無 `new_capital` 旗標）。邏輯住在 L2 可復用；舊 T7 畫面不搬 | 是（要不要進 B；進的話 UI 另設計） |
| E4 | 贖回（to cash） | 舊版**沒有**（`Ledger` 無 redeem；`_TXN_TYPES` 無；`sell_to_cash` 只是顧問標籤；單組 grep） | — | 無 | [兩版皆無] | 登記為新需求候選，非回填 | 是 |
| E5 | 編輯持倉（對帳單抄入→覆蓋 T7）、⚡ 自動估算、孤立 ledger 清理、重置帳本 | `compute_units`、`avg_nav_with_div_from_cumul_div_twd`；`replace_ledgers_for_policy`、`upsert_fund_in_policy` | `_Ledgers`、保單分頁 | 無；由 Sheets 手填取代（Q4） | [過時/重複] | **淘汰 UI**；`compute_units` 公式保留（B 版 L2 已用 units×avg_nav） | 否 |
| E6 | 方案比較（≤5 個暫存方案 vs 主帳本：市值／成本／損益／月配息） | `_t7_summary_from_ledgers` | session | 無 | [舊有B無] | 若 B 版有 E1～E3 才有意義；併入 E1 裁示 | 是 |
| E7 | 目前帳本 19 欄表＋5 metric（組合市值、未實現損益、年現金配息、月被動現金流、年配股）＋衛星停利 | `FundPosition.value_twd／net_investment_twd／roi_*`、`services.satellite.satellite_stop_gain` | session＋即時 NAV/FX | HLD-5 單檔展開有單位數／成本／類別；無組合層市值／損益／現金流 | [縮水] | 組合層彙總與現金流是客戶常用數字；交叉 BL-0393 (3)(4)「持倉頂層概況／現金水位」Data Gap | 是 |
| E8 | 換扣款標的決策、換股顧問、AI 組合摘要／策略3 深度建議 | `services.policy_fee_optimizer`、`services.switch_advisor`、`services.ai_service.analyze_portfolio_mk_advisor` | — | 無 | [舊有B無][投資語意] | 方向性輸出，依 BL-0314 路線；本輪只登記 | 是 |
| E9 | T7 三分頁 `_T7_State`／`_Ledgers`／`_持倉總覽`（帳本快照、交易流水、可讀總覽） | `repositories/snapshot_repository`、`repositories/ledger_repository` | 保單試算表內 `_` 分頁 | B 版不讀（只讀保單分頁＋`_持倉補充`＋`_保單資料`） | [新資料來源]／[過時] | 交易流水（`_Ledgers`）是唯一的歷史操作紀錄；B 版若要有 E1～E3 需決定紀錄去向。三分頁去留屬資料保存裁示 | 是 |
| E10 | 寫死保底匯率 `_FX_FALLBACK`（USD 32…）、幣別未知 fx=0 | `ui/tab3_t7_ledger.py` | — | 無 | [過時] | 違 §1，**不得**帶進 B 版；登記淘汰 | 否 |

### F 其他舊 UI 功能

| # | 舊功能 | 舊邏輯／用途 | 資料來源 | B 版目前狀態 | Gap | 建議 | 需客戶裁示 |
|---|---|---|---|---|---|---|---|
| F1 | ① 市場總覽：六張總覽卡、五桶證據表＋綜合分（含對帳 chip）、建議資產水位、長期座標 7 格、中期循環 Z-Score 矩陣、短線雷達 10 燈＋流動性 4 因子、拐點警報、AI 景氣總結、即時訊號決策矩陣（舊檔） | `services.macro.*`（fetch_all_indicators／calc_macro_phase／detect_turning_points／composite_score／reconcile_composite_score）、`services.risk_radar`、`services.liquidity_engine`、`services.us_liquidity_engine`、`services.allocation_ladder` | FRED（41 個 `FRED_*` 常數，`shared/fred_series.py`，`d2cd3bb` 實數；`CLAUDE.md` §2.1 舊記 34，未同步）、Yahoo、FinMind、RSS、Gemini | MKT 七鍵三卡（VIX、HY、T10Y2Y、Fed Funds；領先／同時／匯率 pending） | [縮水]（指標數 34→4 有值） | 舊總經引擎邏輯完整、已驗證；B 版 mkt 範圍是 49/44 刻意收斂的第一階段。要擴哪些指標進 B 版＝資料來源＋投資語意；決策矩陣已裁示退役（`DEC-2026-10-19-01`） | 是 |
| F2 | ⑤ 診斷：前 4 Tab 資料完整性檢查表、第一手來源總覽、資料註冊表、API 延遲、NAS Proxy 測試、FX 四來源診斷、API 金鑰狀態、基金資料診斷、FRED 發布日、異常清單 | `ui/helpers/io/registry_classify`、`repositories.fund.diagnose_fx_sources` 等 | session registry、各 API | SET-1～SET-8（fetch_log 新鮮度、來源健康、18 參數、重新取數）；BL-0391 已登記「對一般使用者過度複雜」 | [方向衝突] | 舊版診斷更多、B 版已被判過度複雜——兩個方向相反；診斷深度屬產品方向 | 是 |
| F3 | 說明書 10 章（Macro Score、天氣、4D 評等、吃本金、再平衡公式、核心/衛星、汰弱留強、Sheet 結構、指標地圖、教學文獻）＋資料來源地圖 | `ui/tab6_manual.py`（純文字／表） | 靜態 | **無任何說明／help**（只有按鈕 disabled_reason） | [舊有B無] | 說明內容多半仍對（公式、Sheet 結構）；B 版需最小 help（至少 Sheet 結構與各頁職責） | 是（形式） |
| F4 | 🧹 全域刷新（TTL＋st_cache＋落地檔＋session）、🗑️ 清空抓取快取 | `infra.cache.global_refresh_all`、`fund_fetcher.clear_all_caches` | — | 無；只有 SET-5 分層重取 | [舊有B無] | 低優先；若 B 版取數失敗需「重試」入口再議 | 是 |
| F5 | 除息行事曆（月曆 HTML）、LINE 換股通報（預覽／測試發送；NAS 排程） | `services.dividend_calendar`、`services.switch_notify`、`infra.line_push`、`scripts/weekly_switch_notify.py` | 池＋持倉＋MoneyDJ | 無 | [舊有B無] | 通報屬方向性（換股）；行事曆為描述性。皆低優先，登記 | 是 |
| F6 | `ui/views/page_02/03/04/05_*.py` 四格「[新]」預覽（第三層） | 2026-09-07 雙軌裁示 | — | 與 B 版無關 | [過時/重複] | 去留屬 BL-0292 舊 UI 退役閘門；本輪不動、不提議刪 | 是 |
| F7 | sidebar：Proxy 連線測試（6 endpoint）、強制同步 GitHub（`subprocess git ls-remote`）、版本徽章 | UI 內 `requests`／`subprocess`（登記 `P-UISUBPROC-1`） | — | 無 | [過時] | 維運用途；不進 B 版；淘汰候選 | 否 |

---

## §2 各列「建議」總結（總管建議，不是客戶核准）

- **保留邏輯、重設計 UI**（不搬畫面）：A1 A2 A3 B1 B2 B3 C1 C4 D3 D4 E1 E3 E7 F1 F3
- **改造**（舊邏輯要調整才能進 B）：A2（結果自動帶入）、C2（篩選語意）、E2（分配公式下沉 L2）
- **合併**：A2→A1、D5→D1、D8→D2、E6→E1
- **淘汰／不進 B 版**：A4 D6 D7 E5 E10 F7；F6 依 BL-0292
- **方向性輸出，依 Phase 5～8 路線、本輪只登記**：A3 的買賣點／換標建議／AI、B4 配對類、C3、E8、F5 通報
- **兩版皆無、登記為新需求候選**：B5 期間、B6 疊圖、E4 贖回

---

## §3 對應 BACKLOG 列（`docs/BACKLOG.md`「2026-10-22 舊 UI 功能盤點登記」小節）

| BL | 矩陣列 | 狀態 | 一句話 |
|---|---|---|---|
| BL-0397 | A1 A2 | 待客戶裁示 | B 版無「輸入代碼即查一檔」入口、無名稱搜尋 |
| BL-0398 | A3 | 待客戶裁示 | B 版單檔內容只有 EXP-6 六欄；方向性部分依 BL-0314 |
| BL-0399 | B1～B6 | 待客戶裁示 | 多檔比較縮水；兩版皆無期間選擇與疊圖 |
| BL-0400 | C1 C2 C4 | 待客戶裁示 | 選股池加入／移除、篩選語意、補資料入口 |
| BL-0401 | B4 C3 E8 F5 | deferred | 候選標的／方向性建議，依 Phase 5～8 路線 |
| BL-0402 | D1～D5 D8 | 待客戶裁示 | 客戶實際感受：不知道怎麼登入 Google、叫出 Sheet、去哪維護 |
| BL-0403 | E1 E2 E3 E6 | 待客戶裁示 | 持倉操作（新投入／再平衡／Switch）；投資語意保留 |
| BL-0404 | E4 E7 | 待客戶裁示 | 組合層彙總缺口；贖回兩版皆無 |
| BL-0405 | D6 D7 E9 | 待客戶裁示 | T7 三分頁去留；舊「📦 立即全部寫入」已淘汰；遷移腳本不接入 B |
| BL-0406 | F1 | 待客戶裁示 | 市場總覽縮水 34→4 |
| BL-0407 | F3 | 待客戶裁示 | B 版無說明／help |
| BL-0408 | F2 | 待客戶裁示 | 設定與診斷方向衝突 |
| BL-0409 | A4 D6 D7 E5 E10 F4 F6 F7 | deferred | 淘汰候選清單（不構成刪除授權；D6 `cloud_io.dump_all_to_sheet`、E5 編輯持倉 UI 亦在此列） |
| BL-0410 | C5 C6 | 待確認 | 本輪未盤：新 ⑧ 與舊 ③ 差異、`ui/views` 四頁 |
| BL-0411～BL-0414 | （G1 重驗實機證據，非本矩陣列） | open／待客戶裁示 | 略過原因不上畫面、SET-4 參數排序、幣別中文→ISO、級別 vs 類別 |

---

## §4 可復用 L2 函式總表（從四組盤點 §4 抄錄，按 services 模組分組；函式名實讀、呼叫關係單組 grep）

> 本表只列**函式名與其舊 UI 呼叫處**，不評價、不保證每一個都適合 B 版；方向性輸出類（換標／輪動／顧問／AI）列出是為了日後依 BL-0314 路線復用時找得到，**不是**提前進 B 版的授權。

### 4.1 單檔取數與指標（A 組／B 組）

- `services/moneydj_fetcher.py`：`auto_fetch_moneydj`、`build_moneydj_url`
- `services/fund_service.py`：`calc_metrics`（SSOT writer：sharpe/sortino/calmar/std_1y..5y/max_drawdown/risk_metric_meta/ret_1y/3y/5y/annual_div_rate/div_freq_n/buy1-3/sell1-3）、`finalize_fund_metrics`（注入 `sharpe_reconcile`／`ret_1y_reconcile`／`div_yield_reconcile`）、`fetch_fund_by_key_enriched`、`fetch_fund_from_moneydj_url_enriched`、`calculate_fund_total_return`、`assess_series_coverage`、`calc_dividend_estimate`、`get_latest_fx`、`get_latest_nav`、`get_latest_vix`、`get_fx_rate_by_date`、`set_risk_free_rate`
- `services/fund_row.py`：`process_one_fund`（單檔健診 worker，② 並行／③ 序列共用）、`nav_freshness_label`
- `services/reconcile.py`：`reconcile_pair`、`reconcile_fund_annual_return`、`reconcile_sharpe`、`reconcile_dividend_yield`（`reconcile_us10y_yield` 屬總經）
- `services/precision_service.py`：`calc_hwm_sigma_levels`、`PrecisionStrategyEngine`／`PrecisionShieldEngine`（三率：`fetch_stock_three_ratios`／`evaluate_fund_three_ratios`）、`three_ratio_row_html`
- `services/capture_ratio.py`：`benchmark_for_currency`、`compute_capture`；`services/benchmark_compare.py`：`excess_return`、`rebased_pair`
- `services/fund_total_return.py`：`compute_1y_total_return` 等
- `services/health/`：`grade.compute_4d_health`／`score_fx_risk`、`report.build_health_analysis_row`／`build_dividend_summary_row`、`dividend.check_eating_principal_1y_mk`／`classify_eating_principal`／`check_333_principle`／`_resolve_adr_with_fallback`、`dividend_calc.compute_dividend_twd_series`／`monthly_dividend_from_records`／`latest_dividend_per_unit`、`replacement.check_replacement_recommendation`、`action.combine_action`、`asset_class.classify_core_satellite`／`summarize_core_satellite_allocation`／`infer_weight_mode`
- `services/zscore_engine.py`：`nav_zscore`、`rebalance_signal`、`is_core_bucket`
- `services/fund_screening.py`：`check_333_fund`、`batch_333_funds`、`compute_base_state`、`screen_funds`、`fund_inception_years`
- `services/quality_score.py`：`compute_quality_score`；`services/peer_rank.py`：`peer_quartile_labels`、`peer_quartile`、`annualized_return`；`services/ladder235.py`：`ladder_signal`
- `services/fund_type_classifier.py`：`classify_fund_type`／`efficiency_ratio`；`services/fund_invest_calc.py`：`estimate_monthly_income`／`comparable_ccy`／`fund_currency`／`dividend_currency`／`fund_nav`／`fx_rate_to_twd`（單組 grep：只有新 ⑧ `ui/views/page_03_research.py` import）
- `services/currency.py`：`normalize_ccy`
- `services/fund_history.py`：`record_fund`／`get_history_df`／`promote_to_preset`／`export_preset_funds_json`（讀取端在 `ui/` 0 caller，單組 grep；淘汰候選 A4）

### 4.2 多檔比較與候選標的（B 組；含方向性輸出）

- `services/fund_grp_health/`：`capture.capture_by_code`、`risk.hwm_sigma_by_code`／`risk_compare_by_code`、`signals.mk_signal_by_code`、`quality.quality_score_by_code`／`quality_detail_for_code`、`unified.build_merged_extra_columns`／`sharpe_provenance_by_code`／`reconcile_by_code`
- `services/portfolio_service.py`：`calc_fund_factor_score`、`get_factor_availability`、`dividend_safety`、`risk_alert`、`calc_holdings_overlap`、`calc_correlation_matrix`、`compute_max_drawdown`、`compute_portfolio_drawdown`、`rank_funds_within_portfolio`
- `services/homogeneity.py`：`homogeneity_grade`、`build_mutual_exclusion_summary`；`services/allocation_backtest.py`：`backtest_allocations`、`run_strategy`、`rebalance_dates`
- `services/regime_fit.py`：`normalize_regime`、`asset_bucket`、`tag_regime_fit`
- **方向性（依 BL-0314 路線）**：`services/rotation.py`：`classify_base`、`is_healthy_buy`、`revert_upside_pct`、`insufficient_sigma_names`、`rows_from_batch_df`、`suggest_rotation_pairs`；`services/switch_strategy.py`：`switch_score`、`switch_signal`、`switch_coverage_label`、`replacement_candidate`、`market_regime_alert`、`execution_advice`；`services/switch_advisor.py`：`assess_underperformance`、`advise_holding`、`advise_switches`、`eat_is_red`（動作常數 `SWITCH`／`SELL_CASH`／`WARN`／`HOLD`／`INSUFFICIENT`，純建議標籤、不落帳）；`services/policy_fee_optimizer.py`：`optimize_policy_fee`、`build_fee_inputs`；`services/switch_notify.py`：`build_notification`；`services/dividend_calendar.py`：`build_month_calendar`

### 4.3 搜尋、池與 NAV 歷史（B 組／C 組）

- `services/fund_search.py`：`search_funds`（thin L2，僅新 ⑧ 用；C5）
- `services/nav_history_store.py`：`import_nav_csv`／`import_nav_csv_multi`、`list_cache_codes`、`export_nav_csv`、`get_cache_status`、`incremental_update`、`clear_cache`、`backfill_to_gs`（`_CACHE_DIR = cache/nav_history`）
- `services/nav_history_gs.py`：`status`／`is_enabled`／`backend_status`、`append_points`／`append_point`、`load_points`／`load_series`、`coverage_status`、`import_csv_text`
- `services/fundclear_backfill.py`：`find_fund_candidates`／`download_and_store`／`analyze_backfill_conflict`（UI 0 caller，單組 grep）
- L1（供對照，非 L2）：`repositories/fund/sources.py`（`tdcc_search_fund(_with_error)`、`fetch_fund_multi_source`、`get_page_types_to_try`、各 `_src_*`、`fetch_holdings_cnyes`／`_morningstar`）、`repositories/fund/nav_metrics.py`（`fetch_nav`、`fetch_nav_history_long`、`fetch_div`、`fetch_performance_wb01`、`fetch_risk_metrics`、`fetch_holdings`）、`repositories/fund/fund_orchestration.py`（`fetch_fund_from_moneydj_url`、`search_fundclear`、`search_moneydj_by_name`——後兩者 UI 0 caller，單組 grep）、`repositories/fund/fx_and_main.py`（`fetch_fund_by_key`、`fetch_fund_by_code`）、`repositories/pool_repository.py`（`list_pool`／`add_or_update`／`remove_from_pool`／`set_type_override`／`set_secid`／`resolve_secid`／`resolve_isin`／`resolve_currency`／`pool_backend_status`／`get_pool_store`）、`repositories/batch_checkpoint.py`（`save`／`load`／`delete`／`list_recent`／`compute_run_id`）

### 4.4 持倉帳本與 Sheet（C 組）

- `services/ledger_service.py`：`Ledger.subscribe`／`dividend_cash`／`dividend_reinvest`／`to_dict`／`from_dict`；`GhostPortfolio.compare`；`Switch.switch_same_currency`／`switch_cross_currency`／`_do_switch`；`calculate_xirr`（`dividend_cash`／`dividend_reinvest`／`GhostPortfolio`／`calculate_xirr`：單組 grep ④⑤ UI 內未見呼叫，未逐檔驗證全 repo）；`models/ledger.py::FundPosition`（`units`／`cost_unit`／`fx_avg`／`cost_unit_with_div`／`dividends_received_twd`；`net_investment_twd = cost_unit×units×fx_avg`）。**投資語意**：`txn_type` `subscribe`（新投入，XIRR 負現金流）vs `switch_out`／`switch_in`（內部移動，`amount_twd`＝移轉的 TWD 歷史成本基底，`calculate_xirr` 忽略）；無 `new_capital`／`is_internal` 旗標（單組 grep 0 命中，`d2cd3bb`）；無 redeem 方法
- `services/satellite.py`：`satellite_stop_gain`；`services/hot_money_service.py`：`fetch_usdtwd_frame`、`fetch_hot_money_frames`
- `services/ai_service.py`：`gemini_generate`、`get_gemini_keys`、`analyze_portfolio_mk_advisor`（方向性）；`services/ai_prompts.py`：`build_structured_summary_prompt`
- L1（供對照）：`repositories/policy/_helpers.py`（`REQUIRED_COLS`／`OPTIONAL_COLS`／`ALL_COLS`、`get_gspread_client`、`get_gspread_client_from_oauth`、`parse_invest_twd`／`normalize_invest_twd_column`／`get_invest_twd_parse_errors`）、`repositories/policy/v1.py`（`load_policies`／`upsert_policy_row`／`delete_policy_row`／`sync_policies_to_portfolio_funds`）、`repositories/policy/v2.py`（`list_policy_worksheets`／`ensure_policy_worksheet`／`load_policy_worksheet`／`load_all_policy_worksheets(_with_error)`／`upsert_fund_in_policy`／`delete_fund_in_policy`／`delete_policy_worksheet`／`rename_sheet`／`get_sheet_title`／`list_user_sheets`／`list_user_folders`／`create_dashboard_sheet`／`compute_units`／`avg_nav_with_div_from_cumul_div_twd`／`is_v2_worksheet`／`detect_sheet_schema_version`／`estimate_dividend_split`／`load_policy_v2`／`write_policy_v2`／`load_all_policies_v2(_with_error)`／`copy_sheet_as_backup`）、`repositories/snapshot_repository.py`（`ensure_state_worksheet`／`save_all_ledgers_snapshot`／`save_holdings_overview`／`load_all_ledgers_snapshot`／`get_state_metadata`）、`repositories/ledger_repository.py`（`ensure_ledger_worksheet`／`load_all_ledgers(_with_error)`／`append_ledger_row`／`replace_ledgers_for_policy`）、`ui/helpers/cloud_io.py`（`dump_all_to_sheet`／`load_all_from_sheet`；淘汰候選 D6）、`ui/helpers/io/oauth_state.py`（`_gsa_secret`／`_sheet_id_secret`／`_resolve_oauth_cfg`／`refresh_oauth_state`／`get_login_state`／`_get_oauth_client`／`handle_oauth_callback`）、`scripts/migrate_v149_schema.py`（`migrate_sheet`／`migrate_one_policy`；淘汰候選 D7，子法 1 F6 凍結不刪）

### 4.5 總經（A 組）

- `services/macro`：`fetch_all_indicators`、`calc_macro_phase`、`detect_turning_points`、`detect_systemic_risk`、`macro_action_light`、`clear_tab1_macro_caches`、`calc_sub_cycle_lights`、`daily_key_alerts`、`rank_macro_drivers`、`backtest_sub_cycle_lights`；`services/macro/composite_score.py`：`calculate_composite_score(ind, provenance_out=)`、`reconcile_composite_score`；`services/macro/evidence.py`：`phase_support`
- `services/allocation_ladder.py`：`allocation_from_composite(score, ndc)`；`services/risk_radar.py`：`detect_risk_radar`、`summarize_radar`；`services/liquidity_engine.py`：`fetch_liquidity_factors`、`compute_liquidity_score`、`liquidity_verdict`；`services/us_liquidity_engine.py`：`fetch_us_liquidity_snapshot`；`services/realtime_signal.py`：`compute_realtime_dashboard`（舊決策矩陣，已裁示退役 `DEC-2026-10-19-01`）
- **UI 內（非 services）仍自算、尚未下沉的**：三合一圖的 MA20/MA60/布林、買賣點「觸發／接近」判定、投資試算的單位數除法、T7 B 投入再平衡的分配公式（E2）、tab1 舊頁的 ③例外／④可信度彙總、midcycle 的 Z-Score 卡片分類

---

## §5 未盤／未驗清單（四組「未掃到／不確定」合併；不要當成「全都查過了」）

**共通**
1. **未實跑任何 UI**（未起 Streamlit、無 secrets、未看畫面）；各表「顯示什麼」欄為讀碼推定。
2. **可達性為靜態 import 追蹤**（從 `app.py` `st.tabs` 往下追 import／呼叫，單組 grep），未以 AST 驗證動態 import；未跑任何測試。`render_macro_tab` 0 caller、`tab1_macro_{longterm,radar,inflection,ai}` 只被 `render_macro_tab` 呼叫，皆為單組結論。
3. 四組的 §1～§3 判斷（Gap 類型、建議、合併、淘汰）由總管單方產出；本檔由文件組照寫，**落盤後另派獨立稽核**。
4. 客戶 2026-10-22 指示經總管轉達，repo 內無逐字存檔。

**舊 UI A 組（① 市場總覽／單檔／sidebar／`app.py`）**
5. 只掃指派檔：`ui/tab1_macro*.py`、`ui/tab2_single_fund.py`、`ui/sidebar.py`、`app.py`、`ui/views/page_01_macro.py`、`ui/tab_fund_research.py`、`ui/helpers/fund_research/code_finder.py`、`services/moneydj_fetcher.py` 與少數 helper 的 def 行。`ui/helpers/**` 與 `repositories/fund/*` 只看函式名與 import，未逐行讀；「資料來源」欄對這些依 docstring／檔名推斷。
6. `tab2_single_fund.py` 共 2795 行（`d2cd3bb`），健診大卡、風險表細節、投資試算分支只以 grep 抽樣。
7. 「🔄 重新下載」按鈕只在文案出現，`ui/` 內無同名按鈕（單組 grep）；是否以其他字樣實作於 `ui/helpers/settings_diag/fetch_diag_section.py`，未查。
8. `ui/components/` 17 檔只列被 `tab1_macro*`／`tab2` 直接 import 者；其餘是否被 ① 新 View 經 `ui.helpers.ia` 間接用到，未查。
9. `page_01_macro.py` 2263 行只做結構級盤點；每張卡內的門檻、灰態條件未逐一記。OAuth in-app wizard 的實際 UI 在 ④（非 A 組範圍）。`fund_fetcher.py` 根目錄 shim 的 `get_proxy_config`／`fetch_market_news` 轉接到哪個 L1，未追。

**舊 UI B 組（③ 標的探索／多檔比較／② 持倉體檢）**
10. `tests/test_wpf_five_tab_wiring.py`、`tests/test_fund_research_merge.py` 未讀。
11. `ui/tab2_single_fund.py` 投資試算細節、AI 快照內容、健診卡 KPI 細項區段未逐行讀；`ui/tab_fund_grp_health.py` 加權方式說明、核心衛星 note 與中段未逐行讀。
12. `ui/helpers/fund_grp_health/` 的 `ai.py`、`correlation.py`、`dividend.py`、`signals.py`、`investment.py` 只掃標題與 import，各表具體欄名未抄；`ui/helpers/fund/checkup.py` 4 大健診卡內容未讀（只抄 PK 表欄）。
13. `ui/views/page_03_research.py`（新 ⑧）只讀檔頭；它與舊 ③ 的功能差異未盤（→ BL-0410）。
14. `repositories/fund/sources.py` 4000+ 行只讀 `tdcc_search_fund` 與函式清單；`fetch_fund_multi_source` 實際 fallback 順序未逐行確認（`CLAUDE.md` §2.1 寫 yp010000 → yp010001 → TDCC → FundClear → Cnyes，未複核）。
15. `calc_metrics` 的 perf 1M/3M/6M 是否在任何舊 UI 表格顯示：tab2 `"1M"` 0 命中（單組 grep，`d2cd3bb`），僅 checkup PK 表顯示——`ret_1m` 來源未追。`_MAX_CODES` 的值未查。
16. 「③ 內無加入池按鈕」「批次無疊圖」「③／② 內無更新按鈕」「`fund_history.get_history_df` UI 0 caller」皆為單組 grep 結論。

**舊 UI C 組（④ 資產配置／持倉＋⑤ 設定與診斷）**
17. `ui/tab3_portfolio.py` 戰情室 KPI 與健診並行區段僅以 grep 掃關鍵字，未逐行通讀；每檔建議卡 `_compute_advice_for` 的全部欄位未逐欄列出。
18. `ui/tab5_data_guard.py` ⓪ 檢查表的逐列項目未逐一抄錄；`ui/tab6_manual.py` 各章內文只記章名與主要表／公式；`ui/components/mk_dashboard.py` 各 tag 函式的門檻值未列。
19. `services/portfolio_service.py`、`services/fund_invest_calc.py`、`services/switch_advisor.py` 內部門檻／公式未展開；`fund_invest_calc` 呼叫者僅 grep `ui/ services/ app.py`。
20. `delete_fund_in_policy`／`delete_policy_worksheet`／`rename_sheet`／`fix_and_shrink_v2_sheets`／`Ledger.dividend_cash`／`dividend_reinvest`／`GhostPortfolio`／`calculate_xirr` 的 production caller 只在 ④⑤ 相關檔 grep，**未全 repo 驗證**是否為 0 caller。
21. T7「鎖定為主帳本」是否觸發 `_Ledgers`／`_T7_State` 寫入僅由 grep 區段判讀，未逐行讀完該 handler；T7 頂部 v2「純模擬器」warning 與實際寫入路徑的關係只做了 `grep _schema_ver`，未跑程式驗證。
22. `_render_pool_editor` 完整欄位（ISIN／型態覆寫／晨星代碼）只掃到按鈕與 L1 呼叫，未逐欄列。`tests/` 守衛未讀，文中引用的守衛名轉錄自原始碼註解。Google Sheets 實際分頁是否存在（`_T7_State`／`_Ledgers`／`_持倉總覽`／`nav_history`／`_fund_pool`）無法離線驗證。

**B 版組（`ui_v2/` 五頁）**
23. `docs/v2/44_fund_ui_ssot.md` 只讀各塊標題與「來源」欄首行（5288 行全文未逐行通讀）。
24. `ui_v2/*/logic.py`（exp 2488 行、hld 3234 行，`d2cd3bb`；alo／mkt／set）未逐行通讀，只讀常數區、`_build_*` 片段與 grep 命中；`ui_v2/{health,sections,plain,symbols,page_health}.py` 只讀 grep 命中片段；`ui_v2/*/live.py` 只讀常數與函式清單，各頁「正式模式才有的文案」未逐句列出。
25. BL-0389「資產配置兩顆」的第二顆在 alo 程式內未定位（只找到 `_build_alo4` 一處；hld HLD-0 另一處）；可能是同一按鈕在不同狀態各畫一次，未驗。
26. BL-0250「UI Audit 候選十項」：BACKLOG／HANDOFF 以 `十項`、`UI Audit`、`候選` grep 0 對應列；可能在 `docs/evidence/` 或 `docs/v2/55`～`61` 內，未掃。`docs/evidence/phase3_uiux_audit_2026-10-17/oauth_rw_audit.md`、`docs/v2/49`、`50`、`55`、`58`、`59`、`61` 未讀。
27. hld／alo 讀的保單試算表三分頁（`POLICY_TAB`／`TAB_PROFILE`／`TAB_SUPPLEMENT`）實際分頁名未展開查；mkt 正式模式每次 render 是否真的打外部（L1 快取 TTL）未查 `repositories/macro/*` 快取設定；`tests/ui_v2/` 共 77 檔未讀（`ls tests/ui_v2 | wc -l`，`d2cd3bb`；B 版組原記 78，總管實測更正），守衛宣稱轉述自程式 docstring。

**本檔自身**
28. 本檔 §1～§3 一字照抄總管規格，§4／§5 從四組盤點抄錄並按模組重排；文件組未重跑任何 grep、未重讀任何原始碼。§4 的分組（4.1～4.5）與「方向性」標註是文件組依規格 §2 的歸類，未經第二組驗證。

---

## §6 New UI Capability Matrix 與驗收條件（2026-10-25；量測 SHA `7d41705f`）

> ⛔ **本節不構成 production 動工授權**，也不構成 UI 改版核准、不解除 `DEC-2026-10-22-02` G8、不解凍 `docs/v2/44_fund_ui_ssot.md`。本節是規劃與收斂文件：把「舊 UI 值得保留的操作能力」與「客戶 2026-10-25 要求的新 UI 能力」收斂成一張能力表＋可測驗收條件，並對到既有 BACKLOG 列。任何版面配置（Layout）、元件增刪、分頁動線，**動工前仍須先出 UI 線框草稿送客戶核准**（`CLAUDE.md` §-1.5.4、v3 `03`-2 ①；UI 草稿先行與 v1.0 Stop／Decision Gate 並列）。

- **出處**：客戶 2026-10-25 授權本文件批「New UI operational capabilities → 現有 SSOT／BACKLOG 收斂」（要點轉述，經總管派工單轉達；repo 內無逐字存檔；文件組未見客戶對話本身）。決策登記：`docs/DECISIONS.md` `DEC-2026-10-25-01`。
- **與既有文件的關係**：本節是 BL-0435（新版 UI/UX Blueprint 主工作項）的**輸入**，不是平行規格；Blueprint 仍是唯一登記處。資訊擁有權以 `docs/v2/64_v2_ssot_convergence.md` §2 為準，本批在 64 §2.1 補一段「操作能力的唯一擁有者」，不另立第二份。
- **ID 規則**：`CAP-SET-xx`／`CAP-FND-xx`／`CAP-HLD-xx`／`CAP-RFR-xx`／`CAP-GATE-xx` 是**本節的局部 ID，不是 BL ID**，也不是 `docs/v2/64` §9.7 的 `DG-1`～`DG-6`。對應 BL 見各表「Existing BL」欄與 §6.9。
- **頁名對照**：🌍 市場與趨勢＝B 版 `mkt`；⚖️ 資產配置＝`alo`；💼 我的持股＝`hld`；🔍 找基金＝`exp`；⚙️ 設定＝`set`（`ui_v2/` 現行五頁；新頁名依 `DEC-2026-10-23-01`）。
- **欄位安排**：一頁一組兩張表 —— 主表（Capability｜Owner page｜User action｜Existing evidence／current capability｜Old UI reference｜Current B UI state｜Existing BL｜Dependency｜Implementation order｜Decision Gate｜Notes），以及同 ID 的驗收表（Acceptance criteria｜Success state｜Failure state｜Missing／Unknown state｜Refresh／Retry behavior）。兩張表合起來即派工單要求的全部欄位。
- **Current B UI state 的性質**：文件組在 `7d41705f` 讀 `ui_v2/*/logic.py`、`ui_v2/*/source.py`、`services/v2_tables/settings_store.py`、`repositories/settings_sheet_repository.py`、`services/fund_search.py` 的常數、函式與註解；**未起 Streamlit、未看畫面、未跑測試**。Old UI reference 欄轉錄自本檔 §1～§4（2026-10-22 盤點，量測 `d2cd3bb`），本批未重讀舊 UI 原始碼。

### §6.1 共通狀態與驗收規則（四頁共用；不新增文案，最終字樣依 44 現行字表與核准後的 UI 草稿）

1. **Google 帳號狀態只有四態**：已登入（Signed in）／未登入（Signed out）／授權錯誤（Auth error）／無法判定（Unknown）。讀不到狀態一律「無法判定」，**不得預設為已登入**。
2. **Sheet 狀態**：載入中（Loading）／成功（Success）／空（Empty：讀到了、但沒有資料列）／URL 或 ID 格式無效（Invalid）／找不到（Not found）／無權限（Permission denied）／認證失敗（Authentication failure）／API 或取數失敗（API／fetch failure）／缺值或無法判定（Missing／Unknown）。
   - **現有 API 能分到哪裡（讀碼，未實跑）**：設定試算表 L1 `repositories/settings_sheet_repository.py` 以 `SettingsSheetError.code` 區分 `not_configured`（未設定）、`no_service_account`（無服務帳戶）、`cooling`（冷卻中）、`header_mismatch`（標頭不符）、`api`（其餘上游例外，另帶 `http_status`，故 403／404 可由狀態碼分辨）。
   - **分不到的，一律併入「無法判定」**：(a) 持倉試算表（`repositories/policy/v2.py::load_all_policies_v2_with_error`）與選股池路徑只交出錯誤原文、不分類，403／404／認證失敗在現行 API 下**無法可靠區分**；(b) 「URL／ID 格式無效」本組未在 B 版路徑找到格式驗證（未驗）；(c) 「認證失敗」與「無權限」在服務帳戶路徑是否回不同狀態碼，未實測。這三類在新 API 能分辨前，畫面一律顯示「無法判定」並附錯誤原文（遮蔽後），不猜成其中一類。細分錯誤分類屬內部技術工作（不改語意），但會動 L1，須另派工。
3. **操作結果**：成功 → 畫面顯示**最新**狀態（重新讀回，不是沿用按下前的畫面）；失敗 → 顯示失敗原因＋Retry，**保留上一份有效資料，並標示資料日期／舊資料**（不得洗成 0、空表或「尚未建立」；對齊 CAP-RFR-00 與 `CLAUDE.md` §2.4 `is_stale`）。
4. **Missing 一律灰**：缺值顯示「⬜ 資料未取得／無法判定」（找基金欄位缺值沿用 64 §6「⬜ 資料未備／無法判定」），**不得顯示綠色／安全**。Missing ≠ 0 ≠ False ≠ HOLD ≠ 安全 ≠ 未觸發（`DEC-2026-10-24-02`、`PROJECT_RULES.md` 第 13 節 13.1）。
5. **寫入邊界**：凡會寫入任何試算表（設定、持倉、選股池、NAV）的能力，畫面須明示「這個動作會寫入哪一本」；唯讀頁不出現寫入字樣或寫入控制項（BL-0349 完成條件）。是否開放寫入本身是 Decision Gate（§6.8）。
6. **刷新只動資料、不動設定**：Refresh／Retry 只重新讀取資料，不得清除或改寫使用者設定（目標配置、門檻、綁定、觀察清單）。

### §6.2 ⚙️ 設定 —— 主表

| Capability | Owner page | User action | Existing evidence / current capability | Old UI reference | Current B UI state | Existing BL | Dependency | Implementation order | Decision Gate | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| CAP-SET-01 Google 登入 | ⚙️ | 按「登入 Google」→ 完成授權 → 回到設定頁 | `infra.oauth.build_authorize_url`、`ui/helpers/io/oauth_state.py::handle_oauth_callback`（舊 UI 用） | §1 D1（sidebar 登入＋④ in-app OAuth 引導）；D5 SA／OAuth 雙模式 | 無任何登入元件；只走服務帳戶 secret。`ui_v2/*/source.py` 讀 `st.session_state["gsheet_tokens"]` 只用於遮蔽（`masking.secret_values`），不用於授權 | BL-0402、BL-0349、BL-0381 | 無（第一個能力） | 1 | CAP-GATE-01（OAuth scope、權杖存放、資安 2 組稽核） | BL-0349 護欄 4：目前不授權改 OAuth scope／Q10／T6／production write architecture |
| CAP-SET-02 Google 登出 | ⚙️ | 按「登出」→ 清除本次登入 | `oauth_state` 清 session（舊 UI） | §1 D1 | 無 | BL-0402、BL-0349 | CAP-SET-01 | 1 | CAP-GATE-01 | 登出後不得殘留已綁定 Sheet 的資料顯示為「目前帳號」 |
| CAP-SET-03 登入／帳號狀態顯示 | ⚙️（他頁只顯示摘要） | 看一眼即知目前是誰、用哪種憑證（服務帳戶或個人帳號） | `oauth_state.get_login_state`；`settings_store.service_account_status`（B 版，只回服務帳戶有無設定） | §1 D1、D3 | 只有服務帳戶有無設定的狀態（SET-0／SET-2 系列）；無個人帳號狀態 | BL-0402、BL-0393 (5) | CAP-SET-01 | 1 | CAP-GATE-01 | 四態見 §6.1 第 1 點 |
| CAP-SET-04 Sheet URL／ID 輸入 | ⚙️ | 貼上 Sheet 網址或 ID → 系統解析並試讀 | 舊 sidebar `inp_sheet_id`；`session_state["policy_sheet_id"]` 優先於 secret | §1 D2 | 無；`POLICY_SHEET_ID` 綁死 secret | BL-0402、BL-0392 | CAP-SET-03 | 1 | CAP-GATE-02（綁定紀錄存在哪裡） | 解析失敗 → 「格式無效」或「無法判定」（§6.1 第 2 點 (b)） |
| CAP-SET-05 可存取 Sheet 清單載入 | ⚙️ | 按「列出我能用的 Sheet」→ 看到清單 | `repositories/policy/v2.py::list_user_sheets`／`list_user_folders`（需個人授權；舊 ④「從 Drive 挑帳本」） | §1 D2 | 無 | BL-0381 (2)、BL-0402 | CAP-SET-01 | 1 | CAP-GATE-01 | 服務帳戶模式下沒有「我的 Drive」可列，只能貼 ID |
| CAP-SET-06 Sheet 選擇 | ⚙️ | 從清單點一本 | 同上 | §1 D2 | 無 | BL-0381 (3)、BL-0392 | CAP-SET-05 或 CAP-SET-04 | 1 | CAP-GATE-02 | 選擇 ≠ 綁定；選完要明確按綁定 |
| CAP-SET-07 持倉 Sheet 綁定（含顯示目前綁定對象） | ⚙️（💼 只讀這份綁定） | 按「綁定為持倉來源」→ 畫面顯示目前綁定的 Sheet 名稱＋可開啟連結 | `repositories/policy/v2.py::get_sheet_title`；B 版 `settings_store.sheet_title` 只顯示**設定試算表**標題 | §1 D2、D3、D4 | 只顯示設定試算表名稱；持倉、選股池那兩本的名稱不顯示；「前往 Sheets 維護持倉」按鈕依 G5(b) 移除（BL-0389） | BL-0402、BL-0381 (4)(5)、BL-0392、BL-0389 | CAP-SET-06 | 1 | CAP-GATE-02 | 「顯示連到哪幾本＋可開啟連結」即使維持服務帳戶唯讀也成立（BL-0402 下一步原文）；但開啟連結是否算 G5(b) 所禁的「自行新增目的地」，隨 UI 草稿一併確認 |
| CAP-SET-08 切換綁定 | ⚙️ | 選另一本 → 按「改綁定」→ 確認 | 同上 | §1 D2 | 無 | BL-0381 (6)(7)、BL-0392 | CAP-SET-07 | 1 | CAP-GATE-02 | 只有使用者明確操作才切換；不得自動改用其他 Sheet（BL-0381 (7)）；不得把 wen 帳本設計成永久唯一來源（BL-0392） |
| CAP-SET-09 新增（綁定第二本／新建帳本） | ⚙️ | 新增一個綁定；或「建立新帳本」 | `create_dashboard_sheet`（舊 ④「✨ 新增帳本」，會在使用者 Drive 建檔） | §1 D2、D8 | 無 | BL-0392、BL-0402、BL-0363 | CAP-SET-07 | 1 | CAP-GATE-02（多本綁定的資料模型）；CAP-GATE-03（新建檔＝寫入使用者 Drive） | 新建整本試算表＝新增生產檔案；BL-0363 已登記「設定 L1 不得建立或複製整本試算表」的守衛方向 |
| CAP-SET-10 解除綁定 | ⚙️ | 按「解除綁定」→ 確認 | 無 B 版實作 | — | 無 | BL-0381、BL-0392 | CAP-SET-07 | 1 | CAP-GATE-02 | 只移除綁定紀錄，不刪 Sheet 本身；解除後 💼 顯示「尚未綁定」，不是「沒有持倉」 |
| CAP-SET-11 刪除（Sheet 檔／分頁／資料） | ⚙️ | （僅定義，不實作） | 舊 L1 `delete_policy_worksheet`／`delete_fund_in_policy`（production caller 未全 repo 驗證，見 §5 第 20 點） | §4.4 | 無 | BL-0405（T7 分頁去留）、BL-0409（淘汰候選清單） | — | —（只定義、不排程） | **CAP-GATE-03（不可逆，Stop Gate）** | 本批只定義能力與驗收，不實作、不排程；不可逆刪除須客戶逐案裁示（v1.0 Gate：無法證明安全的資料／歷史成果刪除） |
| CAP-SET-12 重新載入（Sheet 清單與綁定狀態） | ⚙️ | 按「重新載入」 | 設定 L1 有冷卻機制（`code="cooling"`，帶剩餘秒數） | §1 F4（全域刷新） | SET-5「重新取數」只管市場指標與淨值兩層，不管 Sheet 清單／綁定 | BL-0402、BL-0452 | CAP-SET-07 | 1 | — | 冷卻中要顯示剩餘時間，不重複打上游（BL-0184：重新取數無次數限制） |
| CAP-SET-13 連線／權限／同步／新鮮度／重試狀態 | ⚙️（他頁只顯示 freshness 標記） | 看一張狀態總表；失敗列旁有 Retry | SET-0 可信度結論燈、SET-1 資料新鮮度卡、SET-2 來源健康卡、SET-6 取數紀錄（`fetch_log`） | §1 F2（⑤ 診斷） | SET-0～SET-7 八塊（`ui_v2/set/logic.py::BLOCK_TITLES`）；客戶 2026-10-22 已登記「對一般使用者過度複雜」 | BL-0346、BL-0351、BL-0391、BL-0408、BL-0393 (5) | CAP-SET-07 | 1 | CAP-GATE-10（診斷深度方向衝突） | 新增 Google／Sheet 狀態列時，不得再加重 BL-0391 所指的工程資訊；精簡方向隨 UI 草稿 |

### §6.2a ⚙️ 設定 —— 驗收表

| Capability | Acceptance criteria | Success state | Failure state | Missing / Unknown state | Refresh / Retry behavior |
|---|---|---|---|---|---|
| CAP-SET-01 | 授權完成後回到設定頁，帳號狀態由「未登入」變「已登入」並顯示帳號；授權取消或失敗不得顯示已登入 | 已登入＋帳號（遮蔽規則照 ACCEPTANCE 7.2） | 授權錯誤＋錯誤原文（遮蔽後）＋重試 | 無法判定（不預設已登入） | 失敗時顯示「重新登入」；不自動重試 |
| CAP-SET-02 | 登出後帳號狀態為「未登入」，依個人授權讀到的 Sheet 清單與資料不再顯示為目前帳號 | 未登入 | 登出失敗＋原因；狀態維持「已登入」並說明 | 無法判定 | 可再按一次 |
| CAP-SET-03 | 四態逐一可測；服務帳戶與個人帳號分開顯示 | 已登入／服務帳戶已設定 | 授權錯誤 | 無法判定（灰） | 隨 CAP-SET-12 重新讀 |
| CAP-SET-04 | 貼網址或 ID 皆可；前後空白處理照既有規則；試讀結果依 §6.1 第 2 點分態 | 成功＋Sheet 名稱 | 格式無效／找不到／無權限／認證失敗／API 失敗（分不到的併「無法判定」並附原文） | 無法判定 | 失敗可重試；不清空輸入框 |
| CAP-SET-05 | 清單只列帳號可存取的 Sheet；空清單與讀取失敗分開 | 清單（含名稱） | 失敗＋原因＋重試 | 「空」（讀到了但沒有）與「無法判定」分開 | 「重新載入清單」 |
| CAP-SET-06 | 點選只改「候選」，未按綁定前 💼 不變 | 已選（未綁定） | — | — | — |
| CAP-SET-07 | 綁定後 ⚙️ 與 💼 顯示同一個 Sheet 名稱；可開啟連結；綁定前後的持倉讀取來源一致可追溯 | 已綁定＋名稱＋最後讀取時間 | 綁定失敗＋原因；保留原綁定 | 尚未綁定（不是「沒有持倉」） | 綁定失敗可重試 |
| CAP-SET-08 | 切換須明確確認；切換失敗時原綁定不變；任何程式路徑不得自動改綁 | 新綁定＋名稱 | 失敗＋原因；原綁定照舊顯示 | — | 可重試 |
| CAP-SET-09 | 新增綁定不覆蓋既有綁定；新建帳本須明示「會在你的 Drive 建立一個新檔」 | 新綁定出現在清單 | 失敗＋原因；既有綁定不變 | — | 可重試；新建檔失敗不得留半成品而不告知 |
| CAP-SET-10 | 解除後 💼 顯示「尚未綁定」；Sheet 本身不被刪除 | 未綁定 | 失敗＋原因；綁定照舊 | — | 可重試 |
| CAP-SET-11 | （只定義）任何刪除須逐案客戶裁示；動工前須能證明可回復或已備份；畫面須二次確認並寫出刪除對象 | （未授權） | （未授權） | （未授權） | （未授權） |
| CAP-SET-12 | 冷卻中不打上游並顯示剩餘秒數；重新載入只重讀，不改綁定與設定 | 最新狀態＋讀取時間 | 失敗＋原因；保留上一份有效狀態 | 無法判定 | 本身即 Retry；冷卻期間停用並寫原因 |
| CAP-SET-13 | 每一列分開顯示連線／權限／同步／新鮮度；投資面狀態與資料面狀態不混在同一燈（BL-0346） | 綠燈只用在確實讀到且新鮮 | 紅＋原文 | 灰「⬜ 資料未取得／無法判定」 | 失敗列旁 Retry，走 §6.6 同一機制 |

### §6.3 🔍 找基金 —— 主表

| Capability | Owner page | User action | Existing evidence / current capability | Old UI reference | Current B UI state | Existing BL | Dependency | Implementation order | Decision Gate | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| CAP-FND-01 代碼直接查詢 | 🔍 | 輸入代碼（例 `ACTI71`）→ 查 → 看到該檔 | `services.moneydj_fetcher.auto_fetch_moneydj` → `services.fund_service.fetch_fund_from_moneydj_url_enriched` → L1 `repositories/fund/fund_orchestration.fetch_fund_from_moneydj_url`（多源 fallback） | §1 A1 | 無單檔查詢框；只能經 EXP-1 條件「fund_code 等於…」＋存檔＋重跑，且限選股池內代碼 | BL-0397 | CAP-SET-07（若查詢結果要對照持倉）；否則無 | 2 | CAP-GATE-07（池外查詢範圍） | 客戶 2026-10-25 要點：直接查、使用者不需先理解候選池。文件組讀法＝可查池外代碼（可被客戶推翻，隨 UI 草稿確認） |
| CAP-FND-02 名稱搜尋（結果可直接帶入查詢） | 🔍 | 輸入名稱關鍵字 → 看候選 → 點一筆直接帶入 CAP-FND-01 | `services.fund_search.search_funds`（thin L2）→ L1 `repositories.fund.tdcc_search_fund`；另有 `tdcc_search_fund_with_error`（交出失敗原文） | §1 A2（舊版結果只顯示代碼、要手抄） | 無名稱搜尋（EXP-1 只有「等於」） | BL-0397 | CAP-FND-01 | 2 | CAP-GATE-06（名稱搜尋涵蓋範圍） | 只重用既有可追溯鏈，不新增來源；`tdcc_search_fund` docstring 寫「搜尋境外基金」，境內基金是否涵蓋未驗 |
| CAP-FND-03 候選池：新增 | 🔍（池所在的 Sheet 連線歸 ⚙️） | 在查詢結果或清單上按「加入候選池」 | L1 `repositories/pool_repository.py::add_or_update`（EX-CRUD-1） | §1 C1（⑤ 管理室） | 無；exp 只讀選股池 `code` 欄當母體（`exp_universe.load_pool_codes`）。另有 EXP-5「加入觀察清單」，寫 `user_setting` 的 `exp_watchlist`，只存代碼 | BL-0400 | CAP-SET-07（池 Sheet 連線）；CAP-FND-01 | 2 | CAP-GATE-05（候選池是哪一份）；CAP-GATE-04（寫池＝寫入邊界） | 現行有兩份「候選」清單：選股池（`POOL_SHEET_ID`→`_fund_pool`）與觀察清單（設定試算表 `exp_watchlist`）—— 不得在未裁示前再造第三份 |
| CAP-FND-04 候選池：移除 | 🔍 | 按「移出候選池」→ 確認 | `pool_repository.remove_from_pool` | §1 C1 | 無 | BL-0400 | CAP-FND-03 | 2 | CAP-GATE-05、CAP-GATE-04；若為實體刪列 → CAP-GATE-03 | 移出是否為狀態改 CLOSED（可回復）或刪列（不可逆）未定 |
| CAP-FND-05 候選池：重新載入 | 🔍 | 按「重新載入候選池」 | `pool_repository.list_pool`（L1 無快取）；L2 `exp_universe` 有代碼快取 | §1 C1 | 母體隨頁面讀取；無獨立重新載入 | BL-0400、BL-0452 | CAP-FND-03 | 2 | — | 走 §6.6 同一機制 |
| CAP-FND-06 搜尋失敗／不存在／未取得狀態與 Retry | 🔍 | 查不到時看到原因並可重試 | `search_funds` 明文「空清單的語意是含混的」（`EMPTY_MEANS_UNKNOWN`）；`tdcc_search_fund` 失敗照舊回 `[]`；只有 `_with_error` 版本分得出失敗 | §1 A1、A2 | 無 | BL-0397 | CAP-FND-01、CAP-FND-02 | 2 | — | 現行 thin L2 分不出「查無此檔」與「查詢失敗」→ 在改用 `_with_error` 或等效路徑前，空結果一律顯示「無法判定」，不得說「不存在」 |
| CAP-FND-07 欄位缺值顯示 | 🔍 | 看查詢結果／候選清單的各欄 | EXP-6 單檔基礎資料六欄（費率恆 ⬜） | §1 A3、B1 | 部分欄位已用 ⬜ | BL-0397、BL-0398、BL-0399 | CAP-FND-01 | 2 | — | 缺欄的基金**照列**，該欄顯示「⬜ 資料未備／無法判定」；不得顯示 0、不得因缺欄排除，除非有正式篩選規格 |

### §6.3a 🔍 找基金 —— 驗收表

| Capability | Acceptance criteria | Success state | Failure state | Missing / Unknown state | Refresh / Retry behavior |
|---|---|---|---|---|---|
| CAP-FND-01 | 一個輸入框＋一個按鈕即可完成；可查的代碼範圍依 CAP-GATE-07 裁示；查詢結果可追溯資料來源 | 該檔基本資料＋來源與取得時間 | 失敗＋原文＋重試；保留上一筆有效結果 | 欄位缺值依 CAP-FND-07 | 「重試」只重查同一代碼 |
| CAP-FND-02 | 點候選即帶入查詢，不需手抄；候選列顯示名稱與代碼 | 候選清單 | 失敗＋原文（需 `_with_error` 或等效）＋重試 | 空結果在無法分辨失敗前顯示「無法判定」 | 重試同一關鍵字 |
| CAP-FND-03 | 加入前明示寫入哪一本；同一檔重複加入只出現一次；加入後清單重讀顯示最新 | 已加入＋最新清單 | 失敗＋原因；清單維持原樣 | 池 Sheet 讀不到 → 「無法判定」，不說「池是空的」 | 可重試 |
| CAP-FND-04 | 須確認；移除後重讀顯示最新；若屬不可逆刪列須另經 CAP-GATE-03 | 已移除＋最新清單 | 失敗＋原因；清單維持原樣 | 同上 | 可重試 |
| CAP-FND-05 | 只重讀，不改池內容與觀察清單 | 最新清單＋讀取時間 | 失敗＋原因；保留上一份有效清單 | 無法判定 | 本身即 Retry |
| CAP-FND-06 | 「查無此檔」「查詢失敗」「無法判定」三種在可分辨時分開顯示；分不到時只顯示「無法判定」 | — | 失敗原文（遮蔽後） | 無法判定 | 重試按鈕在失敗與無法判定兩態出現 |
| CAP-FND-07 | 缺欄列照列；缺值不得進排序成 0；不得綠色 | — | — | 「⬜ 資料未備／無法判定」 | 隨所屬查詢重試 |

### §6.4 💼 我的持股 —— 主表

| Capability | Owner page | User action | Existing evidence / current capability | Old UI reference | Current B UI state | Existing BL | Dependency | Implementation order | Decision Gate | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| CAP-HLD-01 顯示綁定持倉 Sheet 狀態 | 💼（讀 ⚙️ 的綁定 SSOT） | 進頁即看到「目前讀的是哪一本、何時讀的、讀取成功否」 | `ui_v2/hld/source.py`（只讀 secret 指定的保單試算表） | §1 D3（④ caption「📂 帳本：title｜本地持倉 N 檔｜上次讀回」） | 不顯示持倉試算表名稱；持倉表讀不到時走「系統錯誤」、不說「尚未建立任何持倉」（2026-10-05 讀取失敗不說空） | BL-0402、BL-0403 | CAP-SET-07 | 3 | CAP-GATE-09（版面） | **💼 不放 Sheet 選擇器**；要換本 → 指回 ⚙️（指路形式隨 UI 草稿；G5(b) 不得自行新增目的地） |
| CAP-HLD-02 載入持倉 | 💼 | 進頁或按重新載入 | `services/v2_tables` 持倉讀取（保單分頁＋`_持倉補充`＋`_保單資料`） | §1 E7、E9 | HLD-0～HLD-8 九塊（`ui_v2/hld/logic.py::BLOCK_TITLES`） | BL-0403、BL-0404 | CAP-HLD-01 | 3 | — | 投資語意不變：成本、單位數、市值、累積實領配息照 64 §2 歸 💼 |
| CAP-HLD-03 持倉管理操作（新投入／轉換等） | 💼 | （僅定義）新投入、轉換 A→B；必要時修改 | `services.ledger_service.Ledger.subscribe`、`Switch.switch_same_currency／switch_cross_currency`；`txn_type` 區分 `subscribe` 與 `switch_out／switch_in` | §1 E1、E2、E3、E6（舊 T7 畫面不搬） | 零操作；B 版唯讀（`READONLY_TABLES` 含 holding／policy／nav／dividend） | BL-0403、BL-0404（贖回兩版皆無）、BL-0405（`_Ledgers` 去向） | CAP-HLD-02 | 3 | **CAP-GATE-04（寫入邊界 vs 唯讀裁示）**；投資語意獨立稽核 | **投資語意保留（BL-0403 原文）**：新投入＝外部本金增加；A→B＝既有資產內部移動、不算新投入；舊 T7 畫面不搬。本批不改任何語意 |
| CAP-HLD-04 重新載入／Retry | 💼 | 按「重新載入」或失敗列旁「重試」 | HLD 取數失敗欄有「重新取數」（`_retry_button`）；三張核心卡不掛（客戶 2026-09-23 裁示）；HLD-8 正式模式不放（G6，`DEC-2026-10-22-02`） | §1 F4 | 部分塊有、部分塊依裁示不放 | BL-0452、BL-0390、BL-0290 | CAP-HLD-02 | 3（頁內 Retry）／4（五頁一致化） | CAP-GATE-08（與 G6／2026-09-23 裁示衝突） | 本列只定義行為，不推翻現行裁示 |
| CAP-HLD-05 成功／失敗／缺值狀態 | 💼 | — | 2026-10-05「讀取失敗不說空」；BL-0451 T7 報酬率成本 ≤0 → ⬜（舊 UI，已修） | §1 E7 | 已有部分 ⬜／系統錯誤分流 | BL-0403、BL-0404 | CAP-HLD-02 | 3 | — | 「尚未綁定」「讀取失敗」「沒有持倉」三者分開 |

### §6.4a 💼 我的持股 —— 驗收表

| Capability | Acceptance criteria | Success state | Failure state | Missing / Unknown state | Refresh / Retry behavior |
|---|---|---|---|---|---|
| CAP-HLD-01 | 顯示的 Sheet 名稱與 ⚙️ 綁定一致；頁內沒有任何 Sheet 選擇控制項 | 名稱＋最後讀取時間＋成功 | 讀取失敗＋原文 | 尚未綁定／無法判定（灰） | 失敗時出現 Retry |
| CAP-HLD-02 | 讀取失敗不得畫成「沒有持倉」；部分分頁失敗不拖垮其餘（BL-0351） | 持倉表 | 失敗＋原文；保留上一份有效持倉 | 缺欄 ⬜ | 重新載入只重讀 |
| CAP-HLD-03 | （只定義）若日後開放：每筆操作寫明 `txn_type`；新投入計入外部本金、A→B 不計；寫入前二次確認；寫入後重讀；失敗不留半筆 | （未授權） | （未授權） | （未授權） | （未授權） |
| CAP-HLD-04 | Retry 只重讀資料，不改區間、門檻或任何設定 | 最新資料＋時間 | 失敗＋原因；保留上一份 | 無法判定 | 依 §6.6 |
| CAP-HLD-05 | 三態分開可測 | — | 讀取失敗 | 尚未綁定／⬜ 資料未取得／無法判定 | — |

### §6.5 Unique Owner 收斂（摘要；正式擁有權見 64 §2 與 §2.1）

| 能力群 | 唯一擁有頁 | 他頁只可以 |
|---|---|---|
| Google 登入／帳號、Sheet 連線／選擇／綁定／切換／新增／解除、同步、診斷、freshness、Refresh 機制本身 | ⚙️ | 顯示摘要、status、freshness 標記、指回 ⚙️ |
| 代碼直查、名稱搜尋、候選池（新增／移除／重新載入）、候選工具 | 🔍 | 顯示必要數字、drill-down 到 🔍 |
| 持倉事實（保單、成本、單位數、市值、損益、配息、歷史操作）與持倉操作 | 💼 | ⚖️ 讀 💼 facts；不重算 |
| 配置、曝險、目標 | ⚖️ | — |
| 市場／趨勢 evidence | 🌍 | ⚖️ 引用摘要 |

- **💼 與 ⚙️ 的界線**：Sheet 的連線、選擇、綁定、切換只在 ⚙️；💼 只消費已綁定的 SSOT，**不放第二個 Sheet 選擇器**。文件組查 `docs/DECISIONS.md`、本檔 §1～§3 與 64 §2，未見更高位階規格把 Sheet 選擇放在 💼（舊 ④ 曾有「從 Drive 挑帳本」，那是舊 UI 位置，依 `DEC-2026-10-22-04` 不直接移植）；`docs/v2/44` 本批未逐行讀（5288 行），若 44 另有條文，以 44 為準並轉為 Decision Gate。

### §6.6 五頁 Refresh／Retry（一套機制，五頁共用）

**原則**：五頁不各寫一套刷新邏輯。刷新機制本身（快取清除範圍、冷卻、`fetch_log` 紀錄、freshness 判定）的 SSOT 擁有者是 ⚙️（文件組讀法，隨 BL-0452／CAP-GATE-08 請客戶確認；`services/v2_tables/settings_store.py` 的 `refetch_*`／`run_market_indicator_fetch` 一族與 L1 冷卻）；各頁只呼叫同一機制、只刷新本頁所讀的資料。刷新不得改寫任何設定（§6.1 第 6 點）；freshness 門檻值與語意不變（BL-0351；改門檻屬 Stop Gate）。

| Capability | Owner page | User action | Existing evidence / current capability | Old UI reference | Current B UI state | Existing BL | Dependency | Implementation order | Decision Gate | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| CAP-RFR-00 共用刷新機制 | ⚙️ | — | `settings_store.refetch_cached_functions`、`refetch_market_indicator`、`refetch_nav`；L1 冷卻 | §1 F4 `infra.cache.global_refresh_all` | 預覽五頁共用一個行程，快取與冷卻共用；set「重新取數」會影響 mkt／hld（BL-0290） | BL-0452、BL-0290、BL-0184、BL-0351 | CAP-SET-12 | 4 | — | 先解決 BL-0290 的跨頁副作用，五頁一致化才安全；舊 UI F4 `global_refresh_all` 列於 BL-0409 淘汰候選，僅作參考 |
| CAP-RFR-01 🌍 市場與趨勢 | 🌍（機制屬 ⚙️） | 失敗或空時按「重新取數」 | `ui_v2/mkt/logic.py::_retry_button`（宣告寫 `market_indicator`、`fetch_log`） | §1 F1 | 取數失敗與三塊皆無資料時掛一枚 | BL-0452 | CAP-RFR-00 | 4 | — | 只刷新市場指標 |
| CAP-RFR-02 ⚖️ 資產配置 | ⚖️（機制屬 ⚙️） | 重新讀持倉 facts 與目標 | — | §1 E7 | 「重新取數」不畫（ALO-GAP 登記） | BL-0452 | CAP-RFR-00、CAP-HLD-02 | 4 | CAP-GATE-08 | 只重讀；目標輸入（ALO-1）不得被刷新清掉 |
| CAP-RFR-03 💼 我的持股 | 💼（機制屬 ⚙️） | 失敗列旁「重試」 | 見 CAP-HLD-04 | §1 F4 | 部分塊有、核心卡與 HLD-8 正式模式依裁示不放 | BL-0452、BL-0390 | CAP-RFR-00 | 3／4 | **CAP-GATE-08** | 與 G6、2026-09-23 裁示衝突，待客戶裁示 |
| CAP-RFR-04 🔍 找基金 | 🔍（機制屬 ⚙️） | 查詢失敗時「重試」；候選池「重新載入」 | 見 CAP-FND-05、CAP-FND-06 | §1 A1、C1 | 模板那枚「重新取數」本頁不掛（`E-22` 登記） | BL-0452、BL-0397、BL-0400 | CAP-RFR-00 | 2（頁內 Retry）／4 | CAP-GATE-08 | 只重查同一關鍵字／重讀池 |
| CAP-RFR-05 ⚙️ 設定 | ⚙️ | SET-5「重新取數」；Sheet 狀態「重新載入」 | SET-5（市場指標與淨值兩層；只宣告寫 `fetch_log`） | §1 F2、F4 | 有 SET-5 | BL-0452、BL-0184、BL-0391 | — | 1（Sheet 狀態）／4 | — | 設定值本身不因刷新改變 |

**五頁 Refresh／Retry 驗收表**

| Capability | Acceptance criteria | Success state | Failure state | Missing / Unknown state | Refresh / Retry behavior |
|---|---|---|---|---|---|
| CAP-RFR-00 | 五頁呼叫同一機制；一頁刷新不得無聲清掉他頁快取（BL-0290 先處理或明示副作用）；有次數或冷卻保護（BL-0184） | 本頁資料更新＋freshness 時間更新 | 失敗＋原文；保留上一份有效資料並標舊資料日期 | 無法判定（灰） | Retry 只在失敗／無法判定時出現；冷卻中停用並寫剩餘秒數 |
| CAP-RFR-01 | 只刷新 `market_indicator`；顯示資料日期 | 同上 | 同上 | 同上 | 同上 |
| CAP-RFR-02 | 只重讀持倉 facts；目標與分組定義不變 | 同上 | 同上 | 同上 | 同上 |
| CAP-RFR-03 | 不違反現行裁示（G6、2026-09-23）直到客戶另裁 | 同上 | 同上 | 同上 | 同上 |
| CAP-RFR-04 | 不清空輸入框與觀察清單 | 同上 | 同上 | 同上 | 同上 |
| CAP-RFR-05 | 刷新不改任何設定值 | 同上 | 同上 | 同上 | 同上 |

### §6.7 實作順序（規劃記錄，不授權動工）

1. ⚙️ 設定／Google／Sheet 連線（CAP-SET-01～13）
2. 🔍 找基金（CAP-FND-01～07）
3. 💼 持股管理（CAP-HLD-01～05）
4. 五頁 Refresh／Retry 一致化（CAP-RFR-00～05）
5. 視覺打磨（Visual polish）

- 這是客戶 2026-10-25 指定的先後（要點轉述）；**排序不是授權**，每一階段開工前仍須：客戶指派（`CLAUDE.md` §-1）、對應 Decision Gate 裁示、版面類變更先出 UI 線框草稿並經客戶核准（UI 草稿先行）、G8 解除或客戶另行核准。
- 與 BL-0435 Blueprint 路徑（底層邏輯收斂 → Blueprint → 客戶確認 → 新版實作）併讀：本順序是 Blueprint 內各能力的施工先後，不跳過 Blueprint 的客戶確認。
- 候選的第一個動作（未授權）：第 1 階段 ⚙️ 設定的 UI 線框草稿＋CAP-GATE-01／02 請示單（附總管推薦方案），送客戶核准。

### §6.8 Decision Gates（本節發現；裁示前一律照現況，不動工）

| ID | 題目 | 為什麼要停 | 牽動 |
|---|---|---|---|
| CAP-GATE-01 | Google 個人授權（OAuth）是否進 B 版、scope 多大、權杖存哪裡 | 授權範圍與資安；BL-0349 護欄 4 明文目前不授權改 OAuth scope／Q10／T6／production write architecture；須資安 2 組稽核（`PROJECT_RULES.md` 第 8 節） | CAP-SET-01～05 |
| CAP-GATE-02 | Sheet 綁定紀錄的資料模型（存哪裡、可否多本、預設本） | 產品方向＋可能新增設定鍵或 schema；BL-0381 七步流程與 BL-0392 待裁 | CAP-SET-04、06～10 |
| CAP-GATE-03 | 刪除 Sheet 檔／分頁／資料；新建整本試算表 | 不可逆或寫入使用者 Drive；v1.0 Gate「無法證明安全的資料／歷史成果刪除」 | CAP-SET-09、11；CAP-FND-04（若為刪列） |
| CAP-GATE-04 | B 版是否開放寫入（持倉操作、寫選股池） | 持倉操作與客戶 2026-09-21／2026-10-13「保單／帳本改由 Sheets 維護，B 線只讀取」裁示衝突，投資語意須獨立稽核，寫入紀錄去向牽動 BL-0405 `_Ledgers`；寫選股池屬寫入邊界（BL-0349），是否在上述裁示射程內待客戶確認（原裁示只涵蓋保單與帳本；44 `READONLY_TABLES` 為 holding／policy／nav／dividend） | CAP-HLD-03；CAP-FND-03、04 |
| CAP-GATE-05 | 「候選池」是選股池（`_fund_pool`）還是觀察清單（`exp_watchlist`），或兩者合一 | 兩份並存；再造一份即違 SSOT 去重（64 §4） | CAP-FND-03～05 |
| CAP-GATE-06 | 名稱搜尋涵蓋：境內基金是否納入；是否啟用 UI 0 caller 的 `search_moneydj_by_name`／`search_fundclear` | 客戶要求不新增來源；啟用從未上線的取數路徑是否算新 production 來源路徑，需客戶判定 | CAP-FND-02 |
| CAP-GATE-07 | 代碼直查可否查選股池以外的代碼 | 本檔 §1 A1 原列「需客戶裁示（池外查詢範圍）」；客戶 2026-10-25 要點「不需理解候選池」傾向可查，正式範圍隨 UI 草稿確認 | CAP-FND-01 |
| CAP-GATE-08 | 五頁都要有 Refresh／Retry vs 現行裁示（G6：HLD-8 正式模式不放；2026-09-23：hld 三張核心卡不掛；exp `E-22`、alo ALO-GAP 不畫） | 正式規格明定部分塊不放；改動須客戶裁示並走 44 修正程序（含 G7 條文衝突，BL-0390） | CAP-RFR-02～04、CAP-HLD-04 |
| CAP-GATE-09 | 各能力的版面位置、元件、分頁動線 | UI 草稿先行；G8 未解除；BL-0435 Blueprint 決定 | 本節各能力 |
| CAP-GATE-10 | ⚙️ 要加更多能力 vs 客戶已判「設定與診斷過度複雜」 | 本檔 §1 F2 已標 [方向衝突]；BL-0391／BL-0408 | CAP-SET-13 |

- 本節**未發現**需要改投資語意、公式、門檻或新資料來源才能成立的能力；CAP-GATE-04（投資語意）與 CAP-GATE-06（來源）是「若要做就會碰到」的停點，不是本節的建議。

### §6.9 對應 BACKLOG（本批更新；登記不構成動工授權）

| BL | 本節能力 | 本批動作 |
|---|---|---|
| BL-0402 | CAP-SET-01～13 | 列尾補記（範圍、指標、順位第 1） |
| BL-0397 | CAP-FND-01、02、06、07 | 列尾補記（順位第 2） |
| BL-0400 | CAP-FND-03～05 | 列尾補記（順位第 2；CAP-GATE-05） |
| BL-0403 | CAP-HLD-01～05 | 列尾補記（順位第 3；投資語意照原文） |
| BL-0405 | CAP-SET-11、CAP-HLD-03 的紀錄去向 | 列尾補記（刪除只定義、不排程） |
| BL-0435 | 全節 | 列尾補記（本節為 Blueprint 輸入，不是平行規格） |
| BL-0351 | CAP-RFR-00 | 列尾補記（交叉 BL-0452） |
| **BL-0452（新增）** | CAP-RFR-00～05 | 五頁 Refresh／Retry 一致化（順位第 4）；去重理由見該列 |

### §6.10 本節沒查證的部分

1. 未起 Streamlit、未看畫面、未跑任何 UI；Current B UI state 為 `7d41705f` 讀碼，Old UI reference 轉錄自本檔 §1～§4（`d2cd3bb`），未重讀舊 UI。
2. §6.1 第 2 點的錯誤分類只讀了設定試算表 L1 與持倉 L1 的函式簽名／docstring；「認證失敗 vs 無權限」「URL 格式驗證」未實測。
3. `tdcc_search_fund` 是否涵蓋境內基金、`search_moneydj_by_name`／`search_fundclear` 是否仍可用，未實測。
4. `docs/v2/44_fund_ui_ssot.md` 未逐行讀；§6.5「未見更高位階規格把 Sheet 選擇放在 💼」為文件組在 DECISIONS／62／64 範圍內的判讀，不宣稱窮舉。
5. 能力切分、Owner 指派、Decision Gate 歸納由文件組單組依總管規格寫成，未經第二組驗證。
