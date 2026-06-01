"""crisis_ai_advisor.py — 危機回測 AI 策略建議 (v18.260, Phase 5).

User 需求第 5 階段（最終）：把 Phase 1-4 的結果丟給 Gemini，產出白話策略建議。

設計原則：
- 純函式式 prompt builder + 薄包 gemini_generate
- 無 Streamlit 依賴；UI 層只負責拿 prompt → 呼叫 → 渲染
- 沿用 services.ai_prompts 的「白話理財小幫手」風格
- prompt 嚴格上限 ≤ 800 字資料（不含模板），避免炸 token
"""
from __future__ import annotations

from typing import Optional

import pandas as pd


_MAX_EVENT_ROWS = 6
_MAX_GRID_ROWS = 12  # 4 策略 × 3 門檻


def _fmt_pct(v: Optional[float], plus: bool = True) -> str:
    if v is None or pd.isna(v):
        return "—"
    fmt = "{:+.1%}" if plus else "{:.1%}"
    return fmt.format(float(v))


def _fmt_num(v: Optional[float], digits: int = 2) -> str:
    if v is None or pd.isna(v):
        return "—"
    return f"{float(v):.{digits}f}"


def _summarize_events(events: list) -> str:
    """把 CrisisEvent 列表壓縮成簡短 markdown 條列。"""
    if not events:
        return "（這段期間沒有偵測到符合門檻的危機事件）"
    rows = events[:_MAX_EVENT_ROWS]
    lines = []
    for ev in rows:
        d = ev.to_dict() if hasattr(ev, "to_dict") else dict(ev)
        peak = d.get("peak_date", "—")
        trough = d.get("trough_date", "—")
        dd = _fmt_pct(d.get("drawdown_pct"))
        dur = d.get("duration_days", "—")
        rec = d.get("recovery_days")
        rec_txt = f"{rec} 天回升" if rec is not None else "尚未回升"
        lines.append(f"- {peak} ~ {trough}：跌幅 {dd}，歷時 {dur} 天，{rec_txt}")
    extra = len(events) - len(rows)
    if extra > 0:
        lines.append(f"- …另 {extra} 筆事件略")
    return "\n".join(lines)


def _summarize_grid(grid_df: pd.DataFrame) -> str:
    """把 grid_search DataFrame 壓縮成 markdown 表（每策略×門檻一行）。"""
    if grid_df is None or grid_df.empty:
        return "（無網格結果）"
    df = grid_df.head(_MAX_GRID_ROWS)
    lines = ["| 策略 | 門檻 | 期末資產 | 總報酬 | 最大回撤 | Sharpe | 危機期報酬 |",
             "|---|---|---|---|---|---|---|"]
    for _, r in df.iterrows():
        lines.append(
            f"| {r.get('strategy_label', '—')} "
            f"| {_fmt_num(r.get('threshold'), 1)} "
            f"| {_fmt_num(r.get('final_value'), 1)} "
            f"| {_fmt_pct(r.get('total_return_pct'))} "
            f"| {_fmt_pct(r.get('max_drawdown_pct'))} "
            f"| {_fmt_num(r.get('sharpe_ratio'))} "
            f"| {_fmt_pct(r.get('crisis_return_pct'))} |"
        )
    return "\n".join(lines)


def _summarize_top(top_result: dict | pd.Series | None) -> str:
    """單一最佳 cell 摘要。"""
    if top_result is None:
        return "（無最佳 cell）"
    if isinstance(top_result, pd.Series):
        top_result = top_result.to_dict()
    return (
        f"- 策略：{top_result.get('strategy_label', '—')}\n"
        f"- 訊號門檻：{_fmt_num(top_result.get('threshold'), 1)}\n"
        f"- 期末資產：{_fmt_num(top_result.get('final_value'), 1)}（起始 100）\n"
        f"- 總報酬：{_fmt_pct(top_result.get('total_return_pct'))}\n"
        f"- 最大回撤：{_fmt_pct(top_result.get('max_drawdown_pct'))}\n"
        f"- Sharpe：{_fmt_num(top_result.get('sharpe_ratio'))}\n"
        f"- 危機期報酬：{_fmt_pct(top_result.get('crisis_return_pct'))}\n"
        f"- 訊號觸發天數：{top_result.get('n_trigger_days', '—')} / "
        f"{top_result.get('n_total_days', '—')} 天"
    )


def build_strategy_advice_prompt(
    *,
    events: list,
    grid_df: pd.DataFrame,
    top_result: dict | pd.Series | None,
    signal_label: str,
    market_label: str,
    metric_label: str = "Sharpe",
) -> str:
    """組合「危機回測 → AI 策略建議」prompt（白話、≤200 字輸出）。

    Args:
        events: list[CrisisEvent]（或具 to_dict 的 dataclass）
        grid_df: results_to_dataframe 的輸出
        top_result: rank_results 的 top-1（dict / Series）
        signal_label: 用於 prompt 的訊號描述（例：「VIX > 25」）
        market_label: 用於 prompt 的大盤描述（例：「SPX」）
        metric_label: 使用者選的排序指標中文（例：「年化 Sharpe」）

    Returns:
        完整 prompt 字串
    """
    event_block = _summarize_events(events)
    grid_block = _summarize_grid(grid_df)
    top_block = _summarize_top(top_result)

    return f"""你是一位很親切的理財小幫手，講話像在跟剛入門的朋友聊天。

【最重要的講話規則】
- 全程「白話」繁體中文，盡量不要用專業術語；非用不可時用括號解釋
  （例：Sharpe（「冒這麼大風險到底值不值得」的分數））。
- 不要長篇大論，每段 2-3 句講重點。

【嚴格規則】只能根據下面的「歷史回測結果」分析，禁止上網搜尋、禁止杜撰其他數字。

[分析範圍] 大盤：{market_label}；訊號：{signal_label}；排序依據：{metric_label}

[歷史危機事件清單（Phase 1 偵測）]
{event_block}

[策略 × 門檻 網格回測結果（Phase 4）]
{grid_block}

[Top-1 最佳 cell]
{top_block}

═══════════════════════════════════════════
請用繁體中文，依照下面四節順序輸出，每節用 `### ` 當標題：

### 🏆 最佳策略解讀
- 為什麼這組（策略 + 門檻）勝出？用白話講「它在這些危機裡做對了什麼」。

### ⚠️ 風險與盲點
- 這個結論有什麼前提或限制？（例：樣本太少、訊號滯後、忽略交易成本…）

### 🎯 投資人該怎麼做
- 給 1-2 個很具體、新手也能執行的下一步動作。

### 📌 一句話總結
- 用一句最白話的話總結。

【再次提醒】只引用上面的數字，不要編造；越白話越好。"""


def generate_strategy_advice(
    *,
    events: list,
    grid_df: pd.DataFrame,
    top_result: dict | pd.Series | None,
    signal_label: str,
    market_label: str,
    metric_label: str = "Sharpe",
    max_tokens: int = 1200,
) -> str:
    """端到端：build prompt → 呼叫 Gemini → 回字串。

    若無 API key 或 prompt 為空，回傳警示訊息（不丟例外）。
    """
    if grid_df is None or grid_df.empty:
        return "⚠️ 沒有網格回測結果可分析，請先按「跑網格」。"

    prompt = build_strategy_advice_prompt(
        events=events,
        grid_df=grid_df,
        top_result=top_result,
        signal_label=signal_label,
        market_label=market_label,
        metric_label=metric_label,
    )
    try:
        from services.ai_service import gemini_generate, get_gemini_keys
    except Exception as e:
        return f"⚠️ AI 服務不可用：{e}"

    keys = get_gemini_keys()
    if not keys:
        return "⚠️ 未設定 Gemini API Key（請設定環境變數 GEMINI_API_KEY）"

    return gemini_generate(prompt, max_tokens=max_tokens, keys=keys)
