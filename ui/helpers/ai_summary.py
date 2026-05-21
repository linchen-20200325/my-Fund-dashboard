"""ai_summary.py — v18.159 各 Tab 通用「AI 白話文總結」widget。

設計原則（呼應 CLAUDE.md §2 §4）：
- 純 UI 層：呼叫 services/ai_prompts builder + services/ai_service._gemini
- 統一 selectbox（4 個視角）+ 觸發按鈕 + 結果區
- caller 只負責「組裝該 Tab 的 snapshot 字串」，不必碰 prompt / API 細節
- key 命名空間隔離：caller 傳 tab_key（如 "tab1"），避免 6 個 Tab widget key 衝突

使用範例：
    from ui.helpers.ai_summary import render_ai_summary_widget
    render_ai_summary_widget(
        tab_key="tab1",
        tab_label="總經位階",
        snapshot=_build_macro_snapshot_for_ai(),
        headlines=session_state.get("macro_news_headlines", []),
        gemini_api_key=GEMINI_KEY,
    )
"""
from __future__ import annotations
from typing import Optional

import streamlit as st

from services.ai_prompts import (
    build_trend_action_prompt,
    build_allocation_diagnosis_prompt,
    build_beginner_guide_prompt,
    build_news_driven_prompt,
)

PERSPECTIVES: dict[str, str] = {
    "trend_action": "📈 趨勢 + ⚠️ 風險 + 🎯 行動（推薦）",
    "allocation":   "💰 配置診斷",
    "beginner":     "🧠 新手導讀",
    "news":         "📰 新聞連動",
}


def render_ai_summary_widget(
    *,
    tab_key: str,
    tab_label: str,
    snapshot: str,
    headlines: Optional[list[str]] = None,
    stale_note: str = "",
    gemini_api_key: str = "",
    expanded: bool = False,
) -> None:
    """在 Tab 末尾掛一個 AI 白話文總結 widget。

    tab_key:        widget key 命名空間（如 "tab1" / "tab3"）
    tab_label:      中文 label，傳給 AI 知道「在分析哪個 Tab」
    snapshot:       已格式化的資料快照字串（KPI / 標籤 / 數字）
    headlines:      新聞連動視角專用；其它視角忽略
    stale_note:     資料新鮮度註記（如「資料最新更新：2026-05-20」），可空
    gemini_api_key: secrets["GEMINI_KEY"]
    expanded:       expander 是否預設展開（預設關，由 user 點開）
    """
    with st.expander(f"🤖 AI 白話文總結（{tab_label}）", expanded=expanded):
        if not snapshot or not snapshot.strip():
            st.caption("⚠️ 本 Tab 暫無可分析的快照資料（資料尚未載入）。")
            return

        col1, col2 = st.columns([3, 1])
        with col1:
            perspective_key = st.selectbox(
                "分析視角",
                options=list(PERSPECTIVES.keys()),
                format_func=lambda k: PERSPECTIVES[k],
                key=f"{tab_key}_ai_perspective",
                help="同一份資料，不同視角會講不同重點。",
            )
        with col2:
            st.write("")  # vertical align hack
            st.write("")
            run = st.button(
                "▶️ 生成", key=f"{tab_key}_ai_run",
                use_container_width=True, type="primary",
            )

        if perspective_key == "news" and not (headlines or []):
            st.caption("ℹ️ 本 Tab 未提供新聞快照，「新聞連動」視角會回缺資料說明。")

        if not run:
            return

        if not gemini_api_key:
            st.warning("❗ 未設定 Gemini API Key（secrets `GEMINI_KEY`）— 無法呼叫 AI。")
            return

        prompt = _build_prompt(
            perspective_key=perspective_key,
            tab_label=tab_label,
            snapshot=snapshot,
            stale_note=stale_note,
            headlines=headlines or [],
        )

        # 延遲 import：ai_service 重，避免 module import 時拖慢 Streamlit cold start
        from services.ai_service import _gemini  # noqa: PLC0415

        with st.spinner("🤖 AI 思考中（約 5-15 秒）..."):
            try:
                resp = _gemini(gemini_api_key, prompt, max_tokens=2000)
            except Exception as e:
                st.error(f"❌ AI 呼叫失敗：[{type(e).__name__}] {e}")
                return

        st.markdown(resp)
        st.caption(
            f"💡 視角：{PERSPECTIVES[perspective_key]}　"
            f"｜ 模型：Gemini　"
            f"｜ 快照長度：{len(snapshot)} chars"
        )


def _build_prompt(*, perspective_key: str, tab_label: str, snapshot: str,
                  stale_note: str, headlines: list[str]) -> str:
    """依 perspective 派發到對應 builder。"""
    if perspective_key == "trend_action":
        return build_trend_action_prompt(
            tab_label=tab_label, snapshot=snapshot, stale_note=stale_note,
        )
    if perspective_key == "allocation":
        return build_allocation_diagnosis_prompt(
            tab_label=tab_label, snapshot=snapshot, stale_note=stale_note,
        )
    if perspective_key == "beginner":
        return build_beginner_guide_prompt(
            tab_label=tab_label, snapshot=snapshot, stale_note=stale_note,
        )
    if perspective_key == "news":
        return build_news_driven_prompt(
            tab_label=tab_label, snapshot=snapshot,
            headlines=headlines, stale_note=stale_note,
        )
    raise ValueError(f"unknown perspective: {perspective_key}")
