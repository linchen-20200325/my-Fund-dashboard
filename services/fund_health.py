"""v19.177 #3A — 基金健康度 4D 評分 SSOT(zero-IO 純函式)。

從 `ui/tab2_single_fund.py:694-741` inline 邏輯抽出,供 Tab2 / Tab3 / 健診總表
共用同一份「個檔健康度評等」函式,杜絕同基金跨 Tab 不同 grade 散落。

設計
----
**4 維度**(MK 老師體檢風格 — 配息核心):
1. 💵 配息健康度(Coverage) — Coverage = ret_1y_total / annual_div_rate
2. 📈 風險調整報酬(Sharpe) — 年化 Sharpe Ratio
3. 📊 走勢健康(MA 方向 + 報酬) — 60d MA 方向 + ret_1y
4. 🛡️ 低波動性(σ) — 年化標準差(越低越好)

**Grade(v19.177 #4B SSOT)**:
- A ≥ 80 / B ≥ 65 / C ≥ 50 / D ≥ 35 / F < 35
- cutoffs 走 `shared.signal_thresholds.GRADE_CUTOFFS_4D`

**6F vs 4D 分工**(v19.177 後):
- 4D = 個檔健康度評等(Tab2 KPI 卡 / Tab3 fund 評等共用此 SSOT)
- 6F = `portfolio_service.calc_fund_factor_score`,保留為「進階指標 dict」
  供「健診詳表」單獨顯示 Sortino / Calmar / Alpha / 費用率(4D 無法補的維度),
  **不再用於 grade 評等**(@deprecated for grading)
"""
from __future__ import annotations

from typing import Any, Optional

from shared.colors import MATERIAL_GREEN, MATERIAL_ORANGE, MATERIAL_RED
from shared.signal_thresholds import GRADE_CUTOFFS_4D


# v19.222 P1-1:_safe_float 收口至 shared/converters.py SSOT
from shared.converters import safe_float as _safe_float  # noqa: E402



def _score_coverage(tr1y_pct: Optional[float], adr_pct: Optional[float]) -> Optional[int]:
    """配息健康度 0-100(Coverage = tr / adr 5 級分級)。

    coverage ≥ 1.5 → 95 / ≥ 1.2 → 80 / ≥ 1.0 → 65 / ≥ 0.5 → 40 / < 0.5 → 15
    """
    if tr1y_pct is None or adr_pct is None or adr_pct <= 0:
        return None
    cov = tr1y_pct / adr_pct
    if cov >= 1.5:
        return 95
    if cov >= 1.2:
        return 80
    if cov >= 1.0:
        return 65
    if cov >= 0.5:
        return 40
    return 15


def _score_sharpe(sharpe: Optional[float]) -> Optional[int]:
    """風險調整報酬 0-100。≥ 1.5 → 95 / ≥ 1.0 → 80 / ≥ 0.5 → 60 / ≥ 0 → 40 / < 0 → 15"""
    if sharpe is None:
        return None
    if sharpe >= 1.5:
        return 95
    if sharpe >= 1.0:
        return 80
    if sharpe >= 0.5:
        return 60
    if sharpe >= 0:
        return 40
    return 15


def _score_trend(ma_dir: Optional[str], tr1y_pct: Optional[float]) -> Optional[int]:
    """走勢健康 0-100(MA 方向 + ret_1y 組合判斷)。

    up + 正報酬 → 85 / up only → 70 /
    down + 負報酬 → 25 / down only → 45 /
    無 MA 方向但 ret_1y > 5% → 70 / < -5% → 25 / 否則 None
    """
    if ma_dir == "up" and tr1y_pct is not None and tr1y_pct > 0:
        return 85
    if ma_dir == "up":
        return 70
    if ma_dir == "down" and tr1y_pct is not None and tr1y_pct < 0:
        return 25
    if ma_dir == "down":
        return 45
    if tr1y_pct is not None and tr1y_pct > 5:
        return 70
    if tr1y_pct is not None and tr1y_pct < -5:
        return 25
    return None


def _score_volatility(sigma_pct: Optional[float]) -> Optional[int]:
    """低波動性 0-100。σ < 10 → 90 / < 15 → 75 / < 20 → 55 / < 30 → 35 / ≥ 30 → 15"""
    if sigma_pct is None:
        return None
    if sigma_pct < 10:
        return 90
    if sigma_pct < 15:
        return 75
    if sigma_pct < 20:
        return 55
    if sigma_pct < 30:
        return 35
    return 15


def _grade_from_score(score: Optional[float]) -> tuple[str, str, str]:
    """v19.177 #4B SSOT — Grade A/B/C/D/F + 顏色 + 文字評語。

    走 GRADE_CUTOFFS_4D = (80, 65, 50, 35)。
    Returns (grade_letter, color_hex, verdict_text)
    """
    if score is None:
        return "—", "#888", "資料不足以評等"
    a, b, c, d = GRADE_CUTOFFS_4D
    if score >= a:
        return "A", MATERIAL_GREEN, "✅ 健康優質基金"
    if score >= b:
        return "B", "#69f0ae", "🟢 表現穩健"
    if score >= c:
        return "C", "#ffeb3b", "🟡 中性,持續觀察"
    if score >= d:
        return "D", MATERIAL_ORANGE, "🟠 警示偏弱"
    return "F", MATERIAL_RED, "🔴 多項警示"


def compute_4d_health(
    tr1y_pct: Optional[float] = None,
    adr_pct: Optional[float] = None,
    sharpe: Optional[float] = None,
    sigma_pct: Optional[float] = None,
    ma_dir: Optional[str] = None,
) -> dict:
    """基金健康度 4D 評分 SSOT 入口(v19.177)。

    Args
    ----
    tr1y_pct : 1Y 含息報酬率 %(走 compute_1y_total_return SSOT)
    adr_pct : 年化配息率 %(走 _resolve_adr_with_fallback SSOT)
    sharpe : 年化 Sharpe Ratio(metrics.sharpe SSOT)
    sigma_pct : 年化標準差 %(metrics.std_1y SSOT)
    ma_dir : 'up' | 'down' | None(60d MA 方向,UI 端算)

    Returns
    -------
    {
        "score": float | None,                # 綜合 0-100
        "grade": str,                          # 'A' | 'B' | 'C' | 'D' | 'F' | '—'
        "grade_color": str,                    # hex
        "verdict": str,                        # 評語
        "factors": {
            "coverage": int | None,            # 💵 配息健康度
            "sharpe": int | None,              # 📈 風險調整報酬
            "trend": int | None,               # 📊 走勢健康
            "volatility": int | None,          # 🛡️ 低波動性
        },
        "eat_warn": bool,                      # 🔴 吃本金警示(coverage < 50)
    }
    """
    f_cov = _score_coverage(_safe_float(tr1y_pct), _safe_float(adr_pct))
    f_sh = _score_sharpe(_safe_float(sharpe))
    f_tr = _score_trend(ma_dir, _safe_float(tr1y_pct))
    f_vol = _score_volatility(_safe_float(sigma_pct))

    scores = [x for x in (f_cov, f_sh, f_tr, f_vol) if x is not None]
    overall = (sum(scores) / len(scores)) if scores else None
    grade, color, verdict = _grade_from_score(overall)

    return {
        "score": overall,
        "grade": grade,
        "grade_color": color,
        "verdict": verdict,
        "factors": {
            "coverage": f_cov,
            "sharpe": f_sh,
            "trend": f_tr,
            "volatility": f_vol,
        },
        "eat_warn": (f_cov is not None and f_cov < 50),
    }
