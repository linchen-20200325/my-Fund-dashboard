"""v19.74 Signal / Score Thresholds SSOT — Fund-Const W2 群收斂.

對應 Stock 端 `shared/signal_thresholds.py`,Fund 版聚焦基金 + macro 域。

Inline magic 散落 services/* 多檔,集中為語意常數(命名強制帶單位後綴避免 §4.1 量綱陷阱)。

排除:
  - test_*.py:依測試契約保留字面值
  - macro_validation.py SCORE_RULES / MACRO_THRESHOLDS dict 已在 repositories/services
    自有 SSOT 結構,本檔不重複(zone 範圍邊界仍走原 SSOT)

caller 用法:
    from shared.signal_thresholds import TRADING_DAYS_PER_YEAR, SAHM_RECESSION_THRESHOLD

    annualized_std = daily_std * math.sqrt(TRADING_DAYS_PER_YEAR)
    if sahm_v >= SAHM_RECESSION_THRESHOLD: ...
"""
from __future__ import annotations

# ── 年化常數(交易日 vs 日曆日,§4.1 陷阱)──────────────────────
TRADING_DAYS_PER_YEAR: int = 252
# Sharpe / std 年化、1Y rolling window 一律使用此常數(non-Fund-trading-calendar 場合用 365)

# ── 衰退判讀(§3.2 + §3.3)─────────────────────────────────
SAHM_RECESSION_THRESHOLD: float = 0.5
# 失業率 3MA - 過去 12M 最低 ≥ 0.5pp → 衰退中(Fed Sahm rule 原始定義)

# ── 景氣位階「資料充足性」門檻(2026-09-04 第三輪稽核 A1)────────────────────
# `services/macro/us_indicators.py::calc_macro_phase` 的正規化是
#     norm = (earned_w + total_w) / (2 * total_w) * 10
# —— 分母 `total_w` 只由**當次抓到的**指標累加。它有兩個後果:
#   (a) `total_w == 0` 時走 `else: norm = 5` → **零觀測** 直接落在「擴張」帶
#       (score ≥ 5),連帶吐出綠色 `phase_color` 與可據以行動的 `advice`;
#   (b) `total_w` 很小時,**單一指標**就能把分數掃過整個 0~10。
# 兩者都不是「經濟的判讀」,而是「哪幾支 fetcher 剛好活著」的判讀。
#
# 門檻怎麼來的(**推導,不是校準** —— 這一點對後人很重要):
#   單一權重 w 的指標由 -w 翻到 +w,會讓正規化分數移動
#       Δ = 2w / (2 * total_w) * 10 = 10w / total_w
#   本檔案家族裡單一指標的**最大權重是 2**(殖利率曲線 10Y-2Y / 10Y-3M、PMI、
#   HY 信用利差),故最壞情況 Δ_max = 20 / total_w。
#   而 `calc_macro_phase` 的相位邊界最窄的一段是 **復甦(≥3)→ 擴張(≥5)**,
#   相隔 **2 分**。要求「單一指標的有無/翻向不足以把相位推過那道邊界」:
#       20 / total_w < 2   ⟺   total_w > 10
#   健康抓取時權重總和 ~19(見 `calc_macro_phase` docstring 的 meta 污染估算),
#   本門檻約當其 53%,正常運作**不會**觸發。
#
# ⚠️ 這個數字是工程判斷的推導值,**不是**對歷史資料做過的校準,也**沒有**客戶拍板。
#    它可能太鬆(7 個 Yahoo 指標湊到 total_w>10,但全是市場面、沒有任何實體經濟
#    指標,一樣算不出「景氣位階」)。組成面(不只筆數)的疑慮已登記於
#    `BACKLOG.md`「⏸ 待客戶裁示 — 景氣位階卡的組成與線框不符」。
MACRO_PHASE_MIN_TOTAL_WEIGHT: float = 10.0
CFNAI_RECESSION_THRESHOLD: float = -0.7
# ⚠️ 適用對象是 **CFNAI-MA3**(三月移動平均),**不是**月度 CFNAI —— 月度序列波動度約為
# MA3 的 √3 ≈ 1.7 倍,拿 -0.7 去砍月度值會製造大量假衰退訊號。caller 務必先算 3M MA。
# 官方原文(Chicago Fed CFNAI background PDF, p.2):
#   "an increasing likelihood of a recession has historically been associated with a
#    CFNAI-MA3 value below -0.70 following a period of economic expansion."
# https://www.chicagofed.org/-/media/publications/cfnai/background/cfnai-background-pdf.pdf
CFNAI_MA3_EXPANSION_THRESHOLD: float = 0.20
# 官方非對稱含遲滯設計的另一半:衰退門檻 -0.70 / 擴張門檻 +0.20(不是 ±對稱)。
# 官方原文(同一份 background PDF):
#   "a significant likelihood of an expansion has historically been associated with a
#    CFNAI-MA3 value above +0.20 following a period of economic contraction."
# ⚠️ 常被誤用的 -0.35 是 **CFNAI Diffusion Index**(擴散指標,另一條完全不同的序列)的
#    擴張門檻 —— "Periods of economic expansion have historically been associated with
#    values of the CFNAI Diffusion Index above -0.35." 與 CFNAI 水準值無關,禁止混用。
# 現值參考(2026-06):CFNAI = -0.02 / CFNAI-MA3 = -0.05
# https://www.chicagofed.org/research/data/cfnai/current-data
CFNAI_TREND_GROWTH: float = 0.0
# CFNAI(含 MA3)= 0 代表「經濟以歷史趨勢速度成長」;負值 = 低於趨勢,正值 = 高於趨勢。
# 這是官方定義的零點,非設計值,供「低於趨勢」黃燈使用(介於 -0.70 與 +0.20 之間的中間帶)。
RECESSION_LOGIT_COEF_SPREAD: float = -1.5
RECESSION_LOGIT_COEF_INTERCEPT: float = -0.8
# logit = SPREAD_COEF * spread_10y3m + INTERCEPT,經 sigmoid → recession probability

# ── Shadow fund 相似度(portfolio_service.py:424,§3.3)─────────
SHADOW_FUND_THRESHOLD_RATIO: float = 0.70
# composite score > 0.70 → 警示「影子基金」(高度雷同的不同基金)
SHADOW_FUND_JACCARD_WEIGHT_RATIO: float = 0.6
SHADOW_FUND_COSINE_WEIGHT_RATIO: float = 0.4
# composite = jaccard * JACCARD_W + cosine * COSINE_W,JACCARD_W + COSINE_W = 1.0
SHADOW_FUND_NAV_CORR_THRESHOLD_RATIO: float = 0.85
# v19.289:NAV 漲跌幅 Pearson |r| ≥ 0.85 → 警示「走勢同步」影子基金(不同於持股重疊,
# 是另一種曝險維度:即使持股完全不同,若同受單一總經因子驅動,回撤時仍會齊跌)。
# 原本 inline 於 portfolio_service.py::calc_correlation_matrix 與其 UI caller,收 SSOT。

# ── 同質化分級(services/homogeneity.py,2026-08-31 客戶 Q2 拍板)─────────
# 同質化比率 = 高相關警示對數(兩維度**聯集**)÷ 實際比對**成功**對數(聯集)。
# 分母刻意用「成功對數」而非理論對數 N×(N−1)/2:缺資料的對不入分母,
# 比率不被虛增也不被稀釋(§1 不造假)。
# 分級:0 對 → 低(🟢);>0 且 ≤ MID_MAX → 中(🟡);> MID_MAX → 高(🔴)。
# 20% 的直覺:「五對裡有一對互為影子就該警覺」(客戶 2026-08-31 Q2 拍板原文)。
HOMOGENEITY_MID_MAX_RATIO: float = 0.20
# 成功對數 < 此 → 不給等級,顯示 ⬜「樣本不足」,不硬判(客戶 Q2 拍板:< 3 對不硬判)。
HOMOGENEITY_MIN_PAIRS: int = 3

# ── 配息接近警戒(fund_service.py:279, fund_dividend_calculator.py:23)──
NEAR_DIVIDEND_WARNING_PCT: float = 2.0
# 配息年化率距離警戒線(年率 6%/8%)≤ 2pp → near zone,UI 標黃
# v19.175:同時兼任「吃本金 gap 容差」— gap = div - ret > 2pp → 🔴 吃本金

# ── 年化最小歷史長度(fund_dividend_calculator.py:207,v19.175)──────
MIN_YEARS_FOR_ANNUALIZE: float = 0.5
# 持有歷史 < 0.5 年不年化(避免「2 個月配息 × 6 倍」變 30% 高配息幻象,
# 對應 老師「買舊不買新」警告 + §1 Fail Loud 不偽造數字),
# 全期自算欄位顯示「—」+ 燈號顯示「⬜ 歷史不足」

# ── Max Drawdown 評分門檻(portfolio_service.py:95,v19.176)──────────
MAX_DRAWDOWN_ZERO_SCORE_PCT: float = -30.0
# Max DD 0% → score 100 / -30% → score 0,線性內插。
# portfolio_service 6 因子健康度的「回撤評分」分母。
# 不是 alert 紅燈門檻(那是各 UI 自定義),純評分用。

# ── 淨值跌警示門檻(portfolio_service.dividend_safety:222,v19.176)──
NAV_DROP_WARNING_PCT: float = -5.0
# 1Y 淨值跌幅 < -5% → 觸發 nav_warning 旗標,提示「配息源頭值得確認」。
# 對應「配息可能來自本金」的早期警訊,獨立於吃本金主判定。

# ── MoneyDJ 資料新鮮度燈號門檻(ui/helpers/freshness.py:28-32,v19.176)──
MJ_FRESH_DAYS_GREEN: int = 2
MJ_FRESH_DAYS_YELLOW: int = 7
# NAV 延遲天數:🟢 ≤ 2d / 🟠 ≤ 7d / 🔴 > 7d。
# 基金 NAV T+1~T+3 公布,7 天放寬覆蓋連假;> 7d 視為資料異常需確認。

# ── 基金健康度 4D 評分 Grade cutoffs(services/fund_health.py,v19.177 #4B)──
GRADE_CUTOFFS_4D: tuple[int, int, int, int] = (80, 65, 50, 35)
# v19.422 §1:4D 評等最低維度數 —— 不足(或缺配息+Sharpe 兩核心維度)→「資料不足以評等」,
# 不再用單一維度(如僅 σ)硬給 A(稽核 Bug1:資料稀疏基金被評「健康優質」排在完整分析之上)
GRADE_4D_MIN_FACTORS: int = 2
# A ≥ 80 / B ≥ 65 / C ≥ 50 / D ≥ 35 / F < 35。
# 全站個檔基金健康度評等 SSOT(Tab2 KPI 卡 / Tab3 fund 評等共用),
# 取代 portfolio_service 6 因子 (75, 55, 40) 三級制(已 deprecated for grading,
# 6F dict 仍保留供 Sortino / Calmar / Alpha / 費用率單獨顯示)。

# ── 換標的建議  4 規則門檻(services/fund_replacement_verdict.py,v19.181)──
# 任一規則中 → 🔴 建議換 / 1-2 條件靈領未達 hard trigger → 🟡 觀察 / 全未中 → 🟢 保留
REPLACE_RULE_A_MIN_HOLD_YEARS: float = 1.0
# (a) 吃本金 1Y·且持有 ≥ 1 年 — < 1 年不算(短期 NAV 波動正常)
REPLACE_RULE_C_MIN_HOLD_YEARS: float = 3.0
# (c) 3-3-3 未通過且持有 ≥ 3 年 — < 3 年屬於「還沒驗證期」,不該據此換
REPLACE_RULE_D_SHARPE_MAX: float = 0.0
REPLACE_RULE_D_MAX_DD_MIN_PCT: float = -30.0
# (d) Sharpe < 0 且 max_dd < -30%(極差雙條件)
REPLACE_OBSERVE_GRADE: str = "D"
# 4D Grade D 是「警示偏弱」(C/D 邊緣),計 1 個觀察分;F < 35 計 1 個 hard trigger

# ── Risk score 加權(precision_service.py:64, risk_calibration.py:23)─
RISK_SCORE_VIX_WEIGHT_RATIO: float = 0.3
RISK_SCORE_HY_WEIGHT_RATIO: float = 0.4
RISK_SCORE_YIELD_WEIGHT_RATIO: float = 0.3
# risk_score = z_vix * VIX_W + z_hy * HY_W + z_yield * YIELD_W,sum = 1.0

# ── Liquidity stress 加權(liquidity_engine.py:44)────────────────
LIQUIDITY_XCCY_WEIGHT_RATIO: float = 0.4
LIQUIDITY_CARRY_WEIGHT_RATIO: float = 0.3
LIQUIDITY_MOVE_WEIGHT_RATIO: float = 0.3
# liq_score = z_xccy * XCCY_W + z_carry * CARRY_W + z_move * MOVE_W,sum = 1.0

# ── (2026-08-07 移除)台股 TPI 三權重常數 ──────────────────────────
# 說明書章節下架後全站零計算、零渲染,只剩「定義 → import → re-export」三處;
# 且 business / financial / monetary 的切法與原章節寫的 Breadth / FII / M1B
# 語意不符,日後若真要實作也不會沿用這組公式。依 `PROCESS.md §4` 0-consumer
# 條款刪除,不留一組指向不存在功能的常數。

# ── σ verdict cutoffs(macro_explain.py:64-76,§4.1 sign convention)
SIGMA_VERY_HIGH_CUTOFF: float = 1.5
SIGMA_HIGH_CUTOFF: float = 0.8
SIGMA_LOW_CUTOFF: float = 0.3
# 正號 = 偏空(風險升、抑制成長);負號 = 偏多(寬鬆、利成長)
# score >= +1.5σ → 強烈偏空 / +0.8 ~ +1.5 → 偏空 / +0.3 ~ +0.8 → 略偏空
# -0.3 ~ +0.3 → 中性 / -0.8 ~ -0.3 → 略偏多 / -1.5 ~ -0.8 → 偏多 / <= -1.5 → 強烈偏多

# ── Holdings NAV sanity bounds(fund_service.py:239-240)────────────
HOLDINGS_NAV_SANITY_LOWER_RATIO: float = 0.3
HOLDINGS_NAV_SANITY_UPPER_RATIO: float = 3.0
# parsing error 防呆:持股 NAV 比應在 [0.3x, 3.0x] 主要 NAV 之間,否則視為解析錯誤

# ── US CPI YoY 絕對分區(macro_tw_local.py:150-157, W5-4 §3.3)──
# Fed 通膨目標 2%;單位 %YoY
# ≤ IDEAL: +2 / ≤ MILD: +1 / ≤ NEUTRAL: 0 / ≤ ELEVATED: -1 / > ELEVATED: -2
CPI_YOY_IDEAL_MAX_PCT: float = 2.0
CPI_YOY_MILD_MAX_PCT: float = 3.0
CPI_YOY_NEUTRAL_MAX_PCT: float = 4.0
CPI_YOY_ELEVATED_MAX_PCT: float = 5.0

# ── CPI 月變化 MoM 分區(macro_tw_local.py:354-365, 動能指標)──
# Δ ≤ STRONG_DROP: +2 / ≤ MILD_DROP: +1 / |Δ| ≤ FLAT: 0 / ≤ MILD_RISE: -1 / > MILD_RISE: -2
CPI_MOM_STRONG_DROP_PCT: float = -0.3
CPI_MOM_MILD_DROP_PCT: float = -0.1
CPI_MOM_FLAT_MAX_PCT: float = 0.1
CPI_MOM_MILD_RISE_PCT: float = 0.3

# ── nav_history 累積序列覆蓋門檻(fund_service.assess_series_coverage,v19.360 B+②)──
# App 端累積(v19.359 Track 2)為不規則取樣;年化指標(×√252)假設每點=1 交易日,
# 序列稀疏時會失真 → §1 寧可回 None 不給假精確。
NAV_HIST_COVERAGE_MIN: float = 0.6      # 實際點數 / 預期交易日(span×252/365)下限
NAV_HIST_MAX_GAP_DAYS: int = 14         # 相鄰兩點最大缺口(日曆日;台灣長假 ~9-10 天)

# ── 「近30日」短窗判定(fund_orchestration waterfall,2026-08-11 user 拍板)──────
# 背景:`_src_tcb_nav`(waterfall 順位 2c)抓不到長歷史時,會把 MoneyDJ 主頁上的
# 「近30日淨值表」**掛在自己名下**回傳(sources.py 第三段)。waterfall 的 gate 只數
# 筆數(≥10)不看跨度 → 30 筆短窗直接鎖定,後面 2c2/2d/2e… 一次都沒被試過。
# 線上實證(ACCP138):`[fetch] ✅ 主路線成功（src:tcb_moneydj nav=30筆）`,跨度 42 天,
# 而 3Y 年化需 756 點、Sharpe 250、MaxDD 125、σ 252 → 全數留白。
# 判定跨度 < 本值 = 短窗 → 不讓它滿足 gate,改讓**非 MoneyDJ** 來源再試一次
# (user 2026-08-11 拍板:不增加對 MoneyDJ 的請求數;MoneyDJ robots.txt 禁 LLM/AI 用途)。
# 90 天 = 3 個月:近30日表(~42 天)必落在內;真長歷史(2000 天窗)遠大於此,不誤判。
NAV_SHORT_WINDOW_MAX_DAYS: int = 90

# ── 1Y 含息報酬 合理性閘(services/fund_total_return.py;2026-08-14 稽核 E1)────────
# 實測病徵:組合健診大表有兩檔**台幣計價**基金的「1Y 含息報酬」印出 +201.65% / +190.64%。
# 台幣計價的一般共同基金一年翻兩倍在現實中幾乎不存在,而畫面上它就是一個普通數字,
# 排序時直接衝到最上面 —— 使用者會把它當成「今年最會賺的」而加碼。
#
# 根因在 `compute_1y_total_return()` 的第 4 層 fallback:拿 NAV 序列**最短 30 天**
# 的漲幅,乘上 `min(365/實際天數, 12)` 外推成「一年報酬」。30 天漲 17% → 印 +201%。
# 這正是 §1 明文禁止的「自行估一個合理值」:它不是量出來的,是乘出來的。
# (v19.448 已認定這層「最不可靠」並讓吃本金判定拒用,但**數字本身照印**。)
#
# 兩道閘:
#  (1) 外推門檻 —— 資料跨度未達 MIN_DAYS 就**不推**,誠實回 None(§1 寧可留白)。
#      180 天 = 半年,scale 上限自然落在 365/180 ≈ 2.03 → MAX_SCALE 取 2.0 對齊。
#      原本的 30 天 ×12 是「一個月的運氣乘以十二」,沒有統計意義。
#  (2) 合理性帶 —— 不分來源(含 MoneyDJ 官方值)做離譜值標記。**不改值、不丟值**,
#      只是讓來源標籤帶上警語,讓表格與評分端知道這格要打問號(§1 標記而非掩蓋)。
#      上界 150%:真有這種基金(單一產業/槓桿)但極罕見,值得使用者停下來看一眼。
#      下界 −95%:跌超過 95% 幾乎必是幣別 / 除息切割 / 分割換單位造成的口徑錯誤。
RET_1Y_EXTRAPOLATE_MIN_DAYS: int = 180
RET_1Y_EXTRAPOLATE_MAX_SCALE: float = 2.0
RET_1Y_PLAUSIBLE_MAX_PCT: float = 150.0
RET_1Y_PLAUSIBLE_MIN_PCT: float = -95.0

# ── Composite 對帳:不加權方向投票中性帶(macro composite_score,v19.367 6/8)──
# F-RECON-1 最後一項:健康度雙演算法對帳。第二演算法 = 不加權多空投票
# net_ratio=(n_pos-n_neg)/n_valid;|net_ratio| <= 本帶寬 → 方向視為中性(60/40 不算決定性)
COMPOSITE_VOTE_NEUTRAL_BAND: float = 0.2

# ── 上/下檔捕捉率 + 操盤評分(services/capture_ratio.py,v19.414;v19.419 放寬)──────
# 大盤上漲月 / 下跌月任一組月數 < 本值 → 三值 None(§4.6 短歷史不給假精確)。
# v19.419:user 2026-07-28 核准 6→3(貼近高點/短歷史的基金跌月常 <6 → 全留白)。
# 3–5 月為「參考值」(下檔捕捉樣本少較噪),≥ ROBUST 才算穩健(表註明,§1 誠實)。
CAPTURE_MIN_MONTHS: int = 3
CAPTURE_ROBUST_MONTHS: int = 6      # 漲跌月各 ≥ 本值 = 穩健;3–5 = 參考值(low confidence)
# 操盤評分中心 = 上下檔捕捉率相等時的基準分:score = clamp(BASE + (上檔 − 下檔)/2, 0, 100)
CAPTURE_SCORE_BASE: float = 50.0

# ── 基金 vs 大盤比較:純價格報酬差 + 疊圖窗口(services/benchmark_compare.py,v19.420)──
# 近 1 年(日曆日,asof 對齊不規則 NAV);共同歷史 < 本值 → 用全期並標 full_period(§1)
BENCHMARK_WINDOW_DAYS: int = 365

# ── 效率前緣診斷(services/portfolio_frontier.py,v19.424;教學非建議)────────────
FRONTIER_RF_ANNUAL: float = 0.0        # 無風險利率(年,decimal);與 performance_metrics 一致
FRONTIER_N_RANDOM: int = 3000          # 蒙地卡羅隨機組合雲點數(向量化)
FRONTIER_GRID_SIZE: int = 40           # 效率前緣目標報酬格點數(min μ → max μ)
FRONTIER_MIN_OBS: int = 60             # 共同交易日 < 本值 → 不計算(§1 樣本太少不給假精確)
FRONTIER_ROBUST_OBS: int = 252         # < 本值(1 年)→ low_confidence 旗標
FRONTIER_RANDOM_SEED: int = 42         # 隨機雲種子(可重現,§5)
FRONTIER_COND_MAX: float = 1e10        # cond(Σ) > 本值 → near_singular 旗標 + 微脊
FRONTIER_RIDGE_EPS: float = 1e-8       # 微脊 = eps × mean(diag Σ);僅 near_singular 加,ridge_applied 揭露
FRONTIER_MU_SPREAD_MIN: float = 1e-6   # max(μ)−min(μ) < 本值 → mu_degenerate(前緣退化單點)

# ── 匯率位階 σ 切點 + 回看窗(services/nav_fx_switch.py,v19.426)──
# USDTWD 現值相對「近一年均值」的 z-score。sign convention(§4.1):
#   z 負 = USDTWD 低於均值 = 台幣強(TWD→USD 換匯便宜)= 進場有利
#   z 正 = USDTWD 高於均值 = 台幣弱(換回 TWD 划算)      = 出場有利
# 與 NAV σ rank 同向:兩軸皆「愈負 = 愈進場有利」。
FX_REGIME_WINDOW_DAYS: int = 365   # 回看窗(日曆日;≈250 交易日,對齊 NAV 252 lookback)
FX_REGIME_MIN_OBS: int = 60        # 有效點 < 此 → ⬜ 無法判定(§1 短歷史不假精確)
FX_REGIME_ROBUST_OBS: int = 180    # < 此 → low-confidence(仍顯示,標「*」參考)
FX_STRONG_TWD_SIGMA: float = -0.7  # z ≤ 此 → 台幣強
FX_WEAK_TWD_SIGMA: float = 0.7     # z ≥ 此 → 台幣弱

# ── 匯率風險維度切點(健康度第 5 維,services/health/grade.py;2026-08-14 Layer 3-C)──
# 量的是「**這檔基金的台幣報酬有多少會被匯率搖動**」,不是「現在匯率貴不貴」——
# 後者已由「匯率位階」欄負責(z-score vs 近一年均值,見上一組常數)。
#
# 指標 = 變異係數 CV% = std(匯率) / mean(匯率) × 100,取 `fx_regime()` 已算好的
# std 與 mean(§2.1 不另算一份)。用 CV 而非絕對 std 的原因:USDTWD ≈ 32、
# JPYTWD ≈ 0.21,絕對 std 差兩個數量級,直接比大小是 §4.1 量綱錯誤。
#
# 切點依台幣視角的實務區間:USDTWD 年 CV 約 2~4%(最穩),EUR/JPY 約 4~7%,
# ZAR 等高息貨幣可到 10%+ —— 那正是「配息很高但吃匯損」的典型陷阱,
# 也是這一維存在的理由。
# ⚠️ 台幣計價基金為 **N/A(不適用)**,不是 0 分也不是缺資料:
#    它沒有匯率風險是事實,評分時必須從分母移除,給 0 分等於懲罰一個優點。
# ── nav_history 回填衝突偵測(services/fundclear_backfill.py;2026-08-14 稽核 E6)──
# 病徵:「補歷史淨值」把 FundClear 抓到的數千筆淨值直接寫進 Google Sheet 的
# nav_history 分頁 —— **零預覽、零確認、無 dry-run、無 rollback**,
# 而說明書對那個分頁的註記是「🚨 絕對不要刪…無法從任何來源重建」。
#
# 真正致命的是去重鍵只有 `(code, date)`:同一檔基金常有多個級別
# (美元累積 / 美元配息 / 歐元避險…),淨值完全不同。選錯級別寫進去之後,
# **正確級別的淨值會被當成重複而永遠寫不進來** —— 而且錯的那份會被健診
# 拿去算 1Y 報酬、Sharpe、σ。使用者不會收到任何警告。
#
# 對策:寫入前先比對「同一 code 已存在的日期」。重疊日的淨值若差異超過本容差,
# 幾乎可以確定是**不同級別**(同級別的差異只該來自四捨五入)。
# 1% 是刻意寬鬆的 —— 目的是抓「差一個級別」(通常差 5~30%),不是抓小數點誤差。
NAV_BACKFILL_CONFLICT_REL_TOL: float = 0.01

FX_RISK_CV_LOW_PCT: float = 3.0      # < 此 → 90 分(很穩)
FX_RISK_CV_MILD_PCT: float = 5.0     # < 此 → 70
FX_RISK_CV_MID_PCT: float = 8.0      # < 此 → 50
FX_RISK_CV_HIGH_PCT: float = 12.0    # < 此 → 30;≥ 此 → 15(匯損足以吃掉配息)

# ── 輪動配對 σ 基期切點 + 買方健康門檻(services/rotation.py,v19.415)──
# σ rank = 現價在期間高點下方第幾個 σ(負值愈深愈低基期)。跨產業/性質輪動:
# σ rank ≥ SELL_SIGMA → 高基期(貼近高點=賣);≤ BUY_SIGMA → 低基期(深跌=買)
ROTATION_SELL_SIGMA: float = -0.5
ROTATION_BUY_SIGMA: float = -1.5
# 買方健康過濾:操盤評分若有值須 ≥ 本門檻才推薦(fail-closed,§1 避免接刀)
ROTATION_BUY_MIN_SCORE: float = 50.0

# ── 配置回測(services/allocation_backtest.py,v19.427)──────────────────
# 給 N 檔基金 + 歷史,回測數套配置/切換策略在「台幣總報酬」下表現,排名效益最高者。
# 反 lookahead(§2.3):每個再平衡日只用截至當日資料算訊號;成本內含避免切換被高估(§1 誠實)。
BACKTEST_REBALANCE_FREQ: str = "ME"     # 月頻(月底最後交易日)再平衡;closed/label 右閉不引未來
BACKTEST_COST_BPS: float = 20.0         # 申購/贖回/轉換 一次性成本(bps),按換手率收
BACKTEST_FX_SPREAD_BPS: float = 30.0    # TWD↔外幣 換匯點差(bps),按外幣部位換手率額外收
BACKTEST_TILT_BUY: float = 1.5          # buy tier 相對等權放大倍數(非全進,避免單檔爆權重)
BACKTEST_TILT_SELL: float = 0.5         # sell tier 相對等權縮小倍數(不歸零,避免全空)
BACKTEST_MIN_COMMON_DAYS: int = 60      # 共同交易日 < 此 → 不回測(對齊 FRONTIER_MIN_OBS,§1)
BACKTEST_NEW_FUND_MIN_DAYS: int = 252   # 共同窗 < 此(1 年)→ low_confidence 旗標
BACKTEST_FX_FETCH_DAYS: int = 3650      # 抓 USDTWD 歷史天數(~10y);回測窗自然被 NAV 重疊期封頂
BACKTEST_FX_ASOF_TOLERANCE_DAYS: int = 7  # FX 對 NAV as-of 對齊容差(日曆日);超過 → 該 NAV 點無匯率丟棄(§1 不 ffill)

# ── ⚠️ Macro Score 評分函式 v2 開關(2026-08-05 稽核;**預設全 False = 產線行為零變化**)──
#
# 為什麼是開關而不是直接切換:三項改動**都會改變投資結論**(分數位移 → 可能翻位階 →
# 建議配置改變),依 `PROCESS.md §6` 屬「⚠️ 需 user 拍板」類別。實作已完整落地(production
# 與回測 replay 共用同一組 `services/calibration/macro_score.py` 純函式),user 只要把對應
# 旗標改 True 即生效,可逐項對照新舊分數後再決定,**不需要再改任何邏輯**。
#
# 這不是 `CLAUDE.md §8.1 step 6` 的「用不到的抽象」:
#   (a) 兩條分支都是 production 路徑,都有測試守;
#   (b) 旗標本身就是交付物 —— 稽核要求「讓 user 對照新舊分數再決定是否啟用」;
#   (c) 沒有多餘的類別 / 註冊表 / 策略物件,就是一個 dict + 一個讀取函式。
#
# 三項語意(詳見 services/calibration/macro_score.py 各 scorer docstring):
#   pmi_continuous — PMI 由 50 切一刀的階梯改連續 tanh(修「49.9 → 50.1 跳 3 分、
#                    55.6 與 63.8 同分」的解析度缺陷)。尺度參數由既有 SSOT 相減推導。
#   hy_complacency — HY OAS 加**上緣**罰則(極緊利差 = 自滿,非健康;原本 <4% 一律滿分)。
#   cpi_graded     — CPI 中間帶 [2.5%, 4.0%] 由「完全免罰」改線性遞減罰則。
MACRO_SCORE_V2_FLAGS: dict[str, bool] = {
    "pmi_continuous": False,
    "hy_complacency": False,
    "cpi_graded": False,
}


def macro_score_v2_enabled(name: str) -> bool:
    """讀 `MACRO_SCORE_V2_FLAGS`(**每次呼叫即時讀**,不可在 import 時取值快取)。

    未登錄的 name 一律回 False(fail-closed:不認得的旗標不啟用新行為)。
    """
    return bool(MACRO_SCORE_V2_FLAGS.get(str(name), False))
# ── 基金型態分類:震盪型 vs 成長型(services/fund_type_classifier.py,v19.428)──
# Efficiency Ratio(Kaufman)= |淨移動| / Σ|逐日變動| ∈ [0,1];高=趨勢(成長)、低=來回震盪(均值回歸)。
# 震盪型適合「高基期→低基期」輪動;成長型順勢、看總經出場。灰帶用資產類別打破平手(股票→成長 / 其餘→震盪)。
TYPE_ER_GROWTH_MIN: float = 0.35    # ER ≥ 此 → 成長型
TYPE_ER_RANGE_MAX: float = 0.20     # ER ≤ 此 → 震盪型;之間為灰帶
TYPE_MIN_OBS: int = 60              # 有效 NAV 點 < 此 → ⬜ 無法判定(§1 短史不硬判)
TYPE_LOOKBACK_DAYS: int = 252       # ER 回看窗(交易日;取最近 N 點,原幣 NAV)

# ── 成長型賣出雙確認(services/switch_advisor.py,v19.428)──
# 總經看衰(為主)+ 該檔跌破均線(為輔)同時成立 → 建議賣出轉現金;僅前者 → 🟡 警示(§1 缺料不觸發)
GROWTH_MACRO_BEARISH_CUTOFF: float = -5.0  # macro composite 分數 ≤ 此 → 總經看衰(對齊 composite_verdict 悲觀界)
GROWTH_BREAKDOWN_SMA_DAYS: int = 120       # NAV < 此日數均線 → 跌破趨勢確認(交易日)

# ── 組合績效追蹤:趨勢重建最小覆蓋(services/portfolio_tracking.py,v19.430)──
# 走勢由「已累積的每檔 NAV × 目前權重」重建;共同交易日太少 → 稀疏序列 ×√252 年化會失真。
PORTFOLIO_TREND_MIN_DAYS: int = 60    # 共同交易日 < 此 → 只顯示累積曲線、抑制年化 CAGR/σ/Sharpe(§4.6;對齊 BACKTEST_MIN_COMMON_DAYS / FRONTIER_MIN_OBS,全站同一把尺)
PORTFOLIO_TREND_ROBUST_DAYS: int = 252  # < 此(1 年)→ low_confidence 旗標(仍顯示、標「參考」;對齊 FRONTIER_ROBUST_OBS)

# ── 表現差觸發:跑輸大盤門檻(services/switch_advisor.py underperformance,v19.430)──
# excess_pct = 基金近 1 年純價格報酬 − 對應大盤近 1 年純價格報酬(百分點,§4.1;負 = 落後)。
# 大盤依幣別:台股→加權 TWII / 美元→SPX / 其餘幣別→不比(§1 不拿原幣 NAV 比 USD 指數)。
UNDERPERF_LAG_THRESHOLD_PCT: float = -5.0  # excess_pct < 此 → 跑輸大盤(落後逾 5pp;避免 1–2pp 雜訊誤觸,BENCHMARK_WINDOW_DAYS=365 窗)


# ════════════════════════════════════════════════════════════════════════
# 深度強化模組 SSOT(v19.458)—— 資產水位 / Z-Score 動態門檻 / 穿透時效
# 依循「§3.3 反捏造」:以下為 DESIGN 常數(本專案自訂,無單一官方源),集中此處供調校。
# ════════════════════════════════════════════════════════════════════════

# ── 景氣對策信號(NDC monitoring 綜合分數 9~45)→ 5 燈號分界(官方 NDC 分界)──
NDC_LIGHT_BANDS: tuple = (
    (16, "藍",   "衰退低迷"),   # 9~16
    (22, "黃藍", "轉向觀察"),   # 17~22
    (31, "綠",   "穩定成長"),   # 23~31
    (37, "黃紅", "轉熱"),       # 32~37
    (45, "紅",   "過熱"),       # 38~45
)

# ── 模組①:composite_verdict 5 級 → 資產配置水位建議(股/債/貨幣 %,DESIGN)──
# 與 composite_verdict.action_text 既有現金字串一致(悲觀 15–25% / 極度悲觀 30%+)。
ALLOCATION_LADDER: dict = {
    "極度樂觀": {"equity": 85, "bond": 10, "cash": 5},
    "樂觀":     {"equity": 70, "bond": 20, "cash": 10},
    "中性":     {"equity": 55, "bond": 30, "cash": 15},
    "悲觀":     {"equity": 40, "bond": 35, "cash": 25},
    "極度悲觀": {"equity": 25, "bond": 40, "cash": 35},
}

# ── 模組②:Z-Score 位階窗 + 依景氣燈號動態門檻(DESIGN)──
ZSCORE_WINDOW_DAYS: int = 756          # 3 年交易日均線 + 標準差(§4.1;短史 → None 不硬算)
ZSCORE_MIN_OBS: int = 252              # 有效 NAV 點 < 此 → 位階不可信 → None(§1)
# 停利門檻:綠燈放寬(Z>+2.0 才停利,避免太早下車)、過熱紅燈收緊(早點停利避險)
ZSCORE_STOP_GAIN_BY_LIGHT: dict = {"藍": 1.25, "黃藍": 1.5, "綠": 2.0, "黃紅": 1.75, "紅": 1.5}
# 加碼門檻:衰退藍燈逢低積極(-0.75)、過熱紅燈收緊(要更低 -1.5 才加碼)
ZSCORE_ADD_BY_LIGHT: dict = {"藍": -0.75, "黃藍": -1.0, "綠": -1.0, "黃紅": -1.25, "紅": -1.5}
ZSCORE_STOP_GAIN_DEFAULT: float = 1.75  # 無景氣燈號時的預設停利 Z
ZSCORE_ADD_DEFAULT: float = -1.0        # 無景氣燈號時的預設加碼 Z
# 資產分流:這些 asset_bucket = Core(內建配置/現金,不做 Z-Score 擇時,§1 不硬套)
ZSCORE_CORE_BUCKETS: tuple = ("平衡多重", "貨幣市場")

# ── 模組④:穿透成分時效(DESIGN)──
LOOKTHROUGH_STALE_DAYS: int = 100      # 成分 as_of 舊於此(~1 季+)→ 標「落後推估下限」(Fail-Loud)
LOOKTHROUGH_COVERAGE_MIN: float = 0.5  # 單檔已揭露 top_holdings Σpct < 此 → 覆蓋不足,曝險為下限


# ════════════════════════════════════════════════════════════════════════
# 235 加碼引擎(基金版,v19.465)—— 老師「235 精準加碼」方法常數(DESIGN)
# §3.3:老師方法特有門檻,與總經 VIX zone(shared/macro_buckets 22/30)不同源、
# 不同用途(這是個檔加碼水位、那是總經風險燈),獨立集中此處供調校。user 2026-08-18 核准。
# ════════════════════════════════════════════════════════════════════════
# VIX 三燈分界(方法原味 20/25/30;30 恰與總經紅界一致,非巧合對齊)
LADDER235_VIX_L1: float = 20.0    # 20≤VIX<25 → 燈一(小跌)
LADDER235_VIX_L2: float = 25.0    # 25≤VIX<30 → 燈二(急跌)
LADDER235_VIX_L3: float = 30.0    # VIX≥30    → 燈三(深水/崩盤)
# 週均線窗(週 K 交易週)+ 20 週布林
LADDER235_MA_MONTH_W: int = 4     # 4 週月線
LADDER235_MA_QUARTER_W: int = 13  # 13 週季線
LADDER235_MA_YEAR_W: int = 52     # 52 週年線
LADDER235_BB_WINDOW_W: int = 20   # 20 週布林 μ/σ
LADDER235_MIN_WEEKS: int = 20     # 週資料 < 此 → 布林算不出 → 不硬給燈(§1)
LADDER235_MIN_CV: float = 0.002   # 週 σ/均值 < 此(0.2%)→ 低波標的,布林位階雜訊大,不判燈
#                                   (貨幣市場/短債近平盤,σ 極小 → 小跳動誤報極端燈;稽核 #8)
# 加碼金部署比例(當前燈 → 建議動用閒置加碼金%;不追蹤累計耗盡,§1 不假造帳本狀態)
LADDER235_DEPLOY_PCT: dict = {"燈一": 0.20, "燈二": 0.30, "燈三": 0.50, "巡航": 0.0}
# v19.483 稽核 M2:布林 z 決策切點 —— 這些才是**真正驅動燈號**的閾值,原 inline 於
# ladder235._classify(§3.3 違憲)。§3.2 sign:負=下檔加碼、正=上檔停利。
LADDER235_BB_STOPGAIN_FORCE: float = 3.0   # z > +3σ → 強制停利(超漲)
LADDER235_BB_STOPGAIN_BATCH: float = 2.0   # z > +2σ → 分批停利
LADDER235_BB_L1: float = -1.0              # z < -1σ → 燈一(小跌)
LADDER235_BB_L2: float = -2.0              # z < -2σ → 燈二(急跌)
LADDER235_BB_L3: float = -3.0              # z < -3σ → 燈三(深水)
LADDER235_DEFENSE_LOOKBACK_W: int = 8      # 落底回升:近 N 週曾探到年線之下


# ════════════════════════════════════════════════════════════════════════
# 衛星停利自動化(v19.466)—— 老師 80/20:衛星部位獲利達門檻自動亮停利燈(DESIGN)
# §3.3:方法常數(規格「15%~20% 嚴格停利」);獲利基準=T7 帳本純未實現%(不含息)。
# user 2026-08-18 核准。
# ════════════════════════════════════════════════════════════════════════
SATELLITE_STOP_GAIN_BATCH_PCT: float = 15.0   # 衛星未實現獲利 ≥ 此 → 💰 分批停利
SATELLITE_STOP_GAIN_FORCE_PCT: float = 20.0   # 衛星未實現獲利 ≥ 此 → 🔴 強制停利(轉回核心)
