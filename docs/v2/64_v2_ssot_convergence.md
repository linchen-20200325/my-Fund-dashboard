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

## §8 出處與沒查證的部分

- 唯讀稽核 2026-10-22／23，五組 agent ＋ 總管抽驗，量測 SHA `bde2468`；未改 code、未實跑 UI。
- 客戶 2026-10-23 裁示經總管派工單轉達；repo 內無逐字存檔；文件組未見客戶對話本身。
- 本檔由架構與文件組依總管規格落盤；§3 的 −3.24 合成序列實算、§4 的重複點、§5 的分類皆為稽核組結論，**文件組未重跑、未重讀原始碼**；單組實測＋總管抽驗，未經第二組逐條驗證。
