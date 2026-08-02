"""ui/helpers/portfolio_perf.py — 📊 組合績效區塊(v19.421)。

L3 orchestrator:從已載入持倉(rich fund dict,含 series + invest_twd)組 nav_by_code + 權重
→ L2 `services.portfolio_performance`(純數學)→ 4 KPI + 各檔貢獻表。權重依**投入金額**
(無則等權 fallback);§1 缺料/排除誠實顯示。
"""
from __future__ import annotations

import streamlit as st


def render_portfolio_performance(funds: list) -> None:
    """📊 組合績效 —— 年化報酬 / σ / Sharpe / 最大回撤 + 各檔貢獻。funds<1 檔有序列 → 略過。"""
    from services.portfolio_performance import contribution_by_fund, performance_metrics

    _nav = {f.get("code"): f.get("series") for f in (funds or [])
            if f.get("code") and f.get("series") is not None}
    if len(_nav) < 1:
        return
    _w = {c: float((next((f for f in funds if f.get("code") == c), {}) or {}).get("invest_twd") or 0)
          for c in _nav}
    if sum(_w.values()) <= 0:                      # 無投入金額 → 等權 fallback(明示於 caption)
        _w = {c: 1.0 for c in _nav}
        _equal = True
    else:
        _equal = False

    st.divider()
    st.markdown("### 📊 組合績效(固定權重・日再平衡假設)")
    _m = performance_metrics(_nav, _w)
    if _m["n_funds_used"] == 0:
        st.info("組合績效資料不足 —— 需至少 1 檔有足夠 NAV 歷史 + 正權重。")
        return

    def _pct(v):
        return f"{v:+.2f}%" if v is not None else "—"

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("年化報酬", _pct(_m["ann_return_pct"]))
    c2.metric("年化波動 σ", f"{_m['ann_vol_pct']:.2f}%" if _m["ann_vol_pct"] is not None else "—")
    c3.metric("Sharpe", f"{_m['sharpe']:.2f}" if _m["sharpe"] is not None else "—")
    c4.metric("最大回撤", _pct(_m["max_drawdown_pct"]))

    _wsrc = "等權(無投入金額)" if _equal else "投入金額加權"
    st.caption(
        f"期間 {_m['start']} ~ {_m['end']}（{_m['n_days']} 交易日・{_m['n_funds_used']} 檔・{_wsrc}・"
        f"無風險利率 {_m['rf_annual'] * 100:.1f}%）。**固定權重日再平衡**假設;對齊各檔共同交易日。"
    )
    if _m["excluded"]:
        st.caption("⬜ 排除:" + "、".join(f"{e['code']}（{e['reason']}）" for e in _m["excluded"]))

    _contrib = contribution_by_fund(_nav, _w)
    if _contrib:
        import pandas as pd
        _rows = [{"基金": k, "權重%": v["weight_pct"], "期間報酬%": v["fund_return_pct"],
                  "貢獻%": v["contribution_pct"]} for k, v in _contrib.items()]
        _df = pd.DataFrame(_rows).sort_values("貢獻%", ascending=False)
        st.dataframe(_df, use_container_width=True, hide_index=True)
        st.caption("「貢獻%」= 權重 × 該檔期間純價格報酬(各檔對組合總報酬的來源拆解)。")
