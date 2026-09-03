"""ui/helpers/fund_grp_health/regime_section.py — 🧭 景氣位階適配區塊(v19.425)。

讀大表列的「景氣適配」欄 + 頁首快取的當前景氣(phase_info)→ 順風/逆風/全景氣/無法判定 計數
+ 列出逆風標的(參考傾向,**非買賣建議**)。三張大表共用。純顯示,零計算(欄已由 unified 算好)。
"""
from __future__ import annotations

import streamlit as st


def render_regime_fit_section(rows: list, *, show_current_regime: bool = True) -> None:
    """🧭 景氣適配摘要:當前景氣 + 四態計數 + 逆風標的清單。rows = 大表列(dict list)。

    Args:
        rows: 大表列(dict list)。
        show_current_regime: 要不要在本區塊**再宣告一次**當前景氣位階。
            預設 True(既有 caller 零行為變化)。

            2026-09-02 T16:② 持倉體檢頁的最上方已經有一條市場環境橫幅
            (`📊 當前總經 Phase：<icon> <phase> <score>/10　<tip>`),它讀的是
            **同一個** `st.session_state["phase_info"]["phase"]` —— 也就是同一個字串
            在同一頁印了兩次,而且兩次的措辭還不一樣(「當前總經 Phase」vs
            「當前景氣位階」),讀起來像兩個不同的東西。② 因此傳 `False`,
            把「現在是什麼位階」這句話**併回**頁首那一行,本區塊只講「適配結果」。

            ⚠️ **預設值刻意留 True**:另一個 caller `ui/tab_batch_analysis.py`
            **沒有**那條橫幅(實測該檔無 `phase_info` 橫幅),對它而言這句話是唯一的
            位階揭露 —— 拿掉會變成「講適配、卻不講對照的是哪個位階」。
    """
    _rows = [r for r in (rows or []) if isinstance(r, dict) and r.get("code")]
    if not _rows:
        return
    _rc = ((st.session_state.get("phase_info") or {}).get("phase")
           if hasattr(st, "session_state") else None)

    st.divider()
    st.markdown("### 🧭 景氣位階適配")
    _lead = (f"當前景氣位階:**{_rc or '未偵測(請先看總經 Tab)'}**。"
             if show_current_regime else "當前景氣位階見本頁最上方的市場環境橫幅。")
    st.caption(_lead + "依各標的資產屬性 + 抗跌/追漲"
               "對照當前景氣 → 參考傾向(**非買賣建議、非 % 配置**)。詳細理由見大表「景氣適配 / 適配傾向」欄。")

    def _has(_r, _kw):
        return _kw in str(_r.get("景氣適配") or "")

    _tail = [r for r in _rows if _has(r, "順風")]
    _head = [r for r in _rows if _has(r, "逆風")]
    _all = [r for r in _rows if _has(r, "全景氣")]
    _na = [r for r in _rows if _has(r, "無法判定")]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("✅ 順風", len(_tail))
    c2.metric("⚠️ 逆風", len(_head))
    c3.metric("⚪ 全景氣", len(_all))
    c4.metric("⬜ 無法判定", len(_na))

    if _head:
        st.caption("⚠️ **逆風**(資產屬性與當前景氣相左,可留意 —— 非賣出訊號):"
                   + "、".join(f"{(r.get('基金名') or r.get('code'))}"
                              f"（適合 {r.get('適配傾向') or '—'}）" for r in _head[:10]))
