# -*- coding: utf-8 -*-
"""hot_money.py — 熱錢監測：三角交叉（外資 × 匯率） + 背離偵測（基金倉版）

移植自 user 上傳的 `a731802d-app.py`（單頁 Streamlit demo）+ 股票倉 PR #101。
基金倉特色：境外基金為主，但**台幣匯率變動會直接影響 TWD 換匯後報酬**，
故 user 仍受台灣熱錢動向間接影響（避險 / 套利 / 加碼留意點）。

設計（與 CLAUDE.md §2 一致）：
- 純函式 `build_signals` / `_yf_series_to_df` 無 streamlit 依賴，可單測
- `render_hot_money_section` 自取 USDTWD（`repositories.macro_repository.fetch_yf_close`）
  + 外資（FinMind，沿用既有 `tw_macro.FINMIND_BASE` URL）
- FinMind 失敗 / 空資料一律安全降級
"""
from __future__ import annotations

import datetime as _dt

import numpy as np
import pandas as pd
import streamlit as st

from shared.ttls import TTL_10MIN, TTL_30MIN


# 狀態白話解讀（針對基金 user 加上「境外基金影響」面）
STATE_TEXT = {
    "同步流入": "外資資金流入台股，台幣同步升值——對你的境外基金而言：USD/EUR 計價基金 TWD 換算後**短期受壓**（強勢台幣壓低換匯），但反映全球風險偏好上揚。",
    "同步流出": "外資撤出台股、台幣貶值——對境外基金：USD/EUR 計價基金 TWD 換算**有匯兌正貢獻**，但風險偏好下降，警覺全球資產同步壓力。",
    "背離｜熱錢停泊匯市": "台幣明顯升值，但外資並未同步買超台股。熱錢可能匯入停泊匯市觀望——對你境外基金：強勢台幣可能短期持續，USD 計價部位 TWD 換算受壓。",
    "背離｜買盤遭拋匯掩蓋": "外資在買超台股，台幣卻在走貶。匯率訊號被稀釋——對境外基金影響不確定，請看其他指標。",
    "背離｜匯市先撤": "台幣走貶但股市還沒對等賣壓——資金可能從匯市先行撤離，對 USD 計價基金 TWD 換算暫時有利，但要留意風險擴散。",
    "溫和流入": "外資小幅買超、匯率持平——資金溫和偏多、訊號不強，境外基金匯兌影響有限。",
    "溫和流出": "外資小幅賣超、匯率持平——資金溫和偏空、訊號不強，境外基金匯兌影響有限。",
    "中性／觀望": "外資買賣與匯率都無明顯方向——資金觀望，境外基金可純看標的基本面。",
}
DIVERGENCE_STATES = {"背離｜熱錢停泊匯市", "背離｜買盤遭拋匯掩蓋", "背離｜匯市先撤"}

_FINMIND_BASE = "https://api.finmindtrade.com/api/v4/data"


# ────────────────────────────────────────────────────────────────────────
# 純函式：信號計算（無 streamlit 依賴）
# ────────────────────────────────────────────────────────────────────────
def build_signals(flow_df: pd.DataFrame, fx_df: pd.DataFrame,
                   window: int, flow_thr: float, fx_thr: float) -> pd.DataFrame:
    """合併籌碼與匯率、計算滾動訊號並分類狀態（向量化）。"""
    cols = ["date", "foreign_net_yi", "usdtwd", "twd_apprec", "roll_flow",
            "roll_apprec", "flow_sig", "fx_sig", "state", "is_divergence",
            "interpretation"]
    if flow_df.empty or fx_df.empty:
        return pd.DataFrame(columns=cols)

    df = pd.merge(flow_df, fx_df, on="date", how="inner").sort_values("date").reset_index(drop=True)
    if df.empty:
        return pd.DataFrame(columns=cols)

    df["twd_apprec"] = -df["usdtwd"].pct_change() * 100.0
    df["roll_flow"] = df["foreign_net_yi"].rolling(window, min_periods=1).sum()
    df["roll_apprec"] = df["twd_apprec"].rolling(window, min_periods=1).sum()

    f = np.sign(np.where(df["roll_flow"].abs() >= flow_thr, df["roll_flow"], 0)).astype(int)
    x = np.sign(np.where(df["roll_apprec"].abs() >= fx_thr, df["roll_apprec"], 0)).astype(int)
    df["flow_sig"], df["fx_sig"] = f, x

    conds = [
        (f == 1) & (x == 1),
        (f == -1) & (x == -1),
        (x == 1) & (f <= 0),
        (f == 1) & (x == -1),
        (x == -1) & (f >= 0),
        (f == 1) & (x == 0),
        (f == -1) & (x == 0),
    ]
    labels = ["同步流入", "同步流出", "背離｜熱錢停泊匯市", "背離｜買盤遭拋匯掩蓋",
              "背離｜匯市先撤", "溫和流入", "溫和流出"]
    df["state"] = np.select(conds, labels, default="中性／觀望")
    df["is_divergence"] = df["state"].isin(DIVERGENCE_STATES)
    df["interpretation"] = df["state"].map(STATE_TEXT)
    return df


def _yf_series_to_df(series: pd.Series) -> pd.DataFrame:
    """`fetch_yf_close` 回傳的 pd.Series → 標準 [date, usdtwd] DataFrame。

    空 series / 壞輸入 → 空 df。
    """
    if series is None or len(series) == 0:
        return pd.DataFrame(columns=["date", "usdtwd"])
    out = pd.DataFrame({
        "date": pd.to_datetime(series.index).tz_localize(None) if (
            getattr(series.index, "tz", None) is not None
        ) else pd.to_datetime(series.index),
        "usdtwd": pd.to_numeric(series.values, errors="coerce"),
    }).dropna(subset=["usdtwd"])
    out = out[out["usdtwd"] > 0]
    return out.sort_values("date").reset_index(drop=True)


# ────────────────────────────────────────────────────────────────────────
# 資料層
# ────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=TTL_30MIN, show_spinner=False)
def fetch_foreign_flow_series(days: int, token: str = "") -> tuple[pd.DataFrame, str]:
    """抓最近 N 天外資買賣超（FinMind，沿用 tw_macro pattern + token kwarg）。

    Returns: (df[date, foreign_net_yi 億元], error_msg or "")
    """
    try:
        from fund_fetcher import fetch_url_with_retry
        end_d = _dt.date.today()
        start_d = end_d - _dt.timedelta(days=days + 14)
        params = {
            "dataset": "TaiwanStockTotalInstitutionalInvestors",
            "start_date": start_d.strftime("%Y-%m-%d"),
            "end_date":   end_d.strftime("%Y-%m-%d"),
        }
        if token:
            params["token"] = token
        r = fetch_url_with_retry(_FINMIND_BASE, params=params, timeout=15, retries=2)
    except Exception as e:
        return pd.DataFrame(columns=["date", "foreign_net_yi"]), f"FinMind 抓取失敗：{e}"

    if r is None:
        return pd.DataFrame(columns=["date", "foreign_net_yi"]), "FinMind 無回應"

    try:
        rows = r.json().get("data", []) or []
    except Exception as e:
        return pd.DataFrame(columns=["date", "foreign_net_yi"]), f"FinMind JSON 解析失敗：{e}"

    if not rows:
        return pd.DataFrame(columns=["date", "foreign_net_yi"]), "無資料回傳（可能為非交易日區間）"

    df = pd.DataFrame(rows)
    name_col = next((c for c in ("name", "institutional_investors") if c in df.columns), None)
    if name_col is None:
        return pd.DataFrame(columns=["date", "foreign_net_yi"]), f"FinMind 缺類別欄"
    mask = df[name_col].astype(str).str.contains("Foreign|外資", case=False, na=False, regex=True)
    fdf = df.loc[mask].copy()
    if fdf.empty:
        return pd.DataFrame(columns=["date", "foreign_net_yi"]), "FinMind 無 Foreign 類別資料"

    fdf["net"] = pd.to_numeric(fdf["buy"], errors="coerce") - pd.to_numeric(fdf["sell"], errors="coerce")
    out = (fdf.groupby("date", as_index=False)["net"].sum()
              .assign(foreign_net_yi=lambda d: d["net"] / 1e8)
              .loc[:, ["date", "foreign_net_yi"]])
    out["date"] = pd.to_datetime(out["date"])
    out = out.sort_values("date").reset_index(drop=True)
    # v19.151 F-PROV-1 phase 2:DataFrame.attrs 承載血緣(對齊 fetch_yf_close v19.83)
    out.attrs["source"] = "FinMind:TaiwanStockTotalInstitutionalInvestors"
    out.attrs["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
    # v19.186 Pandera Phase B:出口 schema 驗證(date 升序唯一 / net 無 NaN / 單位合理)
    # 契約違反 = 上游資料異常,§1 Fail Loud 直接拋(不靜默回髒資料)
    try:
        from shared.schemas import validate_foreign_flow
        out = validate_foreign_flow(out)
    except ImportError:
        pass  # pandera 不在環境(極罕見,requirements 已 pin)→ 降級不驗
    return out, ""


@st.cache_data(ttl=TTL_10MIN, show_spinner=False)
def fetch_usdtwd_series(days: int) -> tuple[pd.DataFrame, str]:
    """抓 USDTWD=X 時序（複用 macro_repository.fetch_yf_close + NAS proxy）。

    Returns: (df[date, usdtwd], error_msg or "")
    """
    try:
        from repositories.macro_repository import fetch_yf_close
        # range_ 換算：days 60-180 → 1y / 365 → 2y
        range_ = "2y" if days > 365 else "1y" if days > 90 else "6mo"
        series = fetch_yf_close("USDTWD=X", range_=range_, interval="1d")
    except Exception as e:
        return pd.DataFrame(columns=["date", "usdtwd"]), f"USDTWD 抓取失敗：{e}"

    df = _yf_series_to_df(series)
    if df.empty:
        return df, "USDTWD 無資料（Yahoo Chart API 失敗或被限流）"
    # 截取最近 days
    cutoff = pd.Timestamp.now() - pd.Timedelta(days=days)
    df = df[df["date"] >= cutoff].reset_index(drop=True)
    return df, ""


# ────────────────────────────────────────────────────────────────────────
# UI render（基金倉特化：加 disclaimer 強調對境外基金的相關性）
# ────────────────────────────────────────────────────────────────────────
def render_hot_money_section(token: str = "",
                                key_prefix: str = "fund_hm") -> None:
    """渲染熱錢三角交叉深度視圖（基金倉版，自取資料）。"""
    st.caption(
        "💡 **為何境外基金 user 也要看熱錢？** "
        "台灣熱錢動向 → 推動台幣升貶 → 直接影響你 USD/EUR 計價基金 TWD 換算後的報酬。"
        "強勢台幣短期壓低換匯，弱勢台幣有匯兌貢獻。看背離可以提早佈局加碼/減碼時機。"
    )

    # 控制 panel — inline columns 不污染 sidebar
    cc1, cc2, cc3, cc4 = st.columns([1, 1, 1, 1])
    days = cc1.slider("回看天數", 60, 365, 180, step=30,
                       key=f"{key_prefix}_days")
    window = cc2.slider("觀察窗格（交易日）", 3, 20, 5,
                          key=f"{key_prefix}_window")
    flow_thr = cc3.slider("外資累計門檻（億）", 10, 300, 50, step=10,
                            key=f"{key_prefix}_flow_thr")
    fx_thr = cc4.slider("台幣升貶門檻（%）", 0.1, 2.0, 0.5, step=0.1,
                          key=f"{key_prefix}_fx_thr")

    with st.spinner("📡 抓 USDTWD 匯率 + FinMind 外資買賣超..."):
        fx_df, xerr = fetch_usdtwd_series(days)
        flow_df, ferr = fetch_foreign_flow_series(days, token)
    for err in (xerr, ferr):
        if err:
            st.warning(err)
    if fx_df.empty or flow_df.empty:
        st.info("無法取得足夠資料；請等網路 / API 恢復後重試。")
        return

    sig = build_signals(flow_df, fx_df, window, flow_thr, fx_thr)
    if sig.empty:
        st.info("外資與匯率資料沒有重疊的交易日（區間太短？）")
        return

    latest = sig.iloc[-1]

    # v18.255 stash 給 Tab1 AI 白話總體檢
    try:
        st.session_state["_macro_hot_money"] = {
            "date": str(pd.Timestamp(latest["date"]).date()),
            "state": str(latest.get("state", "")),
            "is_divergence": bool(latest.get("is_divergence", False)),
            "interpretation": str(latest.get("interpretation", ""))[:200],
            "foreign_net_yi": float(latest.get("foreign_net_yi", 0) or 0),
            "roll_flow": float(latest.get("roll_flow", 0) or 0),
            "roll_apprec_pct": float(latest.get("roll_apprec", 0) or 0),
            "window": int(window),
        }
    except Exception:
        pass

    st.markdown(f"**📍 最新判讀（{pd.Timestamp(latest['date']).date()}）**")
    box = (st.warning if latest["is_divergence"]
           else (st.success if latest["state"] == "同步流入"
                 else st.error if latest["state"] == "同步流出"
                 else st.info))
    box(f"**{latest['state']}**　—　{latest['interpretation']}")

    # v19.51 ══ 📊 資料新鮮度條 ══（traffic-light 掛「資料截止日距今天數」，不受快取影響 + 強制重抓）
    _hm_cutoff = pd.Timestamp(latest["date"]).date()
    _hm_today = pd.Timestamp.now(tz="Asia/Taipei").date()
    _hm_days_old = (_hm_today - _hm_cutoff).days
    _hm_color = "#3fb950" if _hm_days_old <= 1 else ("#d29922" if _hm_days_old <= 4 else "#f85149")
    _hm_age_txt = "今日" if _hm_days_old <= 0 else f"{_hm_days_old} 天前"
    _hm_load_txt = pd.Timestamp.now(tz="Asia/Taipei").strftime("%m-%d %H:%M")
    _hcols = st.columns([5, 1])
    with _hcols[0]:
        st.markdown(
            f'<div style="background:#0d1117;border:1px solid #30363d;border-radius:8px;'
            f'padding:8px 14px;margin:4px 0 10px;display:flex;gap:18px;flex-wrap:wrap;align-items:center;font-size:12px;">'
            f'<span style="color:#8b949e;">📅 資料截止 <b style="color:{_hm_color};">{_hm_cutoff}（{_hm_age_txt}）</b></span>'
            f'<span style="color:#8b949e;">🕐 本次載入 <b style="color:#c9d1d9;">{_hm_load_txt} TW</b></span>'
            f'<span style="color:#8b949e;">📡 來源 <b style="color:#c9d1d9;">FinMind 外資（快取 30min）/ yfinance USDTWD（快取 10min）</b></span>'
            f'</div>', unsafe_allow_html=True)
    with _hcols[1]:
        if st.button("🔄 強制重抓", key=f"{key_prefix}_force_refresh",
                     help="v19.57 C1：僅清外資 / USDTWD / FRED / Yahoo（Tab1 範圍）快取，"
                          "Tab2~Tab5 基金/組合/政策快取不受影響"):
            try:
                from services.macro_service import clear_tab1_macro_caches
                clear_tab1_macro_caches(session_state=st.session_state)
            except Exception:
                pass
            st.rerun()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("最新外資買賣超", f"{latest['foreign_net_yi']:.1f} 億",
                help="正＝買超(資金進股市)，負＝賣超。")
    m2.metric(f"近{window}日累計外資", f"{latest['roll_flow']:.0f} 億")
    m3.metric("最新美元/台幣", f"{latest['usdtwd']:.3f}",
                help="數字下降＝台幣升值，TWD 換算 USD 基金受壓。")
    m4.metric(f"近{window}日台幣升貶", f"{latest['roll_apprec']:+.2f} %")

    # 三角交叉象限圖
    st.markdown("**🧭 三角交叉象限圖**")
    st.caption("橫軸＝外資累計買賣超，縱軸＝台幣累計升貶。右上＝同步流入，左下＝同步流出，"
                "左上/右下對角區＝背離。黑色菱形＝最新位置。")
    plot = sig.dropna(subset=["roll_flow", "roll_apprec"]).copy()
    try:
        import altair as alt
        scale = alt.Scale(
            domain=["同步流入", "同步流出", "背離｜熱錢停泊匯市", "背離｜買盤遭拋匯掩蓋",
                    "背離｜匯市先撤", "溫和流入", "溫和流出", "中性／觀望"],
            range=["#16a34a", "#dc2626", "#f59e0b", "#f97316", "#eab308",
                   "#86efac", "#fca5a5", "#94a3b8"])
        pts = alt.Chart(plot).mark_circle(size=70, opacity=0.55).encode(
            x=alt.X("roll_flow:Q", title=f"近{window}日外資累計買賣超(億)"),
            y=alt.Y("roll_apprec:Q", title=f"近{window}日台幣升貶(%)"),
            color=alt.Color("state:N", scale=scale, title="狀態"),
            tooltip=[alt.Tooltip("date:T", title="日期"),
                     alt.Tooltip("roll_flow:Q", title="累計買賣超(億)", format=".0f"),
                     alt.Tooltip("roll_apprec:Q", title="累計升貶(%)", format=".2f"),
                     alt.Tooltip("state:N", title="狀態")])
        v = alt.Chart(pd.DataFrame({"x": [0]})).mark_rule(strokeDash=[4, 4], color="#888").encode(x="x:Q")
        h = alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(strokeDash=[4, 4], color="#888").encode(y="y:Q")
        last = alt.Chart(plot.tail(1)).mark_point(
            size=320, shape="diamond", filled=True, color="black").encode(
                x="roll_flow:Q", y="roll_apprec:Q")
        st.altair_chart((pts + v + h + last).properties(height=360),
                          use_container_width=True)
    except Exception as _ce:
        # v18.240：altair 失敗（如 typing_extensions 太舊踩 TypedDict closed=）→
        # 不再 fallback st.scatter_chart（底層仍是 altair 會再炸），改純表格降級
        st.caption(f"⚠️ 象限圖渲染失敗（{type(_ce).__name__}），改顯示原始數據表：")
        _t = plot.tail(20)[["date", "roll_flow", "roll_apprec", "state"]].copy()
        _t["date"] = pd.to_datetime(_t["date"]).dt.date
        st.dataframe(
            _t.rename(columns={"date": "日期", "roll_flow": f"近{window}日外資(億)",
                                  "roll_apprec": f"近{window}日升貶(%)", "state": "狀態"}),
            use_container_width=True, hide_index=True, height=320)

    # 時序圖（雙保險：bar/line 也用 altair → 一併防呆）
    cc_a, cc_b = st.columns(2)
    with cc_a:
        st.markdown("**外資每日買賣超（億元）**")
        try:
            st.bar_chart(sig.set_index("date")["foreign_net_yi"], height=220)
        except Exception as _be:
            st.caption(f"⚠️ bar chart 失敗（{type(_be).__name__}），改顯示尾段數據：")
            st.dataframe(sig[["date", "foreign_net_yi"]].tail(10), use_container_width=True, hide_index=True)
    with cc_b:
        st.markdown("**美元/台幣（下降＝台幣升值）**")
        try:
            st.line_chart(sig.set_index("date")["usdtwd"], height=220)
        except Exception as _le:
            st.caption(f"⚠️ line chart 失敗（{type(_le).__name__}），改顯示尾段數據：")
            st.dataframe(sig[["date", "usdtwd"]].tail(10), use_container_width=True, hide_index=True)

    # 背離事件清單
    st.markdown("**⚠️ 近期背離事件**")
    div = sig[sig["is_divergence"]].copy()
    if div.empty:
        st.success("觀察區間內未偵測到明顯背離，資金訊號大致一致。")
    else:
        show = div.sort_values("date", ascending=False).head(15).copy()
        show["日期"] = show["date"].dt.date
        show = show.rename(columns={
            "state": "狀態",
            "roll_flow": f"近{window}日外資(億)",
            "roll_apprec": f"近{window}日升貶(%)",
            "interpretation": "解讀",
        })
        show[f"近{window}日外資(億)"] = show[f"近{window}日外資(億)"].round(0)
        show[f"近{window}日升貶(%)"] = show[f"近{window}日升貶(%)"].round(2)
        st.dataframe(
            show[["日期", "狀態", f"近{window}日外資(億)", f"近{window}日升貶(%)", "解讀"]],
            use_container_width=True, hide_index=True)
