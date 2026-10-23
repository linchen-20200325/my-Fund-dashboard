"""services/rotation.py — 輪動配對建議(賣高基期 → 買低基期健康標的)v19.415。

跨產業/性質輪動:把「貼近高點(高基期)」的基金,配對換進「深跌但體質健康(低基期)」的
**不同類別**基金(分散 + 賺回歸差價);等買進的漲回高基期再換。純函式:輸入每檔已算好的
σ rank / 基金類別 / 4D Grade / 吃本金燈號 / 操盤評分 / 距 HWM %,輸出配對建議。

§1 誠實:低基期 **≠ 一定回漲**(可能是價值陷阱/接刀)—— 買方**必須通過健康過濾**
(4D ≠ F + 吃本金非吃本金 + 操盤評分 ≥ 門檻)才推薦;無合適配對 → 回空,不硬湊。
σ rank = 現價在期間高點下方第幾個 σ(負值愈深愈低基期),已標準化無量綱陷阱。

σ 切點 + 健康門檻走 shared/signal_thresholds SSOT(§3.3 反捏造)。

⚠️ **legacy 行動語意,待 BL-0428 重新裁示**(2026-10-23 裁示 2C ＋ Stop Gate「選項 1」,BL-0426):
本模組讀到的 σ rank 一律來自唯一 SSOT `services/fund_position.compute_fund_position`
(配息還原序列、fail closed —— 無法判定時 σ rank 缺值,走既有的「資料不足 / unknown」分支,
不補 0、不當中性)。輪動配對讀健診大表的 σ(由 `services/fund_grp_health/risk.hwm_sigma_with_numeric` 經 SSOT 產生;2026-10-23 BL-0428 §9.8 起判定讀正式數值 `sigma_rank`,見 `row_sigma_rank`)。本模組的買賣 / 加碼 / 換股規則、門檻、決策結構與文字**一字未改**;
σ 位置本身只是「相對自身近一年高點的位置證據」,不是交易建議。
"""
from __future__ import annotations

from shared.signal_thresholds import (
    ROTATION_BUY_MIN_SCORE,
    ROTATION_BUY_SIGMA,
    ROTATION_SELL_SIGMA,
)


def _num(v):
    from shared.converters import safe_num
    return safe_num(v)


def _ccy(row) -> str:
    """讀該列計價幣別 → 正規化 ISO 字串(未知回 '')。支援 currency/ccy/幣別 別名。

    §4.1:跨幣別換股會被動吃匯差 —— 由呼叫端據 cross_ccy 旗標標註(user 2026-08-19
    核准「標註匯差但保留」,不主觀砍跨幣別分散機會)。未知幣別 → '' → 不判 cross(§1 不臆測)。
    """
    if not isinstance(row, dict):
        return ""
    from services.currency import normalize_ccy
    for k in ("currency", "ccy", "幣別"):
        v = row.get(k)
        if v:
            return normalize_ccy(v, default="")
    return ""


def _sigma(v):
    """σ rank 顯示字串(如 '-2.00σ')→ 數值。先去 'σ' 再 safe_num。"""
    if v is None:
        return None
    return _num(str(v).replace("σ", "").strip())


def row_sigma_rank(row):
    """列 → σ rank **正式數值**(BL-0428 §9.8,2026-10-23)。

    列帶有 `sigma_rank` 鍵(由 `services/fund_grp_health/risk.hwm_sigma_with_numeric`
    的 SSOT 原始數值組進來;⬜ 時為 None)→ **一律以它為準**,不再解析「σ rank」顯示字串
    (顯示字串四捨五入到兩位小數,切點兩側 0.005σ 內會判錯;已確認 bug)。
    列沒有 `sigma_rank` 鍵(例:批次大表 df / checkpoint 只存顯示字串)→ 才退回解析字串
    (該路徑沒有數值可讀;見 `rows_from_batch_df`)。
    """
    if not isinstance(row, dict):
        return None
    if "sigma_rank" in row:
        _v = row.get("sigma_rank")
        if isinstance(_v, bool) or not isinstance(_v, (int, float)):
            return None
        _f = float(_v)
        return _f if _f == _f and _f not in (float("inf"), float("-inf")) else None
    return _sigma(row.get("σ rank"))


def display_sigma(v):
    """σ 數值 → 與「σ rank」顯示字串同精度的數值(兩位小數),只供配對表 / 通知呈現。
    判定一律用未四捨五入的 `row_sigma_rank`;呈現維持舊有兩位小數(顯示不變)。"""
    return round(float(v), 2) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def classify_base(sigma_rank, sell_sigma: float = ROTATION_SELL_SIGMA,
                  buy_sigma: float = ROTATION_BUY_SIGMA) -> str:
    """依 σ rank 分基期:high(≥ sell_sigma,貼近高點=賣)/ low(≤ buy_sigma,深跌=買)/ mid / unknown。"""
    v = _sigma(sigma_rank)
    if v is None:
        return "unknown"
    if v >= sell_sigma:
        return "high"
    if v <= buy_sigma:
        return "low"
    return "mid"


def is_healthy_buy(row: dict, min_score: float = ROTATION_BUY_MIN_SCORE) -> bool:
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


def insufficient_sigma_names(rows: list, sell_sigma: float = ROTATION_SELL_SIGMA,
                             buy_sigma: float = ROTATION_BUY_SIGMA) -> list:
    """σ 資料不足(classify_base == 'unknown')的檔名清單(name 缺 → 退 code)。

    v19.484 稽核 #5 的門檻判斷:σ 資料不足(淨值史太短 / 停售 → σ rank 回不了值)的檔
    會被排除在買方候選外 —— 原本靜默剔除 → 呼叫端據本清單明確標名,讓使用者知道
    「不是漏了它,是它現在無法評估」(§1)。
    (原 inline 於 ui/helpers/fund_grp_health/rotation.py::_render_pairs_ui,
    2026-08-31 逐字下沉本檔;判斷式一字未改。)
    """
    return [str(r.get("name") or r.get("code"))
            for r in rows
            if classify_base(row_sigma_rank(r), sell_sigma, buy_sigma) == "unknown"]


def _cell(row, col):
    """從 pandas Series / dict 取值,NaN → None(避免 str(nan)='nan' 混入類別/σ)。

    (2026-08-31 自 ui/helpers/fund_grp_health/rotation.py 逐字下沉;邏輯一字未改。)
    """
    import pandas as pd
    v = row.get(col)
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return v


def rows_from_batch_df(df) -> list:
    """批次「組合健診大表」df → suggest_rotation_pairs 所需 rows。

    所有欄位(σ rank / 距 HWM % / 操盤評分 / 基金類別 / 4D Grade / 吃本金燈號)已在大表內,
    **直接讀、不重抓**。σ rank / 距 HWM % 為預格式化字串(如 '-2.00σ'/'‑18%'),
    本檔的 _sigma / _num 會自行剝除單位。
    (2026-08-31 自 ui/helpers/fund_grp_health/rotation.py 逐字下沉 —— 批次 df → 配對核心的
    輸入契約對映與配對演算法同住一檔,全站單一份;邏輯一字未改。)

    ⚠️ BL-0428 §9.8(2026-10-23)**已知殘留**:批次大表 df / checkpoint 只存兩位小數的
    「σ rank」顯示字串、沒有 SSOT 原始數值欄,本路徑的 rows 因此沒有 `sigma_rank` 鍵,
    `row_sigma_rank` 只能退回解析字串(切點兩側 0.005σ 內仍可能與 SSOT 不同)。
    要修需在批次 df 增加數值欄(表格欄增減屬 UI 變更),本批未做,登記於 BL-0428。
    """
    rows = []
    for _, r in df.iterrows():
        _code = _cell(r, "code")
        rows.append({
            "code": _code,
            "name": _cell(r, "基金名") or _code,
            "基金類別": _cell(r, "基金類別"),
            "4D Grade": _cell(r, "4D Grade"),
            "σ rank": _cell(r, "σ rank"),
            "距 HWM %": _cell(r, "距 HWM %"),
            "操盤評分": _cell(r, "操盤評分"),
            "吃本金燈號": _cell(r, "吃本金燈號 (1Y · )"),
            "currency": _cell(r, "ccy"),   # v19.484:跨幣別換股標註(§4.1)用;大表已正規化欄
        })
    return rows


def suggest_rotation_pairs(fund_rows, sell_sigma: float = ROTATION_SELL_SIGMA,
                           buy_sigma: float = ROTATION_BUY_SIGMA,
                           min_score: float = ROTATION_BUY_MIN_SCORE) -> list:
    """回傳配對建議 list[dict](每個高基期賣方一列;配**不同**基金類別最深跌的健康買方)。

    **跨產業/性質輪動**:賣掉某類別的高基期,換進**別類別**深跌但健康的標的(分散 + 賺回歸差價)。
    fund_rows 每檔需含:code / name(或 基金名)/ 基金類別 / σ rank / 4D Grade /
    吃本金燈號 / 操盤評分 / 距 HWM %。無「不同類」健康買方 → buy_* 為 None(誠實)。
    """
    rows = [r for r in (fund_rows or []) if isinstance(r, dict) and r.get("code")]
    sells = [r for r in rows if classify_base(row_sigma_rank(r), sell_sigma, buy_sigma) == "high"]
    buys = [r for r in rows
            if classify_base(row_sigma_rank(r), sell_sigma, buy_sigma) == "low"
            and is_healthy_buy(r, min_score)]

    out = []
    for s in sells:
        _cat = str(s.get("基金類別") or "").strip()
        # 跨類別:買方類別須存在、且與賣方**不同**(不同產業/性質輪動)
        cands = [b for b in buys if b["code"] != s["code"]
                 and str(b.get("基金類別") or "").strip()
                 and str(b.get("基金類別") or "").strip() != _cat]
        cands.sort(key=lambda b: (row_sigma_rank(b) if row_sigma_rank(b) is not None else 0.0))
        best = cands[0] if cands else None       # σ rank 最負(跌最深 = 差價空間大)
        _sell_ccy = _ccy(s)
        _buy_ccy = _ccy(best) if best else ""
        out.append({
            "sell_code": s["code"],
            "sell_name": s.get("name") or s.get("基金名") or s["code"],
            "sell_sigma": display_sigma(row_sigma_rank(s)),
            "sell_cat": _cat,
            "sell_ccy": _sell_ccy or None,
            "buy_code": best["code"] if best else None,
            "buy_name": (best.get("name") or best.get("基金名") or best["code"]) if best else None,
            "buy_sigma": display_sigma(row_sigma_rank(best)) if best else None,
            "buy_cat": str(best.get("基金類別") or "").strip() if best else None,
            "buy_ccy": (_buy_ccy or None) if best else None,
            "buy_grade": best.get("4D Grade") if best else None,
            "buy_score": _num(best.get("操盤評分")) if best else None,
            # 跨幣別旗標:兩邊幣別皆已知且不同 → 換股被動含匯差(§4.1;呼叫端據此標註不砍建議)
            "cross_ccy": bool(best and _sell_ccy and _buy_ccy and _sell_ccy != _buy_ccy),
            "potential_pct": revert_upside_pct(best.get("距 HWM %")) if best else None,
        })
    return out
