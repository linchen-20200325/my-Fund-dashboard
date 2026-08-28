"""ui/helpers/portfolio_perf.py — 📊 組合績效區塊(v19.421)。

L3 orchestrator:從已載入持倉(rich fund dict,含 series + invest_twd)組 nav_by_code + 權重
→ L2 `services.portfolio_performance`(純數學)→ 4 KPI + 各檔貢獻表。權重依**投入金額**
(無則等權 fallback);§1 缺料/排除誠實顯示。
"""
from __future__ import annotations

import streamlit as st

from ui.helpers.render_state import system_error


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

    # v19.449 稽核 HIGH:跨幣別組合須換 TWD basis(含匯率損益),否則美元基金匯率被漏掉。
    # 抓 USDTWD 歷史(L2 facade,不直呼 L1,§8.2);失敗 → 美元基金被排除、誠實提示(§1)。
    _ccy = {f.get("code"): (f.get("currency", "") or "") for f in (funds or []) if f.get("code")}
    _fx = None
    try:
        from shared.signal_thresholds import BACKTEST_FX_FETCH_DAYS
        from services.hot_money_service import fetch_usdtwd_frame
        _fxdf, _fxerr = fetch_usdtwd_frame(BACKTEST_FX_FETCH_DAYS)
        if _fxdf is not None and not _fxdf.empty:
            _fx = _fxdf.set_index("date")["usdtwd"]
    except Exception as _e_fx:  # noqa: BLE001 — 匯率抓取失敗 → 美元基金排除,不靜默造假
        # 2026-08-28 顏色批次二之一：與 `fund_grp_health/backtest_section.py` 的
        # USDTWD 例外**逐字同一句、後果也一樣**（美元計價基金被排除 → 下方 4 個 KPI
        # 與貢獻表少算幾檔），那邊已是 🔴、這邊還是灰字。同一個失敗兩種顏色，
        # 顏色帶的資訊就變成「你在哪個分頁」而不是「這件事嚴不嚴重」。
        # degraded=False：有數字被排除 → 依 render_state.system_error 的通過條件，一律 🔴。
        system_error("USDTWD 匯率抓取失敗,美元計價基金將被排除", _e_fx,
                     hint="下方組合績效僅涵蓋台幣計價基金,不是完整組合。")

    st.divider()
    st.markdown("### 📊 組合績效(固定權重・日再平衡假設・TWD 計價)")
    _m = performance_metrics(_nav, _w, ccy_by_code=_ccy, fx_series=_fx)
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

    _contrib = contribution_by_fund(_nav, _w, ccy_by_code=_ccy, fx_series=_fx)
    if _contrib:
        import pandas as pd
        _rows = [{"基金": k, "權重%": v["weight_pct"], "期間報酬%": v["fund_return_pct"],
                  "貢獻%": v["contribution_pct"]} for k, v in _contrib.items()]
        _df = pd.DataFrame(_rows).sort_values("貢獻%", ascending=False)
        st.dataframe(_df, use_container_width=True, hide_index=True)
        st.caption("「貢獻%」= 權重 × 該檔期間 **TWD 計價報酬(含匯率)**(各檔對組合總報酬的來源拆解)。")


def _nav_weights_from_funds(funds: list):
    """funds(rich dict)→ (nav_by_code, weights, is_equal)。權重依 invest_twd,全 0 → 等權(旗標)。"""
    _nav = {f.get("code"): f.get("series") for f in (funds or [])
            if f.get("code") and f.get("series") is not None}
    _w = {c: float((next((f for f in funds if f.get("code") == c), {}) or {}).get("invest_twd") or 0)
          for c in _nav}
    if sum(_w.values()) <= 0:
        return _nav, {c: 1.0 for c in _nav}, True
    return _nav, _w, False


def render_efficient_frontier(funds: list) -> None:
    """🎯 效率前緣診斷(教學・非建議):隨機組合雲 + 前緣 + 你的組合落點 + max-Sharpe/min-var 示範。"""
    from services.portfolio_frontier import efficient_frontier_diagnostic

    _nav, _w, _equal = _nav_weights_from_funds(funds)
    if len(_nav) < 2:
        return

    st.divider()
    st.markdown("### 🎯 效率前緣診斷（教學・非建議）")
    _res = efficient_frontier_diagnostic(_nav, _w)
    if not _res.get("ok"):
        st.info(_res.get("reason") or "效率前緣資料不足。")
        return
    st.warning(_res["caveat"])                       # §1 caveat 先於圖

    import plotly.graph_objects as go
    _fig = go.Figure()
    _cl = _res["random_cloud"]
    _fig.add_trace(go.Scatter(
        x=[v * 100 for v in _cl["vol"]], y=[v * 100 for v in _cl["ret"]],
        mode="markers", name="隨機組合",
        marker=dict(size=4, opacity=0.35, color=_cl["sharpe"], colorscale="Viridis",
                    colorbar=dict(title="Sharpe"))))
    if len(_res["frontier"]) >= 2:
        _fr = sorted(_res["frontier"], key=lambda p: p["vol"])
        _fig.add_trace(go.Scatter(
            x=[p["vol"] * 100 for p in _fr], y=[p["ret"] * 100 for p in _fr],
            mode="lines+markers", name="效率前緣", line=dict(width=2, color="#00C853")))
    _cur = _res.get("current")
    if _cur:
        _fig.add_trace(go.Scatter(
            x=[_cur["vol"] * 100], y=[_cur["ret"] * 100], mode="markers", name="目前組合",
            marker=dict(symbol="star", size=16, color="#FF1744")))
    for _key, _nm, _sym in (("max_sharpe", "最大 Sharpe（示範）", "diamond"),
                            ("min_var", "最小變異（示範）", "square")):
        _p = _res.get(_key)
        if _p:
            _fig.add_trace(go.Scatter(
                x=[_p["vol"] * 100], y=[_p["ret"] * 100], mode="markers", name=_nm,
                marker=dict(symbol=_sym, size=13, color="#FFB300")))
    _fig.update_layout(height=460, xaxis_title="年化波動 σ (%)", yaxis_title="年化報酬 (%)",
                       margin=dict(t=10, b=10, l=5, r=5),
                       legend=dict(orientation="h", yanchor="bottom", y=1.02))
    st.plotly_chart(_fig, use_container_width=True)

    _fl = _res["flags"]
    _notes = []
    if _fl["near_singular"] or _fl["ridge_applied"]:
        _notes.append("⚠️ 共變異數近奇異,前緣極不穩定,僅示意")
    if _fl["low_confidence"]:
        _notes.append("樣本 <1 年,低信賴")
    if _fl["mu_degenerate"]:
        _notes.append("各檔期望報酬幾乎相同,前緣退化為單點")
    if _fl["zero_variance_codes"]:
        _notes.append("零變異基金:" + "、".join(_fl["zero_variance_codes"]))
    if _res["excluded"]:
        _notes.append("排除:" + "、".join(f"{e['code']}({e['reason']})" for e in _res["excluded"]))
    _wsrc = "等權(無投入金額)" if _equal else "投入金額加權"
    st.caption(f"期間 {_res['start']} ~ {_res['end']}({_res['n_days']} 交易日・{len(_res['codes'])} 檔・"
               f"目前組合權重:{_wsrc}・年化**算術平均** μ + 樣本共變異數・rf {_res['rf_annual'] * 100:.1f}%)。"
               "★「目前組合」的報酬用算術 μ,與上方組合績效的**幾何**年化報酬略有差異(高約 ½σ²)。"
               + ("　·　".join([""] + _notes) if _notes else ""))

    _ms = _res.get("max_sharpe")
    if _ms:
        import pandas as pd
        _wrows = [{"基金": c, "目前權重%": round((_cur["weights"].get(c, 0) if _cur else 0) * 100, 1),
                   "示範最佳權重%（最大Sharpe）": round(w * 100, 1)}
                  for c, w in _ms["weights"].items()]
        st.dataframe(pd.DataFrame(_wrows), use_container_width=True, hide_index=True)
        st.caption("☝️ **示範最佳權重僅供理解風險/報酬取捨,切勿照做**(樣本雜訊會放大成極端不穩權重)。")
