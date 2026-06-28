"""v18.163 PR：組合健康度 KPI helper（純函式）。

整合 4 個 MK 標籤指標（撿便宜雷達 / 留校查看 / 停利提醒 / 配置比例）
+ tab3 真實收益矩陣的 4 個現金流指標，
產出統一的 6 維度 KPI dict 給 Tab3 頂部 hero 用。
"""
from __future__ import annotations

import pandas as pd


def compute_health_kpis(portfolio_funds: list | None,
                         mk_df: pd.DataFrame | None = None) -> dict:
    """從 portfolio_funds + 預算好的 MK dataframe 算 6 個健康度指標。

    回傳 dict（所有數值預設 0 / "—"，缺資料安全）：
      # 配置維度
      n_classed:        歸類 Core/Satellite 的基金數
      pct_core:         核心 %
      pct_sat:          衛星 %
      ratio_label:      "核心 71% / 衛星 29%" or "—"
      ratio_delta:      "-9% vs 策略3 80/20" / "符合 策略3 80/20" / None

      # MK 標籤維度（來自 mk_df）
      n_buy:            🟢 撿便宜雷達（Buy_Zone / Buy_Zone_Deep）
      n_warn:           🔴 留校查看（Sharpe_Warning / Warning / Weak + Core 吃本金）
      n_take:           💰 停利提醒（衛星 Take_Profit）

      # 現金流維度（來自 portfolio_funds.metrics / moneydj_raw）
      n_funds:          組合基金總數（去重）
      n_cash_ok:        ✅ 含息 ≥ 配息
      n_eat:            🔴 吃本金（含息 < 配息 且 配息 > 0）
      n_na:             ⬜ 1Y 資料不足
    """
    out: dict = {
        "n_classed": 0, "pct_core": 0, "pct_sat": 0,
        "ratio_label": "—", "ratio_delta": None,
        "n_buy": 0, "n_warn": 0, "n_take": 0,
        "n_funds": 0, "n_cash_ok": 0, "n_eat": 0, "n_na": 0,
    }
    if not portfolio_funds:
        return out

    _seen: set = set()
    _uniq: list = []
    for _f in portfolio_funds:
        if not _f.get("loaded") or _f.get("load_error"):
            continue
        _c = str(_f.get("code", "") or "").strip().upper()
        if not _c or _c in _seen:
            continue
        _seen.add(_c)
        _uniq.append(_f)

    out["n_funds"] = len(_uniq)

    if mk_df is not None and not mk_df.empty:
        out["n_buy"] = int(
            mk_df["Price_Zone"].isin(["Buy_Zone", "Buy_Zone_Deep"]).sum()
        )
        out["n_warn"] = int(
            mk_df["Health_Check"].isin(
                ["Sharpe_Warning", "Warning", "Weak"]).sum()
        )
        if "Principal_Erosion" in mk_df.columns:
            out["n_warn"] += int(
                ((mk_df["MK_Class"] == "Core") &
                 (mk_df["Principal_Erosion"] == "Eroding")).sum()
            )
        out["n_take"] = int(
            ((mk_df["Price_Zone"] == "Take_Profit") &
             (mk_df["MK_Class"] == "Satellite")).sum()
        )
        n_core = int((mk_df["MK_Class"] == "Core").sum())
        n_sat = int((mk_df["MK_Class"] == "Satellite").sum())
        n_classed = n_core + n_sat
        out["n_classed"] = n_classed
        if n_classed > 0:
            out["pct_core"] = round(n_core / n_classed * 100)
            out["pct_sat"] = round(n_sat / n_classed * 100)
            out["ratio_label"] = (
                f"核心 {out['pct_core']}% / 衛星 {out['pct_sat']}%"
            )
            _gap = out["pct_core"] - 80
            out["ratio_delta"] = (f"{_gap:+d}% vs 策略3 80/20"
                                   if _gap else "符合 策略3 80/20")

    try:
        from ui.helpers.macro_helpers import compute_1y_total_return
    except ImportError:
        return out

    for _f in _uniq:
        _mj = _f.get("moneydj_raw", {}) or {}
        _m = _f.get("metrics", {}) or {}
        _ret_v, _ = compute_1y_total_return(_f)
        _is_real = _ret_v is not None
        try:
            _div = float(
                _mj.get("moneydj_div_yield")
                or _m.get("annual_div_rate") or 0
            )
        except (TypeError, ValueError):
            _div = 0.0
        if not _is_real:
            out["n_na"] += 1
        elif _div > 0 and _ret_v < _div:
            out["n_eat"] += 1
        else:
            out["n_cash_ok"] += 1

    return out


def render_hero_kpi_cards(kpis: dict) -> None:
    """v18.163：Tab3 頂部 6 卡 hero KPI（合併 mk_war_room + 配息矩陣兩段重複 KPI）。

    使用者只需要在 Tab3 頂部看一次 KPI，下方圖表段不再重複顯示。
    """
    import streamlit as st

    if not kpis or kpis.get("n_funds", 0) == 0:
        st.info("📊 組合健康儀表將在載入基金後上線。")
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("📊 組合基金數", f"{kpis['n_funds']} 檔",
              help="按 code 去重後的已載入基金數（同 code 跨多保單只算一次）")
    c2.metric("⚖️ 配置比例", kpis["ratio_label"],
              delta=kpis["ratio_delta"], delta_color="off",
              help="策略3 建議核心 80% / 衛星 20%；偏離過大代表結構失衡")
    _safe_total = kpis["n_funds"] - kpis["n_na"]
    _safe_label = (f"{kpis['n_cash_ok']}/{_safe_total} 檔"
                    if _safe_total > 0 else "—")
    _eat_delta = (f"-{kpis['n_eat']} 吃本金"
                   if kpis["n_eat"] else None)
    c3.metric("💵 現金流安全", _safe_label,
              delta=_eat_delta, delta_color="inverse",
              help=("含息報酬 ≥ 配息率 = 安全；< 配息率 = 吃本金警示。"
                    f"⬜ {kpis['n_na']} 檔 1Y 資料不足，未納入判定。"))

    c4, c5, c6 = st.columns(3)
    c4.metric("🟢 撿便宜雷達", f"{kpis['n_buy']} 檔",
              help="股價跌至 -1σ / -2σ 以下，符合分批進場條件")
    c5.metric("🔴 留校查看", f"{kpis['n_warn']} 檔",
              delta=(f"-{kpis['n_warn']}" if kpis["n_warn"] else None),
              delta_color="inverse",
              help="夏普<0 / 賺息賠本 / 跌破季線 三類紅黃燈合計（含 Core 吃本金）")
    c6.metric("💰 停利提醒", f"{kpis['n_take']} 檔",
              help="衛星標的突破布林上軌，建議部分減碼鎖利")
