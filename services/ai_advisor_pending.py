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

# v19.11：user 對「預警」的口徑偏好 — 注入兩條 AI 線 prompt
_USER_PREFERENCE_NOTE = (
    "\n\n### 🎯 重要使用者偏好（預警 vs 同步）\n"
    "- **目標**：預警系統性風險 / 回調 — 訊號要在 SPX peak **前 30-90 天** 觸發才算 TP\n"
    "- **偏好**：日 / 週頻因子優先（VIX / HY_SPREAD / T10Y2Y / JOBLESS / NFCI 等）— 反應快、噪音可由 z-score 過濾\n"
    "- **避免**：單一**月頻**因子權重 > 0.7（PMI / CPI / SAHM / LEI 等）— 月頻發佈滯後，當下警告等同已 peak\n"
    "- 若候選都集中在月頻 → 給「再校準」建議；若日/週頻佔比 > 50% → 可採納\n"
)



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
        + _USER_PREFERENCE_NOTE +
        "\n請用繁中、最多 5 句話回答：\n"
        "1. 這組權重的「故事」是什麼？（哪幾個因子主導？頻率屬性如何？）\n"
        "2. OOS 表現是否可信？（train/oos gap、Sharpe 合理性、是否能事前預警）\n"
        "3. 建議 user 批准還是再校準？（給明確判斷，月頻佔比過高就建議重跑）\n"
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


def _format_candidate_row(idx: int, cand: dict) -> str:
    """單一候選 → markdown bullet（簡短一行）."""
    w = cand.get("weights") or {}
    top3 = sorted(w.items(), key=lambda kv: -abs(kv[1]))[:3]
    top3_str = ", ".join(f"{k}={v:.2f}" for k, v in top3)
    return (
        f"- **候選 {idx + 1}**：{top3_str}（…）"
        f" | plateau=`{cand.get('plateau_score', 0):.3f}`"
        f" | F1=`{cand.get('f1', 0):.3f}`"
        f" | Sharpe=`{cand.get('sharpe', 0):.3f}`"
        f" | n_crossings=`{cand.get('n_crossings', 0)}`"
    )


def _recommend_fallback(
    candidates: list[dict],
    oos_metrics: dict[str, float],
) -> str:
    """fallback：AI 不可用時純規則建議 — 取最高 plateau，提示分散度."""
    if not candidates:
        return f"{_FALLBACK_HEADER}\n\n（無有效候選 — 可能 F3 全濾掉，請檢查訊號參數）"
    rows = "\n".join(_format_candidate_row(i, c) for i, c in enumerate(candidates))
    top = candidates[0]
    n_cross_top = top.get("n_crossings", 0)
    sparsity_flag = (
        "⚠️ 訊號偏稀疏（n_crossings<5）— 統計信賴區間大"
        if n_cross_top < 5 else "✅ 訊號密度可接受"
    )
    oos_f1 = oos_metrics.get("oos_f1", 0.0)
    oos_flag = (
        "⚠️ OOS F1=0 — 樣本外完全沒命中，建議再校準"
        if oos_f1 == 0 else f"OOS F1=`{oos_f1:.3f}`"
    )
    return (
        f"{_FALLBACK_HEADER}\n\n"
        f"**Top {len(candidates)} 候選（按 plateau 降序）**：\n{rows}\n\n"
        f"**規則建議**：提交 **候選 1**（plateau 最高，已通過 F3 稀疏過濾 + F4 角點懲罰）。\n\n"
        f"- {sparsity_flag}\n"
        f"- {oos_flag}"
    )


def _build_compare_prompt(
    candidates: list[dict],
    oos_metrics: dict[str, float],
    horizon_months: int,
    drawdown_threshold: float,
) -> str:
    """build prompt for AI weight recommendation（事前比對 top-N 候選）."""
    rows = "\n".join(_format_candidate_row(i, c) for i, c in enumerate(candidates))
    return (
        "你是資深量化策略師。以下是用 walk-forward + 高原評分（v19.8 已過濾 corner vertex）"
        f"跑出的 **top {len(candidates)} 因子權重候選**，"
        f"用於預測未來 {horizon_months} 個月 SPX 最大跌幅 < `{drawdown_threshold * 100:.0f}%` 的「危機警戒」訊號。\n\n"
        f"### Top 候選（按 plateau 降序）\n{rows}\n\n"
        "### Walk-forward OOS 整段指標\n"
        f"- OOS F1：`{oos_metrics.get('oos_f1', 0.0):.3f}`\n"
        f"- OOS Sharpe：`{oos_metrics.get('oos_sharpe', 0.0):.3f}`\n"
        f"- 折數：`{oos_metrics.get('n_folds', 0)}`\n\n"
        + _USER_PREFERENCE_NOTE +
        "\n請用繁中、最多 6 句話回答：\n"
        "1. **建議提交候選幾號**？（給明確數字，例如「候選 1」）\n"
        "2. **為何選它**？（看權重分散度、F1、Sharpe、n_crossings、**頻率屬性**）\n"
        "3. **風險旗標**？（n_crossings<5 / OOS F1=0 / 單一因子權重 >0.7 / **月頻占主導 >50%** 任一觸發要點出）\n"
        "4. **是否應該重跑校準**？（如果所有候選月頻佔比都偏高，建議重跑）\n"
        "不要客套話，直接給結論。"
    )


def recommend_weights(
    candidates: list[dict],
    oos_metrics: dict[str, float],
    horizon_months: int = 3,
    drawdown_threshold: float = -0.10,
) -> str:
    """**事前** AI 建議：比對 top-N 候選 → 建議使用者提交哪一組（含風險旗標）。

    與既有 ``explain_pending_weights``（事後解讀）獨立兩條 AI 線。
    AI 失敗或無 key → 回退規則摘要（取最高 plateau 並標稀疏度 / OOS 旗標）。

    Returns:
        markdown 字串（直接餵 st.markdown）
    """
    candidates = candidates or []
    oos_metrics = oos_metrics or {}

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key or not candidates:
        return _recommend_fallback(candidates, oos_metrics)

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.5-flash")
        prompt = _build_compare_prompt(
            candidates, oos_metrics, horizon_months, drawdown_threshold,
        )
        resp = model.generate_content(prompt)
        text = (getattr(resp, "text", "") or "").strip()
        if not text:
            return _recommend_fallback(candidates, oos_metrics)
        return (
            f"🤖 **AI 建議**（事前比對 top-{len(candidates)} 候選）\n\n{text}\n\n---\n\n"
            f"{_recommend_fallback(candidates, oos_metrics)}"
        )
    except Exception as e:
        return (
            f"{_recommend_fallback(candidates, oos_metrics)}\n\n"
            f"_（AI 呼叫失敗：{type(e).__name__}）_"
        )


__all__ = ["explain_pending_weights", "recommend_weights"]
