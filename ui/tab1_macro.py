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

import numpy as np
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
    backtest_sub_cycle_lights,
    backtest_turning_points,
    build_macro_sankey_data,
    build_macro_sankey_dynamic,
    calc_macro_phase,
    calc_sub_cycle_lights,
    detect_systemic_risk,
    detect_turning_points,
    fetch_all_indicators,
    rank_macro_drivers,
)
from ui.components.macro_card_edu import MACRO_EDU
from ui.components.mk_clock import render_mk_clock_section
from ui.helpers.macro_helpers import (
    _CATEGORY_MAP,
    calculate_composite_score,
    category_history,
    category_score,
    category_verdict,
    composite_verdict,
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
        phase = st.session_state.phase_info
        sc    = phase["score"];  ph   = phase["phase"];  ph_c = phase["phase_color"]
        alloc = phase["alloc"];  advice = phase.get("advice","")
        rec_p = phase.get("rec_prob")

        # ══ v17.3 內層 Tab：戰情首頁 + 指標教學手冊（§6-6 資訊不藏匿）═══
        tab_main, tab_edu = st.tabs(["📊 戰情首頁", "📖 指標教學手冊"])

        with tab_edu:
            # ══════════════════════════════════════════════════════════
            # v17.0 ⭐ 16 指標教學手冊（含 24M 趨勢圖 + 完整白話教學）
            # ══════════════════════════════════════════════════════════
            # 每張卡：當前值 / Z-Score / 24 個月趨勢圖（含警戒/危險閾值線）
            # 點開「📖 完整教學」可看：白話定義 / 怎麼判讀 / 搭配看誰 /
            # 上游因 / 下游果 / 歷史錨點。AI Prompt 也吃同一份 EDU。
            try:
                from ui.components.macro_card import build_cards_from_indicators, render_macro_card_grid
                from ui.components.macro_card_edu import MACRO_EDU
                # v17.2：移除外層 expander（每張卡片內已有「📖 完整教學」expander，
                # Streamlit 禁止 nested expanders）→ 改用 st.container(border=True) 視覺包覆
                st.markdown("#### 📊 23 指標教學手冊（含趨勢圖 + 完整白話教學｜⭐ = v16.1 高頻替代源）")
                st.caption("⚠️ 黃線=警戒閾值｜紅線=危險閾值｜黃點=當前值｜Z-Score：紅(極端壞)/綠(極端好)/橘(偏離 1.5σ)/藍(正常)")
                # spec: (key, name, unit, decimals, high_is_bad, threshold_warn, threshold_crit)
                _macro_card_spec = [
                    # ① 領先指標
                    ("SAHM",         "薩姆規則（衰退風險）",        "pp", 2,  True,   0.3,   0.5),
                    ("SLOOS",        "SLOOS（銀行放貸意願）",       "%",  1,  True,   0,     20),
                    ("PMI",          "ISM PMI（製造業景氣）",       "",   1,  False,  50,    45),
                    ("LEI",          "⭐ CFNAI 領先指標（PMI 替代）", "",  2,  False,  0,    -0.7),
                    ("YIELD_10Y2Y",  "殖利率利差 10Y-2Y",           "%",  3,  False,  0.5,   0),
                    ("YIELD_10Y3M",  "殖利率利差 10Y-3M",           "%",  2,  False,  0.5,   0),
                    ("PPI",          "PPI 生產者物價(YoY)",          "%",  2,  True,   3,     5),
                    ("COPPER",       "銅博士月漲跌",                 "%",  2,  False,  0,     -5),
                    ("ADL",          "RSP/SPY 市場廣度",             "",   4,  False,  None,  None),
                    ("JOBLESS",      "初領失業金（裁員領先指標）",   "萬",  1,  True,   27,    30),
                    ("CONT_CLAIMS",  "⭐ 持續失業金週頻（失業率替代）","萬",  0,  True,   180,   190),
                    ("CONSUMER_CONF","消費者信心 (Michigan)",         "",   1,  False,  80,    60),
                    ("PERMIT_HOUSING","⭐ 建照核發（房市領先）",       "千",  0,  False,  1500,  1200),
                    # ② 同時 / 落後
                    ("CPI",          "CPI 通膨率（YoY）",            "%",  2,  True,   2.5,   4),
                    ("INFL_EXP_5Y",  "⭐ 5Y 通膨預期日頻（CPI 替代）","%",  2,  True,   2.8,   3.5),
                    ("FED_RATE",     "聯準會利率",                    "%",  2,  True,   2.5,   5),
                    ("UNEMPLOYMENT", "失業率",                         "%",  1,  True,   4.5,   6),
                    # ③ 流動性
                    ("M2",           "M2 貨幣供給（YoY）",            "%",  2,  False,  5,     0),
                    ("M2_WEEKLY",    "⭐ M2 週頻 YoY（M2 替代）",      "%",  2,  False,  5,     0),
                    ("FED_BS",       "Fed 資產負債表（YoY）",         "%",  2,  False,  0,     -5),
                    ("DXY",          "美元指數",                       "",   2,  True,   105,   110),
                    # ④ 金融壓力
                    ("HY_SPREAD",    "HY 信用利差 (OAS)",             "%",  2,  True,   4,     6),
                    ("VIX",          "VIX 恐慌指數",                   "",  1,  True,   22,    30),
                ]
                _cards = build_cards_from_indicators(ind, _macro_card_spec, edu_map=MACRO_EDU)
                # v17.3：tab_edu 一律展開教學區（§6-6 資訊不藏匿）
                for _c in _cards:
                    _c["edu_default_open"] = True
                with st.container(border=True):
                    st.markdown(
                        "<div style='color:#888;font-size:12px;margin:-4px 0 6px'>"
                        "點開每張卡片下方「📖 完整教學」可看：白話定義 / 怎麼判讀 / 搭配看誰 / "
                        "上游因 / 下游果 / 歷史錨點。"
                        "</div>", unsafe_allow_html=True)
                    render_macro_card_grid(_cards, columns=2)
            except Exception as _exc:
                st.warning(f"指標教學手冊載入失敗：{_exc}")
        with tab_main:
            st.markdown("### ① 總經位階評估")
            # ══ v17.3「宏觀健康度總分」字卡（首頁頂部，5 級白話評價）═══
            # 計算：Σ (score × weight)，缺值/NaN 補 0；零快取（CLAUDE.md §4）
            _macro_total = calculate_composite_score(ind)
            _mc_icon, _mc_lvl, _mc_color, _mc_act = composite_verdict(_macro_total)
            st.markdown(
                f"<div style='background:linear-gradient(135deg,#0d1117 0%,#161b22 100%);"
                f"border:2px solid {_mc_color};border-radius:14px;padding:20px 24px;margin:6px 0 14px'>"
                f"<div style='display:flex;align-items:center;gap:18px;flex-wrap:wrap'>"
                f"<div style='font-size:48px;line-height:1'>{_mc_icon}</div>"
                f"<div style='flex:1;min-width:200px'>"
                f"<div style='color:#888;font-size:11px;letter-spacing:2px'>"
                f"宏觀健康度總分 ＝ Σ(指標得分 × 權重)，覆蓋 23 項領先/同時/落後指標</div>"
                f"<div style='color:{_mc_color};font-weight:900;font-size:32px;margin-top:2px'>"
                f"{_mc_lvl}</div></div>"
                f"<div style='text-align:right'>"
                f"<div style='color:#888;font-size:11px'>TOTAL SCORE</div>"
                f"<div style='color:{_mc_color};font-weight:900;font-size:46px;line-height:1'>"
                f"{_macro_total:+.1f}</div></div></div>"
                f"<div style='color:#e6edf3;font-size:13px;line-height:1.6;margin-top:10px;"
                f"padding-top:10px;border-top:1px solid #30363d'>"
                f"📌 <strong>行動建議：</strong>{_mc_act}<br>"
                f"<span style='color:#666;font-size:11px'>"
                f"門檻參考：&gt;+10 極度樂觀 ｜ +5~+10 樂觀 ｜ -5~+5 中性 ｜ -10~-5 悲觀 ｜ &lt;-10 極度悲觀"
                f"</span></div></div>",
                unsafe_allow_html=True,
            )

            # ══ v17.4「四大類別景氣健康度」分組總覽 + 24M 走勢 ═════════════
            # 把 23 項指標按類別匯總當期分數 + 月度 Z-Score 平均，
            # 讓使用者一眼看出哪個類別在改善 / 惡化，而非逐筆 raw data
            from ui.components.macro_card import make_sparkline as _mk_sl_cat
            st.markdown("#### 🗂️ 四大類別景氣健康度（含 24M 歷史趨勢）")
            st.caption(
                "📖 **怎麼看**：每張卡片顯示該類別的「當期總分（Σ score×weight）」+「24M 健康訊號走勢」（已將 high_is_bad 指標反號，"
                "**線往上＝改善、往下＝惡化**）。想看單一指標細節，請拉到下方 Z-Score 矩陣或貢獻明細。"
            )
            _cat_items = list(_CATEGORY_MAP.items())
            for _cat_row_start in range(0, len(_cat_items), 2):
                _cat_cols = st.columns(2)
                for _ci, (_cat_name, _cat_keys) in enumerate(_cat_items[_cat_row_start:_cat_row_start + 2]):
                    with _cat_cols[_ci]:
                        _cs_total, _cs_n, _cs_max = category_score(ind, _cat_keys)
                        _ch_series = category_history(ind, _cat_keys, lookback=24)
                        _z_now = (float(_ch_series.iloc[-1])
                                  if _ch_series is not None and len(_ch_series) else None)
                        # 近 6 月平均 vs 全期平均：判斷趨勢方向
                        if _ch_series is not None and len(_ch_series) >= 6:
                            _delta = float(_ch_series.tail(6).mean() - _ch_series.mean())
                        else:
                            _delta = 0.0
                        _vd_icon, _vd_color, _vd_text = category_verdict(_z_now, _delta)
                        # 卡片標頭
                        st.markdown(
                            f"<div style='background:#11161e;border:1px solid {_vd_color};"
                            f"border-radius:10px 10px 0 0;padding:10px 14px;margin:8px 0 0'>"
                            f"<div style='display:flex;justify-content:space-between;align-items:baseline'>"
                            f"<span style='font-size:14px;color:#e6edf3;font-weight:700'>"
                            f"{_cat_name}（{_cs_n}/{_cs_max} 項）</span>"
                            f"<span style='font-size:18px;color:{_vd_color};font-weight:900'>"
                            f"{_vd_icon} {_cs_total:+.1f}</span>"
                            f"</div></div>",
                            unsafe_allow_html=True,
                        )
                        # 24M 趨勢線
                        _cat_fig = _mk_sl_cat(
                            _ch_series, threshold_warn=-0.5, threshold_crit=-1.5,
                            high_is_bad=False, lookback=24, height=90,
                        ) if _ch_series is not None else None
                        if _cat_fig is not None:
                            st.plotly_chart(_cat_fig, use_container_width=True,
                                            config={"displayModeBar": False})
                        else:
                            st.caption("⚠️ 24M 歷史資料不足，無法繪製走勢")
                        st.caption(f"💡 {_vd_text}")
            st.markdown("---")

            # ══ v16.0「今日市場結論」hero 卡（結論先行，新人秒懂）═══════
            # 設計原則：把零散的 VIX/SAHM/SLOOS/利差/HY/Fed BS/新聞 等指標
            # 一鍵綜合成「風險等級 + 行動建議」一句話判讀。
            # v17.1：加入 FED_BS（QT/QE 風向球）平衡「壞消息偵測器」訊號，
            #        讓 Gemini AI 能正確區分「事件型恐慌」vs「流動性收緊型熊市」。
            _vix_v0     = (ind.get("VIX") or {}).get("value")
            _spr_v0     = (ind.get("YIELD_10Y2Y") or {}).get("value")
            _hy_v0      = (ind.get("HY_SPREAD") or {}).get("value")
            _sahm_v0    = float((ind.get("SAHM")  or {}).get("value") or 0)
            _sloos_v0   = float((ind.get("SLOOS") or {}).get("value") or 0)
            _fed_bs_v0  = (ind.get("FED_BS") or {}).get("value")
            # v16.1：高頻替代源納入評分（INFL_EXP_5Y 補通膨即時面，LEI 補 PMI 缺失）
            _infl_exp_v0 = (ind.get("INFL_EXP_5Y") or {}).get("value")
            _pmi_v0      = (ind.get("PMI") or {}).get("value")
            _lei_v0      = (ind.get("LEI") or {}).get("value")
            _srd0       = st.session_state.get("systemic_risk_data") or {}
            _news_lvl   = _srd0.get("risk_level", "LOW")

            _risk_pts = 0
            _risk_reasons = []
            if _vix_v0 is not None:
                if _vix_v0 > 30:   _risk_pts += 2; _risk_reasons.append(f"VIX={_vix_v0:.1f}（市場恐慌）")
                elif _vix_v0 > 22: _risk_pts += 1; _risk_reasons.append(f"VIX={_vix_v0:.1f}（情緒緊張）")
            if _spr_v0 is not None:
                if _spr_v0 < -0.3: _risk_pts += 2; _risk_reasons.append(f"殖利率深度倒掛{_spr_v0:.2f}%")
                elif _spr_v0 < 0:  _risk_pts += 1; _risk_reasons.append(f"殖利率倒掛{_spr_v0:.2f}%")
            if _hy_v0 is not None and _hy_v0 > 6:
                _risk_pts += 2; _risk_reasons.append(f"HY 利差{_hy_v0:.2f}%（信用走擴）")
            if _sahm_v0 >= 0.5:
                _risk_pts += 2; _risk_reasons.append(f"薩姆衰退觸發 {_sahm_v0:.2f}pp")
            if _sloos_v0 > 20:
                _risk_pts += 1; _risk_reasons.append(f"銀行緊縮放貸 {_sloos_v0:.0f}%")
            # Fed 資產負債表 YoY：衡量流動性面，補上「QT 抽水」這個鈍刀風險
            if _fed_bs_v0 is not None:
                if _fed_bs_v0 < -5: _risk_pts += 2; _risk_reasons.append(f"Fed 資產負債表 YoY={_fed_bs_v0:.1f}%（大幅縮表 QT）")
                elif _fed_bs_v0 < 0: _risk_pts += 1; _risk_reasons.append(f"Fed 資產負債表 YoY={_fed_bs_v0:.1f}%（緩慢縮表）")
            # v16.1 ⭐ 5Y 通膨預期（日頻）：CPI 月度延遲時的即時通膨溫度計
            if _infl_exp_v0 is not None:
                if _infl_exp_v0 > 3.5: _risk_pts += 2; _risk_reasons.append(f"5Y 通膨預期={_infl_exp_v0:.2f}%（市場不信任 Fed）")
                elif _infl_exp_v0 > 3.0: _risk_pts += 1; _risk_reasons.append(f"5Y 通膨預期={_infl_exp_v0:.2f}%（升溫）")
            # v16.1 ⭐ CFNAI 領先指標：僅在 PMI 缺失時啟用（fallback 不重複評分）
            # CFNAI 為 z-score 標準化值（平均=0、std=1），閾值 -0.7 為衰退門檻
            if _pmi_v0 is None and _lei_v0 is not None:
                if _lei_v0 < -0.7: _risk_pts += 2; _risk_reasons.append(f"CFNAI={_lei_v0:+.2f}（PMI 缺失，領先指標重度衰退）")
                elif _lei_v0 < 0:  _risk_pts += 1; _risk_reasons.append(f"CFNAI={_lei_v0:+.2f}（PMI 缺失，領先指標低於趨勢）")
            if _news_lvl == "HIGH":
                _risk_pts += 2; _risk_reasons.append("新聞系統性風險（HIGH）")
            elif _news_lvl == "MEDIUM":
                _risk_pts += 1; _risk_reasons.append("新聞系統性風險（MEDIUM）")

            # 風險閾值：總分上限 14（VIX2 + 利差2 + HY2 + SAHM2 + SLOOS1 + FedBS2 + News2 + InflExp2 + LEI2 共 17，
            #              扣除 LEI 與 PMI 互斥 ≈ 14 上限）
            if _risk_pts >= 6:
                _hero_lvl, _hero_icon, _hero_color, _hero_bg = "極高", "🔴", "#f44336", "#2a0a0a"
                _hero_action = "**保留 30% 以上現金**，停止衛星基金扣款，核心部位轉防守型（投資等級債 / 全球均衡）"
            elif _risk_pts >= 3:
                _hero_lvl, _hero_icon, _hero_color, _hero_bg = "偏高", "🟡", "#ff9800", "#2a1f00"
                _hero_action = "**保留 15% 現金**，衛星部位設停利，新申購放慢節奏分批進場"
            else:
                _hero_lvl, _hero_icon, _hero_color, _hero_bg = "穩健", "🟢", "#00c853", "#0a2a0a"
                _hero_action = "**現金水位 5%** 即可，可正常定期定額；建議每週重整一次儀表板觀察拐點"

            _reasons_html = "、".join(_risk_reasons) if _risk_reasons else "目前無顯著警報訊號"
            st.markdown(
                f"<div style='background:{_hero_bg};border:2px solid {_hero_color};border-radius:14px;padding:18px 22px;margin:10px 0 14px'>"
                f"<div style='display:flex;align-items:center;gap:12px;margin-bottom:8px'>"
                f"<span style='font-size:34px'>{_hero_icon}</span>"
                f"<div><div style='color:#888;font-size:12px;letter-spacing:2px'>今日市場風險評估（自動綜合 VIX / 殖利率 / 信用利差 / 薩姆 / SLOOS / Fed BS / 5Y 通膨預期 / CFNAI / 新聞）</div>"
                f"<div style='color:{_hero_color};font-weight:800;font-size:24px'>目前市場風險：{_hero_lvl}</div></div></div>"
                f"<div style='color:#e6edf3;font-size:14px;line-height:1.7;margin-top:6px'>"
                f"📌 <strong>行動建議：</strong>{_hero_action}<br>"
                f"🔍 <strong>觸發訊號：</strong>{_reasons_html}（綜合分數 {_risk_pts}/14）</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
            # v17.0: toggle 已移除，下方一律展示完整指標卡片 + Z-Score 矩陣 + 歷史時序
            st.caption("ℹ️ 戰情首頁：總分字卡 → 風險評估 → Z-Score 矩陣 → 風險溫度計 → 戰情室。完整指標教學請切到右側「📖 指標教學手冊」分頁。")


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
                st.markdown("### ② 🎯 全域導航塔（戰情室）")
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


            # ══════════════════════════════════════════════════
            # L2 歷史危機對照圖（L2 + L3 顯示）
            # ══════════════════════════════════════════════════
            if _show_l2_plus:
                with st.expander("📈 L2 景氣循環歷史對照圖（危機紅區 × 指標趨勢）", expanded=True):
                    _sahm_s  = (ind.get("SAHM")  or {}).get("series")
                    _sloos_s = (ind.get("SLOOS") or {}).get("series")
                    _adl_s   = (ind.get("ADL")   or {}).get("series")
                    _l2_has  = any(s is not None and len(s) >= 5
                                   for s in [_sahm_s, _sloos_s, _adl_s])
                    if _l2_has:
                        import pandas as _pd_l2
                        from plotly.subplots import make_subplots as _msp_l2
                        _l2fig = _msp_l2(specs=[[{"secondary_y": True}]])

                        # Sahm Rule 主線
                        if _sahm_s is not None and len(_sahm_s) >= 5:
                            _sh = _sahm_s if isinstance(_sahm_s, _pd_l2.Series) else _pd_l2.Series(_sahm_s)
                            _sh = _sh.dropna().tail(120)
                            _l2fig.add_trace(go.Scatter(
                                x=_sh.index, y=_sh.values, name="薩姆規則 (pp)",
                                line={"color": "#64b5f6", "width": 2},
                                hovertemplate="Sahm: %{y:.2f}pp<extra></extra>"),
                                secondary_y=False)
                            # 0.5 觸發線
                            _l2fig.add_hline(y=0.5, line_dash="dash",
                                             line_color="#f44336", opacity=0.6,
                                             annotation_text="衰退觸發線 0.5",
                                             annotation_font_color="#f44336",
                                             secondary_y=False)

                        # SLOOS 副軸
                        if _sloos_s is not None and len(_sloos_s) >= 5:
                            _sl = _sloos_s if isinstance(_sloos_s, _pd_l2.Series) else _pd_l2.Series(_sloos_s)
                            _sl = _sl.dropna().tail(120)
                            _l2fig.add_trace(go.Scatter(
                                x=_sl.index, y=_sl.values, name="SLOOS (%)",
                                line={"color": "#ff9800", "width": 2, "dash": "dot"},
                                hovertemplate="SLOOS: %{y:.1f}%<extra></extra>"),
                                secondary_y=True)

                        # 歷史危機紅色陰影
                        _crises = [
                            ("2007-12-01", "2009-06-01", "2008 金融海嘯"),
                            ("2020-02-01", "2020-06-01", "2020 COVID"),
                            ("2022-01-01", "2022-12-01", "2022 升息週期"),
                        ]
                        for _cs, _ce, _cn in _crises:
                            _l2fig.add_vrect(
                                x0=_cs, x1=_ce,
                                fillcolor="rgba(244,67,54,0.12)",
                                line_width=0,
                                annotation_text=_cn,
                                annotation_position="top left",
                                annotation_font={"size": 9, "color": "#f44336"})

                        _l2fig.update_layout(
                            paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
                            font_color="#e6edf3", height=320,
                            margin=dict(t=30, b=20, l=50, r=50),
                            legend=dict(orientation="h", y=-0.15,
                                        font={"size": 10}),
                            hovermode="x unified")
                        _l2fig.update_yaxes(title_text="薩姆規則 (pp)",
                                            gridcolor="#21262d", secondary_y=False)
                        _l2fig.update_yaxes(title_text="SLOOS (%)",
                                            gridcolor="#21262d", secondary_y=True)
                        _l2fig.update_xaxes(gridcolor="#21262d")
                        st.plotly_chart(_l2fig, use_container_width=True)
                        st.caption("🔴 紅色陰影 = 歷史衰退/危機區間，藍線 = 薩姆規則，橘虛線 = SLOOS 銀行放貸標準")
                    else:
                        st.info("📡 請先載入總經資料以顯示歷史對照圖")

            # ── L2 視角到此結束，L3 繼續顯示完整儀表板 ──────────────────
            if not _show_l2_plus:
                pass  # L1 只看 Gauge + 清單，不繼續渲染下方 L3 內容

            # ── 景氣時鐘 + 天氣 + 配置 ──（L2/L3）──────────────────────
            if _show_l2_plus:
                _ind_dates = [v.get("date","") for v in ind.values() if isinstance(v,dict) and v.get("date")]
                if _ind_dates:
                    st.caption(f"📅 指標資料截至 {max(_ind_dates)}（FRED 有發布時差，部分指標為上月）")

                PHASES = ["衰退","復甦","擴張","高峰"]
                PCOLORS = {"衰退":"#ff9800","復甦":"#64b5f6","擴張":"#00c853","高峰":"#f44336"}
                nxt_ph = phase.get("next_phase", ph)
                t_arrow = phase.get("trend_arrow","→"); t_label = phase.get("trend_label","持穩")
                t_color = phase.get("trend_color","#888888"); nxt_color = PCOLORS.get(nxt_ph,"#888")

                c1, c2, c3 = st.columns([1.2, 1, 1.5])
                with c1:
                    infl_html = (f"<div style='background:#0d1117;border:1px dashed {t_color};border-radius:8px;padding:6px 10px;margin-top:10px;text-align:center'>"
                                 f"<div style='color:#888;font-size:10px;margin-bottom:4px'>拐點偵測</div>"
                                 f"<div style='font-size:15px;font-weight:800;color:{ph_c}'>{ph}</div>"
                                 f"<div style='font-size:18px;color:{t_color};margin:2px 0'>{t_arrow}</div>"
                                 f"<div style='font-size:15px;font-weight:800;color:{nxt_color}'>{'（持穩）' if nxt_ph==ph else nxt_ph}</div>"
                                 f"<div style='color:{t_color};font-size:10px;margin-top:4px'>{t_label}</div></div>")
                    st.markdown(f"<div style='background:#0d1117;border:2px solid {ph_c};border-radius:14px;padding:18px;text-align:center'>"
                                f"<div style='color:#888;font-size:12px;letter-spacing:2px'>景氣時鐘</div>"
                                f"<div style='color:{ph_c};font-size:42px;font-weight:900;margin:6px 0'>{ph}</div>"
                                f"<div style='display:flex;justify-content:center;gap:8px;margin-top:8px'>"
                                + "".join(f"<span style='background:{PCOLORS[p] if p==ph else '#1a1a2e'};color:{'#fff' if p==ph else '#555'};padding:3px 10px;border-radius:20px;font-size:11px'>{p}</span>" for p in PHASES)
                                + f"</div>{infl_html}</div>", unsafe_allow_html=True)
                with c2:
                    bar = "█"*int(sc) + "░"*(10-int(sc))
                    rec_html = ""
                    if rec_p is not None:
                        rc = "#f44336" if rec_p>60 else ("#ff9800" if rec_p>35 else "#00c853")
                        rec_html = f"<div style='margin-top:8px'><div style='color:#888;font-size:11px'>衰退機率</div><div style='color:{rc};font-size:22px;font-weight:800'>{rec_p:.0f}%</div></div>"
                    _w_icon  = phase.get("weather_icon","⛅"); _w_label = phase.get("weather_label","多雲")
                    _w_color = phase.get("weather_color","#90caf9"); _w_alloc = phase.get("weather_alloc_str","")
                    _wbg = "linear-gradient(135deg,#1a1000,#2a1f00)" if "晴" in _w_label else "linear-gradient(135deg,#0d1a2a,#0d1117)"
                    st.markdown(f"<div style='background:{_wbg};border:2px solid {_w_color};border-radius:14px;padding:18px;text-align:center'>"
                                f"<div style='color:#888;font-size:11px;letter-spacing:2px;margin-bottom:4px'>總經天氣預報</div>"
                                f"<div style='font-size:48px;line-height:1.1;margin:4px 0'>{_w_icon}</div>"
                                f"<div style='color:{_w_color};font-size:22px;font-weight:900'>{_w_label}</div>"
                                f"<div style='color:#ccc;font-size:11px;margin:6px 0;padding:4px 8px;background:#1a1a1a;border-radius:6px'>建議：{_w_alloc}</div>"
                                f"<div style='color:{ph_c};font-size:13px;font-weight:700;margin-top:4px'>Macro Score {sc}/10</div>"
                                f"<div style='color:{ph_c};font-size:10px;letter-spacing:1px'>{bar}</div>"
                                f"{rec_html}</div>", unsafe_allow_html=True)
                with c3:
                    alloc_bars = "".join(
                        f"<div style='display:flex;align-items:center;margin:5px 0'>"
                        f"<div style='color:#ccc;width:38px;font-size:13px'>{k}</div>"
                        f"<div style='flex:1;background:#161b22;border-radius:4px;height:14px;margin:0 8px'>"
                        f"<div style='background:{'#2196f3' if k=='股票' else '#ff9800' if k=='債券' else '#78909c'};width:{v}%;height:100%;border-radius:4px'></div></div>"
                        f"<div style='color:{'#2196f3' if k=='股票' else '#ff9800' if k=='債券' else '#78909c'};font-weight:700;font-size:13px'>{v}%</div></div>"
                        for k,v in alloc.items())
                    st.markdown(f"<div style='background:#0d1117;border:1px solid #30363d;border-radius:14px;padding:18px'>"
                                f"<div style='color:#888;font-size:12px;letter-spacing:2px;margin-bottom:10px'>AI 建議配置</div>"
                                f"{alloc_bars}"
                                f"<div style='color:#69f0ae;font-size:11px;margin-top:8px;line-height:1.6'>{advice}</div>"
                                f"</div>", unsafe_allow_html=True)

            # ── 風險警示燈號 + 系統性風險 + 美林時鐘（L2/L3）────────────
            if _show_l2_plus:
                _vix_v   = (ind.get("VIX") or {}).get("value")
                _spr_v   = (ind.get("YIELD_10Y2Y") or {}).get("value")
                _hy_v    = (ind.get("HY_SPREAD") or {}).get("value")
                _risk    = 0; _msgs = []
                if _vix_v is not None:
                    if _vix_v > 30:  _risk = max(_risk,2); _msgs.append(f"VIX={_vix_v:.1f}>30（市場恐慌）")
                    elif _vix_v > 22: _risk = max(_risk,1); _msgs.append(f"VIX={_vix_v:.1f}偏高")
                if _spr_v is not None:
                    if _spr_v < -0.3: _risk = max(_risk,2); _msgs.append(f"殖利率深度倒掛{_spr_v:.3f}%")
                    elif _spr_v < 0:  _risk = max(_risk,1); _msgs.append(f"殖利率倒掛{_spr_v:.3f}%")
                if _hy_v is not None and _hy_v > 6:
                    _risk = max(_risk,2); _msgs.append(f"HY利差={_hy_v:.2f}%>6%（信用風險）")
                if _risk == 2 and _msgs:
                    st.error(f"🚨 **總經高風險** | {'　|　'.join(_msgs)}\n\n⚠️ 建議提高投資等級債券基金水位，核心部位 ≥80%")
                elif _risk == 1 and _msgs:
                    st.info(f"🟡 市場溫度偏高：{'　|　'.join(_msgs)}　→ 建議：衛星部位設停利、新申購分批進場")

                # ── 系統性風險偵測（新聞 NLP）──
                _srd = st.session_state.get("systemic_risk_data")
                if _srd:
                    _rl  = _srd.get("risk_level","LOW")
                    _rs  = _srd.get("risk_score",0)
                    _rc  = _srd.get("risk_color","#888")
                    _ri  = _srd.get("risk_icon","⬜")
                    _adv = _srd.get("advice","")
                    _trig = _srd.get("triggered",[])
                    _srd_bg = {"HIGH":"#2a0a0a","MEDIUM":"#2a1f00","LOW":"#0a1a0a"}.get(_rl,"#111")
                    _srd_border = {"HIGH":"#f44336","MEDIUM":"#ff9800","LOW":"#00c853"}.get(_rl,"#30363d")
                    _trig_html = ""
                    if _trig:
                        _trig_html = "<div style='margin-top:6px;display:flex;flex-wrap:wrap;gap:4px'>"
                        for t in _trig[:6]:
                            _trig_html += f"<span style='background:#1a1a2e;color:{_rc};border:1px solid {_rc};padding:2px 8px;border-radius:12px;font-size:11px'>#{t['keyword']}({t['sub_score']})</span>"
                        _trig_html += "</div>"
                    st.markdown(
                        f"<div style='background:{_srd_bg};border:1px solid {_srd_border};border-radius:10px;padding:12px 16px;margin:8px 0'>"
                        f"<div style='display:flex;align-items:center;gap:10px'>"
                        f"<span style='font-size:24px'>{_ri}</span>"
                        f"<div><div style='color:#888;font-size:11px'>新聞系統性風險偵測</div>"
                        f"<div style='color:{_rc};font-weight:800;font-size:15px'>{_rl} （評分 {_rs}）</div></div>"
                        f"<div style='flex:1;text-align:right;color:#ccc;font-size:11px'>{_adv}</div></div>"
                        f"{_trig_html}</div>", unsafe_allow_html=True)

                # ── T1: 事件驅動衝擊警報卡 ──────────────────────────────────
                _news_items   = st.session_state.get("news_items", [])
                _pf_loaded_t1 = [f for f in st.session_state.portfolio_funds if f.get("loaded")]
                _holdings_ctx = ""
                for _pf_f in _pf_loaded_t1[:3]:
                    _h_raw = (_pf_f.get("moneydj_raw") or {}).get("holdings") or {}
                    _h_top = _h_raw.get("top_holdings") or []
                    if _h_top:
                        _holdings_ctx += f"{_pf_f.get('code','')}: " + ", ".join(
                            h.get("name","")[:12] for h in _h_top[:5]) + "\n"
                _ev_result = st.session_state.get("event_impact_result", "")
                if _news_items and GEMINI_KEY and (_srd.get("risk_level","LOW") != "LOW" if _srd else False):
                    if st.button("⚡ 執行事件衝擊分析（新聞×持股交叉比對）", key="btn_event_impact"):
                        with st.spinner("分析中..."):
                            _ev_result = event_impact_analysis(
                                GEMINI_KEY, _news_items, _holdings_ctx,
                                ", ".join(f.get("code","") for f in _pf_loaded_t1[:5]))
                            st.session_state["event_impact_result"] = _ev_result
                if _ev_result:
                    st.markdown(
                        f"<div style='background:#1a0a2a;border:2px solid #ce93d8;border-radius:10px;"
                        f"padding:12px 16px;margin:8px 0'>"
                        f"<div style='color:#ce93d8;font-weight:800;font-size:13px;margin-bottom:6px'>"
                        f"⚡ 事件衝擊分析（T1）</div>"
                        f"<div style='color:#e8d5f0;font-size:12px'>{_ev_result.replace(chr(10),'<br>')}</div>"
                        f"</div>", unsafe_allow_html=True)

                # ── 美林時鐘老師語音卡片（V3-2 Core Protocol v3.0）──────────
                _ml_phase_data = {
                    "衰退": {
                        "icon": "❄️", "color": "#64b5f6",
                        "fund_type": "長天期美債基金、高評級投資等級債",
                        "teacher": "策略1：衰退期現金為王，優先配置高評級債券基金。新手最常在此時恐慌贖回，老手反而逢低累積單位數，等景氣復甦自然回漲。",
                        "action": "核心佔比 ≥80%，衛星暫停加碼，開啟定期定額迎接復甦",
                    },
                    "復甦": {
                        "icon": "🌱", "color": "#69f0ae",
                        "fund_type": "市值型 ETF、中小型股基金、成長型股票基金",
                        "teacher": "策略2：復甦期是佈局成長型基金的黃金視窗。PMI 底部翻揚、殖利率倒掛收斂，是最佳進場訊號。避免死守純防禦型基金，錯過早期漲幅。",
                        "action": "積極佈局：股票型基金提升至 60%，衛星佈局中小型或科技主題",
                    },
                    "擴張": {
                        "icon": "🌤️", "color": "#ffcc02",
                        "fund_type": "均衡配置；科技/主題衛星佈局持續追蹤趨勢",
                        "teacher": "策略1：擴張期繼續持有，讓時間複利發揮。定期定額勿停扣，配息收入持續再投入衛星資產，以息養股最佳時機。",
                        "action": "持有核心配息資產，衛星設停利 +15%，注意 VIX 是否異常低",
                    },
                    "高峰": {
                        "icon": "🔥", "color": "#f44336",
                        "fund_type": "核心配息基金（降低衛星部位，落袋為安）",
                        "teacher": "策略2：高峰期居高思危！PMI 高檔鈍化、VIX 極低往往是反轉前兆。老手此時將衛星獲利轉回核心穩健配息基金，不追高。",
                        "action": "衛星部位停利出場，核心佔比回升至 ≥75%，現金水位預備",
                    },
                }
                _ml_d = _ml_phase_data.get(ph, {
                    "icon": "⛅", "color": "#888",
                    "fund_type": "均衡配置",
                    "teacher": "景氣位階轉換中，維持核心/衛星均衡配置。",
                    "action": "持續定期定額，等待景氣訊號明確後再調整",
                })
                _ml_vix_alert = ""
                if _vix_v is not None and _vix_v > 30:
                    _ml_vix_alert = (
                        f"<div style='border-left:3px solid #69f0ae;background:#0a1a0a;"
                        f"padding:8px 12px;margin-top:8px;border-radius:0 6px 6px 0;font-size:12px'>"
                        f"⚡ <b style='color:#69f0ae'>VIX={_vix_v:.1f} 超過 30（市場恐慌）</b>"
                        f"——策略1「左側交易」訊號，核心資產分批加碼時機！</div>"
                    )
                st.markdown(
                    f"<div style='background:linear-gradient(135deg,#0d1117,#0d1a0d);"
                    f"border:2px solid {_ml_d['color']};border-radius:12px;"
                    f"padding:16px 20px;margin:12px 0'>"
                    f"<div style='display:flex;align-items:center;gap:10px;margin-bottom:10px'>"
                    f"<span style='font-size:28px'>{_ml_d['icon']}</span>"
                    f"<div>"
                    f"<div style='color:#888;font-size:11px;letter-spacing:1px'>📐 美林時鐘 · 策略語音</div>"
                    f"<div style='color:{_ml_d['color']};font-weight:800;font-size:16px'>"
                    f"{ph} 期 → 適合：{_ml_d['fund_type']}</div>"
                    f"</div></div>"
                    f"<div style='color:#ccc;font-size:13px;line-height:1.7;border-left:3px solid {_ml_d['color']};"
                    f"padding-left:12px'>{_ml_d['teacher']}</div>"
                    f"<div style='margin-top:10px;background:#1a1f2e;border-radius:6px;padding:8px 12px;"
                    f"font-size:12px;color:#e6edf3'>🎯 <b>本階段行動建議</b>：{_ml_d['action']}</div>"
                    f"{_ml_vix_alert}"
                    f"</div>",
                    unsafe_allow_html=True)

            # ── 宏觀風險溫度計 + 景氣循環羅盤 + AI（僅 L3）──────────────
            import pandas as _pd_mac
            def _safe_series(s):
                if s is None: return None
                try:
                    if not isinstance(s, _pd_mac.Series): s = _pd_mac.Series(s)
                    return s.dropna().tail(60)
                except Exception: return None

            _pmi_s   = (ind.get("PMI")         or {}).get("series")
            _spr_s   = (ind.get("YIELD_10Y2Y") or {}).get("series")
            _vix_s   = (ind.get("VIX")         or {}).get("series")
            _has_chart = any(
                s is not None and hasattr(s, "__len__") and len(s) >= 4
                for s in [_pmi_s, _spr_s, _vix_s])
            if _has_chart and _show_l3:
                # v17.2：拆掉多軸複合圖 → 4 張「左 sparkline 右白話解說」獨立卡
                with st.expander("🌡️ 宏觀風險溫度計（4 大關鍵指標分軌觀察）", expanded=True):
                    from ui.components.macro_card import make_sparkline as _mk_sl
                    _score_val = sc

                    _spr_clean = _safe_series(_spr_s)
                    _vix_clean = _safe_series(_vix_s)
                    _pmi_clean = _safe_series(_pmi_s)

                    # ── Card 1：各指標得分 bar ─────────────────────────────
                    _c1l, _c1r = st.columns([1.5, 1])
                    with _c1l:
                        st.markdown("**📊 各指標當前得分**")
                        _ind_rows = [(k, v) for k, v in ind.items()
                                     if isinstance(v, dict) and v.get("score") is not None]
                        if _ind_rows:
                            _bn = [v.get("name", k)[:10] for k, v in _ind_rows]
                            _bs = [float(v.get("score", 0)) for _, v in _ind_rows]
                            _bc = ["#00c853" if s > 0 else ("#f44336" if s < 0 else "#888")
                                   for s in _bs]
                            _bar = go.Figure(go.Bar(
                                x=_bn, y=_bs, marker_color=_bc,
                                hovertemplate="%{x}: %{y:+.2f}<extra></extra>"))
                            _bar.add_hline(y=0, line_color="#555", line_width=1)
                            _bar.update_layout(
                                height=200, margin=dict(t=4, b=40, l=4, r=4),
                                paper_bgcolor="rgba(0,0,0,0)",
                                plot_bgcolor="rgba(0,0,0,0)",
                                showlegend=False,
                                xaxis=dict(showgrid=False, tickangle=-45,
                                           tickfont=dict(size=9), fixedrange=True),
                                yaxis=dict(showgrid=False, zeroline=False,
                                           fixedrange=True))
                            st.plotly_chart(_bar, use_container_width=True,
                                            config={"displayModeBar": False})
                        else:
                            st.caption("尚無指標得分資料")
                    with _c1r:
                        if _score_val >= 8:
                            _q_lbl, _q_act = "🔥 擴張/高峰期", "股 40% / 債 40% / 現金 20%"
                        elif _score_val >= 5:
                            _q_lbl, _q_act = "🌱 復甦/擴張期", "股 60% / 債 30% / 現金 10%"
                        elif _score_val >= 3:
                            _q_lbl, _q_act = "🍂 衰退轉復甦",  "股 40% / 債 40% / 現金 20%"
                        else:
                            _q_lbl, _q_act = "❄️ 衰退期",      "股 20% / 債 50% / 現金 30%"
                        st.markdown(
                            "**怎麼看？**　綠柱＝該指標當前對景氣加分（健康）、紅柱＝扣分（拖累）。"
                            "棒越長代表貢獻越大。\n\n"
                            f"**目前讀數**　總分 **{_score_val}/14**，象限：**{_q_lbl}**\n\n"
                            f"**AI 結論**　建議配置：{_q_act}")
                    st.divider()

                    # ── Card 2：10Y-2Y 利差 ───────────────────────────────
                    _c2l, _c2r = st.columns([1.5, 1])
                    with _c2l:
                        st.markdown("**📈 10Y-2Y 殖利率利差**")
                        _spr_fig = _mk_sl(_spr_clean, threshold_warn=0.5,
                                          threshold_crit=0, high_is_bad=False,
                                          lookback=60, height=180)
                        if _spr_fig is not None:
                            st.plotly_chart(_spr_fig, use_container_width=True,
                                            config={"displayModeBar": False})
                        else:
                            st.caption("📡 資料載入中或筆數不足…")
                    with _c2r:
                        _spr_v = (float(_spr_clean.iloc[-1])
                                  if _spr_clean is not None and len(_spr_clean) else None)
                        if _spr_v is None:
                            _spr_judge = "—"
                        elif _spr_v < 0:
                            _spr_judge = f"🔴 倒掛 {_spr_v:.3f}%（衰退預警）"
                        elif _spr_v < 0.5:
                            _spr_judge = f"🟡 偏窄 {_spr_v:.3f}%（趨平）"
                        else:
                            _spr_judge = f"🟢 健康正斜率 {_spr_v:.3f}%"
                        st.markdown(
                            "**怎麼看？**　長期利率減短期利率。"
                            "**跌破 0% 紅虛線＝倒掛**，歷史上 12-18 個月後常見衰退。\n\n"
                            f"**目前讀數**　{_spr_judge}")
                    st.divider()

                    # ── Card 3：VIX 恐慌指數 ──────────────────────────────
                    _c3l, _c3r = st.columns([1.5, 1])
                    with _c3l:
                        st.markdown("**😱 VIX 恐慌指數**")
                        _vix_fig = _mk_sl(_vix_clean, threshold_warn=22,
                                          threshold_crit=30, high_is_bad=True,
                                          lookback=60, height=180)
                        if _vix_fig is not None:
                            st.plotly_chart(_vix_fig, use_container_width=True,
                                            config={"displayModeBar": False})
                        else:
                            st.caption("📡 資料載入中或筆數不足…")
                    with _c3r:
                        _vix_v = (float(_vix_clean.iloc[-1])
                                  if _vix_clean is not None and len(_vix_clean) else None)
                        if _vix_v is None:
                            _vix_judge = "—"
                        elif _vix_v >= 30:
                            _vix_judge = f"🔴 恐慌 {_vix_v:.1f}（逢低分批買點）"
                        elif _vix_v >= 22:
                            _vix_judge = f"🟡 偏緊 {_vix_v:.1f}"
                        elif _vix_v < 15:
                            _vix_judge = f"🟠 過樂觀 {_vix_v:.1f}（小心反轉）"
                        else:
                            _vix_judge = f"🟢 平靜 {_vix_v:.1f}"
                        st.markdown(
                            "**怎麼看？**　市場恐慌指數：>30 重度恐慌、22-30 偏緊張、<15 過樂觀。"
                            "**極度恐慌反而是逢低買點**。\n\n"
                            f"**目前讀數**　{_vix_judge}")
                    st.divider()

                    # ── Card 4：PMI 製造業 ────────────────────────────────
                    _c4l, _c4r = st.columns([1.5, 1])
                    with _c4l:
                        st.markdown("**🏭 ISM PMI 製造業景氣**")
                        _pmi_fig = _mk_sl(_pmi_clean, threshold_warn=50,
                                          threshold_crit=45, high_is_bad=False,
                                          lookback=60, height=180)
                        if _pmi_fig is not None:
                            st.plotly_chart(_pmi_fig, use_container_width=True,
                                            config={"displayModeBar": False})
                        else:
                            st.caption("📡 資料載入中或筆數不足…")
                    with _c4r:
                        _pmi_v_card = (float(_pmi_clean.iloc[-1])
                                       if _pmi_clean is not None and len(_pmi_clean) else None)
                        if _pmi_v_card is None:
                            _pmi_judge = "—"
                        elif _pmi_v_card >= 55:
                            _pmi_judge = f"🟢 強擴張 {_pmi_v_card:.1f}"
                        elif _pmi_v_card >= 50:
                            _pmi_judge = f"🟢 擴張 {_pmi_v_card:.1f}"
                        elif _pmi_v_card >= 45:
                            _pmi_judge = f"🟡 收縮 {_pmi_v_card:.1f}（庫存調整）"
                        else:
                            _pmi_judge = f"🔴 深度收縮 {_pmi_v_card:.1f}"
                        st.markdown(
                            "**怎麼看？**　ISM 製造業景氣指數。"
                            "**50 是榮枯線**：>50 擴張、<50 收縮、<45 多半已陷衰退。\n\n"
                            f"**目前讀數**　{_pmi_judge}")
                    st.divider()

                    # ── 複合風險溫度計（V4 精準策略引擎）────────────────────
                    from services.precision_service import PrecisionStrategyEngine as _PSE, risk_score_gauge_html as _rs_html
                    _pse = _PSE()
                    _df_macro = _pse.build_macro_df(ind)
                    _risk_score = _pse.calculate_composite_risk(_df_macro)
                    _risk_strat = _pse.risk_score_strategy(_risk_score)
                    st.markdown(_rs_html(_risk_score, _risk_strat), unsafe_allow_html=True)

                    # 三指標最新值 vs 前期 (metric 卡)
                    if not _df_macro.empty and len(_df_macro) >= 2:
                        _latest = _df_macro.iloc[-1]
                        _prev   = _df_macro.iloc[-2]
                        _mc1, _mc2, _mc3 = st.columns(3)
                        with _mc1:
                            st.metric("VIX 恐慌指數",
                                      f"{_latest['VIX']:.1f}",
                                      f"{_latest['VIX'] - _prev['VIX']:+.1f}")
                        with _mc2:
                            st.metric("HY 信用利差 (%)",
                                      f"{_latest['HY_Spread']:.2f}",
                                      f"{_latest['HY_Spread'] - _prev['HY_Spread']:+.2f}")
                        with _mc3:
                            st.metric("10Y-2Y 利差 (%)",
                                      f"{_latest['Yield_Curve_10Y_2Y']:.3f}",
                                      f"{_latest['Yield_Curve_10Y_2Y'] - _prev['Yield_Curve_10Y_2Y']:+.3f}")
                    elif _df_macro.empty:
                        # v17.2：友善降級為單列 st.info（不再用 warning 嚇人）
                        _diag_parts = []
                        for _diag_k, _diag_label in [
                            ("VIX",         "VIX"),
                            ("HY_SPREAD",   "HY 信用利差"),
                            ("YIELD_10Y2Y", "10Y-2Y 利差"),
                        ]:
                            _diag_s = (ind.get(_diag_k) or {}).get("series")
                            _diag_n = 0 if _diag_s is None else len(_diag_s)
                            _diag_icon = "✅" if _diag_n >= 20 else "⏳"
                            _diag_parts.append(f"{_diag_label}（{_diag_n} 筆）{_diag_icon}")
                        st.info(
                            "ℹ️ **指標同步狀態**：" + " ｜ ".join(_diag_parts)
                            + "　暫不影響整體健康度評估，主源補齊 ≥20 筆後本卡會自動計算複合 Risk Score。"
                        )

                    # ── 🎯 風險評分校準（v18.253，sandbox / 真實 FRED+SPX 雙模式）──
                    # 註：父層已是 expander，這裡改用 container（Streamlit 禁巢狀 expander）
                    st.divider()
                    st.markdown("##### 🎯 風險評分校準（experimental）")
                    with st.container(border=True):
                        from services.risk_calibration import (
                            fetch_real_3factor_monthly as _fetch_real_3f,
                            generate_synthetic_demo as _gen_demo,
                            grid_search_threshold as _grid_thr,
                            label_forward_drawdown as _lbl_dd,
                            rolling_risk_score as _roll_rs,
                        )
                        st.caption(
                            "**Ground truth**：未來 N 個月 SPX 最大回檔 < threshold ⇒ 標 1（命中）。"
                            "校準器掃描 score 門檻，回報每門檻 precision / recall / F1，找出最佳停利警戒點。"
                        )
                        _rc_src = st.radio(
                            "資料來源",
                            options=["🧪 合成（sandbox demo）", "📊 真實 FRED + SPX"],
                            horizontal=True, key="_rc_src_v253",
                        )
                        _rc_use_real = _rc_src.startswith("📊")
                        _cal_c1, _cal_c2, _cal_c3 = st.columns(3)
                        with _cal_c1:
                            _cal_horizon = st.slider("Forward horizon (月)", 1, 12, 3, key="_cal_h_v251")
                        with _cal_c2:
                            _cal_dd = st.slider("Drawdown 門檻 (%)", -30, -5, -10, key="_cal_dd_v251")
                        with _cal_c3:
                            _cal_win = st.slider("Rolling window (月)", 12, 48, 24, key="_cal_w_v251")
                        _df_src, _spx_src, _src_label = None, None, ""
                        if _rc_use_real:
                            _rc_years = st.slider("歷史年數", 5, 20, 10, key="_rc_yrs_v253")
                            _rc_key = f"_rc_real_{_rc_years}y"
                            if _rc_key not in st.session_state:
                                if st.button("📊 抓 FRED + SPX 真實月度資料",
                                              type="primary", key="_rc_btn_v253"):
                                    _fred_key = ""
                                    try:
                                        _fred_key = st.secrets.get("FRED_API_KEY", "")
                                    except Exception:
                                        pass
                                    with st.spinner(f"抓 FRED 3-series + SPX × {_rc_years} 年..."):
                                        _df_real, _spx_real, _rc_notes = _fetch_real_3f(
                                            _fred_key, years=int(_rc_years)
                                        )
                                    st.session_state[_rc_key] = (_df_real, _spx_real, _rc_notes)
                                    st.rerun()
                                else:
                                    st.info("👆 按上方按鈕抓真實 FRED + SPX（需 FRED_API_KEY in secrets）")
                            else:
                                _df_real, _spx_real, _rc_notes = st.session_state[_rc_key]
                                for _w in _rc_notes.get("warnings", []):
                                    st.warning(f"⚠️ {_w}")
                                if _rc_notes.get("missing_factors"):
                                    st.caption("缺失：" + ", ".join(_rc_notes["missing_factors"]))
                                _df_src, _spx_src = _df_real, _spx_real
                                _src_label = f"真實 FRED + SPX × {_rc_years} 年（{len(_df_real)} 月）"
                                if st.button("🔄 重抓真實資料", key="_rc_reload_v253"):
                                    del st.session_state[_rc_key]
                                    st.rerun()
                        else:
                            _df_src, _spx_src = _gen_demo(n_months=60, seed=42)
                            _src_label = "60 月合成 macro + SPX（內含 2 段壓力事件）"
                        if _df_src is not None and not _df_src.empty and not _spx_src.empty:
                            _score_demo = _roll_rs(_df_src, window=_cal_win)
                            _label_demo = _lbl_dd(_spx_src, horizon_months=_cal_horizon,
                                                  threshold=_cal_dd / 100.0)
                            _grid_df = _grid_thr(_score_demo, _label_demo)
                            if _grid_df.empty or _grid_df["f1"].max() <= 0:
                                st.warning("本組參數下校準器無法命中任何危機點（試試放寬 horizon / drawdown）")
                            else:
                                _best = _grid_df.iloc[0]
                                _mc1, _mc2, _mc3, _mc4 = st.columns(4)
                                _mc1.metric("最佳 F1 門檻", f"{_best['threshold']:.2f}")
                                _mc2.metric("Precision", f"{_best['precision']:.1%}")
                                _mc3.metric("Recall", f"{_best['recall']:.1%}")
                                _mc4.metric("F1", f"{_best['f1']:.1%}")
                                st.caption(
                                    f"📊 {_src_label}；當前生產 risk_score={_risk_score:.2f}，"
                                    f"建議警戒門檻={_best['threshold']:.2f}。"
                                )
                                st.dataframe(
                                    _grid_df.head(10).style.format({
                                        "threshold": "{:.2f}", "precision": "{:.1%}",
                                        "recall": "{:.1%}", "f1": "{:.1%}", "accuracy": "{:.1%}",
                                    }),
                                    use_container_width=True, hide_index=True,
                                )
                        if not _rc_use_real:
                            st.caption(
                                "⚠️ 合成資料只用於驗證 pipeline；要看真實命中率切換上方「📊 真實 FRED + SPX」。"
                            )

                    # ── 🧮 景氣分數校準（v18.252，14-factor Macro_Score 真值校準）──
                    # 註：父層已是 expander，這裡用 container（Streamlit 禁巢狀 expander）
                    st.divider()
                    st.markdown("##### 🧮 景氣分數校準（14-factor Macro_Score）")
                    with st.container(border=True):
                        from services.macro_score_calibration import (
                            classify_phase as _cls_phs,
                            compute_historical_score as _hist_sc,
                            fetch_real_macro_factors_monthly as _fetch_real,
                            generate_synthetic_demo as _gen_msc,
                            grid_search_phase_thresholds as _grid_phs,
                            overall_accuracy as _ov_acc,
                            phase_accuracy as _phs_acc,
                        )
                        st.caption(
                            "**Ground truth**：每位階建議「正確」與否由後 N 月 SPX 表現驗證 — "
                            "**高峰**應跌、**擴張**應漲、**復甦**應大漲(>10%)、**衰退**應跌。"
                        )

                        # ── 資料來源切換：合成 vs 真實 ───────────────
                        _src_mode = st.radio(
                            "資料來源",
                            options=["🧪 合成（sandbox demo）", "📊 真實 FRED + SPX"],
                            horizontal=True, key="_msc_src_v252",
                            help="真實資料需 FRED_API_KEY + NAS proxy 可達；首次抓 30-60 秒。",
                        )
                        _use_real = _src_mode.startswith("📊")

                        _msc_c1, _msc_c2 = st.columns(2)
                        with _msc_c1:
                            _msc_h = st.slider("Forward horizon (月)", 3, 24, 12,
                                               key="_msc_h_v252")
                        with _msc_c2:
                            _msc_n = st.slider(
                                "樣本長度（合成月 / 真實年）",
                                3, 120, (10 if _use_real else 60),
                                key="_msc_n_v252",
                                help="真實模式單位為「年」（3-15 年）；合成模式單位為「月」")

                        if _use_real:
                            # 真實資料：cache 在 session_state，按鈕觸發才抓
                            _real_key = f"_msc_real_{_msc_n}y"
                            if _real_key not in st.session_state:
                                if st.button("📊 抓 FRED + SPX 真實月度資料",
                                             type="primary",
                                             key=f"btn_msc_fetch_{_msc_n}"):
                                    with st.spinner(
                                            f"抓 FRED 14-series + SPX × {_msc_n} 年..."):
                                        _df_real, _spx_real, _notes = _fetch_real(
                                            FRED_KEY, years=int(_msc_n))
                                        st.session_state[_real_key] = (
                                            _df_real, _spx_real, _notes)
                                    st.rerun()
                                st.info("👆 按上方按鈕抓真實 FRED + SPX")
                                st.stop()
                            _df_msc, _spx_msc, _notes_real = (
                                st.session_state[_real_key])
                            if _df_msc.empty or _spx_msc.empty:
                                st.error("❌ 真實資料抓取失敗，請看下方警告")
                                st.json(_notes_real)
                                st.stop()
                            if _notes_real.get("missing_factors"):
                                st.warning("⚠️ 部分指標缺失（已自動跳過計分）："
                                           + " ｜ ".join(_notes_real["missing_factors"]))
                            if _notes_real.get("warnings"):
                                for _w in _notes_real["warnings"]:
                                    st.caption(f"ℹ️ {_w}")
                        else:
                            _df_msc, _spx_msc = _gen_msc(
                                n_months=int(_msc_n), seed=42)

                        _score_msc = _hist_sc(_df_msc)
                        _acc_df = _phs_acc(_score_msc, _spx_msc,
                                            horizon_months=_msc_h)
                        _ov = _ov_acc(_score_msc, _spx_msc, horizon_months=_msc_h)
                        # 當前 score 對應位階
                        _cur_score = float(_score_msc.iloc[-1])
                        _cur_phase = _cls_phs(_cur_score)
                        _mc1, _mc2, _mc3 = st.columns(3)
                        _label_prefix = "真實" if _use_real else "合成"
                        _mc1.metric(f"最新{_label_prefix} Macro_Score",
                                     f"{_cur_score:.2f}", _cur_phase)
                        _mc2.metric("總體命中率", f"{_ov:.1f}%",
                                     f"horizon={_msc_h}M")
                        _mc3.metric("樣本數", f"{len(_score_msc)}")
                        st.markdown("**各位階命中率**：")
                        st.dataframe(
                            _acc_df.style.format({
                                "hit_rate_pct": "{:.1f}%",
                                "mean_fwd_pct": "{:+.1f}%",
                                "median_fwd_pct": "{:+.1f}%",
                            }, na_rep="—"),
                            use_container_width=True, hide_index=True,
                        )
                        # 父層已 expander，這裡再 expander 會炸 → 改 checkbox toggle
                        if st.checkbox("🔬 顯示 grid_search 門檻調整建議",
                                       value=False, key="_msc_grid_v252"):
                            _grid_msc = _grid_phs(
                                _score_msc, _spx_msc,
                                horizon_months=_msc_h)
                            st.dataframe(
                                _grid_msc.head(10).style.format({
                                    "peak_thr": "{:.1f}",
                                    "expansion_thr": "{:.1f}",
                                    "recovery_thr": "{:.1f}",
                                    "overall_acc_pct": "{:.1f}%",
                                }),
                                use_container_width=True, hide_index=True,
                            )
                            st.caption(
                                "目前公式預設 (Peak/Exp/Rec)=(8.0/5.0/3.0)。"
                                "若上表第一列門檻明顯不同 → 考慮調整 "
                                "services/macro_service.py 的位階門檻。"
                            )
                        if _use_real:
                            st.caption(
                                "📊 真實資料：FRED + yfinance 月度（NAS proxy）。"
                                "PMI 用就業 YoY 代理（FRED 無 PMI）。換 horizon / 年數會"
                                "重新計算 cache 內資料；要重抓改按上方按鈕。"
                            )
                        else:
                            st.caption(
                                "🧪 合成資料：base_drift=+3.7%/年、σ=4%/月，含 3 段下殺 + "
                                "1 段反彈。命中率 60-75% 屬正常（合成 self-consistent）。"
                                "要看真實命中率切換上方「📊 真實 FRED + SPX」。"
                            )

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
                with st.expander("🌊 流動性壓力預警引擎（深水區 4 因子）", expanded=False):
                    from ui.components.macro_card import make_sparkline as _mk_sl2
                    from services.liquidity_engine import liquidity_verdict
                    if st.button("🔄 重新抓取流動性因子", key="btn_reload_liquidity"):
                        _load_liquidity_factors()
                        st.rerun()
                    st.caption("⚠️ 進階觀察｜XCCY 為代理指標、權重未經真值校準，僅供方向性參考")
                    st.info(liquidity_verdict(_liq_score, _liq_facs))

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

            # ── 景氣循環羅盤（V5：薩姆 + RSP/SPY 廣度 + 基準利率）──────
            _sahm_s  = _safe_series(_sahm_d.get("series"))  if _sahm_d  else None
            _adl_s   = _safe_series(_adl_d.get("series"))   if _adl_d   else None
            _rate_s  = _safe_series((ind.get("FED_RATE") or {}).get("series"))
            _has_compass = any(s is not None and len(s) >= 4
                               for s in [_sahm_s, _adl_s, _rate_s])
            if _has_compass and _show_l3:
                with st.expander("🧭 景氣循環羅盤（薩姆規則 + 市場廣度 + 利率）", expanded=False):
                    from plotly.subplots import make_subplots as _msp5
                    fig_compass = _msp5(rows=1, cols=1,
                                        specs=[[{"secondary_y": True}]])
                    # RSP/SPY 廣度陰影（主軸，面積填色）
                    if _adl_s is not None and len(_adl_s) >= 4:
                        _adl_pos = _adl_s.clip(lower=0)
                        _adl_neg = _adl_s.clip(upper=0)
                        fig_compass.add_trace(go.Scatter(
                            x=list(_adl_s.index), y=list(_adl_pos.values),
                            name="RSP/SPY 廣度(正)", fill="tozeroy",
                            fillcolor="rgba(0,200,83,0.15)",
                            line=dict(color="rgba(0,200,83,0.4)", width=1)),
                            secondary_y=False)
                        fig_compass.add_trace(go.Scatter(
                            x=list(_adl_s.index), y=list(_adl_neg.values),
                            name="RSP/SPY 廣度(負)", fill="tozeroy",
                            fillcolor="rgba(244,67,54,0.15)",
                            line=dict(color="rgba(244,67,54,0.4)", width=1)),
                            secondary_y=False)
                    # 薩姆規則實線（副軸）
                    if _sahm_s is not None and len(_sahm_s) >= 4:
                        fig_compass.add_trace(go.Scatter(
                            x=list(_sahm_s.index), y=list(_sahm_s.values),
                            name="薩姆規則(pp)", mode="lines",
                            line=dict(color="#f44336", width=2)),
                            secondary_y=True)
                        fig_compass.add_hline(y=0.5, line_color="#f44336",
                                              line_dash="dash", line_width=1,
                                              annotation_text="薩姆0.5衰退線",
                                              annotation_font_color="#f44336",
                                              annotation_position="top left")
                    # FedRate 點線（副軸）
                    if _rate_s is not None and len(_rate_s) >= 4:
                        fig_compass.add_trace(go.Scatter(
                            x=list(_rate_s.index), y=list(_rate_s.values),
                            name="基準利率(%)", mode="lines",
                            line=dict(color="#ff9800", width=1.5, dash="dot")),
                            secondary_y=True)
                    fig_compass.update_layout(
                        paper_bgcolor="#0e1117", plot_bgcolor="#161b22",
                        font_color="#e6edf3", height=320,
                        margin=dict(t=20, b=30, l=50, r=50),
                        legend=dict(orientation="h", font_size=10, y=1.04),
                        hovermode="x unified")
                    fig_compass.update_yaxes(title_text="RSP/SPY 廣度(%MoM)",
                                             gridcolor="#1e2a3a", secondary_y=False)
                    fig_compass.update_yaxes(title_text="薩姆 / 利率(%)",
                                             gridcolor="#1e2a3a", secondary_y=True)
                    fig_compass.update_xaxes(gridcolor="#1e2a3a")
                    st.plotly_chart(fig_compass, use_container_width=True)
                    # 研判文字
                    _adl_latest = float(_adl_s.iloc[-1]) if _adl_s is not None and len(_adl_s) else 0
                    _sahm_latest = float(_sahm_s.iloc[-1]) if _sahm_s is not None and len(_sahm_s) else 0
                    if _sahm_latest >= 0.5:
                        _compass_txt = ("🔴 **薩姆規則已觸發**：衰退機率高，停止衛星基金扣款，"
                                        "轉入低波動核心基金，現金部位拉至 30%+")
                    elif _adl_latest < -2 and sc >= 7:
                        _compass_txt = ("🟡 **虛假繁榮警示**：RSP/SPY 廣度持續縮窄但大盤仍高，"
                                        "老手應逢高分批獲利了結，不宜追高 AI 題材股")
                    elif _adl_latest > 2 and _sahm_latest < 0.3:
                        _compass_txt = ("🟢 **2026/4 研判**：復甦/擴張確立（薩姆安全 + 廣度健康），"
                                        "新手定期定額科技基金，老手 1σ 回測加碼三率雙升標的")
                    else:
                        _compass_txt = ("🟡 **行情分化**：AI 板塊續強但廣度未跟上，"
                                        "衛星部位以三率正成長基金為主，避開製造業循環標的")
                    st.info(_compass_txt)

            # ── 指標貢獻明細（折疊）── L3 only
            # v17.2：依 |score × weight| 排序 + 「💡 貢獻說明」欄（指標特定敘事）
            if _show_l3:
                # 指標特定的「現象 → 市場含義」對照表（Map）
                # 每筆 = (key 子串匹配, score>0 敘事, score<0 敘事)
                _CONTRIB_MAP = {
                    "PMI":           ("製造業擴張，有利股市",       "製造業收縮，景氣動能放緩"),
                    "LEI":           ("領先指標走升，景氣加速",     "領先指標走弱，景氣放緩"),
                    "SAHM":          ("勞動市場惡化，衰退預警",     "勞動市場穩健"),
                    "SLOOS":         ("銀行緊縮放貸，信用收斂",     "銀行寬鬆放貸，信用擴張"),
                    "YIELD_10Y2Y":   ("利差走闊，殖利率正常化",     "利差倒掛，衰退預警"),
                    "YIELD_10Y3M":   ("利差走闊，景氣健康",         "利差倒掛，紐約聯儲衰退模型啟動"),
                    "HY_SPREAD":     ("信用利差走闊，避險升溫",     "信用利差收斂，風險偏好上升"),
                    "VIX":           ("恐慌升溫，波動加大",          "市場平靜，風險偏好上升"),
                    "CPI":           ("通膨壓力升溫，緊縮風險",     "通膨回落，貨幣政策放鬆空間"),
                    "PPI":           ("上游成本升溫",                "上游成本回落"),
                    "INFL_EXP_5Y":   ("通膨預期升溫，債市壓力",     "通膨預期降溫，利率下行空間"),
                    "FED_RATE":      ("資金成本上升，估值承壓",     "資金成本下降，流動性寬鬆"),
                    "UNEMPLOYMENT":  ("失業率上升，景氣承壓",       "失業率下降，景氣健康"),
                    "JOBLESS":       ("初領失業金升溫，裁員壓力",   "初領失業金回落，就業改善"),
                    "CONT_CLAIMS":   ("持續失業金升溫",              "持續失業金回落"),
                    "CONSUMER_CONF": ("消費信心強，內需動能足",     "消費信心弱，內需放緩"),
                    "M2":            ("M2 寬鬆，流動性充沛",        "M2 緊縮，流動性收斂"),
                    "M2_WEEKLY":     ("M2 週頻寬鬆",                 "M2 週頻緊縮"),
                    "FED_BS":        ("Fed 擴表（QE）",              "Fed 縮表（QT）"),
                    "DXY":           ("美元走強，外幣資產承壓",     "美元走弱，外幣資產受益"),
                    "ADL":           ("市場廣度健康",                "大型股獨撐，廣度疲弱"),
                    "COPPER":        ("銅價走強，全球景氣轉熱",     "銅價走弱，全球景氣轉冷"),
                    "PERMIT_HOUSING":("建照核發強，房市領先",       "建照核發弱，房市領先疲弱"),
                }
                with st.expander("👉 查看完整 23 項指標加扣分明細（依 |score × weight| 由大至小）", expanded=True):
                    st.caption(
                        "📖 **怎麼看這張表**：「💡 貢獻說明」直接告訴你這檔指標目前如何影響景氣總分。"
                        "排序依 |score × weight| ＝ 對總分實際影響力，最重要的指標在最上方。"
                    )
                    _rows = []
                    for _ik, _iv in ind.items():
                        if not isinstance(_iv, dict): continue
                        _w_raw = _iv.get("weight", 1) or 1
                        try:
                            _w = float(_w_raw)
                        except (TypeError, ValueError):
                            _w = 1.0
                        _sc_raw = _iv.get("score", 0) or 0
                        try:
                            _sc_clamped = round(max(-_w, min(_w, float(_sc_raw))), 2)
                        except (TypeError, ValueError):
                            _sc_clamped = 0.0
                        _val_raw = _iv.get("value")
                        if isinstance(_val_raw, (int, float)):
                            _val_str = f"{_val_raw:.2f}"
                        else:
                            _val_str = str(_val_raw or "")[:10]
                        # 指標特定敘事：取對映 phrase；找不到就回退到通用語氣
                        _phrases = _CONTRIB_MAP.get(_ik)
                        if _phrases:
                            _semantic = _phrases[0] if _sc_clamped > 0 else (_phrases[1] if _sc_clamped < 0 else "現況中性")
                        else:
                            _semantic = "正面訊號" if _sc_clamped > 0 else ("負面訊號" if _sc_clamped < 0 else "現況中性")
                        # 組合貢獻說明：[指標 數值] ➡️ [現象+含義]，貢獻 ±X 分
                        _name = _iv.get("name", _ik)[:18]
                        if _sc_clamped > 0:
                            _verdict = f"{_name} {_val_str} ➡️ {_semantic}，貢獻 +{_sc_clamped:.1f} 分"
                        elif _sc_clamped < 0:
                            _verdict = f"{_name} {_val_str} ➡️ {_semantic}，扣 {_sc_clamped:.1f} 分"
                        else:
                            _verdict = f"{_name} {_val_str} ➡️ {_semantic}（不加減分）"
                        # 排序鍵：|score × weight|
                        _abs_contrib = abs(_sc_clamped * _w)
                        _rows.append({
                            "_abs": _abs_contrib,
                            "指標":      _name,
                            "數值":      _val_str,
                            "信號":      _iv.get("signal", "⬜"),
                            "貢獻分":    _sc_clamped,
                            "權重":      _w,
                            "💡 貢獻說明": _verdict,
                        })
                    if _rows:
                        _rows.sort(key=lambda r: r["_abs"], reverse=True)
                        for r in _rows:
                            r.pop("_abs", None)
                        st.dataframe(pd.DataFrame(_rows), use_container_width=True, hide_index=True,
                                     column_config={
                                         "指標":      st.column_config.TextColumn(width="small"),
                                         "數值":      st.column_config.TextColumn(width="small"),
                                         "信號":      st.column_config.TextColumn(width="small"),
                                         "貢獻分":    st.column_config.NumberColumn(format="%.2f", width="small"),
                                         "權重":      st.column_config.NumberColumn(format="%.0f", width="small"),
                                         "💡 貢獻說明": st.column_config.TextColumn(width="large"),
                                     })

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

            # ── v18.20 📡 景氣拐點監控 (Leading Indicator Tracker) ──
            st.divider()
            st.markdown("### ③ 📡 景氣拐點監控 (Leading Indicator Tracker)")
            st.caption("即時偵測兩個歷史最關鍵的景氣翻轉訊號：製造業新訂單－庫存擴散、"
                       "10Y-2Y 殖利率倒掛翻正")
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

            # ── v18.100 景氣循環細項燈號（Phase 2）──────────────────────
            # 7 個子領域（製造業/房市/就業/信貸/流動性/消費/通膨壓力）
            # 各取 1-2 個既有指標 z-score 平均後 → 🟢🟡🟠🔴 四色燈號
            try:
                _sub_lights = calc_sub_cycle_lights(ind)
                if any(c.get("z_avg") is not None for c in _sub_lights):
                    st.divider()
                    st.markdown("### 🚦 景氣細項燈號（7 子領域 Z-Score 健康度）")
                    st.caption(
                        "依「越偏離歷史均值越紅」原則彙整 7 個子領域：🟢 健康（z<-1）｜"
                        "🟡 中性偏好（-1≤z<0）｜🟠 中性偏弱（0≤z<1）｜🔴 警示（z≥1）。"
                        "資料不足以 ⬜ 顯示。"
                    )
                    _cols = st.columns(4)
                    for _i, _c in enumerate(_sub_lights):
                        with _cols[_i % 4]:
                            _z = _c.get("z_avg")
                            _z_str = f"Z={_z:+.2f}" if _z is not None else "Z=—"
                            _ind_str = " · ".join(
                                f"{ix['key']} z{ix['z']:+.1f}"
                                for ix in _c.get("indicators", [])
                            ) or "—"
                            st.markdown(
                                f"<div style='background:#161b22;border:1px solid {_c['color']};"
                                f"border-radius:8px;padding:10px 12px;margin:4px 0'>"
                                f"<div style='font-size:13px;color:#aaa'>{_c['icon']} {_c['name']}</div>"
                                f"<div style='font-size:22px;font-weight:700;color:{_c['color']};"
                                f"margin:2px 0'>{_c['signal']} {_c['verdict']}</div>"
                                f"<div style='font-size:11px;color:#888'>{_z_str}</div>"
                                f"<div style='font-size:10px;color:#666;margin-top:4px'>{_ind_str}</div>"
                                f"</div>",
                                unsafe_allow_html=True,
                            )
                    # v18.119 issue 2: 7 子領域白話解讀
                    _sl_alerts = []
                    for _c in _sub_lights:
                        _z = _c.get("z_avg")
                        if _z is None:
                            continue
                        _icon = _c.get("icon", ""); _nm = _c.get("name", "?")
                        _sig  = _c.get("signal", "")
                        if _z < -1.5:
                            _hint = "顯著低於歷史均值（>1.5σ）→ 此領域偏健康，可承擔較高風險"
                        elif _z < -0.5:
                            _hint = "低於歷史均值（0.5-1.5σ）→ 中性偏好，無立即壓力"
                        elif _z < 0.5:
                            _hint = "接近歷史均值 → 中性，需搭配其他指標研判"
                        elif _z < 1.5:
                            _hint = "高於歷史均值（0.5-1.5σ）→ 中性偏弱，啟動觀察"
                        else:
                            _hint = "⚠️ 顯著偏離歷史均值（>1.5σ）→ 警示等級，建議降低該領域曝險"
                        _sl_alerts.append(
                            f"{_icon} **{_nm}** {_sig} (z={_z:+.2f}) — {_hint}"
                        )
                    if _sl_alerts:
                        with st.expander("💡 7 子領域 z-score 白話解讀", expanded=False):
                            st.markdown("\n\n".join("- " + a for a in _sl_alerts))
            except Exception as _e_sl:
                st.caption(f"⚠️ 細項燈號計算失敗：{str(_e_sl)[:80]}")

            # ── v18.101+v18.105 總經因果鏈 Sankey（Phase 2 + Phase 3 動態權重）─
            # 「政策 → 信貸 → 實體經濟 → 市場」三層 8 節點 9 邊，
            # 節點色＝健康度（z_norm 翻轉後）；邊粗細：
            #   Phase 2：起點 |z|（固定權重）
            #   Phase 3：兩端 series |corr| × 加權（動態權重）— v18.105 預設開
            with st.expander("🔗 總經因果鏈 Sankey（升息 → 信貸 → 房市/就業 → VIX）",
                             expanded=False):
                _sk_dynamic = st.checkbox(
                    "🆕 動態權重（用兩端 series 相關係數）",
                    value=True, key="sankey_dynamic_weights",
                    help="Phase 3：邊粗細改用「起點 vs 終點 series 的 Pearson |corr| × 加權」，"
                         "取代 Phase 2 的固定起點 |z|；hover 邊顯示實際 corr 值。"
                )
                try:
                    _sk = (build_macro_sankey_dynamic(ind) if _sk_dynamic
                           else build_macro_sankey_data(ind))
                    if not _sk["ok"]:
                        st.info(f"📡 因果鏈節點資料不足（{_sk['note']}）；先載入更多總經指標再來。")
                    else:
                        _sk_fig = go.Figure(data=[go.Sankey(
                            arrangement="snap",
                            node=dict(
                                pad=18, thickness=18,
                                line=dict(color="#30363d", width=0.5),
                                label=_sk["labels"],
                                color=_sk["node_colors"],
                            ),
                            link=dict(
                                source=_sk["sources"],
                                target=_sk["targets"],
                                value=_sk["values"],
                                color=_sk["link_colors"],
                                label=_sk["link_labels"],
                            ),
                        )])
                        _sk_fig.update_layout(
                            paper_bgcolor="#0e1117",
                            font=dict(color="#e6edf3", size=12),
                            height=420, margin=dict(l=10, r=10, t=10, b=10),
                        )
                        st.plotly_chart(_sk_fig, use_container_width=True)
                        st.caption(
                            f"節點色＝z-score 健康度（🟢 z<-1 / 🟡 -1≤z<0 / 🟠 0≤z<1 / 🔴 z≥1，"
                            f"已依 high_is_bad 翻轉）；邊粗細＝起點 |z| 或動態 |corr|。"
                            f"hover 邊可看因果關係教學。{_sk['note']}。"
                        )
                        # v18.174：動態詳細說明 — 逐節點健康度 + 逐邊強弱分級，讓新人秒懂
                        with st.expander(
                            "📖 動態詳細說明（看不懂這張圖？點開逐節點 + 逐邊白話）",
                            expanded=True,
                        ):
                            _color_to_state = {
                                "#f44336": "🔴 壓力高 / 極端偏離（z≥+1σ）",
                                "#ff9800": "🟠 偏離均值（0≤z<+1σ）",
                                "#ffeb3b": "🟡 略偏負面（−1σ≤z<0）",
                                "#4caf50": "🟢 健康（z<−1σ）",
                                "#666":    "🌫️ 無 z-score（資料不足）",
                            }
                            _node_lines = ["**🔍 8 節點現況**（顏色 = 健康度）"]
                            for _i_n, _lbl_n in enumerate(_sk["labels"]):
                                _c_n = _sk["node_colors"][_i_n]
                                _state_n = _color_to_state.get(_c_n, "—")
                                _node_lines.append(f"- {_lbl_n} → {_state_n}")
                            st.markdown("\n".join(_node_lines))

                            st.markdown("")
                            if "link_corrs" not in _sk or not _sk_dynamic:
                                st.info(
                                    "💡 **啟用「🆕 動態權重」**（上方 checkbox 打勾）可看每條邊"
                                    "實際 Pearson 相關係數，並依強弱分為「🔥 強 / 🌤️ 中等 / ❄️ 弱」三組。"
                                    "目前 Phase 2 模式僅用起點 z-score 決定粗細。"
                                )
                            else:
                                _link_corrs = _sk["link_corrs"]
                                def _strip_corr_tag(_s: str) -> str:
                                    _idx = _s.find("（corr=")
                                    return _s[:_idx] if _idx >= 0 else _s
                                _strong: list[str] = []
                                _mid:    list[str] = []
                                _weak:   list[str] = []
                                _na:     list[str] = []
                                for _i_l, _corr_l in enumerate(_link_corrs):
                                    _edu_l = _strip_corr_tag(_sk["link_labels"][_i_l])
                                    _src_lbl = _sk["labels"][_sk["sources"][_i_l]].split(" (z=")[0]
                                    _tgt_lbl = _sk["labels"][_sk["targets"][_i_l]].split(" (z=")[0]
                                    _head = f"{_src_lbl} → {_tgt_lbl}：{_edu_l}"
                                    if _corr_l is None:
                                        _na.append(f"- {_head}（共同期 <12 個月，無法計算）")
                                    else:
                                        _dir_word = "正" if _corr_l > 0 else "負"
                                        _abs_c = abs(_corr_l)
                                        if _abs_c >= 0.5:
                                            _strong.append(
                                                f"- **{_head}**（corr={_corr_l:+.2f}，強{_dir_word}相關）"
                                            )
                                        elif _abs_c >= 0.3:
                                            _mid.append(
                                                f"- {_head}（corr={_corr_l:+.2f}，中等{_dir_word}相關）"
                                            )
                                        else:
                                            _weak.append(
                                                f"- {_head}（corr={_corr_l:+.2f}，相關性微弱）"
                                            )
                                _link_lines = ["**🔗 9 條因果鏈強弱分級**"]
                                if _strong:
                                    _link_lines.append("🔥 **強相關（|corr|≥0.5，傳導明顯）：**")
                                    _link_lines.extend(_strong)
                                if _mid:
                                    _link_lines.append("🌤️ **中等相關（0.3≤|corr|<0.5）：**")
                                    _link_lines.extend(_mid)
                                if _weak:
                                    _link_lines.append("❄️ **弱相關（|corr|<0.3，近期不明顯）：**")
                                    _link_lines.extend(_weak)
                                if _na:
                                    _link_lines.append("🌫️ **資料不足：**")
                                    _link_lines.extend(_na)
                                st.markdown("\n".join(_link_lines))

                                st.caption(
                                    "💡 **怎麼用這張圖？** 先看「🔥 強相關」那組邊 = 目前傳導最明顯的因果鏈；"
                                    "再對照源頭節點的健康度 — 若源頭🔴（極端偏離）+ 邊 🔥 強相關，"
                                    "代表這條傳導路徑正在發揮作用，需要關注終點節點後續變化。"
                                )
                except Exception as _e_sk:
                    st.caption(f"⚠️ Sankey 因果鏈渲染失敗：{str(_e_sk)[:80]}")

            # ── v18.105 燈號歷史回測（Phase 3 B）──────────────────────
            # 每組燈號出現後 target 指標（預設 LEI/CFNAI）3M 變化
            with st.expander("📊 細項燈號歷史回測（紅燈出現後 LEI 走勢驗證）",
                             expanded=False):
                _bt_target = st.selectbox(
                    "回測 target 指標",
                    options=["LEI", "PMI", "CONSUMER_CONF", "PERMIT_HOUSING"],
                    index=0, key="bt_subcycle_target",
                    help="燈號出現後該 target 指標 forward_months 後的平均變化；LEI=CFNAI 領先指標。",
                )
                _bt_fwd = st.slider("forward months（燈號後幾個月看 target 變化）",
                                    min_value=1, max_value=12, value=3, step=1,
                                    key="bt_subcycle_fwd")
                try:
                    _bt = backtest_sub_cycle_lights(
                        ind, target_key=_bt_target, forward_months=_bt_fwd
                    )
                    _bt_rows = []
                    for c in _bt:
                        _bt_rows.append({
                            "子領域": f"{c['icon']} {c['name']}",
                            "n_obs": c["n_obs"],
                            "🟢 綠燈次數": c["n_green"],
                            "🟢 後續變化": (f"{c['fwd_chg_green']:+.2f}"
                                            if c["fwd_chg_green"] is not None else "—"),
                            "🔴 紅燈次數": c["n_red"],
                            "🔴 後續變化": (f"{c['fwd_chg_red']:+.2f}"
                                            if c["fwd_chg_red"] is not None else "—"),
                            "結論": c["verdict"],
                        })
                    st.dataframe(pd.DataFrame(_bt_rows), use_container_width=True,
                                 hide_index=True)
                    st.caption(
                        f"使用 expanding window（最少 {60} 月）避免未來資訊洩漏；"
                        f"每月用該月之前的全部歷史重算 z_avg → 分桶 → 找 {_bt_fwd}M 後 {_bt_target} 變化。"
                        f"理論預期：🔴 紅燈後 target 應該下滑（負數），🟢 綠燈後應該上行（正數）。"
                    )
                    # v18.118 issue 2: 動態講解 — 自動挑出有意義的歷史結論
                    _bt_alerts: list[str] = []
                    for c in _bt:
                        _r_chg = c.get("fwd_chg_red")
                        _g_chg = c.get("fwd_chg_green")
                        _ic = c.get("icon", ""); _nm = c.get("name", "?")
                        if _r_chg is not None and _g_chg is not None:
                            _diff = _r_chg - _g_chg
                            if _diff < -0.1:
                                _bt_alerts.append(
                                    f"✅ {_ic} **{_nm}**：紅燈領先衰退（紅燈後{_bt_fwd}M {_bt_target} "
                                    f"{_r_chg:+.2f} vs 綠燈後 {_g_chg:+.2f}，差 {_diff:+.2f}）"
                                )
                            elif abs(_diff) < 0.05:
                                _bt_alerts.append(
                                    f"⚠️ {_ic} {_nm}：紅綠燈差異小（{_diff:+.2f}），訊號弱"
                                )
                            else:
                                _bt_alerts.append(
                                    f"❓ {_ic} {_nm}：紅燈後 {_r_chg:+.2f} 反向於預期（差 {_diff:+.2f}）"
                                )
                        elif c.get("n_obs", 0) == 0:
                            _bt_alerts.append(
                                f"🌫️ {_ic} {_nm}：樣本不足，無歷史結論可比對"
                            )
                    if _bt_alerts:
                        st.info(
                            "💡 **歷史回測重點解讀**\n\n"
                            + "\n\n".join("- " + a for a in _bt_alerts)
                        )
                except Exception as _e_bt:
                    st.caption(f"⚠️ 燈號歷史回測失敗：{str(_e_bt)[:80]}")

            # ── v18.108 變數重要性 Top-N（Phase 4）─────────────────────
            # 對 Sankey 8 節點 series 算 lag-corr(driver_t, Δtarget_{t→t+lag})
            # 排序回 driver 重要性 — 不引入 sklearn / shap 套件
            with st.expander("📊 變數重要性 Top-N（哪個指標最能預測景氣變化？）",
                             expanded=False):
                _imp_c1, _imp_c2 = st.columns(2)
                with _imp_c1:
                    _imp_target = st.selectbox(
                        "target 指標", options=["LEI", "PMI", "VIX", "PERMIT_HOUSING"],
                        index=0, key="imp_target",
                        help="計算各 driver 與 target lag 後變化的 lag-correlation",
                    )
                with _imp_c2:
                    _imp_lag = st.slider("lag months",
                                         min_value=1, max_value=12, value=3,
                                         step=1, key="imp_lag")
                try:
                    _imp = rank_macro_drivers(ind, target_key=_imp_target,
                                              lag_months=_imp_lag, min_overlap=24)
                    if not _imp["ok"]:
                        st.info(f"📡 {_imp['note']}")
                    else:
                        _imp_rows = []
                        for r in _imp["ranked"]:
                            _imp_rows.append({
                                "排名": "🏅",
                                "driver": r["name"],
                                "lag-corr": f"{r['corr']:+.3f}",
                                "|corr|": f"{r['abs_corr']:.3f}",
                                "方向": ("📈 同向" if r["direction"] == "+"
                                         else "📉 反向"),
                                "權重": r["weight"],
                                "共同期": r["n_overlap"],
                            })
                        # 標記前三名
                        for i, row in enumerate(_imp_rows[:3]):
                            row["排名"] = ["🥇", "🥈", "🥉"][i]
                        st.dataframe(pd.DataFrame(_imp_rows),
                                     use_container_width=True, hide_index=True)
                        st.caption(
                            f"📊 lag-corr 解讀：driver 在 t 月 vs target 在 t+{_imp_lag} 月變化的相關性；"
                            f"|corr|≥0.5「高」/ 0.3-0.5「中」/ <0.3「低」。"
                            f"正號 = 同向（driver 升→target 也升）；負號 = 反向。"
                            f"{_imp['note']}。"
                        )
                        # v18.118 issue 2: 動態講解 — Top 3 driver 的具體意義
                        _top3 = _imp["ranked"][:3]
                        if _top3:
                            _narrative_lines = []
                            for i, r in enumerate(_top3):
                                _medal = ["🥇", "🥈", "🥉"][i]
                                _dir_word = "同向（一起升降）" if r["direction"] == "+" else "反向（升↔降）"
                                _signal_word = (
                                    "顯著" if r["abs_corr"] >= 0.5
                                    else ("中等" if r["abs_corr"] >= 0.3 else "微弱")
                                )
                                _narrative_lines.append(
                                    f"{_medal} **{r['name']}** "
                                    f"與 {_imp_target} 未來 {_imp_lag} 個月變化呈 **{_dir_word}** "
                                    f"相關（|corr|={r['abs_corr']:.2f}，{_signal_word}）"
                                )
                            _top1 = _top3[0]
                            _action_hint = (
                                f"→ **應用**：當 **{_top1['name']}** 出現明顯變化時，"
                                f"預期 {_imp_lag} 個月後 {_imp_target} 將朝"
                                f"{'同方向' if _top1['direction']=='+' else '反方向'}"
                                f"移動（歷史資料 n={_top1['n_overlap']} 月）。"
                            )
                            st.info(
                                "💡 **Top 3 driver 解讀**\n\n"
                                + "\n\n".join("- " + l for l in _narrative_lines)
                                + "\n\n" + _action_hint
                            )
                except Exception as _e_imp:
                    st.caption(f"⚠️ 變數重要性計算失敗：{str(_e_imp)[:80]}")

            # ── 熱錢監測（v18.236）— 三角交叉：外資 × 匯率 × 背離 ──
            # 境外基金 user 仍要看：台幣匯率變動 → 影響你 USD/EUR 計價基金 TWD 換算後報酬
            st.divider()
            with st.expander("💵 台股熱錢監測 — 三角交叉（影響你境外基金 TWD 換匯）",
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
    headlines = [str(n.get("title", "") or n.get("headline", ""))
                 for n in (news or []) if isinstance(n, dict)][:8]
    sections = ["景氣位階與分數", "資產配置建議", "關鍵總經指標", "系統性風險",
                "領先指標與產業燈號", "新聞時事"]
    return "\n".join(lines), headlines, sections


