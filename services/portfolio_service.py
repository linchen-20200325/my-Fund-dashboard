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
    # v19.176:max_dd 值本身為 SSOT(fund_service.py:519 calc_metrics 內自算),
    # 本層只負責「拿 max_dd 套線性評分」。fallback 走 risk_tbl 為次源。
    # 0 → score=100 / MAX_DRAWDOWN_ZERO_SCORE_PCT(-30%)→ score=0。
    from shared.signal_thresholds import MAX_DRAWDOWN_ZERO_SCORE_PCT
    maxdd = m.get("max_drawdown")
    if maxdd is None:
        try: maxdd = float((rt.get("最大回撤") or "0").replace("%", ""))
        except Exception: maxdd = None
    if maxdd is not None:
        try:
            maxdd_f = float(maxdd)
            s = min(max(
                (1 - abs(maxdd_f) / abs(MAX_DRAWDOWN_ZERO_SCORE_PCT)) * 100, 0
            ), 100)
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
        {status, coverage, gap_pct, eating_principal, alert_level, message}

    v19.119:核心判定委派 services.fund_dividend_health.classify_eating_principal。
    v19.175:5 級 coverage 門檻 → 3 色 gap_pct > 2% 制(對齊 MK 老師「化繁為簡」),
            與健診總表 `div_health_light_for_pair()` SSOT 同源。
            「嚴重吃本金(報酬為負)」獨立旗標保留為「報酬為負」修飾,
            主分類仍走 3 色。output schema 向後相容:coverage / eating_principal
            欄位保留,新增 gap_pct 欄位。
    """
    # 保留 v18.x precedence:div ≤ 0 檢查優先於 missing return
    if dividend_yield is not None and dividend_yield <= 0:
        return {"status": "N/A", "alert_level": "grey",
                "message": "無配息資料", "coverage": None, "gap_pct": None,
                "eating_principal": False}

    from services.fund_dividend_health import classify_eating_principal
    core = classify_eating_principal(total_return, dividend_yield)

    if core.is_data_missing:
        return {"status": "無報酬資料", "alert_level": "grey",
                "message": "需要含息報酬率資料",
                "coverage": None, "gap_pct": None, "eating_principal": False}
    if core.is_no_dividend:
        return {"status": "N/A", "alert_level": "grey",
                "message": "無配息資料",
                "coverage": None, "gap_pct": None, "eating_principal": False}

    # v19.175:3 色制 gap_pct 門檻 — 與 fund_dividend_calculator.div_health_light_for_pair
    # 完全同源(都委派 classify_eating_principal 的 core.gap_pct),對齊「化繁為簡」MK 原則。
    from shared.signal_thresholds import NEAR_DIVIDEND_WARNING_PCT
    coverage = round(core.coverage_ratio, 4)
    gap_pct = round(core.gap_pct, 4)  # = div - ret;正 = 吃本金深度
    eating = core.is_eating

    if gap_pct <= 0:
        status = "🟢 健康"
        alert = "green"
        msg = (f"含息報酬{total_return:.1f}% 充分覆蓋配息{dividend_yield:.1f}%,"
               f"覆蓋率{coverage:.2f}")
    elif gap_pct <= NEAR_DIVIDEND_WARNING_PCT:
        status = "🟡 警示"
        alert = "yellow"
        msg = (f"含息報酬{total_return:.1f}% 略低於配息{dividend_yield:.1f}%,"
               f"缺口{gap_pct:.1f}pp(警戒線{NEAR_DIVIDEND_WARNING_PCT:.0f}pp 內,建議觀察)")
    else:
        # 嚴重吃本金(報酬為負)獨立修飾
        if total_return is not None and total_return < 0:
            status = "🔴 嚴重吃本金(報酬為負)"
            msg = (f"含息報酬{total_return:.1f}% < 0,配息{dividend_yield:.1f}%,"
                   f"缺口{gap_pct:.1f}pp,本金快速流失")
        else:
            status = "🔴 吃本金"
            msg = (f"含息報酬{total_return:.1f}% < 配息{dividend_yield:.1f}%,"
                   f"缺口{gap_pct:.1f}pp,長期將侵蝕本金")
        alert = "red"

    # 淨值交叉驗證(本 wrapper 獨有,獨立輔助警示)
    # v19.176:-5% 門檻收 shared/signal_thresholds.NAV_DROP_WARNING_PCT SSOT
    from shared.signal_thresholds import NAV_DROP_WARNING_PCT
    nav_warn = None
    if nav_change is not None and nav_change < NAV_DROP_WARNING_PCT:
        nav_warn = f"⚠️ 淨值下跌{nav_change:.1f}%,配息源頭值得確認"

    return {
        "status":          status,
        "alert_level":     alert,
        "coverage":        coverage,
        "gap_pct":         gap_pct,
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

    **v19.176 SSOT WRITER 公告**:本函式為「**影子基金相似度**」計算 SSOT。
    所有 UI 顯示「影子基金 / 持股重疊度」一律走本入口,不可在 UI 端自算 jaccard /
    cosine / pearson。caller(`ui/tab3_portfolio.py:2049-2074`、
    `ui/helpers/fund_grp_health_extras.py:515-517`)透過本函式取 matrix + shadow_pairs。


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
