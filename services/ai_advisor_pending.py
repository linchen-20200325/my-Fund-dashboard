"""services/ai_advisor_pending.py — Route C-1：AI 解讀待審權重

把回測室產出的「最佳權重 + OOS 指標」交給 Gemini，產出白話解讀：
為何這組權重 / 哪些 cluster 變強變弱 / OOS 是否可信。

設計：
- 純函式 + 純文字 prompt，不依賴 streamlit context
- AI 失敗或無 key → 回退 fallback 數學摘要（不阻塞 user 提交流程）
"""
from __future__ import annotations

import os

_FALLBACK_HEADER = "🧮 數學摘要（AI 不可用）"


def _format_weights_table(weights: dict[str, float]) -> str:
    """權重表 → markdown bullet list（按權重大小排序）。"""
    if not weights:
        return "(無權重)"
    items = sorted(weights.items(), key=lambda kv: -abs(kv[1]))
    return "\n".join(f"- **{k}** = `{v:+.3f}`" for k, v in items)


def _math_summary(
    weights: dict[str, float],
    oos_metrics: dict[str, float],
) -> str:
    """fallback：AI 不可用時的純數學摘要。"""
    table = _format_weights_table(weights)
    train_f1 = oos_metrics.get("train_f1", 0.0)
    oos_f1 = oos_metrics.get("oos_f1", 0.0)
    gap = train_f1 - oos_f1
    overfit_flag = "⚠️ 可能過擬合（gap > 0.15）" if gap > 0.15 else "✅ Train/OOS 落差可接受"
    return (
        f"{_FALLBACK_HEADER}\n\n"
        f"**最佳權重**：\n{table}\n\n"
        f"**Train F1**：`{train_f1:.3f}`　|　"
        f"**OOS F1**：`{oos_f1:.3f}`　|　**Gap**：`{gap:+.3f}` — {overfit_flag}\n\n"
        f"**OOS Sharpe**：`{oos_metrics.get('oos_sharpe', 0.0):.3f}`　|　"
        f"**Walk-forward 折數**：`{oos_metrics.get('n_folds', 0)}`"
    )


def _build_prompt(
    weights: dict[str, float],
    oos_metrics: dict[str, float],
    horizon_months: int,
    drawdown_threshold: float,
) -> str:
    """build Gemini-friendly prompt（繁中、財金語境）."""
    table = _format_weights_table(weights)
    return (
        "你是資深量化策略師。以下是用 walk-forward + 高原評分跑出來的最佳因子權重，"
        f"用於預測未來 {horizon_months} 個月 SPX 最大跌幅 < `{drawdown_threshold * 100:.0f}%` 的「危機警戒」訊號。\n\n"
        f"### 最佳權重\n{table}\n\n"
        "### Walk-forward OOS 指標\n"
        f"- Train F1：`{oos_metrics.get('train_f1', 0.0):.3f}`\n"
        f"- OOS F1：`{oos_metrics.get('oos_f1', 0.0):.3f}`\n"
        f"- OOS Sharpe：`{oos_metrics.get('oos_sharpe', 0.0):.3f}`\n"
        f"- 折數：`{oos_metrics.get('n_folds', 0)}`\n\n"
        "請用繁中、最多 5 句話回答：\n"
        "1. 這組權重的「故事」是什麼？（哪幾個因子主導？）\n"
        "2. OOS 表現是否可信？（train/oos gap、Sharpe 合理性）\n"
        "3. 建議 user 批准還是再校準？（給明確判斷）\n"
        "不要客套話，直接給結論。"
    )


def explain_pending_weights(
    weights: dict[str, float],
    oos_metrics: dict[str, float],
    horizon_months: int = 3,
    drawdown_threshold: float = -0.10,
) -> str:
    """產生待審權重的 AI 解讀。失敗回退數學摘要。

    Returns:
        markdown 字串（直接餵 st.markdown）
    """
    weights = weights or {}
    oos_metrics = oos_metrics or {}

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return _math_summary(weights, oos_metrics)

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.5-flash")
        prompt = _build_prompt(weights, oos_metrics, horizon_months, drawdown_threshold)
        resp = model.generate_content(prompt)
        text = (getattr(resp, "text", "") or "").strip()
        if not text:
            return _math_summary(weights, oos_metrics)
        return f"🤖 **AI 解讀**\n\n{text}\n\n---\n\n{_math_summary(weights, oos_metrics)}"
    except Exception as e:
        return (
            f"{_math_summary(weights, oos_metrics)}\n\n"
            f"_（AI 呼叫失敗：{type(e).__name__}）_"
        )


__all__ = ["explain_pending_weights"]
