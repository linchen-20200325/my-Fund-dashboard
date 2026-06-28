"""ui/helpers/fund_grp_health 子套件 — v19.198 P1-6 從 fund_grp_health_extras.py(1478 LOC god helper)拆出。

結構:
- `_utils`:`_build_fund_dict` / `_safe_num` 共用 helper
- `dividend`:③ 真實收益 vs 配息率健康矩陣
- `investment`:④ 投資試算 + ⑤ TER + 持股分析
- `correlation`:⑥ 持股/產業相關性矩陣
- `risk`:⑦ HWM σ + ⑧ 風險對比 + ⑨ -2σ 超跌警示
- `signals`:⑩ MK 買賣點對比 + ⑪ Bollinger 詳圖
- `ai`:⑫ AI 跨檔評論 + ⑬ 個股新聞 + ⑭ 三率穿透
- 本 __init__:主入口 render_fund_grp_health_extras + re-export 全部子函式

14+ test 透過 fund_grp_health_extras.py shim re-export 取得 _render_* 函式,不需改 patch path。
"""
from __future__ import annotations

import streamlit as st

from ui.helpers.fund_grp_health._utils import _build_fund_dict, _safe_num  # noqa: F401
from ui.helpers.fund_grp_health.dividend import _render_dividend_matrix
from ui.helpers.fund_grp_health.investment import (
    _render_holdings_block,
    _render_investment_calc,
)
from ui.helpers.fund_grp_health.correlation import _render_correlation_matrix
from ui.helpers.fund_grp_health.risk import (
    _render_hwm_sigma_table,
    _render_oversold_badges,
    _render_risk_compare_table,
)
from ui.helpers.fund_grp_health.signals import (
    _render_bollinger_expanders,
    _render_mk_signal_table,
)
from ui.helpers.fund_grp_health.ai import (
    _build_cross_fund_snapshot,  # noqa: F401
    _render_ai_cross_fund_evaluation,
    _render_per_fund_news_expanders,
    _render_per_fund_three_ratio_expanders,
)


def render_fund_grp_health_extras(funds: list, principal_twd: float) -> None:
    """組合健檢進階貼圖區塊 entry。

    區塊順序：
      ③ 真實收益矩陣
      ④ 投資試算（每檔 expander）
      ⑤ TER + 持股分析（每檔 expander）
      ⑥–⑭ 多檔比較 / MK / Bollinger / AI / 新聞 / 三率

    注意（v19.189）：① 基金體檢 PK 表 + ② 4 大健診卡（fund_checkup）已上移至
    tab_fund_grp_health._render_health_table 健診總表之前，不再由本函式渲染。
    """
    if not funds:
        return

    st.divider()
    st.markdown("## 🔬 進階分析（移植自組合基金 / 單一基金）")

    # v19.189：基金體檢 PK + 4 大健診卡（fund_checkup）已上移至
    # tab_fund_grp_health._render_health_table 健診總表之前（user 要求易讀摘要先看到），
    # 此處不再渲染，避免上下兩份相同內容。
    try:
        _render_dividend_matrix(funds)
    except Exception as e:
        st.caption(f"⬜ 真實收益矩陣渲染失敗：[{type(e).__name__}] {str(e)[:80]}")

    st.divider()
    st.markdown("### 💼 逐檔深度分析（投資試算 + TER + 持股）")
    for _f in funds:
        _code = _f.get("code", "?")
        _name = (_f.get("name") or _code)[:30]
        with st.expander(f"💎 {_name}　·　{_code}", expanded=False):
            try:
                _render_investment_calc(_f, principal_twd)
            except Exception as e:
                st.caption(f"⬜ 投資試算失敗：[{type(e).__name__}] {str(e)[:80]}")
            st.divider()
            try:
                _render_holdings_block(_f)
            except Exception as e:
                st.caption(f"⬜ TER/持股渲染失敗：[{type(e).__name__}] {str(e)[:80]}")

    # v19.120 P0 — 多檔比較專屬區塊(每個 try/except 不擋下一個)
    try:
        _render_correlation_matrix(funds)
    except Exception as e:
        st.caption(f"⬜ 相關性矩陣渲染失敗：[{type(e).__name__}] {str(e)[:80]}")
    try:
        _render_hwm_sigma_table(funds)
    except Exception as e:
        st.caption(f"⬜ HWM σ 表渲染失敗：[{type(e).__name__}] {str(e)[:80]}")
    try:
        _render_risk_compare_table(funds)
    except Exception as e:
        st.caption(f"⬜ 風險表渲染失敗：[{type(e).__name__}] {str(e)[:80]}")
    try:
        _render_oversold_badges(funds)
    except Exception as e:
        st.caption(f"⬜ 超跌警示渲染失敗：[{type(e).__name__}] {str(e)[:80]}")

    # v19.121 P1 視覺 — MK 買賣點對比 + Bollinger 可展開詳圖
    try:
        _render_mk_signal_table(funds)
    except Exception as e:
        st.caption(f"⬜ MK 買賣點對比渲染失敗：[{type(e).__name__}] {str(e)[:80]}")
    try:
        _render_bollinger_expanders(funds)
    except Exception as e:
        st.caption(f"⬜ Bollinger 詳圖渲染失敗：[{type(e).__name__}] {str(e)[:80]}")

    # v19.122 P1 AI — 跨檔統一評論
    try:
        _render_ai_cross_fund_evaluation(funds)
    except Exception as e:
        st.caption(f"⬜ AI 跨檔評論渲染失敗：[{type(e).__name__}] {str(e)[:80]}")

    # v19.123 P1 — 個股新聞 + 三率穿透(per-fund lazy)
    try:
        _render_per_fund_news_expanders(funds)
    except Exception as e:
        st.caption(f"⬜ 個股新聞渲染失敗：[{type(e).__name__}] {str(e)[:80]}")
    try:
        _render_per_fund_three_ratio_expanders(funds)
    except Exception as e:
        st.caption(f"⬜ 三率穿透渲染失敗：[{type(e).__name__}] {str(e)[:80]}")
