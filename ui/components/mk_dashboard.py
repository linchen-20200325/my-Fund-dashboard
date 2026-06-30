# mk_dashboard.py — v18.12
# MK郭俊宏存股策略「智能戰情室」
# 重構目標：以「決策導向」呈現核心衛星 / 健康度 / 買賣區間，新手也能看懂。
#
# v18.12 增量（對齊 MK Phase 3 共同基金規格）：
# - 核心新增 Principal_Erosion 紅燈：連續 3 個月每月含息報酬皆為負（持續吃本金）
# - 核心新表格欄：年化波動(1Y%)，並依 <10/15/20% 三段標示低中高波動
# - 衛星新增 Benchmark_Lag 黃燈：連續兩季落後基準（預設 SPY，可切 QQQ）
# - 衛星新增「淨值 vs 基準」對比折線圖（同期歸一化）
#
# v18.11 增量：
# - 補三紅綠燈：夏普<0 紅燈 / 衛星 1M+3M 雙負黃燈 / -2σ 深綠超跌價
# - 表格加欄：夏普值、-2σ超跌價、衛星 1M/3M 動能、Sparkline 走勢迷你圖
# - KPI 卡新增「核心/衛星配置比例 vs MK 建議 80/20」
#
# 設計原則（呼應 CLAUDE.md §2 §4）：
# - 純函式、無 @st.cache_data（STATE.md 鐵律）
# - 重用 portfolio_funds[i]["metrics"] + ["series"]（calc_metrics 既有欄位），零額外 API
# - 標籤化：MK_Class / Health_Check / Momentum / Price_Zone
# - 三 Sub-Tab：核心戰情室 / 波段觀測站 / 3-3-3 篩選器
# - 新手 UX：白話文 expander + Tooltip + 條件高亮 + 隱藏雜訊欄

from __future__ import annotations
from typing import Optional
import math

import pandas as pd
import streamlit as st


# ════════════════════════════════════════════════════════════
# §1 數據標籤化 (Data Tagging)
# ════════════════════════════════════════════════════════════
def tag_mk_class(fund: dict) -> str:
    """MK_Class：Core（核心）/ Satellite（衛星）。重用既有 is_core 欄位。"""
    is_core = fund.get("is_core")
    if is_core is True:
        return "Core"
    if is_core is False:
        return "Satellite"
    return "Unknown"


def tag_health_check(fund: dict) -> str:
    """Health_Check：Sharpe_Warning / Warning / Weak / Healthy / N/A。

    規則（v18.11 同步 MK 規格三條紅綠燈）：
      A. sharpe < 0                        → Sharpe_Warning（承擔風險卻沒賺錢，最強警訊）
      B. ret_1y < annual_div_rate          → Warning（賺息賠本／吃本金）
      C. nav < ma60 且 ma20 < ma60         → Weak（跌破季線且下彎）
      其他                                  → Healthy
    缺欄 → N/A，避免 crash。
    """
    m = fund.get("metrics") or {}
    sharpe = m.get("sharpe")
    ret_1y = m.get("ret_1y")
    div_rate = m.get("annual_div_rate")
    nav = m.get("nav")
    ma60 = m.get("ma60")
    ma20 = m.get("ma20")

    if sharpe is not None:
        try:
            if float(sharpe) < 0:
                return "Sharpe_Warning"
        except (TypeError, ValueError):
            pass

    if ret_1y is None or div_rate is None or nav is None or ma60 is None:
        return "N/A"

    try:
        if float(ret_1y) < float(div_rate):
            return "Warning"
        if ma20 is not None and float(nav) < float(ma60) and float(ma20) < float(ma60):
            return "Weak"
        return "Healthy"
    except (TypeError, ValueError):
        return "N/A"


def tag_momentum(fund: dict) -> str:
    """Momentum（衛星專用）：Weakening / OK / N/A。

    規則：ret_1m < 0 且 ret_3m < 0 → Weakening（趨勢轉弱黃燈）
    Core 標的也會跑此標籤但 UI 只在衛星 Tab 顯示。
    """
    m = fund.get("metrics") or {}
    r1 = m.get("ret_1m")
    r3 = m.get("ret_3m")
    if r1 is None or r3 is None:
        return "N/A"
    try:
        if float(r1) < 0 and float(r3) < 0:
            return "Weakening"
        return "OK"
    except (TypeError, ValueError):
        return "N/A"


def tag_principal_erosion(fund: dict) -> str:
    """Principal_Erosion（核心專用）：Eroding / OK / N/A。

    MK 規格：「淨值漲跌 + 累計配息」整體含息報酬為負且**持續三個月**。
    實作：用 series 算近 3 個 22d 滾動報酬（month_n1/n2/n3），三段皆 < 0 → Eroding。
    缺 series 或長度不足 → N/A，零新 API。
    """
    s = fund.get("series")
    if s is None or not hasattr(s, "dropna"):
        return "N/A"
    try:
        s = s.dropna()
        if len(s) < 66:
            return "N/A"
        p_now = float(s.iloc[-1]); p_22 = float(s.iloc[-22])
        p_44 = float(s.iloc[-44]); p_66 = float(s.iloc[-66])
        if min(p_22, p_44, p_66) <= 0:
            return "N/A"
        m1 = p_now / p_22 - 1.0
        m2 = p_22 / p_44 - 1.0
        m3 = p_44 / p_66 - 1.0
        if m1 < 0 and m2 < 0 and m3 < 0:
            return "Eroding"
        return "OK"
    except (TypeError, ValueError, IndexError):
        return "N/A"


def _fund_age_years(series) -> Optional[float]:
    """v18.158：從 NAV series 算實際成立年資（NAV 起始日 → 今天，單位：年）。

    取代「以 ret_3y 存在性近似 3 年」的舊判斷 — `_ret(756)` 需 series ≥ 756 點，
    對低頻 NAV（週/雙週/月線）即使基金成立 5+ 年也回 None，造成 3-3-3 第一條誤判。
    """
    if series is None or not hasattr(series, "index"):
        return None
    try:
        s = series.dropna()
        if len(s) == 0:
            return None
        first = pd.to_datetime(s.index[0])
        now = pd.Timestamp.now(tz=first.tz) if first.tzinfo else pd.Timestamp.now()
        return float((now - first).days / 365.25)
    except (TypeError, ValueError, IndexError, AttributeError):
        return None


def _quarter_rets_from_series(s) -> Optional[tuple]:
    """從 NAV series 取得「最近兩季」報酬 (q1=近 65d, q2=前一季 65~130d)。"""
    if s is None or not hasattr(s, "dropna"):
        return None
    try:
        s = s.dropna()
        if len(s) < 130:
            return None
        p_now = float(s.iloc[-1]); p_65 = float(s.iloc[-65]); p_130 = float(s.iloc[-130])
        if min(p_65, p_130) <= 0:
            return None
        return (p_now / p_65 - 1.0, p_65 / p_130 - 1.0)
    except (TypeError, ValueError, IndexError):
        return None


def tag_benchmark_lag(fund: dict, bench_series) -> str:
    """Benchmark_Lag（衛星）：Lag / OK / N/A。

    MK 規格：「連續兩季落後大盤」→ 🟡 績效落後警訊。
    衛星 q1, q2 兩季季報酬皆 < 基準同期 → Lag。
    bench_series 取不到時回 N/A，不阻斷其他標籤。
    """
    fund_q = _quarter_rets_from_series(fund.get("series"))
    bench_q = _quarter_rets_from_series(bench_series)
    if fund_q is None or bench_q is None:
        return "N/A"
    try:
        if fund_q[0] < bench_q[0] and fund_q[1] < bench_q[1]:
            return "Lag"
        return "OK"
    except (TypeError, ValueError):
        return "N/A"


def _get_benchmark_series(ticker: str = "SPY"):
    """yfinance 抓基準收盤序列；以 st.session_state 做 session 級快取，每場次最多 1 次外呼。"""
    cache_key = "mk_bench_cache"
    cache = st.session_state.setdefault(cache_key, {})
    if ticker in cache:
        return cache[ticker]
    series = None
    try:
        import yfinance as yf
        tkr = yf.Ticker(ticker)
        hist = tkr.history(period="9mo", interval="1d", auto_adjust=False)
        if hist is not None and not hist.empty and "Close" in hist.columns:
            series = hist["Close"].dropna()
            series.index = pd.to_datetime(series.index).tz_localize(None)
    except Exception as e:  # noqa: BLE001
        print(f"[mk_dashboard] benchmark {ticker} fetch failed: {e}")
    cache[ticker] = series
    return series


def tag_price_zone(fund: dict) -> str:
    """Price_Zone：Buy_Zone_Deep（-2σ 以下）/ Buy_Zone（-1σ 以下）/
    Take_Profit（破布林上軌）/ Hold / N/A。

    重用 calc_metrics 既算的 buy1（-1σ）、buy2（-2σ）、bb_upper（20-day +2σ）。
    """
    m = fund.get("metrics") or {}
    nav = m.get("nav")
    buy1 = m.get("buy1")
    buy2 = m.get("buy2")
    bb_upper = m.get("bb_upper")

    if nav is None:
        return "N/A"
    try:
        nav_f = float(nav)
        if buy2 is not None and nav_f <= float(buy2):
            return "Buy_Zone_Deep"
        if buy1 is not None and nav_f <= float(buy1):
            return "Buy_Zone"
        if bb_upper is not None and nav_f > float(bb_upper):
            return "Take_Profit"
        return "Hold"
    except (TypeError, ValueError):
        return "N/A"


def build_mk_dataframe(portfolio_funds: list, bench_series=None) -> pd.DataFrame:
    """把 portfolio_funds 攤平成可顯示的 DataFrame，附帶五標籤、系統建議與 sparkline。

    bench_series：基準指數 NAV Series（如 SPY/QQQ），用於衛星 Benchmark_Lag 判定。
    """
    rows = []
    for f in portfolio_funds:
        if not f.get("loaded") or f.get("load_error"):
            continue
        m = f.get("metrics") or {}
        mk_class = tag_mk_class(f)
        health = tag_health_check(f)
        momentum = tag_momentum(f)
        zone = tag_price_zone(f)
        principal = tag_principal_erosion(f)
        bench_lag = tag_benchmark_lag(f, bench_series) if bench_series is not None else "N/A"
        rows.append({
            "代碼": f.get("code", "—"),
            "標的名稱": f.get("name") or f.get("code") or "—",
            "MK_Class": mk_class,
            "走勢(60D)": _series_tail(f.get("series"), 60),
            "目前市價": _safe_float(m.get("nav")),
            "含息總報酬(1Y%)": _safe_float(m.get("ret_1y")),
            "年化配息率(%)": _safe_float(m.get("annual_div_rate")),
            "夏普值": _safe_float(m.get("sharpe")),
            "年化波動(1Y%)": _safe_float(m.get("std_1y")),
            "近1M(%)": _safe_float(m.get("ret_1m")),
            "近3M(%)": _safe_float(m.get("ret_3m")),
            "便宜價(-1σ)": _safe_float(m.get("buy1")),
            "超跌價(-2σ)": _safe_float(m.get("buy2")),
            "停利價(+2σ)": _safe_float(m.get("bb_upper")),
            "季線(60MA)": _safe_float(m.get("ma60")),
            "Health_Check": health,
            "Momentum": momentum,
            "Price_Zone": zone,
            "Principal_Erosion": principal,
            "Benchmark_Lag": bench_lag,
            "MK體檢結論": _verdict_text(mk_class, health, momentum, zone,
                                       principal=principal, bench_lag=bench_lag),
            # 隱藏欄（給篩選用）
            "_std_1y": _safe_float(m.get("std_1y")),
            "_ret_3y": _safe_float(m.get("ret_3y")),
            "_age_years": _fund_age_years(f.get("series")),  # v18.158
        })
    return pd.DataFrame(rows)


def _series_tail(series, n: int) -> Optional[list]:
    """擷取最近 n 筆淨值序列為 list，供 st.column_config.LineChartColumn 使用。"""
    if series is None:
        return None
    try:
        if hasattr(series, "dropna"):
            s = series.dropna().tail(n)
            if s.empty:
                return None
            return [float(x) for x in s.tolist()]
        if isinstance(series, (list, tuple)) and series:
            return [float(x) for x in list(series)[-n:]]
    except (TypeError, ValueError):
        return None
    return None


# v19.222 P1-1:_safe_float 收口至 shared/converters.py SSOT
from shared.converters import safe_float as _safe_float  # noqa: E402
from shared.colors import GH_BG_PRIMARY, TRAFFIC_NEUTRAL  # v19.253 Phase 4-B2 #888 SSOT  # noqa: E402



def _verdict_text(mk_class: str, health: str, momentum: str, zone: str,
                  principal: str = "N/A", bench_lag: str = "N/A") -> str:
    """白話文系統建議（僅一句，避免雜訊）。優先序：紅燈 > 黃燈 > 綠燈 > 健康。

    紅燈：Sharpe_Warning > Principal_Erosion > Warning > Weak
    黃燈：Benchmark_Lag（衛星）> Momentum Weakening（衛星）> Take_Profit
    綠燈：Buy_Zone_Deep > Buy_Zone
    """
    if health == "Sharpe_Warning":
        return "🔴 夏普<0，承擔風險卻沒賺錢"
    if mk_class == "Core" and principal == "Eroding":
        return "🔴 連續 3 月含息報酬負，嚴重吃本金"
    if health == "Warning":
        return "🔴 賺息賠本，建議檢視換股"
    if health == "Weak":
        return "🟠 跌破季線，趨勢轉弱觀察"
    if mk_class == "Satellite" and bench_lag == "Lag":
        return "🟡 連續兩季落後大盤，績效落後警訊"
    if mk_class == "Satellite" and momentum == "Weakening":
        return "🟡 1M+3M 雙負，動能轉弱"
    if zone == "Buy_Zone_Deep":
        return "🟢🟢 進入超跌價，加大進場"
    if zone == "Buy_Zone":
        return "🟢 進入便宜價，可分批進場"
    if zone == "Take_Profit":
        return "🟡 觸及停利區，部分減碼"
    if health == "Healthy" and mk_class == "Core":
        return "✅ 核心健康，續抱領息"
    if health == "Healthy" and mk_class == "Satellite":
        return "✅ 衛星健康，等待訊號"
    return "—"


# ════════════════════════════════════════════════════════════
# §2 UI 分組 (Grouping) — KPI 卡片 + 三 Sub-Tab
# ════════════════════════════════════════════════════════════
def _render_buckets_diagnostic(df: pd.DataFrame) -> None:
    """v18.158：當「撿便宜雷達 / 留校查看警示 / 停利提醒」三籃子全為 0 時，
    加 expander 列出每檔 fund 的三標籤 (Price_Zone / Health_Check / Principal_Erosion)，
    讓 user 一眼看出是「metrics 缺欄 → 標籤 N/A」還是「組合確實全 Hold/Healthy」。
    """
    if df.empty:
        return
    n_buy = int(df["Price_Zone"].isin(["Buy_Zone", "Buy_Zone_Deep"]).sum())
    n_warn = int(df["Health_Check"].isin(["Sharpe_Warning", "Warning", "Weak"]).sum())
    n_warn += int(((df["MK_Class"] == "Core") &
                   (df["Principal_Erosion"] == "Eroding")).sum())
    n_take = int(((df["Price_Zone"] == "Take_Profit") &
                  (df["MK_Class"] == "Satellite")).sum())
    if max(n_buy, n_warn, n_take) > 0:
        return   # 至少一籃子有命中 → 不必展開診斷

    with st.expander("🔍 三籃子都 0？展開查每檔基金標籤", expanded=False):
        st.caption(
            "三籃子計數來自三標籤：`Price_Zone` / `Health_Check` / `Principal_Erosion`。\n"
            "若大量 `N/A` → metrics 缺欄位（buy1/buy2/bb_upper/sharpe/series 等）；\n"
            "若全 `Hold` + `Healthy` → 組合確實沒進場 / 停利 / 警示訊號。"
        )
        cols_show = ["代碼", "標的名稱", "MK_Class",
                     "Price_Zone", "Health_Check", "Principal_Erosion"]
        avail = [c for c in cols_show if c in df.columns]
        st.dataframe(df[avail], hide_index=True, use_container_width=True)


def _style_core(df: pd.DataFrame):
    """核心戰情室：Sharpe_Warning / Principal_Erosion 深紅 / Warning 紅 / Weak 橘 / Buy_Zone 系列綠。"""
    def _row_color(row):
        h = row.get("Health_Check")
        p = row.get("Principal_Erosion")
        z = row.get("Price_Zone")
        if h == "Sharpe_Warning" or p == "Eroding":
            return ["background-color: #5a1212"] * len(row)
        if h == "Warning":
            return ["background-color: #4a1f1f"] * len(row)
        if h == "Weak":
            return ["background-color: #3a2a1a"] * len(row)
        if z == "Buy_Zone_Deep":
            return ["background-color: #0f3a1a"] * len(row)
        if z == "Buy_Zone":
            return ["background-color: #1f3a25"] * len(row)
        return [""] * len(row)
    return df.style.apply(_row_color, axis=1)


def _style_satellite(df: pd.DataFrame):
    """波段觀測站：Sharpe_Warning 深紅 / Benchmark_Lag 暗黃 / Buy_Zone 系列綠 / Weakening 暗黃。"""
    def _row_color(row):
        z = row.get("Price_Zone")
        mo = row.get("Momentum")
        h = row.get("Health_Check")
        bl = row.get("Benchmark_Lag")
        if h == "Sharpe_Warning":
            return ["background-color: #5a1212"] * len(row)
        if z == "Buy_Zone_Deep":
            return ["background-color: #0f3a1a"] * len(row)
        if z == "Buy_Zone":
            return ["background-color: #1f3a25"] * len(row)
        if z == "Take_Profit":
            return ["background-color: #4a3315"] * len(row)
        if bl == "Lag" or mo == "Weakening":
            return ["background-color: #3a3315"] * len(row)
        return [""] * len(row)
    return df.style.apply(_row_color, axis=1)


_CORE_COLS = [
    "代碼", "標的名稱", "走勢(60D)", "目前市價",
    "含息總報酬(1Y%)", "年化配息率(%)", "夏普值", "年化波動(1Y%)",
    "便宜價(-1σ)", "超跌價(-2σ)", "停利價(+2σ)", "季線(60MA)",
    "MK體檢結論",
]

_SAT_COLS = [
    "代碼", "標的名稱", "走勢(60D)", "目前市價",
    "含息總報酬(1Y%)", "夏普值", "近1M(%)", "近3M(%)",
    "便宜價(-1σ)", "超跌價(-2σ)", "停利價(+2σ)",
    "MK體檢結論",
]

_333_COLS = [
    "代碼", "標的名稱", "走勢(60D)", "目前市價",
    "含息總報酬(1Y%)", "年化配息率(%)", "夏普值", "年化波動(1Y%)",
    "便宜價(-1σ)", "超跌價(-2σ)", "MK體檢結論",
]

_COL_CONFIG = {
    "走勢(60D)": st.column_config.LineChartColumn(
        "走勢(60D)", width="small",
        help="近 60 個交易日淨值走勢迷你圖（Sparkline）"),
    "目前市價": st.column_config.NumberColumn("目前市價", format="%.2f"),
    "含息總報酬(1Y%)": st.column_config.NumberColumn(
        "含息總報酬(1Y%)", format="%.2f",
        help="包含領到的股息與淨值漲跌的真實總獲利（近一年）"),
    "年化配息率(%)": st.column_config.NumberColumn(
        "年化配息率(%)", format="%.2f",
        help="近 12 期配息加總 ÷ 目前淨值，僅反映現金流回饋"),
    "夏普值": st.column_config.NumberColumn(
        "夏普值", format="%.2f",
        help="(年化報酬-無風險利率)/年化波動。<0 代表承擔風險卻沒賺錢"),
    "年化波動(1Y%)": st.column_config.NumberColumn(
        "年化波動(1Y%)", format="%.2f",
        help="近一年日報酬年化標準差；策略3 核心資產建議 <15%（低波動），>20% 代表波動偏高"),
    "近1M(%)": st.column_config.NumberColumn(
        "近1M(%)", format="%.2f",
        help="近 22 個交易日淨值報酬"),
    "近3M(%)": st.column_config.NumberColumn(
        "近3M(%)", format="%.2f",
        help="近 65 個交易日淨值報酬。1M+3M 雙負為衛星動能轉弱訊號"),
    "便宜價(-1σ)": st.column_config.NumberColumn(
        "便宜價(-1σ)", format="%.2f",
        help="近一年高點向下 1 倍標準差，跌破即為分批進場區"),
    "超跌價(-2σ)": st.column_config.NumberColumn(
        "超跌價(-2σ)", format="%.2f",
        help="近一年高點向下 2 倍標準差，跌破即為加大進場區（深綠列）"),
    "停利價(+2σ)": st.column_config.NumberColumn(
        "停利價(+2σ)", format="%.2f",
        help="20 日布林通道上軌，突破代表過熱可考慮減碼"),
    "季線(60MA)": st.column_config.NumberColumn(
        "季線(60MA)", format="%.2f",
        help="60 日移動平均，跌破且下彎代表中期趨勢轉弱"),
    "MK體檢結論": st.column_config.TextColumn(
        "MK體檢結論",
        help="融合 Health_Check + Momentum + Price_Zone 的白話文建議"),
}


def _render_core_tab(df: pd.DataFrame) -> None:
    """Sub-Tab 1：核心戰情室（以息養股）。"""
    with st.expander("💡 策略3 白話文：這頁怎麼看？", expanded=False):
        st.markdown(
            "**核心資產的重點是『穩定領息』。**\n\n"
            "- 請留意「含息總報酬」是否大於「年化配息率」；\n"
            "  若 **總報酬 < 配息率**，代表你領到的股息其實是吃本金（賺息賠本），需要檢視換股。\n"
            "- **夏普值<0**：深紅底列，代表承擔風險卻沒賺到錢，最強汰換訊號。\n"
            "- 橘底列＝跌破季線、趨勢轉弱；綠/深綠底列＝跌至 −1σ / −2σ 加碼區。\n"
            "- 跌破便宜價(-1σ) 是核心加碼的好時機；跌破超跌價(-2σ) 可加大投入。"
        )
    core_df = df[df["MK_Class"] == "Core"].copy()
    if core_df.empty:
        st.info("組合內目前沒有被分類為「核心」的標的。可在 Tab3 上方加入高股息／債券／平衡型基金。")
        return
    core_df = core_df.sort_values(
        by=["Health_Check", "代碼"],
        key=lambda s: s.map({"Sharpe_Warning": 0, "Warning": 1, "Weak": 2,
                             "Healthy": 3, "N/A": 4}) if s.name == "Health_Check" else s,
    )
    st.dataframe(
        _style_core(core_df[_CORE_COLS]),
        column_config=_COL_CONFIG, hide_index=True, use_container_width=True,
    )


def _render_satellite_tab(df: pd.DataFrame,
                          portfolio_funds: Optional[list] = None,
                          bench_series=None,
                          bench_ticker: str = "SPY") -> None:
    """Sub-Tab 2：波段觀測站（衛星資產）。"""
    with st.expander("💡 策略3 白話文：這頁怎麼看？", expanded=False):
        st.markdown(
            "**衛星資產用來衝高獲利。**\n\n"
            "- 跌到 **深綠（-2σ 超跌價）** = 加大進場；**淺綠（-1σ 便宜價）** = 分批進場；\n"
            "- **亮橘色（突破布林上軌）** = 過熱可部分停利，將獲利換回核心領息；\n"
            "- **暗黃色** = 1M+3M 雙負 **或** 連續兩季落後大盤，動能轉弱；\n"
            "- 下方「淨值 vs 基準」圖把衛星與大盤同期歸一化，肉眼看誰跑贏。"
        )
    sat_df = df[df["MK_Class"] == "Satellite"].copy()
    if sat_df.empty:
        st.info("組合內目前沒有被分類為「衛星」的標的。可加入科技／半導體／生技等成長型基金。")
        return
    sat_df = sat_df.sort_values(
        by="Price_Zone",
        key=lambda s: s.map({"Buy_Zone_Deep": 0, "Buy_Zone": 1, "Take_Profit": 2,
                             "Hold": 3, "N/A": 4}),
    )
    st.dataframe(
        _style_satellite(sat_df[_SAT_COLS]),
        column_config=_COL_CONFIG, hide_index=True, use_container_width=True,
    )
    _render_benchmark_chart(sat_df, portfolio_funds or [], bench_series, bench_ticker)


def _render_benchmark_chart(sat_df: pd.DataFrame, portfolio_funds: list,
                             bench_series, bench_ticker: str) -> None:
    """衛星 vs 基準同期歸一化折線（近 ~6 個月）。bench 取不到時優雅退場。"""
    if bench_series is None or not hasattr(bench_series, "dropna"):
        st.caption(f"📡 基準指數（{bench_ticker}）目前無法取得，已暫時隱藏對比圖。")
        return
    codes = set(sat_df["代碼"].tolist())
    sat_funds = [f for f in portfolio_funds if f.get("code") in codes and f.get("series") is not None]
    if not sat_funds:
        return

    try:
        import plotly.graph_objects as go
    except ImportError:
        return

    bench = bench_series.dropna()
    if bench.empty:
        return
    bench_norm = (bench / float(bench.iloc[0])) * 100.0

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=bench_norm.index, y=bench_norm.values,
        mode="lines", name=f"{bench_ticker}（基準）",
        line=dict(color=TRAFFIC_NEUTRAL, width=2, dash="dash"),
    ))
    for f in sat_funds:
        s = f.get("series")
        if s is None or not hasattr(s, "dropna"):
            continue
        s = s.dropna()
        if len(s) < 30:
            continue
        s_recent = s.tail(len(bench_norm) + 5)
        if s_recent.empty:
            continue
        try:
            s_norm = (s_recent / float(s_recent.iloc[0])) * 100.0
        except (TypeError, ValueError, ZeroDivisionError):
            continue
        fig.add_trace(go.Scatter(
            x=s_norm.index, y=s_norm.values,
            mode="lines", name=f.get("name") or f.get("code"),
        ))
    fig.update_layout(
        title=f"衛星淨值 vs {bench_ticker}（起點歸一化＝100）",
        height=320, margin=dict(t=40, b=20, l=20, r=10),
        legend=dict(orientation="h", y=-0.15, font=dict(size=10)),
        paper_bgcolor=GH_BG_PRIMARY, plot_bgcolor=GH_BG_PRIMARY,
        font=dict(color="#ddd"),
        xaxis=dict(gridcolor="#222"), yaxis=dict(gridcolor="#222"),
    )
    st.plotly_chart(fig, use_container_width=True, key="mk_sat_bench")
    st.caption(
        "🟡 連續兩季（兩個 65 交易日視窗）皆落後基準 → 表格自動顯示「連續兩季落後大盤」黃燈。"
    )


def _render_333_tab(df: pd.DataFrame) -> None:
    """Sub-Tab 3：3-3-3 篩選器。

    原規格：成立>3年、年化>7%、同類前 1/3。
    變通：第三項改為「組合內 std_1y < 中位」（既有資料無同類排名 API）。

    v18.158：① 改用 NAV index[0] 推算實際成立年資（取代脆弱的 ret_3y 存在性近似）；
    ② 三層計數改 cascade（① → ①∩② → ①∩②∩③），讓 user 一眼看出卡哪層。
    """
    with st.expander("💡 策略3 白話文：這頁怎麼看？", expanded=False):
        st.markdown(
            "**舊標的變差想換股？依 3-3-3 法則挑：**\n\n"
            "1. **成立 ≥ 3 年**：以 NAV 起始日推算實際年資（v18.158 起改正：原以 ret_3y 存在性近似，低頻 NAV 會誤判）。\n"
            "2. **年化報酬 > 7%**：以近一年含息總報酬替代。\n"
            "3. **同類排名前 1/3**：暫以「組合內波動率優於中位」變通（待 Lipper / Morningstar API 接通後正式啟用）。\n\n"
            "三層採 cascade（過 ① 才看 ②，過 ② 才看 ③），同時符合者列為 **候選清單**。"
        )
    if df.empty:
        st.info("尚無資料可篩選。")
        return

    # W5-6 §1 註明:此 fillna 為「篩選器」非「資料計算」— 缺值對應「新基金/年齡不明」應被過濾掉,
    # fillna(0)→fail age_pass、fillna(-999)→fail ret_pass,語意正確(非掩蓋)
    age_pass = df["_age_years"].fillna(0) >= 3.0
    ret_pass = df["含息總報酬(1Y%)"].fillna(-999) > 7.0
    # std 中位數取「全部有 std」的 pool，不卡 cascade（讓基準穩定）
    std_pool = df["_std_1y"].dropna()
    std_median = float(std_pool.median()) if not std_pool.empty else None
    std_pass = (df["_std_1y"].fillna(99999) < std_median) if std_median is not None \
               else pd.Series([False] * len(df), index=df.index)

    n_age = int(age_pass.sum())
    n_ret_in_age = int((age_pass & ret_pass).sum())
    n_all = int((age_pass & ret_pass & std_pass).sum())

    c1, c2, c3 = st.columns(3)
    c1.metric("① 成立 ≥ 3 年", f"{n_age} 檔")
    c2.metric("② ① + 年化 > 7%", f"{n_ret_in_age} 檔",
              delta=f"−{n_age - n_ret_in_age} 卡關" if n_age > n_ret_in_age else None,
              delta_color="off")
    c3.metric("③ ② + 波動優於中位", f"{n_all} 檔",
              delta=f"−{n_ret_in_age - n_all} 卡關" if n_ret_in_age > n_all else None,
              delta_color="off")

    cand = df[age_pass & ret_pass & std_pass].copy()
    if cand.empty:
        st.warning("目前組合內無同時符合三條件的標的。可考慮加入更多候選後再篩選。")
        return

    st.markdown(f"**🎯 候選清單（{len(cand)} 檔）**")
    st.dataframe(
        cand[_333_COLS], column_config=_COL_CONFIG,
        hide_index=True, use_container_width=True,
    )


# ════════════════════════════════════════════════════════════
# §3 主入口
# ════════════════════════════════════════════════════════════
def render_mk_war_room(portfolio_funds: Optional[list] = None) -> None:
    """掛在 Tab3 頂部的「MK 智能戰情室」面板。"""
    st.markdown("### 🎯 策略3 智能戰情室")
    st.caption(
        "依 策略3 存股法（核心衛星 × 以息養股 × 標準差找買點）"
        "自動為組合貼標籤，新手也能像老手一樣判斷。"
    )

    pf = portfolio_funds or []
    loaded = [f for f in pf if f.get("loaded") and not f.get("load_error")]
    # v18.34 分析視圖按 code 去重（同基金跨多保單只保留一筆），
    # 避免 KPI 重複計、三張表重複列、SPY 比較圖畫重複線。
    # Tab3 portfolio_funds 與 T7 帳本仍以 (code, policy_id) 複合鍵區分。
    _seen_codes: set[str] = set()
    _uniq: list = []
    for _f in loaded:
        _c = str(_f.get("code", "") or "").strip().upper()
        if not _c or _c in _seen_codes:
            continue
        _seen_codes.add(_c)
        _uniq.append(_f)
    loaded = _uniq
    if not loaded:
        st.info("尚未載入任何基金。請在下方加入基金代碼後，戰情室會自動上線。")
        return

    has_sat = any((not f.get("is_core", True)) for f in loaded)
    bench_ticker = st.session_state.get("mk_bench_ticker", "SPY")
    if has_sat:
        cols = st.columns([1, 3])
        with cols[0]:
            bench_ticker = st.selectbox(
                "衛星對比基準", ["SPY", "QQQ"],
                index=0 if bench_ticker == "SPY" else 1,
                key="mk_bench_ticker_select",
                help="SPY=S&P 500、QQQ=Nasdaq 100。連續兩季落後此基準會在表格顯示黃燈。",
            )
        st.session_state["mk_bench_ticker"] = bench_ticker
        bench_series = _get_benchmark_series(bench_ticker)
    else:
        bench_series = None

    df = build_mk_dataframe(loaded, bench_series=bench_series)
    if df.empty:
        st.info("組合資料正在準備中。")
        return

    _render_buckets_diagnostic(df)   # v18.158：三籃子全 0 時自動展開診斷
    st.divider()

    # v18.163：sub-tab 改用 segmented_control（解決 user「三個 tab 內容看起來
    # 一樣」的困惑）— 共用基金資料池，按鈕切換視角，下方一張表依選項換欄位/排序/標題。
    # KPI 卡片已上移到 Tab3 頂部 hero（避免上下兩段重複 KPI）。
    # v19.13.3：改回 st.radio（horizontal）— streamlit 1.45 AppTest 的
    # segmented_control Multiselect.indices 對 proto.Option 用 list.index 找
    # string，必拋 ValueError("content_icon: ... is not in list")。radio 的
    # selectbox path 不走 content_icon proto，AppTest 全版本兼容。
    _view_options = [
        f"🛡️ 核心戰情室（{int((df['MK_Class'] == 'Core').sum())} 檔）",
        f"⚡ 波段觀測站（{int((df['MK_Class'] == 'Satellite').sum())} 檔）",
        f"🔍 3-3-3 篩選器（{len(df)} 檔池）",
    ]
    _view_pick = st.radio(
        "選擇分析視角",
        _view_options,
        index=0,
        key="mk_view_pick",
        horizontal=True,
        help="三個視角共用同一份基金池：核心/衛星按 MK_Class 篩選；3-3-3 篩 3 年資 + 年化報酬 + 標準差。",
    )
    if _view_pick == _view_options[0]:
        _render_core_tab(df)
    elif _view_pick == _view_options[1]:
        _render_satellite_tab(df, portfolio_funds=loaded,
                              bench_series=bench_series, bench_ticker=bench_ticker)
    else:
        _render_333_tab(df)
