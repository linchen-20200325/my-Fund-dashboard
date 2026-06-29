"""services/fund_service.py — 基金業務計算 Service Layer
（v11.0 C-12 從 fund_fetcher.py 抽出純計算函式）

設計原則：
- 純業務計算，不做 HTTP I/O（I/O 走 repositories/fund_repository）
- 不依賴 streamlit
- 風險率 _RF_ANNUAL 為 module-level 全局狀態，由 app.py 在 fetch_all_indicators 後注入

公開 API：
  - 常數：_RF_ANNUAL
  - 配置：set_risk_free_rate
  - 健康診斷：calc_health_from_manual
  - 報酬計算：calculate_fund_total_return / calc_metrics
  - 配息估算：calc_dividend_estimate

v11.0 分層歸位：本檔屬於 Service Layer，純業務計算。
向後相容：fund_fetcher.py shim re-export 維持既有 caller 零修改。
"""
from __future__ import annotations

import pandas as pd
import numpy as np

from shared.colors import MATERIAL_GREEN, MATERIAL_ORANGE, MATERIAL_RED
from shared.signal_thresholds import (  # v19.74 W2 SSOT
    TRADING_DAYS_PER_YEAR,
    NEAR_DIVIDEND_WARNING_PCT,
    HOLDINGS_NAV_SANITY_LOWER_RATIO,
    HOLDINGS_NAV_SANITY_UPPER_RATIO,
)

# v11.0 C-12：utility 暫留 fund_fetcher（待 E 階段重新評估歸屬，可能整合到 infra/）
# 此處 partial-load 安全：fund_fetcher.py 載入到本 service 的 shim re-export 點（L370）時，
# safe_float (L154) / clean_risk_table (L170) 已在 fund_fetcher 內定義
from fund_fetcher import (  # noqa: F401
    safe_float,
    clean_risk_table,
)


# ── _RF_ANNUAL + set_risk_free_rate ──────────────────────────────────
# ── Bug1 Fix: 無風險利率（可由 app.py 透過 set_risk_free_rate() 注入即時 FEDFUNDS）──
_RF_ANNUAL: float = 0.04  # 預設 4%；載入總經資料後會自動更新為 FEDFUNDS 實際值

def set_risk_free_rate(rf_annual: float) -> None:
    """注入即時無風險利率（FEDFUNDS/100）。在 fetch_all_indicators() 完成後由 app.py 呼叫。"""
    global _RF_ANNUAL
    _RF_ANNUAL = max(0.0, float(rf_annual))


# F-RECON-1 phase 3 v19.88 — Sharpe 對帳 helper(self-calc vs MoneyDJ wb07)
def _reconcile_sharpe_pair(self_calc, moneydj) -> dict | None:
    """Sharpe 雙演算法對帳;失敗(import error / 任一缺值)時 graceful 回 None。

    Returns
    -------
    dict | None  reconcile_pair 標準 dict;graceful fallback 為 None。
    """
    try:
        from services.reconcile import reconcile_sharpe
        _sc = float(self_calc) if self_calc is not None else None
        _mj = float(moneydj) if moneydj is not None else None
        return reconcile_sharpe(_sc, _mj)
    except Exception:  # noqa: BLE001 — pure additive flag,失敗不應影響主流程
        return None


# ── calc_health_from_manual ──────────────────────────────────────────
def calc_health_from_manual(
    nav_current: float,
    nav_1y_ago: float,
    div_per_unit: float,
    div_freq: int = 12,
    fund_name: str = "",
) -> dict:
    """
    v13.7 手動輸入降級計算模式。
    當無法自動抓取時，只需 4 個數字就能完成健康診斷：
      nav_current  : 目前淨值
      nav_1y_ago   : 一年前淨值（或去年同期）
      div_per_unit : 最近一期每單位配息金額
      div_freq     : 配息頻率（月配=12, 季配=4, 半年=2, 年配=1）

    計算：
      配息年化率 = 單次配息 × 年配次數 / 目前淨值 × 100%
      含息報酬率 = (目前淨值 - 一年前淨值 + 單次配息 × 年配次數) / 一年前淨值 × 100%
      真實收益   = 含息報酬率 - 配息年化率
      吃本金     = 含息報酬率 < 配息年化率
    """
    if nav_current <= 0 or nav_1y_ago <= 0:
        return {"error": "淨值不可為 0 或負數"}

    annual_div      = div_per_unit * div_freq
    div_yield_pct   = round(annual_div / nav_current * 100, 2)
    nav_change_pct  = round((nav_current - nav_1y_ago) / nav_1y_ago * 100, 2)
    total_return_pct = round(nav_change_pct + div_yield_pct, 2)

    # v19.119:核心判定委派 services.health.dividend
    # (4 級分類門檻 real_return_pct ≥ 3 / ≥ 0 / < 0 保留於本 wrapper UI 需求)
    from services.health.dividend import classify_eating_principal
    _core = classify_eating_principal(total_return_pct, div_yield_pct)
    real_return_pct  = round(total_return_pct - div_yield_pct, 2)
    eating_principal = _core.is_eating

    # 健康評級(本 wrapper 4 級門檻,保留)
    if eating_principal:
        health = "🔴 吃本金"
        health_color = MATERIAL_RED
        advice = f"含息報酬({total_return_pct:.2f}%) < 配息率({div_yield_pct:.2f}%)，配息部分來自本金，長期持有本金縮水"
    elif real_return_pct >= 3:
        health = "🟢 健康成長"
        health_color = MATERIAL_GREEN
        advice = f"真實收益 +{real_return_pct:.2f}%，淨值成長有餘力支撐配息"
    elif real_return_pct >= 0:
        health = "🟡 邊緣健康"
        health_color = MATERIAL_ORANGE
        advice = f"真實收益 +{real_return_pct:.2f}%，勉強打平，建議持續觀察"
    else:
        health = "🟠 淨值下滑"
        health_color = "#ff7043"
        advice = f"淨值下滑 {real_return_pct:.2f}%，配息雖充足但需注意本金侵蝕趨勢"

    return {
        "fund_name":        fund_name,
        "nav_current":      nav_current,
        "nav_1y_ago":       nav_1y_ago,
        "nav_change_pct":   nav_change_pct,
        "div_per_unit":     div_per_unit,
        "div_freq":         div_freq,
        "annual_div":       round(annual_div, 4),
        "div_yield_pct":    div_yield_pct,
        "total_return_pct": total_return_pct,
        "real_return_pct":  real_return_pct,
        "eating_principal": eating_principal,
        "health":           health,
        "health_color":     health_color,
        "advice":           advice,
        "calc_mode":        "manual",
    }



# ── calculate_fund_total_return + calc_metrics ───────────────────────
def calculate_fund_total_return(nav_df: pd.DataFrame, div_df: pd.DataFrame) -> pd.DataFrame:
    """還原淨值法（配息再投資複利）計算共同基金含息累積報酬率。

    公式：
      Factor_t      = 1 + Dividend_t / NAV_t   （除息日才 > 1，其餘日 = 1）
      Cum_Factor_T  = Π Factor_t
      Adj_NAV_T     = NAV_T × Cum_Factor_T
      Cum_Return%   = (Adj_NAV_T / Adj_NAV_0 − 1) × 100

    輸入：
      nav_df: DataFrame 含 Date(datetime/str), NAV(float)
      div_df: DataFrame 含 Date, Dividend；若空表或 None 視為純累積型

    輸出：
      DataFrame 含 Date, NAV, Dividend, Factor, Cum_Factor, Adj_NAV, Cum_Return_Pct
      （nav_df 空 → 回 empty DataFrame）
    """
    if nav_df is None or nav_df.empty:
        return pd.DataFrame()

    nav = nav_df.copy()
    nav["Date"] = pd.to_datetime(nav["Date"])
    nav = nav.sort_values("Date").reset_index(drop=True)

    if div_df is None or div_df.empty:
        div = pd.DataFrame({"Date": pd.Series([], dtype="datetime64[ns]"),
                            "Dividend": pd.Series([], dtype="float64")})
    else:
        div = div_df.copy()
        div["Date"] = pd.to_datetime(div["Date"])
        div = div.sort_values("Date")

    df = pd.merge(nav, div, on="Date", how="left")
    # W5-1 §1 註明:left-join 後 NaN 表示「該日無配息事件」,fillna(0) 為語意正確(非掩蓋)
    df["Dividend"] = df["Dividend"].fillna(0)

    # 除以零防護：NAV<=0 或 NaN → Factor=1（該日不貢獻再投資）
    # W5-1 §1 註明:此 fillna(0) 對應 _safe_nav 為 NaN 的退化情境,Factor=1 為業務正確(顯式說明)
    _safe_nav = df["NAV"].where(df["NAV"] > 0, np.nan)
    div_ratio = (df["Dividend"] / _safe_nav).fillna(0)
    df["Factor"] = 1.0 + div_ratio
    df["Cum_Factor"] = df["Factor"].cumprod()
    df["Adj_NAV"] = df["NAV"] * df["Cum_Factor"]

    first_val = float(df["Adj_NAV"].iloc[0]) if not df.empty else 0.0
    if first_val > 0:
        df["Cum_Return_Pct"] = (df["Adj_NAV"] / first_val - 1.0) * 100.0
    else:
        df["Cum_Return_Pct"] = 0.0
    return df


def calc_metrics(s: pd.Series, divs: list, risk_override: dict = None) -> dict:
    """
    計算 MK 買點指標。
    risk_override: fetch_risk_metrics() 回傳的 dict，
                   若存在則優先使用 wb07 的年化標準差（更精準）。

    v19.164 A1 Phase C:服務入口加 pandera data-only 驗證(NAV/dividends
    業務契約),不驗 provenance(service caller 可能來自 cache/test fixture)。

    **v19.176 SSOT WRITER 公告**
    -----------------------------
    本函式為以下指標的**單一寫入點**(SSOT),所有 UI reader 一律從返回 dict 讀取,
    不可重新呼叫第二份計算 / 自算覆蓋,免「同檔不同數字」散落:

    - `sharpe`               年化 Sharpe Ratio(優先 wb07,本算 fallback)
    - `sortino`              年化 Sortino Ratio(下檔波動,需 ≥60 筆 + ≥5 筆負報酬)v19.191 +
    - `calmar`               Calmar = 3Y 年化 / |max_dd|(3Y 缺則 1Y fallback)v19.191 +
    - `std_1y` / std_2y / std_3y / std_5y  年化標準差(同優先序)
    - `max_drawdown`         最大回撤 %
    - `ret_1y` / ret_3y / ret_5y  純 NAV 報酬(不含息;1Y 含息走 fund_total_return)
    - `annual_div_rate`      年化配息率(本算 fallback;主源 moneydj_div_yield wb05)
    - `div_freq_n`           配息頻率(12/4/2/1 次/年,由 div 間隔 auto-detect)
    - `buy1` / buy2 / buy3 / sell1 / sell2 / sell3  MK 1-2-3 加碼點

    Reader 看到上述欄位 = 確定同源,無需 verify。
    """
    if s.empty or len(s) < 5: return {}
    # A1 Phase C v19.164:服務入口驗 NAV/dividends 業務契約
    # (data-only,不驗 provenance attrs)
    try:
        from shared.schemas import (
            validate_fund_nav_data_only,
            validate_fund_dividends_data_only,
        )
        validate_fund_nav_data_only(s)
        validate_fund_dividends_data_only(divs)
    except Exception as _ve:
        # Fail Loud:壞 NAV/dividends 進入服務層 = 上游 bug,當場 raise
        print(f"[calc_metrics] schema 違反: {_ve}")
        raise
    now = float(s.iloc[-1])
    log_ret = np.log(s / s.shift(1)).dropna()

    # ── 年化標準差（各期間）─────────────────────────────
    # MK 方法：最少 20 筆資料即可計算（降低門檻以支援短期資料）
    std_dict = {}
    for yrs, lb in [(1,"1年"),(2,"2年"),(3,"3年"),(5,"5年")]:
        n = yrs * TRADING_DAYS_PER_YEAR
        base = log_ret.tail(n) if len(log_ret) >= n else log_ret
        if len(base) >= 20:  # ← 降低門檻 60→20
            std_dict[lb] = round(base.std() * np.sqrt(TRADING_DAYS_PER_YEAR) * 100, 2)
    # 優先用 wb07 績效評比的標準差（最準確）
    # 其次: 2年計算值 > 1年計算值 > 全期計算值
    risk_tbl = (risk_override or {}).get("risk_table", {})
    # ── v13 排錯：先用 safe_float 清洗，再做 N/A 判斷 ──────────────────
    risk_tbl = clean_risk_table(risk_tbl)      # 全表清洗，確保 N/A → None
    std_wb07_1y = safe_float(risk_tbl.get("一年", {}).get("標準差"))

    if std_wb07_1y is not None:
        # 將各期 wb07 標準差填入 std_dict（只填轉換成功的數值）
        _wb07_vals = set()
        for period_key, period_name in [("六個月","6M"),("一年","1Y"),("三年","3Y"),("五年","5Y")]:
            raw_v = risk_tbl.get(period_key, {}).get("標準差")
            v = safe_float(raw_v)          # N/A / -- → None，不爆掉
            if v is not None:
                _wb07_vals.add(v)
                std_dict[period_name] = v
        # 若 wb07 所有期間 std 完全相同（資料品質差），補用 nav 計算值
        if len(_wb07_vals) <= 1:
            for yrs, lb in [(1,"1Y"),(2,"2Y"),(3,"3Y"),(5,"5Y")]:
                n = yrs * TRADING_DAYS_PER_YEAR
                base = log_ret.tail(n) if len(log_ret) >= n else log_ret
                if len(base) >= 20:
                    _nav_std = round(base.std() * np.sqrt(TRADING_DAYS_PER_YEAR) * 100, 2)
                    std_dict[lb] = _nav_std  # 覆蓋為各期真實計算值
        std_2y = std_dict.get("3Y", std_dict.get("2Y", std_wb07_1y))
        std_1y = std_dict.get("1Y", std_wb07_1y)
        print(f"[calc_metrics] 使用 wb07 標準差: 1Y={std_1y}% 3Y={std_2y}%")
    else:
        std_2y = std_dict.get("2年", std_dict.get("1年",
                 round(log_ret.std() * np.sqrt(TRADING_DAYS_PER_YEAR) * 100, 2) if len(log_ret)>=20 else 0))
        std_1y = std_dict.get("1年", std_2y)

    # ── 高低點（MK 買點基準用2年）──────────────────────
    def _hl(n):
        sub = s.tail(n) if len(s) >= n else s
        return (round(float(sub.max()),4), str(sub.idxmax())[:10],
                round(float(sub.min()),4), str(sub.idxmin())[:10])
    h1y,hd1,l1y,ld1 = _hl(TRADING_DAYS_PER_YEAR)
    h2y,hd2,l2y,ld2 = _hl(2 * TRADING_DAYS_PER_YEAR)   # ← 2年高低點
    h3y,hd3,l3y,ld3 = _hl(3 * TRADING_DAYS_PER_YEAR)
    hall = round(float(s.max()),4); hall_d = str(s.idxmax())[:10]
    lall = round(float(s.min()),4); lall_d = str(s.idxmin())[:10]

    # ── MK 標準差加碼買點（以年度最高/最低點為基準）──────
    # 優先使用 fetch_basic 抓到的 年最高/最低淨值
    # σ_amount = (year_high - year_low) / 3
    # Buy3 ≈ year_low，買點三對應歷史最低點
    _yh = risk_override.get("year_high_nav") if risk_override else None
    _yl = risk_override.get("year_low_nav")  if risk_override else None
    # v18.77 sanity check：wb01 parser 偶爾欄位錯位（境外月配型常見），
    #         例：JFZN3 NAV=75.33 但抓到 yh=5.84 / yl=5.54（疑似報酬率/配息率欄位）
    #         若 _yh/_yl 偏離當前 NAV 超過 0.3x ~ 3x 範圍，視為解析錯誤 → 走 NAV 序列
    _hl_ok = (_yh and _yl and _yh > _yl and _yh > 0)
    if _hl_ok and now > 0:
        if (_yh < now * HOLDINGS_NAV_SANITY_LOWER_RATIO or _yh > now * HOLDINGS_NAV_SANITY_UPPER_RATIO
                or _yl < now * HOLDINGS_NAV_SANITY_LOWER_RATIO or _yl > now * HOLDINGS_NAV_SANITY_UPPER_RATIO):
            print(f"[calc_metrics] ⚠️ year_high/low 不合理（yh={_yh} yl={_yl} now={now}），"
                  f"走 NAV 序列 2Y 高低點 fallback")
            _hl_ok = False
    use_annual_hl = _hl_ok

    if use_annual_hl:
        # 年度高低點模式（最直觀）
        ref_high  = float(_yh)
        ref_low   = float(_yl)
        buy_mode  = "年高低點σ"
        print(f"[calc_metrics] 買點模式=年高低點σ 年高={ref_high} 年低={ref_low}")
    else:
        # fallback: 2年高低點 + wb07/NAV σ
        ref_high  = h2y
        ref_low   = l2y
        buy_mode  = "2年高低點σ"
        print(f"[calc_metrics] 買點模式=2年高低點σ 高={ref_high} 低={ref_low}")

    # ── MK v3.0 公式：買=年高-kσ｜賣=年低+kσ（對稱）──────────
    # σ_abs = 年高 × 年化標準差%
    # 買點：小跌(20%)=年高-1σ｜急跌(30%)=年高-2σ｜大跌(50%)=年高-3σ
    # 賣點：小漲(20%)=年低+1σ｜急漲(30%)=年低+2σ｜大漲(50%)=年低+3σ
    std_amt = round(ref_high * std_1y / 100, 4) if std_1y else round((ref_high - ref_low) / 4, 4)
    std_amt = max(std_amt, 0.0001)   # 防呆：σ 不可為 0

    b1    = round(ref_high - std_amt,     4)   # 年高 - 1σ（小跌小買 20%）
    b2    = round(ref_high - 2 * std_amt, 4)   # 年高 - 2σ（急跌穩買 30%）
    b3    = round(ref_high - 3 * std_amt, 4)   # 年高 - 3σ（大跌大買 50%）
    sell1 = round(ref_low  + std_amt,     4)   # 年低 + 1σ（小漲停利 20%）
    sell2 = round(ref_low  + 2 * std_amt, 4)   # 年低 + 2σ（急漲停利 30%）
    sell3 = round(ref_low  + 3 * std_amt, 4)   # 年低 + 3σ（大漲停利 50%）

    print(f"[calc_metrics] σ={std_amt} b1={b1} b2={b2} b3={b3} sell1={sell1} sell2={sell2} sell3={sell3}")

    buy_basis  = ref_high   # MK v3.0: 買點錨定年最高
    sell_basis = ref_low    # MK v3.0: 賣點錨定年最低

    # 距離 % （正=尚未觸發 / 0 或負=已觸發；接近閾值=2%）
    NEAR_PCT = NEAR_DIVIDEND_WARNING_PCT  # v19.74 W2 SSOT
    def _dist(target):
        if (not target) or now <= 0: return None
        return round((now - target) / target * 100, 2)
    buy_distance_pct  = {"b1": _dist(b1), "b2": _dist(b2), "b3": _dist(b3)}
    sell_distance_pct = {"s1": _dist(sell1), "s2": _dist(sell2), "s3": _dist(sell3)}

    # 倉位判斷（深度優先；買勝過賣以利風險控管）
    if std_amt < ref_high * 0.001:   # σ < 0.1% → 資料不可靠
        pos_l, pos_c = "資料待更新 📡", "#555"
    elif now <= b3:    pos_l, pos_c = "大跌大買 🔥 (投 50%)", "#9c27b0"
    elif now <= b2:    pos_l, pos_c = "急跌穩買 📈 (投 30%)", MATERIAL_GREEN
    elif now <= b1:    pos_l, pos_c = "小跌小買 ✅ (投 20%)", "#69f0ae"
    elif now >= sell3: pos_l, pos_c = "大漲停利 🔔 (出 50%)", MATERIAL_RED
    elif now >= sell2: pos_l, pos_c = "急漲停利 ⚠️ (出 30%)", "#ff7043"
    elif now >= sell1: pos_l, pos_c = "小漲停利 💰 (出 20%)", "#ffa726"
    else:              pos_l, pos_c = "正常波動區",            "#888888"

    # ── 布林通道（20日 Rolling Band，作為時間序列輸出）──
    bb_period = min(20, len(s))
    bb_ma  = s.rolling(bb_period).mean()
    bb_std = s.rolling(bb_period).std()
    bb_upper_s = (bb_ma + 2 * bb_std).round(4)
    bb_lower_s = (bb_ma - 2 * bb_std).round(4)
    # 最新值（用於訊號判斷）
    bb_u = float(bb_upper_s.iloc[-1]) if not bb_upper_s.isna().all() else None
    bb_d = float(bb_lower_s.iloc[-1]) if not bb_lower_s.isna().all() else None
    bb_m_val = float(bb_ma.iloc[-1]) if not bb_ma.isna().all() else None
    if bb_u and bb_d and (bb_u - bb_d) > 0.0001:
        if   now >= bb_u: bb_sig, bb_c = "碰天花板 停利 📤", MATERIAL_RED
        elif now <= bb_d: bb_sig, bb_c = "碰地板 買進 📥",   MATERIAL_GREEN
        else:
            p = round((now - bb_d) / (bb_u - bb_d) * 100, 1)
            bb_sig, bb_c = f"通道 {p:.0f}% 位置", MATERIAL_ORANGE
    else:
        bb_sig, bb_c = "通道過窄（波動低）", "#888"
    # 輸出時間序列供圖表用
    bb_upper_series = bb_upper_s.dropna()
    bb_lower_series = bb_lower_s.dropna()
    rf=_RF_ANNUAL/TRADING_DAYS_PER_YEAR; r252=log_ret.tail(TRADING_DAYS_PER_YEAR) if len(log_ret)>=TRADING_DAYS_PER_YEAR else log_ret  # Bug1: rf 改用即時 FEDFUNDS
    sharpe=round(float((r252.mean()-rf)/r252.std()*np.sqrt(TRADING_DAYS_PER_YEAR)),2) if len(r252)>=60 else None
    # v19.191 SSOT WRITER:Sortino(下檔波動年化)— 同 sharpe 60 筆門檻
    # target=0,只取負報酬計 downside_std,避免 ÷0 用 1e-12 guard。
    sortino = None
    if len(r252) >= 60:
        _neg = r252[r252 < 0]
        if len(_neg) >= 5:
            _dstd = float(_neg.std())
            if _dstd > 1e-12:
                sortino = round(float((r252.mean() - rf) / _dstd * np.sqrt(TRADING_DAYS_PER_YEAR)), 2)
    cum=(1+log_ret).cumprod()
    max_dd=round(float(((cum-cum.cummax())/cum.cummax()).min())*100,2)
    def _ret(n): return round((now-float(s.iloc[-n]))/float(s.iloc[-n])*100,2) if len(s)>=n else None

    # v19.177 #2A:NY 報酬雙欄 SSOT — 累計 (cum) + 年化 (ann),
    # 解決「健診表把 metrics.ret_3y 當累計開根,但 fund_service 寫的可能已年化」implicit
    # contract 陷阱。caller 一律讀 ret_NY_ann 用,讀 ret_NY_cum 顯示原始累計。
    # ret_NY(無後綴)保留 = ret_NY_cum 為向後相容,新 caller 不應使用。
    def _annualize_cum_pct(cum_pct, years):
        """純 NAV 累計 % → 年化 %,(1+r)^(1/N)-1 標準公式。失敗回 None(§1 Fail Loud)。"""
        if cum_pct is None or years <= 0:
            return None
        try:
            return round(((1.0 + float(cum_pct) / 100.0) ** (1.0 / years) - 1.0) * 100.0, 2)
        except (ValueError, ZeroDivisionError, OverflowError):
            return None
    _ret_3y_cum = _ret(3 * TRADING_DAYS_PER_YEAR)
    _ret_5y_cum = _ret(5 * TRADING_DAYS_PER_YEAR)
    _ret_3y_ann = _annualize_cum_pct(_ret_3y_cum, 3)
    _ret_5y_ann = _annualize_cum_pct(_ret_5y_cum, 5)
    # v19.191 SSOT WRITER:Calmar = 年化報酬 / |max_drawdown|
    # 優先 3Y 年化(較穩定),fallback 1Y 純 NAV 報酬。max_dd=0 → None(避免 ÷0)。
    calmar = None
    _ann_for_calmar = _ret_3y_ann if _ret_3y_ann is not None else _ret(TRADING_DAYS_PER_YEAR)
    if _ann_for_calmar is not None and max_dd is not None and abs(max_dd) > 1e-9:
        calmar = round(float(_ann_for_calmar) / abs(float(max_dd)), 2)
    # v18.53/v18.55/v18.60/v18.61/v18.65/v18.71: 境內基金 MoneyDJ wb01 不存在 → 本地計算含息
    # v18.71: 改用「還原淨值法（配息再投資複利）」— 透過 calculate_fund_total_return()
    #         比舊版「NAV 變化 + 累積配息率」（單利加總）更接近 MoneyDJ wb01 含息官方值，
    #         在月配高息境外型（如 JFZN3）可縮小 ±5pp 誤差。
    # 短窗口（< 252 天）仍不年化，回累積實值 + window_days 欄位，UI 標「N 天累積」。
    _ret_1y_total = None
    _ret_1y_window_days = None
    if len(s) >= 20 and now > 0:
        # 防禦性算 days_span — pd.to_datetime 強制轉換，失敗則 len(s)×1.4 估算
        _days_span = 0
        try:
            _ts_first = pd.to_datetime(s.index[0])
            _ts_last = pd.to_datetime(s.index[-1])
            _days_span = max(int((_ts_last - _ts_first).days), 0)
        except Exception as _e_span:
            # F-MED v19.170: silent → stderr log;index 解析失敗 fallback estimator
            import sys as _sys_sp
            print(f'[fund_service/calc_metrics] days_span calc fail: {type(_e_span).__name__}: {_e_span}', file=_sys_sp.stderr)
            _days_span = 0
        if _days_span < 7:
            _days_span = max(int(len(s) * 1.4), 14)

        if len(s) >= TRADING_DAYS_PER_YEAR:
            _window_start_idx = -TRADING_DAYS_PER_YEAR
            try:
                _window_start_dt = pd.to_datetime(s.index[-TRADING_DAYS_PER_YEAR])
                _window_actual_days = (pd.to_datetime(s.index[-1]) - _window_start_dt).days
            except Exception as _e_win:
                # F-MED v19.170: silent → stderr log;fallback to 365d
                import sys as _sys_w
                print(f'[fund_service/calc_metrics] 1Y window calc fail: {type(_e_win).__name__}: {_e_win}', file=_sys_w.stderr)
                _window_start_dt = None
                _window_actual_days = 365
            _ret_1y_window_days = _window_actual_days or 365
        elif _days_span >= 30:
            _window_start_idx = 0
            try:
                _window_start_dt = pd.to_datetime(s.index[0])
            except Exception:
                _window_start_dt = None
            _ret_1y_window_days = _days_span
        else:
            _window_start_idx = None
            _window_start_dt = None

        if _window_start_idx is not None and _ret_1y_window_days:
            try:
                _nav_df = pd.DataFrame({
                    "Date": pd.to_datetime(s.index),
                    "NAV": s.values.astype(float),
                })
                _div_rows = []
                if divs:
                    for _d in divs:
                        try:
                            _amt = float(_d.get("amount", 0) or 0)
                            if _amt <= 0:
                                continue
                            _date_raw = str(_d.get("date", "") or "").replace("/", "-")
                            _dt = pd.to_datetime(_date_raw)
                            _div_rows.append({"Date": _dt, "Dividend": _amt})
                        except Exception:
                            continue
                _div_df = pd.DataFrame(_div_rows) if _div_rows else pd.DataFrame()
                _tr = calculate_fund_total_return(_nav_df, _div_df)
                # 取窗口起點 Adj_NAV — 用日期對齊（s.index[-252] 或 s.index[0]）
                _start_dt_norm = pd.to_datetime(s.index[_window_start_idx])
                _mask = _tr["Date"] >= _start_dt_norm
                if _mask.any():
                    _adj_start = float(_tr.loc[_mask, "Adj_NAV"].iloc[0])
                    _adj_end = float(_tr["Adj_NAV"].iloc[-1])
                    if _adj_start > 0:
                        _ret_1y_total = round((_adj_end / _adj_start - 1.0) * 100, 2)
                        print(f"[calc_metrics] 🧮 ret_1y_total={_ret_1y_total}% "
                              f"(len={len(s)}, window_days={_ret_1y_window_days}, "
                              f"還原淨值法 adj_start={_adj_start:.4f} adj_end={_adj_end:.4f})")
            except Exception as _e_tr:
                print(f"[calc_metrics] ⚠️ ret_1y_total 計算失敗：{_e_tr}")
                _ret_1y_total = None

    annual_div=monthly_div=div_rate=0; div_stability=None; div_trend=0; div_freq_n=12
    if divs:
        # ── 自動偵測配息頻率（月配/季配/半年/年配）────────
        if len(divs) >= 2:
            import statistics as _st
            _dates = []
            for _d in divs[:13]:
                try: _dates.append(pd.to_datetime(_d["date"]))
                except Exception: pass  # v19.74 W1-A (§1 Fail Loud): bare except → narrow
            _dates = sorted(_dates, reverse=True)
            if len(_dates) >= 2:
                _gaps = [(_dates[i]-_dates[i+1]).days for i in range(min(len(_dates)-1,6))]
                avg_gap = _st.mean(_gaps) if _gaps else 90
                if avg_gap <= 45:   div_freq_n = 12   # 月配
                elif avg_gap <= 100: div_freq_n = 4   # 季配
                elif avg_gap <= 200: div_freq_n = 2   # 半年配
                else:                div_freq_n = 1   # 年配
        # ── 計算配息年化率（配息年化率 ≠ 含息報酬率！）──────
        # 配息年化率 = 平均單次配息 × 年配次數 / 淨值
        # 含息報酬率 = (淨值漲跌 + 累積配息) / 期初淨值 → 需從 MoneyDJ 取得
        recent=[d["amount"] for d in divs[:div_freq_n]]
        avg_single_div = sum(recent)/len(recent) if recent else 0
        annual_div = avg_single_div * div_freq_n
        monthly_div = annual_div / 12
        div_rate = round(annual_div/now*100, 2) if now>0 else 0
        if len(recent)>=2:
            import statistics
            mn=statistics.mean(recent)
            cv=round(statistics.stdev(recent)/mn*100,1) if mn>0 else 0
            div_stability={"cv":cv,
                "label":"穩定" if cv<10 else("尚可" if cv<25 else "不穩定"),
                "color":MATERIAL_GREEN if cv<10 else(MATERIAL_ORANGE if cv<25 else MATERIAL_RED)}
        recent12=[d["amount"] for d in divs[:12]]
        if len(recent12)>=6:
            div_trend=round((sum(recent12[:3])/3-sum(recent12[3:6])/3)/(sum(recent12[3:6])/3)*100,1) if sum(recent12[3:6])>0 else 0
    return dict(
        nav=now, std_multi=std_dict, std_1y=std_1y, std_2y=std_2y,
        std_multi_cn={
            "1年": std_dict.get("1Y", std_1y),
            "2年": std_dict.get("2Y", std_dict.get("3Y", std_2y)),
            "3年": std_dict.get("3Y", std_2y),
            "5年": std_dict.get("5Y"),
        }, std_amount=std_amt,
        high_1y=h1y,high_date_1y=hd1,low_1y=l1y,low_date_1y=ld1,
        high_2y=h2y,high_date_2y=hd2,low_2y=l2y,low_date_2y=ld2,
        high_3y=h3y,high_date_3y=hd3,low_3y=l3y,low_date_3y=ld3,
        all_high=hall,all_high_date=hall_d,all_low=lall,all_low_date=lall_d,
        buy1=b1,buy2=b2,buy3=b3,sell1=sell1,sell2=sell2,sell3=sell3,
        buy_basis=buy_basis,sell_basis=sell_basis,buy_mode=buy_mode,
        buy_distance_pct=buy_distance_pct,
        sell_distance_pct=sell_distance_pct,
        near_threshold_pct=NEAR_PCT,
        year_high_nav=float(_yh) if use_annual_hl else None,
        year_low_nav=float(_yl) if use_annual_hl else None,
        pos_label=pos_l,pos_color=pos_c,
        bb_upper=bb_u,bb_mid=round(bb_m_val,4) if bb_m_val else None,
        bb_lower=bb_d,bb_signal=bb_sig,bb_color=bb_c,
        bb_upper_series=bb_upper_series,bb_lower_series=bb_lower_series,
        std_source="wb07" if (risk_override and risk_override.get("risk_table")) else "nav",
        risk_table=risk_tbl,
        # 夏普優先用 wb07（更精確），自算值需要60+筆
        # v19.177 #5A:加 sharpe_source provenance 標記,ai_service / UI hover 顯示來源
        sharpe=(
            safe_float(risk_tbl.get("一年",{}).get("Sharpe")) or
            safe_float(risk_tbl.get("六個月",{}).get("Sharpe")) or
            sharpe
        ),
        sharpe_source=(
            "wb07_1y" if safe_float(risk_tbl.get("一年", {}).get("Sharpe")) is not None
            else "wb07_6m" if safe_float(risk_tbl.get("六個月", {}).get("Sharpe")) is not None
            else "self_calc" if sharpe is not None
            else None
        ),
        max_drawdown_source="self_calc",  # max_dd 永遠自算(cum-cummax 算式,fund_service.py:381)
        # F-RECON-1 phase 3 v19.88 — Sharpe 雙演算法對帳(self-calc vs MoneyDJ wb07)
        sharpe_reconcile=_reconcile_sharpe_pair(
            self_calc=sharpe,
            moneydj=safe_float(risk_tbl.get("一年", {}).get("Sharpe")),
        ),
        # v19.191 SSOT WRITER:6F factor 進階指標(配 portfolio_service.calc_fund_factor_score)
        sortino=sortino,
        calmar=calmar,
        max_drawdown=max_dd,
        ma20=round(float(s.tail(20).mean()),4) if len(s)>=20 else None,
        ma60=round(float(s.tail(60).mean()),4) if len(s)>=60 else None,
        ret_1w=_ret(6),ret_1m=_ret(22),ret_3m=_ret(65),
        ret_6m=_ret(130),ret_1y=_ret(TRADING_DAYS_PER_YEAR),
        # v19.177 #2A:NY 雙欄 SSOT。ret_3y / ret_5y 保留 = _cum 向後相容(deprecated)
        ret_3y=_ret_3y_cum, ret_3y_cum=_ret_3y_cum, ret_3y_ann=_ret_3y_ann,
        ret_5y_cum=_ret_5y_cum, ret_5y_ann=_ret_5y_ann,
        ret_1y_total=_ret_1y_total,   # v18.53 含息：NAV 變化 + 累積配息率
        ret_1y_window_days=_ret_1y_window_days,  # v18.65: 計算窗口天數（None / 30~365 / >=365）
        annual_div=round(annual_div,4),monthly_div=round(monthly_div,4),
        annual_div_rate=div_rate,div_stability=div_stability,div_trend=div_trend,
    )


# ── v19.240 R8 EX-L1ORCH-1 升級:L1 orchestrator 業務邏輯上提 ──────
def finalize_fund_metrics(result: dict) -> dict:
    """v19.240 R8 EX-L1ORCH-1 退役:把原 L1 fund_orchestration._finish_metrics +
    fx_and_main.fetch_fund_by_key 收尾 + fund_orchestration.fetch_fund_from_moneydj_url
    收尾 3 處的 metric + perf 注入 + F-RECON-1 對帳 4 個 L2 業務邏輯收編進 L2,
    L1 純化為 raw fetch + packaging。

    接收 raw `result`(含 series / dividends / risk_metrics / perf / year_high_nav /
    year_low_nav / moneydj_div_yield / fund_code / data_source / source_trace),enrich:
    - result["metrics"] = calc_metrics(s, divs, risk_override=combined_override)
    - source_trace append calc_metrics 成功 / 失敗
    - perf["1Y"] 從本地計算注入(v18.65 window >= 350 才視為真 1Y)
    - F-RECON-1 phase 4 ret_1y_reconcile
    - F-RECON-1 phase 5 div_yield_reconcile

    Mutates + returns result(同一物件,方便 chain)。
    """
    from services.reconcile import reconcile_dividend_yield, reconcile_fund_annual_return

    s = result.get("series")
    divs = result.get("dividends", [])
    code = result.get("fund_code", "?")
    src = result.get("data_source", "")

    if "source_trace" not in result:
        result["source_trace"] = []

    if s is None:
        result["source_trace"].append(
            {"source": "nav_series", "success": False, "error": "無淨值序列"})
        return result

    if len(s) < 10:
        result["source_trace"].append(
            {"source": "nav_series", "success": False,
             "error": f"只有 {len(s)} 筆(需≥10)"})
        return result

    try:
        combined_override = dict(result.get("risk_metrics") or {})
        if result.get("year_high_nav"):
            combined_override["year_high_nav"] = result["year_high_nav"]
        if result.get("year_low_nav"):
            combined_override["year_low_nav"] = result["year_low_nav"]
        result["metrics"] = calc_metrics(s, divs, risk_override=combined_override)
        result["source_trace"].append({"source": "calc_metrics", "success": True})

        # v18.53 + v18.65: 境內缺 wb01 perf["1Y"] 改用本地計算,window >= 350 才視為真 1Y
        if not isinstance(result.get("perf"), dict):
            result["perf"] = {}
        if result["perf"].get("1Y") is None:
            _m_local = result.get("metrics") or {}
            _local_1y = _m_local.get("ret_1y_total")
            _local_window = _m_local.get("ret_1y_window_days") or 0
            if _local_1y is not None and _local_window >= 350:
                result["perf"]["1Y"] = _local_1y
                result["perf_source"] = result.get("perf_source") or "local_calc"
                print(f"[metrics] 🧮 {code} perf['1Y'] 用本地計算補:{_local_1y}%")

        # F-RECON-1 phase 4 v19.89 — 1Y 報酬雙演算法對帳(self-calc vs MoneyDJ wb01)
        try:
            _m_local = result.get("metrics") or {}
            _self_calc_1y = _m_local.get("ret_1y_total")
            _wb01_1y = result.get("perf", {}).get("1Y")
            _perf_source = result.get("perf_source") or ""
            _is_wb01 = (_wb01_1y is not None and _perf_source != "local_calc")
            if _self_calc_1y is not None or _is_wb01:
                _sc = float(_self_calc_1y) / 100.0 if _self_calc_1y is not None else None
                _mj = float(_wb01_1y) / 100.0 if _is_wb01 else None
                if isinstance(result.get("metrics"), dict):
                    result["metrics"]["ret_1y_reconcile"] = (
                        reconcile_fund_annual_return(_sc, _mj))
        except Exception:  # noqa: BLE001
            pass

        # F-RECON-1 phase 5 v19.90 — 配息殖利率對帳
        try:
            _m_local = result.get("metrics") or {}
            _self_calc_dy = _m_local.get("annual_div_rate")
            _mj_dy = result.get("moneydj_div_yield")
            if _self_calc_dy is not None or _mj_dy is not None:
                _sc_dy = float(_self_calc_dy) / 100.0 if _self_calc_dy is not None else None
                _mj_dy_dec = float(_mj_dy) / 100.0 if _mj_dy is not None else None
                if isinstance(result.get("metrics"), dict):
                    result["metrics"]["div_yield_reconcile"] = (
                        reconcile_dividend_yield(_sc_dy, _mj_dy_dec))
        except Exception:  # noqa: BLE001
            pass

        print(f"[metrics] ✅ {code} 指標計算完成({len(s)} 筆,src:{src})")
    except Exception as _ce:
        result["source_trace"].append(
            {"source": "calc_metrics", "success": False, "error": str(_ce)[:60]})
        result["error"] = f"指標計算異常:{str(_ce)[:80]}"
        print(f"[metrics] ❌ calc_metrics: {_ce}")

    return result


def fetch_fund_by_key_enriched(full_key: str, fund_name: str = "",
                                portal: str = "", source: str = "",
                                manual_nav_csv: str = "") -> dict:
    """v19.240 R8 L2 enriched wrapper:L1 fetch_fund_by_key(raw NAV + 配息)+
    finalize_fund_metrics(metrics + perf 注入 + reconcile)。

    取代原 L1 fetch_fund_by_key 收尾呼 calc_metrics 的 L1→L2 跨層 import 模式
    (EX-L1ORCH-1 退役)。
    """
    from repositories.fund import fetch_fund_by_key
    result = fetch_fund_by_key(full_key, fund_name, portal, source, manual_nav_csv)
    return finalize_fund_metrics(result)


def fetch_fund_from_moneydj_url_enriched(url: str) -> dict:
    """v19.240 R8 L2 enriched wrapper:L1 fetch_fund_from_moneydj_url(raw)+
    finalize_fund_metrics。

    取代原 L1 內 inline calc_metrics + perf + reconcile 的 L1→L2 跨層 import
    (EX-L1ORCH-1 退役)。L1 cache(@_ttl_cache TTL_15MIN)由 L1 保留,本 wrapper
    每次 L1 命中 cache 後仍 re-run finalize(metrics 計算為 in-memory pandas
    vectorized 操作,成本 ~ms 級可接受)。
    """
    from repositories.fund import fetch_fund_from_moneydj_url
    result = fetch_fund_from_moneydj_url(url)
    return finalize_fund_metrics(result)


# ── calc_dividend_estimate ───────────────────────────────────────────
def calc_dividend_estimate(nav, invest_amount, monthly_div, annual_div,
                           dist_freq, currency, usd_twd=32.0) -> dict:
    if nav<=0 or invest_amount<=0: return {}
    units=invest_amount/nav
    freq_n={"monthly":12,"quarterly":4,"annual":1}.get(dist_freq,12)
    freq_l={"monthly":"每月","quarterly":"每季","annual":"每年"}.get(dist_freq,"每月")
    rate=usd_twd if currency.upper() in ("USD","EUR","AUD") else 1.0
    return dict(
        units=round(units,4), per_dist=round(units*annual_div/freq_n,4),
        freq_label=freq_l, monthly=round(units*monthly_div,4),
        annual=round(units*annual_div,4),
        monthly_twd=round(units*monthly_div*rate,0),
        annual_twd=round(units*annual_div*rate,0),
    )
