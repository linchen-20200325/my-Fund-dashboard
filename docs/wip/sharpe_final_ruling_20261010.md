> ⚠️ **檔頭說明（文件組加註，以下原文內容未改）**：本檔為 planning／audit 產出，**非定稿、非 production 規格**；待協作助手裁示。由計算服務組單組獨立複核 origin/main 549876c 產出，與前一對話第二組草稿（交接本第四十七次更新〈五〉摘要）比對後一致與差異已列於檔內；未經第三組驗證。裁示前不得據以修改 production。

# Sharpe／Sortino 最終公式裁示單（計算服務組・獨立複核版）

- 產出者：計算服務組（獨立複核），**單組產出、未經第二組驗證**（`CLAUDE.md` §-2 規則 6）。
- 基準：`origin/main` ＝ `549876c6f12aa767596a0ddb9be088355292d27f`；所有程式碼以 `git show origin/main:<path>` 讀取，未讀工作樹。
- 性質：**純 planning／audit**。本單任何「建議公式」都**不是**已核准事項；凡標 🔐 者涉及新的 production 資料路徑或資料源，**須客戶授權**，不得預設已核准。
- 草稿來源：交接本 `origin/ccr-99c3296a-jgoapn:docs/handover_2026_09_26_latest.md` 〈第四十七次更新〉五（§10 摘要；原稿已遺失），以及〈第四十五次〉〈第四十六次〉兩段。草稿結論**未被當作前提**，以下逐項獨立判定。

---

## 0. 現行實況重建（origin/main）

### 0.1 全站「自己算」Sharpe／Sortino 的位置

可重跑指令（repo 根目錄）：

```
git grep -n -E "(sharpe|_sh|sortino)\s*=\s*.*(/|np\.divide|round\()" origin/main -- '*.py' ':!tests/**' | grep -v -E "_safe|_num\(|\.get\(|float\(str"
```

2026-10-10 實跑輸出（4 行）：

```
services/fund_service.py:615   sharpe = round(float((r252.mean() - rf) / _std252 * np.sqrt(TRADING_DAYS_PER_YEAR)), 2)
services/fund_service.py:666   sortino = round(
services/portfolio_frontier.py:147   _sh = np.divide(_ret - rf_annual, _vol, ...)
services/portfolio_performance.py:144   _sharpe = ((_cagr - rf_annual) / _ann_vol
```

另加這條指令找回傳 tuple、沒有賦值給 sharpe 變數的一處：`git grep -n "def _sharpe" origin/main -- '*.py'` → `services/portfolio_frontier.py:66`。
⚠️ 這兩條指令都是**字面形態掃描**，動態組出的公式掃不到。所以下表是**已知計算點**，不是窮舉。

| # | 位置（檔案::符號） | 報酬定義 | rf 來源與數值 | 年化 | ddof | 窗長與最小樣本 | 幣別前提 |
|---|---|---|---|---|---|---|---|
| S1 | `services/fund_service.py::calc_metrics`（Sharpe） | **log**：`log_ret = ln(s_tr/s_tr.shift(1))`；`s_tr` ＝ 配息再投資還原序列（`_total_return_nav`） | `rf = _RF_ANNUAL/252`（日**簡單**利率）；`_RF_ANNUAL` 模組全域，預設 **0.04**，見 0.2 | `√252`（`TRADING_DAYS_PER_YEAR`） | pandas `.std()` 預設 **ddof=1** | `tail(252)` **筆**（不是 365 日曆日）；`len ≥ MIN_OBS_SHARPE_SORTINO=250`；σ≤1e-12 → None；`finalize_fund_metrics` 只在併入累積歷史時跑 `assess_series_coverage`，sparse（coverage<0.6 或最大缺口>14 天）就砍掉自算值 | **原幣 NAV**；rf 一律是同一個 4%，不看幣別 |
| S2 | 同上（Sortino） | 同 S1 的 log 報酬 | `MAR = rf`（同上 4%/252） | `√252` | TDD 分母 **1/N**（全樣本，Kidd 2012） | 同 S1，另加「低於 MAR 的筆數 ≥ 5」 | 同 S1 |
| S3 | `services/portfolio_performance.py::metrics_from_return_series`（組合層 SSOT；被 `performance_metrics`、`portfolio_tracking.reconstruct_trend`、`allocation_backtest.run_strategy` 共用） | **simple** `pct_change`；分子是**幾何 CAGR** ＝ `(Π(1+R))^(252/n) − 1`，**不是**算術平均 | 參數 `rf_annual`，預設 **0.0**；caller 實傳：`performance_metrics`／`reconstruct_trend` 沒有傳 → 0；`allocation_backtest` 傳 `FRONTIER_RF_ANNUAL=0.0` | `√252`（σ）、`252/n`（CAGR 指數） | **ddof=1** | `n ≥ 2`；`reconstruct_trend` 另有 `PORTFOLIO_TREND_MIN_DAYS` 年化閘門 | `ccy_by_code`＋`fx_series` 有傳 → 轉成 TWD basis |
| S4 | `services/portfolio_frontier.py::_sharpe`／`random_portfolio_cloud` | **simple** `pct_change`；μ ＝ **算術**平均×252 | `FRONTIER_RF_ANNUAL = 0.0`（`shared/signal_thresholds.py:249`） | ×252、Σ×252 | cov **ddof=1** | `FRONTIER_MIN_OBS=60`；未滿 252 標 low_confidence | ⚠️ `ui/helpers/portfolio_perf.py::render_efficient_frontier` 呼叫 `efficient_frontier_diagnostic(_nav, _w)` 時**沒有傳幣別／匯率** → **原幣混算**（USD 與 TWD 的報酬直接進同一個共變異數矩陣） |
| X1 | MoneyDJ wb07（**外部值，非自算**） | 未知 | 未知 | 未知 | 未知 | 「一年」「六個月」 | 未知 |

**S1 的 Sharpe 實際來源優先序**（`calc_metrics` 末段）：wb07 一年 > wb07 六個月 > 本地自算。
**境內基金沒有 wb07**：`repositories/fund/nav_metrics.py::_fetch_domestic_perf` 的 docstring 寫「境內基金頁根本沒有 wb01 / wb05 / wb07」，這條路徑自 2026-08-11 起凍結，恆回 `{}`。
⇒ 境內基金（docstring 點名 user 的 5 檔：ACCP138／ACDD01／ACDD19／ACTI71／ACTI94）的 Sharpe **100% 來自 S1 自算**。這一點左右了第 3 節的影響評估。

**下游消費（Sharpe 值流向）**：只有一個寫入點，就是 `calc_metrics`。可重跑指令：
`git grep -n -E "calc_metrics\(" origin/main -- '*.py' ':!tests/**'` → 唯一呼叫點是 `services/fund_service.py:1240`（`finalize_fund_metrics`）。
**持久化**：單檔 Sharpe 沒有持久化（`git grep -n -i sharpe` 掃過 `services/nav_history_gs.py`、`repositories/portfolio_perf_repository.py`、`scripts/export_fund_db.py`，結果是只有**組合層** S3 的 `sharpe` 會寫進 `repositories/portfolio_perf_repository.py` 的 `_portfolio_perf_history`，由使用者按下快照按鈕時寫入）。草稿說「單一基金 Sharpe 未持久化」**成立**，但要補一句：**組合層 Sharpe（rf=0）有持久化**。

### 0.2 驗證「rf 注入失效」的宣稱 → **成立**（靜態證據；AppTest 未重跑）

1. `app.py:378-381`（origin/main）：`_cached_ind = st.session_state.get("indicators", {})`；只有 `FED_RATE.value` 不是 None 時才 `set_risk_free_rate(value/100)`。
2. `git show 521ef2e -- app.py`：`-from ui.tab1_macro import render_macro_tab` → `+from ui.views.page_01_macro import render_market_overview`，呼叫點 `render_macro_tab()` → `render_market_overview()`。
3. `ui/views/page_01_macro.py:203` `_SK_IND = "v01_macro_indicators"`，`:310` `st.session_state[_SK_IND] = fetch_all_indicators(fred_key)`。
4. 全 repo 寫入 `"indicators"` 這個 key 的地方。可重跑：
   `git grep -n -E "[\"']indicators[\"']|\.indicators\b" origin/main -- '*.py' | grep -v "^origin/main:tests"`
   → 寫入只有兩處：`ui/helpers/session.py:68` 初始化成 `{}`，以及 `ui/tab1_macro.py:2095` `st.session_state.indicators = ind`。後者位於 `def render_macro_tab()`（:1774 起）之內。
5. `render_macro_tab` 的呼叫者：`git grep -n -E "render_macro_tab\b" origin/main -- '*.py' | grep -v tests` → 除了定義本身，**只剩 docstring／註解**，沒有任何呼叫。`ui/tab6_manual.py:678` 雖然 import 了 `ui.tab1_macro`，用的是 `render_indicator_map`，不是寫入者。
6. `set_risk_free_rate` 的呼叫者只有 `app.py:381` 與 `ui/tab1_macro.py:2111`（後者也在 `render_macro_tab` 內，是死碼）。

⇒ 在 production 路徑上 `_cached_ind` 恆為 `{}`，注入永不發生，`_RF_ANNUAL` 停在 **0.04**。週推播 `scripts/weekly_switch_notify.py` 是另一個 process，從頭到尾沒有呼叫 setter，所以同樣是 **0.04**。
⚠️ 第 4、5 點是「有沒有漏看」型的宣稱（動態 `setattr`／`st.session_state.update(...)` 的字串鍵，字面 grep 掃不到）。**單組靜態查證，未重跑盤點組的 AppTest**。
⚠️ 補一個盤點組沒提的點：**即使 key 修好，注入值也是 `FED_RATE`（FEDFUNDS 單一最新值）**，拿去套整段 252 筆歷史，正是 R4 要排除的「用今天的 rf 套整段歷史」。所以**修 key 不是解法**。

---

## 1. 草稿 A／B／C 三類範圍複核

| 類 | 草稿內容 | 判定 | 證據與補充 |
|---|---|---|---|
| A 公式本體 | `calc_metrics`、`finalize_fund_metrics`；停用 `_RF_ANNUAL`／`set_risk_free_rate`（連帶 `app.py`、`ui/tab1_macro.py`、`fund_fetcher.py` re-export） | **成立，有遺漏** | 遺漏 (a)：`services/reconcile.py::reconcile_sharpe` 的 `source_a="self_calc:mean/std*sqrt(252)"` 字串與 docstring 會變成錯的出處標記（§2.2），要同步改。遺漏 (b)：`calc_metrics` 的 docstring 公式表（:373-376）與 `risk_metric_meta["sortino"]["definition"]` 字串。遺漏 (c)：`std_1y` 等年化 σ 仍用 `√252`。Sharpe 若改用 A＝N/年，畫面上的「σ」與「Sharpe」年化口徑會不一致，見 R13。遺漏 (d)：`tests/test_headless_import_v19517.py` 鎖了 `from fund_fetcher import _RF_ANNUAL, set_risk_free_rate`，`tests/test_services_purity_contract.py:855` 也有列名，停用時要一起處理。 |
| B rf 來源與幣別前提 | L2 r̄ 函式＋L1 讀 `data_cache/fred_indicators.parquet`；週推播取同一份 rf；幣別預設 USD 處加 `ccy_source` | **方向成立，路徑選擇有疑點** | 疑點 (a)：`docs/v2/10_db_inventory.md:1257` 記載該 parquet 在 production 是**「只寫不讀」**，讀它的只有 workflow script。改由 production 讀它，等於**新開一條 production 讀取路徑**🔐，而且新鮮度靠 GitHub workflow 回寫 repo（`metadata.json` 顯示 `fred_indicators.last_updated = 2026-10-01`）。疑點 (b)：**production 其實已經在即時抓 DGS3MO**（`services/macro/us_indicators.py:536` `_fred("DGS3MO", fred_api_key, 2600)`，用來算 10Y-3M 利差），這是第二條候選路徑（R5）。疑點 (c)：`calc_metrics` 收到的 `s` 已經帶 `attrs["currency"]`（`shared/data_quality.py::nav_series_currency`，未知回 `""`，**不會預設 USD**；`_merge_nav_history_series` 遇到幣別分歧就 `pop`）。這條既有通道可以當幣別輸入，但它的值本身是否來自名稱推定，**未查證**（交接本〈四〉提到 `_span_extend_expected_ccy` 的推定會經由 currency_hint 回流），所以草稿要求的 `ccy_source` 仍然必要。 |
| C 防 fail-open 消費端 | `mk_dashboard.tag_health_check`、`switch_strategy`、`replacement` 規則 (d)、週推播紅燈、`grade.compute_4d_health`、AI 提示 | **成立，有遺漏 4 處** | 已列者逐一實讀確認會 fail-open（見 1.1）。**遺漏**：① `services/portfolio_service.py::calc_fund_factor_score`（六因子分，`services/health/report.py:263` 呼叫）：缺 Sharpe（權重 25）與 Sortino（權重 15）就退出分母，`total_s/total_w` 重新歸一，負 Sharpe 原本只拿 0 分的那一格消失，總分**上升**；② `ui/helpers/fund_grp_health/quality.py`（A1 相對品質分）：「因子缺 → 退出分母」；③ `services/switch_strategy.py::market_regime_alert`：None 不計入，「Sharpe 為負比例 ≥80%」的分母縮小，系統性風險判定會變；④ `services/switch_advisor.py:168-172`：`sharpe is None` 時不算 redlight。 |

### 1.1 C 類 fail-open 實證（逐條讀碼）

- `ui/components/mk_dashboard.py::tag_health_check`：`if sharpe is not None: if sharpe<0: return "Sharpe_Warning"`。None 會直接往下走，含息、配息、MA 三條都沒觸發就回 **`"Healthy"`**。**fail-open 成立。**
- `services/switch_strategy.py::switch_signal`：Sharpe None → **GRAY**（誠實的灰燈）。但紅燈條件「含息<0 且 Sharpe<0」從此**到不了**，所以週推播的 `_red` 只剩 `eat_is_red`。**警示消失，成立。**
- `services/health/replacement.py` 規則 (d)：`sharpe_v is not None and sharpe_v < ...`。None 時規則不觸發。**成立。**
- `services/health/grade.py::compute_4d_health`：`scores=[可得維度]`，`overall = sum/len`（`GRADE_4D_MIN_FACTORS=2`，且要求核心維度配息或 Sharpe 至少一個在）。數值例（cutoffs 80/65/50/35）：
  - 配息覆蓋 <0.5 → 15、σ=15~20% → 55、Sharpe<0 → 15：(15+15+55)/3 ＝ **28.3 → F**；拿掉 Sharpe：(15+55)/2 ＝ **35.0 → D**。
  - 配息 15、σ<10% → 90、Sharpe 15：40.0 → D；拿掉後 52.5 → **C**。
  - ⇒ **F→D 會讓 replacement 規則 (b)「4D Grade F → 🔴 建議換」消失。**成立，而且比草稿描述的更嚴重：它不只讓分數變好，還會連帶把汰換紅燈關掉。
- `services/ai_service.py:198`：`m.get("sharpe","—")` 的 key 存在而值為 None 時，提示詞印出 `Sharpe None`（不是 fail-open，是呈現瑕疵）。

**影響集中在哪裡**：TWD rf 不給時，受影響的是**沒有 wb07 的基金**，也就是**境內基金，正好是 user 的 5 檔境內持倉**（0.1）。它們的 Sharpe／Sortino 會**全面變成 None**，連帶 switch_score 的核心維度缺、策略燈全灰。⚠️「這 5 檔都是 TWD 計價」**未查證**（境內基金也可能有美元級別）。

---

## 2. simple vs log 推導（R1 的依據）

記單期 simple 報酬 R，log 報酬 r ＝ ln(1+R)。設 E[R]＝μ，Var[R]＝σ²（單期）。

**(i) 均值偏差**。二階泰勒展開 ln(1+R) ≈ R − R²/2：

E[r] ≈ μ − E[R²]/2 ＝ μ − (σ² + μ²)/2

**變異數**。Var[r] ≈ Var(R − R²/2) ＝ Var(R) − Cov(R, R²) + Var(R²)/4。
若 R ~ N(μ, σ²)，則 Cov(R,R²) ＝ 2μσ²、Var(R²) ＝ 2σ⁴ + 4μ²σ²，代入：

Var[r] ≈ σ² − 2μσ² + σ⁴/2 + μ²σ² ＝ σ²(1−μ)² + σ⁴/2
⇒ sd[r] ≈ σ(1 − μ + σ²/4)（日頻 μ≈3×10⁻⁴、σ²≈10⁻⁴，所以相對差只有 10⁻⁴ 量級）

**Sharpe（先看 rf＝0，單期）**：

S_log ＝ E[r]/sd[r] ≈ (μ − σ²/2 − μ²/2) / (σ(1 − μ + σ²/4))
     ≈ μ/σ − σ/2 + O(μ²/σ, μσ, σ³)
⇒ **S_simple − S_log ≈ σ/2（單期）**

年化時兩者同乘 √A，而 σ_p·√A ＝ σ_ann：

**ΔS_ann ≈ σ_ann / 2，與取樣頻率無關（日頻、週頻同一個結果）。**

**(ii) 超額報酬在 log 空間的正確定義**：一期無風險毛報酬 1+ρ，所以

e_log ＝ ln(1+R) − ln(1+ρ) ＝ ln((1+R)/(1+ρ)) ≈ (R − ρ) − (R² − ρ²)/2

**`R − ρ` 只在 simple 空間正確**。現行 S1 寫的是 `mean(ln(1+R)) − ρ`（log 減 simple），等於少扣了 ρ²/2：ρ＝0.04/252＝1.587×10⁻⁴ 時 ρ²/2＝1.26×10⁻⁸／日，年化約 3×10⁻⁶，**數值上可忽略，但口徑混用**。

**(iii) 本專案量級（合成資料，seed 20261010，2000 次模擬；腳本在 scratchpad `calc/sim.py`〔該腳本未入 repo，容器結束即遺失〕，離線、不連網）**

| σ_ann | 日頻 E[S_simple − S_log] | 理論 σ/2 | 週頻（52） |
|---|---|---|---|
| 8% | 0.0395 | 0.040 | — |
| 15% | 0.0744 | 0.075 | 0.0714 |
| 25% | 0.1238 | 0.125 | 0.1195 |
| 40% | 0.1982 | 0.200 | — |

**正負號翻轉帶**：當 0 < 年化 simple 超額報酬 < σ_ann²/2 時，S_simple > 0 但 S_log < 0。
例：σ_ann＝25%、年化超額 μ＝σ²/4＝1.5625%，實算 S_simple ＝ **+0.062**、S_log ＝ **−0.062**。
本站有多條「Sharpe < 0」的硬門檻：`Sharpe_Warning`、策略紅燈、汰換規則 (d)、`_score_sharpe` 的 15 分。**口徑選擇會直接改變警示**，不是單純的精度問題。

**推薦：simple（算術平均超額報酬）**，與草稿一致。理由：
1. Sharpe（1966／1994）的定義就是「差額報酬 D_t ＝ R_t − R_f,t 的算術平均 ÷ 標準差」；
2. ρ_i 是簡單計息，`R − ρ` 在 simple 空間是**精確**的持有期超額報酬，不用近似；
3. S4 前緣已經用算術 μ，Sortino 的 Kidd（2012）參考也是 simple；
4. log 均值 ≈ 幾何成長率（中位數成長），衡量的是「成長」不是「每期期望超額報酬」。

**代價（如實寫出）**：simple 比現行 log 高約 σ/2。高波動基金的自算 Sharpe 會**系統性上升**（25% 波動約 +0.12），而且會跟組合層 S3（幾何 CAGR 分子，≈ log 口徑）差出同一個量級，見 R11。

---

## 3. rf 對齊推導（R4 的依據）

記 y_d ＝ 日曆日 d 生效的年化 rf（取 ≤7 天內最後一筆 DGS3MO ÷100），區間 (t_{i−1}, t_i] 的日曆天數 Δd_i。

**逐期精確計息**：ρ_i^exact ＝ Π_{d∈區間}(1 + y_d/365) − 1 ≈ Σ_{d∈區間} y_d/365
**草稿（窗內平均）**：r̄ ＝ (1/T) Σ_{d∈窗} y_d，ρ_i^bar ＝ r̄·Δd_i/365

**均值**：Σ_i ρ_i^exact ≈ Σ_d y_d/365 ＝ r̄·T/365 ＝ Σ_i ρ_i^bar
⇒ mean(e^exact) ＝ mean(e^bar) 到一階完全相同。二階差異是複利項，約 (y/365)²·Δd²/2 ≈ 10⁻⁸／期。

**標準差**：令 δ_i ＝ ρ_i^exact − ρ_i^bar ＝ (Δd_i/365)(ȳ_i − r̄)，其中 ȳ_i 是該區間的平均利率。則
Var(e^bar) ＝ Var(e^exact) + Var(δ) − 2Cov(e^exact, δ)。
- Var(δ) ≤ (1/252)²·Var(y) ≈ (1/252)²·(0.015)² ≈ 3.5×10⁻⁹，相對於 Var(R) ≈ 10⁻⁴ 只有 3.5×10⁻⁵。
- 交叉項的 Cauchy–Schwarz 上界是 2·0.01·5.9×10⁻⁵ ≈ 1.2×10⁻⁶（≈ Var 的 1.2%，這是完全相關的極端情形）。實務上日報酬與「利率偏離窗均值」幾乎不相關。

**合成驗證**（rf 在一年內由 0.3% 線性升到 4.7%，跟 2022 年同型）：

| 口徑 | 年化 rf | Sharpe（A＝N/年） |
|---|---|---|
| 逐期精確 | 2.5017% | 2.4237 |
| 草稿窗均 r̄·Δd/365 | 2.5017% | 2.4236 |
| **用期末「今天」的 rf** | 4.7032% | **2.2788（−0.145）** |
| 現行固定 4%/252 | 4.1412% | 2.3170 |

（Sharpe 絕對值偏高是這次隨機抽樣的結果，看的是**各行之間的差**。）

**為什麼不得用「今天的 rf」套整段歷史**：
ΔS ＝ −(y_today − r̄)/σ_ann，是有方向的系統偏誤，上例 −0.022/0.15 ≈ −0.147。
這也違反 §2.3 PIT：窗內每一期當時拿不到「今天」的利率，用它就是 lookahead。若日後要算歷史時點的 Sharpe（回測或快照），偏誤會更明顯。
⇒ **草稿的 r̄ 窗均法成立，與逐期法差 < 0.001，可接受**。逐期法實作也不難；若要做到「逐期 rf 的變動也進入 sd」，可選逐期法。兩者差異在本專案量級下可以忽略。**推薦草稿版 r̄**：簡單、可稽核，覆蓋率也好定義。

**DGS3MO 報價基礎 → 未查證（repo 內）**。
可重跑：`git grep -n -i -E "investment basis|discount basis|bank discount|bond.equivalent" origin/main` → **0 命中**。
依外部知識（**未在 repo 查證**）：FRED 的 DGS3MO 是「3-Month Constant Maturity, Quoted on an **Investment Basis**」，也就是投資收益率（≈ bond-equivalent yield，actual/365 單利）；DTB3 才是 **Discount Basis**（貼現率）。

換算式（d＝貼現率、t＝到期天數 ≈91）：
- 價格 P ＝ 1 − d·t/360
- 投資收益率／BEY（t ≤ 182）：i ＝ (1/P − 1)·365/t ＝ 365·d/(360 − d·t)
- 貨幣市場收益率 MMY ＝ 360·d/(360 − d·t)
- 連續複利 c ＝ (365/t)·ln(1/P) ＝ (365/t)·ln(1 + i·t/365)
- 有效年利率 EAY ＝ (1 + i·t/365)^(365/t) − 1

數值例 d＝5%、t＝91：P＝0.987361、**i＝5.1343%**、MMY＝5.0640%、c＝5.1018%、EAY＝5.2341%。

**結論**：若 DGS3MO 確實是投資基礎，ρ_i ＝ i·Δd/365 就是一致的用法，**不必換算**。若改用 DTB3，必須先用 i 公式換算：5% 貼現率會被低估 0.13pp，σ＝15% 時 Sharpe 偏差約 +0.009。i 與 c 的差約 0.03pp，Sharpe 差約 0.002，可忽略。
⚠️ 採用前請協作助手確認報價基礎。

---

## 4. 年化（R3 的依據）

IID 下，單期 μ_p、σ_p，一年 f 期：年化均值 f·μ_p、年化變異 f·σ_p²，所以 S_ann ＝ √f·μ_p/σ_p。
**f 必須是「實際每年觀測數」**。現行固定 252；草稿提議 f̂ ＝ A ＝ N ÷ ((t_N − t_0)/365.25)。

**固定 √252 的偏誤因子 ＝ √(252/f)**（合成驗證，2000 次）：

| 每年觀測數 f | 偏誤因子 | E[S_252 − S_A] |
|---|---|---|
| 252 | 1.000 | 0.000 |
| 246（台股型日曆，**外部知識，未查證確切天數**） | 1.012 | ≈1% |
| 151（＝ sparse 閘門下限 coverage 0.6） | 1.292 | +0.151 |
| 52（週頻） | 2.201 | +0.639 |

**重點**：現行 sparse 閘門只在「併入累積歷史」時才跑（`finalize_fund_metrics`），coverage 0.6～1.0 的序列都會被放行，按 √252 年化最多可**高估 29%**。而 `tail(252)` 筆在 coverage 0.6 時實際橫跨約 1.67 年，卻標示「近 1 年」。
**rf 一致性**：mean(ρ_i)·A ＝ (r̄·T/365/N)·(N·365.25/T) ＝ r̄·365.25/365 ＝ r̄·1.000685。4% 時只差 +0.003pp，可忽略。若要求精確等於 r̄，ρ_i 的日數基礎改用 365.25，或 A 用 365。
**適用條件**：A＝N/年 在 IID 與「觀測頻率在窗內大致穩定」時成立。不處理報酬自相關（Lo 2002）。NAV 平滑或跨時區定價可能造成自相關，本單**不建議**本輪加入 Lo 校正，只登記。

---

## 5. 裁示項（每項：現行／疑點／建議式／影響／選項＋推薦）

符號：窗內第 i 期，i＝1..N；P_{t_i} 為配息還原 NAV（`s_tr`）；Δd_i ＝ t_i − t_{i−1}（日曆天）；T ＝ t_N − t_0（日曆天）。

### R1 報酬口徑（單檔）
- **現行**：`services/fund_service.py::calc_metrics` 的 log 報酬 `ln(s_tr_t/s_tr_{t−1})`，再減 simple 日 rf。
- **疑點**：log 減 simple 口徑混用；比 simple 低約 σ_ann/2，會讓 Sharpe 正負號翻轉（第 2 節）。
- **建議式**：R_i ＝ P_{t_i}/P_{t_{i−1}} − 1。
- **影響**：S1 與 S2 數值上升約 σ_ann/2；`Sharpe<0` 系列警示會在「超額報酬介於 0 與 σ²/2 之間」的基金上**消失**（這是更正，不是 fail-open）；Calmar／MaxDD 照舊用 log 累積（不受影響）。
- **選項**：(a) simple【**推薦**】；(b) 維持 log，但超額報酬改成 ln(1+R) − ln(1+ρ) 並在畫面標「對數口徑」。
- 與草稿：**一致**。

### R2 窗口與最小樣本
- **現行**：`tail(252)` 筆、N ≥ 250，sparse 檢查只在併入歷史時才做。
- **疑點**：窗口用「筆數」定義，稀疏時橫跨不止 1 年卻標「1Y」；live 序列本身稀疏時沒有閘門。
- **建議式**：窗口 ＝ 最後 252 筆報酬（沿用）；**加一道跨度檢查** T ≤ T_max（建議 400 日曆日），超過就 None，原因寫「窗口橫跨 T 天，非近一年」；或保留值，但 period_label 改寫成實際跨度。
- **影響**：只影響稀疏序列。
- **選項**：(a) 筆數窗＋跨度上限【**推薦**，T_max＝400 待裁】；(b) 改用 365 日曆日窗＋coverage 閘門。⚠️ 若選 (b)，N≥250 必須同步改，否則台灣交易日曆一年可能不足 250 筆，境內基金會**全被擋掉**（台灣每年交易日數未查證）；(c) 維持現狀。
- 與草稿：草稿「沿用 252 期＋N≥250」**一致，但草稿沒處理跨度問題**（補充）。

### R3 年化因子
- **現行**：固定 √252。
- **建議式**：A ＝ N / (T/365.25)；Sharpe ＝ mean(e)/sd(e)·√A。
- **影響**：稠密序列的變化 ≤ 約 1%；稀疏序列修正最多約 29%。
- **選項**：(a) A＝N/年【**推薦**】；(b) 固定 252，另加 coverage ≥ 0.9 閘門。
- 與草稿：**一致**。新增注意：σ 顯示（`std_1y` 等）仍用 √252，見 R13。

### R4 USD rf 定義 🔐（新 production 消費）
- **現行**：固定 4%（注入失效，見 0.2）；即使修好也是 FEDFUNDS「今天」單一值。
- **建議式**：
  - y_d ＝ 日曆日 d 往前 7 天內最後一筆 DGS3MO ÷100（沒有就缺）；
  - r̄ ＝ mean_{d∈(t_0, t_N], y_d 不缺} y_d；
  - ρ_i ＝ r̄·Δd_i/365；e_i ＝ R_i − ρ_i；
  - Sharpe ＝ mean(e)/sd(e, ddof=1)·√A；
  - 覆蓋率 cov_rf ＝ #{d: y_d 不缺}/T。cov_rf < X → `rf_status="rf_insufficient"` → Sharpe／Sortino ＝ None（但適用 R7 的符號界）。**缺 rf 不得刪報酬。**
- **疑點**：DGS3MO 報價基礎未查證（第 3 節）；X 待定。
- **建議 X**：0.95，並且「窗末往前 7 天內必須有觀測」。理由：7 天回看已吸收週末與美國假日，覆蓋率合理值應接近 1；低於 0.95 代表資料停更。
- **影響**：USD 基金的自算 Sharpe（只在沒有 wb07 時才使用）以及全部 Sortino。
- **選項**：(a) DGS3MO＋r̄ 窗均【**推薦**】；(b) DGS3MO 逐期 ρ_i^exact；(c) DTB3（須用 BEY 換算）。
- 與草稿：**一致**（補了 X 的建議值與報價換算）。

### R5 USD rf 的資料路徑 🔐
- **現行**：Sharpe 不讀任何 rf 序列。
- **候選**：(a) 讀 `data_cache/fred_indicators.parquet`（production 目前**只寫不讀**，新鮮度靠 workflow 回寫）；(b) 沿用 production 已經在即時抓的 `fetch_fred("DGS3MO", ..., 2600)`（`services/macro/us_indicators.py:536`），由 L2 從 L1 取回序列；(c) 兩者並用（即時為主、parquet 為備）。
- **疑點**：(a) 有過期風險；(b) 需要 FRED key，週推播 script 要另外接；兩者的 `ccy_source` 都還要上游處理。
- **推薦**：**(c)**，兩者都要求帶 `source`／`fetched_at`／`as_of` provenance。⚠️ 這是**新的 production 消費路徑**，**須客戶授權**；資料源本身（FRED DGS3MO）已在 production 使用，不是新外部來源。
- 與草稿：**不一致**。草稿只列 parquet，沒有評估「production 只寫不讀」的事實，也沒有列即時路徑。

### R6 TWD／未知幣別 🔐（TWD rf 屬新資料源）
- **現行**：一律套 4%。
- **建議**：幣別 ∈ {TWD, 未知} 且沒有核准的 rf 時 → Sharpe／Sortino ＝ None，`rf_status="no_rf_for_ccy"`，畫面標「無對應無風險利率」。不得用 4%、不得用 0 卻仍叫 Sharpe、不得借 USD rf。幣別輸入用 `nav_series_currency(s)`（未知回 `""`）＋上游 `ccy_source`；**名稱推定或預設得到的 USD，一律視為未知**。
- **影響**：境內基金（無 wb07）全部 None，詳見 1.1。
- **選項**：(a) None＋R7 符號界【**推薦**】；(b) 等 TWD rf 來源核准後再上線整包；(c) 暫用 rf＝0 但**改名**為「報酬波動比（未扣無風險利率）」，不叫 Sharpe。
- 與草稿：**一致**，另補「既有 attrs 通道」與 R7 的補救。

### R7 防 fail-open（符號界＋悲觀下界）
- **現行**：None 會讓多個消費端（1.1 列出 + 4 處遺漏）的警示消失或分數變好。
- **推導**：S(ρ) ＝ (mean(R) − ρ̄)/sd(R − ρ)。rf 為常數或變動很小時，sd(R−ρ) ≈ sd(R)，S 對 ρ̄ 單調遞減。所以只要該幣別在窗內 **rf ≥ 0**：
  **S_ub ≡ mean(R)/sd(R)·√A < 0 ⇒ 任何 rf ≥ 0 下 Sharpe < 0**，而且 Sortino（MAR＝ρ）同號。
  不需要知道 rf 值，就能嚴格保留所有「Sharpe < 0」型警示。
- **建議**：
  1. 計算 `sharpe_upper_bound`（rf＝0），只在 ccy＝TWD 時使用（台灣利率歷來為正：**外部知識，未查證**；未知幣別可能是 JPY／EUR 這類曾經負利率的幣別，不適用）；
  2. S_ub < 0 → `sharpe_sign="negative_certain"`：`tag_health_check` → Sharpe_Warning、`switch_signal` 紅燈條件、規則 (d)、`_score_sharpe` → 15 分（因為 Sharpe < 0 時恆為 15，這是精確值），全部照舊觸發；
  3. S_ub ≥ 0（符號不確定）→ 分數類消費端（4D、六因子、A1 品質分）採**悲觀下界**：該維度以最低檔計分，或該檔 grade 標「不完整，不得升級」。這與既有 `_coverage_blocks_green` 的「悲觀下界」模式一致；
  4. `market_regime_alert` 的分母排除 None 時要揭露 n。
- **殘餘風險**（如實揭露）：0 < 年化報酬 < rf_TWD 的基金，真實 Sharpe < 0，但 S_ub ≥ 0，警示仍會漏掉（僅限報酬落在約 0～rf 這一窄帶的基金）。
- **選項**：(a) 符號界＋悲觀下界【**推薦**】；(b) 只做符號界；(c) 什麼都不做，只標 None（**不推薦**：F→D 會把汰換紅燈關掉）。
- 與草稿：草稿只寫「需補救方案，是否以上界保留紅燈待裁」。本單給出嚴格條件（rf≥0）與推導，並補上草稿漏列的 4 處消費端。

### R8 Sortino
- **建議式**：同一組 e_i；σ_D ＝ √((1/N)·Σ min(0, e_i)²)；Sortino ＝ mean(e)/σ_D·√A；保留「低於 MAR 的筆數 ≥ 5」與 σ＝0 守衛。
- 與草稿：**一致**。

### R9 ddof
- Sharpe 的分母用 ddof＝1（樣本標準差）；TDD 用 1/N（依 Kidd 定義）。兩者差 √((N−1)/N) ≈ 0.998，可忽略。**維持現行**，在定義字串中寫明。

### R10 舊 rf 機制退場
- 範圍：`services/fund_service.py` 的 `_RF_ANNUAL`／`set_risk_free_rate`；`app.py:366-388`；`ui/tab1_macro.py:2111`（死碼）；`fund_fetcher.py:316` 的 re-export；相關測試（0 節與第 1 節 A 類列出）；週推播改用同一個 rf 函式。
- **推薦**：一次退場，不留 4% 預設（否則就是第二份 SSOT）。

### R11 組合層與效率前緣（**只登記，不在本輪範圍**）
- S3 的分子是幾何 CAGR（≈ log 口徑），R1 改成 simple 後，單檔與組合會差約 σ²/2 級。
- S3 與 S4 都用 rf＝0 卻叫 Sharpe，與 R6 原則衝突。目前畫面有揭露「無風險利率 0.0%」。
- S4 前緣用**原幣混算**（沒有傳幣別／匯率）。
- 組合 Sharpe 有持久化（`_portfolio_perf_history`）；日後改口徑時需處理歷史列。
- **建議**：另案裁示。

### R12 wb07 與自算混在同一欄（**只登記**）
- 同一欄「Sharpe 1Y」混合了 MoneyDJ 官方值（定義、rf、頻率都**未查證**）與自算值。跨檔排序（A1 品質、替換候選 argmax）會比較不同口徑的數字。`reconcile_sharpe` 的容差 0.1 也是在比較不同定義。
- **建議**：另案；至少在 R14 的揭露中說明。

### R13 σ 顯示的年化一致性（**只登記**）
- `std_1y` 等仍是 log 報酬 ×√252。Sharpe 改成 simple＋√A 後，畫面上 Sharpe ≠ 年化報酬 ÷ 顯示的 σ。建議日後同步，或在 help 中註明。

### R14 揭露與相容性
- 口徑變更日寫進 `risk_metric_meta["sharpe"]["definition"]`／`rf_status`／`rf_source`／`rf_as_of`；`reconcile_sharpe` 的 `source_a` 字串同步改；畫面註明「自 YYYY-MM-DD 起改為簡單報酬＋DGS3MO 窗均」。
- 單檔 Sharpe 沒有持久化，**不需要資料遷移**。

---

## 6. 與草稿的差異清單

**一致**：報酬用 simple（R1）、r̄ 窗均＋Δd/365（R4）、A＝N/年（R3）、Sortino 用同一個 e（R8）、TWD／未知 → None 且禁止三種替代（R6）、缺 rf 不刪報酬、單檔 Sharpe 未持久化。

**不一致或補充**：
1. B 類路徑：草稿只列 parquet；本單指出它在 production「只寫不讀」，並提出即時 FRED 路徑（R5）。
2. C 類漏列 4 處：`calc_fund_factor_score`、A1 `quality.py`、`market_regime_alert`、`switch_advisor` redlight（第 1 節）。
3. 4D fail-open 比草稿描述的嚴重：F→D 會把汰換規則 (b) 的紅燈關掉（1.1 數值例）。
4. 補救方案：給出 rf≥0 的嚴格符號界與悲觀下界（R7），草稿只列為待裁。
5. 窗口跨度：草稿沒處理稀疏序列「252 筆 ≠ 1 年」的問題（R2）。
6. A 類漏列：`reconcile_sharpe` 出處字串、docstring 公式表、σ 年化一致性、鎖住 re-export 的測試。
7. 0.2 補充：即使修好注入 key，注入的也是 FEDFUNDS「今天」單一值，所以修 key 不是解法。
8. 組合層：草稿沒提到組合 Sharpe 有持久化，也沒提到 S3 分子是幾何 CAGR、S4 原幣混算（R11）。
9. 新增 X 的建議值（0.95＋窗末 7 天內必須有觀測），以及 DTB3 換算式（第 3 節）。

---

## 7. 本組沒有查證的部分

- AppTest 離線實驗（新 key 0.04／舊 key 0.0363）**未重跑**，只做了靜態證據。
- DGS3MO 報價基礎、起日（2011-06）與頻率：本機沒有 pyarrow，parquet **讀不出來**；報價基礎屬外部知識。
- MoneyDJ wb07 Sharpe 的定義。
- 台灣利率歷來 ≥ 0、台灣每年交易日數：外部知識。
- user 5 檔境內持倉的計價幣別。
- 「全站計算點只有 S1～S4」「寫入 `indicators` 只有兩處」：字面 grep 掃不到動態寫法。
- `ui/helpers/portfolio_perf.py` 前緣在新舊頁面的 production 可達性，沒有逐條驗證。
- 合成資料的數值是示意（常態 IID），不是本專案實際基金。
