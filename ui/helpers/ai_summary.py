"""ai_summary.py — 各 Tab 通用「AI 白話總體檢」widget（v18.214 改版）。

設計原則（呼應 CLAUDE.md §2 §4）：
- 純 UI 層：呼叫 services/ai_prompts.build_structured_summary_prompt
  + services/ai_service._gemini
- 單一「結構化完整摘要」：吃該 Tab 全章節快照，逐章節給白話結論 + 時事，
  取代 v18.159 的「4 視角散文 selectbox」（已不符合「逐章節結論」需求）。
- caller 只負責組裝 snapshot 字串 + 章節清單 + 新聞 headlines。
- key 命名空間隔離：caller 傳 tab_key（如 "tab2"），避免多 Tab widget key 衝突。
- 結果存 session_state[f"{tab_key}_ai_struct"]，重開 expander 不重打 API。

使用範例：
    from ui.helpers.ai_summary import render_ai_summary_widget
    render_ai_summary_widget(
        tab_key="tab2",
        tab_label="單一基金（00878）",
        snapshot=_snap_text,
        sections=["基本資料", "績效表現", "風險指標", "配息", "新聞時事"],
        headlines=session_state.get("news_titles", []),
        gemini_api_key=GEMINI_KEY,
    )
"""
from __future__ import annotations
from typing import Optional

import streamlit as st

from services.ai_prompts import build_structured_summary_prompt


def render_ai_summary_widget(
    *,
    tab_key: str,
    tab_label: str,
    snapshot: str,
    sections: Optional[list[str]] = None,
    headlines: Optional[list[str]] = None,
    stale_note: str = "",
    gemini_api_key: str = "",
    expanded: bool = False,
) -> None:
    """在 Tab 末尾掛一個「AI 白話總體檢」widget（逐章節結論 + 時事）。

    tab_key:        widget key 命名空間（如 "tab2" / "tab3"）
    tab_label:      中文 label，傳給 AI 知道「在分析哪個 Tab」
    snapshot:       已格式化的「全章節」資料快照字串
    sections:       該 Tab 章節名稱清單（依顯示順序），AI 逐節各給一段
    headlines:      近期新聞標題，用於每節「最近新聞影響」
    stale_note:     資料新鮮度註記，可空
    gemini_api_key: secrets["GEMINI_KEY"]
    expanded:       expander 是否預設展開
    """
    with st.expander(f"🤖 AI 白話總體檢（{tab_label}）", expanded=expanded):
        if not snapshot or not snapshot.strip():
            st.caption("⚠️ 本 Tab 暫無可分析的快照資料（資料尚未載入）。")
            return

        st.caption("把這個 Tab 的所有資料交給 AI，逐段用白話講「現在是好是壞、跟最近新聞有沒有關係、下一步怎麼做」。")
        _cache_key = f"{tab_key}_ai_struct"
        _cached = st.session_state.get(_cache_key)

        _btn_label = "🔄 重新生成" if _cached else "▶️ 生成白話總體檢"
        run = st.button(_btn_label, key=f"{tab_key}_ai_run",
                        use_container_width=True, type="primary")

        if run:
            if not gemini_api_key:
                st.warning("❗ 未設定 Gemini API Key（secrets `GEMINI_KEY`）— 無法呼叫 AI。")
                return
            prompt = build_structured_summary_prompt(
                tab_label=tab_label, snapshot=snapshot,
                sections=sections or [], headlines=headlines or [],
                stale_note=stale_note,
            )
            # 延遲 import：ai_service 重，避免 module import 時拖慢 Streamlit cold start
            from services.ai_service import _gemini  # noqa: PLC0415
            with st.spinner("🤖 AI 正在逐段體檢（約 10-20 秒）..."):
                try:
                    _cached = _gemini(gemini_api_key, prompt, max_tokens=3500)
                except Exception as e:
                    st.error(f"❌ AI 呼叫失敗：[{type(e).__name__}] {e}")
                    return
            st.session_state[_cache_key] = _cached

        if not _cached:
            return

        st.markdown(_cached)
        _n_sec = len([s for s in (sections or []) if str(s).strip()])
        st.caption(
            f"💡 模型：Gemini　｜ 章節：{_n_sec} 節　"
            f"｜ 快照長度：{len(snapshot)} chars　｜ 結果已暫存，重開不會重打 API"
        )
