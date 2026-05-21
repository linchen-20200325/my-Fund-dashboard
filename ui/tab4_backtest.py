"""ui/tab4_backtest.py — 歷史回測 Tab（v18.124 B-C.2）

從 app.py 抽出 Tab4（歷史回測）的渲染邏輯。

設計：
- 純函式 render_backtest_tab() -> None，**零閉包依賴**（不接收 ind/phase 等參數）
- 完全依賴 st.session_state.portfolio_funds 取得已載入基金資料
- imports 跟 app.py 同路徑：services/backtest_service / models/policy /
  repositories/fund_repository

對外 API:
- render_backtest_tab() -> None

v11.0 D-24 規劃但因「Streamlit with tab: closure 設計」擱置；v18.124 因 Tab4
實際無閉包依賴成為 B-C.2 PoC（緊隨 B-C.1 Tab6 之後）。
"""
from __future__ import annotations

import concurrent.futures as _bt_cf

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from models.policy import fund_pk_str
from repositories.fund_repository import fetch_fund_from_moneydj_url
from services.backtest_service import (
    backtest_portfolio,
    calc_performance_metrics,
    quick_backtest,
)


def render_backtest_tab() -> None:
    """渲染歷史回測 Tab — 基金多選 + 期間/權重設定 + 績效摘要 + 淨值/回撤圖。"""
    st.markdown("## 🔬 歷史回測")
    st.caption("選取組合中已載入的基金，或輸入新基金代碼，模擬歷史績效並計算指標。")

    # ── 選擇回測基金 ──────────────────────────────────────────────────────────
    pf_loaded = [
        f for f in st.session_state.portfolio_funds
        if f.get("loaded") and not f.get("load_error")
    ]

    # v18.82: 新增「按保單組合」模式 — 選一張保單 → 自動納入該保單所有已載入基金 + invest_twd 權重
    _bt_mode = st.radio(
        "回測模式",
        options=["🎯 按保單組合（推薦）", "🔧 自訂選擇基金"],
        horizontal=True, key="bt_mode",
        help="按保單組合 = 選保單 → 自動帶入所有基金 + 按投資金額比例分權重；自訂 = 手動挑基金與權重",
    )

    col_bt_left, col_bt_right = st.columns([3, 2])
    _by_policy_locked = (_bt_mode == "🎯 按保單組合（推薦）")

    with col_bt_left:
        st.markdown("#### 選取要回測的基金")
        bt_pk_to_fund: dict = {}
        bt_codes_from_pf: list = []
        _bt_policy_weights: dict = {}   # code → weight % (按保單模式才填)

        if not pf_loaded:
            st.info("組合基金尚無已載入資料，請先至「組合基金」頁籤新增並載入基金。")
        elif _by_policy_locked:
            # ── 按保單組合 ──
            bt_pk_to_fund = {fund_pk_str(f): f for f in pf_loaded}
            _bt_policies = sorted({(_f.get("policy_id") or "(未綁)")
                                    for _f in pf_loaded})
            _bt_sel_pid = st.selectbox(
                "1️⃣ 選保單（該保單下所有已載入基金將自動納入回測）",
                _bt_policies, key="bt_policy_pid",
            )
            _bt_pid_funds = [f for f in pf_loaded
                              if (f.get("policy_id") or "(未綁)") == _bt_sel_pid]
            if not _bt_pid_funds:
                st.warning(f"⚠️ 保單 `{_bt_sel_pid}` 下無已載入基金")
            else:
                bt_codes_from_pf = [f.get("code", "") for f in _bt_pid_funds]
                # 權重 = invest_twd 占該保單總投入的 %；若全部 = 0 退化為等權重
                _tot_inv_pid = sum(int(f.get("invest_twd", 0) or 0)
                                    for f in _bt_pid_funds)
                if _tot_inv_pid > 0:
                    for f in _bt_pid_funds:
                        _w_pid = round(
                            int(f.get("invest_twd", 0) or 0) / _tot_inv_pid * 100, 2)
                        _bt_policy_weights[f.get("code", "")] = _w_pid
                else:
                    _w_eq = round(100.0 / len(_bt_pid_funds), 2)
                    for f in _bt_pid_funds:
                        _bt_policy_weights[f.get("code", "")] = _w_eq
                # 即時預覽
                _prev_rows = []
                for f in _bt_pid_funds:
                    _c = f.get("code", "?")
                    _nm = (f.get("name") or _c)[:24]
                    _inv = int(f.get("invest_twd", 0) or 0)
                    _w = _bt_policy_weights.get(_c, 0)
                    _prev_rows.append({
                        "代碼": _c, "基金名稱": _nm,
                        "投資金額 (TWD)": f"NT${_inv:,}",
                        "權重 %": f"{_w:.2f}%",
                    })
                st.caption(
                    f"📊 將回測 **{len(_bt_pid_funds)} 檔**基金，"
                    f"總投入 **NT${_tot_inv_pid:,}** — 權重按投資金額比例配置"
                )
                st.dataframe(pd.DataFrame(_prev_rows),
                              use_container_width=True, hide_index=True)
        else:
            # ── 自訂選擇（原 flow）──
            bt_pk_to_fund = {fund_pk_str(f): f for f in pf_loaded}
            bt_pks = list(bt_pk_to_fund.keys())
            def _bt_label(pk: str) -> str:
                _f = bt_pk_to_fund[pk]
                _pid = _f.get("policy_id") or "(未綁)"
                _name = (_f.get("name") or _f.get("code", "?"))[:24]
                return f"{_pid}/{_f.get('code','?')} – {_name}"
            bt_selected = st.multiselect(
                "從組合基金選取（可多選）",
                options=bt_pks,
                default=bt_pks[:min(3, len(bt_pks))],
                format_func=_bt_label,
                key="bt_multi_select",
            )
            bt_codes_from_pf = [bt_pk_to_fund[p]["code"] for p in bt_selected]

        # 額外輸入（兩個模式都允許）
        bt_extra_raw = st.text_input(
            "額外加入基金代碼（逗號分隔，選填）",
            placeholder="例：BM0019X, BM0021X",
            key="bt_extra_input",
        )
        bt_extra_codes = [
            c.strip() for c in bt_extra_raw.split(",") if c.strip()
        ]
        bt_all_codes = list(dict.fromkeys(bt_codes_from_pf + bt_extra_codes))

    with col_bt_right:
        st.markdown("#### 回測設定")
        bt_period = st.selectbox(
            "回測期間",
            ["近 1 年", "近 2 年", "近 3 年", "近 5 年", "全部"],
            index=2, key="bt_period",
        )
        bt_rebalance = st.selectbox(
            "再平衡頻率",
            ["月底再平衡", "季底再平衡", "買入持有"],
            index=0, key="bt_rebalance",
        )
        rebalance_map = {"月底再平衡": "ME", "季底再平衡": "QE", "買入持有": None}

        if bt_all_codes:
            wt_rows = []
            if _by_policy_locked and _bt_policy_weights:
                # 按保單模式 → 權重 readonly 顯示（已按 invest_twd 自動算好）
                st.markdown("**各基金權重（按投資金額自動分配）**")
                st.caption("💡 若想改動權重，切到「🔧 自訂選擇基金」模式")
                for code in bt_all_codes:
                    _w_def = _bt_policy_weights.get(code, 0.0)
                    if code not in _bt_policy_weights:
                        # 額外加入的代碼仍用等權 fallback
                        _w_def = round(100 / len(bt_all_codes), 1)
                    st.metric(code, f"{_w_def:.2f}%")
                    wt_rows.append(float(_w_def))
            else:
                default_wts = [round(100 / len(bt_all_codes), 1)] * len(bt_all_codes)
                st.markdown("**各基金權重（%）**")
                for idx, code in enumerate(bt_all_codes):
                    w_val = st.number_input(
                        code, min_value=0.0, max_value=100.0,
                        value=float(default_wts[idx]),
                        step=5.0, key=f"bt_wt_{code}",
                    )
                    wt_rows.append(w_val)
        else:
            wt_rows = []

    # ── 執行回測 ─────────────────────────────────────────────────────────────
    st.divider()
    run_bt = st.button("▶ 執行回測", type="primary", key="run_backtest_btn",
                       disabled=len(bt_all_codes) == 0)

    # v18.92: 快速模式預設開（cache-only），補抓改 opt-in + 硬性 timeout
    _bt_force_refetch = st.checkbox(
        "🌐 同時嘗試補抓全歷史（網路慢/被 proxy 擋時可能卡住，每支 20s timeout）",
        value=False, key="bt_force_refetch",
        help="預設關閉 = 只用已載入 cache（快）；勾選後若 cache 不足會嘗試補抓全歷史，"
              "每支基金最多等 20 秒，超時就用 cache 退而求其次。",
    )

    if run_bt and bt_all_codes:
        # v18.89: 修「執行回測無反應」— 原本檢查 raw_mj.nav_history 永遠不命中
        # v18.90: cache 太短 → 自動補抓 + 涵蓋表 + 門檻降至 2 期
        # v18.92: 補抓改 opt-in + ThreadPoolExecutor timeout（解 proxy 無限重試卡死）
        bt_status = st.empty()
        bt_prog   = st.progress(0.0, text=f"準備回測 {len(bt_all_codes)} 支基金…")

        _period_months_map = {
            "近 1 年": 12, "近 2 年": 24, "近 3 年": 36,
            "近 5 年": 60, "全部": None,
        }
        _target_months = _period_months_map.get(bt_period) or 60
        _need_min_days = max(_target_months * 25, 60)
        _REFETCH_TIMEOUT_S = 20

        nav_data = {}
        fetch_errors = []
        coverage_rows = []
        _total = len(bt_all_codes)
        for _i, code in enumerate(bt_all_codes, 1):
            bt_prog.progress((_i - 1) / _total, text=f"[{_i}/{_total}] {code} — 讀取已載入淨值…")
            cached = next((f for f in pf_loaded if f.get("code") == code), None)
            _s_cached = cached.get("series") if cached else None
            _s_use: pd.Series | None = None
            _source_tag = ""

            # ① cache 任何長度都先收下（即使短也比沒有好）
            if isinstance(_s_cached, pd.Series) and len(_s_cached) >= 4:
                try:
                    _s_use = _s_cached.copy()
                    _s_use.index = pd.to_datetime(_s_use.index)
                    _s_use = _s_use.astype(float).sort_index()
                    _source_tag = f"cache({len(_s_use)}d)"
                except Exception as e:
                    fetch_errors.append(f"{code} 既有淨值解析失敗: {e}")

            # ② 補抓僅在 opt-in 模式下執行，且加硬性 timeout 防 proxy 無限重試
            if _bt_force_refetch and (_s_use is None or len(_s_use) < _need_min_days):
                _s_short = _s_use
                bt_prog.progress((_i - 1) / _total,
                                 text=f"[{_i}/{_total}] {code} — 補抓 MoneyDJ（最多 {_REFETCH_TIMEOUT_S}s）…")
                url_candidate = f"https://www.moneydj.com/funddj/ya/yp001000.djhtm?a={code}"
                _s_new = None
                try:
                    with _bt_cf.ThreadPoolExecutor(max_workers=1) as _ex:
                        _fut = _ex.submit(fetch_fund_from_moneydj_url, url_candidate)
                        _res = _fut.result(timeout=_REFETCH_TIMEOUT_S)
                    _s_new = (_res or {}).get("series")
                except _bt_cf.TimeoutError:
                    fetch_errors.append(f"{code}: 補抓 timeout ({_REFETCH_TIMEOUT_S}s) — 用 cache 退而求其次")
                except Exception as e:
                    fetch_errors.append(f"{code}: 補抓例外 {type(e).__name__} {str(e)[:80]} — 用 cache")

                if isinstance(_s_new, pd.Series) and len(_s_new) >= 4:
                    _s_new = _s_new.copy()
                    _s_new.index = pd.to_datetime(_s_new.index)
                    _s_new = _s_new.astype(float).sort_index()
                    if _s_short is not None:
                        _s_use = pd.concat([_s_short, _s_new])
                        _s_use = _s_use[~_s_use.index.duplicated(keep="last")].sort_index()
                        _source_tag = f"cache+refetch({len(_s_use)}d)"
                    else:
                        _s_use = _s_new
                        _source_tag = f"refetch({len(_s_use)}d)"
                # 補抓失敗 → 保留 _s_short 即可
                elif _s_short is None:
                    fetch_errors.append(f"{code}: 無 cache 且補抓無新資料")

            if _s_use is not None and len(_s_use) >= 4:
                nav_data[code] = _s_use
                _span_d = (_s_use.index.max() - _s_use.index.min()).days
                coverage_rows.append({
                    "代碼": code, "點數": len(_s_use),
                    "起": _s_use.index.min().strftime("%Y-%m-%d"),
                    "迄": _s_use.index.max().strftime("%Y-%m-%d"),
                    "涵蓋天數": _span_d, "來源": _source_tag,
                })
            elif _s_use is None and cached is None:
                fetch_errors.append(f"{code}: 不在已載入組合，請至「組合基金」載入該基金")

        bt_prog.progress(1.0, text=f"淨值擷取完成（成功 {len(nav_data)}/{_total}）")

        if fetch_errors:
            for err in fetch_errors:
                st.warning(f"⚠️ {err}")

        if coverage_rows:
            with st.expander(f"📋 各基金淨值涵蓋範圍（{len(coverage_rows)} 支）", expanded=False):
                st.dataframe(pd.DataFrame(coverage_rows),
                              use_container_width=True, hide_index=True)

        if not nav_data:
            bt_status.error("無法取得任何基金淨值資料，無法執行回測。")
        else:
            # 建立 NAV DataFrame，對齊日期
            nav_df = pd.DataFrame(nav_data).dropna(how="all")
            _full_span_days = (nav_df.index.max() - nav_df.index.min()).days if len(nav_df) > 0 else 0

            # 依期間截取
            _pm = _period_months_map.get(bt_period)
            if _pm:
                cutoff = nav_df.index.max() - pd.DateOffset(months=_pm)
                nav_df = nav_df[nav_df.index >= cutoff]

            # 對齊後刪除全 NaN 行，再前向填充
            nav_df = nav_df.ffill().dropna(how="all")

            # v18.92: cache 太短時，月底 resample 必失敗 → 自動改用週頻/日頻
            _nav_full = pd.DataFrame(nav_data).dropna(how="all").ffill().dropna(how="all")
            nav_monthly = nav_df.resample("ME").last().dropna(how="all")
            _resample_freq = "月底"
            if len(nav_monthly) < 2:
                # 月底不夠 → 試週頻
                nav_monthly = nav_df.resample("W-FRI").last().dropna(how="all")
                _resample_freq = "週末（月底樣本 <2 期，自動降週頻）"
                if len(nav_monthly) < 2:
                    # 週頻也不夠 → 用所有可用資料（不再篩期間）
                    nav_df = _nav_full
                    nav_monthly = nav_df.resample("W-FRI").last().dropna(how="all")
                    _resample_freq = (f"週末（指定期間「{bt_period}」資料太短，"
                                      f"已自動用完整 {_full_span_days} 天）")

            if len(nav_monthly) < 2:
                _all_span = (nav_df.index.max() - nav_df.index.min()).days if len(nav_df) > 0 else 0
                bt_status.error(
                    f"📉 有效淨值樣本不足（僅 {len(nav_monthly)} 期，需 ≥2 期）。\n\n"
                    f"**已抓到資料總長度**：{_full_span_days} 天（{len(_nav_full)} 點）\n"
                    f"**回測期間 `{bt_period}` 後篩剩**：{_all_span} 天\n\n"
                    "💡 **解法**：\n"
                    "- 回 Tab2「組合基金」重新載入該基金以取得完整歷史\n"
                    "- 或勾「🌐 同時嘗試補抓全歷史」再執行（注意 proxy 可能擋住）\n"
                    "- 或縮短回測期間至「近 1 年」"
                )
            else:
                # 建立組合回報
                codes_avail = [c for c in bt_all_codes if c in nav_monthly.columns]
                if not codes_avail:
                    bt_status.error("所選基金均無有效淨值資料。")
                else:
                    # 權重
                    raw_wts = {
                        code: wt_rows[bt_all_codes.index(code)]
                        for code in codes_avail
                    }
                    total_w = sum(raw_wts.values()) or 1.0
                    wts = pd.Series({c: v / total_w for c, v in raw_wts.items()})

                    # v18.92: 月頻 → freq=12 / 週頻 → freq=52
                    _bt_freq = 12 if _resample_freq == "月底" else 52
                    bt_result = backtest_portfolio(
                        nav_monthly[codes_avail],
                        wts,
                        rebalance=rebalance_map[bt_rebalance] if _bt_freq == 12 else None,
                    )
                    metrics = calc_performance_metrics(
                        bt_result["equity_curve"],
                        bt_result["portfolio_return"],
                        rf=0.02, freq=_bt_freq,
                    )

                    bt_status.success(
                        f"回測完成 — {len(nav_monthly)} 期{_resample_freq}資料 "
                        f"（{nav_monthly.index[0].strftime('%Y-%m-%d')} ~ "
                        f"{nav_monthly.index[-1].strftime('%Y-%m-%d')}）"
                    )

                    # ── v18.110：短樣本警告（2 期 returns 只算 total/ann/MDD，σ 系列不顯）─
                    if metrics.get("is_partial"):
                        st.warning(
                            f"⚠️ 短樣本警告：僅 {metrics.get('periods','?')} 期 returns（≥3 期才可算 σ/Sharpe/Sortino/Calmar）。"
                            f"目前只顯示 **總報酬 / 年化報酬 / 最大回撤** 三項；其餘指標顯 `—`。"
                            f"建議延長回測期間或在「組合基金」載入更多歷史 NAV。"
                        )
                    elif not metrics:
                        st.error(
                            "❌ 樣本不足（returns < 2 期），無法計算任何指標。"
                            "請至「組合基金」載入更多歷史 NAV 或勾選「補抓全歷史」後重試。"
                        )

                    # ── 指標卡 ───────────────────────────────────────────────
                    st.markdown("### 📊 績效摘要")
                    m1, m2, m3, m4, m5, m6 = st.columns(6)
                    m1.metric("總報酬", f"{metrics.get('total_return','—')}%")
                    m2.metric("年化報酬", f"{metrics.get('ann_return','—')}%")
                    m3.metric("年化波動", f"{metrics.get('ann_vol','—')}%")
                    m4.metric("Sharpe", f"{metrics.get('sharpe','—')}")
                    m5.metric("Sortino", f"{metrics.get('sortino','—')}")
                    m6.metric("最大回撤", f"{metrics.get('max_drawdown','—')}%")

                    # ── 淨值曲線圖（v18.92 改 plotly 避開 altair × Py3.14 不相容）─
                    st.markdown("### 📈 組合淨值曲線")
                    eq = bt_result["equity_curve"].reset_index()
                    eq.columns = ["日期", "淨值指數"]
                    _fig_eq = go.Figure()
                    _fig_eq.add_trace(go.Scatter(
                        x=eq["日期"], y=eq["淨值指數"],
                        mode="lines", line=dict(color="#58a6ff", width=2),
                        name="組合淨值",
                    ))
                    _fig_eq.update_layout(
                        paper_bgcolor="#0e1117", plot_bgcolor="#161b22",
                        font_color="#e6edf3", height=320,
                        margin=dict(t=10, b=40, l=50, r=20),
                        xaxis=dict(gridcolor="#1e2a3a"),
                        yaxis=dict(gridcolor="#1e2a3a", title="淨值指數"),
                    )
                    st.plotly_chart(_fig_eq, use_container_width=True)

                    # ── 回撤圖 ───────────────────────────────────────────────
                    st.markdown("### 📉 水下曲線（Drawdown）")
                    dd = bt_result["drawdown"].reset_index()
                    dd.columns = ["日期", "回撤%"]
                    dd["回撤%"] = dd["回撤%"] * 100
                    _fig_dd = go.Figure()
                    _fig_dd.add_trace(go.Scatter(
                        x=dd["日期"], y=dd["回撤%"],
                        mode="lines", line=dict(color="#ff4444", width=1.5),
                        fill="tozeroy", fillcolor="rgba(244,68,68,0.25)",
                        name="Drawdown",
                    ))
                    _fig_dd.update_layout(
                        paper_bgcolor="#0e1117", plot_bgcolor="#161b22",
                        font_color="#e6edf3", height=260,
                        margin=dict(t=10, b=40, l=50, r=20),
                        xaxis=dict(gridcolor="#1e2a3a"),
                        yaxis=dict(gridcolor="#1e2a3a", title="回撤 %",
                                   ticksuffix="%"),
                    )
                    st.plotly_chart(_fig_dd, use_container_width=True)

                    # ── 個別基金快速回測 ─────────────────────────────────────
                    st.markdown("### 🔍 個別基金指標對比")
                    single_rows = []
                    for code in codes_avail:
                        s_metrics = quick_backtest(nav_monthly[code].dropna(), freq=12)
                        single_rows.append({
                            "基金代碼": code,
                            "總報酬(%)": s_metrics.get("total_return", "—"),
                            "年化報酬(%)": s_metrics.get("ann_return", "—"),
                            "年化波動(%)": s_metrics.get("ann_vol", "—"),
                            "Sharpe": s_metrics.get("sharpe", "—"),
                            "Sortino": s_metrics.get("sortino", "—"),
                            "最大回撤(%)": s_metrics.get("max_drawdown", "—"),
                            "Calmar": s_metrics.get("calmar", "—"),
                        })
                    st.dataframe(pd.DataFrame(single_rows), use_container_width=True)

                    # v18.159: cache 回測結果供下方 AI summary widget 取用
                    st.session_state["_bt_last_result"] = {
                        **{k: metrics.get(k, "—") for k in
                           ("total_return", "ann_return", "ann_vol", "sharpe",
                            "sortino", "max_drawdown", "calmar")},
                        "single_rows": single_rows,
                    }

    elif not run_bt and bt_all_codes:
        st.info("設定完成後按「▶ 執行回測」開始分析。")
    else:
        st.info("請先在上方選取基金，再執行回測。")

    # v18.159：通用 AI 白話文總結 widget（4 視角 selectbox）
    _render_tab4_ai_summary()


def _render_tab4_ai_summary() -> None:
    """v18.159 Tab4 末端：4 視角 AI 白話文總結 widget。
    snapshot 從上方 single_rows / 回測結果 session_state cache 取（若有）。"""
    import os
    from ui.helpers.ai_summary import render_ai_summary_widget  # noqa: PLC0415
    gemini_key = os.environ.get("GEMINI_API_KEY", "")

    bt_result = st.session_state.get("_bt_last_result")  # 由 run_bt 區塊填入（若有）
    if not bt_result:
        return  # 尚未跑過回測，不掛 widget

    lines = ["## 回測結果快照"]
    if "period" in bt_result:
        lines.append(f"- 回測期間：{bt_result['period']}")
    for k in ("total_return", "ann_return", "ann_vol", "sharpe",
              "sortino", "max_drawdown", "calmar"):
        if k in bt_result and bt_result[k] not in (None, "—"):
            lines.append(f"- {k}：{bt_result[k]}")
    single_rows = bt_result.get("single_rows", []) or []
    for r in single_rows[:8]:
        lines.append(
            f"- 個別基金 {r.get('基金代碼', '—')}："
            f"年化 {r.get('年化報酬(%)', '—')}%　|　Sharpe {r.get('Sharpe', '—')}"
        )

    snapshot = "\n".join(lines) if len(lines) > 1 else ""
    render_ai_summary_widget(
        tab_key="tab4",
        tab_label="歷史回測",
        snapshot=snapshot,
        headlines=[],   # Tab4 不接新聞
        gemini_api_key=gemini_key,
    )
