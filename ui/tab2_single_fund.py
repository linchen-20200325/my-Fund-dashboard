"""ui/tab2_single_fund.py — 單一基金深度分析 Tab（v18.126 B-C.4）

從 app.py 抽出 Tab2（單一基金深度分析）的渲染邏輯。

設計：
- render_single_fund_tab() -> None **零閉包依賴**（與 Tab4/5/6 同設計）
- 外部 helper 從 ui.helpers.session import（_friendly_error / _is_core_fund / calc_data_health）

對外 API:
- render_single_fund_tab() -> None
"""
from __future__ import annotations

import os

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from shared.colors import BG_DARK_AMBER_1, BG_DARK_AMBER_3, BG_DARK_GREEN_1, BG_DARK_GREEN_2, BG_DARK_NAVY_1, BG_DARK_NAVY_3, BG_DARK_NAVY_4, BG_DARK_RED_1, CAUTION_YELLOW, CHIP_BG_NEAR_BLACK, GH_BG_CARD, GH_BG_PRIMARY, GH_BORDER, GH_FG_PRIMARY, GH_FG_SECONDARY, GRAY_44, GRAY_55, GRAY_66, GRAY_AA, GRAY_CC, INFO_BLUE, MATERIAL_GREEN, MATERIAL_ORANGE, MATERIAL_RED, MD_BLUE_500, MD_DEEP_ORANGE_400, MD_GREEN_A200, MD_GREEN_A400, MD_ORANGE_300, MD_PURPLE_500, STREAMLIT_BG, TRAFFIC_GREEN, TRAFFIC_NEUTRAL, TRAFFIC_RED, WARN_AMBER, WHITE
from shared.converters import safe_float as _safe_float  # v19.331 review:占位字串防護
# §3.3 反捏造:接近警戒門檻走 shared SSOT,不在本檔另寫一份同義 literal
from shared.signal_thresholds import NEAR_DIVIDEND_WARNING_PCT as _NEAR_PCT_SSOT

from repositories.fund import (
    tdcc_search_fund,
)
from services.portfolio_service import dividend_safety as div_safety_check
from services.precision_service import (
    calc_hwm_sigma_levels,
)
from ui.helpers.macro_helpers import (
    mk_fund_signal,
    quartile_check as _quartile_check,
)
from ui.helpers.metric_explainers import render_metric_explainer
from ui.helpers.session import (
    friendly_error as _friendly_error,  # noqa: F401 — re-export for tests / external import
    is_core_fund as _is_core_fund,
    calc_data_health as _calc_data_health_pure,
)

# 其他可能需要的 app.py module-level helpers — 用 lazy import 避免 circular
# fund_fetcher 內的 utility 函式（normalize_result_state / classify_fetch_status）
from fund_fetcher import (
    classify_fetch_status,
    normalize_result_state,
)
# v19.76 K3：MoneyDJ 自動偵測 SSOT（tab2 + tab5 共用）
from services.moneydj_fetcher import auto_fetch_moneydj


def _calc_data_health(indicators=None):
    """同 app.py wrapper：indicators=None → 走 session_state。"""
    ind = indicators if indicators is not None else st.session_state.get("indicators", {})
    return _calc_data_health_pure(ind)


# ── MK 3-3-3 原則評估（v19.295）────────────────────────────────────────────

def _render_333_fund_expander(
    nav_series: "pd.Series",
    metrics: dict,
    display_name: str,
) -> None:
    """MK 3-3-3 原則評估區塊（Tab2 單一基金）。

    C1 成立>3年 / C2 三年年化>7% / C3 同儕排名前1/3
    資料來源：nav_series (DatetimeIndex) + metrics.ret_3y_ann (MoneyDJ)。
    C3 目前顯示說明文字（無 portfolio peer 傳入時）。
    """
    from services.fund_screening import check_333_fund  # EX-PASSTHRU L3→L2 直呼 service

    # 摺疊處置(原則 1):本區塊輸出的是**結論資料**(C1/C2/C3 三條判定)而非教學文。
    # 原本外面包一層「永遠展開」的摺疊殼 —— 那層殼不承載任何資訊,只多一圈邊框
    # 與一個「可以收起來」的假暗示;真正的成本是使用者得先辨認出它是空殼。
    # 改成純標題 + container,判定結果直接攤在版面上。
    st.markdown("#### 🎯 MK 3-3-3 優質標的評估")
    with st.container():
        st.caption(
            "**MK 郭俊宏核心篩選原則** — "
            "①成立 >3年（歷經牛熊）｜"
            "②3年年化報酬 >7%（真正定存替代品）｜"
            "③晨星3顆星 / 同儕前1/3（中前段班有潛力）"
        )

        r = check_333_fund(nav_series, metrics)

        def _icon(b) -> str:
            if b is True:  return '✅'
            if b is False: return '❌'
            return '❓'

        age   = r.get('c1_age_years')
        ret3y = r.get('c2_return_3y')
        src   = r.get('c2_source', '')

        age_str = f'{age:.1f} 年' if age is not None else 'N/A'
        if ret3y is not None:
            ret_str = f'{ret3y * 100:.1f}%'
            ret_note = f'（來源：{src}）' if src else ''
        else:
            ret_str  = 'N/A'
            ret_note = '（需 2.5 年以上 NAV 資料）'

        overall = r.get('overall_pass')
        if overall is True:
            bcolor  = '#16a085'
            verdict = '🏆 C1+C2 全過！符合 MK 3-3-3 初步篩選標準'
        elif overall is False:
            bcolor  = '#c0392b'
            verdict = '⚠️ 未達標 — 至少一項條件不符'
        else:
            bcolor  = '#586069'
            verdict = '📊 評估完成（C3 需人工核對晨星評級）'

        st.markdown(
            f'<div style="border-left:4px solid {bcolor};padding:14px 18px;'
            f'border-radius:6px;margin:10px 0;background:rgba(0,0,0,0.10);">'
            f'<div style="font-size:1.05em;font-weight:bold;margin-bottom:10px;">{verdict}</div>'
            '<table style="width:100%;border-collapse:collapse;font-size:0.95em;">'
            f'<tr><td style="padding:5px 0;color:#8b949e;width:55%">① 成立時間 &gt; 3 年</td>'
            f'<td>{_icon(r.get("c1_pass"))} &nbsp;<b>{age_str}</b></td></tr>'
            f'<tr><td style="padding:5px 0;color:#8b949e;">② 3 年年化報酬 &gt; 7%</td>'
            f'<td>{_icon(r.get("c2_pass"))} &nbsp;<b>{ret_str}</b>'
            f'<span style="font-size:0.85em;color:#8b949e;"> {ret_note}</span></td></tr>'
            '<tr><td style="padding:5px 0;color:#8b949e;">③ 晨星評級 / 同儕前 1/3</td>'
            '<td>❓ &nbsp;<span style="font-size:0.85em;color:#8b949e;">'
            '請至 <a href="https://www.morningstar.com.tw" target="_blank">Morningstar.com.tw</a>'
            ' 查詢同類評級</span></td></tr>'
            '</table></div>',
            unsafe_allow_html=True,
        )

        # 輔助提示
        if age is not None and not r.get('c1_pass'):
            remain = 3.0 - age
            st.caption(f'⏳ 距離 3 年門檻還需 {remain:.1f} 年（{int(remain * 12)} 個月）')
        if ret3y is not None and not r.get('c2_pass'):
            gap = 0.07 - ret3y
            st.caption(f'❗ 年化報酬距 7% 目標差 {gap * 100:.1f} 個百分點')
        if r.get('c2_pass') is True and r.get('c1_pass') is True:
            st.caption('💡 C1+C2 通過後，請至晨星確認 C3（同類前 40 名 ≈ 3 顆星以上）'
                       '，三項全過才是 MK 定義的「基優生」。')

        # ⚠️ 這裡**不可以**開摺疊容器。兩個理由,拿掉外層殼之後第二個仍然成立:
        # (1) 說明文本來就不該闔上(原則 1),直接平鋪;
        # (2) 唯一 caller 把整段包在 try/except 裡只印 stderr,一旦這裡拋例外
        #     (例如日後有人又在外面加一層摺疊容器造成巢狀),畫面上是「這一區
        #     整段消失、卻沒有任何錯誤提示」。守門測試見 tests/test_app_smoke.py。
        st.markdown('###### 📖 3-3-3 原則說明')
        st.markdown(
            '**①成立 >3 年** — 足以歷經完整牛熊循環，有資本利得作為配息後盾，'
            '可透過歷史驗證抗跌能力。\n\n'
            '**②3 年年化報酬 >7%** — MK 核心目標：找「7% 以上的定存替代品」。'
            '長期穩定 7%+ 代表能透過資本利得+股息完整支付配息，不吃本金。\n\n'
            '**③晨星 3 顆星 / 同儕前 1/3** — 晨星 3 顆星 = 同類前 40 名。'
            '選中前段班而非頂尖，因為資優生落差大；中前段班費率、風控和績效已達標，'
            '更有持續往上的空間。'
        )


def _risk_1y_rows_html(risk_table: dict, *, label_style: str = "short") -> str:
    """1Y 風險指標列(標準差/Sharpe/Alpha/Beta/追蹤誤差)共用 HTML。

    v19.336 review M9 去重:partial 資料視圖與 complete 視圖原各刻一套
    同款 flex-div 卡(僅標籤微異),抽共用 helper、以 label_style 保留兩處
    原有標籤差異(不趁機統一文案,行為 0 改變)。
    - "short":標準差(1Y)/Sharpe(1Y)…,值原樣(partial 視圖)
    - "long" :波動 σ(1Y)/…,標準差數值型加 %(complete 視圖)

    去重(原則 2):"long"(complete 視圖)**刻意不出 Sharpe 列** —— 同一畫面上方的
    「🩺 健康分析」已有一格 Sharpe,且那一格由 `_lbl_with_period()` 標出**實際期間
    與來源**(官方一年 / 官方六個月 / 本地自算 Nd),資訊嚴格多於此處無標籤的裸數字;
    兩個都印會讓 user 以為是兩個不同指標。partial 視圖(short)沒有上方那一格,
    故仍保留 Sharpe 列。
    v19.347(第九份 ⑯):補「追蹤誤差 Tracking Error」列 — wb07 風險表本就解析
    此欄入 risk_table(clean_risk_table NUMERIC 集含),僅 UI 從未顯示;缺值顯 —。
    """
    _r1y = (risk_table or {}).get("一年", {}) or {}
    _std = _r1y.get("標準差", "—"); _sh = _r1y.get("Sharpe", "—")
    _al  = _r1y.get("Alpha", "—");  _be = _r1y.get("Beta", "—")
    _te  = _r1y.get("Tracking Error", "—")
    if label_style == "long":
        rows = [("波動 σ(1Y)", f"{_std}%" if isinstance(_std, (int, float)) else _std),
                ("Alpha(1Y)", str(_al)), ("Beta(1Y)", str(_be)),
                ("追蹤誤差 TE(1Y)", f"{_te}%" if isinstance(_te, (int, float)) else str(_te))]
    else:
        rows = [("標準差(1Y)", _std), ("Sharpe(1Y)", _sh),
                ("Alpha(1Y)", _al), ("Beta(1Y)", _be),
                ("追蹤誤差(1Y)", _te)]
    return "".join(
        f"<div style='display:flex;justify-content:space-between;padding:5px 10px;"
        f"background:{GH_BG_CARD};border-radius:6px;margin:3px 0'>"
        f"<span style='color:{TRAFFIC_NEUTRAL};font-size:12px'>{lbl}</span>"
        f"<span style='font-weight:700'>{val}</span></div>"
        for lbl, val in rows)


# ── 雙演算法對帳 chip 文案(原則 4:畫面上不留未翻譯的英文狀態碼)───────────
# reconcile_pair 產出的 status 是英文 enum,原本直接印在畫面上,一般使用者
# 讀不出意思;而且「兩邊不一致」時最關鍵的資訊 —— 上方那個大數字到底採用了
# 哪一邊(§2.1 衝突裁決結果)—— 完全沒寫出來。
_RECON_STATUS_ZH = {
    "agree":     "兩套算法一致",
    "disagree":  "兩套算法不一致",
    "a_missing": "本地自算缺值（只有單一來源可比）",
    "b_missing": "官方值缺值（只有單一來源可比）",
}
_RECON_EMOJI = {"agree": "✅", "disagree": "⚠️", "a_missing": "⬜", "b_missing": "⬜"}
_RECON_VALID = tuple(_RECON_STATUS_ZH)

# 年化配息率三層 fallback chain(services.health.dividend SSOT)的中文說明。
# 畫面上每一個年化配息率數字都要說得出自己是哪一層來的(§2.2 provenance),
# 不可以固定寫「官方值」——實際命中第二/三層時那句話就是在說謊。
_ADR_SRC_ZH = {
    "moneydj_wb05": "MoneyDJ wb05 官方年化配息率",
    "metrics_annual_div_rate": "本地自算（近期配息 × 配息頻率 ÷ 淨值）",
    "divs_12m_sum": "本地推算（近 12 個月配息合計 ÷ 現值淨值）",
}


def _recon_zh(status: str) -> str:
    """英文 status → 「表情 + 繁中說明」;未知碼原樣帶出,不吞。"""
    return f"{_RECON_EMOJI.get(status, '⬜')} {_RECON_STATUS_ZH.get(status, status)}"


def render_single_fund_tab() -> None:
    """渲染單一基金深度分析 Tab — MoneyDJ 抓取 + 風險指標 + AI 分析。

    Caller 不需傳參數；Tab 內外部依賴透過 ui.helpers.session 等 import 自取。
    """
    # v18.126 B-C.4: GEMINI_KEY 走 env（app.py:_load_keys 已注入）
    GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")

    # v18.139: _update_data_registry / _zh_holding 已搬到 ui/helpers/
    # 改正規 import 取代 v18.129 sys.modules['__main__'] hack
    from ui.helpers.data_registry import _update_data_registry
    from ui.helpers.holdings import _zh_holding

    st.markdown("## 🔍 單一基金深度分析")
    from ui.helpers.story_nav import render_story_nav
    render_story_nav("fund")
    st.caption("輸入 MoneyDJ 代碼或網址，即時抓取淨值 / 持股 / 配息 / 風險指標")

    # ── 輸入列（自動偵測境內/境外，移除 radio）────────────────────
    _t2_input_col, _t2_btn_col = st.columns([5.6, 1])
    with _t2_input_col:
        mj_url_input = st.text_input("MoneyDJ URL 或代碼",
            placeholder="輸入代碼（TLZF9 / ACTI94）或貼上完整 MoneyDJ 網址",
            label_visibility="collapsed", key="mj_url_input")
    with _t2_btn_col:
        do_load = st.button("🚀 分析", type="primary", use_container_width=True, key="btn_mj_load")

    # v19.76 K3：原 38 行 _auto_fetch_moneydj + 4 行 _build_moneydj_url 已遷移至
    # services.moneydj_fetcher，tab2/tab5 共用同一份 fallback chain。

    if do_load and mj_url_input.strip():
        # v19.353 效能:移除「每次分析都 clear_all_caches()」全站冷清。原 v18.60 為
        # 「確保用最新 calc_metrics 邏輯」而清全站快取,但:(1) calc 是 code — 部署即
        # 重啟自然清快取,不需每次點清;(2) NAV 走 @_daily_cache(T+1,日內不變)。原行為
        # 導致同一基金重複分析、或任何 rerun 後再點,都冷抓 2000d NAV(MoneyDJ HTML 爬)
        # + 全站 fetcher。改吃既有快取 → 同基金再分析走 daily cache 即時回。需最新資料
        # 的 escape hatch 已存在:sidebar「🧹 全域刷新」(global_refresh_all) 或跨日自動失效。
        with st.spinner("📡 自動偵測基金類型並抓取資料..."):
            fd_raw, _t2_page_type = auto_fetch_moneydj(
                mj_url_input.strip(), return_page_type=True
            )
            fd_raw  = normalize_result_state(fd_raw)
            _status = fd_raw.get("status", classify_fetch_status(fd_raw))
            st.session_state.fund_data = {
                "full_key":    fd_raw.get("full_key",""),
                "fund_name":   fd_raw.get("fund_name",""),
                "portal":      "www",
                "series":      fd_raw.get("series"),
                "dividends":   fd_raw.get("dividends",[]),
                "metrics":     fd_raw.get("metrics",{}),
                "error":       fd_raw.get("error"),
                "warning":     fd_raw.get("warning"),
                "status":      _status,
                "moneydj_raw": fd_raw,
                "page_type":   _t2_page_type,
                # v18.18: 補上 metadata 讓 Tab5 「資料診斷」footer 顯示完整
                "is_core":     _is_core_fund(fd_raw.get("fund_name","") or fd_raw.get("full_key","")),
                "currency":    fd_raw.get("currency","") or fd_raw.get("metrics",{}).get("currency",""),
            }
            # v18.272：記錄到「曾經查過的基金清單」（Tab6 說明書顯示）
            try:
                from services.fund_history import record_fund as _rec_fh
                _rec_fh(
                    fd_raw.get("full_key", ""),
                    fd_raw.get("fund_name", ""),
                    source="Tab2",
                )
            except Exception:
                pass  # 紀錄失敗不影響主流程
            _update_data_registry()
            if fd_raw.get("error"):
                st.error(f"❌ {fd_raw['error']}")
            elif _status == "partial":
                _p_fn = fd_raw.get("fund_name","") or fd_raw.get("full_key","")
                st.warning(f"🟡 **{_p_fn}** — 部分資料（歷史淨值未取得，詳情見下方）")
            elif _status == "complete":
                _c_fn = fd_raw.get("fund_name","") or fd_raw.get("full_key","")
                _c_n  = len(fd_raw.get("series")) if fd_raw.get("series") is not None else 0
                st.success(f"✅ **{_c_fn}** ｜ 淨值 {_c_n} 筆 資料已載入")
                # v19.359 Track 2:App 抓成功 → 把當日最新 NAV append 進 Google Sheet
                # nav_history 分頁(從現在累積,解 CI 端抓不到歷史的困境)。冪等 + 非致命。
                try:
                    from ui.helpers.nav_history_hook import record_fund_nav_point
                    record_fund_nav_point(fd_raw, source="Tab2")
                except Exception:
                    pass  # 記錄失敗不影響主流程(helper 內已顯示提示)

                # ── 2026-08-11:累積「有沒有真的讓序列變長」──────────────────
                # 上面那行只說「本次新存 N 筆」（寫入成功），但寫入成功 ≠ 序列變長。
                # `_merge_nav_history_series` 在「累到的點還全落在 live 窗內」時
                # 不會加長序列（added=0），而在此之前**畫面上完全看不出來** ——
                # 使用者只會看到 Sharpe/σ/MaxDD 一直留白卻不知道進度到哪(§1/§5)。
                _nh_tr = next(
                    (_t for _t in (fd_raw.get("source_trace") or [])
                     if isinstance(_t, dict) and _t.get("source") == "nav_history_merge"),
                    None)
                if _nh_tr and _nh_tr.get("note"):
                    st.caption(("✅ " if _nh_tr.get("merged") else "⏳ ") + _nh_tr["note"])

    # ── 關鍵字搜尋（折疊）──
    with st.expander("🔍 關鍵字搜尋境外基金（TDCC / FundClear）", expanded=False):
        c_kw, c_btn = st.columns([4,1])
        with c_kw:
            keyword = st.text_input("基金關鍵字", placeholder="安聯、收益成長、摩根、聯博...",
                label_visibility="collapsed", key="fund_keyword")
        with c_btn:
            do_search = st.button("🔍 搜尋", type="primary", use_container_width=True, key="btn_search")
        if do_search and keyword.strip():
            with st.spinner(f"搜尋「{keyword}」中..."):
                results = tdcc_search_fund(keyword.strip())
                st.session_state.tdcc_results = results
                if not results:
                    st.warning("⚠️ 查無結果，請直接使用上方 MoneyDJ 網址輸入")
                else:
                    st.success(f"✅ 找到 {len(results)} 檔基金")
        results = st.session_state.get("tdcc_results",[])
        if results:
            options = {f"{r.get('基金名稱','')} | {r.get('基金代碼','')}": r for r in results}
            sel = st.selectbox(f"選擇基金（{len(results)} 筆）", list(options.keys()), key="tdcc_select")
            fc  = options[sel].get("基金代碼","")
            st.info(f"💡 代碼：**{fc}** → 在上方輸入框貼入代碼即可分析")

    # ── 分析結果 ──
    fd = st.session_state.fund_data
    if fd:
        _status_fd = fd.get("status","")
        # v18.118 issue 1: partial 狀態（歷史 series 未取得）禁止顯示部分舊資料
        # 之前 partial 仍渲染 nav / metrics / chart → 使用者誤以為「已下載」
        # 修正：partial 比照 failed 處理，要求重新嘗試，不顯示誤導性的單點 metadata
        if _status_fd == "failed":
            st.error(f"❌ 資料抓取失敗：{fd.get('error','未知錯誤')}")
        elif _status_fd == "partial":
            # v19.60：partial = MoneyDJ 已抓到 perf/risk_metrics，僅 NAV 歷史序列失敗。
            # 紅色 st.error 與下方成功顯示的風險/績效表自相矛盾 → 降為黃色 warning。
            _p_fn = fd.get("fund_name", "") or fd.get("full_key", "")
            st.warning(
                f"⚠️ **{_p_fn}** — 部分數據已取得（歷史淨值序列未取得）\n\n"
                f"系統已抓到基本資料 / 績效 / 風險指標，下方可繼續查看。\n"
                f"但 Sharpe / σ 買賣點 / 配息率等需完整 NAV 歷史的核心分析會略過。\n\n"
                f"**建議操作**：\n"
                f"- 點擊「🔄 重新下載」按鈕重試（網路波動常見）\n"
                f"- 確認 MoneyDJ 代碼正確（境外基金需用 wb01 頁面代碼）\n"
                f"- 若連續失敗，可至「📋 保單管理」改抓 FundClear 備援"
            )
            # v18.119/120 issue 4: 抓取診斷 — 列出哪些欄位有 / 沒有 + NAS Proxy 狀態
            # 摺疊處置(原則 1):這一區只在 partial 狀態出現,而 partial 的**唯一用途**
            # 就是回答「到底哪個源失敗」。把它裝進一個永遠展開的摺疊殼,等於在最需要
            # 被讀的診斷資訊外面多包一層裝飾邊框。改標題 + container 直接攤平。
            st.markdown("##### 🔍 抓取診斷細節（哪個源失敗 + NAS Proxy 狀態）")
            with st.container():
                _mj_raw    = fd.get("moneydj_raw", {}) or {}
                _series    = fd.get("series")
                _series_n  = (len(_series) if _series is not None
                              and hasattr(_series, "__len__") else 0)
                _has_metrics = bool(fd.get("metrics"))
                _has_risk    = bool(_mj_raw.get("risk_metrics"))
                _has_div     = bool(fd.get("dividends"))
                _raw_warn = fd.get("warning") or _mj_raw.get("warning", "") or "—"
                _raw_err  = fd.get("error")   or _mj_raw.get("error",  "") or "—"
                # v18.120: NAS Proxy 狀態檢測（issue 4 user 切到 NAS 後仍失敗）
                try:
                    from infra.proxy import get_proxy_config as _gpc
                    _pxy_cfg = _gpc()
                    if _pxy_cfg:
                        _pxy_url = _pxy_cfg.get("https", "—")
                        # 隱藏密碼
                        import re as _re_pxy
                        _pxy_safe = _re_pxy.sub(
                            r"//[^:]+:[^@]+@", "//****:****@", _pxy_url)
                        _pxy_line = f"NAS Proxy: ✅ {_pxy_safe}"
                    else:
                        _pxy_line = "NAS Proxy: ❌ 未設定（走直連，Cloud IP 可能被封）"
                except Exception as _e_pxy:
                    _pxy_line = f"NAS Proxy: ⚠️ 讀取失敗 ({type(_e_pxy).__name__})"
                # v19.193 SSOT:呼叫 portfolio_service.get_factor_availability(),
                # 確保診斷 ✅/❌ ↔ calc_fund_factor_score 實際納入 factor 1-1 對齊。
                # 修正 v19.191 inline 走岔(mgmt_fee="N/A"/expense_ratio=0/tr1y="abc"/
                # annual_div_rate=None 等 case 的 ✅/❌ 偏差)。
                from services.portfolio_service import get_factor_availability as _gfa
                _m_diag = fd.get("metrics") or {}
                # 若 fd 未帶 risk_table 但 moneydj_raw 有 → 補上,匹配 calc_fund_factor_score
                # caller 慣例。
                _avail_fd = dict(fd)
                if "perf" not in _avail_fd:
                    _avail_fd["perf"] = _mj_raw.get("perf") or {}
                _avail = _gfa(_avail_fd, risk_table=_mj_raw.get("risk_metrics"))
                def _mk_bool(b: bool) -> str:
                    return "✅" if b else "—"
                _adv_3y = _m_diag.get("ret_3y_ann")
                _adv_5y = _m_diag.get("ret_5y_ann")
                def _mk(v):
                    return "✅" if v is not None else "—"
                # 必修 4:門檻文案改**直接 import SSOT 常數**渲染,不再寫死數字。
                # 舊文案寫的樣本門檻(60)與 Calmar 的一年期退路皆已過時
                # ⚠️ 本註解**刻意不引用舊文案原字串** —— `test_stale_threshold_copy_removed`
                #    是對整檔原始碼做子字串掃描,註解裡引用等於自己讓自己紅。
                # (實際 250 / 756,且 1Y fallback 已取消)→ user 看到「我有 100 筆
                # 應該夠」但畫面顯示「—」= §1 要防的「無法察覺的矛盾」。
                from services.fund_service import (
                    MIN_DOWNSIDE_OBS_SORTINO as _MIN_DOWN,
                    MIN_OBS_CALMAR as _MIN_CALMAR,
                    MIN_OBS_MAX_DRAWDOWN as _MIN_MDD,
                    MIN_OBS_SHARPE_SORTINO as _MIN_SS,
                )
                st.code(
                    f"{_pxy_line}\n"
                    f"────────────────────────\n"
                    f"狀態: {_status_fd}\n"
                    f"基金名稱: {_p_fn or '（未抓到）'}\n"
                    f"NAV 序列: {_series_n} 筆 "
                    f"{'✅' if _series_n >= 10 else '❌ (需 ≥10)'}\n"
                    f"指標 (calc_metrics): {'✅' if _has_metrics else '❌'}\n"
                    f"風險指標 (wb07):     {'✅' if _has_risk    else '❌'}\n"
                    f"配息歷史 (wb05):     {'✅' if _has_div     else '❌'}\n"
                    f"最新淨值: {_mj_raw.get('nav_latest', '—')}\n"
                    f"基金類別: {_mj_raw.get('fund_type',  '—')}\n"
                    f"page_type: {fd.get('page_type', '—')}\n"
                    f"────────────────────────\n"
                    f"📊 進階指標(對齊 calc_fund_factor_score SSOT):\n"
                    f"  Sortino:     {_mk_bool(_avail['Sortino'])}  "
                    f"(需 ≥{_MIN_SS} 交易日 + ≥{_MIN_DOWN} 筆低於 MAR 的報酬)\n"
                    f"  Calmar:      {_mk_bool(_avail['Calmar'])}  "
                    f"(需 ≥{_MIN_CALMAR} 交易日 = 3Y;**無** 1Y fallback)\n"
                    f"  Max DD:      {_mk(_m_diag.get('max_drawdown'))}  "
                    f"(需 ≥{_MIN_MDD} 交易日)\n"
                    f"  Alpha:       {_mk_bool(_avail['Alpha'])}  (perf.1Y 可解析;adr 預設 0)\n"
                    f"  費用率:      {_mk_bool(_avail['ExpenseRatio'])}  (arg/expense_ratio/mgmt_fee float 可解析)\n"
                    f"  3Y 年化:     {_mk(_adv_3y)}  (需 NAV ≥ 3 年,非 6F factor)\n"
                    f"  5Y 年化:     {_mk(_adv_5y)}  (需 NAV ≥ 5 年,非 6F factor)\n"
                    f"────────────────────────\n"
                    f"warning: {_raw_warn}\n"
                    f"error:   {_raw_err}",
                    language=None,
                )
                st.caption(
                    "📌 **判讀**：\n"
                    "- Proxy ✅ + page_type yp010000 + NAV=0 → 路由錯（境外基金抓到境內頁）\n"
                    "- Proxy ✅ + page_type yp010001 + NAV=0 → 源真壞或 NAS 不通該基金\n"
                    "- Proxy ❌ → 至 Streamlit Cloud secrets 加 PROXY_URL = \"http://user:pwd@host:3128\""
                )
        else:
            s    = fd.get("series"); m = fd.get("metrics",{}); divs = fd.get("dividends",[])
            name = fd.get("fund_name",""); fk = fd.get("full_key","")
            mj_raw = fd.get("moneydj_raw",{}) or {}

            if s is None or (hasattr(s,"empty") and s.empty) or not m:
                # ── 部分資料視圖（series 缺失時仍顯示可用資訊）────────
                _p_name  = name or fk
                _p_nav   = mj_raw.get("nav_latest")
                _p_risk  = (mj_raw.get("risk_metrics") or {})
                _p_perf  = (mj_raw.get("perf") or {})
                _p_err   = fd.get("error") or fd.get("warning") or ""
                _p_cat   = mj_raw.get("category","")
                _p_fee   = mj_raw.get("mgmt_fee","")

                st.markdown(
                    f"<div style='background:{BG_DARK_AMBER_3};border:1px solid {MATERIAL_ORANGE};"
                    f"border-radius:10px;padding:14px 18px;margin:8px 0'>"
                    f"<div style='color:{MATERIAL_ORANGE};font-weight:700;font-size:13px;margin-bottom:8px'>"
                    f"🟡 部分資料（歷史淨值序列未取得，下方顯示已有資訊）</div>"
                    + (f"<div style='color:{GRAY_CC};font-size:11px;margin-bottom:6px'>{_p_err}</div>"
                       if _p_err else "")
                    + (f"<div style='color:{TRAFFIC_NEUTRAL};font-size:11px;border-top:1px solid {BG_DARK_AMBER_1};padding-top:8px;margin-top:4px'>"
                    f"💡 系統已自動嘗試境內/境外雙路由。若仍失敗，可直接貼入完整 MoneyDJ 網址：<br>"
                    f"境內：<code>yp010000.djhtm?a={fk}</code>　"
                    f"境外：<code>yp010001.djhtm?a={fk}</code></div>"
                    f"</div>"),
                    unsafe_allow_html=True)

                # 顯示已取得的基本資料
                _pc1, _pc2, _pc3 = st.columns(3)
                with _pc1:
                    # v19.331 review 修正:MoneyDJ 失敗時 nav_latest 常為 "—"/"N/A"/"查無資料"
                    # (非 None)→ 原裸 float() 轉型直接 ValueError,partial 視圖整頁炸。
                    # 改 safe_float(SSOT shared/converters):非數值顯示 N/A,不造假不炸頁。
                    _p_nav_f = _safe_float(_p_nav)
                    if _p_nav_f is not None:
                        st.metric("最新淨值", f"{_p_nav_f:.4f}")
                    else:
                        st.metric("最新淨值", "N/A")
                with _pc2:
                    st.metric("基金類別", _p_cat[:12] or "N/A")
                with _pc3:
                    st.metric("最高經理費", _p_fee or "N/A")

                # 若有風險指標，仍顯示
                if _p_risk.get("risk_table"):
                    st.markdown("#### 📊 風險指標（已取得）")
                    # v19.336 M9:與 complete 視圖共用 _risk_1y_rows_html(原兩套同款 HTML)
                    st.markdown(_risk_1y_rows_html(_p_risk["risk_table"]),
                                unsafe_allow_html=True)

                # 若有績效數據，顯示
                if _p_perf:
                    st.markdown("#### 📈 績效數據（已取得）")
                    _perf_cols = st.columns(len(_p_perf))
                    for _pi, (_pk, _pv) in enumerate(list(_p_perf.items())[:4]):
                        _perf_cols[_pi].metric(f"報酬率({_pk})", f"{_pv:.2f}%" if isinstance(_pv,(int,float)) else str(_pv))
            else:
                st.markdown("### ① 基本資料 & 淨值趨勢")
                # v19.283:NAV 來源 + 跨度攤在最顯眼處(不藏進 expander)。
                # 背景:user 反饋 TLZF9「成立 0.1 年」查無資料位置 → 根因是
                # _fetch_fund_single 用「筆數」把關導致短源(如 insurance_subdomain
                # ~1 月)搶先鎖定,連 span-extend(v19.281)有無觸發都無從得知。
                # 直接顯示 data_source(哪個 SSOT 來源贏)+ nav_span_days(v19.281
                # fund_orchestration._fetch_fund_single 算好、存在 result 裡的既有
                # 欄位,此處純讀取顯示,不重算 — 對齊 SSOT)。
                # §4.1 單位陷阱:基金 NAV 一律是**原幣**。ZAR / JPY 計價的基金
                # NAV 數量級是幾十~幾百,不標幣別會被直接當成新台幣讀。
                from services.currency import normalize_ccy as _norm_ccy_disp
                _ccy_lbl = _norm_ccy_disp(
                    mj_raw.get("currency") or fd.get("currency") or "", default="")
                _ccy_sfx = f" {_ccy_lbl}" if _ccy_lbl else ""

                _nav_src = mj_raw.get("data_source") or "—"
                _nav_span_d = mj_raw.get("nav_span_days")
                _nav_span_txt = (
                    f" ‧ 跨度 {_nav_span_d} 天(≈{_nav_span_d / 365.25:.1f} 年)"
                    if isinstance(_nav_span_d, (int, float)) else ""
                )
                st.success(
                    f"✅ **{name or fk}** ｜ 淨值 {len(s)} 筆 ‧ 配息 {len(divs)} 筆"
                    f" ‧ 來源:`{_nav_src}`{_nav_span_txt}"
                )

                # 稀疏序列揭露(§1):fund_service 併入累積 NAV 歷史後若判定序列稀疏,
                # 會**真的把** sortino / calmar / 自算 sharpe / std_1y~5y 打成 None。
                # 這件事原本 production 端 0 consumer —— user 只看到欄位變「—」,
                # 不知道是「我們主動砍掉不給假精確」而非「壞掉」。此處接出來。
                _sparse_meta = (m or {}).get("nav_coverage") or {}
                if (m or {}).get("is_sparse"):
                    _sp_cov = _sparse_meta.get("coverage")
                    _sp_gap = _sparse_meta.get("max_gap_days")
                    _sp_extra = ""
                    if isinstance(_sp_cov, (int, float)):
                        _sp_extra = f"（覆蓋率 {_sp_cov:.0%}"
                        if isinstance(_sp_gap, (int, float)):
                            _sp_extra += f"、最大缺口 {_sp_gap} 天"
                        _sp_extra += "）"
                    st.warning(
                        f"⚠️ **本檔 NAV 序列稀疏{_sp_extra}，部分年化指標已被主動移除**\n\n"
                        f"{(m or {}).get('sparse_reason') or ''}\n\n"
                        "說明：稀疏序列算出來的年化波動 / Sharpe / Sortino / Calmar 會是"
                        "**假精確**（缺口愈大、年化倍率放得愈誇張），因此寧可顯示「—」也不給數字。"
                        "MoneyDJ wb07 官方欄位用的是完整日資料，不受影響，仍會照常顯示。"
                    )

                # v19.62 E3：MoneyDJ 資料新鮮度條（單檔，鏡像 Tab5 / Stock 個股）
                try:
                    from ui.helpers.freshness import (
                        nav_age_emoji as _nav_age_emoji,
                        render_mj_freshness_banner,
                    )
                    # 淨值日 / 抓取時戳兩個欄位是 fetcher 寫在 **moneydj_raw** 裡的
                    # (fund_orchestration 產出),session_state.fund_data 那層字面量從來
                    # 沒抄過去 → 這條 banner 在本 Tab 一直是「⬜ ?/—/—」。Tab⑤ 組合層
                    # 本來就是從 moneydj_raw 取,這裡對齊它;fd 層留作向後相容 fallback。
                    _nav_d_show = (mj_raw.get("nav_date", "")
                                   or fd.get("nav_date", ""))
                    render_mj_freshness_banner([{
                        "code": fk or fd.get("fund_code", "?"),
                        "name": name or fk,
                        "nav_date": _nav_d_show,
                        "fetched_at": (mj_raw.get("_moneydj_fetched_at", "")
                                       or fd.get("_moneydj_fetched_at", "")),
                    }])
                    # 上面那條綠色「資料已載入」講的是「抓到幾筆」,不是「資料有多新」。
                    # 停售 / 清算的基金淨值可能停在幾個月前,而下方買賣點、σ 位階、
                    # 「可分批承接」全部照算 —— 那些結論其實是對一個過期價格下的。
                    # 燈號一旦轉黃/紅就明講,不讓成功列獨自代表狀態。
                    _fresh_emoji, _fresh_age = _nav_age_emoji(_nav_d_show)
                    if _fresh_emoji == "🔴":
                        st.error(
                            f"🔴 **最新淨值日期為 {_nav_d_show}（距今 {_fresh_age} 天）** —— "
                            "下方買賣點訊號、σ 位階、超跌判定都是用這個過期淨值算的，"
                            "不代表現在的價格。基金 NAV 正常是 T+1~T+3 公布；若延遲遠超過這個範圍，"
                            "常見原因是該檔已停售 / 清算，或這個來源不再更新。請先確認基金狀態再看下方結論。"
                        )
                    elif _fresh_emoji == "⬜":
                        st.warning(
                            "⬜ **取不到最新淨值日期** —— 無法判斷下方訊號用的是幾號的價格。"
                            "資料來源沒有回傳淨值日欄位，請把下方結論當作參考而非即時判斷。"
                        )
                except Exception as _e_fresh:
                    # v19.346 §3.3:原靜默吞 — 輔助 UI 壞了不擋主流程,但須留痕
                    import sys as _sys_fr
                    print(f'[tab2/freshness] 新鮮度條渲染失敗: '
                          f'{type(_e_fresh).__name__}: {_e_fresh}', file=_sys_fr.stderr)

                # v19.65 I2：單檔 ↔ 組合持倉聯動（讀 Tab3 portfolio_funds，跨 Tab 訊號）
                try:
                    from ui.helpers.portfolio_linkage import render_fund_portfolio_membership
                    render_fund_portfolio_membership(
                        st.session_state,
                        fund_codes=[fk, fd.get("fund_code", ""), fd.get("full_key", "")],
                        fund_name=name,
                    )
                except Exception as _e_link:
                    # v19.346 §3.3:原靜默吞 — 跨 Tab 聯動為輔助訊號,壞了留痕不擋主流程
                    import sys as _sys_lk
                    print(f'[tab2/linkage] 組合持倉聯動渲染失敗: '
                          f'{type(_e_link).__name__}: {_e_link}', file=_sys_lk.stderr)

                # MK 訊號卡片
                phase_info_s = st.session_state.phase_info if st.session_state.macro_done else None
                if phase_info_s:
                    sig = mk_fund_signal(fd, phase_info_s["phase"], phase_info_s["score"])
                    _aa = sig.get("auto_alloc")
                    if _aa:
                        _aa_stk, _aa_bnd, _aa_lbl, _aa_c = _aa
                        st.markdown(f"<div style='background:{BG_DARK_NAVY_1};border:1px solid {_aa_c};border-radius:8px;padding:8px 14px;margin:4px 0 8px 0;display:flex;align-items:center;gap:16px'>"
                            f"<span>📊</span><div><div style='color:{_aa_c};font-weight:700;font-size:12px'>總經自動配比建議：{_aa_lbl}</div>"
                            f"<div style='color:{GRAY_CC};font-size:12px'>股 {_aa_stk}% ／ 債 {_aa_bnd}%</div></div></div>", unsafe_allow_html=True)
                    _sig_style = sig["sig_style"]
                    # v19.273 Phase 2 TOP 2.1:卡片外框走 gh_card chrome SSOT(byte-identical)
                    from ui.components.cards import gh_card
                    from ui.helpers.macro_helpers import format_phase_score  # v19.403 景氣位階 SSOT
                    st.markdown(gh_card(
                        f"<div><div style='color:{TRAFFIC_NEUTRAL};font-size:11px'>資產屬性</div><div style='font-size:14px;font-weight:700;color:{INFO_BLUE}'>{sig['asset_class']}</div></div>"
                        f"<div><div style='color:{TRAFFIC_NEUTRAL};font-size:11px'>策略3 操作訊號</div><span style='{_sig_style};padding:4px 12px;border-radius:20px;font-size:13px;font-weight:700;display:inline-block'>{sig['label']}</span></div>"
                        f"<div style='flex:1'><div style='color:{TRAFFIC_NEUTRAL};font-size:11px'>景氣位階（{format_phase_score(phase_info_s)}）</div>"
                        f"<div style='font-size:12px;color:{GH_FG_SECONDARY}'>{sig['reason']}</div></div>",
                        radius=10, padding="14px 18px", margin="8px 0",
                        extra="display:flex;align-items:center;gap:16px;flex-wrap:wrap",
                    ), unsafe_allow_html=True)

                # 淨值走勢圖（Bollinger Bands + 配息標記 v2.0 + V5 三合一）
                # V5: 微觀防護盾掃描後才出現右側三率動能柱（未掃描時主圖佔滿全寬）
                _shield_for_render = st.session_state.get(f"shield_{fk}")
                if _shield_for_render:
                    _v5_chart_col, _v5_mini_col = st.columns([3, 1])
                else:
                    _v5_chart_col = st.container()
                    _v5_mini_col = None
                with _v5_chart_col:
                    st.markdown("### 📈 三合一趨勢診斷圖")
                df_show = s.reset_index(); df_show.columns = ["date","nav"]
                fig_n = go.Figure()

                # ── Bollinger Bands（MA20 ±2σ，半透明填色）──────────────
                _bb_period = min(20, len(s))
                _bb_ma  = s.rolling(_bb_period).mean()
                _bb_std = s.rolling(_bb_period).std()
                _bb_up  = (_bb_ma + 2 * _bb_std).dropna()
                _bb_dn  = (_bb_ma - 2 * _bb_std).dropna()
                # v19.312 §1 Fail-Loud：帶點 < 2 時畫不出通道(tonexty 填色至少需 2 點成線;
                # rolling(20) 需 ≥21 個 NAV 點)→ 明講「資料不足」,不再默默省略讓 user 以為功能壞掉。
                _bb_drawable = len(_bb_up) >= 2 and len(_bb_dn) >= 2
                if _bb_drawable:
                    # 上軌（填色基準，先畫，不顯示圖例線條）
                    fig_n.add_trace(go.Scatter(
                        x=_bb_up.index, y=_bb_up.values, name="BB上軌",
                        line=dict(color="rgba(33,150,243,0.25)", width=1),
                        showlegend=False))
                    # 下軌 + fill to 上軌（半透明藍色通道）
                    fig_n.add_trace(go.Scatter(
                        x=_bb_dn.index, y=_bb_dn.values, name="布林通道(±2σ)",
                        fill="tonexty",
                        fillcolor="rgba(33,150,243,0.08)",
                        line=dict(color="rgba(33,150,243,0.25)", width=1)))
                else:
                    st.caption(
                        f"⚠️ 布林通道(±2σ)無法繪製 — 本檔 NAV 歷史僅 {len(s)} 點,"
                        "需 ≥21 點(20 日窗口)。此為**資料不足**非功能故障,"
                        "NAV 歷史補足後自動恢復。")
                # MA20 中軌
                fig_n.add_trace(go.Scatter(
                    x=_bb_ma.dropna().index, y=_bb_ma.dropna().values,
                    name="MA20", line=dict(color=MATERIAL_ORANGE, width=1, dash="dot")))
                # MA60（v19.343 A~E 3c：新基金 <60 NAV 點時 rolling(60) 全 NaN →
                # dropna 後 trace 空 = 靜默消失。對齊上方 MA20/布林的 §1 Fail-Loud
                # 模式:明講「資料不足」而非默默省略,避免 user 以為 MA60 功能壞掉。
                # 不用動態縮窗偽裝(縮到 30 點的線標「MA60」會誤導,且與 MA20 概念重疊)。
                if len(s) >= 60:
                    _ma60 = s.rolling(60).mean()
                    fig_n.add_trace(go.Scatter(
                        x=_ma60.dropna().index, y=_ma60.dropna().values,
                        name="MA60", line=dict(color=MD_PURPLE_500, width=1, dash="dot")))
                else:
                    st.caption(
                        f"⚠️ MA60 均線未繪製 — 本檔 NAV 歷史僅 {len(s)} 點,需 ≥60 點。"
                        "此為**資料不足**非功能故障,NAV 歷史補足後自動顯示。")
                # 淨值主線（純線；不再 fill 到 0 以免 y 軸被自動拉到 0 壓扁走勢）
                fig_n.add_trace(go.Scatter(
                    x=df_show["date"], y=df_show["nav"],
                    name="淨值", mode="lines",
                    line=dict(color=MD_BLUE_500, width=2)))

                # ── 配息標記 💰（除息日垂直虛線 + marker）───────────────
                _chart_divs = mj_raw.get("dividends") or []
                _chart_divs = _chart_divs if isinstance(_chart_divs, list) else []
                _div_dates, _div_navs, _div_texts = [], [], []
                for _cd in _chart_divs:
                    try:
                        _cd_date = pd.Timestamp(_cd.get("date",""))
                        if _cd_date in s.index:
                            _cd_nav = float(s.loc[_cd_date])
                        else:
                            # 找最近交易日
                            _near = s.index[s.index.get_indexer([_cd_date], method="nearest")[0]]
                            _cd_nav = float(s.loc[_near])
                            _cd_date = _near
                        _cd_amt = _cd.get("amount") or _cd.get("dividend") or ""
                        _div_dates.append(_cd_date)
                        _div_navs.append(_cd_nav)
                        _div_texts.append(f"💰 配息 {_cd_amt}" if _cd_amt else "💰 配息")
                    except Exception:
                        continue
                if _div_dates:
                    fig_n.add_trace(go.Scatter(
                        x=_div_dates, y=_div_navs,
                        # v19.392 V4b:去每點 💰 標籤(月配 3 年 30+ 個重疊,dataviz #5)。所有配息點
                        # 仍以三角標記全數呈現,配息金額改由 hover(%{text})顯示 —— 零資料遺失。
                        mode="markers",
                        name="配息日",
                        marker=dict(symbol="triangle-up", size=10, color="#ffd600"),
                        text=_div_texts,
                        hovertemplate="%{text}<br>淨值：%{y:.4f}<extra></extra>"))

                # ── MK v3.2 買賣水平線（回歸中樞 ± kσ；σ=近1年淨值統計標準差）────
                for bv, bl, bc in [
                    (m.get("buy1"), "買1 小跌(中樞-1σ)", MD_GREEN_A200),
                    (m.get("buy2"), "買2 急跌(中樞-2σ)", MATERIAL_GREEN),
                    (m.get("buy3"), "買3 大跌(中樞-3σ)", MD_PURPLE_500),
                ]:
                    if bv:
                        fig_n.add_hline(y=bv, line_color=bc, line_dash="dot",
                                        annotation_text=bl, annotation_font_color=bc,
                                        annotation_position="bottom right")
                for sv, sl, sc in [
                    (m.get("sell1"), "賣1 小漲(中樞+1σ)", WARN_AMBER),
                    (m.get("sell2"), "賣2 急漲(中樞+2σ)", MD_DEEP_ORANGE_400),
                    (m.get("sell3"), "賣3 大漲(中樞+3σ)", MATERIAL_RED),
                ]:
                    if sv:
                        fig_n.add_hline(y=sv, line_color=sc, line_dash="dash",
                                        annotation_text=sl, annotation_font_color=sc,
                                        annotation_position="top right")
                # 年高/年低參考線（區間脈絡；非 band 錨點）— A+B 的 A 面
                for _rv, _rl in [(m.get("high_1y"), "年高"), (m.get("low_1y"), "年低")]:
                    if _rv:
                        fig_n.add_hline(y=float(_rv), line_color=TRAFFIC_NEUTRAL,
                                        line_dash="longdash", line_width=1, opacity=0.55,
                                        annotation_text=_rl, annotation_font_color=TRAFFIC_NEUTRAL,
                                        annotation_font_size=9, annotation_position="top left")

                # ── y 軸範圍：取 NAV / BB / 買賣線 / 年高低整體 min-max，留 5% 邊界 ──
                _y_vals = [float(v) for v in df_show["nav"].dropna().values]
                if len(_bb_up) > 0: _y_vals += [float(v) for v in _bb_up.values if pd.notna(v)]
                if len(_bb_dn) > 0: _y_vals += [float(v) for v in _bb_dn.values if pd.notna(v)]
                for _hv in (m.get("buy1"), m.get("buy2"), m.get("buy3"),
                            m.get("sell1"), m.get("sell2"), m.get("sell3"),
                            m.get("high_1y"), m.get("low_1y")):
                    if _hv: _y_vals.append(float(_hv))
                if _y_vals:
                    _y_min, _y_max = min(_y_vals), max(_y_vals)
                    _y_pad = max((_y_max - _y_min) * 0.05, _y_max * 0.005, 1e-4)
                    _y_range = [_y_min - _y_pad, _y_max + _y_pad]
                else:
                    _y_range = None

                fig_n.update_layout(
                    paper_bgcolor=STREAMLIT_BG, plot_bgcolor=GH_BG_CARD,
                    font_color=GH_FG_PRIMARY, height=420,
                    margin=dict(t=15, b=30, l=40, r=20),
                    legend=dict(orientation="h", font_size=10, y=1.02),
                    hovermode="x unified",
                    yaxis_title=f"淨值（原幣{_ccy_sfx}）" if _ccy_lbl else "淨值（原幣）")
                if _y_range:
                    fig_n.update_yaxes(range=_y_range)
                # 左側主圖放入 column 中
                with _v5_chart_col:
                    st.plotly_chart(fig_n, use_container_width=True)
                    # v19.404 Phase 3:旗艦三合一圖補「怎麼看」(原無解讀線,新手看不懂整張圖)
                    st.caption(
                        "💡 **怎麼看**:藍線=淨值。碰綠色買線(中樞−σ)=分批進場區、碰紅/橘賣線"
                        "(中樞+σ)=停利區;跌破布林下軌=短期超跌;MA20/MA60 向上=中期趨勢健康,"
                        "黃三角=配息日。"
                    )

                # ── 右側側邊：持倉三率動能柱（僅在掃描後顯示）─────────────
                if _v5_mini_col is not None:
                    with _v5_mini_col:
                        st.markdown("**📊 三率動能**")
                        _mini_shield = _shield_for_render
                        # §1:原寫法 `r.get(k, 0) or 0` 把「這檔沒解析到該項比率」
                        # 當成「變化 0%」除進分母 —— 10 檔只解析到 3 檔時,平均值被
                        # 7 個假 0 拉平,畫面卻寫「三率持平」,user 讀成全持倉結論。
                        # 改成:每一項各自只對**真的有值**的持股平均,分母寫在標籤上。
                        _MINI_SPEC = [("毛利率", "gross_margin_diff"),
                                      ("營益率", "op_margin_diff"),
                                      ("淨利率", "net_margin_diff")]
                        _mini_x, _mini_y, _mini_missing = [], [], []
                        for _mlbl, _mkey in _MINI_SPEC:
                            _vals = [float(r.get(_mkey)) for r in _mini_shield
                                     if isinstance(r.get(_mkey), (int, float))]
                            if _vals:
                                _mini_x.append(f"{_mlbl}({len(_vals)})")
                                _mini_y.append(sum(_vals) / len(_vals))
                            else:
                                _mini_missing.append(_mlbl)
                        if _mini_y:
                            _mini_colors = [
                                MATERIAL_GREEN if v > 0.5 else (MATERIAL_RED if v < -0.5 else MATERIAL_ORANGE)
                                for v in _mini_y]
                            fig_mini = go.Figure(go.Bar(
                                x=_mini_x,
                                y=_mini_y,
                                marker_color=_mini_colors,
                                text=[f"{v:+.1f}%" for v in _mini_y],
                                textposition="outside",
                                textfont=dict(size=10)))
                            fig_mini.add_hline(y=0, line_color=GRAY_55, line_width=1)
                            fig_mini.update_layout(
                                paper_bgcolor=STREAMLIT_BG, plot_bgcolor=GH_BG_CARD,
                                font_color=GH_FG_PRIMARY, height=240,
                                margin=dict(t=10, b=10, l=5, r=5),
                                showlegend=False,
                                yaxis=dict(gridcolor=BG_DARK_NAVY_3, zeroline=False))
                            st.plotly_chart(fig_mini, use_container_width=True)
                        st.caption(
                            f"已解析 {len(_mini_shield)} 檔持倉；括號內為該項**實際有值**"
                            "的檔數（抓不到的不計入分母）。"
                        )
                        if _mini_missing:
                            st.caption(f"⬜ 無任何持股取得：{'、'.join(_mini_missing)}")
                        # 綜合判定只在三項齊備時給 —— 缺項時「合計 > 2」的門檻語意
                        # 不成立(三項合計 vs 兩項合計不是同一把尺)。
                        if len(_mini_y) == len(_MINI_SPEC):
                            _tot_mom = sum(_mini_y)
                            if _tot_mom > 2:
                                st.markdown("🟢 **三率雙升**<br>基本面防護", unsafe_allow_html=True)
                            elif _tot_mom < -2:
                                st.markdown("🔴 **三率衰退**<br>虛漲陷阱", unsafe_allow_html=True)
                            else:
                                st.markdown("🟡 **三率持平**<br>搭配布林研判", unsafe_allow_html=True)
                        else:
                            st.markdown(
                                "⬜ **三率綜合判定資料不足**<br>"
                                "<span style='font-size:10px'>三項未齊，不給假結論</span>",
                                unsafe_allow_html=True)

                # ── 📈 vs 大盤(純價格,重設基期=100 疊圖)── v19.420 user 要求 ──
                try:
                    import sys as _sys_b
                    from services.benchmark_compare import excess_return, rebased_pair
                    from services.capture_ratio import benchmark_for_currency
                    from services.currency import normalize_ccy
                    from ui.helpers.fund_grp_health.capture import _benchmark_nav
                    _ccy_b = normalize_ccy(fd.get("currency"), default="")
                    if s is not None and len(s) >= 2 and _ccy_b:
                        _bmk = benchmark_for_currency(_ccy_b)
                        _bser = _benchmark_nav(_bmk) if _bmk else None
                        if not _bmk:
                            # §4.1 跨幣別:2026-08-06 起 `benchmark_for_currency` 對
                            # TWD/USD 以外的幣別回 None。原因是基金 NAV 是**原幣**,
                            # 拿原幣報酬直接減 USD 計價的 S&P 500,等於把匯率變動算成
                            # 經理人績效 —— 一檔該年幣別貶 12% 的南非幣配息基金會被
                            # 顯示成「跑輸大盤 12 個百分點」,進而誤觸賣出建議。
                            # 這裡誠實留白並說明,不換算、不硬比(§1)。
                            st.caption(
                                f"⬜ 本基金以 {_ccy_b} 計價，本站沒有對應的可比大盤 → "
                                "vs 大盤留白。原幣報酬直接對美股指數會把匯率變動"
                                "算進績效，寧可不比也不給錯的數字。")
                        elif _bser is None or len(_bser) == 0:
                            # §1:基準抓不到 → 明講,不靜默省略(否則 user 以為功能壞掉)
                            st.caption(f"⬜ 暫時取不到大盤（{_bmk}）資料 → 無法比較(稍後重試)。")
                        else:
                            _pair = rebased_pair(s, _bser)
                            _ex = excess_return(s, _bser)
                            _exv = _ex.get("excess_pct")
                            if _pair is None or _pair.empty or _exv is None:
                                st.caption("⬜ 基金與大盤共同期間不足 → 暫無法比較(§1 不假造)。")
                            else:
                                _win = "全期" if _ex.get("full_period") else "近1年"
                                st.markdown(f"### 📈 vs 大盤（{_bmk}，{_win}純價格）")
                                _fig_b = go.Figure()
                                _fig_b.add_trace(go.Scatter(
                                    x=_pair.index, y=_pair["基金"], name="基金",
                                    line=dict(color=MATERIAL_GREEN, width=2)))
                                _fig_b.add_trace(go.Scatter(
                                    x=_pair.index, y=_pair["大盤"], name=f"大盤 {_bmk}",
                                    line=dict(color=GRAY_66, width=1.5, dash="dot")))
                                _fig_b.update_layout(
                                    paper_bgcolor=STREAMLIT_BG, plot_bgcolor=GH_BG_CARD,
                                    font_color=GH_FG_PRIMARY, height=300,
                                    margin=dict(t=10, b=10, l=5, r=5),
                                    hovermode="x unified", yaxis_title="重設基期 = 100",
                                    legend=dict(orientation="h", yanchor="bottom", y=1.02))
                                st.plotly_chart(_fig_b, use_container_width=True)
                                _emo = ("🟢 跑贏" if _exv > 0 else
                                        ("🔴 跑輸" if _exv < 0 else "⚪ 持平"))
                                _fx = ("" if _ccy_b in ("TWD", "USD")
                                       else f"⚠️ {_ccy_b} 原幣 vs 美股指數有匯率噪音。")
                                st.caption(
                                    f"{_emo}大盤 **{_exv:+.1f} 個百分點**（{_win}純價格:"
                                    f"基金 {_ex['fund_pct']:+.1f}% vs 大盤 "
                                    f"{_ex['bench_pct']:+.1f}%）。純淨值對純指數,兩邊皆不含息。{_fx}")
                except Exception as _e_bmk:  # noqa: BLE001 — 疊圖失敗不擋下方信號
                    print(f"[tab2 vs大盤] {type(_e_bmk).__name__}: {_e_bmk}",
                          file=_sys_b.stderr)
                    st.caption(f"⬜ vs 大盤圖失敗:[{type(_e_bmk).__name__}] {str(_e_bmk)[:60]}")

                st.markdown("### ② 買賣點信號（標準差策略）")
                # ── MK 標準差買賣點分析 v3.0（3 買 + 3 賣 + 接近度）──
                _m_buy1 = m.get("buy1"); _m_buy2 = m.get("buy2"); _m_buy3 = m.get("buy3")
                _m_sell1 = m.get("sell1"); _m_sell2 = m.get("sell2"); _m_sell3 = m.get("sell3")
                _m_pl = m.get("pos_label",""); _m_pc = m.get("pos_color",TRAFFIC_NEUTRAL)
                _m_mode = m.get("buy_mode","")  # v19.313: 買賣 band σ 改區間基準,不再標 wb07
                # v19.331 review:safe_float 防占位字串(數值輸入行為不變;字串 → 0 走
                # _proximity_chip 既有 nav_v<=0 → "—" 路徑,不炸不造假)
                _m_nav_v = _safe_float(m.get("nav")) or 0
                # §3.3:fallback 值改吃 shared SSOT(與 fund_service 產出 metrics
                # 時用的是同一個常數),不在 UI 端另刻一份同義 literal。
                _NEAR = _safe_float(m.get("near_threshold_pct")) or _NEAR_PCT_SSOT
                def _proximity_chip(nav_v, target, is_buy):
                    """買: nav≤target 觸發；賣: nav≥target 觸發；±NEAR% 為接近區"""
                    if (not target) or nav_v <= 0:
                        return ("—", GRAY_66, "")
                    delta = (nav_v - target) / target * 100  # 正=高於 target
                    if is_buy:
                        if delta <= 0:           return ("🟢 觸發", MD_GREEN_A400, f"{abs(delta):.2f}% 已破")
                        elif delta <= _NEAR:     return ("⚠️ 接近", WARN_AMBER, f"還差 {delta:.2f}%")
                        else:                    return ("▲ 距離", GRAY_66,    f"還差 {delta:.2f}%")
                    else:
                        if delta >= 0:           return ("🔔 觸發", MATERIAL_RED, f"{delta:.2f}% 已過")
                        elif delta >= -_NEAR:    return ("⚠️ 接近", WARN_AMBER, f"還差 {-delta:.2f}%")
                        else:                    return ("▼ 距離", GRAY_66,    f"還差 {-delta:.2f}%")
                if _m_buy1:
                    _rows = ""
                    for _bv, _bl, _bc, _is_buy in [
                        (_m_buy3,  "💧 大跌大買 (50%) 中樞-3σ", MD_PURPLE_500, True),
                        (_m_buy2,  "💧 急跌穩買 (30%) 中樞-2σ", MATERIAL_GREEN, True),
                        (_m_buy1,  "💧 小跌小買 (20%) 中樞-1σ", MD_GREEN_A200, True),
                        (_m_sell1, "💰 小漲停利 (20%) 中樞+1σ", WARN_AMBER, False),
                        (_m_sell2, "💰 急漲停利 (30%) 中樞+2σ", MD_DEEP_ORANGE_400, False),
                        (_m_sell3, "💰 大漲停利 (50%) 中樞+3σ", MATERIAL_RED, False),
                    ]:
                        if not _bv: continue
                        _chip_lbl, _chip_color, _chip_dist = _proximity_chip(_m_nav_v, _bv, _is_buy)
                        _rows += (f"<div style='display:flex;align-items:center;justify-content:space-between;"
                                  f"padding:5px 12px;background:{GH_BG_PRIMARY};border-radius:6px;margin:3px 0;gap:8px'>"
                                  f"<span style='color:{_bc};font-size:12px;flex:1'>{_bl}</span>"
                                  f"<span style='font-weight:700;font-size:13px;min-width:64px;text-align:right'>{_bv:.4f}</span>"
                                  f"<span style='color:{_chip_color};font-size:11px;min-width:74px;text-align:right;font-weight:600'>{_chip_lbl}</span>"
                                  f"<span style='color:{GRAY_66};font-size:10px;min-width:96px;text-align:right'>{_chip_dist}</span>"
                                  f"</div>")
                    # v19.273 Phase 2 TOP 2.2:σ 買賣點卡外框走 gh_card chrome SSOT(byte-identical)
                    from ui.components.cards import gh_card
                    st.markdown(gh_card(
                        f"<div style='display:flex;align-items:center;justify-content:space-between;margin-bottom:8px'>"
                        f"<span style='color:{TRAFFIC_NEUTRAL};font-size:11px'>📍 策略3 標準差買賣點 v3.2（{_m_mode} ｜ σ=近1年淨值標準差 ｜ 中樞±kσ）</span>"
                        f"<span style='background:{CHIP_BG_NEAR_BLACK};color:{_m_pc};border:1px solid {_m_pc};padding:2px 10px;"
                        f"border-radius:12px;font-size:12px;font-weight:700'>{_m_pl}</span>"
                        f"</div>"
                        + _rows
                        + f"<div style='color:{GRAY_66};font-size:10px;margin-top:6px'>"
                          f"現值 {_m_nav_v:.4f}{_ccy_sfx} ｜ 接近閾值 ±{_NEAR:.1f}%"
                          f" ｜ 上表買賣點皆為原幣{_ccy_sfx or ''}計價，非新台幣</div>",
                        radius=10, padding="12px 16px", margin="10px 0",
                    ), unsafe_allow_html=True)

                # ── V3-3: -2σ 超跌機會卡（布林下軌突破警報）────────────
                _boll_latest_low = float(_bb_dn.iloc[-1]) if len(_bb_dn) > 0 else None
                if _boll_latest_low is not None and _m_nav_v > 0 and _m_nav_v <= _boll_latest_low:
                    st.markdown(
                        f"<div style='background:linear-gradient(135deg,{BG_DARK_GREEN_2},#0d2a0d);"
                        f"border:2px solid {MD_GREEN_A400};border-radius:12px;padding:14px 18px;margin:10px 0'>"
                        f"<div style='color:{MD_GREEN_A400};font-size:14px;font-weight:700;margin-bottom:8px'>"
                        f"⚡ -2σ 超跌機會卡 — 布林下軌突破！</div>"
                        f"<div style='display:flex;gap:24px;flex-wrap:wrap;margin-bottom:8px'>"
                        f"<div><div style='color:{TRAFFIC_NEUTRAL};font-size:10px'>現值 NAV（原幣{_ccy_sfx}）</div>"
                        f"<div style='color:{WHITE};font-weight:700;font-size:16px'>{_m_nav_v:.4f}{_ccy_sfx}</div></div>"
                        f"<div><div style='color:{TRAFFIC_NEUTRAL};font-size:10px'>布林下軌(-2σ)（原幣{_ccy_sfx}）</div>"
                        f"<div style='color:{MD_GREEN_A400};font-weight:700;font-size:16px'>{_boll_latest_low:.4f}{_ccy_sfx}</div></div>"
                        f"<div><div style='color:{TRAFFIC_NEUTRAL};font-size:10px'>跌破幅度</div>"
                        f"<div style='color:{MD_GREEN_A200};font-weight:700;font-size:16px'>"
                        f"{(_boll_latest_low - _m_nav_v) / _boll_latest_low * 100:.2f}%</div></div>"
                        f"</div>"
                        f"<div style='color:{GRAY_AA};font-size:11px;border-top:1px solid #1a3a1a;padding-top:8px'>"
                        f"策略2：布林下軌突破 = 短期非理性超跌，適合左側交易分批承接。"
                        f"建議：小量試單（部位 ≤20%），並設停損於下軌下方 3%。</div>"
                        f"</div>", unsafe_allow_html=True)

                # ── T5: HWM σ 絕對位階卡 ─────────────────────────────────
                if s is not None and len(s) >= 30:
                    try:
                        from services.precision_service import calc_hwm_sigma_levels as _hwm_fn
                        _hwm = _hwm_fn(s, lookback=252)
                        if "error" not in _hwm:
                            _hc = _hwm["color"]
                            _hl = _hwm["label"]
                            _nav_h = _hwm["current_nav"]
                            _hwm_v = _hwm["hwm"]
                            _sig   = _hwm["sigma_abs"]
                            _sr    = _hwm["sigma_rank"]
                            _dist  = _hwm["dist_to_hwm_pct"]
                            _l1, _l2, _l3 = _hwm["level_1s"], _hwm["level_2s"], _hwm["level_3s"]
                            st.markdown(
                                f"<div style='background:{BG_DARK_NAVY_1};border:2px solid {_hc};"
                                f"border-radius:12px;padding:14px 18px;margin:10px 0'>"
                                f"<div style='color:{_hc};font-size:13px;font-weight:800;margin-bottom:10px'>"
                                f"📐 HWM σ 絕對位階 — {_hl}</div>"
                                f"<div style='display:flex;gap:20px;flex-wrap:wrap;margin-bottom:10px'>"
                                f"<div><div style='color:{TRAFFIC_NEUTRAL};font-size:10px'>歷史最高(HWM)（原幣{_ccy_sfx}）</div>"
                                f"<div style='color:{WHITE};font-weight:700;font-size:16px'>{_hwm_v:.4f}{_ccy_sfx}</div></div>"
                                f"<div><div style='color:{TRAFFIC_NEUTRAL};font-size:10px'>現值 NAV（原幣{_ccy_sfx}）</div>"
                                f"<div style='color:{_hc};font-weight:700;font-size:16px'>{_nav_h:.4f}{_ccy_sfx}</div></div>"
                                f"<div><div style='color:{TRAFFIC_NEUTRAL};font-size:10px'>距 HWM</div>"
                                f"<div style='color:{_hc};font-weight:700;font-size:16px'>{_dist:+.2f}%</div></div>"
                                f"<div><div style='color:{TRAFFIC_NEUTRAL};font-size:10px'>σ 位階</div>"
                                f"<div style='color:{_hc};font-weight:700;font-size:16px'>{_sr:+.2f}σ</div></div>"
                                f"</div>"
                                f"<div style='display:flex;gap:12px;flex-wrap:wrap;font-size:11px'>"
                                f"<span style='color:{MD_GREEN_A200}'>HWM-1σ: {_l1:.4f}{_ccy_sfx}</span>"
                                f"<span style='color:{MATERIAL_ORANGE}'>HWM-2σ: {_l2:.4f}{_ccy_sfx}</span>"
                                f"<span style='color:{MATERIAL_RED}'>HWM-3σ: {_l3:.4f}{_ccy_sfx}</span>"
                                f"</div>"
                                f"<div style='color:{GRAY_66};font-size:10px;margin-top:6px'>"
                                f"σ = HWM × 年化日報酬標準差（{len(s)} 筆淨值計算）</div>"
                                f"</div>", unsafe_allow_html=True)
                            # v19.404 Phase 3:補讀法(對齊 risk.py:19-20 group 版,消單一基金缺口)
                            st.caption(
                                "💡 **怎麼看**:σ 位階 ≤ −2σ = 距歷史高點深跌,基本面若健康可分批"
                                "承接;≥ +1σ = 接近前高偏過熱。此為「絕對位階」(對歷史高點),"
                                "與上方買賣線的「相對中樞」互補。"
                            )
                    except Exception:
                        pass  # smoke-allow-pass

                # ── v18.47: 📊 基金健康總覽（4 維度評分 + Overall Grade + 白話結論）──
                # v19.177 #3A+#4B：4D 評分 + grade 全走 services.health.grade.compute_4d_health SSOT,
                # input 走 _resolve_adr_with_fallback / compute_1y_total_return SSOT。
                # 原本 162 行 inline 邏輯(3 套 fallback chain + 4 套 score lookup + grade cutoff)
                # 收斂到 ~30 行,全站個檔健康度評等統一同源。
                try:
                    from services.health.dividend import _resolve_adr_with_fallback
                    from services.health.grade import compute_4d_health
                    from services.fund_total_return import compute_1y_total_return

                    _g_tr1y, _ = compute_1y_total_return({
                        "metrics": m,
                        "moneydj_raw": mj_raw,
                        "series": s,
                        "perf_source": fd.get("perf_source") or mj_raw.get("perf_source"),
                    })
                    _g_dy, _ = _resolve_adr_with_fallback({
                        "moneydj_raw": mj_raw,
                        "metrics": m,
                        "dividends": divs,
                    })
                    # v19.422 Bug2 修:總覽卡對齊 SSOT(build_health_analysis_row / 大表)——
                    # 只用 m.get(移除 risk_table fallback)+ ma_dir=None。原本卡片多算了 60日均線方向
                    # 並多餵 risk_table Sharpe/σ → 走勢分 85 vs SSOT 70 → 同一檔顯示 A vs B(稽核 Bug2)。
                    _g_sharpe = m.get("sharpe")
                    _g_sigma = m.get("std_1y")
                    _4d = compute_4d_health(
                        tr1y_pct=_g_tr1y, adr_pct=_g_dy,
                        sharpe=_g_sharpe, sigma_pct=_g_sigma, ma_dir=None,
                    )
                    _d1_cov = _4d["factors"]["coverage"]
                    _d2_sh = _4d["factors"]["sharpe"]
                    _d3_tr = _4d["factors"]["trend"]
                    _d4_vol = _4d["factors"]["volatility"]
                    _g_overall = _4d["score"]
                    _gr, _gr_c, _verd = _4d["grade"], _4d["grade_color"], _4d["verdict"]
                    _eat_call = (f" ⚠️ <b style='color:{MATERIAL_RED}'>吃本金風險</b>"
                                 if _4d["eat_warn"] else "")

                    def _g_block(label, score):
                        if score is None:
                            return (f"<div><div style='color:{GRAY_66};font-size:10px'>" + label + "</div>"
                                    f"<div style='color:{GRAY_66};font-size:20px;font-weight:700'>—</div>"
                                    f"<div style='color:{GRAY_55};font-size:9px'>資料不足</div></div>")
                        _c = (MATERIAL_GREEN if score >= 75 else MD_GREEN_A200 if score >= 60 else
                              CAUTION_YELLOW if score >= 45 else MATERIAL_ORANGE if score >= 30 else MATERIAL_RED)
                        return (f"<div><div style='color:{TRAFFIC_NEUTRAL};font-size:10px'>{label}</div>"
                                f"<div style='color:{_c};font-size:20px;font-weight:900'>{score:.0f}</div>"
                                f"<div style='color:{GRAY_55};font-size:9px'>/ 100</div></div>")

                    st.markdown(
                        f"<div style='background:linear-gradient(135deg,{GH_BG_PRIMARY},{GH_BG_CARD});"
                        f"border:2px solid {_gr_c};border-radius:12px;padding:14px 18px;margin:8px 0 12px'>"
                        f"<div style='display:flex;align-items:center;gap:16px;margin-bottom:10px;flex-wrap:wrap'>"
                        f"<div style='color:{_gr_c};font-size:46px;font-weight:900;line-height:1'>{_gr}</div>"
                        f"<div style='flex:1;min-width:200px'>"
                        f"<div style='color:{GRAY_AA};font-size:11px'>📊 基金健康總覽</div>"
                        f"<div style='color:{_gr_c};font-size:16px;font-weight:800;margin-top:2px'>{_verd}{_eat_call}</div></div>"
                        f"<div style='color:{TRAFFIC_NEUTRAL};font-size:11px;text-align:right'>"
                        f"綜合評分<br><b style='color:{_gr_c};font-size:18px'>"
                        f"{('—' if _g_overall is None else f'{_g_overall:.0f}')}"
                        f"</b> / 100</div></div>"
                        f"<div style='display:grid;grid-template-columns:repeat(4,1fr);gap:14px;"
                        f"background:#0a0e14;border-radius:8px;padding:10px 14px'>"
                        f"{_g_block('💵 配息健康度', _d1_cov)}"
                        f"{_g_block('📈 風險調整報酬', _d2_sh)}"
                        f"{_g_block('📊 走勢健康', _d3_tr)}"
                        f"{_g_block('🛡️ 低波動性', _d4_vol)}"
                        f"</div></div>", unsafe_allow_html=True)
                except Exception:
                    pass  # smoke-allow-pass — 評分卡失敗不影響後續資訊

                # ── v18.20: 🔴 吃本金 KPI 紅綠燈（獨立 banner，主 KPI 列旁）──
                # 不依賴 divs[] 是否有資料；只要有 ret_1y + 任一配息率來源即顯示。
                # 無配息資料時顯示 ⬜ 不適用（累積型基金等）。
                try:
                    # v19.177:adr 走 SSOT _resolve_adr_with_fallback 3 層 chain,
                    # 與健診總表 check_eating_principal_1y_mk 同源,免散落。
                    from services.health.dividend import _resolve_adr_with_fallback
                    _kpi_adr, _kpi_adr_src = _resolve_adr_with_fallback({
                        "moneydj_raw": mj_raw,
                        "metrics": m,
                        "dividends": divs,
                    })
                    # v18.134: 改用 compute_1y_total_return 共用 helper
                    # 修使用者反饋「Tab2 跟 Tab3 對同一基金顯示不同 1Y 報酬」
                    # 統一順序：perf["1Y"] > ret_1y_total > ret_1y > NAV
                    from ui.helpers.macro_helpers import compute_1y_total_return
                    _kpi_tr1y, _kpi_tr1y_src = compute_1y_total_return({
                        "metrics": m,
                        "moneydj_raw": mj_raw,
                        "series": s,
                        "perf_source": fd.get("perf_source") or mj_raw.get("perf_source"),
                    })
                    # 必修 2:欄位標籤說實話 —— 線上實測「1Y 含息 = −2.71%」其實只用了
                    # 本地 42 天序列(calc_metrics.ret_1y_window_days),硬掛「1Y」讓 user
                    # 無從察覺它與同畫面 Sharpe(wb07 官方一年)不是同一期間(§1)。
                    # 只在「值確實來自本地短窗」時改標;官方 wb01 真 1Y 不動。
                    # 2026-08-10:判定片語改吃 SSOT（來源標籤已白話化，原本比對的
                    # 「本地」「NAV 序列」字樣不再出現）。涵蓋範圍不變 —— 常數的
                    # docstring 明列哪三條會改標、哪一條刻意不改。
                    from services.fund_total_return import (  # noqa: PLC0415
                        LOCAL_WINDOW_SENSITIVE_HINTS as _LOCAL_WIN_HINTS,
                    )
                    _kpi_tr_label = "1Y 含息報酬"
                    _kpi_win_d = (m or {}).get("ret_1y_window_days")
                    if (isinstance(_kpi_win_d, (int, float)) and _kpi_win_d < 350
                            and any(_t in str(_kpi_tr1y_src or "")
                                    for _t in _LOCAL_WIN_HINTS)):
                        _kpi_tr_label = f"{int(_kpi_win_d)} 天含息報酬(非 1Y)"

                    # `nav_warning`（1Y 淨值跌破 NAV_DROP_WARNING_PCT 的獨立早期警訊）
                    # 原本只印在下方配息區的警示框裡；那個框與本橫幅同源同輸入、
                    # 結論逐字相同（理由見下方「配息覆蓋率講義卡」上方那段說明），
                    # 已移除以免同頁講兩次；但它獨有的這一句必須留下來，
                    # 否則就變成「去重把揭露一起刪掉」。
                    _kpi_nav_warn = ""
                    if _kpi_adr is None or _kpi_adr <= 0:
                        _kpi_icon, _kpi_color, _kpi_bg = "⬜", TRAFFIC_NEUTRAL, GH_BG_CARD
                        _kpi_title = "吃本金檢查 — ⬜ 不適用"
                        _kpi_msg = "本基金無年化配息率資料（可能為累積型 / 不配息基金）"
                        _kpi_cov_txt = "—"
                    elif _kpi_tr1y is None:
                        _kpi_icon, _kpi_color, _kpi_bg = "⬜", TRAFFIC_NEUTRAL, GH_BG_CARD
                        _kpi_title = "吃本金檢查 — ⬜ 資料不足"
                        _kpi_msg = "缺含息總報酬（1Y），無法計算 Coverage"
                        _kpi_cov_txt = "—"
                    else:
                        _kpi_ds = div_safety_check(
                            total_return=_kpi_tr1y,
                            dividend_yield=_kpi_adr,
                            nav_change=_kpi_tr1y,
                        )
                        _kpi_al = _kpi_ds.get("alert_level", "grey")
                        _kpi_cov = _kpi_ds.get("coverage")
                        _kpi_color = {"red": MATERIAL_RED, "yellow": MATERIAL_ORANGE,
                                      "green": MATERIAL_GREEN}.get(_kpi_al, TRAFFIC_NEUTRAL)
                        _kpi_bg = {"red": BG_DARK_RED_1, "yellow": BG_DARK_AMBER_1,
                                   "green": BG_DARK_GREEN_1}.get(_kpi_al, GH_BG_CARD)
                        _kpi_icon = {"red": "🔴", "yellow": "🟡",
                                     "green": "🟢"}.get(_kpi_al, "⬜")
                        _kpi_title = f"吃本金檢查 — {_kpi_icon} {_kpi_ds.get('status','')}"
                        _kpi_msg = _kpi_ds.get("message", "")
                        # v19.178:_src_note dict 過時清掉(舊 key 'perf'/'nav_actual'/
                        # 'nav_annualized_*' v19.175 後皆不命中 → fallback 文字自相矛盾)。
                        # SSOT compute_1y_total_return 已回**使用者看得懂的白話**
                        # (官方 / 各種自算口徑 / 缺值,見該模組頂部常數),直接顯示即可。
                        if _kpi_tr1y_src and _kpi_tr1y_src not in ("metrics", "—", ""):
                            _kpi_msg = f"{_kpi_msg}　〔1Y 來源:{_kpi_tr1y_src}〕"
                        _kpi_cov_txt = (f"{_kpi_cov:.2f}" if _kpi_cov is not None
                                        else "—")
                        _kpi_nav_warn = _kpi_ds.get("nav_warning") or ""

                    st.markdown(
                        f"<div style='background:{_kpi_bg};border:2px solid {_kpi_color};"
                        f"border-radius:12px;padding:12px 16px;margin:10px 0'>"
                        f"<div style='color:{_kpi_color};font-size:13px;font-weight:800;"
                        f"margin-bottom:8px'>{_kpi_title}</div>"
                        f"<div style='display:flex;gap:24px;flex-wrap:wrap'>"
                        f"<div><div style='color:{TRAFFIC_NEUTRAL};font-size:10px'>{_kpi_tr_label}</div>"
                        f"<div style='color:{WHITE};font-weight:700;font-size:16px'>"
                        f"{(f'{_kpi_tr1y:.2f}%' if _kpi_tr1y is not None else '—')}</div></div>"
                        f"<div><div style='color:{TRAFFIC_NEUTRAL};font-size:10px'>年化配息率</div>"
                        f"<div style='color:{WHITE};font-weight:700;font-size:16px'>"
                        f"{(f'{_kpi_adr:.2f}%' if _kpi_adr and _kpi_adr > 0 else '—')}</div></div>"
                        f"<div><div style='color:{TRAFFIC_NEUTRAL};font-size:10px'>Coverage</div>"
                        f"<div style='color:{_kpi_color};font-weight:700;font-size:16px'>"
                        f"{_kpi_cov_txt}</div></div>"
                        f"</div>"
                        f"<div style='color:{GRAY_AA};font-size:11px;margin-top:6px'>{_kpi_msg}</div>"
                        + (f"<div style='color:{MATERIAL_ORANGE};font-size:10px;margin-top:4px'>"
                           f"{_kpi_nav_warn}</div>" if _kpi_nav_warn else "")
                        + "</div>", unsafe_allow_html=True)
                except Exception as _kpi_e:  # noqa: BLE001
                    st.caption(f"吃本金 KPI 計算異常：{str(_kpi_e)[:60]}")

                # v19.181:📊 進階指標(入門 KPI 之外的細項 — Sortino/Calmar/Alpha/Expense
                # /MaxDD/3Y-5Y 年化/3-3-3 篩/MK 換標的建議)— 共用 fund_health_report SSOT,
                # 跨 Tab3/健診 同源。
                try:
                    # v19.182:預設展開,user 第一眼就看到(原 v19.181 expanded=False 收起來
                    # 容易被忽略 — user 反饋「沒看到進階指標」)。
                    # 本次(原則 1)再進一步:「永遠展開的摺疊殼」對使用者而言與沒有殼
                    # 無異,卻仍佔一行標題列高度並暗示「這裡可以收起來」。既然結論
                    # 資料本來就不該闔上,直接改成標題 + container。
                    st.markdown(
                        "#### 📊 進階指標"
                        "(Sortino / Calmar / Alpha / Expense / 3Y-5Y / 3-3-3 / 換標的建議)")
                    with st.container():
                        from services.health.report import (
                            build_dividend_summary_row,
                            build_health_analysis_row,
                        )
                        _adv_fd = {
                            "moneydj_raw": mj_raw,
                            "metrics": m,
                            "series": s,
                            "dividends": divs,
                            "perf_source": fd.get("perf_source") or mj_raw.get("perf_source"),
                            "fund_name": fd.get("fund_name") or mj_raw.get("fund_name") or fk,
                        }
                        # v19.186 fix:本檔局部代碼變數為 fk(L234),非 code → 修 NameError
                        _adv_code = fk or fd.get("fund_code", "?")
                        _adv_h = build_health_analysis_row(_adv_fd, _adv_code)
                        _adv_d = build_dividend_summary_row(_adv_fd, _adv_code, principal_twd=None)

                        # v19.225 P1-1 leftover:inline _fmt_pct 收口至 shared/converters.fmt_pct SSOT
                        # (non-ratio + decimals=2 + plus=False 對應原 "{v:.2f}%")
                        def _fmt_pct(v):
                            from shared.converters import fmt_pct
                            return fmt_pct(v, plus=False, decimals=2, ratio=False)
                        def _fmt_num(v):
                            return f"{v:.2f}" if isinstance(v, (int, float)) else "—"

                        # ── 期間誠實化(必修 2):標籤由 risk_metric_meta 決定 ──────
                        # 線上實測「Sharpe 1Y = 0.28」其實來自 wb07 官方欄,而同畫面的
                        # 「1Y 含息 = −2.71%」只用了本地 42 天序列 —— 欄位硬掛「1Y」
                        # 讓 user 無從察覺兩個數字不同期間(§1)。以下標籤一律標出
                        # **實際**來源與窗長;wb07 六個月欄更是絕對不能再叫「1Y」。
                        _rmm = (m or {}).get("risk_metric_meta") or {}

                        def _meta_of(_k: str) -> dict:
                            _v = _rmm.get(_k)
                            return _v if isinstance(_v, dict) else {}

                        def _lbl_with_period(base: str, key: str) -> str:
                            _mt = _meta_of(key)
                            _src = _mt.get("source")
                            if not _src:
                                return f"{base}(—)"
                            if str(_src).startswith("wb07"):
                                _wb_span = {"wb07_1y": "1Y", "wb07_6m": "6M"}.get(_src, "?")
                                return f"{base} {_wb_span}(wb07)"
                            _d = _mt.get("period_days")
                            return (f"{base} {_d}d(自算)" if isinstance(_d, int)
                                    else f"{base}(自算)")

                        st.markdown("##### 🩺 健康分析(4D Grade + 6 進階指標)")
                        cA, cB, cC, cD = st.columns(4)
                        cA.metric("4D Grade", _adv_h.get("4D Grade") or "—",
                                  help="A≥80 / B≥65 / C≥50 / D≥35 / F<35(SSOT v19.177)")
                        cB.metric("4D Score", _fmt_num(_adv_h.get("4D Score")))
                        cC.metric(_lbl_with_period("Sharpe", "sharpe"),
                                  _fmt_num(_adv_h.get("Sharpe 1Y")),
                                  help=("期間/來源:"
                                        + str(_meta_of("sharpe").get("period_label") or "—")
                                        + ";見下方風險指標對帳"))
                        cD.metric(_lbl_with_period("Sortino", "sortino"),
                                  _fmt_num(_adv_h.get("Sortino")),
                                  help=str(_meta_of("sortino").get("definition") or "—"))

                        cE, cF, cG, cH = st.columns(4)
                        cE.metric(_lbl_with_period("Calmar", "calmar"),
                                  _fmt_num(_adv_h.get("Calmar")),
                                  help=("分子分母同源:3Y 年化含息報酬 "
                                        f"{_meta_of('calmar').get('ret_3y_ann_tr_pct')}% / "
                                        f"|3Y 回撤 {_meta_of('calmar').get('max_dd_3y_pct')}%|"))
                        cF.metric("真實收益 %", _fmt_pct(_adv_h.get("Alpha %")),
                                  help="含息報酬率 − 年化配息率（≠ CAPM Alpha）")
                        cG.metric("費用率 %", _fmt_pct(_adv_h.get("費用率 %")))
                        cH.metric(_lbl_with_period("Max DD %", "max_drawdown"),
                                  _fmt_pct(_adv_h.get("Max DD %")))

                        # 混期示警(必修 2):`mixed_period_warning` 原本 production
                        # **0 reader** —— 只有 fund_service 自己與 test 讀,線上那個
                        # 「Sharpe 1Y 0.28 vs 1Y 含息 −2.71%」的矛盾畫面照舊。此處接上。
                        _mix_warn = _rmm.get("mixed_period_warning")
                        if _mix_warn:
                            st.markdown(
                                f"<div style='font-size:11px;color:{MATERIAL_RED};"
                                f"padding:5px 10px;background:{BG_DARK_RED_1};"
                                f"border-radius:4px;margin:4px 0 8px 0'>"
                                f"⚠️ {_mix_warn}</div>",
                                unsafe_allow_html=True)

                        cI, cJ, cK = st.columns(3)
                        cI.metric("3Y 年化 %", _fmt_pct(_adv_h.get("3Y 年化 %")))
                        cJ.metric("5Y 年化 %", _fmt_pct(_adv_h.get("5Y 年化 %")))
                        cK.metric("MK 3-3-3", _adv_h.get("MK 3-3-3", "⬜"))

                        st.markdown("##### 💰 換標的建議(MK 4 規則心型警結合)")
                        st.markdown(
                            f"**{_adv_d.get('換標的建議', '⬜ 資料不足')}**　"
                            f"<span style='color:{TRAFFIC_NEUTRAL};font-size:11px'>"
                            f"{_adv_d.get('_換標的 detail', '')}</span>",
                            unsafe_allow_html=True,
                        )
                        st.caption(
                            "MK 4 規則:(a) 吃本金且持有 ≥ 1 年 / (b) 4D Grade F / "
                            "(c) 3-3-3 未通過且持有 ≥ 3 年 / (d) Sharpe<0 且 max_dd<-30%。"
                            "任一中 → 🔴 換 / 1-2 觀察 → 🟡 / 全未中 → 🟢。"
                            "**Tab2 單檔無 user 持有期 → (a)(c) 用基金成立年數判定**。"
                        )
                        # v19.191:對齊「資料診斷」面板 — 進階指標各欄位「—」的原因揭露。
                        # user 看了知道是「資料源真沒提供」還是「歷史長度不足」。
                        # 必修 4:門檻文案改吃 calc_metrics SSOT 常數 + meta reason,
                        # 不再寫死已過時的 60 筆 / 1Y fallback(§1 無法察覺的矛盾)。
                        from services.fund_service import (
                            MIN_DOWNSIDE_OBS_SORTINO as _MD_SORT,
                            MIN_OBS_CALMAR as _MO_CAL,
                            MIN_OBS_MAX_DRAWDOWN as _MO_MDD,
                            MIN_OBS_SHARPE_SORTINO as _MO_SS,
                        )

                        def _reason_or(key: str, default: str) -> str:
                            return str(_meta_of(key).get("reason") or default)

                        _miss = []
                        if _adv_h.get("Sharpe 1Y") is None:
                            _miss.append(
                                "Sharpe(" + _reason_or(
                                    "sharpe",
                                    f"需 wb07 官方值,或本地 NAV ≥ {_MO_SS} 交易日") + ")")
                        if _adv_h.get("Sortino") is None:
                            _miss.append(
                                "Sortino(" + _reason_or(
                                    "sortino",
                                    f"需 NAV ≥ {_MO_SS} 交易日 + ≥{_MD_SORT} 筆低於 MAR") + ")")
                        if _adv_h.get("Calmar") is None:
                            _miss.append(
                                "Calmar(" + _reason_or(
                                    "calmar",
                                    f"需 NAV ≥ {_MO_CAL} 交易日 = 3Y,無 1Y fallback") + ")")
                        if _adv_h.get("Max DD %") is None:
                            _miss.append(
                                "Max DD(" + _reason_or(
                                    "max_drawdown", f"需 NAV ≥ {_MO_MDD} 交易日") + ")")
                        if _adv_h.get("Alpha %") is None:
                            _miss.append("真實收益(需 perf.1Y + 年化配息率)")
                        if _adv_h.get("費用率 %") is None:
                            _miss.append("費用率(MoneyDJ wb01 mgmt_fee fallback)")
                        if _adv_h.get("3Y 年化 %") is None:
                            _miss.append("3Y 年化(需 NAV ≥ 3 年)")
                        if _adv_h.get("5Y 年化 %") is None:
                            _miss.append("5Y 年化(需 NAV ≥ 5 年)")
                        if _miss:
                            st.caption(
                                "🔍 **「—」欄位原因**:"
                                + " · ".join(_miss)
                                + "(對齊資料診斷面板)"
                            )
                except Exception as _adv_e:  # noqa: BLE001
                    st.caption(f"⬜ 進階指標渲染失敗:{type(_adv_e).__name__}: {str(_adv_e)[:60]}")

                st.markdown("### ③ 風險指標 & 配息")
                # 關鍵指標 + 配息
                col_a, col_b = st.columns(2)
                with col_a:
                    st.markdown("#### 📊 風險指標")
                    risk_tbl = mj_raw.get("risk_metrics",{}).get("risk_table",{})
                    # v19.336 M9:與 partial 視圖共用 _risk_1y_rows_html(原兩套同款 HTML)
                    st.markdown(_risk_1y_rows_html(risk_tbl, label_style="long"),
                                unsafe_allow_html=True)
                    # ── 必修 2:混期示警 + 對帳降級揭露(沿用 v19.91 chip 樣式)──
                    # 這兩條原本 production 0 reader:`mixed_period_warning` 只有
                    # fund_service 自己與 test 讀,所以線上「Sharpe 1Y 0.28」與
                    # 「1Y 含息 −2.71%」的矛盾畫面完全沒被揭露(§1)。
                    _rm_meta = (m or {}).get("risk_metric_meta") or {}
                    _sh_meta = _rm_meta.get("sharpe") if isinstance(
                        _rm_meta.get("sharpe"), dict) else {}
                    _mix_w = _rm_meta.get("mixed_period_warning")
                    if _mix_w:
                        st.markdown(
                            f"<div style='font-size:10px;color:{MATERIAL_RED};"
                            f"padding:3px 10px;background:{BG_DARK_RED_1};"
                            f"border-radius:4px;margin:2px 0 6px 0'>⚠️ {_mix_w}</div>",
                            unsafe_allow_html=True)
                    if _sh_meta.get("period_label"):
                        st.markdown(
                            f"<div style='font-size:10px;color:{TRAFFIC_NEUTRAL};"
                            f"padding:3px 10px;background:{GH_BG_PRIMARY};"
                            f"border-radius:4px;margin:2px 0 6px 0'>"
                            f"🕒 Sharpe 期間:{_sh_meta['period_label']}</div>",
                            unsafe_allow_html=True)
                    # F-RECON-1 phase 6 v19.91 — Sharpe 對帳 chip(self-calc vs MoneyDJ wb07)
                    _sh_rec = (m or {}).get("sharpe_reconcile")
                    if isinstance(_sh_rec, dict) and _sh_rec.get("status") in _RECON_VALID:
                        _sh_st = _sh_rec.get("status")
                        _sh_color = {"agree": TRAFFIC_GREEN, "disagree": TRAFFIC_RED}.get(_sh_st, TRAFFIC_NEUTRAL)
                        _va, _vb = _sh_rec.get("value_a"), _sh_rec.get("value_b")
                        _va_t = f"{_va:.2f}" if isinstance(_va, (int, float)) else "—"
                        _vb_t = f"{_vb:.2f}" if isinstance(_vb, (int, float)) else "—"
                        # 衝突裁決結果要寫在畫面上(§2.1):meta.source 就是實際被採用的那一邊。
                        _sh_used_src = str(_sh_meta.get("source") or "")
                        if _sh_used_src.startswith("wb07"):
                            _sh_adopt = "上方 Sharpe 採用的是 MoneyDJ wb07 官方值（第三方網站來源優先於本地自算）"
                        elif _sh_used_src:
                            _sh_adopt = f"上方 Sharpe 採用的是本地自算值（來源標記 {_sh_used_src}）"
                        else:
                            _sh_adopt = "上方 Sharpe 未標示來源，無法判斷採用哪一套"
                        st.markdown(
                            f"<div style='font-size:10px;color:{_sh_color};padding:3px 10px;"
                            f"background:{GH_BG_PRIMARY};border-radius:4px;margin:2px 0 6px 0'>"
                            f"{_recon_zh(_sh_st)}｜本地自算={_va_t}　MoneyDJ wb07={_vb_t}<br/>"
                            f"<span style='color:{TRAFFIC_NEUTRAL}'>→ {_sh_adopt}</span>"
                            f"</div>",
                            unsafe_allow_html=True)
                    # C-3:自算 Sharpe 被樣本門檻擋掉時,對帳恆為 a_missing —— chip 只
                    # 顯示「⬜ a_missing」看不出是「本地根本沒算」。顯式說明降級原因,
                    # 否則 §4.3「關鍵指標第二種算法對帳」被靜默關掉(§1)。
                    _rec_blocked = _sh_meta.get("reconcile_blocked_reason")
                    if _rec_blocked:
                        st.markdown(
                            f"<div style='font-size:10px;color:{MATERIAL_ORANGE};"
                            f"padding:3px 10px;background:{GH_BG_PRIMARY};"
                            f"border-radius:4px;margin:2px 0 6px 0'>ℹ️ {_rec_blocked}</div>",
                            unsafe_allow_html=True)
                    # Sharpe 持久性說明（孫慶龍老師框架）
                    # v19.338:M9(v19.336)抽 _risk_1y_rows_html 時 _sh1 定義隨 inline
                    # 區塊移走 → 此處 NameError(except ValueError/TypeError 接不住),
                    # Tab2 完整視圖整段炸(AppTest slow job 抓到)。補回取值。
                    _sh1 = (risk_tbl.get("一年", {}) or {}).get("Sharpe", "—")
                    try:
                        _sh1_v = float(_sh1)
                        if _sh1_v > 0.5:
                            _sh_txt, _sh_c = "優秀（>0.5）持久創造超額報酬", MATERIAL_GREEN
                        elif _sh1_v >= 0:
                            _sh_txt, _sh_c = "普通（0~0.5）勉強補償風險", MATERIAL_ORANGE
                        else:
                            _sh_txt, _sh_c = "差勁（<0）不如持有現金", MATERIAL_RED
                        st.markdown(
                            f"<div style='font-size:10px;color:{_sh_c};padding:3px 10px;"
                            f"background:{GH_BG_PRIMARY};border-radius:4px;margin:2px 0 6px 0'>"
                            f"策略2框架：{_sh_txt}</div>",
                            unsafe_allow_html=True)
                    except (ValueError, TypeError):
                        pass  # smoke-allow-pass
                    # 四分位
                    peer = mj_raw.get("risk_metrics",{}).get("peer_compare",{})
                    qr = _quartile_check(peer, risk_tbl)
                    if qr["quartile"]:
                        _qr_color = qr["color"]
                        _qr_adv = (f"<div style='color:{MATERIAL_ORANGE};font-size:11px;margin-top:4px'>{qr['advice']}</div>"
                                   if qr.get("advice") else "")
                        st.markdown(
                            f"<div style='background:{BG_DARK_NAVY_4};border-radius:8px;padding:8px 12px;margin-top:6px'>"
                            f"<span style='color:{_qr_color};font-weight:700'>{qr['label']}</span>"
                            + _qr_adv + "</div>", unsafe_allow_html=True)
                    # v18.192：教學化 — 風險指標白話文（收合、不藏任何數據）
                    render_metric_explainer(["sharpe", "sigma", "alpha", "beta"])

                with col_b:
                    st.markdown("#### 💸 近期配息")
                    if divs and len(divs) >= 1:
                        # 年化配息率改吃 services.health.dividend 那條三層 SSOT ——
                        # 與同頁「吃本金檢查」橫幅、健康總覽卡完全同源。
                        # 原本這裡是另一份 inline 兩層 fallback,而且末端 `or 0` 會把
                        # 「三層都取不到」變成數值 0 印成 0.00%;但能進到這個分支的前提
                        # 正是「這檔有配息記錄」→ 等於畫面主張「有配息、配息率是零」,
                        # 是 §1 明令禁止的「讓流程看起來成功」。缺值一律顯示破折號。
                        from services.health.dividend import (
                            _resolve_adr_with_fallback as _resolve_adr_t2,
                        )
                        _adr, _adr_src = _resolve_adr_t2({
                            "moneydj_raw": mj_raw,
                            "metrics": m,
                            "dividends": divs,
                        })
                        _adr_src_zh = _ADR_SRC_ZH.get(_adr_src, _adr_src or "—")
                        if _adr is not None and _adr > 0:
                            st.metric("年化配息率", f"{_adr:.2f}%",
                                      help=f"實際採用來源：{_adr_src_zh}")
                        else:
                            st.metric(
                                "年化配息率", "—",
                                help="三層來源（MoneyDJ 官方值 / 本地自算 / 近 12 個月推算）皆無可用值")
                            st.caption(
                                "⬜ **年化配息率無法計算** —— 本檔有配息記錄，但 MoneyDJ 官方欄位、"
                                "本地自算、近 12 個月推算三條路都取不到數字（常見原因：配息紀錄缺"
                                "金額欄、或現值淨值未取得，除不出殖利率）。此處顯示破折號而非 0%，"
                                "0% 會被誤讀成「這檔不配息」。"
                            )
                        # F-RECON-1 phase 6 v19.91 — 配息殖利率對帳 chip(self-calc vs MoneyDJ)
                        _dy_rec = (m or {}).get("div_yield_reconcile")
                        if isinstance(_dy_rec, dict) and _dy_rec.get("status") in _RECON_VALID:
                            _dy_st = _dy_rec.get("status")
                            _dy_color = {"agree": TRAFFIC_GREEN, "disagree": TRAFFIC_RED}.get(_dy_st, TRAFFIC_NEUTRAL)
                            _dva, _dvb = _dy_rec.get("value_a"), _dy_rec.get("value_b")
                            _dva_t = f"{_dva*100:.2f}%" if isinstance(_dva, (int, float)) else "—"
                            _dvb_t = f"{_dvb*100:.2f}%" if isinstance(_dvb, (int, float)) else "—"
                            st.caption(
                                f"<span style='color:{_dy_color};font-size:10px'>"
                                f"{_recon_zh(_dy_st)}｜本地自算={_dva_t}　MoneyDJ={_dvb_t}<br/>"
                                f"→ 上方年化配息率採用：{_adr_src_zh}</span>",
                                unsafe_allow_html=True)
                        for d in divs[:6]:
                            _dt = d.get("date",""); _amt = d.get("amount",""); _yld = d.get("yield_pct","")
                            st.markdown(f"<div style='display:flex;justify-content:space-between;padding:4px 10px;background:{GH_BG_CARD};border-radius:6px;margin:2px 0'><span style='color:{TRAFFIC_NEUTRAL};font-size:11px'>{_dt}</span><span style='font-weight:700'>{_amt}</span><span style='color:{MATERIAL_ORANGE};font-size:11px'>{_yld}</span></div>", unsafe_allow_html=True)

                        # ── 📖 配息覆蓋率講義卡（MK 郭俊宏《以息養股》）──
                        # 這裡原本先印一個「🚨 吃本金警示」框（status + message +
                        # nav_warning），再印下面這張講義卡。那個警示框與本頁上方
                        # 「吃本金檢查」KPI 橫幅**逐字同源**：adr 同一個
                        # `_resolve_adr_with_fallback`、1Y 同一個 `compute_1y_total_return`
                        # 同一份 payload → `div_safety_check` 的回傳必然一模一樣，
                        # 等於同一個結論在同一頁印兩次。
                        #
                        # 留上方 KPI 橫幅、砍這一份，理由：
                        #   (1) 這份被關在 `if divs and len(divs) >= 1:` 內，累積型 /
                        #       MoneyDJ 沒配息頁的基金根本看不到，當不了單一出口；
                        #   (2) 上方橫幅另外處理「⬜ 不適用 / ⬜ 資料不足」兩種缺值狀態，
                        #       並附「1Y 來源」provenance，資訊量嚴格較多；
                        #   (3) 它在主 KPI 列旁，是使用者第一眼看到的位置。
                        # 警示框獨有的 `nav_warning` 已上移到該橫幅，揭露不減少。
                        # 講義卡保留：它講的是**公式與門檻**（教學），不是再講一次結論；
                        # 色/標籤仍讀同一個 `_ds`，與上方橫幅永遠一致。
                        from ui.helpers.macro_helpers import (
                            compute_1y_total_return as _c1ytr_ep,
                        )
                        _tr1y, _ = _c1ytr_ep({
                            "metrics": m,
                            "moneydj_raw": mj_raw,
                            "series": s,
                            "perf_source": fd.get("perf_source") or mj_raw.get("perf_source"),
                        })
                        # `_adr` 現在可能是 None(SSOT 三層全失敗)→ 顯式判空,
                        # 不能沿用舊的 `_adr > 0`(None 直接 TypeError)。
                        if _tr1y is not None and _adr is not None and _adr > 0:
                            _ds = div_safety_check(
                                total_return=float(_tr1y),
                                dividend_yield=float(_adr),
                                nav_change=float(_tr1y),
                            )
                            _al = _ds.get("alert_level","grey")
                            _cov = _ds.get("coverage")
                            _cov_txt = f"{_cov:.2f}" if isinstance(_cov, (int, float)) else "—"
                            _cov_c = {"red":MATERIAL_RED,"yellow":MATERIAL_ORANGE,
                                      "green":MATERIAL_GREEN}.get(_al, TRAFFIC_NEUTRAL)
                            st.markdown(
                                f"<div style='background:{GH_BG_PRIMARY};border:1px dashed {GH_BORDER};"
                                f"border-radius:10px;padding:10px 14px;margin-top:8px'>"
                                f"<div style='color:{TRAFFIC_NEUTRAL};font-size:10px;letter-spacing:1px;margin-bottom:6px'>"
                                f"📖 配息覆蓋率講義 ── 策略3《以息養股》</div>"
                                f"<div style='color:{GRAY_AA};font-size:11px;font-style:italic;"
                                f"border-left:2px solid {GRAY_44};padding-left:8px;margin-bottom:8px'>"
                                f"「高殖利率不等於高報酬，必須確認是否吃本金。」</div>"
                                f"<div style='font-family:monospace;font-size:12px;color:{GH_FG_PRIMARY};margin-bottom:6px'>"
                                f"Coverage = TR₁Y(含息) ÷ 年化配息率<br>"
                                f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
                                f"= {float(_tr1y):.1f}% ÷ {float(_adr):.2f}%"
                                f" = <span style='color:{_cov_c};font-weight:700;font-size:14px'>{_cov_txt}</span></div>"
                                # 去重(原則 2):判定字串本身由本頁上方「吃本金檢查」
                                # KPI 橫幅負責,這裡只留公式與門檻說明(教學)。
                                f"<div style='color:{GRAY_55};font-size:10px'>"
                                f"含息報酬 ≥ 配息率 = 🟢 安全 ｜ 差距 ≤ 2% = 🟡 接近門檻 ｜ 差距 &gt; 2% = 🔴 吃本金</div>"
                                f"</div>", unsafe_allow_html=True)

                    else:
                        st.info("無配息記錄（累積型 / 不配息基金，或 MoneyDJ 未提供配息頁）")

                    # 1Y 報酬對帳 chip —— 原本被關在「有配息記錄」的分支裡,但
                    # `ret_1y_reconcile` 是「本地自算 1Y 報酬 vs MoneyDJ wb01 官方值」
                    # 的比對,和有沒有配息完全無關。累積型 / 不配息基金因此永遠看不到
                    # 這條對帳,即使兩套算法差距很大(§4.3 對帳被靜默關掉)。移出來。
                    _r1y_rec = (m or {}).get("ret_1y_reconcile")
                    if isinstance(_r1y_rec, dict) and _r1y_rec.get("status") in _RECON_VALID:
                        _r1y_st = _r1y_rec.get("status")
                        _r1y_color = {"agree": TRAFFIC_GREEN, "disagree": TRAFFIC_RED}.get(_r1y_st, TRAFFIC_NEUTRAL)
                        _ra, _rb = _r1y_rec.get("value_a"), _r1y_rec.get("value_b")
                        _ra_t = f"{_ra*100:.2f}%" if isinstance(_ra, (int, float)) else "—"
                        _rb_t = f"{_rb*100:.2f}%" if isinstance(_rb, (int, float)) else "—"
                        # 畫面採用哪一個(§2.1 衝突裁決)— 與上方 KPI 橫幅同一個 SSOT。
                        try:
                            from ui.helpers.macro_helpers import (
                                compute_1y_total_return as _c1ytr_rec,
                            )
                            _, _r1y_used_src = _c1ytr_rec({
                                "metrics": m,
                                "moneydj_raw": mj_raw,
                                "series": s,
                                "perf_source": fd.get("perf_source") or mj_raw.get("perf_source"),
                            })
                        except Exception as _e_r1y_src:  # noqa: BLE001
                            import sys as _sys_r1y
                            print(f'[tab2/ret1y-recon] 取用來源標籤失敗: '
                                  f'{type(_e_r1y_src).__name__}: {_e_r1y_src}',
                                  file=_sys_r1y.stderr)
                            _r1y_used_src = ""
                        _r1y_adopt = (f"上方「1Y 含息報酬」採用：{_r1y_used_src}"
                                      if _r1y_used_src and _r1y_used_src not in ("—", "metrics")
                                      else "上方「1Y 含息報酬」未標示來源")
                        st.caption(
                            f"<span style='color:{_r1y_color};font-size:10px'>"
                            f"1Y 報酬對帳：{_recon_zh(_r1y_st)}｜本地自算={_ra_t}　"
                            f"MoneyDJ wb01={_rb_t}<br/>→ {_r1y_adopt}</span>",
                            unsafe_allow_html=True)

                # ── TER 費用率卡（只呈現本檔實際費率，不做同類比較）──────────
                # 這張卡原本還會印一欄「同類均值 x.xx%」與「高於均值 +y.yy%」,
                # 數字來自一份寫死在本檔、自稱是台灣基金市場常見水準的對照表：
                # 無資料源、無抓取時間、無樣本數、無定義(是算術平均？中位數？含不含
                # 保管費？母體是哪一年、哪幾檔？)—— 全都是憑印象填的常數,正是 §1
                # 「自行估一個合理值當常數」與 §3.3 反捏造禁止的東西。畫面上它長得
                # 跟旁邊真的抓來的經理費一模一樣,使用者無從分辨哪個是查來的、哪個
                # 是編的,還會據此做「這檔太貴」的決策 —— 傷害比沒有比較更大。
                #
                # 處置（原則 3+4）：整組比較欄位移除，只留本檔實際費率，並把
                # 「為什麼沒有同類比較」明講。**刻意不去找替代來源硬補**：
                # MoneyDJ / FundClear / TDCC 三個現有基金資料源都沒有提供
                # 「同類型基金平均費用率」欄位，要做就得自行定義同類母體再逐檔
                # 抓費率聚合，那是另一個功能（需先對齊 §7 四點），不是這一輪的範圍。
                _ter_raw = mj_raw.get("mgmt_fee","") or ""
                _ter_cat = mj_raw.get("category","") or ""
                if _ter_raw:
                    try:
                        _ter_val = float(str(_ter_raw).replace("%","").strip())
                    except (ValueError, TypeError):
                        _ter_val = None
                    if _ter_val is not None:
                        st.markdown(
                            f"<div style='background:{GH_BG_CARD};border:1px solid {GH_BORDER};"
                            f"border-radius:10px;padding:10px 16px;margin:8px 0'>"
                            f"<div style='color:{TRAFFIC_NEUTRAL};font-size:11px;margin-bottom:6px'>💰 TER 費用率"
                            + (f" — {_ter_cat[:12]}" if _ter_cat else "") + "</div>"
                            f"<div style='display:flex;gap:24px;flex-wrap:wrap;margin-bottom:6px'>"
                            f"<div><div style='color:{TRAFFIC_NEUTRAL};font-size:10px'>最高經理費（MoneyDJ 基本資料頁）</div>"
                            f"<div style='color:{WHITE};font-weight:700;font-size:16px'>{_ter_val:.2f}%</div></div>"
                            f"</div>"
                            f"<div style='color:{GRAY_55};font-size:10px'>"
                            f"費用率愈低，長期複利效益愈佳（費用每降 1%，20 年後終值多 ~22%＝1.01²⁰ 複利）。"
                            f"</div>"
                            f"</div>", unsafe_allow_html=True)
                        st.caption(
                            "ℹ️ **為什麼這裡沒有「同類均值」比較**：本系統目前接的三個基金資料源"
                            "（MoneyDJ / FundClear / TDCC）都沒有提供「同類型基金平均費用率」這個欄位，"
                            "也沒有可引用的公開統計。與其顯示一個看起來很像查來的、實際是憑印象填的"
                            "數字讓你據此判斷貴不貴，不如誠實留白。要比較費率請直接開兩檔基金並列看"
                            "這一格，或到晨星 / 投信投顧公會查同類清單。"
                        )

                # ── 持股分析（折疊）── v19.282 SSOT:改呼共用 render_holdings_detail;
                # 空持股時顯示三源抓取診斷(不再靜默),expander 永遠顯示(user 要求
                # 單一基金也放持股資訊)。
                from ui.helpers.holdings import (
                    render_holdings_detail, render_holdings_diag,
                )
                _holdings = mj_raw.get("holdings", {}) or {}
                _tops     = _holdings.get("top_holdings", []) or []   # 下方個股新聞 / AI snapshot 用
                _sectors  = _holdings.get("sector_alloc", []) or []   # 下方 AI snapshot 用
                _hdate    = _holdings.get("data_date", "")
                _has_hold = bool(_sectors or _tops)
                with st.expander(
                    "📂 持股分析" + (f"（{_hdate}）" if _hdate else ""),
                    expanded=_has_hold,
                ):
                    if not render_holdings_detail(_holdings):
                        render_holdings_diag(_holdings)

                # ── 📰 個股新聞面（v18.206）：逐股 Google News 搜尋（按鈕）+ AI 新聞面分析 ──
                if _tops:
                    # EX-PASSTHRU-1(v19.377):同 ai.py,fetch_stock_news self-contained news fetcher(見 CLAUDE.md §8.2.A)
                    from repositories.news_repository import (  # noqa: PLC0415
                        fetch_stock_news as _fetch_stk,
                    )
                    _fund_key_sn = str(fk or name or "fund")[:40]
                    _ss_stk = f"_stknews_{_fund_key_sn}"
                    _hold_list = []   # (顯示名, 查詢字)
                    for _topn in _tops[:6]:
                        _nm = str(_topn.get("name", "")).strip()
                        if not _nm:
                            continue
                        _zh = _zh_holding(_nm)
                        _hold_list.append((_zh or _nm[:20], _zh or _nm))
                    # 摺疊處置(原則 1):抓完之後就是「資料」不是「說明」,再讓 user
                    # 多點一次才看得到不合理 → 比照上方持股分析的做法,有內容就展開。
                    with st.expander(f"📰 個股新聞面（前 {len(_hold_list)} 大持股）",
                                     expanded=bool(st.session_state.get(_ss_stk))):
                        _snc1, _snc2 = st.columns([3, 1])
                        _snc1.caption("逐一搜尋 Google News（中文，走 NAS proxy）。"
                                      "廣義 RSS 常抓不到台股/冷門股，此按鈕直接針對每檔持股搜尋。")
                        _do_fetch = _snc2.button(
                            "📡 抓個股新聞", key=f"btn_stknews_{_fund_key_sn}",
                            use_container_width=True)
                        if _do_fetch:
                            _fetched: dict = {}
                            _prog = st.progress(0.0)
                            for _ci, (_disp, _q) in enumerate(_hold_list):
                                try:
                                    _items = _fetch_stk(_q, max_items=3)
                                except Exception:
                                    _items = []
                                if _items:
                                    _fetched[_disp] = _items
                                _prog.progress((_ci + 1) / max(len(_hold_list), 1))
                            _prog.empty()
                            st.session_state[_ss_stk] = _fetched
                        _stk_data = st.session_state.get(_ss_stk)
                        if _stk_data:
                            _tot = sum(len(v) for v in _stk_data.values())
                            st.caption(f"共 {_tot} 則個股新聞（{len(_stk_data)} 檔持股命中）")
                            for _disp_nm, _items in _stk_data.items():
                                for _it in _items:
                                    _u = _it.get("url", "")
                                    _ttl = _it.get("title", "")
                                    _src = _it.get("source", "")
                                    _lh = (f"<a href='{_u}' target='_blank' "
                                           f"style='color:{INFO_BLUE};text-decoration:none'>{_ttl}</a>"
                                           if _u else _ttl)
                                    st.markdown(
                                        f"<div style='padding:4px 8px;background:{GH_BG_CARD};"
                                        f"border-radius:6px;margin:2px 0;font-size:12px'>"
                                        f"<span style='color:{MD_ORANGE_300};font-weight:700'>{_disp_nm}</span>　"
                                        f"{_lh}<span style='color:{GRAY_66};font-size:10px;"
                                        f"margin-left:6px'>{_src}</span></div>",
                                        unsafe_allow_html=True)
                        elif _do_fetch:
                            st.caption("逐股搜尋後仍無結果（可能 NAS Proxy 斷線，"
                                       "或這些持股近期無中文新聞）。")
                        else:
                            st.caption("👆 點「📡 抓個股新聞」開始逐股搜尋。")
                    # v18.207：個股新聞的 AI 分析已併入下方唯一的「④ AI 深度解盤」
                    # （讀 session_state 的 _stknews 一起進全章節快照），此處不再單獨掛 AI。

                # ── V4: 微觀防護盾 — 前十大持倉三率檢核 ────────────────
                _shield_tops = (_holdings.get("top_holdings") or []) if _holdings else []
                if _shield_tops:
                    # 摺疊處置(原則 1):掃描結果是資料,掃完就該看得到,不再要求多點一次。
                    with st.expander(
                        "🛡️ 微觀防護盾 — 持倉三率穿透檢核（V4）",
                        expanded=bool(st.session_state.get(f"shield_{fk}")),
                    ):
                        st.caption(
                            "掃描前十大持倉個股毛利率 / 營業利益率 / 淨利率 QoQ 變化，"
                            "識別「估值虛漲（PE拉高）vs 實質獲利」的 K 型分化陷阱。"
                        )
                        _shield_key = f"shield_{fk}"
                        if st.button("🔍 執行三率穿透掃描", key=f"btn_shield_{fk}"):
                            from services.precision_service import (
                                PrecisionStrategyEngine as _PSE2,
                                three_ratio_row_html as _tr_html,
                            )
                            _pse2 = _PSE2()
                            _shield_results = []
                            with st.spinner(f"正在掃描 {len(_shield_tops)} 檔持倉財報…"):
                                for _sh_top in _shield_tops[:10]:
                                    _sh_name = _sh_top.get("name", "")
                                    _sh_data = _pse2.fetch_stock_three_ratios(_sh_name)
                                    if _sh_data:
                                        _shield_results.append(_sh_data)
                            st.session_state[_shield_key] = _shield_results

                        _cached_shield = st.session_state.get(_shield_key)
                        if _cached_shield is not None:
                            from services.precision_service import (
                                PrecisionStrategyEngine as _PSE2,
                                three_ratio_row_html as _tr_html,
                            )
                            _pse2 = _PSE2()
                            if _cached_shield:
                                # 彙總判斷
                                _overall_verdict = _pse2.evaluate_fund_three_ratios(_cached_shield)
                                _ov_color = (MATERIAL_GREEN if "🟢" in _overall_verdict
                                             else MATERIAL_RED if "🔴" in _overall_verdict
                                             else MATERIAL_ORANGE)
                                st.markdown(
                                    f"<div style='background:{GH_BG_PRIMARY};border:2px solid {_ov_color};"
                                    f"border-radius:10px;padding:10px 16px;margin:8px 0;"
                                    f"font-size:13px;font-weight:700;color:{_ov_color}'>"
                                    f"{_overall_verdict}</div>",
                                    unsafe_allow_html=True)
                                # 逐持倉明細
                                _shield_html = "".join(_tr_html(r) for r in _cached_shield)
                                st.markdown(_shield_html, unsafe_allow_html=True)
                                # 未能解析的持倉列表
                                _resolved_names = {r["stock"] for r in _cached_shield}
                                _failed = [t.get("name","") for t in _shield_tops[:10]
                                           if t.get("name","") not in _resolved_names]
                                if _failed:
                                    st.caption(f"以下持倉 Ticker 無法解析（外幣基金或罕見代碼）：{', '.join(_failed)}")
                            else:
                                st.warning("所有持倉均無法解析 Ticker 或 yfinance 暫無財報，請稍後再試。")

                # v18.260p6：💰 投資試算 — 投入 TWD → 換原幣 → 單位數 / 月配息 TWD / 月配股
                with st.container(border=True):
                    st.markdown("#### 💰 投資試算 — 投入金額 → 單位數 / 配息估算")
                    _ccy_raw = (mj_raw.get("currency") or "TWD").strip() or "TWD"
                    # v19.75 K2：遷移到 services/currency SSOT（mode="yf" 保留 Tab2 既有
                    # 行為：人民幣→CNH 以走 yfinance 較可靠的 CNHTWD=X 報價）。
                    from services.currency import normalize_ccy as _norm_ccy
                    _ccy = _norm_ccy(_ccy_raw, default="TWD", mode="yf")
                    _nav_calc = m.get("nav")
                    # 年化配息率:本區塊原本自己刻了一份兩層 fallback,和上方「近期配息」
                    # 區塊、「吃本金檢查」橫幅各走各的 —— 同一頁三個年化配息率可能是
                    # 三個不同數字。統一改吃 services.health.dividend 那條三層 SSOT,
                    # 並把**實際命中的那一層**帶出來給下方 metric 的 help 用(§2.2):
                    # 原本 help 硬寫「MoneyDJ wb05 官方年化配息率」,但值其實有可能是
                    # 本地自算 —— 那句話會讓使用者以為這個數字有官方背書。
                    from services.health.dividend import (
                        _resolve_adr_with_fallback as _resolve_adr_calc,
                    )
                    _yield_calc, _yield_src = _resolve_adr_calc({
                        "moneydj_raw": mj_raw,
                        "metrics": m,
                        "dividends": divs,
                    })
                    _yield_src_zh = _ADR_SRC_ZH.get(_yield_src, _yield_src or "—")
                    try:
                        _nav_calc = float(_nav_calc) if _nav_calc not in (None, "", "—") else None
                    except (TypeError, ValueError):
                        _nav_calc = None
                    # v18.259：非 TWD 基金抓即時 FX rate（5min TTL，走 NAS proxy）
                    # v18.264：Yahoo 失敗時走 FRED 第二來源（需 FRED_API_KEY）
                    # v18.265：secrets 讀取與 FX 抓取分開 try，避免 secrets 沒設時連 Yahoo 都沒試
                    # v18.278：TWD 基金（不論是「台幣」中文還是「TWD」ISO）直接 fx=1.0 跳過所有 FX 邏輯
                    _fx_to_twd = None
                    _fx_err = ""
                    _fx_manual = False
                    _fx_source = ""  # "Yahoo" / "FRED" / "手動"
                    if _ccy == "TWD":
                        _fx_to_twd = 1.0   # TWD 基金不需換匯
                    elif _ccy != "TWD":
                        # 先讀 FRED key（讀失敗只是少了 fallback，不該擋 Yahoo）
                        import os as _os
                        _fred_k = ""
                        try:
                            _fred_k = st.secrets.get("FRED_API_KEY", "")
                        except Exception:
                            _fred_k = ""
                        if not _fred_k:
                            _fred_k = _os.environ.get("FRED_API_KEY", "")

                        # 抓 FX（Yahoo → FRED fallback chain 內建於 get_latest_fx）
                        try:
                            from services.fund_service import get_latest_fx
                            _fx_to_twd = get_latest_fx(f"{_ccy}TWD=X", fred_api_key=_fred_k)
                            if _fx_to_twd is None or _fx_to_twd <= 0:
                                # v18.275：TWD pair 對應 chain 已精簡為 Yahoo + er-api（其他都已死掉）
                                _fx_err = f"Yahoo / er-api 都暫無 {_ccy}TWD 報價（請至「資料診斷」→ FX 來源診斷查具體失敗源；可能 NAS proxy 暫時不通）"
                                _fx_to_twd = None
                            else:
                                _fx_source = "即時"
                        except Exception as _e:
                            _fx_err = f"FX 抓取失敗：{_e}"
                    _ic1, _ic2 = st.columns([2, 1])
                    with _ic1:
                        _amount_twd = st.number_input(
                            "投入金額（新台幣 TWD）",
                            min_value=10_000, max_value=100_000_000,
                            value=1_000_000, step=100_000,
                            key=f"_calc_amt_{fk}",
                            help="以新台幣計價的投入本金；非 TWD 基金會用即時匯率換成原幣再算單位數與配息。"
                        )
                    with _ic2:
                        st.caption(f"NAV（原幣 {_ccy}）：{_nav_calc if _nav_calc is not None else '—'}")
                        if _yield_calc is not None:
                            st.caption(f"年化配息率：{_yield_calc:.2f} %　（來源：{_yield_src_zh}）")
                        else:
                            st.caption("年化配息率：— （三層來源皆無值，下方不做配息試算）")
                        # v18.278：normalize 後 _ccy 已是 ISO，TWD 基金 _fx_to_twd=1.0 不顯示 FX caption
                        if _ccy == "TWD":
                            st.caption("💰 此基金以新台幣計價（FX = 1）")
                        elif _fx_to_twd:
                            # 自動換匯成功 — user 要求「移除設定匯率的按鈕」
                            st.caption(f"💱 1 {_ccy} = **{_fx_to_twd:.4f}** TWD（即時匯率）")
                        else:
                            # 只有自動失敗才顯示手動 fallback
                            st.caption(f"⚠️ 無法取得 {_ccy}/TWD 即時匯率（{_fx_err}），切換手動模式：")
                            _fx_manual_val = st.number_input(
                                f"手動填 1 {_ccy} = ? TWD",
                                min_value=0.01, max_value=1000.0,
                                value=32.0, step=0.1,
                                key=f"_calc_fx_{fk}",
                                help="自動 FX 抓取失敗時的 fallback；估算僅供參考",
                            )
                            _fx_to_twd = float(_fx_manual_val) if _fx_manual_val > 0 else None
                            _fx_manual = True
                    if _nav_calc and _nav_calc > 0:
                        # TWD → 原幣本金（TWD 基金維持原值）
                        if _ccy != "TWD" and _fx_to_twd:
                            _amt_local = _amount_twd / _fx_to_twd
                        else:
                            _amt_local = float(_amount_twd)
                        _units = _amt_local / _nav_calc
                        _fx_tag = "即時（Yahoo / er-api 雙來源）" if not _fx_manual else "手動"
                        _mc1, _mc2, _mc3, _mc4 = st.columns(4)
                        _mc1.metric("可申購單位數", f"{_units:,.2f}")
                        if _yield_calc and _yield_calc > 0:
                            # v19.324→v19.325：月配息 / 每月配息單位數優先「最近一筆真實配息記錄」，
                            # 真實記錄缺 → 年化配息率估算 fallback，並註記來源（真實/估算）。
                            # 與 Tab3 / 健檢 ② 同源走 dividend_calc。
                            from services.health.dividend_calc import (
                                monthly_dividend_from_records,
                            )
                            _fx_eff2 = _fx_to_twd if (_ccy != "TWD" and _fx_to_twd) else 1.0
                            _mdiv2 = monthly_dividend_from_records(
                                mj_raw.get("dividends") or [], _units, _nav_calc,
                                _fx_eff2, adr_pct=_yield_calc)
                            _src2 = _mdiv2["source"]
                            _latest2 = _mdiv2["latest_div_per_unit"]
                            _has_rec = _src2 == "records"     # 詳細公式 / stash 限真實記錄
                            _has_calc = _mdiv2["mon_div_units"] is not None
                            _mon_div = _mdiv2["mon_div_ccy"] or 0.0       # 月配息(原幣,總額)
                            _mon_div_twd = _mdiv2["mon_div_twd"] or 0.0
                            _mon_units = _mdiv2["mon_div_units"] or 0.0
                            _ann_div = _mon_div * 12.0                    # 年化 = 月配 × 12
                            _ann_div_twd = _mon_div_twd * 12.0
                            _src_lbl2 = "真實記錄" if _has_rec else "年化估算"
                            _mc2.metric("月配息（TWD）",
                                        f"{_mon_div_twd:,.0f}" if _has_calc else "—")
                            _mc3.metric("每月配息單位數",
                                        f"{_mon_units:,.2f}" if _has_calc else "—",
                                        help=f"最近一筆實際配息 × 持有單位 ÷ NAV（來源：{_src_lbl2}）")
                            # §2.2:help 必須說出**這個值實際來自哪一層**。
                            # 原本固定寫「官方」,但走到第二/三層時值是本地算的,
                            # 那句話等於幫自算值掛上官方背書。
                            _mc4.metric("年化配息率", f"{_yield_calc:.2f}%",
                                        help=f"實際採用來源：{_yield_src_zh}")
                            if not _has_calc:
                                st.caption("⬜ 無配息記錄且無年化配息率，無月配試算")
                            else:
                                if _has_rec:
                                    _srcnote2 = (f"📊 配息來源：**真實記錄**"
                                                 f"（最近一筆實配 {_latest2:,.4f} {_ccy}/單位）")
                                else:
                                    _srcnote2 = (f"〜 配息來源：**年化估算**（無逐筆配息記錄，"
                                                 f"以年化配息率 {_yield_calc:.2f}% ÷ 12 攤平，"
                                                 f"季配/年配某些月實際為 0）")
                                if _ccy != "TWD":
                                    st.success(
                                        f"💱 **換算 TWD**（1 {_ccy} = {_fx_to_twd:.4f}，{_fx_tag}）："
                                        f"本金 {_amount_twd:,.0f} TWD → "
                                        f"原幣本金 **{_amt_local:,.2f}** {_ccy} → "
                                        f"可買 **{_units:,.2f}** 單位"
                                        f"（每月 ≈ **{_mon_div_twd:,.0f}** TWD"
                                        f" / 配息單位 ≈ **{_mon_units:,.2f}** 單位）\n\n{_srcnote2}"
                                    )
                                else:
                                    st.success(
                                        f"📌 本金 {_amount_twd:,.0f} TWD → 可買 **{_units:,.2f}** 單位"
                                        f"（每月 ≈ **{_mon_div_twd:,.0f}** TWD"
                                        f" / 配息單位 ≈ **{_mon_units:,.2f}** 單位）\n\n{_srcnote2}"
                                    )

                            # v18.263→v19.324：完整計算公式改「真實配息記錄」版
                            if _has_rec:
                                with st.expander("📐 完整計算公式（含數字代入）", expanded=False):
                                    if _ccy != "TWD" and _fx_to_twd:
                                        _formula_text = (
                                            f"# 投入本金 / 單位數\n"
                                            f"原幣本金   = TWD ÷ FX\n"
                                            f"           = {_amount_twd:,.0f} ÷ {_fx_to_twd:.4f}\n"
                                            f"           = {_amt_local:,.2f} {_ccy}\n"
                                            f"\n"
                                            f"可申購單位 = 原幣本金 ÷ NAV\n"
                                            f"           = {_amt_local:,.2f} ÷ {_nav_calc:.4f}\n"
                                            f"           = {_units:,.2f} 單位\n"
                                            f"\n"
                                            f"# 每月配息（最近一筆真實配息記錄）\n"
                                            f"最近一筆實配 = {_latest2:,.4f} {_ccy}/單位\n"
                                            f"\n"
                                            f"月配息(原幣) = 最近一筆實配 × 持有單位\n"
                                            f"             = {_latest2:,.4f} × {_units:,.2f}\n"
                                            f"             = {_mon_div:,.2f} {_ccy}\n"
                                            f"\n"
                                            f"月配息(TWD)  = 月配息(原幣) × FX\n"
                                            f"             = {_mon_div:,.2f} × {_fx_to_twd:.4f}\n"
                                            f"             = {_mon_div_twd:,.0f} TWD\n"
                                            f"\n"
                                            f"# 每月配息單位數（再投入）\n"
                                            f"配息單位     = 月配息(原幣) ÷ NAV\n"
                                            f"             = {_mon_div:,.2f} ÷ {_nav_calc:.4f}\n"
                                            f"             = {_mon_units:,.2f} 單位\n"
                                        )
                                    else:
                                        _formula_text = (
                                            f"# 投入本金 / 單位數（TWD 計價基金）\n"
                                            f"可申購單位 = TWD ÷ NAV\n"
                                            f"           = {_amount_twd:,.0f} ÷ {_nav_calc:.4f}\n"
                                            f"           = {_units:,.2f} 單位\n"
                                            f"\n"
                                            f"# 每月配息（最近一筆真實配息記錄）\n"
                                            f"最近一筆實配 = {_latest2:,.4f} 元/單位\n"
                                            f"\n"
                                            f"月配息(TWD) = 最近一筆實配 × 持有單位\n"
                                            f"            = {_latest2:,.4f} × {_units:,.2f}\n"
                                            f"            = {_mon_div_twd:,.0f} TWD\n"
                                            f"\n"
                                            f"# 每月配息單位數（再投入）\n"
                                            f"配息單位    = 月配息 ÷ NAV\n"
                                            f"            = {_mon_div_twd:,.0f} ÷ {_nav_calc:.4f}\n"
                                            f"            = {_mon_units:,.2f} 單位\n"
                                        )
                                    st.code(_formula_text, language="text")
                                    st.caption(
                                        "⚠️ 估算假設：(1) 以最近一筆實際配息代表每月配息 "
                                        "(2) FX / NAV 以現值計 (3) 配息 100% 再投入計算配息單位。"
                                        "實際配息以保險公司每月對帳單為準。"
                                    )
                                try:
                                    st.session_state[f"_calc_invest_{fk}"] = {
                                        "amount": float(_amount_twd),
                                        "amount_local": float(_amt_local),
                                        "currency": _ccy,
                                        "nav": float(_nav_calc),
                                        "units": float(_units),
                                        "annual_div_rate": float(_yield_calc),
                                        "latest_div_per_unit": float(_latest2),
                                        "annual_dividend": float(_ann_div),
                                        "monthly_dividend": float(_mon_div),
                                        "monthly_dividend_units": float(_mon_units),
                                        "fx_to_twd": float(_fx_to_twd) if _fx_to_twd else None,
                                        "fx_manual": bool(_fx_manual),
                                        "amount_twd": float(_amount_twd),
                                        "annual_dividend_twd": float(_ann_div_twd),
                                        "monthly_dividend_twd": float(_mon_div_twd),
                                        "fund_type": "income",
                                    }
                                except Exception as _e_inc:
                                    # v19.346 §3.3:原靜默吞 — 配息型試算失敗會讓
                                    # 快照悄悄缺這檔,至少留痕供追查
                                    import sys as _sys_inc
                                    print(f'[tab2/income-calc] 配息型試算失敗: '
                                          f'{type(_e_inc).__name__}: {_e_inc}',
                                          file=_sys_inc.stderr)
                        else:
                            # v19.73 K1：累積型用 1Y 總報酬估市值 — 改走 SSOT compute_1y_total_return
                            # 修補 v18.134 漏接點（原本只用 ret_1y_total/ret_1y 跳過 perf["1Y"] 真 1Y）
                            from ui.helpers.macro_helpers import compute_1y_total_return
                            # payload 補 series / perf_source:同一頁其他三處呼叫都有帶,
                            # 只有這裡漏 → 官方 wb01 與 NAV 序列兩條路都走不到,結果是
                            # 上方「1Y 含息報酬」有數字、這裡「1Y 後預估市值」卻顯示「—」。
                            _ret_1y, _ret_1y_src = compute_1y_total_return({
                                "metrics": m,
                                "moneydj_raw": mj_raw,
                                "series": s,
                                "perf_source": fd.get("perf_source") or mj_raw.get("perf_source"),
                            })
                            _proj_1y = None
                            _proj_1y_twd = None
                            if _ret_1y is not None:
                                _proj_1y = _amt_local * (1 + _ret_1y / 100.0)
                                if _ccy != "TWD" and _fx_to_twd:
                                    _proj_1y_twd = _proj_1y * _fx_to_twd
                                else:
                                    _proj_1y_twd = _proj_1y
                            _mc2.metric("基金類型", "累積型（無配息）")
                            if _proj_1y_twd is not None:
                                _mc3.metric("1Y 後預估市值（TWD）", f"{_proj_1y_twd:,.0f}",
                                            f"{_ret_1y:+.2f}%",
                                            help=f"近 1Y 含息報酬來源：{_ret_1y_src or '—'}")
                                _mc4.metric("1Y 預估損益（TWD）",
                                            f"{(_proj_1y_twd - _amount_twd):+,.0f}")
                            else:
                                _mc3.metric("1Y 後預估市值（TWD）", "—",
                                            help="缺近 1Y 含息報酬（官方 wb01 與本地 NAV 序列皆取不到），不做外推")
                                _mc4.metric("1Y 預估損益（TWD）", "—")
                                st.caption(
                                    "⬜ 缺「近 1Y 含息報酬」→ 不外推 1Y 後市值。"
                                    "外推需要一個真實的年報酬率當基準，硬填 0% 或用不足一年的"
                                    "短窗年化都會讓下面那個金額看起來像預測、實際是編的。"
                                )
                            if _ccy != "TWD":
                                _proj_str = (
                                    f"｜1Y 後預估 **{_proj_1y_twd:,.0f}** TWD"
                                    f"（損益 **{(_proj_1y_twd - _amount_twd):+,.0f}** TWD）"
                                    if _proj_1y_twd is not None else ""
                                )
                                st.success(
                                    f"💱 **換算 TWD**（1 {_ccy} = {_fx_to_twd:.4f}，{_fx_tag}）："
                                    f"本金 {_amount_twd:,.0f} TWD → "
                                    f"原幣本金 **{_amt_local:,.2f}** {_ccy} → "
                                    f"可買 **{_units:,.2f}** 單位"
                                    f"{_proj_str}"
                                )
                            else:
                                _proj_str = (
                                    f"｜1Y 後預估 **{_proj_1y_twd:,.0f}** TWD（{_ret_1y:+.2f}%）"
                                    if _proj_1y_twd is not None else ""
                                )
                                st.caption(
                                    f"📌 本金 {_amount_twd:,.0f} TWD → "
                                    f"可買 **{_units:,.2f}** 單位{_proj_str}"
                                )

                            # v18.263：累積型計算公式
                            with st.expander("📐 完整計算公式（含數字代入）", expanded=False):
                                if _ccy != "TWD" and _fx_to_twd:
                                    _formula_lines = [
                                        "# 投入本金 / 單位數",
                                        "原幣本金   = TWD ÷ FX",
                                        f"           = {_amount_twd:,.0f} ÷ {_fx_to_twd:.4f}",
                                        f"           = {_amt_local:,.2f} {_ccy}",
                                        "",
                                        "可申購單位 = 原幣本金 ÷ NAV",
                                        f"           = {_amt_local:,.2f} ÷ {_nav_calc:.4f}",
                                        f"           = {_units:,.2f} 單位",
                                    ]
                                    if _ret_1y is not None and _proj_1y is not None:
                                        _formula_lines += [
                                            "",
                                            "# 1Y 預估市值（用近 1Y 含息報酬推算）",
                                            "1Y 後原幣  = 原幣本金 × (1 + ret_1Y%)",
                                            f"           = {_amt_local:,.2f} × (1 + {_ret_1y:.2f}%)",
                                            f"           = {_proj_1y:,.2f} {_ccy}",
                                            "",
                                            "1Y 後 TWD  = 1Y 後原幣 × FX",
                                            f"           = {_proj_1y:,.2f} × {_fx_to_twd:.4f}",
                                            f"           = {_proj_1y_twd:,.0f} TWD",
                                            "",
                                            "1Y 預估損益 = 1Y 後 TWD − 本金",
                                            f"            = {_proj_1y_twd:,.0f} − {_amount_twd:,.0f}",
                                            f"            = {(_proj_1y_twd - _amount_twd):+,.0f} TWD",
                                        ]
                                    else:
                                        _formula_lines += [
                                            "",
                                            "# 1Y 預估市值：缺 1Y 含息報酬資料，無法推算",
                                        ]
                                else:
                                    _formula_lines = [
                                        "# 投入本金 / 單位數（TWD 計價基金）",
                                        "可申購單位 = TWD ÷ NAV",
                                        f"           = {_amount_twd:,.0f} ÷ {_nav_calc:.4f}",
                                        f"           = {_units:,.2f} 單位",
                                    ]
                                    if _ret_1y is not None and _proj_1y_twd is not None:
                                        _formula_lines += [
                                            "",
                                            "# 1Y 預估市值",
                                            "1Y 後 TWD  = TWD × (1 + ret_1Y%)",
                                            f"           = {_amount_twd:,.0f} × (1 + {_ret_1y:.2f}%)",
                                            f"           = {_proj_1y_twd:,.0f} TWD",
                                            "",
                                            "1Y 預估損益 = 1Y 後 TWD − 本金",
                                            f"            = {_proj_1y_twd:,.0f} − {_amount_twd:,.0f}",
                                            f"            = {(_proj_1y_twd - _amount_twd):+,.0f} TWD",
                                        ]
                                st.code("\n".join(_formula_lines), language="text")
                                st.caption(
                                    "⚠️ 估算假設：(1) FX 全期不變 (2) 未來報酬等於近 1Y 含息表現 "
                                    "(3) 累積型基金不配息、收益反映在 NAV 上漲。實際結果視市場波動而定。"
                                )
                            try:
                                st.session_state[f"_calc_invest_{fk}"] = {
                                    "amount": float(_amount_twd),
                                    "amount_local": float(_amt_local),
                                    "currency": _ccy,
                                    "nav": float(_nav_calc),
                                    "units": float(_units),
                                    "annual_div_rate": None,
                                    "ret_1y_total": _ret_1y,
                                    "fx_to_twd": float(_fx_to_twd) if _fx_to_twd else None,
                                    "fx_manual": bool(_fx_manual),
                                    "amount_twd": float(_amount_twd),
                                    "proj_1y_twd": float(_proj_1y_twd) if _proj_1y_twd else None,
                                    "fund_type": "accumulation",
                                }
                            except Exception as _e_acc:
                                # v19.346 §3.3:原靜默吞 — 累積型試算失敗至少留痕
                                import sys as _sys_acc
                                print(f'[tab2/accum-calc] 累積型試算失敗: '
                                      f'{type(_e_acc).__name__}: {_e_acc}',
                                      file=_sys_acc.stderr)
                    else:
                        st.info("⚠️ 此基金 NAV 未取得，無法試算單位數。請先確認基本資料區是否成功抓取淨值。")

                # ── MK 3-3-3 原則評估（v19.295）─────────────────────────────
                try:
                    _render_333_fund_expander(s, m, name or fk)
                except Exception as _e333:
                    import sys as _sys333
                    print(f'[tab2/333] render error: {_e333}', file=_sys333.stderr)

                st.markdown("### ④ AI 深度解盤")
                st.divider()
                # v18.207：Tab2「唯一」AI — 統一 render_ai_summary_widget（4 視角），
                # 吃「全章節快照」（基本/績效/風險/配息/買賣點/持股/產業/個股新聞/三率/總經位階）。
                # 原 v18.135 analyze_fund_json 按鈕、個股新聞 AI、末端重複 widget 已整併於此。
                if GEMINI_KEY:
                    from ui.helpers.ai_summary import render_ai_summary_widget  # noqa: PLC0415
                    from repositories.news_repository import (  # noqa: PLC0415
                        infer_asset_class as _infer_ac,
                        filter_news_by_asset_class as _filter_news,
                    )
                    _ai_fd_pct, _ = _calc_data_health()
                    if _ai_fd_pct < 50:
                        st.caption(f"🔴 總經資料完整率 {_ai_fd_pct}%：建議先到「🌐 市場定調」按全量抓取，"
                                   "AI 才有景氣位階背景（仍可直接生成、僅準確度略降）。")
                    elif _ai_fd_pct < 80:
                        st.caption(f"🟡 資料完整率 {_ai_fd_pct}%，AI 參考性略降。")

                    _rt1y = ((mj_raw.get("risk_metrics", {}) or {}).get("risk_table", {}) or {}).get("一年", {}) or {}
                    _snap = [f"## 單一基金全章節快照：{name or fk}"]
                    _snap.append(f"- 基本：類別={mj_raw.get('category','') or '—'}"
                                 f"｜幣別={mj_raw.get('currency','') or '—'}"
                                 f"｜最新淨值={m.get('nav','—')}"
                                 f"｜經理費={mj_raw.get('mgmt_fee','') or '—'}")
                    _perf_bits = [f"{_k}={m.get(_k)}" for _k in
                                  ("ret_1m", "ret_3m", "ret_6m", "ret_1y", "ret_1y_total", "ytd")
                                  if m.get(_k) not in (None, "")]
                    if _perf_bits:
                        _snap.append("- 績效：" + "｜".join(_perf_bits))
                    _risk_bits = [f"{_lbl}={_rt1y.get(_key)}" for _lbl, _key in
                                  (("σ", "標準差"), ("Sharpe", "Sharpe"),
                                   ("Alpha", "Alpha"), ("Beta", "Beta"))
                                  if _rt1y.get(_key) not in (None, "")]
                    if _risk_bits:
                        _snap.append("- 風險(1Y)：" + "｜".join(_risk_bits))
                    # 配息 / 吃本金:這段餵給 AI 的數字原本直接讀 metrics 原始欄位
                    # (ret_1y_total / annual_div_rate),繞過畫面 KPI 用的那兩個 SSOT
                    # (compute_1y_total_return + _resolve_adr_with_fallback)。兩條路
                    # 取到的值不同時,同一頁會出現「畫面 KPI 紅燈說吃本金、AI 解盤說
                    # 配息覆蓋充足」的自打臉。改成與畫面完全同源。
                    from services.health.dividend import (
                        _resolve_adr_with_fallback as _resolve_adr_ai,
                    )
                    from ui.helpers.macro_helpers import (
                        compute_1y_total_return as _c1ytr_ai,
                    )
                    _adr_ai, _adr_ai_src = _resolve_adr_ai({
                        "moneydj_raw": mj_raw, "metrics": m, "dividends": divs,
                    })
                    _tr1y_ai, _tr1y_ai_src = _c1ytr_ai({
                        "metrics": m,
                        "moneydj_raw": mj_raw,
                        "series": s,
                        "perf_source": fd.get("perf_source") or mj_raw.get("perf_source"),
                    })
                    if _adr_ai is not None and _adr_ai > 0:
                        _div_line = (
                            f"- 配息：年化配息率≈{_adr_ai:.2f}%"
                            f"（來源 {_ADR_SRC_ZH.get(_adr_ai_src, _adr_ai_src or '—')}）"
                            f"，近期 {len(divs)} 筆"
                        )
                        if _tr1y_ai is None:
                            _div_line += "｜吃本金：無法判定（缺 1Y 含息總報酬，禁止推測）"
                        else:
                            try:  # 吃本金檢查（含息總報酬 vs 配息率）— Core Protocol Ch.3.2
                                _ds_ai = div_safety_check(
                                    total_return=_tr1y_ai,
                                    dividend_yield=_adr_ai,
                                    nav_change=_tr1y_ai,
                                )
                                _cov_ai = _ds_ai.get("coverage")
                                _div_line += (
                                    f"｜1Y 含息總報酬={_tr1y_ai:.2f}%"
                                    f"（來源 {_tr1y_ai_src or '—'}）"
                                )
                                if _cov_ai is not None:
                                    _div_line += (
                                        f"｜吃本金 coverage={_cov_ai:.2f}"
                                        f"（{_ds_ai.get('alert_level','')}／"
                                        f"{_ds_ai.get('status','')}）"
                                        "｜此結論與畫面上「吃本金檢查」橫幅同源，請勿另行推翻"
                                    )
                            except Exception as _e_dsafe:
                                # v19.346 §3.3:原靜默吞 — AI 快照少掉吃本金線索,留痕
                                import sys as _sys_ds
                                print(f'[tab2/ai-divsafety] 吃本金檢查失敗: '
                                      f'{type(_e_dsafe).__name__}: {_e_dsafe}',
                                      file=_sys_ds.stderr)
                                _div_line += "｜吃本金：計算失敗，無法判定"
                        _snap.append(_div_line)
                    elif divs:
                        _snap.append(
                            f"- 配息：有 {len(divs)} 筆配息記錄，但年化配息率三層來源皆無值"
                            "→ 吃本金無法判定（不得推測）"
                        )
                    _bs = [f"{_k}={m.get(_k)}" for _k in
                           ("buy1", "buy2", "buy3", "sell1", "sell2", "sell3",
                            "bb_upper", "bb_lower", "ma60")
                           if m.get(_k) not in (None, "")]
                    if _bs:
                        _snap.append("- 買賣點/技術：" + "｜".join(_bs))
                    # σ 絕對位階（HWM）— 由淨值序列重算，AI 才知「現價 vs 歷史高點」
                    if s is not None:
                        try:
                            _hwm_ai = calc_hwm_sigma_levels(s, lookback=252)
                            if isinstance(_hwm_ai, dict) and "error" not in _hwm_ai:
                                _snap.append(
                                    f"- σ絕對位階：{_hwm_ai.get('label','')}"
                                    f"｜距HWM={_hwm_ai.get('dist_to_hwm_pct','')}%"
                                    f"｜σ_rank={_hwm_ai.get('sigma_rank','')}")
                        except Exception as _e_hwm:
                            # v19.346 §3.3:原靜默吞 — AI 快照少 σ 位階線索,留痕
                            import sys as _sys_hw
                            print(f'[tab2/ai-hwm] σ絕對位階計算失敗: '
                                  f'{type(_e_hwm).__name__}: {_e_hwm}',
                                  file=_sys_hw.stderr)
                    # 佔比缺值不可寫成 0% —— AI 會把「抓不到佔比」讀成「佔比極低」,
                    # 然後在解盤裡寫「這幾檔權重很小、影響不大」(§1)。缺就明講缺。
                    def _pct_or_unknown(v) -> str:
                        _f = _safe_float(v)
                        return f"{_f:.1f}%" if _f is not None else "佔比未提供"

                    if _tops:
                        _snap.append("- 前10大持股：" + "、".join(
                            f"{_zh_holding(str(_t.get('name',''))) or str(_t.get('name',''))[:14]}"
                            f"({_pct_or_unknown(_t.get('pct'))})" for _t in _tops[:10]))
                    if _sectors:
                        _snap.append("- 產業配置：" + "、".join(
                            f"{str(_s.get('name',''))[:8]} {_pct_or_unknown(_s.get('pct'))}"
                            for _s in _sectors[:5]))
                    _shield_cache_ai = st.session_state.get(f"shield_{fk}")
                    if _shield_cache_ai:
                        _snap.append(f"- 持倉三率穿透：已掃 {len(_shield_cache_ai)} 檔（毛利/營益/淨利 QoQ）")
                    if phase_info_s:
                        _snap.append(f"- 總經背景：位階={phase_info_s.get('phase','')}"
                                     f"（分數 {phase_info_s.get('score','')}）")
                    # v18.260p6：投資試算 stash → AI 解盤可引用 TWD 月配息/月配股
                    _calc_stash = st.session_state.get(f"_calc_invest_{fk}") or {}
                    if _calc_stash:
                        _cs_ccy = _calc_stash.get("currency", "")
                        _cs_amt_twd = _calc_stash.get("amount_twd") or _calc_stash.get("amount", 0)
                        _cs_amt_local = _calc_stash.get("amount_local", 0)
                        _cs_units = _calc_stash.get("units", 0)
                        _cs_fx = _calc_stash.get("fx_to_twd")
                        _cs_fx_tag = "手動" if _calc_stash.get("fx_manual") else "Yahoo 即時"
                        if _calc_stash.get("fund_type") == "income":
                            # `or 0` 會把「這一格沒算出來」餵成金額 0 給 AI,AI 只能
                            # 讀成「配息幾乎是零」。缺值一律送字面「未取得」(§1)。
                            def _amt_or_na(v, fmt: str) -> str:
                                _f = _safe_float(v)
                                return format(_f, fmt) if _f is not None else "未取得"

                            _cs_ann_twd = _amt_or_na(_calc_stash.get("annual_dividend_twd"), ",.0f")
                            _cs_mon_twd = _amt_or_na(_calc_stash.get("monthly_dividend_twd"), ",.0f")
                            _cs_mon_units = _amt_or_na(_calc_stash.get("monthly_dividend_units"), ",.2f")
                            _cs_adr = _amt_or_na(_calc_stash.get("annual_div_rate"), ".2f")
                            _line = (
                                f"- 投資試算：本金 {_cs_amt_twd:,.0f} TWD"
                                f"（≈ {_cs_amt_local:,.2f} {_cs_ccy}）→ "
                                f"{_cs_units:,.2f} 單位｜年息 ≈ {_cs_ann_twd} TWD"
                                f"（月 ≈ {_cs_mon_twd} TWD"
                                f" / 月配股 ≈ {_cs_mon_units} 單位）"
                                f"｜年化配息率 {_cs_adr}%"
                            )
                            if _cs_fx and _cs_ccy != "TWD":
                                _line += f"｜TWD 換算（1 {_cs_ccy}={_cs_fx:.4f}，{_cs_fx_tag}）"
                            _snap.append(_line)
                        else:
                            _ret = _calc_stash.get("ret_1y_total")
                            _ret_str = f"｜1Y 含息報酬 {_ret:+.2f}%" if _ret is not None else ""
                            _cs_proj_twd = _calc_stash.get("proj_1y_twd")
                            _proj_str = (
                                f"｜1Y 後預估 {_cs_proj_twd:,.0f} TWD"
                                if _cs_proj_twd else ""
                            )
                            _line = (
                                f"- 投資試算：本金 {_cs_amt_twd:,.0f} TWD"
                                f"（≈ {_cs_amt_local:,.2f} {_cs_ccy}）→ "
                                f"{_cs_units:,.2f} 單位（累積型，無配息）"
                                f"{_ret_str}{_proj_str}"
                            )
                            if _cs_fx and _cs_ccy != "TWD":
                                _line += f"｜TWD 換算（1 {_cs_ccy}={_cs_fx:.4f}，{_cs_fx_tag}）"
                            _snap.append(_line)
                    # 新聞：優先「已逐股抓的個股新聞」，否則退資產類別過濾的廣義新聞
                    _stk_news_ai = st.session_state.get(
                        f"_stknews_{str(fk or name or 'fund')[:40]}") or {}
                    if _stk_news_ai:
                        _hl = [it.get("title", "") for items in _stk_news_ai.values()
                               for it in items][:15]
                        _snap.append(f"- 個股新聞：{len(_hl)} 則（逐股 Google News）")
                    else:
                        _t2cls = _infer_ac(f"{name} {mj_raw.get('category','')}")
                        _hl = [str(n.get("title", "")) for n in
                               _filter_news(st.session_state.get("news_items", []) or [], _t2cls)
                               if isinstance(n, dict)][:8]
                    render_ai_summary_widget(
                        tab_key="tab2",
                        tab_label=f"單一基金（{name or fk}）",
                        snapshot="\n".join(_snap),
                        sections=[
                            "基本資料（類別/幣別/淨值/費用）",
                            "績效表現（近期報酬）",
                            "風險指標（波動/夏普等）",
                            "配息與吃本金檢查",
                            "投資試算（每百萬可申購單位與配息估算）",
                            "買賣點與價格位階",
                            "持股與產業配置",
                            "總經大環境背景",
                            "新聞時事影響",
                        ],
                        headlines=_hl,
                        gemini_api_key=GEMINI_KEY,
                    )


# ══════════════════════════════════════════════════════
# TAB 3 — 組合基金
