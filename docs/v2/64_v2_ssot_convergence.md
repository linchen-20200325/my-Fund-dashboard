# 64｜新版 SSOT 收斂方向與資訊擁有權（2026-10-23）

> ⛔ **狀態：客戶確認方向（2026-10-23）／不是實作規格、不授權 production 實作、不解凍 `docs/v2/44_fund_ui_ssot.md`。**
> 本檔任何「建議」「候選」一律是總管建議，不是客戶核准；研究候選不得寫成已核准公式或門檻。

- **建立日**：2026-10-23。**量測 SHA**：`bde2468`（＝ `origin/main`，PR #1021 合併後）。本檔的程式位置與事實以此 SHA 為準，會漂移，引用前請現場重量。
- **位階**：受 `CLAUDE.md` §-2 ＋ §-1.5 ＋ §-1 與 `PROJECT_RULES.md` 管轄；不凌駕 `docs/v2/44`、子法 1（併讀 `docs/v2/57`）；不改任何畫面規則；與 `DEC-2026-10-22-02` G8 併讀——本檔不解除 G8。
- **決策登記**：`docs/DECISIONS.md` `DEC-2026-10-23-01`。**待辦登記**：`docs/BACKLOG.md` BL-0420～BL-0423（登記不構成動工授權）。
- **與 62／63 的關係**：補強 `docs/v2/62_old_ui_gap_matrix.md` 與 `docs/v2/63_market_trend_research_baseline.md`，不取代；63 的台股專屬趨勢研究軸已於本批移除（見 63 的 2026-10-23 狀態更新）。
- **誰寫、誰驗過**：見 §8。
- **體例**：繁體中文；程式位置寫「檔案::符號」，不寫行號；不出現任何真實人名——客戶提供的投資教學參考資料一律稱「客戶提供的投資教學參考資料」。

---

## §1 正式方向（客戶 2026-10-23 確認）

- **流程**：新研究邏輯 ＋ 舊 UI 已驗證精華 → 去重 → 唯一 SSOT → 重新設計五頁。
- **五頁**：🌍 市場與趨勢／⚖️ 資產配置／💼 我的持股／🔍 找基金／⚙️ 設定。「今天」這個頁名不使用。
- **一項資訊一個完整主頁**：其他頁只引用摘要、status、必要數字與 drill-down，不另做一份完整版本。
- 本節只確認方向；各項的公式、門檻、版面仍各自走 Decision Gate（`PROJECT_RULES.md` 第 4 節）。

## §2 Information Ownership Matrix

| 資訊 | 唯一主頁 | 他頁允許 | 禁止重複 |
|---|---|---|---|
| 全球景氣、Fed／貨幣政策、利率／信用／流動性、企業獲利／估值、長期產業資本循環、資產環境、市場風險補充區（長週期與短線分層呈現） | 🌍 市場與趨勢 | ⚖️ 引用 🌍 的 evidence 摘要 | composite 單一總分；以舊 regime／verdict 作 SSOT；建議資產水位；台股專屬趨勢軸；投資動作。台灣只作一般 region exposure |
| 基金位置（NAV trend、MA、Bollinger、HWM σ rank） | 🔍 找基金 | 💼 只讀同一 L2 SSOT 顯示位置 status、必要數字、drill-down | 他頁重算位置；完整投資動作語意 |
| 基金健康（4D、3-3-3、Sharpe、Sortino、Calmar、MDD、Total Return、Benchmark、Capture、Peer） | 🔍 找基金 | 💼 只顯示 Grade、必要數字、drill-down | 他頁重算健康 |
| 配息（ADR、吃本金、配息事件、配息品質） | 🔍 找基金 | 💼 只顯示吃本金 status 與必要數字 | 他頁另一套配息率分母 |
| 曝險（holdings、industry、region、overlap、correlation） | 🔍 找基金（單檔層） | ⚖️ 組合層彙整，讀同一份曝險資料 | ⚖️ 自行另抓持股 |
| 找基金工具：代碼直查、多檔比較、batch／checkpoint／resume／export、投資試算 | 🔍 找基金 | — | 完整投資動作語意 |
| 保單、成本、單位數、市值、損益、累積實領配息、歷史操作 | 💼 我的持股 | ⚖️ 讀 💼 facts | 💼 重算基金健康或位置 |
| 現況 vs 目標、concentration、correlation、homogeneity、region／asset-class exposure、情境試算、A→B retrospective | ⚖️ 資產配置 | — | ⚖️ 重算市場或基金健康；只組合 🌍 evidence ＋ 💼 facts ＋ 🔍 exposure |
| Google／Sheet 連線、同步、資料來源、freshness、fetch log、通知、NAV history 維護、必要診斷 | ⚙️ 設定 | 他頁只顯示 freshness 標記 | ⚙️ 放分析與選股 |

## §3 HWM σ 正式邊界

- **保留為「基金位置」核心候選**；語意只許「相對自身近一年高點的位置 evidence」。
- **不得**稱買點、賣點、可買、可賣、加碼、減碼。
- `shared/signal_thresholds.py::ROTATION_SELL_SIGMA`（−0.5）與 `shared/signal_thresholds.py::ROTATION_BUY_SIGMA`（−1.5）無 backtest／校準證據，**不視為新版正式門檻**。
- **現況事實（量測 SHA `bde2468`）**：HWM ＝ 最後 252 筆 NAV 的最高值；σ_abs ＝ HWM × std_{ddof=1}(簡單日報酬) × √252（v19.482 起固定 √252）。

### ⛔ Blocking Issue：raw NAV 除息跳空造成低波動月配基金假低基期

- `services/precision_service.py::calc_hwm_sigma_levels` 收**原始 NAV**；repo 既有的 `services/fund_service.py::_total_return_nav` 未接到此路徑。
- 稽核以 production 公式對合成序列實算：NAV 10、每月配 0.08、無雜訊 → σ_rank 約 −3.24（基金本身沒有下跌，卻被讀成深度低基期）。
- **待客戶裁示四題**：(1) total-return NAV 如何進入基金位置；(2) 不同基金類型是否共用方法；(3) 門檻如何驗證；(4) 四級 label vs 三態分類。
- **裁示前 HWM σ 不得成為 production investment judgment。** 本文件不提出修正公式。→ BL-0421。
- → **2026-10-23 狀態指標（狀態更新，不是漏刪；原文不改）**：四題已由客戶裁示 2C（`docs/DECISIONS.md` `DEC-2026-10-23-02`：輸入改用配息還原／Total Return 序列、fail-closed、中性三態、−0.5／−1.5 僅研究候選門檻未校準）；待實作（`docs/BACKLOG.md` BL-0426），落地前本條禁令照舊。

## §4 SSOT 去重原則

**原則**：一個概念 → 一套 deterministic calculation → 一個 SSOT → 多頁引用。`ui_v2/*/logic.py` 不應形成第二套金融計算 SSOT；UI 只 render／compose。

**優先收斂 12 項**（下列重複點為單組實測＋總管抽驗，未經第二組逐條驗證；量測 SHA `bde2468`）：

| # | 概念 | 稽核發現的重複點 |
|---|---|---|
| 1 | Sharpe 的無風險利率 rf | `services/fund_service.py::_RF_ANNUAL` 與 `shared/signal_thresholds.py::FRONTIER_RF_ANNUAL=0.0` 兩值並存 |
| 2 | volatility | 五種算法並存，含 `ui_v2/hld/logic.py::vol_pct`（ddof=0） |
| 3 | MDD | 含息版與純價版並存（純價：`services/portfolio_service.py::compute_max_drawdown`） |
| 4 | 1Y Total Return | 四種定義，經 `services/fund_total_return.py::compute_1y_total_return` 等路徑 |
| 5 | dividend yield／ADR | 四種分母，含 `ui_v2/exp/live.py::dividend_ratio` |
| 6 | HWM／低基期 | 五把尺並存（見 §3） |
| 7 | 3-3-3 | 兩套：`services/health/dividend.py::check_333_principle` 與 `services/fund_screening.py::check_333_fund` |
| 8 | 核心／衛星語意 | 四種意義並存 |
| 9 | allocation % | 三種分母 |
| 10 | freshness | 2／7 天、v2 的 10 天、`ui/helpers/io/data_registry.py` 閉包三套 |
| 11 | benchmark mapping | 只涵蓋 TWD／USD，且 `^GSPC` 與 `SPY` 兩路並存 |
| 12 | market evidence | 見 BL-0415（2026-10-23 已完成唯讀稽核） |

每一項的收斂方式（選哪一套、是否改值）屬投資語意或公式，須逐項請客戶裁示，附總管推薦方案。→ BL-0420。

→ **2026-10-23 狀態指標（狀態更新，不是漏刪；原文不改）**：第 4、5、6、7 項已由客戶裁示 1B／2C／3A（`docs/DECISIONS.md` `DEC-2026-10-23-02`）；1B 已於 PR #1023 落地 main，2C／3A 待實作；其餘各項仍待裁示，§7 的接手點照舊適用於它們。

## §5 舊 UI 三分類（總管建議；本批不刪任何程式）

- **保留／重構**：`calc_metrics`（含還原風險序列與對帳）、`compute_4d_health`（走勢維 `ma_dir` 全站無 producer，待裁）、`check_eating_principal_1y_mk` ＋ ADR 三層、`calc_hwm_sigma_levels`（僅作位置 evidence）、`compute_capture`、overlap／correlation／homogeneity、`process_one_fund`、`batch_checkpoint`、peer PK、`estimate_monthly_income`、Ledger subscribe／switch、`market_indicator` 七鍵紀律、`EvidenceSupport`。
- **退休候選**（不構成刪除授權；實體刪除依 BL-0292 閘門）：composite／verdict／舊 regime 分類器與其鏡像、`get_market_phase`、`calc_macro_phase_zpct`、`tw_local` 三函式、`synthesize_dual_verdict`、`fetch_nav_history_long`、`calc_health_from_manual`、`calc_dividend_estimate`、`risk_alert`、`GhostPortfolio`、`check_333_fund`、UI 層重算布林／MA、T7 `_FX_FALLBACK` 寫死表、鏡像 `_parse_codes`。→ BL-0422。
- **Decision Gate**（不得因舊 UI 存在而自動恢復）：買、賣、加碼、減碼、停扣、Switch、Cash Parking、自動再平衡、推薦標的。

## §6 資料 ≠ AI：永久資料流

Raw → Validated／Normalized → Deterministic → Evidence → AI Explanation → Portfolio Impact。

- AI 只解釋 Evidence，不產生數字。
- missing 永遠顯示「⬜ 資料未備／無法判定」，不得變成 0、中性、正常、安全、HOLD 或未觸發。

## §7 下一唯一 handoff point

「依本文件 §4 優先收斂清單與 §3 Blocking Issue，逐項提出 SSOT 規格裁示請求（每項附總管推薦方案），客戶裁示前不進 production 實作」

→ **2026-10-23 狀態指標（狀態更新，不是漏刪；原文不改）**：BL-0428 行動類規則唯讀盤點已完成，見 §9；待客戶裁示 §9.7 的 DG-1～DG-5，裁示前照舊。

## §8 出處與沒查證的部分

- 唯讀稽核 2026-10-22／23，五組 agent ＋ 總管抽驗，量測 SHA `bde2468`；未改 code、未實跑 UI。
- 客戶 2026-10-23 裁示經總管派工單轉達；repo 內無逐字存檔；文件組未見客戶對話本身。
- 本檔由架構與文件組依總管規格落盤；§3 的 −3.24 合成序列實算、§4 的重複點、§5 的分類皆為稽核組結論，**文件組未重跑、未重讀原始碼**；單組實測＋總管抽驗，未經第二組逐條驗證。

## §9 BL-0428 行動類規則唯讀盤點（2026-10-23，main 365cfb1d）

> ⛔ **狀態：唯讀盤點紀錄，不是實作規格、不授權任何程式修改。** 下方「建議」欄一律是總管建議（保留／修改／退休），不是客戶核准；行動類規則、Missing 落點、門檻的處置一律等 §9.7 Decision Gate 裁示（`docs/BACKLOG.md` BL-0428）。本節不新增 DEC。
> 量測 SHA：`365cfb1d`（＝ 盤點當時的 main）。程式位置寫「檔案::符號」，不寫行號；位置會漂移，引用前請現場重查。

### §9.1 方法與「兩組／單組」標記

- 兩組獨立唯讀調查，互不參照：**A 組**（consumer-first：從讀 σ 的消費端逐條往上看規則）、**B 組**（call-graph-first：從 `services/fund_position.py::compute_fund_position` 往外追呼叫圖，另找不經 SSOT 的 raw NAV 位置→買賣實作）。兩組皆在 `365cfb1d` 上唯讀，未改檔、未 commit。
- 下表「發現」欄：**兩組**＝A、B 各自獨立找到同一條（兩雙眼睛）；**單組 A**／**單組 B**＝只有一組找到，未經第二組驗證，只能當待驗事項（`CLAUDE.md` §-2 規則 6）。同一列內若某一細節只有一組寫到，在該格內以「（A）」「（B）」標出。
- 兩組各自標了讀碼／實跑／推論；本節沿用其最弱的一級。**SSOT 本身**：`compute_fund_position`／`compute_fund_positions_at` → `services/precision_service.py::calc_hwm_sigma_levels` → 三態經 `services/rotation.py::classify_base`（切點 `shared/signal_thresholds.py::ROTATION_SELL_SIGMA` −0.5、`ROTATION_BUY_SIGMA` −1.5，`thresholds.calibrated=False`）；⬜ 時 `status="unavailable"`、`position=None`、`sigma_rank=None`，另帶 `error` 鍵讓下游 `"error" in` 慣例生效（兩組）。
- 不宣稱窮舉：兩組的搜尋方法（字面搜尋、AST 鍵讀取掃描）抓不到動態鍵名與經 DataFrame 換名的傳遞。

### §9.2 合併表（一列一條規則／consumer；A、B 去重）

| # | 發現 | consumer／function | 頁面／功能 | 輸入 | SSOT | 現行 threshold | 接近高點 | 中段 | 遠離高點 | ⬜ Missing | Missing 被當中性／安全／HOLD／未觸發？ | 輸出文字（摘要） | 行動語意？ | 重複規則 | production 可達性 | 測試 | 風險 | 建議（僅建議） | 需客戶裁示？ |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| R1 | 兩組（A#1＝B N2） | `services/policy_advisor_service.py::recommend_policy` | 舊 Tab④ 資產配置，保單卡「🎯」保單整體建議 | `invest_twd`、`is_core`、`sigma_info`（`ui/tab3_portfolio.py::_hwm_sigma_info_for` → SSOT）、`dividend_info` | 是 | P3 σ ≤ −2.0（inline）、`risk_count_threshold` 預設值 2、核心偏差 ±10.0（inline） | 不計入 P3 | 不計入 P3 | 只有 σ ≤ −2.0 的部分計入 P3；(−2.0, −1.5] 不計 | 不計入 P3 → 可落 P5 `POLICY_HEALTHY` 綠「配置健康」，輸出不提有幾檔 ⬜（兩組實跑） | **是**（安全／未觸發） | P3 紅「深度超跌（σ ≤ -2.0）…可分批加碼但避免單押」；P5 綠「配置健康，持續觀察 60MA 與配息覆蓋率」 | 是（加碼、汰弱換強） | −2.0 與 R2、R3 各自 inline，非具名常數，也不等於 SSOT −1.5 | PRODUCTION | `tests/test_policy_advisor.py`；`tests/test_ssot_2c_fund_position.py::test_downstream_advisor_takes_insufficient_branch` 只斷言不含「深度」，全 ⬜ 時綠燈照樣通過（兩組推論，未實跑該測試） | 高 | 修改 | 是（DG-1、DG-3） |
| R2 | 兩組（A#2＝B N1） | `services/policy_advisor_service.py::advise_fund` | 舊 Tab④ 保單卡逐檔「💡」建議 | `sigma_info`、`dividend_info.alert_level`、`ma60_trend`（UI 以原始 NAV 自算 60MA）、VIX（`VIX_PANIC_THRESHOLD`＝`shared/macro_buckets._VIX_RED`） | 是 | −2.0／−1.0／(−0.5, 0.5]／> 0.5（inline）；VIX 30 | σ ∈ (−0.5, 0]：配息 red →「短期反彈停利檢視」、green →「健康持有」、其他 → 標準持有；σ ＝ −0.5 恰好落「標準持有」；> 0.5「創新高區…分批停利」到不了（見 §9.6） | (−1.0, −0.5) 標準持有；(−1.5, −1.0] 依 60MA「留意 -2σ 加碼點」／「勿接刀」 | (−2.0, −1.5] 同中段的觀察區或持有；≤ −2.0「大買區…建議分批加碼」／「汰弱換強」／「進入加碼參考區…可分批承接」（未確認配息真的穩健，A） | `INSUFFICIENT_DATA` 灰「⏳ 資料不足，暫無法判斷（NAV 序列 < 30 點或無 σ 位階）」；原因字串固定，與 SSOT 白話原因可能不符（兩組） | 否 | 見左三格 | 是（加碼、承接、停利、汰弱換強） | −2.0 同 R1、R3；切點與 SSOT 三態不同一組 | PRODUCTION | `tests/test_policy_advisor.py`、`tests/test_policy_advisor_vix_ssot.py`、`tests/test_ssot_2c_fund_position.py` | 中 | 修改 | 是（DG-3） |
| R3 | 兩組（A#3＝B N3） | `services/decision_matrix.py::verdict_to_actions`／`_action_after_individual_signals` | 舊 ①「📋 即時訊號 + 決策矩陣」（經 `ui/tab1_macro.py::_enrich_fund_for_decision`、`services/realtime_signal.py::compute_realtime_dashboard`） | verdict、級別、`sigma_info`、吃本金燈 | 是 | σ ≤ −2.0、σ > 1.0（inline）；動作目標持有 100／加碼 130／減倉 50／全撤 0 | σ > 1.0 衛星樂觀 → 減倉「過熱→分批停利」、悲觀 → 全撤，到不了（見 §9.6）；其餘不覆寫 | 不覆寫，維持 verdict 預設 | ≤ −2.0：樂觀 → 加碼、中性持有 → 加碼、悲觀 → 加 tag 但沿用預設；(−2.0, −1.5] 不覆寫 | 略過 σ 覆寫 → verdict×級別預設動作（持有／加碼／減倉／全撤），reason 不提 σ 無法判定；與 σ ＝ −1.0 的輸出逐字相同（B 實跑） | **是**（預設動作＝未觸發） | 「加碼」「減倉」「全撤」＋主軸字串 | 是 | −2.0 同 R1、R2 | DEAD（推論：`render_macro_tab` 無非測試呼叫者，`app.py` ① 改走 `ui/views/page_01_macro.py::render_market_overview`；兩組一致，未啟動 App） | `tests/test_decision_matrix.py`、`tests/test_ssot_2c_fund_position.py::test_downstream_decision_matrix_skips_sigma_override`、`tests/test_tab1_macro.py`、`tests/test_tier_dirty_value.py` | 中（若確認無路徑則低） | 退休候選（先確認掛載狀態） | 是（DG-1、DG-3） |
| R4 | 兩組（A#4＝B N4） | `services/allocation_backtest.py::strategy_weights_at`／`tiers_to_weights`／`current_actions_from_signals` | 舊 ② 與 ⑥ [新] 持倉體檢「🔁 配置回測」（`ui/helpers/fund_grp_health/backtest_section.py::render_allocation_backtest_section`） | `compute_fund_positions_at`／`_sigma_rank_at`（`meta_by_code` 缺檔 → 該檔 σ 為 None） | 是（數值，不經字串） | `classify_base`（SSOT 常數）；`BACKTEST_TILT_BUY` 1.5、`BACKTEST_TILT_SELL` 0.5；其他 tier 倍數 1.0 | S3 → `sell`；S1／S2 搭配台幣弱 → `sell` | S3 → `watch` | S3 → `buy`；S1／S2 搭配台幣強 → `buy` | S3 → `watch`、S1／S2 → `na`；兩者倍數 1.0＝基準權重；當前建議把 `watch／na／hold／None` 併入「⚪ 觀望」清單，權重表看不出差別；Missing 也進入歷史再平衡路徑、影響回測績效與排名（B 推論） | **是**（中性／觀望） | 「🟢 進場／🔴 轉出／⚪ 觀望」、賣→買配對、建議配置權重 | 是 | S3 與 R5 對同一 `unknown` 各給 `watch`／`na`，下游又合併 | PRODUCTION | `tests/test_allocation_backtest.py`（鎖住 unknown → watch）、`tests/test_ssot_2c_fund_position.py`；未見斷言 Missing 可辨識的測試（兩組） | 中 | 修改（揭露） | 是（DG-2） |
| R5 | 兩組（A#5＝B N10） | `services/nav_fx_switch.py::nav_fx_signal`（含 `ui/helpers/fund_grp_health/unified.py::compute_nav_fx_column`） | 健診大表「淨值×匯率」欄、配置回測 S1／S2、換股顧問理由 | `nav_level`、`fx_label` | 回測讀數值；大表那條讀 σ rank 字串重新分類（A） | `classify_base` SSOT 常數＋`FX_STRONG_TWD_SIGMA`／`FX_WEAK_TWD_SIGMA` | 搭台幣弱 →「🔴 雙貴(出場佳)」，否則觀望 | 「⚪ 觀望」 | 搭台幣強 →「🟢 雙便宜(進場佳)」，否則觀望 | 「⬜ 無法判定」`na`，與「⚪ 觀望」分得開（兩組實跑／讀碼）；但在 R4 內與觀望同權重、同清單 | 否（本身）；經 R4 時是 | 見左三格 | 是（進場佳／出場佳） | 字串重新分類見 §9.6 | PRODUCTION | `tests/test_nav_fx_switch.py`、`tests/test_flow_layer2.py` | 中 | 保留落點；字串重新分類改讀 SSOT 數值（§9.8） | 隨 DG-2；規則本身屬 BL-0428 (4)，本批 DG 未單獨出題 |
| R6 | 兩組（A#6＝B N5） | `services/switch_advisor.py::advise_holding`（震盪型分支）＋`_best_candidate` | 舊 Tab④ 換股顧問；⑤ 管理室通報預覽（A 讀碼／B 推論）；LINE 週報（R8） | 健診大表 σ rank 字串（A） | 是（經字串） | `classify_base` SSOT 常數；`is_healthy_buy`（`ROTATION_BUY_MIN_SCORE`） | 有低基期健康候選 →「🔄 建議換股」；無 →「續抱…或轉現金」 | 「續抱，等接近高基期再評估換出」 | 「續抱」 | `INSUFFICIENT`「⬜ 資料不足」，理由寫明位置無法判定（`DEC-2026-10-23-07` 已修）；候選端排除；同時「表現差」時仍經 `_best_candidate` 給換入建議（兩組） | 否 | 見左三格 | 是（換股、轉現金） | 與 R7、R9、R10 同經 `classify_base`；殘留死鍵 `_nav_zh["unknown"]`「基期未知」到不了（A） | PRODUCTION | `tests/test_switch_advisor.py`、`tests/test_switch_advisor_unknown_insufficient.py`、`tests/test_switch_advisor_underperf.py` | 中 | 保留落點；字串重新分類改讀 SSOT（§9.8） | 規則本身屬 BL-0428 (4)，本批 DG 未單獨出題 |
| R7 | 兩組（A#7＝B N7） | `services/rotation.py::suggest_rotation_pairs`／`insufficient_sigma_names` | 舊 ② extras、舊 Tab④「🔄 輪動配對建議」；③ 批次「互補配對」（B 推論） | 健診大表 σ rank 字串（A） | 是（經字串） | 滑桿預設 SSOT 常數，使用者可改（見 R16） | 賣方「高基期」 | 皆非 | 低基期且健康 → 買方 | 雙側排除；名單「⬜ 未納入買方候選(σ 資料不足)」；完全沒有配對時主訊息說「沒有貼近高點的高基期持有基金」，揭露只寫「未納入買方」（B） | 部分（全空時的主訊息，B） | 「賣高基期 → 買別類低基期健康」 | 是（賣→買） | 同 R6 | PRODUCTION（③ 批次推論可達） | `tests/test_rotation.py`、`tests/test_rotation_batch_df.py`、`tests/test_ssot_2c_fund_position.py` 等 | 中 | 修改（滑桿、字串切點、全空訊息） | 規則本身屬 BL-0428 (4)，本批 DG 未單獨出題 |
| R8 | 兩組（A#8＝B N6） | `scripts/weekly_switch_notify.py` → `services/switch_notify.py::build_notification` | LINE 週報（`.github/workflows/weekly_switch_notify.yml` 排程） | `services/fund_grp_health/unified.py::build_merged_extra_columns` → `advise_switches` | 是 | 沿用 R6 | 沿用 R6 | 沿用 R6 | 沿用 R6 | `INSUFFICIENT` 不屬 actionable → 不通知（兩組）；摘要列不計 σ ⬜ 檔數、「另有 N 檔資料不足」只計抓不到的觀察標的（B）；帶 `--notify-empty` 時訊息「✅ 本週無需換股：所有標的續抱 / 觀察中。」把 ⬜ 併入續抱（B；排程未帶該旗標） | **是**（`--notify-empty` 時，B） | 換股／賣轉現金／表現差通知；「距高:—」 | 是 | `_assemble_rows` 與 UI 版各一份（已知差異，A） | PRODUCTION（cron） | `tests/test_weekly_switch_notify.py`、`tests/test_switch_notify.py`、`tests/test_line_push_decoupled_from_ui.py` | 中 | 修改（揭露 ⬜ 檔數） | 是（DG-1） |
| R9 | 兩組（A#9＝B N8） | `services/fund_screening.py::compute_base_state`／`screen_funds` | 舊 ②「🎯 選基金（低基期進場點 · HWM σ rank）」，表格欄「買點門檻(−1.5σ)」 | 直接呼叫 SSOT（數值） | 是 | `classify_base` SSOT 常數；`LOW_BASE_MIN_POINTS` 只作可信度旗標 | 預設濾掉 | 預設濾掉 | 「🟢 低基期」進場候選 | `base="unknown"`；預設排除，取消勾選時「⬜ 資料不足」排最後（兩組） | 否 | 「進場候選」「買點門檻」 | 是（用字） | 本區與大表「基期」欄的 fund dict 形狀可能不同，畫面宣稱「本區 🟢 大表也一定 🟢」可能不成立（B 推論、未驗）；字串 vs 數值方向性見 §9.6（A） | PRODUCTION（A 讀碼）／推論可達（B） | `tests/test_fund_screener_low_base.py`、`tests/test_ssot_2c_fund_position.py` | 中 | 修改（用字） | 用字屬投資語意，BL-0428 (4) 範圍，本批 DG 未單獨出題 |
| R10 | 兩組（A#10＝B N9） | `services/fund_grp_health/unified.py::build_merged_extra_columns`「基期」欄（`BASE_LABELS`） | 健診大表、批次大表、tab2 卡片「基期」 | σ rank 字串重新分類（A；tab2 用數值） | 是（經字串） | `classify_base` SSOT 常數 | 「🔴 高基期」；輪動版「🔴 高基期(可賣)」（B） | 「⚪ 中性」 | 「🟢 低基期」；輪動版「(可買)」（B） | 「⬜ 資料不足」（兩組） | 否 | 見左三格 | 間接（legacy 行動用字） | 與 SSOT 三態 label 同頁並存兩套用字；接近高點 SSOT 綠 vs「🔴 高基期」（B）；字串切點（A） | PRODUCTION | `tests/test_base_label_ssot.py` 等 | 低～中 | 修改（用字與色） | 用字／色屬投資語意，本批 DG 未單獨出題 |
| R11 | 兩組（A#11＝B N11） | `ui/helpers/fund_grp_health/risk.py::_render_oversold_badges` | ⑥ 與舊 ②「📍 遠離高點清單」 | SSOT `position` | 是 | `position == "far_from_high"`（−1.5，研究候選） | 不列 | 不列 | 列出 | 跳過；清單為空時 `st.success`「目前無基金位於遠離高點區」綠框，⬜ 檔全空時同一綠框、無名單（兩組） | **是**（安全） | 中性用字，卡片註明非買賣建議 | 否（但綠框是 verdict 形態） | — | PRODUCTION | （兩組未點名專屬測試） | 低 | 修改（空態） | 是（DG-1） |
| R12 | 兩組（A#12＝B N12） | `ui/helpers/fund_grp_health/ai.py::_build_cross_fund_snapshot` | AI 跨檔評論 prompt（按鈕觸發；prompt 含「換手與調整建議」段，B） | SSOT | 是 | 同 R11 | — | — | 計入「遠離高點 N 檔」 | 逐檔印 ⬜ label；整組「遠離高點 {far} 檔 / {全部基金數}」分母含 ⬜、平均 σ 不揭露分母（兩組） | 部分（整組計數） | 「非買賣建議」但段落含換手建議 | 間接（AI 段落） | — | PRODUCTION（按鈕） | `tests/test_fund_grp_health_extras_p1_ai.py` | 低 | 修改（揭露 ⬜ 檔數） | 是（DG-1） |
| R13 | 兩組（A#13＝B N13） | `ui/tab2_single_fund.py` HWM σ 卡＋`_tab2_hwm_ai_line` | 單檔深掘 | SSOT | 是 | SSOT | 卡上 SSOT 綠＋「基期」欄「🔴 高基期」並排（B） | 中性 label | 中性 label | 卡片不畫；AI 行「⬜…（不得推測）」（兩組） | 否 | 中性 label＋legacy「基期」 | 否（用字間接） | 同 R10 色衝突 | PRODUCTION（A）／推論可達（B） | （兩組未點名專屬測試） | 低 | 保留（用字隨 R10） | 否 |
| R14 | 兩組 | `ui/components/health_quadrant_scatter.py`、`ui/components/nav_sigma_channel.py` | 無 | `hwm`／`level_*`／`sigma_rank` | — | — | — | — | — | 「⬜ N 檔無法定位」名單 | 否 | — | 否 | `nav_sigma_channel` docstring 仍描述 raw 舊契約，若復活會繞過 SSOT（A 推論） | DEAD（只有 `tests/test_ui3b_components.py` 使用） | `tests/test_ui3b_components.py` | 低 | 退休候選（§9.8） | 否 |
| R15 | 單組 A | `ui/views/page_02_health.py` 診斷條件「輪動門檻 σ」滑桿（`_DEFAULT_SIGMA`） | ⑥ [新] 持倉體檢 | 使用者輸入 | 不適用 | 預設 1.0 | — | — | — | — | — | — | — | — | DEAD（畫面上有，套用值在 repo 內無讀取端；A 字面搜尋） | （未查） | 低 | 移除候選（§9.8） | 否 |
| R16 | 兩組（A 列為風險、B 記載可調） | `ui/helpers/fund_grp_health/rotation.py::_render_pairs_ui` 門檻滑桿 | 舊 ②／Tab④ 輪動配對 | 使用者輸入 | 預設讀 SSOT 常數 | 賣 −2.0～0.5、買 −3.0～−0.5 可調 | 隨滑桿 | 隨滑桿 | 隨滑桿 | 同 R7 | 同 R7 | 同 R7 | 是 | UI 重算領域邏輯，可與 SSOT `position` 脫鉤 | PRODUCTION | （兩組未點名專屬測試） | 低～中 | 交裁示（併 BL-0428 (4)） | 本批 DG 未單獨出題 |
| R17 | 單組 B（A 只點名、歸 BL-0438） | `services/fund_service.py::calc_metrics`「標準差買賣點」`buy1-3`／`sell1-3`／`pos_label` | tab2「策略3 標準差買賣點」卡；tab3 保單卡迷你卡與「σ+布林 雙確認買／賣」；健診大表「現價位階」欄（`services/fund_grp_health/signals.py`）；`ui/components/mk_dashboard.py::tag_price_zone`／`_verdict_text`；`ui/helpers/fund/checkup.py`「買點」欄；`ui/tab1_macro_inflection.py` 持倉紅綠燈（DEAD） | 原始 NAV 近一年（B 讀碼判讀，未追每個 caller） | **否**（不讀 SSOT、非 HWM） | 一年平均 ± 1／2／3 倍 NAV 標準差（不同數學） | — | — | — | SSOT 判 ⬜ 的基金在這裡仍可拿到買賣訊號（B 推論，未對同一檔實跑） | 不適用（另一指標家族） | 「大跌大買 🔥 (投 50%)」「大漲停利 🔔 (出 50%)」「進入超跌價，加大進場」等 | 是 | 與 HWM σ 並存的第二套位置→買賣；守衛 `test_no_consumer_bypasses_ssot` 擋不到（B） | 推論可達 | 未找到 `tag_price_zone` 直接測試（B） | 中 | 交 BL-0438 | 是（DG-4） |
| R18 | 單組 B（A 只點名、歸 BL-0438） | `ui/tab2_single_fund.py` 布林「⚡ -2σ 超跌機會卡」 | 單檔深掘 | 原始 NAV 20 日 MA ± 2 std | 否 | 下軌 | — | — | — | 同 R17 | 不適用 | 「布林下軌突破！… 建議：小量試單（部位 ≤20%）」 | 是 | 同 R17 | 推論可達 | （B 未查） | 中 | 交 BL-0438 | 是（DG-4） |
| R19 | 單組 B（A 只點名、歸 BL-0438） | `services/ladder235.py::ladder_signal`「235 加碼水位」 | 健診大表「加碼水位」欄 | 週 NAV 20 週布林 z＋均線＋VIX | 否 | 判燈邏輯 B 未逐行讀 | — | — | — | 「⬜ 週資料不足」「⬜ 低波不判」「⚪ 不適用(內建配置)」 | 未驗 | 「🟢 燈一(小跌 20%)」「🟡 燈二」「🔴 燈三(深水 50%)」「💰 停利」 | 是 | 同 R17 | 推論可達 | （B 未查） | 中 | 交 BL-0438 | 是（DG-4） |

- 計數（量測 SHA `365cfb1d`）：合併後 19 列；兩組皆找到 15 列（R1～R14、R16），單組 A 有 1 列（R15），單組 B 有 3 列（R17～R19，A 曾點名但未盤點）。A 原 16 列、B 原 13 節點＋3 個 raw NAV 繞道。
- 另 B 列出 `services/switch_advisor.py::_breakdown_below_sma`（成長型以原始 NAV 120 日均線跌破＋總經判 SELL_CASH）供參，非 HWM／σ 位置，未入表（單組 B）。

### §9.3 Missing → 中性／安全問題清單

| consumer | Missing 落點 | 發現 |
|---|---|---|
| R1 `recommend_policy` | 不計入 P3 → 綠燈「配置健康」，不揭露 ⬜ 檔數 | 兩組，實跑 |
| R3 `decision_matrix` | verdict×級別預設動作，reason 不提 σ | 兩組，B 實跑；production 推論 DEAD |
| R4 `allocation_backtest` | 與「觀望」同權重、同清單；影響歷史回測 | 兩組（歷史回測影響 B 推論） |
| R8 LINE 週報 | `--notify-empty` 時併入「所有標的續抱 / 觀察中」；摘要不計 ⬜ 檔數 | 單組 B |
| R11 遠離高點清單 | 空清單綠色成功框，⬜ 檔全空時同框 | 兩組 |
| R12 AI 快照 | 整組計數分母含 ⬜ | 兩組 |
| R7 輪動配對（部分） | 全空主訊息「沒有貼近高點」 | 單組 B |

對照：R2、R5、R6、R9、R10、R13 的 Missing 落點已明示「資料不足／無法判定」，兩組皆判可與真實判定區分。

### §9.4 真正影響使用者判斷（production）

- **R1**（風險高）：保單多數或全數 σ ⬜ 時亮綠燈「配置健康」，使用者看不出結論沒用到 σ；同一 expander 內 R2 逐檔灰「資料不足」可同時出現（B 推論）。
- **R2**：直接給「分批加碼／承接／停利檢視」文字，切點與 SSOT 三態不同組（σ ＝ −1.6 在 SSOT 是遠離高點、在這裡是觀察區）。
- **R4**：⬜ 與觀望無法區分，且進入回測權重路徑。
- **R6／R7／R8**：換股、輪動、LINE 通知仍以 legacy「高基期賣／低基期買」產生動作語意；⬜ 落點已安全（R8 `--notify-empty` 例外）。
- **R9／R10**：「進場點」「買點門檻」「高基期／低基期」用字與 SSOT 中性三態並存。
- **R17～R19**：原始 NAV 的買賣訊號不經 SSOT，SSOT 判 ⬜ 的基金仍可能出現「加大進場」「小量試單」「加碼水位」（B 推論）。

### §9.5 Dead／research-only

- **R3** `decision_matrix`：推論 DEAD（`ui/tab1_macro.py::render_macro_tab` 未掛載）；兩組一致，未啟動 App。
- **R14** `health_quadrant_scatter`、`nav_sigma_channel`：只被測試使用。
- **R15** ⑥「輪動門檻 σ」滑桿：套用值無讀取端（單組 A）。
- `ui/tab1_macro_inflection.py` 持倉紅綠燈（R17 的下游之一）：只在 `render_macro_tab` 內呼叫 → DEAD（單組 B，推論）。
- 到不了的分支：R2 規則 8「創新高區…分批停利」、R3「σ > 1.0 過熱 → 分批停利／出場」、R6 `_nav_zh["unknown"]`「基期未知」（見 §9.6）。
- `render_rotation_section_from_df`：docstring 自稱 production 不再呼叫（單組 A）。
- 本盤點沒有找到 RESEARCH 類（只供研究腳本使用）的行動規則；不宣稱窮舉。

### §9.6 重複／衝突

1. **寫死的 σ 門檻 vs SSOT 切點**：R1／R2／R3 用 −2.0、R2 另有 −1.0 與 ±0.5、R3 有 +1.0，全部 inline、各自定義；SSOT 三態切點為 −0.5／−1.5（研究候選、未校準）。同一檔在 SSOT 是「中段」或「遠離高點」，在 R2 可能是「標準持有」或「觀察區」（兩組）。
2. **σ rank 結構上 ≤ 0，過熱／停利分支到不了**：`calc_hwm_sigma_levels` 的 hwm 取窗口含現價的最大值，σ rank ＝（現價 − hwm）／σ_abs 不會大於 0 → R2 規則 8、R3 過熱分支到不了。A 組讀碼推論；**總管已讀碼確認** `calc_hwm_sigma_levels` 的 hwm＝窗口含現價的最大值；B 組未單獨指出（B 只記載這些分支存在）。
3. **四捨五入字串重新分類**：`services/fund_grp_health/risk.py::hwm_sigma_by_code` 輸出兩位小數的「±x.xxσ」字串，下游（R5 大表欄、R6、R7、R8、R10）以 `services/rotation.py::classify_base` 解析字串重新分類；切點兩側各 0.005σ 內會與 SSOT `position` 不同（A 實跑：數值 −0.503 判 mid、字串「-0.50σ」判 high）。單組 A；**總管讀碼確認** `services/rotation.py` 有解析「σ」字串的程式（`_sigma` 先去 σ 再轉數值）。R4、R9、R11、R12 與 tab2 讀數值或 `position`，不受影響（A）。
4. **顏色衝突**：接近高點 SSOT `color` 為綠（`MATERIAL_GREEN`），「基期」欄同一狀態是「🔴 高基期」；tab2 卡把兩者並排（單組 B）。
5. **unknown 的多重語意**：同一個 `nav_level="unknown"`，R4-S3 → `watch`、R4-S1／S2 → `na`、R6 → `INSUFFICIENT`、R10 → ⬜ 資料不足、R5 → ⬜ 無法判定；R1／R3／R11 則不揭露；Tab④ 換股顧問摘要有「資料不足 n」而 LINE 摘要沒有（B）。
6. **raw NAV 繞道（與 BL-0438 重疊）**：B1 `calc_metrics` 買賣點（R17）、B2 布林卡（R18）、B3 `ladder235`（R19）不讀 SSOT、不用配息還原序列；`tests/test_ssot_2c_fund_position.py::test_no_consumer_bypasses_ssot` 只擋 `calc_hwm_sigma_levels` 字面使用（B）。這三處屬非 HWM 指標家族，與 `docs/BACKLOG.md` BL-0438 同題。
7. **`_assemble_rows` 重製**：UI 版與 LINE headless 版各一份（已知，A）。

### §9.7 Decision Gate 題目（附總管推薦方案；裁示前一律照舊）

- **DG-1　行動類 consumer 遇 σ ⬜ 的處理**（`recommend_policy` 綠燈、`decision_matrix` 預設動作、LINE 週報 `--notify-empty` 併入續抱、遠離高點清單空清單綠框、AI 快照分母含 ⬜）。
  - A：一律沿用既有「資料不足／無法判定」措辭顯示，並不給綠燈、不給動作，另列 ⬜ 檔數（與 `DEC-2026-10-23-07` 同原則，不新增狀態）。
  - B：維持現有判定，只在文字附註「N 檔位置無法判定」。
  - C：維持現狀。
  - **總管推薦 A**：Missing ≠ 中性為永久原則；沿用既有措辭、不新增語意；B 仍讓 ⬜ 參與綠燈。
- **DG-2　配置回測 ⬜ 的權重**。
  - A：權重維持基準（不改回測數字），但清單與權重表把 ⬜ 與「觀望」分開列示並統計檔數。
  - B：該日把 ⬜ 檔排除出策略宇宙並重新正規化（會改變回測結果）。
  - C：維持現狀。
  - **總管推薦 A**：只改揭露、不改數字；B 屬新策略語意，且影響歷史回測比較。
- **DG-3　HWM σ 驅動的買賣／加減碼／停利文字**（`recommend_policy`、`advise_fund`、`decision_matrix` 寫死的 −2.0／−1.0／±0.5／+1.0；σ rank 結構上 ≤ 0，使過熱／停利分支到不了）。
  - A：改用 SSOT 三態對應原有分支（遠離高點 → 原深度超跌分支等），刪去到不了的分支。
  - B：保留數值，但改為具名常數並標 `calibrated=False` 研究候選。
  - C：退休 HWM σ 產生的行動文字，位置只作中性資訊顯示；行動規則待日後校準另案（對齊 `DEC-2026-10-23-02` 2C「不得再由 HWM evidence 產生可買／可賣」）。
  - **總管推薦 C**：2C 原裁示；門檻未校準；A 等於把未校準切點升格為行動門檻。
- **DG-4　繞過 SSOT 的原始 NAV 買賣訊號**（`calc_metrics` buy1-3／sell1-3、Tab2 布林 −2σ「小量試單」、`ladder235` 加碼水位）。
  - A：SSOT 判 ⬜ 時一併抑制這些訊號。
  - B：保留為另一指標家族，但改名、去除位置／買賣措辭。
  - C：本批不處理，併入 BL-0438 另案裁示。
  - **總管推薦 C**：非 HWM σ，屬不同指標家族；動它是新投資語意，BL-0438 已待裁，避免範圍擴張。
- **DG-5　低波動數值門檻**（BL-0428 第 (5) 題既有題）。
  - A：維持只用 σ≈0 與貨幣市場判 ⬜，不新增門檻。
  - B：新增數值下限（需先校準研究）。
  - C：交研究另案。
  - **總管推薦 A**：客戶「不新增任何 threshold」原則；無校準資料。

> ✅ **2026-10-23 狀態指標（狀態更新，不是漏刪；上列題目與推薦一字未改）**：客戶裁示 **DG-1 A／DG-2 A／DG-3 C／DG-4 C／DG-5 A**（＝五題皆總管推薦），見 `docs/DECISIONS.md` `DEC-2026-10-23-11`；實作落地與未修殘留（批次大表 df 路徑仍解析 σ 字串）見 `docs/BACKLOG.md` BL-0428 列尾、`docs/HANDOFF.md` 第 2 節第九次框；守衛 `tests/test_bl0428_dg_rulings.py`。（→ 2026-10-23 狀態更新，不是漏刪：已由 PR #1033 合併，main `ea06b130`。）本節 §9.2～§9.6 為裁示前 `365cfb1d` 的盤點快照，不隨實作改寫。

> 本批 DG-1～DG-5 未單獨出題、仍屬 BL-0428 的項目（照舊待裁）：R6／R7／R8 換股與輪動規則本身、R9／R10 的「進場點／高基期／低基期」用字與色、R16 輪動滑桿（BL-0428 第 (4) 題）；BL-0428 第 (1)～(3)、(6) 題。

### §9.8 內部可自決、不需裁示（裁示後隨實作處理）

- **四捨五入字串重新分類**（§9.6 第 3 點）：consumer 應改讀 SSOT `position`／數值，不讀兩位小數字串。屬已確認 bug、只有一個安全修法，不包裝成客戶裁示（`PROJECT_RULES.md` 第 4 節反向禁令）。
- **死碼候選**：`decision_matrix`（經未掛載的 `ui/tab1_macro.py`）、`ui/components/health_quadrant_scatter.py`、`ui/components/nav_sigma_channel.py`、`ui/tab1_macro_inflection.py`、⑥ 未被讀取的「輪動門檻 σ」滑桿設定、到不了的「基期未知」字串。**本批不清理**；依 `CLAUDE.md` §-1.5.1c 判定 3，待有任務碰到時處理（判「孤兒」前須再實測 caller）。

### §9.9 A／B 不一致與單組發現

- **文件組比對後未發現兩組互相矛盾的結論**（文件組單組比對，未經第二組驗證）；已見的差異是「一組看到、另一組沒寫」或可達性信心標記不同：
  - 單組 A：σ rank ≤ 0 使分支到不了（總管已讀碼確認前提）；四捨五入字串重新分類（總管已讀碼確認解析存在）；R15 滑桿無讀取端；`switch_advisor._nav_zh["unknown"]` 死鍵；`render_rotation_section_from_df` 不再呼叫。
  - 單組 B：R17～R19 raw NAV 繞道的盤點（A 只點名歸 BL-0438）；LINE `--notify-empty` 併入續抱與摘要不計 ⬜；輪動全空主訊息；接近高點綠 vs 🔴 高基期的顏色衝突；選基金與大表 fund dict 形狀可能分歧（未驗）；配置回測 ⬜ 影響歷史回測（推論）；B4 `_breakdown_below_sma`。
  - 可達性標記：R9 選基金、R13 tab2、⑤ 管理室通報預覽 —— A 標 PRODUCTION（讀碼）、B 標推論可達；本表兩者並列。
  - 範圍描述：A 說「沒有找到直接用 raw NAV 算 HWM σ 的 production consumer」，B 找到 raw NAV 的**非 HWM** 位置→買賣實作（R17～R19）；兩者不衝突（數學不同）。

### §9.10 盲點／未驗與出處

- 兩組皆未跑 pytest、未啟動 App；可達性有一部分靠字面搜尋推得（R3、R9、R13、R17～R19 等）；`ladder235` 判燈邏輯 B 未逐行讀；A 未查 prompt 文字中是否另有 σ 行動語意；B 未查批次 checkpoint 是否保存 2C 之前的 σ rank 字串。
- 兩份原始報告存於總管 scratchpad（不在 repo）；本節由文件組合併落盤，**文件組未重跑兩組的實跑、未重讀原始碼**（只以字面搜尋確認 `calc_hwm_sigma_levels` 的 hwm 取 `s.max()`、`services/rotation.py` 的 σ 字串解析存在，與總管讀碼結論一致）。
- 兩組各自為單組產出；本節「兩組」標記只代表兩組結論一致，不代表任何一列經過第三方逐條複驗。

## §10 BL-0438 唯讀研究（2026-10-24，main `36dd93c6`）

> ⛔ **狀態：唯讀研究結果，不是實作規格、不授權 production 修改。** 客戶 2026-10-24 對 DG-1～DG-3 的傾向見 `docs/DECISIONS.md` `DEC-2026-10-24-01`（**傾向、未核准實作**）。`DEC-2026-10-23-02` 2C（HWM σ）裁示不變。本節不新增公式、門檻、資料來源或語意。程式位置以 main `36dd93c6` 為準，行號會漂移，標「~」者為約略位置。

證據分三類，**不得混讀**：(A) production code 讀碼證實；(B) 合成測試證實；(C) 理論風險／未經真實基金驗證。

### §10.1 (A) production code 讀碼證實（單組讀碼＋總管抽查）

**仍讀原始 NAV 的位置類指標**（目前只有 HWM σ（`services/fund_position.py`）與 `calc_metrics` 的風險指標用配息還原序列）：
- `services/fund_service.py::calc_metrics` 的 σ 通道 buy1-3／sell1-3、`pos_label`、`bb_*`、`ma20`／`ma60`、高低點（同檔註解 ~:420-423 自承只有風險指標用 `s_tr`）。
- `services/zscore_engine.py::nav_zscore`／`rebalance_signal`：唯一 caller `ui/tab2_single_fund.py` 傳原始 `s`，結果進 `services/health/action.py::combine_action`。
- `services/ladder235.py::ladder_signal`：唯一 caller `ui/tab_fund_grp_health.py`。
- `services/switch_advisor.py::_breakdown_below_sma`：120 日均線 → `SELL_CASH`，LINE 週報可達。
- 鄰接項：`fund_type_classifier` 的效率比、`compute_max_drawdown`。

**名稱與內容不符**：`services/allocation_backtest.py::to_twd_total_return_series` ＝ 原始 NAV × FX、無任何配息處理，但 UI caption／assumption 寫「台幣總報酬」；consumer：配置回測權重／進場轉出、`portfolio_performance`。

**Missing → 中性／HOLD／安全／0**（內部 bug，登記 BL-0440）：
- `mk_signal_by_code` 買賣價全缺 →「⚪ 區間內」。
- `tag_price_zone` buy／bb 缺 → `"Hold"`。
- Tab3 hero KPI 建表失敗 → 顯示 0 檔、N/A 不揭露。
- checkup PK 表 Hold 與 N/A 同顯示「—」。
- `ui/tab3_portfolio.py` ~:1817 `pos_label` 預設「正常」。
- `tab1_macro_inflection` 紅綠燈 `x or 0` → 🟢（推論為 dead，`app.py` 未掛）。
- Tab2 −2σ 卡／策略 3 卡：缺值與未觸發不可分。
- Tab2／Tab3 AI prompt：缺鍵直接省略、不標示。

**UI 平行計算**（內部 bug，登記 BL-0440）：
- 布林 20／2σ 至少 3 份：`services/fund_service.py`、`ui/tab2_single_fund.py` ~:774、`ui/helpers/fund_grp_health/signals.py` ~:141。
- Tab2 −2σ 超跌卡讀 UI 重算、未四捨五入的 `_bb_dn`，不是 `metrics.bb_lower`。
- MA60 有 5 處計算。
- 買賣價 → 區間標籤有 6 套用字：`pos_label`、`tag_price_zone`、`mk_signal_by_code`（跳過 b2／s2）、tab1、tab3 迷你卡、tab2 chip。
- Tab3 兩處把 MA60 趨勢傳入 `advise_fund`，但其 docstring 稱不使用（未逐行驗）。

**資料不足 fallback**：`calc_metrics` 在 n<20 時改「區間σ(資料不足)」＝（年高−年低）/6，下游除 Tab2 顯示 `buy_mode` 外不揭露品質；`ladder235` 在 σ=0 時誤標「週資料不足」。

**誠實降級（已正確）**：zscore 不可算時顯示位階未知；ladder 資料不足／低波／Core 有 ⬜⚪。

### §10.2 (B) 合成測試證實

直接呼叫 production 函式（streamlit 與 `shared.schemas` validator 打樁，**schema 驗證未執行**）：
- 不配息序列 200 seeds：原始 vs 還原 0 差異。
- 配息基金：原始 NAV 一律讀得較低／較像「該買」。
- 月配 0.5%、含息持平情境 200 seeds：Z-Score 訊號翻轉 110、`calc_metrics` 位置 124、235 燈 34。
- 配息率越高、期間越長，偏差越大。

⚠️ **參數為自訂，只示方向與量級；上列翻轉次數是合成情境的計數，不是真實基金的發生率。**

### §10.3 (C) 理論風險／未經真實基金驗證

- 真實配息基金未測（repo 內無基金 NAV＋配息快取）。
- `tag_price_zone` 在 nav 存在而 buy 缺的路徑屬罕見，未實測。
- 是否有來源回傳的已是還原 NAV，未逐源驗。
- NDC／VIX 動態門檻維度未測。
- 「dead／無其他 caller」為字面 grep、單組結論，不宣稱窮舉。

### §10.4 出處與未驗

- 研究由單組讀碼與合成測試產出、總管抽查，經總管轉述；文件組未重跑測試、未重讀原始碼。原始報告不在 repo。
- 後續：DG-1～DG-3 傾向見 `DEC-2026-10-24-01`；Missing／UI 重算修補登記 BL-0440（客戶指示尚未開始）。
