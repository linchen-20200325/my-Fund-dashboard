"""shared/switch_thresholds.py — 換標決策引擎常數 SSOT(v19.423)。

user 2026-07-28 spec + 拍板:獨立「換標策略分」(**不混 4D 健康度**)、選股訊號用
**vs 大盤%**(對大盤超額,非真實收益%)、資料不足 → 灰燈。所有門檻/權重集中此處
(§3.3 反捏造,不 inline magic)。
"""
from __future__ import annotations

# ── 換標策略分 0-100:各指標 tier = (下限, 得分),值 ≥ 下限的第一個命中;皆不中 → 0 ──
# 權重 = 各指標最高分之和 = 35 + 30 + 20 + 15 = 100
SWITCH_TR_TIERS: list = [(5.0, 35), (0.0, 25), (-10.0, 10)]      # 1Y 含息 %
SWITCH_SHARPE_TIERS: list = [(0.8, 30), (0.3, 20), (0.0, 10)]    # Sharpe 1Y
SWITCH_MAXDD_TIERS: list = [(-15.0, 20), (-25.0, 10)]           # Max DD %(負值,≥ 下限)
SWITCH_ALPHA_POINTS: int = 15                                    # vs 大盤% > 0 → 15,否則 0

# ── 燈號門檻 ──
# 註:非紅/綠/灰 一律歸黃(觀望)—— 明確黃燈條件(分<60 / vs大盤<0&距HWM<-20)皆為「非綠」
# 子集,故不另設門檻常數(稽核 Finding 2:避免宣告卻不用的死常數 + 誤導文檔)。
SWITCH_GREEN_SCORE: int = 70            # 分 ≥ 此 且 吃本金「健康」→ 🟢

# ── 替換引擎 argmax 權重 + 候選限制(同資產類別「一對一替換」)──
SWITCH_REPLACE_W_SHARPE: float = 0.4
SWITCH_REPLACE_W_RETURN: float = 0.4
SWITCH_REPLACE_W_SORTINO: float = 0.2
# v19.449 稽核 M2:1Y 含息 %(~0-20)先除此值 → 與 Sharpe/Sortino(~0-2)同量級,否則報酬項
# ×0.4 會蓋過風險調整項 10:1,「換品質更好」的排名塌成純追報酬(§4.1 % vs 比率量綱陷阱)。
SWITCH_REPLACE_RETURN_SCALE: float = 10.0
SWITCH_REPLACE_MIN_SHARPE: float = 0.5      # 候選 Sharpe 下限
SWITCH_REPLACE_MAX_EXPENSE_PCT: float = 1.5  # 候選費用率% 上限

# ── 大盤 regime filter(系統性風險)──
SWITCH_REGIME_NEG_SHARPE_RATIO: float = 0.8  # 同池 > 80% Sharpe 為負 → 暫緩換標,避免殺低
