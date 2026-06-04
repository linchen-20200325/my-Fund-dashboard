"""ui/tab_param_finder.py — 🔬 回測找參數獨立分頁 (v19.6).

從 📉 危機回測室 hoist 出來的 Phase 3 多因子權重最佳化 + Route C-1 提交為待審權重。
邏輯零變動，只是 UI 重新分區：

- 生產者（本 tab）：跑 multi-factor + walk-forward OOS → 📌 提交待審權重
- 消費者（🌐 總經 tab）：頂部 banner 批准 → 升格 active.json → 面板自動套用（C-2）

User flow：
1. 先到「📉 危機回測室」按「🚀 開始回測」載入危機事件清單
2. 回本 tab 跑多因子高原 + walk-forward
3. 提交為待審權重 → 至「🌐 總經」Tab 頂部 banner 批准
"""
from __future__ import annotations

import streamlit as st

from ui.tab_crisis_backtest import (
    _PHASE1_CACHE_KEY,
    _render_phase3_multi_factor_optimization,
)


def render_param_finder_tab() -> None:
    """🔬 回測找參數獨立分頁。"""
    st.markdown("## 🔬 回測找參數")
    st.caption(
        "多因子權重最佳化（高原 + walk-forward OOS）→ "
        "📌 提交為待審權重 → 至「🌐 總經」Tab 頂部 banner 批准 / 拒絕。"
    )

    cached_p1 = st.session_state.get(_PHASE1_CACHE_KEY)
    if not cached_p1:
        st.warning(
            "⚠️ 請先到「📉 危機回測室」分頁，按一次「🚀 開始回測」載入危機事件清單，"
            "再回本頁跑多因子最佳化。"
        )
        return

    events = cached_p1.get("events") or []
    if not events:
        st.warning("⚠️ Phase 1 cache 為空 — 請重跑「🚀 開始回測」。")
        return

    # series_by_key 給空 dict 讓 multi-factor 走 lazy-fetch 抓所有 23 因子
    _render_phase3_multi_factor_optimization(events, {})
