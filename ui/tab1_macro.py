"""ui/tab1_macro.py — 總經位階評估 Tab（v18.127 B-C.5）

從 app.py 抽出 Tab1（總經位階評估 ＆ 拐點偵測）的渲染邏輯。

設計：
- render_macro_tab() -> None **零閉包依賴**（與其他 4 個 tab 相同）
- 外部 helper 處理：
  * _update_data_registry() → caller 先 call
  * _calc_data_health / _friendly_error → 從 ui.helpers.session import
  * _now_tw / FRED_KEY / GEMINI_KEY → 本地 / env
  * render_indicator_map → 本檔內私有 helper（從 app.py 搬入）

對外 API:
- render_macro_tab() -> None
"""
from __future__ import annotations

import datetime
import os
import time as _time_mod
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from shared.colors import (
    BG_DARK_AMBER_1,
    BG_DARK_AMBER_2,
    BG_DARK_NAVY_4,
    BG_DARK_RED_1,
    BG_DARK_RED_2,
    GH_BG_CARD,
    GH_BG_PRIMARY,
    GH_BORDER,
    GH_FG_MUTED,
    GH_FG_PRIMARY,
    GH_FG_SECONDARY,
    GRAY_44,
    GRAY_55,
    GRAY_66,
    GRAY_AA,
    GRAY_CC,
    MATERIAL_GREEN,
    MATERIAL_ORANGE,
    MATERIAL_RED,
    MD_AMBER_300,
    MD_BLUE_300,
    MD_GREEN_A200,
    MD_GREEN_A400,
    MD_ORANGE_A200,
    MD_PURPLE_500,
    STREAMLIT_BG,
    TRAFFIC_GREEN,
    TRAFFIC_NEUTRAL,
    TRAFFIC_RED,
    TRAFFIC_YELLOW,
    WHITE,
)

from fund_fetcher import (
    fetch_market_news,
    set_risk_free_rate,
)
from services.macro import (
    backtest_turning_points,
    calc_macro_phase,
    detect_systemic_risk,
    detect_turning_points,
    fetch_all_indicators,
)
from ui.components.mk_clock import render_mk_clock_section
from ui.helpers.session import (
    calc_data_health as _calc_data_health_pure,
    friendly_error as _friendly_error,
)
from shared.macro_thresholds_v2 import (  # F-GRAY-4 v19.169 + v19.179 PMI
    HY_SPREAD_THRESHOLDS as _HY_THR,
    PMI_THRESHOLDS as _PMI_THR,
)
_PMI_SITUATION_BELOW = _PMI_THR["alert_generation"]["contraction_below"]  # 50.0(L3 situation card 用)
from shared.signal_thresholds import (
    CFNAI_RECESSION_THRESHOLD,
    SAHM_RECESSION_THRESHOLD,
)

_TW_TZ = ZoneInfo("Asia/Taipei")


# ════════════════════════════════════════════════════════════════
# v19.132 — 拐點偵測 sparkline 指標特定 threshold 線
# 對齊 §1 Fail Loud 顯示原則:一看就知道有沒有超過 threshold
# SSOT:SAHM 0.5 / CFNAI -0.7 from signal_thresholds.py
# F-GRAY-4 v19.169: HY 由 shared/macro_thresholds_v2.py SSOT 提供 (SPEC §16.2)
# - warn (yellow): stoplight.yellow_below = 6.0
# - crisis: beginner_panic.panic_above = 8.0(教學經驗值,2008/3 / 2020/3 高點)
# ════════════════════════════════════════════════════════════════
_HY_WARN_THRESHOLD: float = _HY_THR["stoplight"]["yellow_below"]
_HY_CRISIS_THRESHOLD: float = _HY_THR["beginner_panic"]["panic_above"]


def _tp_threshold_lines(key: str) -> list[tuple[float, str, str, str]]:
    """回傳該拐點指標的 horizontal threshold lines。

    Returns list of (y_value, dash_style, line_color, annotation_text)。
    無 threshold 的 key 回傳空 list(例:無自然零點的 indicator)。
    """
    if key == "pmi_diff":
        return [(0.0, "dot", TRAFFIC_NEUTRAL, "擴張/收縮 0")]
    if key == "yield_curve":
        return [(0.0, "dot", TRAFFIC_RED, "倒掛 0")]
    if key == "hy_spread":
        return [
            (_HY_WARN_THRESHOLD, "dot", TRAFFIC_YELLOW, f"警戒 {_HY_WARN_THRESHOLD}%"),
            (_HY_CRISIS_THRESHOLD, "dash", TRAFFIC_RED, f"危機 {_HY_CRISIS_THRESHOLD}%"),
        ]
    if key == "sahm_rule":
        return [(SAHM_RECESSION_THRESHOLD, "dash", TRAFFIC_RED,
                 f"衰退鎖定 {SAHM_RECESSION_THRESHOLD}")]
    if key == "lei_cfnai":
        return [(CFNAI_RECESSION_THRESHOLD, "dash", TRAFFIC_RED,
                 f"衰退鎖定 {CFNAI_RECESSION_THRESHOLD}")]
    return []


def _apply_tp_thresholds(spfig, key: str) -> None:
    """對 sparkline figure 加上該指標的 threshold lines + annotation。"""
    for _y, _dash, _color, _txt in _tp_threshold_lines(key):
        spfig.add_hline(
            y=_y, line_dash=_dash, line_color=_color, line_width=1.5,
            opacity=0.7,
            annotation_text=_txt,
            annotation_position="top right",
            annotation_font=dict(size=9, color=_color),
        )


# ════════════════════════════════════════════════════════════════
# v19.133 — 短線雷達 10 燈 sparkline + threshold lines
# threshold 對齊 services.risk_radar 各 signal 函式內部 cut-off 值
# ════════════════════════════════════════════════════════════════

def _radar_threshold_lines(key: str) -> list[tuple[float, str, str, str]]:
    """回傳該 radar 信號的 horizontal threshold lines。

    對齊 services/risk_radar.py 內部判斷邊界。
    無 natural threshold 的 key 回傳空 list。
    """
    if key == "vix_level":
        # services L103-L105:cur >= 30 紅 / cur >= 25 黃
        return [(25.0, "dot", TRAFFIC_YELLOW, "警戒 25"),
                (30.0, "dash", TRAFFIC_RED, "恐慌 30")]
    if key == "vix_term_struct":
        # services L341-L343:cur >= 1.10 紅 / cur >= 1.00 黃 (backwardation = panic)
        return [(1.00, "dot", TRAFFIC_YELLOW, "倒掛 1.00"),
                (1.10, "dash", TRAFFIC_RED, "極端 1.10")]
    if key == "hy_oas_delta":
        # trend 顯示 HY OAS level %;對齊拐點桶 6/8% threshold(SSOT MACRO_THRESHOLDS)
        return [(_HY_WARN_THRESHOLD, "dot", TRAFFIC_YELLOW, f"警戒 {_HY_WARN_THRESHOLD}%"),
                (_HY_CRISIS_THRESHOLD, "dash", TRAFFIC_RED, f"危機 {_HY_CRISIS_THRESHOLD}%")]
    if key == "move_level":
        # services L426-L428:cur >= 130 紅 / cur >= 110 黃
        return [(110.0, "dot", TRAFFIC_YELLOW, "警戒 110"),
                (130.0, "dash", TRAFFIC_RED, "高 130")]
    if key == "sector_rotation":
        # services L532-L534:cur >= 1.20 紅(XLP/XLY)/ cur >= 1.00 黃
        return [(1.00, "dot", TRAFFIC_YELLOW, "防禦領 1.00"),
                (1.20, "dash", TRAFFIC_RED, "極防禦 1.20")]
    if key == "put_call_ratio":
        # PCR > 1.0 較看空,> 1.5 極端恐慌(教學常見值)
        return [(1.00, "dot", TRAFFIC_YELLOW, "看空 1.0"),
                (1.50, "dash", TRAFFIC_RED, "恐慌 1.5")]
    # v19.188 — 🌳 長期座標桶 美股流動性卡片 SPEC 線
    # cut-off 全部 import 自 services.us_liquidity_engine（與各 fetcher 的 color/label 同源 SSOT）
    if key in ("us_hy_oas", "us_m2_yoy", "us_rrp", "us_aaii"):
        try:
            from services.us_liquidity_engine import (
                HY_OAS_WARN_PCT, HY_OAS_CRISIS_PCT,
                M2_YOY_LOOSE_PCT, M2_YOY_HOT_PCT,
                RRP_DRAIN_BN,
                AAII_EUPHORIA_PCT, AAII_PANIC_PCT,
            )
        except Exception:
            return []
        if key == "us_hy_oas":
            return [(HY_OAS_WARN_PCT, "dot", TRAFFIC_YELLOW, f"警戒 {HY_OAS_WARN_PCT}%"),
                    (HY_OAS_CRISIS_PCT, "dash", TRAFFIC_RED, f"緊縮 {HY_OAS_CRISIS_PCT}%")]
        if key == "us_m2_yoy":
            return [(M2_YOY_LOOSE_PCT, "dot", TRAFFIC_GREEN, f"寬鬆 {M2_YOY_LOOSE_PCT}%"),
                    (M2_YOY_HOT_PCT, "dash", TRAFFIC_RED, f"過熱 {M2_YOY_HOT_PCT}%")]
        if key == "us_rrp":
            return [(RRP_DRAIN_BN, "dash", TRAFFIC_YELLOW, f"枯竭 {RRP_DRAIN_BN:.0f}B")]
        if key == "us_aaii":
            return [(AAII_EUPHORIA_PCT, "dash", TRAFFIC_RED, f"過熱 +{AAII_EUPHORIA_PCT:.0f}"),
                    (AAII_PANIC_PCT, "dot", TRAFFIC_GREEN, f"恐慌 {AAII_PANIC_PCT:.0f}")]
    # 其他 key(yield_10y_shock / spx_trend_break / sox_drop / asia_overnight
    #          / us_walcl / us_hyg_lqd:delta-based,無 natural level threshold)
    # trend 為絕對 level 而判斷用 delta,無單一 natural threshold,跳過 hline
    return []


def _make_radar_sparkline(trend: list, key: str, color: str):
    """產生 radar 卡用的迷你 sparkline + threshold lines。

    輸入:
      trend: 近 6-8 期數值 list
      key:   radar signal key(決定 threshold)
      color: 主線色(取卡片 signal color)
    """
    if not trend or len(trend) < 2:
        return None
    try:
        import plotly.graph_objects as _go_r
        _fig = _go_r.Figure()
        _fig.add_trace(_go_r.Scatter(
            y=trend, mode="lines+markers",
            line=dict(color=color, width=2),
            marker=dict(size=4, color=color),
            showlegend=False,
            hovertemplate="%{y:.2f}<extra></extra>",
        ))
        # threshold lines (指標特定)
        for _y, _dash, _color, _txt in _radar_threshold_lines(key):
            _fig.add_hline(
                y=_y, line_dash=_dash, line_color=_color, line_width=1.2,
                opacity=0.65,
                annotation_text=_txt,
                annotation_position="top right",
                annotation_font=dict(size=8, color=_color),
            )
        _fig.update_layout(
            height=70,
            margin=dict(l=2, r=2, t=2, b=2),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(visible=False, fixedrange=True),
            yaxis=dict(visible=False, fixedrange=True),
            showlegend=False,
        )
        return _fig
    except Exception:
        return None


# v19.187 — 燈號 → 卡片邊框色(中期 Z-Score / 長期桶卡片共用,對齊短線雷達色票)
_MACRO_CARD_LIGHT_COLOR = {
    "red": TRAFFIC_RED, "orange": MD_ORANGE_A200, "yellow": TRAFFIC_YELLOW,
    "green": TRAFFIC_GREEN, "gray": TRAFFIC_NEUTRAL,
}


def _render_macro_indicator_card(title: str, signal: str, color: str,
                                 value_str: str, note: str, label: str,
                                 trend, spark_key: str) -> None:
    """v19.187 — 通用總經指標卡(複製短線雷達卡格式:燈號 + 值 + 白話 + mini sparkline)。

    user 2026-06-27:基金短線雷達為範本,長期/中期桶也改成小圖+SPEC 卡片。
    本 helper 與短線雷達卡視覺一致(同 HTML 結構 + 同 _make_radar_sparkline),
    供長期/中期桶複用。**須在 `with st.columns(...)[i]:` 區塊內呼叫**(streamlit 容器)。
    trend 為近 6-8 期 list;spark_key 決定 sparkline 的 SPEC threshold 線(無則純線)。
    """
    import streamlit as _st_c
    _st_c.markdown(
        f"<div style='background:{GH_BG_PRIMARY};border:2px solid {color};"
        f"border-radius:10px;padding:10px 12px 6px;margin:4px 0;min-height:150px;"
        f"display:flex;flex-direction:column;justify-content:space-between'>"
        f"<div>"
        f"<div style='color:{TRAFFIC_NEUTRAL};font-size:10px;letter-spacing:1px'>{title}</div>"
        f"<div style='color:{color};font-size:15px;font-weight:800;margin:4px 0 6px'>{signal}</div>"
        f"<div style='color:{WHITE};font-weight:700;font-size:14px'>值 {value_str}</div>"
        f"</div>"
        f"<div style='color:{GRAY_AA};font-size:9px;border-top:1px solid {GH_BORDER};"
        f"padding-top:4px;margin-top:4px;line-height:1.3'>{note}"
        f"<br/><span style='color:{GRAY_55}'>{label}</span></div>"
        f"</div>", unsafe_allow_html=True)
    _sp = _make_radar_sparkline(trend, spark_key, color)
    if _sp is not None:
        _st_c.plotly_chart(_sp, use_container_width=True,
                           key=f"mcard_sp_{spark_key}",
                           config={"displayModeBar": False})


def _now_tw():
    return datetime.datetime.now(_TW_TZ)


def _calc_data_health(indicators=None):
    """同 app.py wrapper。"""
    ind = indicators if indicators is not None else st.session_state.get("indicators", {})
    return _calc_data_health_pure(ind)


def render_indicator_map() -> None:
    """以 Sankey 圖視覺化「強勢經濟 / 升息劇本」的因果鏈：
       PMI 強勁 → 通膨升溫 → 央行維持高利率 → 殖利率飆升
       → ⓐ 借貸成本增 → 科技/成長股承壓
       → ⓑ 債券下跌

    v18.127: 從 app.py 搬入（原 line 1262），Tab1 私有 helper。
    內容 byte-for-byte 同 app.py 原版（v18.67 pad/thickness/height 縮小設定）。
    """
    labels = [
        "0.PMI 強勁", "1.通膨升溫", "2.維持高利率", "3.殖利率飆升",
        "4.借貸成本增", "5.科技/成長承壓", "6.債券下跌",
    ]
    node_colors = [
        "#3498db", "#f39c12", "#e67e22", "#e74c3c",
        "#c0392b", "#c0392b", "#c0392b",
    ]
    fig = go.Figure(data=[go.Sankey(
        # v18.67: pad/thickness 縮小讓圖更緊湊
        node=dict(pad=10, thickness=14, label=labels, color=node_colors,
                  line=dict(width=0)),
        link=dict(
            source=[0, 1, 2, 3, 3, 4],
            target=[1, 2, 3, 4, 6, 5],
            value =[5, 5, 4, 3, 4, 3],
            color="rgba(189, 195, 199, 0.4)",
        ),
    )])
    fig.update_layout(
        height=220, margin=dict(l=0, r=0, t=8, b=4),
        font=dict(size=10),
    )
    st.plotly_chart(fig, use_container_width=True)


# ════════════════════════════════════════════════
# v19.15：即時訊號燈 + 決策矩陣
# ════════════════════════════════════════════════
_ACTION_BADGE_BG = {
    "持有": "#374151",
    "加碼": "#7f1d1d",
    "減倉": "#7c2d12",
    "全撤": "#991b1b",
}
_ACTION_BADGE_FG = {
    "持有": "#d1d5db",
    "加碼": "#fecaca",
    "減倉": "#fed7aa",
    "全撤": "#fecaca",
}


def _enrich_fund_for_decision(_f: dict) -> dict:
    """從 portfolio_funds 條目擷取 verdict_to_actions 需要的欄位（複用 tab3 邏輯）.

    產出：{code, name, is_core, invest_twd, sigma_info, dividend_info}
    σ 位階 / 配息覆蓋率算法與 tab3_portfolio.py 既有 `_compute_advice_for` 同步。
    """
    code = _f.get("code", "?") or "?"
    name = (_f.get("name") or code)[:30]

    # is_core 沿用 P3 邏輯：Sheet policy_tier 優先，缺則 fallback flag
    _tier = (_f.get("policy_tier") or "").lower()
    if _tier == "core":
        is_core = True
    elif _tier == "satellite":
        is_core = False
    else:
        is_core = bool(_f.get("is_core"))

    sigma_info = None
    _series = _f.get("series")
    if _series is not None and hasattr(_series, "dropna") and len(_series.dropna()) >= 30:
        try:
            from services.precision_service import calc_hwm_sigma_levels as _hwm_fn
            sigma_info = _hwm_fn(_series, lookback=252)
        except Exception as _se:  # noqa: BLE001
            sigma_info = {"error": str(_se)[:60]}

    div_info = None
    try:
        _mj = _f.get("moneydj_raw", {}) or {}
        _metrics = _f.get("metrics", {}) or {}
        _tret = float(_mj.get("perf", {}).get("1Y") or _metrics.get("ret_1y") or 0)
        _dyld = float(_mj.get("moneydj_div_yield") or _metrics.get("annual_div_rate") or 0)
        if _dyld > 0:
            from fund_fetcher import div_safety_check
            div_info = div_safety_check(_tret, _dyld)
    except Exception:
        div_info = None

    return {
        "code": code,
        "name": name,
        "is_core": is_core,
        "invest_twd": float(_f.get("invest_twd", 0) or 0),
        "sigma_info": sigma_info,
        "dividend_info": div_info,
    }


def _render_china_drag_panel(phase_dict: dict | None,
                             fred_api_key: str = "") -> None:
    """v19.118 中國拖累唯讀面板 — 4 個數字 + regime + FX 警示。

    顯示 China 副盤對主分的乘法 modifier 結果,但**不改變**任何既有 UI 數字:
    panel 只 READ phase['score'](0-10),COMPUTE multiplier + composite,RENDER NEW markdown。
    既有的 verdict 大卡 / 戰情室 / 4 欄導航卡 score 顯示完全不動。

    顯示:
      - 主分(總經): phase['score'] / 10 (既有口徑,不重算)
      - 中國副盤:   china_subscore   / 100 (0=最差,100=最好)
      - 乘子:       multiplier ∈ [0.7, 1.0]
      - 折扣後:     phase['score'] × multiplier (顯示同 0-10 scale)
      - 4 級 regime + USDCNY fx_alert(若有)

    §1 fail loud:
      - fred_api_key 缺 → 顯示 '⬜ 未設 FRED key,跳過'
      - china_subscore=None(5 條 series 全敗)→ 顯示 '⬜ 中國資料不足'
      - 任何例外 → caption error,不擋整個 tab(由 caller try/except 包覆)

    §8.2 分層:本函式 lazy import L2 services.macro_service.get_china_snapshot,
              無 L1 直呼,無需 EX-PASSTHRU-1 例外。
    """
    _ph = phase_dict or {}
    _main_score_10 = _ph.get("score")  # 0-10 scale

    # AppTest / 缺 key 守衛(對齊 _render_macro_navigator L277)
    if not fred_api_key or len(str(fred_api_key).strip()) < 30:
        st.caption("🇨🇳 中國拖累 China Drag:⬜ 未設 FRED key,跳過")
        return
    if _main_score_10 is None:
        st.caption("🇨🇳 中國拖累 China Drag:⬜ 等待 FRED 載入主分")
        return

    # ── L2 取數 + 計算 ───────────────────────────────────────────
    from services.macro import (
        apply_china_modifier,
        classify_china_regime,
        compute_china_subscore,
        get_china_snapshot,
    )
    _snap = get_china_snapshot(fred_api_key)
    if not _snap:
        st.caption("🇨🇳 中國拖累 China Drag:⬜ 中國資料不足(5 條 series 全敗)")
        return

    _china_sub = compute_china_subscore(_snap)
    _china_score = _china_sub.get("score") if _china_sub else None
    _regime = classify_china_regime(_china_sub) if _china_sub else None
    _regime_label = _regime.get("regime") if _regime else "—"
    _regime_color = _regime.get("color") if _regime else TRAFFIC_NEUTRAL
    _fx_alert = _regime.get("fx_alert") if _regime else None

    # 將 main 從 0-10 scale 升到 0-100 餵 modifier(modifier 要求 0-100)
    _mod = apply_china_modifier(_main_score_10 * 10.0, _china_score)
    if _mod is None:
        st.caption("🇨🇳 中國拖累 China Drag:⬜ 計算失敗")
        return

    _multiplier = _mod["multiplier"]
    # composite 換回 0-10 scale 顯示
    _composite_10 = _mod["composite"] / 10.0

    # ── 渲染:4-column 唯讀卡 ──────────────────────────────────────
    st.markdown(
        f'<div style="border-left:4px solid {_regime_color};padding:8px 12px;'
        f'background:#fafafa;margin:8px 0;border-radius:4px;">'
        f'<b>🇨🇳 中國拖累 China Drag</b>  '
        f'<span style="color:{_regime_color};font-weight:bold;">{_regime_label}</span>'
        f'{("  ⚠️ " + _fx_alert) if _fx_alert else ""}'
        f'</div>',
        unsafe_allow_html=True,
    )
    _c1, _c2, _c3, _c4 = st.columns(4)
    with _c1:
        st.metric("主分(總經)", f"{_main_score_10:+.2f} / 10")
    with _c2:
        if _china_score is None:
            st.metric("中國副盤", "—")
        else:
            st.metric("中國副盤", f"{_china_score:.1f} / 100")
    with _c3:
        st.metric("乘子", f"{_multiplier:.3f}",
                  help="0.7~1.0,中國越差扣得越多,只懲罰不加成")
    with _c4:
        st.metric("折扣後主分", f"{_composite_10:+.2f} / 10",
                  delta=f"{_composite_10 - _main_score_10:+.2f}",
                  delta_color="inverse")
    st.caption(
        "ℹ️ 唯讀展示:本面板**不改變**上方總經分數,僅示意「若 China 副盤納入主分」的折扣強度。"
        "資料源:5 條 FRED OECD MEI(CLI/PMI/CPI/M2/USDCNY)。"
    )


def _render_macro_navigator(indicators: dict | None,
                            phase_dict: dict | None,
                            fred_api_key: str = "") -> None:
    """v19.45 總經導航卡 — 上方 4 欄 verdict 摘要，對齊台股「震盪整理｜謹慎觀望」UX。

    一眼看到 4 個面板結論（總經 / 短線 / 拐點 / 美林時鐘），下方 ①②④MK 完整面板
    仍保留供細節查看。零 IO 衝擊（radar/inflection 重用 ttl cache）。
    """
    # ── 1. 🌍 總經 verdict（① 戰情室同源：phase + composite score）─────
    _ph = phase_dict or {}
    _ph_label = _ph.get("phase") or "資料不足"
    _ph_score = _ph.get("score")
    _ph_alloc = _ph.get("alloc") or _ph.get("allocation") or "—"
    _ph_advice = _ph.get("advice") or ""
    _ph_color = _ph.get("color") or TRAFFIC_NEUTRAL
    _ph_icon = _ph.get("icon") or "🌍"
    if _ph_score is None:
        _ph_metric = "等待 FRED 載入"
    else:
        _ph_metric = f"分數 {_ph_score:+.2f} ｜ 建議 {_ph_alloc}"

    # ── 2. ⚡ 短線 verdict（④ 短線雷達同源：summarize_radar）──────────
    _rd_level = "—"
    _rd_metric = "等待 FRED 載入"
    _rd_color = TRAFFIC_NEUTRAL
    _rd_icon = "⬜"
    _rd_action = "FRED API key 未設或抓取失敗"
    if fred_api_key and len(str(fred_api_key).strip()) >= 30:
        # v19.49：僅撈 session_state（由 spinner block 預先並行抓好），不重抓
        _cache = st.session_state.get("_radar_v1921_top")
        if _cache is None:
            _rd_action = "等待上方「載入總經資料」按鈕完成"
        else:
            _r, _rs = _cache
            if _rs is not None:
                _rd_level = _rs.get("level", "—")
                _rd_color = _rs.get("color", TRAFFIC_NEUTRAL)
                _rd_icon = {"平靜": "🟢", "警戒": "🟡",
                            "警報": "🔴", "極端警報": "🔴"}.get(_rd_level, "⬜")
                _rd_metric = (f"🔴 {_rs.get('red',0)} ｜ 🟡 {_rs.get('yellow',0)} "
                              f"｜ 🟢 {_rs.get('green',0)} ｜ ⬜ {_rs.get('gray',0)}")
                _rd_action = {
                    "平靜": "10 燈無急殺訊號",
                    "警戒": "短線轉緊，留意波動",
                    "警報": "急殺進行中，降槓桿",
                    "極端警報": "立即減倉防守",
                }.get(_rd_level, "—")

    # ── 3. 🎯 拐點 verdict（② 拐點同源：detect_turning_points 計票）────
    _tp_label = "—"
    _tp_metric = "等待 FRED 載入"
    _tp_color = TRAFFIC_NEUTRAL
    _tp_icon = "⬜"
    _tp_detail = "FRED API key 未設或抓取失敗"
    if fred_api_key and len(str(fred_api_key).strip()) >= 30:
        try:
            # v19.49：僅撈 session_state（由 spinner block 預先並行抓好），不重抓
            _tp = st.session_state.get("_tp_v1948_top")
            if _tp:
                # 5 個拐點訊號計票（pmi_diff / yield_curve / hy_spread / sahm_rule / lei_cfnai）
                _tp_hit = 0
                _tp_total = 0
                for _k in ("pmi_diff", "yield_curve", "hy_spread", "sahm_rule", "lei_cfnai"):
                    _sig = (_tp.get(_k) or {}).get("signal", "")
                    if not _sig or "⬜" in _sig or "資料不足" in _sig:
                        continue
                    _tp_total += 1
                    # 命中：拐點訊號 emoji（🚀 / ⚠️ / 🌟 / 🔭 等非綠色狀態）
                    if any(x in _sig for x in ("🚀", "⚠️", "🌟", "🔭", "拐點", "反彈", "翻揚")):
                        _tp_hit += 1
                _tp_metric = f"訊號命中 {_tp_hit} / {_tp_total}"
                if _tp_total == 0:
                    _tp_label = "資料不足"
                    _tp_color = TRAFFIC_NEUTRAL
                    _tp_icon = "⬜"
                    _tp_detail = "5 個拐點訊號全 ⬜"
                elif _tp_hit >= 2:
                    _tp_label = "拐點訊號"
                    _tp_color = "#fbc02d"
                    _tp_icon = "🎯"
                    _tp_detail = "≥2 訊號同向，留意景氣翻轉"
                elif _tp_hit == 1:
                    _tp_label = "單一警示"
                    _tp_color = MD_GREEN_A200
                    _tp_icon = "🟢"
                    _tp_detail = "僅 1 訊號，雜訊機率高"
                else:
                    _tp_label = "無拐點"
                    _tp_color = MD_GREEN_A200
                    _tp_icon = "🟢"
                    _tp_detail = "5 訊號均無翻轉特徵"
        except Exception as _te:  # noqa: BLE001
            _tp_detail = f"inflection err: {type(_te).__name__}"

    # ── 4. 🕐 美林時鐘 verdict（MK 時鐘同源：classify_phase 四象限）────
    _mk_label = "資料不足"
    _mk_metric = "—"
    _mk_color = TRAFFIC_NEUTRAL
    _mk_icon = "❓"
    _mk_advice = "PMI / CPI 缺資料"
    try:
        from ui.components.mk_clock import classify_phase
        _mk_key, _mk_meta = classify_phase(indicators or {})
        if _mk_key and _mk_meta:
            _mk_label = _mk_meta.get("zh", "—")
            _mk_color = _mk_meta.get("color", TRAFFIC_NEUTRAL)
            _mk_icon = _mk_meta.get("icon", "❓")
            _mk_metric = f"股 {_mk_meta.get('alloc_eq','—')}% ／ 債 {_mk_meta.get('alloc_bd','—')}%"
            _mk_advice = _mk_meta.get("advice", "")[:50]  # 截斷避免卡片過長
    except Exception as _me:  # noqa: BLE001
        _mk_advice = f"mk err: {type(_me).__name__}"

    # ── 渲染 4 欄 ──────────────────────────────────────────────────────
    def _card(title: str, icon: str, label: str, color: str,
              metric: str, detail: str) -> str:
        return (
            f'<div style="background:{GH_BG_PRIMARY};border:2px solid {color};'
            f'border-radius:10px;padding:12px 14px;min-height:140px;'
            f'box-shadow:0 1px 3px rgba(0,0,0,0.3);">'
            f'<div style="color:{GH_FG_MUTED};font-size:12px;margin-bottom:4px;'
            f'font-weight:600;">{icon} {title}</div>'
            f'<div style="color:{color};font-size:20px;font-weight:800;'
            f'line-height:1.2;margin:4px 0;">{label}</div>'
            f'<div style="color:{GH_FG_SECONDARY};font-size:13px;margin-top:6px;">{metric}</div>'
            f'<div style="color:{GH_FG_MUTED};font-size:11px;margin-top:6px;'
            f'line-height:1.5;">{detail}</div>'
            f'</div>'
        )

    st.markdown(
        f'<div style="font-size:13px;color:{GH_FG_MUTED};margin:8px 0 6px 0;'
        'font-weight:600;">🧭 總經導航卡 — 上方 4 面板 verdict 速覽</div>',
        unsafe_allow_html=True,
    )
    _nv1, _nv2, _nv3, _nv4 = st.columns(4)
    with _nv1:
        st.markdown(_card("總經", "🌍", _ph_label, _ph_color,
                          _ph_metric, _ph_advice[:60]),
                    unsafe_allow_html=True)
    with _nv2:
        st.markdown(_card("短線雷達", "⚡", _rd_level, _rd_color,
                          _rd_metric, _rd_action),
                    unsafe_allow_html=True)
    with _nv3:
        st.markdown(_card("拐點偵測", "🎯", _tp_label, _tp_color,
                          _tp_metric, _tp_detail),
                    unsafe_allow_html=True)
    with _nv4:
        st.markdown(_card("美林時鐘", _mk_icon, _mk_label, _mk_color,
                          _mk_metric, _mk_advice),
                    unsafe_allow_html=True)
    st.caption("↓ 下方為 ① 戰情室 / ④ 短線雷達 / ② 拐點偵測 / MK 時鐘 完整面板")


def _render_beginner_dashboard(indicators: dict | None, fred_api_key: str = "") -> None:
    """✨ v19.17：新手友善總經面板 — 接在 tab header 後、v19.15 進階區之前。

    v19.21：頂部結論大卡升級為「雙速合議」— 慢總經 ｜ 短線雷達 ｜ 合議行動。
    fred_api_key 為空或 <30 字元時自動 fallback 回 v19.17 單頭 banner（AppTest 保護）。

    3 區塊：
      1. ✨ 結論大卡（v19.21 雙速合議三卡 | fallback v19.17 漸層 banner）
      2. 🎯 為什麼是這位階？（top 3 driver bullet + 教學）
      3. 📚 本期使用 N 個關鍵指標（每張卡 inline 教學 + how_to_read 表）

    指標排序：按 |contribution|=|score×weight| 降序取 top_n=8 個。
    weight 已由 calculate_composite_score 內部 apply_weight_overrides 套用 active.json
    → 自然落實「動態：讀回測核可組合」需求。

    indicators 為 None / 空 → 顯式 hint 提示按 sidebar 載入。
    """
    try:
        from services.macro_explain import build_beginner_payload
        from ui.components.macro_card_edu import MACRO_EDU
    except ImportError:
        return

    payload = build_beginner_payload(indicators, MACRO_EDU, top_n=8)
    if not payload["ready"]:
        st.info("⏳ 尚未載入總經資料 — 請按 sidebar「📡 載入總經資料」後，本面板將自動帶入即時判讀與教學。")
        return

    # ════════════════════════════════════════════════
    # 區塊 1：結論大卡 — v19.21 雙速合議（慢總經 ｜ 短線雷達 ｜ 合議行動）
    # ════════════════════════════════════════════════
    _color = payload["verdict_color"]
    _icon = payload["verdict_icon"]
    _level = payload["verdict_level"]
    _score = payload["score"]
    _action = payload["verdict_action_text"]
    _n_total = payload["n_total"]

    # 雷達計算 — 快取到 session_state，下方 ③ 拐點區的雷達 5×2 卡片區改讀快取（零新增網路呼叫）
    _radar_top = None
    _radar_sum_top = None
    if fred_api_key and len(str(fred_api_key).strip()) >= 30:
        _cache = st.session_state.get("_radar_v1921_top")
        if _cache is None:
            try:
                from services.risk_radar import detect_risk_radar, summarize_radar
                _r = detect_risk_radar(fred_api_key)
                _rs = summarize_radar(_r)
                st.session_state["_radar_v1921_top"] = (_r, _rs)
                _radar_top, _radar_sum_top = _r, _rs
            except Exception:  # noqa: BLE001
                st.session_state["_radar_v1921_top"] = (None, None)
        else:
            _radar_top, _radar_sum_top = _cache

    if _radar_sum_top is None:
        # Fallback：雷達不可用（無 key / 抓取失敗）→ 退回 v19.17 單頭漸層 banner
        st.markdown(
            f"""
            <div style="background: linear-gradient(90deg, {_color}22, {_color}11);
                        border-left: 6px solid {_color}; border-radius: 8px;
                        padding: 18px 22px; margin: 10px 0;">
              <div style="font-size: 14px; color: {TRAFFIC_NEUTRAL}; margin-bottom: 4px;">
                ✨ 目前總經位階（綜合 {_n_total} 項指標 score × 權重）
              </div>
              <div style="font-size: 30px; font-weight: 700; color: {_color}; line-height: 1.2;">
                {_icon} {_level}
                <span style="font-size: 20px; color: {GRAY_AA}; margin-left: 14px;">score = {_score:+.2f}</span>
              </div>
              <div style="font-size: 15px; color: {GRAY_CC}; margin-top: 8px;">
                🎯 {_action}
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        # v19.21 雙頭並列 + 全寬合議
        from services.risk_radar import synthesize_dual_verdict
        _r_level = _radar_sum_top["level"]
        _r_color = _radar_sum_top["color"]
        _r_icon = {"平靜": "🟢", "警戒": "🟡", "警報": "🔴", "極端警報": "🔴"}.get(_r_level, "⬜")
        _r_red = _radar_sum_top["red"]
        _r_yel = _radar_sum_top["yellow"]
        _r_grn = _radar_sum_top["green"]
        _r_gry = _radar_sum_top["gray"]
        _syn = synthesize_dual_verdict(_level, _score, _color, _icon, _action, _r_level)

        _col_slow, _col_radar = st.columns(2)
        with _col_slow:
            st.markdown(
                f"""
                <div style="background: linear-gradient(90deg, {_color}22, {_color}11);
                            border-left: 6px solid {_color}; border-radius: 8px;
                            padding: 14px 18px; margin: 6px 0; min-height: 132px;">
                  <div style="font-size: 13px; color: {TRAFFIC_NEUTRAL}; margin-bottom: 4px;">
                    🐌 慢總經位階（{_n_total} 項指標 × 權重 ｜ 月～季級）
                  </div>
                  <div style="font-size: 26px; font-weight: 700; color: {_color}; line-height: 1.2;">
                    {_icon} {_level}
                    <span style="font-size: 17px; color: {GRAY_AA}; margin-left: 12px;">score = {_score:+.2f}</span>
                  </div>
                  <div style="font-size: 13px; color: {GRAY_AA}; margin-top: 6px;">
                    📊 完整逐檔 driver 見下方「為什麼是這位階」
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with _col_radar:
            st.markdown(
                f"""
                <div style="background: linear-gradient(90deg, {_r_color}22, {_r_color}11);
                            border-left: 6px solid {_r_color}; border-radius: 8px;
                            padding: 14px 18px; margin: 6px 0; min-height: 132px;">
                  <div style="font-size: 13px; color: {TRAFFIC_NEUTRAL}; margin-bottom: 4px;">
                    ⚡ 短線雷達（10 燈 1-day 動量／情緒 ｜ 日級）
                  </div>
                  <div style="font-size: 26px; font-weight: 700; color: {_r_color}; line-height: 1.2;">
                    {_r_icon} {_r_level}
                  </div>
                  <div style="font-size: 13px; color: {GRAY_AA}; margin-top: 6px;">
                    🔴 {_r_red} ｜ 🟡 {_r_yel} ｜ 🟢 {_r_grn} ｜ ⬜ {_r_gry} ｜ 詳見下方雷達卡片
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # 合議行動全寬卡
        st.markdown(
            f"""
            <div style="background: linear-gradient(90deg, {_syn['color']}33, {_syn['color']}11);
                        border: 2px solid {_syn['color']}; border-radius: 10px;
                        padding: 16px 22px; margin: 6px 0 14px 0;">
              <div style="font-size: 13px; color: {TRAFFIC_NEUTRAL}; margin-bottom: 4px;">
                🤝 雙速合議（mode={_syn['mode']}）
              </div>
              <div style="font-size: 24px; font-weight: 800; color: {_syn['color']}; line-height: 1.2;">
                {_syn['icon']} {_syn['level']}
              </div>
              <div style="font-size: 14px; color: #ddd; margin-top: 8px; line-height: 1.5;">
                🎯 {_syn['action']}
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )



def _render_tw_local_dashboard(indicators: dict | None,
                                fred_api_key: str = "") -> None:
    """📊 v19.25：台股本地視角 — 長期 12M ｜ 短期 1Q 雙判讀。

    接在 `_render_beginner_dashboard`（雙速合議＝全球視角）之後、進階檢視之前，
    補上台股獨有的 NDC 景氣燈號 / TW PMI / 出口 YoY / 外資連續日數判讀。

    資料流：
      v19.24 fetcher × 4  →  v19.23 純函式 (long/short regime)  →  雙欄渲染
        (NDC / TW PMI / Export YoY / FII streak)

    MK 黃金拐點走 indicators["CPI"]/["FED_RATE"] value+prev，全球與本地共用。
    任一 fetcher 失敗會 graceful 在卡片上顯示 source/error，整段不爆。

    AppTest 保護：fred_api_key < 30 字元視為測試環境 → 跳過 4 個 HTTP fetcher
    （FinMind ~15s × 4 會撞破 AppTest 240s 預算）。真實 FRED key 為 32 字元。
    """
    if not indicators:
        return
    if not fred_api_key or len(str(fred_api_key).strip()) < 30:
        return
    try:
        from services.macro_tw_local import (
            classify_long_term_regime,
            classify_short_term_regime,
            detect_mk_golden_inflection,
        )
        # v19.197 P1-4:macro_tw_local_fetch 已下沉 repositories/macro_tw_local_repository
        from repositories.macro_tw_local_repository import (
            fetch_foreign_consecutive_days,
            fetch_ndc_signal_history,
            fetch_tw_export_yoy,
            fetch_tw_pmi_local,
        )
    except ImportError:
        return

    cpi    = (indicators.get("CPI") or {})
    fed    = (indicators.get("FED_RATE") or {})
    vix    = (indicators.get("VIX") or {})
    cpi_v  = cpi.get("value")
    cpi_p  = cpi.get("prev")
    fed_v  = fed.get("value")
    fed_p  = fed.get("prev")
    vix_v  = vix.get("value")

    try:
        ndc_d    = fetch_ndc_signal_history()
        pmi_d    = fetch_tw_pmi_local()
        export_d = fetch_tw_export_yoy()
        fii_d    = fetch_foreign_consecutive_days()
    except Exception as _e:  # noqa: BLE001
        st.warning(f"📊 台股本地視角：fetcher 載入失敗（{_e}）— 跳過本區塊")
        return

    # v19.63：stash 台灣本地總經 + 外資連續日數給 data_registry 監控
    try:
        st.session_state["_macro_tw_local"] = {
            "tw_pmi":     {"value": pmi_d.get("value"),
                           "date":  pmi_d.get("date_latest", "")},
            "ndc_signal": {"score": ndc_d.get("score_latest"),
                           "date":  ndc_d.get("date_latest", "")},
            "tw_export":  {"yoy":   export_d.get("value"),
                           "date":  export_d.get("date_latest", "")},
            "fi_streak":  {"consec_days": fii_d.get("consec_days"),
                           "date":        fii_d.get("date_latest", "")},
        }
    except Exception:
        pass

    ndc_score   = ndc_d.get("score_latest")
    tw_pmi      = pmi_d.get("value")
    export_yoy  = export_d.get("value")
    fi_streak   = fii_d.get("consec_days")

    mk = detect_mk_golden_inflection(cpi_v, cpi_p, fed_v, fed_p)
    long_v  = classify_long_term_regime(cpi_v, fed_v, fed_p, ndc_score, tw_pmi, mk)
    short_v = classify_short_term_regime(export_yoy, tw_pmi, vix_v, fi_streak,
                                         cpi_v, cpi_p)

    st.markdown("### 📊 台股本地視角（12M 長期 ｜ 1Q 短期）")
    st.caption(
        "鏡像 stock dashboard 的 NDC 景氣燈號 / TW PMI / 出口 YoY / 外資連續日數判讀，"
        "與上方「全球慢總經 × 短線雷達」互補。"
    )

    _c1, _c2 = st.columns(2)
    with _c1:
        with st.container(border=True):
            st.markdown(
                f"<div style='padding:8px 4px 4px;border-left:6px solid {long_v['color']};"
                f"background:linear-gradient(90deg,{long_v['color']}22 0%,transparent 80%);'>"
                f"<div style='font-size:12px;color:{GH_FG_MUTED}'>🏔️ 長期 12M ｜ 景氣大循環</div>"
                f"<div style='font-size:22px;font-weight:700;color:{long_v['color']}'>"
                f"{long_v['regime']}</div>"
                f"<div style='font-size:13px;color:{GH_FG_SECONDARY};margin-top:4px'>"
                f"得分：<b>{long_v['score']:+.2f}</b> ｜ 建議持股：<b>{long_v['suggest_pct']}</b></div>"
                f"<div style='font-size:12px;color:{GH_FG_MUTED};margin-top:6px'>{long_v['detail']}</div>"
                "</div>", unsafe_allow_html=True)
            with st.expander("📐 評分拆解（components）", expanded=False):
                if long_v.get("components"):
                    for _name, _pts, _wt in long_v["components"]:
                        _emoji = "🟢" if _pts > 0 else ("🔴" if _pts < 0 else "⚪")
                        st.markdown(f"- {_emoji} **{_name}**：{_pts:+d} 分（權重 {_wt}%）")
                else:
                    st.caption("⚪ 資料全空，無加權項")

    with _c2:
        with st.container(border=True):
            st.markdown(
                f"<div style='padding:8px 4px 4px;border-left:6px solid {short_v['color']};"
                f"background:linear-gradient(90deg,{short_v['color']}22 0%,transparent 80%);'>"
                f"<div style='font-size:12px;color:{GH_FG_MUTED}'>⚡ 短期 1Q ｜ 財報季偏向</div>"
                f"<div style='font-size:22px;font-weight:700;color:{short_v['color']}'>"
                f"{short_v['regime']}</div>"
                f"<div style='font-size:13px;color:{GH_FG_SECONDARY};margin-top:4px'>"
                f"得分：<b>{short_v['score']:+.2f}</b> ｜ 建議行動：<b>{short_v.get('action','—')}</b></div>"
                f"<div style='font-size:12px;color:{GH_FG_MUTED};margin-top:6px'>{short_v['detail']}</div>"
                "</div>", unsafe_allow_html=True)
            with st.expander("📐 評分拆解（components）", expanded=False):
                if short_v.get("components"):
                    for _name, _pts, _wt in short_v["components"]:
                        _emoji = "🟢" if _pts > 0 else ("🔴" if _pts < 0 else "⚪")
                        st.markdown(f"- {_emoji} **{_name}**：{_pts:+d} 分（權重 {_wt}%）")
                else:
                    st.caption("⚪ 資料全空，無加權項")

    with st.expander("📡 資料來源 + 拐點訊號", expanded=False):
        _rows = [
            ("NDC 景氣對策信號",       ndc_d, ndc_d.get("score_latest"), "分"),
            ("台 PMI",                  pmi_d, pmi_d.get("value"),         ""),
            ("出口 YoY",                export_d, export_d.get("value"),   "%"),
            ("外資連續日數",            fii_d, fii_d.get("consec_days"),   "日"),
        ]
        for _label, _d, _val, _unit in _rows:
            _src = _d.get("source") or "—"
            _dt  = _d.get("date_latest") or "—"
            _err = _d.get("error")
            _inf = _d.get("inflection") or "—"
            if _err:
                st.markdown(f"- **{_label}**：⚠️ {_err}")
            else:
                _vs = f"{_val}{_unit}" if _val is not None else "—"
                st.markdown(
                    f"- **{_label}**：{_vs} ｜ 拐點：{_inf} ｜ 來源：{_src} ｜ 最新：{_dt}"
                )
        if mk is not None:
            st.markdown(
                f"- **MK 黃金拐點**：{mk['icon']} {mk['label']}（{mk['strength']}）— {mk['detail']}"
            )
        else:
            st.caption("MK 黃金拐點：無訊號或 CPI/Fed 資料不足")
    st.divider()


def _render_realtime_decision_dashboard(indicators: dict | None) -> None:
    """🎯 v19.15：即時訊號燈 + 決策矩陣 — 接在 tab header 後、tabs 前。

    3 區塊：
      1. 頂部即時 verdict 大卡（icon + level + 分數 + 配置建議）
      2. 7 cluster 燈 quick view（reuse compute_cluster_signals）
      3. 逐檔決策矩陣表（funds 為空 → 顯式提示）

    indicators 為 None / macro_done=False → 完全不渲染（噪音零）。
    """
    if not indicators:
        return
    try:
        from services.realtime_signal import compute_realtime_dashboard
    except ImportError:
        return

    _pf_all = st.session_state.get("portfolio_funds", []) or []
    _pf_loaded = [f for f in _pf_all if isinstance(f, dict) and f.get("loaded")]
    _enriched = [_enrich_fund_for_decision(f) for f in _pf_loaded]

    dash = compute_realtime_dashboard(indicators, _enriched)
    if not dash.get("ready"):
        return

    st.markdown("### 🎯 即時訊號 + 決策矩陣（v19.15）")
    st.caption("總經 verdict 套用 active 權重後 → 5 級分檔 × 個股 σ/配息訊號 → 逐檔持有/加碼/減倉/全撤")

    # ── 區塊 1：頂部 verdict 大卡 ─────────────────────────────
    icon = dash["verdict_icon"]
    level = dash["verdict_level"]
    color = dash["verdict_color"]
    score = dash["score"]
    action_text = dash["verdict_action_text"]

    st.markdown(
        f"<div style='background:linear-gradient(90deg,{color}22,{color}11);"
        f"border-left:6px solid {color};border-radius:8px;padding:14px 18px;margin:8px 0 12px'>"
        f"<div style='font-size:13px;color:{GRAY_AA};margin-bottom:4px'>📌 當前總經 verdict</div>"
        f"<div style='font-size:24px;color:{color};font-weight:700;margin-bottom:6px'>"
        f"{icon} {level}　<span style='font-size:18px;color:{GH_FG_PRIMARY}'>score = {score:+.2f}</span></div>"
        f"<div style='font-size:14px;color:{GH_FG_PRIMARY};line-height:1.55'>{action_text}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # v19.18: 7 cluster 燈 quick view 已移除（戰情首頁 ① 有完整 F1 校準版本，避免視覺重複）
    # 此處只留 verdict 大卡（區塊 1）+ 決策矩陣（區塊 3）

    # ── 區塊 3：逐檔決策矩陣表 ────────────────────────────────
    actions = dash.get("fund_actions") or []
    summary = dash.get("actions_summary") or {}
    if not actions:
        st.info("ℹ️ 尚無已載入基金 — 至「📦 投資組合」載入後本表會自動填入")
        return

    n_total = summary.get("n_total", 0)
    n_add = summary.get("n_add", 0)
    n_hold = summary.get("n_hold", 0)
    n_reduce = summary.get("n_reduce", 0)
    n_exit = summary.get("n_exit", 0)
    st.caption(
        f"📋 {n_total} 檔分析 → "
        f"加碼 **{n_add}** / 持有 **{n_hold}** / 減倉 **{n_reduce}** / 全撤 **{n_exit}**"
    )

    # 用 DataFrame 渲染（無 plotly / 純 markdown 風險）
    import pandas as _pd
    df = _pd.DataFrame([
        {
            "代碼": a["code"],
            "名稱": a["name"],
            "角色": "🏛️ 核心" if a["is_core"] else "🚀 衛星",
            "建議": a["action"],
            "權重": f"{a['target_pct']}%",
            "原因": a["reason"],
        }
        for a in actions
    ])

    def _row_style(row):
        action = row["建議"]
        bg = _ACTION_BADGE_BG.get(action, "#1f2937")
        fg = _ACTION_BADGE_FG.get(action, GH_FG_PRIMARY)
        return [f"background-color: {bg}; color: {fg};" if c == "建議" else "" for c in row.index]

    st.dataframe(
        df.style.apply(_row_style, axis=1),
        use_container_width=True,
        hide_index=True,
    )

    # v19.22.1 hotfix：本函式可能被外層 expander 包覆（render_macro_tab L716），
    # Streamlit 禁止 nested expanders → 沿用 v17.2 慣例改用 st.container(border=True)
    with st.container(border=True):
        st.markdown("**💡 動作對照表 + 邊界規則**")
        st.markdown(
            "- **持有 (100%)** — 維持原配置\n"
            "- **加碼 (130%)** — 跌深 + 多頭環境 / 衛星在極度樂觀區\n"
            "- **減倉 (50%)** — 衛星進入悲觀 / 核心進入極度悲觀 / 過熱停利 / 吃本金 1 級保守化\n"
            "- **全撤 (0%)** — 衛星在極度悲觀 / 過熱 + 風險升 / 吃本金 2 級保守化\n\n"
            "**個股訊號覆寫**：\n"
            "- σ ≤ −2 + 樂觀/極度樂觀 → 升級加碼\n"
            "- σ ≤ −2 + 悲觀/極度悲觀 → 不接刀，沿用 verdict 預設\n"
            "- σ > +1 + 樂觀類 + 衛星 → 分批停利（減倉）\n"
            "- 配息吃本金（含息 < 配息）→ 動作往保守方向 bump 一級"
        )


def render_macro_tab() -> None:
    """渲染總經位階評估 ＆ 拐點偵測 Tab（最大塊 ~1.8k 行）。

    Caller 不需傳參數；FRED_KEY/GEMINI_KEY 走 os.environ。
    """
    FRED_KEY = os.environ.get("FRED_API_KEY", "")
    GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")

    # v18.139: _update_data_registry 已搬到 ui/helpers/data_registry.py
    # 改正規 import 取代 v18.129 sys.modules['__main__'] hack
    from ui.helpers.data_registry import _update_data_registry

    st.markdown("## 🌐 總經位階評估 ＆ 拐點偵測")

    from ui.helpers.story_nav import render_story_nav
    render_story_nav("macro")
    st.caption("策略3 三層指標加權方法論 v7 — 領先×2 | 中級×1 | 次級×0.5")

    # v18.174：「🗺️ 全局指標關聯地圖」整塊搬到「說明書 §10」（純教學圖，無動態資料）
    # 函數 render_indicator_map() 保留在本檔頂層供 tab6 import 復用

    if not FRED_KEY:
        st.warning("⚠️ 請在 Streamlit Cloud Secrets 填入 FRED_API_KEY")
    else:
        _last_upd = st.session_state.get("macro_last_update")
        if _last_upd:
            _age_h   = (_now_tw() - _last_upd).total_seconds() / 3600
            _upd_str = _last_upd.strftime("%Y-%m-%d %H:%M")
            if _age_h > 4:
                # v16.0 異常遮罩：原 warning 會讓新手以為程式壞掉，改溫馨提示
                st.info(f"ℹ️ 指標數據已 {_age_h:.1f} 小時未更新（上次：{_upd_str}），點擊下方「🔄 更新總經資料」即可同步最新數據。")
            else:
                st.caption(f"🕐 最後從 FRED 抓取：{_upd_str}（{_age_h:.1f} 小時前）")
        else:
            st.info("💡 尚未載入總經資料，點擊下方按鈕開始")

        # v19.50：載入按鈕拆雙鈕 — 一般載入（吃既有 cache）／ 強制重抓（保證最新）
        _btn_cols = st.columns([3, 2])
        with _btn_cols[0]:
            _btn_label = "🔄 更新總經資料" if st.session_state.macro_done else "📡 載入總經資料"
            _do_load = st.button(_btn_label, type="primary", key="btn_macro_load")
        with _btn_cols[1]:
            _force_reload = st.button(
                "🆕 強制重抓最新（清快取）",
                key="btn_macro_force",
                help="v19.57 C1：僅清 Tab1（總經）快取 + radar/tp session 殘留，"
                     "其他 Tab（基金詳情/組合/模擬器）不受影響")
        if _force_reload:
            try:
                from services.macro import clear_tab1_macro_caches
                _clr = clear_tab1_macro_caches(session_state=st.session_state)
                st.toast(
                    f"✅ Tab1 精準清快取：TTL {_clr['ttl_cleared']} 條 / "
                    f"st_cache {_clr['st_cache_cleared']} 條 / "
                    f"session {_clr['session_keys_popped']} 鍵",
                    icon="🆕")
            except Exception:
                pass
            st.session_state.macro_done = False
            _do_load = True  # 同流程跑下方 spinner block
        if _do_load:
            # v19.49：合併 2 spinner 為 1，並用 ThreadPoolExecutor(max_workers=4) 並行抓取
            # indicators / news / radar / turning_points → wallclock = max(各 IO 時間)
            # navigator + 下方面板共享 session_state cache，零重抓
            with st.spinner("📡 並行抓取 總經指標 + 新聞 + 雷達 + 拐點..."):
                _t0_macro = _time_mod.time()
                from concurrent.futures import ThreadPoolExecutor as _TPE_ml
                _has_fred = bool(FRED_KEY) and len(str(FRED_KEY).strip()) >= 30
                with _TPE_ml(max_workers=4) as _ex_ml:
                    _fu_ind  = _ex_ml.submit(fetch_all_indicators, FRED_KEY)
                    _fu_news = _ex_ml.submit(fetch_market_news, max_per_feed=5)
                    if _has_fred:
                        from services.risk_radar import (
                            detect_risk_radar, summarize_radar,
                        )
                        _fu_radar = _ex_ml.submit(detect_risk_radar, FRED_KEY)
                        _fu_tp    = _ex_ml.submit(detect_turning_points, FRED_KEY)
                    else:
                        _fu_radar = None
                        _fu_tp = None
                    try:
                        ind = _fu_ind.result()
                    except Exception as _me:
                        ind = {}
                        _friendly_error(
                            "總經指標載入失敗", _me,
                            hint="多半是 NAS proxy 連線異常或來源暫時無回應；"
                                 "可按側欄「🔍 測試 Proxy 連線」確認，或稍後重試。",
                            level="error")
                    try:
                        _news = _fu_news.result()
                    except Exception as _ne:
                        _news = []
                        _friendly_error(
                            "新聞掃描暫時失敗", _ne,
                            hint="不影響總經指標分析，可稍後重試；本次僅以指標面綜合判讀。",
                            level="info")
                    if _fu_radar is not None:
                        try:
                            _r_pre  = _fu_radar.result()
                            _rs_pre = summarize_radar(_r_pre)
                            st.session_state["_radar_v1921_top"] = (_r_pre, _rs_pre)
                        except Exception:
                            st.session_state["_radar_v1921_top"] = (None, None)
                    if _fu_tp is not None:
                        try:
                            st.session_state["_tp_v1948_top"] = _fu_tp.result()
                        except Exception:
                            st.session_state["_tp_v1948_top"] = None
                _macro_ms = round((_time_mod.time() - _t0_macro) * 1000)
                if not ind:
                    st.error(
                        f"❌ 沒有抓到任何總經指標（0 個，耗時 {_macro_ms}ms）。"
                        "多半是 NAS proxy 不通／逾時或來源被擋——"
                        "請按側欄「🔍 測試 Proxy 連線」確認後再重試。")
                else:
                    phase = calc_macro_phase(ind)
                    # v19.141 P0:強制重抓會 pop phase_info(macro_service._TAB1_SESSION_KEYS),
                    # 屬性存取 st.session_state.phase_info 在此路徑會 AttributeError 炸 production。
                    # 改用 .get() 對齊 line 1218 既有的 v19.69 J1 防禦慣例。
                    old_phase = (st.session_state.get("phase_info") or {}).get("phase", "")
                    new_phase = phase.get("phase", "")
                    if old_phase and old_phase != new_phase:
                        # phase_history 雖未被 clear_tab1_macro_caches pop,但同步以 .get() 防初始化未跑路徑
                        _hist = st.session_state.get("phase_history")
                        if _hist is None:
                            st.session_state.phase_history = []
                            _hist = st.session_state.phase_history
                        _hist.append(
                            {"from":old_phase,"to":new_phase,
                             "date":datetime.date.today().isoformat(),
                             "score":phase.get("score",0)})
                    st.session_state.indicators        = ind
                    st.session_state.prev_phase        = old_phase
                    st.session_state.phase_info        = phase
                    st.session_state.macro_done        = True
                    st.session_state.macro_last_update = _now_tw()
                    if "FED_RATE" in ind:
                        set_risk_free_rate(ind["FED_RATE"].get("value",4.0) / 100)
                    _update_data_registry()
                    _lat_log = st.session_state.get("api_latency_log", [])
                    _lat_log.append({
                        "label":    _now_tw().strftime("%H:%M"),
                        "macro_ms": _macro_ms,
                        "moneydj_ms": None,
                        "yf_ms":      None,
                    })
                    st.session_state["api_latency_log"] = _lat_log[-24:]
                    # 系統性風險用已抓好的 _news（CPU 計算 <100ms，無需 spinner）
                    st.session_state.news_items = _news
                    try:
                        _srd = detect_systemic_risk(_news)
                        st.session_state.systemic_risk_data = _srd
                        _rl = _srd.get("risk_level","LOW")
                        _rs_sc = _srd.get("risk_score",0)
                        st.info(
                            f"📰 已掃描 {len(_news)} 則新聞｜系統性風險："
                            f"{_srd.get('risk_icon','⬜')} {_rl}（評分 {_rs_sc}）")
                    except Exception:
                        st.session_state.systemic_risk_data = None
                    st.success(
                        f"✅ 已抓取 {len(ind)} 個指標！"
                        f"（{_now_tw().strftime('%H:%M')} TW｜{_macro_ms}ms）")

    # ── v17.0 移除新手/老手 toggle（單軌完整版）──────────────────
    # 設計原則：所有資訊一律展開，不藏；每個指標附完整教學（白話/判讀/搭配/上下游/歷史）
    # 與 24 個月趨勢圖（含警戒線），讓 AI 與新人都能正確判讀。
    # `_expert_mode` 變數保留供下游引用，恆為 True。
    _expert_mode  = True
    _show_l2_plus = True
    _show_l3      = True
    st.session_state["view_mode"] = "🔬 完整版（教學手冊 + 趨勢圖 + 量化數據）"

    if st.session_state.macro_done:
        ind   = st.session_state.indicators
        st.session_state["_macro_ind"] = ind
        phase = st.session_state.get("phase_info") or {}  # v19.69 J1：防 None→KeyError
        if "phase" not in phase:
            st.warning("⚠️ 市場相位資料缺失，請重新按「更新總經資料」")
            return

        # ════════════════════════════════════════════════════════════
        # v19.128 — 四時域重組:刪除 v19.125 三層 toggle(新手/進階/專家)
        # User 2026-06-25 反饋:只保留專家,新手模式 / 進階模式 / 原理教室全刪;
        # 改為四時域(長期/中期/短線/拐點)分組架構。
        # 詳見下方 render_four_horizon_bar + 四個分組 subheader。
        # ════════════════════════════════════════════════════════════

        ph    = phase["phase"]  # v19.39 PR1C: sc / ph_c 在 archive 後不再使用
        alloc = phase["alloc"];  advice = phase.get("advice","")

        # v19.50 ══ 📊 資料新鮮度條（總抓取時間 + age + 各區塊資料截止日）══
        _ml_upd = st.session_state.get("macro_last_update")
        if _ml_upd is not None:
            _age_min_ml = (_now_tw() - _ml_upd).total_seconds() / 60
            _age_color_ml = (TRAFFIC_GREEN if _age_min_ml < 60
                             else (TRAFFIC_YELLOW if _age_min_ml < 240 else TRAFFIC_RED))
            _age_label_ml = (f'{int(_age_min_ml)} 分鐘前' if _age_min_ml < 60
                             else f'{_age_min_ml/60:.1f} 小時前')
            # 各區塊資料截止日（從 ind 各 indicator 的 date 欄取）
            _src_dates = []
            for _k_src, _lbl_src in (("PMI", "PMI"), ("YIELD_10Y2Y", "10Y-2Y"),
                                     ("HY_SPREAD", "HY"), ("CPI", "CPI"),
                                     ("UNRATE", "UNRATE")):
                _v_src = (ind or {}).get(_k_src) or {}
                _d_src = str(_v_src.get("date", "")).strip()
                if _d_src:
                    _src_dates.append(f'{_lbl_src}:{_d_src}')
            _src_str = ' ｜ '.join(_src_dates) if _src_dates else '—'
            _radar_cache = st.session_state.get("_radar_v1921_top")
            _radar_ready = bool(_radar_cache and _radar_cache[0])
            _tp_ready = bool(st.session_state.get("_tp_v1948_top"))
            # v19.56 B2: 5 條 FRED 個別命中狀態 chip（DGS10 / DGS2 / DGS3MO / HY OAS / M2SL）
            # v19.60 D1: chip 改吃 realtime_start（BLS/FED 真實發布日）算新鮮度，
            # fallback 回 observation date；hover tooltip 顯示「資料月份 / 發布日 / 延遲」
            _fred_srcs = (ind or {}).get("_fred_sources") or {}
            _today_d = _now_tw().date()
            def _fred_chip(_sid: str, _short: str, _daily: bool) -> str:
                _meta = _fred_srcs.get(_sid) or {}
                if not _meta.get("success"):
                    return f'<span title="{_sid} 抓取失敗">{_short}:🔴失敗</span>'
                _obs = str(_meta.get("last_date", "")).strip()
                _rt = str(_meta.get("realtime_start", "")).strip()
                _lag = _meta.get("publish_lag_days")
                _src_date = _rt if _rt else _obs   # 優先用發布日，fallback obs date
                if not _src_date:
                    return f'<span title="{_sid} 日期缺失">{_short}:⬜未知</span>'
                try:
                    _ld = pd.to_datetime(_src_date).date()
                    _age_d = (_today_d - _ld).days
                except Exception:
                    return f'<span title="{_sid} 日期解析失敗">{_short}:⬜未知</span>'
                if _daily:
                    _emoji = '🟢' if _age_d <= 4 else ('🟠' if _age_d <= 14 else '🔴')
                else:
                    _emoji = '🟢' if _age_d <= 40 else ('🟠' if _age_d <= 70 else '🔴')
                # hover tooltip：資料月份 / 發布日 / 延遲（HTML title attr）
                _tip_parts = [f'{_sid}']
                if _obs:
                    _tip_parts.append(f'資料月份 {_obs}')
                if _rt:
                    _tip_parts.append(f'發布 {_rt}')
                if _lag is not None:
                    _tip_parts.append(f'延遲 {_lag}d')
                _tip = ' ｜ '.join(_tip_parts)
                _src_label = '發布' if _rt else 'obs'
                return f'<span title="{_tip}">{_short}:{_emoji}{_age_d}d({_src_label})</span>'
            _chip_d10 = _fred_chip("DGS10", "DGS10", True)
            _chip_d2  = _fred_chip("DGS2",  "DGS2",  True)
            _chip_d3m = _fred_chip("DGS3MO", "DGS3MO", True)
            _chip_hy  = _fred_chip("BAMLH0A0HYM2", "HY", True)
            _chip_m2  = _fred_chip("M2SL", "M2", False)
            _fred_chip_line = ' ｜ '.join([_chip_d10, _chip_d2, _chip_d3m, _chip_hy, _chip_m2])
            _fred_degraded = (
                bool(_fred_srcs) and any(
                    (not (_fred_srcs.get(_sid) or {}).get("success"))
                    or ('🔴' in _fred_chip(_sid, _s, _d))
                    for _sid, _s, _d in (
                        ("DGS10", "DGS10", True), ("DGS2", "DGS2", True),
                        ("DGS3MO", "DGS3MO", True), ("BAMLH0A0HYM2", "HY", True),
                        ("M2SL", "M2", False),
                    )
                )
            )
            st.markdown(
                f'<div style="background:{GH_BG_PRIMARY};border-left:4px solid {_age_color_ml};'
                f'border-radius:4px;padding:8px 14px;margin-bottom:8px;font-size:11px;'
                f'color:{GH_FG_MUTED};line-height:1.6;">'
                f'📊 <b>資料新鮮度</b>　'
                f'🕐 抓取：<b style="color:{GH_FG_SECONDARY};">{_ml_upd.strftime("%Y-%m-%d %H:%M")}</b>　'
                f'⏱️ <span style="color:{_age_color_ml};font-weight:700;">{_age_label_ml}</span>　'
                f'📡 來源：FRED + Yahoo<br/>'
                f'📅 月頻截止：<span style="color:{GH_FG_SECONDARY};">{_src_str}</span>　'
                f'⚡ 雷達：{"🟢 已載入" if _radar_ready else "⬜ 未載入"}　'
                f'🎯 拐點：{"🟢 已載入" if _tp_ready else "⬜ 未載入"}<br/>'
                f'📡 <b>FRED 命中</b>：<span style="color:{GH_FG_SECONDARY};">{_fred_chip_line}</span>'
                f'</div>', unsafe_allow_html=True)
            if _age_min_ml > 240:
                st.warning(
                    f'⚠️ 總經資料已 {_age_label_ml} 未更新，FRED 月頻指標可能已過期，'
                    f'建議按上方「🆕 強制重抓最新」清快取後重新載入。')
            if _fred_degraded:
                st.caption(
                    '🟠 部分 FRED 序列失敗或過期（🔴 = API miss 或太舊），對應指標 / 雷達燈 / 拐點可能缺失；'
                    '建議按上方「🆕 強制重抓最新」清快取重試。'
                )


        # ══ v19.118 中國拖累唯讀面板（China Drag）═════════════════════
        # 4 數字唯讀展示:不改變上方總經分數,僅示意 China 副盤折扣強度
        try:
            _render_china_drag_panel(phase, FRED_KEY)
        except Exception as _cd_e:  # noqa: BLE001
            print(f"[tab1/china_drag] {type(_cd_e).__name__}: {_cd_e}")


        # v19.41 MOVED: ③ 🔬 即時訊號 + 決策矩陣 已移至 tab 內結尾（MK 時鐘前）
        # 改動原因：user 反饋「總經、短期、拐點 三個面板 — 總經放在最上方」，
        # ③ expander 原位於 tab 外擋在 ① 戰情室（總經）之前，下移後 tab 首屏即為總經面板

        # ══ v17.3 內層 Tab：戰情首頁（§6-6 資訊不藏匿）═══
        # v19.40 PR2: 📖 指標教學手冊 已搬至 📖 說明書 Tab §11 宏觀教學文獻
        # v19.42: 單一 tab 包裝拆除 — Streamlit tab strip 擋在 ① 戰情室（總經）前
        #         user 反饋「總經放在最上方」三度仍不見效 → 直接消滅 tab strip
        #         以 contextlib.nullcontext() 取代，所有 `with tab_main:` 區塊保持縮排不動
        import contextlib as _cl_v1942
        tab_main = _cl_v1942.nullcontext()

        # ══ v19.188 — 🩺 綜合健康度 hero 卡(對齊台股「綜合健康度」體驗)══
        # user 2026-06-27:基金總經頂部補綜合健康度。
        # 用 23 指標加權 composite(active.json 權重)+ composite_verdict 5 級白話。
        # 與下方五桶 bar 互補不重複:此為「多空加權淨分」,五桶燈1為「景氣循環階段(0-10 phase)」。
        try:
            from ui.helpers.macro_helpers import (
                calculate_composite_score, composite_verdict,
            )
            _comp_score = calculate_composite_score(ind)
            _cv_icon, _cv_level, _cv_color, _cv_action = composite_verdict(_comp_score)
            st.markdown(
                f"<div style='background:linear-gradient(135deg,{GH_BG_PRIMARY},{GH_BG_CARD});"
                f"border:2px solid {_cv_color};border-radius:12px;padding:14px 20px;margin:0 0 12px;"
                f"display:flex;align-items:center;gap:20px'>"
                f"<div style='flex-shrink:0;text-align:center;min-width:96px'>"
                f"<div style='font-size:11px;color:{GH_FG_MUTED};letter-spacing:1px'>綜合健康度</div>"
                f"<div style='font-size:42px;font-weight:900;color:{_cv_color};line-height:1.1'>{_comp_score:+.1f}</div>"
                f"<div style='font-size:10px;color:#484f58'>23 指標加權淨分<br>🌎 美股 / 全球總經</div>"
                f"</div>"
                f"<div style='flex:1;min-width:0'>"
                f"<div style='font-size:22px;font-weight:900;color:{_cv_color}'>{_cv_icon} {_cv_level}</div>"
                f"<div style='font-size:13px;color:{GH_FG_SECONDARY};margin-top:4px;line-height:1.5'>{_cv_action}</div>"
                f"</div></div>",
                unsafe_allow_html=True)
        except Exception as _comp_e:  # noqa: BLE001
            st.caption(f"綜合健康度卡暫無法顯示：[{type(_comp_e).__name__}] {_comp_e}")

        # ══ v19.146 — 📊 五桶 summary bar(頂部一覽:長期/中期/短線/拐點/新聞)══
        # 對齊 Stock v18.284 五桶 bar 體驗,Fund 加 📰 新聞為第 5 桶(讀 v19.144 SSOT)。
        # news_items=None 時自動降級為 ⬜「未掃描」,點開「執行 AI 裁決」抓 RSS 後燈亮。
        # render_five_bucket_bar 對無 news key 的 summary 會 fallback 為 4 columns,
        # 任何異常(包括 import 失敗)走 except 降級為文字提示。
        try:
            from ui.helpers.macro_beginner_view import (
                compute_five_bucket_summary,
                render_five_bucket_bar,
            )
            _news_items = st.session_state.get("news_items")
            _5b_summary = compute_five_bucket_summary(ind, phase, news_items=_news_items)
            render_five_bucket_bar(_5b_summary)
            st.divider()
        except Exception as _e_5b:
            st.warning(f"五桶 summary 渲染失敗(降級):{_e_5b}")

        with tab_main:
            # v19.18: 原 ① verdict 大卡已移除（與頂部新手面板 + 進階檢視 expander 重複）



            # v19.134 物理重排:60/40 col layout 已移除,sections 按四時域分組連續


            # ══════════════════════════════════════════════════════════
            # v19.134 — 🌳 長期座標 桶(物理重排,連續區塊)
            # v19.262 P3-A5:整 section 抽 ui/tab1_macro_longterm.py(-294 LOC)
            # ══════════════════════════════════════════════════════════
            from ui.tab1_macro_longterm import render_long_term_section
            render_long_term_section(ind, fred_key=FRED_KEY, show_l3=_show_l3)

            # ══════════════════════════════════════════════════════════
            # v19.134 — 📈 中期循環 桶(物理重排,連續區塊)
            # v19.262 P3-A3:整 section 抽 ui/tab1_macro_midcycle.py(-180 LOC)
            # ══════════════════════════════════════════════════════════
            from ui.tab1_macro_midcycle import render_mid_cycle_section
            render_mid_cycle_section(ind, show_l3=_show_l3, show_l2_plus=_show_l2_plus)


            # ══════════════════════════════════════════════════════════
            # v19.134 — 🎯 短線雷達 桶(物理重排,連續區塊)
            # v19.262 P3-A4:整 section 抽 ui/tab1_macro_radar.py(-246 LOC)
            # ══════════════════════════════════════════════════════════
            from ui.tab1_macro_radar import render_short_radar_section
            render_short_radar_section(fred_key=FRED_KEY, show_l3=_show_l3)

            # ══════════════════════════════════════════════════════════
            # v19.134 — ⚠️ 拐點警報 桶(物理重排,連續區塊)
            # v19.262 P3-A6:整 section 抽 ui/tab1_macro_inflection.py(-484 LOC)
            # ══════════════════════════════════════════════════════════
            from ui.tab1_macro_inflection import render_inflection_alert_section
            render_inflection_alert_section(ind, phase=phase, fred_key=FRED_KEY, show_l3=_show_l3)

            # ══════════════════════════════════════════════════════════
            # v19.134 — 📋 即時訊號 + 決策矩陣 桶(物理重排,連續區塊)
            # ══════════════════════════════════════════════════════════
            st.divider()
            st.markdown("## 📋 即時訊號 + 決策矩陣")
            st.caption("跨時域殿後 ｜ verdict 路徑 + 逐檔行動建議")


            # ── v19.41 ③ 🔬 即時訊號決策矩陣（v19.15 verdict + 逐檔行動建議） ──
            # 原位於 tab 外（L799），下移至 tab 內結尾 → 讓 ① 戰情室（總經）成為 tab 首屏
            st.divider()
            with st.expander(
                "③ 🔬 即時訊號 + 決策矩陣（C-2 verdict 路徑｜逐檔行動建議）",
                expanded=False,
            ):
                _render_realtime_decision_dashboard(ind)
            # ── AI 結構化總經摘要 ── L3 only

            # ══════════════════════════════════════════════════════════
            # v19.134 — 🤖 AI 景氣判斷總結 桶(物理重排,連續區塊)
            # ══════════════════════════════════════════════════════════
            st.divider()
            # v19.261 P3-A2:🤖 AI 景氣判斷整 section 抽 ui/tab1_macro_ai.py
            from ui.tab1_macro_ai import render_ai_summary_section  # noqa: PLC0415
            _ai_mac_pct, _ = _calc_data_health(ind)
            render_ai_summary_section(
                ind, phase, GEMINI_KEY,
                show_l3=_show_l3, mac_pct=_ai_mac_pct,
            )
    else:
        st.info("👆 點擊「載入總經資料」開始分析")
