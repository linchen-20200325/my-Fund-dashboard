# 63｜市場趨勢研究基線與舊 UI 架構稽核保存版（2026-10-22 交接防遺失保存批）

> ⛔ **狀態：Research Baseline ／ NOT APPROVED SPEC ／ 不得直接作為實作授權。**
> 本檔是 Decision Gate 前的**輸入**，不是規格、不是核准；本檔內任何「建議」一律是**總管建議，不是客戶核准**。

- **建立日**：2026-10-22。**量測 SHA**：`b149873`（＝ `origin/main`，PR #1020 合併後）。本檔內的數字一律以量測日 2026-10-22、SHA `b149873` 為準，會漂移，引用前請現場重量。
- **位階**：受 `CLAUDE.md` §-2 ＋ §-1.5 ＋ §-1 與 `PROJECT_RULES.md` 管轄；**不凌駕** `docs/v2/44_fund_ui_ssot.md`，也不凌駕子法 1（併讀 `docs/v2/57`）；不改任何畫面規則。
- **與 Decision Gate 的關係**：與 `docs/DECISIONS.md` `DEC-2026-10-22-02` G8（暫不核准任何 UI 改版）併讀——**本檔不解除 G8**。本檔 §4.4 的 G-A～G-S 全部**未裁示**。
- **決策登記**：`docs/DECISIONS.md` `DEC-2026-10-22-04`（B 版設計原則）＋ `DEC-2026-10-22-05`（本批：新版產品方向與市場趨勢研究原則）。**待辦登記**：`docs/BACKLOG.md` BL-0415～BL-0419（登記不構成動工授權、也不構成 UI 改版核准）。
- **誰寫、誰驗過**：§3～§4 的事實來自 2026-10-22 八組平行讀碼（舊 UI 架構唯讀稽核）＋總管複驗九條承重宣稱；§1～§2 與 §5～§6 由總管依客戶 2026-10-22 指示整理為規格；本檔由文件組照總管規格落盤，**文件組未重跑任何掃描指令、未重讀任何原始碼**；八組**皆未實跑任何 UI**（未起 Streamlit、未打外網、未讀任何 Sheet）。完整長報告只存在於當日對話，本檔是**保存版**；**落盤後另派獨立稽核**。
- **客戶指示的出處**：客戶 2026-10-22 指示經總管派工單轉達；**repo 內無逐字存檔**；文件組未見客戶對話本身。
- **體例**：繁體中文；舊條文不刪、狀態更新加「狀態更新，不是漏刪」；程式位置寫「檔案::符號」，不寫行號（行號在重構後失效）；不寫任何 secret 值；**不出現任何真實人名**——客戶提供的投資教學參考資料一律稱「客戶提供的投資教學參考資料」。

- **2026-10-23 狀態更新（不是漏刪；決策者：客戶，`DEC-2026-10-23-01`；方向文件 `docs/v2/64_v2_ssot_convergence.md`）**：移除台股專屬趨勢研究軸（融資、外資籌碼、週 KD、台股 EPS×PE、台股盈餘預估），不作全球趨勢核心、也不作獨立主面板；EPS×PE 不再是新版市場主軸；台灣只作一般 region exposure。本檔 §2 的「台股趨勢方法」與中性名清單中的「台股趨勢」「籌碼狀態」已就地劃線保留；「估值情境」原文本無「台股」限定，故不劃線，改就地註明不含台股專屬 EPS×PE。資訊擁有權與 SSOT 收斂方向以 64 為準；本檔其餘內容仍是 Research Baseline、未核准。

---

## §1 新版產品方向（客戶 2026-10-22 已確認；出處 `DEC-2026-10-22-04` ＋ 本批 `DEC-2026-10-22-05`）

- **新版不是從零重寫**：舊 UI 經驗證的投資邏輯優先評估**重用／重構／退休**（§4），舊畫面不直接移植。
- **五頁產品方向**：🌍 市場與趨勢 → ⚖️ 資產配置 → 💼 我的持股 → 🔍 找基金 → ⚙️ 設定。
- **投資閉環**：市場趨勢 → 配置 → 持股 → 找基金 → 調整（新投入／轉換／贖回）→ 保存真實事件歷史 → 日後覆盤「當初的決策是否較好」。
- **永久資料原則**：
  1. 資料層 ≠ AI 推理層。
  2. missing 不補 0、不補中性、不補 HOLD。
  3. 舊資料不冒充最新。
  4. AI 不補交易事實、NAV、FX、配息、持股。
  5. 不只用顏色傳狀態。
  6. 資料不足時顯示「⬜ 資料未取得／無法判定」。
  - 註：(1)(2) 已登記於 `DEC-2026-10-22-05`；(3)～(6) 出自客戶 2026-10-22 唯讀稽核指示第 4 節，經總管派工單轉述、repo 內無逐字存檔、尚未單獨登記為 DEC，引用時以此身分引用。

---

## §2 市場趨勢研究必須分三層（研究原則；客戶已確認的部分見 `DEC-2026-10-22-05`）

**三層**：
1. ~~**台股趨勢方法**~~（2026-10-23 移除，狀態更新，不是漏刪）；
2. **國際市場趨勢方法**；
3. **Repo 自有補充風控**。

**規則**：
- 不得預設 `services/macro/us_indicators.py::calc_macro_phase`、`services/macro/composite_score.py::calculate_composite_score`、`services/risk_radar.py` 或其他既有 regime 引擎就是新版 SSOT（§3 只登記事實，不選用）。
- 客戶提供的投資教學參考資料只能作「**研究來源**」。
- 正式產品的 UI、卡片、功能名稱、指標名稱、Tooltip、通知、AI 文案**不得出現資料作者或老師姓名**；正式產品只用**中性名稱**：~~台股趨勢~~、國際市場趨勢、市場環境、估值情境（2026-10-23 起只指一般／全球估值情境，不含台股專屬 EPS×PE）、景氣趨勢、利率環境、~~籌碼狀態~~、市場風險（2026-10-23 劃線，狀態更新，不是漏刪：台股專屬趨勢軸已移除，見檔頭 2026-10-23 狀態更新）。
- 參考資料的方法與 Repo 自有補充風控**不得混稱為同一套原始方法**。
- ~~EPS × PE 只視為待驗證的「**台股估值情境之一**」，不得升格為整個市場趨勢公式。~~（2026-10-23 狀態更新，不是漏刪：EPS × PE 不再是新版市場主軸，見檔頭 2026-10-23 狀態更新）
- 新公式、權重、門檻、新來源**一律 Decision Gate**（`PROJECT_RULES.md` 第 4 節）。

---

## §3 Repo 現有趨勢引擎盤點（只登記事實，不選用；量測 SHA `b149873`，單組讀碼）

- **regime 定義至少五套並存**：`services/macro/us_indicators.py` 內的 `calc_macro_phase`、`get_market_phase`、`identify_regime`、`calc_growth_inflation_axis`、`calc_macro_phase_zpct`；另有 `services/macro/tw_local.py::classify_long_term_regime`。
- **配置真相三套**：`shared/signal_thresholds.py::ALLOCATION_LADDER`；`calc_macro_phase` 內嵌 alloc；`identify_regime` 的 alloc_by_regime。
- `calculate_composite_score` **缺指標當 0**（檔內自承違 `CLAUDE.md` §1）。
- **可重用零件**：`EvidenceSupport`（`shared/evidence_support.py` ＋ `services/macro/evidence.py`）；`reconcile_composite_score`（UI 0 消費者，單組讀碼）；`services/risk_radar.py` 10 燈；`services/liquidity_engine.py` 4 因子。
- **沒有的東西**：無「情境」物件；無產業／區域級資料源；無「上次判讀」持久化；總經層無 confidence／conflict 物件。

---

## §4 舊 UI 唯讀架構稽核 durable summary（2026-10-22）

> 八組平行讀碼＋總管複驗，**未實跑 UI、未打外網、未讀 Sheet**；完整長報告只存在於當日對話，本節是保存版。各小節的「建議」「退休」皆為**總管建議，不是客戶核准**。

### 4.1 可直接重用（已驗證的投資邏輯與骨架）

- 取數 waterfall 與快取／退避骨架：`infra/proxy.py::fetch_url`、`infra/source_backoff.py`。
- `services/fund_service.py::calc_metrics`／`finalize_fund_metrics`。
- 三組 reconciliation：`services/reconcile.py`。
- Sharpe／Sortino／Calmar／MaxDD／3Y5Y。
- 1Y 含息：`calculate_fund_total_return`（再投資口徑）。
- `services/fund_row.py::process_one_fund`。
- `ui/helpers/fund_grp_health/unified.py::BATCH_UNIFIED_COLUMNS` 中的核心欄。
- `services/precision_service.py::calc_hwm_sigma_levels`。
- 相關性／重疊矩陣：`services/portfolio_service.py`。
- `services/capture_ratio.py`。
- `services/health/grade.py::compute_4d_health`。
- 批次 checkpoint／續跑：`repositories/batch_checkpoint.py`。
- `repositories/pool_repository.py`。
- `services/nav_history_store.py`／`services/nav_history_gs.py`。
- `services/ledger_service.py::Ledger.subscribe`／`Switch`／`calculate_xirr`。
- `services/currency.py::normalize_ccy`。
- `services/risk_radar.py` ＋ `services/liquidity_engine.py`。
- `EvidenceSupport`。
- B 版 NAV 10 天規則：`ui_v2/thresholds.py::NAV_NOT_READY_DAYS`。
- B 版整頁失敗畫面。

### 4.2 可安全補強（內部自決，仍須派工與稽核；G1 重驗前不開 PR）

- B 版代碼輸入框與名稱搜尋接線（草稿先行）。
- EXP-3 接 `process_one_fund`。
- MA／布林改吃 L2。
- 投資試算下沉 L2（`ui/tab2_single_fund.py` 與 `ui/views/page_03_research.py` 兩份合一）。
- B 投入再平衡分配公式（`ui/tab3_t7_ledger.py` 內算）下沉 L2。
- reconcile 容差、checkup 門檻（`ui/helpers/fund/checkup.py`）、集中度門檻（`ui/helpers/portfolio/concentration.py`）SSOT 化。
- 矩陣與 cnyes／Morningstar 持股補 `data_date`。
- `services/v2_tables/contract.py::_ccy_problem` 前接 `normalize_ccy`（BL-0413 A2 改凍結規格，須裁示）。
- 三本 Sheet 名稱顯示。
- 持倉最後讀回時間。
- `repositories/fund/fund_orchestration.py` 的 `_FUND_SNAPSHOT` 與 `infra/cache.py::_cache_load_nav` 補 `is_stale` ＋ 原 as-of。
- `repositories/fund/sources.py::_tdcc_cache` 加 TTL。
- cnyes／TDCC／Morningstar 直打改經 `fetch_url` 接冷卻。
- `repositories/macro_tw_local_repository.py` 四支加 `cache_if`。
- `repositories/fund/fx_and_main.py::get_latest_fx` 回傳補觀測日。
- 設定頁「進階」分層。
- 四處文件更正（見 §4.5）。

### 4.3 建議退休（總管建議；不構成刪除授權；實體刪除依 BL-0292 九道閘門）

- 編輯持倉 UI／自動估算／`repositories/ledger_repository.py::replace_ledgers_for_policy` 覆寫路徑。
- `ui/helpers/cloud_io.py` 的「📦 全部寫入／讀回」路徑。
- v1→v2 遷移工具不接入 B。
- `ui/tab3_t7_ledger.py` 的 `_FX_FALLBACK`。
- `models/ledger.py::FundPosition.currency` 預設 USD。
- 79 欄中的死欄（幣別偵測／基金屬性／操作訊號）與重複欄。
- `_render_333_fund_expander`。
- `services/fund_history.py`。
- `repositories/fund/nav_metrics.py::fetch_nav_history_long`（production 0 caller，單組讀碼）。
- 舊決策矩陣／買賣四價（`DEC-2026-10-19-01` 已裁退役）。
- sidebar Proxy／GitHub 同步。
- `config/preset_funds.json` 若與池合併。

### 4.4 Decision Gates G-A～G-S（**全部未裁示**；「總管建議」欄只是建議，不是客戶核准）

| Gate | 問題 | 總管建議（不是核准） | 本批加註 |
|---|---|---|---|
| G-A | regime／phase SSOT（五套擇一） | 以 `calc_macro_phase` ＋ `EvidenceSupport` 為單一真相源 | **暫不得裁示**，待趨勢方法專項對齊（BL-0415）完成 |
| G-B | 配置真相 SSOT（三套擇一；`allocation_from_composite` 是否進 B 版） | 收斂 `ALLOCATION_LADDER`，B 版 v1 只顯示對照 | **暫不得裁示**，同上 |
| G-C | 「未來 1–3 月情境」定義；Signal Conflict Index 公式 | 先重用拐點規則 ＋ `EvidenceSupport`，Index 進 Phase 7 | **暫不得裁示**，同上 |
| G-D | 「上次→現在」判讀快照表（新 data identity） | append-only 判讀快照放設定試算表 | — |
| G-E | 產業／區域趨勢新來源 | 本階段不接，列 Phase 6 | — |
| G-F | A→B 費用／NCV／實際淨額是否入帳；`_Ledgers` 擴欄（`txn_type`／`fx_rate`／`fee_orig`）；禁覆寫 | 入帳、擴欄、停用 `replace_ledgers_for_policy` | — |
| G-G | 配息口徑：落袋 vs 再投資分離；配息事件來源 | 損益分三欄（市值／累積現金配息／總損益），配息事件由使用者在 Sheets 登記 | — |
| G-H | 贖回事件型別（`models/ledger.py::_TXN_TYPES` 五種無 redeem） | 新增 `redeem`，B 版 v1 不提供 UI | — |
| G-I | 現金部位 schema（Cash Parking）＋ ALO-3 情境形狀（現封閉為 `{bucket, amount_twd}`） | 新 cash_position 四欄（幣別、金額、as-of、是否計入分母） | — |
| G-J | `holding` 加 `fx_avg`（44 §4.1 無此欄）；`_持倉補充` 去留；級別 vs 類別（BL-0414） | 保留 `_持倉補充`、加 `fx_avg`、級別不當類別來源 | — |
| G-K | 持股 as-of 降權機制與門檻 | 以 `data_date` 為準、缺 as-of 一律 ⬜ 不進曝險 | — |
| G-L | Global Frozen：哪些核心資料 stale 要凍結哪些衍生判讀 | NAV／FX／macro 各一門檻，凍結時資料可看、判讀卡顯示「⬜ 判讀暫停」 | — |
| G-M | Fund identity 主鍵與 corporate action 事件模型 | 公開碼 ＋ ISIN 錨定、新 `fund_identity_event`（old／new／event_type／effective_date／unit_ratio／source）、`txn_type=corporate_action` | — |
| G-N | 多檔比較欄集合、批次上限、期間選擇（BL-0399） | — | — |
| G-O | B 版寫池／池外代碼範圍（BL-0349／BL-0397）；Action Hand-off 的 44 新增鍵 | 只傳 fund_code，金額單位數一律 Sheets 手填 | — |
| G-P | 找標的衍生篩選語意（C2）、持倉體檢「汰弱」判定 | — | — |
| G-Q | 設定頁深度（BL-0391／BL-0408）、通知形式、三本 Sheet 切換（BL-0392） | — | — |
| G-R | `calculate_composite_score` 缺指標當 0 | 改 ⬜ 並降權重分母（投資語意，須裁示） | — |
| G-S | 390px：EXP-1 規則行、EXP-2 表格、HLD-1 表示法（layout） | 依 59 草稿先行，與 BL-0386／BL-0387 同批 | — |

### 4.5 已發現的四項文件／實碼不一致（只登記，本批不改；→ BL-0417）

1. `CLAUDE.md` §2.1／§4.6 寫 NAV fallback「yp010000 → yp010001 → TDCC → FundClear → Cnyes」；實碼 `repositories/fund/fund_orchestration.py::_fetch_fund_single` 為 0 安聯官網 → 2a FundClear → 2b Cnyes → 2c TCB MoneyDJ → 2c2 保險子網域 → 2d www.moneydj（頁型互換）→ 2e SITCA → 2f → 2f2 → 2g Morningstar → 2g2 Yahoo → 2g3 AlphaVantage → 2h → 2i；`get_page_types_to_try` 只是 yp 頁型互換；TDCC 只供 meta、不是 NAV 來源。
2. `CLAUDE.md` §2.4 月頻 45／75 天；實碼 `ui/helpers/io/data_registry.py::_freshness` 為 60／90。
3. `docs/v2/62` F1「34→4」；實碼 `EXPECTED_INDICATOR_KEYS` 為 28 鍵、`shared/fred_series.py` 常數 41，34 的出處未能重現。
4. 持股 as-of 只有 MoneyDJ 路徑寫 `data_date`（月粒度）；`repositories/fund/sources.py::fetch_holdings_cnyes`／`fetch_holdings_morningstar` 函式體未寫（docstring 宣稱有）。

### 4.6 11 項防禦主要缺口（逐項保留，不得合併或省略）

1. **A→B**：`Switch._do_switch` 轉出以市值算、成本守恆；**無 NCV 欄、`fee_orig` 欄 UI 硬編 0、cross_rate 由兩個即時 FX 相除未記來源時間、實際淨額只在 DTO 未落 `_Ledgers`**。
2. **配息**：`Ledger.dividend_cash`／`dividend_reinvest` **production 0 caller**（總管複驗）；損益不含已領配息；1Y 含息全程假設再投資；`div_cash_pct` 預設 100 與之方向相反。
3. **持股 as-of**：**cnyes／Morningstar holdings 缺可靠 as-of**、無 confidence 降權、`lookthrough_coverage` 以抓取時間判 stale。
4. **Core Pool**：池＝`_fund_pool` ＋ 每日 cron 預抓持倉 ∪ 池；Dynamic Fetch 鏈已存在；只有走 `fetch_url` 的來源有跨呼叫冷卻。
5. **Cash Parking 無資料模型**（`holding_row_problems` 要求 fund_code／units>0／cost>0）。
6. **Hand-off**：`exp_watchlist` 已示範只存 fund_code。
7. **Signal Conflict**：總經層無 confidence／conflict 物件。
8. **無 Global Frozen**（總管複驗）；FX 回純 float 無觀測日；phase／composite 無年齡閘門。
9. **fund corporate action 無 identity／event model**（identity ＝ 裸 MoneyDJ 代碼 ＋ 靜態別名；`_TXN_TYPES` 無法容納行政折算）。
10. **降級**：`_FUND_SNAPSHOT` 回填只有 warning 無 `is_stale`；`_cache_load_nav` 不帶 attrs；`_tdcc_cache` 無 TTL；**composite score 缺值當 0**。
11. **390px**：EXP-1 規則行四欄堆疊、EXP-2 內捲、SET 中文斷字（BL-0387）、`page.py` 不傳 viewport_width。

### 4.7 持倉資料架構

- **`_Ledgers` 不是可靠 append-only event history**：`replace_ledgers_for_policy` 可整單覆寫成一筆合成起始；`Ledger.from_dict` 不重播；唯一 production 讀者只取 len（單組讀碼）；fee 恆 0；`twd` 欄同欄異義；無 dividend 列。
- `_持倉補充` 三欄中 `last_synced_at`／`bucket` 無其他來源，仍有存在必要。
- B 版 `holding` 無 `fx_avg`。
- B 版 `_ccy_problem` 不轉碼（BL-0413）。

### 4.8 原則

舊 UI 成熟投資邏輯**不得因新版重設計而無聲消失**（`DEC-2026-10-22-04`）。

---

## §5 建議實作順序（總管建議，非核准；任一步皆須各自的 Decision Gate 與派工）

1. G1 收尾前置（BL-0413／BL-0414／BL-0411）。
2. 文件更正批（§4.5；BL-0417）。
3. 資料層補強批（§4.2；不動 UI、不改語意；BL-0418）。
4. Decision Gate schema 批（G-F／G-G／G-H／G-I／G-J／G-M）。
5. 🔍 找基金。
6. 💼 我的持股。
7. ⚖️ 資產配置。
8. 🌍 市場與趨勢（待 G-A／G-B 收斂）。
9. 防禦 8／7／方向性依 Phase 7。
10. 390px layout（G-S）。

---

## §6 下一個唯一接手點

**不是**實作新版 UI、**不是**裁 G-A～G-S。先執行「客戶提供市場趨勢參考資料 × Repo 現有趨勢引擎」**唯讀對齊稽核**（BL-0415），完成後再回到 G-A～G-S Decision Gate。

---

## §7 本檔誰寫、誰驗、沒查證的部分

- §3～§4 的事實：八組單組讀碼；總管複驗了九條承重宣稱（§4.6 標「總管複驗」者）；其餘「0 caller」「只有」「無」類全稱句皆為單組讀碼，未經第二組驗證。
- 本檔由文件組照總管規格落盤；文件組未重跑任何掃描指令、未重讀任何原始碼、未實跑 UI。
- 客戶 2026-10-22 指示 repo 內無逐字存檔；§1～§2 的「客戶已確認」範圍以 `DEC-2026-10-22-05` 的摘要欄為準，本檔不另作詮釋。
- §4.4 的「總管建議」與 §5 的順序＝總管讀法，可被客戶推翻。
- 落盤後另派獨立稽核。
