"""ui/components/macro_compass_top.py — 總經指南針頂部三卡(C3 拆自 app.py v19.207).

從原 542 LOC orchestrator 抽出:
- _render_compass_card(單張指標卡 UI:值 + Phase 1 訊號燈 + 60D sparkline)
- render_macro_compass(三大美股指標渲染:VIX 恐慌指數 × 美 10Y 殖利率 × S&P 500 vs 60MA)

呼叫站:app.py 在 sidebar 之後、tabs 之前,module-level 直呼 render_macro_compass()。
"""
from __future__ import annotations
from shared.colors import GH_BG_HOVER, GH_BG_PRIMARY, GH_FG_MUTED, GH_FG_PRIMARY  # v19.254 B1 GH_* SSOT
from shared.colors import TRAFFIC_GREEN, TRAFFIC_NEUTRAL, TRAFFIC_RED  # v19.389 V3a:趨勢箭頭色收 SSOT

import pandas as pd
import streamlit as st


def _trend_dir(series: list, lookback: int = 20, threshold_pct: float = 0.03):
    """v19.303: 計算近期趨勢方向。回傳 (arrow_html, arrow_char) 或 ('', '')。
    lookback: 比較最新值 vs N 期前（日資料用 20≈1M，月資料用 3≈一季）。"""
    if not series or len(series) < 4:
        return '', ''
    try:
        lb = min(lookback, len(series) - 1)
        cur, prv = float(series[-1]), float(series[-1 - lb])
        if prv == 0:
            return '', ''
        chg = (cur - prv) / abs(prv)
        if chg > threshold_pct:
            return f'<span style="font-size:11px;color:{TRAFFIC_GREEN};margin-left:5px;">↑ 1M</span>', '↑'
        elif chg < -threshold_pct:
            return f'<span style="font-size:11px;color:{TRAFFIC_RED};margin-left:5px;">↓ 1M</span>', '↓'
        else:
            return f'<span style="font-size:11px;color:{TRAFFIC_NEUTRAL};margin-left:5px;">→ 1M</span>', '→'
    except Exception:
        return '', ''


def _render_compass_card(col, info, title, ticker, fmt='{:.2f}', unit='', show_ma=False):
    """單張指標卡：值 + Phase 1 訊號燈 + 60D sparkline + v19.303 趨勢箭頭。info=None 顯示降級訊息。"""
    if info is None:
        col.markdown(
            f'<div style="background:{GH_BG_PRIMARY};border:1px solid {GH_BG_HOVER};border-radius:8px;padding:10px;height:84px;">'
            f'<div style="font-size:11px;color:{GH_FG_MUTED};">{title}（{ticker}）</div>'
            f'<div style="font-size:13px;color:{GH_FG_MUTED};margin-top:6px;">🔴 未取得（yfinance 暫時失敗）</div>'
            f'</div>', unsafe_allow_html=True)
        return
    val = info.get('value')
    sig = info.get('signal') or ('⚪', '無訊號', GH_FG_MUTED)
    light, label, color = sig[0], sig[1], sig[2]
    val_str = fmt.format(val) + unit if val is not None else 'N/A'
    extra = ''
    if show_ma and info.get('ma60') is not None:
        extra = f' <span style="font-size:10px;color:{GH_FG_MUTED};font-weight:400;">/ 60MA {fmt.format(info["ma60"])}</span>'
    # v19.303: 趨勢箭頭 — 比較當前值與約 1M 前（lookback=20 交易日）
    _trend_html, _ = _trend_dir(info.get('series') or [], lookback=20)
    col.markdown(
        f'<div style="background:{GH_BG_PRIMARY};border:1px solid {color};border-radius:8px;padding:10px;">'
        f'<div style="font-size:11px;color:{GH_FG_MUTED};">{title}（{ticker}）</div>'
        f'<div style="font-size:22px;font-weight:900;color:{GH_FG_PRIMARY};margin:2px 0;">{val_str}{extra}{_trend_html}</div>'
        f'<div style="font-size:11px;font-weight:700;color:{color};">{light} {label}</div>'
        f'</div>', unsafe_allow_html=True)
    ser = info.get('series') or []
    if ser:
        try:
            col.line_chart(pd.Series(ser, name=title), height=80, use_container_width=True)
        except Exception:
            pass  # smoke-allow-pass

def render_macro_compass():
    """頂部三卡：VIX 恐慌指數 × 美 10Y 殖利率 × S&P 500 vs 60MA。
    預設不抓資料（避免顯示過時值誤判），按「📡 抓取最新」按鈕才打 yfinance。
    語意：按鈕當下＝盤面當下＝決策當下真實狀態。"""
    import datetime as _dt_mc

    def _do_fetch():
        try:
            # v19.376 B2b:走 L2 facade(§8.2 硬規則 4:L3 不直呼 L1 fetcher / 不碰 L1 cache 內部)
            from services.macro.compass import refresh_macro_compass
            _data = refresh_macro_compass()
        except Exception as e:
            print(f'[render_macro_compass] fetch failed: {e}')
            _data = {}
        st.session_state['_macro_compass_cache'] = {
            '_ts': _dt_mc.datetime.now(), 'data': _data,
        }

    _cache = st.session_state.get('_macro_compass_cache')
    _has_data = bool(_cache and _cache.get('data'))
    _ts_str = (_cache.get('_ts').strftime('%H:%M:%S')
               if _has_data and _cache.get('_ts') else '尚未抓取')

    _header = st.columns([6, 1])
    _header[0].markdown(
        f'<div style="font-size:14px;font-weight:900;color:{GH_FG_PRIMARY};margin:4px 0 4px;">'
        '🧭 總經指南針 (Top-Down Macro)'
        f'<span style="font-size:10px;color:{GH_FG_MUTED};font-weight:400;margin-left:8px;">'
        f'VIX × 10Y × S&amp;P 500 — {"即將抓取（無快取）" if not _has_data else f"更新於 {_ts_str}"}'
        '</span></div>',
        unsafe_allow_html=True)
    _header[1].button('📡 抓取最新' if not _has_data else '🔄 重抓',
                       key='_compass_fetch_btn', on_click=_do_fetch,
                       use_container_width=True)

    if not _has_data:
        st.info('💡 點擊右上「📡 抓取最新」按鈕載入即時 VIX / 10Y / S&P 500')
        return

    data = _cache.get('data') or {}
    c1, c2, c3 = st.columns(3)
    _render_compass_card(c1, data.get('vix'),  'VIX 恐慌指數',     '^VIX',  fmt='{:.2f}')
    _render_compass_card(c2, data.get('tnx'),  '美 10Y 殖利率',    '^TNX',  fmt='{:.2f}', unit='%')
    _render_compass_card(c3, data.get('gspc'), 'S&P 500 vs 60MA',  '^GSPC', fmt='{:,.2f}', show_ma=True)

# v19.216 BUG-FIX:C3 commit 抽 module-level `render_macro_compass()` 呼叫時
# 連 component 內的 call 一起搬過來,結果 component import 時自動執行一次 +
# app.py:411 又執行一次 → button key='_compass_fetch_btn' 重複 →
# StreamlitDuplicateElementKey。Component 應只 def 不執行,呼叫站留 app.py。
