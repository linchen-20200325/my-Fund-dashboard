"""services/rotation.py — 輪動配對建議(賣高基期 → 買低基期健康標的)v19.415。

均值回歸輪動:把「貼近高點(高基期)」的基金,配對換進「深跌但體質健康(低基期)」的
**同類**基金,賺回歸差價;等買進的漲回高基期再換。純函式:輸入每檔已算好的
σ rank / 基金類別 / 4D Grade / 吃本金燈號 / 操盤評分 / 距 HWM %,輸出配對建議。

§1 誠實:低基期 **≠ 一定回漲**(可能是價值陷阱/接刀)—— 買方**必須通過健康過濾**
(4D ≠ F + 吃本金非吃本金 + 操盤評分 ≥ 門檻)才推薦;無合適配對 → 回空,不硬湊。
σ rank = 現價在期間高點下方第幾個 σ(負值愈深愈低基期),已標準化無量綱陷阱。
"""
from __future__ import annotations


def _num(v):
    from shared.converters import safe_num
    return safe_num(v)


def _sigma(v):
    """σ rank 顯示字串(如 '-2.00σ')→ 數值。先去 'σ' 再 safe_num。"""
    if v is None:
        return None
    return _num(str(v).replace("σ", "").strip())


def classify_base(sigma_rank, sell_sigma: float = -0.5, buy_sigma: float = -1.5) -> str:
    """依 σ rank 分基期:high(≥ sell_sigma,貼近高點=賣)/ low(≤ buy_sigma,深跌=買)/ mid / unknown。"""
    v = _sigma(sigma_rank)
    if v is None:
        return "unknown"
    if v >= sell_sigma:
        return "high"
    if v <= buy_sigma:
        return "low"
    return "mid"


def is_healthy_buy(row: dict, min_score: float = 50.0) -> bool:
    """買方健康過濾 —— **fail-closed**:必須有明確健康訊號才推薦(§1 避免把「資料不足」
    當健康 → 接刀)。條件:4D Grade 為明確好評等(A/B/C)+ 吃本金燈號為明確健康燈
    (🟢/🟡,非吃本金、非空/資料不足)+ 操盤評分若有值須達門檻(缺值不硬擋,因短歷史常缺)。
    """
    r = row or {}
    _grade = str(r.get("4D Grade") or "").strip().upper()
    if _grade not in ("A", "B", "C"):        # D/F/缺(—/空)→ 擋(不推無把握的)
        return False
    _eat = str(r.get("吃本金燈號") or "")
    if ("吃本金" in _eat) or not ("🟢" in _eat or "🟡" in _eat):  # 需明確健康燈;空/資料不足 → 擋
        return False
    _sc = _num(r.get("操盤評分"))
    if _sc is not None and _sc < min_score:  # 操盤評分有值才要求達標(缺值 = 短歷史,已由上兩項把關)
        return False
    return True


def revert_upside_pct(dist_hwm_pct) -> "float | None":
    """距 HWM %(負)→ 回到期間高點的潛在漲幅%。例:−15% → +17.6%。非負/缺 → None。"""
    d = _num(dist_hwm_pct)
    if d is None or d >= 0 or d <= -100:      # d<=-100 → 分母 0(清算基金 NAV=0)→ None,不除零
        return None
    return round(-d / (1.0 + d / 100.0), 1)


def suggest_rotation_pairs(fund_rows, sell_sigma: float = -0.5, buy_sigma: float = -1.5,
                           min_score: float = 50.0) -> list:
    """回傳配對建議 list[dict](每個高基期賣方一列;配**不同**基金類別最深跌的健康買方)。

    **跨產業/性質輪動**:賣掉某類別的高基期,換進**別類別**深跌但健康的標的(分散 + 賺回歸差價)。
    fund_rows 每檔需含:code / name(或 基金名)/ 基金類別 / σ rank / 4D Grade /
    吃本金燈號 / 操盤評分 / 距 HWM %。無「不同類」健康買方 → buy_* 為 None(誠實)。
    """
    rows = [r for r in (fund_rows or []) if isinstance(r, dict) and r.get("code")]
    sells = [r for r in rows if classify_base(r.get("σ rank"), sell_sigma, buy_sigma) == "high"]
    buys = [r for r in rows
            if classify_base(r.get("σ rank"), sell_sigma, buy_sigma) == "low"
            and is_healthy_buy(r, min_score)]

    out = []
    for s in sells:
        _cat = str(s.get("基金類別") or "").strip()
        # 跨類別:買方類別須存在、且與賣方**不同**(不同產業/性質輪動)
        cands = [b for b in buys if b["code"] != s["code"]
                 and str(b.get("基金類別") or "").strip()
                 and str(b.get("基金類別") or "").strip() != _cat]
        cands.sort(key=lambda b: (_sigma(b.get("σ rank")) if _sigma(b.get("σ rank")) is not None else 0.0))
        best = cands[0] if cands else None       # σ rank 最負(跌最深 = 差價空間大)
        out.append({
            "sell_code": s["code"],
            "sell_name": s.get("name") or s.get("基金名") or s["code"],
            "sell_sigma": _sigma(s.get("σ rank")),
            "sell_cat": _cat,
            "buy_code": best["code"] if best else None,
            "buy_name": (best.get("name") or best.get("基金名") or best["code"]) if best else None,
            "buy_sigma": _sigma(best.get("σ rank")) if best else None,
            "buy_cat": str(best.get("基金類別") or "").strip() if best else None,
            "buy_grade": best.get("4D Grade") if best else None,
            "buy_score": _num(best.get("操盤評分")) if best else None,
            "potential_pct": revert_upside_pct(best.get("距 HWM %")) if best else None,
        })
    return out
