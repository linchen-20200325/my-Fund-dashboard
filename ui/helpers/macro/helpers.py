"""ui/helpers/macro_helpers.py — 總經健康度 / 基金 signal 純函式（v18.133）

從 app.py 搬入的 helper：
- calculate_composite_score / composite_verdict（v17.3 宏觀健康度總分，現為 shim re-export）
- format_phase_score（v19.403 DUP-3 景氣位階字卡文字 SSOT）
- mk_fund_signal（基金信號）
- quartile_check（四分位風險檢查）

2026-08-05 稽核 🟡 必修 5：原「四大類別健康度」一組（分類常數 + 3 個
category_* 函式）已整組刪除 —— production 0 caller 的第三套指標分類法。
理由見本檔下方刪除註記。

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

from shared.colors import MATERIAL_GREEN, MATERIAL_ORANGE, MATERIAL_RED, MD_GREEN_A200, TRAFFIC_NEUTRAL
# F-GRAY-4 v19.269 D8 Phase 4 (#3):CPI bull_high SSOT(SPEC §16.2 inflection_detection)
from shared.macro_thresholds_v2 import CPI_YOY_THRESHOLDS as _CPI_THR

_CPI_BULL_HIGH = _CPI_THR["inflection_detection"]["bull_high"]  # 3.0


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
# HELPER: format_phase_score — 景氣位階字卡文字 SSOT（v19.403 Phase 2 DUP-3）
# calc_macro_phase 的 score 為 0-10 循環評分(us_indicators.py round(max(0,min(10,·)),1)),
# **恆 ≥ 0** → 禁用帶正負號格式(`:+.1f`)。原 tab_fund_grp_health.py 誤用 +.1f 顯示
# 「+6.5」,與 hero 的加權淨分(genuinely signed)撞臉。本 SSOT 收單一格式消歧義。
# ══════════════════════════════════════════════════════
def format_phase_score(phase_info: dict | None) -> str:
    """回景氣位階 SSOT 文字：`{phase} {score:.1f}/10`(score 恆 0-10,不帶正負號)。

    - phase_info 非 dict / 無 phase → 回 ""(交由 caller 決定 fallback 文字)
    - 有 phase 但 score 為 None → 回 phase(不捏造 0.0 分,§1)
    """
    if not isinstance(phase_info, dict):
        return ""
    phase = phase_info.get("phase")
    if not phase:
        return ""
    score = phase_info.get("score")
    if score is None:
        return str(phase)
    try:
        return f"{phase} {float(score):.1f}/10"
    except (TypeError, ValueError):
        return str(phase)


# ══════════════════════════════════════════════════════
# 2026-08-05 稽核 🟡 必修 5 — 「四大類別健康度」(v17.4)整組刪除
#
# 刪除對象:`_CATEGORY_MAP` 常數 + `category_score` / `category_history` /
# `category_verdict` 三個函式。理由三條:
#   1. **production 0 caller**:全 repo 只剩 docstring / BACKLOG 提及,
#      `tests/test_macro_indicator_signs.py` 已明文把它登記為死碼例外。
#      依 `PROCESS.md §4` 稽核落地條款:0 consumer → 接線或刪除,
#      不得留著假裝有揭露;§8.1 step 6「用不到的抽象先不做」同向。
#   2. **它是第三套指標分類法**(領先 / 同時-落後 / 流動性 / 金融壓力四大類),
#      與現行的五桶(`shared.macro_buckets`)+ 服務層 `type` 欄並存,
#      會讓後人以為系統真的有四大類 —— 本輪主題正是「歸類」,留著就是誤導。
#   3. `category_score` 內含 `weight` 的 falsy 回退(`0 or 1 == 1`,會把刻意
#      歸零的去重權重還原成 1),是全 repo 最後一處;刪除後該漂移鎖的
#      豁免清單即可清空。
# ══════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════
# HELPER: mk_fund_signal
# ══════════════════════════════════════════════════════
# 2026-10-11（客戶裁示：停用依基金名稱推定核心／衛星）：
# 本函式原以「基金名稱／基金種類」關鍵字猜核心資產／衛星資產／混合型，並據此從
# `RECS[phase][is_core]` 給買進／賣出類操作句。名稱不是級別的可追溯來源 ——
#   (1) 客戶設定的「核心／衛星級別」只來自 Google Sheet 的 policy_tier
#       （SSOT：`shared/policy_tier.py::resolve_tier`），不得由名稱、AI 或其他推測補值；
#   (2)「基金屬性」（舊稱「資產屬性」）是基金本身的客觀分類。MoneyDJ／FundClear 的
#       `category` 原值（`repositories/fund/sources.py::_pick_fund_category`、
#       `_src_fundclear_meta`）本身是可追溯的原始分類，健診頁「基金類別」欄已在用；
#       本函式恆回「—」的原因**不是**「不存在來源」，而是 (a) 客戶裁示停用「依名稱推定」，
#       (b) 本函式簽名未接 category 資料 ⇒ 目前一律「—」。日後若要顯示，須由資料層提供
#       category 原值，不得由基金名稱推定。
# 因此 `asset_class`／`label` 恆為「—」、`sig_type` 恆為 "none"、`reason` 恆為空；
# 不論景氣位階（phase／score）是否接回，都不得重新啟用名稱推定。
# 簽名與回傳鍵刻意不變（caller 不連動修改）；`auto_alloc`（PMI／VIX／失業率／CPI 的
# 股債配比）與基金名稱無關，原封保留。
# 守衛：tests/test_tier_q6_asset_attr_retired.py。
_NO_FUND_ATTR = "—"
# 與停用前 sig_type="none" 實際落到的樣式（原 SIG["hold"]）逐字相同，不改畫面。
_NO_SIGNAL_STYLE = "background:#1a3450;color:{INFO_BLUE};border:1px solid {INFO_BLUE}"


def mk_fund_signal(fund_info: dict, phase: str, score: float) -> dict:
    # fund_info / phase / score 僅為相容舊簽名而保留：基金屬性與操作訊號都不依它們推定。
    asset_class, label, sig_type, reason = _NO_FUND_ATTR, _NO_FUND_ATTR, "none", ""
    sig_style = _NO_SIGNAL_STYLE
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
            if float(_cpi)>float(_cpip) and float(_cpi)>_CPI_BULL_HIGH: auto_alloc=(50,50,f"升息尾聲—均衡（CPI {float(_cpi):.1f}%↑）",MATERIAL_ORANGE)
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
