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

from ui.helpers.ia import applied_form
from ui.helpers.render_state import business_alert, not_ready, system_error

from shared.converters import safe_num  # v19.399 §1:缺值保留 None,不 `or 0` 捏造
from shared.colors import (
    GH_BG_CARD,
    GH_BG_PRIMARY,
    GH_BORDER,
    GH_FG_MUTED,
    GH_FG_PRIMARY,
    GH_FG_SECONDARY,
    GRAY_55,
    GRAY_AA,
    MD_ORANGE_A200,
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
    calc_macro_phase,
    detect_systemic_risk,
    detect_turning_points,
    fetch_all_indicators,
)
from ui.helpers.session import (
    D5_KEYS as _TRUST_EXPECTED_KEYS,  # v19.195 SSOT:16 個關鍵指標(④ 可信度層對差集用)
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
    # ── 稽核 E11（2026-08-14）：門檻改 import services.risk_radar SSOT ──────────
    # 原本這裡手抄了一份門檻，註解還綁死他檔行號（`# services L103-L105`）。
    # 實測 5 組裡 3 組已漂移：VIX 黃 25(SSOT 22)、PCR 紅 1.5(SSOT 1.2)、
    # sector_rotation 更是連**量綱**都錯（畫成比值，實際是百分點差）。
    # service 端已於同批把門檻提升為 `RADAR_*` 模組常數，這裡直接吃它。
    from services.risk_radar import (
        RADAR_MOVE_RED, RADAR_MOVE_YELLOW,
        RADAR_PCR_RED, RADAR_PCR_YELLOW,
        RADAR_SECTOR_GAP_RED_PP, RADAR_SECTOR_GAP_YELLOW_PP,
        RADAR_VIX_RED, RADAR_VIX_TS_RED, RADAR_VIX_TS_YELLOW, RADAR_VIX_YELLOW,
    )

    if key == "vix_level":
        return [(RADAR_VIX_YELLOW, "dot", TRAFFIC_YELLOW,
                 f"警戒 {RADAR_VIX_YELLOW:.0f}"),
                (RADAR_VIX_RED, "dash", TRAFFIC_RED,
                 f"恐慌 {RADAR_VIX_RED:.0f}")]
    if key == "vix_term_struct":
        return [(RADAR_VIX_TS_YELLOW, "dot", TRAFFIC_YELLOW,
                 f"倒掛 {RADAR_VIX_TS_YELLOW:.2f}"),
                (RADAR_VIX_TS_RED, "dash", TRAFFIC_RED,
                 f"極端 {RADAR_VIX_TS_RED:.2f}")]
    if key == "hy_oas_delta":
        # trend 顯示 HY OAS level %;對齊拐點桶 6/8% threshold(SSOT MACRO_THRESHOLDS)
        return [(_HY_WARN_THRESHOLD, "dot", TRAFFIC_YELLOW, f"警戒 {_HY_WARN_THRESHOLD}%"),
                (_HY_CRISIS_THRESHOLD, "dash", TRAFFIC_RED, f"危機 {_HY_CRISIS_THRESHOLD}%")]
    if key == "move_level":
        return [(RADAR_MOVE_YELLOW, "dot", TRAFFIC_YELLOW,
                 f"警戒 {RADAR_MOVE_YELLOW:.0f}"),
                (RADAR_MOVE_RED, "dash", TRAFFIC_RED,
                 f"高 {RADAR_MOVE_RED:.0f}")]
    if key == "sector_rotation":
        # ⚠️ 量綱修正：本訊號的 value 是「防禦 30D 報酬 − 攻擊 30D 報酬」的
        #    **百分點差**（`risk_radar._signal_sector_rotation` 的 `gap`），
        #    不是 XLP/XLY 的比值。原本畫在 1.00 / 1.20 等於拿比值的刻度去標
        #    百分點的軸（實機觀測值 −0.84 就落在兩條線下方、看起來永遠安全）。
        return [(RADAR_SECTOR_GAP_YELLOW_PP, "dot", TRAFFIC_YELLOW,
                 f"防禦領先 +{RADAR_SECTOR_GAP_YELLOW_PP:.0f}pp"),
                (RADAR_SECTOR_GAP_RED_PP, "dash", TRAFFIC_RED,
                 f"資金撤離 +{RADAR_SECTOR_GAP_RED_PP:.0f}pp")]
    if key == "put_call_ratio":
        return [(RADAR_PCR_YELLOW, "dot", TRAFFIC_YELLOW,
                 f"看空 {RADAR_PCR_YELLOW:.2f}"),
                (RADAR_PCR_RED, "dash", TRAFFIC_RED,
                 f"恐慌 {RADAR_PCR_RED:.2f}")]
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
    #
    # ⚠️ `zs_*`(中期 Z-Score 矩陣卡)**不在本表**:它們的警戒線走
    #    `shared.macro_buckets` SSOT,由 `_zs_danger_spec_key` + `add_danger_hlines`
    #    在 `_make_radar_sparkline` 內接線。**請勿**在本函式另補一份 zs 門檻表
    #    (那會變成 registry 之外的第二份真相,§3.3)。
    return []


def _zs_danger_spec_key(spark_key: str):
    """中期 Z-Score 卡的 `spark_key`(`zs_<INDICATOR_KEY>`)→ DangerSpec key;對不上回 None。

    對應規則**只有一條**:去掉前綴後轉小寫,直接查 `shared.macro_buckets.SPECS_BY_KEY`。

    **刻意不寫別名對照表**:Z-Score 矩陣的 indicator key 與 registry 的 spec key
    大量不同名(registry 用 `cpi_yoy` / `m2_yoy` / `fed_bs_yoy` / `cfnai`,矩陣用
    `CPI` / `M2` / `FED_BS` / `LEI`),而 ADL / DXY / PPI / JOBLESS 等在 registry
    根本沒註冊。在 UI 層補一份別名表 = §3.3 禁止的第二份真相
    (同 `ui/tab1_macro_midcycle._card_label` 的既有裁決)。
    對不上 → 回 None → **誠實不畫線**(§1:寧可沒有警戒線,也不畫一條沒有 SSOT
    背書的線)。缺哪些 spec 屬 `shared/` 所有權,需 user 裁決後在 registry 補。
    """
    if not isinstance(spark_key, str) or not spark_key.startswith("zs_"):
        return None
    from shared.macro_buckets import SPECS_BY_KEY  # noqa: PLC0415
    _k = spark_key[3:].strip().lower()
    return _k if _k in SPECS_BY_KEY else None


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
        # 中期 Z-Score 卡:黃/紅警戒線走 `shared.macro_buckets` registry。
        # `add_danger_hlines` 自 v19.145 Phase B 寫好(含 10 條測試)卻 production
        # 0 caller —— SPEC §16.2 的「Phase B 把 SSOT 套到 chart」從未接線
        # (`PROCESS.md §4`:算對了但沒接出去)。本次接上。
        # 這裡刻意**呼叫** helper 而非在 UI 重算門檻:門檻值、線色、標註格式
        # (整數不補 .0 / decimals / 單位)全部只有 registry + helper 一份實作。
        # `trend` 是該指標的**原始值**近 8 期(midcycle `_zser.tail(8)`,非 Z 值),
        # 與 spec 同量綱,線畫在原始刻度上才成立。
        _zs_spec_key = _zs_danger_spec_key(key)
        if _zs_spec_key:
            from ui.helpers.chart.danger import add_danger_hlines  # noqa: PLC0415
            add_danger_hlines(_fig, _zs_spec_key)
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
    # v19.303: 趨勢箭頭 — 比較最新期 vs 3 期前（月資料≈一季趨勢）
    _arr_html = ''
    if trend and len(trend) >= 4:
        try:
            _cur, _prv = float(trend[-1]), float(trend[-4])
            if _prv != 0:
                _chg = (_cur - _prv) / abs(_prv)
                if _chg > 0.02:
                    _arr_html = f'<span style="font-size:11px;color:{TRAFFIC_GREEN};margin-left:5px;">↑</span>'
                elif _chg < -0.02:
                    _arr_html = f'<span style="font-size:11px;color:{TRAFFIC_RED};margin-left:5px;">↓</span>'
                else:
                    _arr_html = f'<span style="font-size:10px;color:{TRAFFIC_NEUTRAL};margin-left:5px;">→</span>'
        except Exception:
            pass
    _st_c.markdown(
        f"<div style='background:{GH_BG_PRIMARY};border:2px solid {color};"
        f"border-radius:10px;padding:10px 12px 6px;margin:4px 0;min-height:150px;"
        f"display:flex;flex-direction:column;justify-content:space-between'>"
        f"<div>"
        f"<div style='color:{TRAFFIC_NEUTRAL};font-size:10px;letter-spacing:1px'>{title}</div>"
        f"<div style='color:{color};font-size:15px;font-weight:800;margin:4px 0 6px'>{signal}</div>"
        f"<div style='color:{WHITE};font-weight:700;font-size:14px'>值 {value_str}{_arr_html}</div>"
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


# ════════════════════════════════════════════════════════════════
# 總表 Section 02 — 5 卡快覽網格(2026-09-03 客戶拍板線框批次二)
#
# 客戶核准的線框把它插在「①結論」持久條與「②依據」之間:①結論維持不摺疊、
# ④可信度維持持久條,本網格夾在中間。**本區塊不新增任何計算** —— 5 張卡
# 全部複用既有、已在跑的判讀函式,只是換一種能一眼掃過的呈現方式(§1)。
# 另有 3 張卡(資產水位建議 / 新聞情緒 / 總經燈號全表)本輪**明確不做**,
# 客戶原線框已標「待審查」,見 `_render_top_card_grid` 結尾的 caption 與
# `BACKLOG.md`「⏸ 待審查 — 總表 Section 02 三張快覽卡」。
# ════════════════════════════════════════════════════════════════
def _render_top_card_grid(ind: dict, phase: dict) -> None:
    """渲染 Section 02 的快覽卡網格(固定 3 欄,複用 `_render_macro_indicator_card`)。

    每張卡各自 try/except 隔離(§1 區塊隔離,同本檔①~④既有寫法):一張卡的
    資料算不出來,不擋掉其餘卡片,也不擋掉下方 ② 依據表。**沒有算出來的卡
    直接跳過,不補假資料**——凡是本函式沒有 append 進 `_cards` 的位置,
    第二排就會少一格,不會有佔位假卡。

    5 張卡的資料來源(全部是既有函式的既有輸出,零新運算):
        景氣位階     — `phase`(呼叫端已算好的 `calc_macro_phase(ind)`,不重算)
        波動與信用   — `st.session_state["_radar_v1921_top"]`
                       (呼叫端「頂部雙速合議」已抓好的 `detect_risk_radar()`
                       結果,同 `ui/tab1_macro_radar.py:81` 既有讀法,不重抓)
        通膨與利率   — `phase["growth_inflation"]`(呼叫端 `calc_macro_phase(ind)` 內部
                       已算好 `calc_growth_inflation_axis(indicators)` 並原樣掛進 return,
                       本卡直接讀那一份,**不重算**;同卡 1 的處理)
                       ⚠️ 2026-09-04 稽核 P5 更正:本行原寫
                       ~~`calc_growth_inflation_axis(ind)`(純函式,零 I/O)~~ ——
                       與同段開頭「零新運算」自相矛盾,也與卡 1 既有的重算守衛
                       (`test_phase_card_reuses_the_caller_supplied_phase_not_recomputed`)
                       同類。**有意識的更正,不是漏刪。**
        熱錢動向     — `services.hot_money_service.fetch_hot_money_frames()`
                       (L2 facade,`@st.cache_data` 走與下方 ARCHIVED expander
                       同一顆 L1 fetcher + 同一組 default 參數,同一把 cache key,
                       不重抓;見 `ui/hot_money.py::refresh_hot_money_data`
                       的既有 default 180d/5窗/50億/0.5%)
        極端風險警語 — `macro_action_light(ind, phase.get("score"))`(純函式,
                       與①結論同一顆,零額外 I/O)
    """
    _cards: list[dict] = []

    # 卡 1 ── 📊 景氣位階
    try:
        _score = phase.get("score")
        _score_str = f"{_score:.1f}/10" if isinstance(_score, (int, float)) else "—"
        _trend_txt = f"{phase.get('trend_arrow', '')} {phase.get('trend_label', '')}".strip()
        _cards.append(dict(
            title="📊 景氣位階",
            signal=f"{phase.get('phase', '—')}（{_score_str}）",
            color=phase.get("phase_color") or _MACRO_CARD_LIGHT_COLOR["gray"],
            value_str=_score_str,
            note=phase.get("advice") or "尚未算出景氣位階",
            label=_trend_txt or "—",
            trend=None,
            spark_key="top_phase",
        ))
    except Exception as _c1e:  # noqa: BLE001 — 一張卡失敗不得擋掉其餘卡片
        system_error("快覽卡「景氣位階」渲染失敗", _c1e)

    # 卡 2 ── 🌊 波動與信用(VIX + HY OAS,worse-of 兩燈)
    try:
        _radar_cache = st.session_state.get("_radar_v1921_top")
        _radar_dict = _radar_cache[0] if (_radar_cache and _radar_cache[0]) else None
        if _radar_dict:
            _vix = _radar_dict.get("vix_level") or {}
            _hy = _radar_dict.get("hy_oas_delta") or {}
            _rank = {"🔴": 3, "🟡": 2, "🟢": 1}
            _vix_rank = _rank.get(str(_vix.get("signal", ""))[:2], 0)
            _hy_rank = _rank.get(str(_hy.get("signal", ""))[:2], 0)
            _worse = _vix if _vix_rank >= _hy_rank else _hy
            _vix_v, _hy_v = _vix.get("value"), _hy.get("value")
            _vix_str = f"VIX {_vix_v:.1f}" if isinstance(_vix_v, (int, float)) else "VIX —"
            _hy_str = f"HY {_hy_v:.2f}%" if isinstance(_hy_v, (int, float)) else "HY —"
            _cards.append(dict(
                title="🌊 波動與信用",
                signal=_worse.get("signal") or "⬜ 無資料",
                color=_worse.get("color") or _MACRO_CARD_LIGHT_COLOR["gray"],
                value_str=f"{_vix_str} ｜ {_hy_str}",
                note=_worse.get("note") or "—",
                label="Yahoo ^VIX ＋ FRED HY OAS（風險雷達 10 燈之 2）",
                trend=_vix.get("trend"),
                spark_key="top_vix_hy",
            ))
        else:
            _cards.append(dict(
                title="🌊 波動與信用",
                signal="⬜ 待取得",
                color=_MACRO_CARD_LIGHT_COLOR["gray"],
                value_str="—",
                note="風險雷達本次未載入（未勾選或逾時）",
                label="到「📡 載入總經資料」勾選「風險雷達」後重試",
                trend=None,
                spark_key="top_vix_hy",
            ))
    except Exception as _c2e:  # noqa: BLE001
        system_error("快覽卡「波動與信用」渲染失敗", _c2e)

    # 卡 3 ── 🌡️ 通膨與利率(成長 × 通膨四象限)
    #
    # 2026-09-04 稽核 P1 修正(§1 Fail Loud, Never Fake)——**兩個獨立的缺陷**:
    #
    # (a) **零觀測捏造彩色定論**。`calc_growth_inflation_axis` 的
    #     `inflation_score = sum(signals) / max(len(signals), 1)`:通膨三個來源
    #     (CPI / PPI / FED_RATE)**全部缺**時分母被墊成 1、分子是 0 → 分數 0.0,
    #     `inflation_up = 0 > 0 = False` 被當成「通膨受控」。FRED 掛掉、Yahoo 還活著
    #     的偏斷情境實測輸出:`🌱 復甦/擴張` **綠燈**、`成長 +1.00 ｜ 通膨 +0.00`、
    #     `0 個通膨訊號` —— 一個「零筆通膨觀測」被畫成「通膨受控」的全綠放行。
    #     全部指標皆缺時退成 `🌧️ 衰退` 橘燈,一樣是憑空定論。
    #     這是五張卡裡**唯一**沒有資料充足性閘門的一張(①`isinstance`、
    #     ②`if _radar_dict else ⬜`、④`if empty → ⬜`、⑤`score is None → ⬜`)。
    #
    #     **判定:任一軸零觀測 → 整張卡走灰態。** 理由是這張卡的頭條(象限名)、
    #     顏色、與 note 三者**都是兩軸的聯合函數** —— 只有一軸有資料時,象限
    #     根本命名不出來,硬給一個名字就是編。**有資料的那半不丟掉**:改以文字
    #     寫進 note / label(不是頭條數字、不帶顏色定論),既不浪費已測到的東西,
    #     也不暗示一個不存在的量測。灰態沿用①②④⑤既有的同一組
    #     (`⬜ 待取得` / `—` / `_MACRO_CARD_LIGHT_COLOR["gray"]`),不另發明第六種。
    #     對照標準:`services/macro/action_light.py` docstring
    #     「位階缺 → 🟡 資料不足,不下假綠燈(§1 Fail-Loud)」。
    #
    # (b) **重算**。`phase["growth_inflation"]` 就是 `calc_growth_inflation_axis(ind)`
    #     的同一份輸出(`services/macro/us_indicators.py::calc_macro_phase` 內算好後
    #     原樣掛進 return dict),本函式 docstring 自稱「零新運算」,卡 1 也已有
    #     `test_phase_card_reuses_the_caller_supplied_phase_not_recomputed` 明文
    #     禁止這個 pattern。改為直接讀呼叫端傳進來的那一份。
    #     **刻意不留「讀不到就自己算一次」的 fallback**:那條路會讓重算守衛失效,
    #     而讀不到本來就該走灰態(沒有已算好的軸 = 沒有這個量測)。
    try:
        _gi_raw = phase.get("growth_inflation")
        _gi = _gi_raw if isinstance(_gi_raw, dict) else {}
        _n_growth = int(_gi.get("n_growth") or 0)
        _n_infl = int(_gi.get("n_inflation") or 0)
        if not _gi or _n_growth == 0 or _n_infl == 0:
            # 缺哪一半就說哪一半;有的那半用文字誠實交代,不當頭條數字。
            if not _gi:
                _gi_note = "成長／通膨雙軸尚未算出（呼叫端未提供 phase.growth_inflation）"
            elif _n_growth == 0 and _n_infl == 0:
                _gi_note = "成長與通膨兩軸都沒有任何可用觀測，無法定象限"
            elif _n_infl == 0:
                _gi_note = (f"通膨軸 0 筆觀測（CPI／PPI／Fed Rate 全缺），"
                            f"無法定象限；成長軸現有 {_n_growth} 個訊號")
            else:
                _gi_note = (f"成長軸 0 筆觀測，無法定象限；"
                            f"通膨軸現有 {_n_infl} 個訊號")
            _cards.append(dict(
                title="🌡️ 通膨與利率",
                signal="⬜ 待取得",
                color=_MACRO_CARD_LIGHT_COLOR["gray"],
                value_str="—",
                note=_gi_note,
                label="象限要兩軸都有觀測才成立；缺一軸不下燈號（§1 不捏造）",
                trend=None,
                spark_key="top_growth_inflation",
            ))
        else:
            _cards.append(dict(
                title="🌡️ 通膨與利率",
                signal=f"{_gi.get('quad_icon', '')} {_gi.get('quadrant', '—')}".strip(),
                color=_gi.get("quad_color") or _MACRO_CARD_LIGHT_COLOR["gray"],
                value_str=(f"成長 {_gi['growth_score']:+.2f} ｜ "
                          f"通膨 {_gi['inflation_score']:+.2f}"),
                note=_gi.get("quad_desc") or "—",
                label=f"{_n_growth} 個成長訊號、{_n_infl} 個通膨訊號",
                trend=None,
                spark_key="top_growth_inflation",
            ))
    except Exception as _c3e:  # noqa: BLE001
        system_error("快覽卡「通膨與利率」渲染失敗", _c3e)

    # 卡 4 ── 💰 熱錢動向(客戶核准由 ARCHIVED 摺疊區升格為常駐卡)
    # SSOT:走與下方「📦 ARCHIVED — 台股熱錢監測」expander 同一顆 L2 facade
    # (`services.hot_money_service.fetch_hot_money_frames`)+ 同一組 default
    # 參數(180d/5窗/50億/0.5%,對齊 `refresh_hot_money_data` 既有 default)。
    # `fetch_foreign_flow_series` / `fetch_usdtwd_series` 皆 `@st.cache_data`,
    # 同一組參數 = 同一把 cache key,本卡與 expander 不會各打一次網路。
    try:
        from services.hot_money_service import fetch_hot_money_frames  # noqa: PLC0415
        from ui.hot_money import build_signals as _hm_build_signals  # noqa: PLC0415
        # 2026-09-03:token 讀取改走 `infra.config.get_secret`(§2.1 SSOT)而非裸
        # `st.secrets.get(...)`——後者在**完全沒有 secrets 檔**時,`hasattr(st,
        # "secrets")` 仍為 True,但 `.get()` 內部會 `_parse()` 直接
        # `raise StreamlitSecretNotFoundError`(同 `app.py` 2026-08-15 那段已修
        # 過的坑)。既有 `ui/hot_money.py` expander 沿用的是舊寫法,但那裡是
        # 摺疊區、user 沒點開就不會跑到;本卡是**常駐**渲染,每次 rerun 都會
        # 打到這一行,風險遠高於摺疊區,故本卡改用已修好的 SSOT helper。
        from infra.config import get_secret as _hm_get_secret  # noqa: PLC0415
        _hm_token = str(_hm_get_secret("FINMIND_TOKEN", "") or "")
        _hm_flow, _hm_fx, _hm_ferr, _hm_xerr = fetch_hot_money_frames(180, _hm_token)
        if _hm_flow.empty or _hm_fx.empty:
            _cards.append(dict(
                title="💰 熱錢動向",
                signal="⬜ 待取得",
                color=_MACRO_CARD_LIGHT_COLOR["gray"],
                value_str="—",
                note=(_hm_ferr or _hm_xerr or "外資買賣超／USDTWD 資料不足"),
                label="展開下方「📦 台股熱錢監測」查看完整判讀",
                trend=None,
                spark_key="top_hot_money",
            ))
        else:
            _hm_sig = _hm_build_signals(_hm_flow, _hm_fx, window=5,
                                        flow_thr=50.0, fx_thr=0.5)
            if _hm_sig.empty:
                _cards.append(dict(
                    title="💰 熱錢動向",
                    signal="⬜ 待取得",
                    color=_MACRO_CARD_LIGHT_COLOR["gray"],
                    value_str="—",
                    note="外資與匯率資料沒有重疊的交易日",
                    label="展開下方「📦 台股熱錢監測」查看完整判讀",
                    trend=None,
                    spark_key="top_hot_money",
                ))
            else:
                _hm_latest = _hm_sig.iloc[-1]
                _hm_state = str(_hm_latest.get("state", "") or "")
                _hm_div = bool(_hm_latest.get("is_divergence", False))
                if _hm_div:
                    _hm_color = _MACRO_CARD_LIGHT_COLOR["yellow"]
                elif "流入" in _hm_state:
                    _hm_color = _MACRO_CARD_LIGHT_COLOR["green"]
                elif "流出" in _hm_state:
                    _hm_color = _MACRO_CARD_LIGHT_COLOR["red"]
                else:
                    _hm_color = _MACRO_CARD_LIGHT_COLOR["gray"]
                _hm_net = _hm_latest.get("foreign_net_yi")
                _hm_net_str = f"外資 {_hm_net:+.0f}億" if isinstance(_hm_net, (int, float)) else "—"
                _hm_trend = (_hm_flow["foreign_net_yi"].tail(8).tolist()
                            if "foreign_net_yi" in _hm_flow.columns else None)
                try:
                    _hm_date_str = str(pd.Timestamp(_hm_latest["date"]).date())
                except Exception:  # noqa: BLE001 — 日期格式異常不擋卡片
                    _hm_date_str = "—"
                _cards.append(dict(
                    title="💰 熱錢動向",
                    signal=_hm_state or "—",
                    color=_hm_color,
                    value_str=_hm_net_str,
                    note=str(_hm_latest.get("interpretation", "") or "")[:70] or "—",
                    label=f"{_hm_date_str}｜展開下方「📦 台股熱錢監測」看完整三角交叉圖",
                    trend=_hm_trend,
                    spark_key="top_hot_money",
                ))
    except Exception as _c4e:  # noqa: BLE001
        system_error("快覽卡「熱錢動向」渲染失敗", _c4e)

    # 卡 5 ── ⚠️ 極端風險警語(macro_action_light 的 override 觸發燈)
    try:
        from services.macro import macro_action_light as _mal_c5  # noqa: PLC0415
        _al5 = _mal_c5(ind, phase.get("score"))
        _reasons5 = _al5.get("reasons") or []
        # 2026-09-04 稽核 P3 修正:`reasons` 只有在 `override=True` 時才是**觸發**
        # 清單;非 override 分支它是一組**固定 2 則的說明文字**
        # (「景氣位階 X/10」+「無硬衰退/恐慌訊號(…均未觸發)」),`score is None`
        # 分支則是 1 則(「景氣位階未取得」)。舊寫法一律 `len(reasons) 項訊號`,
        # 於是**平靜與恐慌印出一模一樣的頭條數字**(實測皆為「2 項訊號」),
        # 而資料不足態印「⬜ 資料不足 / 1 項訊號」—— 一邊說沒資料、一邊報一項訊號。
        # 修法:數字只數**真的觸發**的訊號,標籤與數字語意對齊。
        _n_trig5 = len(_reasons5) if _al5.get("override") else 0
        if _al5.get("override"):
            _sig5, _col5 = "🔴 已觸發", _MACRO_CARD_LIGHT_COLOR["red"]
            _val5 = f"{_n_trig5} 項觸發"
        elif phase.get("score") is None:
            _sig5, _col5 = "⬜ 資料不足", _MACRO_CARD_LIGHT_COLOR["gray"]
            # 灰態沿用①②③④同一組表現(`—`),不報一個不存在的訊號數。
            _val5 = "—"
        else:
            _sig5, _col5 = "🟢 未觸發", _MACRO_CARD_LIGHT_COLOR["green"]
            _val5 = "0 項觸發"
        _cards.append(dict(
            title="⚠️ 極端風險警語",
            signal=_sig5,
            color=_col5,
            value_str=_val5,
            note="；".join(_reasons5) or "—",
            label="殖利率倒掛／Sahm≥0.5／VIX≥30 三者任一觸發即轉紅",
            trend=None,
            spark_key="top_extreme_risk",
        ))
    except Exception as _c5e:  # noqa: BLE001
        system_error("快覽卡「極端風險警語」渲染失敗", _c5e)

    if not _cards:
        st.caption("⬜ 五張快覽卡本次都沒有算出來，請看上方各區塊的錯誤訊息。")
    else:
        # 固定 3 欄自適應網格：5 張卡分兩排，第二排只有 2 張（或更少，視
        # 上面哪幾張失敗而定）—— `st.columns(3)` 字面用滿，不用變數湊欄數
        # （§8.2.A0 判定 1：3 欄是分層概念不是字面路徑要求，但**這裡**確實
        # 就是要 3 欄字面網格，不必迂迴；`tests/test_ui_grid_contract.py`
        # 的 fail-closed 規則只認整數字面 3）。
        for _row_start in range(0, len(_cards), 3):
            _row_cards = _cards[_row_start:_row_start + 3]
            _cols = st.columns(3)
            for _ci, _card in enumerate(_row_cards):
                with _cols[_ci]:
                    # 2026-09-04 稽核 P4:**渲染**這一步先前是裸呼叫 —— 上面每張卡
                    # 各自的 try/except 只保護「算資料」,一張卡的 HTML/sparkline
                    # 渲染炸掉會連坐**整個網格**(其餘 4 張一起消失)。逐張隔離。
                    try:
                        _render_macro_indicator_card(**_card)
                    except Exception as _cre:  # noqa: BLE001 — 一張卡渲染失敗不連坐其餘
                        system_error(
                            f"快覽卡「{_card.get('title', '?')}」渲染失敗", _cre)

    # 3 張本輪明確不做的卡：客戶線框已標「待審查」，不能放假資料佔位（§1），
    # 也不能悄悄消失（§-2 揭露義務）——只留一句待審查說明 + BACKLOG 追蹤。
    st.caption(
        "📌 待審查（線框草稿已提交客戶，暫緩至核准後施作）：資產水位建議、"
        "新聞情緒、總經燈號全表 — 追蹤見 `BACKLOG.md`「⏸ 待審查 — 總表 "
        "Section 02 三張快覽卡」。"
    )


def _now_tw():
    return datetime.datetime.now(_TW_TZ)


def _calc_data_health(indicators=None):
    """同 app.py wrapper。"""
    ind = indicators if indicators is not None else st.session_state.get("indicators", {})
    return _calc_data_health_pure(ind)


def _business_alert_action_light(msg: str) -> None:
    """`business_alert()` 版的 🔴 結論燈,呼叫介面與 `st.error(msg: str)` 相容。

    2026-08-28 客戶拍板(線框 §03「顏色:三態統一規則」)+ 2026-09-03 客戶批次二
    再次點名:**①結論的 🔴 是「這幾個訊號亮了,建議轉保守」—— 分析算完了、
    答案就是這個,不是系統壞掉**。它與「系統真出錯」(抓取/渲染失敗)用同一個
    `st.error` 紅框,會把「不要相信這個畫面」與「相信這個畫面並據以行動」
    畫成同一件事(`ui/helpers/render_state.py` 檔頭原文)。

    呼叫端(`render_macro_tab`)組出的是**單一字串**(第一行粗體結論 + 換行 +
    `- ` 條列理由),對齊 `st.success` / `st.warning` / `st.error` 的呼叫介面
    (皆吃單一 `msg: str`)。`business_alert(title, lines, *, footer="")` 要的是
    拆開的 title + lines list,故這裡依既有慣例(呼叫端組字串時使用的分隔規則)
    把它拆回去 —— 不改變呼叫端半個字,只在 renderer 這一層轉接。
    """
    _parts = msg.split("\n")
    _title = _parts[0].strip("*") if _parts else "結論"
    _lines = [p for p in _parts[1:] if p]
    business_alert(_title, _lines)


def _action_light_renderer(light: str):
    """`macro_action_light()` 的燈色 → streamlit 原生告示元件 / 業務警訊卡。

    🟢 → `st.success` / 🔴 → `_business_alert_action_light`(業務警訊卡,**不是**
    `st.error`)/ 其餘(含 🟡 與服務層日後新增的燈)→ `st.warning`。

    ⚠️ **2026-09-03 就地更正(有意識的更正,不是漏刪 · 決策者:客戶批次二拍板)**:
    🔴 原本走 `st.error`(系統錯誤框)。全 repo 唯一 production 呼叫點是
    `render_macro_tab()` 的①結論,餵給它的**只有** `macro_action_light()` 的輸出
    ——那是**業務判斷**(硬衰退/恐慌 override、景氣位階三級),從頭到尾沒有一條
    分支代表「抓取/渲染出錯」(系統真出錯已由外層 `except ... system_error(...)`
    接手,不會流進本函式)。**手上沒有 exception、印的是業務結論** → 依
    `ui/helpers/render_state.py` 的三態分離規則,不得走系統紅框。
    （查證:`git grep -n "_action_light_renderer" -- '*.py'` —— 除本檔定義與
    測試檔外,唯一呼叫點是 `render_macro_tab()` 內那一行，見同檔行內註解。）

    🟢/🟡 兩支維持原生元件不動:**用原生元件不手刻 HTML** 的理由對它們仍然成立
    (告示框底色/邊框由 theme 提供,不必新造色票,§3.3);只有 🔴 這一支需要
    脫離「錯誤框」語彙,故單獨換掉。

    未知燈色一律落到 warning(偏保守),不當成綠燈 —— §1 不下假綠燈。
    """
    if light == "🟢":
        return st.success
    if light == "🔴":
        return _business_alert_action_light
    return st.warning


# ════════════════════════════════════════════════════════════════
# 總表 ③ 例外層 / ④ 可信度層的判斷 —— 抽成模組層純函式
#
# 兩層原本整段寫在 `render_macro_tab` 內部,唯一能「驗證」的方式是掃原始碼
# 有沒有出現某個片語 —— 而字串比對對「條件恆真」「計數恆 0」這兩類缺陷
# **完全免疫**(`PROCESS.md §4`:拿掉呼叫端那一行仍綠 → 測試無效)。
# 抽出後可直接餵資料斷言行為;呼叫端由 AST 呼叫檢查守著。
# ════════════════════════════════════════════════════════════════

# `detect_systemic_risk()` 契約(見該函式 docstring)把新聞風險分成三級,
# 其中只有前兩級屬於「該警覺」。最低級是常態值 —— 把常態列進例外層,
# 例外層就永遠有內容,使用者會學會整層忽略(§1:沒有例外時誠實說沒有)。
# 等級字串由 `services/macro/us_indicators.py` 產生(不在本次所有權內,
# 無法就地建常數),故本 tuple 是**鏡像**;漂移鎖以「實際呼叫服務層產生
# 各級再比對」的方式寫在 tests/test_audit_20260805_tab1_exceptions.py。
_NEWS_RISK_ALERT_LEVELS: tuple[str, ...] = ("HIGH", "MEDIUM")

# 桶 summary 的燈號中屬於「該警覺」的兩級(green 以外)。
_BUCKET_ALERT_LEVELS: tuple[str, ...] = ("yellow", "red")


def _systemic_risk_is_alerting(systemic_risk) -> bool:
    """新聞系統性風險是否達到該警覺的等級。

    2026-08-05 稽核 🔴 必修 1:原本的條件是「`systemic_risk_data` 有沒有東西」。
    但載入成功時它**一定**被寫進 session,而服務層恆回非空 dict —— 條件恆真,
    於是平靜的日子「③ 例外」底下永遠掛著一條「✅ …最低級(評分 0)」,
    而「沒有例外」那條敘述只有在新聞掃描整個炸掉時才跑得到(死分支)。
    """
    if not isinstance(systemic_risk, dict) or not systemic_risk:
        return False
    _lvl = str(systemic_risk.get("risk_level", "") or "").strip().upper()
    return _lvl in _NEWS_RISK_ALERT_LEVELS


# ② 依據表這次沒成功產出時,③ 要說的話。桶級警戒**無法判定** —— 不可沿用
# 「都不在警戒狀態」那句(那是把「沒算出來」講成「算過了沒事」,§1)。
_BUCKET_STATUS_UNKNOWN_LINE = (
    "- ⬜ **桶級警戒這次無法判定**：上方 ② 依據表未成功產出（見它自己的紅字），"
    "拐點桶／新聞桶有沒有亮燈本次沒有結果 — 請先排除 ② 的錯誤再讀本層。")

# ③ 只講 ② **沒有**的東西。桶級警戒 ② 每一列都已完整寫出(燈號 / 判讀 / 讀數 /
# 門檻 / 指路),③ 再抄一次就是同一件事說兩次(user 原則 2)——改成指出「是哪幾列」。
_BUCKET_ALERT_POINTER_HEAD = "- 🔺 **今日例外落在上表這幾列**："
_BUCKET_ALERT_POINTER_TAIL = (
    " — 讀數、判讀與門檻已完整列在上方 ② 依據表的同名列，此處不重印。")


def _exception_lines(systemic_risk, bucket_summary) -> list[str]:
    """③ 例外層要條列的項目(純函式、零 streamlit、零 I/O)。

    回傳**空 list = 真的沒有例外**,caller 據此顯示「沒有例外」那條敘述。
    指路文字走 `beginner_view.section_hint`(§3.3 不在本層重打區段名);
    未知桶 key 會由它當場 KeyError,不靜默指向空氣。

    2026-08-05 稽核 🔴 必修 5:桶警戒原本把 ② 的 `label` + `headline` **原字串**
    再印一次,而 ③ 就緊貼在 ② 表下方兩行 —— 同一句話上下相鄰出現兩次。
    ③ 現在只保留 ② 沒有的東西(新聞系統性風險的**等級與評分**,那兩個數字
    ② 的新聞列沒有),桶警戒改成一句「是哪幾列」的指路。
    """
    from ui.helpers.macro.beginner_view import (  # noqa: PLC0415
        _bucket_bar_cells as _cells_ssot,
        section_hint as _sec_hint,
    )
    _lines: list[str] = []
    _srd = systemic_risk if isinstance(systemic_risk, dict) else {}
    if _systemic_risk_is_alerting(_srd):
        _lines.append(
            f"- {_srd.get('risk_icon', '⬜')} **新聞系統性風險**："
            f"{_srd.get('risk_level', '—')}"
            f"（評分 {_srd.get('risk_score', '—')}）— {_sec_hint('news')}"
            "的 📰 市場新聞")
    _sum = bucket_summary if isinstance(bucket_summary, dict) else {}
    _alert_keys = [_bk for _bk in ("inflection", "news")
                   if (_sum.get(_bk) or {}).get("level") in _BUCKET_ALERT_LEVELS]
    if _alert_keys:
        # 桶名走 `BUCKET_META` SSOT(`_bucket_bar_cells`),③ 不重打一份桶名。
        _faces = [_t for _k, _t, _s in _cells_ssot(_alert_keys)]
        _lines.append(_BUCKET_ALERT_POINTER_HEAD + "、".join(_faces)
                      + _BUCKET_ALERT_POINTER_TAIL)
    return _lines


def _bucket_status_unavailable_line(bucket_summary) -> list[str]:
    """② 降級(哨兵 `None`)時要補的誠實條;② 正常(dict,含空 dict)時回 []。

    2026-08-05 稽核 🔴 必修 2:`_5b_summary` 原本初值是 `{}`,② 渲染整段失敗時
    它**維持 `{}`**,`_exception_lines` 對空 dict 回 `[]`,③ 於是印出
    「…都不在警戒狀態；各桶讀數完整列在上方 ② 依據表」—— ② 剛用紅字說自己壞了,
    ③ 緊接著說「完整列在上方」。改用 `None` 當「② 未成功」的哨兵,兩種狀態才分得開。
    """
    return [] if bucket_summary is not None else [_BUCKET_STATUS_UNKNOWN_LINE]


def _proxy_indicator_labels(indicators) -> list[str]:
    """帶 `is_proxy` 旗標的指標顯示名(服務層 `name`,缺則退 key)。

    2026-08-05 稽核 🟡 建議 5:④ 可信度層原本只報「代理值 N 筆」,使用者得
    捲到下方 Z-Score 矩陣找 ⚠️ 前綴才知道是哪一筆。名字服務層已經給了,
    本層不另造(§3.3)。
    """
    _ind = indicators if isinstance(indicators, dict) else {}
    _out: list[str] = []
    for _k, _v in _ind.items():
        if str(_k).startswith("_") or not isinstance(_v, dict):
            continue
        if _v.get("is_proxy"):
            _out.append(str(_v.get("name") or _k))
    return _out


def _missing_indicator_keys(indicators) -> list[str]:
    """預期清單裡**沒抓到**的指標 key。

    2026-08-05 稽核 🔴 必修 2:原寫法數的是「value 為 None 的筆數」,但
    `fetch_all_indicators` 的每一個寫入點都在「值存在」的守衛裡 —— 抓失敗的
    指標是**整個 key 不存在**,不是 value 被寫成空。於是 FRED 掛掉 5 條時,
    ④ 可信度層依然報 0,而那一層的職責正是回答「這些數字能信嗎」(§1:
    為了看起來完整而顯示沒有依據的數字)。

    改成與**預期清單對差集**。清單走 `ui/helpers/session.D5_KEYS`
    (v19.195 既有 SSOT,`calc_data_health` 用的同一份),UI 層不新寫第二份
    (§3.3)。`_fred_sources` 那條候選只涵蓋 5 條 FRED 原始序列、且是
    series id 不是指標 key,無法回答「哪幾個指標沒了」,故不採。

    值仍一併檢查:key 在但值為空(理論上不會發生,服務層有守衛)也算缺,
    寧可多報不可少報。
    """
    _ind = indicators if isinstance(indicators, dict) else {}
    _out: list[str] = []
    for _k in _TRUST_EXPECTED_KEYS:
        _v = _ind.get(_k)
        if not isinstance(_v, dict) or _v.get("value") is None:
            _out.append(str(_k))
    return _out


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
    # v19.395 V3:補暗底 + 字色 —— 原 update_layout 無 paper_bgcolor / font color,
    # Sankey 節點標籤走 Plotly 預設深色字,在深色 UI 幾乎黑字黑底不可讀
    # (audit DEFECT-DARKMODE)。node_colors 升息劇本升級漸層為刻意語意色,保留。
    fig.update_layout(
        height=220, margin=dict(l=0, r=0, t=8, b=4),
        font=dict(size=10, color=GH_FG_PRIMARY),
        paper_bgcolor=STREAMLIT_BG, plot_bgcolor=STREAMLIT_BG,
    )
    st.plotly_chart(fig, use_container_width=True)


# ════════════════════════════════════════════════
# v19.15：即時訊號燈 + 決策矩陣
# ════════════════════════════════════════════════
# 2026-08-05 稽核 🟢 選作 7 裁決:**保留 inline,不收 shared/colors.py**。
# 本組是 Tailwind 800/900 級「深底 + 淺字」成對 badge 色(對比比由 pair 決定),
# shared/colors.py 現有 40 個常數裡沒有語意對得上的 —— dark red 只有
# BG_DARK_RED_1/2/3(#2a0a0a/#1a0606/#3a0a0a,比 #7f1d1d 暗一個量級),
# 前景 MD_RED_A100(#ff8a80)/MD_ORANGE_300(#ffb74d)則是不同色相的 Material 調。
# 硬換 = 改動畫面顏色且拆散成對關係;`shared/colors.py` 又不在本次所有權內不得新增常數。
# 依 `CLAUDE.md §8.3` 對 `macro_card_edu.py` 的裁決精神(對不上就別硬收)登記保留。
# **升級條件**:user 要求擴充 shared/colors.py 的 Tailwind badge pair 色階時再收。
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

    # 核心 / 衛星判定走全站唯一那支（Sheet `policy_tier` 優先，缺則退基金名啟發）。
    # 2026-08-07：本處原本 inline 了一份同語意的 if/elif —— 那是「全站一把尺」
    # 收斂時的第 4 個漏網點（前三處在 tab3 已收）。決策矩陣的逐檔行動建議吃的就是
    # 這個 is_core，兩份實作只要有一份沒跟上 Sheet 的改動，同一檔基金在保單卡片與
    # 決策矩陣就會一個標核心、一個標衛星。
    from ui.helpers.portfolio.allocation import resolve_core_flag  # noqa: PLC0415
    is_core = resolve_core_flag(_f)

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
        # v19.399 §1:缺 1Y 含息報酬保留 None(不 `or 0` 捏造 0% → dividend_safety 假吃本金);
        # dividend_safety 對 None 有「無報酬資料」grey 誠實分支(portfolio_service.py:341)。
        _tret = safe_num(_mj.get("perf", {}).get("1Y"))
        if _tret is None:
            _tret = safe_num(_metrics.get("ret_1y"))
        _dyld = float(_mj.get("moneydj_div_yield") or _metrics.get("annual_div_rate") or 0)
        if _dyld > 0:
            # v19.400 §1/§8:原 `from fund_fetcher import div_safety_check` 為 broken import
            # (fund_fetcher 未 export 該名 → ImportError 被下方 except 吞 → tab1 逐檔決策矩陣
            # 「吃本金」訊號長期 dead,div_info 恆 None)。改指 SSOT services.portfolio_service
            # (對齊 tab3:67),啟用 tab1 誠實訊號:缺 ret_1y(_tret=None)→ grey「無報酬資料」,
            # 真吃本金 → red;decision_matrix 僅對 alert=="red" bump 動作,grey/None 不觸發(§1)。
            from services.portfolio_service import dividend_safety as div_safety_check
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

    # 稽核 🟡 建議 10:標題原本帶內部版號「（v19.15）」—— 版號對使用者零意義,
    # 且它是**當年新增這區塊的版本**,不是資料版本,留著只會被誤讀成資料日期。
    # 2026-08-10:這一層 `###` 標題整個拿掉。呼叫端本來就有一個同名的 `##` 區塊標題,
    # 中間隔著的 expander 外框(它自己也印一次同名標題)這次一併拆掉之後,同一句話
    # 會連印三次、彼此只差一個 emoji。留下的 caption 講的是**推導鏈**
    # (呼叫端那句講的是「所以我該怎麼做」),兩者不同義,不算重複故保留。
    st.caption("總經 verdict 套用 active 權重後 → 5 級分檔 × 個股 σ/配息訊號 → 逐檔持有/加碼/減倉/全撤")

    # ── 區塊 1：頂部 verdict 大卡 ─────────────────────────────
    icon = dash["verdict_icon"]
    level = dash["verdict_level"]
    color = dash["verdict_color"]
    score = dash["score"]
    action_text = dash["verdict_action_text"]

    # 2026-08-05 稽核 🟡 建議 4:本大卡與總表 ② 依據表那一列是**同一個數字**
    # (兩邊都是 `calculate_composite_score`;`compute_realtime_dashboard` 多套的
    # 那層權重覆寫,`calculate_composite_score` 自己一進門就會先做一次)。
    # 但兩邊名字不同、小數位還不同(2 位 vs 1 位)—— 看起來像兩個獨立判斷,
    # 正是本輪要消滅的重複。
    # **不刪大卡**:逐檔決策矩陣的「原因」欄與其下的動作對照表整套以 verdict
    # 分級為前提(「衛星在極度樂觀區 → 加碼」),刪掉大卡後這張表就沒有錨點,
    # 讀者無從得知自己在哪一級。改為**標明同源 + 統一小數位**(選項 b)。
    # 小數位對齊 `build_evidence_rows` 那一列的一位小數。
    try:
        from ui.helpers.macro.beginner_view import _STRENGTH_FACE  # noqa: PLC0415
        _same_src = f"＝ 上方總表 ② 依據表的「{_STRENGTH_FACE}」那一列"
    except ImportError:  # 依據表 helper 缺件 → 不猜列名,只誠實說同源
        _same_src = "＝ 上方總表 ② 依據表的綜合健康度那一列"
    st.markdown(
        f"<div style='background:linear-gradient(90deg,{color}22,{color}11);"
        f"border-left:6px solid {color};border-radius:8px;padding:14px 18px;margin:8px 0 12px'>"
        f"<div style='font-size:13px;color:{GRAY_AA};margin-bottom:4px'>📌 當前總經 verdict"
        f"　<span style='font-weight:400'>{_same_src}，同一個數字、不是第二個判斷</span></div>"
        f"<div style='font-size:24px;color:{color};font-weight:700;margin-bottom:6px'>"
        f"{icon} {level}　<span style='font-size:18px;color:{GH_FG_PRIMARY}'>score = {score:+.1f}</span></div>"
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
        # 2026-08-05 稽核 🔴 必修 2:原寫死「📦 投資組合」—— app.py 沒有這個分頁,
        # 指路文案指向不存在的地方。分頁名 SSOT = ui/helpers/story_nav._STEPS。
        from ui.helpers.story_nav import tab_label as _tab_label  # noqa: PLC0415
        st.info(f"ℹ️ 尚無已載入基金 — 至「{_tab_label('portfolio')}」載入後本表會自動填入")
        return

    n_total = summary.get("n_total", 0)
    n_add = summary.get("n_add", 0)
    n_hold = summary.get("n_hold", 0)
    n_reduce = summary.get("n_reduce", 0)
    n_exit = summary.get("n_exit", 0)
    # 2026-08-05 稽核 🟡 必修 5(a):4 個動作計數改吃 `ui/components/stat_tile.py`
    # (其狀態色再走 `ui/components/status.py` 的 TRAFFIC SSOT)。這兩個元件
    # v19.388 建立後 production **0 consumer**(`PROCESS.md §4` 稽核落地條款),
    # 本處為第一個真實 caller。**不做全站 migrate**(97 個 st.metric + 8 種手刻
    # tile = 數千行 churn,§8.1 step 6 反例)。
    # 「持有」刻意 status=None:status_color 的 ⬜ 語意是「資料不足」,
    # 拿來標「維持原配置」會誤導(§1 誠實)。
    from ui.components.stat_tile import stat_tile  # noqa: PLC0415
    st.caption(f"📋 共 {n_total} 檔分析")
    _act_tiles = (
        ("加碼", n_add,    "ok",      "跌深 + 多頭"),
        ("持有", n_hold,   None,      "維持原配置"),
        ("減倉", n_reduce, "caution", "保守化"),
        ("全撤", n_exit,   "bad",     "出清"),
    )
    for _col_act, (_lbl_act, _n_act, _lv_act, _sub_act) in zip(
            st.columns(len(_act_tiles)), _act_tiles):
        with _col_act:
            st.markdown(
                stat_tile(_n_act, _lbl_act, status=_lv_act,
                          sublabel=_sub_act, value_suffix=" 檔"),
                unsafe_allow_html=True)

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

    # 2026-08-05 稽核 🟡 必修 5(a):表格走 `ui/components/tables.styled_dataframe`
    # (預設 hide_index=True + use_container_width=True,與原呼叫**逐參數等值**,
    # 不改 df 內容/列數/欄數)。同為 v19.388 建立後 0 consumer 的元件。
    from ui.components.tables import styled_dataframe  # noqa: PLC0415
    styled_dataframe(df.style.apply(_row_style, axis=1))

    # v19.22.1 hotfix：本函式原本被外層摺疊容器包覆，Streamlit 禁止 nested
    # expanders → 沿用 v17.2 慣例改用 st.container(border=True)。
    # 2026-08-10：外層那層殼已拆除，nested 限制不再適用；此處 container 仍保留 ——
    # 它在這裡的作用是「附註區塊的視覺分界」，本來就不是為了摺疊而存在。
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


# ── §1 Fail-Loud 區塊邊界（2026-08-05 v19.429）──────────────────────────────
# 總經 Tab 的四時域 section（長期／中期／短線／拐點／AI + 即時決策矩陣）原為
# **裸呼叫**：任一 section 在特定線上資料下拋例外會連坐整個總經 Tab；且 app.py 以
# st.tabs 單次 run 渲染全部分頁，總經（第 1 個 with 區塊）未捕捉的例外會中止整個
# script，使其後分頁（健診／批次／個基／組合／參考）全數空白。本檔既有慣例：
# china-drag／綜合健康度 hero／五桶 bar 三塊各自 try/except 降級；此處把同一「單塊
# 隔離」慣例補到剩下的 section。**不吞例外**（§1）：沿用 `_friendly_error`（統一
# 錯誤呈現 + stderr 鏡射進 Streamlit Cloud log + 可展開 traceback 供定位確切
# file:line）；失敗的 section 就地顯示，其餘 section 與其他分頁照常渲染。
def _safe_section(_label: str, _fn, *args, **kwargs) -> None:
    """跑 `_fn(*args, **kwargs)`；若拋例外 → 就地 Fail-Loud 顯示 + log，不外拋。"""
    try:
        _fn(*args, **kwargs)
    except Exception as _sec_e:  # noqa: BLE001 — §1 區塊隔離：顯式顯示 + log，非靜默吞
        _friendly_error(
            f"「{_label}」區塊渲染失敗", _sec_e,
            hint="此區塊已隔離，其他區塊與分頁不受影響；請展開下方「🔧 技術細節」"
                 "把 traceback（含 File \"...\", line N）截圖回報，即可精準定位根因。",
            level="error")


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

    # 2026-08-19（user「說明欄位太多太複雜,請簡化」）:top 原疊 4 行 meta(4 層流程導覽
    # 2 行 + 決策動線 1 行 + 加權方法論 1 行)→ 精簡為單行決策動線;方法論細節下沉,
    # 不在最上方擋內容。render_flow_nav / 方法論 caption 移除(仍保留於 story_nav 供他頁)。
    from ui.helpers.story_nav import render_story_nav
    render_story_nav("macro")

    # ⚡ 今日關鍵橫幅已下移至總表「③ 例外」層(2026-08-05 F1 資訊架構重構)。
    # 它回答的是「有沒有該警覺的」,屬總表第三層;掛在載入按鈕之前時,使用者會
    # 先看到警示才看到結論,與 user 拍板的四層閱讀順序相反。渲染邏輯本身未改。

    # v18.174：「🗺️ 全局指標關聯地圖」整塊搬到「說明書 §10」（純教學圖，無動態資料）
    # 函數 render_indicator_map() 保留在本檔頂層供 tab6 import 復用

    if not FRED_KEY:
        not_ready("尚未設定 FRED 金鑰，無法載入總經資料",
                  where="Streamlit Cloud → Settings → Secrets 的 `FRED_API_KEY`")
    else:
        _last_upd = st.session_state.get("macro_last_update")
        if _last_upd:
            _age_h   = (_now_tw() - _last_upd).total_seconds() / 3600
            _upd_str = _last_upd.strftime("%Y-%m-%d %H:%M")
            if _age_h > 4:
                # v16.0 異常遮罩：原 warning 會讓新手以為程式壞掉，改溫馨提示
                st.info(f"ℹ️ 指標數據已 {_age_h:.1f} 小時未更新（上次：{_upd_str}），點擊下方「🔄 更新總經資料」即可同步最新數據。")
            else:
                st.caption(f"✅ 已載入 · {_upd_str} TW（{_age_h:.1f}h 前）")
        else:
            st.info("💡 尚未載入總經資料，點擊下方按鈕開始")

        # v19.50：載入按鈕拆雙鈕 — 一般載入（吃既有 cache）／ 強制重抓（保證最新）
        # user 2026-08-24：版面對齊 Stock 的 `tab_macro.py`（`🚀 一鍵更新全部數據`）——
        # 改為**兩顆各自整條寬、上下排**，不再用 `st.columns([3, 2])` 擠在同一列。
        # 這是這頁的主要動作按鈕，橫向只佔 3/5 寬時在寬螢幕上不夠顯眼，
        # 使用者一進來常找不到而以為畫面壞了（截圖回報）。
        #
        # ⚠️ 2026-09-02 五分頁 IA 第三批 —— **上面那段是沿革，不是現況**
        # （**有意識的政策變更，不是漏刪** · 決策者：客戶拍板線框
        #  `docs/wireframes/wireframe-macro-health.html` **Form ①-A**）。
        # 舊寫法（兩顆**裸** `st.button`：`btn_macro_load` ＋ `btn_macro_force`）
        # **在它寫下的當天是對的** —— 它解的是「主要動作按鈕不夠顯眼」，那個理由今天
        # 依然成立（本批把兩顆收成一顆整條寬的送出鈕，顯眼度沒有變差）。
        # 被權衡掉的是它的**副作用**：線框就地點名「使用者常誤按兩次」——
        # 兩顆裸鈕各自觸發一次 rerun，而這一頁的載入會**並行打四路外部來源**。
        # 現行：整列收進一個 `st.form`（IA 鐵則 02），勾選過程完全不重繪，
        # 按下唯一那顆送出鈕才跑。
        _btn_label = "🔄 更新總經資料" if st.session_state.macro_done else "📡 載入總經資料"
        # ⚠️ 送出鈕的字**刻意保留動態**（線框畫的是靜態的「📡 載入 ／ 更新總經資料」）：
        # 線框那一格要表達的是「**一顆鈕同時涵蓋載入與更新**」，而既有的動態字
        # 已經做到同一件事，而且多告訴使用者「你現在是哪一種」。**這是本批對線框的
        # 唯一一處刻意偏離，已在 PR 描述具名回報。**
        with applied_form("macro_load_form", submit_label=_btn_label) as _macro_gate:
            # ⚠️ 2026-09-02 就地更正（**有意識的更正，不是漏刪** · 日期 2026-09-02 ·
            # 決策者：AI 總管，依據獨立稽核的執行期實測）：
            # 舊文案 ~~「要更新哪幾塊？（預設全選；**沒有勾的不會重抓**，沿用上次結果）」~~
            # **對「風險雷達」與「拐點偵測」兩路是假的。**
            # **舊文案的用意仍然成立**（勾選框確實會讓這裡少送兩個 future）；
            # **被推翻的是它的前提** —— 稽核用 AppTest 實測：取消勾選之後那兩路
            # **照樣被打**，只是從並行執行緒搬到序列渲染路徑：
            #   `ui/tab1_macro_radar.py::render_short_radar_section` 與
            #   `ui/tab1_macro_inflection.py` 都拿 session 的
            #   `_radar_v1921_top` / `_tp_v1948_top` 當快取，**而唯一的寫入者就是下面
            #   那兩個 `if _fu_* is not None:`** → 沒勾 → key 從未寫入 → 它們落進
            #   自己的 `else:` 分支、自己呼叫 `detect_risk_radar` / `detect_turning_points`。
            # 失效範圍正好是最該有效的兩次：**冷 session** 與**勾了「強制重抓」那一次**
            # （清快取清單含這兩個 key）；暖 session 才是好的。
            # 真正的修法要動那兩個下游檔，**不在本批檔案邊界內** → 已登記交總管另批。
            st.caption("要更新哪幾塊？（預設全選）")
            st.caption(
                "⚠️ 取消勾選「總經指標」／「新聞」＝ 這一輪**真的不重抓**，沿用上次結果；"
                "取消勾選「風險雷達」／「拐點偵測」**只會略過這裡的預抓** —— "
                "它們的區塊用到時仍會自己抓一次。")
            _cw = st.columns(4)
            _want_ind = _cw[0].checkbox("總經指標", value=True,
                                        key="chk_macro_want_ind")
            _want_news = _cw[1].checkbox("新聞", value=True,
                                         key="chk_macro_want_news")
            _want_radar = _cw[2].checkbox("風險雷達", value=True,
                                          key="chk_macro_want_radar")
            _want_tp = _cw[3].checkbox("拐點偵測", value=True,
                                       key="chk_macro_want_tp")
            _force_reload = st.checkbox(
                "🆕 強制重抓最新（清快取）",
                value=False,
                key="chk_macro_force",
                help="v19.57 C1：僅清 Tab1（總經）快取 + radar/tp session 殘留，"
                     "其他 Tab（基金詳情/組合/模擬器）不受影響")
        # ⚠️ `_macro_gate` **一定要在 `with` 之外**判斷（送出鈕排在所有 widget 之後
        # 才建立，區塊內恆為 False）—— 見 `ui/helpers/ia/gated_form.py` 的 ⚠️。
        _do_load = bool(_macro_gate)
        if _do_load and _force_reload:
            try:
                from services.macro import clear_tab1_macro_caches
                _clr = clear_tab1_macro_caches(session_state=st.session_state)
                st.toast(
                    f"✅ Tab1 精準清快取：TTL {_clr['ttl_cleared']} 條 / "
                    f"st_cache {_clr['st_cache_cleared']} 條 / "
                    f"session {_clr['session_keys_popped']} 鍵",
                    icon="🆕")
            except Exception as _e_clr:  # noqa: BLE001
                # 稽核 A10：原本是 `pass` —— 清快取失敗被完全吞掉，**但下面兩行
                # 照樣把 macro_done 設 False、_do_load 設 True**，於是使用者按了
                # ⚠️ 2026-09-02 就地更正（**只更正事實，不改本段結論**）：
                # 「下面兩行」自本批起是**一行** —— `_do_load = True` 已隨兩顆裸鈕
                # 收進 form 而移除（送出鈕本身就代表要載入）。**A10 描述的假成功
                # 路徑一字未變**：清快取失敗 → 照樣往下載入 → 可能拿到舊快取。
                # 「強制重抓最新（清快取）」，拿到的其實是舊快取的資料，畫面卻
                # 一路跑到「✅ 已抓取 N 個指標」。這是最典型的「假成功」（§1）。
                # 改法：留痕 + 明說快取沒清掉，讓使用者知道這次不是真的最新。
                import sys as _sys_clr
                import traceback as _tb_clr
                print(f"[tab1_macro/clear_cache] {type(_e_clr).__name__}: {_e_clr}",
                      file=_sys_clr.stderr)
                _tb_clr.print_exc(file=_sys_clr.stderr)
                # 2026-08-28 顏色批次二之一：這句自己就說「下面的資料可能仍來自舊快取」
                # ＝ 畫面上的數字**可能是錯的**（不是「少一張圖」）。依 render_state
                # system_error 的通過條件，只要有任何一個數字會變 → degraded=False。
                system_error(
                    "快取沒有清成功", _e_clr,
                    hint="下面重新載入的資料**可能仍來自舊快取**，不保證是最新。"
                         "請改用左側「🧹 全域刷新」，或稍後再試。")
            # ⚠️ 這裡**不再**寫 `_do_load = True` —— 舊寫法裡「強制重抓」是獨立的
            # 第二顆鈕，按下去必須自己觸發載入；現在它是 form 內的一個勾選框，
            # 能走到這一行就代表送出鈕已經按下（`_do_load` 為 True）。
            # 留著那行會讓 gate 形同虛設（無條件為真），正是 IA 鐵則 02 要防的事。
            st.session_state.macro_done = False
        if _do_load:
            # v19.49：合併 2 spinner 為 1，並用 ThreadPoolExecutor(max_workers=4) 並行抓取
            # indicators / news / radar / turning_points → wallclock = max(各 IO 時間)
            # navigator + 下方面板共享 session_state cache，零重抓
            with st.spinner("📡 並行抓取 總經指標 + 新聞 + 雷達 + 拐點..."):
                _t0_macro = _time_mod.time()
                from concurrent.futures import (
                    ThreadPoolExecutor as _TPE_ml,
                    TimeoutError as _FutTimeout,
                )
                _has_fred = bool(FRED_KEY) and len(str(FRED_KEY).strip()) >= 30
                # v19.501 §1 UI 安全網:四路 future 共用同一 wall-clock 死線,到點就 fail-loud
                # (user 2026-08-21 回報載入卡 10 分鐘 —— NAS proxy 半死時每網址付 retries×
                # timeout,幾十個串行呼叫累加成分鐘級,原本 .result() 無 timeout + `with` 區塊
                # 離開時 shutdown(wait=True) 兩處都無限等)。75s 足夠 FRED batch + PMI fallback,
                # 遠低於 10 分鐘病態;radar/tp 內部已各自 .result(timeout=15/25) 收斂。
                _MACRO_BUDGET_SEC = 75
                _macro_deadline = _time_mod.monotonic() + _MACRO_BUDGET_SEC

                def _ml_left():
                    return max(1.0, _macro_deadline - _time_mod.monotonic())

                _ex_ml = _TPE_ml(max_workers=4)
                try:
                    # 2026-09-02：四路各自受 form 內的勾選框控制（線框 Form ①-A）。
                    # 沒有勾的那一路**不會在這裡 submit**。
                    # ⛔ **但「不 submit」≠「不會被抓」，這一點務必看清楚**
                    # （2026-09-02 就地更正，**有意識的更正，不是漏刪**；
                    #  依據：獨立稽核的 AppTest 執行期實測）：
                    # 舊註解寫 ~~「而是真的少打一次外部來源」~~ ——
                    # 對 `fetch_all_indicators` / `fetch_market_news` **成立**
                    # （它們的消費端只讀 session，不會自己補抓）；
                    # 對 `detect_risk_radar` / `detect_turning_points` **不成立** ——
                    # 下游 `ui/tab1_macro_radar.py` / `ui/tab1_macro_inflection.py`
                    # 讀不到 session 快取時會**自己抓一次**，總次數一次都沒少。
                    # 兩個下游檔不在本批檔案邊界內 → 缺口已登記交總管另批。
                    _fu_ind = (_ex_ml.submit(fetch_all_indicators, FRED_KEY)
                               if _want_ind else None)
                    _fu_news = (_ex_ml.submit(fetch_market_news, max_per_feed=5)
                                if _want_news else None)
                    if _has_fred and (_want_radar or _want_tp):
                        from services.risk_radar import (
                            detect_risk_radar, summarize_radar,
                        )
                        _fu_radar = (_ex_ml.submit(detect_risk_radar, FRED_KEY)
                                     if _want_radar else None)
                        _fu_tp = (_ex_ml.submit(detect_turning_points, FRED_KEY)
                                  if _want_tp else None)
                    else:
                        _fu_radar = None
                        _fu_tp = None
                    # ⚠️ `_ind_fetched` 是本批最承重的一個旗標：**只有它為 True，
                    # 下方才准更新「上次抓取時間」**。少了它，使用者取消勾選「總經指標」
                    # 之後畫面會顯示「✅ 已載入 · <剛剛>」，而那批數字其實是舊的
                    # —— 那是捏造新鮮度（`CLAUDE.md §1` / §2.4）。
                    _ind_fetched = _fu_ind is not None
                    if _fu_ind is None:
                        # 沿用上次結果（copy 一份，避免下方寫入回頭改到 session 內的 dict）
                        ind = dict(st.session_state.get("indicators") or {})
                    else:
                        ind = {}
                    try:
                        if _fu_ind is not None:
                            ind = _fu_ind.result(timeout=_ml_left())
                    except _FutTimeout as _te:
                        ind = {}
                        _friendly_error(
                            "總經指標載入逾時", _te,
                            hint=f"超過 {_MACRO_BUDGET_SEC}s 仍未回傳,多半是 NAS proxy 或某"
                                 "資料來源卡住。背景執行緒會在各自 socket timeout 後自行結束,"
                                 "本次先跳過、不假裝有資料。請按側欄「🔍 測試 Proxy 連線」"
                                 "確認後重試。",
                            level="error")
                    except Exception as _me:
                        ind = {}
                        _friendly_error(
                            "總經指標載入失敗", _me,
                            hint="多半是 NAS proxy 連線異常或來源暫時無回應；"
                                 "可按側欄「🔍 測試 Proxy 連線」確認，或稍後重試。",
                            level="error")
                    _news_fetched = _fu_news is not None
                    _news = []
                    try:
                        if _fu_news is not None:
                            _news = _fu_news.result(timeout=_ml_left())
                    except _FutTimeout as _nte:
                        _news = []
                        _friendly_error(
                            "新聞掃描逾時", _nte,
                            hint="部分 RSS 來源沒在預算內回來;不影響總經指標分析,"
                                 "本次僅以指標面綜合判讀。",
                            level="info")
                    except Exception as _ne:
                        _news = []
                        _friendly_error(
                            "新聞掃描暫時失敗", _ne,
                            hint="不影響總經指標分析，可稍後重試；本次僅以指標面綜合判讀。",
                            level="info")
                    if _fu_radar is not None:
                        try:
                            _r_pre  = _fu_radar.result(timeout=_ml_left())
                            _rs_pre = summarize_radar(_r_pre)
                            st.session_state["_radar_v1921_top"] = (_r_pre, _rs_pre)
                        except _FutTimeout:
                            st.session_state["_radar_v1921_top"] = (None, None)
                            # ⚠️ **下一批候選，本批刻意不動**（2026-08-28 稽核 A9 登記）：
                            # 逾時＝真失敗，而且 `(None, None)` 之後下方整個風險雷達
                            # 區塊真的不渲染 —— 但這裡是灰字。
                            # **兩把獨立的尺都掃不到它**，因為 handler 沒有把例外物件
                            # 印出來（`_FutTimeout` 未綁 `as`，訊息是純字面字串），
                            # 結構上與「這格沒資料」無法區分（見測試檔規則 1 盲點 4）。
                            # 不在本批改的理由：它不在本批用來定義範圍的那個掃描結果裡，
                            # 逕自加碼會讓「43 處」這個數字失去可複現性（§8.4 step 4）。
                            #
                            # 📌 **2026-08-28 批次二之二補一個「事實」，不改行為**：
                            # 本函式裡**同一種** `_FutTimeout`（都是 `.result(timeout=…)`
                            # 沒回來）現在有**三種顏色**：`_fu_ind` → `level="error"` 🔴、
                            # `_fu_news` → `level="info"` 🔵、`_fu_radar` 與 `_fu_tp` →
                            # `st.caption` ⬜。這正是測試檔 `_TWIN_FAILURES` 在守的那個形狀
                            # （同一個失敗、不同顏色），只是它跨的是「同一函式內的四個 future」
                            # 而不是跨分頁，所以那條規則涵蓋不到。
                            # ⚠️ **這是事實，不是「所以該全部改紅」的結論** —— 三者的後果確實
                            # 不同（指標是主體，news / radar / tp 是附屬），顏色分級**可能是
                            # 刻意的**。下一批要動它時，要先回答的是「附屬區塊整塊失敗算不算
                            # 系統真出錯」，而不是直接上色。
                            # （查證，量測日 2026-08-28，實跑過：
                            #  `python -c "import ast,pathlib;t=ast.parse(pathlib.Path('ui/tab1_macro.py').read_text());print([(h.lineno,[(ast.unparse(c.func),[ast.unparse(k) for k in c.keywords]) for c in ast.walk(h) if isinstance(c,ast.Call)]) for h in ast.walk(t) if isinstance(h,ast.ExceptHandler) and '_FutTimeout' in ast.unparse(h.type or ast.Constant(''))])"`
                            #  → 4 個 handler，顏色分別為 error / info / caption / caption。）
                            st.caption("⚠️ 風險雷達逾時未回,本次略過(不影響指標判讀)。")
                        except Exception:
                            st.session_state["_radar_v1921_top"] = (None, None)
                    if _fu_tp is not None:
                        try:
                            st.session_state["_tp_v1948_top"] = _fu_tp.result(timeout=_ml_left())
                        except _FutTimeout:
                            st.session_state["_tp_v1948_top"] = None
                            # ⚠️ 同上（稽核 A9）：逾時＝真失敗、拐點區塊真的消失，
                            # 卻是灰字；兩把尺都掃不到。下一批候選，本批不動。
                            st.caption("⚠️ 轉折點偵測逾時未回,本次略過。")
                        except Exception:
                            st.session_state["_tp_v1948_top"] = None
                finally:
                    # ⚠️ 關鍵修:原 `with ... as _ex_ml:` 離開時 shutdown(wait=True) 會在上面
                    # 每個 .result(timeout=) 之後「再次」阻塞等所有卡在 C-level socket read 的
                    # worker 跑完 → timeout 形同虛設。改 wait=False:UI 立刻往下顯示逾時訊息;
                    # 背景執行緒無法真正 kill(Python 先天限制),但各 fetch_url socket timeout
                    # (5~20s,Change D 收緊)會讓它們自然收斂,不留假死。
                    _ex_ml.shutdown(wait=False, cancel_futures=True)
                _macro_ms = round((_time_mod.time() - _t0_macro) * 1000)
                if not ind and not _ind_fetched:
                    # 本次刻意沒勾「總經指標」，而且先前也沒有可沿用的 —— 這是
                    # 「條件不足」不是「系統壞了」，依三態要走 ⬜ 灰不是 🔴 紅。
                    not_ready(
                        "本次沒有勾選「總經指標」，先前也沒有已載入的指標可以沿用",
                        # 不寫方位詞（「上方」）：方位是版面順序的函數，
                        # 下一次重排就會指錯 —— 沿用 #759 的既有教訓。
                        where="在載入表單裡勾回「總經指標」，再按一次送出鈕")
                elif not ind:
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
                    if _ind_fetched:
                        # ⚠️ **只有真的重抓才蓋時間戳**。沿用舊指標時蓋下去，
                        # 上方時效列會顯示「✅ 已載入 · 剛剛」，而數字是舊的 ——
                        # 那是捏造新鮮度（§1「錯誤的數字比沒有數字更危險」／§2.4）。
                        st.session_state.macro_last_update = _now_tw()
                    # 稽核 D4：與 app.py 同一個 bug 的第二份副本。
                    # 原 `.get("value",4.0)/100` 會在 value 為 None 時
                    # (a) 捏造 4% 無風險利率灌進全站 Sharpe/Sortino（§1）、
                    # (b) 手抄 services.fund_service._RF_ANNUAL 的值（非 SSOT）、
                    # (c) `None/100` 直接 TypeError。缺值改不呼叫 + 寫 stderr。
                    _fed_v_t1 = (ind.get("FED_RATE") or {}).get("value")
                    if _fed_v_t1 is not None:
                        set_risk_free_rate(float(_fed_v_t1) / 100)
                    elif "FED_RATE" in ind:
                        import sys as _sys_rf_t1
                        print("[tab1_macro] FED_RATE 存在但 value 為 None → "
                              "不設定無風險利率，沿用 SSOT 預設（不捏造）",
                              file=_sys_rf_t1.stderr)
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
                    # ⚠️ 沒勾「新聞」時**整段跳過**：覆寫成空清單會把上次抓到的
                    # 新聞與系統性風險判讀無聲清掉，使用者只是「這次不想重抓新聞」。
                    if _news_fetched:
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
                    if _ind_fetched:
                        st.success(
                            f"✅ 已抓取 {len(ind)} 個指標！"
                            f"（{_now_tw().strftime('%H:%M')} TW｜{_macro_ms}ms）")
                    else:
                        # 不說「已抓取」——這一輪根本沒去抓指標。
                        st.success(
                            f"✅ 已更新（本次未重抓總經指標，沿用上次 {len(ind)} 個；"
                            f"{_macro_ms}ms）")

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
        # 2026-08-05 F1:四時域的「一覽」由總表 ② 依據表承接(原 bar renderer 已刪),
        # 四個分組 subheader 仍在下方詳細區,順序不變。
        # ════════════════════════════════════════════════════════════

        # Detox(v19.487):ph / alloc / advice 為已刪除的 bar renderer 遺留(見上方註解
        # 「原 bar renderer 已刪」),assign 後全程未用 → 移除死變數(§3.3)。

        # ════════════════════════════════════════════════════════════
        # 🧾 總表區 —— 2026-08-05 user 拍板的資訊架構
        #   「最重要的總表放在最上方,下方都是放詳細資料與說明」
        #   形式選擇:混合 —— 結論用敘事、依據用表格。
        #
        # 四層對應初學者的自然提問順序:
        #   ① 結論    現在該加碼還是防禦?    敘事(streamlit 原生告示元件)
        #   ② 依據    憑什麼?                表格(兩把尺並陳 + 各桶狀態 + 指路)
        #   ③ 例外    有沒有該警覺的?        敘事
        #   ④ 可信度  這些數字能信嗎?        chip + 既有資料新鮮度條(一字未改)
        #
        # 本次「合」的界線(user 明示,不可搞混):把**講同一件事的幾個結論**
        # 合成 1 個 —— 原本 hero 卡 / 五桶 bar / 夾在中間的對照 caption 三處
        # 講同一批數字、三套尺度;**不**把 18 個指標合成 5 個 —— 詳細資料
        # 一格都沒少,全數保留在下方詳細區。
        # 回退方式:git history 有原本的 hero 卡 HTML 與五桶 bar renderer。
        # ════════════════════════════════════════════════════════════
        st.markdown("## 🧾 總表 — 先看這裡")

        # ══ ① 結論 —— 一句話 + 理由條列(敘事)═══════════════════════
        # `services.macro.action_light.macro_action_light` 於 v19.316 依 user
        # 2026-07-05 核准的草案實作完成(硬衰退/恐慌 override → 景氣位階三級 →
        # 缺位階誠實 🟡),`tests/test_macro_action_light.py` 8 條測試守著。
        # 燈色 → `_action_light_renderer` 分派:🟢 `st.success` / 🟡(與未知燈色)
        # `st.warning` 兩支仍是原生元件;🔴 走 `_business_alert_action_light`
        # (業務警訊卡)—— 2026-09-03 批次二起**不再是** `st.error`,也不是原生元件
        # (理由見該函式 docstring 的就地更正段:手上沒有 exception、印的是業務
        # 結論,不得走系統紅框)。⚠️ 本行在 2026-09-04 稽核前仍寫「st.success /
        # warning / error 原生元件」,兩處與實作不符 —— 就地更正,非漏刪。
        st.markdown("### ① 結論 — 現在該加碼還是防禦")
        try:
            from services.macro import macro_action_light  # noqa: PLC0415
            _al = macro_action_light(ind, phase.get("score"))
            # 空行是 markdown 需要的:少了它,下面的 `- ` 條列不一定會被當成 list。
            _al_lines = [f"**{_al['light']} 現在能不能買 ── {_al['action']}**", ""]
            _al_lines += [f"- {_r}" for _r in (_al.get("reasons") or [])]
            if _al.get("override"):
                _al_lines.append(
                    "- ⚠️ 安全層優先:硬衰退 / 恐慌訊號亮起時,不論景氣位階多高一律轉保守")
            _al_lines.append(
                "- 這是「位階 / 機率」不是「擇時」;憑什麼這樣說 → 看下面 ② 依據表,"
                "推導細節 → 看再下方的四時域分區")
            _action_light_renderer(_al["light"])("\n".join(_al_lines))
        except Exception as _al_e:  # noqa: BLE001 — 結論燈失敗不得擋掉整頁總經
            # 消失的是本頁**最上面那個結論**（現在能不能買 + 理由）。灰字會讓人以為
            # 「還沒載入、按一下就好」，實際按幾次都一樣。
            system_error("① 買賣總結燈渲染失敗", _al_e)

        # ══ Section 02 —— 5 卡快覽網格(客戶拍板線框批次二,見上方
        # `_render_top_card_grid` docstring)══════════════════════════
        # 2026-09-04 稽核 P4:本呼叫先前是裸的 —— 網格自身(非某一張卡)炸掉時,
        # 唯一的接應是 `app.py` 的分頁級 except,而它會把**整個 Tab ①** 換成
        # friendly_error。加一層 section 級隔離:網格掛了只掉這一段,②依據表、
        # ③例外層、④可信度與下方四時域詳細區照常。
        try:
            _render_top_card_grid(ind, phase)
        except Exception as _grid_e:  # noqa: BLE001 — 快覽網格失敗不得擋掉整頁總經
            system_error("總表 Section 02 快覽卡網格渲染失敗", _grid_e)

        # ══ ② 依據 —— 表格(兩把尺並陳 + 各桶狀態 + 每列指路)══════════
        # 這張表取代三個原本各自為政的區塊,資料一格不少地併進來:
        #   - 🩺 綜合健康度 hero 卡(多空加權淨分,有正負)
        #   - 📊 五桶 summary bar(長期 / 中期 / 短線 / 拐點 / 新聞)
        #   - 夾在兩者之間、說明「別互相換算」的那行 caption
        # 那行 caption 現在是表格「說明」欄本身(user 要求:不要留兩份說法)。
        st.markdown("### ② 依據 — 憑什麼這樣說")
        # 哨兵:`None` = ② 這一段**沒跑完**(下方 except 會維持它);
        # dict(含空 dict)= ② 跑完了。③ 例外層據此區分「沒有例外」與「算不出來」
        # (2026-08-05 稽核 🔴 必修 2;原初值是 `{}`,兩種狀態無法區分)。
        _5b_summary = None
        try:
            from ui.helpers.macro.beginner_view import (  # noqa: PLC0415
                build_evidence_rows,
                build_evidence_footnotes,
                compute_five_bucket_summary,
                render_evidence_table,
                split_evidence_footnotes,
            )
            from ui.helpers.macro.helpers import (  # noqa: PLC0415
                calculate_composite_score,
                composite_verdict,
            )
            _news_items = st.session_state.get("news_items")
            # 先寫進 local:哨兵 `_5b_summary` 要到**表格真的畫出來**之後才交棒。
            # 桶算完了但表格渲染炸掉時,③ 不能說「讀數完整列在上方 ② 依據表」
            # —— 那張表根本不在畫面上(必修 2 的界線是「② 這一層有沒有成立」)。
            _5b = compute_five_bucket_summary(ind, phase, news_items=_news_items)
            # 指標筆數吃 v19.270 D8 #8 的 provenance 側車(筆數隨來源命中浮動,
            # 寫死字面值那版已經漂移過一次)。
            _comp_prov: dict = {}
            _comp_score = calculate_composite_score(ind, provenance_out=_comp_prov)
            # v19.428:persist composite 總分供跨分頁消費 —— 換股顧問成長型「總經看衰」判斷
            # (services/switch_advisor.py 讀 session composite ≤ -5)+ macro AI 綜合分數。
            # 此前 _comp_score 只是 local 變數、session 鍵無 producer → 消費者永遠讀 None(稽核 HIGH)。
            st.session_state["composite_score"] = _comp_score
            _comp_n = int(_comp_prov.get("n_indicators") or 0)
            _cv_icon, _cv_level, _, _cv_action = composite_verdict(_comp_score)
            _ev_rows = build_evidence_rows(
                _5b,
                composite_score=_comp_score,
                composite_icon=_cv_icon,
                composite_level=_cv_level,
                composite_action=_cv_action,
                n_indicators=_comp_n,
            )
            # 必修 3:欄內放不下的長說明(兩套切點揭露 / 完整門檻 / 全綠判讀規則 /
            # 白話行動)由同一份 summary 導出,併進表下那一則 caption。
            # 拿掉 `footnotes=` 這個引數 → 那幾句在畫面上完全消失(接線點)。
            _ev_notes = build_evidence_footnotes(
                _5b, composite_action=_cv_action)
            # 2026-09-03 減字(B):同一批註記分兩層印 —— 上表「說明」欄短版的
            # **完整版**收進摺疊(推導細節),沒有欄內短版的那兩則(🌳 兩套切點
            # 揭露 / 🩺 算式 + 白話行動)維持常駐。分類理由見
            # `_evidence_footnote_items` docstring;`footnotes=` 仍是**完整**清單,
            # 拿掉 `collapsed_footnotes=` 只會退回「全部常駐」,不會少印任何一則。
            _, _ev_collapse = split_evidence_footnotes(
                _5b, composite_action=_cv_action)
            render_evidence_table(_ev_rows, footnotes=_ev_notes,
                                  collapsed_footnotes=_ev_collapse)
            # 表格已在畫面上 → 哨兵交棒,③ 才可以指路回這張表(見上方註解)。
            _5b_summary = _5b
            # v19.459 ①:資產水位連動(composite → 股/債/貨幣 配置水位 + 動態 Z 門檻)。
            # NDC 景氣對策信號(9~45)接回 → 綠燈放寬停利 / 紅燈收緊加碼;抓不到 → 退預設門檻(誠實)。
            from services.allocation_ladder import allocation_from_composite  # noqa: PLC0415
            from ui.helpers.macro.ndc import get_ndc_score  # noqa: PLC0415
            _ndc = get_ndc_score()
            _al = allocation_from_composite(_comp_score, _ndc)
            if _al.get("status") == "ok":
                _a = _al["allocation"]
                st.markdown(
                    f"**{_al['icon']} 建議資產水位（{_al['level']}）**："
                    f"股票 **{_a['equity']}%** ・債券 **{_a['bond']}%** ・貨幣/現金 **{_a['cash']}%**"
                    f"　｜　停利 Z ≥ {_al['stop_gain_z']:+.2f} ・加碼 Z ≤ {_al['add_z']:+.2f}"
                    f"（{'景氣' + _al['light'] + '燈動態' if _al.get('light') else '預設門檻'}）")
                st.caption("↑ 依總經健康度總分的 DESIGN 配置建議(非投資指示);"
                           "Z 門檻供個基體檢的再平衡訊號使用。")
            # v19.367 6/8:F-RECON-1 健康度雙演算法對帳 chip
            # (§4.3 — 加權淨分 vs 不加權多空投票),走 `ui.components.status.status_chip`
            # (dataviz #4:狀態恆帶 emoji + 文字 + 狀態色,不靠顏色單獨編碼)。
            # `note` 走 html.escape:chip 是 unsafe_allow_html,服務層字串若含
            # `<` / `>` 會被當標籤吃掉(同 tab1_macro_midcycle._card_note 的既有處置)。
            try:
                from html import escape as _esc_rc  # noqa: PLC0415
                from services.macro.composite_score import (  # noqa: PLC0415
                    reconcile_composite_score,
                )
                from ui.components.status import status_chip  # noqa: PLC0415
                _rc = reconcile_composite_score(ind)
                if _rc["status"] == "disagree":
                    st.markdown(status_chip(
                        f"對帳:{_esc_rc(str(_rc['note']))}", "warn",
                        sublabel=(f"投票 {_rc['n_pos']}多/{_rc['n_neg']}空,"
                                  f"net {_rc['vote_net_ratio']:+.2f}")),
                        unsafe_allow_html=True)
                elif _rc["status"] == "agree":
                    st.markdown(status_chip(
                        "對帳:加權淨分與多空投票同向", "ok",
                        sublabel=f"{_rc['n_pos']}多/{_rc['n_neg']}空"),
                        unsafe_allow_html=True)
                # neutral_mix / no_data → 不顯示(弱訊號不佔版面)
            except Exception as _rc_e:  # noqa: BLE001 — 對帳 chip 非致命,但不吞聲
                # 對帳 chip 報的是「加權淨分與多空投票同不同向」＝一個判讀結果，
                # 不是一張圖；它消失時使用者少掉的是「這個分數能不能信」的證據。
                system_error("② 對帳 chip 渲染失敗", _rc_e)
        except Exception as _ev_e:  # noqa: BLE001 — 依據表失敗不得擋掉整頁總經
            # 整張「憑什麼這樣說」的證據表（加權淨分 + 五桶狀態）消失 —— 那是本頁
            # 數字最密集的一塊，原本寫「(降級)」但降級的定義是「只掉一張圖」。
            system_error("② 依據表渲染失敗", _ev_e)

        # ══ ③ 例外 —— 敘事(今日關鍵 + 系統性風險 + 拐點 / 新聞桶)═══════
        # 只講「該警覺的」;沒有例外時誠實說沒有,不硬擠內容(§1)。
        st.markdown("### ③ 例外 — 有沒有該警覺的")
        # ⚡ 今日關鍵橫幅(v19.349;股票 v19.108 同構):訊號層吃 indicators 各
        # block 的 score(SCORE_RULES SSOT)+ 拐點層吃 detect_turning_points
        # 輸出 — 零新 I/O,全讀 session。未載入(兩者皆空)不渲染,避免誤導性
        # 的「無異常」。
        _ka_tp = st.session_state.get("_tp_v1948_top") or {}
        if ind or _ka_tp:
            try:
                from services.macro.daily_key_alerts import (  # noqa: PLC0415
                    collect_key_alerts as _cka,
                )
                from ui.helpers.macro.key_alerts import (  # noqa: PLC0415
                    key_alerts_banner as _kab,
                )
                st.markdown(_kab(_cka(ind, _ka_tp)), unsafe_allow_html=True)
            except Exception as _ka_e:  # noqa: BLE001
                # 橫幅內容就是「今天該警覺的事」；它不出現與「今天沒有該警覺的事」
                # 在畫面上長得一模一樣（§1 的鏡像違規）。
                system_error("③ 今日關鍵橫幅渲染失敗", _ka_e)
        try:
            # 必修 2:② 沒跑完時補一條「無法判定」,`_exc_lines` 因此非空 →
            # 下方那句「都不在警戒狀態」不會被印出來(它只在 ② 真的算完且全綠時成立)。
            _exc_lines = _exception_lines(
                st.session_state.get("systemic_risk_data"), _5b_summary)
            _exc_lines += _bucket_status_unavailable_line(_5b_summary)
            if _exc_lines:
                st.markdown("\n".join(_exc_lines))
            else:
                st.caption(
                    "✅ 新聞系統性風險未達警戒等級，拐點桶與新聞桶也都不在警戒狀態；"
                    "各桶讀數完整列在上方 ② 依據表。")
        except Exception as _ex_e:  # noqa: BLE001
            # 同上：例外層失敗時，畫面看起來就像「沒有例外」。
            system_error("③ 例外層渲染失敗", _ex_e)

        # ══ ④ 可信度 —— 這些數字能信嗎(chip + 既有資料新鮮度條)═════════
        # 新鮮度條沿用既有實作**一字未改**(它本身已是 chip 形式,含 hover
        # tooltip 與 FRED 逐序列命中狀態);這裡只補兩件原本頂部看不到、卻直接
        # 影響「能不能信」的事實:代理值與缺漏指標(§1 誠實揭露)。
        # 兩個判讀都在本檔模組層的純函式裡(可餵資料驗行為),此處只負責呈現。
        # 指標名走 `html.escape`:chip 是 unsafe_allow_html,服務層字串若含
        # `<` / `>` 會被當標籤吃掉(同本檔對帳 chip 的既有處置)。
        st.markdown("### ④ 可信度 — 這些數字能信嗎")
        try:
            from html import escape as _esc_tr  # noqa: PLC0415
            from ui.components.status import status_chip as _chip_trust  # noqa: PLC0415
            _n_loaded = sum(1 for _k, _v in (ind or {}).items()
                            if not str(_k).startswith("_") and isinstance(_v, dict))
            _proxy_names = _proxy_indicator_labels(ind)
            _missing_keys = _missing_indicator_keys(ind)
            _n_proxy = len(_proxy_names)
            _n_missing = len(_missing_keys)
            _n_expect = len(_TRUST_EXPECTED_KEYS)
            st.markdown(
                _chip_trust(
                    f"代理值 {_n_proxy} 筆", "warn" if _n_proxy else "ok",
                    sublabel=("非官方本尊，已標記："
                              + _esc_tr("、".join(_proxy_names))
                              if _proxy_names else "全部走官方本尊序列"))
                + "　"
                + _chip_trust(
                    f"缺漏指標 {_n_missing} 筆", "warn" if _n_missing else "ok",
                    # 分母(預期清單長度)與分子(實際缺幾個)**都從變數來**:
                    # 原寫法把分母直接接在「未取得」前面,畫面讀起來是「16 個未
                    # 取得」而主標寫「1 筆」,同一個 chip 自打嘴巴(§1 錯誤的數字
                    # 比沒有數字更危險)。else 分支本來就寫對,這裡補齊 warn 分支。
                    sublabel=(f"已載入 {_n_loaded} 筆；"
                              f"{_n_expect} 個關鍵指標中 {_n_missing} 個未取得："
                              + _esc_tr("、".join(_missing_keys))
                              if _missing_keys
                              else f"已載入 {_n_loaded} 筆；{_n_expect} 個關鍵指標全數到齊")),
                unsafe_allow_html=True)
        except Exception as _tr_e:  # noqa: BLE001
            # 這個 chip 報的正是「N 個關鍵指標中 M 個未取得」—— 它自己消失時，
            # 使用者連「上面那些數字完不完整」都不知道，比少一張圖嚴重得多。
            system_error("④ 可信度 chip 渲染失敗", _tr_e)

        # v19.50 ══ 📊 資料新鮮度條（總抓取時間 + age + 各區塊資料截止日）══
        _ml_upd = st.session_state.get("macro_last_update")
        if _ml_upd is not None:
            _age_min_ml = (_now_tw() - _ml_upd).total_seconds() / 60
            _age_color_ml = (TRAFFIC_GREEN if _age_min_ml < 60
                             else (TRAFFIC_YELLOW if _age_min_ml < 240 else TRAFFIC_RED))
            _age_label_ml = (f'{int(_age_min_ml)} 分鐘前' if _age_min_ml < 60
                             else f'{_age_min_ml/60:.1f} 小時前')
            # 各區塊資料截止日（從 ind 各 indicator 的 date 欄取）
            # v19.296 M5: 加 🟢/🟠/🔴 staleness emoji，對齊 Tab5 資料診斷的新鮮度邏輯
            # 月頻閾值：≤45天🟢 / ≤75天🟠 / >75天🔴（同 CLAUDE.md §2.4）
            _src_dates = []
            _today_src = _now_tw().date()
            # 左 = indicators dict 的 key(服務層寫入名),右 = 畫面標籤。
            # 失業率那格兩者不同名:服務層的 key 是失業率指標名,畫面沿用 FRED
            # series id 當標籤。原本左右都填標籤 → 這格永遠查無資料而靜默消失。
            for _k_src, _lbl_src in (("PMI", "PMI"), ("YIELD_10Y2Y", "10Y-2Y"),
                                     ("HY_SPREAD", "HY"), ("CPI", "CPI"),
                                     ("UNEMPLOYMENT", "UNRATE")):
                _v_src = (ind or {}).get(_k_src) or {}
                _d_src = str(_v_src.get("date", "")).strip()
                if _d_src:
                    try:
                        _age_src = (_today_src - pd.to_datetime(_d_src).date()).days
                        _s_emoji = '🟢' if _age_src <= 45 else ('🟠' if _age_src <= 75 else '🔴')
                    except Exception:
                        _s_emoji = '⬜'
                    _src_dates.append(f'{_s_emoji}{_lbl_src}:{_d_src}')
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


        # ════════════════════════════════════════════════════════════
        # 🔎 詳細區 —— 以下全部是「總表的依據」,一個區塊都沒刪。
        # 順序(2026-08-07 user 拍板「四時域優先」):
        #   🌳 長期 → 📈 中期 → 🎯 短線 → ⚠️ 拐點 → 📋 決策矩陣
        #   → 🇨🇳 中國副盤 → 🤖 AI 總結
        # 上方 ② 依據表的「詳細在下方哪一段」欄指向的就是這些區塊的標題;
        # 改排之前往下捲會先撞到兩個目錄沒提的區塊,指路與版面對不上,本次收斂。
        # ════════════════════════════════════════════════════════════
        st.divider()
        st.markdown("## 🔎 詳細資料與說明")

        # v19.41 MOVED: ③ 🔬 即時訊號 + 決策矩陣 已移至 tab 內結尾（時鐘前）
        # 改動原因：user 反饋「總經、短期、拐點 三個面板 — 總經放在最上方」，
        # ③ expander 原位於 tab 外擋在 ① 戰情室（總經）之前，下移後 tab 首屏即為總經面板

        # ══ v17.3 內層 Tab：戰情首頁（§6-6 資訊不藏匿）═══
        # v19.40 PR2: 📖 指標教學手冊 已搬至 📖 說明書 Tab §11 宏觀教學文獻
        # v19.42: 單一 tab 包裝拆除 — Streamlit tab strip 擋在 ① 戰情室（總經）前
        #         user 反饋「總經放在最上方」三度仍不見效 → 直接消滅 tab strip
        #         以 contextlib.nullcontext() 取代，所有 `with tab_main:` 區塊保持縮排不動
        import contextlib as _cl_v1942
        tab_main = _cl_v1942.nullcontext()

        # 2026-08-05 F1:🚦 結論燈 / 🩺 綜合健康度 hero 卡 / 📊 五桶 summary bar
        # 三段原本在這裡,已上移進本檔上方的總表區:
        #   - 結論燈           → 「① 結論」(內容與呼叫完全相同,只換位置)
        #   - hero 卡          → 「② 依據」表的 🩺 綜合健康度 那一列
        #   - 五桶 bar         → 「② 依據」表的其餘各列
        #   - 兩者之間的對照 caption → 「② 依據」表的「說明」欄 + 表下一行註記
        # 對帳 chip 一併隨 hero 上移(它是綜合健康度的雙演算法對帳)。

        with tab_main:
            # v19.18: 原 ① verdict 大卡已移除（與頂部新手面板 + 進階檢視 expander 重複）



            # v19.134 物理重排:60/40 col layout 已移除,sections 按四時域分組連續

            # ══════════════════════════════════════════════════════════
            # v19.134 — 🌳 長期座標 桶(物理重排,連續區塊)
            # v19.262 P3-A5:整 section 抽 ui/tab1_macro_longterm.py(-294 LOC)
            # ══════════════════════════════════════════════════════════
            from ui.tab1_macro_longterm import render_long_term_section
            _safe_section("🌳 長期座標", render_long_term_section,
                          ind, fred_key=FRED_KEY, show_l3=_show_l3)

            # ══════════════════════════════════════════════════════════
            # 🧭 總經指南針 —— 2026-08-05 稽核 🔴 必修 6:**整塊移除**。
            #
            # 沿革:v19.430 從 app.py 搬進詳細區,同日稽核 🟡 建議 6 再下移一段。
            # 兩次都只是搬位置,沒有解決它本身的兩個問題:
            #   (1) 三張卡全部是**重複**(user 原則 2)。逐張查證後,同一個問題在
            #       🎯 短線雷達都有現成的燈,且雷達是主載入按鈕就一起抓好的:
            #         · VIX          → 雷達 `vix_level`(且 ② 依據表短線列也有)
            #         · 美 10Y 殖利率 → 雷達 `yield_10y_shock`(FRED DGS10,
            #                            內含 vs Yahoo ^TNX 的雙源對帳 chip)
            #         · S&P 500 vs 60MA → 雷達 `spx_trend_break`,同一支 ^GSPC、
            #                            同一個「站上/跌破均線」語意,且列的是
            #                            50DMA / 200DMA 兩條**有燈號分級**的線。
            #       原稽核以為 60MA 那張「全頁獨有」;查 `services/risk_radar.py:360
            #       _signal_spx_trend_break` 後推翻 —— 把它併進雷達會變成同一區塊
            #       裡三個 SPX 均線讀數,反而製造新的重複。
            #   (2) 它是**獨立按鈕**(`_compass_fetch_btn`)+ 先 `cache_clear()` 再抓,
            #       使用者剛按完「載入總經資料」還得再按一次;沒按時整塊只是空框。
            #       且三條路徑各自抓 VIX,畫面可能同時出現三個不同的 VIX 值。
            # 依 `PROCESS.md §4` 0-consumer 條款,L3 元件 / L2 facade / L1 fetcher
            # 三層已於 2026-08-07 一併退役(元件與 facade 模組現為待 git rm 的
            # fail-loud 佔位,L1 fetcher 實體刪除)。
            # 回退方式:git history 有原本的呼叫與元件。
            # ══════════════════════════════════════════════════════════

            # ══════════════════════════════════════════════════════════
            # v19.134 — 📈 中期循環 桶(物理重排,連續區塊)
            # v19.262 P3-A3:整 section 抽 ui/tab1_macro_midcycle.py(-180 LOC)
            # ══════════════════════════════════════════════════════════
            from ui.tab1_macro_midcycle import render_mid_cycle_section
            _safe_section("📈 中期循環", render_mid_cycle_section,
                          ind, show_l3=_show_l3, show_l2_plus=_show_l2_plus)


            # ══════════════════════════════════════════════════════════
            # v19.134 — 🎯 短線雷達 桶(物理重排,連續區塊)
            # v19.262 P3-A4:整 section 抽 ui/tab1_macro_radar.py(-246 LOC)
            # ══════════════════════════════════════════════════════════
            from ui.tab1_macro_radar import render_short_radar_section
            _safe_section("🎯 短線雷達", render_short_radar_section,
                          fred_key=FRED_KEY, show_l3=_show_l3)

            # ══════════════════════════════════════════════════════════
            # v19.134 — ⚠️ 拐點警報 桶(物理重排,連續區塊)
            # v19.262 P3-A6:整 section 抽 ui/tab1_macro_inflection.py(-484 LOC)
            # ══════════════════════════════════════════════════════════
            from ui.tab1_macro_inflection import render_inflection_alert_section
            _safe_section("⚠️ 拐點警報", render_inflection_alert_section,
                          ind, phase=phase, fred_key=FRED_KEY, show_l3=_show_l3)

            # ══════════════════════════════════════════════════════════
            # 📋 即時訊號 + 決策矩陣 桶
            # ⚠️ **本區塊第四次搬家**,動前先讀完前三次的理由:
            #   - v19.41:原在 tab 外(擋在總經前),因 user 反饋「總經放在最上方」
            #     下移;v19.42:Tab① 內的 tab strip 因同一理由被消滅。
            #   - v19.4xx(第三次):從全頁最底部倒數第二區 → 上移到總覽之後、
            #     四時域之前,並改 expanded=True。理由:這是全頁唯一給出「所以呢」
            #     (逐檔 加碼/持有/減倉/全撤 + 目標權重)的區塊,埋在 13 個一級區塊
            #     之後 + 預設收合 = 算對了但使用者看不到。當時 user 曾列過「排在
            #     拐點之後」的順序,coder **刻意未照做**並登記為待裁決項。
            #   - 2026-08-05 F1(第四次動線調整,位置不變):上游錨點由五桶 bar
            #     換成總表的 ② 依據表。
            #   - 2026-08-07(本次):user 拍板「四時域優先」,上述待裁決項結案。
            #     **與前三次理由皆不衝突**:
            #       (a) v19.41 / v19.42 要的是「總經放在最上方」—— 指的是總表那四層,
            #           它們仍在全頁最頂端,本區塊只在詳細區**內部**換位,沒有回到
            #           擋在總經之前的舊位置;
            #       (b) 第三次擔心的是「埋起來看不到」。現在它前面只剩四個一級區塊
            #           (不是 13 個),`expanded=True` 也原樣保留,並非退回原狀。
            #   為什麼放在四時域之後、中國副盤與 AI 之前:四時域正是本區塊 verdict
            #   的推導依據,讀完依據緊接著看行動,中間**不插入任何非因果區塊** ——
            #   中國副盤是唯讀參考(不進總經分數),插在中間會把依據與行動切斷;
            #   AI 是對上面全部內容的綜述,必須排在最後一個。
            #   回退方式:整段移回四時域之前(git history 有第三次搬家後的位置)。
            # ══════════════════════════════════════════════════════════
            st.divider()
            st.markdown("## 📋 即時訊號 + 決策矩陣")
            st.caption("所以我該怎麼做 ｜ verdict 路徑 + 逐檔行動建議"
                       "（推導依據見上方四時域）")
            # 稽核 🟡 建議 10:標題原本帶內部代號(當年的工作項編號),
            # 對使用者是雜訊 —— 拿掉,語意不變。
            # 2026-08-10:整個 expander 外框再拿掉。它已經是 `expanded=True`,
            # 所以外框**不曾**藏住任何東西 —— 唯一的效果是把正上方那個 `##` 區塊
            # 標題換句話再印一次,外加一個誤點就把算好的結論收起來的把手。
            # (user 原則:不要闔上的資料 + 重複的移除。)不改用 container 包:
            # 上面的 `##` 標題 + caption 已經是這一段的框,再加一層邊框只是換個殼。
            # v19.429 §1 區塊隔離（見 _safe_section）
            _safe_section("📋 即時訊號 + 決策矩陣",
                          _render_realtime_decision_dashboard, ind)

            # ── AI 結構化總經摘要 ── L3 only

            # ══════════════════════════════════════════════════════════
            # v19.134 — 🤖 AI 景氣判斷總結 桶(物理重排,連續區塊)
            # ══════════════════════════════════════════════════════════
            st.divider()
            # v19.261 P3-A2:🤖 AI 景氣判斷整 section 抽 ui/tab1_macro_ai.py
            from ui.tab1_macro_ai import render_ai_summary_section  # noqa: PLC0415
            _ai_mac_pct, _ = _calc_data_health(ind)
            _safe_section("🤖 AI 景氣判斷總結", render_ai_summary_section,
                          ind, phase, GEMINI_KEY,
                          show_l3=_show_l3, mac_pct=_ai_mac_pct)
    elif FRED_KEY:
        st.info("👆 點擊「載入總經資料」開始分析")
    # 無金鑰 → **這裡不印任何東西**。
    # 原句「👆 點擊『載入總經資料』開始分析」指向一顆這條路徑上根本不存在的按鈕
    # (載入列整塊在本檔上方的 `if not FRED_KEY:` 分支裡不渲染) —— 線框 §04① 要的是
    # 把那句「指錯對象的話」換掉。上方那個分支已經印過「尚未設定 FRED 金鑰…(去哪裡補)」,
    # 且它與本 if 是**平行**的兩個 `if`(同縮排,都會執行) → 這裡再印一次會是**同一句灰字
    # 印兩遍**,把它變成雜訊。2026-08-28 稽核抓到,就地移除,不另造第二句。
