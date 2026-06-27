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
CFNAI_RECESSION_THRESHOLD: float = -0.7
# Chicago Fed National Activity Index 3MA < -0.7 → 衰退進行中
RECESSION_LOGIT_COEF_SPREAD: float = -1.5
RECESSION_LOGIT_COEF_INTERCEPT: float = -0.8
# logit = SPREAD_COEF * spread_10y3m + INTERCEPT,經 sigmoid → recession probability

# ── Shadow fund 相似度(portfolio_service.py:424,§3.3)─────────
SHADOW_FUND_THRESHOLD_RATIO: float = 0.70
# composite score > 0.70 → 警示「影子基金」(高度雷同的不同基金)
SHADOW_FUND_JACCARD_WEIGHT_RATIO: float = 0.6
SHADOW_FUND_COSINE_WEIGHT_RATIO: float = 0.4
# composite = jaccard * JACCARD_W + cosine * COSINE_W,JACCARD_W + COSINE_W = 1.0

# ── 配息接近警戒(fund_service.py:279, fund_dividend_calculator.py:23)──
NEAR_DIVIDEND_WARNING_PCT: float = 2.0
# 配息年化率距離警戒線(年率 6%/8%)≤ 2pp → near zone,UI 標黃
# v19.175:同時兼任「吃本金 gap 容差」— gap = div - ret > 2pp → 🔴 吃本金

# ── 年化最小歷史長度(fund_dividend_calculator.py:207,v19.175)──────
MIN_YEARS_FOR_ANNUALIZE: float = 0.5
# 持有歷史 < 0.5 年不年化(避免「2 個月配息 × 6 倍」變 30% 高配息幻象,
# 對應 MK 老師「買舊不買新」警告 + §1 Fail Loud 不偽造數字),
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
# A ≥ 80 / B ≥ 65 / C ≥ 50 / D ≥ 35 / F < 35。
# 全站個檔基金健康度評等 SSOT(Tab2 KPI 卡 / Tab3 fund 評等共用),
# 取代 portfolio_service 6 因子 (75, 55, 40) 三級制(已 deprecated for grading,
# 6F dict 仍保留供 Sortino / Calmar / Alpha / 費用率單獨顯示)。

# ── 換標的建議 MK 4 規則門檻(services/fund_replacement_verdict.py,v19.181)──
# 任一規則中 → 🔴 建議換 / 1-2 條件靈領未達 hard trigger → 🟡 觀察 / 全未中 → 🟢 保留
REPLACE_RULE_A_MIN_HOLD_YEARS: float = 1.0
# (a) 吃本金 1Y·MK 且持有 ≥ 1 年 — < 1 年不算(短期 NAV 波動正常)
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

# ── TPI (Taiwan Phase Indicator) 加權(macro_service.py:1343)──────
TPI_BUSINESS_WEIGHT_RATIO: float = 0.4
TPI_FINANCIAL_WEIGHT_RATIO: float = 0.3
TPI_MONETARY_WEIGHT_RATIO: float = 0.3
# tpi = z_b * B_W + z_f * F_W + z_m * M_W,sum = 1.0

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
