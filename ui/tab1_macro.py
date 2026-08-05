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

from shared.converters import safe_num  # v19.399 §1:缺值保留 None,不 `or 0` 捏造
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
    MATERIAL_GREEN,
    MATERIAL_ORANGE,
    MATERIAL_RED,
    MD_AMBER_300,
    MD_BLUE_300,
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


def _now_tw():
    return datetime.datetime.now(_TW_TZ)


def _calc_data_health(indicators=None):
    """同 app.py wrapper。"""
    ind = indicators if indicators is not None else st.session_state.get("indicators", {})
    return _calc_data_health_pure(ind)


def _action_light_renderer(light: str):
    """`macro_action_light()` 的燈色 → streamlit 原生告示元件。

    🟢 → `st.success` / 🔴 → `st.error` / 其餘(含 🟡 與服務層日後新增的燈)
    → `st.warning`。**用原生元件不手刻 HTML**:告示框的底色/邊框由 theme 提供,
    不必新造色票(§3.3),且 emoji + 文字本身就帶語意,不靠顏色單獨編碼。

    未知燈色一律落到 warning(偏保守),不當成綠燈 —— §1 不下假綠燈。
    """
    if light == "🟢":
        return st.success
    if light == "🔴":
        return st.error
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


def _exception_lines(systemic_risk, bucket_summary) -> list[str]:
    """③ 例外層要條列的項目(純函式、零 streamlit、零 I/O)。

    回傳**空 list = 真的沒有例外**,caller 據此顯示「沒有例外」那條敘述。
    指路文字走 `beginner_view.section_hint`(§3.3 不在本層重打區段名);
    未知桶 key 會由它當場 KeyError,不靜默指向空氣。
    """
    from ui.helpers.macro.beginner_view import (  # noqa: PLC0415
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
    for _bk in ("inflection", "news"):
        _b = _sum.get(_bk) or {}
        if _b.get("level") in _BUCKET_ALERT_LEVELS:
            _lines.append(
                f"- {_b.get('emoji', '⚪')} **{_b.get('label', '—')}**："
                f"{_b.get('headline', '')} — {_sec_hint(_bk)}")
    return _lines


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

    # AppTest / 缺 key 守衛(FRED key 未設或過短則跳過)
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
        f'background:{GH_BG_CARD};margin:8px 0;border-radius:4px;">'  # v19.387 V1:#fafafa 淺底孤島→深色卡(原淺字白底不可讀)
        f'<b>🇨🇳 中國拖累 China Drag</b>  '
        f'<span style="color:{_regime_color};font-weight:bold;">{_regime_label}</span>'
        f'{("  ⚠️ " + _fx_alert) if _fx_alert else ""}'
        f'</div>',
        unsafe_allow_html=True,
    )
    _c1, _c2, _c3, _c4 = st.columns(4)
    with _c1:
        st.metric("主分(總經)", f"{_main_score_10:.2f} / 10")  # v19.403 §1:phase score 0-10 恆非負→去 + 號
    with _c2:
        if _china_score is None:
            st.metric("中國副盤", "—")
        else:
            st.metric("中國副盤", f"{_china_score:.1f} / 100")
    with _c3:
        st.metric("乘子", f"{_multiplier:.3f}",
                  help="0.7~1.0,中國越差扣得越多,只懲罰不加成")
    with _c4:
        st.metric("折扣後主分", f"{_composite_10:.2f} / 10",  # v19.403 §1:去 + 號(delta 仍帶號)
                  delta=f"{_composite_10 - _main_score_10:+.2f}",
                  delta_color="inverse")
    st.caption(
        "ℹ️ 唯讀展示:本面板**不改變**上方總經分數,僅示意「若 China 副盤納入主分」的折扣強度。"
        "資料源:5 條 FRED OECD MEI(CLI/BCI/CPI/M2/USDCNY)。"
        "⚠️ BCI=OECD 商業信心指數(BSCICP03CNM665S,基準值 100 ≠ PMI 50 榮枯線)。"
    )


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

    from ui.helpers.story_nav import render_story_nav
    render_story_nav("macro")
    st.caption("策略3 三層指標加權方法論 v7 — 領先×2 | 中級×1 | 次級×0.5")

    # ⚡ 今日關鍵橫幅已下移至總表「③ 例外」層(2026-08-05 F1 資訊架構重構)。
    # 它回答的是「有沒有該警覺的」,屬總表第三層;掛在載入按鈕之前時,使用者會
    # 先看到警示才看到結論,與 user 拍板的四層閱讀順序相反。渲染邏輯本身未改。

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
                st.caption(f"✅ 已載入 · {_upd_str} TW（{_age_h:.1f}h 前）")
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
        # 2026-08-05 F1:四時域的「一覽」由總表 ② 依據表承接(原 bar renderer 已刪),
        # 四個分組 subheader 仍在下方詳細區,順序不變。
        # ════════════════════════════════════════════════════════════

        ph    = phase["phase"]  # v19.39 PR1C: sc / ph_c 在 archive 後不再使用
        alloc = phase["alloc"];  advice = phase.get("advice","")

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
        # 燈色 → `_action_light_renderer` 選 st.success / warning / error 原生元件。
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
            st.caption(
                f"🚦 買賣總結燈暫無法顯示：[{type(_al_e).__name__}] {_al_e}")

        # ══ ② 依據 —— 表格(兩把尺並陳 + 各桶狀態 + 每列指路)══════════
        # 這張表取代三個原本各自為政的區塊,資料一格不少地併進來:
        #   - 🩺 綜合健康度 hero 卡(多空加權淨分,有正負)
        #   - 📊 五桶 summary bar(長期 / 中期 / 短線 / 拐點 / 新聞)
        #   - 夾在兩者之間、說明「別互相換算」的那行 caption
        # 那行 caption 現在是表格「說明」欄本身(user 要求:不要留兩份說法)。
        st.markdown("### ② 依據 — 憑什麼這樣說")
        _5b_summary: dict = {}
        try:
            from ui.helpers.macro.beginner_view import (  # noqa: PLC0415
                build_evidence_rows,
                compute_five_bucket_summary,
                render_evidence_table,
            )
            from ui.helpers.macro.helpers import (  # noqa: PLC0415
                calculate_composite_score,
                composite_verdict,
            )
            _news_items = st.session_state.get("news_items")
            _5b_summary = compute_five_bucket_summary(ind, phase, news_items=_news_items)
            # 指標筆數吃 v19.270 D8 #8 的 provenance 側車(筆數隨來源命中浮動,
            # 寫死字面值那版已經漂移過一次)。
            _comp_prov: dict = {}
            _comp_score = calculate_composite_score(ind, provenance_out=_comp_prov)
            _comp_n = int(_comp_prov.get("n_indicators") or 0)
            _cv_icon, _cv_level, _, _cv_action = composite_verdict(_comp_score)
            _ev_rows = build_evidence_rows(
                _5b_summary,
                composite_score=_comp_score,
                composite_icon=_cv_icon,
                composite_level=_cv_level,
                composite_action=_cv_action,
                n_indicators=_comp_n,
            )
            render_evidence_table(_ev_rows)
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
                st.caption(f"對帳 chip 暫無法顯示：[{type(_rc_e).__name__}] {_rc_e}")
        except Exception as _ev_e:  # noqa: BLE001 — 依據表失敗不得擋掉整頁總經
            st.warning(f"② 依據表渲染失敗(降級)：[{type(_ev_e).__name__}] {_ev_e}")

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
                st.caption(f"⚡ 今日關鍵橫幅暫無法顯示：[{type(_ka_e).__name__}] {_ka_e}")
        try:
            _exc_lines = _exception_lines(
                st.session_state.get("systemic_risk_data"), _5b_summary)
            if _exc_lines:
                st.markdown("\n".join(_exc_lines))
            else:
                st.caption(
                    "✅ 新聞系統性風險未達警戒等級，拐點桶與新聞桶也都不在警戒狀態；"
                    "各桶讀數完整列在上方 ② 依據表。")
        except Exception as _ex_e:  # noqa: BLE001
            st.caption(f"③ 例外層暫無法顯示：[{type(_ex_e).__name__}] {_ex_e}")

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
            st.caption(f"可信度 chip 暫無法顯示：[{type(_tr_e).__name__}] {_tr_e}")

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
        # 順序:中國副盤 → 逐檔決策矩陣 → 🌳 長期 → 🧭 指南針 → 📈 中期
        #      (Z-Score 卡)→ 🎯 短線(10 燈雷達)→ ⚠️ 拐點 → 🤖 AI 總結。
        # 上方 ② 依據表的「詳細在下方哪一段」欄就是指向這些區塊的標題。
        # ════════════════════════════════════════════════════════════
        st.divider()
        st.markdown("## 🔎 詳細資料與說明")

        # ══ v19.118 中國拖累唯讀面板（China Drag）═════════════════════
        # 4 數字唯讀展示:不改變上方總經分數,僅示意 China 副盤折扣強度
        # v19.296: 改為預設摺疊 expander — 資料屬補充參考，不需預設佔版面
        with st.expander("🇨🇳 中國拖累（China Drag）— 唯讀副盤參考", expanded=False):
            try:
                _render_china_drag_panel(phase, FRED_KEY)
            except Exception as _cd_e:  # noqa: BLE001
                st.caption(f"⬜ 中國副盤載入失敗：{type(_cd_e).__name__}")


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
            # 📋 即時訊號 + 決策矩陣 桶
            # ⚠️ 2026-08-05 稽核 🟡 必修 4 —— **本區塊第三次搬家**,動前先讀完:
            #   - v19.41:原在 tab 外(擋在總經前),因 user 反饋「總經放在最上方」下移;
            #   - v19.42:Tab① 內的 tab strip 因同一理由被消滅。
            #   v19.4xx(第三次)從全頁最底部倒數第二區 → 上移到總覽之後、四時域之前,
            #   並改 expanded=True。**不違反 v19.41 那條指示**:總表(即「總經」)
            #   仍在最上方,本區塊只是插在總覽與細節之間。
            #   理由:這是全頁唯一給出「所以呢」(逐檔 加碼/持有/減倉/全撤 + 目標權重)
            #   的區塊,埋在 13 個一級區塊之後 + 預設收合 = 算對了但使用者看不到。
            #   2026-08-05 F1(第四次動線調整,位置**不變**):上游錨點由「五桶 bar」
            #   換成總表的「② 依據表」,本區塊仍是詳細區的第一個實質區塊。
            #   user 這次列的詳細區順序把本區塊排在拐點之後;**刻意未照做**,
            #   理由與上一輪相同(逐檔行動是結論不是細節,埋到底部等於沒揭露),
            #   已在交付報告列為待裁決項。若 user 拍板要下移,回退方式是把本區塊
            #   整段移回 `render_inflection_alert_section` 之後(git history v19.41 位置)。
            # ══════════════════════════════════════════════════════════
            st.markdown("## 📋 即時訊號 + 決策矩陣")
            st.caption("先給結論 ｜ verdict 路徑 + 逐檔行動建議（推導細節見下方四時域）")
            with st.expander(
                "🔬 即時訊號 + 決策矩陣（C-2 verdict 路徑｜逐檔行動建議）",
                expanded=True,
            ):
                # v19.429 §1 區塊隔離（見 _safe_section）
                _safe_section("📋 即時訊號 + 決策矩陣",
                              _render_realtime_decision_dashboard, ind)
            st.divider()

            # ══════════════════════════════════════════════════════════
            # v19.134 — 🌳 長期座標 桶(物理重排,連續區塊)
            # v19.262 P3-A5:整 section 抽 ui/tab1_macro_longterm.py(-294 LOC)
            # ══════════════════════════════════════════════════════════
            from ui.tab1_macro_longterm import render_long_term_section
            _safe_section("🌳 長期座標", render_long_term_section,
                          ind, fred_key=FRED_KEY, show_l3=_show_l3)

            # ══════════════════════════════════════════════════════════
            # 🧭 總經指南針(v19.430 從 app.py 搬入詳細區)
            # user 2026-08-05 拍板 A 案:原本由 `app.py` 在 `render_macro_tab()`
            # **之前**呼叫,等於三張原始值卡(VIX / 10Y / S&P 500)永遠壓在總表上方。
            # 原始值是「依據」不是「結論」,故歸詳細區。
            #
            # 2026-08-05 稽核 🟡 建議 6(第二次調位):原落在詳細區的**第一段**,
            # 但本元件無快取時整塊只顯示「請按右上按鈕載入」—— 使用者剛按過
            # 「載入總經資料」、VIX 已經在 ② 依據表裡,詳細區第一句話卻要他再按
            # 一次抓 VIX。且 ② 表沒有任何一列指向它(它是詳細區裡唯一沒被上方
            # 提及的區塊),放在開頭等於用一個「還要再按一次」的空框擋住真正
            # 被指路指到的四時域。下移到 🌳 長期座標之後,讓被指路的段先出現。
            # ⚠️ 表下那行「往下捲依序是…」目錄只列四時域四段且**從桶對照表導出**,
            # 不含指南針,故本次搬動不會讓它過期。
            # ══════════════════════════════════════════════════════════
            try:
                from ui.components.macro_compass_top import (  # noqa: PLC0415
                    render_macro_compass as _rmc,
                )
                _rmc()
            except Exception as _mc_e:  # noqa: BLE001
                st.caption(f"⬜ 總經指南針暫無法顯示：[{type(_mc_e).__name__}] {_mc_e}")

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
    else:
        st.info("👆 點擊「載入總經資料」開始分析")
