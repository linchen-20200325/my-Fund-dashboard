"""ui/helpers/fund_grp_health/backtest_section.py — 🔁 配置回測區塊(v19.427)。

L3 orchestrator:從已載入持倉(rich fund dict,含 series 原幣 NAV + currency)組
nav_by_code + ccy_by_code → 抓 USDTWD 歷史(L2 facade hot_money_service,不直呼 L1,§8.2)
→ L2 `services.allocation_backtest`(純數學回測)→ 排名表 + 勝出策略 + 匯率方向裁決 +
三輸出(動作清單 / 賣→買配對 / 目標權重%)。§1 全程誠實:缺料/排除顯式顯示。

本區只回答**「哪一套配置效益最高」**。逐檔的 live 買賣訊號在健診大表
(「淨值×匯率」/「策略燈號」欄)—— 原本這裡另有一個「當前訊號快照」expander,
取的是**回測最後一次月頻再平衡日**的 `final_signals`,卻與大表的 live spot 訊號
共用「當前」二字,同一檔可能一邊 🟢 一邊 🔴,是重複且會打架的第二資料源,已移除。

**教學非投資建議**:回測 ≠ 未來,樣本有限為方向性證據(caveat 先於結果)。
"""
from __future__ import annotations

import streamlit as st

from ui.helpers.render_state import not_ready, system_error


def render_allocation_backtest_section(funds: list) -> None:
    """🔁 配置回測 —— 回測 S0..S4 五套配置在台幣總報酬下表現,排名效益最高者 + 當前建議。

    funds: rich fund dict list(含 code / name / series 原幣 NAV / currency)。
    <2 檔有序列 → **印標題 + 一句灰字說明缺什麼**(2026-08-28 Q1;原本是靜默 `return`)。
    """
    from services.allocation_backtest import backtest_allocations, STRATEGY_LABELS
    from shared.signal_thresholds import BACKTEST_FX_FETCH_DAYS

    _nav = {f.get("code"): f.get("series") for f in (funds or [])
            if f.get("code") and f.get("series") is not None}

    # ⚠️ **標題移到守衛之前**(2026-08-28 客戶拍板 Q1)。線框 §01 的結論是:
    #    這不是一個設計問題,是一個**位置問題** —— 守衛寫在標題前面,使用者看不到
    #    任何痕跡;寫在後面,他看到標題和一句灰字說明。本檔原本 `return` 在標題之前,
    #    於是「只健診 1 檔」時整個 🔁 配置回測區塊零痕跡蒸發。
    #    (同檔 `switch_section.py` 早就是對的寫法:`if not _reds:` 在標題之後。)
    #
    # 三問各自的答案:
    #   問一 固定還是取決於資料? → **固定**。它是本頁骨架的一格,不是「每檔一個」的展開區。
    #   問二 使用者已經做過那個動作了嗎? → **已經按過 🩺 開始健診**(本函式只在
    #        `_funds_extra` 非空時才被呼叫)→ 判準命中:一律留灰色占位。
    #   問三 為什麼沒東西? → **還沒給足資料**(不是結構上不適用)→ ⬜ 而非 ➖。
    #
    # ⚠️ 兩種原因要分開講,否則指錯路:檔數本來就 <2 → 去多貼幾檔;
    #    檔數夠但抓不到淨值序列 → 多貼幾檔沒有用,原因在上方的逐檔失敗清單。
    st.divider()
    st.markdown("### 🔁 配置回測(哪套配置效益最高・教學非建議)")
    if len(_nav) < 2:
        _n_funds = len(funds or [])
        if _n_funds < 2:
            not_ready(
                f"配置回測要比較至少 2 檔的走勢,本次只健診了 {_n_funds} 檔",
                where="本頁上方「基金代號」欄位(多貼幾檔後重按 🩺 開始健診)")
        else:
            not_ready(
                f"配置回測需要至少 2 檔**抓得到淨值序列**的基金 —— "
                f"本次 {_n_funds} 檔裡只有 {len(_nav)} 檔有序列 —— 多貼幾檔不會改善這一項",
                where="本頁上方的逐檔失敗原因(看是哪幾檔沒抓到淨值)")
        return
    _ccy = {f.get("code"): f.get("currency", "") for f in funds if f.get("code")}
    _name = {f.get("code"): (f.get("name") or f.get("code")) for f in funds if f.get("code")}

    # USDTWD 歷史(L2 facade;失敗 → 美元計價基金被排除,誠實提示,§1)
    _fx = None
    try:
        from services.hot_money_service import fetch_usdtwd_frame
        _df, _err = fetch_usdtwd_frame(BACKTEST_FX_FETCH_DAYS)
        if _err or _df is None or getattr(_df, "empty", True):
            # 抓回來但是空的/帶錯誤 → 美元基金被排除 = 畫面上的結論會少幾檔,
            # 這是「算錯了」不是「還沒算」,所以走系統紅燈(線框 §03)。
            system_error(
                "USDTWD 匯率不可用,美元計價基金將被排除",
                RuntimeError(str(_err or "空序列")),
                hint="下方回測結果僅涵蓋台幣計價基金,不是完整組合。")
        else:
            _fx = _df.set_index("date")["usdtwd"]
    except Exception as _e:  # noqa: BLE001 — 抓失敗不拖垮整頁
        system_error("USDTWD 匯率抓取失敗,美元計價基金將被排除", _e,
                     hint="下方回測結果僅涵蓋台幣計價基金,不是完整組合。")

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
    from streamlit import column_config as _cc
    st.dataframe(
        pd.DataFrame(_rows), use_container_width=True, hide_index=True,
        column_config={
            "排名": _cc.NumberColumn("排名", format="%d", width="small",
                help="依 Sharpe → Calmar → CAGR 排;**in-sample**,不是未來保證。"),
            "策略": _cc.TextColumn("策略", width="medium"),
            "CAGR%": _cc.NumberColumn("CAGR%", format="%.2f %%",
                help="回測期間的年化複合報酬(台幣總報酬,含換手成本)。"),
            "年化σ%": _cc.NumberColumn("年化σ%", format="%.2f %%", help="年化波動度,越低越穩。"),
            "Sharpe": _cc.NumberColumn("Sharpe", format="%.2f", help="每單位波動換到的報酬。"),
            "最大回撤%": _cc.NumberColumn("最大回撤%", format="%.2f %%",
                help="期間內從高點跌到低點的最大幅度(負值)。"),
            "Calmar": _cc.NumberColumn("Calmar", format="%.2f", help="CAGR ÷ |最大回撤|。"),
        },
    )
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
        # 🟠 而非 🔴:排名表已渲染成功、每一個數字都還在且都是對的,掉的只有這張圖
        # → 使用者不可能因此做出錯誤決定。對照同區塊上方的 USDTWD 失敗(美元計價基金
        # 被**排除**,結論真的會變) —— 那個是 🔴。兩者不可穿同一件衣服(2026-08-28 稽核 M3)。
        system_error("配置回測淨值疊圖繪製失敗", _e_fig, degraded=True,
                     hint="上方排名表的數字不受影響,少的只有這張圖。")

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
                   "（想看**當前**買/賣訊號 → 見上方健診大表的「淨值×匯率」/「策略燈號」欄，"
                   "那是即時值;回測區講的是配置效益）")

    if _act["sell_buy_pairs"]:
        _prows = [{"賣出": _name.get(p["sell_code"], p["sell_code"]),
                   "賣σ": (round(p["sell_sigma"], 2) if p["sell_sigma"] is not None else "—"),
                   "→ 買進": (_name.get(p["buy_code"], p["buy_code"]) if p["buy_code"] else "無合適標的"),
                   "買σ": (round(p["buy_sigma"], 2) if p["buy_sigma"] is not None else "—")}
                  for p in _act["sell_buy_pairs"]]
        st.markdown("**🔄 賣→買 配對建議**")
        st.dataframe(
            pd.DataFrame(_prows), use_container_width=True, hide_index=True,
            column_config={
                "賣出": _cc.TextColumn("賣出", width="medium",
                    help="勝出策略在**最後一次再平衡日**判定要減碼/換出的檔。"),
                "賣σ": _cc.TextColumn("賣σ", width="small",
                    help="該檔當時的 σ rank(愈接近 0 = 愈貼近高點);'—' = 算不出(含 NAV 走平)。"),
                "→ 買進": _cc.TextColumn("→ 買進", width="medium",
                    help="配對的進場標的;無合適者誠實留「無合適標的」。"),
                "買σ": _cc.TextColumn("買σ", width="small", help="買方當時的 σ rank(愈負 = 跌愈深)。"),
            },
        )

    _wrows = [{"基金": _name.get(c, c), "目標權重%": v}
              for c, v in sorted(_act["target_weights_pct"].items(), key=lambda kv: -kv[1])]
    st.markdown("**⚖️ 建議配置權重**")
    st.dataframe(
        pd.DataFrame(_wrows), use_container_width=True, hide_index=True,
        column_config={
            "基金": _cc.TextColumn("基金", width="medium"),
            "目標權重%": _cc.NumberColumn("目標權重%", format="%.1f %%",
                help="勝出策略在最後一次再平衡日的目標配置(總和 100%);**教學示意,非投資建議**。"),
        },
    )
    # 「當前訊號快照」expander 已移除:它取的是回測**最後一次再平衡日**的 final_signals,
    # 與健診大表的 live spot 是兩個時點,兩邊卻都寫「當前」→ 同一檔會一綠一紅。
    # live 買賣訊號一律以大表「淨值×匯率」欄為準(單一資料源)。
