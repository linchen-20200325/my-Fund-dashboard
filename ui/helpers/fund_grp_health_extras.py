"""v19.198 P1-6 shim — 主檔已拆 `ui/helpers/fund_grp_health/` 子套件。

原 1478 LOC god helper 拆 7 子檔:
- `_utils.py`(51 LOC)— _build_fund_dict / _safe_num
- `dividend.py`(136 LOC)— ③ 真實收益矩陣
- `investment.py`(212 LOC)— ④ 投資試算 + ⑤ TER/持股
- `correlation.py`(120 LOC)— ⑥ 相關性矩陣
- `risk.py`(205 LOC)— ⑦ HWM σ + ⑧ 風險對比 + ⑨ -2σ 警示
- `signals.py`(257 LOC)— ⑩ MK + ⑪ Bollinger
- `ai.py`(426 LOC)— ⑫ AI 跨檔 + ⑬ 個股新聞 + ⑭ 三率穿透
- `__init__.py`(127 LOC)— 主入口 render_fund_grp_health_extras + re-export 全部

本檔保留為 backward-compat shim,確保既有 caller 不需改 import path:
- `from ui.helpers.fund_grp_health_extras import render_fund_grp_health_extras` ✓
- `from ui.helpers.fund_grp_health_extras import _render_correlation_matrix` ✓
- 14 個 test 用 `_render_*` 私函(test_fund_grp_health_extras_p0/p1_ai/p1_news_ratio/p1_visual)
  全部直接走 shim,patch path 不需改
"""
from __future__ import annotations

from ui.helpers.fund_grp_health import (  # noqa: F401
    _build_cross_fund_snapshot,
    _build_fund_dict,
    _render_ai_cross_fund_evaluation,
    _render_bollinger_expanders,
    _render_correlation_matrix,
    _render_dividend_matrix,
    _render_holdings_block,
    _render_hwm_sigma_table,
    _render_investment_calc,
    _render_mk_signal_table,
    _render_oversold_badges,
    _render_per_fund_news_expanders,
    _render_per_fund_three_ratio_expanders,
    _render_risk_compare_table,
    _safe_num,
    render_fund_grp_health_extras,
)
