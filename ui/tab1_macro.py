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

from fund_fetcher import (
    fetch_market_news,
    set_risk_free_rate,
)
from services.ai_service import (
    event_impact_analysis,
)
from services.macro_service import (
    backtest_turning_points,
    calc_macro_phase,
    calc_sub_cycle_lights,
    detect_systemic_risk,
    detect_turning_points,
    fetch_all_indicators,
    rank_macro_drivers,
)
from ui.components.mk_clock import render_mk_clock_section
from ui.helpers.macro_helpers import (
    _CATEGORY_MAP,
    category_history,
    category_score,
    category_verdict,
)
from ui.helpers.session import (
    calc_data_health as _calc_data_health_pure,
    friendly_error as _friendly_error,
)

_TW_TZ = ZoneInfo("Asia/Taipei")


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


# v19.14：雙軌 banner 標籤（與 ui.tab_crisis_backtest.MULTIFACTOR_MODE_LABELS 對齊；
# 此處硬編避免循環依賴 — tab_crisis_backtest 也 import 自 services 層）
_PENDING_MODE_LABELS = {
    "macro": "🏔️ 總經長期",
    "pullback": "⚡ 短期回檔",
}


def _render_one_pending_banner(mode: str, payload: dict) -> None:
    """v19.14：單一 mode 的待審 banner + ✅/❌ 按鈕（避免 widget key collision）."""
    from services.macro_weights_store import approve_pending, reject_pending

    label = _PENDING_MODE_LABELS.get(mode, mode)
    _meta = payload.get("oos_metrics") or {}
    _calibrated_at = payload.get("calibrated_at", "—")
    _method = payload.get("calibration_method", "—")
    _n_ind = len(payload.get("indicators") or {})
    _oos_f1 = _meta.get("oos_f1", 0.0)
    _oos_sharpe = _meta.get("oos_sharpe", 0.0)
    _n_folds = _meta.get("n_folds", 0)
    _ai_text = payload.get("ai_explanation") or "_（無 AI 解讀）_"

    st.markdown(
        f"<div style='background:#3a2700;border:2px solid #ff9800;"
        f"border-radius:10px;padding:14px 18px;margin:0 0 14px'>"
        f"<div style='color:#ff9800;font-weight:700;font-size:16px;margin-bottom:6px'>"
        f"⚠️ {label} 有 1 筆新權重待審核</div>"
        f"<div style='color:#e6edf3;font-size:13px;line-height:1.6'>"
        f"來源：<code>{_method}</code>　|　提交時間：<code>{_calibrated_at}</code>　|　"
        f"涵蓋 <b>{_n_ind}</b> 個指標<br>"
        f"OOS F1 = <code>{_oos_f1:.3f}</code>　|　"
        f"OOS Sharpe = <code>{_oos_sharpe:.3f}</code>　|　"
        f"折數 = <code>{_n_folds}</code>"
        f"</div></div>",
        unsafe_allow_html=True,
    )

    with st.expander(f"🤖 看 {label} AI 解讀", expanded=False):
        st.markdown(_ai_text)

    col_a, col_b, _ = st.columns([1, 1, 4])
    if col_a.button(
        f"✅ 批准 {label}（升格為 active）",
        type="primary",
        key=f"_pending_approve_btn_{mode}",
        use_container_width=True,
    ):
        if approve_pending(mode=mode):
            st.success(
                f"✅ {label} 已升格為 active — 重整套用（C-2 後面板會載入新權重）"
            )
            st.rerun()
        else:
            st.error("❌ 升格失敗（可能 pending 已被刪除或 corrupt）")
    if col_b.button(
        f"❌ 拒絕 {label}（刪除待審）",
        type="secondary",
        key=f"_pending_reject_btn_{mode}",
        use_container_width=True,
    ):
        if reject_pending(mode=mode):
            st.warning(f"🗑️ 已拒絕 {label}，該 mode pending 檔已刪除")
            st.rerun()


def _render_pending_weights_banner() -> None:
    """📌 Route C-1：偵測待審權重，存在則顯示審核 banner.

    v19.14：mode-aware — 逐 mode 檢查 ``has_pending(mode=mode)``，每個有 pending 的
    mode 各自獨立渲染 1 條橘色 banner + 1 對 ✅/❌ 按鈕（widget key 帶 mode 後綴）。
    兩 mode 都無 pending → 完全不渲染（無噪音）。
    """
    try:
        from services.macro_weights_store import (
            PENDING_MODES,
            has_pending,
            load_pending,
        )
    except ImportError:
        return  # Route C 未部署時靜默退場

    for mode in PENDING_MODES:
        if not has_pending(mode=mode):
            continue
        payload = load_pending(mode=mode)
        if not payload:
            continue
        _render_one_pending_banner(mode, payload)


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


def _render_beginner_dashboard(indicators: dict | None, fred_api_key: str = "") -> None:
    """✨ v19.17：新手友善總經面板 — 接在 pending banner 後、v19.15 進階區之前。

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
              <div style="font-size: 14px; color: #888; margin-bottom: 4px;">
                ✨ 目前總經位階（綜合 {_n_total} 項指標 score × 權重）
              </div>
              <div style="font-size: 30px; font-weight: 700; color: {_color}; line-height: 1.2;">
                {_icon} {_level}
                <span style="font-size: 20px; color: #aaa; margin-left: 14px;">score = {_score:+.2f}</span>
              </div>
              <div style="font-size: 15px; color: #ccc; margin-top: 8px;">
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
                  <div style="font-size: 13px; color: #888; margin-bottom: 4px;">
                    🐌 慢總經位階（{_n_total} 項指標 × 權重 ｜ 月～季級）
                  </div>
                  <div style="font-size: 26px; font-weight: 700; color: {_color}; line-height: 1.2;">
                    {_icon} {_level}
                    <span style="font-size: 17px; color: #aaa; margin-left: 12px;">score = {_score:+.2f}</span>
                  </div>
                  <div style="font-size: 13px; color: #aaa; margin-top: 6px;">
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
                  <div style="font-size: 13px; color: #888; margin-bottom: 4px;">
                    ⚡ 短線雷達（10 燈 1-day 動量／情緒 ｜ 日級）
                  </div>
                  <div style="font-size: 26px; font-weight: 700; color: {_r_color}; line-height: 1.2;">
                    {_r_icon} {_r_level}
                  </div>
                  <div style="font-size: 13px; color: #aaa; margin-top: 6px;">
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
              <div style="font-size: 13px; color: #888; margin-bottom: 4px;">
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

    # v19.40 ARCHIVED PR2:
    # ════════════════════════════════════════════════
    # 區塊 2：🎯 為什麼是這位階？（top 3 driver 教學）
    # 區塊 3：📚 本期使用 N 個關鍵指標（inline 教學 expanders）
    # archived 原因：搬遷至 📖 說明書 Tab §11 宏觀教學文獻
    # ※ _render_beginner_dashboard() 已在 PR1B v19.38 停用（L853 已 comment out）
    # 完整原始程式碼見 git log @ 13026cc 之前（L408-L472 ~65 行）


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
        from services.macro_tw_local_fetch import (
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
                f"<div style='font-size:12px;color:#8b949e'>🏔️ 長期 12M ｜ 景氣大循環</div>"
                f"<div style='font-size:22px;font-weight:700;color:{long_v['color']}'>"
                f"{long_v['regime']}</div>"
                f"<div style='font-size:13px;color:#c9d1d9;margin-top:4px'>"
                f"得分：<b>{long_v['score']:+.2f}</b> ｜ 建議持股：<b>{long_v['suggest_pct']}</b></div>"
                f"<div style='font-size:12px;color:#8b949e;margin-top:6px'>{long_v['detail']}</div>"
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
                f"<div style='font-size:12px;color:#8b949e'>⚡ 短期 1Q ｜ 財報季偏向</div>"
                f"<div style='font-size:22px;font-weight:700;color:{short_v['color']}'>"
                f"{short_v['regime']}</div>"
                f"<div style='font-size:13px;color:#c9d1d9;margin-top:4px'>"
                f"得分：<b>{short_v['score']:+.2f}</b> ｜ 建議行動：<b>{short_v.get('action','—')}</b></div>"
                f"<div style='font-size:12px;color:#8b949e;margin-top:6px'>{short_v['detail']}</div>"
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
    """🎯 v19.15：即時訊號燈 + 決策矩陣 — 接在 pending banner 後、tabs 前。

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
        f"<div style='font-size:13px;color:#aaa;margin-bottom:4px'>📌 當前總經 verdict</div>"
        f"<div style='font-size:24px;color:{color};font-weight:700;margin-bottom:6px'>"
        f"{icon} {level}　<span style='font-size:18px;color:#e6edf3'>score = {score:+.2f}</span></div>"
        f"<div style='font-size:14px;color:#e6edf3;line-height:1.55'>{action_text}</div>"
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
        fg = _ACTION_BADGE_FG.get(action, "#e6edf3")
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

    # ── 📌 Route C-1：待審權重 banner（從危機回測室提交過來的）───
    _render_pending_weights_banner()

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

        _btn_label = "🔄 更新總經資料" if st.session_state.macro_done else "📡 載入總經資料"
        if st.button(_btn_label, type="primary", key="btn_macro_load"):
            with st.spinner("📡 從 FRED / Yahoo Finance 抓取最新指標..."):
                _t0_macro = _time_mod.time()
                # v18.223：包 try/except + 空結果偵測 — 原本無錯誤處理，抓取失敗會
                # 無聲消失（spinner 沒了、沒資料、沒錯誤）。改成失敗顯示明確原因。
                try:
                    ind = fetch_all_indicators(FRED_KEY)
                except Exception as _me:
                    ind = {}
                    _friendly_error(
                        "總經指標載入失敗", _me,
                        hint="多半是 NAS proxy 連線異常或來源暫時無回應；"
                             "可按側欄「🔍 測試 Proxy 連線」確認，或稍後重試。",
                        level="error")
                _macro_ms = round((_time_mod.time() - _t0_macro) * 1000)
                if not ind:
                    st.error(
                        f"❌ 沒有抓到任何總經指標（0 個，耗時 {_macro_ms}ms）。"
                        "多半是 NAS proxy 不通／逾時或來源被擋——"
                        "請按側欄「🔍 測試 Proxy 連線」確認後再重試。")
                else:
                    phase = calc_macro_phase(ind)
                    old_phase = (st.session_state.phase_info.get("phase","")
                                 if st.session_state.phase_info else "")
                    new_phase = phase.get("phase","")
                    if old_phase and old_phase != new_phase:
                        st.session_state.phase_history.append(
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
                    # v18.228：流動性引擎改按鈕觸發（見下方 expander），不再塞進
                    # 總經主載入路徑 — 3×yfinance 5y + DefiLlama + 3×FRED 序列抓取
                    # 最壞會疊上 ~2 分鐘阻塞，害總經卡在「RUNNING…」。
                    # ── 記錄 API 延遲（供 Tab5 延遲趨勢圖）──
                    _lat_log = st.session_state.get("api_latency_log", [])
                    _lat_log.append({
                        "label":    _now_tw().strftime("%H:%M"),
                        "macro_ms": _macro_ms,
                        "moneydj_ms": None,
                        "yf_ms":      None,
                    })
                    st.session_state["api_latency_log"] = _lat_log[-24:]
                    st.success(f"✅ 已抓取 {len(ind)} 個指標！（{_now_tw().strftime('%H:%M')} TW｜{_macro_ms}ms）")
            with st.spinner("📰 抓取市場新聞 + 系統性風險掃描..."):
                try:
                    _news = fetch_market_news(max_per_feed=5)
                    st.session_state.news_items = _news
                    _srd = detect_systemic_risk(_news)
                    st.session_state.systemic_risk_data = _srd
                    _rl = _srd.get("risk_level","LOW")
                    _rs = _srd.get("risk_score",0)
                    st.info(f"📰 已掃描 {len(_news)} 則新聞｜系統性風險：{_srd.get('risk_icon','⬜')} {_rl}（評分 {_rs}）")
                except Exception as _ne:
                    st.session_state.news_items = []
                    st.session_state.systemic_risk_data = None
                    # v16.0 異常遮罩：用 _friendly_error 收進可展開的技術細節，不嚇到新手
                    _friendly_error(
                        "新聞掃描暫時失敗",
                        _ne,
                        hint="不影響總經指標分析，可稍後重試；本次僅以指標面綜合判讀。",
                        level="info",
                    )

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
        phase = st.session_state.phase_info
        ph    = phase["phase"]  # v19.39 PR1C: sc / ph_c 在 archive 後不再使用
        alloc = phase["alloc"];  advice = phase.get("advice","")
        rec_p = phase.get("rec_prob")

        # v19.38 ARCHIVED: ✨ 新手友善面板（雙速合議）— 矛盾主因（月度合議 vs 日級雷達混在同卡）
        # v19.38 ARCHIVED: 📊 台股本地視角（12M/1Q）— 與下方「💵 台股熱錢監測」重複且 12M 視窗無關熊市驗證
        # 復活：恢復下兩行 import + sub-function 即可（_render_beginner_dashboard / _render_tw_local_dashboard 完整保留）
        # _render_beginner_dashboard(ind, FRED_KEY)
        # _render_tw_local_dashboard(ind, FRED_KEY)

        # ── ③ 🔬 即時訊號決策矩陣（v19.15 verdict + 逐檔行動建議） ──
        with st.expander(
            "③ 🔬 即時訊號 + 決策矩陣（C-2 verdict 路徑｜逐檔行動建議）",
            expanded=False,
        ):
            _render_realtime_decision_dashboard(ind)

        # ══ v17.3 內層 Tab：戰情首頁（§6-6 資訊不藏匿）═══
        # v19.40 PR2: 📖 指標教學手冊 已搬至 📖 說明書 Tab §11 宏觀教學文獻
        (tab_main,) = st.tabs(["📊 戰情首頁（完整 23 指標）"])

        # v19.40 ARCHIVED PR2 (PR #TBD):
        # with tab_edu: 📖 指標教學手冊（build_cards_from_indicators / MACRO_EDU）
        # archived 原因：搬遷至 📖 說明書 Tab §11 宏觀教學文獻
        # 完整原始程式碼見 git log @ 13026cc 之前（L866-L922 ~57 行）
        with tab_main:
            # v19.18: 原 ① verdict 大卡已移除（與頂部新手面板 + 進階檢視 expander 重複）
            # v19.38 ARCHIVED PR1B (PR #245)：
            # ① 7 維獨立合議 + 23 指標健康度 — 與 ② 拐點偵測重複（共用 23 FRED 因子）
            # 🚦 景氣細項燈號（7 子領域 Z-Score 健康度）— 與 ① 7 維獨立合議 100% 重複
            # 🗂️ 四大類別景氣健康度（含 24M 歷史趨勢）— 純加權分類無新訊號
            # ③ 今日市場結論 Hero 卡 — 重複 ① 戰情室三儀表 + ② 拐點偵測之綜合判讀
            # 完整原始程式碼見 git log @ 91da530 之前（L928-L1229）
            st.caption("ℹ️ 戰情首頁：① 戰情室 → ② 拐點偵測 → ④ 短線雷達 → ⑤ 流動性 → ⑥ 台股熱錢。"
                       "完整指標教學請切到右側「📖 指標教學手冊」分頁。")


            # ══ L3 60/40 雙欄佈局（戰情室 × Z-Score 矩陣）══════════════
            if _show_l3:
                _col_l3, _col_r3 = st.columns([3, 2])
                _main_ctx = _col_l3
            else:
                import contextlib as _ctxlib
                _main_ctx = _ctxlib.nullcontext()

            with _main_ctx:
                # ══════════════════════════════════════════════════
                # V5 全域導航塔（War Room）── 三圓形氣象儀表
                # ══════════════════════════════════════════════════
                st.markdown("### ① 🎯 全域導航塔（戰情室三儀表：薩姆 + SLOOS + 廣度）")
                _sahm_d  = ind.get("SAHM")  or {}
                _sloos_d = ind.get("SLOOS") or {}
                _adl_d   = ind.get("ADL")   or {}
                _sahm_v  = float(_sahm_d.get("value")  or 0)
                _sloos_v = float(_sloos_d.get("value") or 0)
                _adl_v   = float(_adl_d.get("value")   or 0)

                _gg1, _gg2, _gg3 = st.columns(3)

                def _make_gauge(val, title, suffix, rng, thresholds, danger_above=True):
                    """thresholds: [(limit, color_hex), ...] 從低到高"""
                    steps = []
                    prev = rng[0]
                    for lim, col in thresholds:
                        steps.append({"range": [prev, lim], "color": col})
                        prev = lim
                    steps.append({"range": [prev, rng[1]], "color": thresholds[-1][1]})
                    # 指針顏色：超過最後閾值的 limit 為警報色
                    danger_lim = thresholds[-1][0]
                    needle_c = ("#f44336" if (danger_above and val >= danger_lim)
                                else ("#00c853" if (not danger_above and val <= danger_lim)
                                else "#ff9800"))
                    f = go.Figure(go.Indicator(
                        mode="gauge+number",
                        value=val,
                        title={"text": title, "font": {"size": 13, "color": "#aaa"}},
                        number={"suffix": suffix, "font": {"size": 22, "color": "#e6edf3"},
                                "valueformat": ".2f"},
                        gauge={"axis": {"range": rng, "tickcolor": "#444",
                                        "tickfont": {"size": 9, "color": "#666"}},
                               "bar":  {"color": needle_c, "thickness": 0.25},
                               "bgcolor": "#161b22",
                               "bordercolor": "#30363d",
                               "steps": steps,
                               "threshold": {"line": {"color": "#f44336", "width": 3},
                                             "thickness": 0.8, "value": danger_lim}}))
                    f.update_layout(paper_bgcolor="#0e1117", font_color="#e6edf3",
                                    height=200, margin=dict(t=40, b=5, l=15, r=15))
                    return f

                with _gg1:
                    st.plotly_chart(_make_gauge(
                        _sahm_v, "薩姆規則<br>衰退機率", "pp", [0, 1.0],
                        [(0.3, "#0a2a0a"), (0.5, "#2a1f00"), (1.0, "#2a0a0a")],
                        danger_above=True), use_container_width=True)
                    _sahm_sig = ("🔴 **衰退觸發** ≥0.5" if _sahm_v >= 0.5
                                 else "🟡 警戒區 ≥0.3" if _sahm_v >= 0.3
                                 else "🟢 安全 <0.3")
                    st.markdown(f"<div style='text-align:center;font-size:12px'>{_sahm_sig}</div>",
                                unsafe_allow_html=True)
                    if not _sahm_d:
                        st.caption("⚠️ FRED SAHMREALTIME 未取得（API Key 或網路）")
                    # T2: Tooltip
                    with st.expander("ℹ️ 薩姆規則說明", expanded=False):
                        st.markdown("**薩姆規則（Sahm Rule）**：當失業率的3個月滾動平均比過去12個月最低點高出 ≥0.5 百分點，代表美國進入衰退。⚠️ 新手白話：儀表板紅色時，代表景氣已經轉壞，建議降低高風險基金比重。")

                with _gg2:
                    st.plotly_chart(_make_gauge(
                        _sloos_v, "SLOOS 放貸寬鬆度<br>銀行信貸標準", "%", [-30, 60],
                        [(-5, "#0a2a0a"), (20, "#2a1f00"), (60, "#2a0a0a")],
                        danger_above=True), use_container_width=True)
                    _sloos_sig = ("🔴 **銀行緊縮** >20%" if _sloos_v > 20
                                  else "🟡 中性偏緊 >0%" if _sloos_v > 0
                                  else "🟢 信貸寬鬆 <0%")
                    st.markdown(f"<div style='text-align:center;font-size:12px'>{_sloos_sig}</div>",
                                unsafe_allow_html=True)
                    if not _sloos_d:
                        st.caption("⚠️ FRED DRTSCILM 未取得")
                    # T2: Tooltip
                    with st.expander("ℹ️ SLOOS 說明", expanded=False):
                        st.markdown("**SLOOS（銀行放貸標準）**：美聯儲季度調查，正值=銀行收緊放貸（壞），負值=銀行放寬放貸（好）。⚠️ 新手白話：儀表板紅色時，代表銀行不願貸款，企業融資困難，景氣降溫訊號。")

                with _gg3:
                    # ADL = RSP/SPY 市場寬度 (% MoM change, negative = narrowing breadth = bad)
                    st.plotly_chart(_make_gauge(
                        _adl_v, "市場健康度<br>RSP/SPY 廣度", "%", [-10, 10],
                        [(-5, "#2a0a0a"), (0, "#2a1f00"), (5, "#0a2a0a")],
                        danger_above=False), use_container_width=True)
                    _adl_sig = ("🟢 市場廣度健康" if _adl_v > 2
                                else "🔴 **廣度收窄** 虛假繁榮" if _adl_v < -2
                                else "🟡 市場廣度持平")
                    st.markdown(f"<div style='text-align:center;font-size:12px'>{_adl_sig}</div>",
                                unsafe_allow_html=True)
                    # T2: Tooltip
                    with st.expander("ℹ️ 市場廣度說明", expanded=False):
                        st.markdown("**RSP/SPY 廣度（市場廣度）**：RSP = 等權重標普500，SPY = 市值加權。RSP/SPY 比值上升 = 中小型股參與行情（健康），下降 = 只有大型股撐盤（虛胖）。⚠️ 新手白話：紅色時代表漲幅集中少數大股，市場不穩健，小心追高。")

                # ── 持倉紅綠燈列表（War Room Middle）──────────────────────────
                _pf_all = st.session_state.get("portfolio_funds", [])
                _pf_loaded = [f for f in _pf_all if f.get("loaded")]
                if _pf_loaded:
                    st.markdown("#### 🚦 持倉紅綠燈")
                    _tl_html = ""
                    for _pf in _pf_loaded:
                        _pf_code  = _pf.get("code","?")
                        _pf_name  = _pf.get("fund_name") or _pf_code
                        _pf_m     = _pf.get("metrics") or _pf.get("m") or {}
                        _pf_divs  = _pf.get("dividends") or []
                        _pf_nav   = float(_pf_m.get("nav") or 0)
                        _pf_b1    = float(_pf_m.get("buy1") or 0)   # v18.6: 年高-1σ（小跌）
                        _pf_b2    = float(_pf_m.get("buy2") or 0)   # 年高-2σ（急跌）
                        _pf_b3    = float(_pf_m.get("buy3") or 0)   # 年高-3σ（大跌）
                        _pf_s1    = float(_pf_m.get("sell1") or 0)  # 年低+1σ
                        _pf_bbd   = float(_pf_m.get("bb_lower") or 0)
                        _pf_bbu   = float(_pf_m.get("bb_upper") or 0)
                        _pf_ret1y = float(_pf_m.get("ret_1y") or 0)
                        _pf_adr   = float(_pf_m.get("annual_div_rate") or 0)
                        _pf_core  = "🛡️ 核" if _pf.get("is_core") else "⚡ 衛"
                        # 燈號判定（v18.6: σ + 布林雙確認 升級）
                        _tl_icon, _tl_bg, _tl_bc, _tl_reason = "🟢", "#061a06", "#00c853", "淨值穩定，含息報酬正常"
                        # 雙確認買 = σ 買點觸發 + 布林下軌觸碰
                        _double_buy = (_pf_b1 > 0 and _pf_nav > 0 and _pf_nav <= _pf_b1
                                       and _pf_bbd > 0 and _pf_nav <= _pf_bbd)
                        _double_sell = (_pf_s1 > 0 and _pf_nav > 0 and _pf_nav >= _pf_s1
                                        and _pf_bbu > 0 and _pf_nav >= _pf_bbu)
                        if _pf_adr > 0 and _pf_ret1y < _pf_adr:
                            _tl_icon, _tl_bg, _tl_bc = "🔴", "#1a0606", "#f44336"
                            _tl_reason = f"吃本金警示：含息報酬 {_pf_ret1y:.1f}% < 配息率 {_pf_adr:.1f}%"
                        elif _double_buy:
                            _tl_icon, _tl_bg, _tl_bc = "🟢🟢", "#0a3a1a", "#00e676"
                            _tl_reason = f"σ+布林雙確認買 NAV {_pf_nav:.4f} ≤ 買1({_pf_b1:.4f}) & 布林下軌"
                        elif _double_sell:
                            _tl_icon, _tl_bg, _tl_bc = "🔔🔔", "#3a0a0a", "#f44336"
                            _tl_reason = f"σ+布林雙確認賣 NAV {_pf_nav:.4f} ≥ 賣1({_pf_s1:.4f}) & 布林上軌"
                        elif _pf_b3 > 0 and _pf_nav > 0 and _pf_nav <= _pf_b3:
                            _tl_icon, _tl_bg, _tl_bc = "🟡", "#1a0a2a", "#9c27b0"
                            _tl_reason = f"大跌大買訊號 NAV {_pf_nav:.4f} ≤ 買3({_pf_b3:.4f})"
                        elif _pf_b1 > 0 and _pf_nav > 0 and _pf_nav <= _pf_b1:
                            _tl_icon, _tl_bg, _tl_bc = "🟡", "#1a1500", "#ff9800"
                            _tl_reason = f"小跌小買訊號 NAV {_pf_nav:.4f} ≤ 買1({_pf_b1:.4f})"
                        elif not _pf_m:
                            _tl_icon, _tl_bg, _tl_bc = "⬜", "#161b22", "#555"
                            _tl_reason = "資料尚未載入"
                        _tl_html += (
                            f"<div style='background:{_tl_bg};border:1px solid {_tl_bc};"
                            f"border-radius:8px;padding:8px 14px;margin:4px 0;"
                            f"display:flex;align-items:center;gap:14px'>"
                            f"<span style='font-size:20px'>{_tl_icon}</span>"
                            f"<span style='color:#64b5f6;font-size:11px;width:32px'>{_pf_core}</span>"
                            f"<span style='color:#ccc;font-size:12px;flex:1'>"
                            f"<b>{_pf_name[:20]}</b></span>"
                            f"<span style='color:{_tl_bc};font-size:11px'>{_tl_reason}</span>"
                            f"</div>"
                        )
                    st.markdown(_tl_html, unsafe_allow_html=True)
                else:
                    st.markdown(
                        "<div style='background:#161b22;border:1px solid #30363d;border-radius:8px;"
                        "padding:10px 16px;color:#555;font-size:12px;text-align:center'>"
                        "🚦 持倉紅綠燈：請先至「📊 組合基金」Tab 新增並載入基金，即可在此顯示即時燈號</div>",
                        unsafe_allow_html=True)

                # ── AI 每日一句結論（v15.2 移除：使用者反饋過於簡略）──
                st.divider()

                # ══════════════════════════════════════════════════
                # L1 新手待辦清單（所有等級均顯示）
                # ══════════════════════════════════════════════════
                _w_icon2  = phase.get("weather_icon", "⛅")
                _w_label2 = phase.get("weather_label", "多雲")
                _l1_stock = alloc.get("股票", 50)
                _l1_bond  = alloc.get("債券", 30)
                _l1_cash  = alloc.get("現金", 20)
                _l1_checks = [
                    f"確認核心部位是否符合 AI 建議：股 {_l1_stock}% / 債 {_l1_bond}% / 現金 {_l1_cash}%",
                ]
                if _sahm_v >= 0.5:
                    _l1_checks.append(f"⚠️ **薩姆衰退警報已觸發**（{_sahm_v:.2f}pp）：暫停衛星加碼，保留防守型部位")
                if _sloos_v > 20:
                    _l1_checks.append(f"📊 **銀行緊縮偵測**（SLOOS {_sloos_v:.1f}%）：高收益債基金降至 10% 以下")
                if _adl_v < -2:
                    _l1_checks.append(f"🌍 **市場廣度警示**（RSP/SPY {_adl_v:.2f}%）：減少主題/集中型基金")
                _l1_checks.append("定期定額不停扣（除非景氣位階進入「高峰」且 VIX < 15）")
                _l1_checks.append(f"本週核心原則：景氣「{ph}」，{(advice or '均衡配置，嚴守紀律')[:40]}。")
                _l1_md = "\n".join(f"- [ ] {c}" for c in _l1_checks)
                st.markdown(
                    f"<div style='background:#0d1117;border:1px solid #30363d;border-radius:12px;"
                    f"padding:16px 20px;margin:8px 0'>"
                    f"<div style='color:#e6edf3;font-weight:700;margin-bottom:10px'>"
                    f"📋 本週操作清單（{_w_label2} {_w_icon2}）</div></div>",
                    unsafe_allow_html=True)
                st.markdown(_l1_md)

            # ══════════════════════════════════════════════════
            # L3 指標 Z-Score 矩陣（14 指標）— L3 only
            # ══════════════════════════════════════════════════
            if _show_l3:
                with _col_r3:
                    # v17.2：Z-Score 矩陣升級 — 燈號儀表 + 白話判讀 + |Z| DESC 排序
                    st.markdown("**🔬 Z-Score 矩陣（23 指標 ｜ 異常先看）**")
                    # 四色說明條（HTML，避免破壞 Streamlit theme）
                    st.markdown(
                        "<div style='display:flex;gap:6px;flex-wrap:wrap;margin:4px 0 8px'>"
                        "<span style='background:#0a3d1f;color:#69f0ae;padding:3px 10px;"
                        "border-radius:4px;font-size:12px'>🟢 正常 |Z|&lt;1</span>"
                        "<span style='background:#3d3408;color:#ffd54f;padding:3px 10px;"
                        "border-radius:4px;font-size:12px'>🟡 關注 |Z|≥1</span>"
                        "<span style='background:#4a2a08;color:#ffab40;padding:3px 10px;"
                        "border-radius:4px;font-size:12px'>🟠 警示 |Z|≥1.5</span>"
                        "<span style='background:#4a0d0d;color:#ff8a80;padding:3px 10px;"
                        "border-radius:4px;font-size:12px'>🔴 極端 |Z|≥2</span>"
                        "</div>",
                        unsafe_allow_html=True,
                    )
                    st.caption("📖 已依 |Z| 由大至小排序，最異常的指標置頂。⭐ = v16.1 高頻替代源")
                    import pandas as _pd_zs
                    # spec: (key, 顯示名, 單位, 小數位, high_is_bad, z>0白話, z<0白話)
                    _zs_indicators = [
                        ("SAHM",         "薩姆規則",            "pp",  2,  True,  "衰退風險升高",     "勞動市場穩健"),
                        ("SLOOS",        "SLOOS 銀行放款意願", "%",   1,  True,  "銀行緊縮放貸",     "銀行寬鬆放貸"),
                        ("ADL",          "RSP/SPY 廣度",        "%",   2,  False, "廣度健康",          "大型股獨撐"),
                        ("PMI",          "ISM PMI",             "",    1,  False, "製造業擴張",        "製造業收縮"),
                        ("LEI",          "⭐ CFNAI 領先指標",   "",    2,  False, "景氣加速",          "景氣放緩"),
                        ("YIELD_10Y2Y",  "10Y-2Y 利差",         "%",   3,  False, "正斜率（健康）",    "倒掛（衰退預警）"),
                        ("YIELD_10Y3M",  "10Y-3M 利差",         "%",   2,  False, "正斜率（健康）",    "倒掛（衰退預警）"),
                        ("HY_SPREAD",    "高收益債利差",        "%",   2,  True,  "信用壓力升溫",      "信用環境寬鬆"),
                        ("VIX",          "VIX 恐慌指數",        "",    1,  True,  "市場恐慌升溫",      "市場情緒平靜"),
                        ("CPI",          "CPI 通膨率",          "%",   1,  True,  "物價壓力升溫",      "通膨壓力減退"),
                        ("PPI",          "PPI 生產者物價",      "%",   2,  True,  "上游成本升溫",      "上游成本回落"),
                        ("INFL_EXP_5Y",  "⭐ 5Y 通膨預期",      "%",   2,  True,  "通膨預期升溫",      "通膨預期降溫"),
                        ("FED_RATE",     "聯準會利率",          "%",   2,  True,  "資金成本上升",      "資金成本下降"),
                        ("UNEMPLOYMENT", "失業率",              "%",   1,  True,  "勞動市場惡化",      "勞動市場改善"),
                        ("CONT_CLAIMS",  "⭐ 持續失業金週頻",   "萬",  0,  True,  "失業惡化",          "就業改善"),
                        ("COPPER",       "銅博士月漲跌",        "%",   1,  False, "全球景氣轉熱",      "全球景氣轉冷"),
                        ("CONSUMER_CONF","消費者信心",          "",    1,  False, "消費信心強",        "消費信心弱"),
                        ("JOBLESS",      "初領失業金",          "萬",  1,  True,  "裁員壓力升溫",      "裁員壓力降溫"),
                        ("M2",           "M2 YoY",              "%",   1,  False, "貨幣供給寬鬆",      "貨幣供給緊縮"),
                        ("M2_WEEKLY",    "⭐ M2 週頻 YoY",      "%",   2,  False, "貨幣供給寬鬆",      "貨幣供給緊縮"),
                        ("FED_BS",       "Fed 資產負債表 YoY",  "%",   2,  False, "QE 擴表",           "QT 縮表"),
                        ("DXY",          "美元指數",            "",    2,  True,  "美元走強（外幣壓力）","美元走弱（外幣受益）"),
                        ("PERMIT_HOUSING","⭐ 建照核發",         "千",  0,  False, "房市領先強",        "房市領先弱"),
                    ]
                    _zs_rows = []
                    for _zk, _zname, _zunit, _zdec, _zhigh_bad, _z_pos_phrase, _z_neg_phrase in _zs_indicators:
                        _zd = ind.get(_zk) or {}
                        _zv = _zd.get("value")
                        _zs_raw = _zd.get("series")
                        # 預設行：資料不足時佔位（不參與 |Z| 排序，會 sink 到表尾）
                        if _zv is None:
                            _zs_rows.append({
                                "_abs": -1, "指標": _zname, "當前值": "—",
                                "白話判讀": "⬜ 資料不足，待補",
                            })
                            continue
                        try:
                            _zv_f = float(_zv)
                        except (TypeError, ValueError):
                            _zs_rows.append({
                                "_abs": -1, "指標": _zname, "當前值": str(_zv)[:10],
                                "白話判讀": "⬜ 數值格式異常",
                            })
                            continue
                        _z_score = None
                        if _zs_raw is not None:
                            try:
                                _zser = (_zs_raw if isinstance(_zs_raw, _pd_zs.Series)
                                         else _pd_zs.Series(_zs_raw)).dropna()
                                if len(_zser) >= 10:
                                    _zmu, _zsig = float(_zser.mean()), float(_zser.std())
                                    if _zsig > 0 and not (_zsig != _zsig):  # NaN guard
                                        _z_cand = (_zv_f - _zmu) / _zsig
                                        if _z_cand == _z_cand:  # NaN guard
                                            _z_score = _z_cand
                            except Exception:
                                pass  # noqa: smoke-allow-pass
                        _unit_s = f" {_zunit}" if _zunit else ""
                        _val_s  = f"{_zv_f:.{_zdec}f}{_unit_s}"
                        # 燈號 + 白話
                        if _z_score is None:
                            _verdict = "⬜ 樣本不足，無法判讀"
                            _abs_z = -1
                        else:
                            _abs_z = abs(_z_score)
                            _phrase = _z_pos_phrase if _z_score > 0 else _z_neg_phrase
                            if _abs_z >= 2:
                                _icon = "🔴 極端"
                            elif _abs_z >= 1.5:
                                _icon = "🟠 警示"
                            elif _abs_z >= 1:
                                _icon = "🟡 關注"
                            else:
                                _icon = "🟢 正常"
                            _verdict = f"{_icon}（{_phrase}，Z={_z_score:+.2f}）"
                        _zs_rows.append({
                            "_abs": _abs_z,
                            "指標": _zname,
                            "當前值": _val_s,
                            "白話判讀": _verdict,
                        })
                    if _zs_rows:
                        # |Z| DESC，資料不足（_abs=-1）一律沉底
                        _zs_rows.sort(key=lambda r: r["_abs"], reverse=True)
                        for r in _zs_rows:
                            r.pop("_abs", None)
                        _zs_df = _pd_zs.DataFrame(_zs_rows)
                        st.dataframe(_zs_df, use_container_width=True, hide_index=True,
                                     column_config={
                                         "指標":     st.column_config.TextColumn(width="small"),
                                         "當前值":   st.column_config.TextColumn(width="small"),
                                         "白話判讀": st.column_config.TextColumn(width="large"),
                                     })

            # ══════════════════════════════════════════════════
            # L3 情境判斷卡（Logic A / B）— L3 only
            # ══════════════════════════════════════════════════
            if _show_l3:
                _pmi_v = float((ind.get("PMI") or {}).get("value") or 0)
                _l3_sit_cards = []
                if _pmi_v > 0 and _pmi_v < 50 and _sahm_v < 0.5:
                    _l3_sit_cards.append({
                        "icon": "🟡", "border": "#ff9800", "bg": "#1a1200",
                        "title": "【Situation A — 庫存調整，非衰退】",
                        "body": (f"PMI={_pmi_v:.1f}（<50 收縮）但薩姆規則={_sahm_v:.2f}（<0.5 安全線）。"
                                 f"製造業庫存去化壓力，消費端仍撐盤，非系統性衰退訊號。"
                                 f"策略：維持衛星資產比重，等待 PMI 觸底回升確認後加碼。"),
                    })
                if _adl_v < -2:
                    _l3_sit_cards.append({
                        "icon": "🔴", "border": "#f44336", "bg": "#1a0606",
                        "title": "【Situation B — 極端乖離警報】",
                        "body": (f"RSP/SPY 市場廣度={_adl_v:.2f}%（< -2% 危險線）。"
                                 f"大型權值股虛假拉抬，等權重指數嚴重落後。"
                                 f"策略：啟動衛星部位分批停利，降低集中型/主題型基金配置。"),
                    })
                if _l3_sit_cards:
                    st.markdown("##### 🧭 L3 情境判斷")
                    for _sc in _l3_sit_cards:
                        st.markdown(
                            f"<div style='background:{_sc['bg']};border-left:4px solid {_sc['border']};" \
                            f"border-radius:0 10px 10px 0;padding:12px 16px;margin:6px 0'>"
                            f"<span style='font-size:16px'>{_sc['icon']}</span> "
                            f"<b style='color:#e6edf3'>{_sc['title']}</b><br>"
                            f"<span style='color:#ccc;font-size:13px'>{_sc['body']}</span></div>",
                            unsafe_allow_html=True)


            # v19.40 ARCHIVED PR2:
            # ══ 📈 L2 景氣循環歷史對照圖（危機紅區 × 指標趨勢）expander
            # archived 原因：搬遷至 📖 說明書 Tab §11 宏觀教學文獻
            # 完整原始程式碼見 git log @ 13026cc 之前（L1284-L1356 ~73 行）

            # ── L2 視角到此結束，L3 繼續顯示完整儀表板 ──────────────────
            if not _show_l2_plus:
                pass  # L1 只看 Gauge + 清單，不繼續渲染下方 L3 內容

            # v19.38 ARCHIVED PR1B (PR #245)：
            # 景氣時鐘 4 象限 + 天氣預報 + AI 配置建議 — 週級反應遲鈍，phase data 已餵 AI 摘要
            # 風險警示燈號 + 系統性風險 + 美林時鐘語音 — 與 ① 戰情室 + 系統性風險 widget 重複
            # （phase / systemic_risk_data 仍存 session_state，AI 摘要繼續吃到）
            # 完整原始程式碼見 git log @ 91da530 之前（L1364-L1551）

            # ── 宏觀風險溫度計 + 景氣循環羅盤 + AI（僅 L3）──────────────
            import pandas as _pd_mac
            def _safe_series(s):
                if s is None: return None
                try:
                    if not isinstance(s, _pd_mac.Series): s = _pd_mac.Series(s)
                    return s.dropna().tail(60)
                except Exception: return None

            # v19.39 ARCHIVED PR1C (PR #TBD):
            # 🌡️ 宏觀風險溫度計 4 cards + V4 複合風險溫度計 + 🎯 風險評分校準 + 🧮 景氣分數校準
            # archived 原因：
            #   - 風險溫度計 VIX/PMI/YIELD/分數 bar 與 ② 拐點偵測 + ① 戰情室三儀表完全重複
            #   - V4 複合 risk_score 為單一加權分，與 score_val 同源
            #   - 校準 2 個（risk score F1 / 14-factor）屬「教學/回測」性質，非熊市直接驗證面板
            # 4 panels session_state stash 已停用，AI 摘要 widget 不再依賴
            # 完整原始程式碼見 git log @ 7244d5a 之前（L1379-L1833 ~455 行）

            # ── 🌊 流動性壓力預警引擎（v18.228：按鈕觸發，不塞總經主載入路徑）──
            def _load_liquidity_factors() -> None:
                with st.spinner("抓取 FRED / DefiLlama / Yahoo 流動性因子（約 10–30 秒）..."):
                    try:
                        from services.liquidity_engine import (
                            compute_liquidity_score, fetch_liquidity_factors)
                        _f = fetch_liquidity_factors(FRED_KEY)
                        st.session_state.liquidity_factors = _f
                        st.session_state.liquidity_score = compute_liquidity_score(_f)
                    except Exception as _le:
                        st.session_state.liquidity_factors = {}
                        st.session_state.liquidity_score = None
                        st.error(f"流動性因子載入失敗：{_le}")

            _liq_score = st.session_state.get("liquidity_score")
            _liq_facs  = st.session_state.get("liquidity_factors") or {}
            if _show_l3 and not _liq_score:
                st.caption("🌊 **流動性壓力預警引擎**（深水區 4 因子）為進階觀察，"
                           "獨立抓取以免拖慢總經主載入。")
                if st.button("🌊 載入流動性壓力預警引擎", key="btn_load_liquidity"):
                    _load_liquidity_factors()
                    st.rerun()
            if _liq_score and _show_l3:
                with st.expander("⑤ 🌊 流動性壓力預警引擎（深水區 4 因子 ｜ lead SPX 1-3 週）", expanded=False):
                    from ui.components.macro_card import make_sparkline as _mk_sl2
                    from services.liquidity_engine import liquidity_verdict
                    if st.button("🔄 重新抓取流動性因子", key="btn_reload_liquidity"):
                        _load_liquidity_factors()
                        st.rerun()
                    st.caption("⚠️ 進階觀察｜XCCY 為代理指標、權重未經真值校準，僅供方向性參考")
                    st.info(liquidity_verdict(_liq_score, _liq_facs))
                    # v18.255 stash 給 AI 白話總體檢
                    try:
                        _liq_top_contrib = []
                        for _b in (_liq_score.get("breakdown") or [])[:3]:
                            _liq_top_contrib.append({
                                "name": str(_b.get("name", ""))[:20],
                                "contrib": float(_b.get("contrib", 0) or 0),
                            })
                        st.session_state["_macro_liquidity"] = {
                            "value": float(_liq_score.get("value", 0) or 0),
                            "tier": str(_liq_score.get("tier", "—")),
                            "signal": str(_liq_score.get("signal", "")),
                            "verdict": liquidity_verdict(_liq_score, _liq_facs),
                            "top_contrib": _liq_top_contrib,
                        }
                    except Exception:
                        pass

                    # ── 壓力分數 + 分級 + 逐因子貢獻 ──────────────────
                    _cs_l, _cs_r = st.columns([1, 2])
                    with _cs_l:
                        st.metric("流動性壓力分數", f"{_liq_score['value']:+.2f}",
                                  _liq_score["tier"])
                        st.markdown(
                            f"<div style='font-size:1.3rem'>{_liq_score['signal']} "
                            f"<b style='color:{_liq_score['color']}'>"
                            f"{_liq_score['tier']}</b></div>",
                            unsafe_allow_html=True)
                    with _cs_r:
                        st.markdown("**逐因子貢獻**（紅=推升壓力／綠=壓低）")
                        _bd = _liq_score.get("breakdown") or []
                        if _bd:
                            _bfig = go.Figure(go.Bar(
                                x=[b["name"][:10] for b in _bd],
                                y=[b["contrib"] for b in _bd],
                                marker_color=["#f44336" if b["contrib"] > 0
                                              else "#00c853" for b in _bd],
                                hovertemplate="%{x}: 貢獻 %{y:+.3f}<extra></extra>"))
                            _bfig.add_hline(y=0, line_color="#555", line_width=1)
                            _bfig.update_layout(
                                height=170, margin=dict(t=4, b=40, l=4, r=4),
                                paper_bgcolor="rgba(0,0,0,0)",
                                plot_bgcolor="rgba(0,0,0,0)", showlegend=False,
                                xaxis=dict(showgrid=False, tickangle=-30,
                                           tickfont=dict(size=9), fixedrange=True),
                                yaxis=dict(showgrid=False, zeroline=False,
                                           fixedrange=True))
                            st.plotly_chart(_bfig, use_container_width=True,
                                            config={"displayModeBar": False})

                    # ── 合成壓力分數歷史趨勢（警戒線 1／危機線 2）──────
                    _scs = _safe_series(_liq_score.get("score_series"))
                    if _scs is not None and len(_scs) >= 2:
                        st.markdown("**📉 流動性壓力分數趨勢**")
                        _trend = _mk_sl2(_scs, threshold_warn=1.0,
                                         threshold_crit=2.0, high_is_bad=True,
                                         lookback=120, height=160)
                        if _trend is not None:
                            st.plotly_chart(_trend, use_container_width=True,
                                            config={"displayModeBar": False})
                    st.divider()

                    # ── 三個 risk-off 壓力因子卡 ─────────────────────
                    _fcols = st.columns(3)
                    for _col, _fk in zip(
                            _fcols, ("XCCY_PROXY", "CARRY_UNWIND", "MOVE_VIX")):
                        _fe = _liq_facs.get(_fk)
                        with _col:
                            if not _fe:
                                st.caption(f"（{_fk} 無資料）")
                                continue
                            _fz = _fe.get("zscore")
                            st.markdown(f"**{_fe['signal']} {_fe['name']}**")
                            st.markdown(
                                f"值 `{_fe['value']}{_fe.get('unit', '')}`　"
                                f"Z `{'—' if _fz is None else f'{_fz:+.2f}'}`")
                            _fs = _safe_series(_fe.get("series"))
                            _fsl = (_mk_sl2(_fs, high_is_bad=True, lookback=60,
                                            height=110)
                                    if _fs is not None else None)
                            if _fsl is not None:
                                st.plotly_chart(_fsl, use_container_width=True,
                                                config={"displayModeBar": False})
                            st.caption(_fe.get("desc", ""))
                    st.divider()

                    # ── SSR 鏈上子彈水位（獨立，不計入壓力分數）──────
                    _ssr = _liq_facs.get("SSR")
                    if _ssr:
                        _ssr_l, _ssr_r = st.columns([1.5, 1])
                        with _ssr_l:
                            st.markdown(f"**🔫 {_ssr['name']}**")
                            _ssr_s = _safe_series(_ssr.get("series"))
                            _ssr_fig = (_mk_sl2(_ssr_s, high_is_bad=False,
                                                lookback=60, height=140)
                                        if _ssr_s is not None else None)
                            if _ssr_fig is not None:
                                st.plotly_chart(_ssr_fig, use_container_width=True,
                                                config={"displayModeBar": False})
                            else:
                                st.caption("📡 資料載入中或筆數不足…")
                        with _ssr_r:
                            _sz = _ssr.get("zscore")
                            st.markdown(
                                "**怎麼看？**　SSR = BTC市值 ÷ 穩定幣市值，"
                                "**獨立於壓力分數**（不計入）。\n\n"
                                f"**目前讀數**　{_ssr['signal']} SSR "
                                f"`{_ssr['value']}`，Z "
                                f"`{'—' if _sz is None else f'{_sz:+.2f}'}`\n\n"
                                "SSR 低(Z<0)=鏈上法幣子彈多=潛在買盤強；高=子彈耗盡")

            # v19.39 ARCHIVED PR1C (PR #TBD):
            # 🧭 景氣循環羅盤（V5：薩姆 + RSP/SPY 廣度 + 基準利率）
            # archived 原因：薩姆規則已在 ② 拐點偵測中心 + ④ 短線雷達 重複呈現，
            #   羅盤的合議文字（虛假繁榮/復甦/分化）與 ① 戰情室評語衝突；
            #   _macro_compass stash 仍保留（AI 摘要遞延使用 — _sahm_d 取自 ② 拐點 cache）
            # 完整原始程式碼見 git log @ 7244d5a 之前

            # v19.40 ARCHIVED PR2:
            # ── 指標貢獻明細 _CONTRIB_MAP + 👉 查看完整 23 項指標加扣分明細 expander
            # archived 原因：搬遷至 📖 說明書 Tab §11 宏觀教學文獻
            # _macro_23items stash 已移至 tab6 render 時寫入（AI 摘要向後相容）
            # 完整原始程式碼見 git log @ 13026cc 之前（L1534-L1637 ~104 行）
            # ══════════════════════════════════════════════════
            # L3 資本防線 — 含息報酬 vs 配息率（Bar Chart）
            # ══════════════════════════════════════════════════
            if _show_l3:
                _pf_def = [f for f in st.session_state.get("portfolio_funds", []) if f.get("loaded")]
                if _pf_def:
                    st.markdown("#### 💰 資本防線 — 含息報酬 vs 配息率")
                    _def_names = [f.get("fund_name") or f.get("code","?") for f in _pf_def]
                    _def_tr1y  = [float((f.get("metrics") or f.get("m") or {}).get("ret_1y") or 0) for f in _pf_def]
                    _def_adr   = [float((f.get("metrics") or f.get("m") or {}).get("annual_div_rate") or 0) for f in _pf_def]
                    _def_colors = ["#f44336" if tr < adr else "#00c853"
                                   for tr, adr in zip(_def_tr1y, _def_adr)]
                    _def_fig = go.Figure()
                    _def_fig.add_trace(go.Bar(
                        x=_def_names, y=_def_tr1y,
                        marker_color=_def_colors,
                        text=[f"{v:.1f}%" for v in _def_tr1y],
                        textposition="outside",
                        name="含息報酬率 TR1Y",
                        customdata=list(zip(_def_adr, ["🚨 本金侵蝕" if tr < adr else "" for tr, adr in zip(_def_tr1y, _def_adr)])),
                        hovertemplate="<b>%{x}</b><br>TR1Y: %{y:.1f}%<br>配息率: %{customdata[0]:.1f}%<br>%{customdata[1]}<extra></extra>",
                    ))
                    _def_fig.add_trace(go.Scatter(
                        x=_def_names, y=_def_adr,
                        mode="markers",
                        marker=dict(symbol="line-ew", size=16, color="#ff9800",
                                    line=dict(width=3, color="#ff9800")),
                        name="配息年化率",
                        hovertemplate="配息率: %{y:.1f}%<extra></extra>",
                    ))
                    _def_fig.update_layout(
                        paper_bgcolor="#0e1117", plot_bgcolor="#161b22",
                        font_color="#e6edf3", height=260,
                        margin=dict(t=20, b=50, l=10, r=10),
                        legend=dict(orientation="h", y=-0.35),
                        xaxis=dict(tickfont=dict(size=11)),
                        yaxis=dict(title="報酬率 (%)", ticksuffix="%"),
                    )
                    st.plotly_chart(_def_fig, use_container_width=True)
                    st.caption("🟢 綠色 = TR1Y > 配息率（配息有保障）｜🔴 紅色 = TR1Y < 配息率（本金侵蝕警示）｜橙色橫線 = 配息年化率")
                    # v18.255 stash 給 AI 白話總體檢
                    try:
                        _eroded = [(n, tr, adr) for n, tr, adr
                                   in zip(_def_names, _def_tr1y, _def_adr)
                                   if tr < adr]
                        st.session_state["_macro_capital_line"] = {
                            "n_funds": len(_def_names),
                            "n_eroded": len(_eroded),
                            "eroded_funds": [{"name": n[:20], "tr1y": float(tr),
                                              "adr": float(adr)} for n, tr, adr in _eroded[:5]],
                        }
                    except Exception:
                        pass

            # ── 市場新聞（折疊）── L3 only
            if _show_l3:
                _news_items = st.session_state.get("news_items",[])
                if _news_items:
                    with st.expander(f"📰 市場新聞（{len(_news_items)} 則）", expanded=False):
                        for _ni in _news_items[:20]:
                            _nt = _ni.get("title","")[:90]
                            _ns = _ni.get("source","")
                            _nu = _ni.get("url","") or _ni.get("link","")
                            _nd = str(_ni.get("published",""))[:16]
                            if _nu:
                                st.markdown(f"**[{_nt}]({_nu})** <span style='color:#888;font-size:11px'>｜{_ns} {_nd}</span>", unsafe_allow_html=True)
                            else:
                                st.markdown(f"**{_nt}** <span style='color:#888;font-size:11px'>｜{_ns} {_nd}</span>", unsafe_allow_html=True)

            # ── v19.20 ⚡ 短線風險雷達（10 燈 1-day 急殺早期警報）──
            st.divider()
            st.markdown("### ④ ⚡ 短線風險雷達（24H Risk-Off Velocity Radar ｜ 日級急殺確認）")
            st.caption("10 個 1-day 動量／情緒／位階訊號 — 補拐點偵測中心（月～季級慢）之短缺，"
                       "捕捉 1-day 急殺前的早期警報："
                       "VIX 級距+期限結構 ｜ HY 信用日變化 ｜ 10Y 殖利率衝擊 ｜ MOVE 債券恐慌 ｜ "
                       "SPX 均線破口 ｜ SOX 半導體 ｜ 防禦/攻擊輪動 ｜ Put/Call ｜ 亞洲夜盤")
            # 真實 FRED API key 為 32 字元；短於 30 視為測試/未設定 → 跳過避免 16 次網路呼叫拖滿 AppTest budget
            # v19.21：頂部雙速合議已抓過雷達並 cache 在 session_state，這裡直接讀避免重複網路呼叫
            _top_cache = st.session_state.get("_radar_v1921_top")
            if _top_cache is not None:
                _radar, _radar_sum = _top_cache
            elif not FRED_KEY or len(str(FRED_KEY).strip()) < 30:
                _radar = None
                _radar_sum = None
            else:
                try:
                    from services.risk_radar import detect_risk_radar, summarize_radar
                    _radar = detect_risk_radar(FRED_KEY)
                    _radar_sum = summarize_radar(_radar)
                    st.session_state["_radar_v1921_top"] = (_radar, _radar_sum)
                except Exception as _radar_e:  # noqa: BLE001
                    _radar = None
                    _radar_sum = None
                    st.warning(f"⚠️ 風險雷達失敗：{str(_radar_e)[:120]}")

            if _radar and _radar_sum:
                st.markdown(
                    f"<div style='background:#0d1117;border:2px solid {_radar_sum['color']};"
                    f"border-radius:10px;padding:10px 16px;margin:6px 0'>"
                    f"<span style='color:{_radar_sum['color']};font-size:18px;font-weight:800'>"
                    f"整體狀態：{_radar_sum['level']}</span>"
                    f"<span style='color:#aaa;margin-left:20px;font-size:13px'>"
                    f"🔴 {_radar_sum['red']} ｜ 🟡 {_radar_sum['yellow']} ｜ "
                    f"🟢 {_radar_sum['green']} ｜ ⬜ {_radar_sum['gray']}</span>"
                    f"</div>", unsafe_allow_html=True)

                _radar_cards = [
                    ("vix_level",       "🌪️ VIX 恐慌指數"),
                    ("vix_term_struct", "📐 VIX 期限結構"),
                    ("hy_oas_delta",    "💳 HY 信用日變化"),
                    ("yield_10y_shock", "📈 10Y 殖利率衝擊"),
                    ("move_level",      "🌊 MOVE 債市波動"),
                    ("spx_trend_break", "📉 SPX 均線破口"),
                    ("sox_drop",        "🔌 半導體單日跌幅"),
                    ("sector_rotation", "🔄 防禦 vs 攻擊"),
                    ("put_call_ratio",  "📊 Put/Call 比率"),
                    ("asia_overnight",  "🌏 亞洲夜盤領先"),
                ]
                for _row in (_radar_cards[:5], _radar_cards[5:]):
                    _cols_radar = st.columns(5)
                    for _col_r, (_key_r, _title_r) in zip(_cols_radar, _row):
                        _dr = _radar.get(_key_r) or {}
                        _sig_r = _dr.get("signal", "⬜ 無資料")
                        _col_c_r = _dr.get("color", "#888")
                        _val_r = _dr.get("value")
                        _note_r = _dr.get("note", "")
                        _label_r = _dr.get("label", "")
                        _val_txt_r = "—" if _val_r is None else f"{_val_r}"
                        with _col_r:
                            st.markdown(
                                f"<div style='background:#0d1117;border:2px solid {_col_c_r};"
                                f"border-radius:10px;padding:10px 12px;margin:4px 0;"
                                f"min-height:165px;"
                                f"display:flex;flex-direction:column;justify-content:space-between'>"
                                f"<div>"
                                f"<div style='color:#888;font-size:10px;letter-spacing:1px'>"
                                f"{_title_r}</div>"
                                f"<div style='color:{_col_c_r};font-size:15px;font-weight:800;"
                                f"margin:4px 0 6px'>{_sig_r}</div>"
                                f"<div style='color:#fff;font-weight:700;font-size:14px'>"
                                f"值 {_val_txt_r}</div>"
                                f"</div>"
                                f"<div style='color:#aaa;font-size:9px;border-top:1px solid #30363d;"
                                f"padding-top:4px;margin-top:4px;line-height:1.3'>{_note_r}"
                                f"<br/><span style='color:#555'>{_label_r}</span></div>"
                                f"</div>", unsafe_allow_html=True)
                st.caption("📡 資料源：FRED + Yahoo Chart API（NAS proxy）｜閾值：🟢平靜 → 🟡警戒 → 🔴警報")

            # v19.39 ARCHIVED PR1C (PR #TBD):
            # 📅 Tier A 事件 + 估值（FOMC / NFP / CPI 倒數日曆 + S&P 500 Forward P/E + GDPNow）
            # archived 原因：屬「事件日曆」短線維度，非熊市結構驗證；
            #   user 反饋：留下近2個月內可驗證熊市的面板，事件日曆已在外部 calendar 服務追蹤
            # 完整原始程式碼見 git log @ 7244d5a 之前

            # ── v19.18 🎯 拐點偵測中心（合併 v18.20 PMI/yield + v18.250 三件套）──
            st.divider()
            st.markdown("### ② 🎯 拐點偵測中心（熊市預警主面板 ｜ 月級結構訊號）")
            st.caption("集中所有景氣翻轉訊號：製造業新訂單－庫存擴散 ｜ 10Y-2Y 殖利率倒掛翻正 ｜ "
                       "HY 信用利差 ｜ 薩姆規則 ｜ CFNAI 領先指標 ｜ 歷史回測 ｜ 變數重要性")
            try:
                _tp = detect_turning_points(FRED_KEY)
            except Exception as _tp_e:  # noqa: BLE001
                _tp = None
                st.warning(f"⚠️ 拐點偵測失敗：{str(_tp_e)[:120]}")

            if _tp:
                _tp_c1, _tp_c2 = st.columns(2)
                for _col, _key, _title in [
                    (_tp_c1, "pmi_diff",    "🏭 新訂單 − 庫存擴散"),
                    (_tp_c2, "yield_curve", "📉 10Y − 2Y 殖利率利差"),
                ]:
                    _d = _tp[_key]
                    _sig = _d.get("signal", "⬜")
                    _col_c = _d.get("color", "#888")
                    _val = _d.get("value")
                    _prev = _d.get("prev")
                    _trend = _d.get("trend") or []
                    _note = _d.get("note", "")
                    _label = _d.get("label", "")
                    _val_txt = ("—" if _val is None else
                                (f"{_val:+.2f}pp" if _key == "pmi_diff"
                                 else f"{_val:+.2f}%"))
                    _prev_txt = ("—" if _prev is None else
                                 (f"{_prev:+.2f}pp" if _key == "pmi_diff"
                                  else f"{_prev:+.2f}%"))
                    with _col:
                        st.markdown(
                            f"<div style='background:#0d1117;border:2px solid {_col_c};"
                            f"border-radius:12px;padding:14px 18px;margin:6px 0'>"
                            f"<div style='color:#888;font-size:11px;letter-spacing:1px'>"
                            f"{_title}</div>"
                            f"<div style='color:{_col_c};font-size:18px;font-weight:800;"
                            f"margin:6px 0 10px'>{_sig}</div>"
                            f"<div style='display:flex;gap:24px;flex-wrap:wrap;margin-bottom:8px'>"
                            f"<div><div style='color:#888;font-size:10px'>本期</div>"
                            f"<div style='color:#fff;font-weight:700;font-size:16px'>{_val_txt}</div></div>"
                            f"<div><div style='color:#888;font-size:10px'>前期</div>"
                            f"<div style='color:#aaa;font-weight:700;font-size:16px'>{_prev_txt}</div></div>"
                            f"</div>"
                            f"<div style='color:#aaa;font-size:11px;border-top:1px solid #30363d;"
                            f"padding-top:6px;margin-top:4px'>{_note}</div>"
                            f"<div style='color:#555;font-size:10px;margin-top:4px'>{_label}</div>"
                            f"</div>", unsafe_allow_html=True)
                        # Sparkline（近 6~8 期）
                        if _trend and len(_trend) >= 2:
                            try:
                                import plotly.graph_objects as _go_tp
                                _spfig = _go_tp.Figure()
                                _spfig.add_trace(_go_tp.Scatter(
                                    y=_trend, mode="lines+markers",
                                    line=dict(color=_col_c, width=2),
                                    marker=dict(size=5, color=_col_c),
                                    showlegend=False,
                                ))
                                _spfig.add_hline(y=0, line_dash="dot",
                                                 line_color="#888", line_width=1)
                                _spfig.update_layout(
                                    height=110, margin=dict(l=10, r=10, t=4, b=4),
                                    plot_bgcolor="#0d1117", paper_bgcolor="#0d1117",
                                    xaxis=dict(visible=False),
                                    yaxis=dict(showgrid=False, color="#555",
                                               tickfont=dict(size=9)),
                                )
                                st.plotly_chart(_spfig, use_container_width=True,
                                                key=f"sp_tp_{_key}")
                            except Exception:
                                pass  # noqa: smoke-allow-pass
                st.caption(
                    "💡 **拐點解讀**："
                    "🚀 新訂單擴散由負轉正 = 製造業景氣領先指標反轉，通常領先 EPS 修正 1~2 季｜"
                    "⚠️ 10Y-2Y 倒掛翻正 = 衰退末期，歷史經驗為股市底部累積區（1990/2000/2008/2020）"
                )

                # ── v18.250 第二排：信用 / 衰退 / 領先 三組景氣反轉拐點 ─────
                _tp_c3, _tp_c4, _tp_c5 = st.columns(3)
                for _col, _key, _title in [
                    (_tp_c3, "hy_spread", "💳 HY 信用利差"),
                    (_tp_c4, "sahm_rule", "📉 薩姆規則（衰退警報）"),
                    (_tp_c5, "lei_cfnai", "🔭 CFNAI 領先指標"),
                ]:
                    _d = _tp.get(_key)
                    if not _d:
                        continue
                    _sig = _d.get("signal", "⬜")
                    _col_c = _d.get("color", "#888")
                    _val = _d.get("value")
                    _prev = _d.get("prev")
                    _trend = _d.get("trend") or []
                    _note = _d.get("note", "")
                    _label = _d.get("label", "")
                    # 單位後綴隨指標調整
                    _unit = "%" if _key == "hy_spread" else ""
                    _val_txt = "—" if _val is None else f"{_val:+.2f}{_unit}"
                    _prev_txt = "—" if _prev is None else f"{_prev:+.2f}{_unit}"
                    with _col:
                        st.markdown(
                            f"<div style='background:#0d1117;border:2px solid {_col_c};"
                            f"border-radius:12px;padding:14px 18px;margin:6px 0'>"
                            f"<div style='color:#888;font-size:11px;letter-spacing:1px'>"
                            f"{_title}</div>"
                            f"<div style='color:{_col_c};font-size:18px;font-weight:800;"
                            f"margin:6px 0 10px'>{_sig}</div>"
                            f"<div style='display:flex;gap:24px;flex-wrap:wrap;margin-bottom:8px'>"
                            f"<div><div style='color:#888;font-size:10px'>本期</div>"
                            f"<div style='color:#fff;font-weight:700;font-size:16px'>{_val_txt}</div></div>"
                            f"<div><div style='color:#888;font-size:10px'>前期</div>"
                            f"<div style='color:#aaa;font-weight:700;font-size:16px'>{_prev_txt}</div></div>"
                            f"</div>"
                            f"<div style='color:#aaa;font-size:11px;border-top:1px solid #30363d;"
                            f"padding-top:6px;margin-top:4px'>{_note}</div>"
                            f"<div style='color:#555;font-size:10px;margin-top:4px'>{_label}</div>"
                            f"</div>", unsafe_allow_html=True)
                        if _trend and len(_trend) >= 2:
                            try:
                                import plotly.graph_objects as _go_tp
                                _spfig = _go_tp.Figure()
                                _spfig.add_trace(_go_tp.Scatter(
                                    y=_trend, mode="lines+markers",
                                    line=dict(color=_col_c, width=2),
                                    marker=dict(size=5, color=_col_c),
                                    showlegend=False,
                                ))
                                _spfig.add_hline(y=0, line_dash="dot",
                                                 line_color="#888", line_width=1)
                                _spfig.update_layout(
                                    height=110, margin=dict(l=10, r=10, t=4, b=4),
                                    plot_bgcolor="#0d1117", paper_bgcolor="#0d1117",
                                    xaxis=dict(visible=False),
                                    yaxis=dict(showgrid=False, color="#555",
                                               tickfont=dict(size=9)),
                                )
                                st.plotly_chart(_spfig, use_container_width=True,
                                                key=f"sp_tp_{_key}")
                            except Exception:
                                pass  # noqa: smoke-allow-pass
                st.caption(
                    "🎯 **景氣反轉三件套**："
                    "💳 HY 利差高位回落 = 信用市場開始正常化｜"
                    "📉 薩姆規則跌破 0.5 = 衰退警報解除（底部布局訊號）｜"
                    "🔭 CFNAI 3M 均值由負轉正 = 85 指標領先翻揚（擴張確認）"
                )

            # ── v18.21 📊 拐點訊號歷史回測（倒掛翻正 vs SPX）─────────────
            with st.expander(
                "📊 歷史回測：倒掛翻正後 6/12/18M SPX 表現",
                expanded=False,
            ):
                try:
                    _bt = backtest_turning_points(FRED_KEY)
                except Exception as _bt_e:  # noqa: BLE001
                    _bt = {"source_ok": False, "note": str(_bt_e)[:120],
                           "events": [], "summary": {"n_events": 0},
                           "spx_series": None, "t10y2y_series": None}

                if not _bt.get("source_ok"):
                    st.info(
                        f"⚠️ FRED 或 ^GSPC 抓取失敗，回測暫不可用。"
                        f"{_bt.get('note','')}"
                    )
                elif _bt["summary"]["n_events"] == 0:
                    st.info(f"近 30 年無符合條件之倒掛翻正事件（{_bt.get('note','')}）")
                else:
                    _sm = _bt["summary"]
                    _ev = _bt["events"]
                    # ── KPI 列（5 欄）─────────────────────────────
                    _bk1, _bk2, _bk3, _bk4, _bk5 = st.columns(5)
                    _bk1.metric("事件數", f"{_sm['n_events']}",
                                help=f"完整 18M 窗口：{_sm['n_complete_18m']}")
                    _bk2.metric(
                        "6M 中位",
                        f"{_sm['median_6m']:+.2f}%" if _sm.get('median_6m') is not None else "—",
                        help=f"勝率 {_sm['win_rate_6m']:.0f}%" if _sm.get('win_rate_6m') is not None else "")
                    _bk3.metric(
                        "12M 中位",
                        f"{_sm['median_12m']:+.2f}%" if _sm.get('median_12m') is not None else "—",
                        help=f"勝率 {_sm['win_rate_12m']:.0f}%" if _sm.get('win_rate_12m') is not None else "")
                    _bk4.metric(
                        "18M 中位",
                        f"{_sm['median_18m']:+.2f}%" if _sm.get('median_18m') is not None else "—",
                        help=f"勝率 {_sm['win_rate_18m']:.0f}%" if _sm.get('win_rate_18m') is not None else "")
                    _bk5.metric(
                        "12M 勝率",
                        f"{_sm['win_rate_12m']:.0f}%" if _sm.get('win_rate_12m') is not None else "—")
                    # v18.255 stash 給 AI 白話總體檢
                    try:
                        st.session_state["_macro_inv_backtest"] = {
                            "n_events": int(_sm.get("n_events", 0)),
                            "median_6m": _sm.get("median_6m"),
                            "median_12m": _sm.get("median_12m"),
                            "median_18m": _sm.get("median_18m"),
                            "win_rate_12m": _sm.get("win_rate_12m"),
                        }
                    except Exception:
                        pass

                    # ── 事件表 ──────────────────────────────────
                    _bt_df = pd.DataFrame([{
                        "翻正日":        e["date"].strftime("%Y-%m-%d"),
                        "倒掛最深 (%)":  e["t10y2y_min_pre"],
                        "6M 報酬 (%)":   e["ret_6m"],
                        "12M 報酬 (%)":  e["ret_12m"],
                        "18M 報酬 (%)":  e["ret_18m"],
                        "完整窗口":      "✅" if e["complete"] else "⏳",
                    } for e in _ev])
                    st.dataframe(
                        _bt_df,
                        column_config={
                            "倒掛最深 (%)": st.column_config.NumberColumn(format="%.2f"),
                            "6M 報酬 (%)":  st.column_config.NumberColumn(format="%.2f"),
                            "12M 報酬 (%)": st.column_config.NumberColumn(format="%.2f"),
                            "18M 報酬 (%)": st.column_config.NumberColumn(format="%.2f"),
                        },
                        use_container_width=True, hide_index=True,
                    )

                    # ── SPX log 走勢 + 翻正日垂直線 + NBER 衰退期紅陰影 ──
                    _spx = _bt.get("spx_series")
                    if _spx is not None and len(_spx) > 0:
                        try:
                            _btfig = go.Figure()
                            _btfig.add_trace(go.Scatter(
                                x=_spx.index, y=_spx.values, mode="lines",
                                name="S&P 500", line=dict(color="#64b5f6", width=1.5),
                            ))
                            # NBER 衰退期（與 app.py:1778 _crises 同源 + 1990/2001）
                            _bt_crises = [
                                ("1990-07-01", "1991-03-01", "1990 衰退"),
                                ("2001-03-01", "2001-11-01", "2001 衰退"),
                                ("2007-12-01", "2009-06-01", "2008 金融海嘯"),
                                ("2020-02-01", "2020-06-01", "2020 COVID"),
                            ]
                            for _cs, _ce, _cn in _bt_crises:
                                _btfig.add_vrect(
                                    x0=_cs, x1=_ce,
                                    fillcolor="rgba(244,67,54,0.12)",
                                    line_width=0,
                                    annotation_text=_cn,
                                    annotation_position="top left",
                                    annotation_font={"size": 9, "color": "#f44336"},
                                )
                            # 翻正日綠虛線
                            for _e in _ev:
                                _btfig.add_vline(
                                    x=_e["date"], line_dash="dash",
                                    line_color="#00c853", line_width=1, opacity=0.7,
                                )
                            _btfig.update_yaxes(type="log",
                                                gridcolor="#1a1f2e",
                                                color="#888")
                            _btfig.update_xaxes(gridcolor="#1a1f2e", color="#888")
                            _btfig.update_layout(
                                paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
                                font_color="#e6edf3", height=360,
                                margin=dict(t=20, b=30, l=50, r=20),
                                hovermode="x unified",
                                showlegend=False,
                            )
                            st.plotly_chart(_btfig, use_container_width=True,
                                            key="bt_tp_spx_chart")
                        except Exception as _bt_fig_e:  # noqa: BLE001
                            st.caption(f"走勢圖繪製失敗：{str(_bt_fig_e)[:80]}")
                    st.caption(
                        f"樣本 n={_sm['n_events']}，僅供參考；"
                        f"綠色虛線＝倒掛翻正日｜紅色陰影＝NBER 衰退期。"
                        f"窗口未到期事件以 ⏳ 標記且不納入中位數/勝率統計。"
                    )

            # ── v19.18: 7 子領域 Z-Score 健康度已搬到戰情首頁 ① 7-cluster 下方 ──
            # 原 v18.100 區塊整段移除，避免與 7-cluster 視覺重複（user 反饋）

            # v19.39 ARCHIVED PR1C (PR #TBD):
            # 🔗 總經因果鏈 Sankey（升息 → 信貸 → 房市/就業 → VIX）
            # archived 原因：8 節點 9 邊 Sankey 為教學圖示，非熊市直接驗證；
            #   AI 摘要區仍可從 _macro_sankey stash 讀（缺失自動回退「—」）
            # 完整原始程式碼見 git log @ 7244d5a 之前

            # v19.39 ARCHIVED PR1C (PR #TBD):
            # 📊 細項燈號歷史回測（紅燈出現後 LEI 走勢驗證）
            # archived 原因：屬「教學/燈號回測」性質，非熊市直接驗證面板；
            #   AI 摘要區仍可從 _macro_subsector_bt stash 讀（缺失自動回退「—」）
            # 完整原始程式碼見 git log @ 7244d5a 之前

            # v19.40 ARCHIVED PR2:
            # ── v18.108 📊 變數重要性 Top-N（Phase 4）
            # archived 原因：搬遷至 📖 說明書 Tab §11 宏觀教學文獻
            # _macro_var_importance stash 已移至 tab6 render 時寫入
            # 完整原始程式碼見 git log @ 13026cc 之前（L2084-L2169 ~86 行）

            # ── 熱錢監測（v18.236）— 三角交叉：外資 × 匯率 × 背離 ──
            # 境外基金 user 仍要看：台幣匯率變動 → 影響你 USD/EUR 計價基金 TWD 換算後報酬
            st.divider()
            with st.expander("⑥ 💵 台股熱錢監測 — 三角交叉（本土訊號 ｜ FII 日級行為）",
                             expanded=False):
                try:
                    from hot_money import render_hot_money_section
                    _finmind_tok = (st.secrets.get("FINMIND_TOKEN", "")
                                     if hasattr(st, "secrets") else "") or ""
                    render_hot_money_section(token=_finmind_tok,
                                              key_prefix="tab1_hm")
                except Exception as _hme:
                    st.error(f"熱錢監測渲染失敗：[{type(_hme).__name__}] {_hme}")

            # ── MK 景氣時鐘 ＆ 資產輪動（v18.8）── L2/L3 皆顯示
            st.divider()
            render_mk_clock_section(ind)

            # ── AI 結構化總經摘要 ── L3 only
            if _show_l3:
                st.divider()
            if GEMINI_KEY and _show_l3:
                # ── 三色燈號阻斷（Core Protocol v2.0 Ch.1）─────────────
                _ai_mac_pct, _ai_mac_tl = _calc_data_health(ind)
                if _ai_mac_pct < 50:
                    st.markdown(
                        "<div style='border-left:4px solid #f44336;background:#1a1f2e;"
                        "border-radius:0 8px 8px 0;padding:10px 14px;font-size:13px'>"
                        "🔴 <b>紅燈阻斷</b>：總經資料完整率 "
                        f"<b>{_ai_mac_pct}%</b>（&lt;50%），AI 分析停用。"
                        "請前往「🔬 資料診斷」頁確認指標載入狀況。</div>",
                        unsafe_allow_html=True)
                else:
                    if _ai_mac_pct < 80:
                        st.warning(f"🟡 資料完整率 **{_ai_mac_pct}%**（黃燈），AI 結果參考性降低。")
                    # v18.215：Tab1 改用通用「白話總體檢」widget（與 Tab2/3 一致），
                    # 刪除舊七節 macro AI；吃全總經資料、逐章節白話結論 + 時事、無選單。
                    # v19.38：明示 AI 總結涵蓋上方 6 個 KEEP 面板的同源資料（FRED 23 指標 + phase + risk + news）
                    st.markdown("### 🤖 AI 景氣判斷總結")
                    st.caption(
                        "本 AI 摘要吃齊上方 **① 戰情室三儀表 / ② 拐點偵測 / ③ 即時決策矩陣 / "
                        "④ 短線雷達 / ⑤ 流動性壓力 / ⑥ 台股熱錢** 的同源資料"
                        "（FRED 23 指標 + phase + 系統性風險 + 時事新聞），逐章節白話結論。"
                    )
                    from ui.helpers.ai_summary import render_ai_summary_widget  # noqa: PLC0415
                    _mac_snap, _mac_heads, _mac_secs = _build_macro_ai_snapshot(
                        ind, phase,
                        st.session_state.get("composite_score", {}),
                        st.session_state.get("systemic_risk_data"),
                        st.session_state.get("news_items", []),
                    )
                    render_ai_summary_widget(
                        tab_key="tab1",
                        tab_label="總經位階",
                        snapshot=_mac_snap,
                        sections=_mac_secs,
                        headlines=_mac_heads,
                        gemini_api_key=GEMINI_KEY,
                        expanded=True,
                    )
            else:
                st.caption("⚠️ 未設定 GEMINI_API_KEY，AI 分析功能關閉")
    else:
        st.info("👆 點擊「載入總經資料」開始分析")


def _build_macro_ai_snapshot(ind, phase, score, srd, news):
    """v18.215：組 Tab1 總經「全資料」快照給通用白話摘要 widget。

    回傳 (snapshot_str, headlines, sections)。吃齊 Tab1 已算好的資料：
    景氣位階/分數、系統性風險、全部總經指標、領先指標排名、當下子領域燈號、新聞。
    """
    lines = ["## 總經全章節快照"]
    if isinstance(phase, dict) and phase:
        _sc = score.get("total", "—") if isinstance(score, dict) else (score or "—")
        lines.append(f"- 景氣位階：{phase.get('phase', '—')}｜綜合分數：{_sc}")
        _alloc = phase.get("allocation") or phase.get("alloc")
        if isinstance(_alloc, dict) and _alloc:
            lines.append("- 建議配置：" + "、".join(f"{k} {v}%" for k, v in _alloc.items()))
        elif _alloc:
            lines.append(f"- 建議配置：{_alloc}")
    if isinstance(srd, dict) and srd:
        lines.append(f"- 系統性風險評級：{srd.get('risk_level', 'LOW')}"
                     f"（分數 {srd.get('risk_score', '—')}）")
        _trig = srd.get("triggered") or srd.get("keywords")
        if isinstance(_trig, (list, tuple)) and _trig:
            lines.append("  - 觸發事件關鍵字：" + "、".join(str(t) for t in _trig[:5]))
    if isinstance(ind, dict) and ind:
        lines.append("- 關鍵總經指標：")
        for k, v in ind.items():
            if isinstance(v, dict) and "value" in v:
                _sig = v.get("signal", "")
                lines.append(f"  - {k}：{v.get('value')} {v.get('unit', '')}"
                             f"{(' / ' + str(_sig)) if _sig else ''}".rstrip())
            elif isinstance(v, (int, float, str)) and v not in (None, ""):
                lines.append(f"  - {k}：{v}")
    try:
        from services.macro_service import (  # noqa: PLC0415
            rank_macro_drivers as _rmd,
            calc_sub_cycle_lights as _csl,
        )
        _drv = _rmd(ind, target_key="LEI", lag_months=3, min_overlap=24)
        if isinstance(_drv, dict) and _drv.get("ok") and _drv.get("ranked"):
            lines.append("- 領先指標排名（與景氣約 3 個月後的關聯強弱）：" + "、".join(
                f"{r.get('name')}({'同向' if r.get('direction') == '+' else '反向'}"
                f" {float(r.get('abs_corr', 0) or 0):.2f})"
                for r in _drv["ranked"][:3]))
        _lights = _csl(ind)
        if isinstance(_lights, list) and _lights:
            lines.append("- 各產業/子領域當下燈號：" + "、".join(
                f"{x.get('name', '')}{x.get('icon', '')}"
                f"{('(' + str(x.get('verdict')) + ')') if x.get('verdict') else ''}"
                for x in _lights[:8]))
    except Exception:
        pass   # noqa: smoke-allow-pass — 進階分析缺失不阻斷 AI 摘要
    # v18.254：把兩個校準器最新結果寫進快照，供 AI 產出「校準健檢」段落
    # v18.255：改三段式（這代表 / 為什麼 / 該怎麼做）
    try:
        import streamlit as _st  # noqa: PLC0415
        _cms = _st.session_state.get("_cal_macro_score")
        _crs = _st.session_state.get("_cal_risk_score")
        if _cms or _crs:
            lines.append("- 校準健檢（真實 FRED+SPX 回測）：")
            if isinstance(_cms, dict) and _cms:
                lines.append(
                    f"  - 14-factor 景氣分數【代表】總體命中率 {_cms['overall_acc_pct']:.1f}%"
                    f"（horizon={_cms['horizon']}M、{_cms['src']}）；"
                    f"當前 Macro_Score={_cms['cur_score']:.2f} → {_cms['cur_phase']}")
                _pa = _cms.get("phase_acc") or []
                if _pa:
                    _pa_str = "、".join(
                        f"{r.get('phase')} {r.get('hit_rate_pct', 0):.0f}%(n={r.get('n', 0)})"
                        for r in _pa)
                    lines.append(f"    -【為什麼】各位階命中：{_pa_str}（n 越大越可信、<10 不能當主要依據）")
                _gt = _cms.get("grid_top")
                if isinstance(_gt, dict):
                    lines.append(
                        f"    -【該怎麼做】grid_search 最佳門檻 (Peak/Exp/Rec)="
                        f"({_gt['peak_thr']:.1f}/{_gt['expansion_thr']:.1f}/{_gt['recovery_thr']:.1f})"
                        f"→ {_gt['overall_acc_pct']:.1f}%；"
                        f"若比當前公式門檻 (8.0/5.0/3.0) 高 >5% 才值得改 macro_service.py")
                else:
                    lines.append(
                        "    -【該怎麼做】命中率 ≥70% 可照位階建議配置；<70% 應搭配其他指標佐證")
            if isinstance(_crs, dict) and _crs:
                if _crs.get("no_hit"):
                    lines.append(
                        f"  - 3-factor 風險評分【代表】horizon={_crs['horizon']}M、"
                        f"drawdown={_crs['drawdown_pct']}%、window={_crs['rolling_win']}M "
                        f"參數下校準器無命中")
                    lines.append(
                        "    -【為什麼】該回看期內 SPX 未出現此規模回檔（樣本不足、不是規則 bug）")
                    lines.append(
                        "    -【該怎麼做】放寬 drawdown 到 -15% 或 -10% 重新校準才能讀")
                else:
                    lines.append(
                        f"  - 3-factor 風險評分【代表】最佳 F1 門檻={_crs['best_threshold']:.2f}（"
                        f"P={_crs['precision']:.0%}、R={_crs['recall']:.0%}、"
                        f"F1={_crs['f1']:.0%}）；當前 risk_score={_crs['cur_risk_score']:.2f}")
                    if _crs['cur_risk_score'] >= _crs['best_threshold']:
                        lines.append(
                            "    -【為什麼】當前分數已 ≥ 警戒門檻 → 歷史上類似讀數有機率出現 drawdown")
                        lines.append(
                            "    -【該怎麼做】建議減持高 beta 部位、提高現金比、停止新加碼")
                    else:
                        lines.append(
                            "    -【為什麼】當前分數低於警戒門檻 → 短期內出現該規模回檔機率較低")
                        lines.append(
                            "    -【該怎麼做】維持配置、追蹤 risk_score 月變化、突破門檻才動作")
    except Exception:
        pass   # noqa: smoke-allow-pass — 校準資料缺失不阻斷 AI 摘要
    # v18.255：9 章節白話判讀
    try:
        import streamlit as _st  # noqa: PLC0415
        _liq = _st.session_state.get("_macro_liquidity")
        if isinstance(_liq, dict) and _liq:
            lines.append(
                f"- 流動性壓力：{_liq.get('signal', '')} {_liq.get('tier', '')}"
                f"（分數 {_liq.get('value', 0):+.2f}）"
            )
            if _liq.get("top_contrib"):
                _tc = "、".join(
                    f"{b['name']}({b['contrib']:+.2f})" for b in _liq["top_contrib"])
                lines.append(f"  - 主要推升/壓低因子：{_tc}")
            if _liq.get("verdict"):
                lines.append(f"  - 判讀：{str(_liq['verdict'])[:200]}")
        _comp = _st.session_state.get("_macro_compass")
        if isinstance(_comp, dict) and _comp:
            _sahm_v = _comp.get("sahm_latest")
            _adl_v = _comp.get("adl_latest")
            lines.append(
                f"- 景氣循環羅盤：薩姆規則={_sahm_v:+.2f}pp" if _sahm_v is not None
                else "- 景氣循環羅盤：薩姆規則=—"
            )
            if _adl_v is not None:
                lines[-1] += f"、RSP/SPY 廣度={_adl_v:+.2f}%MoM"
            if _comp.get("verdict"):
                lines.append(f"  - 研判：{_comp['verdict']}")
        _items = _st.session_state.get("_macro_23items")
        if isinstance(_items, dict) and _items:
            lines.append(
                f"- 23 項加扣分明細：{_items.get('n_pos', 0)} 項正貢獻 / "
                f"{_items.get('n_neg', 0)} 項負貢獻（共 {_items.get('n_total', 0)}）"
            )
            if _items.get("top_pos"):
                lines.append("  - 最強正貢獻 Top3：" + "；".join(
                    str(r.get("verdict", ""))[:60] for r in _items["top_pos"]))
            if _items.get("top_neg"):
                lines.append("  - 最強負貢獻 Top3：" + "；".join(
                    str(r.get("verdict", ""))[:60] for r in _items["top_neg"]))
        _cap = _st.session_state.get("_macro_capital_line")
        if isinstance(_cap, dict) and _cap:
            _n_ero = _cap.get("n_eroded", 0)
            _n_total_funds = _cap.get("n_funds", 0)
            if _n_total_funds > 0:
                if _n_ero == 0:
                    lines.append(
                        f"- 資本防線：{_n_total_funds} 檔基金全部 TR1Y ≥ 配息率（配息有保障）")
                else:
                    lines.append(
                        f"- 資本防線：⚠️ {_n_ero}/{_n_total_funds} 檔本金侵蝕"
                        f"（TR1Y < 配息率，配息來自本金）"
                    )
                    if _cap.get("eroded_funds"):
                        _ef = "、".join(
                            f"{f['name']}(TR1Y {f['tr1y']:.1f}% vs 配息率 {f['adr']:.1f}%)"
                            for f in _cap["eroded_funds"][:3])
                        lines.append(f"  - 受損基金：{_ef}")
        _ibt = _st.session_state.get("_macro_inv_backtest")
        if isinstance(_ibt, dict) and _ibt and _ibt.get("n_events", 0) > 0:
            _m12 = _ibt.get("median_12m")
            _wr12 = _ibt.get("win_rate_12m")
            _m18 = _ibt.get("median_18m")
            lines.append(
                f"- 倒掛翻正歷史回測：近 30 年 {_ibt['n_events']} 個事件，"
                f"翻正後 12M 中位 {_m12:+.2f}%（勝率 {_wr12:.0f}%）" if _m12 is not None
                else f"- 倒掛翻正歷史回測：近 30 年 {_ibt['n_events']} 個事件"
            )
            if _m18 is not None:
                lines.append(
                    f"  - 18M 中位 {_m18:+.2f}%；歷史意義：翻正為衰退末期，"
                    f"屬股市底部累積區（1990/2000/2008/2020）"
                )
        _sk = _st.session_state.get("_macro_sankey")
        if isinstance(_sk, dict) and _sk and _sk.get("ok"):
            lines.append(
                f"- 總經因果鏈 Sankey：{_sk.get('n_strong_links', 0)} 條強相關因果路徑"
                f"（|corr|≥0.5）"
            )
            if _sk.get("top_strong"):
                _ts = "、".join(
                    f"{s['src']}→{s['tgt']}({s['corr']:+.2f})"
                    for s in _sk["top_strong"])
                lines.append(f"  - 強傳導 Top3：{_ts}")
        _sbt = _st.session_state.get("_macro_subsector_bt")
        if isinstance(_sbt, dict) and _sbt and _sbt.get("alerts"):
            lines.append(
                f"- 細項燈號歷史回測（target={_sbt.get('target')}、"
                f"forward={_sbt.get('forward_months')}M）："
            )
            for _a in _sbt["alerts"][:3]:
                lines.append(f"  - {str(_a)[:120]}")
        _vi = _st.session_state.get("_macro_var_importance")
        if isinstance(_vi, dict) and _vi and _vi.get("top3"):
            _top3_str = "、".join(
                f"{r['name']}(|corr|={r['abs_corr']:.2f}, "
                f"{'同向' if r.get('direction') == '+' else '反向'})"
                for r in _vi["top3"])
            lines.append(
                f"- 變數重要性 Top3（預測 {_vi.get('target')} 在 {_vi.get('lag_months')}M 後變化）："
                f"{_top3_str}"
            )
        _hm = _st.session_state.get("_macro_hot_money")
        if isinstance(_hm, dict) and _hm:
            lines.append(
                f"- 台股熱錢三角交叉（{_hm.get('date', '')}）：{_hm.get('state', '')}"
                f"{'（背離警示）' if _hm.get('is_divergence') else ''}"
            )
            lines.append(
                f"  - 近 {_hm.get('window', 5)}日累計外資 {_hm.get('roll_flow', 0):+.0f} 億、"
                f"台幣升貶 {_hm.get('roll_apprec_pct', 0):+.2f}%"
            )
            if _hm.get("interpretation"):
                lines.append(f"  - 判讀：{_hm['interpretation']}")
    except Exception:
        pass   # noqa: smoke-allow-pass — 章節資料缺失不阻斷 AI 摘要
    headlines = [str(n.get("title", "") or n.get("headline", ""))
                 for n in (news or []) if isinstance(n, dict)][:8]
    sections = ["景氣位階與分數", "資產配置建議", "關鍵總經指標", "系統性風險",
                "領先指標與產業燈號", "校準健檢",
                "流動性壓力", "景氣循環羅盤", "23 項加扣分明細", "資本防線",
                "倒掛翻正歷史回測", "總經因果鏈", "細項燈號回測",
                "變數重要性", "台股熱錢三角交叉",
                "新聞時事"]
    return "\n".join(lines), headlines, sections
