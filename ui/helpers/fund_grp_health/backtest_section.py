"""ui/helpers/fund_grp_health/backtest_section.py — 🔁 配置回測區塊(v19.427)。

L3 orchestrator:從已載入持倉(rich fund dict,含 series 原幣 NAV + currency)組
nav_by_code + ccy_by_code → 抓 USDTWD 歷史(L2 facade hot_money_service,不直呼 L1,§8.2)
→ L2 `services.allocation_backtest`(純數學回測)→ 排名表 + 勝出策略 + 匯率方向裁決 +
三輸出(動作清單 / 賣→買配對 / 目標權重%)+ 當前訊號快照。§1 全程誠實:缺料/排除顯式顯示。

**教學非投資建議**:回測 ≠ 未來,樣本有限為方向性證據(caveat 先於結果)。
"""
from __future__ import annotations

import streamlit as st

_TIER_ZH = {"buy": "🟢 進場佳", "sell": "🔴 出場佳", "watch": "⚪ 觀望",
            "na": "⬜ 無法判定", "hold": "➖ 持有", None: "⬜ —"}
_NAV_ZH = {"low": "低基期", "mid": "中性", "high": "高基期", "unknown": "資料不足"}
_FX_ZH = {"strong_twd": "台幣強", "neutral": "匯率中性", "weak_twd": "台幣弱", None: "—"}


def render_allocation_backtest_section(funds: list) -> None:
    """🔁 配置回測 —— 回測 S0..S4 五套配置在台幣總報酬下表現,排名效益最高者 + 當前建議。

    funds: rich fund dict list(含 code / name / series 原幣 NAV / currency)。<2 檔有序列 → 略過。
    """
    from services.allocation_backtest import backtest_allocations, STRATEGY_LABELS
    from shared.signal_thresholds import BACKTEST_FX_FETCH_DAYS

    _nav = {f.get("code"): f.get("series") for f in (funds or [])
            if f.get("code") and f.get("series") is not None}
    if len(_nav) < 2:
        return
    _ccy = {f.get("code"): f.get("currency", "") for f in funds if f.get("code")}
    _name = {f.get("code"): (f.get("name") or f.get("code")) for f in funds if f.get("code")}

    st.divider()
    st.markdown("### 🔁 配置回測(哪套配置效益最高・教學非建議)")

    # USDTWD 歷史(L2 facade;失敗 → 美元計價基金被排除,誠實提示,§1)
    _fx = None
    try:
        from services.hot_money_service import fetch_usdtwd_frame
        _df, _err = fetch_usdtwd_frame(BACKTEST_FX_FETCH_DAYS)
        if _err or _df is None or getattr(_df, "empty", True):
            st.caption(f"⬜ USDTWD 匯率不可用({_err or '空序列'}),美元計價基金將被排除。")
        else:
            _fx = _df.set_index("date")["usdtwd"]
    except Exception as _e:  # noqa: BLE001 — 抓失敗不拖垮整頁
        st.caption(f"⬜ USDTWD 匯率抓取失敗,美元計價基金將被排除:[{type(_e).__name__}] {str(_e)[:80]}")

    _res = backtest_allocations(_nav, _ccy, fx_series=_fx)
    if not _res.get("ok"):
        st.info(_res.get("reason") or "配置回測資料不足。")
        if _res.get("excluded"):
            st.caption("⬜ 排除:" + "、".join(
                f"{_name.get(e['code'], e['code'])}({e['reason']})" for e in _res["excluded"]))
        return

    st.warning(_res["caveat"])                                   # §1 caveat 先於結果
    _w = _res["window"]
    _extra = "　·　⚠️ 低信賴(共同歷史 <1 年)" if _res["flags"].get("low_confidence") else ""
    st.caption(f"期間 {_w['start']} ~ {_w['end']}({_w['n_days']} 交易日・{len(_res['included'])} 檔納入・"
               f"月頻再平衡・台幣總報酬・含換手成本){_extra}")
    if _res.get("excluded"):
        st.caption("⬜ 排除:" + "、".join(
            f"{_name.get(e['code'], e['code'])}({e['reason']})" for e in _res["excluded"]))

    import pandas as pd

    # ── 排名表(五策略全列,含 baseline)──
    _rows = []
    for _rank, _sid in enumerate(_res["ranking"], 1):
        _m = _res["results"][_sid]["metrics"]
        _rows.append({"排名": _rank, "策略": STRATEGY_LABELS[_sid],
                      "CAGR%": _m["cagr_pct"], "年化σ%": _m["ann_vol_pct"], "Sharpe": _m["sharpe"],
                      "最大回撤%": _m["max_drawdown_pct"], "Calmar": _m["calmar"]})
    st.dataframe(pd.DataFrame(_rows), use_container_width=True, hide_index=True)
    st.success(f"🏆 效益最高:**{STRATEGY_LABELS[_res['winner']]}**"
               "(依 Sharpe→Calmar→CAGR 排名;in-sample,勿當未來保證)")
    if not _res["flags"].get("s4_trained"):
        st.caption("⚠️ S4 效率前緣訓練不足/未收斂 → 已退回**等權**(排名中 S4 列等同 S0,僅供對照)。")

    # ── 淨值曲線疊圖 ──
    try:
        import plotly.graph_objects as go
        _fig = go.Figure()
        for _sid in _res["ranking"]:
            _eq = _res["results"][_sid]["equity_curve"]
            if _eq is not None and len(_eq) > 1:
                _fig.add_trace(go.Scatter(x=list(_eq.index), y=[float(v) for v in _eq.to_numpy()],
                                          mode="lines", name=STRATEGY_LABELS[_sid]))
        _fig.update_layout(height=360, yaxis_title="累積淨值(起始=1・台幣)",
                           margin=dict(t=10, b=10, l=5, r=5),
                           legend=dict(orientation="h", yanchor="bottom", y=1.02))
        st.plotly_chart(_fig, use_container_width=True)
    except Exception as _e_fig:  # noqa: BLE001 — 圖失敗不擋數據(排名表已在上方渲染)
        st.caption(f"⬜ 淨值疊圖繪製失敗(數據不受影響):[{type(_e_fig).__name__}]")

    # ── 匯率方向裁決(S1 現行 vs S2 反向)──
    st.markdown("**🧭 匯率方向裁決(S1 現行方向 vs S2 反向)**：" + _res["verdict_s1_vs_s2"]["wording"])

    # ── 三輸出(綁勝出策略)──
    _act = _res["actions"]
    st.markdown(f"#### 📋 勝出策略「{STRATEGY_LABELS[_res['winner']]}」建議")
    _al = _act["action_lists"]
    if _al["buy"] or _al["switch"]:
        _c1, _c2, _c3 = st.columns(3)
        _c1.markdown("**🟢 進場**\n\n" + ("、".join(_name.get(c, c) for c in _al["buy"]) or "—"))
        _c2.markdown("**🔴 轉出**\n\n" + ("、".join(_name.get(c, c) for c in _al["switch"]) or "—"))
        _c3.markdown("**⚪ 觀望**\n\n" + ("、".join(_name.get(c, c) for c in _al["watch"]) or "—"))
    else:
        st.caption("本策略不擇時(等權/靜態最佳)→ 無買賣切換動作;下方為目標配置權重。"
                   "（想看當前買/賣訊號 → 見底部「當前 淨值×匯率 訊號」)")

    if _act["sell_buy_pairs"]:
        _prows = [{"賣出": _name.get(p["sell_code"], p["sell_code"]),
                   "賣σ": (round(p["sell_sigma"], 2) if p["sell_sigma"] is not None else "—"),
                   "→ 買進": (_name.get(p["buy_code"], p["buy_code"]) if p["buy_code"] else "無合適標的"),
                   "買σ": (round(p["buy_sigma"], 2) if p["buy_sigma"] is not None else "—")}
                  for p in _act["sell_buy_pairs"]]
        st.markdown("**🔄 賣→買 配對建議**")
        st.dataframe(pd.DataFrame(_prows), use_container_width=True, hide_index=True)

    _wrows = [{"基金": _name.get(c, c), "目標權重%": v}
              for c, v in sorted(_act["target_weights_pct"].items(), key=lambda kv: -kv[1])]
    st.markdown("**⚖️ 建議配置權重**")
    st.dataframe(pd.DataFrame(_wrows), use_container_width=True, hide_index=True)

    # ── 當前 淨值×匯率 訊號快照(= 已上線 live 邏輯,與 winner 無關,永遠可看)──
    _snap = _res.get("current_signal_snapshot") or {}
    if _snap:
        with st.expander("📶 當前「淨值×匯率」訊號快照(現行方向・參考)", expanded=False):
            _srows = [{"基金": _name.get(c, c),
                       "淨值位階": _NAV_ZH.get(s.get("nav_level"), s.get("nav_level")),
                       "σ rank": (round(s["sigma_rank"], 2) if s.get("sigma_rank") is not None else "—"),
                       "匯率位階": _FX_ZH.get(s.get("fx_label"), "—"),
                       "訊號": _TIER_ZH.get(s.get("tier"), s.get("tier"))}
                      for c, s in _snap.items()]
            st.dataframe(pd.DataFrame(_srows), use_container_width=True, hide_index=True)
            st.caption("此快照為各檔**當前**淨值位階 × 匯率位階的現行方向 2D 訊號(不一定等於勝出策略);"
                       "回測排名才是「哪套配置效益最高」的依據。")
