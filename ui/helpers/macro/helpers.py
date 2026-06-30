"""ui/helpers/macro_helpers.py — 總經健康度 / 基金 signal 純函式（v18.133）

從 app.py 搬入 6 個 helper + 1 個 constant：
- _CATEGORY_MAP（4 大類指標分組）
- calculate_composite_score / composite_verdict（v17.3 宏觀健康度總分）
- category_score / category_history / category_verdict（v17.4 類別健康度）
- mk_fund_signal（基金信號）
- _quartile_check（四分位風險檢查）

設計：
- 純函式（無 streamlit context 依賴除了 mk_fund_signal 讀 session_state）
- 從 ui/helpers/macro_helpers 直接 import，不走 sys.modules['__main__'] hack
- app.py 保留 shim re-export，向後相容

歷史：
- v18.128~131 hotfix 嘗試用 sys.modules['__main__'] lookup 從 ui/tab1_macro 取
  這些 helper，但 Streamlit Cloud 內部 exec 機制不一定維持 __main__ namespace
  → 改搬到專屬 module 由 ui/tab*.py 正規 import，最穩。
"""
from __future__ import annotations

import streamlit as st

from shared.colors import MATERIAL_GREEN, MATERIAL_ORANGE, MATERIAL_RED, MD_AMBER_300, MD_GREEN_A200, TRAFFIC_NEUTRAL, TRAFFIC_RED


# ══════════════════════════════════════════════════════
# HELPER: calculate_composite_score / composite_verdict
# v19.197 P1-1:已下沉 services/macro_composite_score.py(L2 純函式,實為 macro 業務邏輯)
# 本檔保留 shim re-export 確保既有 L3 caller(app.py / ui/tab1_macro.py)不需改 import path
# ══════════════════════════════════════════════════════
from services.macro_composite_score import (  # noqa: F401
    calculate_composite_score,
    composite_verdict,
)


# ══════════════════════════════════════════════════════
# HELPER: 四大類別健康度（v17.4）
# ══════════════════════════════════════════════════════
_CATEGORY_MAP = {
    "📈 領先指標": [
        ("SAHM", True), ("SLOOS", True), ("PMI", False), ("LEI", False),
        ("YIELD_10Y2Y", False), ("YIELD_10Y3M", False), ("PPI", True),
        ("COPPER", False), ("ADL", False), ("JOBLESS", True),
        ("CONT_CLAIMS", True), ("CONSUMER_CONF", False), ("PERMIT_HOUSING", False),
    ],
    "📍 同時 / 落後": [
        ("CPI", True), ("INFL_EXP_5Y", True),
        ("FED_RATE", True), ("UNEMPLOYMENT", True),
    ],
    "💧 流動性": [
        ("M2", False), ("M2_WEEKLY", False), ("FED_BS", False), ("DXY", True),
    ],
    "⚠️ 金融壓力": [
        ("HY_SPREAD", True), ("VIX", True),
    ],
}


def category_score(ind: dict, keys: list) -> tuple[float, int, int]:
    """回傳 (Σ score×weight, 有效資料筆數, 該類總指標數)。

    v19.1 (C-2)：入口呼叫 ``apply_weight_overrides``；active 空時行為不變。
    """
    try:
        from services.macro.weights_store import apply_weight_overrides
        ind = apply_weight_overrides(ind or {})
    except ImportError:
        ind = ind or {}
    total = 0.0
    n_data = 0
    for k, _hib in keys:
        v = ind.get(k)
        if not isinstance(v, dict):
            continue
        try:
            s = float(v.get("score", 0) or 0)
            w = float(v.get("weight", 1) or 1)
        except (TypeError, ValueError):
            continue
        if s != s or w != w:
            continue
        total += s * w
        n_data += 1
    return round(total, 2), n_data, len(keys)


def category_history(ind: dict, keys: list, lookback: int = 24):
    """回傳該類別 24M 月底「方向化 Z-Score 平均」序列；資料不足回 None。"""
    import pandas as pd
    sigs = []
    for k, hib in keys:
        v = (ind or {}).get(k)
        if not isinstance(v, dict):
            continue
        s = v.get("series")
        if s is None:
            continue
        try:
            ser = s if isinstance(s, pd.Series) else pd.Series(s)
            ser = ser.dropna().tail(lookback * 5)
            if len(ser) < 6:
                continue
            mu = float(ser.mean())
            sigma = float(ser.std())
            if sigma == 0 or sigma != sigma or mu != mu:
                continue
            z = (ser - mu) / sigma
            if hib:
                z = -z
            try:
                z.index = pd.to_datetime(z.index)
                z_m = z.resample("ME").last().dropna().tail(lookback)
            except Exception:
                z_m = z.tail(lookback)
            if len(z_m) >= 3:
                sigs.append(z_m)
        except Exception:
            continue
    if not sigs:
        return None
    df = pd.concat(sigs, axis=1)
    out = df.mean(axis=1).dropna()
    return out if len(out) >= 3 else None


def category_verdict(z_now: float | None, z_trend_delta: float) -> tuple[str, str, str]:
    """根據最新 Z 與近期變化回傳 (icon, color, 一句話)。"""
    if z_now is None:
        return ("⬜", TRAFFIC_NEUTRAL, "資料不足，待補")
    if z_now <= -1.5:
        icon, color = "🔴", MATERIAL_RED
    elif z_now <= -0.5:
        icon, color = "🟠", MATERIAL_ORANGE
    elif z_now < 0.5:
        icon, color = "🟡", MD_AMBER_300
    else:
        icon, color = "🟢", MD_GREEN_A200
    direction = "改善中 📈" if z_trend_delta > 0.2 else ("惡化中 📉" if z_trend_delta < -0.2 else "持平 →")
    return (icon, color, f"當前 Z={z_now:+.2f}（{direction}）")


# ══════════════════════════════════════════════════════
# HELPER: mk_fund_signal
# ══════════════════════════════════════════════════════
def mk_fund_signal(fund_info: dict, phase: str, score: float) -> dict:
    name  = (fund_info.get("基金名稱","") or fund_info.get("name","") or fund_info.get("fund_name","")).lower()
    ftype = (fund_info.get("基金種類","") or "").lower()
    core_kw = ["收益","配息","債","高股息","均衡","平衡","公債","income","bond","fixed"]
    sat_kw  = ["科技","ai","半導體","新興","生技","成長","tech","equity","growth","theme"]
    is_core = any(k in name or k in ftype for k in core_kw)
    is_sat  = any(k in name or k in ftype for k in sat_kw) and not is_core
    asset_class = "核心資產 🛡️" if is_core else ("衛星資產 ⚡" if is_sat else "混合型 ⚖️")
    RECS = {
        "復甦": {True:("🟢 買進加碼","buy","復甦期景氣反轉，核心配息資產為最高勝率佈局"),False:("🟢 積極買進","buy","復甦期是衛星資產最佳進場點，成長基金爆發力強")},
        "擴張": {True:("⚪ 持有核心","hold","擴張期繼續持有核心配息資產，定期收息再投入"),False:("🟡 持有設停利","hold","擴張期衛星資產保持持有，設停利點 +10~15%")},
        "高峰": {True:("🟡 持有減碼","switch","景氣高峰，核心資產可適度減碼增加防禦性債券"),False:("🔴 賣出獲利","sell","高峰期衛星資產應積極獲利了結，避免高基期風險")},
        "衰退": {True:("🟢 逢低買進","buy","衰退末期優先佈局核心配息資產，等待景氣拐點"),False:("⏸️ 觀望等待","hold","衰退期衛星資產避免進場，等待PMI落底確認訊號")},
    }
    label, sig_type, reason = RECS.get(phase, RECS["擴張"])[is_core]
    # v19.252 Phase 4A:sell 走 TRAFFIC_RED SSOT(原 inline #f85149)
    SIG = {"buy":"background:#1a3328;color:#00c853;border:1px solid #00c853","sell":f"background:#3a1a1a;color:{TRAFFIC_RED};border:1px solid {TRAFFIC_RED}","hold":"background:#1a3450;color:#58a6ff;border:1px solid #58a6ff","switch":"background:#3a2a10;color:#f0a500;border:1px solid #f0a500"}
    sig_style = SIG.get(sig_type, SIG["hold"])
    _ind  = st.session_state.get("indicators", {})
    _pmi  = _ind.get("PMI",{}).get("value"); _vix = _ind.get("VIX",{}).get("value")
    _ue   = _ind.get("UNEMPLOYMENT",{}).get("value")
    _cpi  = _ind.get("CPI",{}).get("value"); _cpip = _ind.get("CPI",{}).get("prev")
    auto_alloc = None
    if _pmi and _vix:
        pf, vf = float(_pmi), float(_vix)
        if pf>50 and vf<20: auto_alloc=(70,30,"復甦/擴張—積極",MATERIAL_GREEN)
        elif pf>50:          auto_alloc=(60,40,"擴張—穩健",MD_GREEN_A200)
        elif pf<50 and vf>25: auto_alloc=(40,60,"衰退—保守",MATERIAL_RED)
        else:                auto_alloc=(50,50,"觀望—中性",MATERIAL_ORANGE)
    if _ue:
        try:
            if float(_ue)>4.0: auto_alloc=(40,60,f"衰退（失業率{float(_ue):.1f}%破4%）",MATERIAL_RED)
        except Exception:
            pass   # smoke-allow-pass
    if _cpi and _cpip:
        try:
            if float(_cpi)>float(_cpip) and float(_cpi)>3.0: auto_alloc=(50,50,f"升息尾聲—均衡（CPI {float(_cpi):.1f}%↑）",MATERIAL_ORANGE)
        except Exception:
            pass   # smoke-allow-pass
    return dict(asset_class=asset_class, label=label, sig_type=sig_type, sig_style=sig_style, reason=reason, auto_alloc=auto_alloc)


# ══════════════════════════════════════════════════════
# HELPER: _quartile_check
# ══════════════════════════════════════════════════════
def quartile_check(peer_compare: dict, risk_table: dict) -> dict:
    out = {"quartile":None,"color":TRAFFIC_NEUTRAL,"label":"無同類資料","warning":False,"fund_sharpe":None,"peer_avg":None,"advice":""}
    if not peer_compare and not risk_table:
        return out
    fund_sh = None
    try:
        fund_sh = float(str(risk_table.get("一年",{}).get("Sharpe","") or "").replace("—",""))
    except Exception:
        pass   # smoke-allow-pass
    peer_sharpes = []
    for row_v in (peer_compare or {}).values():
        if isinstance(row_v, dict):
            for k2, v2 in row_v.items():
                if "sharpe" in k2.lower() or "夏普" in k2:
                    try:
                        peer_sharpes.append(float(str(v2).replace("—","")))
                    except Exception:
                        pass   # smoke-allow-pass
            try:
                sh_v = float(str(row_v.get("Sharpe", row_v.get("夏普","")) or "").replace("—",""))
                peer_sharpes.append(sh_v)
            except Exception:
                pass   # smoke-allow-pass
    if fund_sh is None and not peer_sharpes:
        return out
    if not peer_sharpes:
        q = 1 if fund_sh > 1.5 else (2 if fund_sh > 0.8 else (3 if fund_sh > 0 else 4))
        c = [MATERIAL_GREEN,MD_GREEN_A200,MATERIAL_ORANGE,MATERIAL_RED][q-1]
        lbl = ["第1四分位🏆(前25%)","第2四分位✅(前50%)","第3四分位⚠️(後50%)","第4四分位🔴(後25%)"][q-1]
        adv = "⚠️ 後25%達2季→建議跨行轉存至同類前25%標的" if q==4 else ("追蹤：若下季仍第3四分位考慮替換" if q==3 else "")
        return {"quartile":q,"color":c,"label":lbl,"warning":q>=4,"fund_sharpe":fund_sh,"peer_avg":None,"advice":adv}
    import statistics as _stat
    ps = sorted(peer_sharpes); n = len(ps)
    q25 = ps[max(0,n//4-1)]; q75 = ps[min(n-1,3*n//4)]; pavg = _stat.mean(ps)
    sh_ref = fund_sh if fund_sh is not None else pavg
    if sh_ref>=q75:    q,c,lbl = 1,MATERIAL_GREEN,"第1四分位🏆(前25%)"
    elif sh_ref>=pavg: q,c,lbl = 2,MD_GREEN_A200,"第2四分位✅(前50%)"
    elif sh_ref>=q25:  q,c,lbl = 3,MATERIAL_ORANGE,"第3四分位⚠️(後50%)"
    else:              q,c,lbl = 4,MATERIAL_RED,"第4四分位🔴(後25%—警戒)"
    adv = "⚠️ 後25%達2季→建議跨行轉存至同類前25%標的" if q>=4 else ("注意：若下季仍第3四分位，考慮替換" if q==3 else "")
    return {"quartile":q,"color":c,"label":lbl,"warning":q>=4,"fund_sharpe":fund_sh,"peer_avg":round(pavg,3),"advice":adv}


# v19.175:compute_1y_total_return 搬到 services/fund_total_return.py(L2 純函式)。
# 理由:services/fund_dividend_health.check_eating_principal_1y_mk() 需 SSOT 呼叫,
# 但 L2 service 不得 import L3 ui(§8.2)。本檔保留 shim re-export 確保 14 處 caller
# 不需改 import path。E402 因 shim 必須在原 def 位置(檔案中段),允許之。
from services.fund_total_return import compute_1y_total_return  # noqa: F401, E402
