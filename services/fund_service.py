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

from shared.colors import GRAY_55, MATERIAL_GREEN, MATERIAL_ORANGE, MATERIAL_RED, MD_DEEP_ORANGE_400, MD_GREEN_A200, MD_PURPLE_500, TRAFFIC_NEUTRAL, WARN_AMBER
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

_RF_ANNUAL_MAX: float = 0.25   # 25%：美國聯邦資金利率史上最高約 19-20%(1981)，留緩衝

def set_risk_free_rate(rf_annual: float) -> None:
    """注入即時無風險利率（FEDFUNDS/100）。在 fetch_all_indicators() 完成後由 app.py 呼叫。

    §1 Fail Loud + §4.1 單位陷阱防護
    ---------------------------------
    呼叫端(`app.py:119`)寫的是 `_cached_ind["FED_RATE"].get("value", 4.0) / 100`
    —— 它**假設** value 的單位是「百分比數值」(3.63 → 0.0363)。一旦上游改回小數、
    或塞進佔位/髒值，rf 會直接失控：

      實際踩到過 — `tests/test_app_apptest.py:357` 對 23 個指標一律塞
      `"value": 50.0` 佔位(含 FED_RATE)→ rf = 50%/年 → 該測試之後**同一個
      process 內**所有 Sharpe / Sortino 的分子都被扣掉 50%，且
      `_RF_ANNUAL` 是 module 全域、跑完不還原 → 跨測試污染。

    rf 只出現在分子 `(r̄ − rf)`，錯了**不會拋例外、不會變 NaN**，只會讓每一檔
    基金的風險調整後報酬一起偏移 → 是典型的「靜默全域污染」。故此處加界:
    超出 [0, `_RF_ANNUAL_MAX`] 一律**拒絕採用並大聲 log**，保留前一個值
    (寧可用略舊的 rf，也不要用一個明顯錯的 rf 汙染全站)。
    """
    global _RF_ANNUAL
    try:
        _v = float(rf_annual)
    except (TypeError, ValueError):
        print(f"[fund_service] ⚠️ set_risk_free_rate 收到非數值 {rf_annual!r} — "
              f"拒絕採用，維持 _RF_ANNUAL={_RF_ANNUAL:.4f}")
        return
    if not (0.0 <= _v <= _RF_ANNUAL_MAX):
        print(f"[fund_service] ⚠️ set_risk_free_rate 收到不合理值 {_v:.4f} "
              f"(合理區間 0 ~ {_RF_ANNUAL_MAX:.2f}) — 疑似單位錯誤(% vs 小數)或髒值，"
              f"拒絕採用，維持 _RF_ANNUAL={_RF_ANNUAL:.4f}")
        return
    _RF_ANNUAL = _v


# ── 風險指標最小樣本門檻（§1 樣本不足寧缺勿假 / §3.3 具名常數非 inline magic）──
# 【為什麼要有門檻】原碼 sharpe/sortino 門檻僅 60 筆（≈3 個月），卻把結果掛在
# 「1Y」欄位旁；線上實測出現「Sharpe 1Y = 0.28」與「1Y 含息 = -2.71%」並列 ——
# 分子 = R − Rf，R=-2.71%、Rf≈3.63%（app.py 由 FED_RATE 注入 _RF_ANNUAL），
# 分子必為負、σ 恆正 → 自算 Sharpe 不可能是 +0.28。兩個不同期間的數字被並列，
# 使用者無從察覺矛盾。門檻與期間標籤必須同一批修，缺一不可。
#
# 【Lo (2002) Eq.9 標準誤】IID 假設下 SE(Ŝ) ≈ sqrt((1 + ½S²)/T)。
#   n=42、S=0.28 → SE=0.157 → 95% CI=[-0.03, 0.59]，**跨越 0**（無方向性）。
#   注意：即使 T=250，年化 Sharpe 的 SE 仍 ≈ 1.0（SE_ann = √252 × SE_daily
#   ≈ sqrt((1+½S_d²)/T_years)），統計顯著性在基金常見歷史長度下**不可達**。
#   因此門檻不以「達成顯著」為目標，而以「達成標籤宣稱的期間」為目標：
#   欄位叫 1Y 就必須真的有 1 年資料，否則 §1 回 None + 原因字串。
MIN_OBS_SHARPE_SORTINO: int = 250   # 250/252 = 99.2% 交易年（留 ~2 日假期容差）
MIN_OBS_MAX_DRAWDOWN: int = 125     # ≈ 半個交易年（126）；MaxDD 是路徑統計不需年化，
                                    # 但對窗長單調非遞減，< 半年時「窗內有沒有碰到修正」
                                    # 的運氣成分大於基金本身風險特徵。
MIN_OBS_CALMAR: int = 3 * TRADING_DAYS_PER_YEAR   # 756 = Young (1991) 原始定義 36 個月
MIN_DOWNSIDE_OBS_SORTINO: int = 5   # 低於 MAR 的樣本數下限（TDD 估計可靠度）
# ⚠️ SSOT 待遷移：以上 4 個常數語意上屬 `shared/signal_thresholds.py`
#    （對照既有 FRONTIER_MIN_OBS / BACKTEST_MIN_COMMON_DAYS）。本次改動的檔案
#    所有權僅限本檔 + tests/，故先在本檔具名常數化；shared 開放後應整組上移。


def _insufficient_reason(n: int, need: int, what: str = "交易日") -> str:
    """樣本不足原因字串（§1：回 None 必須說明為什麼，不可靜默）。"""
    return f"樣本不足（{n}/{need} {what}）"


def _target_downside_deviation(excess) -> float:
    """Target Downside Deviation（TDD，Sortino 分母）。

        σ_D = sqrt( (1/N) · Σ_{t=1..N} [ min(0, r_t − MAR) ]² )

    Parameters
    ----------
    excess : array-like
        **已扣掉 MAR 的超額報酬序列**（r − MAR），單位 = ratio（非 %）。

    Returns
    -------
    float
        σ_D，與 `excess` 同單位。空序列回 0.0（caller 須自行判定並回 None）。

    Notes
    -----
    分母為**全樣本 N**：超過 MAR 的觀測值平方離差計 0，但**仍留在分母**。
    CFA Institute（Kidd 2012, "The Sortino Ratio"）逐字點名「除以低於 MAR 的
    筆數而非總筆數」是 *a fairly common mistake*——那算出來的是「負報酬子集合
    繞自身平均數的樣本標準差」，不是 downside deviation。
    以 {−1%, −2%, −3%, −5%} 為例：本式 = 3.12%，錯式 = 1.71%（低估 45%）。
    """
    _a = np.asarray(excess, dtype=float)
    if _a.size == 0:
        return 0.0
    return float(np.sqrt(float(np.square(np.minimum(_a, 0.0)).mean())))


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
        health_color = MD_DEEP_ORANGE_400
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


def _total_return_nav(s: pd.Series, divs: list) -> pd.Series:
    """把配息「再投資複利」還原進 NAV 序列,供風險指標(σ / Sharpe / Sortino /
    max_drawdown)計算,消除除息日 NAV 跳空造成的**假**波動與**假**回撤。

    背景(§4.5 配息切割 / §4.6 ex-date 跳空):配息型基金除息日 NAV 會下跳一個
    配息額,這**不是**真實下跌(持有人領到現金),但自算的 log return 會把它當一次
    暴跌 → 高估波動度、放大 max_drawdown、壓低 Sharpe/Sortino。wb07(MoneyDJ 官方
    風險表)本就含息;本函式讓「自算 fallback」與 wb07 同基準(apples-to-apples),
    也讓 reconcile 對帳兩邊可比。

    複用 SSOT `calculate_fund_total_return()`(Factor 還原法)+ 既有
    `divs → div_df` 轉換規則(對齊 calc_metrics ret_1y_total 路徑:skip
    amount<=0、日期斜線正規化)。

    Returns
    -------
    pd.Series
        與 `s` **同 index、同長度** 的還原後序列(Adj_NAV)。

    降級(§1 Fail Loud → 顯式回退,不偽造):
      - `divs` 空 / 全部 amount<=0 / 日期不可解析 → 無配息事件 → **逐點等於 `s`**
        (純累積型基金天然一致,非掩蓋;純累積型行為零變化)。
      - 還原序列長度/正值不變量不符(如同一除息日重複配息使 left-merge 膨脹)→
        stderr log + **回退原始 `s`**(寧可用未還原序列,不可回傳錯位序列污染指標)。
    """
    if s is None or s.empty:
        return s
    # divs(list[dict{date,amount}]) → div_df:複用 ret_1y_total 路徑的轉換規則
    _div_rows = []
    if divs:
        for _d in divs:
            try:
                _amt = float(_d.get("amount", 0) or 0)
                if _amt <= 0:                       # 0 / 負配息不還原
                    continue
                _date_raw = str(_d.get("date", "") or "").replace("/", "-")
                _div_rows.append(
                    {"Date": pd.to_datetime(_date_raw), "Dividend": _amt}
                )
            except Exception:
                continue
    if not _div_rows:
        # 無有效配息事件 → 還原序列 == 原序列(顯式,非偽造)
        return s
    try:
        _nav_df = pd.DataFrame({
            "Date": pd.to_datetime(s.index),
            "NAV": s.values.astype(float),
        })
        _tr = calculate_fund_total_return(_nav_df, pd.DataFrame(_div_rows))
        # 不變量(§4.2):還原序列須與原序列等長 + 全正。
        # FundNavSchema 保證 s 升冪,calculate_fund_total_return 內部亦 sort_values,
        # 故可位置對齊;長度不符(重複除息日使 left-merge 膨脹)即放棄還原、回退 s。
        if _tr.empty or len(_tr) != len(s):
            raise ValueError(f"還原序列長度 {len(_tr)} != 原序列 {len(s)}")
        s_tr = pd.Series(_tr["Adj_NAV"].to_numpy(), index=s.index)
        if not bool((s_tr > 0).all()):
            raise ValueError("還原後序列含非正值")
        return s_tr
    except Exception as _e:
        import sys as _sys_tr
        print(
            f"[fund_service/_total_return_nav] 配息還原失敗,回退原始 NAV 算風險:"
            f"{type(_e).__name__}: {_e}",
            file=_sys_tr.stderr,
        )
        return s


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
    - `sortino`              年化 Sortino Ratio(TDD 下檔離差)
    - `calmar`               Calmar = 3Y 年化含息報酬 / |3Y 期間最大回撤|
                             (分子分母**同一條含息還原序列 s_tr、同一個 3Y 窗**,C-4)
    - `std_1y` / std_2y / std_3y / std_5y  年化標準差(同優先序)
    - `max_drawdown`         最大回撤 %(全序列)
    - `risk_metric_meta`     上述 4 指標的實際期間 / 來源 / 缺值原因(P0-3)

    **風險指標定義與樣本門檻(P0-3 修正,§1 + §4.1)**
    ---------------------------------------------
    | 指標 | 公式 | 基準(MAR/rf) | 最小樣本 | 期間 |
    |---|---|---|---|---|
    | Sharpe  | (r̄ − rf) / σ × √252 | rf = _RF_ANNUAL/252 | 250 交易日 | 近 1 年 |
    | Sortino | (r̄ − MAR) / σ_D × √252,<br>σ_D = √( (1/N)·Σ[min(0, rₜ−MAR)]² ) | **MAR = rf(同 Sharpe 分子)** | 250 交易日<br>+ ≥5 筆低於 MAR | 近 1 年 |
    | MaxDD   | min( cum/cummax − 1 ),cum = exp(cumsum(log_ret)) | — | 125 交易日 | 全序列 |
    | Calmar  | 3Y 年化**含息**報酬 / abs(3Y 期間 MaxDD)<br>兩者同源 `cum = exp(cumsum(log s_tr))` 同窗 | — | 756 交易日 | 固定 3Y |

    - **Sharpe 與 Sortino 分子完全相同**(r̄ − rf),差別只在風險量測(全域 σ vs
      下檔 σ_D)→ **同一張表可並列比較**。(若改採 MAR=0 則兩者基準不同,
      屆時必須加註「不可交叉比較」。)
    - **Calmar 已取消 1Y fallback**:MaxDD 對窗長單調非遞減 ⇒ Calmar_1Y ≥ Calmar_3Y
      恆成立,混排會系統性抬高短歷史基金。不足 3Y → None + 原因字串。
    - 任一指標樣本不足一律回 **None + `risk_metric_meta[<指標>]["reason"]`**,
      **禁止**靜默回 0 或硬算(§1)。
    - 全部年化用 `TRADING_DAYS_PER_YEAR`(252 交易日,**非** 365 日曆日,§4.1)。
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
    # v19.356 項4:風險指標(σ / Sharpe / Sortino / max_drawdown)改用「配息還原
    # 淨值序列」s_tr — 消除除息日跳空造成的假波動/假回撤,並與 wb07 官方含息風險表
    # 同基準(詳見 _total_return_nav docstring)。**顯示值 `now`、買賣點(_sig_win)、
    # 高低點(_hl)、純 NAV 報酬(_ret / ret_1y_total)一律仍用原始 `s`。**
    # 無配息基金 s_tr 逐點等於 s → log_ret 與舊版位元相同,行為零變化。
    s_tr = _total_return_nav(s, divs)
    log_ret = np.log(s_tr / s_tr.shift(1)).dropna()

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

    # ── MK v3.2 公式（A+B v19.318）：回歸中樞 ± kσ，σ=真·淨值統計標準差 ─────────
    # 沿革:v3.0 用 wb07 年化波動率(σ_abs=年高×年化σ%)→ 3σ 常超出區間、買賣點永遠觸不到;
    #   v3.1(v19.313)改區間基準 (年高-年低)/3,但「買錨年高、賣錨年低」使 買1=賣2、買2=賣1
    #   數學重疊,6 條線塌成 4 條,且 band 寬度=年區間(平靜基金仍看似過寬)。
    # v3.2(user 選 A+B):
    #   B — σ 改「近 1 年淨值的統計標準差」(真 standard deviation,隨實際波動縮放,
    #       平靜期自動變窄貼價,不受一年前大跌拖累)。
    #   A — 以「回歸中樞(近 1 年均值)」為中心 ± kσ 對稱佈局 → 6 條線天然不重疊。
    #   年高/年低改在 Tab2 圖上以參考線呈現(區間脈絡),不再當 band 錨點。
    #   訊號語意:現價偏離回歸中樞幾個 σ → 幾檔買/賣。std_1y(年化%)仍供 Sharpe/波動顯示。
    _sig_win = s.dropna()
    if len(_sig_win) > TRADING_DAYS_PER_YEAR:
        _sig_win = _sig_win.tail(TRADING_DAYS_PER_YEAR)   # 近 1 年(不足則全序列)
    if len(_sig_win) >= 20:
        sigma_center = round(float(_sig_win.mean()), 4)          # 回歸中樞
        sigma_abs    = round(float(_sig_win.std(ddof=1)), 4)     # 真·統計標準差(NAV 單位)
        buy_mode     = "淨值σ通道"
        print(f"[calc_metrics] 買點模式=淨值σ通道 中樞={sigma_center} σ={sigma_abs} n={len(_sig_win)}")
    else:
        # 資料不足(<20 筆)→ 退回區間中點 + (年高-年低)/6(仍對稱不重疊),旗標待更新
        sigma_center = round((ref_high + ref_low) / 2, 4)
        sigma_abs    = round((ref_high - ref_low) / 6, 4)
        buy_mode     = "區間σ(資料不足)"
        print(f"[calc_metrics] 買點模式=區間σ fallback(n<20) 中樞={sigma_center} σ={sigma_abs}")

    std_amt = max(sigma_abs, 0.0001)   # 防呆:σ 不可為 0(全平序列)

    b1    = round(sigma_center - std_amt,     4)   # 中樞 - 1σ（小跌小買 20%）
    b2    = round(sigma_center - 2 * std_amt, 4)   # 中樞 - 2σ（急跌穩買 30%）
    b3    = round(sigma_center - 3 * std_amt, 4)   # 中樞 - 3σ（大跌大買 50%）
    sell1 = round(sigma_center + std_amt,     4)   # 中樞 + 1σ（小漲停利 20%）
    sell2 = round(sigma_center + 2 * std_amt, 4)   # 中樞 + 2σ（急漲停利 30%）
    sell3 = round(sigma_center + 3 * std_amt, 4)   # 中樞 + 3σ（大漲停利 50%）

    print(f"[calc_metrics] σ={std_amt} b1={b1} b2={b2} b3={b3} sell1={sell1} sell2={sell2} sell3={sell3}")

    buy_basis  = sigma_center   # v3.2: 買賣點均錨定回歸中樞(近 1 年均值)
    sell_basis = sigma_center

    # 距離 % （正=尚未觸發 / 0 或負=已觸發；接近閾值=2%）
    NEAR_PCT = NEAR_DIVIDEND_WARNING_PCT  # v19.74 W2 SSOT
    def _dist(target):
        if (not target) or now <= 0: return None
        return round((now - target) / target * 100, 2)
    buy_distance_pct  = {"b1": _dist(b1), "b2": _dist(b2), "b3": _dist(b3)}
    sell_distance_pct = {"s1": _dist(sell1), "s2": _dist(sell2), "s3": _dist(sell3)}

    # 倉位判斷（深度優先；買勝過賣以利風險控管）
    if std_amt < ref_high * 0.001:   # σ < 現價 0.1% → 波動極低或資料不足,訊號不可靠
        pos_l, pos_c = "波動極低/待更新 📡", GRAY_55
    elif now <= b3:    pos_l, pos_c = "大跌大買 🔥 (投 50%)", MD_PURPLE_500
    elif now <= b2:    pos_l, pos_c = "急跌穩買 📈 (投 30%)", MATERIAL_GREEN
    elif now <= b1:    pos_l, pos_c = "小跌小買 ✅ (投 20%)", MD_GREEN_A200
    elif now >= sell3: pos_l, pos_c = "大漲停利 🔔 (出 50%)", MATERIAL_RED
    elif now >= sell2: pos_l, pos_c = "急漲停利 ⚠️ (出 30%)", MD_DEEP_ORANGE_400
    elif now >= sell1: pos_l, pos_c = "小漲停利 💰 (出 20%)", WARN_AMBER
    else:              pos_l, pos_c = "正常波動區",            TRAFFIC_NEUTRAL

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
        bb_sig, bb_c = "通道過窄（波動低）", TRAFFIC_NEUTRAL
    # 輸出時間序列供圖表用
    bb_upper_series = bb_upper_s.dropna()
    bb_lower_series = bb_lower_s.dropna()
    rf=_RF_ANNUAL/TRADING_DAYS_PER_YEAR; r252=log_ret.tail(TRADING_DAYS_PER_YEAR) if len(log_ret)>=TRADING_DAYS_PER_YEAR else log_ret  # Bug1: rf 改用即時 FEDFUNDS
    # ── 樣本閘門(P0-3):自算 Sharpe / Sortino 一律 ≥ MIN_OBS_SHARPE_SORTINO ──
    # 原門檻 60 筆(≈3 個月)讓 42 天序列也能吐出掛在「1Y」旁的 Sharpe(見常數區
    # 說明)。不足 → None + 原因字串(§1),**禁止**靜默回 0 或硬算。
    _n252 = len(r252)
    _sharpe_reason = None
    _sortino_reason = None
    if _n252 < MIN_OBS_SHARPE_SORTINO:
        _sharpe_reason = _insufficient_reason(_n252, MIN_OBS_SHARPE_SORTINO)
        _sortino_reason = _sharpe_reason
    # v19.341(第七份 review 3-2):Sharpe 分母補 std guard — 同函式 Sortino/
    # Calmar 皆有防,唯 Sharpe 漏。常數 NAV(停售/剛成立填平值,§4.6)std=0 →
    # inf 直流 UI。不足回 None(§1 寧缺勿假)。
    _std252 = float(r252.std()) if _n252 >= MIN_OBS_SHARPE_SORTINO else 0.0
    sharpe = None
    if _n252 >= MIN_OBS_SHARPE_SORTINO:
        if _std252>1e-12:
            sharpe = round(float((r252.mean() - rf) / _std252 * np.sqrt(TRADING_DAYS_PER_YEAR)), 2)
        else:
            _sharpe_reason = "σ=0(常數 NAV / 停售,§4.6)→ Sharpe 未定義"

    # ── Sortino:Target Downside Deviation(TDD)─────────────────────────
    # 【修正】原式 `r252[r252 < 0].std()` 是「負報酬**子集合**繞**自身平均數**的
    # 樣本標準差(ddof=1)」,**不是** downside deviation。CFA Institute
    # (Kidd 2012, "The Sortino Ratio")逐字點名此為 "a fairly common mistake":
    # 把平方離差和除以「低於 MAR 的筆數」而非「總樣本數」。
    # 以 {-1%,-2%,-3%,-5%} 為例:正確 TDD = 3.12%、原式 = 1.71%
    # → TDD 低估 45%、Sortino **高估 82%**。方向恆為高估 ⇒ 下檔風險最大的基金
    # 被評得最好,這是**排序反向**不是精度問題。
    #
    #   σ_D = sqrt( (1/N) · Σ_{t=1..N} [ min(0, r_t − MAR) ]² )   ← 分母為全樣本 N
    #                                                                (超過 MAR 者計 0,
    #                                                                 但**仍留在分母**)
    #   Sortino = (r̄ − MAR) / σ_D × √252
    #
    # 【MAR 選定 = rf(日化無風險利率)】原碼分子扣 rf、分母隱含 target=0,
    # 分子分母基準不一致。統一取 MAR = rf 的理由:
    #  (1) Sortino & Price (1994) 原始定義分子分母用**同一個** MAR;
    #      CFA Institute 文件確認 MAR=0 亦為合法取值,但必須前後一致。
    #  (2) 取 MAR=rf 後,Sortino 與 Sharpe **分子完全相同**(r̄ − rf),差別只在
    #      風險量測(全域 σ vs 下檔 σ_D)→ 同一張表可並列比較;若取 MAR=0
    #      則兩者基準不同,不可交叉比較(需另加警語)。
    #  (3) wb07 官方風險表**無** Sortino 欄(ui/helpers/fund_grp_health/risk.py:96),
    #      不存在必須對齊 MAR=0 的外部錨。
    # 【單位】r252 為日對數報酬(ratio 非 %),rf 為日簡單利率(_RF_ANNUAL/252);
    #        年化用 √252 交易日(非 365 日曆日,§4.1)。
    sortino = None
    if _n252 >= MIN_OBS_SHARPE_SORTINO:
        _mar = rf                                  # MAR 與 Sharpe 分子同基準
        _excess = r252 - _mar
        _n_down = int((_excess < 0).sum())
        if _std252 <= 1e-12:
            # 退化序列守衛(對齊 Sharpe 的 v19.341 guard):總波動 = 0 表示 NAV 為
            # 常數(停售 / 剛成立填平值,§4.6)—— 這是**資料假影**不是「零風險投資」。
            # 此時每日報酬皆等距低於 MAR,σ_D 恰等於 |rf|,Sortino 會收斂到
            # −√252 ≈ −15.87 這種「看起來很精確」的數字,但它只反映 rf 不反映基金。
            # §1:寧缺勿假 → None + 原因。
            _sortino_reason = "σ=0(常數 NAV / 停售,§4.6)→ 序列無風險資訊,Sortino 未定義"
        elif _n_down < MIN_DOWNSIDE_OBS_SORTINO:
            # 全正報酬 / 幾乎無下檔 → σ_D 趨近 0,Sortino → inf。§1 決策:回 **None**
            # 而非 inf —— inf 不是「零風險」的證據,只代表這個窗口內沒出現下檔;
            # 且 inf 會汙染 portfolio_service.calc_fund_factor_score 的排序與正規化。
            _sortino_reason = (
                f"低於 MAR 的樣本僅 {_n_down} 筆(需 ≥{MIN_DOWNSIDE_OBS_SORTINO})"
                f"→ 下檔離差不可靠,不給假精確")
        else:
            _tdd = _target_downside_deviation(_excess.to_numpy(dtype=float))
            if _tdd > 1e-12:
                sortino = round(
                    float(float(_excess.mean()) / _tdd * np.sqrt(TRADING_DAYS_PER_YEAR)), 2)
            else:
                _sortino_reason = "σ_D=0(全期無低於 MAR 的報酬)→ Sortino 未定義(不回 inf)"

    # ── 累積淨值指數(log 空間連乘,§4.4 數值穩定性)────────────────────
    # 【修正】原式 `(1 + log_ret).cumprod()` 把**對數**報酬餵進**簡單**報酬的複利式。
    # 正確:cum_t = exp( Σ_{i≤t} ln(1+r_i) ) = exp(cumsum(log_ret))。
    # 因 ln(1+x) ≤ x(等號僅 x=0),原式每一步都少算 → cum **系統性向下漂移**
    # → **MaxDD 被高估**,且下游 Calmar 分母全部繼承此偏差
    # (以 ACCP138 官方年化 σ=8.69% 估算,漂移約 0.38%/年,3 年 ≈ 1.1pp)。
    # 改 exp(cumsum) 後 cum 逐點恰等於 s_tr / s_tr[0](還原淨值歸一化),零漂移。
    cum=np.exp(log_ret.cumsum())
    # v19.372:max_dd ÷0 guard(對齊本函式 Sharpe/Sortino/Calmar 既有 §1 防線 + SSOT
    # portfolio_service.compute_max_drawdown 的 (s<=0) 語意)。停售/剛成立/資料異常使 cum
    # 或其 running-max ≤0(§4.6 邊界)→ 回撤未定義,回 None 寧缺勿假,避免 inf/NaN 汙染 KPI。
    # drawdown_t = cum_t / cummax_t − 1 ∈ [-1, 0];取 min 即最大回撤(負值 %)。
    _n_cum = len(cum)
    _maxdd_reason = None
    _cummax=cum.cummax()
    if _n_cum < MIN_OBS_MAX_DRAWDOWN:
        max_dd=None
        _maxdd_reason=_insufficient_reason(_n_cum, MIN_OBS_MAX_DRAWDOWN)
    elif bool((cum>0).all()) and bool((_cummax>0).all()):
        max_dd=round(float(((cum-_cummax)/_cummax).min())*100,2)
    else:
        max_dd=None
        _maxdd_reason="累積淨值序列含非正值(停售/資料異常,§4.6)→ 回撤未定義"
    # v19.341(第七份 review 3-2):分母補 >0 guard(第二道防線)— 本函式入口
    # pandera 已擋 nav<=0,此 guard 防未來驗證放寬/內部直呼時 ZeroDivisionError。
    def _ret(n): return round((now-float(s.iloc[-n]))/float(s.iloc[-n])*100,2) if (len(s)>=n and float(s.iloc[-n])>0) else None

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
    # ── Calmar:統一 36 個月(Young 1991 原始定義)= 3 × 252 = 756 交易日 ──────
    # 【修正】原碼「3Y 年化不可得 → fallback 1Y 純 NAV 報酬」+「分母用全期 max_dd」
    # 有兩重期間不一致:
    #  (a) 1Y fallback:MaxDD 對窗口長度**單調非遞減**(W₁ ⊆ W₂ ⇒ |DD(W₁)| ≤ |DD(W₂)|),
    #      故年化報酬相同時 Calmar_1Y = R/|DD_1Y| ≥ R/|DD_3Y| = Calmar_3Y **恆成立**。
    #      同表混排 1Y 與 3Y Calmar 是兩個不可比的統計量,短歷史基金被系統性抬高,
    #      排序無意義。且 caller `portfolio_service.calc_fund_factor_score` 是**跨基金
    #      排序**,只加期間標籤救不了 —— 必須統一,故**取消 1Y fallback**。
    #  (b) 分母原用「全期」max_dd:10 年歷史的基金拿 3Y 分子除以 2008 年的回撤,
    #      同樣是期間錯配。改用**同一個 3Y 窗**的回撤(Young 定義即為同窗)。
    # 不足 3Y → None + 原因字串(§1),不以短窗充數。
    #  (c) **C-4 分子分母同源(本次收斂)**:原分子 `_ret_3y_ann` 來自**原始 NAV**
    #      (純價格報酬),分母 3Y 回撤來自 `cum`(= s_tr 配息還原含息序列)。本專案
    #      主力是月配息基金:年配息 8% 的基金 3 年純價格報酬可能 −15%(年化 −5.3%),
    #      含息回撤卻只有 −6% → Calmar **連正負號都可能相反**。剛以「期間不一致 ⇒
    #      排序無意義」砍掉 1Y fallback,同一式子留「基準不一致」破口即自相矛盾。
    #      修法:分子改由**同一條 `cum` 的同一個 3Y 窗**端點推年化 —
    #          R_ann = (cum[-1] / cum[窗首])^(1/年數) − 1
    #      無配息基金 s_tr ≡ s → 分子與 `_ret_3y_ann` 同值(僅少一次中間 round)。
    #      **`ret_3y_ann` 欄位語意不動**(多 caller 消費純 NAV 年化),僅 Calmar 改用
    #      同源分子,並在 meta 揭露 `ret_3y_ann_tr_pct` 供對帳。
    #  (d) **C-11 先 round 再除(本次修正)**:原碼把 `round(dd,2)` 拿去當除數 ——
    #      分母被量化到 0.01pp;更糟的是真實回撤 −0.004% 會 round 成 −0.0 →
    #      命中 `abs(...) <= 1e-9` → Calmar 被誤判為 None。除法一律用**未 round**
    #      的 `_dd3_raw`,`round` 只用在 meta 顯示。
    calmar = None
    _calmar_reason = None
    _calmar_dd_3y = None            # 顯示用(2dp);**禁止**拿去當除數(C-11)
    _calmar_ret_3y_ann_tr = None    # 顯示用(2dp);分子同源揭露(C-4)
    _calmar_window_days = None
    if len(s) < MIN_OBS_CALMAR:
        _calmar_reason = _insufficient_reason(len(s), MIN_OBS_CALMAR)
    else:
        _c3 = cum.tail(MIN_OBS_CALMAR)            # 同窗:最近 36 個月的還原淨值路徑
        _m3 = _c3.cummax()
        _calmar_window_days = int(len(_c3))       # 期間誠實化:實際窗長(log 差分少 1 點)
        _dd3_raw = None
        if bool((_c3 > 0).all()) and bool((_m3 > 0).all()):
            _dd3_raw = float(((_c3 - _m3) / _m3).min()) * 100.0
            _calmar_dd_3y = round(_dd3_raw, 2)
        # 分子:同一條 s_tr 還原序列 + 同一個窗 → 與分母 apples-to-apples(C-4)
        _ret3_tr_raw = None
        _c3_start = float(_c3.iloc[0]) if _calmar_window_days else 0.0
        _c3_end = float(_c3.iloc[-1]) if _calmar_window_days else 0.0
        _years3 = _calmar_window_days / TRADING_DAYS_PER_YEAR if _calmar_window_days else 0.0
        if _c3_start > 0 and _c3_end > 0 and _years3 > 0:
            _ret3_tr_raw = ((_c3_end / _c3_start) ** (1.0 / _years3) - 1.0) * 100.0
            _calmar_ret_3y_ann_tr = round(_ret3_tr_raw, 2)
        if _dd3_raw is None:
            _calmar_reason = "3Y 累積序列含非正值(§4.6)→ 回撤未定義"
        elif _ret3_tr_raw is None:
            _calmar_reason = "3Y 含息還原序列端點非正 → 同源年化報酬不可得"
        elif abs(_dd3_raw) <= 1e-9:
            _calmar_reason = "3Y 期間最大回撤 = 0 → Calmar 未定義(不回 inf)"
        else:
            calmar = round(_ret3_tr_raw / abs(_dd3_raw), 2)
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

    # ── 風險指標來源 / 期間 meta(§2.2 provenance + §1 期間誠實化)──────────
    # 背景:同一列同時出現「Sharpe 1Y = 0.28」與「1Y 含息 = -2.71%」時,前者其實
    # 來自 wb07 官方一年欄、後者來自本地 42 天序列 —— 兩個不同期間的數字被並列,
    # 使用者無從察覺。本區塊讓 caller 能取得每個指標**實際**使用的期間與來源。
    # 【向後相容】純新增 key(caller 全部走 dict.get(),已 grep 確認無 `**metrics`
    # 展開 / 無固定 key set 斷言 / fund_batch.py 為顯式欄位對映)→ 零破壞。
    _wb07_sharpe_1y = safe_float(risk_tbl.get("一年", {}).get("Sharpe"))
    _wb07_sharpe_6m = safe_float(risk_tbl.get("六個月", {}).get("Sharpe"))
    _sharpe_self_calc = sharpe          # 本地自算值(可能為 None)
    # 優先序:wb07 一年 > wb07 六個月 > 本地自算。用 `is not None` 而非 `or`:
    # 原碼 `A or B or C` 在 wb07 Sharpe **恰為 0.0** 時 falsy → 落到自算值,
    # 但 sharpe_source 用 `is not None` 判定仍標 "wb07_1y" → **值與來源標籤不一致**
    # (provenance 說謊,§2.2;同 portfolio_service v19.397 `or 0` 家族)。
    if _wb07_sharpe_1y is not None:
        _sharpe_out, _sharpe_src = _wb07_sharpe_1y, "wb07_1y"
        _sharpe_period_days, _sharpe_period_label = None, "wb07 官方一年(期間由 MoneyDJ 定義)"
    elif _wb07_sharpe_6m is not None:
        _sharpe_out, _sharpe_src = _wb07_sharpe_6m, "wb07_6m"
        _sharpe_period_days, _sharpe_period_label = None, "wb07 官方六個月"
    elif _sharpe_self_calc is not None:
        _sharpe_out, _sharpe_src = _sharpe_self_calc, "self_calc"
        _sharpe_period_days, _sharpe_period_label = _n252, f"本地自算 {_n252} 交易日"
    else:
        _sharpe_out, _sharpe_src = None, None
        _sharpe_period_days, _sharpe_period_label = None, None

    # 混期警告:官方 Sharpe(1Y/6M)× 本地短窗報酬並列 = 使用者看不見的期間錯配。
    _mixed_period_warning = None
    if _sharpe_src in ("wb07_1y", "wb07_6m") and _ret_1y_window_days and _ret_1y_window_days < 350:
        _mixed_period_warning = (
            f"期間不一致:Sharpe 來自「{_sharpe_period_label}」,但同列 1Y 含息報酬"
            f"只用了本地 {_ret_1y_window_days} 天序列 → 兩者非同一期間,不可交叉推論。")

    # C-3:自算 Sharpe 被 MIN_OBS_SHARPE_SORTINO 擋掉時,§4.3「關鍵指標第二種算法對帳」
    # 的 `sharpe_reconcile` 恆為 a_missing —— **對帳能力被門檻降級**,而 UI 的四態 chip
    # 只會顯示「⬜ a_missing」,看不出是「本地根本沒算」還是「本地算了但沒值」。
    # 此處顯式標記原因,UI 必須渲染(§1:降級不可靜默)。
    _sharpe_reconcile_blocked = None
    if _sharpe_self_calc is None and (_wb07_sharpe_1y is not None or _wb07_sharpe_6m is not None):
        _sharpe_reconcile_blocked = (
            f"雙演算法對帳停用:僅有 wb07 單源,本地自算 Sharpe 缺"
            f"({_sharpe_reason or '原因未記錄'})→ 無第二演算法可比(§4.3)。")

    _risk_metric_meta = {
        "sharpe": {
            "source": _sharpe_src,
            "period_days": _sharpe_period_days,          # None = 官方值,期間非本地決定
            "period_label": _sharpe_period_label,
            "min_required": MIN_OBS_SHARPE_SORTINO,
            "self_calc_value": _sharpe_self_calc,
            "self_calc_reason": _sharpe_reason,          # 自算為何缺(即使 wb07 有值)
            "reconcile_blocked_reason": _sharpe_reconcile_blocked,   # C-3
        },
        "sortino": {
            "source": "self_calc" if sortino is not None else None,
            "period_days": _n252 if sortino is not None else None,
            "period_label": (f"本地自算 {_n252} 交易日" if sortino is not None else None),
            "min_required": MIN_OBS_SHARPE_SORTINO,
            "definition": "TDD(分母全樣本 N),MAR=rf,與 Sharpe 分子同基準",
            "reason": _sortino_reason,
        },
        "max_drawdown": {
            "source": "self_calc" if max_dd is not None else None,
            "period_days": _n_cum if max_dd is not None else None,
            "period_label": (f"全序列 {_n_cum} 交易日" if max_dd is not None else None),
            "min_required": MIN_OBS_MAX_DRAWDOWN,
            "reason": _maxdd_reason,
        },
        "calmar": {
            "source": "self_calc" if calmar is not None else None,
            # 期間誠實化:回報**實際**窗長(log 差分後比 len(s) 少 1 點),不報宣稱值
            "period_days": _calmar_window_days if calmar is not None else None,
            "period_label": (
                f"3Y 同源含息窗 {_calmar_window_days} 交易日(Young 1991)"
                if calmar is not None else None),
            "min_required": MIN_OBS_CALMAR,
            "max_dd_3y_pct": _calmar_dd_3y,
            # C-4 對帳用:Calmar 分子(含息還原、同窗年化);與欄位 `ret_3y_ann`
            # (純 NAV 價格年化)刻意不同源,高配息基金兩者差距即為配息貢獻。
            "ret_3y_ann_tr_pct": _calmar_ret_3y_ann_tr,
            "ret_3y_ann_price_pct": _ret_3y_ann,
            "reason": _calmar_reason,
        },
        "mixed_period_warning": _mixed_period_warning,
    }
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
        # 夏普優先用 wb07(更精確);自算值需 ≥ MIN_OBS_SHARPE_SORTINO 筆
        # v19.177 #5A:加 sharpe_source provenance 標記,ai_service / UI hover 顯示來源
        # (P0-3:值與來源改由上方單一選擇邏輯決定,消除 `or` falsy-0 造成的標籤說謊)
        sharpe=_sharpe_out,
        sharpe_source=_sharpe_src,
        # max_dd 永遠自算(exp(cumsum) − cummax 算式);None 時來源亦誠實為 None
        max_drawdown_source=("self_calc" if max_dd is not None else None),
        sortino_source=("self_calc" if sortino is not None else None),
        calmar_source=("self_calc" if calmar is not None else None),
        # P0-3:各風險指標實際期間 / 門檻 / 缺值原因(§1 + §2.2)
        risk_metric_meta=_risk_metric_meta,
        # F-RECON-1 phase 3 v19.88 — Sharpe 雙演算法對帳(self-calc vs MoneyDJ wb07)
        sharpe_reconcile=_reconcile_sharpe_pair(
            self_calc=_sharpe_self_calc,
            moneydj=_wb07_sharpe_1y,
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
def assess_series_coverage(s: pd.Series) -> dict:
    """v19.360 ②:序列覆蓋診斷 — 年化指標(×√252)假設每點=1 交易日,稀疏序列會失真。

    回傳 {"coverage": float, "max_gap_days": int|None, "sparse": bool}:
    - coverage    = 實際點數 / 預期交易日(span_days × 252/365),上限 1.0
    - max_gap_days = 相鄰兩點最大缺口(日曆日)
    - sparse      = coverage < NAV_HIST_COVERAGE_MIN 或 max_gap > NAV_HIST_MAX_GAP_DAYS
    門檻 SSOT:shared/signal_thresholds.py(§3.3 無 inline magic)。
    """
    from shared.signal_thresholds import (
        NAV_HIST_COVERAGE_MIN, NAV_HIST_MAX_GAP_DAYS, TRADING_DAYS_PER_YEAR)

    if s is None or len(s) < 2:
        return {"coverage": 0.0, "max_gap_days": None, "sparse": True}
    span_days = (s.index[-1] - s.index[0]).days
    if span_days <= 0:
        return {"coverage": 0.0, "max_gap_days": None, "sparse": True}
    expected = span_days * TRADING_DAYS_PER_YEAR / 365.0
    coverage = min(1.0, len(s) / expected) if expected > 0 else 0.0
    gaps = s.index.to_series().diff().dt.days.dropna()
    max_gap = int(gaps.max()) if len(gaps) else None
    sparse = coverage < NAV_HIST_COVERAGE_MIN or (max_gap or 0) > NAV_HIST_MAX_GAP_DAYS
    return {"coverage": round(float(coverage), 3), "max_gap_days": max_gap,
            "sparse": bool(sparse)}


def _merge_nav_history_series(s_live: pd.Series, code: str) -> tuple:
    """v19.360 B:合併 nav_history 累積/匯入序列(union keep-last,**live 優先**)。

    L2→L2(services.nav_history_gs),不碰 L1(§8.2;避免重蹈 EX-L1ORCH-1)。
    - Sheet 無資料 / 未啟用 → 回 (s_live, None) 行為與現在完全一致
    - Sheet 讀失敗 → fail-soft:log + 回 (s_live, trace{success:False})(不炸整個健診)
    - 有新增點 → 回 (merged, trace{success:True, added:N})
    - v19.366 5/8:s_live=None(live 全敗)→ 視為空序列,純累積歷史可整段頂上(救援)
    """
    if s_live is None:
        s_live = pd.Series(dtype=float)
    try:
        from services.nav_history_gs import load_series
        s_hist = load_series(code)
    except Exception as e:  # NavHistoryError 等 — 讀失敗退回 live-only(§4.6 降級鏈)
        print(f"[nav_history] ⚠️ {code} 讀取失敗,退回 live-only:{e}")
        return s_live, {"source": "nav_history_merge", "success": False,
                        "error": str(e)[:120]}
    if s_hist is None or len(s_hist) == 0:
        return s_live, None
    # union keep-last:hist 在前、live 在後 → 同日 live 蓋 hist(live 為權威新抓)
    merged = pd.concat([s_hist, s_live]).groupby(level=0).last().sort_index()
    added = len(merged) - len(s_live)
    if added <= 0:  # hist 全被 live 涵蓋 → 不動原序列(保留 live attrs)
        # 2026-08-11:原本這裡 `return s_live, None` —— 這是**全站唯一**知道
        # 「有累積、但還沒產生淨增益」的地方,卻把資訊整包丟掉。後果:累積機制
        # 每天確實在寫(畫面有「本次新存 N 筆」),序列卻一動不動,而畫面上**沒有
        # 任何地方**講得出中間的落差 → 使用者(和我)只能猜。
        # 改成回一個資訊性 trace。
        # ⚠️ 刻意**不設 `success` 這個 key**:呼叫端(fund_service:1108/1141)用
        #   `_hist_trace.get("success")` 當「真的併入了累積歷史」的閘門,設了會連帶
        #   啟動 coverage/sparse 重審 —— 那是行為變更。`merged` 才是本 trace 的語意欄。
        try:
            _first = str(s_hist.index.min())[:10]
            _last = str(s_hist.index.max())[:10]
        except Exception:  # noqa: BLE001 — 純顯示欄位,取不到不該影響取數
            _first = _last = ""
        return s_live, {
            "source": "nav_history_merge",
            "merged": False,
            "hist_points": len(s_hist),
            "hist_first": _first,
            "hist_last": _last,
            "added": 0,
            "note": (f"累積 {len(s_hist)} 點（{_first} 起）目前全部落在本次 live 序列"
                     f"（{len(s_live)} 筆）的日期範圍內 → 尚未產生淨增益。"
                     f"要等最舊的累積點掉出 live 的滾動窗，序列才會開始變長。"),
        }
    merged.attrs = dict(getattr(s_live, "attrs", {}) or {})
    merged.attrs["nav_history_merged"] = f"+{added} pts from {s_hist.attrs.get('source', 'nav_history')}"
    print(f"[nav_history] 🗂️ {code} 併入累積序列 +{added} 筆"
          f"(live {len(s_live)} → merged {len(merged)})")
    return merged, {"source": "nav_history_merge", "success": True,
                    "merged": True, "added": added,
                    "hist_points": len(s_hist),
                    "note": f"累積序列併入 +{added} 筆（live {len(s_live)} → {len(merged)}）"}


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

    # v19.360 B + v19.366 5/8:合併 nav_history 累積/匯入序列(union keep-last,live 優先)。
    # 放在 len<10 gate 之前 → 短 live 序列可被累積歷史「救回」;
    # v19.366:live **全敗**(s=None)也試 — Sheet 有累積 → 純累積序列頂上(救援),
    # status 由後續 classify_fetch_status 從內容自然升級(L1 不預寫 status,已查證)。
    _hist_trace = None
    _s_merged, _hist_trace = _merge_nav_history_series(s, code)
    if _hist_trace is not None:
        result["source_trace"].append(_hist_trace)
        if _hist_trace.get("success"):
            if s is None:
                print(f"[nav_history] 🛟 {code} live 全敗 → 純累積序列救援"
                      f"({len(_s_merged)} 筆)")
                result["source_trace"].append(
                    {"source": "nav_history_rescue", "success": True,
                     "note": f"live 全敗,改用累積序列 {len(_s_merged)} 筆"})
            s = _s_merged
            result["series"] = s
            # v19.431:併入累積序列後 series 已換成長序列 → nav_span_days 必須跟著重算,
            # 否則 UI 標頭出現「1579 筆 · 跨度 42 天」自相矛盾(§1;span 停在 pre-merge live 值)。
            # 從合併後 series 首末日直接算(純 pandas,無 I/O);日期軸異常不覆寫舊值、不炸主流程。
            try:
                if len(s) >= 2:
                    result["nav_span_days"] = int(
                        (pd.Timestamp(s.index.max()) - pd.Timestamp(s.index.min())).days)
            except Exception:  # noqa: BLE001
                pass

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

        # v19.360 ②:缺口偵測 + 誠實降級 — 只在「真的併入了累積歷史」時啟動
        #(純 live 序列走既有路,不重審 → 零回歸風險)。稀疏時**只砍自算**年化值:
        # wb07 權威值(MoneyDJ 用完整日資料算)不受我們序列稀疏影響,保留。
        if _hist_trace and _hist_trace.get("success"):
            _cov = assess_series_coverage(s)
            _m = result["metrics"]
            _m["nav_coverage"] = _cov
            if _cov["sparse"]:
                _killed = []
                for _k in ("sortino", "calmar"):        # 永遠自算 → 稀疏必砍
                    if _m.get(_k) is not None:
                        _m[_k] = None
                        _killed.append(_k)
                if _m.get("sharpe") is not None and _m.get("sharpe_source") == "self_calc":
                    _m["sharpe"] = None
                    _killed.append("sharpe")
                if _m.get("std_source") == "nav":       # 自算年化 σ → 稀疏必砍
                    for _k in ("std_1y", "std_2y", "std_3y", "std_5y"):
                        if _m.get(_k) is not None:
                            _m[_k] = None
                            _killed.append(_k)
                _m["is_sparse"] = True
                _m["sparse_reason"] = (
                    f"累積序列稀疏(覆蓋 {_cov['coverage']:.0%}、最大缺口 "
                    f"{_cov['max_gap_days']} 天)→ 年化指標不給假精確(§1):"
                    f"{', '.join(_killed) if _killed else '無自算值需砍'}")
                # P0-3:被砍的指標其 provenance meta 同步歸零 —— 否則 meta 仍宣稱
                # source="self_calc"、period_days=N 而值已是 None(§2.2 provenance 說謊)。
                _meta = _m.get("risk_metric_meta")
                if isinstance(_meta, dict):
                    for _k in _killed:
                        _e = _meta.get(_k)
                        if isinstance(_e, dict):
                            _e["source"] = None
                            _e["period_days"] = None
                            _e["period_label"] = None
                            _e["reason"] = _m["sparse_reason"]
                    if "sharpe" in _killed and isinstance(_meta.get("sharpe"), dict):
                        _meta["sharpe"]["self_calc_value"] = None
                        _meta["sharpe"]["self_calc_reason"] = _m["sparse_reason"]
                    if "sortino" in _killed or "calmar" in _killed or "sharpe" in _killed:
                        _m["sortino_source"] = ("self_calc" if _m.get("sortino") is not None else None)
                        _m["calmar_source"] = ("self_calc" if _m.get("calmar") is not None else None)
                        _m["sharpe_source"] = (_m.get("sharpe_source")
                                               if _m.get("sharpe") is not None else None)
                print(f"[nav_history] ⬜ {code} {_m['sparse_reason']}")

        # v19.308：把 MoneyDJ 現成「成立日」帶進 metrics，讓只吃 metrics 的 consumer
        #（check_333_fund / mk_dashboard 成立年）免依賴本地長 NAV 歷史即可算成立年。
        if result.get("inception_date") and isinstance(result.get("metrics"), dict):
            result["metrics"]["inception_date"] = result["inception_date"]

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


# ── v19.247 R16 EX-PASSTHRU-1 升級:get_latest_fx L2 facade ────────────────
def get_latest_fx(currency_pair: str, fred_api_key: str = "") -> "float | None":
    """v19.247 R16 EX-PASSTHRU-1 升級 — L2 service layer entry for FX。

    包裝 L1 multi-source orchestrator(`repositories.fund.get_latest_fx`)的:
    - 4 源 fallback chain(Yahoo → FRED DEX* → open.er-api → Frankfurter)
    - positive-only `_FX_CACHE` TTL_300(via `_CACHE_REGISTRY`)
    - currency normalize + `=X` 補綴 + TWD pair 特殊路徑

    R16 升級**架構意義**:UI 不再直接 import L1 fetcher,改走 L2 service 層,
    符合 §8.2 規則「L3 不得直呼 L1 — L2 wrapper 才能集中 cache」核心理由。
    本 wrapper 為 thin pass-through,L1 實作不動(保留 `diagnose_fx_sources`
    internal use + 0 行為改動風險)。EX-PASSTHRU-1 例外清單對 get_latest_fx
    條目退役(`tdcc_search_fund` / `fetch_market_news` 例外維持,規則繼續適用)。
    """
    from repositories.fund import get_latest_fx as _l1_impl
    return _l1_impl(currency_pair, fred_api_key)
