"""services/quality_score.py — L2:同類相對品質分(v19.496)。

把數個「品質因子」各自的**同類百分位**加權合成一個 0-100 相對品質分 + 因子貢獻分解。
user 2026-08-20 核准 Option A(混合 rank 相對分)+ 母體選 (b)(同類大母體):
- 核心因子(報酬 / Sharpe / 下檔 / 成本)百分位取自 **MoneyDJ 同類大母體**(peer_compare「12/45」);
  niche 因子(操盤 / 配息)取自「持倉 ∪ 選股池」**小 universe**(caller 端決定,標「僅參考」)。
- **本檔只做數學,不管母體從哪來** —— caller 傳入時已把每個因子統一成
  **percentile 0 = 最佳 ~ 1 = 最差**(方向翻正:σ / MaxDD / 費用率 / 下檔捕捉 等「越小越好」的,
  caller 已翻成 0 = 最佳)。
- **相對分,非絕對**:分數是「同類相對位置」,不是絕對好壞;紅線(吃本金 / 3-3-3)不進本分。

§1 Fail-Loud:缺因子**不填 0**(填 0 = 假裝它同類最差,是造假)→ 退出分母,權重在可得因子上
  重正規化;有效因子太少 → 不給分(None)。純函式・零 IO・離線可驗(§8.2 L2)。
"""
from __future__ import annotations

from typing import Optional

# 建議預設權重(user 核准;可由 caller 覆蓋)。key = 因子名,和 caller 餵的 percentile key 對齊。
DEFAULT_WEIGHTS: dict = {
    "報酬": 25.0,      # 3Y 年化含息(MoneyDJ 同類大母體)
    "Sharpe": 25.0,    # 年化 Sharpe(MoneyDJ 同類大母體)
    "下檔": 20.0,      # σ / 下檔保護(MoneyDJ 同類大母體;越小越好 → caller 已翻)
    "操盤": 10.0,      # 上檔 − 下檔捕捉(小 universe)
    "配息": 10.0,      # coverage = 含息 ÷ 配息率(小 universe)
    "成本": 10.0,      # 費用率(MoneyDJ 同類大母體;越小越好 → caller 已翻)
}
# 有效因子少於此數 → 不給相對分(§1 樣本太少不硬湊)。單一基金頁只有 4 個大母體因子 → 仍達標。
MIN_FACTORS_FOR_SCORE: int = 3


def _pct_to_factor_score(pct: float) -> float:
    """同類百分位(0 = 最佳 ~ 1 = 最差)→ 0-100 因子分(高 = 好)。越界值 clip。"""
    p = min(max(float(pct), 0.0), 1.0)
    return (1.0 - p) * 100.0


def compute_quality_score(factor_pcts: dict,
                          weights: Optional[dict] = None) -> dict:
    """factor_pcts: {因子名: 同類百分位 0最佳~1最差 | None(缺 → 退出分母)}。

    回 dict:
      score          : 0-100 | None(有效因子 < MIN_FACTORS_FOR_SCORE → None,不硬給)
      contributions  : {因子名: 加權後貢獻分}(加總 ≈ score,供貢獻分解)
      n_used / n_total
      coverage_pct   : 有效因子權重 / 全權重 × 100
      note           : 白話覆蓋率說明

    §1:缺因子退出分母、權重在可得因子上重正規化(不填 0 假裝最差)。
    """
    w = dict(weights or DEFAULT_WEIGHTS)
    names = list(w.keys())
    n_total = len(names)
    total_w_all = sum(w[k] for k in names) or 1.0

    avail = {k: float(factor_pcts.get(k)) for k in names
             if isinstance(factor_pcts.get(k), (int, float))
             and not isinstance(factor_pcts.get(k), bool)}
    n_used = len(avail)
    cov_all = round(100.0 * sum(w[k] for k in avail) / total_w_all, 1)

    if n_used < MIN_FACTORS_FOR_SCORE:
        return {"score": None, "contributions": {}, "n_used": n_used,
                "n_total": n_total, "coverage_pct": cov_all,
                "note": f"有效因子僅 {n_used} 項(< {MIN_FACTORS_FOR_SCORE})→ 不給相對分(§1)"}

    total_w_avail = sum(w[k] for k in avail) or 1.0
    contributions: dict = {}
    score = 0.0
    for k, pct in avail.items():
        contrib = (w[k] / total_w_avail) * _pct_to_factor_score(pct)
        contributions[k] = round(contrib, 1)
        score += contrib

    return {"score": round(score, 1), "contributions": contributions,
            "n_used": n_used, "n_total": n_total, "coverage_pct": cov_all,
            "note": f"用 {n_used}/{n_total} 因子(覆蓋 {cov_all:.0f}%)"}


__all__ = ["compute_quality_score", "DEFAULT_WEIGHTS",
           "MIN_FACTORS_FOR_SCORE", "_pct_to_factor_score"]
