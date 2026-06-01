"""tab_allocation_simulator.py — 💼 配置模擬器 Tab (v18.260, Phase 6b).

前向月度模擬器：給定本金 / 年化配息率 / 4 段景氣劇本（復甦/擴張/放緩/衰退）→
每月配息分 3 桶（配股 DRIP / 領現 CASH / 停泊定存 STAY）→ 看 N 月後 TWD 終值 +
累計現金流。FX 支援固定 / 線性 / 隨機 GBM 蒙地卡羅。
"""
from __future__ import annotations

import pandas as pd
import streamlit as st


def render_allocation_simulator_tab() -> None:
    """主入口：💼 配置模擬器 Tab。"""
    st.markdown("## 💼 配置模擬器")
    st.caption(
        "前向模擬：給定本金 / 年化配息率 / 景氣劇本 → 每月配息分 3 桶（配股 DRIP / 領現 CASH / "
        "停泊定存 STAY）→ 看 N 月後 TWD 終值 + 累計現金流。FX 支援固定 / 線性 / 隨機 GBM 蒙地卡羅。"
    )

    # ── 預設值（從 Tab2 投資試算 stash 帶入）──────────────
    default_amount = 1_000_000.0
    default_yield = 6.0
    default_nav = 10.0
    default_fx = 32.0

    fund_data = st.session_state.get("fund_data") or {}
    fund_key = fund_data.get("full_key")
    if fund_key:
        calc = st.session_state.get(f"_calc_invest_{fund_key}")
        if calc:
            default_amount = float(calc.get("amount_twd") or default_amount)
            default_yield = float(calc.get("annual_div_rate") or default_yield)
            default_nav = float(calc.get("nav") or default_nav)
            # v18.279: 過濾掉 TWD 基金 stash 的 fx=1.0（v18.278 後 TWD 基金 fx_to_twd=1.0
            # 會被 stash，但 simulator 的 number_input min_value=10.0 → crash）
            _fx = calc.get("fx_to_twd")
            try:
                _fx_f = float(_fx) if _fx else 0.0
            except (TypeError, ValueError):
                _fx_f = 0.0
            if _fx_f >= 10.0:   # USD/EUR 等正常外幣
                default_fx = _fx_f
            st.success(
                f"✅ 已從 Tab2 投資試算 stash 帶入預設值"
                f"（基金：{fund_data.get('fund_name') or fund_key}）"
            )

    # ── 1️⃣ 基本設定 ──────────────────────────────────
    st.markdown("### 1️⃣ 基本設定")
    col_a, col_b, col_c, col_d = st.columns(4)
    with col_a:
        amount_twd = st.number_input(
            "本金（TWD）", min_value=10_000.0, max_value=100_000_000.0,
            value=default_amount, step=100_000.0, key="sim_amount",
        )
    with col_b:
        annual_yield_pct = st.number_input(
            "年化配息率 %", min_value=0.0, max_value=30.0,
            value=default_yield, step=0.5, key="sim_yield",
        )
    with col_c:
        initial_nav = st.number_input(
            "起始 NAV", min_value=0.1, max_value=10_000.0,
            value=default_nav, step=0.5, key="sim_nav",
        )
    with col_d:
        initial_fx = st.number_input(
            "起始 FX (1 USD = ? TWD)", min_value=10.0, max_value=100.0,
            value=default_fx, step=0.5, key="sim_fx",
        )

    # ── 2️⃣ 景氣劇本 ──────────────────────────────────
    st.markdown("### 2️⃣ 景氣劇本（4 段循環）")
    st.caption(
        "預設 4 段：**復甦 → 擴張 → 放緩 → 衰退**（完整景氣週期）。"
        "可直接編輯月數、phase 與月 NAV 變化率。"
    )
    from services.allocation_simulator import DEFAULT_PHASE_SCRIPT

    if "_sim_phase_script_df" not in st.session_state:
        st.session_state["_sim_phase_script_df"] = pd.DataFrame(DEFAULT_PHASE_SCRIPT)

    edited = st.data_editor(
        st.session_state["_sim_phase_script_df"],
        num_rows="dynamic",
        column_config={
            "months": st.column_config.NumberColumn(
                "月數", min_value=1, max_value=120, step=1,
            ),
            "phase": st.column_config.SelectboxColumn(
                "Phase", options=["復甦", "擴張", "放緩", "衰退"],
            ),
            "monthly_nav_change_pct": st.column_config.NumberColumn(
                "月 NAV 變化 %", min_value=-5.0, max_value=5.0,
                step=0.1, format="%.2f",
            ),
        },
        hide_index=True,
        use_container_width=True,
        key="sim_phase_editor",
    )
    try:
        total_months = int(edited["months"].sum())
    except Exception:
        total_months = 0
    st.caption(f"📅 總模擬期：**{total_months} 個月 ≈ {total_months / 12:.1f} 年**")

    # ── 3️⃣ 三桶比例 ──────────────────────────────────
    st.markdown("### 3️⃣ 配息分配（總和 100%，自動 normalize）")
    col_x, col_y, col_z = st.columns(3)
    with col_x:
        drip_pct = st.slider("配股 DRIP %", 0, 100, 70, key="sim_drip")
        st.caption("配息 ÷ NAV 立即換成新單位（複利）")
    with col_y:
        cash_pct = st.slider("領現金 %", 0, 100, 20, key="sim_cash")
        st.caption("配息直接累積外幣現金桶（無利息）")
    with col_z:
        stay_pct = st.slider("停泊定存 %", 0, 100, 10, key="sim_stay")
        st.caption("配息 × FX 換 TWD 進定存（月複利）")

    total_pct = drip_pct + cash_pct + stay_pct
    if total_pct == 0:
        st.error("⚠️ 三桶總和 = 0%，請至少設一桶")
        return
    if total_pct != 100:
        d_norm = drip_pct * 100 / total_pct
        c_norm = cash_pct * 100 / total_pct
        s_norm = stay_pct * 100 / total_pct
        st.warning(
            f"⚠️ 總和 {total_pct}% ≠ 100%，會自動 normalize 為 "
            f"(DRIP={d_norm:.1f}%, CASH={c_norm:.1f}%, STAY={s_norm:.1f}%)"
        )

    stay_yield_pct = st.number_input(
        "停泊定存年利率 %", min_value=0.0, max_value=10.0, value=1.5, step=0.1,
        key="sim_stay_yield",
    )

    # ── 4️⃣ FX 匯率模型 ────────────────────────────────
    st.markdown("### 4️⃣ FX 匯率模型")
    fx_model = st.radio(
        "匯率變化模型",
        options=["fixed", "linear", "random"],
        format_func=lambda x: {
            "fixed": "🔒 固定",
            "linear": "📈 線性",
            "random": "🎲 隨機（蒙地卡羅）",
        }[x],
        horizontal=True,
        key="sim_fx_model",
    )

    fx_end_value = initial_fx
    fx_volatility_pct = 2.0
    mc_runs = 1

    if fx_model == "linear":
        fx_end_value = st.number_input(
            "期末 FX", min_value=10.0, max_value=100.0,
            value=float(initial_fx) + 1.0, step=0.5, key="sim_fx_end",
        )
    elif fx_model == "random":
        col_v, col_n = st.columns(2)
        with col_v:
            fx_volatility_pct = st.number_input(
                "FX 年化波動 σ %", min_value=0.5, max_value=20.0,
                value=3.0, step=0.5, key="sim_fx_vol",
            )
        with col_n:
            mc_runs = st.slider(
                "蒙地卡羅次數", min_value=50, max_value=1000,
                value=200, step=50, key="sim_mc_runs",
            )
        st.caption(
            f"🎲 將跑 {mc_runs} 次模擬 → 5/50/95% quantile 帶 + 終值分佈統計"
        )

    # ── 跑模擬 ─────────────────────────────────────
    st.markdown("---")
    if not st.button("🚀 跑模擬", type="primary",
                     use_container_width=True, key="sim_run"):
        st.info("⬆️ 設定參數後按「跑模擬」")
        return

    from services.allocation_simulator import (
        SimulationParams,
        run_monte_carlo,
    )

    phase_script = []
    for _, r in edited.iterrows():
        try:
            n = int(r["months"])
        except Exception:
            continue
        if n <= 0:
            continue
        phase_script.append({
            "months": n,
            "phase": str(r["phase"]),
            "monthly_nav_change_pct": float(r["monthly_nav_change_pct"]),
        })
    if not phase_script:
        st.error("⚠️ 景氣劇本為空，無法模擬")
        return

    params = SimulationParams(
        amount_twd=float(amount_twd),
        annual_yield_pct=float(annual_yield_pct),
        initial_nav=float(initial_nav),
        initial_fx=float(initial_fx),
        phase_script=phase_script,
        drip_pct=float(drip_pct),
        cash_pct=float(cash_pct),
        stay_pct=float(stay_pct),
        stay_yield_pct=float(stay_yield_pct),
        fx_model=fx_model,
        fx_end_value=float(fx_end_value),
        fx_volatility_pct=float(fx_volatility_pct),
    )

    n_runs_actual = mc_runs if fx_model == "random" else 1
    with st.spinner(f"跑 {n_runs_actual} 次模擬..."):
        result = run_monte_carlo(params, n_runs=n_runs_actual)

    _render_simulation_results(result, fx_model)


def _render_simulation_results(result: dict, fx_model: str) -> None:
    """模擬結果展示：終值卡 + 走勢圖 + MC quantile + 月度資料."""
    st.markdown("### 📊 模擬結果")
    summary = result["summary"]

    cm1, cm2, cm3, cm4 = st.columns(4)
    cm1.metric(
        "基金桶終值",
        f"{summary['fund_value_twd']/10_000:.1f} 萬",
        help="期末單位數 × 期末 NAV × 期末 FX",
    )
    cm2.metric(
        "現金桶終值",
        f"{summary['cash_value_twd']/10_000:.1f} 萬",
        help="累積外幣現金 × 期末 FX",
    )
    cm3.metric(
        "定存桶終值",
        f"{summary['stay_twd']/10_000:.1f} 萬",
        help="累積 TWD 停泊金額（含每月複利）",
    )
    cm4.metric(
        "合計終值",
        f"{summary['total_twd']/10_000:.1f} 萬",
        delta=f"{summary['total_return_pct']:+.1f}%",
        help="基金桶 + 現金桶 + 定存桶",
    )

    cm5, cm6 = st.columns(2)
    cm5.metric(
        "累計領到現金（TWD）",
        f"{summary['cum_div_twd']/10_000:.1f} 萬",
        help="所有月份配息的 TWD 等值總和（含 DRIP 部分）",
    )
    cm6.metric(
        "平均月配息（TWD）",
        f"{summary['monthly_div_avg_twd']:,.0f}",
        help="月配息 TWD 的全期平均",
    )

    # ── 走勢圖 ──────────────────────────────────
    try:
        import plotly.graph_objects as go
        fig = go.Figure()

        ref_df = result["paths_sample"][0]
        x = ref_df.index

        fig.add_trace(go.Scatter(
            x=x, y=ref_df["fund_value_twd"] / 10_000,
            mode="lines", name="基金桶",
            line=dict(color="#1976d2", width=2),
        ))
        fig.add_trace(go.Scatter(
            x=x, y=ref_df["cash_value_twd"] / 10_000,
            mode="lines", name="現金桶",
            line=dict(color="#fb8c00", width=2),
        ))
        fig.add_trace(go.Scatter(
            x=x, y=ref_df["stay_twd"] / 10_000,
            mode="lines", name="定存桶",
            line=dict(color="#43a047", width=2),
        ))
        fig.add_trace(go.Scatter(
            x=x, y=ref_df["total_twd"] / 10_000,
            mode="lines", name="合計",
            line=dict(color="#212121", width=2.5, dash="dash"),
        ))

        # Monte Carlo: 多條淡色路徑當 fan chart
        if fx_model == "random" and len(result["paths_sample"]) > 1:
            for p in result["paths_sample"][1:30]:
                fig.add_trace(go.Scatter(
                    x=p.index, y=p["total_twd"] / 10_000,
                    mode="lines",
                    line=dict(color="rgba(180,180,180,0.35)", width=0.6),
                    showlegend=False, hoverinfo="skip",
                ))

        fig.update_layout(
            height=420,
            yaxis=dict(title="TWD（萬）"),
            xaxis=dict(title="月份"),
            hovermode="x unified",
            margin=dict(l=20, r=20, t=20, b=20),
        )
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.warning(f"⚠️ 走勢圖繪製失敗：{e}")

    # ── Monte Carlo: 終值分佈 ──────────────────────
    if result["terminal_quantiles"]:
        q = result["terminal_quantiles"]["total_twd"]
        st.markdown("#### 🎲 蒙地卡羅終值分佈（合計）")
        c1, c2, c3 = st.columns(3)
        c1.metric("悲觀情境 P5", f"{q['p5']/10_000:.1f} 萬")
        c2.metric("中位數 P50", f"{q['p50']/10_000:.1f} 萬")
        c3.metric("樂觀情境 P95", f"{q['p95']/10_000:.1f} 萬")
        st.caption(
            f"📊 {result['n_runs']} 次模擬：平均 {q['mean']/10_000:.1f} 萬，"
            f"標準差 {q['std']/10_000:.1f} 萬"
            f"（P95-P5 區間 = {(q['p95']-q['p5'])/10_000:.1f} 萬）"
        )

    # ── 月度資料表 ─────────────────────────────────
    with st.expander("📋 月度詳細資料（範例路徑）"):
        st.dataframe(result["paths_sample"][0], use_container_width=True)
