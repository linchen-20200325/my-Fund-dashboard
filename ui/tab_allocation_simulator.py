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
    from services.allocation_simulator import (
        DEFAULT_PHASE_SCRIPT,
        STRATEGY_PRESETS,
        build_preset_matrix_df,
        get_preset_phase_script,
    )

    # ── v18.284：4 風格 × 4 階段 全展開對照表（橫向比較用，read-only）─────
    with st.expander("📊 4 風格 × 4 階段 對照表（全展開）", expanded=False):
        st.caption(
            "格式：D = DRIP / C = CASH / S = STAY（單位：%）。看完比較再用下方"
            "「策略 preset」selectbox 選一個 + ✨ 套用。"
        )
        st.dataframe(
            build_preset_matrix_df(),
            use_container_width=True,
        )

    # ── v18.280：4 風格策略 preset × 4 階段矩陣 ─────────────────
    st.markdown("#### 🎯 策略 preset（4 風格 × 4 階段）")
    _preset_keys = list(STRATEGY_PRESETS.keys())
    _preset_labels = [STRATEGY_PRESETS[k]["label"] for k in _preset_keys]
    col_preset, col_apply = st.columns([3, 1])
    with col_preset:
        _selected_label = st.selectbox(
            "選擇策略風格",
            options=_preset_labels,
            index=0,
            key="sim_preset_selectbox",
            help="切換 preset 後按「套用」即覆寫下方 4 階段的 DRIP/CASH/STAY 三桶比例"
                 "（月數 / 月 NAV 變化率保留）。",
        )
        _selected_key = _preset_keys[_preset_labels.index(_selected_label)]
        st.caption(f"📖 {STRATEGY_PRESETS[_selected_key]['desc']}")
    with col_apply:
        st.write("")  # 對齊
        if st.button("✨ 套用 preset", key="sim_preset_apply",
                     use_container_width=True):
            st.session_state["_sim_phase_script_df"] = pd.DataFrame(
                get_preset_phase_script(_selected_key))
            st.success(f"✅ 已套用 **{_selected_label}**：4 階段三桶比例已更新")

    if "_sim_phase_script_df" not in st.session_state:
        st.session_state["_sim_phase_script_df"] = pd.DataFrame(DEFAULT_PHASE_SCRIPT)
    else:
        # v18.287: session_state migration — 舊版本 cached 的 DataFrame 只有 3 欄
        # （月數/phase/monthly_nav_change_pct），缺 drip_pct/cash_pct/stay_pct → user
        # 即使升到 v18.286+ 也看不到新欄位，所有 phase 仍走 params 全期值（看起來都一樣）。
        _existing_df = st.session_state["_sim_phase_script_df"]
        _missing = [c for c in ("drip_pct", "cash_pct", "stay_pct")
                    if c not in _existing_df.columns]
        if _missing:
            # 從 DEFAULT_PHASE_SCRIPT 對應 phase 補回預設值，user 已修改的月數/NAV 保留
            _defaults_by_phase = {p["phase"]: p for p in DEFAULT_PHASE_SCRIPT}
            for _col in _missing:
                _existing_df[_col] = _existing_df.get("phase", pd.Series(dtype=object)).map(
                    lambda _ph: _defaults_by_phase.get(str(_ph), {}).get(_col, 33)
                ).fillna(33)
            st.session_state["_sim_phase_script_df"] = _existing_df
            st.info(
                "🔄 v18.287 session_state migration：補上 DRIP/CASH/STAY 三欄到舊紀錄。"
                "你的月數 / NAV 變化保留；策略欄已由預設值填入，可自由修改。"
            )

    # v18.286：data_editor 加 DRIP%/CASH%/STAY% 三欄讓 user 各 phase 獨立調策略
    st.caption(
        "💡 **v18.286 新**：每階段可獨立設 DRIP/CASH/STAY 配息策略。"
        "預設復甦多 DRIP、衰退多 STAY，user 可自由覆蓋。"
        "Section 3 的全期預設只有當階段未填策略時才會 fallback。"
    )
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
            "drip_pct": st.column_config.NumberColumn(
                "DRIP %", min_value=0, max_value=100, step=5, format="%d",
                help="配股再投入百分比（該 phase 內）",
            ),
            "cash_pct": st.column_config.NumberColumn(
                "CASH %", min_value=0, max_value=100, step=5, format="%d",
                help="領現百分比（該 phase 內）",
            ),
            "stay_pct": st.column_config.NumberColumn(
                "STAY %", min_value=0, max_value=100, step=5, format="%d",
                help="停泊百分比（該 phase 內）",
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
        _seg = {
            "months": n,
            "phase": str(r["phase"]),
            "monthly_nav_change_pct": float(r["monthly_nav_change_pct"]),
        }
        # v18.287：把 user 在 data_editor 編輯的 DRIP/CASH/STAY 也帶進 phase_script
        # 否則 simulator 看不到 per-phase 設定 → 所有 phase 用 params 全期值
        for _c in ("drip_pct", "cash_pct", "stay_pct"):
            if _c in r and pd.notna(r[_c]):
                try:
                    _seg[_c] = float(r[_c])
                except (TypeError, ValueError):
                    pass
        phase_script.append(_seg)
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

    # ── v18.285：FX × NAV 4 象限策略分析 ────────────────────────────
    st.divider()
    _render_quadrant_analysis(
        initial_twd=float(amount_twd),
        nav=float(initial_nav),
        fx=float(initial_fx),
        annual_div_rate_pct=float(annual_yield_pct),
    )


def _render_quadrant_analysis(
    initial_twd: float, nav: float, fx: float, annual_div_rate_pct: float
) -> None:
    """v18.285：FX 升貶 × NAV 升降 4 象限分析。

    User 反饋：「想知道 台幣升值/貶值 × NAV 升降 四種狀態下，基金要怎麼調整
    才能得到最大效益」。對每象限模擬 DRIP/CASH/STAY 三策略，標出最佳。
    """
    st.markdown("### 🎯 FX × NAV 4 象限策略分析（user 反饋新加）")
    st.caption(
        "📐 對 **台幣升值/貶值 × NAV 升降** 4 種組合，分別模擬 **DRIP（配股再投入）/ "
        "CASH（配息領現）/ STAY（停泊外幣）** 三策略，找出每象限最佳。"
    )
    from services.quadrant_simulator import (
        DEFAULT_QUADRANTS,
        compare_strategies_per_quadrant,
        summarize_best_per_quadrant,
    )

    _qa_c1, _qa_c2 = st.columns(2)
    with _qa_c1:
        _fx_chg = st.slider(
            "FX 升貶幅度 (年化 %)",
            min_value=1, max_value=20, value=5, step=1,
            key="_quad_fx_chg_pct",
            help="設 5 = TWD 升 5% / 貶 5% 兩種對稱模擬",
        )
    with _qa_c2:
        _nav_chg = st.slider(
            "NAV 升降幅度 (年化 %)",
            min_value=2, max_value=30, value=10, step=1,
            key="_quad_nav_chg_pct",
            help="設 10 = NAV 漲 10% / 跌 10% 兩種對稱模擬",
        )
    _horizon = st.slider(
        "模擬期間 (月)", min_value=6, max_value=36, value=12, step=3,
        key="_quad_horizon",
    )

    # 動態 quadrants（user 可調幅度）
    _custom_quadrants = tuple([
        type(DEFAULT_QUADRANTS[0])(
            code=q.code, name=q.name,
            fx_change_pct_year=(-_fx_chg if q.fx_change_pct_year < 0 else _fx_chg),
            nav_change_pct_year=(-_nav_chg if q.nav_change_pct_year < 0 else _nav_chg),
            color=q.color, insight=q.insight,
        )
        for q in DEFAULT_QUADRANTS
    ])

    df_long = compare_strategies_per_quadrant(
        quadrants=_custom_quadrants,
        initial_twd=initial_twd, nav=nav, fx=fx,
        annual_div_rate_pct=annual_div_rate_pct,
        horizon_months=_horizon,
    )

    # 4 象限 metric 卡（每象限最佳）
    st.markdown(f"#### 🏆 每象限最佳策略（{_horizon} 個月後）")
    _summary_df = summarize_best_per_quadrant(df_long)
    _q_cols = st.columns(4)
    for _idx, q in enumerate(_custom_quadrants):
        with _q_cols[_idx]:
            _row = _summary_df[_summary_df["象限"] == q.name]
            if not _row.empty:
                _r = _row.iloc[0]
                st.metric(
                    label=q.name,
                    value=f"{_r['最佳策略']}",
                    delta=f"{_r['報酬 %']:+.2f}%",
                    help=q.insight,
                )
                st.caption(f"💰 期末 NT$ {int(_r['期末 TWD']):,}")

    # 完整 12-cell 矩陣
    st.markdown("#### 📋 完整矩陣（4 象限 × 3 策略 = 12 cells）")
    st.dataframe(df_long, use_container_width=True, hide_index=True)

    # 直覺解讀
    with st.expander("📖 直覺解讀（每象限該怎麼想）", expanded=False):
        for q in _custom_quadrants:
            st.markdown(f"**{q.name}**：{q.insight}")
        st.divider()
        st.caption(
            "💡 **公式**：每月更新 NAV (×(1+月化變化))、FX (×(1+月化變化))，"
            "配息 = units × NAV × (ADR%/12)。DRIP 加單位；CASH 立即換 TWD 累積；"
            "STAY 留原幣到期末才換。期末值 = units × 期末 NAV × 期末 FX + CASH 累計 + STAY × 期末 FX。"
        )

    # ── v18.286 Part B：歷史四象限分佈（用實際 NAV + FX）─────────────
    st.divider()
    st.markdown("### 📈 歷史四象限分佈（用實際資料看過去落在哪些象限）")
    st.caption(
        "💡 **User 反饋「歷史資料上面已經有這資料」確實沒錯**。"
        "拿某檔基金的歷史 NAV + USD/TWD 歷史匯率，按 rolling N 個月分類 → 看實際歷史上"
        "落在 Q1/Q2/Q3/Q4 各多少時間，輔助你判斷未來機率。"
    )

    _hist_c1, _hist_c2, _hist_c3 = st.columns([2, 1, 1])
    _hist_code = _hist_c1.text_input(
        "基金代號", value="ACTI94", key="_quad_hist_code",
        help="會用 fetch_nav_history_long 抓多年歷史",
    )
    _hist_window = _hist_c2.slider(
        "判定 window (月)", min_value=1, max_value=12, value=3, step=1,
        key="_quad_hist_window",
    )
    _hist_run = _hist_c3.button(
        "📊 跑歷史分析", use_container_width=True, key="_quad_hist_run",
    )

    if _hist_run and _hist_code.strip():
        with st.spinner(f"抓 {_hist_code} 歷史 NAV + USDTWD 匯率歷史..."):
            try:
                from repositories.fund_repository import fetch_nav_history_long
                from repositories.macro_repository import fetch_yf_close
                from services.quadrant_simulator import (
                    classify_historical_quadrants,
                    summarize_historical_distribution,
                )
                _nav_hist = fetch_nav_history_long(_hist_code.strip())
                _fx_hist = fetch_yf_close("USDTWD=X", range_="10y", interval="1d")
            except Exception as _e_h:
                st.error(f"歷史抓取失敗：{_e_h}")
                _nav_hist = pd.Series(dtype=float)
                _fx_hist = pd.Series(dtype=float)

        if _nav_hist.empty:
            st.warning(f"⚠️ 抓不到 {_hist_code} 歷史 NAV — 無法做歷史四象限分析")
        elif _fx_hist.empty:
            st.warning("⚠️ 抓不到 USDTWD 歷史匯率")
        else:
            _classified = classify_historical_quadrants(
                _nav_hist, _fx_hist, window_months=_hist_window,
            )
            if _classified.empty:
                st.warning("⚠️ 歷史對齊後資料不足以分類")
            else:
                _summary = summarize_historical_distribution(_classified)
                _total = _summary.get("_total", 0)
                _span = (_classified["date"].max() - _classified["date"].min()).days / 365.25
                st.success(
                    f"✅ 分析 {_total} 個月（涵蓋 {_span:.1f} 年，"
                    f"{_classified['date'].min().date()} ~ {_classified['date'].max().date()}）"
                )
                _hcs = st.columns(4)
                _q_names_short = {"Q1": "🔴 TWD升+NAV跌", "Q2": "🟠 TWD貶+NAV跌",
                                  "Q3": "🟢 TWD升+NAV漲", "Q4": "🟩 TWD貶+NAV漲"}
                for _i, _q in enumerate(["Q1", "Q2", "Q3", "Q4"]):
                    _s = _summary.get(_q, {})
                    with _hcs[_i]:
                        st.metric(
                            _q_names_short[_q],
                            f"{_s.get('pct', 0):.1f}%",
                            help=(
                                f"歷史 {int(_s.get('count', 0))} 個月落在此象限\n"
                                f"平均 NAV 變化 {_s.get('avg_nav_chg', 0):+.2f}% / "
                                f"FX {_s.get('avg_fx_chg', 0):+.2f}%"
                            ),
                        )
                with st.expander("📋 月度分類明細", expanded=False):
                    st.dataframe(_classified.tail(60), use_container_width=True, hide_index=True)
                st.caption(
                    "🎯 **怎麼用**：哪個象限歷史佔比最大，未來再次出現的可能性也較高 → "
                    "Section 3 該 phase 的策略應傾向該象限的最佳（Q1→STAY/Q2→DRIP/Q4→CASH）。"
                )


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
