"""v18.163 PR：組合健康度 KPI helper（純函式）。

整合 4 個 標籤指標（撿便宜雷達 / 留校查看 / 停利提醒 / 配置比例）
+ tab3 真實收益矩陣的 4 個現金流指標，
產出統一的 6 維度 KPI dict 給 Tab3 頂部 hero 用。
"""
from __future__ import annotations

import pandas as pd


def compute_health_kpis(portfolio_funds: list | None,
                         mk_df: pd.DataFrame | None = None) -> dict:
    """從 portfolio_funds + 預算好的  dataframe 算 6 個健康度指標。

    回傳 dict（所有數值預設 0 / "—"，缺資料安全）：
      # 配置維度 —— ⚠️ 這裡是「檔數」口徑（分母 = 被 歸類的檔數），
      # **不是**配置比例。金額口徑（Σ 投入本金 + policy_tier 優先 + 目標吃
      # portfolio_core_pct）的唯一真相在 ui/helpers/portfolio/allocation.py，
      # Tab3「① 配置總覽」「Hero 甜甜圈」「保單分組」三處都走那支。
      # 兩者本來就會不同（3 檔核心 = 60% 檔數，但可能持有 90% 的錢），
      # 故此處不再與任何目標值比較，避免和金額版的「目標偏差」打架。
      n_classed:        歸類 Core/Satellite 的基金數
      pct_core:         核心佔比 %（**檔數**）
      pct_sat:          衛星佔比 %（**檔數**）
      ratio_label:      "核心 3 檔 / 衛星 2 檔（檔數）" or "—"
      ratio_delta:      None（保留 key 供既有 caller，恆為 None）

      # 標籤維度（來自 mk_df）
      n_buy:            🟢 撿便宜雷達（Buy_Zone / Buy_Zone_Deep）
      n_warn:           🔴 留校查看（Sharpe_Warning / Warning / Weak + Core 吃本金）
      n_take:           💰 停利提醒（衛星 Take_Profit）
                        ⚠️ BL-0440：有已載入基金但 mk_df 為 None／空 → 以上三格為 **None**
                        （無法判定，不是 0 檔），並帶 `tags_unavailable=True`
      n_zone_na:        Price_Zone == "N/A"（價位區間無法判定）的檔數，供揭露

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

    # BL-0440(§1 Missing ≠ 0):有已載入基金、但標籤表拿不到(呼叫端建表失敗傳 None /
    # 建出空表)→ 三個標籤格**不是 0 檔,是無法判定**。原本留在預設 0,hero 顯示
    # 「🟢 撿便宜雷達 0 檔」把「沒算」說成「算過、沒有」。改 None,由 render 端顯示 ⬜。
    # (本 dict 是 L3 內部回傳值,不是 shared/schemas 契約;consumer 已同批更新。)
    out["n_zone_na"] = 0
    if _uniq and (mk_df is None or mk_df.empty):
        out["n_buy"] = None
        out["n_warn"] = None
        out["n_take"] = None
        out["tags_unavailable"] = True

    if mk_df is not None and not mk_df.empty:
        # BL-0440:價位區間無法判定(Price_Zone == "N/A")的檔數 —— 這些檔**沒有**被
        # 算進撿便宜／停利,畫面要揭露,不能讓 0 檔看起來像「全部確認沒有」。
        out["n_zone_na"] = int((mk_df["Price_Zone"] == "N/A").sum())
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
        # 2026-10-10（級別三態，S15）：未設定不進核心／衛星，另列檔數。
        n_unset = int((mk_df["MK_Class"] == "Unset").sum())
        if n_classed > 0:
            out["pct_core"] = round(n_core / n_classed * 100)
            out["pct_sat"] = round(n_sat / n_classed * 100)
            # 標題明寫「檔數」：這格是「幾檔核心 / 幾檔衛星」，不是資金配置比例。
            out["ratio_label"] = f"核心 {n_core} 檔 / 衛星 {n_sat} 檔"
            if n_unset:
                out["ratio_label"] += f" / ⬜ 未設定 {n_unset} 檔"
            # 目標比較刻意留空：目標值（portfolio_core_pct）是對**金額**的，
            # 拿來比檔數會給出與「① 配置總覽」相反的再平衡結論。
            out["ratio_delta"] = None
        elif n_unset:
            # 全部未設定：原本只剩「—」，看不出那幾檔去哪了。沿用上面同一段 S15 字串
            # （去掉前導「 / 」分隔），不新增文案；百分比照舊不算（沒有已設定的檔）。
            out["ratio_label"] = f"⬜ 未設定 {n_unset} 檔"

    # 2026-10-23 裁示 1B:現金流三格改走唯一吃本金判定 `check_eating_principal_1y_mk`
    # (1Y 含息 = 本地配息還原淨值法、年化配息率 = 近 12 個月實配 ÷ 最新淨值)。
    # 本檔原本自己讀 wb05 官方配息率、自己比大小 —— 同一檔基金在這格與健診大表會
    # 因輸入不同而得到不同結論(§2.1)。
    #   · 灰色 dict(資料未備／無法判定)→ n_na(缺料不得算成安全,§1)
    #   · eating_principal=True(含息 < 配息率,含 2pp 黃燈帶,與舊判式同語意)→ n_eat
    #   · 其餘 dict → n_cash_ok
    #   · None(非配息基金,吃本金不適用)→ 沿用舊契約:1Y 含息算得出來才算安全,否則 n_na
    try:
        from services.fund_total_return import compute_1y_total_return
        from services.health.dividend import check_eating_principal_1y_mk
    except ImportError:
        return out

    for _f in _uniq:
        try:
            _eat = check_eating_principal_1y_mk(_f)
        except Exception as _e_eat:  # noqa: BLE001 — 單檔判定炸掉 → 當缺料,不冒充安全
            import sys as _sys_eat
            print(f"[portfolio/health] {_f.get('code', '?')} 吃本金判定失敗:"
                  f"{type(_e_eat).__name__}: {_e_eat}", file=_sys_eat.stderr)
            _eat = {"alert_level": "grey"}
        if isinstance(_eat, dict):
            if _eat.get("alert_level") == "grey":
                out["n_na"] += 1
            elif _eat.get("eating_principal") is True:
                out["n_eat"] += 1
            else:
                out["n_cash_ok"] += 1
            continue
        _ret_v, _ = compute_1y_total_return(_f)
        if _ret_v is None:
            out["n_na"] += 1
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
    c2.metric("⚖️ 核心/衛星檔數", kpis["ratio_label"],
              delta=kpis["ratio_delta"], delta_color="off",
              help=("**檔數**口徑（分母 = 被 歸類的檔數），只回答「幾檔核心、幾檔衛星」。\n\n"
                    "要看**資金**配置比例與目標偏差，請看下方「① 配置總覽」的"
                    "「核心資產比例」卡與甜甜圈 —— 那裡是 Σ 投入本金加權，"
                    "3 檔核心可能只佔 60% 的檔數卻佔 90% 的錢，兩個數字本來就不同。"))
    _safe_total = kpis["n_funds"] - kpis["n_na"]
    _safe_label = (f"{kpis['n_cash_ok']}/{_safe_total} 檔"
                    if _safe_total > 0 else "—")
    _eat_delta = (f"-{kpis['n_eat']} 吃本金"
                   if kpis["n_eat"] else None)
    c3.metric("💵 現金流安全", _safe_label,
              delta=_eat_delta, delta_color="inverse",
              help=("含息報酬 ≥ 配息率 = 安全；< 配息率 = 吃本金警示。"
                    f"⬜ {kpis['n_na']} 檔 1Y 資料不足，未納入判定。"))

    # BL-0440:None = 標籤表無法建立 → 「⬜ 無法判定」,不顯示 0 檔;
    # Price_Zone 無法判定的檔數寫進 help(那幾檔不在 0 / N 的分子分母裡)。
    _UNK = "⬜ 無法判定"
    _zone_na = int(kpis.get("n_zone_na") or 0)
    _zone_na_note = (f"\n\n⬜ {_zone_na} 檔便宜價／布林上軌未取得，價位區間無法判定，未納入計數。"
                     if _zone_na else "")
    _tags_na_note = ("\n\n⬜ 本次標籤表建立失敗，三格皆無法判定（不是 0 檔）。"
                     if kpis.get("tags_unavailable") else "")

    def _cnt(v) -> str:
        return _UNK if v is None else f"{v} 檔"

    c4, c5, c6 = st.columns(3)
    c4.metric("🟢 撿便宜雷達", _cnt(kpis["n_buy"]),
              help="股價跌至 -1σ / -2σ 以下，符合分批進場條件" + _zone_na_note + _tags_na_note)
    c5.metric("🔴 留校查看", _cnt(kpis["n_warn"]),
              delta=(f"-{kpis['n_warn']}" if kpis["n_warn"] else None),
              delta_color="inverse",
              help="夏普<0 / 賺息賠本 / 跌破季線 三類紅黃燈合計（含 Core 吃本金）" + _tags_na_note)
    c6.metric("💰 停利提醒", _cnt(kpis["n_take"]),
              help="衛星標的突破布林上軌，建議部分減碼鎖利" + _zone_na_note + _tags_na_note)
