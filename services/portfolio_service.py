"""services/portfolio_service.py — 投資組合 Service Layer
（v11.0 C-14 從 portfolio_engine.py 搬入）

包含：
  1. Fund Factor Model    基金六因子評分（calc_fund_factor_score）
  2. Dividend Safety      配息安全分析（dividend_safety）
  3. Portfolio Optimizer  最大化 Sharpe 投資組合最佳化（optimize_portfolio）
  4. Risk Alert System    即時風險預警（risk_alert）
  5. Holdings Overlap     持股 Jaccard × 0.6 + 產業 cosine × 0.4 → shadow score
  6. Correlation Matrix   T5 fallback：NAV Pearson 相關係數矩陣
  7. Kelly Criterion      凱利公式計算（calc_kelly）

v11.0 分層歸位：本檔屬於 Service Layer，純業務計算。
向後相容：根目錄 portfolio_engine.py 保留 `from services.portfolio_service import *` shim，
        E 階段收尾後 shim 刪除。
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional
from shared.signal_thresholds import (  # v19.74 W2 SSOT
    SHADOW_FUND_THRESHOLD_RATIO,
    SHADOW_FUND_JACCARD_WEIGHT_RATIO,
    SHADOW_FUND_COSINE_WEIGHT_RATIO,
)
from shared.macro_thresholds_v2 import HY_SPREAD_THRESHOLDS as _HY_THR  # F-GRAY-4 v19.169

# F-GRAY-4 v19.169: HY_SPREAD portfolio_advisor SSOT (SPEC §16.2)
# 注意:warn=4.5 與 stoplight (4.0) 不同 — 投組建議更寬容
_HY_PORTFOLIO_WARN = _HY_THR["portfolio_advisor"]["warn_above"]
_HY_PORTFOLIO_RISK = _HY_THR["portfolio_advisor"]["risk_above"]

# ── scipy 可選（Optimizer 需要）────────────────────────────────────────────
try:
    from scipy.optimize import minimize
    _SCIPY_OK = True
except ImportError:
    _SCIPY_OK = False


# ══════════════════════════════════════════════════════════════════════════
# 一、Fund Factor Model — 六因子評分模型
# ══════════════════════════════════════════════════════════════════════════

def calc_fund_factor_score(fund_data: Dict,
                           risk_table: Optional[Dict] = None,
                           expense_ratio: Optional[float] = None) -> Dict:
    """
    六因子評分：Sharpe / Sortino / MaxDD / Calmar / Alpha / 費用率
    輸入：
        fund_data   : 含 perf(1Y/3Y/5Y)、metrics(max_drawdown, sharpe 等) 的 dict
        risk_table  : MoneyDJ 風險表（含 Sharpe、標準差 等）
        expense_ratio: 費用率 % (optional)
    回傳：
        {"score": 0~100, "grade": "A/B/C/D", "factors": {...}}
    """
    factors = {}
    total_w = 0.0
    total_s = 0.0

    rt = (risk_table or {}).get("一年", {}) if risk_table else {}
    m  = fund_data.get("metrics", {}) or {}
    pf = fund_data.get("perf", {}) or {}

    # ── 1. Sharpe Ratio（權重 25）──────────────────────────────────────
    sharpe = None
    try:
        sharpe = float(rt.get("Sharpe") or m.get("sharpe") or 0)
    except (TypeError, ValueError):
        sharpe = None
    if sharpe is not None:
        s = min(max((sharpe + 1) / 2 * 100, 0), 100)   # -1~+1 → 0~100
        factors["Sharpe"] = {"value": sharpe, "score": round(s, 1), "weight": 25}
        total_s += s * 25; total_w += 25

    # ── 2. Sortino Ratio（權重 15）─────────────────────────────────────
    sortino = m.get("sortino")
    if sortino is not None:
        try:
            sortino = float(sortino)
            s = min(max((sortino + 1) / 2 * 100, 0), 100)
            factors["Sortino"] = {"value": sortino, "score": round(s, 1), "weight": 15}
            total_s += s * 15; total_w += 15
        except (TypeError, ValueError):
            pass

    # ── 3. Max Drawdown（權重 20，正向：回撤越小越好）──────────────────
    maxdd = m.get("max_drawdown")
    if maxdd is None:
        try: maxdd = float((rt.get("最大回撤") or "0").replace("%", ""))
        except Exception: maxdd = None
    if maxdd is not None:
        try:
            maxdd_f = float(maxdd)
            # 0% → 100分；-30% → 0分
            s = min(max((1 - abs(maxdd_f) / 30) * 100, 0), 100)
            factors["MaxDrawdown"] = {"value": round(maxdd_f, 2), "score": round(s, 1), "weight": 20}
            total_s += s * 20; total_w += 20
        except (TypeError, ValueError):
            pass

    # ── 4. Calmar Ratio（權重 10）──────────────────────────────────────
    calmar = m.get("calmar")
    if calmar is not None:
        try:
            calmar = float(calmar)
            s = min(max(calmar / 2 * 100, 0), 100)
            factors["Calmar"] = {"value": calmar, "score": round(s, 1), "weight": 10}
            total_s += s * 10; total_w += 10
        except (TypeError, ValueError):
            pass

    # ── 5. Alpha（超額報酬，權重 20）───────────────────────────────────
    tr1y = pf.get("1Y")
    adr  = m.get("annual_div_rate", 0) or 0
    if tr1y is not None:
        try:
            alpha = float(tr1y) - float(adr)   # 真實收益 = 含息報酬 - 配息率
            s = min(max((alpha + 10) / 20 * 100, 0), 100)  # -10%~+10% → 0~100
            factors["Alpha"] = {"value": round(alpha, 2), "score": round(s, 1), "weight": 20}
            total_s += s * 20; total_w += 20
        except (TypeError, ValueError):
            pass

    # ── 6. 費用率（Expense Ratio，權重 10，越低越好）───────────────────
    er = expense_ratio or m.get("expense_ratio")
    if er is not None:
        try:
            er = float(er)
            s = min(max((3 - er) / 3 * 100, 0), 100)   # 0%→100分；3%→0分
            factors["ExpenseRatio"] = {"value": er, "score": round(s, 1), "weight": 10}
            total_s += s * 10; total_w += 10
        except (TypeError, ValueError):
            pass

    # ── 總分 ──────────────────────────────────────────────────────────
    final_score = round(total_s / total_w, 1) if total_w > 0 else 50.0
    if final_score >= 75:   grade = "A"
    elif final_score >= 55: grade = "B"
    elif final_score >= 40: grade = "C"
    else:                   grade = "D"

    return {
        "score":   final_score,
        "grade":   grade,
        "factors": factors,
        "factors_count": len(factors),
    }


# ══════════════════════════════════════════════════════════════════════════
# 二、Dividend Safety Model — 配息安全分析
# ══════════════════════════════════════════════════════════════════════════

def dividend_safety(total_return: Optional[float],
                    dividend_yield: float,
                    nav_change: Optional[float] = None) -> Dict:
    """
    配息安全分析。
    參數：
        total_return  : 含息報酬率 % (1Y)
        dividend_yield: 年化配息率 %
        nav_change    : 淨值變化率 % (可選，用於交叉驗證)
    回傳：
        {status, coverage, eating_principal, alert_level, message}

    v19.119:核心判定委派 services.fund_dividend_health.classify_eating_principal
    (output schema 100% 向後相容,5 級分類門檻保留於本 wrapper)。
    """
    # 保留 v18.x precedence:div ≤ 0 檢查優先於 missing return
    # (canonical 把 missing 視為比 no_dividend 優先,本 wrapper 為 UI 顯示需要反過來)
    if dividend_yield is not None and dividend_yield <= 0:
        return {"status": "N/A", "alert_level": "grey",
                "message": "無配息資料", "coverage": None, "eating_principal": False}

    from services.fund_dividend_health import classify_eating_principal
    core = classify_eating_principal(total_return, dividend_yield)

    if core.is_data_missing:
        return {"status": "無報酬資料", "alert_level": "grey",
                "message": "需要含息報酬率資料", "coverage": None, "eating_principal": False}
    if core.is_no_dividend:
        # 理論上不會走到(上方已先檢 div ≤ 0),保留為防禦性 fallback
        return {"status": "N/A", "alert_level": "grey",
                "message": "無配息資料", "coverage": None, "eating_principal": False}

    # 5 級分類門檻(本 wrapper UI 需求,保留)
    coverage = round(core.coverage_ratio, 4)
    eating = core.is_eating
    if coverage < 0:
        status = "🔴 嚴重吃本金（報酬為負）"
        alert  = "red"
        msg    = f"含息報酬{total_return:.1f}% < 0，配息{dividend_yield:.1f}%，本金快速流失"
    elif coverage < 1.0:
        status = "🔴 吃本金警示"
        alert  = "red"
        msg    = f"含息報酬{total_return:.1f}% < 配息{dividend_yield:.1f}%，覆蓋率{coverage:.2f}"
    elif coverage < 1.2:
        status = "🟡 邊緣（建議觀察）"
        alert  = "yellow"
        msg    = f"覆蓋率{coverage:.2f}，略高於1但空間不足，需觀察淨值趨勢"
    else:
        status = "🟢 健康"
        alert  = "green"
        msg    = f"含息報酬{total_return:.1f}% 充分覆蓋配息{dividend_yield:.1f}%，覆蓋率{coverage:.2f}"

    # 淨值交叉驗證(本 wrapper 獨有)
    nav_warn = None
    if nav_change is not None and nav_change < -5:
        nav_warn = f"⚠️ 淨值下跌{nav_change:.1f}%，配息源頭值得確認"

    return {
        "status":          status,
        "alert_level":     alert,
        "coverage":        coverage,
        "eating_principal": eating,
        "message":         msg,
        "nav_warning":     nav_warn,
    }


# ══════════════════════════════════════════════════════════════════════════
# 三、Portfolio Optimizer — 最大化 Sharpe 投資組合最佳化
# ══════════════════════════════════════════════════════════════════════════

def optimize_portfolio(returns_df: pd.DataFrame,
                       rf: float = 0.02,
                       max_weight: float = 0.6,
                       min_weight: float = 0.0) -> Dict:
    """
    最大化 Sharpe Ratio 最佳化投資組合。
    參數：
        returns_df : 各基金月報酬率 DataFrame (列=時間, 欄=基金)
        rf         : 無風險利率（年化）
        max_weight : 單一資產最大權重
        min_weight : 單一資產最小權重
    回傳：
        {weights, expected_return, expected_vol, expected_sharpe, status}
    """
    if not _SCIPY_OK:
        return {"status": "❌ 需要安裝 scipy：pip install scipy",
                "weights": None}

    n = len(returns_df.columns)
    if n < 2:
        return {"status": "❌ 需要至少 2 檔基金", "weights": None}

    mean_ret  = returns_df.mean() * 12              # 年化報酬
    cov_matrix = returns_df.cov() * 12              # 年化共變異數

    # ── 目標函數：最大化 Sharpe（最小化負 Sharpe）────────────────────
    def neg_sharpe(w):
        port_ret = float(w @ mean_ret)
        port_vol = float(np.sqrt(w @ cov_matrix.values @ w))
        if port_vol <= 0:
            return 0.0
        return -(port_ret - rf) / port_vol

    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]
    bounds      = [(min_weight, max_weight)] * n
    w0          = np.ones(n) / n

    try:
        res = minimize(neg_sharpe, w0, method="SLSQP",
                       bounds=bounds, constraints=constraints,
                       options={"maxiter": 500, "ftol": 1e-9})
        if not res.success:
            # fallback：等權
            opt_w = np.ones(n) / n
            status = "⚠️ 最佳化未收斂，回退等權配置"
        else:
            opt_w  = res.x
            status = "✅ 最佳化成功"
    except Exception as e:
        opt_w  = np.ones(n) / n
        status = f"❌ 最佳化失敗：{e}"

    weights_dict = {col: round(float(w), 4)
                    for col, w in zip(returns_df.columns, opt_w)}
    exp_ret = float(opt_w @ mean_ret)
    exp_vol = float(np.sqrt(opt_w @ cov_matrix.values @ opt_w))
    exp_shp = round((exp_ret - rf) / exp_vol, 4) if exp_vol > 0 else 0.0

    return {
        "status":            status,
        "weights":           weights_dict,
        "expected_return":   round(exp_ret * 100, 2),
        "expected_vol":      round(exp_vol * 100, 2),
        "expected_sharpe":   exp_shp,
    }


# ══════════════════════════════════════════════════════════════════════════
# 四、Risk Alert System — 即時風險預警
# ══════════════════════════════════════════════════════════════════════════

def risk_alert(drawdown:       Optional[float] = None,
               coverage:       Optional[float] = None,
               regime:         str = "",
               fed_direction:  str = "",
               hy_spread:      Optional[float] = None,
               vix:            Optional[float] = None) -> List[Dict]:
    """
    即時風險預警系統。
    參數（均可選）：
        drawdown      : 最大回撤（負值，e.g. -0.25）
        coverage      : 配息覆蓋率（<1 吃本金）
        regime        : 景氣循環標籤
        fed_direction : 'up' 升息 / 'down' 降息 / ''
        hy_spread     : HY 信用利差 %
        vix           : VIX 恐慌指數
    回傳：
        [{"level": "red/yellow/green", "type": str, "message": str}]
    """
    alerts = []

    # ── 最大回撤 ──────────────────────────────────────────────────────
    if drawdown is not None:
        if drawdown < -0.30:
            alerts.append({"level": "red",    "type": "MaxDrawdown",
                           "message": f"🔴 最大回撤 {drawdown*100:.1f}%，已超過 30% 高危門檻，建議減碼"})
        elif drawdown < -0.20:
            alerts.append({"level": "yellow", "type": "MaxDrawdown",
                           "message": f"🟡 最大回撤 {drawdown*100:.1f}%，接近 20% 警戒線，持續觀察"})

    # ── 配息覆蓋率 ─────────────────────────────────────────────────────
    if coverage is not None:
        if coverage < 1.0:
            alerts.append({"level": "red",    "type": "DividendRisk",
                           "message": f"🔴 配息覆蓋率 {coverage:.2f} < 1，正在吃本金，考慮汰換"})
        elif coverage < 1.2:
            alerts.append({"level": "yellow", "type": "DividendRisk",
                           "message": f"🟡 配息覆蓋率 {coverage:.2f}，邊緣狀態，需監控淨值趨勢"})

    # ── 景氣衰退 ───────────────────────────────────────────────────────
    if "衰退" in regime:
        alerts.append({"level": "red",    "type": "RegimeAlert",
                       "message": "🔴 景氣衰退期：建議降低股票型比重，增加投資等級債 / 貨幣型"})
    elif "過熱" in regime:
        alerts.append({"level": "yellow", "type": "RegimeAlert",
                       "message": "🟡 景氣過熱期：注意通膨壓力，降低久期，減少高收益債"})

    # ── 升息 ───────────────────────────────────────────────────────────
    if fed_direction == "up":
        alerts.append({"level": "yellow", "type": "RateAlert",
                       "message": "🟡 升息環境：降低長久期債券，避免利率風險"})

    # ── HY 信用利差擴大 ────────────────────────────────────────────────
    if hy_spread is not None and hy_spread > _HY_PORTFOLIO_RISK:
        alerts.append({"level": "red",    "type": "CreditSpread",
                       "message": f"🔴 HY 利差 {hy_spread:.2f}%，市場避險情緒高，減少非投資等級債"})
    elif hy_spread is not None and hy_spread > _HY_PORTFOLIO_WARN:
        alerts.append({"level": "yellow", "type": "CreditSpread",
                       "message": f"🟡 HY 利差 {hy_spread:.2f}%，信用風險升高，保持謹慎"})

    # ── VIX 恐慌 ───────────────────────────────────────────────────────
    if vix is not None and vix > 35:
        alerts.append({"level": "red",    "type": "VIXAlert",
                       "message": f"🔴 VIX {vix:.1f} 極度恐慌，可能是逢低加碼機會（需搭配其他確認）"})
    elif vix is not None and vix > 25:
        alerts.append({"level": "yellow", "type": "VIXAlert",
                       "message": f"🟡 VIX {vix:.1f} 恐慌升高，市場波動加劇，縮短操作週期"})

    # ── 無警示 ─────────────────────────────────────────────────────────
    if not alerts:
        alerts.append({"level": "green", "type": "AllClear",
                       "message": "✅ 目前無重大風險預警，維持現有配置"})

    return alerts




def calc_holdings_overlap(funds_data: list) -> "dict | None":
    """T5 新版：以「底層持股 Jaccard + 產業 cosine」為主、NAV pearson 為 fallback。

    輸入：
        [{
            "code":         str,
            "name":         str (optional),
            "top_holdings": [{"name": str, "pct": float}, ...]   # 持股名稱 + 占比 %
            "sector_alloc": [{"name": str, "pct": float}, ...]   # 產業 + 占比 %
        }, ...]

    輸出：
        {
            "matrix":       pd.DataFrame[code × code],   # 0~1 重疊度
            "shadow_pairs": [(codeA, codeB, score), ...],
            "method":       "holdings" | "sector" | "hybrid" | "n/a",
            "notes":        str
        }

    閾值：score >= SHADOW_FUND_THRESHOLD_RATIO (0.70) → shadow（持股+產業都很像 = 影子基金 / 集中度過高）
    公式：score = jaccard_holdings × SHADOW_FUND_JACCARD_WEIGHT_RATIO + cosine_sector × SHADOW_FUND_COSINE_WEIGHT_RATIO
    （W5-3 §3.3:weights 已 SSOT 化於 shared/signal_thresholds.py,本 docstring 對應 v19.74 W2 落地）

    任一基金缺持股或產業資料 → 該對改用單獨可得的維度；皆缺 → score = 0、不入 shadow。
    """
    try:
        import numpy as np
    except Exception as _e_np:
        # F-MED v19.170: silent → stderr log
        import sys as _sys_np
        print(f'[portfolio_service/calc_shadow_score] numpy missing: {type(_e_np).__name__}: {_e_np}', file=_sys_np.stderr)
        return None

    # 整理資料：建 holdings set（由名稱代表）與 sector vector（dict 名稱→pct）
    rows = []
    for f in funds_data:
        code = f.get("code") or "?"
        tops = f.get("top_holdings") or []
        sects = f.get("sector_alloc") or []
        h_names = {(h.get("name") or "").strip().upper() for h in tops if h.get("name")}
        s_dict = {}
        for s in sects:
            name = (s.get("name") or "").strip().upper()
            try: pct = float(s.get("pct", 0) or 0)
            except Exception: pct = 0.0
            if name and pct > 0: s_dict[name] = s_dict.get(name, 0.0) + pct
        rows.append({"code": code, "h": h_names, "s": s_dict,
                     "has_h": bool(h_names), "has_s": bool(s_dict)})

    if len(rows) < 2:
        return None
    if not any(r["has_h"] or r["has_s"] for r in rows):
        return {"matrix": None, "shadow_pairs": [], "method": "n/a",
                "notes": "所有基金皆缺持股 / 產業資料，無法計算 holdings 重疊"}

    codes = [r["code"] for r in rows]
    n = len(codes)
    M = np.eye(n)  # 對角=1
    for i in range(n):
        for j in range(i + 1, n):
            ri, rj = rows[i], rows[j]
            # Jaccard on holdings name set
            j_score = None
            if ri["has_h"] and rj["has_h"]:
                inter = len(ri["h"] & rj["h"])
                union = len(ri["h"] | rj["h"])
                j_score = (inter / union) if union > 0 else 0.0
            # Cosine on sector vectors
            c_score = None
            if ri["has_s"] and rj["has_s"]:
                keys = list(set(ri["s"]) | set(rj["s"]))
                a = np.array([ri["s"].get(k, 0.0) for k in keys])
                b = np.array([rj["s"].get(k, 0.0) for k in keys])
                na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
                c_score = float(np.dot(a, b) / (na * nb)) if (na > 0 and nb > 0) else 0.0
            # 綜合
            if j_score is not None and c_score is not None:
                v = j_score * SHADOW_FUND_JACCARD_WEIGHT_RATIO + c_score * SHADOW_FUND_COSINE_WEIGHT_RATIO
            elif j_score is not None:
                v = j_score
            elif c_score is not None:
                v = c_score
            else:
                v = 0.0
            M[i, j] = M[j, i] = round(v, 4)

    # 決定 method 標籤
    all_h = all(r["has_h"] for r in rows)
    all_s = all(r["has_s"] for r in rows)
    if all_h and all_s: method = "hybrid"
    elif all_h:         method = "holdings"
    elif all_s:         method = "sector"
    else:               method = "partial"

    matrix = pd.DataFrame(M, index=codes, columns=codes)
    shadow_pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            v = float(M[i, j])
            if v >= SHADOW_FUND_THRESHOLD_RATIO:
                shadow_pairs.append((codes[i], codes[j], round(v, 4)))
    shadow_pairs.sort(key=lambda x: -x[2])
    notes = (f"method={method}；jaccard(holdings) × {SHADOW_FUND_JACCARD_WEIGHT_RATIO} + "
             f"cosine(sector) × {SHADOW_FUND_COSINE_WEIGHT_RATIO}；shadow 門檻 = {SHADOW_FUND_THRESHOLD_RATIO}")
    return {"matrix": matrix, "shadow_pairs": shadow_pairs,
            "method": method, "notes": notes}


def calc_correlation_matrix(funds_data: list) -> "dict | None":
    """
    T5 fallback：NAV Pearson 相關係數矩陣（持股資料不可得時備用）。
    輸入: [{"code": str, "series": pd.Series}, ...]
    回傳: {"matrix": pd.DataFrame, "shadow_pairs": [(codeA, codeB, corr), ...], "freq": str}
    相關係數 > 0.85 → 影子基金警告

    v18.177: 自適應頻率 — 短 NAV（卡 ~30 天 fallback）月底 resample 只剩 1-2 點
             → pct_change 僅 1 個 return → 相關係數退化成 NaN（顯示成 0），
             造成「同台股基金相關係數=0」假象。改月→週→日逐級降頻，挑第一個
             return 列數 ≥6 的最粗頻率；都不足時退到日頻（點數最多）。
    """
    try:
        import numpy as np
        valid = [(f["code"], f["series"]) for f in funds_data
                 if f.get("series") is not None and len(f["series"]) >= 30]
        if len(valid) < 2:
            return None

        def _returns_at(freq):
            if freq is None:
                cols = {code: s.sort_index() for code, s in valid}
            else:
                cols = {code: s.sort_index().resample(freq).last() for code, s in valid}
            df = pd.concat(cols, axis=1).dropna(how="all")
            return df.pct_change().dropna(how="all")

        # 月→週→日：挑第一個 return 列數 ≥6 的最粗頻率；都 <6 則用日頻（最 granular）
        _MIN_ROWS = 6
        rets, freq_label = None, "日頻"
        for _freq, _lbl in (("ME", "月底"), ("W-FRI", "週末"), (None, "日頻")):
            rets, freq_label = _returns_at(_freq), _lbl
            if len(rets) >= _MIN_ROWS:
                break

        if rets is None or len(rets) < 2:
            return None

        corr = rets.corr()
        shadow_pairs = []
        codes = list(corr.columns)
        for i in range(len(codes)):
            for j in range(i + 1, len(codes)):
                v = corr.iloc[i, j]
                if not np.isnan(v) and abs(v) >= 0.85:
                    shadow_pairs.append((codes[i], codes[j], round(float(v), 4)))
        shadow_pairs.sort(key=lambda x: -abs(x[2]))
        return {"matrix": corr, "shadow_pairs": shadow_pairs, "freq": freq_label}
    except Exception as _e_corr:
        # F-MED v19.170: silent → stderr log
        import sys as _sys_corr
        print(f'[portfolio_service/calc_correlation_matrix] fail: {type(_e_corr).__name__}: {_e_corr}', file=_sys_corr.stderr)
        return None


def _safe_num_ps(v) -> "float | None":
    """寬鬆數值轉換(portfolio_service 內用):float / "12.3%" / "1,234" / None → float|None。"""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        f = float(v)
    else:
        try:
            f = float(str(v).replace("%", "").replace(",", "").strip())
        except (TypeError, ValueError):
            return None
    if f != f or f in (float("inf"), float("-inf")):  # NaN / inf guard
        return None
    return f


def compute_max_drawdown(series: "pd.Series") -> "dict":
    """單一基金最大回撤(從 NAV 序列算)。

    定義(§4.1 量綱:回撤為負值 %,代表自前高的最大跌幅):
        drawdown_t = (NAV_t − running_max(NAV_≤t)) / running_max(NAV_≤t) × 100
        max_drawdown = min_t(drawdown_t)   # 最深(最負)的一點

    Args
    ----
    series: pd.Series(index=date, value=NAV),原幣計價即可(回撤為相對值,不需換匯)

    Returns
    -------
    {
      "max_dd_pct": float|None,    # 最大回撤 %(≤ 0;-15.0 表最深跌 15%)
      "peak_date":  str|None,      # 回撤起算的前高日期
      "trough_date":str|None,      # 回撤最深谷底日期
      "n_obs":      int,           # 有效 NAV 筆數
    }
    §1 Fail Loud:資料不足回 None 欄位 + n_obs,不偽造 0。
    """
    _empty = {"max_dd_pct": None, "peak_date": None, "trough_date": None, "n_obs": 0}
    if series is None:
        return _empty
    try:
        s = series.dropna().sort_index()
    except Exception:
        return _empty
    n = len(s)
    if n < 2:
        return {**_empty, "n_obs": n}
    # NAV 必為正(§3.2);非正值視為無效資料,Fail Loud 回 None
    if (s <= 0).any():
        return {**_empty, "n_obs": n}

    running_max = s.cummax()
    dd = (s - running_max) / running_max * 100.0
    trough_pos = int(dd.values.argmin())
    max_dd = float(dd.iloc[trough_pos])
    trough_date = str(s.index[trough_pos])[:10]
    # 谷底前的 running_max 對應的前高日期
    peak_nav = float(running_max.iloc[trough_pos])
    _peak_slice = s.iloc[: trough_pos + 1]
    _peak_hits = _peak_slice[_peak_slice >= peak_nav]
    peak_date = str(_peak_hits.index[0])[:10] if len(_peak_hits) else None
    return {
        "max_dd_pct": round(max_dd, 4),
        "peak_date": peak_date,
        "trough_date": trough_date,
        "n_obs": n,
    }


def compute_portfolio_drawdown(funds_data: list,
                               weights: "dict | None" = None) -> "dict":
    """組合加權最大回撤 + 各年度報酬(把持倉權重套到各基金 NAV 後合成組合指數)。

    方法(§4.1 / §4.5):
      1. 各檔 NAV 對齊到共同交易日(outer join),**禁止 ffill 偽造**週末值,
         以 inner-join(全員都有報價的日)避免缺值汙染合成指數。
      2. 各檔正規化:nav / nav[第一個共同日] = 累積淨值倍數(起點=1.0)。
      3. 組合指數 = Σ weight_i × 正規化_i(weight 缺則等權)。
      4. max_drawdown(組合指數)+ 各年度(YE resample)報酬。

    Args
    ----
    funds_data: [{"code": str, "series": pd.Series}, ...]
    weights: {code: weight} 權重(可不歸一,函式內歸一);None → 等權

    Returns
    -------
    {
      "max_dd_pct": float|None,         # 組合最大回撤 %
      "peak_date": str|None, "trough_date": str|None,
      "yearly_returns": {year:int → ret_pct:float},  # 各年度報酬 %
      "n_funds": int,                   # 納入合成的基金數
      "n_obs": int,                     # 共同交易日筆數
      "aligned_freq": str,              # "daily"(共同日 inner-join)
      "note": str|None,                 # 降級/警示說明
    }
    §1 Fail Loud:< 1 檔有效 / 共同日 < 2 → None 欄位 + note,不偽造。
    """
    _empty = {
        "max_dd_pct": None, "peak_date": None, "trough_date": None,
        "yearly_returns": {}, "n_funds": 0, "n_obs": 0,
        "aligned_freq": "daily", "note": None,
    }
    valid = [(f.get("code"), f.get("series")) for f in (funds_data or [])
             if f.get("series") is not None and len(f.get("series")) >= 2]
    if not valid:
        return {**_empty, "note": "無有效 NAV 序列"}

    try:
        cols = {}
        for code, s in valid:
            ss = s.dropna().sort_index()
            ss = ss[ss > 0]  # NAV 必正(§3.2),非正值丟棄
            if len(ss) >= 2 and not ss.index.has_duplicates:
                cols[code] = ss
            elif len(ss) >= 2:
                cols[code] = ss[~ss.index.duplicated(keep="last")]
        if not cols:
            return {**_empty, "note": "NAV 全為非正或重複"}

        df = pd.concat(cols, axis=1)
        # inner-join:只取全員都有報價的交易日(避免缺值用 0 / ffill 汙染)
        df_inner = df.dropna(how="any")
        n_funds = df_inner.shape[1]
        n_obs = df_inner.shape[0]
        if n_obs < 2:
            return {**_empty, "n_funds": n_funds,
                    "note": "共同交易日不足 2 筆(各基金歷史重疊太少)"}

        # 權重歸一(缺則等權)
        codes = list(df_inner.columns)
        if weights:
            w_raw = {c: _safe_num_ps(weights.get(c)) for c in codes}
            w_clean = {c: (v if (v is not None and v > 0) else 0.0)
                       for c, v in w_raw.items()}
            w_sum = sum(w_clean.values())
            if w_sum <= 0:
                w_norm = {c: 1.0 / len(codes) for c in codes}
                _wnote = "權重全缺 → 等權"
            else:
                w_norm = {c: w_clean[c] / w_sum for c in codes}
                _wnote = None
        else:
            w_norm = {c: 1.0 / len(codes) for c in codes}
            _wnote = None

        # 正規化各檔(起點=1.0)→ 加權合成組合指數
        norm = df_inner / df_inner.iloc[0]
        port_index = sum(norm[c] * w_norm[c] for c in codes)

        _dd = compute_max_drawdown(port_index)

        # 各年度報酬(YE resample 右閉,§4.5 不引入未來)
        # 首年以「首筆 NAV」為基準(部分年報酬,標 partial);其後以前一年底為基準。
        yearly = {}
        try:
            ye = port_index.resample("YE").last()
            prev = float(port_index.iloc[0])  # 首年基準 = 起點(已正規化為 1.0)
            for ts, val in ye.items():
                yr = ts.year
                if prev is not None and prev > 0:
                    yearly[yr] = round((val / prev - 1.0) * 100.0, 2)
                prev = val
        except Exception as _e_yr:
            import sys as _sys_yr
            print(f"[portfolio_service/compute_portfolio_drawdown] yearly fail: {type(_e_yr).__name__}: {_e_yr}", file=_sys_yr.stderr)

        return {
            "max_dd_pct": _dd["max_dd_pct"],
            "peak_date": _dd["peak_date"],
            "trough_date": _dd["trough_date"],
            "yearly_returns": yearly,
            "n_funds": n_funds,
            "n_obs": n_obs,
            "aligned_freq": "daily",
            "note": _wnote,
        }
    except Exception as _e_pdd:
        import sys as _sys_pdd
        print(f"[portfolio_service/compute_portfolio_drawdown] fail: {type(_e_pdd).__name__}: {_e_pdd}", file=_sys_pdd.stderr)
        return {**_empty, "note": f"計算失敗 [{type(_e_pdd).__name__}]"}


def rank_funds_within_portfolio(funds_data: list) -> "dict":
    """組內排名 + 同類 percentile(供組合基金摘要表「費用率排名 / 同性質排名」用)。

    兩種排名(user 2026-06-27 決策「兩者都要」):
      A. **組內排名**(intra-portfolio):在 user 載入的這幾檔之間排,純函式可算
         - 費用率排名:mgmt_fee 越低越好(第 1 名 = 最便宜)
         - 報酬排名:1Y 含息越高越好(第 1 名 = 最強)
      B. **同類 percentile**:從 MoneyDJ peer_compare「同類排名」欄萃取(已抓資料,
         不新增 fetch);格式多為 "12/45" → percentile = 1 - (12-1)/(45-1)。
         缺資料 → None(§1 Fail Loud,不偽造)。

    Args
    ----
    funds_data: [{"code","name","moneydj_raw":{mgmt_fee, risk_metrics:{peer_compare}},
                  "metrics":{...}}, ...]
                報酬取值與 fund_checkup 同源(MoneyDJ perf 1Y → metrics fallback)。

    Returns
    -------
    {code: {
      "expense_rank": int|None, "expense_n": int,     # 組內費用率名次 / 樣本數
      "return_rank": int|None,  "return_n": int,      # 組內 1Y 報酬名次 / 樣本數
      "peer_percentile": float|None,                  # 同類 percentile(0~100,越高越強)
      "peer_rank_raw": str|None,                      # 原始 "12/45" 供顯示
    }}
    """
    funds = [f for f in (funds_data or []) if f.get("code")]
    if not funds:
        return {}

    def _expense(f):
        return _safe_num_ps((f.get("moneydj_raw") or {}).get("mgmt_fee"))

    def _ret1y(f):
        mj = f.get("moneydj_raw") or {}
        v = _safe_num_ps((mj.get("perf") or {}).get("1Y"))
        if v is not None:
            return v
        m = f.get("metrics") or {}
        for k in ("ret_1y_total", "ret_1y"):
            v = _safe_num_ps(m.get(k))
            if v is not None:
                return v
        return None

    # A. 組內排名(只在「有該指標」的子集合內排名,缺值不參與)
    _exp_pairs = [(f["code"], _expense(f)) for f in funds]
    _exp_have = [(c, v) for c, v in _exp_pairs if v is not None]
    # 費用率:升序(低=第1名)
    _exp_sorted = sorted(_exp_have, key=lambda x: x[1])
    _exp_rank = {c: i + 1 for i, (c, _) in enumerate(_exp_sorted)}
    _exp_n = len(_exp_have)

    _ret_pairs = [(f["code"], _ret1y(f)) for f in funds]
    _ret_have = [(c, v) for c, v in _ret_pairs if v is not None]
    # 報酬:降序(高=第1名)
    _ret_sorted = sorted(_ret_have, key=lambda x: -x[1])
    _ret_rank = {c: i + 1 for i, (c, _) in enumerate(_ret_sorted)}
    _ret_n = len(_ret_have)

    # B. 同類 percentile（從 peer_compare 萃取 "x/y" 名次）
    import re as _re

    def _peer(f):
        mj = f.get("moneydj_raw") or {}
        peer = ((mj.get("risk_metrics") or {}).get("peer_compare")) or {}
        # 找含「排名」的 row / value
        for _k, _row in peer.items():
            if not isinstance(_row, dict):
                continue
            for _col, _val in _row.items():
                if "排名" in str(_col):
                    _m = _re.search(r"(\d+)\s*/\s*(\d+)", str(_val))
                    if _m:
                        rank_i, total = int(_m.group(1)), int(_m.group(2))
                        if total >= 2 and 1 <= rank_i <= total:
                            # percentile：第1名=100,最後一名 → 接近 0
                            pct = (1.0 - (rank_i - 1) / (total - 1)) * 100.0
                            return round(pct, 1), f"{rank_i}/{total}"
        return None, None

    out = {}
    for f in funds:
        c = f["code"]
        _pp, _praw = _peer(f)
        out[c] = {
            "expense_rank": _exp_rank.get(c),
            "expense_n": _exp_n,
            "return_rank": _ret_rank.get(c),
            "return_n": _ret_n,
            "peer_percentile": _pp,
            "peer_rank_raw": _praw,
        }
    return out


def calc_kelly(series: "pd.Series",
               lookback: int = 252,
               risk_free: float = 0.02) -> Dict:
    """
    凱利公式：根據歷史日報酬計算最佳資金投入比例
    - b  = 平均獲利日 / 平均虧損日  (賠率)
    - p  = 正報酬日佔比              (勝率)
    - q  = 1 - p                     (敗率)
    - f* = (b*p - q) / b             (全凱利)
    - Half-Kelly = f*/2              (建議實用值)
    邊界保護：f* 超過 1 時夾在 [0, 1]
    """
    if series is None or len(series) < 30:
        return {"kelly": None, "half_kelly": None,
                "win_rate": None, "odds": None, "note": "資料不足"}
    try:
        import numpy as np
        s = series.tail(lookback).dropna()
        if len(s) < 30:
            return {"kelly": None, "half_kelly": None,
                    "win_rate": None, "odds": None, "note": "資料不足"}
        r = s.pct_change().dropna()
        wins  = r[r > 0]
        losses= r[r < 0]
        if len(wins) == 0 or len(losses) == 0:
            return {"kelly": None, "half_kelly": None,
                    "win_rate": None, "odds": None, "note": "無法計算"}
        p  = len(wins) / len(r)
        q  = 1 - p
        b      = wins.mean() / abs(losses.mean())     # 賠率
        _f_raw = (b * p - q) / b                     # 全凱利（未夾取，負值代表期望值為負）
        f_star = float(np.clip(_f_raw, 0, 1))        # 夾在 [0,1]
        half_k = round(f_star / 2, 4)
        return {
            "kelly":          round(f_star, 4),
            "kelly_raw":      round(_f_raw, 4),   # 負值代表數學期望為負
            "half_kelly":     half_k,
            "half_kelly_pct": round(half_k * 100, 1),
            "win_rate":       round(p, 4),
            "win_rate_pct":   round(p * 100, 1),
            "odds":           round(b, 4),
            "note": (
                f"勝率{p*100:.1f}% 賠率{b:.2f}x → 建議投入{half_k*100:.1f}%資金"
                if f_star > 0 else
                f"勝率{p*100:.1f}% 賠率{b:.2f}x，期望值為負(f*={_f_raw:.3f})，建議不加碼"
            ),
        }
    except Exception as e:
        return {"kelly": None, "half_kelly": None,
                "win_rate": None, "odds": None, "note": str(e)[:60]}
