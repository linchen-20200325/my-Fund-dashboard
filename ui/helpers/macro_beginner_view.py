"""v19.124 起 / v19.128 重整 — 總經 Tab 四時域分組計算用 helper。

歷史:
- v19.124-126:三大紅綠燈 + 教室(新手模式專用)
- v19.128:user 反饋砍掉新手 / 進階 / 教室,改採「長期 / 中期 / 短線 / 拐點」
  四時域 summary bar。本檔保留 `compute_traffic_lights` 作為純函式運算基礎,
  將在四時域 summary 中被重用(警訊燈邏輯對應「拐點」桶等)。
- 已刪除:`_render_one_traffic_light` / `render_beginner_view`
  / `render_principle_classroom` / `_PRINCIPLE_CHAPTERS`(對應教室全砍指示)

§3.3 SSOT
- macro score / phase → services.macro_service.calc_macro_phase
- 美林時鐘 → services.macro_explain.classify_merrill_clock
- 警訊閾值 → shared/signal_thresholds.py(SAHM_RECESSION_THRESHOLD 等)
- 不新增 magic number

§8 架構
- L3 UI helper,純函式 compute_traffic_lights(無 streamlit 依賴 → 可單獨測試)

由 PR 2 (v19.125) wire 進 ui/tab1_macro.py:
    from ui.helpers.macro_beginner_view import (
        render_beginner_view, render_principle_classroom,
    )
    _mode = st.radio(...)
    if _mode == "🟢 新手":
        render_beginner_view(indicators, phase_info)
        render_principle_classroom()
"""
from __future__ import annotations

from typing import Optional

import streamlit as st

from shared.colors import MATERIAL_GREEN, MATERIAL_ORANGE, MATERIAL_RED
from shared.macro_thresholds_v2 import HY_SPREAD_THRESHOLDS as _HY_THR  # F-GRAY-4 v19.169
from shared.signal_thresholds import (
    CFNAI_RECESSION_THRESHOLD,
    SAHM_RECESSION_THRESHOLD,
)

# ════════════════════════════════════════════════════════════════
# 閾值常數(本檔特用,非通用 metric — 不抽 SSOT;§8.2.A EX-POLICY-1 同理)
# ════════════════════════════════════════════════════════════════

# 景氣燈號:macro score 0~10 切 3 級(對應 calc_macro_phase 的 0~2 衰退/8~10 高峰)
_MACRO_SCORE_DANGER_MAX: float = 3.0    # < 3 → 衰退區
_MACRO_SCORE_HEALTHY_MIN: float = 6.0   # ≥ 6 → 擴張區(中間 3~6 為警戒)

# 警訊燈號:任一觸發 = 紅
#
# C2-B v19.158 — VIX warning 20 → 22(直接 import SSOT _VIX_YELLOW)
# user 拍板撤銷 v19.147 multi-cutoff(教學前置 20 比 SSOT 22 早 2 點),
# 接受「教學卡片不再提前 2 點預警」trade-off 換 SSOT 收斂。panic=30 不變。
# F-GRAY-4 v19.169 — HY beginner_panic 改 SSOT(SPEC §16.2):
# 數值不變(panic=8 / warn=5,仍為新手保守版),改 import shared/macro_thresholds_v2。
from shared.macro_buckets import _VIX_RED as _MB_VIX_RED, _VIX_YELLOW as _MB_VIX_YELLOW

_VIX_PANIC_THRESHOLD: float = _MB_VIX_RED      # = 30,恐慌(全員一致)
_VIX_WARNING_THRESHOLD: float = _MB_VIX_YELLOW # = 22,警戒(C2-B v19.158 收 SSOT)
# 注意:新手介面閾值與 stoplight (4/6) 不同 — 更保守 (避免過早警示)
_HY_SPREAD_PANIC_THRESHOLD: float = _HY_THR["beginner_panic"]["panic_above"]  # 8.0
_HY_SPREAD_WARN_THRESHOLD: float = _HY_THR["beginner_panic"]["warn_above"]    # 5.0

# UI 顏色(沿用 MATERIAL_*)
_C_GREEN, _C_YELLOW, _C_RED = MATERIAL_GREEN, MATERIAL_ORANGE, MATERIAL_RED


# ════════════════════════════════════════════════════════════════
# 紅綠燈計算(純函式,易測)
# ════════════════════════════════════════════════════════════════

def compute_traffic_lights(
    indicators: Optional[dict],
    phase_info: Optional[dict] = None,
) -> dict:
    """三大紅綠燈純函式計算。

    輸入:
      indicators: st.session_state["indicators"] 的 macro 指標字典
                  (key 大寫,各帶 value / score / weight / prev / z_score 等欄位)
      phase_info: 已算好的 {"phase", "score"} dict(可選),
                  若為 None 則本函式內部呼叫 calc_macro_phase 重算

    回傳: dict 含 3 個子 dict,每個為 {
        "level": "green"|"yellow"|"red",
        "label": str (中文簡短結論),
        "headline": str (一行白話),
        "reasons": list[str] (推導依據,顯示在 expander 裡),
        "principle": str (背後原理白話),
        "color": hex string,
        "emoji": "🟢"|"🟡"|"🔴",
    }
    """
    indicators = indicators or {}

    # ── 用既有 phase_info 或重算
    if phase_info is None:
        try:
            from services.macro_service import calc_macro_phase
            phase_info = calc_macro_phase(indicators) or {}
        except Exception:
            phase_info = {}

    _macro_score = float(phase_info.get("score") or 5.0)
    _phase_label = phase_info.get("phase") or "未定"

    # ── helper:從 indicators 撈某 key 的 value
    def _ind_val(key: str, attr: str = "value") -> Optional[float]:
        _d = indicators.get(key) or {}
        _v = _d.get(attr)
        try:
            return float(_v) if _v is not None else None
        except (TypeError, ValueError):
            return None

    _vix = _ind_val("VIX")
    _hy = _ind_val("HY_SPREAD")
    _sahm = _ind_val("SAHM")
    _y2 = _ind_val("YIELD_10Y2Y")
    _y3 = _ind_val("YIELD_10Y3M")
    _cfnai = _ind_val("CFNAI")

    # ════════════════════════════════════════════
    # 燈 1:景氣現在好不好?(用 macro score)
    # ════════════════════════════════════════════
    if _macro_score >= _MACRO_SCORE_HEALTHY_MIN:
        _l1_level = "green"
        _l1_label = f"健康({_phase_label})"
        _l1_headline = (
            f"分數 {_macro_score:.1f}/10 — 景氣處於擴張或高峰,"
            "整體經濟動能正面。"
        )
    elif _macro_score <= _MACRO_SCORE_DANGER_MAX:
        _l1_level = "red"
        _l1_label = f"危險({_phase_label})"
        _l1_headline = (
            f"分數 {_macro_score:.1f}/10 — 景氣處於衰退或復甦早期,"
            "經濟動能偏弱。"
        )
    else:
        _l1_level = "yellow"
        _l1_label = f"轉折({_phase_label})"
        _l1_headline = (
            f"分數 {_macro_score:.1f}/10 — 景氣處於擴張/減速交界,"
            "方向未明。"
        )

    _l1_reasons = [
        f"**綜合分數**:{_macro_score:.1f}/10(來自 12 個總經指標加權)",
        f"**景氣階段**:{_phase_label}(衰退 0-2 / 復甦 3-4 / 擴張 5-7 / 高峰 8-10)",
        "**主要依據**(權重高 → 低):",
        "  - PMI 採購經理指數(weight 2)",
        "  - 殖利率曲線 10Y-2Y / 10Y-3M(各 weight 2)",
        "  - HY 高收益債利差(weight 2)",
        "  - M2 流動性 / Fed BS / 市場廣度 RSP/SPY(各 weight 1)",
        "  - DXY / VIX / CPI / Fed Rate / 失業率(weight 0.5-1)",
    ]
    _l1_principle = (
        "綜合分數採機構級 12 指標加權:景氣循環受**實質經濟動能**(PMI / 失業率)、"
        "**信用環境**(HY 利差 / 殖利率曲線)、**流動性**(M2 / Fed BS)、"
        "**情緒**(VIX / 廣度)四大面向驅動。任一面向極端 → 整體分數偏離 5(中性);"
        "歷史驗證:綜合 ≥ 6 期間 SPX 平均年報酬 +12%,≤ 3 期間平均 -8%。"
    )

    # ════════════════════════════════════════════
    # 燈 2:該不該加碼?(用 phase + 拐點)
    # ════════════════════════════════════════════
    _action_map = {
        "復甦": ("green", "建議加碼",
                 "景氣谷底翻揚,股市歷史上此階段平均年報酬最高(+18%)。"),
        "擴張": ("green", "持有 / 適度加碼",
                 "景氣健康擴張,股市穩步上行,可繼續持有並逢低加碼。"),
        "高峰": ("yellow", "獲利了結",
                 "景氣高位,風險升高;歷史上此階段後常見回檔,建議減碼防禦。"),
        "減速": ("yellow", "減碼防禦",
                 "景氣動能放緩,提早調整部位降低波動。"),
        "衰退": ("red", "降低風險",
                 "景氣下行,股市平均報酬轉負;優先持有現金/債券,等待落底訊號。"),
    }
    _l2_level, _l2_label, _l2_headline = _action_map.get(
        _phase_label, ("yellow", "觀望", "景氣階段未定,建議維持現況觀察。"),
    )

    _l2_reasons = [
        f"**目前景氣階段**:{_phase_label}",
        f"**建議操作**:{_l2_label}",
        "**美林時鐘四階段股票配置歷史最佳值**:",
        "  - 復甦:股 80% / 債 20%(成長動能最強)",
        "  - 擴張:股 60% / 債 40%(穩健持有)",
        "  - 高峰:股 40% / 債 60%(風險升高)",
        "  - 衰退:股 20% / 債 80%(防禦為主)",
    ]
    _l2_principle = (
        "美林時鐘把景氣 ×通膨切成 4 象限,推導出股/債/商品/現金的歷史最佳配比。"
        "原理:**股票偏好景氣擴張期**(企業獲利成長),**債券偏好景氣放緩期**"
        "(降息預期 → 債價上揚),**商品偏好通膨上升期**(原物料定價權)。"
        "本系統用 PMI 趨勢 + 殖利率曲線 + 通膨綜合判斷階段。"
    )

    # ════════════════════════════════════════════
    # 燈 3:有沒有警訊?(任一觸發 → 紅;全 OK → 綠)
    # ════════════════════════════════════════════
    _triggers = []   # 紅燈級
    _warnings = []   # 黃燈級

    if _sahm is not None and _sahm >= SAHM_RECESSION_THRESHOLD:
        _triggers.append(
            f"🔴 **薩姆規則 {_sahm:.2f}** ≥ {SAHM_RECESSION_THRESHOLD} — 衰退鎖定"
        )
    if _vix is not None and _vix >= _VIX_PANIC_THRESHOLD:
        _triggers.append(f"🔴 **VIX {_vix:.1f}** ≥ {_VIX_PANIC_THRESHOLD} — 市場恐慌")
    elif _vix is not None and _vix >= _VIX_WARNING_THRESHOLD:
        _warnings.append(f"🟡 **VIX {_vix:.1f}** 已超過 {_VIX_WARNING_THRESHOLD} 警戒值")
    if _hy is not None and _hy >= _HY_SPREAD_PANIC_THRESHOLD:
        _triggers.append(
            f"🔴 **HY 利差 {_hy:.2f}%** ≥ {_HY_SPREAD_PANIC_THRESHOLD}% — 信用危機"
        )
    elif _hy is not None and _hy >= _HY_SPREAD_WARN_THRESHOLD:
        _warnings.append(f"🟡 **HY 利差 {_hy:.2f}%** 偏高")
    if _y2 is not None and _y2 < 0:
        _warnings.append(
            f"🟡 **10Y-2Y 殖利率倒掛 {_y2:.2f}%** — 歷史上 6-18 月後常見衰退"
        )
    if _y3 is not None and _y3 < 0:
        _warnings.append(
            f"🟡 **10Y-3M 殖利率倒掛 {_y3:.2f}%** — 倒掛 = 衰退領先指標"
        )
    if _cfnai is not None and _cfnai <= CFNAI_RECESSION_THRESHOLD:
        _triggers.append(
            f"🔴 **CFNAI {_cfnai:.2f}** ≤ {CFNAI_RECESSION_THRESHOLD} — 全美活動指數萎縮"
        )

    if _triggers:
        _l3_level = "red"
        _l3_label = "緊急警訊"
        _l3_headline = f"觸發 {len(_triggers)} 項危機指標,建議大幅減碼防禦。"
    elif _warnings:
        _l3_level = "yellow"
        _l3_label = "注意警戒"
        _l3_headline = f"出現 {len(_warnings)} 項偏離,須密切觀察。"
    else:
        _l3_level = "green"
        _l3_label = "平靜"
        _l3_headline = "未偵測到任何衰退 / 流動性 / 恐慌警訊。"

    _l3_reasons = (
        ["**🔴 觸發中**:"] + [f"  - {t}" for t in _triggers]
        if _triggers else []
    ) + (
        ["**🟡 警戒中**:"] + [f"  - {w}" for w in _warnings]
        if _warnings else []
    ) + [
        "",
        "**監測規則**:",
        f"  - 薩姆規則 ≥ {SAHM_RECESSION_THRESHOLD}:失業率上升動能鎖定衰退",
        f"  - VIX ≥ {_VIX_PANIC_THRESHOLD}(恐慌)/ ≥ {_VIX_WARNING_THRESHOLD}(警戒)",
        f"  - HY 利差 ≥ {_HY_SPREAD_PANIC_THRESHOLD}%(危機)/ ≥ {_HY_SPREAD_WARN_THRESHOLD}%(警戒)",
        f"  - 殖利率曲線倒掛:10Y-2Y / 10Y-3M < 0",
        f"  - CFNAI ≤ {CFNAI_RECESSION_THRESHOLD}:全美經濟活動萎縮",
    ]
    if not _triggers and not _warnings:
        _l3_reasons.insert(0, "✅ 所有警訊指標皆位於安全區")

    _l3_principle = (
        "5 大警訊各擷取「歷史上衰退/危機前 6-18 個月會先動」的領先指標。"
        "**薩姆規則**(克勞蒂亞・薩姆 2019 年提出):失業率 3 月均比 12 月最低點高 ≥ 0.5pp,"
        "1949 年以來 100% 命中美國衰退。**殖利率倒掛**:10Y < 2Y/3M 是 50 年來"
        "最準確衰退領先指標(平均提前 12 個月)。**HY 利差爆炸**:垃圾債券殖利率"
        "與公債價差擴大 → 信用環境惡化 → 企業破產潮。**VIX 恐慌**:恐慌指數 ≥ 30 "
        "代表 S&P 500 隱含波動率年化 ≥ 30%,投資人對未來 30 天極度不確定。"
    )

    # ════════════════════════════════════════════
    _level_to_color = {"green": _C_GREEN, "yellow": _C_YELLOW, "red": _C_RED}
    _level_to_emoji = {"green": "🟢", "yellow": "🟡", "red": "🔴"}

    return {
        "light1_health": {
            "level": _l1_level,
            "label": _l1_label,
            "headline": _l1_headline,
            "reasons": _l1_reasons,
            "principle": _l1_principle,
            "color": _level_to_color[_l1_level],
            "emoji": _level_to_emoji[_l1_level],
        },
        "light2_action": {
            "level": _l2_level,
            "label": _l2_label,
            "headline": _l2_headline,
            "reasons": _l2_reasons,
            "principle": _l2_principle,
            "color": _level_to_color[_l2_level],
            "emoji": _level_to_emoji[_l2_level],
        },
        "light3_alert": {
            "level": _l3_level,
            "label": _l3_label,
            "headline": _l3_headline,
            "reasons": _l3_reasons,
            "principle": _l3_principle,
            "color": _level_to_color[_l3_level],
            "emoji": _level_to_emoji[_l3_level],
        },
    }


# ════════════════════════════════════════════════════════════════
# v19.128 — 四時域分組 summary(長期 / 中期 / 短線 / 拐點)
# ════════════════════════════════════════════════════════════════

# 中期循環警戒閾值(本檔特用,§3.3 EX-POLICY-1 同理 — 教學語意門檻)
_PMI_CONTRACTION_THRESHOLD: float = 50.0   # PMI < 50 = 收縮
_CPI_OVERHEAT_THRESHOLD: float = 4.0       # CPI YoY > 4% = 過熱
_UNEMP_ELEVATED_THRESHOLD: float = 5.0     # 失業率 > 5% = 偏高

# 短線震盪警戒
_MOVE_WARNING_THRESHOLD: float = 100.0     # MOVE > 100 = 警戒
_PCR_PANIC_THRESHOLD: float = 1.5          # Put/Call > 1.5 = 恐慌

# 拐點警報
_SLOOS_TIGHTENING_THRESHOLD: float = 50.0  # SLOOS > 50 = 銀行收緊


def compute_four_horizon_summary(
    indicators: Optional[dict],
    phase_info: Optional[dict] = None,
) -> dict:
    """四時域分組 summary 純函式計算。

    回傳:
      {
        "long":       {...},  # 🌳 長期:regime / 結構(美林時鐘 + 寬鬆度)
        "mid":        {...},  # 📈 中期:景氣循環(PMI / CPI / 失業)
        "short":      {...},  # 🎯 短線:即時 risk-off(VIX / HY / MOVE / PCR)
        "inflection": {...},  # ⚠️ 拐點:領先警報(Sahm / 倒掛 / CFNAI / SLOOS)
      }
    每桶 dict = { level, label, headline, color, emoji }
    """
    indicators = indicators or {}

    # ── phase 重算備援
    if phase_info is None:
        try:
            from services.macro_service import calc_macro_phase
            phase_info = calc_macro_phase(indicators) or {}
        except Exception:
            phase_info = {}

    def _v(name: str):
        _d = indicators.get(name) or {}
        if not _d:
            return None
        _val = _d.get("value")
        try:
            return float(_val) if _val is not None else None
        except (TypeError, ValueError):
            return None

    _level_to_color = {"green": _C_GREEN, "yellow": _C_YELLOW, "red": _C_RED}
    _level_to_emoji = {"green": "🟢", "yellow": "🟡", "red": "🔴"}

    # ═══ 🌳 長期:regime ═══
    _macro_score = float(phase_info.get("score") or 5.0)
    _phase_name = phase_info.get("phase") or "未定"
    if _macro_score >= _MACRO_SCORE_HEALTHY_MIN:
        _long_level, _long_label = "green", "擴張 / 復甦"
    elif _macro_score < _MACRO_SCORE_DANGER_MAX:
        _long_level, _long_label = "red", "高峰 / 衰退"
    else:
        _long_level, _long_label = "yellow", "轉折中"
    _long_headline = f"{_phase_name} ({_macro_score:.1f}/10)"

    # ═══ 📈 中期:景氣循環 ═══
    _pmi = _v("PMI") or _v("US_PMI")
    _cpi = _v("CPI_YOY") or _v("US_CPI_YOY") or _v("CPI")
    _unemp = _v("UNRATE") or _v("US_UNEMP")
    _mid_msgs = []
    if _pmi is not None and _pmi < _PMI_CONTRACTION_THRESHOLD:
        _mid_msgs.append(f"PMI {_pmi:.1f} 收縮")
    if _cpi is not None and _cpi > _CPI_OVERHEAT_THRESHOLD:
        _mid_msgs.append(f"CPI {_cpi:.1f}% 過熱")
    if _unemp is not None and _unemp > _UNEMP_ELEVATED_THRESHOLD:
        _mid_msgs.append(f"失業 {_unemp:.1f}% 偏高")
    if len(_mid_msgs) >= 2:
        _mid_level, _mid_label = "red", "循環惡化"
    elif _mid_msgs:
        _mid_level, _mid_label = "yellow", "局部走弱"
    else:
        _mid_level, _mid_label = "green", "循環健康"
    _mid_headline = _mid_msgs[0] if _mid_msgs else "PMI/CPI/失業 三項皆健康"

    # ═══ 🎯 短線:即時 risk-off ═══
    _vix = _v("VIX") or 0.0
    _hy = _v("HY_SPREAD") or _v("HY") or 0.0
    _move = _v("MOVE") or 0.0
    _pcr = _v("PCR") or 0.0
    _short_msgs = []
    _short_severe = False
    if _vix >= _VIX_PANIC_THRESHOLD:
        _short_msgs.append(f"VIX {_vix:.1f} 恐慌")
        _short_severe = True
    elif _vix >= _VIX_WARNING_THRESHOLD:
        _short_msgs.append(f"VIX {_vix:.1f} 警戒")
    if _hy >= _HY_SPREAD_PANIC_THRESHOLD:
        _short_msgs.append(f"HY {_hy:.2f}% 危機")
        _short_severe = True
    elif _hy >= _HY_SPREAD_WARN_THRESHOLD:
        _short_msgs.append(f"HY {_hy:.2f}% 警戒")
    if _move >= _MOVE_WARNING_THRESHOLD:
        _short_msgs.append(f"MOVE {_move:.0f}")
    if _pcr >= _PCR_PANIC_THRESHOLD:
        _short_msgs.append(f"PCR {_pcr:.2f}")
        _short_severe = True
    if _short_severe:
        _short_level, _short_label = "red", "極度恐慌"
    elif _short_msgs:
        _short_level, _short_label = "yellow", "短線警戒"
    else:
        _short_level, _short_label = "green", "短線平靜"
    _short_headline = _short_msgs[0] if _short_msgs else f"VIX {_vix:.1f} 正常"

    # ═══ ⚠️ 拐點:領先警報 ═══
    _sahm = _v("SAHM") or 0.0
    _y2 = _v("YIELD_10Y2Y")
    _y3 = _v("YIELD_10Y3M")
    _cfnai = _v("CFNAI")
    _sloos = _v("SLOOS")
    _inf_triggers = []
    _inf_warnings = []
    if _sahm >= SAHM_RECESSION_THRESHOLD:
        _inf_triggers.append(f"薩姆 {_sahm:.2f} 觸發")
    if _y2 is not None and _y2 < 0:
        _inf_warnings.append(f"10Y-2Y 倒掛 {_y2:.2f}%")
    if _y3 is not None and _y3 < 0:
        _inf_warnings.append(f"10Y-3M 倒掛 {_y3:.2f}%")
    if _cfnai is not None and _cfnai <= CFNAI_RECESSION_THRESHOLD:
        _inf_triggers.append(f"CFNAI {_cfnai:.2f} 衰退")
    if _sloos is not None and _sloos >= _SLOOS_TIGHTENING_THRESHOLD:
        _inf_warnings.append(f"SLOOS {_sloos:.0f} 收緊")
    if _inf_triggers:
        _inf_level, _inf_label = "red", "拐點鎖定"
    elif len(_inf_warnings) >= 2:
        _inf_level, _inf_label = "red", "多重警訊"
    elif _inf_warnings:
        _inf_level, _inf_label = "yellow", "拐點臨近"
    else:
        _inf_level, _inf_label = "green", "拐點未現"
    _inf_msgs_all = _inf_triggers + _inf_warnings
    _inf_headline = _inf_msgs_all[0] if _inf_msgs_all else "Sahm/倒掛/CFNAI/SLOOS 全綠"

    return {
        "long": {
            "level": _long_level, "label": _long_label, "headline": _long_headline,
            "color": _level_to_color[_long_level], "emoji": _level_to_emoji[_long_level],
        },
        "mid": {
            "level": _mid_level, "label": _mid_label, "headline": _mid_headline,
            "color": _level_to_color[_mid_level], "emoji": _level_to_emoji[_mid_level],
        },
        "short": {
            "level": _short_level, "label": _short_label, "headline": _short_headline,
            "color": _level_to_color[_short_level], "emoji": _level_to_emoji[_short_level],
        },
        "inflection": {
            "level": _inf_level, "label": _inf_label, "headline": _inf_headline,
            "color": _level_to_color[_inf_level], "emoji": _level_to_emoji[_inf_level],
        },
    }


def render_four_horizon_bar(summary: dict) -> None:
    """頂部四時域 summary bar(4 columns × emoji+燈號+1句)。

    順序鎖定:🌳 長期 → 📈 中期 → 🎯 短線 → ⚠️ 拐點
    對齊下方四桶詳細區塊由上而下的閱讀順序。
    """
    _cols = st.columns(4)
    _order = [
        ("long",       "🌳 長期", "regime / 結構"),
        ("mid",        "📈 中期", "景氣循環"),
        ("short",      "🎯 短線", "即時 risk-off"),
        ("inflection", "⚠️ 拐點", "領先警報"),
    ]
    for _col, (_key, _title, _sub) in zip(_cols, _order):
        _d = summary.get(_key) or {}
        _color = _d.get("color", "#888")
        _emoji = _d.get("emoji", "⚪")
        _label = _d.get("label", "—")
        _headline = _d.get("headline", "")
        with _col:
            st.markdown(
                f"""<div style="border-left:4px solid {_color};padding:10px 14px;background:rgba(255,255,255,0.03);border-radius:6px;margin-bottom:6px;">
<div style="font-size:0.78em;color:#888;letter-spacing:0.5px;">{_sub}</div>
<div style="font-size:1.05em;font-weight:600;margin-top:2px;">{_emoji} {_title}: <span style="color:{_color};">{_label}</span></div>
<div style="font-size:0.85em;color:#bbb;margin-top:4px;line-height:1.4;">{_headline}</div>
</div>""",
                unsafe_allow_html=True,
            )


# ════════════════════════════════════════════════════════════════
# v19.146 — 五桶 summary 擴充(對齊 Stock v18.284,Fund 加 📰 新聞為第 5 桶)
#   wraps compute_four_horizon_summary + 新增新聞桶(讀 v19.144 SSOT 閾值)
#   不修改既有 4-horizon 函式,zero 既有測試回歸
# ════════════════════════════════════════════════════════════════
def compute_five_bucket_summary(
    indicators: Optional[dict],
    phase_info: Optional[dict] = None,
    news_items: Optional[list] = None,
) -> dict:
    """五桶 summary(4-horizon + 新聞)。

    擴充自 compute_four_horizon_summary,直接呼叫它取 4 桶,再算第 5 桶。
    不複製計算邏輯,避免兩處飄移。

    第 5 桶「新聞」邏輯:
    - news_items=None(尚未抓取)→ gray「未掃描」
    - 數 is_systemic 命中數,依 shared.macro_buckets SSOT 閾值分級
      (NEWS_SYSTEMIC_YELLOW_COUNT=1,NEWS_SYSTEMIC_RED_COUNT=2)
    - 對齊 Stock 五桶 bar 第 5 桶語意

    Returns
    -------
    dict 同 compute_four_horizon_summary 結構,多 "news" key:
      {"long": {...}, "mid": {...}, "short": {...}, "inflection": {...},
       "news": {level, label, headline, color, emoji}}
    """
    _summary = compute_four_horizon_summary(indicators, phase_info)

    _level_to_color = {"green": _C_GREEN, "yellow": _C_YELLOW, "red": _C_RED,
                       "gray": "#6e7681"}
    _level_to_emoji = {"green": "🟢", "yellow": "🟡", "red": "🔴", "gray": "⬜"}

    if news_items is None:
        _summary["news"] = {
            "level": "gray", "label": "未掃描",
            "headline": "尚未抓取 RSS 新聞",
            "color": _level_to_color["gray"], "emoji": _level_to_emoji["gray"],
        }
        return _summary

    # 數 is_systemic 命中(對齊 news_repository.SYSTEMIC_RISK_KEYWORDS 標記)
    try:
        _sys_count = sum(1 for n in news_items
                         if isinstance(n, dict) and n.get("is_systemic"))
    except Exception:
        _sys_count = 0

    # 讀 SSOT 閾值(v19.144 shared.macro_buckets)
    try:
        from shared.macro_buckets import (
            NEWS_SYSTEMIC_YELLOW_COUNT, NEWS_SYSTEMIC_RED_COUNT,
        )
    except Exception:
        NEWS_SYSTEMIC_YELLOW_COUNT, NEWS_SYSTEMIC_RED_COUNT = 1, 2

    if _sys_count >= NEWS_SYSTEMIC_RED_COUNT:
        _n_level, _n_label = "red", "系統性警報"
        _n_headline = f"🚨 {_sys_count} 則系統性風險新聞(戰爭/倒閉/崩盤)"
    elif _sys_count >= NEWS_SYSTEMIC_YELLOW_COUNT:
        _n_level, _n_label = "yellow", "風險新聞"
        _n_headline = f"🚨 {_sys_count} 則系統性風險新聞,留意"
    else:
        _n_level, _n_label = "green", "無系統風險"
        _n_total = len(news_items)
        _n_headline = (f"{_n_total} 則新聞掃描,無系統性風險" if _n_total > 0
                       else "新聞掃描完成,無命中")

    _summary["news"] = {
        "level": _n_level, "label": _n_label, "headline": _n_headline,
        "color": _level_to_color[_n_level], "emoji": _level_to_emoji[_n_level],
    }
    return _summary


def render_five_bucket_bar(summary: dict) -> None:
    """頂部五桶 summary bar(5 columns × emoji+燈號+1句)。

    順序鎖定:🌳 長期 → 📈 中期 → 🎯 短線 → ⚠️ 拐點 → 📰 新聞
    對齊 Stock v18.284 五桶 bar 語意,Fund 第 5 桶為新聞(Stock 是籌碼)。

    向下相容:若 summary 沒有 "news" key(e.g. 仍用 4-horizon)→ fallback
    為 4 columns,避免空白格。
    """
    _has_news = isinstance(summary.get("news"), dict) and summary["news"]
    _order = [
        ("long",       "🌳 長期", "regime / 結構"),
        ("mid",        "📈 中期", "景氣循環"),
        ("short",      "🎯 短線", "即時 risk-off"),
        ("inflection", "⚠️ 拐點", "領先警報"),
    ]
    if _has_news:
        _order.append(("news", "📰 新聞", "系統性風險"))

    _cols = st.columns(len(_order))
    for _col, (_key, _title, _sub) in zip(_cols, _order):
        _d = summary.get(_key) or {}
        _color = _d.get("color", "#888")
        _emoji = _d.get("emoji", "⚪")
        _label = _d.get("label", "—")
        _headline = _d.get("headline", "")
        with _col:
            st.markdown(
                f"""<div style="border-left:4px solid {_color};padding:10px 14px;background:rgba(255,255,255,0.03);border-radius:6px;margin-bottom:6px;">
<div style="font-size:0.78em;color:#888;letter-spacing:0.5px;">{_sub}</div>
<div style="font-size:1.05em;font-weight:600;margin-top:2px;">{_emoji} {_title}: <span style="color:{_color};">{_label}</span></div>
<div style="font-size:0.85em;color:#bbb;margin-top:4px;line-height:1.4;">{_headline}</div>
</div>""",
                unsafe_allow_html=True,
            )
